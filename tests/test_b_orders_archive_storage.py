from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.flows.B import B001_run_orders_to_sheet as b001
from scripts.flows.B import B002_run_pending_orders_to_sheet as b002
from scripts.one_off import T019_D020_backfill_missing_orders_from_sellerboard as t019


def test_b_order_archive_table_names_are_shared() -> None:
    assert {b001.SQL_TABLE_ORDERS_ALL, b002.SQL_TABLE_ORDERS_ALL, t019.SQL_TABLE_ORDERS_ALL} == {"b_orders_all"}
    assert {b001.SQL_TABLE_ORDER_ITEMS_ALL, b002.SQL_TABLE_ORDER_ITEMS_ALL, t019.SQL_TABLE_ORDER_ITEMS_ALL} == {
        "b_order_items_all"
    }


def test_b001_write_compiled_unique_sql_primary_writes_orders(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    incoming = pd.DataFrame([{"amazon_order_id": "ORDER-1", "purchase_date": "2026-04-28T10:00:00Z"}])

    rows = b001._write_compiled_unique(
        b001.ORDERS_ALL_PATH,
        pd.DataFrame(),
        incoming,
        dedupe_key_cols=["amazon_order_id"],
    )

    assert rows == 1
    assert len(pd.read_csv(b001.ORDERS_ALL_PATH, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {b001.SQL_TABLE_ORDERS_ALL}").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_b002_write_compiled_unique_sql_primary_writes_items(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    incoming = pd.DataFrame([{"amazon_order_id": "ORDER-1", "order_item_id": "ITEM-1", "seller_sku": "SKU-1"}])

    rows = b002._write_compiled_unique(
        b002.ITEMS_ALL,
        pd.DataFrame(),
        incoming,
        dedupe_key_cols=["order_item_id"],
    )

    assert rows == 1
    assert len(pd.read_csv(b002.ITEMS_ALL, dtype=str)) == 1
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {b002.SQL_TABLE_ORDER_ITEMS_ALL}").fetchone()[0]
    finally:
        conn.close()
    assert count == 1
