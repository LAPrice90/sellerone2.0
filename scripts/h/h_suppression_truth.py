from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SUPPRESSED_STATES = {"SUPPRESSED_ASIN", "DISQUALIFIED_SELF_PRICE"}
NON_ATTEMPT_WRITE_STATUSES = {"", "NO_WRITE_REQUIRED"}
APPLIED_WRITE_STATUSES = {"APPLIED", "APPLIED_OBSERVED"}
SUPPRESSION_ACTIVE_REASON_CODES = {
    "BUY_BOX_STATE_SUPPRESSED_ASIN",
    "SUPPRESSION_DIRECT_TARGET",
    "SUPPRESSION_PROBE_DOWNWARD_STEP",
    "SUPPRESSION_CEILING_CLAMPED_TO_EXISTING_FINAL",
    "SUPPRESSION_PROBE_CEILING_USED",
}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        out = float(text)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if text == "":
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _safe_int_flag(value: Any) -> int:
    text = str(value or "").strip().lower()
    return 1 if text in {"1", "true", "yes", "y", "on"} else 0


def _approx_equal(left: float | None, right: float | None, *, tol: float = 0.02) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= tol


def _clean_text(value: Any, *, upper: bool = False) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        return ""
    return text.upper() if upper else text


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame()


def _json_list(value: Any) -> list[str]:
    text = str(value or "").strip()
    if text == "":
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[str] = []
    for item in parsed:
        item_text = str(item or "").strip()
        if item_text != "":
            out.append(item_text)
    return out


def _latest_rows_by_sku(df: pd.DataFrame, ts_col: str) -> pd.DataFrame:
    if df.empty or "sku" not in df.columns:
        return pd.DataFrame(columns=["sku"])
    work = df.copy()
    work["sku"] = work.get("sku", "").astype(str).str.strip()
    work = work.loc[work["sku"].ne("")].copy()
    if work.empty:
        return pd.DataFrame(columns=["sku"])
    work["_ts"] = pd.to_datetime(work.get(ts_col, ""), errors="coerce", utc=True)
    work = work.sort_values(["sku", "_ts"], ascending=[True, False], kind="stable")
    work = work.drop_duplicates(subset=["sku"], keep="first")
    return work.drop(columns=["_ts"], errors="ignore")


