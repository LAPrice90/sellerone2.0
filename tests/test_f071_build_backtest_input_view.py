from __future__ import annotations

import sys
from datetime import date, timedelta
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
from scripts.flows.F.F071_build_backtest_input_view import build_backtest_input_view
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_source(tmp_path: Path, source_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_source_contract(source_name)
    _write_csv(tmp_path / contract.source_path, rows)


def _write_asin_resolver(tmp_path: Path, rows: list[dict[str, str]]) -> None:
    _write_csv(tmp_path / "config" / "f_backtest_asin_resolution.csv", rows)


def _chart_rows(asin: str, *, days: int, start_day: date) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for i in range(days):
        day = start_day + timedelta(days=i)
        rows.append(
            {
                "observed_utc": f"{day.isoformat()}T08:00:00Z",
                "asin": asin,
                "day": day.isoformat(),
                "amazon_price_raw": "13.10",
                "fba_price_raw": "12.50",
                "fbm_price_raw": "12.80",
                "buy_box_price_raw": "12.50",
                "bsr_raw": str(15000 + i),
                "price_chosen_processed": "12.50",
                "phase_processed": "normal",
            }
        )
    return rows


def _chart_rows_with_sparse_buy_box(
    asin: str,
    *,
    days: int,
    start_day: date,
    buy_box_days: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for i in range(days):
        day = start_day + timedelta(days=i)
        buy_box_price = "12.50" if i < buy_box_days else ""
        rows.append(
            {
                "observed_utc": f"{day.isoformat()}T08:00:00Z",
                "asin": asin,
                "day": day.isoformat(),
                "amazon_price_raw": "13.10",
                "fba_price_raw": "12.50",
                "fbm_price_raw": "12.80",
                "buy_box_price_raw": buy_box_price,
                "bsr_raw": str(15000 + i),
                "price_chosen_processed": "12.50",
                "phase_processed": "normal",
            }
        )
    return rows


def test_f071_builds_ready_row_for_unique_asin_match(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000TEST01", days=120, start_day=date(2025, 12, 1)),
    )
    _write_source(
        tmp_path,
        "product_db_preview",
        [
            {
                "seller_sku": "SKU-UNIQUE-1",
                "asin": "B000TEST01",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_catalog_price": "8.50",
                "last_purchase_price": "8.20",
                "sale_status": "active",
                "title": "Example Product",
            }
        ],
    )
    _write_source(
        tmp_path,
        "sku_sales_velocity",
        [
            {"sku": "SKU-UNIQUE-1", "window_days": "90", "units_sold": "90", "velocity_units_per_day": "1.0"},
            {"sku": "SKU-UNIQUE-1", "window_days": "30", "units_sold": "45", "velocity_units_per_day": "1.5"},
        ],
    )
    _write_source(
        tmp_path,
        "sku_performance_summary",
        [
            {
                "sku": "SKU-UNIQUE-1",
                "expected_refund_cost_per_unit_gbp": "0.35",
                "break_even_price_gbp": "10.10",
                "roi_at_market_price_pct": "22.5",
            }
        ],
    )
    _write_source(
        tmp_path,
        "listing_offer_snapshot_latest",
        [
            {
                "timestamp_utc": "2026-04-10T08:00:00Z",
                "asof_date": "2026-04-10",
                "sku": "SKU-UNIQUE-1",
                "asin": "B000TEST01",
                "our_price": "12.40",
                "buy_box_price": "12.49",
                "buy_box_present_flag": "1",
                "lowest_fba_price": "12.49",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:30:00Z",
                "asin": "B000TEST01",
                "supplier_id": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_sku": "SKU-UNIQUE-1",
                "break_even": "10.10",
                "monthly_sold": "45",
                "bbp_monthly_units_chosen": "45",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "45",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "2026-03",
                "bbp_sales_replay_demand_basis_units": "45",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["observed_utc"] == "2026-04-10T11:00:00Z"
    assert row["policy_id"] == "f_backtest_policy_v1"
    assert row["seller_sku"] == "SKU-UNIQUE-1"
    assert row["mapping_status"] == "unique_asin_match"
    assert row["input_status"] == "ready"
    assert row["manual_review_flag"] == "0"
    assert row["history_confidence"] == "medium"
    assert row["base_velocity_30d_units_per_day"] == "1.5"
    assert row["break_even_price_gbp"] == "10.1"
    assert row["market_price_gbp"] == "12.49"
    assert row["qualification_market_gate_state"] == "market_open"
    assert row["qualification_market_gate_factor"] == "1"
    assert row["qualification_final_factor"] != ""
    assert row["price_qualification_reason_codes"] != ""


def test_f071_marks_multi_sku_asin_match_for_manual_review(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000TEST02", days=120, start_day=date(2025, 12, 1)),
    )
    _write_source(
        tmp_path,
        "product_db_preview",
        [
            {
                "seller_sku": "SKU-MULTI-A",
                "asin": "B000TEST02",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_catalog_price": "8.50",
                "last_purchase_price": "8.20",
                "sale_status": "active",
            },
            {
                "seller_sku": "SKU-MULTI-B",
                "asin": "B000TEST02",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "supplier_catalog_price": "8.70",
                "last_purchase_price": "8.30",
                "sale_status": "active",
            },
        ],
    )
    _write_source(
        tmp_path,
        "sku_sales_velocity",
        [
            {"sku": "SKU-MULTI-A", "window_days": "30", "units_sold": "40", "velocity_units_per_day": "1.33"},
            {"sku": "SKU-MULTI-B", "window_days": "30", "units_sold": "38", "velocity_units_per_day": "1.26"},
        ],
    )
    _write_source(
        tmp_path,
        "sku_performance_summary",
        [
            {"sku": "SKU-MULTI-A", "expected_refund_cost_per_unit_gbp": "0.30", "break_even_price_gbp": "10.00"},
            {"sku": "SKU-MULTI-B", "expected_refund_cost_per_unit_gbp": "0.32", "break_even_price_gbp": "10.20"},
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 2
    assert set(out_df["mapping_status"].tolist()) == {"multi_sku_asin_match"}
    assert set(out_df["input_status"].tolist()) == {"manual_review"}
    assert set(out_df["manual_review_flag"].tolist()) == {"1"}
    assert all("multi_sku_asin_match" in str(v) for v in out_df["input_reason_codes"].tolist())


def test_f071_applies_asin_resolver_and_marks_resolved_asin_match(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000TEST02", days=120, start_day=date(2025, 12, 1)),
    )
    _write_source(
        tmp_path,
        "product_db_preview",
        [
            {
                "seller_sku": "SKU-MULTI-A",
                "asin": "B000TEST02",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_catalog_price": "8.50",
                "last_purchase_price": "8.20",
                "sale_status": "active",
            },
            {
                "seller_sku": "SKU-MULTI-B",
                "asin": "B000TEST02",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "supplier_catalog_price": "8.70",
                "last_purchase_price": "8.30",
                "sale_status": "active",
            },
        ],
    )
    _write_source(
        tmp_path,
        "sku_sales_velocity",
        [
            {"sku": "SKU-MULTI-A", "window_days": "30", "units_sold": "40", "velocity_units_per_day": "1.33"},
            {"sku": "SKU-MULTI-B", "window_days": "30", "units_sold": "38", "velocity_units_per_day": "1.26"},
        ],
    )
    _write_source(
        tmp_path,
        "sku_performance_summary",
        [
            {"sku": "SKU-MULTI-A", "expected_refund_cost_per_unit_gbp": "0.30", "break_even_price_gbp": "10.00"},
            {"sku": "SKU-MULTI-B", "expected_refund_cost_per_unit_gbp": "0.32", "break_even_price_gbp": "10.20"},
        ],
    )
    _write_asin_resolver(
        tmp_path,
        [
            {
                "asin": "B000TEST02",
                "seller_sku": "SKU-MULTI-B",
                "resolution_status": "resolved",
                "resolution_reason": "unit_test_resolution",
                "resolution_source": "unit_test",
                "approved_utc": "2026-04-10T11:30:00Z",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:30:00Z",
                "asin": "B000TEST02",
                "supplier_id": "SUP-B",
                "supplier_name": "Beta",
                "supplier_sku": "SKU-MULTI-B",
                "break_even": "10.20",
                "monthly_sold": "38",
                "bbp_monthly_units_chosen": "38",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "38",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "2026-03",
                "bbp_sales_replay_demand_basis_units": "38",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["seller_sku"] == "SKU-MULTI-B"
    assert row["mapping_status"] == "resolved_asin_match"
    assert row["input_status"] == "ready"
    assert row["manual_review_flag"] == "0"
    assert "multi_sku_asin_match" not in row["input_reason_codes"]


def test_f071_keeps_no_product_match_rows_for_f_output(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000TEST03", days=45, start_day=date(2026, 1, 1)),
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["asin"] == "B000TEST03"
    assert row["seller_sku"] == ""
    assert row["mapping_status"] == "no_product_db_match"
    assert row["input_status"] == "manual_review"
    assert row["manual_review_flag"] == "1"
    assert "no_product_db_match" in row["input_reason_codes"]

    out_path = tmp_path / get_f_output_contract("feeder_backtest_input_view_live").rel_path
    assert out_path.exists()


def test_f071_uses_legacy_fallback_for_ready_row_when_product_db_missing(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000LEG001", days=120, start_day=date(2025, 12, 1)),
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:00:00Z",
                "asin": "B000LEG001",
                "supplier_id": "LEG-SUP-1",
                "supplier_name": "Legacy Supplier",
                "supplier_sku": "SKU-LEG-1",
                "break_even": "9.50",
                "monthly_sold": "60",
                "bbp_monthly_units_chosen": "60",
                "title": "Legacy fallback title",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "asin": "B000LEG001",
                "supplier": "Legacy Supplier",
                "supplier_sku": "SKU-LEG-1",
                "cost": "7.20",
                "break_even": "9.50",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["asin"] == "B000LEG001"
    assert row["seller_sku"] == "SKU-LEG-1"
    assert row["mapping_status"] == "legacy_asin_match"
    assert row["input_status"] == "manual_review"
    assert row["manual_review_flag"] == "1"
    assert "demand_basis_not_trusted_completed_month" in row["input_reason_codes"]
    assert row["supplier_code"] == "LEG-SUP-1"
    assert row["supplier_name"] == "Legacy Supplier"
    assert row["title"] == "Legacy fallback title"
    assert row["base_velocity_30d_units_per_day"] == "2"
    assert row["current_supplier_buy_cost_gbp"] == "7.2"
    assert row["break_even_price_gbp"] == "9.5"
    assert "no_product_db_match" not in row["input_reason_codes"]


def test_f071_uses_supplier_universal_cost_when_first_check_cost_missing(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000LEG002", days=120, start_day=date(2025, 12, 1)),
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:00:00Z",
                "asin": "B000LEG002",
                "supplier_id": "LEG-SUP-2",
                "supplier_name": "Legacy Supplier 2",
                "supplier_sku": "SKU-LEG-2",
                "break_even": "11.20",
                "monthly_sold": "30",
                "bbp_monthly_units_chosen": "30",
                "title": "Legacy fallback title 2",
            }
        ],
    )
    _write_source(
        tmp_path,
        "supplier_price_list_universal_live",
        [
            {
                "supplier_id": "LEG-SUP-2",
                "supplier_name": "Legacy Supplier 2",
                "supplier_sku": "SKU-LEG-2",
                "supplier_title": "Legacy fallback title 2",
                "barcode": "1234567890123",
                "unit_cost": "8.40",
                "currency": "GBP",
                "vat_rate": "20",
                "source_url": "https://example.invalid/item",
                "source_file_path": "source.csv",
                "source_seen_at_utc": "2026-04-10T08:00:00Z",
                "row_hash": "rowhash-1",
                "is_valid_source_row": "1",
                "normalized_utc": "2026-04-10T08:00:00Z",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["mapping_status"] == "legacy_asin_match"
    assert row["input_status"] == "manual_review"
    assert row["manual_review_flag"] == "1"
    assert "demand_basis_not_trusted_completed_month" in row["input_reason_codes"]
    assert row["current_supplier_buy_cost_gbp"] == "8.4"
    assert row["break_even_price_gbp"] == "11.2"


def test_f071_prefers_last_completed_bbp_month_for_demand_basis(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000DEMAND1", days=120, start_day=date(2025, 12, 1)),
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:00:00Z",
                "asin": "B000DEMAND1",
                "supplier_id": "LEG-SUP-3",
                "supplier_name": "Legacy Supplier 3",
                "supplier_sku": "SKU-LEG-3",
                "break_even": "11.20",
                "monthly_sold": "150",
                "bbp_monthly_units_chosen": "50",
                "bbp_monthly_sales_current": "10",
                "bbp_monthly_sales_recent_avg": "10",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "10",
                "bbp_sales_current_month_label": "2026-04",
                "bbp_sales_current_month_units": "79",
                "bbp_sales_future_month_count_ignored": "2",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "2026-03",
                "bbp_sales_replay_demand_basis_units": "10",
                "title": "Legacy demand basis product",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "asin": "B000DEMAND1",
                "supplier": "Legacy Supplier 3",
                "supplier_sku": "SKU-LEG-3",
                "cost": "8.40",
                "break_even": "11.20",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["mapping_status"] == "legacy_asin_match"
    assert row["input_status"] == "ready"
    assert row["demand_basis_source"] == "bbp_last_completed_month"
    assert row["demand_basis_units_monthly"] == "10"
    assert row["demand_basis_month_label"] == "2026-03"
    assert row["bbp_sales_last_completed_month_units"] == "10"
    assert row["bbp_sales_future_month_count_ignored"] == "2"
    assert abs(float(row["base_velocity_30d_units_per_day"]) - (10.0 / 30.0)) < 0.00001
    assert row["history_maturity_state"] == "developing"
    assert float(row["price_qualified_units_monthly"]) <= float(row["demand_basis_units_monthly"])
    assert float(row["price_qualified_profit_monthly_gbp"]) >= 0.0
    assert row["price_qualification_reason_codes"] != ""


def test_f071_preserves_zero_history_demand_basis(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000ZERO01", days=120, start_day=date(2025, 12, 1)),
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:00:00Z",
                "asin": "B000ZERO01",
                "supplier_id": "LEG-SUP-4",
                "supplier_name": "Legacy Supplier 4",
                "supplier_sku": "SKU-LEG-4",
                "break_even": "11.20",
                "monthly_sold": "150",
                "bbp_monthly_units_chosen": "1",
                "bbp_monthly_sales_current": "0",
                "bbp_monthly_sales_recent_avg": "1",
                "bbp_sales_last_completed_month_label": "",
                "bbp_sales_last_completed_month_units": "0",
                "bbp_sales_current_month_label": "",
                "bbp_sales_current_month_units": "0",
                "bbp_sales_future_month_count_ignored": "0",
                "bbp_sales_replay_demand_basis_source": "bbp_zero_history",
                "bbp_sales_replay_demand_basis_label": "zero_history",
                "bbp_sales_replay_demand_basis_units": "0",
                "title": "Legacy zero history product",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "asin": "B000ZERO01",
                "supplier": "Legacy Supplier 4",
                "supplier_sku": "SKU-LEG-4",
                "cost": "8.40",
                "break_even": "11.20",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["demand_basis_source"] == "bbp_zero_history"
    assert row["demand_basis_units_monthly"] == "0"
    assert row["demand_basis_month_label"] == "zero_history"
    assert row["base_velocity_30d_units_per_day"] == "0"
    assert row["price_qualified_units_monthly"] == "0"
    assert row["price_qualified_profit_monthly_gbp"] == "0"
    assert row["price_qualification_reason_codes"] == "raw_demand_zero"
    assert row["qualification_market_gate_state"] == "raw_demand_zero"
    assert row["qualification_final_factor"] == "0"
    assert row["qualification_zero_or_block_reason"] == "raw_demand_zero"


def test_f071_blocks_qualification_when_market_is_below_break_even(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000GATE01", days=120, start_day=date(2025, 12, 1)),
    )
    _write_source(
        tmp_path,
        "product_db_preview",
        [
            {
                "seller_sku": "SKU-GATE-1",
                "asin": "B000GATE01",
                "supplier_code": "SUP-GATE",
                "supplier_name": "Gate Supplier",
                "supplier_catalog_price": "8.50",
                "last_purchase_price": "8.20",
                "sale_status": "active",
            }
        ],
    )
    _write_source(
        tmp_path,
        "sku_sales_velocity",
        [
            {"sku": "SKU-GATE-1", "window_days": "30", "units_sold": "45", "velocity_units_per_day": "1.5"},
        ],
    )
    _write_source(
        tmp_path,
        "sku_performance_summary",
        [
            {
                "sku": "SKU-GATE-1",
                "expected_refund_cost_per_unit_gbp": "0.35",
                "break_even_price_gbp": "10.10",
            }
        ],
    )
    _write_source(
        tmp_path,
        "listing_offer_snapshot_latest",
        [
            {
                "timestamp_utc": "2026-04-10T08:00:00Z",
                "asof_date": "2026-04-10",
                "sku": "SKU-GATE-1",
                "asin": "B000GATE01",
                "our_price": "9.40",
                "buy_box_price": "9.50",
                "buy_box_present_flag": "1",
                "lowest_fba_price": "9.49",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:30:00Z",
                "asin": "B000GATE01",
                "supplier_id": "SUP-GATE",
                "supplier_name": "Gate Supplier",
                "supplier_sku": "SKU-GATE-1",
                "break_even": "10.10",
                "monthly_sold": "45",
                "bbp_monthly_units_chosen": "45",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "45",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "2026-03",
                "bbp_sales_replay_demand_basis_units": "45",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["input_status"] == "ready"
    assert row["price_qualified_units_monthly"] == "0"
    assert row["price_qualified_profit_monthly_gbp"] == "0"
    assert row["price_qualification_reason_codes"] == "market_below_break_even"
    assert row["qualification_market_gate_state"] == "market_below_break_even"
    assert row["qualification_market_gate_factor"] == "0"
    assert row["qualification_final_factor"] == "0"
    assert row["qualification_zero_or_block_reason"] == "market_below_break_even"


def test_f071_writes_explicit_qualification_component_factors(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows_with_sparse_buy_box("B000FACT01", days=45, start_day=date(2026, 1, 1), buy_box_days=20),
    )
    _write_source(
        tmp_path,
        "product_db_preview",
        [
            {
                "seller_sku": "SKU-FACT-1",
                "asin": "B000FACT01",
                "supplier_code": "SUP-FACT",
                "supplier_name": "Factor Supplier",
                "supplier_catalog_price": "8.50",
                "last_purchase_price": "8.20",
                "sale_status": "active",
            }
        ],
    )
    _write_source(
        tmp_path,
        "sku_sales_velocity",
        [
            {"sku": "SKU-FACT-1", "window_days": "30", "units_sold": "24", "velocity_units_per_day": "0.8"},
        ],
    )
    _write_source(
        tmp_path,
        "sku_performance_summary",
        [
            {
                "sku": "SKU-FACT-1",
                "expected_refund_cost_per_unit_gbp": "0.35",
                "break_even_price_gbp": "10.00",
            }
        ],
    )
    _write_source(
        tmp_path,
        "listing_offer_snapshot_latest",
        [
            {
                "timestamp_utc": "2026-04-10T08:00:00Z",
                "asof_date": "2026-04-10",
                "sku": "SKU-FACT-1",
                "asin": "B000FACT01",
                "our_price": "12.40",
                "buy_box_price": "12.49",
                "buy_box_present_flag": "1",
                "lowest_fba_price": "12.49",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:30:00Z",
                "asin": "B000FACT01",
                "supplier_id": "SUP-FACT",
                "supplier_name": "Factor Supplier",
                "supplier_sku": "SKU-FACT-1",
                "break_even": "10.00",
                "monthly_sold": "24",
                "bbp_monthly_units_chosen": "24",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "24",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "2026-03",
                "bbp_sales_replay_demand_basis_units": "24",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["input_status"] == "manual_review"
    assert row["manual_review_flag"] == "1"
    assert row["history_maturity_state"] == "recent_only"
    assert row["qualification_market_gate_state"] == "market_open"
    assert row["qualification_market_gate_factor"] == "1"
    assert row["qualification_amazon_pressure_factor"] == "0.05"
    assert row["qualification_buy_box_coverage_factor"] == "0.8"
    assert row["qualification_maturity_factor"] == "0.8"
    assert row["qualification_final_factor"] == "0.032"
    assert row["qualification_zero_or_block_reason"] == ""
    reason_codes = row["price_qualification_reason_codes"]
    assert "amazon_dominant_30d" in reason_codes
    assert "buy_box_coverage_medium" in reason_codes
    assert "history_maturity_limited" in reason_codes


def test_f071_requires_exactly_one_active_policy(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / get_source_contract("feeder_backtest_policy_live").source_path,
        [
            {
                "observed_utc": "2026-04-10T10:00:00Z",
                "policy_id": "f_backtest_policy_v1",
                "policy_version": "1.0",
                "policy_status": "paused",
                "minimum_expected_profit_gbp": "100",
                "entry_target_roi_pct": "20",
                "working_floor_roi_pct": "10",
                "exit_floor_roi_pct": "0",
                "emergency_floor_roi_pct": "-5",
                "recency_weight_30d": "0.5",
                "recency_weight_90d": "0.3",
                "recency_weight_180d": "0.15",
                "recency_weight_365d": "0.05",
                "ceiling_warn_ratio_30d": "1.25",
                "ceiling_red_ratio_30d": "1.5",
                "ceiling_extreme_ratio_30d": "2",
                "shock_trigger_pct_1d": "20",
                "shared_sales_default_pct": "50",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000TEST04", days=45, start_day=date(2026, 1, 1)),
    )

    with pytest.raises(ValueError, match="exactly 1 active policy row"):
        build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")


def test_f071_downgrades_confidence_with_attribution_reasons(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000ATTR01", days=220, start_day=date(2025, 8, 1)),
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:00:00Z",
                "asin": "B000ATTR01",
                "supplier_id": "ATTR-SUP-1",
                "supplier_name": "Attribution Supplier",
                "supplier_sku": "SKU-ATTR-1",
                "break_even": "10.00",
                "monthly_sold": "40",
                "bbp_monthly_units_chosen": "40",
                "bbp_sales_last_completed_month_label": "2026-03",
                "bbp_sales_last_completed_month_units": "40",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "2026-03",
                "bbp_sales_replay_demand_basis_units": "40",
                "title": "Attribution Product",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "asin": "B000ATTR01",
                "supplier": "Attribution Supplier",
                "supplier_sku": "SKU-ATTR-1",
                "cost": "8.20",
                "break_even": "10.00",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["history_confidence"] == "medium"
    assert row["input_status"] == "ready"
    assert "attribution_identity_legacy_source" in row["input_reason_codes"]
    assert "history_confidence_downgraded_by_attribution" in row["input_reason_codes"]


def test_f071_sets_classifier_states_with_full_year_pattern(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000CLASS01", days=400, start_day=date(2025, 1, 1)),
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:00:00Z",
                "asin": "B000CLASS01",
                "supplier_id": "CLS-SUP-1",
                "supplier_name": "Classifier Supplier",
                "supplier_sku": "SKU-CLS-1",
                "break_even": "10.00",
                "monthly_sold": "50",
                "bbp_monthly_units_chosen": "50",
                "bbp_sales_chart_month_labels": "01/25|02/25|03/25|04/25|05/25|06/25|07/25|08/25|09/25|10/25|11/25|12/25",
                "bbp_sales_chart_month_units": "4|4|5|5|6|6|7|8|9|10|45|50",
                "bbp_sales_last_completed_month_label": "12/25",
                "bbp_sales_last_completed_month_units": "50",
                "bbp_sales_current_month_label": "01/26",
                "bbp_sales_current_month_units": "3",
                "bbp_sales_future_month_count_ignored": "0",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "12/25",
                "bbp_sales_replay_demand_basis_units": "50",
                "title": "Classifier Product",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "asin": "B000CLASS01",
                "supplier": "Classifier Supplier",
                "supplier_sku": "SKU-CLS-1",
                "cost": "7.50",
                "break_even": "10.00",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["input_status"] == "ready"
    assert row["completed_months_count"] == "12"
    assert row["seasonality_state"] == "seasonal_confirmed"
    assert row["seasonality_reason_codes"] != ""
    assert row["stability_state"] == "drifting_up"
    assert row["stability_reason_codes"] != ""
    assert row["recent_vs_baseline_state"] == "overperforming"
    assert "seasonal_window" in row["recent_vs_baseline_reason_codes"]


def test_f071_holds_classifier_at_insufficient_history_for_short_series(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_source(
        tmp_path,
        "feeder_legacy_chart_daily_raw_live",
        _chart_rows("B000CLASS02", days=80, start_day=date(2026, 1, 1)),
    )
    _write_source(
        tmp_path,
        "feeder_legacy_scrape_evidence_live",
        [
            {
                "observed_utc": "2026-04-10T08:00:00Z",
                "asin": "B000CLASS02",
                "supplier_id": "CLS-SUP-2",
                "supplier_name": "Classifier Supplier 2",
                "supplier_sku": "SKU-CLS-2",
                "break_even": "10.00",
                "monthly_sold": "8",
                "bbp_monthly_units_chosen": "8",
                "bbp_sales_chart_month_labels": "01/26|02/26",
                "bbp_sales_chart_month_units": "8|9",
                "bbp_sales_last_completed_month_label": "02/26",
                "bbp_sales_last_completed_month_units": "9",
                "bbp_sales_current_month_label": "03/26",
                "bbp_sales_current_month_units": "8",
                "bbp_sales_future_month_count_ignored": "0",
                "bbp_sales_replay_demand_basis_source": "bbp_last_completed_month",
                "bbp_sales_replay_demand_basis_label": "02/26",
                "bbp_sales_replay_demand_basis_units": "9",
            }
        ],
    )
    _write_source(
        tmp_path,
        "feeder_legacy_first_checks_live",
        [
            {
                "asin": "B000CLASS02",
                "supplier": "Classifier Supplier 2",
                "supplier_sku": "SKU-CLS-2",
                "cost": "7.50",
                "break_even": "10.00",
            }
        ],
    )

    out_df = build_backtest_input_view(root=tmp_path, observed_utc="2026-04-10T11:00:00Z")
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["completed_months_count"] == "2"
    assert row["seasonality_state"] == "insufficient_history"
    assert row["stability_state"] == "too_new"
    assert row["recent_vs_baseline_state"] == "insufficient_history"
