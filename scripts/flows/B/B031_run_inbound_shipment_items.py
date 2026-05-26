"""
Fetch inbound shipment item contents via Fulfillment Inbound API and write mapping.

Outputs:
- out/inbound_shipment_contents.csv
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing  # noqa: E402
from scripts.api.spapi_signed import sign_spapi_request  # noqa: E402
from scripts.api.get_restricted_data_token import get_rdt  # noqa: E402
from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe  # noqa: E402


SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
MARKETPLACE_ID = os.environ.get("MARKETPLACE_ID")
OUT_MAP = Path("out/inbound_shipment_contents.csv")
SQL_TABLE_INBOUND_SHIPMENT_CONTENTS = "sys_inbound_shipment_contents"


def _list_shipments(access_token: str) -> List[str]:
    """
    List inbound shipment IDs via Fulfillment Inbound API v2024-03-20.
    Uses pagination token when present.
    """
    url = f"{SPAPI_BASE_URL}/inbound/fba/2024-03-20/shipments"
    rdt = get_rdt(
        [
            {
                "method": "GET",
                "path": "/inbound/fba/2024-03-20/shipments",
            }
        ]
    )
    headers = {
        "x-amz-access-token": rdt,
        "Accept": "application/json",
    }
    shipment_ids: List[str] = []
    next_token = None
    while True:
        params = {}
        if MARKETPLACE_ID:
            params["marketplaceId"] = MARKETPLACE_ID
        if next_token:
            params["nextToken"] = next_token
        signed = sign_spapi_request("GET", url, SPAPI_BASE_URL, headers, params=params)
        signed_url = signed.pop("x-signed-url", url)
        resp = requests.get(signed_url, headers=signed, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"List shipments failed {resp.status_code}: {resp.text}")
        payload = resp.json() or {}
        data = payload.get("payload") or payload
        items = data.get("shipments") or data.get("Shipments") or data.get("shipmentSummaries") or []
        if isinstance(items, dict):
            items = [items]
        for it in items:
            sid = it.get("shipmentId") or it.get("ShipmentId")
            if sid:
                shipment_ids.append(str(sid))
        next_token = data.get("nextToken") or data.get("NextToken")
        if not next_token:
            break
    return sorted(set(shipment_ids))


def _fetch_items(access_token: str, shipment_id: str) -> List[Dict[str, object]]:
    url = f"{SPAPI_BASE_URL}/inbound/fba/2024-03-20/shipments/{shipment_id}/items"
    rdt = get_rdt(
        [
            {
                "method": "GET",
                "path": f"/inbound/fba/2024-03-20/shipments/{shipment_id}/items",
            }
        ]
    )
    headers = {
        "x-amz-access-token": rdt,
        "Accept": "application/json",
    }
    params = {}
    if MARKETPLACE_ID:
        params["marketplaceId"] = MARKETPLACE_ID
    signed = sign_spapi_request("GET", url, SPAPI_BASE_URL, headers, params=params)
    signed_url = signed.pop("x-signed-url", url)
    resp = requests.get(signed_url, headers=signed, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Shipment items failed {resp.status_code}: {resp.text}")
    payload = resp.json() or {}
    data = payload.get("payload") or payload
    items = data.get("items") or data.get("Items") or data.get("shipmentItems") or []
    if isinstance(items, dict):
        items = [items]
    return items


def _write_output_frame(df: pd.DataFrame, path: Path, sql_table: str) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE"))
    sql_rows = 0
    if mode in {"sql_shadow", "sql_primary_csv_export"}:
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, sql_table, df)
            sql_rows = int(result["rows"])
        finally:
            store.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return {
        "mode": mode,
        "path": str(path),
        "csv_rows": int(len(df.index)),
        "sql_table": sql_table if mode != "csv" else "",
        "sql_rows": sql_rows,
    }


def main() -> None:
    load_dotenv_if_missing()
    access_token = get_lwa_access_token()
    shipment_ids = _list_shipments(access_token)
    if not shipment_ids:
        print({"status": "skip", "reason": "no_inbound_shipment_ids"})
        return

    access_token = get_lwa_access_token()
    rows = []
    for sid in shipment_ids:
        try:
            items = _fetch_items(access_token, sid)
        except Exception as exc:
            print({"status": "warning", "shipment_id": sid, "error": str(exc)})
            continue
        for it in items:
            sku = it.get("sellerSku") or it.get("sellerSKU") or it.get("seller_sku") or ""
            qty = it.get("quantity") or it.get("quantityShipped") or it.get("quantityReceived") or ""
            rows.append({"inbound_shipment_id": sid, "sku": sku, "quantity": qty})

    if not rows:
        print({"status": "skip", "reason": "no_items_returned"})
        return

    df = pd.DataFrame(rows)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)
    df = df[df["quantity"] > 0]
    df = df[df["sku"].astype(str).str.len() > 0]
    df = df.groupby(["inbound_shipment_id", "sku"], dropna=False)["quantity"].sum().reset_index()

    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    _write_output_frame(df, OUT_MAP, SQL_TABLE_INBOUND_SHIPMENT_CONTENTS)

    print(
        json.dumps(
            {"status": "success", "shipment_ids": len(shipment_ids), "rows": len(df), "map": str(OUT_MAP)},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()


