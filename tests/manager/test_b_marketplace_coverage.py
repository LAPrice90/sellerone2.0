from __future__ import annotations

import csv
from pathlib import Path

from sellerone_manager.b_marketplace_coverage import (
    build_b_marketplace_coverage_report,
    write_b_marketplace_coverage_outputs,
)
from sellerone_manager.b_order_recovery import EXPECTED_QUARANTINE_REL_PATH, QUARANTINE_REQUIRED_COLUMNS
from sellerone_manager.sellerboard_bridge import ORDER_RECONCILIATION_COLUMNS, ORDER_RECONCILIATION_NAME


OBSERVED = "2026-05-27T11:00:00Z"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_marketplace_fixture(root: Path) -> None:
    _write_csv(
        root / "out" / "marketplace_participations.csv",
        ["marketplace_id", "name", "country_code", "domain_name", "is_participating"],
        [
            {"marketplace_id": "A1F83G8C2ARO7P", "name": "Amazon.co.uk", "country_code": "GB", "domain_name": "www.amazon.co.uk", "is_participating": "1"},
            {"marketplace_id": "A28R8C7NBKEWEA", "name": "Amazon.ie", "country_code": "IE", "domain_name": "www.amazon.ie", "is_participating": "1"},
            {"marketplace_id": "A2VIGQ35RCS4UG", "name": "Amazon.ae", "country_code": "AE", "domain_name": "www.amazon.ae", "is_participating": "1"},
            {"marketplace_id": "A17E79C6D8DWNP", "name": "Amazon.sa", "country_code": "SA", "domain_name": "www.amazon.sa", "is_participating": "1"},
            {"marketplace_id": "AZMDEXL2RVFNN", "name": "Non-Amazon UK", "country_code": "GB", "domain_name": "siprodukmarketplace.stores.amazon.co.uk", "is_participating": "1"},
        ],
    )
    _write_csv(
        root / "out" / "orders_all.csv",
        ["amazon_order_id", "purchase_date", "order_status", "marketplace_id", "sales_channel", "order_total_currency"],
        [
            {"amazon_order_id": "205-1111111-1111111", "purchase_date": "2026-05-27T10:00:00Z", "order_status": "Shipped", "marketplace_id": "A1F83G8C2ARO7P", "sales_channel": "Amazon.co.uk", "order_total_currency": "GBP"},
            {"amazon_order_id": "408-4682075-2203536", "purchase_date": "2026-05-20T18:20:32Z", "order_status": "Shipped", "marketplace_id": "A28R8C7NBKEWEA", "sales_channel": "Amazon.ie", "order_total_currency": "EUR"},
            {"amazon_order_id": "404-7471611-6464300", "purchase_date": "2026-02-13T06:10:10Z", "order_status": "Shipped", "marketplace_id": "A2VIGQ35RCS4UG", "sales_channel": "Amazon.ae", "order_total_currency": "AED"},
            {"amazon_order_id": "405-0400730-2116333", "purchase_date": "2025-12-27T06:16:02Z", "order_status": "Shipped", "marketplace_id": "A17E79C6D8DWNP", "sales_channel": "Amazon.sa", "order_total_currency": "SAR"},
        ],
    )
    _write_csv(
        root / "out" / "order_items_all.csv",
        ["amazon_order_id", "asin", "seller_sku", "quantity_ordered"],
        [
            {"amazon_order_id": "205-1111111-1111111", "asin": "B1", "seller_sku": "SKU-UK", "quantity_ordered": "1"},
            {"amazon_order_id": "408-4682075-2203536", "asin": "B2", "seller_sku": "SKU-IE", "quantity_ordered": "1"},
            {"amazon_order_id": "404-7471611-6464300", "asin": "B3", "seller_sku": "SKU-AE-OLD", "quantity_ordered": "1"},
            {"amazon_order_id": "405-0400730-2116333", "asin": "B4", "seller_sku": "SKU-SA", "quantity_ordered": "1"},
        ],
    )
    _write_csv(
        root / "out" / "financial_events_level1.csv",
        ["Date", "Order ID", "marketplace_id", "SKU"],
        [
            {"Date": "2026-05-27T10:00:00Z", "Order ID": "205-1111111-1111111", "marketplace_id": "A1F83G8C2ARO7P", "SKU": "SKU-UK"},
            {"Date": "2026-05-20T18:20:32Z", "Order ID": "408-4682075-2203536", "marketplace_id": "A28R8C7NBKEWEA", "SKU": "SKU-IE"},
            {"Date": "2026-02-13T06:10:10Z", "Order ID": "404-7471611-6464300", "marketplace_id": "A2VIGQ35RCS4UG", "SKU": "SKU-AE-OLD"},
        ],
    )
    _write_csv(
        root / "out" / "order_master.csv",
        ["Date", "Order ID", "SKU", "country_code", "currency_code"],
        [
            {"Date": "2026-05-27T10:00:00Z", "Order ID": "205-1111111-1111111", "SKU": "SKU-UK", "country_code": "GB", "currency_code": "GBP"},
            {"Date": "2026-05-20T18:20:32Z", "Order ID": "408-4682075-2203536", "SKU": "SKU-IE", "country_code": "IE", "currency_code": "EUR"},
            {"Date": "2026-02-13T06:10:10Z", "Order ID": "404-7471611-6464300", "SKU": "SKU-AE-OLD", "country_code": "AE", "currency_code": "AED"},
        ],
    )
    _write_csv(root / "out" / "financial_events_level3_official.csv", ["Order ID", "SKU", "FBA_Fee_ExVAT"], [])
    _write_csv(root / "out" / "financial_events_refunds.csv", ["order_id", "sku", "amount"], [])
    (root / "out" / "orders_last_updated.txt").write_text("2026-05-27T10:00:00Z", encoding="utf-8")
    _write_csv(
        root / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME,
        ORDER_RECONCILIATION_COLUMNS,
        [
            {
                "amazon_order_id": "205-1111111-1111111",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-27T10:00:00Z",
                "sellerboard_sales_channel": "Amazon.co.uk",
                "sellerboard_currency": "GBP",
                "sellerboard_asin": "B1",
                "mapped_sku": "SKU-UK",
                "local_order_status": "Shipped",
                "local_purchase_utc": "2026-05-27T10:00:00Z",
                "local_marketplace_id": "A1F83G8C2ARO7P",
                "local_sales_channel": "Amazon.co.uk",
                "match_status": "matched",
                "proof_label": "API proved",
            },
            {
                "amazon_order_id": "408-4682075-2203536",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-20T18:20:32Z",
                "sellerboard_sales_channel": "Amazon.ie",
                "sellerboard_currency": "GBP",
                "sellerboard_asin": "B2",
                "mapped_sku": "SKU-IE",
                "local_order_status": "Shipped",
                "local_purchase_utc": "2026-05-20T18:20:32Z",
                "local_marketplace_id": "A28R8C7NBKEWEA",
                "local_sales_channel": "Amazon.ie",
                "match_status": "matched",
                "proof_label": "API proved",
            },
            {
                "amazon_order_id": "171-1388771-2409132",
                "sellerboard_status": "Shipped",
                "sellerboard_purchase_utc": "2026-05-23T11:59:20Z",
                "sellerboard_sales_channel": "Amazon.ae",
                "sellerboard_currency": "GBP",
                "sellerboard_asin": "B072K2PG11",
                "mapped_sku": "",
                "match_status": "sellerboard_shipped_missing_in_sellerone",
                "proof_label": "Sellerboard bridge estimate",
            },
        ],
    )


