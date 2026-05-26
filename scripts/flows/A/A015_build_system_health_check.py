from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

BOOT_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = BOOT_ROOT / "scripts"
for _path in (BOOT_ROOT, SCRIPTS_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import pandas as pd
from scripts.core.out_paths import resolve_compat_path
from scripts.core.storage import read_dataframe_with_sql_fallback, write_dataframe_with_sql_compat
try:
    from scripts.core.flow_health_gate import flow_gate_checklist_path
except ModuleNotFoundError:
    from core.flow_health_gate import flow_gate_checklist_path
try:
    from scripts.core.cycle_failure_events import (
        FAILURE_EVENT_COLUMNS,
        DEFAULT_LEDGER_PATH as DEFAULT_CYCLE_FAILURE_LEDGER_PATH,
        validate_cycle_failure_events_schema,
    )
except ModuleNotFoundError:
    from core.cycle_failure_events import (
        FAILURE_EVENT_COLUMNS,
        DEFAULT_LEDGER_PATH as DEFAULT_CYCLE_FAILURE_LEDGER_PATH,
        validate_cycle_failure_events_schema,
    )
try:
    from scripts.phase1 import daily_intel_required_skus
except ModuleNotFoundError:
    from phase1 import daily_intel_required_skus

OUT = Path("out")
ROOT = Path(__file__).resolve().parents[3]
DATA = Path("data")
CHECKLIST_CSV = OUT / "system_health_checklist.csv"
CYCLE_ALERT_DIR = OUT / "cycle_alerts"
CYCLE_FAILURE_EVENTS_PATH = Path(
    os.environ.get("CYCLE_FAILURE_EVENTS_PATH", DEFAULT_CYCLE_FAILURE_LEDGER_PATH)
)
SQL_TABLE_SYSTEM_HEALTH_CHECKLIST = "sys_system_health_checklist"
SQL_TABLE_CHECKLIST_B = "b_checklist_b"
ALERT_STATE_CSV = OUT / "system_health_alert_state.csv"
ALERT_STATE_A_CSV = OUT / "system_health_alert_state_A.csv"
ALERT_STATE_B_CSV = OUT / "system_health_alert_state_B.csv"
ALERT_STATE_E_CSV = OUT / "system_health_alert_state_E.csv"
ALERT_STATE_H_CSV = OUT / "system_health_alert_state_H.csv"
ALERT_HISTORY_CSV = OUT / "system_health_alert_history.csv"
ALERT_HISTORY_A_CSV = OUT / "system_health_alert_history_A.csv"
ALERT_HISTORY_B_CSV = OUT / "system_health_alert_history_B.csv"
ALERT_HISTORY_E_CSV = OUT / "system_health_alert_history_E.csv"
ALERT_HISTORY_H_CSV = OUT / "system_health_alert_history_H.csv"
ALERT_SNOOZE_PATH = OUT / "locks" / "health_alert_snooze.json"
DETAIL_BLANK_COGS = OUT / "health_order_master_blank_cogs_lvl1plus.csv"
DETAIL_PLACEHOLDER_COGS = OUT / "health_order_master_placeholder_cogs.csv"
DETAIL_MISSING_TOKEN_NO_PLACEHOLDER = OUT / "health_order_master_missing_token_no_placeholder.csv"
DETAIL_ALLOCATED_TOKENS_ON_CANCELED_ORDERS = OUT / "health_allocated_tokens_on_canceled_orders.csv"
DETAIL_UNKNOWN_FEE_COUNTRIES = OUT / "health_unknown_fee_countries.csv"
FEE_RULES_PATH = Path("reference/fee_vat_rules.csv")
VAT_MODEL = OUT / "vat_country_model.csv"
FEE_MODEL = OUT / "fee_country_model.csv"
DETAIL_ORDERS_MISSING_ITEMS = OUT / "health_orders_missing_items_window.csv"
HEALTH_STATUS_CSV = OUT / "health_status.csv"
HEALTH_STATUS_A_CSV = OUT / "health_status_A.csv"
HEALTH_STATUS_B_CSV = OUT / "health_status_B.csv"
HEALTH_STATUS_E_CSV = OUT / "health_status_E.csv"
HEALTH_STATUS_H_CSV = OUT / "health_status_H.csv"
CHECKLIST_A_SPLIT_CSV = OUT / "cycle_alerts" / "checklist_A_split.csv"
CHECKLIST_B_SPLIT_CSV = OUT / "cycle_alerts" / "checklist_B_split.csv"
CHECKLIST_E_SPLIT_CSV = OUT / "cycle_alerts" / "checklist_E_split.csv"
# H flow-owned gate truth is checklist_H.csv; split file remains observability-only.
CHECKLIST_H_GATE_CSV = flow_gate_checklist_path("H")
CHECKLIST_H_SPLIT_CSV = OUT / "cycle_alerts" / "checklist_H_split.csv"
A015_SPLIT_RUNTIME_EXCEPTION_PATH = OUT / "cycle_alerts" / "A015_split_runtime_exception.txt"
L1_MISSING_FEE_KEYS = OUT / "l1_missing_fee_keys.csv"
MISSING_TOKEN_ORDERS = OUT / "orders_missing_tokens.csv"
TRAINING_SET_PATH = Path("config/f_training_set.csv")
LAB_COHORT_PATH = Path("config/h_lab_cohort.csv")
HEAD_BOUNDARIES_PATH = Path("config/h_head_boundaries.csv")
SUPERVISOR_TACTICAL_RULES_PATH = Path("config/h_supervisor_tactical_rules.csv")
OFFICIAL_PILOT_SKU = os.environ.get("H_OFFICIAL_PILOT_SKU", "L1-54EX-56YC").strip() or "L1-54EX-56YC"
PROBE_EVENT_LOG_COMPAT = resolve_compat_path("h_worker_probe_event_log.csv", default_system="H")
PROBE_EVENT_LOG_PATH = (
    PROBE_EVENT_LOG_COMPAT.live_path if PROBE_EVENT_LOG_COMPAT.live_path.exists() else PROBE_EVENT_LOG_COMPAT.legacy_path
)
PROBE_RESPONSE_LOG_COMPAT = resolve_compat_path("h_worker_probe_response_log.csv", default_system="H")
PROBE_RESPONSE_LOG_PATH = (
    PROBE_RESPONSE_LOG_COMPAT.live_path
    if PROBE_RESPONSE_LOG_COMPAT.live_path.exists()
    else PROBE_RESPONSE_LOG_COMPAT.legacy_path
)
H_EXECUTIONER_ACTION_LOG_PATH = OUT / "h_executioner_action_log.csv"
H_SELLER_PROFILE_PATH = OUT / "h_seller_profiles.csv"
H_SELLER_SOI_PATH = OUT / "h_seller_of_interest.csv"
H_CEILING_EVENTS_PATH = OUT / "h_ceiling_events.csv"
H_STRATEGY_OUTCOME_LOG_PATH = OUT / "h_strategy_outcome_log.csv"
H_STRATEGY_OUTCOME_DAILY_PATH = OUT / "h_strategy_outcome_daily.csv"
H_SUPPRESSION_CASES_PATH = OUT / "h_suppression_cases.csv"
H_SUPPRESSION_REACTIVATION_LOG_PATH = OUT / "h_suppression_reactivation_log.csv"
LISTING_OFFER_HISTORY_COMPAT = resolve_compat_path("listing_offer_history.csv", default_system="H")
LISTING_OFFER_HISTORY = (
    LISTING_OFFER_HISTORY_COMPAT.live_path
    if LISTING_OFFER_HISTORY_COMPAT.live_path.exists()
    else LISTING_OFFER_HISTORY_COMPAT.legacy_path
)
LISTING_OFFER_SELLER_HISTORY = OUT / "listing_offer_seller_observation_history.csv"
PHASE1_SELLER_HISTORY = OUT / "phase1_seller_history.csv"
LISTING_OFFER_SNAPSHOT_GLOB = "listing_offer_snapshot_*.csv"
LISTING_OFFER_SELLER_SNAPSHOT_GLOB = "listing_offer_seller_snapshot_*.csv"
RUN_SCOPED_SELLER_SNAPSHOT_REL = Path("snapshots") / "H"
HOS_DAILY_MARKET_SNAPSHOT_GLOB = "hos_daily_market_snapshot_*.csv"
HOS_DAILY_REPORT_DIR = OUT / "reports" / "hos_daily"
HOS_DAILY_REPORT_CHART_DIR = HOS_DAILY_REPORT_DIR / "charts"
INVENTORY_HISTORY = OUT / "inventory_history.csv"
INBOUND_HISTORY = OUT / "inbound_history.csv"
INVENTORY_SNAPSHOT_GLOB = "inventory_snapshot_*.csv"
INBOUND_SNAPSHOT_GLOB = "inbound_snapshot_*.csv"
INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
MERCHANT_LISTINGS_PATH = OUT / "merchant_listings_latest.csv"
STOCK_SNAPSHOT_LATEST_PATH = OUT / "parking" / "stock_snapshot_latest.csv"
REFUND_ADJUSTMENT_HISTORY = OUT / "refund_adjustment_history.csv"
REFUND_ADJUSTMENT_SNAPSHOT_GLOB = "refund_adjustment_snapshot_*.csv"
API_CALL_LOG_JSONL = OUT / "api_call_log.jsonl"
API_RUN_LOG_CSV = OUT / "api_run_log.csv"
API_RATE_STATE_JSON = OUT / "api_rate_state.json"
SPAPI_LOCK_PATH = OUT / "locks" / "spapi.lock"
E_RUN_LOG_JSONL = OUT / "e_run_log.jsonl"
E_RUN_LOG_PATH_CANDIDATES = [
    OUT / "systems" / "E" / "live" / "e_run_log.jsonl",
    OUT / "e_run_log.jsonl",
]
PHASE1_SCOPE_PATH = OUT / "phase1_sku_scope.csv"
O_RESTOCK_SOURCE_VIEW_PATH = OUT / "systems" / "O" / "live" / "restock_source_view.csv"
O_RESTOCK_RECOMMENDATIONS_PATH = OUT / "systems" / "O" / "live" / "restock_recommendations_live.csv"
O_REORDER_INPUT_COVERAGE_PATH = OUT / "systems" / "O" / "live" / "reorder_input_coverage_report.csv"
O_NET_FEE_ACTION_STATUSES = {
    "full_restock",
    "test_restock",
    "approve_full_restock",
    "approve_test_restock",
}
O_NET_FEE_SOURCE_REQUIRED_FIELDS = (
    "market_price_ex_vat_gbp",
    "market_price_vat_rate_pct",
    "current_token_cost_gbp",
    "break_even_price_gbp",
    "net_fee_drag_per_unit_gbp",
    "net_fee_model_status",
    "net_fee_model_asof",
    "net_fee_model_age_hours",
    "net_fee_model_source",
)
O_NET_FEE_RECOMMENDATION_REQUIRED_FIELDS = (
    "forward_roi_pct",
    "forward_profit_per_unit_gbp",
    "market_price_ex_vat_gbp",
    "current_token_cost_gbp",
    "break_even_price_gbp",
    "net_fee_drag_per_unit_gbp",
    "net_fee_model_status",
    "net_fee_model_asof",
    "net_fee_model_age_hours",
    "net_fee_model_source",
    "gross_forward_roi_pct",
    "gross_forward_profit_per_unit_gbp",
)
O_NET_FEE_COVERAGE_REQUIRED_FIELDS = (
    "expected_forward_roi_pct",
    "net_fee_drag_per_unit_gbp",
    "net_fee_model_status",
    "net_fee_model_asof",
    "net_fee_model_age_hours",
)
O_NET_FEE_NUMERIC_FIELDS = {
    "market_price_ex_vat_gbp",
    "market_price_vat_rate_pct",
    "current_token_cost_gbp",
    "break_even_price_gbp",
    "net_fee_drag_per_unit_gbp",
    "net_fee_model_age_hours",
    "forward_roi_pct",
    "forward_profit_per_unit_gbp",
    "expected_forward_roi_pct",
    "gross_forward_roi_pct",
    "gross_forward_profit_per_unit_gbp",
}
O_NET_FEE_POSITIVE_FIELDS = {
    "market_price_ex_vat_gbp",
    "current_token_cost_gbp",
    "break_even_price_gbp",
}


def _write_health_checklist_csv(dataframe: pd.DataFrame, path: Path) -> None:
    rel_path = path.as_posix().replace("\\", "/")
    if rel_path.endswith("out/system_health_checklist.csv"):
        write_dataframe_with_sql_compat(dataframe, path, SQL_TABLE_SYSTEM_HEALTH_CHECKLIST)
        return
    if rel_path.endswith("out/cycle_alerts/checklist_B.csv"):
        write_dataframe_with_sql_compat(dataframe, path, SQL_TABLE_CHECKLIST_B)
        return
    dataframe.to_csv(path, index=False)


SQL_READER_TABLES = {
    str((OUT / "phase1_sku_scope.csv").as_posix()): "b_phase1_sku_scope",
    str((OUT / "inventory_summaries.csv").as_posix()): "a_inventory_summaries",
    str((OUT / "inventory_history.csv").as_posix()): "a_inventory_history",
    str((OUT / "h_seller_of_interest.csv").as_posix()): "h_seller_of_interest",
    str(LISTING_OFFER_HISTORY.as_posix()): "h_listing_offer_history",
}
PHASE1_DAILY_INTEL_PATH = DATA / "sku_daily_intel.csv"
PHASE1_DAILY_INTEL_LATEST_PATH = OUT / "phase1_daily_intel_latest.csv"
PHASE1_EXECUTION_LOG_PATH = DATA / "execution_log.csv"
PARKED_SKUS_PATH = OUT / "parking" / "parked_skus.csv"
FEES_FAILED_PATH = OUT / "fees_failed.csv"
H_PRICING_STATE_PATH_CANDIDATES = [
    OUT / "systems" / "H" / "live" / "h_pricing_cycle_state.json",
    OUT / "h_pricing_cycle_state.json",
]
B_CYCLE_LOG_PATH_CANDIDATES = [
    OUT / "systems" / "B" / "live" / "B_cycle.log",
    OUT / "B_cycle.log",
]
H_CYCLE_LOG_PATH_CANDIDATES = [
    OUT / "systems" / "H" / "live" / "H_cycle.log",
    OUT / "H_cycle.log",
]
H_LOCK_PATH_CANDIDATES = [
    OUT / "systems" / "H" / "live" / "H_pricing_cycle.lock",
    OUT / "H_pricing_cycle.lock",
]
E_LOCK_PATH_CANDIDATES = [
    OUT / "systems" / "E" / "live" / "E_cycle.lock",
    OUT / "E_cycle.lock",
]
B_SHEET_SYNC_STATUS_PATH = OUT / "b_sheet_sync_status.csv"
B_LISTING_COLLECTION_STATUS_PATH = OUT / "systems" / "B" / "live" / "listing_offer_collection_status.json"
B_MAINTENANCE_MARKER_PATHS = [
    OUT / "locks" / "maintenance.requested",
    OUT / "locks" / "maintenance.ready",
    OUT / "locks" / "maintenance.active",
    OUT / "locks" / "b_cycle.maintenance",
]
ORDERS_ALL_PATH = OUT / "orders_all.csv"
ORDER_MASTER_PATH = OUT / "order_master.csv"
LISTING_OFFER_SNAPSHOT_LATEST_PATH = OUT / "listing_offer_snapshot_latest.csv"
PHASE1_RUNTIME_FLOOR_SNAPSHOT_LATEST_PATH = OUT / "phase1_runtime_floor_snapshot_latest.csv"
H_PUBLISH_INFO_PATH_CANDIDATES = [
    OUT / "systems" / "H" / "live" / "H_cycle_last_publish_info.txt",
    OUT / "H_cycle_last_publish_info.txt",
]
H_TERMINAL_INFO_PATH_CANDIDATES = [
    OUT / "systems" / "H" / "live" / "H_cycle_last_terminal_info.txt",
    OUT / "H_cycle_last_terminal_info.txt",
]
H_CPT_ENDPOINT = "products_pricing_post_competitive_summary_batch"
H_FLOOR_VAT_POLICY_PATH = Path("config/h_floor_vat_policy.json")
H_TEMP_FLOOR_SNAPSHOT_PATH = OUT / "sku_temp_floor_snapshot.csv"
H_FLOOR_TRUTH_TRACE_PATH = OUT / "h_floor_truth_trace.csv"
H_LEGACY_EXECUTION_LOG_PATH = DATA / "repricing_live_execution_log.csv"
H_KILL_SWITCH_PATH = OUT / "locks" / "h_pricing_cycle.kill"
A_MANIFESTS_DIR = OUT / "manifests" / "A"
TOKEN_LEDGER_COMPAT = resolve_compat_path("token_ledger_live.csv", default_system="B")
TOKEN_LEDGER_PATH = TOKEN_LEDGER_COMPAT.live_path if TOKEN_LEDGER_COMPAT.live_path.exists() else TOKEN_LEDGER_COMPAT.legacy_path
TOKEN_ALLOCATIONS_COMPAT = resolve_compat_path("token_allocations_live.csv", default_system="B")
TOKEN_ALLOCATIONS_PATH = (
    TOKEN_ALLOCATIONS_COMPAT.live_path
    if TOKEN_ALLOCATIONS_COMPAT.live_path.exists()
    else TOKEN_ALLOCATIONS_COMPAT.legacy_path
)
ORPHAN_SCOPE_START_DATE = os.environ.get("ORPHAN_SCOPE_START_DATE", "").strip()
# Default scope start to keep pre-window orphans from failing health checks.
if not ORPHAN_SCOPE_START_DATE:
    ORPHAN_SCOPE_START_DATE = "2025-11-01"
ORPHAN_IGNORE_ORDER_IDS_FILE = os.environ.get("ORPHAN_IGNORE_ORDER_IDS_FILE", "").strip()
# Default ignore list to standard file if env var is not set.
if not ORPHAN_IGNORE_ORDER_IDS_FILE:
    default_ignore = OUT / "orphan_ignore_orders_combined.csv"
    if default_ignore.exists():
        ORPHAN_IGNORE_ORDER_IDS_FILE = str(default_ignore)


def _file_info(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {"exists": "no", "size_bytes": "0", "mtime_utc": ""}
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return {"exists": "yes", "size_bytes": str(stat.st_size), "mtime_utc": mtime}


def _critical_freshness_check(
    rows: List[Dict[str, str]],
    check_name: str,
    paths: List[Path] | Tuple[Path, ...],
    *,
    warn_after_minutes: float,
    fail_after_minutes: float,
    owner_cycle: str,
    recovery_signal: str,
    now_utc: datetime | None = None,
    missing_status: str = "fail",
) -> None:
    candidate_paths = list(paths)
    chosen = _first_existing_path(candidate_paths) or (candidate_paths[0] if candidate_paths else None)
    if chosen is None:
        _add(
            rows,
            check_name,
            "warn",
            "missing_path_config",
            f"owner={owner_cycle};recovery_signal={recovery_signal}",
        )
        return
    note_base = (
        f"owner={owner_cycle};recovery_signal={recovery_signal};path={chosen};"
        f"warn_after_min={warn_after_minutes:.1f};fail_after_min={fail_after_minutes:.1f}"
    )
    if not chosen.exists():
        _add(rows, check_name, missing_status, "missing", note_base)
        return
    probe_now = now_utc or datetime.now(timezone.utc)
    try:
        mtime_utc = datetime.fromtimestamp(chosen.stat().st_mtime, tz=timezone.utc)
        age_minutes = max((probe_now - mtime_utc).total_seconds() / 60.0, 0.0)
    except Exception as exc:
        _add(rows, check_name, "warn", "read_error", f"{note_base};error={exc.__class__.__name__}:{exc}")
        return
    status = "ok"
    if fail_after_minutes >= 0 and age_minutes >= fail_after_minutes:
        status = "fail"
    elif warn_after_minutes >= 0 and age_minutes >= warn_after_minutes:
        status = "warn"
    _add(rows, check_name, status, f"{age_minutes:.2f}", f"{note_base};mtime_utc={mtime_utc.isoformat()}")


def _relax_check_status_for_maintenance(
    rows: List[Dict[str, str]],
    *,
    check_name: str,
    from_status: str = "fail",
    to_status: str = "warn",
) -> None:
    active_markers = _b_maintenance_marker_paths_present()
    if not active_markers:
        return
    for row in reversed(rows):
        if str(row.get("check", "")) != check_name:
            continue
        current_status = str(row.get("status", "")).strip().lower()
        if current_status == from_status:
            row["status"] = to_status
        notes = str(row.get("notes", "")).strip()
        marker_text = ",".join([path.name for path in active_markers])
        suffix = f"maintenance_markers={marker_text};maintenance_expected_staleness=1"
        row["notes"] = f"{notes};{suffix}" if notes else suffix
        break


def _read_kv_file_value(path: Path, key: str) -> str:
    key_norm = str(key or "").strip()
    if not key_norm or not path.exists():
        return ""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = str(raw_line or "").strip()
                if not line or "=" not in line:
                    continue
                lhs, rhs = line.split("=", 1)
                if str(lhs or "").strip() == key_norm:
                    return str(rhs or "").strip()
    except Exception:
        return ""
    return ""


def _h_publish_marker_freshness_check(
    rows: List[Dict[str, str]],
    *,
    now_utc: datetime | None = None,
) -> None:
    warn_after_minutes = float(os.environ.get("H_PUBLISH_MARKER_WARN_MINUTES", "30"))
    fail_after_minutes = float(os.environ.get("H_PUBLISH_MARKER_FAIL_MINUTES", "90"))
    probe_now = now_utc or datetime.now(timezone.utc)
    publish_path = _first_existing_path(H_PUBLISH_INFO_PATH_CANDIDATES) or H_PUBLISH_INFO_PATH_CANDIDATES[0]
    terminal_path = _first_existing_path(H_TERMINAL_INFO_PATH_CANDIDATES) or H_TERMINAL_INFO_PATH_CANDIDATES[0]

    def _age_minutes(path: Path) -> float | None:
        if not path.exists():
            return None
        try:
            mtime_utc = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            return max((probe_now - mtime_utc).total_seconds() / 60.0, 0.0)
        except Exception:
            return None

    publish_age_min = _age_minutes(publish_path)
    terminal_age_min = _age_minutes(terminal_path)
    publish_status_value = _read_kv_file_value(publish_path, "status")
    terminal_state_value = _read_kv_file_value(terminal_path, "state")
    note_base = (
        "owner=H;recovery_signal=run_H_cycle.bat_guarded_owner;"
        f"publish_path={publish_path};terminal_path={terminal_path};"
        f"warn_after_min={warn_after_minutes:.1f};fail_after_min={fail_after_minutes:.1f};"
        f"publish_status={publish_status_value or 'unknown'};terminal_state={terminal_state_value or 'unknown'}"
    )
    publish_age_note = f"publish_age_min={publish_age_min:.2f}" if publish_age_min is not None else "publish_age_min=missing"
    terminal_age_note = f"terminal_age_min={terminal_age_min:.2f}" if terminal_age_min is not None else "terminal_age_min=missing"

    if publish_age_min is not None:
        if publish_age_min >= fail_after_minutes:
            publish_class = "fail"
        elif publish_age_min >= warn_after_minutes:
            publish_class = "warn"
        else:
            publish_class = "ok"
    else:
        publish_class = "missing"

    if publish_class in {"ok", "warn"}:
        _add(
            rows,
            "h_publish_marker_freshness",
            publish_class,
            f"{publish_age_min:.2f}" if publish_age_min is not None else "missing",
            f"{note_base};source=publish_marker;{publish_age_note};{terminal_age_note}",
        )
        return

    if terminal_age_min is None:
        _add(
            rows,
            "h_publish_marker_freshness",
            "fail",
            f"{publish_age_min:.2f}" if publish_age_min is not None else "missing",
            f"{note_base};source=publish_marker;publish_class={publish_class};{publish_age_note};{terminal_age_note}",
        )
        return

    if terminal_age_min >= fail_after_minutes:
        status = "fail"
    elif terminal_age_min >= warn_after_minutes:
        status = "warn"
    else:
        status = "warn"
    _add(
        rows,
        "h_publish_marker_freshness",
        status,
        f"{publish_age_min:.2f}" if publish_age_min is not None else f"{terminal_age_min:.2f}",
        (
            f"{note_base};source=terminal_marker_fallback;publish_class={publish_class};"
            f"{publish_age_note};{terminal_age_note}"
        ),
    )


def _h_cycle_pause_requested() -> bool:
    return H_KILL_SWITCH_PATH.exists()


def _h_cycle_running() -> bool:
    lock_path = _first_existing_path(H_LOCK_PATH_CANDIDATES)
    if lock_path is None:
        return False
    try:
        payload = lock_path.read_text(encoding="utf-8")
    except Exception:
        return False
    pid = _parse_lock_pid(payload)
    if pid is None:
        # Lock exists but pid is unreadable - treat as running to avoid false timing WARNs.
        return True
    return _pid_alive(pid)


def _read_csv(path: Path, usecols: List[str] | None = None) -> pd.DataFrame:
    table = SQL_READER_TABLES.get(path.as_posix())
    if table:
        try:
            return read_dataframe_with_sql_fallback(path, table, dtype=str, usecols=usecols)
        except FileNotFoundError:
            return pd.DataFrame()
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, usecols=usecols)


def _order_key_series(df: pd.DataFrame, *, order_col: str = "Order ID", sku_col: str = "SKU") -> pd.Series:
    if df.empty or order_col not in df.columns or sku_col not in df.columns:
        return pd.Series([], dtype=str)
    return df[order_col].astype(str).str.strip() + "||" + df[sku_col].astype(str).str.strip()


def _read_order_key_file(path: Path) -> set[str]:
    df = _read_csv(path)
    if df.empty:
        return set()
    return set(_order_key_series(df).tolist())


def _order_master_l1_coverage_stats(
    l1: pd.DataFrame,
    order_master: pd.DataFrame,
    *,
    l1_missing_fee_keys_path: Path = L1_MISSING_FEE_KEYS,
    missing_token_orders_path: Path = MISSING_TOKEN_ORDERS,
) -> Dict[str, object]:
    l1_keys = set(_order_key_series(l1).tolist())
    master_keys = set(_order_key_series(order_master).tolist())
    observed_missing_fee_keys = _read_order_key_file(l1_missing_fee_keys_path)
    observed_missing_token_keys = _read_order_key_file(missing_token_orders_path)

    notes: List[str] = []
    if observed_missing_fee_keys:
        notes.append(f"observed_missing_fee_keys={len(observed_missing_fee_keys)}")
    if observed_missing_token_keys:
        notes.append(f"observed_missing_token_keys={len(observed_missing_token_keys)}")

    missing_set = l1_keys - master_keys
    orphan_set = master_keys - l1_keys
    return {
        "missing_set": missing_set,
        "missing_count": len(missing_set),
        "orphan_set": orphan_set,
        "orphan_count": len(orphan_set),
        "note": ";".join(notes),
    }


def _order_master_placeholder_stats(order_master: pd.DataFrame) -> Dict[str, object]:
    if order_master.empty:
        return {
            "placeholder_rows": 0,
            "missing_token_no_placeholder_rows": 0,
            "placeholder_repeat_sku_count": 0,
            "placeholder_repeat_row_count": 0,
            "placeholder_repeat_sample": [],
        }

    df = order_master.copy()
    qty = pd.to_numeric(df.get("Quantity Ordered", pd.Series([], dtype=str)), errors="coerce").fillna(0.0)
    lvl = df.get("lvl", pd.Series([], dtype=str)).astype(str).str.strip()
    target_rows = qty.gt(0) & lvl.ne("0")

    placeholder_flag = (
        df.get("COGS_Placeholder_Applied", pd.Series([], dtype=str))
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"1", "true", "yes", "y"})
    )
    missing_token_flag = (
        df.get("Missing_Token_Flag", pd.Series([], dtype=str))
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"1", "true", "yes", "y"})
    )

    placeholder_rows = int((target_rows & placeholder_flag).sum())
    missing_token_no_placeholder_rows = int((target_rows & missing_token_flag & ~placeholder_flag).sum())

    sku_series = df.get("SKU", pd.Series([], dtype=str)).astype(str).str.strip().str.upper()
    placeholder_skus = sku_series[target_rows & placeholder_flag]
    if placeholder_skus.empty:
        placeholder_repeat_sku_count = 0
        placeholder_repeat_row_count = 0
        placeholder_repeat_sample: List[str] = []
    else:
        sku_counts = placeholder_skus.value_counts()
        repeated = sku_counts[sku_counts > 1]
        placeholder_repeat_sku_count = int(len(repeated.index))
        placeholder_repeat_row_count = int(repeated.sum())
        placeholder_repeat_sample = [f"{sku}:{int(count)}" for sku, count in repeated.head(5).items()]

    return {
        "placeholder_rows": placeholder_rows,
        "missing_token_no_placeholder_rows": missing_token_no_placeholder_rows,
        "placeholder_repeat_sku_count": placeholder_repeat_sku_count,
        "placeholder_repeat_row_count": placeholder_repeat_row_count,
        "placeholder_repeat_sample": placeholder_repeat_sample,
    }


def _token_allocated_on_canceled_orders_stats(
    token_allocations: pd.DataFrame,
    orders_all_status: pd.DataFrame,
    order_master: pd.DataFrame,
) -> Dict[str, object]:
    required_alloc_cols = {"order_id", "seller_sku", "quantity", "token_id", "allocation_date"}
    if token_allocations.empty:
        return {
            "ready": True,
            "rows": 0,
            "units": 0,
            "sample": [],
            "details": pd.DataFrame(columns=["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"]),
            "notes": "allocations_empty",
        }
    if not required_alloc_cols.issubset(set(token_allocations.columns)):
        missing = sorted(required_alloc_cols - set(token_allocations.columns))
        return {
            "ready": False,
            "rows": 0,
            "units": 0,
            "sample": [],
            "details": pd.DataFrame(columns=["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"]),
            "notes": "missing_alloc_cols=" + ",".join(missing),
        }
    if orders_all_status.empty or {"amazon_order_id", "order_status"} - set(orders_all_status.columns):
        return {
            "ready": False,
            "rows": 0,
            "units": 0,
            "sample": [],
            "details": pd.DataFrame(columns=["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"]),
            "notes": "missing_orders_all_status",
        }

    canceled_ids = set(
        orders_all_status.loc[
            orders_all_status["order_status"].astype(str).str.strip().str.lower().eq("canceled"),
            "amazon_order_id",
        ]
        .astype(str)
        .str.strip()
        .tolist()
    )
    if not canceled_ids:
        return {
            "ready": True,
            "rows": 0,
            "units": 0,
            "sample": [],
            "details": pd.DataFrame(columns=["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"]),
            "notes": "no_canceled_orders",
        }

    demand_keys: set[str] = set()
    if not order_master.empty and {"Order ID", "SKU"}.issubset(set(order_master.columns)):
        qty = pd.to_numeric(order_master.get("Quantity Ordered", pd.Series([], dtype=str)), errors="coerce").fillna(0.0)
        lvl = order_master.get("lvl", pd.Series([], dtype=str)).astype(str).str.strip()
        active = qty.gt(0) & lvl.ne("0")
        demand_keys = set(
            (
                order_master.loc[active, "Order ID"].astype(str).str.strip()
                + "||"
                + order_master.loc[active, "SKU"].astype(str).str.strip()
            ).tolist()
        )

    alloc = token_allocations.copy()
    alloc["order_id"] = alloc["order_id"].astype(str).str.strip()
    alloc["seller_sku"] = alloc["seller_sku"].astype(str).str.strip()
    alloc["quantity_num"] = pd.to_numeric(alloc["quantity"], errors="coerce").fillna(1).clip(lower=0)
    alloc_key = alloc["order_id"] + "||" + alloc["seller_sku"]
    candidate = alloc[alloc["order_id"].isin(canceled_ids) & ~alloc_key.isin(demand_keys)].copy()
    if candidate.empty:
        return {
            "ready": True,
            "rows": 0,
            "units": 0,
            "sample": [],
            "details": pd.DataFrame(columns=["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"]),
            "notes": "none",
        }

    candidate["order_status"] = "Canceled"
    details = candidate[["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"]].copy()
    sample = (
        details.assign(_qty_num=candidate["quantity_num"])
        .head(5)
        .apply(lambda r: f"{r['order_id']}|{r['seller_sku']}|{int(float(r['_qty_num']))}", axis=1)
        .tolist()
    )
    return {
        "ready": True,
        "rows": int(len(details)),
        "units": int(candidate["quantity_num"].sum()),
        "sample": sample,
        "details": details,
        "notes": "canceled_allocations_detected",
    }


def _load_parked_sku_reasons(path: Path = PARKED_SKUS_PATH) -> Dict[str, str]:
    parked = _read_csv(path)
    if parked.empty or "sku" not in parked.columns:
        return {}
    if "reason" not in parked.columns:
        parked["reason"] = ""
    result: Dict[str, str] = {}
    for _, row in parked.iterrows():
        sku = str(row.get("sku", "")).strip().upper()
        if not sku:
            continue
        reason = str(row.get("reason", "")).strip() or "parked"
        result[sku] = reason
    return result


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_first_json(paths: List[Path]) -> Tuple[Dict[str, object], Path | None]:
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload, path
        except Exception:
            continue
    return {}, None


def _h_expected_empty_seller_profile_reason() -> str:
    state_payload, _ = _read_first_json(H_PRICING_STATE_PATH_CANDIDATES)
    if not state_payload:
        return ""
    reason = str(state_payload.get("seller_profile_warn_reason", "") or "").strip().lower()
    status = str(state_payload.get("seller_profile_status", "") or "").strip().lower()
    if reason in {"no_seller_rows_for_active_lab_skus", "all_rows_filtered_as_self", "forced_empty_for_diagnostics"}:
        if status in {"warn", "info", ""}:
            return reason
    return ""


def _latest_cycle_manifest(cycle: str) -> Path | None:
    manifest_dir = OUT / "manifests" / str(cycle).strip().upper()
    if not manifest_dir.exists():
        return None
    latest_path: Path | None = None
    latest_mtime = -1.0
    for path in manifest_dir.rglob("*.json"):
        try:
            mtime = float(path.stat().st_mtime)
        except Exception:
            continue
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = path
    return latest_path


def _a_stock_receipts_step_health(now_utc_dt: datetime) -> Dict[str, str]:
    manifest_path = _latest_cycle_manifest("A")
    if manifest_path is None:
        return {
            "status": "warn",
            "value": "missing_manifest",
            "notes": f"path={OUT / 'manifests' / 'A'}",
        }
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "warn",
            "value": "manifest_read_error",
            "notes": f"path={manifest_path};error={type(exc).__name__}:{exc}",
        }
    if not isinstance(payload, dict):
        return {
            "status": "warn",
            "value": "manifest_invalid",
            "notes": f"path={manifest_path}",
        }
    if "configured_step_count" not in payload or "final_state" not in payload:
        return {
            "status": "warn",
            "value": "manifest_truth_fields_missing",
            "notes": f"path={manifest_path};run_id={payload.get('run_id', '')}",
        }

    end_time_raw = str(payload.get("end_time", "") or payload.get("start_time", "")).strip()
    end_dt = pd.to_datetime(end_time_raw, errors="coerce", utc=True)
    age_hours = ""
    if pd.notna(end_dt):
        age_hours = f"{max((now_utc_dt - end_dt.to_pydatetime()).total_seconds() / 3600.0, 0.0):.2f}"
    else:
        age_hours = "n/a"

    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    configured_step_count = int(pd.to_numeric(pd.Series([payload.get("configured_step_count", len(steps))]), errors="coerce").fillna(len(steps)).iloc[0])
    recorded_step_count = int(pd.to_numeric(pd.Series([payload.get("recorded_step_count", len(steps))]), errors="coerce").fillna(len(steps)).iloc[0])
    final_state = str(payload.get("final_state", "") or "").strip().lower()
    health_summary = payload.get("health_summary", {})
    if not isinstance(health_summary, dict):
        health_summary = {}
    health_status = str(health_summary.get("status", "") or "").strip().lower() or "missing"
    current_cycle_evidence = bool(health_summary.get("current_cycle_evidence", False))
    receipt_step = None
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("name", "")).strip() == "process_stock_receipts_sheet.py":
            receipt_step = step
            break

    base_notes = (
        f"path={manifest_path};run_id={payload.get('run_id', '')};"
        f"end_time={end_time_raw};age_hours={age_hours};"
        f"final_state={final_state or 'missing'};"
        f"recorded_step_count={recorded_step_count};configured_step_count={configured_step_count};"
        f"health_status={health_status};current_cycle_evidence={'1' if current_cycle_evidence else '0'}"
    )
    if pd.notna(end_dt) and (now_utc_dt - end_dt.to_pydatetime()) > timedelta(hours=36):
        return {
            "status": "warn",
            "value": "stale_manifest",
            "notes": base_notes,
        }
    if receipt_step is not None:
        step_rc = int(step.get("rc", 1)) if isinstance((step := receipt_step), dict) else 1
        step_notes = str(step.get("notes", "") or "").strip()
        step_status = str(step.get("step_status", "") or "").strip().lower()
        if step_rc != 0:
            return {
                "status": "warn" if "guardrail blocked receipts" in step_notes.lower() else "fail",
                "value": str(step_rc),
                "notes": f"{base_notes};step_status={step_status};step_notes={step_notes}",
            }
        if step_status and step_status not in {"completed", "degraded", "skipped"}:
            return {
                "status": "warn",
                "value": f"step_{step_status}",
                "notes": f"{base_notes};step_notes={step_notes}",
            }
        return {
            "status": "ok",
            "value": "0",
            "notes": f"{base_notes};step_status={step_status};step_notes={step_notes}",
        }

    if configured_step_count > 0 and recorded_step_count < configured_step_count:
        return {
            "status": "warn",
            "value": "partial_cycle",
            "notes": base_notes,
        }
    if final_state in {"partial", "interrupted", "running"}:
        return {
            "status": "warn",
            "value": f"cycle_{final_state}",
            "notes": base_notes,
        }
    if not current_cycle_evidence:
        return {
            "status": "warn",
            "value": f"health_{health_status}",
            "notes": base_notes,
        }
    return {
        "status": "warn",
        "value": "step_missing",
        "notes": base_notes,
    }


