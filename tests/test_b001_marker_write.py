from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.B import B001_run_orders_to_sheet as b001


def test_b001_save_marker_writes_normalised_utc_marker(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "orders_last_updated.txt"
    monkeypatch.setattr(b001, "MARKER_PATH", marker_path)

    b001.save_marker("2026-05-26T18:34:33+00:00")

    assert marker_path.read_text(encoding="utf-8") == "2026-05-26T18:34:33Z"


def test_b001_save_marker_retries_transient_windows_replace_error(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "orders_last_updated.txt"
    real_replace = b001.os.replace
    attempts = {"count": 0}
    monkeypatch.setattr(b001, "MARKER_PATH", marker_path)

    def flaky_replace(src: Path, dst: Path) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError(22, "Invalid argument")
        real_replace(src, dst)

    monkeypatch.setattr(b001.os, "replace", flaky_replace)

    b001.save_marker("2026-05-26T18:34:33Z")

    assert attempts["count"] == 2
    assert marker_path.read_text(encoding="utf-8") == "2026-05-26T18:34:33Z"


def test_b001_save_marker_raises_after_repeated_replace_errors(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "orders_last_updated.txt"
    monkeypatch.setattr(b001, "MARKER_PATH", marker_path)
    monkeypatch.setattr(
        b001.os,
        "replace",
        lambda src, dst: (_ for _ in ()).throw(OSError(22, "Invalid argument")),
    )

    with pytest.raises(OSError):
        b001.save_marker("2026-05-26T18:34:33Z")


def test_b001_promoted_recovery_overlay_keeps_order_in_compiled_outputs(monkeypatch, tmp_path: Path) -> None:
    order_id = "171-1388771-2409132"
    item_id = "63511800911762"
    orders_all = tmp_path / "out" / "orders_all.csv"
    items_all = tmp_path / "out" / "order_items_all.csv"
    quarantine = tmp_path / "out" / "systems" / "B" / "recovery_quarantine" / "b_order_recovery_quarantine.csv"
    manifest = tmp_path / "out" / "systems" / "B" / "order_promotion" / "b_order_promotion_manifest.json"

    monkeypatch.setattr(b001, "ORDERS_ALL_PATH", orders_all)
    monkeypatch.setattr(b001, "ITEMS_ALL_PATH", items_all)
    monkeypatch.setattr(b001, "RECOVERY_QUARANTINE_PATH", quarantine)
    monkeypatch.setattr(b001, "ORDER_PROMOTION_MANIFEST_PATH", manifest)
    monkeypatch.setattr(b001, "write_dataframe_with_sql_compat", lambda df, path, table: df.to_csv(path, index=False))

    order_payload = {
        "AmazonOrderId": order_id,
        "PurchaseDate": "2026-05-23T11:59:20Z",
        "LastUpdateDate": "2026-05-23T12:02:00Z",
        "OrderStatus": "Shipped",
        "MarketplaceId": "A2VIGQ35RCS4UG",
        "SalesChannel": "Amazon.ae",
        "FulfillmentChannel": "AFN",
        "OrderTotal": {"Amount": "41.19", "CurrencyCode": "AED"},
    }
    item_payload = {
        "AmazonOrderId": order_id,
        "OrderItemId": item_id,
        "ASIN": "B072K2PG11",
        "SellerSKU": "GH-XAAE-HRU7",
        "QuantityOrdered": 1,
        "QuantityShipped": 1,
        "ItemPrice": {"Amount": "41.19", "CurrencyCode": "AED"},
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"status": "promoted", "promoted_orders": [order_id]}), encoding="utf-8")
    quarantine.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "amazon_order_id": order_id,
                "marketplace_id": "A2VIGQ35RCS4UG",
                "purchase_utc": "2026-05-23T11:59:20Z",
                "order_status": "Shipped",
                "sku": "GH-XAAE-HRU7",
                "asin": "B072K2PG11",
                "order_item_ids": item_id,
                "quantity": "1",
                "currency": "AED",
                "order_total": "41.19",
                "proof_label": "API proved",
                "order_payload_json": json.dumps(order_payload),
                "items_payload_json": json.dumps([item_payload]),
            }
        ]
    ).to_csv(quarantine, index=False)

    recovery_orders, recovery_items = b001._load_promoted_recovery_frames()
    b001._merge_promoted_recovery_into_compiled(recovery_orders, recovery_items)
    recovery_level1 = b001.build_level1(recovery_orders, recovery_items)
    merged_level1 = b001._merge_level1_unique(pd.DataFrame(), recovery_level1)

    # Simulate a normal later UK-only compiled write. The recovered UAE order must remain.
    existing_orders = b001._read_csv_if_exists(orders_all)
    b001._write_compiled_unique(
        orders_all,
        existing_orders,
        pd.DataFrame([{"amazon_order_id": "026-TEST", "purchase_date": "2026-05-27T10:00:00Z"}]),
        dedupe_key_cols=["amazon_order_id"],
        sort_cols=["purchase_date", "amazon_order_id"],
    )

    existing_items = b001._read_csv_if_exists(items_all)
    incoming_items = pd.DataFrame([{"amazon_order_id": "026-TEST", "order_item_id": "test-item", "asin": "BTEST", "seller_sku": "TEST-SKU"}])
    incoming_items["_dedupe_key"] = b001._compiled_items_dedupe_key(incoming_items)
    existing_items["_dedupe_key"] = b001._compiled_items_dedupe_key(existing_items)
    b001._write_compiled_unique(items_all, existing_items, incoming_items, dedupe_key_cols=["_dedupe_key"])

    orders = pd.read_csv(orders_all, dtype=str).fillna("")
    items = pd.read_csv(items_all, dtype=str).fillna("")
    assert order_id in set(orders["amazon_order_id"])
    assert order_id in set(items["amazon_order_id"])
    assert item_id in set(items["order_item_id"])
    assert order_id in set(merged_level1["Order ID"])
