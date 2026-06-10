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

from scripts.flows.O.O021_build_restock_profit_checks import build_restock_profit_checks
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _rec_row(
    sku: str,
    *,
    status: str,
    cost: str = "10",
    market: str = "13",
    roi: str = "20",
    profit: str = "2",
    reason: str = "ROI_OK",
    qty: str = "5",
    velocity: str = "1",
    price_basis: str = "BUY_BOX_PRICE",
    purchase_status: str = "within_target_roi_max",
    max_target: str = "10.9",
    net_fee_status: str = "fresh",
) -> dict[str, str]:
    return {
        "asof_utc": "2026-05-22T08:00:00Z",
        "seller_sku": sku,
        "asin": f"ASIN-{sku}",
        "supplier_code": "SUP",
        "supplier_name": "Supplier",
        "recommendation_status": status,
        "reason_codes": reason,
        "recommended_qty_raw": qty,
        "recommended_qty_rounded": qty,
        "target_days_cover": "30",
        "days_cover_available_only": "2",
        "days_cover_total_pipeline": "2",
        "current_supplier_buy_cost_gbp": cost,
        "current_supplier_cost_source": "supplier_catalog_price",
        "market_price_gbp": market,
        "market_price_basis_used": price_basis,
        "expected_refund_cost_per_unit_gbp": "0.1",
        "refund_proof_state": "api_proved_or_not_applicable",
        "refund_sample_confidence": "high",
        "expected_inbound_cost_per_unit_gbp": "0.2",
        "inbound_cost_basis": "allocated_inbound_cost_per_received_unit",
        "inbound_cost_confidence": "sku_allocated",
        "profit_input_confidence": "profit_inputs_verified",
        "profit_input_blockers": "",
        "forward_roi_pct": roi,
        "forward_profit_per_unit_gbp": profit,
        "cost_mode": "live",
        "recommendation_basis": "live_cost_inputs",
        "net_fee_drag_per_unit_gbp": "0.5",
        "net_fee_model_status": net_fee_status,
        "purchase_price_safety_status": purchase_status,
        "max_break_even_purchase_price_gbp": "12",
        "max_target_roi_purchase_price_gbp": max_target,
        "price_list_unit_cost_gbp": cost,
        "price_list_source_received_at_utc": "2026-05-22T07:30:00Z",
        "cost_match_method": "supplier_sku_supplier_matched",
        "cost_confidence": "price_list_actual_match",
        "expected_cost_source": "supplier_price_list_no_discount",
        "usual_paid_unit_cost_gbp": cost,
        "price_list_change_status": "unchanged",
        "target_roi_pct": "10",
        "velocity_30d": velocity,
    }


