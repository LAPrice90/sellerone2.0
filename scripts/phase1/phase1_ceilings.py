from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import List


@dataclass(frozen=True)
class ComplianceCeilingResult:
    compliance_ceiling_landed_gbp: str
    compliance_confidence: str
    reason_codes: List[str]


@dataclass(frozen=True)
class EligibilityCeilingResult:
    eligibility_ceiling_landed_gbp: str
    eligibility_source: str
    eligibility_confidence: str
    reason_codes: List[str]


@dataclass(frozen=True)
class FinalCeilingResult:
    compliance_ceiling_landed_gbp: str
    eligibility_ceiling_landed_gbp: str
    suppression_ceiling_landed_temp: str
    demand_ceiling_landed_gbp: str
    final_ceiling_landed_gbp: str
    binding_ceiling_type: str
    reason_codes: List[str]


@dataclass(frozen=True)
class SuppressionReactivationResult:
    suppression_reactivation_target_landed_gbp: str
    suppression_target_source: str
    suppression_threshold_upper_bound_gbp: str
    suppression_ceiling_landed_temp: str
    suppression_ceiling_source: str
    suppression_ceiling_confidence: str
    suppression_ceiling_expiry_utc: str
    reason_codes: List[str]


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


def _to_money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _to_confidence(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP):.4f}".rstrip("0").rstrip(".")


