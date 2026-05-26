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

from scripts.flows.O.O100_build_purchase_orders import build_purchase_orders
from scripts.flows.O._schemas import get_o_output_contract


def _write_sources(tmp_path: Path) -> None:
    rec_path = tmp_path / get_o_output_contract("restock_recommendations_live").rel_path
    src_path = tmp_path / get_o_output_contract("restock_source_view").rel_path
    decisions_path = tmp_path / get_o_output_contract("restock_decisions_log").rel_path
    rec_path.parent.mkdir(parents=True, exist_ok=True)

    rec_df = pd.DataFrame(
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "reason_codes": "ROI_OK",
                "recommended_qty_raw": "10",
                "recommended_qty_rounded": "10",
                "target_days_cover": "30",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "current_supplier_buy_cost_gbp": "5",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "8",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "60",
                "forward_profit_per_unit_gbp": "3",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-2",
                "asin": "ASIN-2",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "test_restock",
                "reason_codes": "ROI_MID_BAND",
                "recommended_qty_raw": "3",
                "recommended_qty_rounded": "3",
                "target_days_cover": "10",
                "days_cover_available_only": "2",
                "days_cover_total_pipeline": "2",
                "current_supplier_buy_cost_gbp": "4",
                "current_supplier_cost_source": "supplier_cost_snapshot_test",
                "market_price_gbp": "5",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "25",
                "forward_profit_per_unit_gbp": "1",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
            },
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-3",
                "asin": "ASIN-3",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "recommendation_status": "wait",
                "reason_codes": "ROI_BELOW_MIN_THRESHOLD",
                "recommended_qty_raw": "0",
                "recommended_qty_rounded": "0",
                "target_days_cover": "0",
                "days_cover_available_only": "20",
                "days_cover_total_pipeline": "20",
                "current_supplier_buy_cost_gbp": "6",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "6.2",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "3.3333",
                "forward_profit_per_unit_gbp": "0.2",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-5",
                "asin": "ASIN-5",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "recommendation_status": "test_restock",
                "reason_codes": "ROI_MID_BAND",
                "recommended_qty_raw": "5",
                "recommended_qty_rounded": "5",
                "target_days_cover": "10",
                "days_cover_available_only": "2",
                "days_cover_total_pipeline": "2",
                "current_supplier_buy_cost_gbp": "3",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "4",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "33.3333",
                "forward_profit_per_unit_gbp": "1",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-7",
                "asin": "ASIN-7",
                "supplier_code": "SUP-C",
                "supplier_name": "Gamma",
                "recommendation_status": "full_restock",
                "reason_codes": "ROI_OK",
                "recommended_qty_raw": "8",
                "recommended_qty_rounded": "8",
                "target_days_cover": "30",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "current_supplier_buy_cost_gbp": "7",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "9",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "28.57",
                "forward_profit_per_unit_gbp": "2",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ]
    )
    rec_df.to_csv(rec_path, index=False)

    src_df = pd.DataFrame(
        [
            {"seller_sku": "SKU-1", "asin": "ASIN-1", "supplier_code": "SUP-A", "supplier_name": "Alpha", "supplier_pack_size": "2", "moq": "4", "lead_time_days": "5"},
            {"seller_sku": "SKU-2", "asin": "ASIN-2", "supplier_code": "SUP-A", "supplier_name": "Alpha", "supplier_pack_size": "1", "moq": "1", "lead_time_days": "7"},
            {"seller_sku": "SKU-3", "asin": "ASIN-3", "supplier_code": "SUP-B", "supplier_name": "Beta", "supplier_pack_size": "1", "moq": "1", "lead_time_days": "10"},
            {"seller_sku": "SKU-5", "asin": "ASIN-5", "supplier_code": "SUP-B", "supplier_name": "Beta", "supplier_pack_size": "3", "moq": "6", "lead_time_days": "14"},
            {"seller_sku": "SKU-7", "asin": "ASIN-7", "supplier_code": "SUP-C", "supplier_name": "Gamma", "supplier_pack_size": "2", "moq": "2", "lead_time_days": "21"},
        ]
    )
    src_df.to_csv(src_path, index=False)

    decisions_df = pd.DataFrame(
        [
            # Latest decision for SKU-1 should be used as PO candidate.
            {
                "decision_utc": "2026-04-03T11:00:00Z",
                "event_utc": "2026-04-03T10:59:00Z",
                "event_id": "evt-1",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "decision_action": "approve_full_restock",
                "final_decision_status": "full_restock",
                "confirmed_unit_cost": "5",
                "confirmed_qty": "10",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            },
            # Older decision for SKU-2 should be ignored because later one exists.
            {
                "decision_utc": "2026-04-03T10:00:00Z",
                "event_utc": "2026-04-03T09:59:00Z",
                "event_id": "evt-2-old",
                "seller_sku": "SKU-2",
                "asin": "ASIN-2",
                "decision_action": "wait",
                "final_decision_status": "wait",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "source_reference": "test",
            },
            {
                "decision_utc": "2026-04-03T11:05:00Z",
                "event_utc": "2026-04-03T11:04:00Z",
                "event_id": "evt-2",
                "seller_sku": "SKU-2",
                "asin": "ASIN-2",
                "decision_action": "approve_test_restock",
                "final_decision_status": "test_restock",
                "confirmed_unit_cost": "4",
                "confirmed_qty": "3",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "source_reference": "test",
            },
            {
                "decision_utc": "2026-04-03T11:06:00Z",
                "event_utc": "2026-04-03T11:06:00Z",
                "event_id": "evt-3",
                "seller_sku": "SKU-3",
                "asin": "ASIN-3",
                "decision_action": "wait",
                "final_decision_status": "wait",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            },
            {
                "decision_utc": "2026-04-03T11:07:00Z",
                "event_utc": "2026-04-03T11:07:00Z",
                "event_id": "evt-4",
                "seller_sku": "SKU-4",
                "asin": "ASIN-4",
                "decision_action": "approve_test_restock",
                "final_decision_status": "test_restock",
                "confirmed_unit_cost": "2",
                "confirmed_qty": "5",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            },
            {
                "decision_utc": "2026-04-03T11:08:00Z",
                "event_utc": "2026-04-03T11:08:00Z",
                "event_id": "evt-5",
                "seller_sku": "SKU-5",
                "asin": "ASIN-5",
                "decision_action": "bulk_review",
                "final_decision_status": "bulk_review",
                "confirmed_unit_cost": "3",
                "confirmed_qty": "",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            },
            {
                "decision_utc": "2026-04-03T11:09:00Z",
                "event_utc": "2026-04-03T11:09:00Z",
                "event_id": "evt-6",
                "seller_sku": "SKU-6",
                "asin": "ASIN-6",
                "decision_action": "mystery_action",
                "final_decision_status": "mystery_action",
                "confirmed_unit_cost": "3",
                "confirmed_qty": "2",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            },
            {
                "decision_utc": "2026-04-03T11:10:00Z",
                "event_utc": "2026-04-03T11:10:00Z",
                "event_id": "evt-7",
                "seller_sku": "SKU-7",
                "asin": "ASIN-7",
                "decision_action": "approve_full_restock",
                "final_decision_status": "wait",
                "confirmed_unit_cost": "7",
                "confirmed_qty": "8",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            },
            {
                "decision_utc": "2026-04-03T11:11:00Z",
                "event_utc": "2026-04-03T11:11:00Z",
                "event_id": "evt-8",
                "seller_sku": "SKU-8",
                "asin": "ASIN-8",
                "decision_action": "snooze",
                "final_decision_status": "snooze",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            },
        ]
    )
    decisions_df.to_csv(decisions_path, index=False)


