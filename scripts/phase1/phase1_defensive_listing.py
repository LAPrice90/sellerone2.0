from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Mapping


SUPPORTED_MODES = {"pressure_then_match", "match_only", "off"}
LEGACY_MODE_ALIASES = {"balanced_defend": "pressure_then_match"}
AFTER_PRESSURE_ACTIONS = {"match", "normal_h_control"}
LIVE_WRITE_ALLOWLIST_SKUS = {"6V-EEC1-2S9Z"}
MAX_BALANCED_UNDERCUT_GBP = Decimal("0.01")
MONEY_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class DefensiveListingRule:
    sku: str
    asin: str
    enabled: bool
    mode: str
    live_write_enabled: bool
    pressure_days: int
    undercut_gbp: Decimal
    after_pressure_action: str
    reset_after_absent_hours: int
    min_margin_guard: Decimal
    notes: str = ""


@dataclass(frozen=True)
class DefensiveListingEvaluation:
    active: bool
    override_decision: bool
    state: str
    phase: str
    target_price_gbp: str
    write_required: bool
    live_write_enabled: bool
    reason_codes: list[str]
    memory_row: dict[str, str]


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_decimal(value: object) -> Decimal | None:
    raw = str(value or "").strip()
    if raw == "":
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP):.2f}"


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return default


def _parse_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _coerce_positive_int(row: Mapping[str, object], key: str, default: int) -> int | None:
    value = _safe_int(row.get(key, ""), default)
    if value < 0:
        return None
    return value


def _coerce_decimal(row: Mapping[str, object], key: str, default: Decimal) -> Decimal | None:
    raw = row.get(key, "")
    if str(raw or "").strip() == "":
        return default
    value = _to_decimal(raw)
    if value is None or value < Decimal("0"):
        return None
    return value


def _rule_from_row(row: Mapping[str, object]) -> DefensiveListingRule | None:
    sku = str(row.get("sku", "") or "").strip()
    asin = str(row.get("asin", "") or "").strip()
    if not sku or not asin:
        return None
    if not _truthy(row.get("enabled", "0")):
        return None
    mode_raw = str(row.get("mode", "") or "").strip().lower()
    mode = LEGACY_MODE_ALIASES.get(mode_raw, mode_raw)
    if mode not in SUPPORTED_MODES:
        return None
    live_write_enabled = _truthy(row.get("live_write_enabled", "0"))
    if live_write_enabled and sku not in LIVE_WRITE_ALLOWLIST_SKUS:
        return None

    undercut = _to_decimal(row.get("undercut_gbp", ""))
    if undercut is None or undercut < Decimal("0") or undercut > MAX_BALANCED_UNDERCUT_GBP:
        return None

    pressure_days = _coerce_positive_int(row, "pressure_days", _safe_int(row.get("match_after_days", ""), 30))
    after_pressure_action = str(row.get("after_pressure_action", "") or "").strip().lower() or "match"
    if after_pressure_action not in AFTER_PRESSURE_ACTIONS:
        return None
    reset_after_absent_hours = _coerce_positive_int(row, "reset_after_absent_hours", 24)
    min_margin_guard = _coerce_decimal(row, "min_margin_guard", Decimal("0"))
    if None in {pressure_days, reset_after_absent_hours} or min_margin_guard is None:
        return None
    if pressure_days == 0:
        return None

    return DefensiveListingRule(
        sku=sku,
        asin=asin,
        enabled=True,
        mode=mode,
        live_write_enabled=live_write_enabled,
        pressure_days=int(pressure_days),
        undercut_gbp=undercut,
        after_pressure_action=after_pressure_action,
        reset_after_absent_hours=int(reset_after_absent_hours),
        min_margin_guard=min_margin_guard,
        notes=str(row.get("notes", "") or "").strip(),
    )


