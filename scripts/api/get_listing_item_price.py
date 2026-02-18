"""
Fetch *our* offer price for SKUs using the Listings Items API.

This returns the seller's own offer price (not Buy Box, not lowest competitor),
which is what we want for Level 1 estimates when customers click our offer.
"""

from __future__ import annotations

import os
import time
from typing import Dict, List, Tuple

from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing, require_env
from scripts.api.spapi_owner import SpApiCallContext, spapi_get

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.environ.get(name, str(default))).strip())
    except Exception:
        return float(default)


def _pick_listing_price(offer: dict) -> Tuple[str, str]:
    """
    Try to extract listing price from a single offer entry.
    Returns (amount, currency) or ("", "").
    """
    # Common structure: offer["price"] is a list of price components.
    price = offer.get("price")
    if isinstance(price, list):
        for entry in price:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") == "ListingPrice":
                val = entry.get("value") or {}
                amt = val.get("amount")
                cur = val.get("currencyCode")
                if amt is not None and cur:
                    return str(amt), str(cur)
        # Fallback: first price entry with value
        for entry in price:
            if not isinstance(entry, dict):
                continue
            val = entry.get("value") or {}
            amt = val.get("amount")
            cur = val.get("currencyCode")
            if amt is not None and cur:
                return str(amt), str(cur)

    # Alternate structure: offer["price"] is a dict
    if isinstance(price, dict):
        amt = price.get("amount")
        cur = price.get("currencyCode")
        if amt is not None and cur:
            return str(amt), str(cur)

    # Alternate structure: offer["listingPrice"]
    listing = offer.get("listingPrice") or offer.get("ListingPrice") or {}
    if isinstance(listing, dict):
        amt = listing.get("amount")
        cur = listing.get("currencyCode")
        if amt is not None and cur:
            return str(amt), str(cur)

    return "", ""


def _extract_our_offer_price(payload: dict) -> Tuple[str, str]:
    """
    Extract our offer price from Listings Items API response.
    Returns (amount, currency) or ("", "").
    """
    # Listings Items responses vary slightly by region and includedData.
    root = payload or {}
    offers = root.get("offers") or (root.get("payload") or {}).get("offers") or []
    if not isinstance(offers, list):
        offers = []

    for offer in offers:
        if not isinstance(offer, dict):
            continue
        amt, cur = _pick_listing_price(offer)
        if amt and cur:
            return amt, cur

    return "", ""


def fetch_our_offer_prices(
    skus: List[str],
    marketplace_id: str,
    access_token: str,
    seller_id: str,
    run_id: str = "",
    script_name: str = "",
    sleep_sec: float = 0.25,
    timeout: int = 30,
) -> Dict[str, Dict[str, str]]:
    """
    Fetch our offer prices for SKUs (one-by-one; Listings Items has no batch).
    Returns dict: sku -> {"price": "...", "currency": "..."}.
    """
    out: Dict[str, Dict[str, str]] = {}
    if not skus:
        return out

    uniq = [s for s in dict.fromkeys(skus) if s]
    for i, sku in enumerate(uniq, start=1):
        params = {
            "marketplaceIds": marketplace_id,
            "includedData": "offers",
        }
        url = f"{SPAPI_BASE_URL}/listings/2021-08-01/items/{seller_id}/{sku}"
        headers = {
            "x-amz-access-token": access_token,
            "Accept": "application/json",
        }
        ctx = SpApiCallContext(
            run_id=run_id or os.environ.get("SPAPI_RUN_ID", ""),
            script_name=script_name or os.environ.get("SPAPI_SCRIPT_NAME", "unknown_script"),
            endpoint="listings_items_get_item",
            marketplace=marketplace_id,
            sku_count=1,
        )
        resp = spapi_get(
            ctx=ctx,
            url=url,
            spapi_base_url=SPAPI_BASE_URL,
            headers=headers,
            params=params,
            timeout=timeout,
            min_interval_sec=max(_env_float("SPAPI_LISTINGS_ITEMS_MIN_INTERVAL_SEC", 0.25), 0.0),
            max_retries=2,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Listings Items API failed for {sku}: {resp.status_code} {resp.text}")
        payload = resp.json() or {}
        price, cur = _extract_our_offer_price(payload)
        if price and cur:
            out[sku] = {"price": price, "currency": cur}

        # Rate limit spacing between SKUs
        if i < len(uniq):
            time.sleep(sleep_sec)

    return out


def run_own_offer_price_lookup(
    skus: List[str],
    marketplace_id: str,
    run_id: str = "",
    script_name: str = "",
) -> Dict[str, Dict[str, str]]:
    """
    Helper for scripts: loads env, gets LWA token, fetches our offer prices.
    """
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    seller_id = (
        os.environ.get("SELLER_ID")
        or os.environ.get("SELLER_PARTNER_ID")
        or os.environ.get("MERCHANT_ID")
        or os.environ.get("SELLING_PARTNER_ID")
        or ""
    )
    if not seller_id:
        # Use require_env for a clear error message if nothing is set.
        seller_id = require_env("SELLER_ID")
    sleep_sec = _env_float("SPAPI_LISTINGS_ITEMS_SLEEP_SEC", _env_float("PRICE_API_SLEEP_SEC", 0.25))
    return fetch_our_offer_prices(
        skus=skus,
        marketplace_id=marketplace_id,
        access_token=token,
        seller_id=seller_id,
        run_id=run_id,
        script_name=script_name,
        sleep_sec=sleep_sec,
    )
