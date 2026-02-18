from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class SnapshotProcessResult:
    rows: List[Dict[str, str]]
    featured_offer_winner_seller_id: str
    featured_offer_price_gbp: str
    unknown_featured_outcome: bool


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonicalize_seller_id(raw: object) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return "unknown_seller"
    return "".join(ch for ch in text if ch.isalnum() or ch in {"_", "."}) or "unknown_seller"


def normalize_fulfilment_channel(raw_offer: Mapping[str, object]) -> str:
    if raw_offer.get("IsFulfilledByAmazon") is True:
        return "FBA"
    if raw_offer.get("IsFulfilledByAmazon") is False:
        return "FBM"
    value = str(
        raw_offer.get("fulfilment_channel")
        or raw_offer.get("fulfillmentChannel")
        or raw_offer.get("FulfillmentChannel")
        or ""
    ).strip().upper()
    if any(tag in value for tag in ("AMAZON", "AFN", "FBA")):
        return "FBA"
    if any(tag in value for tag in ("MERCHANT", "MFN", "FBM")):
        return "FBM"
    return ""


def _to_price_string(value: object) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.2f}"
    except Exception:
        return ""


def _to_days(value: object) -> str:
    if value is None:
        return ""
    try:
        return str(int(float(value)))
    except Exception:
        return ""


def _price_from_container(container: Mapping[str, object] | None) -> str:
    if not isinstance(container, Mapping):
        return ""
    direct = _to_price_string(container.get("Amount"))
    if direct:
        return direct
    direct = _to_price_string(container.get("amount"))
    if direct:
        return direct
    return _to_price_string(container.get("value"))


def _extract_listing_price_gbp(offer: Mapping[str, object]) -> str:
    listing = offer.get("ListingPrice")
    if isinstance(listing, Mapping):
        return _price_from_container(listing)
    return _to_price_string(offer.get("listing_price_gbp") or offer.get("listingPrice"))


def _extract_shipping_gbp(offer: Mapping[str, object]) -> str:
    shipping = offer.get("Shipping")
    if isinstance(shipping, Mapping):
        return _price_from_container(shipping)
    return _to_price_string(offer.get("shipping_gbp") or offer.get("shippingPrice"))


def _extract_landed_gbp(offer: Mapping[str, object], listing_price_gbp: str, shipping_gbp: str) -> str:
    landed = offer.get("LandedPrice")
    if isinstance(landed, Mapping):
        landed_value = _price_from_container(landed)
        if landed_value:
            return landed_value
    explicit = _to_price_string(offer.get("landed_price_gbp") or offer.get("landedPrice"))
    if explicit:
        return explicit
    try:
        listing = float(listing_price_gbp) if listing_price_gbp else 0.0
        shipping = float(shipping_gbp) if shipping_gbp else 0.0
        return f"{listing + shipping:.2f}"
    except Exception:
        return ""


def _extract_delivery_days(offer: Mapping[str, object]) -> tuple[str, str]:
    shipping_time = offer.get("ShippingTime")
    if isinstance(shipping_time, Mapping):
        min_days = _to_days(shipping_time.get("minimumDays") or shipping_time.get("MinimumDays"))
        max_days = _to_days(shipping_time.get("maximumDays") or shipping_time.get("MaximumDays"))
        if min_days or max_days:
            return min_days, max_days
    return (
        _to_days(offer.get("min_delivery_days") or offer.get("minimumDeliveryDays")),
        _to_days(offer.get("max_delivery_days") or offer.get("maximumDeliveryDays")),
    )


def _extract_bool_flag(value: object) -> str:
    if value is True:
        return "1"
    if value is False:
        return "0"
    return ""


def _extract_offers(payload: Mapping[str, object]) -> List[Mapping[str, object]]:
    offers: List[Mapping[str, object]] = []

    def _collect_from_node(node: object) -> None:
        if isinstance(node, Mapping):
            raw_offers = node.get("offers") or node.get("Offers")
            if isinstance(raw_offers, list):
                for offer in raw_offers:
                    if isinstance(offer, Mapping):
                        offers.append(offer)
            for value in node.values():
                _collect_from_node(value)
        elif isinstance(node, list):
            for item in node:
                _collect_from_node(item)

    _collect_from_node(payload)
    return offers