def _parse_utc(ts: object) -> datetime | None:
    text = str(ts or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _add_days_iso(now_utc: object, days: int) -> str:
    now_dt = _parse_utc(now_utc)
    if now_dt is None:
        return ""
    return (now_dt + timedelta(days=max(int(days), 0))).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_compliance_ceiling(
    *,
    cpt_gbp: object = None,
    external_reference_price_gbp: object = None,
    compliance_anchor_gbp: object,
    policy_buffer_pct: object,
    manual_cap_gbp: object,
) -> ComplianceCeilingResult:
    reason_codes: List[str] = []
    cpt = _to_decimal(cpt_gbp)
    compliance_anchor = _to_decimal(compliance_anchor_gbp)
    manual_cap = _to_decimal(manual_cap_gbp)
    policy_buffer = _to_decimal(policy_buffer_pct)

    if policy_buffer is None or policy_buffer < Decimal("0") or policy_buffer >= Decimal("1"):
        policy_buffer = Decimal("0")
        reason_codes.append("COMPLIANCE_POLICY_BUFFER_DEFAULT_ZERO")

    # Phase 1 policy: CPT is telemetry only and does not clamp compliance ceiling.
    if cpt is not None and cpt > 0:
        reason_codes.append("COMPLIANCE_CPT_TELEMETRY_ONLY")
    else:
        reason_codes.append("COMPLIANCE_CPT_UNAVAILABLE")

    if compliance_anchor is not None and compliance_anchor > 0:
        reason_codes.append("COMPLIANCE_ANCHOR_FALLBACK")
        return ComplianceCeilingResult(
            compliance_ceiling_landed_gbp=_to_money(compliance_anchor),
            compliance_confidence="0.7",
            reason_codes=reason_codes,
        )

    if manual_cap is not None and manual_cap > 0:
        reason_codes.append("COMPLIANCE_MANUAL_CAP_FALLBACK")
        return ComplianceCeilingResult(
            compliance_ceiling_landed_gbp=_to_money(manual_cap),
            compliance_confidence="0.5",
            reason_codes=reason_codes,
        )

    reason_codes.append("COMPLIANCE_UNAVAILABLE")
    return ComplianceCeilingResult(
        compliance_ceiling_landed_gbp="",
        compliance_confidence="0",
        reason_codes=reason_codes,
    )


def _foep_status_reason(foep_status: str) -> str | None:
    status = foep_status.strip().upper()
    if not status:
        return None
    if "ASIN_NOT_ELIGIBLE" in status:
        return "FOEP_INELIGIBLE_ASIN"
    if status in {"OK", "SUCCESS", "ELIGIBLE"}:
        return None
    return "FOEP_ERROR"


def resolve_eligibility_ladder(
    *,
    foep_price_gbp: object,
    foep_status: object,
    foep_last_refresh_utc: object,
    cpt_gbp: object,
    manual_cap_gbp: object,
    last_known_safe_gbp: object,
    now_utc: object,
    foep_stale_hours: int,
    foep_sanity_min_mult: object,
    foep_sanity_max_mult: object,
    market_reference_price_gbp: object = None,
) -> EligibilityCeilingResult:
    reason_codes: List[str] = []

    foep = _to_decimal(foep_price_gbp)
    cpt = _to_decimal(cpt_gbp)
    manual_cap = _to_decimal(manual_cap_gbp)
    last_known_safe = _to_decimal(last_known_safe_gbp)
    market_ref = _to_decimal(market_reference_price_gbp)

    status_reason = _foep_status_reason(str(foep_status or ""))
    if status_reason:
        reason_codes.append(status_reason)

    now_dt = _parse_utc(now_utc)
    foep_refresh_dt = _parse_utc(foep_last_refresh_utc)
    foep_stale = False
    if now_dt is not None and foep_refresh_dt is not None:
        age = now_dt - foep_refresh_dt
        if age > timedelta(hours=int(foep_stale_hours)):
            foep_stale = True
            reason_codes.append("FOEP_STALE")

    foep_sane = True
    min_mult = _to_decimal(foep_sanity_min_mult)
    max_mult = _to_decimal(foep_sanity_max_mult)
    if foep is not None and market_ref is not None and market_ref > 0 and min_mult is not None and max_mult is not None:
        lower = market_ref * min_mult
        upper = market_ref * max_mult
        if foep < lower or foep > upper:
            foep_sane = False
            reason_codes.append("FOEP_SANITY_FAIL")

    foep_usable = foep is not None and foep > 0 and not status_reason and not foep_stale and foep_sane
    if foep_usable:
        reason_codes.append("ELIG_CEILING_FOEP_USED")
        return EligibilityCeilingResult(
            eligibility_ceiling_landed_gbp=_to_money(foep),
            eligibility_source="FOEP",
            eligibility_confidence="0.95",
            reason_codes=reason_codes,
        )

    if foep is None:
        reason_codes.append("FOEP_MISSING")

    if cpt is not None and cpt > 0:
        reason_codes.append("CPT_TELEMETRY_ONLY")

    if manual_cap is not None and manual_cap > 0:
        reason_codes.append("ELIG_CEILING_MANUAL_USED")
        return EligibilityCeilingResult(
            eligibility_ceiling_landed_gbp=_to_money(manual_cap),
            eligibility_source="MANUAL",
            eligibility_confidence="0.5",
            reason_codes=reason_codes,
        )

    if last_known_safe is not None and last_known_safe > 0:
        reason_codes.append("ELIG_CEILING_LAST_KNOWN_SAFE_USED")
        return EligibilityCeilingResult(
            eligibility_ceiling_landed_gbp=_to_money(last_known_safe),
            eligibility_source="LAST_KNOWN_SAFE",
            eligibility_confidence="0.4",
            reason_codes=reason_codes,
        )

    reason_codes.append("ELIGIBILITY_UNAVAILABLE")
    return EligibilityCeilingResult(
        eligibility_ceiling_landed_gbp="",
        eligibility_source="LAST_KNOWN_SAFE",
        eligibility_confidence="0",
        reason_codes=reason_codes,
    )


def resolve_suppression_reactivation_target(
    *,
    buy_box_state: object,
    now_utc: object,
    competitive_price_threshold_gbp: object = None,
    competitive_price_gbp: object = None,
    average_selling_price_gbp: object = None,
    foep_price_gbp: object = None,
    probe_threshold_estimate_gbp: object = None,
    existing_final_ceiling_landed_gbp: object = None,
    anchor_floor_price_gbp: object = None,
    hard_floor_gbp: object = None,
    probe_ceiling_candidate_gbp: object = None,
    best_competitor_price_gbp: object = None,
    no_buy_box_offer_present: object = False,
    current_suppression_ceiling_landed_temp: object = None,
    current_suppression_ceiling_expiry_utc: object = None,
    expiry_days: int = 3,
) -> SuppressionReactivationResult:
    reason_codes: List[str] = []
    state = str(buy_box_state or "").strip().upper()
    if state not in {"SUPPRESSED_ASIN", "DISQUALIFIED_SELF_PRICE"}:
        reason_codes.append("SUPPRESSION_NOT_ACTIVE")
        return SuppressionReactivationResult(
            suppression_reactivation_target_landed_gbp="",
            suppression_target_source="",
            suppression_threshold_upper_bound_gbp="",
            suppression_ceiling_landed_temp="",
            suppression_ceiling_source="",
            suppression_ceiling_confidence="0",
            suppression_ceiling_expiry_utc="",
            reason_codes=reason_codes,
        )

    candidates = [
        ("CPT", _to_decimal(competitive_price_threshold_gbp), Decimal("0.95")),
        ("COMPETITIVE_PRICE", _to_decimal(competitive_price_gbp), Decimal("0.9")),
        ("AVERAGE_SELLING_PRICE", _to_decimal(average_selling_price_gbp), Decimal("0.8")),
        ("FOEP", _to_decimal(foep_price_gbp), Decimal("0.7")),
        ("PROBE_BRACKET", _to_decimal(probe_threshold_estimate_gbp), Decimal("0.5")),
    ]
    chosen_source = ""
    chosen_value: Decimal | None = None
    chosen_confidence = Decimal("0")
    probe_ceiling_candidate = _to_decimal(probe_ceiling_candidate_gbp)
    inferred_upper_bound: Decimal | None = None
    for source, value, confidence in candidates:
        if value is not None and value > 0:
            chosen_source = source
            chosen_value = value
            chosen_confidence = confidence
            reason_codes.append(f"SUPPRESSION_TARGET_{source}_USED")
            break

    if chosen_value is None:
        best_competitor = _to_decimal(best_competitor_price_gbp)
        no_buy_box_present = str(no_buy_box_offer_present or "").strip().lower() in {"1", "true", "yes", "y", "on"}
        if state == "SUPPRESSED_ASIN" and no_buy_box_present and best_competitor is not None and best_competitor > 0:
            inferred_upper_bound = best_competitor
            suppression_ceiling = inferred_upper_bound
            existing_final = _to_decimal(existing_final_ceiling_landed_gbp)
            if existing_final is not None and existing_final > 0 and suppression_ceiling > existing_final:
                suppression_ceiling = existing_final
                reason_codes.append("SUPPRESSION_CEILING_CLAMPED_TO_EXISTING_FINAL")
            expiry_utc = _add_days_iso(now_utc, expiry_days)
            reason_codes.append("SUPPRESSION_THRESHOLD_UPPER_BOUND_INFERRED_LOWEST_COMPETITOR")
            return SuppressionReactivationResult(
                suppression_reactivation_target_landed_gbp="",
                suppression_target_source="",
                suppression_threshold_upper_bound_gbp=_to_money(inferred_upper_bound),
                suppression_ceiling_landed_temp=_to_money(suppression_ceiling),
                suppression_ceiling_source="LOWEST_COMPETITOR_INFERENCE",
                suppression_ceiling_confidence="0.3",
                suppression_ceiling_expiry_utc=expiry_utc,
                reason_codes=reason_codes,
            )
        if probe_ceiling_candidate is not None and probe_ceiling_candidate > 0:
            existing_final = _to_decimal(existing_final_ceiling_landed_gbp)
            probe_ceiling = probe_ceiling_candidate
            if existing_final is not None and existing_final > 0 and probe_ceiling > existing_final:
                probe_ceiling = existing_final
                reason_codes.append("SUPPRESSION_CEILING_CLAMPED_TO_EXISTING_FINAL")
            expiry_utc = _add_days_iso(now_utc, expiry_days)
            reason_codes.append("SUPPRESSION_PROBE_CEILING_USED")
            return SuppressionReactivationResult(
                suppression_reactivation_target_landed_gbp="",
                suppression_target_source="",
                suppression_threshold_upper_bound_gbp="",
                suppression_ceiling_landed_temp=_to_money(probe_ceiling),
                suppression_ceiling_source="PROBE_BRACKET",
                suppression_ceiling_confidence="0.2",
                suppression_ceiling_expiry_utc=expiry_utc,
                reason_codes=reason_codes,
            )
        current_ceiling = _to_decimal(current_suppression_ceiling_landed_temp)
        expiry_dt = _parse_utc(current_suppression_ceiling_expiry_utc)
        now_dt = _parse_utc(now_utc)
        if current_ceiling is not None and current_ceiling > 0 and expiry_dt is not None and now_dt is not None and expiry_dt >= now_dt:
            reason_codes.append("SUPPRESSION_TARGET_CARRY_FORWARD_USED")
            return SuppressionReactivationResult(
                suppression_reactivation_target_landed_gbp=_to_money(current_ceiling),
                suppression_target_source="CARRY_FORWARD",
                suppression_threshold_upper_bound_gbp="",
                suppression_ceiling_landed_temp=_to_money(current_ceiling),
                suppression_ceiling_source="CARRY_FORWARD",
                suppression_ceiling_confidence="0.4",
                suppression_ceiling_expiry_utc=expiry_dt.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
                reason_codes=reason_codes,
            )
        reason_codes.append("SUPPRESSION_TARGET_UNAVAILABLE")
        return SuppressionReactivationResult(
            suppression_reactivation_target_landed_gbp="",
            suppression_target_source="",
            suppression_threshold_upper_bound_gbp="",
            suppression_ceiling_landed_temp="",
            suppression_ceiling_source="",
            suppression_ceiling_confidence="0",
            suppression_ceiling_expiry_utc="",
            reason_codes=reason_codes,
        )

    floor_candidates = [d for d in (_to_decimal(anchor_floor_price_gbp), _to_decimal(hard_floor_gbp)) if d is not None and d > 0]
    if floor_candidates:
        floor_guard = max(floor_candidates)
        if chosen_value < floor_guard:
            chosen_value = floor_guard
            reason_codes.append("SUPPRESSION_TARGET_CLAMPED_TO_ANCHOR_OR_HARD_FLOOR")

    existing_final = _to_decimal(existing_final_ceiling_landed_gbp)
    suppression_ceiling = chosen_value
    if existing_final is not None and existing_final > 0 and suppression_ceiling > existing_final:
        suppression_ceiling = existing_final
        reason_codes.append("SUPPRESSION_CEILING_CLAMPED_TO_EXISTING_FINAL")

    expiry_utc = _add_days_iso(now_utc, expiry_days)
    return SuppressionReactivationResult(
        suppression_reactivation_target_landed_gbp=_to_money(chosen_value),
        suppression_target_source=chosen_source,
        suppression_threshold_upper_bound_gbp="",
        suppression_ceiling_landed_temp=_to_money(suppression_ceiling),
        suppression_ceiling_source=chosen_source,
        suppression_ceiling_confidence=_to_confidence(chosen_confidence),
        suppression_ceiling_expiry_utc=expiry_utc,
        reason_codes=reason_codes,
    )


def compute_final_ceiling(
    *,
    compliance_ceiling_landed_gbp: object,
    eligibility_ceiling_landed_gbp: object,
    manual_cap_gbp: object,
    suppression_ceiling_landed_temp: object = None,
) -> FinalCeilingResult:
    reason_codes: List[str] = []

    compliance = _to_decimal(compliance_ceiling_landed_gbp)
    eligibility = _to_decimal(eligibility_ceiling_landed_gbp)
    manual_cap = _to_decimal(manual_cap_gbp)
    suppression_temp = _to_decimal(suppression_ceiling_landed_temp)

    candidates: List[tuple[str, Decimal]] = []
    if compliance is not None and compliance > 0:
        candidates.append(("COMPLIANCE", compliance))
    if eligibility is not None and eligibility > 0:
        candidates.append(("ELIGIBILITY", eligibility))
    if suppression_temp is not None and suppression_temp > 0:
        candidates.append(("SUPPRESSION_TEMP", suppression_temp))
    if manual_cap is not None and manual_cap > 0:
        candidates.append(("MANUAL_CAP", manual_cap))

    if not candidates:
        reason_codes.append("FINAL_CEILING_UNAVAILABLE")
        return FinalCeilingResult(
            compliance_ceiling_landed_gbp=_to_money(compliance),
            eligibility_ceiling_landed_gbp=_to_money(eligibility),
            suppression_ceiling_landed_temp=_to_money(suppression_temp),
            demand_ceiling_landed_gbp=_to_money(manual_cap),
            final_ceiling_landed_gbp="",
            binding_ceiling_type="NONE",
            reason_codes=reason_codes,
        )

    ordered = ["COMPLIANCE", "MANUAL_CAP", "SUPPRESSION_TEMP", "ELIGIBILITY"]
    final_type, final_value = min(
        candidates,
        key=lambda item: (item[1], ordered.index(item[0])),
    )
    reason_codes.append(f"BINDING_CEILING_{final_type}")

    return FinalCeilingResult(
        compliance_ceiling_landed_gbp=_to_money(compliance),
        eligibility_ceiling_landed_gbp=_to_money(eligibility),
        suppression_ceiling_landed_temp=_to_money(suppression_temp),
        demand_ceiling_landed_gbp=_to_money(manual_cap),
        final_ceiling_landed_gbp=_to_money(final_value),
        binding_ceiling_type=final_type,
        reason_codes=reason_codes,
    )

