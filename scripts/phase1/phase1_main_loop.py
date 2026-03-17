from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable, Mapping

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

try:
    from scripts.phase1 import phase1_ceilings, phase1_dve, phase1_market_snapshot_processor, phase1_oas, phase1_phase_engine, phase1_probe_engine, phase1_storage, phase1_write_gate, phase1_write_verify
except ModuleNotFoundError:
    from scripts.phase1 import phase1_ceilings, phase1_dve, phase1_market_snapshot_processor, phase1_oas, phase1_phase_engine, phase1_probe_engine, phase1_storage, phase1_write_gate, phase1_write_verify


PHASE_WRITE_AUDIT_PATH = BOOT_ROOT / "out" / "phase_write_audit.csv"
H_FLOOR_TRACE_PATH = BOOT_ROOT / "out" / "h_floor_truth_trace.csv"
PHASE_WRITE_AUDIT_FIELDS = [
    "ts_utc",
    "sku",
    "allowed",
    "writer_mode",
    "in_cohort",
    "excluded",
    "flag_live",
    "effective_live_writes",
    "attempted_write",
    "wrote",
]

_floor_trace_cache: tuple[float, dict[str, tuple[str, Decimal, Decimal]]] | None = None


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


def _max_money(*values: object) -> str:
    candidates = [d for d in (_to_decimal(value) for value in values) if d is not None]
    if not candidates:
        return ""
    return _money(max(candidates))