def test_o100_builds_po_drafts_groups_by_supplier_and_preserves_lineage(tmp_path: Path) -> None:
    _write_sources(tmp_path)

    headers_df, lines_df, holds_df = build_purchase_orders(
        root=tmp_path,
        build_utc="2026-04-03T12:00:00Z",
    )

    assert len(headers_df) == 1
    assert len(lines_df) == 2
    header = headers_df.iloc[0]
    assert header["supplier_code"] == "SUP-A"
    assert header["supplier_name"] == "Alpha"
    assert header["total_lines"] == "2"
    assert header["total_units"] == "13"
    assert header["total_value_gbp"] == "62"
    assert "evt-1" in header["approved_from_decision_batch"]
    assert "evt-2" in header["approved_from_decision_batch"]

    by_event = lines_df.set_index("source_event_id")
    line1 = by_event.loc["evt-1"]
    assert line1["seller_sku"] == "SKU-1"
    assert line1["ordered_qty"] == "10"
    assert line1["ordered_unit_cost_gbp"] == "5"
    assert line1["source_decision_action"] == "approve_full_restock"
    assert line1["cost_mode"] == "live"
    assert line1["recommendation_basis"] == "live_cost_inputs"
    assert line1["remaining_open_qty"] == "10"
    assert line1["ordered_supplier_packs"] == "5"

    line2 = by_event.loc["evt-2"]
    assert line2["seller_sku"] == "SKU-2"
    assert line2["ordered_qty"] == "3"
    assert line2["ordered_unit_cost_gbp"] == "4"
    assert line2["source_decision_action"] == "approve_test_restock"
    assert line2["cost_mode"] == "test"
    assert line2["recommendation_basis"] == "test_cost_snapshot"

    hold_reasons = set(holds_df["hold_reason"])
    assert "missing_supplier_identity" in hold_reasons
    assert "missing_confirmed_qty" in hold_reasons
    assert "unsupported_decision_action" in hold_reasons
    assert "final_status_not_buyable" in hold_reasons

    # Non-buy actions should be excluded cleanly rather than held.
    hold_events = set(holds_df["event_id"])
    assert "evt-3" not in hold_events  # wait
    assert "evt-8" not in hold_events  # snooze


