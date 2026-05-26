from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.core.storage import read_review_pack_dataframe


DEFAULT_PASS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
DEFAULT_NEAR_MISS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_uk_review_signal_audit_latest.csv"

OUTPUT_COLUMNS = [
    "asin",
    "candidate_id",
    "supplier_sku",
    "review_pack_type",
    "uk_review_code",
    "uk_review_recommended_action",
    "uk_review_supporting_codes",
    "uk_reviews",
    "variant_reviews",
    "expected_units_next_30d",
    "expected_profit_next_30d_gbp",
    "evidence_source",
]

VALID_UK_REVIEW_CODES = {
    "uk_reviews_lt3",
    "uk_reviews_3_to_5",
    "uk_reviews_6_to_9",
    "uk_reviews_10_plus",
    "uk_reviews_missing",
}

UK_REVIEW_ACTIONS = {
    "uk_reviews_lt3": "remove_from_clean_pass",
    "uk_reviews_3_to_5": "manual_review",
    "uk_reviews_6_to_9": "supporting_evidence_only",
    "uk_reviews_10_plus": "allow_if_other_checks_pass",
    "uk_reviews_missing": "targeted_rescan_needed",
}


@dataclass(frozen=True)
class UkReviewSignalAuditResult:
    audit_df: pd.DataFrame
    output_path: Path
    report: dict[str, Any]


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_review_pack(path: Path, pack_type: str) -> pd.DataFrame:
    return read_review_pack_dataframe(path, pack_type=pack_type, dtype=str).fillna("")


