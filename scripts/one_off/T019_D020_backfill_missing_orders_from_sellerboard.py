"""
Backfill missing orders referenced by Sellerboard export.

Reads out/analysis_reports/missing_orders_vs_sellerboard.csv and fetches
order + items via Orders API, then appends to out/orders_all.csv and
out/order_items_all.csv.

Outputs:
- out/analysis_reports/missing_orders_backfill_results.csv
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
import requests

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_orders import (
    SPAPI_BASE_URL,
    get_lwa_access_token,
    list_order_items,
    load_dotenv_if_missing,
)
from scripts.B001_run_orders_to_sheet import flatten_orders, flatten_items


MISSING_REPORT = Path("out/analysis_reports/missing_orders_vs_sellerboard.csv")
ORDERS_ALL = Path("out/orders_all.csv")
ITEMS_ALL = Path("out/order_items_all.csv")
OUT_REPORT = Path("out/analysis_reports/missing_orders_backfill_results.csv")


def fetch_order(access_token: str, order_id: str, timeout: int = 30) -> Dict[str, object]:
    url = f"{SPAPI_BASE_URL}/orders/v0/orders/{order_id}"
    headers = {
        "x-amz-access-token": access_token,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Order fetch failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    order = (payload.get("payload") or {})
    if not order:
        raise RuntimeError("Order payload missing")
    return order


def fetch_order_items(access_token: str, order_id: str) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    next_token = None
    while True:
        batch, next_token = list_order_items(access_token, order_id, next_token=next_token)
        items.extend(batch)
        if not next_token:
            break
    return items


def main() -> None:
    if not MISSING_REPORT.exists():
        print({"status": "skip", "reason": "missing missing_orders_vs_sellerboard.csv"})
        return

    load_dotenv_if_missing()
    token = get_lwa_access_token()

    missing = pd.read_csv(MISSING_REPORT, dtype=str).fillna("")
    order_ids = sorted(set(missing.get("order_id", [])))
    if not order_ids:
        print({"status": "success", "message": "no missing orders"})
        return

    existing_orders = pd.read_csv(ORDERS_ALL, dtype=str).fillna("") if ORDERS_ALL.exists() else pd.DataFrame()
    existing_items = pd.read_csv(ITEMS_ALL, dtype=str).fillna("") if ITEMS_ALL.exists() else pd.DataFrame()
    existing_order_ids = set(existing_orders.get("amazon_order_id", []))
    existing_item_ids = set(existing_items.get("order_item_id", []))

    new_orders: List[Dict[str, object]] = []
    new_items: List[Dict[str, object]] = []
    results: List[Dict[str, object]] = []

    for order_id in order_ids:
        if order_id in existing_order_ids:
            has_items = False
            if not existing_items.empty:
                has_items = any(existing_items.get("amazon_order_id", "") == order_id)
            if has_items:
                results.append({"order_id": order_id, "status": "skip_exists", "error": ""})
                continue
            # Order exists but items are missing; fetch items only.
            try:
                items = fetch_order_items(token, order_id)
                if items:
                    for it in items:
                        if isinstance(it, dict):
                            it["AmazonOrderId"] = order_id
                    new_items.extend(items)
                    results.append({"order_id": order_id, "status": "items_backfilled", "error": ""})
                else:
                    results.append({"order_id": order_id, "status": "no_items", "error": "order items empty"})
                continue
            except Exception as exc:
                results.append({"order_id": order_id, "status": "error_items", "error": str(exc)})
                continue
        try:
            order = fetch_order(token, order_id)
            items = fetch_order_items(token, order_id)
            new_orders.append(order)
            if items:
                for it in items:
                    if isinstance(it, dict):
                        it["AmazonOrderId"] = order_id
                new_items.extend(items)
                results.append({"order_id": order_id, "status": "ok", "error": ""})
            else:
                results.append({"order_id": order_id, "status": "no_items", "error": "order items empty"})
        except Exception as exc:
            results.append({"order_id": order_id, "status": "error", "error": str(exc)})

    # Append orders
    if new_orders:
        df_orders = flatten_orders(new_orders).fillna("")
        if not existing_orders.empty:
            df_orders = pd.concat([existing_orders, df_orders], ignore_index=True)
            df_orders = df_orders.drop_duplicates(subset=["amazon_order_id"])
        df_orders.to_csv(ORDERS_ALL, index=False)

    # Append items
    if new_items:
        df_items = flatten_items(new_items).fillna("")
        if not existing_items.empty:
            df_items = pd.concat([existing_items, df_items], ignore_index=True)
            if "order_item_id" in df_items.columns:
                df_items = df_items.drop_duplicates(subset=["order_item_id"])
        df_items.to_csv(ITEMS_ALL, index=False)

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(OUT_REPORT, index=False)
    print({"status": "success", "orders_added": len(new_orders), "items_added": len(new_items), "report": str(OUT_REPORT)})


if __name__ == "__main__":
    main()

