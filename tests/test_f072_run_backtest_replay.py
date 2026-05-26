from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F070_build_backtest_policy_snapshot import build_backtest_policy_snapshot
from scripts.flows.F.F072_run_backtest_replay import run_backtest_replay
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _source_row(source_name: str, overrides: dict[str, str]) -> dict[str, str]:
    cols = get_source_contract(source_name).required_columns
    row = {col: "" for col in cols}
    row.update(overrides)
    return row


def _write_source(tmp_path: Path, source_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_source_contract(source_name)
    _write_csv(tmp_path / contract.source_path, rows)


def test_f072_builds_daily_replay_rows_for_ready_input(tmp_path: Path) -> None:
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
                    "seller_sku": "SKU-REPLAY-1",
                    "asin": "B000REPLAY1",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "60",
                    "demand_basis_month_label": "2026-03",
                    "bbp_sales_last_completed_month_label": "2026-03",
                    "bbp_sales_last_completed_month_units": "60",
                    "bbp_sales_current_month_label": "2026-04",
                    "bbp_sales_current_month_units": "79",
                    "bbp_sales_future_month_count_ignored": "2",
                    "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                    "bbp_sales_replay_demand_basis_label": "2026-03",
                    "bbp_sales_replay_demand_basis_units": "60",
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

    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        [
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000REPLAY1",
                    "day": "2026-03-01",
                    "amazon_price_raw": "12.9",
                    "fba_price_raw": "12.5",
                    "fbm_price_raw": "12.8",
                    "buy_box_price_raw": "12.5",
                    "bsr_raw": "11000",
                    "price_chosen_processed": "12.5",
                    "phase_processed": "normal",
                },
            ),
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-02T08:00:00Z",
                    "asin": "B000REPLAY1",
                    "day": "2026-03-02",
                    "amazon_price_raw": "9.4",
                    "fba_price_raw": "9.5",
                    "fbm_price_raw": "9.7",
                    "buy_box_price_raw": "9.5",
                    "bsr_raw": "19000",
                    "price_chosen_processed": "9.5",
                    "phase_processed": "normal",
                },
            ),
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-03T08:00:00Z",
                    "asin": "B000REPLAY1",
                    "day": "2026-03-03",
                    "amazon_price_raw": "",
                    "fba_price_raw": "",
                    "fbm_price_raw": "11.9",
                    "buy_box_price_raw": "12.0",
                    "bsr_raw": "13000",
                    "price_chosen_processed": "12.0",
                    "phase_processed": "normal",
                },
            ),
        ],
    )

    out_df = run_backtest_replay(root=tmp_path, observed_utc="2026-04-10T12:00:00Z")
    assert len(out_df) == 3
    assert set(out_df["policy_id"].tolist()) == {"f_backtest_policy_v1"}
    assert set(out_df["seller_sku"].tolist()) == {"SKU-REPLAY-1"}
    assert set(out_df["asin"].tolist()) == {"B000REPLAY1"}

    day1 = out_df[out_df["day"] == "2026-03-01"].iloc[0]
    assert day1["competition_scenario"] == "sharing_with_amazon_and_fba"
    assert day1["replay_mode"] == "normal_sell"
    assert day1["sales_share_pct"] == "70"
    assert day1["failure_event_flag"] == "0"
    assert day1["demand_basis_source"] == "bbp_last_completed_month"
    assert day1["demand_basis_units_monthly"] == "60"
    assert "demand_basis_bbp_last_completed_month" in day1["reason_codes"]
    assert "bbp_future_months_ignored" in day1["reason_codes"]
    assert "share_governance_cap_applied" in day1["reason_codes"]

    day2 = out_df[out_df["day"] == "2026-03-02"].iloc[0]
    assert day2["replay_mode"] == "sell_off"
    assert day2["failure_event_flag"] == "1"

    day3 = out_df[out_df["day"] == "2026-03-03"].iloc[0]
    assert day3["competition_scenario"] == "solo_or_no_meaningful_competition"
    assert day3["sales_share_pct"] == "100"

    out_path = tmp_path / get_f_output_contract("feeder_backtest_replay_daily_live").rel_path
    assert out_path.exists()


