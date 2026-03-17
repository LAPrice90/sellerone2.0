from __future__ import annotations

import argparse
import atexit
import contextlib
import csv
import faulthandler
import importlib
import io
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

try:
    from scripts.core.run_manifest import (
        append_step,
        finalize_manifest,
        new_manifest,
        utc_now_iso,
        write_manifest,
    )
except ModuleNotFoundError:
    from core.run_manifest import (
        append_step,
        finalize_manifest,
        new_manifest,
        utc_now_iso,
        write_manifest,
    )
try:
    from scripts.core.script_locator import resolve_script_path
except ModuleNotFoundError:
    from core.script_locator import resolve_script_path
try:
    from scripts.core.out_paths import resolve_compat_path
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path

from scripts.h.h_head_boundaries import load_head_boundaries
from scripts.h.h_lab_cohort import load_active_lab_skus
from scripts.h.h_probe_logs import append_probe_events, append_probe_responses, initialize_probe_logs, load_probe_event_log
from scripts.h.h_supervisor_tactical_rules import load_active_supervisor_tactical_rules
try:
    from scripts.h.h_floor_policy import cogs_cost_from_exvat, gross_from_exvat, load_h_floor_vat_policy
except ModuleNotFoundError:
    from scripts.h.h_floor_policy import cogs_cost_from_exvat, gross_from_exvat, load_h_floor_vat_policy
try:
    from scripts.h.h_floor_truth import (
        HFloorContext,
        append_h_floor_trace_rows,
        build_h_floor_trace_row,
        compute_h_floor_for_sku,
        has_blocking_reason_codes,
        load_h_floor_context,
    )
except ModuleNotFoundError:
    from scripts.h.h_floor_truth import (
        HFloorContext,
        append_h_floor_trace_rows,
        build_h_floor_trace_row,
        compute_h_floor_for_sku,
        has_blocking_reason_codes,
        load_h_floor_context,
    )
try:
    from scripts.h.h_suppression_truth import load_latest_suppression_truth, resolve_unified_truth
except ModuleNotFoundError:
    from h.h_suppression_truth import load_latest_suppression_truth, resolve_unified_truth

try:
    from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing, require_env
    from scripts.api.get_listing_item_price import run_own_offer_price_lookup
    from scripts.api.get_pricing import run_market_context_lookup_with_offers
    from scripts.api.spapi_owner import SpApiCallContext, spapi_get, spapi_patch_json
except ModuleNotFoundError:
    from api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing, require_env
    from api.get_listing_item_price import run_own_offer_price_lookup
    from api.get_pricing import run_market_context_lookup_with_offers
    from api.spapi_owner import SpApiCallContext, spapi_get, spapi_patch_json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DATA = ROOT / "data"
LOCKS_DIR = OUT / "locks"
H_LIVE_DIR = OUT / "systems" / "H" / "live"
H_CYCLE_CURRENT_RUN_PATH = H_LIVE_DIR / "H_cycle_current_run_id.txt"
H_CYCLE_LAST_PUBLISH_RUN_PATH = H_LIVE_DIR / "H_cycle_last_publish_run_id.txt"
H_CYCLE_LAST_PUBLISH_INFO_PATH = H_LIVE_DIR / "H_cycle_last_publish_info.txt"
H_CYCLE_LAST_COMPLETED_RUN_PATH = H_LIVE_DIR / "H_cycle_last_completed_run_id.txt"
H_PUBLISH_GAP_TRACE_PATH = H_LIVE_DIR / "H_publish_gap_trace.txt"
H_PHASE1_INTEL_PROGRESS_LOG_PATH = H_LIVE_DIR / "phase1_intel.progress.log"
H_RUN_IN_PROGRESS_PATH = H_LIVE_DIR / "H_run_in_progress.txt"
H_LAST_FINALIZED_RUN_ID_PATH = H_LIVE_DIR / "H_last_finalized_run_id.txt"
H_UNFINALIZED_EXIT_PATH = H_LIVE_DIR / "H_unfinalized_exit.json"
H_ATEXIT_TRACE_PATH = H_LIVE_DIR / "H_ATEXIT_TRACE.log"
H_PARENT_TRACE_PATH = H_LIVE_DIR / "H_parent_trace.log"
H_PARENT_FAULT_TRACE_PATH = H_LIVE_DIR / "H_parent_fault_trace.log"
H_PHASE1_INTEL_WAIT_STATE_GLOB = "phase1_intel_wait.*.json"
H_BATCH_STATE_PATH = H_LIVE_DIR / "H_batch_state.json"
H_BATCH_STAGE_DIR_PATH = H_LIVE_DIR / "H_batch_stage_dir.txt"
H_RUNTIME_STATUS_PATH = H_LIVE_DIR / "H_runtime_status.json"
H_RUNTIME_STATUS_TEXT_PATH = H_LIVE_DIR / "H_runtime_status.txt"
H_RUNTIME_PHASE_PATH = H_LIVE_DIR / "H_pricing_cycle.PHASE.txt"
H_RESTART_DRAIN_READY_PATH = H_LIVE_DIR / "H_restart_drain.ready"
H_RESTART_DRAIN_NOTICE_PREFIX = "H_restart_drain.notice"
H_STAGED_ROOT = OUT / "systems" / "H" / "staged"
LOCK_ARCHIVE_DIR = OUT / "locks" / "archive"
MAINTENANCE_REQUEST_PATH = LOCKS_DIR / "maintenance.requested"
MAINTENANCE_READY_PATH = LOCKS_DIR / "maintenance.ready"
MAINTENANCE_ACTIVE_PATH = LOCKS_DIR / "maintenance.active"

LOCK_PATH = Path(os.environ.get("H_CYCLE_LOCK_PATH", str(H_LIVE_DIR / "H_pricing_cycle.lock")))
LEGACY_LOCK_PATH = OUT / "H_pricing_cycle.lock"
H_WRITE_LEGACY_LOCK = os.environ.get("H_WRITE_LEGACY_LOCK", "1").strip() == "1"
LOG_PATH = Path(os.environ.get("H_PRICING_LOG_PATH", str(H_LIVE_DIR / "H_pricing_cycle.log")))
LEGACY_LOG_PATH = OUT / "H_pricing_cycle.log"
H_CYCLE_LOG_PATH = Path(os.environ.get("H_CYCLE_LOG_PATH", str(H_LIVE_DIR / "H_cycle.log")))
LEGACY_H_CYCLE_LOG_PATH = OUT / "H_cycle.log"
STATE_PATH = Path(os.environ.get("H_PRICING_STATE_PATH", str(H_LIVE_DIR / "h_pricing_cycle_state.json")))
LEGACY_STATE_PATH = OUT / "h_pricing_cycle_state.json"
ACTION_LOG_PATH = OUT / "h_executioner_action_log.csv"
LIVE_TEST_EXEC_LOG_PATH = DATA / "repricing_live_execution_log.csv"
PHASE1_EXECUTION_LOG_PATH = DATA / "execution_log.csv"
H110_SKU_LIFECYCLE_LOG_PATH = H_LIVE_DIR / "h110_sku_lifecycle_log.csv"
H_FLOOR_TRACE_PATH = OUT / "h_floor_truth_trace.csv"
PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH = OUT / "phase1_runtime_floor_snapshot_latest.csv"
PHASE1_FLOOR_TABLE_PATH = OUT / "phase1_floor_table_latest.csv"
SKU_CEILING_EVENTS_PATH = DATA / "sku_ceiling_events.csv"
LISTING_OFFER_SELLER_HISTORY_PATH = OUT / "listing_offer_seller_observation_history.csv"
LISTING_OFFER_HISTORY_PATH = OUT / "listing_offer_history.csv"
SELLER_SNAPSHOT_DEDUP_REPORT_DIR = OUT / "cycle_alerts"
INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
INVENTORY_HISTORY_PATH = OUT / "inventory_history.csv"
INBOUND_HISTORY_PATH = OUT / "inbound_history.csv"
REFUND_ADJUSTMENT_HISTORY_PATH = OUT / "refund_adjustment_history.csv"
KILL_SWITCH_PATH = LOCKS_DIR / "h_pricing_cycle.kill"
SELLER_PROFILE_PATH = OUT / "h_seller_profiles.csv"
SELLER_SOI_PATH = OUT / "h_seller_of_interest.csv"
SELLER_DELTA_PATH = OUT / "h_seller_delta_learning.csv"
SNAPSHOT_REFRESH_SCRIPT = resolve_script_path(ROOT / "scripts", "H001_capture_offer_snapshot.py")

SOURCE = "run_H_pricing_cycle"
OFFICIAL_PILOT_SKU = os.environ.get("H_OFFICIAL_PILOT_SKU", "L1-54EX-56YC").strip() or "L1-54EX-56YC"
SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
TOKEN_COGS_LEDGER_PATH = OUT / "token_cogs_ledger.csv"
TOKEN_LEDGER_COMPAT = resolve_compat_path("token_ledger_live.csv", default_system="B")
TOKEN_LEDGER_PATH = TOKEN_LEDGER_COMPAT.live_path if TOKEN_LEDGER_COMPAT.live_path.exists() else TOKEN_LEDGER_COMPAT.legacy_path
MIN_REFERRAL_FEE_GBP = 0.25
# Terminology: "commission" in this repricer equals Amazon referral fee.
VAT_DEFAULT = 0.2
LISTINGS_ITEMS_READ_MIN_INTERVAL_SEC = max(float(os.environ.get("SPAPI_LISTINGS_ITEMS_MIN_INTERVAL_SEC", "0.25") or "0.25"), 0.0)
LISTINGS_ITEMS_PATCH_MIN_INTERVAL_SEC = max(float(os.environ.get("SPAPI_LISTINGS_PATCH_MIN_INTERVAL_SEC", "0.25") or "0.25"), 0.0)
H_FLOOR_VAT_POLICY = load_h_floor_vat_policy()

MARKETPLACE_CODE_TO_ID = {"UK": "A1F83G8C2ARO7P"}
MARKETPLACE_ID_TO_CODE = {"A1F83G8C2ARO7P": "UK"}
PHASE1_PILOT_TIMEOUT_SECONDS = max(float(os.environ.get("H_PHASE1_PILOT_TIMEOUT_SECONDS", "300") or "300"), 30.0)
PHASE1_PILOT_STALL_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_STALL_TIMEOUT_SECONDS", str(int(PHASE1_PILOT_TIMEOUT_SECONDS))) or str(int(PHASE1_PILOT_TIMEOUT_SECONDS))),
    30.0,
)
PHASE1_PILOT_MAX_TIMEOUT_SECONDS = max(
    float(
        os.environ.get(
            "H_PHASE1_PILOT_MAX_TIMEOUT_SECONDS",
            str(int(max(PHASE1_PILOT_TIMEOUT_SECONDS * 3.0, 900.0))),
        )
        or str(int(max(PHASE1_PILOT_TIMEOUT_SECONDS * 3.0, 900.0)))
    ),
    PHASE1_PILOT_STALL_TIMEOUT_SECONDS + 30.0,
)
PHASE1_PILOT_POST_EXIT_HANDOFF_WAIT_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_POST_EXIT_HANDOFF_WAIT_SECONDS", "240") or "240"),
    0.0,
)
H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS", "240") or "240"),
    60.0,
)
H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS", "240") or "240"),
    60.0,
)
PHASE1_INTEL_TIMEOUT_SECONDS = max(
    float(
        os.environ.get(
            "H_PHASE1_INTEL_TIMEOUT_SECONDS",
            os.environ.get("H_PHASE1_ALIGNMENT_TIMEOUT_SECONDS", "900"),
        )
        or "900"
    ),
    30.0,
)
PHASE1_OBSERVATION_PUBLISH_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_PHASE1_OBSERVATION_PUBLISH_TIMEOUT_SECONDS", "900") or "900"),
    30.0,
)
H_DAILY_MARKET_REPORT_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_DAILY_MARKET_REPORT_TIMEOUT_SECONDS", "600") or "600"),
    30.0,
)
PHASE1_FLOOR_TABLE_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_PHASE1_FLOOR_TABLE_TIMEOUT_SECONDS", "300") or "300"),
    30.0,
)
PHASE1_OBSERVATION_PUBLISH_ENABLED = os.environ.get("H_PHASE1_OBSERVATION_PUBLISH_ENABLED", "1").strip() == "1"
PHASE1_OBSERVATION_SHEET_ID = os.environ.get("H_PHASE1_OBSERVATION_SHEET_ID", "").strip()
PHASE1_OBSERVATION_VIEW_TAB = os.environ.get("H_PHASE1_OBSERVATION_VIEW_TAB", "PRICING_DASHBOARD").strip()
H_PHASE1_PILOT_MODE = os.environ.get("H_PHASE1_PILOT_MODE", "inline").strip().lower() or "inline"
H_PHASE1_INTEL_MODE = os.environ.get("H_PHASE1_INTEL_MODE", "subprocess").strip().lower() or "subprocess"
H_PHASE1_INTEL_ALIGNMENT_MODE = (
    os.environ.get("H_PHASE1_INTEL_ALIGNMENT_MODE", "full_universe").strip().lower() or "full_universe"
)
H_PHASE1_PUBLISH_MODE = os.environ.get("H_PHASE1_PUBLISH_MODE", "inline").strip().lower() or "inline"
H_PHASE1_FLOOR_TABLE_MODE = os.environ.get("H_PHASE1_FLOOR_TABLE_MODE", "inline").strip().lower() or "inline"
H_BISECT_FORCE_INLINE = os.environ.get("H_BISECT_FORCE_INLINE", "0").strip() == "1"
H_STAGE_PROCESS_TREE_SNAPSHOT = os.environ.get("H_STAGE_PROCESS_TREE_SNAPSHOT", "0").strip() == "1"
# Keep runtime floor snapshot always active so observation/publish never runs on stale floor data.
H_PHASE1_RUNTIME_FLOOR_SNAPSHOT_ENABLED = True
H_LOOP_ERROR_SLEEP_SECONDS = max(float(os.environ.get("H_LOOP_ERROR_SLEEP_SECONDS", "30") or "30"), 1.0)
H_STEP_MAX_RETRIES = max(int(float(os.environ.get("H_STEP_MAX_RETRIES", "2") or "2")), 1)
H_STEP_BACKOFF_BASE = max(float(os.environ.get("H_STEP_BACKOFF_BASE", "2") or "2"), 1.0)
H_SPLIT_HEALTH_MODE = os.environ.get("H_SPLIT_HEALTH_MODE", "shadow").strip().lower() or "shadow"
H_SPLIT_CHECKLIST_PATH = Path(
    os.environ.get("H_SPLIT_CHECKLIST_PATH", OUT / "cycle_alerts" / "checklist_H_split.csv")
)
H_PRIMARY_CHECKLIST_PATH = Path(
    os.environ.get("H_PRIMARY_CHECKLIST_PATH", OUT / "cycle_alerts" / "checklist_H.csv")
)
H_RUNTIME_READINESS_PATH = H_LIVE_DIR / "H_runtime_readiness.json"
H_RUNTIME_READINESS_TEXT_PATH = H_LIVE_DIR / "H_runtime_readiness.txt"
H_HEALTH_INTERVAL_SECONDS = max(float(os.environ.get("H_HEALTH_INTERVAL_SECONDS", "900") or "900"), 1.0)
H_HEALTH_FAIL_CLOSED = os.environ.get("H_HEALTH_FAIL_CLOSED", "1").strip() == "1"
# H split health must self-refresh from live artifacts; treat env toggles as non-authoritative.
# Do not run A015 inline from H cycle by default.
# Gate from existing checklist artifacts unless explicitly enabled.
H_HEALTH_RUN_INLINE = os.environ.get("H_HEALTH_RUN_INLINE", "0").strip() == "1"
H_HEALTH_CHECK_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_HEALTH_CHECK_TIMEOUT_SECONDS", "120") or "120"),
    120.0,
)
H_CHECKLIST_MAX_AGE_SECONDS = max(
    float(os.environ.get("H_CHECKLIST_MAX_AGE_SECONDS", "21600") or "21600"),
    60.0,
)
H_EXECUTION_EVIDENCE_MAX_AGE_SECONDS = max(
    float(os.environ.get("H_EXECUTION_EVIDENCE_MAX_AGE_SECONDS", "21600") or "21600"),
    60.0,
)
H_LOCK_STALE_SECONDS = max(float(os.environ.get("H_LOCK_STALE_SECONDS", "600") or "600"), 60.0)
override = os.environ.get("H_LOCK_STALE_SECONDS_OVERRIDE")
if override is not None:
    try:
        H_LOCK_STALE_SECONDS = int(override)
    except Exception:
        pass
SPLIT_SHADOW_COMPARE_PATH = OUT / "cycle_alerts" / "split_shadow_compare.csv"
SPLIT_SHADOW_STATE_PATH = OUT / "cycle_alerts" / "split_shadow_state.json"
SPLIT_SHADOW_COMPARE_FIELDS = [
    "timestamp_utc",
    "cycle_start_utc",
    "cycle",
    "mode_requested",
    "mode_effective",
    "legacy_fail_count",
    "legacy_warn_count",
    "legacy_gate_block",
    "split_fail_count",
    "split_warn_count",
    "split_gate_block",
    "decision_match",
    "h_clean",
    "b_match_streak",
    "h_clean_streak",
    "ready_for_cutover",
    "legacy_source",
    "split_source",
    "notes",
]
STEP_ARTIFACTS = {
    "phase1_snapshot_refresh": ["out/listing_offer_snapshot_latest.csv", "out/listing_offer_seller_snapshot_latest.csv"],
    "phase1_daily_intel_alignment": ["out/phase1_daily_intel_latest.csv"],
    "phase1_build_seller_profiles": ["out/h_seller_profiles.csv", "out/h_seller_of_interest.csv"],
    "resolve_h_split_gate": ["out/cycle_alerts/checklist_H_split.csv", "out/system_health_checklist.csv"],
    "phase1_pilot_step": [
        "data/execution_log.csv",
        "out/systems/H/live/h110_sku_lifecycle_log.csv",
        "out/h_executioner_action_log.csv",
    ],
    "phase1_runtime_floor_snapshot": ["out/phase1_runtime_floor_snapshot_latest.csv"],
    "phase1_floor_table_build": ["out/phase1_floor_table_latest.csv"],
    "phase1_observation_publish": [],
    "legacy_head_step": ["out/h_head_boundaries.csv"],
    "legacy_supervisor_step": ["out/h_supervisor_tactical_rules.csv"],
    "legacy_executioner_step": ["out/h_executioner_action_log.csv"],
}
STAGE_NAMES = (
    "snapshot_refresh",
    "item_offers",
    "phase1_pilot",
    "phase1_intel",
    "phase1_publish",
)
H_BATCH_STATUSES = (
    "started",
    "collect_done",
    "compute_done",
    "validate_done",
    "published",
    "finalized",
    "failed",
)
PHASE1_STAGED_TABLES = (
    "offer_snapshot_facts",
    "offer_variants",
    "sku_daily_intel",
    "sku_ceiling_events",
    "variant_delta_memory",
    "execution_log",
    "decision_log",
    "scenario_rollup",
    "probe_windows",
    "oas_log",
    "daily_intel_refresh_attempts",
    "sku_phase_state",
    "sku_phase_transition_log",
)
_CURRENT_H_RUN_ID = ""
_RUN_CONTEXT: dict[str, str] = {"run_id": ""}
_LAST_TRACE_CHECKPOINT = ""
_FINALIZER_REACHED_RUN_ID = ""
_EXIT_CODE_HINT = ""
_REAL_OS_EXIT = os._exit
_LAST_STAGE_NAME = ""
_RUNTIME_STATUS_CACHE: dict[str, str] = {}
_INTERRUPTION_CLASS_HINT = "0"
_INTERRUPTION_SIGNAL_HINT = ""
_EXIT_CATEGORY_HINT = ""
_ACTIVE_PHASE1_INTEL_BOUNDARY: dict[str, str] = {}
_ACTIVE_PHASE1_INTEL_WAIT: dict[str, str] = {}
_ACTIVE_PHASE1_PILOT_WAIT: dict[str, str] = {}
_PARENT_FAULT_TRACE_FH: io.TextIOWrapper | None = None


def _set_run_context(run_id: str) -> str:
    global _CURRENT_H_RUN_ID
    normalized = _norm(run_id)
    _CURRENT_H_RUN_ID = normalized
    _RUN_CONTEXT["run_id"] = normalized
    return normalized


def _context_run_id() -> str:
    return _norm(_RUN_CONTEXT.get("run_id", "")) or _norm(_CURRENT_H_RUN_ID)


def _phase1_intel_boundary_state_path(run_id: str) -> Path:
    return H_LIVE_DIR / f"phase1_intel_alignment.boundary.{_norm(run_id) or 'unknown'}.json"


def _phase1_intel_wait_state_path(run_id: str) -> Path:
    return H_LIVE_DIR / f"phase1_intel_wait.{_norm(run_id) or 'unknown'}.json"


def _phase1_intel_boundary_is_resolved(status: object) -> bool:
    return _norm(status).lower() in {"resolved_success", "resolved_failure", "timed_out", "killed"}


def _read_phase1_intel_boundary_state(run_id: str) -> dict[str, object]:
    path = _phase1_intel_boundary_state_path(run_id)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_phase1_intel_wait_state(run_id: str) -> dict[str, object]:
    path = _phase1_intel_wait_state_path(run_id)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_phase1_intel_boundary_state(run_id: str, status: str, **fields: object) -> Path:
    normalized_run_id = _norm(run_id) or _context_run_id() or "unknown"
    path = _phase1_intel_boundary_state_path(normalized_run_id)
    payload: dict[str, object] = {}
    existing = _read_phase1_intel_boundary_state(normalized_run_id)
    if existing:
        payload.update(existing)
    payload.update(
        {
            "run_id": normalized_run_id,
            "status": _norm(status),
            "updated_utc": _ts(),
            "owner": "H",
            "owner_pid": os.getpid(),
            "last_trace_checkpoint": _norm(_LAST_TRACE_CHECKPOINT),
            "last_stage_name": _norm(_LAST_STAGE_NAME),
        }
    )
    for key, value in fields.items():
        key_norm = _norm(key)
        if not key_norm:
            continue
        payload[key_norm] = str(value) if value is not None else ""
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    return path


def _write_phase1_intel_wait_state(run_id: str, status: str, **fields: object) -> Path:
    normalized_run_id = _norm(run_id) or _context_run_id() or "unknown"
    path = _phase1_intel_wait_state_path(normalized_run_id)
    payload: dict[str, object] = {}
    existing = _read_phase1_intel_wait_state(normalized_run_id)
    if existing:
        payload.update(existing)
    payload.update(
        {
            "run_id": normalized_run_id,
            "status": _norm(status),
            "updated_utc": _ts(),
            "owner": "H",
            "owner_pid": os.getpid(),
            "last_trace_checkpoint": _norm(_LAST_TRACE_CHECKPOINT),
            "last_stage_name": _norm(_LAST_STAGE_NAME),
        }
    )
    for key, value in fields.items():
        key_norm = _norm(key)
        if not key_norm:
            continue
        # Callers pass cached wait-state payloads that already include run_id/status.
        # Ignore those reserved keys here so positional arguments remain authoritative.
        if key_norm in {"run_id", "status"}:
            continue
        payload[key_norm] = str(value) if value is not None else ""
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    return path


def _phase1_intel_wait_state_fields(fields: dict[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in (fields or {}).items():
        key_norm = _norm(key)
        if not key_norm or key_norm in {"run_id", "status"}:
            continue
        sanitized[key_norm] = value
    return sanitized


def _clear_active_phase1_intel_boundary(run_id: str = "") -> None:
    target_run_id = _norm(run_id) or _norm(_ACTIVE_PHASE1_INTEL_BOUNDARY.get("run_id", ""))
    active_run_id = _norm(_ACTIVE_PHASE1_INTEL_BOUNDARY.get("run_id", ""))
    if target_run_id and active_run_id and target_run_id != active_run_id:
        return
    _ACTIVE_PHASE1_INTEL_BOUNDARY.clear()


def _clear_active_phase1_intel_wait(run_id: str = "") -> None:
    target_run_id = _norm(run_id) or _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("run_id", ""))
    active_run_id = _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("run_id", ""))
    if target_run_id and active_run_id and target_run_id != active_run_id:
        return
    _ACTIVE_PHASE1_INTEL_WAIT.clear()


def _phase1_intel_wait_exit_class(reason: str, *, signal_name: str = "", exit_code: object = "") -> str:
    reason_norm = _norm(reason).lower()
    signal_norm = _norm(signal_name)
    rc_norm = _norm(exit_code)
    if signal_norm or "signal" in reason_norm or "keyboardinterrupt" in reason_norm:
        return "external_interruption"
    if reason_norm.startswith("controlled_shutdown") or (rc_norm == "0" and "boundary_resolution" not in reason_norm):
        return "controlled_shutdown"
    if "atexit_before_boundary_resolution" in reason_norm:
        return "unexpected_disappearance"
    if (
        "hard_exit" in reason_norm
        or "timeout" in reason_norm
        or "failure" in reason_norm
        or "invalid_result" in reason_norm
        or "missing_result" in reason_norm
        or "child_" in reason_norm
        or "systemexit" in reason_norm
        or rc_norm not in {"", "0"}
    ):
        return "handled_failure"
    return "unexpected_disappearance"


def _phase1_intel_wait_window_active() -> bool:
    return (
        _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("run_id", "")) != ""
        and _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("status", "")).lower() == "waiting"
    )


def _enter_phase1_intel_wait_window(
    run_id: str,
    *,
    child_pid: int,
    requested_mode: str,
    effective_mode: str,
    result_path: Path,
    boundary_state_path: Path,
) -> None:
    normalized_run_id = _norm(run_id)
    if not normalized_run_id:
        return
    wait_state_path = _phase1_intel_wait_state_path(normalized_run_id)
    payload = {
        "run_id": normalized_run_id,
        "status": "waiting",
        "wait_enter_utc": _ts(),
        "wait_exit_utc": "",
        "parent_pid": str(os.getpid()),
        "child_pid": str(child_pid),
        "requested_mode": _norm(requested_mode),
        "effective_mode": _norm(effective_mode),
        "result_path": str(result_path),
        "boundary_state_path": str(boundary_state_path),
        "wait_state_path": str(wait_state_path),
        "exit_class": "",
        "exit_reason": "",
        "signal_name": "",
        "last_wait_heartbeat_utc": "",
        "last_progress_tail": _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
        "unexpected_disappearance_if_open": "1",
    }
    _ACTIVE_PHASE1_INTEL_WAIT.clear()
    _ACTIVE_PHASE1_INTEL_WAIT.update(payload)
    _ACTIVE_PHASE1_INTEL_BOUNDARY["wait_state_path"] = str(wait_state_path)
    _write_phase1_intel_wait_state(
        normalized_run_id,
        "waiting",
        **_phase1_intel_wait_state_fields(payload),
    )
    _append_phase1_intel_progress(
        normalized_run_id,
        "wait_window_enter",
        parent_pid=os.getpid(),
        child_pid=child_pid,
        wait_state_path=wait_state_path,
    )


def _heartbeat_phase1_intel_wait_window(
    run_id: str,
    *,
    elapsed_seconds: object,
    progress_tail: str = "",
    checkpoint: str = "",
    **extra_fields: object,
) -> None:
    normalized_run_id = _norm(run_id) or _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("run_id", ""))
    if not normalized_run_id or _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("run_id", "")) != normalized_run_id:
        return
    if _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("status", "")).lower() != "waiting":
        return
    _ACTIVE_PHASE1_INTEL_WAIT["last_wait_heartbeat_utc"] = _ts()
    _ACTIVE_PHASE1_INTEL_WAIT["last_elapsed_seconds"] = _norm(elapsed_seconds)
    if _norm(checkpoint):
        _ACTIVE_PHASE1_INTEL_WAIT["wait_checkpoint"] = _norm(checkpoint)
        _ACTIVE_PHASE1_INTEL_WAIT["wait_checkpoint_utc"] = _ts()
    if _norm(progress_tail):
        _ACTIVE_PHASE1_INTEL_WAIT["last_progress_tail"] = _norm(progress_tail)
    for key, value in extra_fields.items():
        key_norm = _norm(key)
        if not key_norm or key_norm in {"run_id", "status"}:
            continue
        _ACTIVE_PHASE1_INTEL_WAIT[key_norm] = _norm(value) if value is not None else ""
    _write_phase1_intel_wait_state(
        normalized_run_id,
        "waiting",
        **_phase1_intel_wait_state_fields(_ACTIVE_PHASE1_INTEL_WAIT),
    )


def _finalize_phase1_intel_wait_window(
    run_id: str = "",
    *,
    status: str,
    exit_reason: str,
    exit_class: str = "",
    child_rc: object = "",
    signal_name: str = "",
    progress_tail: str = "",
    boundary_status: str = "",
    result_path: object = "",
    force: bool = False,
) -> None:
    normalized_run_id = _norm(run_id) or _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("run_id", ""))
    if not normalized_run_id:
        return
    if _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("run_id", "")) not in {"", normalized_run_id}:
        return
    current_status = _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("status", "")).lower()
    if current_status and current_status != "waiting" and not force:
        return
    payload = dict(_ACTIVE_PHASE1_INTEL_WAIT)
    payload.update(
        {
            "run_id": normalized_run_id,
            "status": _norm(status),
            "wait_exit_utc": _ts(),
            "exit_reason": _norm(exit_reason),
            "exit_class": _norm(exit_class) or _phase1_intel_wait_exit_class(exit_reason, signal_name=signal_name, exit_code=child_rc),
            "child_rc": _norm(child_rc),
            "signal_name": _norm(signal_name),
            "last_progress_tail": _norm(progress_tail) or _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
            "boundary_status": _norm(boundary_status) or _norm(_ACTIVE_PHASE1_INTEL_BOUNDARY.get("status", "")),
        }
    )
    if _norm(result_path):
        payload["result_path"] = _norm(result_path)
    _ACTIVE_PHASE1_INTEL_WAIT.clear()
    _ACTIVE_PHASE1_INTEL_WAIT.update(payload)
    _write_phase1_intel_wait_state(
        normalized_run_id,
        payload["status"],
        **_phase1_intel_wait_state_fields(payload),
    )
    _append_phase1_intel_progress(
        normalized_run_id,
        "wait_window_exit",
        status=payload["status"],
        exit_class=payload["exit_class"],
        exit_reason=payload["exit_reason"],
        child_rc=payload.get("child_rc", ""),
        signal_name=payload.get("signal_name", ""),
    )


def _record_unresolved_phase1_intel_parent_exit(reason: str) -> None:
    active_run_id = _norm(_ACTIVE_PHASE1_INTEL_BOUNDARY.get("run_id", ""))
    run_id = active_run_id or _context_run_id()
    if not run_id:
        return
    _append_h_parent_trace("boundary_parent_exit_record", reason=reason)
    has_active_boundary_for_run = bool(active_run_id) and active_run_id == run_id
    if not has_active_boundary_for_run:
        existing = _read_phase1_intel_boundary_state(run_id)
        existing_status = _norm(existing.get("status", "")).lower() if isinstance(existing, dict) else ""
        if not existing_status or _phase1_intel_boundary_is_resolved(existing_status):
            _append_h_parent_trace(
                "boundary_parent_exit_skip",
                run_id=run_id,
                reason=reason,
                skip_reason="no_active_or_unresolved_boundary_for_run",
            )
            return
    current_status = _norm(_ACTIVE_PHASE1_INTEL_BOUNDARY.get("status", "")).lower()
    if (not current_status) and not has_active_boundary_for_run:
        existing = _read_phase1_intel_boundary_state(run_id)
        current_status = _norm(existing.get("status", "")).lower() if isinstance(existing, dict) else ""
    if _phase1_intel_boundary_is_resolved(current_status):
        return
    fields = dict(_ACTIVE_PHASE1_INTEL_BOUNDARY)
    fields.update(
        {
            "reason": _norm(reason) or "parent_exit_before_resolution",
            "parent_exit_code": _norm(_EXIT_CODE_HINT),
            "progress_tail": _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
            "parent_exited_utc": _ts(),
        }
    )
    path = _write_phase1_intel_boundary_state(run_id, "unresolved_parent_exit", **fields)
    _ACTIVE_PHASE1_INTEL_BOUNDARY["status"] = "unresolved_parent_exit"
    _ACTIVE_PHASE1_INTEL_BOUNDARY["boundary_state_path"] = str(path)
    _finalize_phase1_intel_wait_window(
        run_id,
        status="parent_exit",
        exit_reason=_norm(reason) or "parent_exit_before_boundary_resolution",
        child_rc=_EXIT_CODE_HINT,
        progress_tail=_norm(fields.get("progress_tail", "")),
        boundary_status="unresolved_parent_exit",
        force=True,
    )
    _log(
        "phase1 daily_intel boundary_failure "
        f"reason=parent_exit_before_resolution "
        f"run_id={run_id} "
        f"boundary_state_path={path} "
        f"child_pid={_norm(fields.get('child_pid', ''))} "
        f"progress_tail={_norm(fields.get('progress_tail', ''))}"
    )


def _append_h_atexit_trace(marker: str) -> None:
    try:
        run_id = _context_run_id()
        line = (
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
            f"pid={os.getpid()} "
            f"run_id={_norm(run_id)} "
            f"{_norm(marker)}"
        )
        H_ATEXIT_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with H_ATEXIT_TRACE_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _append_h_parent_trace(event: str, **fields: object) -> None:
    try:
        run_id = _context_run_id()
        parts = [
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            f"pid={os.getpid()}",
            f"ppid={os.getppid()}",
            f"run_id={_norm(run_id)}",
            f"event={_norm(event)}",
        ]
        if _ACTIVE_PHASE1_INTEL_BOUNDARY:
            boundary_status = _norm(_ACTIVE_PHASE1_INTEL_BOUNDARY.get("status", ""))
            if boundary_status:
                parts.append(f"boundary_status={boundary_status}")
            boundary_reason = _norm(
                _ACTIVE_PHASE1_INTEL_BOUNDARY.get("state_reason", _ACTIVE_PHASE1_INTEL_BOUNDARY.get("reason", ""))
            )
            if boundary_reason:
                parts.append(f"boundary_reason={boundary_reason}")
        if _ACTIVE_PHASE1_INTEL_WAIT:
            wait_status = _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("status", ""))
            if wait_status:
                parts.append(f"wait_status={wait_status}")
            wait_checkpoint = _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("wait_checkpoint", ""))
            if wait_checkpoint:
                parts.append(f"wait_checkpoint={wait_checkpoint}")
        if _ACTIVE_PHASE1_PILOT_WAIT:
            pilot_wait_status = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("status", ""))
            if pilot_wait_status:
                parts.append(f"pilot_wait_status={pilot_wait_status}")
            pilot_wait_checkpoint = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("wait_checkpoint", ""))
            if pilot_wait_checkpoint:
                parts.append(f"pilot_wait_checkpoint={pilot_wait_checkpoint}")
            pilot_child_pid = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("child_pid", ""))
            if pilot_child_pid:
                parts.append(f"pilot_child_pid={pilot_child_pid}")
            pilot_last_known_child_state = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("last_known_child_state", ""))
            if pilot_last_known_child_state:
                parts.append(f"pilot_last_known_child_state={pilot_last_known_child_state}")
            pilot_result_exists = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("result_exists", ""))
            if pilot_result_exists:
                parts.append(f"pilot_result_exists={pilot_result_exists}")
            pilot_marker_status = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("marker_status", ""))
            if pilot_marker_status:
                parts.append(f"pilot_marker_status={pilot_marker_status}")
            pilot_result_ok = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("result_ok", ""))
            if pilot_result_ok:
                parts.append(f"pilot_result_ok={pilot_result_ok}")
            pilot_boundary_status = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("boundary_status", ""))
            if pilot_boundary_status:
                parts.append(f"pilot_boundary_status={pilot_boundary_status}")
        for key, value in fields.items():
            key_norm = _norm(key)
            if not key_norm:
                continue
            value_norm = _norm(value)
            if value_norm:
                parts.append(f"{key_norm}={value_norm}")
        H_PARENT_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with H_PARENT_TRACE_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(" ".join(parts) + "\n")
    except Exception:
        pass


def _ensure_parent_fault_trace() -> None:
    global _PARENT_FAULT_TRACE_FH
    if _PARENT_FAULT_TRACE_FH is not None:
        return
    try:
        H_PARENT_FAULT_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PARENT_FAULT_TRACE_FH = H_PARENT_FAULT_TRACE_PATH.open("a", encoding="utf-8", newline="\n")
        faulthandler.enable(file=_PARENT_FAULT_TRACE_FH, all_threads=True)
        _PARENT_FAULT_TRACE_FH.write(
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} pid={os.getpid()} run_id={_context_run_id()} event=fault_handler_enabled\n"
        )
        _PARENT_FAULT_TRACE_FH.flush()
    except Exception:
        _PARENT_FAULT_TRACE_FH = None


def _h_atexit_handler() -> None:
    _append_h_parent_trace("atexit_handler")
    _append_h_atexit_trace("ATEXIT")


def _h_signal_exit_handler(signum: int, _frame: object) -> None:
    global _INTERRUPTION_CLASS_HINT, _INTERRUPTION_SIGNAL_HINT, _EXIT_CATEGORY_HINT
    sig_name = f"SIG{int(signum)}"
    try:
        sig_name = signal.Signals(signum).name
    except Exception:
        pass
    _append_h_parent_trace("signal_exit_handler", signal_name=sig_name)
    _append_h_atexit_trace(sig_name)
    _INTERRUPTION_CLASS_HINT = "1"
    _INTERRUPTION_SIGNAL_HINT = sig_name
    _EXIT_CATEGORY_HINT = "signal_interruption"
    _finalize_phase1_intel_wait_window(
        status="interrupted",
        exit_reason=f"signal_handler:{sig_name}",
        exit_class="external_interruption",
        signal_name=sig_name,
        child_rc=_EXIT_CODE_HINT,
        force=True,
    )
    raise SystemExit(3)


def _h_signal_ignore_handler(signum: int, _frame: object) -> None:
    sig_name = f"SIG{int(signum)}"
    try:
        sig_name = signal.Signals(signum).name
    except Exception:
        pass
    _append_h_parent_trace("signal_ignored", signal_name=sig_name)
    _append_h_atexit_trace(f"IGNORED_{sig_name}")


atexit.register(_h_atexit_handler)
for _sig_name in ("SIGTERM", "SIGINT", "SIGBREAK"):
    _sig = getattr(signal, _sig_name, None)
    if _sig is None:
        continue
    try:
        signal.signal(_sig, _h_signal_exit_handler)
    except Exception:
        continue


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _is_nonfatal_own_offer_lock_contention(error_text: str) -> bool:
    err = _norm(error_text).lower()
    if not err:
        return False
    err_path_norm = err.replace("\\\\", "\\")
    return (
        "own_offer_lookup_failed" in err
        and "acquire_spapi_lock" in err
        and "fileexistserror" in err
        and "out\\locks\\sp" in err_path_norm
    )


def _to_float(value: object) -> float | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        return float(raw)
    except Exception:
        return None


def _to_int(value: object) -> int | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        return int(float(raw))
    except Exception:
        return None


def _safe_int(value: object, default: int = 0) -> int:
    out = _to_int(value)
    return out if out is not None else default


def _normalize_split_mode(value: object, *, default: str = "shadow") -> str:
    raw = _norm(value).lower()
    if raw in {"legacy", "shadow", "split"}:
        return raw
    return default


def _normalize_phase1_mode(value: object, *, default: str = "inline") -> str:
    raw = _norm(value).lower()
    if raw in {"inline", "subprocess"}:
        return raw
    return default


def _env_stage_enabled(name: str) -> bool:
    key = f"H_STAGE_{name.upper()}"
    return os.environ.get(key, "1").strip() == "1"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass
    os.replace(tmp, path)


def _atomic_write_csv(path: Path, frame: pd.DataFrame) -> None:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False)
    _atomic_write_text(path, buffer.getvalue())


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8") as fh:
            return _norm(fh.readline())
    except Exception:
        return ""


def _read_publish_proof_run_id(expected_run_id: str = "") -> str:
    return _read_publish_proof_details(expected_run_id=expected_run_id).get("selected_run_id", "")


def _read_publish_proof_details(expected_run_id: str = "") -> dict[str, str]:
    expected_run_id_norm = _norm(expected_run_id)
    details = {
        "selected_run_id": "",
        "selected_source": "",
        "publish_marker_path": str(H_CYCLE_LAST_PUBLISH_RUN_PATH),
        "publish_marker_run_id": "",
        "publish_info_path": str(H_CYCLE_LAST_PUBLISH_INFO_PATH),
        "publish_info_run_id": "",
        "expected_run_id": expected_run_id_norm,
    }
    details["publish_marker_run_id"] = _read_first_line(H_CYCLE_LAST_PUBLISH_RUN_PATH)
    try:
        if H_CYCLE_LAST_PUBLISH_INFO_PATH.exists():
            with H_CYCLE_LAST_PUBLISH_INFO_PATH.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = str(raw_line or "").strip()
                    if not line or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if _norm(key) == "run_id":
                        details["publish_info_run_id"] = _norm(value)
                        break
    except Exception:
        return details
    marker_run_id = _norm(details["publish_marker_run_id"])
    info_run_id = _norm(details["publish_info_run_id"])
    if expected_run_id_norm:
        if marker_run_id == expected_run_id_norm:
            details["selected_run_id"] = marker_run_id
            details["selected_source"] = "publish_run_file_expected_match"
        elif info_run_id == expected_run_id_norm:
            details["selected_run_id"] = info_run_id
            details["selected_source"] = "publish_info_file_expected_match"
    elif marker_run_id:
        details["selected_run_id"] = marker_run_id
        details["selected_source"] = "publish_run_file"
    elif info_run_id:
        details["selected_run_id"] = info_run_id
        details["selected_source"] = "publish_info_file"
    return details


def _is_publish_completed_status(status: str) -> bool:
    status_norm = _norm(status).lower()
    if status_norm == "ok":
        return True
    if status_norm == "noop":
        return True
    return status_norm.startswith("skipped")


def _is_phase1_intel_completed_status(status: object) -> bool:
    status_norm = _norm(status).lower()
    if status_norm == "ok":
        return True
    return status_norm.startswith("skipped")


def _write_last_publish_marker(*, run_id: str, now_utc: datetime, observation_state: dict[str, str]) -> None:
    status_value = _norm(observation_state.get("phase1_observation_publish_status", "")) or "unknown"
    _atomic_write_text(H_CYCLE_LAST_PUBLISH_RUN_PATH, f"{run_id}\n")
    _atomic_write_text(
        H_CYCLE_LAST_PUBLISH_INFO_PATH,
        (
            f"run_id={run_id}\n"
            f"utc={now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            f"view_tab={_norm(observation_state.get('phase1_observation_publish_view_tab', ''))}\n"
            f"rows={_norm(observation_state.get('phase1_observation_publish_rows', ''))}\n"
            f"status={status_value}\n"
        ),
    )


def _write_completed_marker(run_id: str) -> None:
    _atomic_write_text(H_CYCLE_LAST_COMPLETED_RUN_PATH, f"{run_id}\n")


def _trace_publish_gap(run_id: str, checkpoint: str, **fields: object) -> None:
    global _LAST_TRACE_CHECKPOINT
    # Diagnostic hook: append-only and best-effort, never fatal.
    try:
        H_PUBLISH_GAP_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        parts = [f"{_ts()} run_id={_norm(run_id)} checkpoint={_norm(checkpoint)}"]
        for key, value in fields.items():
            k = _norm(key)
            if not k:
                continue
            v = _norm(value)
            if v:
                parts.append(f"{k}={v}")
        with H_PUBLISH_GAP_TRACE_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(" ".join(parts) + "\n")
        _LAST_TRACE_CHECKPOINT = _norm(checkpoint)
    except Exception:
        pass


def _system_exit_code(exc: BaseException) -> int | None:
    if not isinstance(exc, SystemExit):
        return None
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return int(code)
    return 1


def _promote_zero_exit_without_finalizer(rc: int) -> int:
    safe_rc = int(rc)
    if safe_rc != 0:
        return safe_rc
    run_id = _context_run_id()
    finalized_run_id = _read_first_line(H_LAST_FINALIZED_RUN_ID_PATH)
    if _norm(run_id) and _norm(run_id) != _norm(finalized_run_id):
        _trace_publish_gap(
            run_id,
            "system_exit_zero_promoted_missing_finalizer",
            last_finalized=finalized_run_id,
        )
        _log(
            "FATAL system_exit_zero_promoted_missing_finalizer "
            f"run_id={run_id} "
            f"last_finalized={finalized_run_id}"
        )
        return 3
    return safe_rc


def _write_run_in_progress(run_id: str) -> None:
    _atomic_write_text(H_RUN_IN_PROGRESS_PATH, f"{_norm(run_id)}\n")


def _clear_run_in_progress(run_id: str = "", *, reason: str = "") -> None:
    target_run_id = _norm(run_id) or _context_run_id()
    current_run_id = _read_first_line(H_RUN_IN_PROGRESS_PATH)
    if current_run_id and target_run_id and _norm(current_run_id) != _norm(target_run_id):
        _log(
            "run_in_progress_clear_skip "
            f"current={current_run_id} "
            f"target={target_run_id} "
            f"reason={_norm(reason) or 'run_id_mismatch'}"
        )
        return
    try:
        H_RUN_IN_PROGRESS_PATH.unlink(missing_ok=True)
        _log(
            "run_in_progress_cleared "
            f"run_id={target_run_id or current_run_id} "
            f"reason={_norm(reason) or 'explicit_clear'}"
        )
    except Exception as exc:
        _log(
            "run_in_progress_clear_failed "
            f"run_id={target_run_id or current_run_id} "
            f"reason={_norm(reason) or 'explicit_clear'} "
            f"error={type(exc).__name__}:{exc}"
        )


def _mark_finalizer_reached(run_id: str) -> None:
    global _FINALIZER_REACHED_RUN_ID
    final_run_id = _norm(run_id)
    if not final_run_id:
        return
    stale_foreign, stale_path, stale_run_id = _has_stale_foreign_lock(final_run_id)
    if stale_foreign:
        _log(
            "FATAL finalizer_blocked_stale_lock "
            f"path={stale_path} "
            f"lock_run_id={stale_run_id} "
            f"current_run_id={final_run_id}"
        )
        return
    _atomic_write_text(H_LAST_FINALIZED_RUN_ID_PATH, f"{final_run_id}\n")
    try:
        H_RUN_IN_PROGRESS_PATH.unlink(missing_ok=True)
    except Exception:
        pass
    _FINALIZER_REACHED_RUN_ID = final_run_id


def _write_unfinalized_exit_report() -> None:
    # Crash-safety marker for rc=0 exits that bypass finalizer updates.
    try:
        _append_h_parent_trace("write_unfinalized_exit_report", exit_code=_EXIT_CODE_HINT)
        _record_unresolved_phase1_intel_parent_exit("atexit_before_boundary_resolution")
        run_id = _read_first_line(H_RUN_IN_PROGRESS_PATH)
        if not run_id:
            return
        finalized_run_id = _read_first_line(H_LAST_FINALIZED_RUN_ID_PATH)
        if _norm(run_id) == _norm(finalized_run_id):
            return
        payload = {
            "run_id": _norm(run_id),
            "ts_utc": _ts(),
            "last_trace_checkpoint": _norm(_LAST_TRACE_CHECKPOINT),
            "exit_code": _norm(_EXIT_CODE_HINT),
        }
        H_UNFINALIZED_EXIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        H_UNFINALIZED_EXIT_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


atexit.register(_write_unfinalized_exit_report)


def _guarded_os_exit(code: int = 0) -> None:
    global _EXIT_CODE_HINT
    # Fail-closed for hard exits that bypass return/finalizer flow.
    requested_rc = code
    try:
        rc = int(code)
    except Exception:
        rc = 1
    run_id = _context_run_id()
    finalized_run_id = _read_first_line(H_LAST_FINALIZED_RUN_ID_PATH)
    if rc == 0 and _norm(run_id) and _norm(run_id) != _norm(finalized_run_id):
        _trace_publish_gap(run_id, "os_exit_promoted_missing_finalizer", last_finalized=finalized_run_id)
        rc = 3
    _EXIT_CODE_HINT = str(rc)
    _append_h_parent_trace("guarded_os_exit", requested_rc=requested_rc, forced_rc=rc, finalized_run_id=finalized_run_id)
    _record_unresolved_phase1_intel_parent_exit("hard_exit_before_boundary_resolution")
    _log(
        "FATAL hard_exit "
        "path=run_H_pricing_cycle._guarded_os_exit "
        f"requested_rc={requested_rc!r} "
        f"forced_rc={rc}"
    )
    raise SystemExit(rc)


os._exit = _guarded_os_exit  # type: ignore


def _effective_phase1_mode(value: object) -> str:
    mode = _normalize_phase1_mode(value, default="inline")
    if H_BISECT_FORCE_INLINE:
        return "inline"
    return mode


def _set_active_phase1_pilot_wait(
    *,
    run_id: str,
    status: str,
    wait_checkpoint: str,
    child_pid: object = "",
    detail: str = "",
    last_known_child_state: str = "",
    result_exists: object = "",
    marker_status: str = "",
    result_ok: object = "",
    boundary_status: str = "",
) -> None:
    _ACTIVE_PHASE1_PILOT_WAIT.clear()
    _ACTIVE_PHASE1_PILOT_WAIT.update(
        {
            "run_id": _norm(run_id),
            "status": _norm(status),
            "wait_checkpoint": _norm(wait_checkpoint),
            "child_pid": _norm(child_pid),
            "detail": _norm(detail),
            "last_known_child_state": _norm(last_known_child_state),
            "result_exists": _norm(result_exists),
            "marker_status": _norm(marker_status),
            "result_ok": _norm(result_ok),
            "boundary_status": _norm(boundary_status),
            "updated_utc": _ts(),
        }
    )


def _clear_active_phase1_pilot_wait() -> None:
    _ACTIVE_PHASE1_PILOT_WAIT.clear()


def _resolve_cycle_run_id(now_utc: datetime) -> str:
    forced = _norm(os.environ.get("H_CYCLE_EXPECTED_RUN_ID", ""))
    if forced and re.fullmatch(r"\d{8}T\d{6}Z", forced):
        return forced
    if forced:
        _log(f"cycle_run_id override ignored invalid_value={forced!r}")
    return now_utc.strftime("%Y%m%dT%H%M%SZ")


def _stage_context_line(*, stage: str, run_id: str) -> str:
    return (
        f"utc={_ts()} "
        f"pid={os.getpid()} "
        f"stage={stage} "
        f"run_id={run_id} "
        f"pilot_mode={_effective_phase1_mode(H_PHASE1_PILOT_MODE)} "
        f"intel_mode={_effective_phase1_mode(H_PHASE1_INTEL_MODE)} "
        f"publish_mode={_effective_phase1_mode(H_PHASE1_PUBLISH_MODE)} "
        f"bisect_force_inline={'1' if H_BISECT_FORCE_INLINE else '0'}"
    )


def _write_process_tree_snapshot(*, stage: str, phase: str, run_id: str) -> None:
    if not H_STAGE_PROCESS_TREE_SNAPSHOT:
        return
    path = H_LIVE_DIR / f"process_tree.{stage}.{phase}.txt"
    header = _stage_context_line(stage=stage, run_id=run_id)
    lines = [header]
    try:
        if os.name == "nt":
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' } | "
                "Select-Object ProcessId,ParentProcessId,CommandLine | Format-List",
            ]
        else:
            cmd = ["ps", "-ef"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)
        lines.append(f"cmd={' '.join(cmd)}")
        lines.append("--- stdout ---")
        lines.append(_norm(proc.stdout))
        lines.append("--- stderr ---")
        lines.append(_norm(proc.stderr))
        lines.append(f"rc={proc.returncode}")
    except subprocess.TimeoutExpired:
        lines.append("process_tree_capture_error=TimeoutExpired:subprocess timed out after 5s")
    except Exception as exc:
        lines.append(f"process_tree_capture_error={type(exc).__name__}:{exc}")
    _atomic_write_text(path, "\n".join(lines).strip() + "\n")


def _stage_enter(*, stage: str, run_id: str) -> float:
    global _LAST_STAGE_NAME
    _LAST_STAGE_NAME = _norm(stage)
    _touch_lock_heartbeat()
    _write_runtime_status("RUNNING", run_id=run_id, stage=stage, detail="stage_enter")
    _atomic_write_text(H_LIVE_DIR / f"STAGE_ENTER.{stage}.txt", _stage_context_line(stage=stage, run_id=run_id) + "\n")
    _write_process_tree_snapshot(stage=stage, phase="enter", run_id=run_id)
    _log(f"H_RUN_ID={run_id} stage={stage}")
    _log(f"stage {stage} enter")
    return time.monotonic()


def _stage_exit(*, stage: str, run_id: str, started: float, rc: str, note: str = "") -> None:
    _touch_lock_heartbeat()
    elapsed = max(time.monotonic() - started, 0.0)
    detail = "stage_exit"
    if note:
        detail = f"{detail}:{note}"
    _write_runtime_status("RUNNING", run_id=run_id, stage=stage, detail=detail)
    extra = f" rc={rc} duration_s={_fmt(_r2(elapsed))}"
    if note:
        extra = f"{extra} note={note}"
    _atomic_write_text(
        H_LIVE_DIR / f"STAGE_EXIT.{stage}.txt",
        _stage_context_line(stage=stage, run_id=run_id) + extra + "\n",
    )
    _write_process_tree_snapshot(stage=stage, phase="exit", run_id=run_id)
    _log(f"stage {stage} exit rc={rc} duration_s={_fmt(_r2(elapsed))}{' note=' + note if note else ''}")


def _mtime_seconds(path: Path) -> float | None:
    try:
        if not path.exists():
            return None
        return float(path.stat().st_mtime)
    except Exception:
        return None


def _checklist_counts(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    fail = 0
    warn = 0
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = _norm(row.get("status", "")).lower()
                if status == "fail":
                    fail += 1
                elif status == "warn":
                    warn += 1
    except Exception:
        return None
    return fail, warn


def _tail_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        if not lines:
            return ""
        return lines[-1].strip()
    except Exception:
        return ""


def _checklist_snapshot_utc(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return datetime.utcfromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""


def _choose_h_gate_checklist_path() -> tuple[Path, str]:
    split_exists = H_SPLIT_CHECKLIST_PATH.exists()
    primary_exists = H_PRIMARY_CHECKLIST_PATH.exists()
    # In production mode H reuses existing health artifacts; use fresh primary checklist as authority.
    if not H_HEALTH_RUN_INLINE and primary_exists:
        return H_PRIMARY_CHECKLIST_PATH, "primary_checklist_h"
    if split_exists:
        return H_SPLIT_CHECKLIST_PATH, "split_checklist_h"
    if primary_exists:
        return H_PRIMARY_CHECKLIST_PATH, "primary_checklist_h"
    return H_SPLIT_CHECKLIST_PATH, "fallback_split_missing"


def _file_age_seconds(path: Path, now_utc: datetime) -> float | None:
    try:
        if not path.exists():
            return None
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return max((now_utc - mtime).total_seconds(), 0.0)
    except Exception:
        return None


def _readiness_seller_snapshot_status(*, run_id: str, item_offers_enabled: bool) -> tuple[str, int | None]:
    run_scoped = OUT / "snapshots" / "H" / _norm(run_id) / "listing_offer_seller_snapshot.csv"
    if not run_scoped.exists():
        if item_offers_enabled:
            return "missing_unexpected", None
        return "missing_expected_item_offers_skipped", None
    rows = 0
    try:
        with run_scoped.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for _ in reader:
                rows += 1
    except Exception:
        return "read_error", None
    if rows > 0:
        return "present", rows
    if item_offers_enabled:
        return "empty_unexpected", 0
    return "empty_expected_item_offers_skipped", 0


def _write_runtime_readiness(
    *,
    run_id: str,
    manifest_final_state: str,
    item_offers_enabled: bool,
    now_utc: datetime,
) -> None:
    checklist_path, checklist_source = _choose_h_gate_checklist_path()
    checklist_counts = _checklist_counts(checklist_path)
    checklist_age = _file_age_seconds(checklist_path, now_utc)
    checklist_fresh = bool(checklist_age is not None and checklist_age <= H_CHECKLIST_MAX_AGE_SECONDS)
    checklist_readable = checklist_counts is not None

    execution_age = _file_age_seconds(PHASE1_EXECUTION_LOG_PATH, now_utc)
    execution_fresh = bool(execution_age is not None and execution_age <= H_EXECUTION_EVIDENCE_MAX_AGE_SECONDS)
    execution_has_rows = False
    execution_rows_today = 0
    try:
        if PHASE1_EXECUTION_LOG_PATH.exists():
            with PHASE1_EXECUTION_LOG_PATH.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    execution_has_rows = True
                    if _norm(row.get("event_ts_utc", "")).startswith(now_utc.strftime("%Y-%m-%d")):
                        execution_rows_today += 1
    except Exception:
        execution_has_rows = False
        execution_rows_today = 0

    h110_age = _file_age_seconds(H110_SKU_LIFECYCLE_LOG_PATH, now_utc)
    h110_fresh = bool(h110_age is not None and h110_age <= H_EXECUTION_EVIDENCE_MAX_AGE_SECONDS)
    h110_finish_rows_today = 0
    try:
        if H110_SKU_LIFECYCLE_LOG_PATH.exists():
            with H110_SKU_LIFECYCLE_LOG_PATH.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if _norm(row.get("event", "")).lower() != "finish":
                        continue
                    if _norm(row.get("event_ts_utc", "")).startswith(now_utc.strftime("%Y-%m-%d")):
                        h110_finish_rows_today += 1
    except Exception:
        h110_finish_rows_today = 0

    seller_snapshot_status, seller_snapshot_rows = _readiness_seller_snapshot_status(
        run_id=run_id,
        item_offers_enabled=item_offers_enabled,
    )
    seller_snapshot_ok = seller_snapshot_status in {
        "present",
        "empty_expected_item_offers_skipped",
        "missing_expected_item_offers_skipped",
    }
    manifest_completed = _norm(manifest_final_state).lower() == "completed"

    coherent = (
        manifest_completed
        and checklist_readable
        and checklist_fresh
        and execution_fresh
        and execution_has_rows
        and h110_fresh
        and h110_finish_rows_today > 0
        and seller_snapshot_ok
    )
    reasons: list[str] = []
    if not manifest_completed:
        reasons.append("manifest_not_completed")
    if not checklist_readable:
        reasons.append("checklist_unreadable")
    if checklist_readable and not checklist_fresh:
        reasons.append("checklist_stale")
    if not execution_has_rows:
        reasons.append("execution_missing")
    if execution_has_rows and not execution_fresh:
        reasons.append("execution_stale")
    if not h110_fresh:
        reasons.append("h110_lifecycle_stale")
    if h110_finish_rows_today <= 0:
        reasons.append("h110_lifecycle_no_finish_rows_today")
    if not seller_snapshot_ok:
        reasons.append(f"seller_snapshot_{seller_snapshot_status}")

    payload = {
        "utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": _norm(run_id),
        "coherent": "1" if coherent else "0",
        "manifest_final_state": _norm(manifest_final_state).lower(),
        "checklist_path": str(checklist_path),
        "checklist_source": checklist_source,
        "checklist_readable": "1" if checklist_readable else "0",
        "checklist_fresh": "1" if checklist_fresh else "0",
        "checklist_age_seconds": _fmt(_r2(checklist_age)) if checklist_age is not None else "",
        "checklist_fail_count": str(checklist_counts[0]) if checklist_counts is not None else "",
        "checklist_warn_count": str(checklist_counts[1]) if checklist_counts is not None else "",
        "execution_path": str(PHASE1_EXECUTION_LOG_PATH),
        "execution_fresh": "1" if execution_fresh else "0",
        "execution_age_seconds": _fmt(_r2(execution_age)) if execution_age is not None else "",
        "execution_has_rows": "1" if execution_has_rows else "0",
        "execution_rows_today": str(execution_rows_today),
        "h110_lifecycle_path": str(H110_SKU_LIFECYCLE_LOG_PATH),
        "h110_lifecycle_fresh": "1" if h110_fresh else "0",
        "h110_lifecycle_age_seconds": _fmt(_r2(h110_age)) if h110_age is not None else "",
        "h110_lifecycle_finish_rows_today": str(h110_finish_rows_today),
        "seller_snapshot_status": seller_snapshot_status,
        "seller_snapshot_rows": "" if seller_snapshot_rows is None else str(seller_snapshot_rows),
        "item_offers_enabled": "1" if item_offers_enabled else "0",
        "reasons_csv": ",".join(reasons),
    }
    _write_json(H_RUNTIME_READINESS_PATH, payload)
    lines = [
        f"utc={payload['utc']}",
        f"run_id={payload['run_id']}",
        f"coherent={payload['coherent']}",
        f"manifest_final_state={payload['manifest_final_state']}",
        f"checklist_source={payload['checklist_source']}",
        f"checklist_fresh={payload['checklist_fresh']}",
        f"execution_fresh={payload['execution_fresh']}",
        f"execution_rows_today={payload['execution_rows_today']}",
        f"h110_lifecycle_fresh={payload['h110_lifecycle_fresh']}",
        f"h110_lifecycle_finish_rows_today={payload['h110_lifecycle_finish_rows_today']}",
        f"seller_snapshot_status={payload['seller_snapshot_status']}",
        f"item_offers_enabled={payload['item_offers_enabled']}",
        f"reasons_csv={payload['reasons_csv']}",
    ]
    _atomic_write_text(H_RUNTIME_READINESS_TEXT_PATH, "\n".join(lines) + "\n")


def _load_split_shadow_state() -> dict:
    default = {
        "b_match_streak": 0,
        "h_clean_streak": 0,
        "ready_for_cutover": False,
        "updated_utc": "",
    }
    if not SPLIT_SHADOW_STATE_PATH.exists():
        return default
    try:
        payload = json.loads(SPLIT_SHADOW_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default
    if not isinstance(payload, dict):
        return default
    out = default.copy()
    out["b_match_streak"] = _safe_int(payload.get("b_match_streak", 0), 0)
    out["h_clean_streak"] = _safe_int(payload.get("h_clean_streak", 0), 0)
    out["ready_for_cutover"] = bool(payload.get("ready_for_cutover", False))
    out["updated_utc"] = _norm(payload.get("updated_utc", ""))
    return out


def _write_split_shadow_state(state: dict) -> None:
    payload = {
        "b_match_streak": _safe_int(state.get("b_match_streak", 0), 0),
        "h_clean_streak": _safe_int(state.get("h_clean_streak", 0), 0),
        "ready_for_cutover": bool(state.get("ready_for_cutover", False)),
        "updated_utc": _norm(state.get("updated_utc", "")),
    }
    SPLIT_SHADOW_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_SHADOW_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _append_split_shadow_compare(row: dict) -> None:
    SPLIT_SHADOW_COMPARE_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = not SPLIT_SHADOW_COMPARE_PATH.exists() or SPLIT_SHADOW_COMPARE_PATH.stat().st_size == 0
    with SPLIT_SHADOW_COMPARE_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SPLIT_SHADOW_COMPARE_FIELDS)
        if need_header:
            writer.writeheader()
        payload = {k: _norm(row.get(k, "")) for k in SPLIT_SHADOW_COMPARE_FIELDS}
        writer.writerow(payload)


def _effective_h_split_mode() -> str:
    requested = _normalize_split_mode(H_SPLIT_HEALTH_MODE, default="shadow")
    if requested != "shadow":
        return requested
    state = _load_split_shadow_state()
    if bool(state.get("ready_for_cutover", False)):
        return "split"
    return "shadow"


def _update_h_shadow_streak(clean_run: bool) -> dict:
    state = _load_split_shadow_state()
    if clean_run:
        state["h_clean_streak"] = _safe_int(state.get("h_clean_streak", 0), 0) + 1
    else:
        state["h_clean_streak"] = 0
    b_streak = _safe_int(state.get("b_match_streak", 0), 0)
    h_streak = _safe_int(state.get("h_clean_streak", 0), 0)
    ready_before = bool(state.get("ready_for_cutover", False))
    state["ready_for_cutover"] = b_streak >= 10 and h_streak >= 10
    state["updated_utc"] = _ts()
    _write_split_shadow_state(state)
    if state["ready_for_cutover"] and not ready_before:
        _log(
            "split_health ready_for_cutover=true "
            f"(b_match_streak={b_streak} h_clean_streak={h_streak})"
        )
    return state


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _r2(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _round_half_up(value: float, ndigits: int = 2) -> float:
    q = Decimal("1").scaleb(-ndigits)
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def _to_dt(value: object) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return payload if isinstance(payload, dict) else default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _read_state(default: dict) -> dict:
    for path in (STATE_PATH, LEGACY_STATE_PATH):
        payload = _read_json(path, default={})
        if payload:
            return payload
    return default


def _write_state(payload: dict) -> None:
    _write_json(STATE_PATH, payload)
    if LEGACY_STATE_PATH != STATE_PATH:
        _write_json(LEGACY_STATE_PATH, payload)


def _write_runtime_status(
    mode: str,
    *,
    run_id: str = "",
    stage: str = "",
    detail: str = "",
    wake_at_utc: str = "",
    next_due_sku: str = "",
    next_due_seconds: str = "",
    publish_status: str = "",
    error: str = "",
    interruption_class: str = "",
    interruption_signal: str = "",
    exit_category: str = "",
) -> None:
    mode_norm = _norm(mode).upper() or "RUNNING"
    run_norm = _norm(run_id) or _context_run_id()
    stage_norm = _norm(stage) or _norm(_LAST_STAGE_NAME)
    payload = {
        "utc": _ts(),
        "pid": str(os.getpid()),
        "run_id": run_norm,
        "mode": mode_norm,
        "stage": stage_norm,
        "detail": _norm(detail),
        "wake_at_utc": _norm(wake_at_utc),
        "next_due_sku": _norm(next_due_sku),
        "next_due_seconds": _norm(next_due_seconds),
        "publish_status": _norm(publish_status),
        "error": _norm(error),
        "interruption_class": _norm(interruption_class) or _norm(_INTERRUPTION_CLASS_HINT) or "0",
        "interruption_signal": _norm(interruption_signal) or _norm(_INTERRUPTION_SIGNAL_HINT),
        "exit_category": _norm(exit_category) or _norm(_EXIT_CATEGORY_HINT),
    }
    _RUNTIME_STATUS_CACHE.clear()
    _RUNTIME_STATUS_CACHE.update(payload)
    _write_json(H_RUNTIME_STATUS_PATH, payload)
    lines = [
        f"utc={payload['utc']}",
        f"pid={payload['pid']}",
        f"run_id={payload['run_id']}",
        f"mode={payload['mode']}",
        f"stage={payload['stage']}",
    ]
    if payload["detail"]:
        lines.append(f"detail={payload['detail']}")
    if payload["wake_at_utc"]:
        lines.append(f"wake_at_utc={payload['wake_at_utc']}")
    if payload["next_due_sku"]:
        lines.append(f"next_due_sku={payload['next_due_sku']}")
    if payload["next_due_seconds"]:
        lines.append(f"next_due_seconds={payload['next_due_seconds']}")
    if payload["publish_status"]:
        lines.append(f"publish_status={payload['publish_status']}")
    if payload["error"]:
        lines.append(f"error={payload['error']}")
    if payload["interruption_class"]:
        lines.append(f"interruption_class={payload['interruption_class']}")
    if payload["interruption_signal"]:
        lines.append(f"interruption_signal={payload['interruption_signal']}")
    if payload["exit_category"]:
        lines.append(f"exit_category={payload['exit_category']}")
    _atomic_write_text(H_RUNTIME_STATUS_TEXT_PATH, "\n".join(lines) + "\n")
    phase_parts = [payload["mode"]]
    if payload["stage"]:
        phase_parts.append(f"stage={payload['stage']}")
    if payload["detail"]:
        phase_parts.append(f"detail={payload['detail']}")
    if payload["wake_at_utc"]:
        phase_parts.append(f"wake_at_utc={payload['wake_at_utc']}")
    _atomic_write_text(H_RUNTIME_PHASE_PATH, " ".join(phase_parts) + "\n")


def _refresh_runtime_status_heartbeat() -> None:
    if not _RUNTIME_STATUS_CACHE:
        return
    _write_runtime_status(
        _RUNTIME_STATUS_CACHE.get("mode", "RUNNING"),
        run_id=_RUNTIME_STATUS_CACHE.get("run_id", ""),
        stage=_RUNTIME_STATUS_CACHE.get("stage", ""),
        detail=_RUNTIME_STATUS_CACHE.get("detail", ""),
        wake_at_utc=_RUNTIME_STATUS_CACHE.get("wake_at_utc", ""),
        next_due_sku=_RUNTIME_STATUS_CACHE.get("next_due_sku", ""),
        next_due_seconds=_RUNTIME_STATUS_CACHE.get("next_due_seconds", ""),
        publish_status=_RUNTIME_STATUS_CACHE.get("publish_status", ""),
        error=_RUNTIME_STATUS_CACHE.get("error", ""),
        interruption_class=_RUNTIME_STATUS_CACHE.get("interruption_class", ""),
        interruption_signal=_RUNTIME_STATUS_CACHE.get("interruption_signal", ""),
        exit_category=_RUNTIME_STATUS_CACHE.get("exit_category", ""),
    )


def _phase1_execution_log_path() -> Path:
    staged_data_dir = _norm(os.environ.get("PHASE1_DATA_DIR", ""))
    if staged_data_dir:
        return Path(staged_data_dir) / "execution_log.csv"
    return PHASE1_EXECUTION_LOG_PATH


def _h_stage_dir(run_id: str) -> Path:
    safe_run_id = _norm(run_id) or "unknown_run"
    return H_STAGED_ROOT / safe_run_id


def _h_stage_data_dir(run_id: str) -> Path:
    return _h_stage_dir(run_id) / "data"


def _h_stage_lock_path(run_id: str) -> Path:
    return _h_stage_dir(run_id) / "phase1.lock"


def _phase1_stage_env(run_id: str) -> dict[str, str]:
    if not _norm(run_id):
        return {}
    data_dir = _h_stage_data_dir(run_id)
    data_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(H_BATCH_STAGE_DIR_PATH, f"{str(_h_stage_dir(run_id))}\n")
    boundary_state_path = _phase1_intel_boundary_state_path(run_id)
    return {
        "PHASE1_DATA_DIR": str(data_dir),
        "PHASE1_LOCK_PATH": str(_h_stage_lock_path(run_id)),
        "H_PHASE1_INTEL_PROGRESS_PATH": str(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
        "A016_PROGRESS_LOG_PATH": str(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
        "H_RUN_ID": _norm(run_id),
        "A016_BOUNDARY_STATE_PATH": str(boundary_state_path),
    }


def _seed_phase1_staged_outputs_from_live(run_id: str) -> dict[str, str]:
    stage_data_dir = _h_stage_data_dir(run_id)
    stage_data_dir.mkdir(parents=True, exist_ok=True)
    seeded = 0
    for table_name in PHASE1_STAGED_TABLES:
        src = DATA / f"{table_name}.csv"
        dst = stage_data_dir / f"{table_name}.csv"
        if dst.exists() or not src.exists():
            continue
        try:
            shutil.copy2(src, dst)
            seeded += 1
        except Exception:
            continue
    return {
        "phase1_stage_seeded_from_live": str(seeded),
        "phase1_stage_seeded_run_id": _norm(run_id),
    }


def _phase1_staged_precommit_diag(run_id: str) -> dict[str, str]:
    stage_data_dir = _h_stage_data_dir(run_id)
    expected_tables = [str(t) for t in PHASE1_STAGED_TABLES]
    present_tables: list[str] = []
    missing_tables: list[str] = []
    for table_name in expected_tables:
        path = stage_data_dir / f"{table_name}.csv"
        if path.exists():
            present_tables.append(table_name)
        else:
            missing_tables.append(table_name)
    return {
        "staged_dir": str(stage_data_dir),
        "staged_file_count": str(len(present_tables)),
        "expected_tables": "|".join(expected_tables),
        "missing_tables": "|".join(missing_tables) if missing_tables else "none",
    }


def _promote_phase1_staged_outputs(run_id: str) -> dict[str, str]:
    stage_data_dir = _h_stage_data_dir(run_id)
    if not stage_data_dir.exists():
        return {
            "phase1_staged_publish_status": "missing_staged_dir",
            "phase1_staged_publish_files": "0",
        }
    copy_plan: list[tuple[Path, Path, Path]] = []
    for table_name in PHASE1_STAGED_TABLES:
        src = stage_data_dir / f"{table_name}.csv"
        if not src.exists():
            continue
        dst = DATA / f"{table_name}.csv"
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp_dst = dst.with_name(f".{dst.name}.tmp.h_stage.{os.getpid()}.{time.time_ns()}")
        copy_plan.append((src, dst, tmp_dst))
    if not copy_plan:
        return {
            "phase1_staged_publish_status": "missing_staged_files",
            "phase1_staged_publish_files": "0",
        }

    restored = 0
    replaced = 0
    backups: list[tuple[Path, Path]] = []
    backup_dir = H_LIVE_DIR / "tmp_publish_backups" / (_norm(run_id) or "unknown_run")
    backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Pre-copy every staged source into temp target files before commit.
        for src, _dst, tmp_dst in copy_plan:
            shutil.copy2(src, tmp_dst)

        # Commit phase: replace live files and keep backups for rollback.
        for _src, dst, tmp_dst in copy_plan:
            backup_path = backup_dir / f"{dst.name}.bak.{time.time_ns()}"
            if dst.exists():
                shutil.copy2(dst, backup_path)
                backups.append((backup_path, dst))
            os.replace(tmp_dst, dst)
            replaced += 1
    except Exception as exc:
        # Roll back any replaced destinations to keep live set unchanged on failure.
        for backup_path, dst in backups:
            try:
                if backup_path.exists():
                    shutil.copy2(backup_path, dst)
                    restored += 1
            except Exception:
                pass
        return {
            "phase1_staged_publish_status": f"failed:{type(exc).__name__}",
            "phase1_staged_publish_files": str(replaced),
            "phase1_staged_publish_restored_files": str(restored),
        }
    finally:
        for _src, _dst, tmp_dst in copy_plan:
            try:
                tmp_dst.unlink(missing_ok=True)
            except Exception:
                pass
        for backup_path, _dst in backups:
            try:
                backup_path.unlink(missing_ok=True)
            except Exception:
                pass
    return {
        "phase1_staged_publish_status": "ok",
        "phase1_staged_publish_files": str(replaced),
    }


def _publish_phase1_commit(*, run_id: str, now_utc: datetime, observation_state: dict[str, str]) -> dict[str, str]:
    staged_publish_state = _promote_phase1_staged_outputs(run_id)
    if staged_publish_state.get("phase1_staged_publish_status", "") != "ok":
        return staged_publish_state
    _write_last_publish_marker(
        run_id=run_id,
        now_utc=now_utc,
        observation_state=observation_state,
    )
    _write_completed_marker(run_id)
    return staged_publish_state


def _run_item_offers_lookup_guarded(
    *,
    sku_asins: List[tuple[str, str]],
    marketplace_id: str,
    snapshot_ts: str,
    snapshot_date: str,
    run_id: str,
    script_name: str,
) -> tuple[Dict[str, Dict[str, str]], List[Dict[str, str]]]:
    helper_script = resolve_script_path(ROOT / "scripts", "tools/H_item_offers_lookup.py")
    tmp_dir = H_LIVE_DIR / "tmp_item_offers_lookup"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{os.getpid()}.{time.time_ns()}"
    in_path = tmp_dir / f"in.{token}.json"
    out_path = tmp_dir / f"out.{token}.json"
    proc: subprocess.CompletedProcess | None = None
    try:
        _append_h_parent_trace(
            "item_offers_enter",
            run_id=run_id,
            sku_count=str(len(sku_asins)),
            marketplace_id=marketplace_id,
            helper_script=helper_script,
            input_path=in_path,
            output_path=out_path,
        )
        _write_runtime_status("RUNNING", run_id=run_id, stage="item_offers", detail="item_offers_enter")
        in_path.write_text(json.dumps({"sku_asins": sku_asins}, ensure_ascii=True), encoding="utf-8")
        cmd = [
            sys.executable,
            str(helper_script),
            "--input",
            str(in_path),
            "--output",
            str(out_path),
            "--marketplace-id",
            str(marketplace_id),
            "--snapshot-ts",
            str(snapshot_ts),
            "--snapshot-date",
            str(snapshot_date),
            "--run-id",
            str(run_id),
            "--script-name",
            str(script_name),
        ]
        _append_h_parent_trace(
            "item_offers_wait_active",
            run_id=run_id,
            sku_count=str(len(sku_asins)),
            marketplace_id=marketplace_id,
            helper_script=helper_script,
            input_path=in_path,
            output_path=out_path,
            timeout_seconds=str(int(H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS)),
        )
        _write_runtime_status("RUNNING", run_id=run_id, stage="item_offers", detail="item_offers_wait_active")
        proc = _run_subprocess_with_watchdog(
            cmd,
            timeout_seconds=H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS,
            cwd=ROOT,
            log_prefix="snapshot_refresh item_offers",
        )
        if int(proc.returncode) != 0:
            err = _norm(proc.stderr or "") or _norm(proc.stdout or "") or f"rc={proc.returncode}"
            raise RuntimeError(f"item_offers_lookup_failed {err[:400]}")
        payload = _read_json(out_path, default={})
        if not isinstance(payload, dict):
            raise RuntimeError("item_offers_lookup_invalid_output")
        bb_map = payload.get("bb_map", {})
        offer_rows = payload.get("offer_rows", [])
        if not isinstance(bb_map, dict):
            bb_map = {}
        if not isinstance(offer_rows, list):
            offer_rows = []
        out_map: Dict[str, Dict[str, str]] = {}
        for key, value in bb_map.items():
            key_norm = _norm(key).upper()
            if not key_norm or not isinstance(value, dict):
                continue
            out_map[key_norm] = {str(k): _norm(v) for k, v in value.items()}
        out_rows: List[Dict[str, str]] = []
        for row in offer_rows:
            if not isinstance(row, dict):
                continue
            out_rows.append({str(k): _norm(v) for k, v in row.items()})
        _append_h_parent_trace(
            "item_offers_exit_normal",
            run_id=run_id,
            child_rc=str(int(proc.returncode)),
            bb_count=str(len(out_map)),
            offer_row_count=str(len(out_rows)),
            output_path=out_path,
        )
        _write_runtime_status("RUNNING", run_id=run_id, stage="item_offers", detail="item_offers_exit_normal rc=0")
        return out_map, out_rows
    except BaseException as exc:
        error_text = f"{type(exc).__name__}:{exc}"[:400]
        child_rc = ""
        if proc is not None:
            with contextlib.suppress(Exception):
                child_rc = str(int(proc.returncode))
        _append_h_parent_trace(
            "item_offers_abnormal_exit",
            run_id=run_id,
            error_type=type(exc).__name__,
            error=str(exc)[:400],
            child_rc=child_rc,
            sku_count=str(len(sku_asins)),
            marketplace_id=marketplace_id,
            helper_script=helper_script,
            input_path=in_path,
            output_path=out_path,
            output_exists="1" if out_path.exists() else "0",
        )
        _log(
            "snapshot_refresh item_offers abnormal_exit "
            f"error={error_text} "
            f"child_rc={child_rc or '?'} "
            f"helper_script={helper_script} "
            f"output_exists={'1' if out_path.exists() else '0'}"
        )
        _write_runtime_status(
            "ERROR",
            run_id=run_id,
            stage="item_offers",
            detail=f"item_offers_abnormal_exit error={error_text}",
            error="ITEM_OFFERS_ABNORMAL_EXIT",
        )
        raise
    finally:
        try:
            in_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


def _run_own_offer_lookup_guarded(
    *,
    skus: List[str],
    marketplace_id: str,
    run_id: str,
    script_name: str,
) -> Dict[str, Dict[str, str]]:
    if not skus:
        return {}
    helper_script = resolve_script_path(ROOT / "scripts", "tools/H_own_offer_lookup.py")
    marketplace_id_norm = _norm(marketplace_id)
    if not marketplace_id_norm:
        raise RuntimeError("own_offer_lookup_failed missing_marketplace_id")
    tmp_dir = H_LIVE_DIR / "tmp_own_offer_lookup"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{os.getpid()}.{time.time_ns()}"
    in_path = tmp_dir / f"in.{token}.json"
    out_path = tmp_dir / f"out.{token}.json"
    try:
        in_path.write_text(json.dumps({"skus": skus}, ensure_ascii=True), encoding="utf-8")
        cmd = [
            sys.executable,
            str(helper_script),
            "--input",
            str(in_path),
            "--output",
            str(out_path),
            "--marketplace-id",
            marketplace_id_norm,
            "--run-id",
            str(run_id),
            "--script-name",
            str(script_name),
        ]
        _log(
            "snapshot_refresh own_offer_lookup launch "
            f"helper={helper_script} "
            f"sku_count={len(skus)} "
            f"marketplace_id={marketplace_id_norm} "
            f"cmd={' '.join(str(part) for part in cmd)}"
        )
        proc = _run_subprocess_with_watchdog(
            cmd,
            timeout_seconds=H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS,
            cwd=ROOT,
            log_prefix="snapshot_refresh own_offer_lookup",
            heartbeat_every_seconds=5.0,
        )
        if int(proc.returncode) != 0:
            err = _norm(proc.stderr or "") or _norm(proc.stdout or "") or f"rc={proc.returncode}"
            raise RuntimeError(f"own_offer_lookup_failed {err[:400]}")
        payload = _read_json(out_path, default={})
        if not isinstance(payload, dict):
            raise RuntimeError("own_offer_lookup_invalid_output")
        own_map = payload.get("own_map", {})
        if not isinstance(own_map, dict):
            own_map = {}
        out_map: Dict[str, Dict[str, str]] = {}
        for key, value in own_map.items():
            key_norm = _norm(key).upper()
            if not key_norm or not isinstance(value, dict):
                continue
            out_map[key_norm] = {str(k): _norm(v) for k, v in value.items()}
        return out_map
    finally:
        try:
            in_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


def _transition_h_batch_state(run_id: str, status: str, **fields: object) -> None:
    status_norm = _norm(status).lower()
    if status_norm not in H_BATCH_STATUSES:
        raise ValueError(f"unsupported H batch status '{status_norm}'")
    run_norm = _norm(run_id)
    existing = _read_json(H_BATCH_STATE_PATH, default={})
    if _norm(existing.get("run_id", "")) == run_norm and _norm(existing.get("status", "")).lower() == status_norm:
        return
    payload: dict[str, object] = {
        "run_id": run_norm,
        "status": status_norm,
        "updated_utc": _ts(),
    }
    for key, value in fields.items():
        key_norm = _norm(key)
        if not key_norm:
            continue
        payload[key_norm] = _norm(value)
    _write_json(H_BATCH_STATE_PATH, payload)
    _log(
        "h_batch_state_transition "
        f"run_id={run_norm} "
        f"from={_norm(existing.get('status', '')).lower() or 'none'} "
        f"to={status_norm}"
    )


def _lock_paths() -> List[Path]:
    out: List[Path] = [LOCK_PATH]
    if H_WRITE_LEGACY_LOCK and LEGACY_LOCK_PATH != LOCK_PATH:
        out.append(LEGACY_LOCK_PATH)
    return out


def _lock_probe_paths() -> List[Path]:
    out = list(_lock_paths())
    if LEGACY_LOCK_PATH not in out:
        out.append(LEGACY_LOCK_PATH)
    return out


def _log(message: str) -> None:
    line = f"{_ts()} {message}"
    seen: set[Path] = set()
    for path in (LOG_PATH, H_CYCLE_LOG_PATH, LEGACY_LOG_PATH, LEGACY_H_CYCLE_LOG_PATH):
        if path in seen:
            continue
        seen.add(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except BaseException:
            pass
    try:
        print(f"[H_cycle] {message}")
    except BaseException:
        pass


def _write_watchdog_kill_marker(
    *,
    log_prefix: str,
    pid: int,
    elapsed_seconds: float,
    timeout_seconds: float,
    cmd: List[str],
) -> None:
    marker = H_LIVE_DIR / "WATCHDOG_LAST_KILL.txt"
    cmd_text = " ".join(str(part) for part in cmd)
    line = (
        f"utc={_ts()} "
        f"log_prefix={log_prefix or 'subprocess'} "
        f"pid={pid} "
        f"elapsed_seconds={_fmt(_r2(elapsed_seconds))} "
        f"timeout_seconds={int(timeout_seconds)} "
        f"cmd={cmd_text}\n"
    )
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(line, encoding="utf-8")
    except Exception:
        pass


def _write_watchdog_marker(*, name: str, log_prefix: str, details: str) -> None:
    marker = H_LIVE_DIR / name
    line = f"utc={_ts()} log_prefix={log_prefix or 'subprocess'} {details}\n"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(line, encoding="utf-8")
    except Exception:
        pass


def _append_phase1_intel_progress(run_id: str, checkpoint: str, **fields: object) -> None:
    parts = [f"utc={_ts()}", f"run_id={_norm(run_id)}", f"checkpoint={_norm(checkpoint)}"]
    for key, value in fields.items():
        k = _norm(key)
        if not k:
            continue
        parts.append(f"{k}={_norm(value)}")
    line = " ".join(parts) + "\n"
    try:
        H_PHASE1_INTEL_PROGRESS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with H_PHASE1_INTEL_PROGRESS_LOG_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
    except Exception:
        pass


def _pid_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        # Process exists but signal probe is not permitted for this user/context.
        return True
    except Exception:
        pass
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = (result.stdout or "").strip().lower()
            if "no tasks are running" in out:
                return False
            return str(int(pid)) in out
        except Exception:
            return False
    return False


def _parse_lock_pid(payload: str) -> int | None:
    parts = [p.strip() for p in str(payload).split("|") if p.strip()]
    for part in parts:
        if part.startswith("pid="):
            try:
                return int(part.split("=", 1)[1].strip())
            except Exception:
                return None
    return None


def _parse_lock_value(payload: str, key: str) -> str:
    parts = [p.strip() for p in str(payload).split("|") if p.strip()]
    for part in parts:
        if part.startswith(f"{key}="):
            return _norm(part.split("=", 1)[1])
    return ""


def _parse_lock_utc(payload: str, key: str) -> datetime | None:
    parts = [p.strip() for p in str(payload).split("|") if p.strip()]
    for part in parts:
        if not part.startswith(f"{key}="):
            continue
        raw = part.split("=", 1)[1].strip()
        return _to_dt(raw)
    return None


def _lock_is_stale(payload: str, now_utc: datetime) -> bool:
    lock_utc = _parse_lock_utc(payload, "heartbeat") or _parse_lock_utc(payload, "start")
    if lock_utc is None:
        return False
    age = max((now_utc - lock_utc).total_seconds(), 0.0)
    return age >= H_LOCK_STALE_SECONDS


def _lock_age_seconds(payload: str, now_utc: datetime) -> float | None:
    lock_utc = _parse_lock_utc(payload, "heartbeat") or _parse_lock_utc(payload, "start")
    if lock_utc is None:
        return None
    return max((now_utc - lock_utc).total_seconds(), 0.0)


def _read_lock_payload(path: Path) -> tuple[str, str]:
    try:
        return _norm(path.read_text(encoding="utf-8")), ""
    except Exception as exc:
        read_error = f"{type(exc).__name__}:{exc}"
        try:
            raw = path.read_bytes()
        except Exception:
            return "", read_error
        if not raw:
            return "", read_error
        return _norm(raw.decode("utf-8", errors="replace")), read_error


def _archive_lock(path: Path, payload: str, now_utc: datetime, reason: str) -> Path:
    LOCK_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_utc.strftime("%Y%m%dT%H%M%SZ")
    archive = LOCK_ARCHIVE_DIR / f"H.lock.{stamp}"
    suffix = 1
    while archive.exists():
        suffix += 1
        archive = LOCK_ARCHIVE_DIR / f"H.lock.{stamp}.{suffix}"
    try:
        path.rename(archive)
    except Exception:
        archive.write_text(payload + ("\n" if not payload.endswith("\n") else ""), encoding="utf-8")
        path.unlink(missing_ok=True)
    _log(f"stale_lock_archived path={path} archive={archive} reason={reason}")
    return archive


def _has_stale_foreign_lock(current_run_id: str, now_utc: datetime | None = None) -> tuple[bool, str, str]:
    now = now_utc or _utc_now()
    current = _norm(current_run_id)
    for path in _lock_probe_paths():
        if not path.exists():
            continue
        try:
            payload = _norm(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        lock_run_id = _parse_lock_value(payload, "run_id")
        if not lock_run_id or lock_run_id == current:
            continue
        if _lock_is_stale(payload, now):
            return True, str(path), lock_run_id
    return False, "", ""


def _acquire_lock() -> None:
    force = os.environ.get("H_CYCLE_FORCE", "0").strip() == "1"
    now_utc = _utc_now()
    if not force:
        for path in _lock_probe_paths():
            if not path.exists():
                continue
            payload, read_error = _read_lock_payload(path)
            if read_error and not payload:
                # Fail closed if lock contents cannot be inspected.
                raise SystemExit(f"[H_cycle] lock unreadable path={path} error={read_error}")
            pid = _parse_lock_pid(payload)
            stale = _lock_is_stale(payload, now_utc)
            age_seconds = _lock_age_seconds(payload, now_utc)
            lock_run_id = _parse_lock_value(payload, "run_id")
            pid_alive = _pid_alive(pid) if pid is not None else False
            if pid is not None and pid_alive:
                # Strict single-run guarantee: never recover/replace a lock owned by a live process.
                raise SystemExit(f"[H_cycle] lock exists (pid {pid})")
            if stale:
                _archive_lock(
                    path,
                    payload,
                    now_utc,
                    f"heartbeat_older_than_seconds={int(H_LOCK_STALE_SECONDS)} lock_run_id={lock_run_id}",
                )
                continue
            if pid is not None and not pid_alive:
                _archive_lock(
                    path,
                    payload,
                    now_utc,
                    (
                        f"dead_pid lock_run_id={lock_run_id} pid={pid} "
                        f"age_seconds={_fmt(_r2(age_seconds)) if age_seconds is not None else ''}".strip()
                    ),
                )
                continue
            _archive_lock(
                path,
                payload,
                now_utc,
                (
                    f"missing_or_invalid_pid lock_run_id={lock_run_id} "
                    f"age_seconds={_fmt(_r2(age_seconds)) if age_seconds is not None else ''} "
                    f"{f'read_error={read_error}' if read_error else ''}".strip()
                ),
            )
    _write_lock()


def _write_lock(run_id: str = "") -> None:
    now = _ts()
    lock_run_id = _norm(run_id) or _context_run_id()
    payload = f"H|pid={os.getpid()}|run_id={lock_run_id}|start={now}|heartbeat={now}\n"
    for path in _lock_paths():
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(path, payload)


def _touch_lock_heartbeat() -> None:
    now = _ts()
    for path in _lock_probe_paths():
        try:
            if not path.exists():
                continue
            payload = _norm(path.read_text(encoding="utf-8"))
            if not payload:
                continue
            pid = _parse_lock_pid(payload)
            if pid != os.getpid():
                continue
            parts = [p.strip() for p in payload.split("|") if p.strip()]
            if not parts:
                continue
            updated: List[str] = []
            has_heartbeat = False
            for part in parts:
                if part.startswith("heartbeat="):
                    updated.append(f"heartbeat={now}")
                    has_heartbeat = True
                else:
                    updated.append(part)
            if not has_heartbeat:
                updated.append(f"heartbeat={now}")
            _atomic_write_text(path, "|".join(updated) + "\n")
        except Exception:
            continue
    _refresh_runtime_status_heartbeat()


def _ensure_lock_ownership() -> None:
    had_any_lock = False
    stale_pids: List[str] = []
    for path in _lock_probe_paths():
        if not path.exists():
            continue
        had_any_lock = True
        payload, read_error = _read_lock_payload(path)
        if read_error and not payload:
            raise RuntimeError(f"lock unreadable path={path} error={read_error}")
        pid = _parse_lock_pid(payload)
        if pid == os.getpid():
            continue
        if pid is not None and _pid_alive(pid):
            raise RuntimeError(f"lock owned by active pid {pid}")
        path.unlink(missing_ok=True)
        stale_pids.append(str(pid) if pid is not None else "")
    _write_lock()
    if not had_any_lock:
        _log("lock missing - recreated for current process")
    elif stale_pids:
        _log(f"stale lock recovered (prior_pid={','.join([p for p in stale_pids if p])})")


def _archive_lock_for_exit(path: Path, payload: str, run_id: str, rc: str) -> Path:
    LOCK_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _ts().replace("-", "").replace(":", "")
    safe_run_id = _norm(run_id) or "unknown_run"
    safe_rc = _norm(rc) or "unknown"
    archive = LOCK_ARCHIVE_DIR / f"H.lock.{stamp}.{safe_run_id}.rc{safe_rc}"
    suffix = 1
    while archive.exists():
        suffix += 1
        archive = LOCK_ARCHIVE_DIR / f"H.lock.{stamp}.{safe_run_id}.rc{safe_rc}.{suffix}"
    try:
        path.rename(archive)
    except Exception:
        archive.write_text(payload + ("\n" if not payload.endswith("\n") else ""), encoding="utf-8")
        path.unlink(missing_ok=True)
    return archive


def _release_lock(*, rc_hint: str = "", run_id: str = "") -> None:
    rc_value = _norm(rc_hint) or _norm(_EXIT_CODE_HINT) or "0"
    run_value = _norm(run_id) or _context_run_id()
    for path in _lock_probe_paths():
        try:
            if not path.exists():
                continue
            payload = _norm(path.read_text(encoding="utf-8"))
            pid = _parse_lock_pid(payload)
            if pid == os.getpid():
                if rc_value == "0":
                    path.unlink(missing_ok=True)
                    _log(f"lock_released path={path} run_id={run_value} rc={rc_value}")
                else:
                    archived = _archive_lock_for_exit(path, payload, run_value, rc_value)
                    _log(f"lock_archived path={path} archive={archived} run_id={run_value} rc={rc_value}")
                continue
            if pid is None or not _pid_alive(pid):
                path.unlink(missing_ok=True)
        except Exception:
            # Never let cleanup failures on one path skip cleanup on others.
            continue


def _owned_lock_paths_for_current_pid() -> List[Path]:
    owned: List[Path] = []
    current_pid = os.getpid()
    for path in _lock_probe_paths():
        try:
            if not path.exists():
                continue
            payload = _norm(path.read_text(encoding="utf-8"))
            pid = _parse_lock_pid(payload)
            if pid == current_pid:
                owned.append(path)
        except Exception:
            continue
    return owned


def _release_lock_with_report(*, stage: str = "", rc_hint: str = "", run_id: str = "") -> None:
    _release_lock(rc_hint=rc_hint, run_id=run_id)
    owned_after = _owned_lock_paths_for_current_pid()
    stage_value = _norm(stage) or _norm(_LAST_STAGE_NAME) or "unknown"
    rc_value = _norm(rc_hint) or _norm(_EXIT_CODE_HINT) or "0"
    released = "1" if not owned_after else "0"
    _log(f"lock_release_attempt stage={stage_value} rc={rc_value} released={released}")


def _sleep_with_lock_heartbeat(total_seconds: float, *, chunk_seconds: float = 30.0) -> None:
    remaining = max(float(total_seconds), 0.0)
    step = max(float(chunk_seconds), 1.0)
    while remaining > 0:
        _write_lock()
        _refresh_runtime_status_heartbeat()
        snooze = min(step, remaining)
        time.sleep(snooze)
        remaining -= snooze


def _run_with_retries(name: str, fn, *, attempts: int = H_STEP_MAX_RETRIES) -> object:
    max_attempts = max(int(attempts), 1)
    attempt = 0
    while True:
        attempt += 1
        started = time.monotonic()
        try:
            out = fn()
            elapsed = max(time.monotonic() - started, 0.0)
            _log(f"stage={name} attempt={attempt} rc=0 elapsed={_fmt(_r2(elapsed))}")
            return out
        except BaseException as exc:
            elapsed = max(time.monotonic() - started, 0.0)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                _log(
                    f"stage={name} attempt={attempt} rc=1 elapsed={_fmt(_r2(elapsed))} "
                    f"error={type(exc).__name__}:{exc}"
                )
                raise
            _log(
                f"stage={name} attempt={attempt} rc=1 elapsed={_fmt(_r2(elapsed))} "
                f"error={type(exc).__name__}:{exc}"
            )
            if attempt >= max_attempts:
                _log(f"{name} failed after {attempt} attempts")
                raise
            backoff = min(H_STEP_BACKOFF_BASE ** attempt, 60.0)
            _log(
                f"stage={name} attempt={attempt} rc=retry backoff={_fmt(_r2(backoff))} "
                f"next_attempt={attempt + 1}"
            )
            _sleep_with_lock_heartbeat(backoff, chunk_seconds=5.0)


def _kill_switch_active() -> bool:
    if os.environ.get("H_KILL_SWITCH", "0").strip() == "1":
        return True
    return KILL_SWITCH_PATH.exists()


def _restart_drain_requested() -> bool:
    if not MAINTENANCE_REQUEST_PATH.exists():
        return False
    try:
        marker = MAINTENANCE_REQUEST_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    marker_norm = _norm(marker)
    if not marker_norm:
        return False
    return "requested_by=controlled_restart_gate" in marker_norm and "reason=overnight_restart_eval" in marker_norm


def _restart_drain_marker_token() -> str:
    if not MAINTENANCE_REQUEST_PATH.exists():
        return ""
    try:
        return _norm(MAINTENANCE_REQUEST_PATH.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""


def _restart_drain_notice_path(event_key: str) -> Path:
    key = _norm(event_key) or "event"
    key = key.replace("|", "_").replace(" ", "_")
    return H_LIVE_DIR / f"{H_RESTART_DRAIN_NOTICE_PREFIX}.{key}.txt"


def _log_restart_drain_once(*, event_key: str, message: str) -> None:
    token = _restart_drain_marker_token()
    if not token:
        _log(message)
        return
    notice_path = _restart_drain_notice_path(event_key)
    seen_token = ""
    try:
        seen_token = _norm(notice_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        seen_token = ""
    if seen_token == token:
        return
    _log(message)
    try:
        _atomic_write_text(notice_path, token + "\n")
    except Exception:
        pass


def _write_restart_drain_ready(*, state: str) -> None:
    now = _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = (
        "H_DRAIN_READY"
        f"|pid={os.getpid()}"
        f"|ts={now}"
        f"|state={_norm(state) or 'boundary_wait'}"
    )
    _atomic_write_text(H_RESTART_DRAIN_READY_PATH, payload + "\n")


def _clear_restart_drain_ready() -> None:
    try:
        H_RESTART_DRAIN_READY_PATH.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        for path in H_LIVE_DIR.glob(f"{H_RESTART_DRAIN_NOTICE_PREFIX}.*.txt"):
            path.unlink(missing_ok=True)
    except Exception:
        pass


def _arm_kill_switch(reason: str) -> None:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    KILL_SWITCH_PATH.write_text(f"{_ts()} {reason}\n", encoding="utf-8")
    _log(f"kill_switch armed reason={reason}")


def _ensure_action_log() -> None:
    headers = [
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
    ]
    ACTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ACTION_LOG_PATH.exists():
        with ACTION_LOG_PATH.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(headers)
        return
    try:
        df = pd.read_csv(ACTION_LOG_PATH, dtype=str).fillna("")
    except Exception:
        with ACTION_LOG_PATH.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(headers)
        return
    missing = [c for c in headers if c not in df.columns]
    if not missing:
        return
    for col in missing:
        df[col] = ""
    df = df[headers]
    df.to_csv(ACTION_LOG_PATH, index=False)


def _append_action_log(row: dict) -> None:
    _ensure_action_log()
    existing = pd.read_csv(ACTION_LOG_PATH, dtype=str).fillna("")
    one = pd.DataFrame([row], dtype=str).fillna("")
    for col in existing.columns:
        if col not in one.columns:
            one[col] = ""
    one = one[existing.columns]
    merged = pd.concat([existing, one], ignore_index=True)
    merged.to_csv(ACTION_LOG_PATH, index=False)


def _ensure_live_test_execution_log() -> None:
    headers = [
        "event_ts_utc",
        "sku",
        "state",
        "old_price_gbp",
        "new_price_gbp",
        "write_status",
        "write_error",
        "final_ceiling_landed_gbp",
        "hard_floor_gbp",
        "profit_floor_required_total_gbp",
        "effective_floor_gbp",
        "profit_floor_cogs_exvat_gbp",
        "profit_floor_cogs_total_gbp",
        "reason_codes_json",
    ]
    LIVE_TEST_EXEC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LIVE_TEST_EXEC_LOG_PATH.exists():
        with LIVE_TEST_EXEC_LOG_PATH.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(headers)
        return
    try:
        df = pd.read_csv(LIVE_TEST_EXEC_LOG_PATH, dtype=str).fillna("")
    except Exception:
        with LIVE_TEST_EXEC_LOG_PATH.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(headers)
        return
    missing = [c for c in headers if c not in df.columns]
    if not missing:
        return
    for col in missing:
        df[col] = ""
    df = df[headers]
    df.to_csv(LIVE_TEST_EXEC_LOG_PATH, index=False)


def _append_live_test_execution_log(row: dict) -> None:
    _ensure_live_test_execution_log()
    existing = pd.read_csv(LIVE_TEST_EXEC_LOG_PATH, dtype=str).fillna("")
    one = pd.DataFrame([row], dtype=str).fillna("")
    for col in existing.columns:
        if col not in one.columns:
            one[col] = ""
    one = one[existing.columns]
    merged = pd.concat([existing, one], ignore_index=True)
    merged.to_csv(LIVE_TEST_EXEC_LOG_PATH, index=False)


def _latest_listing_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        raise FileNotFoundError("No listing snapshot found: out/listing_offer_snapshot_YYYY-MM-DD.csv")
    return files[-1]


def _snapshot_age_minutes(timestamp_utc: str, now_utc: datetime) -> float | None:
    ts = _to_dt(timestamp_utc)
    if ts is None:
        return None
    delta = now_utc - ts
    return max(delta.total_seconds() / 60.0, 0.0)


def _active_sku_asin_rows(target_skus: List[str] | None = None) -> List[Dict[str, str]]:
    active: List[str] = []
    merchant_path = OUT / "merchant_listings_latest.csv"
    if merchant_path.exists():
        try:
            m = pd.read_csv(merchant_path, dtype=str).fillna("")
            status = m.get("status", "").astype(str).str.strip().str.lower()
            sku_col = m.get("seller-sku", "").astype(str).str.strip().str.upper()
            active = [s for s in sku_col.loc[status.eq("active")].tolist() if s]
        except Exception:
            active = []
    if not active:
        active = [s.upper() for s in load_active_lab_skus() if str(s).strip()]
    if target_skus:
        target_keys = {str(s or "").strip().upper() for s in target_skus if str(s or "").strip()}
        if target_keys:
            active = [s for s in active if s in target_keys]
    if not active:
        return []
    out: Dict[str, Dict[str, str]] = {}

    if merchant_path.exists():
        try:
            m = pd.read_csv(merchant_path, dtype=str).fillna("")
            status = m.get("status", "").astype(str).str.strip().str.lower()
            scoped = m.loc[status.eq("active")].copy()
            for _, rec in scoped.iterrows():
                sku = _norm(rec.get("seller-sku", "")).upper()
                if not sku or sku not in active:
                    continue
                out[sku] = {
                    "sku": sku,
                    "asin": _norm(rec.get("asin1", "")),
                    "marketplace": "UK",
                    "notes": _norm(rec.get("item-note", "")),
                }
        except Exception:
            pass

    snap_files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if snap_files:
        try:
            snap = pd.read_csv(snap_files[-1], dtype=str).fillna("")
            snap["sku_key"] = snap.get("sku", "").astype(str).str.strip().str.upper()
            for _, rec in snap.loc[snap["sku_key"].isin(active)].iterrows():
                sku = _norm(rec.get("sku", "")).upper()
                if not sku:
                    continue
                out[sku] = {
                    "sku": sku,
                    "asin": _norm(rec.get("asin", "")),
                    "marketplace": _norm(rec.get("marketplace", "")) or "UK",
                    "notes": _norm(rec.get("notes", "")),
                }
        except Exception:
            pass

    training_path = ROOT / "config" / "f_training_set.csv"
    if training_path.exists():
        try:
            t = pd.read_csv(training_path, dtype=str).fillna("")
            t["sku_key"] = t.get("sku", "").astype(str).str.strip().str.upper()
            for _, rec in t.loc[t["sku_key"].isin(active)].iterrows():
                sku = _norm(rec.get("sku", "")).upper()
                if not sku:
                    continue
                prior = out.get(sku, {"sku": sku, "asin": "", "marketplace": "UK", "notes": ""})
                prior["asin"] = prior["asin"] or _norm(rec.get("asin", ""))
                prior["marketplace"] = prior["marketplace"] or _norm(rec.get("marketplace", "")) or "UK"
                prior["notes"] = prior["notes"] or _norm(rec.get("notes", ""))
                out[sku] = prior
        except Exception:
            pass
    return list(out.values())


def _upsert_snapshot_rows(path: Path, rows: pd.DataFrame, key_cols: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            existing = pd.read_csv(path, dtype=str).fillna("")
        except Exception:
            existing = pd.DataFrame(columns=rows.columns)
    else:
        existing = pd.DataFrame(columns=rows.columns)
    for c in rows.columns:
        if c not in existing.columns:
            existing[c] = ""
    existing = existing[rows.columns]

    keys = rows[key_cols].astype(str).agg("||".join, axis=1)
    existing_keys = existing[key_cols].astype(str).agg("||".join, axis=1) if not existing.empty else pd.Series([], dtype=str)
    keep = ~existing_keys.isin(set(keys.tolist())) if not existing.empty else pd.Series([], dtype=bool)
    merged = pd.concat([existing.loc[keep].copy(), rows], ignore_index=True)
    _atomic_write_csv(path, merged)


def _update_latest_snapshot_pointer(snapshot_path: Path, latest_path: Path) -> None:
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = latest_path.with_suffix(latest_path.suffix + f".tmp.{os.getpid()}")
    shutil.copyfile(snapshot_path, temp_path)
    os.replace(temp_path, latest_path)


def _upsert_listing_offer_history_today_partition(snapshot_date: str, snapshot_path: Path) -> Dict[str, str]:
    key_cols = ["asof_date", "marketplace", "sku"]
    result = {
        "history_rows_today": "0",
        "history_dup_groups_today": "0",
        "history_dup_rows_today": "0",
        "snapshot_rows_today": "0",
        "snapshot_dup_groups_today": "0",
        "snapshot_dup_rows_today": "0",
        "history_rewrite_status": "skipped_snapshot_missing",
    }
    if not snapshot_path.exists():
        _log(f"listing_history_partition_rewrite skipped snapshot_missing path={snapshot_path}")
        return result
    try:
        snapshot_df = pd.read_csv(snapshot_path, dtype=str).fillna("")
    except Exception as exc:
        _log(f"listing_history_partition_rewrite error snapshot_read_failed path={snapshot_path} error={exc}")
        result["history_rewrite_status"] = "snapshot_read_failed"
        return result

    for col in key_cols:
        if col not in snapshot_df.columns:
            snapshot_df[col] = ""
    snapshot_df["asof_date"] = snapshot_df["asof_date"].astype(str).str.strip()
    snapshot_today = snapshot_df.loc[snapshot_df["asof_date"].eq(snapshot_date)].copy()
    result["snapshot_rows_today"] = str(len(snapshot_today.index))

    if "timestamp_utc" in snapshot_today.columns:
        snapshot_today["_order_ts"] = pd.to_datetime(snapshot_today["timestamp_utc"], errors="coerce", utc=True)
    else:
        snapshot_today["_order_ts"] = pd.NaT
    snapshot_today["_source_order"] = list(range(len(snapshot_today.index)))

    dup_mask = snapshot_today.duplicated(subset=key_cols, keep=False) if not snapshot_today.empty else pd.Series([], dtype=bool)
    dup_rows = int(dup_mask.sum()) if len(dup_mask.index) else 0
    dup_groups = int(snapshot_today.loc[dup_mask, key_cols].drop_duplicates().shape[0]) if dup_rows else 0
    result["snapshot_dup_groups_today"] = str(dup_groups)
    result["snapshot_dup_rows_today"] = str(dup_rows)

    snapshot_today = snapshot_today.sort_values(
        key_cols + ["_order_ts", "_source_order"],
        ascending=[True, True, True, False, True],
        kind="stable",
    )
    dedup_today = snapshot_today.drop_duplicates(subset=key_cols, keep="first").copy()
    dedup_today = dedup_today.drop(columns=["_order_ts", "_source_order"], errors="ignore")

    history_path = LISTING_OFFER_HISTORY_PATH
    if history_path.exists():
        try:
            history_df = pd.read_csv(history_path, dtype=str).fillna("")
        except Exception:
            history_df = pd.DataFrame(columns=dedup_today.columns)
    else:
        history_df = pd.DataFrame(columns=dedup_today.columns)

    marketplaces_today = {
        _norm(v).upper()
        for v in dedup_today.get("marketplace", pd.Series([], dtype=str)).astype(str).tolist()
        if _norm(v)
    }
    for col in key_cols:
        if col not in history_df.columns:
            history_df[col] = ""
    history_df["asof_date"] = history_df["asof_date"].astype(str).str.strip()
    history_df["marketplace"] = history_df["marketplace"].astype(str).str.strip().str.upper()
    dedup_today["marketplace"] = dedup_today["marketplace"].astype(str).str.strip().str.upper()
    is_today = history_df["asof_date"].eq(snapshot_date)
    if marketplaces_today:
        is_today = is_today & history_df["marketplace"].isin(marketplaces_today)
    history_keep = history_df.loc[~is_today].copy()

    merged_cols = list(history_keep.columns)
    for col in dedup_today.columns:
        if col not in merged_cols:
            merged_cols.append(col)
    history_keep = history_keep.reindex(columns=merged_cols, fill_value="")
    dedup_today = dedup_today.reindex(columns=merged_cols, fill_value="")
    merged = pd.concat([history_keep, dedup_today], ignore_index=True)
    _atomic_write_csv(history_path, merged)

    history_today = merged.loc[merged.get("asof_date", "").astype(str).str.strip().eq(snapshot_date)].copy()
    history_dup_mask = (
        history_today.duplicated(subset=key_cols, keep=False)
        if not history_today.empty
        else pd.Series([], dtype=bool)
    )
    history_dup_rows = int(history_dup_mask.sum()) if len(history_dup_mask.index) else 0
    history_dup_groups = (
        int(history_today.loc[history_dup_mask, key_cols].drop_duplicates().shape[0])
        if history_dup_rows
        else 0
    )
    result["history_rows_today"] = str(len(history_today.index))
    result["history_dup_groups_today"] = str(history_dup_groups)
    result["history_dup_rows_today"] = str(history_dup_rows)
    result["history_rewrite_status"] = "ok"
    _log(
        "listing_history_partition_rewrite "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"snapshot_rows={result['snapshot_rows_today']} "
        f"snapshot_dup_groups={result['snapshot_dup_groups_today']} "
        f"snapshot_dup_rows={result['snapshot_dup_rows_today']} "
        f"history_rows={result['history_rows_today']} "
        f"history_dup_groups={result['history_dup_groups_today']} "
        f"history_dup_rows={result['history_dup_rows_today']} "
        f"history_path={history_path}"
    )
    return result


def _is_artifact_refreshed_in_run(path: Path, refresh_started: datetime) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except Exception as exc:
        return False, f"stat_error:{type(exc).__name__}"
    refreshed = mtime >= (refresh_started - timedelta(seconds=1))
    return refreshed, f"mtime_utc={mtime.strftime('%Y-%m-%dT%H:%M:%SZ')}"


def _rewrite_seller_history_today_partition(snapshot_date: str, snapshot_path: Path) -> Dict[str, str]:
    key_cols = ["asof_date", "marketplace", "sku", "asin", "seller_id"]
    result = {
        "history_rows_today": "0",
        "history_dup_groups_today": "0",
        "history_dup_rows_today": "0",
        "snapshot_rows_today": "0",
        "snapshot_dup_groups_today": "0",
        "snapshot_dup_rows_today": "0",
        "history_rewrite_status": "skipped_snapshot_missing",
    }
    if not snapshot_path.exists():
        _log(f"seller_history_partition_rewrite skipped snapshot_missing path={snapshot_path}")
        return result

    try:
        snapshot_df = pd.read_csv(snapshot_path, dtype=str).fillna("")
    except Exception as exc:
        _log(f"seller_history_partition_rewrite error snapshot_read_failed path={snapshot_path} error={exc}")
        result["history_rewrite_status"] = "snapshot_read_failed"
        return result

    for col in key_cols:
        if col not in snapshot_df.columns:
            snapshot_df[col] = ""
    snapshot_df["asof_date"] = snapshot_df["asof_date"].astype(str).str.strip()
    snapshot_today = snapshot_df.loc[snapshot_df["asof_date"].eq(snapshot_date)].copy()
    result["snapshot_rows_today"] = str(len(snapshot_today.index))

    ts_col = ""
    for candidate in ("observed_at", "scrape_ts", "timestamp_utc"):
        if candidate in snapshot_today.columns:
            ts_col = candidate
            break
    if ts_col:
        snapshot_today["_order_ts"] = pd.to_datetime(snapshot_today.get(ts_col, ""), errors="coerce", utc=True)
    else:
        snapshot_today["_order_ts"] = pd.NaT
    snapshot_today["_source_order"] = list(range(len(snapshot_today.index)))

    dup_mask = snapshot_today.duplicated(subset=key_cols, keep=False) if not snapshot_today.empty else pd.Series([], dtype=bool)
    dup_rows = int(dup_mask.sum()) if len(dup_mask.index) else 0
    dup_groups = (
        int(snapshot_today.loc[dup_mask, key_cols].drop_duplicates().shape[0])
        if dup_rows
        else 0
    )
    result["snapshot_dup_groups_today"] = str(dup_groups)
    result["snapshot_dup_rows_today"] = str(dup_rows)

    snapshot_today = snapshot_today.sort_values(
        key_cols + ["_order_ts", "_source_order"],
        ascending=[True, True, True, True, True, False, True],
        kind="stable",
    )
    dedup_today = snapshot_today.drop_duplicates(subset=key_cols, keep="first").copy()
    dedup_today = dedup_today.drop(columns=["_order_ts", "_source_order"], errors="ignore")

    history_path = LISTING_OFFER_SELLER_HISTORY_PATH
    if history_path.exists():
        try:
            history_df = pd.read_csv(history_path, dtype=str).fillna("")
        except Exception:
            history_df = pd.DataFrame(columns=dedup_today.columns)
    else:
        history_df = pd.DataFrame(columns=dedup_today.columns)

    marketplaces_today = {
        _norm(v).upper()
        for v in dedup_today.get("marketplace", pd.Series([], dtype=str)).astype(str).tolist()
        if _norm(v)
    }
    for col in key_cols:
        if col not in history_df.columns:
            history_df[col] = ""
    history_df["asof_date"] = history_df["asof_date"].astype(str).str.strip()
    history_df["marketplace"] = history_df["marketplace"].astype(str).str.strip().str.upper()
    is_today = history_df["asof_date"].eq(snapshot_date)
    if marketplaces_today:
        is_today = is_today & history_df["marketplace"].isin(marketplaces_today)
    history_keep = history_df.loc[~is_today].copy()

    merged_cols = list(history_keep.columns)
    for col in dedup_today.columns:
        if col not in merged_cols:
            merged_cols.append(col)
    history_keep = history_keep.reindex(columns=merged_cols, fill_value="")
    dedup_today = dedup_today.reindex(columns=merged_cols, fill_value="")
    merged = pd.concat([history_keep, dedup_today], ignore_index=True)
    _atomic_write_csv(history_path, merged)

    history_today = merged.loc[merged.get("asof_date", "").astype(str).str.strip().eq(snapshot_date)].copy()
    history_dup_mask = (
        history_today.duplicated(subset=key_cols, keep=False)
        if not history_today.empty
        else pd.Series([], dtype=bool)
    )
    history_dup_rows = int(history_dup_mask.sum()) if len(history_dup_mask.index) else 0
    history_dup_groups = (
        int(history_today.loc[history_dup_mask, key_cols].drop_duplicates().shape[0])
        if history_dup_rows
        else 0
    )
    result["history_rows_today"] = str(len(history_today.index))
    result["history_dup_groups_today"] = str(history_dup_groups)
    result["history_dup_rows_today"] = str(history_dup_rows)
    result["history_rewrite_status"] = "ok"

    sample_keys = ""
    if dup_rows:
        sample_df = snapshot_today.loc[dup_mask, key_cols].drop_duplicates().head(5)
        sample_keys = "|".join(
            [
                "||".join([_norm(rec.get(col, "")) for col in key_cols])
                for rec in sample_df.to_dict("records")
            ]
        )
    dedup_report_path = SELLER_SNAPSHOT_DEDUP_REPORT_DIR / f"seller_snapshot_dedup_report_{snapshot_date}.csv"
    dedup_report = pd.DataFrame(
        [
            {
                "asof_date": snapshot_date,
                "snapshot_path": str(snapshot_path),
                "snapshot_rows_today": result["snapshot_rows_today"],
                "dup_group_count": result["snapshot_dup_groups_today"],
                "dup_row_count": result["snapshot_dup_rows_today"],
                "history_rows_today": result["history_rows_today"],
                "history_dup_group_count": result["history_dup_groups_today"],
                "history_dup_row_count": result["history_dup_rows_today"],
                "sample_keys": sample_keys,
            }
        ],
        columns=[
            "asof_date",
            "snapshot_path",
            "snapshot_rows_today",
            "dup_group_count",
            "dup_row_count",
            "history_rows_today",
            "history_dup_group_count",
            "history_dup_row_count",
            "sample_keys",
        ],
    )
    _atomic_write_csv(dedup_report_path, dedup_report)
    _log(
        "seller_history_partition_rewrite "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"snapshot_rows={result['snapshot_rows_today']} "
        f"snapshot_dup_groups={result['snapshot_dup_groups_today']} "
        f"snapshot_dup_rows={result['snapshot_dup_rows_today']} "
        f"history_rows={result['history_rows_today']} "
        f"history_dup_groups={result['history_dup_groups_today']} "
        f"history_dup_rows={result['history_dup_rows_today']} "
        f"report_path={dedup_report_path}"
    )
    return result


def _to_int_str(value: object) -> str:
    try:
        return str(int(float(str(value).strip())))
    except Exception:
        return "0"


def _ensure_inventory_snapshot_today(snapshot_date: str, snapshot_ts: str) -> tuple[Path, str]:
    snapshot_path = OUT / f"inventory_snapshot_{snapshot_date}.csv"
    if snapshot_path.exists():
        return snapshot_path, "existing_snapshot"
    if not INVENTORY_SUMMARIES_PATH.exists():
        _log(
            "inventory_snapshot_today_missing "
            f"today_utc={snapshot_date} "
            f"snapshot_path={snapshot_path} "
            f"inventory_summaries_path={INVENTORY_SUMMARIES_PATH}"
        )
        return snapshot_path, "missing"
    try:
        summaries = pd.read_csv(INVENTORY_SUMMARIES_PATH, dtype=str).fillna("")
    except Exception as exc:
        _log(
            "inventory_snapshot_today_read_error "
            f"today_utc={snapshot_date} "
            f"inventory_summaries_path={INVENTORY_SUMMARIES_PATH} "
            f"error={exc}"
        )
        return snapshot_path, "read_error"
    if summaries.empty:
        empty = pd.DataFrame(
            columns=[
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
                "unsellable",
                "researching",
                "reserved_transfers",
                "reserved_processing",
                "reserved_customer",
                "total_quantity",
                "last_updated_time",
                "source",
                "notes",
            ]
        )
        _atomic_write_csv(snapshot_path, empty)
        return snapshot_path, "from_inventory_summaries_empty"

    out_df = pd.DataFrame(index=summaries.index.copy())
    out_df["timestamp_utc"] = snapshot_ts
    out_df["asof_date"] = snapshot_date
    out_df["marketplace"] = "UK"
    out_df["sku"] = summaries.get("seller_sku", "").astype(str).str.strip().str.upper()
    out_df["asin"] = summaries.get("asin", "").astype(str).str.strip()
    out_df["available"] = summaries.get("available", "0").apply(_to_int_str)
    out_df["inbound_working"] = summaries.get("inbound_working", "0").apply(_to_int_str)
    out_df["inbound_shipped"] = summaries.get("inbound_shipped", "0").apply(_to_int_str)
    out_df["inbound_receiving"] = summaries.get("inbound_receiving", "0").apply(_to_int_str)
    out_df["inbound_total"] = (
        pd.to_numeric(out_df["inbound_working"], errors="coerce").fillna(0).astype(int)
        + pd.to_numeric(out_df["inbound_shipped"], errors="coerce").fillna(0).astype(int)
        + pd.to_numeric(out_df["inbound_receiving"], errors="coerce").fillna(0).astype(int)
    ).astype(str)
    out_df["unsellable"] = summaries.get("unsellable", "0").apply(_to_int_str)
    out_df["researching"] = summaries.get("researching", "0").apply(_to_int_str)
    out_df["reserved_transfers"] = summaries.get("reserved_transfers", "0").apply(_to_int_str)
    out_df["reserved_processing"] = summaries.get("reserved_processing", "0").apply(_to_int_str)
    out_df["reserved_customer"] = summaries.get("reserved_customer", "0").apply(_to_int_str)
    out_df["total_quantity"] = summaries.get("total_quantity", "0").apply(_to_int_str)
    out_df["last_updated_time"] = summaries.get("last_updated_time", "").astype(str)
    out_df["source"] = "SPAPI"
    out_df["notes"] = "derived_from_inventory_summaries"
    out_df = out_df.loc[out_df["sku"].ne("")].copy()
    out_df = out_df.drop_duplicates(subset=["asof_date", "sku", "marketplace"], keep="first")
    _atomic_write_csv(snapshot_path, out_df)
    _log(
        "inventory_snapshot_today_materialized "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"rows={len(out_df.index)} "
        f"source_path={INVENTORY_SUMMARIES_PATH}"
    )
    return snapshot_path, "from_inventory_summaries"


def _rewrite_inventory_history_today_partition(snapshot_date: str, snapshot_path: Path) -> Dict[str, str]:
    key_cols = ["asof_date", "sku", "marketplace"]
    result = {
        "snapshot_rows_today": "0",
        "snapshot_dup_groups_today": "0",
        "snapshot_dup_rows_today": "0",
        "history_rows_today": "0",
        "history_dup_groups_today": "0",
        "history_dup_rows_today": "0",
        "history_rewrite_status": "skipped_snapshot_missing",
    }
    if not snapshot_path.exists():
        _log(f"inventory_history_partition_rewrite skipped snapshot_missing path={snapshot_path}")
        return result
    try:
        snapshot_df = pd.read_csv(snapshot_path, dtype=str).fillna("")
    except Exception as exc:
        _log(f"inventory_history_partition_rewrite error snapshot_read_failed path={snapshot_path} error={exc}")
        result["history_rewrite_status"] = "snapshot_read_failed"
        return result
    for col in key_cols:
        if col not in snapshot_df.columns:
            snapshot_df[col] = ""
    snapshot_df["asof_date"] = snapshot_df["asof_date"].astype(str).str.strip()
    snapshot_today = snapshot_df.loc[snapshot_df["asof_date"].eq(snapshot_date)].copy()
    result["snapshot_rows_today"] = str(len(snapshot_today.index))
    if "timestamp_utc" in snapshot_today.columns:
        snapshot_today["_order_ts"] = pd.to_datetime(snapshot_today["timestamp_utc"], errors="coerce", utc=True)
    else:
        snapshot_today["_order_ts"] = pd.NaT
    snapshot_today["_source_order"] = list(range(len(snapshot_today.index)))
    dup_mask = snapshot_today.duplicated(subset=key_cols, keep=False) if not snapshot_today.empty else pd.Series([], dtype=bool)
    dup_rows = int(dup_mask.sum()) if len(dup_mask.index) else 0
    dup_groups = int(snapshot_today.loc[dup_mask, key_cols].drop_duplicates().shape[0]) if dup_rows else 0
    result["snapshot_dup_groups_today"] = str(dup_groups)
    result["snapshot_dup_rows_today"] = str(dup_rows)
    snapshot_today = snapshot_today.sort_values(
        key_cols + ["_order_ts", "_source_order"],
        ascending=[True, True, True, False, True],
        kind="stable",
    )
    dedup_today = snapshot_today.drop_duplicates(subset=key_cols, keep="first").copy()
    dedup_today = dedup_today.drop(columns=["_order_ts", "_source_order"], errors="ignore")

    history_path = INVENTORY_HISTORY_PATH
    if history_path.exists():
        try:
            history_df = pd.read_csv(history_path, dtype=str).fillna("")
        except Exception:
            history_df = pd.DataFrame(columns=dedup_today.columns)
    else:
        history_df = pd.DataFrame(columns=dedup_today.columns)
    for col in key_cols:
        if col not in history_df.columns:
            history_df[col] = ""
    history_df["asof_date"] = history_df["asof_date"].astype(str).str.strip()
    history_df["marketplace"] = history_df["marketplace"].astype(str).str.strip().str.upper()
    dedup_today["marketplace"] = dedup_today["marketplace"].astype(str).str.strip().str.upper()
    marketplaces_today = {
        _norm(v).upper()
        for v in dedup_today.get("marketplace", pd.Series([], dtype=str)).astype(str).tolist()
        if _norm(v)
    }
    is_today = history_df["asof_date"].eq(snapshot_date)
    if marketplaces_today:
        is_today = is_today & history_df["marketplace"].isin(marketplaces_today)
    history_keep = history_df.loc[~is_today].copy()
    merged_cols = list(history_keep.columns)
    for col in dedup_today.columns:
        if col not in merged_cols:
            merged_cols.append(col)
    history_keep = history_keep.reindex(columns=merged_cols, fill_value="")
    dedup_today = dedup_today.reindex(columns=merged_cols, fill_value="")
    merged = pd.concat([history_keep, dedup_today], ignore_index=True)
    _atomic_write_csv(history_path, merged)

    history_today = merged.loc[merged.get("asof_date", "").astype(str).str.strip().eq(snapshot_date)].copy()
    history_dup_mask = (
        history_today.duplicated(subset=key_cols, keep=False)
        if not history_today.empty
        else pd.Series([], dtype=bool)
    )
    history_dup_rows = int(history_dup_mask.sum()) if len(history_dup_mask.index) else 0
    history_dup_groups = (
        int(history_today.loc[history_dup_mask, key_cols].drop_duplicates().shape[0])
        if history_dup_rows
        else 0
    )
    result["history_rows_today"] = str(len(history_today.index))
    result["history_dup_groups_today"] = str(history_dup_groups)
    result["history_dup_rows_today"] = str(history_dup_rows)
    result["history_rewrite_status"] = "ok"

    report_path = OUT / "cycle_alerts" / f"inventory_snapshot_dedup_report_{snapshot_date}.csv"
    report = pd.DataFrame(
        [
            {
                "asof_date": snapshot_date,
                "snapshot_path": str(snapshot_path),
                "snapshot_rows_today": result["snapshot_rows_today"],
                "snapshot_dup_group_count": result["snapshot_dup_groups_today"],
                "snapshot_dup_row_count": result["snapshot_dup_rows_today"],
                "history_rows_today": result["history_rows_today"],
                "history_dup_group_count": result["history_dup_groups_today"],
                "history_dup_row_count": result["history_dup_rows_today"],
            }
        ]
    )
    _atomic_write_csv(report_path, report)
    _log(
        "inventory_history_partition_rewrite "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"snapshot_rows={result['snapshot_rows_today']} "
        f"snapshot_dup_groups={result['snapshot_dup_groups_today']} "
        f"snapshot_dup_rows={result['snapshot_dup_rows_today']} "
        f"history_rows={result['history_rows_today']} "
        f"history_dup_groups={result['history_dup_groups_today']} "
        f"history_dup_rows={result['history_dup_rows_today']} "
        f"report_path={report_path}"
    )
    return result


def _ensure_inbound_snapshot_today(snapshot_date: str, snapshot_ts: str) -> tuple[Path, str]:
    snapshot_path = OUT / f"inbound_snapshot_{snapshot_date}.csv"
    if snapshot_path.exists():
        return snapshot_path, "existing_snapshot"
    inventory_snapshot_path = OUT / f"inventory_snapshot_{snapshot_date}.csv"
    if not inventory_snapshot_path.exists():
        inventory_snapshot_path, _ = _ensure_inventory_snapshot_today(snapshot_date, snapshot_ts)
    if not inventory_snapshot_path.exists():
        _log(
            "inbound_snapshot_today_missing "
            f"today_utc={snapshot_date} "
            f"snapshot_path={snapshot_path} "
            f"inventory_snapshot_path={inventory_snapshot_path}"
        )
        return snapshot_path, "missing"
    try:
        inv = pd.read_csv(inventory_snapshot_path, dtype=str).fillna("")
    except Exception as exc:
        _log(
            "inbound_snapshot_today_read_error "
            f"today_utc={snapshot_date} "
            f"inventory_snapshot_path={inventory_snapshot_path} "
            f"error={exc}"
        )
        return snapshot_path, "read_error"
    cols = [
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
    ]
    out_df = pd.DataFrame(index=inv.index.copy())
    out_df["timestamp_utc"] = inv.get("timestamp_utc", snapshot_ts).astype(str)
    out_df["asof_date"] = inv.get("asof_date", snapshot_date).astype(str)
    out_df["marketplace"] = inv.get("marketplace", "UK").astype(str)
    out_df["sku"] = inv.get("sku", "").astype(str).str.strip().str.upper()
    out_df["asin"] = inv.get("asin", "").astype(str)
    out_df["inbound_working"] = inv.get("inbound_working", "0").apply(_to_int_str)
    out_df["inbound_shipped"] = inv.get("inbound_shipped", "0").apply(_to_int_str)
    out_df["inbound_receiving"] = inv.get("inbound_receiving", "0").apply(_to_int_str)
    out_df["inbound_total"] = inv.get("inbound_total", "").astype(str)
    needs_total = out_df["inbound_total"].str.strip().eq("")
    if bool(needs_total.any()):
        derived_total = (
            pd.to_numeric(out_df["inbound_working"], errors="coerce").fillna(0).astype(int)
            + pd.to_numeric(out_df["inbound_shipped"], errors="coerce").fillna(0).astype(int)
            + pd.to_numeric(out_df["inbound_receiving"], errors="coerce").fillna(0).astype(int)
        ).astype(str)
        out_df.loc[needs_total, "inbound_total"] = derived_total.loc[needs_total]
    out_df["source"] = inv.get("source", "SPAPI").astype(str).replace("", "SPAPI")
    out_df["notes"] = inv.get("notes", "").astype(str)
    out_df = out_df.reindex(columns=cols, fill_value="")
    out_df = out_df.loc[out_df["sku"].ne("")].copy()
    out_df = out_df.drop_duplicates(subset=["asof_date", "sku", "marketplace"], keep="first")
    _atomic_write_csv(snapshot_path, out_df)
    _log(
        "inbound_snapshot_today_materialized "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"rows={len(out_df.index)} "
        f"source_path={inventory_snapshot_path}"
    )
    return snapshot_path, "from_inventory_snapshot"


def _rewrite_inbound_history_today_partition(snapshot_date: str, snapshot_path: Path) -> Dict[str, str]:
    key_cols = ["asof_date", "sku", "marketplace"]
    result = {
        "snapshot_rows_today": "0",
        "snapshot_dup_groups_today": "0",
        "snapshot_dup_rows_today": "0",
        "history_rows_today": "0",
        "history_dup_groups_today": "0",
        "history_dup_rows_today": "0",
        "history_rewrite_status": "skipped_snapshot_missing",
    }
    if not snapshot_path.exists():
        _log(f"inbound_history_partition_rewrite skipped snapshot_missing path={snapshot_path}")
        return result
    try:
        snapshot_df = pd.read_csv(snapshot_path, dtype=str).fillna("")
    except Exception as exc:
        _log(f"inbound_history_partition_rewrite error snapshot_read_failed path={snapshot_path} error={exc}")
        result["history_rewrite_status"] = "snapshot_read_failed"
        return result
    for col in key_cols:
        if col not in snapshot_df.columns:
            snapshot_df[col] = ""
    snapshot_df["asof_date"] = snapshot_df["asof_date"].astype(str).str.strip()
    snapshot_today = snapshot_df.loc[snapshot_df["asof_date"].eq(snapshot_date)].copy()
    result["snapshot_rows_today"] = str(len(snapshot_today.index))
    if "timestamp_utc" in snapshot_today.columns:
        snapshot_today["_order_ts"] = pd.to_datetime(snapshot_today["timestamp_utc"], errors="coerce", utc=True)
    else:
        snapshot_today["_order_ts"] = pd.NaT
    snapshot_today["_source_order"] = list(range(len(snapshot_today.index)))
    dup_mask = snapshot_today.duplicated(subset=key_cols, keep=False) if not snapshot_today.empty else pd.Series([], dtype=bool)
    dup_rows = int(dup_mask.sum()) if len(dup_mask.index) else 0
    dup_groups = int(snapshot_today.loc[dup_mask, key_cols].drop_duplicates().shape[0]) if dup_rows else 0
    result["snapshot_dup_groups_today"] = str(dup_groups)
    result["snapshot_dup_rows_today"] = str(dup_rows)
    snapshot_today = snapshot_today.sort_values(
        key_cols + ["_order_ts", "_source_order"],
        ascending=[True, True, True, False, True],
        kind="stable",
    )
    dedup_today = snapshot_today.drop_duplicates(subset=key_cols, keep="first").copy()
    dedup_today = dedup_today.drop(columns=["_order_ts", "_source_order"], errors="ignore")

    history_path = INBOUND_HISTORY_PATH
    if history_path.exists():
        try:
            history_df = pd.read_csv(history_path, dtype=str).fillna("")
        except Exception:
            history_df = pd.DataFrame(columns=dedup_today.columns)
    else:
        history_df = pd.DataFrame(columns=dedup_today.columns)
    for col in key_cols:
        if col not in history_df.columns:
            history_df[col] = ""
    history_df["asof_date"] = history_df["asof_date"].astype(str).str.strip()
    history_df["marketplace"] = history_df["marketplace"].astype(str).str.strip().str.upper()
    dedup_today["marketplace"] = dedup_today["marketplace"].astype(str).str.strip().str.upper()
    marketplaces_today = {
        _norm(v).upper()
        for v in dedup_today.get("marketplace", pd.Series([], dtype=str)).astype(str).tolist()
        if _norm(v)
    }
    is_today = history_df["asof_date"].eq(snapshot_date)
    if marketplaces_today:
        is_today = is_today & history_df["marketplace"].isin(marketplaces_today)
    history_keep = history_df.loc[~is_today].copy()
    merged_cols = list(history_keep.columns)
    for col in dedup_today.columns:
        if col not in merged_cols:
            merged_cols.append(col)
    history_keep = history_keep.reindex(columns=merged_cols, fill_value="")
    dedup_today = dedup_today.reindex(columns=merged_cols, fill_value="")
    merged = pd.concat([history_keep, dedup_today], ignore_index=True)
    _atomic_write_csv(history_path, merged)

    history_today = merged.loc[merged.get("asof_date", "").astype(str).str.strip().eq(snapshot_date)].copy()
    history_dup_mask = (
        history_today.duplicated(subset=key_cols, keep=False)
        if not history_today.empty
        else pd.Series([], dtype=bool)
    )
    history_dup_rows = int(history_dup_mask.sum()) if len(history_dup_mask.index) else 0
    history_dup_groups = (
        int(history_today.loc[history_dup_mask, key_cols].drop_duplicates().shape[0])
        if history_dup_rows
        else 0
    )
    result["history_rows_today"] = str(len(history_today.index))
    result["history_dup_groups_today"] = str(history_dup_groups)
    result["history_dup_rows_today"] = str(history_dup_rows)
    result["history_rewrite_status"] = "ok"

    report_path = OUT / "cycle_alerts" / f"inbound_snapshot_dedup_report_{snapshot_date}.csv"
    report = pd.DataFrame(
        [
            {
                "asof_date": snapshot_date,
                "snapshot_path": str(snapshot_path),
                "snapshot_rows_today": result["snapshot_rows_today"],
                "snapshot_dup_group_count": result["snapshot_dup_groups_today"],
                "snapshot_dup_row_count": result["snapshot_dup_rows_today"],
                "history_rows_today": result["history_rows_today"],
                "history_dup_group_count": result["history_dup_groups_today"],
                "history_dup_row_count": result["history_dup_rows_today"],
            }
        ]
    )
    _atomic_write_csv(report_path, report)
    _log(
        "inbound_history_partition_rewrite "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"snapshot_rows={result['snapshot_rows_today']} "
        f"snapshot_dup_groups={result['snapshot_dup_groups_today']} "
        f"snapshot_dup_rows={result['snapshot_dup_rows_today']} "
        f"history_rows={result['history_rows_today']} "
        f"history_dup_groups={result['history_dup_groups_today']} "
        f"history_dup_rows={result['history_dup_rows_today']} "
        f"report_path={report_path}"
    )
    return result


def _ensure_refund_adjustment_snapshot_today(snapshot_date: str, snapshot_ts: str) -> tuple[Path, str]:
    snapshot_path = OUT / f"refund_adjustment_snapshot_{snapshot_date}.csv"
    if snapshot_path.exists():
        return snapshot_path, "existing_snapshot"
    sku_rows = _active_sku_asin_rows(target_skus=None)
    cols = [
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
    ]
    rows: List[Dict[str, str]] = []
    for rec in sku_rows:
        sku = _norm(rec.get("sku", "")).upper()
        if not sku:
            continue
        rows.append(
            {
                "timestamp_utc": snapshot_ts,
                "asof_date": snapshot_date,
                "marketplace": _norm(rec.get("marketplace", "")) or "UK",
                "sku": sku,
                "asin": _norm(rec.get("asin", "")),
                "refund_event_count": "0",
                "adjustment_event_count": "0",
                "refund_units": "0",
                "adjustment_units": "0",
                "refund_amount_gbp": "0",
                "adjustment_amount_gbp": "0",
                "source": "SPAPI",
                "notes": "no_financial_events_in_window",
            }
        )
    out_df = pd.DataFrame(rows, columns=cols, dtype=str).fillna("")
    out_df = out_df.drop_duplicates(subset=["asof_date", "sku", "marketplace"], keep="first")
    _atomic_write_csv(snapshot_path, out_df)
    _log(
        "refund_snapshot_today_materialized "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"rows={len(out_df.index)} "
        f"source=active_sku_asin_rows"
    )
    return snapshot_path, "from_active_sku_seed"


def _rewrite_refund_history_today_partition(snapshot_date: str, snapshot_path: Path) -> Dict[str, str]:
    key_cols = ["asof_date", "sku", "marketplace"]
    result = {
        "snapshot_rows_today": "0",
        "snapshot_dup_groups_today": "0",
        "snapshot_dup_rows_today": "0",
        "history_rows_today": "0",
        "history_dup_groups_today": "0",
        "history_dup_rows_today": "0",
        "history_rewrite_status": "skipped_snapshot_missing",
    }
    if not snapshot_path.exists():
        _log(f"refund_history_partition_rewrite skipped snapshot_missing path={snapshot_path}")
        return result
    try:
        snapshot_df = pd.read_csv(snapshot_path, dtype=str).fillna("")
    except Exception as exc:
        _log(f"refund_history_partition_rewrite error snapshot_read_failed path={snapshot_path} error={exc}")
        result["history_rewrite_status"] = "snapshot_read_failed"
        return result
    for col in key_cols:
        if col not in snapshot_df.columns:
            snapshot_df[col] = ""
    snapshot_df["asof_date"] = snapshot_df["asof_date"].astype(str).str.strip()
    snapshot_today = snapshot_df.loc[snapshot_df["asof_date"].eq(snapshot_date)].copy()
    result["snapshot_rows_today"] = str(len(snapshot_today.index))
    if "timestamp_utc" in snapshot_today.columns:
        snapshot_today["_order_ts"] = pd.to_datetime(snapshot_today["timestamp_utc"], errors="coerce", utc=True)
    else:
        snapshot_today["_order_ts"] = pd.NaT
    snapshot_today["_source_order"] = list(range(len(snapshot_today.index)))
    dup_mask = snapshot_today.duplicated(subset=key_cols, keep=False) if not snapshot_today.empty else pd.Series([], dtype=bool)
    dup_rows = int(dup_mask.sum()) if len(dup_mask.index) else 0
    dup_groups = int(snapshot_today.loc[dup_mask, key_cols].drop_duplicates().shape[0]) if dup_rows else 0
    result["snapshot_dup_groups_today"] = str(dup_groups)
    result["snapshot_dup_rows_today"] = str(dup_rows)
    snapshot_today = snapshot_today.sort_values(
        key_cols + ["_order_ts", "_source_order"],
        ascending=[True, True, True, False, True],
        kind="stable",
    )
    dedup_today = snapshot_today.drop_duplicates(subset=key_cols, keep="first").copy()
    dedup_today = dedup_today.drop(columns=["_order_ts", "_source_order"], errors="ignore")

    history_path = REFUND_ADJUSTMENT_HISTORY_PATH
    if history_path.exists():
        try:
            history_df = pd.read_csv(history_path, dtype=str).fillna("")
        except Exception:
            history_df = pd.DataFrame(columns=dedup_today.columns)
    else:
        history_df = pd.DataFrame(columns=dedup_today.columns)
    for col in key_cols:
        if col not in history_df.columns:
            history_df[col] = ""
    history_df["asof_date"] = history_df["asof_date"].astype(str).str.strip()
    history_df["marketplace"] = history_df["marketplace"].astype(str).str.strip().str.upper()
    dedup_today["marketplace"] = dedup_today["marketplace"].astype(str).str.strip().str.upper()
    marketplaces_today = {
        _norm(v).upper()
        for v in dedup_today.get("marketplace", pd.Series([], dtype=str)).astype(str).tolist()
        if _norm(v)
    }
    is_today = history_df["asof_date"].eq(snapshot_date)
    if marketplaces_today:
        is_today = is_today & history_df["marketplace"].isin(marketplaces_today)
    history_keep = history_df.loc[~is_today].copy()
    merged_cols = list(history_keep.columns)
    for col in dedup_today.columns:
        if col not in merged_cols:
            merged_cols.append(col)
    history_keep = history_keep.reindex(columns=merged_cols, fill_value="")
    dedup_today = dedup_today.reindex(columns=merged_cols, fill_value="")
    merged = pd.concat([history_keep, dedup_today], ignore_index=True)
    _atomic_write_csv(history_path, merged)

    history_today = merged.loc[merged.get("asof_date", "").astype(str).str.strip().eq(snapshot_date)].copy()
    history_dup_mask = (
        history_today.duplicated(subset=key_cols, keep=False)
        if not history_today.empty
        else pd.Series([], dtype=bool)
    )
    history_dup_rows = int(history_dup_mask.sum()) if len(history_dup_mask.index) else 0
    history_dup_groups = (
        int(history_today.loc[history_dup_mask, key_cols].drop_duplicates().shape[0])
        if history_dup_rows
        else 0
    )
    result["history_rows_today"] = str(len(history_today.index))
    result["history_dup_groups_today"] = str(history_dup_groups)
    result["history_dup_rows_today"] = str(history_dup_rows)
    result["history_rewrite_status"] = "ok"

    report_path = OUT / "cycle_alerts" / f"refund_snapshot_dedup_report_{snapshot_date}.csv"
    report = pd.DataFrame(
        [
            {
                "asof_date": snapshot_date,
                "snapshot_path": str(snapshot_path),
                "snapshot_rows_today": result["snapshot_rows_today"],
                "snapshot_dup_group_count": result["snapshot_dup_groups_today"],
                "snapshot_dup_row_count": result["snapshot_dup_rows_today"],
                "history_rows_today": result["history_rows_today"],
                "history_dup_group_count": result["history_dup_groups_today"],
                "history_dup_row_count": result["history_dup_rows_today"],
            }
        ]
    )
    _atomic_write_csv(report_path, report)
    _log(
        "refund_history_partition_rewrite "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"snapshot_rows={result['snapshot_rows_today']} "
        f"snapshot_dup_groups={result['snapshot_dup_groups_today']} "
        f"snapshot_dup_rows={result['snapshot_dup_rows_today']} "
        f"history_rows={result['history_rows_today']} "
        f"history_dup_groups={result['history_dup_groups_today']} "
        f"history_dup_rows={result['history_dup_rows_today']} "
        f"report_path={report_path}"
    )
    return result


def _context_value_present(col: str, value: str) -> bool:
    v = _norm(value)
    if not v:
        return False
    if col == "buy_box_channel":
        return v.upper() != "UNKNOWN"
    if col in {"buy_box_price", "lowest_fba_price", "lowest_fbm_price", "offer_count_fba", "offer_count_fbm"}:
        return v not in {"0", "0.0", "0.00"}
    return True


def _recent_snapshot_candidates(snapshot_date: str, max_days_back: int = 7) -> List[str]:
    try:
        base = datetime.strptime(snapshot_date, "%Y-%m-%d").date()
    except Exception:
        return []
    days = max(int(max_days_back), 1)
    out: List[str] = []
    for i in range(1, days + 1):
        out.append((base - timedelta(days=i)).isoformat())
    return out


def _load_prior_listing_context(snapshot_date: str) -> Dict[str, Dict[str, str]]:
    context_cols = [
        "buy_box_price",
        "buy_box_channel",
        "lowest_fba_price",
        "lowest_fbm_price",
        "offer_count_fba",
        "offer_count_fbm",
        "timestamp_utc",
    ]
    paths: List[Path] = []
    today_path = OUT / f"listing_offer_snapshot_{snapshot_date}.csv"
    if today_path.exists():
        paths.append(today_path)
    for prior in _recent_snapshot_candidates(snapshot_date):
        p = OUT / f"listing_offer_snapshot_{prior}.csv"
        if p.exists():
            paths.append(p)
    if not paths:
        return {}
    frames: List[pd.DataFrame] = []
    for path in paths:
        try:
            frames.append(pd.read_csv(path, dtype=str).fillna(""))
        except Exception:
            continue
    if not frames:
        return {}
    df = pd.concat(frames, ignore_index=True)
    if df.empty or "sku" not in df.columns:
        return {}
    df["sku_key"] = df["sku"].astype(str).str.strip().str.upper()
    df["ts_dt"] = pd.to_datetime(df.get("timestamp_utc", ""), errors="coerce", utc=True)
    df = df.loc[df["sku_key"].ne("")].copy()
    df = df.sort_values(["ts_dt"], ascending=[False], kind="stable")
    out: Dict[str, Dict[str, str]] = {}
    for _, rec in df.iterrows():
        sku_key = _norm(rec.get("sku_key", "")).upper()
        if not sku_key:
            continue
        row = out.setdefault(sku_key, {})
        for col in context_cols:
            if row.get(col):
                continue
            candidate = _norm(rec.get(col, ""))
            if _context_value_present(col, candidate):
                row[col] = candidate
    return out


def _load_prior_own_offer_prices(snapshot_date: str) -> Dict[str, Dict[str, str]]:
    paths: List[Path] = []
    today_path = OUT / f"listing_offer_snapshot_{snapshot_date}.csv"
    if today_path.exists():
        paths.append(today_path)
    for prior in _recent_snapshot_candidates(snapshot_date):
        p = OUT / f"listing_offer_snapshot_{prior}.csv"
        if p.exists():
            paths.append(p)
    if not paths:
        return {}
    frames: List[pd.DataFrame] = []
    for path in paths:
        try:
            frames.append(pd.read_csv(path, dtype=str).fillna(""))
        except Exception:
            continue
    if not frames:
        return {}
    df = pd.concat(frames, ignore_index=True)
    if df.empty or "sku" not in df.columns or "marketplace" not in df.columns:
        return {}
    df["sku_key"] = df["sku"].astype(str).str.strip().str.upper()
    df["mp_key"] = df["marketplace"].astype(str).str.strip().str.upper()
    if "our_price" in df.columns:
        df["our_price_norm"] = df["our_price"].astype(str).str.strip()
    else:
        df["our_price_norm"] = ""
    if "timestamp_utc" in df.columns:
        df["ts_dt"] = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
    else:
        df["ts_dt"] = pd.NaT
    df = df.loc[df["sku_key"].ne("") & df["mp_key"].ne("")].copy()
    df = df.sort_values(["ts_dt"], ascending=[False], kind="stable")
    out: Dict[str, Dict[str, str]] = {}
    for _, rec in df.iterrows():
        mp_key = _norm(rec.get("mp_key", "")).upper()
        sku_key = _norm(rec.get("sku_key", "")).upper()
        price = _norm(rec.get("our_price_norm", ""))
        if not mp_key or not sku_key or not price:
            continue
        by_sku = out.setdefault(mp_key, {})
        if sku_key not in by_sku:
            by_sku[sku_key] = price
    return out


def _refresh_offer_snapshots(
    now_utc: datetime,
    state: dict,
    target_skus: List[str] | None = None,
    *,
    item_offers_enabled: bool = True,
    stage_run_id: str = "",
) -> dict:
    min_interval_sec = max(float(os.environ.get("H_REFRESH_MIN_SECONDS", "120") or "120"), 1.0)
    last_refresh = _to_dt(state.get("last_snapshot_refresh_utc", ""))
    if last_refresh is not None:
        elapsed = (now_utc - last_refresh).total_seconds()
        if elapsed < min_interval_sec:
            return {
                "snapshot_refresh_attempted": "0",
                "snapshot_refresh_status": "throttled",
            }

    sku_asin_rows = _active_sku_asin_rows(target_skus=target_skus)
    if not sku_asin_rows:
        return {
            "last_snapshot_refresh_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot_refresh_attempted": "1",
            "snapshot_refresh_status": "no_active_sku_rows",
        }
    snapshot_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_date = now_utc.strftime("%Y-%m-%d")
    run_id = _norm(stage_run_id) or _context_run_id()

    try:
        rows_out: List[Dict[str, str]] = []
        seller_rows_out: List[Dict[str, str]] = []
        prior_context_by_sku = _load_prior_listing_context(snapshot_date)
        prior_own_offer_by_market = _load_prior_own_offer_prices(snapshot_date)
        refresh_started = time.monotonic()
        last_heartbeat = refresh_started
        last_status_log = refresh_started
        progress_state: dict[str, str] = {"stage": "init", "completed": "", "total": ""}
        heartbeat_stop = threading.Event()

        def _snapshot_heartbeat_loop() -> None:
            while not heartbeat_stop.wait(30.0):
                elapsed = max(time.monotonic() - refresh_started, 0.0)
                _write_lock()
                _log(
                    "snapshot_refresh still_working "
                    f"stage={progress_state.get('stage') or 'progress'} "
                    f"elapsed_seconds={_fmt(_r2(elapsed))} "
                    f"completed={progress_state.get('completed') or '?'} "
                    f"total={progress_state.get('total') or '?'}"
                )

        heartbeat_thread = threading.Thread(target=_snapshot_heartbeat_loop, name="h_snapshot_heartbeat", daemon=True)
        heartbeat_thread.start()

        def _ensure_refresh_not_timed_out(stage: str) -> None:
            elapsed = max(time.monotonic() - refresh_started, 0.0)
            if elapsed > H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"snapshot_refresh_timeout stage={stage} "
                    f"elapsed_seconds={_fmt(_r2(elapsed))} "
                    f"timeout_seconds={int(H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS)}"
                )

        def _refresh_progress(**kwargs) -> None:
            stage = _norm(kwargs.get("stage", ""))
            completed = _norm(kwargs.get("completed", ""))
            total = _norm(kwargs.get("total", ""))
            nonlocal last_heartbeat
            nonlocal last_status_log
            if stage:
                progress_state["stage"] = stage
            if completed:
                progress_state["completed"] = completed
            if total:
                progress_state["total"] = total
            _ensure_refresh_not_timed_out(stage or "progress")
            now_mono = time.monotonic()
            # Keep lock heartbeat alive during long API pulls.
            if now_mono - last_heartbeat >= 5.0:
                _write_lock()
                last_heartbeat = now_mono
            # Operator heartbeat: show that refresh is still alive during long waits.
            if now_mono - last_status_log >= 30.0:
                elapsed = max(now_mono - refresh_started, 0.0)
                _log(
                    "snapshot_refresh working "
                    f"stage={stage or 'progress'} "
                    f"elapsed_seconds={_fmt(_r2(elapsed))} "
                    f"completed={completed or '?'} "
                    f"total={total or '?'}"
                )
                last_status_log = now_mono

        for marketplace, grp in pd.DataFrame(sku_asin_rows, dtype=str).fillna("").groupby("marketplace", dropna=False):
            progress_state["stage"] = "marketplace_loop"
            _ensure_refresh_not_timed_out("marketplace_loop")
            mp_code = _norm(marketplace).upper() or "UK"
            mp_id = _resolve_marketplace_id({"marketplace": mp_code})
            skus = grp["sku"].astype(str).str.strip().tolist()
            sku_asins = [(str(r["sku"]).strip(), str(r["asin"]).strip()) for _, r in grp.iterrows()]
            progress_state["stage"] = "own_offer_lookup"
            own_map: Dict[str, Dict[str, str]] = {}
            try:
                own_map = _run_own_offer_lookup_guarded(
                    skus=skus,
                    marketplace_id=mp_id,
                    run_id=run_id,
                    script_name=SOURCE,
                )
            except Exception as exc:
                cached = prior_own_offer_by_market.get(mp_code, {})
                fallback_count = 0
                for sku in skus:
                    sku_key = _norm(sku).upper()
                    price = _norm(cached.get(sku_key, ""))
                    if not sku_key or not price:
                        continue
                    own_map[sku_key] = {"price": price, "currency": ""}
                    fallback_count += 1
                error_text = _norm(str(exc))[:300]
                if fallback_count > 0 and _is_nonfatal_own_offer_lock_contention(error_text):
                    _log(
                        "snapshot_refresh own_offer_lookup info "
                        f"marketplace={mp_code} "
                        "class=nonfatal_lock_contention "
                        f"error={error_text} "
                        f"fallback_cached_price_rows={fallback_count}"
                    )
                else:
                    _log(
                        "snapshot_refresh own_offer_lookup warning "
                        f"marketplace={mp_code} "
                        f"error={error_text} "
                        f"fallback_cached_price_rows={fallback_count}"
                    )
            progress_state["stage"] = "own_offer_lookup_done"
            _ensure_refresh_not_timed_out("after_own_offer_lookup")
            progress_state["stage"] = "item_offers"
            if item_offers_enabled:
                item_stage_start = _stage_enter(stage="item_offers", run_id=stage_run_id or run_id)
                try:
                    bb_map, offer_rows = _run_item_offers_lookup_guarded(
                        sku_asins=sku_asins,
                        marketplace_id=mp_id,
                        snapshot_ts=snapshot_ts,
                        snapshot_date=snapshot_date,
                        run_id=run_id,
                        script_name=SOURCE,
                    )
                    _stage_exit(stage="item_offers", run_id=stage_run_id or run_id, started=item_stage_start, rc="0")
                except Exception:
                    _stage_exit(stage="item_offers", run_id=stage_run_id or run_id, started=item_stage_start, rc="1")
                    raise
            else:
                item_stage_start = _stage_enter(stage="item_offers", run_id=stage_run_id or run_id)
                bb_map = {}
                offer_rows = []
                _stage_exit(
                    stage="item_offers",
                    run_id=stage_run_id or run_id,
                    started=item_stage_start,
                    rc="skipped",
                    note="disabled",
                )
            progress_state["stage"] = "item_offers_done"
            _ensure_refresh_not_timed_out("after_market_context_lookup")
            seller_rows_out.extend(offer_rows)
            notes_by_sku = {str(r["sku"]).strip().upper(): str(r.get("notes", "")).strip() for _, r in grp.iterrows()}
            asin_by_sku = {str(r["sku"]).strip().upper(): str(r.get("asin", "")).strip() for _, r in grp.iterrows()}
            cached_own_prices = prior_own_offer_by_market.get(mp_code, {})
            cached_own_price_fallback_count = 0
            for sku in skus:
                sku_key = str(sku).strip().upper()
                prior_ctx = prior_context_by_sku.get(sku_key, {})
                bb = bb_map.get(sku_key, {})
                our_price = _norm((own_map.get(sku_key) or {}).get("price", ""))
                if not our_price:
                    cached_price = _norm(cached_own_prices.get(sku_key, ""))
                    if cached_price:
                        our_price = cached_price
                        cached_own_price_fallback_count += 1
                buy_box_price = _norm(bb.get("price", "")) or _norm(prior_ctx.get("buy_box_price", ""))
                buy_box_present_flag = "1" if buy_box_price else "0"
                row = {
                    "timestamp_utc": snapshot_ts,
                    "asof_date": snapshot_date,
                    "marketplace": mp_code,
                    "sku": sku_key,
                    "asin": asin_by_sku.get(sku_key, ""),
                    "our_price": our_price,
                    "buy_box_price": buy_box_price,
                    "buy_box_present_flag": buy_box_present_flag,
                    "outcome_known_flag": buy_box_present_flag,
                    "we_present_flag": "1" if our_price else "0",
                    "buy_box_channel": (
                        _norm(bb.get("buy_box_channel", ""))
                        or _norm(prior_ctx.get("buy_box_channel", ""))
                        or ""
                    ),
                    "lowest_fba_price": _norm(bb.get("lowest_fba_price", "")) or _norm(prior_ctx.get("lowest_fba_price", "")),
                    "lowest_fbm_price": _norm(bb.get("lowest_fbm_price", "")) or _norm(prior_ctx.get("lowest_fbm_price", "")),
                    "offer_count_fba": _norm(bb.get("offer_count_fba", "")) or _norm(prior_ctx.get("offer_count_fba", "")),
                    "offer_count_fbm": _norm(bb.get("offer_count_fbm", "")) or _norm(prior_ctx.get("offer_count_fbm", "")),
                    "bsr": "",
                    "bsr_category": "",
                    "source": "SPAPI",
                    "notes": notes_by_sku.get(sku_key, ""),
                }
                rows_out.append(row)
            if cached_own_price_fallback_count > 0:
                _log(
                    "snapshot_refresh own_offer_lookup partial_result "
                    f"marketplace={mp_code} "
                    f"fallback_cached_price_rows={cached_own_price_fallback_count}"
                )

        listing_cols = [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "our_price",
            "buy_box_price",
            "buy_box_present_flag",
            "outcome_known_flag",
            "we_present_flag",
            "buy_box_channel",
            "lowest_fba_price",
            "lowest_fbm_price",
            "offer_count_fba",
            "offer_count_fbm",
            "bsr",
            "bsr_category",
            "source",
            "notes",
        ]
        seller_cols = [
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
        ]
        listing_df = pd.DataFrame(rows_out, columns=listing_cols, dtype=str).fillna("")
        seller_df = pd.DataFrame(seller_rows_out, columns=seller_cols, dtype=str).fillna("")

        _log(f"snapshot_refresh seller_snapshot_stage item_offers_enabled={'1' if item_offers_enabled else '0'}")
        listing_snapshot_path = OUT / f"listing_offer_snapshot_{snapshot_date}.csv"
        _upsert_snapshot_rows(listing_snapshot_path, listing_df, ["marketplace", "sku"])
        listing_latest_path = OUT / "listing_offer_snapshot_latest.csv"
        _update_latest_snapshot_pointer(listing_snapshot_path, listing_latest_path)
        _log(f"snapshot_refresh latest_pointer_updated target={listing_latest_path}")
        run_scoped_seller_path = OUT / "snapshots" / "H" / _norm(stage_run_id or run_id) / "listing_offer_seller_snapshot.csv"
        _atomic_write_csv(run_scoped_seller_path, seller_df)
        _log(
            "snapshot_refresh run_scoped_seller_snapshot "
            f"path={run_scoped_seller_path} "
            f"rows={len(seller_df.index)}"
        )

        seller_snapshot_path = OUT / f"listing_offer_seller_snapshot_{snapshot_date}.csv"
        _atomic_write_csv(seller_snapshot_path, seller_df)
        seller_latest_path = OUT / "listing_offer_seller_snapshot_latest.csv"
        _update_latest_snapshot_pointer(seller_snapshot_path, seller_latest_path)
        _log(f"snapshot_refresh latest_pointer_updated target={seller_latest_path}")
        if seller_df.empty:
            _log(f"snapshot_refresh seller_snapshot_dated_written rows=0 path={seller_snapshot_path}")
        else:
            _log(f"snapshot_refresh seller_snapshot_dated_written rows={len(seller_df.index)} path={seller_snapshot_path}")

        listing_history_rewrite = _upsert_listing_offer_history_today_partition(snapshot_date, listing_snapshot_path)
        _log(
            "snapshot_refresh listing_history_refreshed "
            f"status={listing_history_rewrite.get('history_rewrite_status', '')} "
            f"rows_today={listing_history_rewrite.get('history_rows_today', '0')}"
        )
        history_rewrite = _rewrite_seller_history_today_partition(snapshot_date, seller_snapshot_path)
        inventory_snapshot_path, inventory_snapshot_source = _ensure_inventory_snapshot_today(snapshot_date, snapshot_ts)
        inventory_history_rewrite = _rewrite_inventory_history_today_partition(snapshot_date, inventory_snapshot_path)
        _log(
            "inventory_history_partition_rewrite_decision "
            f"today_utc={snapshot_date} "
            f"snapshot_source={inventory_snapshot_source} "
            f"snapshot_path={inventory_snapshot_path} "
            f"snapshot_rows={inventory_history_rewrite.get('snapshot_rows_today', '0')} "
            f"history_rows={inventory_history_rewrite.get('history_rows_today', '0')} "
            f"history_dup_groups={inventory_history_rewrite.get('history_dup_groups_today', '0')} "
            f"history_dup_rows={inventory_history_rewrite.get('history_dup_rows_today', '0')} "
            f"status={inventory_history_rewrite.get('history_rewrite_status', '')}"
        )
        inbound_snapshot_path, inbound_snapshot_source = _ensure_inbound_snapshot_today(snapshot_date, snapshot_ts)
        inbound_history_rewrite = _rewrite_inbound_history_today_partition(snapshot_date, inbound_snapshot_path)
        _log(
            "inbound_history_partition_rewrite_decision "
            f"today_utc={snapshot_date} "
            f"snapshot_source={inbound_snapshot_source} "
            f"snapshot_path={inbound_snapshot_path} "
            f"snapshot_rows={inbound_history_rewrite.get('snapshot_rows_today', '0')} "
            f"history_rows={inbound_history_rewrite.get('history_rows_today', '0')} "
            f"history_dup_groups={inbound_history_rewrite.get('history_dup_groups_today', '0')} "
            f"history_dup_rows={inbound_history_rewrite.get('history_dup_rows_today', '0')} "
            f"status={inbound_history_rewrite.get('history_rewrite_status', '')}"
        )
        refund_snapshot_path, refund_snapshot_source = _ensure_refund_adjustment_snapshot_today(snapshot_date, snapshot_ts)
        refund_history_rewrite = _rewrite_refund_history_today_partition(snapshot_date, refund_snapshot_path)
        _log(
            "refund_history_partition_rewrite_decision "
            f"today_utc={snapshot_date} "
            f"snapshot_source={refund_snapshot_source} "
            f"snapshot_path={refund_snapshot_path} "
            f"snapshot_rows={refund_history_rewrite.get('snapshot_rows_today', '0')} "
            f"history_rows={refund_history_rewrite.get('history_rows_today', '0')} "
            f"history_dup_groups={refund_history_rewrite.get('history_dup_groups_today', '0')} "
            f"history_dup_rows={refund_history_rewrite.get('history_dup_rows_today', '0')} "
            f"status={refund_history_rewrite.get('history_rewrite_status', '')}"
        )
        contract_artifacts = [
            listing_latest_path,
            seller_latest_path,
            LISTING_OFFER_HISTORY_PATH,
        ]
        contract_details: List[str] = []
        contract_ok = True
        for artifact_path in contract_artifacts:
            refreshed, detail = _is_artifact_refreshed_in_run(artifact_path, now_utc)
            contract_details.append(
                f"{artifact_path.name}:exists={'1' if artifact_path.exists() else '0'}:refreshed={'1' if refreshed else '0'}:{detail}"
            )
            if not refreshed:
                contract_ok = False
        if not contract_ok:
            detail_text = ";".join(contract_details)
            _log(f"FATAL snapshot_refresh_artifact_contract_failed details={detail_text}")
            raise RuntimeError(f"snapshot_refresh_artifact_contract_failed:{detail_text}")
        _log(f"snapshot_refresh artifact_contract_pass details={';'.join(contract_details)}")
        _log(f"snapshot_refresh ok listing_rows={len(listing_df.index)} seller_rows={len(seller_df.index)}")
        _log(f"snapshot_refresh timing elapsed_seconds={_fmt(_r2(time.monotonic() - refresh_started))}")
        status = "ok"
        return {
            "last_snapshot_refresh_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot_refresh_attempted": "1",
            "snapshot_refresh_status": status,
            "listing_history_rows_today": listing_history_rewrite.get("history_rows_today", "0"),
            "listing_history_dup_groups_today": listing_history_rewrite.get("history_dup_groups_today", "0"),
            "listing_history_dup_rows_today": listing_history_rewrite.get("history_dup_rows_today", "0"),
            "listing_history_rewrite_status": listing_history_rewrite.get("history_rewrite_status", ""),
            "seller_history_rows_today": history_rewrite.get("history_rows_today", "0"),
            "seller_history_dup_groups_today": history_rewrite.get("history_dup_groups_today", "0"),
            "seller_history_dup_rows_today": history_rewrite.get("history_dup_rows_today", "0"),
            "seller_history_rewrite_status": history_rewrite.get("history_rewrite_status", ""),
            "inventory_history_rows_today": inventory_history_rewrite.get("history_rows_today", "0"),
            "inventory_history_dup_groups_today": inventory_history_rewrite.get("history_dup_groups_today", "0"),
            "inventory_history_dup_rows_today": inventory_history_rewrite.get("history_dup_rows_today", "0"),
            "inventory_history_rewrite_status": inventory_history_rewrite.get("history_rewrite_status", ""),
            "inbound_history_rows_today": inbound_history_rewrite.get("history_rows_today", "0"),
            "inbound_history_dup_groups_today": inbound_history_rewrite.get("history_dup_groups_today", "0"),
            "inbound_history_dup_rows_today": inbound_history_rewrite.get("history_dup_rows_today", "0"),
            "inbound_history_rewrite_status": inbound_history_rewrite.get("history_rewrite_status", ""),
            "refund_history_rows_today": refund_history_rewrite.get("history_rows_today", "0"),
            "refund_history_dup_groups_today": refund_history_rewrite.get("history_dup_groups_today", "0"),
            "refund_history_dup_rows_today": refund_history_rewrite.get("history_dup_rows_today", "0"),
            "refund_history_rewrite_status": refund_history_rewrite.get("history_rewrite_status", ""),
        }
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        if isinstance(exc, SystemExit):
            code = _system_exit_code(exc)
            if code == 0:
                _log("FATAL snapshot_refresh_system_exit_zero_promoted rc=3")
                raise SystemExit(3)
            raise
        _log(f"snapshot_refresh error={exc}")
        return {
            "last_snapshot_refresh_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot_refresh_attempted": "1",
            "snapshot_refresh_status": "error",
            "snapshot_refresh_error": str(exc),
        }
    finally:
        try:
            heartbeat_stop.set()
        except Exception:
            pass


def _latest_seller_snapshot_age_for_sku(sku: str, now_utc: datetime) -> Dict[str, str]:
    path = _latest_seller_snapshot()
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {"seller_snapshot_file": path.name, "seller_snapshot_age_minutes": ""}
    sku_col = df.get("sku", "").astype(str).str.strip().str.upper()
    scoped = df.loc[sku_col.eq(sku.upper())].copy()
    if scoped.empty:
        return {"seller_snapshot_file": path.name, "seller_snapshot_age_minutes": ""}
    ts_vals = pd.to_datetime(scoped.get("timestamp_utc", ""), errors="coerce", utc=True).dropna()
    if ts_vals.empty:
        return {"seller_snapshot_file": path.name, "seller_snapshot_age_minutes": ""}
    latest = ts_vals.max().to_pydatetime()
    age_minutes = max((now_utc - latest).total_seconds() / 60.0, 0.0)
    return {
        "seller_snapshot_file": path.name,
        "seller_snapshot_age_minutes": _fmt(_r2(age_minutes)),
    }


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


def _optional_seller_partner_id() -> str:
    return _norm(
        os.environ.get("SELLER_ID")
        or os.environ.get("SELLER_PARTNER_ID")
        or os.environ.get("MERCHANT_ID")
        or os.environ.get("SELLING_PARTNER_ID")
        or ""
    )


def _latest_seller_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_seller_snapshot_*.csv"))
    if not files:
        raise FileNotFoundError("No seller snapshot found: out/listing_offer_seller_snapshot_YYYY-MM-DD.csv")
    return files[-1]


def _build_seller_profiles() -> Dict[str, str]:
    snapshot_path = _latest_seller_snapshot()
    df = pd.read_csv(snapshot_path, dtype=str).fillna("")
    required = ["asof_date", "marketplace", "sku", "seller_id", "offer_price_gbp", "offer_landed_price_gbp"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Seller profile build failed: snapshot missing columns {','.join(missing)}")

    active_skus = load_active_lab_skus()
    if not active_skus:
        raise RuntimeError("Seller profile build failed: no active lab SKUs")

    profile_cols = [
        "snapshot_file",
        "asof_date",
        "marketplace",
        "sku",
        "seller_id",
        "offers_seen",
        "rank_by_landed_price",
        "best_landed_price_gbp",
        "seller_landed_price_latest_gbp",
        "seller_landed_price_min_gbp",
        "seller_landed_price_max_gbp",
        "seller_landed_price_median_gbp",
        "gap_to_best_landed_gbp",
        "min_delivery_days",
        "prime_seen_flag",
        "tier",
        "tier_reason",
        "source",
    ]
    asof_date_fallback = _norm(df.get("asof_date", pd.Series([], dtype=str)).astype(str).max())
    run_id = _context_run_id()

    def _write_empty_seller_profile_outputs(reason_code: str) -> Dict[str, str]:
        profile_df = pd.DataFrame(columns=profile_cols)
        profile_df.to_csv(SELLER_PROFILE_PATH, index=False)
        soi_rows = []
        for sku in sorted({str(s).strip().upper() for s in active_skus if str(s).strip()}):
            soi_rows.append(
                {
                    "snapshot_file": snapshot_path.name,
                    "asof_date": asof_date_fallback,
                    "marketplace": "UK",
                    "sku": sku,
                    "seller_id": "",
                    "offers_seen": "0",
                    "rank_by_landed_price": "",
                    "best_landed_price_gbp": "",
                    "seller_landed_price_latest_gbp": "",
                    "seller_landed_price_min_gbp": "",
                    "seller_landed_price_max_gbp": "",
                    "seller_landed_price_median_gbp": "",
                    "gap_to_best_landed_gbp": "",
                    "min_delivery_days": "",
                    "prime_seen_flag": "",
                    "tier": "seller_of_interest",
                    "tier_reason": "active_cohort_placeholder",
                    "source": SOURCE,
                }
            )
        soi_df = pd.DataFrame(soi_rows, dtype=str).fillna("")
        if soi_df.empty:
            soi_df = pd.DataFrame(columns=profile_cols)
        soi_df = soi_df[profile_cols].sort_values(["sku", "rank_by_landed_price", "seller_id"], kind="stable")
        soi_df.to_csv(SELLER_SOI_PATH, index=False)
        _log(
            "INFO seller_profiles_empty "
            f"run_id={run_id} "
            "seller_rows=0 "
            "action=continue_without_seller_profiles "
            f"reason={reason_code}"
        )
        return {
            "seller_profile_snapshot": snapshot_path.name,
            "seller_profile_rows": "0",
            "seller_soi_rows": str(len(soi_df.index)),
            "seller_soi_top_n": "0",
            "seller_soi_max_gap_gbp": "0",
            "seller_profile_status": "info",
            "seller_profile_warn_reason": reason_code,
        }

    df["sku_key"] = df["sku"].astype(str).str.strip().str.upper()
    df["seller_key"] = df["seller_id"].astype(str).str.strip()
    scoped = df.loc[df["sku_key"].isin([s.upper() for s in active_skus])].copy()
    scoped = scoped.loc[scoped["seller_key"].ne("")].copy()
    if os.environ.get("H_FORCE_SELLER_PROFILES_EMPTY", "0").strip() == "1":
        return _write_empty_seller_profile_outputs("forced_empty_for_diagnostics")
    if scoped.empty:
        return _write_empty_seller_profile_outputs("no_seller_rows_for_active_lab_skus")

    our_seller = _optional_seller_partner_id()
    if our_seller:
        scoped = scoped.loc[~scoped["seller_key"].eq(our_seller)].copy()
    if scoped.empty:
        return _write_empty_seller_profile_outputs("all_rows_filtered_as_self")

    scoped["offer_price_num"] = pd.to_numeric(scoped.get("offer_price_gbp", ""), errors="coerce")
    scoped["offer_ship_num"] = pd.to_numeric(scoped.get("offer_shipping_price_gbp", ""), errors="coerce")
    scoped["offer_landed_num"] = pd.to_numeric(scoped.get("offer_landed_price_gbp", ""), errors="coerce")
    fill_landed = scoped["offer_landed_num"].isna()
    scoped.loc[fill_landed, "offer_landed_num"] = (
        scoped.loc[fill_landed, "offer_price_num"].fillna(0) + scoped.loc[fill_landed, "offer_ship_num"].fillna(0)
    )
    scoped["delivery_days_num"] = pd.to_numeric(scoped.get("min_delivery_days", ""), errors="coerce")
    scoped["is_prime_num"] = scoped.get("is_prime", "").astype(str).str.strip().isin({"1", "true", "yes", "y"}).astype(int)
    scoped["asof_date_key"] = scoped["asof_date"].astype(str).str.strip()

    top_n = max(_to_int(os.environ.get("H_SOI_TOP_N", "5")) or 5, 1)
    max_gap = max(_to_float(os.environ.get("H_SOI_MAX_GAP_GBP", "1.50")) or 1.5, 0.0)

    out_rows: List[Dict[str, str]] = []
    soi_rows: List[Dict[str, str]] = []
    for sku_key, sku_grp in scoped.groupby("sku_key", sort=True):
        sku_grp = sku_grp.copy()
        best_landed = float(pd.to_numeric(sku_grp["offer_landed_num"], errors="coerce").min())
        if pd.isna(best_landed):
            continue
        seller_stats = (
            sku_grp.groupby("seller_key", as_index=False)
            .agg(
                asof_date=("asof_date_key", "max"),
                marketplace=("marketplace", "first"),
                offers_seen=("seller_key", "size"),
                landed_min=("offer_landed_num", "min"),
                landed_max=("offer_landed_num", "max"),
                landed_median=("offer_landed_num", "median"),
                landed_latest=("offer_landed_num", "last"),
                min_delivery_days=("delivery_days_num", "min"),
                prime_seen=("is_prime_num", "max"),
            )
        )
        seller_stats = seller_stats.sort_values(["landed_latest", "seller_key"], kind="stable").reset_index(drop=True)
        seller_stats["rank"] = seller_stats.index + 1
        seller_stats["gap_to_best"] = seller_stats["landed_latest"] - best_landed

        for _, rec in seller_stats.iterrows():
            tier = "background_basic"
            reason = "outside_soi_gate"
            if int(rec["rank"]) <= top_n and float(rec["gap_to_best"]) <= max_gap:
                tier = "seller_of_interest"
                reason = "rank_and_gap_gate"
            row = {
                "snapshot_file": snapshot_path.name,
                "asof_date": _norm(rec.get("asof_date", "")),
                "marketplace": _norm(rec.get("marketplace", "")),
                "sku": sku_key,
                "seller_id": _norm(rec.get("seller_key", "")),
                "offers_seen": str(int(rec.get("offers_seen", 0) or 0)),
                "rank_by_landed_price": str(int(rec.get("rank", 0) or 0)),
                "best_landed_price_gbp": _fmt(_r2(best_landed)),
                "seller_landed_price_latest_gbp": _fmt(_r2(_to_float(rec.get("landed_latest", "")))),
                "seller_landed_price_min_gbp": _fmt(_r2(_to_float(rec.get("landed_min", "")))),
                "seller_landed_price_max_gbp": _fmt(_r2(_to_float(rec.get("landed_max", "")))),
                "seller_landed_price_median_gbp": _fmt(_r2(_to_float(rec.get("landed_median", "")))),
                "gap_to_best_landed_gbp": _fmt(_r2(_to_float(rec.get("gap_to_best", "")))),
                "min_delivery_days": _fmt(_r2(_to_float(rec.get("min_delivery_days", "")))),
                "prime_seen_flag": "1" if _to_int(rec.get("prime_seen", "")) == 1 else "0",
                "tier": tier,
                "tier_reason": reason,
                "source": SOURCE,
            }
            out_rows.append(row)
            if tier == "seller_of_interest":
                soi_rows.append(row)

    if not out_rows:
        return _write_empty_seller_profile_outputs("no_profile_rows_produced")

    profile_df = pd.DataFrame(out_rows, dtype=str).fillna("")
    profile_df = profile_df[profile_cols].sort_values(["sku", "rank_by_landed_price", "seller_id"], kind="stable")
    profile_df.to_csv(SELLER_PROFILE_PATH, index=False)

    soi_df = pd.DataFrame(soi_rows, dtype=str).fillna("")
    if soi_df.empty:
        soi_df = pd.DataFrame(columns=profile_cols)
    soi_skus = set(soi_df.get("sku", pd.Series([], dtype=str)).astype(str).str.strip().str.upper().tolist())
    asof_date = _norm(scoped.get("asof_date_key", pd.Series([], dtype=str)).astype(str).max())
    for sku in sorted({str(s).strip().upper() for s in active_skus if str(s).strip()}):
        if sku in soi_skus:
            continue
        soi_df = pd.concat(
            [
                soi_df,
                pd.DataFrame(
                    [
                        {
                            "snapshot_file": snapshot_path.name,
                            "asof_date": asof_date,
                            "marketplace": "UK",
                            "sku": sku,
                            "seller_id": "",
                            "offers_seen": "0",
                            "rank_by_landed_price": "",
                            "best_landed_price_gbp": "",
                            "seller_landed_price_latest_gbp": "",
                            "seller_landed_price_min_gbp": "",
                            "seller_landed_price_max_gbp": "",
                            "seller_landed_price_median_gbp": "",
                            "gap_to_best_landed_gbp": "",
                            "min_delivery_days": "",
                            "prime_seen_flag": "",
                            "tier": "seller_of_interest",
                            "tier_reason": "active_cohort_placeholder",
                            "source": SOURCE,
                        }
                    ],
                    dtype=str,
                ),
            ],
            ignore_index=True,
        )
    soi_df = soi_df[profile_cols].sort_values(["sku", "rank_by_landed_price", "seller_id"], kind="stable")
    soi_df.to_csv(SELLER_SOI_PATH, index=False)

    return {
        "seller_profile_snapshot": snapshot_path.name,
        "seller_profile_rows": str(len(profile_df.index)),
        "seller_soi_rows": str(len(soi_df.index)),
        "seller_soi_top_n": str(top_n),
        "seller_soi_max_gap_gbp": _fmt(max_gap),
        "seller_profile_status": "ok",
        "seller_profile_warn_reason": "",
    }


def _used_daily_down_move(event_log: pd.DataFrame, sku: str, asof_date: str) -> float:
    if event_log.empty:
        return 0.0
    e = event_log.copy()
    source_col = e.get("source", "").astype(str).str.strip()
    sku_col = e.get("sku", "").astype(str).str.strip().str.upper()
    asof_col = e.get("asof_date", "").astype(str).str.strip()
    subset = e.loc[source_col.eq(SOURCE) & sku_col.eq(sku.upper()) & asof_col.eq(asof_date)].copy()
    if subset.empty:
        return 0.0
    before = pd.to_numeric(subset.get("action_price_before_gbp", ""), errors="coerce")
    target = pd.to_numeric(subset.get("action_price_target_gbp", ""), errors="coerce")
    down = (before - target).clip(lower=0).fillna(0)
    return float(down.sum())


def _last_event_utc(event_log: pd.DataFrame, sku: str) -> datetime | None:
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


def _seller_id() -> str:
    sid = (
        os.environ.get("SELLER_ID")
        or os.environ.get("SELLER_PARTNER_ID")
        or os.environ.get("MERCHANT_ID")
        or os.environ.get("SELLING_PARTNER_ID")
        or ""
    )
    if sid:
        return sid
    return require_env("SELLER_ID")


def _resolve_marketplace_id(snapshot_row: Dict[str, str]) -> str:
    explicit = _norm(snapshot_row.get("marketplace_id", ""))
    if explicit:
        return explicit
    code = _norm(snapshot_row.get("marketplace", "")).upper()
    mapped = MARKETPLACE_CODE_TO_ID.get(code, "")
    if mapped:
        return mapped
    return os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")


def _load_product_db_row(sku: str) -> Dict[str, str]:
    if not PRODUCT_DB_PATH.exists():
        return {}
    try:
        df = pd.read_csv(PRODUCT_DB_PATH, dtype=str).fillna("")
    except Exception:
        return {}
    if df.empty:
        return {}
    sku_col = ""
    for c in ["seller_sku", "sku", "SKU"]:
        if c in df.columns:
            sku_col = c
            break
    if not sku_col:
        return {}
    key = df[sku_col].astype(str).str.strip().str.upper()
    one = df.loc[key.eq(sku.upper())]
    if one.empty:
        return {}
    return {k: _norm(v) for k, v in one.iloc[0].to_dict().items()}


def _h_floor_context() -> HFloorContext:
    return load_h_floor_context(
        product_db_path=PRODUCT_DB_PATH,
        token_ledger_path=TOKEN_LEDGER_PATH,
        token_cogs_path=TOKEN_COGS_LEDGER_PATH,
    )


def _product_db_max_price_gbp(sku: str) -> float | None:
    row = _load_product_db_row(sku)
    if not row:
        return None
    for col in [
        "max_price_gbp",
        "competitive_ceiling_gbp",
        "competitive_ceiling_price",
        "repricer_max_price_gbp",
        "ceiling_gbp",
    ]:
        val = _to_float(row.get(col, ""))
        if val is not None and val > 0:
            return float(val)
    return None


def _fallback_max_price_gbp_from_roi(sku: str, marketplace_id: str) -> Dict[str, str]:
    roi_pct = float(os.environ.get("H_MAX_PRICE_FALLBACK_ROI_PCT", "150") or "150")
    probe_price = float(os.environ.get("H_MAX_PRICE_FALLBACK_PROBE_GBP", "10") or "10")
    probe_price = max(probe_price, 0.01)
    fee = _estimate_level2_style_fees(sku, marketplace_id, probe_price, qty=1.0)
    vat_rate = _to_float(fee.get("vat_rate", "")) or VAT_DEFAULT
    cogs_ref = _load_sku_cogs_reference(sku, vat_rate)
    cogs_ex = _to_float(cogs_ref.get("cogs_exvat", "")) or 0.0

    candidate = probe_price
    details: Dict[str, str] = {}
    for _ in range(10):
        fee = _estimate_level2_style_fees(sku, marketplace_id, candidate, qty=1.0)
        fba_ex = _to_float(fee.get("fba_ex", "")) or 0.0
        comm_ex = _to_float(fee.get("comm_ex", "")) or 0.0
        dsf_ex = _to_float(fee.get("dsf_ex", "")) or 0.0
        fee_ex = abs(fba_ex) + abs(comm_ex) + abs(dsf_ex)
        cost_ex = cogs_ex + fee_ex
        required_profit_ex = cost_ex * max(roi_pct, 0.0) / 100.0
        required_revenue_ex = cost_ex + required_profit_ex
        required_total = _round_half_up(gross_from_exvat(required_revenue_ex, vat_rate, H_FLOOR_VAT_POLICY), 2)
        details = {
            "fallback_max_price_gbp": _fmt(required_total),
            "fallback_roi_pct": _fmt(roi_pct),
            "fallback_cost_exvat_gbp": _fmt(cost_ex),
            "fallback_required_profit_exvat_gbp": _fmt(required_profit_ex),
            "fallback_required_revenue_exvat_gbp": _fmt(required_revenue_ex),
            "fallback_cogs_exvat_gbp": _fmt(cogs_ex),
            "fallback_fee_fba_exvat_gbp": _fmt(fba_ex),
            "fallback_fee_commission_exvat_gbp": _fmt(comm_ex),
            "fallback_fee_dsf_exvat_gbp": _fmt(dsf_ex),
            "fallback_cogs_source": cogs_ref.get("source", ""),
        }
        if abs(required_total - candidate) < 0.01:
            break
        candidate = required_total
    return details


def _sku_vat_rate(product_row: Dict[str, str], marketplace_id: str) -> float:
    for fld in ["vat_rate", "last_vat_rate_pct", "last_vat_rate_candidate"]:
        raw = _to_float(product_row.get(fld, ""))
        if raw is None:
            continue
        rate = raw / 100.0 if raw > 1.0 else raw
        if rate > 0:
            return rate
    if MARKETPLACE_ID_TO_CODE.get(marketplace_id, "").upper() == "UK":
        return 0.2
    return VAT_DEFAULT


def _load_sku_cogs_reference(sku: str, vat_rate: float) -> Dict[str, str]:
    cogs_exvat = None
    source = ""
    if TOKEN_LEDGER_PATH.exists():
        try:
            t = pd.read_csv(TOKEN_LEDGER_PATH, dtype=str).fillna("")
            sku_col = t.get("seller_sku", "").astype(str).str.strip().str.upper()
            c = t.loc[sku_col.eq(sku.upper())].copy()
            if not c.empty:
                c["cost_num"] = pd.to_numeric(c.get("cost_per_unit", ""), errors="coerce")
                c["status_key"] = c.get("status", "").astype(str).str.strip().str.lower()
                c = c.loc[c["cost_num"].notna() & c["cost_num"].gt(0.0)].copy()
                if not c.empty:
                    available = c.loc[c["status_key"].eq("available")].copy()
                    base = available if not available.empty else c
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
                    base = base.sort_values(["sort_rank_num", "received_dt"], kind="stable")
                    cogs_exvat = float(base.iloc[0]["cost_num"])
                    source = "token_ledger_live_next_available" if not available.empty else "token_ledger_live_first_cost"
        except Exception:
            pass
    if cogs_exvat is None and TOKEN_COGS_LEDGER_PATH.exists():
        try:
            t = pd.read_csv(TOKEN_COGS_LEDGER_PATH, dtype=str).fillna("")
            sku_col = t.get("seller_sku", "").astype(str).str.strip().str.upper()
            c = t.loc[sku_col.eq(sku.upper())].copy()
            vals = pd.to_numeric(c.get("cogs_exvat", ""), errors="coerce").dropna()
            vals = vals[vals > 0]
            if not vals.empty:
                cogs_exvat = float(vals.median())
                source = "token_cogs_ledger_median"
        except Exception:
            pass
    if cogs_exvat is None:
        cogs_exvat = 0.0
        source = "missing_default_zero"
    cogs_total = _round_half_up(cogs_cost_from_exvat(cogs_exvat, vat_rate, H_FLOOR_VAT_POLICY), 2)
    cogs_vat = _round_half_up(max(cogs_total - cogs_exvat, 0.0), 2)
    return {
        "cogs_exvat": _fmt(cogs_exvat),
        "cogs_vat": _fmt(cogs_vat),
        "cogs_total": _fmt(cogs_total),
        "source": source,
    }


def _estimate_level2_style_fees(sku: str, marketplace_id: str, gross_price_gbp: float, qty: float = 1.0) -> Dict[str, str]:
    del marketplace_id  # shared floor resolver handles VAT from Product DB policy.
    qty = max(float(qty or 1.0), 1.0)
    unit_price = max(float(gross_price_gbp), 0.0) / qty

    inputs, _ = compute_h_floor_for_sku(sku, unit_price, context=_h_floor_context())

    source_to_rate_field = {
        "L3_BAND_10": "last_commission_pct_10",
        "L3_BAND_100": "last_commission_pct_100",
        "API_BAND_10": "referral_fee_10",
        "API_BAND_100": "referral_fee_100",
    }
    selected_rate_field = source_to_rate_field.get(_norm(inputs.source_referral), "")

    fba_ex = _round_half_up(float(inputs.fba_exvat_gbp) * qty, 2)
    comm_ex = _round_half_up(float(inputs.referral_amount_gbp) * qty, 2)
    dsf_ex = _round_half_up(float(inputs.digital_fee_exvat_gbp) * qty, 2)
    vat_rate = float(inputs.vat_rate)

    return {
        "vat_rate": _fmt(vat_rate),
        "fba_ex": _fmt(fba_ex),
        "fba_vat": _fmt(_round_half_up(fba_ex * vat_rate, 2)),
        "comm_ex": _fmt(comm_ex),
        "comm_vat": _fmt(_round_half_up(comm_ex * vat_rate, 2)),
        "dsf_ex": _fmt(dsf_ex),
        "dsf_vat": _fmt(_round_half_up(dsf_ex * vat_rate, 2)),
        "comm_rate": _fmt(inputs.referral_pct),
        "comm_rate_field": selected_rate_field,
        "comm_min_fee_applied": "1" if inputs.referral_min_fee_applied else "0",
        "reason_codes_csv": ",".join(inputs.reason_codes),
        "source_fba": _norm(inputs.source_fba),
        "source_referral": _norm(inputs.source_referral),
        "source_cogs": _norm(inputs.source_cogs),
        "band_bucket": _norm(inputs.band_bucket),
        "blocking_floor_input": "1" if has_blocking_reason_codes(inputs.reason_codes) else "0",
    }


def _profit_floor_price_gbp(sku: str, marketplace_id: str, proposed_total_gbp: float) -> Dict[str, str]:
    del marketplace_id
    candidate = max(float(proposed_total_gbp), 0.0)
    inputs, result = compute_h_floor_for_sku(sku, candidate, context=_h_floor_context())
    floor_total = _round_half_up(result.floor_total_gbp, 2)
    blocking = has_blocking_reason_codes(inputs.reason_codes)
    source_to_rate_field = {
        "L3_BAND_10": "last_commission_pct_10",
        "L3_BAND_100": "last_commission_pct_100",
        "API_BAND_10": "referral_fee_10",
        "API_BAND_100": "referral_fee_100",
    }
    commission_rate_field = source_to_rate_field.get(_norm(inputs.source_referral), "")

    append_h_floor_trace_rows(
        [
            build_h_floor_trace_row(
                inputs=inputs,
                result=result,
                source_script=SOURCE,
            )
        ]
    )

    details = {
        "required_total_gbp": _fmt(floor_total),
        "required_exvat_gbp": _fmt(result.sale_exvat_gbp),
        "required_profit_exvat_gbp": _fmt(inputs.margin_exvat_gbp),
        "roi_on_cost_pct": _fmt(10.0),
        "min_profit_exvat_gbp": _fmt(inputs.margin_exvat_gbp),
        "cogs_exvat_gbp": _fmt(inputs.cogs_exvat_gbp),
        "cogs_total_gbp": _fmt(inputs.cogs_exvat_gbp),
        "cogs_source": _norm(inputs.source_cogs),
        "fee_fba_exvat_gbp": _fmt(inputs.fba_exvat_gbp),
        "fee_commission_exvat_gbp": _fmt(inputs.referral_amount_gbp),
        "fee_dsf_exvat_gbp": _fmt(inputs.digital_fee_exvat_gbp),
        "fee_vat_rate": _fmt(inputs.vat_rate),
        "commission_rate_used": _fmt(inputs.referral_pct),
        "commission_rate_field": commission_rate_field,
        "commission_min_fee_applied": "1" if inputs.referral_min_fee_applied else "0",
        "blocking_floor_input": "1" if blocking else "0",
        "reason_codes_csv": ",".join(inputs.reason_codes),
        "referral_source": _norm(inputs.source_referral),
        "fba_source": _norm(inputs.source_fba),
        "band_bucket": _norm(inputs.band_bucket),
    }
    details["floor_total_gbp"] = _fmt(floor_total)
    return details


def _latest_l2_cost_break_even(sku: str) -> Dict[str, str]:
    path = OUT / "order_master.csv"
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
    for col in ["SKU", "lvl", "Date"]:
        if col not in df.columns:
            return {}
    rows = df.loc[
        df["SKU"].astype(str).str.strip().str.upper().eq(sku.upper())
        & df["lvl"].astype(str).str.strip().eq("2")
    ].copy()
    if rows.empty:
        return {}
    rows["date_key"] = pd.to_datetime(rows["Date"], errors="coerce", utc=True)
    rows = rows.sort_values(["date_key"], ascending=[False], kind="stable")
    latest = rows.iloc[0]
    price_exvat = _to_float(latest.get("Price_ExVAT", ""))
    price_total = _to_float(latest.get("Price_Total", ""))
    cogs_exvat = abs(_to_float(latest.get("COGS_ExVAT", "")) or 0.0)
    fba_fee_exvat = abs(_to_float(latest.get("FBA_Fee_ExVAT", "")) or 0.0)
    commission_exvat = abs(_to_float(latest.get("Commission_ExVAT", "")) or 0.0)
    digital_fee_exvat = abs(_to_float(latest.get("Digital_Fee_ExVAT", "")) or 0.0)
    fixed_closing_exvat = abs(_to_float(latest.get("FixedClosingFee_ExVAT", "")) or 0.0)
    break_even_exvat = cogs_exvat + fba_fee_exvat + commission_exvat + digital_fee_exvat + fixed_closing_exvat
    vat_mult = None
    if price_exvat is not None and price_total is not None and price_exvat > 0:
        vat_mult = price_total / price_exvat
    if vat_mult is None or vat_mult <= 0:
        vat_mult = 1.2
    break_even_total = break_even_exvat * vat_mult
    return {
        "l2_ref_order_id": _norm(latest.get("Order ID", "")),
        "l2_ref_order_utc": _norm(latest.get("Date", "")),
        "l2_ref_break_even_exvat_gbp": _fmt(_r2(break_even_exvat)),
        "l2_ref_break_even_total_gbp": _fmt(_r2(break_even_total)),
        "l2_ref_cogs_total_gbp": _fmt(_r2(abs(_to_float(latest.get("COGS_Total", "")) or 0.0))),
        "l2_ref_cogs_exvat_gbp": _fmt(_r2(cogs_exvat)),
        "l2_ref_fba_fee_exvat_gbp": _fmt(_r2(fba_fee_exvat)),
        "l2_ref_commission_exvat_gbp": _fmt(_r2(commission_exvat)),
        "l2_ref_digital_fee_exvat_gbp": _fmt(_r2(digital_fee_exvat)),
        "l2_ref_fixed_closing_exvat_gbp": _fmt(_r2(fixed_closing_exvat)),
    }


def _get_product_type(access_token: str, seller_id: str, sku: str, marketplace_id: str, run_id: str) -> str:
    url = f"{SPAPI_BASE_URL}/listings/2021-08-01/items/{seller_id}/{sku}"
    headers = {"x-amz-access-token": access_token, "Accept": "application/json"}
    params = {"marketplaceIds": marketplace_id, "includedData": "summaries"}
    ctx = SpApiCallContext(
        run_id=run_id,
        script_name=SOURCE,
        endpoint="listings_items_get_item",
        marketplace=marketplace_id,
        sku_count=1,
    )
    resp = spapi_get(
        ctx=ctx,
        url=url,
        spapi_base_url=SPAPI_BASE_URL,
        headers=headers,
        params=params,
        timeout=30,
        min_interval_sec=LISTINGS_ITEMS_READ_MIN_INTERVAL_SEC,
        max_retries=2,
    )
    if resp.status_code != 200:
        default_type = os.environ.get("H_DEFAULT_PRODUCT_TYPE", "PRODUCT")
        _log(f"product_type lookup failed sku={sku} status={resp.status_code}; using default={default_type}")
        return default_type
    payload = resp.json() or {}
    summaries = payload.get("summaries") or (payload.get("payload") or {}).get("summaries") or []
    if isinstance(summaries, list):
        for rec in summaries:
            if not isinstance(rec, dict):
                continue
            product_type = _norm(rec.get("productType", ""))
            if product_type:
                return product_type
    return os.environ.get("H_DEFAULT_PRODUCT_TYPE", "PRODUCT")


def _patch_listing_price(access_token: str, seller_id: str, sku: str, marketplace_id: str, target_price: float, run_id: str) -> dict:
    product_type = _get_product_type(access_token, seller_id, sku, marketplace_id, run_id)
    body_obj = {
        "productType": product_type,
        "patches": [
            {
                "op": "replace",
                "path": "/attributes/purchasable_offer",
                "value": [
                    {
                        "currency": "GBP",
                        "marketplace_id": marketplace_id,
                        "our_price": [{"schedule": [{"value_with_tax": round(float(target_price), 2)}]}],
                    }
                ],
            }
        ],
    }
    body = json.dumps(body_obj, ensure_ascii=True, separators=(",", ":"))
    url = f"{SPAPI_BASE_URL}/listings/2021-08-01/items/{seller_id}/{sku}"
    params = {"marketplaceIds": marketplace_id}
    headers = {
        "x-amz-access-token": access_token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    ctx = SpApiCallContext(
        run_id=run_id,
        script_name=SOURCE,
        endpoint="listings_items_patch_item",
        marketplace=marketplace_id,
        sku_count=1,
    )
    resp = spapi_patch_json(
        ctx=ctx,
        url=url,
        spapi_base_url=SPAPI_BASE_URL,
        headers=headers,
        params=params,
        body=body,
        timeout=30,
        min_interval_sec=LISTINGS_ITEMS_PATCH_MIN_INTERVAL_SEC,
        max_retries=2,
    )
    payload = {}
    try:
        payload = resp.json() or {}
    except Exception:
        payload = {}
    submission_id = _norm(payload.get("submissionId", ""))
    return {
        "ok": "1" if resp.status_code in (200, 202) else "0",
        "http_status": str(resp.status_code),
        "submission_id": submission_id,
        "response_text": _norm(resp.text),
    }


def _run_head(now_utc: datetime) -> dict:
    active_skus = load_active_lab_skus()
    if OFFICIAL_PILOT_SKU not in active_skus:
        raise RuntimeError(f"Head guardrail fail: pilot SKU not active in config/h_lab_cohort.csv: {OFFICIAL_PILOT_SKU}")
    boundary = _active_head_boundary_for_sku(OFFICIAL_PILOT_SKU)
    if not boundary:
        raise RuntimeError(f"Head guardrail fail: no active boundary for pilot SKU: {OFFICIAL_PILOT_SKU}")
    return {"head_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "head_sku_count": str(len(active_skus))}


def _run_supervisor(now_utc: datetime) -> dict:
    rule = _active_rule_for_sku(OFFICIAL_PILOT_SKU)
    if not rule:
        raise RuntimeError(f"Supervisor guardrail fail: no active tactical rule for pilot SKU: {OFFICIAL_PILOT_SKU}")
    seller_state = _build_seller_profiles()
    return {
        "supervisor_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "supervisor_state": _norm(rule.get("state", "unknown")).lower(),
        "supervisor_probe_type": _norm(rule.get("allowed_probe_type", "hold")).lower(),
        **seller_state,
    }


def _ensure_seller_delta_log() -> None:
    headers = [
        "asof_date",
        "updated_utc",
        "marketplace",
        "sku",
        "seller_id",
        "seller_mode",
        "learned_delta_gbp",
        "highest_delta_win_gbp",
        "lowest_delta_loss_gbp",
        "delta_gap_gbp",
        "delta_confidence",
        "last_validated_utc",
        "source",
        "notes",
    ]
    SELLER_DELTA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SELLER_DELTA_PATH.exists():
        with SELLER_DELTA_PATH.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(headers)
        return
    try:
        df = pd.read_csv(SELLER_DELTA_PATH, dtype=str).fillna("")
    except Exception:
        with SELLER_DELTA_PATH.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(headers)
        return
    missing = [c for c in headers if c not in df.columns]
    if missing:
        for col in missing:
            df[col] = ""
        df = df[headers]
        df.to_csv(SELLER_DELTA_PATH, index=False)


def _load_primary_soi_for_sku(sku: str) -> Dict[str, str]:
    path = SELLER_SOI_PATH if SELLER_SOI_PATH.exists() else SELLER_PROFILE_PATH
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
    if df.empty:
        return {}
    sku_key = df.get("sku", "").astype(str).str.strip().str.upper()
    one = df.loc[sku_key.eq(sku.upper())].copy()
    if one.empty:
        return {}
    rank = pd.to_numeric(one.get("rank_by_landed_price", ""), errors="coerce")
    one = one.assign(_rank=rank.fillna(999999.0))
    one = one.sort_values(["_rank", "seller_landed_price_latest_gbp"], kind="stable")
    return {k: _norm(v) for k, v in one.iloc[0].to_dict().items()}


def _load_seller_delta_row(sku: str, seller_id: str) -> Dict[str, str]:
    _ensure_seller_delta_log()
    try:
        df = pd.read_csv(SELLER_DELTA_PATH, dtype=str).fillna("")
    except Exception:
        return {}
    if df.empty:
        return {}
    sku_col = df.get("sku", "").astype(str).str.strip().str.upper()
    seller_col = df.get("seller_id", "").astype(str).str.strip()
    one = df.loc[sku_col.eq(sku.upper()) & seller_col.eq(_norm(seller_id))]
    if one.empty:
        return {}
    return {k: _norm(v) for k, v in one.iloc[-1].to_dict().items()}


def _delta_confidence_from_bounds(highest_win: float | None, lowest_loss: float | None) -> str:
    if highest_win is None:
        return "unknown"
    if lowest_loss is None:
        return "low"
    gap = abs(highest_win - lowest_loss)
    if gap <= 0.02:
        return "high"
    if gap <= 0.05:
        return "medium"
    return "low"


def _upsert_seller_delta_row(row: Dict[str, str]) -> None:
    _ensure_seller_delta_log()
    df = pd.read_csv(SELLER_DELTA_PATH, dtype=str).fillna("")
    one = pd.DataFrame([row], dtype=str).fillna("")
    for col in df.columns:
        if col not in one.columns:
            one[col] = ""
    one = one[df.columns]
    if df.empty:
        merged = one.copy()
    else:
        sku_col = df.get("sku", "").astype(str).str.strip().str.upper()
        seller_col = df.get("seller_id", "").astype(str).str.strip()
        keep = ~(sku_col.eq(_norm(row.get("sku", "")).upper()) & seller_col.eq(_norm(row.get("seller_id", ""))))
        merged = pd.concat([df.loc[keep].copy(), one], ignore_index=True)
    merged.to_csv(SELLER_DELTA_PATH, index=False)


def _run_executioner(now_utc: datetime, run_id: str, live_write: bool, state: dict) -> dict:
    snapshot_path = _latest_listing_snapshot()
    snapshot = pd.read_csv(snapshot_path, dtype=str).fillna("")
    sku_rows = snapshot.loc[snapshot.get("sku", "").astype(str).str.strip().str.upper().eq(OFFICIAL_PILOT_SKU)]
    if sku_rows.empty:
        _log("executioner_guardrail_violation pilot_sku_missing_from_snapshot")
        return {
            "executioner_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_probe_event_id": "",
            "executioner_probe_type": "hold",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "executioner_step_status": "failed_guardrail_pilot_sku_missing_from_snapshot",
            "executioner_step_error": f"pilot SKU not in snapshot {snapshot_path.name}",
        }
    row = {k: _norm(v) for k, v in sku_rows.iloc[0].to_dict().items()}
    soi = _load_primary_soi_for_sku(OFFICIAL_PILOT_SKU)
    seller_id_focus = _norm(soi.get("seller_id", ""))
    rival_landed_price = _to_float(soi.get("seller_landed_price_latest_gbp", ""))
    delta_row = _load_seller_delta_row(OFFICIAL_PILOT_SKU, seller_id_focus) if seller_id_focus else {}
    learned_delta = _to_float(delta_row.get("learned_delta_gbp", ""))
    highest_win = _to_float(delta_row.get("highest_delta_win_gbp", ""))
    lowest_loss = _to_float(delta_row.get("lowest_delta_loss_gbp", ""))
    seller_mode = ""

    max_snapshot_age_min = max(float(os.environ.get("H_MAX_SNAPSHOT_AGE_MINUTES", "20") or "20"), 1.0)
    listing_snapshot_age_min = _snapshot_age_minutes(_norm(row.get("timestamp_utc", "")), now_utc)
    seller_snapshot_meta = _latest_seller_snapshot_age_for_sku(OFFICIAL_PILOT_SKU, now_utc)
    seller_snapshot_age_min = _to_float(seller_snapshot_meta.get("seller_snapshot_age_minutes", ""))
    stale_snapshot = (
        listing_snapshot_age_min is None
        or seller_snapshot_age_min is None
        or listing_snapshot_age_min > max_snapshot_age_min
        or seller_snapshot_age_min > max_snapshot_age_min
    )

    boundary_refresh_forced = os.environ.get("H_FORCE_HEAD_BOUNDARY_REFRESH", "0").strip() == "1"
    today_key = now_utc.date().isoformat()
    lock_date = _norm(state.get("head_boundary_lock_date", ""))
    lock_payload = state.get("head_boundary_lock_payload", {})
    boundary_source = "head_boundary_daily_lock"
    if (
        (not boundary_refresh_forced)
        and lock_date == today_key
        and isinstance(lock_payload, dict)
        and bool(lock_payload)
    ):
        boundary = {str(k): _norm(v) for k, v in lock_payload.items()}
    else:
        boundary = _active_head_boundary_for_sku(OFFICIAL_PILOT_SKU)
        if boundary:
            state["head_boundary_lock_date"] = today_key
            state["head_boundary_lock_payload"] = {str(k): _norm(v) for k, v in boundary.items()}
            state["head_boundary_lock_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            state["head_boundary_lock_reason"] = "forced_refresh" if boundary_refresh_forced else "daily_refresh"
            boundary_source = "head_boundary_daily_refresh"
    rule = _active_rule_for_sku(OFFICIAL_PILOT_SKU)
    if not boundary:
        raise RuntimeError(f"Executioner guardrail fail: missing head boundary for {OFFICIAL_PILOT_SKU}")
    if not rule:
        raise RuntimeError(f"Executioner guardrail fail: missing supervisor rule for {OFFICIAL_PILOT_SKU}")

    before_price = _to_float(row.get("our_price", ""))
    buy_box_price = _to_float(row.get("buy_box_price", ""))
    if before_price is None:
        raise RuntimeError(f"Executioner guardrail fail: missing our_price for {OFFICIAL_PILOT_SKU}")
    buy_box_present_flag = _norm(row.get("buy_box_present_flag", ""))
    outcome_known_flag = _norm(row.get("outcome_known_flag", ""))
    we_present_flag = _norm(row.get("we_present_flag", ""))
    hold_blocker_reasons: List[str] = []
    if buy_box_present_flag != "1" or buy_box_price is None:
        hold_blocker_reasons.append("BUY_BOX_MISSING")
    if outcome_known_flag != "1":
        hold_blocker_reasons.append("OUTCOME_UNKNOWN")
    if we_present_flag != "1":
        hold_blocker_reasons.append("WE_NOT_PRESENT")
    hold_blocker = bool(hold_blocker_reasons)

    asof_date = _norm(row.get("asof_date", "")) or now_utc.date().isoformat()
    probe_event_id = f"h_cycle_{OFFICIAL_PILOT_SKU}_{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
    event_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    marketplace_id = _resolve_marketplace_id(row)

    hard_floor = _to_float(boundary.get("hard_floor_gbp", ""))
    manual_ceiling = _to_float(boundary.get("ceiling_gbp", ""))
    if hard_floor is None or hard_floor <= 0:
        hold_blocker_reasons.append("HEAD_FLOOR_MISSING")
    if manual_ceiling is None or manual_ceiling <= 0:
        hold_blocker_reasons.append("HEAD_CEILING_MISSING")
    hold_blocker = bool(hold_blocker_reasons)

    ceiling = manual_ceiling
    ceiling_source = boundary_source
    cpt_gbp = None
    cpt_ceiling = None
    cpt_status = "DISABLED_IN_H"
    cpt_multiplier = None
    fallback_ceiling = None
    product_db_ceiling = _product_db_max_price_gbp(OFFICIAL_PILOT_SKU)
    max_move = _to_float(boundary.get("max_move_per_cycle_gbp", ""))
    max_daily_down = _to_float(boundary.get("max_daily_down_move_gbp", ""))
    max_probes_per_day = _to_int(boundary.get("max_probes_per_day", ""))

    cooldown_boundary = _to_int(boundary.get("cooldown_minutes", "")) or 0
    cooldown_rule = _to_int(rule.get("cooldown_minutes", "")) or 0
    cooldown_minutes = max(cooldown_boundary, cooldown_rule, 1)

    expiry_minutes = _to_int(rule.get("expiry_minutes", ""))
    if expiry_minutes is None or expiry_minutes < 1:
        expiry_minutes = 240
    expiry_utc = (now_utc + timedelta(minutes=expiry_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

    probe_type = _norm(rule.get("allowed_probe_type", "hold")).lower() or "hold"
    target_adjust = _to_float(rule.get("target_adjustment_gbp", "")) or 0.0
    reason_codes: List[str] = ["phase1_live_pilot"]

    requested_probe_type = probe_type
    learn_step_down = max(_to_float(os.environ.get("H_LEARN_STEP_DOWN_GBP", "0.10")) or 0.10, 0.01)
    learn_step_up = max(_to_float(os.environ.get("H_LEARN_STEP_UP_GBP", "0.01")) or 0.01, 0.01)
    force_match_when_losing = os.environ.get("H_FORCE_MATCH_WHEN_LOSING", "1").strip() == "1"
    win_tolerance = max(_to_float(os.environ.get("H_DELTA_WIN_TOLERANCE_GBP", "0.01")) or 0.01, 0.0)
    observed_win_now = bool(
        buy_box_price is not None
        and before_price is not None
        and abs(before_price - buy_box_price) <= win_tolerance
    )
    delta_confidence_existing = _norm(delta_row.get("delta_confidence", "")).lower()
    if not seller_id_focus:
        seller_mode = "seller_unknown_learning"
    elif learned_delta is None:
        seller_mode = "new_seller_learning"
    elif delta_confidence_existing in {"high", "medium"} and observed_win_now:
        seller_mode = "apply_delta"
    else:
        seller_mode = "drift_retest_learning"
    if probe_type == "match":
        if buy_box_price is not None:
            target_price = buy_box_price
        else:
            target_price = before_price
            probe_type = "hold"
            reason_codes.append("buy_box_missing_fallback_hold")
    elif probe_type == "lower":
        target_price = before_price - target_adjust
    elif probe_type == "raise":
        target_price = before_price + target_adjust
    else:
        target_price = before_price
        probe_type = "hold"

    # Seller delta mode switch:
    # - unknown/new seller -> learning
    # - known seller, not revalidated today -> daily learning retest
    # - validated today -> apply learned delta
    if seller_mode == "apply_delta" and rival_landed_price is not None and learned_delta is not None:
        target_price = rival_landed_price + learned_delta
        probe_type = "apply_delta"
        reason_codes.append("seller_mode_apply_delta")
    elif seller_mode in {"new_seller_learning", "daily_retest_learning", "seller_unknown_learning"}:
        if observed_win_now:
            target_price = before_price + learn_step_up
            probe_type = "learn_up"
            reason_codes.append("seller_mode_learning_up")
        else:
            if force_match_when_losing and buy_box_price is not None:
                target_price = buy_box_price
                probe_type = "match"
                reason_codes.append("seller_mode_force_match_when_losing")
            else:
                target_price = before_price - learn_step_down
                probe_type = "learn_down"
                reason_codes.append("seller_mode_learning_down")

    pre_guardrail_target = target_price
    event_log = load_probe_event_log()
    last_event_time = _last_event_utc(event_log, OFFICIAL_PILOT_SKU)
    elapsed_minutes = None
    if last_event_time is not None:
        elapsed_minutes = (now_utc - last_event_time).total_seconds() / 60.0
        if elapsed_minutes < cooldown_minutes:
            target_price = before_price
            probe_type = "hold"
            reason_codes.append("cooldown_enforced")

    used_probes = 0
    # Probe budget: positive values enforce a daily cap; zero/negative disables cap.
    if max_probes_per_day is not None and max_probes_per_day > 0 and not event_log.empty:
        e = event_log.copy()
        source_col = e.get("source", "").astype(str).str.strip()
        sku_col = e.get("sku", "").astype(str).str.strip().str.upper()
        asof_col = e.get("asof_date", "").astype(str).str.strip()
        used_probes = int((source_col.eq(SOURCE) & sku_col.eq(OFFICIAL_PILOT_SKU) & asof_col.eq(asof_date)).sum())
        if used_probes >= max_probes_per_day:
            target_price = before_price
            probe_type = "hold"
            reason_codes.append("max_probes_per_day_enforced")

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
    used_down = 0.0
    remaining_daily_down = None
    if max_daily_down is not None and max_daily_down >= 0:
        used_down = _used_daily_down_move(event_log, OFFICIAL_PILOT_SKU, asof_date)
        remaining_daily_down = max(max_daily_down - used_down, 0.0)
        this_down = max(before_price - target_price, 0.0)
        if used_down + this_down > max_daily_down:
            allowed_this = max(max_daily_down - used_down, 0.0)
            target_price = before_price - allowed_this
            reason_codes.append("max_daily_down_enforced")

    required_floor = float(hard_floor) if hard_floor is not None and hard_floor > 0 else 0.0
    profit_floor = {
        "floor_total_gbp": _fmt(required_floor) if required_floor > 0 else "",
        "required_total_gbp": _fmt(required_floor) if required_floor > 0 else "",
        "required_exvat_gbp": "",
        "required_profit_exvat_gbp": "",
        "roi_on_cost_pct": "",
        "min_profit_exvat_gbp": "",
        "cogs_exvat_gbp": "",
        "cogs_total_gbp": "",
        "cogs_source": "HEAD_DAILY_BOUNDARY",
        "fee_fba_exvat_gbp": "",
        "fee_commission_exvat_gbp": "",
        "fee_dsf_exvat_gbp": "",
        "fee_vat_rate": "",
        "commission_rate_used": "",
        "commission_rate_field": "",
        "commission_min_fee_applied": "0",
        "blocking_floor_input": "0",
        "reason_codes_csv": "",
        "referral_source": "",
        "fba_source": "",
        "band_bucket": "",
    }
    if required_floor > 0 and target_price < required_floor:
        target_price = required_floor
        reason_codes.append("head_daily_floor_enforced")
        if ceiling is not None and target_price > ceiling:
            reason_codes.append("FLOOR_PRIORITY_CEILING_CONFLICT")
            if before_price < required_floor:
                reason_codes.append("FLOOR_PRIORITY_ENFORCED")
            else:
                target_price = before_price
                reason_codes.append("FLOOR_PRIORITY_ALREADY_SAFE_NO_WRITE")

    if abs(target_price - before_price) < 0.000001:
        probe_type = "hold"
    if stale_snapshot:
        target_price = before_price
        probe_type = "hold"
        reason_codes.append("stale_snapshot_hold")
    if hold_blocker:
        target_price = before_price
        probe_type = "hold"
        reason_codes.append("SUPPRESSION_OR_UNKNOWN_OUTCOME")

    should_write = live_write and probe_type != "hold" and abs(target_price - before_price) >= 0.000001
    if hold_blocker:
        should_write = False
    if _kill_switch_active():
        should_write = False
        reason_codes.append("kill_switch_active")

    write_ok = "0"
    http_status = ""
    submission_id = ""
    calc_trace = {
        "snapshot": snapshot_path.name,
        "seller_mode": seller_mode,
        "seller_focus_id": seller_id_focus,
        "seller_focus_rival_landed_gbp": _fmt(_r2(rival_landed_price)),
        "seller_learned_delta_gbp": _fmt(_r2(learned_delta)),
        "seller_highest_delta_win_gbp": _fmt(_r2(highest_win)),
        "seller_lowest_delta_loss_gbp": _fmt(_r2(lowest_loss)),
        "seller_observed_win_now": "1" if observed_win_now else "0",
        "learn_step_down_gbp": _fmt(_r2(learn_step_down)),
        "learn_step_up_gbp": _fmt(_r2(learn_step_up)),
        "before_gbp": _fmt(_r2(before_price)),
        "buy_box_gbp": _fmt(_r2(buy_box_price)),
        "buy_box_present_flag": buy_box_present_flag,
        "outcome_known_flag": outcome_known_flag,
        "we_present_flag": we_present_flag,
        "hold_blocker_flag": "1" if hold_blocker else "0",
        "hold_blocker_reasons": "|".join(hold_blocker_reasons),
        "requested_probe_type": requested_probe_type,
        "target_adjustment_gbp": _fmt(_r2(target_adjust)),
        "pre_guardrail_target_gbp": _fmt(_r2(pre_guardrail_target)),
        "final_target_gbp": _fmt(_r2(target_price)),
        "final_probe_type": probe_type,
        "cooldown_minutes": str(cooldown_minutes),
        "last_event_utc": last_event_time.strftime("%Y-%m-%dT%H:%M:%SZ") if last_event_time else "",
        "elapsed_since_last_event_minutes": _fmt(_r2(elapsed_minutes)),
        "max_probes_per_day": str(max_probes_per_day) if max_probes_per_day is not None else "",
        "used_probes_today": str(used_probes),
        "hard_floor_gbp": _fmt(_r2(hard_floor)),
        "ceiling_gbp": _fmt(_r2(ceiling)),
        "ceiling_source": ceiling_source,
        "head_boundary_lock_date": _norm(state.get("head_boundary_lock_date", "")),
        "head_boundary_lock_reason": _norm(state.get("head_boundary_lock_reason", "")),
        "manual_ceiling_gbp": _fmt(_r2(manual_ceiling)),
        "cpt_gbp": _fmt(_r2(cpt_gbp)),
        "cpt_ceiling_gbp": _fmt(_r2(cpt_ceiling)),
        "cpt_status": cpt_status,
        "cpt_ceiling_multiplier": _fmt(cpt_multiplier),
        "product_db_max_price_gbp": _fmt(_r2(product_db_ceiling)),
        "fallback_max_price_gbp": _fmt(_r2(fallback_ceiling)),
        "max_move_per_cycle_gbp": _fmt(_r2(max_move)),
        "max_daily_down_move_gbp": _fmt(_r2(max_daily_down)),
        "used_daily_down_move_gbp": _fmt(_r2(used_down)),
        "remaining_daily_down_move_gbp": _fmt(_r2(remaining_daily_down)),
        "live_write_enabled": "1" if live_write else "0",
        "kill_switch_active": "1" if _kill_switch_active() else "0",
        "snapshot_age_limit_minutes": _fmt(_r2(max_snapshot_age_min)),
        "listing_snapshot_file": snapshot_path.name,
        "listing_snapshot_age_minutes": _fmt(_r2(listing_snapshot_age_min)),
        "seller_snapshot_file": seller_snapshot_meta.get("seller_snapshot_file", ""),
        "seller_snapshot_age_minutes": _fmt(_r2(seller_snapshot_age_min)),
        "stale_snapshot_flag": "1" if stale_snapshot else "0",
        "profit_floor_total_gbp": profit_floor.get("floor_total_gbp", ""),
        "profit_floor_required_total_gbp": profit_floor.get("required_total_gbp", ""),
        "profit_floor_required_exvat_gbp": profit_floor.get("required_exvat_gbp", ""),
        "profit_floor_required_profit_exvat_gbp": profit_floor.get("required_profit_exvat_gbp", ""),
        "profit_floor_roi_on_cost_pct": profit_floor.get("roi_on_cost_pct", ""),
        "profit_floor_min_profit_exvat_gbp": profit_floor.get("min_profit_exvat_gbp", ""),
        "profit_floor_cogs_exvat_gbp": profit_floor.get("cogs_exvat_gbp", ""),
        "profit_floor_cogs_total_gbp": profit_floor.get("cogs_total_gbp", ""),
        "profit_floor_cogs_source": profit_floor.get("cogs_source", ""),
        "profit_floor_fee_fba_exvat_gbp": profit_floor.get("fee_fba_exvat_gbp", ""),
        "profit_floor_fee_commission_exvat_gbp": profit_floor.get("fee_commission_exvat_gbp", ""),
        "profit_floor_fee_dsf_exvat_gbp": profit_floor.get("fee_dsf_exvat_gbp", ""),
        "profit_floor_commission_rate_used": profit_floor.get("commission_rate_used", ""),
        "profit_floor_commission_rate_field": profit_floor.get("commission_rate_field", ""),
        "profit_floor_commission_min_fee_applied": profit_floor.get("commission_min_fee_applied", ""),
        "profit_floor_blocking_floor_input": profit_floor.get("blocking_floor_input", "0"),
        "profit_floor_reason_codes_csv": profit_floor.get("reason_codes_csv", ""),
        "profit_floor_referral_source": profit_floor.get("referral_source", ""),
        "profit_floor_fba_source": profit_floor.get("fba_source", ""),
        "profit_floor_band_bucket": profit_floor.get("band_bucket", ""),
        "l2_ref_order_id": "",
        "l2_ref_order_utc": "",
        "l2_ref_break_even_exvat_gbp": "",
        "l2_ref_break_even_total_gbp": "",
        "l2_ref_cogs_total_gbp": "",
        "l2_ref_cogs_exvat_gbp": "",
        "l2_ref_fba_fee_exvat_gbp": "",
        "l2_ref_commission_exvat_gbp": "",
        "l2_ref_digital_fee_exvat_gbp": "",
        "l2_ref_fixed_closing_exvat_gbp": "",
    }
    notes = f"calc_trace={json.dumps(calc_trace, ensure_ascii=True, separators=(',', ':'))}"
    executed_price = before_price

    if should_write:
        load_dotenv_if_missing()
        access_token = get_lwa_access_token()
        seller_id = _seller_id()
        result = _patch_listing_price(
            access_token=access_token,
            seller_id=seller_id,
            sku=OFFICIAL_PILOT_SKU,
            marketplace_id=marketplace_id,
            target_price=target_price,
            run_id=run_id,
        )
        write_ok = _norm(result.get("ok", "0"))
        http_status = _norm(result.get("http_status", ""))
        submission_id = _norm(result.get("submission_id", ""))
        if write_ok == "1":
            executed_price = target_price
            reason_codes.append("live_write_applied")
        else:
            reason_codes.append("live_write_failed")
            _arm_kill_switch(f"patch_failed status={http_status} sku={OFFICIAL_PILOT_SKU}")
            notes = f"{notes}|patch_failed={_norm(result.get('response_text', ''))[:180]}"
    else:
        reason_codes.append("live_write_skipped")

    approved_rule_id = (
        f"{_norm(rule.get('state', 'unknown')).lower()}|"
        f"{_norm(rule.get('trigger_code', 'baseline_check')).lower()}|"
        f"{probe_type}"
    )
    event_row = {
        "probe_event_id": probe_event_id,
        "asof_date": asof_date,
        "event_utc": event_utc,
        "marketplace": _norm(row.get("marketplace", "")),
        "sku": OFFICIAL_PILOT_SKU,
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
        "notes": notes,
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
                "sku": OFFICIAL_PILOT_SKU,
                "asin": _norm(row.get("asin", "")),
                "competitor_moved_flag": "0",
                "competitor_move_direction": "flat",
                "competitor_move_size_gbp": "0.00",
                "reaction_lag_minutes": "",
                "buy_box_price_gbp_after": _norm(row.get("buy_box_price", "")),
                "buy_box_channel_after": _norm(row.get("buy_box_channel", "")),
                "buy_box_owner_after": "",
                "our_price_gbp_after": _fmt(executed_price),
                "outcome_code": "pending_observation",
                "source": SOURCE,
                "notes": "executioner_placeholder_response_window",
            }
        )

    initialize_probe_logs()
    append_probe_events([event_row])
    append_probe_responses(response_rows)
    _append_action_log(
        {
            "run_id": run_id,
            "event_utc": event_utc,
            "sku": OFFICIAL_PILOT_SKU,
            "marketplace_id": marketplace_id,
            "probe_event_id": probe_event_id,
            "probe_type": probe_type,
            "price_before_gbp": _fmt(before_price),
            "price_target_gbp": _fmt(target_price),
            "price_executed_gbp": _fmt(executed_price),
            "live_write_attempted": "1" if should_write else "0",
            "live_write_success": write_ok,
            "http_status": http_status,
            "submission_id": submission_id,
            "reason_codes": "|".join(reason_codes),
            "source": SOURCE,
            "notes": notes,
        }
    )
    _append_live_test_execution_log(
        {
            "event_ts_utc": event_utc,
            "sku": OFFICIAL_PILOT_SKU,
            "state": _norm(rule.get("state", "unknown")).upper(),
            "old_price_gbp": _fmt(before_price),
            "new_price_gbp": _fmt(target_price),
            "write_status": "APPLIED" if write_ok == "1" else ("DRY_RUN_NO_WRITE" if not should_write else "WRITE_FAILED"),
            "write_error": "" if write_ok == "1" else _norm(http_status or ""),
            "final_ceiling_landed_gbp": _fmt(_r2(ceiling)),
            "hard_floor_gbp": _fmt(_r2(hard_floor)),
            "profit_floor_required_total_gbp": profit_floor.get("required_total_gbp", ""),
            "effective_floor_gbp": _fmt(
                _r2(
                    max(
                        _to_float(profit_floor.get("required_total_gbp", "")) or 0.0,
                        _to_float(hard_floor) or 0.0,
                    )
                )
            ),
            "profit_floor_cogs_exvat_gbp": profit_floor.get("cogs_exvat_gbp", ""),
            "profit_floor_cogs_total_gbp": profit_floor.get("cogs_total_gbp", ""),
            "reason_codes_json": json.dumps(reason_codes, ensure_ascii=True, separators=(",", ":")),
        }
    )

    # Update seller delta learning memory from current observation.
    # This is a lightweight online update and gets refined by repeated cycles.
    floor_ceiling_conflict = "FLOOR_PRIORITY_CEILING_CONFLICT" in reason_codes
    if (not hold_blocker) and (not floor_ceiling_conflict) and seller_id_focus and rival_landed_price is not None and before_price is not None:
        observed_delta = before_price - rival_landed_price
        if observed_win_now:
            if highest_win is None:
                highest_win = observed_delta
            else:
                highest_win = max(highest_win, observed_delta)
        else:
            if lowest_loss is None:
                lowest_loss = observed_delta
            else:
                lowest_loss = min(lowest_loss, observed_delta)
        learned_out = highest_win if highest_win is not None else learned_delta
        gap = abs(highest_win - lowest_loss) if highest_win is not None and lowest_loss is not None else None
        confidence = _delta_confidence_from_bounds(highest_win, lowest_loss)
        mode_out = "apply_delta" if (learned_out is not None and confidence in {"high", "medium"}) else "learn"
        _upsert_seller_delta_row(
            {
                "asof_date": asof_date,
                "updated_utc": event_utc,
                "marketplace": _norm(row.get("marketplace", "")),
                "sku": OFFICIAL_PILOT_SKU,
                "seller_id": seller_id_focus,
                "seller_mode": mode_out,
                "learned_delta_gbp": _fmt(_r2(learned_out)),
                "highest_delta_win_gbp": _fmt(_r2(highest_win)),
                "lowest_delta_loss_gbp": _fmt(_r2(lowest_loss)),
                "delta_gap_gbp": _fmt(_r2(gap)),
                "delta_confidence": confidence,
                "last_validated_utc": event_utc if mode_out == "apply_delta" else _norm(delta_row.get("last_validated_utc", "")),
                "source": SOURCE,
                "notes": f"observed_win_now={'1' if observed_win_now else '0'}",
            }
        )

    if hold_blocker:
        _log(
            "reason=SUPPRESSION_OR_UNKNOWN_OUTCOME "
            f"sku={OFFICIAL_PILOT_SKU} asin={_norm(row.get('asin', ''))} "
            f"buy_box_present={buy_box_present_flag} buy_box_price={_fmt(_r2(buy_box_price))} "
            f"outcome_known={outcome_known_flag} we_present={we_present_flag} "
            f"event_utc={event_utc}"
        )
    else:
        _log(
            "executioner sku="
            f"{OFFICIAL_PILOT_SKU} probe_type={probe_type} before={_fmt(before_price)} target={_fmt(target_price)} "
            f"live_write_attempted={'1' if should_write else '0'} live_write_success={write_ok} http_status={http_status}"
        )
    return {
        "executioner_ran_utc": event_utc,
        "executioner_probe_event_id": probe_event_id,
        "executioner_probe_type": probe_type,
        "executioner_live_write_attempted": "1" if should_write else "0",
        "executioner_live_write_success": write_ok,
    }


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run H pricing cycle")
    parser.add_argument("--phase1-pilot", action="store_true", help="Activate Phase 1 pilot mode")
    parser.add_argument("--phase1-config", default="", help="Path to Phase 1 pilot YAML config")
    parser.add_argument(
        "--run-once",
        action="store_true",
        default=os.environ.get("H_RUN_ONCE", "0").strip() == "1",
        help="Execute one cycle then exit",
    )
    parser.add_argument(
        "--sleep-minutes",
        type=int,
        default=15,
        help="Sleep between cycles when looping (Phase 1 pilot mode)",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Force read-only mode (disable live writes regardless of config)",
    )
    parser.add_argument(
        "--only-stage",
        choices=list(STAGE_NAMES),
        default="",
        help="Run only one phase1 stage for deterministic bisect",
    )
    parser.add_argument(
        "--skip-stage",
        action="append",
        choices=list(STAGE_NAMES),
        default=[],
        help="Skip a phase1 stage for deterministic bisect (repeatable)",
    )
    return parser.parse_args()


def _run_phase1_pilot_subprocess(
    *,
    now_utc: datetime,
    run_id: str,
    config_path: str,
    read_only: bool,
    stage_env: dict[str, str] | None = None,
) -> dict[str, str]:
    requested_pilot_mode = _effective_phase1_mode(H_PHASE1_PILOT_MODE)
    pilot_mode = "subprocess" if requested_pilot_mode == "inline" else requested_pilot_mode
    pilot_script = resolve_script_path(ROOT / "scripts", "H110_run_phase1_h_pilot.py")
    pilot_argv = [
        str(pilot_script),
        "--phase1-config",
        str(config_path),
        "--run-id",
        run_id,
        "--now-utc",
        now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ]
    if read_only:
        pilot_argv.append("--read-only")
    progress_path = H_LIVE_DIR / "phase1_pilot_step.progress.log"
    attempt_token = time.time_ns()
    result_path = H_LIVE_DIR / f"phase1_pilot_step.result.{run_id}.{os.getpid()}.{attempt_token}.json"
    completion_marker_path = H_LIVE_DIR / f"phase1_pilot_step.complete.{run_id}.{os.getpid()}.{attempt_token}.json"
    try:
        if progress_path.exists():
            progress_path.unlink()
    except Exception:
        pass
    try:
        if result_path.exists():
            result_path.unlink()
    except Exception:
        pass
    try:
        if completion_marker_path.exists():
            completion_marker_path.unlink()
    except Exception:
        pass

    if requested_pilot_mode == "inline":
        _log(
            "phase1 pilot_step mode_override "
            "requested=inline effective=subprocess "
            "reason=inline_pilot_can_short_circuit_parent_before_publish"
        )

    cmd = [sys.executable, "-u", *pilot_argv]
    heartbeat_every_seconds = 30.0
    poll_seconds = 5.0
    _log(
        "phase1 pilot_step start "
        f"mode={pilot_mode} "
        f"requested_mode={requested_pilot_mode} "
        "stdio_mode=result_file_only "
        f"stall_timeout_seconds={int(PHASE1_PILOT_STALL_TIMEOUT_SECONDS)} "
        f"max_timeout_seconds={int(PHASE1_PILOT_MAX_TIMEOUT_SECONDS)} "
        f"read_only={'1' if read_only else '0'} "
        f"progress_path={progress_path} "
        f"result_path={result_path} "
        f"completion_marker_path={completion_marker_path}"
    )
    start_monotonic = time.monotonic()
    last_heartbeat = start_monotonic
    last_progress_change = start_monotonic
    last_progress_tail = _tail_line(progress_path)
    env = os.environ.copy()
    env["H_RUN_ID"] = str(run_id)
    env["H_PHASE1_PROGRESS_PATH"] = str(progress_path)
    env["H_PHASE1_RESULT_PATH"] = str(result_path)
    env["H_PHASE1_COMPLETION_MARKER_PATH"] = str(completion_marker_path)
    env.update(stage_env or {})
    stdout_log_path = H_LIVE_DIR / f"phase1_pilot_step.stdout.{run_id}.{os.getpid()}.{attempt_token}.log"
    stderr_log_path = H_LIVE_DIR / f"phase1_pilot_step.stderr.{run_id}.{os.getpid()}.{attempt_token}.log"
    proc: subprocess.Popen | None = None

    def _collect_wait_contract_snapshot() -> dict[str, str]:
        marker_status = ""
        marker_result_ok = ""
        result_exists = "0"
        result_candidate = result_path
        marker_exists = "0"
        child_state = "unknown"
        boundary_status = _norm(_ACTIVE_PHASE1_INTEL_BOUNDARY.get("status", ""))
        if proc is not None:
            rc_now = proc.poll()
            if rc_now is None:
                child_state = "running"
            else:
                child_state = f"exited_rc_{rc_now}"
        try:
            marker_present = completion_marker_path.exists()
            marker_exists = "1" if marker_present else "0"
            if marker_present:
                marker_raw = json.loads(completion_marker_path.read_text(encoding="utf-8"))
                if isinstance(marker_raw, dict):
                    marker_status = _norm(marker_raw.get("status", "")).lower()
                    marker_result_ok = _norm(marker_raw.get("result_ok", ""))
        except Exception:
            marker_status = "invalid_json"
        try:
            if result_candidate.exists():
                result_exists = "1"
            else:
                for candidate in sorted(
                    H_LIVE_DIR.glob(f"phase1_pilot_step.result.{run_id}.*.json"),
                    key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
                    reverse=True,
                ):
                    try:
                        if int(candidate.stat().st_size) <= 0:
                            continue
                    except Exception:
                        continue
                    result_exists = "1"
                    break
        except Exception:
            result_exists = "0"
        return {
            "run_id": _norm(run_id),
            "child_pid": _norm(proc.pid if proc is not None else ""),
            "last_known_child_state": child_state,
            "result_exists": result_exists,
            "marker_exists": marker_exists,
            "marker_status": marker_status,
            "result_ok": marker_result_ok,
            "boundary_status": boundary_status,
        }

    def _write_pilot_wait_abnormal_cause(*, reason: str, detail: str = "") -> Path | None:
        try:
            evidence = _collect_wait_contract_snapshot()
            payload = {
                "utc": _ts(),
                "run_id": _norm(run_id),
                "parent_pid": str(os.getpid()),
                "reason": _norm(reason),
                "detail": _norm(detail),
                "wait_checkpoint": "pilot_wait_exit_abnormal",
                "child_pid": evidence.get("child_pid", ""),
                "last_known_child_state": evidence.get("last_known_child_state", ""),
                "result_exists": evidence.get("result_exists", ""),
                "marker_exists": evidence.get("marker_exists", ""),
                "marker_status": evidence.get("marker_status", ""),
                "result_ok": evidence.get("result_ok", ""),
                "boundary_status": evidence.get("boundary_status", ""),
                "completion_marker_path": str(completion_marker_path),
                "result_path": str(result_path),
            }
            cause_path = H_LIVE_DIR / f"phase1_pilot_wait_abnormal.{run_id}.{attempt_token}.json"
            _write_json(cause_path, payload)
            return cause_path
        except Exception:
            return None

    def _kill_phase1_pilot_process_tree() -> None:
        if proc is None:
            return
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except Exception as exc:
            _log(
                "phase1 pilot_step tree_kill_failed "
                f"child_pid={proc.pid} "
                f"error={type(exc).__name__}:{exc}"
            )

    with stdout_log_path.open("wb") as child_stdout, stderr_log_path.open("wb") as child_stderr:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=child_stdout,
            stderr=child_stderr,
            env=env,
        )
        _write_watchdog_marker(
            name="WATCHDOG_ENTER.txt",
            log_prefix="phase1_pilot_step",
            details=f"pid={proc.pid} cmd={' '.join(str(part) for part in cmd)}",
        )
        _log(f"phase1 pilot_step child_started pid={proc.pid} run_id={run_id}")
        _write_runtime_status(
            "RUNNING",
            run_id=run_id,
            stage="phase1_pilot",
            detail=f"pilot_child_running pid={proc.pid} elapsed_seconds=0.00 stalled_seconds=0.00",
        )
        _set_active_phase1_pilot_wait(
            run_id=run_id,
            status="entered",
            wait_checkpoint="pilot_wait_enter",
            child_pid=proc.pid,
            detail="child_wait_started",
            last_known_child_state="running",
            result_exists="0",
            marker_status="",
            result_ok="",
            boundary_status=_norm(_ACTIVE_PHASE1_INTEL_BOUNDARY.get("status", "")),
        )
        wait_enter_snapshot = _collect_wait_contract_snapshot()
        _append_h_parent_trace(
            "pilot_wait_enter",
            run_id=run_id,
            child_pid=proc.pid,
            result_path=result_path,
            completion_marker_path=completion_marker_path,
            last_known_child_state=wait_enter_snapshot.get("last_known_child_state", ""),
            result_exists=wait_enter_snapshot.get("result_exists", "0"),
            marker_status=wait_enter_snapshot.get("marker_status", ""),
            result_ok=wait_enter_snapshot.get("result_ok", ""),
            boundary_status=wait_enter_snapshot.get("boundary_status", ""),
        )
        _log(
            "phase1 pilot_wait_enter "
            f"run_id={run_id} "
            f"child_pid={proc.pid} "
            f"poll_seconds={_fmt(_r2(poll_seconds))} "
            f"heartbeat_every_seconds={_fmt(_r2(heartbeat_every_seconds))}"
        )

        try:
            while True:
                try:
                    proc.wait(timeout=poll_seconds)
                    break
                except subprocess.TimeoutExpired:
                    elapsed = time.monotonic() - start_monotonic
                    progress_tail = _tail_line(progress_path)
                    progress_advanced = progress_tail != last_progress_tail
                    if progress_advanced:
                        last_progress_change = time.monotonic()
                        last_progress_tail = progress_tail
                    stalled_for = time.monotonic() - last_progress_change
                    timeout_reason = ""
                    timeout_limit = 0.0
                    if elapsed >= PHASE1_PILOT_MAX_TIMEOUT_SECONDS:
                        timeout_reason = "max_runtime"
                        timeout_limit = PHASE1_PILOT_MAX_TIMEOUT_SECONDS
                    elif stalled_for >= PHASE1_PILOT_STALL_TIMEOUT_SECONDS:
                        timeout_reason = "stall"
                        timeout_limit = PHASE1_PILOT_STALL_TIMEOUT_SECONDS
                    if timeout_reason:
                        timeout_snapshot = _collect_wait_contract_snapshot()
                        _set_active_phase1_pilot_wait(
                            run_id=run_id,
                            status="abnormal_exit",
                            wait_checkpoint="pilot_wait_abnormal_exit",
                            child_pid=proc.pid,
                            detail=f"timeout_reason={timeout_reason}",
                            last_known_child_state=timeout_snapshot.get("last_known_child_state", ""),
                            result_exists=timeout_snapshot.get("result_exists", "0"),
                            marker_status=timeout_snapshot.get("marker_status", ""),
                            result_ok=timeout_snapshot.get("result_ok", ""),
                            boundary_status=timeout_snapshot.get("boundary_status", ""),
                        )
                        cause_path = _write_pilot_wait_abnormal_cause(
                            reason=f"timeout_{timeout_reason}",
                            detail=(
                                f"elapsed_seconds={_fmt(_r2(elapsed))} "
                                f"stalled_seconds={_fmt(_r2(stalled_for))}"
                            ),
                        )
                        _append_h_parent_trace(
                            "pilot_wait_exit_abnormal",
                            run_id=run_id,
                            child_pid=proc.pid,
                            reason=f"timeout_{timeout_reason}",
                            elapsed_seconds=_fmt(_r2(elapsed)),
                            stalled_seconds=_fmt(_r2(stalled_for)),
                            progress_tail=progress_tail,
                            last_known_child_state=timeout_snapshot.get("last_known_child_state", ""),
                            result_exists=timeout_snapshot.get("result_exists", "0"),
                            marker_status=timeout_snapshot.get("marker_status", ""),
                            result_ok=timeout_snapshot.get("result_ok", ""),
                            boundary_status=timeout_snapshot.get("boundary_status", ""),
                            cause_artifact_path=str(cause_path) if cause_path else "",
                        )
                        _log(
                            "phase1 pilot_wait_exit_abnormal "
                            f"run_id={run_id} "
                            f"child_pid={proc.pid} "
                            f"reason=timeout_{timeout_reason} "
                            f"elapsed_seconds={_fmt(_r2(elapsed))} "
                            f"stalled_seconds={_fmt(_r2(stalled_for))} "
                            f"progress_tail={progress_tail} "
                            f"last_known_child_state={timeout_snapshot.get('last_known_child_state', '')} "
                            f"result_exists={timeout_snapshot.get('result_exists', '0')} "
                            f"marker_status={timeout_snapshot.get('marker_status', '') or 'none'} "
                            f"result_ok={timeout_snapshot.get('result_ok', '') or 'none'} "
                            f"boundary_status={timeout_snapshot.get('boundary_status', '') or 'none'} "
                            f"cause_artifact_path={str(cause_path) if cause_path else 'none'}"
                        )
                        _write_watchdog_kill_marker(
                            log_prefix="phase1_pilot_step",
                            pid=proc.pid,
                            elapsed_seconds=elapsed,
                            timeout_seconds=timeout_limit,
                            cmd=cmd,
                        )
                        _kill_phase1_pilot_process_tree()
                        proc.wait(timeout=15)
                        _write_watchdog_marker(
                            name="WATCHDOG_EXIT.txt",
                            log_prefix="phase1_pilot_step",
                            details=f"rc=124 reason=timeout_kill timeout_reason={timeout_reason}",
                        )
                        raise RuntimeError(
                            "phase1 pilot step timeout "
                            f"reason={timeout_reason} "
                            f"elapsed_seconds={_fmt(_r2(elapsed))} "
                            f"stalled_seconds={_fmt(_r2(stalled_for))} "
                            f"stall_timeout_seconds={int(PHASE1_PILOT_STALL_TIMEOUT_SECONDS)} "
                            f"max_timeout_seconds={int(PHASE1_PILOT_MAX_TIMEOUT_SECONDS)} "
                            f"progress_tail={progress_tail}"
                        )
                    if elapsed - last_heartbeat >= heartbeat_every_seconds:
                        poll_snapshot = _collect_wait_contract_snapshot()
                        _set_active_phase1_pilot_wait(
                            run_id=run_id,
                            status="active",
                            wait_checkpoint="pilot_wait_poll",
                            child_pid=proc.pid,
                            detail=(
                                f"elapsed_seconds={_fmt(_r2(elapsed))} "
                                f"stalled_seconds={_fmt(_r2(stalled_for))} "
                                f"progress_advanced={'1' if progress_advanced else '0'}"
                            ),
                            last_known_child_state=poll_snapshot.get("last_known_child_state", ""),
                            result_exists=poll_snapshot.get("result_exists", "0"),
                            marker_status=poll_snapshot.get("marker_status", ""),
                            result_ok=poll_snapshot.get("result_ok", ""),
                            boundary_status=poll_snapshot.get("boundary_status", ""),
                        )
                        _append_h_parent_trace(
                            "pilot_wait_poll",
                            run_id=run_id,
                            child_pid=proc.pid,
                            elapsed_seconds=_fmt(_r2(elapsed)),
                            stalled_seconds=_fmt(_r2(stalled_for)),
                            progress_advanced="1" if progress_advanced else "0",
                            last_known_child_state=poll_snapshot.get("last_known_child_state", ""),
                            result_exists=poll_snapshot.get("result_exists", "0"),
                            marker_status=poll_snapshot.get("marker_status", ""),
                            result_ok=poll_snapshot.get("result_ok", ""),
                            boundary_status=poll_snapshot.get("boundary_status", ""),
                        )
                        _write_runtime_status(
                            "RUNNING",
                            run_id=run_id,
                            stage="phase1_pilot",
                            detail=(
                                "pilot_child_running "
                                f"pid={proc.pid} "
                                f"elapsed_seconds={_fmt(_r2(elapsed))} "
                                f"stalled_seconds={_fmt(_r2(stalled_for))} "
                                f"progress_advanced={'1' if progress_advanced else '0'}"
                            ),
                        )
                        _log(
                            "phase1 pilot_wait_poll "
                            f"run_id={run_id} "
                            f"elapsed_seconds={_fmt(_r2(elapsed))} "
                            f"stalled_seconds={_fmt(_r2(stalled_for))} "
                            f"progress_advanced={'1' if progress_advanced else '0'} "
                            f"child_pid={proc.pid} "
                            f"progress_tail={progress_tail} "
                            f"last_known_child_state={poll_snapshot.get('last_known_child_state', '')} "
                            f"result_exists={poll_snapshot.get('result_exists', '0')} "
                            f"marker_status={poll_snapshot.get('marker_status', '') or 'none'} "
                            f"result_ok={poll_snapshot.get('result_ok', '') or 'none'} "
                            f"boundary_status={poll_snapshot.get('boundary_status', '') or 'none'}"
                        )
                        last_heartbeat = time.monotonic()
        except BaseException as exc:
            exit_code = _system_exit_code(exc)
            reason = (
                f"system_exit_{exit_code}" if isinstance(exc, SystemExit) else f"{type(exc).__name__}:{exc}"
            )
            progress_tail = _tail_line(progress_path)
            exception_snapshot = _collect_wait_contract_snapshot()
            _set_active_phase1_pilot_wait(
                run_id=run_id,
                status="abnormal_exit",
                wait_checkpoint="pilot_wait_abnormal_exit",
                child_pid=proc.pid,
                detail=reason,
                last_known_child_state=exception_snapshot.get("last_known_child_state", ""),
                result_exists=exception_snapshot.get("result_exists", "0"),
                marker_status=exception_snapshot.get("marker_status", ""),
                result_ok=exception_snapshot.get("result_ok", ""),
                boundary_status=exception_snapshot.get("boundary_status", ""),
            )
            cause_path = _write_pilot_wait_abnormal_cause(reason=reason, detail=f"progress_tail={progress_tail}")
            _append_h_parent_trace(
                "pilot_wait_exit_abnormal",
                run_id=run_id,
                child_pid=proc.pid,
                reason=reason,
                progress_tail=progress_tail,
                last_known_child_state=exception_snapshot.get("last_known_child_state", ""),
                result_exists=exception_snapshot.get("result_exists", "0"),
                marker_status=exception_snapshot.get("marker_status", ""),
                result_ok=exception_snapshot.get("result_ok", ""),
                boundary_status=exception_snapshot.get("boundary_status", ""),
                cause_artifact_path=str(cause_path) if cause_path else "",
            )
            _log(
                "phase1 pilot_wait_exit_abnormal "
                f"run_id={run_id} "
                f"child_pid={proc.pid} "
                f"reason={reason} "
                f"progress_tail={progress_tail} "
                f"last_known_child_state={exception_snapshot.get('last_known_child_state', '')} "
                f"result_exists={exception_snapshot.get('result_exists', '0')} "
                f"marker_status={exception_snapshot.get('marker_status', '') or 'none'} "
                f"result_ok={exception_snapshot.get('result_ok', '') or 'none'} "
                f"boundary_status={exception_snapshot.get('boundary_status', '') or 'none'} "
                f"cause_artifact_path={str(cause_path) if cause_path else 'none'}"
            )
            _write_runtime_status(
                "ERROR",
                run_id=run_id,
                stage="phase1_pilot",
                detail=(
                    f"pilot_wait_exit_abnormal child_pid={proc.pid} reason={reason} "
                    f"cause_artifact_path={str(cause_path) if cause_path else 'none'}"
                ),
            )
            raise

    exit_snapshot = _collect_wait_contract_snapshot()
    _set_active_phase1_pilot_wait(
        run_id=run_id,
        status="exited_normal",
        wait_checkpoint="pilot_wait_exit_normal",
        child_pid=proc.pid if proc is not None else "",
        detail="child_wait_completed",
        last_known_child_state=exit_snapshot.get("last_known_child_state", ""),
        result_exists=exit_snapshot.get("result_exists", "0"),
        marker_status=exit_snapshot.get("marker_status", ""),
        result_ok=exit_snapshot.get("result_ok", ""),
        boundary_status=exit_snapshot.get("boundary_status", ""),
    )
    _append_h_parent_trace(
        "pilot_wait_exit_normal",
        run_id=run_id,
        child_pid=proc.pid if proc is not None else "",
        last_known_child_state=exit_snapshot.get("last_known_child_state", ""),
        result_exists=exit_snapshot.get("result_exists", "0"),
        marker_status=exit_snapshot.get("marker_status", ""),
        result_ok=exit_snapshot.get("result_ok", ""),
        boundary_status=exit_snapshot.get("boundary_status", ""),
    )
    _log(
        "phase1 pilot_wait_exit_normal "
        f"run_id={run_id} "
        f"child_pid={proc.pid if proc is not None else ''} "
        f"last_known_child_state={exit_snapshot.get('last_known_child_state', '')} "
        f"result_exists={exit_snapshot.get('result_exists', '0')} "
        f"marker_status={exit_snapshot.get('marker_status', '') or 'none'} "
        f"result_ok={exit_snapshot.get('result_ok', '') or 'none'} "
        f"boundary_status={exit_snapshot.get('boundary_status', '') or 'none'}"
    )

    elapsed = time.monotonic() - start_monotonic
    progress_tail = _tail_line(progress_path)
    child_rc_raw = int(proc.returncode or 0)
    _write_watchdog_marker(
        name="WATCHDOG_EXIT.txt",
        log_prefix="phase1_pilot_step",
        details=f"rc={child_rc_raw} reason=communicate_done",
    )
    if child_rc_raw != 0:
        details = f"rc={proc.returncode} progress_tail={progress_tail}"
        _log(
            "phase1 pilot_step done "
            f"rc_raw={child_rc_raw} "
            f"rc_effective={child_rc_raw} "
            f"contract_status=child_failed "
            f"elapsed_seconds={_fmt(_r2(elapsed))} "
            f"progress_tail={progress_tail}"
        )
        raise RuntimeError(f"phase1 pilot step failed: {details}")
    stdout_text = ""
    stderr_text = ""
    try:
        stdout_text = stdout_log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        stdout_text = ""
    try:
        stderr_text = stderr_log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        stderr_text = ""
    lines = [line.strip() for line in stdout_text.splitlines() if _norm(line)]
    stderr_tail = _norm(stderr_text.splitlines()[-1] if stderr_text else "")
    # Marker can land just after process exit on busy Windows filesystems.
    marker_deadline = time.monotonic() + 3.0
    marker_exists = completion_marker_path.exists()
    while not marker_exists and time.monotonic() <= marker_deadline:
        time.sleep(0.1)
        marker_exists = completion_marker_path.exists()
    marker_status = ""
    marker_reason = ""
    marker_run_id = ""
    marker_result_ok = ""
    if marker_exists:
        try:
            marker_raw = json.loads(completion_marker_path.read_text(encoding="utf-8"))
            if isinstance(marker_raw, dict):
                marker_status = _norm(marker_raw.get("status", "")).lower()
                marker_reason = _norm(marker_raw.get("reason", ""))
                marker_run_id = _norm(marker_raw.get("run_id", ""))
                marker_result_ok = _norm(marker_raw.get("result_ok", ""))
        except Exception as exc:
            marker_status = "invalid_json"
            marker_reason = f"{type(exc).__name__}:{exc}"
    payload_text = ""
    result_exists = False
    result_size = 0
    payload_source = "none"
    # On Windows the result file can appear fractionally after process exit.
    deadline = time.monotonic() + 3.0
    while time.monotonic() <= deadline:
        result_exists = result_path.exists()
        result_size = 0
        if result_exists:
            try:
                result_size = int(result_path.stat().st_size)
            except Exception:
                result_size = 0
            if result_size > 0:
                break
        time.sleep(0.1)
    if not result_exists or result_size <= 0:
        for candidate in sorted(
            H_LIVE_DIR.glob(f"phase1_pilot_step.result.{run_id}.*.json"),
            key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
            reverse=True,
        ):
            try:
                candidate_size = int(candidate.stat().st_size)
            except Exception:
                candidate_size = 0
            if candidate_size <= 0:
                continue
            if candidate != result_path:
                _log(
                    "phase1 pilot_step result_path_reconciled "
                    f"expected_path={result_path} "
                    f"selected_path={candidate} "
                    f"selected_size={candidate_size}"
                )
            result_path = candidate
            result_exists = True
            result_size = candidate_size
            break
    if not payload_text and result_exists:
        try:
            payload_text = result_path.read_text(encoding="utf-8").strip()
            if payload_text:
                payload_source = "result_file"
        except Exception as exc:
            payload_text = ""
            _log(
                "phase1 pilot_step result_read_failed "
                f"result_path={result_path} "
                f"error={type(exc).__name__}:{exc}"
            )
    if not payload_text and lines:
        payload_text = lines[-1]
        payload_source = "stdout"
    def _evaluate_contract() -> tuple[str, str]:
        if not marker_exists:
            return "completion_marker_missing", f"completion_marker_path={completion_marker_path}"
        if marker_status != "success":
            return (
                "completion_marker_not_success",
                (
                    f"completion_marker_path={completion_marker_path} "
                    f"status={marker_status or 'none'} reason={marker_reason} run_id={marker_run_id}"
                ),
            )
        if marker_run_id and _norm(marker_run_id) != _norm(run_id):
            return (
                "completion_marker_run_mismatch",
                (
                    f"expected_run_id={run_id} marker_run_id={marker_run_id} "
                    f"completion_marker_path={completion_marker_path}"
                ),
            )
        if marker_result_ok not in {"1", "true"}:
            return (
                "completion_marker_result_not_ok",
                (
                    f"completion_marker_path={completion_marker_path} "
                    f"marker_result_ok={marker_result_ok or 'none'}"
                ),
            )
        if not payload_text:
            return (
                "result_payload_missing",
                (
                    f"stdout_lines={len(lines)} result_path={result_path} "
                    f"result_exists={'1' if result_exists else '0'} result_size={result_size}"
                ),
            )
        return "", ""

    def _contract_reconcile_eligible(contract_class: str) -> tuple[bool, str]:
        if not contract_class or PHASE1_PILOT_POST_EXIT_HANDOFF_WAIT_SECONDS <= 0:
            return False, "disabled_or_not_needed"
        if contract_class == "completion_marker_missing":
            return True, "marker_missing_may_land_after_exit"
        if contract_class == "completion_marker_not_success":
            marker_status_norm = _norm(marker_status).lower()
            marker_reason_norm = _norm(marker_reason).lower()
            if marker_status_norm in {"", "invalid_json"}:
                return True, "marker_unreadable_or_empty"
            if marker_status_norm == "started":
                return False, "marker_started_after_child_exit_is_terminal"
            if marker_status_norm == "failed":
                return False, "marker_failed_is_terminal"
            if "run_started" in marker_reason_norm:
                return False, "marker_run_started_reason_is_terminal"
            return True, "marker_status_may_settle"
        if contract_class == "completion_marker_result_not_ok":
            if payload_text:
                return True, "payload_present_result_flag_may_settle"
            if _norm(marker_result_ok).lower() in {"0", "false", ""}:
                return False, "result_not_ok_without_payload_is_terminal"
            return True, "result_flag_may_settle"
        if contract_class == "result_payload_missing":
            if marker_status == "success":
                return True, "success_marker_waiting_for_payload"
            return False, "payload_missing_without_success_marker_is_terminal"
        return False, "contract_not_recoverable"

    contract_error, contract_reason = _evaluate_contract()
    reconcile_allowed, reconcile_reason = _contract_reconcile_eligible(contract_error)
    if reconcile_allowed:
        handoff_deadline = time.monotonic() + PHASE1_PILOT_POST_EXIT_HANDOFF_WAIT_SECONDS
        _log(
            "phase1 pilot_step handoff_reconcile_wait "
            f"seconds={_fmt(_r2(PHASE1_PILOT_POST_EXIT_HANDOFF_WAIT_SECONDS))} "
            f"initial_contract_class={contract_error} "
            f"initial_marker_status={marker_status or 'none'} "
            f"initial_marker_result_ok={marker_result_ok or 'none'} "
            f"initial_result_exists={'1' if result_exists else '0'} "
            f"eligibility_reason={reconcile_reason}"
        )
        while time.monotonic() <= handoff_deadline:
            time.sleep(1.0)
            marker_exists = completion_marker_path.exists()
            marker_status = ""
            marker_reason = ""
            marker_run_id = ""
            marker_result_ok = ""
            if marker_exists:
                try:
                    marker_raw = json.loads(completion_marker_path.read_text(encoding="utf-8"))
                    if isinstance(marker_raw, dict):
                        marker_status = _norm(marker_raw.get("status", "")).lower()
                        marker_reason = _norm(marker_raw.get("reason", ""))
                        marker_run_id = _norm(marker_raw.get("run_id", ""))
                        marker_result_ok = _norm(marker_raw.get("result_ok", "")).lower()
                except Exception as exc:
                    marker_status = "invalid_json"
                    marker_reason = f"{type(exc).__name__}:{exc}"
            result_exists = result_path.exists()
            result_size = 0
            if result_exists:
                try:
                    result_size = int(result_path.stat().st_size)
                except Exception:
                    result_size = 0
            if (not result_exists or result_size <= 0):
                for candidate in sorted(
                    H_LIVE_DIR.glob(f"phase1_pilot_step.result.{run_id}.*.json"),
                    key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
                    reverse=True,
                ):
                    try:
                        candidate_size = int(candidate.stat().st_size)
                    except Exception:
                        candidate_size = 0
                    if candidate_size <= 0:
                        continue
                    result_path = candidate
                    result_exists = True
                    result_size = candidate_size
                    break
            if result_exists and not payload_text:
                try:
                    payload_text = result_path.read_text(encoding="utf-8").strip()
                    if payload_text:
                        payload_source = "result_file"
                except Exception:
                    payload_text = ""
            contract_error, contract_reason = _evaluate_contract()
            reconcile_allowed, reconcile_reason = _contract_reconcile_eligible(contract_error)
            if not reconcile_allowed:
                break
        if not contract_error:
            _log(
                "phase1 pilot_step handoff_reconcile_resolved "
                "status=ok "
                f"marker_status={marker_status or 'none'} "
                f"marker_result_ok={marker_result_ok or 'none'} "
                f"result_exists={'1' if result_exists else '0'} "
                f"payload_source={payload_source}"
            )
        else:
            _log(
                "phase1 pilot_step handoff_reconcile_expired "
                f"contract_class={contract_error} "
                f"marker_status={marker_status or 'none'} "
                f"marker_result_ok={marker_result_ok or 'none'} "
                f"result_exists={'1' if result_exists else '0'} "
                f"payload_source={payload_source or 'none'} "
                f"eligibility_reason={reconcile_reason}"
            )
    elif contract_error:
        _log(
            "phase1 pilot_step handoff_reconcile_skipped "
            f"contract_class={contract_error} "
            f"marker_status={marker_status or 'none'} "
            f"marker_result_ok={marker_result_ok or 'none'} "
            f"result_exists={'1' if result_exists else '0'} "
            f"payload_source={payload_source or 'none'} "
            f"eligibility_reason={reconcile_reason}"
        )
    promoted_rc = child_rc_raw
    if contract_error:
        promoted_rc = 91
        _log(
            "phase1 pilot_step rc_promoted "
            f"rc_raw={child_rc_raw} "
            f"rc_effective={promoted_rc} "
            f"class={contract_error} "
            f"reason={contract_reason}"
        )
    _log(
        "phase1 pilot_step payload_check "
        f"rc_raw={child_rc_raw} "
        f"rc_effective={promoted_rc} "
        f"contract_class={contract_error or 'ok'} "
        f"stdout_lines={len(lines)} "
        f"result_path={result_path} "
        f"result_exists={'1' if result_exists else '0'} "
        f"result_size={result_size} "
        f"payload_source={payload_source} "
        f"marker_exists={'1' if marker_exists else '0'} "
        f"marker_status={marker_status or 'none'} "
        f"marker_run_id={marker_run_id} "
        f"marker_result_ok={marker_result_ok} "
        f"marker_reason={marker_reason} "
        f"stderr_tail={stderr_tail}"
    )
    _log(
        "phase1 pilot_step done "
        f"rc_raw={child_rc_raw} "
        f"rc_effective={promoted_rc} "
        f"contract_status={'ok' if not contract_error else 'failed'} "
        f"elapsed_seconds={_fmt(_r2(elapsed))} "
        f"progress_tail={progress_tail}"
    )
    _clear_active_phase1_pilot_wait()
    if contract_error:
        raise RuntimeError(
            "phase1 pilot completion contract failed "
            f"(class={contract_error} rc_raw={child_rc_raw} rc_effective={promoted_rc} {contract_reason})"
        )
    try:
        payload = json.loads(payload_text)
    except Exception as exc:
        _log(
            "phase1 pilot_step rc_promoted "
            f"rc_raw={child_rc_raw} "
            "rc_effective=91 "
            "class=result_payload_invalid_json "
            f"reason=payload_source={payload_source} result_path={result_path} error={exc}"
        )
        raise RuntimeError(
            "phase1 pilot completion contract failed "
            "(class=result_payload_invalid_json "
            f"rc_raw={child_rc_raw} rc_effective=91 "
            f"payload_source={'stdout' if lines else ('result_file' if result_exists else 'none')} "
            f"result_path={result_path} error={exc})"
        ) from exc
    if not isinstance(payload, dict):
        _log(
            "phase1 pilot_step rc_promoted "
            f"rc_raw={child_rc_raw} "
            "rc_effective=91 "
            "class=result_payload_not_object"
        )
        raise RuntimeError(
            "phase1 pilot completion contract failed "
            f"(class=result_payload_not_object rc_raw={child_rc_raw} rc_effective=91)"
        )
    payload_run_id = _norm(payload.get("run_id", ""))
    if payload_run_id and _norm(payload_run_id) != _norm(run_id):
        _log(
            "phase1 pilot_step rc_promoted "
            f"rc_raw={child_rc_raw} "
            "rc_effective=91 "
            "class=marker_result_mismatch "
            f"reason=expected_run_id={run_id} payload_run_id={payload_run_id}"
        )
        raise RuntimeError(
            "phase1 pilot completion contract failed "
            f"(class=marker_result_mismatch rc_raw={child_rc_raw} rc_effective=91 "
            f"expected_run_id={run_id} payload_run_id={payload_run_id})"
        )
    return {str(k): str(v) for k, v in payload.items()}


def _run_subprocess_with_watchdog(
    cmd: List[str],
    *,
    timeout_seconds: float,
    cwd: Path | None = None,
    log_prefix: str = "",
    heartbeat_every_seconds: float = 30.0,
    poll_seconds: float = 5.0,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    if log_prefix:
        _log(
            f"{log_prefix} watchdog_run_start "
            f"timeout_seconds={int(timeout_seconds)} "
            f"cwd={cwd or ROOT} "
            f"cmd={' '.join(str(part) for part in cmd)}"
        )
    _write_watchdog_marker(
        name="WATCHDOG_ENTER.txt",
        log_prefix=log_prefix or "subprocess",
        details=f"timeout_seconds={int(timeout_seconds)} cmd={' '.join(str(part) for part in cmd)}",
    )
    env = os.environ.copy()
    env.update(env_overrides or {})
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd or ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=float(timeout_seconds),
        )
        _write_watchdog_marker(
            name="WATCHDOG_EXIT.txt",
            log_prefix=log_prefix or "subprocess",
            details=f"rc={int(result.returncode)} reason=run_done",
        )
        if log_prefix:
            stderr_tail = (_norm(result.stderr or "").splitlines()[-1:] or [""])[0]
            stdout_tail = (_norm(result.stdout or "").splitlines()[-1:] or [""])[0]
            _log(
                f"{log_prefix} watchdog_run_end "
                f"rc={int(result.returncode)} "
                f"stdout_tail={stdout_tail} "
                f"stderr_tail={stderr_tail}"
            )
        return result
    except subprocess.TimeoutExpired as exc:
        _write_watchdog_kill_marker(
            log_prefix=log_prefix or "subprocess",
            pid=0,
            elapsed_seconds=float(timeout_seconds),
            timeout_seconds=timeout_seconds,
            cmd=cmd,
        )
        _write_watchdog_marker(
            name="WATCHDOG_EXIT.txt",
            log_prefix=log_prefix or "subprocess",
            details="rc=124 reason=timeout_expired",
        )
        stdout_text = str(exc.output or "")
        stderr_text = str(exc.stderr or "")
        if log_prefix:
            stdout_tail = (_norm(stdout_text).splitlines()[-1:] or [""])[0]
            stderr_tail = (_norm(stderr_text).splitlines()[-1:] or [""])[0]
            _log(
                f"{log_prefix} watchdog_timeout "
                f"timeout_seconds={int(timeout_seconds)} "
                f"stdout_tail={stdout_tail} "
                f"stderr_tail={stderr_tail}"
            )
        timeout_note = (
            f"watchdog_timeout_seconds={int(timeout_seconds)};"
            f"log_prefix={log_prefix or 'subprocess'}"
        )
        stderr_joined = f"{stderr_text}\n{timeout_note}".strip()
        return subprocess.CompletedProcess(cmd, 124, stdout_text, stderr_joined)
    except Exception as exc:
        if log_prefix:
            _log(
                f"{log_prefix} watchdog_run_exception "
                f"error={type(exc).__name__}:{exc}"
            )
        raise


def _h_split_health_due(*, now_utc: datetime, state: dict) -> bool:
    last_run = _to_dt(state.get("h_gate_health_run_utc", ""))
    if last_run is None:
        return True
    age_seconds = (now_utc - last_run).total_seconds()
    return age_seconds >= H_HEALTH_INTERVAL_SECONDS


def _run_h_profile_health_check() -> dict[str, str]:
    health_path = resolve_script_path(ROOT / "scripts", "A015_build_system_health_check.py")
    if not health_path.exists():
        return {
            "rc": "2",
            "fresh": "0",
            "error": "missing_A015_build_system_health_check.py",
        }
    before_mtime = _mtime_seconds(H_SPLIT_CHECKLIST_PATH)
    proc_returncode = 2
    proc_stdout = ""
    proc_stderr = ""
    start_monotonic = time.monotonic()
    cmd = [
        sys.executable,
        str(health_path),
        "--profile",
        "h",
        "--checklist-path",
        str(H_SPLIT_CHECKLIST_PATH),
        "--no-toast",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=H_HEALTH_CHECK_TIMEOUT_SECONDS,
            check=False,
        )
        proc_returncode = int(proc.returncode)
        proc_stdout = proc.stdout or ""
        proc_stderr = proc.stderr or ""
    except subprocess.TimeoutExpired:
        return {
            "rc": "2",
            "fresh": "0",
            "error": f"health_check_timeout_after_{int(H_HEALTH_CHECK_TIMEOUT_SECONDS)}s",
        }
    except Exception as exc:
        return {"rc": "2", "fresh": "0", "error": f"run_error: {exc}"}
    elapsed = max(time.monotonic() - start_monotonic, 0.0)
    if elapsed > H_HEALTH_CHECK_TIMEOUT_SECONDS:
        return {
            "rc": "2",
            "fresh": "0",
            "error": f"health_check_timeout_after_{int(H_HEALTH_CHECK_TIMEOUT_SECONDS)}s",
        }
    after_mtime = _mtime_seconds(H_SPLIT_CHECKLIST_PATH)
    fresh = bool(after_mtime is not None and (before_mtime is None or after_mtime > before_mtime))
    rc = int(proc_returncode)
    if rc == 1 and not fresh:
        rc = 2
    counts = _checklist_counts(H_SPLIT_CHECKLIST_PATH)
    fail_count = counts[0] if counts is not None else -1
    warn_count = counts[1] if counts is not None else -1
    out = {
        "rc": str(rc),
        "fresh": "1" if fresh else "0",
        "snapshot_utc": _checklist_snapshot_utc(H_SPLIT_CHECKLIST_PATH),
        "fail_count": "" if fail_count < 0 else str(fail_count),
        "warn_count": "" if warn_count < 0 else str(warn_count),
        "readable": "1" if counts is not None else "0",
    }
    if proc_returncode != 0 and rc == 2:
        stderr = _norm(proc_stderr or "")
        stdout = _norm(proc_stdout or "")
        out["error"] = (stderr or stdout or f"rc={proc_returncode}")[:300]
    return out


def _resolve_h_split_gate(
    *,
    now_utc: datetime,
    run_id: str,
    mode_requested: str,
    mode_effective: str,
    state: dict,
) -> dict[str, str]:
    payload: dict[str, str] = {
        "h_split_health_mode": mode_effective,
        "h_gate_fail_count": "",
        "h_gate_warn_count": "",
        "h_gate_block_live_writes": "0",
        "h_gate_snapshot_utc": "",
    }
    mode = _normalize_split_mode(mode_effective, default="shadow")
    if mode == "legacy":
        return payload

    ran_health = False
    run_result: dict[str, str] = {}
    if _h_split_health_due(now_utc=now_utc, state=state):
        ran_health = True
        health_started = time.time()
        _log(
            "split_health_run_start "
            f"mode={mode} "
            f"inline={'1' if H_HEALTH_RUN_INLINE else '0'} "
            f"timeout_seconds={int(H_HEALTH_CHECK_TIMEOUT_SECONDS)}"
        )
        if H_HEALTH_RUN_INLINE:
            try:
                run_result = _run_h_profile_health_check()
            except Exception as exc:
                run_result = {
                    "rc": "2",
                    "fresh": "0",
                    "error": f"split_health_run_error: {type(exc).__name__}: {exc}",
                }
        else:
            # Production-safe mode: never run A015 inline inside H loop.
            run_result = {
                "rc": "0",
                "fresh": "0",
                "error": "inline_health_run_disabled_using_existing_checklist",
            }
        state["h_gate_health_run_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        state["h_gate_health_last_rc"] = _norm(run_result.get("rc", ""))
        state["h_gate_health_last_error"] = _norm(run_result.get("error", ""))
        _log(
            "split_health_run "
            f"mode={mode} "
            f"inline={'1' if H_HEALTH_RUN_INLINE else '0'} "
            f"rc={run_result.get('rc', '')} "
            f"fresh={run_result.get('fresh', '')} "
            f"fail={run_result.get('fail_count', '')} "
            f"warn={run_result.get('warn_count', '')} "
            f"readable={run_result.get('readable', '')} "
            f"elapsed_seconds={_fmt(_r2(time.time() - health_started))}"
        )

    gate_checklist_path, gate_checklist_source = _choose_h_gate_checklist_path()
    counts = _checklist_counts(gate_checklist_path)
    snapshot_utc = _checklist_snapshot_utc(gate_checklist_path)
    readable = counts is not None
    fail_count = counts[0] if counts is not None else -1
    warn_count = counts[1] if counts is not None else -1
    block_live_writes = False
    if mode == "split":
        if not readable:
            block_live_writes = H_HEALTH_FAIL_CLOSED
        elif fail_count > 0:
            block_live_writes = True

    payload["h_gate_fail_count"] = "" if fail_count < 0 else str(fail_count)
    payload["h_gate_warn_count"] = "" if warn_count < 0 else str(warn_count)
    payload["h_gate_snapshot_utc"] = snapshot_utc
    payload["h_gate_block_live_writes"] = "1" if block_live_writes else "0"
    payload["h_gate_checklist_source"] = gate_checklist_source
    payload["h_gate_checklist_path"] = str(gate_checklist_path)

    clean_run = False
    if ran_health:
        rc_val = _safe_int(run_result.get("rc", "2"), 2)
        clean_run = rc_val in {0, 1} and readable
        shadow_state = _update_h_shadow_streak(clean_run)
        try:
            _append_split_shadow_compare(
                {
                    "timestamp_utc": _ts(),
                    "cycle_start_utc": run_id,
                    "cycle": "H",
                    "mode_requested": mode_requested,
                    "mode_effective": mode,
                    "legacy_fail_count": "",
                    "legacy_warn_count": "",
                    "legacy_gate_block": "",
                    "split_fail_count": payload["h_gate_fail_count"],
                    "split_warn_count": payload["h_gate_warn_count"],
                    "split_gate_block": payload["h_gate_block_live_writes"],
                    "decision_match": "",
                    "h_clean": "1" if clean_run else "0",
                    "b_match_streak": str(_safe_int(shadow_state.get("b_match_streak", 0), 0)),
                    "h_clean_streak": str(_safe_int(shadow_state.get("h_clean_streak", 0), 0)),
                    "ready_for_cutover": "1" if bool(shadow_state.get("ready_for_cutover", False)) else "0",
                    "legacy_source": "",
                    "split_source": gate_checklist_path.name,
                    "notes": _norm(run_result.get("error", "")),
                }
            )
        except Exception as exc:
            _log(f"split_shadow_compare_write_error {type(exc).__name__}: {exc}")
        _log(
            "split_shadow_h "
            f"clean={'1' if clean_run else '0'} "
            f"fail={payload['h_gate_fail_count']} warn={payload['h_gate_warn_count']} "
            f"block_live_writes={payload['h_gate_block_live_writes']} "
            f"source={gate_checklist_source} "
            f"b_match_streak={_safe_int(shadow_state.get('b_match_streak', 0), 0)} "
            f"h_clean_streak={_safe_int(shadow_state.get('h_clean_streak', 0), 0)} "
            f"ready_for_cutover={'1' if bool(shadow_state.get('ready_for_cutover', False)) else '0'}"
        )

    return payload


def _parse_key_value_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_line in str(text or "").splitlines():
        line = str(raw_line).strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        k = _norm(key)
        if not k:
            continue
        out[k] = _norm(value)
    return out


def _run_module_inline(module_path: str, argv: list[str], *, promote_exit: bool = True) -> int:
    argv_backup = list(sys.argv)
    try:
        sys.argv = list(argv)
        module = importlib.import_module(module_path)
        entry = getattr(module, "main", None)
        if entry is None:
            entry = getattr(module, "run", None)
        if entry is None:
            raise RuntimeError(f"inline module missing entrypoint: {module_path} (main/run not found)")
        try:
            rc_raw = entry()
        except SystemExit as exc:
            code = exc.code
            if isinstance(code, int):
                rc = int(code)
                return _promote_zero_exit_without_finalizer(rc) if promote_exit else rc
            return 1
        if rc_raw is None:
            rc = 0
            return _promote_zero_exit_without_finalizer(rc) if promote_exit else rc
        rc = int(rc_raw)
        return _promote_zero_exit_without_finalizer(rc) if promote_exit else rc
    finally:
        sys.argv = argv_backup


def _run_module_inline_capture(
    *,
    module_path: str,
    argv: list[str],
    env_updates: dict[str, str] | None = None,
    promote_exit: bool = True,
) -> subprocess.CompletedProcess:
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    env_backup: dict[str, str | None] = {}
    if env_updates:
        for key, value in env_updates.items():
            env_backup[key] = os.environ.get(key)
            os.environ[key] = str(value)
    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            rc = _run_module_inline(module_path, argv, promote_exit=promote_exit)
    finally:
        for key, old_value in env_backup.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
    return subprocess.CompletedProcess(
        argv,
        int(rc),
        stdout_buf.getvalue(),
        stderr_buf.getvalue(),
    )


def _run_phase1_daily_intel_alignment_subprocess(
    *,
    now_utc: datetime,
    run_id: str,
    config_path: str,
    stage_env: dict[str, str] | None = None,
) -> dict[str, str]:
    global _ACTIVE_PHASE1_INTEL_BOUNDARY
    class _Phase1IntelBoundaryError(RuntimeError):
        def __init__(self, reason: str, *, exit_code: int = 5) -> None:
            super().__init__(reason)
            self.exit_code = int(exit_code)

    requested_intel_mode = _effective_phase1_mode(H_PHASE1_INTEL_MODE)
    intel_mode = "subprocess"
    intel_script = resolve_script_path(ROOT / "scripts", "A016_refresh_phase1_daily_intel.py")
    alignment_mode = "single_sku" if H_PHASE1_INTEL_ALIGNMENT_MODE == "single_sku" else "full_universe"
    intel_argv = [
        str(intel_script),
        "--phase1-config",
        str(config_path),
        "--mode",
        alignment_mode,
    ]
    if alignment_mode == "single_sku":
        intel_argv.extend(["--sku", OFFICIAL_PILOT_SKU])
    intel_env = dict(stage_env or {})
    intel_env.setdefault("H_PHASE1_INTEL_PROGRESS_PATH", str(H_PHASE1_INTEL_PROGRESS_LOG_PATH))
    intel_env.setdefault("A016_PROGRESS_LOG_PATH", str(H_PHASE1_INTEL_PROGRESS_LOG_PATH))
    intel_env.setdefault("H_RUN_ID", run_id)
    attempt_token = time.time_ns()
    result_path = H_LIVE_DIR / f"phase1_intel_alignment.result.{run_id}.{os.getpid()}.{attempt_token}.json"
    boundary_state_path = _phase1_intel_boundary_state_path(run_id)
    try:
        if result_path.exists():
            result_path.unlink()
    except Exception:
        pass
    intel_env["A016_RESULT_PATH"] = str(result_path)
    intel_env["A016_BOUNDARY_STATE_PATH"] = str(boundary_state_path)
    intel_env["A016_PARENT_PID"] = str(os.getpid())
    _append_phase1_intel_progress(
        run_id,
        "start",
        mode=intel_mode,
        requested_mode=requested_intel_mode,
        timeout_seconds=int(PHASE1_INTEL_TIMEOUT_SECONDS),
    )
    elapsed = 0.0
    if requested_intel_mode != intel_mode:
        _log(
            "phase1 daily_intel alignment forcing_subprocess "
            f"requested_mode={requested_intel_mode} "
            "effective_mode=subprocess "
            "reason=inline_boundary_unstable"
        )
    cmd = [sys.executable, *intel_argv]
    stage_output_path = ""
    phase1_data_dir = _norm(intel_env.get("PHASE1_DATA_DIR", ""))
    if phase1_data_dir:
        stage_output_path = str(Path(phase1_data_dir) / "sku_daily_intel.csv")
    _ACTIVE_PHASE1_INTEL_BOUNDARY = {
        "run_id": _norm(run_id),
        "status": "active",
        "boundary_state_path": str(boundary_state_path),
        "result_path": str(result_path),
        "progress_path": str(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
        "requested_mode": requested_intel_mode,
        "effective_mode": intel_mode,
        "alignment_mode": alignment_mode,
        "stage_output_path": stage_output_path,
        "parent_pid": str(os.getpid()),
    }
    _write_phase1_intel_boundary_state(
        run_id,
        "active",
        parent_pid=os.getpid(),
        boundary_state_path=boundary_state_path,
        result_path=result_path,
        progress_path=H_PHASE1_INTEL_PROGRESS_LOG_PATH,
        requested_mode=requested_intel_mode,
        effective_mode=intel_mode,
        alignment_mode=alignment_mode,
        stage_output_path=stage_output_path,
        state_reason="prelaunch",
    )
    _log(
        "phase1 daily_intel alignment subprocess_start "
        f"requested_mode={requested_intel_mode} "
        f"effective_mode={intel_mode} "
        f"timeout_seconds={int(PHASE1_INTEL_TIMEOUT_SECONDS)} "
        f"result_path={result_path} "
        f"cmd={' '.join(str(part) for part in cmd)}"
    )
    start_monotonic = time.monotonic()
    last_heartbeat = start_monotonic
    stdout_capture = tempfile.NamedTemporaryFile(
        mode="w+",
        encoding="utf-8",
        delete=False,
        dir=str(H_LIVE_DIR),
        prefix=f"phase1_intel_wait.{run_id}.",
        suffix=".stdout.log",
    )
    stderr_capture = tempfile.NamedTemporaryFile(
        mode="w+",
        encoding="utf-8",
        delete=False,
        dir=str(H_LIVE_DIR),
        prefix=f"phase1_intel_wait.{run_id}.",
        suffix=".stderr.log",
    )
    stdout_capture_path = Path(stdout_capture.name)
    stderr_capture_path = Path(stderr_capture.name)
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=stdout_capture,
        stderr=stderr_capture,
        text=True,
        env={**os.environ.copy(), **intel_env},
    )
    _write_watchdog_marker(
        name="WATCHDOG_ENTER.txt",
        log_prefix="phase1 daily_intel alignment",
        details=f"pid={proc.pid} cmd={' '.join(str(part) for part in cmd)}",
    )
    _append_h_parent_trace(
        "phase1_intel_child_started",
        child_pid=proc.pid,
        requested_mode=requested_intel_mode,
        effective_mode=intel_mode,
        result_path=result_path,
    )
    _ACTIVE_PHASE1_INTEL_BOUNDARY["child_pid"] = str(proc.pid)
    _enter_phase1_intel_wait_window(
        run_id,
        child_pid=proc.pid,
        requested_mode=requested_intel_mode,
        effective_mode=intel_mode,
        result_path=result_path,
        boundary_state_path=boundary_state_path,
    )
    _write_phase1_intel_boundary_state(
        run_id,
        "active",
        child_pid=proc.pid,
        parent_pid=os.getpid(),
        state_reason="child_started",
        wait_state_path=_ACTIVE_PHASE1_INTEL_WAIT.get("wait_state_path", ""),
    )
    _log(f"phase1 daily_intel alignment child_started pid={proc.pid} run_id={run_id}")
    initial_progress_tail = _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH)
    _ACTIVE_PHASE1_INTEL_WAIT["first_poll_enter_utc"] = _ts()
    _ACTIVE_PHASE1_INTEL_WAIT["poll_iteration"] = "0"
    _ACTIVE_PHASE1_INTEL_WAIT["timeout_count"] = "0"
    _append_h_parent_trace(
        "phase1_intel_wait_enter",
        child_pid=proc.pid,
        wait_state_path=_ACTIVE_PHASE1_INTEL_WAIT.get("wait_state_path", ""),
        boundary_state_path=boundary_state_path,
    )
    _heartbeat_phase1_intel_wait_window(
        run_id,
        elapsed_seconds="0.00",
        progress_tail=initial_progress_tail,
        checkpoint="post_enter_pre_poll",
    )
    stdout_text = ""
    stderr_text = ""

    def _kill_phase1_intel_process_tree() -> None:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except Exception as exc:
            _log(
                "phase1 daily_intel alignment tree_kill_failed "
                f"child_pid={proc.pid} "
                f"error={type(exc).__name__}:{exc}"
            )

    try:
        while True:
            poll_iteration = int(float(_ACTIVE_PHASE1_INTEL_WAIT.get("poll_iteration", "0") or "0")) + 1
            if poll_iteration == 1:
                _append_h_parent_trace("phase1_intel_poll_loop_start", child_pid=proc.pid, poll_iteration=str(poll_iteration))
            _heartbeat_phase1_intel_wait_window(
                run_id,
                elapsed_seconds=_fmt(_r2(max(time.monotonic() - start_monotonic, 0.0))),
                checkpoint="poll_iteration_start",
                poll_iteration=str(poll_iteration),
                last_poll_enter_utc=_ts(),
                poll_timeout_seconds="5.0",
                poll_iteration_phase="next_poll_pending",
                next_poll_pending_utc=_ts(),
            )
            try:
                _heartbeat_phase1_intel_wait_window(
                    run_id,
                    elapsed_seconds=_fmt(_r2(max(time.monotonic() - start_monotonic, 0.0))),
                checkpoint="wait_call_enter",
                poll_iteration=str(poll_iteration),
                poll_iteration_phase="wait_call_enter",
                last_poll_call_enter_utc=_ts(),
                last_wait_call_enter_utc=_ts(),
                )
                try:
                    _append_h_parent_trace(
                        "phase1_intel_wait_call_enter",
                        child_pid=proc.pid,
                        poll_iteration=str(poll_iteration),
                    )
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    elapsed = max(time.monotonic() - start_monotonic, 0.0)
                    timeout_count = int(float(_ACTIVE_PHASE1_INTEL_WAIT.get("timeout_count", "0") or "0")) + 1
                    progress_tail = _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH)
                    heartbeat_checkpoint = "first_poll_timeout"
                    heartbeat_fields: dict[str, object] = {
                        "poll_iteration": str(poll_iteration),
                        "timeout_count": str(timeout_count),
                        "last_poll_timeout_utc": _ts(),
                        "last_poll_timeout_return_utc": _ts(),
                        "last_wait_timeout_return_utc": _ts(),
                        "poll_iteration_phase": "wait_timeout_return",
                    }
                    if not _norm(_ACTIVE_PHASE1_INTEL_WAIT.get("first_poll_timeout_utc", "")):
                        _ACTIVE_PHASE1_INTEL_WAIT["first_poll_timeout_utc"] = _ts()
                        heartbeat_fields["first_poll_timeout_utc"] = _ACTIVE_PHASE1_INTEL_WAIT["first_poll_timeout_utc"]
                    else:
                        heartbeat_checkpoint = "poll_iteration_timeout"
                    if timeout_count == 1 or timeout_count % 6 == 0:
                        _append_h_parent_trace(
                            "phase1_intel_wait_timeout",
                            child_pid=proc.pid,
                            poll_iteration=str(poll_iteration),
                            timeout_count=str(timeout_count),
                            elapsed_seconds=_fmt(_r2(elapsed)),
                            progress_tail=progress_tail,
                        )
                    _heartbeat_phase1_intel_wait_window(
                        run_id,
                        elapsed_seconds=_fmt(_r2(elapsed)),
                        progress_tail=progress_tail,
                        checkpoint=heartbeat_checkpoint,
                        **heartbeat_fields,
                    )
                    _heartbeat_phase1_intel_wait_window(
                        run_id,
                        elapsed_seconds=_fmt(_r2(elapsed)),
                        progress_tail=progress_tail,
                        checkpoint="poll_timeout_bookkeeping_done",
                        poll_iteration=str(poll_iteration),
                        timeout_count=str(timeout_count),
                        poll_iteration_phase="poll_timeout_bookkeeping_done",
                        last_poll_bookkeeping_done_utc=_ts(),
                    )
                    if elapsed >= PHASE1_INTEL_TIMEOUT_SECONDS:
                        _write_watchdog_kill_marker(
                            log_prefix="phase1 daily_intel alignment",
                            pid=proc.pid,
                            elapsed_seconds=elapsed,
                            timeout_seconds=PHASE1_INTEL_TIMEOUT_SECONDS,
                            cmd=cmd,
                        )
                        _kill_phase1_intel_process_tree()
                        stdout_text, stderr_text = proc.communicate()
                        _write_watchdog_marker(
                            name="WATCHDOG_EXIT.txt",
                            log_prefix="phase1 daily_intel alignment",
                            details="rc=124 reason=timeout_kill",
                        )
                        progress_tail = _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH)
                        _append_phase1_intel_progress(
                            run_id,
                            "alignment_done",
                            rc="124",
                            status="timeout",
                            elapsed_seconds=_fmt(_r2(elapsed)),
                        )
                        _append_phase1_intel_progress(run_id, "end", status="timeout")
                        _ACTIVE_PHASE1_INTEL_BOUNDARY["status"] = "timed_out"
                        _write_phase1_intel_boundary_state(
                            run_id,
                            "timed_out",
                            child_pid=proc.pid,
                            child_rc="124",
                            result_path=result_path,
                            stage_output_path=stage_output_path,
                            stage_output_exists="1" if stage_output_path and Path(stage_output_path).exists() else "0",
                            state_reason="timeout_kill",
                            progress_tail=progress_tail,
                        )
                        _finalize_phase1_intel_wait_window(
                            run_id,
                            status="timed_out",
                            exit_reason="timeout_kill",
                            exit_class="handled_failure",
                            child_rc="124",
                            progress_tail=progress_tail,
                            boundary_status="timed_out",
                            result_path=result_path,
                        )
                        _log(
                            "phase1 daily_intel boundary_failure "
                            f"reason=timeout "
                            f"elapsed_seconds={_fmt(_r2(elapsed))} "
                            f"result_path={result_path} "
                            f"progress_tail={progress_tail}"
                        )
                        raise _Phase1IntelBoundaryError(
                            "phase1 daily_intel alignment timeout "
                            f"after {int(PHASE1_INTEL_TIMEOUT_SECONDS)}s "
                            f"progress_tail={progress_tail}",
                            exit_code=4,
                        )
                    if elapsed - last_heartbeat >= 30.0:
                        _log(
                            "phase1 daily_intel alignment waiting "
                            f"elapsed_seconds={_fmt(_r2(elapsed))} "
                            f"child_pid={proc.pid} "
                            f"progress_tail={progress_tail}"
                        )
                        _heartbeat_phase1_intel_wait_window(
                            run_id,
                            elapsed_seconds=_fmt(_r2(elapsed)),
                            progress_tail=progress_tail,
                            checkpoint="waiting_heartbeat",
                            poll_iteration=str(poll_iteration),
                            timeout_count=str(timeout_count),
                            poll_iteration_phase="waiting_heartbeat",
                        )
                        last_heartbeat = time.monotonic()
                    continue
                except BaseException as communicate_exc:
                    elapsed = max(time.monotonic() - start_monotonic, 0.0)
                    progress_tail = _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH)
                    _heartbeat_phase1_intel_wait_window(
                        run_id,
                        elapsed_seconds=_fmt(_r2(elapsed)),
                        progress_tail=progress_tail,
                        checkpoint="wait_exception",
                        poll_iteration=str(poll_iteration),
                        poll_iteration_phase="wait_exception",
                        last_wait_exception_utc=_ts(),
                        wait_exception_type=type(communicate_exc).__name__,
                        wait_exception=str(communicate_exc)[:400],
                    )
                    raise
                _heartbeat_phase1_intel_wait_window(
                    run_id,
                    elapsed_seconds=_fmt(_r2(max(time.monotonic() - start_monotonic, 0.0))),
                    checkpoint="wait_return_to_python",
                    poll_iteration=str(poll_iteration),
                    poll_iteration_phase="wait_return_to_python",
                    last_wait_return_to_python_utc=_ts(),
                )
                _append_h_parent_trace(
                    "phase1_intel_wait_return",
                    child_pid=proc.pid,
                    poll_iteration=str(poll_iteration),
                    child_rc=proc.returncode,
                )
                _heartbeat_phase1_intel_wait_window(
                    run_id,
                    elapsed_seconds=_fmt(_r2(max(time.monotonic() - start_monotonic, 0.0))),
                    checkpoint="poll_iteration_return",
                    poll_iteration=str(poll_iteration),
                    last_poll_return_utc=_ts(),
                    poll_iteration_phase="poll_iteration_return",
                )
                break
            except BaseException:
                raise
    except BaseException as exc:
        progress_tail = _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH)
        signal_name = "SIGINT" if isinstance(exc, KeyboardInterrupt) else ""
        exit_class = "external_interruption" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "handled_failure"
        _append_h_parent_trace(
            "phase1_intel_wait_exception",
            child_pid=proc.pid,
            exit_class=exit_class,
            error_type=type(exc).__name__,
            error=str(exc)[:400],
            progress_tail=progress_tail,
        )
        _finalize_phase1_intel_wait_window(
            run_id,
            status="interrupted" if exit_class == "external_interruption" else "failed",
            exit_reason=f"{type(exc).__name__}:{exc}",
            exit_class=exit_class,
            child_rc=_EXIT_CODE_HINT,
            signal_name=signal_name,
            progress_tail=progress_tail,
            boundary_status=_ACTIVE_PHASE1_INTEL_BOUNDARY.get("status", ""),
            result_path=result_path,
            force=True,
        )
        _log(
            "phase1 daily_intel alignment wait_exit "
            f"exit_class={exit_class} "
            f"error={type(exc).__name__}:{exc} "
            f"child_pid={proc.pid} "
            f"progress_tail={progress_tail}"
        )
        raise
    finally:
        _append_h_parent_trace(
            "phase1_intel_wait_finally",
            child_pid=proc.pid,
            child_returncode=proc.returncode,
            stdout_path=stdout_capture_path,
            stderr_path=stderr_capture_path,
        )
        with contextlib.suppress(Exception):
            stdout_capture.flush()
        with contextlib.suppress(Exception):
            stderr_capture.flush()
        with contextlib.suppress(Exception):
            stdout_capture.close()
        with contextlib.suppress(Exception):
            stderr_capture.close()

    try:
        stdout_text = stdout_capture_path.read_text(encoding="utf-8")
    except Exception:
        stdout_text = ""
    try:
        stderr_text = stderr_capture_path.read_text(encoding="utf-8")
    except Exception:
        stderr_text = ""
    with contextlib.suppress(Exception):
        stdout_capture_path.unlink()
    with contextlib.suppress(Exception):
        stderr_capture_path.unlink()

    elapsed = max(time.monotonic() - start_monotonic, 0.0)
    stderr_tail = (stderr_text or "").strip().splitlines()[-1:] or [""]
    progress_tail = _tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH)
    _log(
        "phase1 daily_intel alignment subprocess_done "
        f"rc={proc.returncode} "
        f"elapsed_seconds={_fmt(_r2(elapsed))} "
        f"stderr_tail={stderr_tail[0]} "
        f"progress_tail={progress_tail}"
    )
    _append_h_parent_trace(
        "phase1_intel_subprocess_done",
        child_pid=proc.pid,
        child_rc=proc.returncode,
        elapsed_seconds=_fmt(_r2(elapsed)),
        progress_tail=progress_tail,
        stderr_tail=stderr_tail[0],
    )
    _write_watchdog_marker(
        name="WATCHDOG_EXIT.txt",
        log_prefix="phase1 daily_intel alignment",
        details=f"rc={int(proc.returncode)} reason=wait_done",
    )
    lines = [ln.strip() for ln in (stdout_text or "").splitlines() if ln.strip()]
    payload_text = lines[-1] if lines and lines[-1].startswith("{") else ""
    result_exists = result_path.exists()
    result_size = 0
    if result_exists:
        try:
            result_size = int(result_path.stat().st_size)
        except Exception:
            result_size = 0
    if not payload_text and result_exists:
        try:
            payload_text = result_path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            payload_text = ""
            _log(
                "phase1 daily_intel alignment result_read_failed "
                f"result_path={result_path} "
                f"error={type(exc).__name__}:{exc}"
            )
    payload_source = "stdout" if lines and lines[-1].startswith("{") else ("result_file" if payload_text else "none")
    _log(
        "phase1 daily_intel alignment payload_check "
        f"rc={proc.returncode} "
        f"stdout_lines={len(lines)} "
        f"result_path={result_path} "
        f"result_exists={'1' if result_exists else '0'} "
        f"result_size={result_size} "
        f"payload_source={payload_source}"
    )
    parsed = _parse_key_value_lines(stdout_text or "")
    stage_output_exists = "1" if stage_output_path and Path(stage_output_path).exists() else "0"
    if not payload_text:
        status = "timeout" if int(proc.returncode) == 124 else "failed"
        _append_h_parent_trace(
            "phase1_intel_result_missing",
            child_pid=proc.pid,
            child_rc=proc.returncode,
            payload_source=payload_source,
            result_exists="1" if result_exists else "0",
            result_size=result_size,
            stage_output_exists=stage_output_exists,
        )
        _append_phase1_intel_progress(
            run_id,
            "alignment_done",
            rc=proc.returncode,
            status=status,
            elapsed_seconds=_fmt(_r2(elapsed)),
        )
        _append_phase1_intel_progress(run_id, "end", status=status)
        failure_reason = "missing_result_with_outputs" if stage_output_exists == "1" else "missing_result"
        _ACTIVE_PHASE1_INTEL_BOUNDARY["status"] = "resolved_failure"
        _write_phase1_intel_boundary_state(
            run_id,
            "resolved_failure",
            child_pid=proc.pid,
            child_rc=proc.returncode,
            payload_source=payload_source,
            result_path=result_path,
            result_exists="1" if result_exists else "0",
            result_size=result_size,
            stage_output_path=stage_output_path,
            stage_output_exists=stage_output_exists,
            progress_tail=progress_tail,
            state_reason=failure_reason,
        )
        _finalize_phase1_intel_wait_window(
            run_id,
            status="failed",
            exit_reason=failure_reason,
            exit_class="handled_failure",
            child_rc=proc.returncode,
            progress_tail=progress_tail,
            boundary_status="resolved_failure",
            result_path=result_path,
        )
        _log(
            "phase1 daily_intel boundary_failure "
            f"reason={failure_reason} "
            f"rc={proc.returncode} "
            f"result_path={result_path} "
            f"result_exists={'1' if result_exists else '0'} "
            f"result_size={result_size} "
            f"stage_output_exists={stage_output_exists} "
            f"progress_tail={progress_tail}"
        )
        raise _Phase1IntelBoundaryError(
            "phase1 daily_intel alignment returned no usable result "
            f"(rc={proc.returncode} stdout_lines={len(lines)} result_path={result_path} "
            f"result_exists={'1' if result_exists else '0'} result_size={result_size})"
        )
    try:
        payload_raw = json.loads(payload_text)
    except Exception as exc:
        _append_h_parent_trace(
            "phase1_intel_result_invalid_json",
            child_pid=proc.pid,
            child_rc=proc.returncode,
            payload_source=payload_source,
            error=f"{type(exc).__name__}:{exc}",
        )
        _append_phase1_intel_progress(
            run_id,
            "alignment_done",
            rc=proc.returncode,
            status="failed",
            elapsed_seconds=_fmt(_r2(elapsed)),
        )
        _append_phase1_intel_progress(run_id, "end", status="failed")
        _ACTIVE_PHASE1_INTEL_BOUNDARY["status"] = "resolved_failure"
        _write_phase1_intel_boundary_state(
            run_id,
            "resolved_failure",
            child_pid=proc.pid,
            child_rc=proc.returncode,
            payload_source=payload_source,
            result_path=result_path,
            stage_output_path=stage_output_path,
            stage_output_exists=stage_output_exists,
            state_reason="invalid_result",
            error=f"{type(exc).__name__}:{exc}",
        )
        _finalize_phase1_intel_wait_window(
            run_id,
            status="failed",
            exit_reason="invalid_result",
            exit_class="handled_failure",
            child_rc=proc.returncode,
            progress_tail=_tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
            boundary_status="resolved_failure",
            result_path=result_path,
        )
        _log(
            "phase1 daily_intel boundary_failure "
            f"reason=invalid_result "
            f"rc={proc.returncode} "
            f"payload_source={payload_source} "
            f"result_path={result_path} "
            f"error={type(exc).__name__}:{exc}"
        )
        raise _Phase1IntelBoundaryError(
            "phase1 daily_intel alignment returned invalid JSON "
            f"(payload_source={payload_source} result_path={result_path} error={exc})"
        ) from exc
    if not isinstance(payload_raw, dict):
        _append_h_parent_trace(
            "phase1_intel_result_not_object",
            child_pid=proc.pid,
            child_rc=proc.returncode,
            payload_source=payload_source,
        )
        _append_phase1_intel_progress(run_id, "alignment_done", rc=proc.returncode, status="failed", elapsed_seconds=_fmt(_r2(elapsed)))
        _append_phase1_intel_progress(run_id, "end", status="failed")
        _ACTIVE_PHASE1_INTEL_BOUNDARY["status"] = "resolved_failure"
        _write_phase1_intel_boundary_state(
            run_id,
            "resolved_failure",
            child_pid=proc.pid,
            child_rc=proc.returncode,
            payload_source=payload_source,
            result_path=result_path,
            stage_output_path=stage_output_path,
            stage_output_exists=stage_output_exists,
            state_reason="payload_not_object",
        )
        _finalize_phase1_intel_wait_window(
            run_id,
            status="failed",
            exit_reason="payload_not_object",
            exit_class="handled_failure",
            child_rc=proc.returncode,
            progress_tail=_tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
            boundary_status="resolved_failure",
            result_path=result_path,
        )
        _log(
            "phase1 daily_intel boundary_failure "
            "reason=payload_not_object "
            f"rc={proc.returncode} payload_source={payload_source} result_path={result_path}"
        )
        raise _Phase1IntelBoundaryError("phase1 daily_intel alignment payload is not a JSON object")
    payload = {str(k): str(v) for k, v in payload_raw.items()}
    status = _norm(payload.get("phase1_daily_intel_alignment_status", "")).lower() or (
        "ok" if int(proc.returncode) == 0 else ("timeout" if int(proc.returncode) == 124 else "failed")
    )
    payload.setdefault("phase1_daily_intel_alignment_status", status)
    payload.setdefault("phase1_daily_intel_alignment_run_id", run_id)
    payload.setdefault("phase1_daily_intel_alignment_elapsed_seconds", _fmt(_r2(elapsed)))
    payload.setdefault("phase1_daily_intel_alignment_timeout_seconds", str(int(PHASE1_INTEL_TIMEOUT_SECONDS)))
    payload.setdefault("phase1_daily_intel_alignment_requested_mode", requested_intel_mode)
    payload.setdefault("phase1_daily_intel_alignment_effective_mode", intel_mode)
    payload.setdefault("phase1_daily_intel_alignment_scope", parsed.get("a016_scope", "full_db"))
    payload.setdefault("phase1_daily_intel_alignment_target_mode", parsed.get("a016_target_universe_mode", ""))
    payload.setdefault("phase1_daily_intel_alignment_target_source", parsed.get("a016_target_universe_source", ""))
    payload.setdefault("phase1_daily_intel_alignment_target_resolved_count", parsed.get("a016_target_universe_resolved_count", ""))
    payload.setdefault("phase1_daily_intel_alignment_target_candidate_count", parsed.get("a016_target_universe_candidate_count", ""))
    payload.setdefault("phase1_daily_intel_alignment_processed_count", parsed.get("a016_processed", ""))
    payload.setdefault("phase1_daily_intel_alignment_missing_compliance_rows", parsed.get("a016_missing_compliance_rows", ""))
    payload.setdefault("phase1_daily_intel_alignment_cpt_calls", parsed.get("a016_cpt_calls", ""))
    payload.setdefault("phase1_daily_intel_alignment_scope_file", parsed.get("a016_scope_file", ""))
    payload.setdefault("phase1_daily_intel_alignment_output_path", parsed.get("a016_output_path", ""))
    payload["phase1_daily_intel_alignment_payload_source"] = payload_source
    payload["phase1_daily_intel_alignment_child_rc"] = str(int(proc.returncode))
    error_summary = (
        _norm(payload.get("phase1_daily_intel_alignment_error", ""))
        or _norm(stderr_text or "")
        or _norm(stdout_text or "")
    )
    _append_phase1_intel_progress(
        run_id,
        "alignment_done",
        rc=proc.returncode,
        status=status,
        elapsed_seconds=_fmt(_r2(elapsed)),
    )
    if status != "ok" or int(proc.returncode) != 0:
        _append_h_parent_trace(
            "phase1_intel_child_failed",
            child_pid=proc.pid,
            child_rc=proc.returncode,
            status=status,
            payload_source=payload_source,
            error=error_summary[:400],
        )
        payload["phase1_daily_intel_alignment_error"] = error_summary[:400]
        _append_phase1_intel_progress(run_id, "end", status=status)
        _ACTIVE_PHASE1_INTEL_BOUNDARY["status"] = "resolved_failure"
        _write_phase1_intel_boundary_state(
            run_id,
            "resolved_failure",
            child_pid=proc.pid,
            child_rc=proc.returncode,
            payload_source=payload_source,
            result_path=result_path,
            stage_output_path=stage_output_path,
            stage_output_exists=stage_output_exists,
            output_path=payload.get("phase1_daily_intel_alignment_output_path", ""),
            state_reason=f"child_{status}",
            error=payload.get("phase1_daily_intel_alignment_error", ""),
        )
        _finalize_phase1_intel_wait_window(
            run_id,
            status="failed",
            exit_reason=f"child_{status}",
            exit_class="handled_failure",
            child_rc=proc.returncode,
            progress_tail=_tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
            boundary_status="resolved_failure",
            result_path=result_path,
        )
        _log(
            "phase1 daily_intel boundary_failure "
            f"reason=child_{status} "
            f"rc={proc.returncode} "
            f"payload_source={payload_source} "
            f"result_path={result_path} "
            f"error={payload.get('phase1_daily_intel_alignment_error', '')}"
        )
        raise _Phase1IntelBoundaryError(
            "phase1 daily_intel alignment child did not return success "
            f"(rc={proc.returncode} status={status} payload_source={payload_source} "
            f"result_path={result_path} error={payload.get('phase1_daily_intel_alignment_error', '')})",
            exit_code=4 if status == "timeout" or int(proc.returncode) == 124 else 5,
        )
    _append_phase1_intel_progress(
        run_id,
        "outputs_written",
        output_path=payload.get("phase1_daily_intel_alignment_output_path", ""),
        processed=payload.get("phase1_daily_intel_alignment_processed_count", ""),
    )
    _append_h_parent_trace(
        "phase1_intel_child_success",
        child_pid=proc.pid,
        child_rc=proc.returncode,
        payload_source=payload_source,
        output_path=payload.get("phase1_daily_intel_alignment_output_path", ""),
        processed=payload.get("phase1_daily_intel_alignment_processed_count", ""),
    )
    _append_phase1_intel_progress(run_id, "end", status=status)
    _ACTIVE_PHASE1_INTEL_BOUNDARY["status"] = "resolved_success"
    _write_phase1_intel_boundary_state(
        run_id,
        "resolved_success",
        child_pid=proc.pid,
        child_rc=proc.returncode,
        payload_source=payload_source,
        result_path=result_path,
        result_exists="1" if result_exists else "0",
        result_size=result_size,
        stage_output_path=payload.get("phase1_daily_intel_alignment_output_path", "") or stage_output_path,
        stage_output_exists="1",
        output_path=payload.get("phase1_daily_intel_alignment_output_path", ""),
        processed=payload.get("phase1_daily_intel_alignment_processed_count", ""),
        target_mode=payload.get("phase1_daily_intel_alignment_target_mode", ""),
        target_resolved=payload.get("phase1_daily_intel_alignment_target_resolved_count", ""),
        state_reason="child_success",
    )
    _finalize_phase1_intel_wait_window(
        run_id,
        status="resolved_success",
        exit_reason="child_success",
        exit_class="handled_success",
        child_rc=proc.returncode,
        progress_tail=_tail_line(H_PHASE1_INTEL_PROGRESS_LOG_PATH),
        boundary_status="resolved_success",
        result_path=result_path,
    )
    _log(
        "phase1 daily_intel decision "
        f"requested_mode={requested_intel_mode} "
        f"effective_mode={intel_mode} "
        f"alignment_mode={alignment_mode} "
        f"payload_source={payload_source} "
        f"child_rc={proc.returncode} "
        f"output_path={payload.get('phase1_daily_intel_alignment_output_path', '')} "
        f"scope_file={payload.get('phase1_daily_intel_alignment_scope_file', '')} "
        f"date_utc={now_utc.date().isoformat()} "
        f"processed={payload.get('phase1_daily_intel_alignment_processed_count', '')} "
        f"target_mode={payload.get('phase1_daily_intel_alignment_target_mode', '')} "
        f"target_resolved={payload.get('phase1_daily_intel_alignment_target_resolved_count', '')}"
    )
    _clear_active_phase1_intel_boundary(run_id)
    _clear_active_phase1_intel_wait(run_id)
    return payload


def _run_phase1_observation_publish_subprocess(
    *,
    now_utc: datetime,
    run_id: str,
    stage_env: dict[str, str] | None = None,
) -> dict[str, str]:
    if not PHASE1_OBSERVATION_PUBLISH_ENABLED:
        return {
            "phase1_observation_publish_status": "skipped_disabled",
            "phase1_publish_completed": "1",
            "phase1_observation_publish_run_id": run_id,
            "phase1_observation_publish_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "phase1_observation_publish_date_utc": now_utc.date().isoformat(),
        }
    publish_mode = _effective_phase1_mode(H_PHASE1_PUBLISH_MODE)
    publish_script = resolve_script_path(ROOT / "scripts", "H130_build_phase1_observation_sheet.py")
    publish_argv = [
        str(publish_script),
        "--publish",
        "--date-utc",
        now_utc.date().isoformat(),
    ]
    if PHASE1_OBSERVATION_SHEET_ID:
        publish_argv.extend(["--sheet-id", PHASE1_OBSERVATION_SHEET_ID])
    if PHASE1_OBSERVATION_VIEW_TAB:
        publish_argv.extend(["--view-tab", PHASE1_OBSERVATION_VIEW_TAB])
    if publish_mode == "inline":
        _log(
            "phase1 observation_publish inline_start "
            f"timeout_seconds={int(PHASE1_OBSERVATION_PUBLISH_TIMEOUT_SECONDS)}"
        )
        start_monotonic = time.monotonic()
        _write_watchdog_marker(
            name="WATCHDOG_ENTER.txt",
            log_prefix="phase1_observation_publish",
            details=f"mode=inline cmd={' '.join(str(part) for part in publish_argv)}",
        )
        proc = _run_module_inline_capture(
            module_path="scripts.flows.H.H130_build_phase1_observation_sheet",
            argv=publish_argv,
            env_updates=stage_env,
            promote_exit=False,
        )
        elapsed = max(time.monotonic() - start_monotonic, 0.0)
        _log(
            "phase1 observation_publish inline_end "
            f"rc={proc.returncode} "
            f"duration_s={_fmt(_r2(elapsed))}"
        )
        _write_watchdog_marker(
            name="WATCHDOG_EXIT.txt",
            log_prefix="phase1_observation_publish",
            details=f"mode=inline rc={int(proc.returncode)} reason=inline_return",
        )
    else:
        cmd = [sys.executable, *publish_argv]
        proc = _run_subprocess_with_watchdog(
            cmd,
            timeout_seconds=PHASE1_OBSERVATION_PUBLISH_TIMEOUT_SECONDS,
            cwd=ROOT,
            log_prefix="phase1 observation_publish",
            env_overrides=stage_env,
        )
    parsed = _parse_key_value_lines(proc.stdout or "")
    status = "ok" if proc.returncode == 0 else "failed"
    stderr_text = _norm(proc.stderr or "")
    stdout_text = _norm(proc.stdout or "")
    error_summary = stderr_text or stdout_text
    payload = {
        "phase1_observation_publish_status": status,
        "phase1_publish_completed": "1" if _is_publish_completed_status(status) else "0",
        "phase1_observation_publish_run_id": run_id,
        "phase1_observation_publish_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase1_observation_publish_date_utc": now_utc.date().isoformat(),
        "phase1_observation_publish_sheet_id": parsed.get("phase1_observation_sheet_id", ""),
        "phase1_observation_publish_view_tab": parsed.get("phase1_observation_view_tab", ""),
        "phase1_observation_publish_rows": parsed.get("phase1_observation_view_rows", ""),
    }
    if status != "ok":
        payload["phase1_observation_publish_error"] = error_summary[:400]
    return payload


def _run_h_daily_market_reports_subprocess(
    *,
    now_utc: datetime,
    run_id: str,
    stage_env: dict[str, str] | None = None,
) -> dict[str, str]:
    report_script = resolve_script_path(ROOT / "scripts", "H005_build_daily_market_reports.py")
    report_argv = [str(report_script)]
    cmd = [sys.executable, *report_argv]
    proc = _run_subprocess_with_watchdog(
        cmd,
        timeout_seconds=H_DAILY_MARKET_REPORT_TIMEOUT_SECONDS,
        cwd=ROOT,
        log_prefix="h daily_market_reports",
        env_overrides=stage_env,
    )
    parsed = _parse_key_value_lines(proc.stdout or "")
    status = "ok" if proc.returncode == 0 else "failed"
    stderr_text = _norm(proc.stderr or "")
    stdout_text = _norm(proc.stdout or "")
    error_summary = stderr_text or stdout_text
    payload = {
        "h_daily_market_reports_status": status,
        "h_daily_market_reports_run_id": run_id,
        "h_daily_market_reports_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "h_daily_market_report_html": parsed.get("created_html", ""),
        "h_daily_market_report_pdf": parsed.get("created_pdf", ""),
        "h_daily_market_report_price_charts": parsed.get("price_chart_count", ""),
        "h_daily_market_report_seller_mix_charts": parsed.get("seller_mix_chart_count", ""),
    }
    if status != "ok":
        payload["h_daily_market_reports_error"] = error_summary[:400]
    return payload


def _run_phase1_floor_table_build_subprocess(
    *,
    now_utc: datetime,
    run_id: str,
    stage_env: dict[str, str] | None = None,
) -> dict[str, str]:
    floor_mode = _effective_phase1_mode(H_PHASE1_FLOOR_TABLE_MODE)
    floor_script = resolve_script_path(ROOT / "scripts", "A018_build_phase1_floor_table.py")
    floor_argv = [
        str(floor_script),
        "--out-path",
        str(PHASE1_FLOOR_TABLE_PATH),
    ]
    if floor_mode == "inline":
        _log(
            "phase1 floor_table_build inline_start "
            f"timeout_seconds={int(PHASE1_FLOOR_TABLE_TIMEOUT_SECONDS)}"
        )
        start_monotonic = time.monotonic()
        _write_watchdog_marker(
            name="WATCHDOG_ENTER.txt",
            log_prefix="phase1_floor_table_build",
            details=f"mode=inline cmd={' '.join(str(part) for part in floor_argv)}",
        )
        proc = _run_module_inline_capture(
            module_path="scripts.flows.A.A018_build_phase1_floor_table",
            argv=floor_argv,
            env_updates=stage_env,
            promote_exit=False,
        )
        elapsed = max(time.monotonic() - start_monotonic, 0.0)
        _log(
            "phase1 floor_table_build inline_end "
            f"rc={proc.returncode} "
            f"duration_s={_fmt(_r2(elapsed))}"
        )
        _write_watchdog_marker(
            name="WATCHDOG_EXIT.txt",
            log_prefix="phase1_floor_table_build",
            details=f"mode=inline rc={int(proc.returncode)} reason=inline_return",
        )
    else:
        cmd = [sys.executable, *floor_argv]
        proc = _run_subprocess_with_watchdog(
            cmd,
            timeout_seconds=PHASE1_FLOOR_TABLE_TIMEOUT_SECONDS,
            cwd=ROOT,
            log_prefix="phase1 floor_table_build",
            env_overrides=stage_env,
        )
    parsed = _parse_key_value_lines(proc.stdout or "")
    status = "ok" if proc.returncode == 0 else "failed"
    stderr_text = _norm(proc.stderr or "")
    stdout_text = _norm(proc.stdout or "")
    error_summary = stderr_text or stdout_text
    payload = {
        "phase1_floor_table_status": status,
        "phase1_floor_table_run_id": run_id,
        "phase1_floor_table_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase1_floor_table_path": parsed.get("a018_floor_table_path", str(PHASE1_FLOOR_TABLE_PATH)),
        "phase1_floor_table_required_skus": parsed.get("a018_floor_required_skus", ""),
        "phase1_floor_table_rows_written": parsed.get("a018_floor_rows_written", ""),
        "phase1_floor_table_populated": parsed.get("a018_floor_populated", ""),
        "phase1_floor_table_reason_coded": parsed.get("a018_floor_reason_coded", ""),
    }
    if status != "ok":
        payload["phase1_floor_table_error"] = error_summary[:400]
    return payload


def _write_phase1_runtime_floor_snapshot(now_utc: datetime) -> dict[str, str]:
    event_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "phase1_runtime_floor_snapshot_file": PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH.name,
        "phase1_runtime_floor_snapshot_utc": event_ts,
        "phase1_runtime_floor_snapshot_rows": "0",
        "phase1_runtime_floor_snapshot_trace_rows": "0",
        "phase1_runtime_floor_snapshot_status": "missing_inputs",
    }

    exec_log_path = _phase1_execution_log_path()
    if not exec_log_path.exists():
        payload["phase1_runtime_floor_snapshot_status"] = "missing_execution_log"
        return payload

    try:
        exec_df = pd.read_csv(exec_log_path, dtype=str).fillna("")
    except Exception:
        payload["phase1_runtime_floor_snapshot_status"] = "execution_log_read_error"
        return payload

    required_exec_cols = {"sku", "event_ts_utc", "hard_floor_gbp", "final_ceiling_landed_gbp", "state", "write_status"}
    if not required_exec_cols.issubset(set(exec_df.columns)):
        payload["phase1_runtime_floor_snapshot_status"] = "execution_log_missing_columns"
        return payload

    exec_df["sku_key"] = exec_df["sku"].astype(str).str.strip().str.upper()
    exec_df["event_dt"] = pd.to_datetime(exec_df["event_ts_utc"], errors="coerce", utc=True)
    exec_df = exec_df.loc[exec_df["sku_key"].ne("")].copy()
    exec_df = exec_df.sort_values(["event_dt"], ascending=[False], kind="stable")
    latest_exec = exec_df.groupby("sku_key", as_index=False).head(1).copy()
    latest_exec["sku_norm"] = latest_exec["sku_key"].astype(str).str.strip().str.upper()
    latest_exec = latest_exec.drop(columns=[c for c in ["sku", "sku_key"] if c in latest_exec.columns], errors="ignore")
    latest_exec = latest_exec.rename(columns={"sku_norm": "sku"})

    latest_exec = latest_exec.rename(
        columns={
            "event_ts_utc": "execution_event_ts_utc",
            "state": "execution_state",
            "write_status": "execution_write_status",
            "write_error": "execution_write_error",
            "old_price_gbp": "execution_old_price_gbp",
            "new_price_gbp": "execution_new_price_gbp",
            "hard_floor_gbp": "execution_hard_floor_gbp",
            "final_ceiling_landed_gbp": "execution_final_ceiling_landed_gbp",
            "reason_codes_json": "execution_reason_codes_json",
        }
    )
    latest_exec["execution_binding_ceiling_type"] = ""

    if SKU_CEILING_EVENTS_PATH.exists():
        try:
            ceiling_df = pd.read_csv(SKU_CEILING_EVENTS_PATH, dtype=str).fillna("")
            if {"sku", "event_ts_utc", "binding_ceiling_type"}.issubset(set(ceiling_df.columns)):
                ceiling_df["sku_key"] = ceiling_df["sku"].astype(str).str.strip().str.upper()
                ceiling_df["event_dt"] = pd.to_datetime(ceiling_df["event_ts_utc"], errors="coerce", utc=True)
                ceiling_df = ceiling_df.loc[ceiling_df["sku_key"].ne("")].copy()
                ceiling_df = ceiling_df.sort_values(["event_dt"], ascending=[False], kind="stable")
                ceiling_latest = ceiling_df.groupby("sku_key", as_index=False).head(1).copy()
                ceiling_latest["sku_norm"] = ceiling_latest["sku_key"].astype(str).str.strip().str.upper()
                ceiling_latest = ceiling_latest.rename(columns={"sku_norm": "sku"})
                latest_exec = latest_exec.merge(
                    ceiling_latest[["sku", "binding_ceiling_type"]],
                    on="sku",
                    how="left",
                )
                latest_exec["execution_binding_ceiling_type"] = latest_exec["binding_ceiling_type"].astype(str)
                latest_exec = latest_exec.drop(columns=["binding_ceiling_type"], errors="ignore")
        except Exception:
            pass

    trace_latest = pd.DataFrame(columns=["sku"])
    if H_FLOOR_TRACE_PATH.exists():
        try:
            trace_df = pd.read_csv(H_FLOOR_TRACE_PATH, dtype=str).fillna("")
            if {"sku", "asof_utc", "floor_total_gbp"}.issubset(set(trace_df.columns)):
                trace_df["sku_key"] = trace_df["sku"].astype(str).str.strip().str.upper()
                trace_df["asof_dt"] = pd.to_datetime(trace_df["asof_utc"], errors="coerce", utc=True)
                trace_df = trace_df.loc[trace_df["sku_key"].ne("")].copy()
                trace_df = trace_df.sort_values(["asof_dt"], ascending=[False], kind="stable")
                trace_latest = trace_df.groupby("sku_key", as_index=False).head(1).copy()
                trace_latest["sku_norm"] = trace_latest["sku_key"].astype(str).str.strip().str.upper()
                trace_latest = trace_latest.drop(
                    columns=[c for c in ["sku", "sku_key"] if c in trace_latest.columns],
                    errors="ignore",
                )
                trace_latest = trace_latest.rename(columns={"sku_norm": "sku"})
                trace_latest = trace_latest.rename(
                    columns={
                        "asof_utc": "trace_asof_utc",
                        "source_script": "trace_source_script",
                        "candidate_price_gbp": "trace_candidate_price_gbp",
                        "floor_total_gbp": "trace_floor_total_gbp",
                        "break_even_total_gbp": "trace_break_even_total_gbp",
                        "cogs_exvat_gbp": "trace_cogs_exvat_gbp",
                        "fba_exvat_gbp": "trace_fba_exvat_gbp",
                        "referral_amount_gbp": "trace_referral_amount_gbp",
                        "band_bucket": "trace_band_bucket",
                        "reason_codes_csv": "trace_reason_codes_csv",
                    }
                )
        except Exception:
            trace_latest = pd.DataFrame(columns=["sku"])

    merged = latest_exec.merge(trace_latest, on="sku", how="left")
    suppression_truth = load_latest_suppression_truth(OUT, DATA)
    if not suppression_truth.empty:
        suppression_truth["sku"] = suppression_truth.get("sku", "").astype(str).str.strip().str.upper()
        merged = merged.merge(suppression_truth, on="sku", how="left")

    truth_rows: list[dict[str, str]] = []
    for _, row in merged.iterrows():
        truth = resolve_unified_truth(
            suppression_active_flag=row.get("suppression_active_flag", ""),
            parked_flag="0",
            write_capable=False,
            execution_state=row.get("execution_state", ""),
            execution_write_status=row.get("execution_write_status", ""),
            execution_reason_codes_json=row.get("execution_reason_codes_json", ""),
            execution_final_ceiling_landed_gbp=row.get("execution_final_ceiling_landed_gbp", ""),
            execution_binding_ceiling_type=row.get("execution_binding_ceiling_type", ""),
            suppression_buy_box_state=row.get("suppression_buy_box_state", ""),
            suppression_strategy_state=row.get("suppression_strategy_state", ""),
            suppression_write_status=row.get("suppression_write_status", ""),
            suppression_ceiling_landed_temp=row.get("suppression_ceiling_landed_temp", ""),
            execution_old_price_gbp=row.get("execution_old_price_gbp", ""),
            execution_new_price_gbp=row.get("execution_new_price_gbp", ""),
            execution_hard_floor_gbp=row.get("execution_hard_floor_gbp", ""),
            observed_our_price_gbp=row.get("observed_our_price_gbp", ""),
            trace_candidate_price_gbp=row.get("trace_candidate_price_gbp", ""),
            trace_floor_total_gbp=row.get("trace_floor_total_gbp", ""),
            execution_event_ts_utc=row.get("execution_event_ts_utc", ""),
            trace_asof_utc=row.get("trace_asof_utc", ""),
        )
        truth_rows.append(truth)
    if truth_rows:
        truth_df = pd.DataFrame.from_records(truth_rows)
        for col in truth_df.columns:
            merged[col] = truth_df[col]
    merged["snapshot_utc"] = event_ts
    merged["floor_reconcile_delta_gbp"] = ""
    try:
        hard_floor_num = pd.to_numeric(merged.get("execution_hard_floor_gbp", ""), errors="coerce")
        trace_floor_num = pd.to_numeric(merged.get("trace_floor_total_gbp", ""), errors="coerce")
        delta = (hard_floor_num - trace_floor_num).round(2)
        merged["floor_reconcile_delta_gbp"] = delta.map(lambda v: "" if pd.isna(v) else f"{float(v):.2f}")
    except Exception:
        pass

    out_cols = [
        "snapshot_utc",
        "sku",
        "execution_event_ts_utc",
        "execution_state",
        "execution_write_status",
        "execution_write_error",
        "execution_old_price_gbp",
        "execution_new_price_gbp",
        "execution_hard_floor_gbp",
        "execution_final_ceiling_landed_gbp",
        "execution_binding_ceiling_type",
        "execution_reason_codes_json",
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
        "suppression_resolved_flag",
        "observed_our_price_gbp",
        "observed_our_price_ts_utc",
        "unified_buy_box_state",
        "unified_strategy_state",
        "unified_writer_outcome",
        "write_attempted_flag",
        "write_applied_flag",
        "true_binding_ceiling_gbp",
        "true_binding_ceiling_type",
        "truth_status",
        "trace_asof_utc",
        "trace_source_script",
        "trace_candidate_price_gbp",
        "trace_floor_total_gbp",
        "trace_break_even_total_gbp",
        "trace_cogs_exvat_gbp",
        "trace_fba_exvat_gbp",
        "trace_referral_amount_gbp",
        "trace_band_bucket",
        "trace_reason_codes_csv",
        "floor_reconcile_delta_gbp",
    ]
    for col in out_cols:
        if col not in merged.columns:
            merged[col] = ""
    merged = merged[out_cols].fillna("")
    PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH, index=False)

    payload["phase1_runtime_floor_snapshot_rows"] = str(len(merged.index))
    payload["phase1_runtime_floor_snapshot_trace_rows"] = str(
        int(merged["trace_floor_total_gbp"].astype(str).str.strip().ne("").sum())
    )
    payload["phase1_runtime_floor_snapshot_status"] = "ok"
    return payload


def main() -> int:
    global _CURRENT_H_RUN_ID
    _ensure_parent_fault_trace()
    _append_h_parent_trace("main_enter")
    args = _parse_cli_args()
    ignore_sigint = os.environ.get("H_IGNORE_SIGINT", "1").strip() == "1"
    if ignore_sigint:
        for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, _h_signal_ignore_handler)
                _log(f"signal_policy {sig_name.lower()}=ignored")
                _append_h_parent_trace("signal_policy_ignored", signal_name=sig_name)
            except Exception as exc:
                _log(f"signal_policy {sig_name.lower()}=ignore_failed error={type(exc).__name__}:{exc}")
                _append_h_parent_trace(
                    "signal_policy_ignore_failed",
                    signal_name=sig_name,
                    error=f"{type(exc).__name__}:{exc}",
                )
    run_once = bool(args.run_once)
    live_write = os.environ.get("H_LIVE_WRITE", "0").strip() == "1"
    legacy_live_write = False
    if live_write:
        _log("legacy non-phase1 execution forced to READ_ONLY (H_LIVE_WRITE ignored)")
    loop_sleep_seconds = max(float(os.environ.get("H_LOOP_SLEEP_SECONDS", "30") or "30"), 1.0)
    head_cadence_hours = max(float(os.environ.get("H_HEAD_CADENCE_HOURS", "24") or "24"), 0.0)
    supervisor_cadence_hours = max(float(os.environ.get("H_SUPERVISOR_CADENCE_HOURS", "4") or "4"), 0.0)
    executioner_cadence_minutes = max(float(os.environ.get("H_EXECUTIONER_CADENCE_MINUTES", "5") or "5"), 0.0)
    phase1_cfg_path = ""
    if args.phase1_pilot:
        if not _norm(args.phase1_config):
            raise SystemExit("[H_cycle] --phase1-config is required with --phase1-pilot")
        phase1_cfg_path = str(args.phase1_config)
        loop_sleep_seconds = max(float(args.sleep_minutes) * 60.0, 1.0)

    stage_enabled: dict[str, bool] = {name: _env_stage_enabled(name) for name in STAGE_NAMES}
    only_stage = _norm(getattr(args, "only_stage", ""))
    if only_stage:
        for name in STAGE_NAMES:
            stage_enabled[name] = (name == only_stage)
    for name in list(getattr(args, "skip_stage", []) or []):
        stage_enabled[_norm(name)] = False

    cycle_run_id = ""
    loop_rc = ""
    _acquire_lock()
    try:
        _ensure_action_log()
        _ensure_live_test_execution_log()
        _write_runtime_status("RUNNING", stage="startup", detail="loop_ready")
        while True:
            cycle_manifest = None
            cycle_started = utc_now_iso()
            cycle_run_id = ""
            loop_rc = ""
            pre_cycle_drain_exit = False
            state: dict[str, str] = {}
            try:
                if _restart_drain_requested():
                    loop_rc = "0"
                    pre_cycle_drain_exit = True
                    _set_run_context("")
                    _write_restart_drain_ready(state="boundary_wait")
                    _write_runtime_status("STOPPING", stage="boundary_wait", detail="restart_drain_requested_before_cycle")
                    _log_restart_drain_once(
                        event_key="before_cycle_boundary_wait",
                        message="restart_drain requested - boundary reached before new cycle start; exiting loop",
                    )
                    break
                _ensure_lock_ownership()
                _clear_restart_drain_ready()
                now_utc = _utc_now()
                run_id = _set_run_context(_resolve_cycle_run_id(now_utc))
                _write_run_in_progress(run_id)
                _write_lock(run_id)
                for _lock_path in _lock_paths():
                    _log(f"lock_acquired path={_lock_path} run_id={run_id}")
                if os.environ.get("H_LOCK_TEST_RAISE_AFTER_ACQUIRE", "0").strip() == "1":
                    raise RuntimeError("lock_test_forced_exception_after_acquire")
                _trace_publish_gap(run_id, "cycle_start")
                _transition_h_batch_state(run_id, "started")
                _write_runtime_status("RUNNING", run_id=run_id, stage="cycle_start", detail="cycle_started")
                stage_env = _phase1_stage_env(run_id)
                stage_seed_state = _seed_phase1_staged_outputs_from_live(run_id)
                cycle_run_id = run_id
                cycle_manifest = new_manifest(cycle="H", run_id=f"H_{run_id}", start_time=cycle_started)
                cycle_manifest["configured_step_count"] = 1
                mode_requested = _normalize_split_mode(H_SPLIT_HEALTH_MODE, default="shadow")
                mode_effective = _effective_h_split_mode()
                _atomic_write_text(H_CYCLE_CURRENT_RUN_PATH, f"{run_id}\n")
                _log(
                    "cycle_start "
                    f"run_id={run_id} "
                    f"pid={os.getpid()} "
                    f"ppid={os.getppid()} "
                    f"phase1_pilot={'1' if args.phase1_pilot else '0'} "
                    f"run_once={'1' if run_once else '0'} "
                    f"loop_sleep_seconds={_fmt(_r2(loop_sleep_seconds))} "
                    f"h_split_mode_requested={mode_requested} "
                    f"h_split_mode_effective={mode_effective} "
                    f"strategy_go_live_utc={_norm(os.environ.get('H_STRATEGY_GO_LIVE_UTC', '')) or 'unset'} "
                    f"phase1_pilot_mode={_effective_phase1_mode(H_PHASE1_PILOT_MODE)} "
                    f"phase1_intel_mode={_effective_phase1_mode(H_PHASE1_INTEL_MODE)} "
                    f"phase1_publish_mode={_effective_phase1_mode(H_PHASE1_PUBLISH_MODE)} "
                    f"bisect_force_inline={'1' if H_BISECT_FORCE_INLINE else '0'} "
                    f"stage_snapshot_refresh={'1' if stage_enabled.get('snapshot_refresh', True) else '0'} "
                    f"stage_item_offers={'1' if stage_enabled.get('item_offers', True) else '0'} "
                    f"stage_phase1_pilot={'1' if stage_enabled.get('phase1_pilot', True) else '0'} "
                    f"stage_phase1_intel={'1' if stage_enabled.get('phase1_intel', True) else '0'} "
                    f"stage_phase1_publish={'1' if stage_enabled.get('phase1_publish', True) else '0'}"
                )
                _log(
                    "phase1 stage_seed "
                    f"run_id={run_id} "
                    f"seeded_from_live={stage_seed_state.get('phase1_stage_seeded_from_live', '0')}"
                )
                state = _read_state(default={})
                state["h_split_health_mode"] = mode_effective
                if args.phase1_pilot:
                    _log("phase1 snapshot_refresh start")
                    _trace_publish_gap(run_id, "snapshot_refresh_start")
                    snapshot_stage_started = _stage_enter(stage="snapshot_refresh", run_id=run_id)
                    if stage_enabled.get("snapshot_refresh", True):
                        _trace_publish_gap(run_id, "snapshot_refresh_subprocess_start", mode="inline")
                        try:
                            refresh_state = _run_with_retries(
                                "snapshot_refresh",
                                lambda: _refresh_offer_snapshots(
                                    now_utc,
                                    state,
                                    None,
                                    item_offers_enabled=stage_enabled.get("item_offers", True),
                                    stage_run_id=run_id,
                                ),
                            )
                            _trace_publish_gap(run_id, "snapshot_refresh_subprocess_end", rc="0")
                            _stage_exit(stage="snapshot_refresh", run_id=run_id, started=snapshot_stage_started, rc="0")
                        except BaseException as exc:
                            rc = _system_exit_code(exc)
                            if rc is None:
                                rc = 1
                            if isinstance(exc, SystemExit) and rc == 0:
                                rc = 3
                                _trace_publish_gap(run_id, "snapshot_refresh_subprocess_end", rc=str(rc))
                                _stage_exit(stage="snapshot_refresh", run_id=run_id, started=snapshot_stage_started, rc=str(rc))
                                _log("FATAL snapshot_refresh_system_exit_zero_promoted rc=3")
                                raise SystemExit(3)
                            _trace_publish_gap(run_id, "snapshot_refresh_subprocess_end", rc=str(rc))
                            _stage_exit(stage="snapshot_refresh", run_id=run_id, started=snapshot_stage_started, rc=str(rc))
                            raise
                    else:
                        _trace_publish_gap(run_id, "snapshot_refresh_subprocess_start", mode="disabled")
                        _trace_publish_gap(run_id, "snapshot_refresh_subprocess_end", rc="0")
                        refresh_state = {
                            "snapshot_refresh_attempted": "0",
                            "snapshot_refresh_status": "skipped_disabled",
                            "snapshot_refresh_error": "",
                        }
                        _stage_exit(
                            stage="snapshot_refresh",
                            run_id=run_id,
                            started=snapshot_stage_started,
                            rc="skipped",
                            note="disabled",
                        )
                    if refresh_state:
                        state.update(refresh_state)
                    _trace_publish_gap(
                        run_id,
                        "snapshot_refresh_done",
                        status=state.get("snapshot_refresh_status", ""),
                    )
                    _log(
                        "phase1 snapshot_refresh done "
                        f"attempted={state.get('snapshot_refresh_attempted', '')} "
                        f"status={state.get('snapshot_refresh_status', '')}"
                    )
                    refresh_status = _norm(state.get("snapshot_refresh_status", "")).lower()
                    if stage_enabled.get("snapshot_refresh", True) and refresh_status != "ok":
                        _log(
                            "FATAL snapshot_refresh_failed "
                            f"status={state.get('snapshot_refresh_status', '')} "
                            f"error={state.get('snapshot_refresh_error', '')}"
                        )
                        raise SystemExit(2)
                    today_key = now_utc.date().isoformat()
                    intel_aligned_today = (
                        _norm(state.get("phase1_daily_intel_alignment_date", "")) == today_key
                        and _is_phase1_intel_completed_status(
                            state.get("phase1_daily_intel_alignment_status", "")
                        )
                    )
                    if not intel_aligned_today:
                        intel_stage_started = _stage_enter(stage="phase1_intel", run_id=run_id)
                        state["phase1_intel_started_run_id"] = run_id
                        _write_state(state)
                        if stage_enabled.get("phase1_intel", True):
                            try:
                                alignment_state = _run_with_retries(
                                    "phase1_intel",
                                    lambda: _run_phase1_daily_intel_alignment_subprocess(
                                        now_utc=now_utc,
                                        run_id=run_id,
                                        config_path=phase1_cfg_path,
                                        stage_env=stage_env,
                                    ),
                                )
                                intel_status = _norm(
                                    alignment_state.get("phase1_daily_intel_alignment_status", "")
                                ).lower()
                                _stage_exit(
                                    stage="phase1_intel",
                                    run_id=run_id,
                                    started=intel_stage_started,
                                    rc="0" if intel_status == "ok" else "1",
                                )
                            except Exception as exc:
                                _stage_exit(stage="phase1_intel", run_id=run_id, started=intel_stage_started, rc="1")
                                state["phase1_daily_intel_alignment_status"] = "failed"
                                state["phase1_daily_intel_alignment_run_id"] = run_id
                                state["phase1_daily_intel_alignment_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                                state["phase1_daily_intel_alignment_date"] = ""
                                state["phase1_daily_intel_alignment_error"] = f"{type(exc).__name__}:{exc}"
                                _write_state(state)
                                exit_code = 4 if "timeout" in _norm(exc).lower() else 5
                                _log(
                                    "FATAL phase1_intel_boundary_failure "
                                    f"run_id={run_id} "
                                    f"exit_code={exit_code} "
                                    f"error={type(exc).__name__}:{exc}"
                                )
                                raise SystemExit(exit_code)
                        else:
                            alignment_state = {
                                "phase1_daily_intel_alignment_status": "skipped_disabled",
                                "phase1_daily_intel_alignment_run_id": run_id,
                                "phase1_daily_intel_alignment_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            }
                            _stage_exit(
                                stage="phase1_intel",
                                run_id=run_id,
                                started=intel_stage_started,
                                rc="skipped",
                                note="disabled",
                            )
                        state.update(alignment_state)
                        if _is_phase1_intel_completed_status(
                            alignment_state.get("phase1_daily_intel_alignment_status", "")
                        ):
                            state["phase1_daily_intel_alignment_date"] = today_key
                        else:
                            state["phase1_daily_intel_alignment_date"] = ""
                        _log(
                            "phase1 daily_intel alignment "
                            f"status={alignment_state.get('phase1_daily_intel_alignment_status', '')} "
                            f"target_mode={alignment_state.get('phase1_daily_intel_alignment_target_mode', '')} "
                            f"resolved_count={alignment_state.get('phase1_daily_intel_alignment_target_resolved_count', '')} "
                            f"processed={alignment_state.get('phase1_daily_intel_alignment_processed_count', '')} "
                            f"missing_compliance={alignment_state.get('phase1_daily_intel_alignment_missing_compliance_rows', '')}"
                        )
                        if _norm(alignment_state.get("phase1_daily_intel_alignment_status", "")).lower() == "timeout":
                            _log(
                                "FATAL phase1_intel_timeout "
                                f"elapsed={alignment_state.get('phase1_daily_intel_alignment_elapsed_seconds', '')} "
                                f"timeout={alignment_state.get('phase1_daily_intel_alignment_timeout_seconds', '')}"
                            )
                            raise SystemExit(4)
                        _log(
                            "POST_INTEL_CHECK "
                            f"run_id={run_id} "
                            f"stage_phase1_publish={'1' if stage_enabled.get('phase1_publish', True) else '0'} "
                            f"publish_mode={_effective_phase1_mode(H_PHASE1_PUBLISH_MODE)} "
                            "next_step=phase1_build_seller_profiles"
                        )
                    # Keep seller profile + SOI coverage aligned with active Phase 1 cohort on every pilot cycle.
                    _log("phase1 build_seller_profiles start")
                    seller_state = _run_with_retries("phase1_build_seller_profiles", _build_seller_profiles)
                    state.update(seller_state)
                    _log(
                        "phase1 build_seller_profiles done "
                        f"status={seller_state.get('seller_profile_status', 'ok')} "
                        f"profile_rows={seller_state.get('seller_profile_rows', '')} "
                        f"soi_rows={seller_state.get('seller_soi_rows', '')}"
                    )
                    _log("phase1 split_health gate evaluation start")
                    gate_state = _resolve_h_split_gate(
                        now_utc=now_utc,
                        run_id=run_id,
                        mode_requested=mode_requested,
                        mode_effective=mode_effective,
                        state=state,
                    )
                    state.update(gate_state)
                    _transition_h_batch_state(run_id, "collect_done")
                    _log(
                        "phase1 split_health gate evaluation done "
                        f"fail={gate_state.get('h_gate_fail_count', '')} "
                        f"warn={gate_state.get('h_gate_warn_count', '')} "
                        f"block={gate_state.get('h_gate_block_live_writes', '')}"
                    )
                    pilot_gate_block = gate_state.get("h_gate_block_live_writes", "0") == "1"
                    pilot_read_only = bool(args.read_only) or pilot_gate_block
                    if mode_effective == "shadow":
                        _log(
                            "split_health_shadow_candidate "
                            f"fail={gate_state.get('h_gate_fail_count', '')} "
                            f"warn={gate_state.get('h_gate_warn_count', '')} "
                            f"candidate_block_live_writes={gate_state.get('h_gate_block_live_writes', '0')}"
                        )
                    elif mode_effective == "split":
                        _log(
                            "split_health_gate "
                            f"fail={gate_state.get('h_gate_fail_count', '')} "
                            f"warn={gate_state.get('h_gate_warn_count', '')} "
                            f"block_live_writes={'1' if pilot_gate_block else '0'} "
                            f"fail_closed={'1' if H_HEALTH_FAIL_CLOSED else '0'}"
                        )
                    pilot_stage_started = _stage_enter(stage="phase1_pilot", run_id=run_id)
                    state["phase1_pilot_started_run_id"] = run_id
                    state["phase1_pilot_started_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    state["phase1_post_pilot_transition_run_id"] = run_id
                    state["phase1_post_pilot_transition_status"] = "pilot_started"
                    state["phase1_publish_entry_run_id"] = ""
                    state["phase1_publish_entry_status"] = ""
                    _write_state(state)
                    if stage_enabled.get("phase1_pilot", True):
                        try:
                            pilot_state = _run_with_retries(
                                "phase1_pilot",
                                lambda: _run_phase1_pilot_subprocess(
                                    now_utc=now_utc,
                                    run_id=run_id,
                                    config_path=phase1_cfg_path,
                                    read_only=pilot_read_only,
                                    stage_env=stage_env,
                                ),
                                attempts=1,
                            )
                            _stage_exit(stage="phase1_pilot", run_id=run_id, started=pilot_stage_started, rc="0")
                        except Exception:
                            state["phase1_post_pilot_transition_run_id"] = run_id
                            state["phase1_post_pilot_transition_status"] = "pilot_failed"
                            _write_state(state)
                            _stage_exit(stage="phase1_pilot", run_id=run_id, started=pilot_stage_started, rc="1")
                            raise
                    else:
                        pilot_state = {
                            "phase1_pilot_step_status": "skipped_disabled",
                            "phase1_sku": "",
                            "phase1_skus_processed_count": "0",
                            "phase1_skus_processed_csv": "",
                            "phase1_skus_skipped_cooldown_count": "0",
                            "executioner_probe_type": "SKIPPED_STAGE",
                            "write_status": "SKIPPED_STAGE",
                            "final_ceiling_landed_gbp": "",
                            "reason_codes_csv": "PHASE1_PILOT_DISABLED",
                            "phase1_next_due_sleep_seconds": "",
                            "phase1_next_due_sku": "",
                        }
                        _stage_exit(
                            stage="phase1_pilot",
                            run_id=run_id,
                            started=pilot_stage_started,
                            rc="skipped",
                            note="disabled",
                        )
                        state["phase1_post_pilot_transition_run_id"] = run_id
                        state["phase1_post_pilot_transition_status"] = "pilot_skipped"
                    pilot_state["phase1_split_gate_read_only"] = "1" if pilot_read_only else "0"
                    pilot_state["phase1_split_gate_mode"] = mode_effective
                    state.update(pilot_state)
                    state["phase1_post_pilot_transition_run_id"] = run_id
                    state["phase1_post_pilot_transition_status"] = "pilot_completed"
                    _write_state(state)
                    _log(
                        "phase1 transition_state "
                        f"run_id={run_id} "
                        "status=pilot_completed"
                    )
                    # Self-heal intel drift: if pilot reports missing/stale daily intel
                    # for the normal universe, clear the once-per-day intel lock.
                    # clear the once-per-day intel lock so next loop reruns A016.
                    intel_gate_missing = _norm(
                        pilot_state.get(
                            "daily_intel_normal_missing_count",
                            pilot_state.get("daily_intel_missing_count", "0"),
                        )
                    )
                    intel_missing_signal = intel_gate_missing not in {"", "0"}
                    if intel_missing_signal and stage_enabled.get("phase1_intel", True):
                        state["phase1_daily_intel_alignment_date"] = ""
                        _log(
                            "phase1 daily_intel alignment invalidated "
                            "reason=pilot_missing_or_stale_intel; will_retry_next_loop=1"
                        )
                    if H_PHASE1_RUNTIME_FLOOR_SNAPSHOT_ENABLED:
                        floor_snapshot_state = _run_with_retries(
                            "phase1_runtime_floor_snapshot",
                            lambda: _write_phase1_runtime_floor_snapshot(now_utc),
                        )
                    else:
                        floor_snapshot_state = {
                            "phase1_runtime_floor_snapshot_status": "skipped_disabled",
                            "phase1_runtime_floor_snapshot_rows": "",
                            "phase1_runtime_floor_snapshot_trace_rows": "",
                        }
                    state.update(floor_snapshot_state)
                    _log(
                        "phase1 post_pilot_continue "
                        f"run_id={run_id} "
                        f"pilot_status={pilot_state.get('phase1_pilot_step_status', '')} "
                        f"floor_snapshot_status={floor_snapshot_state.get('phase1_runtime_floor_snapshot_status', '')}"
                    )
                    floor_table_state = _run_with_retries(
                        "phase1_floor_table_build",
                        lambda: _run_phase1_floor_table_build_subprocess(
                            now_utc=now_utc,
                            run_id=run_id,
                            stage_env=stage_env,
                        ),
                    )
                    state.update(floor_table_state)
                    _log(
                        "phase1 floor_table_build done "
                        f"status={floor_table_state.get('phase1_floor_table_status', '')} "
                        f"rows_written={floor_table_state.get('phase1_floor_table_rows_written', '')}"
                    )
                    _transition_h_batch_state(run_id, "compute_done")
                    if _norm(pilot_state.get("daily_intel_gate_policy", "")):
                        _log(
                            "h_daily_intel_gate_decision "
                            f"today_utc={now_utc.date().isoformat()} "
                            f"normal_processed={pilot_state.get('daily_intel_normal_processed_count', '')} "
                            f"normal_missing={pilot_state.get('daily_intel_normal_missing_count', '')} "
                            f"exception_processed={pilot_state.get('daily_intel_exception_processed_count', '')} "
                            f"exception_missing={pilot_state.get('daily_intel_exception_missing_count', '')} "
                            f"policy={pilot_state.get('daily_intel_gate_policy', '')}"
                        )
                    if pilot_state.get("daily_intel_missing_for_today", "0") == "1":
                        _log(
                            "phase1 h_cycle daily_intel missing_for_today=1 "
                            f"normal_missing_count={pilot_state.get('daily_intel_normal_missing_count', pilot_state.get('daily_intel_missing_count', ''))} "
                            f"exception_missing_count={pilot_state.get('daily_intel_exception_missing_count', '0')} "
                            f"processed_count={pilot_state.get('phase1_skus_processed_count', '')} "
                            f"alignment_mode={H_PHASE1_INTEL_ALIGNMENT_MODE} "
                            f"daily_intel_path={ROOT / 'data' / 'sku_daily_intel.csv'}"
                        )
                    if _norm(pilot_state.get("phase1_scope_total", "")):
                        _log(
                            "h_universe_scope_filter "
                            f"today_utc={now_utc.date().isoformat()} "
                            f"scope_total={pilot_state.get('phase1_scope_total', '')} "
                            f"excluded_dropped={pilot_state.get('phase1_scope_excluded_dropped_count', '')} "
                            f"excluded_parked={pilot_state.get('phase1_scope_excluded_parked_count', '')} "
                            f"remaining={pilot_state.get('phase1_scope_remaining_count', '')}"
                        )
                    if _norm(pilot_state.get("phase1_stock_scope_total", "")):
                        _log(
                            "h_stock_snapshot_decision "
                            f"today_utc={now_utc.date().isoformat()} "
                            f"chosen_path={pilot_state.get('phase1_stock_source_path', '')} "
                            f"chosen_date={pilot_state.get('phase1_stock_snapshot_date', '')} "
                            f"age_hours={pilot_state.get('phase1_stock_snapshot_age_hours', '')} "
                            f"is_fallback={pilot_state.get('phase1_stock_snapshot_is_fallback', '')} "
                            f"action={pilot_state.get('phase1_stock_snapshot_action', '')}"
                        )
                        _log(
                            "h_universe_stock_decision "
                            f"today_utc={now_utc.date().isoformat()} "
                            f"scope_total={pilot_state.get('phase1_stock_scope_total', '')} "
                            f"eligible={pilot_state.get('phase1_stock_eligible_count', '')} "
                            f"excluded_oos={pilot_state.get('phase1_stock_excluded_oos_count', '')} "
                            f"excluded_unknown={pilot_state.get('phase1_stock_excluded_unknown_count', '')} "
                                f"stock_source={pilot_state.get('phase1_stock_source_path', '')} "
                                f"sku_col={pilot_state.get('phase1_stock_sku_col', '')} "
                                f"stock_col={pilot_state.get('phase1_stock_qty_col', '')}"
                        )
                    if _norm(pilot_state.get("phase1_exception_enabled", "")):
                        _log(
                            "h_universe_exception_decision "
                            f"today_utc={now_utc.date().isoformat()} "
                            f"enabled={pilot_state.get('phase1_exception_enabled', '')} "
                            f"normal_count={pilot_state.get('phase1_exception_normal_count', '')} "
                            f"exception_count={pilot_state.get('phase1_exception_count', '')} "
                            f"overlap_count={pilot_state.get('phase1_exception_overlap_count', '')} "
                            f"final_process_count={pilot_state.get('phase1_exception_final_process_count', '')}"
                        )
                    if _norm(pilot_state.get("phase1_stock_snapshot_status", "")).upper() == "WARN":
                        _log(
                            "phase1 h_cycle warn stock_snapshot_fallback=1 "
                            f"chosen_date={pilot_state.get('phase1_stock_snapshot_date', '')} "
                            f"age_hours={pilot_state.get('phase1_stock_snapshot_age_hours', '')} "
                            f"source={pilot_state.get('phase1_stock_source_path', '')}"
                        )
                    _log(
                        "phase1 h_cycle sku="
                        f"{pilot_state.get('phase1_sku', '')} "
                        f"processed_count={pilot_state.get('phase1_skus_processed_count', '1')} "
                        f"processed_skus={pilot_state.get('phase1_skus_processed_csv', pilot_state.get('phase1_sku', ''))} "
                        f"skipped_cooldown_count={pilot_state.get('phase1_skus_skipped_cooldown_count', '0')} "
                        f"state={pilot_state.get('executioner_probe_type', '')} "
                        f"write_status={pilot_state.get('write_status', '')} "
                        f"ceiling={pilot_state.get('final_ceiling_landed_gbp', '')} "
                        f"reason_codes={pilot_state.get('reason_codes_csv', '')}"
                    )
                    _log(
                        "phase1 runtime_floor_snapshot "
                        f"status={floor_snapshot_state.get('phase1_runtime_floor_snapshot_status', '')} "
                        f"rows={floor_snapshot_state.get('phase1_runtime_floor_snapshot_rows', '')} "
                        f"trace_rows={floor_snapshot_state.get('phase1_runtime_floor_snapshot_trace_rows', '')}"
                    )
                    _log(
                        "phase1 floor_table_build "
                        f"status={floor_table_state.get('phase1_floor_table_status', '')} "
                        f"required={floor_table_state.get('phase1_floor_table_required_skus', '')} "
                        f"rows={floor_table_state.get('phase1_floor_table_rows_written', '')} "
                        f"populated={floor_table_state.get('phase1_floor_table_populated', '')} "
                        f"reason_coded={floor_table_state.get('phase1_floor_table_reason_coded', '')}"
                    )
                    state["phase1_publish_entry_run_id"] = run_id
                    state["phase1_publish_entry_status"] = "entered"
                    state["phase1_post_pilot_transition_run_id"] = run_id
                    state["phase1_post_pilot_transition_status"] = "publish_entered"
                    _write_state(state)
                    _log(
                        "phase1 transition_state "
                        f"run_id={run_id} "
                        "status=publish_entered"
                    )
                    _log("phase1 publish_start")
                    _trace_publish_gap(run_id, "publish_start")
                    publish_stage_started = _stage_enter(stage="phase1_publish", run_id=run_id)
                    _write_runtime_status("PUBLISHING", run_id=run_id, stage="phase1_publish", detail="publish_start")
                    state["phase1_publish_started"] = "1"
                    state["phase1_publish_started_run_id"] = run_id
                    state["phase1_publish_completed"] = "0"
                    _write_state(state)
                    _log(f"PUBLISH_BLOCK_REACHED run_id={run_id}")
                    if stage_enabled.get("phase1_publish", True):
                        try:
                            _trace_publish_gap(
                                run_id,
                                "publish_subprocess_start",
                                mode=_effective_phase1_mode(H_PHASE1_PUBLISH_MODE),
                            )
                            observation_state = _run_with_retries(
                                "phase1_publish",
                                lambda: _run_phase1_observation_publish_subprocess(
                                    now_utc=now_utc,
                                    run_id=run_id,
                                    stage_env=stage_env,
                                ),
                            )
                            _trace_publish_gap(run_id, "publish_subprocess_end", rc="0")
                            _stage_exit(stage="phase1_publish", run_id=run_id, started=publish_stage_started, rc="0")
                        except Exception:
                            _trace_publish_gap(run_id, "publish_subprocess_end", rc="1")
                            _stage_exit(stage="phase1_publish", run_id=run_id, started=publish_stage_started, rc="1")
                            raise
                    else:
                        _log("publish_disabled_reason=stage_phase1_publish_disabled")
                        _trace_publish_gap(run_id, "publish_subprocess_start", mode="disabled")
                        _trace_publish_gap(run_id, "publish_subprocess_end", rc="0")
                        observation_state = {
                            "phase1_observation_publish_status": "skipped_disabled",
                            "phase1_publish_completed": "1",
                            "phase1_observation_publish_run_id": run_id,
                            "phase1_observation_publish_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "phase1_observation_publish_date_utc": now_utc.date().isoformat(),
                        }
                        _stage_exit(
                            stage="phase1_publish",
                            run_id=run_id,
                            started=publish_stage_started,
                            rc="skipped",
                            note="disabled",
                        )
                    state.update(observation_state)
                    observation_status = _norm(observation_state.get("phase1_observation_publish_status", "")).lower()
                    publish_completed = (
                        observation_state.get("phase1_publish_completed", "") == "1"
                        or _is_publish_completed_status(observation_status)
                    )
                    state["phase1_publish_completed"] = "1" if publish_completed else "0"
                    if (
                        stage_enabled.get("phase1_publish", True)
                        and state.get("phase1_publish_started") == "1"
                        and state.get("phase1_publish_started_run_id") == run_id
                        and state.get("phase1_publish_completed") != "1"
                    ):
                        state["phase1_observation_publish_error"] = "publish_interrupted_or_incomplete"
                        _write_state(state)
                        _log(
                            "FATAL publish_incomplete "
                            f"current={run_id} "
                            f"status={observation_state.get('phase1_observation_publish_status', '')} "
                            f"error={observation_state.get('phase1_observation_publish_error', '')}"
                        )
                        raise SystemExit(3)
                    _log(
                        "phase1 observation_publish "
                        f"status={observation_state.get('phase1_observation_publish_status', '')} "
                        f"view_tab={observation_state.get('phase1_observation_publish_view_tab', '')} "
                        f"rows={observation_state.get('phase1_observation_publish_rows', '')} "
                        f"error={observation_state.get('phase1_observation_publish_error', '')}"
                    )
                    _log(
                        "phase1 publish_done "
                        f"status={observation_state.get('phase1_observation_publish_status', '')}"
                    )
                    report_state = _run_h_daily_market_reports_subprocess(
                        now_utc=now_utc,
                        run_id=run_id,
                        stage_env=stage_env,
                    )
                    state.update(report_state)
                    _write_state(state)
                    _log(
                        "h daily_market_reports "
                        f"status={report_state.get('h_daily_market_reports_status', '')} "
                        f"html={report_state.get('h_daily_market_report_html', '')} "
                        f"pdf={report_state.get('h_daily_market_report_pdf', '')} "
                        f"price_charts={report_state.get('h_daily_market_report_price_charts', '')} "
                        f"seller_mix_charts={report_state.get('h_daily_market_report_seller_mix_charts', '')} "
                        f"error={report_state.get('h_daily_market_reports_error', '')}"
                    )
                    if report_state.get("h_daily_market_reports_status", "") == "ok":
                        _log("H005 report generation ran")
                    _write_runtime_status(
                        "PUBLISHING",
                        run_id=run_id,
                        stage="phase1_publish",
                        detail="publish_done",
                        publish_status=_norm(observation_state.get("phase1_observation_publish_status", "")),
                        error=_norm(observation_state.get("phase1_observation_publish_error", "")),
                    )
                    current_publish_marker = _read_first_line(H_CYCLE_LAST_PUBLISH_RUN_PATH)
                    _log(
                        "publish_state "
                        f"current={run_id} "
                        f"last_publish={current_publish_marker} "
                        f"completed={'1' if publish_completed else '0'}"
                    )
                    publish_sheet_id = _norm(
                        observation_state.get("phase1_observation_publish_sheet_id", "")
                    ) or _norm(PHASE1_OBSERVATION_SHEET_ID)
                    publish_tab = _norm(observation_state.get("phase1_observation_publish_view_tab", ""))
                    if publish_sheet_id:
                        _log(
                            "phase1 observation_publish_target "
                            f"sheet_id={publish_sheet_id} "
                            f"sheet_url=https://docs.google.com/spreadsheets/d/{publish_sheet_id} "
                            f"view_tab={publish_tab}"
                        )
                    if (
                        PHASE1_OBSERVATION_PUBLISH_ENABLED
                        and stage_enabled.get("phase1_publish", True)
                        and observation_status != "ok"
                    ):
                        _write_state(state)
                        _log(
                            "FATAL publish_missing "
                            f"status={observation_state.get('phase1_observation_publish_status', '')} "
                            f"error={observation_state.get('phase1_observation_publish_error', '')}"
                        )
                        raise SystemExit(3)
                    if (
                        stage_enabled.get("phase1_publish", True)
                        and publish_completed
                        and current_publish_marker != run_id
                    ):
                        # Marker is committed in publish commit phase, not before.
                        pass
                    staged_diag = _phase1_staged_precommit_diag(run_id)
                    _log(
                        "phase1 staged_precommit_diag "
                        f"staged_dir={staged_diag.get('staged_dir', '')} "
                        f"staged_file_count={staged_diag.get('staged_file_count', '0')} "
                        f"expected_tables={staged_diag.get('expected_tables', '')} "
                        f"missing_tables={staged_diag.get('missing_tables', '')}"
                    )
                    if int(staged_diag.get("staged_file_count", "0") or "0") <= 0:
                        reason_code = "H_STAGED_FILES_ZERO"
                        state["phase1_staged_publish_reason_code"] = reason_code
                        state["phase1_observation_publish_error"] = (
                            f"staged_files_zero_before_publish_commit run_id={run_id} reason_code={reason_code}"
                        )
                        _write_state(state)
                        _log(
                            "FATAL publish_precheck_failed "
                            f"run_id={run_id} reason_code={reason_code} "
                            f"staged_dir={staged_diag.get('staged_dir', '')} "
                            f"staged_file_count={staged_diag.get('staged_file_count', '0')}"
                        )
                        raise SystemExit(3)
                    _transition_h_batch_state(run_id, "validate_done")
                    _log(f"publish_commit_start run_id={run_id}")
                    _trace_publish_gap(run_id, "publish_commit_start")
                    staged_publish_state = _publish_phase1_commit(
                        run_id=run_id,
                        now_utc=now_utc,
                        observation_state=observation_state,
                    )
                    state.update(staged_publish_state)
                    _log(
                        "phase1 staged_publish "
                        f"status={staged_publish_state.get('phase1_staged_publish_status', '')} "
                        f"files={staged_publish_state.get('phase1_staged_publish_files', '')}"
                    )
                    if staged_publish_state.get("phase1_staged_publish_status", "") != "ok":
                        state["phase1_observation_publish_error"] = f"staged_publish_failed run_id={run_id}"
                        _write_state(state)
                        raise SystemExit(3)
                    _trace_publish_gap(
                        run_id,
                        "publish_commit_end",
                        marker=_read_first_line(H_CYCLE_LAST_PUBLISH_RUN_PATH),
                        completed=_read_first_line(H_CYCLE_LAST_COMPLETED_RUN_PATH),
                    )
                    _log(
                        "publish_commit_end "
                        f"run_id={run_id} "
                        f"last_publish={_read_first_line(H_CYCLE_LAST_PUBLISH_RUN_PATH)} "
                        f"last_completed={_read_first_line(H_CYCLE_LAST_COMPLETED_RUN_PATH)}"
                    )
                    _write_runtime_status(
                        "RUNNING",
                        run_id=run_id,
                        stage="phase1_publish",
                        detail="publish_commit_end",
                        publish_status=_norm(observation_state.get("phase1_observation_publish_status", "")),
                    )
                    current_publish_marker = _read_first_line(H_CYCLE_LAST_PUBLISH_RUN_PATH)
                    if current_publish_marker != run_id:
                        state["phase1_observation_publish_error"] = (
                            "publish_marker_mismatch "
                            f"current={run_id} last_publish={current_publish_marker}"
                        )
                        _write_state(state)
                        _log(
                            "FATAL publish_marker_mismatch "
                            f"current={run_id} "
                            f"last_publish={current_publish_marker} "
                            f"status={observation_state.get('phase1_observation_publish_status', '')}"
                        )
                        raise SystemExit(3)
                    _log(
                        "publish_state_commit "
                        f"current={run_id} "
                        f"last_publish={current_publish_marker}"
                    )
                    _transition_h_batch_state(run_id, "published")
                    _trace_publish_gap(
                        run_id,
                        "completed_marker_written",
                        marker=_read_first_line(H_CYCLE_LAST_COMPLETED_RUN_PATH),
                    )
                    # Per-cycle finalizer commit:
                    # launcher validates current run id against H_last_finalized_run_id.txt
                    # after child exit. In long-running (run_once=0) mode, process-level
                    # finally may not run for a while, so commit finalized marker here.
                    _mark_finalizer_reached(run_id)
                    _transition_h_batch_state(run_id, "finalized")
                    _trace_publish_gap(run_id, "finalizer_cycle_commit", rc="0")
                    _log(f"run_completed_marker written run_id={run_id}")
                    state["phase1_publish_started"] = "0"
                    state["phase1_publish_started_run_id"] = run_id
                    _write_state(state)
                    if run_once:
                        loop_rc = "0"
                        _log("run_once enabled - exiting after one loop")
                        break
                    next_due_seconds = _to_float(pilot_state.get("phase1_next_due_sleep_seconds", ""))
                    effective_sleep_seconds = loop_sleep_seconds
                    sleep_mode = "fixed"
                    if next_due_seconds is not None and next_due_seconds > 0:
                        effective_sleep_seconds = max(next_due_seconds, 1.0)
                        sleep_mode = "next_due"
                    wake_at_utc = (
                        now_utc + timedelta(seconds=effective_sleep_seconds)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    _log(
                        "cycle_sleep "
                        f"seconds={_fmt(_r2(effective_sleep_seconds))} "
                        f"mode={sleep_mode} "
                        f"wake_at_utc={wake_at_utc} "
                        f"next_due_seconds={pilot_state.get('phase1_next_due_sleep_seconds', '')} "
                        f"next_due_sku={pilot_state.get('phase1_next_due_sku', '')}"
                    )
                    _write_runtime_status(
                        "SLEEPING",
                        run_id=run_id,
                        stage="cycle_sleep",
                        detail=f"mode={sleep_mode}",
                        wake_at_utc=wake_at_utc,
                        next_due_sku=_norm(pilot_state.get("phase1_next_due_sku", "")),
                        next_due_seconds=_norm(pilot_state.get("phase1_next_due_sleep_seconds", "")),
                        publish_status=_norm(observation_state.get("phase1_observation_publish_status", "")),
                    )
                    loop_rc = "0"
                    if _restart_drain_requested():
                        _write_runtime_status(
                            "STOPPING",
                            run_id=run_id,
                            stage="cycle_sleep",
                            detail="restart_drain_requested_after_safe_cycle",
                        )
                        _log_restart_drain_once(
                            event_key="after_safe_cycle_boundary_wait",
                            message=(
                                "restart_drain requested - completed current safe cycle; "
                                "skipping next cycle start and exiting loop"
                            ),
                        )
                        break
                    _sleep_with_lock_heartbeat(effective_sleep_seconds)
                    continue

                last_head = _to_dt(state.get("last_head_utc", ""))
                last_supervisor = _to_dt(state.get("last_supervisor_utc", ""))
                last_executioner = _to_dt(state.get("last_executioner_utc", ""))

                due_head = last_head is None or now_utc >= last_head + timedelta(hours=head_cadence_hours)
                due_supervisor = last_supervisor is None or now_utc >= last_supervisor + timedelta(hours=supervisor_cadence_hours)
                due_executioner = (
                    last_executioner is None
                    or now_utc >= last_executioner + timedelta(minutes=executioner_cadence_minutes)
                )

                if _kill_switch_active():
                    _log("kill_switch active - executioner paused")
                    due_executioner = False

                if due_supervisor or due_executioner:
                    if stage_enabled.get("snapshot_refresh", True):
                        refresh_state = _run_with_retries(
                            "legacy_snapshot_refresh",
                            lambda: _refresh_offer_snapshots(
                                now_utc,
                                state,
                                item_offers_enabled=stage_enabled.get("item_offers", True),
                                stage_run_id=run_id,
                            ),
                        )
                    else:
                        refresh_state = {
                            "snapshot_refresh_attempted": "0",
                            "snapshot_refresh_status": "skipped_disabled",
                            "snapshot_refresh_error": "",
                        }
                    if refresh_state:
                        state.update(refresh_state)
                        _write_state(state)
                    refresh_status = _norm(state.get("snapshot_refresh_status", "")).lower()
                    if stage_enabled.get("snapshot_refresh", True) and refresh_status != "ok":
                        _log(
                            "FATAL snapshot_refresh_failed "
                            f"status={state.get('snapshot_refresh_status', '')} "
                            f"error={state.get('snapshot_refresh_error', '')}"
                        )
                        raise SystemExit(2)

                if due_head:
                    head_state = _run_with_retries("legacy_head_step", lambda: _run_head(now_utc))
                    state.update(head_state)
                    state["last_head_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    _write_state(state)
                    _log("head cadence run complete")

                if due_supervisor:
                    supervisor_state = _run_with_retries("legacy_supervisor_step", lambda: _run_supervisor(now_utc))
                    state.update(supervisor_state)
                    state["last_supervisor_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    _write_state(state)
                    _log("supervisor cadence run complete")

                if due_executioner:
                    executioner_state = _run_with_retries(
                        "legacy_executioner_step",
                        lambda: _run_executioner(now_utc, run_id, live_write=legacy_live_write, state=state),
                    )
                    state.update(executioner_state)
                    state["last_executioner_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    _write_state(state)

                if run_once:
                    loop_rc = "0"
                    _log("run_once enabled - exiting after one loop")
                    break
                _log(
                    "cycle_sleep "
                    f"seconds={_fmt(_r2(loop_sleep_seconds))} "
                    f"wake_at_utc={(now_utc + timedelta(seconds=loop_sleep_seconds)).strftime('%Y-%m-%dT%H:%M:%SZ')} "
                    f"due_head={'1' if due_head else '0'} "
                    f"due_supervisor={'1' if due_supervisor else '0'} "
                    f"due_executioner={'1' if due_executioner else '0'}"
                )
                _write_runtime_status(
                    "SLEEPING",
                    run_id=run_id,
                    stage="cycle_sleep",
                    detail="legacy_cadence_wait",
                    wake_at_utc=(now_utc + timedelta(seconds=loop_sleep_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
                loop_rc = "0"
                if _restart_drain_requested():
                    _write_runtime_status(
                        "STOPPING",
                        run_id=run_id,
                        stage="cycle_sleep",
                        detail="restart_drain_requested_after_safe_cycle",
                    )
                    _log_restart_drain_once(
                        event_key="legacy_cadence_boundary_wait",
                        message=(
                            "restart_drain requested - legacy cadence boundary reached; "
                            "skipping next cycle start and exiting loop"
                        ),
                    )
                    break
                _sleep_with_lock_heartbeat(loop_sleep_seconds)
            except BaseException as exc:
                if cycle_run_id:
                    _transition_h_batch_state(cycle_run_id, "failed", reason=f"{type(exc).__name__}:{exc}")
                _write_runtime_status(
                    "ERROR",
                    run_id=cycle_run_id,
                    stage=_LAST_STAGE_NAME,
                    detail="cycle_error",
                    error=f"{type(exc).__name__}:{exc}",
                )
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    if isinstance(exc, SystemExit):
                        code = exc.code
                        loop_rc = str(code if isinstance(code, int) else 1)
                    else:
                        loop_rc = "130"
                    raise
                if cycle_manifest is not None:
                    append_step(
                        cycle_manifest,
                        name="h_cycle_iteration",
                        script_or_function="run_H_pricing_cycle.py",
                        inputs=[],
                        outputs=[],
                        rc=1,
                        notes=f"error={type(exc).__name__}:{exc}",
                        started_at=cycle_started,
                        ended_at=utc_now_iso(),
                    )
                _log(f"cycle_error {type(exc).__name__}: {exc}")
                loop_rc = "1"
                if run_once:
                    raise
                _log(f"cycle_recover sleep_seconds={_fmt(_r2(H_LOOP_ERROR_SLEEP_SECONDS))}")
                _sleep_with_lock_heartbeat(H_LOOP_ERROR_SLEEP_SECONDS)
            finally:
                finalizer_run_id = _norm(cycle_run_id) or _context_run_id()
                if pre_cycle_drain_exit:
                    _trace_publish_gap("", "enter_finalizer_skip_pre_cycle_drain", rc=loop_rc)
                elif not _norm(cycle_run_id):
                    _trace_publish_gap("", "enter_finalizer_skip_no_cycle", rc=loop_rc)
                else:
                    if (
                        _norm(loop_rc) == "0"
                        and _norm(finalizer_run_id)
                        and _norm(state.get("phase1_intel_started_run_id", "")) == _norm(finalizer_run_id)
                    ):
                        publish_started_for_run = _norm(state.get("phase1_publish_started_run_id", "")) == _norm(finalizer_run_id)
                        publish_completed_for_run = _norm(state.get("phase1_publish_completed", "")) == "1"
                        if not (publish_started_for_run and publish_completed_for_run):
                            loop_rc = "3"
                            state["phase1_observation_publish_error"] = "publish_skipped"
                            _write_state(state)
                            _log(
                                "FATAL publish_skipped "
                                f"current={finalizer_run_id} "
                                f"phase1_intel_started_run_id={state.get('phase1_intel_started_run_id', '')} "
                                f"phase1_publish_started_run_id={state.get('phase1_publish_started_run_id', '')} "
                                f"phase1_publish_completed={state.get('phase1_publish_completed', '')}"
                            )
                            _transition_h_batch_state(finalizer_run_id, "failed", reason="publish_skipped")
                    _trace_publish_gap(finalizer_run_id, "enter_finalizer", rc=loop_rc)
                    if _norm(loop_rc) == "0":
                        publish_proof = _read_publish_proof_details(expected_run_id=finalizer_run_id)
                        publish_proof_run_id = _norm(publish_proof.get("selected_run_id", ""))
                        _log(
                            "publish_proof_check "
                            f"current={finalizer_run_id} "
                            f"selected_source={publish_proof.get('selected_source', '') or 'none'} "
                            f"selected_run_id={publish_proof_run_id} "
                            f"publish_marker_path={publish_proof.get('publish_marker_path', '')} "
                            f"publish_marker_run_id={publish_proof.get('publish_marker_run_id', '')} "
                            f"publish_info_path={publish_proof.get('publish_info_path', '')} "
                            f"publish_info_run_id={publish_proof.get('publish_info_run_id', '')}"
                        )
                        if _norm(publish_proof_run_id) != _norm(finalizer_run_id):
                            loop_rc = "3"
                            state["phase1_observation_publish_error"] = "FINALIZE_BLOCKED_NO_PUBLISH"
                            _write_state(state)
                            _log(
                                "FINALIZE_BLOCKED_NO_PUBLISH "
                                f"current={finalizer_run_id} "
                                f"publish_run_id={publish_proof_run_id} "
                                f"selected_source={publish_proof.get('selected_source', '') or 'none'} "
                                f"publish_marker_path={publish_proof.get('publish_marker_path', '')} "
                                f"publish_marker_run_id={publish_proof.get('publish_marker_run_id', '')} "
                                f"publish_info_path={publish_proof.get('publish_info_path', '')} "
                                f"publish_info_run_id={publish_proof.get('publish_info_run_id', '')}"
                            )
                            _transition_h_batch_state(finalizer_run_id, "failed", reason="FINALIZE_BLOCKED_NO_PUBLISH")
                        else:
                            _mark_finalizer_reached(finalizer_run_id)
                            _transition_h_batch_state(finalizer_run_id, "finalized")
                    if _norm(loop_rc) != "0" and _norm(finalizer_run_id):
                        _clear_run_in_progress(finalizer_run_id, reason=f"terminal_failure_rc={loop_rc}")
                    _trace_publish_gap(finalizer_run_id, "finalizer_reached", rc=loop_rc)
                if cycle_manifest is not None:
                    if not cycle_manifest.get("steps"):
                        append_step(
                            cycle_manifest,
                            name="h_cycle_iteration",
                            script_or_function="run_H_pricing_cycle.py",
                            inputs=[],
                            outputs=[
                                "out/h_pricing_cycle_state.json",
                                "data/execution_log.csv",
                                "out/systems/H/live/h110_sku_lifecycle_log.csv",
                                "out/h_executioner_action_log.csv",
                                "out/phase1_runtime_floor_snapshot_latest.csv",
                            ],
                            rc=_safe_int(loop_rc, 1),
                            notes=f"cycle_run_id={cycle_run_id}",
                            started_at=cycle_started,
                            ended_at=utc_now_iso(),
                        )
                    health_path, _health_source = _choose_h_gate_checklist_path()
                    manifest_final_state = None
                    if _norm(loop_rc) == "0" and _norm(finalizer_run_id):
                        completed_run_id = _read_first_line(H_CYCLE_LAST_COMPLETED_RUN_PATH)
                        finalized_run_id = _read_first_line(H_LAST_FINALIZED_RUN_ID_PATH)
                        if _norm(completed_run_id) == _norm(finalizer_run_id) and _norm(finalized_run_id) == _norm(finalizer_run_id):
                            manifest_final_state = "completed"
                    finalize_manifest(
                        cycle_manifest,
                        health_checklist_path=health_path,
                        end_time=utc_now_iso(),
                        final_state=manifest_final_state,
                    )
                    try:
                        _write_runtime_readiness(
                            run_id=_norm(finalizer_run_id) or _norm(cycle_run_id),
                            manifest_final_state=_norm(cycle_manifest.get("final_state", "")),
                            item_offers_enabled=bool(stage_enabled.get("item_offers", True)),
                            now_utc=_utc_now(),
                        )
                    except Exception as readiness_exc:
                        _log(f"runtime_readiness_write_error {type(readiness_exc).__name__}: {readiness_exc}")
                    write_manifest(ROOT, cycle_manifest)
    finally:
        _release_lock_with_report(
            stage=_LAST_STAGE_NAME,
            rc_hint=loop_rc,
            run_id=_context_run_id() or cycle_run_id,
        )
        if _norm(loop_rc) == "0":
            _write_runtime_status("STOPPED", run_id=_context_run_id() or cycle_run_id, stage=_LAST_STAGE_NAME, detail="process_exit rc=0")
        elif _norm(loop_rc):
            _write_runtime_status("ERROR", run_id=_context_run_id() or cycle_run_id, stage=_LAST_STAGE_NAME, detail=f"process_exit rc={loop_rc}")
    success_run_id = _context_run_id() or _norm(cycle_run_id)
    last_finalized_run_id = _read_first_line(H_LAST_FINALIZED_RUN_ID_PATH)
    if success_run_id and _norm(last_finalized_run_id) != success_run_id:
        _trace_publish_gap(
            success_run_id,
            "return_blocked_missing_finalizer",
            last_finalized=last_finalized_run_id,
        )
        _log(
            "FATAL success_exit_blocked_missing_finalizer "
            f"run_id={success_run_id} "
            f"last_finalized={last_finalized_run_id}"
        )
        raise SystemExit(3)
    _trace_publish_gap(success_run_id, "about_to_return", rc="0")
    return 0


if __name__ == "__main__":
    try:
        rc = int(main())
        _INTERRUPTION_CLASS_HINT = "0"
        _INTERRUPTION_SIGNAL_HINT = ""
        _EXIT_CATEGORY_HINT = "main_return"
        rc = _promote_zero_exit_without_finalizer(rc)
    except KeyboardInterrupt:
        _EXIT_CODE_HINT = "130"
        _INTERRUPTION_CLASS_HINT = "1"
        _INTERRUPTION_SIGNAL_HINT = "SIGINT"
        _EXIT_CATEGORY_HINT = "keyboard_interrupt"
        _append_h_parent_trace("process_exit_keyboard_interrupt", rc="130")
        _log("process_exit reason=keyboard_interrupt rc=130")
        sys.exit(130)
    except SystemExit as exc:
        code = exc.code
        rc = int(code) if isinstance(code, int) else 1
        rc = _promote_zero_exit_without_finalizer(rc)
        _EXIT_CODE_HINT = str(rc)
        if rc in (130, 3):
            _INTERRUPTION_CLASS_HINT = "1"
            if not _norm(_INTERRUPTION_SIGNAL_HINT):
                _INTERRUPTION_SIGNAL_HINT = "SIGINT" if rc == 130 else ""
            _EXIT_CATEGORY_HINT = _norm(_EXIT_CATEGORY_HINT) or "system_exit_interruption"
        else:
            _INTERRUPTION_CLASS_HINT = "0"
            _INTERRUPTION_SIGNAL_HINT = ""
            _EXIT_CATEGORY_HINT = "system_exit"
        _append_h_parent_trace("process_exit_system_exit", code=code, rc=rc)
        _log(f"process_exit reason=system_exit code={code!r} rc={rc}")
        raise SystemExit(rc)
    except BaseException as exc:
        _EXIT_CODE_HINT = "1"
        _INTERRUPTION_CLASS_HINT = "0"
        _INTERRUPTION_SIGNAL_HINT = ""
        _EXIT_CATEGORY_HINT = "unhandled_exception"
        _append_h_parent_trace(
            "process_exit_unhandled_exception",
            error_type=type(exc).__name__,
            detail=str(exc)[:400],
        )
        _log(f"process_exit reason=unhandled_exception type={type(exc).__name__} detail={exc}")
        raise
    _EXIT_CODE_HINT = str(rc)
    _INTERRUPTION_CLASS_HINT = "0"
    _INTERRUPTION_SIGNAL_HINT = ""
    _EXIT_CATEGORY_HINT = "main_return"
    _append_h_parent_trace("process_exit_main_return", rc=rc)
    _log(f"process_exit reason=main_return rc={rc}")
    raise SystemExit(rc)

