from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off import BEF003_build_sales_feedback_examples as bef003


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_build_sales_feedback_examples_classifies_overlap_and_model_rows(tmp_path: Path, monkeypatch) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    review_path = analysis_dir / "f_sales_history_learning_review_latest.csv"
    actuals_path = analysis_dir / "f_sales_history_learning_actuals_latest.csv"
    output_path = analysis_dir / "bef_sales_feedback_examples_latest.csv"

    monkeypatch.setattr(bef003, "REVIEW_PATH", review_path)
    monkeypatch.setattr(bef003, "ACTUALS_PATH", actuals_path)

    _write_csv(
        review_path,
        [
            {
                "decision_snapshot_utc": "2026-04-20T10:00:00Z",
                "seller_sku": "SKU-OVERLAP",
                "asin": "A1",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "20",
                "learning_outcome": "pending_outcome",
            },
            {
                "decision_snapshot_utc": "2026-04-20T10:00:00Z",
                "seller_sku": "SKU-NOCOVER",
                "asin": "A2",
                "learning_outcome": "pending_outcome",
            },
            {
                "decision_snapshot_utc": "2026-04-20T10:00:00Z",
                "seller_sku": "SKU-PENDING",
                "asin": "A3",
                "learning_outcome": "pending_outcome",
            },
            {
                "decision_snapshot_utc": "2026-04-20T10:00:00Z",
                "seller_sku": "SKU-HIGH",
                "asin": "A4",
                "actual_units_90d": "18",
                "learning_outcome": "demand_too_high",
            },
            {
                "decision_snapshot_utc": "2026-04-20T10:00:00Z",
                "seller_sku": "SKU-LOW",
                "asin": "A5",
                "actual_units_90d": "45",
                "learning_outcome": "demand_too_low",
            },
            {
                "decision_snapshot_utc": "2026-04-20T10:00:00Z",
                "seller_sku": "SKU-RIGHT",
                "asin": "A6",
                "actual_units_30d": "11",
                "learning_outcome": "right_call",
            },
            {
                "decision_snapshot_utc": "2026-04-20T10:00:00Z",
                "seller_sku": "SKU-OTHER",
                "asin": "A7",
                "learning_outcome": "price_assumption_wrong",
                "learning_reason_codes": "operator_override",
            },
        ],
    )
    _write_csv(
        actuals_path,
        [
            {"asin": "A1", "actuals_basis": "operational_baseline"},
            {"asin": "A3", "actuals_basis": "operational_baseline"},
            {"asin": "A3", "actuals_basis": "SUMMARY_ASIN_MAP"},
        ],
    )

    result = bef003.build_sales_feedback_examples(
        output_path=output_path,
        observed_utc="2026-04-20T16:00:00Z",
    )

    assert result.output_path.exists()
    out_df = pd.read_csv(result.output_path, dtype=str).fillna("")
    assert len(out_df.index) == 7
    assert list(out_df.columns) == bef003.EXAMPLE_COLUMNS

    by_sku = {row["seller_sku"]: row for row in out_df.to_dict("records")}
    assert by_sku["SKU-OVERLAP"]["example_class"] == "overlap_gap_no_summary_match"
    assert by_sku["SKU-NOCOVER"]["example_class"] == "no_operational_truth_coverage"
    assert by_sku["SKU-PENDING"]["example_class"] == "pending_window_not_ready"
    assert by_sku["SKU-HIGH"]["example_class"] == "model_error_demand_too_high"
    assert by_sku["SKU-LOW"]["example_class"] == "model_error_demand_too_low"
    assert by_sku["SKU-RIGHT"]["example_class"] == "right_call"
    assert by_sku["SKU-OTHER"]["example_class"] == "model_error_other"
    assert by_sku["SKU-OVERLAP"]["expected_result"] == "expected_units_next_30d=10; expected_profit_next_30d_gbp=20"
    assert by_sku["SKU-NOCOVER"]["actual_result"] == "actuals_pending"
    assert "reason=operator_override" in by_sku["SKU-OTHER"]["evidence_notes"]

    overlap_rank = int(by_sku["SKU-OVERLAP"]["example_rank"])
    right_call_rank = int(by_sku["SKU-RIGHT"]["example_rank"])
    assert overlap_rank < right_call_rank


def test_build_sales_feedback_examples_handles_empty_review(tmp_path: Path, monkeypatch) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    review_path = analysis_dir / "f_sales_history_learning_review_latest.csv"
    actuals_path = analysis_dir / "f_sales_history_learning_actuals_latest.csv"
    output_path = analysis_dir / "bef_sales_feedback_examples_latest.csv"

    monkeypatch.setattr(bef003, "REVIEW_PATH", review_path)
    monkeypatch.setattr(bef003, "ACTUALS_PATH", actuals_path)

    _write_csv(review_path, [])
    _write_csv(actuals_path, [])

    result = bef003.build_sales_feedback_examples(
        output_path=output_path,
        observed_utc="2026-04-20T16:01:00Z",
    )

    out_df = pd.read_csv(result.output_path, dtype=str).fillna("")
    assert list(out_df.columns) == bef003.EXAMPLE_COLUMNS
    assert out_df.empty
