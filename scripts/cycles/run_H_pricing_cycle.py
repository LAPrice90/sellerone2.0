from __future__ import annotations

import argparse
import atexit
import contextlib
import csv
import faulthandler
import hashlib
import importlib
import io
import json
import os
import re
import signal
import shutil
import stat
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
try:
    from scripts.core.flow_health_gate import flow_gate_checklist_path
except ModuleNotFoundError:
    from core.flow_health_gate import flow_gate_checklist_path
try:
    from scripts.core.storage import write_dataframe_with_sql_compat
except ModuleNotFoundError:
    from core.storage import write_dataframe_with_sql_compat
try:
    from scripts.core.runtime_owner_contract import (
        RuntimeOwnerContractError,
        assert_flow_owner_mapping,
        is_truthy,
    )
except ModuleNotFoundError:
    from core.runtime_owner_contract import (
        RuntimeOwnerContractError,
        assert_flow_owner_mapping,
        is_truthy,
    )
try:
    from scripts.core.cycle_failure_events import (
        classify_failure_cause,
        tail_text,
        upsert_cycle_failure_event,
    )
except ModuleNotFoundError:
    from core.cycle_failure_events import (
        classify_failure_cause,
        tail_text,
        upsert_cycle_failure_event,
    )

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
    from scripts.api.get_pricing import (
        DETAIL_STATUS_API_ERROR,
        DETAIL_STATUS_EMPTY_RESPONSE,
        DETAIL_STATUS_OK,
        DETAIL_STATUS_SKIPPED_ROTATION,
        run_market_context_lookup_with_offers_detail,
    )
    from scripts.api.spapi_owner import SpApiCallContext, spapi_get, spapi_patch_json
except ModuleNotFoundError:
    from api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing, require_env
    from api.get_listing_item_price import run_own_offer_price_lookup
    from api.get_pricing import (
        DETAIL_STATUS_API_ERROR,
        DETAIL_STATUS_EMPTY_RESPONSE,
        DETAIL_STATUS_OK,
        DETAIL_STATUS_SKIPPED_ROTATION,
        run_market_context_lookup_with_offers_detail,
    )
    from api.spapi_owner import SpApiCallContext, spapi_get, spapi_patch_json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DATA = ROOT / "data"
LOCKS_DIR = OUT / "locks"
H_LIVE_DIR = OUT / "systems" / "H" / "live"
H_CYCLE_CURRENT_RUN_PATH = H_LIVE_DIR / "H_cycle_current_run_id.txt"
H_CYCLE_LAST_PUBLISH_RUN_PATH = H_LIVE_DIR / "H_cycle_last_publish_run_id.txt"
H_CYCLE_LAST_PUBLISH_INFO_PATH = H_LIVE_DIR / "H_cycle_last_publish_info.txt"
H_CYCLE_LAST_TERMINAL_INFO_PATH = H_LIVE_DIR / "H_cycle_last_terminal_info.txt"
LEGACY_H_CYCLE_LAST_TERMINAL_INFO_PATH = OUT / "H_cycle_last_terminal_info.txt"
H_CYCLE_LAST_COMPLETED_RUN_PATH = H_LIVE_DIR / "H_cycle_last_completed_run_id.txt"
H_PUBLISH_GAP_TRACE_PATH = H_LIVE_DIR / "H_publish_gap_trace.txt"
H_PHASE1_INTEL_PROGRESS_LOG_PATH = H_LIVE_DIR / "phase1_intel.progress.log"
PHASE1_LOCK_EVENTS_LOG_PATH = H_LIVE_DIR / "phase1_lock_events.log"
PHASE1_PILOT_TASK_LOG_PATH = H_LIVE_DIR / "phase1_pilot_task.log"
H_RUN_IN_PROGRESS_PATH = H_LIVE_DIR / "H_run_in_progress.txt"
H_LAST_FINALIZED_RUN_ID_PATH = H_LIVE_DIR / "H_last_finalized_run_id.txt"
H_UNFINALIZED_EXIT_PATH = H_LIVE_DIR / "H_unfinalized_exit.json"
H_SNAPSHOT_WORKER_PARENT_HANDOFF_PATH = H_LIVE_DIR / "snapshot_worker_parent_handoff.json"
H_ATEXIT_TRACE_PATH = H_LIVE_DIR / "H_ATEXIT_TRACE.log"
H_PARENT_TRACE_PATH = H_LIVE_DIR / "H_parent_trace.log"
H_PARENT_FAULT_TRACE_PATH = H_LIVE_DIR / "H_parent_fault_trace.log"
H_HOME_TIME_MODE_LOG_PATH = H_LIVE_DIR / "H_home_time_mode.log"
H_PHASE1_INTEL_WAIT_STATE_GLOB = "phase1_intel_wait.*.json"
H_BATCH_STATE_PATH = H_LIVE_DIR / "H_batch_state.json"
H_BATCH_STAGE_DIR_PATH = H_LIVE_DIR / "H_batch_stage_dir.txt"
H_RUNTIME_STATUS_PATH = H_LIVE_DIR / "H_runtime_status.json"
H_RUNTIME_STATUS_TEXT_PATH = H_LIVE_DIR / "H_runtime_status.txt"
H_RUN_STATE_PATH = H_LIVE_DIR / "H_run_state.json"
H_WORKER_LIFECYCLE_PATH = H_LIVE_DIR / "H_worker_lifecycle.json"
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
H110_SKU_DECISION_LOG_PATH = H_LIVE_DIR / "h110_sku_decision_log.csv"
H_FLOOR_TRACE_PATH = OUT / "h_floor_truth_trace.csv"
PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH = OUT / "phase1_runtime_floor_snapshot_latest.csv"
H_SELLER_DETAIL_PROOF_PATH = H_LIVE_DIR / "h_seller_detail_resolution_proof_latest.csv"
H_SELLER_DETAIL_RECOVERY_HISTORY_PATH = H_LIVE_DIR / "h_seller_detail_recovery_history_latest.csv"
H_SELLER_DETAIL_MEASUREMENT_SUMMARY_PATH = H_LIVE_DIR / "h_seller_detail_measurement_summary_latest.csv"
H_SELLER_DETAIL_MEASUREMENT_ALERTS_PATH = H_LIVE_DIR / "h_seller_detail_measurement_alerts_latest.csv"
H_SELLER_DETAIL_OPERATOR_REVIEW_PATH = H_LIVE_DIR / "h_seller_detail_operator_review_latest.csv"
H_SELLER_DETAIL_HISTORY_DIR = H_LIVE_DIR / "history"
PHASE1_FLOOR_TABLE_PATH = OUT / "phase1_floor_table_latest.csv"
SKU_CEILING_EVENTS_PATH = DATA / "sku_ceiling_events.csv"
LISTING_OFFER_SELLER_HISTORY_PATH = OUT / "listing_offer_seller_observation_history.csv"
LISTING_OFFER_HISTORY_PATH = OUT / "listing_offer_history.csv"
SQL_TABLE_LISTING_OFFER_HISTORY = "h_listing_offer_history"
SQL_TABLE_LISTING_OFFER_SNAPSHOT_LATEST = "h_listing_offer_snapshot_latest"
SQL_TABLE_LISTING_OFFER_SELLER_SNAPSHOT_LATEST = "h_listing_offer_seller_snapshot_latest"
SQL_TABLE_PHASE1_RUNTIME_FLOOR_SNAPSHOT_LATEST = "h_phase1_runtime_floor_snapshot_latest"
H_ITEM_OFFERS_RETRY_QUEUE_PATH = H_LIVE_DIR / "h_item_offers_retry_queue.csv"
H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS = [
    "marketplace",
    "asin",
    "sample_sku",
    "first_missed_at_utc",
    "last_attempt_at_utc",
    "last_success_at_utc",
    "last_status",
    "miss_reason",
    "retry_count",
    "active_flag",
    "first_missing_utc",
    "last_attempt_utc",
    "last_success_utc",
    "attempt_count",
    "rotation_skip_count",
    "empty_response_count",
    "api_error_count",
    "detail_status_current",
    "detail_resolution_status",
    "priority_band",
    "force_attempt_next_run_flag",
    "exhausted_flag",
    "operator_reason",
]
DETAIL_RESOLUTION_PENDING_RETRY = "PENDING_RETRY"
DETAIL_RESOLUTION_RECOVERED = "RECOVERED"
DETAIL_RESOLUTION_AMAZON_EMPTY_CONFIRMED = "AMAZON_EMPTY_CONFIRMED"
DETAIL_RESOLUTION_API_ERROR_CONFIRMED = "API_ERROR_CONFIRMED"
DETAIL_RESOLUTION_RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
DETAIL_PRIORITY_HIGH = "HIGH"
DETAIL_PRIORITY_NORMAL = "NORMAL"
DETAIL_CLASS_PENDING_RETRY = "PENDING_RETRY"
DETAIL_CLASS_RECOVERED = "RECOVERED"
DETAIL_CLASS_LIKELY_AMAZON_MISSING = "LIKELY_AMAZON_MISSING"
DETAIL_CLASS_LIKELY_LOCAL_SELECTION_DELAY = "LIKELY_LOCAL_SELECTION_DELAY"
DETAIL_CLASS_RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
DETAIL_CLASS_NOT_APPLICABLE = "NOT_APPLICABLE"
DETAIL_REVIEW_BUCKET_LIKELY_AMAZON_UPSTREAM = "LIKELY_AMAZON_UPSTREAM"
DETAIL_REVIEW_BUCKET_LIKELY_LOCAL_SELECTION_CADENCE = "LIKELY_LOCAL_SELECTION_CADENCE"
DETAIL_REVIEW_BUCKET_RETRY_EXHAUSTED_OPERATOR_REVIEW = "RETRY_EXHAUSTED_OPERATOR_REVIEW"
DETAIL_REVIEW_BUCKET_GENUINE_PRICING_OR_SUPPRESSION_BLOCKER = "GENUINE_PRICING_OR_SUPPRESSION_BLOCKER"
SELLER_SNAPSHOT_DEDUP_REPORT_DIR = OUT / "cycle_alerts"
INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
INVENTORY_HISTORY_PATH = OUT / "inventory_history.csv"
INBOUND_HISTORY_PATH = OUT / "inbound_history.csv"
REFUND_ADJUSTMENT_HISTORY_PATH = OUT / "refund_adjustment_history.csv"
KILL_SWITCH_PATH = LOCKS_DIR / "h_pricing_cycle.kill"
SELLER_PROFILE_PATH = OUT / "h_seller_profiles.csv"
SELLER_SOI_PATH = OUT / "h_seller_of_interest.csv"
SQL_TABLE_SELLER_PROFILES = "h_seller_profiles"
SQL_TABLE_SELLER_SOI = "h_seller_of_interest"
SELLER_DELTA_PATH = OUT / "h_seller_delta_learning.csv"
SNAPSHOT_REFRESH_SCRIPT = resolve_script_path(ROOT / "scripts", "H001_capture_offer_snapshot.py")
HOME_TIME_ARTIFACT_RETENTION_SCRIPT = resolve_script_path(ROOT / "scripts", "tools/home_time_artifact_retention.py")

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
PHASE1_PILOT_PROGRESS_GRACE_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_PROGRESS_GRACE_SECONDS", "300") or "300"),
    0.0,
)
PHASE1_PILOT_MAX_PROGRESS_GRACE_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_MAX_PROGRESS_GRACE_SECONDS", "2700") or "2700"),
    0.0,
)
PHASE1_PILOT_POST_EXIT_HANDOFF_WAIT_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_POST_EXIT_HANDOFF_WAIT_SECONDS", "240") or "240"),
    0.0,
)
PHASE1_PILOT_COMPLETION_RECHECK_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_COMPLETION_RECHECK_SECONDS", "8") or "8"),
    0.0,
)
PHASE1_PILOT_COMPLETION_RECHECK_INTERVAL_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_COMPLETION_RECHECK_INTERVAL_SECONDS", "0.5") or "0.5"),
    0.1,
)
PHASE1_PILOT_CYCLE_RC_SETTLE_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_CYCLE_RC_SETTLE_SECONDS", "8") or "8"),
    0.0,
)
PHASE1_PILOT_CYCLE_RC_SETTLE_INTERVAL_SECONDS = max(
    float(os.environ.get("H_PHASE1_PILOT_CYCLE_RC_SETTLE_INTERVAL_SECONDS", "0.25") or "0.25"),
    0.1,
)
H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS", "240") or "240"),
    60.0,
)
H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS", "240") or "240"),
    60.0,
)
H_ITEM_OFFERS_OUTPUT_VISIBILITY_WAIT_SECONDS = max(
    float(os.environ.get("H_ITEM_OFFERS_OUTPUT_VISIBILITY_WAIT_SECONDS", "45") or "45"),
    5.0,
)
H_ITEM_OFFERS_LOOKUP_RC0_RECOVERY_RETRIES = max(
    int(float(os.environ.get("H_ITEM_OFFERS_LOOKUP_RC0_RECOVERY_RETRIES", "1") or "1")),
    0,
)
H_ITEM_OFFERS_LOOKUP_RC0_INLINE_FALLBACK_ENABLED = is_truthy(
    os.environ.get("H_ITEM_OFFERS_LOOKUP_RC0_INLINE_FALLBACK_ENABLED", "1")
)
_H_SNAPSHOT_REFRESH_ONE_CYCLE_TIMEOUT_DEFAULT_SECONDS = int(
    (
        H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS * float(H_ITEM_OFFERS_LOOKUP_RC0_RECOVERY_RETRIES + 1)
    )
    + H_ITEM_OFFERS_OUTPUT_VISIBILITY_WAIT_SECONDS
    + 120.0
)
H_SNAPSHOT_REFRESH_ONE_CYCLE_TIMEOUT_SECONDS = max(
    float(
        os.environ.get(
            "H_SNAPSHOT_REFRESH_ONE_CYCLE_TIMEOUT_SECONDS",
            str(_H_SNAPSHOT_REFRESH_ONE_CYCLE_TIMEOUT_DEFAULT_SECONDS),
        )
        or str(_H_SNAPSHOT_REFRESH_ONE_CYCLE_TIMEOUT_DEFAULT_SECONDS)
    ),
    H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS,
)
H_SNAPSHOT_WORKER_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_SNAPSHOT_WORKER_TIMEOUT_SECONDS", str(int(H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS + 120))) or str(int(H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS + 120))),
    60.0,
)
H_SNAPSHOT_WORKER_CONTRACT_WAIT_ATTEMPTS = max(
    int(float(os.environ.get("H_SNAPSHOT_WORKER_CONTRACT_WAIT_ATTEMPTS", "20") or "20")),
    1,
)
H_SNAPSHOT_WORKER_CONTRACT_RECOVERY_RUNS = max(
    int(float(os.environ.get("H_SNAPSHOT_WORKER_CONTRACT_RECOVERY_RUNS", "2") or "2")),
    1,
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
PHASE1_OBSERVATION_STATUS_PUBLISH_TIMEOUT_SECONDS = max(
    float(
        os.environ.get(
            "H_PHASE1_OBSERVATION_STATUS_PUBLISH_TIMEOUT_SECONDS",
            os.environ.get("H_PHASE1_OBSERVATION_PUBLISH_TIMEOUT_SECONDS", "900"),
        )
        or "900"
    ),
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
PHASE1_OBSERVATION_STATUS_PUBLISH_ENABLED = os.environ.get("H_PHASE1_OBSERVATION_STATUS_PUBLISH_ENABLED", "1").strip() == "1"
PHASE1_OBSERVATION_STATUS_PUBLISH_ON_START = os.environ.get("H_PHASE1_OBSERVATION_STATUS_PUBLISH_ON_START", "1").strip() == "1"
PHASE1_OBSERVATION_STATUS_PUBLISH_ON_ERROR = os.environ.get("H_PHASE1_OBSERVATION_STATUS_PUBLISH_ON_ERROR", "1").strip() == "1"
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
H_PRIMARY_CHECKLIST_PATH = flow_gate_checklist_path("H")
H_STRATEGY_OUTCOME_DAILY_PATH = OUT / "h_strategy_outcome_daily.csv"
H_ALERT_STATE_PATH = OUT / "system_health_alert_state_H.csv"
H_ALERT_STATE_GLOBAL_PATH = OUT / "system_health_alert_state.csv"
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
H_WRITE_LEGACY_LOGS = os.environ.get("H_WRITE_LEGACY_LOGS", "0").strip() == "1"
H_LOG_ROTATE_MAX_BYTES = max(int(float(os.environ.get("H_LOG_ROTATE_MAX_MB", "50") or "50") * 1024 * 1024), 1024 * 1024)
H_LOG_ROTATE_MAX_FILES = max(int(float(os.environ.get("H_LOG_ROTATE_MAX_FILES", "5") or "5")), 2)
H_CYCLE_LOG_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_CYCLE_LOG_FAMILY_MAX_MB", "120") or "120") * 1024 * 1024),
    5 * 1024 * 1024,
)
H_PRICING_LOG_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_PRICING_LOG_FAMILY_MAX_MB", "120") or "120") * 1024 * 1024),
    5 * 1024 * 1024,
)
H_PROGRESS_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_PROGRESS_ROTATE_MAX_MB", "20") or "20") * 1024 * 1024),
    512 * 1024,
)
H_PROGRESS_ROTATE_MAX_FILES = max(int(float(os.environ.get("H_PROGRESS_ROTATE_MAX_FILES", "3") or "3")), 2)
H_PHASE1_PROGRESS_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_PHASE1_PROGRESS_ROTATE_MAX_MB", "6") or "6") * 1024 * 1024),
    512 * 1024,
)
H_PHASE1_PROGRESS_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H_PHASE1_PROGRESS_ROTATE_MAX_FILES", "3") or "3")),
    2,
)
H_PHASE1_PROGRESS_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_PHASE1_PROGRESS_FAMILY_MAX_MB", "16") or "16") * 1024 * 1024),
    1024 * 1024,
)
H_PARENT_TRACE_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_PARENT_TRACE_ROTATE_MAX_MB", "4") or "4") * 1024 * 1024),
    512 * 1024,
)
H_PARENT_TRACE_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H_PARENT_TRACE_ROTATE_MAX_FILES", "3") or "3")),
    2,
)
H_PARENT_TRACE_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_PARENT_TRACE_FAMILY_MAX_MB", "12") or "12") * 1024 * 1024),
    1024 * 1024,
)
H_HOME_TIME_MODE_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_HOME_TIME_MODE_ROTATE_MAX_MB", "4") or "4") * 1024 * 1024),
    512 * 1024,
)
H_HOME_TIME_MODE_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H_HOME_TIME_MODE_ROTATE_MAX_FILES", "3") or "3")),
    2,
)
H_HOME_TIME_MODE_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_HOME_TIME_MODE_FAMILY_MAX_MB", "12") or "12") * 1024 * 1024),
    1024 * 1024,
)
PHASE1_LOCK_EVENTS_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_PHASE1_LOCK_EVENTS_ROTATE_MAX_MB", "24") or "24") * 1024 * 1024),
    512 * 1024,
)
PHASE1_LOCK_EVENTS_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H_PHASE1_LOCK_EVENTS_ROTATE_MAX_FILES", "3") or "3")),
    2,
)
PHASE1_LOCK_EVENTS_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_PHASE1_LOCK_EVENTS_FAMILY_MAX_MB", "64") or "64") * 1024 * 1024),
    1024 * 1024,
)
PHASE1_PILOT_TASK_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_PHASE1_PILOT_TASK_ROTATE_MAX_MB", "24") or "24") * 1024 * 1024),
    512 * 1024,
)
PHASE1_PILOT_TASK_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H_PHASE1_PILOT_TASK_ROTATE_MAX_FILES", "3") or "3")),
    2,
)
PHASE1_PILOT_TASK_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_PHASE1_PILOT_TASK_FAMILY_MAX_MB", "48") or "48") * 1024 * 1024),
    1024 * 1024,
)
H110_LIFECYCLE_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H110_LIFECYCLE_ROTATE_MAX_MB", "12") or "12") * 1024 * 1024),
    512 * 1024,
)
H110_LIFECYCLE_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H110_LIFECYCLE_ROTATE_MAX_FILES", "3") or "3")),
    2,
)
H110_LIFECYCLE_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H110_LIFECYCLE_FAMILY_MAX_MB", "24") or "24") * 1024 * 1024),
    1024 * 1024,
)
H110_DECISION_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H110_DECISION_ROTATE_MAX_MB", "8") or "8") * 1024 * 1024),
    512 * 1024,
)
H110_DECISION_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H110_DECISION_ROTATE_MAX_FILES", "3") or "3")),
    2,
)
H110_DECISION_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H110_DECISION_FAMILY_MAX_MB", "16") or "16") * 1024 * 1024),
    1024 * 1024,
)
H_LOG_DEDUP_INTERVAL_SECONDS = max(float(os.environ.get("H_LOG_DEDUP_INTERVAL_SECONDS", "1.5") or "1.5"), 0.0)
H_PROGRESS_MIN_INTERVAL_SECONDS = max(
    float(os.environ.get("H_PHASE1_PROGRESS_MIN_INTERVAL_SECONDS", "3.0") or "3.0"),
    0.0,
)
H_PARENT_TRACE_MIN_INTERVAL_SECONDS = max(
    float(os.environ.get("H_PARENT_TRACE_MIN_INTERVAL_SECONDS", "5.0") or "5.0"),
    0.0,
)
H_ENABLE_SELF_CLEANING = os.environ.get("H_ENABLE_SELF_CLEANING", "1").strip() == "1"
H_SELF_CLEAN_TMP_TTL_DAYS = max(float(os.environ.get("H_SELF_CLEAN_TMP_TTL_DAYS", "3") or "3"), 0.25)
H_SELF_CLEAN_LOCK_ARCHIVE_TTL_DAYS = max(float(os.environ.get("H_SELF_CLEAN_LOCK_ARCHIVE_TTL_DAYS", "14") or "14"), 1.0)
H_SELF_CLEAN_LOCK_ARCHIVE_MAX_FILES = max(
    int(float(os.environ.get("H_SELF_CLEAN_LOCK_ARCHIVE_MAX_FILES", "200") or "200")),
    20,
)
H_SELF_CLEAN_HOME_TIME_RETENTION_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_SELF_CLEAN_HOME_TIME_RETENTION_TIMEOUT_SECONDS", "20") or "20"),
    5.0,
)
H_HOME_TIME_DIAGNOSTIC_MAX_FILES = max(
    int(float(os.environ.get("H_HOME_TIME_DIAGNOSTIC_MAX_FILES", "80") or "80")),
    1,
)
H_STAGED_RETENTION_MAX_RUN_DIRS = max(
    int(float(os.environ.get("H_STAGED_RETENTION_MAX_RUN_DIRS", "240") or "240")),
    20,
)
H_STAGED_RETENTION_TTL_DAYS = max(
    float(os.environ.get("H_STAGED_RETENTION_TTL_DAYS", "7") or "7"),
    1.0,
)
H_STAGED_RETENTION_MIN_AGE_HOURS = max(
    float(os.environ.get("H_STAGED_RETENTION_MIN_AGE_HOURS", "6") or "6"),
    0.5,
)
H_EMERGENCY_BACKUP_MAX_DIRS = max(
    int(float(os.environ.get("H_EMERGENCY_BACKUP_MAX_DIRS", "1") or "1")),
    1,
)
H_EMERGENCY_BACKUP_TTL_DAYS = max(
    float(os.environ.get("H_EMERGENCY_BACKUP_TTL_DAYS", "60") or "60"),
    1.0,
)
H_EMERGENCY_BACKUP_RECURSION_CONTAIN_ENABLED = (
    os.environ.get("H_EMERGENCY_BACKUP_RECURSION_CONTAIN_ENABLED", "1").strip() == "1"
)
H_LIVE_SNAPSHOTS_RETENTION_TTL_DAYS = max(
    float(os.environ.get("H_LIVE_SNAPSHOTS_RETENTION_TTL_DAYS", "14") or "14"),
    1.0,
)
H_LIVE_SNAPSHOTS_RETENTION_MAX_DIRS = max(
    int(float(os.environ.get("H_LIVE_SNAPSHOTS_RETENTION_MAX_DIRS", "80") or "80")),
    5,
)
H_LIVE_SNAPSHOTS_RETENTION_MIN_AGE_HOURS = max(
    float(os.environ.get("H_LIVE_SNAPSHOTS_RETENTION_MIN_AGE_HOURS", "12") or "12"),
    0.5,
)
H_TMP_PUBLISH_BACKUPS_TTL_DAYS = max(
    float(os.environ.get("H_TMP_PUBLISH_BACKUPS_TTL_DAYS", "2") or "2"),
    0.25,
)
H_TMP_PUBLISH_BACKUPS_MAX_DIRS = max(
    int(float(os.environ.get("H_TMP_PUBLISH_BACKUPS_MAX_DIRS", "40") or "40")),
    5,
)
H_CLEANUP_LEDGER_PATH = H_LIVE_DIR / "H_cleanup_ledger.jsonl"
H_CLEANUP_LEDGER_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_CLEANUP_LEDGER_ROTATE_MAX_MB", "2") or "2") * 1024 * 1024),
    256 * 1024,
)
H_CLEANUP_LEDGER_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H_CLEANUP_LEDGER_ROTATE_MAX_FILES", "4") or "4")),
    2,
)
H_CLEANUP_LEDGER_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_CLEANUP_LEDGER_FAMILY_MAX_MB", "8") or "8") * 1024 * 1024),
    1024 * 1024,
)
H_FLOOR_TRACE_COMPACT_TRIGGER_BYTES = max(
    int(float(os.environ.get("H_FLOOR_TRACE_COMPACT_TRIGGER_MB", "256") or "256") * 1024 * 1024),
    8 * 1024 * 1024,
)
H_FLOOR_TRACE_TARGET_MAX_BYTES = max(
    int(float(os.environ.get("H_FLOOR_TRACE_TARGET_MAX_MB", "192") or "192") * 1024 * 1024),
    8 * 1024 * 1024,
)
H_SKU_TEMP_FLOOR_COMPACT_TRIGGER_BYTES = max(
    int(float(os.environ.get("H_SKU_TEMP_FLOOR_COMPACT_TRIGGER_MB", "128") or "128") * 1024 * 1024),
    8 * 1024 * 1024,
)
H_SKU_TEMP_FLOOR_TARGET_MAX_BYTES = max(
    int(float(os.environ.get("H_SKU_TEMP_FLOOR_TARGET_MAX_MB", "96") or "96") * 1024 * 1024),
    8 * 1024 * 1024,
)
H_API_CALL_LOG_PATH = OUT / "api_call_log.jsonl"
H_API_CALL_LOG_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_API_CALL_LOG_ROTATE_MAX_MB", "48") or "48") * 1024 * 1024),
    1024 * 1024,
)
H_API_CALL_LOG_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H_API_CALL_LOG_ROTATE_MAX_FILES", "4") or "4")),
    2,
)
H_API_CALL_LOG_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_API_CALL_LOG_FAMILY_MAX_MB", "160") or "160") * 1024 * 1024),
    8 * 1024 * 1024,
)
H_LIVE_SNAPSHOTS_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_LIVE_SNAPSHOTS_FAMILY_MAX_MB", "1024") or "1024") * 1024 * 1024),
    16 * 1024 * 1024,
)
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
    "resolve_h_split_gate": ["out/cycle_alerts/checklist_H.csv"],
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
H_WORKER_LIFECYCLE_STATES = (
    "pending",
    "claimed",
    "running",
    "finalizing",
    "succeeded",
    "failed",
    "abandoned",
)
H_WORKER_TERMINAL_STATES = {"succeeded", "failed", "abandoned"}
H_WORKER_LIFECYCLE_STALE_SECONDS = max(float(os.environ.get("H_WORKER_LIFECYCLE_STALE_SECONDS", "120") or "120"), 30.0)
H_WORKER_LIFECYCLE_WRITE_RETRIES = max(int(float(os.environ.get("H_WORKER_LIFECYCLE_WRITE_RETRIES", "3") or "3")), 1)
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
_WORKER_LIFECYCLE_CACHE: dict[str, str] = {}
_RUN_CONTEXT: dict[str, str] = {"run_id": ""}
_LAST_TRACE_CHECKPOINT = ""
_FINALIZER_REACHED_RUN_ID = ""
_FINALIZER_CONTRACT_ENFORCED = True
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
_ACTIVE_OWN_OFFER_BOUNDARY: dict[str, str] = {}
_PARENT_FAULT_TRACE_FH: io.TextIOWrapper | None = None
_LOG_DEDUP_CACHE: dict[str, float] = {}
_PHASE1_PROGRESS_DEDUP_CACHE: dict[str, float] = {}
_PARENT_TRACE_DEDUP_CACHE: dict[str, float] = {}


def _set_run_context(run_id: str) -> str:
    global _CURRENT_H_RUN_ID
    normalized = _norm(run_id)
    if normalized != _norm(_CURRENT_H_RUN_ID):
        _WORKER_LIFECYCLE_CACHE.clear()
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
    _heartbeat_h_worker_lifecycle()
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
        event_norm = _norm(event)
        dedupe_basis: list[str] = [
            _norm(run_id),
            event_norm,
            _norm(fields.get("reason", "")),
            _norm(fields.get("status", "")),
            _norm(fields.get("checkpoint", "")),
            _norm(fields.get("signal_name", "")),
        ]
        dedupe_key = "|".join(dedupe_basis)
        if event_norm not in {"main_enter", "process_exit_main_return", "process_exit_system_exit", "process_exit_unhandled_exception"}:
            if not _dedupe_emit(_PARENT_TRACE_DEDUP_CACHE, dedupe_key, H_PARENT_TRACE_MIN_INTERVAL_SECONDS):
                return
        parts = [
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            f"pid={os.getpid()}",
            f"ppid={os.getppid()}",
            f"run_id={_norm(run_id)}",
            f"event={event_norm}",
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
        _rotate_log_file(
            H_PARENT_TRACE_PATH,
            max_bytes=H_PARENT_TRACE_ROTATE_MAX_BYTES,
            max_files=H_PARENT_TRACE_ROTATE_MAX_FILES,
        )
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


def _run_storage_housekeeping_hook(flow: str, reason: str) -> None:
    if _norm(os.environ.get("SELLERONE_STORAGE_HOUSEKEEPING_HOOK", "1")).lower() in {"0", "false", "off", "disabled"}:
        return
    timeout_raw = os.environ.get("SELLERONE_STORAGE_HOUSEKEEPING_HOOK_TIMEOUT_SECONDS", "600")
    try:
        timeout_seconds = max(float(timeout_raw), 30.0)
    except Exception:
        timeout_seconds = 600.0
    out_dir = ROOT / "out" / "housekeeping"
    out_dir.mkdir(parents=True, exist_ok=True)
    run_token = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    status = {
        "generated_utc": _ts(),
        "flow": flow,
        "reason": reason,
        "mode": "dry_run",
        "status": "not_run",
        "returncode": "",
        "stdout_tail": "",
        "stderr_tail": "",
    }
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "tools" / "log_housekeeping.py"), "--flow", flow],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        status["status"] = "ok" if completed.returncode == 0 else "error"
        status["returncode"] = str(completed.returncode)
        status["stdout_tail"] = "\n".join((completed.stdout or "").splitlines()[-20:])
        status["stderr_tail"] = "\n".join((completed.stderr or "").splitlines()[-20:])
    except Exception as exc:
        status["status"] = "error"
        status["returncode"] = type(exc).__name__
        status["stderr_tail"] = str(exc)
    payload = json.dumps(status, ensure_ascii=True, indent=2) + "\n"
    (out_dir / f"storage_housekeeping_hook.{flow}.{run_token}.json").write_text(payload, encoding="utf-8")
    (out_dir / f"storage_housekeeping_hook.{flow}.latest.json").write_text(payload, encoding="utf-8")


def _norm(value: object) -> str:
    try:
        return str(value or "").strip()
    except BaseException:
        try:
            return repr(value).strip()
        except BaseException:
            return f"<unprintable:{type(value).__name__}>"


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


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _norm(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


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


def _env_int(name: str, default: int, *, min_value: int = 0) -> int:
    raw = os.environ.get(name, "")
    parsed = _to_int(raw)
    if parsed is None:
        parsed = int(default)
    return max(int(parsed), int(min_value))


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


def _read_kv_file_value(path: Path, key: str) -> str:
    key_norm = _norm(key)
    if not key_norm:
        return ""
    try:
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = str(raw_line or "").strip()
                if not line or "=" not in line:
                    continue
                lhs, rhs = line.split("=", 1)
                if _norm(lhs) == key_norm:
                    return _norm(rhs)
    except Exception:
        return ""
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


def _write_last_terminal_marker(
    *,
    run_id: str,
    now_utc: datetime,
    terminal_state: str,
    stage: str,
    publish_status: str,
    failure_code: str = "",
    failure_detail: str = "",
) -> None:
    text = (
        f"run_id={_norm(run_id)}\n"
        f"utc={now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"state={_norm(terminal_state).lower()}\n"
        f"stage={_norm(stage)}\n"
        f"publish_status={_norm(publish_status)}\n"
        f"failure_code={_norm(failure_code)}\n"
        f"failure_detail={_norm(failure_detail)[:500]}\n"
    )
    _atomic_write_text(H_CYCLE_LAST_TERMINAL_INFO_PATH, text)
    with contextlib.suppress(Exception):
        _atomic_write_text(LEGACY_H_CYCLE_LAST_TERMINAL_INFO_PATH, text)


def _classify_h_publish_freshness_with_terminal_fallback(
    now_utc: datetime,
    *,
    warn_after_seconds: float = 30.0 * 60.0,
    fail_after_seconds: float = 90.0 * 60.0,
) -> tuple[str, str]:
    publish_age = _file_age_seconds(H_CYCLE_LAST_PUBLISH_INFO_PATH, now_utc)
    terminal_age = _file_age_seconds(H_CYCLE_LAST_TERMINAL_INFO_PATH, now_utc)
    terminal_state = _read_kv_file_value(H_CYCLE_LAST_TERMINAL_INFO_PATH, "state").lower()
    publish_status = _read_kv_file_value(H_CYCLE_LAST_PUBLISH_INFO_PATH, "status").lower()

    if publish_age is not None:
        if publish_age > fail_after_seconds:
            publish_class = "fail"
        elif publish_age > warn_after_seconds:
            publish_class = "warn"
        else:
            publish_class = "ok"
    else:
        publish_class = "missing"

    publish_note = (
        f"publish_age_s={_fmt(_r2(publish_age)) if publish_age is not None else 'missing'} "
        f"publish_status={publish_status or 'unknown'}"
    )
    terminal_note = (
        f"terminal_age_s={_fmt(_r2(terminal_age)) if terminal_age is not None else 'missing'} "
        f"terminal_state={terminal_state or 'unknown'}"
    )

    if publish_class in {"ok", "warn"}:
        return publish_class, f"{publish_note};{terminal_note};source=publish_marker"

    if terminal_age is None:
        return "fail", f"{publish_note};{terminal_note};source=publish_marker"

    if terminal_age > fail_after_seconds:
        return "fail", f"{publish_note};{terminal_note};source=terminal_marker_stale"
    if terminal_age > warn_after_seconds:
        return "warn", f"{publish_note};{terminal_note};source=terminal_marker_recent"

    # Terminal proof is fresh, so stale publish marker is a warning (not hard fail).
    return "warn", f"{publish_note};{terminal_note};source=terminal_marker_fallback"


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
    if not _finalizer_contract_enforced():
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
    worker_lifecycle = _read_h_worker_lifecycle()
    worker_run_id = _norm(worker_lifecycle.get("run_id", ""))
    worker_state = _norm(worker_lifecycle.get("state", "")).lower()
    if _norm(run_id) and (
        worker_run_id != _norm(run_id)
        or worker_state != "succeeded"
    ):
        _trace_publish_gap(
            run_id,
            "system_exit_zero_promoted_missing_worker_terminal",
            worker_run_id=worker_run_id,
            worker_state=worker_state,
        )
        _log(
            "FATAL system_exit_zero_promoted_missing_worker_terminal "
            f"run_id={run_id} "
            f"worker_run_id={worker_run_id or 'missing'} "
            f"worker_state={worker_state or 'missing'}"
        )
        return 3
    pilot_wait_run_id = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("run_id", ""))
    pilot_wait_status = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("status", "")).lower()
    pilot_marker_status = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("marker_status", "")).lower()
    if (
        _norm(run_id)
        and pilot_wait_run_id == _norm(run_id)
        and (
            pilot_wait_status in {"entered", "active", "abnormal_exit", "exited_normal"}
            or pilot_marker_status in {"", "started"}
        )
    ):
        _record_unresolved_phase1_pilot_parent_exit("zero_exit_before_pilot_terminal_resolution")
        _trace_publish_gap(
            run_id,
            "system_exit_zero_promoted_unresolved_pilot_wait",
            pilot_wait_status=pilot_wait_status or "missing",
            pilot_marker_status=pilot_marker_status or "missing",
            pilot_child_pid=_norm(_ACTIVE_PHASE1_PILOT_WAIT.get("child_pid", "")),
        )
        _log(
            "FATAL system_exit_zero_promoted_unresolved_pilot_wait "
            f"run_id={run_id} "
            f"pilot_wait_status={pilot_wait_status or 'missing'} "
            f"pilot_marker_status={pilot_marker_status or 'missing'} "
            f"pilot_child_pid={_norm(_ACTIVE_PHASE1_PILOT_WAIT.get('child_pid', '')) or 'missing'}"
        )
        return 3
    return safe_rc


def _classify_h_failure_event(
    *,
    failure_code: str = "",
    failure_detail: str = "",
    loop_rc: object = "",
) -> tuple[str, str]:
    detail = tail_text(failure_detail, max_chars=1000)
    code = classify_failure_cause(
        verification_status="",
        rc=loop_rc,
        failure_code=failure_code,
        detail=detail,
    )
    if code == "UNKNOWN_FAILURE" and _norm(failure_code):
        detail = tail_text(f"{failure_code}:{detail}", max_chars=1000)
    return code, detail


def _record_h_failure_event(
    *,
    run_id: str,
    final_state: str,
    cause_code: str,
    cause_detail: str,
    stage: str = "",
    rc: object = "",
    manifest_path: Path | str = "",
    health_path: Path | str = "",
    recovery_action: str = "",
) -> None:
    try:
        upsert_cycle_failure_event(
            {
                "timestamp_utc": utc_now_iso(),
                "cycle": "H",
                "run_id": run_id,
                "final_state": final_state,
                "cause_code": cause_code,
                "cause_detail": cause_detail,
                "step_name": "h_cycle_iteration",
                "stage": stage,
                "rc": str(rc),
                "verification_status": cause_code,
                "manifest_path": str(manifest_path) if manifest_path else "",
                "health_path": str(health_path) if health_path else "",
                "source_path": "scripts/cycles/run_H_pricing_cycle.py",
                "recovery_action": recovery_action,
            }
        )
    except Exception as exc:
        _log(f"cycle_failure_event_write_failed error={type(exc).__name__}:{exc}")


def _finalizer_contract_enforced() -> bool:
    if not _FINALIZER_CONTRACT_ENFORCED:
        return False
    # Worker subprocesses do not own cycle finalization markers.
    return "--snapshot-refresh-worker" not in sys.argv


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


def _write_snapshot_worker_parent_handoff(
    *,
    run_id: str,
    worker_run: int,
    worker_run_limit: int,
    worker_rc: int,
    contract_path: Path,
) -> None:
    payload = {
        "run_id": _norm(run_id),
        "status": "worker_return_observed",
        "worker_run": str(int(worker_run)),
        "worker_run_limit": str(int(worker_run_limit)),
        "worker_rc": str(int(worker_rc)),
        "contract_path": str(contract_path),
        "updated_utc": _ts(),
    }
    _write_json(H_SNAPSHOT_WORKER_PARENT_HANDOFF_PATH, payload)
    _log(
        "snapshot_worker_parent_handoff_write "
        f"run_id={payload['run_id']} "
        f"status={payload['status']} "
        f"worker_run={payload['worker_run']} "
        f"worker_run_limit={payload['worker_run_limit']} "
        f"worker_rc={payload['worker_rc']} "
        f"contract_path={payload['contract_path']}"
    )


def _clear_snapshot_worker_parent_handoff(run_id: str = "", *, reason: str = "") -> None:
    target_run_id = _norm(run_id) or _context_run_id()
    payload = _read_json(H_SNAPSHOT_WORKER_PARENT_HANDOFF_PATH, default={})
    payload_run_id = _norm(payload.get("run_id", "")) if isinstance(payload, dict) else ""
    if target_run_id and payload_run_id and payload_run_id != target_run_id:
        return
    try:
        H_SNAPSHOT_WORKER_PARENT_HANDOFF_PATH.unlink(missing_ok=True)
        _log(
            "snapshot_worker_parent_handoff_cleared "
            f"run_id={target_run_id or payload_run_id} "
            f"reason={_norm(reason) or 'explicit_clear'}"
        )
    except Exception as exc:
        _log(
            "snapshot_worker_parent_handoff_clear_failed "
            f"run_id={target_run_id or payload_run_id} "
            f"reason={_norm(reason) or 'explicit_clear'} "
            f"error={type(exc).__name__}:{exc}"
        )


def _reconcile_snapshot_worker_parent_handoff_on_parent_exit() -> None:
    # Snapshot worker subprocesses can read the shared handoff marker, but they
    # must never perform parent-side reconciliation against run state/locks.
    if "--snapshot-refresh-worker" in sys.argv:
        return
    try:
        payload = _read_json(H_SNAPSHOT_WORKER_PARENT_HANDOFF_PATH, default={})
        if not isinstance(payload, dict):
            return
        run_id = _norm(payload.get("run_id", ""))
        status = _norm(payload.get("status", "")).lower()
        if not run_id or status != "worker_return_observed":
            return
        active_run_id = _norm(_read_first_line(H_RUN_IN_PROGRESS_PATH))
        if active_run_id and active_run_id != run_id:
            return
        worker_rc = _norm(payload.get("worker_rc", ""))
        contract_path = Path(_norm(payload.get("contract_path", ""))) if _norm(payload.get("contract_path", "")) else Path()
        contract_exists = bool(contract_path and contract_path.exists())
        detail = "parent_exit_after_snapshot_worker_before_contract_handoff"
        if contract_exists:
            contract_payload = _read_json(contract_path, default={})
            contract_status = _norm(contract_payload.get("status", "")).lower() if isinstance(contract_payload, dict) else ""
            contract_reason = _norm(contract_payload.get("reason", "")) if isinstance(contract_payload, dict) else ""
            if contract_status == "ok":
                detail = "parent_exit_after_snapshot_worker_success_before_contract_handoff"
            elif contract_status == "failed":
                detail = f"parent_exit_after_snapshot_worker_failed_contract:{contract_reason or 'missing_reason'}"
            else:
                detail = f"parent_exit_after_snapshot_worker_contract_invalid_status:{contract_status or 'missing'}"
        else:
            detail = "parent_exit_after_snapshot_worker_contract_missing"
        _write_h_run_state(
            "failed",
            run_id=run_id,
            stage="snapshot_refresh",
            publish_status="not_started",
            failure_code="SNAPSHOT_WORKER_HANDOFF_PARENT_EXIT",
            failure_detail=(f"{detail}:worker_rc={worker_rc or 'missing'}")[:500],
        )
        _clear_run_in_progress(run_id, reason="snapshot_worker_handoff_parent_exit")
        locks_cleared = 0
        for lock_path in _lock_probe_paths():
            if not lock_path.exists():
                continue
            lock_payload, _ = _read_lock_payload(lock_path)
            if not lock_payload:
                continue
            lock_run_id = _parse_lock_value(lock_payload, "run_id")
            if lock_run_id and lock_run_id != run_id:
                continue
            lock_pid = _parse_lock_pid(lock_payload)
            if lock_pid is not None and lock_pid not in {0, os.getpid()} and _pid_alive(lock_pid):
                continue
            try:
                lock_path.unlink(missing_ok=True)
                locks_cleared += 1
            except Exception:
                continue
        _log(
            "snapshot_worker_parent_handoff_parent_exit_reconciled "
            f"run_id={run_id} "
            f"worker_rc={worker_rc or 'missing'} "
            f"contract_exists={'1' if contract_exists else '0'} "
            f"locks_cleared={locks_cleared} "
            f"detail={detail}"
        )
        _clear_snapshot_worker_parent_handoff(run_id, reason="parent_exit_reconciled")
    except Exception as exc:
        _log(f"snapshot_worker_parent_handoff_parent_exit_reconcile_failed error={type(exc).__name__}:{exc}")

def _read_latest_phase1_pilot_terminal_artifacts(run_id: str) -> dict[str, str]:
    evidence = {
        "marker_status": "",
        "marker_result_ok": "",
        "marker_path": "",
        "result_path": "",
        "result_exists": "0",
        "result_size": "0",
        "result_terminal_status": "",
        "result_terminal_reason": "",
        "success_ok": "0",
    }
    run_norm = _norm(run_id)
    if not run_norm:
        return evidence
    marker_candidates = sorted(
        H_LIVE_DIR.glob(f"phase1_pilot_step.complete.{run_norm}.*.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    for candidate in marker_candidates:
        try:
            marker_raw = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(marker_raw, dict):
            continue
        marker_run_id = _norm(marker_raw.get("run_id", ""))
        if marker_run_id and marker_run_id != run_norm:
            continue
        evidence["marker_path"] = str(candidate)
        evidence["marker_status"] = _norm(marker_raw.get("status", "")).lower()
        evidence["marker_result_ok"] = _norm(marker_raw.get("result_ok", ""))
        break
    result_candidates = sorted(
        H_LIVE_DIR.glob(f"phase1_pilot_step.result.{run_norm}.*.json"),
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    for candidate in result_candidates:
        try:
            if int(candidate.stat().st_size) <= 0:
                continue
        except Exception:
            continue
        evidence["result_path"] = str(candidate)
        evidence["result_exists"] = "1"
        try:
            evidence["result_size"] = str(int(candidate.stat().st_size))
        except Exception:
            evidence["result_size"] = "0"
        try:
            result_raw = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(result_raw, dict):
                evidence["result_terminal_status"] = _norm(result_raw.get("phase1_terminal_status", "")).lower()
                evidence["result_terminal_reason"] = _norm(
                    result_raw.get("phase1_terminal_reason", "")
                ) or _norm(result_raw.get("reason_codes_csv", ""))
        except Exception:
            pass
        break
    if evidence["marker_status"] == "success" and evidence["marker_result_ok"] in {"1", "true"} and evidence["result_exists"] == "1":
        evidence["success_ok"] = "1"
    return evidence


def _runtime_status_child_pid(detail: object) -> int:
    text = _norm(detail)
    if not text:
        return 0
    match = re.search(r"(?:^|\s)child_pid=(\d+)", text)
    if not match:
        return 0
    try:
        pid = int(match.group(1))
        return pid if pid > 0 else 0
    except Exception:
        return 0


def _wrapper_child_wait_handover_active(run_id: str, *, expected_child_pid: int = 0) -> tuple[bool, str]:
    run_norm = _norm(run_id)
    if not run_norm:
        return False, "missing_run_id"
    runtime = _read_json(H_RUNTIME_STATUS_PATH, default={})
    if not isinstance(runtime, dict) or not runtime:
        return False, "runtime_status_missing"
    runtime_run_id = _norm(runtime.get("run_id", ""))
    if runtime_run_id and runtime_run_id != run_norm:
        return False, f"runtime_run_mismatch:{runtime_run_id}"
    mode = _norm(runtime.get("mode", "")).upper()
    stage = _norm(runtime.get("stage", "")).lower()
    if mode != "RUNNING" or stage != "child_wait":
        return False, f"runtime_not_child_wait:{mode or 'missing'}:{stage or 'missing'}"
    wrapper_pid = _to_int(runtime.get("pid", "")) or 0
    if wrapper_pid <= 0 or not _pid_alive(wrapper_pid):
        return False, f"wrapper_pid_dead:{wrapper_pid}"
    child_pid = _runtime_status_child_pid(runtime.get("detail", ""))
    if expected_child_pid > 0 and child_pid != expected_child_pid:
        return False, f"child_pid_mismatch:{child_pid or 0}:{expected_child_pid}"
    return True, f"wrapper_pid={wrapper_pid} child_pid={child_pid or 0}"


def _owner_exit_capture_paths_for_pid(owner_pid: int) -> List[Path]:
    pid = _to_int(owner_pid) or 0
    if pid <= 0:
        return []
    candidates = list(H_LIVE_DIR.glob(f"H_core_parent_exit_capture.{pid}.*.json"))
    candidates.sort(
        key=lambda path: path.stat().st_mtime if path.exists() else 0.0,
        reverse=True,
    )
    return candidates


def _read_owner_exit_capture_payload(path: Path) -> dict:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            raw = path.read_text(encoding=encoding)
        except Exception:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict) and payload:
            return payload
    return {}


def _extract_owner_exit_status_from_capture(payload: dict, owner_pid: int) -> tuple[str, str]:
    try:
        pid_hex = f"0x{int(owner_pid):X}".lower()
    except Exception:
        return "", ""
    correlation = payload.get("correlation", {}) if isinstance(payload, dict) else {}
    for source_name in ("security_4688_4689", "security"):
        source_payload = correlation.get(source_name, {}) if isinstance(correlation, dict) else {}
        events = source_payload.get("events", []) if isinstance(source_payload, dict) else []
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            message = _norm(event.get("message_excerpt", ""))
            message_lower = message.lower()
            if "process has exited" not in message_lower:
                continue
            if pid_hex not in message_lower:
                continue
            status_match = re.search(r"exit status:\s*(0x[0-9a-f]+)", message, re.IGNORECASE)
            status_value = status_match.group(1).lower() if status_match else ""
            return status_value, _norm(event.get("record_id", ""))
    return "", ""


def _classify_stale_owner_exit_evidence(
    run_id: str,
    owner_pid: int,
    *,
    run_state_utc: str = "",
) -> dict[str, str]:
    run_norm = _norm(run_id)
    pid_value = _to_int(owner_pid) or 0
    if not run_norm:
        return {"usable": "0", "reason": "missing_run_id"}
    if pid_value <= 0:
        return {"usable": "0", "reason": "missing_owner_pid"}
    run_state_dt = _to_dt(run_state_utc)
    capture_paths = _owner_exit_capture_paths_for_pid(pid_value)
    if not capture_paths:
        return {"usable": "0", "reason": "missing_owner_exit_capture"}
    for capture_path in capture_paths:
        payload = _read_owner_exit_capture_payload(capture_path)
        if not isinstance(payload, dict) or not payload:
            continue
        observed_start = payload.get("observed", {})
        if not isinstance(observed_start, dict):
            observed_start = {}
        observed_end = payload.get("observed_end", {})
        if not isinstance(observed_end, dict):
            observed_end = {}
        runtime_start = observed_start.get("runtime_status_start", {})
        if not isinstance(runtime_start, dict):
            runtime_start = {}
        runtime_end = observed_end.get("runtime_status_end", {})
        if not isinstance(runtime_end, dict):
            runtime_end = {}
        target_pid = _to_int(payload.get("target_pid", "")) or 0
        if target_pid > 0 and target_pid != pid_value:
            continue
        run_start = (
            _norm(observed_start.get("run_id_current_start", ""))
            or _norm(observed_start.get("run_id_in_progress_start", ""))
            or _norm(runtime_start.get("run_id", ""))
        )
        run_end = (
            _norm(observed_end.get("run_id_current_end", ""))
            or _norm(observed_end.get("run_id_in_progress_end", ""))
            or _norm(runtime_end.get("run_id", ""))
        )
        # Fail closed: stale-owner reconciliation needs explicit same-run binding.
        if not run_end:
            continue
        if run_end and run_end != run_norm:
            continue
        start_binding_mode = "strict"
        if run_start and run_start != run_norm:
            # Guard wrappers can begin owner-exit capture before the core owner
            # advances the current run marker. Accept this only when the same
            # target pid, same run end-marker, and run-state timestamp are all
            # inside one capture window.
            capture_start_dt = _to_dt(observed_start.get("capture_start_utc", ""))
            disappearance_dt = _to_dt(payload.get("liveness", {}).get("disappearance_utc", ""))
            run_current_end = _norm(observed_end.get("run_id_current_end", ""))
            run_in_progress_end = _norm(observed_end.get("run_id_in_progress_end", ""))
            if (
                run_state_dt is None
                or capture_start_dt is None
                or disappearance_dt is None
                or run_current_end != run_norm
                or run_in_progress_end != run_norm
                or disappearance_dt < capture_start_dt
                or run_state_dt < capture_start_dt
                or run_state_dt > disappearance_dt
            ):
                continue
            start_binding_mode = "capture_window_transition"
        authoritative_linkage = payload.get("authoritative_linkage", {})
        if not isinstance(authoritative_linkage, dict):
            authoritative_linkage = {}
        audit_linkage = authoritative_linkage.get("security_process_audit", {})
        if not isinstance(audit_linkage, dict):
            audit_linkage = {}
        attribution_possible = (
            _norm(authoritative_linkage.get("attribution_possible", ""))
            or _norm(audit_linkage.get("attribution_possible", ""))
        )
        if attribution_possible != "1":
            continue
        candidates = audit_linkage.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        matched_candidate: dict[str, object] = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            event_class = _norm(candidate.get("event_class", "")).lower()
            contains_target_pid = _norm(candidate.get("contains_target_pid", ""))
            if event_class == "process_exit" and contains_target_pid in {"1", "true"}:
                matched_candidate = candidate
                break
        if not matched_candidate:
            continue
        exit_status, exit_record_id = _extract_owner_exit_status_from_capture(payload, pid_value)
        return {
            "usable": "1",
            "reason": "owner_exit_capture_matched",
            "capture_path": str(capture_path),
            "run_end": run_end,
            "attribution_level": (
                _norm(authoritative_linkage.get("attribution_level", ""))
                or _norm(audit_linkage.get("attribution_level", ""))
                or "best_effort"
            ),
            "record_id": _norm(matched_candidate.get("record_id", "")) or exit_record_id,
            "exit_status": exit_status,
            "disappearance_utc": _norm(payload.get("liveness", {}).get("disappearance_utc", "")),
            "runtime_end_error": _norm(runtime_end.get("error", "")),
            "start_binding_mode": start_binding_mode,
        }
    return {"usable": "0", "reason": "owner_exit_capture_not_matched_for_run"}


def _reconcile_stale_pilot_started_dead_owner() -> dict[str, str]:
    outcome: dict[str, str] = {
        "blocked": "0",
        "applied": "0",
        "reason": "no_stale_dead_owner",
        "run_id": "",
        "state": "",
    }
    try:
        run_state = _read_json(H_RUN_STATE_PATH, default={})
        if not isinstance(run_state, dict):
            outcome["reason"] = "run_state_missing"
            return outcome
        run_id = _norm(run_state.get("run_id", ""))
        if not run_id:
            outcome["reason"] = "run_id_missing"
            return outcome
        state_name = _norm(run_state.get("state", "")).lower()
        outcome["run_id"] = run_id
        outcome["state"] = state_name
        terminal_states = {"failed", "finalized", "succeeded"}
        if state_name in terminal_states:
            outcome["reason"] = "already_terminal_state"
            return outcome
        recoverable_states = {"pilot_started", "started", "snapshot_done", "collect_done"}
        if state_name not in recoverable_states:
            outcome["reason"] = "state_not_recoverable"
            return outcome
        owner_pid = _to_int(run_state.get("owner_pid", "")) or 0
        if owner_pid <= 0:
            outcome["blocked"] = "1"
            outcome["reason"] = "owner_pid_missing_nonterminal"
            return outcome
        if _h_owner_pid_alive(owner_pid):
            outcome["reason"] = "owner_pid_alive"
            return outcome
        run_in_progress = _read_first_line(H_RUN_IN_PROGRESS_PATH)
        run_in_progress_norm = _norm(run_in_progress)
        current_cycle_run_id = _norm(_read_first_line(H_CYCLE_CURRENT_RUN_PATH))
        if run_in_progress_norm and run_in_progress_norm != run_id:
            outcome["blocked"] = "1"
            outcome["reason"] = "run_in_progress_mismatch"
            return outcome
        run_state_utc = _to_dt(run_state.get("utc", ""))
        run_state_age_seconds: float | None = None
        if run_state_utc is not None:
            try:
                run_state_age_seconds = max((datetime.now(timezone.utc) - run_state_utc).total_seconds(), 0.0)
            except Exception:
                run_state_age_seconds = None
        handover_defer_max_seconds = max(
            float(os.environ.get("H_STALE_HANDOVER_DEFER_MAX_SECONDS", "180") or "180"),
            30.0,
        )
        wrapper_handover_active, wrapper_handover_reason = _wrapper_child_wait_handover_active(
            run_id,
            expected_child_pid=os.getpid(),
        )
        handover_marker_match = (
            run_in_progress_norm == run_id
            or current_cycle_run_id == run_id
        )
        within_handover_defer_window = (
            run_state_age_seconds is not None
            and run_state_age_seconds <= handover_defer_max_seconds
        )
        allow_handover_defer = (
            wrapper_handover_active
            and handover_marker_match
            and within_handover_defer_window
        )
        if allow_handover_defer:
            _log(
                "stale_pilot_started_reconcile_deferred "
                f"run_id={run_id} "
                f"state={state_name} "
                f"owner_pid={owner_pid} "
                f"reason={wrapper_handover_reason} "
                f"run_in_progress={run_in_progress_norm or 'missing'} "
                f"current_cycle_run_id={current_cycle_run_id or 'missing'} "
                f"run_state_age_seconds={_fmt(_r2(run_state_age_seconds)) if run_state_age_seconds is not None else 'missing'} "
                f"defer_max_seconds={_fmt(_r2(handover_defer_max_seconds))} "
                "within_defer_window=1"
            )
            outcome["blocked"] = "1"
            outcome["reason"] = "handover_defer_window_active"
            return outcome
        if wrapper_handover_active and not allow_handover_defer:
            handover_ignore_reason = "marker_mismatch"
            if handover_marker_match and not within_handover_defer_window:
                handover_ignore_reason = "defer_window_expired"
            elif handover_marker_match and run_state_age_seconds is None:
                handover_ignore_reason = "missing_run_state_age"
            _log(
                "stale_pilot_started_reconcile_handover_ignored "
                f"run_id={run_id} "
                f"state={state_name} "
                f"owner_pid={owner_pid} "
                f"reason={wrapper_handover_reason} "
                f"ignore_reason={handover_ignore_reason} "
                f"run_in_progress={run_in_progress_norm or 'missing'} "
                f"current_cycle_run_id={current_cycle_run_id or 'missing'} "
                f"run_state_age_seconds={_fmt(_r2(run_state_age_seconds)) if run_state_age_seconds is not None else 'missing'} "
                f"defer_max_seconds={_fmt(_r2(handover_defer_max_seconds))}"
            )

        worker_lifecycle = _read_h_worker_lifecycle()
        worker_run_id = _norm(worker_lifecycle.get("run_id", ""))
        worker_state = _norm(worker_lifecycle.get("state", "")).lower()
        worker_heartbeat_utc = _to_dt(worker_lifecycle.get("heartbeat_utc", ""))
        worker_heartbeat_age_seconds: float | None = None
        if worker_heartbeat_utc is not None:
            try:
                worker_heartbeat_age_seconds = max(
                    (datetime.now(timezone.utc) - worker_heartbeat_utc).total_seconds(),
                    0.0,
                )
            except Exception:
                worker_heartbeat_age_seconds = None
        worker_stale_after_seconds = max(float(H_WORKER_LIFECYCLE_STALE_SECONDS), 30.0)
        worker_stale_for_run = (
            worker_run_id == run_id
            and worker_state in {"pending", "claimed", "running", "finalizing"}
            and worker_heartbeat_age_seconds is not None
            and worker_heartbeat_age_seconds > worker_stale_after_seconds
        )
        if worker_stale_for_run and not _h_owner_pid_alive(owner_pid):
            identity = _windows_process_identity(owner_pid)
            identity_name = _norm(identity.get("name", "")) or "missing"
            identity_command = _norm(identity.get("command_line", "")) or "missing"
            failure_code = "STALE_OWNER_IDENTITY_MISMATCH"
            failure_detail = (
                "startup_reconcile_owner_identity_mismatch "
                f"owner_pid={owner_pid} "
                f"identity_name={identity_name} "
                f"worker_state={worker_state} "
                f"worker_heartbeat_age_seconds={_fmt(_r2(worker_heartbeat_age_seconds))} "
                f"stale_after_seconds={_fmt(_r2(worker_stale_after_seconds))}"
            )[:500]
            _log(
                "stale_pilot_started_hard_proof_confirmed "
                f"run_id={run_id} "
                f"owner_pid={owner_pid} "
                f"state={state_name} "
                "evidence_type=owner_pid_identity_mismatch "
                f"identity_name={identity_name} "
                f"identity_command={identity_command[:180]} "
                f"worker_state={worker_state} "
                f"worker_heartbeat_age_seconds={_fmt(_r2(worker_heartbeat_age_seconds))} "
                "action=core_terminalize_stale_run"
            )
            _write_h_run_state(
                "failed",
                run_id=run_id,
                stage="startup_reconcile",
                publish_status="not_started",
                failure_code=failure_code,
                failure_detail=failure_detail,
            )
            confirmed_state = _read_json(H_RUN_STATE_PATH, default={})
            confirmed_run_id = _norm(confirmed_state.get("run_id", "")) if isinstance(confirmed_state, dict) else ""
            confirmed_status = _norm(confirmed_state.get("state", "")).lower() if isinstance(confirmed_state, dict) else ""
            if confirmed_run_id != run_id or confirmed_status != "failed":
                _log(
                    "FATAL stale_pilot_started_terminalize_write_unconfirmed "
                    f"run_id={run_id} "
                    "expected_state=failed "
                    f"confirmed_run_id={confirmed_run_id or 'missing'} "
                    f"confirmed_state={confirmed_status or 'missing'} "
                    f"failure_code={failure_code}"
                )
                outcome["blocked"] = "1"
                outcome["reason"] = "terminal_write_not_confirmed"
                outcome["failure_code"] = failure_code
                return outcome
            worker_written = _transition_h_worker_lifecycle(
                run_id,
                "failed",
                reason_code=failure_code,
                reason_detail=failure_detail,
                terminal_outcome="failed",
            )
            batch_written = "1"
            batch_error = ""
            try:
                _transition_h_batch_state(run_id, "failed", reason=failure_code, source="startup_reconcile")
            except Exception as exc:
                batch_written = "0"
                batch_error = f"{type(exc).__name__}:{exc}"
                _log(
                    "stale_pilot_started_batch_transition_failed "
                    f"run_id={run_id} "
                    f"error={batch_error}"
                )
            _clear_run_in_progress(run_id, reason="startup_stale_owner_identity_mismatch")
            _log(
                "stale_pilot_started_terminalized_by_core "
                f"run_id={run_id} "
                f"failure_code={failure_code} "
                f"worker_written={'1' if worker_written else '0'} "
                f"batch_written={batch_written} "
                f"batch_error={batch_error or 'none'} "
                "action=continue_new_run"
            )
            outcome["applied"] = "1"
            outcome["reason"] = "stale_owner_identity_terminalized_by_core"
            outcome["failure_code"] = failure_code
            outcome["worker_written"] = "1" if worker_written else "0"
            outcome["batch_written"] = batch_written
            return outcome

        terminal_evidence = _read_latest_phase1_pilot_terminal_artifacts(run_id)
        owner_exit_evidence = _classify_stale_owner_exit_evidence(
            run_id,
            owner_pid,
            run_state_utc=_norm(run_state.get("utc", "")),
        )
        if owner_exit_evidence.get("usable", "0") == "1" and state_name not in {"failed", "finalized", "succeeded"}:
            evidence_reason = _norm(owner_exit_evidence.get("reason", "")) or "missing"
            capture_path = _norm(owner_exit_evidence.get("capture_path", "")) or "missing"
            record_id = _norm(owner_exit_evidence.get("record_id", "")) or "missing"
            exit_status = _norm(owner_exit_evidence.get("exit_status", "")) or "missing"
            runtime_end_error = _norm(owner_exit_evidence.get("runtime_end_error", "")) or "missing"
            failure_code = "STALE_OWNER_EXIT_HARD_PROOF"
            failure_detail = (
                "startup_reconcile_owner_exit_hard_proof "
                f"evidence_reason={evidence_reason} "
                f"capture_path={capture_path} "
                f"record_id={record_id} "
                f"exit_status={exit_status} "
                f"runtime_end_error={runtime_end_error}"
            )[:500]
            outcome["owner_exit_evidence"] = evidence_reason
            _log(
                "stale_pilot_started_hard_proof_confirmed "
                f"run_id={run_id} "
                f"owner_pid={owner_pid} "
                f"state={state_name} "
                "evidence_type=owner_exit_capture "
                f"capture_path={capture_path} "
                f"record_id={record_id} "
                f"exit_status={exit_status} "
                f"runtime_end_error={runtime_end_error} "
                "action=core_terminalize_stale_run"
            )
            _write_h_run_state(
                "failed",
                run_id=run_id,
                stage="startup_reconcile",
                publish_status="not_started",
                failure_code=failure_code,
                failure_detail=failure_detail,
            )
            confirmed_state = _read_json(H_RUN_STATE_PATH, default={})
            confirmed_run_id = _norm(confirmed_state.get("run_id", "")) if isinstance(confirmed_state, dict) else ""
            confirmed_status = _norm(confirmed_state.get("state", "")).lower() if isinstance(confirmed_state, dict) else ""
            if confirmed_run_id != run_id or confirmed_status != "failed":
                _log(
                    "FATAL stale_pilot_started_terminalize_write_unconfirmed "
                    f"run_id={run_id} "
                    f"expected_state=failed "
                    f"confirmed_run_id={confirmed_run_id or 'missing'} "
                    f"confirmed_state={confirmed_status or 'missing'} "
                    f"failure_code={failure_code}"
                )
                outcome["blocked"] = "1"
                outcome["reason"] = "terminal_write_not_confirmed"
                outcome["failure_code"] = failure_code
                return outcome
            worker_written = _transition_h_worker_lifecycle(
                run_id,
                "failed",
                reason_code=failure_code,
                reason_detail=failure_detail,
                terminal_outcome="failed",
            )
            batch_written = "1"
            batch_error = ""
            try:
                _transition_h_batch_state(run_id, "failed", reason=failure_code, source="startup_reconcile")
            except Exception as exc:
                batch_written = "0"
                batch_error = f"{type(exc).__name__}:{exc}"
                _log(
                    "stale_pilot_started_batch_transition_failed "
                    f"run_id={run_id} "
                    f"error={batch_error}"
                )
            _clear_run_in_progress(run_id, reason="startup_stale_owner_exit_hard_proof")
            _log(
                "stale_pilot_started_terminalized_by_core "
                f"run_id={run_id} "
                f"failure_code={failure_code} "
                f"worker_written={'1' if worker_written else '0'} "
                f"batch_written={batch_written} "
                f"batch_error={batch_error or 'none'} "
                "action=continue_new_run"
            )
            outcome["applied"] = "1"
            outcome["reason"] = "stale_owner_hard_proof_terminalized_by_core"
            outcome["failure_code"] = failure_code
            outcome["worker_written"] = "1" if worker_written else "0"
            outcome["batch_written"] = batch_written
            return outcome

        pilot_marker_status = _norm(terminal_evidence.get("marker_status", "")).lower()
        pilot_result_exists = _norm(terminal_evidence.get("result_exists", "0")).lower() in {"1", "true"}
        if pilot_marker_status == "failed" and pilot_result_exists and state_name not in {"failed", "finalized", "succeeded"}:
            marker_path = _norm(terminal_evidence.get("marker_path", "")) or "missing"
            result_path = _norm(terminal_evidence.get("result_path", "")) or "missing"
            terminal_reason = _norm(terminal_evidence.get("result_terminal_reason", "")) or "missing"
            failure_code = "STALE_PILOT_TERMINAL_FAILED_HARD_PROOF"
            failure_detail = (
                "startup_reconcile_pilot_terminal_failed_hard_proof "
                f"marker_path={marker_path} "
                f"result_path={result_path} "
                f"terminal_reason={terminal_reason}"
            )[:500]
            outcome["owner_exit_evidence"] = _norm(owner_exit_evidence.get("reason", "")) or "missing"
            _log(
                "stale_pilot_started_hard_proof_confirmed "
                f"run_id={run_id} "
                f"owner_pid={owner_pid} "
                f"state={state_name} "
                "evidence_type=pilot_terminal_failed_marker "
                f"marker_path={marker_path} "
                f"result_path={result_path} "
                f"terminal_reason={terminal_reason} "
                "action=core_terminalize_stale_run"
            )
            _write_h_run_state(
                "failed",
                run_id=run_id,
                stage="startup_reconcile",
                publish_status="not_started",
                failure_code=failure_code,
                failure_detail=failure_detail,
            )
            confirmed_state = _read_json(H_RUN_STATE_PATH, default={})
            confirmed_run_id = _norm(confirmed_state.get("run_id", "")) if isinstance(confirmed_state, dict) else ""
            confirmed_status = _norm(confirmed_state.get("state", "")).lower() if isinstance(confirmed_state, dict) else ""
            if confirmed_run_id != run_id or confirmed_status != "failed":
                _log(
                    "FATAL stale_pilot_started_terminalize_write_unconfirmed "
                    f"run_id={run_id} "
                    f"expected_state=failed "
                    f"confirmed_run_id={confirmed_run_id or 'missing'} "
                    f"confirmed_state={confirmed_status or 'missing'} "
                    f"failure_code={failure_code}"
                )
                outcome["blocked"] = "1"
                outcome["reason"] = "terminal_write_not_confirmed"
                outcome["failure_code"] = failure_code
                return outcome
            worker_written = _transition_h_worker_lifecycle(
                run_id,
                "failed",
                reason_code=failure_code,
                reason_detail=failure_detail,
                terminal_outcome="failed",
            )
            batch_written = "1"
            batch_error = ""
            try:
                _transition_h_batch_state(run_id, "failed", reason=failure_code, source="startup_reconcile")
            except Exception as exc:
                batch_written = "0"
                batch_error = f"{type(exc).__name__}:{exc}"
                _log(
                    "stale_pilot_started_batch_transition_failed "
                    f"run_id={run_id} "
                    f"error={batch_error}"
                )
            _clear_run_in_progress(run_id, reason="startup_stale_pilot_terminal_hard_proof")
            _log(
                "stale_pilot_started_terminalized_by_core "
                f"run_id={run_id} "
                f"failure_code={failure_code} "
                f"worker_written={'1' if worker_written else '0'} "
                f"batch_written={batch_written} "
                f"batch_error={batch_error or 'none'} "
                "action=continue_new_run"
            )
            outcome["applied"] = "1"
            outcome["reason"] = "stale_pilot_hard_proof_terminalized_by_core"
            outcome["failure_code"] = failure_code
            outcome["worker_written"] = "1" if worker_written else "0"
            outcome["batch_written"] = batch_written
            return outcome

        # No hard proof for a dead owner on a non-terminal state: block startup.
        _log(
            "stale_pilot_started_observed "
            f"run_id={run_id} "
            f"owner_pid={owner_pid} "
            f"state={state_name} "
            f"run_in_progress={run_in_progress_norm or 'missing'} "
            f"current_cycle_run_id={current_cycle_run_id or 'missing'} "
            f"run_state_age_seconds={_fmt(_r2(run_state_age_seconds)) if run_state_age_seconds is not None else 'missing'} "
            f"terminal_success_ok={_norm(terminal_evidence.get('success_ok', '0')) or '0'} "
            f"terminal_marker_status={_norm(terminal_evidence.get('marker_status', '')) or 'missing'} "
            f"terminal_result_size={_norm(terminal_evidence.get('result_size', '0')) or '0'} "
            f"owner_exit_evidence={_norm(owner_exit_evidence.get('reason', '')) or 'missing'} "
            "action=fail_closed_block_startup_no_hard_proof"
        )
        outcome["blocked"] = "1"
        outcome["reason"] = "stale_owner_nonterminal_without_hard_proof"
        outcome["owner_exit_evidence"] = _norm(owner_exit_evidence.get("reason", "")) or "missing"
        return outcome
    except Exception as exc:
        _log(f"stale_pilot_started_reconcile_failed error={type(exc).__name__}:{exc}")
        return {
            "blocked": "1",
            "reason": "reconcile_exception",
            "error": f"{type(exc).__name__}:{exc}",
        }


def _startup_nonterminal_truth_guard() -> dict[str, str]:
    outcome: dict[str, str] = {
        "blocked": "0",
        "reason": "clear",
        "run_id": "",
        "state": "",
        "owner_pid": "",
        "owner_alive": "0",
        "run_in_progress": "",
        "current_cycle_run_id": "",
        "state_utc": "",
    }
    try:
        run_state = _read_json(H_RUN_STATE_PATH, default={})
        if not isinstance(run_state, dict):
            outcome["reason"] = "run_state_missing"
            return outcome
        run_id = _norm(run_state.get("run_id", ""))
        state_name = _norm(run_state.get("state", "")).lower()
        outcome["run_id"] = run_id
        outcome["state"] = state_name
        outcome["state_utc"] = _norm(run_state.get("utc", ""))
        owner_pid = _to_int(run_state.get("owner_pid", "")) or 0
        outcome["owner_pid"] = str(owner_pid) if owner_pid > 0 else ""
        terminal_states = {"failed", "finalized", "succeeded", "success"}
        if not run_id or state_name in {"", "none"}:
            outcome["reason"] = "run_state_incomplete"
            return outcome
        if state_name in terminal_states:
            outcome["reason"] = "terminal_state"
            return outcome
        owner_alive = owner_pid > 0 and _h_owner_pid_alive(owner_pid)
        outcome["owner_alive"] = "1" if owner_alive else "0"
        run_in_progress = _norm(_read_first_line(H_RUN_IN_PROGRESS_PATH))
        current_cycle_run_id = _norm(_read_first_line(H_CYCLE_CURRENT_RUN_PATH))
        outcome["run_in_progress"] = run_in_progress
        outcome["current_cycle_run_id"] = current_cycle_run_id
        outcome["blocked"] = "1"
        if owner_alive:
            outcome["reason"] = "active_owner_nonterminal_previous_run"
            return outcome
        if run_in_progress == run_id:
            outcome["reason"] = "dead_owner_nonterminal_previous_run_without_mutation"
            return outcome
        # Recovery path: dead owner + no matching run-in-progress marker means stale
        # run-state residue. Allow startup to proceed so the next run can own truth.
        outcome["blocked"] = "0"
        if run_in_progress:
            outcome["reason"] = "dead_owner_nonterminal_stale_run_marker_mismatch"
        else:
            outcome["reason"] = "dead_owner_nonterminal_stale_run_marker_missing"
        return outcome
    except Exception as exc:
        return {
            "blocked": "1",
            "reason": "startup_nonterminal_guard_exception",
            "error": f"{type(exc).__name__}:{exc}",
            "run_id": "",
            "state": "",
            "owner_pid": "",
            "owner_alive": "0",
            "run_in_progress": "",
            "current_cycle_run_id": "",
            "state_utc": "",
        }


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
        # Worker subprocesses do not own cycle finalization ownership markers.
        if "--snapshot-refresh-worker" in sys.argv:
            return
        _append_h_parent_trace("write_unfinalized_exit_report", exit_code=_EXIT_CODE_HINT)
        _record_unresolved_phase1_intel_parent_exit("atexit_before_boundary_resolution")
        _record_unresolved_own_offer_parent_exit("atexit_before_own_offer_boundary_resolution")
        _record_unresolved_phase1_pilot_parent_exit("atexit_before_pilot_terminal_resolution")
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
        _reconcile_snapshot_worker_parent_handoff_on_parent_exit()
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
    if (
        rc == 0
        and _finalizer_contract_enforced()
        and _norm(run_id)
        and _norm(run_id) != _norm(finalized_run_id)
    ):
        _trace_publish_gap(run_id, "os_exit_promoted_missing_finalizer", last_finalized=finalized_run_id)
        rc = 3
    _EXIT_CODE_HINT = str(rc)
    _append_h_parent_trace("guarded_os_exit", requested_rc=requested_rc, forced_rc=rc, finalized_run_id=finalized_run_id)
    _record_unresolved_phase1_intel_parent_exit("hard_exit_before_boundary_resolution")
    _record_unresolved_own_offer_parent_exit("hard_exit_before_own_offer_boundary_resolution")
    _record_unresolved_phase1_pilot_parent_exit("hard_exit_before_pilot_terminal_resolution")
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
    completion_marker_path: Path | None = None,
    result_path: Path | None = None,
    checkpoint_path: Path | None = None,
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
            "completion_marker_path": str(completion_marker_path) if completion_marker_path is not None else "",
            "result_path": str(result_path) if result_path is not None else "",
            "checkpoint_path": str(checkpoint_path) if checkpoint_path is not None else "",
            "updated_utc": _ts(),
        }
    )


def _clear_active_phase1_pilot_wait() -> None:
    _ACTIVE_PHASE1_PILOT_WAIT.clear()


def _record_unresolved_phase1_pilot_parent_exit(reason: str) -> None:
    run_id = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("run_id", "")) or _context_run_id()
    if not run_id:
        return
    status = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("status", "")).lower()
    marker_status = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("marker_status", "")).lower()
    child_pid_raw = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("child_pid", ""))
    completion_marker_path_raw = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("completion_marker_path", ""))
    result_path_raw = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("result_path", ""))
    checkpoint_path_raw = _norm(_ACTIVE_PHASE1_PILOT_WAIT.get("checkpoint_path", ""))
    has_pilot_wait_context = any(
        (
            status,
            marker_status,
            child_pid_raw,
            completion_marker_path_raw,
            result_path_raw,
            checkpoint_path_raw,
        )
    )
    if not has_pilot_wait_context:
        return
    if status in {"", "exited_normal"} and marker_status in {"success", "failed"}:
        return

    child_pid = _to_int(child_pid_raw)
    completion_marker_path = Path(completion_marker_path_raw) if completion_marker_path_raw else None
    result_path = Path(result_path_raw) if result_path_raw else None
    checkpoint_path = Path(checkpoint_path_raw) if checkpoint_path_raw else None

    if child_pid is not None and _pid_alive(child_pid):
        try:
            subprocess.run(
                ["taskkill", "/PID", str(child_pid), "/T"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except Exception:
            pass
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and _pid_alive(child_pid):
            time.sleep(0.25)
        if _pid_alive(child_pid):
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(child_pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
            except Exception:
                pass

    marker_status_after = ""
    result_exists_after = False
    if completion_marker_path is not None and completion_marker_path.exists():
        try:
            marker_raw = json.loads(completion_marker_path.read_text(encoding="utf-8"))
            if isinstance(marker_raw, dict):
                marker_status_after = _norm(marker_raw.get("status", "")).lower()
        except Exception:
            marker_status_after = "invalid_json"
    if result_path is not None and result_path.exists():
        try:
            result_exists_after = int(result_path.stat().st_size) > 0
        except Exception:
            result_exists_after = False

    if (
        completion_marker_path is not None
        and result_path is not None
        and marker_status_after in {"", "started"}
        and not result_exists_after
    ):
        try:
            pilot_script = resolve_script_path(ROOT / "scripts", "H110_run_phase1_h_pilot.py")
            terminalizer_cmd = [
                sys.executable,
                "-u",
                str(pilot_script),
                "--post-exit-terminalizer",
                "--terminalizer-run-id",
                run_id,
                "--terminalizer-parent-pid",
                "0",
                "--terminalizer-marker-path",
                str(completion_marker_path),
                "--terminalizer-result-path",
                str(result_path),
                "--terminalizer-checkpoint-path",
                str(checkpoint_path) if checkpoint_path is not None else "",
                "--terminalizer-wait-seconds",
                "1",
            ]
            terminalizer_env = os.environ.copy()
            terminalizer_env["H110_TERMINALIZER_FALSE_FAIL_GUARD_SECONDS"] = "12"
            subprocess.run(
                terminalizer_cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
                timeout=45,
                env=terminalizer_env,
            )
        except Exception as exc:
            _log(
                "phase1 pilot_parent_exit_terminalizer_error "
                f"run_id={run_id} "
                f"error={type(exc).__name__}:{exc}"
            )

    marker_status_after = marker_status_after or marker_status
    _ACTIVE_PHASE1_PILOT_WAIT["status"] = "unresolved_parent_exit"
    _ACTIVE_PHASE1_PILOT_WAIT["detail"] = _norm(reason) or "parent_exit_before_pilot_terminal_resolution"
    _ACTIVE_PHASE1_PILOT_WAIT["marker_status"] = marker_status_after
    _ACTIVE_PHASE1_PILOT_WAIT["updated_utc"] = _ts()
    _log(
        "phase1 pilot boundary_failure "
        f"reason=parent_exit_before_resolution "
        f"run_id={run_id} "
        f"pilot_wait_status={status or 'missing'} "
        f"marker_status={marker_status_after or 'missing'} "
        f"child_pid={_norm(child_pid)}"
    )


def _set_active_own_offer_boundary(
    *,
    run_id: str,
    status: str,
    checkpoint: str = "",
    detail: str = "",
    output_path: Path | None = None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    child_pid: object = "",
) -> None:
    _ACTIVE_OWN_OFFER_BOUNDARY.clear()
    _ACTIVE_OWN_OFFER_BOUNDARY.update(
        {
            "run_id": _norm(run_id),
            "status": _norm(status).lower(),
            "checkpoint": _norm(checkpoint),
            "detail": _norm(detail),
            "output_path": str(output_path) if output_path is not None else "",
            "stdout_path": str(stdout_path) if stdout_path is not None else "",
            "stderr_path": str(stderr_path) if stderr_path is not None else "",
            "child_pid": _norm(child_pid),
            "updated_utc": _ts(),
        }
    )


def _clear_active_own_offer_boundary(run_id: str = "") -> None:
    target_run_id = _norm(run_id) or _norm(_ACTIVE_OWN_OFFER_BOUNDARY.get("run_id", ""))
    active_run_id = _norm(_ACTIVE_OWN_OFFER_BOUNDARY.get("run_id", ""))
    if target_run_id and active_run_id and target_run_id != active_run_id:
        return
    _ACTIVE_OWN_OFFER_BOUNDARY.clear()


def _record_unresolved_own_offer_parent_exit(reason: str) -> None:
    run_id = _norm(_ACTIVE_OWN_OFFER_BOUNDARY.get("run_id", "")) or _context_run_id()
    if not run_id:
        return
    status = _norm(_ACTIVE_OWN_OFFER_BOUNDARY.get("status", "")).lower()
    if status not in {"wait_start", "wait_done", "read_start", "read_done", "accept_start"}:
        return
    checkpoint = _norm(_ACTIVE_OWN_OFFER_BOUNDARY.get("checkpoint", "")) or "unknown"
    detail = _norm(reason) or "parent_exit_before_own_offer_boundary_resolution"
    stage_name = "snapshot_refresh/own_offer_lookup"
    failure_code = "OWN_OFFER_BOUNDARY_PARENT_EXIT_GAP"
    _append_h_parent_trace(
        "own_offer_boundary_parent_exit_gap",
        run_id=run_id,
        checkpoint=checkpoint,
        detail=detail,
        output_path=_ACTIVE_OWN_OFFER_BOUNDARY.get("output_path", ""),
        stdout_path=_ACTIVE_OWN_OFFER_BOUNDARY.get("stdout_path", ""),
        stderr_path=_ACTIVE_OWN_OFFER_BOUNDARY.get("stderr_path", ""),
        child_pid=_ACTIVE_OWN_OFFER_BOUNDARY.get("child_pid", ""),
    )
    _log(
        "snapshot_refresh own_offer_lookup own_offer_boundary_parent_exit_gap "
        f"run_id={run_id} "
        f"checkpoint={checkpoint} "
        f"detail={detail} "
        f"output_path={_norm(_ACTIVE_OWN_OFFER_BOUNDARY.get('output_path', ''))} "
        f"stdout_path={_norm(_ACTIVE_OWN_OFFER_BOUNDARY.get('stdout_path', ''))} "
        f"stderr_path={_norm(_ACTIVE_OWN_OFFER_BOUNDARY.get('stderr_path', ''))}"
    )
    _write_runtime_status(
        "ERROR",
        run_id=run_id,
        stage=stage_name,
        detail=f"own_offer_boundary_parent_exit_gap checkpoint={checkpoint} detail={detail}",
        error=failure_code,
    )
    _write_h_run_state(
        "failed",
        run_id=run_id,
        stage=stage_name,
        publish_status="not_started",
        failure_code=failure_code,
        failure_detail=f"checkpoint={checkpoint} detail={detail}",
    )


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
        popen_window_kwargs: dict[str, object] = {}
        if os.name == "nt":
            powershell_exe = (
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "WindowsPowerShell"
                / "v1.0"
                / "powershell.exe"
            )
            cmd = [
                str(powershell_exe),
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' } | "
                "Select-Object ProcessId,ParentProcessId,CommandLine | Format-List",
            ]
            popen_window_kwargs = _windows_hidden_subprocess_kwargs()
        else:
            cmd = ["ps", "-ef"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
            **popen_window_kwargs,
        )
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


def _alert_state_counts(path: Path, *, check_prefix: str = "") -> tuple[int, int] | None:
    if not path.exists():
        return None
    fail = 0
    warn = 0
    prefix = _norm(check_prefix).lower()
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                check_name = _norm(row.get("check", "")).lower()
                if prefix and not check_name.startswith(prefix):
                    continue
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
    # Single-stream rule: H gate decisions always use the H flow-owned gate file.
    if H_PRIMARY_CHECKLIST_PATH.exists():
        return H_PRIMARY_CHECKLIST_PATH, "flow_gate_primary_h"
    return H_PRIMARY_CHECKLIST_PATH, "flow_gate_primary_h_missing"


def _strategy_sample_min_rows_for_health(scenario_type: object) -> int:
    scenario = _norm(scenario_type).lower()
    if scenario == "multi_seller_ladder_cap":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_MULTI_SELLER", "150"), 150), 1)
    if scenario == "single_rival_reset":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_SINGLE_RIVAL", "30"), 30), 1)
    if scenario == "suppression_reactivation":
        return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_SUPPRESSION", "20"), 20), 1)
    return max(_safe_int(os.environ.get("H_STRATEGY_SAMPLE_MIN_DEFAULT", "30"), 30), 1)


def _strategy_health_scenarios_for_entry(*, scenario_type: object, chosen_tactic: object) -> list[str]:
    scenario = _norm(scenario_type).lower()
    tactic = _norm(chosen_tactic).upper()
    out: list[str] = []
    if scenario in {"multi_seller_ladder_cap", "single_rival_reset", "suppression_reactivation"}:
        out.append(scenario)
    if "SINGLE_RIVAL_RESET" in tactic and "single_rival_reset" not in out:
        out.append("single_rival_reset")
    if "SUPPRESSION_REACTIVATION" in tactic and "suppression_reactivation" not in out:
        out.append("suppression_reactivation")
    return out


def _h_strategy_sample_size_live_snapshot(path: Path, checklist_snapshot_utc: str) -> dict[str, str]:
    focus = ["multi_seller_ladder_cap", "single_rival_reset", "suppression_reactivation"]
    out: dict[str, str] = {
        "h_strategy_sample_live_status": "missing",
        "h_strategy_sample_live_path": str(path),
        "h_strategy_sample_live_mtime_utc": "",
        "h_strategy_sample_checklist_snapshot_utc": _norm(checklist_snapshot_utc),
        "h_strategy_sample_live_stale_vs_checklist": "0",
        "h_strategy_sample_live_asof_date": "",
        "h_strategy_sample_live_rows_scoped": "0",
        "h_strategy_sample_live_read_error": "",
    }
    for scenario in focus:
        out[f"h_strategy_sample_live_{scenario}_decision_rows"] = "0"
        out[f"h_strategy_sample_live_{scenario}_sample_min_rows"] = str(_strategy_sample_min_rows_for_health(scenario))
        out[f"h_strategy_sample_live_{scenario}_provisional_flag"] = "1"
        out[f"h_strategy_sample_live_{scenario}_gap_rows"] = out[
            f"h_strategy_sample_live_{scenario}_sample_min_rows"
        ]
        out[f"h_strategy_sample_live_{scenario}_chosen_tactic"] = ""

    if not path.exists():
        return out

    mtime_utc = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    out["h_strategy_sample_live_mtime_utc"] = mtime_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    checklist_dt = _to_dt(checklist_snapshot_utc)
    if checklist_dt is None:
        out["h_strategy_sample_live_stale_vs_checklist"] = "1" if _norm(checklist_snapshot_utc) else "0"
    else:
        out["h_strategy_sample_live_stale_vs_checklist"] = "1" if mtime_utc > (checklist_dt + timedelta(seconds=1)) else "0"

    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        out["h_strategy_sample_live_status"] = "read_error"
        out["h_strategy_sample_live_read_error"] = f"{type(exc).__name__}:{exc}"[:240]
        return out

    if df.empty:
        out["h_strategy_sample_live_status"] = "empty"
        return out
    if "scenario_type" not in df.columns:
        out["h_strategy_sample_live_status"] = "missing_scenario_type"
        return out

    asof_series = df.get("asof_date", "").astype(str).str.strip() if "asof_date" in df.columns else pd.Series([""] * len(df))
    non_blank_asof = asof_series[asof_series.ne("")]
    latest_asof = str(non_blank_asof.max()) if not non_blank_asof.empty else ""
    out["h_strategy_sample_live_asof_date"] = latest_asof
    if latest_asof:
        scoped = df.loc[asof_series.eq(latest_asof)].copy()
    else:
        scoped = df.copy()
    out["h_strategy_sample_live_rows_scoped"] = str(len(scoped.index))

    rows_by_scenario: dict[str, dict[str, object]] = {}
    for _, row in scoped.iterrows():
        row_scenarios = _strategy_health_scenarios_for_entry(
            scenario_type=row.get("scenario_type", ""),
            chosen_tactic=row.get("chosen_tactic", ""),
        )
        if not row_scenarios:
            continue
        row_decision_rows = max(_safe_int(row.get("decision_rows", "0"), 0), 0)
        row_sample_min = max(_safe_int(row.get("sample_min_rows", "0"), 0), 0)
        row_chosen_tactic = _norm(row.get("chosen_tactic", ""))
        for scenario in row_scenarios:
            stat = rows_by_scenario.get(
                scenario,
                {
                    "decision_rows": 0,
                    "sample_min_rows": _strategy_sample_min_rows_for_health(scenario),
                    "chosen_tactic": "",
                    "_chosen_tactic_decision_rows": -1,
                },
            )
            stat["decision_rows"] = int(_safe_int(stat.get("decision_rows", 0), 0) + row_decision_rows)
            stat["sample_min_rows"] = int(
                max(_safe_int(stat.get("sample_min_rows", 0), 0), row_sample_min or _strategy_sample_min_rows_for_health(scenario))
            )
            chosen_rows = _safe_int(stat.get("_chosen_tactic_decision_rows", -1), -1)
            if row_decision_rows > chosen_rows:
                stat["chosen_tactic"] = row_chosen_tactic
                stat["_chosen_tactic_decision_rows"] = row_decision_rows
            rows_by_scenario[scenario] = stat

    for scenario in focus:
        stat = rows_by_scenario.get(scenario, {})
        decision_rows = max(_safe_int(stat.get("decision_rows", "0"), 0), 0)
        sample_min_rows = max(
            _safe_int(stat.get("sample_min_rows", "0"), 0),
            _strategy_sample_min_rows_for_health(scenario),
        )
        provisional_flag = 1 if decision_rows < sample_min_rows else 0
        out[f"h_strategy_sample_live_{scenario}_decision_rows"] = str(decision_rows)
        out[f"h_strategy_sample_live_{scenario}_sample_min_rows"] = str(sample_min_rows)
        out[f"h_strategy_sample_live_{scenario}_provisional_flag"] = str(provisional_flag)
        out[f"h_strategy_sample_live_{scenario}_gap_rows"] = str(max(sample_min_rows - decision_rows, 0))
        out[f"h_strategy_sample_live_{scenario}_chosen_tactic"] = _norm(stat.get("chosen_tactic", ""))

    out["h_strategy_sample_live_status"] = "ok"
    return out


def _h_shadow_live_artifact_counts(now_utc: datetime) -> tuple[int, int, str]:
    # Shadow fallback: compute freshness directly from H-owned live artifacts.
    checks = [
        ("h_cycle_log_freshness", H_CYCLE_LOG_PATH, 20.0 * 60.0, 60.0 * 60.0),
        ("h_listing_offer_snapshot_latest_freshness", OUT / "listing_offer_snapshot_latest.csv", 20.0 * 60.0, 60.0 * 60.0),
        ("h_phase1_runtime_floor_snapshot_latest_freshness", PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH, 30.0 * 60.0, 90.0 * 60.0),
        ("h_terminal_marker_freshness", H_CYCLE_LAST_TERMINAL_INFO_PATH, 30.0 * 60.0, 90.0 * 60.0),
    ]
    fail_count = 0
    warn_count = 0
    notes: list[str] = []
    for check_name, path, warn_after_seconds, fail_after_seconds in checks:
        age_seconds = _file_age_seconds(path, now_utc)
        if age_seconds is None:
            fail_count += 1
            notes.append(f"{check_name}=missing")
            continue
        if age_seconds > fail_after_seconds:
            fail_count += 1
            notes.append(f"{check_name}=fail age_s={_fmt(_r2(age_seconds))}")
            continue
        if age_seconds > warn_after_seconds:
            warn_count += 1
            notes.append(f"{check_name}=warn age_s={_fmt(_r2(age_seconds))}")
            continue
        notes.append(f"{check_name}=ok age_s={_fmt(_r2(age_seconds))}")
    publish_status, publish_note = _classify_h_publish_freshness_with_terminal_fallback(
        now_utc,
        warn_after_seconds=30.0 * 60.0,
        fail_after_seconds=90.0 * 60.0,
    )
    if publish_status == "fail":
        fail_count += 1
    elif publish_status == "warn":
        warn_count += 1
    notes.append(f"h_publish_marker_freshness={publish_status} {publish_note}")
    return fail_count, warn_count, ";".join(notes)


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
    checklist_mtime_seconds = _mtime_seconds(checklist_path)
    checklist_age = _file_age_seconds(checklist_path, now_utc)
    checklist_age_fresh = bool(checklist_age is not None and checklist_age <= H_CHECKLIST_MAX_AGE_SECONDS)
    runtime_evidence_paths = [
        ("H_runtime_status", H_RUNTIME_STATUS_PATH),
        ("H_cycle_last_terminal_info", H_CYCLE_LAST_TERMINAL_INFO_PATH),
        ("H_cycle_last_publish_info", H_CYCLE_LAST_PUBLISH_INFO_PATH),
        ("H_run_in_progress", H_RUN_IN_PROGRESS_PATH),
        ("H_last_finalized_run_id", H_LAST_FINALIZED_RUN_ID_PATH),
    ]
    runtime_evidence_seconds: list[tuple[str, float]] = []
    for label, path in runtime_evidence_paths:
        ts = _mtime_seconds(path)
        if ts is None:
            continue
        runtime_evidence_seconds.append((label, float(ts)))
    runtime_latest_seconds = max([ts for _, ts in runtime_evidence_seconds], default=None)
    runtime_newer_sources = [
        label
        for label, ts in runtime_evidence_seconds
        if checklist_mtime_seconds is None or ts > (float(checklist_mtime_seconds) + 1.0)
    ]
    checklist_stale_vs_runtime = bool(runtime_newer_sources)
    checklist_readable = checklist_counts is not None
    alert_state_counts = _alert_state_counts(H_ALERT_STATE_PATH, check_prefix="h_")
    if alert_state_counts is None:
        alert_state_counts = _alert_state_counts(H_ALERT_STATE_GLOBAL_PATH, check_prefix="h_")
    alert_state_readable = alert_state_counts is not None
    alert_state_fail_count = alert_state_counts[0] if alert_state_counts is not None else -1
    alert_state_warn_count = alert_state_counts[1] if alert_state_counts is not None else -1
    alert_state_clean = bool(
        alert_state_readable and alert_state_fail_count <= 0 and alert_state_warn_count <= 0
    )
    checklist_stale_downgraded = bool(checklist_readable and checklist_stale_vs_runtime and alert_state_clean)
    checklist_fresh = bool(checklist_age_fresh and (not checklist_stale_vs_runtime or checklist_stale_downgraded))
    checklist_fail_count = checklist_counts[0] if checklist_counts is not None else -1
    checklist_warn_count = checklist_counts[1] if checklist_counts is not None else -1
    checklist_fail_count_effective = checklist_fail_count
    checklist_warn_count_effective = checklist_warn_count
    if checklist_stale_downgraded:
        checklist_fail_count_effective = 0
        checklist_warn_count_effective = 0

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
    if checklist_stale_downgraded:
        reasons.append("checklist_stale_downgraded_to_active_alert_state")
    elif checklist_readable and not checklist_fresh:
        reasons.append("checklist_stale")
    if checklist_readable and not checklist_age_fresh:
        reasons.append("checklist_stale_age")
    if checklist_readable and checklist_stale_vs_runtime and not checklist_stale_downgraded:
        reasons.append("checklist_stale_vs_newer_runtime_evidence")
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
        "checklist_age_fresh": "1" if checklist_age_fresh else "0",
        "checklist_stale_vs_runtime_evidence": "1" if checklist_stale_vs_runtime else "0",
        "checklist_stale_downgraded": "1" if checklist_stale_downgraded else "0",
        "checklist_fresh": "1" if checklist_fresh else "0",
        "checklist_age_seconds": _fmt(_r2(checklist_age)) if checklist_age is not None else "",
        "checklist_runtime_evidence_latest_utc": (
            datetime.fromtimestamp(runtime_latest_seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if runtime_latest_seconds is not None
            else ""
        ),
        "checklist_newer_runtime_evidence_count": str(len(runtime_newer_sources)),
        "checklist_newer_runtime_evidence_csv": ",".join(runtime_newer_sources),
        "checklist_fail_count": "" if checklist_fail_count_effective < 0 else str(checklist_fail_count_effective),
        "checklist_warn_count": "" if checklist_warn_count_effective < 0 else str(checklist_warn_count_effective),
        "checklist_fail_count_raw": "" if checklist_fail_count < 0 else str(checklist_fail_count),
        "checklist_warn_count_raw": "" if checklist_warn_count < 0 else str(checklist_warn_count),
        "alert_state_path": str(H_ALERT_STATE_PATH if H_ALERT_STATE_PATH.exists() else H_ALERT_STATE_GLOBAL_PATH),
        "alert_state_readable": "1" if alert_state_readable else "0",
        "alert_state_fail_count": "" if alert_state_fail_count < 0 else str(alert_state_fail_count),
        "alert_state_warn_count": "" if alert_state_warn_count < 0 else str(alert_state_warn_count),
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
        f"checklist_age_fresh={payload['checklist_age_fresh']}",
        f"checklist_stale_vs_runtime_evidence={payload['checklist_stale_vs_runtime_evidence']}",
        f"checklist_stale_downgraded={payload['checklist_stale_downgraded']}",
        f"checklist_fresh={payload['checklist_fresh']}",
        f"checklist_fail_count={payload['checklist_fail_count']}",
        f"checklist_warn_count={payload['checklist_warn_count']}",
        f"checklist_fail_count_raw={payload['checklist_fail_count_raw']}",
        f"checklist_warn_count_raw={payload['checklist_warn_count_raw']}",
        f"alert_state_readable={payload['alert_state_readable']}",
        f"alert_state_fail_count={payload['alert_state_fail_count']}",
        f"alert_state_warn_count={payload['alert_state_warn_count']}",
        f"checklist_newer_runtime_evidence_count={payload['checklist_newer_runtime_evidence_count']}",
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


def _write_h_run_state(
    state: str,
    *,
    run_id: str = "",
    stage: str = "",
    publish_status: str = "",
    failure_code: str = "",
    failure_detail: str = "",
) -> None:
    state_norm = _norm(state).lower()
    run_norm = _norm(run_id) or _context_run_id()
    stage_norm = _norm(stage) or _norm(_LAST_STAGE_NAME)
    payload = {
        "run_id": run_norm,
        "state": state_norm,
        "utc": _ts(),
        "owner_pid": str(os.getpid()),
        "stage": stage_norm,
        "publish_status": _norm(publish_status),
        "failure_code": _norm(failure_code),
        "failure_detail": _norm(failure_detail),
    }
    try:
        _write_json(H_RUN_STATE_PATH, payload)
    except Exception as exc:
        _log(
            "h_run_state_write_failed "
            f"state={state_norm or 'unknown'} "
            f"run_id={run_norm} "
            f"error={type(exc).__name__}:{exc}"
        )
        return
    if state_norm in {"failed", "finalized", "succeeded"} and run_norm:
        try:
            _write_last_terminal_marker(
                run_id=run_norm,
                now_utc=datetime.now(timezone.utc),
                terminal_state=state_norm,
                stage=stage_norm,
                publish_status=_norm(publish_status),
                failure_code=_norm(failure_code),
                failure_detail=_norm(failure_detail),
            )
        except Exception as exc:
            _log(
                "h_terminal_marker_write_failed "
                f"state={state_norm or 'unknown'} "
                f"run_id={run_norm} "
                f"error={type(exc).__name__}:{exc}"
            )
    line_parts = [
        "h_run_state_write",
        f"state={payload['state']}",
        f"run_id={payload['run_id']}",
        f"stage={payload['stage']}",
    ]
    if payload["publish_status"]:
        line_parts.append(f"publish_status={payload['publish_status']}")
    if payload["failure_code"]:
        line_parts.append(f"failure_code={payload['failure_code']}")
    _log(" ".join(line_parts))


def _read_h_worker_lifecycle() -> dict[str, str]:
    raw = _read_json(H_WORKER_LIFECYCLE_PATH, default={})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        out[str(key)] = _norm(value)
    return out


def _write_h_worker_lifecycle(payload: dict[str, str], *, emit_log: bool = True) -> bool:
    for attempt in range(1, H_WORKER_LIFECYCLE_WRITE_RETRIES + 1):
        try:
            _write_json(H_WORKER_LIFECYCLE_PATH, payload)
            if emit_log:
                _log(
                    "h_worker_lifecycle_write "
                    f"run_id={payload.get('run_id', '')} "
                    f"state={payload.get('state', '')} "
                    f"attempt={attempt}"
                )
            return True
        except Exception as exc:
            if attempt >= H_WORKER_LIFECYCLE_WRITE_RETRIES:
                _log(
                    "h_worker_lifecycle_write_failed "
                    f"run_id={payload.get('run_id', '')} "
                    f"state={payload.get('state', '')} "
                    f"attempt={attempt} "
                    f"error={type(exc).__name__}:{exc}"
                )
                return False
            time.sleep(0.05 * attempt)
    return False


def _transition_h_worker_lifecycle(
    run_id: str,
    state: str,
    *,
    reason_code: str = "",
    reason_detail: str = "",
    terminal_outcome: str = "",
    expected_outputs_ok: str = "",
    expected_outputs_missing: str = "",
    emit_log: bool = True,
) -> bool:
    state_norm = _norm(state).lower()
    if state_norm not in H_WORKER_LIFECYCLE_STATES:
        raise ValueError(f"unsupported H worker lifecycle state '{state_norm}'")
    run_norm = _norm(run_id) or _context_run_id()
    previous = dict(_WORKER_LIFECYCLE_CACHE) if _WORKER_LIFECYCLE_CACHE else _read_h_worker_lifecycle()
    payload = dict(previous)
    previous_run_norm = _norm(payload.get("run_id", ""))
    run_changed = bool(run_norm) and previous_run_norm != run_norm
    if run_changed:
        for stale_key in (
            "pending_utc",
            "claimed_utc",
            "claim_owner_pid",
            "running_utc",
            "finalizing_utc",
            "terminal_utc",
            "terminal_outcome",
            "reason_code",
            "reason_detail",
            "failure_code",
            "failure_detail",
            "archive_marker_path",
            "expected_outputs_ok",
            "expected_outputs_missing",
        ):
            payload.pop(stale_key, None)
    for stale_key in ("failure_code", "failure_detail", "archive_marker_path"):
        payload.pop(stale_key, None)
    payload["run_id"] = run_norm
    payload["worker_id"] = str(os.getpid())
    payload["state"] = state_norm
    payload["heartbeat_utc"] = _ts()
    payload["heartbeat_stale_after_seconds"] = _fmt(_r2(H_WORKER_LIFECYCLE_STALE_SECONDS))
    payload["write_retries"] = str(H_WORKER_LIFECYCLE_WRITE_RETRIES)
    if state_norm == "pending" and not payload.get("pending_utc"):
        payload["pending_utc"] = _ts()
    if state_norm == "claimed":
        payload["claimed_utc"] = _ts()
        payload["claim_owner_pid"] = str(os.getpid())
    if state_norm == "running" and not payload.get("running_utc"):
        payload["running_utc"] = _ts()
    if state_norm == "finalizing":
        payload["finalizing_utc"] = _ts()
    if state_norm in H_WORKER_TERMINAL_STATES:
        payload["terminal_utc"] = _ts()
        payload["terminal_outcome"] = _norm(terminal_outcome) or state_norm
    else:
        payload.pop("terminal_utc", None)
        payload.pop("terminal_outcome", None)
        payload.pop("expected_outputs_ok", None)
        payload.pop("expected_outputs_missing", None)
        if not reason_code:
            payload.pop("reason_code", None)
        if not reason_detail:
            payload.pop("reason_detail", None)
    if reason_code:
        payload["reason_code"] = _norm(reason_code)
    if reason_detail:
        payload["reason_detail"] = _norm(reason_detail)[:1000]
    if expected_outputs_ok:
        payload["expected_outputs_ok"] = _norm(expected_outputs_ok)
    if expected_outputs_missing:
        payload["expected_outputs_missing"] = _norm(expected_outputs_missing)
    ok = _write_h_worker_lifecycle(payload, emit_log=emit_log)
    if ok:
        _WORKER_LIFECYCLE_CACHE.clear()
        _WORKER_LIFECYCLE_CACHE.update(payload)
    return ok


def _heartbeat_h_worker_lifecycle() -> None:
    if not _WORKER_LIFECYCLE_CACHE:
        return
    state = _norm(_WORKER_LIFECYCLE_CACHE.get("state", "")).lower()
    if state in H_WORKER_TERMINAL_STATES:
        return
    payload = dict(_WORKER_LIFECYCLE_CACHE)
    payload["heartbeat_utc"] = _ts()
    if _write_h_worker_lifecycle(payload, emit_log=False):
        _WORKER_LIFECYCLE_CACHE.clear()
        _WORKER_LIFECYCLE_CACHE.update(payload)


def _verify_h_success_outputs(run_id: str) -> tuple[bool, list[str]]:
    run_norm = _norm(run_id)
    missing: list[str] = []
    if _read_first_line(H_CYCLE_LAST_PUBLISH_RUN_PATH) != run_norm:
        missing.append("H_cycle_last_publish_run_id_mismatch")
    if _read_first_line(H_CYCLE_LAST_COMPLETED_RUN_PATH) != run_norm:
        missing.append("H_cycle_last_completed_run_id_mismatch")
    if _read_first_line(H_LAST_FINALIZED_RUN_ID_PATH) != run_norm:
        missing.append("H_last_finalized_run_id_mismatch")
    run_state = _read_json(H_RUN_STATE_PATH, default={})
    state_run_id = _norm(run_state.get("run_id", "")) if isinstance(run_state, dict) else ""
    state_value = _norm(run_state.get("state", "")).lower() if isinstance(run_state, dict) else ""
    if state_run_id != run_norm or state_value != "finalized":
        missing.append("H_run_state_not_finalized_for_run")
    return (not missing), missing


def _assert_h_worker_claimed(run_id: str) -> None:
    run_norm = _norm(run_id)
    lifecycle = _read_h_worker_lifecycle()
    life_run_id = _norm(lifecycle.get("run_id", ""))
    life_state = _norm(lifecycle.get("state", "")).lower()
    if life_run_id != run_norm or life_state not in {"claimed", "running", "finalizing"}:
        raise RuntimeError(
            "h_worker_claim_required "
            f"run_id={run_norm} "
            f"lifecycle_run_id={life_run_id or 'missing'} "
            f"lifecycle_state={life_state or 'missing'}"
        )


def _refresh_runtime_status_heartbeat() -> None:
    _heartbeat_h_worker_lifecycle()
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


def _phase1_stage_seed_manifest_path(run_id: str) -> Path:
    return _h_stage_dir(run_id) / "phase1_stage_seed_manifest.json"


def _sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _file_signature(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        stat = path.stat()
    except Exception:
        return {}
    try:
        mtime_ns = int(getattr(stat, "st_mtime_ns", int(float(stat.st_mtime) * 1_000_000_000)))
    except Exception:
        mtime_ns = 0
    signature = {
        "size_bytes": str(int(stat.st_size)),
        "mtime_ns": str(mtime_ns),
        "sha1": "",
    }
    try:
        signature["sha1"] = _sha1_file(path)
    except Exception:
        signature["sha1"] = ""
    return signature


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
    seed_manifest_path = _phase1_stage_seed_manifest_path(run_id)
    seed_manifest: dict[str, object] = {
        "run_id": _norm(run_id),
        "seeded_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tables": {},
    }
    seed_tables: dict[str, dict[str, str]] = {}
    seeded = 0
    for table_name in PHASE1_STAGED_TABLES:
        src = DATA / f"{table_name}.csv"
        dst = stage_data_dir / f"{table_name}.csv"
        if not src.exists():
            continue
        if not dst.exists():
            try:
                shutil.copy2(src, dst)
                seeded += 1
            except Exception:
                continue
        signature = _file_signature(dst)
        if signature:
            seed_tables[table_name] = signature
    if seed_tables:
        seed_manifest["tables"] = seed_tables
        try:
            _write_json(seed_manifest_path, seed_manifest)
        except Exception:
            pass
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


def _phase1_publish_copy2(src: Path, dst: Path, *, retries: int = 30, sleep_seconds: float = 0.2) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError as exc:
            last_error = exc
            _log(
                "phase1 staged_publish_retry "
                f"op=copy2 attempt={attempt} retries={retries} src={src} dst={dst} error={exc}"
            )
            time.sleep(sleep_seconds)
    if last_error is not None:
        raise last_error
    shutil.copy2(src, dst)


def _phase1_publish_replace(src: Path, dst: Path, *, retries: int = 30, sleep_seconds: float = 0.2) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            os.replace(src, dst)
            return
        except PermissionError as exc:
            last_error = exc
            _log(
                "phase1 staged_publish_retry "
                f"op=replace attempt={attempt} retries={retries} src={src} dst={dst} error={exc}"
            )
            time.sleep(sleep_seconds)
    if last_error is not None:
        raise last_error
    os.replace(src, dst)


def _promote_phase1_staged_outputs(run_id: str) -> dict[str, str]:
    stage_data_dir = _h_stage_data_dir(run_id)
    if not stage_data_dir.exists():
        return {
            "phase1_staged_publish_status": "missing_staged_dir",
            "phase1_staged_publish_files": "0",
        }
    copy_plan: list[tuple[str, Path, Path, Path]] = []
    for table_name in PHASE1_STAGED_TABLES:
        src = stage_data_dir / f"{table_name}.csv"
        if not src.exists():
            continue
        dst = DATA / f"{table_name}.csv"
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp_dst = dst.with_name(f".{dst.name}.tmp.h_stage.{os.getpid()}.{time.time_ns()}")
        copy_plan.append((table_name, src, dst, tmp_dst))
    if not copy_plan:
        return {
            "phase1_staged_publish_status": "missing_staged_files",
            "phase1_staged_publish_files": "0",
        }

    seed_manifest = _read_json(_phase1_stage_seed_manifest_path(run_id), default={})
    seed_tables_raw = seed_manifest.get("tables", {}) if isinstance(seed_manifest, dict) else {}
    seed_tables = seed_tables_raw if isinstance(seed_tables_raw, dict) else {}
    publish_plan: list[tuple[str, Path, Path, Path]] = []
    skipped_live_newer_tables: list[str] = []
    for table_name, src, dst, tmp_dst in copy_plan:
        should_skip = False
        seed_sig_raw = seed_tables.get(table_name, {})
        seed_sig = seed_sig_raw if isinstance(seed_sig_raw, dict) else {}
        seed_sha1 = _norm(seed_sig.get("sha1", ""))
        if dst.exists() and seed_sha1:
            stage_sig = _file_signature(src)
            live_sig = _file_signature(dst)
            stage_unchanged_since_seed = _norm(stage_sig.get("sha1", "")) == seed_sha1
            live_changed_since_seed = bool(_norm(live_sig.get("sha1", ""))) and _norm(live_sig.get("sha1", "")) != seed_sha1
            if stage_unchanged_since_seed and live_changed_since_seed:
                should_skip = True
        if should_skip:
            skipped_live_newer_tables.append(table_name)
            continue
        publish_plan.append((table_name, src, dst, tmp_dst))

    restored = 0
    replaced = 0
    backups: list[tuple[Path, Path]] = []
    backup_dir = H_LIVE_DIR / "tmp_publish_backups" / (_norm(run_id) or "unknown_run")
    backup_dir.mkdir(parents=True, exist_ok=True)
    failed_table = ""
    failed_target = ""
    try:
        # Pre-copy every staged source into temp target files before commit.
        for table_name, src, _dst, tmp_dst in publish_plan:
            failed_table = table_name
            failed_target = str(tmp_dst)
            _phase1_publish_copy2(src, tmp_dst)

        # Commit phase: replace live files and keep backups for rollback.
        for table_name, _src, dst, tmp_dst in publish_plan:
            failed_table = table_name
            failed_target = str(dst)
            backup_path = backup_dir / f"{dst.name}.bak.{time.time_ns()}"
            if dst.exists():
                _phase1_publish_copy2(dst, backup_path)
                backups.append((backup_path, dst))
            _phase1_publish_replace(tmp_dst, dst)
            replaced += 1
    except Exception as exc:
        # Roll back any replaced destinations to keep live set unchanged on failure.
        for backup_path, dst in backups:
            try:
                if backup_path.exists():
                    _phase1_publish_copy2(backup_path, dst)
                    restored += 1
            except Exception:
                pass
        return {
            "phase1_staged_publish_status": f"failed:{type(exc).__name__}",
            "phase1_staged_publish_files": str(replaced),
            "phase1_staged_publish_restored_files": str(restored),
            "phase1_staged_publish_skipped_live_newer": str(len(skipped_live_newer_tables)),
            "phase1_staged_publish_skipped_tables": "|".join(skipped_live_newer_tables) if skipped_live_newer_tables else "",
            "phase1_staged_publish_failed_table": failed_table,
            "phase1_staged_publish_failed_target": failed_target,
            "phase1_staged_publish_error": str(exc),
        }
    finally:
        for _table_name, _src, _dst, tmp_dst in copy_plan:
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
        "phase1_staged_publish_skipped_live_newer": str(len(skipped_live_newer_tables)),
        "phase1_staged_publish_skipped_tables": "|".join(skipped_live_newer_tables) if skipped_live_newer_tables else "",
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


def _resolve_item_offers_watchdog_timeout_seconds(
    *,
    snapshot_refresh_timeout_seconds: float,
    base_timeout_seconds: float | None = None,
    elapsed_seconds: float = 0.0,
) -> float:
    try:
        base = float(base_timeout_seconds if base_timeout_seconds is not None else H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS)
    except Exception:
        base = float(H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS)
    base = max(base, 1.0)
    try:
        snapshot_budget = float(snapshot_refresh_timeout_seconds)
    except Exception:
        snapshot_budget = base
    snapshot_budget = max(snapshot_budget, base)
    if snapshot_budget <= base:
        return base
    try:
        elapsed = max(float(elapsed_seconds), 0.0)
    except Exception:
        elapsed = 0.0
    return max(snapshot_budget - elapsed, 1.0)


def _run_item_offers_lookup_guarded(
    *,
    sku_asins: List[tuple[str, str]],
    marketplace_id: str,
    snapshot_ts: str,
    snapshot_date: str,
    run_id: str,
    script_name: str,
    subprocess_boundary: bool = False,
    prioritized_asins: List[str] | None = None,
    max_asins_override: int | None = None,
    timeout_seconds: float | None = None,
) -> tuple[Dict[str, Dict[str, str]], List[Dict[str, str]], Dict[str, Dict[str, str]]]:
    tmp_dir = H_LIVE_DIR / "tmp_item_offers_lookup"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{os.getpid()}.{time.time_ns()}"
    in_path = tmp_dir / f"in.{token}.json"
    out_path = tmp_dir / f"out.{token}.json"
    proc: subprocess.CompletedProcess | None = None
    max_asins_env_prev = os.environ.get("SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN")
    max_asins_override_int = int(max_asins_override or 0)
    lookup_timeout_seconds = max(float(timeout_seconds or H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS), 1.0)

    def _run_inline_lookup_payload() -> dict[str, object]:
        bb_map_raw, offer_rows_raw, detail_meta_raw = run_market_context_lookup_with_offers_detail(
            sku_asin_rows=sku_asins,
            marketplace_id=_norm(marketplace_id),
            snapshot_timestamp_utc=_norm(snapshot_ts),
            snapshot_asof_date=_norm(snapshot_date),
            run_id=_norm(run_id),
            script_name=_norm(script_name) or "run_H_pricing_cycle",
            progress_callback=None,
            prioritized_asins=prioritized_asins or [],
        )
        return {
            "bb_map": bb_map_raw,
            "offer_rows": offer_rows_raw,
            "detail_meta_by_asin": detail_meta_raw,
        }

    if max_asins_override_int > 0:
        os.environ["SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN"] = str(max_asins_override_int)
    try:
        _append_h_parent_trace(
            "item_offers_enter",
            run_id=run_id,
            sku_count=str(len(sku_asins)),
            marketplace_id=marketplace_id,
            helper_script="inline:run_market_context_lookup_with_offers_detail",
            input_path=in_path,
            output_path=out_path,
        )
        _write_runtime_status("RUNNING", run_id=run_id, stage="item_offers", detail="item_offers_enter")
        in_path.write_text(
            json.dumps({"sku_asins": sku_asins, "prioritized_asins": prioritized_asins or []}, ensure_ascii=True),
            encoding="utf-8",
        )
        _log(
            "snapshot_refresh item_offers inline_call_start "
            f"sku_count={len(sku_asins)} "
            f"marketplace_id={marketplace_id} "
            f"run_id={run_id}"
        )
        _append_h_parent_trace(
            "item_offers_wait_active",
            run_id=run_id,
            sku_count=str(len(sku_asins)),
            marketplace_id=marketplace_id,
            helper_script=(
                "subprocess:H_item_offers_lookup.py"
                if subprocess_boundary
                else "inline:run_market_context_lookup_with_offers_detail"
            ),
            input_path=in_path,
            output_path=out_path,
            timeout_seconds=str(int(lookup_timeout_seconds)),
        )
        _write_runtime_status("RUNNING", run_id=run_id, stage="item_offers", detail="item_offers_wait_active")
        if subprocess_boundary:
            helper_path = resolve_script_path(ROOT / "scripts" / "tools", "H_item_offers_lookup.py")
            stdout_path = tmp_dir / f"stdout.{token}.log"
            stderr_path = tmp_dir / f"stderr.{token}.log"
            cmd = [
                sys.executable,
                str(helper_path),
                "--input",
                str(in_path),
                "--output",
                str(out_path),
                "--marketplace-id",
                str(_norm(marketplace_id)),
                "--snapshot-ts",
                str(_norm(snapshot_ts)),
                "--snapshot-date",
                str(_norm(snapshot_date)),
                "--run-id",
                str(_norm(run_id)),
                "--script-name",
                str(_norm(script_name) or "run_H_pricing_cycle"),
            ]
            proc = _run_subprocess_with_watchdog_redirected(
                cmd,
                timeout_seconds=lookup_timeout_seconds,
                cwd=ROOT,
                log_prefix="snapshot_refresh item_offers",
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            if int(proc.returncode) != 0:
                stderr_tail = _norm(proc.stderr or "").splitlines()
                stderr_last = stderr_tail[-1] if stderr_tail else ""
                raise RuntimeError(
                    "item_offers_lookup_subprocess_failed "
                    f"rc={int(proc.returncode)} "
                    f"stderr_tail={stderr_last}"
                )
            if not out_path.exists():
                # Windows/AV/file-indexer lag can make just-written files briefly invisible
                # even after subprocess rc=0. Wait on visibility before fail-closing.
                output_wait_seconds = float(H_ITEM_OFFERS_OUTPUT_VISIBILITY_WAIT_SECONDS)
                _log(
                    "snapshot_refresh item_offers subprocess_missing_output_rc0 "
                    f"run_id={run_id} "
                    f"sku_count={len(sku_asins)} "
                    f"output_path={out_path} "
                    f"recovery=visibility_wait_start wait_seconds={int(output_wait_seconds)}"
                )
                output_wait_deadline = time.monotonic() + output_wait_seconds
                while time.monotonic() < output_wait_deadline:
                    if out_path.exists():
                        break
                    time.sleep(0.25)
                if out_path.exists():
                    _log(
                        "snapshot_refresh item_offers subprocess_missing_output_rc0 "
                        f"run_id={run_id} "
                        f"sku_count={len(sku_asins)} "
                        f"output_path={out_path} "
                        "recovery=visibility_wait_success"
                    )
                else:
                    _log(
                        "snapshot_refresh item_offers subprocess_missing_output_rc0 "
                        f"run_id={run_id} "
                        f"sku_count={len(sku_asins)} "
                        f"output_path={out_path} "
                        "recovery=visibility_wait_failed_fail_closed"
                    )
                    recovered = False
                    recovery_retries = int(H_ITEM_OFFERS_LOOKUP_RC0_RECOVERY_RETRIES)
                    for retry_idx in range(1, recovery_retries + 1):
                        _log(
                            "snapshot_refresh item_offers subprocess_missing_output_rc0 "
                            f"run_id={run_id} "
                            f"sku_count={len(sku_asins)} "
                            f"output_path={out_path} "
                            f"recovery=subprocess_retry_start retry={retry_idx}/{recovery_retries}"
                        )
                        proc_retry = _run_subprocess_with_watchdog_redirected(
                            cmd,
                            timeout_seconds=lookup_timeout_seconds,
                            cwd=ROOT,
                            log_prefix="snapshot_refresh item_offers",
                            stdout_path=stdout_path,
                            stderr_path=stderr_path,
                        )
                        if int(proc_retry.returncode) != 0:
                            stderr_tail_retry = _norm(proc_retry.stderr or "").splitlines()
                            stderr_last_retry = stderr_tail_retry[-1] if stderr_tail_retry else ""
                            raise RuntimeError(
                                "item_offers_lookup_subprocess_failed "
                                f"rc={int(proc_retry.returncode)} "
                                f"stderr_tail={stderr_last_retry}"
                            )
                        retry_deadline = time.monotonic() + output_wait_seconds
                        while time.monotonic() < retry_deadline:
                            if out_path.exists():
                                recovered = True
                                break
                            time.sleep(0.25)
                        if recovered:
                            _log(
                                "snapshot_refresh item_offers subprocess_missing_output_rc0 "
                                f"run_id={run_id} "
                                f"sku_count={len(sku_asins)} "
                                f"output_path={out_path} "
                                f"recovery=subprocess_retry_success retry={retry_idx}/{recovery_retries}"
                            )
                            break
                        _log(
                            "snapshot_refresh item_offers subprocess_missing_output_rc0 "
                            f"run_id={run_id} "
                            f"sku_count={len(sku_asins)} "
                            f"output_path={out_path} "
                            f"recovery=subprocess_retry_missing retry={retry_idx}/{recovery_retries}"
                        )
                    if not recovered and H_ITEM_OFFERS_LOOKUP_RC0_INLINE_FALLBACK_ENABLED:
                        _log(
                            "snapshot_refresh item_offers subprocess_missing_output_rc0 "
                            f"run_id={run_id} "
                            f"sku_count={len(sku_asins)} "
                            f"output_path={out_path} "
                            "recovery=inline_fallback_start"
                        )
                        _append_h_parent_trace(
                            "item_offers_missing_output_inline_fallback_start",
                            run_id=run_id,
                            child_rc="0",
                            output_path=out_path,
                        )
                        payload = _run_inline_lookup_payload()
                        out_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
                        recovered = out_path.exists()
                        _append_h_parent_trace(
                            "item_offers_missing_output_inline_fallback_done",
                            run_id=run_id,
                            child_rc="0",
                            output_exists="1" if recovered else "0",
                            output_path=out_path,
                        )
                        _log(
                            "snapshot_refresh item_offers subprocess_missing_output_rc0 "
                            f"run_id={run_id} "
                            f"sku_count={len(sku_asins)} "
                            f"output_path={out_path} "
                            f"recovery=inline_fallback_{'success' if recovered else 'missing'}"
                        )
                    if not recovered:
                        raise RuntimeError(
                            "item_offers_lookup_subprocess_missing_output_rc0 "
                            f"output_path={out_path} "
                            "visibility_wait_timeout"
                        )
        else:
            out_path.write_text(json.dumps(_run_inline_lookup_payload(), ensure_ascii=True), encoding="utf-8")
        _append_h_parent_trace(
            "item_offers_boundary_wait_done",
            run_id=run_id,
            child_rc="0",
            output_exists="1" if out_path.exists() else "0",
            output_path=out_path,
        )
        _append_h_parent_trace(
            "item_offers_boundary_read_start",
            run_id=run_id,
            output_path=out_path,
        )
        payload = _read_json(out_path, default={})
        if not isinstance(payload, dict):
            raise RuntimeError("item_offers_lookup_invalid_output")
        bb_map = payload.get("bb_map", {})
        offer_rows = payload.get("offer_rows", [])
        detail_meta = payload.get("detail_meta_by_asin", {})
        if not isinstance(bb_map, dict):
            bb_map = {}
        if not isinstance(offer_rows, list):
            offer_rows = []
        if not isinstance(detail_meta, dict):
            detail_meta = {}
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
        out_detail: Dict[str, Dict[str, str]] = {}
        for asin, meta in detail_meta.items():
            asin_key = _norm(asin)
            if not asin_key or not isinstance(meta, dict):
                continue
            out_detail[asin_key] = {str(k): _norm(v) for k, v in meta.items()}
        _append_h_parent_trace(
            "item_offers_boundary_read_done",
            run_id=run_id,
            payload_type=type(payload).__name__,
            bb_count=str(len(out_map)),
            offer_row_count=str(len(out_rows)),
            detail_meta_count=str(len(out_detail)),
        )
        _append_h_parent_trace(
            "item_offers_exit_normal",
            run_id=run_id,
            child_rc="0",
            bb_count=str(len(out_map)),
            offer_row_count=str(len(out_rows)),
            detail_meta_count=str(len(out_detail)),
            output_path=out_path,
        )
        _write_runtime_status("RUNNING", run_id=run_id, stage="item_offers", detail="item_offers_exit_normal rc=0")
        return out_map, out_rows, out_detail
    except BaseException as exc:
        error_text = f"{type(exc).__name__}:{exc}"[:400]
        child_rc = str(int(proc.returncode)) if proc is not None else ""
        abnormal_reason = "inline_exception_before_result"
        helper_script = (
            "subprocess:H_item_offers_lookup.py"
            if subprocess_boundary
            else "inline:run_market_context_lookup_with_offers_detail"
        )
        _append_h_parent_trace(
            "item_offers_abnormal_exit",
            run_id=run_id,
            error_type=type(exc).__name__,
            error=str(exc)[:400],
            abnormal_reason=abnormal_reason,
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
        if max_asins_override_int > 0:
            if max_asins_env_prev is None:
                os.environ.pop("SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN", None)
            else:
                os.environ["SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN"] = max_asins_env_prev
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
    stdout_path = tmp_dir / f"stdout.{token}.log"
    stderr_path = tmp_dir / f"stderr.{token}.log"
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
        env = os.environ.copy()
        rc = -1
        stdout_tail = ""
        stderr_tail = ""
        _log(
            "snapshot_refresh own_offer_lookup launch "
            f"helper={helper_script} "
            f"sku_count={len(skus)} "
            f"marketplace_id={marketplace_id_norm} "
            f"stdout_path={stdout_path} "
            f"stderr_path={stderr_path} "
            f"cmd={' '.join(str(part) for part in cmd)}"
        )
        _log(
            "snapshot_refresh own_offer_lookup watchdog_run_start "
            f"timeout_seconds={int(H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS)} "
            f"cwd={ROOT} "
            f"cmd={' '.join(str(part) for part in cmd)}"
        )
        _set_active_own_offer_boundary(
            run_id=run_id,
            status="wait_start",
            checkpoint="own_offer_boundary_wait_start",
            output_path=out_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            child_pid="",
        )
        proc = _run_subprocess_with_watchdog_redirected(
            cmd,
            timeout_seconds=H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS,
            cwd=ROOT,
            log_prefix="snapshot_refresh own_offer_lookup",
            env_overrides=env,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        rc = int(proc.returncode)
        stdout_tail = _norm(proc.stdout)
        stderr_tail = _norm(proc.stderr)
        _set_active_own_offer_boundary(
            run_id=run_id,
            status="wait_done",
            checkpoint="own_offer_boundary_wait_done",
            output_path=out_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            child_pid="",
        )
        _log(
            "snapshot_refresh own_offer_lookup own_offer_boundary_wait_done "
            f"run_id={run_id} "
            "child_pid=0 "
            f"rc={rc} "
            f"output_exists={'1' if out_path.exists() else '0'}"
        )
        _log(
            "snapshot_refresh own_offer_lookup watchdog_wait_end "
            "child_pid=0 "
            f"rc={rc}"
        )
        _log(
            "snapshot_refresh own_offer_lookup watchdog_run_end "
            f"rc={rc} "
            f"stdout_tail={stdout_tail} "
            f"stderr_tail={stderr_tail}"
        )
        _log(
            "snapshot_refresh own_offer_lookup output_json_check "
            f"output_path={out_path} "
            f"output_exists={'1' if out_path.exists() else '0'}"
        )
        if int(rc) != 0:
            err = _norm(stderr_tail) or _norm(stdout_tail) or f"rc={rc}"
            raise RuntimeError(f"own_offer_lookup_failed {err[:400]}")
        _set_active_own_offer_boundary(
            run_id=run_id,
            status="read_start",
            checkpoint="own_offer_boundary_read_start",
            output_path=out_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            child_pid="",
        )
        _log(
            "snapshot_refresh own_offer_lookup own_offer_boundary_read_start "
            f"run_id={run_id} "
            f"output_path={out_path}"
        )
        payload = _read_json(out_path, default={})
        _set_active_own_offer_boundary(
            run_id=run_id,
            status="read_done",
            checkpoint="own_offer_boundary_read_done",
            output_path=out_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            child_pid="",
        )
        _log(
            "snapshot_refresh own_offer_lookup own_offer_boundary_read_done "
            f"run_id={run_id} "
            f"payload_type={type(payload).__name__}"
        )
        _set_active_own_offer_boundary(
            run_id=run_id,
            status="accept_start",
            checkpoint="own_offer_boundary_accept_start",
            output_path=out_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            child_pid="",
        )
        _log(
            "snapshot_refresh own_offer_lookup own_offer_boundary_accept_start "
            f"run_id={run_id}"
        )
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
        _set_active_own_offer_boundary(
            run_id=run_id,
            status="accept_done",
            checkpoint="own_offer_boundary_accept_done",
            output_path=out_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            child_pid="",
        )
        _log(
            "snapshot_refresh own_offer_lookup own_offer_boundary_accept_done "
            f"run_id={run_id} "
            f"accepted_rows={len(out_map)}"
        )
        _clear_active_own_offer_boundary(run_id)
        return out_map
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        if isinstance(exc, SystemExit):
            code = _system_exit_code(exc)
            if code == 0:
                raise RuntimeError("own_offer_lookup_boundary_failure system_exit_zero_promoted") from exc
            raise
        error_type = type(exc).__name__
        error_text = _norm(str(exc))[:400] or "unknown"
        _set_active_own_offer_boundary(
            run_id=run_id,
            status="failed",
            checkpoint="own_offer_boundary_failed",
            detail=f"{error_type}:{error_text}",
            output_path=out_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        _log(
            "snapshot_refresh own_offer_lookup own_offer_boundary_failed "
            f"run_id={run_id} "
            f"error_type={error_type} "
            f"detail={error_text}"
        )
        stage_name = "snapshot_refresh/own_offer_lookup"
        failure_code = "OWN_OFFER_LOOKUP_ABNORMAL_EXIT"
        _append_h_parent_trace(
            "own_offer_lookup_abnormal_exit",
            run_id=run_id,
            stage=stage_name,
            failure_code=failure_code,
            error_type=error_type,
            detail=error_text,
            helper_script=helper_script,
            output_exists="1" if out_path.exists() else "0",
        )
        _log(
            "snapshot_refresh own_offer_lookup abnormal_exit "
            f"run_id={run_id} "
            f"stage={stage_name} "
            f"failure_code={failure_code} "
            f"error_type={error_type} "
            f"error={error_text} "
            f"helper_script={helper_script} "
            f"output_exists={'1' if out_path.exists() else '0'}"
        )
        _write_runtime_status(
            "ERROR",
            run_id=run_id,
            stage=stage_name,
            detail=f"own_offer_lookup_abnormal_exit error={error_type}:{error_text}",
            error=failure_code,
        )
        _write_h_run_state(
            "failed",
            run_id=run_id,
            stage=stage_name,
            publish_status="not_started",
            failure_code=failure_code,
            failure_detail=f"{error_type}:{error_text}",
        )
        raise RuntimeError(
            f"own_offer_lookup_boundary_failure run_id={run_id} "
            f"failure_code={failure_code} error_type={error_type} detail={error_text}"
        ) from exc
    finally:
        _clear_active_own_offer_boundary(run_id)
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


def _log_target_paths() -> List[Path]:
    out: List[Path] = [LOG_PATH, H_CYCLE_LOG_PATH]
    if H_WRITE_LEGACY_LOGS:
        if LEGACY_LOG_PATH not in out:
            out.append(LEGACY_LOG_PATH)
        if LEGACY_H_CYCLE_LOG_PATH not in out:
            out.append(LEGACY_H_CYCLE_LOG_PATH)
    return out


def _rotate_log_file(path: Path, *, max_bytes: int, max_files: int) -> bool:
    if max_bytes <= 0 or max_files <= 1:
        return False
    try:
        if not path.exists():
            return False
        if int(path.stat().st_size) < int(max_bytes):
            return False
    except Exception:
        return False
    try:
        oldest = Path(f"{path}.{max_files}")
        if oldest.exists():
            oldest.unlink(missing_ok=True)
        for idx in range(max_files - 1, 0, -1):
            src = Path(f"{path}.{idx}")
            dst = Path(f"{path}.{idx + 1}")
            if src.exists():
                src.replace(dst)
        path.replace(Path(f"{path}.1"))
        return True
    except Exception:
        return False


def _dedupe_emit(cache: dict[str, float], key: str, min_interval_seconds: float) -> bool:
    if min_interval_seconds <= 0:
        return True
    now = time.monotonic()
    last = float(cache.get(key, 0.0) or 0.0)
    if last > 0.0 and (now - last) < min_interval_seconds:
        return False
    cache[key] = now
    if len(cache) > 8192:
        stale_before = now - max(min_interval_seconds * 4.0, 60.0)
        stale_keys = [k for k, ts in cache.items() if ts < stale_before]
        for stale_key in stale_keys[:4096]:
            cache.pop(stale_key, None)
    return True


def _file_size_bytes(path: Path) -> int:
    try:
        if path.exists():
            return int(path.stat().st_size)
    except Exception:
        pass
    return 0


def _dir_tree_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += _file_size_bytes(item)
    except Exception:
        return 0
    return int(total)


def _extended_path_for_windows(path: Path) -> str:
    raw = str(path.resolve())
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\?\\"):
        return raw
    if raw.startswith("\\\\"):
        # UNC form: \\server\share -> \\?\UNC\server\share
        return "\\\\?\\UNC\\" + raw.lstrip("\\")
    return "\\\\?\\" + raw


def _rmtree_best_effort(path: Path) -> bool:
    def _onerror(func, p, _exc_info):
        with contextlib.suppress(Exception):
            os.chmod(p, stat.S_IWRITE)
            func(p)

    try:
        shutil.rmtree(path, onerror=_onerror)
        return True
    except Exception:
        pass
    try:
        shutil.rmtree(_extended_path_for_windows(path), onerror=_onerror)
        return True
    except Exception:
        pass
    try:
        proc = subprocess.run(
            ["cmd", "/c", "rmdir", "/s", "/q", str(path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        return proc.returncode == 0 and not path.exists()
    except Exception:
        return False


def _record_cleanup_ledger_entries(entries: list[dict[str, object]]) -> dict[str, int]:
    if not entries:
        return {"ledger_entries_written": 0, "ledger_before_bytes": _file_size_bytes(H_CLEANUP_LEDGER_PATH), "ledger_after_bytes": _file_size_bytes(H_CLEANUP_LEDGER_PATH), "ledger_rotated": 0}
    H_CLEANUP_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    before = _log_family_snapshot(H_CLEANUP_LEDGER_PATH)
    rotated = 0
    if _rotate_log_file(
        H_CLEANUP_LEDGER_PATH,
        max_bytes=H_CLEANUP_LEDGER_ROTATE_MAX_BYTES,
        max_files=H_CLEANUP_LEDGER_ROTATE_MAX_FILES,
    ):
        rotated = 1
    with H_CLEANUP_LEDGER_PATH.open("a", encoding="utf-8", newline="\n") as fh:
        for entry in entries:
            payload = {
                "ts_utc": _ts(),
                "policy": _norm(entry.get("policy", "")),
                "target": _norm(entry.get("target", "")),
                "action": _norm(entry.get("action", "")),
                "reason": _norm(entry.get("reason", "")),
                "file_count": int(float(entry.get("file_count", 0) or 0)),
                "bytes_removed": int(float(entry.get("bytes_removed", 0) or 0)),
                "status": _norm(entry.get("status", "")) or "ok",
                "sample": [str(x) for x in (entry.get("sample", []) or [])[:3]],
            }
            fh.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
    _prune_log_family_budget(
        H_CLEANUP_LEDGER_PATH,
        max_total_bytes=H_CLEANUP_LEDGER_FAMILY_MAX_BYTES,
        max_total_files=H_CLEANUP_LEDGER_ROTATE_MAX_FILES + 1,
    )
    after = _log_family_snapshot(H_CLEANUP_LEDGER_PATH)
    return {
        "ledger_entries_written": len(entries),
        "ledger_before_bytes": int(before.get("total_bytes", 0)),
        "ledger_after_bytes": int(after.get("total_bytes", 0)),
        "ledger_rotated": int(rotated),
    }


def _compact_csv_latest_per_key(
    *,
    path: Path,
    key_col: str,
    ts_col: str,
    trigger_bytes: int,
    target_max_bytes: int,
) -> dict[str, object]:
    before_bytes = _file_size_bytes(path)
    if before_bytes <= 0:
        return {"status": "missing", "before_bytes": 0, "after_bytes": 0, "bytes_removed": 0, "rows_before": 0, "rows_after": 0}
    if before_bytes < max(trigger_bytes, 1):
        return {"status": "below_trigger", "before_bytes": before_bytes, "after_bytes": before_bytes, "bytes_removed": 0, "rows_before": 0, "rows_after": 0}
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, engine="python")
    except Exception:
        return {"status": "read_error", "before_bytes": before_bytes, "after_bytes": before_bytes, "bytes_removed": 0, "rows_before": 0, "rows_after": 0}
    if key_col not in frame.columns:
        return {"status": "missing_key", "before_bytes": before_bytes, "after_bytes": before_bytes, "bytes_removed": 0, "rows_before": int(len(frame.index)), "rows_after": int(len(frame.index))}

    rows_before = int(len(frame.index))
    if rows_before <= 1:
        return {"status": "no_rows", "before_bytes": before_bytes, "after_bytes": before_bytes, "bytes_removed": 0, "rows_before": rows_before, "rows_after": rows_before}

    frame["_cleanup_key"] = frame.get(key_col, "").astype(str).str.strip().str.upper()
    frame = frame.loc[frame["_cleanup_key"].ne("")].copy()
    if frame.empty:
        return {"status": "empty_after_key_filter", "before_bytes": before_bytes, "after_bytes": before_bytes, "bytes_removed": 0, "rows_before": rows_before, "rows_after": 0}

    if ts_col in frame.columns:
        frame["_cleanup_ts"] = pd.to_datetime(frame.get(ts_col, ""), errors="coerce", utc=True)
    else:
        frame["_cleanup_ts"] = pd.NaT
    frame["_cleanup_idx"] = range(len(frame.index))
    frame = frame.sort_values(["_cleanup_ts", "_cleanup_idx"], ascending=[False, False], kind="stable")
    compacted = frame.groupby("_cleanup_key", as_index=False).head(1).copy()
    compacted = compacted.drop(columns=[c for c in ["_cleanup_key", "_cleanup_ts", "_cleanup_idx"] if c in compacted.columns], errors="ignore")

    tmp_path = path.with_name(f".{path.name}.tmp.cleanup.{os.getpid()}.{time.time_ns()}")
    try:
        compacted.to_csv(tmp_path, index=False, encoding="utf-8", lineterminator="\n")
        os.replace(tmp_path, path)
    except Exception:
        with contextlib.suppress(Exception):
            tmp_path.unlink(missing_ok=True)
        return {"status": "write_error", "before_bytes": before_bytes, "after_bytes": before_bytes, "bytes_removed": 0, "rows_before": rows_before, "rows_after": rows_before}

    after_bytes = _file_size_bytes(path)
    rows_after = int(len(compacted.index))
    status = "ok" if after_bytes <= max(target_max_bytes, 1) else "ok_over_target"
    return {
        "status": status,
        "before_bytes": int(before_bytes),
        "after_bytes": int(after_bytes),
        "bytes_removed": int(max(before_bytes - after_bytes, 0)),
        "rows_before": int(rows_before),
        "rows_after": int(rows_after),
    }


def _protected_staged_run_ids() -> set[str]:
    protected: set[str] = set()
    for marker in (H_CYCLE_CURRENT_RUN_PATH, H_CYCLE_LAST_PUBLISH_RUN_PATH, H_CYCLE_LAST_COMPLETED_RUN_PATH):
        run_id = _read_first_line(marker)
        if _norm(run_id):
            protected.add(_norm(run_id))
    return protected


def _prune_h_staged_runs(now_utc: datetime) -> dict[str, int]:
    if not H_STAGED_ROOT.exists():
        return {
            "before_runs": 0,
            "after_runs": 0,
            "pruned_runs": 0,
            "pruned_bytes": 0,
            "ttl_days": int(H_STAGED_RETENTION_TTL_DAYS),
            "max_runs": int(H_STAGED_RETENTION_MAX_RUN_DIRS),
            "min_age_hours": int(H_STAGED_RETENTION_MIN_AGE_HOURS),
        }
    staged_dirs = [p for p in H_STAGED_ROOT.iterdir() if p.is_dir()]
    before_runs = len(staged_dirs)
    if not staged_dirs:
        return {
            "before_runs": 0,
            "after_runs": 0,
            "pruned_runs": 0,
            "pruned_bytes": 0,
            "ttl_days": int(H_STAGED_RETENTION_TTL_DAYS),
            "max_runs": int(H_STAGED_RETENTION_MAX_RUN_DIRS),
            "min_age_hours": int(H_STAGED_RETENTION_MIN_AGE_HOURS),
        }
    cutoff_ttl = now_utc - timedelta(days=H_STAGED_RETENTION_TTL_DAYS)
    cutoff_min_age = now_utc - timedelta(hours=H_STAGED_RETENTION_MIN_AGE_HOURS)
    protected = _protected_staged_run_ids()
    sorted_newest = sorted(
        staged_dirs,
        key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        reverse=True,
    )
    keep_newest = set(sorted_newest[:H_STAGED_RETENTION_MAX_RUN_DIRS])
    pruned_runs = 0
    pruned_bytes = 0
    prune_failures = 0
    samples: list[str] = []
    for path in sorted_newest[H_STAGED_RETENTION_MAX_RUN_DIRS :]:
        run_id = _norm(path.name)
        if run_id in protected:
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            continue
        # Never prune very recent staged directories that might still be settling.
        if mtime >= cutoff_min_age:
            keep_newest.add(path)
            continue
        # Keep newest-capped runs unless they are past TTL.
        if path in keep_newest and mtime >= cutoff_ttl:
            continue
        size = _dir_tree_size_bytes(path)
        if _rmtree_best_effort(path):
            pruned_runs += 1
            pruned_bytes += max(size, 0)
            if len(samples) < 3:
                samples.append(path.name)
        else:
            prune_failures += 1
    # TTL pass for old runs that still survived by count protection.
    for path in sorted_newest[: H_STAGED_RETENTION_MAX_RUN_DIRS]:
        run_id = _norm(path.name)
        if run_id in protected:
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            continue
        if mtime >= cutoff_ttl or mtime >= cutoff_min_age:
            continue
        size = _dir_tree_size_bytes(path)
        if _rmtree_best_effort(path):
            pruned_runs += 1
            pruned_bytes += max(size, 0)
            if len(samples) < 3:
                samples.append(path.name)
        else:
            prune_failures += 1
    after_runs = len([p for p in H_STAGED_ROOT.iterdir() if p.is_dir()])
    return {
        "before_runs": int(before_runs),
        "after_runs": int(after_runs),
        "pruned_runs": int(pruned_runs),
        "pruned_bytes": int(pruned_bytes),
        "prune_failures": int(prune_failures),
        "sample": samples,
        "ttl_days": int(H_STAGED_RETENTION_TTL_DAYS),
        "max_runs": int(H_STAGED_RETENTION_MAX_RUN_DIRS),
        "min_age_hours": int(H_STAGED_RETENTION_MIN_AGE_HOURS),
    }


def _prune_emergency_backups(now_utc: datetime) -> dict[str, int]:
    backup_roots = [p for p in OUT.glob("_emergency_backup_*") if p.is_dir()]
    before_dirs = len(backup_roots)
    pruned_dirs = 0
    pruned_bytes = 0
    recursion_pruned_dirs = 0
    recursion_pruned_bytes = 0
    prune_failures = 0
    recursion_prune_failures = 0
    samples: list[str] = []

    if H_EMERGENCY_BACKUP_RECURSION_CONTAIN_ENABLED:
        for root in backup_roots:
            nested = root / "out" / root.name
            if nested.exists() and nested.is_dir():
                size = _dir_tree_size_bytes(nested)
                if _rmtree_best_effort(nested):
                    recursion_pruned_dirs += 1
                    recursion_pruned_bytes += max(size, 0)
                    if len(samples) < 3:
                        samples.append(str(nested.relative_to(root)))
                else:
                    recursion_prune_failures += 1

    cutoff_ttl = now_utc - timedelta(days=H_EMERGENCY_BACKUP_TTL_DAYS)
    newest_first = sorted(
        [p for p in OUT.glob("_emergency_backup_*") if p.is_dir()],
        key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        reverse=True,
    )
    keep_set = set(newest_first[:H_EMERGENCY_BACKUP_MAX_DIRS])
    for path in newest_first[H_EMERGENCY_BACKUP_MAX_DIRS :]:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            continue
        if path in keep_set and mtime >= cutoff_ttl:
            continue
        size = _dir_tree_size_bytes(path)
        if _rmtree_best_effort(path):
            pruned_dirs += 1
            pruned_bytes += max(size, 0)
            if len(samples) < 3:
                samples.append(path.name)
        else:
            prune_failures += 1
    # TTL pass for any old roots (except newest retained root).
    for path in newest_first[: H_EMERGENCY_BACKUP_MAX_DIRS]:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            continue
        if mtime >= cutoff_ttl:
            continue
        size = _dir_tree_size_bytes(path)
        if _rmtree_best_effort(path):
            pruned_dirs += 1
            pruned_bytes += max(size, 0)
            if len(samples) < 3:
                samples.append(path.name)
        else:
            prune_failures += 1

    after_dirs = len([p for p in OUT.glob("_emergency_backup_*") if p.is_dir()])
    return {
        "before_dirs": int(before_dirs),
        "after_dirs": int(after_dirs),
        "pruned_dirs": int(pruned_dirs),
        "pruned_bytes": int(pruned_bytes),
        "recursion_pruned_dirs": int(recursion_pruned_dirs),
        "recursion_pruned_bytes": int(recursion_pruned_bytes),
        "recursion_prune_failures": int(recursion_prune_failures),
        "prune_failures": int(prune_failures),
        "sample": samples,
        "max_dirs": int(H_EMERGENCY_BACKUP_MAX_DIRS),
        "ttl_days": int(H_EMERGENCY_BACKUP_TTL_DAYS),
    }


def _prune_h_live_snapshots(now_utc: datetime) -> dict[str, int]:
    root = H_LIVE_DIR / "snapshots"
    if not root.exists():
        return {
            "before_dirs": 0,
            "after_dirs": 0,
            "pruned_dirs": 0,
            "pruned_bytes": 0,
            "prune_failures": 0,
            "ttl_days": int(H_LIVE_SNAPSHOTS_RETENTION_TTL_DAYS),
            "max_dirs": int(H_LIVE_SNAPSHOTS_RETENTION_MAX_DIRS),
            "sample": [],
        }
    dirs = [p for p in root.iterdir() if p.is_dir()]
    before_dirs = len(dirs)
    cutoff_ttl = now_utc - timedelta(days=H_LIVE_SNAPSHOTS_RETENTION_TTL_DAYS)
    cutoff_min_age = now_utc - timedelta(hours=H_LIVE_SNAPSHOTS_RETENTION_MIN_AGE_HOURS)
    ordered = sorted(dirs, key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
    keep_newest = set(ordered[:H_LIVE_SNAPSHOTS_RETENTION_MAX_DIRS])
    pruned_dirs = 0
    pruned_bytes = 0
    prune_failures = 0
    samples: list[str] = []
    before_bytes = _dir_tree_size_bytes(root)
    for path in ordered:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            continue
        if mtime >= cutoff_min_age:
            continue
        should_prune = (path not in keep_newest) or (mtime < cutoff_ttl)
        if not should_prune:
            continue
        size = _dir_tree_size_bytes(path)
        if _rmtree_best_effort(path):
            pruned_dirs += 1
            pruned_bytes += max(size, 0)
            if len(samples) < 3:
                samples.append(path.name)
        else:
            prune_failures += 1
    # Enforce total family byte cap by pruning oldest eligible snapshot dirs.
    family_bytes = _dir_tree_size_bytes(root)
    if family_bytes > H_LIVE_SNAPSHOTS_FAMILY_MAX_BYTES:
        remaining = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime if p.exists() else 0.0)
        for path in remaining:
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except Exception:
                continue
            if family_bytes <= H_LIVE_SNAPSHOTS_FAMILY_MAX_BYTES:
                break
            if mtime >= cutoff_min_age:
                continue
            size = _dir_tree_size_bytes(path)
            if _rmtree_best_effort(path):
                pruned_dirs += 1
                pruned_bytes += max(size, 0)
                family_bytes = max(family_bytes - max(size, 0), 0)
                if len(samples) < 3:
                    samples.append(path.name)
            else:
                prune_failures += 1
    after_dirs = len([p for p in root.iterdir() if p.is_dir()]) if root.exists() else 0
    after_bytes = _dir_tree_size_bytes(root) if root.exists() else 0
    return {
        "before_dirs": int(before_dirs),
        "after_dirs": int(after_dirs),
        "pruned_dirs": int(pruned_dirs),
        "pruned_bytes": int(pruned_bytes),
        "prune_failures": int(prune_failures),
        "before_bytes": int(before_bytes),
        "after_bytes": int(after_bytes),
        "family_max_bytes": int(H_LIVE_SNAPSHOTS_FAMILY_MAX_BYTES),
        "ttl_days": int(H_LIVE_SNAPSHOTS_RETENTION_TTL_DAYS),
        "max_dirs": int(H_LIVE_SNAPSHOTS_RETENTION_MAX_DIRS),
        "sample": samples,
    }


def _prune_tmp_publish_backups(now_utc: datetime) -> dict[str, int]:
    root = H_LIVE_DIR / "tmp_publish_backups"
    if not root.exists():
        return {
            "before_dirs": 0,
            "after_dirs": 0,
            "pruned_dirs": 0,
            "pruned_bytes": 0,
            "prune_failures": 0,
            "ttl_days": int(H_TMP_PUBLISH_BACKUPS_TTL_DAYS),
            "max_dirs": int(H_TMP_PUBLISH_BACKUPS_MAX_DIRS),
            "sample": [],
        }
    dirs = [p for p in root.iterdir() if p.is_dir()]
    before_dirs = len(dirs)
    cutoff_ttl = now_utc - timedelta(days=H_TMP_PUBLISH_BACKUPS_TTL_DAYS)
    ordered = sorted(dirs, key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
    keep_newest = set(ordered[:H_TMP_PUBLISH_BACKUPS_MAX_DIRS])
    pruned_dirs = 0
    pruned_bytes = 0
    prune_failures = 0
    samples: list[str] = []
    for path in ordered:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            continue
        should_prune = (path not in keep_newest) or (mtime < cutoff_ttl)
        if not should_prune:
            continue
        size = _dir_tree_size_bytes(path)
        if _rmtree_best_effort(path):
            pruned_dirs += 1
            pruned_bytes += max(size, 0)
            if len(samples) < 3:
                samples.append(path.name)
        else:
            prune_failures += 1
    after_dirs = len([p for p in root.iterdir() if p.is_dir()]) if root.exists() else 0
    return {
        "before_dirs": int(before_dirs),
        "after_dirs": int(after_dirs),
        "pruned_dirs": int(pruned_dirs),
        "pruned_bytes": int(pruned_bytes),
        "prune_failures": int(prune_failures),
        "ttl_days": int(H_TMP_PUBLISH_BACKUPS_TTL_DAYS),
        "max_dirs": int(H_TMP_PUBLISH_BACKUPS_MAX_DIRS),
        "sample": samples,
    }


def _log_family_members(base_path: Path) -> list[tuple[int, Path]]:
    members: list[tuple[int, Path]] = []
    if base_path.exists():
        members.append((0, base_path))
    pattern = f"{base_path.name}.*"
    for candidate in base_path.parent.glob(pattern):
        if not candidate.is_file():
            continue
        suffix = candidate.name[len(base_path.name) + 1 :]
        if not suffix.isdigit():
            continue
        try:
            idx = int(suffix)
        except Exception:
            continue
        if idx <= 0:
            continue
        members.append((idx, candidate))
    members.sort(key=lambda item: item[0])
    return members


def _log_family_snapshot(base_path: Path) -> dict[str, int]:
    members = _log_family_members(base_path)
    total_bytes = sum(_file_size_bytes(path) for _, path in members)
    return {
        "total_bytes": int(total_bytes),
        "total_files": int(len(members)),
        "rotated_files": int(max(len(members) - 1, 0)),
        "active_bytes": int(_file_size_bytes(base_path)),
    }


def _prune_log_family_budget(base_path: Path, *, max_total_bytes: int, max_total_files: int) -> dict[str, int]:
    before = _log_family_snapshot(base_path)
    max_files = max(int(max_total_files), 1)
    max_bytes = max(int(max_total_bytes), 1)
    pruned_files = 0
    pruned_bytes = 0

    members = _log_family_members(base_path)
    rotated_desc = sorted([item for item in members if item[0] > 0], key=lambda item: item[0], reverse=True)

    # Enforce file-count cap first by dropping oldest rotated files.
    while len(members) > max_files and rotated_desc:
        idx, path = rotated_desc.pop(0)
        pruned_bytes += _file_size_bytes(path)
        with contextlib.suppress(Exception):
            path.unlink(missing_ok=True)
        pruned_files += 1
        members = [item for item in members if item[1] != path]

    # Enforce retained-byte budget by dropping oldest rotated files only.
    total_bytes = sum(_file_size_bytes(path) for _, path in members)
    while total_bytes > max_bytes and rotated_desc:
        idx, path = rotated_desc.pop(0)
        pruned_bytes += _file_size_bytes(path)
        with contextlib.suppress(Exception):
            path.unlink(missing_ok=True)
        pruned_files += 1
        members = [item for item in members if item[1] != path]
        total_bytes = sum(_file_size_bytes(path2) for _, path2 in members)

    after = _log_family_snapshot(base_path)
    return {
        "before_total_bytes": int(before["total_bytes"]),
        "after_total_bytes": int(after["total_bytes"]),
        "before_total_files": int(before["total_files"]),
        "after_total_files": int(after["total_files"]),
        "before_active_bytes": int(before["active_bytes"]),
        "after_active_bytes": int(after["active_bytes"]),
        "pruned_files": int(pruned_files),
        "pruned_bytes": int(pruned_bytes),
    }


def _h_storage_snapshot() -> dict[str, object]:
    h_live = H_LIVE_DIR
    log_paths = [p for p in _log_target_paths() if p.exists()]
    log_paths += [p for p in [H_PHASE1_INTEL_PROGRESS_LOG_PATH, H_PARENT_TRACE_PATH, H_ATEXIT_TRACE_PATH] if p.exists()]
    unique_logs: list[Path] = []
    seen: set[Path] = set()
    for p in log_paths:
        if p in seen:
            continue
        seen.add(p)
        unique_logs.append(p)
    log_size_total = sum(_file_size_bytes(p) for p in unique_logs)
    tmp_files = [p for p in h_live.glob("tmp_h110_*/*") if p.is_file()]
    lock_archives = [p for p in LOCK_ARCHIVE_DIR.glob("H.lock.*") if p.is_file()]
    cycle_family = _log_family_snapshot(H_CYCLE_LOG_PATH)
    pricing_family = _log_family_snapshot(LOG_PATH)
    phase1_progress_family = _log_family_snapshot(H_PHASE1_INTEL_PROGRESS_LOG_PATH)
    parent_trace_family = _log_family_snapshot(H_PARENT_TRACE_PATH)
    home_time_mode_family = _log_family_snapshot(H_HOME_TIME_MODE_LOG_PATH)
    lock_events_family = _log_family_snapshot(PHASE1_LOCK_EVENTS_LOG_PATH)
    pilot_task_family = _log_family_snapshot(PHASE1_PILOT_TASK_LOG_PATH)
    h110_lifecycle_family = _log_family_snapshot(H110_SKU_LIFECYCLE_LOG_PATH)
    h110_decision_family = _log_family_snapshot(H110_SKU_DECISION_LOG_PATH)
    return {
        "utc": _ts(),
        "log_size_total_bytes": str(log_size_total),
        "tmp_h110_file_count": str(len(tmp_files)),
        "tmp_h110_size_bytes": str(sum(_file_size_bytes(p) for p in tmp_files)),
        "lock_archive_count": str(len(lock_archives)),
        "lock_archive_size_bytes": str(sum(_file_size_bytes(p) for p in lock_archives)),
        "h_cycle_log_bytes": str(_file_size_bytes(H_CYCLE_LOG_PATH)),
        "h_pricing_log_bytes": str(_file_size_bytes(LOG_PATH)),
        "h_cycle_log_family_bytes": str(cycle_family["total_bytes"]),
        "h_cycle_log_family_files": str(cycle_family["total_files"]),
        "h_pricing_log_family_bytes": str(pricing_family["total_bytes"]),
        "h_pricing_log_family_files": str(pricing_family["total_files"]),
        "phase1_progress_family_bytes": str(phase1_progress_family["total_bytes"]),
        "phase1_progress_family_files": str(phase1_progress_family["total_files"]),
        "h_parent_trace_family_bytes": str(parent_trace_family["total_bytes"]),
        "h_parent_trace_family_files": str(parent_trace_family["total_files"]),
        "h_home_time_mode_family_bytes": str(home_time_mode_family["total_bytes"]),
        "h_home_time_mode_family_files": str(home_time_mode_family["total_files"]),
        "phase1_lock_events_family_bytes": str(lock_events_family["total_bytes"]),
        "phase1_lock_events_family_files": str(lock_events_family["total_files"]),
        "phase1_pilot_task_family_bytes": str(pilot_task_family["total_bytes"]),
        "phase1_pilot_task_family_files": str(pilot_task_family["total_files"]),
        "h110_lifecycle_family_bytes": str(h110_lifecycle_family["total_bytes"]),
        "h110_lifecycle_family_files": str(h110_lifecycle_family["total_files"]),
        "h110_decision_family_bytes": str(h110_decision_family["total_bytes"]),
        "h110_decision_family_files": str(h110_decision_family["total_files"]),
        "phase1_progress_log_bytes": str(_file_size_bytes(H_PHASE1_INTEL_PROGRESS_LOG_PATH)),
    }


def _cleanup_h_live_artifacts() -> dict[str, str]:
    now_utc = _utc_now()
    tmp_cutoff = now_utc - timedelta(days=H_SELF_CLEAN_TMP_TTL_DAYS)
    lock_cutoff = now_utc - timedelta(days=H_SELF_CLEAN_LOCK_ARCHIVE_TTL_DAYS)
    removed_tmp = 0
    removed_tmp_bytes = 0
    removed_lock = 0
    removed_lock_bytes = 0
    removed_home_time_files = 0
    removed_home_time_bytes = 0
    home_time_diagnostics_before = 0
    home_time_diagnostics_after = 0
    forced_home_time_diagnostic_pruned_files = 0
    forced_home_time_diagnostic_pruned_bytes = 0
    staged_prune = _prune_h_staged_runs(now_utc)
    emergency_prune = _prune_emergency_backups(now_utc)
    snapshots_prune = _prune_h_live_snapshots(now_utc)
    tmp_publish_prune = _prune_tmp_publish_backups(now_utc)
    floor_trace_compact = _compact_csv_latest_per_key(
        path=H_FLOOR_TRACE_PATH,
        key_col="sku",
        ts_col="asof_utc",
        trigger_bytes=H_FLOOR_TRACE_COMPACT_TRIGGER_BYTES,
        target_max_bytes=H_FLOOR_TRACE_TARGET_MAX_BYTES,
    )
    sku_temp_compact = _compact_csv_latest_per_key(
        path=OUT / "sku_temp_floor_snapshot.csv",
        key_col="sku",
        ts_col="asof_utc",
        trigger_bytes=H_SKU_TEMP_FLOOR_COMPACT_TRIGGER_BYTES,
        target_max_bytes=H_SKU_TEMP_FLOOR_TARGET_MAX_BYTES,
    )
    api_family_before = _log_family_snapshot(H_API_CALL_LOG_PATH)
    api_rotated = 1 if _rotate_log_file(H_API_CALL_LOG_PATH, max_bytes=H_API_CALL_LOG_ROTATE_MAX_BYTES, max_files=H_API_CALL_LOG_ROTATE_MAX_FILES) else 0
    api_family_budget = _prune_log_family_budget(
        H_API_CALL_LOG_PATH,
        max_total_bytes=H_API_CALL_LOG_FAMILY_MAX_BYTES,
        max_total_files=H_API_CALL_LOG_ROTATE_MAX_FILES + 1,
    )
    api_family_after = _log_family_snapshot(H_API_CALL_LOG_PATH)

    for path in H_LIVE_DIR.glob("tmp_h110_*/*"):
        if not path.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime >= tmp_cutoff:
                continue
            size = int(path.stat().st_size)
            path.unlink(missing_ok=True)
            removed_tmp += 1
            removed_tmp_bytes += max(size, 0)
        except Exception:
            continue
    for tmp_dir in H_LIVE_DIR.glob("tmp_h110_*"):
        if not tmp_dir.is_dir():
            continue
        with contextlib.suppress(Exception):
            if not any(tmp_dir.iterdir()):
                tmp_dir.rmdir()

    lock_candidates: list[Path] = [p for p in LOCK_ARCHIVE_DIR.glob("H.lock.*") if p.is_file()]
    lock_candidates_sorted = sorted(
        lock_candidates,
        key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        reverse=True,
    )
    keep_set = set(lock_candidates_sorted[:H_SELF_CLEAN_LOCK_ARCHIVE_MAX_FILES])
    for path in lock_candidates:
        if path in keep_set:
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime >= lock_cutoff:
                continue
            size = int(path.stat().st_size)
            path.unlink(missing_ok=True)
            removed_lock += 1
            removed_lock_bytes += max(size, 0)
        except Exception:
            continue

    try:
        proc = subprocess.run(
            [sys.executable, str(HOME_TIME_ARTIFACT_RETENTION_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=H_SELF_CLEAN_HOME_TIME_RETENTION_TIMEOUT_SECONDS,
            check=False,
        )
        stdout_norm = _norm(proc.stdout)
        if proc.returncode == 0 and stdout_norm:
            parsed = json.loads(stdout_norm)
            if isinstance(parsed, dict):
                for key in ("home_time_reports", "home_time_diagnostics", "home_time_remediations", "home_time_safety_snapshots"):
                    group = parsed.get(key, {})
                    if not isinstance(group, dict):
                        continue
                    removed_home_time_files += int(float(group.get("removed_files", 0) or 0))
                    removed_home_time_bytes += int(float(group.get("removed_bytes", 0) or 0))
        else:
            _log(
                "cleanup_h_live_storage_home_time_retention_error "
                f"rc={proc.returncode} "
                f"stdout={_norm(proc.stdout)[:200]} "
                f"stderr={_norm(proc.stderr)[:200]}"
            )
    except Exception as exc:
        _log(
            "cleanup_h_live_storage_home_time_retention_error "
            f"exception={type(exc).__name__}:{_norm(exc)}"
        )

    diagnostic_files = sorted(
        [p for p in H_LIVE_DIR.glob("H_home_time_*diagnostic*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
    )
    home_time_diagnostics_before = len(diagnostic_files)
    if home_time_diagnostics_before > H_HOME_TIME_DIAGNOSTIC_MAX_FILES:
        overflow = home_time_diagnostics_before - H_HOME_TIME_DIAGNOSTIC_MAX_FILES
        for path in diagnostic_files[:overflow]:
            try:
                size = int(path.stat().st_size)
                path.unlink(missing_ok=True)
                forced_home_time_diagnostic_pruned_files += 1
                forced_home_time_diagnostic_pruned_bytes += max(size, 0)
            except Exception:
                continue
        removed_home_time_files += forced_home_time_diagnostic_pruned_files
        removed_home_time_bytes += forced_home_time_diagnostic_pruned_bytes
    home_time_diagnostics_after = len(
        [p for p in H_LIVE_DIR.glob("H_home_time_*diagnostic*.json") if p.is_file()]
    )

    ledger_entries: list[dict[str, object]] = []
    if int(staged_prune.get("pruned_runs", 0)) > 0 or int(staged_prune.get("prune_failures", 0)) > 0:
        ledger_entries.append(
            {
                "policy": "h_staged_retention",
                "target": str(H_STAGED_ROOT),
                "action": "deleted",
                "reason": (
                    f"age_ttl_days={staged_prune.get('ttl_days', int(H_STAGED_RETENTION_TTL_DAYS))};"
                    f"count_cap={staged_prune.get('max_runs', H_STAGED_RETENTION_MAX_RUN_DIRS)}"
                ),
                "file_count": int(staged_prune.get("pruned_runs", 0)),
                "bytes_removed": int(staged_prune.get("pruned_bytes", 0)),
                "status": "ok" if int(staged_prune.get("prune_failures", 0)) == 0 else "partial",
                "sample": staged_prune.get("sample", []),
            }
        )
    if int(snapshots_prune.get("pruned_dirs", 0)) > 0 or int(snapshots_prune.get("prune_failures", 0)) > 0:
        ledger_entries.append(
            {
                "policy": "h_live_snapshots_retention",
                "target": str(H_LIVE_DIR / "snapshots"),
                "action": "deleted",
                "reason": (
                    f"age_ttl_days={snapshots_prune.get('ttl_days', int(H_LIVE_SNAPSHOTS_RETENTION_TTL_DAYS))};"
                    f"count_cap={snapshots_prune.get('max_dirs', H_LIVE_SNAPSHOTS_RETENTION_MAX_DIRS)}"
                ),
                "file_count": int(snapshots_prune.get("pruned_dirs", 0)),
                "bytes_removed": int(snapshots_prune.get("pruned_bytes", 0)),
                "status": "ok" if int(snapshots_prune.get("prune_failures", 0)) == 0 else "partial",
                "sample": snapshots_prune.get("sample", []),
            }
        )
    if int(tmp_publish_prune.get("pruned_dirs", 0)) > 0 or int(tmp_publish_prune.get("prune_failures", 0)) > 0:
        ledger_entries.append(
            {
                "policy": "h_tmp_publish_backups_retention",
                "target": str(H_LIVE_DIR / "tmp_publish_backups"),
                "action": "deleted",
                "reason": (
                    f"age_ttl_days={tmp_publish_prune.get('ttl_days', int(H_TMP_PUBLISH_BACKUPS_TTL_DAYS))};"
                    f"count_cap={tmp_publish_prune.get('max_dirs', H_TMP_PUBLISH_BACKUPS_MAX_DIRS)}"
                ),
                "file_count": int(tmp_publish_prune.get("pruned_dirs", 0)),
                "bytes_removed": int(tmp_publish_prune.get("pruned_bytes", 0)),
                "status": "ok" if int(tmp_publish_prune.get("prune_failures", 0)) == 0 else "partial",
                "sample": tmp_publish_prune.get("sample", []),
            }
        )
    if (
        int(emergency_prune.get("pruned_dirs", 0)) > 0
        or int(emergency_prune.get("recursion_pruned_dirs", 0)) > 0
        or int(emergency_prune.get("prune_failures", 0)) > 0
        or int(emergency_prune.get("recursion_prune_failures", 0)) > 0
    ):
        ledger_entries.append(
            {
                "policy": "h_emergency_backup_retention",
                "target": str(OUT / "_emergency_backup_*"),
                "action": "deleted",
                "reason": (
                    f"age_ttl_days={emergency_prune.get('ttl_days', int(H_EMERGENCY_BACKUP_TTL_DAYS))};"
                    f"count_cap={emergency_prune.get('max_dirs', H_EMERGENCY_BACKUP_MAX_DIRS)};"
                    f"recursion_containment={1 if H_EMERGENCY_BACKUP_RECURSION_CONTAIN_ENABLED else 0}"
                ),
                "file_count": int(emergency_prune.get("pruned_dirs", 0)) + int(emergency_prune.get("recursion_pruned_dirs", 0)),
                "bytes_removed": int(emergency_prune.get("pruned_bytes", 0)) + int(emergency_prune.get("recursion_pruned_bytes", 0)),
                "status": (
                    "ok"
                    if (int(emergency_prune.get("prune_failures", 0)) + int(emergency_prune.get("recursion_prune_failures", 0))) == 0
                    else "partial"
                ),
                "sample": emergency_prune.get("sample", []),
            }
        )
    if int(floor_trace_compact.get("bytes_removed", 0)) > 0:
        ledger_entries.append(
            {
                "policy": "h_floor_truth_trace_compact",
                "target": str(H_FLOOR_TRACE_PATH),
                "action": "compacted",
                "reason": f"trigger_bytes={H_FLOOR_TRACE_COMPACT_TRIGGER_BYTES};target_max_bytes={H_FLOOR_TRACE_TARGET_MAX_BYTES}",
                "file_count": 1,
                "bytes_removed": int(floor_trace_compact.get("bytes_removed", 0)),
                "status": _norm(floor_trace_compact.get("status", "")) or "ok",
                "sample": [],
            }
        )
    if int(sku_temp_compact.get("bytes_removed", 0)) > 0:
        ledger_entries.append(
            {
                "policy": "h_sku_temp_floor_snapshot_compact",
                "target": str(OUT / "sku_temp_floor_snapshot.csv"),
                "action": "compacted",
                "reason": f"trigger_bytes={H_SKU_TEMP_FLOOR_COMPACT_TRIGGER_BYTES};target_max_bytes={H_SKU_TEMP_FLOOR_TARGET_MAX_BYTES}",
                "file_count": 1,
                "bytes_removed": int(sku_temp_compact.get("bytes_removed", 0)),
                "status": _norm(sku_temp_compact.get("status", "")) or "ok",
                "sample": [],
            }
        )
    if int(api_rotated) > 0 or int(api_family_budget.get("pruned_files", 0)) > 0:
        ledger_entries.append(
            {
                "policy": "h_api_call_log_retention",
                "target": str(H_API_CALL_LOG_PATH),
                "action": "rotated_pruned",
                "reason": f"rotate_max_bytes={H_API_CALL_LOG_ROTATE_MAX_BYTES};family_max_bytes={H_API_CALL_LOG_FAMILY_MAX_BYTES}",
                "file_count": int(api_rotated) + int(api_family_budget.get("pruned_files", 0)),
                "bytes_removed": int(api_family_budget.get("pruned_bytes", 0)),
                "status": "ok",
                "sample": [],
            }
        )
    ledger_stats = _record_cleanup_ledger_entries(ledger_entries)

    return {
        "removed_tmp_files": str(removed_tmp),
        "removed_tmp_bytes": str(removed_tmp_bytes),
        "removed_lock_archive_files": str(removed_lock),
        "removed_lock_archive_bytes": str(removed_lock_bytes),
        "removed_home_time_files": str(removed_home_time_files),
        "removed_home_time_bytes": str(removed_home_time_bytes),
        "home_time_diagnostics_cap": str(H_HOME_TIME_DIAGNOSTIC_MAX_FILES),
        "home_time_diagnostics_before": str(home_time_diagnostics_before),
        "home_time_diagnostics_after": str(home_time_diagnostics_after),
        "forced_home_time_diagnostic_pruned_files": str(forced_home_time_diagnostic_pruned_files),
        "forced_home_time_diagnostic_pruned_bytes": str(forced_home_time_diagnostic_pruned_bytes),
        "staged_runs_before": str(staged_prune.get("before_runs", 0)),
        "staged_runs_after": str(staged_prune.get("after_runs", 0)),
        "staged_runs_pruned": str(staged_prune.get("pruned_runs", 0)),
        "staged_pruned_bytes": str(staged_prune.get("pruned_bytes", 0)),
        "staged_prune_failures": str(staged_prune.get("prune_failures", 0)),
        "staged_max_runs": str(staged_prune.get("max_runs", H_STAGED_RETENTION_MAX_RUN_DIRS)),
        "staged_ttl_days": str(staged_prune.get("ttl_days", int(H_STAGED_RETENTION_TTL_DAYS))),
        "staged_min_age_hours": str(staged_prune.get("min_age_hours", int(H_STAGED_RETENTION_MIN_AGE_HOURS))),
        "live_snapshots_dirs_before": str(snapshots_prune.get("before_dirs", 0)),
        "live_snapshots_dirs_after": str(snapshots_prune.get("after_dirs", 0)),
        "live_snapshots_dirs_pruned": str(snapshots_prune.get("pruned_dirs", 0)),
        "live_snapshots_pruned_bytes": str(snapshots_prune.get("pruned_bytes", 0)),
        "live_snapshots_prune_failures": str(snapshots_prune.get("prune_failures", 0)),
        "live_snapshots_before_bytes": str(snapshots_prune.get("before_bytes", 0)),
        "live_snapshots_after_bytes": str(snapshots_prune.get("after_bytes", 0)),
        "live_snapshots_family_max_bytes": str(snapshots_prune.get("family_max_bytes", H_LIVE_SNAPSHOTS_FAMILY_MAX_BYTES)),
        "live_snapshots_ttl_days": str(snapshots_prune.get("ttl_days", int(H_LIVE_SNAPSHOTS_RETENTION_TTL_DAYS))),
        "live_snapshots_max_dirs": str(snapshots_prune.get("max_dirs", H_LIVE_SNAPSHOTS_RETENTION_MAX_DIRS)),
        "tmp_publish_dirs_before": str(tmp_publish_prune.get("before_dirs", 0)),
        "tmp_publish_dirs_after": str(tmp_publish_prune.get("after_dirs", 0)),
        "tmp_publish_dirs_pruned": str(tmp_publish_prune.get("pruned_dirs", 0)),
        "tmp_publish_pruned_bytes": str(tmp_publish_prune.get("pruned_bytes", 0)),
        "tmp_publish_prune_failures": str(tmp_publish_prune.get("prune_failures", 0)),
        "tmp_publish_ttl_days": str(tmp_publish_prune.get("ttl_days", int(H_TMP_PUBLISH_BACKUPS_TTL_DAYS))),
        "tmp_publish_max_dirs": str(tmp_publish_prune.get("max_dirs", H_TMP_PUBLISH_BACKUPS_MAX_DIRS)),
        "emergency_dirs_before": str(emergency_prune.get("before_dirs", 0)),
        "emergency_dirs_after": str(emergency_prune.get("after_dirs", 0)),
        "emergency_dirs_pruned": str(emergency_prune.get("pruned_dirs", 0)),
        "emergency_pruned_bytes": str(emergency_prune.get("pruned_bytes", 0)),
        "emergency_recursion_pruned_dirs": str(emergency_prune.get("recursion_pruned_dirs", 0)),
        "emergency_recursion_pruned_bytes": str(emergency_prune.get("recursion_pruned_bytes", 0)),
        "emergency_recursion_prune_failures": str(emergency_prune.get("recursion_prune_failures", 0)),
        "emergency_prune_failures": str(emergency_prune.get("prune_failures", 0)),
        "emergency_max_dirs": str(emergency_prune.get("max_dirs", H_EMERGENCY_BACKUP_MAX_DIRS)),
        "emergency_ttl_days": str(emergency_prune.get("ttl_days", int(H_EMERGENCY_BACKUP_TTL_DAYS))),
        "h_floor_trace_compact_status": str(floor_trace_compact.get("status", "")),
        "h_floor_trace_before_bytes": str(floor_trace_compact.get("before_bytes", 0)),
        "h_floor_trace_after_bytes": str(floor_trace_compact.get("after_bytes", 0)),
        "h_floor_trace_bytes_removed": str(floor_trace_compact.get("bytes_removed", 0)),
        "h_floor_trace_rows_before": str(floor_trace_compact.get("rows_before", 0)),
        "h_floor_trace_rows_after": str(floor_trace_compact.get("rows_after", 0)),
        "h_sku_temp_floor_compact_status": str(sku_temp_compact.get("status", "")),
        "h_sku_temp_floor_before_bytes": str(sku_temp_compact.get("before_bytes", 0)),
        "h_sku_temp_floor_after_bytes": str(sku_temp_compact.get("after_bytes", 0)),
        "h_sku_temp_floor_bytes_removed": str(sku_temp_compact.get("bytes_removed", 0)),
        "h_sku_temp_floor_rows_before": str(sku_temp_compact.get("rows_before", 0)),
        "h_sku_temp_floor_rows_after": str(sku_temp_compact.get("rows_after", 0)),
        "api_call_log_before_bytes": str(api_family_before.get("total_bytes", 0)),
        "api_call_log_after_bytes": str(api_family_after.get("total_bytes", 0)),
        "api_call_log_before_files": str(api_family_before.get("total_files", 0)),
        "api_call_log_after_files": str(api_family_after.get("total_files", 0)),
        "api_call_log_rotated": str(api_rotated),
        "api_call_log_pruned_files": str(api_family_budget.get("pruned_files", 0)),
        "api_call_log_pruned_bytes": str(api_family_budget.get("pruned_bytes", 0)),
        "api_call_log_family_max_bytes": str(H_API_CALL_LOG_FAMILY_MAX_BYTES),
        "cleanup_ledger_path": str(H_CLEANUP_LEDGER_PATH),
        "cleanup_ledger_entries_written": str(ledger_stats.get("ledger_entries_written", 0)),
        "cleanup_ledger_before_bytes": str(ledger_stats.get("ledger_before_bytes", 0)),
        "cleanup_ledger_after_bytes": str(ledger_stats.get("ledger_after_bytes", 0)),
        "cleanup_ledger_rotated": str(ledger_stats.get("ledger_rotated", 0)),
        "cleanup_ledger_family_budget_bytes": str(H_CLEANUP_LEDGER_FAMILY_MAX_BYTES),
    }


def _run_h_live_self_cleanup() -> None:
    if not H_ENABLE_SELF_CLEANING:
        return
    before = _h_storage_snapshot()
    rotated = 0
    for path in _log_target_paths():
        if _rotate_log_file(path, max_bytes=H_LOG_ROTATE_MAX_BYTES, max_files=H_LOG_ROTATE_MAX_FILES):
            rotated += 1
    for path in (H_ATEXIT_TRACE_PATH,):
        if _rotate_log_file(path, max_bytes=H_PROGRESS_ROTATE_MAX_BYTES, max_files=H_PROGRESS_ROTATE_MAX_FILES):
            rotated += 1
    retained_family_targets: list[tuple[Path, int, int]] = [
        (H_PHASE1_INTEL_PROGRESS_LOG_PATH, H_PHASE1_PROGRESS_ROTATE_MAX_BYTES, H_PHASE1_PROGRESS_ROTATE_MAX_FILES),
        (H_PARENT_TRACE_PATH, H_PARENT_TRACE_ROTATE_MAX_BYTES, H_PARENT_TRACE_ROTATE_MAX_FILES),
        (H_HOME_TIME_MODE_LOG_PATH, H_HOME_TIME_MODE_ROTATE_MAX_BYTES, H_HOME_TIME_MODE_ROTATE_MAX_FILES),
        (PHASE1_LOCK_EVENTS_LOG_PATH, PHASE1_LOCK_EVENTS_ROTATE_MAX_BYTES, PHASE1_LOCK_EVENTS_ROTATE_MAX_FILES),
        (PHASE1_PILOT_TASK_LOG_PATH, PHASE1_PILOT_TASK_ROTATE_MAX_BYTES, PHASE1_PILOT_TASK_ROTATE_MAX_FILES),
        (H110_SKU_LIFECYCLE_LOG_PATH, H110_LIFECYCLE_ROTATE_MAX_BYTES, H110_LIFECYCLE_ROTATE_MAX_FILES),
        (H110_SKU_DECISION_LOG_PATH, H110_DECISION_ROTATE_MAX_BYTES, H110_DECISION_ROTATE_MAX_FILES),
    ]
    for path, max_bytes, max_files in retained_family_targets:
        if _rotate_log_file(path, max_bytes=max_bytes, max_files=max_files):
            rotated += 1

    family_targets: list[tuple[str, Path, int, int]] = [
        ("h_cycle", H_CYCLE_LOG_PATH, H_CYCLE_LOG_FAMILY_MAX_BYTES, H_LOG_ROTATE_MAX_FILES + 1),
        ("h_pricing", LOG_PATH, H_PRICING_LOG_FAMILY_MAX_BYTES, H_LOG_ROTATE_MAX_FILES + 1),
        ("phase1_progress", H_PHASE1_INTEL_PROGRESS_LOG_PATH, H_PHASE1_PROGRESS_FAMILY_MAX_BYTES, H_PHASE1_PROGRESS_ROTATE_MAX_FILES + 1),
        ("h_parent_trace", H_PARENT_TRACE_PATH, H_PARENT_TRACE_FAMILY_MAX_BYTES, H_PARENT_TRACE_ROTATE_MAX_FILES + 1),
        ("h_home_time_mode", H_HOME_TIME_MODE_LOG_PATH, H_HOME_TIME_MODE_FAMILY_MAX_BYTES, H_HOME_TIME_MODE_ROTATE_MAX_FILES + 1),
        ("phase1_lock_events", PHASE1_LOCK_EVENTS_LOG_PATH, PHASE1_LOCK_EVENTS_FAMILY_MAX_BYTES, PHASE1_LOCK_EVENTS_ROTATE_MAX_FILES + 1),
        ("phase1_pilot_task", PHASE1_PILOT_TASK_LOG_PATH, PHASE1_PILOT_TASK_FAMILY_MAX_BYTES, PHASE1_PILOT_TASK_ROTATE_MAX_FILES + 1),
        ("h110_lifecycle", H110_SKU_LIFECYCLE_LOG_PATH, H110_LIFECYCLE_FAMILY_MAX_BYTES, H110_LIFECYCLE_ROTATE_MAX_FILES + 1),
        ("h110_decision", H110_SKU_DECISION_LOG_PATH, H110_DECISION_FAMILY_MAX_BYTES, H110_DECISION_ROTATE_MAX_FILES + 1),
    ]
    family_budget_metrics: dict[str, dict[str, int]] = {}
    seen_family_paths: set[Path] = set()
    for family_name, family_path, family_budget_bytes, family_max_files in family_targets:
        if family_path in seen_family_paths:
            continue
        seen_family_paths.add(family_path)
        family_budget_metrics[family_name] = _prune_log_family_budget(
            family_path,
            max_total_bytes=family_budget_bytes,
            max_total_files=family_max_files,
        )
    cleanup = _cleanup_h_live_artifacts()
    after = _h_storage_snapshot()
    try:
        cycle_budget = family_budget_metrics.get("h_cycle", {})
        pricing_budget = family_budget_metrics.get("h_pricing", {})
        phase1_progress_budget = family_budget_metrics.get("phase1_progress", {})
        parent_trace_budget = family_budget_metrics.get("h_parent_trace", {})
        home_time_mode_budget = family_budget_metrics.get("h_home_time_mode", {})
        lock_events_budget = family_budget_metrics.get("phase1_lock_events", {})
        pilot_task_budget = family_budget_metrics.get("phase1_pilot_task", {})
        h110_lifecycle_budget = family_budget_metrics.get("h110_lifecycle", {})
        h110_decision_budget = family_budget_metrics.get("h110_decision", {})
        _log(
            "cleanup_h_live_storage "
            f"rotated_files={rotated} "
            f"removed_tmp_files={cleanup.get('removed_tmp_files', '0')} "
            f"removed_tmp_bytes={cleanup.get('removed_tmp_bytes', '0')} "
            f"removed_lock_archive_files={cleanup.get('removed_lock_archive_files', '0')} "
            f"removed_lock_archive_bytes={cleanup.get('removed_lock_archive_bytes', '0')} "
            f"removed_home_time_files={cleanup.get('removed_home_time_files', '0')} "
            f"removed_home_time_bytes={cleanup.get('removed_home_time_bytes', '0')} "
            f"home_time_diagnostics_cap={cleanup.get('home_time_diagnostics_cap', '0')} "
            f"home_time_diagnostics_before={cleanup.get('home_time_diagnostics_before', '0')} "
            f"home_time_diagnostics_after={cleanup.get('home_time_diagnostics_after', '0')} "
            f"forced_home_time_diagnostic_pruned_files={cleanup.get('forced_home_time_diagnostic_pruned_files', '0')} "
            f"forced_home_time_diagnostic_pruned_bytes={cleanup.get('forced_home_time_diagnostic_pruned_bytes', '0')} "
            f"staged_runs_before={cleanup.get('staged_runs_before', '0')} "
            f"staged_runs_after={cleanup.get('staged_runs_after', '0')} "
            f"staged_runs_pruned={cleanup.get('staged_runs_pruned', '0')} "
            f"staged_pruned_bytes={cleanup.get('staged_pruned_bytes', '0')} "
            f"staged_prune_failures={cleanup.get('staged_prune_failures', '0')} "
            f"staged_max_runs={cleanup.get('staged_max_runs', '0')} "
            f"staged_ttl_days={cleanup.get('staged_ttl_days', '0')} "
            f"staged_min_age_hours={cleanup.get('staged_min_age_hours', '0')} "
            f"live_snapshots_dirs_before={cleanup.get('live_snapshots_dirs_before', '0')} "
            f"live_snapshots_dirs_after={cleanup.get('live_snapshots_dirs_after', '0')} "
            f"live_snapshots_dirs_pruned={cleanup.get('live_snapshots_dirs_pruned', '0')} "
            f"live_snapshots_pruned_bytes={cleanup.get('live_snapshots_pruned_bytes', '0')} "
            f"live_snapshots_prune_failures={cleanup.get('live_snapshots_prune_failures', '0')} "
            f"live_snapshots_before_bytes={cleanup.get('live_snapshots_before_bytes', '0')} "
            f"live_snapshots_after_bytes={cleanup.get('live_snapshots_after_bytes', '0')} "
            f"live_snapshots_family_max_bytes={cleanup.get('live_snapshots_family_max_bytes', '0')} "
            f"live_snapshots_ttl_days={cleanup.get('live_snapshots_ttl_days', '0')} "
            f"live_snapshots_max_dirs={cleanup.get('live_snapshots_max_dirs', '0')} "
            f"tmp_publish_dirs_before={cleanup.get('tmp_publish_dirs_before', '0')} "
            f"tmp_publish_dirs_after={cleanup.get('tmp_publish_dirs_after', '0')} "
            f"tmp_publish_dirs_pruned={cleanup.get('tmp_publish_dirs_pruned', '0')} "
            f"tmp_publish_pruned_bytes={cleanup.get('tmp_publish_pruned_bytes', '0')} "
            f"tmp_publish_prune_failures={cleanup.get('tmp_publish_prune_failures', '0')} "
            f"tmp_publish_ttl_days={cleanup.get('tmp_publish_ttl_days', '0')} "
            f"tmp_publish_max_dirs={cleanup.get('tmp_publish_max_dirs', '0')} "
            f"emergency_dirs_before={cleanup.get('emergency_dirs_before', '0')} "
            f"emergency_dirs_after={cleanup.get('emergency_dirs_after', '0')} "
            f"emergency_dirs_pruned={cleanup.get('emergency_dirs_pruned', '0')} "
            f"emergency_pruned_bytes={cleanup.get('emergency_pruned_bytes', '0')} "
            f"emergency_recursion_pruned_dirs={cleanup.get('emergency_recursion_pruned_dirs', '0')} "
            f"emergency_recursion_pruned_bytes={cleanup.get('emergency_recursion_pruned_bytes', '0')} "
            f"emergency_recursion_prune_failures={cleanup.get('emergency_recursion_prune_failures', '0')} "
            f"emergency_prune_failures={cleanup.get('emergency_prune_failures', '0')} "
            f"emergency_max_dirs={cleanup.get('emergency_max_dirs', '0')} "
            f"emergency_ttl_days={cleanup.get('emergency_ttl_days', '0')} "
            f"h_floor_trace_compact_status={cleanup.get('h_floor_trace_compact_status', '')} "
            f"h_floor_trace_before_bytes={cleanup.get('h_floor_trace_before_bytes', '0')} "
            f"h_floor_trace_after_bytes={cleanup.get('h_floor_trace_after_bytes', '0')} "
            f"h_floor_trace_bytes_removed={cleanup.get('h_floor_trace_bytes_removed', '0')} "
            f"h_floor_trace_rows_before={cleanup.get('h_floor_trace_rows_before', '0')} "
            f"h_floor_trace_rows_after={cleanup.get('h_floor_trace_rows_after', '0')} "
            f"h_sku_temp_floor_compact_status={cleanup.get('h_sku_temp_floor_compact_status', '')} "
            f"h_sku_temp_floor_before_bytes={cleanup.get('h_sku_temp_floor_before_bytes', '0')} "
            f"h_sku_temp_floor_after_bytes={cleanup.get('h_sku_temp_floor_after_bytes', '0')} "
            f"h_sku_temp_floor_bytes_removed={cleanup.get('h_sku_temp_floor_bytes_removed', '0')} "
            f"h_sku_temp_floor_rows_before={cleanup.get('h_sku_temp_floor_rows_before', '0')} "
            f"h_sku_temp_floor_rows_after={cleanup.get('h_sku_temp_floor_rows_after', '0')} "
            f"api_call_log_before_bytes={cleanup.get('api_call_log_before_bytes', '0')} "
            f"api_call_log_after_bytes={cleanup.get('api_call_log_after_bytes', '0')} "
            f"api_call_log_before_files={cleanup.get('api_call_log_before_files', '0')} "
            f"api_call_log_after_files={cleanup.get('api_call_log_after_files', '0')} "
            f"api_call_log_rotated={cleanup.get('api_call_log_rotated', '0')} "
            f"api_call_log_pruned_files={cleanup.get('api_call_log_pruned_files', '0')} "
            f"api_call_log_pruned_bytes={cleanup.get('api_call_log_pruned_bytes', '0')} "
            f"api_call_log_family_max_bytes={cleanup.get('api_call_log_family_max_bytes', '0')} "
            f"cleanup_ledger_path={cleanup.get('cleanup_ledger_path', '')} "
            f"cleanup_ledger_entries_written={cleanup.get('cleanup_ledger_entries_written', '0')} "
            f"cleanup_ledger_before_bytes={cleanup.get('cleanup_ledger_before_bytes', '0')} "
            f"cleanup_ledger_after_bytes={cleanup.get('cleanup_ledger_after_bytes', '0')} "
            f"cleanup_ledger_rotated={cleanup.get('cleanup_ledger_rotated', '0')} "
            f"cleanup_ledger_family_budget_bytes={cleanup.get('cleanup_ledger_family_budget_bytes', '0')} "
            f"h_cycle_family_before_bytes={cycle_budget.get('before_total_bytes', 0)} "
            f"h_cycle_family_after_bytes={cycle_budget.get('after_total_bytes', 0)} "
            f"h_cycle_family_before_files={cycle_budget.get('before_total_files', 0)} "
            f"h_cycle_family_after_files={cycle_budget.get('after_total_files', 0)} "
            f"h_cycle_family_pruned_files={cycle_budget.get('pruned_files', 0)} "
            f"h_cycle_family_pruned_bytes={cycle_budget.get('pruned_bytes', 0)} "
            f"h_cycle_family_budget_bytes={H_CYCLE_LOG_FAMILY_MAX_BYTES} "
            f"h_pricing_family_before_bytes={pricing_budget.get('before_total_bytes', 0)} "
            f"h_pricing_family_after_bytes={pricing_budget.get('after_total_bytes', 0)} "
            f"h_pricing_family_before_files={pricing_budget.get('before_total_files', 0)} "
            f"h_pricing_family_after_files={pricing_budget.get('after_total_files', 0)} "
            f"h_pricing_family_pruned_files={pricing_budget.get('pruned_files', 0)} "
            f"h_pricing_family_pruned_bytes={pricing_budget.get('pruned_bytes', 0)} "
            f"h_pricing_family_budget_bytes={H_PRICING_LOG_FAMILY_MAX_BYTES} "
            f"phase1_progress_family_before_bytes={phase1_progress_budget.get('before_total_bytes', 0)} "
            f"phase1_progress_family_after_bytes={phase1_progress_budget.get('after_total_bytes', 0)} "
            f"phase1_progress_family_before_files={phase1_progress_budget.get('before_total_files', 0)} "
            f"phase1_progress_family_after_files={phase1_progress_budget.get('after_total_files', 0)} "
            f"phase1_progress_family_pruned_files={phase1_progress_budget.get('pruned_files', 0)} "
            f"phase1_progress_family_pruned_bytes={phase1_progress_budget.get('pruned_bytes', 0)} "
            f"phase1_progress_family_budget_bytes={H_PHASE1_PROGRESS_FAMILY_MAX_BYTES} "
            f"h_parent_trace_family_before_bytes={parent_trace_budget.get('before_total_bytes', 0)} "
            f"h_parent_trace_family_after_bytes={parent_trace_budget.get('after_total_bytes', 0)} "
            f"h_parent_trace_family_before_files={parent_trace_budget.get('before_total_files', 0)} "
            f"h_parent_trace_family_after_files={parent_trace_budget.get('after_total_files', 0)} "
            f"h_parent_trace_family_pruned_files={parent_trace_budget.get('pruned_files', 0)} "
            f"h_parent_trace_family_pruned_bytes={parent_trace_budget.get('pruned_bytes', 0)} "
            f"h_parent_trace_family_budget_bytes={H_PARENT_TRACE_FAMILY_MAX_BYTES} "
            f"h_home_time_mode_family_before_bytes={home_time_mode_budget.get('before_total_bytes', 0)} "
            f"h_home_time_mode_family_after_bytes={home_time_mode_budget.get('after_total_bytes', 0)} "
            f"h_home_time_mode_family_before_files={home_time_mode_budget.get('before_total_files', 0)} "
            f"h_home_time_mode_family_after_files={home_time_mode_budget.get('after_total_files', 0)} "
            f"h_home_time_mode_family_pruned_files={home_time_mode_budget.get('pruned_files', 0)} "
            f"h_home_time_mode_family_pruned_bytes={home_time_mode_budget.get('pruned_bytes', 0)} "
            f"h_home_time_mode_family_budget_bytes={H_HOME_TIME_MODE_FAMILY_MAX_BYTES} "
            f"phase1_lock_events_family_before_bytes={lock_events_budget.get('before_total_bytes', 0)} "
            f"phase1_lock_events_family_after_bytes={lock_events_budget.get('after_total_bytes', 0)} "
            f"phase1_lock_events_family_before_files={lock_events_budget.get('before_total_files', 0)} "
            f"phase1_lock_events_family_after_files={lock_events_budget.get('after_total_files', 0)} "
            f"phase1_lock_events_family_pruned_files={lock_events_budget.get('pruned_files', 0)} "
            f"phase1_lock_events_family_pruned_bytes={lock_events_budget.get('pruned_bytes', 0)} "
            f"phase1_lock_events_family_budget_bytes={PHASE1_LOCK_EVENTS_FAMILY_MAX_BYTES} "
            f"phase1_pilot_task_family_before_bytes={pilot_task_budget.get('before_total_bytes', 0)} "
            f"phase1_pilot_task_family_after_bytes={pilot_task_budget.get('after_total_bytes', 0)} "
            f"phase1_pilot_task_family_before_files={pilot_task_budget.get('before_total_files', 0)} "
            f"phase1_pilot_task_family_after_files={pilot_task_budget.get('after_total_files', 0)} "
            f"phase1_pilot_task_family_pruned_files={pilot_task_budget.get('pruned_files', 0)} "
            f"phase1_pilot_task_family_pruned_bytes={pilot_task_budget.get('pruned_bytes', 0)} "
            f"phase1_pilot_task_family_budget_bytes={PHASE1_PILOT_TASK_FAMILY_MAX_BYTES} "
            f"h110_lifecycle_family_before_bytes={h110_lifecycle_budget.get('before_total_bytes', 0)} "
            f"h110_lifecycle_family_after_bytes={h110_lifecycle_budget.get('after_total_bytes', 0)} "
            f"h110_lifecycle_family_before_files={h110_lifecycle_budget.get('before_total_files', 0)} "
            f"h110_lifecycle_family_after_files={h110_lifecycle_budget.get('after_total_files', 0)} "
            f"h110_lifecycle_family_pruned_files={h110_lifecycle_budget.get('pruned_files', 0)} "
            f"h110_lifecycle_family_pruned_bytes={h110_lifecycle_budget.get('pruned_bytes', 0)} "
            f"h110_lifecycle_family_budget_bytes={H110_LIFECYCLE_FAMILY_MAX_BYTES} "
            f"h110_decision_family_before_bytes={h110_decision_budget.get('before_total_bytes', 0)} "
            f"h110_decision_family_after_bytes={h110_decision_budget.get('after_total_bytes', 0)} "
            f"h110_decision_family_before_files={h110_decision_budget.get('before_total_files', 0)} "
            f"h110_decision_family_after_files={h110_decision_budget.get('after_total_files', 0)} "
            f"h110_decision_family_pruned_files={h110_decision_budget.get('pruned_files', 0)} "
            f"h110_decision_family_pruned_bytes={h110_decision_budget.get('pruned_bytes', 0)} "
            f"h110_decision_family_budget_bytes={H110_DECISION_FAMILY_MAX_BYTES} "
            f"h_cycle_log_before={before.get('h_cycle_log_bytes', '0')} "
            f"h_cycle_log_after={after.get('h_cycle_log_bytes', '0')} "
            f"h_pricing_log_before={before.get('h_pricing_log_bytes', '0')} "
            f"h_pricing_log_after={after.get('h_pricing_log_bytes', '0')} "
            f"phase1_progress_before={before.get('phase1_progress_log_bytes', '0')} "
            f"phase1_progress_after={after.get('phase1_progress_log_bytes', '0')}"
        )
    except Exception:
        pass


def _log(message: str) -> None:
    msg_norm = _norm(message)
    if not msg_norm:
        return
    if not msg_norm.startswith("FATAL") and not msg_norm.startswith("ERROR"):
        if not _dedupe_emit(_LOG_DEDUP_CACHE, msg_norm, H_LOG_DEDUP_INTERVAL_SECONDS):
            return
    line = f"{_ts()} {msg_norm}"
    seen: set[Path] = set()
    for path in _log_target_paths():
        if path in seen:
            continue
        seen.add(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _rotate_log_file(path, max_bytes=H_LOG_ROTATE_MAX_BYTES, max_files=H_LOG_ROTATE_MAX_FILES)
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
    run_id_norm = _norm(run_id)
    checkpoint_norm = _norm(checkpoint)
    high_priority_tokens = ("fail", "fatal", "error", "timeout", "resolved", "exit", "abandon", "missing")
    is_high_priority = any(token in checkpoint_norm.lower() for token in high_priority_tokens)
    dedupe_basis = [
        run_id_norm,
        checkpoint_norm,
        _norm(fields.get("status", "")),
        _norm(fields.get("reason", "")),
        _norm(fields.get("exit_reason", "")),
    ]
    dedupe_key = "|".join(dedupe_basis)
    if not is_high_priority:
        if not _dedupe_emit(_PHASE1_PROGRESS_DEDUP_CACHE, dedupe_key, H_PROGRESS_MIN_INTERVAL_SECONDS):
            return

    parts = [f"utc={_ts()}", f"run_id={run_id_norm}", f"checkpoint={checkpoint_norm}"]
    for key, value in fields.items():
        k = _norm(key)
        if not k:
            continue
        parts.append(f"{k}={_norm(value)}")
    line = " ".join(parts) + "\n"
    try:
        H_PHASE1_INTEL_PROGRESS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _rotate_log_file(
            H_PHASE1_INTEL_PROGRESS_LOG_PATH,
            max_bytes=H_PHASE1_PROGRESS_ROTATE_MAX_BYTES,
            max_files=H_PHASE1_PROGRESS_ROTATE_MAX_FILES,
        )
        with H_PHASE1_INTEL_PROGRESS_LOG_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
    except Exception:
        pass


def _pid_alive(pid: int) -> bool:
    if int(pid) <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            access = PROCESS_QUERY_LIMITED_INFORMATION
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

            handle = open_process(access, False, int(pid))
            if handle:
                try:
                    exit_code = wintypes.DWORD(0)
                    if bool(get_exit_code(handle, ctypes.byref(exit_code))):
                        return int(exit_code.value) == STILL_ACTIVE
                    return True
                finally:
                    with contextlib.suppress(Exception):
                        close_handle(handle)
            last_error = ctypes.get_last_error()
            if int(last_error or 0) == 5:
                return True
        except Exception:
            pass
        try:
            probe = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            combined = f"{probe.stdout or ''}\n{probe.stderr or ''}".strip()
            if not combined:
                return False
            if "No tasks are running which match the specified criteria" in combined:
                return False
            return f"\"{int(pid)}\"" in combined
        except Exception:
            return False
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        # Process exists but signal probe is not permitted for this user/context.
        return True
    except OSError:
        return False
    except Exception:
        return False
    return False


def _windows_process_identity(pid: int) -> dict[str, str]:
    if int(pid) <= 0 or os.name != "nt":
        return {}
    try:
        ps = (
            "$p=Get-CimInstance Win32_Process -Filter \"ProcessId="
            + str(int(pid))
            + "\" -ErrorAction SilentlyContinue;"
            "$row=@{};"
            "if($p){$row=@{name=[string]$p.Name;command_line=[string]$p.CommandLine;process_id=[string]$p.ProcessId}};"
            "$row | ConvertTo-Json -Compress"
        )
        probe = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
        raw = _norm(probe.stdout)
        if not raw:
            return {}
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return {}
        return {str(key): _norm(value) for key, value in payload.items()}
    except Exception:
        return {}


def _identity_is_h_cycle_owner(identity: dict[str, str]) -> bool:
    name = _norm(identity.get("name", "")).lower()
    command_line = _norm(identity.get("command_line", ""))
    if name != "python.exe" or not command_line:
        return False
    command_norm = command_line.lower().replace("/", "\\")
    root_norm = str(ROOT).lower().replace("/", "\\")
    return (
        root_norm in command_norm
        and (
            "scripts\\cycles\\run_h_pricing_cycle.py" in command_norm
            or "scripts\\cycles\\run_h_pricing_cycle_guarded.py" in command_norm
        )
    )


def _h_owner_pid_alive(pid: int) -> bool:
    pid_int = int(pid or 0)
    if pid_int <= 0:
        return False
    if pid_int == os.getpid():
        return True
    if not _pid_alive(pid_int):
        return False
    if os.name != "nt":
        return True
    return _identity_is_h_cycle_owner(_windows_process_identity(pid_int))


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
    # Snapshot worker subprocesses must not claim the parent cycle lock.
    if "--snapshot-refresh-worker" in sys.argv:
        return
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
    latest_name = latest_path.name
    if latest_name in {"listing_offer_snapshot_latest.csv", "listing_offer_seller_snapshot_latest.csv"}:
        table_name = (
            SQL_TABLE_LISTING_OFFER_SNAPSHOT_LATEST
            if latest_name == "listing_offer_snapshot_latest.csv"
            else SQL_TABLE_LISTING_OFFER_SELLER_SNAPSHOT_LATEST
        )
        try:
            snapshot_df = pd.read_csv(snapshot_path, dtype=str).fillna("")
        except Exception:
            temp_path = latest_path.with_suffix(latest_path.suffix + f".tmp.{os.getpid()}")
            shutil.copyfile(snapshot_path, temp_path)
            os.replace(temp_path, latest_path)
            return
        write_dataframe_with_sql_compat(snapshot_df, latest_path, table_name)
        return
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
    write_dataframe_with_sql_compat(merged, history_path, SQL_TABLE_LISTING_OFFER_HISTORY)

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


def _inventory_snapshot_capture_dt(path: Path) -> datetime | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        df = pd.DataFrame()
    if not df.empty:
        for col in ("timestamp_utc", "asof_utc", "date_utc", "asof_date"):
            if col not in df.columns:
                continue
            parsed = [_to_dt(v) for v in df[col].astype(str).tolist()]
            parsed = [v for v in parsed if v is not None]
            if parsed:
                return max(parsed)
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except Exception:
        return None


def _refresh_inventory_snapshot_with_a003(*, reason: str) -> int:
    script_path = ROOT / "scripts" / "flows" / "A" / "A003_run_inventory_to_sheet.py"
    if not script_path.exists():
        _log(f"inventory_snapshot_refresh_missing_script reason={reason} path={script_path}")
        return 127
    try:
        timeout_seconds = max(float(os.environ.get("H_INVENTORY_REFRESH_TIMEOUT_SECONDS", "180") or "180"), 30.0)
    except Exception:
        timeout_seconds = 180.0
    env = os.environ.copy()
    env["INVENTORY_WRITE_SHEETS"] = "0"
    env["INVENTORY_USE_API_OWNER"] = env.get("H_INVENTORY_REFRESH_USE_API_OWNER", "0")
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "scripts"), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    cmd = [sys.executable, str(script_path)]
    _log(
        "inventory_snapshot_refresh_start "
        f"reason={reason} "
        f"timeout_seconds={timeout_seconds:.0f} "
        "sheet_writes=0"
    )
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        _log(
            "inventory_snapshot_refresh_end "
            f"reason={reason} rc=124 timeout_seconds={timeout_seconds:.0f}"
        )
        return 124
    except Exception as exc:
        _log(f"inventory_snapshot_refresh_end reason={reason} rc=1 error={type(exc).__name__}:{exc}")
        return 1
    stdout_tail = " | ".join((result.stdout or "").splitlines()[-3:])[:500]
    stderr_tail = " | ".join((result.stderr or "").splitlines()[-3:])[:500]
    _log(
        "inventory_snapshot_refresh_end "
        f"reason={reason} rc={result.returncode} "
        f"stdout_tail={stdout_tail} "
        f"stderr_tail={stderr_tail}"
    )
    return int(result.returncode)


def _ensure_inventory_snapshot_today(snapshot_date: str, snapshot_ts: str) -> tuple[Path, str]:
    snapshot_path = OUT / f"inventory_snapshot_{snapshot_date}.csv"
    if snapshot_path.exists():
        refresh_enabled = os.environ.get("H_INVENTORY_REFRESH_STALE_SNAPSHOT", "1").strip().lower() not in {"0", "false", "no", "off"}
        try:
            max_age_seconds = max(float(os.environ.get("H_INVENTORY_SNAPSHOT_REFRESH_MAX_AGE_SECONDS", "3600") or "3600"), 0.0)
        except Exception:
            max_age_seconds = 3600.0
        capture_dt = _inventory_snapshot_capture_dt(snapshot_path)
        now_dt = _to_dt(snapshot_ts) or datetime.now(timezone.utc)
        age_seconds = max((now_dt - capture_dt).total_seconds(), 0.0) if capture_dt is not None else None
        if refresh_enabled and age_seconds is not None and age_seconds > max_age_seconds:
            rc = _refresh_inventory_snapshot_with_a003(reason="existing_inventory_snapshot_stale")
            if rc == 0:
                return snapshot_path, "refreshed_existing_snapshot"
            return snapshot_path, f"existing_snapshot_refresh_failed_rc_{rc}"
        return snapshot_path, "existing_snapshot"
    row_stale_hours = _to_float(os.environ.get("H_STOCK_ROW_STALE_HOURS", "24"))
    if row_stale_hours is None:
        row_stale_hours = 24.0
    row_stale_hours = max(float(row_stale_hours), 0.0)
    snapshot_now_dt = _to_dt(snapshot_ts) or datetime.now(timezone.utc)
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
                "row_last_updated_age_hours",
                "row_last_updated_status",
                "row_last_updated_is_stale",
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
    row_age_hours: list[str] = []
    row_status: list[str] = []
    stale_count = 0
    unknown_count = 0
    stale_age_values: list[float] = []
    stale_skus_sample: list[str] = []
    for _, row in out_df.iterrows():
        updated_dt = _to_dt(row.get("last_updated_time", ""))
        if updated_dt is None:
            row_age_hours.append("")
            row_status.append("UNKNOWN")
            unknown_count += 1
            continue
        age_hours = max((snapshot_now_dt - updated_dt).total_seconds() / 3600.0, 0.0)
        row_age_hours.append(f"{_round_half_up(age_hours, 2):.2f}")
        if age_hours >= row_stale_hours:
            row_status.append("STALE")
            stale_count += 1
            stale_age_values.append(age_hours)
            if len(stale_skus_sample) < 5:
                sku_sample = _norm(row.get("sku", "")).upper()
                if sku_sample:
                    stale_skus_sample.append(sku_sample)
        else:
            row_status.append("FRESH")
    out_df["row_last_updated_age_hours"] = row_age_hours
    out_df["row_last_updated_status"] = row_status
    out_df["row_last_updated_is_stale"] = out_df["row_last_updated_status"].map(
        lambda status: "1" if _norm(status).upper() == "STALE" else "0"
    )
    _atomic_write_csv(snapshot_path, out_df)
    worst_row_age_hours = max(stale_age_values) if stale_age_values else 0.0
    _log(
        "inventory_snapshot_today_materialized "
        f"today_utc={snapshot_date} "
        f"snapshot_path={snapshot_path} "
        f"rows={len(out_df.index)} "
        f"source_path={INVENTORY_SUMMARIES_PATH} "
        f"row_stale_hours={_round_half_up(row_stale_hours, 2):.2f} "
        f"stale_rows={stale_count} "
        f"unknown_last_updated_rows={unknown_count} "
        f"worst_row_age_hours={_round_half_up(worst_row_age_hours, 2):.2f} "
        f"stale_skus_sample={','.join(stale_skus_sample)}"
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


def _load_item_offers_retry_queue() -> pd.DataFrame:
    if H_ITEM_OFFERS_RETRY_QUEUE_PATH.exists():
        try:
            df = pd.read_csv(H_ITEM_OFFERS_RETRY_QUEUE_PATH, dtype=str).fillna("")
        except Exception:
            df = pd.DataFrame(columns=H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS)
    else:
        df = pd.DataFrame(columns=H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS)
    for col in H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS].fillna("")
    return df


def _persist_item_offers_retry_queue(df: pd.DataFrame) -> None:
    out_df = df.copy()
    for col in H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS:
        if col not in out_df.columns:
            out_df[col] = ""
    out_df = out_df[H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS].fillna("")
    _atomic_write_csv(H_ITEM_OFFERS_RETRY_QUEUE_PATH, out_df)


def _with_seller_detail_columns(
    seller_df: pd.DataFrame,
    listing_df: pd.DataFrame,
) -> pd.DataFrame:
    detail_cols = [
        "seller_detail_status",
        "seller_detail_attempted_flag",
        "seller_detail_offer_row_count",
        "seller_detail_snapshot_ts_utc",
        "seller_detail_resolution_status",
        "seller_detail_retry_attempt_count",
        "seller_detail_rotation_skip_count",
        "seller_detail_empty_response_count",
        "seller_detail_api_error_count",
        "seller_detail_force_attempt_flag",
        "seller_detail_retry_exhausted_flag",
        "seller_detail_operator_reason",
        "retry_next_run_flag",
    ]
    if seller_df is None:
        seller_df = pd.DataFrame()
    out_df = seller_df.copy()
    for col in detail_cols:
        if col not in out_df.columns:
            out_df[col] = ""
    if out_df.empty:
        return out_df
    if listing_df is None or listing_df.empty:
        return out_df.fillna("")
    required_join_cols = {"marketplace", "sku", "asin"}
    if not required_join_cols.issubset(set(listing_df.columns)):
        return out_df.fillna("")
    enrich_cols = [c for c in detail_cols if c in listing_df.columns]
    if not enrich_cols:
        return out_df.fillna("")
    listing_enrich = (
        listing_df[list(required_join_cols) + enrich_cols]
        .astype(str)
        .fillna("")
        .drop_duplicates(subset=["marketplace", "sku", "asin"], keep="first")
    )
    out_df = out_df.merge(listing_enrich, on=["marketplace", "sku", "asin"], how="left", suffixes=("", "__new"))
    for col in detail_cols:
        new_col = f"{col}__new"
        if new_col in out_df.columns:
            out_df[col] = out_df[new_col].astype(str).fillna("")
            out_df = out_df.drop(columns=[new_col], errors="ignore")
        out_df[col] = out_df[col].astype(str).fillna("")
    return out_df.fillna("")


def _build_seller_detail_resolution_proof(
    *,
    snapshot_utc: str,
    run_id: str,
    listing_df: pd.DataFrame,
    runtime_floor_df: pd.DataFrame,
) -> pd.DataFrame:
    listing = listing_df if isinstance(listing_df, pd.DataFrame) else pd.DataFrame()
    runtime = runtime_floor_df if isinstance(runtime_floor_df, pd.DataFrame) else pd.DataFrame()
    if "seller_detail_resolution_status" not in listing.columns:
        listing_resolution = pd.Series([], dtype=str)
    else:
        listing_resolution = (
            listing["seller_detail_resolution_status"].astype(str).str.strip().str.upper()
        )
    if "truth_status" not in runtime.columns:
        runtime_truth = pd.Series([], dtype=str)
    else:
        runtime_truth = runtime["truth_status"].astype(str).str.strip().str.upper()
    row = {
        "snapshot_utc": _norm(snapshot_utc),
        "run_id": _norm(run_id),
        "listing_rows": str(int(len(listing.index))),
        "runtime_floor_rows": str(int(len(runtime.index))),
        "pending_retry_count": str(int(listing_resolution.eq(DETAIL_RESOLUTION_PENDING_RETRY).sum())),
        "recovered_count": str(int(listing_resolution.eq(DETAIL_RESOLUTION_RECOVERED).sum())),
        "supp_gated_detail_count": str(int(runtime_truth.eq("SUPP_GATED_DETAIL").sum())),
        "supp_blocked_count": str(int(runtime_truth.eq("SUPP_BLOCKED").sum())),
    }
    return pd.DataFrame([row], dtype=str).fillna("")


def _seller_detail_recovery_history_columns() -> list[str]:
    return [
        "snapshot_utc",
        "run_id",
        "marketplace",
        "sku",
        "asin",
        "seller_detail_status",
        "seller_detail_resolution_status",
        "retry_next_run_flag",
        "retry_attempt_count",
        "rotation_skip_count",
        "empty_response_count",
        "api_error_count",
        "truth_status",
        "aging_runs",
        "aging_first_seen_utc",
        "aging_last_seen_utc",
        "classification",
    ]


def _seller_detail_measurement_summary_columns() -> list[str]:
    return [
        "snapshot_utc",
        "run_id",
        "history_rows",
        "pending_retry_count",
        "recovered_count",
        "amazon_missing_likely_count",
        "retry_exhausted_count",
        "supp_gated_detail_count",
        "supp_blocked_count",
        "newly_recovered_count",
        "stale_pending_over_threshold_count",
    ]


def _seller_detail_measurement_alert_columns() -> list[str]:
    return [
        "snapshot_utc",
        "run_id",
        "previous_run_id",
        "alert_key",
        "status",
        "current_value",
        "previous_value",
        "delta",
        "threshold",
        "notes",
    ]


def _seller_detail_operator_review_columns() -> list[str]:
    return [
        "snapshot_utc",
        "run_id",
        "review_rank",
        "operator_priority",
        "review_bucket",
        "review_reason",
        "marketplace",
        "sku",
        "asin",
        "classification",
        "truth_status",
        "seller_detail_status",
        "seller_detail_resolution_status",
        "retry_next_run_flag",
        "retry_attempt_count",
        "rotation_skip_count",
        "empty_response_count",
        "api_error_count",
        "aging_runs",
    ]


def _seller_detail_int(value: object) -> int:
    try:
        return int(str(value or "").strip())
    except Exception:
        return 0


def _df_text_series(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if not isinstance(df, pd.DataFrame):
        return pd.Series([], dtype=str)
    if col in df.columns:
        series = df[col]
        return series if isinstance(series, pd.Series) else pd.Series(series, index=df.index)
    if df.empty:
        return pd.Series([], dtype=str)
    return pd.Series([default] * len(df.index), index=df.index, dtype=str)


def _load_seller_detail_recovery_history() -> pd.DataFrame:
    cols = _seller_detail_recovery_history_columns()
    if not H_SELLER_DETAIL_RECOVERY_HISTORY_PATH.exists():
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(H_SELLER_DETAIL_RECOVERY_HISTORY_PATH, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame(columns=cols)
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df[cols].fillna("")


def _classify_seller_detail_row(
    *,
    resolution_status: str,
    retry_attempt_count: int,
    rotation_skip_count: int,
    empty_response_count: int,
    api_error_count: int,
    aging_runs: int,
) -> str:
    resolution_key = _norm(resolution_status).upper()
    stale_pending_run_threshold = _env_int("H_SELLER_DETAIL_STALE_PENDING_RUN_THRESHOLD", 3, min_value=1)
    likely_amazon_missing_threshold = _env_int("H_SELLER_DETAIL_AMAZON_EMPTY_THRESHOLD", 3, min_value=1)
    retry_exhausted_threshold = _env_int("H_SELLER_DETAIL_RETRY_EXHAUSTED_THRESHOLD", 8, min_value=1)
    local_selection_delay_threshold = _env_int("H_SELLER_DETAIL_LOCAL_SELECTION_DELAY_SKIP_THRESHOLD", 3, min_value=1)
    if resolution_key == DETAIL_RESOLUTION_RECOVERED:
        return DETAIL_CLASS_RECOVERED
    if resolution_key == DETAIL_RESOLUTION_RETRY_EXHAUSTED:
        return DETAIL_CLASS_RETRY_EXHAUSTED
    if resolution_key in {DETAIL_RESOLUTION_AMAZON_EMPTY_CONFIRMED, DETAIL_RESOLUTION_API_ERROR_CONFIRMED}:
        return DETAIL_CLASS_LIKELY_AMAZON_MISSING
    if resolution_key != DETAIL_RESOLUTION_PENDING_RETRY:
        return DETAIL_CLASS_NOT_APPLICABLE
    if retry_attempt_count >= retry_exhausted_threshold:
        return DETAIL_CLASS_RETRY_EXHAUSTED
    if empty_response_count >= likely_amazon_missing_threshold or api_error_count >= likely_amazon_missing_threshold:
        return DETAIL_CLASS_LIKELY_AMAZON_MISSING
    if rotation_skip_count >= local_selection_delay_threshold and retry_attempt_count <= 1:
        return DETAIL_CLASS_LIKELY_LOCAL_SELECTION_DELAY
    if aging_runs >= stale_pending_run_threshold and rotation_skip_count >= local_selection_delay_threshold:
        return DETAIL_CLASS_LIKELY_LOCAL_SELECTION_DELAY
    return DETAIL_CLASS_PENDING_RETRY


def _build_seller_detail_recovery_rows(
    *,
    snapshot_utc: str,
    run_id: str,
    listing_df: pd.DataFrame,
    runtime_floor_df: pd.DataFrame,
    retry_queue_df: pd.DataFrame,
) -> pd.DataFrame:
    cols = _seller_detail_recovery_history_columns()
    listing = listing_df if isinstance(listing_df, pd.DataFrame) else pd.DataFrame()
    if listing.empty:
        return pd.DataFrame(columns=cols)
    needed_listing_cols = ["marketplace", "sku", "asin", "seller_detail_status", "seller_detail_resolution_status", "retry_next_run_flag"]
    for col in needed_listing_cols:
        if col not in listing.columns:
            listing[col] = ""
    listing = listing.copy()
    listing["marketplace"] = listing["marketplace"].astype(str).str.strip().str.upper()
    listing["sku"] = listing["sku"].astype(str).str.strip().str.upper()
    listing["asin"] = listing["asin"].astype(str).str.strip()
    listing = listing.loc[listing["sku"].ne("")].copy()
    if listing.empty:
        return pd.DataFrame(columns=cols)
    detail_count_cols = {
        "retry_attempt_count": "seller_detail_retry_attempt_count",
        "rotation_skip_count": "seller_detail_rotation_skip_count",
        "empty_response_count": "seller_detail_empty_response_count",
        "api_error_count": "seller_detail_api_error_count",
    }
    for out_col, src_col in detail_count_cols.items():
        listing[out_col] = _df_text_series(listing, src_col).astype(str).str.strip()
    runtime = runtime_floor_df if isinstance(runtime_floor_df, pd.DataFrame) else pd.DataFrame()
    if "sku" in runtime.columns and "truth_status" in runtime.columns:
        runtime_map = (
            runtime[["sku", "truth_status"]]
            .astype(str)
            .fillna("")
            .assign(sku=lambda d: d["sku"].str.strip().str.upper())
            .drop_duplicates(subset=["sku"], keep="first")
        )
        listing = listing.merge(runtime_map, on="sku", how="left")
    else:
        listing["truth_status"] = ""
    queue = retry_queue_df if isinstance(retry_queue_df, pd.DataFrame) else pd.DataFrame()
    if not queue.empty and {"marketplace", "asin"}.issubset(set(queue.columns)):
        queue_map = queue.copy()
        queue_map["marketplace"] = _df_text_series(queue_map, "marketplace").astype(str).str.strip().str.upper()
        queue_map["asin"] = _df_text_series(queue_map, "asin").astype(str).str.strip()
        queue_map = queue_map.drop_duplicates(subset=["marketplace", "asin"], keep="first")
        queue_count_cols = {
            "retry_attempt_count": "attempt_count",
            "rotation_skip_count": "rotation_skip_count",
            "empty_response_count": "empty_response_count",
            "api_error_count": "api_error_count",
        }
        for out_col, queue_col in queue_count_cols.items():
            if queue_col in queue_map.columns:
                listing = listing.merge(
                    queue_map[["marketplace", "asin", queue_col]].rename(columns={queue_col: f"{out_col}__queue"}),
                    on=["marketplace", "asin"],
                    how="left",
                )
                listing[out_col] = listing[f"{out_col}__queue"].astype(str).where(
                    listing[f"{out_col}__queue"].astype(str).str.strip().ne(""),
                    listing[out_col].astype(str),
                )
                listing = listing.drop(columns=[f"{out_col}__queue"], errors="ignore")
    listing["snapshot_utc"] = _norm(snapshot_utc)
    listing["run_id"] = _norm(run_id)
    listing["aging_runs"] = ""
    listing["aging_first_seen_utc"] = ""
    listing["aging_last_seen_utc"] = ""
    listing["classification"] = ""
    out = listing[
        [
            "snapshot_utc",
            "run_id",
            "marketplace",
            "sku",
            "asin",
            "seller_detail_status",
            "seller_detail_resolution_status",
            "retry_next_run_flag",
            "retry_attempt_count",
            "rotation_skip_count",
            "empty_response_count",
            "api_error_count",
            "truth_status",
            "aging_runs",
            "aging_first_seen_utc",
            "aging_last_seen_utc",
            "classification",
        ]
    ].fillna("")
    return out


def _annotate_seller_detail_history(df: pd.DataFrame) -> pd.DataFrame:
    cols = _seller_detail_recovery_history_columns()
    if df.empty:
        return pd.DataFrame(columns=cols)
    out = df.copy()
    for col in cols:
        if col not in out.columns:
            out[col] = ""
    out["snapshot_dt"] = pd.to_datetime(out.get("snapshot_utc", ""), errors="coerce", utc=True)
    out = out.sort_values(["marketplace", "sku", "asin", "snapshot_dt", "run_id"], kind="stable").reset_index(drop=True)
    out["aging_runs"] = _df_text_series(out, "aging_runs").astype(str)
    out["aging_first_seen_utc"] = _df_text_series(out, "aging_first_seen_utc").astype(str)
    out["aging_last_seen_utc"] = _df_text_series(out, "aging_last_seen_utc").astype(str)
    out["classification"] = _df_text_series(out, "classification").astype(str)
    grouped = out.groupby(["marketplace", "sku", "asin"], sort=False, dropna=False)
    for _, idxs in grouped.indices.items():
        pending_streak = 0
        streak_first_ts = ""
        for idx in idxs:
            resolution = _norm(out.at[idx, "seller_detail_resolution_status"]).upper()
            if resolution == DETAIL_RESOLUTION_PENDING_RETRY:
                pending_streak += 1
                snapshot_utc = _norm(out.at[idx, "snapshot_utc"])
                if pending_streak == 1:
                    streak_first_ts = snapshot_utc
                out.at[idx, "aging_runs"] = str(pending_streak)
                out.at[idx, "aging_first_seen_utc"] = streak_first_ts
                out.at[idx, "aging_last_seen_utc"] = snapshot_utc
            else:
                pending_streak = 0
                streak_first_ts = ""
                out.at[idx, "aging_runs"] = "0"
                out.at[idx, "aging_first_seen_utc"] = ""
                out.at[idx, "aging_last_seen_utc"] = ""
            out.at[idx, "classification"] = _classify_seller_detail_row(
                resolution_status=resolution,
                retry_attempt_count=_seller_detail_int(out.at[idx, "retry_attempt_count"]),
                rotation_skip_count=_seller_detail_int(out.at[idx, "rotation_skip_count"]),
                empty_response_count=_seller_detail_int(out.at[idx, "empty_response_count"]),
                api_error_count=_seller_detail_int(out.at[idx, "api_error_count"]),
                aging_runs=_seller_detail_int(out.at[idx, "aging_runs"]),
            )
    out = out.drop(columns=["snapshot_dt"], errors="ignore")
    return out[cols].fillna("")


def _build_seller_detail_measurement_summary(
    *,
    snapshot_utc: str,
    run_id: str,
    history_df: pd.DataFrame,
) -> pd.DataFrame:
    stale_pending_run_threshold = _env_int("H_SELLER_DETAIL_STALE_PENDING_RUN_THRESHOLD", 3, min_value=1)
    cols = _seller_detail_measurement_summary_columns()
    if history_df.empty:
        return pd.DataFrame(
            [
                {
                    "snapshot_utc": _norm(snapshot_utc),
                    "run_id": _norm(run_id),
                    "history_rows": "0",
                    "pending_retry_count": "0",
                    "recovered_count": "0",
                    "amazon_missing_likely_count": "0",
                    "retry_exhausted_count": "0",
                    "supp_gated_detail_count": "0",
                    "supp_blocked_count": "0",
                    "newly_recovered_count": "0",
                    "stale_pending_over_threshold_count": "0",
                }
            ],
            columns=cols,
            dtype=str,
        ).fillna("")
    run_key = _norm(run_id)
    run_id_series = _df_text_series(history_df, "run_id").astype(str)
    current = history_df.loc[run_id_series.eq(run_key)].copy()
    prior = history_df.loc[~run_id_series.eq(run_key)].copy()
    current["key"] = (
        _df_text_series(current, "marketplace").astype(str).str.strip().str.upper()
        + "|"
        + _df_text_series(current, "sku").astype(str).str.strip().str.upper()
        + "|"
        + _df_text_series(current, "asin").astype(str).str.strip()
    )
    prior["key"] = (
        _df_text_series(prior, "marketplace").astype(str).str.strip().str.upper()
        + "|"
        + _df_text_series(prior, "sku").astype(str).str.strip().str.upper()
        + "|"
        + _df_text_series(prior, "asin").astype(str).str.strip()
    )
    prior["snapshot_dt"] = pd.to_datetime(prior.get("snapshot_utc", ""), errors="coerce", utc=True)
    prior = prior.sort_values(["key", "snapshot_dt"], ascending=[True, False], kind="stable")
    prior_latest = prior.drop_duplicates(subset=["key"], keep="first")
    prior_resolution_map = {
        _norm(rec.get("key", "")): _norm(rec.get("seller_detail_resolution_status", "")).upper()
        for _, rec in prior_latest.iterrows()
        if _norm(rec.get("key", ""))
    }
    newly_recovered_count = 0
    for _, rec in current.iterrows():
        current_resolution = _norm(rec.get("seller_detail_resolution_status", "")).upper()
        if current_resolution != DETAIL_RESOLUTION_RECOVERED:
            continue
        key = _norm(rec.get("key", ""))
        prior_resolution = prior_resolution_map.get(key, "")
        if prior_resolution and prior_resolution != DETAIL_RESOLUTION_RECOVERED:
            newly_recovered_count += 1
    stale_pending_over_threshold_count = int(
        (
            _df_text_series(current, "classification").astype(str).str.strip().eq(DETAIL_CLASS_PENDING_RETRY)
            & pd.to_numeric(_df_text_series(current, "aging_runs", "0"), errors="coerce").fillna(0).ge(stale_pending_run_threshold)
        ).sum()
    )
    row = {
        "snapshot_utc": _norm(snapshot_utc),
        "run_id": run_key,
        "history_rows": str(int(len(current.index))),
        "pending_retry_count": str(
            int(_df_text_series(current, "seller_detail_resolution_status").astype(str).str.strip().str.upper().eq(DETAIL_RESOLUTION_PENDING_RETRY).sum())
        ),
        "recovered_count": str(
            int(_df_text_series(current, "seller_detail_resolution_status").astype(str).str.strip().str.upper().eq(DETAIL_RESOLUTION_RECOVERED).sum())
        ),
        "amazon_missing_likely_count": str(
            int(_df_text_series(current, "classification").astype(str).str.strip().eq(DETAIL_CLASS_LIKELY_AMAZON_MISSING).sum())
        ),
        "retry_exhausted_count": str(
            int(_df_text_series(current, "classification").astype(str).str.strip().eq(DETAIL_CLASS_RETRY_EXHAUSTED).sum())
        ),
        "supp_gated_detail_count": str(
            int(_df_text_series(current, "truth_status").astype(str).str.strip().str.upper().eq("SUPP_GATED_DETAIL").sum())
        ),
        "supp_blocked_count": str(
            int(_df_text_series(current, "truth_status").astype(str).str.strip().str.upper().eq("SUPP_BLOCKED").sum())
        ),
        "newly_recovered_count": str(int(newly_recovered_count)),
        "stale_pending_over_threshold_count": str(int(stale_pending_over_threshold_count)),
    }
    return pd.DataFrame([row], columns=cols, dtype=str).fillna("")


def _latest_prior_seller_detail_run_id(history_df: pd.DataFrame, *, current_run_id: str) -> str:
    if history_df.empty or "run_id" not in history_df.columns:
        return ""
    view = history_df.copy()
    view["run_id"] = _df_text_series(view, "run_id").astype(str).str.strip()
    view = view.loc[view["run_id"].ne("") & view["run_id"].ne(_norm(current_run_id))].copy()
    if view.empty:
        return ""
    view["snapshot_dt"] = pd.to_datetime(view.get("snapshot_utc", ""), errors="coerce", utc=True)
    view = view.sort_values(["snapshot_dt", "run_id"], ascending=[False, False], kind="stable")
    return _norm(view.iloc[0].get("run_id", ""))


def _build_seller_detail_measurement_alerts(
    *,
    snapshot_utc: str,
    run_id: str,
    history_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> pd.DataFrame:
    cols = _seller_detail_measurement_alert_columns()
    if summary_df.empty:
        return pd.DataFrame(columns=cols)
    current_row = summary_df.iloc[0].to_dict()
    previous_run_id = _latest_prior_seller_detail_run_id(history_df, current_run_id=run_id)
    previous_summary_row: dict[str, str] = {}
    if previous_run_id:
        previous_summary = _build_seller_detail_measurement_summary(
            snapshot_utc="",
            run_id=previous_run_id,
            history_df=history_df,
        )
        if not previous_summary.empty:
            previous_summary_row = {str(k): _norm(v) for k, v in previous_summary.iloc[0].to_dict().items()}

    backlog_growth_warn_delta = _env_int("H_SELLER_DETAIL_BACKLOG_GROWTH_WARN_DELTA", 3, min_value=1)
    exhausted_growth_warn_delta = _env_int("H_SELLER_DETAIL_EXHAUSTED_GROWTH_WARN_DELTA", 3, min_value=1)
    amazon_missing_warn_count = _env_int("H_SELLER_DETAIL_AMAZON_MISSING_WARN_COUNT", 3, min_value=1)
    stale_pending_warn_count = _env_int("H_SELLER_DETAIL_STALE_PENDING_WARN_COUNT", 1, min_value=1)

    def _build_growth_row(alert_key: str, field_name: str, threshold: int, notes: str) -> dict[str, str]:
        current_value = _seller_detail_int(current_row.get(field_name, "0"))
        previous_value_raw = previous_summary_row.get(field_name, "")
        previous_value = _seller_detail_int(previous_value_raw)
        if previous_run_id:
            delta = current_value - previous_value
            status = "warn" if delta >= threshold and current_value > previous_value else "ok"
            delta_text = str(int(delta))
            previous_text = str(int(previous_value))
        else:
            status = "baseline"
            delta_text = ""
            previous_text = ""
        return {
            "snapshot_utc": _norm(snapshot_utc),
            "run_id": _norm(run_id),
            "previous_run_id": _norm(previous_run_id),
            "alert_key": alert_key,
            "status": status,
            "current_value": str(int(current_value)),
            "previous_value": previous_text,
            "delta": delta_text,
            "threshold": str(int(threshold)),
            "notes": notes,
        }

    def _build_pressure_row(alert_key: str, field_name: str, threshold: int, notes: str) -> dict[str, str]:
        current_value = _seller_detail_int(current_row.get(field_name, "0"))
        return {
            "snapshot_utc": _norm(snapshot_utc),
            "run_id": _norm(run_id),
            "previous_run_id": _norm(previous_run_id),
            "alert_key": alert_key,
            "status": "warn" if current_value >= threshold else "ok",
            "current_value": str(int(current_value)),
            "previous_value": previous_summary_row.get(field_name, ""),
            "delta": "",
            "threshold": str(int(threshold)),
            "notes": notes,
        }

    rows = [
        _build_growth_row(
            "pending_retry_growth",
            "pending_retry_count",
            backlog_growth_warn_delta,
            "warn_when_pending_retry_grows_vs_previous_run",
        ),
        _build_growth_row(
            "retry_exhausted_growth",
            "retry_exhausted_count",
            exhausted_growth_warn_delta,
            "warn_when_retry_exhausted_grows_vs_previous_run",
        ),
        _build_pressure_row(
            "amazon_missing_pressure",
            "amazon_missing_likely_count",
            amazon_missing_warn_count,
            "warn_when_likely_amazon_missing_count_reaches_threshold",
        ),
        _build_pressure_row(
            "stale_pending_pressure",
            "stale_pending_over_threshold_count",
            stale_pending_warn_count,
            "warn_when_stale_pending_count_reaches_threshold",
        ),
    ]
    return pd.DataFrame(rows, columns=cols, dtype=str).fillna("")


def _seller_detail_review_bucket_and_reason(row: pd.Series) -> tuple[str, str]:
    classification = _norm(row.get("classification", ""))
    truth_status = _norm(row.get("truth_status", "")).upper()
    retry_attempt_count = _seller_detail_int(row.get("retry_attempt_count", "0"))
    rotation_skip_count = _seller_detail_int(row.get("rotation_skip_count", "0"))
    empty_response_count = _seller_detail_int(row.get("empty_response_count", "0"))
    api_error_count = _seller_detail_int(row.get("api_error_count", "0"))

    if classification == DETAIL_CLASS_LIKELY_AMAZON_MISSING:
        return DETAIL_REVIEW_BUCKET_LIKELY_AMAZON_UPSTREAM, "repeated_attempted_empty_or_api_responses"
    if classification == DETAIL_CLASS_LIKELY_LOCAL_SELECTION_DELAY:
        return DETAIL_REVIEW_BUCKET_LIKELY_LOCAL_SELECTION_CADENCE, "rotation_skip_pressure_exceeds_attempt_pressure"
    if classification == DETAIL_CLASS_RETRY_EXHAUSTED:
        if empty_response_count + api_error_count >= max(rotation_skip_count, 1):
            return DETAIL_REVIEW_BUCKET_LIKELY_AMAZON_UPSTREAM, "retry_exhausted_with_attempted_empty_or_api_pressure"
        if rotation_skip_count > max(retry_attempt_count, 1) and empty_response_count <= 0 and api_error_count <= 0:
            return DETAIL_REVIEW_BUCKET_LIKELY_LOCAL_SELECTION_CADENCE, "retry_exhausted_with_rotation_skip_pressure"
        return DETAIL_REVIEW_BUCKET_RETRY_EXHAUSTED_OPERATOR_REVIEW, "retry_budget_exhausted_needs_manual_case_review"
    if truth_status == "SUPP_BLOCKED":
        return (
            DETAIL_REVIEW_BUCKET_GENUINE_PRICING_OR_SUPPRESSION_BLOCKER,
            "truth_status_supp_blocked_requires_non_detail_review",
        )
    return "", ""


def _seller_detail_operator_priority(review_bucket: str, truth_status: str) -> str:
    bucket_key = _norm(review_bucket)
    truth_key = _norm(truth_status).upper()
    if truth_key == "SUPP_BLOCKED" or bucket_key in {
        DETAIL_REVIEW_BUCKET_GENUINE_PRICING_OR_SUPPRESSION_BLOCKER,
        DETAIL_REVIEW_BUCKET_RETRY_EXHAUSTED_OPERATOR_REVIEW,
    }:
        return "P1"
    if truth_key == "SUPP_GATED_DETAIL" or bucket_key in {
        DETAIL_REVIEW_BUCKET_LIKELY_AMAZON_UPSTREAM,
        DETAIL_REVIEW_BUCKET_LIKELY_LOCAL_SELECTION_CADENCE,
    }:
        return "P2"
    return "P3"


def _build_seller_detail_operator_review(
    *,
    snapshot_utc: str,
    run_id: str,
    history_df: pd.DataFrame,
) -> pd.DataFrame:
    cols = _seller_detail_operator_review_columns()
    if history_df.empty:
        return pd.DataFrame(columns=cols)
    current = history_df.loc[_df_text_series(history_df, "run_id").astype(str).str.strip().eq(_norm(run_id))].copy()
    if current.empty:
        return pd.DataFrame(columns=cols)
    rows: list[dict[str, str]] = []
    for _, rec in current.iterrows():
        review_bucket, review_reason = _seller_detail_review_bucket_and_reason(rec)
        if not review_bucket:
            continue
        rows.append(
            {
                "snapshot_utc": _norm(snapshot_utc),
                "run_id": _norm(run_id),
                "review_rank": "",
                "operator_priority": _seller_detail_operator_priority(review_bucket, _norm(rec.get("truth_status", ""))),
                "review_bucket": review_bucket,
                "review_reason": review_reason,
                "marketplace": _norm(rec.get("marketplace", "")),
                "sku": _norm(rec.get("sku", "")),
                "asin": _norm(rec.get("asin", "")),
                "classification": _norm(rec.get("classification", "")),
                "truth_status": _norm(rec.get("truth_status", "")),
                "seller_detail_status": _norm(rec.get("seller_detail_status", "")),
                "seller_detail_resolution_status": _norm(rec.get("seller_detail_resolution_status", "")),
                "retry_next_run_flag": _norm(rec.get("retry_next_run_flag", "")),
                "retry_attempt_count": _norm(rec.get("retry_attempt_count", "")),
                "rotation_skip_count": _norm(rec.get("rotation_skip_count", "")),
                "empty_response_count": _norm(rec.get("empty_response_count", "")),
                "api_error_count": _norm(rec.get("api_error_count", "")),
                "aging_runs": _norm(rec.get("aging_runs", "")),
            }
        )
    review = pd.DataFrame(rows, columns=cols, dtype=str).fillna("")
    if review.empty:
        return review
    review["priority_sort"] = review["operator_priority"].astype(str).map({"P1": 1, "P2": 2, "P3": 3}).fillna(9)
    review["aging_sort"] = pd.to_numeric(review["aging_runs"], errors="coerce").fillna(0)
    review["attempt_sort"] = pd.to_numeric(review["retry_attempt_count"], errors="coerce").fillna(0)
    review["empty_sort"] = pd.to_numeric(review["empty_response_count"], errors="coerce").fillna(0)
    review["skip_sort"] = pd.to_numeric(review["rotation_skip_count"], errors="coerce").fillna(0)
    review = review.sort_values(
        ["priority_sort", "aging_sort", "attempt_sort", "empty_sort", "skip_sort", "sku", "asin"],
        ascending=[True, False, False, False, False, True, True],
        kind="stable",
    ).reset_index(drop=True)
    review["review_rank"] = (review.index + 1).astype(int).astype(str)
    review = review.drop(columns=["priority_sort", "aging_sort", "attempt_sort", "empty_sort", "skip_sort"], errors="ignore")
    return review[cols].fillna("")


def _seller_detail_measurement_summary_archive_path(run_id: str) -> Path:
    run_token = _norm(run_id) or "unknown_run"
    return H_SELLER_DETAIL_HISTORY_DIR / f"h_seller_detail_measurement_summary_{run_token}.csv"


def _seller_detail_operator_review_bucket_counts(review_df: pd.DataFrame) -> dict[str, int]:
    if review_df.empty or "review_bucket" not in review_df.columns:
        return {
            "amazon_upstream": 0,
            "local_selection": 0,
            "retry_exhausted_review": 0,
            "genuine_blocker": 0,
        }
    bucket = review_df["review_bucket"].astype(str).str.strip()
    return {
        "amazon_upstream": int(bucket.eq(DETAIL_REVIEW_BUCKET_LIKELY_AMAZON_UPSTREAM).sum()),
        "local_selection": int(bucket.eq(DETAIL_REVIEW_BUCKET_LIKELY_LOCAL_SELECTION_CADENCE).sum()),
        "retry_exhausted_review": int(bucket.eq(DETAIL_REVIEW_BUCKET_RETRY_EXHAUSTED_OPERATOR_REVIEW).sum()),
        "genuine_blocker": int(bucket.eq(DETAIL_REVIEW_BUCKET_GENUINE_PRICING_OR_SUPPRESSION_BLOCKER).sum()),
    }


def _build_seller_detail_measurement_outputs(
    *,
    snapshot_utc: str,
    run_id: str,
    listing_df: pd.DataFrame,
    runtime_floor_df: pd.DataFrame,
    retry_queue_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    previous_history = _load_seller_detail_recovery_history()
    current_rows = _build_seller_detail_recovery_rows(
        snapshot_utc=snapshot_utc,
        run_id=run_id,
        listing_df=listing_df,
        runtime_floor_df=runtime_floor_df,
        retry_queue_df=retry_queue_df,
    )
    history = pd.concat([previous_history, current_rows], ignore_index=True)
    history = history.drop_duplicates(
        subset=["snapshot_utc", "run_id", "marketplace", "sku", "asin"],
        keep="last",
    )
    history = _annotate_seller_detail_history(history)
    summary = _build_seller_detail_measurement_summary(
        snapshot_utc=snapshot_utc,
        run_id=run_id,
        history_df=history,
    )
    return history, summary


def _active_retry_asins_for_marketplace(
    *,
    queue_df: pd.DataFrame,
    marketplace_code: str,
    candidate_asins: List[str],
    retry_budget: int | None = None,
) -> List[str]:
    plan = _build_retry_selection_plan_for_marketplace(
        queue_df=queue_df,
        marketplace_code=marketplace_code,
        candidate_asins=candidate_asins,
        retry_budget=retry_budget,
    )
    return [str(v).strip() for v in plan.get("selected_asins", []) if str(v).strip()]


def _resolve_item_offers_effective_budget(
    *,
    candidate_count: int,
    base_budget: int,
    active_pending_count: int,
) -> int:
    candidates = max(int(candidate_count or 0), 0)
    base = max(int(base_budget or 0), 1)
    if candidates <= 0:
        return 0
    default_budget = min(base, candidates)
    pending = max(int(active_pending_count or 0), 0)
    if pending <= 0:
        return default_budget
    one_cycle_enabled = is_truthy(os.environ.get("H_ITEM_OFFERS_ONE_CYCLE_RETRY_ENABLED", "1"))
    one_cycle_trigger_pending = _env_int(
        "H_ITEM_OFFERS_ONE_CYCLE_RETRY_TRIGGER_PENDING",
        1,
        min_value=1,
    )
    hard_cap = _env_int("H_ITEM_OFFERS_ONE_CYCLE_RETRY_HARD_CAP", candidates, min_value=base)
    one_cycle_active = one_cycle_enabled and pending >= one_cycle_trigger_pending
    if one_cycle_active and hard_cap < candidates:
        # One-cycle recovery takes precedence over stale/manual low caps.
        hard_cap = candidates
    boosted = candidates if one_cycle_active else max(base, pending)
    boosted = min(boosted, hard_cap, candidates)
    return max(boosted, default_budget)


def _build_retry_selection_plan_for_marketplace(
    *,
    queue_df: pd.DataFrame,
    marketplace_code: str,
    candidate_asins: List[str],
    retry_budget: int | None = None,
) -> dict[str, object]:
    if queue_df.empty:
        return {
            "selected_asins": [],
            "selected_count": 0,
            "candidate_count": 0,
            "active_pending_count": 0,
            "protected_candidate_count": 0,
            "protected_selected_count": 0,
            "protected_cap": 0,
            "protected_fairness_deferred_count": 0,
            "amazon_upstream_candidate_count": 0,
            "retry_budget": int(retry_budget or 0),
        }
    mp_key = _norm(marketplace_code).upper()
    candidates = {str(v).strip() for v in candidate_asins if str(v).strip()}
    if not candidates:
        return {
            "selected_asins": [],
            "selected_count": 0,
            "candidate_count": 0,
            "active_pending_count": 0,
            "protected_candidate_count": 0,
            "protected_selected_count": 0,
            "protected_cap": 0,
            "protected_fairness_deferred_count": 0,
            "amazon_upstream_candidate_count": 0,
            "retry_budget": int(retry_budget or 0),
        }
    view = queue_df.copy()
    view["marketplace_key"] = view.get("marketplace", "").astype(str).str.strip().str.upper()
    view["asin_key"] = view.get("asin", "").astype(str).str.strip()
    view["active_flag_key"] = view.get("active_flag", "").astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y", "on"})
    view["resolution_key"] = view.get("detail_resolution_status", "").astype(str).str.strip().str.upper()
    view = view.loc[
        view["marketplace_key"].eq(mp_key)
        & view["active_flag_key"]
        & view["resolution_key"].isin({"", DETAIL_RESOLUTION_PENDING_RETRY})
        & view["asin_key"].isin(candidates)
    ].copy()
    if view.empty:
        return {
            "selected_asins": [],
            "selected_count": 0,
            "candidate_count": len(candidates),
            "active_pending_count": 0,
            "protected_candidate_count": 0,
            "protected_selected_count": 0,
            "protected_cap": 0,
            "protected_fairness_deferred_count": 0,
            "amazon_upstream_candidate_count": 0,
            "retry_budget": int(retry_budget or 0),
        }
    local_selection_skip_threshold = _env_int("H_ITEM_OFFERS_LOCAL_SELECTION_DELAY_SKIP_THRESHOLD", 3, min_value=1)
    amazon_missing_threshold = _env_int("H_ITEM_OFFERS_AMAZON_MISSING_CONFIRM_THRESHOLD", 3, min_value=1)
    protected_lane_budget = _env_int("H_ITEM_OFFERS_PROTECTED_LANE_BUDGET", 5, min_value=0)
    protected_lane_fairness_window_minutes = _env_int(
        "H_ITEM_OFFERS_PROTECTED_LANE_FAIRNESS_WINDOW_MINUTES",
        180,
        min_value=1,
    )
    protected_lane_max_share_raw = _to_float(os.environ.get("H_ITEM_OFFERS_PROTECTED_LANE_MAX_SHARE", "0.50"))
    if protected_lane_max_share_raw is None:
        protected_lane_max_share_raw = 0.50
    protected_lane_max_share = min(max(float(protected_lane_max_share_raw), 0.0), 1.0)
    view["first_missing_sort"] = pd.to_datetime(
        view.get("first_missing_utc", view.get("first_missed_at_utc", "")),
        errors="coerce",
        utc=True,
    )
    view["last_attempt_sort"] = pd.to_datetime(
        view.get("last_attempt_utc", view.get("last_attempt_at_utc", "")),
        errors="coerce",
        utc=True,
    )
    view["last_attempt_missing_sort"] = view["last_attempt_sort"].isna()
    view["attempt_count_sort"] = pd.to_numeric(view.get("attempt_count", "0"), errors="coerce").fillna(0)
    view["rotation_skip_sort"] = pd.to_numeric(view.get("rotation_skip_count", "0"), errors="coerce").fillna(0)
    view["empty_response_sort"] = pd.to_numeric(view.get("empty_response_count", "0"), errors="coerce").fillna(0)
    view["api_error_sort"] = pd.to_numeric(view.get("api_error_count", "0"), errors="coerce").fillna(0)
    view["force_attempt_sort"] = view.get("force_attempt_next_run_flag", "").astype(str).str.strip().str.lower().isin(
        {"1", "true", "yes", "y", "on"}
    )
    view["priority_sort"] = view.get("priority_band", "").astype(str).str.strip().str.upper().map(
        {DETAIL_PRIORITY_HIGH: 2, DETAIL_PRIORITY_NORMAL: 1}
    ).fillna(0)
    view["is_likely_amazon_upstream"] = (
        view["empty_response_sort"].ge(float(amazon_missing_threshold))
        | view["api_error_sort"].ge(float(amazon_missing_threshold))
    )
    view["is_local_selection_candidate"] = (
        view["rotation_skip_sort"].ge(float(local_selection_skip_threshold))
        & view["attempt_count_sort"].le(1.0)
        & view["empty_response_sort"].le(0.0)
        & view["api_error_sort"].le(0.0)
        & ~view["is_likely_amazon_upstream"]
    )
    now_utc = _utc_now()
    fairness_window_minutes = max(float(protected_lane_fairness_window_minutes), 1.0)
    view["last_attempt_age_minutes"] = (
        (now_utc - view["last_attempt_sort"]).dt.total_seconds().div(60.0)
    )
    view["protected_fairness_hold"] = (
        view["is_local_selection_candidate"]
        & view["last_attempt_age_minutes"].fillna(10**9).lt(fairness_window_minutes)
    )
    main_order = view.sort_values(
        [
            "force_attempt_sort",
            "priority_sort",
            "last_attempt_missing_sort",
            "last_attempt_sort",
            "first_missing_sort",
            "rotation_skip_sort",
            "attempt_count_sort",
            "asin_key",
        ],
        ascending=[False, False, False, True, True, False, True, True],
        kind="stable",
    )
    ordered = [str(v).strip() for v in main_order.get("asin_key", []).tolist() if str(v).strip()]
    final_budget = len(ordered)
    if retry_budget is not None and retry_budget > 0:
        final_budget = min(final_budget, int(retry_budget))

    protected_candidates = view.loc[view["is_local_selection_candidate"]].copy()
    protected_candidates = protected_candidates.sort_values(
        [
            "protected_fairness_hold",
            "force_attempt_sort",
            "rotation_skip_sort",
            "attempt_count_sort",
            "last_attempt_missing_sort",
            "last_attempt_sort",
            "first_missing_sort",
            "asin_key",
        ],
        ascending=[True, False, False, True, False, True, True, True],
        kind="stable",
    )
    protected_asins = [str(v).strip() for v in protected_candidates.get("asin_key", []).tolist() if str(v).strip()]

    protected_cap = 0
    if final_budget > 0 and protected_lane_budget > 0 and protected_lane_max_share > 0.0:
        share_cap = int(final_budget * protected_lane_max_share)
        if share_cap <= 0:
            share_cap = 1
        protected_cap = min(final_budget, protected_lane_budget, share_cap)

    selected_protected = protected_asins[:protected_cap]
    selected_keys = set(selected_protected)
    remainder = [asin for asin in ordered if asin not in selected_keys]
    selected = (selected_protected + remainder)[:final_budget]

    return {
        "selected_asins": selected,
        "selected_count": len(selected),
        "candidate_count": len(candidates),
        "active_pending_count": int(len(view.index)),
        "protected_candidate_count": int(len(protected_asins)),
        "protected_selected_count": int(len(selected_protected)),
        "protected_cap": int(protected_cap),
        "protected_fairness_deferred_count": int(view["protected_fairness_hold"].sum()),
        "amazon_upstream_candidate_count": int(view["is_likely_amazon_upstream"].sum()),
        "retry_budget": int(final_budget),
    }


def _compute_item_offers_budget_plan_for_marketplace(
    *,
    queue_df: pd.DataFrame,
    marketplace_code: str,
    candidate_asins: List[str],
    base_budget: int,
) -> dict[str, object]:
    normalized_candidates = [str(v).strip() for v in dict.fromkeys(candidate_asins) if str(v).strip()]
    candidate_asins_count = len(normalized_candidates)
    if candidate_asins_count <= 0:
        return {
            "candidate_asins_count": 0,
            "active_pending_count": 0,
            "effective_item_offers_budget": 0,
            "retry_priority_budget": 0,
            "one_cycle_active": False,
            "retry_selection": _build_retry_selection_plan_for_marketplace(
                queue_df=queue_df,
                marketplace_code=marketplace_code,
                candidate_asins=normalized_candidates,
                retry_budget=0,
            ),
        }

    # Start from the base budget until the live retry queue proves there is
    # pending seller-detail work. Seeding a synthetic pending count here would
    # turn every normal run into a one-cycle retry sweep.
    initial_effective_budget = _resolve_item_offers_effective_budget(
        candidate_count=candidate_asins_count,
        base_budget=base_budget,
        active_pending_count=0,
    )
    retry_priority_budget = min(initial_effective_budget, candidate_asins_count)
    retry_selection = _build_retry_selection_plan_for_marketplace(
        queue_df=queue_df,
        marketplace_code=marketplace_code,
        candidate_asins=normalized_candidates,
        retry_budget=retry_priority_budget,
    )
    active_pending_count = _to_int(retry_selection.get("active_pending_count", 0)) or 0
    effective_item_offers_budget = max(
        initial_effective_budget,
        _resolve_item_offers_effective_budget(
            candidate_count=candidate_asins_count,
            base_budget=base_budget,
            active_pending_count=active_pending_count,
        ),
    )
    one_cycle_enabled = is_truthy(os.environ.get("H_ITEM_OFFERS_ONE_CYCLE_RETRY_ENABLED", "1"))
    one_cycle_trigger_pending = _env_int(
        "H_ITEM_OFFERS_ONE_CYCLE_RETRY_TRIGGER_PENDING",
        1,
        min_value=1,
    )
    one_cycle_active = one_cycle_enabled and active_pending_count >= one_cycle_trigger_pending
    forced_pending_budget = (
        candidate_asins_count
        if one_cycle_active
        else min(
            candidate_asins_count,
            max(base_budget, int(active_pending_count)),
        )
    )
    if active_pending_count > retry_priority_budget and forced_pending_budget > retry_priority_budget:
        effective_item_offers_budget = max(effective_item_offers_budget, forced_pending_budget)
    if effective_item_offers_budget != retry_priority_budget:
        retry_priority_budget = min(effective_item_offers_budget, candidate_asins_count)
        retry_selection = _build_retry_selection_plan_for_marketplace(
            queue_df=queue_df,
            marketplace_code=marketplace_code,
            candidate_asins=normalized_candidates,
            retry_budget=retry_priority_budget,
        )
    return {
        "candidate_asins_count": int(candidate_asins_count),
        "active_pending_count": int(active_pending_count),
        "effective_item_offers_budget": int(effective_item_offers_budget),
        "retry_priority_budget": int(retry_priority_budget),
        "one_cycle_active": bool(one_cycle_active),
        "retry_selection": retry_selection,
    }


def _update_item_offers_retry_queue_for_marketplace(
    *,
    queue_df: pd.DataFrame,
    marketplace_code: str,
    snapshot_ts: str,
    asin_to_skus: Dict[str, List[str]],
    detail_meta_by_asin: Dict[str, Dict[str, str]],
) -> tuple[pd.DataFrame, Dict[str, int], Dict[str, Dict[str, str]]]:
    if queue_df.empty:
        queue_df = pd.DataFrame(columns=H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS)
    for col in H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS:
        if col not in queue_df.columns:
            queue_df[col] = ""
    queue_df = queue_df[H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS].fillna("").copy()
    queue_df["marketplace_key"] = queue_df["marketplace"].astype(str).str.strip().str.upper()
    queue_df["asin_key"] = queue_df["asin"].astype(str).str.strip()
    row_index_by_key = {
        (str(rec.get("marketplace_key", "")), str(rec.get("asin_key", ""))): idx
        for idx, rec in queue_df.iterrows()
    }

    stats = {
        "detail_ok_count": 0,
        "detail_skipped_count": 0,
        "detail_empty_count": 0,
        "detail_error_count": 0,
        "queue_active_count": 0,
        "resolution_pending_count": 0,
        "resolution_recovered_count": 0,
        "resolution_amazon_empty_count": 0,
        "resolution_api_error_count": 0,
        "resolution_exhausted_count": 0,
    }
    resolution_by_asin: Dict[str, Dict[str, str]] = {}
    mp_key = _norm(marketplace_code).upper() or "UK"
    rotation_skip_threshold = _env_int("H_ITEM_OFFERS_ROTATION_SKIP_THRESHOLD", 3, min_value=1)
    empty_confirm_threshold = _env_int("H_ITEM_OFFERS_EMPTY_CONFIRM_THRESHOLD", 3, min_value=1)
    api_error_confirm_threshold = _env_int("H_ITEM_OFFERS_API_ERROR_CONFIRM_THRESHOLD", 3, min_value=1)
    retry_exhausted_threshold = _env_int("H_ITEM_OFFERS_RETRY_EXHAUSTED_THRESHOLD", 8, min_value=rotation_skip_threshold)

    for asin, skus in asin_to_skus.items():
        asin_key = _norm(asin)
        if not asin_key:
            continue
        meta = detail_meta_by_asin.get(asin_key, {}) if isinstance(detail_meta_by_asin, dict) else {}
        detail_status = _norm(meta.get("detail_status", "")) or DETAIL_STATUS_SKIPPED_ROTATION
        attempted_flag = "1" if _to_bool(meta.get("attempted_flag", ""), default=False) else "0"
        selected_flag = "1" if _to_bool(meta.get("selected_flag", ""), default=False) else "0"
        if detail_status == DETAIL_STATUS_OK:
            stats["detail_ok_count"] += 1
        elif detail_status == DETAIL_STATUS_EMPTY_RESPONSE:
            stats["detail_empty_count"] += 1
        elif detail_status == DETAIL_STATUS_API_ERROR:
            stats["detail_error_count"] += 1
        else:
            stats["detail_skipped_count"] += 1

        key = (mp_key, asin_key)
        idx = row_index_by_key.get(key)
        if idx is None:
            queue_df.loc[len(queue_df.index)] = {
                "marketplace": mp_key,
                "asin": asin_key,
                "sample_sku": _norm((skus or [""])[0]),
                "first_missed_at_utc": "",
                "last_attempt_at_utc": "",
                "last_success_at_utc": "",
                "last_status": "",
                "miss_reason": "",
                "retry_count": "0",
                "active_flag": "0",
                "first_missing_utc": "",
                "last_attempt_utc": "",
                "last_success_utc": "",
                "attempt_count": "0",
                "rotation_skip_count": "0",
                "empty_response_count": "0",
                "api_error_count": "0",
                "detail_status_current": "",
                "detail_resolution_status": "",
                "priority_band": "",
                "force_attempt_next_run_flag": "0",
                "exhausted_flag": "0",
                "operator_reason": "",
                "marketplace_key": mp_key,
                "asin_key": asin_key,
            }
            idx = int(queue_df.index[-1])
            row_index_by_key[key] = idx

        attempt_count = _safe_int(queue_df.at[idx, "attempt_count"], default=0)
        rotation_skip_count = _safe_int(queue_df.at[idx, "rotation_skip_count"], default=0)
        empty_response_count = _safe_int(queue_df.at[idx, "empty_response_count"], default=0)
        api_error_count = _safe_int(queue_df.at[idx, "api_error_count"], default=0)

        if detail_status in {DETAIL_STATUS_OK, DETAIL_STATUS_EMPTY_RESPONSE, DETAIL_STATUS_API_ERROR} and selected_flag == "1":
            attempt_count += 1
        if detail_status == DETAIL_STATUS_SKIPPED_ROTATION:
            rotation_skip_count += 1
        elif detail_status == DETAIL_STATUS_EMPTY_RESPONSE:
            empty_response_count += 1
        elif detail_status == DETAIL_STATUS_API_ERROR:
            api_error_count += 1

        queue_df.at[idx, "marketplace"] = mp_key
        queue_df.at[idx, "asin"] = asin_key
        queue_df.at[idx, "sample_sku"] = _norm((skus or [""])[0]) or _norm(queue_df.at[idx, "sample_sku"])
        if selected_flag == "1":
            queue_df.at[idx, "last_attempt_at_utc"] = snapshot_ts
            queue_df.at[idx, "last_attempt_utc"] = snapshot_ts
        queue_df.at[idx, "last_status"] = detail_status
        queue_df.at[idx, "detail_status_current"] = detail_status
        queue_df.at[idx, "attempt_count"] = str(max(attempt_count, 0))
        queue_df.at[idx, "rotation_skip_count"] = str(max(rotation_skip_count, 0))
        queue_df.at[idx, "empty_response_count"] = str(max(empty_response_count, 0))
        queue_df.at[idx, "api_error_count"] = str(max(api_error_count, 0))

        detail_resolution_status = DETAIL_RESOLUTION_PENDING_RETRY
        active_flag = "1"
        force_attempt = "0"
        exhausted_flag = "0"
        priority_band = DETAIL_PRIORITY_NORMAL
        operator_reason = ""

        if detail_status == DETAIL_STATUS_OK:
            detail_resolution_status = DETAIL_RESOLUTION_RECOVERED
            active_flag = "0"
            priority_band = ""
            force_attempt = "0"
            exhausted_flag = "0"
            queue_df.at[idx, "miss_reason"] = ""
            queue_df.at[idx, "first_missed_at_utc"] = ""
            queue_df.at[idx, "first_missing_utc"] = ""
            queue_df.at[idx, "retry_count"] = "0"
            queue_df.at[idx, "last_success_at_utc"] = snapshot_ts
            queue_df.at[idx, "last_success_utc"] = snapshot_ts
        else:
            first_missing = _norm(queue_df.at[idx, "first_missing_utc"]) or _norm(queue_df.at[idx, "first_missed_at_utc"]) or snapshot_ts
            queue_df.at[idx, "miss_reason"] = detail_status
            queue_df.at[idx, "first_missed_at_utc"] = first_missing
            queue_df.at[idx, "first_missing_utc"] = first_missing
            queue_df.at[idx, "retry_count"] = str(max(attempt_count + rotation_skip_count, 1))

            if detail_status == DETAIL_STATUS_EMPTY_RESPONSE and empty_response_count >= empty_confirm_threshold:
                detail_resolution_status = DETAIL_RESOLUTION_AMAZON_EMPTY_CONFIRMED
                active_flag = "0"
                priority_band = ""
                operator_reason = f"empty_confirmed_after_{empty_response_count}"
            elif detail_status == DETAIL_STATUS_API_ERROR and api_error_count >= api_error_confirm_threshold:
                detail_resolution_status = DETAIL_RESOLUTION_API_ERROR_CONFIRMED
                active_flag = "0"
                priority_band = ""
                operator_reason = f"api_error_confirmed_after_{api_error_count}"
            elif detail_status in {DETAIL_STATUS_EMPTY_RESPONSE, DETAIL_STATUS_API_ERROR} and attempt_count >= retry_exhausted_threshold:
                detail_resolution_status = DETAIL_RESOLUTION_RETRY_EXHAUSTED
                active_flag = "0"
                exhausted_flag = "1"
                priority_band = ""
                operator_reason = f"retry_exhausted_after_{attempt_count}_attempts"
            else:
                if detail_status in {DETAIL_STATUS_EMPTY_RESPONSE, DETAIL_STATUS_API_ERROR}:
                    force_attempt = "1"
                    priority_band = DETAIL_PRIORITY_HIGH
                elif rotation_skip_count >= rotation_skip_threshold:
                    force_attempt = "1"
                    priority_band = DETAIL_PRIORITY_HIGH
                if detail_status == DETAIL_STATUS_SKIPPED_ROTATION:
                    operator_reason = f"rotation_retry_pending_after_{rotation_skip_count}_skips"
                else:
                    operator_reason = "pending_retry"

        queue_df.at[idx, "active_flag"] = active_flag
        queue_df.at[idx, "detail_resolution_status"] = detail_resolution_status
        queue_df.at[idx, "force_attempt_next_run_flag"] = force_attempt
        queue_df.at[idx, "priority_band"] = priority_band
        queue_df.at[idx, "exhausted_flag"] = exhausted_flag
        queue_df.at[idx, "operator_reason"] = operator_reason

        if detail_resolution_status == DETAIL_RESOLUTION_PENDING_RETRY:
            stats["resolution_pending_count"] += 1
        elif detail_resolution_status == DETAIL_RESOLUTION_RECOVERED:
            stats["resolution_recovered_count"] += 1
        elif detail_resolution_status == DETAIL_RESOLUTION_AMAZON_EMPTY_CONFIRMED:
            stats["resolution_amazon_empty_count"] += 1
        elif detail_resolution_status == DETAIL_RESOLUTION_API_ERROR_CONFIRMED:
            stats["resolution_api_error_count"] += 1
        else:
            stats["resolution_exhausted_count"] += 1

        resolution_by_asin[asin_key] = {
            "seller_detail_resolution_status": detail_resolution_status,
            "seller_detail_retry_attempt_count": str(max(attempt_count, 0)),
            "seller_detail_rotation_skip_count": str(max(rotation_skip_count, 0)),
            "seller_detail_empty_response_count": str(max(empty_response_count, 0)),
            "seller_detail_api_error_count": str(max(api_error_count, 0)),
            "seller_detail_force_attempt_flag": force_attempt,
            "seller_detail_retry_exhausted_flag": exhausted_flag,
            "seller_detail_operator_reason": operator_reason,
        }

    active_mask = queue_df.get("active_flag", "").astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y", "on"})
    stats["queue_active_count"] = int(active_mask.sum())
    queue_df = queue_df.drop(columns=["marketplace_key", "asin_key"], errors="ignore")
    return queue_df, stats, resolution_by_asin


def _refresh_offer_snapshots(
    now_utc: datetime,
    state: dict,
    target_skus: List[str] | None = None,
    *,
    item_offers_enabled: bool = True,
    stage_run_id: str = "",
    item_offers_subprocess_boundary: bool = True,
) -> dict:
    own_offer_stage_status = "not_run"
    item_offers_stage_status = "not_run"
    min_interval_sec = max(float(os.environ.get("H_REFRESH_MIN_SECONDS", "120") or "120"), 1.0)
    last_refresh = _to_dt(state.get("last_snapshot_refresh_utc", ""))
    if last_refresh is not None:
        elapsed = (now_utc - last_refresh).total_seconds()
        if elapsed < min_interval_sec:
            return {
                "snapshot_refresh_attempted": "0",
                "snapshot_refresh_status": "throttled",
                "snapshot_refresh_own_offer_status": own_offer_stage_status,
                "snapshot_refresh_item_offers_status": item_offers_stage_status,
            }

    sku_asin_rows = _active_sku_asin_rows(target_skus=target_skus)
    if not sku_asin_rows:
        return {
            "last_snapshot_refresh_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot_refresh_attempted": "1",
            "snapshot_refresh_status": "no_active_sku_rows",
            "snapshot_refresh_own_offer_status": own_offer_stage_status,
            "snapshot_refresh_item_offers_status": item_offers_stage_status,
        }
    snapshot_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_date = now_utc.strftime("%Y-%m-%d")
    run_id = _norm(stage_run_id) or _context_run_id()

    try:
        rows_out: List[Dict[str, str]] = []
        seller_rows_out: List[Dict[str, str]] = []
        prior_context_by_sku = _load_prior_listing_context(snapshot_date)
        prior_own_offer_by_market = _load_prior_own_offer_prices(snapshot_date)
        retry_queue_df = _load_item_offers_retry_queue()
        detail_ok_total = 0
        detail_skipped_total = 0
        detail_empty_total = 0
        detail_error_total = 0
        detail_resolution_pending_total = 0
        detail_resolution_recovered_total = 0
        detail_resolution_amazon_empty_total = 0
        detail_resolution_api_error_total = 0
        detail_resolution_exhausted_total = 0
        max_item_offers_asins_per_run = _env_int("SPAPI_ITEM_OFFERS_MAX_ASINS_PER_RUN", 15, min_value=1)
        refresh_started = time.monotonic()
        last_heartbeat = refresh_started
        last_status_log = refresh_started
        progress_state: dict[str, str] = {"stage": "init", "completed": "", "total": ""}
        heartbeat_stop = threading.Event()
        one_cycle_retry_enabled = is_truthy(os.environ.get("H_ITEM_OFFERS_ONE_CYCLE_RETRY_ENABLED", "1"))
        snapshot_refresh_timeout_seconds = (
            H_SNAPSHOT_REFRESH_ONE_CYCLE_TIMEOUT_SECONDS
            if one_cycle_retry_enabled
            else H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS
        )
        _log(
            "snapshot_refresh timeout_budget "
            f"base_seconds={int(H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS)} "
            f"effective_seconds={int(snapshot_refresh_timeout_seconds)} "
            f"one_cycle_retry_enabled={1 if one_cycle_retry_enabled else 0}"
        )

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
            if elapsed > snapshot_refresh_timeout_seconds:
                raise TimeoutError(
                    f"snapshot_refresh_timeout stage={stage} "
                    f"elapsed_seconds={_fmt(_r2(elapsed))} "
                    f"timeout_seconds={int(snapshot_refresh_timeout_seconds)}"
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
            asin_by_sku = {str(r["sku"]).strip().upper(): str(r.get("asin", "")).strip() for _, r in grp.iterrows()}
            asin_to_skus: Dict[str, List[str]] = {}
            for sku_key, asin_value in asin_by_sku.items():
                if not sku_key or not asin_value:
                    continue
                asin_to_skus.setdefault(asin_value, [])
                if sku_key not in asin_to_skus[asin_value]:
                    asin_to_skus[asin_value].append(sku_key)
            budget_plan = _compute_item_offers_budget_plan_for_marketplace(
                queue_df=retry_queue_df,
                marketplace_code=mp_code,
                candidate_asins=list(asin_to_skus.keys()),
                base_budget=max_item_offers_asins_per_run,
            )
            candidate_asins_count = int(budget_plan.get("candidate_asins_count", 0) or 0)
            effective_item_offers_budget = int(budget_plan.get("effective_item_offers_budget", 0) or 0)
            retry_priority_budget = int(budget_plan.get("retry_priority_budget", 0) or 0)
            active_pending_count = int(budget_plan.get("active_pending_count", 0) or 0)
            retry_selection = dict(budget_plan.get("retry_selection", {}) or {})
            prioritized_asins = [str(v).strip() for v in retry_selection.get("selected_asins", []) if str(v).strip()]
            if effective_item_offers_budget > max_item_offers_asins_per_run:
                _log(
                    "snapshot_refresh item_offers_budget_override "
                    f"marketplace={mp_code} "
                    f"candidate_asins={candidate_asins_count} "
                    f"base_budget={max_item_offers_asins_per_run} "
                    f"effective_budget={effective_item_offers_budget} "
                    f"active_pending_count={retry_selection.get('active_pending_count', 0)} "
                    "reason=one_cycle_retry"
                )
            _log(
                "snapshot_refresh retry_priority "
                f"marketplace={mp_code} "
                f"candidate_asins={candidate_asins_count} "
                f"prioritized_count={len(prioritized_asins)} "
                f"retry_budget={retry_priority_budget} "
                f"active_pending_count={retry_selection.get('active_pending_count', 0)} "
                f"protected_candidates={retry_selection.get('protected_candidate_count', 0)} "
                f"protected_selected={retry_selection.get('protected_selected_count', 0)} "
                f"protected_cap={retry_selection.get('protected_cap', 0)} "
                f"fairness_deferred={retry_selection.get('protected_fairness_deferred_count', 0)} "
                f"amazon_upstream_candidates={retry_selection.get('amazon_upstream_candidate_count', 0)}"
            )
            progress_state["stage"] = "own_offer_lookup"
            own_map: Dict[str, Dict[str, str]] = {}
            try:
                own_map = _run_own_offer_lookup_guarded(
                    skus=skus,
                    marketplace_id=mp_id,
                    run_id=run_id,
                    script_name=SOURCE,
                )
                own_offer_stage_status = "ok"
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
                boundary_failure = "own_offer_lookup_boundary_failure" in error_text.lower()
                if boundary_failure:
                    own_offer_stage_status = "failed"
                    _log(
                        "FATAL snapshot_refresh own_offer_lookup boundary_failure "
                        f"run_id={run_id} "
                        f"marketplace={mp_code} "
                        f"error={error_text}"
                    )
                    raise RuntimeError(
                        f"snapshot_refresh_own_offer_lookup_boundary_failure run_id={run_id} "
                        f"marketplace={mp_code} error={error_text}"
                    ) from exc
                if fallback_count > 0 and _is_nonfatal_own_offer_lock_contention(error_text):
                    own_offer_stage_status = "ok_with_cached_fallback"
                    _log(
                        "snapshot_refresh own_offer_lookup info "
                        f"marketplace={mp_code} "
                        "class=nonfatal_lock_contention "
                        f"error={error_text} "
                        f"fallback_cached_price_rows={fallback_count}"
                    )
                else:
                    own_offer_stage_status = "warning"
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
                    item_offers_watchdog_timeout_seconds = _resolve_item_offers_watchdog_timeout_seconds(
                        snapshot_refresh_timeout_seconds=snapshot_refresh_timeout_seconds,
                        base_timeout_seconds=H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS,
                        elapsed_seconds=max(time.monotonic() - refresh_started, 0.0),
                    )
                    if int(item_offers_watchdog_timeout_seconds) != int(H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS):
                        _log(
                            "snapshot_refresh item_offers watchdog_budget_override "
                            f"base_seconds={int(H_ITEM_OFFERS_LOOKUP_TIMEOUT_SECONDS)} "
                            f"effective_seconds={int(item_offers_watchdog_timeout_seconds)} "
                            f"snapshot_budget_seconds={int(snapshot_refresh_timeout_seconds)} "
                            f"elapsed_before_item_offers_seconds={int(max(time.monotonic() - refresh_started, 0.0))} "
                            f"candidate_asins={candidate_asins_count} "
                            f"effective_budget={effective_item_offers_budget}"
                        )
                    bb_map, offer_rows, detail_meta_by_asin = _run_item_offers_lookup_guarded(
                        sku_asins=sku_asins,
                        marketplace_id=mp_id,
                        snapshot_ts=snapshot_ts,
                        snapshot_date=snapshot_date,
                        run_id=run_id,
                        script_name=SOURCE,
                        subprocess_boundary=item_offers_subprocess_boundary,
                        prioritized_asins=prioritized_asins,
                        max_asins_override=effective_item_offers_budget,
                        timeout_seconds=item_offers_watchdog_timeout_seconds,
                    )
                    item_offers_stage_status = "ok"
                    _stage_exit(stage="item_offers", run_id=stage_run_id or run_id, started=item_stage_start, rc="0")
                except Exception:
                    item_offers_stage_status = "failed"
                    _stage_exit(stage="item_offers", run_id=stage_run_id or run_id, started=item_stage_start, rc="1")
                    raise
            else:
                item_stage_start = _stage_enter(stage="item_offers", run_id=stage_run_id or run_id)
                bb_map = {}
                offer_rows = []
                detail_meta_by_asin = {
                    asin: {
                        "detail_status": DETAIL_STATUS_SKIPPED_ROTATION,
                        "attempted_flag": "0",
                        "selected_flag": "0",
                        "offer_row_count": "0",
                        "summary_present_flag": "0",
                        "error": "item_offers_disabled",
                    }
                    for asin in asin_to_skus.keys()
                }
                item_offers_stage_status = "skipped_disabled"
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
            retry_queue_df, queue_stats, resolution_by_asin = _update_item_offers_retry_queue_for_marketplace(
                queue_df=retry_queue_df,
                marketplace_code=mp_code,
                snapshot_ts=snapshot_ts,
                asin_to_skus=asin_to_skus,
                detail_meta_by_asin=detail_meta_by_asin,
            )
            detail_ok_total += int(queue_stats.get("detail_ok_count", 0))
            detail_skipped_total += int(queue_stats.get("detail_skipped_count", 0))
            detail_empty_total += int(queue_stats.get("detail_empty_count", 0))
            detail_error_total += int(queue_stats.get("detail_error_count", 0))
            detail_resolution_pending_total += int(queue_stats.get("resolution_pending_count", 0))
            detail_resolution_recovered_total += int(queue_stats.get("resolution_recovered_count", 0))
            detail_resolution_amazon_empty_total += int(queue_stats.get("resolution_amazon_empty_count", 0))
            detail_resolution_api_error_total += int(queue_stats.get("resolution_api_error_count", 0))
            detail_resolution_exhausted_total += int(queue_stats.get("resolution_exhausted_count", 0))
            notes_by_sku = {str(r["sku"]).strip().upper(): str(r.get("notes", "")).strip() for _, r in grp.iterrows()}
            cached_own_prices = prior_own_offer_by_market.get(mp_code, {})
            cached_own_price_fallback_count = 0
            for sku in skus:
                sku_key = str(sku).strip().upper()
                prior_ctx = prior_context_by_sku.get(sku_key, {})
                bb = bb_map.get(sku_key, {})
                asin_key = asin_by_sku.get(sku_key, "")
                detail_meta = detail_meta_by_asin.get(asin_key, {}) if asin_key else {}
                resolution_meta = resolution_by_asin.get(asin_key, {}) if asin_key else {}
                detail_status = _norm(detail_meta.get("detail_status", "")) or DETAIL_STATUS_SKIPPED_ROTATION
                detail_attempted = _norm(detail_meta.get("attempted_flag", ""))
                if not detail_attempted:
                    detail_attempted = "1" if detail_status in {DETAIL_STATUS_OK, DETAIL_STATUS_EMPTY_RESPONSE, DETAIL_STATUS_API_ERROR} else "0"
                detail_offer_row_count = _norm(detail_meta.get("offer_row_count", "")) or "0"
                detail_resolution_status = _norm(resolution_meta.get("seller_detail_resolution_status", ""))
                if not detail_resolution_status:
                    detail_resolution_status = (
                        DETAIL_RESOLUTION_RECOVERED if detail_status == DETAIL_STATUS_OK else DETAIL_RESOLUTION_PENDING_RETRY
                    )
                retry_next_run_flag = "1" if detail_resolution_status == DETAIL_RESOLUTION_PENDING_RETRY else "0"
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
                    "asin": asin_key,
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
                    "seller_detail_status": detail_status,
                    "seller_detail_attempted_flag": detail_attempted,
                    "seller_detail_offer_row_count": detail_offer_row_count,
                    "seller_detail_snapshot_ts_utc": snapshot_ts if detail_attempted == "1" else "",
                    "seller_detail_resolution_status": detail_resolution_status,
                    "seller_detail_retry_attempt_count": _norm(resolution_meta.get("seller_detail_retry_attempt_count", "")),
                    "seller_detail_rotation_skip_count": _norm(resolution_meta.get("seller_detail_rotation_skip_count", "")),
                    "seller_detail_empty_response_count": _norm(resolution_meta.get("seller_detail_empty_response_count", "")),
                    "seller_detail_api_error_count": _norm(resolution_meta.get("seller_detail_api_error_count", "")),
                    "seller_detail_force_attempt_flag": _norm(resolution_meta.get("seller_detail_force_attempt_flag", "0")),
                    "seller_detail_retry_exhausted_flag": _norm(resolution_meta.get("seller_detail_retry_exhausted_flag", "0")),
                    "seller_detail_operator_reason": _norm(resolution_meta.get("seller_detail_operator_reason", "")),
                    "retry_next_run_flag": retry_next_run_flag,
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
            "seller_detail_status",
            "seller_detail_attempted_flag",
            "seller_detail_offer_row_count",
            "seller_detail_snapshot_ts_utc",
            "seller_detail_resolution_status",
            "seller_detail_retry_attempt_count",
            "seller_detail_rotation_skip_count",
            "seller_detail_empty_response_count",
            "seller_detail_api_error_count",
            "seller_detail_force_attempt_flag",
            "seller_detail_retry_exhausted_flag",
            "seller_detail_operator_reason",
            "retry_next_run_flag",
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
            "seller_detail_status",
            "seller_detail_attempted_flag",
            "seller_detail_offer_row_count",
            "seller_detail_snapshot_ts_utc",
            "seller_detail_resolution_status",
            "seller_detail_retry_attempt_count",
            "seller_detail_rotation_skip_count",
            "seller_detail_empty_response_count",
            "seller_detail_api_error_count",
            "seller_detail_force_attempt_flag",
            "seller_detail_retry_exhausted_flag",
            "seller_detail_operator_reason",
            "retry_next_run_flag",
            "source",
            "notes",
        ]
        listing_df = pd.DataFrame(rows_out, columns=listing_cols, dtype=str).fillna("")
        seller_df = pd.DataFrame(seller_rows_out, dtype=str).fillna("")
        seller_df = _with_seller_detail_columns(seller_df=seller_df, listing_df=listing_df)
        seller_df = seller_df.reindex(columns=seller_cols, fill_value="").fillna("")
        _persist_item_offers_retry_queue(retry_queue_df)

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
        retry_queue_active_now = int(
            retry_queue_df.get("active_flag", "").astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y", "on"}).sum()
        )
        _log(
            "snapshot_refresh detail_status_counts "
            f"detail_ok={detail_ok_total} "
            f"detail_skipped={detail_skipped_total} "
            f"detail_empty={detail_empty_total} "
            f"detail_error={detail_error_total} "
            f"pending_retry={detail_resolution_pending_total} "
            f"recovered={detail_resolution_recovered_total} "
            f"amazon_empty_confirmed={detail_resolution_amazon_empty_total} "
            f"api_error_confirmed={detail_resolution_api_error_total} "
            f"retry_exhausted={detail_resolution_exhausted_total} "
            f"queue_active={retry_queue_active_now}"
        )
        _log(f"snapshot_refresh ok listing_rows={len(listing_df.index)} seller_rows={len(seller_df.index)}")
        _log(f"snapshot_refresh timing elapsed_seconds={_fmt(_r2(time.monotonic() - refresh_started))}")
        status = "ok"
        return {
            "last_snapshot_refresh_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot_refresh_attempted": "1",
            "snapshot_refresh_status": status,
            "snapshot_refresh_own_offer_status": own_offer_stage_status,
            "snapshot_refresh_item_offers_status": item_offers_stage_status,
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
            "snapshot_refresh_own_offer_status": own_offer_stage_status,
            "snapshot_refresh_item_offers_status": item_offers_stage_status,
        }
    finally:
        try:
            heartbeat_stop.set()
        except Exception:
            pass


def _snapshot_worker_mode_enabled() -> bool:
    # Fail closed to inline snapshot refresh unless subprocess mode is
    # explicitly requested. The live H parent has been observed disappearing
    # mid snapshot-worker wait, which strands the run before publish.
    return os.environ.get("H_SNAPSHOT_WORKER_MODE", "0").strip() == "1"


def _snapshot_worker_contract_paths(run_id: str) -> tuple[Path, Path, Path]:
    token = f"{_norm(run_id)}.{os.getpid()}.{time.time_ns()}"
    contract_path = H_LIVE_DIR / f"snapshot_refresh_worker.contract.{token}.json"
    stdout_path = H_LIVE_DIR / f"snapshot_refresh_worker.stdout.{token}.log"
    stderr_path = H_LIVE_DIR / f"snapshot_refresh_worker.stderr.{token}.log"
    return contract_path, stdout_path, stderr_path


def _validate_snapshot_worker_contract(*, payload: dict, expected_run_id: str) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise RuntimeError("snapshot_worker_contract_invalid:not_object")
    run_id = _norm(payload.get("run_id", ""))
    if not run_id:
        raise RuntimeError("snapshot_worker_contract_invalid:missing_run_id")
    if _norm(expected_run_id) and run_id != _norm(expected_run_id):
        raise RuntimeError(
            f"snapshot_worker_contract_invalid:run_id_mismatch expected={_norm(expected_run_id)} actual={run_id}"
        )
    status = _norm(payload.get("status", "")).lower()
    if status == "failed":
        reason = _norm(payload.get("reason", "")) or "unknown"
        raise RuntimeError(f"snapshot_worker_contract_failed:{reason}")
    if status != "ok":
        raise RuntimeError(f"snapshot_worker_contract_invalid:unexpected_status:{status or 'missing'}")
    refresh_state_raw = payload.get("refresh_state", {})
    if not isinstance(refresh_state_raw, dict):
        raise RuntimeError("snapshot_worker_contract_invalid:missing_refresh_state")
    refresh_state = {str(k): _norm(v) for k, v in refresh_state_raw.items()}
    if _norm(refresh_state.get("snapshot_refresh_status", "")).lower() != "ok":
        reason = _norm(refresh_state.get("snapshot_refresh_error", "")) or _norm(refresh_state.get("snapshot_refresh_status", "")) or "unknown"
        raise RuntimeError(f"snapshot_worker_contract_failed:{reason}")
    outputs_raw = payload.get("required_output_paths", {})
    if not isinstance(outputs_raw, dict):
        raise RuntimeError("snapshot_worker_contract_invalid:missing_required_output_paths")
    required_output_keys = (
        "listing_offer_snapshot_latest",
        "listing_offer_seller_snapshot_latest",
        "listing_offer_history",
    )
    for key in required_output_keys:
        path_text = _norm(outputs_raw.get(key, ""))
        if not path_text:
            raise RuntimeError(f"snapshot_worker_contract_invalid:missing_output_path:{key}")
        if not Path(path_text).exists():
            raise RuntimeError(f"snapshot_worker_contract_invalid:output_missing:{key}")
    return refresh_state


def _build_snapshot_worker_missing_contract_payload(
    *,
    run_id: str,
    reason: str,
    checkpoint_last: str = "snapshot_worker_contract_missing_after_wait",
) -> dict:
    output_paths = {
        "listing_offer_snapshot_latest": str(OUT / "listing_offer_snapshot_latest.csv"),
        "listing_offer_seller_snapshot_latest": str(OUT / "listing_offer_seller_snapshot_latest.csv"),
        "listing_offer_history": str(LISTING_OFFER_HISTORY_PATH),
    }
    readiness = {
        key: ("1" if Path(path_text).exists() else "0")
        for key, path_text in output_paths.items()
    }
    refresh_state = {
        "snapshot_refresh_status": "failed",
        "snapshot_refresh_error": reason,
        "snapshot_refresh_own_offer_status": "",
        "snapshot_refresh_item_offers_status": "",
    }
    now_ts = _ts()
    return {
        "run_id": run_id,
        "status": "failed",
        "reason": reason,
        "worker_started_utc": now_ts,
        "worker_finished_utc": now_ts,
        "own_offer_status": "",
        "item_offers_status": "",
        "required_output_paths": output_paths,
        "readiness": readiness,
        "checkpoint_last": checkpoint_last,
        "error_class": "missing_contract_after_wait",
        "refresh_state": refresh_state,
    }


def _snapshot_worker_payload_incomplete_before_finalization(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    status = _norm(payload.get("status", "")).lower()
    reason = _norm(payload.get("reason", ""))
    if status != "failed":
        return False
    return reason == "snapshot_worker_incomplete_before_finalization"


def _run_snapshot_refresh_worker_subprocess(
    *,
    now_utc: datetime,
    run_id: str,
    item_offers_enabled: bool,
) -> dict[str, str]:
    payload: dict = {}
    proc: subprocess.CompletedProcess | None = None
    contract_path = Path()
    handoff_marker_active = False
    recovery_runs = H_SNAPSHOT_WORKER_CONTRACT_RECOVERY_RUNS
    attempts_used = 0
    for worker_run in range(1, recovery_runs + 1):
        contract_path, stdout_path, stderr_path = _snapshot_worker_contract_paths(run_id)
        cmd = [
            sys.executable,
            "-u",
            "-m",
            "scripts.cycles.run_H_pricing_cycle",
            "--snapshot-refresh-worker",
            "--snapshot-worker-run-id",
            str(run_id),
            "--snapshot-worker-now-utc",
            now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "--snapshot-worker-contract-path",
            str(contract_path),
            "--snapshot-worker-item-offers-enabled",
            "1" if item_offers_enabled else "0",
        ]
        _log(
            "snapshot_worker_spawned "
            f"run_id={run_id} "
            f"worker_run={worker_run} "
            f"worker_run_limit={recovery_runs} "
            f"stdout_path={stdout_path} "
            f"stderr_path={stderr_path} "
            f"contract_path={contract_path} "
            f"cmd={' '.join(str(part) for part in cmd)}"
        )
        proc = _run_subprocess_with_watchdog_redirected(
            cmd,
            timeout_seconds=H_SNAPSHOT_WORKER_TIMEOUT_SECONDS,
            cwd=ROOT,
            log_prefix="snapshot_refresh worker",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        _write_snapshot_worker_parent_handoff(
            run_id=run_id,
            worker_run=worker_run,
            worker_run_limit=recovery_runs,
            worker_rc=int(proc.returncode),
            contract_path=contract_path,
        )
        handoff_marker_active = True
        payload = {}
        attempts_used = 0
        payload_incomplete_before_finalization = False
        max_attempts = H_SNAPSHOT_WORKER_CONTRACT_WAIT_ATTEMPTS
        for attempt in range(1, max_attempts + 1):
            attempts_used = attempt
            if contract_path.exists():
                payload_candidate = _read_json(contract_path, default={})
                if isinstance(payload_candidate, dict) and payload_candidate:
                    payload = payload_candidate
                    payload_incomplete_before_finalization = _snapshot_worker_payload_incomplete_before_finalization(
                        payload_candidate
                    )
                    if payload_incomplete_before_finalization and attempt < max_attempts:
                        time.sleep(0.25)
                        continue
                    break
            if attempt < max_attempts:
                time.sleep(0.25)
        fallback_written = False
        if payload and not payload_incomplete_before_finalization:
            _log(
                "snapshot_worker_contract_read "
                f"run_id={run_id} "
                f"worker_run={worker_run} "
                f"worker_run_limit={recovery_runs} "
                f"contract_path={contract_path} "
                f"contract_exists={'1' if contract_path.exists() else '0'} "
                f"worker_rc={int(proc.returncode)} "
                f"attempts={attempts_used} "
                "fallback_written=0"
            )
            break
        if payload_incomplete_before_finalization:
            missing_reason = (
                "snapshot_worker_contract_incomplete_after_wait:"
                f"worker_rc={int(proc.returncode)}:worker_run={worker_run}:attempts={attempts_used}"
            )
        else:
            missing_reason = (
                "snapshot_worker_contract_missing_after_wait:"
                f"worker_rc={int(proc.returncode)}:worker_run={worker_run}:attempts={attempts_used}"
            )
        checkpoint_last = (
            "snapshot_worker_contract_incomplete_after_wait"
            if payload_incomplete_before_finalization
            else "snapshot_worker_contract_missing_after_wait"
        )
        fallback_payload = _build_snapshot_worker_missing_contract_payload(
            run_id=run_id,
            reason=missing_reason,
            checkpoint_last=checkpoint_last,
        )
        payload = fallback_payload
        try:
            _write_json(contract_path, fallback_payload)
            fallback_written = True
            _log(
                "snapshot_worker_contract_fallback_written "
                f"run_id={run_id} "
                f"worker_run={worker_run} "
                f"worker_run_limit={recovery_runs} "
                f"worker_rc={int(proc.returncode)} "
                f"contract_path={contract_path} "
                f"reason={missing_reason}"
            )
        except Exception as exc:
            payload = {}
            _log(
                "snapshot_worker_contract_fallback_write_failed "
                f"run_id={run_id} "
                f"worker_run={worker_run} "
                f"worker_run_limit={recovery_runs} "
                f"worker_rc={int(proc.returncode)} "
                f"contract_path={contract_path} "
                f"error={type(exc).__name__}:{exc}"
            )
        _log(
            "snapshot_worker_contract_read "
            f"run_id={run_id} "
            f"worker_run={worker_run} "
            f"worker_run_limit={recovery_runs} "
            f"contract_path={contract_path} "
            f"contract_exists={'1' if contract_path.exists() else '0'} "
            f"worker_rc={int(proc.returncode)} "
            f"attempts={attempts_used} "
            f"fallback_written={'1' if fallback_written else '0'}"
        )
        if int(proc.returncode) == 0 and worker_run < recovery_runs:
            _log(
                "snapshot_worker_contract_missing_retry "
                f"run_id={run_id} "
                f"worker_run={worker_run} "
                f"worker_run_limit={recovery_runs} "
                f"worker_rc={int(proc.returncode)} "
                f"contract_path={contract_path}"
            )
            continue
        if payload:
            break
        if int(proc.returncode) == 0:
            raise RuntimeError("snapshot_worker_contract_failed:missing_contract_after_worker_rc0")
        raise RuntimeError(
            f"snapshot_worker_contract_failed:missing_contract_after_worker_rc{int(proc.returncode)}"
        )
    try:
        refresh_state = _validate_snapshot_worker_contract(payload=payload, expected_run_id=run_id)
    except RuntimeError as exc:
        reason = _norm(str(exc))
        if reason.startswith("snapshot_worker_contract_failed:"):
            _log(f"snapshot_worker_contract_failed run_id={run_id} reason={reason}")
        else:
            _log(f"snapshot_worker_contract_invalid run_id={run_id} reason={reason}")
        _write_runtime_status(
            "ERROR",
            run_id=run_id,
            stage="snapshot_refresh",
            detail=f"snapshot_worker_contract_failure reason={reason}",
            error="SNAPSHOT_WORKER_CONTRACT_FAILURE",
        )
        _write_h_run_state(
            "failed",
            run_id=run_id,
            stage="snapshot_refresh",
            publish_status="not_started",
            failure_code="SNAPSHOT_WORKER_CONTRACT_FAILURE",
            failure_detail=reason[:500],
        )
        _log(f"parent_terminalization_after_snapshot_worker_failure run_id={run_id} reason={reason}")
        if handoff_marker_active:
            _clear_snapshot_worker_parent_handoff(run_id, reason="parent_handoff_terminal_failure")
        raise
    _log(
        "snapshot_worker_contract_valid "
        f"run_id={run_id} "
        f"snapshot_status={refresh_state.get('snapshot_refresh_status', '')} "
        f"own_offer_status={refresh_state.get('snapshot_refresh_own_offer_status', '')} "
        f"item_offers_status={refresh_state.get('snapshot_refresh_item_offers_status', '')}"
    )
    _log(
        "parent_continuation_after_snapshot_worker "
        f"run_id={run_id} "
        f"snapshot_status={refresh_state.get('snapshot_refresh_status', '')}"
    )
    if handoff_marker_active:
        _clear_snapshot_worker_parent_handoff(run_id, reason="parent_handoff_continuation")
    return refresh_state


def _run_snapshot_refresh_worker_entry(args: argparse.Namespace) -> int:
    run_id = _norm(getattr(args, "snapshot_worker_run_id", "")) or _resolve_cycle_run_id(_utc_now())
    now_utc_raw = _norm(getattr(args, "snapshot_worker_now_utc", ""))
    now_utc = _to_dt(now_utc_raw) or _utc_now()
    contract_path_raw = _norm(getattr(args, "snapshot_worker_contract_path", ""))
    if not contract_path_raw:
        raise SystemExit("snapshot_refresh_worker_missing_contract_path")
    contract_path = Path(contract_path_raw)
    item_offers_enabled = _norm(getattr(args, "snapshot_worker_item_offers_enabled", "1")) != "0"
    worker_started_utc = _ts()
    state = _read_state(default={})
    status = "failed"
    reason = ""
    error_class = ""
    checkpoint_last = "snapshot_worker_enter"
    refresh_state: dict[str, str] = {}
    output_paths = {
        "listing_offer_snapshot_latest": str(OUT / "listing_offer_snapshot_latest.csv"),
        "listing_offer_seller_snapshot_latest": str(OUT / "listing_offer_seller_snapshot_latest.csv"),
        "listing_offer_history": str(LISTING_OFFER_HISTORY_PATH),
    }
    bootstrap_reason = "snapshot_worker_incomplete_before_finalization"
    _write_json(
        contract_path,
        {
            "run_id": run_id,
            "status": "failed",
            "reason": bootstrap_reason,
            "worker_started_utc": worker_started_utc,
            "worker_finished_utc": worker_started_utc,
            "own_offer_status": "",
            "item_offers_status": "",
            "required_output_paths": output_paths,
            "readiness": {
                key: ("1" if Path(path_text).exists() else "0")
                for key, path_text in output_paths.items()
            },
            "checkpoint_last": "snapshot_worker_started",
            "error_class": "",
            "refresh_state": {
                "snapshot_refresh_status": "failed",
                "snapshot_refresh_error": bootstrap_reason,
                "snapshot_refresh_own_offer_status": "",
                "snapshot_refresh_item_offers_status": "",
            },
        },
    )
    try:
        _set_run_context(run_id)
        _log(
            "snapshot_worker_entry "
            f"run_id={run_id} "
            f"item_offers_enabled={'1' if item_offers_enabled else '0'} "
            f"contract_path={contract_path}"
        )
        refresh_state_raw = _refresh_offer_snapshots(
            now_utc,
            state,
            None,
            item_offers_enabled=item_offers_enabled,
            stage_run_id=run_id,
            item_offers_subprocess_boundary=True,
        )
        refresh_state = {str(k): _norm(v) for k, v in refresh_state_raw.items()}
        snapshot_status = _norm(refresh_state.get("snapshot_refresh_status", "")).lower()
        checkpoint_last = "snapshot_worker_refresh_done"
        if snapshot_status == "ok":
            status = "ok"
            reason = ""
        else:
            status = "failed"
            reason = _norm(refresh_state.get("snapshot_refresh_error", "")) or f"snapshot_refresh_status:{snapshot_status or 'missing'}"
    except BaseException as exc:
        error_class = type(exc).__name__
        reason = _norm(str(exc))[:500] or "snapshot_refresh_worker_exception"
        checkpoint_last = "snapshot_worker_exception"
        status = "failed"
    finally:
        readiness = {
            key: ("1" if Path(path_text).exists() else "0")
            for key, path_text in output_paths.items()
        }
        payload = {
            "run_id": run_id,
            "status": status,
            "reason": reason,
            "worker_started_utc": worker_started_utc,
            "worker_finished_utc": _ts(),
            "own_offer_status": _norm(refresh_state.get("snapshot_refresh_own_offer_status", "")),
            "item_offers_status": _norm(refresh_state.get("snapshot_refresh_item_offers_status", "")),
            "required_output_paths": output_paths,
            "readiness": readiness,
            "checkpoint_last": checkpoint_last,
            "error_class": error_class,
            "refresh_state": refresh_state,
        }
        _write_json(contract_path, payload)
        _log(
            "snapshot_worker_exit "
            f"run_id={run_id} "
            f"status={status} "
            f"reason={reason} "
            f"checkpoint_last={checkpoint_last} "
            f"contract_path={contract_path}"
        )
    return 0 if status == "ok" else 1


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
        write_dataframe_with_sql_compat(profile_df, SELLER_PROFILE_PATH, SQL_TABLE_SELLER_PROFILES)
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
        write_dataframe_with_sql_compat(soi_df, SELLER_SOI_PATH, SQL_TABLE_SELLER_SOI)
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
    write_dataframe_with_sql_compat(profile_df, SELLER_PROFILE_PATH, SQL_TABLE_SELLER_PROFILES)

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
    write_dataframe_with_sql_compat(soi_df, SELLER_SOI_PATH, SQL_TABLE_SELLER_SOI)

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
        "--snapshot-refresh-worker",
        action="store_true",
        help="Internal mode: run snapshot_refresh worker and write one final contract",
    )
    parser.add_argument("--snapshot-worker-run-id", default="", help="Internal mode run_id")
    parser.add_argument("--snapshot-worker-now-utc", default="", help="Internal mode timestamp (UTC)")
    parser.add_argument("--snapshot-worker-contract-path", default="", help="Internal mode contract output path")
    parser.add_argument(
        "--snapshot-worker-item-offers-enabled",
        choices=["0", "1"],
        default="1",
        help="Internal mode toggle for item_offers",
    )
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


def _phase1_pilot_contract_reconcile_eligibility(
    *,
    contract_class: str,
    marker_status: str,
    marker_reason: str,
    payload_present: bool,
    marker_result_ok: str,
) -> tuple[bool, str]:
    marker_status_norm = _norm(marker_status).lower()
    marker_reason_norm = _norm(marker_reason).lower()
    marker_result_ok_norm = _norm(marker_result_ok).lower()
    if contract_class == "completion_marker_missing":
        return True, "marker_missing_may_land_after_exit"
    if contract_class == "completion_marker_not_success":
        if marker_status_norm in {"", "invalid_json"}:
            return True, "marker_unreadable_or_empty"
        if marker_status_norm == "started":
            return True, "marker_started_may_settle_via_owner_handoff"
        if marker_status_norm == "failed":
            return False, "marker_failed_is_terminal"
        if "run_started" in marker_reason_norm:
            return True, "marker_run_started_may_settle_via_owner_handoff"
        return True, "marker_status_may_settle"
    if contract_class == "completion_marker_result_not_ok":
        if payload_present:
            return True, "payload_present_result_flag_may_settle"
        if marker_result_ok_norm in {"0", "false", ""}:
            return False, "result_not_ok_without_payload_is_terminal"
        return True, "result_flag_may_settle"
    if contract_class == "result_payload_missing":
        if marker_status_norm == "success":
            return True, "success_marker_waiting_for_payload"
        return False, "payload_missing_without_success_marker_is_terminal"
    return False, "contract_not_recoverable"


def _phase1_pilot_progress_grace_extension_seconds(
    *,
    elapsed: float,
    max_runtime_seconds: float,
    stalled_seconds: float,
    stall_timeout_seconds: float,
    progress_tail: str,
    progress_grace_used_seconds: float,
    progress_grace_chunk_seconds: float,
    progress_grace_max_seconds: float,
) -> tuple[float, str]:
    if elapsed < max_runtime_seconds:
        return 0.0, "below_max_runtime"
    if progress_grace_chunk_seconds <= 0.0 or progress_grace_max_seconds <= 0.0:
        return 0.0, "progress_grace_disabled"
    if progress_grace_used_seconds >= progress_grace_max_seconds:
        return 0.0, "progress_grace_exhausted"
    if stalled_seconds >= stall_timeout_seconds:
        return 0.0, "stall_timeout_reached"
    if not _norm(progress_tail):
        return 0.0, "no_progress_tail"
    remaining = max(progress_grace_max_seconds - progress_grace_used_seconds, 0.0)
    if remaining <= 0.0:
        return 0.0, "progress_grace_exhausted"
    return min(progress_grace_chunk_seconds, remaining), "recent_progress"


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
    parent_handoff_path = H_LIVE_DIR / f"phase1_pilot_parent_handoff.{run_id}.{os.getpid()}.{attempt_token}.json"
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
    try:
        if parent_handoff_path.exists():
            parent_handoff_path.unlink()
    except Exception:
        pass

    if requested_pilot_mode == "inline":
        _log(
            "phase1 pilot_step mode_override "
            "requested=inline effective=subprocess "
            "reason=inline_pilot_can_short_circuit_parent_before_publish"
        )

    cmd = [sys.executable, "-u", *pilot_argv]
    heartbeat_every_seconds = max(
        float(
            os.environ.get(
                "H_PHASE1_PARENT_HANDOFF_HEARTBEAT_SECONDS",
                "30",
            )
            or "30"
        ),
        1.0,
    )
    poll_seconds = 5.0
    _log(
        "phase1 pilot_step start "
        f"mode={pilot_mode} "
        f"requested_mode={requested_pilot_mode} "
        "stdio_mode=result_file_only "
        f"stall_timeout_seconds={int(PHASE1_PILOT_STALL_TIMEOUT_SECONDS)} "
        f"max_timeout_seconds={int(PHASE1_PILOT_MAX_TIMEOUT_SECONDS)} "
        f"progress_grace_seconds={int(PHASE1_PILOT_PROGRESS_GRACE_SECONDS)} "
        f"max_progress_grace_seconds={int(PHASE1_PILOT_MAX_PROGRESS_GRACE_SECONDS)} "
        f"read_only={'1' if read_only else '0'} "
        f"progress_path={progress_path} "
        f"result_path={result_path} "
        f"completion_marker_path={completion_marker_path} "
        f"parent_handoff_path={parent_handoff_path}"
    )
    start_monotonic = time.monotonic()
    last_heartbeat = start_monotonic
    last_progress_change = start_monotonic
    last_progress_tail = _tail_line(progress_path)
    max_runtime_deadline = PHASE1_PILOT_MAX_TIMEOUT_SECONDS
    progress_grace_used_seconds = 0.0
    env = os.environ.copy()
    env["H_RUN_ID"] = str(run_id)
    env["H_PHASE1_PROGRESS_PATH"] = str(progress_path)
    env["H_PHASE1_RESULT_PATH"] = str(result_path)
    env["H_PHASE1_COMPLETION_MARKER_PATH"] = str(completion_marker_path)
    env["H_PHASE1_PARENT_HANDOFF_PATH"] = str(parent_handoff_path)
    env["H_PHASE1_PARENT_PID"] = str(os.getpid())
    env["H_PHASE1_PARENT_HANDOFF_HEARTBEAT_SECONDS"] = _fmt(_r2(heartbeat_every_seconds))
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

    checkpoint_path = completion_marker_path.with_name(
        completion_marker_path.name.replace("complete.", "checkpoint.")
    )

    def _write_parent_handoff_signal(*, status: str, detail: str = "") -> None:
        try:
            payload = {
                "utc": _ts(),
                "run_id": _norm(run_id),
                "parent_pid": str(os.getpid()),
                "child_pid": str(proc.pid) if proc is not None else "",
                "status": _norm(status),
                "detail": _norm(detail),
                "completion_marker_path": str(completion_marker_path),
                "result_path": str(result_path),
            }
            _write_json(parent_handoff_path, payload)
        except Exception as exc:
            _log(
                "phase1 pilot_parent_handoff_write_failed "
                f"run_id={run_id} status={_norm(status)} "
                f"path={parent_handoff_path} error={type(exc).__name__}:{exc}"
            )
            return
        _append_h_parent_trace(
            "pilot_parent_handoff_write",
            run_id=run_id,
            status=_norm(status),
            detail=_norm(detail),
            child_pid=str(proc.pid) if proc is not None else "",
            path=str(parent_handoff_path),
        )
        _log(
            "phase1 pilot_parent_handoff_write "
            f"run_id={run_id} status={_norm(status)} "
            f"child_pid={str(proc.pid) if proc is not None else ''} "
            f"path={parent_handoff_path} detail={_norm(detail) or 'none'}"
        )

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
        popen_window_kwargs = _windows_hidden_subprocess_kwargs()
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=child_stdout,
            stderr=child_stderr,
            env=env,
            **popen_window_kwargs,
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
            completion_marker_path=completion_marker_path,
            result_path=result_path,
            checkpoint_path=checkpoint_path,
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
        _write_parent_handoff_signal(status="pilot_wait_entered", detail="child_wait_started")

        try:
            while True:
                if proc.poll() is not None:
                    break
                time.sleep(max(poll_seconds, 0.1))
                # Keep lock + runtime heartbeat current during long pilot waits.
                with contextlib.suppress(Exception):
                    _touch_lock_heartbeat()
                elapsed = time.monotonic() - start_monotonic
                progress_tail = _tail_line(progress_path)
                progress_advanced = progress_tail != last_progress_tail
                if progress_advanced:
                    last_progress_change = time.monotonic()
                    last_progress_tail = progress_tail
                stalled_for = time.monotonic() - last_progress_change
                timeout_reason = ""
                timeout_limit = 0.0
                if stalled_for >= PHASE1_PILOT_STALL_TIMEOUT_SECONDS:
                    timeout_reason = "stall"
                    timeout_limit = PHASE1_PILOT_STALL_TIMEOUT_SECONDS
                elif elapsed >= max_runtime_deadline:
                    extension_seconds, progress_grace_reason = _phase1_pilot_progress_grace_extension_seconds(
                        elapsed=elapsed,
                        max_runtime_seconds=max_runtime_deadline,
                        stalled_seconds=stalled_for,
                        stall_timeout_seconds=PHASE1_PILOT_STALL_TIMEOUT_SECONDS,
                        progress_tail=progress_tail,
                        progress_grace_used_seconds=progress_grace_used_seconds,
                        progress_grace_chunk_seconds=PHASE1_PILOT_PROGRESS_GRACE_SECONDS,
                        progress_grace_max_seconds=PHASE1_PILOT_MAX_PROGRESS_GRACE_SECONDS,
                    )
                    if extension_seconds > 0.0:
                        previous_deadline = max_runtime_deadline
                        progress_grace_used_seconds += extension_seconds
                        max_runtime_deadline += extension_seconds
                        progress_snapshot = _collect_wait_contract_snapshot()
                        _set_active_phase1_pilot_wait(
                            run_id=run_id,
                            status="active",
                            wait_checkpoint="pilot_wait_progress_grace",
                            child_pid=proc.pid,
                            detail=(
                                f"reason={progress_grace_reason} "
                                f"elapsed_seconds={_fmt(_r2(elapsed))} "
                                f"stalled_seconds={_fmt(_r2(stalled_for))} "
                                f"new_max_timeout_seconds={_fmt(_r2(max_runtime_deadline))}"
                            ),
                            last_known_child_state=progress_snapshot.get("last_known_child_state", ""),
                            result_exists=progress_snapshot.get("result_exists", "0"),
                            marker_status=progress_snapshot.get("marker_status", ""),
                            result_ok=progress_snapshot.get("result_ok", ""),
                            boundary_status=progress_snapshot.get("boundary_status", ""),
                        )
                        _append_h_parent_trace(
                            "pilot_wait_progress_grace",
                            run_id=run_id,
                            child_pid=proc.pid,
                            reason=progress_grace_reason,
                            elapsed_seconds=_fmt(_r2(elapsed)),
                            stalled_seconds=_fmt(_r2(stalled_for)),
                            progress_tail=progress_tail,
                            previous_max_timeout_seconds=_fmt(_r2(previous_deadline)),
                            extension_seconds=_fmt(_r2(extension_seconds)),
                            progress_grace_used_seconds=_fmt(_r2(progress_grace_used_seconds)),
                            new_max_timeout_seconds=_fmt(_r2(max_runtime_deadline)),
                            last_known_child_state=progress_snapshot.get("last_known_child_state", ""),
                            result_exists=progress_snapshot.get("result_exists", "0"),
                            marker_status=progress_snapshot.get("marker_status", ""),
                            result_ok=progress_snapshot.get("result_ok", ""),
                            boundary_status=progress_snapshot.get("boundary_status", ""),
                        )
                        _log(
                            "phase1 pilot_wait_progress_grace "
                            f"run_id={run_id} "
                            f"child_pid={proc.pid} "
                            f"reason={progress_grace_reason} "
                            f"elapsed_seconds={_fmt(_r2(elapsed))} "
                            f"stalled_seconds={_fmt(_r2(stalled_for))} "
                            f"previous_max_timeout_seconds={_fmt(_r2(previous_deadline))} "
                            f"extension_seconds={_fmt(_r2(extension_seconds))} "
                            f"progress_grace_used_seconds={_fmt(_r2(progress_grace_used_seconds))} "
                            f"new_max_timeout_seconds={_fmt(_r2(max_runtime_deadline))} "
                            f"progress_tail={progress_tail}"
                        )
                        _write_runtime_status(
                            "RUNNING",
                            run_id=run_id,
                            stage="phase1_pilot",
                            detail=(
                                "pilot_child_progress_grace "
                                f"pid={proc.pid} "
                                f"elapsed_seconds={_fmt(_r2(elapsed))} "
                                f"stalled_seconds={_fmt(_r2(stalled_for))} "
                                f"new_max_timeout_seconds={_fmt(_r2(max_runtime_deadline))}"
                            ),
                        )
                        last_heartbeat = time.monotonic()
                        continue
                    timeout_reason = "max_runtime"
                    timeout_limit = max_runtime_deadline
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
                            f"stalled_seconds={_fmt(_r2(stalled_for))} "
                            f"progress_grace_used_seconds={_fmt(_r2(progress_grace_used_seconds))} "
                            f"effective_max_timeout_seconds={_fmt(_r2(max_runtime_deadline))}"
                        ),
                    )
                    _append_h_parent_trace(
                        "pilot_wait_exit_abnormal",
                        run_id=run_id,
                        child_pid=proc.pid,
                        reason=f"timeout_{timeout_reason}",
                        elapsed_seconds=_fmt(_r2(elapsed)),
                        stalled_seconds=_fmt(_r2(stalled_for)),
                        progress_grace_used_seconds=_fmt(_r2(progress_grace_used_seconds)),
                        effective_max_timeout_seconds=_fmt(_r2(max_runtime_deadline)),
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
                        f"progress_grace_used_seconds={_fmt(_r2(progress_grace_used_seconds))} "
                        f"effective_max_timeout_seconds={_fmt(_r2(max_runtime_deadline))} "
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
                    _write_parent_handoff_signal(
                        status="pilot_wait_abnormal_exit",
                        detail=f"timeout_{timeout_reason}",
                    )
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
                        f"effective_max_timeout_seconds={int(max_runtime_deadline)} "
                        f"progress_grace_used_seconds={int(progress_grace_used_seconds)} "
                        f"progress_tail={progress_tail}"
                    )
                if elapsed - last_heartbeat >= heartbeat_every_seconds:
                    poll_snapshot = _collect_wait_contract_snapshot()
                    heartbeat_detail = (
                        f"elapsed_seconds={_fmt(_r2(elapsed))} "
                        f"stalled_seconds={_fmt(_r2(stalled_for))} "
                        f"progress_advanced={'1' if progress_advanced else '0'}"
                    )
                    _set_active_phase1_pilot_wait(
                        run_id=run_id,
                        status="active",
                        wait_checkpoint="pilot_wait_poll",
                        child_pid=proc.pid,
                        detail=heartbeat_detail,
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
                    _write_parent_handoff_signal(status="pilot_wait_heartbeat", detail=heartbeat_detail)
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
            _write_parent_handoff_signal(status="pilot_wait_abnormal_exit", detail=reason)
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
    _write_parent_handoff_signal(status="pilot_wait_exit_observed", detail="child_wait_completed")

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
        return _phase1_pilot_contract_reconcile_eligibility(
            contract_class=contract_class,
            marker_status=marker_status,
            marker_reason=marker_reason,
            payload_present=bool(payload_text),
            marker_result_ok=marker_result_ok,
        )

    def _short_completion_recheck_eligible(contract_class: str) -> tuple[bool, str]:
        if PHASE1_PILOT_COMPLETION_RECHECK_SECONDS <= 0:
            return False, "disabled"
        marker_status_norm = _norm(marker_status).lower()
        if contract_class == "completion_marker_not_success" and marker_status_norm == "started":
            return True, "marker_status_started"
        if contract_class in {"result_payload_missing", "completion_marker_result_not_ok"} and not payload_text:
            return True, "result_missing_after_child_exit"
        return False, "not_needed"

    def _run_short_completion_recheck(reason: str, contract_class: str) -> None:
        nonlocal result_path
        nonlocal marker_exists
        nonlocal marker_status
        nonlocal marker_reason
        nonlocal marker_run_id
        nonlocal marker_result_ok
        nonlocal result_exists
        nonlocal result_size
        nonlocal payload_text
        nonlocal payload_source
        interval = PHASE1_PILOT_COMPLETION_RECHECK_INTERVAL_SECONDS
        attempts = max(1, int(PHASE1_PILOT_COMPLETION_RECHECK_SECONDS / interval))
        _append_h_parent_trace(
            "pilot_completion_recheck_enter",
            run_id=run_id,
            reason=reason,
            initial_contract_class=contract_class,
            initial_marker_status=marker_status or "none",
            initial_result_exists="1" if result_exists else "0",
            initial_payload_ready="1" if bool(payload_text) else "0",
            max_attempts=str(attempts),
        )
        _log(
            "phase1 pilot_step completion_recheck_enter "
            f"run_id={run_id} "
            f"reason={reason} "
            f"contract_class={contract_class} "
            f"max_attempts={attempts} "
            f"interval_seconds={_fmt(_r2(interval))} "
            f"window_seconds={_fmt(_r2(PHASE1_PILOT_COMPLETION_RECHECK_SECONDS))}"
        )
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                time.sleep(interval)
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
            if result_exists:
                try:
                    payload_text = result_path.read_text(encoding="utf-8").strip()
                    if payload_text:
                        payload_source = "result_file"
                except Exception:
                    payload_text = ""
            _log(
                "phase1 pilot_step completion_recheck_attempt "
                f"run_id={run_id} "
                f"attempt={attempt}/{attempts} "
                f"marker_exists={'1' if marker_exists else '0'} "
                f"marker_status={marker_status or 'none'} "
                f"marker_result_ok={marker_result_ok or 'none'} "
                f"result_exists={'1' if result_exists else '0'} "
                f"result_size={result_size} "
                f"payload_ready={'1' if bool(payload_text) else '0'}"
            )

    def _cycle_rc_settle_eligible(contract_class: str) -> tuple[bool, str]:
        if not contract_class or PHASE1_PILOT_CYCLE_RC_SETTLE_SECONDS <= 0:
            return False, "disabled_or_not_needed"
        if int(child_rc_raw) != 0:
            return False, "child_rc_nonzero_terminal"
        if contract_class in {
            "completion_marker_not_success",
            "completion_marker_result_not_ok",
            "result_payload_missing",
            "completion_marker_missing",
        }:
            return True, "late_terminal_artifacts_possible"
        return False, "contract_not_supported"

    def _run_cycle_rc_settle(reason: str, contract_class: str) -> None:
        nonlocal result_path
        nonlocal marker_exists
        nonlocal marker_status
        nonlocal marker_reason
        nonlocal marker_run_id
        nonlocal marker_result_ok
        nonlocal result_exists
        nonlocal result_size
        nonlocal payload_text
        nonlocal payload_source
        nonlocal contract_error
        nonlocal contract_reason
        interval = PHASE1_PILOT_CYCLE_RC_SETTLE_INTERVAL_SECONDS
        attempts = max(1, int(PHASE1_PILOT_CYCLE_RC_SETTLE_SECONDS / interval))
        last_cycle_settle_heartbeat = time.monotonic()
        _log(
            "cycle_rc_settle_enter "
            f"run_id={run_id} "
            f"reason={reason} "
            f"initial_contract_class={contract_class} "
            f"initial_marker_status={marker_status or 'none'} "
            f"initial_result_exists={'1' if result_exists else '0'} "
            f"initial_payload_ready={'1' if bool(payload_text) else '0'} "
            f"max_attempts={attempts} "
            f"interval_seconds={_fmt(_r2(interval))} "
            f"window_seconds={_fmt(_r2(PHASE1_PILOT_CYCLE_RC_SETTLE_SECONDS))}"
        )
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                time.sleep(interval)
            now_cycle_settle = time.monotonic()
            if now_cycle_settle - last_cycle_settle_heartbeat >= 5.0:
                _refresh_runtime_status_heartbeat()
                last_cycle_settle_heartbeat = now_cycle_settle
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
            if result_exists:
                try:
                    payload_text = result_path.read_text(encoding="utf-8").strip()
                    if payload_text:
                        payload_source = "result_file"
                except Exception:
                    payload_text = ""
            contract_error, contract_reason = _evaluate_contract()
            _log(
                "cycle_rc_settle_attempt "
                f"run_id={run_id} "
                f"attempt={attempt}/{attempts} "
                f"contract_class={contract_error or 'ok'} "
                f"marker_status={marker_status or 'none'} "
                f"marker_result_ok={marker_result_ok or 'none'} "
                f"result_exists={'1' if result_exists else '0'} "
                f"result_size={result_size} "
                f"payload_ready={'1' if bool(payload_text) else '0'}"
            )
            if not contract_error:
                _log(
                    "cycle_rc_settle_success "
                    f"run_id={run_id} "
                    f"attempt={attempt} "
                    f"marker_status={marker_status or 'none'} "
                    f"result_exists={'1' if result_exists else '0'} "
                    f"payload_source={payload_source or 'none'}"
                )
                _log(
                    "cycle_rc_final_classification "
                    f"run_id={run_id} "
                    "final_classification=success "
                    f"marker_status={marker_status or 'none'} "
                    f"result_exists={'1' if result_exists else '0'} "
                    f"payload_ready={'1' if bool(payload_text) else '0'}"
                )
                return
        _log(
            "cycle_rc_settle_timeout "
            f"run_id={run_id} "
            f"attempts={attempts} "
            f"final_contract_class={contract_error or 'ok'} "
            f"marker_status={marker_status or 'none'} "
            f"result_exists={'1' if result_exists else '0'} "
            f"payload_ready={'1' if bool(payload_text) else '0'}"
        )
        _log(
            "cycle_rc_final_classification "
            f"run_id={run_id} "
            "final_classification=failed "
            f"final_contract_class={contract_error or 'ok'} "
            f"marker_status={marker_status or 'none'} "
            f"result_exists={'1' if result_exists else '0'} "
            f"payload_ready={'1' if bool(payload_text) else '0'}"
        )

    contract_error, contract_reason = _evaluate_contract()
    short_recheck_allowed, short_recheck_reason = _short_completion_recheck_eligible(contract_error)
    if short_recheck_allowed:
        _run_short_completion_recheck(short_recheck_reason, contract_error)
        contract_error, contract_reason = _evaluate_contract()
        _append_h_parent_trace(
            "pilot_completion_recheck_result",
            run_id=run_id,
            reason=short_recheck_reason,
            final_contract_class=contract_error or "ok",
            final_marker_status=marker_status or "none",
            final_result_exists="1" if result_exists else "0",
            final_payload_ready="1" if bool(payload_text) else "0",
        )
        _log(
            "phase1 pilot_step completion_recheck_result "
            f"run_id={run_id} "
            f"reason={short_recheck_reason} "
            f"final_contract_class={contract_error or 'ok'} "
            f"marker_status={marker_status or 'none'} "
            f"result_exists={'1' if result_exists else '0'} "
            f"payload_ready={'1' if bool(payload_text) else '0'}"
        )
    reconcile_allowed, reconcile_reason = _contract_reconcile_eligible(contract_error)
    post_exit_handoff_reconcile_enabled = _to_bool(
        os.environ.get("H_PHASE1_PILOT_POST_EXIT_HANDOFF_RECONCILE_ENABLE", "0"),
        default=False,
    )
    if reconcile_allowed and not post_exit_handoff_reconcile_enabled:
        _log(
            "phase1 pilot_step handoff_reconcile_disabled "
            f"run_id={run_id} "
            f"contract_class={contract_error or 'ok'} "
            f"marker_status={marker_status or 'none'} "
            f"result_exists={'1' if result_exists else '0'} "
            "policy=single_owner_authority"
        )
        reconcile_allowed = False
        reconcile_reason = "disabled_single_owner_authority"
    if reconcile_allowed:
        handoff_deadline = time.monotonic() + PHASE1_PILOT_POST_EXIT_HANDOFF_WAIT_SECONDS
        last_handoff_heartbeat = time.monotonic()
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
            now_handoff = time.monotonic()
            if now_handoff - last_handoff_heartbeat >= 5.0:
                _refresh_runtime_status_heartbeat()
                last_handoff_heartbeat = now_handoff
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
    cycle_settle_allowed, cycle_settle_reason = _cycle_rc_settle_eligible(contract_error)
    if cycle_settle_allowed:
        _run_cycle_rc_settle(cycle_settle_reason, contract_error)
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
        payload_retry_done = False
        if PHASE1_PILOT_COMPLETION_RECHECK_SECONDS > 0 and result_exists:
            payload_retry_done = True
            _run_short_completion_recheck("result_payload_invalid_after_child_exit", "result_payload_invalid_json")
            try:
                payload = json.loads(payload_text)
            except Exception:
                payload = None
            _append_h_parent_trace(
                "pilot_completion_recheck_result",
                run_id=run_id,
                reason="result_payload_invalid_after_child_exit",
                final_contract_class="result_payload_invalid_json" if payload is None else "ok",
                final_marker_status=marker_status or "none",
                final_result_exists="1" if result_exists else "0",
                final_payload_ready="1" if bool(payload_text) else "0",
            )
            _log(
                "phase1 pilot_step completion_recheck_result "
                f"run_id={run_id} "
                "reason=result_payload_invalid_after_child_exit "
                f"final_contract_class={'result_payload_invalid_json' if payload is None else 'ok'} "
                f"marker_status={marker_status or 'none'} "
                f"result_exists={'1' if result_exists else '0'} "
                f"payload_ready={'1' if bool(payload_text) else '0'}"
            )
            if isinstance(payload, dict):
                return {str(k): str(v) for k, v in payload.items()}
        _log(
            "phase1 pilot_step rc_promoted "
            f"rc_raw={child_rc_raw} "
            "rc_effective=91 "
            "class=result_payload_invalid_json "
            "reason="
            f"payload_source={payload_source} result_path={result_path} "
            f"recheck={'1' if payload_retry_done else '0'} error={exc}"
        )
        raise RuntimeError(
            "phase1 pilot completion contract failed "
            "(class=result_payload_invalid_json "
            f"rc_raw={child_rc_raw} rc_effective=91 "
            f"payload_source={'stdout' if lines else ('result_file' if result_exists else 'none')} "
            f"result_path={result_path} recheck={'1' if payload_retry_done else '0'} error={exc})"
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


def _windows_hidden_subprocess_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {}
    if os.name != "nt":
        return kwargs
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if creationflags:
        kwargs["creationflags"] = creationflags
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0))
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
        kwargs["startupinfo"] = startupinfo
    except Exception:
        pass
    return kwargs


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
    popen_window_kwargs = _windows_hidden_subprocess_kwargs()
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
            **popen_window_kwargs,
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


def _run_subprocess_with_watchdog_redirected(
    cmd: List[str],
    *,
    timeout_seconds: float,
    cwd: Path | None = None,
    log_prefix: str = "",
    heartbeat_every_seconds: float = 30.0,
    poll_seconds: float = 5.0,
    env_overrides: dict[str, str] | None = None,
    stdout_path: Path,
    stderr_path: Path,
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
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    popen_window_kwargs = _windows_hidden_subprocess_kwargs()
    proc: subprocess.Popen[str] | None = None
    start = time.monotonic()
    last_heartbeat = start
    try:
        with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_fh, stderr_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as stderr_fh:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd or ROOT),
                stdout=stdout_fh,
                stderr=stderr_fh,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                **popen_window_kwargs,
            )
            if log_prefix:
                _log(
                    f"{log_prefix} watchdog_child_launch "
                    f"child_pid={int(proc.pid)} "
                    f"stdout_path={stdout_path} "
                    f"stderr_path={stderr_path}"
                )
                _log(
                    f"{log_prefix} watchdog_wait_start "
                    f"child_pid={int(proc.pid)}"
                )
            poll_interval = max(0.1, min(float(poll_seconds), 5.0))
            while True:
                rc = proc.poll()
                if rc is not None:
                    break
                now = time.monotonic()
                elapsed = now - start
                with contextlib.suppress(Exception):
                    _refresh_runtime_status_heartbeat()
                if elapsed >= float(timeout_seconds):
                    _write_watchdog_kill_marker(
                        log_prefix=log_prefix or "subprocess",
                        pid=int(proc.pid),
                        elapsed_seconds=elapsed,
                        timeout_seconds=timeout_seconds,
                        cmd=cmd,
                    )
                    with contextlib.suppress(Exception):
                        proc.terminate()
                    with contextlib.suppress(Exception):
                        proc.wait(timeout=3.0)
                    if proc.poll() is None:
                        with contextlib.suppress(Exception):
                            proc.kill()
                        with contextlib.suppress(Exception):
                            proc.wait(timeout=3.0)
                    _write_watchdog_marker(
                        name="WATCHDOG_EXIT.txt",
                        log_prefix=log_prefix or "subprocess",
                        details="rc=124 reason=timeout_expired",
                    )
                    stdout_tail = _tail_line(stdout_path)
                    stderr_tail = _tail_line(stderr_path)
                    if log_prefix:
                        _log(
                            f"{log_prefix} watchdog_timeout "
                            f"child_pid={int(proc.pid)} "
                            f"timeout_seconds={int(timeout_seconds)} "
                            f"stdout_tail={stdout_tail} "
                            f"stderr_tail={stderr_tail}"
                        )
                    timeout_note = (
                        f"watchdog_timeout_seconds={int(timeout_seconds)};"
                        f"log_prefix={log_prefix or 'subprocess'}"
                    )
                    stderr_text = f"{stderr_tail}\n{timeout_note}".strip()
                    return subprocess.CompletedProcess(cmd, 124, stdout_tail, stderr_text)
                if heartbeat_every_seconds > 0 and (now - last_heartbeat) >= float(heartbeat_every_seconds):
                    if log_prefix:
                        _log(
                            f"{log_prefix} watchdog_wait_heartbeat "
                            f"child_pid={int(proc.pid)} "
                            f"elapsed_seconds={elapsed:.1f}"
                        )
                    last_heartbeat = now
                time.sleep(poll_interval)
            return_code = int(proc.returncode or 0)
            _write_watchdog_marker(
                name="WATCHDOG_EXIT.txt",
                log_prefix=log_prefix or "subprocess",
                details=f"rc={return_code} reason=popen_done",
            )
            stdout_tail = _tail_line(stdout_path)
            stderr_tail = _tail_line(stderr_path)
            if log_prefix:
                _log(
                    f"{log_prefix} watchdog_wait_end "
                    f"child_pid={int(proc.pid)} "
                    f"rc={return_code}"
                )
                _log(
                    f"{log_prefix} watchdog_run_end "
                    f"rc={return_code} "
                    f"stdout_tail={stdout_tail} "
                    f"stderr_tail={stderr_tail}"
                )
            return subprocess.CompletedProcess(cmd, return_code, stdout_tail, stderr_tail)
    except Exception as exc:
        if log_prefix:
            _log(
                f"{log_prefix} watchdog_run_exception "
                f"error={type(exc).__name__}:{exc} "
                f"stdout_path={stdout_path} "
                f"stderr_path={stderr_path} "
                f"child_pid={int(proc.pid) if proc and proc.pid else 0}"
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
    target_gate_path = H_PRIMARY_CHECKLIST_PATH
    before_mtime = _mtime_seconds(target_gate_path)
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
        str(target_gate_path),
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
    after_mtime = _mtime_seconds(target_gate_path)
    fresh = bool(after_mtime is not None and (before_mtime is None or after_mtime > before_mtime))
    rc = int(proc_returncode)
    if rc == 1 and not fresh:
        rc = 2
    counts = _checklist_counts(target_gate_path)
    fail_count = counts[0] if counts is not None else -1
    warn_count = counts[1] if counts is not None else -1
    out = {
        "rc": str(rc),
        "fresh": "1" if fresh else "0",
        "snapshot_utc": _checklist_snapshot_utc(target_gate_path),
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
        "h_gate_pending_fail_count": "0",
        "h_gate_pending_warn_count": "0",
        "h_gate_block_live_writes": "0",
        "h_gate_snapshot_utc": "",
        "h_gate_checklist_snapshot_utc": "",
        "h_gate_checklist_fail_count": "",
        "h_gate_checklist_warn_count": "",
        "h_gate_condition_status": "unknown",
        "h_gate_active_source": "",
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
    checklist_fail_count = fail_count
    checklist_warn_count = warn_count
    checklist_snapshot_utc = snapshot_utc
    pending_fail_count = 0
    pending_warn_count = 0
    checklist_age_seconds = _file_age_seconds(gate_checklist_path, now_utc)
    checklist_stale = bool(checklist_age_seconds is None or checklist_age_seconds > H_CHECKLIST_MAX_AGE_SECONDS)
    # In shadow mode, report active state from H-owned live artifacts.
    # Checklist non-ok rows become pending_recheck when live truth is clean.
    if mode == "shadow" and not H_HEALTH_RUN_INLINE:
        live_fail, live_warn, live_notes = _h_shadow_live_artifact_counts(now_utc)
        if readable and checklist_fail_count > 0 and live_fail <= 0:
            pending_fail_count = checklist_fail_count
        if readable and checklist_warn_count > 0 and live_warn <= 0:
            pending_warn_count = checklist_warn_count
        fail_count = live_fail
        warn_count = live_warn
        readable = True
        snapshot_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        gate_checklist_source = "live_artifact_freshness_shadow"
        state["h_gate_shadow_live_notes"] = _norm(live_notes)
        state["h_gate_shadow_checklist_fail_count"] = "" if checklist_fail_count < 0 else str(checklist_fail_count)
        state["h_gate_shadow_checklist_warn_count"] = "" if checklist_warn_count < 0 else str(checklist_warn_count)
        _log(
            "split_health_shadow_live_fallback "
            f"fail={fail_count} warn={warn_count} "
            f"checklist_stale={'1' if checklist_stale else '0'} "
            f"checklist_age_s={_fmt(_r2(checklist_age_seconds if checklist_age_seconds is not None else -1))} "
            f"pending_fail={pending_fail_count} pending_warn={pending_warn_count} "
            f"notes={_norm(live_notes)}"
        )

    block_live_writes = False
    if mode == "split":
        if not readable:
            block_live_writes = H_HEALTH_FAIL_CLOSED
        elif fail_count > 0:
            block_live_writes = True

    payload["h_gate_fail_count"] = "" if fail_count < 0 else str(fail_count)
    payload["h_gate_warn_count"] = "" if warn_count < 0 else str(warn_count)
    payload["h_gate_pending_fail_count"] = str(max(pending_fail_count, 0))
    payload["h_gate_pending_warn_count"] = str(max(pending_warn_count, 0))
    payload["h_gate_snapshot_utc"] = snapshot_utc
    payload["h_gate_checklist_snapshot_utc"] = checklist_snapshot_utc
    payload["h_gate_checklist_fail_count"] = "" if checklist_fail_count < 0 else str(checklist_fail_count)
    payload["h_gate_checklist_warn_count"] = "" if checklist_warn_count < 0 else str(checklist_warn_count)
    payload["h_gate_block_live_writes"] = "1" if block_live_writes else "0"
    payload["h_gate_checklist_source"] = gate_checklist_source
    payload["h_gate_active_source"] = gate_checklist_source
    payload["h_gate_checklist_path"] = str(gate_checklist_path)
    sample_snapshot = _h_strategy_sample_size_live_snapshot(
        H_STRATEGY_OUTCOME_DAILY_PATH,
        checklist_snapshot_utc,
    )
    for key, value in sample_snapshot.items():
        payload[key] = value
        state[key] = value
    if not readable:
        payload["h_gate_condition_status"] = "unreadable"
    elif fail_count > 0:
        payload["h_gate_condition_status"] = "active_fail"
    elif warn_count > 0:
        payload["h_gate_condition_status"] = "active_warn"
    elif pending_fail_count > 0 or pending_warn_count > 0:
        payload["h_gate_condition_status"] = "pending_recheck"
    else:
        payload["h_gate_condition_status"] = "ok"

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
            f"pending_fail={payload['h_gate_pending_fail_count']} pending_warn={payload['h_gate_pending_warn_count']} "
            f"block_live_writes={payload['h_gate_block_live_writes']} "
            f"condition={payload['h_gate_condition_status']} "
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
    popen_window_kwargs = _windows_hidden_subprocess_kwargs()
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=stdout_capture,
        stderr=stderr_capture,
        text=True,
        env={**os.environ.copy(), **intel_env},
        **popen_window_kwargs,
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
    requested_publish_mode = _effective_phase1_mode(H_PHASE1_PUBLISH_MODE)
    publish_mode = "subprocess"
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
    if requested_publish_mode != publish_mode:
        _log(
            "phase1 observation_publish mode_override "
            f"requested={requested_publish_mode} "
            f"effective={publish_mode} "
            "reason=inline_publish_boundary_can_terminate_parent_before_commit"
        )
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


def _run_phase1_observation_status_publish_subprocess(
    *,
    now_utc: datetime,
    run_id: str,
    stage_env: dict[str, str] | None = None,
    reason: str = "",
) -> dict[str, str]:
    if not PHASE1_OBSERVATION_STATUS_PUBLISH_ENABLED:
        return {
            "phase1_observation_status_publish_status": "skipped_disabled",
            "phase1_observation_status_publish_run_id": run_id,
            "phase1_observation_status_publish_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "phase1_observation_status_publish_reason": reason,
        }
    publish_script = resolve_script_path(ROOT / "scripts", "H130_build_phase1_observation_sheet.py")
    publish_argv = [
        str(publish_script),
        "--publish",
        "--status-only",
        "--date-utc",
        now_utc.date().isoformat(),
    ]
    if PHASE1_OBSERVATION_SHEET_ID:
        publish_argv.extend(["--sheet-id", PHASE1_OBSERVATION_SHEET_ID])
    cmd = [sys.executable, *publish_argv]
    proc = _run_subprocess_with_watchdog(
        cmd,
        timeout_seconds=PHASE1_OBSERVATION_STATUS_PUBLISH_TIMEOUT_SECONDS,
        cwd=ROOT,
        log_prefix="phase1 status_publish",
        env_overrides=stage_env,
    )
    parsed = _parse_key_value_lines(proc.stdout or "")
    status = "ok" if proc.returncode == 0 else "failed"
    stderr_text = _norm(proc.stderr or "")
    stdout_text = _norm(proc.stdout or "")
    error_summary = stderr_text or stdout_text
    payload = {
        "phase1_observation_status_publish_status": status,
        "phase1_observation_status_publish_run_id": run_id,
        "phase1_observation_status_publish_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase1_observation_status_publish_reason": reason,
        "phase1_observation_status_publish_sheet_id": parsed.get("phase1_observation_sheet_id", ""),
        "phase1_observation_status_publish_status_tab": parsed.get("phase1_observation_ops_status_tab", ""),
        "phase1_observation_status_publish_alerts_tab": parsed.get("phase1_observation_ops_alerts_tab", ""),
        "phase1_observation_status_publish_alert_rows": parsed.get("phase1_observation_ops_alert_rows", ""),
    }
    if status != "ok":
        payload["phase1_observation_status_publish_error"] = error_summary[:400]
    return payload


def _run_phase1_observation_status_publish_nonblocking(
    *,
    now_utc: datetime,
    run_id: str,
    stage_env: dict[str, str] | None = None,
    reason: str = "",
) -> dict[str, str]:
    try:
        payload = _run_phase1_observation_status_publish_subprocess(
            now_utc=now_utc,
            run_id=run_id,
            stage_env=stage_env,
            reason=reason,
        )
    except Exception as exc:
        _log(f"phase1 status_publish error reason={reason or 'unspecified'} {type(exc).__name__}: {exc}")
        return {
            "phase1_observation_status_publish_status": "failed",
            "phase1_observation_status_publish_run_id": run_id,
            "phase1_observation_status_publish_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "phase1_observation_status_publish_reason": reason,
            "phase1_observation_status_publish_error": f"{type(exc).__name__}:{exc}"[:400],
        }
    _log(
        "phase1 status_publish "
        f"reason={reason or 'unspecified'} "
        f"status={payload.get('phase1_observation_status_publish_status', '')} "
        f"alerts={payload.get('phase1_observation_status_publish_alert_rows', '')} "
        f"error={payload.get('phase1_observation_status_publish_error', '')}"
    )
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


def _select_latest_execution_log_df(
    *,
    candidate_paths: List[Path],
    required_exec_cols: set[str],
) -> tuple[pd.DataFrame, Path | None, pd.Timestamp]:
    selected_df = pd.DataFrame()
    selected_path: Path | None = None
    selected_max_dt = pd.NaT
    selected_mtime = -1.0

    for path in candidate_paths:
        if path is None or not path.exists():
            continue
        try:
            candidate_df = pd.read_csv(path, dtype=str).fillna("")
        except Exception:
            continue
        if not required_exec_cols.issubset(set(candidate_df.columns)):
            continue
        candidate_max_dt = pd.to_datetime(candidate_df.get("event_ts_utc", ""), errors="coerce", utc=True).max()
        try:
            candidate_mtime = float(path.stat().st_mtime)
        except Exception:
            candidate_mtime = -1.0
        choose = False
        if selected_path is None:
            choose = True
        elif pd.notna(candidate_max_dt) and (pd.isna(selected_max_dt) or candidate_max_dt > selected_max_dt):
            choose = True
        elif pd.notna(candidate_max_dt) and pd.notna(selected_max_dt) and candidate_max_dt == selected_max_dt:
            choose = candidate_mtime > selected_mtime
        elif pd.isna(candidate_max_dt) and pd.isna(selected_max_dt):
            choose = candidate_mtime > selected_mtime
        if choose:
            selected_df = candidate_df
            selected_path = path
            selected_max_dt = candidate_max_dt
            selected_mtime = candidate_mtime
    return selected_df, selected_path, selected_max_dt


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
    if not exec_log_path.exists() and not PHASE1_EXECUTION_LOG_PATH.exists():
        payload["phase1_runtime_floor_snapshot_status"] = "missing_execution_log"
        return payload

    required_exec_cols = {"sku", "event_ts_utc", "hard_floor_gbp", "final_ceiling_landed_gbp", "state", "write_status"}
    candidate_exec_paths: list[Path] = []

    def _push_exec_candidate(path: Path) -> None:
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        if any(
            (
                str(existing.resolve()) if existing.exists() else str(existing)
            )
            == resolved
            for existing in candidate_exec_paths
        ):
            return
        candidate_exec_paths.append(path)

    _push_exec_candidate(exec_log_path)
    current_run_id = _norm(_CURRENT_H_RUN_ID)
    if current_run_id:
        _push_exec_candidate(_h_stage_data_dir(current_run_id) / "execution_log.csv")
    _push_exec_candidate(PHASE1_EXECUTION_LOG_PATH)

    exec_df, selected_exec_path, selected_max_dt = _select_latest_execution_log_df(
        candidate_paths=candidate_exec_paths,
        required_exec_cols=required_exec_cols,
    )
    if exec_df.empty or selected_exec_path is None:
        payload["phase1_runtime_floor_snapshot_status"] = "execution_log_missing_columns"
        return payload
    try:
        preferred_same_as_selected = exec_log_path.resolve() == selected_exec_path.resolve()
    except Exception:
        preferred_same_as_selected = str(exec_log_path) == str(selected_exec_path)
    if not preferred_same_as_selected:
        _log(
            "phase1_runtime_floor_snapshot execution_log_source_override "
            f"preferred_path={exec_log_path} "
            f"selected_path={selected_exec_path} "
            f"selected_max_event_utc={'' if pd.isna(selected_max_dt) else selected_max_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        )

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

    latest_decision = pd.DataFrame(
        columns=[
            "sku",
            "current_cycle_decision_ts_utc",
            "current_cycle_run_id",
            "current_cycle_market_data_present",
            "current_cycle_decision",
            "current_cycle_decision_reason_code",
        ]
    )
    if H110_SKU_DECISION_LOG_PATH.exists():
        try:
            decision_df = pd.read_csv(H110_SKU_DECISION_LOG_PATH, dtype=str).fillna("")
            required_decision_cols = {"sku", "decision_ts_utc", "market_data_present", "decision"}
            if required_decision_cols.issubset(set(decision_df.columns)):
                decision_df["sku"] = _df_text_series(decision_df, "sku").astype(str).str.strip().str.upper()
                decision_df = decision_df.loc[decision_df["sku"].ne("")].copy()
                decision_df["_decision_dt"] = pd.to_datetime(
                    _df_text_series(decision_df, "decision_ts_utc"),
                    errors="coerce",
                    utc=True,
                )
                decision_df = decision_df.sort_values(["sku", "_decision_dt"], ascending=[True, False], kind="stable")
                decision_df = decision_df.drop_duplicates(subset=["sku"], keep="first")
                latest_decision = decision_df.rename(
                    columns={
                        "decision_ts_utc": "current_cycle_decision_ts_utc",
                        "run_id": "current_cycle_run_id",
                        "market_data_present": "current_cycle_market_data_present",
                        "decision": "current_cycle_decision",
                        "reason_code": "current_cycle_decision_reason_code",
                    }
                )
                keep_decision_cols = [
                    "sku",
                    "current_cycle_decision_ts_utc",
                    "current_cycle_run_id",
                    "current_cycle_market_data_present",
                    "current_cycle_decision",
                    "current_cycle_decision_reason_code",
                ]
                latest_decision = latest_decision[keep_decision_cols]
        except Exception:
            latest_decision = pd.DataFrame(
                columns=[
                    "sku",
                    "current_cycle_decision_ts_utc",
                    "current_cycle_run_id",
                    "current_cycle_market_data_present",
                    "current_cycle_decision",
                    "current_cycle_decision_reason_code",
                ]
            )

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
    if not latest_decision.empty:
        merged = merged.merge(latest_decision, on="sku", how="left")
    suppression_truth = load_latest_suppression_truth(OUT, DATA)
    if not suppression_truth.empty:
        suppression_truth["sku"] = _df_text_series(suppression_truth, "sku").astype(str).str.strip().str.upper()
        merged = merged.merge(suppression_truth, on="sku", how="left")
    scope_path = OUT / "phase1_sku_scope.csv"
    if scope_path.exists():
        try:
            scope_df = pd.read_csv(scope_path, dtype=str).fillna("")
            if {"sku", "parked_flag"}.issubset(set(scope_df.columns)):
                scope_df["sku"] = _df_text_series(scope_df, "sku").astype(str).str.strip().str.upper()
                scope_df = scope_df.loc[scope_df["sku"].ne("")].copy()
                if "asof_utc" in scope_df.columns:
                    scope_df = scope_df.sort_values(["sku", "asof_utc"], ascending=[True, False], kind="stable")
                scope_df["scope_parked_flag"] = (
                    _df_text_series(scope_df, "parked_flag")
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .isin({"1", "true", "yes", "y", "on"})
                    .map({True: "1", False: "0"})
                )
                scope_latest = scope_df[["sku", "scope_parked_flag"]].drop_duplicates(subset=["sku"], keep="first")
                merged = merged.merge(scope_latest, on="sku", how="left")
        except Exception:
            pass

    merged["stale_execution_context_cleared_flag"] = "0"
    merged["current_cycle_blocker_code"] = ""
    merged["current_cycle_blocker_reason_codes_json"] = ""
    stale_live_execution_cols = [
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
    ]
    for col in stale_live_execution_cols:
        stale_col = f"stale_{col}"
        if stale_col not in merged.columns:
            merged[stale_col] = ""

    current_decision = _df_text_series(merged, "current_cycle_decision").astype(str).str.strip().str.lower()
    current_market_data_present = _df_text_series(merged, "current_cycle_market_data_present").astype(str).str.strip()
    current_decision_dt = pd.to_datetime(
        _df_text_series(merged, "current_cycle_decision_ts_utc"),
        errors="coerce",
        utc=True,
    )
    execution_event_dt = pd.to_datetime(
        _df_text_series(merged, "execution_event_ts_utc"),
        errors="coerce",
        utc=True,
    )
    stale_execution_superseded_mask = (
        current_decision.eq("skip_no_market_data")
        & current_market_data_present.ne("1")
        & current_decision_dt.notna()
        & (execution_event_dt.isna() | current_decision_dt.ge(execution_event_dt))
        & _df_text_series(merged, "execution_event_ts_utc").astype(str).str.strip().ne("")
    )
    if bool(stale_execution_superseded_mask.any()):
        for col in stale_live_execution_cols:
            stale_col = f"stale_{col}"
            merged.loc[stale_execution_superseded_mask, stale_col] = _df_text_series(merged, col).loc[
                stale_execution_superseded_mask
            ]
            if col in merged.columns:
                merged.loc[stale_execution_superseded_mask, col] = ""
        merged.loc[stale_execution_superseded_mask, "stale_execution_context_cleared_flag"] = "1"
        merged.loc[stale_execution_superseded_mask, "execution_write_status"] = "READ_ONLY_NO_WRITE"
        merged.loc[stale_execution_superseded_mask, "current_cycle_blocker_code"] = "MARKET_DATA_MISSING_CURRENT_CYCLE"
        merged.loc[
            stale_execution_superseded_mask,
            "current_cycle_blocker_reason_codes_json",
        ] = '["MARKET_DATA_MISSING_CURRENT_CYCLE"]'

    truth_rows: list[dict[str, str]] = []
    for _, row in merged.iterrows():
        truth = resolve_unified_truth(
            suppression_active_flag=row.get("suppression_active_flag", ""),
            parked_flag=row.get("scope_parked_flag", "0"),
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
    if bool(stale_execution_superseded_mask.any()):
        # Truth reconciliation does not own execution_write_status, so re-assert
        # the current-cycle no-write outcome after the merge.
        merged.loc[stale_execution_superseded_mask, "execution_write_status"] = "READ_ONLY_NO_WRITE"
        merged.loc[stale_execution_superseded_mask, "unified_writer_outcome"] = "READ_ONLY_NO_WRITE"
        merged.loc[stale_execution_superseded_mask, "write_attempted_flag"] = "0"
        merged.loc[stale_execution_superseded_mask, "write_applied_flag"] = "0"
        merged.loc[stale_execution_superseded_mask, "truth_status"] = "READ_ONLY"
    if "scope_parked_flag" in merged.columns:
        parked_mask = merged["scope_parked_flag"].astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y", "on"})
        if bool(parked_mask.any()):
            stale_write_cols = [
                "execution_event_ts_utc",
                "execution_state",
                "execution_write_status",
                "execution_write_error",
                "execution_old_price_gbp",
                "execution_new_price_gbp",
                "execution_reason_codes_json",
            ]
            for col in stale_write_cols:
                if col in merged.columns:
                    merged.loc[parked_mask, col] = ""
            merged.loc[parked_mask, "execution_write_status"] = "NO_WRITE_REQUIRED"
            merged.loc[parked_mask, "unified_writer_outcome"] = "NO_WRITE_REQUIRED"
            merged.loc[parked_mask, "write_attempted_flag"] = "0"
            merged.loc[parked_mask, "write_applied_flag"] = "0"
            merged.loc[parked_mask, "truth_status"] = "PARKED"
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
        "current_cycle_decision_ts_utc",
        "current_cycle_run_id",
        "current_cycle_market_data_present",
        "current_cycle_decision",
        "current_cycle_decision_reason_code",
        "current_cycle_blocker_code",
        "current_cycle_blocker_reason_codes_json",
        "stale_execution_context_cleared_flag",
        "stale_execution_event_ts_utc",
        "stale_execution_state",
        "stale_execution_write_status",
        "stale_execution_write_error",
        "stale_execution_old_price_gbp",
        "stale_execution_new_price_gbp",
        "stale_execution_hard_floor_gbp",
        "stale_execution_final_ceiling_landed_gbp",
        "stale_execution_binding_ceiling_type",
        "stale_execution_reason_codes_json",
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
    write_dataframe_with_sql_compat(
        merged,
        PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH,
        SQL_TABLE_PHASE1_RUNTIME_FLOOR_SNAPSHOT_LATEST,
    )

    listing_latest_df = pd.DataFrame()
    listing_latest_path = OUT / "listing_offer_snapshot_latest.csv"
    if listing_latest_path.exists():
        try:
            listing_latest_df = pd.read_csv(listing_latest_path, dtype=str).fillna("")
        except Exception:
            listing_latest_df = pd.DataFrame()
    proof_df = _build_seller_detail_resolution_proof(
        snapshot_utc=event_ts,
        run_id=_norm(_CURRENT_H_RUN_ID),
        listing_df=listing_latest_df,
        runtime_floor_df=merged,
    )
    _atomic_write_csv(H_SELLER_DETAIL_PROOF_PATH, proof_df)
    retry_queue_df = _load_item_offers_retry_queue()
    recovery_history_df, measurement_summary_df = _build_seller_detail_measurement_outputs(
        snapshot_utc=event_ts,
        run_id=_norm(_CURRENT_H_RUN_ID),
        listing_df=listing_latest_df,
        runtime_floor_df=merged,
        retry_queue_df=retry_queue_df,
    )
    measurement_alerts_df = _build_seller_detail_measurement_alerts(
        snapshot_utc=event_ts,
        run_id=_norm(_CURRENT_H_RUN_ID),
        history_df=recovery_history_df,
        summary_df=measurement_summary_df,
    )
    operator_review_df = _build_seller_detail_operator_review(
        snapshot_utc=event_ts,
        run_id=_norm(_CURRENT_H_RUN_ID),
        history_df=recovery_history_df,
    )
    _atomic_write_csv(H_SELLER_DETAIL_RECOVERY_HISTORY_PATH, recovery_history_df)
    _atomic_write_csv(H_SELLER_DETAIL_MEASUREMENT_SUMMARY_PATH, measurement_summary_df)
    _atomic_write_csv(H_SELLER_DETAIL_MEASUREMENT_ALERTS_PATH, measurement_alerts_df)
    _atomic_write_csv(H_SELLER_DETAIL_OPERATOR_REVIEW_PATH, operator_review_df)
    _atomic_write_csv(_seller_detail_measurement_summary_archive_path(_norm(_CURRENT_H_RUN_ID)), measurement_summary_df)
    alert_warn_count = int(measurement_alerts_df.get("status", pd.Series([], dtype=str)).astype(str).str.strip().str.lower().eq("warn").sum())
    review_bucket_counts = _seller_detail_operator_review_bucket_counts(operator_review_df)

    payload["phase1_runtime_floor_snapshot_rows"] = str(len(merged.index))
    payload["phase1_runtime_floor_snapshot_trace_rows"] = str(
        int(merged["trace_floor_total_gbp"].astype(str).str.strip().ne("").sum())
    )
    payload["phase1_seller_detail_pending_retry_count"] = str(
        int(proof_df.get("pending_retry_count", pd.Series(["0"])).iloc[0])
    )
    payload["phase1_seller_detail_recovered_count"] = str(
        int(proof_df.get("recovered_count", pd.Series(["0"])).iloc[0])
    )
    payload["phase1_seller_detail_supp_gated_count"] = str(
        int(proof_df.get("supp_gated_detail_count", pd.Series(["0"])).iloc[0])
    )
    payload["phase1_seller_detail_supp_blocked_count"] = str(
        int(proof_df.get("supp_blocked_count", pd.Series(["0"])).iloc[0])
    )
    payload["phase1_seller_detail_amazon_missing_likely_count"] = str(
        int(measurement_summary_df.get("amazon_missing_likely_count", pd.Series(["0"])).iloc[0])
    )
    payload["phase1_seller_detail_retry_exhausted_count"] = str(
        int(measurement_summary_df.get("retry_exhausted_count", pd.Series(["0"])).iloc[0])
    )
    payload["phase1_seller_detail_newly_recovered_count"] = str(
        int(measurement_summary_df.get("newly_recovered_count", pd.Series(["0"])).iloc[0])
    )
    payload["phase1_seller_detail_stale_pending_count"] = str(
        int(measurement_summary_df.get("stale_pending_over_threshold_count", pd.Series(["0"])).iloc[0])
    )
    payload["phase1_seller_detail_alert_warn_count"] = str(int(alert_warn_count))
    payload["phase1_seller_detail_review_rows"] = str(int(len(operator_review_df.index)))
    payload["phase1_seller_detail_review_amazon_bucket_count"] = str(int(review_bucket_counts["amazon_upstream"]))
    payload["phase1_seller_detail_review_local_selection_count"] = str(int(review_bucket_counts["local_selection"]))
    payload["phase1_seller_detail_review_retry_exhausted_bucket_count"] = str(int(review_bucket_counts["retry_exhausted_review"]))
    payload["phase1_seller_detail_review_genuine_blocker_count"] = str(int(review_bucket_counts["genuine_blocker"]))
    _log(
        "phase1 seller_detail_resolution_proof "
        f"pending_retry={payload['phase1_seller_detail_pending_retry_count']} "
        f"recovered={payload['phase1_seller_detail_recovered_count']} "
        f"supp_gated_detail={payload['phase1_seller_detail_supp_gated_count']} "
        f"supp_blocked={payload['phase1_seller_detail_supp_blocked_count']} "
        f"path={H_SELLER_DETAIL_PROOF_PATH}"
    )
    _log(
        "phase1 seller_detail_measurement_summary "
        f"pending_retry={payload['phase1_seller_detail_pending_retry_count']} "
        f"recovered={payload['phase1_seller_detail_recovered_count']} "
        f"amazon_missing_likely={payload['phase1_seller_detail_amazon_missing_likely_count']} "
        f"retry_exhausted={payload['phase1_seller_detail_retry_exhausted_count']} "
        f"newly_recovered={payload['phase1_seller_detail_newly_recovered_count']} "
        f"stale_pending={payload['phase1_seller_detail_stale_pending_count']} "
        f"history_path={H_SELLER_DETAIL_RECOVERY_HISTORY_PATH} "
        f"summary_path={H_SELLER_DETAIL_MEASUREMENT_SUMMARY_PATH}"
    )
    _log(
        "phase1 seller_detail_alerts "
        f"warn_count={payload['phase1_seller_detail_alert_warn_count']} "
        f"review_rows={payload['phase1_seller_detail_review_rows']} "
        f"amazon_bucket={payload['phase1_seller_detail_review_amazon_bucket_count']} "
        f"local_selection_bucket={payload['phase1_seller_detail_review_local_selection_count']} "
        f"retry_exhausted_bucket={payload['phase1_seller_detail_review_retry_exhausted_bucket_count']} "
        f"genuine_blocker_bucket={payload['phase1_seller_detail_review_genuine_blocker_count']} "
        f"alerts_path={H_SELLER_DETAIL_MEASUREMENT_ALERTS_PATH} "
        f"review_path={H_SELLER_DETAIL_OPERATOR_REVIEW_PATH}"
    )
    payload["phase1_runtime_floor_snapshot_status"] = "ok"
    return payload


def main() -> int:
    global _CURRENT_H_RUN_ID, _FINALIZER_CONTRACT_ENFORCED
    _ensure_parent_fault_trace()
    _append_h_parent_trace("main_enter")
    args = _parse_cli_args()
    try:
        if is_truthy(os.environ.get("H_OWNER_CONTRACT_ENFORCE", "1")):
            assert_flow_owner_mapping(
                "H",
                runtime_owner=ROOT / "scripts" / "cycles" / "run_H_pricing_cycle_guarded.py",
                worker_entry=Path(__file__),
                launcher_entrypoint=ROOT / "run_H_cycle.bat",
            )
        if not is_truthy(os.environ.get("H_ALLOW_DIRECT_WORKER_START", "0")):
            if not is_truthy(os.environ.get("H_GUARD_WRAPPER_ACTIVE", "0")):
                raise RuntimeError(
                    "direct_worker_start_blocked missing_guard_wrapper; "
                    "use run_H_cycle.bat or set H_ALLOW_DIRECT_WORKER_START=1"
                )
    except RuntimeOwnerContractError as exc:
        _log(f"FATAL owner_contract_violation detail={exc}")
        _append_h_parent_trace("owner_contract_violation", detail=str(exc))
        return 2
    except RuntimeError as exc:
        _log(f"FATAL {exc}")
        _append_h_parent_trace("direct_worker_start_blocked", detail=str(exc))
        return 2
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
    if bool(getattr(args, "snapshot_refresh_worker", False)):
        _FINALIZER_CONTRACT_ENFORCED = False
        return int(_run_snapshot_refresh_worker_entry(args))
    _FINALIZER_CONTRACT_ENFORCED = True
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
    startup_reconcile_enabled = is_truthy(os.environ.get("H_CORE_STARTUP_RECONCILE_ENABLE", "1"))
    _acquire_lock()
    try:
        if startup_reconcile_enabled:
            startup_reconcile = _reconcile_stale_pilot_started_dead_owner()
            startup_reconcile_reason = _norm(startup_reconcile.get("reason", "")) or "missing"
            startup_reconcile_run_id = _norm(startup_reconcile.get("run_id", ""))
            startup_reconcile_state = _norm(startup_reconcile.get("state", ""))
            if startup_reconcile.get("blocked", "0") == "1":
                _write_runtime_status(
                    "ERROR",
                    run_id=startup_reconcile_run_id,
                    stage="startup_reconcile",
                    detail=f"blocked reason={startup_reconcile_reason}",
                    error="RUN_STATE_NOT_TERMINAL",
                )
                _log(
                    "FATAL startup_stale_reconcile_blocked "
                    f"run_id={startup_reconcile_run_id or 'missing'} "
                    f"state={startup_reconcile_state or 'missing'} "
                    f"reason={startup_reconcile_reason} "
                    f"owner_exit_evidence={_norm(startup_reconcile.get('owner_exit_evidence', '')) or 'missing'} "
                    "action=fail_closed_no_new_run"
                )
                raise SystemExit(3)
            if startup_reconcile.get("applied", "0") == "1":
                _log(
                    "startup_stale_reconcile_applied "
                    f"run_id={startup_reconcile_run_id or 'missing'} "
                    f"state={startup_reconcile_state or 'missing'} "
                    f"reason={startup_reconcile_reason} "
                    f"failure_code={_norm(startup_reconcile.get('failure_code', '')) or 'missing'} "
                    "action=continue_new_run"
                )
            else:
                _log(
                    "startup_stale_reconcile_clear "
                    f"run_id={startup_reconcile_run_id or 'missing'} "
                    f"state={startup_reconcile_state or 'missing'} "
                    f"reason={startup_reconcile_reason} "
                    "action=continue_new_run"
                )
        else:
            _log("startup_stale_reconcile_disabled policy=single_owner_no_cross_run_inference")
            startup_guard = _startup_nonterminal_truth_guard()
            if startup_guard.get("blocked", "0") == "1":
                guard_run_id = _norm(startup_guard.get("run_id", ""))
                guard_state = _norm(startup_guard.get("state", ""))
                guard_reason = _norm(startup_guard.get("reason", "")) or "missing"
                _write_runtime_status(
                    "ERROR",
                    run_id=guard_run_id,
                    stage="startup_guard",
                    detail=f"blocked reason={guard_reason}",
                    error="RUN_STATE_NOT_TERMINAL",
                )
                _log(
                    "FATAL startup_nonterminal_guard_blocked "
                    f"run_id={guard_run_id or 'missing'} "
                    f"state={guard_state or 'missing'} "
                    f"owner_pid={_norm(startup_guard.get('owner_pid', '')) or 'missing'} "
                    f"owner_alive={_norm(startup_guard.get('owner_alive', '0')) or '0'} "
                    f"run_in_progress={_norm(startup_guard.get('run_in_progress', '')) or 'missing'} "
                    f"current_cycle_run_id={_norm(startup_guard.get('current_cycle_run_id', '')) or 'missing'} "
                    f"state_utc={_norm(startup_guard.get('state_utc', '')) or 'missing'} "
                    f"reason={guard_reason} "
                    "action=fail_closed_no_new_run"
                )
                raise SystemExit(3)
            _log(
                "startup_nonterminal_guard_clear "
                f"run_id={_norm(startup_guard.get('run_id', '')) or 'missing'} "
                f"state={_norm(startup_guard.get('state', '')) or 'missing'} "
                f"reason={_norm(startup_guard.get('reason', '')) or 'missing'} "
                "action=continue_new_run"
            )
        _ensure_action_log()
        _ensure_live_test_execution_log()
        _run_h_live_self_cleanup()
        _write_runtime_status("RUNNING", stage="startup", detail="loop_ready")
        while True:
            cycle_manifest = None
            cycle_started = utc_now_iso()
            cycle_run_id = ""
            loop_rc = ""
            cycle_failure_code = ""
            cycle_failure_detail = ""
            pre_cycle_drain_exit = False
            state: dict[str, str] = {}
            stage_env: dict[str, str] | None = None
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
                _run_h_live_self_cleanup()
                _clear_restart_drain_ready()
                now_utc = _utc_now()
                run_id = _set_run_context(_resolve_cycle_run_id(now_utc))
                _write_run_in_progress(run_id)
                _transition_h_worker_lifecycle(run_id, "pending", emit_log=True)
                _write_lock(run_id)
                for _lock_path in _lock_paths():
                    _log(f"lock_acquired path={_lock_path} run_id={run_id}")
                if os.environ.get("H_LOCK_TEST_RAISE_AFTER_ACQUIRE", "0").strip() == "1":
                    raise RuntimeError("lock_test_forced_exception_after_acquire")
                _trace_publish_gap(run_id, "cycle_start")
                _transition_h_batch_state(run_id, "started")
                _transition_h_worker_lifecycle(run_id, "claimed", emit_log=True)
                _transition_h_worker_lifecycle(run_id, "running", emit_log=True)
                _write_h_run_state(
                    "started",
                    run_id=run_id,
                    stage="cycle_start",
                    publish_status="not_started",
                )
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
                selected_runtime_branch = "phase1" if args.phase1_pilot else "legacy"
                guard_requires_phase1 = bool(run_once and not args.snapshot_refresh_worker)
                _log(
                    "runtime_mode_selected "
                    f"run_id={run_id} "
                    f"selected_branch={selected_runtime_branch} "
                    f"cli_phase1_pilot={'1' if args.phase1_pilot else '0'} "
                    f"cli_run_once={'1' if run_once else '0'} "
                    f"env_H_RUN_ONCE={_norm(os.environ.get('H_RUN_ONCE', '')) or 'unset'} "
                    f"guard_requires_phase1={'1' if guard_requires_phase1 else '0'}"
                )
                if guard_requires_phase1 and not args.phase1_pilot:
                    reason = "run_once_requires_phase1_pilot"
                    _log(
                        "FATAL runtime_mode_guard "
                        f"run_id={run_id} "
                        f"reason={reason} "
                        f"selected_branch={selected_runtime_branch}"
                    )
                    raise SystemExit(2)
                _log(
                    "phase1 stage_seed "
                    f"run_id={run_id} "
                    f"seeded_from_live={stage_seed_state.get('phase1_stage_seeded_from_live', '0')}"
                )
                _assert_h_worker_claimed(run_id)
                state = _read_state(default={})
                # Reset publish/finalize contract fields per run so failed-early paths
                # never inherit stale publish state from a previous run.
                state["phase1_observation_publish_status"] = "not_started"
                state["phase1_observation_publish_error"] = ""
                state["phase1_publish_started"] = "0"
                state["phase1_publish_started_run_id"] = ""
                state["phase1_publish_completed"] = "0"
                state["phase1_publish_entry_run_id"] = ""
                state["phase1_publish_entry_status"] = ""
                state["h_split_health_mode"] = mode_effective
                if PHASE1_OBSERVATION_STATUS_PUBLISH_ON_START:
                    start_status_publish = _run_phase1_observation_status_publish_nonblocking(
                        now_utc=now_utc,
                        run_id=run_id,
                        stage_env=stage_env,
                        reason="cycle_start",
                    )
                    if start_status_publish:
                        state.update(start_status_publish)
                else:
                    _log("phase1 status_publish skipped reason=cycle_start_disabled")
                _write_state(state)
                if args.phase1_pilot:
                    _log("phase1 snapshot_refresh start")
                    _trace_publish_gap(run_id, "snapshot_refresh_start")
                    snapshot_stage_started = _stage_enter(stage="snapshot_refresh", run_id=run_id)
                    if stage_enabled.get("snapshot_refresh", True):
                        snapshot_worker_mode = _snapshot_worker_mode_enabled()
                        _trace_publish_gap(
                            run_id,
                            "snapshot_refresh_subprocess_start",
                            mode="snapshot_worker" if snapshot_worker_mode else "inline",
                        )
                        try:
                            if snapshot_worker_mode:
                                refresh_state = _run_with_retries(
                                    "snapshot_refresh",
                                    lambda: _run_snapshot_refresh_worker_subprocess(
                                        now_utc=now_utc,
                                        run_id=run_id,
                                        item_offers_enabled=stage_enabled.get("item_offers", True),
                                    ),
                                )
                            else:
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
                    _write_h_run_state(
                        "snapshot_done",
                        run_id=run_id,
                        stage="snapshot_refresh",
                        publish_status="not_started",
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
                        f"pending_fail={gate_state.get('h_gate_pending_fail_count', '0')} "
                        f"pending_warn={gate_state.get('h_gate_pending_warn_count', '0')} "
                        f"condition={gate_state.get('h_gate_condition_status', '')} "
                        f"block={gate_state.get('h_gate_block_live_writes', '')}"
                    )
                    pilot_gate_block = gate_state.get("h_gate_block_live_writes", "0") == "1"
                    pilot_read_only = bool(args.read_only) or pilot_gate_block
                    if mode_effective == "shadow":
                        _log(
                            "split_health_shadow_candidate "
                            f"fail={gate_state.get('h_gate_fail_count', '')} "
                            f"warn={gate_state.get('h_gate_warn_count', '')} "
                            f"pending_fail={gate_state.get('h_gate_pending_fail_count', '0')} "
                            f"pending_warn={gate_state.get('h_gate_pending_warn_count', '0')} "
                            f"condition={gate_state.get('h_gate_condition_status', '')} "
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
                    _write_h_run_state(
                        "pilot_started",
                        run_id=run_id,
                        stage="phase1_pilot",
                        publish_status="not_started",
                    )
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
                    _write_h_run_state(
                        "pilot_done",
                        run_id=run_id,
                        stage="phase1_pilot",
                        publish_status="not_started",
                    )
                    if stage_enabled.get("phase1_publish", True):
                        # Commit same-run publish entry intent immediately after pilot completion
                        # so wrapper finalization cannot observe pilot_done without publish transition state.
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
                    if state.get("phase1_publish_started_run_id", "") != run_id:
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
                    _write_h_run_state(
                        "publish_started",
                        run_id=run_id,
                        stage="phase1_publish",
                        publish_status="started",
                    )
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
                    _write_h_run_state(
                        "publish_done",
                        run_id=run_id,
                        stage="phase1_publish",
                        publish_status=_norm(observation_state.get("phase1_observation_publish_status", "")) or "unknown",
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
                    _transition_h_worker_lifecycle(run_id, "finalizing", emit_log=True)
                    _mark_finalizer_reached(run_id)
                    _write_h_run_state(
                        "finalized",
                        run_id=run_id,
                        stage="phase1_publish",
                        publish_status=_norm(observation_state.get("phase1_observation_publish_status", "")) or "ok",
                    )
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
                raw_failure_code = type(exc).__name__.upper()
                raw_failure_detail = f"{type(exc).__name__}:{exc}"
                cycle_failure_code, cycle_failure_detail = _classify_h_failure_event(
                    failure_code=raw_failure_code,
                    failure_detail=raw_failure_detail,
                    loop_rc="1",
                )
                if cycle_run_id:
                    _transition_h_batch_state(cycle_run_id, "failed", reason=f"{type(exc).__name__}:{exc}")
                _write_runtime_status(
                    "ERROR",
                    run_id=cycle_run_id,
                    stage=_LAST_STAGE_NAME,
                    detail="cycle_error",
                    error=f"{type(exc).__name__}:{exc}",
                )
                _write_h_run_state(
                    "failed",
                    run_id=cycle_run_id,
                    stage=_LAST_STAGE_NAME,
                    publish_status=_norm(state.get("phase1_observation_publish_status", "")),
                    failure_code=cycle_failure_code,
                    failure_detail=cycle_failure_detail,
                )
                if _norm(cycle_run_id):
                    _transition_h_worker_lifecycle(
                        cycle_run_id,
                        "failed",
                        reason_code=cycle_failure_code,
                        reason_detail=cycle_failure_detail,
                        terminal_outcome="failed",
                        emit_log=True,
                    )
                if PHASE1_OBSERVATION_STATUS_PUBLISH_ON_ERROR and not isinstance(exc, KeyboardInterrupt):
                    error_now_utc = _utc_now()
                    error_run_id = _norm(cycle_run_id) or _norm(_context_run_id()) or "unknown"
                    error_status_publish = _run_phase1_observation_status_publish_nonblocking(
                        now_utc=error_now_utc,
                        run_id=error_run_id,
                        stage_env=stage_env,
                        reason="cycle_error",
                    )
                    if error_status_publish:
                        state.update(error_status_publish)
                        _write_state(state)
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
                        notes=f"cause_code={cycle_failure_code};error={type(exc).__name__}:{exc}",
                        started_at=cycle_started,
                        ended_at=utc_now_iso(),
                    )
                _log(f"cycle_error {type(exc).__name__}: {exc}")
                _append_h_parent_trace(
                    "core_abnormal_exit",
                    run_id=_norm(cycle_run_id) or _context_run_id(),
                    stage=_LAST_STAGE_NAME,
                    error_type=type(exc).__name__,
                    reason=str(exc)[:400],
                )
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
                    _transition_h_worker_lifecycle(finalizer_run_id, "finalizing", emit_log=True)
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
                            cycle_failure_code = "PUBLISH_PROOF_MISSING"
                            cycle_failure_detail = "phase1_publish_started_and_completed_not_proven"
                            _write_state(state)
                            _log(
                                "FATAL publish_skipped "
                                f"current={finalizer_run_id} "
                                f"phase1_intel_started_run_id={state.get('phase1_intel_started_run_id', '')} "
                                f"phase1_publish_started_run_id={state.get('phase1_publish_started_run_id', '')} "
                                f"phase1_publish_completed={state.get('phase1_publish_completed', '')}"
                            )
                            _write_h_run_state(
                                "failed",
                                run_id=finalizer_run_id,
                                stage="phase1_publish",
                                publish_status=_norm(state.get("phase1_observation_publish_status", "")),
                                failure_code=cycle_failure_code,
                                failure_detail=cycle_failure_detail,
                            )
                            _transition_h_worker_lifecycle(
                                finalizer_run_id,
                                "failed",
                                reason_code=cycle_failure_code,
                                reason_detail=cycle_failure_detail,
                                terminal_outcome="failed",
                                emit_log=True,
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
                            cycle_failure_code = "PUBLISH_PROOF_MISSING"
                            cycle_failure_detail = (
                                f"selected_source={publish_proof.get('selected_source', '') or 'none'} "
                                f"selected_run_id={publish_proof_run_id}"
                            )
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
                            _write_h_run_state(
                                "failed",
                                run_id=finalizer_run_id,
                                stage="phase1_publish",
                                publish_status=_norm(state.get("phase1_observation_publish_status", "")),
                                failure_code=cycle_failure_code,
                                failure_detail=cycle_failure_detail,
                            )
                            _transition_h_worker_lifecycle(
                                finalizer_run_id,
                                "failed",
                                reason_code=cycle_failure_code,
                                reason_detail=cycle_failure_detail,
                                terminal_outcome="failed",
                                emit_log=True,
                            )
                            _transition_h_batch_state(finalizer_run_id, "failed", reason="FINALIZE_BLOCKED_NO_PUBLISH")
                        else:
                            _mark_finalizer_reached(finalizer_run_id)
                            _write_h_run_state(
                                "finalized",
                                run_id=finalizer_run_id,
                                stage="phase1_publish",
                                publish_status=_norm(state.get("phase1_observation_publish_status", "")) or "ok",
                            )
                            outputs_ok, missing_outputs = _verify_h_success_outputs(finalizer_run_id)
                            if not outputs_ok:
                                loop_rc = "3"
                                missing_text = "|".join(missing_outputs)
                                cycle_failure_code = "REQUIRED_OUTPUTS_MISSING"
                                cycle_failure_detail = missing_text
                                _write_h_run_state(
                                    "failed",
                                    run_id=finalizer_run_id,
                                    stage="phase1_publish",
                                    publish_status=_norm(state.get("phase1_observation_publish_status", "")),
                                    failure_code=cycle_failure_code,
                                    failure_detail=cycle_failure_detail,
                                )
                                _transition_h_worker_lifecycle(
                                    finalizer_run_id,
                                    "failed",
                                    reason_code=cycle_failure_code,
                                    reason_detail=cycle_failure_detail,
                                    terminal_outcome="failed",
                                    expected_outputs_ok="0",
                                    expected_outputs_missing=missing_text,
                                    emit_log=True,
                                )
                                _transition_h_batch_state(finalizer_run_id, "failed", reason="REQUIRED_OUTPUTS_MISSING")
                            else:
                                _transition_h_worker_lifecycle(
                                    finalizer_run_id,
                                    "succeeded",
                                    terminal_outcome="succeeded",
                                    expected_outputs_ok="1",
                                    emit_log=True,
                                )
                            _transition_h_batch_state(finalizer_run_id, "finalized")
                    if _norm(loop_rc) != "0" and _norm(finalizer_run_id):
                        terminal_failure_code = _norm(cycle_failure_code)
                        terminal_failure_detail = _norm(cycle_failure_detail)
                        if not terminal_failure_code:
                            terminal_failure_detail = _norm(state.get("phase1_observation_publish_error", ""))
                            terminal_failure_code, terminal_failure_detail = _classify_h_failure_event(
                                failure_code=f"LOOP_RC_{_norm(loop_rc)}",
                                failure_detail=terminal_failure_detail,
                                loop_rc=loop_rc,
                            )
                        _write_h_run_state(
                            "failed",
                            run_id=finalizer_run_id,
                            stage=_LAST_STAGE_NAME,
                            publish_status=_norm(state.get("phase1_observation_publish_status", "")),
                            failure_code=terminal_failure_code,
                            failure_detail=terminal_failure_detail,
                        )
                        _transition_h_worker_lifecycle(
                            finalizer_run_id,
                            "failed",
                            reason_code=terminal_failure_code,
                            reason_detail=terminal_failure_detail,
                            terminal_outcome="failed",
                            emit_log=True,
                        )
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
                            notes=(
                                f"cycle_run_id={cycle_run_id};"
                                f"cause_code={_norm(cycle_failure_code)};"
                                f"cause_detail={tail_text(cycle_failure_detail, max_chars=500)}"
                            ),
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
                    manifest_path = write_manifest(ROOT, cycle_manifest)
                    if _norm(cycle_manifest.get("final_state", "")).lower() != "completed":
                        event_code = _norm(cycle_failure_code)
                        event_detail = _norm(cycle_failure_detail)
                        if not event_code:
                            event_code, event_detail = _classify_h_failure_event(
                                failure_code=f"LOOP_RC_{_norm(loop_rc)}",
                                failure_detail=_norm(state.get("phase1_observation_publish_error", "")),
                                loop_rc=loop_rc,
                            )
                        _record_h_failure_event(
                            run_id=_norm(finalizer_run_id) or _norm(cycle_run_id),
                            final_state=_norm(cycle_manifest.get("final_state", "")),
                            cause_code=event_code,
                            cause_detail=event_detail,
                            stage=_LAST_STAGE_NAME,
                            rc=loop_rc,
                            manifest_path=manifest_path,
                            health_path=health_path,
                            recovery_action="inspect H manifest, terminal marker, and phase1 wait abnormal artifact before restarting",
                        )
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
    if _finalizer_contract_enforced() and success_run_id and _norm(last_finalized_run_id) != success_run_id:
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
    _run_storage_housekeeping_hook("H", "h_success_finalized")
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
