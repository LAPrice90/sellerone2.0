from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Mapping

import pandas as pd

from scripts.phase1 import phase1_storage

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

SALES_VELOCITY_PATH = OUT / "sku_sales_velocity.csv"
INVENTORY_SUMMARY_PATH = OUT / "inventory_summaries.csv"
INVENTORY_LEDGER_PATH = OUT / "inventory_ledger_raw.csv"

# v1.1 defaults from strategy blueprint.
GRACE_PERIOD_DAYS = 14
PHASE_TRIGGER_DAYS = {1: 21, 2: 35, 3: 60, 4: 90}
MINIMUM_DAYS_IN_PHASE = 14
BELOW_FLOOR_SUSTAIN_DAYS = 14
COMPETITIVE_TEST_WINDOW_DAYS = 14
VELOCITY_THRESHOLD_14D = 2.0
RECOVERY_VELOCITY_THRESHOLD_14D = 4.0
RECOVERY_SUSTAIN_DAYS = 14
PRICE_GAP_LARGE_THRESHOLD_PCT = 0.15
STOCK_RISK_THRESHOLD = 60
ESTIMATED_STORAGE_COST_PER_DAY = 0.0
COST_PRESSURE_THRESHOLD = 0.0

PHASE_REASON_CODES: tuple[str, ...] = (
    "PHASE_ENGINE_SHADOW_ACTIVE",
    "PHASE_ENGINE_ENABLED_NO_BEHAVIOUR_CHANGE",
    "PHASE_INPUTS_PARTIAL",
    "PHASE_INITIALIZED_P1",
    "PHASE_FROZEN_OUT_OF_STOCK",
    "PHASE_ESCALATION_DISABLED_GRACE_PERIOD",
    "PHASE_FAST_TRACK_BELOW_FLOOR",
    "PHASE_TIME_TRIGGER_ELIGIBLE",
    "PHASE_COMPETITIVE_TEST_LOCK_P1",
    "PHASE_INVENTORY_ACCELERATION_APPLIED",
    "PHASE_CAP_APPLIED_P4",
    "PHASE_LOCK_BLOCKED_DOWNGRADE",
    "PHASE_RECOVERY_DOWNGRADE",
    "PHASE_TRANSITION_RECORDED",
    "PHASE_STATE_UPDATED_NO_TRANSITION",
    "PHASE_GO_LIVE_RESEED_APPLIED",
)

_velocity_cache: dict[str, float] | None = None
_inventory_cache: dict[str, float] | None = None
_restock_cache: tuple[float, dict[str, datetime]] | None = None
_sku_list_cache: dict[str, tuple[float, set[str]]] = {}


@dataclass(frozen=True)
class PhaseEvalResult:
    computed_phase: int
    phase_changed_this_cycle: bool
    reason_codes: list[str]
    diagnostics_snapshot_json: str
    diagnostics_snapshot: dict[str, object]


@dataclass(frozen=True)
class PhaseBehaviorProfile:
    phase: int
    undercut_bias_gbp: str
    max_step_down_gbp: str
    active_floor_gbp: str
    soft_floor_relax_pct: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _to_float(value: object) -> float | None:
    try:
        raw = str(value or "").strip()
        if not raw:
            return None
        out = float(raw)
        if out != out:
            return None
        return out
    except Exception:
        return None


def _to_decimal(value: object) -> Decimal | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def _money(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _resolve_path(path_value: str) -> Path:
    p = Path(path_value)
    if not p.is_absolute():
        p = ROOT / p
    return p


def load_sku_csv(path_value: str) -> set[str]:
    path = _resolve_path(path_value)
    if not path.exists():
        return set()
    mtime = path.stat().st_mtime
    key = str(path).lower()
    cached = _sku_list_cache.get(key)
    if cached is not None and cached[0] == mtime:
        return set(cached[1])
    out: set[str] = set()
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, engine="python")
    except Exception:
        _sku_list_cache[key] = (mtime, out)
        return out
    if frame.empty:
        _sku_list_cache[key] = (mtime, out)
        return out
    columns = {str(col).strip().lower(): str(col) for col in frame.columns}
    sku_header = columns.get("sku", "")
    if not sku_header:
        _sku_list_cache[key] = (mtime, out)
        return out
    for sku in frame[sku_header].astype(str).tolist():
        sku_norm = str(sku or "").strip()
        if sku_norm:
            out.add(sku_norm)
    _sku_list_cache[key] = (mtime, out)
    return set(out)


