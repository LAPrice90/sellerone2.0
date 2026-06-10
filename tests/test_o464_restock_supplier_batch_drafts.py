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
from scripts.flows.O.O462_restock_session_draft_decisions import submit_restock_session_draft_decision
from scripts.flows.O.O464_build_restock_supplier_batch_drafts import build_restock_supplier_batch_drafts
from scripts.flows.O.O466_restock_supplier_proof_events import submit_restock_session_supplier_proof_event
from scripts.flows.O.O468_restock_pack_moq_proof_events import submit_restock_session_pack_moq_proof_event
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-02T20:55:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _write_batch_source(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": OBSERVED,
                "seller_sku": "SKU-BATCH",
                "asin": "ASIN-BATCH",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_30d": "2",
                "current_supplier_buy_cost_gbp": "3.50",
                "current_supplier_cost_source": "supplier_price_list",
                "market_price_gbp": "10",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "net_fee_model_status": "fresh",
                "components_per_sell_pack": "1",
                "supplier_cost_basis": "unit",
                "component_unit_label": "Unit",
                "expected_sell_pack_cost_gbp": "3.50",
                "expected_component_cost_gbp": "3.50",
                "quantity_strategy": "raw_units",
                "preferred_order_sell_packs": "3",
                "preferred_order_components": "3",
                "preferred_supplier_boxes": "0",
                "supplier_box_components": "0",
                "pack_profile_status": "ok",
                "source_inventory_asof": OBSERVED,
                "source_velocity_asof": OBSERVED,
                "source_performance_asof": OBSERVED,
                "title": "Batch Product",
                "supplier_sku": "SUP-BATCH",
                "barcode": "1234567890123",
                "cost_match_method": "supplier_sku_supplier_matched",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": OBSERVED,
                "seller_sku": "SKU-BATCH",
                "asin": "ASIN-BATCH",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "recommendation_status": "test_restock",
                "suggested_qty": "3",
                "suggested_unit_cost_gbp": "3.50",
                "suggested_market_price_gbp": "10",
                "expected_forward_roi_pct": "30",
                "expected_forward_profit_per_unit_gbp": "2",
                "reason_codes": "ROI_OK",
                "queue_status": "ready",
            }
        ],
    )


def test_o464_builds_supplier_batch_draft_from_saved_order_qty(tmp_path: Path) -> None:
    _write_batch_source(tmp_path)
    review_df, _summary_df, _reason_df, _health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
    )
    session_row = review_df.iloc[0].to_dict()
    submit_restock_session_draft_decision(
        root=tmp_path,
        session_row=session_row,
        decision_code="order_qty_draft",
        draft_order_qty="5",
        decision_note="draft batch qty",
        actor="operator_ui",
        event_source_reference="test",
    )

    lines_df, summary_df, health_df = build_restock_supplier_batch_drafts(
        root=tmp_path,
        batch_utc=OBSERVED,
    )

    assert len(lines_df.index) == 1
    line = lines_df.iloc[0]
    assert line["seller_sku"] == "SKU-BATCH"
    assert line["draft_order_qty"] == "5"
    assert line["draft_line_value_gbp"] == "17.5"
    assert line["line_state"] == "review_only_blocked"
    assert line["creates_live_action"] == "0"
    assert line["supplier_proof_checklist_status"] == "needs_supplier_proof"
    assert "supplier_stock_not_verified" in line["supplier_proof_missing_reasons"]
    assert "backorder_not_verified" in line["supplier_proof_missing_reasons"]
    assert "supplier_file_asof_missing" in line["supplier_proof_missing_reasons"]
    assert line["supplier_batch_readiness_state"] == "blocked_from_purchase_approval"
    assert "supplier_proof:supplier_stock_not_verified" in line["supplier_batch_readiness_reasons"]
    assert line["supplier_match_state"] == "exact_supplier_sku_or_barcode_match"
    assert line["supplier_cost_proof_state"] == "supplier_cost_verified"
    assert len(summary_df.index) == 1
    summary = summary_df.iloc[0]
    assert summary["line_count"] == "1"
    assert summary["draft_order_qty_total"] == "5"
    assert summary["draft_order_value_gbp"] == "17.5"
    assert summary["creates_live_action"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}

    written = read_o_contract_df(tmp_path, "restock_session_supplier_batch_lines_live")
    assert len(written.index) == 1


