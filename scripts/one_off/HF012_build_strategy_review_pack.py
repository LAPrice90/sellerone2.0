from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "out" / "reports" / "hf_strategy_review_pack_latest.csv"

SCORECARD_PATH = ROOT / "out" / "analysis_reports" / "hf_strategy_scorecard_latest.csv"
ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
SCOPE_SUMMARY_PATH = ROOT / "out" / "analysis_reports" / "hf_scope_expansion_summary_latest.csv"

REQUIRED_INPUTS = [SCORECARD_PATH, ALIGNMENT_PATH]

REVIEW_COLUMNS = [
    "snapshot_utc",
    "review_section",
    "record_type",
    "record_key",
    "scenario_type",
    "dominant_class",
    "record_count",
    "decision_rows",
    "sample_min_rows",
    "sample_mature_flag",
    "review_status",
    "recommendation",
    "source_scorecard_snapshot_utc",
    "source_alignment_snapshot_utc",
    "source_scope_snapshot_utc",
    "notes",
]


@dataclass(frozen=True)
class StrategyReviewPackResult:
    output_path: Path
    rows: int
    alignment_class_rows: int
    tactic_rows: int


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _to_int(value: object, default: int = 0) -> int:
    text = _normalize_text(value)
    if text == "":
        return int(default)
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return int(default)