def test_marketplace_coverage_flags_sellerboard_only_amazon_ae_order(tmp_path: Path) -> None:
    _write_marketplace_fixture(tmp_path)

    result = build_b_marketplace_coverage_report(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["marketplace_id"]: row for row in result.coverage_rows}
    paths = write_b_marketplace_coverage_outputs(result, tmp_path / "out" / "systems" / "M")

    assert result.status == "fail"
    assert rows["A2VIGQ35RCS4UG"]["coverage_status"] == "fail"
    assert rows["A2VIGQ35RCS4UG"]["sellerboard_missing_shipped_orders"] == "1"
    assert rows["A2VIGQ35RCS4UG"]["shared_cursor_risk"] == "1"
    assert rows["A28R8C7NBKEWEA"]["coverage_status"] == "ok"
    assert paths["coverage_csv"].exists()
    assert paths["summary_csv"].exists()


def test_marketplace_coverage_treats_api_quarantine_as_recovered_not_shared_cursor_risk(tmp_path: Path) -> None:
    _write_marketplace_fixture(tmp_path)
    _write_csv(
        tmp_path / EXPECTED_QUARANTINE_REL_PATH,
        QUARANTINE_REQUIRED_COLUMNS,
        [
            {
                "amazon_order_id": "171-1388771-2409132",
                "marketplace_id": "A2VIGQ35RCS4UG",
                "purchase_utc": "2026-05-23T11:59:20Z",
                "order_status": "Shipped",
                "sku": "GH-XAAE-HRU7",
                "asin": "B072K2PG11",
                "quantity": "1",
                "currency": "AED",
                "order_total": "41.19",
                "source": "api_backdate",
                "proof_label": "API proved",
                "duplicate_state": "unique_in_quarantine",
                "ready_for_live_merge": "0",
            }
        ],
    )

    result = build_b_marketplace_coverage_report(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["marketplace_id"]: row for row in result.coverage_rows}

    assert rows["A2VIGQ35RCS4UG"]["coverage_status"] == "ok"
    assert rows["A2VIGQ35RCS4UG"]["sellerboard_missing_shipped_orders"] == "0"
    assert rows["A2VIGQ35RCS4UG"]["sellerboard_api_proved_quarantine_orders"] == "1"
    assert rows["A2VIGQ35RCS4UG"]["shared_cursor_risk"] == "0"


