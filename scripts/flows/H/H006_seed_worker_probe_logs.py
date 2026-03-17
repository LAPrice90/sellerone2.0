from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

import pandas as pd

from scripts.h.h_head_boundaries import load_head_boundaries
from scripts.h.h_lab_cohort import load_active_lab_skus
from scripts.h.h_probe_logs import (
    PROBE_EVENT_LOG_PATH,
    PROBE_RESPONSE_LOG_PATH,
    append_probe_events,
    append_probe_responses,
    initialize_probe_logs,
    load_probe_event_log,
    load_probe_response_log,
)
from scripts.h.h_supervisor_tactical_rules import load_active_supervisor_tactical_rules

OUT = Path("out")


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


def _compute_target_price(before: float | None, buy_box: float | None, probe_type: str, adjust: float | None) -> float | None:
    if before is None:
        return None
    pt = probe_type.strip().lower()
    adj = adjust if adjust is not None else 0.0
    if pt == "lower":
        return before - adj
    if pt == "raise":
        return before + adj
    if pt == "match" and buy_box is not None:
        return buy_box
    return before


def main() -> None:
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    snapshot = pd.read_csv(_latest_listing_snapshot(), dtype=str).fillna("")
    active_skus = load_active_lab_skus()
    if not active_skus:
        raise RuntimeError("No active lab cohort SKU found in config/h_lab_cohort.csv")
    pilot_sku = active_skus[0]

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

    before_price = _to_float(row.get("our_price", ""))
    buy_box_price = _to_float(row.get("buy_box_price", ""))
    probe_type = _norm(rule.get("allowed_probe_type", "hold")).lower() or "hold"
    target_adjust = _to_float(rule.get("target_adjustment_gbp", "")) or 0.0
    target_price = _compute_target_price(before_price, buy_box_price, probe_type, target_adjust)

    hard_floor = _to_float(boundary.get("hard_floor_gbp", ""))
    ceiling = _to_float(boundary.get("ceiling_gbp", ""))
    if target_price is not None and hard_floor is not None:
        target_price = max(target_price, hard_floor)
    if target_price is not None and ceiling is not None:
        target_price = min(target_price, ceiling)

    event_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    asof_date = _norm(row.get("asof_date", "")) or now_utc.date().isoformat()
    probe_event_id = f"probe_{pilot_sku}_{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
    expiry_minutes = int(_to_float(rule.get("expiry_minutes", "")) or 240)
    expiry_utc = (now_utc + timedelta(minutes=expiry_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    approved_rule_id = (
        f"{_norm(rule.get('state', 'unknown')).lower()}|"
        f"{_norm(rule.get('trigger_code', 'baseline')).lower()}|"
        f"{probe_type}"
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
        "max_move_per_cycle_gbp": _fmt(_to_float(boundary.get("max_move_per_cycle_gbp", ""))),
        "cooldown_minutes": _norm(boundary.get("cooldown_minutes", "")),
        "expiry_utc": expiry_utc,
        "reason_codes": "phase0_schema_seed",
        "approved_rule_id": approved_rule_id,
        "source": "H006_seed_worker_probe_logs",
        "notes": "seed_row_for_schema_and_health_validation",
    }

    response_rows = []
    for minutes in [5, 15, 60, 240]:
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
                "our_price_gbp_after": _norm(row.get("our_price", "")),
                "outcome_code": "pending_observation",
                "source": "H006_seed_worker_probe_logs",
                "notes": "seed_response_window",
            }
        )

    initialize_probe_logs()
    events_after = append_probe_events([event_row])
    responses_after = append_probe_responses(response_rows)
    this_event_responses = responses_after.loc[responses_after["probe_event_id"].astype(str).str.strip().eq(probe_event_id)]

    print(f"probe_event_log={PROBE_EVENT_LOG_PATH.as_posix()}")
    print(f"probe_response_log={PROBE_RESPONSE_LOG_PATH.as_posix()}")
    print(f"seed_probe_event_id={probe_event_id}")
    print(f"event_rows_total={len(events_after)}")
    print(f"response_rows_total={len(responses_after)}")
    print(f"response_rows_for_seed_event={len(this_event_responses)}")
    print(f"response_windows_for_seed_event={'|'.join(sorted(this_event_responses['response_window_minutes'].astype(str).tolist()))}")
    print(f"pilot_sku={pilot_sku}")


if __name__ == "__main__":
    main()