def load_latest_suppression_truth(out_dir: Path, data_dir: Path) -> pd.DataFrame:
    reactivation_df = _load_csv(out_dir / "h_suppression_reactivation_log.csv")
    memory_df = _load_csv(out_dir / "h_suppression_threshold_memory.csv")
    facts_df = _load_csv(data_dir / "offer_snapshot_facts.csv")

    latest_reactivation = _latest_rows_by_sku(reactivation_df, "event_ts_utc")
    latest_memory = _latest_rows_by_sku(memory_df, "updated_utc")

    observed_cols = ["sku", "observed_our_price_gbp", "observed_our_price_ts_utc"]
    if facts_df.empty or "sku" not in facts_df.columns:
        observed_df = pd.DataFrame(columns=observed_cols)
    else:
        facts = facts_df.copy()
        facts["sku"] = facts.get("sku", "").astype(str).str.strip()
        facts["is_our_offer_num"] = pd.to_numeric(facts.get("is_our_offer", "0"), errors="coerce").fillna(0)
        facts = facts.loc[facts["sku"].ne("") & facts["is_our_offer_num"].eq(1)].copy()
        facts["_ts"] = pd.to_datetime(facts.get("snapshot_ts_utc", ""), errors="coerce", utc=True)
        facts = facts.sort_values(["sku", "_ts"], ascending=[True, False], kind="stable")
        facts = facts.drop_duplicates(subset=["sku"], keep="first")
        observed_df = pd.DataFrame(
            {
                "sku": facts.get("sku", "").astype(str),
                "observed_our_price_gbp": facts.get("landed_price_gbp", "").astype(str),
                "observed_our_price_ts_utc": facts.get("snapshot_ts_utc", "").astype(str),
            }
        )

    if latest_reactivation.empty and latest_memory.empty and observed_df.empty:
        return pd.DataFrame(
            columns=[
                "sku",
                "suppression_last_event_ts_utc",
                "suppression_buy_box_state",
                "suppression_strategy_state",
                "suppression_write_status",
                "suppression_target_price_gbp",
                "suppression_target_source",
                "suppression_reactivation_target_landed_gbp",
                "suppression_threshold_upper_bound_gbp",
                "suppression_ceiling_landed_temp",
                "suppression_ceiling_expiry_utc",
                "suppression_anchor_floor_gbp",
                "suppression_memory_updated_utc",
                "suppression_last_validated_utc",
                "suppression_active_flag",
                "observed_our_price_gbp",
                "observed_our_price_ts_utc",
            ]
        )

    frames = [df for df in [latest_reactivation[["sku"]] if not latest_reactivation.empty else pd.DataFrame(), latest_memory[["sku"]] if not latest_memory.empty else pd.DataFrame(), observed_df[["sku"]] if not observed_df.empty else pd.DataFrame()] if not df.empty]
    base = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["sku"], keep="first")

    if not latest_reactivation.empty:
        keep = [
            "sku",
            "event_ts_utc",
            "buy_box_state",
            "state",
            "write_status",
            "target_price_gbp",
            "suppression_target_source",
            "suppression_reactivation_target_landed_gbp",
            "suppression_ceiling_landed_temp",
            "anchor_floor_price",
        ]
        keep = [c for c in keep if c in latest_reactivation.columns]
        base = base.merge(latest_reactivation[keep], on="sku", how="left")

    if not latest_memory.empty:
        keep = [
            "sku",
            "lowest_ineligible_price",
            "suppression_ceiling_landed_temp",
            "suppression_ceiling_expiry_utc",
            "last_buy_box_state",
            "updated_utc",
            "suppression_last_validated_utc",
        ]
        keep = [c for c in keep if c in latest_memory.columns]
        latest_memory_keep = latest_memory[keep].copy()
        latest_memory_keep = latest_memory_keep.rename(
            columns={
                "lowest_ineligible_price": "suppression_threshold_upper_bound_gbp",
                "suppression_ceiling_landed_temp": "memory_suppression_ceiling_landed_temp",
                "suppression_ceiling_expiry_utc": "memory_suppression_ceiling_expiry_utc",
                "last_buy_box_state": "memory_last_buy_box_state",
                "updated_utc": "suppression_memory_updated_utc",
            }
        )
        base = base.merge(latest_memory_keep, on="sku", how="left")

    if not observed_df.empty:
        base = base.merge(observed_df, on="sku", how="left")

    out_rows: list[dict[str, str]] = []
    now_utc = datetime.now(timezone.utc)
    for _, row in base.iterrows():
        sku = str(row.get("sku", "")).strip()
        if sku == "":
            continue
        suppression_ceiling = (
            _clean_text(row.get("suppression_ceiling_landed_temp", ""))
            or _clean_text(row.get("memory_suppression_ceiling_landed_temp", ""))
        )
        suppression_expiry = (
            _clean_text(row.get("memory_suppression_ceiling_expiry_utc", ""))
            or _clean_text(row.get("suppression_ceiling_expiry_utc", ""))
        )
        last_buy_box_state = (
            _clean_text(row.get("buy_box_state", ""), upper=True)
            or _clean_text(row.get("memory_last_buy_box_state", ""), upper=True)
        )
        last_event_dt = _parse_utc(row.get("event_ts_utc", ""))
        last_memory_dt = _parse_utc(row.get("suppression_memory_updated_utc", ""))
        expiry_dt = _parse_utc(suppression_expiry)
        suppression_recent = False
        if last_event_dt is not None and last_event_dt >= now_utc - timedelta(days=7):
            suppression_recent = True
        if last_memory_dt is not None and last_memory_dt >= now_utc - timedelta(days=7):
            suppression_recent = True
        suppression_active = last_buy_box_state in SUPPRESSED_STATES and (
            expiry_dt is None or expiry_dt >= now_utc or suppression_recent
        )
        out_rows.append(
            {
                "sku": sku,
                "suppression_last_event_ts_utc": _clean_text(row.get("event_ts_utc", "")),
                "suppression_buy_box_state": last_buy_box_state,
                "suppression_strategy_state": _clean_text(row.get("state", "")),
                "suppression_write_status": _clean_text(row.get("write_status", "")),
                "suppression_target_price_gbp": _clean_text(row.get("target_price_gbp", "")),
                "suppression_target_source": _clean_text(row.get("suppression_target_source", "")),
                "suppression_reactivation_target_landed_gbp": _clean_text(row.get("suppression_reactivation_target_landed_gbp", "")),
                "suppression_threshold_upper_bound_gbp": _clean_text(row.get("suppression_threshold_upper_bound_gbp", "")),
                "suppression_ceiling_landed_temp": suppression_ceiling,
                "suppression_ceiling_expiry_utc": suppression_expiry,
                "suppression_anchor_floor_gbp": _clean_text(row.get("anchor_floor_price", "")),
                "suppression_memory_updated_utc": _clean_text(row.get("suppression_memory_updated_utc", "")),
                "suppression_last_validated_utc": _clean_text(row.get("suppression_last_validated_utc", "")),
                "suppression_active_flag": "1" if suppression_active else "0",
                "observed_our_price_gbp": _clean_text(row.get("observed_our_price_gbp", "")),
                "observed_our_price_ts_utc": _clean_text(row.get("observed_our_price_ts_utc", "")),
            }
        )

    return pd.DataFrame.from_records(out_rows)