def test_o021_builds_profit_verdicts_and_temporary_sale_guardrails(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_recommendations_live",
        [
            _rec_row("SKU-SAFE", status="full_restock", roi="20", profit="2"),
            _rec_row("SKU-TEST", status="test_restock", roi="12", profit="1.2"),
            _rec_row("SKU-LOW-TEMP", status="wait", roi="5", profit="0.5", reason="ROI_BELOW_MIN_THRESHOLD"),
            _rec_row("SKU-MISSING-MARKET", status="wait", market="", roi="", profit="", reason="BLOCKED_MISSING_MARKET_PRICE_INPUT"),
            _rec_row("SKU-MISSING-FEE", status="full_restock", roi="20", profit="2", net_fee_status="missing"),
            _rec_row(
                "SKU-BREAK",
                status="wait",
                roi="5",
                profit="0.5",
                velocity="0",
                reason="COST_ABOVE_BREAK_EVEN_MAX_PURCHASE_PRICE",
                purchase_status="above_break_even_max",
            ),
            _rec_row("SKU-SUPPLY", status="wait", roi="20", profit="2", reason="SUFFICIENT_EFFECTIVE_SUPPLY", qty="0"),
            _rec_row("SKU-ROUND", status="test_restock", cost="100", market="112", roi="12", profit="12", qty="2", max_target="101"),
            _rec_row("SKU-REPEAT", status="wait", roi="5", profit="0.5", reason="ROI_BELOW_MIN_THRESHOLD"),
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-05-22T08:00:00Z",
                "seller_sku": sku,
                "asin": f"ASIN-{sku}",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "available_now": "50" if sku == "SKU-SUPPLY" else "0",
                "total_quantity_now": "50" if sku == "SKU-SUPPLY" else "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "1",
                "current_supplier_buy_cost_gbp": "10",
                "market_price_gbp": "" if sku == "SKU-MISSING-MARKET" else "13",
                "market_price_basis_used": "MISSING_MARKET_CONTEXT" if sku == "SKU-MISSING-MARKET" else "BUY_BOX_PRICE",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "0" if sku == "SKU-MISSING-MARKET" else "1",
                "has_demand_input": "1",
                "cost_mode": "live",
            }
            for sku in [
                "SKU-SAFE",
                "SKU-TEST",
                "SKU-LOW-TEMP",
                "SKU-MISSING-MARKET",
                "SKU-MISSING-FEE",
                "SKU-BREAK",
                "SKU-SUPPLY",
                "SKU-ROUND",
                "SKU-REPEAT",
            ]
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_profit_check_history",
        [
            {
                "check_utc": "2026-05-13T08:00:00Z",
                "seller_sku": "SKU-REPEAT",
                "asin": "ASIN-SKU-REPEAT",
                "supplier_name": "Supplier",
                "profit_verdict": "temporary_market_risk",
                "forward_roi_pct": "5",
                "current_sell_price_gbp": "13",
                "supplier_cost_gbp": "10",
                "profit_proof_source": "native_profit_proof",
                "guardrail_flags": "single_current_market_snapshot_not_drop",
                "source_reference": "history",
            },
            {
                "check_utc": "2026-05-16T08:00:00Z",
                "seller_sku": "SKU-REPEAT",
                "asin": "ASIN-SKU-REPEAT",
                "supplier_name": "Supplier",
                "profit_verdict": "temporary_market_risk",
                "forward_roi_pct": "5",
                "current_sell_price_gbp": "13",
                "supplier_cost_gbp": "10",
                "profit_proof_source": "native_profit_proof",
                "guardrail_flags": "single_current_market_snapshot_not_drop",
                "source_reference": "history",
            },
        ],
    )
    checks_df, health_df = build_restock_profit_checks(
        root=tmp_path,
        check_utc="2026-05-22T08:00:00Z",
        append_history=False,
    )
    by_sku = checks_df.set_index("seller_sku")

    assert by_sku.loc["SKU-SAFE", "profit_verdict"] == "safe_to_review"
    assert by_sku.loc["SKU-TEST", "profit_verdict"] == "test_only"
    assert by_sku.loc["SKU-LOW-TEMP", "profit_verdict"] == "temporary_market_risk"
    assert "single_current_market_snapshot_not_drop" in by_sku.loc["SKU-LOW-TEMP", "guardrail_flags"]
    assert by_sku.loc["SKU-MISSING-MARKET", "profit_verdict"] == "missing_profit_inputs"
    assert "missing_market_price" in by_sku.loc["SKU-MISSING-MARKET", "missing_input_reasons"]
    assert by_sku.loc["SKU-MISSING-FEE", "profit_verdict"] == "missing_profit_inputs"
    assert "missing_net_fee_model" in by_sku.loc["SKU-MISSING-FEE", "missing_input_reasons"]
    assert by_sku.loc["SKU-BREAK", "profit_verdict"] == "do_not_buy_now"
    assert by_sku.loc["SKU-SUPPLY", "profit_verdict"] == "do_not_buy_now"
    assert "existing_stock_or_order_prevents_overbuy" in by_sku.loc["SKU-SUPPLY", "guardrail_flags"]
    assert by_sku.loc["SKU-ROUND", "profit_verdict"] == "needs_price_check"
    assert "test_spend_cap_exceeded_after_rounding" in by_sku.loc["SKU-ROUND", "guardrail_flags"]
    assert by_sku.loc["SKU-REPEAT", "profit_verdict"] == "drop_review_only"
    assert by_sku.loc["SKU-REPEAT", "bad_economics_snapshot_count"] == "3"
    assert by_sku.loc["SKU-REPEAT", "bad_economics_window_days"] == "9"

    health = health_df.set_index("check_name")
    assert health.loc["drop_review_requires_repeated_bad_economics", "status"] == "ok"
    assert health.loc["verdict::temporary_market_risk", "value"] == "1"