def _first_existing_path(paths: List[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            open_process = kernel32.OpenProcess
            open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            open_process.restype = wintypes.HANDLE
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL
            get_exit_code = kernel32.GetExitCodeProcess
            get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            get_exit_code.restype = wintypes.BOOL

            handle = open_process(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if handle:
                try:
                    exit_code = wintypes.DWORD(0)
                    if bool(get_exit_code(handle, ctypes.byref(exit_code))):
                        return int(exit_code.value) == STILL_ACTIVE
                    return True
                finally:
                    close_handle(handle)
            last_error = ctypes.get_last_error()
            if int(last_error or 0) == 5:
                return True
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = f"{result.stdout or ''}\n{result.stderr or ''}".strip().lower()
            if not out:
                return False
            if "no tasks are running" in out:
                return False
            return f"\"{int(pid)}\"" in out or str(int(pid)) in out
        except Exception:
            return False
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        # Process exists but signal probe is not permitted on this platform/user.
        return True
    except Exception:
        return False


def _a016_refresh_running_pids() -> List[int]:
    pids: List[int] = []
    if os.name == "nt":
        try:
            probe = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "Get-CimInstance Win32_Process | "
                        "Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*A016_refresh_phase1_daily_intel.py*' } | "
                        "Select-Object -ExpandProperty ProcessId"
                    ),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            for raw in (probe.stdout or "").splitlines():
                text = str(raw or "").strip()
                if not text:
                    continue
                try:
                    pid = int(text)
                except Exception:
                    continue
                if pid > 0:
                    pids.append(pid)
        except Exception:
            return []
    else:
        try:
            probe = subprocess.run(
                ["pgrep", "-f", "A016_refresh_phase1_daily_intel.py"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            for raw in (probe.stdout or "").splitlines():
                text = str(raw or "").strip()
                if not text:
                    continue
                try:
                    pid = int(text)
                except Exception:
                    continue
                if pid > 0:
                    pids.append(pid)
        except Exception:
            return []
    unique: List[int] = []
    seen: set[int] = set()
    for pid in pids:
        if pid in seen:
            continue
        seen.add(pid)
        unique.append(pid)
    return unique


def _a016_refresh_is_running() -> bool:
    return len(_a016_refresh_running_pids()) > 0


def _parse_lock_pid(payload: str) -> int | None:
    parts = [p.strip() for p in str(payload or "").split("|") if p.strip()]
    for part in parts:
        if part.startswith("pid="):
            try:
                return int(part.split("=", 1)[1].strip())
            except Exception:
                return None
    return None


def _parse_lock_value(payload: str, key: str) -> str:
    parts = [p.strip() for p in str(payload or "").split("|") if p.strip()]
    for part in parts:
        if part.startswith(f"{key}="):
            return str(part.split("=", 1)[1]).strip()
    return ""


def _parse_lock_utc(payload: str, key: str) -> datetime | None:
    raw = _parse_lock_value(payload, key)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _lock_age_seconds(payload: str, now_utc: datetime) -> float | None:
    lock_utc = _parse_lock_utc(payload, "heartbeat") or _parse_lock_utc(payload, "start")
    if lock_utc is None:
        return None
    try:
        return max((now_utc - lock_utc).total_seconds(), 0.0)
    except Exception:
        return None


def _cycle_stale_lock_check(
    rows: List[Dict[str, str]],
    check_name: str,
    candidates: List[Path] | Tuple[Path, ...],
    *,
    now_utc: datetime | None = None,
) -> None:
    existing = [p for p in candidates if p.exists()]
    if not existing:
        _add(rows, check_name, "ok", "0", f"searched={','.join([str(p) for p in candidates])}")
        return
    probe_now = now_utc or datetime.now(timezone.utc)
    active_paths: List[str] = []
    active_pids: List[int] = []
    dead_paths: List[Tuple[Path, str, int | None, float | None]] = []
    unreadable_paths: List[str] = []
    for lock_path in existing:
        try:
            payload = lock_path.read_text(encoding="utf-8")
            pid = _parse_lock_pid(payload)
            if pid is None:
                unreadable_paths.append(str(lock_path))
                continue
            if _pid_alive(pid):
                active_paths.append(f"{lock_path}|pid={pid}")
                active_pids.append(pid)
                continue
            dead_paths.append((lock_path, payload, pid, _lock_age_seconds(payload, probe_now)))
        except Exception:
            unreadable_paths.append(str(lock_path))

    unique_active_pids = sorted({int(pid) for pid in active_pids})
    if len(unique_active_pids) > 1:
        _add(
            rows,
            check_name,
            "fail",
            str(len(unique_active_pids)),
            f"active_conflict={';'.join(active_paths)}",
        )
        return

    cleared_dead: List[str] = []
    unresolved_dead: List[str] = []
    for dead_path, _payload, pid, age_seconds in dead_paths:
        dead_note = f"{dead_path}|pid={pid}"
        if age_seconds is not None:
            dead_note = f"{dead_note}|age_seconds={int(age_seconds)}"
        try:
            dead_path.unlink(missing_ok=True)
            cleared_dead.append(dead_note)
        except Exception:
            unresolved_dead.append(dead_note)

    if unresolved_dead:
        _add(
            rows,
            check_name,
            "fail",
            str(len(unresolved_dead)),
            f"stale_unresolved={';'.join(unresolved_dead)}",
        )
    elif active_paths:
        if cleared_dead:
            _add(
                rows,
                check_name,
                "ok",
                "0",
                f"active={';'.join(active_paths)};cleared_stale={';'.join(cleared_dead)}",
            )
        else:
            _add(rows, check_name, "ok", "0", f"active={';'.join(active_paths)}")
    elif cleared_dead:
        _add(rows, check_name, "ok", "0", f"cleared_stale={';'.join(cleared_dead)}")
    elif unreadable_paths:
        _add(rows, check_name, "warn", str(len(unreadable_paths)), f"unreadable={';'.join(unreadable_paths)}")
    else:
        _add(rows, check_name, "ok", "0", f"path={existing[0]}")


def _to_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _add(rows: List[Dict[str, str]], check: str, status: str, value: str, notes: str = "") -> None:
    rows.append({"check": check, "status": status, "value": value, "notes": notes})


def _status_from_gap(hours_gap: float) -> str:
    if hours_gap <= 2:
        return "ok"
    if hours_gap <= 12:
        return "warn"
    return "fail"


def _cycle_for_check(check: str) -> str:
    name = str(check or "").strip().lower()
    if not name:
        return "shared"
    if name.startswith("a_"):
        return "A"
    if name.startswith("h_"):
        return "H"
    if name.startswith("e_"):
        return "E"
    if name.startswith("c_"):
        return "C"
    if name.startswith("f_"):
        return "F"
    if name.startswith("o_"):
        return "O"
    if name.startswith("z_"):
        return "Z"
    b_prefixes = (
        "b_",
        "l1_",
        "l2_",
        "l3_",
        "order_master_",
        "orders_",
        "token_",
        "orphan_",
    )
    if name.startswith(b_prefixes):
        return "B"
    b_exact = {
        "l1_keys_missing_in_master",
        "order_master_orphans_count",
        "order_master_blank_cogs_lvl1plus",
        "l3_orphans_count",
    }
    if name in b_exact:
        return "B"
    return "shared"


def _write_cycle_alert_files(df_out: pd.DataFrame) -> None:
    CYCLE_ALERT_DIR.mkdir(parents=True, exist_ok=True)
    df_all = df_out.copy()
    df_all["cycle"] = df_all.get("check", "").map(_cycle_for_check)
    # canonical full snapshot in cycle folder
    df_all.to_csv(CYCLE_ALERT_DIR / "checklist_all.csv", index=False)

    for cycle in ["A", "B", "H", "E", "C", "F", "O", "Z", "shared"]:
        scoped = df_all[df_all["cycle"] == cycle].copy()
        _write_health_checklist_csv(scoped, CYCLE_ALERT_DIR / f"checklist_{cycle}.csv")

    summary_rows: List[Dict[str, str]] = []
    for cycle in ["all", "A", "B", "H", "E", "C", "F", "O", "Z", "shared"]:
        scoped = df_all if cycle == "all" else df_all[df_all["cycle"] == cycle]
        status = scoped.get("status", pd.Series(dtype=str)).astype(str).str.lower()
        fail_count = int(status.eq("fail").sum())
        warn_count = int(status.eq("warn").sum())
        summary_rows.append(
            {
                "cycle": cycle,
                "rows": str(int(len(scoped.index))),
                "fail_count": str(fail_count),
                "warn_count": str(warn_count),
            }
        )
    pd.DataFrame(summary_rows).to_csv(CYCLE_ALERT_DIR / "summary.csv", index=False)


def _normalize_profile(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"global", "a", "b", "e", "h"}:
        return raw
    return "global"


def _default_checklist_for_profile(profile: str) -> Path:
    if profile == "a":
        return CHECKLIST_A_SPLIT_CSV
    if profile == "b":
        return CHECKLIST_B_SPLIT_CSV
    if profile == "e":
        return CHECKLIST_E_SPLIT_CSV
    if profile == "h":
        return CHECKLIST_H_GATE_CSV
    return CHECKLIST_CSV


def _default_alert_state_for_profile(profile: str) -> Path:
    if profile == "a":
        return ALERT_STATE_A_CSV
    if profile == "b":
        return ALERT_STATE_B_CSV
    if profile == "e":
        return ALERT_STATE_E_CSV
    if profile == "h":
        return ALERT_STATE_H_CSV
    return ALERT_STATE_CSV


def _default_alert_history_for_profile(profile: str) -> Path:
    if profile == "a":
        return ALERT_HISTORY_A_CSV
    if profile == "b":
        return ALERT_HISTORY_B_CSV
    if profile == "e":
        return ALERT_HISTORY_E_CSV
    if profile == "h":
        return ALERT_HISTORY_H_CSV
    return ALERT_HISTORY_CSV


def _default_health_status_for_profile(profile: str) -> Path:
    if profile == "a":
        return HEALTH_STATUS_A_CSV
    if profile == "b":
        return HEALTH_STATUS_B_CSV
    if profile == "e":
        return HEALTH_STATUS_E_CSV
    if profile == "h":
        return HEALTH_STATUS_H_CSV
    return HEALTH_STATUS_CSV


def _profile_filter_mask(df: pd.DataFrame, profile: str) -> pd.Series:
    if "check" not in df.columns:
        return pd.Series([False] * len(df.index), index=df.index)
    cycles = df["check"].astype(str).map(_cycle_for_check)
    if profile == "a":
        return cycles.eq("A")
    if profile == "b":
        return cycles.eq("B")
    if profile == "e":
        return cycles.eq("E")
    if profile == "h":
        return cycles.eq("H")
    return pd.Series([True] * len(df.index), index=df.index)


def _stabilize_index(df: pd.DataFrame) -> pd.DataFrame:
    """Force a plain Int64 index to avoid intermittent RangeIndex C-extension crashes."""
    out = df.copy()
    try:
        out.index = pd.Index([int(i) for i in range(int(out.shape[0]))], dtype="int64")
    except Exception:
        pass
    return out


def _build_arg_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build system health checklist", add_help=add_help)
    parser.add_argument(
        "--profile",
        choices=["global", "a", "b", "e", "h"],
        default="global",
        help="Health profile scope. global keeps existing full-system behavior.",
    )
    parser.add_argument(
        "--checklist-path",
        default="",
        help="Optional output path override for checklist CSV.",
    )
    parser.add_argument(
        "--alert-state-path",
        default="",
        help="Optional output path override for alert aging state CSV.",
    )
    parser.add_argument(
        "--alert-history-path",
        default="",
        help="Optional output path override for alert lifecycle history CSV.",
    )
    parser.add_argument(
        "--health-status-path",
        default="",
        help="Optional output path override for health status CSV.",
    )
    parser.add_argument(
        "--no-toast",
        action="store_true",
        help="Disable toast notifications for this run.",
    )
    return parser


def _parse_cli_args(argv: List[str] | None = None, *, strict: bool = True) -> argparse.Namespace:
    parser = _build_arg_parser(add_help=strict)
    if strict:
        return parser.parse_args(argv)
    args, _unknown = parser.parse_known_args(argv)
    return args


def _resolve_runtime_paths(args: argparse.Namespace) -> dict:
    profile = _normalize_profile(getattr(args, "profile", "global"))
    checklist_path = Path(getattr(args, "checklist_path", "") or _default_checklist_for_profile(profile))
    alert_state_override = str(getattr(args, "alert_state_path", "") or "").strip()
    alert_state_path = Path(alert_state_override or _default_alert_state_for_profile(profile))
    alert_history_override = str(getattr(args, "alert_history_path", "") or "").strip()
    if alert_history_override:
        alert_history_path = Path(alert_history_override)
    elif alert_state_override:
        history_name = alert_state_path.name.replace("alert_state", "alert_history")
        if history_name == alert_state_path.name:
            history_name = f"{alert_state_path.stem}.history{alert_state_path.suffix}"
        alert_history_path = alert_state_path.with_name(history_name)
    else:
        alert_history_path = _default_alert_history_for_profile(profile)
    health_status_path = Path(getattr(args, "health_status_path", "") or _default_health_status_for_profile(profile))
    no_toast = bool(getattr(args, "no_toast", False))
    return {
        "profile": profile,
        "checklist_path": checklist_path,
        "alert_state_path": alert_state_path,
        "alert_history_path": alert_history_path,
        "health_status_path": health_status_path,
        "no_toast": no_toast,
    }


def _schema_check(rows: List[Dict[str, str]], name: str, path: Path, required_cols: List[str], optional: bool = False) -> None:
    if not path.exists():
        status = "warn" if optional else "fail"
        _add(rows, name, status, "missing", f"path {path}")
        return
    try:
        df = pd.read_csv(path, nrows=1, dtype=str)
    except Exception as exc:
        _add(rows, name, "fail", "read_error", str(exc))
        return
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        _add(rows, name, "fail" if not optional else "warn", "missing_cols", ",".join(missing))
    else:
        _add(rows, name, "ok", "ok", "")


def _cycle_failure_ledger_schema_check(rows: List[Dict[str, str]], path: Path = CYCLE_FAILURE_EVENTS_PATH) -> None:
    ok, reason = validate_cycle_failure_events_schema(path)
    status = "ok" if ok else "fail"
    value = "ok" if ok else "invalid"
    required = ",".join(FAILURE_EVENT_COLUMNS)
    _add(rows, "shared_cycle_failure_ledger_schema", status, value, f"path {path};reason={reason};required={required}")


def _required_non_blank_check(
    rows: List[Dict[str, str]],
    name: str,
    path: Path,
    required_cols: List[str],
    *,
    optional: bool = False,
) -> None:
    if not path.exists():
        status = "warn" if optional else "fail"
        _add(rows, name, status, "missing", f"path {path}")
        return
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        _add(rows, name, "fail", "read_error", str(exc))
        return
    if df.empty:
        status = "warn" if optional else "ok"
        _add(rows, name, status, "0", "empty")
        return
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        _add(rows, name, "fail" if not optional else "warn", "missing_cols", ",".join(missing))
        return
    blank_counts: List[str] = []
    bad_total = 0
    for col in required_cols:
        blanks = int(df[col].astype(str).str.strip().eq("").sum())
        if blanks > 0:
            blank_counts.append(f"{col}:{blanks}")
            bad_total += blanks
    if bad_total > 0:
        _add(
            rows,
            name,
            "fail" if not optional else "warn",
            str(bad_total),
            "blank_required=" + ",".join(blank_counts),
        )
        return
    _add(rows, name, "ok", "0", "")


def _phase1_contract_checks(rows: List[Dict[str, str]], path: Path) -> None:
    if not path.exists():
        _add(rows, "h_phase1_contract_types", "warn", "missing", f"path {path}")
        _add(rows, "h_phase1_history_idempotent", "warn", "missing", f"path {path}")
        return

    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        _add(rows, "h_phase1_contract_types", "fail", "read_error", str(exc))
        _add(rows, "h_phase1_history_idempotent", "fail", "read_error", str(exc))
        return

    if df.empty:
        _add(rows, "h_phase1_contract_types", "warn", "empty", "")
        _add(rows, "h_phase1_history_idempotent", "warn", "empty", "")
        return

    required_non_null = [
        "timestamp_utc",
        "asof_date",
        "marketplace",
        "sku",
        "asin",
        "seller_id",
        "seller_seen_flag",
        "source",
    ]
    bad_non_null = 0
    for col in required_non_null:
        if col not in df.columns:
            bad_non_null += len(df)
            continue
        bad_non_null += int(df[col].astype(str).str.strip().eq("").sum())

    bad_date = 0
    if "asof_date" in df.columns:
        asof = df["asof_date"].astype(str).str.strip()
        non_blank = asof.ne("")
        bad_date = int((non_blank & pd.to_datetime(asof, format="%Y-%m-%d", errors="coerce").isna()).sum())
    else:
        bad_date = len(df)

    datetime_cols = ["timestamp_utc", "first_seen_timestamp", "last_seen_timestamp"]
    bad_datetime = 0
    for col in datetime_cols:
        if col not in df.columns:
            continue
        vals = df[col].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_datetime += int((non_blank & pd.to_datetime(vals, errors="coerce", utc=True).isna()).sum())

    numeric_cols = [
        "continuous_presence_hours",
        "absence_gap_hours",
        "offer_price_gbp",
        "min_price_seen_gbp",
        "max_price_seen_gbp",
        "median_price_seen_gbp",
        "time_at_min_price_hours",
        "time_at_max_price_hours",
        "price_move_initiations",
        "follow_events",
        "reaction_lag_minutes",
        "floor_set_events",
        "min_delivery_days",
        "max_delivery_days",
        "delivery_range_days",
        "delivery_delta_vs_fastest_days",
        "our_price",
        "our_price_changes",
        "manual_interventions",
    ]
    bad_numeric = 0
    for col in numeric_cols:
        if col not in df.columns:
            continue
        vals = df[col].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_numeric += int((non_blank & pd.to_numeric(vals, errors="coerce").isna()).sum())

    allowed_binary = {"0", "1"}
    binary_cols = ["seller_seen_flag", "reentry_after_absence_flag", "is_prime"]
    bad_binary = 0
    for col in binary_cols:
        if col not in df.columns:
            continue
        vals = df[col].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_binary += int((non_blank & ~vals.isin(allowed_binary)).sum())

    bad_direction = 0
    if "directional_bias" in df.columns:
        vals = df["directional_bias"].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_direction = int((non_blank & ~vals.isin({"up", "down", "flat"})).sum())

    bad_channel = 0
    if "fulfilment_channel" in df.columns:
        vals = df["fulfilment_channel"].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_channel = int((non_blank & ~vals.isin({"FBA", "FBM", "Unknown"})).sum())

    bad_types_total = bad_non_null + bad_date + bad_datetime + bad_numeric + bad_binary + bad_direction + bad_channel
    type_notes = (
        f"non_null={bad_non_null};bad_date={bad_date};bad_datetime={bad_datetime};"
        f"bad_numeric={bad_numeric};bad_binary={bad_binary};bad_direction={bad_direction};bad_channel={bad_channel}"
    )
    _add(
        rows,
        "h_phase1_contract_types",
        "ok" if bad_types_total == 0 else "fail",
        str(bad_types_total),
        type_notes,
    )

    idempotent_keys = ["asof_date", "marketplace", "sku", "asin", "seller_id"]
    missing_keys = [c for c in idempotent_keys if c not in df.columns]
    if missing_keys:
        _add(rows, "h_phase1_history_idempotent", "fail", "missing_keys", ",".join(missing_keys))
    else:
        dup_count = int(df.duplicated(subset=idempotent_keys, keep=False).sum())
        _add(rows, "h_phase1_history_idempotent", "ok" if dup_count == 0 else "fail", str(dup_count), "global_key_check")


def _schema_check_jsonl(rows: List[Dict[str, str]], name: str, path: Path, required_cols: List[str], optional: bool = False) -> None:
    if not path.exists():
        status = "warn" if optional else "fail"
        _add(rows, name, status, "missing", f"path {path}")
        return
    try:
        last_payload: Dict[str, object] | None = None
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    last_payload = obj
    except Exception as exc:
        _add(rows, name, "fail", "read_error", str(exc))
        return
    if last_payload is None:
        status = "warn" if optional else "fail"
        _add(rows, name, status, "empty", "")
        return
    present = set([str(k) for k in last_payload.keys()])
    missing = [c for c in required_cols if c not in present]
    if missing:
        _add(rows, name, "fail" if not optional else "warn", "missing_cols", ",".join(missing))
    else:
        _add(rows, name, "ok", "ok", "")


def _schema_check_json_object(
    rows: List[Dict[str, str]],
    name: str,
    path: Path,
    required_keys: List[str],
    optional: bool = False,
) -> None:
    if not path.exists():
        status = "warn" if optional else "fail"
        _add(rows, name, status, "missing", f"path {path}")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _add(rows, name, "fail", "read_error", str(exc))
        return
    if not isinstance(payload, dict):
        _add(rows, name, "fail" if not optional else "warn", "invalid_type", type(payload).__name__)
        return
    missing = [k for k in required_keys if k not in payload]
    if missing:
        _add(rows, name, "fail" if not optional else "warn", "missing_keys", ",".join(missing))
        return
    _add(rows, name, "ok", "ok", "")


def _read_last_health_status(path: Path = HEALTH_STATUS_CSV) -> str:
    if not path.exists():
        return ""
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception:
        return ""
    if df.empty or "status" not in df.columns:
        return ""
    return str(df.iloc[-1]["status"]).strip().upper()


ALERT_STATE_COLUMNS = ["check", "status", "first_seen_utc", "last_seen_utc", "consecutive_runs"]
ALERT_HISTORY_COLUMNS = [
    "event_utc",
    "event_type",
    "check",
    "status",
    "instance_first_seen_utc",
    "instance_last_seen_utc",
    "consecutive_runs",
    "cleared_by_status",
    "clear_reason",
    "evidence_source",
    "evidence_utc",
    "profile",
]


def _read_alert_state(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=ALERT_STATE_COLUMNS)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame(columns=ALERT_STATE_COLUMNS)
    for col in ALERT_STATE_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[ALERT_STATE_COLUMNS]


def _append_alert_history(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    df_new = pd.DataFrame(rows, columns=ALERT_HISTORY_COLUMNS)
    if not path.exists():
        df_new.to_csv(path, index=False)
        return
    try:
        existing = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        existing = pd.DataFrame(columns=ALERT_HISTORY_COLUMNS)
    for col in ALERT_HISTORY_COLUMNS:
        if col not in existing.columns:
            existing[col] = ""
    merged = pd.concat([existing[ALERT_HISTORY_COLUMNS], df_new], ignore_index=True)
    merged.to_csv(path, index=False)


def _apply_alert_aging(
    df_out: pd.DataFrame,
    state_path: Path,
    now_utc: datetime,
    *,
    history_path: Path | None = None,
    recompute_source: str = "",
    profile: str = "global",
) -> pd.DataFrame:
    prev = _read_alert_state(state_path)
    prev_map = {
        str(r["check"]).strip(): {
            "status": str(r["status"]).strip().lower(),
            "first_seen_utc": str(r["first_seen_utc"]).strip(),
            "last_seen_utc": str(r["last_seen_utc"]).strip(),
            "consecutive_runs": str(r["consecutive_runs"]).strip(),
        }
        for _, r in prev.iterrows()
    }

    first_seen_vals: List[str] = []
    last_seen_vals: List[str] = []
    streak_vals: List[str] = []
    age_hours_vals: List[str] = []
    next_state_rows: List[Dict[str, str]] = []
    history_rows: List[Dict[str, str]] = []
    opened_keys: set[str] = set()
    now_iso = now_utc.isoformat()
    evidence_source = recompute_source or "current_checklist"
    latest_status_by_check: Dict[str, str] = {}
    for _, row in df_out.iterrows():
        check_name = str(row.get("check", "")).strip()
        if not check_name:
            continue
        latest_status_by_check[check_name] = str(row.get("status", "")).strip().lower()

    for _, row in df_out.iterrows():
        check = str(row.get("check", "")).strip()
        status = str(row.get("status", "")).strip().lower()
        if status not in {"fail", "warn"}:
            first_seen_vals.append("")
            last_seen_vals.append("")
            streak_vals.append("")
            age_hours_vals.append("")
            continue

        prev_row = prev_map.get(check, {})
        prev_status = str(prev_row.get("status", "")).strip().lower()
        prev_first = str(prev_row.get("first_seen_utc", "")).strip()
        prev_streak_raw = str(prev_row.get("consecutive_runs", "")).strip()
        try:
            prev_streak = int(prev_streak_raw) if prev_streak_raw else 0
        except Exception:
            prev_streak = 0

        if prev_status == status and prev_first:
            first_seen = prev_first
            streak = prev_streak + 1 if prev_streak > 0 else 1
            opened_new_instance = False
        else:
            first_seen = now_iso
            streak = 1
            opened_new_instance = True

        age_hours = ""
        try:
            first_dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
            if first_dt.tzinfo is None:
                first_dt = first_dt.replace(tzinfo=timezone.utc)
            age_hours = f"{max((now_utc - first_dt).total_seconds() / 3600.0, 0.0):.2f}"
        except Exception:
            age_hours = ""

        first_seen_vals.append(first_seen)
        last_seen_vals.append(now_iso)
        streak_vals.append(str(streak))
        age_hours_vals.append(age_hours)
        next_state_rows.append(
            {
                "check": check,
                "status": status,
                "first_seen_utc": first_seen,
                "last_seen_utc": now_iso,
                "consecutive_runs": str(streak),
            }
        )
        if opened_new_instance:
            opened_keys.add(check)
            if prev_status in {"fail", "warn"} and prev_first and prev_status != status:
                history_rows.append(
                    {
                        "event_utc": now_iso,
                        "event_type": "cleared",
                        "check": check,
                        "status": prev_status,
                        "instance_first_seen_utc": prev_first,
                        "instance_last_seen_utc": str(prev_row.get("last_seen_utc", "")).strip() or now_iso,
                        "consecutive_runs": str(prev_row.get("consecutive_runs", "")).strip(),
                        "cleared_by_status": status,
                        "clear_reason": "status_transition",
                        "evidence_source": evidence_source,
                        "evidence_utc": now_iso,
                        "profile": profile,
                    }
                )
            history_rows.append(
                {
                    "event_utc": now_iso,
                    "event_type": "opened",
                    "check": check,
                    "status": status,
                    "instance_first_seen_utc": first_seen,
                    "instance_last_seen_utc": now_iso,
                    "consecutive_runs": str(streak),
                    "cleared_by_status": "",
                    "clear_reason": "",
                    "evidence_source": evidence_source,
                    "evidence_utc": now_iso,
                    "profile": profile,
                }
            )

    df_out = df_out.copy()
    df_out["alert_first_seen_utc"] = first_seen_vals
    df_out["alert_last_seen_utc"] = last_seen_vals
    df_out["alert_consecutive_runs"] = streak_vals
    df_out["alert_age_hours"] = age_hours_vals
    pd.DataFrame(next_state_rows, columns=ALERT_STATE_COLUMNS).to_csv(state_path, index=False)
    prev_active_keys = {k for k, v in prev_map.items() if str(v.get("status", "")).strip().lower() in {"fail", "warn"}}
    current_active_keys = {str(r.get("check", "")).strip() for r in next_state_rows}
    carried_keys = prev_active_keys.intersection(current_active_keys)
    cleared_keys = prev_active_keys.difference(current_active_keys)
    for check in sorted(cleared_keys):
        prev_row = prev_map.get(check, {})
        prev_status = str(prev_row.get("status", "")).strip().lower()
        prev_first = str(prev_row.get("first_seen_utc", "")).strip()
        if prev_status not in {"fail", "warn"} or not prev_first:
            continue
        cleared_by_status = latest_status_by_check.get(check, "") or "missing"
        history_rows.append(
            {
                "event_utc": now_iso,
                "event_type": "cleared",
                "check": check,
                "status": prev_status,
                "instance_first_seen_utc": prev_first,
                "instance_last_seen_utc": str(prev_row.get("last_seen_utc", "")).strip() or now_iso,
                "consecutive_runs": str(prev_row.get("consecutive_runs", "")).strip(),
                "cleared_by_status": cleared_by_status,
                "clear_reason": "contradicted_by_newer_healthy_evidence",
                "evidence_source": evidence_source,
                "evidence_utc": now_iso,
                "profile": profile,
            }
        )
    if history_path is not None:
        _append_alert_history(history_path, history_rows)
    print(
        "[health_check] alert_state_reconcile "
        f"profile={profile} "
        f"keys_total={len(df_out.index)} "
        f"opened_warn_fail={len(opened_keys)} "
        f"carried_warn_fail={len(carried_keys)} "
        f"cleared_to_ok={len(cleared_keys)} "
        f"recomputed_from={recompute_source or 'current_checklist'} "
        f"state_path={state_path} "
        f"history_path={history_path or ''} "
        f"ts={now_iso} "
        f"cleared_sample={','.join(sorted(list(cleared_keys))[:5])}"
    )
    return df_out


def _latest_snapshot(glob_name: str) -> Path | None:
    candidates = sorted(OUT.glob(glob_name))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _preferred_seller_snapshot_path() -> Path | None:
    run_id = os.environ.get("H_RUN_ID", "").strip()
    if run_id:
        run_scoped = OUT / RUN_SCOPED_SELLER_SNAPSHOT_REL / run_id / "listing_offer_seller_snapshot.csv"
        if run_scoped.exists():
            return run_scoped
    return _latest_snapshot(LISTING_OFFER_SELLER_SNAPSHOT_GLOB)


def _max_asof_date(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        df = pd.read_csv(path, usecols=["asof_date"], dtype=str).fillna("")
    except Exception:
        return ""
    if df.empty or "asof_date" not in df.columns:
        return ""
    vals = (
        df["asof_date"]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
    )
    if vals.empty:
        return ""
    return str(vals.max())


def _today_listing_offer_snapshot_asof(today_utc: str) -> str:
    snapshot_path = OUT / f"listing_offer_snapshot_{today_utc}.csv"
    if not snapshot_path.exists():
        return ""
    try:
        mtime_utc = datetime.fromtimestamp(snapshot_path.stat().st_mtime, tz=timezone.utc).date().isoformat()
    except Exception:
        return ""
    if mtime_utc != today_utc:
        return ""
    asof = _max_asof_date(snapshot_path)
    if asof != today_utc:
        return ""
    return asof


def _safe_int(value: object) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _safe_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        out = float(text)
        if out != out:
            return None
        return out
    except Exception:
        return None


def _o_net_fee_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def _o_net_fee_truthy(value: object) -> bool:
    return _o_net_fee_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _o_net_fee_sku_key(value: object) -> str:
    return _o_net_fee_text(value).upper()


def _o_net_fee_series(df: pd.DataFrame, column: str) -> pd.Series:
    if df.empty or column not in df.columns:
        return pd.Series([""] * len(df.index), index=df.index, dtype=str)
    return df[column].fillna("").astype(str).map(_o_net_fee_text)


def _read_o_net_fee_csv(path: Path) -> Tuple[pd.DataFrame, str, str]:
    if not path.exists():
        return pd.DataFrame(), "missing", f"path={path}"
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(), "empty", f"path={path};empty_file=1"
    except Exception as exc:
        return pd.DataFrame(), "read_error", f"path={path};error={exc.__class__.__name__}:{exc}"
    if df.empty:
        return df, "empty", f"path={path};rows=0"
    return df, "ok", f"path={path};rows={len(df.index)}"


def _o_net_fee_field_errors(row: pd.Series, required_fields: Tuple[str, ...]) -> List[str]:
    errors: List[str] = []
    for field in required_fields:
        value = _o_net_fee_text(row.get(field, ""))
        if value == "":
            errors.append(field)
            continue
        if field in O_NET_FEE_NUMERIC_FIELDS:
            parsed = _safe_float(value)
            if parsed is None:
                errors.append(f"{field}:invalid")
            elif field in O_NET_FEE_POSITIVE_FIELDS and parsed <= 0:
                errors.append(f"{field}:nonpositive")
    return errors


def _o_net_fee_rows_by_sku(df: pd.DataFrame) -> Dict[str, pd.Series]:
    if df.empty or "seller_sku" not in df.columns:
        return {}
    out: Dict[str, pd.Series] = {}
    for _, row in df.iterrows():
        sku_key = _o_net_fee_sku_key(row.get("seller_sku", ""))
        if sku_key:
            out[sku_key] = row
    return out


def _o_net_fee_action_mask(df: pd.DataFrame, *, flag_column: str, action_column: str) -> pd.Series:
    if df.empty:
        return pd.Series([], dtype=bool)
    if flag_column in df.columns:
        return _o_net_fee_series(df, flag_column).map(_o_net_fee_truthy).astype(bool)
    if action_column in df.columns:
        return _o_net_fee_series(df, action_column).str.lower().isin(O_NET_FEE_ACTION_STATUSES)
    return pd.Series([False] * len(df.index), index=df.index, dtype=bool)


def _o_net_fee_collect_action_skus(
    coverage_df: pd.DataFrame,
    recommendation_df: pd.DataFrame,
) -> Tuple[set[str], pd.DataFrame, pd.DataFrame, int]:
    action_skus: set[str] = set()
    missing_sku_rows = 0

    coverage_action = coverage_df.iloc[0:0].copy()
    if not coverage_df.empty:
        coverage_mask = _o_net_fee_action_mask(
            coverage_df,
            flag_column="action_ready_now",
            action_column="suggested_action",
        )
        coverage_action = coverage_df.loc[coverage_mask].copy()
        for _, row in coverage_action.iterrows():
            sku_key = _o_net_fee_sku_key(row.get("seller_sku", ""))
            if sku_key:
                action_skus.add(sku_key)
            else:
                missing_sku_rows += 1

    recommendation_action = recommendation_df.iloc[0:0].copy()
    if not recommendation_df.empty:
        rec_mask = _o_net_fee_action_mask(
            recommendation_df,
            flag_column="",
            action_column="recommendation_status",
        )
        recommendation_action = recommendation_df.loc[rec_mask].copy()
        for _, row in recommendation_action.iterrows():
            sku_key = _o_net_fee_sku_key(row.get("seller_sku", ""))
            if sku_key:
                action_skus.add(sku_key)
            else:
                missing_sku_rows += 1

    return action_skus, coverage_action, recommendation_action, missing_sku_rows


def _o_net_fee_bad_status(row: pd.Series) -> bool:
    return _o_net_fee_text(row.get("net_fee_model_status", "")).lower() != "fresh"


def _o_net_fee_bad_age(row: pd.Series, max_age_hours: float) -> bool:
    age = _safe_float(row.get("net_fee_model_age_hours", ""))
    return age is None or age > max_age_hours


def _o_net_fee_first_float(row: pd.Series, fallback_row: pd.Series | None, fields: Tuple[str, ...]) -> float | None:
    for source_row in (row, fallback_row):
        if source_row is None:
            continue
        for field in fields:
            parsed = _safe_float(source_row.get(field, ""))
            if parsed is not None:
                return parsed
    return None


def _o_net_fee_first_text(row: pd.Series, fallback_row: pd.Series | None, fields: Tuple[str, ...]) -> str:
    for source_row in (row, fallback_row):
        if source_row is None:
            continue
        for field in fields:
            text = _o_net_fee_text(source_row.get(field, ""))
            if text:
                return text
    return ""


def _o_net_fee_roi_compare_applicable(row: pd.Series, fallback_row: pd.Series | None) -> bool:
    status = _o_net_fee_first_text(row, fallback_row, ("net_fee_model_status",)).lower()
    current_cost = _o_net_fee_first_float(
        row,
        fallback_row,
        ("expected_sell_pack_cost_gbp", "current_supplier_buy_cost_gbp"),
    )
    market_price = _o_net_fee_first_float(row, fallback_row, ("market_price_gbp",))
    market_price_ex_vat = _o_net_fee_first_float(row, fallback_row, ("market_price_ex_vat_gbp",))
    return (
        status == "fresh"
        and current_cost is not None
        and current_cost > 0
        and market_price is not None
        and market_price > 0
        and market_price_ex_vat is not None
        and market_price_ex_vat > 0
    )


def _o_net_fee_bridge_stats(
    source_path: Path = O_RESTOCK_SOURCE_VIEW_PATH,
    recommendations_path: Path = O_RESTOCK_RECOMMENDATIONS_PATH,
    coverage_path: Path = O_REORDER_INPUT_COVERAGE_PATH,
    *,
    max_age_hours: float | None = None,
    roi_tolerance_pct: float | None = None,
    fee_drag_tolerance_gbp: float | None = None,
) -> Dict[str, object]:
    max_age = (
        max_age_hours
        if max_age_hours is not None
        else float(os.environ.get("O_NET_FEE_MAX_AGE_HOURS", "48") or "48")
    )
    roi_tolerance = (
        roi_tolerance_pct
        if roi_tolerance_pct is not None
        else float(os.environ.get("O_NET_FEE_ROI_TOLERANCE_PCT", "0.01") or "0.01")
    )
    fee_drag_tolerance = (
        fee_drag_tolerance_gbp
        if fee_drag_tolerance_gbp is not None
        else float(os.environ.get("O_NET_FEE_DRAG_TOLERANCE_GBP", "0.0001") or "0.0001")
    )

    source_df, source_state, source_note = _read_o_net_fee_csv(source_path)
    rec_df, rec_state, rec_note = _read_o_net_fee_csv(recommendations_path)
    coverage_df, coverage_state, coverage_note = _read_o_net_fee_csv(coverage_path)
    read_states = {
        "source": source_state,
        "recommendations": rec_state,
        "coverage": coverage_state,
    }
    read_notes = {
        "source": source_note,
        "recommendations": rec_note,
        "coverage": coverage_note,
    }

    source_by_sku = _o_net_fee_rows_by_sku(source_df)
    rec_by_sku = _o_net_fee_rows_by_sku(rec_df)
    action_skus, coverage_action, recommendation_action, missing_sku_rows = _o_net_fee_collect_action_skus(
        coverage_df,
        rec_df,
    )

    missing_action_source_rows = 0
    missing_action_recommendation_rows = 0
    missing_net_field_rows = 0
    bad_status_rows = 0
    stale_age_rows = 0
    issue_samples: List[str] = []

    def remember(sample: str) -> None:
        if len(issue_samples) < 8:
            issue_samples.append(sample)

    for sku_key in sorted(action_skus):
        source_row = source_by_sku.get(sku_key)
        if source_row is None:
            missing_action_source_rows += 1
            remember(f"{sku_key}:missing_source_row")
        else:
            field_errors = _o_net_fee_field_errors(source_row, O_NET_FEE_SOURCE_REQUIRED_FIELDS)
            if field_errors:
                missing_net_field_rows += 1
                remember(f"{sku_key}:source_fields={','.join(field_errors[:4])}")
            if _o_net_fee_bad_status(source_row):
                bad_status_rows += 1
                remember(f"{sku_key}:source_status={_o_net_fee_text(source_row.get('net_fee_model_status', '')) or 'blank'}")
            if _o_net_fee_bad_age(source_row, max_age):
                stale_age_rows += 1
                remember(f"{sku_key}:source_age={_o_net_fee_text(source_row.get('net_fee_model_age_hours', '')) or 'blank'}")

        rec_row = rec_by_sku.get(sku_key)
        if rec_row is None:
            missing_action_recommendation_rows += 1
            remember(f"{sku_key}:missing_recommendation_row")
        else:
            field_errors = _o_net_fee_field_errors(rec_row, O_NET_FEE_RECOMMENDATION_REQUIRED_FIELDS)
            if field_errors:
                missing_net_field_rows += 1
                remember(f"{sku_key}:recommendation_fields={','.join(field_errors[:4])}")
            if _o_net_fee_bad_status(rec_row):
                bad_status_rows += 1
                remember(f"{sku_key}:recommendation_status={_o_net_fee_text(rec_row.get('net_fee_model_status', '')) or 'blank'}")
            if _o_net_fee_bad_age(rec_row, max_age):
                stale_age_rows += 1
                remember(f"{sku_key}:recommendation_age={_o_net_fee_text(rec_row.get('net_fee_model_age_hours', '')) or 'blank'}")

    if not coverage_action.empty:
        for _, row in coverage_action.iterrows():
            sku_key = _o_net_fee_sku_key(row.get("seller_sku", "")) or "blank_sku"
            field_errors = _o_net_fee_field_errors(row, O_NET_FEE_COVERAGE_REQUIRED_FIELDS)
            if field_errors:
                missing_net_field_rows += 1
                remember(f"{sku_key}:coverage_fields={','.join(field_errors[:4])}")
            if _o_net_fee_bad_status(row):
                bad_status_rows += 1
                remember(f"{sku_key}:coverage_status={_o_net_fee_text(row.get('net_fee_model_status', '')) or 'blank'}")
            if _o_net_fee_bad_age(row, max_age):
                stale_age_rows += 1
                remember(f"{sku_key}:coverage_age={_o_net_fee_text(row.get('net_fee_model_age_hours', '')) or 'blank'}")

    fee_drag_rows = 0
    equal_net_gross_roi_rows = 0
    roi_compare_missing_rows = 0
    roi_compare_not_applicable_rows = 0
    if not rec_df.empty:
        for _, row in rec_df.iterrows():
            sku_key = _o_net_fee_sku_key(row.get("seller_sku", ""))
            source_row = source_by_sku.get(sku_key) if sku_key else None
            drag = _safe_float(row.get("net_fee_drag_per_unit_gbp", ""))
            if drag is None and source_row is not None:
                drag = _safe_float(source_row.get("net_fee_drag_per_unit_gbp", ""))
            if drag is None or abs(drag) <= fee_drag_tolerance:
                continue
            fee_drag_rows += 1
            net_roi = _safe_float(row.get("forward_roi_pct", ""))
            gross_roi = _safe_float(row.get("gross_forward_roi_pct", ""))
            if net_roi is None or gross_roi is None:
                if not _o_net_fee_roi_compare_applicable(row, source_row):
                    roi_compare_not_applicable_rows += 1
                    continue
                roi_compare_missing_rows += 1
                remember(f"{sku_key or 'blank_sku'}:roi_compare_missing")
                continue
            if abs(net_roi - gross_roi) <= roi_tolerance:
                equal_net_gross_roi_rows += 1
                remember(f"{sku_key or 'blank_sku'}:net_roi_equals_gross_roi")

    hard_fail_count = (
        missing_sku_rows
        + missing_action_source_rows
        + missing_action_recommendation_rows
        + missing_net_field_rows
        + bad_status_rows
        + stale_age_rows
        + equal_net_gross_roi_rows
    )
    missing_or_error_files = [name for name, state in read_states.items() if state in {"missing", "read_error"}]
    empty_files = [name for name, state in read_states.items() if state == "empty"]

    status = "ok"
    value = str(len(action_skus))
    if hard_fail_count > 0:
        status = "fail"
        value = str(hard_fail_count)
    elif roi_compare_missing_rows > 0 and fee_drag_rows > 0:
        status = "warn"
        value = "roi_compare_missing"
    elif missing_or_error_files:
        status = "warn"
        value = "missing_live_output"
    elif len(empty_files) == len(read_states):
        value = "empty_outputs"
    elif len(action_skus) == 0:
        value = "no_action_ready"

    notes = (
        f"source={source_path};recommendations={recommendations_path};coverage={coverage_path};"
        f"source_rows={len(source_df.index)};recommendation_rows={len(rec_df.index)};coverage_rows={len(coverage_df.index)};"
        f"coverage_action_ready_rows={len(coverage_action.index)};buy_recommendation_rows={len(recommendation_action.index)};"
        f"action_skus={len(action_skus)};max_age_hours={max_age:.2f};"
        f"missing_sku_rows={missing_sku_rows};missing_action_source_rows={missing_action_source_rows};"
        f"missing_action_recommendation_rows={missing_action_recommendation_rows};"
        f"missing_net_field_rows={missing_net_field_rows};bad_status_rows={bad_status_rows};"
        f"stale_age_rows={stale_age_rows};fee_drag_rows={fee_drag_rows};"
        f"equal_net_gross_roi_rows={equal_net_gross_roi_rows};roi_compare_missing_rows={roi_compare_missing_rows};"
        f"roi_compare_not_applicable_rows={roi_compare_not_applicable_rows};"
        f"read_states={','.join([f'{k}:{v}' for k, v in read_states.items()])};"
        f"read_notes={'|'.join(read_notes.values())};sample={','.join(issue_samples)}"
    )
    return {
        "status": status,
        "value": value,
        "notes": notes,
        "action_skus": len(action_skus),
        "coverage_action_ready_rows": len(coverage_action.index),
        "buy_recommendation_rows": len(recommendation_action.index),
        "hard_fail_count": hard_fail_count,
        "missing_net_field_rows": missing_net_field_rows,
        "bad_status_rows": bad_status_rows,
        "stale_age_rows": stale_age_rows,
        "equal_net_gross_roi_rows": equal_net_gross_roi_rows,
        "roi_compare_missing_rows": roi_compare_missing_rows,
        "roi_compare_not_applicable_rows": roi_compare_not_applicable_rows,
        "read_states": read_states,
    }


def _o_net_fee_bridge_check(
    rows: List[Dict[str, str]],
    source_path: Path = O_RESTOCK_SOURCE_VIEW_PATH,
    recommendations_path: Path = O_RESTOCK_RECOMMENDATIONS_PATH,
    coverage_path: Path = O_REORDER_INPUT_COVERAGE_PATH,
) -> None:
    stats = _o_net_fee_bridge_stats(
        source_path=source_path,
        recommendations_path=recommendations_path,
        coverage_path=coverage_path,
    )
    _add(
        rows,
        "o_net_fee_bridge_health",
        str(stats.get("status", "warn") or "warn"),
        str(stats.get("value", "unknown") or "unknown"),
        str(stats.get("notes", "") or ""),
    )


def _inventory_scope_skus(path: Path = MERCHANT_LISTINGS_PATH) -> set[str]:
    if not path.exists():
        return set()
    try:
        scope = _read_csv(path)
    except Exception:
        return set()
    if scope.empty:
        return set()
    skus: set[str] = set()
    for col in ("seller_sku", "seller-sku", "sku", "SKU"):
        if col not in scope.columns:
            continue
        vals = scope[col].astype(str).str.strip().str.upper()
        skus.update([v for v in vals.tolist() if v])
    return skus


def _a_inventory_stale_token_gap_stats(
    inventory: pd.DataFrame,
    token_ledger: pd.DataFrame,
    *,
    scope_skus: set[str] | None = None,
    now_utc: datetime | None = None,
) -> Dict[str, object]:
    stats: Dict[str, object] = {
        "status": "warn",
        "reason": "not_checked",
        "row_stale_hours": 24.0,
        "scope_rows": 0,
        "stale_scope_rows": 0,
        "unresolved_gap_rows": 0,
        "unresolved_available_gap_rows": 0,
        "unresolved_total_gap_rows": 0,
        "stale_scope_sample": [],
        "unresolved_sample": [],
    }
    raw_stale_hours = os.environ.get("A003_STOCK_ROW_STALE_HOURS", os.environ.get("H_STOCK_ROW_STALE_HOURS", "24"))
    try:
        stats["row_stale_hours"] = max(float(str(raw_stale_hours).strip() or "24"), 0.0)
    except Exception:
        stats["row_stale_hours"] = 24.0
    row_stale_hours = float(stats["row_stale_hours"])
    probe_now = now_utc or datetime.now(timezone.utc)

    if inventory is None or inventory.empty:
        stats["reason"] = "missing_inventory"
        return stats
    if token_ledger is None or token_ledger.empty:
        stats["reason"] = "missing_token_ledger"
        return stats
    if "seller_sku" not in token_ledger.columns or "status" not in token_ledger.columns:
        stats["reason"] = "token_ledger_missing_cols"
        return stats

    token_work = token_ledger.copy()
    token_work["sku_key"] = token_work["seller_sku"].astype(str).str.strip().str.upper()
    token_work["status_key"] = token_work["status"].astype(str).str.strip().str.lower()
    token_work = token_work.loc[token_work["sku_key"].ne("")].copy()
    if token_work.empty:
        stats["reason"] = "empty_token_skus"
        return stats

    token_available_rows = token_work.loc[token_work["status_key"].eq("available")]
    token_available_by_sku = token_available_rows.groupby("sku_key", as_index=False).size()
    token_available_map = {str(r["sku_key"]): int(r["size"]) for _, r in token_available_by_sku.iterrows()}
    effective_statuses = {"available", "allocated", "unsellable", "research_pending", "returned_pending"}
    token_effective_rows = token_work.loc[token_work["status_key"].isin(effective_statuses)]
    token_effective_by_sku = token_effective_rows.groupby("sku_key", as_index=False).size()
    token_effective_map = {str(r["sku_key"]): int(r["size"]) for _, r in token_effective_by_sku.iterrows()}

    scope = {str(v).strip().upper() for v in (scope_skus or set()) if str(v).strip()}
    work = inventory.copy()
    if "seller_sku" not in work.columns and "sku" in work.columns:
        work["seller_sku"] = work["sku"]
    if "seller_sku" not in work.columns:
        stats["reason"] = "inventory_missing_seller_sku"
        return stats

    stale_scope_sample: List[str] = []
    unresolved_sample: List[str] = []
    unresolved_gap_rows = 0
    unresolved_available_gap_rows = 0
    unresolved_total_gap_rows = 0
    stale_scope_rows = 0
    scope_rows = 0

    for _, row in work.iterrows():
        sku = str(row.get("seller_sku", "")).strip().upper()
        if not sku:
            continue
        if scope and sku not in scope:
            continue
        scope_rows += 1

        stale_flag_raw = str(row.get("row_last_updated_is_stale", "")).strip().lower()
        stale_status_raw = str(row.get("row_last_updated_status", "")).strip().lower()
        is_stale = False
        if stale_flag_raw in {"1", "true", "yes", "y", "on"}:
            is_stale = True
        elif stale_flag_raw in {"0", "false", "no", "n", "off"}:
            is_stale = False
        elif stale_status_raw in {"stale", "unknown"}:
            is_stale = True
        elif stale_status_raw == "fresh":
            is_stale = False
        else:
            age_hours = _safe_float(row.get("row_last_updated_age_hours", ""))
            if age_hours is None:
                updated = _to_dt(pd.Series([row.get("last_updated_time", "")])).iloc[0]
                if pd.isna(updated):
                    age_hours = None
                else:
                    age_hours = max((probe_now - updated.to_pydatetime()).total_seconds() / 3600.0, 0.0)
            if age_hours is None:
                is_stale = True
            else:
                is_stale = bool(age_hours >= row_stale_hours)
        if not is_stale:
            continue

        stale_scope_rows += 1
        if len(stale_scope_sample) < 5:
            stale_scope_sample.append(sku)

        inv_available = max(_safe_int(row.get("available", 0)), _safe_int(row.get("in_stock_supply_quantity", 0)))
        inv_total = max(_safe_int(row.get("total_quantity", 0)), inv_available)
        token_available = int(token_available_map.get(sku, 0))
        token_total_effective = int(token_effective_map.get(sku, token_available))
        available_gap = max(token_available - inv_available, 0)
        total_gap = max(token_total_effective - inv_total, 0)
        if available_gap > 0:
            unresolved_available_gap_rows += 1
        if total_gap > 0:
            unresolved_total_gap_rows += 1
        if available_gap > 0 or total_gap > 0:
            unresolved_gap_rows += 1
            if len(unresolved_sample) < 5:
                unresolved_sample.append(
                    f"{sku}:avail_gap={available_gap},total_gap={total_gap},inv_avail={inv_available},token_avail={token_available}"
                )

    stats.update(
        {
            "status": "fail" if unresolved_gap_rows > 0 else "ok",
            "reason": "",
            "scope_rows": int(scope_rows),
            "stale_scope_rows": int(stale_scope_rows),
            "unresolved_gap_rows": int(unresolved_gap_rows),
            "unresolved_available_gap_rows": int(unresolved_available_gap_rows),
            "unresolved_total_gap_rows": int(unresolved_total_gap_rows),
            "stale_scope_sample": stale_scope_sample,
            "unresolved_sample": unresolved_sample,
        }
    )
    return stats


def _e_sales_truth_roi_integrity_stats(path: Path) -> Dict[str, object]:
    required = ["units_sold", "revenue_exvat_gbp", "profit_exvat_gbp", "missing_cogs_units"]
    if not path.exists():
        return {"ready": False, "status": "warn", "reason": "missing_file", "notes": f"path={path}"}
    try:
        df = _read_csv(path)
    except Exception as exc:
        return {
            "ready": False,
            "status": "warn",
            "reason": "read_error",
            "notes": f"path={path};error={exc.__class__.__name__}:{exc}",
        }
    if df.empty:
        return {"ready": False, "status": "warn", "reason": "empty_file", "notes": f"path={path}"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {
            "ready": False,
            "status": "fail",
            "reason": "missing_cols",
            "notes": f"path={path};missing_cols={','.join(missing)}",
        }
    units = pd.to_numeric(df["units_sold"], errors="coerce").fillna(0)
    revenue = pd.to_numeric(df["revenue_exvat_gbp"], errors="coerce").fillna(0)
    profit = pd.to_numeric(df["profit_exvat_gbp"], errors="coerce").fillna(0)
    missing_cogs_units = pd.to_numeric(df["missing_cogs_units"], errors="coerce").fillna(0)
    selling = units > 0
    selling_rows = int(selling.sum())
    zero_revenue_rows = int((selling & revenue.eq(0)).sum())
    zero_profit_with_revenue_rows = int((selling & revenue.ne(0) & profit.eq(0)).sum())
    missing_cogs_equals_units_rows = int((selling & missing_cogs_units.ge(units)).sum())
    return {
        "ready": True,
        "selling_rows": selling_rows,
        "zero_revenue_rows": zero_revenue_rows,
        "zero_profit_with_revenue_rows": zero_profit_with_revenue_rows,
        "missing_cogs_equals_units_rows": missing_cogs_equals_units_rows,
        "notes": f"path={path};selling_rows={selling_rows}",
    }


def _e_sales_truth_reconciliation_stats(path: Path) -> Dict[str, object]:
    required = ["confidence_status", "revenue_delta_gbp", "profit_delta_gbp"]
    if not path.exists():
        return {"ready": False, "status": "warn", "reason": "missing_file", "notes": f"path={path}"}
    try:
        df = _read_csv(path)
    except Exception as exc:
        return {
            "ready": False,
            "status": "warn",
            "reason": "read_error",
            "notes": f"path={path};error={exc.__class__.__name__}:{exc}",
        }
    if df.empty:
        return {"ready": False, "status": "warn", "reason": "empty_file", "notes": f"path={path}"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {
            "ready": False,
            "status": "fail",
            "reason": "missing_cols",
            "notes": f"path={path};missing_cols={','.join(missing)}",
        }
    status_col = df["confidence_status"].astype(str).str.strip().str.lower()
    mismatch_rows = int(status_col.ne("match").sum())
    total_rows = int(len(df.index))
    mismatch_share = (mismatch_rows / total_rows) if total_rows > 0 else 0.0
    revenue_delta_abs_sum = float(pd.to_numeric(df["revenue_delta_gbp"], errors="coerce").fillna(0).abs().sum())
    profit_delta_abs_sum = float(pd.to_numeric(df["profit_delta_gbp"], errors="coerce").fillna(0).abs().sum())
    fail_share = _safe_float(os.environ.get("E_SALES_TRUTH_RECON_FAIL_SHARE", "0.80"))
    if fail_share is None or fail_share <= 0:
        fail_share = 0.80
    status = "ok"
    if mismatch_rows > 0 and mismatch_share >= fail_share:
        status = "fail"
    elif mismatch_rows > 0:
        status = "warn"
    return {
        "ready": True,
        "status": status,
        "mismatch_rows": mismatch_rows,
        "total_rows": total_rows,
        "mismatch_share": mismatch_share,
        "revenue_delta_abs_sum": revenue_delta_abs_sum,
        "profit_delta_abs_sum": profit_delta_abs_sum,
        "notes": (
            f"path={path};total_rows={total_rows};mismatch_rows={mismatch_rows};"
            f"mismatch_share={mismatch_share:.4f};revenue_delta_abs_sum={revenue_delta_abs_sum:.2f};"
            f"profit_delta_abs_sum={profit_delta_abs_sum:.2f};fail_share={fail_share:.2f}"
        ),
    }


def _e_performance_units_alignment_stats(path: Path) -> Dict[str, object]:
    required = ["units_sold", "units_sold_roi", "revenue_exvat_gbp", "profit_exvat_gbp"]
    if not path.exists():
        return {"ready": False, "status": "warn", "reason": "missing_file", "notes": f"path={path}"}
    try:
        df = _read_csv(path)
    except Exception as exc:
        return {
            "ready": False,
            "status": "warn",
            "reason": "read_error",
            "notes": f"path={path};error={exc.__class__.__name__}:{exc}",
        }
    if df.empty:
        return {"ready": False, "status": "warn", "reason": "empty_file", "notes": f"path={path}"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {
            "ready": False,
            "status": "fail",
            "reason": "missing_cols",
            "notes": f"path={path};missing_cols={','.join(missing)}",
        }

    units = pd.to_numeric(df["units_sold"], errors="coerce")
    units_roi = pd.to_numeric(df["units_sold_roi"], errors="coerce")
    roi_rows = units_roi.fillna(0).gt(0)
    mismatch = (units.fillna(0) - units_roi.fillna(0)).abs().gt(1e-6)
    mismatch_rows = int((roi_rows & mismatch).sum())
    roi_row_count = int(roi_rows.sum())
    status = "fail" if mismatch_rows > 0 else "ok"
    return {
        "ready": True,
        "status": status,
        "roi_row_count": roi_row_count,
        "mismatch_rows": mismatch_rows,
        "notes": f"path={path};roi_row_count={roi_row_count};mismatch_rows={mismatch_rows}",
    }


def _e_daily_sales_truth_stats(path: Path) -> Dict[str, object]:
    required = [
        "sku",
        "date",
        "source_state",
        "units",
        "revenue_gbp",
        "profit_gbp",
        "confidence_status",
        "notes",
    ]
    if not path.exists():
        return {"ready": False, "status": "warn", "reason": "missing_file", "notes": f"path={path}"}
    try:
        df = _read_csv(path)
    except Exception as exc:
        return {
            "ready": False,
            "status": "warn",
            "reason": "read_error",
            "notes": f"path={path};error={exc.__class__.__name__}:{exc}",
        }
    if df.empty:
        return {"ready": False, "status": "warn", "reason": "empty_file", "notes": f"path={path}"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {
            "ready": False,
            "status": "fail",
            "reason": "missing_cols",
            "notes": f"path={path};missing_cols={','.join(missing)}",
        }

    source = df["source_state"].astype(str).str.strip()
    confidence = df["confidence_status"].astype(str).str.strip().str.lower()

    allowed_source = {"finalized_ledger", "provisional_order_master"}
    invalid_source_rows = int(source[~source.isin(allowed_source)].shape[0])
    blank_source_rows = int(source.eq("").sum())
    provisional_mask = source.eq("provisional_order_master")
    finalized_mask = source.eq("finalized_ledger")
    provisional_bad_confidence = int((provisional_mask & ~confidence.str.startswith("provisional")).sum())
    finalized_bad_confidence = int((finalized_mask & confidence.ne("finalized")).sum())

    status = "ok"
    if invalid_source_rows > 0 or blank_source_rows > 0:
        status = "fail"
    elif provisional_bad_confidence > 0 or finalized_bad_confidence > 0:
        status = "fail"
    return {
        "ready": True,
        "status": status,
        "rows": int(len(df.index)),
        "invalid_source_rows": invalid_source_rows,
        "blank_source_rows": blank_source_rows,
        "provisional_bad_confidence_rows": provisional_bad_confidence,
        "finalized_bad_confidence_rows": finalized_bad_confidence,
        "notes": (
            f"path={path};rows={len(df.index)};invalid_source_rows={invalid_source_rows};"
            f"blank_source_rows={blank_source_rows};provisional_bad_confidence_rows={provisional_bad_confidence};"
            f"finalized_bad_confidence_rows={finalized_bad_confidence}"
        ),
    }


def _e_study_report_fresh_vs_summary_stats(summary_path: Path, study_path: Path) -> Dict[str, object]:
    if not summary_path.exists():
        return {"ready": False, "status": "warn", "reason": "missing_summary", "notes": f"path={summary_path}"}
    if not study_path.exists():
        return {"ready": False, "status": "fail", "reason": "missing_study", "notes": f"path={study_path}"}
    try:
        summary_mtime = datetime.fromtimestamp(summary_path.stat().st_mtime, tz=timezone.utc)
        study_mtime = datetime.fromtimestamp(study_path.stat().st_mtime, tz=timezone.utc)
    except Exception as exc:
        return {
            "ready": False,
            "status": "warn",
            "reason": "stat_error",
            "notes": f"summary={summary_path};study={study_path};error={exc.__class__.__name__}:{exc}",
        }

    lag_seconds = max((summary_mtime - study_mtime).total_seconds(), 0.0)
    status = "fail" if study_mtime < summary_mtime else "ok"
    return {
        "ready": True,
        "status": status,
        "lag_seconds": lag_seconds,
        "notes": (
            f"summary={summary_path};study={study_path};summary_mtime_utc={summary_mtime.isoformat()};"
            f"study_mtime_utc={study_mtime.isoformat()};lag_seconds={lag_seconds:.0f}"
        ),
    }


def _e_study_report_truth_alignment_stats(summary_path: Path, study_path: Path) -> Dict[str, object]:
    summary_required = ["sku", "units_sold", "revenue_exvat_gbp", "profit_exvat_gbp", "units_sold_roi"]
    study_required = [
        "sku",
        "units_sold_30d",
        "units_sold_truth_30d",
        "revenue_exvat_gbp_30d",
        "profit_exvat_gbp_30d",
    ]
    if not summary_path.exists():
        return {"ready": False, "status": "warn", "reason": "missing_summary", "notes": f"path={summary_path}"}
    if not study_path.exists():
        return {"ready": False, "status": "fail", "reason": "missing_study", "notes": f"path={study_path}"}
    try:
        summary = _read_csv(summary_path)
        study = _read_csv(study_path)
    except Exception as exc:
        return {
            "ready": False,
            "status": "warn",
            "reason": "read_error",
            "notes": f"summary={summary_path};study={study_path};error={exc.__class__.__name__}:{exc}",
        }
    if summary.empty:
        return {"ready": False, "status": "warn", "reason": "empty_summary", "notes": f"path={summary_path}"}
    if study.empty:
        return {"ready": False, "status": "fail", "reason": "empty_study", "notes": f"path={study_path}"}
    missing_summary = [c for c in summary_required if c not in summary.columns]
    if missing_summary:
        return {
            "ready": False,
            "status": "fail",
            "reason": "missing_summary_cols",
            "notes": f"path={summary_path};missing_cols={','.join(missing_summary)}",
        }
    missing_study = [c for c in study_required if c not in study.columns]
    if missing_study:
        return {
            "ready": False,
            "status": "fail",
            "reason": "missing_study_cols",
            "notes": f"path={study_path};missing_cols={','.join(missing_study)}",
        }

    summary_cmp = summary.rename(
        columns={
            "units_sold": "summary_units_sold",
            "units_sold_roi": "summary_units_sold_roi",
            "revenue_exvat_gbp": "summary_revenue_exvat_gbp",
            "profit_exvat_gbp": "summary_profit_exvat_gbp",
        }
    )
    study_cmp = study.rename(
        columns={
            "units_sold_30d": "study_units_sold_30d",
            "units_sold_truth_30d": "study_units_sold_truth_30d",
            "revenue_exvat_gbp_30d": "study_revenue_exvat_gbp_30d",
            "profit_exvat_gbp_30d": "study_profit_exvat_gbp_30d",
        }
    )

    merged = summary_cmp.merge(study_cmp, on="sku", how="left")
    roi_rows = pd.to_numeric(merged["summary_units_sold_roi"], errors="coerce").fillna(0).gt(0)
    study_missing = merged["study_units_sold_truth_30d"].astype(str).eq("")
    units_match = (
        pd.to_numeric(merged["study_units_sold_truth_30d"], errors="coerce").fillna(0)
        - pd.to_numeric(merged["summary_units_sold"], errors="coerce").fillna(0)
    ).abs().le(1e-6)
    revenue_match = (
        pd.to_numeric(merged["study_revenue_exvat_gbp_30d"], errors="coerce").fillna(0)
        - pd.to_numeric(merged["summary_revenue_exvat_gbp"], errors="coerce").fillna(0)
    ).abs().le(1e-6)
    profit_match = (
        pd.to_numeric(merged["study_profit_exvat_gbp_30d"], errors="coerce").fillna(0)
        - pd.to_numeric(merged["summary_profit_exvat_gbp"], errors="coerce").fillna(0)
    ).abs().le(1e-6)

    mismatch_mask = roi_rows & (study_missing | ~units_match | ~revenue_match | ~profit_match)
    mismatch_rows = int(mismatch_mask.sum())
    roi_row_count = int(roi_rows.sum())
    sample = merged.loc[mismatch_mask, "sku"].astype(str).head(5).tolist()
    return {
        "ready": True,
        "status": "fail" if mismatch_rows > 0 else "ok",
        "roi_row_count": roi_row_count,
        "mismatch_rows": mismatch_rows,
        "notes": f"summary={summary_path};study={study_path};roi_row_count={roi_row_count};mismatch_rows={mismatch_rows};sample={','.join(sample)}",
    }


def _h_ceiling_effective_floor_integrity_result(ceiling_df: pd.DataFrame, *, path: Path) -> Dict[str, str]:
    if ceiling_df.empty:
        return {
            "status": "warn",
            "value": "missing_or_empty",
            "notes": f"path={path}",
        }

    if "run_id" not in ceiling_df.columns:
        return {
            "status": "warn",
            "value": "missing_run_id_col",
            "notes": f"path={path};total_rows={len(ceiling_df.index)}",
        }

    run_ids = ceiling_df["run_id"].astype(str).str.strip()
    latest_run_candidates = run_ids.replace("", pd.NA).dropna()
    if latest_run_candidates.empty:
        return {
            "status": "warn",
            "value": "missing_run_id_values",
            "notes": f"path={path};total_rows={len(ceiling_df.index)}",
        }

    latest_run_id = str(latest_run_candidates.max())
    scoped_df = ceiling_df.loc[run_ids.eq(latest_run_id)].copy()
    conflict_count = 0
    checked_rows = 0
    samples: list[str] = []

    for _, row in scoped_df.iterrows():
        ceiling_val = _safe_float(row.get("true_binding_ceiling_gbp", ""))
        floor_val = _safe_float(row.get("hard_floor_gbp", ""))
        if ceiling_val is None or floor_val is None:
            continue
        checked_rows += 1
        if ceiling_val + 1e-9 < floor_val:
            conflict_count += 1
            if len(samples) < 5:
                sku = str(row.get("sku", "")).strip()
                samples.append(f"{sku}:{ceiling_val:.2f}<{floor_val:.2f}")

    return {
        "status": "fail" if conflict_count > 0 else "ok",
        "value": str(conflict_count),
        "notes": (
            f"path={path};scope_run_id={latest_run_id};scoped_rows={len(scoped_df.index)};"
            f"checked_rows={checked_rows};total_rows={len(ceiling_df.index)};"
            + (f"samples={','.join(samples)}" if samples else "samples=none")
        ),
    }


def _strategy_sample_min_rows_for_health(scenario_type: object) -> int:
    scenario = str(scenario_type or "").strip().lower()
    if scenario == "multi_seller_ladder_cap":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_MULTI_SELLER", "150")), 1)
    if scenario == "single_rival_reset":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_SINGLE_RIVAL", "30")), 1)
    if scenario == "suppression_reactivation":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_SUPPRESSION", "20")), 1)
    return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_DEFAULT", "30")), 1)


def _strategy_health_scenarios_for_entry(*, scenario_type: object, chosen_tactic: object) -> List[str]:
    scenario = str(scenario_type or "").strip().lower()
    tactic = str(chosen_tactic or "").strip().upper()
    out: List[str] = []
    if scenario in {"multi_seller_ladder_cap", "single_rival_reset", "suppression_reactivation"}:
        out.append(scenario)
    if "SINGLE_RIVAL_RESET" in tactic and "single_rival_reset" not in out:
        out.append("single_rival_reset")
    if "SUPPRESSION_REACTIVATION" in tactic and "suppression_reactivation" not in out:
        out.append("suppression_reactivation")
    return out


def _strategy_is_failed_write_for_streak(*, tactic_success_state: object, writer_outcome: object) -> bool:
    state = str(tactic_success_state or "").strip().lower()
    writer = str(writer_outcome or "").strip().upper()
    if state != "failed":
        return False
    if writer in {"", "NO_WRITE_REQUIRED", "READ_ONLY_NO_WRITE", "APPLIED"}:
        return False
    return True


def _strategy_no_write_failed_streaks(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
    if df.empty:
        return {}
    for col in ["event_ts_utc", "scenario_type", "chosen_tactic", "writer_outcome", "tactic_success_state", "tactic_case_id"]:
        if col not in df.columns:
            df[col] = ""
    df["event_dt"] = pd.to_datetime(df.get("event_ts_utc", ""), errors="coerce", utc=True)
    df = df.sort_values(["event_dt"], ascending=[False], kind="stable")
    focus = ["multi_seller_ladder_cap", "single_rival_reset", "suppression_reactivation"]
    streaks: Dict[str, int] = {key: 0 for key in focus}
    sample_cases: Dict[str, List[str]] = {key: [] for key in focus}
    closed: Dict[str, bool] = {key: False for key in focus}
    for _, row in df.iterrows():
        row_scenarios = _strategy_health_scenarios_for_entry(
            scenario_type=row.get("scenario_type", ""),
            chosen_tactic=row.get("chosen_tactic", ""),
        )
        if not row_scenarios:
            continue
        for scenario in row_scenarios:
            if scenario not in closed or closed[scenario]:
                continue
            is_failed_write = _strategy_is_failed_write_for_streak(
                tactic_success_state=row.get("tactic_success_state", ""),
                writer_outcome=row.get("writer_outcome", ""),
            )
            if is_failed_write:
                streaks[scenario] += 1
                case_id = str(row.get("tactic_case_id", "")).strip()
                if case_id and case_id not in sample_cases[scenario] and len(sample_cases[scenario]) < 3:
                    sample_cases[scenario].append(case_id)
            else:
                closed[scenario] = True
        if all(closed.values()):
            break
    out: Dict[str, Dict[str, object]] = {}
    for scenario in focus:
        out[scenario] = {"streak": int(streaks.get(scenario, 0)), "sample_case_ids": sample_cases.get(scenario, [])}
    return out


def _strategy_sample_size_snapshot(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"asof_date": "", "rows_by_scenario": {}}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {"asof_date": "", "rows_by_scenario": {}}
    if df.empty or "scenario_type" not in df.columns:
        return {"asof_date": "", "rows_by_scenario": {}}
    asof_series = df.get("asof_date", "").astype(str).str.strip()
    non_blank = asof_series[asof_series.ne("")]
    latest_asof = str(non_blank.max()) if not non_blank.empty else ""
    if latest_asof:
        work = df.loc[asof_series.eq(latest_asof)].copy()
    else:
        work = df.copy()
    rows_by_scenario: Dict[str, Dict[str, object]] = {}
    for _, row in work.iterrows():
        row_scenarios = _strategy_health_scenarios_for_entry(
            scenario_type=row.get("scenario_type", ""),
            chosen_tactic=row.get("chosen_tactic", ""),
        )
        if not row_scenarios:
            continue
        row_decision_rows = _safe_int(row.get("decision_rows", "0"))
        row_chosen_tactic = str(row.get("chosen_tactic", "")).strip()
        for scenario in row_scenarios:
            sample_min_rows = _safe_int(row.get("sample_min_rows", "0")) or _strategy_sample_min_rows_for_health(scenario)
            stat = rows_by_scenario.get(
                scenario,
                {
                    "decision_rows": 0,
                    "sample_min_rows": _strategy_sample_min_rows_for_health(scenario),
                    "provisional_sample_flag": 1,
                    "success_rows": 0,
                    "failed_rows": 0,
                    "expired_rows": 0,
                    "aborted_rows": 0,
                    "chosen_tactic": "",
                    "_chosen_tactic_decision_rows": -1,
                },
            )
            row_success_rows = _safe_int(row.get("success_rows", "0"))
            row_failed_rows = _safe_int(row.get("failed_rows", "0"))
            row_expired_rows = _safe_int(row.get("expired_rows", "0"))
            row_aborted_rows = _safe_int(row.get("aborted_rows", "0"))
            stat["decision_rows"] = int(_safe_int(stat.get("decision_rows", 0)) + row_decision_rows)
            stat["sample_min_rows"] = int(max(_safe_int(stat.get("sample_min_rows", 0)), sample_min_rows))
            stat["success_rows"] = int(_safe_int(stat.get("success_rows", 0)) + row_success_rows)
            stat["failed_rows"] = int(_safe_int(stat.get("failed_rows", 0)) + row_failed_rows)
            stat["expired_rows"] = int(_safe_int(stat.get("expired_rows", 0)) + row_expired_rows)
            stat["aborted_rows"] = int(_safe_int(stat.get("aborted_rows", 0)) + row_aborted_rows)
            chosen_rows = _safe_int(stat.get("_chosen_tactic_decision_rows", -1))
            if row_decision_rows > chosen_rows:
                stat["chosen_tactic"] = row_chosen_tactic
                stat["_chosen_tactic_decision_rows"] = row_decision_rows
            rows_by_scenario[scenario] = stat
    for scenario, stat in rows_by_scenario.items():
        decision_rows = _safe_int(stat.get("decision_rows", 0))
        sample_min_rows = _safe_int(stat.get("sample_min_rows", 0)) or _strategy_sample_min_rows_for_health(scenario)
        success_rows = _safe_int(stat.get("success_rows", 0))
        failed_rows = _safe_int(stat.get("failed_rows", 0))
        expired_rows = _safe_int(stat.get("expired_rows", 0))
        aborted_rows = _safe_int(stat.get("aborted_rows", 0))
        terminal_rows = max(success_rows + failed_rows + expired_rows + aborted_rows, 0)
        judged_rows = max(success_rows + failed_rows, 0)
        expired_share_pct = (expired_rows * 100.0 / decision_rows) if decision_rows > 0 else 0.0
        stat["decision_rows"] = int(decision_rows)
        stat["sample_min_rows"] = int(sample_min_rows)
        stat["success_rows"] = int(success_rows)
        stat["failed_rows"] = int(failed_rows)
        stat["expired_rows"] = int(expired_rows)
        stat["aborted_rows"] = int(aborted_rows)
        stat["terminal_rows"] = int(terminal_rows)
        stat["judged_rows"] = int(judged_rows)
        stat["expired_share_pct"] = round(float(expired_share_pct), 2)
        stat["provisional_sample_flag"] = 1 if decision_rows < sample_min_rows else 0
        stat.pop("_chosen_tactic_decision_rows", None)
    return {"asof_date": latest_asof, "rows_by_scenario": rows_by_scenario}


def _stock_qty_map_from_path(path: Path) -> Dict[str, float]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
    if df.empty:
        return {}
    sku_col = ""
    for candidate in ("seller_sku", "sku", "seller-sku", "SKU"):
        if candidate in df.columns:
            sku_col = candidate
            break
    qty_col = ""
    for candidate in ("total_quantity", "total_qty", "available", "stock"):
        if candidate in df.columns:
            qty_col = candidate
            break
    if not sku_col or not qty_col:
        return {}
    out: Dict[str, float] = {}
    for _, row in df.iterrows():
        sku = str(row.get(sku_col, "")).strip().upper()
        qty = _safe_float(row.get(qty_col, ""))
        if not sku or qty is None:
            continue
        prev = out.get(sku)
        if prev is None or qty > prev:
            out[sku] = float(qty)
    return out


def _load_stock_qty_by_sku() -> Tuple[Dict[str, float], str]:
    candidates: List[Path] = []
    if INVENTORY_SUMMARIES_PATH.exists():
        candidates.append(INVENTORY_SUMMARIES_PATH)
    latest_inventory_snapshot = _latest_snapshot(INVENTORY_SNAPSHOT_GLOB)
    if latest_inventory_snapshot is not None:
        candidates.append(latest_inventory_snapshot)
    if STOCK_SNAPSHOT_LATEST_PATH.exists():
        candidates.append(STOCK_SNAPSHOT_LATEST_PATH)

    for path in candidates:
        qty_map = _stock_qty_map_from_path(path)
        if qty_map:
            return qty_map, str(path)
    return {}, ""


def _safe_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _read_jsonl_rows(path: Path) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    if not path.exists():
        return out
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    out.append(payload)
    except Exception:
        return []
    return out


def _latest_successful_e_run(path: Path) -> Dict[str, str]:
    rows = _read_jsonl_rows(path)
    for payload in reversed(rows):
        status = str(payload.get("status", "")).strip().lower()
        if status not in {"success", "ok"}:
            continue
        return {
            "run_id": str(payload.get("run_id", "")).strip(),
            "status": status,
            "started_utc": str(payload.get("started_utc", "")).strip(),
            "finished_utc": str(payload.get("finished_utc", "")).strip(),
            "output_asof": str(payload.get("output_asof", "")).strip(),
        }
    return {}


def _parse_utc_ts(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _iter_b_cycle_log_events(path: Path, cutoff: datetime) -> List[Dict[str, object]]:
    line_events = _iter_b_cycle_log_lines(path, cutoff=cutoff)
    events: List[Dict[str, object]] = []
    event_re = re.compile(r"^(ok|warn|fail|skip)\s+([^\s]+)", re.IGNORECASE)
    for line_event in line_events:
        msg = str(line_event.get("msg", "")).strip()
        em = event_re.match(msg)
        if not em:
            continue
        event = str(em.group(1)).strip().lower()
        script = str(em.group(2)).strip()
        events.append(
            {
                "idx": int(line_event.get("idx", 0)),
                "ts": str(line_event.get("ts", "")),
                "cycle": str(line_event.get("cycle", "")),
                "event": event,
                "script": script,
                "msg": msg,
                "line": str(line_event.get("line", "")),
            }
        )
    return events


def _iter_b_cycle_log_lines(path: Path, cutoff: datetime) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    if not path.exists():
        return events
    line_re = re.compile(r"^(?P<ts>\S+)\s+\[(?P<cycle>[^\]]+)\]\s+(?P<msg>.*)$")
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for idx, raw in enumerate(fh):
                line = raw.strip()
                if not line:
                    continue
                m = line_re.match(line)
                if not m:
                    continue
                ts = _parse_utc_ts(m.group("ts"))
                if ts is not None and ts < cutoff:
                    continue
                msg = m.group("msg").strip()
                cycle = str(m.group("cycle")).strip()
                events.append(
                    {
                        "idx": idx,
                        "ts": ts.isoformat() if ts is not None else "",
                        "cycle": cycle,
                        "msg": msg,
                        "line": line,
                    }
                )
    except Exception:
        return []
    return events


def _b_maintenance_marker_paths_present() -> List[Path]:
    return [path for path in B_MAINTENANCE_MARKER_PATHS if path.exists()]


def _normalize_step_name(value: object) -> str:
    text = str(value or "").strip().lower()
    if text.endswith(".py"):
        text = text[:-3]
    return text


def _b_cycle_latest_cycle_context(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {
            "latest_cycle": "",
            "maintenance_abort_scripts": set(),
            "maintenance_marker_lines": 0,
            "maintenance_context": False,
            "finalized_cycle_complete": False,
        }

    cutoff = datetime.now(timezone.utc) - timedelta(days=3650)
    lines = _iter_b_cycle_log_lines(path, cutoff=cutoff)
    latest_cycle = str(lines[-1].get("cycle", "")).strip() if lines else ""
    cycle_lines = [row for row in lines if str(row.get("cycle", "")).strip() == latest_cycle] if latest_cycle else []

    maintenance_abort_scripts: set[str] = set()
    maintenance_marker_lines = 0
    finalized_cycle_complete = False
    for row in cycle_lines:
        msg = str(row.get("msg", "")).strip()
        msg_l = msg.lower()
        if msg_l.startswith("maintenance_abort "):
            parts = msg.split()
            if len(parts) >= 2:
                maintenance_abort_scripts.add(_normalize_step_name(parts[1]))
        if "maintenance " in msg_l:
            maintenance_marker_lines += 1
        if "b_finalize ran" in msg_l and "reason=cycle_complete" in msg_l:
            finalized_cycle_complete = True

    maintenance_context = maintenance_marker_lines > 0 or bool(maintenance_abort_scripts)
    return {
        "latest_cycle": latest_cycle,
        "maintenance_abort_scripts": maintenance_abort_scripts,
        "maintenance_marker_lines": maintenance_marker_lines,
        "maintenance_context": maintenance_context,
        "finalized_cycle_complete": finalized_cycle_complete,
    }


def _fees_failed_rows_today(path: Path, now_utc: datetime) -> Dict[str, object]:
    result: Dict[str, object] = {
        "count": 0,
        "sample_skus": [],
        "notes": "",
        "read_error": False,
    }
    today = now_utc.strftime("%Y-%m-%d")
    if not path.exists():
        result["notes"] = f"path={path};missing"
        return result

    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        result["read_error"] = True
        result["notes"] = f"path={path};read_error={exc}"
        return result

    if df.empty:
        result["notes"] = f"path={path};total_rows=0"
        return result

    ts_col = ""
    for candidate in [
        "failure_recorded_utc",
        "recorded_utc",
        "generated_at_utc",
        "run_utc",
        "event_ts_utc",
        "timestamp_utc",
        "created_utc",
    ]:
        if candidate in df.columns:
            ts_col = candidate
            break

    if ts_col:
        ts = _to_dt(df[ts_col])
        mask_today = ts.notna() & ts.dt.strftime("%Y-%m-%d").eq(today)
        rows_today = df.loc[mask_today].copy()
    else:
        try:
            mtime_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            mtime_dt = None
        if mtime_dt is not None and mtime_dt.strftime("%Y-%m-%d") == today:
            rows_today = df.copy()
        else:
            rows_today = df.iloc[0:0].copy()

    sku_col = "seller_sku" if "seller_sku" in rows_today.columns else ("sku" if "sku" in rows_today.columns else "")
    sample_skus: List[str] = []
    if sku_col:
        for val in rows_today[sku_col].astype(str).str.strip().tolist():
            if val and val not in sample_skus:
                sample_skus.append(val)
            if len(sample_skus) >= 5:
                break

    count = int(len(rows_today.index))
    result["count"] = count
    result["sample_skus"] = sample_skus
    result["notes"] = (
        f"date={today};path={path};total_rows={len(df.index)};"
        f"rows_today={count};ts_source={ts_col or 'file_mtime'}"
    )
    return result


def _b_cycle_recent_fail_stats(path: Path, window_hours: float) -> Dict[str, object]:
    # Do not depend on rolling time windows for this check.
    # Evaluate only the latest completed B cycle so old fail lines cannot keep alerting.
    _ = window_hours
    cycle_context = _b_cycle_latest_cycle_context(path)
    latest_cycle = str(cycle_context.get("latest_cycle", "")).strip()
    cutoff = datetime.now(timezone.utc) - timedelta(days=3650)
    events_all = _iter_b_cycle_log_events(path, cutoff=cutoff)
    events = [e for e in events_all if str(e.get("cycle", "")).strip() == latest_cycle] if latest_cycle else []
    fail_events: List[Dict[str, object]] = []
    ignored_non_actionable = 0
    maintenance_abort_scripts = cycle_context.get("maintenance_abort_scripts")
    if not isinstance(maintenance_abort_scripts, set):
        maintenance_abort_scripts = set()
    maintenance_context = bool(cycle_context.get("maintenance_context", False))
    active_maintenance_markers = _b_maintenance_marker_paths_present()
    if active_maintenance_markers:
        maintenance_context = True
    for event in events:
        if str(event.get("event", "")).strip().lower() != "fail":
            continue
        script = str(event.get("script", "")).strip()
        line = str(event.get("line", "")).strip().lower()
        # Ignore legacy/global end-of-cycle A015 fail lines here.
        # They are health summaries, not actionable B step failures.
        if script == "A015_build_system_health_check.py" and "end_of_cycle" in line:
            ignored_non_actionable += 1
            continue
        is_maintenance_abort = "rc=125" in line or "aborted_for_maintenance" in line
        script_norm = _normalize_step_name(script)
        script_in_abort_set = script_norm in maintenance_abort_scripts
        if is_maintenance_abort and (script_in_abort_set or maintenance_context):
            ignored_non_actionable += 1
            continue
        fail_events.append(event)
    latest_non_fail_idx: Dict[Tuple[str, str], int] = {}
    for event in events:
        event_name = str(event.get("event", "")).strip().lower()
        if event_name not in {"ok", "warn", "skip"}:
            continue
        key = (str(event.get("cycle", "")), str(event.get("script", "")))
        latest_non_fail_idx[key] = int(event.get("idx", 0))

    unresolved_events: List[Dict[str, object]] = []
    recovered_count = 0
    for fail_event in fail_events:
        key = (str(fail_event.get("cycle", "")), str(fail_event.get("script", "")))
        fail_idx = int(fail_event.get("idx", 0))
        if int(latest_non_fail_idx.get(key, -1)) > fail_idx:
            recovered_count += 1
        else:
            unresolved_events.append(fail_event)

    unresolved_sample = [str(event.get("line", "")) for event in unresolved_events[:5]]
    return {
        "latest_cycle": latest_cycle,
        "raw_fail_count": len(fail_events),
        "recovered_count": recovered_count,
        "unresolved_count": len(unresolved_events),
        "unresolved_sample": unresolved_sample,
        "ignored_non_actionable": ignored_non_actionable,
        "maintenance_context": int(1 if maintenance_context else 0),
        "maintenance_markers_active": ",".join([path.name for path in active_maintenance_markers]),
        "maintenance_marker_lines": int(cycle_context.get("maintenance_marker_lines", 0)),
    }


def _h_floor_policy_checks(rows: List[Dict[str, str]], now_utc: datetime) -> None:
    today = now_utc.strftime("%Y-%m-%d")
    policy_raw = _read_json(H_FLOOR_VAT_POLICY_PATH, default={})
    if not isinstance(policy_raw, dict) or not policy_raw:
        _add(
            rows,
            "h_floor_vat_policy_config",
            "fail",
            "missing_or_invalid",
            f"path={H_FLOOR_VAT_POLICY_PATH}",
        )
        _add(rows, "h_floor_phase1_cogs_basis_drift", "warn", "not_checked", "policy_missing")
        _add(rows, "h_floor_legacy_cogs_basis_drift", "warn", "not_checked", "policy_missing")
        return

    vat_registered = _safe_bool(policy_raw.get("vat_registered"), True)
    recover_cogs_vat = _safe_bool(policy_raw.get("recover_input_vat_on_cogs"), True)
    recover_fee_vat = _safe_bool(policy_raw.get("recover_input_vat_on_fees"), True)
    formula = str(policy_raw.get("formula_version", "") or "").strip()
    note = str(policy_raw.get("note", "") or "").strip()
    policy_ok = vat_registered and recover_cogs_vat and recover_fee_vat
    _add(
        rows,
        "h_floor_vat_policy_config",
        "ok" if policy_ok else "fail",
        "ok" if policy_ok else "unexpected_values",
        (
            f"vat_registered={int(vat_registered)};recover_input_vat_on_cogs={int(recover_cogs_vat)};"
            f"recover_input_vat_on_fees={int(recover_fee_vat)};formula_version={formula};note={note}"
        ),
    )

    if not recover_cogs_vat:
        _add(
            rows,
            "h_floor_phase1_cogs_basis_drift",
            "warn",
            "not_checked",
            "policy recover_input_vat_on_cogs=0; cogs drift check skipped",
        )
        _add(
            rows,
            "h_floor_legacy_cogs_basis_drift",
            "warn",
            "not_checked",
            "policy recover_input_vat_on_cogs=0; cogs drift check skipped",
        )
        return

    snapshot = _read_csv(H_TEMP_FLOOR_SNAPSHOT_PATH)
    if snapshot.empty:
        _add(
            rows,
            "h_floor_phase1_cogs_basis_drift",
            "warn",
            "missing_snapshot",
            f"path={H_TEMP_FLOOR_SNAPSHOT_PATH}",
        )
    else:
        required_snapshot_cols = {"asof_utc", "sku", "cogs_total_gbp"}
        if not required_snapshot_cols.issubset(set(snapshot.columns)):
            _add(
                rows,
                "h_floor_phase1_cogs_basis_drift",
                "warn",
                "missing_columns",
                f"snapshot_required={','.join(sorted(required_snapshot_cols))}",
            )
        else:
            snap = snapshot.copy()
            snap["asof_utc_key"] = snap["asof_utc"].astype(str).str.strip()
            snap["asof_date"] = snap["asof_utc_key"].str[:10]
            snap = snap.loc[snap["asof_date"].eq(today)].copy()
            if snap.empty:
                _add(
                    rows,
                    "h_floor_phase1_cogs_basis_drift",
                    "ok",
                    "0",
                    f"date={today};rows_today=0",
                )
            else:
                latest_asof = str(snap["asof_utc_key"].max())
                snap = snap.loc[snap["asof_utc_key"].eq(latest_asof)].copy()
                expected_lookup: Dict[str, float] = {}
                expected_source = "trace_latest_asof"
                trace_for_asof = _read_csv(H_FLOOR_TRUTH_TRACE_PATH)
                basis_col = "cogs_exvat_gbp" if recover_cogs_vat else "cogs_total_gbp"
                trace_required = {"asof_utc", "sku", basis_col}
                if not trace_for_asof.empty and trace_required.issubset(set(trace_for_asof.columns)):
                    trace_for_asof = trace_for_asof.copy()
                    trace_for_asof["asof_utc_key"] = trace_for_asof["asof_utc"].astype(str).str.strip()
                    trace_for_asof = trace_for_asof.loc[trace_for_asof["asof_utc_key"].eq(latest_asof)].copy()
                    trace_for_asof["expected_num"] = pd.to_numeric(trace_for_asof[basis_col], errors="coerce")
                    trace_for_asof["sku_key"] = trace_for_asof["sku"].astype(str).str.strip().str.upper()
                    trace_for_asof = trace_for_asof.loc[
                        (trace_for_asof["sku_key"] != "")
                        & trace_for_asof["expected_num"].notna()
                        & trace_for_asof["expected_num"].gt(0.0)
                    ].copy()
                    if not trace_for_asof.empty:
                        expected_lookup = {
                            str(k).strip().upper(): float(v)
                            for k, v in trace_for_asof.groupby("sku_key")["expected_num"].median().to_dict().items()
                        }

                if not expected_lookup:
                    expected_source = "token_ledger_fallback"
                    token_live = _read_csv(TOKEN_LEDGER_PATH)
                    if not token_live.empty and {"seller_sku", "cost_per_unit"}.issubset(set(token_live.columns)):
                        live = token_live.copy()
                        live["sku_key"] = live["seller_sku"].astype(str).str.strip().str.upper()
                        live["cost_num"] = pd.to_numeric(live["cost_per_unit"], errors="coerce")
                        live["status_key"] = live.get("status", "").astype(str).str.strip().str.lower()
                        live = live.loc[
                            (live["sku_key"] != "") & live["cost_num"].notna() & live["cost_num"].gt(0.0)
                        ].copy()
                        if not live.empty:
                            available = live.loc[live["status_key"].eq("available")].copy()
                            base = available if not available.empty else live
                            if "sort_rank" in base.columns:
                                base["sort_rank_num"] = pd.to_numeric(base.get("sort_rank", ""), errors="coerce")
                            elif "lot_rank_num" in base.columns:
                                base["sort_rank_num"] = pd.to_numeric(base.get("lot_rank_num", ""), errors="coerce")
                            else:
                                base["sort_rank_num"] = pd.Series([float("nan")] * len(base), index=base.index)
                            if "received_date" in base.columns:
                                base["received_dt"] = pd.to_datetime(
                                    base.get("received_date", ""),
                                    errors="coerce",
                                    utc=True,
                                    format="ISO8601",
                                )
                            else:
                                base["received_dt"] = pd.NaT
                            base["sort_rank_num"] = base["sort_rank_num"].fillna(10**12)
                            base["received_dt"] = base["received_dt"].fillna(pd.Timestamp("2262-04-11T00:00:00Z"))
                            base = base.sort_values(["sku_key", "sort_rank_num", "received_dt"], kind="stable")
                            first = base.groupby("sku_key", as_index=False).head(1).copy()
                            expected_lookup = {
                                str(r["sku_key"]).strip().upper(): float(r["cost_num"])
                                for _, r in first.iterrows()
                            }

                    token_hist = _read_csv(OUT / "token_cogs_ledger.csv")
                    if (
                        not token_hist.empty
                        and {"seller_sku", "cogs_exvat", "cogs_total"}.issubset(set(token_hist.columns))
                    ):
                        hist = token_hist.copy()
                        hist["sku_key"] = hist["seller_sku"].astype(str).str.strip().str.upper()
                        hist["cogs_ex_num"] = pd.to_numeric(hist["cogs_exvat"], errors="coerce")
                        hist["cogs_total_num"] = pd.to_numeric(hist["cogs_total"], errors="coerce")
                        if recover_cogs_vat:
                            hist["basis_num"] = hist["cogs_ex_num"].where(
                                hist["cogs_ex_num"].gt(0.0), hist["cogs_total_num"]
                            )
                        else:
                            hist["basis_num"] = hist["cogs_total_num"].where(
                                hist["cogs_total_num"].gt(0.0), hist["cogs_ex_num"]
                            )
                        hist = hist.loc[
                            (hist["sku_key"] != "")
                            & hist["basis_num"].notna()
                            & hist["basis_num"].gt(0.0)
                        ].copy()
                        if not hist.empty:
                            med = hist.groupby("sku_key")["basis_num"].median().to_dict()
                            for sku_key, val in med.items():
                                if sku_key not in expected_lookup:
                                    expected_lookup[str(sku_key).strip().upper()] = float(val)

                compared = 0
                missing_expected = 0
                mismatches: List[str] = []
                for _, row in snap.iterrows():
                    sku_key = str(row.get("sku", "") or "").strip().upper()
                    if not sku_key:
                        continue
                    expected = expected_lookup.get(sku_key)
                    observed = _safe_float(row.get("cogs_total_gbp", ""))
                    if observed is None:
                        continue
                    if expected is None:
                        missing_expected += 1
                        continue
                    compared += 1
                    if abs(observed - expected) > 0.01:
                        mismatches.append(f"{sku_key}:{observed:.2f}!={expected:.2f}")
                _add(
                    rows,
                    "h_floor_phase1_cogs_basis_drift",
                    "ok" if not mismatches else "fail",
                    str(len(mismatches)),
                    (
                        f"date={today};latest_asof={latest_asof};rows_in_run={len(snap.index)};compared={compared};"
                        f"missing_expected={missing_expected};expected_source={expected_source};sample={','.join(mismatches[:5])}"
                    ),
                )

    legacy = _read_csv(H_LEGACY_EXECUTION_LOG_PATH)
    required_legacy_cols = {"event_ts_utc", "profit_floor_cogs_exvat_gbp", "profit_floor_cogs_total_gbp"}
    if legacy.empty or not required_legacy_cols.issubset(set(legacy.columns)):
        _add(
            rows,
            "h_floor_legacy_cogs_basis_drift",
            "ok",
            "0",
            f"path={H_LEGACY_EXECUTION_LOG_PATH};rows={len(legacy.index)}",
        )
    else:
        leg = legacy.copy()
        leg["event_date"] = leg["event_ts_utc"].astype(str).str.strip().str[:10]
        leg = leg.loc[leg["event_date"].eq(today)].copy()
        leg["cogs_ex"] = pd.to_numeric(leg["profit_floor_cogs_exvat_gbp"], errors="coerce")
        leg["cogs_total"] = pd.to_numeric(leg["profit_floor_cogs_total_gbp"], errors="coerce")
        cmp = leg.loc[leg["cogs_ex"].notna() & leg["cogs_total"].notna()].copy()
        drift = cmp.loc[cmp["cogs_total"] > (cmp["cogs_ex"] + 0.01)].copy()
        _add(
            rows,
            "h_floor_legacy_cogs_basis_drift",
            "ok" if drift.empty else "fail",
            str(len(drift.index)),
            (
                f"date={today};rows_today={len(leg.index)};compared={len(cmp.index)};"
                f"sample={','.join(drift.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
            ),
        )

    trace = _read_csv(H_FLOOR_TRUTH_TRACE_PATH)
    required_trace_cols = {
        "asof_utc",
        "sku",
        "floor_total_gbp",
        "sale_exvat_gbp",
        "vat_rate",
        "cogs_exvat_gbp",
        "fba_exvat_gbp",
        "referral_amount_gbp",
        "digital_fee_exvat_gbp",
        "margin_exvat_gbp",
        "source_referral",
        "band_bucket",
        "reason_codes_csv",
        "used_order_data_flag",
    }
    h_paused = _h_cycle_pause_requested()
    h_running = _h_cycle_running()
    try:
        trace_empty = trace.empty
    except Exception as exc:
        note = f"path={H_FLOOR_TRUTH_TRACE_PATH};read_error={str(exc)[:240]}"
        if h_paused:
            note = f"{note}; h_cycle_pause_requested=1"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", note)
        elif h_running:
            note = f"{note}; h_cycle_running=1; awaiting_trace_rows"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", note)
        else:
            _add(rows, "h_floor_no_order_inputs", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_band_integrity", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_source_coverage", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "warn", "not_checked", note)
            _add(rows, "h_floor_formula_consistency", "warn", "not_checked", note)
        return

    if trace_empty:
        msg = f"path={H_FLOOR_TRUTH_TRACE_PATH}"
        if h_paused:
            note = f"{msg}; h_cycle_pause_requested=1"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", note)
        elif h_running:
            note = f"{msg}; h_cycle_running=1; awaiting_trace_rows"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", note)
        else:
            _add(rows, "h_floor_no_order_inputs", "warn", "not_checked", msg)
            _add(rows, "h_floor_referral_band_integrity", "warn", "not_checked", msg)
            _add(rows, "h_floor_referral_source_coverage", "warn", "not_checked", msg)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "warn", "not_checked", msg)
            _add(rows, "h_floor_formula_consistency", "warn", "not_checked", msg)
        return

    if not required_trace_cols.issubset(set(trace.columns)):
        missing_cols = ",".join(sorted(required_trace_cols.difference(set(trace.columns))))
        _add(rows, "h_floor_no_order_inputs", "fail", "missing_columns", missing_cols)
        _add(rows, "h_floor_referral_band_integrity", "fail", "missing_columns", missing_cols)
        _add(rows, "h_floor_referral_source_coverage", "fail", "missing_columns", missing_cols)
        _add(rows, "h_floor_referral_source_coverage_parked_observability", "fail", "missing_columns", missing_cols)
        _add(rows, "h_floor_formula_consistency", "fail", "missing_columns", missing_cols)
        return

    tr = trace.copy()
    tr["asof_date"] = tr["asof_utc"].astype(str).str.strip().str[:10]
    tr = tr.loc[tr["asof_date"].eq(today)].copy()
    if tr.empty:
        note = f"date={today};path={H_FLOOR_TRUTH_TRACE_PATH};rows_today=0"
        if h_paused:
            paused_note = f"{note}; h_cycle_pause_requested=1"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", paused_note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", paused_note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", paused_note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", paused_note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", paused_note)
        elif h_running:
            running_note = f"{note}; h_cycle_running=1; awaiting_rows_today"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", running_note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", running_note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", running_note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", running_note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", running_note)
        else:
            _add(rows, "h_floor_no_order_inputs", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_band_integrity", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_source_coverage", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "warn", "not_checked", note)
            _add(rows, "h_floor_formula_consistency", "warn", "not_checked", note)
        return

    used_flag = tr["used_order_data_flag"].astype(str).str.strip().str.lower()
    source_cogs = tr.get("source_cogs", pd.Series([""] * len(tr), index=tr.index)).astype(str).str.strip().str.lower()
    source_ref = tr.get("source_referral", pd.Series([""] * len(tr), index=tr.index)).astype(str).str.strip().str.lower()
    source_fba = tr.get("source_fba", pd.Series([""] * len(tr), index=tr.index)).astype(str).str.strip().str.lower()
    order_like = used_flag.isin({"1", "true", "yes", "y", "on"}) | source_cogs.str.contains("order", na=False) | source_ref.str.contains("order", na=False) | source_fba.str.contains("order", na=False)
    order_rows = tr.loc[order_like].copy()
    _add(
        rows,
        "h_floor_no_order_inputs",
        "ok" if order_rows.empty else "fail",
        str(len(order_rows.index)),
        (
            f"date={today};rows_today={len(tr.index)};sample="
            f"{','.join(order_rows.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )

    bucket = tr["band_bucket"].astype(str).str.strip()
    src = tr["source_referral"].astype(str).str.strip()
    cross_band = tr.loc[
        (
            bucket.eq("10")
            & src.isin({"L3_BAND_100", "API_BAND_100"})
        )
        | (
            bucket.eq("100")
            & src.isin({"L3_BAND_10", "API_BAND_10"})
        )
    ].copy()
    _add(
        rows,
        "h_floor_referral_band_integrity",
        "ok" if cross_band.empty else "fail",
        str(len(cross_band.index)),
        (
            f"date={today};rows_today={len(tr.index)};sample="
            f"{','.join(cross_band.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )

    reason_codes = tr["reason_codes_csv"].astype(str).str.strip()
    missing_referral = src.eq("MISSING") | reason_codes.str.contains("REFERRAL_BAND_MISSING_", regex=False)
    scope = _read_csv(PHASE1_SCOPE_PATH)
    scope_map: Dict[str, str] = {}
    if not scope.empty and {"sku", "parked_flag"}.issubset(set(scope.columns)):
        scope_map = dict(
            zip(
                scope["sku"].astype(str).str.strip(),
                scope["parked_flag"].astype(str).str.strip().str.lower(),
            )
        )
    tr["parked_flag_scope"] = tr.get("sku", pd.Series([""] * len(tr), index=tr.index)).astype(str).str.strip().map(scope_map).fillna("")
    parked_mask = tr["parked_flag_scope"].isin({"1", "true", "yes", "y"})
    non_parked_mask = ~parked_mask
    non_parked_rows = tr.loc[non_parked_mask].copy()
    parked_rows = tr.loc[parked_mask].copy()
    missing_ref_rows_non_parked = tr.loc[missing_referral & non_parked_mask].copy()
    missing_ref_rows_parked = tr.loc[missing_referral & parked_mask].copy()
    missing_ref_count = len(missing_ref_rows_non_parked.index)
    coverage_status = "ok"
    non_parked_total = len(non_parked_rows.index)
    warn_rate = _safe_float(os.environ.get("H_FLOOR_REFERRAL_COVERAGE_WARN_RATE", "0.05"))
    fail_rate = _safe_float(os.environ.get("H_FLOOR_REFERRAL_COVERAGE_FAIL_RATE", "0.20"))
    warn_rate = warn_rate if warn_rate is not None else 0.05
    fail_rate = fail_rate if fail_rate is not None else 0.20
    missing_rate = (missing_ref_count / float(non_parked_total)) if non_parked_total > 0 else 0.0
    if missing_ref_count > 0 and non_parked_total > 0:
        if missing_rate >= fail_rate:
            coverage_status = "fail"
        elif missing_rate >= warn_rate:
            coverage_status = "warn"
    _add(
        rows,
        "h_floor_referral_source_coverage",
        coverage_status,
        str(missing_ref_count),
        (
            f"date={today};rows_today={len(tr.index)};rows_non_parked={non_parked_total};"
            f"rows_parked={len(parked_rows.index)};missing_rate_pct={missing_rate*100:.2f};"
            f"warn_rate_pct={warn_rate*100:.2f};fail_rate_pct={fail_rate*100:.2f};sample="
            f"{','.join(missing_ref_rows_non_parked.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )
    _add(
        rows,
        "h_floor_referral_source_coverage_parked_observability",
        "ok",
        str(len(missing_ref_rows_parked.index)),
        (
            f"date={today};rows_parked={len(parked_rows.index)};observability_only=1;sample="
            f"{','.join(missing_ref_rows_parked.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )

    sale_ex = pd.to_numeric(tr["sale_exvat_gbp"], errors="coerce")
    cogs_ex = pd.to_numeric(tr["cogs_exvat_gbp"], errors="coerce")
    fba_ex = pd.to_numeric(tr["fba_exvat_gbp"], errors="coerce")
    ref_ex = pd.to_numeric(tr["referral_amount_gbp"], errors="coerce")
    digital_ex = pd.to_numeric(tr["digital_fee_exvat_gbp"], errors="coerce")
    margin_ex = pd.to_numeric(tr["margin_exvat_gbp"], errors="coerce")
    floor_total = pd.to_numeric(tr["floor_total_gbp"], errors="coerce")
    vat_rate = pd.to_numeric(tr["vat_rate"], errors="coerce")

    recomputed_sale = cogs_ex + fba_ex + ref_ex + digital_ex + margin_ex
    recomputed_total = (recomputed_sale * (1.0 + vat_rate)).round(2)
    comparable = sale_ex.notna() & floor_total.notna() & recomputed_sale.notna() & recomputed_total.notna()
    sale_mismatch = (sale_ex - recomputed_sale).abs() > 0.02
    floor_mismatch = (floor_total - recomputed_total).abs() > 0.02
    mismatch_mask = comparable & (sale_mismatch | floor_mismatch)
    mismatch_rows = tr.loc[mismatch_mask].copy()
    _add(
        rows,
        "h_floor_formula_consistency",
        "ok" if mismatch_rows.empty else "fail",
        str(len(mismatch_rows.index)),
        (
            f"date={today};rows_today={len(tr.index)};comparable={int(comparable.sum())};sample="
            f"{','.join(mismatch_rows.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )


def _phase1_rollout_checks(rows: List[Dict[str, str]], now_utc: datetime, log_fn) -> None:
    today = now_utc.strftime("%Y-%m-%d")
    scope = _read_csv(PHASE1_SCOPE_PATH)
    daily = _read_csv(PHASE1_DAILY_INTEL_PATH)
    refresh_timeout_seconds = max(
        float(os.environ.get("A015_DAILY_INTEL_REFRESH_TIMEOUT_SECONDS", "900") or "900"),
        5.0,
    )

    def _run_daily_intel_refresh(trigger_reason: str) -> bool:
        if _a016_refresh_is_running():
            running_pids = ",".join([str(pid) for pid in _a016_refresh_running_pids()[:5]])
            log_fn(
                "Daily intel refresh skipped because another A016 run is active "
                f"(reason={trigger_reason};active_pids={running_pids})"
            )
            return False
        log_fn(f"Daily intel refresh triggered ({trigger_reason})")
        try:
            a016_script = ROOT / "scripts" / "flows" / "A" / "A016_refresh_phase1_daily_intel.py"
            subprocess.run(
                [sys.executable, str(a016_script)],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                timeout=refresh_timeout_seconds,
            )
            log_fn("Daily intel successfully refreshed")
            return True
        except subprocess.TimeoutExpired as exc:
            log_fn("Daily intel refresh attempted but timed out")
            log_fn(
                "Daily intel refresh timeout: "
                f"{exc.__class__.__name__}: timeout={refresh_timeout_seconds:.0f}s"
            )
            return False
        except Exception as exc:
            log_fn("Daily intel refresh attempted but failed")
            log_fn(f"Daily intel refresh error: {exc.__class__.__name__}: {exc}")
            return False

    # Orchestration guard: if scope is newer than daily-intel latest output,
    # trigger one A016 refresh attempt before evaluating freshness gates.
    refresh_attempted = False
    scope_mtime_guard = _parse_utc_ts(_file_info(PHASE1_SCOPE_PATH).get("mtime_utc", ""))
    daily_latest_mtime_guard = _parse_utc_ts(_file_info(PHASE1_DAILY_INTEL_LATEST_PATH).get("mtime_utc", ""))
    if scope_mtime_guard and (
        daily_latest_mtime_guard is None or daily_latest_mtime_guard + timedelta(seconds=1) < scope_mtime_guard
    ):
        refresh_attempted = _run_daily_intel_refresh("scope_newer_than_daily_latest")

    if refresh_attempted:
        # Re-read after attempted refresh so existing health checks use latest artifacts.
        scope = _read_csv(PHASE1_SCOPE_PATH)
        daily = _read_csv(PHASE1_DAILY_INTEL_PATH)

    if scope.empty:
        _add(rows, "a_daily_intel_coverage_non_parked", "fail", "missing_scope", f"path {PHASE1_SCOPE_PATH}")
        _add(rows, "a_daily_intel_compliance_nonempty_non_parked", "fail", "missing_scope", f"path {PHASE1_SCOPE_PATH}")
        _add(rows, "h_parked_sku_write_attempts", "warn", "missing_scope", f"path {PHASE1_SCOPE_PATH}")
        _add(rows, "h_scope_non_parked_matches_targets", "fail", "missing_scope", f"path {PHASE1_SCOPE_PATH}")
    elif "sku" not in scope.columns or "parked_flag" not in scope.columns:
        _add(rows, "a_daily_intel_coverage_non_parked", "fail", "missing_scope_cols", "required=sku,parked_flag")
        _add(rows, "a_daily_intel_compliance_nonempty_non_parked", "fail", "missing_scope_cols", "required=sku,parked_flag")
        _add(rows, "h_parked_sku_write_attempts", "warn", "missing_scope_cols", "required=sku,parked_flag")
        _add(rows, "h_scope_non_parked_matches_targets", "fail", "missing_scope_cols", "required=sku,parked_flag")
    else:
        scoped = scope.copy()
        scoped["sku_key"] = scoped["sku"].astype(str).str.strip().str.upper()
        scoped["parked_key"] = scoped["parked_flag"].astype(str).str.strip()
        scope_skus = set(scoped["sku_key"].tolist())
        non_parked_skus = set(scoped.loc[~scoped["parked_key"].eq("1"), "sku_key"].tolist())
        parked_skus = set(scoped.loc[scoped["parked_key"].eq("1"), "sku_key"].tolist())
        parked_reason_map = _load_parked_sku_reasons()
        scope_reason_col = ""
        if "park_reason_codes" in scoped.columns:
            scope_reason_col = "park_reason_codes"
        elif "park_reason_code" in scoped.columns:
            scope_reason_col = "park_reason_code"
        elif "park_reason" in scoped.columns:
            scope_reason_col = "park_reason"
        if scope_reason_col:
            for _, row in scoped.loc[scoped["parked_key"].eq("1")].iterrows():
                sku_key = str(row.get("sku_key", "")).strip().upper()
                reason_val = str(row.get(scope_reason_col, "")).strip()
                if sku_key and reason_val and sku_key not in parked_reason_map:
                    parked_reason_map[sku_key] = reason_val
        if parked_reason_map:
            parked_skus = parked_skus.union(set(parked_reason_map.keys()))
            non_parked_skus = set([sku for sku in non_parked_skus if sku not in parked_skus])
        required_daily_skus_list, required_meta = daily_intel_required_skus.derive_required_daily_skus(
            scope,
            scope_path=PHASE1_SCOPE_PATH,
            parked_skus_path=PARKED_SKUS_PATH,
            out_dir=OUT,
            inventory_summaries_path=INVENTORY_SUMMARIES_PATH,
            stock_snapshot_latest_path=STOCK_SNAPSHOT_LATEST_PATH,
        )
        required_daily_skus = set(required_daily_skus_list)
        dropped_skus = set()
        if "sale_status" in scoped.columns:
            scoped["sale_status_key"] = scoped["sale_status"].astype(str).str.strip().str.lower()
            dropped_skus = set(scoped.loc[scoped["sale_status_key"].eq("dropped"), "sku_key"].tolist())
        stock_source_path = str(required_meta.get("stock_source_path", "") or "")
        scope_mtime_utc = str(required_meta.get("scope_mtime_utc", "") or "")
        stock_source_mtime_utc = str(required_meta.get("stock_source_mtime_utc", "") or "")
        daily_data_mtime_utc = _file_info(PHASE1_DAILY_INTEL_PATH).get("mtime_utc", "")
        daily_latest_mtime_utc = _file_info(PHASE1_DAILY_INTEL_LATEST_PATH).get("mtime_utc", "")
        daily_data_dt = _parse_utc_ts(daily_data_mtime_utc)
        daily_latest_dt = _parse_utc_ts(daily_latest_mtime_utc)
        daily_mtime_utc = daily_data_mtime_utc
        daily_mtime_source = "daily_intel"
        if daily_latest_dt is not None and (daily_data_dt is None or daily_latest_dt > daily_data_dt):
            daily_mtime_utc = daily_latest_mtime_utc
            daily_mtime_source = "daily_intel_latest"

        daily_today = pd.DataFrame()
        covered_required_count = 0
        freshness_reason = ""
        freshness_notes = ""

        if daily.empty:
            freshness_reason = "missing_daily_intel"
        elif "sku" not in daily.columns or "date_utc" not in daily.columns:
            freshness_reason = "missing_daily_cols"
            freshness_notes = "required=sku,date_utc"
        else:
            daily_today = daily.copy()
            daily_today["sku_key"] = daily_today["sku"].astype(str).str.strip().str.upper()
            daily_today["date_key"] = daily_today["date_utc"].astype(str).str.strip()
            daily_today = daily_today.loc[daily_today["date_key"].eq(today)].copy()
            if daily_today.empty:
                freshness_reason = "missing_today_rows"
            else:
                covered_skus = set(daily_today["sku_key"].tolist())
                covered_required_count = len(required_daily_skus.intersection(covered_skus))
                daily_dt = _parse_utc_ts(daily_mtime_utc)
                scope_dt = _parse_utc_ts(scope_mtime_utc)
                stock_source_dt = _parse_utc_ts(stock_source_mtime_utc)
                if daily_dt is None:
                    freshness_reason = "daily_mtime_unknown"
                elif scope_dt is not None and daily_dt + timedelta(seconds=1) < scope_dt:
                    freshness_reason = "stale_vs_scope"
                elif stock_source_dt is not None and daily_dt + timedelta(seconds=1) < stock_source_dt:
                    freshness_reason = "stale_vs_stock_source"

        freshness_context = (
            f"date={today}; required={len(required_daily_skus)}; "
            f"non_parked={int(required_meta.get('non_parked', len(non_parked_skus)) or 0)}; "
            f"dropped={int(required_meta.get('dropped', len(dropped_skus)) or 0)}; "
            f"covered={covered_required_count}; stock_source={stock_source_path}; "
            f"scope_mtime_utc={scope_mtime_utc}; daily_mtime_utc={daily_mtime_utc}; "
            f"stock_source_mtime_utc={stock_source_mtime_utc}; "
            f"daily_mtime_source={daily_mtime_source}"
        )

        if freshness_reason:
            _add(
                rows,
                "a_daily_intel_prerequisite_freshness",
                "fail",
                freshness_reason,
                f"{freshness_context}; {freshness_notes}".strip(),
            )
            _add(
                rows,
                "a_daily_intel_coverage_non_parked",
                "fail",
                "prerequisite_blocked",
                f"blocked_by=a_daily_intel_prerequisite_freshness; {freshness_context}",
            )
            _add(
                rows,
                "a_daily_intel_compliance_nonempty_non_parked",
                "fail",
                "prerequisite_blocked",
                f"blocked_by=a_daily_intel_prerequisite_freshness; {freshness_context}",
            )
        else:
            _add(rows, "a_daily_intel_prerequisite_freshness", "ok", "0", freshness_context)
            covered_skus = set(daily_today["sku_key"].tolist())
            covered_required = required_daily_skus.intersection(covered_skus)
            missing_skus = sorted([s for s in required_daily_skus if s not in covered_skus])

            _add(
                rows,
                "a_daily_intel_coverage_non_parked",
                "ok" if not missing_skus else "fail",
                str(len(missing_skus)),
                (
                    f"date={today}; required={len(required_daily_skus)}; dropped={len(dropped_skus)}; "
                    f"non_parked={len(non_parked_skus)}; covered={len(covered_required)}; "
                    f"stock_source={stock_source_path};missing_sample={','.join(missing_skus[:5])}"
                ),
            )

            if "compliance_ceiling_landed_gbp" not in daily_today.columns:
                _add(
                    rows,
                    "a_daily_intel_compliance_nonempty_non_parked",
                    "fail",
                    "missing_daily_col",
                    "required=compliance_ceiling_landed_gbp",
                )
            else:
                missing_row_count = 0
                blank_compliance_count = 0
                reason_coded_count = 0
                for sku in required_daily_skus:
                    sku_rows = daily_today.loc[daily_today["sku_key"].eq(sku)].copy()
                    if sku_rows.empty:
                        missing_row_count += 1
                        continue
                    has_compliance = sku_rows["compliance_ceiling_landed_gbp"].astype(str).str.strip().ne("").any()
                    if has_compliance:
                        continue
                    has_compliance_status = (
                        "compliance_status" in sku_rows.columns
                        and sku_rows["compliance_status"].astype(str).str.strip().ne("").any()
                    )
                    has_compliance_reason = (
                        "compliance_reason_code" in sku_rows.columns
                        and sku_rows["compliance_reason_code"].astype(str).str.strip().ne("").any()
                    )
                    if has_compliance_status or has_compliance_reason:
                        reason_coded_count += 1
                        continue
                    if not has_compliance:
                        blank_compliance_count += 1
                bad_total = missing_row_count + blank_compliance_count
                _add(
                    rows,
                    "a_daily_intel_compliance_nonempty_non_parked",
                    "ok" if bad_total == 0 else "fail",
                    str(bad_total),
                    (
                        f"date={today}; required={len(required_daily_skus)}; dropped={len(dropped_skus)}; "
                        f"non_parked={len(non_parked_skus)}; missing_rows={missing_row_count}; "
                        f"blank_compliance={blank_compliance_count}; reason_coded={reason_coded_count}; "
                        f"stock_source={stock_source_path}"
                    ),
                )

            pilot_daily = daily_today.loc[daily_today["sku_key"].eq(OFFICIAL_PILOT_SKU)].copy()
            required_cols = {
                "bbp_max_sold_gbp",
                "cpt_gbp",
                "cpt_x1_2_gbp",
                "ceiling_rule_value_gbp",
                "ceiling_source_used",
                "ceiling_inputs_missing_flag",
            }
            pilot_key = OFFICIAL_PILOT_SKU.strip().upper()
            if pilot_key in parked_skus:
                parked_reason = parked_reason_map.get(pilot_key, "parked")
                parked_msg = f"sku={OFFICIAL_PILOT_SKU};date={today};reason={parked_reason}"
                _add(rows, "h_ceiling_rule_bbp_missing_trial", "ok", "skipped_parked", parked_msg)
                _add(rows, "h_ceiling_rule_cpt_missing_trial", "ok", "skipped_parked", parked_msg)
                _add(rows, "h_ceiling_rule_inputs_missing_trial", "ok", "skipped_parked", parked_msg)
            elif pilot_daily.empty:
                _add(rows, "h_ceiling_rule_bbp_missing_trial", "warn", "missing_row", f"sku={OFFICIAL_PILOT_SKU};date={today}")
                _add(rows, "h_ceiling_rule_cpt_missing_trial", "warn", "missing_row", f"sku={OFFICIAL_PILOT_SKU};date={today}")
                _add(rows, "h_ceiling_rule_inputs_missing_trial", "warn", "missing_row", f"sku={OFFICIAL_PILOT_SKU};date={today}")
            else:
                missing_cols = sorted([c for c in required_cols if c not in pilot_daily.columns])
                if missing_cols:
                    msg = f"required={','.join(missing_cols)}"
                    _add(rows, "h_ceiling_rule_bbp_missing_trial", "fail", "missing_columns", msg)
                    _add(rows, "h_ceiling_rule_cpt_missing_trial", "fail", "missing_columns", msg)
                    _add(rows, "h_ceiling_rule_inputs_missing_trial", "fail", "missing_columns", msg)
                else:
                    bbp_missing = pilot_daily["bbp_max_sold_gbp"].astype(str).str.strip().eq("").all()
                    cpt_missing = pilot_daily["cpt_x1_2_gbp"].astype(str).str.strip().eq("").all()
                    both_missing = pilot_daily["ceiling_inputs_missing_flag"].astype(str).str.strip().eq("1").any()
                    source_sample = pilot_daily["ceiling_source_used"].astype(str).str.strip().head(1).tolist()
                    source_used = source_sample[0] if source_sample else ""
                    _add(
                        rows,
                        "h_ceiling_rule_bbp_missing_trial",
                        "warn" if bbp_missing else "ok",
                        "1" if bbp_missing else "0",
                        f"sku={OFFICIAL_PILOT_SKU};date={today};source={source_used}",
                    )
                    _add(
                        rows,
                        "h_ceiling_rule_cpt_missing_trial",
                        "warn" if cpt_missing else "ok",
                        "1" if cpt_missing else "0",
                        f"sku={OFFICIAL_PILOT_SKU};date={today};source={source_used}",
                    )
                    _add(
                        rows,
                        "h_ceiling_rule_inputs_missing_trial",
                        "fail" if both_missing else "ok",
                        "1" if both_missing else "0",
                        f"sku={OFFICIAL_PILOT_SKU};date={today};source={source_used}",
                    )

        state_payload, state_path = _read_first_json(H_PRICING_STATE_PATH_CANDIDATES)
        if not state_payload:
            searched = "|".join(str(p).replace("\\", "/") for p in H_PRICING_STATE_PATH_CANDIDATES)
            _add(rows, "h_scope_non_parked_matches_targets", "warn", "missing_state", f"paths {searched}")
        else:
            processed_csv = str(state_payload.get("phase1_skus_processed_csv", "") or "").strip()
            processed_skus = {
                part.strip().upper()
                for part in processed_csv.split(",")
                if part.strip()
            }
            invalid_processed = sorted([s for s in processed_skus if s not in scope_skus])
            skipped_parked = _safe_int(state_payload.get("phase1_skus_skipped_parked_count", "0"))
            # Canonical-universe runs may intentionally skip parked SKUs.
            # Health should only fail when processed SKUs are outside the canonical scope.
            mismatch_total = len(invalid_processed)
            resolved_state_path = str(state_path).replace("\\", "/") if state_path is not None else ""
            _add(
                rows,
                "h_scope_non_parked_matches_targets",
                "ok" if mismatch_total == 0 else "fail",
                str(mismatch_total),
                (
                    f"processed={len(processed_skus)}; non_parked_scope={len(non_parked_skus)}; "
                    f"skipped_parked={skipped_parked}; invalid_processed_sample={','.join(invalid_processed[:5])}; "
                    f"state_path={resolved_state_path}"
                ),
            )

        execution = _read_csv(PHASE1_EXECUTION_LOG_PATH)
        if execution.empty or "sku" not in execution.columns or "write_status" not in execution.columns:
            _add(rows, "h_parked_sku_write_attempts", "ok", "0", f"path {PHASE1_EXECUTION_LOG_PATH}; no_rows")
        else:
            exec_today = execution.copy()
            exec_today["sku_key"] = exec_today["sku"].astype(str).str.strip().str.upper()
            if "event_ts_utc" in exec_today.columns:
                exec_today["event_date"] = exec_today["event_ts_utc"].astype(str).str.strip().str[:10]
                exec_today = exec_today.loc[exec_today["event_date"].eq(today)].copy()
            parked_exec = exec_today.loc[exec_today["sku_key"].isin(parked_skus)].copy()
            non_attempt_status = {"", "NO_WRITE_REQUIRED", "READ_ONLY_NO_WRITE", "OBSERVABILITY_BLOCK_NO_WRITE"}
            parked_exec["write_status_key"] = parked_exec["write_status"].astype(str).str.strip().str.upper()
            attempts = parked_exec.loc[~parked_exec["write_status_key"].isin(non_attempt_status)].copy()
            parked_reasons = sorted(
                {
                    token.strip().upper()
                    for sku_key in parked_exec["sku_key"].astype(str).str.strip().str.upper().tolist()
                    for token in re.split(r"[|,;]", str(parked_reason_map.get(sku_key, "")).strip())
                    if token.strip()
                }
            )
            out_of_stock_only = bool(parked_reasons) and all(
                reason in {"PARK_OUT_OF_STOCK", "OUT_OF_STOCK", "PARKED_OUT_OF_STOCK"}
                for reason in parked_reasons
            )
            event_time_cols = {
                "parked_flag_at_event",
                "park_reason_at_event",
                "park_reason_codes_at_event",
                "was_parked_at_event",
            }
            event_time_proof_available = any(col in parked_exec.columns for col in event_time_cols)
            parked_status = "ok"
            if not attempts.empty:
                parked_status = "warn" if (out_of_stock_only and not event_time_proof_available) else "fail"
            _add(
                rows,
                "h_parked_sku_write_attempts",
                parked_status,
                str(len(attempts.index)),
                (
                    f"date={today}; parked_skus={len(parked_skus)}; parked_rows_today={len(parked_exec.index)}; "
                    f"attempt_statuses={','.join(sorted(set(attempts['write_status_key'].tolist()))[:5])}; "
                    f"park_reasons={','.join(parked_reasons[:5])}; "
                    f"event_time_proof_available={1 if event_time_proof_available else 0}; "
                    f"severity_basis={'out_of_stock_only_no_event_time_proof' if parked_status == 'warn' else 'strict'}"
                ),
            )

    api_rows = _read_jsonl_rows(API_CALL_LOG_JSONL)
    if not api_rows:
        _add(rows, "h_no_cpt_calls_in_h_cycle", "warn", "missing_or_empty", f"path {API_CALL_LOG_JSONL}")
    else:
        h_cpt_rows: List[Dict[str, object]] = []
        for row in api_rows:
            endpoint = str(row.get("endpoint", "") or "").strip()
            if endpoint != H_CPT_ENDPOINT:
                continue
            script_name = str(row.get("script_name", "") or "").strip()
            script_upper = script_name.upper()
            is_h_script = script_upper.startswith("RUN_H_") or script_upper.startswith("H110_")
            if not is_h_script:
                continue
            ts = _parse_utc_ts(row.get("timestamp_utc", ""))
            if ts is not None and ts.strftime("%Y-%m-%d") != today:
                continue
            h_cpt_rows.append(row)
        sample = []
        for row in h_cpt_rows[:5]:
            sample.append(f"{row.get('script_name', '')}@{row.get('timestamp_utc', '')}")
        _add(
            rows,
            "h_no_cpt_calls_in_h_cycle",
            "ok" if not h_cpt_rows else "fail",
            str(len(h_cpt_rows)),
            f"date={today}; endpoint={H_CPT_ENDPOINT}; sample={';'.join(sample)}",
        )

    _h_floor_policy_checks(rows, now_utc)


def _send_toast(title: str, body: str) -> None:
    # Windows toast via PowerShell (no external modules).
    ps = f"""
$ErrorActionPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$text = $template.GetElementsByTagName('text')
$text.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null
$text.Item(1).AppendChild($template.CreateTextNode('{body}')) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('SellerOne')
$notifier.Show($toast)
"""
    try:
        run_kwargs: Dict[str, object] = {
            "check": False,
            "capture_output": True,
            "text": True,
        }
        if os.name == "nt":
            no_window = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if no_window:
                run_kwargs["creationflags"] = no_window
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0))
                startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
                run_kwargs["startupinfo"] = startupinfo
            except Exception:
                pass
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], **run_kwargs)
    except Exception:
        pass


def _read_alert_snooze(path: Path, now_utc: datetime) -> Dict[str, str]:
    out = {
        "active": "no",
        "status": "off",
        "snooze_until_utc": "",
        "reason": "",
        "error": "",
    }
    if not path.exists():
        return out
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        out["status"] = "invalid"
        out["error"] = f"read_error: {exc}"
        return out
    if not isinstance(payload, dict):
        out["status"] = "invalid"
        out["error"] = "payload_not_object"
        return out
    until_raw = str(payload.get("snooze_until_utc", "")).strip()
    reason = str(payload.get("reason", "")).strip()
    out["snooze_until_utc"] = until_raw
    out["reason"] = reason
    if not until_raw:
        out["status"] = "invalid"
        out["error"] = "missing_snooze_until_utc"
        return out
    try:
        until_dt = datetime.fromisoformat(until_raw.replace("Z", "+00:00"))
        if until_dt.tzinfo is None:
            until_dt = until_dt.replace(tzinfo=timezone.utc)
    except Exception:
        out["status"] = "invalid"
        out["error"] = "invalid_snooze_until_utc"
        return out
    if until_dt > now_utc:
        out["active"] = "yes"
        out["status"] = "active"
    else:
        out["status"] = "expired"
    return out


def main() -> None:
    args = _parse_cli_args()
    runtime = _resolve_runtime_paths(args)
    profile = str(runtime["profile"])
    checklist_path = Path(runtime["checklist_path"])
    alert_state_path = Path(runtime["alert_state_path"])
    alert_history_path = Path(runtime["alert_history_path"])
    health_status_path = Path(runtime["health_status_path"])
    no_toast = bool(runtime["no_toast"])

    def log(msg: str) -> None:
        print(f"[health_check] {msg}")

    abs_checklist_path = checklist_path.resolve()
    print(f"A015 profile={profile} writing_checklist={abs_checklist_path}")
    if profile != "global":
        print("NOTE: global files NOT updated: out/system_health_checklist.csv, out/cycle_alerts/checklist_H.csv")
    else:
        print("NOTE: global files updated: out/system_health_checklist.csv, out/cycle_alerts/checklist_H.csv")

    rows: List[Dict[str, str]] = []
    OUT.mkdir(parents=True, exist_ok=True)
    checklist_path.parent.mkdir(parents=True, exist_ok=True)
    alert_state_path.parent.mkdir(parents=True, exist_ok=True)
    alert_history_path.parent.mkdir(parents=True, exist_ok=True)
    health_status_path.parent.mkdir(parents=True, exist_ok=True)
    now_utc_dt = datetime.now(timezone.utc)
    snooze = _read_alert_snooze(ALERT_SNOOZE_PATH, now_utc_dt)
    if snooze["error"]:
        _add(rows, "h_health_alert_snooze_config", "warn", "invalid", snooze["error"])
    else:
        snooze_notes = ""
        if snooze["snooze_until_utc"]:
            snooze_notes = f"until={snooze['snooze_until_utc']}"
            if snooze["reason"]:
                snooze_notes += f";reason={snooze['reason']}"
        _add(rows, "h_health_alert_snooze_config", "ok", snooze["status"], snooze_notes)

    _cycle_failure_ledger_schema_check(rows)

    if not health_status_path.exists():
        pd.DataFrame(columns=["timestamp_utc", "status", "fail_count", "warn_count", "notes"]).to_csv(
            health_status_path, index=False
        )

    log(
        "profile_config "
        f"profile={profile} "
        f"checklist_path={checklist_path} "
        f"alert_state_path={alert_state_path} "
        f"alert_history_path={alert_history_path} "
        f"health_status_path={health_status_path} "
        f"no_toast={'1' if no_toast else '0'}"
    )

    log("loading orders_all.csv")
    orders_all = _read_csv(ORDERS_ALL_PATH, usecols=["amazon_order_id", "purchase_date"])
    log(f"orders_all rows: {len(orders_all)}")
    log("loading orders_all status view")
    orders_all_status = _read_csv(ORDERS_ALL_PATH)
    if not orders_all_status.empty:
        for col in ["amazon_order_id", "order_status"]:
            if col not in orders_all_status.columns:
                orders_all_status[col] = ""
        orders_all_status = orders_all_status[["amazon_order_id", "order_status"]].copy()
    log(f"orders_all status rows: {len(orders_all_status)}")

    log("loading order_items_all.csv")
    order_items_all = _read_csv(OUT / "order_items_all.csv", usecols=["amazon_order_id", "seller_sku", "quantity_shipped", "quantity_ordered"])
    log(f"order_items_all rows: {len(order_items_all)}")

    log("loading order_master.csv")
    order_master = _read_csv(
        ORDER_MASTER_PATH,
        usecols=[
            "Date",
            "Order ID",
            "SKU",
            "lvl",
            "COGS_Total",
            "COGS_ExVAT",
            "Quantity Ordered",
            "COGS_Placeholder_Applied",
            "COGS_Basis_Type",
            "COGS_Basis_Source",
            "COGS_Basis_Date",
            "Missing_Token_Flag",
            "Missing_Token_Reason",
        ],
    )
    log("loading order_master_prev.csv")
    order_master_prev = _read_csv(OUT / "order_master_prev.csv", usecols=["Order ID", "SKU"])
    log(f"order_master rows: {len(order_master)}")

    log("loading financial_events_level1.csv")
    l1 = _read_csv(OUT / "financial_events_level1.csv", usecols=["Order ID", "SKU", "Date", "Quantity Ordered"])
    log("loading financial_events_level2.csv")
    l2 = _read_csv(OUT / "financial_events_level2.csv", usecols=["Order ID", "SKU", "Quantity Ordered"])
    log("loading financial_events_level3_official.csv")
    l3 = _read_csv(OUT / "financial_events_level3_official.csv", usecols=["Order ID", "SKU"])
    log(f"level1 rows: {len(l1)}")

    log("loading token_ledger_live.csv")
    token_ledger = _read_csv(TOKEN_LEDGER_PATH)
    for col in ["token_id", "seller_sku", "status"]:
        if col not in token_ledger.columns:
            token_ledger[col] = ""
    log(f"token_ledger rows: {len(token_ledger)}")
    log("loading token_allocations_live.csv")
    token_allocations = _read_csv(TOKEN_ALLOCATIONS_PATH)
    log(f"token_allocations rows: {len(token_allocations)}")

    log("loading token_cogs_ledger.csv")
    token_cogs_path = OUT / "token_cogs_ledger.csv"
    token_cogs = _read_csv(token_cogs_path)
    # Normalize column names for compatibility across versions
    token_cogs = token_cogs.rename(columns={
        "Order ID": "order_id",
        "SKU": "seller_sku",
    })
    if "order_id" not in token_cogs.columns or "seller_sku" not in token_cogs.columns:
        raise ValueError(f"token_cogs_ledger.csv missing required columns: order_id/seller_sku (found {list(token_cogs.columns)})")
    log(f"token_cogs rows: {len(token_cogs)}")

    log("loading inventory_summaries.csv")
    inventory = _read_csv(OUT / "inventory_summaries.csv")
    log(f"inventory rows: {len(inventory)}")

    # Orders overview
    orders_all_count = len(orders_all)
    _add(rows, "orders_all_rows", "ok" if orders_all_count > 0 else "fail", str(orders_all_count))
    _critical_freshness_check(
        rows,
        "b_orders_all_freshness",
        [ORDERS_ALL_PATH],
        warn_after_minutes=float(os.environ.get("B_ORDERS_ALL_WARN_MINUTES", "45")),
        fail_after_minutes=float(os.environ.get("B_ORDERS_ALL_FAIL_MINUTES", "180")),
        owner_cycle="B",
        recovery_signal="controlled_restart_gate",
        now_utc=now_utc_dt,
    )
    _critical_freshness_check(
        rows,
        "b_order_master_freshness",
        [ORDER_MASTER_PATH],
        warn_after_minutes=float(os.environ.get("B_ORDER_MASTER_WARN_MINUTES", "60")),
        fail_after_minutes=float(os.environ.get("B_ORDER_MASTER_FAIL_MINUTES", "180")),
        owner_cycle="B",
        recovery_signal="controlled_restart_gate",
        now_utc=now_utc_dt,
    )
    _relax_check_status_for_maintenance(rows, check_name="b_order_master_freshness")
    if not orders_all.empty:
        max_order_dt = _to_dt(orders_all["purchase_date"]).max()
    else:
        max_order_dt = pd.NaT

    # Order items overview
    _add(rows, "order_items_all_rows", "ok" if len(order_items_all) > 0 else "warn", str(len(order_items_all)))
    # Orders missing items within recent window (default 24h from latest order)
    gap_window_hours = float(os.environ.get("ORDER_ITEMS_GAP_WINDOW_HOURS", "24"))
    if not orders_all.empty:
        orders_all = orders_all.copy()
        orders_all["purchase_date_dt"] = _to_dt(orders_all["purchase_date"])
        max_dt = orders_all["purchase_date_dt"].max()
        if pd.notna(max_dt):
            window_start = max_dt - pd.Timedelta(hours=gap_window_hours)
            window_orders = orders_all[
                orders_all["purchase_date_dt"].notna()
                & (orders_all["purchase_date_dt"] >= window_start)
                & (orders_all["purchase_date_dt"] <= max_dt)
            ]
        else:
            window_orders = orders_all.iloc[0:0]
        if not window_orders.empty:
            item_order_ids = set(order_items_all.get("amazon_order_id", pd.Series([], dtype=str)).astype(str).str.strip())
            window_orders = window_orders.copy()
            window_orders["amazon_order_id"] = window_orders["amazon_order_id"].astype(str).str.strip()
            missing_items = window_orders[~window_orders["amazon_order_id"].isin(item_order_ids)]
            missing_count = len(missing_items)
            _add(rows, "orders_missing_items_window", "fail" if missing_count > 0 else "ok", str(missing_count))
            if missing_count > 0:
                missing_items[["amazon_order_id", "purchase_date"]].to_csv(DETAIL_ORDERS_MISSING_ITEMS, index=False)
            else:
                pd.DataFrame(columns=["amazon_order_id", "purchase_date"]).to_csv(DETAIL_ORDERS_MISSING_ITEMS, index=False)
        else:
            _add(rows, "orders_missing_items_window", "ok", "0")
            pd.DataFrame(columns=["amazon_order_id", "purchase_date"]).to_csv(DETAIL_ORDERS_MISSING_ITEMS, index=False)
    else:
        _add(rows, "orders_missing_items_window", "warn", "n/a", "missing orders_all")

    # Order master completeness
    master_rows = len(order_master)
    _add(rows, "order_master_rows", "ok" if master_rows > 0 else "fail", str(master_rows))
    if not order_master_prev.empty:
        prev_rows = len(order_master_prev)
        if master_rows < prev_rows:
            drop = prev_rows - master_rows
            note_parts = [f"prev={prev_rows}", f"current={master_rows}"]
            observed_missing_fee_keys = len(_read_order_key_file(L1_MISSING_FEE_KEYS))
            observed_missing_token_keys = len(_read_order_key_file(MISSING_TOKEN_ORDERS))
            if observed_missing_fee_keys > 0:
                note_parts.append(f"observed_missing_fee_keys={observed_missing_fee_keys}")
            if observed_missing_token_keys > 0:
                note_parts.append(f"observed_missing_token_keys={observed_missing_token_keys}")
            status = "warn"
            note = ", ".join(note_parts)
            _add(rows, "order_master_row_drop", status, str(drop), note)
        else:
            _add(rows, "order_master_row_drop", "ok", "0", f"prev={prev_rows}, current={master_rows}")
    if not order_master.empty:
        blank_sku = order_master["SKU"].isna() | (order_master["SKU"].astype(str).str.strip() == "")
        blank_date = order_master["Date"].isna() | (order_master["Date"].astype(str).str.strip() == "")
        _add(rows, "order_master_blank_sku", "fail" if blank_sku.sum() > 0 else "ok", str(int(blank_sku.sum())))
        _add(rows, "order_master_blank_date", "fail" if blank_date.sum() > 0 else "ok", str(int(blank_date.sum())))
        if "Quantity Ordered" in order_master.columns:
            qty_raw = order_master["Quantity Ordered"].astype(str).str.strip()
            blank_qty = qty_raw.isna() | qty_raw.eq("") | qty_raw.eq("nan")
            _add(rows, "order_master_blank_qty", "fail" if blank_qty.sum() > 0 else "ok", str(int(blank_qty.sum())))
        if blank_sku.any():
            bad_orders = order_master.loc[blank_sku, "Order ID"].astype(str).head(10).tolist()
            print("[health_check] blank SKU order ids (first 10):", bad_orders)
        if blank_date.any():
            bad_orders = order_master.loc[blank_date, "Order ID"].astype(str).head(10).tolist()
            print("[health_check] blank Date order ids (first 10):", bad_orders)

        max_master_dt = _to_dt(order_master["Date"]).max()
        recency_ref_dt = max_order_dt
        recency_ref_label = "orders_all"
        # Order_Master is expected to keep all current L1 keys, even when COGS is still provisional.
        # Use the latest L1 order date when it is newer than orders_all so coverage gaps stay visible.
        if not l1.empty and "Date" in l1.columns:
            try:
                l1_dates = _to_dt(l1["Date"])
                max_l1_dt = l1_dates.max()
                if pd.notna(max_l1_dt) and (pd.isna(recency_ref_dt) or max_l1_dt > recency_ref_dt):
                    recency_ref_dt = max_l1_dt
                    recency_ref_label = "l1"
            except Exception:
                pass
        if pd.notna(recency_ref_dt) and pd.notna(max_master_dt):
            gap_hours = (recency_ref_dt - max_master_dt).total_seconds() / 3600.0
            _add(
                rows,
                "order_master_date_gap_hours",
                _status_from_gap(gap_hours),
                f"{gap_hours:.2f}",
                f"{recency_ref_label} max {recency_ref_dt}; master max {max_master_dt}",
            )
        else:
            _add(rows, "order_master_date_gap_hours", "warn", "n/a", "missing dates")

        # Blank COGS (lvl >=1)
        lvl = order_master.get("lvl", pd.Series([], dtype=str)).astype(str)
        cogs = order_master.get("COGS_ExVAT", pd.Series([], dtype=str)).astype(str)
        qty = order_master.get("Quantity Ordered", pd.Series([], dtype=str)).astype(str)
        blank_cogs = (cogs.str.strip().isin(["", "0", "0.0", "0.00"])) & (lvl != "0")
        # Ignore rows with zero quantity (no cost expected).
        blank_cogs = blank_cogs & (~qty.str.strip().isin(["", "0", "0.0", "0.00"]))
        blank_cogs_count = int(blank_cogs.sum())
        _add(rows, "order_master_blank_cogs_lvl1plus", "warn" if blank_cogs_count > 0 else "ok", str(blank_cogs_count))
        if blank_cogs_count > 0:
            cols = ["Order ID", "SKU", "Date", "lvl", "COGS_ExVAT", "COGS_VAT", "COGS_Total"]
            cols = [c for c in cols if c in order_master.columns]
            details = order_master.loc[blank_cogs, cols].copy()
            details.to_csv(DETAIL_BLANK_COGS, index=False)

        # Placeholder COGS observability:
        # keep placeholder-backed rows visible as WARN (not PASS), and fail any missing-token rows
        # that still have no placeholder basis.
        placeholder_stats = _order_master_placeholder_stats(order_master)
        placeholder_rows = int(placeholder_stats.get("placeholder_rows", 0))
        missing_token_no_placeholder_rows = int(placeholder_stats.get("missing_token_no_placeholder_rows", 0))
        repeat_sku_count = int(placeholder_stats.get("placeholder_repeat_sku_count", 0))
        repeat_row_count = int(placeholder_stats.get("placeholder_repeat_row_count", 0))
        repeat_sample = placeholder_stats.get("placeholder_repeat_sample", [])
        repeat_note = ""
        if repeat_sku_count > 0:
            repeat_note = (
                f"repeat_sku_count={repeat_sku_count};repeat_row_count={repeat_row_count};"
                f"sample={','.join([str(v) for v in repeat_sample])}"
            )
        _add(
            rows,
            "order_master_placeholder_cogs_rows",
            "warn" if placeholder_rows > 0 else "ok",
            str(placeholder_rows),
            repeat_note,
        )
        _add(
            rows,
            "order_master_missing_token_no_placeholder_rows",
            "fail" if missing_token_no_placeholder_rows > 0 else "ok",
            str(missing_token_no_placeholder_rows),
        )

        placeholder_mask = (
            order_master.get("COGS_Placeholder_Applied", pd.Series([], dtype=str))
            .astype(str)
            .str.strip()
            .str.lower()
            .isin({"1", "true", "yes", "y"})
        )
        missing_no_placeholder_mask = (
            order_master.get("Missing_Token_Flag", pd.Series([], dtype=str))
            .astype(str)
            .str.strip()
            .str.lower()
            .isin({"1", "true", "yes", "y"})
            & ~placeholder_mask
        )
        if placeholder_rows > 0:
            cols = [
                "Order ID",
                "SKU",
                "Date",
                "lvl",
                "Quantity Ordered",
                "COGS_ExVAT",
                "COGS_Basis_Type",
                "COGS_Basis_Source",
                "COGS_Basis_Date",
                "Missing_Token_Reason",
            ]
            cols = [c for c in cols if c in order_master.columns]
            order_master.loc[placeholder_mask, cols].copy().to_csv(DETAIL_PLACEHOLDER_COGS, index=False)
        else:
            pd.DataFrame(
                columns=[
                    "Order ID",
                    "SKU",
                    "Date",
                    "lvl",
                    "Quantity Ordered",
                    "COGS_ExVAT",
                    "COGS_Basis_Type",
                    "COGS_Basis_Source",
                    "COGS_Basis_Date",
                    "Missing_Token_Reason",
                ]
            ).to_csv(DETAIL_PLACEHOLDER_COGS, index=False)
        if missing_token_no_placeholder_rows > 0:
            cols = [
                "Order ID",
                "SKU",
                "Date",
                "lvl",
                "Quantity Ordered",
                "COGS_ExVAT",
                "Missing_Token_Flag",
                "Missing_Token_Reason",
            ]
            cols = [c for c in cols if c in order_master.columns]
            order_master.loc[missing_no_placeholder_mask, cols].copy().to_csv(
                DETAIL_MISSING_TOKEN_NO_PLACEHOLDER,
                index=False,
            )
        else:
            pd.DataFrame(
                columns=[
                    "Order ID",
                    "SKU",
                    "Date",
                    "lvl",
                    "Quantity Ordered",
                    "COGS_ExVAT",
                    "Missing_Token_Flag",
                    "Missing_Token_Reason",
                ]
            ).to_csv(DETAIL_MISSING_TOKEN_NO_PLACEHOLDER, index=False)

    # L1 vs master key coverage
    if not l1.empty and not order_master.empty:
        coverage = _order_master_l1_coverage_stats(l1, order_master)
        missing_set = set(coverage.get("missing_set", set()))
        missing = int(coverage.get("missing_count", 0))
        note = str(coverage.get("note", ""))
        _add(rows, "l1_keys_missing_in_master", "fail" if missing > 0 else "ok", str(missing), note)
        if missing:
            missing_keys = list(missing_set)[:10]
            print("[health_check] missing L1 keys (first 10):", missing_keys)
        orphans = int(coverage.get("orphan_count", 0))
        _add(rows, "order_master_orphans_count", "fail" if orphans > 0 else "ok", str(orphans))
        if orphans:
            orphan_keys = list(set(coverage.get("orphan_set", set())))[:10]
            print("[health_check] master keys not in L1 (first 10):", orphan_keys)
    else:
        _add(rows, "l1_keys_missing_in_master", "warn", "n/a", "missing L1 or master")
        _add(rows, "order_master_orphans_count", "warn", "n/a", "missing L1 or master")

    # L3 orphans (L3 keys not in L1)
    if not l3.empty and not l1.empty:
        l1_keys = set((l1["Order ID"].astype(str).str.strip() + "||" + l1["SKU"].astype(str).str.strip()).tolist())
        l3_keys = set((l3["Order ID"].astype(str).str.strip() + "||" + l3["SKU"].astype(str).str.strip()).tolist())
        l3_orphan_keys = list(l3_keys - l1_keys)
        scoped_orphans = l3_orphan_keys
        missing_scope_dates = 0
        ignored_count = 0
        if ORPHAN_IGNORE_ORDER_IDS_FILE:
            ignore_path = Path(ORPHAN_IGNORE_ORDER_IDS_FILE)
            if ignore_path.exists():
                try:
                    try:
                        ignore_df = pd.read_csv(ignore_path, dtype=str)
                    except Exception:
                        ignore_df = pd.read_csv(ignore_path, dtype=str, sep=";")
                    ignore_ids = set()
                    if "Order number" in ignore_df.columns:
                        ids = (
                            ignore_df["Order number"]
                            .fillna("")
                            .astype(str)
                            .str.split(" / ", n=1, expand=False)
                            .str[0]
                            .str.strip()
                        )
                        ignore_ids.update([v for v in ids.tolist() if v])
                    else:
                        for col in ignore_df.columns:
                            if col.lower() in ("order id", "order_id", "amazon_order_id"):
                                ids = ignore_df[col].fillna("").astype(str).str.strip()
                                ignore_ids.update([v for v in ids.tolist() if v])
                                break
                    if ignore_ids:
                        filtered = []
                        for k in scoped_orphans:
                            order_id = k.split("||", 1)[0]
                            if order_id in ignore_ids:
                                ignored_count += 1
                                continue
                            filtered.append(k)
                        scoped_orphans = filtered
                except Exception:
                    pass
        if ORPHAN_SCOPE_START_DATE:
            try:
                scope_dt = pd.to_datetime(ORPHAN_SCOPE_START_DATE + "T00:00:00Z", utc=True)
                if not orders_all.empty and "amazon_order_id" in orders_all.columns and "purchase_date_dt" in orders_all.columns:
                    order_dates = orders_all[["amazon_order_id", "purchase_date_dt"]].dropna()
                    order_dates["amazon_order_id"] = order_dates["amazon_order_id"].astype(str).str.strip()
                    order_date_map = dict(zip(order_dates["amazon_order_id"], order_dates["purchase_date_dt"]))
                    filtered = []
                    for k in scoped_orphans:
                        order_id = k.split("||", 1)[0]
                        dt = order_date_map.get(order_id)
                        if dt is None or pd.isna(dt):
                            missing_scope_dates += 1
                            filtered.append(k)
                        elif dt >= scope_dt:
                            filtered.append(k)
                    scoped_orphans = filtered
            except Exception:
                pass
        l3_orphans = len(scoped_orphans)
        notes = ""
        if ORPHAN_SCOPE_START_DATE:
            notes = f"scope_start={ORPHAN_SCOPE_START_DATE}; missing_dates={missing_scope_dates}"
        if ignored_count:
            notes = (notes + "; " if notes else "") + f"ignored_orders={ignored_count}"
        # If an ignore list is provided, do not fail the health check on L3 orphans.
        l3_status = "ok" if (l3_orphans == 0 or ORPHAN_IGNORE_ORDER_IDS_FILE) else "fail"
        _add(rows, "l3_orphans_count", l3_status, str(l3_orphans), notes)
        if l3_orphans:
            print("[health_check] L3 keys not in L1 (first 10):", scoped_orphans[:10])
    else:
        _add(rows, "l3_orphans_count", "warn", "n/a", "missing L1 or L3")

    # Level 2 duplicate keys (Order ID + SKU)
    if not l2.empty:
        l2_keys = l2[["Order ID", "SKU"]].astype(str).agg("||".join, axis=1)
        dupes = int(l2_keys.duplicated().sum())
        _add(rows, "level2_duplicate_keys", "fail" if dupes > 0 else "ok", str(dupes))
    else:
        _add(rows, "level2_duplicate_keys", "warn", "n/a", "missing Level 2")

    # Tokens
    if not token_ledger.empty:
        total = len(token_ledger)
        available = (token_ledger["status"] == "available").sum()
        allocated = (token_ledger["status"] == "allocated").sum()
        _add(rows, "tokens_total", "ok", str(total))
        _add(rows, "tokens_available", "ok", str(int(available)))
        _add(rows, "tokens_allocated", "ok", str(int(allocated)))
        if "source" not in token_ledger.columns:
            _add(rows, "tokens_stock_receipt_missing_order_key", "warn", "missing_col", "source")
        else:
            stock_receipt = token_ledger[token_ledger["source"].astype(str).str.strip() == "stock_receipt"].copy()
            if stock_receipt.empty:
                _add(rows, "tokens_stock_receipt_missing_order_key", "ok", "0", "no_stock_receipt_rows")
            elif "source_order_key" not in token_ledger.columns:
                _add(rows, "tokens_stock_receipt_missing_order_key", "warn", "missing_col", "source_order_key")
            else:
                blank_order_key = int(stock_receipt["source_order_key"].astype(str).str.strip().eq("").sum())
                _add(
                    rows,
                    "tokens_stock_receipt_missing_order_key",
                    "warn" if blank_order_key > 0 else "ok",
                    str(blank_order_key),
                    f"stock_receipt_rows={len(stock_receipt)}",
                )
    else:
        _add(rows, "tokens_total", "fail", "0")

    # Token COGS ledger
    _add(rows, "token_cogs_rows", "ok" if len(token_cogs) > 0 else "warn", str(len(token_cogs)))

    # Inventory
    _add(rows, "inventory_rows", "ok" if len(inventory) > 0 else "warn", str(len(inventory)))
    inventory_gap_stats = _a_inventory_stale_token_gap_stats(
        inventory,
        token_ledger,
        scope_skus=_inventory_scope_skus(),
        now_utc=now_utc_dt,
    )
    inventory_gap_status = str(inventory_gap_stats.get("status", "warn")).strip().lower() or "warn"
    inventory_gap_reason = str(inventory_gap_stats.get("reason", "")).strip()
    inventory_gap_notes = (
        f"stale_hours={inventory_gap_stats.get('row_stale_hours', '')};"
        f"scope_rows={inventory_gap_stats.get('scope_rows', 0)};"
        f"stale_scope_rows={inventory_gap_stats.get('stale_scope_rows', 0)};"
        f"available_gap_rows={inventory_gap_stats.get('unresolved_available_gap_rows', 0)};"
        f"total_gap_rows={inventory_gap_stats.get('unresolved_total_gap_rows', 0)};"
        f"stale_scope_sample={','.join([str(v) for v in inventory_gap_stats.get('stale_scope_sample', [])])};"
        f"unresolved_sample={';'.join([str(v) for v in inventory_gap_stats.get('unresolved_sample', [])])}"
    )
    if inventory_gap_reason:
        inventory_gap_notes = f"reason={inventory_gap_reason};" + inventory_gap_notes
    _add(
        rows,
        "a_inventory_stale_token_gap",
        inventory_gap_status,
        str(inventory_gap_stats.get("unresolved_gap_rows", "n/a")),
        inventory_gap_notes,
    )

    # Token shortages (per SKU)
    shortage_path = OUT / "token_shortages_by_sku.csv"
    if shortage_path.exists():
        try:
            shortages = pd.read_csv(shortage_path, dtype=str)
            count = len(shortages)
            notes = ""
            if count > 0 and "shortage_class" in shortages.columns:
                classes = (
                    shortages["shortage_class"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .replace("", "unclassified")
                    .value_counts()
                    .sort_index()
                )
                notes = "classes=" + ",".join([f"{name}:{int(value)}" for name, value in classes.items()])
            _add(rows, "token_shortages_by_sku", "fail" if count > 0 else "ok", str(count), notes)
        except Exception as exc:
            _add(rows, "token_shortages_by_sku", "fail", "read_error", str(exc))
    else:
        _add(rows, "token_shortages_by_sku", "warn", "missing", f"path {shortage_path}")

    canceled_alloc_stats = _token_allocated_on_canceled_orders_stats(
        token_allocations,
        orders_all_status,
        order_master,
    )
    DETAIL_ALLOCATED_TOKENS_ON_CANCELED_ORDERS.parent.mkdir(parents=True, exist_ok=True)
    canceled_details = canceled_alloc_stats.get("details", pd.DataFrame())
    if isinstance(canceled_details, pd.DataFrame):
        if canceled_details.empty:
            pd.DataFrame(
                columns=["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"]
            ).to_csv(DETAIL_ALLOCATED_TOKENS_ON_CANCELED_ORDERS, index=False)
        else:
            canceled_details.to_csv(DETAIL_ALLOCATED_TOKENS_ON_CANCELED_ORDERS, index=False)
    else:
        pd.DataFrame(
            columns=["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"]
        ).to_csv(DETAIL_ALLOCATED_TOKENS_ON_CANCELED_ORDERS, index=False)
    if not bool(canceled_alloc_stats.get("ready", False)):
        _add(
            rows,
            "token_allocated_on_canceled_orders",
            "warn",
            "n/a",
            str(canceled_alloc_stats.get("notes", "unavailable")),
        )
    else:
        canceled_rows = int(canceled_alloc_stats.get("rows", 0))
        canceled_units = int(canceled_alloc_stats.get("units", 0))
        sample = canceled_alloc_stats.get("sample", [])
        sample_text = ""
        if isinstance(sample, list) and sample:
            sample_text = f";sample={';'.join([str(x) for x in sample[:3]])}"
        _add(
            rows,
            "token_allocated_on_canceled_orders",
            "fail" if canceled_units > 0 else "ok",
            str(canceled_rows),
            f"units={canceled_units}{sample_text}",
        )

    # Recent log health
    log_path = _first_existing_path(B_CYCLE_LOG_PATH_CANDIDATES)
    if log_path is None:
        _add(rows, "b_cycle_log_exists", "fail", "no", f"searched={','.join([str(p) for p in B_CYCLE_LOG_PATH_CANDIDATES])}")
    else:
        log_info = _file_info(log_path)
        _add(
            rows,
            "b_cycle_log_exists",
            "ok" if log_info["exists"] == "yes" else "fail",
            log_info["exists"],
            f"mtime {log_info['mtime_utc']}; path={log_path}",
        )
        window_hours = float(os.environ.get("B_CYCLE_FAIL_LOG_HOURS", "2"))
        fail_stats = _b_cycle_recent_fail_stats(log_path, window_hours=window_hours)
        latest_cycle = str(fail_stats.get("latest_cycle", "") or "").strip()
        unresolved_count = int(fail_stats.get("unresolved_count", 0))
        raw_fail_count = int(fail_stats.get("raw_fail_count", 0))
        recovered_count = int(fail_stats.get("recovered_count", 0))
        ignored_non_actionable = int(fail_stats.get("ignored_non_actionable", 0))
        maintenance_context = int(fail_stats.get("maintenance_context", 0))
        maintenance_markers_active = str(fail_stats.get("maintenance_markers_active", "")).strip()
        maintenance_marker_lines = int(fail_stats.get("maintenance_marker_lines", 0))
        unresolved_sample = fail_stats.get("unresolved_sample", [])
        sample_text = ""
        if isinstance(unresolved_sample, list) and unresolved_sample:
            sample_text = f"; unresolved_sample={';'.join([str(x) for x in unresolved_sample[:3]])}"
        _add(
            rows,
            "b_cycle_recent_fail_lines",
            "warn" if unresolved_count > 0 else "ok",
            str(unresolved_count),
            (
                f"latest_cycle={latest_cycle}; raw_fail_count={raw_fail_count}; "
                f"recovered_count={recovered_count}; unresolved_count={unresolved_count}; "
                f"ignored_non_actionable={ignored_non_actionable}; "
                f"maintenance_context={maintenance_context}; "
                f"maintenance_marker_lines={maintenance_marker_lines}; "
                f"maintenance_markers_active={maintenance_markers_active}; "
                f"path={log_path}{sample_text}"
            ),
        )
    try:
        if not B_LISTING_COLLECTION_STATUS_PATH.exists():
            _add(rows, "b_listing_offer_collection", "warn", "missing", f"path={B_LISTING_COLLECTION_STATUS_PATH}")
        else:
            try:
                payload = json.loads(B_LISTING_COLLECTION_STATUS_PATH.read_text(encoding="utf-8"))
                status_text = str(payload.get("status", "")).strip().lower()
                rc_raw = payload.get("rc", "")
                try:
                    rc_int = int(float(str(rc_raw).strip()))
                except Exception:
                    rc_int = -1
                stamp = str(payload.get("timestamp_utc", "")).strip()
                notes = str(payload.get("notes", "")).strip()
                warn_statuses = {"warn", "fail", "error"}
                # B cycle intentionally treats SystemExit(130) as nonfatal boundary interruption.
                # Do not keep B health blocked when the collector reports this known nonfatal exit.
                nonfatal_130 = rc_int == 130 and "system_exit_nonfatal" in notes.lower()
                active_maintenance_markers = _b_maintenance_marker_paths_present()
                maintenance_context = bool(active_maintenance_markers)
                if not maintenance_context and isinstance(log_path, Path) and log_path.exists():
                    maintenance_context = bool(_b_cycle_latest_cycle_context(log_path).get("maintenance_context", False))
                nonfatal_maintenance = rc_int == 125 and maintenance_context
                is_warn = (
                    status_text in warn_statuses or (rc_int not in {0} and rc_int != -1)
                ) and not (nonfatal_130 or nonfatal_maintenance)
                notes_out = notes
                if nonfatal_130:
                    notes_out = f"{notes_out};classified_nonfatal_130=1"
                if nonfatal_maintenance:
                    marker_text = ",".join([path.name for path in active_maintenance_markers])
                    suffix = "classified_nonfatal_maintenance=1"
                    if marker_text:
                        suffix += f";maintenance_markers={marker_text}"
                    notes_out = f"{notes_out};{suffix}" if notes_out else suffix
                _add(
                    rows,
                    "b_listing_offer_collection",
                    "warn" if is_warn else "ok",
                    str(rc_int),
                    f"status={status_text};timestamp_utc={stamp};notes={notes_out}",
                )
            except Exception as exc:
                _add(rows, "b_listing_offer_collection", "warn", "read_error", str(exc))

        if not B_SHEET_SYNC_STATUS_PATH.exists():
            _add(rows, "b_sheet_sync_external_health", "warn", "missing", f"path={B_SHEET_SYNC_STATUS_PATH}")
            _add(rows, "b_token_source_single_truth", "fail", "missing", f"path={B_SHEET_SYNC_STATUS_PATH}")
        else:
            sync = pd.read_csv(B_SHEET_SYNC_STATUS_PATH, dtype=str).fillna("")
            required = {"timestamp_utc", "step", "status", "severity"}
            if sync.empty or not required.issubset(set(sync.columns)):
                _add(rows, "b_sheet_sync_external_health", "warn", "invalid", f"path={B_SHEET_SYNC_STATUS_PATH}")
                _add(rows, "b_token_source_single_truth", "fail", "invalid", f"path={B_SHEET_SYNC_STATUS_PATH}")
            else:
                ts = _to_dt(sync["timestamp_utc"])
                window_hours = float(os.environ.get("B_SHEET_SYNC_WARN_HOURS", "6"))
                cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
                recent = sync.loc[ts.notna() & (ts >= cutoff)].copy()
                degraded = recent[
                    recent["status"].astype(str).str.strip().str.lower().isin({"degraded_local", "hard_fail"})
                ]
                latest = sync.iloc[-1]
                _add(
                    rows,
                    "b_sheet_sync_external_health",
                    "warn" if not degraded.empty else "ok",
                    str(len(degraded.index)),
                    (
                        f"window_hours={window_hours};path={B_SHEET_SYNC_STATUS_PATH};"
                        f"latest_step={latest.get('step', '')};latest_status={latest.get('status', '')};"
                        f"latest_severity={latest.get('severity', '')}"
                    ),
                )
                target_steps = {"B030_sync_token_allocations_from_sheet", "B007_allocate_tokens_live"}
                step_col = sync.get("step", pd.Series(dtype=str)).astype(str).str.strip()
                target = sync.loc[step_col.isin(target_steps)].copy()
                latest_rows = []
                for step_name in sorted(target_steps):
                    step_rows = target.loc[target["step"].astype(str).str.strip() == step_name]
                    if not step_rows.empty:
                        latest_rows.append(step_rows.iloc[-1])
                unsafe_count = 0
                latest_mode_notes = []
                for row_latest in latest_rows:
                    mode_val = str(row_latest.get("mode", "")).strip().lower()
                    status_val = str(row_latest.get("status", "")).strip().lower()
                    step_val = str(row_latest.get("step", "")).strip()
                    latest_mode_notes.append(f"{step_val}:{mode_val}:{status_val}")
                    if mode_val in {"local_fallback", "sheet_sync_skipped_local_newer"} or status_val in {
                        "degraded_local",
                        "hard_fail",
                    }:
                        unsafe_count += 1
                _add(
                    rows,
                    "b_token_source_single_truth",
                    "fail" if unsafe_count > 0 else "ok",
                    str(unsafe_count),
                    (
                        f"window_hours={window_hours};path={B_SHEET_SYNC_STATUS_PATH};"
                        "unsafe_mode=local_fallback|sheet_sync_skipped_local_newer;"
                        "unsafe_status=degraded_local|hard_fail;"
                        f"latest_step_modes={','.join(latest_mode_notes)}"
                    ),
                )
    except Exception as exc:
        _add(rows, "b_sheet_sync_external_health", "warn", "read_error", str(exc))
        _add(rows, "b_token_source_single_truth", "fail", "read_error", str(exc))

    fees_failed_stats = _fees_failed_rows_today(FEES_FAILED_PATH, now_utc_dt)
    fees_failed_notes = str(fees_failed_stats.get("notes", "") or "")
    sample_skus = fees_failed_stats.get("sample_skus", [])
    if isinstance(sample_skus, list) and sample_skus:
        fees_failed_notes = f"{fees_failed_notes};sample_skus={','.join([str(x) for x in sample_skus[:5]])}"
    if bool(fees_failed_stats.get("read_error", False)):
        _add(rows, "a_fees_failed_rows_today", "warn", "read_error", fees_failed_notes)
    else:
        unresolved_today = int(fees_failed_stats.get("count", 0))
        _add(
            rows,
            "a_fees_failed_rows_today",
            "warn" if unresolved_today > 0 else "ok",
            str(unresolved_today),
            fees_failed_notes,
        )
    receipt_health = _a_stock_receipts_step_health(now_utc_dt)
    _add(
        rows,
        "a_stock_receipts_collection_health",
        str(receipt_health.get("status", "warn")),
        str(receipt_health.get("value", "unknown")),
        str(receipt_health.get("notes", "")),
    )

    _schema_check(
        rows,
        "b_schema_orders_missing_items_window",
        DETAIL_ORDERS_MISSING_ITEMS,
        ["amazon_order_id", "purchase_date"],
        optional=False,
    )
    _schema_check(
        rows,
        "b_schema_allocated_tokens_on_canceled_orders",
        DETAIL_ALLOCATED_TOKENS_ON_CANCELED_ORDERS,
        ["order_id", "seller_sku", "quantity", "token_id", "allocation_date", "order_status"],
        optional=False,
    )
    # Ensure the unknown-fee-country detail file exists (empty is OK).
    if not DETAIL_UNKNOWN_FEE_COUNTRIES.exists():
        DETAIL_UNKNOWN_FEE_COUNTRIES.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["ship_country_code", "count"]).to_csv(
            DETAIL_UNKNOWN_FEE_COUNTRIES, index=False
        )
    _schema_check(
        rows,
        "b_schema_unknown_fee_countries",
        DETAIL_UNKNOWN_FEE_COUNTRIES,
        ["ship_country_code", "count"],
        optional=True,
    )

    # Unknown fee VAT rules (new country codes)
    try:
        known = set()
        if FEE_RULES_PATH.exists():
            rules_df = pd.read_csv(FEE_RULES_PATH, dtype=str).fillna("")
            if "country_code" in rules_df.columns:
                known = set(rules_df["country_code"].astype(str).str.strip().str.upper())
        orders = pd.read_csv(OUT / "orders_all.csv", dtype=str).fillna("")
        cc = orders.get("ship_country_code", pd.Series([], dtype=str)).astype(str).str.strip().str.upper()
        cc = cc[cc != ""]
        # Only alert on unknown countries that have recent orders (last 30 days from latest order date).
        recent_unknown = []
        try:
            if "purchase_date" in orders.columns:
                orders = orders.copy()
                orders["purchase_date_dt"] = _to_dt(orders["purchase_date"])
                max_dt = orders["purchase_date_dt"].max()
                if pd.notna(max_dt):
                    window_start = max_dt - pd.Timedelta(days=30)
                    recent = orders[orders["purchase_date_dt"].notna() & (orders["purchase_date_dt"] >= window_start)]
                else:
                    recent = orders.iloc[0:0]
            else:
                recent = orders
            recent_cc = recent.get("ship_country_code", pd.Series([], dtype=str)).astype(str).str.strip().str.upper()
            recent_cc = recent_cc[recent_cc != ""]
            recent_unknown = sorted([c for c in recent_cc.unique().tolist() if c not in known])
        except Exception:
            recent_unknown = sorted([c for c in cc.unique().tolist() if c not in known])
        if recent_unknown:
            counts = (
                orders[orders["ship_country_code"].astype(str).str.strip().str.upper().isin(recent_unknown)]
                .groupby("ship_country_code")
                .size()
                .reset_index(name="count")
            )
            DETAIL_UNKNOWN_FEE_COUNTRIES.parent.mkdir(parents=True, exist_ok=True)
            counts.to_csv(DETAIL_UNKNOWN_FEE_COUNTRIES, index=False)
            _add(
                rows,
                "fee_rules_unknown_countries",
                "warn",
                str(len(recent_unknown)),
                ",".join(recent_unknown[:10]),
            )
        else:
            # Always write a stub file so the schema check does not warn.
            DETAIL_UNKNOWN_FEE_COUNTRIES.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=["ship_country_code", "count"]).to_csv(
                DETAIL_UNKNOWN_FEE_COUNTRIES, index=False
            )
            _add(rows, "fee_rules_unknown_countries", "ok", "0")
    except Exception as exc:
        _add(rows, "fee_rules_unknown_countries", "warn", "error", str(exc))

    # C cycle schema checks (phase 1)
    _schema_check(
        rows,
        "c_schema_financial_events_shipments",
        OUT / "financial_events_shipments.csv",
        ["shipment_id", "inbound_shipment_id", "parsed_fba_shipment_id"],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_financial_events_inbound_summary",
        OUT / "financial_events_inbound_summary.csv",
        ["date", "amount_type", "total_amount"],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_inventory_ledger_raw",
        OUT / "inventory_ledger_raw.csv",
        ["Reference ID", "MSKU", "Event Type", "Quantity"],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_purchase_source",
        Path("reference/Amazon Supplier Process - Orders (3).csv"),
        ["SKU", "Cost PU", "Order Date", "Sent to FBA"],
        optional=False,
    )
    _schema_check(
        rows,
        "b_schema_l3_orphans",
        OUT / "l3_orphans.csv",
        ["Order ID", "SKU"],
        optional=False,
    )
    _schema_check(
        rows,
        "b_schema_token_allocation_skipped",
        OUT / "token_allocation_skipped.csv",
        ["Order ID", "SKU", "Date", "Quantity Ordered", "reason"],
        optional=False,
    )
    _schema_check(
        rows,
        "b_schema_orphan_recovery_alerts",
        OUT / "orphan_recovery_alerts.csv",
        ["timestamp", "orphan_count", "window_start", "window_end", "action"],
        optional=True,
    )
    _schema_check(
        rows,
        "b_schema_orphan_order_items_recovered",
        OUT / "orphan_order_items_recovered.csv",
        ["AmazonOrderId"],
        optional=True,
    )
    _schema_check(
        rows,
        "b_schema_orphan_order_items_failed",
        OUT / "orphan_order_items_failed.csv",
        ["order_id", "error"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_merchant_listings",
        OUT / "merchant_listings_latest.csv",
        ["seller-sku", "asin1", "product-id"],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_storage_fee_monthly",
        OUT / "fba_storage_fee_charges_monthly.csv",
        ["asin", "estimated_monthly_storage_fee"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_long_term_storage_fee_monthly",
        OUT / "fba_long_term_storage_fee_charges_monthly.csv",
        ["asin"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_delivery_status",
        OUT / "inbound_delivery_status.csv",
        ["inbound_shipment_id", "expected_qty", "received_qty", "pct_received"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_missing_units",
        OUT / "inbound_missing_units.csv",
        ["inbound_shipment_id", "sku", "missing_qty"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_cost_events",
        OUT / "inbound_cost_events.csv",
        ["shipment_id", "inbound_shipment_id", "parsed_fba_shipment_id", "amount", "currency"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_allocated",
        OUT / "inbound_costs_allocated.csv",
        ["shipment_id", "currency", "event_count", "total_amount", "total_tax", "total_with_tax"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_unallocated",
        OUT / "inbound_costs_unallocated.csv",
        ["shipment_key", "amount", "currency"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_allocated_sku",
        OUT / "inbound_costs_allocated_sku.csv",
        ["shipment_id", "sku", "allocated_total"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_unallocated_sku",
        OUT / "inbound_costs_unallocated_sku.csv",
        ["shipment_id", "unallocated_reason"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_allocation_summary",
        OUT / "inbound_costs_allocation_summary.csv",
        ["shipment_id", "currency", "allocated_total"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_vat_country_model",
        VAT_MODEL,
        [
            "country_code",
            "marketplace_id",
            "currency",
            "sample_orders",
            "taxable_orders",
            "pct_taxable",
            "avg_vat_rate",
            "last_order_date",
            "built_at",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_fee_country_model",
        FEE_MODEL,
        [
            "country_code",
            "marketplace_id",
            "currency",
            "sample_orders",
            "fba_avg_ex_per_unit",
            "fba_taxable_pct",
            "fba_vat_rate",
            "commission_pct_avg",
            "commission_taxable_pct",
            "commission_vat_rate",
            "dsf_pct",
            "dsf_vat_rate",
            "last_order_date",
            "built_at",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_token_maturity_window",
        OUT / "token_maturity_window.csv",
        ["inbound_shipment_id", "expected_qty", "received_qty", "in_flight_qty", "is_mature"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_token_maturity_window_sku",
        OUT / "token_maturity_window_sku.csv",
        ["inbound_shipment_id", "sku", "expected_qty"],
        optional=True,
    )
    # E cycle schema checks (optional until E is running daily)
    _schema_check(
        rows,
        "e_schema_sales_velocity",
        OUT / "sku_sales_velocity.csv",
        ["sku", "window_days", "units_sold", "velocity_units_per_day"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_roi_snapshot",
        OUT / "sku_roi_snapshot.csv",
        ["sku", "window_days", "units_sold", "roi_exvat"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_roi_snapshot_uk",
        OUT / "sku_roi_snapshot_uk.csv",
        ["sku", "window_days", "units_sold", "roi_exvat"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_roi_snapshot_non_uk",
        OUT / "sku_roi_snapshot_non_uk.csv",
        ["sku", "window_days", "units_sold", "roi_exvat"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_roi_snapshot_by_country",
        OUT / "sku_roi_snapshot_by_country.csv",
        ["sku", "country_code", "window_days", "units_sold", "roi_exvat"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_restock_signals",
        OUT / "sku_restock_signals.csv",
        ["sku", "velocity_30d", "days_of_stock_left", "reorder_flag"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_performance_summary",
        OUT / "sku_performance_summary.csv",
        [
            "sku",
            "profit_per_unit_gbp_30d",
            "value_velocity_gbp_per_day",
            "current_token_cost_gbp",
            "break_even_price_gbp",
            "expected_refund_cost_per_unit_gbp",
            "roi_at_our_price_pct",
            "roi_at_buy_box_price_pct",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_study_report",
        OUT / "e_study_report.csv",
        [
            "study_rank",
            "sku",
            "reorder_flag",
            "value_velocity_gbp_per_day",
            "asof_date",
            "units_sold_truth_30d",
            "units_sold_velocity_30d",
            "units_sold_source",
            "latest_daily_truth_date",
            "latest_daily_truth_state",
            "latest_daily_truth_units",
            "latest_daily_truth_profit_gbp",
        ],
        optional=True,
    )
    e_run_log_path = _first_existing_path(E_RUN_LOG_PATH_CANDIDATES) or E_RUN_LOG_JSONL
    _schema_check_jsonl(
        rows,
        "e_schema_run_log",
        e_run_log_path,
        [
            "run_id",
            "started_utc",
            "finished_utc",
            "status",
            "tasks_run",
            "elapsed_seconds",
            "expected_input_asof",
            "output_asof",
            "asof_rerun_trigger",
            "error",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_decision_log",
        OUT / "e_decision_log.csv",
        [
            "run_id",
            "sku",
            "decision_type",
            "decision_value",
            "reason_code",
            "note",
            "profit_per_unit_gbp_30d",
            "value_velocity_gbp_per_day",
            "created_utc",
            "source",
            "asof_date",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_sales_truth_sku_30d",
        OUT / "sales_truth_sku_30d_latest.csv",
        ["sku", "window_days", "asof_date", "units_b_source", "revenue_b_source_gbp", "profit_b_source_gbp"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_sales_truth_reconciliation",
        OUT / "sales_truth_reconciliation_latest.csv",
        [
            "sku",
            "window_days",
            "asof_date",
            "units_b_source",
            "revenue_b_source_gbp",
            "profit_b_source_gbp",
            "units_e_output",
            "revenue_e_output_gbp",
            "profit_e_output_gbp",
            "revenue_delta_gbp",
            "profit_delta_gbp",
            "confidence_status",
            "root_cause_hint",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_sku_daily_sales_truth",
        OUT / "sku_daily_sales_truth_latest.csv",
        [
            "sku",
            "date",
            "source_state",
            "units",
            "revenue_gbp",
            "profit_gbp",
            "fees_gbp",
            "cogs_gbp",
            "confidence_status",
            "notes",
        ],
        optional=True,
    )
    roi_truth_stats = _e_sales_truth_roi_integrity_stats(OUT / "sku_roi_snapshot.csv")
    if not bool(roi_truth_stats.get("ready", False)):
        missing_status = str(roi_truth_stats.get("status", "warn") or "warn")
        missing_reason = str(roi_truth_stats.get("reason", "n/a") or "n/a")
        missing_notes = str(roi_truth_stats.get("notes", "") or "")
        _add(rows, "e_sales_truth_selling_rows_revenue_zero", missing_status, missing_reason, missing_notes)
        _add(rows, "e_sales_truth_zero_profit_with_revenue", missing_status, missing_reason, missing_notes)
        _add(rows, "e_sales_truth_missing_cogs_equals_units", missing_status, missing_reason, missing_notes)
    else:
        roi_notes = str(roi_truth_stats.get("notes", "") or "")
        zero_revenue_rows = _safe_int(roi_truth_stats.get("zero_revenue_rows", 0))
        zero_profit_with_revenue_rows = _safe_int(roi_truth_stats.get("zero_profit_with_revenue_rows", 0))
        missing_cogs_equals_units_rows = _safe_int(roi_truth_stats.get("missing_cogs_equals_units_rows", 0))
        _add(
            rows,
            "e_sales_truth_selling_rows_revenue_zero",
            "fail" if zero_revenue_rows > 0 else "ok",
            str(zero_revenue_rows),
            roi_notes,
        )
        _add(
            rows,
            "e_sales_truth_zero_profit_with_revenue",
            "fail" if zero_profit_with_revenue_rows > 0 else "ok",
            str(zero_profit_with_revenue_rows),
            roi_notes,
        )
        _add(
            rows,
            "e_sales_truth_missing_cogs_equals_units",
            "fail" if missing_cogs_equals_units_rows > 0 else "ok",
            str(missing_cogs_equals_units_rows),
            roi_notes,
        )
    recon_stats = _e_sales_truth_reconciliation_stats(OUT / "sales_truth_reconciliation_latest.csv")
    if not bool(recon_stats.get("ready", False)):
        _add(
            rows,
            "e_sales_truth_reconciliation_mismatch_rows",
            str(recon_stats.get("status", "warn") or "warn"),
            str(recon_stats.get("reason", "n/a") or "n/a"),
            str(recon_stats.get("notes", "") or ""),
        )
    else:
        _add(
            rows,
            "e_sales_truth_reconciliation_mismatch_rows",
            str(recon_stats.get("status", "warn") or "warn"),
            str(_safe_int(recon_stats.get("mismatch_rows", 0))),
            str(recon_stats.get("notes", "") or ""),
        )
    perf_units_stats = _e_performance_units_alignment_stats(OUT / "sku_performance_summary.csv")
    if not bool(perf_units_stats.get("ready", False)):
        _add(
            rows,
            "e_sales_truth_performance_units_align_roi",
            str(perf_units_stats.get("status", "warn") or "warn"),
            str(perf_units_stats.get("reason", "n/a") or "n/a"),
            str(perf_units_stats.get("notes", "") or ""),
        )
    else:
        _add(
            rows,
            "e_sales_truth_performance_units_align_roi",
            str(perf_units_stats.get("status", "warn") or "warn"),
            str(_safe_int(perf_units_stats.get("mismatch_rows", 0))),
            str(perf_units_stats.get("notes", "") or ""),
        )
    daily_truth_stats = _e_daily_sales_truth_stats(OUT / "sku_daily_sales_truth_latest.csv")
    if not bool(daily_truth_stats.get("ready", False)):
        _add(
            rows,
            "e_sales_truth_daily_state_explicit",
            str(daily_truth_stats.get("status", "warn") or "warn"),
            str(daily_truth_stats.get("reason", "n/a") or "n/a"),
            str(daily_truth_stats.get("notes", "") or ""),
        )
        _add(
            rows,
            "e_sales_truth_daily_confidence_state_alignment",
            str(daily_truth_stats.get("status", "warn") or "warn"),
            str(daily_truth_stats.get("reason", "n/a") or "n/a"),
            str(daily_truth_stats.get("notes", "") or ""),
        )
    else:
        bad_source_count = _safe_int(daily_truth_stats.get("invalid_source_rows", 0)) + _safe_int(
            daily_truth_stats.get("blank_source_rows", 0)
        )
        bad_conf_count = _safe_int(daily_truth_stats.get("provisional_bad_confidence_rows", 0)) + _safe_int(
            daily_truth_stats.get("finalized_bad_confidence_rows", 0)
        )
        _add(
            rows,
            "e_sales_truth_daily_state_explicit",
            "fail" if bad_source_count > 0 else "ok",
            str(bad_source_count),
            str(daily_truth_stats.get("notes", "") or ""),
        )
        _add(
            rows,
            "e_sales_truth_daily_confidence_state_alignment",
            "fail" if bad_conf_count > 0 else "ok",
            str(bad_conf_count),
            str(daily_truth_stats.get("notes", "") or ""),
        )
    study_fresh_stats = _e_study_report_fresh_vs_summary_stats(OUT / "sku_performance_summary.csv", OUT / "e_study_report.csv")
    if not bool(study_fresh_stats.get("ready", False)):
        _add(
            rows,
            "e_study_report_fresh_vs_summary",
            str(study_fresh_stats.get("status", "warn") or "warn"),
            str(study_fresh_stats.get("reason", "n/a") or "n/a"),
            str(study_fresh_stats.get("notes", "") or ""),
        )
    else:
        _add(
            rows,
            "e_study_report_fresh_vs_summary",
            str(study_fresh_stats.get("status", "warn") or "warn"),
            str(int(float(study_fresh_stats.get("lag_seconds", 0) or 0))),
            str(study_fresh_stats.get("notes", "") or ""),
        )
    study_align_stats = _e_study_report_truth_alignment_stats(OUT / "sku_performance_summary.csv", OUT / "e_study_report.csv")
    if not bool(study_align_stats.get("ready", False)):
        _add(
            rows,
            "e_study_report_truth_alignment",
            str(study_align_stats.get("status", "warn") or "warn"),
            str(study_align_stats.get("reason", "n/a") or "n/a"),
            str(study_align_stats.get("notes", "") or ""),
        )
    else:
        _add(
            rows,
            "e_study_report_truth_alignment",
            str(study_align_stats.get("status", "warn") or "warn"),
            str(_safe_int(study_align_stats.get("mismatch_rows", 0))),
            str(study_align_stats.get("notes", "") or ""),
        )
    _o_net_fee_bridge_check(rows)
    today_utc = datetime.now(timezone.utc).date().isoformat()
    input_asof = {
        "listing_offer_history": _today_listing_offer_snapshot_asof(today_utc),
        "inventory_history": _max_asof_date(INVENTORY_HISTORY),
        "inbound_history": _max_asof_date(INBOUND_HISTORY),
        "refund_adjustment_history": _max_asof_date(REFUND_ADJUSTMENT_HISTORY),
    }
    h_paused = _h_cycle_pause_requested()
    paused_relaxed_inputs = {"inventory_history", "inbound_history"} if h_paused else set()
    required_input_asof = {
        name: val for name, val in input_asof.items() if name not in paused_relaxed_inputs
    }
    missing_input_asof = [name for name, val in required_input_asof.items() if not val]
    missing_relaxed_asof = [name for name in paused_relaxed_inputs if not input_asof.get(name)]
    missing_all_asof = missing_input_asof + sorted(missing_relaxed_asof)
    if missing_input_asof:
        _add(rows, "h_e_inputs_fresh", "warn", "missing_asof", ",".join(missing_all_asof))
        expected_input_asof = ""
    else:
        compare_inputs = required_input_asof if required_input_asof else input_asof
        unique_input_dates = sorted(set(compare_inputs.values()))
        expected_input_asof = min(unique_input_dates)
        if len(unique_input_dates) > 1:
            _add(
                rows,
                "h_e_inputs_fresh",
                "warn",
                str(len(unique_input_dates)),
                "; ".join([f"{k}={v}" for k, v in compare_inputs.items()]),
            )
        else:
            try:
                expected_dt = datetime.fromisoformat(expected_input_asof).replace(tzinfo=timezone.utc)
                now_day = datetime.now(timezone.utc).date()
                age_days = (now_day - expected_dt.date()).days
                max_age_days = int(float(os.environ.get("E_INPUT_MAX_AGE_DAYS", "1")))
                freshness_status = "ok" if age_days <= max_age_days else "warn"
                pause_note = "; h_cycle_pause_requested=1" if h_paused else ""
                _add(
                    rows,
                    "h_e_inputs_fresh",
                    freshness_status,
                    str(age_days),
                    f"asof_date={expected_input_asof}; max_age_days={max_age_days}{pause_note}",
                )
            except Exception:
                _add(rows, "h_e_inputs_fresh", "warn", "bad_date", f"asof_date={expected_input_asof}")

    expected_output_asof = expected_input_asof
    allowed_output_asof = {expected_input_asof} if expected_input_asof else set()
    output_max_age_days = max(int(float(os.environ.get("E_OUTPUT_MAX_AGE_DAYS", "1") or "1")), 0)
    if expected_input_asof:
        try:
            expected_out_dt = datetime.fromisoformat(expected_input_asof).replace(tzinfo=timezone.utc)
            for lag_day in range(1, output_max_age_days + 1):
                allowed_output_asof.add((expected_out_dt.date() - timedelta(days=lag_day)).isoformat())
        except Exception:
            pass
    if h_paused:
        all_input_dates = [str(v).strip() for v in input_asof.values() if str(v).strip()]
        if len(all_input_dates) == len(input_asof):
            expected_output_asof = min(all_input_dates)
            allowed_output_asof.add(expected_output_asof)

    if not allowed_output_asof:
        _add(rows, "h_e_outputs_latest_asof", "warn", "n/a", "missing expected input asof_date")
    else:
        latest_success = _latest_successful_e_run(e_run_log_path)
        if not latest_success:
            _add(
                rows,
                "h_e_outputs_latest_asof",
                "warn",
                "missing_success",
                f"run_log_path={e_run_log_path}; reason=no_success_rows",
            )
        else:
            chosen_run_id = str(latest_success.get("run_id", "")).strip()
            chosen_output_asof = str(latest_success.get("output_asof", "")).strip()
            allowed_any = set(allowed_output_asof)
            allowed_any.add(today_utc)
            ok_match = bool(chosen_output_asof) and chosen_output_asof in allowed_any
            pause_note = "; h_cycle_pause_requested=1" if h_paused else ""
            note_base = (
                f"run_log_path={e_run_log_path}; chosen_run_id={chosen_run_id or 'missing'}; "
                f"chosen_output_asof={chosen_output_asof or 'missing'}; "
                f"today_utc={today_utc}; expected_any={','.join(sorted(allowed_any))}{pause_note}"
            )
            print(f"[health_check] h_e_outputs_asof_decision {note_base}")
            if ok_match:
                _add(
                    rows,
                    "h_e_outputs_latest_asof",
                    "ok",
                    "0",
                    note_base,
                )
            else:
                _add(
                    rows,
                    "h_e_outputs_latest_asof",
                    "warn",
                    "1",
                    f"{note_base}; reason=output_asof_not_allowed",
                )

    _schema_check(
        rows,
        "z_schema_health_status",
        HEALTH_STATUS_CSV,
        ["timestamp_utc", "status", "fail_count", "warn_count", "notes"],
        optional=True,
    )
    _schema_check(
        rows,
        "f_schema_training_set",
        TRAINING_SET_PATH,
        ["sku", "asin", "marketplace", "notes", "enabled"],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_lab_cohort",
        LAB_COHORT_PATH,
        ["sku", "lane", "enabled", "effective_utc", "note"],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_head_boundaries",
        HEAD_BOUNDARIES_PATH,
        [
            "sku",
            "lane",
            "enabled",
            "effective_utc",
            "expiry_utc",
            "hard_floor_gbp",
            "ceiling_gbp",
            "max_move_per_cycle_gbp",
            "max_daily_down_move_gbp",
            "cooldown_minutes",
            "max_probes_per_day",
            "max_active_probe_skus",
            "note",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_supervisor_tactical_rules",
        SUPERVISOR_TACTICAL_RULES_PATH,
        [
            "sku",
            "lane",
            "state",
            "trigger_code",
            "allowed_probe_type",
            "target_adjustment_gbp",
            "cooldown_minutes",
            "expiry_minutes",
            "priority",
            "enabled",
            "stop_condition",
            "escalation_action",
            "note",
        ],
        optional=False,
    )
    try:
        cohort = _read_csv(LAB_COHORT_PATH)
        if cohort.empty:
            _add(rows, "h_lab_cohort_active_rows", "fail", "0", "empty cohort file")
        else:
            required = ["sku", "enabled"]
            missing = [c for c in required if c not in cohort.columns]
            if missing:
                _add(rows, "h_lab_cohort_active_rows", "fail", "missing_cols", ",".join(missing))
            else:
                enabled = cohort["enabled"].astype(str).str.strip().str.lower()
                active_count = int(enabled.isin({"1", "true", "yes", "y"}).sum())
                _add(
                    rows,
                    "h_lab_cohort_active_rows",
                    "ok" if active_count > 0 else "fail",
                    str(active_count),
                    "expected_at_least=1",
                )
    except Exception as exc:
        _add(rows, "h_lab_cohort_active_rows", "fail", "read_error", str(exc))
    try:
        boundaries = _read_csv(HEAD_BOUNDARIES_PATH)
        if boundaries.empty:
            _add(rows, "h_head_boundaries_active_rows", "fail", "0", "empty head boundary file")
            _add(rows, "h_head_boundary_pilot_present", "fail", "0", f"missing_active_sku={OFFICIAL_PILOT_SKU}")
            _add(rows, "h_head_boundaries_numeric_valid", "fail", "0", "no rows to validate")
        else:
            required = [
                "sku",
                "enabled",
                "hard_floor_gbp",
                "ceiling_gbp",
                "max_move_per_cycle_gbp",
                "max_daily_down_move_gbp",
                "cooldown_minutes",
                "max_probes_per_day",
                "max_active_probe_skus",
            ]
            missing = [c for c in required if c not in boundaries.columns]
            if missing:
                _add(rows, "h_head_boundaries_active_rows", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_head_boundary_pilot_present", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_head_boundaries_numeric_valid", "fail", "missing_cols", ",".join(missing))
            else:
                enabled = boundaries["enabled"].astype(str).str.strip().str.lower()
                active = boundaries[enabled.isin({"1", "true", "yes", "y"})].copy()
                active_count = int(len(active.index))
                _add(
                    rows,
                    "h_head_boundaries_active_rows",
                    "ok" if active_count > 0 else "fail",
                    str(active_count),
                    "expected_at_least=1",
                )

                active_skus = active["sku"].astype(str).str.strip().str.upper()
                pilot_present = int(active_skus.eq(OFFICIAL_PILOT_SKU).any())
                _add(
                    rows,
                    "h_head_boundary_pilot_present",
                    "ok" if pilot_present == 1 else "fail",
                    str(pilot_present),
                    f"expected_active_sku={OFFICIAL_PILOT_SKU}",
                )

                if active.empty:
                    _add(rows, "h_head_boundaries_numeric_valid", "fail", "0", "no active rows")
                else:
                    for col in [
                        "hard_floor_gbp",
                        "ceiling_gbp",
                        "max_move_per_cycle_gbp",
                        "max_daily_down_move_gbp",
                        "cooldown_minutes",
                        "max_probes_per_day",
                        "max_active_probe_skus",
                    ]:
                        active[col] = pd.to_numeric(active[col], errors="coerce")
                    invalid = (
                        active["hard_floor_gbp"].isna()
                        | active["ceiling_gbp"].isna()
                        | active["max_move_per_cycle_gbp"].isna()
                        | active["max_daily_down_move_gbp"].isna()
                        | active["cooldown_minutes"].isna()
                        | active["max_probes_per_day"].isna()
                        | active["max_active_probe_skus"].isna()
                        | (active["hard_floor_gbp"] < 0)
                        | (active["ceiling_gbp"] < active["hard_floor_gbp"])
                        | (active["max_move_per_cycle_gbp"] <= 0)
                        | (active["max_daily_down_move_gbp"] < active["max_move_per_cycle_gbp"])
                        | (active["cooldown_minutes"] < 1)
                        | (active["max_probes_per_day"] < 0)
                        | (active["max_active_probe_skus"] < 1)
                    )
                    invalid_count = int(invalid.sum())
                    _add(
                        rows,
                        "h_head_boundaries_numeric_valid",
                        "ok" if invalid_count == 0 else "fail",
                        str(invalid_count),
                        "rules=ceiling>=floor,max_move>0,max_daily_down>=max_move,cooldown>=1,max_probes>=0,max_active_probe_skus>=1",
                    )
    except Exception as exc:
        _add(rows, "h_head_boundaries_active_rows", "fail", "read_error", str(exc))
        _add(rows, "h_head_boundary_pilot_present", "fail", "read_error", str(exc))
        _add(rows, "h_head_boundaries_numeric_valid", "fail", "read_error", str(exc))
    try:
        rules = _read_csv(SUPERVISOR_TACTICAL_RULES_PATH)
        if rules.empty:
            _add(rows, "h_supervisor_tactical_active_rows", "fail", "0", "empty supervisor tactical rules file")
            _add(rows, "h_supervisor_tactical_pilot_coverage", "fail", "0", f"missing_active_sku={OFFICIAL_PILOT_SKU}")
            _add(rows, "h_supervisor_tactical_rules_valid", "fail", "0", "no rows to validate")
        else:
            required = [
                "sku",
                "state",
                "allowed_probe_type",
                "target_adjustment_gbp",
                "cooldown_minutes",
                "expiry_minutes",
                "priority",
                "enabled",
            ]
            missing = [c for c in required if c not in rules.columns]
            if missing:
                _add(rows, "h_supervisor_tactical_active_rows", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_supervisor_tactical_pilot_coverage", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_supervisor_tactical_rules_valid", "fail", "missing_cols", ",".join(missing))
            else:
                enabled = rules["enabled"].astype(str).str.strip().str.lower()
                active = rules[enabled.isin({"1", "true", "yes", "y"})].copy()
                active_count = int(len(active.index))
                _add(
                    rows,
                    "h_supervisor_tactical_active_rows",
                    "ok" if active_count > 0 else "fail",
                    str(active_count),
                    "expected_at_least=1",
                )

                active_skus = active["sku"].astype(str).str.strip().str.upper()
                pilot_present = int(active_skus.eq(OFFICIAL_PILOT_SKU).any())
                _add(
                    rows,
                    "h_supervisor_tactical_pilot_coverage",
                    "ok" if pilot_present == 1 else "fail",
                    str(pilot_present),
                    f"expected_active_sku={OFFICIAL_PILOT_SKU}",
                )

                if active.empty:
                    _add(rows, "h_supervisor_tactical_rules_valid", "fail", "0", "no active rows")
                else:
                    for col in [
                        "target_adjustment_gbp",
                        "cooldown_minutes",
                        "expiry_minutes",
                        "priority",
                    ]:
                        active[col] = pd.to_numeric(active[col], errors="coerce")

                    valid_states = {"unknown", "stable", "follower", "aggressor_candidate"}
                    valid_probe_types = {"lower", "match", "raise", "hold"}

                    state_col = active["state"].astype(str).str.strip().str.lower()
                    probe_col = active["allowed_probe_type"].astype(str).str.strip().str.lower()
                    invalid = (
                        active["target_adjustment_gbp"].isna()
                        | active["cooldown_minutes"].isna()
                        | active["expiry_minutes"].isna()
                        | active["priority"].isna()
                        | (active["target_adjustment_gbp"] < 0)
                        | (active["cooldown_minutes"] < 1)
                        | (active["expiry_minutes"] < 1)
                        | (active["priority"] < 1)
                        | (~state_col.isin(valid_states))
                        | (~probe_col.isin(valid_probe_types))
                    )
                    invalid_count = int(invalid.sum())
                    _add(
                        rows,
                        "h_supervisor_tactical_rules_valid",
                        "ok" if invalid_count == 0 else "fail",
                        str(invalid_count),
                        "rules=state_enum,probe_enum,target_adjustment>=0,cooldown>=1,expiry>=1,priority>=1",
                    )
    except Exception as exc:
        _add(rows, "h_supervisor_tactical_active_rows", "fail", "read_error", str(exc))
        _add(rows, "h_supervisor_tactical_pilot_coverage", "fail", "read_error", str(exc))
        _add(rows, "h_supervisor_tactical_rules_valid", "fail", "read_error", str(exc))
    _schema_check(
        rows,
        "h_schema_worker_probe_event_log",
        PROBE_EVENT_LOG_PATH,
        [
            "probe_event_id",
            "asof_date",
            "event_utc",
            "marketplace",
            "sku",
            "asin",
            "lane",
            "supervisor_state",
            "trigger_code",
            "probe_type",
            "action_price_before_gbp",
            "action_price_target_gbp",
            "hard_floor_gbp",
            "ceiling_gbp",
            "max_move_per_cycle_gbp",
            "cooldown_minutes",
            "expiry_utc",
            "reason_codes",
            "approved_rule_id",
            "source",
            "notes",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_worker_probe_response_log",
        PROBE_RESPONSE_LOG_PATH,
        [
            "probe_event_id",
            "asof_date",
            "response_utc",
            "response_window_minutes",
            "marketplace",
            "sku",
            "asin",
            "competitor_moved_flag",
            "competitor_move_direction",
            "competitor_move_size_gbp",
            "reaction_lag_minutes",
            "buy_box_price_gbp_after",
            "buy_box_channel_after",
            "buy_box_owner_after",
            "our_price_gbp_after",
            "outcome_code",
            "source",
            "notes",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_executioner_action_log",
        H_EXECUTIONER_ACTION_LOG_PATH,
        [
            "run_id",
            "event_utc",
            "sku",
            "marketplace_id",
            "probe_event_id",
            "probe_type",
            "price_before_gbp",
            "price_target_gbp",
            "price_executed_gbp",
            "live_write_attempted",
            "live_write_success",
            "http_status",
            "submission_id",
            "reason_codes",
            "source",
            "notes",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_seller_profiles",
        H_SELLER_PROFILE_PATH,
        [
            "snapshot_file",
            "asof_date",
            "marketplace",
            "sku",
            "seller_id",
            "offers_seen",
            "rank_by_landed_price",
            "best_landed_price_gbp",
            "seller_landed_price_latest_gbp",
            "gap_to_best_landed_gbp",
            "tier",
            "tier_reason",
            "source",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_seller_soi",
        H_SELLER_SOI_PATH,
        [
            "asof_date",
            "marketplace",
            "sku",
            "seller_id",
            "rank_by_landed_price",
            "seller_landed_price_latest_gbp",
            "tier",
            "tier_reason",
            "source",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_ceiling_events",
        H_CEILING_EVENTS_PATH,
        [
            "event_ts_utc",
            "run_id",
            "sku",
            "ceiling_event_id",
            "compliance_ceiling_gbp",
            "eligibility_ceiling_gbp",
            "demand_ceiling_gbp",
            "suppression_ceiling_gbp",
            "true_binding_ceiling_gbp",
            "true_binding_ceiling_type",
            "target_price_gbp",
            "hard_floor_gbp",
            "ceiling_conflict_flag",
            "reason_codes_json",
        ],
        optional=False,
    )
    _required_non_blank_check(
        rows,
        "h_ceiling_events_required_fields_non_blank",
        H_CEILING_EVENTS_PATH,
        [
            "run_id",
            "ceiling_event_id",
            "true_binding_ceiling_gbp",
            "true_binding_ceiling_type",
            "target_price_gbp",
            "hard_floor_gbp",
            "ceiling_conflict_flag",
            "reason_codes_json",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_strategy_outcome_log",
        H_STRATEGY_OUTCOME_LOG_PATH,
        [
            "event_ts_utc",
            "run_id",
            "sku",
            "asin",
            "scenario_type",
            "chosen_tactic",
            "buy_box_state_before",
            "buy_box_state_after",
            "seller_count",
            "lowest_price_1_gbp",
            "lowest_price_2_gbp",
            "lowest_price_3_gbp",
            "our_price_before_gbp",
            "target_price_gbp",
            "price_written_gbp",
            "hold_until_utc",
            "response_window_minutes",
            "retry_budget_remaining",
            "stop_rule_code",
            "writer_outcome",
            "tactic_success_state",
            "reason_codes_json",
            "tactic_case_id",
        ],
        optional=False,
    )
    _required_non_blank_check(
        rows,
        "h_strategy_outcome_log_required_fields_non_blank",
        H_STRATEGY_OUTCOME_LOG_PATH,
        [
            "run_id",
            "scenario_type",
            "chosen_tactic",
            "seller_count",
            "our_price_before_gbp",
            "target_price_gbp",
            "response_window_minutes",
            "retry_budget_remaining",
            "writer_outcome",
            "reason_codes_json",
            "tactic_case_id",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_strategy_outcome_daily",
        H_STRATEGY_OUTCOME_DAILY_PATH,
        [
            "asof_date",
            "scenario_type",
            "chosen_tactic",
            "decision_rows",
            "applied_rows",
            "no_write_rows",
            "resolved_rows",
            "pending_rows",
            "success_rows",
            "failed_rows",
            "expired_rows",
            "aborted_rows",
            "success_rate_pct",
            "failed_rate_pct",
            "sample_min_rows",
            "provisional_sample_flag",
            "avg_seller_count",
            "avg_price_gap_to_lowest_gbp",
            "below_break_even_rows",
            "at_floor_rows",
            "notes",
        ],
        optional=False,
    )
    _required_non_blank_check(
        rows,
        "h_strategy_outcome_daily_required_fields_non_blank",
        H_STRATEGY_OUTCOME_DAILY_PATH,
        [
            "decision_rows",
            "applied_rows",
            "no_write_rows",
            "resolved_rows",
            "pending_rows",
            "success_rows",
            "failed_rows",
            "expired_rows",
            "aborted_rows",
            "success_rate_pct",
            "failed_rate_pct",
            "sample_min_rows",
            "provisional_sample_flag",
            "avg_seller_count",
            "avg_price_gap_to_lowest_gbp",
            "below_break_even_rows",
            "at_floor_rows",
        ],
        optional=False,
    )
    try:
        ceiling_df = _read_csv(H_CEILING_EVENTS_PATH)
        result = _h_ceiling_effective_floor_integrity_result(ceiling_df, path=H_CEILING_EVENTS_PATH)
        _add(
            rows,
            "h_ceiling_effective_floor_integrity",
            result.get("status", "warn"),
            result.get("value", "read_error"),
            result.get("notes", ""),
        )
    except Exception as exc:
        _add(
            rows,
            "h_ceiling_effective_floor_integrity",
            "warn",
            "read_error",
            str(exc),
        )

    try:
        daily_df = _read_csv(H_STRATEGY_OUTCOME_DAILY_PATH)
        if daily_df.empty:
            _add(
                rows,
                "h_strategy_outcome_daily_count_integrity",
                "warn",
                "missing_or_empty",
                f"path={H_STRATEGY_OUTCOME_DAILY_PATH}",
            )
        else:
            invalid_count = 0
            checked_rows = 0
            samples: list[str] = []
            for _, row in daily_df.iterrows():
                checked_rows += 1
                decision_rows = max(_safe_int(row.get("decision_rows", "0")), 0)
                applied_rows = max(_safe_int(row.get("applied_rows", "0")), 0)
                no_write_rows = max(_safe_int(row.get("no_write_rows", "0")), 0)
                resolved_rows = max(_safe_int(row.get("resolved_rows", "0")), 0)
                pending_rows = max(_safe_int(row.get("pending_rows", "0")), 0)
                success_rows = max(_safe_int(row.get("success_rows", "0")), 0)
                failed_rows = max(_safe_int(row.get("failed_rows", "0")), 0)
                expired_rows = max(_safe_int(row.get("expired_rows", "0")), 0)
                aborted_rows = max(_safe_int(row.get("aborted_rows", "0")), 0)
                below_break_even_rows = max(_safe_int(row.get("below_break_even_rows", "0")), 0)
                at_floor_rows = max(_safe_int(row.get("at_floor_rows", "0")), 0)

                row_issues: list[str] = []
                if applied_rows + no_write_rows != decision_rows:
                    row_issues.append("apply_split")
                if resolved_rows + pending_rows != decision_rows:
                    row_issues.append("resolve_split")
                if success_rows + failed_rows + expired_rows + aborted_rows > decision_rows:
                    row_issues.append("terminal_over_decision")
                if at_floor_rows > decision_rows:
                    row_issues.append("at_floor_over_decision")
                if below_break_even_rows > decision_rows:
                    row_issues.append("break_even_over_decision")
                if row_issues:
                    invalid_count += 1
                    if len(samples) < 5:
                        asof = str(row.get("asof_date", "")).strip() or "na"
                        scenario = str(row.get("scenario_type", "")).strip() or "na"
                        tactic = str(row.get("chosen_tactic", "")).strip() or "na"
                        samples.append(f"{asof}|{scenario}|{tactic}|{'+'.join(row_issues)}")

            _add(
                rows,
                "h_strategy_outcome_daily_count_integrity",
                "fail" if invalid_count > 0 else "ok",
                str(invalid_count),
                (
                    f"checked_rows={checked_rows};"
                    + (f"samples={','.join(samples)}" if samples else "samples=none")
                ),
            )
    except Exception as exc:
        _add(
            rows,
            "h_strategy_outcome_daily_count_integrity",
            "warn",
            "read_error",
            str(exc),
        )

    strategy_focus_scenarios = [
        "multi_seller_ladder_cap",
        "single_rival_reset",
        "suppression_reactivation",
    ]
    no_write_failed_threshold = max(
        _safe_int(os.environ.get("H_STRATEGY_NO_WRITE_FAILED_STREAK_WARN", "5")),
        1,
    )
    streak_stats = _strategy_no_write_failed_streaks(H_STRATEGY_OUTCOME_LOG_PATH)
    for scenario in strategy_focus_scenarios:
        scenario_stat = streak_stats.get(scenario, {})
        streak = int(scenario_stat.get("streak", 0) or 0)
        sample_cases = scenario_stat.get("sample_case_ids", [])
        sample_text = ",".join([str(item) for item in sample_cases[:3]]) if isinstance(sample_cases, list) else ""
        _add(
            rows,
            f"h_strategy_no_write_failed_streak_{scenario}",
            "warn" if streak >= no_write_failed_threshold else "ok",
            str(streak),
            f"scenario={scenario};warn_threshold={no_write_failed_threshold};sample_case_ids={sample_text}",
        )

    sample_snapshot = _strategy_sample_size_snapshot(H_STRATEGY_OUTCOME_DAILY_PATH)
    latest_asof = str(sample_snapshot.get("asof_date", "") or "")
    rows_by_scenario = sample_snapshot.get("rows_by_scenario", {})
    if not isinstance(rows_by_scenario, dict):
        rows_by_scenario = {}
    expired_share_warn_pct = _safe_float(os.environ.get("H_STRATEGY_EXPIRED_SHARE_WARN_PCT", "70")) or 70.0
    for scenario in strategy_focus_scenarios:
        scenario_row = rows_by_scenario.get(scenario, {}) if isinstance(rows_by_scenario, dict) else {}
        decision_rows = int(scenario_row.get("decision_rows", 0) or 0) if isinstance(scenario_row, dict) else 0
        sample_min_rows = (
            int(scenario_row.get("sample_min_rows", 0) or 0) if isinstance(scenario_row, dict) else 0
        ) or _strategy_sample_min_rows_for_health(scenario)
        provisional_flag = (
            int(scenario_row.get("provisional_sample_flag", 0) or 0) if isinstance(scenario_row, dict) else 0
        )
        expired_rows = int(scenario_row.get("expired_rows", 0) or 0) if isinstance(scenario_row, dict) else 0
        terminal_rows = int(scenario_row.get("terminal_rows", 0) or 0) if isinstance(scenario_row, dict) else 0
        expired_share_pct = (
            float(scenario_row.get("expired_share_pct", 0.0) or 0.0) if isinstance(scenario_row, dict) else 0.0
        )
        chosen_tactic = str(scenario_row.get("chosen_tactic", "") if isinstance(scenario_row, dict) else "").strip()
        if not scenario_row:
            provisional_flag = 1
        _add(
            rows,
            f"h_strategy_sample_size_{scenario}",
            "warn" if provisional_flag == 1 else "ok",
            str(decision_rows),
            (
                f"scenario={scenario};asof_date={latest_asof or 'none'};"
                f"sample_min_rows={sample_min_rows};provisional_sample_flag={provisional_flag};"
                f"chosen_tactic={chosen_tactic}"
            ),
        )
        _add(
            rows,
            f"h_strategy_expired_share_{scenario}",
            "warn" if (provisional_flag == 0 and expired_share_pct >= expired_share_warn_pct) else "ok",
            f"{expired_share_pct:.2f}",
            (
                f"scenario={scenario};asof_date={latest_asof or 'none'};"
                f"expired_rows={expired_rows};terminal_rows={terminal_rows};"
                f"warn_threshold_pct={expired_share_warn_pct:.2f}"
            ),
        )
    _required_non_blank_check(
        rows,
        "h_suppression_cases_required_fields_non_blank",
        H_SUPPRESSION_CASES_PATH,
        [
            "suppression_target_source",
            "suppression_ceiling_landed_temp",
            "anchor_floor_price",
            "action",
            "notes",
        ],
        optional=True,
    )
    _required_non_blank_check(
        rows,
        "h_suppression_reactivation_required_fields_non_blank",
        H_SUPPRESSION_REACTIVATION_LOG_PATH,
        [
            "suppression_target_source",
            "suppression_ceiling_landed_temp",
            "anchor_floor_price",
            "write_status",
            "reason_codes_json",
        ],
        optional=True,
    )
    try:
        cohort = _read_csv(LAB_COHORT_PATH)
        soi = _read_csv(H_SELLER_SOI_PATH)
        if cohort.empty:
            _add(rows, "h_seller_soi_active_coverage", "warn", "n/a", "cohort file missing or empty")
        else:
            enabled = cohort.get("enabled", "").astype(str).str.strip().str.lower()
            active_skus = set(
                cohort.loc[enabled.isin({"1", "true", "yes", "y"}), "sku"]
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )
            if not active_skus:
                _add(rows, "h_seller_soi_active_coverage", "warn", "0", "no active cohort SKUs")
            elif soi.empty:
                _add(rows, "h_seller_soi_active_coverage", "warn", str(len(active_skus)), "soi file empty")
            else:
                soi_skus = set(soi.get("sku", "").astype(str).str.strip().str.upper().tolist())
                missing = sorted([s for s in active_skus if s not in soi_skus])
                _add(
                    rows,
                    "h_seller_soi_active_coverage",
                    "ok" if not missing else "warn",
                    str(len(missing)),
                    "missing_skus=" + ",".join(missing) if missing else "all_active_skus_have_soi",
                )
    except Exception as exc:
        _add(rows, "h_seller_soi_active_coverage", "warn", "read_error", str(exc))
    try:
        event_log = _read_csv(PROBE_EVENT_LOG_PATH)
        if event_log.empty:
            _add(rows, "h_worker_probe_event_idempotent", "ok", "0", "no rows yet")
            _add(rows, "h_worker_probe_event_numeric_valid", "ok", "0", "no rows yet")
        else:
            required = [
                "probe_event_id",
                "probe_type",
                "action_price_before_gbp",
                "action_price_target_gbp",
                "hard_floor_gbp",
                "ceiling_gbp",
                "max_move_per_cycle_gbp",
                "cooldown_minutes",
                "expiry_utc",
                "event_utc",
                "supervisor_state",
            ]
            missing = [c for c in required if c not in event_log.columns]
            if missing:
                _add(rows, "h_worker_probe_event_idempotent", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_worker_probe_event_numeric_valid", "fail", "missing_cols", ",".join(missing))
            else:
                dup_count = int(event_log.duplicated(subset=["probe_event_id"], keep=False).sum())
                _add(rows, "h_worker_probe_event_idempotent", "ok" if dup_count == 0 else "fail", str(dup_count), "key=probe_event_id")

                e = event_log.copy()
                for col in [
                    "action_price_before_gbp",
                    "action_price_target_gbp",
                    "hard_floor_gbp",
                    "ceiling_gbp",
                    "max_move_per_cycle_gbp",
                    "cooldown_minutes",
                ]:
                    e[col] = pd.to_numeric(e[col], errors="coerce")

                allowed_state = {"unknown", "stable", "follower", "aggressor_candidate"}
                allowed_probe = {"lower", "match", "raise", "hold", "learn_down", "learn_up"}
                state_col = event_log["supervisor_state"].astype(str).str.strip().str.lower()
                probe_col = event_log["probe_type"].astype(str).str.strip().str.lower()

                bad_time = int(pd.to_datetime(event_log["event_utc"], errors="coerce", utc=True).isna().sum())
                bad_time += int(pd.to_datetime(event_log["expiry_utc"], errors="coerce", utc=True).isna().sum())

                move_size = (e["action_price_target_gbp"] - e["action_price_before_gbp"]).abs()
                invalid = (
                    e["action_price_before_gbp"].isna()
                    | e["action_price_target_gbp"].isna()
                    | e["hard_floor_gbp"].isna()
                    | e["ceiling_gbp"].isna()
                    | e["max_move_per_cycle_gbp"].isna()
                    | e["cooldown_minutes"].isna()
                    | (e["hard_floor_gbp"] < 0)
                    | (e["ceiling_gbp"] < e["hard_floor_gbp"])
                    | (e["action_price_target_gbp"] < e["hard_floor_gbp"])
                    | (e["action_price_target_gbp"] > e["ceiling_gbp"])
                    | (move_size > e["max_move_per_cycle_gbp"])
                    | (e["max_move_per_cycle_gbp"] <= 0)
                    | (e["cooldown_minutes"] < 1)
                    | (~state_col.isin(allowed_state))
                    | (~probe_col.isin(allowed_probe))
                )
                invalid_count = int(invalid.sum()) + bad_time
                _add(
                    rows,
                    "h_worker_probe_event_numeric_valid",
                    "ok" if invalid_count == 0 else "fail",
                    str(invalid_count),
                    "rules=target_in_floor_ceiling,move_within_max,cooldown>=1,state_enum,probe_enum,valid_timestamps",
                )
    except Exception as exc:
        _add(rows, "h_worker_probe_event_idempotent", "fail", "read_error", str(exc))
        _add(rows, "h_worker_probe_event_numeric_valid", "fail", "read_error", str(exc))
    try:
        event_log = _read_csv(PROBE_EVENT_LOG_PATH)
        if event_log.empty:
            _add(rows, "h_safe_mode_pilot_event_present", "fail", "0", "no probe events found")
            _add(rows, "h_safe_mode_pilot_scope_pilot_only", "ok", "0", "no safe mode rows yet")
            _add(rows, "h_safe_mode_pilot_actions_allowed", "ok", "0", "no safe mode rows yet")
        else:
            e = event_log.copy()
            source_col = e.get("source", "").astype(str).str.strip()

            safe = e.loc[source_col.eq("H007_run_safe_mode_pilot")].copy()
            if safe.empty:
                _add(
                    rows,
                    "h_safe_mode_pilot_event_present",
                    "fail",
                    "0",
                    "missing source=H007_run_safe_mode_pilot",
                )
                _add(rows, "h_safe_mode_pilot_scope_pilot_only", "ok", "0", "no safe mode rows yet")
                _add(rows, "h_safe_mode_pilot_actions_allowed", "ok", "0", "no safe mode rows yet")
            else:
                # Evaluate safe-mode scope on recent rows only, so historical pilot swaps
                # do not keep tripping the current pilot guardrail forever.
                window_hours = 48.0
                event_dt = pd.to_datetime(safe.get("event_utc", ""), errors="coerce", utc=True)
                cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
                recent_mask = event_dt.notna() & event_dt.ge(cutoff)
                safe_recent = safe.loc[recent_mask].copy()
                if safe_recent.empty:
                    _add(
                        rows,
                        "h_safe_mode_pilot_event_present",
                        "ok",
                        "0",
                        f"no recent safe mode rows;window_hours={window_hours:.1f}",
                    )
                    _add(
                        rows,
                        "h_safe_mode_pilot_scope_pilot_only",
                        "ok",
                        "0",
                        f"no recent safe mode rows;window_hours={window_hours:.1f}",
                    )
                    _add(
                        rows,
                        "h_safe_mode_pilot_actions_allowed",
                        "ok",
                        "0",
                        f"no recent safe mode rows;window_hours={window_hours:.1f}",
                    )
                    safe_recent = pd.DataFrame()

                if not safe_recent.empty:
                    safe_sku = safe_recent["sku"].astype(str).str.strip().str.upper()
                    pilot_rows = int(safe_sku.eq(OFFICIAL_PILOT_SKU).sum())
                    scope_invalid = int((~safe_sku.eq(OFFICIAL_PILOT_SKU)).sum())
                    safe_probe = safe_recent.get("probe_type", "").astype(str).str.strip().str.lower()
                    action_invalid = int((~safe_probe.isin({"hold", "match"})).sum())

                    _add(
                        rows,
                        "h_safe_mode_pilot_event_present",
                        "ok" if pilot_rows > 0 else "fail",
                        str(pilot_rows),
                        f"required_sku={OFFICIAL_PILOT_SKU};window_hours={window_hours:.1f};rows_considered={len(safe_recent)}",
                    )
                    _add(
                        rows,
                        "h_safe_mode_pilot_scope_pilot_only",
                        "ok" if scope_invalid == 0 else "fail",
                        str(scope_invalid),
                        f"required_scope_sku={OFFICIAL_PILOT_SKU};window_hours={window_hours:.1f};rows_considered={len(safe_recent)}",
                    )
                    _add(
                        rows,
                        "h_safe_mode_pilot_actions_allowed",
                        "ok" if action_invalid == 0 else "fail",
                        str(action_invalid),
                        "allowed=hold|match",
                    )
    except Exception as exc:
        _add(rows, "h_safe_mode_pilot_event_present", "fail", "read_error", str(exc))
        _add(rows, "h_safe_mode_pilot_scope_pilot_only", "fail", "read_error", str(exc))
        _add(rows, "h_safe_mode_pilot_actions_allowed", "fail", "read_error", str(exc))
    try:
        action_log = _read_csv(H_EXECUTIONER_ACTION_LOG_PATH)
        if action_log.empty:
            _add(rows, "h_executioner_action_log_idempotent", "warn", "0", "no action rows yet")
            _add(rows, "h_executioner_live_write_guardrails", "warn", "0", "no attempted live writes yet")
        else:
            required = [
                "probe_event_id",
                "sku",
                "live_write_attempted",
                "live_write_success",
                "price_before_gbp",
                "price_target_gbp",
                "price_executed_gbp",
                "source",
            ]
            missing = [c for c in required if c not in action_log.columns]
            if missing:
                _add(rows, "h_executioner_action_log_idempotent", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_executioner_live_write_guardrails", "fail", "missing_cols", ",".join(missing))
            else:
                dup_count = int(action_log.duplicated(subset=["probe_event_id"], keep=False).sum())
                _add(
                    rows,
                    "h_executioner_action_log_idempotent",
                    "ok" if dup_count == 0 else "fail",
                    str(dup_count),
                    "key=probe_event_id",
                )

                a = action_log.copy()
                a["price_before_gbp"] = pd.to_numeric(a["price_before_gbp"], errors="coerce")
                a["price_target_gbp"] = pd.to_numeric(a["price_target_gbp"], errors="coerce")
                a["price_executed_gbp"] = pd.to_numeric(a["price_executed_gbp"], errors="coerce")
                attempted = a["live_write_attempted"].astype(str).str.strip()
                succeeded = a["live_write_success"].astype(str).str.strip()
                sku_col = a["sku"].astype(str).str.strip().str.upper()
                src_col = a["source"].astype(str).str.strip()
                attempted_rows = attempted.eq("1")

                bool_invalid = int((~attempted.isin({"0", "1"})).sum() + (~succeeded.isin({"0", "1"})).sum())
                numeric_invalid = int(
                    a["price_before_gbp"].isna().sum()
                    + a["price_target_gbp"].isna().sum()
                    + a["price_executed_gbp"].isna().sum()
                )
                scope_invalid = int((attempted_rows & ~sku_col.eq(OFFICIAL_PILOT_SKU)).sum())
                source_invalid = int((attempted_rows & ~src_col.eq("run_H_pricing_cycle")).sum())
                success_conflict = int((succeeded.eq("1") & ~attempted_rows).sum())

                invalid_count = bool_invalid + numeric_invalid + scope_invalid + source_invalid + success_conflict
                _add(
                    rows,
                    "h_executioner_live_write_guardrails",
                    "ok" if invalid_count == 0 else "fail",
                    str(invalid_count),
                    "rules=bool_flags_valid,numeric_prices_present,attempt_scope_pilot_only,attempt_source=run_H_pricing_cycle",
                )
    except Exception as exc:
        _add(rows, "h_executioner_action_log_idempotent", "fail", "read_error", str(exc))
        _add(rows, "h_executioner_live_write_guardrails", "fail", "read_error", str(exc))
    try:
        response_log = _read_csv(PROBE_RESPONSE_LOG_PATH)
        if response_log.empty:
            _add(rows, "h_worker_probe_response_idempotent", "ok", "0", "no rows yet")
            _add(rows, "h_worker_probe_response_types_valid", "ok", "0", "no rows yet")
        else:
            required = [
                "probe_event_id",
                "response_window_minutes",
                "response_utc",
                "competitor_moved_flag",
                "competitor_move_direction",
                "competitor_move_size_gbp",
                "reaction_lag_minutes",
            ]
            missing = [c for c in required if c not in response_log.columns]
            if missing:
                _add(rows, "h_worker_probe_response_idempotent", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_worker_probe_response_types_valid", "fail", "missing_cols", ",".join(missing))
            else:
                dup_count = int(
                    response_log.duplicated(subset=["probe_event_id", "response_window_minutes"], keep=False).sum()
                )
                _add(
                    rows,
                    "h_worker_probe_response_idempotent",
                    "ok" if dup_count == 0 else "fail",
                    str(dup_count),
                    "key=probe_event_id+response_window_minutes",
                )

                r = response_log.copy()
                r["response_window_minutes"] = pd.to_numeric(r["response_window_minutes"], errors="coerce")
                r["competitor_move_size_gbp"] = pd.to_numeric(r["competitor_move_size_gbp"], errors="coerce")
                r["reaction_lag_minutes"] = pd.to_numeric(r["reaction_lag_minutes"], errors="coerce")

                moved = response_log["competitor_moved_flag"].astype(str).str.strip()
                direction = response_log["competitor_move_direction"].astype(str).str.strip().str.lower()
                bad_time = int(pd.to_datetime(response_log["response_utc"], errors="coerce", utc=True).isna().sum())
                valid_windows = {5, 15, 60, 240}
                bad_window = int((r["response_window_minutes"].isna() | ~r["response_window_minutes"].isin(valid_windows)).sum())
                bad_moved = int((~moved.isin({"0", "1"})).sum())
                bad_direction = int((~direction.isin({"up", "down", "flat", "unknown"})).sum())
                bad_move_size = int((r["competitor_move_size_gbp"].isna() | (r["competitor_move_size_gbp"] < 0)).sum())
                bad_reaction = int((r["reaction_lag_minutes"].notna() & (r["reaction_lag_minutes"] < 0)).sum())
                conflict_static = int(((moved == "0") & direction.isin({"up", "down"})).sum())
                conflict_dynamic = int(((moved == "1") & ~direction.isin({"up", "down"})).sum())

                invalid_count = (
                    bad_time
                    + bad_window
                    + bad_moved
                    + bad_direction
                    + bad_move_size
                    + bad_reaction
                    + conflict_static
                    + conflict_dynamic
                )
                _add(
                    rows,
                    "h_worker_probe_response_types_valid",
                    "ok" if invalid_count == 0 else "fail",
                    str(invalid_count),
                    "rules=window_enum,moved_flag_binary,direction_enum,move_size>=0,reaction_lag>=0,valid_timestamps",
                )
    except Exception as exc:
        _add(rows, "h_worker_probe_response_idempotent", "fail", "read_error", str(exc))
        _add(rows, "h_worker_probe_response_types_valid", "fail", "read_error", str(exc))
    _schema_check(
        rows,
        "h_schema_listing_offer_history",
        LISTING_OFFER_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "our_price",
            "buy_box_price",
            "buy_box_channel",
            "lowest_fba_price",
            "lowest_fbm_price",
            "offer_count_fba",
            "offer_count_fbm",
            "bsr",
            "bsr_category",
            "source",
            "notes",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_listing_offer_seller_history",
        LISTING_OFFER_SELLER_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "seller_id",
            "seller_seen_flag",
            "offer_price_gbp",
            "offer_shipping_price_gbp",
            "offer_landed_price_gbp",
            "is_prime",
            "fulfilment_channel",
            "min_delivery_days",
            "max_delivery_days",
            "delivery_range_days",
            "source",
            "notes",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_phase1_seller_history",
        PHASE1_SELLER_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "seller_id",
            "seller_seen_flag",
            "first_seen_timestamp",
            "last_seen_timestamp",
            "continuous_presence_hours",
            "absence_gap_hours",
            "reentry_after_absence_flag",
            "offer_price_gbp",
            "min_price_seen_gbp",
            "max_price_seen_gbp",
            "median_price_seen_gbp",
            "time_at_min_price_hours",
            "time_at_max_price_hours",
            "price_move_initiations",
            "follow_events",
            "reaction_lag_minutes",
            "directional_bias",
            "floor_set_events",
            "min_delivery_days",
            "max_delivery_days",
            "delivery_range_days",
            "is_prime",
            "delivery_delta_vs_fastest_days",
            "fulfilment_channel",
            "our_price",
            "our_price_changes",
            "our_delivery_posture",
            "manual_interventions",
            "intent_notes",
            "source",
            "notes",
        ],
        optional=True,
    )
    _phase1_contract_checks(rows, PHASE1_SELLER_HISTORY)
    _schema_check_jsonl(
        rows,
        "h_schema_api_call_log",
        API_CALL_LOG_JSONL,
        [
            "run_id",
            "timestamp_utc",
            "script_name",
            "endpoint",
            "marketplace",
            "sku_count",
            "http_status",
            "retries",
            "throttled",
            "backoff_seconds",
            "error_code",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_api_run_log",
        API_RUN_LOG_CSV,
        [
            "run_id",
            "started_utc",
            "finished_utc",
            "status",
            "calls_products_pricing_get_price",
            "calls_listings_items_get_item",
            "calls_finances_get_financial_events",
            "notes",
        ],
        optional=True,
    )
    try:
        if API_RUN_LOG_CSV.exists():
            api_runs = pd.read_csv(API_RUN_LOG_CSV, dtype=str).fillna("")
            window_hours = float(os.environ.get("API_RUN_FAIL_LOG_HOURS", "24"))
            cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
            if api_runs.empty or "status" not in api_runs.columns:
                _add(rows, "h_api_recent_fail_runs", "warn", "n/a", "missing status column or no rows")
            else:
                finished = (
                    _to_dt(api_runs["finished_utc"]) if "finished_utc" in api_runs.columns
                    else pd.Series(pd.NaT, index=api_runs.index)
                )
                started = (
                    _to_dt(api_runs["started_utc"]) if "started_utc" in api_runs.columns
                    else pd.Series(pd.NaT, index=api_runs.index)
                )
                event_ts = finished.where(~finished.isna(), started)
                recent_mask = event_ts.isna() | (event_ts >= cutoff)
                recent = api_runs.loc[recent_mask].copy()
                recent["_status"] = recent["status"].astype(str).str.upper()
                recent["_event_ts"] = event_ts.loc[recent.index]
                ok_ts = recent.loc[recent["_status"] == "OK", "_event_ts"].dropna()
                if ok_ts.empty:
                    fail_runs = recent[recent["_status"] == "FAIL"]
                else:
                    last_ok_ts = ok_ts.max()
                    fail_runs = recent[
                        (recent["_status"] == "FAIL")
                        & (recent["_event_ts"].isna() | (recent["_event_ts"] > last_ok_ts))
                    ]
                _add(
                    rows,
                    "h_api_recent_fail_runs",
                    "warn" if not fail_runs.empty else "ok",
                    str(len(fail_runs)),
                    f"window_hours={window_hours}",
                )
        else:
            _add(rows, "h_api_recent_fail_runs", "warn", "missing", f"path {API_RUN_LOG_CSV}")
    except Exception as exc:
        _add(rows, "h_api_recent_fail_runs", "warn", "read_error", str(exc))

    _schema_check_json_object(
        rows,
        "h_schema_api_rate_state",
        API_RATE_STATE_JSON,
        [],
        optional=True,
    )
    if SPAPI_LOCK_PATH.exists():
        lock_info = _file_info(SPAPI_LOCK_PATH)
        try:
            lock_mtime = datetime.fromisoformat(lock_info["mtime_utc"].replace("Z", "+00:00"))
            lock_age_hours = max((datetime.now(timezone.utc) - lock_mtime).total_seconds() / 3600.0, 0.0)
            lock_status = "fail" if lock_age_hours > 2.0 else "warn"
            _add(rows, "h_spapi_lock_present", lock_status, f"{lock_age_hours:.2f}", f"path {SPAPI_LOCK_PATH}")
        except Exception:
            _add(rows, "h_spapi_lock_present", "warn", "n/a", f"path {SPAPI_LOCK_PATH}")
    else:
        _add(rows, "h_spapi_lock_present", "ok", "0", "")
    for check_name, candidates in [
        ("h_cycle_stale_lock", H_LOCK_PATH_CANDIDATES),
        ("e_cycle_stale_lock", E_LOCK_PATH_CANDIDATES),
    ]:
        _cycle_stale_lock_check(rows, check_name, candidates)
    _critical_freshness_check(
        rows,
        "h_cycle_log_freshness",
        H_CYCLE_LOG_PATH_CANDIDATES,
        warn_after_minutes=float(os.environ.get("H_CYCLE_LOG_WARN_MINUTES", "20")),
        fail_after_minutes=float(os.environ.get("H_CYCLE_LOG_FAIL_MINUTES", "60")),
        owner_cycle="H",
        recovery_signal="run_H_cycle.bat_guarded_owner",
        now_utc=now_utc_dt,
    )
    _critical_freshness_check(
        rows,
        "h_listing_offer_snapshot_latest_freshness",
        [LISTING_OFFER_SNAPSHOT_LATEST_PATH],
        warn_after_minutes=float(os.environ.get("H_LISTING_SNAPSHOT_WARN_MINUTES", "20")),
        fail_after_minutes=float(os.environ.get("H_LISTING_SNAPSHOT_FAIL_MINUTES", "60")),
        owner_cycle="H",
        recovery_signal="run_H_cycle.bat_guarded_owner",
        now_utc=now_utc_dt,
    )
    _critical_freshness_check(
        rows,
        "h_phase1_runtime_floor_snapshot_latest_freshness",
        [PHASE1_RUNTIME_FLOOR_SNAPSHOT_LATEST_PATH],
        warn_after_minutes=float(os.environ.get("H_FLOOR_SNAPSHOT_WARN_MINUTES", "30")),
        fail_after_minutes=float(os.environ.get("H_FLOOR_SNAPSHOT_FAIL_MINUTES", "90")),
        owner_cycle="H",
        recovery_signal="run_H_cycle.bat_guarded_owner",
        now_utc=now_utc_dt,
    )
    _critical_freshness_check(
        rows,
        "h_ceiling_events_current",
        [H_CEILING_EVENTS_PATH],
        warn_after_minutes=float(os.environ.get("H_CEILING_EVENTS_WARN_MINUTES", "20")),
        fail_after_minutes=float(os.environ.get("H_CEILING_EVENTS_FAIL_MINUTES", "60")),
        owner_cycle="H",
        recovery_signal="run_H_cycle.bat_guarded_owner",
        now_utc=now_utc_dt,
    )
    _critical_freshness_check(
        rows,
        "h_strategy_outcome_log_current",
        [H_STRATEGY_OUTCOME_LOG_PATH],
        warn_after_minutes=float(os.environ.get("H_STRATEGY_OUTCOME_LOG_WARN_MINUTES", "20")),
        fail_after_minutes=float(os.environ.get("H_STRATEGY_OUTCOME_LOG_FAIL_MINUTES", "60")),
        owner_cycle="H",
        recovery_signal="run_H_cycle.bat_guarded_owner",
        now_utc=now_utc_dt,
    )
    _critical_freshness_check(
        rows,
        "h_strategy_outcome_daily_current",
        [H_STRATEGY_OUTCOME_DAILY_PATH],
        warn_after_minutes=float(os.environ.get("H_STRATEGY_OUTCOME_DAILY_WARN_MINUTES", "1440")),
        fail_after_minutes=float(os.environ.get("H_STRATEGY_OUTCOME_DAILY_FAIL_MINUTES", "2880")),
        owner_cycle="H",
        recovery_signal="run_H_cycle.bat_guarded_owner",
        now_utc=now_utc_dt,
        missing_status="warn",
    )
    _critical_freshness_check(
        rows,
        "h_terminal_marker_freshness",
        H_TERMINAL_INFO_PATH_CANDIDATES,
        warn_after_minutes=float(os.environ.get("H_PUBLISH_MARKER_WARN_MINUTES", "30")),
        fail_after_minutes=float(os.environ.get("H_PUBLISH_MARKER_FAIL_MINUTES", "90")),
        owner_cycle="H",
        recovery_signal="run_H_cycle.bat_guarded_owner",
        now_utc=now_utc_dt,
        missing_status="warn",
    )
    _h_publish_marker_freshness_check(
        rows,
        now_utc=now_utc_dt,
    )
    snapshot_path = _latest_snapshot(LISTING_OFFER_SNAPSHOT_GLOB)
    if snapshot_path is None:
        _add(rows, "h_schema_listing_offer_snapshot", "warn", "missing", "no snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_listing_offer_snapshot",
            snapshot_path,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "our_price",
                "buy_box_price",
                "buy_box_channel",
                "lowest_fba_price",
                "lowest_fbm_price",
                "offer_count_fba",
                "offer_count_fbm",
                "bsr",
                "bsr_category",
                "source",
                "notes",
            ],
            optional=True,
        )
        try:
            snap = pd.read_csv(snapshot_path, dtype=str).fillna("")
            if snap.empty:
                _add(rows, "h_market_context_fill_nonzero", "warn", "0", "snapshot empty")
            else:
                required_nonzero = [
                    "buy_box_channel",
                    "lowest_fba_price",
                    "lowest_fbm_price",
                    "offer_count_fba",
                    "offer_count_fbm",
                ]
                zero_cols = []
                filled_parts = []
                for col in required_nonzero:
                    filled = int(snap[col].astype(str).str.strip().ne("").sum()) if col in snap.columns else 0
                    if filled == 0:
                        zero_cols.append(col)
                    filled_parts.append(f"{col}={filled}")
                if zero_cols:
                    _add(
                        rows,
                        "h_market_context_fill_nonzero",
                        "fail",
                        str(len(zero_cols)),
                        "zero_fill_cols=" + ",".join(zero_cols) + "; " + "; ".join(filled_parts),
                    )
                else:
                    _add(rows, "h_market_context_fill_nonzero", "ok", "0", "; ".join(filled_parts))
        except Exception as exc:
            _add(rows, "h_market_context_fill_nonzero", "warn", "read_error", str(exc))
    seller_snapshot_path = _preferred_seller_snapshot_path()
    if seller_snapshot_path is None:
        _add(rows, "h_schema_listing_offer_seller_snapshot", "warn", "missing", "no seller snapshot files found")
        _add(rows, "h_seller_snapshot_landed_non_null_training", "warn", "missing", "no seller snapshot files found")
        _add(rows, "h_seller_snapshot_landed_ge_listing", "warn", "missing", "no seller snapshot files found")
        _add(rows, "h_seller_snapshot_shipping_non_negative", "warn", "missing", "no seller snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_listing_offer_seller_snapshot",
            seller_snapshot_path,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "seller_id",
                "seller_seen_flag",
                "offer_price_gbp",
                "offer_shipping_price_gbp",
                "offer_landed_price_gbp",
                "is_prime",
                "fulfilment_channel",
                "min_delivery_days",
                "max_delivery_days",
                "delivery_range_days",
                "source",
                "notes",
            ],
            optional=True,
        )
        try:
            seller_snap = pd.read_csv(seller_snapshot_path, dtype=str).fillna("")
            expected_empty_reason = _h_expected_empty_seller_profile_reason()
            if seller_snap.empty:
                empty_note = "snapshot empty"
                if expected_empty_reason:
                    empty_note = f"{empty_note}; expected_empty_reason={expected_empty_reason}"
                    _add(rows, "h_seller_snapshot_landed_non_null_training", "ok", "0", empty_note)
                    _add(rows, "h_seller_snapshot_landed_ge_listing", "ok", "0", empty_note)
                    _add(rows, "h_seller_snapshot_shipping_non_negative", "ok", "0", empty_note)
                else:
                    _add(rows, "h_seller_snapshot_landed_non_null_training", "warn", "0", empty_note)
                    _add(rows, "h_seller_snapshot_landed_ge_listing", "warn", "0", empty_note)
                    _add(rows, "h_seller_snapshot_shipping_non_negative", "warn", "0", empty_note)
            else:
                train = _read_csv(TRAINING_SET_PATH)
                if train.empty or "sku" not in train.columns:
                    training_skus = set(seller_snap.get("sku", pd.Series(dtype=str)).astype(str).str.strip().str.upper().tolist())
                else:
                    if "enabled" in train.columns:
                        enabled = train["enabled"].astype(str).str.strip().str.lower()
                        train = train[enabled.isin({"1", "true", "yes", "y"})].copy()
                    training_skus = set(train["sku"].astype(str).str.strip().str.upper().tolist())
                snap_sku = seller_snap.get("sku", pd.Series(dtype=str)).astype(str).str.strip().str.upper()
                train_rows = seller_snap.loc[snap_sku.isin(training_skus)].copy() if training_skus else seller_snap.copy()
                if train_rows.empty:
                    train_empty_note = "no training rows in snapshot"
                    if expected_empty_reason:
                        train_empty_note = f"{train_empty_note}; expected_empty_reason={expected_empty_reason}"
                        _add(rows, "h_seller_snapshot_landed_non_null_training", "ok", "0", train_empty_note)
                        _add(rows, "h_seller_snapshot_landed_ge_listing", "ok", "0", train_empty_note)
                        _add(rows, "h_seller_snapshot_shipping_non_negative", "ok", "0", train_empty_note)
                    else:
                        _add(rows, "h_seller_snapshot_landed_non_null_training", "warn", "0", train_empty_note)
                        _add(rows, "h_seller_snapshot_landed_ge_listing", "warn", "0", train_empty_note)
                        _add(rows, "h_seller_snapshot_shipping_non_negative", "warn", "0", train_empty_note)
                else:
                    listing_num = pd.to_numeric(train_rows.get("offer_price_gbp", ""), errors="coerce")
                    shipping_num = pd.to_numeric(train_rows.get("offer_shipping_price_gbp", ""), errors="coerce")
                    landed_num = pd.to_numeric(train_rows.get("offer_landed_price_gbp", ""), errors="coerce")

                    needs_landed = listing_num.notna()
                    landed_blank = int((needs_landed & landed_num.isna()).sum())
                    _add(
                        rows,
                        "h_seller_snapshot_landed_non_null_training",
                        "ok" if landed_blank == 0 else "fail",
                        str(landed_blank),
                        f"training_rows={len(train_rows.index)}",
                    )

                    comparable = listing_num.notna() & landed_num.notna()
                    landed_lt_listing = int((comparable & (landed_num + 1e-9 < listing_num)).sum())
                    _add(
                        rows,
                        "h_seller_snapshot_landed_ge_listing",
                        "ok" if landed_lt_listing == 0 else "fail",
                        str(landed_lt_listing),
                        f"comparable_rows={int(comparable.sum())}",
                    )

                    shipping_present = shipping_num.notna()
                    shipping_negative = int((shipping_present & (shipping_num < 0)).sum())
                    _add(
                        rows,
                        "h_seller_snapshot_shipping_non_negative",
                        "ok" if shipping_negative == 0 else "fail",
                        str(shipping_negative),
                        f"shipping_rows={int(shipping_present.sum())}",
                    )
        except Exception as exc:
            _add(rows, "h_seller_snapshot_landed_non_null_training", "warn", "read_error", str(exc))
            _add(rows, "h_seller_snapshot_landed_ge_listing", "warn", "read_error", str(exc))
            _add(rows, "h_seller_snapshot_shipping_non_negative", "warn", "read_error", str(exc))

    market_snapshot_path = _latest_snapshot(HOS_DAILY_MARKET_SNAPSHOT_GLOB)
    market_required_cols = [
        "asof_date",
        "marketplace",
        "sku",
        "asin",
        "buy_box_price_raw_gross",
        "buy_box_price_used_gross",
        "buy_box_channel",
        "buy_box_seller_id",
        "buy_box_missing_flag",
        "buy_box_fallback_used_flag",
        "lowest_offer_price_gross",
        "lowest_fba_price_gross",
        "lowest_fbm_price_gross",
        "highest_offer_price_gross",
        "median_offer_price_gross",
        "price_spread_gross",
        "offer_count_total",
        "offer_count_fba",
        "offer_count_fbm",
        "amazon_present_flag",
        "seller_entry_count_today",
        "seller_exit_count_today",
        "our_delivery_days",
        "buy_box_delivery_days",
        "delivery_parity_flag",
        "prime_eligible_flag",
        "break_even_exvat_gbp",
        "break_even_gross_gbp",
        "token_cost_exvat_gbp",
        "min_price_gross_10pct",
        "max_price_gross_current",
    ]
    if market_snapshot_path is None:
        _add(rows, "h_market_snapshot_exists", "fail", "missing", "no hos_daily_market_snapshot files found")
        _add(rows, "h_market_snapshot_rows_10", "fail", "missing", "")
        _add(rows, "h_market_snapshot_required_columns", "fail", "missing", "")
        _add(rows, "h_market_snapshot_no_null_core_fields", "fail", "missing", "")
        _add(rows, "h_market_snapshot_delivery_parity_binary", "fail", "missing", "")
        _add(rows, "h_market_snapshot_econ_anchors_filled", "fail", "missing", "")
        _add(rows, "h_market_report_html_exists", "fail", "missing", "market snapshot missing")
        _add(rows, "h_market_report_pdf_exists", "fail", "missing", "market snapshot missing")
        _add(rows, "h_market_report_price_charts_count", "fail", "missing", "market snapshot missing")
        _add(rows, "h_market_report_seller_mix_charts_count", "fail", "missing", "market snapshot missing")
    else:
        _add(rows, "h_market_snapshot_exists", "ok", "yes", f"path {market_snapshot_path}")
        try:
            market = pd.read_csv(market_snapshot_path, dtype=str).fillna("")
        except Exception as exc:
            _add(rows, "h_market_snapshot_rows_10", "fail", "read_error", str(exc))
            _add(rows, "h_market_snapshot_required_columns", "fail", "read_error", str(exc))
            _add(rows, "h_market_snapshot_no_null_core_fields", "fail", "read_error", str(exc))
            _add(rows, "h_market_snapshot_delivery_parity_binary", "fail", "read_error", str(exc))
            _add(rows, "h_market_snapshot_econ_anchors_filled", "fail", "read_error", str(exc))
        else:
            row_count = len(market.index)
            _add(
                rows,
                "h_market_snapshot_rows_10",
                "ok" if row_count >= 10 else "fail",
                str(row_count),
                "expected_at_least=10",
            )

            missing_cols = [c for c in market_required_cols if c not in market.columns]
            if missing_cols:
                _add(rows, "h_market_snapshot_required_columns", "fail", str(len(missing_cols)), ",".join(missing_cols))
            else:
                _add(rows, "h_market_snapshot_required_columns", "ok", "0", "")

            core_fields = ["buy_box_price_used_gross", "offer_count_fba", "offer_count_fbm"]
            missing_core_counts: List[str] = []
            missing_core_total = 0
            for col in core_fields:
                if col not in market.columns:
                    missing_core_total += row_count
                    missing_core_counts.append(f"{col}=MISSING_COL")
                    continue
                blank_count = int(market[col].astype(str).str.strip().eq("").sum())
                missing_core_total += blank_count
                missing_core_counts.append(f"{col}={blank_count}")
            _add(
                rows,
                "h_market_snapshot_no_null_core_fields",
                "ok" if missing_core_total == 0 else "fail",
                str(missing_core_total),
                "; ".join(missing_core_counts),
            )

            if "delivery_parity_flag" not in market.columns:
                _add(rows, "h_market_snapshot_delivery_parity_binary", "fail", str(row_count), "delivery_parity_flag missing")
            else:
                parity = market["delivery_parity_flag"].astype(str).str.strip()
                invalid = int((parity.ne("") & ~parity.isin({"0", "1"})).sum())
                _add(
                    rows,
                    "h_market_snapshot_delivery_parity_binary",
                    "ok" if invalid == 0 else "fail",
                    str(invalid),
                    "allowed_values=0,1",
                )

            train = _read_csv(TRAINING_SET_PATH)
            if train.empty or "sku" not in train.columns:
                training_skus = set(market.get("sku", pd.Series(dtype=str)).astype(str).str.strip().str.upper().tolist())
            else:
                if "enabled" in train.columns:
                    enabled = train["enabled"].astype(str).str.strip().str.lower()
                    train = train[enabled.isin({"1", "true", "yes", "y"})].copy()
                training_skus = set(train["sku"].astype(str).str.strip().str.upper().tolist())
            if not training_skus:
                _add(rows, "h_market_snapshot_econ_anchors_filled", "warn", "0", "no training SKUs found")
            else:
                market_sku = market.get("sku", pd.Series(dtype=str)).astype(str).str.strip().str.upper()
                train_mask = market_sku.isin(training_skus)
                train_rows = market.loc[train_mask].copy()
                if train_rows.empty:
                    _add(rows, "h_market_snapshot_econ_anchors_filled", "fail", str(len(training_skus)), "training SKUs missing from snapshot")
                else:
                    econ_cols = [
                        "break_even_exvat_gbp",
                        "break_even_gross_gbp",
                        "token_cost_exvat_gbp",
                        "min_price_gross_10pct",
                        "max_price_gross_current",
                    ]
                    missing_econ_total = 0
                    missing_econ_parts: List[str] = []
                    for col in econ_cols:
                        if col not in train_rows.columns:
                            missing = len(train_rows.index)
                        else:
                            missing = int(train_rows[col].astype(str).str.strip().eq("").sum())
                        missing_econ_total += missing
                        missing_econ_parts.append(f"{col}={missing}")
                    _add(
                        rows,
                        "h_market_snapshot_econ_anchors_filled",
                        "ok" if missing_econ_total == 0 else "fail",
                        str(missing_econ_total),
                        f"training_rows={len(train_rows.index)}; " + "; ".join(missing_econ_parts),
                    )

            report_asof_date = _max_asof_date(market_snapshot_path)
            if not report_asof_date:
                report_asof_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            report_html = HOS_DAILY_REPORT_DIR / f"hos_daily_report_{report_asof_date}.html"
            report_pdf = HOS_DAILY_REPORT_DIR / f"hos_daily_report_{report_asof_date}.pdf"
            expected_skus = int(market.get("sku", pd.Series(dtype=str)).astype(str).str.strip().replace("", pd.NA).dropna().nunique())
            if expected_skus == 0:
                expected_skus = int(len(market.index))

            _add(
                rows,
                "h_market_report_html_exists",
                "ok" if report_html.exists() else "fail",
                "yes" if report_html.exists() else "missing",
                f"path {report_html}",
            )
            _add(
                rows,
                "h_market_report_pdf_exists",
                "ok" if report_pdf.exists() else "fail",
                "yes" if report_pdf.exists() else "missing",
                f"path {report_pdf}",
            )

            price_chart_count = 0
            mix_chart_count = 0
            if HOS_DAILY_REPORT_CHART_DIR.exists():
                price_chart_count = len(list(HOS_DAILY_REPORT_CHART_DIR.glob(f"{report_asof_date}_*_price_trend.png")))
                mix_chart_count = len(list(HOS_DAILY_REPORT_CHART_DIR.glob(f"{report_asof_date}_*_seller_mix.png")))

            _add(
                rows,
                "h_market_report_price_charts_count",
                "ok" if price_chart_count >= expected_skus else "fail",
                str(price_chart_count),
                f"expected_at_least={expected_skus}",
            )
            _add(
                rows,
                "h_market_report_seller_mix_charts_count",
                "ok" if mix_chart_count >= expected_skus else "fail",
                str(mix_chart_count),
                f"expected_at_least={expected_skus}",
            )

    _schema_check(
        rows,
        "h_schema_inventory_history",
        INVENTORY_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "available",
            "inbound_working",
            "inbound_shipped",
            "inbound_receiving",
            "inbound_total",
            "source",
            "notes",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_inbound_history",
        INBOUND_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "inbound_working",
            "inbound_shipped",
            "inbound_receiving",
            "inbound_total",
            "source",
            "notes",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_refund_adjustment_history",
        REFUND_ADJUSTMENT_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "refund_event_count",
            "adjustment_event_count",
            "refund_units",
            "adjustment_units",
            "refund_amount_gbp",
            "adjustment_amount_gbp",
            "source",
            "notes",
        ],
        optional=True,
    )

    inv_snapshot = _latest_snapshot(INVENTORY_SNAPSHOT_GLOB)
    if inv_snapshot is None:
        _add(rows, "h_schema_inventory_snapshot", "warn", "missing", "no snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_inventory_snapshot",
            inv_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "available",
                "inbound_working",
                "inbound_shipped",
                "inbound_receiving",
                "inbound_total",
                "source",
                "notes",
            ],
            optional=True,
        )

    inbound_snapshot = _latest_snapshot(INBOUND_SNAPSHOT_GLOB)
    if inbound_snapshot is None:
        _add(rows, "h_schema_inbound_snapshot", "warn", "missing", "no snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_inbound_snapshot",
            inbound_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "inbound_working",
                "inbound_shipped",
                "inbound_receiving",
                "inbound_total",
                "source",
                "notes",
            ],
            optional=True,
        )
    refund_snapshot = _latest_snapshot(REFUND_ADJUSTMENT_SNAPSHOT_GLOB)
    if refund_snapshot is None:
        _add(rows, "h_schema_refund_adjustment_snapshot", "warn", "missing", "no snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_refund_adjustment_snapshot",
            refund_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "refund_event_count",
                "adjustment_event_count",
                "refund_units",
                "adjustment_units",
                "refund_amount_gbp",
                "adjustment_amount_gbp",
                "source",
                "notes",
            ],
            optional=True,
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        if LISTING_OFFER_HISTORY.exists():
            offer_hist = read_dataframe_with_sql_fallback(
                LISTING_OFFER_HISTORY,
                "h_listing_offer_history",
                dtype=str,
            ).fillna("")
            if "asof_date" not in offer_hist.columns:
                _add(rows, "h_listing_offer_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                offer_hist_today = offer_hist[offer_hist["asof_date"].astype(str) == today].copy()
                if offer_hist_today.empty:
                    snapshot_today_path = OUT / f"listing_offer_snapshot_{today}.csv"
                    if snapshot_today_path.exists():
                        try:
                            snap_today = pd.read_csv(snapshot_today_path, dtype=str).fillna("")
                            if {"asof_date", "sku", "marketplace"}.issubset(set(snap_today.columns)):
                                snap_today = snap_today[snap_today["asof_date"].astype(str) == today].copy()
                                if snap_today.empty:
                                    _add(
                                        rows,
                                        "h_listing_offer_history_idempotent_today",
                                        "warn",
                                        "0",
                                        f"no rows for {today}; history_path={LISTING_OFFER_HISTORY}; fallback_snapshot={snapshot_today_path}",
                                    )
                                else:
                                    offer_dup = int(
                                        snap_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum()
                                    )
                                    offer_status = "fail" if offer_dup > 0 else "ok"
                                    _add(
                                        rows,
                                        "h_listing_offer_history_idempotent_today",
                                        offer_status,
                                        str(offer_dup),
                                        f"asof_date={today}; source=fallback_snapshot; path={snapshot_today_path}",
                                    )
                            else:
                                _add(
                                    rows,
                                    "h_listing_offer_history_idempotent_today",
                                    "warn",
                                    "missing_col",
                                    f"fallback_snapshot={snapshot_today_path}; required=asof_date,sku,marketplace",
                                )
                        except Exception as exc:
                            _add(rows, "h_listing_offer_history_idempotent_today", "warn", "read_error", str(exc))
                    else:
                        _add(rows, "h_listing_offer_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    offer_dup = int(
                        offer_hist_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum()
                    )
                    offer_status = "fail" if offer_dup > 0 else "ok"
                    _add(rows, "h_listing_offer_history_idempotent_today", offer_status, str(offer_dup), f"asof_date={today}")
        else:
            _add(rows, "h_listing_offer_history_idempotent_today", "warn", "missing", f"path {LISTING_OFFER_HISTORY}")
    except Exception as exc:
        _add(rows, "h_listing_offer_history_idempotent_today", "warn", "read_error", str(exc))
    try:
        if LISTING_OFFER_SELLER_HISTORY.exists():
            seller_hist = pd.read_csv(LISTING_OFFER_SELLER_HISTORY, dtype=str).fillna("")
            if "asof_date" not in seller_hist.columns:
                _add(rows, "h_listing_offer_seller_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                seller_today = seller_hist[seller_hist["asof_date"].astype(str) == today].copy()
                if seller_today.empty:
                    expected_empty_reason = _h_expected_empty_seller_profile_reason()
                    note = f"no rows for {today}"
                    if expected_empty_reason:
                        note = f"{note}; expected_empty_reason={expected_empty_reason}"
                        _add(rows, "h_listing_offer_seller_history_idempotent_today", "ok", "0", note)
                    else:
                        _add(rows, "h_listing_offer_seller_history_idempotent_today", "warn", "0", note)
                else:
                    seller_dup = int(
                        seller_today.duplicated(
                            subset=["asof_date", "marketplace", "sku", "asin", "seller_id"],
                            keep=False,
                        ).sum()
                    )
                    seller_status = "fail" if seller_dup > 0 else "ok"
                    _add(
                        rows,
                        "h_listing_offer_seller_history_idempotent_today",
                        seller_status,
                        str(seller_dup),
                        f"asof_date={today}",
                    )
        else:
            _add(
                rows,
                "h_listing_offer_seller_history_idempotent_today",
                "warn",
                "missing",
                f"path {LISTING_OFFER_SELLER_HISTORY}",
            )
    except Exception as exc:
        _add(rows, "h_listing_offer_seller_history_idempotent_today", "warn", "read_error", str(exc))

    try:
        if INVENTORY_HISTORY.exists():
            inv_hist = read_dataframe_with_sql_fallback(
                INVENTORY_HISTORY,
                "a_inventory_history",
                dtype=str,
            ).fillna("")
            if "asof_date" not in inv_hist.columns:
                _add(rows, "h_inventory_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                inv_hist_today = inv_hist[inv_hist["asof_date"].astype(str) == today].copy()
                if inv_hist_today.empty:
                    if h_paused:
                        _add(
                            rows,
                            "h_inventory_history_idempotent_today",
                            "ok",
                            "0",
                            f"no rows for {today}; h_cycle_pause_requested=1",
                        )
                    else:
                        _add(rows, "h_inventory_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    inv_dup = int(inv_hist_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum())
                    inv_status = "fail" if inv_dup > 0 else "ok"
                    _add(rows, "h_inventory_history_idempotent_today", inv_status, str(inv_dup), f"asof_date={today}")
        else:
            _add(rows, "h_inventory_history_idempotent_today", "warn", "missing", f"path {INVENTORY_HISTORY}")
    except Exception as exc:
        _add(rows, "h_inventory_history_idempotent_today", "warn", "read_error", str(exc))

    try:
        if INBOUND_HISTORY.exists():
            inbound_hist = pd.read_csv(INBOUND_HISTORY, dtype=str).fillna("")
            if "asof_date" not in inbound_hist.columns:
                _add(rows, "h_inbound_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                inbound_hist_today = inbound_hist[inbound_hist["asof_date"].astype(str) == today].copy()
                if inbound_hist_today.empty:
                    if h_paused:
                        _add(
                            rows,
                            "h_inbound_history_idempotent_today",
                            "ok",
                            "0",
                            f"no rows for {today}; h_cycle_pause_requested=1",
                        )
                    else:
                        _add(rows, "h_inbound_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    inb_dup = int(inbound_hist_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum())
                    inb_status = "fail" if inb_dup > 0 else "ok"
                    _add(rows, "h_inbound_history_idempotent_today", inb_status, str(inb_dup), f"asof_date={today}")
        else:
            _add(rows, "h_inbound_history_idempotent_today", "warn", "missing", f"path {INBOUND_HISTORY}")
    except Exception as exc:
        _add(rows, "h_inbound_history_idempotent_today", "warn", "read_error", str(exc))
    try:
        if REFUND_ADJUSTMENT_HISTORY.exists():
            ra_hist = pd.read_csv(REFUND_ADJUSTMENT_HISTORY, dtype=str).fillna("")
            if "asof_date" not in ra_hist.columns:
                _add(rows, "h_refund_adjustment_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                ra_hist_today = ra_hist[ra_hist["asof_date"].astype(str) == today].copy()
                if ra_hist_today.empty:
                    _add(rows, "h_refund_adjustment_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    ra_dup = int(ra_hist_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum())
                    ra_status = "fail" if ra_dup > 0 else "ok"
                    _add(rows, "h_refund_adjustment_history_idempotent_today", ra_status, str(ra_dup), f"asof_date={today}")
        else:
            _add(rows, "h_refund_adjustment_history_idempotent_today", "warn", "missing", f"path {REFUND_ADJUSTMENT_HISTORY}")
    except Exception as exc:
        _add(rows, "h_refund_adjustment_history_idempotent_today", "warn", "read_error", str(exc))

    _phase1_rollout_checks(rows, now_utc_dt, log)

    # Write output
    df_all = _stabilize_index(pd.DataFrame(rows))
    df_profile = _stabilize_index(df_all.loc[_profile_filter_mask(df_all, profile)].copy())
    if profile == "global":
        df_all = _apply_alert_aging(
            df_all,
            alert_state_path,
            now_utc_dt,
            history_path=alert_history_path,
            recompute_source=str(checklist_path),
            profile=profile,
        )
        df_profile = _stabilize_index(df_all.loc[_profile_filter_mask(df_all, profile)].copy())
    else:
        df_profile = _apply_alert_aging(
            df_profile,
            alert_state_path,
            now_utc_dt,
            history_path=alert_history_path,
            recompute_source=str(checklist_path),
            profile=profile,
        )
    if "status" not in df_profile.columns:
        df_profile["status"] = ""
    if "check" not in df_profile.columns:
        df_profile["check"] = ""
    _write_health_checklist_csv(df_profile, checklist_path)
    if profile == "global":
        _write_cycle_alert_files(df_all)

    # Console summary
    log("writing checklist output")
    row_count = int(df_profile.shape[0])
    print({"status": "success", "rows": row_count, "snapshot": str(checklist_path), "profile": profile})
    try:
        print(df_profile.to_string(index=False))
    except Exception as exc:
        print({"status": "warn", "check": "a015_console_summary_render", "notes": f"{exc.__class__.__name__}: {exc}"})

    # Write health status + optional toast
    status = df_profile["status"].astype(str).str.lower()
    fail_count = int((status == "fail").sum())
    warn_count = int((status == "warn").sum())
    overall = "FAIL" if fail_count > 0 else "WARN" if warn_count > 0 else "OK"
    fail_checks = df_profile.loc[status == "fail", "check"].tolist()
    warn_checks = df_profile.loc[status == "warn", "check"].tolist()
    notes = f"fail={fail_count} warn={warn_count}"
    now_utc = now_utc_dt.isoformat()
    last_status = _read_last_health_status(health_status_path)
    pd.DataFrame(
        [{
            "timestamp_utc": now_utc,
            "status": overall,
            "fail_count": fail_count,
            "warn_count": warn_count,
            "notes": notes,
        }]
    ).to_csv(health_status_path, mode="a", header=False, index=False)

    if overall == "FAIL" and last_status != "FAIL":
        top_fail = ", ".join(fail_checks[:3])
        detail = f"FAIL: {top_fail}" if top_fail else "FAIL detected"
        body = f"{notes}. {detail}"
        if snooze["active"] == "yes":
            reason_suffix = f" reason={snooze['reason']}" if snooze["reason"] else ""
            log(f"toast suppressed by snooze until {snooze['snooze_until_utc']}{reason_suffix}")
        elif no_toast:
            log("toast suppressed by --no-toast")
        else:
            _send_toast("SellerOne Health Check ALERT", body[:240])

    # Non-invasive blueprint validation hook: run after health checklist/status output.
    try:
        validator_script = ROOT / "scripts" / "tools" / "data_blueprint_validator.py"
        subprocess.run(
            [sys.executable, str(validator_script)],
            check=True,
            capture_output=True,
            text=True,
        )
        log("Blueprint validation completed")
    except Exception as exc:
        log("Blueprint validation failed but health check continued")
        log(f"Blueprint validation error: {exc.__class__.__name__}: {exc}")

    # H profile can run in operational mode: keep WARN visible in outputs
    # while allowing rc=0 for WARN-only snapshots.
    if profile == "h":
        exit_on_warn = os.environ.get("H_EXIT_ON_WARN", "1").strip() == "1"
        if fail_count > 0:
            chosen_rc = 2 if exit_on_warn else 1
        elif warn_count > 0:
            chosen_rc = 1 if exit_on_warn else 0
        else:
            chosen_rc = 0
        log(
            "h_exit_policy "
            f"exit_on_warn={1 if exit_on_warn else 0} "
            f"warn_count={warn_count} "
            f"fail_count={fail_count} "
            f"chosen_rc={chosen_rc}"
        )
        if chosen_rc != 0:
            raise SystemExit(chosen_rc)
        return

    # Exit code: 2 if any FAIL, 1 if WARN only, 0 if OK.
    if (status == "fail").any():
        raise SystemExit(2)
    if (status == "warn").any():
        raise SystemExit(1)


def _write_runtime_exception_snapshot(
    exc: Exception,
    *,
    profile: str = "global",
    checklist_path: Path | None = None,
    alert_state_path: Path | None = None,
    alert_history_path: Path | None = None,
    health_status_path: Path | None = None,
) -> None:
    profile_norm = _normalize_profile(profile)
    checklist = checklist_path or _default_checklist_for_profile(profile_norm)
    alert_state = alert_state_path or _default_alert_state_for_profile(profile_norm)
    alert_history = alert_history_path or _default_alert_history_for_profile(profile_norm)
    health_status = health_status_path or _default_health_status_for_profile(profile_norm)
    now_utc_dt = datetime.now(timezone.utc)
    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    tb_text = tb_text.strip()
    top = traceback.extract_tb(exc.__traceback__)[-1] if exc.__traceback__ else None
    top_location = ""
    if top is not None:
        top_location = f"{top.filename}:{top.lineno}:{top.name}"
    note_parts = [f"{exc.__class__.__name__}: {exc}"]
    if top_location:
        note_parts.append(f"location={top_location}")
    if tb_text:
        note_parts.append(f"traceback={tb_text}")
    notes = " | ".join(note_parts)
    notes = notes.replace("\r", " ").replace("\n", " ").strip()[:16000]
    rows = [
        {
            "check": "a015_runtime_exception",
            "status": "fail",
            "value": "1",
            "notes": notes,
        }
    ]
    df_out = pd.DataFrame(rows)
    try:
        OUT.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        checklist.parent.mkdir(parents=True, exist_ok=True)
        alert_state.parent.mkdir(parents=True, exist_ok=True)
        alert_history.parent.mkdir(parents=True, exist_ok=True)
        health_status.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    # Split profile diagnostics: keep full traceback in a dedicated artifact.
    if profile_norm in {"a", "b", "e", "h"}:
        try:
            A015_SPLIT_RUNTIME_EXCEPTION_PATH.parent.mkdir(parents=True, exist_ok=True)
            A015_SPLIT_RUNTIME_EXCEPTION_PATH.write_text(
                "\n".join(
                    [
                        f"timestamp_utc={now_utc_dt.isoformat()}",
                        f"profile={profile_norm}",
                        f"exception={exc.__class__.__name__}: {exc}",
                        f"location={top_location or 'unknown'}",
                        "",
                        tb_text or "(no traceback captured)",
                    ]
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    try:
        df_out = _apply_alert_aging(df_out, alert_state, now_utc_dt, history_path=alert_history)
    except Exception:
        pass

    try:
        _write_health_checklist_csv(df_out, checklist)
    except Exception:
        pass
    try:
        if profile_norm == "global":
            _write_cycle_alert_files(df_out)
    except Exception:
        pass

    try:
        if not health_status.exists():
            pd.DataFrame(columns=["timestamp_utc", "status", "fail_count", "warn_count", "notes"]).to_csv(
                health_status, index=False
            )
        pd.DataFrame(
            [
                {
                    "timestamp_utc": now_utc_dt.isoformat(),
                    "status": "FAIL",
                    "fail_count": 1,
                    "warn_count": 0,
                    "notes": "runtime_exception",
                }
            ]
        ).to_csv(health_status, mode="a", header=False, index=False)
    except Exception:
        pass

    print(
        {
            "status": "fail",
            "check": "a015_runtime_exception",
            "profile": profile_norm,
            "snapshot": str(checklist),
            "traceback_path": str(A015_SPLIT_RUNTIME_EXCEPTION_PATH)
            if profile_norm in {"a", "b", "e", "h"}
            else "",
            "notes": notes,
        }
    )


def _run_main_fail_closed(main_fn) -> int:
    try:
        main_fn()
        return 0
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 1 if code else 0
    except Exception as exc:
        runtime = _resolve_runtime_paths(_parse_cli_args(strict=False))
        _write_runtime_exception_snapshot(
            exc,
            profile=str(runtime["profile"]),
            checklist_path=Path(runtime["checklist_path"]),
            alert_state_path=Path(runtime["alert_state_path"]),
            alert_history_path=Path(runtime["alert_history_path"]),
            health_status_path=Path(runtime["health_status_path"]),
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(_run_main_fail_closed(main))

