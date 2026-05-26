from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


VALID_STORAGE_MODES = {"csv", "sql_shadow", "sql_primary_csv_export"}


def parse_storage_mode(value: str | None) -> str:
    mode = str(value or "csv").strip().lower()
    if mode not in VALID_STORAGE_MODES:
        allowed = ", ".join(sorted(VALID_STORAGE_MODES))
        raise ValueError(f"Unsupported storage mode: {mode!r}. Expected one of: {allowed}")
    return mode


@dataclass(frozen=True)
class StorageConfig:
    mode: str = "csv"
    database_url: str = ""
    sqlite_path: Path = Path("out/sql/sellerone_dev.sqlite3")

    @property
    def backend(self) -> str:
        if self.database_url.startswith(("postgres://", "postgresql://")):
            return "postgres"
        if self.database_url.startswith("sqlite:///"):
            return "sqlite"
        if self.database_url:
            raise ValueError(f"Unsupported database URL: {self.database_url!r}")
        return "sqlite"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "StorageConfig":
        env = os.environ if environ is None else environ
        mode = parse_storage_mode(env.get("SELLERONE_STORAGE_MODE", "csv"))
        database_url = str(env.get("SELLERONE_DATABASE_URL", "")).strip()
        sqlite_path = Path(env.get("SELLERONE_SQLITE_PATH", "out/sql/sellerone_dev.sqlite3"))
        return cls(mode=mode, database_url=database_url, sqlite_path=sqlite_path)
