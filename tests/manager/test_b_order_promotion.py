from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from sellerone_manager.b_order_promotion import (
    apply_b_order_promotion,
    build_b_order_promotion_plan,
)
from sellerone_manager.b_order_recovery import EXPECTED_QUARANTINE_REL_PATH, QUARANTINE_REQUIRED_COLUMNS


OBSERVED = "2026-05-27T15:00:00Z"
ORDER_ID = "171-1388771-2409132"
ITEM_ID = "63511800911762"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _order_payload() -> dict[str, object]:
    return {
        "AmazonOrderId": ORDER_ID,
        "PurchaseDate": "2026-05-23T11:59:20Z",
        "LastUpdateDate": "2026-05-23T12:02:00Z",
        "OrderStatus": "Shipped",
        "FulfillmentChannel": "AFN",
        "SalesChannel": "Amazon.ae",
        "ShipServiceLevel": "Expedited",
        "OrderTotal": {"Amount": "41.19", "CurrencyCode": "AED"},
        "NumberOfItemsShipped": 1,
        "NumberOfItemsUnshipped": 0,
        "MarketplaceId": "A2VIGQ35RCS4UG",
        "ShippingAddress": {"City": "Dubai", "CountryCode": "AE"},
    }


def _item_payload(*, order_item_id: str = ITEM_ID) -> dict[str, object]:
    return {
        "AmazonOrderId": ORDER_ID,
        "ASIN": "B072K2PG11",
        "SellerSKU": "GH-XAAE-HRU7",
        "OrderItemId": order_item_id,
        "Title": "Dishmatic Value Pack Kit",
        "QuantityOrdered": 1,
        "QuantityShipped": 1,
        "ItemPrice": {"Amount": "41.19", "CurrencyCode": "AED"},
    }


def _write_quarantine(root: Path, *, order_item_id: str = ITEM_ID, include_payloads: bool = True) -> None:
    order = _order_payload()
    item = _item_payload(order_item_id=order_item_id)
    _write_csv(
        root / EXPECTED_QUARANTINE_REL_PATH,
        QUARANTINE_REQUIRED_COLUMNS,
        [
            {
                "amazon_order_id": ORDER_ID,
                "marketplace_id": "A2VIGQ35RCS4UG",
                "purchase_utc": "2026-05-23T11:59:20Z",
                "order_status": "Shipped",
                "sku": "GH-XAAE-HRU7",
                "asin": "B072K2PG11",
                "order_item_ids": order_item_id,
                "quantity": "1",
                "currency": "AED",
                "order_total": "41.19",
                "last_update_utc": "2026-05-23T12:02:00Z",
                "sales_channel": "Amazon.ae",
                "fulfillment_channel": "AFN",
                "order_payload_json": json.dumps(order) if include_payloads else "",
                "items_payload_json": json.dumps([item]) if include_payloads else "",
                "source": "api_backdate",
                "proof_label": "API proved",
                "duplicate_state": "unique_in_quarantine",
                "ready_for_live_merge": "0",
            }
        ],
    )


def _write_marketplaces(root: Path) -> None:
    _write_csv(
        root / "out" / "marketplace_participations.csv",
        ["marketplace_id", "name", "country_code", "domain_name", "is_participating"],
        [
            {
                "marketplace_id": "A2VIGQ35RCS4UG",
                "name": "Amazon.ae",
                "country_code": "AE",
                "domain_name": "www.amazon.ae",
                "is_participating": "1",
            }
        ],
    )


def _write_live_duplicate_order_only(root: Path) -> None:
    _write_csv(
        root / "out" / "orders_all.csv",
        ["amazon_order_id", "purchase_date", "order_status", "marketplace_id", "order_total_currency"],
        [
            {
                "amazon_order_id": ORDER_ID,
                "purchase_date": "2026-05-23T11:59:20Z",
                "order_status": "Shipped",
                "marketplace_id": "A2VIGQ35RCS4UG",
                "order_total_currency": "AED",
            }
        ],
    )


