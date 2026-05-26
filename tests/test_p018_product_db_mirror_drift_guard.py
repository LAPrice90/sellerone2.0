from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS, stage_product_db_import_sqlite
from scripts.flows.O._contract_io import write_o_contract_df
from scripts.one_off.P018_product_db_mirror_drift_guard import run_check


def _product_row(seller_sku: str, asin: str) -> dict[str, str]:
    row = {column: "" for column in PRODUCT_DB_REQUIRED_COLUMNS}
    row.update(
        {
            "seller_sku": seller_sku,
            "asin": asin,
            "title": f"Title {seller_sku}",
            "sale_status": "active",
            "supplier_code": "SUP",
            "supplier_name": "Supplier",
            "supplier_pack_size": "1",
            "amazon_pack_size": "1",
            "supplier_catalog_price": "1.00",
            "last_purchase_price": "1.00",
            "vat_rate": "20",
            "stock_total": "0",
            "stock_available": "0",
            "stock_reserved": "0",
            "stock_inbound": "0",
            "last_updated": "2026-05-01T10:00:00Z",
        }
    )
    return row


def test_p018_warns_for_stale_csv_but_keeps_sql_and_o_as_authority(tmp_path: Path) -> None:
    sql_df = pd.DataFrame([_product_row("SKU-1", "ASIN-1"), _product_row("SKU-2", "ASIN-2")])
    sqlite_path = tmp_path / "out" / "sql" / "sellerone_dev.sqlite3"
    stage_product_db_import_sqlite(df=sql_df, sqlite_path=sqlite_path, observed_utc="2026-05-01T10:00:00Z")
    mirror_path = tmp_path / "out" / "product_db_preview.csv"
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([_product_row("SKU-1", "ASIN-1")]).to_csv(mirror_path, index=False)
    write_o_contract_df(tmp_path, "product_db_operator_view", pd.DataFrame([{"seller_sku": "SKU-1"}, {"seller_sku": "SKU-2"}]))
    write_o_contract_df(tmp_path, "product_db_source_health", pd.DataFrame([{"check": "product_db_source_exists", "status": "ok", "value": "1", "notes": "sql_product_db_products present", "observed_utc": "", "source_path": str(sqlite_path)}]))

    payload = run_check(root=tmp_path, sqlite_path=sqlite_path, product_db_mirror=mirror_path, output_dir=tmp_path / "proof", observed_utc="2026-05-01T11:00:00Z")

    assert payload["status"] == "warn"
    assert payload["fail_count"] == 0
    assert payload["csv_mirror_authority_status"] == "mirror_stale_not_authority"
    assert payload["p014_loaded_source_mode"] == "sql"


def test_p018_fails_when_o_view_does_not_match_sql(tmp_path: Path) -> None:
    sql_df = pd.DataFrame([_product_row("SKU-1", "ASIN-1")])
    sqlite_path = tmp_path / "out" / "sql" / "sellerone_dev.sqlite3"
    stage_product_db_import_sqlite(df=sql_df, sqlite_path=sqlite_path, observed_utc="2026-05-01T10:00:00Z")
    mirror_path = tmp_path / "out" / "product_db_preview.csv"
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    sql_df.to_csv(mirror_path, index=False)
    write_o_contract_df(tmp_path, "product_db_operator_view", pd.DataFrame([{"seller_sku": "SKU-OTHER"}]))
    write_o_contract_df(tmp_path, "product_db_source_health", pd.DataFrame([{"check": "product_db_source_exists", "status": "ok", "value": "1", "notes": "sql_product_db_products present", "observed_utc": "", "source_path": str(sqlite_path)}]))

    payload = run_check(root=tmp_path, sqlite_path=sqlite_path, product_db_mirror=mirror_path, output_dir=tmp_path / "proof", observed_utc="2026-05-01T11:00:00Z")

    assert payload["status"] == "fail"
    checks = pd.read_csv(tmp_path / "proof" / "product_db_mirror_drift_guard.csv", dtype=str).fillna("")
    o_check = checks[checks["check"].eq("o_product_db_view_matches_sql")].iloc[0]
    assert o_check["status"] == "fail"
