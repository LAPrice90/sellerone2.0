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

from scripts.flows.O.O200_build_ordered_stock_state import build_ordered_stock_state
from scripts.flows.O._schemas import get_o_output_contract


def _write_headers_and_lines(tmp_path: Path) -> None:
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
                "total_value_gbp": "65",
                "approved_from_decision_batch": "evt-1|evt-2",
            },
            {
                "po_id": "PO-2",
                "created_utc": "2026-04-03T10:00:00Z",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "po_status": "draft",
                "currency": "GBP",
                "total_lines": "1",
                "total_units": "4",
                "total_value_gbp": "12",
                "approved_from_decision_batch": "evt-3",
            },
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
                "supplier_pack_size": "2",
                "moq": "4",
                "receipt_status": "not_received",
                "received_qty": "0",
                "remaining_open_qty": "10",
                "expected_arrival_utc": "2026-04-10T00:00:00Z",
                "backorder_flag": "0",
                "source_event_id": "evt-1",
                "source_decision_action": "approve_full_restock",
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
                "receipt_status": "not_received",
                "received_qty": "0",
                "remaining_open_qty": "5",
                "expected_arrival_utc": "2026-04-11T00:00:00Z",
                "backorder_flag": "0",
                "source_event_id": "evt-2",
                "source_decision_action": "approve_test_restock",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
            },
            {
                "po_id": "PO-2",
                "po_line_id": "PO-2-L001",
                "seller_sku": "SKU-3",
                "asin": "ASIN-3",
                "ordered_qty": "4",
                "ordered_unit_cost_gbp": "3",
                "supplier_pack_size": "1",
                "moq": "1",
                "receipt_status": "not_received",
                "received_qty": "0",
                "remaining_open_qty": "4",
                "expected_arrival_utc": "2026-04-12T00:00:00Z",
                "backorder_flag": "1",
                "source_event_id": "evt-3",
                "source_decision_action": "approve_test_restock",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ]
    ).to_csv(lines_path, index=False)


def _write_receiving_events(tmp_path: Path) -> None:
    path = tmp_path / get_o_output_contract("receiving_events").rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            # line1 fully received
            {"event_utc": "2026-04-03T11:00:00Z", "event_id": "r1", "po_id": "PO-1", "po_line_id": "PO-1-L001", "seller_sku": "SKU-1", "asin": "ASIN-1", "received_qty": "3", "warehouse_ref": "WH-A", "event_source": "manual", "note": "", "actor": "tester"},
            {"event_utc": "2026-04-03T11:10:00Z", "event_id": "r2", "po_id": "PO-1", "po_line_id": "PO-1-L001", "seller_sku": "SKU-1", "asin": "ASIN-1", "received_qty": "7", "warehouse_ref": "WH-A", "event_source": "manual", "note": "", "actor": "tester"},
            # line2 partial
            {"event_utc": "2026-04-03T11:20:00Z", "event_id": "r3", "po_id": "PO-1", "po_line_id": "PO-1-L002", "seller_sku": "SKU-2", "asin": "ASIN-2", "received_qty": "2", "warehouse_ref": "WH-A", "event_source": "manual", "note": "", "actor": "tester"},
        ]
    ).to_csv(path, index=False)


def test_o200_builds_open_ordered_stock_state_from_lines_and_receipts(tmp_path: Path) -> None:
    _write_headers_and_lines(tmp_path)
    _write_receiving_events(tmp_path)

    out_df = build_ordered_stock_state(
        root=tmp_path,
        asof_utc="2026-04-03T12:00:00Z",
    )

    # line1 is fully received and should be excluded from open pipeline.
    assert "PO-1-L001" not in set(out_df["po_line_id"])
    assert len(out_df) == 2

    by_line = out_df.set_index("po_line_id")
    line2 = by_line.loc["PO-1-L002"]
    assert line2["ordered_qty"] == "5"
    assert line2["received_qty"] == "2"
    assert line2["remaining_open_qty"] == "3"
    assert line2["receipt_status"] == "partial_received"
    assert line2["supplier_code"] == "SUP-A"
    assert line2["supplier_name"] == "Alpha"
    assert line2["cost_mode"] == "test"
    assert line2["recommendation_basis"] == "test_cost_snapshot"
    assert line2["source_event_id"] == "evt-2"

    line3 = by_line.loc["PO-2-L001"]
    assert line3["ordered_qty"] == "4"
    assert line3["received_qty"] == "0"
    assert line3["remaining_open_qty"] == "4"
    assert line3["receipt_status"] == "not_received"
    assert line3["backorder_flag"] == "1"
