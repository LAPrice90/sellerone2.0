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

from scripts.flows.F.F070_build_backtest_policy_snapshot import build_backtest_policy_snapshot
from scripts.flows.F.F073_build_backtest_summary import build_backtest_summary
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(columns=columns or [])
    df.to_csv(path, index=False)


def _source_row(source_name: str, overrides: dict[str, str]) -> dict[str, str]:
    cols = get_source_contract(source_name).required_columns
    row = {col: "" for col in cols}
    row.update(overrides)
    return row


def _write_source(tmp_path: Path, source_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_source_contract(source_name)
    _write_csv(tmp_path / contract.source_path, rows, columns=list(contract.required_columns))


def test_f073_builds_ready_summary_from_replay_rows(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-1",
                    "asin": "B000SUM001",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "demand_basis_units_monthly": "45",
                    "seasonality_state": "possible_seasonal",
                    "seasonality_reason_codes": "seasonal_shape_present_without_full_year",
                    "stability_state": "stable",
                    "stability_reason_codes": "within_stability_band",
                    "recent_vs_baseline_state": "stable",
                    "recent_vs_baseline_reason_codes": "baseline_threshold_stable",
                    "completed_months_count": "7",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "12",
                    "price_qualified_profit_monthly_gbp": "24",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_final_factor": "0.266667",
                    "qualification_zero_or_block_reason": "",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.5",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-1",
                    "asin": "B000SUM001",
                    "day": "2026-03-01",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_amazon_and_fba",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "50",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "3",
                    "failure_event_flag": "0",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-1",
                    "asin": "B000SUM001",
                    "day": "2026-03-02",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_fba",
                    "replay_mode": "hold_wait",
                    "price_zone": "stretched",
                    "sales_share_pct": "50",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "2",
                    "failure_event_flag": "0",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-1",
                    "asin": "B000SUM001",
                    "day": "2026-03-03",
                    "replay_status": "ok",
                    "competition_scenario": "solo_or_no_meaningful_competition",
                    "replay_mode": "sell_off",
                    "price_zone": "stretched",
                    "sales_share_pct": "100",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "-1",
                    "failure_event_flag": "1",
                },
            ),
        ],
    )

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["observed_utc"] == "2026-04-10T13:00:00Z"
    assert row["summary_status"] == "ready"
    assert row["estimated_total_profit_gbp"] == "4"
    assert row["capital_lockup_days"] == "2"
    assert row["failure_event_count"] == "1"
    assert row["longest_failure_streak_days"] == "1"
    assert row["time_normal_sell_days"] == "1"
    assert row["time_hold_wait_days"] == "1"
    assert row["time_selloff_days"] == "1"
    assert row["sellable_ceiling_zone"] == "stretched"
    assert row["recommendation"] == "Managed fit"
    assert row["share_assumption_basis"] == "v1_measured_share_with_prior_and_scenario_caps"
    assert row["expected_units_source"] == "input_qualified"
    assert row["expected_profit_source"] == "input_qualified"
    assert row["seasonality_state"] == "possible_seasonal"
    assert row["stability_state"] == "stable"
    assert row["recent_vs_baseline_state"] == "stable"
    assert row["completed_months_count"] == "7"
    assert row["decision_confidence"] == "medium"
    assert "confidence_medium_gate_met" in row["decision_confidence_reason_codes"]
    assert "seasonality_state_possible_seasonal" in row["summary_reason_codes"]
    assert "stability_state_stable" in row["summary_reason_codes"]
    assert "recent_vs_baseline_state_stable" in row["summary_reason_codes"]

    out_path = tmp_path / get_f_output_contract("feeder_backtest_summary_live").rel_path
    assert out_path.exists()


def test_f073_sets_manual_review_when_input_not_ready(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-2",
                    "asin": "B000SUM002",
                    "mapping_status": "no_product_db_match",
                    "input_status": "manual_review",
                    "input_reason_codes": "no_product_db_match|missing_velocity_30d",
                    "history_days": "45",
                    "paired_buy_box_bsr_days": "10",
                    "buy_box_coverage_share": "0.20",
                    "base_velocity_30d_units_per_day": "",
                    "current_supplier_buy_cost_gbp": "",
                    "break_even_price_gbp": "",
                    "market_price_gbp": "12.5",
                    "history_confidence": "low",
                    "manual_review_flag": "1",
                },
            )
        ],
    )
    _write_source(tmp_path, "feeder_backtest_replay_daily_live", [])

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["summary_status"] == "manual_review"
    assert row["recommendation"] == "Manual review"
    assert row["manual_review_reason"] == "no_product_db_match|missing_velocity_30d"
    assert "input_not_ready" in row["summary_reason_codes"]


