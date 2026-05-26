from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from scripts.core.storage.config import StorageConfig


@dataclass(frozen=True)
class Migration:
    migration_id: str
    sql: str


class SqlStore:
    def __init__(self, connection: Any, *, backend: str) -> None:
        self.connection = connection
        self.backend = backend
        if self.backend == "sqlite":
            self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator["SqlStore"]:
        try:
            yield self
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def execute(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> Any:
        return self.connection.execute(sql, params or ())

    def execute_many(self, sql: str, rows: Iterable[Sequence[Any] | Mapping[str, Any]]) -> Any:
        return self.connection.executemany(sql, rows)

    def query_all(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        cursor = self.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def table_exists(self, table_name: str) -> bool:
        if self.backend == "sqlite":
            rows = self.query_all(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                [table_name],
            )
            return bool(rows)
        rows = self.query_all(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            [table_name],
        )
        return bool(rows)

    def _param(self) -> str:
        return "?" if self.backend == "sqlite" else "%s"

    def _execute_migration_sql(self, sql: str) -> None:
        if self.backend == "sqlite":
            self.connection.executescript(sql)
            return
        self.execute(sql)

    def ensure_migration_table(self) -> None:
        if self.backend == "sqlite":
            sql = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id TEXT PRIMARY KEY,
                applied_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
            """
        else:
            sql = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id TEXT PRIMARY KEY,
                applied_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        self.execute(sql)
        self.connection.commit()

    def applied_migrations(self) -> set[str]:
        self.ensure_migration_table()
        rows = self.query_all("SELECT migration_id FROM schema_migrations")
        return {str(row["migration_id"]) for row in rows}

    def apply_migrations(self, migrations: Iterable[Migration]) -> list[str]:
        self.ensure_migration_table()
        applied = self.applied_migrations()
        newly_applied: list[str] = []
        with self.transaction():
            for migration in migrations:
                migration_id = migration.migration_id.strip()
                if not migration_id:
                    raise ValueError("migration_id is required")
                if migration_id in applied:
                    continue
                self._execute_migration_sql(migration.sql)
                self.execute(
                    f"INSERT INTO schema_migrations (migration_id) VALUES ({self._param()})",
                    [migration_id],
                )
                applied.add(migration_id)
                newly_applied.append(migration_id)
        return newly_applied


def _sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(f"Not a sqlite URL: {database_url!r}")
    return Path(database_url[len(prefix) :])


def connect_store(config: StorageConfig) -> SqlStore:
    backend = config.backend
    if backend == "sqlite":
        path = _sqlite_path_from_url(config.database_url) if config.database_url else config.sqlite_path
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        return SqlStore(connection, backend="sqlite")
    if backend == "postgres":
        try:
            import psycopg  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "PostgreSQL storage requires the optional psycopg driver. "
                "Install/configure it before using SELLERONE_DATABASE_URL=postgresql://..."
            ) from exc
        return SqlStore(psycopg.connect(config.database_url), backend="postgres")
    raise ValueError(f"Unsupported backend: {backend}")