def test_o021_blocks_clean_profit_when_inbound_cost_confidence_is_missing(tmp_path: Path) -> None:
    weak_rec = _rec_row("SKU-WEAK-INBOUND", status="full_restock", roi="20", profit="2")
    weak_rec.update(
        {
            "expected_inbound_cost_per_unit_gbp": "",
            "inbound_cost_basis": "missing_sku_inbound_cost_allocation",
            "inbound_cost_confidence": "missing",
            "profit_input_confidence": "missing_profit_inputs",
            "profit_input_blockers": "missing_inbound_cost_confidence",
        }
    )
    _write_contract_rows(tmp_path, "restock_recommendations_live", [weak_rec])
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-05-22T08:00:00Z",
                "seller_sku": "SKU-WEAK-INBOUND",
                "asin": "ASIN-SKU-WEAK-INBOUND",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "sale_status": "active",
                "sale_status_normalized": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "1",
                "current_supplier_buy_cost_gbp": "10",
                "market_price_gbp": "13",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "has_current_cost_input": "1",
                "has_current_market_price_input": "1",
                "has_demand_input": "1",
                "cost_mode": "live",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "refund_proof_state": "api_proved_or_not_applicable",
                "refund_sample_confidence": "high",
                "expected_inbound_cost_per_unit_gbp": "",
                "inbound_cost_basis": "missing_sku_inbound_cost_allocation",
                "inbound_cost_confidence": "missing",
                "profit_input_confidence": "missing_profit_inputs",
                "profit_input_blockers": "missing_inbound_cost_confidence",
            }
        ],
    )

    checks_df, _health_df = build_restock_profit_checks(
        root=tmp_path,
        check_utc="2026-05-22T08:00:00Z",
        append_history=False,
    )
    row = checks_df.iloc[0]

    assert row["profit_verdict"] == "missing_profit_inputs"
    assert "missing_inbound_cost_confidence" in row["missing_input_reasons"]
    assert row["inbound_cost_drag_gbp"] == ""


