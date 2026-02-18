"""
Helpers to fetch financial events from SP-API finances/v0/financialEvents.
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


def list_financial_events(
    access_token: str,
    posted_after: Optional[str] = None,
    posted_before: Optional[str] = None,
    next_token: Optional[str] = None,
    timeout: int = 30,
) -> Tuple[Dict[str, object], Optional[str]]:
    url = f"{SPAPI_BASE_URL}/finances/v0/financialEvents"
    params: Dict[str, object] = {}
    if posted_after:
        params["PostedAfter"] = posted_after
    if posted_before:
        params["PostedBefore"] = posted_before
    if next_token:
        params["NextToken"] = next_token
    headers = {
        "x-amz-access-token": access_token,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Financial events failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    events = (payload.get("payload") or {}).get("FinancialEvents") or {}
    next_token = (payload.get("payload") or {}).get("NextToken")
    return events, next_token
