from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS
from scripts.one_off.P009_product_db_link_simulation import run_link_simulation


def _product_row(seller_sku: str, asin: str) -> dict[str, str]:
    row = {column: "" for column in PRODUCT_DB_REQUIRED_COLUMNS}
    row.update(
        {
            "seller_sku": seller_sku,
            "asin": asin,
            "title": f"Title {seller_sku}",
            "brand_name": "Brand",
            "main_image": "https://example.test/image.jpg",
            "sale_status": "active",
            "supplier_code": "SUP",
            "supplier_name": "Supplier",
            "supplier_pack_size": "1",
            "amazon_pack_size": "1",
            "supplier_catalog_price": "1.00",
            "last_purchase_price": "1.00",
            "vat_rate": "20",
            "fba_fee_10": "1.00",
            "fba_fee_100": "1.00",
            "referral_fee_10": "1.00",
            "referral_fee_100": "1.00",
            "live_listing_price": "10.00",
            "stock_total": "1",
            "stock_available": "1",
            "stock_reserved": "0",
            "stock_inbound": "0",
            "last_updated": "2026-05-01T10:00:00Z",
        }
    )
    return row


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_link_simulation_classifies_insert_update_review_and_collapses_exact_duplicates(tmp_path: Path) -> None:
    scanner = tmp_path / "scanner_latest.csv"
    product_db = tmp_path / "product_db_preview.csv"
    _write_csv(
        scanner,
        [
            {"asin": "A1", "supplier_sku": "SUP-1", "candidate_id": "C1"},
            {"asin": "A2", "supplier_sku": "SUP-2", "candidate_id": "C2"},
            {"asin": "A3", "supplier_sku": "SUP-3", "candidate_id": "C3"},
            {"asin": "", "supplier_sku": "SUP-4", "candidate_id": "C4"},
            {"asin": "A4", "supplier_sku": "", "candidate_id": "C5"},
            {"asin": "A5", "supplier_sku": "SUP-5A", "candidate_id": "C6"},
            {"asin": "A5", "supplier_sku": "SUP-5B", "candidate_id": "C7"},
            {"asin": "A6", "supplier_sku": "SUP-6", "candidate_id": "C8"},
            {"asin": "A6", "supplier_sku": "SUP-6", "candidate_id": "C9"},
        ],
        ["asin", "supplier_sku", "candidate_id"],
    )
    _write_csv(
        product_db,
        [
            _product_row("SKU-1", "A1"),
            _product_row("SKU-3A", "A3"),
            _product_row("SKU-3B", "A3"),
        ],
        list(PRODUCT_DB_REQUIRED_COLUMNS),
    )

    payload = run_link_simulation(
        scanner_path=scanner,
        product_db_path=product_db,
        observed_utc="2026-05-01T10:00:00Z",
    )
    by_key = {(row["asin"], row["supplier_sku"]): row for row in payload["rows"]}

    assert payload["status"] == "warn"
    assert payload["scanner_rows"] == 9
    assert payload["simulation_rows"] == 8
    assert payload["collapsed_exact_duplicate_rows"] == 1
    assert payload["action_counts"] == {"REVIEW": 5, "WOULD INSERT": 2, "WOULD UPDATE": 1}
    assert by_key[("A1", "SUP-1")]["action"] == "WOULD UPDATE"
    assert by_key[("A1", "SUP-1")]["matched_seller_skus"] == "SKU-1"
    assert by_key[("A2", "SUP-2")]["action"] == "WOULD INSERT"
    assert by_key[("A3", "SUP-3")]["reason"] == "multiple_product_db_asin_matches"
    assert by_key[("", "SUP-4")]["reason"] == "blank_scanner_asin"
    assert by_key[("A4", "")]["reason"] == "missing_supplier_sku"
    assert by_key[("A5", "SUP-5A")]["reason"] == "duplicate_scanner_asin_requires_review"
    assert by_key[("A5", "SUP-5A")]["scanner_duplicate_asin_supplier_skus"] == "SUP-5A|SUP-5B"
    assert by_key[("A6", "SUP-6")]["candidate_id"] == "C8|C9"
    assert by_key[("A6", "SUP-6")]["collapsed_duplicate_rows"] == "1"


def test_link_simulation_blocks_when_product_db_contract_has_duplicate_header(tmp_path: Path) -> None:
    scanner = tmp_path / "scanner_latest.csv"
    product_db = tmp_path / "product_db_preview.csv"
    _write_csv(
        scanner,
        [{"asin": "A1", "supplier_sku": "SUP-1", "candidate_id": "C1"}],
        ["asin", "supplier_sku", "candidate_id"],
    )
    headers = [*PRODUCT_DB_REQUIRED_COLUMNS, "last_updated_A003", "last_updated_A003"]
    product_row = _product_row("SKU-1", "A1")
    values = [product_row.get(column, "") for column in PRODUCT_DB_REQUIRED_COLUMNS] + ["", ""]
    with product_db.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerow(values)

    payload = run_link_simulation(
        scanner_path=scanner,
        product_db_path=product_db,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert payload["status"] == "fail"
    assert payload["product_db_contract_status"] == "fail"
    assert payload["action_counts"] == {"BLOCKED": 1}
    assert payload["rows"][0]["action"] == "BLOCKED"
    assert "product_db_schema_failed:product_db_unique_headers" in payload["rows"][0]["reason"]


def test_link_simulation_missing_scanner_source_fails_without_outputs(tmp_path: Path) -> None:
    payload = run_link_simulation(
        scanner_path=tmp_path / "missing_scanner.csv",
        product_db_path=tmp_path / "missing_product_db.csv",
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert payload["status"] == "fail"
    assert payload["block_reasons"] == ["scanner_source_missing"]
    assert payload["rows"] == []
