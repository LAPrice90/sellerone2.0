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

from scripts.one_off import HF001_build_learning_baseline as hf001


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_build_baseline_outputs_and_coverage_states(tmp_path: Path, monkeypatch) -> None:
    paths = {
        "IDENTITY_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv",
        "ASSUMPTION_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_assumption_snapshots_latest.csv",
        "H_OUTCOME_LOG_PATH": tmp_path / "out" / "h_strategy_outcome_log.csv",
        "H_OUTCOME_DAILY_PATH": tmp_path / "out" / "h_strategy_outcome_daily.csv",
        "LISTING_SNAPSHOT_PATH": tmp_path / "out" / "listing_offer_snapshot_latest.csv",
        "LISTING_SELLER_SNAPSHOT_PATH": tmp_path / "out" / "listing_offer_seller_snapshot_latest.csv",
        "LISTING_HISTORY_PATH": tmp_path / "out" / "listing_offer_history.csv",
        "LISTING_SELLER_HISTORY_PATH": tmp_path / "out" / "listing_offer_seller_observation_history.csv",
        "HOS_MARKET_PATH": tmp_path / "out" / "hos_daily_market_snapshot_latest.csv",
        "SKU_PERF_PATH": tmp_path / "out" / "sku_performance_summary.csv",
        "SKU_VELOCITY_PATH": tmp_path / "out" / "sku_sales_velocity.csv",
        "F_SALES_VALIDATION_PATH": tmp_path / "out" / "analysis_reports" / "f_sales_history_validation_latest.csv",
        "F_CALIBRATION_PATH": tmp_path / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv",
        "F_LEGACY_EVIDENCE_PATH": tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv",
        "F_LEGACY_CHART_PATH": tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_chart_daily_raw_live.csv",
    }

    identity_columns = [
        "snapshot_utc",
        "candidate_id",
        "feeder_candidate_id",
        "supplier_id",
        "supplier_sku",
        "asin",
        "sku",
        "sku_resolution_status",
        "sku_resolution_source",
        "asin_value_count",
        "supplier_sku_value_count",
        "asin_conflict_flag",
        "supplier_sku_conflict_flag",
        "source_screening_flag",
        "source_recommendation_flag",
        "source_queue_flag",
        "source_decision_flag",
        "source_handoff_flag",
        "source_event_count",
        "latest_source_utc",
        "latest_source_name",
    ]

    _write_csv(
        paths["IDENTITY_PATH"],
        [
            {
                "snapshot_utc": "2026-04-17T18:00:00Z",
                "candidate_id": "C_OK",
                "feeder_candidate_id": "F_OK",
                "supplier_id": "SUP-1",
                "supplier_sku": "SS1",
                "asin": "A1",
                "sku": "SKU1",
                "sku_resolution_status": "RESOLVED_FROM_H_SNAPSHOT",
                "sku_resolution_source": "event",
                "asin_value_count": "1",
                "supplier_sku_value_count": "1",
                "asin_conflict_flag": "0",
                "supplier_sku_conflict_flag": "0",
                "source_screening_flag": "1",
                "source_recommendation_flag": "1",
                "source_queue_flag": "1",
                "source_decision_flag": "1",
                "source_handoff_flag": "0",
                "source_event_count": "2",
                "latest_source_utc": "2026-04-17T08:00:00Z",
                "latest_source_name": "approval_decision",
            },
            {
                "snapshot_utc": "2026-04-17T18:00:00Z",
                "candidate_id": "C_MISSING",
                "feeder_candidate_id": "F_MISSING",
                "supplier_id": "SUP-2",
                "supplier_sku": "SS2",
                "asin": "",
                "sku": "",
                "sku_resolution_status": "UNRESOLVED_NO_ASIN",
                "sku_resolution_source": "event",
                "asin_value_count": "0",
                "supplier_sku_value_count": "1",
                "asin_conflict_flag": "0",
                "supplier_sku_conflict_flag": "0",
                "source_screening_flag": "1",
                "source_recommendation_flag": "0",
                "source_queue_flag": "0",
                "source_decision_flag": "0",
                "source_handoff_flag": "0",
                "source_event_count": "1",
                "latest_source_utc": "2026-04-17T08:05:00Z",
                "latest_source_name": "screening",
            },
            {
                "snapshot_utc": "2026-04-17T18:00:00Z",
                "candidate_id": "C_STALE",
                "feeder_candidate_id": "F_STALE",
                "supplier_id": "SUP-3",
                "supplier_sku": "SS3",
                "asin": "A3",
                "sku": "",
                "sku_resolution_status": "UNRESOLVED_ASIN_NOT_IN_H_SCOPE",
                "sku_resolution_source": "event",
                "asin_value_count": "1",
                "supplier_sku_value_count": "1",
                "asin_conflict_flag": "0",
                "supplier_sku_conflict_flag": "0",
                "source_screening_flag": "1",
                "source_recommendation_flag": "0",
                "source_queue_flag": "0",
                "source_decision_flag": "0",
                "source_handoff_flag": "0",
                "source_event_count": "1",
                "latest_source_utc": "2026-04-17T08:10:00Z",
                "latest_source_name": "screening",
            },
            {
                "snapshot_utc": "2026-04-17T18:00:00Z",
                "candidate_id": "C_THIN",
                "feeder_candidate_id": "F_THIN",
                "supplier_id": "SUP-4",
                "supplier_sku": "SS4",
                "asin": "A4",
                "sku": "",
                "sku_resolution_status": "UNRESOLVED_ASIN_NOT_IN_H_SCOPE",
                "sku_resolution_source": "event",
                "asin_value_count": "1",
                "supplier_sku_value_count": "1",
                "asin_conflict_flag": "0",
                "supplier_sku_conflict_flag": "0",
                "source_screening_flag": "1",
                "source_recommendation_flag": "0",
                "source_queue_flag": "0",
                "source_decision_flag": "0",
                "source_handoff_flag": "0",
                "source_event_count": "1",
                "latest_source_utc": "2026-04-17T08:20:00Z",
                "latest_source_name": "screening",
            },
        ],
        columns=identity_columns,
    )

    _write_csv(
        paths["ASSUMPTION_PATH"],
        [
            {
                "snapshot_utc": "2026-04-17T18:00:00Z",
                "candidate_id": "C_OK",
                "feeder_candidate_id": "F_OK",
                "supplier_id": "SUP-1",
                "supplier_sku": "SS1",
                "asin": "A1",
                "snapshot_stage": "approval_decision",
                "assumption_anchor_utc": "2026-04-17T08:00:00Z",
                "assumption_anchor_source": "approval_decision",
                "in_scope_approval_decision_flag": "1",
                "recommendation_status": "approved",
                "recommended_test_qty": "4",
                "estimated_roi_pct": "25",
                "estimated_margin_gbp": "2.0",
                "estimated_demand": "8",
                "decision_action": "approve",
                "final_decision_status": "approved",
                "decision_source": "operator",
                "actor": "luke",
                "decision_utc": "2026-04-17T08:00:00Z",
                "handoff_utc": "",
                "source_row_hash": "HASH-1",
                "source_file_path": "out/systems/F/history/feeder_approval_decisions_log.csv",
                "source_seen_at_utc": "2026-04-17T08:00:01Z",
            }
        ],
        columns=[
            "snapshot_utc",
            "candidate_id",
            "feeder_candidate_id",
            "supplier_id",
            "supplier_sku",
            "asin",
            "snapshot_stage",
            "assumption_anchor_utc",
            "assumption_anchor_source",
            "in_scope_approval_decision_flag",
            "recommendation_status",
            "recommended_test_qty",
            "estimated_roi_pct",
            "estimated_margin_gbp",
            "estimated_demand",
            "decision_action",
            "final_decision_status",
            "decision_source",
            "actor",
            "decision_utc",
            "handoff_utc",
            "source_row_hash",
            "source_file_path",
            "source_seen_at_utc",
        ],
    )

    _write_csv(
        paths["H_OUTCOME_LOG_PATH"],
        [
            {
                "event_ts_utc": "2026-04-17T10:00:00Z",
                "run_id": "RUN-1",
                "sku": "SKU1",
                "asin": "A1",
                "scenario_type": "share_hold",
                "chosen_tactic": "REGAIN",
                "buy_box_state_before": "lost",
                "buy_box_state_after": "won",
                "seller_count": "2",
                "lowest_price_1_gbp": "9.80",
                "lowest_price_2_gbp": "10.00",
                "lowest_price_3_gbp": "",
                "our_price_before_gbp": "10.50",
                "target_price_gbp": "9.90",
                "price_written_gbp": "9.90",
                "hold_until_utc": "",
                "response_window_minutes": "60",
                "retry_budget_remaining": "0",
                "stop_rule_code": "",
                "writer_outcome": "APPLIED",
                "tactic_success_state": "success",
                "reason_codes_json": "[]",
                "tactic_case_id": "CASE-1",
            },
            {
                "event_ts_utc": "2026-04-17T10:05:00Z",
                "run_id": "RUN-1",
                "sku": "SKU2",
                "asin": "A2",
                "scenario_type": "share_hold",
                "chosen_tactic": "HOLD_OBSERVE",
                "buy_box_state_before": "shared",
                "buy_box_state_after": "shared",
                "seller_count": "3",
                "lowest_price_1_gbp": "8.90",
                "lowest_price_2_gbp": "9.20",
                "lowest_price_3_gbp": "",
                "our_price_before_gbp": "9.20",
                "target_price_gbp": "9.20",
                "price_written_gbp": "",
                "hold_until_utc": "",
                "response_window_minutes": "120",
                "retry_budget_remaining": "1",
                "stop_rule_code": "",
                "writer_outcome": "NO_WRITE_REQUIRED",
                "tactic_success_state": "resolved",
                "reason_codes_json": "[]",
                "tactic_case_id": "CASE-2",
            },
            {
                "event_ts_utc": "2026-04-17T10:10:00Z",
                "run_id": "RUN-2",
                "sku": "SKU3",
                "asin": "A3",
                "scenario_type": "share_hold",
                "chosen_tactic": "SELLER_DETAIL_HOLD",
                "buy_box_state_before": "lost",
                "buy_box_state_after": "lost",
                "seller_count": "4",
                "lowest_price_1_gbp": "7.90",
                "lowest_price_2_gbp": "8.10",
                "lowest_price_3_gbp": "",
                "our_price_before_gbp": "8.20",
                "target_price_gbp": "8.00",
                "price_written_gbp": "",
                "hold_until_utc": "",
                "response_window_minutes": "30",
                "retry_budget_remaining": "2",
                "stop_rule_code": "",
                "writer_outcome": "READ_ONLY_NO_WRITE",
                "tactic_success_state": "aborted",
                "reason_codes_json": "[]",
                "tactic_case_id": "CASE-3",
            },
        ],
        columns=[
            "event_ts_utc",
            "run_id",
            "sku",
            "asin",
            "scenario_type",
            "chosen_tactic",
            "buy_box_state_before",
            "buy_box_state_after",
            "seller_count",
            "lowest_price_1_gbp",
            "lowest_price_2_gbp",
            "lowest_price_3_gbp",
            "our_price_before_gbp",
            "target_price_gbp",
            "price_written_gbp",
            "hold_until_utc",
            "response_window_minutes",
            "retry_budget_remaining",
            "stop_rule_code",
            "writer_outcome",
            "tactic_success_state",
            "reason_codes_json",
            "tactic_case_id",
        ],
    )

    _write_csv(
        paths["H_OUTCOME_DAILY_PATH"],
        [
            {
                "asof_date": "2026-04-17",
                "scenario_type": "share_hold",
                "chosen_tactic": "REGAIN",
                "decision_rows": "1",
                "applied_rows": "1",
                "no_write_rows": "0",
                "resolved_rows": "1",
                "pending_rows": "0",
                "success_rows": "1",
                "failed_rows": "0",
                "expired_rows": "0",
                "aborted_rows": "0",
                "success_rate_pct": "100",
                "failed_rate_pct": "0",
                "sample_min_rows": "30",
                "provisional_sample_flag": "0",
                "avg_seller_count": "2.0",
                "avg_price_gap_to_lowest_gbp": "0.2",
                "below_break_even_rows": "0",
                "at_floor_rows": "0",
                "notes": "",
            }
        ],
        columns=[
            "asof_date",
            "scenario_type",
            "chosen_tactic",
            "decision_rows",
            "applied_rows",
            "no_write_rows",
            "resolved_rows",
            "pending_rows",
            "success_rows",
            "failed_rows",
            "expired_rows",
            "aborted_rows",
            "success_rate_pct",
            "failed_rate_pct",
            "sample_min_rows",
            "provisional_sample_flag",
            "avg_seller_count",
            "avg_price_gap_to_lowest_gbp",
            "below_break_even_rows",
            "at_floor_rows",
            "notes",
        ],
    )

    listing_rows = [
        {
            "timestamp_utc": "2026-04-17T09:59:00Z",
            "asof_date": "2026-04-17",
            "marketplace": "UK",
            "sku": "SKU1",
            "asin": "A1",
            "our_price": "10.5",
            "buy_box_price": "9.9",
            "lowest_fba_price": "9.8",
            "lowest_fbm_price": "10.1",
            "offer_count_fba": "3",
            "offer_count_fbm": "2",
            "seller_detail_status": "",
            "seller_detail_attempted_flag": "0",
            "seller_detail_offer_row_count": "0",
            "seller_detail_snapshot_ts_utc": "",
            "retry_next_run_flag": "0",
            "list_price": "",
            "list_price_currency": "",
            "apparent_sale_amount_gbp": "",
            "apparent_sale_pct": "",
            "bsr": "1000",
            "bsr_category": "",
            "source": "test",
            "notes": "",
            "buy_box_present_flag": "1",
            "outcome_known_flag": "1",
            "we_present_flag": "1",
            "seller_detail_resolution_status": "",
            "seller_detail_retry_attempt_count": "0",
            "seller_detail_rotation_skip_count": "0",
            "seller_detail_empty_response_count": "0",
            "seller_detail_api_error_count": "0",
            "seller_detail_force_attempt_flag": "0",
            "seller_detail_retry_exhausted_flag": "0",
            "seller_detail_operator_reason": "",
        },
        {
            "timestamp_utc": "2026-04-17T10:04:00Z",
            "asof_date": "2026-04-17",
            "marketplace": "UK",
            "sku": "SKU2",
            "asin": "A2",
            "our_price": "9.2",
            "buy_box_price": "9.2",
            "lowest_fba_price": "9.0",
            "lowest_fbm_price": "9.1",
            "offer_count_fba": "2",
            "offer_count_fbm": "1",
            "seller_detail_status": "",
            "seller_detail_attempted_flag": "0",
            "seller_detail_offer_row_count": "0",
            "seller_detail_snapshot_ts_utc": "",
            "retry_next_run_flag": "0",
            "list_price": "",
            "list_price_currency": "",
            "apparent_sale_amount_gbp": "",
            "apparent_sale_pct": "",
            "bsr": "2000",
            "bsr_category": "",
            "source": "test",
            "notes": "",
            "buy_box_present_flag": "1",
            "outcome_known_flag": "1",
            "we_present_flag": "1",
            "seller_detail_resolution_status": "",
            "seller_detail_retry_attempt_count": "0",
            "seller_detail_rotation_skip_count": "0",
            "seller_detail_empty_response_count": "0",
            "seller_detail_api_error_count": "0",
            "seller_detail_force_attempt_flag": "0",
            "seller_detail_retry_exhausted_flag": "0",
            "seller_detail_operator_reason": "",
        },
        {
            "timestamp_utc": "2026-04-17T10:09:00Z",
            "asof_date": "2026-04-17",
            "marketplace": "UK",
            "sku": "SKU3",
            "asin": "A3",
            "our_price": "8.2",
            "buy_box_price": "8.0",
            "lowest_fba_price": "7.9",
            "lowest_fbm_price": "8.1",
            "offer_count_fba": "4",
            "offer_count_fbm": "1",
            "seller_detail_status": "",
            "seller_detail_attempted_flag": "0",
            "seller_detail_offer_row_count": "0",
            "seller_detail_snapshot_ts_utc": "",
            "retry_next_run_flag": "0",
            "list_price": "",
            "list_price_currency": "",
            "apparent_sale_amount_gbp": "",
            "apparent_sale_pct": "",
            "bsr": "3000",
            "bsr_category": "",
            "source": "test",
            "notes": "",
            "buy_box_present_flag": "1",
            "outcome_known_flag": "1",
            "we_present_flag": "1",
            "seller_detail_resolution_status": "",
            "seller_detail_retry_attempt_count": "0",
            "seller_detail_rotation_skip_count": "0",
            "seller_detail_empty_response_count": "0",
            "seller_detail_api_error_count": "0",
            "seller_detail_force_attempt_flag": "0",
            "seller_detail_retry_exhausted_flag": "0",
            "seller_detail_operator_reason": "",
        },
    ]
    listing_columns = list(listing_rows[0].keys())
    _write_csv(paths["LISTING_HISTORY_PATH"], listing_rows, columns=listing_columns)
    _write_csv(paths["LISTING_SNAPSHOT_PATH"], [listing_rows[0]], columns=listing_columns)

    _write_csv(
        paths["LISTING_SELLER_SNAPSHOT_PATH"],
        [{"timestamp_utc": "2026-04-17T10:00:00Z", "asof_date": "2026-04-17", "marketplace": "UK", "sku": "SKU1", "asin": "A1", "seller_id": "SELL1"}],
        columns=["timestamp_utc", "asof_date", "marketplace", "sku", "asin", "seller_id"],
    )
    _write_csv(
        paths["LISTING_SELLER_HISTORY_PATH"],
        [{"timestamp_utc": "2026-04-17T10:00:00Z", "asof_date": "2026-04-17", "marketplace": "UK", "sku": "SKU1", "asin": "A1", "seller_id": "SELL1"}],
        columns=["timestamp_utc", "asof_date", "marketplace", "sku", "asin", "seller_id"],
    )

    _write_csv(
        paths["HOS_MARKET_PATH"],
        [
            {
                "asof_date": "2026-04-17",
                "marketplace": "UK",
                "sku": "SKU1",
                "asin": "A1",
                "amazon_present_flag": "0",
                "seller_entry_count_today": "1",
                "seller_exit_count_today": "0",
                "delivery_parity_flag": "1",
                "break_even_gross_gbp": "11.1",
            }
        ],
        columns=[
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "amazon_present_flag",
            "seller_entry_count_today",
            "seller_exit_count_today",
            "delivery_parity_flag",
            "break_even_gross_gbp",
        ],
    )

    _write_csv(
        paths["SKU_PERF_PATH"],
        [
            {"sku": "SKU1", "break_even_price_gbp": "10.9"},
            {"sku": "SKU2", "break_even_price_gbp": "9.0"},
            {"sku": "SKU3", "break_even_price_gbp": "8.1"},
        ],
        columns=["sku", "break_even_price_gbp"],
    )
    _write_csv(paths["SKU_VELOCITY_PATH"], [{"sku": "SKU1", "window_days": "30"}], columns=["sku", "window_days"])
    _write_csv(
        paths["F_SALES_VALIDATION_PATH"],
        [{"seller_sku": "SS1", "asin": "A1", "month_label_iso": "2026-03", "month_units": "5"}],
        columns=["seller_sku", "asin", "month_label_iso", "month_units"],
    )
    _write_csv(
        paths["F_CALIBRATION_PATH"],
        [{"seller_sku": "SS1", "asin": "A1", "recommendation": "Manual review"}],
        columns=["seller_sku", "asin", "recommendation"],
    )

    _write_csv(
        paths["F_LEGACY_EVIDENCE_PATH"],
        [
            {"candidate_id": "C_OK", "supplier_sku": "SS1", "asin": "A1", "observed_utc": "2026-04-15T00:00:00Z", "scrape_success": "1"},
            {"candidate_id": "C_STALE", "supplier_sku": "SS3", "asin": "A3", "observed_utc": "2026-02-01T00:00:00Z", "scrape_success": "1"},
            {"candidate_id": "C_THIN", "supplier_sku": "SS4", "asin": "A4", "observed_utc": "2026-04-16T00:00:00Z", "scrape_success": "1"},
        ],
        columns=["candidate_id", "supplier_sku", "asin", "observed_utc", "scrape_success"],
    )

    chart_rows: list[dict[str, str]] = []
    for idx in range(40):
        chart_rows.append(
            {
                "observed_utc": f"2026-04-{(idx % 28) + 1:02d}T00:00:00Z",
                "candidate_id": "C_OK",
                "supplier_sku": "SS1",
                "asin": "A1",
            }
        )
    for idx in range(40):
        chart_rows.append(
            {
                "observed_utc": f"2026-02-{(idx % 28) + 1:02d}T00:00:00Z",
                "candidate_id": "C_STALE",
                "supplier_sku": "SS3",
                "asin": "A3",
            }
        )
    for idx in range(5):
        chart_rows.append(
            {
                "observed_utc": f"2026-04-{(idx % 28) + 1:02d}T00:00:00Z",
                "candidate_id": "C_THIN",
                "supplier_sku": "SS4",
                "asin": "A4",
            }
        )
    _write_csv(
        paths["F_LEGACY_CHART_PATH"],
        chart_rows,
        columns=["observed_utc", "candidate_id", "supplier_sku", "asin"],
    )

    for attr, path in paths.items():
        monkeypatch.setattr(hf001, attr, path)
    monkeypatch.setattr(
        hf001,
        "SCANNER_OWNED_INPUTS",
        [paths["F_LEGACY_EVIDENCE_PATH"], paths["F_LEGACY_CHART_PATH"]],
    )
    monkeypatch.setattr(
        hf001,
        "REQUIRED_INPUTS",
        list(paths.values()),
    )
    monkeypatch.setattr(hf001, "_utc_now_iso", lambda: "2026-04-17T18:00:00Z")

    market_output = tmp_path / "out" / "analysis_reports" / "market.csv"
    action_output = tmp_path / "out" / "analysis_reports" / "actions.csv"
    gap_output = tmp_path / "out" / "analysis_reports" / "gaps.csv"
    result = hf001.build_baseline(
        repo_root=tmp_path,
        market_facts_output_path=market_output,
        action_outcomes_output_path=action_output,
        scrape_gap_output_path=gap_output,
    )

    assert result.market_facts_rows >= 3
    assert result.action_outcomes_rows == 3
    assert result.scrape_gap_rows == 4
    assert result.scanner_source_hash_verified is True

    action_df = pd.read_csv(action_output, dtype=str).fillna("")
    regain = action_df[action_df["chosen_tactic"] == "REGAIN"].iloc[0]
    assert regain["eligible_to_write_flag"] == "1"
    assert regain["decision_to_change_price_flag"] == "1"
    assert regain["write_attempted_flag"] == "1"
    assert regain["write_applied_flag"] == "1"

    hold = action_df[action_df["chosen_tactic"] == "HOLD_OBSERVE"].iloc[0]
    assert hold["eligible_to_write_flag"] == "1"
    assert hold["decision_to_change_price_flag"] == "0"
    assert hold["write_attempted_flag"] == "0"
    assert hold["write_applied_flag"] == "0"

    readonly = action_df[action_df["chosen_tactic"] == "SELLER_DETAIL_HOLD"].iloc[0]
    assert readonly["eligible_to_write_flag"] == "0"
    assert readonly["write_applied_flag"] == "0"

    gap_df = pd.read_csv(gap_output, dtype=str).fillna("").set_index("candidate_id")
    assert gap_df.loc["C_OK", "scrape_coverage_status"] == "ok"
    assert gap_df.loc["C_OK", "rescrape_needed_flag"] == "0"
    assert gap_df.loc["C_MISSING", "scrape_coverage_status"] == "non_scraper_scope"
    assert gap_df.loc["C_MISSING", "rescrape_needed_flag"] == "0"
    assert "NON_SCRAPER_SCOPE_NO_ASIN" in gap_df.loc["C_MISSING", "rescrape_reason_codes"]
    assert gap_df.loc["C_STALE", "scrape_coverage_status"] == "stale"
    assert gap_df.loc["C_THIN", "scrape_coverage_status"] == "thin"
    assert "BRIDGE_UNRESOLVED" in gap_df.loc["C_THIN", "rescrape_reason_codes"]


