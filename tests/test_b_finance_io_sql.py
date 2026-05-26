from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.flows.B._finance_io import (
    read_finance_frame,
    sync_csv_to_finance_table,
    table_for_path,
    write_finance_frame,
)


def test_b_finance_io_writes_sql_primary_and_csv_export(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    sqlite_path = tmp_path / "sellerone.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    frame = pd.DataFrame([{"Order ID": "ORDER-1", "SKU": "SKU-1", "Price_Total": "10.00"}])
    result = write_finance_frame(frame, Path("out/financial_events_level2.csv"))

    assert result["sql_rows"] == 1
    assert Path("out/financial_events_level2.csv").exists()

    loaded = read_finance_frame(Path("out/financial_events_level2.csv"), dtype=str).fillna("")
    assert loaded.loc[0, "Order ID"] == "ORDER-1"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT order_id, sku, price_total FROM b_financial_events_level2"
        ).fetchall()
    finally:
        connection.close()
    assert rows == [("ORDER-1", "SKU-1", "10.00")]


def test_b_finance_io_can_seed_sql_from_existing_csv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    sqlite_path = tmp_path / "sellerone.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    path = Path("out/orders_sheet_orders.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"SKU": "SKU-1", "Cost PU": "2.50"}]).to_csv(path, index=False)

    assert table_for_path(path) == "b_orders_sheet_orders"
    assert sync_csv_to_finance_table(path) == 1

    loaded = read_finance_frame(path, dtype=str).fillna("")
    assert loaded.loc[0, "Cost PU"] == "2.50"
