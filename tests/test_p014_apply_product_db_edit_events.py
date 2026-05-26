from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS, stage_product_db_import_sqlite
from scripts.flows.O.O420_product_database_edit_ui import submit_product_db_edit
from scripts.one_off.P014_apply_product_db_edit_events import run_apply


def _product_row(seller_sku: str, asin: str, *, supplier_name: str = "Supplier") -> dict[str, str]:
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
            "supplier_name": supplier_name,
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
            "supplier_sku": "SUP-1",
            "barcode": "123456",
            "order_qty_mode": "raw_units",
            "sell_pack_qty": "",
            "supplier_case_qty": "6",
            "supplier_case_multiple": "1",
            "valid_order_step": "6",
            "repack_required": "0",
            "bundle_required": "0",
            "pack_conversion_note": "",
            "moq": "1",
            "target_margin": "0.2",
            "notes": "old note",
        }
    )
    return row


def _write_product_db(tmp_path: Path, rows: list[dict[str, str]]) -> tuple[Path, Path]:
    product_db_path = tmp_path / "product_db_preview.csv"
    sqlite_path = tmp_path / "sellerone.sqlite3"
    df = pd.DataFrame(rows).fillna("")
    df.to_csv(product_db_path, index=False)
    stage_product_db_import_sqlite(df=df, sqlite_path=sqlite_path, observed_utc="2026-05-01T10:00:00Z")
    return product_db_path, sqlite_path


def _valid_edit_payload(*, asin: str = "ASIN-1", supplier_name: str = "New Supplier") -> dict[str, object]:
    return {
        "seller_sku": "SKU-1",
        "asin": asin,
        "sale_status": "active",
        "supplier_code": "SUP",
        "supplier_name": supplier_name,
        "supplier_sku": "SUP-NEW",
        "barcode": "789",
        "order_qty_mode": "raw_units",
        "supplier_pack_size": "1",
        "amazon_pack_size": "1",
        "sell_pack_qty": "",
        "supplier_case_qty": "12",
        "supplier_case_multiple": True,
        "valid_order_step": "12",
        "repack_required": False,
        "bundle_required": False,
        "pack_conversion_note": "case update",
        "moq": "1",
        "supplier_catalog_price": "2.00",
        "last_purchase_price": "1.80",
        "target_margin": "0.25",
        "vat_rate": "20",
        "notes": "new note",
    }


