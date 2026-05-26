from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.core.storage import write_dataframe_with_sql_compat
from scripts.one_off import T002_B015_fix_duplicate_token_ids as t002
from scripts.one_off import T009_B031_backfill_tokens_from_orders_sheet as t009
from scripts.one_off import T010_B034_full_rebuild_tokens_from_orders_sheet as t010


def test_token_live_table_names_are_shared() -> None:
    assert {
        t002.SQL_TABLE_TOKEN_LEDGER_LIVE,
        t009.SQL_TABLE_TOKEN_LEDGER_LIVE,
        t010.SQL_TABLE_TOKEN_LEDGER_LIVE,
    } == {"b_token_ledger_live"}
    assert {
        t002.SQL_TABLE_TOKEN_ALLOCATIONS_LIVE,
        t010.SQL_TABLE_TOKEN_ALLOCATIONS_LIVE,
    } == {"b_token_allocations_live"}


def test_token_ledger_live_sql_primary_exports_csv_and_sql(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "token_ledger_live.csv"
    df = pd.DataFrame([{"token_id": "TOKEN-1", "seller_sku": "SKU-1", "status": "available"}])

    result = write_dataframe_with_sql_compat(df, out_csv, t002.SQL_TABLE_TOKEN_LEDGER_LIVE)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 1
    assert len(pd.read_csv(out_csv, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {t002.SQL_TABLE_TOKEN_LEDGER_LIVE}").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_token_allocations_live_sql_primary_exports_csv_and_sql(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "token_allocations_live.csv"
    df = pd.DataFrame([{"order_id": "ORDER-1", "token_id": "TOKEN-1", "seller_sku": "SKU-1"}])

    result = write_dataframe_with_sql_compat(df, out_csv, t002.SQL_TABLE_TOKEN_ALLOCATIONS_LIVE)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 1
    assert len(pd.read_csv(out_csv, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {t002.SQL_TABLE_TOKEN_ALLOCATIONS_LIVE}").fetchone()[0]
    finally:
        conn.close()
    assert count == 1