def test_o100_holds_approved_decisions_not_in_supplier_pack_multiple(tmp_path: Path) -> None:
    _write_sources(tmp_path)

    rec_path = tmp_path / get_o_output_contract("restock_recommendations_live").rel_path
    src_path = tmp_path / get_o_output_contract("restock_source_view").rel_path
    decisions_path = tmp_path / get_o_output_contract("restock_decisions_log").rel_path

    rec_df = pd.read_csv(rec_path, dtype=str).fillna("")
    src_df = pd.read_csv(src_path, dtype=str).fillna("")
    decisions_df = pd.read_csv(decisions_path, dtype=str).fillna("")

    rec_df = pd.concat(
        [
            rec_df,
            pd.DataFrame(
                [
                    {
                        "asof_utc": "2026-04-03T10:00:00Z",
                        "seller_sku": "SKU-PK12",
                        "asin": "ASIN-PK12",
                        "supplier_code": "SUP-A",
                        "supplier_name": "Alpha",
                        "recommendation_status": "full_restock",
                        "reason_codes": "ROI_OK",
                        "recommended_qty_raw": "18",
                        "recommended_qty_rounded": "24",
                        "current_supplier_buy_cost_gbp": "3.33",
                        "cost_mode": "live",
                        "recommendation_basis": "live_cost_inputs",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    src_df = pd.concat(
        [
            src_df,
            pd.DataFrame(
                [
                    {
                        "seller_sku": "SKU-PK12",
                        "asin": "ASIN-PK12",
                        "supplier_code": "SUP-A",
                        "supplier_name": "Alpha",
                        "supplier_pack_size": "12",
                        "moq": "12",
                        "valid_order_step": "12",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    decisions_df = pd.concat(
        [
            decisions_df,
            pd.DataFrame(
                [
                    {
                        "decision_utc": "2026-04-03T11:30:00Z",
                        "event_utc": "2026-04-03T11:29:00Z",
                        "event_id": "evt-pk12-bad",
                        "seller_sku": "SKU-PK12",
                        "asin": "ASIN-PK12",
                        "decision_action": "approve_full_restock",
                        "final_decision_status": "full_restock",
                        "confirmed_unit_cost": "3.33",
                        "confirmed_qty": "18",
                        "recommendation_asof_utc": "2026-04-03T10:00:00Z",
                        "cost_mode": "live",
                        "recommendation_basis": "live_cost_inputs",
                        "source_reference": "test",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    rec_df.to_csv(rec_path, index=False)
    src_df.to_csv(src_path, index=False)
    decisions_df.to_csv(decisions_path, index=False)

    _, lines_df, holds_df = build_purchase_orders(root=tmp_path, build_utc="2026-04-03T12:00:00Z")

    assert "SKU-PK12" not in set(lines_df.get("seller_sku", pd.Series(dtype=str)))
    hold = holds_df[holds_df["event_id"] == "evt-pk12-bad"].iloc[0]
    assert hold["hold_reason"] == "confirmed_qty_not_pack_multiple"
    assert "multiples of 12" in hold["hold_note"]


def test_o100_builds_po_draft_from_legacy_bridge_decision(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "O" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "bridge_utc": "2026-05-22T10:00:00Z",
                "source_system": "legacy_purchase_list",
                "source_sheet_id": "sheet-1",
                "source_sheet_title": "Amazon Supplier Process",
                "source_tab": "Purchase List",
                "source_row_number": "20",
                "source_reference": "legacy_purchase_list:sheet-1:Purchase List:row20",
                "supplier_name": "Bridge Supplier",
                "supplier_code": "",
                "seller_sku": "SKU-BRIDGE-PO",
                "asin": "ASIN-BRIDGE-PO",
                "title": "Bridge PO Product",
                "display_qtys_label": "Unit",
                "barcode": "7777777777777",
                "supplier_sku": "BR-SUP-20",
                "suggested_action": "full_restock",
                "recommendation_status": "full_restock",
                "sheet_recommend_label": "Restock",
                "suggested_qty": "6",
                "recommended_qty_rounded": "6",
                "current_supplier_buy_cost_gbp": "4",
                "suggested_unit_cost_gbp": "4",
                "suggested_market_price_gbp": "7",
                "market_price_gbp": "7",
                "expected_forward_roi_pct": "75",
                "forward_roi_pct": "75",
                "forward_profit_per_unit_gbp": "3",
                "queue_status": "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_restock",
                "bridge_status": "ready",
                "bridge_note": "LEGACY_PURCHASE_LIST_RESTOCK|NATIVE_O_PARITY_PENDING",
                "reason_codes": "LEGACY_PURCHASE_LIST_RESTOCK|NATIVE_O_PARITY_PENDING",
            }
        ]
    ).to_csv(live_dir / "legacy_purchase_list_bridge.csv", index=False)
    pd.DataFrame(
        [
            {
                "asof_utc": "2026-05-22T09:00:00Z",
                "seller_sku": "SKU-BRIDGE-PO",
                "asin": "ASIN-BRIDGE-PO",
                "supplier_code": "BR-SUP-20",
                "supplier_name": "Native Stale Supplier",
                "recommendation_status": "wait",
                "reason_codes": "NATIVE_O_PARITY_PENDING",
                "recommended_qty_raw": "0",
                "recommended_qty_rounded": "0",
                "target_days_cover": "0",
                "days_cover_available_only": "99",
                "days_cover_total_pipeline": "99",
                "current_supplier_buy_cost_gbp": "9",
                "current_supplier_cost_source": "native_stale",
                "market_price_gbp": "10",
                "market_price_basis_used": "native_stale",
                "forward_roi_pct": "1",
                "forward_profit_per_unit_gbp": "1",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            }
        ]
    ).to_csv(live_dir / "restock_recommendations_live.csv", index=False)
    pd.DataFrame(
        [
            {
                "decision_utc": "2026-05-22T10:20:00Z",
                "event_utc": "2026-05-22T10:15:00Z",
                "event_id": "evt-bridge-po",
                "seller_sku": "SKU-BRIDGE-PO",
                "asin": "ASIN-BRIDGE-PO",
                "original_recommendation_status": "full_restock",
                "original_recommendation_reason": "LEGACY_PURCHASE_LIST_RESTOCK",
                "decision_action": "approve_full_restock",
                "final_decision_status": "full_restock",
                "confirmed_unit_cost": "4",
                "confirmed_qty": "6",
                "recalculated_forward_roi_pct": "75",
                "decision_note": "bridge approve",
                "snooze_until_utc": "",
                "actor": "tester",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_restock",
                "recommendation_asof_utc": "2026-05-22T10:00:00Z",
                "source_reference": "o_ui_supplier_batch:Bridge Supplier|legacy_purchase_list|legacy_purchase_list:sheet-1:Purchase List:row20",
            }
        ]
    ).to_csv(live_dir / "restock_decisions_log.csv", index=False)

    headers_df, lines_df, holds_df = build_purchase_orders(
        root=tmp_path,
        build_utc="2026-05-22T10:30:00Z",
    )

    assert holds_df.empty
    assert len(headers_df) == 1
    assert len(lines_df) == 1
    header = headers_df.iloc[0]
    assert header["supplier_code"] == ""
    assert header["supplier_name"] == "Bridge Supplier"
    assert header["total_units"] == "6"
    assert header["total_value_gbp"] == "24"

    line = lines_df.iloc[0]
    assert line["seller_sku"] == "SKU-BRIDGE-PO"
    assert line["ordered_qty"] == "6"
    assert line["ordered_unit_cost_gbp"] == "4"
    assert line["title"] == "Bridge PO Product"
    assert line["supplier_sku"] == "BR-SUP-20"
    assert line["barcode"] == "7777777777777"
    assert line["source_bridge_row"] == "20"
    assert line["source_bridge_reference"] == "legacy_purchase_list:sheet-1:Purchase List:row20"
    assert line["cost_mode"] == "legacy_sheet"


def test_o100_rounds_special_sika_pack_to_supplier_boxes(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "O" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "asof_utc": "2026-05-19T12:00:00Z",
                "seller_sku": "SIKA-20G-PACK3",
                "asin": "B06WW79DX5",
                "supplier_code": "484651",
                "supplier_name": "Sika",
                "recommendation_status": "full_restock",
                "reason_codes": "ROI_OK",
                "recommended_qty_raw": "167",
                "recommended_qty_rounded": "167",
                "target_days_cover": "30",
                "days_cover_available_only": "8",
                "days_cover_total_pipeline": "22",
                "current_supplier_buy_cost_gbp": "4.35",
                "current_supplier_cost_source": "supplier_buy_cost_truth_pack_converted",
                "market_price_gbp": "6.98",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "60.45977",
                "forward_profit_per_unit_gbp": "2.63",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            }
        ]
    ).to_csv(live_dir / "restock_recommendations_live.csv", index=False)

    pd.DataFrame(
        [
            {
                "seller_sku": "SIKA-20G-PACK3",
                "asin": "B06WW79DX5",
                "supplier_code": "484651",
                "supplier_name": "Sika",
                "supplier_pack_size": "1",
                "moq": "1",
                "lead_time_days": "7",
                "components_per_sell_pack": "3",
                "component_unit_label": "bottle",
                "supplier_cost_basis": "component_unit",
                "supplier_box_components": "25",
                "preferred_order_sell_packs": "250",
                "preferred_order_components": "750",
                "preferred_supplier_boxes": "30",
                "quantity_strategy": "preferred_carton_multiple",
                "hazmat_group": "sika_glue",
                "isolate_from_normal_po": "1",
                "target_carton_weight_kg": "23",
                "pack_profile_status": "confirmed",
                "pack_conversion_note": "20g bottles; buy 30 boxes of 25 = 750 bottles = 250 Amazon packs",
            }
        ]
    ).to_csv(live_dir / "restock_source_view.csv", index=False)

    pd.DataFrame(
        [
            {
                "decision_utc": "2026-05-19T13:00:00Z",
                "event_utc": "2026-05-19T12:59:00Z",
                "event_id": "evt-sika",
                "seller_sku": "SIKA-20G-PACK3",
                "asin": "B06WW79DX5",
                "decision_action": "approve_full_restock",
                "final_decision_status": "full_restock",
                "confirmed_unit_cost": "4.35",
                "confirmed_qty": "167",
                "recommendation_asof_utc": "2026-05-19T12:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            }
        ]
    ).to_csv(live_dir / "restock_decisions_log.csv", index=False)

    headers_df, lines_df, holds_df = build_purchase_orders(
        root=tmp_path,
        build_utc="2026-05-19T13:30:00Z",
    )

    assert holds_df.empty
    assert len(headers_df) == 1
    assert len(lines_df) == 1

    header = headers_df.iloc[0]
    assert header["supplier_code"] == "484651"
    assert header["supplier_name"] == "Sika"
    assert header["total_units"] == "250"
    assert header["total_value_gbp"] == "1087.5"
    assert "isolated_special_order:sika_glue" in header["po_notes"]
    assert "total_components:750" in header["po_notes"]

    line = lines_df.iloc[0]
    assert line["ordered_qty"] == "250"
    assert line["requested_sell_packs"] == "167"
    assert line["ordered_sell_packs"] == "250"
    assert line["components_per_sell_pack"] == "3"
    assert line["component_unit_label"] == "bottle"
    assert line["ordered_components"] == "750"
    assert line["supplier_box_components"] == "25"
    assert line["ordered_supplier_boxes"] == "30"
    assert line["quantity_strategy"] == "preferred_carton_multiple"
    assert line["hazmat_group"] == "sika_glue"
    assert line["isolate_from_normal_po"] == "1"


def test_o100_holds_approved_decisions_when_pack_profile_is_not_safe(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "O" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    rec_rows = []
    source_rows = []
    decision_rows = []
    statuses = {
        "SKU-MISSING-PACK": ("missing_pack_profile", "missing_pack_profile"),
        "SKU-PENDING-PACK": ("pending", "unconfirmed_pack_profile"),
        "SKU-INVALID-PACK": ("invalid", "invalid_component_conversion"),
    }
    for index, (sku, (status, source_note)) in enumerate(statuses.items(), start=1):
        asin = f"ASIN-PACK-{index}"
        rec_rows.append(
            {
                "asof_utc": "2026-05-19T12:00:00Z",
                "seller_sku": sku,
                "asin": asin,
                "supplier_code": "SIKA",
                "supplier_name": "Sika",
                "recommendation_status": "full_restock",
                "reason_codes": "ROI_OK",
                "recommended_qty_raw": "20",
                "recommended_qty_rounded": "20",
                "target_days_cover": "30",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "current_supplier_buy_cost_gbp": "4.35",
                "current_supplier_cost_source": "supplier_catalog_price_converted_to_sell_pack",
                "market_price_gbp": "9",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "106.896552",
                "forward_profit_per_unit_gbp": "4.65",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            }
        )
        source_rows.append(
            {
                "seller_sku": sku,
                "asin": asin,
                "supplier_code": "SIKA",
                "supplier_name": "Sika",
                "supplier_pack_size": "1",
                "moq": "1",
                "lead_time_days": "7",
                "components_per_sell_pack": "3",
                "component_unit_label": "bottle",
                "supplier_cost_basis": "component_unit",
                "supplier_box_components": "25",
                "preferred_order_sell_packs": "250",
                "preferred_order_components": "750",
                "preferred_supplier_boxes": "30",
                "quantity_strategy": "preferred_carton_multiple",
                "hazmat_group": "sika_glue",
                "isolate_from_normal_po": "1",
                "target_carton_weight_kg": "23",
                "pack_profile_status": status,
                "source_notes": source_note,
            }
        )
        decision_rows.append(
            {
                "decision_utc": "2026-05-19T13:00:00Z",
                "event_utc": "2026-05-19T12:59:00Z",
                "event_id": f"evt-pack-{index}",
                "seller_sku": sku,
                "asin": asin,
                "decision_action": "approve_full_restock",
                "final_decision_status": "full_restock",
                "confirmed_unit_cost": "4.35",
                "confirmed_qty": "20",
                "recommendation_asof_utc": "2026-05-19T12:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            }
        )

    pd.DataFrame(rec_rows).to_csv(live_dir / "restock_recommendations_live.csv", index=False)
    pd.DataFrame(source_rows).to_csv(live_dir / "restock_source_view.csv", index=False)
    pd.DataFrame(decision_rows).to_csv(live_dir / "restock_decisions_log.csv", index=False)

    headers_df, lines_df, holds_df = build_purchase_orders(
        root=tmp_path,
        build_utc="2026-05-19T13:30:00Z",
    )

    assert headers_df.empty
    assert lines_df.empty
    assert len(holds_df) == 3
    hold_reasons = set(holds_df["hold_reason"])
    assert "missing_pack_profile" in hold_reasons
    assert "unconfirmed_pack_profile" in hold_reasons
    assert "invalid_pack_profile" in hold_reasons


def test_o100_holds_pack_blocker_from_recommendation_when_source_row_is_missing(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "O" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "asof_utc": "2026-05-19T12:00:00Z",
                "seller_sku": "SKU-REC-ONLY-PACK",
                "asin": "ASIN-REC-ONLY-PACK",
                "supplier_code": "SIKA",
                "supplier_name": "Sika",
                "recommendation_status": "full_restock",
                "reason_codes": "PACK_PROFILE_MISSING,SPECIAL_ORDER_PROFILE_REQUIRED",
                "recommended_qty_raw": "20",
                "recommended_qty_rounded": "20",
                "target_days_cover": "30",
                "days_cover_available_only": "0",
                "days_cover_total_pipeline": "0",
                "current_supplier_buy_cost_gbp": "4.35",
                "current_supplier_cost_source": "supplier_catalog_price_converted_to_sell_pack",
                "market_price_gbp": "9",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "106.896552",
                "forward_profit_per_unit_gbp": "4.65",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "components_per_sell_pack": "1",
                "supplier_cost_basis": "sell_pack",
                "pack_profile_status": "",
            }
        ]
    ).to_csv(live_dir / "restock_recommendations_live.csv", index=False)
    pd.DataFrame(columns=get_o_output_contract("restock_source_view").required_columns).to_csv(
        live_dir / "restock_source_view.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "decision_utc": "2026-05-19T13:00:00Z",
                "event_utc": "2026-05-19T12:59:00Z",
                "event_id": "evt-rec-only-pack",
                "seller_sku": "SKU-REC-ONLY-PACK",
                "asin": "ASIN-REC-ONLY-PACK",
                "decision_action": "approve_full_restock",
                "final_decision_status": "full_restock",
                "confirmed_unit_cost": "4.35",
                "confirmed_qty": "20",
                "recommendation_asof_utc": "2026-05-19T12:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_reference": "test",
            }
        ]
    ).to_csv(live_dir / "restock_decisions_log.csv", index=False)

    headers_df, lines_df, holds_df = build_purchase_orders(
        root=tmp_path,
        build_utc="2026-05-19T13:30:00Z",
    )

    assert headers_df.empty
    assert lines_df.empty
    assert len(holds_df) == 1
    assert holds_df.iloc[0]["hold_reason"] == "missing_pack_profile"


def test_o100_holds_over_max_price_safety_decision(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "O" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "asof_utc": "2026-05-22T10:00:00Z",
                "seller_sku": "SKU-OVER-MAX-PO",
                "asin": "ASIN-OVER-MAX-PO",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "recommendation_status": "full_restock",
                "reason_codes": "ROI_OK",
                "recommended_qty_raw": "2",
                "recommended_qty_rounded": "2",
                "target_days_cover": "30",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "current_supplier_buy_cost_gbp": "2",
                "current_supplier_cost_source": "supplier_price_list",
                "market_price_gbp": "3",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "20",
                "forward_profit_per_unit_gbp": "0.4",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            }
        ]
    ).to_csv(live_dir / "restock_recommendations_live.csv", index=False)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-OVER-MAX-PO",
                "asin": "ASIN-OVER-MAX-PO",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "supplier_pack_size": "1",
                "moq": "1",
            }
        ]
    ).to_csv(live_dir / "restock_source_view.csv", index=False)
    pd.DataFrame(
        [
            {
                "decision_utc": "2026-05-22T11:00:00Z",
                "event_utc": "2026-05-22T10:59:00Z",
                "event_id": "evt-over-max-po",
                "seller_sku": "SKU-OVER-MAX-PO",
                "asin": "ASIN-OVER-MAX-PO",
                "decision_action": "approve_full_restock",
                "final_decision_status": "full_restock",
                "confirmed_unit_cost": "2",
                "confirmed_qty": "2",
                "recommendation_asof_utc": "2026-05-22T10:00:00Z",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "confirmed_price_safety_status": "confirmed_over_max_blocked",
                "max_safe_unit_cost_gbp": "1.9",
            }
        ]
    ).to_csv(live_dir / "restock_decisions_log.csv", index=False)

    headers_df, lines_df, holds_df = build_purchase_orders(root=tmp_path, build_utc="2026-05-22T12:00:00Z")

    assert headers_df.empty
    assert lines_df.empty
    assert len(holds_df.index) == 1
    assert holds_df.iloc[0]["hold_reason"] == "price_safety_blocked"
