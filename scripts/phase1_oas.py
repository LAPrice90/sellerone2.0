from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class OasDecisionResult:
    context_quality_score: str
    admissible_flag: str
    hard_fail_reason_codes: list[str]


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _to_money_string(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _truthy(value: object) -> bool:
    return str(value or "").strip() in {"1", "true", "True", "TRUE", "yes", "YES"}


def _is_not_purchasable(value: object) -> bool:
    text = str(value or "").strip().upper()
    return text in {"0", "FALSE", "NO", "NOT_PURCHASABLE", "INACTIVE"}


def build_market_structure_hash(snapshot_rows: Iterable[Mapping[str, object]]) -> str:
    offer_rows = list(snapshot_rows)
    variant_ids = sorted(
        {
            str(row.get("offer_variant_id", "")).strip()
            for row in offer_rows
            if str(row.get("offer_variant_id", "")).strip() != ""
        }
    )

    fulfilment_distribution: dict[str, int] = {}
    for row in offer_rows:
        channel = str(row.get("fulfilment_channel", "")).strip().upper()
        if channel == "":
            continue
        fulfilment_distribution[channel] = fulfilment_distribution.get(channel, 0) + 1

    structure_payload = {
        "offer_variant_ids": variant_ids,
        "offer_count": len(offer_rows),
        "fulfilment_distribution": {k: fulfilment_distribution[k] for k in sorted(fulfilment_distribution.keys())},
    }
    encoded = json.dumps(structure_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def detect_writer_conflict(
    *,
    submitted_write_in_last_cycle: object,
    previous_verified_our_price_gbp: object,
    current_verified_our_price_gbp: object,
    approved_manual_override_prices_gbp: Sequence[object] | None = None,
) -> tuple[bool, str]:
    if _truthy(submitted_write_in_last_cycle):
        return False, ""

    previous = _to_money_string(_to_decimal(previous_verified_our_price_gbp))
    current = _to_money_string(_to_decimal(current_verified_our_price_gbp))
    if previous == "" or current == "":
        return False, ""
    if previous == current:
        return False, ""

    allowlist = {
        _to_money_string(_to_decimal(value))
        for value in (approved_manual_override_prices_gbp or [])
        if _to_money_string(_to_decimal(value)) != ""
    }
    if current in allowlist:
        return False, "WRITER_CHANGE_ALLOWLISTED_MANUAL_OVERRIDE"
    return True, "WRITER_CONFLICT_EXTERNAL_PRICE_CHANGE"


def evaluate_oas_hard_fails(
    *,
    market_structure_hash_start: object,
    market_structure_hash_end: object,
    featured_outcome: object,
    writer_conflict_flag: object,
    promo_suspected_flag: object,
    pricing_health_suppressed_flag: object,
    our_purchasable_flag: object,
    our_purchasable_reliable_flag: object,
    featured_winner_delivery_unknown_flag: object = "0",
) -> OasDecisionResult:
    reason_codes: list[str] = []

    start_hash = str(market_structure_hash_start or "").strip()
    end_hash = str(market_structure_hash_end or "").strip()
    if start_hash and end_hash and start_hash != end_hash:
        reason_codes.append("OAS_FAIL_MARKET_STRUCTURE_CHANGED")

    outcome = str(featured_outcome or "").strip().upper()
    if outcome in {"", "UNKNOWN"}:
        reason_codes.append("OAS_FAIL_FEATURED_OUTCOME_MISSING")

    if _truthy(writer_conflict_flag):
        reason_codes.append("OAS_FAIL_WRITER_CONFLICT")
    if _truthy(promo_suspected_flag):
        reason_codes.append("OAS_FAIL_PROMO_SUSPECTED")
    if _truthy(pricing_health_suppressed_flag):
        reason_codes.append("OAS_FAIL_PRICING_HEALTH_OR_SUPPRESSED")
    if _truthy(featured_winner_delivery_unknown_flag):
        reason_codes.append("OAS_FAIL_FEATURED_WINNER_DELIVERY_UNKNOWN")

    purchasable_reliable = _truthy(our_purchasable_reliable_flag)
    if purchasable_reliable and _is_not_purchasable(our_purchasable_flag):
        reason_codes.append("OAS_FAIL_OUR_OFFER_NOT_PURCHASABLE")

    admissible = "0" if reason_codes else "1"
    score = "0" if reason_codes else "1"
    return OasDecisionResult(
        context_quality_score=score,
        admissible_flag=admissible,
        hard_fail_reason_codes=reason_codes,
    )
