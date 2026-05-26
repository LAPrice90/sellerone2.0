from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS, stage_product_db_import_sqlite
from scripts.flows.O._contract_io import write_o_contract_df
from scripts.one_off.P015_product_db_sql_authority_rehearsal import run_check


def _product_row(seller_sku: str, asin: str) -> dict[str, str]:
    row = {column: "" for column in PRODUCT_DB_REQUIRED_COLUMNS}
    row.update(
        {
            "seller_sku": seller_sku,
            "asin": asin,
            "title": f"Title {seller_sku}",
            "brand_name": "Brand",
            "main_image": "",
            "sale_status": "active",
            "supplier_code": "SUP",
            "supplier_name": "Supplier",
            "supplier_pack_size": "1",
            "amazon_pack_size": "1",
            "supplier_catalog_price": "1.00",
            "last_purchase_price": "1.00",
            "vat_rate": "20",
            "fba_fee_10": "",
            "fba_fee_100": "",
            "referral_fee_10": "",
            "referral_fee_100": "",
            "live_listing_price": "",
            "stock_total": "0",
            "stock_available": "0",
            "stock_reserved": "0",
            "stock_inbound": "0",
            "last_updated": "2026-05-01T10:00:00Z",
        }
    )
    return row


def test_p015_warns_when_csv_mirror_is_stale_but_o_view_matches_sql(tmp_path: Path) -> None:
    sql_df = pd.DataFrame([_product_row("SKU-1", "ASIN-1"), _product_row("SKU-2", "ASIN-2")])
    sqlite_path = tmp_path / "out" / "sql" / "sellerone_dev.sqlite3"
    stage_product_db_import_sqlite(df=sql_df, sqlite_path=sqlite_path, observed_utc="2026-05-01T10:00:00Z")
    mirror_path = tmp_path / "out" / "product_db_preview.csv"
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([_product_row("SKU-1", "ASIN-1")]).to_csv(mirror_path, index=False)
    write_o_contract_df(
        tmp_path,
        "product_db_operator_view",
        pd.DataFrame(
            [
                {"seller_sku": "SKU-1", "asin": "ASIN-1"},
                {"seller_sku": "SKU-2", "asin": "ASIN-2"},
            ]
        ),
    )

    payload = run_check(
        root=tmp_path,
        sqlite_path=sqlite_path,
        product_db_mirror=mirror_path,
        output_dir=tmp_path / "proof",
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "warn"
    assert payload["sql_rows"] == 2
    assert payload["csv_mirror_rows"] == 1
    checks = pd.read_csv(tmp_path / "proof" / "product_db_sql_authority_rehearsal.csv", dtype=str).fillna("")
    csv_check = checks[checks["check"].eq("csv_mirror_rows_match_sql")].iloc[0]
    assert csv_check["status"] == "warn"
    o_check = checks[checks["check"].eq("o_product_db_operator_view_rows_match_sql")].iloc[0]
    assert o_check["status"] == "ok"


def test_p015_fails_when_o_view_does_not_match_sql(tmp_path: Path) -> None:
    sql_df = pd.DataFrame([_product_row("SKU-1", "ASIN-1")])
    sqlite_path = tmp_path / "out" / "sql" / "sellerone_dev.sqlite3"
    stage_product_db_import_sqlite(df=sql_df, sqlite_path=sqlite_path, observed_utc="2026-05-01T10:00:00Z")
    mirror_path = tmp_path / "out" / "product_db_preview.csv"
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    sql_df.to_csv(mirror_path, index=False)
    write_o_contract_df(
        tmp_path,
        "product_db_operator_view",
        pd.DataFrame([{"seller_sku": "SKU-OTHER", "asin": "ASIN-OTHER"}]),
    )

    payload = run_check(
        root=tmp_path,
        sqlite_path=sqlite_path,
        product_db_mirror=mirror_path,
        output_dir=tmp_path / "proof",
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "fail"
    checks = pd.read_csv(tmp_path / "proof" / "product_db_sql_authority_rehearsal.csv", dtype=str).fillna("")
    o_check = checks[checks["check"].eq("o_product_db_operator_view_rows_match_sql")].iloc[0]
    assert o_check["status"] == "fail"
