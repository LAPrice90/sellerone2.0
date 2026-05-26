from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.core.storage.adapter import SqlStore, connect_store
from scripts.core.storage.config import StorageConfig, parse_storage_mode
from scripts.core.storage.pandas_bridge import quote_identifier


SQL_TABLE_REVIEW_PACK_ROWS = "f_new_product_review_pack_rows"
SQL_TABLE_REVIEW_SUMMARY = "f_new_product_review_summary"
SQL_TABLE_FEEDER_REVIEW_EVENTS = "f_feeder_review_events"
SQL_TABLE_FEEDER_REVIEW_UI_DRAFTS = "o_feeder_review_ui_drafts"


def _sql_storage_enabled() -> bool:
    return parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE")) in {
        "sql_shadow",
        "sql_primary_csv_export",
    }


def _clean_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    return dataframe.where(pd.notna(dataframe), "").astype(str)


def _connect_store_if_enabled() -> SqlStore | None:
    if not _sql_storage_enabled():
        return None
    return connect_store(StorageConfig.from_env())


def _ensure_review_tables(store: SqlStore) -> None:
    store.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(SQL_TABLE_REVIEW_PACK_ROWS)} (
            review_pack_snapshot TEXT NOT NULL,
            review_pack_type TEXT NOT NULL,
            row_ordinal INTEGER NOT NULL,
            row_json TEXT NOT NULL,
            observed_utc TEXT NOT NULL,
            active_supplier_id TEXT NOT NULL,
            active_run_id TEXT NOT NULL,
            review_batch_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            supplier_sku TEXT NOT NULL,
            asin TEXT NOT NULL,
            PRIMARY KEY (review_pack_snapshot, review_pack_type, row_ordinal)
        )
        """
    )
    store.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {quote_identifier(SQL_TABLE_REVIEW_SUMMARY)} (
            review_pack_snapshot TEXT NOT NULL,
            row_ordinal INTEGER NOT NULL,
            observed_utc TEXT NOT NULL,
            metric TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (review_pack_snapshot, row_ordinal)
        )
        """
    )


def _record_value(record: dict[str, Any], key: str) -> str:
    return str(record.get(key, "") or "")


def _pack_rows(
    dataframe: pd.DataFrame,
    *,
    snapshot: str,
    pack_type: str,
) -> list[tuple[str, str, int, str, str, str, str, str, str, str, str]]:
    clean = _clean_dataframe(dataframe)
    rows: list[tuple[str, str, int, str, str, str, str, str, str, str, str]] = []
    for ordinal, record in enumerate(clean.to_dict("records")):
        rows.append(
            (
                snapshot,
                pack_type,
                ordinal,
                json.dumps(record, ensure_ascii=True, sort_keys=True),
                _record_value(record, "observed_utc"),
                _record_value(record, "active_supplier_id"),
                _record_value(record, "active_run_id"),
                _record_value(record, "review_batch_id"),
                _record_value(record, "candidate_id"),
                _record_value(record, "supplier_sku"),
                _record_value(record, "asin"),
            )
        )
    return rows


def _summary_rows(dataframe: pd.DataFrame, *, snapshot: str) -> list[tuple[str, int, str, str, str]]:
    clean = _clean_dataframe(dataframe)
    rows: list[tuple[str, int, str, str, str]] = []
    for ordinal, record in enumerate(clean.to_dict("records")):
        rows.append(
            (
                snapshot,
                ordinal,
                _record_value(record, "observed_utc"),
                _record_value(record, "metric"),
                _record_value(record, "value"),
            )
        )
    return rows