def sku_in_csv(path_value: str, sku: str) -> bool:
    sku_norm = str(sku or "").strip()
    if not sku_norm:
        return False
    return sku_norm in load_sku_csv(path_value)


def resolve_behavior_profile(
    *,
    phase: int,
    current_max_step_down_gbp: object,
    hard_floor_gbp: object,
    exit_floor_price_gbp: object,
) -> PhaseBehaviorProfile:
    current_step = _to_decimal(current_max_step_down_gbp) or Decimal("0")
    hard_floor = _to_decimal(hard_floor_gbp) or Decimal("0")
    exit_floor = _to_decimal(exit_floor_price_gbp)
    active_floor = hard_floor
    bias = Decimal("0.00")
    soft_floor_relax = "0.00"
    max_step_out: Decimal | None = current_step

    if phase == 1:
        # Phase 1 undercut bias is computed dynamically in main loop using rival price:
        # max(0.05, rival_price * 0.003). Keep a minimum here for backward-compatible logs.
        bias = Decimal("0.05")
        # Explicitly no step-down cap in Phase 1.
        max_step_out = None
        # Reduce effective Phase 1 floor from 10% ROI to 7% ROI by relaxing
        # 30% of the margin component above break-even.
        soft_floor_relax = "0.30"
    elif phase == 2:
        bias = Decimal("0.10")
        max_step_out = min(current_step, Decimal("0.20"))
        soft_floor_relax = "0.00"
    elif phase == 3:
        bias = Decimal("0.15")
        max_step_out = min(current_step, Decimal("0.30"))
        if exit_floor is not None and exit_floor > 0:
            active_floor = exit_floor
    elif phase >= 4:
        bias = Decimal("0.20")
        max_step_out = min(current_step, Decimal("0.40"))
        if exit_floor is not None and exit_floor > 0:
            active_floor = exit_floor

    return PhaseBehaviorProfile(
        phase=phase,
        undercut_bias_gbp=_money(bias),
        max_step_down_gbp=_money(max_step_out),
        active_floor_gbp=_money(active_floor),
        soft_floor_relax_pct=soft_floor_relax,
    )


def _to_phase(value: object, default: int = 1) -> int:
    try:
        out = int(str(value or "").strip())
        return max(0, min(4, out))
    except Exception:
        return default


def _to_non_negative_int(value: object, default: int = 0) -> int:
    try:
        out = int(str(value or "").strip())
        if out < 0:
            return default
        return out
    except Exception:
        return default


