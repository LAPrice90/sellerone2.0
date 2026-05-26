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

from scripts.one_off.F011_build_sales_history_accuracy_pack import build_sales_history_accuracy_pack


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _metric(summary_df: pd.DataFrame, metric_name: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == metric_name]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["value"])


def test_f011_sold_truth_row_with_missing_model_evidence_is_explicit(tmp_path: Path) -> None:
    sold_truth_path = tmp_path / "actuals.csv"
    summary_path = tmp_path / "summary.csv"
    alignment_path = tmp_path / "alignment.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sold_truth_path,
        [
            {
                "seller_sku": "OPER::B00TEST001",
                "asin": "B00TEST001",
                "actual_units_30d": "6",
                "actual_profit_30d_gbp": "12",
                "actual_units_60d": "6",
                "actual_profit_60d_gbp": "12",
                "actual_units_90d": "6",
                "actual_profit_90d_gbp": "12",
                "actuals_basis": "operational_baseline",
                "actuals_observed_utc": "2026-04-21T10:00:00Z",
                "actuals_source_state_30d": "finalized_only",
                "actuals_source_state_60d": "finalized_only",
                "actuals_source_state_90d": "finalized_only",
            }
        ],
    )
    _write_csv(summary_path, [])
    _write_csv(alignment_path, [])

    result = build_sales_history_accuracy_pack(
        sold_truth_path=sold_truth_path,
        summary_path=summary_path,
        alignment_path=alignment_path,
        output_dir=output_dir,
        observed_utc="2026-04-21T10:05:00Z",
    )

    assert len(result.accuracy_df) == 1
    row = result.accuracy_df.iloc[0]
    assert row["model_side_evidence_state"] == "missing"
    assert row["judged_accuracy_flag"] == "0"
    assert "missing_model_side_evidence" in row["accuracy_bucket_codes"]
    assert _metric(result.summary_df, "sold_rows_missing_model_side_evidence") == "1"
    assert _metric(result.summary_df, "sold_truth_replay_queue_rows") == "1"
    assert _metric(result.summary_df, "judged_accuracy_rows") == "0"
    assert len(result.queue_df) == 1
    assert result.queue_df.iloc[0]["capture_reason"] == "missing_model_side_evidence_for_sold_truth_row"
    assert result.queue_latest_path.exists()
    assert result.template_latest_path.exists()


def test_f011_flags_false_pass_from_sold_truth_decision_gate(tmp_path: Path) -> None:
    sold_truth_path = tmp_path / "actuals.csv"
    summary_path = tmp_path / "summary.csv"
    alignment_path = tmp_path / "alignment.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sold_truth_path,
        [
            {
                "seller_sku": "OPER::B00TEST002",
                "asin": "B00TEST002",
                "actual_units_30d": "5",
                "actual_profit_30d_gbp": "8",
                "actual_units_60d": "5",
                "actual_profit_60d_gbp": "8",
                "actual_units_90d": "5",
                "actual_profit_90d_gbp": "8",
                "actuals_basis": "operational_baseline",
                "actuals_observed_utc": "2026-04-21T10:00:00Z",
            }
        ],
    )
    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-21T10:02:00Z",
                "seller_sku": "SKU-2",
                "asin": "B00TEST002",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "expected_units_next_30d": "7",
                "expected_profit_next_30d_gbp": "25",
                "minimum_expected_profit_gbp": "20",
            }
        ],
    )
    _write_csv(alignment_path, [])

    result = build_sales_history_accuracy_pack(
        sold_truth_path=sold_truth_path,
        summary_path=summary_path,
        alignment_path=alignment_path,
        output_dir=output_dir,
        observed_utc="2026-04-21T10:06:00Z",
        decision_profit_floor_gbp=20.0,
    )

    assert len(result.accuracy_df) == 1
    row = result.accuracy_df.iloc[0]
    assert row["truth_decision_state"] == "fail"
    assert row["model_decision_state"] == "pass"
    assert row["decision_alignment_state"] == "mismatch"
    assert row["mismatch_flag"] == "1"
    assert "model_false_pass" in row["accuracy_bucket_codes"]
    assert _metric(result.summary_df, "false_pass_rows") == "1"