def test_p014_dry_run_does_not_change_product_db(tmp_path: Path) -> None:
    product_db_path, sqlite_path = _write_product_db(tmp_path, [_product_row("SKU-1", "ASIN-1")])
    ok, errors, _ = submit_product_db_edit(root=tmp_path, payload=_valid_edit_payload())
    assert ok is True
    assert errors == []

    payload = run_apply(
        root=tmp_path,
        product_db_path=product_db_path,
        sqlite_path=sqlite_path,
        output_dir=tmp_path / "proof",
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "dry_run"
    assert payload["applicable_rows"] == 1
    assert payload["applied_rows"] == 0
    preview = pd.read_csv(product_db_path, dtype=str).fillna("")
    assert preview.loc[0, "supplier_name"] == "Supplier"


def test_p014_apply_updates_local_mirror_and_sql_idempotently(tmp_path: Path) -> None:
    product_db_path, sqlite_path = _write_product_db(tmp_path, [_product_row("SKU-1", "ASIN-1")])
    ok, errors, _ = submit_product_db_edit(root=tmp_path, payload=_valid_edit_payload())
    assert ok is True
    assert errors == []

    first = run_apply(
        root=tmp_path,
        product_db_path=product_db_path,
        sqlite_path=sqlite_path,
        output_dir=tmp_path / "proof",
        apply=True,
        confirm_product_db_edit_apply=True,
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert first["status"] == "applied"
    assert first["applied_rows"] == 1
    preview = pd.read_csv(product_db_path, dtype=str).fillna("")
    assert preview.loc[0, "supplier_name"] == "New Supplier"
    assert preview.loc[0, "supplier_case_qty"] == "12"
    assert preview.loc[0, "last_updated"] == "2026-05-01T11:00:00Z"

    conn = sqlite3.connect(sqlite_path)
    try:
        row = conn.execute(
            "select supplier_name, source_payload_json from product_db_products where seller_sku='SKU-1'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "New Supplier"
    assert json.loads(row[1])["supplier_case_qty"] == "12"

    second = run_apply(
        root=tmp_path,
        product_db_path=product_db_path,
        sqlite_path=sqlite_path,
        output_dir=tmp_path / "proof",
        apply=True,
        confirm_product_db_edit_apply=True,
        observed_utc="2026-05-01T12:00:00Z",
    )
    assert second["status"] == "applied"
    assert second["applied_rows"] == 0
    assert second["skipped_rows"] == 1


def test_p014_holds_unsafe_nonblank_asin_change(tmp_path: Path) -> None:
    product_db_path, sqlite_path = _write_product_db(tmp_path, [_product_row("SKU-1", "ASIN-1")])
    ok, errors, _ = submit_product_db_edit(root=tmp_path, payload=_valid_edit_payload(asin="ASIN-2"))
    assert ok is True
    assert errors == []

    payload = run_apply(
        root=tmp_path,
        product_db_path=product_db_path,
        sqlite_path=sqlite_path,
        output_dir=tmp_path / "proof",
        apply=True,
        confirm_product_db_edit_apply=True,
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "applied_with_holds"
    assert payload["held_rows"] == 1
    plan = pd.read_csv(tmp_path / "proof" / "product_db_edit_event_apply_plan.csv", dtype=str).fillna("")
    assert plan.loc[0, "reason"] == "unsafe_asin_change_requires_review"
    preview = pd.read_csv(product_db_path, dtype=str).fillna("")
    assert preview.loc[0, "asin"] == "ASIN-1"


def test_p014_holds_duplicate_asin_when_filling_blank(tmp_path: Path) -> None:
    product_db_path, sqlite_path = _write_product_db(
        tmp_path,
        [
            _product_row("SKU-1", ""),
            _product_row("SKU-2", "ASIN-EXISTS"),
        ],
    )
    ok, errors, _ = submit_product_db_edit(root=tmp_path, payload=_valid_edit_payload(asin="ASIN-EXISTS"))
    assert ok is True
    assert errors == []

    payload = run_apply(
        root=tmp_path,
        product_db_path=product_db_path,
        sqlite_path=sqlite_path,
        output_dir=tmp_path / "proof",
        apply=True,
        confirm_product_db_edit_apply=True,
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "applied_with_holds"
    assert payload["held_rows"] == 1
    plan = pd.read_csv(tmp_path / "proof" / "product_db_edit_event_apply_plan.csv", dtype=str).fillna("")
    assert plan.loc[0, "reason"] == "duplicate_asin_requires_classification"


def test_p014_rejects_duplicate_seller_sku_source_before_write(tmp_path: Path) -> None:
    product_db_path = tmp_path / "product_db_preview.csv"
    sqlite_path = tmp_path / "sellerone.sqlite3"
    pd.DataFrame([_product_row("SKU-1", "ASIN-1"), _product_row("SKU-1", "ASIN-2")]).to_csv(
        product_db_path,
        index=False,
    )
    ok, errors, _ = submit_product_db_edit(root=tmp_path, payload=_valid_edit_payload())
    assert ok is True
    assert errors == []

    payload = run_apply(
        root=tmp_path,
        product_db_path=product_db_path,
        sqlite_path=sqlite_path,
        output_dir=tmp_path / "proof",
        apply=True,
        confirm_product_db_edit_apply=True,
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "fail"
    assert payload["reason"] == "product_db_contract_failed"