def _extract_featured_outcome(payload: Mapping[str, object], offer_rows: Iterable[Dict[str, str]]) -> tuple[str, str, bool]:
    winner_id = ""
    winner_price = ""
    unknown = False

    for key in ("featured_offer_winner_seller_id", "featuredOfferWinnerSellerId"):
        val = str(payload.get(key, "")).strip()
        if val:
            winner_id = canonicalize_seller_id(val)
            break
    for key in ("featured_offer_price_gbp", "featuredOfferPrice"):
        val = _to_price_string(payload.get(key))
        if val:
            winner_price = val
            break

    if not winner_id:
        for row in offer_rows:
            if row.get("is_featured_offer_winner") == "1":
                winner_id = row.get("seller_id_canonical", "")
                winner_price = row.get("landed_price_gbp", "")
                break

    if not winner_id and not winner_price:
        unknown = True
    return winner_id, winner_price, unknown


def compute_offer_variant_id(
    marketplace_id: str,
    sku: str,
    seller_id_canonical: str,
    fulfilment_channel: str,
    condition: str,
    shipping_template: str,
) -> str:
    key = "|".join(
        [
            str(marketplace_id or "").strip().upper(),
            str(sku or "").strip().upper(),
            str(seller_id_canonical or "").strip().lower(),
            str(fulfilment_channel or "").strip().upper(),
            str(condition or "").strip().upper(),
            str(shipping_template or "").strip().upper(),
        ]
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"ov_{digest[:20]}"


def process_competitive_summary(
    *,
    payload: Mapping[str, object],
    sku: str,
    asin: str,
    marketplace_id: str,
    our_seller_id: str,
    snapshot_ts_utc: str | None = None,
) -> SnapshotProcessResult:
    snapshot_ts = snapshot_ts_utc or _utc_now_iso()
    our_seller_canonical = canonicalize_seller_id(our_seller_id)
    offers = _extract_offers(payload)
    rows: List[Dict[str, str]] = []

    for offer in offers:
        seller_id_raw = str(
            offer.get("sellerId")
            or offer.get("SellerId")
            or offer.get("seller_id_raw")
            or ""
        ).strip()
        seller_id_canonical = canonicalize_seller_id(seller_id_raw)
        fulfilment_channel = normalize_fulfilment_channel(offer)
        condition = str(offer.get("condition") or offer.get("Condition") or "").strip()
        shipping_template = str(offer.get("shippingTemplate") or offer.get("shipping_template") or "UNKNOWN").strip()
        listing_price_gbp = _extract_listing_price_gbp(offer)
        shipping_gbp = _extract_shipping_gbp(offer)
        landed_price_gbp = _extract_landed_gbp(offer, listing_price_gbp, shipping_gbp)
        min_delivery_days, max_delivery_days = _extract_delivery_days(offer)
        is_prime = _extract_bool_flag(offer.get("isPrime") if "isPrime" in offer else offer.get("IsPrime"))
        is_featured_offer_winner = _extract_bool_flag(
            offer.get("isFeaturedOfferWinner")
            if "isFeaturedOfferWinner" in offer
            else offer.get("IsFeaturedOfferWinner")
        )
        is_our_offer = "1" if seller_id_canonical == our_seller_canonical else "0"
        offer_variant_id = compute_offer_variant_id(
            marketplace_id=marketplace_id,
            sku=sku,
            seller_id_canonical=seller_id_canonical,
            fulfilment_channel=fulfilment_channel,
            condition=condition,
            shipping_template=shipping_template,
        )

        row = {
            "offer_snapshot_id": str(uuid.uuid4()),
            "snapshot_ts_utc": snapshot_ts,
            "sku": str(sku),
            "asin": str(asin),
            "marketplace_id": str(marketplace_id),
            "seller_id_raw": seller_id_raw,
            "seller_id_canonical": seller_id_canonical,
            "offer_variant_id": offer_variant_id,
            "fulfilment_channel": fulfilment_channel,
            "condition": condition,
            "listing_price_gbp": listing_price_gbp,
            "shipping_gbp": shipping_gbp,
            "landed_price_gbp": landed_price_gbp,
            "min_delivery_days": min_delivery_days,
            "max_delivery_days": max_delivery_days,
            "is_prime": is_prime,
            "is_featured_offer_winner": is_featured_offer_winner,
            "is_our_offer": is_our_offer,
            "promo_suspected_flag": "0",
            "unknown_outcome_flag": "0",
        }
        rows.append(row)

    winner_id, winner_price, unknown = _extract_featured_outcome(payload, rows)
    if unknown:
        for row in rows:
            row["unknown_outcome_flag"] = "1"

    return SnapshotProcessResult(
        rows=rows,
        featured_offer_winner_seller_id=winner_id,
        featured_offer_price_gbp=winner_price,
        unknown_featured_outcome=unknown,
    )
