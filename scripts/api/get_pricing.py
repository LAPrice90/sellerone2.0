"""
Fetch listing prices for SKUs using the SP-API Product Pricing endpoint.

Notes:
- Uses batch calls (up to PRICE_API_BATCH_SIZE SKUs per request).
- Returns a map: sku -> {price, currency}
- This is intended for Level 1 estimates only. It does NOT write to Sheets.
"""

from __future__ import annotations

import math
import os
import time
from typing import Dict, List, Tuple

from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing
from scripts.api.spapi_owner import SpApiCallContext, spapi_get

SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.environ.get(name, str(default))).strip())
    except Exception:
        return float(default)


def _offer_price(offer: dict) -> Tuple[str, str]:
    buying = offer.get("BuyingPrice") or {}
    listing = buying.get("ListingPrice") or {}
    amt = listing.get("Amount")
    cur = listing.get("CurrencyCode")
    if amt is None or not cur:
        return "", ""
    return str(amt), str(cur)


def _offer_shipping(offer: dict) -> Tuple[str, str]:
    buying = offer.get("BuyingPrice") or {}
    shipping = buying.get("Shipping") or {}
    amt = shipping.get("Amount")
    cur = shipping.get("CurrencyCode")
    if amt is None:
        return "", str(cur or "")
    return str(amt), str(cur or "")


def _offer_landed_price(offer: dict) -> Tuple[str, str]:
    listing, cur = _offer_price(offer)
    if not listing or not cur:
        return "", ""
    shipping, shipping_cur = _offer_shipping(offer)
    listing_num = _to_float(listing)
    shipping_num = _to_float(shipping)
    if listing_num is None:
        return "", ""
    if shipping_num is None:
        return str(listing_num), cur
    if shipping_cur and shipping_cur != cur:
        return str(listing_num), cur
    return str(listing_num + shipping_num), cur


def _to_float(text: str) -> float | None:
    try:
        return float(str(text))
    except Exception:
        return None


def _channel_from_offer(offer: dict) -> str:
    # Product Pricing may expose either a boolean or channel text.
    if offer.get("IsFulfilledByAmazon") is True:
        return "FBA"
    if offer.get("IsFulfilledByAmazon") is False:
        return "FBM"

    raw = str(
        offer.get("FulfillmentChannel")
        or offer.get("fulfillmentChannel")
        or offer.get("ShipsFrom")
        or ""
    ).strip().upper()
    if not raw:
        return "Unknown"
    if any(tag in raw for tag in ["AMAZON", "FBA", "AFN"]):
        return "FBA"
    if any(tag in raw for tag in ["MERCHANT", "FBM", "MFN", "DEFAULT"]):
        return "FBM"
    return "Unknown"


def _channel_from_value(raw: object) -> str:
    txt = str(raw or "").strip().upper()
    if any(tag in txt for tag in ["AMAZON", "FBA", "AFN"]):
        return "FBA"
    if any(tag in txt for tag in ["MERCHANT", "FBM", "MFN", "DEFAULT"]):
        return "FBM"
    return "Unknown"


def _seller_id_from_offer(offer: dict, fallback_index: int) -> str:
    for key in ("SellerId", "sellerId", "MerchantId", "merchantId", "SellerIdentifier", "sellerIdentifier"):
        val = str(offer.get(key, "")).strip()
        if val:
            return val
    return f"unknown_{fallback_index}"


def _safe_int(value: object) -> int | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        return int(float(text))
    except Exception:
        return None


def _delivery_days_from_offer(offer: dict) -> Tuple[str, str]:
    shipping = offer.get("ShippingTime") or offer.get("shippingTime") or {}
    if not isinstance(shipping, dict):
        return "", ""

    min_hours = None
    max_hours = None
    for key in ("minimumHours", "MinimumHours", "minHours", "MinHours"):
        parsed = _safe_int(shipping.get(key))
        if parsed is not None:
            min_hours = parsed
            break
    for key in ("maximumHours", "MaximumHours", "maxHours", "MaxHours"):
        parsed = _safe_int(shipping.get(key))
        if parsed is not None:
            max_hours = parsed
            break

    if min_hours is None and max_hours is None:
        return "", ""

    min_days = ""
    max_days = ""
    if min_hours is not None:
        min_days = str(max(0, int(math.ceil(min_hours / 24.0))))
    if max_hours is not None:
        max_days = str(max(0, int(math.ceil(max_hours / 24.0))))
    return min_days, max_days


