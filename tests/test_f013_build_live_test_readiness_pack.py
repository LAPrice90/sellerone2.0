from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off.F013_build_live_test_readiness_pack import build_live_test_readiness_pack


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _metric(summary_df: pd.DataFrame, metric: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == metric]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["value"])


def test_f013_builds_commercial_pack_and_summary_metrics(tmp_path: Path) -> None:
    accuracy_path = tmp_path / "accuracy.csv"
    panel_path = tmp_path / "panel.csv"
    backtest_path = tmp_path / "backtest.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        accuracy_path,
        [
            {
                "asin": "A1",
                "seller_sku": "OPER::A1",
                "truth_decision_state": "pass",
                "actual_units_30d": "10",
                "actual_profit_30d_gbp": "30",
                "model_expected_units_next_30d": "12",
                "model_expected_profit_next_30d_gbp": "28",
                "demand_error_ratio_30d": "0.2",
                "estimated_demand": "high",
                "recommended_test_qty": "6",
                "recommendation_status": "pass",
            },
            {
                "asin": "A2",
                "seller_sku": "OPER::A2",
                "truth_decision_state": "fail",
                "actual_units_30d": "2",
                "actual_profit_30d_gbp": "-2",
                "model_expected_units_next_30d": "8",
                "model_expected_profit_next_30d_gbp": "25",
                "demand_error_ratio_30d": "1.2",
                "estimated_demand": "medium",
                "recommended_test_qty": "4",
                "recommendation_status": "pass",
            },
            {
                "asin": "A3",
                "seller_sku": "OPER::A3",
                "truth_decision_state": "pass",
                "actual_units_30d": "5",
                "actual_profit_30d_gbp": "10",
                "model_expected_units_next_30d": "5",
                "model_expected_profit_next_30d_gbp": "10",
                "demand_error_ratio_30d": "1.0",
                "estimated_demand": "low",
                "recommended_test_qty": "1",
                "recommendation_status": "reject",
            },
            {
                "asin": "A4",
                "seller_sku": "OPER::A4",
                "truth_decision_state": "fail",
                "actual_units_30d": "1",
                "actual_profit_30d_gbp": "25",
                "model_expected_units_next_30d": "10",
                "model_expected_profit_next_30d_gbp": "30",
                "demand_error_ratio_30d": "0.1",
                "estimated_demand": "high",
                "recommended_test_qty": "2",
                "recommendation_status": "pass",
            },
        ],
    )
    _write_csv(
        panel_path,
        [
            {"asin": "A1", "panel_group": "big_pass", "panel_rank": "1", "selection_reason": "seed"},
            {"asin": "A2", "panel_group": "big_fail", "panel_rank": "1", "selection_reason": "seed"},
            {"asin": "A3", "panel_group": "on_the_line", "panel_rank": "1", "selection_reason": "seed"},
        ],
    )
    _write_csv(
        backtest_path,
        [
            {"asin": "A1", "observed_utc": "2026-04-21T10:00:00Z", "bsr_median_30d": "10000", "bsr_median_90d": "12000"},
            {"asin": "A2", "observed_utc": "2026-04-21T10:00:00Z", "bsr_median_30d": "130000", "bsr_median_90d": "150000"},
            {"asin": "A4", "observed_utc": "2026-04-21T10:00:00Z", "bsr_median_30d": "10000", "bsr_median_90d": "12000"},
        ],
    )

    result = build_live_test_readiness_pack(
        accuracy_path=accuracy_path,
        panel_path=panel_path,
        backtest_input_view_path=backtest_path,
        output_dir=output_dir,
        decision_profit_floor_gbp=20.0,
        observed_utc="2026-04-21T16:30:00Z",
    )

    assert len(result.pack_df.index) == 4
    by_asin = {row["asin"]: row for row in result.pack_df.to_dict("records")}

    assert by_asin["A1"]["commercial_decision_state"] == "test_buy"
    assert by_asin["A1"]["live_test_readiness_state"] == "ready_for_live_test"
    assert by_asin["A2"]["commercial_decision_state"] == "reject"
    assert by_asin["A2"]["negative_mode_truth_state"] == "negative_mode_active"
    assert by_asin["A3"]["live_test_readiness_state"] == "not_ready_rank_gap"
    assert by_asin["A3"]["false_red_flag"] == "1"
    assert by_asin["A4"]["false_green_flag"] == "1"
    assert by_asin["A4"]["starter_qty_too_high_flag"] == "1"

    assert _metric(result.summary_df, "commercial_rows_total") == "4"
    assert _metric(result.summary_df, "commercial_judged_rows") == "4"
    assert _metric(result.summary_df, "false_green_rows") == "1"
    assert _metric(result.summary_df, "false_red_rows") == "1"
    assert _metric(result.summary_df, "negative_mode_miss_rows") == "0"
    assert _metric(result.summary_df, "starter_qty_too_high_rows") == "1"
    assert _metric(result.summary_df, "starter_qty_too_low_rows") == "1"
    assert _metric(result.summary_df, "band_hit_rows") == "3"
    assert _metric(result.summary_df, "live_test_ready_rows") == "2"
    assert _metric(result.summary_df, "rank_gap_rows") == "1"
    assert _metric(result.summary_df, "panel_rows_total") == "3"
    assert _metric(result.summary_df, "panel_rows_with_blank_commercial_state") == "0"
    assert result.pack_latest_path.exists()
    assert result.summary_latest_path.exists()


