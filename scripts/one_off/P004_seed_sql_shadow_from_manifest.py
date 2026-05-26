from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage import Migration, StorageConfig, SqlStore, connect_store


SHADOW_METADATA_MIGRATIONS = [
    Migration(
        migration_id="0002_shadow_seed_metadata",
        sql="""
        CREATE TABLE IF NOT EXISTS shadow_seed_runs (
            run_id TEXT PRIMARY KEY,
            manifest_path TEXT NOT NULL,
            started_at_utc TEXT NOT NULL,
            completed_at_utc TEXT NOT NULL,
            table_count TEXT NOT NULL,
            row_count TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shadow_seed_tables (
            dataset_id TEXT PRIMARY KEY,
            table_name TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_header_json TEXT NOT NULL,
            sql_columns_json TEXT NOT NULL,
            row_count TEXT NOT NULL,
            loaded_at_utc TEXT NOT NULL
        );
        """,
    )
]


@dataclass(frozen=True)
class SeedResult:
    run_id: str
    table_count: int
    row_count: int
    sqlite_path: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_table_name(dataset_id: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", dataset_id.strip().lower()).strip("_")
    if not value:
        raise ValueError("dataset_id is required for shadow table name")
    if value[0].isdigit():
        value = f"d_{value}"
    return value


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def normalize_columns(header: Iterable[str]) -> list[str]:
    seen: dict[str, int] = {}
    columns: list[str] = []
    for idx, raw in enumerate(header, start=1):
        base = re.sub(r"[^a-zA-Z0-9_]+", "_", str(raw or "").strip()).strip("_").lower()
        if not base:
            base = f"column_{idx}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        columns.append(base if count == 1 else f"{base}_{count}")
    return columns


def delimiter_for_path(path: Path) -> str:
    return "\t" if path.suffix.lower() == ".tsv" else ","


def read_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_path_for_manifest_row(row: dict[str, str], *, manifest_path: Path, root: Path) -> Path:
    bundle_dir = manifest_path.parent
    copied_path = bundle_dir / "files" / row["path"]
    if copied_path.exists():
        return copied_path
    return root / row["path"]


def seed_table_from_csv(
    store: SqlStore,
    *,
    dataset_id: str,
    source_path: Path,
    source_rel: str,
    loaded_at_utc: str,
) -> tuple[str, int]:
    table_name = sanitize_table_name(dataset_id)
    delimiter = delimiter_for_path(source_path)
    with source_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            header = []
        if not header:
            return "", 0
        columns = normalize_columns(header)
        quoted_cols = ", ".join(f"{quote_identifier(col)} TEXT" for col in columns)
        store.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")
        store.execute(f"CREATE TABLE {quote_identifier(table_name)} ({quoted_cols})")
        placeholders = ", ".join(["?"] * len(columns))
        insert_sql = (
            f"INSERT INTO {quote_identifier(table_name)} "
            f"({', '.join(quote_identifier(col) for col in columns)}) VALUES ({placeholders})"
        )
        row_count = 0
        for raw_row in reader:
            values = list(raw_row[: len(columns)])
            if len(values) < len(columns):
                values.extend([""] * (len(columns) - len(values)))
            store.execute(insert_sql, values)
            row_count += 1

    store.execute(
        """
        INSERT OR REPLACE INTO shadow_seed_tables
        (dataset_id, table_name, source_path, source_header_json, sql_columns_json, row_count, loaded_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            dataset_id,
            table_name,
            source_rel,
            json.dumps(header),
            json.dumps(columns),
            str(row_count),
            loaded_at_utc,
        ],
    )
    return table_name, row_count


def seed_from_manifest(
    *,
    manifest_path: Path,
    sqlite_path: Path,
    root: Path = ROOT,
) -> SeedResult:
    run_id = f"shadow_seed_{utc_now_iso().replace(':', '').replace('-', '')}"
    started_at = utc_now_iso()
    store = connect_store(StorageConfig(mode="sql_shadow", sqlite_path=sqlite_path))
    table_count = 0
    total_rows = 0
    try:
        store.apply_migrations(SHADOW_METADATA_MIGRATIONS)
        manifest_rows = read_manifest_rows(manifest_path)
        loaded_at = utc_now_iso()
        seeded_dataset_ids: set[str] = set()
        with store.transaction():
            for row in manifest_rows:
                if row.get("exists") != "true":
                    continue
                if row.get("row_count_status") != "ok":
                    continue
                dataset_id = row.get("dataset_id", "").strip()
                if not dataset_id:
                    continue
                if dataset_id in seeded_dataset_ids:
                    continue
                source_path = source_path_for_manifest_row(row, manifest_path=manifest_path, root=root)
                table_name, row_count = seed_table_from_csv(
                    store,
                    dataset_id=dataset_id,
                    source_path=source_path,
                    source_rel=row["path"],
                    loaded_at_utc=loaded_at,
                )
                if table_name:
                    seeded_dataset_ids.add(dataset_id)
                    table_count += 1
                    total_rows += row_count
            store.execute(
                """
                INSERT INTO shadow_seed_runs
                (run_id, manifest_path, started_at_utc, completed_at_utc, table_count, row_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    str(manifest_path),
                    started_at,
                    utc_now_iso(),
                    str(table_count),
                    str(total_rows),
                    "succeeded",
                ],
            )
    finally:
        store.close()
    return SeedResult(run_id=run_id, table_count=table_count, row_count=total_rows, sqlite_path=sqlite_path)


def export_dataset(*, sqlite_path: Path, dataset_id: str, output_path: Path) -> int:
    store = connect_store(StorageConfig(mode="sql_shadow", sqlite_path=sqlite_path))
    try:
        metadata_rows = store.query_all(
            "SELECT table_name, source_header_json, sql_columns_json FROM shadow_seed_tables WHERE dataset_id = ?",
            [dataset_id],
        )
        if not metadata_rows:
            raise ValueError(f"Dataset not seeded: {dataset_id}")
        metadata = metadata_rows[0]
        table_name = str(metadata["table_name"])
        source_header = json.loads(str(metadata["source_header_json"]))
        sql_columns = json.loads(str(metadata["sql_columns_json"]))
        rows = store.query_all(
            f"SELECT {', '.join(quote_identifier(col) for col in sql_columns)} FROM {quote_identifier(table_name)}"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(source_header)
            for row in rows:
                writer.writerow([row.get(col, "") for col in sql_columns])
        return len(rows)
    finally:
        store.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed SQL shadow tables from a SellerOne backup manifest.")
    parser.add_argument("--manifest", required=True, help="Path to backup manifest.csv.")
    parser.add_argument("--sqlite-path", required=True, help="SQLite DB path for shadow seed.")
    parser.add_argument("--export-dataset", default="", help="Optional dataset_id to export after seed.")
    parser.add_argument("--export-path", default="", help="CSV output path for --export-dataset.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = seed_from_manifest(
        manifest_path=Path(args.manifest),
        sqlite_path=Path(args.sqlite_path),
        root=ROOT,
    )
    payload: dict[str, object] = {
        "run_id": result.run_id,
        "table_count": result.table_count,
        "row_count": result.row_count,
        "sqlite_path": str(result.sqlite_path),
    }
    if args.export_dataset:
        if not args.export_path:
            raise SystemExit("--export-path is required with --export-dataset")
        exported_rows = export_dataset(
            sqlite_path=Path(args.sqlite_path),
            dataset_id=args.export_dataset,
            output_path=Path(args.export_path),
        )
        payload["export_dataset"] = args.export_dataset
        payload["export_path"] = args.export_path
        payload["exported_rows"] = exported_rows
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
