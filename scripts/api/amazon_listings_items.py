from __future__ import annotations

import json
import os
from typing import Any

try:
    from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing, require_env
    from scripts.api.spapi_owner import SpApiCallContext, spapi_get, spapi_put_json
except ModuleNotFoundError:
    from api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing, require_env
    from api.spapi_owner import SpApiCallContext, spapi_get, spapi_put_json


SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
VALIDATION_PREVIEW_MODE = "VALIDATION_PREVIEW"


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


def _numeric(value: object) -> float | None:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except Exception:
        return None


def _quantity(value: object) -> int:
    parsed = _numeric(value)
    if parsed is None or parsed < 0:
        return 0
    return int(parsed)


def _truthy_flag(value: object) -> bool:
    text = _normalize_text(value).lower()
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return True


def currency_for_marketplace(marketplace_id: str) -> str:
    marketplace = _normalize_text(marketplace_id)
    if marketplace == "A1F83G8C2ARO7P":
        return "GBP"
    return "GBP"


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


def build_offer_only_listing_payload(draft_row: dict[str, object], *, currency_code: str | None = None) -> dict[str, Any]:
    marketplace_id = _normalize_text(draft_row.get("marketplace_id", ""))
    price = _numeric(draft_row.get("starting_price_gbp", ""))
    if price is None:
        raise ValueError("starting_price_gbp is required for Amazon listing preview")

    currency = (_normalize_text(currency_code) or _normalize_text(draft_row.get("currency_code", ""))).upper()
    if currency == "":
        currency = currency_for_marketplace(marketplace_id)
    product_type = _normalize_text(draft_row.get("product_type", "")) or "PRODUCT"
    condition_type = _normalize_text(draft_row.get("condition_type", ""))
    asin = _normalize_text(draft_row.get("asin", "")).upper()
    fulfillment_channel = _normalize_text(draft_row.get("fulfillment_channel", ""))
    country_of_origin = _normalize_text(draft_row.get("country_of_origin", "")).upper()
    product_tax_code = _normalize_text(draft_row.get("product_tax_code", ""))
    price_includes_tax = _truthy_flag(draft_row.get("price_includes_tax", "1"))

    if marketplace_id == "":
        raise ValueError("marketplace_id is required for Amazon listing preview")
    if condition_type == "":
        raise ValueError("condition_type is required for Amazon listing preview")
    if asin == "":
        raise ValueError("asin is required for Amazon listing preview")
    if fulfillment_channel == "":
        raise ValueError("fulfillment_channel is required for Amazon listing preview")
    if len(country_of_origin) != 2 or not country_of_origin.isalpha():
        raise ValueError("country_of_origin is required for Amazon listing preview")
    if product_tax_code == "":
        raise ValueError("product_tax_code is required for Amazon listing preview")
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency_code is required for Amazon listing preview")

    price_key = "value_with_tax" if price_includes_tax else "value"

    return {
        "productType": product_type,
        "requirements": "LISTING_OFFER_ONLY",
        "attributes": {
            "condition_type": [
                {
                    "value": condition_type,
                    "marketplace_id": marketplace_id,
                }
            ],
            "merchant_suggested_asin": [
                {
                    "value": asin,
                    "marketplace_id": marketplace_id,
                }
            ],
            "country_of_origin": [
                {
                    "value": country_of_origin,
                    "marketplace_id": marketplace_id,
                }
            ],
            "product_tax_code": [
                {
                    "value": product_tax_code,
                    "marketplace_id": marketplace_id,
                }
            ],
            "fulfillment_availability": [
                {
                    "fulfillment_channel_code": fulfillment_channel,
                    "quantity": _quantity(draft_row.get("starting_quantity", "")),
                }
            ],
            "purchasable_offer": [
                {
                    "audience": "ALL",
                    "currency": currency,
                    "marketplace_id": marketplace_id,
                    "our_price": [
                        {
                            "schedule": [
                                {
                                    price_key: round(price, 2),
                                }
                            ]
                        }
                    ],
                }
            ],
        },
    }