def write_review_pack_snapshots_sql_compat(
    *,
    pass_df: pd.DataFrame,
    near_miss_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    snapshot_id: str,
) -> dict[str, object]:
    store = _connect_store_if_enabled()
    if store is None:
        return {
            "mode": "csv",
            "snapshot_id": snapshot_id,
            "sql_pack_rows": 0,
            "sql_summary_rows": 0,
        }
    try:
        pack_rows: list[tuple[str, str, int, str, str, str, str, str, str, str, str]] = []
        summary_rows: list[tuple[str, int, str, str, str]] = []
        for target_snapshot in (snapshot_id, "latest"):
            pack_rows.extend(_pack_rows(pass_df, snapshot=target_snapshot, pack_type="passes"))
            pack_rows.extend(_pack_rows(near_miss_df, snapshot=target_snapshot, pack_type="near_misses"))
            summary_rows.extend(_summary_rows(summary_df, snapshot=target_snapshot))

        with store.transaction():
            _ensure_review_tables(store)
            for target_snapshot in (snapshot_id, "latest"):
                store.execute(
                    (
                        f"DELETE FROM {quote_identifier(SQL_TABLE_REVIEW_PACK_ROWS)} "
                        f"WHERE review_pack_snapshot = {store._param()}"
                    ),
                    [target_snapshot],
                )
                store.execute(
                    (
                        f"DELETE FROM {quote_identifier(SQL_TABLE_REVIEW_SUMMARY)} "
                        f"WHERE review_pack_snapshot = {store._param()}"
                    ),
                    [target_snapshot],
                )
            if pack_rows:
                store.execute_many(
                    (
                        f"INSERT INTO {quote_identifier(SQL_TABLE_REVIEW_PACK_ROWS)} "
                        "(review_pack_snapshot, review_pack_type, row_ordinal, row_json, observed_utc, "
                        "active_supplier_id, active_run_id, review_batch_id, candidate_id, supplier_sku, asin) "
                        f"VALUES ({', '.join([store._param()] * 11)})"
                    ),
                    pack_rows,
                )
            if summary_rows:
                store.execute_many(
                    (
                        f"INSERT INTO {quote_identifier(SQL_TABLE_REVIEW_SUMMARY)} "
                        "(review_pack_snapshot, row_ordinal, observed_utc, metric, value) "
                        f"VALUES ({', '.join([store._param()] * 5)})"
                    ),
                    summary_rows,
                )
        return {
            "mode": parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE")),
            "snapshot_id": snapshot_id,
            "sql_pack_rows": len(pack_rows),
            "sql_summary_rows": len(summary_rows),
        }
    finally:
        store.close()


def _read_csv_or_empty(path: str | Path, **read_csv_kwargs: object) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(csv_path, **read_csv_kwargs).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def read_review_pack_dataframe(
    path: str | Path,
    *,
    pack_type: str,
    snapshot_id: str = "latest",
    **read_csv_kwargs: object,
) -> pd.DataFrame:
    store = _connect_store_if_enabled()
    if store is not None:
        try:
            if store.table_exists(SQL_TABLE_REVIEW_PACK_ROWS):
                rows = store.query_all(
                    (
                        f"SELECT row_json FROM {quote_identifier(SQL_TABLE_REVIEW_PACK_ROWS)} "
                        f"WHERE review_pack_snapshot = {store._param()} "
                        f"AND review_pack_type = {store._param()} "
                        "ORDER BY row_ordinal"
                    ),
                    [snapshot_id or "latest", pack_type],
                )
                if rows:
                    return pd.DataFrame([json.loads(str(row["row_json"])) for row in rows]).fillna("")
        finally:
            store.close()
    return _read_csv_or_empty(path, **read_csv_kwargs)


def read_review_summary_dataframe(
    path: str | Path,
    *,
    snapshot_id: str = "latest",
    **read_csv_kwargs: object,
) -> pd.DataFrame:
    store = _connect_store_if_enabled()
    if store is not None:
        try:
            if store.table_exists(SQL_TABLE_REVIEW_SUMMARY):
                rows = store.query_all(
                    (
                        f"SELECT observed_utc, metric, value FROM {quote_identifier(SQL_TABLE_REVIEW_SUMMARY)} "
                        f"WHERE review_pack_snapshot = {store._param()} "
                        "ORDER BY row_ordinal"
                    ),
                    [snapshot_id or "latest"],
                )
                if rows:
                    return pd.DataFrame(rows, columns=["observed_utc", "metric", "value"]).fillna("")
        finally:
            store.close()
    return _read_csv_or_empty(path, **read_csv_kwargs)


def list_review_summary_snapshots() -> list[str]:
    store = _connect_store_if_enabled()
    if store is None:
        return []
    try:
        if not store.table_exists(SQL_TABLE_REVIEW_SUMMARY):
            return []
        rows = store.query_all(
            (
                f"SELECT DISTINCT review_pack_snapshot FROM {quote_identifier(SQL_TABLE_REVIEW_SUMMARY)} "
                "WHERE review_pack_snapshot <> 'latest' "
                "ORDER BY review_pack_snapshot DESC"
            )
        )
        return [str(row["review_pack_snapshot"]) for row in rows]
    finally:
        store.close()
