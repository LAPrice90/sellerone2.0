from __future__ import annotations

import sqlite3

import pandas as pd

from scripts.flows.A import A006_build_stock_events_raw as a006


def test_a006_sql_primary_writes_stock_events_table_and_csv_export(monkeypatch, tmp_path):
    ledger_path = tmp_path / "inventory_ledger_raw.csv"
    out_path = tmp_path / "stock_events_raw.csv"
    sqlite_path = tmp_path / "pilot.sqlite3"

    pd.DataFrame(
        [
            {
                "Reference ID": "REF-1",
                "Date and Time": "2026-04-03T12:00:00Z",
                "MSKU": "SKU-1",
                "ASIN": "ASIN-1",
                "FNSKU": "FNSKU-1",
                "Event Type": "Adjust",
                "Quantity": "2",
                "Disposition": "SELLABLE",
                "Reason": "Found",
                "Country": "GB",
                "Fulfillment Center": "FC-1",
                "Reconciled Quantity": "2",
                "Unreconciled Quantity": "0",
            }
        ]
    ).to_csv(ledger_path, index=False)

    monkeypatch.setattr(a006, "LEDGER_CSV", ledger_path)
    monkeypatch.setattr(a006, "OUT_CSV", out_path)
    monkeypatch.setenv("A006_WRITE_SHEETS", "0")
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    a006.main()

    built = pd.read_csv(out_path, dtype=str).fillna("")
    assert built.loc[0, "event_id"] == "REF-1"
    assert built.loc[0, "sku"] == "SKU-1"
    assert built.loc[0, "quantity"] == "2"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT event_id, sku, quantity FROM a_stock_events_raw"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("REF-1", "SKU-1", "2")]
