from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import (
    PRODUCT_DB_REQUIRED_COLUMNS,
    SQL_TABLE_PRODUCT_DB_PRODUCTS,
    coalesce_duplicate_header_rows,
    dataframe_from_product_db_sheet_rows,
    duplicate_header_names,
    product_db_create_table_sql,
    product_db_indexes_sql,
    load_product_db_products_from_sqlite,
    stage_product_db_import_sqlite,
    validate_product_db_dataframe,
)


def _valid_product_df() -> pd.DataFrame:
    row = {column: "" for column in PRODUCT_DB_REQUIRED_COLUMNS}
    row.update(
        {
            "seller_sku": "SKU-1",
            "asin": "ASIN-1",
            "title": "Product One",
            "brand_name": "Brand",
            "main_image": "https://example.invalid/image.jpg",
            "sale_status": "active",
            "supplier_code": "SUP",
            "supplier_name": "Supplier",
            "supplier_pack_size": "1",
            "amazon_pack_size": "1",
            "supplier_catalog_price": "2.50",
            "last_purchase_price": "2.40",
            "vat_rate": "20",
            "fba_fee_10": "1.00",
            "fba_fee_100": "1.50",
            "referral_fee_10": "0.50",
            "referral_fee_100": "2.00",
            "live_listing_price": "9.99",
            "stock_total": "3",
            "stock_available": "2",
            "stock_reserved": "1",
            "stock_inbound": "0",
            "last_updated": "2026-05-01T10:00:00Z",
        }
    )
    return pd.DataFrame([row])


def test_product_db_sql_contract_declares_seller_sku_primary_key_and_non_unique_asin() -> None:
    sql = product_db_create_table_sql()
    indexes = "\n".join(product_db_indexes_sql())

    assert '"seller_sku" TEXT PRIMARY KEY' in sql
    assert '"asin" TEXT PRIMARY KEY' not in sql
    assert "UNIQUE" not in indexes.upper()
    assert "idx_product_db_products_asin" in indexes


def test_product_db_validation_blocks_duplicate_headers_and_duplicate_skus() -> None:
    df = _valid_product_df()
    df = pd.concat([df, df.assign(seller_sku="SKU-1")], ignore_index=True)

    result = validate_product_db_dataframe(
        df,
        raw_headers=[*PRODUCT_DB_REQUIRED_COLUMNS, "last_updated_A003", "last_updated_A003"],
        source_path="out/product_db_preview.csv",
        observed_utc="2026-05-01T10:00:00Z",
    )
    by_check = {row["check"]: row for row in result.checks}

    assert duplicate_header_names(["a", "b", "a"]) == ["a"]
    assert result.status == "fail"
    assert by_check["product_db_unique_headers"]["status"] == "fail"
    assert by_check["product_db_seller_sku_unique"]["status"] == "fail"


def test_product_db_header_repair_keeps_rightmost_duplicate_and_fills_blanks() -> None:
    rows = [
        ["last_updated_A003", "seller_sku", "asin", "last_updated_A003", "last_updated_A004"],
        ["old-a", "SKU-1", "ASIN-1", "", "a004"],
        ["old-b", "SKU-2", "ASIN-2", "new-b", "a004"],
    ]

    repaired_rows, repaired_headers = coalesce_duplicate_header_rows(rows)
    df, df_repaired_headers = dataframe_from_product_db_sheet_rows(rows)

    assert repaired_headers == ["last_updated_A003"]
    assert df_repaired_headers == ["last_updated_A003"]
    assert repaired_rows == [
        ["seller_sku", "asin", "last_updated_A003", "last_updated_A004"],
        ["SKU-1", "ASIN-1", "old-a", "a004"],
        ["SKU-2", "ASIN-2", "new-b", "a004"],
    ]
    assert list(df.columns) == ["seller_sku", "asin", "last_updated_A003", "last_updated_A004"]
    assert df.loc[0, "last_updated_A003"] == "old-a"
    assert df.loc[1, "last_updated_A003"] == "new-b"


def test_product_db_validation_warns_for_controlled_duplicate_asin() -> None:
    df = pd.concat(
        [
            _valid_product_df(),
            _valid_product_df().assign(seller_sku="SKU-2", asin="ASIN-1"),
        ],
        ignore_index=True,
    )

    result = validate_product_db_dataframe(
        df,
        raw_headers=list(df.columns),
        source_path="out/product_db_preview.csv",
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert result.status == "warn"
    assert result.duplicate_asin_rows == [
        {
            "asin": "ASIN-1",
            "match_count": "2",
            "seller_skus": "SKU-1|SKU-2",
            "action": "REVIEW",
            "reason": "duplicate_product_db_asin_requires_classification",
        }
    ]


def test_stage_product_db_import_sqlite_uses_contract_table(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "product_db_stage.sqlite3"

    result = stage_product_db_import_sqlite(
        df=_valid_product_df(),
        sqlite_path=sqlite_path,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert result["table"] == SQL_TABLE_PRODUCT_DB_PRODUCTS
    assert result["rows"] == "1"
    conn = sqlite3.connect(sqlite_path)
    try:
        schema = conn.execute("PRAGMA table_info(product_db_products)").fetchall()
        rows = conn.execute("select seller_sku, asin from product_db_products").fetchall()
    finally:
        conn.close()
    pk_cols = [row[1] for row in schema if row[5] == 1]
    assert pk_cols == ["seller_sku"]
    assert rows == [("SKU-1", "ASIN-1")]


def test_load_product_db_products_from_sqlite_restores_source_payload_columns(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "product_db.sqlite3"
    source = pd.DataFrame(
        [
            {
                **_valid_product_df().iloc[0].to_dict(),
                "supplier_sku": "SUP-1",
                "order_qty_mode": "raw_units",
                "supplier_case_qty": "12",
            }
        ]
    )
    stage_product_db_import_sqlite(
        df=source,
        sqlite_path=sqlite_path,
        observed_utc="2026-05-01T10:00:00Z",
    )

    restored = load_product_db_products_from_sqlite(sqlite_path)

    assert len(restored.index) == 1
    assert restored.iloc[0]["seller_sku"] == "SKU-1"
    assert restored.iloc[0]["supplier_sku"] == "SUP-1"
    assert restored.iloc[0]["supplier_case_qty"] == "12"
