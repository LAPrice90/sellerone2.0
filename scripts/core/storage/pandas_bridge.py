from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from scripts.core.safe_file_writes import safe_to_csv
from scripts.core.storage.adapter import SqlStore, connect_store
from scripts.core.storage.config import StorageConfig, parse_storage_mode


_VALID_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(identifier: str) -> str:
    value = str(identifier or "").strip()
    if not _VALID_IDENTIFIER_RE.match(value):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return value


def quote_identifier(identifier: str) -> str:
    value = validate_identifier(identifier)
    return f'"{value}"'


def _normalize_column_names(columns: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for index, column in enumerate(columns):
        raw = str(column or "").strip()
        base = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_").lower()
        if not base:
            base = f"column_{index + 1}"
        if base[0].isdigit():
            base = f"col_{base}"
        name = base
        suffix = 2
        while name in seen:
            name = f"{base}_{suffix}"
            suffix += 1
        validate_identifier(name)
        normalized.append(name)
        seen.add(name)
    return normalized


def _prepared_table(table_name: str, dataframe: pd.DataFrame) -> dict[str, object]:
    table = validate_identifier(table_name)
    columns = _normalize_column_names(dataframe.columns)
    original_columns = [str(column or "") for column in dataframe.columns]
    rows = list(
        dataframe.where(pd.notna(dataframe), "")
        .astype(str)
        .itertuples(index=False, name=None)
    )
    return {
        "table": table,
        "columns": columns,
        "original_columns": original_columns,
        "rows": rows,
        "row_count": int(len(dataframe.index)),
    }


def replace_tables_from_dataframes(store: SqlStore, tables: Mapping[str, pd.DataFrame]) -> list[dict[str, object]]:
    prepared = [_prepared_table(table_name, dataframe) for table_name, dataframe in tables.items()]
    with store.transaction():
        if store.backend == "sqlite":
            store.execute(
                """
                CREATE TABLE IF NOT EXISTS storage_column_metadata (
                    table_name TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    sql_column_name TEXT NOT NULL,
                    original_column_name TEXT NOT NULL,
                    PRIMARY KEY (table_name, ordinal)
                )
                """
            )
        else:
            store.execute(
                """
                CREATE TABLE IF NOT EXISTS storage_column_metadata (
                    table_name TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    sql_column_name TEXT NOT NULL,
                    original_column_name TEXT NOT NULL,
                    PRIMARY KEY (table_name, ordinal)
                )
                """
            )
        for item in prepared:
            table = str(item["table"])
            columns = list(item["columns"])
            original_columns = list(item["original_columns"])
            quoted_table = quote_identifier(table)
            quoted_columns = [quote_identifier(column) for column in columns]
            create_columns = ", ".join(f"{column} TEXT" for column in quoted_columns)
            placeholders = ", ".join([store._param()] * len(columns))
            insert_columns = ", ".join(quoted_columns)

            store.execute(f"DROP TABLE IF EXISTS {quoted_table}")
            store.execute(f"CREATE TABLE {quoted_table} ({create_columns})")
            store.execute(
                f"DELETE FROM storage_column_metadata WHERE table_name = {store._param()}",
                [table],
            )
            store.execute_many(
                (
                    "INSERT INTO storage_column_metadata "
                    f"(table_name, ordinal, sql_column_name, original_column_name) "
                    f"VALUES ({store._param()}, {store._param()}, {store._param()}, {store._param()})"
                ),
                [
                    (table, ordinal, sql_column, original_column)
                    for ordinal, (sql_column, original_column) in enumerate(zip(columns, original_columns))
                ],
            )
            if item["rows"]:
                store.execute_many(
                    f"INSERT INTO {quoted_table} ({insert_columns}) VALUES ({placeholders})",
                    item["rows"],
                )

    return [
        {
            "table": str(item["table"]),
            "rows": int(item["row_count"]),
            "columns": list(item["columns"]),
            "original_columns": list(item["original_columns"]),
        }
        for item in prepared
    ]


def replace_table_from_dataframe(store: SqlStore, table_name: str, dataframe: pd.DataFrame) -> dict[str, object]:
    result = replace_tables_from_dataframes(store, {table_name: dataframe})[0]
    return result


def write_dataframe_with_sql_compat(dataframe: pd.DataFrame, path: str | Path, table_name: str) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE"))
    sql_rows = 0
    if mode in {"sql_shadow", "sql_primary_csv_export"}:
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, table_name, dataframe)
            sql_rows = int(result["rows"])
        finally:
            store.close()
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(dataframe, csv_path, index=False)
    return {
        "mode": mode,
        "path": str(csv_path),
        "csv_rows": int(len(dataframe.index)),
        "sql_table": table_name if mode != "csv" else "",
        "sql_rows": sql_rows,
    }


def _table_columns_from_metadata(store: SqlStore, table_name: str) -> list[str]:
    if not store.table_exists("storage_column_metadata"):
        return []
    table = validate_identifier(table_name)
    rows = store.query_all(
        f"""
        SELECT original_column_name
        FROM storage_column_metadata
        WHERE table_name = {store._param()}
        ORDER BY ordinal
        """,
        [table],
    )
    return [str(row["original_column_name"]) for row in rows]


def _table_sql_columns(store: SqlStore, table_name: str) -> list[str]:
    table = validate_identifier(table_name)
    if store.backend == "sqlite":
        rows = store.query_all(f"PRAGMA table_info({quote_identifier(table)})")
        return [str(row["name"]) for row in rows]
    rows = store.query_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        [table],
    )
    return [str(row["column_name"]) for row in rows]


def read_dataframe_with_sql_fallback(
    path: str | Path,
    table_name: str,
    **read_csv_kwargs: object,
) -> pd.DataFrame:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE"))
    csv_path = Path(path)
    if mode == "sql_shadow" and csv_path.exists():
        return pd.read_csv(csv_path, **read_csv_kwargs)
    if mode in {"sql_shadow", "sql_primary_csv_export"}:
        store = connect_store(StorageConfig.from_env())
        try:
            table = validate_identifier(table_name)
            if store.table_exists(table):
                quoted_table = quote_identifier(table)
                df = pd.read_sql_query(f"SELECT * FROM {quoted_table}", store.connection)
                original_columns = _table_columns_from_metadata(store, table)
                if original_columns and len(original_columns) == len(df.columns):
                    df.columns = original_columns
                elif csv_path.exists():
                    csv_columns = pd.read_csv(csv_path, nrows=0, **read_csv_kwargs).columns.tolist()
                    if len(csv_columns) == len(df.columns):
                        df.columns = csv_columns
                usecols = read_csv_kwargs.get("usecols")
                if usecols is not None:
                    df = df.loc[:, list(usecols)]
                return df.fillna("")
        finally:
            store.close()
    return pd.read_csv(csv_path, **read_csv_kwargs)
