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
    demand_ceiling_landed_gbp: str
    final_ceiling_landed_gbp: str
    binding_ceiling_type: str
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


def compute_final_ceiling(
    *,
    compliance_ceiling_landed_gbp: object,
    eligibility_ceiling_landed_gbp: object,
    manual_cap_gbp: object,
) -> FinalCeilingResult:
    reason_codes: List[str] = []

    compliance = _to_decimal(compliance_ceiling_landed_gbp)
    eligibility = _to_decimal(eligibility_ceiling_landed_gbp)
    manual_cap = _to_decimal(manual_cap_gbp)

    candidates: List[tuple[str, Decimal]] = []
    if compliance is not None and compliance > 0:
        candidates.append(("COMPLIANCE", compliance))
    if eligibility is not None and eligibility > 0:
        candidates.append(("ELIGIBILITY", eligibility))
    if manual_cap is not None and manual_cap > 0:
        candidates.append(("MANUAL_CAP", manual_cap))

    if not candidates:
        reason_codes.append("FINAL_CEILING_UNAVAILABLE")
        return FinalCeilingResult(
            compliance_ceiling_landed_gbp=_to_money(compliance),
            eligibility_ceiling_landed_gbp=_to_money(eligibility),
            demand_ceiling_landed_gbp=_to_money(manual_cap),
            final_ceiling_landed_gbp="",
            binding_ceiling_type="NONE",
            reason_codes=reason_codes,
        )

    ordered = ["COMPLIANCE", "MANUAL_CAP", "ELIGIBILITY"]
    final_type, final_value = min(
        candidates,
        key=lambda item: (item[1], ordered.index(item[0])),
    )
    reason_codes.append(f"BINDING_CEILING_{final_type}")

    return FinalCeilingResult(
        compliance_ceiling_landed_gbp=_to_money(compliance),
        eligibility_ceiling_landed_gbp=_to_money(eligibility),
        demand_ceiling_landed_gbp=_to_money(manual_cap),
        final_ceiling_landed_gbp=_to_money(final_value),
        binding_ceiling_type=final_type,
        reason_codes=reason_codes,
    )