def _to_dt(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _to_dt_flexible(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    dt = _to_dt(raw)
    if dt is not None:
        return dt
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _days_since(start: datetime, end: datetime) -> int:
    delta_days = (end.date() - start.date()).days
    return max(0, delta_days)


def _load_velocity_map() -> dict[str, float]:
    global _velocity_cache
    if _velocity_cache is not None:
        return _velocity_cache
    out: dict[str, float] = {}
    if not SALES_VELOCITY_PATH.exists():
        _velocity_cache = out
        return out
    try:
        frame = pd.read_csv(SALES_VELOCITY_PATH, dtype=str, keep_default_na=False, engine="python")
    except Exception:
        _velocity_cache = out
        return out
    for row in frame.to_dict("records"):
        sku = str(row.get("sku", "")).strip()
        if not sku:
            continue
        window_days = _to_float(row.get("window_days", ""))
        units_sold = _to_float(row.get("units_sold", ""))
        velocity_per_day = _to_float(row.get("velocity_units_per_day", ""))
        rolling_14 = None
        if window_days is not None and window_days > 0 and units_sold is not None:
            rolling_14 = (units_sold / window_days) * 14.0
        elif velocity_per_day is not None and velocity_per_day >= 0:
            rolling_14 = velocity_per_day * 14.0
        if rolling_14 is None:
            continue
        prev = out.get(sku)
        out[sku] = rolling_14 if prev is None else max(prev, rolling_14)
    _velocity_cache = out
    return out


def _load_inventory_map() -> dict[str, float]:
    global _inventory_cache
    if _inventory_cache is not None:
        return _inventory_cache
    out: dict[str, float] = {}
    if not INVENTORY_SUMMARY_PATH.exists():
        _inventory_cache = out
        return out
    try:
        frame = pd.read_csv(INVENTORY_SUMMARY_PATH, dtype=str, keep_default_na=False, engine="python")
    except Exception:
        _inventory_cache = out
        return out
    for row in frame.to_dict("records"):
        sku = str(row.get("seller_sku", "")).strip()
        if not sku:
            continue
        available = _to_float(row.get("available", ""))
        total_qty = _to_float(row.get("total_quantity", ""))
        qty = available if available is not None else total_qty
        if qty is None:
            continue
        out[sku] = qty
    _inventory_cache = out
    return out


def _load_last_restock_map() -> dict[str, datetime]:
    global _restock_cache
    if not INVENTORY_LEDGER_PATH.exists():
        _restock_cache = (0.0, {})
        return {}
    mtime = INVENTORY_LEDGER_PATH.stat().st_mtime
    if _restock_cache is not None and _restock_cache[0] == mtime:
        return _restock_cache[1]
    out: dict[str, datetime] = {}
    try:
        frame = pd.read_csv(INVENTORY_LEDGER_PATH, dtype=str, keep_default_na=False, engine="python")
    except Exception:
        _restock_cache = (mtime, out)
        return out
    for row in frame.to_dict("records"):
        sku = str(row.get("MSKU", "")).strip()
        if not sku:
            continue
        event_type = str(row.get("Event Type", "")).strip().lower()
        if "receipt" not in event_type:
            continue
        ts = _to_dt_flexible(row.get("Date and Time", "")) or _to_dt_flexible(row.get("Date", ""))
        if ts is None:
            continue
        prev = out.get(sku)
        if prev is None or ts > prev:
            out[sku] = ts
    _restock_cache = (mtime, out)
    return out


def _resolve_strategy_start_date(existing: Mapping[str, object] | None, event_ts: datetime) -> datetime:
    go_live_dt = _to_dt(os.environ.get("H_STRATEGY_GO_LIVE_UTC", ""))
    if go_live_dt is not None:
        return go_live_dt
    existing_dt = _to_dt((existing or {}).get("strategy_start_date", ""))
    if existing_dt is not None:
        return existing_dt
    return event_ts


def evaluate_phase(
    *,
    sku: str,
    now_utc: str,
    current_price_gbp: object,
    hard_floor_gbp: object,
    best_rival_effective_gbp: object,
) -> PhaseEvalResult:
    sku_norm = str(sku or "").strip()
    if not sku_norm:
        return PhaseEvalResult(0, False, ["PHASE_INPUTS_PARTIAL"], _json_compact({}), {})

    event_ts = _to_dt(now_utc) or _to_dt(_utc_now_iso()) or datetime.now(timezone.utc)
    existing = phase1_storage.read_by_keys("sku_phase_state", {"sku": sku_norm})
    current_phase = _to_phase((existing or {}).get("phase", ""), default=1)
    below_floor_streak_days = _to_non_negative_int((existing or {}).get("below_floor_streak_days", ""), default=0)
    recovery_streak_days = _to_non_negative_int((existing or {}).get("recovery_streak_days", ""), default=0)
    strategy_go_live_dt = _to_dt(os.environ.get("H_STRATEGY_GO_LIVE_UTC", ""))
    existing_strategy_start_dt = _to_dt((existing or {}).get("strategy_start_date", ""))
    strategy_go_live_reseed = (
        strategy_go_live_dt is not None
        and existing is not None
        and existing_strategy_start_dt is not None
        and existing_strategy_start_dt < strategy_go_live_dt
    )

    reason_codes: list[str] = []
    if existing is None:
        reason_codes.append("PHASE_INITIALIZED_P1")
    if strategy_go_live_reseed:
        current_phase = 1
        below_floor_streak_days = 0
        recovery_streak_days = 0
        reason_codes.append("PHASE_GO_LIVE_RESEED_APPLIED")

    strategy_start_dt = _resolve_strategy_start_date(existing, event_ts)
    days_under_new_strategy = _days_since(strategy_start_dt, event_ts) + 1

    velocity_map = _load_velocity_map()
    inventory_map = _load_inventory_map()
    restock_map = _load_last_restock_map()
    rolling_14d_units = velocity_map.get(sku_norm)
    current_stock_units = inventory_map.get(sku_norm)
    last_restock_dt = restock_map.get(sku_norm)
    if last_restock_dt is None:
        days_since_last_restock = GRACE_PERIOD_DAYS
    else:
        days_since_last_restock = _days_since(last_restock_dt, event_ts)

    current_price = _to_float(current_price_gbp)
    hard_floor = _to_float(hard_floor_gbp)
    best_rival = _to_float(best_rival_effective_gbp)
    below_floor_market = (
        best_rival is not None
        and hard_floor is not None
        and best_rival < hard_floor
    )
    previous_price_gap_large = (
        current_price is not None
        and best_rival is not None
        and best_rival > 0
        and abs(current_price - best_rival) / best_rival >= PRICE_GAP_LARGE_THRESHOLD_PCT
    )

    low_velocity = rolling_14d_units is not None and rolling_14d_units <= VELOCITY_THRESHOLD_14D
    recovery_velocity = rolling_14d_units is not None and rolling_14d_units >= RECOVERY_VELOCITY_THRESHOLD_14D

    in_grace_period = days_since_last_restock < GRACE_PERIOD_DAYS
    high_cost_pressure = False
    if current_stock_units is not None:
        storage_cost_pressure = current_stock_units * ESTIMATED_STORAGE_COST_PER_DAY
        high_cost_pressure = storage_cost_pressure > COST_PRESSURE_THRESHOLD
    else:
        reason_codes.append("PHASE_INPUTS_PARTIAL")

    computed_phase = current_phase
    escalation_allowed = True
    days_in_current_phase = 0
    phase_entered_dt = _to_dt((existing or {}).get("phase_entered_utc", ""))
    if strategy_go_live_reseed:
        phase_entered_dt = strategy_start_dt
    if phase_entered_dt is not None:
        days_in_current_phase = _days_since(phase_entered_dt, event_ts)

    in_stock = current_stock_units is None or current_stock_units > 0
    if in_stock:
        if below_floor_market:
            below_floor_streak_days += 1
        else:
            below_floor_streak_days = 0
        if recovery_velocity:
            recovery_streak_days += 1
        else:
            recovery_streak_days = 0

    # 1) Out-of-stock freeze
    if current_stock_units is not None and current_stock_units <= 0:
        reason_codes.append("PHASE_FROZEN_OUT_OF_STOCK")
    else:
        # 2) Grace period blocks escalation
        if in_grace_period:
            escalation_allowed = False
            reason_codes.append("PHASE_ESCALATION_DISABLED_GRACE_PERIOD")

        # 3) Market-impossible fast track (streak-based)
        if escalation_allowed and below_floor_streak_days >= BELOW_FLOOR_SUSTAIN_DAYS:
            computed_phase = max(computed_phase, 3)
            reason_codes.append("PHASE_FAST_TRACK_BELOW_FLOOR")

        # 4) Time-based triggers (days_under_new_strategy + low_velocity)
        if escalation_allowed and low_velocity:
            if days_under_new_strategy >= PHASE_TRIGGER_DAYS[4]:
                computed_phase = max(computed_phase, 4)
                reason_codes.append("PHASE_TIME_TRIGGER_ELIGIBLE")
            elif days_under_new_strategy >= PHASE_TRIGGER_DAYS[3]:
                computed_phase = max(computed_phase, 3)
                reason_codes.append("PHASE_TIME_TRIGGER_ELIGIBLE")
            elif days_under_new_strategy >= PHASE_TRIGGER_DAYS[2]:
                computed_phase = max(computed_phase, 2)
                reason_codes.append("PHASE_TIME_TRIGGER_ELIGIBLE")
            elif days_under_new_strategy >= PHASE_TRIGGER_DAYS[1]:
                computed_phase = max(computed_phase, 1)
                reason_codes.append("PHASE_TIME_TRIGGER_ELIGIBLE")

        # 5) Competitive test protection
        if previous_price_gap_large and days_under_new_strategy < COMPETITIVE_TEST_WINDOW_DAYS and computed_phase > 1:
            computed_phase = 1
            reason_codes.append("PHASE_COMPETITIVE_TEST_LOCK_P1")

        # 6) Inventory-pressure acceleration (piggybacks only on prior upward movement)
        upward_move_triggered = computed_phase > current_phase
        if upward_move_triggered and high_cost_pressure and not in_grace_period:
            computed_phase += 1
            reason_codes.append("PHASE_INVENTORY_ACCELERATION_APPLIED")

        # 7) Cap at phase 4
        if computed_phase > 4:
            computed_phase = 4
            reason_codes.append("PHASE_CAP_APPLIED_P4")

        # 8) Phase lock: block downgrade until minimum days in phase
        if computed_phase < current_phase and days_in_current_phase < MINIMUM_DAYS_IN_PHASE:
            computed_phase = current_phase
            reason_codes.append("PHASE_LOCK_BLOCKED_DOWNGRADE")

        # 9) Recovery downgrade
        if recovery_streak_days >= RECOVERY_SUSTAIN_DAYS and days_in_current_phase >= MINIMUM_DAYS_IN_PHASE and current_phase > 0:
            recovered_phase = max(current_phase - 1, 0)
            if recovered_phase < computed_phase:
                computed_phase = recovered_phase
            else:
                computed_phase = recovered_phase
            reason_codes.append("PHASE_RECOVERY_DOWNGRADE")

    changed = computed_phase != current_phase
    diag = {
        "sku": sku_norm,
        "strategy_start_date": strategy_start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days_under_new_strategy": days_under_new_strategy,
        "days_since_last_restock": days_since_last_restock,
        "grace_blocked": in_grace_period,
        "rolling_14d_units": rolling_14d_units if rolling_14d_units is not None else "",
        "below_floor_market": "1" if below_floor_market else "0",
        "current_stock_units": current_stock_units if current_stock_units is not None else "",
        "below_floor_streak_days": below_floor_streak_days,
        "recovery_streak_days": recovery_streak_days,
        "phase_prev": current_phase,
        "phase_new": computed_phase,
        "strategy_go_live_utc": strategy_start_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if strategy_go_live_dt is not None else "",
        "strategy_go_live_reseed": "1" if strategy_go_live_reseed else "0",
    }
    return PhaseEvalResult(
        computed_phase=computed_phase,
        phase_changed_this_cycle=changed,
        reason_codes=reason_codes,
        diagnostics_snapshot_json=_json_compact(diag),
        diagnostics_snapshot=diag,
    )


def compute_and_persist_shadow(
    *,
    sku: str,
    now_utc: str,
    enabled_flag: bool,
    shadow_flag: bool,
    current_price_gbp: object,
    hard_floor_gbp: object,
    best_rival_effective_gbp: object,
) -> PhaseEvalResult:
    result = evaluate_phase(
        sku=sku,
        now_utc=now_utc,
        current_price_gbp=current_price_gbp,
        hard_floor_gbp=hard_floor_gbp,
        best_rival_effective_gbp=best_rival_effective_gbp,
    )

    reasons = list(result.reason_codes)
    if enabled_flag:
        reasons.append("PHASE_ENGINE_ENABLED_NO_BEHAVIOUR_CHANGE")
    if shadow_flag:
        reasons.append("PHASE_ENGINE_SHADOW_ACTIVE")

    if not shadow_flag:
        return PhaseEvalResult(
            computed_phase=result.computed_phase,
            phase_changed_this_cycle=result.phase_changed_this_cycle,
            reason_codes=reasons,
            diagnostics_snapshot_json=result.diagnostics_snapshot_json,
            diagnostics_snapshot=result.diagnostics_snapshot,
        )

    phase1_storage.ensure_phase_engine_tables()
    event_ts = _to_dt(now_utc) or _to_dt(_utc_now_iso()) or datetime.now(timezone.utc)
    existing = phase1_storage.read_by_keys("sku_phase_state", {"sku": sku}) or {}
    prev_phase = _to_phase(existing.get("phase", ""), default=1)
    changed = result.computed_phase != prev_phase
    strategy_start_date = str(result.diagnostics_snapshot.get("strategy_start_date", "") or existing.get("strategy_start_date", ""))
    go_live_reseed = str(result.diagnostics_snapshot.get("strategy_go_live_reseed", "0")) == "1"
    phase_entered_utc = str(existing.get("phase_entered_utc", "") or event_ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
    if go_live_reseed:
        phase_entered_utc = strategy_start_date or event_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    elif changed or not existing:
        phase_entered_utc = event_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    phase_lock_until = str(existing.get("phase_lock_until_utc", ""))
    if go_live_reseed:
        phase_lock_until = ""
    elif changed:
        phase_lock_until = (event_ts + timedelta(days=MINIMUM_DAYS_IN_PHASE)).strftime("%Y-%m-%dT%H:%M:%SZ")
    phase_to_store = 1 if go_live_reseed else result.computed_phase
    changed = phase_to_store != prev_phase

    phase1_storage.upsert_sku_phase_state(
        {
            "sku": sku,
            "phase": str(phase_to_store),
            "phase_entered_utc": phase_entered_utc,
            "strategy_start_date": strategy_start_date,
            "phase_lock_until_utc": phase_lock_until,
            "below_floor_streak_days": str(
                0 if go_live_reseed else _to_non_negative_int(result.diagnostics_snapshot.get("below_floor_streak_days", 0), default=0)
            ),
            "recovery_streak_days": str(
                0 if go_live_reseed else _to_non_negative_int(result.diagnostics_snapshot.get("recovery_streak_days", 0), default=0)
            ),
            "last_transition_reason_codes_json": _json_compact(reasons),
            "updated_utc": event_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )

    if changed or not existing:
        reasons.append("PHASE_TRANSITION_RECORDED")
        phase1_storage.append_sku_phase_transition(
            {
                "event_ts_utc": event_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "sku": sku,
                "from_phase": "" if not existing else str(prev_phase),
                "to_phase": str(phase_to_store),
                "transition_reason_codes_json": _json_compact(reasons),
                "diagnostics_snapshot_json": result.diagnostics_snapshot_json,
            }
        )
    else:
        reasons.append("PHASE_STATE_UPDATED_NO_TRANSITION")

    return PhaseEvalResult(
        computed_phase=phase_to_store,
        phase_changed_this_cycle=changed,
        reason_codes=reasons,
        diagnostics_snapshot_json=result.diagnostics_snapshot_json,
        diagnostics_snapshot=result.diagnostics_snapshot,
    )
