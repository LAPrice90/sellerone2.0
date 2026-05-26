from __future__ import annotations

import os
from typing import Any

try:
    from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing, require_env
    from scripts.api.spapi_owner import SpApiCallContext, spapi_get
except ModuleNotFoundError:
    from api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing, require_env
    from api.spapi_owner import SpApiCallContext, spapi_get


SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.environ.get(name, str(default))).strip())
    except Exception:
        return float(default)


def seller_id_from_env() -> str:
    seller_id = (
        os.environ.get("SELLER_ID")
        or os.environ.get("SELLER_PARTNER_ID")
        or os.environ.get("MERCHANT_ID")
        or os.environ.get("SELLING_PARTNER_ID")
        or ""
    )
    if seller_id:
        return seller_id
    return require_env("SELLER_ID")


def get_listings_restrictions(
    *,
    seller_id: str,
    asin: str,
    marketplace_id: str,
    access_token: str,
    condition_type: str = "new_new",
    reason_locale: str = "en_GB",
    run_id: str = "",
    script_name: str = "F097_check_amazon_listing_restrictions.py",
    endpoint: str = "listings_restrictions_get",
    timeout: int = 30,
) -> dict[str, Any]:
    seller = _normalize_text(seller_id)
    item_asin = _normalize_text(asin).upper()
    marketplace = _normalize_text(marketplace_id)
    token = _normalize_text(access_token)
    condition = _normalize_text(condition_type)
    if seller == "":
        raise ValueError("seller_id is required")
    if item_asin == "":
        raise ValueError("asin is required")
    if marketplace == "":
        raise ValueError("marketplace_id is required")
    if token == "":
        raise ValueError("access_token is required")

    url = f"{SPAPI_BASE_URL}/listings/2021-08-01/restrictions"
    params = {
        "asin": item_asin,
        "sellerId": seller,
        "marketplaceIds": marketplace,
        "reasonLocale": _normalize_text(reason_locale) or "en_GB",
    }
    if condition:
        params["conditionType"] = condition
    headers = {
        "x-amz-access-token": token,
        "Accept": "application/json",
    }
    ctx = SpApiCallContext(
        run_id=run_id or os.environ.get("SPAPI_RUN_ID", ""),
        script_name=script_name or os.environ.get("SPAPI_SCRIPT_NAME", "unknown_script"),
        endpoint=endpoint,
        marketplace=marketplace,
        sku_count=1,
    )
    resp = spapi_get(
        ctx=ctx,
        url=url,
        spapi_base_url=SPAPI_BASE_URL,
        headers=headers,
        params=params,
        timeout=timeout,
        min_interval_sec=max(_env_float("SPAPI_LISTINGS_RESTRICTIONS_GET_MIN_INTERVAL_SEC", 0.25), 0.0),
        max_retries=2,
    )
    try:
        payload = resp.json() or {}
    except Exception:
        payload = {"raw_text": getattr(resp, "text", "")}
    return {
        "http_status": str(getattr(resp, "status_code", "")),
        "payload": payload,
    }


def run_restriction_check_for_draft_row(
    draft_row: dict[str, object],
    *,
    seller_id: str | None = None,
    access_token: str | None = None,
    reason_locale: str = "en_GB",
    run_id: str = "",
) -> dict[str, Any]:
    load_dotenv_if_missing()
    seller = _normalize_text(seller_id) or seller_id_from_env()
    token = _normalize_text(access_token) or get_lwa_access_token()
    return get_listings_restrictions(
        seller_id=seller,
        asin=_normalize_text(draft_row.get("asin", "")),
        marketplace_id=_normalize_text(draft_row.get("marketplace_id", "")),
        condition_type=_normalize_text(draft_row.get("condition_type", "")) or "new_new",
        access_token=token,
        reason_locale=reason_locale,
        run_id=run_id,
    )