def put_listings_item(
    *,
    seller_id: str,
    sku: str,
    marketplace_id: str,
    access_token: str,
    payload: dict[str, Any],
    issue_locale: str = "en_GB",
    mode: str = "",
    run_id: str = "",
    script_name: str = "amazon_listings_items.py",
    endpoint: str = "listings_items_put",
    timeout: int = 30,
) -> dict[str, Any]:
    seller = _normalize_text(seller_id)
    seller_sku = _normalize_text(sku)
    marketplace = _normalize_text(marketplace_id)
    token = _normalize_text(access_token)
    if seller == "":
        raise ValueError("seller_id is required")
    if seller_sku == "":
        raise ValueError("sku is required")
    if marketplace == "":
        raise ValueError("marketplace_id is required")
    if token == "":
        raise ValueError("access_token is required")

    url = f"{SPAPI_BASE_URL}/listings/2021-08-01/items/{seller}/{seller_sku}"
    params = {
        "marketplaceIds": marketplace,
        "issueLocale": _normalize_text(issue_locale) or "en_GB",
    }
    submit_mode = _normalize_text(mode)
    if submit_mode != "":
        params["mode"] = submit_mode
    if submit_mode == VALIDATION_PREVIEW_MODE:
        params["includedData"] = "issues,identifiers"
    headers = {
        "x-amz-access-token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    ctx = SpApiCallContext(
        run_id=run_id or os.environ.get("SPAPI_RUN_ID", ""),
        script_name=script_name or os.environ.get("SPAPI_SCRIPT_NAME", "unknown_script"),
        endpoint=endpoint,
        marketplace=marketplace,
        sku_count=1,
    )
    body = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    resp = spapi_put_json(
        ctx=ctx,
        url=url,
        spapi_base_url=SPAPI_BASE_URL,
        headers=headers,
        params=params,
        body=body,
        timeout=timeout,
        min_interval_sec=max(_env_float("SPAPI_LISTINGS_ITEMS_PUT_MIN_INTERVAL_SEC", 1.0), 1.0),
        max_retries=2,
    )
    try:
        response_payload = resp.json() or {}
    except Exception:
        response_payload = {"raw_text": getattr(resp, "text", "")}
    return {
        "http_status": str(getattr(resp, "status_code", "")),
        "payload": response_payload,
    }


def get_listings_item(
    *,
    seller_id: str,
    sku: str,
    marketplace_id: str,
    access_token: str,
    issue_locale: str = "en_GB",
    included_data: str = "summaries,attributes,issues,offers,fulfillmentAvailability",
    run_id: str = "",
    script_name: str = "F095_check_amazon_listing_submission_status.py",
    endpoint: str = "listings_items_get_item",
    timeout: int = 30,
) -> dict[str, Any]:
    seller = _normalize_text(seller_id)
    seller_sku = _normalize_text(sku)
    marketplace = _normalize_text(marketplace_id)
    token = _normalize_text(access_token)
    if seller == "":
        raise ValueError("seller_id is required")
    if seller_sku == "":
        raise ValueError("sku is required")
    if marketplace == "":
        raise ValueError("marketplace_id is required")
    if token == "":
        raise ValueError("access_token is required")

    url = f"{SPAPI_BASE_URL}/listings/2021-08-01/items/{seller}/{seller_sku}"
    params = {
        "marketplaceIds": marketplace,
        "includedData": _normalize_text(included_data) or "summaries,attributes,issues",
        "issueLocale": _normalize_text(issue_locale) or "en_GB",
    }
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
        min_interval_sec=max(_env_float("SPAPI_LISTINGS_ITEMS_GET_MIN_INTERVAL_SEC", 0.25), 0.0),
        max_retries=2,
    )
    try:
        response_payload = resp.json() or {}
    except Exception:
        response_payload = {"raw_text": getattr(resp, "text", "")}
    return {
        "http_status": str(getattr(resp, "status_code", "")),
        "payload": response_payload,
    }


