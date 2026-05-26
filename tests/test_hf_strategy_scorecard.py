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

from scripts.one_off import HF011_build_strategy_scorecard as hf011


def _write_csv(path: Path, rows: list[dict[str, object]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_hf011_strategy_scorecard_maturity_and_rates(tmp_path: Path, monkeypatch) -> None:
    action_path = tmp_path / "out" / "analysis_reports" / "hf_learning_action_outcomes_latest.csv"
    alignment_path = tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
    daily_path = tmp_path / "out" / "h_strategy_outcome_daily.csv"
    perf_path = tmp_path / "out" / "sku_performance_summary.csv"
    state_path = tmp_path / "out" / "h_pricing_cycle_state.json"

    _write_csv(
        action_path,
        [
            {
                "event_ts_utc": "2026-04-18T08:00:00Z",
                "scenario_type": "multi_seller_ladder_cap",
                "eligible_to_write_flag": "1",
                "decision_to_change_price_flag": "1",
                "write_attempted_flag": "1",
                "write_applied_flag": "0",
                "tactic_success_state": "failed",
                "seller_count": "8",
                "sku": "SKU-M1",
            },
            {
                "event_ts_utc": "2026-04-18T08:01:00Z",
                "scenario_type": "multi_seller_ladder_cap",
                "eligible_to_write_flag": "1",
                "decision_to_change_price_flag": "0",
                "write_attempted_flag": "0",
                "write_applied_flag": "0",
                "tactic_success_state": "expired",
                "seller_count": "9",
                "sku": "SKU-M2",
            },
            {
                "event_ts_utc": "2026-04-18T08:02:00Z",
                "scenario_type": "single_rival_reset",
                "eligible_to_write_flag": "1",
                "decision_to_change_price_flag": "1",
                "write_attempted_flag": "1",
                "write_applied_flag": "1",
                "tactic_success_state": "pending",
                "seller_count": "2",
                "sku": "SKU-S1",
            },
            {
                "event_ts_utc": "2026-04-18T08:03:00Z",
                "scenario_type": "suppression_reactivation",
                "eligible_to_write_flag": "1",
                "decision_to_change_price_flag": "1",
                "write_attempted_flag": "1",
                "write_applied_flag": "1",
                "tactic_success_state": "success",
                "seller_count": "3",
                "sku": "SKU-R1",
            },
            {
                "event_ts_utc": "2026-04-18T08:04:00Z",
                "scenario_type": "suppression_reactivation",
                "eligible_to_write_flag": "1",
                "decision_to_change_price_flag": "1",
                "write_attempted_flag": "1",
                "write_applied_flag": "1",
                "tactic_success_state": "success",
                "seller_count": "4",
                "sku": "SKU-R2",
            },
            {
                "event_ts_utc": "2026-04-18T08:05:00Z",
                "scenario_type": "suppression_reactivation",
                "eligible_to_write_flag": "1",
                "decision_to_change_price_flag": "0",
                "write_attempted_flag": "0",
                "write_applied_flag": "0",
                "tactic_success_state": "expired",
                "seller_count": "5",
                "sku": "SKU-R3",
            },
        ],
        columns=[
            "event_ts_utc",
            "scenario_type",
            "eligible_to_write_flag",
            "decision_to_change_price_flag",
            "write_attempted_flag",
            "write_applied_flag",
            "tactic_success_state",
            "seller_count",
            "sku",
        ],
    )

    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-18T08:10:00Z",
                "sku": "SKU-M1",
                "asin": "A1",
                "dominant_discrepancy_class": "missing_expected_baseline",
            },
            {
                "alignment_window_end_utc": "2026-04-18T08:10:00Z",
                "sku": "SKU-M2",
                "asin": "A2",
                "dominant_discrepancy_class": "underperform_vs_expected",
            },
            {
                "alignment_window_end_utc": "2026-04-18T08:10:00Z",
                "sku": "SKU-R1",
                "asin": "A3",
                "dominant_discrepancy_class": "aligned",
            },
            {
                "alignment_window_end_utc": "2026-04-18T08:10:00Z",
                "sku": "SKU-R2",
                "asin": "A4",
                "dominant_discrepancy_class": "aligned",
            },
        ],
        columns=["alignment_window_end_utc", "sku", "asin", "dominant_discrepancy_class"],
    )

    _write_csv(
        daily_path,
        [
            {
                "asof_date": "2026-04-18",
                "scenario_type": "multi_seller_ladder_cap",
                "decision_rows": "87",
                "sample_min_rows": "150",
                "provisional_sample_flag": "1",
                "failed_rows": "29",
                "expired_rows": "55",
            },
            {
                "asof_date": "2026-04-18",
                "scenario_type": "single_rival_reset",
                "decision_rows": "5",
                "sample_min_rows": "30",
                "provisional_sample_flag": "1",
                "failed_rows": "0",
                "expired_rows": "0",
            },
            {
                "asof_date": "2026-04-18",
                "scenario_type": "suppression_reactivation",
                "decision_rows": "62",
                "sample_min_rows": "20",
                "provisional_sample_flag": "0",
                "failed_rows": "0",
                "expired_rows": "2",
            },
        ],
        columns=[
            "asof_date",
            "scenario_type",
            "decision_rows",
            "sample_min_rows",
            "provisional_sample_flag",
            "failed_rows",
            "expired_rows",
        ],
    )

    _write_csv(
        perf_path,
        [
            {"sku": "SKU-R1", "window_days": "30", "units_sold": "6", "profit_exvat_gbp": "4.5"},
            {"sku": "SKU-R2", "window_days": "30", "units_sold": "8", "profit_exvat_gbp": "5.5"},
            {"sku": "SKU-R3", "window_days": "30", "units_sold": "3", "profit_exvat_gbp": "1.0"},
        ],
        columns=["sku", "window_days", "units_sold", "profit_exvat_gbp"],
    )

    state_payload = {
        "h_strategy_sample_live_multi_seller_ladder_cap_decision_rows": 87,
        "h_strategy_sample_live_multi_seller_ladder_cap_sample_min_rows": 150,
        "h_strategy_sample_live_multi_seller_ladder_cap_provisional_flag": 1,
        "h_strategy_sample_live_single_rival_reset_decision_rows": 5,
        "h_strategy_sample_live_single_rival_reset_sample_min_rows": 30,
        "h_strategy_sample_live_single_rival_reset_provisional_flag": 1,
        "h_strategy_sample_live_suppression_reactivation_decision_rows": 62,
        "h_strategy_sample_live_suppression_reactivation_sample_min_rows": 20,
        "h_strategy_sample_live_suppression_reactivation_provisional_flag": 0,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state_payload), encoding="utf-8")

    monkeypatch.setattr(hf011, "ACTION_OUTCOMES_PATH", action_path)
    monkeypatch.setattr(hf011, "ALIGNMENT_PATH", alignment_path)
    monkeypatch.setattr(hf011, "DAILY_STRATEGY_PATH", daily_path)
    monkeypatch.setattr(hf011, "SKU_PERFORMANCE_PATH", perf_path)
    monkeypatch.setattr(hf011, "H_CYCLE_STATE_PATH", state_path)
    monkeypatch.setattr(hf011, "REQUIRED_INPUTS", [action_path, alignment_path, daily_path, perf_path])
    monkeypatch.setattr(hf011, "_utc_now_iso", lambda: "2026-04-18T12:30:00Z")

    output_path = tmp_path / "out" / "analysis_reports" / "hf_strategy_scorecard_latest.csv"
    result = hf011.build_strategy_scorecard(output_path=output_path)

    assert result.rows == 3
    assert result.mature_rows == 1
    assert result.blocked_rows == 2
    assert output_path.exists()

    scorecard_df = pd.read_csv(output_path, dtype=str).fillna("").set_index("scenario_type")
    assert scorecard_df.columns.tolist() == [col for col in hf011.SCORECARD_COLUMNS if col != "scenario_type"]
    assert scorecard_df.loc["multi_seller_ladder_cap", "sample_mature_flag"] == "0"
    assert scorecard_df.loc["single_rival_reset", "sample_mature_flag"] == "0"
    assert scorecard_df.loc["suppression_reactivation", "sample_mature_flag"] == "1"
    assert scorecard_df.loc["multi_seller_ladder_cap", "review_status"] == "blocked"
    assert scorecard_df.loc["single_rival_reset", "review_status"] == "blocked"
    assert scorecard_df.loc["suppression_reactivation", "review_status"] == "eligible_shadow"
    assert scorecard_df.loc["suppression_reactivation", "actual_units_30d"] == "17"
    assert scorecard_df.loc["suppression_reactivation", "actual_profit_30d_gbp"] == "11"
