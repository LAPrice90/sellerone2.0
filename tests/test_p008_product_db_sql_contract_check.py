from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS
from scripts.one_off.P008_product_db_sql_contract_check import run_contract_check


def _write_product_db(path: Path, *, duplicate_header: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: "" for column in PRODUCT_DB_REQUIRED_COLUMNS}
    row.update(
        {
            "seller_sku": "SKU-1",
            "asin": "ASIN-1",
            "title": "Product One",
            "brand_name": "Brand",
            "main_image": "image",
            "sale_status": "active",
            "supplier_code": "SUP",
            "supplier_name": "Supplier",
            "supplier_pack_size": "1",
            "amazon_pack_size": "1",
            "supplier_catalog_price": "2.50",
            "last_purchase_price": "2.40",
            "vat_rate": "20",
            "fba_fee_10": "1",
            "fba_fee_100": "2",
            "referral_fee_10": "0.5",
            "referral_fee_100": "1.5",
            "live_listing_price": "9.99",
            "stock_total": "3",
            "stock_available": "2",
            "stock_reserved": "1",
            "stock_inbound": "0",
            "last_updated": "2026-05-01T10:00:00Z",
        }
    )
    if duplicate_header:
        headers = [*PRODUCT_DB_REQUIRED_COLUMNS, "last_updated_A003", "last_updated_A003"]
        values = [str(row.get(column, "")) for column in PRODUCT_DB_REQUIRED_COLUMNS] + ["a", "b"]
        path.write_text(",".join(headers) + "\n" + ",".join(values) + "\n", encoding="utf-8")
    else:
        pd.DataFrame([row], columns=list(PRODUCT_DB_REQUIRED_COLUMNS)).to_csv(path, index=False)


def test_p008_writes_contract_reports_and_stages_clean_source(tmp_path: Path) -> None:
    source = tmp_path / "out" / "product_db_preview.csv"
    output_dir = tmp_path / "out" / "sql_migration" / "product_db_contract"
    sqlite_path = output_dir / "staging.sqlite3"
    _write_product_db(source)

    payload = run_contract_check(source_path=source, output_dir=output_dir, staging_sqlite_path=sqlite_path)

    assert payload["status"] == "ok"
    assert payload["source_rows"] == 1
    assert payload["staged_import"]["status"] == "passed"
    assert (output_dir / "product_db_sql_contract_check.csv").exists()
    assert (output_dir / "product_db_duplicate_asin_review.csv").exists()
    summary = json.loads((output_dir / "product_db_sql_contract_summary.json").read_text(encoding="utf-8"))
    assert summary["staged_import"]["rows"] == "1"
    conn = sqlite3.connect(sqlite_path)
    try:
        count = conn.execute("select count(*) from product_db_products").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_p008_blocks_staged_import_when_source_has_duplicate_headers(tmp_path: Path) -> None:
    source = tmp_path / "out" / "product_db_preview.csv"
    output_dir = tmp_path / "out" / "sql_migration" / "product_db_contract"
    sqlite_path = output_dir / "staging.sqlite3"
    _write_product_db(source, duplicate_header=True)

    payload = run_contract_check(source_path=source, output_dir=output_dir, staging_sqlite_path=sqlite_path)

    assert payload["status"] == "fail"
    assert payload["staged_import"]["status"] == "skipped"
    checks = pd.read_csv(output_dir / "product_db_sql_contract_check.csv", dtype=str).fillna("")
    duplicate_header = checks[checks["check"] == "product_db_unique_headers"].iloc[0]
    assert duplicate_header["status"] == "fail"
    assert not sqlite_path.exists()