def test_scrape_gap_full_capture_coverage_overrides_missing_scrape() -> None:
    identity_df = pd.DataFrame(
        [
            {
                "candidate_id": "C1",
                "supplier_id": "SUP-1",
                "supplier_sku": "SS1",
                "sku": "SKU1",
                "asin": "A1",
                "sku_resolution_status": "UNRESOLVED_ASIN_NOT_IN_H_SCOPE",
            }
        ]
    )
    assumption_df = pd.DataFrame(
        [
            {
                "candidate_id": "C1",
                "snapshot_stage": "approval_decision",
                "in_scope_approval_decision_flag": "1",
                "assumption_anchor_utc": "2026-04-17T08:00:00Z",
            }
        ]
    )
    legacy_evidence_df = pd.DataFrame(columns=["candidate_id", "supplier_sku", "asin", "observed_utc", "scrape_success"])
    legacy_chart_df = pd.DataFrame(columns=["candidate_id", "supplier_sku", "asin", "observed_utc"])
    full_capture_facts_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-17T17:55:00Z",
                "asin": "A1",
                "capture_status": "success",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
            }
        ]
    )

    gap_df = hf001._build_scrape_gap_report(
        identity_df=identity_df,
        assumption_df=assumption_df,
        legacy_evidence_df=legacy_evidence_df,
        legacy_chart_df=legacy_chart_df,
        full_capture_facts_df=full_capture_facts_df,
        snapshot_utc="2026-04-17T18:00:00Z",
    ).set_index("candidate_id")

    assert gap_df.loc["C1", "scrape_coverage_status"] == "ok"
    assert gap_df.loc["C1", "rescrape_needed_flag"] == "0"
    assert "FULL_CAPTURE_COVERED" in gap_df.loc["C1", "rescrape_reason_codes"]
    assert "F008_capture_full_bbp_evidence_pack.py" in gap_df.loc["C1", "queue_owner_path"]


