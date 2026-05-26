from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_PATH = ROOT / "out" / "analysis_reports" / "f_demand_range_bbp_conflict_audit_latest.csv"
DEFAULT_SAMPLE_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_demand_range_review_sample_pack_latest.csv"
DEFAULT_SUMMARY_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_demand_range_review_sample_summary_latest.csv"

SAMPLE_COLUMNS = [
    "asin",
    "candidate_id",
    "supplier_sku",
    "review_pack_type",
    "title",
    "amazon_demand_signal",
    "amazon_demand_floor",
    "amazon_demand_ceiling",
    "bbp_units",
    "expected_units_next_30d",
    "demand_conflict_code",
    "uk_reviews",
    "variant_reviews",
    "confidence_adjustment",
    "recommended_action",
    "evidence_source",
    "sample_reason",
    "threshold_decision_blank",
    "reviewer_note_blank",
]

SUMMARY_COLUMNS = ["metric", "value"]

MAJOR_DEMAND_CONFLICT_CODES = [
    "amazon_blank_bbp_high",
    "amazon_50_bbp_inflated",
    "amazon_50_bbp_warn",
    "weak_uk_review_confirms_demand_risk",
    "seller_stock_missing_for_demand_check",
]

ALWAYS_INCLUDE_ASIN = "B0C8C3JF9X"
REMOVE_FROM_CLEAN_PASS = "remove_from_clean_pass"
ALLOW_IF_OTHER_CHECKS_PASS = "allow_if_other_checks_pass"
SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class DemandRangeReviewSamplePackResult:
    sample_df: pd.DataFrame
    summary_df: pd.DataFrame
    sample_output_path: Path
    summary_output_path: Path
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


def _parse_float(value: object) -> float:
    text = _normalize_text(value)
    if text == "":
        return 0.0
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = df.copy()
    for column in columns:
        if column not in work.columns:
            work[column] = ""
    return work