def test_f073_sets_manual_review_when_ready_row_has_no_replay(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-3",
                    "asin": "B000SUM003",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.5",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )
    _write_source(tmp_path, "feeder_backtest_replay_daily_live", [])

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["summary_status"] == "manual_review"
    assert row["recommendation"] == "Manual review"
    assert row["manual_review_reason"] == "missing_replay_rows"
    assert "missing_replay_rows" in row["summary_reason_codes"]


def test_f073_caps_critical_amazon_ready_recommendation_to_exit_only(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-CRIT",
                    "asin": "B000CRIT01",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "180",
                    "paired_buy_box_bsr_days": "120",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "demand_basis_units_monthly": "80",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "20",
                    "price_qualified_profit_monthly_gbp": "60",
                    "price_qualification_reason_codes": "amazon_heavy_30d",
                    "qualification_final_factor": "0.25",
                    "qualification_zero_or_block_reason": "",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "14",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-CRIT",
                    "asin": "B000CRIT01",
                    "day": "2026-03-01",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_amazon",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "50",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "5",
                    "failure_event_flag": "0",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-CRIT",
                    "asin": "B000CRIT01",
                    "day": "2026-03-02",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_amazon",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "50",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "5",
                    "failure_event_flag": "0",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-CRIT",
                    "asin": "B000CRIT01",
                    "day": "2026-03-03",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_amazon",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "50",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "5",
                    "failure_event_flag": "0",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-CRIT",
                    "asin": "B000CRIT01",
                    "day": "2026-03-04",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_amazon_and_fba",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "50",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "5",
                    "failure_event_flag": "0",
                },
            ),
        ],
    )

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["summary_status"] == "ready"
    assert row["amazon_risk_level"] == "critical"
    assert row["recommendation"] == "Exit-only"
    assert row["recommendation"] not in {"Normal fit", "Managed fit"}


def test_f073_carries_attribution_reason_tags_for_ready_rows(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-ATTR",
                    "asin": "B000ATTRSUM",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "attribution_amazon_dominant_90d|history_confidence_downgraded_by_attribution",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "demand_basis_units_monthly": "60",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "15",
                    "price_qualified_profit_monthly_gbp": "25",
                    "price_qualification_reason_codes": "history_maturity_limited",
                    "qualification_final_factor": "0.25",
                    "qualification_zero_or_block_reason": "",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.5",
                    "history_confidence": "medium",
                    "manual_review_flag": "0",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-ATTR",
                    "asin": "B000ATTRSUM",
                    "day": "2026-03-01",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_fba",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "100",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "3",
                    "failure_event_flag": "0",
                },
            ),
        ],
    )

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["summary_status"] == "ready"
    assert "summary_ready" in row["summary_reason_codes"]
    assert "attribution_amazon_dominant_90d" in row["summary_reason_codes"]
    assert "history_confidence_downgraded_by_attribution" in row["summary_reason_codes"]


def test_f073_carries_share_governance_tags_from_replay(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-SHARE",
                    "asin": "B000SUMSHARE",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "demand_basis_units_monthly": "60",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "18",
                    "price_qualified_profit_monthly_gbp": "28",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_final_factor": "0.3",
                    "qualification_zero_or_block_reason": "",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.5",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-SHARE",
                    "asin": "B000SUMSHARE",
                    "day": "2026-03-01",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_fba",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "90",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "3",
                    "failure_event_flag": "0",
                    "reason_codes": "share_source_sparse_asin_blend|share_sparse_asin_history|share_governance_cap_applied",
                },
            ),
        ],
    )

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["summary_status"] == "ready"
    assert "share_source_sparse_asin_blend" in row["summary_reason_codes"]
    assert "share_sparse_asin_history" in row["summary_reason_codes"]
    assert "share_governance_cap_applied" in row["summary_reason_codes"]


def test_f073_flags_replay_fallback_when_ready_row_has_no_qualified_input(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-FALLBACK",
                    "asin": "B000SUMFBK",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "demand_basis_units_monthly": "60",
                    "history_maturity_state": "stable",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.5",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-FALLBACK",
                    "asin": "B000SUMFBK",
                    "day": "2026-03-01",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_fba",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "90",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "3",
                    "failure_event_flag": "0",
                },
            ),
        ],
    )

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["summary_status"] == "manual_review"
    assert row["manual_review_reason"] == "missing_qualified_input_for_ready_row"
    assert row["expected_units_source"] == "replay_fallback"
    assert row["expected_profit_source"] == "replay_fallback"
    assert "missing_qualified_input_for_ready_row" in row["summary_reason_codes"]
    assert "expected_units_source_replay_fallback" in row["summary_reason_codes"]
    assert "expected_profit_source_replay_fallback" in row["summary_reason_codes"]
    assert row["seasonality_state"] == "insufficient_history"
    assert row["stability_state"] == "too_new"
    assert row["recent_vs_baseline_state"] == "insufficient_history"
    assert row["decision_confidence"] == "low"
    assert "confidence_summary_not_ready" in row["decision_confidence_reason_codes"]
    assert "seasonality_state_defaulted" in row["summary_reason_codes"]
    assert "stability_state_defaulted" in row["summary_reason_codes"]
    assert "recent_state_defaulted" in row["summary_reason_codes"]


