from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.flows.E import E003_build_restock_signals as e003


def test_e003_sql_primary_writes_restock_table_and_csv_export(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    velocity_path = out / "sku_sales_velocity.csv"
    restock_path = out / "sku_restock_signals.csv"
    sqlite_path = tmp_path / "pilot.sqlite3"

    pd.DataFrame(
        [
            {
                "sku": "SKU-A",
                "window_days": "30",
                "velocity_units_per_day": "2",
                "available": "10",
                "total_quantity": "12",
                "asof_date": "2026-04-28",
            }
        ]
    ).to_csv(velocity_path, index=False)

    monkeypatch.setattr(e003, "VELOCITY", velocity_path)
    monkeypatch.setattr(e003, "INVENTORY", out / "inventory_summaries.csv")
    monkeypatch.setattr(e003, "OUT_RESTOCK", restock_path)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    e003.main()

    built = pd.read_csv(restock_path, dtype=str).fillna("")
    assert built.loc[0, "sku"] == "SKU-A"
    assert built.loc[0, "reorder_flag"] == "yes"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT sku, reorder_flag FROM e_sku_restock_signals"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("SKU-A", "yes")]
