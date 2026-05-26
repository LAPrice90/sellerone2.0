from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.tools import process_stock_receipts_sheet as receipts


def test_summarize_token_rows_builds_order_key_counts() -> None:
    header = ["token_id", "seller_sku", "source_batch_id", "source_order_key"]
    rows = [
        ["SR-1-0001", "SKU-1", "SR-1", "ORDER-KEY-1"],
        ["SR-1-0002", "SKU-1", "SR-1", "ORDER-KEY-1"],
        ["SR-2-0001", "SKU-1", "SR-2", "ORDER-KEY-1"],
        ["SR-3-0001", "SKU-2", "SR-3", "ORDER-KEY-2"],
    ]

    token_ids, batch_counts, order_key_counts = receipts._summarize_token_rows(header, rows)

    assert len(token_ids) == 4
    assert batch_counts == {"SR-1": 2, "SR-2": 1, "SR-3": 1}
    key = ("ORDER-KEY-1", "SKU-1")
    assert key in order_key_counts
    assert int(order_key_counts[key]["count"]) == 3
    assert set(order_key_counts[key]["batch_ids"]) == {"SR-1", "SR-2"}


def test_summary_columns_keep_empty_output_schema() -> None:
    df = pd.DataFrame([], columns=receipts.SUMMARY_COLUMNS)

    assert list(df.columns) == receipts.SUMMARY_COLUMNS
    assert len(df) == 0


def test_write_output_frame_sql_primary_exports_empty_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "stock_receipts_latest.csv"
    df = pd.DataFrame([], columns=receipts.SUMMARY_COLUMNS)

    result = receipts._write_output_frame(df, out_csv, receipts.SQL_TABLE_STOCK_RECEIPTS_LATEST)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 0
    assert result["sql_rows"] == 0
    assert pd.read_csv(out_csv, dtype=str).columns.tolist() == receipts.SUMMARY_COLUMNS
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {receipts.SQL_TABLE_STOCK_RECEIPTS_LATEST}").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_write_output_frame_csv_mode_does_not_create_sql(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "sellerone.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(db_path))
    out_csv = tmp_path / "stock_receipt_summary.csv"
    df = pd.DataFrame([], columns=receipts.SUMMARY_COLUMNS)

    result = receipts._write_output_frame(df, out_csv, receipts.SQL_TABLE_STOCK_RECEIPT_SUMMARY)

    assert result["mode"] == "csv"
    assert result["csv_rows"] == 0
    assert result["sql_rows"] == 0
    assert result["sql_table"] == ""
    assert out_csv.exists()
    assert not db_path.exists()
