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

from scripts.flows.O.O460_build_restock_session_view import build_restock_session_view
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-02T18:31:49Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def test_o460_builds_local_restock_session_with_source_labels_and_guards(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": OBSERVED,
                "seller_sku": "SKU-NATIVE",
                "asin": "ASIN-NATIVE",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "3",
                "current_supplier_buy_cost_gbp": "5",
                "current_supplier_cost_source": "supplier_price_list",
                "market_price_gbp": "12",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "",
                "refund_proof_state": "",
                "refund_sample_confidence": "",
                "roi_at_market_price_pct": "20",
                "market_price_ex_vat_gbp": "10",
                "market_price_vat_rate_pct": "20",
                "current_token_cost_gbp": "5",
                "break_even_price_gbp": "8",
                "net_fee_drag_per_unit_gbp": "2",
                "net_fee_model_status": "fresh",
                "net_fee_model_asof": OBSERVED,
                "net_fee_model_age_hours": "1",
                "net_fee_model_source": "api",
                "components_per_sell_pack": "1",
                "supplier_cost_basis": "unit",
                "component_unit_label": "Unit",
                "expected_sell_pack_cost_gbp": "5",
                "expected_component_cost_gbp": "5",
                "quantity_strategy": "raw_units",
                "preferred_order_sell_packs": "6",
                "preferred_order_components": "6",
                "preferred_supplier_boxes": "0",
                "supplier_box_components": "0",
                "hazmat_group": "",
                "isolate_from_normal_po": "0",
                "target_carton_weight_kg": "",
                "pack_profile_status": "ok",
                "source_inventory_asof": OBSERVED,
                "source_velocity_asof": OBSERVED,
                "source_performance_asof": OBSERVED,
                "title": "Native Product",
                "supplier_sku": "SUP-1",
                "barcode": "1234567890123",
                "price_list_unit_cost_gbp": "5",
                "price_list_source_received_at_utc": OBSERVED,
                "price_list_pack_size": "6",
                "price_list_moq": "6",
                "cost_match_method": "supplier_sku_supplier_matched",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_recommendations_live",
        [
            {
                "asof_utc": OBSERVED,
                "seller_sku": "SKU-NATIVE",
                "asin": "ASIN-NATIVE",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "recommendation_status": "test_restock",
                "recommended_qty_rounded": "6",
                "current_supplier_buy_cost_gbp": "5",
                "market_price_gbp": "12",
                "forward_roi_pct": "20",
                "forward_profit_per_unit_gbp": "2",
                "reason_codes": "ROI_OK",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": OBSERVED,
                "seller_sku": "SKU-NATIVE",
                "asin": "ASIN-NATIVE",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "recommendation_status": "test_restock",
                "suggested_qty": "6",
                "suggested_unit_cost_gbp": "5",
                "suggested_market_price_gbp": "12",
                "expected_forward_roi_pct": "20",
                "expected_forward_profit_per_unit_gbp": "2",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "reason_codes": "ROI_OK",
                "queue_status": "ready",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "legacy_purchase_list_bridge",
        [
            {
                "bridge_utc": OBSERVED,
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:row2",
                "supplier_name": "Legacy Supplier",
                "supplier_code": "LEG",
                "seller_sku": "SKU-LEGACY",
                "asin": "ASIN-LEGACY",
                "title": "Legacy Product",
                "supplier_sku": "LEG-1",
                "suggested_action": "full_restock",
                "recommendation_status": "full_restock",
                "suggested_qty": "2",
                "current_supplier_buy_cost_gbp": "4",
                "suggested_market_price_gbp": "10",
                "bridge_status": "ready",
                "done_flag": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_profit_checks_live",
        [
            {
                "check_utc": OBSERVED,
                "seller_sku": "SKU-NATIVE",
                "asin": "ASIN-NATIVE",
                "supplier_name": "Supplier",
                "suggested_action": "test_restock",
                "profit_verdict": "test_only",
                "profit_proof_source": "native_profit_proof",
                "profit_check_message": "safe review only",
                "current_sell_price_gbp": "12",
                "supplier_cost_gbp": "5",
                "fee_drag_gbp": "2",
                "refund_drag_gbp": "",
                "forward_profit_per_unit_gbp": "2",
                "forward_roi_pct": "20",
                "net_fee_model_status": "fresh",
                "cost_match_method": "supplier_sku_supplier_matched",
            }
        ],
    )

    review_df, summary_df, reason_df, health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
    )

    assert len(review_df.index) == 2
    by_sku = review_df.set_index("seller_sku")
    assert by_sku.loc["SKU-NATIVE", "source_class"] == "native_o"
    assert by_sku.loc["SKU-NATIVE", "supplier_match_state"] == "exact_supplier_sku_or_barcode_match"
    assert by_sku.loc["SKU-NATIVE", "refund_proof_state"] == "missing_refund_confidence"
    assert by_sku.loc["SKU-NATIVE", "inbound_cost_proof_state"] == "missing_inbound_cost_confidence"
    assert by_sku.loc["SKU-NATIVE", "profit_input_confidence"] == "missing_profit_inputs"
    assert by_sku.loc["SKU-NATIVE", "action_safety_state"] == "blocked_from_clean_buy"
    assert "refund:missing_refund_confidence" in by_sku.loc["SKU-NATIVE", "action_block_reason"]
    assert by_sku.loc["SKU-LEGACY", "source_class"] == "legacy_bridge"
    assert by_sku.loc["SKU-LEGACY", "supplier_cost_proof_state"] == "bridge_cost_only"
    assert set(reason_df["creates_live_action"].tolist()) == {"0"}
    assert summary_df.set_index("supplier_name").loc["Supplier", "total_rows"] == "1"
    assert set(health_df["status"].tolist()) == {"ok"}

    written = read_o_contract_df(tmp_path, "restock_session_review_live")
    assert len(written.index) == 2


def test_o460_allows_clean_review_when_refund_inbound_and_profit_inputs_are_verified(tmp_path: Path) -> None:
    source_row = {
        "asof_utc": OBSERVED,
        "seller_sku": "SKU-NATIVE",
        "asin": "ASIN-NATIVE",
        "supplier_code": "SUP",
        "supplier_name": "Supplier",
        "sale_status": "active",
        "available_now": "0",
        "total_quantity_now": "0",
        "amazon_inbound_working": "0",
        "amazon_inbound_shipped": "0",
        "amazon_inbound_receiving": "0",
        "velocity_30d": "3",
        "current_supplier_buy_cost_gbp": "5",
        "current_supplier_cost_source": "supplier_price_list",
        "market_price_gbp": "12",
        "market_price_basis_used": "BUY_BOX_PRICE",
        "expected_refund_cost_per_unit_gbp": "0.2",
        "refund_proof_state": "api_proved_or_not_applicable",
        "refund_sample_confidence": "high",
        "expected_inbound_cost_per_unit_gbp": "0.3",
        "inbound_cost_basis": "allocated_inbound_cost_per_received_unit",
        "inbound_cost_confidence": "sku_allocated",
        "profit_input_confidence": "profit_inputs_verified",
        "profit_input_blockers": "",
        "roi_at_market_price_pct": "20",
        "market_price_ex_vat_gbp": "10",
        "market_price_vat_rate_pct": "20",
        "current_token_cost_gbp": "5",
        "token_cost_trust_state": "trusted",
        "token_cost_trust_basis": "no_b_fallback_cost_risk_for_sku",
        "token_cost_trust_source": "out/systems/B/refunds/b_fallback_token_cost_audit.csv",
        "token_cost_trust_blockers": "",
        "break_even_price_gbp": "8",
        "net_fee_drag_per_unit_gbp": "2",
        "net_fee_model_status": "fresh",
        "net_fee_model_asof": OBSERVED,
        "net_fee_model_age_hours": "1",
        "net_fee_model_source": "api",
        "components_per_sell_pack": "1",
        "supplier_cost_basis": "unit",
        "component_unit_label": "Unit",
        "expected_sell_pack_cost_gbp": "5",
        "expected_component_cost_gbp": "5",
        "quantity_strategy": "raw_units",
        "preferred_order_sell_packs": "6",
        "preferred_order_components": "6",
        "preferred_supplier_boxes": "0",
        "supplier_box_components": "0",
        "hazmat_group": "",
        "isolate_from_normal_po": "0",
        "target_carton_weight_kg": "",
        "pack_profile_status": "ok",
        "source_inventory_asof": OBSERVED,
        "source_velocity_asof": OBSERVED,
        "source_performance_asof": OBSERVED,
        "title": "Native Product",
        "supplier_sku": "SUP-1",
        "barcode": "1234567890123",
        "price_list_unit_cost_gbp": "5",
        "price_list_source_received_at_utc": OBSERVED,
        "price_list_pack_size": "6",
        "price_list_moq": "6",
        "cost_match_method": "supplier_sku_supplier_matched",
    }
    _write_contract_rows(tmp_path, "restock_source_view", [source_row])
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": OBSERVED,
                "seller_sku": "SKU-NATIVE",
                "asin": "ASIN-NATIVE",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "recommendation_status": "test_restock",
                "suggested_qty": "6",
                "suggested_unit_cost_gbp": "5",
                "suggested_market_price_gbp": "12",
                "expected_forward_roi_pct": "20",
                "expected_forward_profit_per_unit_gbp": "2",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "reason_codes": "ROI_OK",
                "queue_status": "ready",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_profit_checks_live",
        [
            {
                "check_utc": OBSERVED,
                "seller_sku": "SKU-NATIVE",
                "asin": "ASIN-NATIVE",
                "supplier_name": "Supplier",
                "suggested_action": "test_restock",
                "profit_verdict": "test_only",
                "profit_proof_source": "native_profit_proof",
                "profit_check_message": "safe review only",
                "current_sell_price_gbp": "12",
                "supplier_cost_gbp": "5",
                "fee_drag_gbp": "2",
                "refund_drag_gbp": "0.2",
                "inbound_cost_drag_gbp": "0.3",
                "forward_profit_per_unit_gbp": "2",
                "forward_roi_pct": "20",
                "net_fee_model_status": "fresh",
                "cost_match_method": "supplier_sku_supplier_matched",
                "profit_input_confidence": "profit_inputs_verified",
                "profit_input_blockers": "",
            }
        ],
    )

    review_df, _summary_df, _reason_df, _health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
    )

    row = review_df.set_index("seller_sku").loc["SKU-NATIVE"]
    assert row["refund_proof_state"] == "api_proved_or_not_applicable"
    assert row["inbound_cost_proof_state"] == "inbound_cost_verified"
    assert row["profit_input_confidence"] == "profit_inputs_verified"
    assert row["action_safety_state"] == "clean_review_ready_not_po"


def test_o460_marks_missing_supplier_file_as_likely_discontinued_candidate(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": OBSERVED,
                "seller_sku": "SKU-MISSING",
                "asin": "ASIN-MISSING",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "1",
                "current_supplier_buy_cost_gbp": "",
                "current_supplier_cost_source": "missing",
                "market_price_gbp": "20",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "net_fee_model_status": "fresh",
                "components_per_sell_pack": "1",
                "supplier_cost_basis": "unit",
                "component_unit_label": "Unit",
                "expected_sell_pack_cost_gbp": "",
                "expected_component_cost_gbp": "",
                "quantity_strategy": "raw_units",
                "preferred_order_sell_packs": "1",
                "preferred_order_components": "1",
                "preferred_supplier_boxes": "0",
                "supplier_box_components": "0",
                "pack_profile_status": "ok",
                "source_inventory_asof": OBSERVED,
                "source_velocity_asof": OBSERVED,
                "source_performance_asof": OBSERVED,
                "supplier_cost_review_reason": "missing_from_latest_supplier_file",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": OBSERVED,
                "seller_sku": "SKU-MISSING",
                "asin": "ASIN-MISSING",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "recommendation_status": "wait",
                "suggested_qty": "1",
                "suggested_unit_cost_gbp": "",
                "suggested_market_price_gbp": "20",
                "expected_forward_roi_pct": "",
                "expected_forward_profit_per_unit_gbp": "",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "reason_codes": "BLOCKED_MISSING_COST",
                "queue_status": "ready",
            }
        ],
    )

    review_df, _summary_df, _reason_df, health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
        write_outputs=False,
    )

    row = review_df.iloc[0]
    assert row["supplier_match_state"] == "missing_from_latest_supplier_file"
    assert row["operator_decision_state"] == "likely_discontinued"
    assert "supplier:likely_discontinued_candidate" in row["action_block_reason"]
    assert set(health_df["status"].tolist()) == {"ok"}
