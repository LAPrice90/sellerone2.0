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

from scripts.one_off.F012_build_sales_history_learning_pack import build_sales_history_learning_pack


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_f012_builds_pending_outcome_when_actuals_missing_and_filters_non_pass(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    actuals_path = tmp_path / "missing_actuals.csv"
    learning_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_sales_history_learning_live.csv"
    output_dir = tmp_path / "out" / "analysis_reports"

    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00LEARN001",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "25",
            },
            {
                "observed_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-2",
                "asin": "B00LEARN002",
                "decision_state": "fail",
                "decision_confidence": "low",
                "expected_units_next_30d": "2",
                "expected_profit_next_30d_gbp": "3",
            },
        ],
    )

    result = build_sales_history_learning_pack(
        summary_path=summary_path,
        actuals_path=actuals_path,
        learning_path=learning_path,
        output_dir=output_dir,
        observed_utc="2026-04-20T12:05:00Z",
    )

    assert len(result.review_df) == 1
    row = result.review_df.iloc[0]
    assert row["seller_sku"] == "SKU-1"
    assert row["learning_outcome"] == "pending_outcome"
    assert row["learning_reason_codes"] == "missing_actual_units"
    assert row["outcome_basis_window_days"] == ""
    assert result.template_latest_path.exists()
    assert result.learning_path.exists()

    health = {
        rec["metric"]: rec["value"]
        for rec in result.health_df.to_dict("records")
    }
    assert health["rows_total"] == "1"
    assert health["rows_pending_outcome"] == "1"
    assert health["outcome::pending_outcome"] == "1"


def test_f012_inferrs_demand_high_and_low_from_90d_actuals(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    actuals_path = tmp_path / "actuals.csv"
    learning_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_sales_history_learning_live.csv"
    output_dir = tmp_path / "out" / "analysis_reports"

    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-LOW",
                "asin": "B00LEARN010",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "20",
            },
            {
                "observed_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-HIGH",
                "asin": "B00LEARN011",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "20",
            },
        ],
    )
    _write_csv(
        actuals_path,
        [
            {
                "decision_snapshot_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-LOW",
                "asin": "B00LEARN010",
                "actual_units_90d": "18",
                "operator_check_utc": "2026-04-21T10:00:00Z",
            },
            {
                "decision_snapshot_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-HIGH",
                "asin": "B00LEARN011",
                "actual_units_90d": "45",
                "operator_check_utc": "2026-04-21T10:00:00Z",
            },
        ],
    )

    result = build_sales_history_learning_pack(
        summary_path=summary_path,
        actuals_path=actuals_path,
        learning_path=learning_path,
        output_dir=output_dir,
        observed_utc="2026-04-20T12:06:00Z",
    )

    assert len(result.review_df) == 2
    records = {
        row["seller_sku"]: row
        for row in result.review_df.to_dict("records")
    }
    assert records["SKU-LOW"]["learning_outcome"] == "demand_too_high"
    assert records["SKU-LOW"]["outcome_basis_window_days"] == "90"
    assert records["SKU-HIGH"]["learning_outcome"] == "demand_too_low"
    assert records["SKU-HIGH"]["outcome_basis_window_days"] == "90"


def test_f012_upserts_existing_learning_row_with_operator_override(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    actuals_path = tmp_path / "actuals.csv"
    learning_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_sales_history_learning_live.csv"
    output_dir = tmp_path / "out" / "analysis_reports"

    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00LEARN900",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "expected_units_next_30d": "8",
                "expected_profit_next_30d_gbp": "22",
            }
        ],
    )
    _write_csv(
        learning_path,
        [
            {
                "observed_utc": "2026-04-20T12:01:00Z",
                "decision_snapshot_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00LEARN900",
                "amazon_link": "https://www.amazon.co.uk/dp/B00LEARN900",
                "decision_state_at_snapshot": "pass",
                "decision_confidence_at_snapshot": "medium",
                "expected_units_next_30d": "8",
                "expected_profit_next_30d_gbp": "22",
                "actual_units_30d": "",
                "actual_profit_30d_gbp": "",
                "actual_units_60d": "",
                "actual_profit_60d_gbp": "",
                "actual_units_90d": "",
                "actual_profit_90d_gbp": "",
                "outcome_basis_window_days": "",
                "expected_units_at_basis_window": "",
                "actual_units_at_basis_window": "",
                "units_error_at_basis_window": "",
                "units_error_ratio_at_basis_window": "",
                "learning_outcome": "pending_outcome",
                "learning_reason_codes": "missing_actual_units",
                "operator_check_utc": "",
                "operator_notes": "",
                "purchased_flag": "",
                "record_updated_utc": "2026-04-20T12:01:00Z",
            }
        ],
    )
    _write_csv(
        actuals_path,
        [
            {
                "decision_snapshot_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00LEARN900",
                "actual_units_30d": "5",
                "learning_outcome": "seasonality_misread",
                "learning_reason_codes": "operator_override",
                "operator_check_utc": "2026-04-22T09:00:00Z",
            }
        ],
    )

    result = build_sales_history_learning_pack(
        summary_path=summary_path,
        actuals_path=actuals_path,
        learning_path=learning_path,
        output_dir=output_dir,
        observed_utc="2026-04-20T12:10:00Z",
    )

    assert len(result.learning_df) == 1
    row = result.learning_df.iloc[0]
    assert row["learning_outcome"] == "seasonality_misread"
    assert row["learning_reason_codes"] == "operator_override"
    assert row["actual_units_30d"] == "5"
    assert row["record_updated_utc"] == "2026-04-20T12:10:00Z"


