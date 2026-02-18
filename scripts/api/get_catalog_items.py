"""
Helpers to call Catalog Items (2022-04-01).
"""

from __future__ import annotations

import os
from typing import Dict

import requests

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
CATALOG_BASE_URL = "https://sellingpartnerapi-eu.amazon.com"


class MissingEnvError(RuntimeError):
    pass


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvError(f"Missing env var: {name}")
    return value


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


def fetch_catalog_item(asin: str, marketplace_id: str, access_token: str, timeout: int = 30) -> Dict[str, object]:
    url = f"{CATALOG_BASE_URL}/catalog/2022-04-01/items/{asin}"
    params = {
        "marketplaceIds": marketplace_id,
        "includedData": "images,attributes,summaries,productTypes,identifiers,relationships",
    }
    headers = {
        "x-amz-access-token": access_token,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    out: Dict[str, object] = {"asin": asin, "status": resp.status_code, "data": None, "error": None}
    if resp.status_code == 200:
        out["data"] = resp.json()
    else:
        try:
            out["error"] = resp.json()
        except Exception:
            out["error"] = resp.text
    return out