def test_f013_handles_missing_accuracy_input(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    result = build_live_test_readiness_pack(
        accuracy_path=tmp_path / "missing_accuracy.csv",
        panel_path=tmp_path / "missing_panel.csv",
        backtest_input_view_path=tmp_path / "missing_backtest.csv",
        output_dir=output_dir,
        observed_utc="2026-04-21T16:31:00Z",
    )

    assert result.pack_df.empty
    assert _metric(result.summary_df, "commercial_rows_total") == "0"
    assert _metric(result.summary_df, "commercial_judged_rows") == "0"
    assert _metric(result.summary_df, "live_test_ready_rows") == "0"
    assert _metric(result.summary_df, "panel_rows_total") == "0"


def test_f013_uses_full_capture_rank_window_when_backtest_rank_missing(tmp_path: Path) -> None:
    accuracy_path = tmp_path / "accuracy.csv"
    panel_path = tmp_path / "panel.csv"
    backtest_path = tmp_path / "backtest.csv"
    capture_manifest_dir = tmp_path / "capture_manifests"
    output_dir = tmp_path / "out"

    _write_csv(
        accuracy_path,
        [
            {
                "asin": "A5",
                "seller_sku": "OPER::A5",
                "truth_decision_state": "pass",
                "actual_units_30d": "12",
                "actual_profit_30d_gbp": "32",
                "model_expected_units_next_30d": "10",
                "model_expected_profit_next_30d_gbp": "25",
                "demand_error_ratio_30d": "0.1",
                "estimated_demand": "high",
                "recommended_test_qty": "5",
                "recommendation_status": "pass",
            }
        ],
    )
    _write_csv(panel_path, [{"asin": "A5", "panel_group": "big_pass", "panel_rank": "1", "selection_reason": "seed"}])
    _write_csv(backtest_path, [{"asin": "A5", "bsr_median_30d": "", "bsr_median_90d": ""}])

    raw_json_path = tmp_path / "raw_capture.json"
    bsr_points = ";".join([f"2026-01-{day:02d}={20000 + day}" for day in range(1, 31)]) + ";" + ";".join(
        [f"2026-02-{day:02d}={20500 + day}" for day in range(1, 29)]
    )
    raw_payload = {
        "scraped_data": {
            "chart_raw_bsr_daily_series": bsr_points,
        }
    }
    raw_json_path.write_text(json.dumps(raw_payload), encoding="utf-8")

    capture_manifest_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        capture_manifest_dir / "f_full_capture_manifest_20260421T200000Z.csv",
        [
            {
                "observed_utc": "2026-04-21T20:00:00Z",
                "run_id": "20260421T200000Z_A5_p1",
                "asin": "A5",
                "capture_status": "success",
                "raw_json_path": str(raw_json_path),
            }
        ],
    )

    result = build_live_test_readiness_pack(
        accuracy_path=accuracy_path,
        panel_path=panel_path,
        backtest_input_view_path=backtest_path,
        full_capture_manifest_dir=capture_manifest_dir,
        output_dir=output_dir,
        decision_profit_floor_gbp=20.0,
        observed_utc="2026-04-21T16:32:00Z",
    )

    assert len(result.pack_df.index) == 1
    row = result.pack_df.iloc[0]
    assert row["sales_rank_best_observed"] != ""
    assert row["sales_rank_worst_observed"] != ""
    assert row["live_test_readiness_state"] == "ready_for_live_test"
    assert _metric(result.summary_df, "rows_using_full_capture_rank_window") == "1"
    assert _metric(result.summary_df, "rows_missing_rank_window") == "0"
