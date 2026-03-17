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
    buy_box_state: str
    buy_box_state_confidence: str
    buy_box_eligible_offers: str
    pricing_health_active_flag: str
    pricing_health_disqualified_flag: str
    pricing_health_reason_codes: List[str]


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


def _flatten_values(payload: object) -> Iterable[object]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield key
            yield from _flatten_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _flatten_values(item)
    else:
        yield payload


def _find_first_value(payload: object, names: set[str]) -> object | None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).strip().lower() in names:
                return value
            found = _find_first_value(value, names)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first_value(item, names)
            if found is not None:
                return found
    return None


def _to_int_string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return _to_int_string(len(value))
    if isinstance(value, Mapping):
        for key in ("count", "offerCount", "eligibleOfferCount", "quantity"):
            text = _to_int_string(value.get(key))
            if text:
                return text
        return ""
    try:
        return str(int(float(str(value).strip())))
    except Exception:
        return ""


def _extract_buy_box_eligible_offers(payload: Mapping[str, object], offer_rows: Iterable[Dict[str, str]]) -> str:
    names = {
        "buyboxeligibleoffers",
        "buy_box_eligible_offers",
        "featuredoffereligibleoffers",
        "featured_offer_eligible_offers",
    }
    raw_value = _find_first_value(payload, names)
    text = _to_int_string(raw_value)
    if text:
        return text
    winner_rows = [row for row in offer_rows if row.get("is_featured_offer_winner") == "1"]
    if winner_rows:
        return str(len(winner_rows))
    return ""


def _extract_buy_box_prices_present(payload: Mapping[str, object], featured_offer_price_gbp: str) -> bool:
    if featured_offer_price_gbp:
        return True
    names = {
        "buyboxprices",
        "buy_box_prices",
        "featuredofferprices",
        "featured_offer_prices",
    }
    raw_value = _find_first_value(payload, names)
    if raw_value is None:
        return False
    if isinstance(raw_value, list):
        return len(raw_value) > 0
    if isinstance(raw_value, Mapping):
        return len(raw_value) > 0
    return str(raw_value).strip() != ""


def _extract_pricing_health(payload: Mapping[str, object]) -> tuple[str, str, List[str]]:
    reason_codes: List[str] = []
    active = False
    disqualified = False

    for value in _flatten_values(payload):
        text = str(value or "").strip()
        if not text:
            continue
        upper = text.upper()
        if "PRICING_HEALTH" in upper:
            active = True
            reason_codes.append("PRICING_HEALTH_SIGNAL_PRESENT")
        if any(token in upper for token in ("BUYBOXDISQUALIFICATION", "BUY_BOX_DISQUALIFICATION", "DISQUALIFIED", "INELIGIBLE")):
            active = True
            disqualified = True
            reason_codes.append("PRICING_HEALTH_SELF_DISQUALIFIED")

    explicit_active = _find_first_value(
        payload,
        {"pricinghealthactiveflag", "pricing_health_active_flag", "pricinghealthsuppressedflag", "pricing_health_suppressed_flag"},
    )
    if str(explicit_active or "").strip() in {"1", "true", "True", "TRUE", "yes", "YES"}:
        active = True
        reason_codes.append("PRICING_HEALTH_FLAG_ACTIVE")

    explicit_reason = _find_first_value(
        payload,
        {"issuetype", "issue_type", "pricinghealthreason", "pricing_health_reason"},
    )
    explicit_text = str(explicit_reason or "").strip().upper()
    if any(token in explicit_text for token in ("BUYBOXDISQUALIFICATION", "BUY_BOX_DISQUALIFICATION", "DISQUALIFIED")):
        active = True
        disqualified = True
        reason_codes.append("PRICING_HEALTH_REASON_SELF_DISQUALIFIED")

    deduped = []
    for code in reason_codes:
        if code not in deduped:
            deduped.append(code)
    return ("1" if active else "0", "1" if disqualified else "0", deduped)


def _classify_buy_box_state(
    *,
    rows: Iterable[Dict[str, str]],
    featured_offer_winner_seller_id: str,
    featured_offer_price_gbp: str,
    unknown_featured_outcome: bool,
    buy_box_eligible_offers: str,
    pricing_health_disqualified_flag: str,
    our_seller_id: str,
    payload: Mapping[str, object],
) -> tuple[str, str]:
    offer_rows = list(rows)
    eligible_count = _to_int_string(buy_box_eligible_offers)
    buy_box_prices_present = _extract_buy_box_prices_present(payload, featured_offer_price_gbp)
    ours = canonicalize_seller_id(our_seller_id)
    winner_raw = str(featured_offer_winner_seller_id or "").strip()
    winner = canonicalize_seller_id(winner_raw) if winner_raw else ""
    offers_exist = len(offer_rows) > 0

    if pricing_health_disqualified_flag == "1":
        return "DISQUALIFIED_SELF_PRICE", "0.95"

    if not offers_exist:
        return "UNKNOWN", "0.2"

    if eligible_count == "0" or (not buy_box_prices_present and offers_exist):
        return "SUPPRESSED_ASIN", "0.9"

    if winner and ours and winner != ours:
        return "LOST_TO_COMPETITOR", "0.95"

    if featured_offer_price_gbp and not unknown_featured_outcome:
        return "NORMAL", "0.95"

    return "UNKNOWN", "0.3"


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
    eligible_offers = _extract_buy_box_eligible_offers(payload, rows)
    pricing_health_active_flag, pricing_health_disqualified_flag, pricing_health_reason_codes = _extract_pricing_health(payload)
    buy_box_state, buy_box_state_confidence = _classify_buy_box_state(
        rows=rows,
        featured_offer_winner_seller_id=winner_id,
        featured_offer_price_gbp=winner_price,
        unknown_featured_outcome=unknown,
        buy_box_eligible_offers=eligible_offers,
        pricing_health_disqualified_flag=pricing_health_disqualified_flag,
        our_seller_id=our_seller_id,
        payload=payload,
    )

    return SnapshotProcessResult(
        rows=rows,
        featured_offer_winner_seller_id=winner_id,
        featured_offer_price_gbp=winner_price,
        unknown_featured_outcome=unknown,
        buy_box_state=buy_box_state,
        buy_box_state_confidence=buy_box_state_confidence,
        buy_box_eligible_offers=eligible_offers,
        pricing_health_active_flag=pricing_health_active_flag,
        pricing_health_disqualified_flag=pricing_health_disqualified_flag,
        pricing_health_reason_codes=pricing_health_reason_codes,
    )

