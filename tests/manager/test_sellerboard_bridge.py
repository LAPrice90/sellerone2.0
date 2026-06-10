from __future__ import annotations

import csv
from pathlib import Path

from sellerone_manager.sellerboard_bridge import (
    build_sellerboard_bridge_report,
    write_sellerboard_bridge_outputs,
)


OBSERVED = "2026-05-27T10:00:00Z"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _sellerboard_columns() -> list[str]:
    return [
        "AmazonOrderId",
        "PurchaseDate(UTC)",
        "OrderTotalCurrencyCode",
        "OrderTotalAmount",
        "Shipping",
        "Gift wrap",
        "Tax",
        "Item promotion",
        "Ship Promotion",
        "Products",
        "Comission",
        "FBAPerUnitFulfillmentFee",
        "OrderStatus",
        "NumberOfItems",
        "SalesChannel",
        "IsPremiumOrder",
        "ShippedByAmazonTFM",
        "IsReplacementOrder",
        "IsBusinessOrder",
        "FulfillmentChannel",
        "IsPrime",
        "ShipmentServiceLevelCategory",
        "Coupons",
        "ShippingCost",
    ]


def _write_local_files(root: Path, *, include_fee_detail: bool = True, expected_refund: str = "0.20") -> None:
    _write_csv(
        root / "out" / "orders_all.csv",
        ["amazon_order_id", "purchase_date", "order_status", "order_total_amount"],
        [
            {"amazon_order_id": "205-1111111-1111111", "purchase_date": "2026-05-20T10:00:00Z", "order_status": "Shipped", "order_total_amount": "10.00"},
            {"amazon_order_id": "205-2222222-2222222", "purchase_date": "2026-05-21T10:00:00Z", "order_status": "Shipped", "order_total_amount": "8.00"},
        ],
    )
    _write_csv(
        root / "out" / "order_items_all.csv",
        ["amazon_order_id", "asin", "seller_sku", "quantity_ordered"],
        [
            {"amazon_order_id": "205-1111111-1111111", "asin": "B000000001", "seller_sku": "SKU1", "quantity_ordered": "1"},
            {"amazon_order_id": "205-2222222-2222222", "asin": "B000000002", "seller_sku": "SKU2", "quantity_ordered": "1"},
        ],
    )
    _write_csv(
        root / "out" / "order_master.csv",
        ["Date", "Order ID", "SKU", "Quantity Ordered", "Price_Total", "Shipping_Total", "FBA_Fee_ExVAT", "Commission_ExVAT"],
        [
            {"Date": "2026-05-20T10:00:00Z", "Order ID": "205-1111111-1111111", "SKU": "SKU1", "Quantity Ordered": "1", "Price_Total": "10.00", "Shipping_Total": "0", "FBA_Fee_ExVAT": "-2.00", "Commission_ExVAT": "-1.00"},
            {"Date": "2026-05-21T10:00:00Z", "Order ID": "205-2222222-2222222", "SKU": "SKU2", "Quantity Ordered": "1", "Price_Total": "8.00", "Shipping_Total": "0", "FBA_Fee_ExVAT": "-2.00", "Commission_ExVAT": "-1.00"},
        ],
    )
    _write_csv(
        root / "out" / "financial_events_refunds.csv",
        ["order_id", "sku", "posted_date", "amount_type", "amount"],
        [
            {"order_id": "205-2222222-2222222", "sku": "SKU2", "posted_date": "2026-05-22T10:00:00Z", "amount_type": "Refund_Principal", "amount": "-8.00"},
        ],
    )
    _write_csv(
        root / "out" / "sku_performance_summary.csv",
        ["sku", "expected_refund_cost_per_unit_gbp"],
        [
            {"sku": "SKU1", "expected_refund_cost_per_unit_gbp": "0"},
            {"sku": "SKU2", "expected_refund_cost_per_unit_gbp": expected_refund},
        ],
    )
    _write_csv(
        root / "out" / "fee_detail_ledger_api.csv",
        ["date", "posted_date", "transaction_id", "fee_type", "amount_total", "amount_base", "amount_vat", "currency", "non_gbp_api_only", "inbound_shipment_id"],
        [
            {"date": "2026-05-20", "posted_date": "2026-05-20T10:00:00Z", "transaction_id": "fee1", "fee_type": "FBA", "amount_total": "-2", "amount_base": "-1.67", "amount_vat": "-0.33", "currency": "GBP", "non_gbp_api_only": "0", "inbound_shipment_id": ""},
            {"date": "2026-05-20", "posted_date": "2026-05-20T10:00:00Z", "transaction_id": "fee2", "fee_type": "Commission", "amount_total": "-1", "amount_base": "-0.83", "amount_vat": "-0.17", "currency": "GBP", "non_gbp_api_only": "0", "inbound_shipment_id": ""},
        ]
        if include_fee_detail
        else [],
    )


