from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.flows.B import B009_apply_stock_adjustments_to_tokens as b009


def test_append_adjustment_fallback_tokens_creates_tokens_from_latest_cost_basis() -> None:
    ledger = pd.DataFrame(
        [
            {
                "token_id": "tok-1",
                "seller_sku": "SKU-1",
                "cost_per_unit": "2.50",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-01-10",
                "notes": "",
                "source": "stock_receipt",
                "source_batch_id": "SR-1",
                "source_order_key": "OK-1",
                "created_at": "2026-01-10T00:00:00Z",
                "allocated_order_id": "ORDER-1",
                "allocated_date": "2026-01-20T00:00:00Z",
            }
        ]
    )

    updated, created = b009._append_adjustment_fallback_tokens(
        ledger,
        sku="SKU-1",
        qty=2,
        event_id="EVT-1",
        disposition="SELLABLE",
        now_iso="2026-04-22T15:00:00Z",
        event_date="2026-04-20T10:00:00+0000",
    )

    assert created == 2
    new_rows = updated.loc[updated["source"].eq("stock_adjustment_fallback")].copy()
    assert len(new_rows.index) == 2
    assert set(new_rows["status"].astype(str)) == {"available"}
    assert set(new_rows["cost_per_unit"].astype(str)) == {"2.50"}
    assert set(new_rows["source_batch_id"].astype(str)) == {"EVT-1"}


def test_append_adjustment_fallback_tokens_requires_cost_basis() -> None:
    ledger = pd.DataFrame(
        [
            {
                "token_id": "tok-1",
                "seller_sku": "SKU-1",
                "cost_per_unit": "",
                "currency": "GBP",
                "status": "allocated",
            }
        ]
    )

    updated, created = b009._append_adjustment_fallback_tokens(
        ledger,
        sku="SKU-1",
        qty=1,
        event_id="EVT-2",
        disposition="SELLABLE",
        now_iso="2026-04-22T15:00:00Z",
        event_date="2026-04-20T10:00:00+0000",
    )

    assert created == 0
    assert len(updated.index) == 1


def test_stock_adjustment_events_sql_primary_writes_combined_log(monkeypatch, tmp_path: Path) -> None:
    sqlite_path = tmp_path / "pilot.sqlite3"
    out_events = tmp_path / "out" / "stock_adjustment_token_events.csv"
    monkeypatch.setattr(b009, "OUT_EVENTS", out_events)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))
    prior = pd.DataFrame(
        [
            {
                "event_id": "EVT-1",
                "sku": "SKU-1",
                "event_date": "2026-04-27",
                "event_type": "Adjustments",
                "disposition": "SELLABLE",
                "quantity": "1",
                "applied_qty": "1",
                "status": "ok",
                "note": "prior",
                "event_ts": "2026-04-27T00:00:00Z",
            }
        ],
        columns=b009.EVENT_COLUMNS,
    )
    new_events = pd.DataFrame(
        [
            {
                "event_id": "EVT-2",
                "sku": "SKU-2",
                "event_date": "2026-04-28",
                "event_type": "CustomerReturns",
                "disposition": "UNSELLABLE",
                "quantity": "2",
                "applied_qty": "2",
                "status": "ok",
                "note": "",
                "event_ts": "2026-04-28T00:00:00Z",
            }
        ],
        columns=b009.EVENT_COLUMNS,
    )

    result = b009._write_stock_adjustment_events_output(prior, new_events, use_sheets=False)

    assert result["sql_rows"] == 2
    built = pd.read_csv(out_events, dtype=str).fillna("")
    assert len(built) == 2
    assert set(built["event_id"]) == {"EVT-1", "EVT-2"}

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT event_id, sku, status FROM b_stock_adjustment_token_events ORDER BY event_id"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("EVT-1", "SKU-1", "ok"), ("EVT-2", "SKU-2", "ok")]


def test_stock_adjustment_events_writer_preserves_repeated_event_ids(monkeypatch, tmp_path: Path) -> None:
    out_events = tmp_path / "out" / "stock_adjustment_token_events.csv"
    monkeypatch.setattr(b009, "OUT_EVENTS", out_events)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    prior = pd.DataFrame(
        [{"event_id": "EVT-1", "sku": "OLD", "status": "partial"}],
        columns=["event_id", "sku", "status"],
    )
    new_events = pd.DataFrame(
        [{"event_id": "EVT-1", "sku": "NEW", "status": "ok"}],
        columns=["event_id", "sku", "status"],
    )

    result = b009._write_stock_adjustment_events_output(prior, new_events, use_sheets=False)

    built = pd.read_csv(out_events, dtype=str).fillna("")
    assert result["total_events"] == 2
    assert len(built) == 2
    assert built["event_id"].tolist() == ["EVT-1", "EVT-1"]
    assert built["sku"].tolist() == ["OLD", "NEW"]