def test_o464_merges_supplier_proof_events_into_batch_line(tmp_path: Path) -> None:
    _write_batch_source(tmp_path)
    review_df, _summary_df, _reason_df, _health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
    )
    session_row = review_df.iloc[0].to_dict()
    submit_restock_session_draft_decision(
        root=tmp_path,
        session_row=session_row,
        decision_code="order_qty_draft",
        draft_order_qty="5",
        decision_note="draft batch qty",
        actor="operator_ui",
        event_source_reference="test",
    )
    saved_proof = submit_restock_session_supplier_proof_event(
        root=tmp_path,
        session_row=session_row,
        supplier_stock_state="supplier_stock_verified_in_stock",
        supplier_stock_qty="8",
        backorder_state="backorder_none_confirmed",
        supplier_file_asof_utc="2026-06-02",
        supplier_file_reference="supplier-file.csv",
        proof_note="checked file",
        actor="operator_ui",
        event_source_reference="test",
    )

    lines_df, _summary_df, health_df = build_restock_supplier_batch_drafts(
        root=tmp_path,
        batch_utc=OBSERVED,
    )

    assert len(lines_df.index) == 1
    line = lines_df.iloc[0]
    assert line["supplier_stock_state"] == "supplier_stock_verified_in_stock"
    assert line["supplier_stock_qty"] == "8"
    assert line["backorder_state"] == "backorder_none_confirmed"
    assert line["supplier_file_asof_utc"] == "2026-06-02T00:00:00Z"
    assert line["supplier_file_reference"] == "supplier-file.csv"
    assert line["latest_supplier_proof_id"] == saved_proof["proof_id"]
    assert line["latest_supplier_proof_note"] == "checked file"
    assert line["supplier_proof_checklist_status"] == "supplier_proof_clear"
    assert line["supplier_proof_missing_reasons"] == ""
    assert line["supplier_batch_readiness_state"] == "blocked_from_purchase_approval"
    assert "line_state:review_only_blocked" in line["supplier_batch_readiness_reasons"]
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o464_merges_pack_moq_proof_events_into_batch_line(tmp_path: Path) -> None:
    _write_batch_source(tmp_path)
    review_df, _summary_df, _reason_df, _health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
    )
    session_row = review_df.iloc[0].to_dict()
    submit_restock_session_draft_decision(
        root=tmp_path,
        session_row=session_row,
        decision_code="order_qty_draft",
        draft_order_qty="12",
        decision_note="draft batch qty",
        actor="operator_ui",
        event_source_reference="test",
    )
    saved_proof = submit_restock_session_pack_moq_proof_event(
        root=tmp_path,
        session_row=session_row,
        pack_moq_proof_state="pack_moq_verified",
        pack_multiple="6",
        supplier_moq="12",
        valid_order_step="6",
        proof_file_reference="pack-file.csv",
        proof_note="checked pack",
        actor="operator_ui",
        event_source_reference="test",
    )

    lines_df, summary_df, health_df = build_restock_supplier_batch_drafts(
        root=tmp_path,
        batch_utc=OBSERVED,
    )

    assert len(lines_df.index) == 1
    line = lines_df.iloc[0]
    assert line["pack_moq_proof_state"] == "pack_moq_verified"
    assert line["pack_multiple"] == "6"
    assert line["supplier_moq"] == "12"
    assert line["valid_order_step"] == "6"
    assert line["latest_pack_moq_proof_id"] == saved_proof["proof_id"]
    assert line["latest_pack_moq_proof_file_reference"] == "pack-file.csv"
    assert line["supplier_batch_readiness_state"] == "blocked_from_purchase_approval"
    assert "supplier_proof:supplier_stock_not_verified" in line["supplier_batch_readiness_reasons"]
    assert summary_df.iloc[0]["blocked_readiness_line_count"] == "1"
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o464_marks_line_ready_for_purchase_approval_review_only_when_all_proof_is_clear(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_session_review_live",
        [
            {
                "session_utc": OBSERVED,
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:native_o:supplier:ready",
                "source_class": "native_o",
                "source_system": "native_o",
                "source_reference": "native_o:SKU-READY",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "seller_sku": "SKU-READY",
                "asin": "ASIN-READY",
                "title": "Ready Product",
                "supplier_sku": "SUP-READY",
                "barcode": "1234567890123",
                "old_suggested_qty": "6",
                "order_qty_draft": "6",
                "current_supplier_cost_gbp": "3.50",
                "supplier_proof_state": "supplier_exact_match_proved",
                "supplier_match_state": "exact_supplier_sku_or_barcode_match",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "backorder_state": "backorder_none_confirmed",
                "supplier_file_asof_utc": OBSERVED,
                "supplier_cost_proof_state": "supplier_cost_verified",
                "pack_moq_proof_state": "pack_moq_verified",
                "pack_multiple": "6",
                "supplier_moq": "6",
                "valid_order_step": "6",
                "supplier_order_viability_state": "review_only_not_po",
                "action_safety_state": "clean_review_ready_not_po",
                "row_status": "review_only",
                "latest_draft_id": "draft-ready",
                "latest_draft_utc": OBSERVED,
                "latest_draft_decision_code": "order_qty_draft",
            }
        ],
    )

    lines_df, summary_df, health_df = build_restock_supplier_batch_drafts(
        root=tmp_path,
        batch_utc=OBSERVED,
        refresh_session=False,
    )

    assert len(lines_df.index) == 1
    line = lines_df.iloc[0]
    assert line["line_state"] == "review_only_ready"
    assert line["supplier_proof_checklist_status"] == "supplier_proof_clear"
    assert line["supplier_batch_readiness_state"] == "ready_for_purchase_approval_review_only"
    assert line["supplier_batch_readiness_reasons"] == ""
    assert line["creates_live_action"] == "0"
    assert summary_df.iloc[0]["ready_for_purchase_approval_line_count"] == "1"
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o464_excludes_non_quantity_draft_decisions_from_supplier_batch(tmp_path: Path) -> None:
    _write_batch_source(tmp_path)
    review_df, _summary_df, _reason_df, _health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
    )
    submit_restock_session_draft_decision(
        root=tmp_path,
        session_row=review_df.iloc[0].to_dict(),
        decision_code="drop",
        decision_note="not buying",
        actor="operator_ui",
        event_source_reference="test",
    )

    lines_df, summary_df, health_df = build_restock_supplier_batch_drafts(
        root=tmp_path,
        batch_utc=OBSERVED,
    )

    assert lines_df.empty
    assert summary_df.empty
    assert set(health_df["status"].tolist()) == {"ok"}