def resolve_unified_truth(
    *,
    suppression_active_flag: Any,
    parked_flag: Any,
    write_capable: bool,
    execution_state: Any,
    execution_write_status: Any,
    execution_reason_codes_json: Any,
    execution_final_ceiling_landed_gbp: Any,
    execution_binding_ceiling_type: Any,
    suppression_buy_box_state: Any,
    suppression_strategy_state: Any,
    suppression_write_status: Any,
    suppression_ceiling_landed_temp: Any,
    execution_old_price_gbp: Any = "",
    execution_new_price_gbp: Any = "",
    execution_hard_floor_gbp: Any = "",
    observed_our_price_gbp: Any = "",
    trace_candidate_price_gbp: Any = "",
    trace_floor_total_gbp: Any = "",
    execution_event_ts_utc: Any = "",
    trace_asof_utc: Any = "",
) -> dict[str, str]:
    suppression_active = _safe_int_flag(suppression_active_flag) == 1
    parked = _safe_int_flag(parked_flag) == 1
    exec_write_status = _clean_text(execution_write_status)
    suppression_write = _clean_text(suppression_write_status)
    exec_reason_codes = _json_list(execution_reason_codes_json)
    execution_old_price = _safe_float(execution_old_price_gbp)
    execution_new_price = _safe_float(execution_new_price_gbp)
    execution_hard_floor = _safe_float(execution_hard_floor_gbp)
    observed_our_price = _safe_float(observed_our_price_gbp)
    trace_candidate_price = _safe_float(trace_candidate_price_gbp)
    trace_floor_total = _safe_float(trace_floor_total_gbp)
    execution_event_dt = _parse_utc(execution_event_ts_utc)
    trace_asof_dt = _parse_utc(trace_asof_utc)
    exec_reason_set = {str(code or "").strip().upper() for code in exec_reason_codes if str(code or "").strip()}

    # Reconcile stale suppression memory against direct execution evidence.
    # If execution explicitly reports suppression not active and does not also
    # report active suppression signals, treat suppression memory as stale.
    suppression_reconcile_action = ""
    effective_suppression_active = suppression_active
    if suppression_active and "SUPPRESSION_NOT_ACTIVE" in exec_reason_set:
        has_active_suppression_signal = any(code in SUPPRESSION_ACTIVE_REASON_CODES for code in exec_reason_set)
        if not has_active_suppression_signal:
            effective_suppression_active = False
            suppression_reconcile_action = "SUPPRESSION_STALE_CLEARED_BY_EXECUTION_NOT_ACTIVE"

    unified_writer_outcome = exec_write_status
    if effective_suppression_active and suppression_write != "":
        unified_writer_outcome = suppression_write

    strategy_state = _clean_text(execution_state)
    if effective_suppression_active and _clean_text(suppression_strategy_state) != "":
        strategy_state = _clean_text(suppression_strategy_state)

    buy_box_truth = _clean_text(suppression_buy_box_state, upper=True)
    if buy_box_truth == "" and "SUPPRESSION_OR_UNKNOWN_OUTCOME" in exec_reason_codes:
        buy_box_truth = "UNKNOWN"

    true_binding_ceiling_gbp = _clean_text(execution_final_ceiling_landed_gbp)
    true_binding_ceiling_type = _clean_text(execution_binding_ceiling_type, upper=True)
    suppression_ceiling = _clean_text(suppression_ceiling_landed_temp)
    if effective_suppression_active and suppression_ceiling != "":
        true_binding_ceiling_gbp = suppression_ceiling
        true_binding_ceiling_type = "SUPPRESSION_TEMP"

    floor_conflict_active = "FLOOR_PRIORITY_CEILING_CONFLICT" in exec_reason_codes
    observed_floor_seek_applied = bool(
        not effective_suppression_active
        and unified_writer_outcome in NON_ATTEMPT_WRITE_STATUSES
        and observed_our_price is not None
        and execution_old_price is not None
        and observed_our_price < execution_old_price - 0.01
        and trace_asof_dt is not None
        and (execution_event_dt is None or trace_asof_dt >= execution_event_dt)
        and (
            _approx_equal(observed_our_price, trace_candidate_price)
            or _approx_equal(observed_our_price, trace_floor_total)
            or (floor_conflict_active and _approx_equal(observed_our_price, execution_hard_floor))
        )
    )
    if observed_floor_seek_applied:
        unified_writer_outcome = "APPLIED_OBSERVED"
        if floor_conflict_active and strategy_state in {"", "HOLD_OBSERVE", "RAISE_FIND_LOSS"}:
            strategy_state = "CONTROLLED_EXIT_TO_FLOOR"
        if _approx_equal(observed_our_price, trace_floor_total) or (floor_conflict_active and _approx_equal(observed_our_price, execution_hard_floor)):
            if trace_floor_total is not None:
                true_binding_ceiling_gbp = f"{trace_floor_total:.2f}"
            elif execution_hard_floor is not None:
                true_binding_ceiling_gbp = f"{execution_hard_floor:.2f}"
            true_binding_ceiling_type = "PHASE_FLOOR"

    write_attempted = unified_writer_outcome not in NON_ATTEMPT_WRITE_STATUSES
    write_applied = unified_writer_outcome in APPLIED_WRITE_STATUSES

    if parked:
        truth_status = "PARKED"
    elif effective_suppression_active and write_applied:
        truth_status = "SUPP_APPLIED"
    elif effective_suppression_active and write_attempted:
        truth_status = "SUPP_BLOCKED"
    elif effective_suppression_active:
        truth_status = "SUPPRESSED"
    elif write_applied:
        truth_status = "WRITE_APPLIED"
    elif write_capable:
        truth_status = "WRITE_CAPABLE"
    else:
        truth_status = "READ_ONLY"

    return {
        "unified_buy_box_state": buy_box_truth,
        "unified_strategy_state": strategy_state,
        "unified_writer_outcome": unified_writer_outcome,
        "write_attempted_flag": "1" if write_attempted else "0",
        "write_applied_flag": "1" if write_applied else "0",
        "true_binding_ceiling_gbp": true_binding_ceiling_gbp,
        "true_binding_ceiling_type": true_binding_ceiling_type,
        "truth_status": truth_status,
        "suppression_resolved_flag": "0" if effective_suppression_active else "",
        "suppression_effective_active_flag": "1" if effective_suppression_active else "0",
        "suppression_reconcile_action": suppression_reconcile_action,
    }
