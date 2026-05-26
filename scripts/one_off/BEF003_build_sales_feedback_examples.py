from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DEFAULT_OUTPUT_DIR = OUT / "analysis_reports"

REVIEW_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_review_latest.csv"
ACTUALS_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_actuals_latest.csv"
OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "bef_sales_feedback_examples_latest.csv"

EXAMPLE_COLUMNS = [
    "observed_utc",
    "example_rank",
    "example_class",
    "example_priority",
    "decision_snapshot_utc",
    "seller_sku",
    "asin",
    "expected_units_next_30d",
    "expected_profit_next_30d_gbp",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "actual_units_60d",
    "actual_profit_60d_gbp",
    "actual_units_90d",
    "actual_profit_90d_gbp",
    "expected_result",
    "actual_result",
    "learning_outcome",
    "learning_reason_codes",
    "review_prompt",
    "evidence_notes",
]

CLASS_PRIORITY = {
    "overlap_gap_no_summary_match": 1,
    "no_operational_truth_coverage": 2,
    "pending_window_not_ready": 3,
    "model_error_demand_too_high": 4,
    "model_error_demand_too_low": 4,
    "model_error_other": 5,
    "right_call": 6,
}


@dataclass(frozen=True)
class SalesFeedbackExamplesResult:
    examples_df: pd.DataFrame
    output_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _build_actuals_maps(actuals_df: pd.DataFrame) -> tuple[set[str], set[str]]:
    if actuals_df.empty:
        return set(), set()
    asins = actuals_df.get("asin", pd.Series([], dtype=str)).map(_normalize_text).str.upper()
    basis = actuals_df.get("actuals_basis", pd.Series([], dtype=str)).map(_normalize_text).str.lower()
    summary_map = {asin for asin, b in zip(asins.tolist(), basis.tolist()) if asin and b == "summary_asin_map"}
    operational = {asin for asin, b in zip(asins.tolist(), basis.tolist()) if asin and b == "operational_baseline"}
    return summary_map, operational


def _classify_row(row: pd.Series, *, summary_asins: set[str], operational_asins: set[str]) -> tuple[str, str]:
    asin = _normalize_text(row.get("asin", "")).upper()
    outcome = _normalize_text(row.get("learning_outcome", "")).lower()
    reason = _normalize_text(row.get("learning_reason_codes", ""))

    if outcome == "pending_outcome":
        if asin in operational_asins and asin not in summary_asins:
            return "overlap_gap_no_summary_match", (
                "ASIN has operational baseline truth but no summary-mapped actual row; "
                "this is an overlap bridge issue, not a demand model result."
            )
        if asin not in operational_asins:
            return "no_operational_truth_coverage", (
                "ASIN has no operational truth coverage yet; scrape and bridge coverage must improve before scoring model quality."
            )
        return "pending_window_not_ready", (
            "ASIN is linked but outcome remains pending; confirm window maturity and recent finalized/provisional timing."
        )

    if outcome == "right_call":
        return "right_call", "Prediction and actuals are aligned for the selected outcome window."
    if outcome == "demand_too_high":
        return "model_error_demand_too_high", "Expected demand exceeded observed demand at the selected outcome window."
    if outcome == "demand_too_low":
        return "model_error_demand_too_low", "Observed demand exceeded expected demand at the selected outcome window."

    note = "Model outcome is non-pending but outside the core demand classes."
    if reason != "":
        note = f"{note} reason={reason}"
    return "model_error_other", note


def _priority_for(example_class: str) -> int:
    return int(CLASS_PRIORITY.get(example_class, 9))


def _format_expected_result(row: pd.Series) -> str:
    expected_units = _normalize_text(row.get("expected_units_next_30d", ""))
    expected_profit = _normalize_text(row.get("expected_profit_next_30d_gbp", ""))
    parts: list[str] = []
    if expected_units != "":
        parts.append(f"expected_units_next_30d={expected_units}")
    if expected_profit != "":
        parts.append(f"expected_profit_next_30d_gbp={expected_profit}")
    return "; ".join(parts) if parts else "expected_30d_missing"