def _write_sellerboard_file(path: Path, rows: list[dict[str, str]]) -> None:
    base = {column: "" for column in _sellerboard_columns()}
    output_rows = []
    for row in rows:
        merged = dict(base)
        merged.update(row)
        output_rows.append(merged)
    _write_csv(path, _sellerboard_columns(), output_rows)


def _summary_metric(rows: list[dict[str, str]], metric: str) -> str:
    return next(row for row in rows if row["metric"] == metric)["value"]


def test_sellerboard_bridge_builds_clean_read_only_pack(tmp_path: Path) -> None:
    _write_local_files(tmp_path)
    sellerboard_path = tmp_path / "DRJ_Hardware_OrderList_20_05_2026-26_05_2026_(test).csv"
    _write_sellerboard_file(
        sellerboard_path,
        [
            {"AmazonOrderId": "205-1111111-1111111", "PurchaseDate(UTC)": "20/05/2026 10:00:00", "OrderTotalAmount": "10.00", "Products": "B000000001", "Comission": "-1.00", "FBAPerUnitFulfillmentFee": "-2.00", "OrderStatus": "Shipped", "NumberOfItems": "1", "FulfillmentChannel": "AFN"},
            {"AmazonOrderId": "205-2222222-2222222", "PurchaseDate(UTC)": "21/05/2026 10:00:00", "OrderTotalAmount": "8.00", "Products": "B000000002", "Comission": "-1.00", "FBAPerUnitFulfillmentFee": "-2.00", "OrderStatus": "Return", "NumberOfItems": "1", "FulfillmentChannel": "AFN"},
        ],
    )

    result = build_sellerboard_bridge_report(root=tmp_path, sellerboard_path=sellerboard_path, observed_utc=OBSERVED)
    paths = write_sellerboard_bridge_outputs(result, tmp_path / "out" / "systems" / "M")

    assert result.status == "ok"
    assert _summary_metric(result.summary_rows, "sellerboard_rows_total") == "2"
    assert _summary_metric(result.summary_rows, "sellerboard_shipped_missing_from_sellerone_orders") == "0"
    assert _summary_metric(result.summary_rows, "sellerboard_rows_unmapped_to_sku") == "0"
    assert _summary_metric(result.summary_rows, "refund_proof_state") == "api_proved_or_not_applicable"
    assert _summary_metric(result.summary_rows, "fee_shipping_proof_state") == "api_proved"
    assert _summary_metric(result.summary_rows, "roi_refund_proof_state") == "api_proved_or_not_applicable"
    assert _summary_metric(result.summary_rows, "refund_api_proof_state") == "api_proved"
    assert _summary_metric(result.summary_rows, "commission_api_proof_state") == "api_proved"
    assert _summary_metric(result.summary_rows, "fba_fee_api_proof_state") == "api_proved"
    assert _summary_metric(result.summary_rows, "shipping_income_api_proof_state") == "api_proved_or_not_applicable"
    assert _summary_metric(result.summary_rows, "shipping_fee_api_proof_state") == "api_proved_or_not_applicable"
    assert _summary_metric(result.summary_rows, "roi_money_confidence_state") == "api_backed_safe"
    assert _summary_metric(result.summary_rows, "bridge_values_safe_for_live_roi") == "1"
    assert paths["summary_csv"].exists()
    assert paths["order_reconciliation_csv"].exists()
    assert paths["sku_gap_csv"].exists()