def preview_put_listings_item(
    *,
    seller_id: str,
    sku: str,
    marketplace_id: str,
    access_token: str,
    payload: dict[str, Any],
    issue_locale: str = "en_GB",
    run_id: str = "",
    script_name: str = "F093_run_amazon_listing_preview.py",
    timeout: int = 30,
) -> dict[str, Any]:
    return put_listings_item(
        seller_id=seller_id,
        sku=sku,
        marketplace_id=marketplace_id,
        access_token=access_token,
        payload=payload,
        issue_locale=issue_locale,
        mode=VALIDATION_PREVIEW_MODE,
        run_id=run_id,
        script_name=script_name,
        endpoint="listings_items_put_validation_preview",
        timeout=timeout,
    )


def submit_put_listings_item(
    *,
    seller_id: str,
    sku: str,
    marketplace_id: str,
    access_token: str,
    payload: dict[str, Any],
    issue_locale: str = "en_GB",
    run_id: str = "",
    script_name: str = "F094_submit_amazon_listing_drafts.py",
    timeout: int = 30,
) -> dict[str, Any]:
    return put_listings_item(
        seller_id=seller_id,
        sku=sku,
        marketplace_id=marketplace_id,
        access_token=access_token,
        payload=payload,
        issue_locale=issue_locale,
        mode="",
        run_id=run_id,
        script_name=script_name,
        endpoint="listings_items_put_live_submit",
        timeout=timeout,
    )


def run_preview_for_draft_row(
    draft_row: dict[str, object],
    *,
    seller_id: str | None = None,
    access_token: str | None = None,
    issue_locale: str = "en_GB",
    run_id: str = "",
) -> dict[str, Any]:
    load_dotenv_if_missing()
    seller = _normalize_text(seller_id) or seller_id_from_env()
    token = _normalize_text(access_token) or get_lwa_access_token()
    payload = build_offer_only_listing_payload(draft_row)
    return preview_put_listings_item(
        seller_id=seller,
        sku=_normalize_text(draft_row.get("expected_seller_sku", "")),
        marketplace_id=_normalize_text(draft_row.get("marketplace_id", "")),
        access_token=token,
        payload=payload,
        issue_locale=issue_locale,
        run_id=run_id,
    )


def run_submit_for_draft_row(
    draft_row: dict[str, object],
    *,
    seller_id: str | None = None,
    access_token: str | None = None,
    issue_locale: str = "en_GB",
    run_id: str = "",
) -> dict[str, Any]:
    load_dotenv_if_missing()
    seller = _normalize_text(seller_id) or seller_id_from_env()
    token = _normalize_text(access_token) or get_lwa_access_token()
    payload = build_offer_only_listing_payload(draft_row)
    return submit_put_listings_item(
        seller_id=seller,
        sku=_normalize_text(draft_row.get("expected_seller_sku", "")),
        marketplace_id=_normalize_text(draft_row.get("marketplace_id", "")),
        access_token=token,
        payload=payload,
        issue_locale=issue_locale,
        run_id=run_id,
    )


def run_readback_for_draft_row(
    draft_row: dict[str, object],
    *,
    seller_id: str | None = None,
    access_token: str | None = None,
    issue_locale: str = "en_GB",
    run_id: str = "",
) -> dict[str, Any]:
    load_dotenv_if_missing()
    seller = _normalize_text(seller_id) or seller_id_from_env()
    token = _normalize_text(access_token) or get_lwa_access_token()
    return get_listings_item(
        seller_id=seller,
        sku=_normalize_text(draft_row.get("expected_seller_sku", "")),
        marketplace_id=_normalize_text(draft_row.get("marketplace_id", "")),
        access_token=token,
        issue_locale=issue_locale,
        run_id=run_id,
    )
