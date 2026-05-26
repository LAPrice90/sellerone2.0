from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import (
    duplicate_header_names,
    normalize_key,
    normalize_text,
    utc_now_iso,
)


DEFAULT_SCANNER_SOURCE = ROOT / "out" / "scanner_latest.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"

REQUIRED_COLUMNS: tuple[str, ...] = ("asin", "supplier_sku")
DETAIL_COLUMNS: tuple[str, ...] = (
    "asin",
    "supplier_sku",
    "row_count",
    "candidate_ids",
    "status",
    "reason",
)
ASIN_CONTEXT_COLUMNS: tuple[str, ...] = (
    "asin",
    "supplier_sku_count",
    "supplier_skus",
    "status",
    "reason",
)


def _read_csv_header_raw(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle), [])


def _schema_reasons(scanner: pd.DataFrame, raw_headers: list[str]) -> list[str]:
    reasons: list[str] = []
    duplicates = duplicate_header_names(raw_headers)
    if duplicates:
        reasons.append("scanner_duplicate_headers:" + ",".join(duplicates))
    missing = [column for column in REQUIRED_COLUMNS if column not in scanner.columns]
    if missing:
        reasons.append("scanner_missing_columns:" + ",".join(missing))
    return reasons


def _empty_payload(*, scanner_path: Path, observed_utc: str, reason: str) -> dict[str, Any]:
    return {
        "status": "fail",
        "observed_utc": observed_utc,
        "scanner_path": str(scanner_path),
        "scanner_rows": 0,
        "unique_asin_supplier_keys": 0,
        "exact_duplicate_key_count": 0,
        "exact_duplicate_extra_rows": 0,
        "same_asin_different_supplier_sku_count": 0,
        "blank_asin_rows": 0,
        "missing_supplier_sku_rows": 0,
        "check_counts": {"fail": 1},
        "block_reasons": [reason],
        "detail_rows": [],
        "asin_context_rows": [],
    }