def _is_truthy(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _env_flag(name: str, default: str) -> bool:
    raw = str(os.environ.get(name, default) or "").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _env_text(name: str, default: str) -> str:
    return str(os.environ.get(name, default) or "").strip() or default


def _phase_log(line: str) -> None:
    text = str(line or "").strip()
    if not text:
        return
    print(text, file=sys.stderr, flush=True)
    progress_path = str(os.environ.get("H_PHASE1_PROGRESS_PATH", "") or "").strip()
    if not progress_path:
        return
    try:
        p = Path(progress_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    except Exception:
        pass


def _csv_cell(value: object) -> str:
    text = str(value or "")
    if any(ch in text for ch in [",", "\"", "\n", "\r"]):
        text = "\"" + text.replace("\"", "\"\"") + "\""
    return text


def _append_phase_write_audit(row: Mapping[str, object]) -> None:
    PHASE_WRITE_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PHASE_WRITE_AUDIT_PATH.open("a", encoding="utf-8", newline="\n") as fh:
        if fh.tell() == 0:
            fh.write(",".join(PHASE_WRITE_AUDIT_FIELDS) + "\n")
        fh.write(",".join(_csv_cell(row.get(k, "")) for k in PHASE_WRITE_AUDIT_FIELDS) + "\n")


def _load_floor_trace_latest_map() -> dict[str, tuple[str, Decimal, Decimal]]:
    global _floor_trace_cache
    if not H_FLOOR_TRACE_PATH.exists():
        _floor_trace_cache = (0.0, {})
        return {}
    mtime = H_FLOOR_TRACE_PATH.stat().st_mtime
    if _floor_trace_cache is not None and _floor_trace_cache[0] == mtime:
        return _floor_trace_cache[1]

    latest: dict[str, tuple[str, Decimal, Decimal]] = {}
    try:
        frame = pd.read_csv(H_FLOOR_TRACE_PATH, dtype=str, keep_default_na=False, engine="python")
        for row in frame.to_dict("records"):
            sku = str(row.get("sku", "")).strip().upper()
            if not sku:
                continue
            asof = str(row.get("asof_utc", "")).strip()
            break_even = _to_decimal(row.get("break_even_total_gbp"))
            floor_total = _to_decimal(row.get("floor_total_gbp"))
            if break_even is None or floor_total is None:
                continue
            prev = latest.get(sku)
            if prev is None or asof >= prev[0]:
                latest[sku] = (asof, break_even, floor_total)
    except Exception:
        latest = {}

    _floor_trace_cache = (mtime, latest)
    return latest


def _phase1_relaxed_floor_gbp(*, sku: str, hard_floor: Decimal, soft_floor_relax_pct: Decimal) -> Decimal:
    floor_map = _load_floor_trace_latest_map()
    entry = floor_map.get(str(sku or "").strip().upper())
    if entry is None:
        return hard_floor
    break_even_total = entry[1]
    if hard_floor <= break_even_total:
        return hard_floor
    if soft_floor_relax_pct <= Decimal("0") or soft_floor_relax_pct >= Decimal("1"):
        return hard_floor
    keep_ratio = Decimal("1") - soft_floor_relax_pct
    adjusted = break_even_total + ((hard_floor - break_even_total) * keep_ratio)
    if adjusted < break_even_total:
        adjusted = break_even_total
    if adjusted > hard_floor:
        adjusted = hard_floor
    return adjusted


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
    parked_flag = _is_truthy(daily_intel.get("parked_flag", "0"))
    if not date_utc:
        return "MISSING"
    if date_utc != today_utc_date:
        return "STALE"
    if parked_flag:
        return "FRESH"
    # Eligibility ceiling can be blank for valid rows (for example CPT-only ceiling source).
    # Gate on compliance ceiling presence to avoid false defensive-hold.
    if compliance_ceiling == "":
        return "MISSING"
    return "FRESH"


def _cannot_compete_phase_state(*, phase: int) -> str:
    if int(phase or 0) >= 4:
        return "LIQUIDATE_TO_FLOOR"
    if int(phase or 0) >= 3:
        return "CONTROLLED_EXIT_TO_FLOOR"
    if int(phase or 0) >= 2:
        return "MARGIN_COMPRESS_TO_FLOOR"
    return ""


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
    cpt_ceiling_input_gbp: object = "",
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
    bbp_max_sold_gbp: object = "",
    competitive_price_threshold_gbp: object = "",
    competitive_price_gbp: object = "",
    average_selling_price_gbp: object = "",
    anchor_floor_price_gbp: object = "",
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
    bbp_max_sold_text = str(bbp_max_sold_gbp or "").strip()
    competitive_price_threshold_text = str(competitive_price_threshold_gbp or cpt_gbp or "").strip()
    competitive_price_text = str(competitive_price_gbp or "").strip()
    average_selling_price_text = str(average_selling_price_gbp or "").strip()
    anchor_floor_price_text = str(anchor_floor_price_gbp or "").strip()
    cpt_ceiling_input_text = str(cpt_ceiling_input_gbp or "").strip()
    bbp_dec = _to_decimal(bbp_max_sold_text)
    cpt_ceiling_input_dec = _to_decimal(cpt_ceiling_input_text)
    cpt_x1_2_dec = cpt_ceiling_input_dec * Decimal("1.2") if cpt_ceiling_input_dec is not None and cpt_ceiling_input_dec > 0 else None
    ceiling_source_used = "NONE"
    ceiling_rule_dec: Decimal | None = None
    if bbp_dec is not None and bbp_dec > 0 and cpt_x1_2_dec is not None and cpt_x1_2_dec > 0:
        ceiling_rule_dec = min(bbp_dec, cpt_x1_2_dec)
        ceiling_source_used = "MIN_BBP_CPTX1_2"
    elif bbp_dec is not None and bbp_dec > 0:
        ceiling_rule_dec = bbp_dec
        ceiling_source_used = "BBP_ONLY"
    elif cpt_x1_2_dec is not None and cpt_x1_2_dec > 0:
        ceiling_rule_dec = cpt_x1_2_dec
        ceiling_source_used = "CPTX1_2_ONLY"
    else:
        ceiling_source_used = "MISSING"
    ceiling_inputs_missing_flag = "1" if ceiling_rule_dec is None else "0"

    row = {
        "date_utc": str(now_utc)[:10],
        "sku": sku,
        "foep_price_gbp": str(foep_price_gbp or ""),
        "foep_status": str(foep_status or ""),
        "foep_last_refresh_utc": str(foep_last_refresh_utc or ""),
        "bbp_max_sold_gbp": bbp_max_sold_text,
        "cpt_gbp": str(cpt_gbp or ""),
        "cpt_ceiling_input_gbp": cpt_ceiling_input_text,
        "cpt_x1_2_gbp": _money(cpt_x1_2_dec),
        "cpt_last_refresh_utc": str(cpt_last_refresh_utc or ""),
        "cpt_status": cpt_status_text,
        "cpt_risk_band": cpt_risk_band_text,
        "cpt_delta_vs_buy_box_gbp": str(cpt_delta_vs_buy_box_gbp or ""),
        "cpt_delta_vs_buy_box_pct": str(cpt_delta_vs_buy_box_pct or ""),
        "cpt_call_tier": str(cpt_call_tier or ""),
        "cpt_call_reason_codes_json": _json_compact(cpt_call_reason_codes),
        "ceiling_rule_value_gbp": _money(ceiling_rule_dec),
        "ceiling_source_used": ceiling_source_used,
        "ceiling_inputs_missing_flag": ceiling_inputs_missing_flag,
        "parked_flag": parked_text,
        "park_reason_codes_json": _json_compact(park_reason_codes),
        "eligibility_ceiling_landed_gbp": eligibility.eligibility_ceiling_landed_gbp,
        "eligibility_source": eligibility.eligibility_source,
        "eligibility_confidence": eligibility.eligibility_confidence,
        "eligibility_reason_codes_json": _json_compact(eligibility.reason_codes + extra_reason_codes),
        "competitive_price_threshold_gbp": competitive_price_threshold_text,
        "competitive_price_gbp": competitive_price_text,
        "average_selling_price_gbp": average_selling_price_text,
        "suppression_reactivation_target_landed_gbp": "",
        "suppression_target_source": "",
        "suppression_ceiling_landed_temp": "",
        "suppression_ceiling_source": "",
        "suppression_ceiling_confidence": "",
        "suppression_ceiling_expiry_utc": "",
        "anchor_floor_price_gbp": anchor_floor_price_text,
        "compliance_ceiling_landed_gbp": compliance.compliance_ceiling_landed_gbp,
        "compliance_confidence": compliance.compliance_confidence,
        "compliance_status": "",
        "compliance_reason_code": "",
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
    post_write_observed_price_lookup: Callable[[], object] | None = None,
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
    reentry_price_discovery_active: bool = False,
    reentry_event: bool = False,
    inbound_price_discovery_active: bool = False,
) -> HcycleResult:
    event_ts = str(now_utc or _utc_now_iso())
    phase_engine_enabled = _env_flag("H_PHASE_ENGINE_ENABLED", "0")
    phase_engine_shadow = _env_flag("H_PHASE_ENGINE_SHADOW", "1")
    phase_engine_behavior = _env_flag("H_PHASE_ENGINE_BEHAVIOR", "0")
    phase_engine_live_writes = _env_flag("H_PHASE_ENGINE_LIVE_WRITES", "0")
    phase_engine_cohort_file = _env_text("H_PHASE_ENGINE_COHORT_FILE", "config/phase_engine_cohort.csv")
    phase_engine_exclude_file = _env_text("H_PHASE_ENGINE_EXCLUDE_FILE", "config/phase_engine_exclusions.csv")
    phase_shadow: object | None = None
    phase_behavior_phase = 0
    phase_behavior_excluded = phase1_phase_engine.sku_in_csv(phase_engine_exclude_file, sku)
    phase_behavior_in_cohort = phase1_phase_engine.sku_in_csv(phase_engine_cohort_file, sku)
    _phase_log(
        f"PHASE_ENGINE_FLAGS sku={sku} enabled={'1' if phase_engine_enabled else '0'} "
        f"shadow={'1' if phase_engine_shadow else '0'} "
        f"behavior={'1' if phase_engine_behavior else '0'} "
        f"live={'1' if phase_engine_live_writes else '0'} "
        f"cohort_file={phase_engine_cohort_file} "
        f"exclude_file={phase_engine_exclude_file}"
    )
    _phase_log(
        f"PHASE_ENGINE_MEMBERSHIP sku={sku} in_cohort={'1' if phase_behavior_in_cohort else '0'} "
        f"excluded={'1' if phase_behavior_excluded else '0'}"
    )
    today = event_ts[:10]
    writer_mode = _canonical_writer_mode(pricing_writer_mode)
    invalid_writer_mode = writer_mode not in ALLOWED_WRITER_MODES
    writer_lock_blocked = writer_mode != "CODEX_H"
    live_gate = phase1_write_gate.evaluate_live_write_gate(
        writer_mode=writer_mode,
        phase_engine_enabled=phase_engine_enabled,
        phase_engine_behavior=phase_engine_behavior,
        phase_engine_live_writes=phase_engine_live_writes,
        in_cohort=phase_behavior_in_cohort,
        excluded=phase_behavior_excluded,
    )
    live_gate_reason = live_gate.reason_codes[0] if live_gate.reason_codes else "PHASE_LIVE_WRITE_BLOCKED_FLAG_OFF"
    live_gate_allowed = live_gate.write_allowed
    effective_live_writes = bool(enabled_live_writes) and live_gate_allowed
    _phase_log(
        f"LIVE_WRITE_GATE sku={sku} writer_mode={writer_mode} "
        f"allowed={'1' if effective_live_writes else '0'} reason={live_gate_reason}",
    )

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
    if (phase_engine_enabled or phase_engine_shadow) and not phase_behavior_excluded:
        phase_shadow = phase1_phase_engine.compute_and_persist_shadow(
            sku=sku,
            now_utc=event_ts,
            enabled_flag=phase_engine_enabled,
            shadow_flag=phase_engine_shadow,
            current_price_gbp=current_price_gbp,
            hard_floor_gbp=hard_floor_gbp,
            best_rival_effective_gbp=_money(best_rival_effective),
        )
        phase_reasons = ",".join(phase_shadow.reason_codes)
        _phase_log(
            f"PHASE_SHADOW sku={sku} phase={phase_shadow.computed_phase} "
            f"changed={'1' if phase_shadow.phase_changed_this_cycle else '0'} reasons=[{phase_reasons}]"
        )
        phase_behavior_phase = int(getattr(phase_shadow, "computed_phase", 0) or 0)
    elif phase_behavior_excluded:
        _phase_log(f"PHASE_BEHAVIOR_SKIPPED_EXCLUDED sku={sku}")
    reason_codes: list[str] = []
    refresh_attempted_count = "0"
    refresh_throttled_count = "0"
    blocked_due_to_missing_intel = "0"
    blocked_due_to_stale_intel = "0"
    daily_intel = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
    suppression_memory = phase1_storage.read_by_keys("suppression_threshold_memory", {"sku": sku}) or {
        "sku": sku,
        "highest_eligible_price": "",
        "lowest_ineligible_price": "",
        "suppression_threshold_estimate": "",
        "suppression_threshold_confidence": "0",
        "suppression_last_validated_utc": "",
        "anchor_floor_price": "",
        "suppression_ceiling_landed_temp": "",
        "suppression_ceiling_expiry_utc": "",
        "last_buy_box_state": "",
        "updated_utc": "",
    }
    buy_box_present = "1" if str(snap.featured_offer_price_gbp or "").strip() else "0"
    buy_box_state = str(getattr(snap, "buy_box_state", "UNKNOWN") or "UNKNOWN").strip().upper()
    buy_box_eligible_offers = str(getattr(snap, "buy_box_eligible_offers", "") or "")
    outcome_known = "0" if buy_box_state == "UNKNOWN" else "1"
    we_present = "1" if any(str(r.get("is_our_offer", "")).strip() == "1" for r in pricing_rows) else "0"
    if we_present != "1" and str(current_price_gbp or "").strip():
        we_present = "1"
    suppression_active = buy_box_state in {"SUPPRESSED_ASIN", "DISQUALIFIED_SELF_PRICE"}
    current_price_dec = _to_decimal(current_price_gbp)
    hard_floor_dec = _to_decimal(hard_floor_gbp)
    stale_intel_floor_seek_state = ""
    if (
        phase_engine_enabled
        and phase_engine_behavior
        and not phase_behavior_excluded
        and phase_behavior_in_cohort
        and not suppression_active
    ):
        phase_state_candidate = _cannot_compete_phase_state(phase=phase_behavior_phase)
        if (
            phase_state_candidate
            and current_price_dec is not None
            and hard_floor_dec is not None
            and current_price_dec > hard_floor_dec
        ):
            stale_intel_floor_seek_state = phase_state_candidate
    hold_buy_box_missing = buy_box_present != "1" and not suppression_active
    hold_outcome_unknown = outcome_known != "1"
    hold_we_not_present = we_present != "1"
    observable = not (hold_buy_box_missing or hold_outcome_unknown or hold_we_not_present)
    allowed_to_act_count = 1 if observable else 0
    reason_codes.append(f"BUY_BOX_STATE_{buy_box_state}")
    reason_codes.extend(getattr(snap, "pricing_health_reason_codes", []))
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

    degraded_floor_seek_allowed = False
    if daily_intel_status != "FRESH":
        if daily_intel_status == "STALE":
            reason_codes.append("DAILY_INTEL_STALE")
            blocked_due_to_stale_intel = "1"
        else:
            reason_codes.append("DAILY_INTEL_MISSING")
            blocked_due_to_missing_intel = "1"
        if stale_intel_floor_seek_state:
            degraded_floor_seek_allowed = True
            reason_codes.append("DAILY_INTEL_DEGRADED_FLOOR_SEEK_ALLOWED")
        else:
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
    parked_gate_blocked = parked_flag
    cpt_risk_band = str(daily_intel.get("cpt_risk_band", "") or "").strip().upper() or "UNKNOWN"
    if parked_gate_blocked:
        reason_codes.append("PARKED_NO_ACTION")
        allowed_to_act_count = 0

    compliance_ceiling = str(daily_intel.get("compliance_ceiling_landed_gbp", "") or "")
    eligibility_ceiling = str(daily_intel.get("eligibility_ceiling_landed_gbp", "") or "")
    competitive_price_threshold_gbp = str(daily_intel.get("competitive_price_threshold_gbp", "") or "")
    competitive_price_gbp = str(daily_intel.get("competitive_price_gbp", "") or "")
    average_selling_price_gbp = str(daily_intel.get("average_selling_price_gbp", "") or "")
    anchor_floor_price_gbp = _max_money(
        hard_floor_gbp,
        daily_intel.get("anchor_floor_price_gbp", ""),
        suppression_memory.get("anchor_floor_price", ""),
    )
    ceiling_rule_value = str(daily_intel.get("ceiling_rule_value_gbp", "") or "").strip()
    ceiling_rule_source = str(daily_intel.get("ceiling_source_used", "") or "").strip().upper()
    ceiling_inputs_missing_flag = str(daily_intel.get("ceiling_inputs_missing_flag", "0") or "0").strip() == "1"
    ceiling_reason_codes_extra: list[str] = []
    no_buy_box_offer_present = not any(
        str(row.get("is_featured_offer_winner", "")).strip() == "1"
        for row in pricing_rows
    ) and not str(snap.featured_offer_winner_seller_id or "").strip()
    suppression_plan = phase1_ceilings.resolve_suppression_reactivation_target(
        buy_box_state=buy_box_state,
        now_utc=event_ts,
        competitive_price_threshold_gbp=competitive_price_threshold_gbp,
        competitive_price_gbp=competitive_price_gbp,
        average_selling_price_gbp=average_selling_price_gbp,
        foep_price_gbp=daily_intel.get("foep_price_gbp", ""),
        probe_threshold_estimate_gbp=suppression_memory.get("suppression_threshold_estimate", ""),
        existing_final_ceiling_landed_gbp=ceiling_rule_value or eligibility_ceiling or compliance_ceiling or manual_cap_gbp,
        anchor_floor_price_gbp=anchor_floor_price_gbp,
        hard_floor_gbp=hard_floor_gbp,
        probe_ceiling_candidate_gbp=(
            suppression_memory.get("lowest_ineligible_price", "")
            or (str(current_price_gbp or "").strip() if suppression_active else "")
        ),
        best_competitor_price_gbp=_money(best_rival),
        no_buy_box_offer_present="1" if no_buy_box_offer_present else "0",
        current_suppression_ceiling_landed_temp=suppression_memory.get("suppression_ceiling_landed_temp", ""),
        current_suppression_ceiling_expiry_utc=suppression_memory.get("suppression_ceiling_expiry_utc", ""),
    )

    if ceiling_rule_value:
        final_ceiling = phase1_ceilings.compute_final_ceiling(
            compliance_ceiling_landed_gbp=ceiling_rule_value,
            eligibility_ceiling_landed_gbp=ceiling_rule_value,
            manual_cap_gbp=ceiling_rule_value,
            suppression_ceiling_landed_temp=suppression_plan.suppression_ceiling_landed_temp,
        )
        if ceiling_rule_source:
            ceiling_reason_codes_extra.append(f"CEILING_RULE_SOURCE_{ceiling_rule_source}")
        ceiling_reason_codes_extra.append("CEILING_RULE_BBP_CPT_APPLIED")
    else:
        final_ceiling = phase1_ceilings.compute_final_ceiling(
            compliance_ceiling_landed_gbp=compliance_ceiling,
            eligibility_ceiling_landed_gbp=eligibility_ceiling,
            manual_cap_gbp=manual_cap_gbp,
            suppression_ceiling_landed_temp=suppression_plan.suppression_ceiling_landed_temp,
        )
        if ceiling_inputs_missing_flag:
            ceiling_reason_codes_extra.append("CEILING_RULE_INPUTS_MISSING")

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
                "suppression_ceiling_landed_temp": final_ceiling.suppression_ceiling_landed_temp,
                "demand_ceiling_landed_gbp": final_ceiling.demand_ceiling_landed_gbp,
                "final_ceiling_landed_gbp": final_ceiling.final_ceiling_landed_gbp,
                "binding_ceiling_type": final_ceiling.binding_ceiling_type,
                "ceiling_reason_codes_json": _json_compact(final_ceiling.reason_codes + ceiling_reason_codes_extra + suppression_plan.reason_codes),
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
        buy_box_state=buy_box_state,
    )
    hard_floor_for_decision = str(hard_floor_gbp or "")
    max_step_down_for_decision = str(max_step_down_gbp or "")
    best_rival_for_decision = _money(best_rival)
    phase_behavior_reason = ""
    phase_behavior_active = False
    phase_floor_seek_state = ""
    if phase_engine_behavior and phase_engine_enabled and not phase_behavior_excluded:
        if phase_behavior_in_cohort:
            exit_floor_price = str(daily_intel.get("exit_floor_price_gbp", "") or "")
            if not exit_floor_price and phase_behavior_phase >= 3:
                exit_floor_price = hard_floor_for_decision
            profile = phase1_phase_engine.resolve_behavior_profile(
                phase=phase_behavior_phase,
                current_max_step_down_gbp=max_step_down_for_decision,
                hard_floor_gbp=hard_floor_for_decision,
                exit_floor_price_gbp=exit_floor_price,
            )
            hard_floor_for_decision = profile.active_floor_gbp or hard_floor_for_decision
            if phase_behavior_phase == 1:
                max_step_down_for_decision = ""
            else:
                max_step_down_for_decision = profile.max_step_down_gbp or max_step_down_for_decision
            rival_dec = _to_decimal(best_rival_for_decision)
            bias_dec = _to_decimal(profile.undercut_bias_gbp) or _to_decimal("0")
            if phase_behavior_phase == 1 and rival_dec is not None:
                pct_bias_dec = rival_dec * Decimal("0.003")
                if pct_bias_dec > bias_dec:
                    bias_dec = pct_bias_dec
            if rival_dec is not None and bias_dec is not None:
                biased = rival_dec - bias_dec
                best_rival_for_decision = _money(biased)
            soft_floor_relax_dec = _to_decimal(profile.soft_floor_relax_pct) or _to_decimal("0")
            floor_dec = _to_decimal(hard_floor_for_decision)
            if phase_behavior_phase >= 2:
                phase_floor_seek_state = _cannot_compete_phase_state(phase=phase_behavior_phase)
            if phase_behavior_phase == 1 and floor_dec is not None and soft_floor_relax_dec is not None:
                floor_dec = _phase1_relaxed_floor_gbp(
                    sku=sku,
                    hard_floor=floor_dec,
                    soft_floor_relax_pct=soft_floor_relax_dec,
                )
                hard_floor_for_decision = _money(floor_dec)
            phase_behavior_active = True
            phase_behavior_reason = "PHASE_BEHAVIOR_APPLIED"
            _phase_log(
                f"PHASE_BEHAVIOR_APPLIED sku={sku} phase={profile.phase} "
                f"undercut_bias_gbp={profile.undercut_bias_gbp} "
                f"max_step_down_gbp={'NO_CAP' if phase_behavior_phase == 1 else profile.max_step_down_gbp} "
                f"soft_floor_relax_pct={profile.soft_floor_relax_pct} "
                f"active_floor_gbp={hard_floor_for_decision}"
            )
        else:
            phase_behavior_reason = "PHASE_BEHAVIOR_SKIPPED_NOT_IN_COHORT"
            _phase_log(f"PHASE_BEHAVIOR_SKIPPED_NOT_IN_COHORT sku={sku}")
    elif phase_behavior_excluded:
        phase_behavior_reason = "PHASE_BEHAVIOR_SKIPPED_EXCLUDED"

    active_floor_dec = _to_decimal(hard_floor_for_decision)
    cannot_compete_floor_seek_active = bool(
        phase_floor_seek_state
        and not suppression_active
        and current_price_dec is not None
        and active_floor_dec is not None
        and current_price_dec > active_floor_dec
    )
    if (
        cannot_compete_floor_seek_active
        and state_result.state != "STATE_SUPPRESSION_REACTIVATION"
        and state_result.state != phase_floor_seek_state
    ):
        floor_seek_reasons = list(state_result.reason_codes)
        floor_seek_reasons.append(f"PHASE_{phase_behavior_phase}_CANNOT_COMPETE_EXECUTION_OVERRIDE")
        if degraded_floor_seek_allowed:
            floor_seek_reasons.append("DAILY_INTEL_DEGRADED_FLOOR_SEEK")
        state_result = phase1_probe_engine.ProbeStateResult(
            state=phase_floor_seek_state,
            featured_outcome=state_result.featured_outcome,
            learning_blocked=True,
            reason_codes=floor_seek_reasons,
        )

    decision = phase1_probe_engine.choose_next_price(
        state=state_result.state,
        current_price_gbp=current_price_gbp,
        hard_floor_gbp=hard_floor_for_decision,
        final_ceiling_landed_gbp=final_ceiling.final_ceiling_landed_gbp,
        max_step_down_gbp=max_step_down_for_decision,
        max_step_up_gbp=max_step_up_gbp,
        max_daily_drop_gbp=max_daily_drop_gbp,
        daily_drop_used_gbp=daily_drop_used_gbp,
        highest_delta_win_effective_gbp=memory.get("highest_delta_win_effective_gbp", ""),
        lowest_delta_loss_effective_gbp=memory.get("lowest_delta_loss_effective_gbp", ""),
        best_rival_effective_price_gbp=best_rival_for_decision,
        stable_buffer_gbp=stable_buffer_gbp,
        suppression_reactivation_target_landed_gbp=suppression_plan.suppression_reactivation_target_landed_gbp,
        anchor_floor_gbp=anchor_floor_price_gbp,
        suppression_threshold_estimate_gbp=suppression_memory.get("suppression_threshold_estimate", ""),
        suppression_threshold_upper_bound_gbp=suppression_plan.suppression_threshold_upper_bound_gbp,
    )

    decision_effective = decision
    current_dec = _to_decimal(current_price_gbp)
    target_dec = _to_decimal(decision.target_price_gbp)
    if (
        current_dec is not None
        and target_dec is not None
        and target_dec > current_dec
        and ceiling_inputs_missing_flag
    ):
        decision_effective = phase1_probe_engine.NextPriceDecision(
            state="HOLD_OBSERVE",
            target_price_gbp=decision.target_price_gbp,
            write_required=False,
            reason_codes=decision.reason_codes + ["CEILING_RULE_INPUTS_MISSING_UPWARD_BLOCK"],
        )
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
    if reentry_price_discovery_active:
        competitor_dec = _to_decimal(_money(best_rival_effective))
        ceiling_dec = _to_decimal(final_ceiling.final_ceiling_landed_gbp)
        candidates = [d for d in (competitor_dec, ceiling_dec) if d is not None and d > 0]
        if candidates:
            reentry_target_dec = min(candidates)
            reentry_target = _money(reentry_target_dec)
            write_required = bool(
                current_dec is None
                or abs(reentry_target_dec - current_dec) >= Decimal("0.01")
            )
            reentry_reasons = list(decision_effective.reason_codes)
            reentry_reasons.append("REENTRY_PRICE_DISCOVERY_ACTIVE")
            if reentry_event:
                reentry_reasons.append("REENTRY_PRICE_DISCOVERY")
            decision_effective = phase1_probe_engine.NextPriceDecision(
                state="REENTRY_PRICE_DISCOVERY",
                target_price_gbp=reentry_target,
                write_required=write_required,
                reason_codes=reentry_reasons,
            )
            _phase_log(
                f"REENTRY_PRICE_DISCOVERY sku={sku} "
                f"target_price_gbp={reentry_target} "
                f"competitor_price_gbp={_money(best_rival_effective)} "
                f"ceiling_price_gbp={final_ceiling.final_ceiling_landed_gbp}"
            )
    if inbound_price_discovery_active:
        competitor_dec = _to_decimal(_money(best_rival_effective))
        ceiling_dec = _to_decimal(final_ceiling.final_ceiling_landed_gbp)
        candidates = [d for d in (competitor_dec, ceiling_dec) if d is not None and d > 0]
        if candidates:
            inbound_target_dec = min(candidates)
            inbound_target = _money(inbound_target_dec)
            write_required = bool(
                current_dec is None
                or abs(inbound_target_dec - current_dec) >= Decimal("0.01")
            )
            inbound_reasons = list(decision_effective.reason_codes)
            inbound_reasons.append("INBOUND_PRICE_DISCOVERY")
            decision_effective = phase1_probe_engine.NextPriceDecision(
                state="INBOUND_DISCOVERY",
                target_price_gbp=inbound_target,
                write_required=write_required,
                reason_codes=inbound_reasons,
            )
            _phase_log(
                f"INBOUND_DISCOVERY sku={sku} "
                f"target_price_gbp={inbound_target} "
                f"competitor_price_gbp={_money(best_rival_effective)} "
                f"ceiling_price_gbp={final_ceiling.final_ceiling_landed_gbp}"
            )

    write_status = "NO_WRITE_REQUIRED"
    write_error = ""
    probe_id = ""
    attempted_write = "0"
    wrote = "0"
    reason_codes.extend(
        state_result.reason_codes
        + decision_effective.reason_codes
        + final_ceiling.reason_codes
        + ceiling_reason_codes_extra
        + suppression_plan.reason_codes
    )
    if phase_behavior_reason:
        reason_codes.append(phase_behavior_reason)
    reason_codes.append(live_gate_reason)
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
    elif decision_effective.write_required and parked_gate_blocked:
        write_status = "READ_ONLY_NO_WRITE"
        write_error = "parked_no_action"
    elif decision_effective.write_required and writer_lock_blocked:
        write_status = "READ_ONLY_NO_WRITE"
        write_error = (
            f"writer_lock_block mode={writer_mode or 'UNKNOWN'} requires=CODEX_H"
            if invalid_writer_mode
            else ""
        )
    elif decision_effective.write_required and effective_live_writes and write_submitter is not None:
        attempted_write = "1"
        _phase_log(
            f"WRITE_INTENT sku={sku} allowed={'1' if live_gate_allowed else '0'} "
            f"writer_mode={writer_mode} in_cohort={'1' if phase_behavior_in_cohort else '0'} "
            f"excluded={'1' if phase_behavior_excluded else '0'} "
            f"flag_live={'1' if phase_engine_live_writes else '0'} "
            f"effective_live_writes={'1' if effective_live_writes else '0'}"
        )
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
            post_write_observed_price_lookup=post_write_observed_price_lookup,
            post_write_verify_attempts=18 if decision_effective.state == "STATE_SUPPRESSION_REACTIVATION" else 3,
            post_write_verify_sleep_seconds=5.0 if decision_effective.state == "STATE_SUPPRESSION_REACTIVATION" else 2.0,
            now_utc=event_ts,
        )
        write_status = write_result.write_status
        write_error = write_result.write_error
        probe_id = write_result.probe_id
        reason_codes.extend(write_result.reason_codes)
        if write_status == "APPLIED":
            wrote = "1"
    elif decision_effective.write_required and not effective_live_writes:
        write_status = "READ_ONLY_NO_WRITE"
        reason_codes.append("LIVE_WRITES_DISABLED")

    _append_phase_write_audit(
        {
            "ts_utc": event_ts,
            "sku": sku,
            "allowed": "1" if live_gate_allowed else "0",
            "writer_mode": writer_mode,
            "in_cohort": "1" if phase_behavior_in_cohort else "0",
            "excluded": "1" if phase_behavior_excluded else "0",
            "flag_live": "1" if phase_engine_live_writes else "0",
            "effective_live_writes": "1" if effective_live_writes else "0",
            "attempted_write": attempted_write,
            "wrote": wrote,
        }
    )

    suppression_update_allowed = "1" if suppression_active and not _is_truthy(promo_suspected_flag) and not writer_lock_blocked else "0"
    suppression_memory_update = phase1_probe_engine.update_suppression_memory(
        current_memory=suppression_memory,
        observed_price_gbp=current_price_gbp,
        buy_box_state=buy_box_state,
        buy_box_eligible_offers=buy_box_eligible_offers,
        direct_target_gbp=suppression_plan.suppression_reactivation_target_landed_gbp,
        anchor_floor_gbp=anchor_floor_price_gbp,
        now_utc=event_ts,
        update_allowed_flag=suppression_update_allowed if suppression_active else "1",
    )
    if suppression_active or suppression_memory_update.learning_updated or str(suppression_memory.get("last_buy_box_state", "")).strip().upper() in {"SUPPRESSED_ASIN", "DISQUALIFIED_SELF_PRICE"}:
        phase1_storage.upsert_suppression_threshold_memory(
            [
                {
                    "sku": sku,
                    "highest_eligible_price": suppression_memory_update.highest_eligible_price,
                    "lowest_ineligible_price": suppression_memory_update.lowest_ineligible_price,
                    "suppression_threshold_estimate": suppression_memory_update.suppression_threshold_estimate,
                    "suppression_threshold_confidence": suppression_memory_update.suppression_threshold_confidence,
                    "suppression_last_validated_utc": suppression_memory_update.suppression_last_validated_utc,
                    "anchor_floor_price": anchor_floor_price_gbp,
                    "suppression_ceiling_landed_temp": suppression_plan.suppression_ceiling_landed_temp,
                    "suppression_ceiling_expiry_utc": suppression_plan.suppression_ceiling_expiry_utc,
                    "last_buy_box_state": buy_box_state,
                    "updated_utc": event_ts,
                }
            ]
        )
    if suppression_active:
        suppression_case_id = f"{sku}-{event_ts.replace(':', '').replace('-', '')}"
        phase1_storage.append_suppression_cases(
            [
                {
                    "event_ts_utc": event_ts,
                    "sku": sku,
                    "asin": asin,
                    "suppression_case_id": suppression_case_id,
                    "buy_box_state": buy_box_state,
                    "buy_box_eligible_offers": buy_box_eligible_offers,
                    "pricing_health_active_flag": getattr(snap, "pricing_health_active_flag", "0"),
                    "pricing_health_disqualified_flag": getattr(snap, "pricing_health_disqualified_flag", "0"),
                    "suppression_target_source": suppression_plan.suppression_target_source,
                    "suppression_reactivation_target_landed_gbp": suppression_plan.suppression_reactivation_target_landed_gbp,
                    "suppression_ceiling_landed_temp": suppression_plan.suppression_ceiling_landed_temp,
                    "suppression_ceiling_expiry_utc": suppression_plan.suppression_ceiling_expiry_utc,
                    "anchor_floor_price": anchor_floor_price_gbp,
                    "action": decision_effective.state,
                    "notes": "|".join(suppression_memory_update.reason_codes + suppression_plan.reason_codes),
                }
            ]
        )
        phase1_storage.append_suppression_reactivation_log(
            [
                {
                    "event_ts_utc": event_ts,
                    "sku": sku,
                    "asin": asin,
                    "buy_box_state": buy_box_state,
                    "state": decision_effective.state,
                    "current_price_gbp": str(current_price_gbp or ""),
                    "target_price_gbp": decision_effective.target_price_gbp,
                    "suppression_target_source": suppression_plan.suppression_target_source,
                    "suppression_reactivation_target_landed_gbp": suppression_plan.suppression_reactivation_target_landed_gbp,
                    "suppression_ceiling_landed_temp": suppression_plan.suppression_ceiling_landed_temp,
                    "anchor_floor_price": anchor_floor_price_gbp,
                    "write_status": write_status,
                    "reason_codes_json": _json_compact(reason_codes + suppression_memory_update.reason_codes),
                }
            ]
        )

    action = "HOLD"
    if write_status == "APPLIED":
        action = "WRITE"
    elif decision_effective.write_required and allowed_to_act_count == 1 and not parked_gate_blocked:
        action = "PROPOSED_WRITE"
    blocker_reasons: list[str] = []
    if parked_gate_blocked:
        blocker_reasons.append("parked_no_action")
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
                pricing_health_suppressed_flag="1" if _is_truthy(pricing_health_suppressed_flag) or buy_box_state in {"SUPPRESSED_ASIN", "DISQUALIFIED_SELF_PRICE"} or getattr(snap, "pricing_health_disqualified_flag", "0") == "1" else "0",
                our_purchasable_flag=our_purchasable_flag,
                our_purchasable_reliable_flag=our_purchasable_reliable_flag,
                featured_winner_delivery_unknown_flag="1" if end_featured_winner_delivery_unknown else "0",
                suppression_active_flag="1" if suppression_active else "0",
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
            learning_blocked_phase_transition = bool(
                phase_engine_enabled
                and not phase_behavior_excluded
                and phase_shadow is not None
                and bool(getattr(phase_shadow, "phase_changed_this_cycle", False))
            )
            if learning_blocked_phase_transition:
                reason_codes.append("LEARNING_BLOCKED_PHASE_TRANSITION")
                _phase_log(f"LEARNING_GUARD sku={sku} reason=LEARNING_BLOCKED_PHASE_TRANSITION")
            if suppression_active:
                reason_codes.append("LEARNING_BLOCKED_SUPPRESSION_WINDOW")
            if observable and not floor_ceiling_conflict and not learning_blocked_phase_transition and not suppression_active:
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

