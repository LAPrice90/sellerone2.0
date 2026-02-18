from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Dict, List

import pandas as pd

from h_head_boundaries import load_head_boundaries
from h_lab_cohort import load_active_lab_skus
from h_probe_logs import (
    PROBE_EVENT_LOG_PATH,
    PROBE_RESPONSE_LOG_PATH,
    append_probe_events,
    append_probe_responses,
    initialize_probe_logs,
    load_probe_event_log,
)
from h_supervisor_tactical_rules import load_active_supervisor_tactical_rules

OUT = Path("out")
SOURCE = "H007_run_safe_mode_pilot"
SAFE_MODE_ALLOWED_PROBES = {"hold", "match"}
RESPONSE_WINDOWS = [5, 15, 60, 240]
OFFICIAL_PILOT_SKU = os.environ.get("H_OFFICIAL_PILOT_SKU", "L1-54EX-56YC").strip().upper() or "L1-54EX-56YC"


def _norm(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _to_int(value: object) -> int | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return int(float(text))
    except Exception:
        return None


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _latest_listing_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        raise FileNotFoundError("No listing snapshot found: out/listing_offer_snapshot_YYYY-MM-DD.csv")
    return files[-1]


def _active_head_boundary_for_sku(sku: str) -> Dict[str, str]:
    boundaries = load_head_boundaries()
    if boundaries.empty:
        return {}
    enabled = boundaries.get("enabled", "").astype(str).str.strip().str.lower()
    active = boundaries.loc[enabled.isin({"1", "true", "yes", "y"})].copy()
    if active.empty:
        return {}
    active["sku_key"] = active.get("sku", "").astype(str).str.strip().str.upper()
    one = active.loc[active["sku_key"].eq(sku.upper())]
    if one.empty:
        return {}
    return {k: _norm(v) for k, v in one.iloc[0].to_dict().items()}


def _active_rule_for_sku(sku: str) -> Dict[str, str]:
    rules = load_active_supervisor_tactical_rules()
    if rules.empty:
        return {}
    rules = rules.copy()
    rules["sku_key"] = rules.get("sku", "").astype(str).str.strip().str.upper()
    one = rules.loc[rules["sku_key"].eq(sku.upper())].copy()
    if one.empty:
        return {}
    one["priority_num"] = pd.to_numeric(one.get("priority", ""), errors="coerce").fillna(9999)
    one = one.sort_values(["priority_num"], kind="stable")
    return {k: _norm(v) for k, v in one.iloc[0].to_dict().items()}


def _last_safe_mode_event_time(event_log: pd.DataFrame, sku: str) -> datetime | None:
    if event_log.empty:
        return None
    e = event_log.copy()
    source_col = e.get("source", "").astype(str).str.strip()
    sku_col = e.get("sku", "").astype(str).str.strip().str.upper()
    subset = e.loc[source_col.eq(SOURCE) & sku_col.eq(sku.upper())].copy()
    if subset.empty:
        return None
    dt = pd.to_datetime(subset.get("event_utc", ""), errors="coerce", utc=True).dropna()
    if dt.empty:
        return None
    return dt.max().to_pydatetime()


def _used_daily_down_move(event_log: pd.DataFrame, sku: str, asof_date: str, event_id: str) -> float:
    if event_log.empty:
        return 0.0
    e = event_log.copy()
    source_col = e.get("source", "").astype(str).str.strip()
    sku_col = e.get("sku", "").astype(str).str.strip().str.upper()
    asof_col = e.get("asof_date", "").astype(str).str.strip()
    keep = source_col.eq(SOURCE) & sku_col.eq(sku.upper()) & asof_col.eq(asof_date)
    if "probe_event_id" in e.columns:
        keep = keep & ~e["probe_event_id"].astype(str).str.strip().eq(event_id)
    subset = e.loc[keep].copy()
    if subset.empty:
        return 0.0
    before = pd.to_numeric(subset.get("action_price_before_gbp", ""), errors="coerce")
    target = pd.to_numeric(subset.get("action_price_target_gbp", ""), errors="coerce")
    down = (before - target).clip(lower=0).fillna(0)
    return float(down.sum())


def _choose_safe_mode_probe(rule_probe: str, reason_codes: List[str]) -> str:
    p = _norm(rule_probe).lower() or "hold"
    if p not in SAFE_MODE_ALLOWED_PROBES:
        reason_codes.append("safe_mode_probe_override")
        return "hold"
    return p


def main() -> None:
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    snapshot_path = _latest_listing_snapshot()
    snapshot = pd.read_csv(snapshot_path, dtype=str).fillna("")

    active_skus = load_active_lab_skus()
    if not active_skus:
        raise RuntimeError("No active lab cohort SKU found in config/h_lab_cohort.csv")
    if OFFICIAL_PILOT_SKU not in {s.upper() for s in active_skus}:
        raise RuntimeError(
            f"Official pilot SKU not active in config/h_lab_cohort.csv: {OFFICIAL_PILOT_SKU}"
        )
    pilot_sku = OFFICIAL_PILOT_SKU

    sku_rows = snapshot.loc[snapshot.get("sku", "").astype(str).str.strip().str.upper().eq(pilot_sku.upper())]
    if sku_rows.empty:
        raise RuntimeError(f"Pilot SKU not found in latest listing snapshot: {pilot_sku}")
    row = sku_rows.iloc[0].to_dict()

    boundary = _active_head_boundary_for_sku(pilot_sku)
    rule = _active_rule_for_sku(pilot_sku)
    if not boundary:
        raise RuntimeError(f"No active head boundary found for pilot SKU: {pilot_sku}")
    if not rule:
        raise RuntimeError(f"No active supervisor tactical rule found for pilot SKU: {pilot_sku}")

    asof_date = _norm(row.get("asof_date", "")) or now_utc.date().isoformat()
    probe_event_id = f"safe_mode_{pilot_sku}_{asof_date.replace('-', '')}"
    event_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    before_price = _to_float(row.get("our_price", ""))
    buy_box_price = _to_float(row.get("buy_box_price", ""))
    hard_floor = _to_float(boundary.get("hard_floor_gbp", ""))
    ceiling = _to_float(boundary.get("ceiling_gbp", ""))
    max_move = _to_float(boundary.get("max_move_per_cycle_gbp", ""))
    max_daily_down = _to_float(boundary.get("max_daily_down_move_gbp", ""))
    cooldown_boundary = _to_int(boundary.get("cooldown_minutes", ""))
    cooldown_rule = _to_int(rule.get("cooldown_minutes", ""))
    cooldown_minutes = max(cooldown_boundary or 0, cooldown_rule or 0)
    if cooldown_minutes < 1:
        cooldown_minutes = 1

    expiry_minutes = _to_int(rule.get("expiry_minutes", ""))
    if expiry_minutes is None or expiry_minutes < 1:
        expiry_minutes = 240
    expiry_utc = (now_utc + timedelta(minutes=expiry_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

    if before_price is None:
        raise RuntimeError(f"Missing our_price for pilot SKU in snapshot: {pilot_sku}")

    reason_codes: List[str] = ["phase0_safe_mode"]
    probe_type = _choose_safe_mode_probe(rule.get("allowed_probe_type", "hold"), reason_codes)

    if probe_type == "match" and buy_box_price is not None:
        target_price = buy_box_price
    else:
        target_price = before_price
        if probe_type == "match" and buy_box_price is None:
            reason_codes.append("buy_box_missing_fallback_hold")

    event_log = load_probe_event_log()
    last_event_time = _last_safe_mode_event_time(event_log, pilot_sku)
    if last_event_time is not None:
        elapsed_minutes = (now_utc - last_event_time).total_seconds() / 60.0
        if elapsed_minutes < cooldown_minutes:
            target_price = before_price
            probe_type = "hold"
            reason_codes.append("cooldown_enforced")

    if hard_floor is not None and target_price < hard_floor:
        target_price = hard_floor
        reason_codes.append("hard_floor_enforced")
    if ceiling is not None and target_price > ceiling:
        target_price = ceiling
        reason_codes.append("ceiling_enforced")

    if max_move is not None and max_move > 0:
        move = target_price - before_price
        if abs(move) > max_move:
            target_price = before_price + (max_move if move > 0 else -max_move)
            reason_codes.append("max_move_enforced")

    if max_daily_down is not None and max_daily_down >= 0:
        used_down = _used_daily_down_move(event_log, pilot_sku, asof_date, probe_event_id)
        this_down = max(before_price - target_price, 0.0)
        if used_down + this_down > max_daily_down:
            allowed_this = max(max_daily_down - used_down, 0.0)
            target_price = before_price - allowed_this
            reason_codes.append("max_daily_down_enforced")

    if hard_floor is not None and target_price < hard_floor:
        target_price = hard_floor
    if ceiling is not None and target_price > ceiling:
        target_price = ceiling

    # In Safe Mode, any downward result is converted to hold to avoid battle behavior.
    if target_price < before_price:
        target_price = before_price
        probe_type = "hold"
        reason_codes.append("safe_mode_no_downward_move")

    if abs(target_price - before_price) < 0.000001:
        probe_type = "hold"

    approved_rule_id = (
        f"safe_mode|{_norm(rule.get('state', 'unknown')).lower()}|"
        f"{_norm(rule.get('trigger_code', 'baseline_check')).lower()}|{probe_type}"
    )

    event_row = {
        "probe_event_id": probe_event_id,
        "asof_date": asof_date,
        "event_utc": event_utc,
        "marketplace": _norm(row.get("marketplace", "")),
        "sku": _norm(row.get("sku", "")),
        "asin": _norm(row.get("asin", "")),
        "lane": _norm(boundary.get("lane", "managed")),
        "supervisor_state": _norm(rule.get("state", "unknown")).lower(),
        "trigger_code": _norm(rule.get("trigger_code", "baseline_check")).lower(),
        "probe_type": probe_type,
        "action_price_before_gbp": _fmt(before_price),
        "action_price_target_gbp": _fmt(target_price),
        "hard_floor_gbp": _fmt(hard_floor),
        "ceiling_gbp": _fmt(ceiling),
        "max_move_per_cycle_gbp": _fmt(max_move),
        "cooldown_minutes": str(cooldown_minutes),
        "expiry_utc": expiry_utc,
        "reason_codes": "|".join(reason_codes),
        "approved_rule_id": approved_rule_id,
        "source": SOURCE,
        "notes": f"snapshot={snapshot_path.name}",
    }

    response_rows = []
    for minutes in RESPONSE_WINDOWS:
        response_rows.append(
            {
                "probe_event_id": probe_event_id,
                "asof_date": asof_date,
                "response_utc": (now_utc + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "response_window_minutes": str(minutes),
                "marketplace": _norm(row.get("marketplace", "")),
                "sku": _norm(row.get("sku", "")),
                "asin": _norm(row.get("asin", "")),
                "competitor_moved_flag": "0",
                "competitor_move_direction": "flat",
                "competitor_move_size_gbp": "0.00",
                "reaction_lag_minutes": "",
                "buy_box_price_gbp_after": _norm(row.get("buy_box_price", "")),
                "buy_box_channel_after": _norm(row.get("buy_box_channel", "")),
                "buy_box_owner_after": "",
                "our_price_gbp_after": _fmt(target_price),
                "outcome_code": "pending_observation",
                "source": SOURCE,
                "notes": "safe_mode_placeholder_response_window",
            }
        )

    initialize_probe_logs()
    events_after = append_probe_events([event_row])
    responses_after = append_probe_responses(response_rows)

    events_source = events_after.loc[events_after["source"].astype(str).str.strip().eq(SOURCE)].copy()
    events_source["sku_key"] = events_source["sku"].astype(str).str.strip().str.upper()
    source_pilot = events_source.loc[events_source["sku_key"].eq(pilot_sku.upper())]
    this_event_responses = responses_after.loc[
        responses_after["probe_event_id"].astype(str).str.strip().eq(probe_event_id)
    ].copy()

    print(f"safe_mode_source={SOURCE}")
    print(f"snapshot_used={snapshot_path.as_posix()}")
    print(f"probe_event_log={PROBE_EVENT_LOG_PATH.as_posix()}")
    print(f"probe_response_log={PROBE_RESPONSE_LOG_PATH.as_posix()}")
    print(f"pilot_sku={pilot_sku}")
    print(f"probe_event_id={probe_event_id}")
    print(f"event_rows_total={len(events_after)}")
    print(f"response_rows_total={len(responses_after)}")
    print(f"safe_mode_event_rows_total={len(events_source)}")
    print(f"safe_mode_event_rows_pilot={len(source_pilot)}")
    print(f"action_before_gbp={_fmt(before_price)}")
    print(f"action_target_gbp={_fmt(target_price)}")
    print(f"probe_type={probe_type}")
    print(f"reason_codes={event_row['reason_codes']}")
    print(f"response_rows_for_event={len(this_event_responses)}")
    windows = "|".join(sorted(this_event_responses["response_window_minutes"].astype(str).tolist()))
    print(f"response_windows_for_event={windows}")


if __name__ == "__main__":
    main()