def test_f012_adds_operational_truth_only_rows_when_summary_overlap_is_missing(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    actuals_path = tmp_path / "actuals.csv"
    learning_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_sales_history_learning_live.csv"
    output_dir = tmp_path / "out" / "analysis_reports"

    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00SUM001",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "25",
            }
        ],
    )
    _write_csv(
        actuals_path,
        [
            {
                "decision_snapshot_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "OPER::B00OPS001",
                "asin": "B00OPS001",
                "actual_units_30d": "12",
                "actual_profit_30d_gbp": "18",
                "actuals_basis": "operational_baseline",
            }
        ],
    )

    result = build_sales_history_learning_pack(
        summary_path=summary_path,
        actuals_path=actuals_path,
        learning_path=learning_path,
        output_dir=output_dir,
        observed_utc="2026-04-20T12:15:00Z",
    )

    assert len(result.review_df) == 2
    records = {
        (row["seller_sku"], row["asin"]): row
        for row in result.review_df.to_dict("records")
    }

    ops_row = records[("OPER::B00OPS001", "B00OPS001")]
    assert ops_row["decision_state_at_snapshot"] == "operational_truth_only"
    assert ops_row["expected_units_next_30d"] == ""
    assert ops_row["actual_units_30d"] == "12"
    assert ops_row["learning_outcome"] == "pending_outcome"
    assert ops_row["learning_reason_codes"] == "missing_expected_units"
    assert ops_row["outcome_basis_window_days"] == "30"

    health = {row["metric"]: row["value"] for row in result.health_df.to_dict("records")}
    assert health["rows_operational_truth_only"] == "1"


def test_f012_enriches_operational_truth_rows_from_alignment_expected_baseline(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    actuals_path = tmp_path / "actuals.csv"
    alignment_path = tmp_path / "alignment.csv"
    learning_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_sales_history_learning_live.csv"
    output_dir = tmp_path / "out" / "analysis_reports"

    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00SUM001",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "25",
            }
        ],
    )
    _write_csv(
        actuals_path,
        [
            {
                "decision_snapshot_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "OPER::B00OPS001",
                "asin": "B00OPS001",
                "actual_units_30d": "12",
                "actual_profit_30d_gbp": "18",
                "actuals_basis": "operational_baseline",
            }
        ],
    )
    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-20T11:59:00Z",
                "sku": "OPS-SKU-001",
                "asin": "B00OPS001",
                "expected_units_30d": "10",
                "expected_profit_30d_gbp": "5",
            }
        ],
    )

    result = build_sales_history_learning_pack(
        summary_path=summary_path,
        actuals_path=actuals_path,
        alignment_path=alignment_path,
        learning_path=learning_path,
        output_dir=output_dir,
        observed_utc="2026-04-20T12:15:00Z",
    )

    records = {
        (row["seller_sku"], row["asin"]): row
        for row in result.review_df.to_dict("records")
    }
    ops_row = records[("OPER::B00OPS001", "B00OPS001")]
    assert ops_row["decision_state_at_snapshot"] == "operational_truth_only"
    assert ops_row["expected_units_next_30d"] == "10"
    assert ops_row["expected_profit_next_30d_gbp"] == "5"
    assert ops_row["learning_outcome"] == "right_call"
    assert ops_row["learning_reason_codes"] == "inferred_from_30d_units"

    health = {row["metric"]: row["value"] for row in result.health_df.to_dict("records")}
    assert health["rows_operational_truth_only"] == "1"
    assert health["rows_operational_truth_with_expected"] == "1"


def test_f012_operational_truth_rows_use_pair_fallback_when_actuals_snapshot_is_blank(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.csv"
    actuals_path = tmp_path / "actuals.csv"
    alignment_path = tmp_path / "alignment.csv"
    learning_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_sales_history_learning_live.csv"
    output_dir = tmp_path / "out" / "analysis_reports"

    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-20T12:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "B00SUM001",
                "decision_state": "pass",
                "decision_confidence": "medium",
                "expected_units_next_30d": "10",
                "expected_profit_next_30d_gbp": "25",
            }
        ],
    )
    _write_csv(
        actuals_path,
        [
            {
                "decision_snapshot_utc": "",
                "seller_sku": "OPER::B00OPS002",
                "asin": "B00OPS002",
                "actual_units_30d": "12",
                "actual_profit_30d_gbp": "18",
                "actuals_basis": "operational_baseline",
            }
        ],
    )
    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-20T11:59:00Z",
                "sku": "OPS-SKU-002",
                "asin": "B00OPS002",
                "expected_units_30d": "10",
                "expected_profit_30d_gbp": "5",
            }
        ],
    )

    result = build_sales_history_learning_pack(
        summary_path=summary_path,
        actuals_path=actuals_path,
        alignment_path=alignment_path,
        learning_path=learning_path,
        output_dir=output_dir,
        observed_utc="2026-04-20T12:15:00Z",
    )

    records = {
        (row["seller_sku"], row["asin"]): row
        for row in result.review_df.to_dict("records")
    }
    ops_row = records[("OPER::B00OPS002", "B00OPS002")]
    assert ops_row["actual_units_30d"] == "12"
    assert ops_row["expected_units_next_30d"] == "10"
    assert ops_row["learning_outcome"] == "right_call"
