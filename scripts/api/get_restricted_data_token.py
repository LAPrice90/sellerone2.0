"""
Fetch Restricted Data Token (RDT) for SP-API endpoints.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

import requests

from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing
from scripts.api.spapi_signed import sign_spapi_request


SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")


def get_rdt(restricted_resources: List[Dict[str, object]]) -> str:
    """
    restricted_resources: list of dicts with:
      - method (GET/POST/...)
      - path (/inbound/fba/2024-03-20/shipments)
      - dataElements (optional)
    """
    load_dotenv_if_missing()
    target_app = os.environ.get("SPAPI_APP_ID") or os.environ.get("LWA_CLIENT_ID") or ""
    if not target_app:
        raise RuntimeError("Missing SPAPI_APP_ID or LWA_CLIENT_ID for RDT targetApplication")

    access_token = get_lwa_access_token()
    url = f"{SPAPI_BASE_URL}/tokens/2021-03-01/restrictedDataToken"
    body = json.dumps(
        {
            "targetApplication": target_app,
            "restrictedResources": restricted_resources,
        },
        separators=(",", ":"),
    )
    headers = {
        "x-amz-access-token": access_token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    signed = sign_spapi_request("POST", url, SPAPI_BASE_URL, headers, body=body)
    signed_url = signed.pop("x-signed-url", url)
    if os.environ.get("SPAPI_RDT_DEBUG") == "1":
        print(
            json.dumps(
                {
                    "rdt_url": signed_url,
                    "rdt_body": json.loads(body),
                    "rdt_headers": {k: v for k, v in signed.items() if k.lower() != "authorization"},
                },
                indent=2,
            )
        )
    resp = requests.post(signed_url, headers=signed, data=body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"RDT failed {resp.status_code}: {resp.text}")
    payload = resp.json() or {}
    token = payload.get("restrictedDataToken")
    if not token:
        raise RuntimeError(f"RDT missing in response: {payload}")
    return token
