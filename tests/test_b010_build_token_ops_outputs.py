from __future__ import annotations

import sqlite3

import pandas as pd

from scripts.flows.B import B010_build_token_ops_outputs as b010


def test_b010_sql_primary_writes_token_ops_tables_and_csv_exports(monkeypatch, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    events_path = out_dir / "token_events.csv"
    cogs_ledger_path = out_dir / "token_cogs_ledger.csv"
    movement_path = out_dir / "token_movement_log.csv"
    cogs_path = out_dir / "order_cogs_from_tokens.csv"
    sqlite_path = tmp_path / "pilot.sqlite3"

    pd.DataFrame(
        [
            {
                "event_ts": "2026-04-03T12:01:00Z",
                "event_type": "Allocation",
                "sku": "SKU-1",
                "order_id": "ORDER-1",
                "token_id": "TOKEN-1",
                "qty": "1",
                "token_cost": "2.22",
                "currency": "GBP",
            }
        ]
    ).to_csv(events_path, index=False)
    pd.DataFrame(
        [
            {
                "order_id": "ORDER-1",
                "seller_sku": "SKU-1",
                "currency": "GBP",
                "quantity": "1",
                "token_cost": "2.22",
            }
        ]
    ).to_csv(cogs_ledger_path, index=False)

    monkeypatch.setattr(b010, "OUT_EVENTS", events_path)
    monkeypatch.setattr(b010, "TOKEN_COGS_LEDGER", cogs_ledger_path)
    monkeypatch.setattr(b010, "OUT_MOVEMENT", movement_path)
    monkeypatch.setattr(b010, "OUT_COGS", cogs_path)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    b010.main()

    movement = pd.read_csv(movement_path, dtype=str).fillna("")
    cogs = pd.read_csv(cogs_path, dtype=str).fillna("")
    assert movement.loc[0, "token_id"] == "TOKEN-1"
    assert cogs.loc[0, "order_id"] == "ORDER-1"
    assert cogs.loc[0, "sku"] == "SKU-1"

    connection = sqlite3.connect(sqlite_path)
    try:
        movement_rows = connection.execute(
            "SELECT order_id, sku, token_id FROM b_token_movement_log"
        ).fetchall()
        cogs_rows = connection.execute(
            "SELECT order_id, sku, quantity, cogs_total FROM b_order_cogs_from_tokens"
        ).fetchall()
    finally:
        connection.close()

    assert movement_rows == [("ORDER-1", "SKU-1", "TOKEN-1")]
    assert cogs_rows == [("ORDER-1", "SKU-1", "1", "2.22")]