def test_build_baseline_allows_external_scanner_source_drift(tmp_path: Path, monkeypatch) -> None:
    scanner_a = tmp_path / "scanner_a.csv"
    scanner_b = tmp_path / "scanner_b.csv"
    scanner_a.write_text("candidate_id,asin\n", encoding="utf-8")
    scanner_b.write_text("candidate_id,asin\n", encoding="utf-8")

    monkeypatch.setattr(hf001, "SCANNER_OWNED_INPUTS", [scanner_a, scanner_b])
    monkeypatch.setattr(hf001, "_ensure_required_inputs", lambda: None)
    monkeypatch.setattr(hf001, "_read_csv_required", lambda path: pd.DataFrame())
    monkeypatch.setattr(hf001, "_read_csv_optional", lambda path: pd.DataFrame())
    monkeypatch.setattr(hf001, "_utc_now_iso", lambda: "2026-04-17T18:00:00Z")

    counter = {"n": 0}

    def _sha_with_drift(path: Path) -> str:
        _ = path
        counter["n"] += 1
        return f"HASH-{counter['n']}"

    monkeypatch.setattr(hf001, "_sha256_file", _sha_with_drift)

    market_output = tmp_path / "out" / "analysis_reports" / "market.csv"
    action_output = tmp_path / "out" / "analysis_reports" / "actions.csv"
    gap_output = tmp_path / "out" / "analysis_reports" / "gaps.csv"

    result = hf001.build_baseline(
        repo_root=tmp_path,
        market_facts_output_path=market_output,
        action_outcomes_output_path=action_output,
        scrape_gap_output_path=gap_output,
    )

    assert result.scanner_source_hash_verified is False
    assert market_output.exists()
    assert action_output.exists()
    assert gap_output.exists()