def test_o021_labels_legacy_sheet_profit_hints_no_data_and_drop_rows(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "legacy_purchase_list_bridge",
        [
            {
                "bridge_utc": "2026-05-22T08:00:00Z",
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:sheet:Purchase List:row3",
                "supplier_name": "Legacy Supplier",
                "seller_sku": "SKU-BRIDGE-RESTOCK",
                "asin": "ASIN-BRIDGE-RESTOCK",
                "title": "Bridge Restock",
                "display_qtys_label": "Unit",
                "suggested_action": "full_restock",
                "recommendation_status": "full_restock",
                "sheet_recommend_label": "Restock",
                "suggested_qty": "5",
                "recommended_qty_rounded": "5",
                "current_supplier_buy_cost_gbp": "5",
                "suggested_unit_cost_gbp": "5",
                "suggested_market_price_gbp": "7",
                "market_price_gbp": "7",
                "expected_forward_roi_pct": "40",
                "forward_roi_pct": "40",
                "forward_profit_per_unit_gbp": "2",
                "velocity_30d": "1",
                "days_cover_available_only": "1",
                "queue_status": "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_restock",
                "bridge_status": "ready",
                "bridge_note": "LEGACY_PURCHASE_LIST_RESTOCK",
                "market_price_basis_used": "LEGACY_PURCHASE_LIST_ROI_BACKSOLVE",
            },
            {
                "bridge_utc": "2026-05-22T08:00:00Z",
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:sheet:Purchase List:row4",
                "supplier_name": "Legacy Supplier",
                "seller_sku": "SKU-BRIDGE-NODATA",
                "asin": "ASIN-BRIDGE-NODATA",
                "title": "Bridge No Data",
                "display_qtys_label": "Unit",
                "suggested_action": "test_restock",
                "recommendation_status": "test_restock",
                "sheet_recommend_label": "No Data",
                "suggested_qty": "1",
                "recommended_qty_rounded": "1",
                "current_supplier_buy_cost_gbp": "3",
                "suggested_unit_cost_gbp": "3",
                "queue_status": "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_no_data",
                "bridge_status": "ready",
                "bridge_note": "NO_DATA_TEST_CANDIDATE",
            },
            {
                "bridge_utc": "2026-05-22T08:00:00Z",
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:sheet:Purchase List:row5",
                "supplier_name": "Legacy Supplier",
                "seller_sku": "SKU-BRIDGE-DROP",
                "asin": "ASIN-BRIDGE-DROP",
                "title": "Bridge Drop",
                "display_qtys_label": "Unit",
                "suggested_action": "wait",
                "recommendation_status": "wait",
                "sheet_recommend_label": "Drop",
                "suggested_qty": "0",
                "recommended_qty_rounded": "0",
                "current_supplier_buy_cost_gbp": "2",
                "suggested_unit_cost_gbp": "2",
                "expected_forward_roi_pct": "0",
                "forward_roi_pct": "0",
                "queue_status": "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_drop",
                "bridge_status": "ready",
                "bridge_note": "DROP_VISIBLE_NOT_BUYABLE_BY_DEFAULT",
                "drop_flag": "1",
            },
            {
                "bridge_utc": "2026-05-22T08:00:00Z",
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:sheet:Purchase List:row6",
                "supplier_name": "Legacy Supplier",
                "seller_sku": "SKU-BRIDGE-NODATA-ZERO-COST",
                "asin": "ASIN-BRIDGE-NODATA-ZERO-COST",
                "title": "Bridge No Data Zero Cost",
                "display_qtys_label": "Unit",
                "suggested_action": "test_restock",
                "recommendation_status": "test_restock",
                "sheet_recommend_label": "No Data",
                "suggested_qty": "1",
                "recommended_qty_rounded": "1",
                "current_supplier_buy_cost_gbp": "0",
                "suggested_unit_cost_gbp": "0",
                "queue_status": "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_no_data",
                "bridge_status": "ready",
                "bridge_note": "NO_DATA_TEST_CANDIDATE",
            },
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-05-22T08:00:00Z",
                "seller_sku": "SKU-BRIDGE-RESTOCK",
                "asin": "ASIN-BRIDGE-RESTOCK",
                "supplier_code": "SUP",
                "supplier_name": "Legacy Supplier",
                "sale_status": "active",
                "current_supplier_buy_cost_gbp": "4.5",
                "price_list_unit_cost_gbp": "4.5",
                "price_list_source_received_at_utc": "2026-05-22T07:30:00Z",
                "price_list_unit_code": "PK12",
                "price_list_pack_size": "12",
                "price_list_pack_cost_gbp": "54",
                "price_list_moq": "12",
                "cost_match_method": "supplier_sku_supplier_matched",
                "current_cost_confidence": "price_list_actual_match",
                "supplier_cost_review_reason": "",
                "expected_cost_source": "supplier_price_list_no_discount",
                "actual_paid_unit_cost_gbp": "5",
                "price_list_vs_actual_paid_delta_gbp": "-0.5",
                "price_list_vs_purchase_reference_delta_gbp": "-0.5",
            }
        ],
    )

    checks_df, health_df = build_restock_profit_checks(
        root=tmp_path,
        check_utc="2026-05-22T08:00:00Z",
        append_history=False,
    )
    by_sku = checks_df.set_index("seller_sku")

    assert by_sku.loc["SKU-BRIDGE-RESTOCK", "profit_proof_source"] == "legacy_sheet_profit_hint"
    assert "legacy_sheet_profit_not_native_proof" in by_sku.loc["SKU-BRIDGE-RESTOCK", "guardrail_flags"]
    assert by_sku.loc["SKU-BRIDGE-RESTOCK", "price_list_unit_cost_gbp"] == "4.5"
    assert by_sku.loc["SKU-BRIDGE-RESTOCK", "price_list_pack_size"] == "12"
    assert by_sku.loc["SKU-BRIDGE-RESTOCK", "cost_match_method"] == "supplier_sku_supplier_matched"
    assert "PK12 pack cost GBP 54 divided by 12 units" in by_sku.loc["SKU-BRIDGE-RESTOCK", "price_proof_summary"]
    assert "fresh list is GBP 0.5 cheaper than old paid" in by_sku.loc["SKU-BRIDGE-RESTOCK", "price_proof_summary"]
    assert by_sku.loc["SKU-BRIDGE-NODATA", "profit_verdict"] == "test_only"
    assert "no_data_test_only" in by_sku.loc["SKU-BRIDGE-NODATA", "guardrail_flags"]
    assert by_sku.loc["SKU-BRIDGE-NODATA-ZERO-COST", "profit_verdict"] == "missing_profit_inputs"
    assert "no_data_missing_cost_not_buy" in by_sku.loc["SKU-BRIDGE-NODATA-ZERO-COST", "guardrail_flags"]
    assert by_sku.loc["SKU-BRIDGE-DROP", "profit_verdict"] == "drop_review_only"
    assert "manual_sheet_drop_review" in by_sku.loc["SKU-BRIDGE-DROP", "guardrail_flags"]

    health = health_df.set_index("check_name")
    assert health.loc["legacy_sheet_profit_hint_rows", "status"] == "warn"
    assert health.loc["buy_candidates_without_native_profit_proof", "status"] == "warn"
    assert health.loc["current_price_list_cost_rows", "value"] == "1"
    assert health.loc["bridge_rows_with_current_price_list_cost", "value"] == "1"
    assert health.loc["market_refresh_candidates_ready", "value"] == "2"

    candidates = read_o_contract_df(tmp_path, "restock_market_refresh_candidates_live")
    candidate_by_sku = candidates.set_index("seller_sku")
    assert candidate_by_sku.loc["SKU-BRIDGE-RESTOCK", "candidate_status"] == "ready"
    assert "legacy_sheet_market_not_native" in candidate_by_sku.loc["SKU-BRIDGE-RESTOCK", "market_refresh_reason"]
    assert "missing_native_max_pay" in candidate_by_sku.loc["SKU-BRIDGE-RESTOCK", "market_refresh_reason"]
    assert candidate_by_sku.loc["SKU-BRIDGE-NODATA", "suggested_action"] == "test_restock"


