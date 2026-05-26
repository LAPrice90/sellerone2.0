from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import (
    load_product_db_for_validation,
    normalize_key,
    normalize_text,
    utc_now_iso,
    validate_product_db_dataframe,
)
from scripts.one_off.P009_product_db_link_simulation import (
    DEFAULT_PRODUCT_DB_SOURCE,
    DEFAULT_SCANNER_SOURCE,
    run_link_simulation,
)


DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_DUPLICATE_ASIN_OUTPUT = DEFAULT_OUTPUT_DIR / "product_db_duplicate_asin_classification_review.csv"
DEFAULT_SCANNER_LINK_OUTPUT = DEFAULT_OUTPUT_DIR / "scanner_product_db_link_review.csv"
DEFAULT_SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "product_db_review_pack_summary.json"

DUPLICATE_ASIN_REVIEW_COLUMNS: tuple[str, ...] = (
    "asin",
    "match_count",
    "seller_skus",
    "sale_statuses",
    "active_seller_skus",
    "inactive_or_blank_seller_skus",
    "title_count",
    "titles",
    "supplier_codes",
    "supplier_names",
    "supplier_pack_sizes",
    "amazon_pack_sizes",
    "stock_totals",
    "suggested_classification",
    "classification_status",
    "reason",
    "required_next_action",
)

SCANNER_LINK_REVIEW_COLUMNS: tuple[str, ...] = (
    "asin",
    "supplier_sku",
    "candidate_id",
    "scanner_action",
    "review_bucket",
    "reason",
    "exists_in_db",
    "match_count",
    "matched_seller_skus",
    "scanner_duplicate_asin_supplier_skus",
    "title",
    "brand",
    "cost",
    "buy_box_price",
    "pf",
    "recommendation_status",
    "required_next_action",
)


def _unique_join(values: list[object]) -> str:
    cleaned = sorted({normalize_text(value) for value in values if normalize_text(value)})
    return "|".join(cleaned)


def _ordered_join(values: list[object]) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = normalize_text(value)
        if not text or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return "|".join(ordered)


def _normalized_title(value: object) -> str:
    return " ".join(normalize_text(value).lower().split())


def _seller_skus_for_status(group: pd.DataFrame, statuses: set[str]) -> list[str]:
    rows: list[str] = []
    for _, row in group.iterrows():
        status = normalize_text(row.get("sale_status", "")).lower()
        sku = normalize_text(row.get("seller_sku", ""))
        if sku and status in statuses:
            rows.append(sku)
    return rows


def _suggest_duplicate_asin_classification(group: pd.DataFrame) -> tuple[str, str, str]:
    if "duplicate_asin_reason" in group.columns:
        reasons = [normalize_text(value) for value in group["duplicate_asin_reason"].tolist()]
        unique_reasons = sorted({reason for reason in reasons if reason})
        if reasons and all(reasons) and unique_reasons:
            return (
                unique_reasons[0] if len(unique_reasons) == 1 else "multiple_recorded_duplicate_asin_reasons",
                "classified",
                "duplicate_asin_business_reason_recorded",
            )
    status_series = group.get("sale_status", pd.Series([""] * len(group.index))).map(normalize_text).str.lower()
    statuses = [status for status in status_series.tolist() if status]
    active_count = sum(1 for status in statuses if status == "active")
    inactive_count = sum(1 for status in statuses if status in {"dropped", "discontinued"})
    blank_status_count = int(status_series.eq("").sum())
    titles = {_normalized_title(value) for value in group.get("title", pd.Series([], dtype=str)).tolist() if _normalized_title(value)}

    if active_count == 0 and inactive_count > 0 and blank_status_count == 0:
        return (
            "inactive_duplicate_candidate",
            "needs_user_decision",
            "all_duplicate_asin_rows_are_inactive_or_dropped",
        )
    if active_count <= 1 and inactive_count > 0 and len(titles) <= 1:
        return (
            "legacy_or_replacement_listing_candidate",
            "needs_user_decision",
            "one_or_zero_active_rows_with_matching_titles_and_inactive_legacy_rows",
        )
    if len(titles) > 1:
        return (
            "possible_catalog_collision",
            "needs_user_decision",
            "duplicate_asin_rows_have_different_titles",
        )
    return (
        "manual_classification_required",
        "needs_user_decision",
        "duplicate_asin_requires_business_reason_before_automated_linking",
    )


