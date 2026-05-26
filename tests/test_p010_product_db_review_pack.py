from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS
from scripts.one_off.P010_product_db_review_pack import (
    DUPLICATE_ASIN_REVIEW_COLUMNS,
    SCANNER_LINK_REVIEW_COLUMNS,
    build_duplicate_asin_review,
    run_review_pack,
)


def _product_row(seller_sku: str, asin: str, *, status: str = "active") -> dict[str, str]:
    row = {column: "" for column in PRODUCT_DB_REQUIRED_COLUMNS}
    row.update(
        {
            "seller_sku": seller_sku,
            "asin": asin,
            "title": f"Title {asin}",
            "brand_name": "Brand",
            "main_image": "https://example.test/image.jpg",
            "sale_status": status,
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


def test_duplicate_asin_review_suggests_legacy_or_replacement_candidate() -> None:
    product_db = pd.DataFrame(
        [
            _product_row("SKU-A", "ASIN-1", status="active"),
            _product_row("SKU-B", "ASIN-1", status="discontinued"),
            _product_row("SKU-C", "ASIN-2", status="active"),
        ],
        columns=PRODUCT_DB_REQUIRED_COLUMNS,
    )

    rows = build_duplicate_asin_review(product_db)

    assert len(rows) == 1
    assert rows[0]["asin"] == "ASIN-1"
    assert rows[0]["match_count"] == "2"
    assert rows[0]["seller_skus"] == "SKU-A|SKU-B"
    assert rows[0]["suggested_classification"] == "legacy_or_replacement_listing_candidate"
    assert rows[0]["classification_status"] == "needs_user_decision"


def test_review_pack_writes_duplicate_asin_and_scanner_link_reports(tmp_path: Path) -> None:
    scanner_path = tmp_path / "scanner_latest.csv"
    product_db_path = tmp_path / "product_db_preview.csv"
    output_dir = tmp_path / "review_pack"

    pd.DataFrame(
        [
            {
                "asin": "ASIN-NEW",
                "supplier_sku": "SUP-1",
                "candidate_id": "C1",
                "title": "New title",
                "brand": "Brand",
                "cost": "1.25",
                "buy_box_price": "9.99",
                "pf": "1.0",
                "recommendation_status": "PASS",
            },
            {
                "asin": "ASIN-DUP",
                "supplier_sku": "SUP-2A",
                "candidate_id": "C2",
                "title": "Dup title",
                "brand": "Brand",
                "cost": "1.50",
                "buy_box_price": "10.99",
                "pf": "0.8",
                "recommendation_status": "PASS",
            },
            {
                "asin": "ASIN-DUP",
                "supplier_sku": "SUP-2B",
                "candidate_id": "C3",
                "title": "Dup title",
                "brand": "Brand",
                "cost": "1.75",
                "buy_box_price": "11.99",
                "pf": "0.7",
                "recommendation_status": "PASS",
            },
        ]
    ).to_csv(scanner_path, index=False)
    pd.DataFrame(
        [
            _product_row("SKU-A", "ASIN-OLD", status="active"),
            _product_row("SKU-B", "ASIN-OLD", status="dropped"),
        ],
        columns=PRODUCT_DB_REQUIRED_COLUMNS,
    ).to_csv(product_db_path, index=False)

    payload = run_review_pack(
        scanner_path=scanner_path,
        product_db_path=product_db_path,
        output_dir=output_dir,
        observed_utc="2026-05-01T10:00:00Z",
    )

    duplicate_df = pd.read_csv(output_dir / "product_db_duplicate_asin_classification_review.csv", dtype=str).fillna("")
    scanner_df = pd.read_csv(output_dir / "scanner_product_db_link_review.csv", dtype=str).fillna("")
    summary = json.loads((output_dir / "product_db_review_pack_summary.json").read_text(encoding="utf-8"))

    assert payload["status"] == "warn"
    assert summary["scanner_action_counts"] == {"REVIEW": 2, "WOULD INSERT": 1}
    assert list(duplicate_df.columns) == list(DUPLICATE_ASIN_REVIEW_COLUMNS)
    assert list(scanner_df.columns) == list(SCANNER_LINK_REVIEW_COLUMNS)
    assert duplicate_df.iloc[0]["asin"] == "ASIN-OLD"
    assert scanner_df["review_bucket"].value_counts().to_dict() == {
        "duplicate_scanner_asin_review": 2,
        "new_product_create_review": 1,
    }


def test_review_pack_fails_closed_when_source_missing(tmp_path: Path) -> None:
    payload = run_review_pack(
        scanner_path=tmp_path / "missing_scanner.csv",
        product_db_path=tmp_path / "missing_product_db.csv",
        output_dir=tmp_path / "review_pack",
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert payload["status"] == "fail"
    assert payload["reason"] == "missing_source_file"
    assert (tmp_path / "review_pack" / "product_db_duplicate_asin_classification_review.csv").exists()
    assert (tmp_path / "review_pack" / "scanner_product_db_link_review.csv").exists()