def test_o021_price_variation_statuses_use_max_pay_without_auto_drop(tmp_path: Path) -> None:
    rows = [
        _rec_row("SKU-USUAL-UNDER-LIST", status="full_restock", cost="2", market="3", roi="25", profit="0.5", max_target="1.9"),
        _rec_row("SKU-LIST-OVER", status="full_restock", cost="2", market="3", roi="25", profit="0.5", max_target="1.9"),
        _rec_row("SKU-NO-LIST", status="full_restock", cost="1.5", market="3", roi="25", profit="0.5", max_target="1.9"),
        _rec_row("SKU-LIST-CHEAPER", status="full_restock", cost="1.5", market="3", roi="25", profit="0.5", max_target="1.9"),
    ]
    for row in rows:
        if row["seller_sku"] == "SKU-USUAL-UNDER-LIST":
            row["usual_paid_unit_cost_gbp"] = "1.7"
        if row["seller_sku"] == "SKU-LIST-OVER":
            row["usual_paid_unit_cost_gbp"] = ""
        if row["seller_sku"] == "SKU-NO-LIST":
            row["price_list_unit_cost_gbp"] = ""
            row["cost_match_method"] = ""
        if row["seller_sku"] == "SKU-LIST-CHEAPER":
            row["usual_paid_unit_cost_gbp"] = "2"

    _write_contract_rows(tmp_path, "restock_recommendations_live", rows)
    checks_df, _ = build_restock_profit_checks(
        root=tmp_path,
        check_utc="2026-05-22T08:00:00Z",
        append_history=False,
    )
    by_sku = checks_df.set_index("seller_sku")

    assert by_sku.loc["SKU-USUAL-UNDER-LIST", "price_status"] == "caution_usual_paid_under_list"
    assert by_sku.loc["SKU-USUAL-UNDER-LIST", "profit_verdict"] == "safe_to_review"
    assert by_sku.loc["SKU-LIST-OVER", "price_status"] == "over_max_snooze_candidate"
    assert by_sku.loc["SKU-LIST-OVER", "profit_verdict"] == "do_not_buy_now"
    assert by_sku.loc["SKU-LIST-OVER", "recommended_snooze_until_utc"] == "2026-05-29T00:00:00Z"
    assert by_sku.loc["SKU-NO-LIST", "price_status"] == "check_price"
    assert by_sku.loc["SKU-NO-LIST", "profit_verdict"] == "needs_price_check"
    assert by_sku.loc["SKU-LIST-CHEAPER", "price_status"] == "list_cheaper_than_usual_paid"