def _sort_for_sampling(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df.copy()
    work["_demand_sort"] = work.apply(
        lambda row: max(
            _parse_float(row.get("bbp_units", "")),
            _parse_float(row.get("expected_units_next_30d", "")),
        ),
        axis=1,
    )
    work["_asin_sort"] = work["asin"].map(_normalize_key)
    work["_code_sort"] = work["demand_conflict_code"].map(_normalize_key)
    return work.sort_values(
        by=["_demand_sort", "_asin_sort", "_code_sort"],
        ascending=[False, True, True],
        kind="stable",
    ).drop(columns=["_demand_sort", "_asin_sort", "_code_sort"], errors="ignore")


def _dedupe_key(row: pd.Series) -> tuple[str, str]:
    return (_normalize_key(row.get("asin", "")), _normalize_key(row.get("demand_conflict_code", "")))


def _append_reason(existing: str, reason: str) -> str:
    reasons = [_normalize_text(item) for item in existing.split("|") if _normalize_text(item)]
    if reason not in reasons:
        reasons.append(reason)
    return "|".join(reasons)


def _add_rows(
    selected: dict[tuple[str, str], dict[str, str]],
    rows: pd.DataFrame,
    *,
    sample_reason: str,
) -> None:
    if rows.empty:
        return
    for _, row in rows.iterrows():
        key = _dedupe_key(row)
        if key[0] == "" or key[1] == "":
            continue
        row_dict = {column: _normalize_text(row.get(column, "")) for column in SAMPLE_COLUMNS if column != "sample_reason"}
        if key not in selected:
            row_dict["sample_reason"] = sample_reason
            row_dict["threshold_decision_blank"] = ""
            row_dict["reviewer_note_blank"] = ""
            selected[key] = row_dict
            continue
        selected[key]["sample_reason"] = _append_reason(selected[key].get("sample_reason", ""), sample_reason)


def _selected_contains_asin(selected: dict[tuple[str, str], dict[str, str]], asin: str) -> bool:
    asin_key = _normalize_key(asin)
    return any(_normalize_key(row.get("asin", "")) == asin_key for row in selected.values())


def _summary_value(summary_df: pd.DataFrame, metric: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == metric]
    if rows.empty:
        return ""
    return _normalize_text(rows.iloc[0]["value"])


def build_demand_range_review_sample_pack(
    *,
    audit_path: Path = DEFAULT_AUDIT_PATH,
    sample_output_path: Path = DEFAULT_SAMPLE_OUTPUT_PATH,
    summary_output_path: Path = DEFAULT_SUMMARY_OUTPUT_PATH,
    sample_limit: int = SAMPLE_LIMIT,
) -> DemandRangeReviewSamplePackResult:
    audit_df = _read_csv(audit_path)
    audit_df = _ensure_columns(audit_df, SAMPLE_COLUMNS)
    audit_df = audit_df.drop(columns=["sample_reason", "threshold_decision_blank", "reviewer_note_blank"], errors="ignore")
    audit_df = _ensure_columns(audit_df, SAMPLE_COLUMNS)

    ordered_audit_df = _sort_for_sampling(audit_df)
    selected: dict[tuple[str, str], dict[str, str]] = {}

    remove_rows = ordered_audit_df.loc[ordered_audit_df["recommended_action"].map(_normalize_text) == REMOVE_FROM_CLEAN_PASS]
    _add_rows(selected, remove_rows, sample_reason="all_remove_from_clean_pass")

    other_actions = sorted(
        {
            _normalize_text(value)
            for value in ordered_audit_df["recommended_action"].tolist()
            if _normalize_text(value) and _normalize_text(value) != REMOVE_FROM_CLEAN_PASS
        }
    )
    for action in other_actions:
        action_rows = ordered_audit_df.loc[ordered_audit_df["recommended_action"].map(_normalize_text) == action].head(sample_limit)
        _add_rows(selected, action_rows, sample_reason=f"recommended_action_sample:{action}")

    for code in MAJOR_DEMAND_CONFLICT_CODES:
        code_rows = ordered_audit_df.loc[ordered_audit_df["demand_conflict_code"].map(_normalize_text) == code].head(sample_limit)
        _add_rows(selected, code_rows, sample_reason=f"major_conflict_code_sample:{code}")

    b0_rows = ordered_audit_df.loc[ordered_audit_df["asin"].map(_normalize_key) == ALWAYS_INCLUDE_ASIN]
    if not b0_rows.empty and not _selected_contains_asin(selected, ALWAYS_INCLUDE_ASIN):
        _add_rows(selected, b0_rows.head(1), sample_reason=f"always_include:{ALWAYS_INCLUDE_ASIN}")

    sample_df = pd.DataFrame(list(selected.values()), columns=SAMPLE_COLUMNS)
    if not sample_df.empty:
        sample_df["_action_sort"] = sample_df["recommended_action"].map(_normalize_text)
        sample_df["_code_sort"] = sample_df["demand_conflict_code"].map(_normalize_text)
        sample_df["_demand_sort"] = sample_df.apply(
            lambda row: max(
                _parse_float(row.get("bbp_units", "")),
                _parse_float(row.get("expected_units_next_30d", "")),
            ),
            axis=1,
        )
        sample_df = sample_df.sort_values(
            by=["_action_sort", "_code_sort", "_demand_sort", "asin", "candidate_id"],
            ascending=[True, True, False, True, True],
            kind="stable",
        ).drop(columns=["_action_sort", "_code_sort", "_demand_sort"], errors="ignore")
        sample_df = sample_df.reset_index(drop=True)

    unclassified_rows = 0
    if not audit_df.empty:
        unclassified_rows += int((audit_df["demand_conflict_code"].map(_normalize_text) == "").sum())
        unclassified_rows += int((audit_df["recommended_action"].map(_normalize_text) == "").sum())

    sample_action_counts = (
        {str(key): int(value) for key, value in sample_df["recommended_action"].value_counts().sort_index().items()}
        if not sample_df.empty
        else {}
    )
    summary_rows = [
        {"metric": "input_audit_rows", "value": str(int(len(audit_df.index)))},
        {"metric": "output_sample_rows", "value": str(int(len(sample_df.index)))},
        {
            "metric": "rows_remove_from_clean_pass",
            "value": str(sample_action_counts.get("remove_from_clean_pass", 0)),
        },
        {"metric": "rows_manual_review", "value": str(sample_action_counts.get("manual_review", 0))},
        {
            "metric": "rows_strengthen_demand_risk_action",
            "value": str(sample_action_counts.get("strengthen_demand_risk_action", 0)),
        },
        {
            "metric": "rows_targeted_rescan_needed",
            "value": str(sample_action_counts.get("targeted_rescan_needed", 0)),
        },
        {
            "metric": "rows_allow_if_other_checks_pass_sampled",
            "value": str(sample_action_counts.get("allow_if_other_checks_pass", 0)),
        },
        {
            "metric": "b0c8c3jf9x_included",
            "value": "yes" if bool((sample_df["asin"].map(_normalize_key) == ALWAYS_INCLUDE_ASIN).any()) else "no",
        },
        {"metric": "unclassified_rows", "value": str(int(unclassified_rows))},
    ]
    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)

    sample_output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_df.to_csv(sample_output_path, index=False)
    summary_df.to_csv(summary_output_path, index=False)

    report = {
        "audit_path": str(audit_path),
        "sample_output_path": str(sample_output_path),
        "summary_output_path": str(summary_output_path),
        "input_audit_rows": int(len(audit_df.index)),
        "output_sample_rows": int(len(sample_df.index)),
        "summary_metrics": {row["metric"]: row["value"] for row in summary_rows},
        "b0c8c3jf9x_included": _summary_value(summary_df, "b0c8c3jf9x_included") == "yes",
        "unclassified_rows": int(unclassified_rows),
    }
    return DemandRangeReviewSamplePackResult(
        sample_df=sample_df,
        summary_df=summary_df,
        sample_output_path=sample_output_path,
        summary_output_path=summary_output_path,
        report=report,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build human-review samples for demand range threshold approval.")
    parser.add_argument("--audit-path", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--sample-output-path", type=Path, default=DEFAULT_SAMPLE_OUTPUT_PATH)
    parser.add_argument("--summary-output-path", type=Path, default=DEFAULT_SUMMARY_OUTPUT_PATH)
    parser.add_argument("--sample-limit", type=int, default=SAMPLE_LIMIT)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_demand_range_review_sample_pack(
        audit_path=args.audit_path,
        sample_output_path=args.sample_output_path,
        summary_output_path=args.summary_output_path,
        sample_limit=max(int(args.sample_limit), 1),
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
