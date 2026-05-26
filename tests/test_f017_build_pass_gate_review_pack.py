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

from scripts.one_off.F017_build_pass_gate_review_pack import build_pass_gate_review_pack


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _metric(summary_df: pd.DataFrame, metric: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == metric]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["value"])


def test_f017_builds_blockers_recovery_and_panel(tmp_path: Path) -> None:
    readiness_path = tmp_path / "readiness.csv"
    accuracy_path = tmp_path / "accuracy.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        readiness_path,
        [
            {
                "asin": "A1",
                "seller_sku": "OPER::A1",
                "commercial_decision_state": "test_buy",
                "live_test_readiness_state": "ready_for_live_test",
                "truth_decision_state": "pass",
                "actual_units_30d": "20",
                "actual_profit_30d_gbp": "50",
                "recommendation_status": "approve_test_buy",
                "recommended_test_qty": "8",
                "starter_test_qty_recommended": "5",
                "starter_order_band": "controlled_test",
                "demand_consistency_band": "stable",
                "sales_lower_30d": "10",
                "sales_upper_30d": "30",
                "rank_snapshot_risk_state": "low_rank_risk",
                "profit_risk_band": "strong",
                "negative_mode_truth_state": "negative_mode_clear",
            },
            {
                "asin": "A2",
                "seller_sku": "OPER::A2",
                "commercial_decision_state": "reject",
                "live_test_readiness_state": "not_ready_commercial",
                "truth_decision_state": "pass",
                "actual_units_30d": "100",
                "actual_profit_30d_gbp": "120",
                "recommendation_status": "reject",
                "recommended_test_qty": "0",
                "starter_test_qty_recommended": "0",
                "starter_order_band": "hold",
                "demand_consistency_band": "stable",
                "sales_lower_30d": "80",
                "sales_upper_30d": "130",
                "rank_snapshot_risk_state": "low_rank_risk",
                "profit_risk_band": "strong",
                "negative_mode_truth_state": "negative_mode_clear",
            },
            {
                "asin": "A3",
                "seller_sku": "OPER::A3",
                "commercial_decision_state": "reject",
                "live_test_readiness_state": "not_ready_commercial",
                "truth_decision_state": "pass",
                "actual_units_30d": "30",
                "actual_profit_30d_gbp": "35",
                "recommendation_status": "reject",
                "recommended_test_qty": "0",
                "starter_test_qty_recommended": "0",
                "starter_order_band": "hold",
                "demand_consistency_band": "variable",
                "sales_lower_30d": "20",
                "sales_upper_30d": "50",
                "rank_snapshot_risk_state": "moderate_rank_risk",
                "profit_risk_band": "healthy",
                "negative_mode_truth_state": "negative_mode_clear",
            },
            {
                "asin": "A4",
                "seller_sku": "OPER::A4",
                "commercial_decision_state": "reject",
                "live_test_readiness_state": "not_ready_commercial",
                "truth_decision_state": "pass",
                "actual_units_30d": "40",
                "actual_profit_30d_gbp": "40",
                "recommendation_status": "reject",
                "recommended_test_qty": "0",
                "starter_test_qty_recommended": "0",
                "starter_order_band": "hold",
                "demand_consistency_band": "unstable",
                "sales_lower_30d": "10",
                "sales_upper_30d": "80",
                "rank_snapshot_risk_state": "low_rank_risk",
                "profit_risk_band": "strong",
                "negative_mode_truth_state": "negative_mode_clear",
            },
            {
                "asin": "A5",
                "seller_sku": "OPER::A5",
                "commercial_decision_state": "reject",
                "live_test_readiness_state": "not_ready_commercial",
                "truth_decision_state": "fail",
                "actual_units_30d": "2",
                "actual_profit_30d_gbp": "-5",
                "recommendation_status": "reject",
                "recommended_test_qty": "0",
                "starter_test_qty_recommended": "0",
                "starter_order_band": "hold",
                "demand_consistency_band": "unstable",
                "sales_lower_30d": "1",
                "sales_upper_30d": "10",
                "rank_snapshot_risk_state": "low_rank_risk",
                "profit_risk_band": "negative",
                "negative_mode_truth_state": "negative_mode_active",
            },
            {
                "asin": "A6",
                "seller_sku": "OPER::A6",
                "commercial_decision_state": "reject",
                "live_test_readiness_state": "not_ready_commercial",
                "truth_decision_state": "fail",
                "actual_units_30d": "3",
                "actual_profit_30d_gbp": "18",
                "recommendation_status": "",
                "recommended_test_qty": "",
                "starter_test_qty_recommended": "3",
                "starter_order_band": "controlled_test",
                "demand_consistency_band": "stable",
                "sales_lower_30d": "2",
                "sales_upper_30d": "4",
                "rank_snapshot_risk_state": "moderate_rank_risk",
                "profit_risk_band": "near_floor",
                "negative_mode_truth_state": "negative_mode_risk",
            },
        ],
    )

    _write_csv(
        accuracy_path,
        [
            {"asin": "A1", "observed_utc": "2026-04-22T13:00:00Z", "model_side_evidence_state": "full_decision_and_estimate"},
            {"asin": "A2", "observed_utc": "2026-04-22T13:00:00Z", "model_side_evidence_state": "full_decision_and_estimate"},
            {"asin": "A3", "observed_utc": "2026-04-22T13:00:00Z", "model_side_evidence_state": "full_decision_and_estimate"},
            {"asin": "A4", "observed_utc": "2026-04-22T13:00:00Z", "model_side_evidence_state": "full_decision_and_estimate"},
            {"asin": "A5", "observed_utc": "2026-04-22T13:00:00Z", "model_side_evidence_state": "full_decision_and_estimate"},
            {"asin": "A6", "observed_utc": "2026-04-22T13:00:00Z", "model_side_evidence_state": "estimate_only"},
        ],
    )

    result = build_pass_gate_review_pack(
        readiness_path=readiness_path,
        accuracy_path=accuracy_path,
        output_dir=output_dir,
        observed_utc="2026-04-22T14:00:00Z",
    )

    assert len(result.review_df.index) == 6
    by_asin = {row["asin"]: row for row in result.review_df.to_dict("records")}

    assert by_asin["A1"]["recovery_lane_state"] == "current_test_buy"
    assert by_asin["A1"]["pass_check_tier"] == "tier_a"

    assert by_asin["A2"]["first_blocker_code"] == "blocked_legacy_recommendation_reject"
    assert by_asin["A2"]["false_red_candidate_flag"] == "1"
    assert by_asin["A2"]["recovery_lane_state"] == "promote_to_test_buy"

    assert by_asin["A3"]["false_red_candidate_flag"] == "1"
    assert by_asin["A3"]["recovery_lane_state"] == "promote_to_watch"
    assert by_asin["A3"]["pass_check_tier"] == "tier_b"

    assert by_asin["A4"]["first_blocker_code"] == "blocked_demand_instability"
    assert by_asin["A4"]["recovery_lane_state"] == "review_only_profitable_reject"
    assert by_asin["A4"]["pass_check_tier"] == "tier_c"

    assert by_asin["A5"]["first_blocker_code"] == "blocked_negative_mode"
    assert by_asin["A5"]["recovery_lane_state"] == "keep_reject"

    assert by_asin["A6"]["first_blocker_code"] == "blocked_missing_model_decision"
    assert by_asin["A6"]["expanded_panel_group"] == "near_floor_review"

    assert _metric(result.summary_df, "rows_total") == "6"
    assert _metric(result.summary_df, "false_red_candidate_rows") == "2"
    assert _metric(result.summary_df, "promote_to_test_buy_rows") == "1"
    assert _metric(result.summary_df, "promote_to_watch_rows") == "1"
    assert _metric(result.summary_df, "review_only_profitable_reject_rows") == "1"
    assert _metric(result.summary_df, "tier_a_rows") == "2"
    assert _metric(result.summary_df, "tier_b_rows") == "1"
    assert _metric(result.summary_df, "tier_c_rows") == "1"
    assert _metric(result.summary_df, "expanded_panel::profitable_reject_gbp20_plus") == "3"
    assert _metric(result.summary_df, "expanded_panel::near_floor_review") == "1"

    assert result.review_latest_path.exists()
    assert result.panel_latest_path.exists()
    assert result.summary_latest_path.exists()
