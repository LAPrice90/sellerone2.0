from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import (
    duplicate_header_names,
    load_product_db_for_validation,
    normalize_key,
    normalize_text,
    utc_now_iso,
    validate_product_db_dataframe,
)


DEFAULT_SCANNER_SOURCE = ROOT / "out" / "scanner_latest.csv"
DEFAULT_PRODUCT_DB_SOURCE = ROOT / "out" / "product_db_preview.csv"

SCANNER_REQUIRED_COLUMNS: tuple[str, ...] = ("asin", "supplier_sku")
ROW_COLUMNS: tuple[str, ...] = (
    "asin",
    "supplier_sku",
    "candidate_id",
    "exists_in_db",
    "match_count",
    "matched_seller_skus",
    "action",
    "reason",
    "collapsed_duplicate_rows",
    "scanner_duplicate_asin_supplier_skus",
)


def _read_csv_header_raw(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def _read_csv_for_validation(path: Path) -> tuple[pd.DataFrame, list[str]]:
    raw_headers = _read_csv_header_raw(path)
    df = pd.read_csv(path, dtype=str).fillna("")
    return df, raw_headers


def _reason(*parts: str) -> str:
    return "|".join(part for part in parts if part)


def _schema_problem_reasons(
    *,
    source_name: str,
    raw_headers: Iterable[str],
    df: pd.DataFrame,
    required_columns: Iterable[str],
) -> list[str]:
    reasons: list[str] = []
    duplicates = duplicate_header_names(raw_headers)
    if duplicates:
        reasons.append(f"{source_name}_duplicate_headers:" + ",".join(duplicates))
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        reasons.append(f"{source_name}_missing_columns:" + ",".join(missing))
    return reasons


def _product_db_block_reasons(product_validation_checks: list[dict[str, str]]) -> list[str]:
    failed = [
        normalize_text(row.get("check"))
        for row in product_validation_checks
        if normalize_text(row.get("status")).lower() == "fail"
    ]
    return ["product_db_schema_failed:" + ",".join(failed)] if failed else []


def _build_product_db_asin_index(product_db: pd.DataFrame) -> dict[str, list[str]]:
    if "asin" not in product_db.columns or "seller_sku" not in product_db.columns:
        return {}
    index: dict[str, set[str]] = defaultdict(set)
    for _, row in product_db.iterrows():
        asin = normalize_key(row.get("asin", ""))
        sku = normalize_text(row.get("seller_sku", ""))
        if asin and sku:
            index[asin].add(sku)
    return {asin: sorted(skus) for asin, skus in index.items()}


def _dedupe_scanner_rows(scanner: pd.DataFrame) -> list[dict[str, object]]:
    rows_by_key: OrderedDict[tuple[str, str], dict[str, object]] = OrderedDict()
    for _, source_row in scanner.iterrows():
        asin = normalize_key(source_row.get("asin", ""))
        supplier_sku = normalize_text(source_row.get("supplier_sku", ""))
        key = (asin, supplier_sku)
        candidate_id = normalize_text(source_row.get("candidate_id", ""))
        if key not in rows_by_key:
            rows_by_key[key] = {
                "asin": asin,
                "supplier_sku": supplier_sku,
                "candidate_ids": [],
                "source_count": 0,
            }
        row = rows_by_key[key]
        row["source_count"] = int(row["source_count"]) + 1
        if candidate_id:
            candidate_ids = list(row["candidate_ids"])
            candidate_ids.append(candidate_id)
            row["candidate_ids"] = candidate_ids
    return list(rows_by_key.values())


def _scanner_duplicate_asin_context(scanner_rows: list[dict[str, object]]) -> dict[str, str]:
    suppliers_by_asin: dict[str, set[str]] = defaultdict(set)
    for row in scanner_rows:
        asin = normalize_key(row.get("asin", ""))
        supplier_sku = normalize_text(row.get("supplier_sku", ""))
        if asin and supplier_sku:
            suppliers_by_asin[asin].add(supplier_sku)
    return {
        asin: "|".join(sorted(suppliers))
        for asin, suppliers in suppliers_by_asin.items()
        if len(suppliers) > 1
    }


def _simulate_row(
    *,
    scanner_row: dict[str, object],
    asin_index: dict[str, list[str]],
    scanner_duplicate_context: dict[str, str],
    global_block_reasons: list[str],
) -> dict[str, str]:
    asin = normalize_key(scanner_row.get("asin", ""))
    supplier_sku = normalize_text(scanner_row.get("supplier_sku", ""))
    candidate_ids = [normalize_text(value) for value in list(scanner_row.get("candidate_ids", []))]
    candidate_id = "|".join(candidate_id for candidate_id in candidate_ids if candidate_id)
    source_count = int(scanner_row.get("source_count", 1) or 1)
    exact_duplicate_count = max(source_count - 1, 0)

    row_reasons: list[str] = []
    if not asin:
        row_reasons.append("blank_scanner_asin")
    if not supplier_sku:
        row_reasons.append("missing_supplier_sku")
    duplicate_context = scanner_duplicate_context.get(asin, "")
    if duplicate_context:
        row_reasons.append("duplicate_scanner_asin_requires_review")

    matched_skus = asin_index.get(asin, []) if asin else []
    match_count = len(matched_skus)
    exists_in_db = "YES" if match_count else "NO"

    if global_block_reasons:
        action = "BLOCKED"
        reason = _reason(*global_block_reasons, *row_reasons)
    elif row_reasons:
        action = "REVIEW"
        reason = _reason(*row_reasons)
    elif match_count == 0:
        action = "WOULD INSERT"
        reason = "no_product_db_asin_match"
    elif match_count == 1:
        action = "WOULD UPDATE"
        reason = "single_product_db_asin_match"
    else:
        action = "REVIEW"
        reason = "multiple_product_db_asin_matches"

    return {
        "asin": asin,
        "supplier_sku": supplier_sku,
        "candidate_id": candidate_id,
        "exists_in_db": exists_in_db,
        "match_count": str(match_count),
        "matched_seller_skus": "|".join(matched_skus),
        "action": action,
        "reason": reason,
        "collapsed_duplicate_rows": str(exact_duplicate_count),
        "scanner_duplicate_asin_supplier_skus": duplicate_context,
    }


def _empty_payload(
    *,
    status: str,
    observed_utc: str,
    scanner_path: Path,
    product_db_path: Path,
    reason: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "observed_utc": observed_utc,
        "scanner_path": str(scanner_path),
        "product_db_path": str(product_db_path),
        "scanner_rows": 0,
        "simulation_rows": 0,
        "product_db_rows": 0,
        "collapsed_exact_duplicate_rows": 0,
        "action_counts": {},
        "product_db_contract_status": "unknown",
        "block_reasons": [reason],
        "rows": [],
    }


def run_link_simulation(
    *,
    scanner_path: Path = DEFAULT_SCANNER_SOURCE,
    product_db_path: Path = DEFAULT_PRODUCT_DB_SOURCE,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    if not scanner_path.exists():
        return _empty_payload(
            status="fail",
            observed_utc=observed,
            scanner_path=scanner_path,
            product_db_path=product_db_path,
            reason="scanner_source_missing",
        )
    if not product_db_path.exists():
        return _empty_payload(
            status="fail",
            observed_utc=observed,
            scanner_path=scanner_path,
            product_db_path=product_db_path,
            reason="product_db_source_missing",
        )

    scanner, scanner_headers = _read_csv_for_validation(scanner_path)
    product_db, product_headers = load_product_db_for_validation(product_db_path)

    scanner_schema_reasons = _schema_problem_reasons(
        source_name="scanner",
        raw_headers=scanner_headers,
        df=scanner,
        required_columns=SCANNER_REQUIRED_COLUMNS,
    )
    product_validation = validate_product_db_dataframe(
        product_db,
        raw_headers=product_headers,
        source_path=str(product_db_path),
        observed_utc=observed,
    )
    global_block_reasons = [*scanner_schema_reasons, *_product_db_block_reasons(product_validation.checks)]

    scanner_rows = _dedupe_scanner_rows(scanner) if not scanner_schema_reasons else []
    duplicate_context = _scanner_duplicate_asin_context(scanner_rows)
    asin_index = _build_product_db_asin_index(product_db)
    rows = [
        _simulate_row(
            scanner_row=row,
            asin_index=asin_index,
            scanner_duplicate_context=duplicate_context,
            global_block_reasons=global_block_reasons,
        )
        for row in scanner_rows
    ]
    action_counts = dict(sorted(Counter(row["action"] for row in rows).items()))
    collapsed_exact_duplicate_rows = sum(int(row["collapsed_duplicate_rows"] or "0") for row in rows)

    if global_block_reasons:
        status = "fail"
    elif action_counts.get("REVIEW", 0):
        status = "warn"
    else:
        status = "ok"

    return {
        "status": status,
        "observed_utc": observed,
        "scanner_path": str(scanner_path),
        "product_db_path": str(product_db_path),
        "scanner_rows": int(len(scanner.index)),
        "simulation_rows": int(len(rows)),
        "product_db_rows": int(len(product_db.index)),
        "collapsed_exact_duplicate_rows": int(collapsed_exact_duplicate_rows),
        "action_counts": action_counts,
        "product_db_contract_status": product_validation.status,
        "block_reasons": global_block_reasons,
        "rows": rows,
    }


def _output_payload(payload: dict[str, Any], *, include_rows: bool) -> dict[str, Any]:
    if include_rows:
        return payload
    return {key: value for key, value in payload.items() if key != "rows"}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Simulate scanner to Product DB link actions without writing SQL, CSV, "
            "Google Sheets, or Product DB records."
        )
    )
    parser.add_argument("--scanner", default=str(DEFAULT_SCANNER_SOURCE), help="Scanner CSV to classify.")
    parser.add_argument("--product-db", default=str(DEFAULT_PRODUCT_DB_SOURCE), help="Product DB CSV to read.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--include-rows", action="store_true", help="Include simulated row decisions in JSON output.")
    parser.add_argument("--sample-size", type=int, default=10, help="Rows to show in text mode.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_link_simulation(
        scanner_path=Path(args.scanner),
        product_db_path=Path(args.product_db),
    )
    if args.format == "json":
        print(json.dumps(_output_payload(payload, include_rows=bool(args.include_rows)), indent=2, ensure_ascii=True))
    else:
        print(f"status={payload['status']}")
        print(f"scanner_rows={payload['scanner_rows']}")
        print(f"simulation_rows={payload['simulation_rows']}")
        print(f"product_db_rows={payload['product_db_rows']}")
        print(f"collapsed_exact_duplicate_rows={payload['collapsed_exact_duplicate_rows']}")
        print(f"product_db_contract_status={payload['product_db_contract_status']}")
        print(f"action_counts={json.dumps(payload['action_counts'], ensure_ascii=True, sort_keys=True)}")
        print(f"block_reasons={json.dumps(payload['block_reasons'], ensure_ascii=True)}")
        sample_size = max(int(args.sample_size), 0)
        for row in payload["rows"][:sample_size]:
            print(
                "row="
                + json.dumps(
                    {column: row.get(column, "") for column in ROW_COLUMNS},
                    ensure_ascii=True,
                    sort_keys=True,
                )
            )
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