def _to_rate_text(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0000"
    return f"{(numerator / denominator):.4f}"


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required batch-003 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required batch-003 input missing: {path}")


def _recommendation_for_review_status(review_status: str, sample_mature_flag: int) -> str:
    status = _normalize_text(review_status)
    if sample_mature_flag != 1:
        return "sample_too_thin"
    if status == "overlap_first":
        return "recover_overlap_first"
    if status == "eligible_shadow":
        return "eligible_for_shadow_experiment"
    if status == "keep_observing":
        return "keep_observing"
    if status == "blocked":
        return "blocked_pending_recovery"
    return "manual_review"


def _alignment_recommendation(discrepancy_class: str) -> str:
    mapping = {
        "missing_expected_baseline": "recover_overlap_first",
        "underperform_vs_expected": "investigate_true_underperformance",
        "aligned": "keep_current_strategy",
        "outperform_vs_expected": "protect_margin_and_monitor",
        "missing_actual_30d": "collect_actuals_first",
        "matched_zero": "keep_observing",
        "expected_zero_actual_positive": "validate_expected_model",
    }
    key = _normalize_text(discrepancy_class)
    return mapping.get(key, "manual_review")


def _summary_metric(summary_df: pd.DataFrame, metric_name: str) -> str:
    if summary_df.empty:
        return ""
    work = summary_df.copy()
    work["metric_name"] = work.get("metric_name", "").map(_normalize_text)
    work["metric_value"] = work.get("metric_value", "").map(_normalize_text)
    hit = work[work["metric_name"] == metric_name]
    if hit.empty:
        return ""
    return _normalize_text(hit.iloc[0]["metric_value"])


def build_strategy_review_pack(*, output_path: Path) -> StrategyReviewPackResult:
    _ensure_required_inputs()
    snapshot_utc = _utc_now_iso()

    scorecard_df = _read_csv_required(SCORECARD_PATH)
    alignment_df = _read_csv_required(ALIGNMENT_PATH)
    scope_summary_df = _read_csv_optional(SCOPE_SUMMARY_PATH)

    scorecard_snapshot_utc = _normalize_text(scorecard_df.get("snapshot_utc", pd.Series([], dtype=str)).max())
    alignment_snapshot_utc = _normalize_text(alignment_df.get("alignment_window_end_utc", pd.Series([], dtype=str)).max())
    scope_snapshot_utc = _summary_metric(scope_summary_df, "identity_snapshot_utc")

    rows: list[dict[str, str]] = []

    alignment_rows_count = 0
    if not alignment_df.empty and "dominant_discrepancy_class" in alignment_df.columns:
        grouped = (
            alignment_df.assign(dominant_discrepancy_class=alignment_df["dominant_discrepancy_class"].map(_normalize_text))
            .groupby("dominant_discrepancy_class", dropna=False)
            .size()
            .reset_index(name="row_count")
        )
        grouped = grouped.sort_values(["row_count", "dominant_discrepancy_class"], ascending=[False, True], kind="stable")
        total_alignment_rows = int(grouped["row_count"].sum())
        for _, row in grouped.iterrows():
            discrepancy_class = _normalize_text(row.get("dominant_discrepancy_class", ""))
            row_count = _to_int(row.get("row_count", 0))
            rows.append(
                {
                    "snapshot_utc": snapshot_utc,
                    "review_section": "alignment_class",
                    "record_type": "class_summary",
                    "record_key": discrepancy_class,
                    "scenario_type": "",
                    "dominant_class": discrepancy_class,
                    "record_count": str(row_count),
                    "decision_rows": "",
                    "sample_min_rows": "",
                    "sample_mature_flag": "",
                    "review_status": "",
                    "recommendation": _alignment_recommendation(discrepancy_class),
                    "source_scorecard_snapshot_utc": scorecard_snapshot_utc,
                    "source_alignment_snapshot_utc": alignment_snapshot_utc,
                    "source_scope_snapshot_utc": scope_snapshot_utc,
                    "notes": f"class_share={_to_rate_text(row_count, total_alignment_rows)}",
                }
            )
            alignment_rows_count += 1

    tactic_rows_count = 0
    if not scorecard_df.empty:
        work = scorecard_df.copy()
        work["scenario_type"] = work.get("scenario_type", "").map(_normalize_text)
        work = work[work["scenario_type"] != ""].copy()
        work = work.sort_values(["scenario_type"], ascending=[True], kind="stable")
        for _, row in work.iterrows():
            scenario_type = _normalize_text(row.get("scenario_type", ""))
            sample_mature_flag = _to_int(row.get("sample_mature_flag", 0))
            review_status = _normalize_text(row.get("review_status", ""))
            recommendation = _recommendation_for_review_status(
                review_status=review_status,
                sample_mature_flag=sample_mature_flag,
            )
            notes = (
                f"missing_expected_rate={_normalize_text(row.get('missing_expected_baseline_rate', ''))};"
                f"underperform_rate={_normalize_text(row.get('underperform_rate', ''))}"
            )
            rows.append(
                {
                    "snapshot_utc": snapshot_utc,
                    "review_section": "tactic_scorecard",
                    "record_type": "tactic_summary",
                    "record_key": scenario_type,
                    "scenario_type": scenario_type,
                    "dominant_class": _normalize_text(row.get("dominant_alignment_class", "")),
                    "record_count": "1",
                    "decision_rows": _normalize_text(row.get("decision_rows", "")),
                    "sample_min_rows": _normalize_text(row.get("sample_min_rows", "")),
                    "sample_mature_flag": str(sample_mature_flag),
                    "review_status": review_status,
                    "recommendation": recommendation,
                    "source_scorecard_snapshot_utc": scorecard_snapshot_utc,
                    "source_alignment_snapshot_utc": alignment_snapshot_utc,
                    "source_scope_snapshot_utc": scope_snapshot_utc,
                    "notes": notes,
                }
            )
            tactic_rows_count += 1

    outside_h_scope_rows = _summary_metric(scope_summary_df, "outside_h_scope_rows")
    if outside_h_scope_rows != "":
        rows.append(
            {
                "snapshot_utc": snapshot_utc,
                "review_section": "overlap_scope",
                "record_type": "scope_summary",
                "record_key": "outside_h_scope_with_capture_path",
                "scenario_type": "",
                "dominant_class": "missing_expected_baseline",
                "record_count": outside_h_scope_rows,
                "decision_rows": "",
                "sample_min_rows": "",
                "sample_mature_flag": "",
                "review_status": "",
                "recommendation": "recover_overlap_first",
                "source_scorecard_snapshot_utc": scorecard_snapshot_utc,
                "source_alignment_snapshot_utc": alignment_snapshot_utc,
                "source_scope_snapshot_utc": scope_snapshot_utc,
                "notes": "from_scope_expansion_summary",
            }
        )

    review_df = pd.DataFrame(rows).fillna("")
    if not review_df.empty:
        review_df = review_df.sort_values(
            ["review_section", "record_type", "record_key", "scenario_type"],
            ascending=[True, True, True, True],
            kind="stable",
        )
    for column in REVIEW_COLUMNS:
        if column not in review_df.columns:
            review_df[column] = ""
    review_df = review_df[REVIEW_COLUMNS]
    for column in review_df.columns:
        review_df[column] = review_df[column].map(_normalize_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    review_df.to_csv(output_path, index=False)
    return StrategyReviewPackResult(
        output_path=output_path,
        rows=int(len(review_df.index)),
        alignment_class_rows=alignment_rows_count,
        tactic_rows=tactic_rows_count,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build HF strategy review pack (Phase 3).")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path for strategy review pack")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_strategy_review_pack(output_path=Path(args.output))
    print(f"strategy_review_output_path={result.output_path}")
    print(f"strategy_review_rows={result.rows}")
    print(f"strategy_review_alignment_class_rows={result.alignment_class_rows}")
    print(f"strategy_review_tactic_rows={result.tactic_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
