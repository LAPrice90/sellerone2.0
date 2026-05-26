from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.B import B003_run_financial_events_level3 as b003


def test_b003_official_output_sql_primary_writes_table_and_csv(monkeypatch, tmp_path: Path) -> None:
    sqlite_path = tmp_path / "pilot.sqlite3"
    out_path = tmp_path / "out" / "financial_events_level3_official.csv"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))
    df = pd.DataFrame(
        [
            {
                "Date": "2026-04-28T10:00:00Z",
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "Price_Total": "10.00",
            }
        ]
    )

    result = b003._write_output_frame(df, out_path, b003.SQL_TABLE_OFFICIAL)

    assert result["sql_rows"] == 1
    built = pd.read_csv(out_path, dtype=str).fillna("")
    assert built.loc[0, "Order ID"] == "ORDER-1"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT date, order_id, sku, price_total FROM b_financial_events_level3_official"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("2026-04-28T10:00:00Z", "ORDER-1", "SKU-A", "10.00")]


def test_b003_official_output_csv_mode_writes_only_csv(monkeypatch, tmp_path: Path) -> None:
    out_path = tmp_path / "out" / "financial_events_level3_official.csv"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    df = pd.DataFrame([{"Order ID": "ORDER-CSV", "SKU": "SKU-C"}])

    result = b003._write_output_frame(df, out_path, b003.SQL_TABLE_OFFICIAL)

    assert result["sql_rows"] == 0
    built = pd.read_csv(out_path, dtype=str).fillna("")
    assert built.loc[0, "Order ID"] == "ORDER-CSV"
