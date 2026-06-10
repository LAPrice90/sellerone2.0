from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O001_build_restock_source_view import build_restock_source_view
from scripts.flows.O.O005_build_supplier_cost_snapshot_test import build_supplier_cost_snapshot_test
from scripts.flows.O._contract_io import write_o_contract_df


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "o_phase1"


def _prepare_sources(tmp_path: Path, *, include_offer: bool = True, include_backtest: bool = True) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_DIR / "product_db_preview.csv", out_dir / "product_db_preview.csv")
    shutil.copy(FIXTURE_DIR / "inventory_summaries.csv", out_dir / "inventory_summaries.csv")
    shutil.copy(FIXTURE_DIR / "sku_sales_velocity.csv", out_dir / "sku_sales_velocity.csv")
    shutil.copy(FIXTURE_DIR / "sku_performance_summary.csv", out_dir / "sku_performance_summary.csv")
    shutil.copy(FIXTURE_DIR / "order_master.csv", out_dir / "order_master.csv")
    if include_offer:
        shutil.copy(FIXTURE_DIR / "listing_offer_snapshot_latest.csv", out_dir / "listing_offer_snapshot_latest.csv")
    if include_backtest:
        backtest_dir = out_dir / "systems" / "F" / "live"
        backtest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(
            FIXTURE_DIR / "feeder_backtest_summary_live.csv",
            backtest_dir / "feeder_backtest_summary_live.csv",
        )


def test_o001_source_join_success_and_one_row_per_sku(tmp_path: Path) -> None:
    tmp_root = tmp_path
    _prepare_sources(tmp_root, include_offer=True)

    out_df = build_restock_source_view(root=tmp_root, asof_utc="2026-04-03T11:00:00Z")
    assert len(out_df) == 7
    assert out_df["seller_sku"].nunique() == 7

    fallback = out_df.loc[out_df["seller_sku"] == "SKU-FALLBACK"].iloc[0]
    assert fallback["current_supplier_cost_source"] == "last_purchase_price"
    assert fallback["current_supplier_buy_cost_gbp"] == "6"
    assert fallback["current_cost_source"] == "last_purchase_price"
    assert fallback["current_cost_confidence"] == "medium"
    assert fallback["current_cost_class"] == "last_purchase_fallback"
    assert fallback["current_cost_value_gbp"] == "6"

    missing_cost = out_df.loc[out_df["seller_sku"] == "SKU-MISSINGCOST"].iloc[0]
    assert missing_cost["current_supplier_buy_cost_gbp"] == ""
    assert missing_cost["current_cost_source"] == "missing_cost"
    assert missing_cost["current_cost_confidence"] == "none"
    assert missing_cost["current_cost_class"] == "no_cost"
    assert "BLOCKED_MISSING_COST_INPUT" in missing_cost["source_notes"]

    full = out_df.loc[out_df["seller_sku"] == "SKU-FULL"].iloc[0]
    assert full["market_price_ex_vat_gbp"] == "6.833333"
    assert full["market_price_vat_rate_pct"] == "20"
    assert full["current_token_cost_gbp"] == "4.9"
    assert full["break_even_price_gbp"] == "6.2"
    assert full["net_fee_drag_per_unit_gbp"] == "1.2"
    assert full["net_fee_model_status"] == "fresh"
    assert full["net_fee_model_asof"] == "2026-04-03"
    assert full["net_fee_model_age_hours"] == "11"
    assert full["net_fee_model_source"] == "sku_performance_summary"


def test_o001_merges_optional_backtest_summary_fields_by_seller_sku(tmp_path: Path) -> None:
    _prepare_sources(tmp_path, include_offer=True, include_backtest=True)

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    full = out_df.loc[out_df["seller_sku"] == "SKU-FULL"].iloc[0]
    assert full["backtest_policy_id"] == "policy_live_default"
    assert full["backtest_history_confidence"] == "high"
    assert full["backtest_market_viability_score"] == "82.5"
    assert full["backtest_exit_risk_score"] == "18.2"
    assert full["backtest_estimated_total_profit_gbp"] == "312.4"
    assert full["backtest_estimated_monthly_profit_gbp"] == "44.6"
    assert full["backtest_recommendation"] == "Normal fit"

    missing = out_df.loc[out_df["seller_sku"] == "SKU-BULK"].iloc[0]
    assert missing["backtest_policy_id"] == ""
    assert missing["backtest_recommendation"] == ""