def test_sellerboard_bridge_marks_missing_order_and_unmapped_sku_not_proven(tmp_path: Path) -> None:
    _write_local_files(tmp_path, include_fee_detail=False, expected_refund="0")
    sellerboard_path = tmp_path / "DRJ_Hardware_OrderList_20_05_2026-26_05_2026_(test).csv"
    _write_sellerboard_file(
        sellerboard_path,
        [
            {"AmazonOrderId": "205-3333333-3333333", "PurchaseDate(UTC)": "20/05/2026 10:00:00", "OrderTotalAmount": "10.00", "Products": "B000000003", "Comission": "-1.00", "FBAPerUnitFulfillmentFee": "-2.00", "OrderStatus": "Shipped", "NumberOfItems": "1", "FulfillmentChannel": "AFN"},
        ],
    )

    result = build_sellerboard_bridge_report(root=tmp_path, sellerboard_path=sellerboard_path, observed_utc=OBSERVED)

    assert result.status == "fail"
    assert _summary_metric(result.summary_rows, "sellerboard_shipped_missing_from_sellerone_orders") == "1"
    assert _summary_metric(result.summary_rows, "sellerboard_shipped_rows_unmapped_to_sku") == "1"
    missing_row = next(row for row in result.order_rows if row["amazon_order_id"] == "205-3333333-3333333")
    assert missing_row["proof_label"] == "Sellerboard bridge estimate"


def test_sellerboard_bridge_labels_refund_fee_roi_not_proven(tmp_path: Path) -> None:
    _write_local_files(tmp_path, include_fee_detail=False, expected_refund="0")
    sellerboard_path = tmp_path / "DRJ_Hardware_OrderList_20_05_2026-26_05_2026_(test).csv"
    _write_sellerboard_file(
        sellerboard_path,
        [
            {"AmazonOrderId": "205-1111111-1111111", "PurchaseDate(UTC)": "20/05/2026 10:00:00", "OrderTotalAmount": "10.00", "Products": "B000000001", "Comission": "-1.00", "FBAPerUnitFulfillmentFee": "-2.00", "OrderStatus": "Shipped", "NumberOfItems": "1", "FulfillmentChannel": "AFN"},
            {"AmazonOrderId": "205-2222222-2222222", "PurchaseDate(UTC)": "21/05/2026 10:00:00", "OrderTotalAmount": "8.00", "Products": "B000000002", "Comission": "-1.00", "FBAPerUnitFulfillmentFee": "-2.00", "OrderStatus": "Return", "NumberOfItems": "1", "FulfillmentChannel": "AFN"},
        ],
    )

    result = build_sellerboard_bridge_report(root=tmp_path, sellerboard_path=sellerboard_path, observed_utc=OBSERVED)

    assert result.status == "warn"
    assert _summary_metric(result.summary_rows, "refund_proof_state") == "api_proved_or_not_applicable"
    assert _summary_metric(result.summary_rows, "fee_shipping_proof_state") == "not_yet_proven"
    assert _summary_metric(result.summary_rows, "roi_refund_proof_state") == "not_yet_proven"
    assert _summary_metric(result.summary_rows, "refund_api_proof_state") == "api_proved"
    assert _summary_metric(result.summary_rows, "commission_api_proof_state") == "not_yet_proven"
    assert _summary_metric(result.summary_rows, "fba_fee_api_proof_state") == "not_yet_proven"
    assert _summary_metric(result.summary_rows, "roi_money_confidence_state") == "not_yet_proven"
    assert _summary_metric(result.summary_rows, "bridge_values_safe_for_live_roi") == "0"