def run_scanner_identity_check(
    *,
    scanner_path: Path = DEFAULT_SCANNER_SOURCE,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    if not scanner_path.exists():
        return _empty_payload(scanner_path=scanner_path, observed_utc=observed, reason="scanner_source_missing")

    raw_headers = _read_csv_header_raw(scanner_path)
    scanner = pd.read_csv(scanner_path, dtype=str).fillna("")
    schema_reasons = _schema_reasons(scanner, raw_headers)
    if schema_reasons:
        return {
            **_empty_payload(scanner_path=scanner_path, observed_utc=observed, reason="scanner_schema_failed"),
            "scanner_rows": int(len(scanner.index)),
            "block_reasons": schema_reasons,
        }

    key_rows: dict[tuple[str, str], dict[str, Any]] = {}
    asin_to_supplier_skus: dict[str, set[str]] = defaultdict(set)
    blank_asin_rows = 0
    missing_supplier_sku_rows = 0

    for _, source_row in scanner.iterrows():
        asin = normalize_key(source_row.get("asin", ""))
        supplier_sku = normalize_text(source_row.get("supplier_sku", ""))
        candidate_id = normalize_text(source_row.get("candidate_id", ""))
        if not asin:
            blank_asin_rows += 1
        if not supplier_sku:
            missing_supplier_sku_rows += 1
        if asin and supplier_sku:
            asin_to_supplier_skus[asin].add(supplier_sku)
        key = (asin, supplier_sku)
        if key not in key_rows:
            key_rows[key] = {
                "asin": asin,
                "supplier_sku": supplier_sku,
                "row_count": 0,
                "candidate_ids": [],
            }
        key_rows[key]["row_count"] += 1
        if candidate_id:
            key_rows[key]["candidate_ids"].append(candidate_id)

    detail_rows: list[dict[str, str]] = []
    exact_duplicate_key_count = 0
    exact_duplicate_extra_rows = 0
    for row in key_rows.values():
        row_count = int(row["row_count"])
        reason = ""
        status = "ok"
        if row_count > 1:
            status = "fail"
            reason = "duplicate_asin_supplier_sku"
            exact_duplicate_key_count += 1
            exact_duplicate_extra_rows += row_count - 1
        if not row["asin"]:
            status = "warn" if status == "ok" else status
            reason = "|".join(part for part in [reason, "blank_asin"] if part)
        if not row["supplier_sku"]:
            status = "warn" if status == "ok" else status
            reason = "|".join(part for part in [reason, "missing_supplier_sku"] if part)
        detail_rows.append(
            {
                "asin": str(row["asin"]),
                "supplier_sku": str(row["supplier_sku"]),
                "row_count": str(row_count),
                "candidate_ids": "|".join(row["candidate_ids"]),
                "status": status,
                "reason": reason,
            }
        )

    asin_context_rows: list[dict[str, str]] = []
    for asin, supplier_skus in sorted(asin_to_supplier_skus.items()):
        if len(supplier_skus) <= 1:
            continue
        asin_context_rows.append(
            {
                "asin": asin,
                "supplier_sku_count": str(len(supplier_skus)),
                "supplier_skus": "|".join(sorted(supplier_skus)),
                "status": "info",
                "reason": "same_asin_different_supplier_sku_separate_products",
            }
        )

    check_counts = dict(sorted(Counter(row["status"] for row in detail_rows).items()))
    status = "fail" if exact_duplicate_key_count else "warn" if blank_asin_rows or missing_supplier_sku_rows else "ok"

    return {
        "status": status,
        "observed_utc": observed,
        "scanner_path": str(scanner_path),
        "scanner_rows": int(len(scanner.index)),
        "unique_asin_supplier_keys": int(len(key_rows)),
        "exact_duplicate_key_count": int(exact_duplicate_key_count),
        "exact_duplicate_extra_rows": int(exact_duplicate_extra_rows),
        "same_asin_different_supplier_sku_count": int(len(asin_context_rows)),
        "blank_asin_rows": int(blank_asin_rows),
        "missing_supplier_sku_rows": int(missing_supplier_sku_rows),
        "check_counts": check_counts,
        "block_reasons": [],
        "detail_rows": detail_rows,
        "asin_context_rows": asin_context_rows,
    }


def write_outputs(payload: dict[str, Any], *, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / "scanner_identity_check.csv"
    context_path = output_dir / "scanner_same_asin_context.csv"
    summary_path = output_dir / "scanner_identity_check_summary.json"
    pd.DataFrame(payload["detail_rows"], columns=DETAIL_COLUMNS).to_csv(detail_path, index=False)
    pd.DataFrame(payload["asin_context_rows"], columns=ASIN_CONTEXT_COLUMNS).to_csv(context_path, index=False)
    summary = {key: value for key, value in payload.items() if key not in {"detail_rows", "asin_context_rows"}}
    summary["outputs"] = {
        "detail": str(detail_path),
        "same_asin_context": str(context_path),
        "summary": str(summary_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return summary["outputs"]


def _output_payload(payload: dict[str, Any], *, include_rows: bool) -> dict[str, Any]:
    if include_rows:
        return payload
    return {key: value for key, value in payload.items() if key not in {"detail_rows", "asin_context_rows"}}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check scanner identity uniqueness for asin + supplier_sku.")
    parser.add_argument("--scanner", default=str(DEFAULT_SCANNER_SOURCE), help="Scanner CSV to check.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for local proof outputs.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--include-rows", action="store_true", help="Include detail rows in JSON output.")
    parser.add_argument("--no-write", action="store_true", help="Do not write local proof outputs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_scanner_identity_check(scanner_path=Path(args.scanner))
    outputs: dict[str, str] = {}
    if not args.no_write:
        outputs = write_outputs(payload, output_dir=Path(args.output_dir))
    payload_with_outputs = {**payload, "outputs": outputs}
    if args.format == "json":
        print(json.dumps(_output_payload(payload_with_outputs, include_rows=bool(args.include_rows)), indent=2, ensure_ascii=True))
    else:
        print(f"status={payload['status']}")
        print(f"scanner_rows={payload['scanner_rows']}")
        print(f"unique_asin_supplier_keys={payload['unique_asin_supplier_keys']}")
        print(f"exact_duplicate_key_count={payload['exact_duplicate_key_count']}")
        print(f"same_asin_different_supplier_sku_count={payload['same_asin_different_supplier_sku_count']}")
        print(f"blank_asin_rows={payload['blank_asin_rows']}")
        print(f"missing_supplier_sku_rows={payload['missing_supplier_sku_rows']}")
        print(f"outputs={json.dumps(outputs, ensure_ascii=True, sort_keys=True)}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
