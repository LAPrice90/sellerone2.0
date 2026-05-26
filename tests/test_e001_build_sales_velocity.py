from __future__ import annotations

import sqlite3

import pandas as pd

from scripts.flows.E import E001_build_sales_velocity as e001


def test_e001_sql_primary_writes_velocity_table_and_csv_export(monkeypatch, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    orders_path = out_dir / "order_master.csv"
    inventory_path = out_dir / "inventory_summaries.csv"
    velocity_path = out_dir / "sku_sales_velocity.csv"
    sqlite_path = tmp_path / "pilot.sqlite3"

    pd.DataFrame(
        [
            {"Date": "2026-04-01", "SKU": "SKU-1", "Quantity Ordered": "2"},
            {"Date": "2026-04-03", "SKU": "SKU-1", "Quantity Ordered": "4"},
        ]
    ).to_csv(orders_path, index=False)
    pd.DataFrame(
        [{"seller_sku": "SKU-1", "available": "5", "total_quantity": "8"}]
    ).to_csv(inventory_path, index=False)

    monkeypatch.setattr(e001, "ORDERS", orders_path)
    monkeypatch.setattr(e001, "INVENTORY", inventory_path)
    monkeypatch.setattr(e001, "OUT_VELOCITY", velocity_path)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    e001.main()

    built = pd.read_csv(velocity_path, dtype=str).fillna("")
    assert len(built) == 3
    assert set(built["window_days"]) == {"7", "30", "90"}
    assert set(built["sku"]) == {"SKU-1"}

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT sku, window_days, units_sold FROM e_sku_sales_velocity ORDER BY window_days"
        ).fetchall()
    finally:
        connection.close()

    assert len(rows) == 3
    assert {row[0] for row in rows} == {"SKU-1"}
    assert {row[2] for row in rows} == {"6.0"}
