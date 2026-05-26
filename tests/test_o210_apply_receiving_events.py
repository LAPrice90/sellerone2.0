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

from scripts.flows.O.O210_apply_receiving_events import apply_receiving_events
from scripts.flows.O._schemas import get_o_output_contract


def _write_po_lines(tmp_path: Path) -> None:
    path = tmp_path / get_o_output_contract("purchase_order_lines_live").rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
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
                "receipt_status": "not_received",
                "received_qty": "0",
                "remaining_open_qty": "10",
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
            },
        ]
    ).to_csv(path, index=False)


def _write_existing_receiving(tmp_path: Path) -> None:
    path = tmp_path / get_o_output_contract("receiving_events").rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T10:00:00Z",
                "event_id": "old-evt",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "received_qty": "2",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
                "note": "existing",
                "actor": "tester",
            }
        ]
    ).to_csv(path, index=False)


def _write_inbox_events(tmp_path: Path) -> None:
    path = tmp_path / get_o_output_contract("receiving_events_inbox").rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            # partial receipt on line1 (2 existing + 3 new = 5)
            {
                "event_utc": "2026-04-03T11:00:00Z",
                "event_id": "evt-partial",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "received_qty": "3",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
                "note": "partial",
                "actor": "tester",
            },
            # full receipt on line1 (5 + 5 = 10)
            {
                "event_utc": "2026-04-03T11:01:00Z",
                "event_id": "evt-full",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "received_qty": "5",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
                "note": "full",
                "actor": "tester",
            },
            # duplicate event id
            {
                "event_utc": "2026-04-03T11:02:00Z",
                "event_id": "old-evt",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "received_qty": "1",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
                "note": "dup",
                "actor": "tester",
            },
            # over receipt attempt (already 10 after prior events)
            {
                "event_utc": "2026-04-03T11:03:00Z",
                "event_id": "evt-over",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-1",
                "received_qty": "1",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
                "note": "over",
                "actor": "tester",
            },
            # invalid qty
            {
                "event_utc": "2026-04-03T11:04:00Z",
                "event_id": "evt-invalid",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L002",
                "seller_sku": "SKU-2",
                "received_qty": "0",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
                "note": "bad qty",
                "actor": "tester",
            },
            # missing po line
            {
                "event_utc": "2026-04-03T11:05:00Z",
                "event_id": "evt-missing",
                "po_id": "PO-X",
                "po_line_id": "PO-X-L001",
                "seller_sku": "SKU-X",
                "received_qty": "1",
                "warehouse_ref": "WH-A",
                "event_source": "manual_test",
                "note": "missing line",
                "actor": "tester",
            },
            # fallback match by po_id + seller_sku (no po_line_id)
            {
                "event_utc": "2026-04-03T11:06:00Z",
                "event_id": "evt-fallback",
                "po_id": "PO-2",
                "po_line_id": "",
                "seller_sku": "SKU-3",
                "received_qty": "2",
                "warehouse_ref": "WH-B",
                "event_source": "manual_test",
                "note": "fallback id match",
                "actor": "tester",
            },
        ]
    ).to_csv(path, index=False)


def test_o210_applies_receiving_events_with_dedupe_and_holds(tmp_path: Path) -> None:
    _write_po_lines(tmp_path)
    _write_existing_receiving(tmp_path)
    _write_inbox_events(tmp_path)

    append_df, full_df, holds_df = apply_receiving_events(
        root=tmp_path,
        applied_utc="2026-04-03T12:00:00Z",
    )

    assert len(append_df) == 3
    assert len(full_df) == 4
    assert set(append_df["event_id"]) == {"evt-partial", "evt-full", "evt-fallback"}
    assert len(holds_df) == 4
    assert set(holds_df["hold_reason"]) == {
        "duplicate_event_id",
        "over_receipt",
        "invalid_received_qty",
        "missing_po_line",
    }

    fallback_row = append_df.loc[append_df["event_id"] == "evt-fallback"].iloc[0]
    assert fallback_row["po_line_id"] == "PO-2-L001"
    assert fallback_row["seller_sku"] == "SKU-3"
    assert fallback_row["received_qty"] == "2"


def test_o210_second_run_is_deduped_by_event_id(tmp_path: Path) -> None:
    _write_po_lines(tmp_path)
    _write_existing_receiving(tmp_path)
    _write_inbox_events(tmp_path)

    _, first_full, _ = apply_receiving_events(
        root=tmp_path,
        applied_utc="2026-04-03T12:00:00Z",
    )
    second_append, second_full, second_holds = apply_receiving_events(
        root=tmp_path,
        applied_utc="2026-04-03T12:10:00Z",
    )

    assert len(first_full) == 4
    assert len(second_append) == 0
    assert len(second_full) == 4
    second_hold_reasons = set(second_holds["hold_reason"])
    assert "duplicate_event_id" in second_hold_reasons
    assert "invalid_received_qty" in second_hold_reasons
    assert "missing_po_line" in second_hold_reasons
