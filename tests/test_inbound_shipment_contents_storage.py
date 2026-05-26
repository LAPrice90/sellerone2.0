from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.flows.B import B030_run_inbound_shipment_contents_report as b030
from scripts.flows.B import B031_run_inbound_shipment_items as b031


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "inbound_shipment_id": "FBA123",
                "sku": "SKU-1",
                "quantity": "4",
            }
        ]
    )


def test_b030_write_output_frame_sql_primary_exports_csv_and_sql(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "inbound_shipment_contents.csv"

    result = b030._write_output_frame(_sample_frame(), out_csv, b030.SQL_TABLE_INBOUND_SHIPMENT_CONTENTS)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 1
    assert len(pd.read_csv(out_csv, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {b030.SQL_TABLE_INBOUND_SHIPMENT_CONTENTS}").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_b031_write_output_frame_sql_primary_exports_csv_and_sql(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "inbound_shipment_contents.csv"

    result = b031._write_output_frame(_sample_frame(), out_csv, b031.SQL_TABLE_INBOUND_SHIPMENT_CONTENTS)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 1
    assert len(pd.read_csv(out_csv, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {b031.SQL_TABLE_INBOUND_SHIPMENT_CONTENTS}").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_b031_write_output_frame_csv_mode_does_not_create_sql(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "sellerone.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(db_path))
    out_csv = tmp_path / "inbound_shipment_contents.csv"

    result = b031._write_output_frame(_sample_frame(), out_csv, b031.SQL_TABLE_INBOUND_SHIPMENT_CONTENTS)

    assert result["mode"] == "csv"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 0
    assert result["sql_table"] == ""
    assert out_csv.exists()
    assert not db_path.exists()