def test_f072_skips_non_ready_input_rows(tmp_path: Path) -> None:
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
                    "seller_sku": "SKU-REPLAY-2",
                    "asin": "B000REPLAY2",
                    "mapping_status": "no_product_db_match",
                    "input_status": "manual_review",
                    "input_reason_codes": "no_product_db_match",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.5",
                    "history_confidence": "high",
                    "manual_review_flag": "1",
                },
            )
        ],
    )

    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        [
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000REPLAY2",
                    "day": "2026-03-01",
                    "amazon_price_raw": "12.9",
                    "fba_price_raw": "12.5",
                    "fbm_price_raw": "12.8",
                    "buy_box_price_raw": "12.5",
                    "bsr_raw": "11000",
                    "price_chosen_processed": "12.5",
                    "phase_processed": "normal",
                },
            )
        ],
    )

    out_df = run_backtest_replay(root=tmp_path, observed_utc="2026-04-10T12:00:00Z")
    assert out_df.empty


def test_f072_requires_exactly_one_active_policy(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(
        root=tmp_path,
        observed_utc="2026-04-10T10:00:00Z",
        policy_status="paused",
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
                    "seller_sku": "SKU-REPLAY-3",
                    "asin": "B000REPLAY3",
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
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        [
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000REPLAY3",
                    "day": "2026-03-01",
                    "amazon_price_raw": "12.9",
                    "fba_price_raw": "12.5",
                    "fbm_price_raw": "12.8",
                    "buy_box_price_raw": "12.5",
                    "bsr_raw": "11000",
                    "price_chosen_processed": "12.5",
                    "phase_processed": "normal",
                },
            )
        ],
    )

    with pytest.raises(ValueError, match="exactly 1 active policy row"):
        run_backtest_replay(root=tmp_path, observed_utc="2026-04-10T12:00:00Z")


def test_f072_measured_share_is_zero_when_amazon_owns_buy_box(tmp_path: Path) -> None:
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
                    "seller_sku": "SKU-REPLAY-AMZ",
                    "asin": "B000REPLAY4",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "10.0",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )

    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        [
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000REPLAY4",
                    "day": "2026-03-01",
                    "amazon_price_raw": "10.0",
                    "fba_price_raw": "",
                    "fbm_price_raw": "",
                    "buy_box_price_raw": "10.0",
                    "bsr_raw": "12000",
                    "price_chosen_processed": "10.0",
                    "phase_processed": "normal",
                },
            ),
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-02T08:00:00Z",
                    "asin": "B000REPLAY4",
                    "day": "2026-03-02",
                    "amazon_price_raw": "10.0",
                    "fba_price_raw": "",
                    "fbm_price_raw": "",
                    "buy_box_price_raw": "10.0",
                    "bsr_raw": "12000",
                    "price_chosen_processed": "10.0",
                    "phase_processed": "normal",
                },
            ),
        ],
    )

    out_df = run_backtest_replay(root=tmp_path, observed_utc="2026-04-10T12:00:00Z")
    assert len(out_df) == 2
    assert set(out_df["competition_scenario"].tolist()) == {"sharing_with_amazon"}
    assert set(out_df["sales_share_pct"].tolist()) == {"0"}
    assert set(out_df["estimated_units_ours"].tolist()) == {"0"}