def test_f011_alignment_fill_provides_estimate_when_summary_is_thin(tmp_path: Path) -> None:
    sold_truth_path = tmp_path / "actuals.csv"
    summary_path = tmp_path / "summary.csv"
    alignment_path = tmp_path / "alignment.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sold_truth_path,
        [
            {
                "seller_sku": "OPER::B00TEST003",
                "asin": "B00TEST003",
                "actual_units_30d": "2",
                "actual_profit_30d_gbp": "3",
                "actual_units_60d": "2",
                "actual_profit_60d_gbp": "3",
                "actual_units_90d": "2",
                "actual_profit_90d_gbp": "3",
                "actuals_basis": "operational_baseline",
                "actuals_observed_utc": "2026-04-21T10:00:00Z",
            }
        ],
    )
    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-21T10:02:00Z",
                "seller_sku": "SKU-3",
                "asin": "B00TEST003",
                "decision_state": "fail",
                "decision_confidence": "low",
                "expected_units_next_30d": "",
                "expected_profit_next_30d_gbp": "",
            }
        ],
    )
    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-21T10:03:00Z",
                "asin": "B00TEST003",
                "expected_units_30d": "10",
                "expected_profit_30d_gbp": "22",
            }
        ],
    )

    result = build_sales_history_accuracy_pack(
        sold_truth_path=sold_truth_path,
        summary_path=summary_path,
        alignment_path=alignment_path,
        output_dir=output_dir,
        observed_utc="2026-04-21T10:07:00Z",
    )

    assert len(result.accuracy_df) == 1
    row = result.accuracy_df.iloc[0]
    assert row["model_source"] == "summary_plus_alignment_fill"
    assert row["model_side_evidence_state"] == "full_decision_and_estimate"
    assert row["judged_accuracy_flag"] == "1"
    assert row["demand_alignment_state"] == "severe_model_overestimate"
    assert "demand_overestimate" in row["accuracy_bucket_codes"]
    assert "profit_overestimate" in row["accuracy_bucket_codes"]
    assert _metric(result.summary_df, "demand_overestimate_rows") == "1"


def test_f011_uses_replay_bridge_before_summary_and_alignment(tmp_path: Path) -> None:
    sold_truth_path = tmp_path / "actuals.csv"
    summary_path = tmp_path / "summary.csv"
    alignment_path = tmp_path / "alignment.csv"
    replay_path = tmp_path / "replay.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sold_truth_path,
        [
            {
                "seller_sku": "OPER::B00TEST004",
                "asin": "B00TEST004",
                "actual_units_30d": "4",
                "actual_profit_30d_gbp": "15",
                "actual_units_60d": "4",
                "actual_profit_60d_gbp": "15",
                "actual_units_90d": "4",
                "actual_profit_90d_gbp": "15",
                "actuals_basis": "operational_baseline",
                "actuals_observed_utc": "2026-04-21T10:00:00Z",
            }
        ],
    )
    _write_csv(
        replay_path,
        [
            {
                "observed_utc": "2026-04-21T10:04:00Z",
                "asin": "B00TEST004",
                "model_source": "replay_bridge",
                "model_decision_state": "fail",
                "model_decision_confidence": "medium",
                "model_expected_units_next_30d": "6",
                "model_expected_profit_next_30d_gbp": "11",
                "model_minimum_expected_profit_gbp": "20",
                "estimated_demand": "medium",
                "recommended_test_qty": "5",
                "recommendation_status": "reject",
                "commercial_guidance_source": "replay_source_field",
            }
        ],
    )
    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-21T10:03:00Z",
                "seller_sku": "SKU-4",
                "asin": "B00TEST004",
                "decision_state": "pass",
                "decision_confidence": "high",
                "expected_units_next_30d": "90",
                "expected_profit_next_30d_gbp": "190",
                "minimum_expected_profit_gbp": "20",
            }
        ],
    )
    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-21T10:05:00Z",
                "asin": "B00TEST004",
                "expected_units_30d": "50",
                "expected_profit_30d_gbp": "150",
            }
        ],
    )

    result = build_sales_history_accuracy_pack(
        sold_truth_path=sold_truth_path,
        summary_path=summary_path,
        alignment_path=alignment_path,
        replay_path=replay_path,
        output_dir=output_dir,
        observed_utc="2026-04-21T10:06:00Z",
    )

    row = result.accuracy_df.iloc[0]
    assert row["model_source"] == "replay_bridge"
    assert row["model_decision_state"] == "fail"
    assert row["model_expected_units_next_30d"] == "6"
    assert row["model_expected_profit_next_30d_gbp"] == "11"
    assert row["estimated_demand"] == "medium"
    assert row["recommended_test_qty"] == "5"
    assert row["recommendation_status"] == "reject"
    assert row["commercial_guidance_source"] == "replay_source_field"
    assert _metric(result.summary_df, "sold_decision_replay_coverage_rows") == "1"
    assert _metric(result.summary_df, "rows_with_recommended_test_qty") == "1"