def _parse_float(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    cleaned = text.replace(",", "").replace("GBP", "").replace("gbp", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_to_text(value: float | int | None) -> str:
    if value is None:
        return ""
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _latest_records(
    df: pd.DataFrame,
    *,
    key_columns: list[str],
    utc_columns: list[str],
) -> dict[tuple[str, ...], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    for column in key_columns + utc_columns:
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)

    utc_sort = None
    for column in utc_columns:
        parsed = pd.to_datetime(work[column], errors="coerce", utc=True, format="mixed")
        utc_sort = parsed if utc_sort is None else utc_sort.fillna(parsed)
    if utc_sort is not None:
        work["_utc_sort"] = utc_sort
        work = work.sort_values(by=["_utc_sort"], ascending=[False], kind="stable")

    latest: dict[tuple[str, ...], dict[str, str]] = {}
    for _, row in work.iterrows():
        key = tuple(_normalize_key(row.get(column, "")) for column in key_columns)
        if any(part == "" for part in key):
            continue
        if key in latest:
            continue
        latest[key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return latest


def _lookup_latest(
    *,
    candidate_id: str,
    supplier_sku: str,
    asin: str,
    by_candidate: dict[tuple[str, ...], dict[str, str]],
    by_supplier_asin: dict[tuple[str, ...], dict[str, str]],
    by_asin: dict[tuple[str, ...], dict[str, str]],
) -> dict[str, str]:
    candidate_key = (_normalize_key(candidate_id),)
    supplier_asin_key = (_normalize_key(supplier_sku), _normalize_key(asin))
    asin_key = (_normalize_key(asin),)
    if candidate_key in by_candidate:
        return by_candidate[candidate_key]
    if supplier_asin_key in by_supplier_asin:
        return by_supplier_asin[supplier_asin_key]
    if asin_key in by_asin:
        return by_asin[asin_key]
    return {}


def _classify_uk_review_code(uk_reviews: float | None) -> str:
    if uk_reviews is None:
        return "uk_reviews_missing"
    if uk_reviews < 3:
        return "uk_reviews_lt3"
    if uk_reviews < 6:
        return "uk_reviews_3_to_5"
    if uk_reviews < 10:
        return "uk_reviews_6_to_9"
    return "uk_reviews_10_plus"


def _pick_uk_reviews(source_row: dict[str, str], scrape_row: dict[str, str]) -> tuple[float | None, str]:
    source_uk = _parse_float(source_row.get("uk_reviews", ""))
    if source_uk is not None:
        return source_uk, "f_live_price_file_pass_or_near_miss_review_latest.csv:uk_reviews"

    source_hist_uk = _parse_float(source_row.get("historical_uk_reviews", ""))
    if source_hist_uk is not None:
        return source_hist_uk, "f_live_price_file_pass_or_near_miss_review_latest.csv:historical_uk_reviews"

    scrape_hist_uk = _parse_float(scrape_row.get("historical_uk_reviews", ""))
    if scrape_hist_uk is not None:
        return scrape_hist_uk, "feeder_legacy_scrape_evidence_live.csv:historical_uk_reviews"

    return None, "historical_uk_reviews_missing_in_stored_artifacts"


def _pick_variant_reviews(source_row: dict[str, str], scrape_row: dict[str, str]) -> float | None:
    for column in ("variant_reviews", "matching_variant_reviews"):
        source_value = _parse_float(source_row.get(column, ""))
        if source_value is not None:
            return source_value
    for column in ("variant_reviews", "matching_variant_reviews"):
        scrape_value = _parse_float(scrape_row.get(column, ""))
        if scrape_value is not None:
            return scrape_value
    return None


def _build_row(
    *,
    source_row: dict[str, str],
    review_pack_type: str,
    scrape_row: dict[str, str],
) -> dict[str, str]:
    uk_reviews, evidence_source = _pick_uk_reviews(source_row, scrape_row)
    uk_review_code = _classify_uk_review_code(uk_reviews)
    recommended_action = UK_REVIEW_ACTIONS[uk_review_code]
    variant_reviews = _pick_variant_reviews(source_row, scrape_row)

    expected_units = _parse_float(source_row.get("expected_units_next_30d", ""))
    expected_profit = _parse_float(source_row.get("expected_profit_next_30d_gbp", ""))
    if expected_profit is None:
        expected_profit = _parse_float(source_row.get("estimated_monthly_profit_gbp", ""))

    return {
        "asin": _normalize_text(source_row.get("asin", "")),
        "candidate_id": _normalize_text(source_row.get("candidate_id", "")),
        "supplier_sku": _normalize_text(source_row.get("supplier_sku", "")),
        "review_pack_type": review_pack_type,
        "uk_review_code": uk_review_code,
        "uk_review_recommended_action": recommended_action,
        "uk_review_supporting_codes": uk_review_code,
        "uk_reviews": _num_to_text(uk_reviews),
        "variant_reviews": _num_to_text(variant_reviews),
        "expected_units_next_30d": _num_to_text(expected_units),
        "expected_profit_next_30d_gbp": _num_to_text(expected_profit),
        "evidence_source": evidence_source,
    }


def build_uk_review_signal_audit(
    *,
    pass_path: Path = DEFAULT_PASS_PATH,
    near_miss_path: Path = DEFAULT_NEAR_MISS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> UkReviewSignalAuditResult:
    pass_df = _read_review_pack(pass_path, "passes")
    near_miss_df = _read_review_pack(near_miss_path, "near_misses")
    scrape_df = _read_csv(scrape_evidence_path)

    scrape_by_candidate = _latest_records(scrape_df, key_columns=["candidate_id"], utc_columns=["observed_utc", "scan_day"])
    scrape_by_supplier_asin = _latest_records(
        scrape_df,
        key_columns=["supplier_sku", "asin"],
        utc_columns=["observed_utc", "scan_day"],
    )
    scrape_by_asin = _latest_records(scrape_df, key_columns=["asin"], utc_columns=["observed_utc", "scan_day"])

    output_rows: list[dict[str, str]] = []
    for review_pack_type, source_df in (("passes", pass_df), ("near_misses", near_miss_df)):
        if source_df.empty:
            continue
        for _, row in source_df.iterrows():
            source_row = {column: _normalize_text(value) for column, value in row.to_dict().items()}
            scrape_row = _lookup_latest(
                candidate_id=source_row.get("candidate_id", ""),
                supplier_sku=source_row.get("supplier_sku", ""),
                asin=source_row.get("asin", ""),
                by_candidate=scrape_by_candidate,
                by_supplier_asin=scrape_by_supplier_asin,
                by_asin=scrape_by_asin,
            )
            output_rows.append(
                _build_row(
                    source_row=source_row,
                    review_pack_type=review_pack_type,
                    scrape_row=scrape_row,
                )
            )

    audit_df = pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS)
    if not audit_df.empty:
        audit_df = audit_df.sort_values(
            by=["review_pack_type", "uk_review_code", "asin", "candidate_id", "supplier_sku"],
            ascending=[True, True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)

    unclassified_rows = 0
    if not audit_df.empty:
        unclassified_rows += int((~audit_df["uk_review_code"].isin(VALID_UK_REVIEW_CODES)).sum())
        unclassified_rows += int((audit_df["uk_review_code"].map(_normalize_text) == "").sum())
        unclassified_rows += int((audit_df["uk_review_recommended_action"].map(_normalize_text) == "").sum())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(output_path, index=False)

    code_counts = (
        {str(key): int(value) for key, value in audit_df["uk_review_code"].value_counts().sort_index().items()}
        if not audit_df.empty
        else {}
    )
    action_counts = (
        {str(key): int(value) for key, value in audit_df["uk_review_recommended_action"].value_counts().sort_index().items()}
        if not audit_df.empty
        else {}
    )

    report = {
        "pass_input_rows": int(len(pass_df.index)),
        "near_miss_input_rows": int(len(near_miss_df.index)),
        "total_input_rows_audited": int(len(pass_df.index) + len(near_miss_df.index)),
        "audit_output_rows": int(len(audit_df.index)),
        "scrape_evidence_rows": int(len(scrape_df.index)),
        "unclassified_rows": int(unclassified_rows),
        "uk_review_code_counts": code_counts,
        "uk_review_recommended_action_counts": action_counts,
        "output_path": str(output_path),
    }
    return UkReviewSignalAuditResult(audit_df=audit_df, output_path=output_path, report=report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only UK review signal audit for pass and near-miss rows.")
    parser.add_argument("--pass-path", type=Path, default=DEFAULT_PASS_PATH)
    parser.add_argument("--near-miss-path", type=Path, default=DEFAULT_NEAR_MISS_PATH)
    parser.add_argument("--scrape-evidence-path", type=Path, default=DEFAULT_SCRAPE_EVIDENCE_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_uk_review_signal_audit(
        pass_path=args.pass_path,
        near_miss_path=args.near_miss_path,
        scrape_evidence_path=args.scrape_evidence_path,
        output_path=args.output_path,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
