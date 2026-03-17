"""
Fetch FBA inventory summaries with optional pagination.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from scripts.api.spapi_owner import SpApiCallContext, spapi_get

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


def fetch_inventory_summaries(
    marketplace_id: str,
    access_token: str,
    granularity_type: str = "Marketplace",
    granularity_id: Optional[str] = None,
    details: bool = True,
    seller_skus: Optional[List[str]] = None,
    next_token: Optional[str] = None,
    timeout: int = 30,
    run_id: str = "",
    script_name: str = "",
) -> Tuple[List[Dict[str, object]], Optional[str]]:
    granularity_id = granularity_id or marketplace_id
    params = {
        "marketplaceIds": marketplace_id,
        "granularityType": granularity_type,
        "granularityId": granularity_id,
        "details": str(details).lower(),
    }
    if seller_skus:
        params["sellerSkus"] = ",".join(seller_skus)
    if next_token:
        params["nextToken"] = next_token
    url = f"{SPAPI_BASE_URL}/fba/inventory/v1/summaries"
    headers = {
        "x-amz-access-token": access_token,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    ctx = SpApiCallContext(
        run_id=run_id or os.environ.get("SPAPI_RUN_ID", ""),
        script_name=script_name or os.environ.get("SPAPI_SCRIPT_NAME", "unknown_script"),
        endpoint="fba_inventory_get_summaries",
        marketplace=marketplace_id,
        sku_count=len(seller_skus or []),
    )
    resp = spapi_get(
        ctx=ctx,
        url=url,
        spapi_base_url=SPAPI_BASE_URL,
        headers=headers,
        params=params,
        timeout=timeout,
        min_interval_sec=1.0,
        max_retries=2,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Inventory summaries failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    summaries = payload.get("payload") or {}
    records = summaries.get("inventorySummaries") or []
    nt = summaries.get("nextToken")
    return records, nt