def _extract_offer_rows_from_item_offers(payload: dict) -> List[Dict[str, str]]:
    out_rows: List[Dict[str, str]] = []
    body = payload.get("payload") or {}
    offers = body.get("Offers") or []
    if not isinstance(offers, list):
        return out_rows

    for idx, offer in enumerate(offers, start=1):
        if not isinstance(offer, dict):
            continue
        listing_price, currency = _price_from_obj(offer)
        shipping_price, shipping_currency = _shipping_from_obj(offer)
        landed_price, landed_currency = _landed_price_from_obj(offer)
        ch = _channel_from_offer(offer)
        is_prime = ""
        prime_info = offer.get("PrimeInformation") or offer.get("primeInformation") or {}
        if isinstance(prime_info, dict):
            is_prime_raw = prime_info.get("IsPrime")
            if is_prime_raw is None:
                is_prime_raw = prime_info.get("isPrime")
        else:
            is_prime_raw = None
        if is_prime_raw is True:
            is_prime = "1"
        elif is_prime_raw is False:
            is_prime = "0"

        min_days, max_days = _delivery_days_from_offer(offer)
        delivery_range = ""
        if min_days != "" and max_days != "":
            try:
                delivery_range = str(max(int(max_days) - int(min_days), 0))
            except Exception:
                delivery_range = ""

        notes = ""
        if str(currency).strip().upper() not in {"", "GBP"}:
            notes = "non_gbp_offer"
        elif shipping_currency and str(shipping_currency).strip().upper() not in {"", "GBP"}:
            notes = "non_gbp_shipping"

        out_rows.append(
            {
                "seller_id": _seller_id_from_offer(offer, idx),
                "offer_price_gbp": listing_price if str(currency).strip().upper() == "GBP" else "",
                "offer_shipping_price_gbp": shipping_price if str(shipping_currency or currency).strip().upper() in {"", "GBP"} else "",
                "offer_landed_price_gbp": landed_price if str(landed_currency).strip().upper() == "GBP" else "",
                "seller_seen_flag": "1",
                "is_prime": is_prime,
                "fulfilment_channel": ch if ch != "Unknown" else "Unknown",
                "min_delivery_days": min_days,
                "max_delivery_days": max_days,
                "delivery_range_days": delivery_range,
                "notes": notes,
            }
        )
    return out_rows


def _extract_market_context(payload_item: dict) -> Dict[str, str]:
    """
    Extract market context from Product Pricing payload.
    Returns:
    - price/currency (buy box preferred)
    - buy_box_channel
    - lowest_fba_price
    - lowest_fbm_price
    - offer_count_fba / offer_count_fbm
    """
    out: Dict[str, str] = {
        "price": "",
        "currency": "",
        "buy_box_channel": "",
        "lowest_fba_price": "",
        "lowest_fbm_price": "",
        "offer_count_fba": "",
        "offer_count_fbm": "",
    }
    product = payload_item.get("Product") or {}
    offers = product.get("Offers") or []

    fba_prices: List[float] = []
    fbm_prices: List[float] = []
    counted_fba = 0
    counted_fbm = 0
    winning_offer_found = False

    for offer in offers:
        if not isinstance(offer, dict):
            continue
        ch = _channel_from_offer(offer)
        price, curr = _offer_landed_price(offer)
        price_num = _to_float(price) if price else None

        if ch == "FBA":
            counted_fba += 1
            if price_num is not None:
                fba_prices.append(price_num)
        elif ch == "FBM":
            counted_fbm += 1
            if price_num is not None:
                fbm_prices.append(price_num)

        if offer.get("IsBuyBoxWinner") is True and price and curr:
            out["price"] = price
            out["currency"] = curr
            out["buy_box_channel"] = ch
            winning_offer_found = True

    # Fallback to BuyBoxPrices for price if winner-specific offer wasn't present.
    if not winning_offer_found:
        buybox = product.get("BuyBoxPrices") or []
        for bb in buybox:
            if not isinstance(bb, dict):
                continue
            amt, cur = _landed_price_from_obj(bb)
            if not amt or not cur:
                continue
            out["price"] = str(amt)
            out["currency"] = str(cur)
            ch = _channel_from_value(bb.get("condition") or bb.get("fulfillmentChannel"))
            out["buy_box_channel"] = ch
            break

    # Final fallback: first priced offer.
    if not out["price"] or not out["currency"]:
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            price, curr = _offer_landed_price(offer)
            if price and curr:
                out["price"] = price
                out["currency"] = curr
                break

    # Prefer explicit NumberOfOffers breakdown when available.
    counted_from_breakdown = False
    for item in product.get("NumberOfOffers") or []:
        if not isinstance(item, dict):
            continue
        ch = _channel_from_value(item.get("fulfillmentChannel") or item.get("FulfillmentChannel"))
        count_raw = item.get("OfferCount") if "OfferCount" in item else item.get("offerCount")
        try:
            count_val = int(count_raw)
        except Exception:
            continue
        if ch == "FBA":
            counted_fba += count_val
            counted_from_breakdown = True
        elif ch == "FBM":
            counted_fbm += count_val
            counted_from_breakdown = True
    if counted_from_breakdown:
        # Breakdown counts are authoritative; remove per-offer increments.
        # Reset based on breakdown only.
        counted_fba = 0
        counted_fbm = 0
        for item in product.get("NumberOfOffers") or []:
            if not isinstance(item, dict):
                continue
            ch = _channel_from_value(item.get("fulfillmentChannel") or item.get("FulfillmentChannel"))
            count_raw = item.get("OfferCount") if "OfferCount" in item else item.get("offerCount")
            try:
                count_val = int(count_raw)
            except Exception:
                continue
            if ch == "FBA":
                counted_fba += count_val
            elif ch == "FBM":
                counted_fbm += count_val

    if fba_prices:
        out["lowest_fba_price"] = str(min(fba_prices))
    if fbm_prices:
        out["lowest_fbm_price"] = str(min(fbm_prices))
    if counted_fba > 0:
        out["offer_count_fba"] = str(counted_fba)
    if counted_fbm > 0:
        out["offer_count_fbm"] = str(counted_fbm)

    # Preserve channel visibility for health and downstream logic.
    if not out["buy_box_channel"]:
        out["buy_box_channel"] = "Unknown"
    return out


