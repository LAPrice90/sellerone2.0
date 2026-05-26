from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.core.storage import write_dataframe_with_sql_compat
from scripts.flows.A import A001_run_listings_to_sheet as a001
from scripts.flows.A import A002_run_catalog_items_to_sheet as a002
from scripts.flows.A import A003_run_inventory_to_sheet as a003
from scripts.flows.A import A004_run_fees_to_sheet as a004
from scripts.flows.B import B001_run_orders_to_sheet as b001
from scripts.flows.B import B002_run_pending_orders_to_sheet as b002
from scripts.flows.B import B003_run_financial_events_level3 as b003


def test_product_db_preview_table_name_is_shared() -> None:
    names = {
        a001.SQL_TABLE_PRODUCT_DB_PREVIEW,
        a002.SQL_TABLE_PRODUCT_DB_PREVIEW,
        a003.SQL_TABLE_PRODUCT_DB_PREVIEW,
        a004.SQL_TABLE_PRODUCT_DB_PREVIEW,
        b001.SQL_TABLE_PRODUCT_DB_PREVIEW,
        b002.SQL_TABLE_PRODUCT_DB_PREVIEW,
        b003.SQL_TABLE_PRODUCT_DB_PREVIEW,
    }
    assert names == {"sys_product_db_preview"}


def test_product_db_preview_writer_sql_primary_exports_csv_and_sql(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "product_db_preview.csv"
    df = pd.DataFrame([{"seller_sku": "SKU-1", "asin": "ASIN1", "sale_status": "active"}])

    result = write_dataframe_with_sql_compat(df, out_csv, a001.SQL_TABLE_PRODUCT_DB_PREVIEW)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 1
    assert len(pd.read_csv(out_csv, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute("select count(*) from sys_product_db_preview").fetchone()[0]
    finally:
        conn.close()
    assert count == 1
