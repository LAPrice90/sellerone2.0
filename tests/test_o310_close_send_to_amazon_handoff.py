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

from scripts.flows.O.O310_close_send_to_amazon_handoff import close_send_to_amazon_handoff
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
            }
        ]
    ).to_csv(headers_path, index=False)

    pd.DataFrame(
        [
            {
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "ordered_qty": "10",
                "ordered_unit_cost_gbp": "5",
                "supplier_pack_size": "1",
                "moq": "1",
                "receipt_status": "partial_received",
                "received_qty": "0",
                "remaining_open_qty": "10",
                "source_event_id": "evt-1",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "po_id": "PO-1",
                "po_line_id": "PO-1-L002",
                "seller_sku": "SKU-2",
                "asin": "ASIN-2",
                "ordered_qty": "5",
                "ordered_unit_cost_gbp": "4",
                "supplier_pack_size": "1",
                "moq": "1",
                "receipt_status": "partial_received",
                "received_qty": "0",
                "remaining_open_qty": "5",
                "source_event_id": "evt-2",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
            },
        ]
    ).to_csv(lines_path, index=False)


def _write_receiving_and_existing_handoff(tmp_path: Path) -> None:
    receiving_path = tmp_path / get_o_output_contract("receiving_events").rel_path
    handoff_log_path = tmp_path / get_o_output_contract("send_to_amazon_handoff_log").rel_path
    receiving_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T11:00:00Z",
                "event_id": "recv-1",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "received_qty": "5",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
            },
            {
                "event_utc": "2026-04-03T11:10:00Z",
                "event_id": "recv-2",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L002",
                "seller_sku": "SKU-2",
                "asin": "ASIN-2",
                "received_qty": "2",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
            },
        ]
    ).to_csv(receiving_path, index=False)

    pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T12:00:00Z",
                "event_id": "h-old",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "handoff_qty": "1",
                "shipment_ref": "SHIP-OLD",
                "handoff_status": "handoff_closed",
                "actor": "tester",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "source_event_id": "evt-1",
            }
        ]
    ).to_csv(handoff_log_path, index=False)


def _write_handoff_inbox(tmp_path: Path) -> None:
    inbox_path = tmp_path / get_o_output_contract("send_to_amazon_handoff_events").rel_path
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T13:00:00Z",
                "event_id": "h-partial",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "handoff_qty": "2",
                "shipment_ref": "SHIP-001",
                "handoff_status": "handoff_closed",
                "note": "partial handoff",
                "actor": "tester",
            },
            {
                "event_utc": "2026-04-03T13:01:00Z",
                "event_id": "h-over",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "handoff_qty": "3",
                "shipment_ref": "SHIP-001",
                "handoff_status": "handoff_closed",
                "note": "too much",
                "actor": "tester",
            },
            {
                "event_utc": "2026-04-03T13:02:00Z",
                "event_id": "h-full",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "handoff_qty": "2",
                "shipment_ref": "SHIP-001",
                "handoff_status": "handoff_closed",
                "note": "close line",
                "actor": "tester",
            },
            {
                "event_utc": "2026-04-03T13:03:00Z",
                "event_id": "h-old",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "handoff_qty": "1",
                "shipment_ref": "SHIP-001",
                "handoff_status": "handoff_closed",
                "note": "duplicate id",
                "actor": "tester",
            },
            {
                "event_utc": "2026-04-03T13:04:00Z",
                "event_id": "h-invalid",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L002",
                "seller_sku": "SKU-2",
                "handoff_qty": "0",
                "shipment_ref": "SHIP-002",
                "handoff_status": "handoff_closed",
                "note": "bad qty",
                "actor": "tester",
            },
            {
                "event_utc": "2026-04-03T13:05:00Z",
                "event_id": "h-missing",
                "po_id": "PO-X",
                "po_line_id": "PO-X-L001",
                "seller_sku": "SKU-X",
                "handoff_qty": "1",
                "shipment_ref": "SHIP-003",
                "handoff_status": "handoff_closed",
                "note": "missing line",
                "actor": "tester",
            },
            {
                "event_utc": "2026-04-03T13:06:00Z",
                "event_id": "h-fallback",
                "po_id": "PO-1",
                "po_line_id": "",
                "seller_sku": "SKU-2",
                "handoff_qty": "1",
                "shipment_ref": "SHIP-002",
                "handoff_status": "queued_for_shipment",
                "note": "fallback by po+sku",
                "actor": "tester",
            },
        ]
    ).to_csv(inbox_path, index=False)


def test_o310_applies_handoff_events_updates_queue_and_holds_invalid_rows(tmp_path: Path) -> None:
    _write_po_headers_and_lines(tmp_path)
    _write_receiving_and_existing_handoff(tmp_path)
    _write_handoff_inbox(tmp_path)

    append_df, full_log_df, holds_df, queue_df = close_send_to_amazon_handoff(
        root=tmp_path,
        applied_utc="2026-04-03T14:00:00Z",
    )

    assert len(append_df) == 3
    assert set(append_df["event_id"]) == {"h-partial", "h-full", "h-fallback"}
    assert len(full_log_df) == 4

    hold_reasons = set(holds_df["hold_reason"])
    assert "duplicate_event_id" in hold_reasons
    assert "invalid_handoff_qty" in hold_reasons
    assert "missing_po_line" in hold_reasons
    assert "over_handoff_qty" in hold_reasons

    fallback = append_df.loc[append_df["event_id"] == "h-fallback"].iloc[0]
    assert fallback["po_line_id"] == "PO-1-L002"
    assert fallback["seller_sku"] == "SKU-2"
    assert fallback["cost_mode"] == "test"
    assert fallback["recommendation_basis"] == "test_cost_snapshot"
    assert fallback["source_event_id"] == "evt-2"

    # line 1 received 5 and handed off 1(old)+2+2 = 5, so it should leave queue.
    # line 2 received 2 and handed off 1(fallback), so 1 remains open in queue.
    assert len(queue_df) == 1
    queue_row = queue_df.iloc[0]
    assert queue_row["po_line_id"] == "PO-1-L002"
    assert queue_row["received_qty_available_for_send"] == "1"
    assert queue_row["send_status"] == "partial_handoff_open"


def test_o310_second_run_is_idempotent_by_event_id(tmp_path: Path) -> None:
    _write_po_headers_and_lines(tmp_path)
    _write_receiving_and_existing_handoff(tmp_path)
    _write_handoff_inbox(tmp_path)

    _, first_full_log, _, _ = close_send_to_amazon_handoff(
        root=tmp_path,
        applied_utc="2026-04-03T14:00:00Z",
    )
    second_append, second_full_log, second_holds, second_queue = close_send_to_amazon_handoff(
        root=tmp_path,
        applied_utc="2026-04-03T14:10:00Z",
    )

    assert len(first_full_log) == 4
    assert len(second_append) == 0
    assert len(second_full_log) == 4
    assert "duplicate_event_id" in set(second_holds["hold_reason"])
    assert len(second_queue) == 1
    assert second_queue.iloc[0]["po_line_id"] == "PO-1-L002"
