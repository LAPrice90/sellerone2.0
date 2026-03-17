"""
Fetch marketplace participations from SP-API Sellers v0.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

import requests

from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")


def _region_for_host(host: str) -> str:
    host = host.lower()
    if "sellingpartnerapi-eu.amazon.com" in host:
        return "eu-west-1"
    if "sellingpartnerapi-na.amazon.com" in host:
        return "us-east-1"
    if "sellingpartnerapi-fe.amazon.com" in host:
        return "us-west-2"
    # Default to eu-west-1 unless explicitly overridden.
    return os.environ.get("SPAPI_AWS_REGION", "eu-west-1")


def _sign_v4(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: bytes,
    access_key: str,
    secret_key: str,
    session_token: str | None,
) -> Dict[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc
    region = _region_for_host(host)
    service = "execute-api"

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")

    headers = {k.lower(): v for k, v in headers.items()}
    headers["host"] = host
    headers["x-amz-date"] = amz_date
    if session_token:
        headers["x-amz-security-token"] = session_token

    canonical_headers = "".join(f"{k}:{headers[k].strip()}\n" for k in sorted(headers))
    signed_headers = ";".join(sorted(headers))
    payload_hash = hashlib.sha256(payload).hexdigest()

    canonical_request = "\n".join(
        [
            method,
            parsed.path or "/",
            parsed.query,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            algorithm,
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), datestamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} Credential={access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers["authorization"] = authorization
    return {k: headers[k] for k in headers}


def list_marketplace_participations() -> List[Dict[str, object]]:
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    url = f"{SPAPI_BASE_URL}/sellers/v1/marketplaceParticipations"
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    session_token = os.environ.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key:
        raise RuntimeError("Missing AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY for SigV4 signing")

    base_headers = {
        "x-amz-access-token": token,
        "accept": "application/json",
    }
    signed = _sign_v4("GET", url, base_headers, b"", access_key, secret_key, session_token)
    resp = requests.get(url, headers=signed, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"marketplaceParticipations failed: {resp.status_code} {resp.text}")
    payload = resp.json() or {}
    data = payload.get("payload") if isinstance(payload, dict) else payload
    if isinstance(data, list):
        parts = data
    else:
        parts = (data or {}).get("marketplaceParticipations") or (data or {}).get("MarketplaceParticipations") or []
    if isinstance(parts, dict):
        return [parts]
    if isinstance(parts, list):
        return parts
    return []