def build_duplicate_asin_review(product_db: pd.DataFrame) -> list[dict[str, str]]:
    if product_db.empty or "asin" not in product_db.columns or "seller_sku" not in product_db.columns:
        return []
    work = product_db.copy()
    work["_asin_key"] = work["asin"].map(normalize_key)
    work["_seller_sku_key"] = work["seller_sku"].map(normalize_text)
    work = work.loc[work["_asin_key"].ne("") & work["_seller_sku_key"].ne("")].copy()
    rows: list[dict[str, str]] = []
    for asin, group in work.groupby("_asin_key", sort=True):
        seller_skus = sorted(set(group["_seller_sku_key"].tolist()))
        if len(seller_skus) <= 1:
            continue
        suggested, status, reason = _suggest_duplicate_asin_classification(group)
        title_values = group.get("title", pd.Series([], dtype=str)).tolist()
        active_skus = _seller_skus_for_status(group, {"active"})
        inactive_skus = [
            normalize_text(row.get("seller_sku", ""))
            for _, row in group.iterrows()
            if normalize_text(row.get("seller_sku", ""))
            and normalize_text(row.get("sale_status", "")).lower() != "active"
        ]
        rows.append(
            {
                "asin": asin,
                "match_count": str(len(seller_skus)),
                "seller_skus": "|".join(seller_skus),
                "sale_statuses": _unique_join(group.get("sale_status", pd.Series([], dtype=str)).tolist()),
                "active_seller_skus": "|".join(sorted(set(active_skus))),
                "inactive_or_blank_seller_skus": "|".join(sorted(set(inactive_skus))),
                "title_count": str(len({_normalized_title(value) for value in title_values if _normalized_title(value)})),
                "titles": _ordered_join(title_values),
                "supplier_codes": _unique_join(group.get("supplier_code", pd.Series([], dtype=str)).tolist()),
                "supplier_names": _unique_join(group.get("supplier_name", pd.Series([], dtype=str)).tolist()),
                "supplier_pack_sizes": _unique_join(group.get("supplier_pack_size", pd.Series([], dtype=str)).tolist()),
                "amazon_pack_sizes": _unique_join(group.get("amazon_pack_size", pd.Series([], dtype=str)).tolist()),
                "stock_totals": _unique_join(group.get("stock_total", pd.Series([], dtype=str)).tolist()),
                "suggested_classification": suggested,
                "classification_status": status,
                "reason": reason,
                "required_next_action": "choose_duplicate_asin_business_reason_or_cleanup_action",
            }
        )
    return rows


