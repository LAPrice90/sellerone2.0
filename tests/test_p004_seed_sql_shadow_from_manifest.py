from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from scripts.one_off import P004_seed_sql_shadow_from_manifest as p004


def _write_manifest_bundle(root: Path) -> Path:
    bundle = root / "out" / "backups" / "sql_storage_migration_v1" / "bundle_1"
    files = bundle / "files" / "out"
    files.mkdir(parents=True, exist_ok=True)
    (files / "orders_all.csv").write_text("Order ID,SKU\n1,ABC\n2,DEF\n", encoding="utf-8")
    (files / "notes.txt").write_text("not tabular\n", encoding="utf-8")
    manifest = bundle / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path",
                "exists",
                "row_count_status",
                "dataset_id",
                "hash_status",
                "row_count",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerow(
            {
                "path": "out/orders_all.csv",
                "exists": "true",
                "row_count_status": "ok",
                "dataset_id": "B.ORDERS_ALL",
                "hash_status": "ok",
                "row_count": "2",
            }
        )
        writer.writerow(
            {
                "path": "out/notes.txt",
                "exists": "true",
                "row_count_status": "not_tabular",
                "dataset_id": "SYS.NOTES",
                "hash_status": "ok",
                "row_count": "",
            }
        )
    return manifest


def test_seed_from_manifest_loads_csv_shadow_table(tmp_path: Path) -> None:
    manifest = _write_manifest_bundle(tmp_path)
    sqlite_path = tmp_path / "shadow.sqlite3"

    result = p004.seed_from_manifest(manifest_path=manifest, sqlite_path=sqlite_path, root=tmp_path)

    assert result.table_count == 1
    assert result.row_count == 2

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute("SELECT order_id, sku FROM b_orders_all ORDER BY order_id")]
        assert rows == [{"order_id": "1", "sku": "ABC"}, {"order_id": "2", "sku": "DEF"}]
        meta = [
            dict(row)
            for row in conn.execute(
                "SELECT dataset_id, table_name, row_count FROM shadow_seed_tables WHERE dataset_id = ?",
                ["B.ORDERS_ALL"],
            )
        ]
        assert meta == [{"dataset_id": "B.ORDERS_ALL", "table_name": "b_orders_all", "row_count": "2"}]
    finally:
        conn.close()


def test_export_dataset_round_trips_header_and_rows(tmp_path: Path) -> None:
    manifest = _write_manifest_bundle(tmp_path)
    sqlite_path = tmp_path / "shadow.sqlite3"
    output_path = tmp_path / "exported" / "orders_all.csv"
    p004.seed_from_manifest(manifest_path=manifest, sqlite_path=sqlite_path, root=tmp_path)

    exported_rows = p004.export_dataset(
        sqlite_path=sqlite_path,
        dataset_id="B.ORDERS_ALL",
        output_path=output_path,
    )

    assert exported_rows == 2
    assert output_path.read_text(encoding="utf-8").splitlines() == [
        "Order ID,SKU",
        "1,ABC",
        "2,DEF",
    ]


def test_sanitize_table_name_rejects_blank_dataset_id() -> None:
    try:
        p004.sanitize_table_name("")
    except ValueError as exc:
        assert "dataset_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_empty_csv_is_skipped_without_failing(tmp_path: Path) -> None:
    source = tmp_path / "empty.csv"
    source.write_text("", encoding="utf-8")
    sqlite_path = tmp_path / "shadow.sqlite3"
    store = p004.connect_store(p004.StorageConfig(mode="sql_shadow", sqlite_path=sqlite_path))
    try:
        store.apply_migrations(p004.SHADOW_METADATA_MIGRATIONS)
        table_name, row_count = p004.seed_table_from_csv(
            store,
            dataset_id="A.EMPTY",
            source_path=source,
            source_rel="empty.csv",
            loaded_at_utc="2026-04-28T12:00:00Z",
        )
    finally:
        store.close()

    assert table_name == ""
    assert row_count == 0
