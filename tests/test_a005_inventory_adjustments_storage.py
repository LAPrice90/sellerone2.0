from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from scripts.flows.A import A005_run_inventory_adjustments_report as a005


def test_sql_table_for_output_maps_known_paths() -> None:
    assert a005._sql_table_for_output(a005.OUT_CSV_LEDGER) == a005.SQL_TABLE_LEDGER
    assert a005._sql_table_for_output(a005.OUT_CSV_ADJUSTMENTS) == a005.SQL_TABLE_ADJUSTMENTS
    assert a005._sql_table_for_output(a005.OUT_CSV_LATEST) == a005.SQL_TABLE_LATEST


def test_sql_table_for_output_rejects_unknown_path() -> None:
    with pytest.raises(ValueError):
        a005._sql_table_for_output(Path("out/unknown_inventory_output.csv"))


def test_write_output_frame_sql_primary_exports_csv_and_sql(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "inventory_ledger_raw.csv"
    df = pd.DataFrame(
        [
            {
                "Date": "2026-04-28",
                "MSKU": "SKU-1",
                "Event Type": "Receipts",
                "Reference ID": "REF-1",
                "Quantity": "3",
            }
        ]
    )

    result = a005._write_output_frame(df, out_csv, a005.SQL_TABLE_LEDGER)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 1
    assert len(pd.read_csv(out_csv, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {a005.SQL_TABLE_LEDGER}").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_write_output_frame_csv_mode_does_not_create_sql(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "sellerone.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(db_path))
    out_csv = tmp_path / "inventory_adjustments_latest.csv"
    df = pd.DataFrame(columns=["Date", "MSKU", "Event Type", "Reference ID", "Quantity"])

    result = a005._write_output_frame(df, out_csv, a005.SQL_TABLE_LATEST)

    assert result["mode"] == "csv"
    assert result["csv_rows"] == 0
    assert result["sql_rows"] == 0
    assert result["sql_table"] == ""
    assert out_csv.exists()
    assert not db_path.exists()