def test_marketplace_coverage_labels_status_difference_as_warning_only(tmp_path: Path) -> None:
    _write_marketplace_fixture(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "sellerboard_bridge" / ORDER_RECONCILIATION_NAME,
        ORDER_RECONCILIATION_COLUMNS,
        [
            {
                "amazon_order_id": "205-1111111-1111111",
                "sellerboard_status": "Unshipped",
                "sellerboard_purchase_utc": "2026-05-27T10:00:00Z",
                "sellerboard_sales_channel": "Amazon.co.uk",
                "sellerboard_currency": "GBP",
                "sellerboard_asin": "B1",
                "mapped_sku": "SKU-UK",
                "local_order_status": "Shipped",
                "local_purchase_utc": "2026-05-27T10:00:00Z",
                "local_marketplace_id": "A1F83G8C2ARO7P",
                "local_sales_channel": "Amazon.co.uk",
                "match_status": "status_difference",
                "proof_label": "Sellerboard bridge estimate",
            }
        ],
    )

    result = build_b_marketplace_coverage_report(root=tmp_path, observed_utc=OBSERVED)
    rows = {row["marketplace_id"]: row for row in result.coverage_rows}
    summary = {row["metric"]: row for row in result.summary_rows}

    assert result.status == "warn"
    assert rows["A1F83G8C2ARO7P"]["coverage_status"] == "warn"
    assert rows["A1F83G8C2ARO7P"]["manager_coverage_label"] == "warning_labelled_status_difference"
    assert rows["A1F83G8C2ARO7P"]["sellerboard_missing_shipped_orders"] == "0"
    assert rows["A1F83G8C2ARO7P"]["shared_cursor_risk"] == "0"
    assert summary["marketplace_status_difference_warn_rows"]["value"] == "1"
    assert "warning_labelled_status_difference=1" in summary["marketplace_warn_rows"]["notes"]


def test_marketplace_coverage_is_not_checked_when_core_schema_is_placeholder(tmp_path: Path) -> None:
    _write_csv(tmp_path / "out" / "orders_all.csv", ["id", "value"], [{"id": "1", "value": "placeholder"}])

    result = build_b_marketplace_coverage_report(root=tmp_path, observed_utc=OBSERVED)

    assert result.status == "not_checked"