def _scanner_lookup(scanner_path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    if not scanner_path.exists():
        return {}
    df = pd.read_csv(scanner_path, dtype=str).fillna("")
    lookup: dict[tuple[str, str, str], dict[str, str]] = {}
    for _, row in df.iterrows():
        asin = normalize_key(row.get("asin", ""))
        supplier_sku = normalize_text(row.get("supplier_sku", ""))
        candidate_id = normalize_text(row.get("candidate_id", ""))
        lookup[(asin, supplier_sku, candidate_id)] = {str(key): normalize_text(value) for key, value in row.to_dict().items()}
    return lookup


def _scanner_review_bucket(link_row: dict[str, str]) -> tuple[str, str]:
    action = normalize_text(link_row.get("action"))
    reason = normalize_text(link_row.get("reason"))
    if action == "WOULD INSERT":
        return "new_product_create_review", "review_candidate_before_product_db_insert"
    if action == "REVIEW" and "duplicate_scanner_asin_requires_review" in reason:
        return "duplicate_scanner_asin_review", "choose_one_supplier_row_or_keep_both_with_reason"
    if action == "REVIEW":
        return "manual_link_review", "resolve_review_reason_before_product_db_action"
    if action == "WOULD UPDATE":
        return "existing_product_update_review", "review_candidate_before_product_db_update"
    if action == "BLOCKED":
        return "blocked", "fix_schema_or_source_block_before_review"
    return "unknown", "review_unclassified_link_action"


def build_scanner_link_review(
    *,
    scanner_path: Path,
    link_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    lookup = _scanner_lookup(scanner_path)
    review_rows: list[dict[str, str]] = []
    for link_row in link_rows:
        candidate_ids = [value for value in normalize_text(link_row.get("candidate_id")).split("|") if value]
        if not candidate_ids:
            candidate_ids = [""]
        for candidate_id in candidate_ids:
            key = (
                normalize_key(link_row.get("asin", "")),
                normalize_text(link_row.get("supplier_sku", "")),
                candidate_id,
            )
            scanner_row = lookup.get(key, {})
            bucket, next_action = _scanner_review_bucket(link_row)
            review_rows.append(
                {
                    "asin": normalize_key(link_row.get("asin", "")),
                    "supplier_sku": normalize_text(link_row.get("supplier_sku", "")),
                    "candidate_id": candidate_id,
                    "scanner_action": normalize_text(link_row.get("action")),
                    "review_bucket": bucket,
                    "reason": normalize_text(link_row.get("reason")),
                    "exists_in_db": normalize_text(link_row.get("exists_in_db")),
                    "match_count": normalize_text(link_row.get("match_count")),
                    "matched_seller_skus": normalize_text(link_row.get("matched_seller_skus")),
                    "scanner_duplicate_asin_supplier_skus": normalize_text(
                        link_row.get("scanner_duplicate_asin_supplier_skus")
                    ),
                    "title": normalize_text(scanner_row.get("title", "")),
                    "brand": normalize_text(scanner_row.get("brand", "")),
                    "cost": normalize_text(scanner_row.get("cost", "")),
                    "buy_box_price": normalize_text(scanner_row.get("buy_box_price", "")),
                    "pf": normalize_text(scanner_row.get("pf", "")),
                    "recommendation_status": normalize_text(scanner_row.get("recommendation_status", "")),
                    "required_next_action": next_action,
                }
            )
    return review_rows


def run_review_pack(
    *,
    scanner_path: Path = DEFAULT_SCANNER_SOURCE,
    product_db_path: Path = DEFAULT_PRODUCT_DB_SOURCE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    duplicate_output = output_dir / DEFAULT_DUPLICATE_ASIN_OUTPUT.name
    scanner_output = output_dir / DEFAULT_SCANNER_LINK_OUTPUT.name
    summary_output = output_dir / DEFAULT_SUMMARY_OUTPUT.name

    if not product_db_path.exists() or not scanner_path.exists():
        payload = {
            "status": "fail",
            "observed_utc": observed,
            "scanner_path": str(scanner_path),
            "product_db_path": str(product_db_path),
            "reason": "missing_source_file",
            "duplicate_asin_review_rows": 0,
            "scanner_link_review_rows": 0,
            "outputs": {
                "duplicate_asin_review": str(duplicate_output),
                "scanner_link_review": str(scanner_output),
                "summary": str(summary_output),
            },
        }
        pd.DataFrame(columns=DUPLICATE_ASIN_REVIEW_COLUMNS).to_csv(duplicate_output, index=False)
        pd.DataFrame(columns=SCANNER_LINK_REVIEW_COLUMNS).to_csv(scanner_output, index=False)
        summary_output.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    product_db, product_headers = load_product_db_for_validation(product_db_path)
    product_validation = validate_product_db_dataframe(
        product_db,
        raw_headers=product_headers,
        source_path=str(product_db_path),
        observed_utc=observed,
    )
    link_payload = run_link_simulation(
        scanner_path=scanner_path,
        product_db_path=product_db_path,
        observed_utc=observed,
    )

    duplicate_rows = build_duplicate_asin_review(product_db)
    scanner_rows = build_scanner_link_review(scanner_path=scanner_path, link_rows=list(link_payload.get("rows", [])))
    pd.DataFrame(duplicate_rows, columns=DUPLICATE_ASIN_REVIEW_COLUMNS).to_csv(duplicate_output, index=False)
    pd.DataFrame(scanner_rows, columns=SCANNER_LINK_REVIEW_COLUMNS).to_csv(scanner_output, index=False)

    scanner_action_counts = dict(sorted(Counter(row.get("scanner_action", "") for row in scanner_rows).items()))
    duplicate_suggestions = dict(
        sorted(Counter(row.get("suggested_classification", "") for row in duplicate_rows).items())
    )
    status = "fail" if product_validation.status == "fail" or link_payload.get("status") == "fail" else "warn"
    if not duplicate_rows and not scanner_action_counts.get("REVIEW", 0):
        status = "ok"

    payload = {
        "status": status,
        "observed_utc": observed,
        "scanner_path": str(scanner_path),
        "product_db_path": str(product_db_path),
        "product_db_contract_status": product_validation.status,
        "scanner_link_status": link_payload.get("status", ""),
        "product_db_rows": int(len(product_db.index)),
        "scanner_rows": int(link_payload.get("scanner_rows", 0)),
        "duplicate_asin_review_rows": int(len(duplicate_rows)),
        "scanner_link_review_rows": int(len(scanner_rows)),
        "scanner_action_counts": scanner_action_counts,
        "duplicate_asin_suggestion_counts": duplicate_suggestions,
        "outputs": {
            "duplicate_asin_review": str(duplicate_output),
            "scanner_link_review": str(scanner_output),
            "summary": str(summary_output),
        },
    }
    summary_output.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local review pack for Product DB duplicate ASINs and scanner link candidates."
    )
    parser.add_argument("--scanner", default=str(DEFAULT_SCANNER_SOURCE), help="Scanner CSV to review.")
    parser.add_argument("--product-db", default=str(DEFAULT_PRODUCT_DB_SOURCE), help="Product DB CSV to review.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for local review outputs.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_review_pack(
        scanner_path=Path(args.scanner),
        product_db_path=Path(args.product_db),
        output_dir=Path(args.output_dir),
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        for key, value in payload.items():
            if isinstance(value, dict):
                print(f"{key}={json.dumps(value, ensure_ascii=True, sort_keys=True)}")
            else:
                print(f"{key}={value}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