def _fake_rebuild_order_master(root: Path) -> int:
    l1 = pd.read_csv(root / "out" / "financial_events_level1.csv", dtype=str).fillna("")
    out = pd.DataFrame({"Order ID": l1.get("Order ID", ""), "SKU": l1.get("SKU", "")})
    out.to_csv(root / "out" / "order_master.csv", index=False)
    return 0


def test_b_order_promotion_preview_requires_luke_for_valid_api_quarantine(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_quarantine(tmp_path)

    result = build_b_order_promotion_plan(root=tmp_path, observed_utc=OBSERVED)

    assert result.status == "decision_needed"
    assert result.preview_rows[0]["promotion_status"] == "ready_pending_approval"
    assert result.preview_rows[0]["order_item_ids"] == ITEM_ID


def test_b_order_promotion_blocks_partial_duplicate_live_order(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_quarantine(tmp_path)
    _write_live_duplicate_order_only(tmp_path)

    result = build_b_order_promotion_plan(root=tmp_path, observed_utc=OBSERVED)

    assert result.status == "fail"
    assert result.preview_rows[0]["promotion_status"] == "blocked_duplicate_partial"


def test_b_order_promotion_blocks_missing_order_item_id(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_quarantine(tmp_path, order_item_id="", include_payloads=False)

    result = build_b_order_promotion_plan(root=tmp_path, observed_utc=OBSERVED)

    assert result.status == "fail"
    assert result.preview_rows[0]["promotion_status"] == "blocked_validation"
    assert "missing_order_item_id" in result.preview_rows[0]["validation_errors"]


def test_b_order_promotion_apply_without_approval_does_not_write_live_outputs(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_quarantine(tmp_path)

    result = apply_b_order_promotion(root=tmp_path, observed_utc=OBSERVED)

    assert result.manifest["status"] == "blocked"
    assert not (tmp_path / "out" / "orders_all.csv").exists()
    assert not (tmp_path / "out" / "order_items_all.csv").exists()


def test_b_order_promotion_apply_with_approval_updates_live_chain(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_quarantine(tmp_path)

    result = apply_b_order_promotion(
        root=tmp_path,
        observed_utc=OBSERVED,
        approve_protected_promotion=True,
        order_master_rebuilder=_fake_rebuild_order_master,
    )
    orders = pd.read_csv(tmp_path / "out" / "orders_all.csv", dtype=str).fillna("")
    items = pd.read_csv(tmp_path / "out" / "order_items_all.csv", dtype=str).fillna("")
    l1 = pd.read_csv(tmp_path / "out" / "financial_events_level1.csv", dtype=str).fillna("")
    master = pd.read_csv(tmp_path / "out" / "order_master.csv", dtype=str).fillna("")

    assert result.manifest["status"] == "promoted"
    assert ORDER_ID in set(orders["amazon_order_id"])
    assert ITEM_ID in set(items["order_item_id"])
    assert ORDER_ID in set(l1["Order ID"])
    assert ORDER_ID in set(master["Order ID"])


def test_b_order_promotion_apply_allows_boundary_maintenance_lock(tmp_path: Path) -> None:
    _write_marketplaces(tmp_path)
    _write_quarantine(tmp_path)
    live = tmp_path / "out" / "systems" / "B" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (live / "B_cycle.lock").write_text("owner=B|pid=123|heartbeat=2026-05-27T15:00:00Z\n", encoding="utf-8")
    locks = tmp_path / "out" / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    (locks / "maintenance.requested").write_text("requested_by=codex_b_order_promotion\n", encoding="utf-8")
    (locks / "maintenance.ready").write_text("B_READY|context=after cycle end\n", encoding="utf-8")

    result = apply_b_order_promotion(
        root=tmp_path,
        observed_utc=OBSERVED,
        approve_protected_promotion=True,
        order_master_rebuilder=_fake_rebuild_order_master,
    )

    assert result.manifest["status"] == "promoted"
