from __future__ import annotations

from scripts.core.storage.adapter import Migration, SqlStore, connect_store
from scripts.core.storage.config import StorageConfig, parse_storage_mode
from scripts.core.storage.pandas_bridge import (
    read_dataframe_with_sql_fallback,
    replace_table_from_dataframe,
    replace_tables_from_dataframes,
    write_dataframe_with_sql_compat,
)
from scripts.core.storage.feeder_review import (
    SQL_TABLE_FEEDER_REVIEW_EVENTS,
    SQL_TABLE_FEEDER_REVIEW_UI_DRAFTS,
    SQL_TABLE_REVIEW_PACK_ROWS,
    SQL_TABLE_REVIEW_SUMMARY,
    list_review_summary_snapshots,
    read_review_pack_dataframe,
    read_review_summary_dataframe,
    write_review_pack_snapshots_sql_compat,
)
from scripts.core.storage.product_db_contract import (
    PRODUCT_DB_REQUIRED_COLUMNS,
    SQL_TABLE_PRODUCT_DB_PRODUCTS,
    build_product_db_import_rows,
    coalesce_duplicate_header_rows,
    dataframe_from_product_db_sheet_rows,
    duplicate_header_names,
    load_product_db_for_validation,
    load_product_db_products_from_sqlite,
    product_db_create_table_sql,
    product_db_indexes_sql,
    stage_product_db_import_sqlite,
    validate_product_db_dataframe,
)

__all__ = [
    "Migration",
    "SqlStore",
    "StorageConfig",
    "SQL_TABLE_FEEDER_REVIEW_EVENTS",
    "SQL_TABLE_FEEDER_REVIEW_UI_DRAFTS",
    "SQL_TABLE_PRODUCT_DB_PRODUCTS",
    "SQL_TABLE_REVIEW_PACK_ROWS",
    "SQL_TABLE_REVIEW_SUMMARY",
    "connect_store",
    "PRODUCT_DB_REQUIRED_COLUMNS",
    "build_product_db_import_rows",
    "coalesce_duplicate_header_rows",
    "dataframe_from_product_db_sheet_rows",
    "duplicate_header_names",
    "list_review_summary_snapshots",
    "load_product_db_for_validation",
    "load_product_db_products_from_sqlite",
    "parse_storage_mode",
    "product_db_create_table_sql",
    "product_db_indexes_sql",
    "read_dataframe_with_sql_fallback",
    "read_review_pack_dataframe",
    "read_review_summary_dataframe",
    "replace_table_from_dataframe",
    "replace_tables_from_dataframes",
    "stage_product_db_import_sqlite",
    "validate_product_db_dataframe",
    "write_dataframe_with_sql_compat",
    "write_review_pack_snapshots_sql_compat",
]
