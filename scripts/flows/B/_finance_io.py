from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from scripts.core.storage import (
    StorageConfig,
    connect_store,
    parse_storage_mode,
    read_dataframe_with_sql_fallback,
    replace_table_from_dataframe,
    write_dataframe_with_sql_compat,
)


TABLE_BY_PATH = {
    "out/orders_raw.csv": "b_orders_raw",
    "out/order_items_raw.csv": "b_order_items_raw",
    "out/orders_all.csv": "b_orders_all",
    "out/order_items_all.csv": "b_order_items_all",
    "out/orders_pulled_last_run.csv": "b_orders_pulled_last_run",
    "out/financial_events_level1.csv": "b_financial_events_level1",
    "out/financial_events_level2.csv": "b_financial_events_level2",
    "out/order_master.csv": "b_order_master",
    "out/financial_events_level3_raw.csv": "b_financial_events_level3_raw",
    "out/financial_events_level3_raw_dedup.csv": "b_financial_events_level3_raw_dedup",
    "out/financial_events_level3_summary.csv": "b_financial_events_level3_summary",
    "out/financial_events_level3_official.csv": "b_financial_events_level3_official",
    "out/financial_events_account_ledger.csv": "b_financial_events_account_ledger",
    "out/financial_events_refunds.csv": "b_financial_events_refunds",
    "out/financial_events_refunds_official.csv": "b_financial_events_refunds_official",
    "out/financial_events_shipments.csv": "b_financial_events_shipments",
    "out/financial_events_inbound_summary.csv": "b_financial_events_inbound_summary",
    "out/financial_events_storage.csv": "b_financial_events_storage",
    "out/financial_events_storage_summary.csv": "b_financial_events_storage_summary",
    "out/financial_events_account_summary.csv": "b_financial_events_account_summary",
    "out/l2_vs_l3_discrepancies.csv": "b_l2_vs_l3_discrepancies",
    "out/vat_country_model.csv": "b_vat_country_model",
    "out/fee_country_model.csv": "b_fee_country_model",
    "out/orders_sheet_orders.csv": "b_orders_sheet_orders",
}


def table_for_path(path: str | Path) -> str:
    raw_path = Path(path)
    normalized = raw_path.as_posix()
    if normalized not in TABLE_BY_PATH:
        try:
            normalized = raw_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except Exception:
            pass
    table = TABLE_BY_PATH.get(normalized)
    if not table:
        raise KeyError(f"No SQL finance table registered for {normalized}")
    return table


def read_finance_frame(path: str | Path, table_name: str | None = None, **kwargs: object) -> pd.DataFrame:
    table = table_name or table_for_path(path)
    return read_dataframe_with_sql_fallback(path, table, **kwargs)


def write_finance_frame(dataframe: pd.DataFrame, path: str | Path, table_name: str | None = None) -> dict[str, object]:
    table = table_name or table_for_path(path)
    return write_dataframe_with_sql_compat(dataframe, path, table)


def replace_finance_table(dataframe: pd.DataFrame, table_name: str) -> int:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE"))
    if mode not in {"sql_shadow", "sql_primary_csv_export"}:
        return 0
    store = connect_store(StorageConfig.from_env())
    try:
        result = replace_table_from_dataframe(store, table_name, dataframe)
    finally:
        store.close()
    return int(result["rows"])


def sync_csv_to_finance_table(path: str | Path, table_name: str | None = None) -> int:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE"))
    csv_path = Path(path)
    if mode not in {"sql_shadow", "sql_primary_csv_export"} or not csv_path.exists():
        return 0
    table = table_name or table_for_path(csv_path)
    dataframe = pd.read_csv(csv_path, dtype=str).fillna("")
    return replace_finance_table(dataframe, table)
