from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import pandas as pd

from scripts.core.storage import (
    Migration,
    StorageConfig,
    connect_store,
    list_review_summary_snapshots,
    parse_storage_mode,
    read_dataframe_with_sql_fallback,
    read_review_pack_dataframe,
    read_review_summary_dataframe,
    write_dataframe_with_sql_compat,
    write_review_pack_snapshots_sql_compat,
)


def test_parse_storage_mode_accepts_known_modes() -> None:
    assert parse_storage_mode(None) == "csv"
    assert parse_storage_mode("SQL_SHADOW") == "sql_shadow"
    assert parse_storage_mode("sql_primary_csv_export") == "sql_primary_csv_export"


def test_parse_storage_mode_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        parse_storage_mode("sql_primary")


def test_storage_config_from_env_uses_sqlite_default() -> None:
    config = StorageConfig.from_env({"SELLERONE_STORAGE_MODE": "sql_shadow"})
    assert config.mode == "sql_shadow"
    assert config.backend == "sqlite"
    assert config.sqlite_path == Path("out/sql/sellerone_dev.sqlite3")


def test_sqlite_store_transaction_commits(tmp_path: Path) -> None:
    store = connect_store(StorageConfig(mode="sql_shadow", sqlite_path=tmp_path / "sellerone.sqlite3"))
    try:
        with store.transaction():
            store.execute("CREATE TABLE demo (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
            store.execute("INSERT INTO demo (id, value) VALUES (?, ?)", ["a", "1"])
        rows = store.query_all("SELECT id, value FROM demo")
        assert rows == [{"id": "a", "value": "1"}]
    finally:
        store.close()


def test_sqlite_store_transaction_rolls_back(tmp_path: Path) -> None:
    store = connect_store(StorageConfig(mode="sql_shadow", sqlite_path=tmp_path / "sellerone.sqlite3"))
    try:
        store.execute("CREATE TABLE demo (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        store.connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            with store.transaction():
                store.execute("INSERT INTO demo (id, value) VALUES (?, ?)", ["a", "1"])
                store.execute("INSERT INTO demo (id, value) VALUES (?, ?)", ["a", "2"])
        rows = store.query_all("SELECT id, value FROM demo")
        assert rows == []
    finally:
        store.close()


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    store = connect_store(StorageConfig(mode="sql_shadow", sqlite_path=tmp_path / "sellerone.sqlite3"))
    try:
        migration = Migration(
            migration_id="0002_demo",
            sql="CREATE TABLE demo_migration (id TEXT PRIMARY KEY);",
        )
        first = store.apply_migrations([migration])
        second = store.apply_migrations([migration])
        assert first == ["0002_demo"]
        assert second == []
        assert store.table_exists("schema_migrations")
        assert store.table_exists("demo_migration")
        assert "0002_demo" in store.applied_migrations()
    finally:
        store.close()


def test_postgres_backend_requires_optional_driver() -> None:
    config = StorageConfig(mode="sql_shadow", database_url="postgresql://example.invalid/db")
    if config.backend != "postgres":
        pytest.fail("expected postgres backend")
    try:
        import psycopg  # noqa: F401
    except ModuleNotFoundError:
        with pytest.raises(RuntimeError):
            connect_store(config)


def test_write_dataframe_with_sql_compat_sql_primary_writes_csv_and_sql(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    csv_path = tmp_path / "product_db_preview.csv"
    df = pd.DataFrame([{"seller_sku": "SKU-1", "asin": "ASIN1"}])

    result = write_dataframe_with_sql_compat(df, csv_path, "sys_product_db_preview")

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 1
    assert result["sql_rows"] == 1
    assert len(pd.read_csv(csv_path, dtype=str)) == 1
    store = connect_store(StorageConfig(mode="sql_shadow", sqlite_path=tmp_path / "sellerone.sqlite3"))
    try:
        rows = store.query_all("select seller_sku, asin from sys_product_db_preview")
    finally:
        store.close()
    assert rows == [{"seller_sku": "SKU-1", "asin": "ASIN1"}]


def test_read_dataframe_with_sql_fallback_preserves_original_columns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    csv_path = tmp_path / "inventory_summaries.csv"
    df = pd.DataFrame([{"seller-sku": "SKU-1", "Total Quantity": "3"}])
    write_dataframe_with_sql_compat(df, csv_path, "a_inventory_summaries")

    out = read_dataframe_with_sql_fallback(csv_path, "a_inventory_summaries", dtype=str)

    assert out.to_dict("records") == [{"seller-sku": "SKU-1", "Total Quantity": "3"}]


def test_sql_shadow_reads_csv_before_sql_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_shadow")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    csv_path = tmp_path / "inventory_summaries.csv"
    write_dataframe_with_sql_compat(
        pd.DataFrame([{"seller_sku": "SKU-SQL", "quantity": "1"}]),
        csv_path,
        "a_inventory_summaries",
    )
    csv_path.write_text(
        "seller_sku,quantity\n"
        "SKU-CSV,2\n",
        encoding="utf-8",
    )

    out = read_dataframe_with_sql_fallback(csv_path, "a_inventory_summaries", dtype=str)

    assert out.to_dict("records") == [{"seller_sku": "SKU-CSV", "quantity": "2"}]


def test_sql_shadow_falls_back_to_sql_when_csv_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_shadow")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    csv_path = tmp_path / "inventory_summaries.csv"
    write_dataframe_with_sql_compat(
        pd.DataFrame([{"seller_sku": "SKU-SQL", "quantity": "1"}]),
        csv_path,
        "a_inventory_summaries",
    )
    csv_path.unlink()

    out = read_dataframe_with_sql_fallback(csv_path, "a_inventory_summaries", dtype=str)

    assert out.to_dict("records") == [{"seller_sku": "SKU-SQL", "quantity": "1"}]


def test_review_pack_snapshot_sql_round_trip_without_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    snapshot = "20260429T150000Z"
    pass_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "active_supplier_id": "supplier-a",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-1",
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
            }
        ]
    )
    near_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "active_supplier_id": "supplier-a",
                "active_run_id": "run-1",
                "review_batch_id": "near_miss_batch_001",
                "candidate_id": "cand-2",
                "supplier_sku": "SKU-2",
                "asin": "B000000002",
            }
        ]
    )
    summary_df = pd.DataFrame(
        [
            {"observed_utc": "2026-04-29T15:00:00Z", "metric": "active_supplier_id", "value": "supplier-a"},
            {"observed_utc": "2026-04-29T15:00:00Z", "metric": "active_run_id", "value": "run-1"},
        ]
    )

    result = write_review_pack_snapshots_sql_compat(
        pass_df=pass_df,
        near_miss_df=near_df,
        summary_df=summary_df,
        snapshot_id=snapshot,
    )

    assert result["mode"] == "sql_primary_csv_export"
    assert result["sql_pack_rows"] == 4
    assert result["sql_summary_rows"] == 4
    assert list_review_summary_snapshots() == [snapshot]
    pass_latest = read_review_pack_dataframe(tmp_path / "missing_pass.csv", pack_type="passes", dtype=str)
    near_historical = read_review_pack_dataframe(
        tmp_path / "missing_near.csv",
        pack_type="near_misses",
        snapshot_id=snapshot,
        dtype=str,
    )
    summary_latest = read_review_summary_dataframe(tmp_path / "missing_summary.csv", dtype=str)

    assert pass_latest.to_dict("records") == pass_df.to_dict("records")
    assert near_historical.to_dict("records") == near_df.to_dict("records")
    assert summary_latest.to_dict("records") == summary_df.to_dict("records")