def _format_actual_result(row: pd.Series) -> str:
    windows: list[str] = []
    for window in ("30d", "60d", "90d"):
        units = _normalize_text(row.get(f"actual_units_{window}", ""))
        profit = _normalize_text(row.get(f"actual_profit_{window}_gbp", ""))
        if units != "":
            windows.append(f"actual_units_{window}={units}")
        if profit != "":
            windows.append(f"actual_profit_{window}_gbp={profit}")
    return "; ".join(windows) if windows else "actuals_pending"


def build_sales_feedback_examples(
    *,
    output_path: Path = OUTPUT_PATH,
    observed_utc: str | None = None,
) -> SalesFeedbackExamplesResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    review_df = _read_csv(REVIEW_PATH)
    actuals_df = _read_csv(ACTUALS_PATH)

    if review_df.empty:
        out = pd.DataFrame(columns=EXAMPLE_COLUMNS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output_path, index=False)
        print(json.dumps({"status": "success", "observed_utc": snapshot_utc, "rows": 0, "output": str(output_path)}))
        return SalesFeedbackExamplesResult(examples_df=out, output_path=output_path)

    summary_asins, operational_asins = _build_actuals_maps(actuals_df)

    rows: list[dict[str, str]] = []
    for _, row in review_df.iterrows():
        asin = _normalize_text(row.get("asin", "")).upper()
        example_class, note = _classify_row(row, summary_asins=summary_asins, operational_asins=operational_asins)
        rows.append(
            {
                "observed_utc": snapshot_utc,
                "example_rank": "",
                "example_class": example_class,
                "example_priority": str(_priority_for(example_class)),
                "decision_snapshot_utc": _normalize_text(row.get("decision_snapshot_utc", "")),
                "seller_sku": _normalize_text(row.get("seller_sku", "")),
                "asin": asin,
                "expected_units_next_30d": _normalize_text(row.get("expected_units_next_30d", "")),
                "expected_profit_next_30d_gbp": _normalize_text(row.get("expected_profit_next_30d_gbp", "")),
                "actual_units_30d": _normalize_text(row.get("actual_units_30d", "")),
                "actual_profit_30d_gbp": _normalize_text(row.get("actual_profit_30d_gbp", "")),
                "actual_units_60d": _normalize_text(row.get("actual_units_60d", "")),
                "actual_profit_60d_gbp": _normalize_text(row.get("actual_profit_60d_gbp", "")),
                "actual_units_90d": _normalize_text(row.get("actual_units_90d", "")),
                "actual_profit_90d_gbp": _normalize_text(row.get("actual_profit_90d_gbp", "")),
                "expected_result": _format_expected_result(row),
                "actual_result": _format_actual_result(row),
                "learning_outcome": _normalize_text(row.get("learning_outcome", "")),
                "learning_reason_codes": _normalize_text(row.get("learning_reason_codes", "")),
                "review_prompt": (
                    "Check if this classification is correct and whether action is bridge-coverage work, "
                    "model tuning, or no change."
                ),
                "evidence_notes": note,
            }
        )

    out = pd.DataFrame(rows, columns=EXAMPLE_COLUMNS)
    out = out.sort_values(
        by=["example_priority", "decision_snapshot_utc", "asin", "seller_sku"],
        key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
        kind="stable",
    ).reset_index(drop=True)
    out["example_rank"] = (out.index + 1).astype(str)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    class_counts = out["example_class"].value_counts().to_dict() if not out.empty else {}
    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "rows": int(len(out.index)),
                "class_counts": class_counts,
                "output": str(output_path),
            }
        )
    )
    return SalesFeedbackExamplesResult(examples_df=out, output_path=output_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build overlap-aware operator examples for sales feedback review.")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--observed-utc", default=None, help="Override observed UTC timestamp in ISO format.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_sales_feedback_examples(
        output_path=Path(args.output),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