def load_defensive_listing_rules(path: Path) -> dict[str, DefensiveListingRule]:
    if not path.exists():
        return {}
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return {}
    rules: dict[str, DefensiveListingRule] = {}
    for row in rows:
        rule = _rule_from_row(row)
        if rule is not None:
            rules[rule.sku] = rule
    return rules


def active_rule_for_sku(path: Path, sku: str) -> DefensiveListingRule | None:
    return load_defensive_listing_rules(path).get(str(sku or "").strip())


def _base_memory(
    *,
    rule: DefensiveListingRule,
    memory: Mapping[str, object],
    event_dt: datetime,
    phase: str,
    last_target_price_gbp: str,
    last_rival_price_gbp: str,
    last_action: str,
) -> dict[str, str]:
    write_date = str(memory.get("writes_date", "") or "").strip()
    today = event_dt.date().isoformat()
    writes_today = _safe_int(memory.get("writes_today", "0"), 0) if write_date == today else 0
    return {
        "sku": rule.sku,
        "asin": rule.asin,
        "mode": rule.mode,
        "campaign_started_utc": str(memory.get("campaign_started_utc", "") or "").strip(),
        "last_seen_rival_utc": str(memory.get("last_seen_rival_utc", "") or "").strip(),
        "last_absent_utc": str(memory.get("last_absent_utc", "") or "").strip(),
        "reset_count": str(_safe_int(memory.get("reset_count", "0"), 0)),
        "failed_defend_count": str(_safe_int(memory.get("failed_defend_count", "0"), 0)),
        "writes_date": today,
        "writes_today": str(writes_today),
        "cooldown_until_utc": str(memory.get("cooldown_until_utc", "") or "").strip(),
        "phase": phase,
        "last_target_price_gbp": last_target_price_gbp,
        "last_rival_price_gbp": last_rival_price_gbp,
        "last_action": last_action,
        "live_write_enabled": "1" if rule.live_write_enabled else "0",
        "updated_utc": _format_utc(event_dt),
    }


def _finish(
    *,
    rule: DefensiveListingRule,
    memory: Mapping[str, object],
    event_dt: datetime,
    state: str,
    phase: str,
    target_price_gbp: str,
    write_required: bool,
    reason_codes: list[str],
    lowest_rival_price_gbp: str,
    override_decision: bool = True,
) -> DefensiveListingEvaluation:
    memory_row = _base_memory(
        rule=rule,
        memory=memory,
        event_dt=event_dt,
        phase=phase,
        last_target_price_gbp=target_price_gbp,
        last_rival_price_gbp=lowest_rival_price_gbp,
        last_action=state,
    )
    if write_required and rule.live_write_enabled:
        memory_row["writes_today"] = str(_safe_int(memory_row.get("writes_today", "0"), 0) + 1)
    return DefensiveListingEvaluation(
        active=True,
        override_decision=override_decision,
        state=state,
        phase=phase,
        target_price_gbp=target_price_gbp,
        write_required=write_required,
        live_write_enabled=rule.live_write_enabled,
        reason_codes=reason_codes,
        memory_row=memory_row,
    )