def test_f072_applies_global_prior_when_scenario_sample_is_sparse(tmp_path: Path) -> None:
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
                    "seller_sku": "SKU-REPLAY-SPARSE",
                    "asin": "B000REPLAY5",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "10.0",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )

    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        [
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000REPLAY5",
                    "day": "2026-03-01",
                    "amazon_price_raw": "12.0",
                    "fba_price_raw": "",
                    "fbm_price_raw": "",
                    "buy_box_price_raw": "10.0",
                    "bsr_raw": "12000",
                    "price_chosen_processed": "10.0",
                    "phase_processed": "normal",
                },
            ),
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000REPLAY5B",
                    "day": "2026-03-01",
                    "amazon_price_raw": "10.0",
                    "fba_price_raw": "",
                    "fbm_price_raw": "",
                    "buy_box_price_raw": "10.0",
                    "bsr_raw": "12000",
                    "price_chosen_processed": "10.0",
                    "phase_processed": "normal",
                },
            ),
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-02T08:00:00Z",
                    "asin": "B000REPLAY5B",
                    "day": "2026-03-02",
                    "amazon_price_raw": "10.0",
                    "fba_price_raw": "",
                    "fbm_price_raw": "",
                    "buy_box_price_raw": "10.0",
                    "bsr_raw": "12000",
                    "price_chosen_processed": "10.0",
                    "phase_processed": "normal",
                },
            ),
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-03T08:00:00Z",
                    "asin": "B000REPLAY5B",
                    "day": "2026-03-03",
                    "amazon_price_raw": "10.0",
                    "fba_price_raw": "",
                    "fbm_price_raw": "",
                    "buy_box_price_raw": "10.0",
                    "bsr_raw": "12000",
                    "price_chosen_processed": "10.0",
                    "phase_processed": "normal",
                },
            ),
        ],
    )

    out_df = run_backtest_replay(root=tmp_path, observed_utc="2026-04-10T12:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["competition_scenario"] == "sharing_with_amazon"
    measured_share = float(row["sales_share_pct"])
    assert measured_share > 20.0
    assert measured_share < 40.0
    assert "share_source_sparse_asin_blend" in row["reason_codes"]
    assert "share_sparse_asin_history" in row["reason_codes"]


def test_f072_caps_shared_fba_scenario_share_and_tags_reason(tmp_path: Path) -> None:
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
                    "seller_sku": "SKU-REPLAY-FBA-CAP",
                    "asin": "B000REPLAY6",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "base_velocity_30d_units_per_day": "2",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12.0",
                    "history_confidence": "high",
                    "manual_review_flag": "0",
                },
            )
        ],
    )

    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        [
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000REPLAY6",
                    "day": "2026-03-01",
                    "amazon_price_raw": "",
                    "fba_price_raw": "12.0",
                    "fbm_price_raw": "12.2",
                    "buy_box_price_raw": "12.0",
                    "bsr_raw": "12000",
                    "price_chosen_processed": "12.0",
                    "phase_processed": "normal",
                },
            ),
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-02T08:00:00Z",
                    "asin": "B000REPLAY6",
                    "day": "2026-03-02",
                    "amazon_price_raw": "",
                    "fba_price_raw": "12.0",
                    "fbm_price_raw": "12.1",
                    "buy_box_price_raw": "12.0",
                    "bsr_raw": "12100",
                    "price_chosen_processed": "12.0",
                    "phase_processed": "normal",
                },
            ),
        ],
    )

    out_df = run_backtest_replay(root=tmp_path, observed_utc="2026-04-10T12:00:00Z")
    assert len(out_df) == 2
    assert set(out_df["competition_scenario"].tolist()) == {"sharing_with_fba"}
    assert set(out_df["sales_share_pct"].tolist()) == {"90"}
    assert all("share_governance_cap_applied" in str(v) for v in out_df["reason_codes"].tolist())


