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

from scripts.flows.O.O300_build_send_to_amazon_queue import build_send_to_amazon_queue
from scripts.flows.O._schemas import get_o_output_contract


def _write_po_headers_and_lines(tmp_path: Path) -> None:
    headers_path = tmp_path / get_o_output_contract("purchase_orders_live").rel_path
    lines_path = tmp_path / get_o_output_contract("purchase_order_lines_live").rel_path
    headers_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "po_id": "PO-1",
                "created_utc": "2026-04-03T10:00:00Z",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "po_status": "draft",
                "currency": "GBP",
                "total_lines": "2",
                "total_units": "15",
                "total_value_gbp": "70",
                "approved_from_decision_batch": "evt-1|evt-2",
            },
            {
                "po_id": "PO-2",
                "created_utc": "2026-04-03T10:05:00Z",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "po_status": "draft",
                "currency": "GBP",
                "total_lines": "2",
                "total_units": "7",
                "total_value_gbp": "20",
                "approved_from_decision_batch": "evt-3|evt-4",
            },
        ]
    ).to_csv(headers_path, index=False)

    pd.DataFrame(
        [
            {
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-READY",
                "asin": "ASIN-READY",
                "ordered_qty": "10",
                "ordered_unit_cost_gbp": "5",
                "supplier_pack_size": "1",
                "moq": "1",
                "receipt_status": "partial_received",
                "received_qty": "6",
                "remaining_open_qty": "4",
                "source_event_id": "evt-1",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "po_id": "PO-1",
                "po_line_id": "PO-1-L002",
                "seller_sku": "SKU-PARTIAL-HANDOFF",
                "asin": "ASIN-PARTIAL-HANDOFF",
                "ordered_qty": "5",
                "ordered_unit_cost_gbp": "4",
                "supplier_pack_size": "1",
                "moq": "1",
                "receipt_status": "full_received",
                "received_qty": "5",
                "remaining_open_qty": "0",
                "source_event_id": "evt-2",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
            },
            {
                "po_id": "PO-2",
                "po_line_id": "PO-2-L001",
                "seller_sku": "SKU-NOT-RECEIVED",
                "asin": "ASIN-NOT-RECEIVED",
                "ordered_qty": "4",
                "ordered_unit_cost_gbp": "3",
                "supplier_pack_size": "1",
                "moq": "1",
                "receipt_status": "not_received",
                "received_qty": "0",
                "remaining_open_qty": "4",
                "source_event_id": "evt-3",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "po_id": "PO-2",
                "po_line_id": "PO-2-L002",
                "seller_sku": "SKU-FULLY-HANDED",
                "asin": "ASIN-FULLY-HANDED",
                "ordered_qty": "3",
                "ordered_unit_cost_gbp": "3",
                "supplier_pack_size": "1",
                "moq": "1",
                "receipt_status": "full_received",
                "received_qty": "3",
                "remaining_open_qty": "0",
                "source_event_id": "evt-4",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ]
    ).to_csv(lines_path, index=False)


def _write_receiving_and_handoff(tmp_path: Path) -> None:
    receiving_path = tmp_path / get_o_output_contract("receiving_events").rel_path
    handoff_path = tmp_path / get_o_output_contract("send_to_amazon_handoff_log").rel_path
    receiving_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T11:00:00Z",
                "event_id": "recv-1",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-READY",
                "asin": "ASIN-READY",
                "received_qty": "6",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
            },
            {
                "event_utc": "2026-04-03T11:10:00Z",
                "event_id": "recv-2",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L002",
                "seller_sku": "SKU-PARTIAL-HANDOFF",
                "asin": "ASIN-PARTIAL-HANDOFF",
                "received_qty": "5",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
            },
            {
                "event_utc": "2026-04-03T11:20:00Z",
                "event_id": "recv-3",
                "po_id": "PO-2",
                "po_line_id": "PO-2-L002",
                "seller_sku": "SKU-FULLY-HANDED",
                "asin": "ASIN-FULLY-HANDED",
                "received_qty": "3",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
            },
        ]
    ).to_csv(receiving_path, index=False)

    pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T12:00:00Z",
                "event_id": "hnd-1",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L002",
                "seller_sku": "SKU-PARTIAL-HANDOFF",
                "asin": "ASIN-PARTIAL-HANDOFF",
                "handoff_qty": "2",
                "shipment_ref": "SHIP-001",
                "handoff_status": "handoff_closed",
                "actor": "tester",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "source_event_id": "evt-2",
            },
            {
                "event_utc": "2026-04-03T12:10:00Z",
                "event_id": "hnd-2",
                "po_id": "PO-2",
                "po_line_id": "PO-2-L002",
                "seller_sku": "SKU-FULLY-HANDED",
                "asin": "ASIN-FULLY-HANDED",
                "handoff_qty": "3",
                "shipment_ref": "SHIP-002",
                "handoff_status": "handoff_closed",
                "actor": "tester",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_event_id": "evt-4",
            },
        ]
    ).to_csv(handoff_path, index=False)


def test_o300_builds_queue_from_received_minus_handed_off_stock(tmp_path: Path) -> None:
    _write_po_headers_and_lines(tmp_path)
    _write_receiving_and_handoff(tmp_path)

    queue_df = build_send_to_amazon_queue(root=tmp_path, queue_utc="2026-04-03T13:00:00Z")

    assert len(queue_df) == 2
    assert set(queue_df["po_line_id"]) == {"PO-1-L001", "PO-1-L002"}
    assert "PO-2-L001" not in set(queue_df["po_line_id"])  # not received yet
    assert "PO-2-L002" not in set(queue_df["po_line_id"])  # already fully handed off

    by_line = queue_df.set_index("po_line_id")

    ready_row = by_line.loc["PO-1-L001"]
    assert ready_row["received_qty_available_for_send"] == "6"
    assert ready_row["total_received_qty"] == "6"
    assert ready_row["total_handed_off_qty"] == "0"
    assert ready_row["send_status"] == "ready_to_handoff"
    assert ready_row["queue_note"] == "received_stock_ready"
    assert ready_row["source_event_id"] == "evt-1"
    assert ready_row["cost_mode"] == "live"
    assert ready_row["recommendation_basis"] == "live_cost_inputs"

    partial_row = by_line.loc["PO-1-L002"]
    assert partial_row["received_qty_available_for_send"] == "3"
    assert partial_row["total_received_qty"] == "5"
    assert partial_row["total_handed_off_qty"] == "2"
    assert partial_row["send_status"] == "partial_handoff_open"
    assert partial_row["shipment_ref"] == "SHIP-001"
    assert partial_row["queue_note"] == "partial_handoff_remaining_qty"
    assert partial_row["source_event_id"] == "evt-2"
    assert partial_row["cost_mode"] == "test"
    assert partial_row["recommendation_basis"] == "test_cost_snapshot"
