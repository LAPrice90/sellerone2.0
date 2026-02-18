"""
Helpers to fetch Orders and Order Items from SP-API.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"


class MissingEnvError(RuntimeError):
    pass


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvError(f"Missing env var: {name}")
    return value


def load_dotenv_if_missing(env_files: Optional[list[str]] = None) -> None:
    env_files = env_files or ["secrets/.env", ".env"]
    for env_file in env_files:
        path = Path(env_file)
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.split("#", 1)[0].strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def get_lwa_access_token(timeout: int = 30) -> str:
    refresh_token = require_env("LWA_REFRESH_TOKEN")
    client_id = require_env("LWA_CLIENT_ID")
    client_secret = require_env("LWA_CLIENT_SECRET")
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    resp = requests.post(LWA_TOKEN_URL, data=data, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"LWA token failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"LWA token missing in response: {payload}")
    return token


def list_orders(
    access_token: str,
    marketplace_ids: List[str],
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    updated_after: Optional[str] = None,
    updated_before: Optional[str] = None,
    next_token: Optional[str] = None,
    max_results_per_page: int = 100,
    timeout: int = 30,
) -> Tuple[List[Dict[str, object]], Optional[str]]:
    url = f"{SPAPI_BASE_URL}/orders/v0/orders"
    params: Dict[str, object] = {
        "MarketplaceIds": ",".join(marketplace_ids),
        "MaxResultsPerPage": max_results_per_page,
        "OrderStatuses": "Unshipped,PartiallyShipped,Shipped,Canceled,Pending,Unfulfillable",
    }
    if created_after:
        params["CreatedAfter"] = created_after
    if created_before:
        params["CreatedBefore"] = created_before
    if updated_after:
        params["LastUpdatedAfter"] = updated_after
    if updated_before:
        params["LastUpdatedBefore"] = updated_before
    if next_token:
        params["NextToken"] = next_token
    headers = {
        "x-amz-access-token": access_token,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Orders list failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    orders = (payload.get("payload") or {}).get("Orders") or []
    next_token = (payload.get("payload") or {}).get("NextToken")
    return orders, next_token


def list_order_items(
    access_token: str,
    amazon_order_id: str,
    next_token: Optional[str] = None,
    timeout: int = 30,
) -> Tuple[List[Dict[str, object]], Optional[str]]:
    base_url = f"{SPAPI_BASE_URL}/orders/v0/orders/{amazon_order_id}/orderItems"
    url = base_url if not next_token else f"{base_url}?NextToken={next_token}"
    headers = {
        "x-amz-access-token": access_token,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Order items failed for {amazon_order_id}: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    items = (payload.get("payload") or {}).get("OrderItems") or []
    next_token = (payload.get("payload") or {}).get("NextToken")
    return items, next_token
