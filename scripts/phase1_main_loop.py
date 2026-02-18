from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable, Mapping

BOOT_ROOT = Path(__file__).resolve().parent.parent
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

try:
    from scripts import phase1_ceilings, phase1_dve, phase1_market_snapshot_processor, phase1_oas, phase1_probe_engine, phase1_storage, phase1_write_verify
except ModuleNotFoundError:
    import phase1_ceilings
    import phase1_dve
    import phase1_market_snapshot_processor
    import phase1_oas
    import phase1_probe_engine
    import phase1_storage
    import phase1_write_verify


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _is_truthy(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _our_price_from_rows(rows: Iterable[Mapping[str, object]]) -> str:
    for row in rows:
        if str(row.get("is_our_offer", "")).strip() != "1":
            continue
        landed = _to_decimal(row.get("landed_price_gbp"))
        if landed is not None:
            return _money(landed)
        listing = _to_decimal(row.get("listing_price_gbp"))
        if listing is not None:
            return _money(listing)
    return ""


def _build_offer_variants_rows(snapshot_rows: Iterable[Mapping[str, object]], event_ts_utc: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in snapshot_rows:
        rows.append(
            {
                "offer_variant_id": str(row.get("offer_variant_id", "")),
                "sku": str(row.get("sku", "")),
                "seller_id_canonical": str(row.get("seller_id_canonical", "")),
                "fulfilment_channel": str(row.get("fulfilment_channel", "")),
                "condition": str(row.get("condition", "")),
                "shipping_template": "UNKNOWN",
                "variant_first_seen_utc": event_ts_utc,
                "variant_last_seen_utc": event_ts_utc,
                "variant_active_flag": "1",
            }
        )
    return rows


def _pick_latest_open_probe(sku: str) -> dict[str, str] | None:
    probe_rows = phase1_storage.read_where("probe_windows", {"sku": sku})
    if not probe_rows:
        return None
    for row in reversed(probe_rows):
        if str(row.get("oas_result", "")).strip().upper() == "PENDING":
            return row
    return None


def _delivery_days_known(row: Mapping[str, object]) -> bool:
    min_days = _to_decimal(row.get("min_delivery_days"))
    max_days = _to_decimal(row.get("max_delivery_days"))
    if min_days is not None and min_days >= 0:
        return True
    if max_days is not None and max_days >= 0:
        return True
    return False


def _featured_winner_delivery_unknown(
    *,
    snapshot_rows: Iterable[Mapping[str, object]],
    featured_offer_winner_seller_id: object,
) -> bool:
    rows = [dict(r) for r in snapshot_rows]
    winner_rows = [r for r in rows if str(r.get("is_featured_offer_winner", "")).strip() == "1"]

    if not winner_rows:
        winner_id = str(featured_offer_winner_seller_id or "").strip().lower()
        if winner_id:
            winner_rows = [r for r in rows if str(r.get("seller_id_canonical", "")).strip().lower() == winner_id]

    if not winner_rows:
        return True

    for row in winner_rows:
        if _delivery_days_known(row):
            return False
    return True


def _disable_dve_rows(snapshot_rows: Iterable[Mapping[str, object]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in snapshot_rows:
        out_row = {str(k): str(v) if v is not None else "" for k, v in row.items()}
        landed = _to_decimal(row.get("landed_price_gbp"))
        out_row["delivery_gap_days"] = ""
        out_row["delivery_penalty_gbp"] = ""
        out_row["effective_price_gbp"] = _money(landed)
        out.append(out_row)
    return out


def _best_rival_effective_and_variant_id(rows: Iterable[Mapping[str, object]]) -> tuple[Decimal | None, str]:
    best_price: Decimal | None = None
    best_variant_id = ""
    for row in rows:
        if str(row.get("is_our_offer", "")).strip() == "1":
            continue
        effective = _to_decimal(row.get("effective_price_gbp"))
        if effective is None:
            effective = _to_decimal(row.get("landed_price_gbp"))
        if effective is None:
            continue
        if best_price is None or effective < best_price:
            best_price = effective
            best_variant_id = str(row.get("offer_variant_id", "") or "")
    return best_price, best_variant_id


@dataclass(frozen=True)
class AcycleResult:
    date_utc: str
    sku: str
    eligibility_source: str
    compliance_ceiling_landed_gbp: str
    eligibility_ceiling_landed_gbp: str
    cpt_status: str
    reason_codes: list[str]


@dataclass(frozen=True)
class HcycleResult:
    sku: str
    state: str
    write_status: str
    final_ceiling_landed_gbp: str
    probe_id: str
    reason_codes: list[str]
    oas_admissible_flag: str
    blocked_due_to_missing_intel: str = "0"
    blocked_due_to_stale_intel: str = "0"
    refresh_attempted_count: str = "0"
    refresh_throttled_count: str = "0"


ALLOWED_WRITER_MODES = {"PPP", "CODEX_H", "READ_ONLY"}


def _canonical_writer_mode(value: object) -> str:
    return str(value or "").strip().upper()


def _daily_intel_gate_status(*, daily_intel: Mapping[str, object], today_utc_date: str) -> str:
    date_utc = str(daily_intel.get("date_utc", "") or "").strip()
    compliance_ceiling = str(daily_intel.get("compliance_ceiling_landed_gbp", "") or "").strip()
    eligibility_ceiling = str(daily_intel.get("eligibility_ceiling_landed_gbp", "") or "").strip()
    parked_flag = _is_truthy(daily_intel.get("parked_flag", "0"))
    if not date_utc:
        return "MISSING"
    if date_utc != today_utc_date:
        return "STALE"
    if parked_flag:
        return "FRESH"
    if compliance_ceiling == "" or eligibility_ceiling == "":
        return "MISSING"
    return "FRESH"


def _refresh_already_attempted_today(*, sku: str, today_utc_date: str) -> bool:
    rows = phase1_storage.read_where("daily_intel_refresh_attempts", {"sku": sku})
    for row in rows:
        if str(row.get("date_utc", "")).strip() == today_utc_date:
            return True
    return False


def _record_refresh_attempt(*, event_ts_utc: str, sku: str, today_utc_date: str, status: str) -> None:
    phase1_storage.append(
        "daily_intel_refresh_attempts",
        [
            {
                "event_ts_utc": event_ts_utc,
                "date_utc": today_utc_date,
                "sku": sku,
                "status": status,
            }
        ],
    )


def run_a_cycle(
    *,
    sku: str,
    now_utc: str,
    compliance_anchor_gbp: object,
    policy_buffer_pct: object,
    manual_cap_gbp: object,
    foep_price_gbp: object,
    foep_status: object,
    foep_last_refresh_utc: object,
    cpt_gbp: object,
    cpt_last_refresh_utc: object,
    cpt_status: object = "",
    last_known_safe_gbp: object,
    foep_stale_hours: int,
    foep_sanity_min_mult: object,
    foep_sanity_max_mult: object,
    market_reference_price_gbp: object = None,
    extra_reason_codes: list[str] | None = None,
    cpt_risk_band: object = "",
    cpt_delta_vs_buy_box_gbp: object = "",
    cpt_delta_vs_buy_box_pct: object = "",
    cpt_call_tier: object = "",
    cpt_call_reason_codes: list[str] | None = None,
    parked_flag: object = "0",
    park_reason_codes: list[str] | None = None,
) -> AcycleResult:
    compliance = phase1_ceilings.compute_compliance_ceiling(
        cpt_gbp=cpt_gbp,
        external_reference_price_gbp=market_reference_price_gbp,
        compliance_anchor_gbp=compliance_anchor_gbp,
        policy_buffer_pct=policy_buffer_pct,
        manual_cap_gbp=manual_cap_gbp,
    )
    eligibility = phase1_ceilings.resolve_eligibility_ladder(
        foep_price_gbp=foep_price_gbp,
        foep_status=foep_status,
        foep_last_refresh_utc=foep_last_refresh_utc,
        cpt_gbp=cpt_gbp,
        manual_cap_gbp=manual_cap_gbp,
        last_known_safe_gbp=last_known_safe_gbp,
        now_utc=now_utc,
        foep_stale_hours=int(foep_stale_hours),
        foep_sanity_min_mult=foep_sanity_min_mult,
        foep_sanity_max_mult=foep_sanity_max_mult,
        market_reference_price_gbp=market_reference_price_gbp,
    )

    if not str(eligibility.eligibility_source or "").strip():
        raise RuntimeError("A-cycle invariant failed: eligibility_source is empty")

    extra_reason_codes = [str(x).strip() for x in (extra_reason_codes or []) if str(x).strip()]
    cpt_call_reason_codes = [str(x).strip() for x in (cpt_call_reason_codes or []) if str(x).strip()]
    park_reason_codes = [str(x).strip() for x in (park_reason_codes or []) if str(x).strip()]
    cpt_status_text = str(cpt_status or "").strip().upper()
    if cpt_status_text == "":
        cpt_status_text = "OK" if str(cpt_gbp or "").strip() else "MISSING"
    cpt_risk_band_text = str(cpt_risk_band or "").strip().upper()
    if cpt_risk_band_text not in {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}:
        cpt_risk_band_text = "LOW" if str(cpt_gbp or "").strip() and cpt_status_text == "OK" else "UNKNOWN"
    parked_text = "1" if _is_truthy(parked_flag) else "0"

    row = {
        "date_utc": str(now_utc)[:10],
        "sku": sku,
        "foep_price_gbp": str(foep_price_gbp or ""),
        "foep_status": str(foep_status or ""),
        "foep_last_refresh_utc": str(foep_last_refresh_utc or ""),
        "cpt_gbp": str(cpt_gbp or ""),
        "cpt_last_refresh_utc": str(cpt_last_refresh_utc or ""),
        "cpt_status": cpt_status_text,
        "cpt_risk_band": cpt_risk_band_text,
        "cpt_delta_vs_buy_box_gbp": str(cpt_delta_vs_buy_box_gbp or ""),
        "cpt_delta_vs_buy_box_pct": str(cpt_delta_vs_buy_box_pct or ""),
        "cpt_call_tier": str(cpt_call_tier or ""),
        "cpt_call_reason_codes_json": _json_compact(cpt_call_reason_codes),
        "parked_flag": parked_text,
        "park_reason_codes_json": _json_compact(park_reason_codes),
        "eligibility_ceiling_landed_gbp": eligibility.eligibility_ceiling_landed_gbp,
        "eligibility_source": eligibility.eligibility_source,
        "eligibility_confidence": eligibility.eligibility_confidence,
        "eligibility_reason_codes_json": _json_compact(eligibility.reason_codes + extra_reason_codes),
        "compliance_ceiling_landed_gbp": compliance.compliance_ceiling_landed_gbp,
        "compliance_confidence": compliance.compliance_confidence,
    }
    phase1_storage.write_table("sku_daily_intel", [row])

    return AcycleResult(
        date_utc=row["date_utc"],
        sku=sku,
        eligibility_source=eligibility.eligibility_source,
        compliance_ceiling_landed_gbp=compliance.compliance_ceiling_landed_gbp,
        eligibility_ceiling_landed_gbp=eligibility.eligibility_ceiling_landed_gbp,
        cpt_status=cpt_status_text,
        reason_codes=compliance.reason_codes + eligibility.reason_codes + extra_reason_codes,
    )


def run_h_cycle(
    *,
    sku: str,
    asin: str,
    marketplace_id: str,
    our_seller_id: str,
    pricing_writer_mode: str,
    enabled_live_writes: bool,
    current_price_gbp: object,
    hard_floor_gbp: object,
    manual_cap_gbp: object,
    max_step_down_gbp: object,
    max_step_up_gbp: object,
    max_daily_drop_gbp: object,
    daily_drop_used_gbp: object,
    delta_tolerance_gbp: object,
    stable_buffer_gbp: object,
    min_clean_tests_for_confidence: int,
    price_apply_tolerance_gbp: object,
    policy_buffer_pct: object,
    market_payload: Mapping[str, object],
    listings_observed_price_gbp: object = "",
    write_submitter: Callable[[str], Mapping[str, object]] | None = None,
    probe_observation_payload: Mapping[str, object] | None = None,
    writer_conflict_manual_allowlist_gbp: list[object] | None = None,
    submitted_write_in_last_cycle: object = "0",
    previous_verified_our_price_gbp: object = "",
    our_purchasable_flag: object = "",
    our_purchasable_reliable_flag: object = "0",
    pricing_health_suppressed_flag: object = "0",
    promo_suspected_flag: object = "0",
    now_utc: str | None = None,
    daily_intel_refresher: Callable[[], object] | None = None,
) -> HcycleResult:
    event_ts = str(now_utc or _utc_now_iso())
    today = event_ts[:10]
    writer_mode = _canonical_writer_mode(pricing_writer_mode)
    invalid_writer_mode = writer_mode not in ALLOWED_WRITER_MODES
    writer_lock_blocked = writer_mode != "CODEX_H"

    snap = phase1_market_snapshot_processor.process_competitive_summary(
        payload=market_payload,
        sku=sku,
        asin=asin,
        marketplace_id=marketplace_id,
        our_seller_id=our_seller_id,
        snapshot_ts_utc=event_ts,
    )
    phase1_storage.append("offer_snapshot_facts", snap.rows)
    phase1_storage.upsert("offer_variants", ["offer_variant_id"], _build_offer_variants_rows(snap.rows, event_ts))

    dve = phase1_dve.apply_dve_v0(snap.rows)
    featured_winner_delivery_unknown = _featured_winner_delivery_unknown(
        snapshot_rows=dve.rows,
        featured_offer_winner_seller_id=snap.featured_offer_winner_seller_id,
    )
    pricing_rows = _disable_dve_rows(dve.rows) if featured_winner_delivery_unknown else dve.rows
    best_rival = phase1_probe_engine.best_rival_effective_price(pricing_rows)
    best_rival_effective, direct_competitor_variant_id = _best_rival_effective_and_variant_id(pricing_rows)
    buy_box_present = "1" if str(snap.featured_offer_price_gbp or "").strip() else "0"
    outcome_known = "0" if bool(getattr(snap, "unknown_featured_outcome", False)) else "1"
    we_present = "1" if any(str(r.get("is_our_offer", "")).strip() == "1" for r in pricing_rows) else "0"
    if we_present != "1" and str(current_price_gbp or "").strip():
        we_present = "1"
    hold_buy_box_missing = buy_box_present != "1"
    hold_outcome_unknown = outcome_known != "1"
    hold_we_not_present = we_present != "1"
    observable = not (hold_buy_box_missing or hold_outcome_unknown or hold_we_not_present)
    allowed_to_act_count = 1 if observable else 0
    reason_codes: list[str] = []
    refresh_attempted_count = "0"
    refresh_throttled_count = "0"
    blocked_due_to_missing_intel = "0"
    blocked_due_to_stale_intel = "0"
    daily_intel = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
    daily_intel_status = _daily_intel_gate_status(daily_intel=daily_intel, today_utc_date=today)
    if daily_intel_status != "FRESH":
        can_attempt_refresh = daily_intel_refresher is not None and not _refresh_already_attempted_today(sku=sku, today_utc_date=today)
        if can_attempt_refresh:
            refresh_attempted_count = "1"
            refresh_status = "error"
            try:
                daily_intel_refresher()
                refresh_status = "ok"
            except Exception:
                refresh_status = "error"
            _record_refresh_attempt(event_ts_utc=event_ts, sku=sku, today_utc_date=today, status=refresh_status)
            reason_codes.append("DAILY_INTEL_REFRESH_ATTEMPTED")
            daily_intel = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
            daily_intel_status = _daily_intel_gate_status(daily_intel=daily_intel, today_utc_date=today)
        elif daily_intel_refresher is not None:
            refresh_throttled_count = "1"
            reason_codes.append("DAILY_INTEL_REFRESH_THROTTLED")

    if daily_intel_status != "FRESH":
        if daily_intel_status == "STALE":
            reason_codes.append("DAILY_INTEL_STALE")
            blocked_due_to_stale_intel = "1"
        else:
            reason_codes.append("DAILY_INTEL_MISSING")
            blocked_due_to_missing_intel = "1"
        reason_codes.append("A_CYCLE_MISSING_DEFENSIVE_HOLD")
        phase1_storage.append(
            "decision_log",
            [
                {
                    "event_ts_utc": event_ts,
                    "ts_utc": event_ts,
                    "sku": sku,
                    "asin": asin,
                    "sku_or_asin": sku or asin,
                    "buy_box_present": buy_box_present,
                    "outcome_known": outcome_known,
                    "we_present": we_present,
                    "action": "HOLD",
                    "reason": "daily_intel_gate",
                    "hold_reason": "daily_intel_missing_or_stale",
                    "proposed_price_gbp": "",
                    "current_price_gbp": str(current_price_gbp or ""),
                    "best_rival_effective_price_gbp": _money(best_rival_effective),
                    "direct_competitor_variant_id": direct_competitor_variant_id,
                    "writer_mode": writer_mode,
                }
            ],
        )
        phase1_storage.append(
            "scenario_rollup",
            [
                {
                    "event_ts_utc": event_ts,
                    "sku": sku,
                    "asin": asin,
                    "hold_buy_box_missing_count": "1" if hold_buy_box_missing else "0",
                    "hold_outcome_unknown_count": "1" if hold_outcome_unknown else "0",
                    "allowed_to_act_count": str(allowed_to_act_count),
                }
            ],
        )
        phase1_storage.append(
            "execution_log",
            [
                {
                    "event_ts_utc": event_ts,
                    "sku": sku,
                    "state": "DEFENSIVE_HOLD",
                    "old_price_gbp": str(current_price_gbp or ""),
                    "new_price_gbp": str(current_price_gbp or ""),
                    "write_status": "READ_ONLY_NO_WRITE",
                    "write_error": "daily_intel_missing_or_stale",
                    "final_ceiling_landed_gbp": "",
                    "hard_floor_gbp": str(hard_floor_gbp or ""),
                    "reason_codes_json": _json_compact(reason_codes),
                }
            ],
        )
        return HcycleResult(
            sku=sku,
            state="DEFENSIVE_HOLD",
            write_status="READ_ONLY_NO_WRITE",
            final_ceiling_landed_gbp="",
            probe_id="",
            reason_codes=reason_codes,
            oas_admissible_flag="",
            blocked_due_to_missing_intel=blocked_due_to_missing_intel,
            blocked_due_to_stale_intel=blocked_due_to_stale_intel,
            refresh_attempted_count=refresh_attempted_count,
            refresh_throttled_count=refresh_throttled_count,
        )

    parked_flag = _is_truthy(daily_intel.get("parked_flag", "0"))
    cpt_risk_band = str(daily_intel.get("cpt_risk_band", "") or "").strip().upper() or "UNKNOWN"
    if parked_flag:
        reason_codes.append("PARKED_NO_ACTION")
        phase1_storage.append(
            "decision_log",
            [
                {
                    "event_ts_utc": event_ts,
                    "ts_utc": event_ts,
                    "sku": sku,
                    "asin": asin,
                    "sku_or_asin": sku or asin,
                    "buy_box_present": buy_box_present,
                    "outcome_known": outcome_known,
                    "we_present": we_present,
                    "action": "HOLD",
                    "reason": "parked_gate",
                    "hold_reason": "parked_no_action",
                    "proposed_price_gbp": "",
                    "current_price_gbp": str(current_price_gbp or ""),
                    "best_rival_effective_price_gbp": _money(best_rival_effective),
                    "direct_competitor_variant_id": direct_competitor_variant_id,
                    "writer_mode": writer_mode,
                }
            ],
        )
        phase1_storage.append(
            "scenario_rollup",
            [
                {
                    "event_ts_utc": event_ts,
                    "sku": sku,
                    "asin": asin,
                    "hold_buy_box_missing_count": "1" if hold_buy_box_missing else "0",
                    "hold_outcome_unknown_count": "1" if hold_outcome_unknown else "0",
                    "allowed_to_act_count": "0",
                }
            ],
        )
        phase1_storage.append(
            "execution_log",
            [
                {
                    "event_ts_utc": event_ts,
                    "sku": sku,
                    "state": "DEFENSIVE_HOLD",
                    "old_price_gbp": str(current_price_gbp or ""),
                    "new_price_gbp": str(current_price_gbp or ""),
                    "write_status": "READ_ONLY_NO_WRITE",
                    "write_error": "parked_no_action",
                    "final_ceiling_landed_gbp": "",
                    "hard_floor_gbp": str(hard_floor_gbp or ""),
                    "reason_codes_json": _json_compact(reason_codes),
                }
            ],
        )
        return HcycleResult(
            sku=sku,
            state="DEFENSIVE_HOLD",
            write_status="READ_ONLY_NO_WRITE",
            final_ceiling_landed_gbp="",
            probe_id="",
            reason_codes=reason_codes,
            oas_admissible_flag="",
            blocked_due_to_missing_intel=blocked_due_to_missing_intel,
            blocked_due_to_stale_intel=blocked_due_to_stale_intel,
            refresh_attempted_count=refresh_attempted_count,
            refresh_throttled_count=refresh_throttled_count,
        )

    compliance_ceiling = str(daily_intel.get("compliance_ceiling_landed_gbp", "") or "")
    eligibility_ceiling = str(daily_intel.get("eligibility_ceiling_landed_gbp", "") or "")

    final_ceiling = phase1_ceilings.compute_final_ceiling(
        compliance_ceiling_landed_gbp=compliance_ceiling,
        eligibility_ceiling_landed_gbp=eligibility_ceiling,
        manual_cap_gbp=manual_cap_gbp,
    )

    our_penalty = ""
    for row in pricing_rows:
        if str(row.get("is_our_offer", "")).strip() == "1":
            our_penalty = str(row.get("delivery_penalty_gbp", "") or "")
            break
    phase1_storage.append(
        "sku_ceiling_events",
        [
            {
                "event_ts_utc": event_ts,
                "sku": sku,
                "our_delivery_penalty_gbp": our_penalty,
                "compliance_ceiling_landed_gbp": final_ceiling.compliance_ceiling_landed_gbp,
                "eligibility_ceiling_landed_gbp": final_ceiling.eligibility_ceiling_landed_gbp,
                "demand_ceiling_landed_gbp": final_ceiling.demand_ceiling_landed_gbp,
                "final_ceiling_landed_gbp": final_ceiling.final_ceiling_landed_gbp,
                "binding_ceiling_type": final_ceiling.binding_ceiling_type,
                "ceiling_reason_codes_json": _json_compact(final_ceiling.reason_codes),
            }
        ],
    )

    memory = phase1_storage.read_by_keys("variant_delta_memory", {"sku": sku, "rival_key": "BEST_RIVAL"}) or {
        "sku": sku,
        "rival_key": "BEST_RIVAL",
        "learned_delta_effective_gbp": "",
        "highest_delta_win_effective_gbp": "",
        "lowest_delta_loss_effective_gbp": "",
        "delta_confidence": "0",
        "valid_test_count": "0",
        "contaminated_test_count": "0",
        "last_valid_test_utc": "",
    }

    featured_outcome = phase1_probe_engine.evaluate_featured_outcome(
        featured_offer_winner_seller_id=snap.featured_offer_winner_seller_id,
        our_seller_id=our_seller_id,
        snapshot_rows=pricing_rows,
    )
    state_result = phase1_probe_engine.resolve_probe_state(
        featured_outcome=featured_outcome,
        best_rival_effective_price_gbp=best_rival,
        highest_delta_win_effective_gbp=memory.get("highest_delta_win_effective_gbp", ""),
        lowest_delta_loss_effective_gbp=memory.get("lowest_delta_loss_effective_gbp", ""),
        delta_tolerance_gbp=delta_tolerance_gbp,
    )
    decision = phase1_probe_engine.choose_next_price(
        state=state_result.state,
        current_price_gbp=current_price_gbp,
        hard_floor_gbp=hard_floor_gbp,
        final_ceiling_landed_gbp=final_ceiling.final_ceiling_landed_gbp,
        max_step_down_gbp=max_step_down_gbp,
        max_step_up_gbp=max_step_up_gbp,
        max_daily_drop_gbp=max_daily_drop_gbp,
        daily_drop_used_gbp=daily_drop_used_gbp,
        highest_delta_win_effective_gbp=memory.get("highest_delta_win_effective_gbp", ""),
        lowest_delta_loss_effective_gbp=memory.get("lowest_delta_loss_effective_gbp", ""),
        best_rival_effective_price_gbp=_money(best_rival),
        stable_buffer_gbp=stable_buffer_gbp,
    )

    decision_effective = decision
    current_dec = _to_decimal(current_price_gbp)
    target_dec = _to_decimal(decision.target_price_gbp)
    if current_dec is not None and target_dec is not None and target_dec > current_dec:
        if cpt_risk_band == "HIGH":
            decision_effective = phase1_probe_engine.NextPriceDecision(
                state=decision.state,
                target_price_gbp=_money(current_dec),
                write_required=False,
                reason_codes=decision.reason_codes + ["CPT_RISK_HIGH_UPWARD_BLOCK"],
            )
        elif cpt_risk_band == "UNKNOWN":
            decision_effective = phase1_probe_engine.NextPriceDecision(
                state=decision.state,
                target_price_gbp=_money(current_dec),
                write_required=False,
                reason_codes=decision.reason_codes + ["CPT_RISK_UNKNOWN_CONSERVATIVE_HOLD"],
            )

    write_status = "NO_WRITE_REQUIRED"
    write_error = ""
    probe_id = ""
    reason_codes.extend(state_result.reason_codes + decision_effective.reason_codes + final_ceiling.reason_codes)
    if featured_winner_delivery_unknown:
        reason_codes.append("DVE_DISABLED_FEATURED_WINNER_DELIVERY_UNKNOWN")
    if writer_lock_blocked:
        reason_codes.append("WRITER_LOCK_BLOCK")
    if invalid_writer_mode:
        reason_codes.append("WRITER_MODE_INVALID")

    if decision_effective.write_required and not observable:
        write_status = "OBSERVABILITY_BLOCK_NO_WRITE"
        write_error = "observable_gate_blocked"
        reason_codes.append("SUPPRESSION_OR_UNKNOWN_OUTCOME")
    elif decision_effective.write_required and writer_lock_blocked:
        write_status = "READ_ONLY_NO_WRITE"
        write_error = (
            f"writer_lock_block mode={writer_mode or 'UNKNOWN'} requires=CODEX_H"
            if invalid_writer_mode
            else ""
        )
    elif decision_effective.write_required and enabled_live_writes and write_submitter is not None:
        start_snapshot_id = str(snap.rows[0].get("offer_snapshot_id", "")) if snap.rows else ""
        start_hash = phase1_oas.build_market_structure_hash(dve.rows)
        write_result = phase1_write_verify.execute_write_verify_and_start_probe(
            sku=sku,
            state_at_start=decision_effective.state,
            proposed_price_gbp=decision_effective.target_price_gbp,
            hard_floor_gbp=hard_floor_gbp,
            price_apply_tolerance_gbp=price_apply_tolerance_gbp,
            start_snapshot_id=start_snapshot_id,
            start_featured_seller_id=snap.featured_offer_winner_seller_id,
            market_structure_hash_start=start_hash,
            listings_observed_price_gbp=listings_observed_price_gbp,
            latest_snapshot_rows=snap.rows,
            write_submitter=write_submitter,
            now_utc=event_ts,
        )
        write_status = write_result.write_status
        write_error = write_result.write_error
        probe_id = write_result.probe_id
        reason_codes.extend(write_result.reason_codes)
    elif decision_effective.write_required and not enabled_live_writes:
        write_status = "READ_ONLY_NO_WRITE"
        reason_codes.append("LIVE_WRITES_DISABLED")

    action = "HOLD"
    if write_status == "APPLIED":
        action = "WRITE"
    elif decision_effective.write_required and allowed_to_act_count == 1:
        action = "PROPOSED_WRITE"
    blocker_reasons: list[str] = []
    if hold_buy_box_missing:
        blocker_reasons.append("buy_box_missing")
    if hold_outcome_unknown:
        blocker_reasons.append("outcome_unknown")
    if hold_we_not_present:
        blocker_reasons.append("we_not_present")
    hold_reason = "|".join(blocker_reasons)
    decision_reason = "|".join(blocker_reasons) if blocker_reasons else decision_effective.state
    proposed_price = decision_effective.target_price_gbp if decision_effective.write_required else ""

    phase1_storage.append(
        "decision_log",
        [
            {
                "event_ts_utc": event_ts,
                "ts_utc": event_ts,
                "sku": sku,
                "asin": asin,
                "sku_or_asin": sku or asin,
                "buy_box_present": buy_box_present,
                "outcome_known": outcome_known,
                "we_present": we_present,
                "action": action,
                "reason": decision_reason,
                "hold_reason": hold_reason,
                "proposed_price_gbp": proposed_price,
                "current_price_gbp": str(current_price_gbp or ""),
                "best_rival_effective_price_gbp": _money(best_rival_effective),
                "direct_competitor_variant_id": direct_competitor_variant_id,
                "writer_mode": writer_mode,
            }
        ],
    )
    phase1_storage.append(
        "scenario_rollup",
        [
            {
                "event_ts_utc": event_ts,
                "sku": sku,
                "asin": asin,
                "hold_buy_box_missing_count": "1" if hold_buy_box_missing else "0",
                "hold_outcome_unknown_count": "1" if hold_outcome_unknown else "0",
                "allowed_to_act_count": str(allowed_to_act_count),
            }
        ],
    )

    phase1_storage.append(
        "execution_log",
        [
            {
                "event_ts_utc": event_ts,
                "sku": sku,
                "state": decision_effective.state,
                "old_price_gbp": str(current_price_gbp or ""),
                "new_price_gbp": decision_effective.target_price_gbp,
                "write_status": write_status,
                "write_error": write_error,
                "final_ceiling_landed_gbp": final_ceiling.final_ceiling_landed_gbp,
                "hard_floor_gbp": str(hard_floor_gbp or ""),
                "reason_codes_json": _json_compact(reason_codes),
            }
        ],
    )

    oas_admissible = ""
    if probe_observation_payload is not None:
        open_probe = _pick_latest_open_probe(sku)
        if open_probe is not None:
            end_snap = phase1_market_snapshot_processor.process_competitive_summary(
                payload=probe_observation_payload,
                sku=sku,
                asin=asin,
                marketplace_id=marketplace_id,
                our_seller_id=our_seller_id,
                snapshot_ts_utc=event_ts,
            )
            phase1_storage.append("offer_snapshot_facts", end_snap.rows)
            end_dve = phase1_dve.apply_dve_v0(end_snap.rows)
            end_featured_winner_delivery_unknown = _featured_winner_delivery_unknown(
                snapshot_rows=end_dve.rows,
                featured_offer_winner_seller_id=end_snap.featured_offer_winner_seller_id,
            )
            end_pricing_rows = _disable_dve_rows(end_dve.rows) if end_featured_winner_delivery_unknown else end_dve.rows
            end_hash = phase1_oas.build_market_structure_hash(end_pricing_rows)
            end_featured_outcome = phase1_probe_engine.evaluate_featured_outcome(
                featured_offer_winner_seller_id=end_snap.featured_offer_winner_seller_id,
                our_seller_id=our_seller_id,
                snapshot_rows=end_pricing_rows,
            )
            conflict_flag, conflict_reason = phase1_oas.detect_writer_conflict(
                submitted_write_in_last_cycle=submitted_write_in_last_cycle,
                previous_verified_our_price_gbp=previous_verified_our_price_gbp,
                current_verified_our_price_gbp=_our_price_from_rows(end_snap.rows),
                approved_manual_override_prices_gbp=writer_conflict_manual_allowlist_gbp or [],
            )
            oas = phase1_oas.evaluate_oas_hard_fails(
                market_structure_hash_start=open_probe.get("market_structure_hash_start", ""),
                market_structure_hash_end=end_hash,
                featured_outcome=end_featured_outcome,
                writer_conflict_flag="1" if conflict_flag else "0",
                promo_suspected_flag=promo_suspected_flag,
                pricing_health_suppressed_flag=pricing_health_suppressed_flag,
                our_purchasable_flag=our_purchasable_flag,
                our_purchasable_reliable_flag=our_purchasable_reliable_flag,
                featured_winner_delivery_unknown_flag="1" if end_featured_winner_delivery_unknown else "0",
            )
            oas_admissible = oas.admissible_flag
            phase1_storage.append(
                "oas_log",
                [
                    {
                        "event_ts_utc": event_ts,
                        "probe_id": open_probe.get("probe_id", ""),
                        "sku": sku,
                        "context_quality_score": oas.context_quality_score,
                        "admissible_flag": oas.admissible_flag,
                        "hard_fail_reason_codes_json": _json_compact(oas.hard_fail_reason_codes),
                        "notes": "; ".join(
                            part
                            for part in [
                                conflict_reason,
                                "FEATURED_WINNER_DELIVERY_UNKNOWN" if end_featured_winner_delivery_unknown else "",
                            ]
                            if part
                        ),
                    }
                ],
            )

            close_row = dict(open_probe)
            close_row.update(
                {
                    "end_ts_utc": event_ts,
                    "end_snapshot_id": str(end_snap.rows[0].get("offer_snapshot_id", "")) if end_snap.rows else "",
                    "end_featured_seller_id": end_snap.featured_offer_winner_seller_id,
                    "observed_outcome": "WIN" if end_featured_outcome == "OURS" else "LOSS" if end_featured_outcome == "NOT_OURS" else "UNKNOWN",
                    "market_structure_hash_end": end_hash,
                    "oas_result": "ADMISSIBLE" if oas.admissible_flag == "1" else "BLOCKED",
                }
            )
            phase1_storage.append("probe_windows", [close_row])

            end_best_rival = phase1_probe_engine.best_rival_effective_price(end_pricing_rows)
            observed_delta = ""
            our_effective = None
            for row in end_pricing_rows:
                if str(row.get("is_our_offer", "")).strip() == "1":
                    our_effective = _to_decimal(row.get("effective_price_gbp"))
                    break
            if our_effective is not None and end_best_rival is not None:
                observed_delta = _money(our_effective - end_best_rival)

            floor_ceiling_conflict = "FLOOR_PRIORITY_CEILING_CONFLICT" in reason_codes
            if observable and not floor_ceiling_conflict:
                memory_update = phase1_probe_engine.update_delta_memory(
                    current_memory=memory,
                    observed_delta_effective_gbp=observed_delta,
                    observed_outcome=close_row.get("observed_outcome", ""),
                    oas_admissible_flag=oas.admissible_flag,
                    now_utc=event_ts,
                    min_clean_tests_for_confidence=min_clean_tests_for_confidence,
                )
                phase1_storage.upsert(
                    "variant_delta_memory",
                    ["sku", "rival_key"],
                    [
                        {
                            "sku": sku,
                            "rival_key": "BEST_RIVAL",
                            "learned_delta_effective_gbp": memory_update.learned_delta_effective_gbp,
                            "highest_delta_win_effective_gbp": memory_update.highest_delta_win_effective_gbp,
                            "lowest_delta_loss_effective_gbp": memory_update.lowest_delta_loss_effective_gbp,
                            "delta_confidence": memory_update.delta_confidence,
                            "valid_test_count": memory_update.valid_test_count,
                            "contaminated_test_count": memory_update.contaminated_test_count,
                            "last_valid_test_utc": memory_update.last_valid_test_utc,
                        }
                    ],
                )

    return HcycleResult(
        sku=sku,
        state=decision_effective.state,
        write_status=write_status,
        final_ceiling_landed_gbp=final_ceiling.final_ceiling_landed_gbp,
        probe_id=probe_id,
        reason_codes=reason_codes,
        oas_admissible_flag=oas_admissible,
        blocked_due_to_missing_intel=blocked_due_to_missing_intel,
        blocked_due_to_stale_intel=blocked_due_to_stale_intel,
        refresh_attempted_count=refresh_attempted_count,
        refresh_throttled_count=refresh_throttled_count,
    )


def _run_demo() -> None:
    # Keep demo writes isolated from live operational tables.
    original_data_dir = phase1_storage.DATA_DIR
    original_lock_path = phase1_storage.LOCK_PATH
    demo_data_dir = BOOT_ROOT / "data_demo"
    demo_lock_path = BOOT_ROOT / "out" / "phase1_demo.lock"
    demo_data_dir.mkdir(parents=True, exist_ok=True)
    demo_lock_path.parent.mkdir(parents=True, exist_ok=True)
    phase1_storage.DATA_DIR = demo_data_dir
    phase1_storage.LOCK_PATH = demo_lock_path

    try:
        now = _utc_now_iso()
        a = run_a_cycle(
            sku="DEMO-SKU",
            now_utc=now,
            compliance_anchor_gbp="20.00",
            policy_buffer_pct="0.03",
            manual_cap_gbp="19.00",
            foep_price_gbp="18.95",
            foep_status="OK",
            foep_last_refresh_utc=now,
            cpt_gbp="18.90",
            cpt_last_refresh_utc=now,
            last_known_safe_gbp="18.80",
            foep_stale_hours=48,
            foep_sanity_min_mult="0.5",
            foep_sanity_max_mult="2.0",
            market_reference_price_gbp="19.00",
        )

        payload = {
            "offers": [
                {
                    "SellerId": "OUR_SELLER",
                    "ListingPrice": {"Amount": 10.40},
                    "Shipping": {"Amount": 0.00},
                    "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                    "IsFeaturedOfferWinner": False,
                    "IsFulfilledByAmazon": True,
                },
                {
                    "SellerId": "RIVAL_A",
                    "ListingPrice": {"Amount": 10.30},
                    "Shipping": {"Amount": 0.00},
                    "ShippingTime": {"minimumDays": 1, "maximumDays": 1},
                    "IsFeaturedOfferWinner": True,
                    "IsFulfilledByAmazon": True,
                },
            ]
        }
        h = run_h_cycle(
            sku="DEMO-SKU",
            asin="DEMO-ASIN",
            marketplace_id="A1F83G8C2ARO7P",
            our_seller_id="OUR_SELLER",
            pricing_writer_mode="CODEX_H",
            enabled_live_writes=False,
            current_price_gbp="10.40",
            hard_floor_gbp="9.50",
            manual_cap_gbp="19.00",
            max_step_down_gbp="0.20",
            max_step_up_gbp="0.20",
            max_daily_drop_gbp="0.60",
            daily_drop_used_gbp="0.00",
            delta_tolerance_gbp="0.02",
            stable_buffer_gbp="0.02",
            min_clean_tests_for_confidence=5,
            price_apply_tolerance_gbp="0.01",
            policy_buffer_pct="0.03",
            market_payload=payload,
            now_utc=now,
        )

        print(
            _json_compact(
                {
                    "demo_data_dir": str(demo_data_dir),
                    "a_cycle": a.__dict__,
                    "h_cycle": h.__dict__,
                }
            )
        )
    finally:
        phase1_storage.DATA_DIR = original_data_dir
        phase1_storage.LOCK_PATH = original_lock_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 main loop wiring (A-cycle + H-cycle + logging)")
    parser.add_argument("--demo", action="store_true", help="Run a local demo cycle with sample payload")
    args = parser.parse_args()

    if args.demo:
        _run_demo()
        return

    raise SystemExit("Use --demo to run the wired Phase 1 loop locally.")


if __name__ == "__main__":
    main()
