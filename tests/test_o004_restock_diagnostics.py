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

from scripts.flows.O.O004_build_restock_diagnostics import build_restock_diagnostics
from scripts.flows.O._schemas import get_o_output_contract


def test_o004_active_coverage_breakdown_summary(tmp_path: Path) -> None:
    source_path = tmp_path / get_o_output_contract("restock_source_view").rel_path
    rec_path = tmp_path / get_o_output_contract("restock_recommendations_live").rel_path
    source_path.parent.mkdir(parents=True, exist_ok=True)

    source_df = pd.DataFrame(
        [
            {
                "asof_utc": "2026-04-03T11:00:00Z",
                "seller_sku": "SKU-ACT-READY",
                "asin": "ASIN-A",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "supplier_catalog_price": "",
                "last_purchase_price": "5.0",
                "available_now": "1",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "1.2",
                "current_supplier_buy_cost_gbp": "5.0",
                "current_supplier_cost_source": "last_purchase_price",
                "current_cost_value_gbp": "5.0",
                "current_cost_source": "last_purchase_price",
                "current_cost_confidence": "medium",
                "current_cost_class": "last_purchase_fallback",
                "cost_mode": "live",
                "cost_source_type": "live_product_inputs",
                "cost_source_reference": "out/product_db_preview.csv",
                "current_cost_truth_type": "live_cost_truth",
                "market_price_gbp": "10.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "source_notes": "",
                "is_active_candidate": "1",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "1",
                "has_demand_input": "1",
                "has_minimum_restock_inputs": "1",
                "coverage_block_reason": "ready_minimum_inputs",
            },
            {
                "asof_utc": "2026-04-03T11:00:00Z",
                "seller_sku": "SKU-ACT-NOCOST",
                "asin": "ASIN-B",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "supplier_catalog_price": "",
                "last_purchase_price": "",
                "available_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "1.0",
                "current_supplier_buy_cost_gbp": "",
                "current_supplier_cost_source": "missing_cost",
                "current_cost_value_gbp": "",
                "current_cost_source": "missing_cost",
                "current_cost_confidence": "none",
                "current_cost_class": "no_cost",
                "cost_mode": "live",
                "cost_source_type": "live_product_inputs",
                "cost_source_reference": "out/product_db_preview.csv",
                "current_cost_truth_type": "no_cost_truth",
                "market_price_gbp": "9.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "source_notes": "BLOCKED_MISSING_COST_INPUT",
                "is_active_candidate": "1",
                "has_current_cost_input": "0",
                "has_current_market_price_input": "1",
                "has_demand_input": "1",
                "has_minimum_restock_inputs": "0",
                "coverage_block_reason": "missing_cost_only",
            },
            {
                "asof_utc": "2026-04-03T11:00:00Z",
                "seller_sku": "SKU-ACT-NOMKT",
                "asin": "ASIN-C",
                "supplier_code": "SUP-C",
                "supplier_name": "Gamma",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "supplier_catalog_price": "",
                "last_purchase_price": "4.0",
                "available_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "1.0",
                "current_supplier_buy_cost_gbp": "4.0",
                "current_supplier_cost_source": "supplier_cost_snapshot_test",
                "current_cost_value_gbp": "4.0",
                "current_cost_source": "supplier_cost_snapshot_test",
                "current_cost_confidence": "test",
                "current_cost_class": "current_supplier_cost",
                "cost_mode": "test",
                "cost_source_type": "test_fixture",
                "cost_source_reference": "tests/fixtures/o_phase1/supplier_cost_snapshot_test_input.csv",
                "current_cost_truth_type": "test_cost_truth",
                "market_price_gbp": "",
                "market_price_basis_used": "MISSING_MARKET_CONTEXT",
                "source_notes": "REDUCED_CONFIDENCE_MISSING_H_PRICE_CONTEXT",
                "is_active_candidate": "1",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "0",
                "has_demand_input": "1",
                "has_minimum_restock_inputs": "0",
                "coverage_block_reason": "missing_market_only",
            },
            {
                "asof_utc": "2026-04-03T11:00:00Z",
                "seller_sku": "SKU-INACTIVE",
                "asin": "ASIN-D",
                "supplier_code": "SUP-D",
                "supplier_name": "Delta",
                "sale_status": "dropped",
                "sale_status_normalized": "inactive",
                "supplier_catalog_price": "",
                "last_purchase_price": "",
                "available_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "0",
                "current_supplier_buy_cost_gbp": "",
                "current_supplier_cost_source": "missing_cost",
                "current_cost_value_gbp": "",
                "current_cost_source": "missing_cost",
                "current_cost_confidence": "none",
                "current_cost_class": "no_cost",
                "cost_mode": "live",
                "cost_source_type": "live_product_inputs",
                "cost_source_reference": "out/product_db_preview.csv",
                "current_cost_truth_type": "no_cost_truth",
                "market_price_gbp": "",
                "market_price_basis_used": "MISSING_MARKET_CONTEXT",
                "source_notes": "",
                "is_active_candidate": "0",
                "has_current_cost_input": "0",
                "has_current_market_price_input": "0",
                "has_demand_input": "0",
                "has_minimum_restock_inputs": "0",
                "coverage_block_reason": "inactive_status",
            },
        ]
    )
    source_df.to_csv(source_path, index=False)

    rec_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-ACT-READY",
                "recommendation_status": "full_restock",
                "reason_codes": "ROI_OK",
                "recommended_qty_raw": "20",
                "recommended_qty_rounded": "20",
                "forward_roi_pct": "40",
                "confidence_note": "",
                "blocked_note": "",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "seller_sku": "SKU-ACT-NOCOST",
                "recommendation_status": "wait",
                "reason_codes": "BLOCKED_MISSING_COST_INPUT",
                "recommended_qty_raw": "0",
                "recommended_qty_rounded": "0",
                "forward_roi_pct": "",
                "confidence_note": "missing_forward_roi_inputs",
                "blocked_note": "missing_forward_roi_inputs",
                "cost_mode": "live",
                "recommendation_basis": "live_mode_missing_cost",
            },
            {
                "seller_sku": "SKU-ACT-NOMKT",
                "recommendation_status": "wait",
                "reason_codes": "BLOCKED_MISSING_MARKET_PRICE_INPUT",
                "recommended_qty_raw": "0",
                "recommended_qty_rounded": "0",
                "forward_roi_pct": "",
                "confidence_note": "missing_forward_roi_inputs",
                "blocked_note": "missing_forward_roi_inputs",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
            },
            {
                "seller_sku": "SKU-INACTIVE",
                "recommendation_status": "wait",
                "reason_codes": "SALE_STATUS_NOT_ACTIVE",
                "recommended_qty_raw": "0",
                "recommended_qty_rounded": "0",
                "forward_roi_pct": "",
                "confidence_note": "inactive_sale_status",
                "blocked_note": "inactive_sale_status",
                "cost_mode": "live",
                "recommendation_basis": "live_mode_missing_cost",
            },
        ]
    )
    rec_df.to_csv(rec_path, index=False)

    detail_df, summary_df = build_restock_diagnostics(root=tmp_path)
    summary = {str(r["metric"]): str(r["value"]) for _, r in summary_df.iterrows()}

    assert len(detail_df) == 4
    assert summary["rows_source"] == "4"
    assert summary["rows_active_only"] == "3"
    assert summary["active_actionable_now"] == "1"
    assert summary["active_missing_cost_only"] == "1"
    assert summary["active_missing_market_only"] == "1"
    assert summary["rows_recommendation_full_restock"] == "1"
    assert summary["rows_recommendation_wait"] == "3"
    assert summary["active_rows_with_current_supplier_cost"] == "1"
    assert summary["active_rows_with_last_purchase_fallback_only"] == "1"
    assert summary["active_rows_with_no_cost_input"] == "1"
    assert summary["active_rows_with_ambiguous_cost"] == "0"
    assert summary["active_rows_with_demand_market_last_purchase_fallback"] == "1"
    assert summary["active_rows_with_test_cost_truth"] == "1"
    assert summary["active_rows_with_live_cost_truth"] == "1"
    assert summary["active_rows_with_no_cost_truth"] == "1"
