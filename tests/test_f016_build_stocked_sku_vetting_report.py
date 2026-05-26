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

from scripts.one_off.F016_build_stocked_sku_vetting_report import build_stocked_sku_vetting_report


def test_f016_builds_current_and_prior_vetting_report(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()

    current_pack_path = analysis_dir / "f_live_test_readiness_pack_latest.csv"
    actuals_path = analysis_dir / "f_sales_history_learning_actuals_latest.csv"
    manifest_path = analysis_dir / "f_full_capture_manifest_20260422T120000Z.csv"
    raw_json_path = analysis_dir / "capture.json"

    pd.DataFrame(
        [
            {
                "asin": "B000TEST01",
                "seller_sku": "OPER::B000TEST01",
                "commercial_decision_state": "test_buy",
                "live_test_readiness_state": "ready_for_live_test",
                "truth_decision_state": "pass",
                "actual_units_30d": "12",
                "actual_profit_30d_gbp": "30",
                "sales_lower_30d": "8",
                "sales_upper_30d": "18",
                "rank_snapshot_risk_state": "low_rank_risk",
                "starter_order_band": "controlled_test",
                "starter_test_qty_recommended": "3",
                "model_expected_units_next_30d": "10",
                "model_expected_profit_next_30d_gbp": "40",
                "recommendation_status": "approve_test_buy",
                "recommended_test_qty": "5",
            },
            {
                "asin": "B000TEST02",
                "seller_sku": "OPER::B000TEST02",
                "commercial_decision_state": "reject",
                "live_test_readiness_state": "not_ready_commercial",
                "truth_decision_state": "fail",
                "actual_units_30d": "2",
                "actual_profit_30d_gbp": "5",
                "sales_lower_30d": "1",
                "sales_upper_30d": "4",
                "rank_snapshot_risk_state": "high_rank_risk",
                "starter_order_band": "hold",
                "starter_test_qty_recommended": "0",
                "model_expected_units_next_30d": "15",
                "model_expected_profit_next_30d_gbp": "0",
                "recommendation_status": "reject",
                "recommended_test_qty": "0",
            },
        ]
    ).to_csv(current_pack_path, index=False)

    pd.DataFrame(
        [
            {
                "seller_sku": "OPER::B000TEST01",
                "asin": "B000TEST01",
                "actuals_basis": "operational_baseline",
                "actuals_observed_utc": "2026-04-22T12:00:00Z",
                "actual_units_30d": "12",
                "actual_units_60d": "20",
                "actual_profit_30d_gbp": "30",
                "actual_profit_60d_gbp": "45",
            },
            {
                "seller_sku": "OPER::B000TEST02",
                "asin": "B000TEST02",
                "actuals_basis": "operational_baseline",
                "actuals_observed_utc": "2026-04-22T12:00:00Z",
                "actual_units_30d": "2",
                "actual_units_60d": "7",
                "actual_profit_30d_gbp": "5",
                "actual_profit_60d_gbp": "9",
            },
        ]
    ).to_csv(actuals_path, index=False)

    raw_json_path.write_text(
        json.dumps(
            {
                "scraped_data": {
                    "chart_raw_bsr_daily_series": (
                        "2026-03-20=30000;2026-03-21=32000;2026-03-22=31000;2026-03-23=33000;"
                        "2026-04-19=28000;2026-04-20=29000;2026-04-21=30000"
                    )
                }
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "run_id": "run-1",
                "observed_utc": "2026-04-22T12:00:00Z",
                "capture_status": "success",
                "asin": "B000TEST01",
                "raw_json_path": str(raw_json_path),
            },
            {
                "run_id": "run-2",
                "observed_utc": "2026-04-22T12:00:00Z",
                "capture_status": "success",
                "asin": "B000TEST02",
                "raw_json_path": str(raw_json_path),
            },
        ]
    ).to_csv(manifest_path, index=False)

    result = build_stocked_sku_vetting_report(
        current_pack_path=current_pack_path,
        actuals_path=actuals_path,
        full_capture_manifest_dir=analysis_dir,
        output_dir=analysis_dir,
        observed_utc="2026-04-22T12:00:00Z",
        lookback_days=30,
    )

    assert len(result.report_df) == 2
    first = result.report_df[result.report_df["asin"] == "B000TEST01"].iloc[0]
    assert first["prior_window_units_30d"] == "8"
    assert first["prior_window_profit_30d_gbp"] == "15"
    assert first["decision_30d_ago_state"] == "watch"
    assert first["outcome_next_30d_truth_decision_state"] == "pass"
    assert first["decision_30d_ago_vs_outcome"] == "missed_winner"

    second = result.report_df[result.report_df["asin"] == "B000TEST02"].iloc[0]
    assert second["prior_window_units_30d"] == "5"
    assert second["prior_window_profit_30d_gbp"] == "4"
    assert second["decision_30d_ago_state"] == "reject"
    assert second["decision_30d_ago_vs_outcome"] == "avoided_loser"

    summary = {row["metric"]: row["value"] for _, row in result.summary_df.iterrows()}
    assert summary["rows_total"] == "2"
    assert summary["current_test_buy_rows"] == "1"
    assert summary["prior_watch_rows"] == "1"
    assert summary["prior_reject_rows"] == "1"
    assert summary["prior_missed_winner_rows"] == "1"
    assert summary["prior_avoided_loser_rows"] == "1"
    assert result.markdown_latest_path.exists()