def test_o001_handles_missing_optional_h_context_with_reduced_confidence(tmp_path: Path) -> None:
    tmp_root = tmp_path
    _prepare_sources(tmp_root, include_offer=False)

    out_df = build_restock_source_view(root=tmp_root, asof_utc="2026-04-03T11:00:00Z")
    stale = out_df.loc[out_df["seller_sku"] == "SKU-STALE"].iloc[0]
    assert stale["market_price_basis_used"].startswith("PERFORMANCE_")
    assert "REDUCED_CONFIDENCE_MISSING_H_PRICE_CONTEXT" in stale["source_notes"]


def test_o001_does_not_duplicate_upstream_truth_domains(tmp_path: Path) -> None:
    tmp_root = tmp_path
    _prepare_sources(tmp_root, include_offer=True)

    out_df = build_restock_source_view(root=tmp_root, asof_utc="2026-04-03T11:00:00Z")
    blocked_columns = {
        "Price_ExVAT",
        "Quantity Ordered",
        "units_sold",
        "roi_exvat",
        "order_line_history_truth",
    }
    assert blocked_columns.isdisjoint(set(out_df.columns))


def test_o001_prefers_30_day_velocity_row_when_multiple_windows_exist(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-001,ASIN001,SUP-A,Alpha,1,1,5.0,4.8,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-001,ASIN001,5,2,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,window_days,velocity_units_per_day,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-001,7,2.0,2.0,,,2,5,2026-04-03\n"
        "SKU-001,30,1.1,,1.1,,2,5,2026-04-03\n"
        "SKU-001,90,0.9,,,0.9,2,5,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-001,0.1,20,21,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-001,ASIN001,9.0,9.2,1,9.1\n",
        encoding="utf-8",
    )
    (out_dir / "inbound_costs_allocated_sku.csv").write_text(
        "shipment_id,sku,received_qty,total_received_qty,currency,allocated_amount,allocated_tax,allocated_total\n"
        "SHIP-1,SKU-001,10,10,GBP,5,1,6\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )
    live = out_dir / "systems" / "O" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (live / "restock_token_cost_trust_gate_live.csv").write_text(
        "proof_utc,seller_sku,current_token_cost_gbp,token_cost_trust_state,token_cost_trust_basis,"
        "token_cost_trust_source,token_cost_trust_blockers,b_fallback_audit_rows,b_weak_fallback_rows_for_sku,"
        "token_ledger_fallback_rows_for_sku,safe_for_clean_buy,safe_for_po,source_path\n"
        "2026-04-03T11:00:00Z,SKU-001,5.0,trusted,no_b_fallback_cost_risk_for_sku,"
        "out/systems/B/refunds/b_fallback_token_cost_audit.csv,,1,0,0,1,1,out/sku_performance_summary.csv\n",
        encoding="utf-8",
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    row = out_df.loc[out_df["seller_sku"] == "SKU-001"].iloc[0]
    assert row["velocity_30d"] == "1.1"


def test_o001_carries_refund_confidence_fields_from_performance_summary(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-001,ASIN001,SUP-A,Alpha,1,1,5.0,4.8,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-001,ASIN001,5,2,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-001,1.1,1.0,0.9,2,5,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,refund_unit_rate_30d,refund_unit_rate_90d,refund_units_30d,sales_units_30d,refund_cost_basis,refund_proof_state,refund_sample_confidence,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-001,0.6,0.1,0.08,1,10,sale_cohort_90d,api_proved_or_not_applicable,high,20,21,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-001,ASIN001,9.0,9.2,1,9.1\n",
        encoding="utf-8",
    )
    (out_dir / "inbound_costs_allocated_sku.csv").write_text(
        "shipment_id,sku,received_qty,total_received_qty,currency,allocated_amount,allocated_tax,allocated_total\n"
        "SHIP-1,SKU-001,10,10,GBP,5,1,6\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )
    live = out_dir / "systems" / "O" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (live / "restock_token_cost_trust_gate_live.csv").write_text(
        "proof_utc,seller_sku,current_token_cost_gbp,token_cost_trust_state,token_cost_trust_basis,"
        "token_cost_trust_source,token_cost_trust_blockers,b_fallback_audit_rows,b_weak_fallback_rows_for_sku,"
        "token_ledger_fallback_rows_for_sku,safe_for_clean_buy,safe_for_po,source_path\n"
        "2026-04-03T11:00:00Z,SKU-001,5.0,trusted,no_b_fallback_cost_risk_for_sku,"
        "out/systems/B/refunds/b_fallback_token_cost_audit.csv,,1,0,0,1,1,out/sku_performance_summary.csv\n",
        encoding="utf-8",
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    row = out_df.loc[out_df["seller_sku"] == "SKU-001"].iloc[0]
    assert row["expected_refund_cost_per_unit_gbp"] == "0.6"
    assert row["refund_unit_rate_30d"] == "0.1"
    assert row["refund_unit_rate_90d"] == "0.08"
    assert row["refund_cost_basis"] == "sale_cohort_90d"
    assert row["refund_proof_state"] == "api_proved_or_not_applicable"
    assert row["expected_inbound_cost_per_unit_gbp"] == "0.6"
    assert row["inbound_cost_basis"] == "allocated_inbound_cost_per_received_unit"
    assert row["inbound_cost_confidence"] == "sku_allocated"
    assert row["profit_input_confidence"] == "profit_inputs_verified"
    assert row["profit_input_blockers"] == ""
    assert "REFUND_PROOF_WEAK" not in row["source_notes"]


def test_o001_carries_e_roi_and_restock_confidence_fields(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-001,ASIN001,SUP-A,Alpha,1,1,5.0,4.8,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-001,ASIN001,5,2,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-001,1.1,1.0,0.9,2,5,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,refund_unit_rate_30d,refund_unit_rate_90d,refund_units_30d,sales_units_30d,refund_cost_basis,refund_proof_state,refund_sample_confidence,profit_confidence,sales_truth_state,stock_signal,restock_business_ready,restock_decision_state,restock_missing_proof,missing_roi_reason,missing_roi_reason_detail,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-001,0.6,0.1,0.08,1,10,sale_cohort_90d,api_proved_or_not_applicable,high,profit_missing,velocity_only,yes,no,blocked_missing_roi,missing_roi;velocity_only_sales_truth,velocity_only_sales_truth,velocity_only_sales_truth,20,21,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-001,ASIN001,9.0,9.2,1,9.1\n",
        encoding="utf-8",
    )
    (out_dir / "inbound_costs_allocated_sku.csv").write_text(
        "shipment_id,sku,received_qty,total_received_qty,currency,allocated_amount,allocated_tax,allocated_total\n"
        "SHIP-1,SKU-001,10,10,GBP,5,1,6\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    row = out_df.loc[out_df["seller_sku"] == "SKU-001"].iloc[0]
    assert row["profit_confidence"] == "profit_missing"
    assert row["sales_truth_state"] == "velocity_only"
    assert row["stock_signal"] == "yes"
    assert row["restock_business_ready"] == "no"
    assert row["restock_decision_state"] == "blocked_missing_roi"
    assert row["restock_missing_proof"] == "missing_roi;velocity_only_sales_truth"
    assert row["missing_roi_reason"] == "velocity_only_sales_truth"
    assert row["missing_roi_reason_detail"] == "velocity_only_sales_truth"


def test_o001_labels_missing_inbound_cost_confidence_without_zero_cost(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-001,ASIN001,SUP-A,Alpha,1,1,5.0,4.8,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-001,ASIN001,5,2,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-001,1.1,1.0,0.9,2,5,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,refund_unit_rate_30d,refund_unit_rate_90d,refund_units_30d,sales_units_30d,refund_cost_basis,refund_proof_state,refund_sample_confidence,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-001,0.6,0.1,0.08,1,10,sale_cohort_90d,api_proved_or_not_applicable,high,20,21,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-001,ASIN001,9.0,9.2,1,9.1\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    row = out_df.loc[out_df["seller_sku"] == "SKU-001"].iloc[0]
    assert row["expected_inbound_cost_per_unit_gbp"] == ""
    assert row["inbound_cost_confidence"] == "missing"
    assert row["profit_input_confidence"] == "missing_profit_inputs"
    assert "missing_inbound_cost_confidence" in row["profit_input_blockers"]
    assert "INBOUND_COST_CONFIDENCE_MISSING" in row["source_notes"]


def test_o001_builds_coverage_classification_and_market_fallback_from_product_db(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate,live_listing_price\n"
        "SKU-ACTIVE,ASIN-A,SUP-A,Alpha,1,1,,4.50,active,20,12.20\n"
        "SKU-INACTIVE,ASIN-I,SUP-I,Inactive,1,1,,4.20,dropped,20,9.90\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-ACTIVE,ASIN-A,5,2,0,0,0,2026-04-03T09:00:00Z\n"
        "SKU-INACTIVE,ASIN-I,5,2,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-ACTIVE,1.1,1.0,0.9,2,5,2026-04-03\n"
        "SKU-INACTIVE,1.1,1.0,0.9,2,5,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-ACTIVE,0.1,20,21,6.0,5.0,2026-04-03\n"
        "SKU-INACTIVE,0.1,20,21,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )
    # Intentionally omit listing_offer_snapshot_latest.csv to force product_db live_listing fallback.

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    active = out_df.loc[out_df["seller_sku"] == "SKU-ACTIVE"].iloc[0]
    inactive = out_df.loc[out_df["seller_sku"] == "SKU-INACTIVE"].iloc[0]

    assert active["market_price_basis_used"] == "PRODUCT_DB_LIVE_LISTING_PRICE"
    assert active["has_current_market_price_input"] == "1"
    assert active["has_current_cost_input"] == "1"
    assert active["current_cost_source"] == "last_purchase_price"
    assert active["current_cost_confidence"] == "medium"
    assert active["current_cost_class"] == "last_purchase_fallback"
    assert active["has_demand_input"] == "1"
    assert active["has_minimum_restock_inputs"] == "1"
    assert active["coverage_block_reason"] == "ready_minimum_inputs"
    assert active["sale_status_normalized"] == "active"
    assert active["is_active_candidate"] == "1"
    assert "REDUCED_CONFIDENCE_PRODUCT_DB_MARKET_CONTEXT" in active["source_notes"]

    assert inactive["sale_status_normalized"] == "inactive"
    assert inactive["is_active_candidate"] == "0"
    assert inactive["coverage_block_reason"] == "inactive_status"


def test_o001_cost_classification_marks_ambiguous_cost_when_non_numeric(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-AMB,ASIN-AMB,SUP-A,Alpha,1,1,POA,TBD,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-AMB,ASIN-AMB,1,1,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-AMB,0.5,0.4,0.4,1,1,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-AMB,0.1,20,21,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-AMB,ASIN-AMB,9.0,9.2,1,9.1\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    row = out_df.loc[out_df["seller_sku"] == "SKU-AMB"].iloc[0]
    assert row["current_cost_source"] == "ambiguous_cost"
    assert row["current_cost_confidence"] == "low"
    assert row["current_cost_class"] == "ambiguous_cost"
    assert row["current_cost_value_gbp"] == ""
    assert "COST_AMBIGUOUS_SUPPLIER_CATALOG" in row["source_notes"]
    assert "COST_AMBIGUOUS_LAST_PURCHASE" in row["source_notes"]


def test_o001_carries_mock_quantity_profile_fields_from_product_inputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,title,main_image,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate,supplier_sku,barcode,amazon_pack_size,pack_conversion_note,order_qty_mode,sell_pack_qty,supplier_case_qty,supplier_case_multiple,valid_order_step,repack_required,bundle_required\n"
        "SKU-PACK,ASIN-PACK,Mock Pack Product,https://example.com/pack.jpg,SUP-P,Gamma Trade,20,20,0.70,,active,20,GAMMA-RAW-20,1234567890123,3,repack into packs of 3,sell_packs,3,20,1,20,1,0\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-PACK,ASIN-PACK,9,7,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-PACK,2.2,2.0,1.9,7,9,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-PACK,0.1,20,21,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-PACK,ASIN-PACK,9.0,9.2,1,9.1\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-04-03T11:00:00Z")
    row = out_df.loc[out_df["seller_sku"] == "SKU-PACK"].iloc[0]

    assert row["supplier_sku"] == "GAMMA-RAW-20"
    assert row["barcode"] == "1234567890123"
    assert row["amazon_pack_size"] == "3"
    assert row["pack_conversion_note"] == "repack into packs of 3"
    assert row["order_qty_mode"] == "sell_packs"
    assert row["order_qty_unit_label"] == "Packs"
    assert row["sell_pack_qty"] == "3"
    assert row["supplier_case_qty"] == "20"
    assert row["supplier_case_multiple"] == "1"
    assert row["valid_order_step"] == "20"
    assert row["repack_required"] == "1"
    assert row["bundle_required"] == "0"
    assert row["display_qtys_label"] == "Pack 3 | Case 20 | Step 20"


def test_o001_uses_test_supplier_cost_snapshot_only_in_explicit_test_mode(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-TFULL,ASIN-TFULL,SUP-A,Alpha,1,1,,,active,20\n"
        "SKU-NOMATCH,ASIN-NOMATCH,SUP-B,Beta,1,1,,,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-TFULL,ASIN-TFULL,2,0,0,0,0,2026-04-03T09:00:00Z\n"
        "SKU-NOMATCH,ASIN-NOMATCH,2,0,0,0,0,2026-04-03T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-TFULL,1.0,1.0,1.0,0,2,2026-04-03\n"
        "SKU-NOMATCH,1.0,1.0,1.0,0,2,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-TFULL,0.1,20,21,6.0,5.0,2026-04-03\n"
        "SKU-NOMATCH,0.1,20,21,6.0,5.0,2026-04-03\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-TFULL,ASIN-TFULL,12.0,12.0,1,11.9\n"
        "2026-04-03T09:00:00Z,2026-04-03,SKU-NOMATCH,ASIN-NOMATCH,12.0,12.0,1,11.9\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )

    fixture_rel = "tests/fixtures/o_phase1/supplier_cost_snapshot_test_input.csv"
    fixture_dst = tmp_path / fixture_rel
    fixture_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_DIR / "supplier_cost_snapshot_test_input.csv", fixture_dst)
    build_supplier_cost_snapshot_test(root=tmp_path)

    out_df = build_restock_source_view(
        root=tmp_path,
        asof_utc="2026-04-03T11:00:00Z",
        cost_mode="test",
    )
    matched = out_df.loc[out_df["seller_sku"] == "SKU-TFULL"].iloc[0]
    no_match = out_df.loc[out_df["seller_sku"] == "SKU-NOMATCH"].iloc[0]

    assert matched["current_supplier_cost_source"] == "supplier_cost_snapshot_test"
    assert matched["current_supplier_buy_cost_gbp"] == "8"
    assert matched["cost_mode"] == "test"
    assert matched["cost_source_type"] == "test_fixture"
    assert matched["current_cost_truth_type"] == "test_cost_truth"
    assert "TEST_COST_MODE_ACTIVE" in matched["source_notes"]
    assert "TEST_COST_SOURCE_APPLIED" in matched["source_notes"]

    assert no_match["current_supplier_buy_cost_gbp"] == ""
    assert no_match["cost_mode"] == "live"
    assert no_match["current_cost_truth_type"] == "no_cost_truth"
    assert "TEST_COST_NO_MATCH" in no_match["source_notes"]


def test_o001_uses_supplier_buy_cost_truth_when_live_cost_bridge_exists(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,supplier_code,supplier_name,supplier_sku,barcode,supplier_pack_size,amazon_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "SKU-DISCOUNT,ASIN-DISCOUNT,SUP-A,Alpha,ALPHA-DISCOUNT,2222222222222,1,1,1,2.00,1.80,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "SKU-DISCOUNT,ASIN-DISCOUNT,0,0,0,0,0,2026-05-19T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "SKU-DISCOUNT,1.0,1.0,1.0,0,0,2026-05-19\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "SKU-DISCOUNT,0.10,20,21,3.0,2.0,2026-05-19\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_channel,lowest_fba_price\n"
        "2026-05-19T09:00:00Z,2026-05-19,SKU-DISCOUNT,ASIN-DISCOUNT,3.00,3.00,buy_box,2.95\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )
    write_o_contract_df(
        tmp_path,
        "supplier_buy_cost_truth",
        pd.DataFrame(
            [
                {
                    "asof_utc": "2026-05-19T12:00:00Z",
                    "seller_sku": "SKU-DISCOUNT",
                    "asin": "ASIN-DISCOUNT",
                    "supplier_code": "SUP-A",
                    "supplier_name": "Alpha",
                    "supplier_sku": "ALPHA-DISCOUNT",
                    "barcode": "2222222222222",
                    "price_list_unit_cost_gbp": "2.50",
                    "price_list_currency": "GBP",
                    "price_list_unit_code": "PK12",
                    "price_list_pack_size": "12",
                    "price_list_pack_cost_gbp": "30.00",
                    "price_list_moq": "12",
                    "price_list_source_batch_id": "alpha_20260519",
                    "price_list_source_received_at_utc": "2026-05-19T09:00:00Z",
                    "price_list_source_row_key": "row_discount",
                    "purchase_reference_list_cost_gbp": "2.00",
                    "actual_paid_unit_cost_gbp": "1.80",
                    "actual_paid_source": "product_db_last_purchase_price",
                    "actual_vs_list_ratio": "0.9",
                    "discount_assumption_pct": "10",
                    "expected_next_unit_cost_gbp": "2.25",
                    "expected_cost_source": "discount_assumption_from_actual_paid",
                    "cost_confidence": "discount_assumption_needs_confirmation",
                    "user_price_check_required": "1",
                    "review_reason": "discount_assumption_needs_confirmation|price_list_changed_after_discounted_purchase",
                    "source_lineage": "product_db_preview|f_price_list_batch:alpha_20260519",
                }
            ]
        ),
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-05-19T12:10:00Z")
    row = out_df.loc[out_df["seller_sku"] == "SKU-DISCOUNT"].iloc[0]

    assert row["current_supplier_buy_cost_gbp"] == "2.25"
    assert row["current_supplier_cost_source"] == "supplier_buy_cost_truth"
    assert row["current_cost_source"] == "discount_assumption_from_actual_paid"
    assert row["user_price_check_required"] == "1"
    assert row["discount_assumption_pct"] == "10"
    assert row["expected_next_unit_cost_gbp"] == "2.25"
    assert row["supplier_pack_size"] == "12"
    assert row["moq"] == "12"
    assert row["order_qty_mode"] == "sell_packs"
    assert row["order_qty_unit_label"] == "Packs"
    assert row["sell_pack_qty"] == "12"
    assert row["display_qtys_label"] == "Pack 12 | Case 12"
    assert "PRICE_LIST_PACK_SIZE_APPLIED" in row["source_notes"]
    assert "SUPPLIER_BUY_COST_TRUTH_APPLIED" in row["source_notes"]
    assert "SUPPLIER_COST_USER_CHECK_REQUIRED" in row["source_notes"]


def test_o001_applies_confirmed_sika_pack_profiles_and_preserves_normal_rows(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,title,main_image,supplier_code,supplier_name,supplier_sku,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "6V-EEC1-2S9Z,ASIN-SIKA20,Sika 20g glue pack of 3,https://example.com/sika20.jpg,SIKA,Sika,484651,1,1,1.45,,active,20\n"
        "A2-T2AC-TW3L,ASIN-SIKA50,Sika 50g glue pack of 3,https://example.com/sika50.jpg,SIKA,Sika,484652,1,1,2.10,,active,20\n"
        "SKU-NORMAL,ASIN-NORMAL,Normal unit item,https://example.com/normal.jpg,SUP-N,Normal Supplier,N-1,1,1,5.00,,active,20\n"
        "SKU-SIKA-OTHER,ASIN-SIKA-OTHER,Sika waterproof tape roll,https://example.com/sika-other.jpg,SIKA,Sika,999999,1,1,3.00,,active,20\n"
        "SKU-EVERBUILD-3PCS,ASIN-EVERBUILD,3 PCS EVERBUILD INDUSTRIAL GRADE SUPER GLUE 20G EACH,https://example.com/everbuild.jpg,SIKA,Sika,484654,1,1,2.52,,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "6V-EEC1-2S9Z,ASIN-SIKA20,0,0,0,0,0,2026-05-19T09:00:00Z\n"
        "A2-T2AC-TW3L,ASIN-SIKA50,0,0,0,0,0,2026-05-19T09:00:00Z\n"
        "SKU-NORMAL,ASIN-NORMAL,0,0,0,0,0,2026-05-19T09:00:00Z\n"
        "SKU-SIKA-OTHER,ASIN-SIKA-OTHER,0,0,0,0,0,2026-05-19T09:00:00Z\n"
        "SKU-EVERBUILD-3PCS,ASIN-EVERBUILD,0,0,0,0,0,2026-05-19T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "6V-EEC1-2S9Z,10,10,10,0,0,2026-05-19\n"
        "A2-T2AC-TW3L,5,5,5,0,0,2026-05-19\n"
        "SKU-NORMAL,1,1,1,0,0,2026-05-19\n"
        "SKU-SIKA-OTHER,1,1,1,0,0,2026-05-19\n"
        "SKU-EVERBUILD-3PCS,1,1,1,0,0,2026-05-19\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "6V-EEC1-2S9Z,0,20,20,9.0,4.35,2026-05-19\n"
        "A2-T2AC-TW3L,0,20,20,12.0,6.30,2026-05-19\n"
        "SKU-NORMAL,0,20,20,8.0,5.00,2026-05-19\n"
        "SKU-SIKA-OTHER,0,20,20,7.0,3.00,2026-05-19\n"
        "SKU-EVERBUILD-3PCS,0,20,20,8.0,2.52,2026-05-19\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-05-19T09:00:00Z,2026-05-19,6V-EEC1-2S9Z,ASIN-SIKA20,9.00,9.00,1,8.90\n"
        "2026-05-19T09:00:00Z,2026-05-19,A2-T2AC-TW3L,ASIN-SIKA50,12.00,12.00,1,11.90\n"
        "2026-05-19T09:00:00Z,2026-05-19,SKU-NORMAL,ASIN-NORMAL,8.00,8.00,1,7.90\n"
        "2026-05-19T09:00:00Z,2026-05-19,SKU-SIKA-OTHER,ASIN-SIKA-OTHER,7.00,7.00,1,6.90\n"
        "2026-05-19T09:00:00Z,2026-05-19,SKU-EVERBUILD-3PCS,ASIN-EVERBUILD,8.00,8.00,1,7.90\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )
    write_o_contract_df(
        tmp_path,
        "sku_quantity_profiles",
        pd.DataFrame(
            [
                {
                    "seller_sku": "6V-EEC1-2S9Z",
                    "asin": "ASIN-SIKA20",
                    "supplier_name": "Sika",
                    "supplier_sku": "484651",
                    "profile_status": "confirmed",
                    "component_unit_label": "bottle",
                    "components_per_sell_pack": "3",
                    "amazon_pack_size": "3",
                    "order_qty_mode": "sell_packs",
                    "supplier_cost_basis": "component_unit",
                    "pack_profile_source": "operator_confirmed",
                    "pack_profile_note": "20g pack of 3 bottles",
                },
                {
                    "seller_sku": "A2-T2AC-TW3L",
                    "asin": "ASIN-SIKA50",
                    "supplier_name": "Sika",
                    "supplier_sku": "484652",
                    "profile_status": "confirmed",
                    "component_unit_label": "bottle",
                    "components_per_sell_pack": "3",
                    "amazon_pack_size": "3",
                    "order_qty_mode": "sell_packs",
                    "supplier_cost_basis": "component_unit",
                    "pack_profile_source": "operator_confirmed",
                    "pack_profile_note": "50g pack of 3 bottles",
                },
            ]
        ),
    )
    write_o_contract_df(
        tmp_path,
        "special_order_profiles",
        pd.DataFrame(
            [
                {
                    "profile_id": "sika_20g_pack3",
                    "supplier_name": "Sika",
                    "supplier_sku": "484651",
                    "seller_sku": "6V-EEC1-2S9Z",
                    "quantity_strategy": "preferred_carton_multiple",
                    "supplier_box_components": "25",
                    "preferred_order_sell_packs": "250",
                    "preferred_order_components": "750",
                    "preferred_supplier_boxes": "30",
                    "target_carton_weight_kg": "23",
                    "hazmat_group": "sika_glue",
                    "isolate_from_normal_po": "1",
                    "profile_status": "confirmed",
                    "profile_note": "operator confirmed",
                },
                {
                    "profile_id": "sika_50g_pack3",
                    "supplier_name": "Sika",
                    "supplier_sku": "484652",
                    "seller_sku": "A2-T2AC-TW3L",
                    "quantity_strategy": "preferred_carton_multiple",
                    "supplier_box_components": "20",
                    "preferred_order_sell_packs": "120",
                    "preferred_order_components": "360",
                    "preferred_supplier_boxes": "18",
                    "target_carton_weight_kg": "23",
                    "hazmat_group": "sika_glue",
                    "isolate_from_normal_po": "1",
                    "profile_status": "confirmed",
                    "profile_note": "operator confirmed",
                },
            ]
        ),
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-05-19T12:00:00Z")
    by_sku = out_df.set_index("seller_sku")

    sika20 = by_sku.loc["6V-EEC1-2S9Z"]
    assert sika20["components_per_sell_pack"] == "3"
    assert sika20["supplier_cost_basis"] == "component_unit"
    assert sika20["current_supplier_buy_cost_gbp"] == "4.35"
    assert sika20["current_supplier_cost_source"] == "supplier_catalog_price_converted_to_sell_pack"
    assert sika20["current_cost_source"] == "supplier_catalog_price_converted_to_sell_pack"
    assert sika20["current_cost_value_gbp"] == "4.35"
    assert sika20["current_cost_class"] == "sell_pack_converted_supplier_cost"
    assert sika20["expected_sell_pack_cost_gbp"] == "4.35"
    assert sika20["expected_component_cost_gbp"] == "1.45"
    assert sika20["preferred_order_sell_packs"] == "250"
    assert sika20["preferred_order_components"] == "750"
    assert sika20["preferred_supplier_boxes"] == "30"
    assert sika20["supplier_box_components"] == "25"
    assert sika20["hazmat_group"] == "sika_glue"
    assert sika20["isolate_from_normal_po"] == "1"
    assert sika20["pack_profile_status"] == "confirmed"

    sika50 = by_sku.loc["A2-T2AC-TW3L"]
    assert sika50["expected_sell_pack_cost_gbp"] == "6.3"
    assert sika50["preferred_order_sell_packs"] == "120"
    assert sika50["preferred_order_components"] == "360"
    assert sika50["preferred_supplier_boxes"] == "18"
    assert sika50["supplier_box_components"] == "20"

    normal = by_sku.loc["SKU-NORMAL"]
    assert normal["components_per_sell_pack"] == "1"
    assert normal["supplier_cost_basis"] == "sell_pack"
    assert normal["current_supplier_buy_cost_gbp"] == "5"
    assert normal["expected_sell_pack_cost_gbp"] == "5"
    assert normal["pack_profile_status"] == "default_normal"

    other_sika = by_sku.loc["SKU-SIKA-OTHER"]
    assert other_sika["components_per_sell_pack"] == "1"
    assert other_sika["supplier_cost_basis"] == "sell_pack"
    assert other_sika["pack_profile_status"] == "default_normal"

    everbuild_pack = by_sku.loc["SKU-EVERBUILD-3PCS"]
    assert everbuild_pack["components_per_sell_pack"] == "1"
    assert everbuild_pack["pack_profile_status"] == "missing_pack_profile"
    assert "missing_pack_profile" in everbuild_pack["source_notes"]
    assert "special_order_profile_required" in everbuild_pack["source_notes"]


def test_o001_does_not_apply_sika_pack_profile_by_supplier_sku_only(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "product_db_preview.csv").write_text(
        "seller_sku,asin,title,main_image,supplier_code,supplier_name,supplier_sku,supplier_pack_size,moq,supplier_catalog_price,last_purchase_price,sale_status,vat_rate\n"
        "PE-G94Y-4PYO,ASIN-PE,Sika 50g glue 2 pack,https://example.com/pe.jpg,SIKA,Sika,484652,1,1,2.10,,active,20\n",
        encoding="utf-8",
    )
    (out_dir / "inventory_summaries.csv").write_text(
        "seller_sku,asin,total_quantity,available,inbound_working,inbound_shipped,inbound_receiving,last_updated_time\n"
        "PE-G94Y-4PYO,ASIN-PE,0,0,0,0,0,2026-05-19T09:00:00Z\n",
        encoding="utf-8",
    )
    (out_dir / "sku_sales_velocity.csv").write_text(
        "sku,v7,v30,v90,available,total_quantity,asof_date\n"
        "PE-G94Y-4PYO,1,1,1,0,0,2026-05-19\n",
        encoding="utf-8",
    )
    (out_dir / "sku_performance_summary.csv").write_text(
        "sku,expected_refund_cost_per_unit_gbp,roi_at_our_price_pct,roi_at_buy_box_price_pct,break_even_price_gbp,current_token_cost_gbp,asof_date\n"
        "PE-G94Y-4PYO,0,20,20,12.0,2.10,2026-05-19\n",
        encoding="utf-8",
    )
    (out_dir / "listing_offer_snapshot_latest.csv").write_text(
        "timestamp_utc,asof_date,sku,asin,our_price,buy_box_price,buy_box_present_flag,lowest_fba_price\n"
        "2026-05-19T09:00:00Z,2026-05-19,PE-G94Y-4PYO,ASIN-PE,12.00,12.00,1,11.90\n",
        encoding="utf-8",
    )
    (out_dir / "order_master.csv").write_text(
        "Date,Order ID,country_code,SKU,Quantity Ordered,currency_code,Price_ExVAT,COGS_ExVAT,FBA_Fee_ExVAT\n",
        encoding="utf-8",
    )
    write_o_contract_df(
        tmp_path,
        "sku_quantity_profiles",
        pd.DataFrame(
            [
                {
                    "seller_sku": "A2-T2AC-TW3L",
                    "asin": "ASIN-SIKA50",
                    "supplier_name": "Sika",
                    "supplier_sku": "484652",
                    "profile_status": "confirmed",
                    "component_unit_label": "bottle",
                    "components_per_sell_pack": "3",
                    "amazon_pack_size": "3",
                    "order_qty_mode": "sell_packs",
                    "supplier_cost_basis": "component_unit",
                    "pack_profile_source": "operator_confirmed",
                    "pack_profile_note": "50g pack of 3 bottles",
                }
            ]
        ),
    )

    out_df = build_restock_source_view(root=tmp_path, asof_utc="2026-05-19T12:00:00Z")
    row = out_df.loc[out_df["seller_sku"] == "PE-G94Y-4PYO"].iloc[0]

    assert row["components_per_sell_pack"] == "1"
    assert row["current_supplier_buy_cost_gbp"] == "2.1"
    assert row["pack_profile_status"] == "missing_pack_profile"
    assert "missing_pack_profile" in row["source_notes"]
