from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS
from scripts.one_off.P011_apply_scanner_product_db_inserts import (
    DUPLICATE_ASIN_REASON,
    build_insert_plan,
    run_apply,
)


def _product_row(seller_sku: str, asin: str, *, status: str = "active") -> dict[str, str]:
    row = {column: "" for column in PRODUCT_DB_REQUIRED_COLUMNS}
    row.update(
        {
            "seller_sku": seller_sku,
            "asin": asin,
            "title": f"Title {asin}",
            "brand_name": "Brand",
            "main_image": "",
            "sale_status": status,
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


def _scanner_rows() -> list[dict[str, str]]:
    return [
        {
            "supplier": "Entertainment Trading",
            "supplier_sku": "SUP-1",
            "candidate_id": "C1",
            "asin": "ASIN-NEW",
            "title": "New one",
            "brand": "Brand",
            "cost": "2.50",
            "vat": "20",
            "buy_box_price": "9.99",
            "pf": "1.0",
            "recommendation_status": "PASS",
            "scan_day": "2026-05-01 10:00:00",
        },
        {
            "supplier": "Entertainment Trading",
            "supplier_sku": "SUP-2",
            "candidate_id": "C2",
            "asin": "ASIN-DUP-SCANNER",
            "title": "Dup A",
            "brand": "Brand",
            "cost": "3.50",
            "vat": "0.2",
            "buy_box_price": "10.99",
            "pf": "1.1",
            "recommendation_status": "PASS",
            "scan_day": "2026-05-01 11:00:00",
        },
        {
            "supplier": "Entertainment Trading",
            "supplier_sku": "SUP-3",
            "candidate_id": "C3",
            "asin": "ASIN-DUP-SCANNER",
            "title": "Dup B",
            "brand": "Brand",
            "cost": "4.50",
            "vat": "20",
            "buy_box_price": "11.99",
            "pf": "1.2",
            "recommendation_status": "PASS",
            "scan_day": "2026-05-01 12:00:00",
        },
        {
            "supplier": "Entertainment Trading",
            "supplier_sku": "SUP-4",
            "candidate_id": "C4",
            "asin": "ASIN-EXISTING",
            "title": "Existing",
            "brand": "Brand",
            "cost": "5.50",
            "vat": "20",
            "scan_day": "2026-05-01 13:00:00",
        },
    ]


def test_build_insert_plan_uses_np_skus_and_includes_duplicate_scanner_asin() -> None:
    product_db = pd.DataFrame([_product_row("SKU-EXISTING", "ASIN-EXISTING")], columns=PRODUCT_DB_REQUIRED_COLUMNS)
    scanner = pd.DataFrame(_scanner_rows())

    planned, events = build_insert_plan(
        scanner=scanner,
        product_db=product_db,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert len(planned) == 3
    assert all(str(value).startswith("NP-ENT-") for value in planned["seller_sku"].tolist())
    assert set(planned["asin"]) == {"ASIN-NEW", "ASIN-DUP-SCANNER"}
    assert planned.loc[planned["asin"].eq("ASIN-DUP-SCANNER"), "duplicate_asin_reason"].tolist() == [
        DUPLICATE_ASIN_REASON,
        DUPLICATE_ASIN_REASON,
    ]
    assert len(events) == 3
    assert all(row["apply_status"] == "planned" for row in events)


def test_run_apply_writes_sql_table_and_local_preview_mirror(tmp_path: Path) -> None:
    scanner_path = tmp_path / "scanner_latest.csv"
    product_db_path = tmp_path / "product_db_preview.csv"
    sqlite_path = tmp_path / "sellerone.sqlite3"
    output_dir = tmp_path / "proof"
    pd.DataFrame(_scanner_rows()).to_csv(scanner_path, index=False)
    pd.DataFrame(
        [
            _product_row("SKU-EXISTING", "ASIN-EXISTING"),
            _product_row("SKU-DUP-A", "ASIN-OLD-DUP"),
            _product_row("SKU-DUP-B", "ASIN-OLD-DUP"),
        ],
        columns=PRODUCT_DB_REQUIRED_COLUMNS,
    ).to_csv(product_db_path, index=False)

    payload = run_apply(
        scanner_path=scanner_path,
        product_db_path=product_db_path,
        sqlite_path=sqlite_path,
        output_dir=output_dir,
        apply=True,
        confirm_scanner_product_db_insert=True,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert payload["status"] == "applied"
    assert payload["planned_insert_rows"] == 3
    assert payload["final_product_db_rows"] == 6
    assert payload["sql_rows"] == 6
    assert payload["sql_unique_seller_sku"] == 6

    preview = pd.read_csv(product_db_path, dtype=str).fillna("")
    assert len(preview) == 6
    assert preview["seller_sku"].str.startswith("NP-ENT-").sum() == 3

    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(
            "select seller_sku, asin, duplicate_asin_reason, source_payload_json from product_db_products"
        ).fetchall()
    finally:
        conn.close()
    duplicate_reason_rows = [row for row in rows if row[2] == DUPLICATE_ASIN_REASON]
    assert len(duplicate_reason_rows) == 4
    assert "supplier_sku" in duplicate_reason_rows[-1][3]


def test_run_apply_requires_confirmation_for_write(tmp_path: Path) -> None:
    scanner_path = tmp_path / "scanner_latest.csv"
    product_db_path = tmp_path / "product_db_preview.csv"
    pd.DataFrame(_scanner_rows()).to_csv(scanner_path, index=False)
    pd.DataFrame([_product_row("SKU-EXISTING", "ASIN-EXISTING")], columns=PRODUCT_DB_REQUIRED_COLUMNS).to_csv(
        product_db_path,
        index=False,
    )

    payload = run_apply(
        scanner_path=scanner_path,
        product_db_path=product_db_path,
        sqlite_path=tmp_path / "sellerone.sqlite3",
        output_dir=tmp_path / "proof",
        apply=True,
        confirm_scanner_product_db_insert=False,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert payload["status"] == "confirmation_missing"
    assert not (tmp_path / "sellerone.sqlite3").exists()