def _extract_sku(payload_item: dict) -> str:
    """
    Extract Seller SKU from known Product Pricing payload shapes.
    """
    # Current live shape often uses top-level SellerSKU/SellerSku.
    top_level = payload_item.get("SellerSKU") or payload_item.get("SellerSku") or ""
    if top_level:
        return str(top_level)

    # Backward/alternate shape may nest under Identifier.
    ident = payload_item.get("Identifier") or {}
    nested = ident.get("SellerSKU") or ident.get("SellerSku") or ""
    if nested:
        return str(nested)

    return ""


def fetch_pricing_for_skus(
    skus: List[str],
    marketplace_id: str,
    access_token: str,
    run_id: str = "",
    script_name: str = "",
    batch_size: int = 20,
    sleep_sec: float = 2.1,
    timeout: int = 30,
) -> Dict[str, Dict[str, str]]:
    """
    Fetch listing prices for SKUs.
    Returns dict: sku -> market context fields:
    - price, currency
    - buy_box_channel
    - lowest_fba_price, lowest_fbm_price
    - offer_count_fba, offer_count_fbm
    """
    out: Dict[str, Dict[str, str]] = {}
    if not skus:
        return out

    # Dedupe and chunk
    uniq = [s for s in dict.fromkeys(skus) if s]
    batches = [uniq[i : i + batch_size] for i in range(0, len(uniq), batch_size)]

    for i, batch in enumerate(batches, start=1):
        params = {
            "MarketplaceId": marketplace_id,
            "ItemType": "Sku",
            "Skus": ",".join(batch),
        }
        url = f"{SPAPI_BASE_URL}/products/pricing/v0/price"
        headers = {
            "x-amz-access-token": access_token,
            "Accept": "application/json",
        }
        ctx = SpApiCallContext(
            run_id=run_id or os.environ.get("SPAPI_RUN_ID", ""),
            script_name=script_name or os.environ.get("SPAPI_SCRIPT_NAME", "unknown_script"),
            endpoint="products_pricing_get_price",
            marketplace=marketplace_id,
            sku_count=len(batch),
        )
        resp = spapi_get(
            ctx=ctx,
            url=url,
            spapi_base_url=SPAPI_BASE_URL,
            headers=headers,
            params=params,
            timeout=timeout,
            min_interval_sec=max(_env_float("SPAPI_PRICE_BATCH_MIN_INTERVAL_SEC", 2.1), 0.0),
            max_retries=2,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Pricing API failed: {resp.status_code} {resp.text}")

        payload = resp.json() or {}
        items = payload.get("payload") or []
        for item in items:
            sku = _extract_sku(item)
            ctx_data = _extract_market_context(item)
            if sku and (ctx_data.get("price") or ctx_data.get("lowest_fba_price") or ctx_data.get("lowest_fbm_price")):
                out[sku] = ctx_data

        # Rate limit spacing between batches
        if i < len(batches):
            time.sleep(sleep_sec)

    return out


def run_live_price_lookup(
    skus: List[str],
    marketplace_id: str,
    run_id: str = "",
    script_name: str = "",
) -> Dict[str, Dict[str, str]]:
    """
    Helper for scripts: loads env, gets LWA token, fetches pricing.
    """
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    batch_size = int(os.environ.get("PRICE_API_BATCH_SIZE", "20"))
    sleep_sec = _env_float("PRICE_API_BATCH_SLEEP_SEC", _env_float("PRICE_API_SLEEP_SEC", 2.1))
    return fetch_pricing_for_skus(
        skus=skus,
        marketplace_id=marketplace_id,
        access_token=token,
        run_id=run_id,
        script_name=script_name,
        batch_size=batch_size,
        sleep_sec=sleep_sec,
    )


def _price_from_obj(obj: dict) -> Tuple[str, str]:
    if not isinstance(obj, dict):
        return "", ""
    for key in ("ListingPrice", "listingPrice", "LandedPrice", "landedPrice"):
        price_obj = obj.get(key) or {}
        if not isinstance(price_obj, dict):
            continue
        amt = price_obj.get("Amount")
        cur = price_obj.get("CurrencyCode") or price_obj.get("currencyCode")
        if amt is not None and cur:
            return str(amt), str(cur)

    # Some payload branches may already be a price object.
    amt = obj.get("Amount")
    cur = obj.get("CurrencyCode") or obj.get("currencyCode")
    if amt is None or not cur:
        return "", ""
    return str(amt), str(cur)


def _shipping_from_obj(obj: dict) -> Tuple[str, str]:
    if not isinstance(obj, dict):
        return "", ""
    shipping = obj.get("Shipping") or obj.get("shipping") or {}
    amt = shipping.get("Amount")
    cur = shipping.get("CurrencyCode") or shipping.get("currencyCode")
    if amt is None:
        return "", str(cur or "")
    return str(amt), str(cur or "")


def _landed_price_from_obj(obj: dict) -> Tuple[str, str]:
    if not isinstance(obj, dict):
        return "", ""
    landed = obj.get("LandedPrice") or obj.get("landedPrice") or {}
    if isinstance(landed, dict):
        landed_amt = landed.get("Amount")
        landed_cur = landed.get("CurrencyCode") or landed.get("currencyCode")
        if landed_amt is not None and landed_cur:
            return str(landed_amt), str(landed_cur)

    listing, cur = _price_from_obj(obj)
    if not listing or not cur:
        return "", ""
    shipping, shipping_cur = _shipping_from_obj(obj)
    listing_num = _to_float(listing)
    shipping_num = _to_float(shipping)
    if listing_num is None:
        return "", ""
    if shipping_num is None:
        return str(listing_num), cur
    if shipping_cur and shipping_cur != cur:
        return str(listing_num), cur
    return str(listing_num + shipping_num), cur


def _extract_market_context_from_item_offers(payload: dict) -> Dict[str, str]:
    out: Dict[str, str] = {
        "price": "",
        "currency": "",
        "buy_box_channel": "",
        "lowest_fba_price": "",
        "lowest_fbm_price": "",
        "offer_count_fba": "",
        "offer_count_fbm": "",
        "list_price": "",
        "list_price_currency": "",
        "apparent_sale_amount_gbp": "",
        "apparent_sale_pct": "",
    }
    body = payload.get("payload") or {}
    offers = body.get("Offers") or body.get("offers") or []
    summary = body.get("Summary") or body.get("summary") or {}

    # Buy box price
    for bb in (summary.get("BuyBoxPrices") or summary.get("buyBoxPrices") or []):
        price, cur = _landed_price_from_obj(bb)
        if price and cur:
            out["price"] = price
            out["currency"] = cur
            break
    list_obj = summary.get("ListPrice") or {}
    if isinstance(list_obj, dict):
        list_amt = list_obj.get("Amount")
        list_cur = str(list_obj.get("CurrencyCode") or "").strip()
        if list_amt is not None and list_cur:
            out["list_price"] = str(list_amt)
            out["list_price_currency"] = list_cur
    if not out["price"]:
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            if offer.get("IsBuyBoxWinner") is True or offer.get("isBuyBoxWinner") is True:
                price, cur = _landed_price_from_obj(offer)
                if price and cur:
                    out["price"] = price
                    out["currency"] = cur
                    break

    # Buy box channel from winner flag first.
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        if offer.get("IsBuyBoxWinner") is True or offer.get("isBuyBoxWinner") is True:
            out["buy_box_channel"] = _channel_from_offer(offer)
            break

    # Lowest prices and channel counts from summary.
    for lp in summary.get("LowestPrices") or []:
        if not isinstance(lp, dict):
            continue
        ch = _channel_from_value(lp.get("fulfillmentChannel") or lp.get("FulfillmentChannel"))
        price, _ = _landed_price_from_obj(lp)
        if ch == "FBA" and price:
            out["lowest_fba_price"] = price
        elif ch == "FBM" and price:
            out["lowest_fbm_price"] = price

    for no in summary.get("NumberOfOffers") or []:
        if not isinstance(no, dict):
            continue
        ch = _channel_from_value(no.get("fulfillmentChannel") or no.get("FulfillmentChannel"))
        count_raw = no.get("OfferCount") if "OfferCount" in no else no.get("offerCount")
        try:
            count = int(count_raw)
        except Exception:
            continue
        if ch == "FBA":
            out["offer_count_fba"] = str(count)
        elif ch == "FBM":
            out["offer_count_fbm"] = str(count)

    # Fallback to offers array if summary is incomplete.
    if not out["lowest_fba_price"] or not out["lowest_fbm_price"]:
        fba_prices: List[float] = []
        fbm_prices: List[float] = []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            price, _ = _landed_price_from_obj(offer)
            price_num = _to_float(price) if price else None
            if price_num is None:
                continue
            if offer.get("IsFulfilledByAmazon") is True:
                fba_prices.append(price_num)
            else:
                fbm_prices.append(price_num)
        if not out["lowest_fba_price"] and fba_prices:
            out["lowest_fba_price"] = str(min(fba_prices))
        if not out["lowest_fbm_price"] and fbm_prices:
            out["lowest_fbm_price"] = str(min(fbm_prices))

    if not out["offer_count_fba"] or not out["offer_count_fbm"]:
        fba_count = 0
        fbm_count = 0
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            if offer.get("IsFulfilledByAmazon") is True:
                fba_count += 1
            else:
                fbm_count += 1
        if not out["offer_count_fba"] and fba_count > 0:
            out["offer_count_fba"] = str(fba_count)
        if not out["offer_count_fbm"] and fbm_count > 0:
            out["offer_count_fbm"] = str(fbm_count)

    # Final fallback for channel: infer from where the buy box price matches.
    if not out["buy_box_channel"] and out["price"]:
        p = _to_float(out["price"])
        pfba = _to_float(out["lowest_fba_price"])
        pfbm = _to_float(out["lowest_fbm_price"])
        if p is not None and pfba is not None and abs(p - pfba) < 1e-9:
            out["buy_box_channel"] = "FBA"
        elif p is not None and pfbm is not None and abs(p - pfbm) < 1e-9:
            out["buy_box_channel"] = "FBM"

    # Keep channel explicit when context exists but exact source is unknown.
    if not out["buy_box_channel"] and (
        out["price"] or out["lowest_fba_price"] or out["lowest_fbm_price"] or out["offer_count_fba"] or out["offer_count_fbm"]
    ):
        out["buy_box_channel"] = "Unknown"

    # Inference only: if ListPrice > Buy Box in GBP, treat gap as apparent sale amount.
    if (
        str(out.get("currency", "")).strip().upper() == "GBP"
        and str(out.get("list_price_currency", "")).strip().upper() == "GBP"
    ):
        buy_num = _to_float(out.get("price", ""))
        list_num = _to_float(out.get("list_price", ""))
        if buy_num is not None and list_num is not None and list_num > buy_num:
            sale_amt = list_num - buy_num
            out["apparent_sale_amount_gbp"] = str(round(sale_amt, 2))
            if list_num > 0:
                out["apparent_sale_pct"] = str(round((sale_amt / list_num) * 100.0, 2))
    return out


def fetch_market_context_for_sku_asin(
    sku_asin_rows: List[Tuple[str, str]],
    marketplace_id: str,
    access_token: str,
    run_id: str = "",
    script_name: str = "",
    sleep_sec: float = 2.1,
    timeout: int = 30,
    include_offer_rows: bool = False,
    snapshot_timestamp_utc: str = "",
    snapshot_asof_date: str = "",
) -> Tuple[Dict[str, Dict[str, str]], List[Dict[str, str]]]:
    """
    Fetch market offer context for SKU/ASIN rows using:
    GET /products/pricing/v0/items/{asin}/offers
    Returns dict: sku -> market context fields.
    """
    out: Dict[str, Dict[str, str]] = {}
    offer_rows: List[Dict[str, str]] = []
    if not sku_asin_rows:
        return out, offer_rows

    # Keep first-seen order and map back from ASIN to one or more SKUs.
    asin_to_skus: Dict[str, List[str]] = {}
    for sku, asin in sku_asin_rows:
        sku_clean = str(sku or "").strip()
        asin_clean = str(asin or "").strip()
        if not sku_clean or not asin_clean:
            continue
        asin_to_skus.setdefault(asin_clean, [])
        if sku_clean not in asin_to_skus[asin_clean]:
            asin_to_skus[asin_clean].append(sku_clean)

    uniq_asins = list(asin_to_skus.keys())
    for i, asin in enumerate(uniq_asins, start=1):
        url = f"{SPAPI_BASE_URL}/products/pricing/v0/items/{asin}/offers"
        headers = {
            "x-amz-access-token": access_token,
            "Accept": "application/json",
        }
        params = {
            "MarketplaceId": marketplace_id,
            "ItemCondition": "New",
        }
        ctx = SpApiCallContext(
            run_id=run_id or os.environ.get("SPAPI_RUN_ID", ""),
            script_name=script_name or os.environ.get("SPAPI_SCRIPT_NAME", "unknown_script"),
            endpoint="products_pricing_get_item_offers",
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
            min_interval_sec=max(_env_float("SPAPI_ITEM_OFFERS_MIN_INTERVAL_SEC", 2.1), 0.0),
            max_retries=2,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Pricing Item Offers API failed for {asin}: {resp.status_code} {resp.text}")
        payload = resp.json() or {}
        ctx_data = _extract_market_context_from_item_offers(payload)
        for sku in asin_to_skus.get(asin, []):
            out[sku] = dict(ctx_data)
        if include_offer_rows:
            asin_offer_rows = _extract_offer_rows_from_item_offers(payload)
            for sku in asin_to_skus.get(asin, []):
                for row in asin_offer_rows:
                    rec = dict(row)
                    rec["timestamp_utc"] = snapshot_timestamp_utc
                    rec["asof_date"] = snapshot_asof_date
                    rec["marketplace"] = "UK"
                    rec["sku"] = sku
                    rec["asin"] = asin
                    rec["source"] = "SPAPI"
                    offer_rows.append(rec)

        if i < len(uniq_asins):
            time.sleep(sleep_sec)

    return out, offer_rows


def run_market_context_lookup(
    sku_asin_rows: List[Tuple[str, str]],
    marketplace_id: str,
    run_id: str = "",
    script_name: str = "",
) -> Dict[str, Dict[str, str]]:
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    sleep_sec = _env_float("SPAPI_ITEM_OFFERS_SLEEP_SEC", _env_float("PRICE_API_SLEEP_SEC", 2.1))
    ctx_map, _ = fetch_market_context_for_sku_asin(
        sku_asin_rows=sku_asin_rows,
        marketplace_id=marketplace_id,
        access_token=token,
        run_id=run_id,
        script_name=script_name,
        sleep_sec=sleep_sec,
    )
    return ctx_map


def run_market_context_lookup_with_offers(
    sku_asin_rows: List[Tuple[str, str]],
    marketplace_id: str,
    snapshot_timestamp_utc: str,
    snapshot_asof_date: str,
    run_id: str = "",
    script_name: str = "",
) -> Tuple[Dict[str, Dict[str, str]], List[Dict[str, str]]]:
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    sleep_sec = _env_float("SPAPI_ITEM_OFFERS_SLEEP_SEC", _env_float("PRICE_API_SLEEP_SEC", 2.1))
    return fetch_market_context_for_sku_asin(
        sku_asin_rows=sku_asin_rows,
        marketplace_id=marketplace_id,
        access_token=token,
        run_id=run_id,
        script_name=script_name,
        sleep_sec=sleep_sec,
        include_offer_rows=True,
        snapshot_timestamp_utc=snapshot_timestamp_utc,
        snapshot_asof_date=snapshot_asof_date,
    )