def test_f073_sets_decision_state_from_profit_floor_and_quality_fields(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(
        root=tmp_path,
        observed_utc="2026-04-10T10:00:00Z",
        minimum_expected_profit_gbp=20.0,
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-FLOOR-FAIL",
                    "asin": "B000SUMF01",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "220",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "demand_basis_units_monthly": "40",
                    "seasonality_state": "possible_seasonal",
                    "seasonality_reason_codes": "seasonal_shape_present_without_full_year",
                    "stability_state": "stable",
                    "stability_reason_codes": "within_stability_band",
                    "recent_vs_baseline_state": "stable",
                    "recent_vs_baseline_reason_codes": "baseline_threshold_stable",
                    "completed_months_count": "7",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "10",
                    "price_qualified_profit_monthly_gbp": "15",
                    "price_qualification_reason_codes": "qualification_factor_reduced_to_zero",
                    "qualification_final_factor": "0.25",
                    "qualification_zero_or_block_reason": "",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.5",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            ),
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-FLOOR-PASS",
                    "asin": "B000SUMF02",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "220",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "demand_basis_units_monthly": "40",
                    "seasonality_state": "possible_seasonal",
                    "seasonality_reason_codes": "seasonal_shape_present_without_full_year",
                    "stability_state": "stable",
                    "stability_reason_codes": "within_stability_band",
                    "recent_vs_baseline_state": "stable",
                    "recent_vs_baseline_reason_codes": "baseline_threshold_stable",
                    "completed_months_count": "7",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "12",
                    "price_qualified_profit_monthly_gbp": "25",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_final_factor": "0.3",
                    "qualification_zero_or_block_reason": "",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.5",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-FLOOR-FAIL",
                    "asin": "B000SUMF01",
                    "day": "2026-03-01",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_fba",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "90",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "1",
                    "failure_event_flag": "0",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-FLOOR-PASS",
                    "asin": "B000SUMF02",
                    "day": "2026-03-01",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_fba",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "90",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "1",
                    "failure_event_flag": "0",
                },
            ),
        ],
    )

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 2
    fail_row = out_df[out_df["seller_sku"] == "SKU-SUM-FLOOR-FAIL"].iloc[0]
    pass_row = out_df[out_df["seller_sku"] == "SKU-SUM-FLOOR-PASS"].iloc[0]

    assert fail_row["decision_state"] == "fail"
    assert fail_row["expected_profit_next_30d_gbp"] == "15"
    assert fail_row["expected_units_source"] == "input_qualified"
    assert fail_row["expected_profit_source"] == "input_qualified"
    assert fail_row["decision_confidence"] == "medium"
    assert "expected_profit_below_floor" in fail_row["decision_reason_codes"]

    assert pass_row["decision_state"] == "pass"
    assert pass_row["expected_profit_next_30d_gbp"] == "25"
    assert pass_row["expected_units_source"] == "input_qualified"
    assert pass_row["expected_profit_source"] == "input_qualified"
    assert pass_row["decision_confidence"] == "medium"
    assert "meets_profit_floor" in pass_row["decision_reason_codes"]


def test_f073_routes_low_confidence_ready_row_to_manual_review(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(
        root=tmp_path,
        observed_utc="2026-04-10T10:00:00Z",
        minimum_expected_profit_gbp=20.0,
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T10:05:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-LOWCONF",
                    "asin": "B000LOWCONF",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "40",
                    "paired_buy_box_bsr_days": "12",
                    "buy_box_coverage_share": "0.50",
                    "base_velocity_30d_units_per_day": "1",
                    "demand_basis_units_monthly": "12",
                    "seasonality_state": "insufficient_history",
                    "seasonality_reason_codes": "insufficient_history",
                    "stability_state": "too_new",
                    "stability_reason_codes": "insufficient_history",
                    "recent_vs_baseline_state": "insufficient_history",
                    "recent_vs_baseline_reason_codes": "insufficient_history",
                    "completed_months_count": "2",
                    "history_maturity_state": "recent_only",
                    "price_qualified_units_monthly": "9",
                    "price_qualified_profit_monthly_gbp": "27",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "14",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T12:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-SUM-LOWCONF",
                    "asin": "B000LOWCONF",
                    "day": "2026-03-01",
                    "replay_status": "ok",
                    "competition_scenario": "sharing_with_fba",
                    "replay_mode": "normal_sell",
                    "price_zone": "normal",
                    "sales_share_pct": "90",
                    "estimated_units_ours": "1",
                    "estimated_profit_gbp": "1",
                    "failure_event_flag": "0",
                },
            ),
        ],
    )

    out_df = build_backtest_summary(root=tmp_path, observed_utc="2026-04-10T13:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["summary_status"] == "ready"
    assert row["decision_confidence"] == "low"
    assert row["decision_state"] == "manual_review"
    assert "confidence_maturity_too_new" in row["decision_confidence_reason_codes"]
    assert "decision_confidence_low" in row["decision_reason_codes"]