def test_f072_uses_price_qualified_units_when_present(tmp_path: Path) -> None:
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
                    "seller_sku": "SKU-QUAL-1",
                    "asin": "B000QUAL01",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "300",
                    "base_velocity_30d_units_per_day": "10",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12",
                    "seasonality_state": "limited_history",
                    "seasonality_reason_codes": "insufficient_history",
                    "stability_state": "stable",
                    "stability_reason_codes": "within_stability_band",
                    "recent_vs_baseline_state": "stable",
                    "recent_vs_baseline_reason_codes": "baseline_threshold_stable",
                    "completed_months_count": "4",
                    "history_confidence": "high",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "30",
                    "price_qualified_profit_monthly_gbp": "60",
                    "price_qualification_reason_codes": "amazon_heavy_30d|buy_box_coverage_medium",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "0.2",
                    "qualification_buy_box_coverage_factor": "0.8",
                    "qualification_maturity_factor": "1",
                    "qualification_final_factor": "0.16",
                    "qualification_zero_or_block_reason": "",
                    "manual_review_flag": "0",
                },
            )
        ],
    )

    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        [
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000QUAL01",
                    "day": "2026-03-01",
                    "amazon_price_raw": "",
                    "fba_price_raw": "12.0",
                    "fbm_price_raw": "12.2",
                    "buy_box_price_raw": "12.0",
                    "bsr_raw": "11000",
                    "price_chosen_processed": "12.0",
                    "phase_processed": "normal",
                },
            )
        ],
    )

    out_df = run_backtest_replay(root=tmp_path, observed_utc="2026-04-10T12:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["history_maturity_state"] == "stable"
    assert row["raw_demand_units_monthly"] == "300"
    assert row["price_qualified_units_monthly"] == "30"
    assert row["price_qualified_profit_monthly_gbp"] == "60"
    assert row["price_qualification_reason_codes"] == "amazon_heavy_30d|buy_box_coverage_medium"
    assert row["qualification_market_gate_state"] == "market_open"
    assert row["qualification_market_gate_factor"] == "1"
    assert row["qualification_amazon_pressure_factor"] == "0.2"
    assert row["qualification_buy_box_coverage_factor"] == "0.8"
    assert row["qualification_maturity_factor"] == "1"
    assert row["qualification_final_factor"] == "0.16"
    assert row["qualification_value_source"] == "input_qualified"
    assert row["seasonality_state"] == "limited_history"
    assert row["stability_state"] == "stable"
    assert row["recent_vs_baseline_state"] == "stable"
    assert row["completed_months_count"] == "4"
    assert "seasonality_state_limited_history" in row["reason_codes"]
    assert "stability_state_stable" in row["reason_codes"]
    assert "recent_vs_baseline_state_stable" in row["reason_codes"]
    # 30 units/month => 1/day effective velocity, with limited_history seasonality multiplier 0.9.
    assert row["estimated_listing_units"] == "0.9"


def test_f072_marks_replay_fallback_when_qualified_values_are_missing(tmp_path: Path) -> None:
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
                    "seller_sku": "SKU-QUAL-MISS",
                    "asin": "B000QUALMS",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_days": "120",
                    "paired_buy_box_bsr_days": "95",
                    "buy_box_coverage_share": "0.82",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "150",
                    "base_velocity_30d_units_per_day": "5",
                    "current_supplier_buy_cost_gbp": "8",
                    "break_even_price_gbp": "10",
                    "market_price_gbp": "12",
                    "seasonality_state": "limited_history",
                    "history_confidence": "high",
                    "history_maturity_state": "stable",
                    "manual_review_flag": "0",
                },
            )
        ],
    )

    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        [
            _source_row(
                "feeder_legacy_chart_daily_raw_live",
                {
                    "observed_utc": "2026-03-01T08:00:00Z",
                    "asin": "B000QUALMS",
                    "day": "2026-03-01",
                    "amazon_price_raw": "",
                    "fba_price_raw": "12.0",
                    "fbm_price_raw": "12.2",
                    "buy_box_price_raw": "12.0",
                    "bsr_raw": "11000",
                    "price_chosen_processed": "12.0",
                    "phase_processed": "normal",
                },
            )
        ],
    )

    out_df = run_backtest_replay(root=tmp_path, observed_utc="2026-04-10T12:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["qualification_value_source"] == "replay_fallback"
    assert "qualification_value_source_replay_fallback" in row["reason_codes"]