def evaluate_defensive_listing(
    *,
    rule: DefensiveListingRule,
    memory: Mapping[str, object] | None,
    event_ts_utc: str,
    buy_box_state: str,
    seller_count: int,
    lowest_rival_price_gbp: object,
    current_price_gbp: object,
    hard_floor_gbp: object,
    final_ceiling_gbp: object,
    max_step_down_gbp: object,
    max_step_up_gbp: object,
    observable: bool,
    we_present: bool,
) -> DefensiveListingEvaluation:
    memory_map: Mapping[str, object] = memory or {}
    event_dt = _parse_utc(event_ts_utc) or datetime.now(timezone.utc)
    reasons = ["DEFENSIVE_LISTING_ACTIVE", f"DEFENSIVE_LISTING_MODE_{rule.mode.upper()}"]
    current = _to_decimal(current_price_gbp)
    floor = _to_decimal(hard_floor_gbp)
    ceiling = _to_decimal(final_ceiling_gbp)
    rival = _to_decimal(lowest_rival_price_gbp)

    hold_target = _money(current)
    if not observable:
        reasons.append("DEFENSIVE_LISTING_HOLD_STALE_OR_UNPROVEN_MARKET")
        return _finish(
            rule=rule,
            memory=memory_map,
            event_dt=event_dt,
            state="DEFENSIVE_LISTING_HOLD",
            phase="proof_hold",
            target_price_gbp=hold_target,
            write_required=False,
            reason_codes=reasons,
            lowest_rival_price_gbp=str(lowest_rival_price_gbp or ""),
        )
    if not we_present:
        reasons.append("DEFENSIVE_LISTING_HOLD_OWN_OFFER_MISSING")
        return _finish(
            rule=rule,
            memory=memory_map,
            event_dt=event_dt,
            state="DEFENSIVE_LISTING_HOLD",
            phase="proof_hold",
            target_price_gbp=hold_target,
            write_required=False,
            reason_codes=reasons,
            lowest_rival_price_gbp=str(lowest_rival_price_gbp or ""),
        )
    if current is None or floor is None or ceiling is None:
        reasons.append("DEFENSIVE_LISTING_HOLD_MISSING_PRICE_FLOOR_OR_CEILING")
        return _finish(
            rule=rule,
            memory=memory_map,
            event_dt=event_dt,
            state="DEFENSIVE_LISTING_HOLD",
            phase="proof_hold",
            target_price_gbp=hold_target,
            write_required=False,
            reason_codes=reasons,
            lowest_rival_price_gbp=str(lowest_rival_price_gbp or ""),
        )
    if floor > ceiling:
        reasons.append("DEFENSIVE_LISTING_HOLD_FLOOR_CEILING_CONFLICT")
        return _finish(
            rule=rule,
            memory=memory_map,
            event_dt=event_dt,
            state="DEFENSIVE_LISTING_HOLD",
            phase="proof_hold",
            target_price_gbp=_money(current),
            write_required=False,
            reason_codes=reasons,
            lowest_rival_price_gbp=str(lowest_rival_price_gbp or ""),
        )

    max_step_down = _to_decimal(max_step_down_gbp) or Decimal("0")

    if rule.mode == "off":
        reasons.append("DEFENSIVE_LISTING_MODE_OFF_NORMAL_H_CONTROL")
        return _finish(
            rule=rule,
            memory=memory_map,
            event_dt=event_dt,
            state="DEFENSIVE_LISTING_NOT_TRIGGERED",
            phase="normal_h_control",
            target_price_gbp="",
            write_required=False,
            override_decision=False,
            reason_codes=reasons,
            lowest_rival_price_gbp=str(lowest_rival_price_gbp or ""),
        )

    if seller_count <= 0 or rival is None:
        reasons.append("DEFENSIVE_LISTING_RIVAL_ABSENT_NORMAL_H_CONTROL")
        result = _finish(
            rule=rule,
            memory=memory_map,
            event_dt=event_dt,
            state="DEFENSIVE_LISTING_NOT_TRIGGERED",
            phase="normal_h_control",
            target_price_gbp="",
            write_required=False,
            override_decision=False,
            reason_codes=reasons,
            lowest_rival_price_gbp="",
        )
        result.memory_row["last_absent_utc"] = _format_utc(event_dt)
        return result

    buy_box_norm = str(buy_box_state or "").strip().upper()
    failed_count = _safe_int(memory_map.get("failed_defend_count", "0"), 0)
    previous_action = str(memory_map.get("last_action", "") or "").strip().upper()
    if buy_box_norm == "NORMAL":
        failed_count = 0
    elif previous_action == "DEFENSIVE_LISTING_BALANCED_DEFEND":
        failed_count += 1

    last_absent = _parse_utc(memory_map.get("last_absent_utc", ""))
    reset_after_seconds = max(rule.reset_after_absent_hours, 0) * 3600
    reset_after_absence = bool(
        last_absent is not None and (event_dt - last_absent).total_seconds() >= reset_after_seconds
    )
    campaign_started = event_dt if reset_after_absence else (_parse_utc(memory_map.get("campaign_started_utc", "")) or event_dt)
    campaign_age_days = max(int((event_dt - campaign_started).total_seconds() // 86400), 0)
    if reset_after_absence:
        reasons.append("DEFENSIVE_LISTING_RESET_AFTER_ABSENCE")
    if rule.mode == "match_only":
        undercut = Decimal("0")
        phase = "match_only"
        reasons.append("DEFENSIVE_LISTING_MATCH_ONLY")
    elif campaign_age_days < rule.pressure_days:
        undercut = rule.undercut_gbp
        phase = "pressure_undercut"
        reasons.append("DEFENSIVE_LISTING_PRESSURE_UNDERCUT")
    else:
        undercut = Decimal("0")
        if rule.after_pressure_action == "normal_h_control":
            reasons.append("DEFENSIVE_LISTING_AFTER_PRESSURE_NORMAL_H_CONTROL")
            result = _finish(
                rule=rule,
                memory={**dict(memory_map), "failed_defend_count": str(failed_count)},
                event_dt=event_dt,
                state="DEFENSIVE_LISTING_NOT_TRIGGERED",
                phase="normal_h_control",
                target_price_gbp="",
                write_required=False,
                override_decision=False,
                reason_codes=reasons,
                lowest_rival_price_gbp=_money(rival),
            )
            result.memory_row["campaign_started_utc"] = _format_utc(campaign_started)
            result.memory_row["last_seen_rival_utc"] = _format_utc(event_dt)
            return result
        phase = "match_after_pressure"
        reasons.append("DEFENSIVE_LISTING_AFTER_PRESSURE_MATCH")

    target = rival - undercut
    min_target = floor + rule.min_margin_guard
    if target < min_target:
        target = min_target
        reasons.append("DEFENSIVE_LISTING_MIN_MARGIN_GUARD_CLAMP")
    if target < floor:
        target = floor
        reasons.append("DEFENSIVE_LISTING_FLOOR_CLAMP")
    if target > ceiling:
        target = ceiling
        reasons.append("DEFENSIVE_LISTING_CEILING_CLAMP")
    if max_step_down > 0 and target < current - max_step_down:
        target = current - max_step_down
        if target < floor:
            target = floor
        reasons.append("DEFENSIVE_LISTING_STEP_DOWN_CLAMP")

    if target >= current and phase == "pressure_undercut":
        reasons.append("DEFENSIVE_LISTING_SINGLE_STRATEGY_OWNS_RIVAL_PRESENT")
        reasons.append("DEFENSIVE_LISTING_PRESSURE_POSITION_HELD")
        result = _finish(
            rule=rule,
            memory={**dict(memory_map), "failed_defend_count": str(failed_count)},
            event_dt=event_dt,
            state="DEFENSIVE_LISTING_HOLD",
            phase="pressure_hold",
            target_price_gbp=_money(current),
            write_required=False,
            reason_codes=reasons,
            lowest_rival_price_gbp=_money(rival),
        )
        result.memory_row["campaign_started_utc"] = _format_utc(campaign_started)
        result.memory_row["last_seen_rival_utc"] = _format_utc(event_dt)
        return result

    write_required = current - target >= MONEY_QUANT
    result = _finish(
        rule=rule,
        memory={**dict(memory_map), "failed_defend_count": str(failed_count)},
        event_dt=event_dt,
        state="DEFENSIVE_LISTING_BALANCED_DEFEND",
        phase=phase,
        target_price_gbp=_money(target),
        write_required=write_required,
        reason_codes=reasons,
        lowest_rival_price_gbp=_money(rival),
    )
    result.memory_row["campaign_started_utc"] = _format_utc(campaign_started)
    result.memory_row["last_seen_rival_utc"] = _format_utc(event_dt)
    result.memory_row["failed_defend_count"] = str(failed_count)
    return result
