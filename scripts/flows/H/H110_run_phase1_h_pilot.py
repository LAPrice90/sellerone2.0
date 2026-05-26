from __future__ import annotations

import argparse
import atexit
import contextlib
import csv
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "out"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SELF_MODULE = "scripts.flows.H.H110_run_phase1_h_pilot"

from scripts.phase1 import phase1_main_loop, phase1_phase_engine, phase1_storage  # noqa: E402
from scripts.phase1 import phase1_sku_scope  # noqa: E402
from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing  # noqa: E402
from scripts.api.get_listing_item_price import fetch_our_offer_prices, run_own_offer_price_lookup  # noqa: E402
from scripts.h.h_floor_policy import load_h_floor_vat_policy  # noqa: E402
from scripts.h.h_floor_truth import (  # noqa: E402
    HFloorContext,
    append_h_floor_trace_rows,
    build_h_floor_trace_row,
    compute_h_floor_for_sku,
    has_blocking_reason_codes,
    load_h_floor_context,
)
from scripts.phase1.phase1_write_verify import patch_listings_item_price  # noqa: E402

SOURCE = "H110_run_phase1_h_pilot"
SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
MARKETPLACE_CODE_TO_ID = {"UK": "A1F83G8C2ARO7P"}
SKU_SCAN_STATE_PATH = OUT / "phase1_sku_scan_state.json"
MANUAL_CAPS_PATH = ROOT / "config" / "phase1_manual_max_caps.csv"
PRODUCT_DB_PATH = OUT / "product_db_preview.csv"
TOKEN_COGS_LEDGER_PATH = OUT / "token_cogs_ledger.csv"
TOKEN_LEDGER_PATH = OUT / "token_ledger_live.csv"
ORDER_MASTER_PATH = OUT / "order_master.csv"
TEMP_FLOOR_SNAPSHOT_PATH = OUT / "sku_temp_floor_snapshot.csv"
OFFER_SNAPSHOT_FACTS_PATH = ROOT / "data" / "offer_snapshot_facts.csv"
MIN_REFERRAL_FEE_GBP = 0.25
# Terminology: "commission" in this repricer equals Amazon referral fee.
H_FLOOR_VAT_POLICY = load_h_floor_vat_policy()
PHASE1_PROGRESS_PATH = Path(os.environ.get("H_PHASE1_PROGRESS_PATH", "").strip()) if os.environ.get("H_PHASE1_PROGRESS_PATH", "").strip() else None
PHASE1_RESULT_PATH = Path(os.environ.get("H_PHASE1_RESULT_PATH", "").strip()) if os.environ.get("H_PHASE1_RESULT_PATH", "").strip() else None
PHASE1_COMPLETION_MARKER_PATH = (
    Path(os.environ.get("H_PHASE1_COMPLETION_MARKER_PATH", "").strip())
    if os.environ.get("H_PHASE1_COMPLETION_MARKER_PATH", "").strip()
    else None
)
PHASE1_PARENT_HANDOFF_PATH = (
    Path(os.environ.get("H_PHASE1_PARENT_HANDOFF_PATH", "").strip())
    if os.environ.get("H_PHASE1_PARENT_HANDOFF_PATH", "").strip()
    else None
)
H110_SKU_DECISION_LOG_PATH = OUT / "systems" / "H" / "live" / "h110_sku_decision_log.csv"
H110_SKU_LIFECYCLE_LOG_PATH = OUT / "systems" / "H" / "live" / "h110_sku_lifecycle_log.csv"
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
H_LIVE_DIR = OUT / "systems" / "H" / "live"
H_RUN_STATE_PATH = H_LIVE_DIR / "H_run_state.json"
H_REENTRY_STATE_PATH = H_LIVE_DIR / "h_reentry_price_state.json"
H_INBOUND_ACTIVATION_STATE_PATH = H_LIVE_DIR / "h_inbound_activation_state.json"
CANONICAL_UNIVERSE_PATH = OUT / "phase1_sku_scope.csv"
STOCKED_EXCLUDED_REPORT_PATH = OUT / "REPORT_live_but_excluded.csv"
H_INCLUDE_STOCKED_EXCLUDED_ENV = "H_INCLUDE_STOCKED_EXCLUDED"
DEFAULT_STOCK_SNAPSHOT_PATH = OUT / "parking" / "stock_snapshot_latest.csv"
INVENTORY_SNAPSHOT_GLOB = "inventory_snapshot_*.csv"
INVENTORY_SUMMARIES_PATH = OUT / "inventory_summaries.csv"
STOCK_SNAPSHOT_PATH_ENV = "H_STOCK_SNAPSHOT_PATH"
STOCK_SNAPSHOT_GLOB_ENV = "H_STOCK_SNAPSHOT_GLOB"
STOCK_SNAPSHOT_SKU_COL_ENV = "H_STOCK_SNAPSHOT_SKU_COL"
STOCK_SNAPSHOT_QTY_COL_ENV = "H_STOCK_SNAPSHOT_QTY_COL"
STOCK_SNAPSHOT_MAX_AGE_HOURS_ENV = "H_STOCK_SNAPSHOT_MAX_AGE_HOURS"
STOCK_SNAPSHOT_REQUIRE_TODAY_ENV = "H_STOCK_SNAPSHOT_REQUIRE_TODAY"
STOCK_ROW_STALE_HOURS_ENV = "H_STOCK_ROW_STALE_HOURS"
DEFAULT_STOCK_SNAPSHOT_GLOB = "out/parking/stock_snapshot_*.csv"
DEFAULT_STOCK_SNAPSHOT_MAX_AGE_HOURS = 48.0
DEFAULT_STOCK_ROW_STALE_HOURS = 24.0
STOCK_SKU_COL_CANDIDATES = ["sku", "SKU", "Sku", "seller_sku", "SellerSKU"]
STOCK_QTY_COL_CANDIDATES = [
    "total_qty",
    "stock",
    "Stock",
    "qty",
    "Qty",
    "available",
    "Available",
    "on_hand",
    "OnHand",
    "available_qty",
    "quantity",
    "total_quantity",
]
INBOUND_UNITS_COL_CANDIDATES = [
    "inbound_total",
    "inbound_working",
    "inbound_shipped",
    "inbound_receiving",
]
INBOUND_COMPONENT_COLS = [
    "inbound_working",
    "inbound_shipped",
    "inbound_receiving",
]
REQUIRED_UNIVERSE_COLUMNS = {
    "sku",
    "merchant_status",
    "manually_disabled",
    "repricing_enabled",
    "observe_enabled",
    "write_enabled",
    "observe_effective",
    "write_effective",
    "reason_code",
    "asof",
}

_ACTIVE_COMPLETION_RUN_ID = ""
_SUCCESS_MARKER_WRITTEN = False
_TERMINAL_MARKER_ATTEMPTED = False
_MARKER_GUARD_LOCK = threading.Lock()
_LAST_COMPLETION_CHECKPOINT = "init"
_LAST_COMPLETION_RUN_ID = ""
_COMPLETION_CHECKPOINT_STATE_PATH: Path | None = None
_CONTINUATION_BOUNDARY_STATE: dict[str, str] = {
    "active": "0",
    "run_id": "",
    "sku": "",
    "stage": "",
    "detail": "",
}
_CONTINUATION_BOUNDARY_LOCK = threading.Lock()
_MARKET_PAYLOAD_CHECKPOINT_RUN_ID = ""
_MARKET_PAYLOAD_CHECKPOINT_SKU = ""
_MARKET_PAYLOAD_CHECKPOINT_PATH: Path | None = None
_NORM_TRACE_ACTIVE = False
_NORM_TRACE_LABEL = ""
_NATIVE_OS_EXIT = os._exit
_OWNER_WAIT_STATE: dict[str, str] = {
    "active": "0",
    "run_id": "",
    "sku": "",
    "owner_pid": "",
    "subcall_pid": "",
    "helper_pid": "",
    "state": "",
    "reason": "",
}
_OWNER_WAIT_LOCK = threading.Lock()
_OWNER_PROVENANCE_STATE: dict[str, str] = {
    "active": "0",
    "run_id": "",
    "sku": "",
    "owner_pid": "",
    "monitor_pid": "",
    "window_token": "",
    "stop_signal_path": "",
}
_OWNER_PROVENANCE_LOCK = threading.Lock()
_OWNER_INTERRUPT_RECONCILE_STATE: dict[str, str] = {
    "active": "0",
    "run_id": "",
    "sku": "",
    "deadline_monotonic": "0",
}
_OWNER_INTERRUPT_RECONCILE_LOCK = threading.Lock()
_PARENT_WATCHDOG_ABORT_STATE: dict[str, str] = {
    "active": "0",
    "reason": "",
    "run_id": "",
}
_PARENT_WATCHDOG_ABORT_LOCK = threading.Lock()


class _TerminalizationOsExitIntercepted(RuntimeError):
    def __init__(self, code: object) -> None:
        self.code = int(code) if str(code).strip() else 1
        super().__init__(f"os._exit intercepted code={self.code}")


class _DirectArtifactOwnershipHandoff(RuntimeError):
    def __init__(self, *, owner_pid: int, root_run_id: str) -> None:
        self.owner_pid = int(owner_pid)
        self.root_run_id = _norm(root_run_id)
        super().__init__("direct_artifact_owner_handoff")


def _norm(value: object) -> str:
    try:
        raw = str(value or "")
    except BaseException:
        try:
            raw = repr(value)
        except BaseException:
            raw = f"<unprintable:{type(value).__name__}>"
    if _NORM_TRACE_ACTIVE:
        _market_payload_checkpoint_raw(
            "market_payload_entry_window_norm_helper_entry",
            label=_NORM_TRACE_LABEL,
            raw_len=str(len(raw)),
        )
    stripped = raw.strip()
    if _NORM_TRACE_ACTIVE:
        _market_payload_checkpoint_raw(
            "market_payload_entry_window_norm_helper_before_return",
            label=_NORM_TRACE_LABEL,
            stripped_len=str(len(stripped)),
        )
    return stripped


def _root_run_id(value: object) -> str:
    run_id = _norm(value)
    if not run_id:
        return ""
    head, sep, tail = run_id.rpartition("_")
    if sep and head and len(tail) == 2 and tail.isdigit():
        return head
    return run_id


def _self_python_cmd(*args: str) -> list[str]:
    return [sys.executable, "-m", SELF_MODULE, *list(args)]


def _popen_hidden(*args: object, **kwargs: object) -> subprocess.Popen:
    """Launch subprocesses hidden on Windows to avoid console flash."""
    if os.name == "nt":
        flags = int(kwargs.get("creationflags", 0) or 0)
        flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        kwargs["creationflags"] = flags
        if kwargs.get("startupinfo") is None:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
            startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
            kwargs["startupinfo"] = startupinfo
    return subprocess.Popen(*args, **kwargs)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass
    os.replace(tmp_path, path)


def _progress(step: str, **fields: object) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [f"{k}={_norm(v)}" for k, v in fields.items() if _norm(v) != ""]
    line = f"{ts} {step}"
    if parts:
        line = f"{line} {' '.join(parts)}"
    if PHASE1_PROGRESS_PATH is not None:
        try:
            PHASE1_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with PHASE1_PROGRESS_PATH.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(line + "\n")
                fh.flush()
        except Exception:
            pass
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:
        pass


def _checkpoint(step: str, **fields: object) -> None:
    global _LAST_COMPLETION_CHECKPOINT
    abort_reason = _parent_watchdog_abort_reason()
    if abort_reason and not _SUCCESS_MARKER_WRITTEN:
        raise RuntimeError(abort_reason)
    requested_checkpoint = _norm(step) or _LAST_COMPLETION_CHECKPOINT
    if _COMPLETION_CHECKPOINT_STATE_PATH is not None and _LAST_COMPLETION_RUN_ID:
        try:
            existing_raw = json.loads(_COMPLETION_CHECKPOINT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing_raw = None
        if isinstance(existing_raw, dict):
            existing_run_id = _norm(existing_raw.get("run_id", ""))
            existing_root_run_id = _root_run_id(existing_run_id)
            current_root_run_id = _root_run_id(_LAST_COMPLETION_RUN_ID)
            existing_checkpoint = _norm(existing_raw.get("checkpoint", ""))
            existing_output_exists = _norm(existing_raw.get("output_exists", "")).lower()
            existing_worker_rc = _norm(existing_raw.get("worker_rc", ""))
            handoff_ready = (
                existing_checkpoint == "owner_post_subcall_read_boundary_wait_returned"
                and existing_output_exists in {"1", "true", "yes"}
                and existing_worker_rc in {"", "0"}
            )
            requested_handoff_ready = False
            if requested_checkpoint == "owner_post_subcall_read_boundary_wait_returned":
                requested_output_exists = _norm(fields.get("output_exists", "")).lower()
                requested_worker_rc = _norm(fields.get("worker_rc", ""))
                requested_handoff_ready = (
                    requested_output_exists in {"1", "true", "yes"}
                    and requested_worker_rc in {"", "0"}
                )
            # Preserve a handoff-ready checkpoint only for the exact same
            # sub-run id. Allow newer SKU sub-runs under the same root run to
            # advance checkpoints independently so terminalization cannot rely
            # on stale handoff-ready state from an earlier SKU.
            if (
                existing_run_id
                and _LAST_COMPLETION_RUN_ID
                and existing_run_id == _LAST_COMPLETION_RUN_ID
                and handoff_ready
                and not requested_handoff_ready
            ):
                _LAST_COMPLETION_CHECKPOINT = existing_checkpoint
                _progress(
                    "completion_checkpoint_regression_ignored",
                    run_id=current_root_run_id,
                    ignored_checkpoint=requested_checkpoint,
                    preserved_checkpoint=existing_checkpoint,
                    existing_run_id=existing_run_id,
                    current_run_id=_LAST_COMPLETION_RUN_ID,
                    reason="handoff_ready_state_already_recorded",
                )
                _progress(
                    "completion_gap_last_checkpoint",
                    checkpoint=existing_checkpoint,
                    run_id=existing_run_id,
                    worker_rc=existing_worker_rc,
                    output_exists=existing_output_exists,
                )
                return
    _LAST_COMPLETION_CHECKPOINT = requested_checkpoint
    payload = {"checkpoint": _LAST_COMPLETION_CHECKPOINT}
    payload.update(fields)
    _progress("completion_gap_last_checkpoint", **payload)
    if _COMPLETION_CHECKPOINT_STATE_PATH is not None:
        try:
            state_payload = {
                "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "run_id": _LAST_COMPLETION_RUN_ID,
                "pid": str(os.getpid()),
                "checkpoint": _LAST_COMPLETION_CHECKPOINT,
            }
            for key, value in fields.items():
                norm_key = _norm(key)
                if not norm_key:
                    continue
                state_payload[norm_key] = _norm(value)
            _atomic_write_text(_COMPLETION_CHECKPOINT_STATE_PATH, json.dumps(state_payload, ensure_ascii=True) + "\n")
        except Exception:
            pass


def _set_parent_watchdog_abort(*, run_id: str, reason: str) -> None:
    with _PARENT_WATCHDOG_ABORT_LOCK:
        _PARENT_WATCHDOG_ABORT_STATE["active"] = "1"
        _PARENT_WATCHDOG_ABORT_STATE["reason"] = _norm(reason)
        _PARENT_WATCHDOG_ABORT_STATE["run_id"] = _norm(run_id)


def _clear_parent_watchdog_abort() -> None:
    with _PARENT_WATCHDOG_ABORT_LOCK:
        _PARENT_WATCHDOG_ABORT_STATE["active"] = "0"
        _PARENT_WATCHDOG_ABORT_STATE["reason"] = ""
        _PARENT_WATCHDOG_ABORT_STATE["run_id"] = ""


def _parent_watchdog_abort_reason() -> str:
    with _PARENT_WATCHDOG_ABORT_LOCK:
        if _PARENT_WATCHDOG_ABORT_STATE.get("active") != "1":
            return ""
        abort_run_id = _norm(_PARENT_WATCHDOG_ABORT_STATE.get("run_id", ""))
        if abort_run_id and _LAST_COMPLETION_RUN_ID and abort_run_id != _LAST_COMPLETION_RUN_ID:
            return ""
        return _norm(_PARENT_WATCHDOG_ABORT_STATE.get("reason", ""))


def _set_completion_checkpoint_context(*, run_id: str, checkpoint_path: Path | None) -> None:
    global _LAST_COMPLETION_RUN_ID, _COMPLETION_CHECKPOINT_STATE_PATH
    _LAST_COMPLETION_RUN_ID = _norm(run_id)
    _COMPLETION_CHECKPOINT_STATE_PATH = checkpoint_path
    if checkpoint_path is not None:
        try:
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass


def _continuation_boundary_mark(*, active: bool, run_id: str = "", sku: str = "", stage: str = "", detail: str = "") -> None:
    with _CONTINUATION_BOUNDARY_LOCK:
        _CONTINUATION_BOUNDARY_STATE["active"] = "1" if active else "0"
        _CONTINUATION_BOUNDARY_STATE["run_id"] = _norm(run_id)
        _CONTINUATION_BOUNDARY_STATE["sku"] = _norm(sku)
        _CONTINUATION_BOUNDARY_STATE["stage"] = _norm(stage)
        _CONTINUATION_BOUNDARY_STATE["detail"] = _norm(detail)


def _emit_continuation_boundary_parent_exit_gap() -> None:
    with _CONTINUATION_BOUNDARY_LOCK:
        active = _CONTINUATION_BOUNDARY_STATE.get("active", "0") == "1"
        run_id = _CONTINUATION_BOUNDARY_STATE.get("run_id", "")
        sku = _CONTINUATION_BOUNDARY_STATE.get("sku", "")
        stage = _CONTINUATION_BOUNDARY_STATE.get("stage", "")
        detail = _CONTINUATION_BOUNDARY_STATE.get("detail", "")
    if not active:
        return
    _progress(
        "continuation_boundary_parent_gap_confirmed",
        run_id=run_id,
        sku=sku,
        stage=stage or "unknown",
        detail=detail,
    )
    _progress(
        "continuation_boundary_parent_exit_gap",
        run_id=run_id,
        sku=sku,
        stage=stage or "unknown",
        detail=detail,
    )


def _owner_wait_mark_enter(
    *,
    run_id: str,
    sku: str,
    subcall_pid: str,
    helper_pid: str,
    timeout_seconds: object,
) -> None:
    run_id_norm = _norm(run_id)
    sku_norm = _norm(sku).upper()
    owner_pid = str(os.getpid())
    with _OWNER_WAIT_LOCK:
        _OWNER_WAIT_STATE["active"] = "1"
        _OWNER_WAIT_STATE["run_id"] = run_id_norm
        _OWNER_WAIT_STATE["sku"] = sku_norm
        _OWNER_WAIT_STATE["owner_pid"] = owner_pid
        _OWNER_WAIT_STATE["subcall_pid"] = _norm(subcall_pid)
        _OWNER_WAIT_STATE["helper_pid"] = _norm(helper_pid)
        _OWNER_WAIT_STATE["state"] = "entered"
        _OWNER_WAIT_STATE["reason"] = "waiting_read_boundary_helper"
    _progress(
        "owner_wait_enter",
        run_id=run_id_norm,
        sku=sku_norm,
        owner_pid=owner_pid,
        subcall_pid=_norm(subcall_pid),
        helper_pid=_norm(helper_pid),
        timeout_seconds=_norm(timeout_seconds),
    )


def _owner_wait_mark_exit(
    *,
    run_id: str,
    sku: str,
    state: str,
    reason: str,
    worker_rc: object = "",
    output_exists: object = "",
) -> None:
    run_id_norm = _norm(run_id)
    sku_norm = _norm(sku).upper()
    owner_pid = str(os.getpid())
    state_norm = _norm(state) or "exited"
    reason_norm = _norm(reason) or "owner_wait_exit"
    _owner_provenance_capture_stop(
        run_id=run_id_norm,
        sku=sku_norm,
        owner_pid=owner_pid,
        state=state_norm,
        reason=reason_norm,
    )
    with _OWNER_WAIT_LOCK:
        _OWNER_WAIT_STATE["active"] = "0"
        _OWNER_WAIT_STATE["run_id"] = run_id_norm
        _OWNER_WAIT_STATE["sku"] = sku_norm
        _OWNER_WAIT_STATE["owner_pid"] = owner_pid
        _OWNER_WAIT_STATE["state"] = state_norm
        _OWNER_WAIT_STATE["reason"] = reason_norm
    _progress(
        "owner_wait_exit",
        run_id=run_id_norm,
        sku=sku_norm,
        owner_pid=owner_pid,
        state=state_norm,
        reason=reason_norm,
        worker_rc=_norm(worker_rc),
        output_exists=_norm(output_exists),
    )
    _progress(
        "owner_exit_reason",
        run_id=run_id_norm,
        sku=sku_norm,
        owner_pid=owner_pid,
        reason=reason_norm,
        state=state_norm,
    )


def _owner_provenance_capture_start(
    *,
    run_id: str,
    sku: str,
    owner_pid: str,
    subcall_pid: str,
    helper_pid: str,
    timeout_seconds: str,
) -> None:
    scope_mode = str(os.environ.get("H110_OWNER_PROVENANCE_SCOPE", "owner_only") or "").strip().lower()
    root_run_id = _root_run_id(run_id)
    owner_scope_only = scope_mode in {"", "owner_only", "root_only"}
    is_owner_scope = (_norm(sku).upper() == "OWNER_SCOPE") and (_norm(run_id) == root_run_id)
    if owner_scope_only and not is_owner_scope:
        _progress(
            "owner_provenance_capture_skipped",
            run_id=run_id,
            sku=sku,
            reason="scope_owner_only",
            scope_mode=scope_mode or "owner_only",
        )
        return
    with _OWNER_PROVENANCE_LOCK:
        already_active = _OWNER_PROVENANCE_STATE.get("active", "0") == "1"
        existing_run_id = _norm(_OWNER_PROVENANCE_STATE.get("run_id", ""))
    if already_active and existing_run_id and (existing_run_id == run_id or existing_run_id.startswith(f"{run_id}_")):
        return
    if os.name != "nt":
        _progress("owner_provenance_capture_skipped", run_id=run_id, sku=sku, reason="non_windows_host")
        return
    script_path = ROOT / "scripts" / "tools" / "h_capture_process_exit.ps1"
    if not script_path.exists():
        _progress("owner_provenance_capture_skipped", run_id=run_id, sku=sku, reason="capture_script_missing")
        return
    token = f"{run_id}.{sku}.{owner_pid}.{time.time_ns()}"
    work_dir = H_LIVE_DIR / "tmp_h110_owner_provenance"
    work_dir.mkdir(parents=True, exist_ok=True)
    stop_signal_path = work_dir / f"stop.{token}.json"
    context_path = work_dir / f"context.{token}.json"
    ready_signal_path = work_dir / f"ready.{token}.txt"
    context_payload = {
        "run_id": run_id,
        "sku": sku,
        "window_label": "owner_wait_enter",
        "window_token": token,
        "owner_pid": owner_pid,
        "subcall_pid": subcall_pid,
        "helper_pid": helper_pid,
        "timeout_seconds": timeout_seconds,
        "launcher_pid": str(os.getppid()),
        "cycle_pid": str(os.getpid()),
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with contextlib.suppress(Exception):
        _atomic_write_text(context_path, json.dumps(context_payload, ensure_ascii=True) + "\n")
    powershell_exe = (
        Path(os.environ.get("SystemRoot", "C:\\Windows"))
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
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-TargetPid",
        owner_pid,
        "-LiveDir",
        str(H_LIVE_DIR),
        "-RunId",
        run_id,
        "-WindowLabel",
        "owner_wait_enter",
        "-WindowToken",
        token,
        "-StopSignalPath",
        str(stop_signal_path),
        "-ContextPath",
        str(context_path),
        "-ReadySignalPath",
        str(ready_signal_path),
    ]
    flags = 0
    flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    flags |= int(getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
    popen_kwargs: dict[str, object] = {
        "cwd": str(ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
        "creationflags": flags,
        "env": os.environ.copy(),
    }
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
        startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
        popen_kwargs["startupinfo"] = startupinfo
    try:
        proc = _popen_hidden(cmd, **popen_kwargs)
    except PermissionError as exc:
        _progress(
            "owner_provenance_capture_spawn_retry",
            run_id=run_id,
            sku=sku,
            reason="permission_error_retry_without_breakaway",
            error=f"{type(exc).__name__}:{exc}",
        )
        retry_kwargs = dict(popen_kwargs)
        retry_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        retry_kwargs["creationflags"] = retry_flags
        try:
            proc = _popen_hidden(cmd, **retry_kwargs)
        except Exception as retry_exc:
            _progress(
                "owner_provenance_capture_error",
                run_id=run_id,
                sku=sku,
                reason="spawn_failed_after_retry",
                error=f"{type(retry_exc).__name__}:{retry_exc}",
            )
            return
    except Exception as exc:
        _progress(
            "owner_provenance_capture_error",
            run_id=run_id,
            sku=sku,
            reason="spawn_failed",
            error=f"{type(exc).__name__}:{exc}",
        )
        return
    with _OWNER_PROVENANCE_LOCK:
        _OWNER_PROVENANCE_STATE["active"] = "1"
        _OWNER_PROVENANCE_STATE["run_id"] = run_id
        _OWNER_PROVENANCE_STATE["sku"] = sku
        _OWNER_PROVENANCE_STATE["owner_pid"] = owner_pid
        _OWNER_PROVENANCE_STATE["monitor_pid"] = str(proc.pid)
        _OWNER_PROVENANCE_STATE["window_token"] = token
        _OWNER_PROVENANCE_STATE["stop_signal_path"] = str(stop_signal_path)
    ready_seen = ready_signal_path.exists()
    if not ready_seen:
        deadline = time.time() + 1.5
        while time.time() < deadline:
            if ready_signal_path.exists():
                ready_seen = True
                break
            time.sleep(0.05)
    _progress(
        "owner_provenance_capture_started",
        run_id=run_id,
        sku=sku,
        owner_pid=owner_pid,
        monitor_pid=str(proc.pid),
        window_token=token,
        stop_signal_path=str(stop_signal_path),
        ready_signal_path=str(ready_signal_path),
        ready_seen="1" if ready_seen else "0",
    )
    if not ready_seen:
        _progress(
            "owner_provenance_capture_error",
            run_id=run_id,
            sku=sku,
            owner_pid=owner_pid,
            monitor_pid=str(proc.pid),
            reason="ready_signal_not_observed",
        )


def _owner_provenance_capture_stop(*, run_id: str, sku: str, owner_pid: str, state: str, reason: str) -> None:
    with _OWNER_PROVENANCE_LOCK:
        active = _OWNER_PROVENANCE_STATE.get("active", "0") == "1"
        state_run_id = _norm(_OWNER_PROVENANCE_STATE.get("run_id", ""))
        stop_signal_path = _norm(_OWNER_PROVENANCE_STATE.get("stop_signal_path", ""))
        monitor_pid = _norm(_OWNER_PROVENANCE_STATE.get("monitor_pid", ""))
        window_token = _norm(_OWNER_PROVENANCE_STATE.get("window_token", ""))
        _OWNER_PROVENANCE_STATE["active"] = "0"
    if not active:
        return
    if state_run_id and run_id and state_run_id != run_id and not state_run_id.startswith(f"{run_id}_"):
        return
    if stop_signal_path:
        payload = {
            "run_id": run_id,
            "sku": sku,
            "owner_pid": owner_pid,
            "state": state,
            "reason": reason,
            "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window_token": window_token,
            "monitor_pid": monitor_pid,
        }
        with contextlib.suppress(Exception):
            _atomic_write_text(Path(stop_signal_path), json.dumps(payload, ensure_ascii=True) + "\n")
    _progress(
        "owner_provenance_capture_stop_signaled",
        run_id=run_id,
        sku=sku,
        owner_pid=owner_pid,
        monitor_pid=monitor_pid,
        window_token=window_token,
        stop_signal_path=stop_signal_path,
        state=state,
        reason=reason,
    )


def _owner_wait_unresolved_reason(*, run_id: str = "") -> str:
    run_id_norm = _norm(run_id)
    with _OWNER_WAIT_LOCK:
        active = _OWNER_WAIT_STATE.get("active", "0") == "1"
        state_run_id = _norm(_OWNER_WAIT_STATE.get("run_id", ""))
        state_reason = _norm(_OWNER_WAIT_STATE.get("reason", ""))
        state_name = _norm(_OWNER_WAIT_STATE.get("state", ""))
    if not active:
        return ""
    if run_id_norm and state_run_id:
        if state_run_id != run_id_norm and not state_run_id.startswith(f"{run_id_norm}_"):
            return ""
    return (
        f"owner_wait_unresolved:{state_name or 'active'}:{state_reason or 'unknown'}:"
        f"{state_run_id or run_id_norm or 'missing_run'}"
    )


def _owner_interrupt_reconcile_mark_enter(*, run_id: str, sku: str, wait_seconds: float) -> None:
    run_id_norm = _norm(run_id)
    sku_norm = _norm(sku).upper()
    bounded_wait = min(max(float(wait_seconds), 0.5), 20.0)
    deadline = time.monotonic() + bounded_wait
    with _OWNER_INTERRUPT_RECONCILE_LOCK:
        _OWNER_INTERRUPT_RECONCILE_STATE["active"] = "1"
        _OWNER_INTERRUPT_RECONCILE_STATE["run_id"] = run_id_norm
        _OWNER_INTERRUPT_RECONCILE_STATE["sku"] = sku_norm
        _OWNER_INTERRUPT_RECONCILE_STATE["deadline_monotonic"] = f"{deadline:.6f}"


def _owner_interrupt_reconcile_mark_exit(*, run_id: str = "") -> None:
    run_id_norm = _norm(run_id)
    with _OWNER_INTERRUPT_RECONCILE_LOCK:
        state_run_id = _norm(_OWNER_INTERRUPT_RECONCILE_STATE.get("run_id", ""))
        if run_id_norm and state_run_id and state_run_id != run_id_norm and not state_run_id.startswith(f"{run_id_norm}_"):
            return
        _OWNER_INTERRUPT_RECONCILE_STATE["active"] = "0"
        _OWNER_INTERRUPT_RECONCILE_STATE["run_id"] = state_run_id if state_run_id else run_id_norm
        _OWNER_INTERRUPT_RECONCILE_STATE["sku"] = _norm(_OWNER_INTERRUPT_RECONCILE_STATE.get("sku", ""))
        _OWNER_INTERRUPT_RECONCILE_STATE["deadline_monotonic"] = "0"


def _owner_interrupt_reconcile_grace_active(*, run_id: str) -> bool:
    now_mono = time.monotonic()
    run_id_norm = _norm(run_id)
    with _OWNER_INTERRUPT_RECONCILE_LOCK:
        active = _OWNER_INTERRUPT_RECONCILE_STATE.get("active", "0") == "1"
        state_run_id = _norm(_OWNER_INTERRUPT_RECONCILE_STATE.get("run_id", ""))
        if not active:
            return False
        if run_id_norm and state_run_id:
            if state_run_id != run_id_norm and not state_run_id.startswith(f"{run_id_norm}_"):
                return False
        deadline_raw = _norm(_OWNER_INTERRUPT_RECONCILE_STATE.get("deadline_monotonic", "0"))
        try:
            deadline = float(deadline_raw)
        except Exception:
            deadline = 0.0
        if deadline <= now_mono:
            _OWNER_INTERRUPT_RECONCILE_STATE["active"] = "0"
            _OWNER_INTERRUPT_RECONCILE_STATE["deadline_monotonic"] = "0"
            return False
        return True


def _parent_terminal_handoff_grace_active(*, run_id: str, parent_cycle_pid: int) -> tuple[bool, str]:
    handoff_path = PHASE1_PARENT_HANDOFF_PATH
    if handoff_path is None:
        return False, "handoff_path_missing"
    if parent_cycle_pid <= 0:
        return False, "parent_pid_missing"
    try:
        if not handoff_path.exists():
            return False, "handoff_path_absent"
        raw = json.loads(handoff_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"handoff_unreadable:{type(exc).__name__}:{exc}"
    if not isinstance(raw, dict):
        return False, "handoff_not_object"
    handoff_run_id = _norm(raw.get("run_id", ""))
    if handoff_run_id != _norm(run_id):
        return False, f"handoff_run_mismatch:{handoff_run_id or 'missing'}"
    handoff_parent_pid = _to_int(raw.get("parent_pid", ""))
    if handoff_parent_pid != int(parent_cycle_pid):
        return False, f"handoff_parent_pid_mismatch:{handoff_parent_pid}"
    handoff_status = _norm(raw.get("status", "")).lower()
    parent_heartbeat_seconds = max(
        _env_float(
            "H_PHASE1_PARENT_HANDOFF_HEARTBEAT_SECONDS",
            _env_float("H110_PARENT_HANDOFF_HEARTBEAT_SECONDS", 30.0),
        ),
        0.5,
    )
    dead_confirm_cycles = max(_env_int("H110_PARENT_DEAD_CONFIRM_CYCLES", 3), 1)
    # Keep this window longer than the parent heartbeat cadence plus watchdog
    # confirmation lag so the child cannot misclassify an active owner before the
    # first heartbeat update arrives.
    min_safe_grace = max(parent_heartbeat_seconds + float(dead_confirm_cycles) + 5.0, 6.0)
    if handoff_status == "pilot_wait_exit_observed":
        grace_seconds = max(_env_float("H110_PARENT_TERMINAL_HANDOFF_GRACE_SECONDS", 8.0), 0.5)
    elif handoff_status in {"pilot_wait_entered", "pilot_wait_heartbeat"}:
        if handoff_status == "pilot_wait_entered":
            configured = _env_float("H110_PARENT_TERMINAL_HANDOFF_WAIT_ENTER_GRACE_SECONDS", min_safe_grace)
        else:
            configured = _env_float("H110_PARENT_TERMINAL_HANDOFF_HEARTBEAT_GRACE_SECONDS", min_safe_grace)
        grace_seconds = max(configured, min_safe_grace)
    else:
        return False, f"handoff_status_not_grace:{handoff_status or 'missing'}"
    try:
        age_seconds = max(time.time() - float(handoff_path.stat().st_mtime), 0.0)
    except Exception as exc:
        return False, f"handoff_age_unavailable:{type(exc).__name__}:{exc}"
    if age_seconds > grace_seconds:
        return False, f"handoff_grace_expired:{age_seconds:.2f}>{grace_seconds:.2f}"
    return True, f"handoff_status={handoff_status}:age_seconds={age_seconds:.2f}:grace_seconds={grace_seconds:.2f}"


def _run_state_terminal_failed_for_run(*, run_id: str) -> tuple[bool, str]:
    run_id_norm = _norm(run_id)
    if not run_id_norm:
        return False, "run_id_missing"
    if not H_RUN_STATE_PATH.exists():
        return False, "run_state_missing"
    try:
        raw = json.loads(H_RUN_STATE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return True, f"run_state_unreadable:{type(exc).__name__}:{exc}"
    if not isinstance(raw, dict):
        return True, "run_state_not_object"
    state_run_id = _norm(raw.get("run_id", ""))
    if state_run_id != run_id_norm:
        return False, f"run_state_run_mismatch:{state_run_id or 'missing'}"
    state_name = _norm(raw.get("state", "")).lower()
    if state_name == "failed":
        failure_detail = _norm(raw.get("failure_detail", ""))
        if failure_detail:
            return True, f"run_state_failed:{failure_detail}"
        return True, "run_state_failed"
    return False, f"run_state_not_failed:{state_name or 'missing'}"


def _set_market_payload_checkpoint_context(*, run_id: str, sku: str, checkpoint_path: Path | None) -> None:
    global _MARKET_PAYLOAD_CHECKPOINT_RUN_ID, _MARKET_PAYLOAD_CHECKPOINT_SKU, _MARKET_PAYLOAD_CHECKPOINT_PATH
    _MARKET_PAYLOAD_CHECKPOINT_RUN_ID = _norm(run_id)
    _MARKET_PAYLOAD_CHECKPOINT_SKU = _norm(sku).upper()
    _MARKET_PAYLOAD_CHECKPOINT_PATH = checkpoint_path


def _market_payload_checkpoint(name: str, **fields: object) -> None:
    name_raw = str(name)

    def _checkpoint_internal_trace(step: str) -> None:
        if name_raw != "market_payload_entry_window_norm_sku_before":
            return
        ts_local = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line_local = (
            f"{ts_local} market_payload_checkpoint_internal "
            f"step={step} checkpoint={name_raw} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
            f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
        )
        with contextlib.suppress(Exception):
            os.write(2, (line_local + "\n").encode("utf-8", errors="replace"))

    _checkpoint_internal_trace("entry")
    payload: dict[str, str] = {
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checkpoint": _norm(name_raw),
        "run_id": _MARKET_PAYLOAD_CHECKPOINT_RUN_ID,
        "sku": _MARKET_PAYLOAD_CHECKPOINT_SKU,
        "pid": str(os.getpid()),
    }
    _checkpoint_internal_trace("payload_dict_built")
    for key, value in fields.items():
        payload[str(key)] = _norm(value)
    _checkpoint_internal_trace("payload_fields_done")
    if _MARKET_PAYLOAD_CHECKPOINT_PATH is not None:
        _checkpoint_internal_trace("atomic_write_enter")
        with contextlib.suppress(Exception):
            _atomic_write_text(_MARKET_PAYLOAD_CHECKPOINT_PATH, json.dumps(payload, ensure_ascii=True) + "\n")
        _checkpoint_internal_trace("atomic_write_return")
    _checkpoint_internal_trace("progress_call_enter")
    _progress(name_raw, **payload)
    _checkpoint_internal_trace("progress_call_return")


def _market_payload_checkpoint_raw(name: str, **fields: object) -> None:
    target_name = "market_payload_setup_to_sku_gap_before_sku_before_emission"
    divergence_target_name = "market_payload_entry_window_to_after_enter_gap_before_first_instruction"
    callsite_divergence_target_name = "market_payload_callsite_to_entry_gap_before_first_instruction"
    callsite_caller_pre_target_name = "caller_pre_checkpoint_call_for_callsite_to_entry_before_first_instruction_checkpoint"

    def _raw_internal_trace(step: str) -> None:
        checkpoint_name = str(name)
        if (
            checkpoint_name != target_name
            and checkpoint_name != divergence_target_name
            and checkpoint_name != callsite_divergence_target_name
            and checkpoint_name != callsite_caller_pre_target_name
        ):
            return
        ts_local = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line_local = (
            f"{ts_local} market_payload_checkpoint_raw_internal "
            f"step={step} checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
            f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
        )
        with contextlib.suppress(Exception):
            os.write(2, (line_local + "\n").encode("utf-8", errors="replace"))
        if checkpoint_name == divergence_target_name and step == "entry":
            boundary_line = (
                f"{ts_local} raw_checkpoint_entry_for_before_first_instruction_checkpoint "
                f"checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
                f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
            )
            with contextlib.suppress(Exception):
                os.write(2, (boundary_line + "\n").encode("utf-8", errors="replace"))
        if checkpoint_name == divergence_target_name and step == "return":
            boundary_line = (
                f"{ts_local} raw_checkpoint_pre_return_for_before_first_instruction_checkpoint "
                f"checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
                f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
            )
            with contextlib.suppress(Exception):
                os.write(2, (boundary_line + "\n").encode("utf-8", errors="replace"))
        if checkpoint_name == callsite_divergence_target_name and step == "entry":
            boundary_line = (
                f"{ts_local} raw_checkpoint_entry_for_callsite_to_entry_before_first_instruction_checkpoint "
                f"checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
                f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
            )
            with contextlib.suppress(Exception):
                os.write(2, (boundary_line + "\n").encode("utf-8", errors="replace"))
        if checkpoint_name == callsite_divergence_target_name and step == "return":
            boundary_line = (
                f"{ts_local} raw_checkpoint_pre_return_for_callsite_to_entry_before_first_instruction_checkpoint "
                f"checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
                f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
            )
            with contextlib.suppress(Exception):
                os.write(2, (boundary_line + "\n").encode("utf-8", errors="replace"))
        if checkpoint_name == callsite_divergence_target_name and step == "line_build_done":
            boundary_line = (
                f"{ts_local} raw_checkpoint_callsite_to_entry_before_first_instruction_final_value_ready "
                f"checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
                f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
            )
            with contextlib.suppress(Exception):
                os.write(2, (boundary_line + "\n").encode("utf-8", errors="replace"))
        if checkpoint_name == callsite_divergence_target_name and step == "return":
            boundary_line = (
                f"{ts_local} raw_checkpoint_callsite_to_entry_before_first_instruction_before_literal_return "
                f"checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
                f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
            )
            with contextlib.suppress(Exception):
                os.write(2, (boundary_line + "\n").encode("utf-8", errors="replace"))
        if checkpoint_name == callsite_caller_pre_target_name and step == "entry":
            boundary_line = (
                f"{ts_local} raw_checkpoint_entry_for_caller_pre_checkpoint_callsite_to_entry_before_first_instruction "
                f"checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
                f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
            )
            with contextlib.suppress(Exception):
                os.write(2, (boundary_line + "\n").encode("utf-8", errors="replace"))
        if checkpoint_name == callsite_caller_pre_target_name and step == "return":
            boundary_line = (
                f"{ts_local} raw_checkpoint_pre_return_for_caller_pre_checkpoint_callsite_to_entry_before_first_instruction "
                f"checkpoint={checkpoint_name} run_id={_MARKET_PAYLOAD_CHECKPOINT_RUN_ID} "
                f"sku={_MARKET_PAYLOAD_CHECKPOINT_SKU} pid={os.getpid()}"
            )
            with contextlib.suppress(Exception):
                os.write(2, (boundary_line + "\n").encode("utf-8", errors="replace"))

    _raw_internal_trace("entry")
    payload: dict[str, str] = {
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checkpoint": str(name),
        "run_id": _MARKET_PAYLOAD_CHECKPOINT_RUN_ID,
        "sku": _MARKET_PAYLOAD_CHECKPOINT_SKU,
        "pid": str(os.getpid()),
    }
    _raw_internal_trace("payload_build_done")
    for key, value in fields.items():
        payload[str(key)] = "" if value is None else str(value)
    _raw_internal_trace("payload_fields_done")
    payload_json = json.dumps(payload, ensure_ascii=True) + "\n"
    _raw_internal_trace("serialization_done")
    if _MARKET_PAYLOAD_CHECKPOINT_PATH is not None:
        _raw_internal_trace("atomic_write_enter")
        with contextlib.suppress(Exception):
            _atomic_write_text(_MARKET_PAYLOAD_CHECKPOINT_PATH, payload_json)
        _raw_internal_trace("atomic_write_return")
    ts = payload["utc"]
    parts = [f"{k}={v}" for k, v in payload.items()]
    line = f"{ts} {str(name)}"
    if parts:
        line = f"{line} {' '.join(parts)}"
    _raw_internal_trace("line_build_done")
    _raw_internal_trace("stderr_write_enter")
    try:
        sys.stderr.write(line + "\n")
        _raw_internal_trace("stderr_write_return")
        _raw_internal_trace("stderr_flush_enter")
        sys.stderr.flush()
        _raw_internal_trace("stderr_flush_return")
    except Exception:
        _raw_internal_trace("stderr_write_or_flush_except")
        pass
    _raw_internal_trace("return")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False

    def _pid_alive_windows_fallback(target_pid: int) -> bool:
        try:
            probe = subprocess.run(
                ["tasklist", "/FI", f"PID eq {target_pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
        except Exception:
            return False
        combined = f"{probe.stdout or ''}\n{probe.stderr or ''}".strip()
        if not combined:
            return False
        if "No tasks are running which match the specified criteria" in combined:
            return False
        return f"\"{target_pid}\"" in combined

    # Avoid os.kill(..., 0) on Windows; this probe has intermittently raised
    # interpreter-level SystemError in detached terminalizer workers.
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
                    # If query fails after opening the handle, prefer alive over
                    # false dead classification in watchdog paths.
                    return True
                finally:
                    with contextlib.suppress(Exception):
                        close_handle(handle)
            # Access denied can happen under some host security contexts even
            # when the target process is alive.
            last_error = ctypes.get_last_error()
            if int(last_error or 0) == 5:
                return True
        except Exception:
            pass
        return _pid_alive_windows_fallback(pid)
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False
    except Exception:
        return False


def _run_post_exit_terminalizer(
    *,
    run_id: str,
    parent_pid: int,
    marker_path: Path,
    result_path: Path,
    checkpoint_path: Path | None,
    wait_seconds: float,
) -> int:
    try:
        def _write_terminal_failure_result_if_missing(*, reason: str) -> tuple[bool, str]:
            try:
                if result_path.exists():
                    try:
                        if int(result_path.stat().st_size) > 0:
                            return True, "already_present"
                    except Exception:
                        pass
                payload = {
                    "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "run_id": _norm(run_id),
                    "phase1_pilot": "1",
                    "phase1_terminal_status": "failed",
                    "phase1_terminal_reason": _norm(reason) or "parent_cycle_dead_before_pilot_terminal",
                    "write_status": "PILOT_FAILED",
                    "reason_codes_csv": _norm(reason) or "parent_cycle_dead_before_pilot_terminal",
                    "phase1_sku": "",
                    "phase1_skus_processed_csv": "",
                    "phase1_skus_processed_count": "0",
                    "executioner_live_write_attempted": "0",
                    "executioner_live_write_success": "0",
                }
                _atomic_write_text(result_path, json.dumps(payload, ensure_ascii=True) + "\n")
                size = int(result_path.stat().st_size) if result_path.exists() else 0
                if size <= 0:
                    return False, "result_file_empty_after_write"
                return True, "written"
            except Exception as exc:
                return False, f"result_write_error:{type(exc).__name__}:{exc}"

        def _fail_closed_parent_death_cleanup(*, reason: str) -> None:
            result_ok, result_status = _write_terminal_failure_result_if_missing(reason=reason)
            _progress(
                "post_exit_terminalizer_fail_closed_cleanup",
                run_id=run_id,
                reason=_norm(reason),
                result_status=result_status,
                run_state_status="skipped_no_global_state_mutation",
                ownership_status="skipped_no_owner_cleanup_mutation",
                status="ok" if result_ok else "partial",
            )

        def _recent_run_activity_count(*, activity_window_seconds: float) -> int:
            window = max(float(activity_window_seconds), 0.5)
            now_ts = time.time()
            recent_count = 0
            for path in H_LIVE_DIR.glob("tmp_h110_*/*"):
                try:
                    path_name = str(path.name)
                except Exception:
                    continue
                if run_id not in path_name:
                    continue
                try:
                    age_seconds = max(now_ts - float(path.stat().st_mtime), 0.0)
                except Exception:
                    continue
                if age_seconds <= window:
                    recent_count += 1
                    if recent_count >= 64:
                        break
            if PHASE1_PROGRESS_PATH is not None and PHASE1_PROGRESS_PATH.exists():
                try:
                    age_seconds = max(now_ts - float(PHASE1_PROGRESS_PATH.stat().st_mtime), 0.0)
                    if age_seconds <= window:
                        with PHASE1_PROGRESS_PATH.open("rb") as fh:
                            fh.seek(0, os.SEEK_END)
                            size = int(fh.tell())
                            read_bytes = min(size, 32768)
                            if read_bytes > 0:
                                fh.seek(-read_bytes, os.SEEK_END)
                                tail = fh.read(read_bytes).decode("utf-8", errors="replace")
                                if f"run_id={run_id}" in tail:
                                    recent_count += 1
                except Exception:
                    pass
            return recent_count

        def _checkpoint_owner_wait_timeout_seconds() -> float | None:
            if checkpoint_path is None or (not checkpoint_path.exists()):
                return None
            try:
                checkpoint_raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            except Exception:
                return None
            if not isinstance(checkpoint_raw, dict):
                return None
            checkpoint_name = _norm(checkpoint_raw.get("checkpoint", ""))
            if checkpoint_name != "owner_post_subcall_read_boundary_wait_enter":
                return None
            timeout_seconds = _to_float(checkpoint_raw.get("timeout_seconds", ""))
            if timeout_seconds is None or timeout_seconds <= 0:
                timeout_seconds = 110.0
            return float(timeout_seconds)

        def _checkpoint_owner_wait_pid() -> int:
            if checkpoint_path is None or (not checkpoint_path.exists()):
                return 0
            try:
                checkpoint_raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            except Exception:
                return 0
            if not isinstance(checkpoint_raw, dict):
                return 0
            pid_text = _norm(checkpoint_raw.get("pid", ""))
            if not pid_text.isdigit():
                return 0
            pid_value = int(pid_text)
            return pid_value if pid_value > 0 else 0

        def _checkpoint_owner_wait_handoff_ready() -> tuple[bool, str]:
            if checkpoint_path is None or (not checkpoint_path.exists()):
                return (False, "")
            try:
                checkpoint_raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            except Exception:
                return (False, "")
            if not isinstance(checkpoint_raw, dict):
                return (False, "")
            checkpoint_name = _norm(checkpoint_raw.get("checkpoint", ""))
            if checkpoint_name != "owner_post_subcall_read_boundary_wait_returned":
                return (False, checkpoint_name)
            output_exists = _norm(checkpoint_raw.get("output_exists", "")).lower()
            worker_rc = _norm(checkpoint_raw.get("worker_rc", ""))
            if output_exists in {"1", "true", "yes"} and worker_rc in {"", "0"}:
                return (True, checkpoint_name)
            return (False, checkpoint_name)

        initial_wait_seconds = max(wait_seconds, 0.5)
        pilot_max_timeout_seconds = max(_env_float("H_PHASE1_PILOT_MAX_TIMEOUT_SECONDS", 900.0), 240.0)
        observe_default_seconds = max(pilot_max_timeout_seconds + 60.0, 300.0)
        observe_max_seconds = max(
            _env_float("H110_POST_EXIT_TERMINALIZER_MAX_OBSERVE_SECONDS", observe_default_seconds),
            initial_wait_seconds,
        )
        observe_deadline = time.monotonic() + observe_max_seconds
        parent_dead_observed = False
        parent_alive_after_wait = False
        while time.monotonic() < observe_deadline:
            parent_alive_now = _pid_alive(parent_pid)
            if not parent_alive_now:
                parent_dead_observed = True
                parent_alive_after_wait = False
                break
            if marker_path.exists():
                marker_status_now = ""
                marker_run_id_now = ""
                with contextlib.suppress(Exception):
                    marker_raw_now = json.loads(marker_path.read_text(encoding="utf-8"))
                    if isinstance(marker_raw_now, dict):
                        marker_status_now = _norm(marker_raw_now.get("status", "")).lower()
                        marker_run_id_now = _norm(marker_raw_now.get("run_id", ""))
                if marker_status_now and (not marker_run_id_now or marker_run_id_now == run_id):
                    if marker_status_now != "started":
                        _progress(
                            "post_exit_terminalizer_noop",
                            run_id=run_id,
                            reason=f"observe_marker_terminal:{marker_status_now}",
                        )
                        return 0
                if result_path.exists():
                    result_size_now = 0
                    with contextlib.suppress(Exception):
                        result_size_now = int(result_path.stat().st_size)
                    if result_size_now > 0:
                        _progress(
                            "post_exit_terminalizer_noop",
                            run_id=run_id,
                            reason="observe_result_present",
                            result_size=str(result_size_now),
                        )
                        return 0
            time.sleep(0.25)
        else:
            parent_alive_after_wait = _pid_alive(parent_pid)
        _progress(
            "post_exit_terminalizer_checked",
            run_id=run_id,
            parent_pid=str(parent_pid),
            marker_path=str(marker_path),
            result_path=str(result_path),
            parent_alive="1" if parent_alive_after_wait else "0",
            parent_dead_observed="1" if parent_dead_observed else "0",
            initial_wait_seconds=f"{initial_wait_seconds:.2f}",
            observe_max_seconds=f"{observe_max_seconds:.2f}",
        )
        if parent_alive_after_wait and not parent_dead_observed:
            _progress(
                "post_exit_terminalizer_noop",
                run_id=run_id,
                reason="parent_still_alive_after_observe_window",
            )
            return 0
        if parent_alive_after_wait and parent_dead_observed:
            _progress(
                "post_exit_terminalizer_parent_pid_reuse_suspected",
                run_id=run_id,
                reason="parent_dead_then_alive_detected",
                parent_pid=str(parent_pid),
            )
        if not marker_path.exists():
            _progress(
                "post_exit_terminalizer_noop",
                run_id=run_id,
                reason="marker_missing",
            )
            return 0
        try:
            marker_raw = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _progress(
                "post_exit_terminalizer_error",
                run_id=run_id,
                reason="marker_invalid_json",
                error=f"{type(exc).__name__}:{exc}",
            )
            return 1
        if not isinstance(marker_raw, dict):
            _progress(
                "post_exit_terminalizer_noop",
                run_id=run_id,
                reason="marker_not_object",
            )
            return 0
        marker_status = _norm(marker_raw.get("status", "")).lower()
        marker_run_id = _norm(marker_raw.get("run_id", ""))
        if marker_run_id and marker_run_id != run_id:
            _progress(
                "post_exit_terminalizer_noop",
                run_id=run_id,
                reason=f"run_id_mismatch:{marker_run_id}",
            )
            return 0
        if marker_status != "started":
            if marker_status == "failed":
                marker_reason = _norm(marker_raw.get("reason", ""))
                _fail_closed_parent_death_cleanup(
                    reason=marker_reason or "parent_cycle_dead_before_pilot_terminal"
                )
            _progress(
                "post_exit_terminalizer_noop",
                run_id=run_id,
                reason=f"marker_already_terminal:{marker_status or 'missing'}",
            )
            return 0
        result_exists = result_path.exists()
        result_size = 0
        if result_exists:
            try:
                result_size = int(result_path.stat().st_size)
            except Exception:
                result_size = 0
        if result_exists and result_size > 0:
            _progress(
                "post_exit_terminalizer_noop",
                run_id=run_id,
                reason="result_present",
                result_path=str(result_path),
                result_size=str(result_size),
            )
            return 0
        guard_seconds = max(_env_float("H110_TERMINALIZER_FALSE_FAIL_GUARD_SECONDS", 20.0), 1.0)
        guard_interval_seconds = max(_env_float("H110_TERMINALIZER_FALSE_FAIL_GUARD_INTERVAL_SECONDS", 0.5), 0.1)
        guard_activity_window_seconds = max(
            _env_float("H110_TERMINALIZER_FALSE_FAIL_GUARD_ACTIVITY_WINDOW_SECONDS", 6.0),
            guard_interval_seconds,
        )
        guard_start_monotonic = time.monotonic()
        guard_deadline = guard_start_monotonic + guard_seconds
        owner_wait_guard_max_seconds = max(
            _env_float("H110_TERMINALIZER_OWNER_WAIT_MAX_SECONDS", 140.0),
            guard_seconds,
        )
        max_guard_deadline = guard_start_monotonic + owner_wait_guard_max_seconds
        guard_attempt = 0
        _progress(
            "terminalizer_false_fail_guard_enter",
            run_id=run_id,
            parent_pid=str(parent_pid),
            marker_status=marker_status or "missing",
            guard_seconds=f"{guard_seconds:.2f}",
            guard_interval_seconds=f"{guard_interval_seconds:.2f}",
            activity_window_seconds=f"{guard_activity_window_seconds:.2f}",
        )
        recent_activity_count = 0
        while time.monotonic() < guard_deadline:
            guard_attempt += 1
            parent_alive_now = _pid_alive(parent_pid)
            if parent_alive_now:
                if parent_dead_observed:
                    _progress(
                        "terminalizer_false_fail_guard_attempt",
                        run_id=run_id,
                        attempt=str(guard_attempt),
                        parent_alive="1",
                        marker_status=marker_status or "missing",
                        result_exists="1" if result_exists else "0",
                        result_size=str(result_size),
                        recent_activity_count="0",
                        parent_pid_reuse_suspected="1",
                    )
                    _progress(
                        "terminalizer_false_fail_guard_continue",
                        run_id=run_id,
                        attempt=str(guard_attempt),
                        reason="parent_pid_reuse_suspected",
                        recent_activity_count="0",
                        remaining_seconds=f"{max(guard_deadline - time.monotonic(), 0.0):.2f}",
                    )
                    time.sleep(guard_interval_seconds)
                    continue
                _progress(
                    "terminalizer_false_fail_guard_attempt",
                    run_id=run_id,
                    attempt=str(guard_attempt),
                    parent_alive="1",
                    marker_status=marker_status or "missing",
                    result_exists="1" if result_exists else "0",
                    result_size=str(result_size),
                    recent_activity_count="0",
                )
                _progress(
                    "terminalizer_false_fail_guard_final",
                    run_id=run_id,
                    decision="noop_parent_alive",
                    attempt=str(guard_attempt),
                )
                _progress("post_exit_terminalizer_noop", run_id=run_id, reason="guard_parent_alive")
                return 0
            if marker_path.exists():
                try:
                    marker_raw_now = json.loads(marker_path.read_text(encoding="utf-8"))
                    if isinstance(marker_raw_now, dict):
                        marker_status = _norm(marker_raw_now.get("status", "")).lower()
                except Exception:
                    marker_status = marker_status or "started"
            result_exists = result_path.exists()
            result_size = 0
            if result_exists:
                with contextlib.suppress(Exception):
                    result_size = int(result_path.stat().st_size)
            recent_activity_count = _recent_run_activity_count(
                activity_window_seconds=guard_activity_window_seconds
            )
            if recent_activity_count > 0:
                activity_requested_deadline = min(max_guard_deadline, time.monotonic() + guard_seconds)
                if activity_requested_deadline > (guard_deadline + 0.5):
                    guard_deadline = activity_requested_deadline
                    _progress(
                        "terminalizer_false_fail_guard_extend_recent_activity",
                        run_id=run_id,
                        attempt=str(guard_attempt),
                        recent_activity_count=str(recent_activity_count),
                        guard_seconds=f"{guard_seconds:.2f}",
                        remaining_seconds=f"{max(guard_deadline - time.monotonic(), 0.0):.2f}",
                    )
            owner_wait_timeout_seconds = _checkpoint_owner_wait_timeout_seconds()
            if owner_wait_timeout_seconds is not None:
                requested_guard_seconds = min(
                    max(owner_wait_timeout_seconds + 15.0, guard_seconds),
                    owner_wait_guard_max_seconds,
                )
                requested_deadline = guard_start_monotonic + requested_guard_seconds
                if requested_deadline > (guard_deadline + 0.5):
                    guard_deadline = requested_deadline
                    _progress(
                        "terminalizer_false_fail_guard_extend_owner_wait",
                        run_id=run_id,
                        attempt=str(guard_attempt),
                        checkpoint="owner_post_subcall_read_boundary_wait_enter",
                        checkpoint_timeout_seconds=f"{owner_wait_timeout_seconds:.2f}",
                        guard_seconds=f"{requested_guard_seconds:.2f}",
                        remaining_seconds=f"{max(guard_deadline - time.monotonic(), 0.0):.2f}",
                    )
            _progress(
                "terminalizer_false_fail_guard_attempt",
                run_id=run_id,
                attempt=str(guard_attempt),
                parent_alive="0",
                marker_status=marker_status or "missing",
                result_exists="1" if result_exists else "0",
                result_size=str(result_size),
                recent_activity_count=str(recent_activity_count),
            )
            if marker_status != "started":
                _progress(
                    "terminalizer_false_fail_guard_final",
                    run_id=run_id,
                    decision="noop_marker_terminal",
                    attempt=str(guard_attempt),
                    marker_status=marker_status or "missing",
                )
                _progress(
                    "post_exit_terminalizer_noop",
                    run_id=run_id,
                    reason=f"guard_marker_terminal:{marker_status or 'missing'}",
                )
                return 0
            if result_exists and result_size > 0:
                _progress(
                    "terminalizer_false_fail_guard_final",
                    run_id=run_id,
                    decision="noop_result_present",
                    attempt=str(guard_attempt),
                    result_size=str(result_size),
                )
                _progress(
                    "post_exit_terminalizer_noop",
                    run_id=run_id,
                    reason="guard_result_present",
                    result_path=str(result_path),
                    result_size=str(result_size),
                )
                return 0
            handoff_ready, handoff_checkpoint = _checkpoint_owner_wait_handoff_ready()
            if handoff_ready:
                _progress(
                    "terminalizer_false_fail_guard_final",
                    run_id=run_id,
                    decision="noop_checkpoint_handoff_ready",
                    attempt=str(guard_attempt),
                    checkpoint=handoff_checkpoint or "owner_post_subcall_read_boundary_wait_returned",
                )
                _progress(
                    "post_exit_terminalizer_noop",
                    run_id=run_id,
                    reason="guard_checkpoint_handoff_ready",
                    checkpoint=handoff_checkpoint or "owner_post_subcall_read_boundary_wait_returned",
                )
                return 0
            _progress(
                "terminalizer_false_fail_guard_continue",
                run_id=run_id,
                attempt=str(guard_attempt),
                reason="recent_activity_detected" if recent_activity_count > 0 else "awaiting_terminal_artifacts",
                recent_activity_count=str(recent_activity_count),
                remaining_seconds=f"{max(guard_deadline - time.monotonic(), 0.0):.2f}",
            )
            time.sleep(guard_interval_seconds)
        owner_wait_pid = _checkpoint_owner_wait_pid()
        owner_wait_alive = owner_wait_pid > 0 and _pid_alive(owner_wait_pid)
        if owner_wait_alive:
            _progress(
                "terminalizer_false_fail_guard_final",
                run_id=run_id,
                decision="noop_owner_wait_pid_alive",
                owner_wait_pid=str(owner_wait_pid),
                attempts=str(guard_attempt),
            )
            _progress(
                "post_exit_terminalizer_noop",
                run_id=run_id,
                reason="guard_owner_wait_pid_alive",
                owner_wait_pid=str(owner_wait_pid),
            )
            return 0
        _progress(
            "terminalizer_false_fail_guard_timeout",
            run_id=run_id,
            attempts=str(guard_attempt),
            marker_status=marker_status or "missing",
            result_exists="1" if result_exists else "0",
            result_size=str(result_size),
        )
        checkpoint_name = ""
        if checkpoint_path is not None and checkpoint_path.exists():
            try:
                checkpoint_raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                if isinstance(checkpoint_raw, dict):
                    checkpoint_name = _norm(checkpoint_raw.get("checkpoint", ""))
            except Exception:
                checkpoint_name = ""
        failure_reason = "post_exit_terminalizer_started_marker_timeout"
        if checkpoint_name:
            failure_reason = f"full_worker_convergence_failed:{checkpoint_name}"
        _progress(
            "owner_wait_exit",
            run_id=run_id,
            sku="",
            owner_pid=str(parent_pid),
            state="abandoned",
            reason=failure_reason,
            worker_rc="",
            output_exists="0",
        )
        _progress(
            "owner_exit_reason",
            run_id=run_id,
            sku="",
            owner_pid=str(parent_pid),
            state="post_exit_terminalizer_owner_gap",
            reason=failure_reason,
        )
        _progress(
            "full_worker_convergence_failed",
            run_id=run_id,
            stage="post_exit_terminalizer",
            checkpoint=checkpoint_name or "missing",
            reason=failure_reason,
        )
        _progress(
            "terminalizer_false_fail_guard_final",
            run_id=run_id,
            decision="write_failed_marker",
            reason=failure_reason,
            checkpoint=checkpoint_name or "missing",
        )
        payload = {
            "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "failed",
            "run_id": run_id,
            "reason": failure_reason,
            "result_path": str(result_path),
            "result_ok": "0",
        }
        _atomic_write_text(marker_path, json.dumps(payload, ensure_ascii=True) + "\n")
        _progress(
            "post_exit_terminalizer_failed_written",
            run_id=run_id,
            marker_path=str(marker_path),
            result_path=str(result_path),
            reason=failure_reason,
        )
        _fail_closed_parent_death_cleanup(reason=failure_reason)
        return 0
    except Exception as exc:
        failure_reason = f"post_exit_terminalizer_exception:{type(exc).__name__}"
        with contextlib.suppress(Exception):
            if marker_path.exists():
                marker_raw = json.loads(marker_path.read_text(encoding="utf-8"))
                if isinstance(marker_raw, dict):
                    marker_status = _norm(marker_raw.get("status", "")).lower()
                    marker_run_id = _norm(marker_raw.get("run_id", ""))
                    if marker_status == "started" and (not marker_run_id or marker_run_id == run_id):
                        marker_payload = {
                            "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "status": "failed",
                            "run_id": run_id,
                            "reason": failure_reason,
                            "result_path": str(result_path),
                            "result_ok": "0",
                        }
                        _atomic_write_text(marker_path, json.dumps(marker_payload, ensure_ascii=True) + "\n")
        with contextlib.suppress(Exception):
            if (not result_path.exists()) or int(result_path.stat().st_size) <= 0:
                result_payload = {
                    "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "run_id": _norm(run_id),
                    "phase1_pilot": "1",
                    "phase1_terminal_status": "failed",
                    "phase1_terminal_reason": failure_reason,
                    "write_status": "PILOT_FAILED",
                    "reason_codes_csv": failure_reason,
                    "phase1_sku": "",
                    "phase1_skus_processed_csv": "",
                    "phase1_skus_processed_count": "0",
                    "executioner_live_write_attempted": "0",
                    "executioner_live_write_success": "0",
                }
                _atomic_write_text(result_path, json.dumps(result_payload, ensure_ascii=True) + "\n")
        _progress(
            "post_exit_terminalizer_skip_global_state_mutation",
            run_id=run_id,
            reason="core_owner_authority_only",
            state_path=str(H_RUN_STATE_PATH),
        )
        _progress(
            "post_exit_terminalizer_error",
            run_id=run_id,
            reason="terminalizer_exception",
            error=f"{type(exc).__name__}:{exc}",
        )
        return 0


def _to_bool_int(value: object, default: int = 0) -> int:
    return 1 if _to_bool(value, default=bool(default)) else 0


def _invoke_sku_pre_result_helper(
    *,
    run_id: str,
    sku: str,
    cfg: dict[str, object],
    universe_row: dict[str, str],
    listing_row: dict[str, str],
    listing_snapshot_path: str,
    seller_snapshot_path: str,
) -> dict[str, object]:
    _continuation_boundary_mark(
        active=True,
        run_id=run_id,
        sku=sku,
        stage="spawn_wait_boundary",
        detail="enter",
    )
    helper_dir = H_LIVE_DIR / "tmp_h110_sku_helper"
    helper_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{os.getpid()}.{time.time_ns()}"
    boundary_input_path = helper_dir / f"wait_boundary.in.{token}.json"
    boundary_output_path = helper_dir / f"wait_boundary.out.{token}.json"
    boundary_stdout_path = helper_dir / f"wait_boundary.stdout.{token}.log"
    boundary_stderr_path = helper_dir / f"wait_boundary.stderr.{token}.log"
    req = {
        "run_id": run_id,
        "sku": sku,
        "cfg_marketplace_id": _norm(_cfg_get(cfg, "marketplace_id", default="")),
        "cfg_sku": _norm(_cfg_get(cfg, "sku", default="")),
        "cfg_asin": _norm(_cfg_get(cfg, "asin", default="")),
        "cfg_seller_id": _norm(_cfg_get(cfg, "seller_id", default="")),
        "universe_row": universe_row,
        "listing_row": listing_row,
        "listing_snapshot_path": _norm(listing_snapshot_path),
        "seller_snapshot_path": _norm(seller_snapshot_path),
    }
    # Reliability reduction: default to inline helper contract path and avoid fragile nested wait/join subprocess chain.
    if _norm(os.environ.get("H110_HELPER_WAIT_BOUNDARY_INLINE", "1")) != "0":
        _progress(
            "helper_wait_boundary_spawned",
            run_id=run_id,
            sku=sku,
            child_pid="inline",
            boundary_input_path="inline_contract",
            boundary_output_path="inline_contract",
            stdout_path="inline_contract",
            stderr_path="inline_contract",
        )
        _progress(
            "parent_continuation_enter",
            run_id=run_id,
            sku=sku,
            stage="helper_wait_boundary_inline",
        )
        _progress(
            "continuation_boundary_read_start",
            run_id=run_id,
            sku=sku,
            boundary_output_path="inline_contract",
        )
        _continuation_boundary_mark(
            active=True,
            run_id=run_id,
            sku=sku,
            stage="inline_contract",
            detail="read_start",
        )
        try:
            helper_token = f"inline.{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
            helper_input_path = helper_dir / f"in.{helper_token}.json"
            helper_output_path = helper_dir / f"out.{helper_token}.json"
            helper_stdout_path = helper_dir / f"stdout.{helper_token}.log"
            helper_stderr_path = helper_dir / f"stderr.{helper_token}.log"
            _atomic_write_text(helper_input_path, json.dumps(req, ensure_ascii=True) + "\n")
            helper_cmd = _self_python_cmd(
                "--sku-pre-result-helper",
                "--sku-helper-input",
                str(helper_input_path),
                "--sku-helper-output",
                str(helper_output_path),
            )
            timeout_seconds = max(_env_int("H110_INLINE_HELPER_TIMEOUT_SECONDS", 90), 20)
            with helper_stdout_path.open("wb") as out_fh, helper_stderr_path.open("wb") as err_fh:
                proc = _popen_hidden(
                    helper_cmd,
                    cwd=str(ROOT),
                    stdin=subprocess.DEVNULL,
                    stdout=out_fh,
                    stderr=err_fh,
                    close_fds=True,
                    env=os.environ.copy(),
                )
                deadline = time.monotonic() + float(timeout_seconds)
                while True:
                    rc_now = proc.poll()
                    if rc_now is not None:
                        break
                    if time.monotonic() >= deadline:
                        with contextlib.suppress(Exception):
                            proc.terminate()
                        with contextlib.suppress(Exception):
                            proc.wait(timeout=3.0)
                        if proc.poll() is None:
                            with contextlib.suppress(Exception):
                                proc.kill()
                            with contextlib.suppress(Exception):
                                proc.wait(timeout=3.0)
                        raise RuntimeError("inline_contract_helper_timeout")
                    time.sleep(0.1)
            if not helper_output_path.exists():
                raise RuntimeError("inline_contract_helper_missing_output")
            try:
                contract_raw = json.loads(helper_output_path.read_text(encoding="utf-8"))
            except Exception as json_exc:
                raise RuntimeError(f"inline_contract_helper_invalid_json:{type(json_exc).__name__}:{json_exc}") from json_exc
            if not isinstance(contract_raw, dict):
                raise RuntimeError("inline_contract_helper_output_not_object")
            helper_status = _norm(contract_raw.get("status", "")).lower()
            if helper_status != "ok":
                helper_reason = _norm(contract_raw.get("reason", "")) or "helper_status_not_ok"
                raise RuntimeError(f"inline_contract_helper_failed:{helper_reason}")
        except BaseException as exc:
            _progress(
                "helper_wait_boundary_failed",
                run_id=run_id,
                sku=sku,
                reason="inline_contract_failed",
                error=f"{type(exc).__name__}:{exc}",
            )
            _progress(
                "continuation_boundary_failed",
                run_id=run_id,
                sku=sku,
                stage="inline_contract",
                reason="inline_contract_failed",
                error=f"{type(exc).__name__}:{exc}",
            )
            _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="inline_contract_failed")
            raise RuntimeError(f"continuation_boundary_failed:inline_contract_failed:{type(exc).__name__}:{exc}") from exc
        if not isinstance(contract_raw, dict):
            _progress(
                "helper_wait_boundary_invalid",
                run_id=run_id,
                sku=sku,
                reason="inline_contract_not_object",
            )
            _progress(
                "continuation_boundary_failed",
                run_id=run_id,
                sku=sku,
                stage="inline_contract",
                reason="inline_contract_not_object",
            )
            _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="inline_contract_not_object")
            raise RuntimeError("continuation_boundary_failed:inline_contract_not_object")
        _progress(
            "helper_wait_boundary_read",
            run_id=run_id,
            sku=sku,
            boundary_status="valid",
            boundary_reason="inline_contract",
            rc="0",
            boundary_output_path="inline_contract",
        )
        _progress(
            "continuation_boundary_read_done",
            run_id=run_id,
            sku=sku,
            boundary_status="valid",
            boundary_reason="inline_contract",
            rc="0",
        )
        _progress(
            "helper_wait_boundary_valid",
            run_id=run_id,
            sku=sku,
            boundary_reason="inline_contract",
            rc="0",
        )
        _progress(
            "continuation_boundary_accept_start",
            run_id=run_id,
            sku=sku,
            helper_output_path="inline_contract",
        )
        _progress(
            "continuation_boundary_accept_done",
            run_id=run_id,
            sku=sku,
            status="ok",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="done", detail="inline_contract_ok")
        return contract_raw
    _atomic_write_text(boundary_input_path, json.dumps(req, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--helper-wait-boundary",
        "--wait-boundary-input",
        str(boundary_input_path),
        "--wait-boundary-output",
        str(boundary_output_path),
        "--wait-boundary-run-id",
        run_id,
        "--wait-boundary-sku",
        sku,
    )
    with boundary_stdout_path.open("wb") as out_fh, boundary_stderr_path.open("wb") as err_fh:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            close_fds=True,
            env=os.environ.copy(),
        )
        _progress(
            "helper_wait_boundary_spawned",
            run_id=run_id,
            sku=sku,
            child_pid=str(proc.pid),
            boundary_input_path=str(boundary_input_path),
            boundary_output_path=str(boundary_output_path),
            stdout_path=str(boundary_stdout_path),
            stderr_path=str(boundary_stderr_path),
        )
        _progress(
            "parent_continuation_enter",
            run_id=run_id,
            sku=sku,
            stage="helper_wait_boundary",
        )
        timeout_seconds = max(_env_int("H110_HELPER_WAIT_BOUNDARY_TIMEOUT_SECONDS", 70), 15)
        join_input_path = helper_dir / f"join_isolation.in.{token}.json"
        join_output_path = helper_dir / f"join_isolation.out.{token}.json"
        join_req = {
            "run_id": run_id,
            "sku": sku,
            "boundary_output_path": str(boundary_output_path),
            "timeout_seconds": str(timeout_seconds),
        }
        _atomic_write_text(join_input_path, json.dumps(join_req, ensure_ascii=True) + "\n")
        join_cmd = _self_python_cmd(
            "--join-isolation",
            "--join-input",
            str(join_input_path),
            "--join-output",
            str(join_output_path),
            "--join-run-id",
            run_id,
            "--join-sku",
            sku,
        )
        join_proc = _popen_hidden(
            join_cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            env=os.environ.copy(),
        )
        _progress(
            "join_isolation_spawned",
            run_id=run_id,
            sku=sku,
            child_pid=str(join_proc.pid),
            join_input_path=str(join_input_path),
            join_output_path=str(join_output_path),
            boundary_output_path=str(boundary_output_path),
            timeout_seconds=str(timeout_seconds),
        )
        join_deadline = time.monotonic() + float(timeout_seconds + 30)
        while time.monotonic() < join_deadline:
            if join_output_path.exists():
                break
            if join_proc.poll() is not None and not join_output_path.exists():
                break
            time.sleep(0.1)
    if not join_output_path.exists():
        _progress(
            "join_isolation_failed",
            run_id=run_id,
            sku=sku,
            reason="missing_join_output_json",
            join_output_path=str(join_output_path),
            boundary_output_path=str(boundary_output_path),
        )
        _progress(
            "helper_wait_boundary_failed",
            run_id=run_id,
            sku=sku,
            reason="join_isolation_missing_output",
        )
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="join_isolation",
            reason="missing_join_output_json",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="join_isolation_missing_output")
        raise RuntimeError("join_isolation_failed:missing_join_output_json")
    try:
        join_raw = json.loads(join_output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _progress(
            "join_isolation_invalid",
            run_id=run_id,
            sku=sku,
            reason="invalid_json",
            error=f"{type(exc).__name__}:{exc}",
            join_output_path=str(join_output_path),
        )
        _progress(
            "join_isolation_failed",
            run_id=run_id,
            sku=sku,
            reason="invalid_json",
            join_output_path=str(join_output_path),
        )
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="join_isolation",
            reason="invalid_json",
            error=f"{type(exc).__name__}:{exc}",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="join_isolation_invalid_json")
        raise RuntimeError(f"join_isolation_failed:invalid_json:{type(exc).__name__}:{exc}") from exc
    if not isinstance(join_raw, dict):
        _progress(
            "join_isolation_invalid",
            run_id=run_id,
            sku=sku,
            reason="join_output_not_object",
            join_output_path=str(join_output_path),
        )
        _progress(
            "join_isolation_failed",
            run_id=run_id,
            sku=sku,
            reason="join_output_not_object",
            join_output_path=str(join_output_path),
        )
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="join_isolation",
            reason="join_output_not_object",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="join_output_not_object")
        raise RuntimeError("join_isolation_failed:join_output_not_object")
    join_status = _norm(join_raw.get("join_status", "")).lower()
    join_reason = _norm(join_raw.get("reason", ""))
    _progress(
        "join_isolation_read",
        run_id=run_id,
        sku=sku,
        join_status=join_status or "missing",
        reason=join_reason,
        join_output_path=str(join_output_path),
    )
    if join_status != "valid":
        _progress(
            "join_isolation_invalid",
            run_id=run_id,
            sku=sku,
            reason=join_reason or "join_status_invalid",
            join_output_path=str(join_output_path),
            boundary_output_path=_norm(join_raw.get("boundary_output_path", "")),
        )
        _progress(
            "join_isolation_failed",
            run_id=run_id,
            sku=sku,
            reason=join_reason or "join_status_invalid",
            join_output_path=str(join_output_path),
        )
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="join_isolation",
            reason=join_reason or "join_status_invalid",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail=join_reason or "join_status_invalid")
        raise RuntimeError(f"join_isolation_failed:{join_reason or 'join_status_invalid'}")
    _progress(
        "join_isolation_valid",
        run_id=run_id,
        sku=sku,
        reason=join_reason or "ok",
        boundary_output_path=_norm(join_raw.get("boundary_output_path", "")),
    )
    boundary_output_path = Path(_norm(join_raw.get("boundary_output_path", "")) or str(boundary_output_path))
    boundary_raw = join_raw.get("boundary_contract", {})
    if not isinstance(boundary_raw, dict):
        _progress(
            "join_isolation_invalid",
            run_id=run_id,
            sku=sku,
            reason="boundary_contract_not_object",
            join_output_path=str(join_output_path),
        )
        _progress(
            "join_isolation_failed",
            run_id=run_id,
            sku=sku,
            reason="boundary_contract_not_object",
            join_output_path=str(join_output_path),
        )
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="join_isolation",
            reason="boundary_contract_not_object",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="boundary_contract_not_object")
        raise RuntimeError("join_isolation_failed:boundary_contract_not_object")
    rc_text = _norm(join_raw.get("helper_rc", ""))
    _progress(
        "continuation_boundary_read_start",
        run_id=run_id,
        sku=sku,
        boundary_output_path=str(boundary_output_path),
    )
    _continuation_boundary_mark(
        active=True,
        run_id=run_id,
        sku=sku,
        stage="boundary_output_read",
        detail="read_start",
    )
    boundary_status = _norm(boundary_raw.get("boundary_status", "")).lower()
    boundary_reason = _norm(boundary_raw.get("reason", ""))
    _progress(
        "helper_wait_boundary_read",
        run_id=run_id,
        sku=sku,
        boundary_status=boundary_status or "missing",
        boundary_reason=boundary_reason,
        rc=rc_text,
        boundary_output_path=str(boundary_output_path),
    )
    _progress(
        "continuation_boundary_read_done",
        run_id=run_id,
        sku=sku,
        boundary_status=boundary_status or "missing",
        boundary_reason=boundary_reason,
        rc=rc_text,
    )
    helper_rc_text = _norm(boundary_raw.get("helper_rc", ""))
    helper_rc_int = _to_int(helper_rc_text)
    rc_nonzero = helper_rc_int is not None and int(helper_rc_int) != 0
    if rc_nonzero or boundary_status != "valid":
        _progress(
            "helper_wait_boundary_invalid",
            run_id=run_id,
            sku=sku,
            reason=boundary_reason or ("wait_boundary_nonzero_rc" if rc_nonzero else "wait_boundary_invalid"),
            rc=rc_text,
            boundary_status=boundary_status or "missing",
            boundary_reason=boundary_reason,
        )
        _progress(
            "helper_wait_boundary_failed",
            run_id=run_id,
            sku=sku,
            reason=boundary_reason or ("wait_boundary_nonzero_rc" if rc_nonzero else "wait_boundary_invalid"),
            rc=rc_text,
        )
        resolved_reason = boundary_reason or ("wait_boundary_nonzero_rc" if rc_nonzero else "wait_boundary_invalid")
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="boundary_output_validate",
            reason=resolved_reason,
            rc=rc_text,
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail=resolved_reason)
        raise RuntimeError(f"continuation_boundary_failed:{resolved_reason}:rc={rc_text or 'missing'}")
    _progress(
        "helper_wait_boundary_valid",
        run_id=run_id,
        sku=sku,
        boundary_reason=boundary_reason,
        rc=rc_text,
    )
    helper_output_path_raw = _norm(boundary_raw.get("helper_output_path", ""))
    if not helper_output_path_raw:
        _progress(
            "helper_wait_boundary_invalid",
            run_id=run_id,
            sku=sku,
            reason="helper_output_path_missing",
        )
        _progress("helper_wait_boundary_failed", run_id=run_id, sku=sku, reason="helper_output_path_missing")
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="boundary_output_validate",
            reason="helper_output_path_missing",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="helper_output_path_missing")
        raise RuntimeError("continuation_boundary_failed:helper_output_path_missing")
    helper_output_path = Path(helper_output_path_raw)
    helper_contract = boundary_raw.get("helper_contract", {})
    if not isinstance(helper_contract, dict):
        _progress(
            "helper_wait_boundary_invalid",
            run_id=run_id,
            sku=sku,
            reason="helper_contract_not_object",
            helper_output_path=str(helper_output_path),
        )
        _progress("helper_wait_boundary_failed", run_id=run_id, sku=sku, reason="helper_contract_not_object")
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="boundary_output_validate",
            reason="helper_contract_not_object",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="helper_contract_not_object")
        raise RuntimeError("continuation_boundary_failed:helper_contract_not_object")
    _progress(
        "continuation_boundary_accept_start",
        run_id=run_id,
        sku=sku,
        helper_output_path=str(helper_output_path),
    )
    _continuation_boundary_mark(
        active=True,
        run_id=run_id,
        sku=sku,
        stage="boundary_acceptance",
        detail="accept_start",
    )
    try:
        acceptance = _invoke_post_helper_acceptance(
            run_id=run_id,
            sku=sku,
            helper_output_path=helper_output_path,
            helper_dir=helper_dir,
        )
    except BaseException as exc:
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="boundary_acceptance",
            reason="acceptance_invoke_failed",
            error=f"{type(exc).__name__}:{exc}",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="acceptance_invoke_failed")
        raise RuntimeError(f"continuation_boundary_failed:acceptance_invoke_failed:{type(exc).__name__}:{exc}") from exc
    contract_raw = acceptance.get("contract", {})
    if not isinstance(contract_raw, dict):
        _progress(
            "post_helper_acceptance_invalid",
            run_id=run_id,
            sku=sku,
            reason="contract_missing_after_acceptance",
        )
        _progress(
            "continuation_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="boundary_acceptance",
            reason="contract_missing_after_acceptance",
        )
        _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="failed", detail="contract_missing_after_acceptance")
        raise RuntimeError("continuation_boundary_failed:contract_missing_after_acceptance")
    _progress(
        "continuation_boundary_accept_done",
        run_id=run_id,
        sku=sku,
        status="ok",
    )
    _continuation_boundary_mark(active=False, run_id=run_id, sku=sku, stage="done", detail="ok")
    return contract_raw


def _run_pre_result_worker_mode(*, input_path: Path, output_path: Path) -> int:
    started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = ""
    sku = ""
    checkpoint_last = "pre_result_worker_enter"
    error_class = ""
    status = "failed"
    reason = ""
    payload: dict[str, object] | None = None
    try:
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req_raw, dict):
            raise RuntimeError("request_not_object")
        req = req_raw
        run_id = _norm(req.get("run_id", ""))
        sku = _norm(req.get("sku", "")).upper()
        helper_contract = _run_sku_pre_result_helper_contract(req)
        if not isinstance(helper_contract, dict):
            raise RuntimeError("helper_contract_not_object")
        helper_status = _norm(helper_contract.get("status", "")).lower()
        helper_reason = _norm(helper_contract.get("reason", ""))
        checkpoint_last = _norm(helper_contract.get("checkpoint_last", "")) or "helper_contract_returned"
        if helper_status in {"ok", "skip"}:
            status = "ok"
            reason = helper_reason or helper_status
            payload = {"helper_contract": helper_contract}
        else:
            status = "failed"
            reason = helper_reason or f"helper_status_{helper_status or 'missing'}"
    except BaseException as exc:
        error_class = type(exc).__name__
        status = "failed"
        reason = _norm(str(exc)) or "pre_result_worker_exception"
        checkpoint_last = checkpoint_last or "pre_result_worker_exception"
    contract = {
        "run_id": run_id,
        "sku": sku,
        "status": status,
        "reason": reason,
        "worker_started_utc": started_utc,
        "worker_finished_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checkpoint_last": checkpoint_last,
        "error_class": error_class,
        "payload": payload if isinstance(payload, dict) else {},
    }
    _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
    return 0 if status == "ok" else 1


def _run_pre_result_ready_reader_mode(*, input_path: Path, output_path: Path) -> int:
    run_id = ""
    sku = ""
    contract_status = "failed"
    reason = "uninitialized"
    worker_contract_path = ""
    checkpoint_last = "pre_result_ready_reader_enter"
    error_class = ""
    worker_contract: dict[str, object] = {}
    try:
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req_raw, dict):
            raise RuntimeError("request_not_object")
        run_id = _norm(req_raw.get("run_id", ""))
        sku = _norm(req_raw.get("sku", "")).upper()
        worker_contract_path = _norm(req_raw.get("worker_contract_path", ""))
        if not run_id:
            raise RuntimeError("missing_run_id")
        if not sku:
            raise RuntimeError("missing_sku")
        if not worker_contract_path:
            raise RuntimeError("missing_worker_contract_path")
        timeout_seconds = max(_to_int(req_raw.get("timeout_seconds")) or 120, 30)
        worker_contract_file = Path(worker_contract_path)
        deadline = time.monotonic() + float(timeout_seconds)
        while not worker_contract_file.exists():
            if time.monotonic() >= deadline:
                reason = f"timeout_waiting_for_worker_contract_after_{timeout_seconds}s"
                checkpoint_last = "wait_worker_contract_timeout"
                payload = {
                    "run_id": run_id,
                    "sku": sku,
                    "contract_status": "failed",
                    "reason": reason,
                    "worker_contract_path": worker_contract_path,
                    "worker_contract": {},
                    "checkpoint_last": checkpoint_last,
                    "error_class": error_class,
                }
                _atomic_write_text(output_path, json.dumps(payload, ensure_ascii=True) + "\n")
                return 1
            time.sleep(0.1)
        checkpoint_last = "worker_contract_found"
        contract_raw = json.loads(worker_contract_file.read_text(encoding="utf-8"))
        if not isinstance(contract_raw, dict):
            raise RuntimeError("worker_contract_not_object")
        checkpoint_last = _norm(contract_raw.get("checkpoint_last", "")) or "worker_contract_loaded"
        contract_run_id = _norm(contract_raw.get("run_id", ""))
        contract_sku = _norm(contract_raw.get("sku", "")).upper()
        if contract_run_id != run_id:
            raise RuntimeError(f"run_id_mismatch:{contract_run_id or 'missing'}")
        if contract_sku != sku:
            raise RuntimeError(f"sku_mismatch:{contract_sku or 'missing'}")
        status = _norm(contract_raw.get("status", "")).lower()
        status_reason = _norm(contract_raw.get("reason", ""))
        payload_raw = contract_raw.get("payload", {})
        if status != "ok":
            reason = status_reason or f"worker_status_{status or 'missing'}"
            checkpoint_last = checkpoint_last or "worker_status_not_ok"
            contract_status = "failed"
        elif not isinstance(payload_raw, dict):
            reason = "payload_not_object"
            checkpoint_last = "worker_payload_not_object"
            contract_status = "failed"
        else:
            helper_contract = payload_raw.get("helper_contract", {})
            if not isinstance(helper_contract, dict):
                reason = "helper_contract_not_object"
                checkpoint_last = "helper_contract_not_object"
                contract_status = "failed"
            else:
                contract_status = "ok"
                reason = status_reason or "ok"
                worker_contract = contract_raw
    except BaseException as exc:
        contract_status = "failed"
        error_class = type(exc).__name__
        reason = _norm(str(exc)) or "pre_result_ready_reader_exception"
        checkpoint_last = checkpoint_last or "pre_result_ready_reader_exception"
    ready_contract = {
        "run_id": run_id,
        "sku": sku,
        "contract_status": contract_status,
        "reason": reason,
        "worker_contract_path": worker_contract_path,
        "worker_contract": worker_contract if isinstance(worker_contract, dict) else {},
        "checkpoint_last": checkpoint_last,
        "error_class": error_class,
    }
    _atomic_write_text(output_path, json.dumps(ready_contract, ensure_ascii=True) + "\n")
    return 0 if contract_status == "ok" else 1


def _invoke_pre_result_worker(
    *,
    run_id: str,
    sku: str,
    cfg: dict[str, object],
    universe_row: dict[str, str],
    listing_row: dict[str, str],
    listing_snapshot_path: str,
    seller_snapshot_path: str,
) -> dict[str, object]:
    worker_dir = H_LIVE_DIR / "tmp_h110_pre_result_worker"
    ready_dir = H_LIVE_DIR / "tmp_h110_pre_result_ready_reader"
    worker_dir.mkdir(parents=True, exist_ok=True)
    ready_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
    worker_input_path = worker_dir / f"in.{token}.json"
    worker_output_path = worker_dir / f"out.{token}.json"
    worker_stdout_path = worker_dir / f"stdout.{token}.log"
    worker_stderr_path = worker_dir / f"stderr.{token}.log"
    ready_input_path = ready_dir / f"in.{token}.json"
    ready_output_path = ready_dir / f"out.{token}.json"
    ready_stdout_path = ready_dir / f"stdout.{token}.log"
    ready_stderr_path = ready_dir / f"stderr.{token}.log"
    req = {
        "run_id": run_id,
        "sku": sku,
        "cfg_marketplace_id": _norm(_cfg_get(cfg, "marketplace_id", default="")),
        "cfg_sku": _norm(_cfg_get(cfg, "sku", default="")),
        "cfg_asin": _norm(_cfg_get(cfg, "asin", default="")),
        "cfg_seller_id": _norm(_cfg_get(cfg, "seller_id", default="")),
        "universe_row": universe_row,
        "listing_row": listing_row,
        "listing_snapshot_path": _norm(listing_snapshot_path),
        "seller_snapshot_path": _norm(seller_snapshot_path),
    }
    _atomic_write_text(worker_input_path, json.dumps(req, ensure_ascii=True) + "\n")
    worker_cmd = _self_python_cmd(
        "--pre-result-worker",
        "--pre-result-input",
        str(worker_input_path),
        "--pre-result-output",
        str(worker_output_path),
    )
    with worker_stdout_path.open("wb") as out_fh, worker_stderr_path.open("wb") as err_fh:
        worker_proc = _popen_hidden(
            worker_cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            close_fds=True,
            env=os.environ.copy(),
        )
        _progress(
            "pre_result_worker_spawned",
            run_id=run_id,
            sku=sku,
            child_pid=str(worker_proc.pid),
            worker_input_path=str(worker_input_path),
            worker_output_path=str(worker_output_path),
            worker_stdout_path=str(worker_stdout_path),
            worker_stderr_path=str(worker_stderr_path),
        )
    ready_req = {
        "run_id": run_id,
        "sku": sku,
        "worker_contract_path": str(worker_output_path),
        "timeout_seconds": str(max(_env_int("H110_PRE_RESULT_WORKER_TIMEOUT_SECONDS", 120), 30)),
    }
    _atomic_write_text(ready_input_path, json.dumps(ready_req, ensure_ascii=True) + "\n")
    ready_cmd = _self_python_cmd(
        "--pre-result-ready-reader",
        "--pre-result-ready-input",
        str(ready_input_path),
        "--pre-result-ready-output",
        str(ready_output_path),
    )
    with ready_stdout_path.open("wb") as out_fh, ready_stderr_path.open("wb") as err_fh:
        ready_proc = _popen_hidden(
            ready_cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            close_fds=True,
            env=os.environ.copy(),
        )
    _progress(
        "pre_result_ready_reader_spawned",
        run_id=run_id,
        sku=sku,
        child_pid=str(ready_proc.pid),
        ready_input_path=str(ready_input_path),
        ready_output_path=str(ready_output_path),
        ready_stdout_path=str(ready_stdout_path),
        ready_stderr_path=str(ready_stderr_path),
        worker_contract_path=str(worker_output_path),
    )
    ready_timeout = max(_env_int("H110_PRE_RESULT_READY_READER_TIMEOUT_SECONDS", 150), 45)
    try:
        ready_proc.wait(timeout=float(ready_timeout))
    except Exception:
        with contextlib.suppress(Exception):
            ready_proc.terminate()
        with contextlib.suppress(Exception):
            ready_proc.wait(timeout=3.0)
        if ready_proc.poll() is None:
            with contextlib.suppress(Exception):
                ready_proc.kill()
            with contextlib.suppress(Exception):
                ready_proc.wait(timeout=3.0)
        _progress("pre_result_ready_reader_invalid", run_id=run_id, sku=sku, reason="timeout_waiting_for_ready_reader")
        raise RuntimeError(f"pre_result_ready_contract_invalid:ready_reader_timeout_after_{ready_timeout}s")
    if not ready_output_path.exists():
        _progress("pre_result_ready_reader_invalid", run_id=run_id, sku=sku, reason="missing_ready_output")
        raise RuntimeError("pre_result_ready_contract_invalid:missing_ready_output")
    _progress(
        "pre_result_ready_reader_read",
        run_id=run_id,
        sku=sku,
        ready_output_path=str(ready_output_path),
    )
    try:
        ready_contract_raw = json.loads(ready_output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _progress(
            "pre_result_ready_reader_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"invalid_json:{type(exc).__name__}:{exc}",
        )
        raise RuntimeError(f"pre_result_ready_contract_invalid:invalid_json:{type(exc).__name__}:{exc}") from exc
    if not isinstance(ready_contract_raw, dict):
        _progress("pre_result_ready_reader_invalid", run_id=run_id, sku=sku, reason="contract_not_object")
        raise RuntimeError("pre_result_ready_contract_invalid:contract_not_object")
    contract_run_id = _norm(ready_contract_raw.get("run_id", ""))
    contract_sku = _norm(ready_contract_raw.get("sku", "")).upper()
    if contract_run_id != run_id:
        _progress(
            "pre_result_ready_reader_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"run_id_mismatch:{contract_run_id or 'missing'}",
        )
        raise RuntimeError(f"pre_result_ready_contract_invalid:run_id_mismatch:{contract_run_id or 'missing'}")
    if contract_sku != sku:
        _progress(
            "pre_result_ready_reader_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"sku_mismatch:{contract_sku or 'missing'}",
        )
        raise RuntimeError(f"pre_result_ready_contract_invalid:sku_mismatch:{contract_sku or 'missing'}")
    contract_status = _norm(ready_contract_raw.get("contract_status", "")).lower()
    contract_reason = _norm(ready_contract_raw.get("reason", ""))
    worker_contract_raw = ready_contract_raw.get("worker_contract", {})
    if contract_status != "ok":
        _progress(
            "pre_result_ready_reader_failed",
            run_id=run_id,
            sku=sku,
            reason=contract_reason or f"status_{contract_status or 'missing'}",
        )
        raise RuntimeError(f"pre_result_ready_contract_failed:{contract_reason or (contract_status or 'missing')}")
    if not isinstance(worker_contract_raw, dict):
        _progress("pre_result_ready_reader_invalid", run_id=run_id, sku=sku, reason="worker_contract_not_object")
        raise RuntimeError("pre_result_ready_contract_invalid:worker_contract_not_object")
    worker_payload_raw = worker_contract_raw.get("payload", {})
    if not isinstance(worker_payload_raw, dict):
        _progress("pre_result_ready_reader_invalid", run_id=run_id, sku=sku, reason="worker_payload_not_object")
        raise RuntimeError("pre_result_ready_contract_invalid:worker_payload_not_object")
    helper_contract = worker_payload_raw.get("helper_contract", {})
    if not isinstance(helper_contract, dict):
        _progress("pre_result_ready_reader_invalid", run_id=run_id, sku=sku, reason="helper_contract_not_object")
        raise RuntimeError("pre_result_ready_contract_invalid:helper_contract_not_object")
    _progress(
        "pre_result_ready_reader_valid",
        run_id=run_id,
        sku=sku,
        checkpoint_last=_norm(ready_contract_raw.get("checkpoint_last", "")),
        error_class=_norm(ready_contract_raw.get("error_class", "")),
    )
    _progress(
        "full_worker_after_ready_reader",
        run_id=run_id,
        sku=sku,
        reason=_norm(contract_reason) or "ok",
    )
    return helper_contract


def _run_helper_wait_boundary_mode(
    *,
    input_path: Path,
    output_path: Path,
    run_id: str,
    sku: str,
) -> int:
    boundary: dict[str, object] = {
        "run_id": run_id,
        "sku": sku,
        "boundary_status": "invalid",
        "reason": "uninitialized",
    }
    try:
        req = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req, dict):
            raise RuntimeError("wait_boundary_input_not_object")
    except Exception as exc:
        boundary["reason"] = f"input_read_error:{type(exc).__name__}:{exc}"
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1

    helper_dir = H_LIVE_DIR / "tmp_h110_sku_helper"
    helper_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
    helper_input_path = helper_dir / f"in.{token}.json"
    helper_output_path = helper_dir / f"out.{token}.json"
    helper_stdout_path = helper_dir / f"stdout.{token}.log"
    helper_stderr_path = helper_dir / f"stderr.{token}.log"
    _atomic_write_text(helper_input_path, json.dumps(req, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--sku-pre-result-helper",
        "--sku-helper-input",
        str(helper_input_path),
        "--sku-helper-output",
        str(helper_output_path),
    )
    with helper_stdout_path.open("wb") as out_fh, helper_stderr_path.open("wb") as err_fh:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            close_fds=True,
            env=os.environ.copy(),
        )
        _progress(
            "sku_helper_spawned",
            run_id=run_id,
            sku=sku,
            child_pid=str(proc.pid),
            input_path=str(helper_input_path),
            output_path=str(helper_output_path),
            stdout_path=str(helper_stdout_path),
            stderr_path=str(helper_stderr_path),
        )
        timeout_seconds = max(_env_int("H110_SKU_HELPER_TIMEOUT_SECONDS", 45), 10)
        try:
            rc = int(proc.wait(timeout=float(timeout_seconds)))
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            boundary.update(
                {
                    "boundary_status": "invalid",
                    "reason": f"helper_timeout_after_{timeout_seconds}s",
                    "helper_rc": "",
                    "helper_output_path": str(helper_output_path),
                    "helper_stdout_path": str(helper_stdout_path),
                    "helper_stderr_path": str(helper_stderr_path),
                }
            )
            _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
            return 1

    boundary.update(
        {
            "helper_rc": str(rc),
            "helper_output_path": str(helper_output_path),
            "helper_stdout_path": str(helper_stdout_path),
            "helper_stderr_path": str(helper_stderr_path),
        }
    )
    if not helper_output_path.exists():
        boundary.update(
            {
                "boundary_status": "invalid",
                "reason": "missing_helper_output_json",
            }
        )
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1
    try:
        helper_contract = json.loads(helper_output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        boundary.update(
            {
                "boundary_status": "invalid",
                "reason": f"helper_output_invalid_json:{type(exc).__name__}:{exc}",
            }
        )
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1
    if not isinstance(helper_contract, dict):
        boundary.update(
            {
                "boundary_status": "invalid",
                "reason": "helper_output_not_object",
            }
        )
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1
    helper_status = _norm(helper_contract.get("status", "")).lower()
    helper_reason = _norm(helper_contract.get("reason", ""))
    if rc != 0:
        boundary.update(
            {
                "boundary_status": "invalid",
                "reason": helper_reason or "helper_nonzero_rc",
                "helper_contract": helper_contract,
            }
        )
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1
    if helper_status not in {"ok", "skip"}:
        boundary.update(
            {
                "boundary_status": "invalid",
                "reason": helper_reason or f"helper_status_invalid:{helper_status or 'missing'}",
                "helper_contract": helper_contract,
            }
        )
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1
    boundary.update(
        {
            "boundary_status": "valid",
            "reason": helper_reason or "ok",
            "helper_status": helper_status,
            "helper_contract": helper_contract,
        }
    )
    _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
    return 0


def _run_join_isolation_mode(
    *,
    input_path: Path,
    output_path: Path,
    run_id: str,
    sku: str,
) -> int:
    result: dict[str, object] = {
        "run_id": run_id,
        "sku": sku,
        "join_status": "invalid",
        "reason": "uninitialized",
    }
    try:
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req_raw, dict):
            raise RuntimeError("join_input_not_object")
    except Exception as exc:
        result["reason"] = f"join_input_read_error:{type(exc).__name__}:{exc}"
        _atomic_write_text(output_path, json.dumps(result, ensure_ascii=True) + "\n")
        return 1

    boundary_output_path = Path(_norm(req_raw.get("boundary_output_path", "")))
    timeout_seconds = _to_int(req_raw.get("timeout_seconds"))
    if timeout_seconds is None:
        timeout_seconds = 90
    timeout_seconds = max(int(timeout_seconds), 15)

    if not _norm(str(boundary_output_path)):
        result["reason"] = "boundary_output_path_missing"
        _atomic_write_text(output_path, json.dumps(result, ensure_ascii=True) + "\n")
        return 1

    deadline = time.monotonic() + float(timeout_seconds)
    while time.monotonic() < deadline:
        if boundary_output_path.exists():
            break
        time.sleep(0.1)
    if not boundary_output_path.exists():
        result["reason"] = f"parent_join_timeout_after_{timeout_seconds}s"
        result["boundary_output_path"] = str(boundary_output_path)
        _atomic_write_text(output_path, json.dumps(result, ensure_ascii=True) + "\n")
        return 1

    boundary_size = 0
    with contextlib.suppress(Exception):
        boundary_size = int(boundary_output_path.stat().st_size)
    try:
        boundary_raw = json.loads(boundary_output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["reason"] = f"boundary_output_invalid_json:{type(exc).__name__}:{exc}"
        result["boundary_output_path"] = str(boundary_output_path)
        result["boundary_output_size"] = str(boundary_size)
        _atomic_write_text(output_path, json.dumps(result, ensure_ascii=True) + "\n")
        return 1
    if not isinstance(boundary_raw, dict):
        result["reason"] = "boundary_output_not_object"
        result["boundary_output_path"] = str(boundary_output_path)
        result["boundary_output_size"] = str(boundary_size)
        _atomic_write_text(output_path, json.dumps(result, ensure_ascii=True) + "\n")
        return 1

    boundary_status = _norm(boundary_raw.get("boundary_status", "")).lower()
    boundary_reason = _norm(boundary_raw.get("reason", ""))
    helper_output_path = _norm(boundary_raw.get("helper_output_path", ""))
    helper_contract_raw = boundary_raw.get("helper_contract", {})
    if not isinstance(helper_contract_raw, dict):
        result["reason"] = "helper_contract_not_object"
        result["boundary_output_path"] = str(boundary_output_path)
        result["boundary_status"] = boundary_status
        result["boundary_reason"] = boundary_reason
        _atomic_write_text(output_path, json.dumps(result, ensure_ascii=True) + "\n")
        return 1
    result = {
        "run_id": run_id,
        "sku": sku,
        "join_status": "valid",
        "reason": boundary_reason or "ok",
        "boundary_output_path": str(boundary_output_path),
        "boundary_output_size": str(boundary_size),
        "boundary_status": boundary_status,
        "helper_rc": _norm(boundary_raw.get("helper_rc", "")),
        "helper_output_path": helper_output_path,
        "helper_contract": helper_contract_raw,
        "boundary_contract": boundary_raw,
    }
    _atomic_write_text(output_path, json.dumps(result, ensure_ascii=True) + "\n")
    return 0


def _run_first_sku_worker_mode(*, input_path: Path, output_path: Path) -> int:
    started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract: dict[str, object] = {
        "run_id": "",
        "sku": "",
        "status": "failed",
        "reason": "uninitialized",
        "worker_started_utc": started_utc,
        "worker_finished_utc": started_utc,
        "payload": {},
        "checkpoint_last": "",
        "error_class": "",
    }
    try:
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req_raw, dict):
            raise RuntimeError("worker_input_not_object")
    except Exception as exc:
        contract["reason"] = f"worker_input_read_error:{type(exc).__name__}:{exc}"
        contract["error_class"] = type(exc).__name__
        contract["checkpoint_last"] = _LAST_COMPLETION_CHECKPOINT
        contract["worker_finished_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 1

    run_id = _norm(req_raw.get("run_id", ""))
    sku = _norm(req_raw.get("sku", "")).upper()
    contract["run_id"] = run_id
    contract["sku"] = sku

    try:
        now_utc_raw = _norm(req_raw.get("now_utc", ""))
        if not now_utc_raw:
            now_utc = datetime.now(timezone.utc)
        else:
            parsed = datetime.fromisoformat(now_utc_raw.replace("Z", "+00:00"))
            now_utc = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        cfg_raw = req_raw.get("cfg", {})
        cfg = cfg_raw if isinstance(cfg_raw, dict) else {}
        universe_row_raw = req_raw.get("universe_row", {})
        universe_row = universe_row_raw if isinstance(universe_row_raw, dict) else {}
        listing_row_raw = req_raw.get("listing_row", {})
        listing_row = listing_row_raw if isinstance(listing_row_raw, dict) else {}
        listing_map = {sku: listing_row} if sku else {}
        row = _run_one_sku(
            cfg=cfg,
            sku=sku,
            read_only=_to_bool(req_raw.get("read_only", False), default=False),
            run_id=run_id,
            now_utc=now_utc,
            manual_cap_by_sku=req_raw.get("manual_cap_by_sku", {}) if isinstance(req_raw.get("manual_cap_by_sku", {}), dict) else {},
            manual_cap_by_asin=req_raw.get("manual_cap_by_asin", {}) if isinstance(req_raw.get("manual_cap_by_asin", {}), dict) else {},
            temp_floor_by_sku=req_raw.get("temp_floor_by_sku", {}) if isinstance(req_raw.get("temp_floor_by_sku", {}), dict) else {},
            temp_floor_blockers_by_sku=req_raw.get("temp_floor_blockers_by_sku", {}) if isinstance(req_raw.get("temp_floor_blockers_by_sku", {}), dict) else {},
            daily_boundary_lock_by_sku=req_raw.get("daily_boundary_lock_by_sku", {}) if isinstance(req_raw.get("daily_boundary_lock_by_sku", {}), dict) else {},
            boundary_lock_date_utc=_norm(req_raw.get("boundary_lock_date_utc", "")),
            universe_row=universe_row,
            listing_map=listing_map,
            listing_snapshot_path=_norm(req_raw.get("listing_snapshot_path", "")),
            seller_snapshot_path=_norm(req_raw.get("seller_snapshot_path", "")),
            reentry_price_discovery_active=_to_bool(req_raw.get("reentry_price_discovery_active", False), default=False),
            reentry_event=_to_bool(req_raw.get("reentry_event", False), default=False),
            inbound_price_discovery_active=_to_bool(req_raw.get("inbound_price_discovery_active", False), default=False),
        )
        contract["status"] = "ok"
        contract["reason"] = "ok"
        contract["payload"] = row if isinstance(row, dict) else {}
        contract["checkpoint_last"] = _LAST_COMPLETION_CHECKPOINT
        contract["error_class"] = ""
        contract["worker_finished_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 0
    except BaseException as exc:
        contract["status"] = "failed"
        contract["reason"] = f"worker_run_failed:{type(exc).__name__}:{_norm(str(exc))[:220]}"
        contract["payload"] = {}
        contract["checkpoint_last"] = _LAST_COMPLETION_CHECKPOINT
        contract["error_class"] = type(exc).__name__
        contract["worker_finished_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 1


def _run_first_sku_exec_worker_mode(*, input_path: Path, output_path: Path) -> int:
    return _run_first_sku_worker_mode(input_path=input_path, output_path=output_path)


def _run_first_sku_exec_worker(
    *,
    cfg: dict,
    sku: str,
    read_only: bool,
    run_id: str,
    now_utc: datetime,
    manual_cap_by_sku: dict[str, str],
    manual_cap_by_asin: dict[str, str],
    temp_floor_by_sku: dict[str, str],
    temp_floor_blockers_by_sku: dict[str, str],
    daily_boundary_lock_by_sku: dict[str, dict[str, str]],
    boundary_lock_date_utc: str,
    universe_row: dict[str, str],
    listing_row: dict[str, str],
    listing_snapshot_path: str,
    seller_snapshot_path: str,
    reentry_price_discovery_active: bool = False,
    reentry_event: bool = False,
    inbound_price_discovery_active: bool = False,
) -> dict[str, str]:
    worker_dir = H_LIVE_DIR / "tmp_h110_first_sku_exec_worker"
    worker_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{os.getpid()}.{time.time_ns()}"
    worker_input_path = worker_dir / f"in.{token}.json"
    worker_output_path = worker_dir / f"out.{token}.json"
    worker_stdout_path = worker_dir / f"stdout.{token}.log"
    worker_stderr_path = worker_dir / f"stderr.{token}.log"
    req: dict[str, object] = {
        "run_id": run_id,
        "sku": sku,
        "read_only": "1" if read_only else "0",
        "now_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cfg": cfg,
        "manual_cap_by_sku": manual_cap_by_sku,
        "manual_cap_by_asin": manual_cap_by_asin,
        "temp_floor_by_sku": temp_floor_by_sku,
        "temp_floor_blockers_by_sku": temp_floor_blockers_by_sku,
        "daily_boundary_lock_by_sku": daily_boundary_lock_by_sku,
        "boundary_lock_date_utc": boundary_lock_date_utc,
        "universe_row": universe_row,
        "listing_row": listing_row,
        "listing_snapshot_path": listing_snapshot_path,
        "seller_snapshot_path": seller_snapshot_path,
        "reentry_price_discovery_active": "1" if reentry_price_discovery_active else "0",
        "reentry_event": "1" if reentry_event else "0",
        "inbound_price_discovery_active": "1" if inbound_price_discovery_active else "0",
    }
    _atomic_write_text(worker_input_path, json.dumps(req, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--first-sku-exec-worker",
        "--exec-worker-input",
        str(worker_input_path),
        "--exec-worker-output",
        str(worker_output_path),
    )
    timeout_seconds = max(_env_int("H110_FIRST_SKU_EXEC_WORKER_TIMEOUT_SECONDS", 300), 30)
    with open(worker_stdout_path, "w", encoding="utf-8", newline="") as out_fh, open(
        worker_stderr_path, "w", encoding="utf-8", newline=""
    ) as err_fh:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdout=out_fh,
            stderr=err_fh,
            text=True,
        )
        _progress(
            "first_sku_exec_worker_spawned",
            run_id=run_id,
            sku=sku,
            child_pid=proc.pid,
            worker_input_path=str(worker_input_path),
            worker_output_path=str(worker_output_path),
            stdout_path=str(worker_stdout_path),
            stderr_path=str(worker_stderr_path),
            timeout_seconds=timeout_seconds,
        )
        try:
            worker_rc = int(proc.wait(timeout=float(timeout_seconds)))
        except Exception:
            with contextlib.suppress(Exception):
                proc.kill()
            _progress("first_sku_exec_worker_contract_invalid", run_id=run_id, sku=sku, reason="timeout_waiting_for_contract")
            raise RuntimeError(f"worker_contract_invalid:timeout_after_{timeout_seconds}s")
    if not worker_output_path.exists():
        _progress("first_sku_exec_worker_contract_invalid", run_id=run_id, sku=sku, reason="missing_worker_contract_output")
        raise RuntimeError("worker_contract_invalid:missing_contract_output")
    _progress(
        "first_sku_exec_worker_contract_read",
        run_id=run_id,
        sku=sku,
        worker_rc=worker_rc,
        worker_output_path=str(worker_output_path),
    )
    try:
        contract_raw = json.loads(worker_output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _progress(
            "first_sku_exec_worker_contract_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"contract_json_error:{type(exc).__name__}:{exc}",
        )
        raise RuntimeError(f"worker_contract_invalid:contract_json_error:{type(exc).__name__}:{exc}") from exc
    if not isinstance(contract_raw, dict):
        _progress("first_sku_exec_worker_contract_invalid", run_id=run_id, sku=sku, reason="contract_not_object")
        raise RuntimeError("worker_contract_invalid:contract_not_object")
    contract_run_id = _norm(contract_raw.get("run_id", ""))
    contract_sku = _norm(contract_raw.get("sku", "")).upper()
    if contract_run_id != run_id:
        _progress(
            "first_sku_exec_worker_contract_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"run_id_mismatch:{contract_run_id}",
        )
        raise RuntimeError(f"worker_contract_invalid:run_id_mismatch:{contract_run_id or 'missing'}")
    if contract_sku != sku:
        _progress(
            "first_sku_exec_worker_contract_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"sku_mismatch:{contract_sku}",
        )
        raise RuntimeError(f"worker_contract_invalid:sku_mismatch:{contract_sku or 'missing'}")
    status = _norm(contract_raw.get("status", "")).lower()
    reason = _norm(contract_raw.get("reason", ""))
    payload_raw = contract_raw.get("payload", {})
    if status != "ok":
        _progress(
            "first_sku_exec_worker_contract_failed",
            run_id=run_id,
            sku=sku,
            reason=reason or "status_not_ok",
            worker_status=status or "missing",
            worker_rc=worker_rc,
        )
        raise RuntimeError(f"worker_contract_failed:{reason or (status or 'status_not_ok')}")
    if not isinstance(payload_raw, dict):
        _progress("first_sku_exec_worker_contract_invalid", run_id=run_id, sku=sku, reason="payload_not_object")
        raise RuntimeError("worker_contract_invalid:payload_not_object")
    _progress(
        "first_sku_exec_worker_contract_valid",
        run_id=run_id,
        sku=sku,
        worker_status=status,
        worker_reason=reason or "ok",
        worker_rc=worker_rc,
    )
    return {str(k): _norm(v) for k, v in payload_raw.items()}


def _run_first_sku_worker_boundary_mode(
    *,
    input_path: Path,
    output_path: Path,
    run_id: str,
    sku: str,
) -> int:
    boundary: dict[str, object] = {
        "run_id": run_id,
        "sku": sku,
        "contract_status": "failed",
        "reason": "uninitialized",
        "worker_output_path": "",
        "worker_rc": "",
        "worker_contract": {},
    }
    try:
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req_raw, dict):
            raise RuntimeError("worker_boundary_input_not_object")
    except Exception as exc:
        boundary["reason"] = f"worker_boundary_input_read_error:{type(exc).__name__}:{exc}"
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1

    worker_input_path = Path(_norm(req_raw.get("worker_input_path", "")))
    worker_output_path = Path(_norm(req_raw.get("worker_output_path", "")))
    worker_stdout_path = Path(_norm(req_raw.get("worker_stdout_path", "")))
    worker_stderr_path = Path(_norm(req_raw.get("worker_stderr_path", "")))
    worker_timeout = _to_int(req_raw.get("worker_timeout_seconds"))
    if worker_timeout is None:
        worker_timeout = 300
    worker_timeout = max(int(worker_timeout), 30)
    worker_request_raw = req_raw.get("worker_request", {})
    worker_request = worker_request_raw if isinstance(worker_request_raw, dict) else {}

    if not _norm(str(worker_input_path)) or not _norm(str(worker_output_path)):
        boundary["reason"] = "worker_boundary_missing_worker_paths"
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1
    if not isinstance(worker_request, dict) or not worker_request:
        boundary["reason"] = "worker_boundary_missing_worker_request"
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1

    with contextlib.suppress(Exception):
        worker_input_path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception):
        worker_stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception):
        worker_stderr_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(worker_input_path, json.dumps(worker_request, ensure_ascii=True) + "\n")

    cmd = _self_python_cmd(
        "--first-sku-worker",
        "--worker-input",
        str(worker_input_path),
        "--worker-output",
        str(worker_output_path),
    )

    rc = ""
    with open(worker_stdout_path, "w", encoding="utf-8", newline="") as out_fh, open(
        worker_stderr_path, "w", encoding="utf-8", newline=""
    ) as err_fh:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdout=out_fh,
            stderr=err_fh,
            text=True,
        )
        try:
            rc = str(int(proc.wait(timeout=float(worker_timeout))))
        except Exception:
            with contextlib.suppress(Exception):
                proc.kill()
            boundary.update(
                {
                    "contract_status": "failed",
                    "reason": f"worker_timeout_after_{worker_timeout}s",
                    "worker_output_path": str(worker_output_path),
                    "worker_rc": "",
                }
            )
            _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
            return 1

    boundary["worker_output_path"] = str(worker_output_path)
    boundary["worker_rc"] = rc
    if not worker_output_path.exists():
        boundary["contract_status"] = "failed"
        boundary["reason"] = "missing_worker_contract_output"
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1

    try:
        worker_contract_raw = json.loads(worker_output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        boundary["contract_status"] = "failed"
        boundary["reason"] = f"worker_contract_json_error:{type(exc).__name__}:{exc}"
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1
    if not isinstance(worker_contract_raw, dict):
        boundary["contract_status"] = "failed"
        boundary["reason"] = "worker_contract_not_object"
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1

    contract_run_id = _norm(worker_contract_raw.get("run_id", ""))
    contract_sku = _norm(worker_contract_raw.get("sku", "")).upper()
    if contract_run_id != run_id:
        boundary["contract_status"] = "failed"
        boundary["reason"] = f"worker_contract_run_id_mismatch:{contract_run_id or 'missing'}"
        boundary["worker_contract"] = worker_contract_raw
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1
    if contract_sku != sku:
        boundary["contract_status"] = "failed"
        boundary["reason"] = f"worker_contract_sku_mismatch:{contract_sku or 'missing'}"
        boundary["worker_contract"] = worker_contract_raw
        _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
        return 1

    boundary["contract_status"] = "ok"
    boundary["reason"] = "ok"
    boundary["worker_contract"] = worker_contract_raw
    _atomic_write_text(output_path, json.dumps(boundary, ensure_ascii=True) + "\n")
    return 0


def _run_first_sku_worker_boundary(
    *,
    cfg: dict,
    sku: str,
    read_only: bool,
    run_id: str,
    now_utc: datetime,
    manual_cap_by_sku: dict[str, str],
    manual_cap_by_asin: dict[str, str],
    temp_floor_by_sku: dict[str, str],
    temp_floor_blockers_by_sku: dict[str, str],
    daily_boundary_lock_by_sku: dict[str, dict[str, str]],
    boundary_lock_date_utc: str,
    universe_row: dict[str, str],
    listing_row: dict[str, str],
    listing_snapshot_path: str,
    seller_snapshot_path: str,
    reentry_price_discovery_active: bool = False,
    reentry_event: bool = False,
    inbound_price_discovery_active: bool = False,
) -> dict[str, str]:
    worker_dir = H_LIVE_DIR / "tmp_h110_first_sku_worker"
    worker_dir.mkdir(parents=True, exist_ok=True)
    boundary_dir = H_LIVE_DIR / "tmp_h110_first_sku_worker_boundary"
    boundary_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{os.getpid()}.{time.time_ns()}"
    worker_input_path = worker_dir / f"in.{token}.json"
    worker_output_path = worker_dir / f"out.{token}.json"
    worker_stdout_path = worker_dir / f"stdout.{token}.log"
    worker_stderr_path = worker_dir / f"stderr.{token}.log"
    boundary_input_path = boundary_dir / f"in.{token}.json"
    boundary_output_path = boundary_dir / f"out.{token}.json"
    boundary_stdout_path = boundary_dir / f"stdout.{token}.log"
    boundary_stderr_path = boundary_dir / f"stderr.{token}.log"

    worker_req: dict[str, object] = {
        "run_id": run_id,
        "sku": sku,
        "read_only": "1" if read_only else "0",
        "now_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cfg": cfg,
        "manual_cap_by_sku": manual_cap_by_sku,
        "manual_cap_by_asin": manual_cap_by_asin,
        "temp_floor_by_sku": temp_floor_by_sku,
        "temp_floor_blockers_by_sku": temp_floor_blockers_by_sku,
        "daily_boundary_lock_by_sku": daily_boundary_lock_by_sku,
        "boundary_lock_date_utc": boundary_lock_date_utc,
        "universe_row": universe_row,
        "listing_row": listing_row,
        "listing_snapshot_path": listing_snapshot_path,
        "seller_snapshot_path": seller_snapshot_path,
        "reentry_price_discovery_active": "1" if reentry_price_discovery_active else "0",
        "reentry_event": "1" if reentry_event else "0",
        "inbound_price_discovery_active": "1" if inbound_price_discovery_active else "0",
    }
    worker_timeout_seconds = max(_env_int("H110_FIRST_SKU_WORKER_TIMEOUT_SECONDS", 300), 30)
    boundary_timeout_seconds = max(_env_int("H110_FIRST_SKU_WORKER_BOUNDARY_TIMEOUT_SECONDS", worker_timeout_seconds + 45), 60)
    boundary_req: dict[str, object] = {
        "worker_input_path": str(worker_input_path),
        "worker_output_path": str(worker_output_path),
        "worker_stdout_path": str(worker_stdout_path),
        "worker_stderr_path": str(worker_stderr_path),
        "worker_timeout_seconds": worker_timeout_seconds,
        "worker_request": worker_req,
    }
    _atomic_write_text(boundary_input_path, json.dumps(boundary_req, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--first-sku-worker-boundary",
        "--first-worker-boundary-input",
        str(boundary_input_path),
        "--first-worker-boundary-output",
        str(boundary_output_path),
        "--first-worker-boundary-run-id",
        run_id,
        "--first-worker-boundary-sku",
        sku,
    )
    with open(boundary_stdout_path, "w", encoding="utf-8", newline="") as out_fh, open(
        boundary_stderr_path, "w", encoding="utf-8", newline=""
    ) as err_fh:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdout=out_fh,
            stderr=err_fh,
            text=True,
        )
        _progress(
            "first_sku_worker_boundary_spawned",
            run_id=run_id,
            sku=sku,
            child_pid=proc.pid,
            boundary_input_path=str(boundary_input_path),
            boundary_output_path=str(boundary_output_path),
            boundary_stdout_path=str(boundary_stdout_path),
            boundary_stderr_path=str(boundary_stderr_path),
            worker_input_path=str(worker_input_path),
            worker_output_path=str(worker_output_path),
            worker_timeout_seconds=worker_timeout_seconds,
            boundary_timeout_seconds=boundary_timeout_seconds,
        )
        try:
            boundary_rc = int(proc.wait(timeout=float(boundary_timeout_seconds)))
        except Exception:
            with contextlib.suppress(Exception):
                proc.kill()
            _progress(
                "first_sku_worker_boundary_invalid",
                run_id=run_id,
                sku=sku,
                reason="timeout_waiting_for_boundary_output",
            )
            raise RuntimeError(f"worker_boundary_invalid:timeout_after_{boundary_timeout_seconds}s")
    if not boundary_output_path.exists():
        _progress("first_sku_worker_boundary_invalid", run_id=run_id, sku=sku, reason="missing_boundary_output")
        raise RuntimeError("worker_boundary_invalid:missing_boundary_output")
    _progress(
        "first_sku_worker_boundary_read",
        run_id=run_id,
        sku=sku,
        boundary_rc=boundary_rc,
        boundary_output_path=str(boundary_output_path),
    )
    try:
        boundary_raw = json.loads(boundary_output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _progress(
            "first_sku_worker_boundary_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"boundary_json_error:{type(exc).__name__}:{exc}",
        )
        raise RuntimeError(f"worker_boundary_invalid:boundary_json_error:{type(exc).__name__}:{exc}") from exc
    if not isinstance(boundary_raw, dict):
        _progress("first_sku_worker_boundary_invalid", run_id=run_id, sku=sku, reason="boundary_not_object")
        raise RuntimeError("worker_boundary_invalid:boundary_not_object")
    boundary_run_id = _norm(boundary_raw.get("run_id", ""))
    boundary_sku = _norm(boundary_raw.get("sku", "")).upper()
    if boundary_run_id != run_id:
        _progress(
            "first_sku_worker_boundary_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"run_id_mismatch:{boundary_run_id}",
        )
        raise RuntimeError(f"worker_boundary_invalid:run_id_mismatch:{boundary_run_id or 'missing'}")
    if boundary_sku != sku:
        _progress(
            "first_sku_worker_boundary_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"sku_mismatch:{boundary_sku}",
        )
        raise RuntimeError(f"worker_boundary_invalid:sku_mismatch:{boundary_sku or 'missing'}")
    contract_status = _norm(boundary_raw.get("contract_status", "")).lower()
    boundary_reason = _norm(boundary_raw.get("reason", ""))
    worker_rc_text = _norm(boundary_raw.get("worker_rc", ""))
    worker_contract_raw = boundary_raw.get("worker_contract", {})
    if contract_status != "ok":
        _progress(
            "first_sku_worker_boundary_failed",
            run_id=run_id,
            sku=sku,
            reason=boundary_reason or "contract_status_not_ok",
            contract_status=contract_status or "missing",
            worker_rc=worker_rc_text,
        )
        raise RuntimeError(
            f"worker_boundary_failed:{boundary_reason or (contract_status or 'contract_status_not_ok')}"
        )
    if not isinstance(worker_contract_raw, dict):
        _progress(
            "first_sku_worker_boundary_invalid",
            run_id=run_id,
            sku=sku,
            reason="worker_contract_not_object",
        )
        raise RuntimeError("worker_boundary_invalid:worker_contract_not_object")
    _progress(
        "first_sku_worker_boundary_valid",
        run_id=run_id,
        sku=sku,
        worker_rc=worker_rc_text or "missing",
        contract_status=contract_status,
        reason=boundary_reason or "ok",
    )

    status = _norm(worker_contract_raw.get("status", "")).lower()
    reason = _norm(worker_contract_raw.get("reason", ""))
    payload_raw = worker_contract_raw.get("payload", {})
    if status != "ok":
        _progress(
            "first_sku_worker_contract_failed",
            run_id=run_id,
            sku=sku,
            reason=reason or "status_not_ok",
            worker_status=status or "missing",
            worker_rc=worker_rc_text or "missing",
        )
        raise RuntimeError(f"worker_contract_failed:{reason or (status or 'status_not_ok')}")
    if not isinstance(payload_raw, dict):
        _progress("first_sku_worker_contract_invalid", run_id=run_id, sku=sku, reason="payload_not_object")
        raise RuntimeError("worker_contract_invalid:payload_not_object")
    _progress(
        "first_sku_worker_contract_valid",
        run_id=run_id,
        sku=sku,
        worker_status=status,
        worker_reason=reason or "ok",
        worker_rc=worker_rc_text or "missing",
    )
    return {str(k): _norm(v) for k, v in payload_raw.items()}


def _run_sku_pre_result_helper_contract(req: dict[str, object]) -> dict[str, object]:
    run_id = _norm(req.get("run_id", ""))
    sku = _norm(req.get("sku", "")).upper()
    cfg_marketplace_id = _norm(req.get("cfg_marketplace_id", ""))
    cfg_sku = _norm(req.get("cfg_sku", "")).upper()
    cfg_asin = _norm(req.get("cfg_asin", ""))
    cfg_seller_id = _norm(req.get("cfg_seller_id", ""))
    universe_row_raw = req.get("universe_row", {})
    listing_row_raw = req.get("listing_row", {})
    universe_row = universe_row_raw if isinstance(universe_row_raw, dict) else {}
    listing_row = listing_row_raw if isinstance(listing_row_raw, dict) else {}
    listing_snapshot_path = _norm(req.get("listing_snapshot_path", ""))
    seller_snapshot_path = _norm(req.get("seller_snapshot_path", ""))

    if not sku:
        return {
            "status": "failed",
            "run_id": run_id,
            "sku": sku,
            "reason": "empty_sku",
        }
    market_data_present = "1" if listing_row else "0"
    write_effective = _as_bool_text(universe_row.get("write_effective", ""), "0") == "1"
    repricing_enabled = _as_bool_text(universe_row.get("repricing_enabled", ""), "0") == "1"
    asin = _norm(universe_row.get("asin", "")) or _norm(listing_row.get("asin", ""))
    if cfg_asin and cfg_sku == sku:
        asin = cfg_asin
    marketplace_id = _resolve_marketplace_id(listing_row, cfg_marketplace_id)
    seller_id = cfg_seller_id or _seller_id_from_env()
    if not seller_id:
        return {
            "status": "failed",
            "run_id": run_id,
            "sku": sku,
            "reason": "missing_seller_id",
        }

    writer_mode = "CODEX_H" if write_effective else "READ_ONLY"
    cohort_file = str(os.environ.get("H_PHASE_ENGINE_COHORT_FILE", "config/phase_engine_cohort.csv") or "").strip() or "config/phase_engine_cohort.csv"
    exclude_file = str(os.environ.get("H_PHASE_ENGINE_EXCLUDE_FILE", "config/phase_engine_exclusions.csv") or "").strip() or "config/phase_engine_exclusions.csv"
    in_cohort = phase1_phase_engine.sku_in_csv(cohort_file, sku)
    excluded = phase1_phase_engine.sku_in_csv(exclude_file, sku)
    if in_cohort and not excluded:
        writer_mode = "CODEX_H"

    if not listing_row:
        out_row = {
            "phase1_pilot": "1",
            "phase1_sku": sku,
            "phase1_asin": asin,
            "daily_intel_missing_for_today": "0",
            "last_executioner_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_ran_utc": "",
            "executioner_probe_type": "SKIP_NO_MARKET_DATA",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "SKIP_NO_MARKET_DATA",
            "writer_mode": writer_mode,
            "hard_floor_applied_gbp": "",
            "manual_cap_applied_gbp": "",
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": "SKIP_NO_MARKET_DATA",
            "phase1_boundary_lock_mode": "set_pending",
            "phase1_boundary_lock_date": "",
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
            "market_data_present": market_data_present,
            "write_effective": "1" if write_effective else "0",
            "repricing_enabled": "1" if repricing_enabled else "0",
            "universe_reason_code": _norm(universe_row.get("reason_code", "")),
            "decision": "skip_no_market_data",
        }
        return {
            "status": "skip",
            "run_id": run_id,
            "sku": sku,
            "reason": "skip_no_market_data",
            "out_row": out_row,
        }
    if not _has_active_offer_price(listing_row):
        out_row = {
            "phase1_pilot": "1",
            "phase1_sku": sku,
            "phase1_asin": asin,
            "daily_intel_missing_for_today": "0",
            "last_executioner_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_ran_utc": "",
            "executioner_probe_type": "SKIP_NO_ACTIVE_OFFER",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "SKIP_NO_ACTIVE_OFFER",
            "writer_mode": writer_mode,
            "hard_floor_applied_gbp": "",
            "manual_cap_applied_gbp": "",
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": "SKIP_NO_ACTIVE_OFFER",
            "phase1_boundary_lock_mode": "set_pending",
            "phase1_boundary_lock_date": "",
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
            "market_data_present": market_data_present,
            "write_effective": "1" if write_effective else "0",
            "repricing_enabled": "1" if repricing_enabled else "0",
            "universe_reason_code": _norm(universe_row.get("reason_code", "")),
            "decision": "skip_no_active_offer",
        }
        return {
            "status": "skip",
            "run_id": run_id,
            "sku": sku,
            "reason": "skip_no_active_offer",
            "out_row": out_row,
        }

    try:
        _progress(
            "helper_inner_boundary_before_first_call",
            run_id=run_id,
            sku=sku,
            first_call="_invoke_market_payload_subcall",
        )
        _checkpoint(
            "helper_inner_boundary_before_first_call",
            run_id=run_id,
            sku=sku,
        )
        try:
            subcall_spawn_contract = _invoke_market_payload_subcall(
                run_id=run_id,
                sku=sku,
                asin=asin,
                marketplace_id=marketplace_id,
                seller_id=seller_id,
                listing_row=listing_row,
            )
        except BaseException as exc:
            first_call_reason = _norm(str(exc)) or type(exc).__name__
            _progress(
                "helper_inner_boundary_failed",
                run_id=run_id,
                sku=sku,
                stage="first_call",
                error_type=type(exc).__name__,
                reason=first_call_reason[:240],
            )
            _checkpoint(
                "helper_inner_boundary_failed",
                run_id=run_id,
                sku=sku,
                stage="first_call",
            )
            # Preserve SIGINT/SystemExit(130) semantics so the outer owner
            # post-subcall boundary can run bounded reconcile before fail-close.
            if isinstance(exc, SystemExit):
                raw_code = getattr(exc, "code", "")
                code_text = _norm(raw_code)
                if not code_text and isinstance(raw_code, int):
                    code_text = str(raw_code)
                is_sigint_exit = code_text in {"130", "SIGINT"}
                if not is_sigint_exit:
                    try:
                        is_sigint_exit = int(float(code_text)) == 130
                    except Exception:
                        is_sigint_exit = False
                if is_sigint_exit:
                    raise
            raise RuntimeError(f"completion_convergence_failed:helper_inner_first_call:{first_call_reason[:180]}") from exc
        _progress(
            "helper_inner_boundary_after_first_call",
            run_id=run_id,
            sku=sku,
            first_call="_invoke_market_payload_subcall",
            contract_type=type(subcall_spawn_contract).__name__,
        )
        _checkpoint(
            "helper_inner_boundary_after_first_call",
            run_id=run_id,
            sku=sku,
        )
        _owner_provenance_capture_start(
            run_id=run_id,
            sku=sku,
            owner_pid=str(os.getpid()),
            subcall_pid=_norm(subcall_spawn_contract.get("subcall_pid", "")) if isinstance(subcall_spawn_contract, dict) else "",
            helper_pid="pending",
            timeout_seconds=_norm(subcall_spawn_contract.get("timeout_seconds", "")) if isinstance(subcall_spawn_contract, dict) else "",
        )
        try:
            _progress(
                "helper_inner_boundary_before_first_return_use",
                run_id=run_id,
                sku=sku,
                contract_type=type(subcall_spawn_contract).__name__,
            )
            _checkpoint(
                "helper_inner_boundary_before_first_return_use",
                run_id=run_id,
                sku=sku,
            )
            if not isinstance(subcall_spawn_contract, dict):
                raise RuntimeError("subcall_spawn_contract_not_object")
            subcall_checkpoint_last = _norm(subcall_spawn_contract.get("checkpoint_last", ""))
            subcall_pid_text = _norm(subcall_spawn_contract.get("subcall_pid", ""))
            _progress(
                "helper_inner_boundary_after_first_return_use",
                run_id=run_id,
                sku=sku,
                checkpoint_last=subcall_checkpoint_last,
                subcall_pid=subcall_pid_text,
            )
            _checkpoint(
                "helper_inner_boundary_after_first_return_use",
                run_id=run_id,
                sku=sku,
            )
        except BaseException as exc:
            return_use_reason = _norm(str(exc)) or type(exc).__name__
            _progress(
                "helper_inner_boundary_failed",
                run_id=run_id,
                sku=sku,
                stage="first_return_use",
                error_type=type(exc).__name__,
                reason=return_use_reason[:240],
            )
            _checkpoint(
                "helper_inner_boundary_failed",
                run_id=run_id,
                sku=sku,
                stage="first_return_use",
            )
            raise RuntimeError(
                f"completion_convergence_failed:helper_inner_first_return_use:{return_use_reason[:180]}"
            ) from exc
        _progress(
            "owner_post_subcall_probe_alive",
            run_id=run_id,
            sku=sku,
            checkpoint_last=subcall_checkpoint_last,
            subcall_pid=subcall_pid_text,
        )
        _progress(
            "owner_post_subcall_before_read_boundary",
            run_id=run_id,
            sku=sku,
            subcall_output_path=_norm(subcall_spawn_contract.get("subcall_output_path", "")),
            timeout_seconds=_norm(subcall_spawn_contract.get("timeout_seconds", "")),
        )
        _checkpoint(
            "owner_post_subcall_before_read_boundary",
            run_id=run_id,
            sku=sku,
            timeout_seconds=_norm(subcall_spawn_contract.get("timeout_seconds", "")),
        )
        read_boundary_contract = _invoke_market_payload_read_boundary(
            run_id=run_id,
            sku=sku,
            subcall_spawn_contract=subcall_spawn_contract,
        )
        _progress(
            "owner_post_subcall_after_read_boundary",
            run_id=run_id,
            sku=sku,
            contract_status=_norm(read_boundary_contract.get("contract_status", "")),
            checkpoint_last=_norm(read_boundary_contract.get("checkpoint_last", "")),
            error_class=_norm(read_boundary_contract.get("error_class", "")),
        )
        boundary_status = _norm(read_boundary_contract.get("contract_status", "")).lower()
        if boundary_status != "ok":
            boundary_reason = _norm(read_boundary_contract.get("reason", "")) or "market_payload_read_boundary_failed"
            raise RuntimeError(f"market_payload_read_boundary_failed:{boundary_reason}")
        payload_raw = read_boundary_contract.get("parsed_payload", {})
        if not isinstance(payload_raw, dict):
            raise RuntimeError("market_payload_read_boundary_invalid:payload_not_object")
        payload = payload_raw
        listings_observed_price = _norm(read_boundary_contract.get("listings_observed_price", ""))
    except BaseException as exc:
        boundary_reason = _norm(str(exc)) or type(exc).__name__
        _progress(
            "owner_post_subcall_failed",
            run_id=run_id,
            sku=sku,
            error_type=type(exc).__name__,
            reason=boundary_reason[:240],
        )
        if boundary_reason.startswith("completion_convergence_failed:helper_inner_"):
            raise RuntimeError(boundary_reason[:240]) from exc
        is_sigint_exit = False
        if isinstance(exc, SystemExit):
            raw_code = getattr(exc, "code", "")
            code_text = _norm(raw_code)
            if not code_text and isinstance(raw_code, int):
                code_text = str(raw_code)
            if code_text in {"130", "SIGINT"}:
                is_sigint_exit = True
            else:
                try:
                    is_sigint_exit = int(float(code_text)) == 130
                except Exception:
                    is_sigint_exit = False
        if is_sigint_exit:
            reconcile_wait_seconds = min(
                max(_env_float("H110_OWNER_POST_SUBCALL_INTERRUPT_RECONCILE_SECONDS", 8.0), 0.5),
                20.0,
            )
            reconcile_contract = dict(subcall_spawn_contract)
            reconcile_contract["timeout_seconds"] = f"{reconcile_wait_seconds:.2f}"
            _progress(
                "owner_post_subcall_interrupt_reconcile_enter",
                run_id=run_id,
                sku=sku,
                reason=boundary_reason[:240],
                wait_seconds=f"{reconcile_wait_seconds:.2f}",
                subcall_output_path=_norm(subcall_spawn_contract.get("subcall_output_path", "")),
            )
            _owner_interrupt_reconcile_mark_enter(run_id=run_id, sku=sku, wait_seconds=reconcile_wait_seconds)
            try:
                try:
                    reconcile_result = _invoke_market_payload_read_boundary(
                        run_id=run_id,
                        sku=sku,
                        subcall_spawn_contract=reconcile_contract,
                    )
                    reconcile_status = _norm(reconcile_result.get("contract_status", "")).lower()
                    if reconcile_status == "ok" and isinstance(reconcile_result.get("parsed_payload", {}), dict):
                        state_failed, state_reason = _run_state_terminal_failed_for_run(run_id=run_id)
                        if state_failed:
                            _progress(
                                "owner_post_subcall_interrupt_reconcile_blocked",
                                run_id=run_id,
                                sku=sku,
                                reason=state_reason[:240],
                            )
                            raise RuntimeError(
                                f"completion_convergence_failed:owner_post_subcall_boundary_failed:{state_reason[:180]}"
                            ) from exc
                        payload = reconcile_result.get("parsed_payload", {})
                        listings_observed_price = _norm(reconcile_result.get("listings_observed_price", ""))
                        _progress(
                            "owner_post_subcall_interrupt_reconcile_success",
                            run_id=run_id,
                            sku=sku,
                            checkpoint_last=_norm(reconcile_result.get("checkpoint_last", "")),
                        )
                    else:
                        reconcile_reason = _norm(reconcile_result.get("reason", "")) or "reconcile_contract_not_ok"
                        _progress(
                            "owner_post_subcall_interrupt_reconcile_failed",
                            run_id=run_id,
                            sku=sku,
                            reason=reconcile_reason[:240],
                            checkpoint_last=_norm(reconcile_result.get("checkpoint_last", "")),
                        )
                        raise RuntimeError(
                            f"completion_convergence_failed:owner_post_subcall_boundary_failed:{boundary_reason[:180]}"
                        ) from exc
                finally:
                    _owner_interrupt_reconcile_mark_exit(run_id=run_id)
            except BaseException as reconcile_exc:
                _progress(
                    "owner_post_subcall_interrupt_reconcile_failed",
                    run_id=run_id,
                    sku=sku,
                    error_type=type(reconcile_exc).__name__,
                    reason=_norm(str(reconcile_exc))[:240],
                )
                raise RuntimeError(
                    f"completion_convergence_failed:owner_post_subcall_boundary_failed:{boundary_reason[:180]}"
                ) from exc
        else:
            raise RuntimeError(
                f"completion_convergence_failed:owner_post_subcall_boundary_failed:{boundary_reason[:180]}"
            ) from exc
    return {
        "status": "ok",
        "run_id": run_id,
        "sku": sku,
        "reason": "ok",
        "market_data_present": market_data_present,
        "write_effective": str(_to_bool_int(write_effective)),
        "repricing_enabled": str(_to_bool_int(repricing_enabled)),
        "writer_mode": writer_mode,
        "asin": asin,
        "marketplace_id": marketplace_id,
        "seller_id": seller_id,
        "listings_observed_price": listings_observed_price,
        "payload": payload,
        "listing_snapshot_path": listing_snapshot_path,
        "seller_snapshot_path": seller_snapshot_path,
    }


def _run_market_payload_subcall_mode(*, input_path: Path, output_path: Path) -> int:
    checkpoint_state_path = output_path.with_name(f"checkpoint.{output_path.name}")
    req: dict[str, object] = {}
    run_id = ""
    sku = ""

    def _subcall_checkpoint(name: str, **fields: object) -> None:
        payload: dict[str, str] = {
            "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "checkpoint": _norm(name),
            "run_id": _norm(run_id),
            "sku": _norm(sku),
            "pid": str(os.getpid()),
            "input_path": str(input_path),
            "output_path": str(output_path),
        }
        for key, value in fields.items():
            payload[str(key)] = _norm(value)
        try:
            _atomic_write_text(checkpoint_state_path, json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            pass
        _progress(name, **payload)

    try:
        _subcall_checkpoint("market_payload_subcall_mode_enter")
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        req = req_raw if isinstance(req_raw, dict) else {}
        run_id = _norm(req.get("run_id", ""))
        sku = _norm(req.get("sku", "")).upper()
        _subcall_checkpoint("market_payload_subcall_mode_after_input_read")
        _subcall_checkpoint("market_payload_subcall_to_callsite_gap_entry")
        _subcall_checkpoint("market_payload_subcall_to_callsite_gap_before_first_instruction")
        _subcall_checkpoint("live_subcall_to_callsite_before_first_instruction_invocation")
        _set_market_payload_checkpoint_context(run_id=run_id, sku=sku, checkpoint_path=checkpoint_state_path)
        _subcall_checkpoint("market_payload_subcall_to_callsite_gap_after_first_instruction_return")
        _subcall_checkpoint("live_subcall_to_callsite_after_first_instruction_return")
        _subcall_checkpoint("live_subcall_to_callsite_before_req_rebind")
        req = req_raw
        _subcall_checkpoint("live_subcall_to_callsite_after_req_rebind")
        _subcall_checkpoint("live_subcall_to_callsite_before_req_dict_guard")
        if not isinstance(req, dict):
            raise RuntimeError("input_json_not_object")
        _subcall_checkpoint("live_subcall_to_callsite_after_req_dict_guard")
        _subcall_checkpoint("live_subcall_to_callsite_before_asin_norm")
        asin = _norm(req.get("asin", ""))
        _subcall_checkpoint("live_subcall_to_callsite_after_asin_norm")
        _subcall_checkpoint("live_subcall_to_callsite_before_marketplace_norm")
        _subcall_checkpoint("live_subcall_to_callsite_before_marketplace_get")
        marketplace_id_raw = req.get("marketplace_id", "")
        _subcall_checkpoint("live_subcall_to_callsite_after_marketplace_get")
        _subcall_checkpoint("live_subcall_to_callsite_before_marketplace_norm_call")
        marketplace_id = _norm(marketplace_id_raw)
        _subcall_checkpoint("live_subcall_to_callsite_after_marketplace_norm_call")
        _subcall_checkpoint("live_subcall_to_callsite_after_marketplace_assignment")
        _subcall_checkpoint("live_subcall_to_callsite_after_marketplace_norm")
        _subcall_checkpoint("live_subcall_to_callsite_before_seller_norm")
        seller_id = _norm(req.get("seller_id", ""))
        _subcall_checkpoint("live_subcall_to_callsite_after_seller_norm")
        _subcall_checkpoint("live_subcall_to_callsite_before_listing_row_raw_get")
        _subcall_checkpoint("live_subcall_to_callsite_before_listing_row_get")
        listing_row_value = req.get("listing_row", {})
        _subcall_checkpoint("live_subcall_to_callsite_after_listing_row_get")
        listing_row_raw = listing_row_value
        _subcall_checkpoint("live_subcall_to_callsite_after_listing_row_assignment")
        _subcall_checkpoint("live_subcall_to_callsite_after_listing_row_raw_get")
        _subcall_checkpoint("live_subcall_to_callsite_before_listing_row_guard")
        _subcall_checkpoint("live_subcall_to_callsite_before_listing_row_guard_eval")
        if not isinstance(listing_row_raw, dict):
            raise RuntimeError("listing_row_not_object")
        _subcall_checkpoint("live_subcall_to_callsite_after_listing_row_guard_eval")
        _subcall_checkpoint("live_subcall_to_callsite_after_listing_row_guard")
        _subcall_checkpoint("live_subcall_to_callsite_before_normalized_listing_row_build")
        normalized_listing_row = {str(k): _norm(v) for k, v in listing_row_raw.items()}
        _subcall_checkpoint("live_subcall_to_callsite_after_normalized_listing_row_build")
        _subcall_checkpoint("live_subcall_to_callsite_before_target_emission_instruction")
        _subcall_checkpoint("market_payload_subcall_to_callsite_gap_before_target_emission_call")
        _subcall_checkpoint("live_subcall_to_callsite_after_target_emission_instruction")
        _subcall_checkpoint("live_subcall_to_callsite_before_callsite_before_function_emission")
        _subcall_checkpoint("market_payload_callsite_before_function")
        _subcall_checkpoint("live_subcall_to_callsite_after_callsite_before_function_emission_return")
        _subcall_checkpoint("market_payload_subcall_to_callsite_gap_after_target_emission_return")
        _market_payload_checkpoint_raw("market_payload_callsite_to_entry_gap_entry")
        _market_payload_checkpoint_raw("live_callsite_to_entry_before_caller_pre_checkpoint_call_invocation")
        _market_payload_checkpoint_raw("caller_pre_checkpoint_call_for_callsite_to_entry_before_first_instruction_checkpoint")
        _market_payload_checkpoint_raw("live_callsite_to_entry_after_caller_pre_checkpoint_call_return")
        _market_payload_checkpoint_raw("market_payload_callsite_to_entry_gap_before_first_instruction")
        _market_payload_checkpoint_raw("caller_first_instruction_after_callsite_to_entry_before_first_instruction_call")
        _market_payload_checkpoint_raw("caller_post_checkpoint_call_for_callsite_to_entry_before_first_instruction_checkpoint")
        _market_payload_checkpoint_raw("caller_after_first_instruction_after_callsite_to_entry_before_first_instruction_call")
        _market_payload_checkpoint_raw("callsite_to_entry_after_restored_return_edge")
        try:
            payload, listings_observed_price = _phase1_market_payload_from_snapshots(
                sku=sku,
                asin=asin,
                marketplace_id=marketplace_id,
                our_seller_id=seller_id,
                listing_row=normalized_listing_row,
            )
        except Exception as exc:
            _subcall_checkpoint(
                "market_payload_callsite_except",
                error_class=type(exc).__name__,
                reason=_norm(str(exc)),
            )
            raise
        _subcall_checkpoint("market_payload_callsite_after_function")
        contract = {
            "run_id": run_id,
            "sku": sku,
            "status": "ok",
            "reason": "ok",
            "payload": payload if isinstance(payload, dict) else {},
            "listings_observed_price": _norm(listings_observed_price),
            "checkpoint_last": "market_payload_ready",
            "error_class": "",
        }
        _subcall_checkpoint("market_payload_subcall_mode_before_output_write", contract_status="ok")
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 0
    except BaseException as exc:
        _subcall_checkpoint(
            "market_payload_subcall_mode_except_before_output_write",
            error_class=type(exc).__name__,
            reason=_norm(str(exc)),
        )
        run_id = _norm((req if isinstance(req, dict) else {}).get("run_id", ""))
        sku = _norm((req if isinstance(req, dict) else {}).get("sku", "")).upper()
        contract = {
            "run_id": run_id,
            "sku": sku,
            "status": "failed",
            "reason": _norm(str(exc)) or type(exc).__name__,
            "payload": {},
            "listings_observed_price": "",
            "checkpoint_last": "market_payload_subcall_failed",
            "error_class": type(exc).__name__,
        }
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 1
    finally:
        _set_market_payload_checkpoint_context(run_id="", sku="", checkpoint_path=None)


def _invoke_market_payload_subcall(
    *,
    run_id: str,
    sku: str,
    asin: str,
    marketplace_id: str,
    seller_id: str,
    listing_row: dict[str, str],
) -> dict[str, object]:
    helper_dir = H_LIVE_DIR / "tmp_h110_market_payload_subcall"
    helper_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
    input_path = helper_dir / f"in.{token}.json"
    output_path = helper_dir / f"out.{token}.json"
    stdout_path = helper_dir / f"stdout.{token}.log"
    stderr_path = helper_dir / f"stderr.{token}.log"
    req = {
        "run_id": run_id,
        "sku": sku,
        "asin": asin,
        "marketplace_id": marketplace_id,
        "seller_id": seller_id,
        "listing_row": listing_row,
    }
    _atomic_write_text(input_path, json.dumps(req, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--market-payload-subcall",
        "--market-payload-input",
        str(input_path),
        "--market-payload-output",
        str(output_path),
    )
    timeout_seconds = max(_env_int("H110_MARKET_PAYLOAD_SUBCALL_TIMEOUT_SECONDS", 90), 20)
    creationflags = 0
    if os.name == "nt":
        creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        creationflags |= int(getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
    with stdout_path.open("wb") as out_fh, stderr_path.open("wb") as err_fh:
        try:
            proc = _popen_hidden(
                cmd,
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=out_fh,
                stderr=err_fh,
                close_fds=True,
                env=os.environ.copy(),
                creationflags=creationflags,
            )
        except PermissionError as exc:
            if creationflags and os.name == "nt":
                _progress(
                    "market_payload_subcall_creationflags_fallback",
                    run_id=run_id,
                    sku=sku,
                    reason=f"{type(exc).__name__}:{exc}",
                    creationflags=str(creationflags),
                )
                proc = _popen_hidden(
                    cmd,
                    cwd=str(ROOT),
                    stdin=subprocess.DEVNULL,
                    stdout=out_fh,
                    stderr=err_fh,
                    close_fds=True,
                    env=os.environ.copy(),
                    creationflags=0,
                )
            else:
                raise
    child_pid = int(proc.pid)
    _progress(
        "market_payload_subcall_launch",
        run_id=run_id,
        sku=sku,
        child_pid=str(child_pid),
        cmd=" ".join(cmd),
        input_path=str(input_path),
        output_path=str(output_path),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )
    probe_seconds = min(max(_env_float("H110_MARKET_PAYLOAD_SUBCALL_EARLY_EXIT_PROBE_SECONDS", 1.0), 0.2), 2.0)
    probe_interval = min(max(_env_float("H110_MARKET_PAYLOAD_SUBCALL_EARLY_EXIT_PROBE_INTERVAL_SECONDS", 0.1), 0.05), 0.5)
    probe_boundary_enabled = _to_bool(
        os.environ.get("H110_MARKET_PAYLOAD_SUBCALL_PROBE_BOUNDARY_ENABLED", "0"),
        default=False,
    )
    if not probe_boundary_enabled:
        _progress(
            "market_payload_subcall_probe_boundary_bypassed",
            run_id=run_id,
            sku=sku,
            child_pid=str(child_pid),
            reason="probe_boundary_disabled_use_read_boundary",
            timeout_seconds=str(timeout_seconds),
        )
        _progress(
            "market_payload_subcall_spawned",
            run_id=run_id,
            sku=sku,
            child_pid=str(child_pid),
            input_path=str(input_path),
            output_path=str(output_path),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            timeout_seconds=str(timeout_seconds),
        )
        return {
            "run_id": run_id,
            "sku": sku,
            "asin": asin,
            "marketplace_id": marketplace_id,
            "seller_id": seller_id,
            "listing_row": listing_row,
            "contract_status": "ok",
            "reason": "spawned_probe_bypassed",
            "subcall_output_path": str(output_path),
            "subcall_input_path": str(input_path),
            "subcall_stdout_path": str(stdout_path),
            "subcall_stderr_path": str(stderr_path),
            "subcall_pid": child_pid,
            "timeout_seconds": timeout_seconds,
            "checkpoint_last": "market_payload_subcall_spawned",
            "error_class": "",
        }
    _progress(
        "market_payload_subcall_early_exit_probe_enter",
        run_id=run_id,
        sku=sku,
        child_pid=str(child_pid),
        probe_seconds=f"{probe_seconds:.2f}",
        probe_interval_seconds=f"{probe_interval:.2f}",
    )
    _progress(
        "subcall_inner_boundary_before_first_call",
        run_id=run_id,
        sku=sku,
        first_call="_invoke_market_payload_probe_boundary",
        child_pid=str(child_pid),
    )
    _checkpoint(
        "subcall_inner_boundary_before_first_call",
        run_id=run_id,
        sku=sku,
    )
    try:
        probe_contract = _invoke_market_payload_probe_boundary(
            run_id=run_id,
            sku=sku,
            subcall_pid=child_pid,
            subcall_output_path=str(output_path),
            probe_seconds=probe_seconds,
            probe_interval_seconds=probe_interval,
        )
    except BaseException as exc:
        first_call_reason = _norm(str(exc)) or type(exc).__name__
        _progress(
            "subcall_inner_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="first_call",
            error_type=type(exc).__name__,
            reason=first_call_reason[:240],
        )
        _checkpoint(
            "subcall_inner_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="first_call",
        )
        raise RuntimeError(
            f"completion_convergence_failed:subcall_inner_first_call:{first_call_reason[:180]}"
        ) from exc
    _progress(
        "subcall_inner_boundary_after_first_call",
        run_id=run_id,
        sku=sku,
        first_call="_invoke_market_payload_probe_boundary",
        contract_type=type(probe_contract).__name__,
    )
    _checkpoint(
        "subcall_inner_boundary_after_first_call",
        run_id=run_id,
        sku=sku,
    )
    try:
        _progress(
            "subcall_inner_boundary_before_first_return_use",
            run_id=run_id,
            sku=sku,
            contract_type=type(probe_contract).__name__,
        )
        _checkpoint(
            "subcall_inner_boundary_before_first_return_use",
            run_id=run_id,
            sku=sku,
        )
        if not isinstance(probe_contract, dict):
            raise RuntimeError("probe_contract_not_object")
        observed_rc = _norm(probe_contract.get("observed_rc", ""))
        probe_checkpoint_last = _norm(probe_contract.get("checkpoint_last", ""))
        _progress(
            "subcall_inner_boundary_after_first_return_use",
            run_id=run_id,
            sku=sku,
            checkpoint_last=probe_checkpoint_last,
            observed_rc=observed_rc,
        )
        _checkpoint(
            "subcall_inner_boundary_after_first_return_use",
            run_id=run_id,
            sku=sku,
        )
    except BaseException as exc:
        return_use_reason = _norm(str(exc)) or type(exc).__name__
        _progress(
            "subcall_inner_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="first_return_use",
            error_type=type(exc).__name__,
            reason=return_use_reason[:240],
        )
        _checkpoint(
            "subcall_inner_boundary_failed",
            run_id=run_id,
            sku=sku,
            stage="first_return_use",
        )
        raise RuntimeError(
            f"completion_convergence_failed:subcall_inner_first_return_use:{return_use_reason[:180]}"
        ) from exc
    if observed_rc:
        _progress(
            "market_payload_subcall_early_exit",
            run_id=run_id,
            sku=sku,
            child_pid=str(child_pid),
            rc=observed_rc,
        )
        _progress(
            "market_payload_subcall_early_exit_details",
            run_id=run_id,
            sku=sku,
            child_pid=str(child_pid),
            rc=observed_rc,
            cmd=" ".join(cmd),
            input_path=str(input_path),
            output_path=str(output_path),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )
        raise RuntimeError(f"completion_convergence_failed:market_payload_subcall_early_exit:rc_{observed_rc}")
    _progress(
        "market_payload_subcall_early_exit_probe_alive",
        run_id=run_id,
        sku=sku,
        child_pid=str(child_pid),
        probe_seconds=f"{probe_seconds:.2f}",
    )
    _progress(
        "market_payload_subcall_spawned",
        run_id=run_id,
        sku=sku,
        child_pid=str(child_pid),
        input_path=str(input_path),
        output_path=str(output_path),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        timeout_seconds=str(timeout_seconds),
    )
    return {
        "run_id": run_id,
        "sku": sku,
        "asin": asin,
        "marketplace_id": marketplace_id,
        "seller_id": seller_id,
        "listing_row": listing_row,
        "contract_status": "ok",
        "reason": "spawned",
        "subcall_output_path": str(output_path),
        "subcall_input_path": str(input_path),
        "subcall_stdout_path": str(stdout_path),
        "subcall_stderr_path": str(stderr_path),
        "subcall_pid": child_pid,
        "timeout_seconds": timeout_seconds,
        "checkpoint_last": "market_payload_subcall_spawned",
        "error_class": "",
    }


def _run_market_payload_probe_boundary_mode(*, input_path: Path, output_path: Path) -> int:
    checkpoint_state_path = output_path.with_name(f"checkpoint.{output_path.name}")
    req: dict[str, object] = {}
    run_id = ""
    sku = ""

    def _probe_boundary_checkpoint(name: str, **fields: object) -> None:
        payload: dict[str, str] = {
            "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "checkpoint": _norm(name),
            "run_id": _norm(run_id),
            "sku": _norm(sku),
            "pid": str(os.getpid()),
            "input_path": str(input_path),
            "output_path": str(output_path),
        }
        for key, value in fields.items():
            payload[str(key)] = _norm(value)
        try:
            _atomic_write_text(checkpoint_state_path, json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            pass
        _progress(name, **payload)

    def _validate_subcall_output_contract(*, expected_run_id: str, expected_sku: str, subcall_output_path_raw: str) -> tuple[bool, str]:
        path = Path(subcall_output_path_raw)
        if not path.exists():
            return False, "missing_output"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return False, "invalid_json"
        if not isinstance(raw, dict):
            return False, "output_not_object"
        out_run_id = _norm(raw.get("run_id", ""))
        out_sku = _norm(raw.get("sku", "")).upper()
        if out_run_id != expected_run_id or out_sku != expected_sku:
            return False, "identity_mismatch"
        status = _norm(raw.get("status", "")).lower()
        payload = raw.get("payload", {})
        if status != "ok":
            return False, f"status_{status or 'missing'}"
        if not isinstance(payload, dict):
            return False, "payload_not_object"
        return True, "ok"

    try:
        _probe_boundary_checkpoint("market_payload_probe_boundary_mode_enter")
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        req = req_raw if isinstance(req_raw, dict) else {}
        run_id = _norm(req.get("run_id", ""))
        sku = _norm(req.get("sku", "")).upper()
        _probe_boundary_checkpoint("market_payload_probe_boundary_mode_after_input_read")
        req = req_raw
        if not isinstance(req_raw, dict):
            raise RuntimeError("input_json_not_object")
        subcall_pid = int(_norm(req.get("subcall_pid", "")) or "0")
        subcall_output_path = _norm(req.get("subcall_output_path", ""))
        probe_seconds = min(max(float(_norm(req.get("probe_seconds", "")) or "1.0"), 0.2), 2.0)
        probe_interval_seconds = min(max(float(_norm(req.get("probe_interval_seconds", "")) or "0.1"), 0.05), 0.5)
        if subcall_pid <= 0:
            raise RuntimeError("invalid_subcall_pid")
        if not subcall_output_path:
            raise RuntimeError("missing_subcall_output_path")

        deadline = time.time() + probe_seconds
        child_alive = True
        loop_iteration = 0
        _probe_boundary_checkpoint(
            "market_payload_probe_boundary_loop_enter",
            subcall_pid=str(subcall_pid),
            probe_seconds=f"{probe_seconds:.3f}",
            probe_interval_seconds=f"{probe_interval_seconds:.3f}",
        )
        while time.time() < deadline:
            loop_iteration += 1
            _probe_boundary_checkpoint(
                "market_payload_probe_boundary_before_pid_alive",
                iteration=str(loop_iteration),
                subcall_pid=str(subcall_pid),
            )
            pid_alive_now = _pid_alive(subcall_pid)
            _probe_boundary_checkpoint(
                "market_payload_probe_boundary_after_pid_alive",
                iteration=str(loop_iteration),
                subcall_pid=str(subcall_pid),
                pid_alive="1" if pid_alive_now else "0",
            )
            if not pid_alive_now:
                child_alive = False
                break
            time.sleep(probe_interval_seconds)
        deadline_reached = time.time() >= deadline
        _probe_boundary_checkpoint(
            "market_payload_probe_boundary_before_timeout_classification",
            iteration=str(loop_iteration),
            child_alive="1" if child_alive else "0",
            deadline_reached="1" if deadline_reached else "0",
        )
        _probe_boundary_checkpoint(
            "market_payload_probe_boundary_before_output_check",
            subcall_output_path=subcall_output_path,
        )
        subcall_output_exists = "0"
        subcall_output_size = ""
        with contextlib.suppress(Exception):
            subcall_output_exists = "1" if Path(subcall_output_path).exists() else "0"
            if subcall_output_exists == "1":
                subcall_output_size = str(int(Path(subcall_output_path).stat().st_size))
        _probe_boundary_checkpoint(
            "market_payload_probe_boundary_after_output_check",
            subcall_output_path=subcall_output_path,
            subcall_output_exists=subcall_output_exists,
            subcall_output_size=subcall_output_size,
        )
        pid0_grace_failed = False
        pid0_grace_deferred = False
        if (not child_alive) and loop_iteration == 1 and (not deadline_reached) and subcall_output_exists == "0":
            grace_seconds = min(max(_env_float("H110_PROBE_BOUNDARY_PID0_GRACE_SECONDS", 0.35), 0.05), 1.0)
            _probe_boundary_checkpoint(
                "market_payload_probe_boundary_pid0_grace_enter",
                grace_seconds=f"{grace_seconds:.3f}",
                subcall_pid=str(subcall_pid),
            )
            time.sleep(grace_seconds)
            grace_pid_alive = _pid_alive(subcall_pid)
            grace_output_exists = "1" if Path(subcall_output_path).exists() else "0"
            _probe_boundary_checkpoint(
                "market_payload_probe_boundary_pid0_grace_recheck",
                subcall_pid=str(subcall_pid),
                pid_alive="1" if grace_pid_alive else "0",
                subcall_output_exists=grace_output_exists,
            )
            if grace_pid_alive or grace_output_exists == "1":
                child_alive = True
                subcall_output_exists = grace_output_exists
                _probe_boundary_checkpoint(
                    "market_payload_probe_boundary_pid0_grace_continue",
                    subcall_pid=str(subcall_pid),
                    pid_alive="1" if grace_pid_alive else "0",
                    subcall_output_exists=grace_output_exists,
                )
            else:
                _probe_boundary_checkpoint(
                    "market_payload_probe_boundary_pid0_grace_fail",
                    subcall_pid=str(subcall_pid),
                    pid_alive="0",
                    subcall_output_exists="0",
                )
                pid0_grace_failed = True
                if not deadline_reached:
                    pid0_grace_deferred = True
                    _probe_boundary_checkpoint(
                        "market_payload_probe_boundary_pid0_grace_defer",
                        subcall_pid=str(subcall_pid),
                        remaining_seconds=f"{max(deadline - time.time(), 0.0):.3f}",
                    )
                    while time.time() < deadline:
                        time.sleep(probe_interval_seconds)
                        defer_pid_alive = _pid_alive(subcall_pid)
                        defer_output_exists = "1" if Path(subcall_output_path).exists() else "0"
                        if defer_pid_alive or defer_output_exists == "1":
                            child_alive = True
                            subcall_output_exists = defer_output_exists
                            break
                    deadline_reached = time.time() >= deadline
                    if (not child_alive) and subcall_output_exists == "0" and deadline_reached:
                        _probe_boundary_checkpoint(
                            "market_payload_probe_boundary_pid0_grace_deadline_reached",
                            subcall_pid=str(subcall_pid),
                            child_alive="0",
                            subcall_output_exists="0",
                        )

        output_contract_valid = False
        output_contract_reason = ""
        output_exists_now = Path(subcall_output_path).exists()
        if output_exists_now:
            subcall_output_exists = "1"
            with contextlib.suppress(Exception):
                subcall_output_size = str(int(Path(subcall_output_path).stat().st_size))
            output_contract_valid, output_contract_reason = _validate_subcall_output_contract(
                expected_run_id=run_id,
                expected_sku=sku,
                subcall_output_path_raw=subcall_output_path,
            )
            if output_contract_valid:
                _probe_boundary_checkpoint(
                    "market_payload_probe_boundary_output_success",
                    subcall_output_path=subcall_output_path,
                    child_alive="1" if child_alive else "0",
                )
                if not child_alive:
                    _probe_boundary_checkpoint(
                        "market_payload_probe_boundary_output_success_after_dead_child",
                        subcall_output_path=subcall_output_path,
                    )
            else:
                _probe_boundary_checkpoint(
                    "market_payload_probe_boundary_output_invalid",
                    subcall_output_path=subcall_output_path,
                    reason=output_contract_reason or "output_invalid",
                )
        elif deadline_reached and (not child_alive):
            _probe_boundary_checkpoint(
                "market_payload_probe_boundary_output_missing_at_deadline",
                subcall_output_path=subcall_output_path,
            )

        if child_alive or output_contract_valid:
            contract_reason = "probe_alive" if child_alive else "probe_output_valid_after_dead_child"
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "ok",
                "reason": contract_reason,
                "subcall_pid": str(subcall_pid),
                "subcall_output_path": subcall_output_path,
                "observed_rc": "",
                "checkpoint_last": "market_payload_subcall_early_exit_probe_alive",
                "error_class": "",
            }
            _probe_boundary_checkpoint(
                "market_payload_probe_boundary_mode_before_output_write",
                contract_status="ok",
                contract_reason=contract_reason,
            )
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 0

        if pid0_grace_failed and pid0_grace_deferred and deadline_reached and subcall_output_exists == "0":
            _probe_boundary_checkpoint(
                "market_payload_probe_boundary_pid0_grace_final_fail",
                subcall_pid=str(subcall_pid),
                child_alive="0",
                subcall_output_exists="0",
            )

        contract = {
            "run_id": run_id,
            "sku": sku,
            "contract_status": "failed",
            "reason": "subcall_exited_during_probe",
            "subcall_pid": str(subcall_pid),
            "subcall_output_path": subcall_output_path,
            "observed_rc": "",
            "checkpoint_last": "market_payload_probe_boundary_failed",
            "error_class": "ChildProcessError",
        }
        _probe_boundary_checkpoint(
            "market_payload_probe_boundary_mode_before_output_write",
            contract_status="failed",
            contract_reason="subcall_exited_during_probe",
        )
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 1
    except BaseException as exc:
        _probe_boundary_checkpoint(
            "market_payload_probe_boundary_mode_except_before_output_write",
            error_class=type(exc).__name__,
            reason=_norm(str(exc)),
        )
        contract = {
            "run_id": run_id,
            "sku": sku,
            "contract_status": "failed",
            "reason": _norm(str(exc)) or type(exc).__name__,
            "subcall_pid": _norm(req.get("subcall_pid", "")),
            "subcall_output_path": _norm(req.get("subcall_output_path", "")),
            "observed_rc": "",
            "checkpoint_last": "market_payload_probe_boundary_invalid",
            "error_class": type(exc).__name__,
        }
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 1


def _run_market_payload_probe_boundary_read_helper_mode(*, input_path: Path, output_path: Path) -> int:
    req: dict[str, object] = {}
    run_id = ""
    sku = ""
    try:
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req_raw, dict):
            raise RuntimeError("input_json_not_object")
        req = req_raw
        run_id = _norm(req.get("run_id", ""))
        sku = _norm(req.get("sku", "")).upper()
        probe_boundary_pid = int(_norm(req.get("probe_boundary_pid", "")) or "0")
        probe_boundary_output_path = Path(_norm(req.get("probe_boundary_output_path", "")))
        timeout_seconds = max(int(float(_norm(req.get("timeout_seconds", "")) or "20")), 10)
        if probe_boundary_pid <= 0:
            raise RuntimeError("invalid_probe_boundary_pid")
        if not _norm(str(probe_boundary_output_path)):
            raise RuntimeError("missing_probe_boundary_output_path")

        deadline = time.monotonic() + float(timeout_seconds)
        while time.monotonic() < deadline:
            if not _pid_alive(probe_boundary_pid):
                break
            time.sleep(0.1)

        if _pid_alive(probe_boundary_pid):
            _progress(
                "probe_boundary_read_helper_failed",
                run_id=run_id,
                sku=sku,
                reason=f"timeout_after_{timeout_seconds}s",
            )
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": f"timeout_after_{timeout_seconds}s",
                "probe_boundary_output_path": str(probe_boundary_output_path),
                "probe_boundary_payload": {},
                "checkpoint_last": "probe_boundary_read_helper_failed",
                "error_class": "TimeoutError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1

        flush_deadline = time.monotonic() + 1.0
        while time.monotonic() < flush_deadline and (not probe_boundary_output_path.exists()):
            time.sleep(0.1)
        if not probe_boundary_output_path.exists():
            _progress(
                "probe_boundary_read_helper_failed",
                run_id=run_id,
                sku=sku,
                reason="missing_probe_boundary_output",
            )
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": "missing_probe_boundary_output",
                "probe_boundary_output_path": str(probe_boundary_output_path),
                "probe_boundary_payload": {},
                "checkpoint_last": "probe_boundary_read_helper_failed",
                "error_class": "FileNotFoundError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1

        try:
            probe_contract_raw = json.loads(probe_boundary_output_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _progress(
                "probe_boundary_read_helper_invalid",
                run_id=run_id,
                sku=sku,
                reason="invalid_probe_boundary_json",
                error=f"{type(exc).__name__}:{exc}",
            )
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": "invalid_probe_boundary_json",
                "probe_boundary_output_path": str(probe_boundary_output_path),
                "probe_boundary_payload": {},
                "checkpoint_last": "probe_boundary_read_helper_invalid",
                "error_class": type(exc).__name__,
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1
        if not isinstance(probe_contract_raw, dict):
            _progress(
                "probe_boundary_read_helper_invalid",
                run_id=run_id,
                sku=sku,
                reason="probe_boundary_contract_not_object",
            )
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": "probe_boundary_contract_not_object",
                "probe_boundary_output_path": str(probe_boundary_output_path),
                "probe_boundary_payload": {},
                "checkpoint_last": "probe_boundary_read_helper_invalid",
                "error_class": "TypeError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1

        _progress(
            "probe_boundary_read_helper_read",
            run_id=run_id,
            sku=sku,
            probe_boundary_output_path=str(probe_boundary_output_path),
        )
        contract_run_id = _norm(probe_contract_raw.get("run_id", ""))
        contract_sku = _norm(probe_contract_raw.get("sku", "")).upper()
        if contract_run_id != run_id or contract_sku != sku:
            _progress(
                "probe_boundary_read_helper_invalid",
                run_id=run_id,
                sku=sku,
                reason="identity_mismatch",
            )
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": "identity_mismatch",
                "probe_boundary_output_path": str(probe_boundary_output_path),
                "probe_boundary_payload": probe_contract_raw,
                "checkpoint_last": "probe_boundary_read_helper_invalid",
                "error_class": "ValueError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1
        contract_status = _norm(probe_contract_raw.get("contract_status", "")).lower()
        if contract_status not in {"ok", "failed"}:
            _progress(
                "probe_boundary_read_helper_invalid",
                run_id=run_id,
                sku=sku,
                reason="status_invalid",
            )
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": "status_invalid",
                "probe_boundary_output_path": str(probe_boundary_output_path),
                "probe_boundary_payload": probe_contract_raw,
                "checkpoint_last": "probe_boundary_read_helper_invalid",
                "error_class": "ValueError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1
        if not _norm(probe_contract_raw.get("subcall_pid", "")) or not _norm(probe_contract_raw.get("subcall_output_path", "")):
            _progress(
                "probe_boundary_read_helper_invalid",
                run_id=run_id,
                sku=sku,
                reason="missing_required_fields",
            )
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": "missing_required_fields",
                "probe_boundary_output_path": str(probe_boundary_output_path),
                "probe_boundary_payload": probe_contract_raw,
                "checkpoint_last": "probe_boundary_read_helper_invalid",
                "error_class": "ValueError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1
        if contract_status != "ok":
            failed_reason = _norm(probe_contract_raw.get("reason", "")) or "status_not_ok"
            _progress(
                "probe_boundary_read_helper_failed",
                run_id=run_id,
                sku=sku,
                reason=failed_reason,
                checkpoint_last=_norm(probe_contract_raw.get("checkpoint_last", "")),
                error_class=_norm(probe_contract_raw.get("error_class", "")),
            )
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": failed_reason,
                "probe_boundary_output_path": str(probe_boundary_output_path),
                "probe_boundary_payload": probe_contract_raw,
                "checkpoint_last": "probe_boundary_read_helper_failed",
                "error_class": _norm(probe_contract_raw.get("error_class", "")) or "RuntimeError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1

        _progress(
            "probe_boundary_read_helper_valid",
            run_id=run_id,
            sku=sku,
            checkpoint_last=_norm(probe_contract_raw.get("checkpoint_last", "")),
            error_class=_norm(probe_contract_raw.get("error_class", "")),
        )
        contract = {
            "run_id": run_id,
            "sku": sku,
            "contract_status": "ok",
            "reason": "ok",
            "probe_boundary_output_path": str(probe_boundary_output_path),
            "probe_boundary_payload": probe_contract_raw,
            "checkpoint_last": "probe_boundary_read_helper_valid",
            "error_class": "",
        }
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 0
    except BaseException as exc:
        _progress(
            "probe_boundary_read_helper_invalid",
            run_id=run_id,
            sku=sku,
            reason=_norm(str(exc)) or type(exc).__name__,
            error_class=type(exc).__name__,
        )
        contract = {
            "run_id": run_id,
            "sku": sku,
            "contract_status": "failed",
            "reason": _norm(str(exc)) or type(exc).__name__,
            "probe_boundary_output_path": _norm(req.get("probe_boundary_output_path", "")),
            "probe_boundary_payload": {},
            "checkpoint_last": "probe_boundary_read_helper_invalid",
            "error_class": type(exc).__name__,
        }
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 1


def _probe_boundary_failure_is_inconclusive_for_read_boundary(
    *,
    failed_reason: str,
    probe_boundary_payload: object,
) -> tuple[bool, str]:
    if _norm(failed_reason) != "subcall_exited_during_probe":
        return False, ""
    payload = probe_boundary_payload if isinstance(probe_boundary_payload, dict) else {}
    subcall_output_path = _norm(payload.get("subcall_output_path", ""))
    if not subcall_output_path:
        return False, ""
    return True, subcall_output_path


def _invoke_market_payload_probe_boundary(
    *,
    run_id: str,
    sku: str,
    subcall_pid: int,
    subcall_output_path: str,
    probe_seconds: float,
    probe_interval_seconds: float,
) -> dict[str, object]:
    helper_dir = H_LIVE_DIR / "tmp_h110_market_payload_probe_boundary"
    helper_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
    input_path = helper_dir / f"in.{token}.json"
    output_path = helper_dir / f"out.{token}.json"
    stdout_path = helper_dir / f"stdout.{token}.log"
    stderr_path = helper_dir / f"stderr.{token}.log"
    req = {
        "run_id": run_id,
        "sku": sku,
        "subcall_pid": str(subcall_pid),
        "subcall_output_path": _norm(subcall_output_path),
        "probe_seconds": f"{float(probe_seconds):.3f}",
        "probe_interval_seconds": f"{float(probe_interval_seconds):.3f}",
    }
    _atomic_write_text(input_path, json.dumps(req, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--market-payload-probe-boundary",
        "--market-payload-probe-boundary-input",
        str(input_path),
        "--market-payload-probe-boundary-output",
        str(output_path),
    )
    helper_timeout_seconds = max(int(float(_norm(req.get("probe_seconds", "")) or "1.0")) + 15, 20)
    spawn_env = os.environ.copy()
    # Keep run-scoped artifacts present even when process boot fails before mode entry.
    _atomic_write_text(stdout_path, "")
    _atomic_write_text(stderr_path, "")
    proc = _popen_hidden(
        cmd,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        env=spawn_env,
    )
    env_min = {
        "PYTHONPATH": _norm(spawn_env.get("PYTHONPATH", "")),
        "PYTHONHOME": _norm(spawn_env.get("PYTHONHOME", "")),
        "PATH_head": _norm(spawn_env.get("PATH", ""))[:512],
        "SYSTEMROOT": _norm(spawn_env.get("SYSTEMROOT", "")),
        "COMSPEC": _norm(spawn_env.get("COMSPEC", "")),
        "H_RUN_ONCE": _norm(spawn_env.get("H_RUN_ONCE", "")),
        "H_PHASE1_PILOT_MODE": _norm(spawn_env.get("H_PHASE1_PILOT_MODE", "")),
    }
    _progress(
        "probe_boundary_process_spawned_full_context",
        run_id=run_id,
        sku=sku,
        child_pid=str(proc.pid),
        cmd=" ".join(cmd),
        cwd=str(ROOT),
        env_min_json=json.dumps(env_min, ensure_ascii=True),
    )
    _progress("probe_boundary_spawn_gap_stmt1_before", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_spawn_gap_stmt1_before", run_id=run_id, sku=sku)
    early_probe_seconds = min(max(_env_float("H110_PROBE_BOUNDARY_BOOT_PROBE_SECONDS", 0.75), 0.5), 1.0)
    _progress("probe_boundary_spawn_gap_stmt1_after", run_id=run_id, sku=sku, early_probe_seconds=f"{early_probe_seconds:.2f}")
    _checkpoint("probe_boundary_spawn_gap_stmt1_after", run_id=run_id, sku=sku)
    _progress("probe_boundary_spawn_gap_stmt2_before", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_spawn_gap_stmt2_before", run_id=run_id, sku=sku)
    early_deadline = time.monotonic() + float(early_probe_seconds)
    _progress("probe_boundary_spawn_gap_stmt2_after", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_spawn_gap_stmt2_after", run_id=run_id, sku=sku)
    _progress("probe_boundary_spawn_gap_stmt3_before", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_spawn_gap_stmt3_before", run_id=run_id, sku=sku)
    first_boot_loop_op = True
    boot_loop_exit_reason = ""
    while True:
        _progress("probe_boundary_boot_loop_cond_eval_start", run_id=run_id, sku=sku)
        _checkpoint("probe_boundary_boot_loop_cond_eval_start", run_id=run_id, sku=sku)
        now_mono = time.monotonic()
        deadline_not_reached = now_mono < early_deadline
        _progress(
            "probe_boundary_boot_loop_deadline_compare_done",
            run_id=run_id,
            sku=sku,
            deadline_not_reached="1" if deadline_not_reached else "0",
        )
        _checkpoint(
            "probe_boundary_boot_loop_deadline_compare_done",
            run_id=run_id,
            sku=sku,
            deadline_not_reached="1" if deadline_not_reached else "0",
        )
        if not deadline_not_reached:
            _progress(
                "probe_boundary_boot_exit_transition_observed",
                run_id=run_id,
                sku=sku,
                exit_type="deadline_reached",
            )
            _checkpoint(
                "probe_boundary_boot_exit_transition_observed",
                run_id=run_id,
                sku=sku,
                exit_type="deadline_reached",
            )
            _progress(
                "probe_boundary_boot_exit_branch_selected",
                run_id=run_id,
                sku=sku,
                exit_type="deadline_reached",
            )
            _checkpoint(
                "probe_boundary_boot_exit_branch_selected",
                run_id=run_id,
                sku=sku,
                exit_type="deadline_reached",
            )
            _progress("probe_boundary_boot_exit_first_stmt_before", run_id=run_id, sku=sku, exit_type="deadline_reached")
            _checkpoint("probe_boundary_boot_exit_first_stmt_before", run_id=run_id, sku=sku, exit_type="deadline_reached")
            boot_loop_exit_reason = "deadline_reached"
            _progress("probe_boundary_boot_exit_first_stmt_after", run_id=run_id, sku=sku, exit_type="deadline_reached")
            _checkpoint("probe_boundary_boot_exit_first_stmt_after", run_id=run_id, sku=sku, exit_type="deadline_reached")
            _progress("probe_boundary_boot_exit_break_before", run_id=run_id, sku=sku, exit_type="deadline_reached")
            _checkpoint("probe_boundary_boot_exit_break_before", run_id=run_id, sku=sku, exit_type="deadline_reached")
            _progress("probe_boundary_boot_loop_cond_decision_made", run_id=run_id, sku=sku, continue_loop="0")
            _checkpoint("probe_boundary_boot_loop_cond_decision_made", run_id=run_id, sku=sku, continue_loop="0")
            break
        _progress("probe_boundary_boot_loop_before_proc_poll", run_id=run_id, sku=sku)
        _checkpoint("probe_boundary_boot_loop_before_proc_poll", run_id=run_id, sku=sku)
        poll_rc = proc.poll()
        _progress(
            "probe_boundary_boot_loop_after_proc_poll",
            run_id=run_id,
            sku=sku,
            poll_is_none="1" if poll_rc is None else "0",
        )
        _checkpoint(
            "probe_boundary_boot_loop_after_proc_poll",
            run_id=run_id,
            sku=sku,
            poll_is_none="1" if poll_rc is None else "0",
        )
        continue_loop = poll_rc is None
        _progress(
            "probe_boundary_boot_loop_cond_decision_made",
            run_id=run_id,
            sku=sku,
            continue_loop="1" if continue_loop else "0",
        )
        _checkpoint(
            "probe_boundary_boot_loop_cond_decision_made",
            run_id=run_id,
            sku=sku,
            continue_loop="1" if continue_loop else "0",
        )
        if not continue_loop:
            _progress(
                "probe_boundary_boot_exit_transition_observed",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            _checkpoint(
                "probe_boundary_boot_exit_transition_observed",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            _progress(
                "probe_boundary_boot_exit_branch_selected",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            _checkpoint(
                "probe_boundary_boot_exit_branch_selected",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            _progress(
                "probe_boundary_boot_exit_first_stmt_before",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            _checkpoint(
                "probe_boundary_boot_exit_first_stmt_before",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            boot_loop_exit_reason = "continue_loop_false"
            _progress(
                "probe_boundary_boot_exit_first_stmt_after",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            _checkpoint(
                "probe_boundary_boot_exit_first_stmt_after",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            _progress(
                "probe_boundary_boot_exit_break_before",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            _checkpoint(
                "probe_boundary_boot_exit_break_before",
                run_id=run_id,
                sku=sku,
                exit_type="continue_loop_false",
            )
            break
        if first_boot_loop_op:
            _progress("probe_boundary_boot_loop_first_op_before", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_first_op_before", run_id=run_id, sku=sku)
            time.sleep(0.05)
            _progress("probe_boundary_boot_loop_first_op_after", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_first_op_after", run_id=run_id, sku=sku)
            _progress("probe_boundary_boot_loop_true_branch_before_flag_flip", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_true_branch_before_flag_flip", run_id=run_id, sku=sku)
            first_boot_loop_op = False
            _progress("probe_boundary_boot_loop_true_branch_after_flag_flip", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_true_branch_after_flag_flip", run_id=run_id, sku=sku)
            _progress("probe_boundary_boot_loop_true_branch_back_edge", run_id=run_id, sku=sku, branch="first")
            _checkpoint("probe_boundary_boot_loop_true_branch_back_edge", run_id=run_id, sku=sku, branch="first")
        else:
            _progress("probe_boundary_boot_loop_true_branch_else_before_sleep", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_true_branch_else_before_sleep", run_id=run_id, sku=sku)
            _progress("probe_boundary_boot_loop_else_sleep_call_entry", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_else_sleep_call_entry", run_id=run_id, sku=sku)
            time.sleep(0.05)
            _progress("probe_boundary_boot_loop_else_sleep_call_return", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_else_sleep_call_return", run_id=run_id, sku=sku)
            _progress("probe_boundary_boot_loop_true_branch_else_after_sleep", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_true_branch_else_after_sleep", run_id=run_id, sku=sku)
            _progress("probe_boundary_boot_loop_else_post_sleep_before_back_edge", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_else_post_sleep_before_back_edge", run_id=run_id, sku=sku)
            _progress("probe_boundary_boot_loop_true_branch_back_edge", run_id=run_id, sku=sku, branch="else")
            _checkpoint("probe_boundary_boot_loop_true_branch_back_edge", run_id=run_id, sku=sku, branch="else")
            _progress("probe_boundary_boot_loop_else_post_sleep_after_back_edge", run_id=run_id, sku=sku)
            _checkpoint("probe_boundary_boot_loop_else_post_sleep_after_back_edge", run_id=run_id, sku=sku)
    _progress("probe_boundary_boot_loop_exit", run_id=run_id, sku=sku, exit_type=boot_loop_exit_reason or "unknown")
    _checkpoint("probe_boundary_boot_loop_exit", run_id=run_id, sku=sku, exit_type=boot_loop_exit_reason or "unknown")
    _progress("probe_boundary_spawn_gap_stmt3_after", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_spawn_gap_stmt3_after", run_id=run_id, sku=sku)
    _progress("probe_boundary_spawn_gap_stmt4_before", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_spawn_gap_stmt4_before", run_id=run_id, sku=sku)
    if proc.poll() is not None:
        with contextlib.suppress(Exception):
            stdout_bytes, stderr_bytes = proc.communicate(timeout=0.5)
        stdout_bytes = stdout_bytes if "stdout_bytes" in locals() and isinstance(stdout_bytes, (bytes, bytearray)) else b""
        stderr_bytes = stderr_bytes if "stderr_bytes" in locals() and isinstance(stderr_bytes, (bytes, bytearray)) else b""
        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        _atomic_write_text(stdout_path, stdout_text)
        _atomic_write_text(stderr_path, stderr_text)
        rc_text = str(proc.returncode if proc.returncode is not None else "")
        process_exit_artifact = helper_dir / f"process_exit.{run_id}.json"
        process_exit_payload = {
            "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_id": run_id,
            "sku": sku,
            "child_pid": str(proc.pid),
            "rc": rc_text,
            "args": cmd,
            "cwd": str(ROOT),
            "input_path": str(input_path),
            "output_path": str(output_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "stdout": stdout_text,
            "stderr": stderr_text,
            "env_min": env_min,
        }
        _atomic_write_text(process_exit_artifact, json.dumps(process_exit_payload, ensure_ascii=True) + "\n")
        _progress(
            "probe_boundary_process_died_early",
            run_id=run_id,
            sku=sku,
            child_pid=str(proc.pid),
            rc=rc_text,
            stdout_text=stdout_text[-400:],
            stderr_text=stderr_text[-400:],
            process_exit_artifact=str(process_exit_artifact),
            probe_seconds=f"{early_probe_seconds:.2f}",
        )
    _progress("probe_boundary_spawn_gap_stmt4_after", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_spawn_gap_stmt4_after", run_id=run_id, sku=sku)
    _progress("probe_boundary_post_loop_before_spawned", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_loop_before_spawned", run_id=run_id, sku=sku)
    _progress(
        "market_payload_probe_boundary_spawned",
        run_id=run_id,
        sku=sku,
        child_pid=str(proc.pid),
        input_path=str(input_path),
        output_path=str(output_path),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        timeout_seconds=str(helper_timeout_seconds),
    )
    _progress(
        "probe_boundary_post_spawn_micro_after_spawned",
        run_id=run_id,
        sku=sku,
    )
    _checkpoint(
        "probe_boundary_post_spawn_micro_after_spawned",
        run_id=run_id,
        sku=sku,
    )
    _progress("probe_boundary_post_spawn_seg_paths_before", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_spawn_seg_paths_before", run_id=run_id, sku=sku)
    read_helper_input_path = helper_dir / f"read.in.{token}.json"
    read_helper_output_path = helper_dir / f"read.out.{token}.json"
    read_helper_stdout_path = helper_dir / f"read.stdout.{token}.log"
    read_helper_stderr_path = helper_dir / f"read.stderr.{token}.log"
    _progress("probe_boundary_post_spawn_seg_paths_after", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_spawn_seg_paths_after", run_id=run_id, sku=sku)
    _progress(
        "probe_boundary_post_spawn_micro_paths_prepped",
        run_id=run_id,
        sku=sku,
        read_helper_input_path=str(read_helper_input_path),
        read_helper_output_path=str(read_helper_output_path),
    )
    _checkpoint(
        "probe_boundary_post_spawn_micro_paths_prepped",
        run_id=run_id,
        sku=sku,
    )
    _progress("probe_boundary_post_spawn_seg_req_before", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_spawn_seg_req_before", run_id=run_id, sku=sku)
    read_helper_req = {
        "run_id": run_id,
        "sku": sku,
        "probe_boundary_pid": str(proc.pid),
        "probe_boundary_output_path": str(output_path),
        "timeout_seconds": str(helper_timeout_seconds),
    }
    _progress("probe_boundary_post_spawn_seg_req_after", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_spawn_seg_req_after", run_id=run_id, sku=sku)
    _progress(
        "probe_boundary_post_spawn_micro_req_built",
        run_id=run_id,
        sku=sku,
    )
    _checkpoint(
        "probe_boundary_post_spawn_micro_req_built",
        run_id=run_id,
        sku=sku,
    )
    _progress("probe_boundary_post_spawn_seg_req_write_before", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_spawn_seg_req_write_before", run_id=run_id, sku=sku)
    _atomic_write_text(read_helper_input_path, json.dumps(read_helper_req, ensure_ascii=True) + "\n")
    _progress("probe_boundary_post_spawn_seg_req_write_after", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_spawn_seg_req_write_after", run_id=run_id, sku=sku)
    _progress(
        "probe_boundary_post_spawn_micro_req_written",
        run_id=run_id,
        sku=sku,
        read_helper_input_path=str(read_helper_input_path),
    )
    _checkpoint(
        "probe_boundary_post_spawn_micro_req_written",
        run_id=run_id,
        sku=sku,
    )
    _progress("probe_boundary_post_spawn_seg_cmd_before", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_spawn_seg_cmd_before", run_id=run_id, sku=sku)
    read_cmd = _self_python_cmd(
        "--market-payload-probe-boundary-read-helper",
        "--market-payload-probe-boundary-read-input",
        str(read_helper_input_path),
        "--market-payload-probe-boundary-read-output",
        str(read_helper_output_path),
    )
    _progress("probe_boundary_post_spawn_seg_cmd_after", run_id=run_id, sku=sku)
    _checkpoint("probe_boundary_post_spawn_seg_cmd_after", run_id=run_id, sku=sku)
    _progress(
        "probe_boundary_post_spawn_micro_read_cmd_built",
        run_id=run_id,
        sku=sku,
        argc=str(len(read_cmd)),
    )
    _checkpoint(
        "probe_boundary_post_spawn_micro_read_cmd_built",
        run_id=run_id,
        sku=sku,
    )
    _progress(
        "probe_boundary_pre_readiness_before_read_helper_spawn",
        run_id=run_id,
        sku=sku,
        input_path=str(read_helper_input_path),
        output_path=str(read_helper_output_path),
    )
    _checkpoint(
        "probe_boundary_pre_readiness_before_read_helper_spawn",
        run_id=run_id,
        sku=sku,
    )
    with read_helper_stdout_path.open("wb") as out_fh, read_helper_stderr_path.open("wb") as err_fh:
        read_proc = _popen_hidden(
            read_cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            close_fds=True,
            env=os.environ.copy(),
        )
    _progress(
        "probe_boundary_pre_readiness_after_read_helper_spawn",
        run_id=run_id,
        sku=sku,
        child_pid=str(read_proc.pid),
    )
    _checkpoint(
        "probe_boundary_pre_readiness_after_read_helper_spawn",
        run_id=run_id,
        sku=sku,
    )
    read_timeout_seconds = max(helper_timeout_seconds + 20, 30)
    _progress(
        "probe_boundary_read_helper_spawned",
        run_id=run_id,
        sku=sku,
        child_pid=str(read_proc.pid),
        input_path=str(read_helper_input_path),
        output_path=str(read_helper_output_path),
        stdout_path=str(read_helper_stdout_path),
        stderr_path=str(read_helper_stderr_path),
        timeout_seconds=str(read_timeout_seconds),
    )
    try:
        _progress(
            "probe_boundary_inner_before_first_call",
            run_id=run_id,
            sku=sku,
            first_call="probe_boundary_output_readiness_poll",
            child_pid=str(read_proc.pid),
        )
        _checkpoint(
            "probe_boundary_inner_before_first_call",
            run_id=run_id,
            sku=sku,
        )
        output_ready = False
        readiness_deadline = time.monotonic() + float(read_timeout_seconds)
        _progress(
            "probe_boundary_pre_readiness_before_loop_entry",
            run_id=run_id,
            sku=sku,
            timeout_seconds=str(read_timeout_seconds),
            output_path=str(read_helper_output_path),
        )
        _checkpoint(
            "probe_boundary_pre_readiness_before_loop_entry",
            run_id=run_id,
            sku=sku,
        )
        loop_iter = 0
        while time.monotonic() < readiness_deadline:
            loop_iter += 1
            if loop_iter == 1:
                _progress(
                    "probe_boundary_pre_readiness_after_first_loop_iteration",
                    run_id=run_id,
                    sku=sku,
                    output_exists="1" if read_helper_output_path.exists() else "0",
                )
                _checkpoint(
                    "probe_boundary_pre_readiness_after_first_loop_iteration",
                    run_id=run_id,
                    sku=sku,
                )
            if read_helper_output_path.exists():
                output_ready = True
                break
            time.sleep(0.10)
        if not output_ready:
            with contextlib.suppress(Exception):
                read_proc.terminate()
            if read_proc.poll() is None:
                with contextlib.suppress(Exception):
                    read_proc.kill()
            _progress(
                "probe_boundary_read_helper_failed",
                run_id=run_id,
                sku=sku,
                reason=f"output_readiness_timeout_after_{read_timeout_seconds}s",
            )
            raise RuntimeError(f"probe_boundary_output_readiness_timeout_after_{read_timeout_seconds}s")
        read_worker_rc_raw = read_proc.poll()
        read_worker_rc_text = ""
        if isinstance(read_worker_rc_raw, int):
            read_worker_rc_text = str(read_worker_rc_raw)
        _progress(
            "probe_boundary_inner_after_first_call",
            run_id=run_id,
            sku=sku,
            first_call="probe_boundary_output_readiness_poll",
            worker_rc=read_worker_rc_text,
            output_ready="1",
        )
        _checkpoint(
            "probe_boundary_inner_after_first_call",
            run_id=run_id,
            sku=sku,
        )
        _progress(
            "probe_boundary_inner_before_return_use",
            run_id=run_id,
            sku=sku,
            worker_rc=read_worker_rc_text,
            output_path=str(read_helper_output_path),
        )
        _checkpoint(
            "probe_boundary_inner_before_return_use",
            run_id=run_id,
            sku=sku,
        )
        if not read_helper_output_path.exists():
            _progress("probe_boundary_read_helper_invalid", run_id=run_id, sku=sku, reason="missing_output")
            raise RuntimeError("probe_boundary_read_output_missing")
        _progress(
            "probe_boundary_inner_after_return_use",
            run_id=run_id,
            sku=sku,
            worker_rc=read_worker_rc_text,
            output_path=str(read_helper_output_path),
        )
        _checkpoint(
            "probe_boundary_inner_after_return_use",
            run_id=run_id,
            sku=sku,
        )
    except BaseException as exc:
        inner_reason = _norm(str(exc)) or type(exc).__name__
        _progress(
            "probe_boundary_inner_failed",
            run_id=run_id,
            sku=sku,
            reason=inner_reason[:240],
            error_class=type(exc).__name__,
        )
        _checkpoint(
            "probe_boundary_inner_failed",
            run_id=run_id,
            sku=sku,
        )
        if inner_reason.startswith("completion_convergence_failed:probe_boundary_inner:"):
            raise RuntimeError(inner_reason[:240]) from exc
        raise RuntimeError(f"completion_convergence_failed:probe_boundary_inner:{inner_reason[:180]}") from exc
    _progress(
        "probe_boundary_read_helper_read",
        run_id=run_id,
        sku=sku,
        worker_rc=read_worker_rc_text,
        output_path=str(read_helper_output_path),
    )
    try:
        read_contract = json.loads(read_helper_output_path.read_text(encoding="utf-8"))
    except Exception:
        _progress("probe_boundary_read_helper_invalid", run_id=run_id, sku=sku, reason="invalid_json")
        raise RuntimeError("completion_convergence_failed:probe_boundary_read_invalid")
    if not isinstance(read_contract, dict):
        _progress("probe_boundary_read_helper_invalid", run_id=run_id, sku=sku, reason="contract_not_object")
        raise RuntimeError("completion_convergence_failed:probe_boundary_read_invalid")
    contract_run_id = _norm(read_contract.get("run_id", ""))
    contract_sku = _norm(read_contract.get("sku", "")).upper()
    if contract_run_id != run_id or contract_sku != sku:
        _progress("probe_boundary_read_helper_invalid", run_id=run_id, sku=sku, reason="identity_mismatch")
        raise RuntimeError("completion_convergence_failed:probe_boundary_read_invalid")
    contract_status = _norm(read_contract.get("contract_status", "")).lower()
    probe_boundary_output_path = _norm(read_contract.get("probe_boundary_output_path", ""))
    probe_boundary_payload = read_contract.get("probe_boundary_payload", {})
    if contract_status not in {"ok", "failed"}:
        _progress("probe_boundary_read_helper_invalid", run_id=run_id, sku=sku, reason="status_invalid")
        raise RuntimeError("completion_convergence_failed:probe_boundary_read_invalid")
    if not probe_boundary_output_path:
        _progress("probe_boundary_read_helper_invalid", run_id=run_id, sku=sku, reason="missing_output_path")
        raise RuntimeError("completion_convergence_failed:probe_boundary_read_invalid")
    if not isinstance(probe_boundary_payload, dict):
        _progress("probe_boundary_read_helper_invalid", run_id=run_id, sku=sku, reason="payload_not_object")
        raise RuntimeError("completion_convergence_failed:probe_boundary_read_invalid")
    if read_worker_rc_text and read_worker_rc_text != "0" and contract_status == "ok":
        _progress("probe_boundary_read_helper_invalid", run_id=run_id, sku=sku, reason="worker_rc_mismatch")
        raise RuntimeError("completion_convergence_failed:probe_boundary_read_invalid")
    if contract_status != "ok":
        failed_reason = _norm(read_contract.get("reason", "")) or "probe_boundary_read_failed"
        # Treat early probe "child exited during probe" as inconclusive and defer
        # final truth to the read-boundary contract, which has a full timeout window.
        is_inconclusive, probe_payload_subcall_path = _probe_boundary_failure_is_inconclusive_for_read_boundary(
            failed_reason=failed_reason,
            probe_boundary_payload=probe_boundary_payload,
        )
        if is_inconclusive:
            _progress(
                "probe_boundary_read_helper_inconclusive_continue",
                run_id=run_id,
                sku=sku,
                reason=failed_reason,
                checkpoint_last=_norm(read_contract.get("checkpoint_last", "")),
                error_class=_norm(read_contract.get("error_class", "")),
                worker_rc=read_worker_rc_text,
                subcall_output_path=probe_payload_subcall_path,
            )
            if isinstance(probe_boundary_payload, dict):
                return probe_boundary_payload
            return {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": failed_reason,
                "subcall_pid": "",
                "subcall_output_path": probe_payload_subcall_path,
                "observed_rc": "",
                "checkpoint_last": "market_payload_probe_boundary_inconclusive",
                "error_class": _norm(read_contract.get("error_class", "")),
            }
        _progress(
            "probe_boundary_read_helper_failed",
            run_id=run_id,
            sku=sku,
            reason=failed_reason,
            checkpoint_last=_norm(read_contract.get("checkpoint_last", "")),
            error_class=_norm(read_contract.get("error_class", "")),
            worker_rc=read_worker_rc_text,
        )
        raise RuntimeError(f"completion_convergence_failed:probe_boundary_read_failed:{failed_reason}")
    _progress(
        "probe_boundary_read_helper_valid",
        run_id=run_id,
        sku=sku,
        checkpoint_last=_norm(read_contract.get("checkpoint_last", "")),
        error_class=_norm(read_contract.get("error_class", "")),
        worker_rc=read_worker_rc_text,
    )
    _progress(
        "market_payload_probe_boundary_read",
        run_id=run_id,
        sku=sku,
        worker_rc=read_worker_rc_text,
        output_path=probe_boundary_output_path,
    )
    return probe_boundary_payload


def _run_market_payload_read_boundary_mode(*, input_path: Path, output_path: Path) -> int:
    req: dict[str, object] = {}
    run_id = ""
    sku = ""
    try:
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req_raw, dict):
            raise RuntimeError("input_json_not_object")
        req = req_raw
        run_id = _norm(req.get("run_id", ""))
        sku = _norm(req.get("sku", "")).upper()
        subcall_output_path = Path(_norm(req.get("subcall_output_path", "")))
        subcall_pid = int(_norm(req.get("subcall_pid", "")) or "0")
        owner_pid = int(_norm(req.get("owner_pid", "")) or "0")
        timeout_seconds = max(int(float(_norm(req.get("timeout_seconds", "")) or "90")), 20)
        checkpoint_path_raw = _norm(req.get("checkpoint_path", ""))
        checkpoint_path = Path(checkpoint_path_raw) if checkpoint_path_raw else None
        subcall_stderr_path_raw = _norm(req.get("subcall_stderr_path", ""))
        subcall_stdout_path_raw = _norm(req.get("subcall_stdout_path", ""))
        subcall_stderr_path = Path(subcall_stderr_path_raw) if subcall_stderr_path_raw else None
        subcall_stdout_path = Path(subcall_stdout_path_raw) if subcall_stdout_path_raw else None
        if not str(subcall_output_path):
            raise RuntimeError("missing_subcall_output_path")

        def _emit_wait_returned_handoff_checkpoint(*, worker_rc: str, output_exists: str) -> None:
            if checkpoint_path is None:
                return
            if _norm(worker_rc) != "0":
                return
            if _norm(output_exists).lower() not in {"1", "true", "yes"}:
                return
            payload = {
                "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "run_id": run_id,
                "pid": str(os.getpid()),
                "checkpoint": "owner_post_subcall_read_boundary_wait_returned",
                "sku": sku,
                "worker_rc": "0",
                "output_exists": "1",
            }
            with contextlib.suppress(Exception):
                _atomic_write_text(checkpoint_path, json.dumps(payload, ensure_ascii=True) + "\n")

        def _read_tail(path: Path | None, *, max_chars: int = 8192) -> str:
            if path is None or (not path.exists()):
                return ""
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return ""
            return raw[-max_chars:]

        def _has_interrupt_marker() -> bool:
            stderr_tail = _read_tail(subcall_stderr_path)
            stdout_tail = _read_tail(subcall_stdout_path)
            return ("KeyboardInterrupt" in stderr_tail) or ("KeyboardInterrupt" in stdout_tail)

        def _emit_interrupt_resolved_contract() -> int:
            asin = _norm(req.get("asin", ""))
            marketplace_id = _norm(req.get("marketplace_id", ""))
            seller_id = _norm(req.get("seller_id", ""))
            listing_row_raw = req.get("listing_row", {})
            if not isinstance(listing_row_raw, dict):
                raise RuntimeError("listing_row_not_object")
            if not (asin and marketplace_id and seller_id):
                raise RuntimeError("missing_inline_fallback_context")
            listing_row_norm = {str(k): _norm(v) for k, v in listing_row_raw.items()}
            payload, listings_observed_price = _phase1_market_payload_from_snapshots(
                sku=sku,
                asin=asin,
                marketplace_id=marketplace_id,
                our_seller_id=seller_id,
                listing_row=listing_row_norm,
            )
            boundary_contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "ok",
                "reason": "inline_fallback_after_subcall_interrupt_missing_output",
                "subcall_output_path": str(subcall_output_path),
                "parsed_payload": payload if isinstance(payload, dict) else {},
                "listings_observed_price": _norm(listings_observed_price),
                "checkpoint_last": "market_payload_read_boundary_inline_fallback_after_subcall_interrupt_missing_output",
                "error_class": "",
            }
            _atomic_write_text(output_path, json.dumps(boundary_contract, ensure_ascii=True) + "\n")
            _emit_wait_returned_handoff_checkpoint(worker_rc="0", output_exists="1")
            return 0

        deadline = time.time() + float(timeout_seconds)
        owner_loss_reason = ""
        while time.time() < deadline:
            if subcall_output_path.exists():
                break
            if owner_pid > 0 and (not _pid_alive(owner_pid)):
                owner_loss_reason = f"owner_pid_{owner_pid}_not_alive"
                _progress(
                    "market_payload_read_boundary_owner_lost",
                    run_id=run_id,
                    sku=sku,
                    owner_pid=str(owner_pid),
                    subcall_pid=str(subcall_pid) if subcall_pid > 0 else "",
                    reason=owner_loss_reason,
                )
                break
            if subcall_pid > 0 and (not _pid_alive(subcall_pid)):
                interrupt_fallback_enabled = _to_bool(
                    os.environ.get("H110_READ_BOUNDARY_MISSING_OUTPUT_INTERRUPT_FALLBACK_ENABLED", "1"),
                    default=True,
                )
                if interrupt_fallback_enabled and _has_interrupt_marker():
                    _progress(
                        "market_payload_read_boundary_missing_output_interrupt_fallback",
                        run_id=run_id,
                        sku=sku,
                        reason="subcall_keyboard_interrupt_without_output",
                        subcall_stderr_path=subcall_stderr_path_raw,
                        subcall_stdout_path=subcall_stdout_path_raw,
                    )
                    try:
                        rc = _emit_interrupt_resolved_contract()
                        _progress(
                            "market_payload_read_boundary_missing_output_interrupt_fallback_resolved",
                            run_id=run_id,
                            sku=sku,
                            checkpoint_last="market_payload_read_boundary_inline_fallback_after_subcall_interrupt_missing_output",
                        )
                        return rc
                    except Exception as fallback_exc:
                        _progress(
                            "market_payload_read_boundary_missing_output_interrupt_fallback_failed",
                            run_id=run_id,
                            sku=sku,
                            error_type=type(fallback_exc).__name__,
                            reason=_norm(str(fallback_exc))[:240],
                        )
                # Give a short grace period for filesystem flush after child exit.
                if (time.time() + 0.5) >= deadline:
                    break
            time.sleep(0.2)

        if owner_loss_reason:
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": f"owner_lost_before_boundary_settle:{owner_loss_reason}",
                "subcall_output_path": str(subcall_output_path),
                "parsed_payload": {},
                "listings_observed_price": "",
                "checkpoint_last": "market_payload_read_boundary_owner_lost",
                "error_class": "ParentLossError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1

        if not subcall_output_path.exists():
            contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": f"timeout_after_{timeout_seconds}s",
                "subcall_output_path": str(subcall_output_path),
                "parsed_payload": {},
                "listings_observed_price": "",
                "checkpoint_last": "market_payload_read_boundary_failed",
                "error_class": "TimeoutError",
            }
            _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
            return 1

        contract_raw = json.loads(subcall_output_path.read_text(encoding="utf-8"))
        if not isinstance(contract_raw, dict):
            raise RuntimeError("subcall_contract_not_object")
        contract_run_id = _norm(contract_raw.get("run_id", ""))
        contract_sku = _norm(contract_raw.get("sku", "")).upper()
        if contract_run_id != run_id or contract_sku != sku:
            raise RuntimeError("identity_mismatch")
        status = _norm(contract_raw.get("status", "")).lower()
        reason = _norm(contract_raw.get("reason", ""))
        payload = contract_raw.get("payload", {})
        if status == "ok" and not isinstance(payload, dict):
            raise RuntimeError("payload_not_object")
        if status != "ok":
            boundary_contract = {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "failed",
                "reason": reason or "status_not_ok",
                "subcall_output_path": str(subcall_output_path),
                "parsed_payload": payload if isinstance(payload, dict) else {},
                "listings_observed_price": _norm(contract_raw.get("listings_observed_price", "")),
                "checkpoint_last": _norm(contract_raw.get("checkpoint_last", "")) or "market_payload_read_boundary_failed",
                "error_class": _norm(contract_raw.get("error_class", "")) or "RuntimeError",
            }
            _atomic_write_text(output_path, json.dumps(boundary_contract, ensure_ascii=True) + "\n")
            return 1

        boundary_contract = {
            "run_id": run_id,
            "sku": sku,
            "contract_status": "ok",
            "reason": "ok",
            "subcall_output_path": str(subcall_output_path),
            "parsed_payload": payload,
            "listings_observed_price": _norm(contract_raw.get("listings_observed_price", "")),
            "checkpoint_last": _norm(contract_raw.get("checkpoint_last", "")) or "market_payload_read_boundary_valid",
            "error_class": _norm(contract_raw.get("error_class", "")),
        }
        _atomic_write_text(output_path, json.dumps(boundary_contract, ensure_ascii=True) + "\n")
        _emit_wait_returned_handoff_checkpoint(worker_rc="0", output_exists="1")
        return 0
    except BaseException as exc:
        fallback_output_path = _norm(req.get("subcall_output_path", ""))
        contract = {
            "run_id": run_id,
            "sku": sku,
            "contract_status": "failed",
            "reason": _norm(str(exc)) or type(exc).__name__,
            "subcall_output_path": fallback_output_path,
            "parsed_payload": {},
            "listings_observed_price": "",
            "checkpoint_last": "market_payload_read_boundary_invalid",
            "error_class": type(exc).__name__,
        }
        _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
        return 1


def _invoke_market_payload_read_boundary(
    *,
    run_id: str,
    sku: str,
    subcall_spawn_contract: dict[str, object],
) -> dict[str, object]:
    def _is_interrupt_contract(contract: dict[str, object], worker_rc_text: str) -> bool:
        reason_norm = _norm(contract.get("reason", "")).lower()
        error_class_norm = _norm(contract.get("error_class", "")).lower()
        worker_rc_norm = _norm(worker_rc_text)
        if reason_norm in {"130", "keyboardinterrupt", "keyboard_interrupt"}:
            return True
        if error_class_norm in {"systemexit", "keyboardinterrupt"} and (reason_norm == "130" or worker_rc_norm in {"130", ""}):
            return True
        return False

    def _inline_market_payload_fallback() -> dict[str, object]:
        asin = _norm(subcall_spawn_contract.get("asin", ""))
        marketplace_id = _norm(subcall_spawn_contract.get("marketplace_id", ""))
        seller_id = _norm(subcall_spawn_contract.get("seller_id", ""))
        listing_row_raw = subcall_spawn_contract.get("listing_row", {})
        if not (asin and marketplace_id and seller_id and isinstance(listing_row_raw, dict)):
            raise RuntimeError("missing_inline_fallback_context")
        listing_row_norm = {str(k): _norm(v) for k, v in listing_row_raw.items()}
        payload, listings_observed_price = _phase1_market_payload_from_snapshots(
            sku=sku,
            asin=asin,
            marketplace_id=marketplace_id,
            our_seller_id=seller_id,
            listing_row=listing_row_norm,
        )
        return {
            "run_id": run_id,
            "sku": sku,
            "contract_status": "ok",
            "reason": "inline_fallback_after_interrupt",
            "subcall_output_path": _norm(subcall_spawn_contract.get("subcall_output_path", "")),
            "parsed_payload": payload if isinstance(payload, dict) else {},
            "listings_observed_price": _norm(listings_observed_price),
            "checkpoint_last": "market_payload_read_boundary_inline_fallback_after_interrupt",
            "error_class": "",
        }

    def _try_fastpath_subcall_handoff(*, wait_seconds: float) -> dict[str, object] | None:
        subcall_output_path_raw = _norm(subcall_spawn_contract.get("subcall_output_path", ""))
        if not subcall_output_path_raw:
            return None
        subcall_output_path = Path(subcall_output_path_raw)
        deadline = time.time() + max(wait_seconds, 0.0)
        while time.time() < deadline:
            if not subcall_output_path.exists():
                time.sleep(0.1)
                continue
            try:
                subcall_contract_raw = json.loads(subcall_output_path.read_text(encoding="utf-8"))
            except Exception:
                # Subcall may still be flushing output; keep polling until deadline.
                time.sleep(0.1)
                continue
            if not isinstance(subcall_contract_raw, dict):
                time.sleep(0.1)
                continue
            contract_run_id = _norm(subcall_contract_raw.get("run_id", ""))
            contract_sku = _norm(subcall_contract_raw.get("sku", "")).upper()
            if contract_run_id != run_id or contract_sku != sku:
                return None
            contract_status = _norm(subcall_contract_raw.get("status", "")).lower()
            payload = subcall_contract_raw.get("payload", {})
            if contract_status != "ok" or not isinstance(payload, dict):
                return None
            return {
                "run_id": run_id,
                "sku": sku,
                "contract_status": "ok",
                "reason": "ok",
                "subcall_output_path": str(subcall_output_path),
                "parsed_payload": payload,
                "listings_observed_price": _norm(subcall_contract_raw.get("listings_observed_price", "")),
                "checkpoint_last": _norm(subcall_contract_raw.get("checkpoint_last", "")) or "market_payload_read_boundary_valid",
                "error_class": _norm(subcall_contract_raw.get("error_class", "")),
            }
        return None

    helper_dir = H_LIVE_DIR / "tmp_h110_market_payload_read_boundary"
    helper_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
    input_path = helper_dir / f"in.{token}.json"
    output_path = helper_dir / f"out.{token}.json"
    req = {
        "run_id": run_id,
        "sku": sku,
        "owner_pid": str(os.getpid()),
        "subcall_output_path": _norm(subcall_spawn_contract.get("subcall_output_path", "")),
        "subcall_pid": _norm(subcall_spawn_contract.get("subcall_pid", "")),
        "timeout_seconds": _norm(subcall_spawn_contract.get("timeout_seconds", "")),
        "checkpoint_path": str(_COMPLETION_CHECKPOINT_STATE_PATH) if _COMPLETION_CHECKPOINT_STATE_PATH is not None else "",
        "asin": _norm(subcall_spawn_contract.get("asin", "")),
        "marketplace_id": _norm(subcall_spawn_contract.get("marketplace_id", "")),
        "seller_id": _norm(subcall_spawn_contract.get("seller_id", "")),
        "listing_row": subcall_spawn_contract.get("listing_row", {}),
        "subcall_stderr_path": _norm(subcall_spawn_contract.get("subcall_stderr_path", "")),
        "subcall_stdout_path": _norm(subcall_spawn_contract.get("subcall_stdout_path", "")),
    }
    _atomic_write_text(input_path, json.dumps(req, ensure_ascii=True) + "\n")
    # Floor the fast-path window above the observed live jitter so valid
    # subcall output does not miss fast-path and fall into legacy wait-enter.
    configured_fastpath_wait_seconds = _env_float("H110_READ_BOUNDARY_FASTPATH_WAIT_SECONDS", 4.0)
    fastpath_wait_seconds = max(configured_fastpath_wait_seconds, 4.0, 0.0)
    fastpath_contract = _try_fastpath_subcall_handoff(wait_seconds=fastpath_wait_seconds)
    if isinstance(fastpath_contract, dict):
        _atomic_write_text(output_path, json.dumps(fastpath_contract, ensure_ascii=True) + "\n")
        _progress(
            "market_payload_read_boundary_fastpath_emitted",
            run_id=run_id,
            sku=sku,
            output_path=str(output_path),
            wait_seconds=f"{fastpath_wait_seconds:.2f}",
            checkpoint_last=_norm(fastpath_contract.get("checkpoint_last", "")),
        )
        _checkpoint(
            "owner_post_subcall_read_boundary_wait_returned",
            run_id=run_id,
            sku=sku,
            worker_rc="0",
            output_exists="1",
        )
        return fastpath_contract
    cmd = _self_python_cmd(
        "--market-payload-read-boundary",
        "--market-payload-read-boundary-input",
        str(input_path),
        "--market-payload-read-boundary-output",
        str(output_path),
    )
    # Keep owner wait aligned to the read-boundary timeout window so the
    # authoritative wait-returned checkpoint can be emitted before external
    # isolation wrapper teardown.
    helper_timeout_seconds = max(int(float(_norm(req.get("timeout_seconds", "")) or "90")), 30)
    _owner_provenance_capture_start(
        run_id=run_id,
        sku=sku,
        owner_pid=str(os.getpid()),
        subcall_pid=_norm(req.get("subcall_pid", "")),
        helper_pid="subprocess",
        timeout_seconds=str(helper_timeout_seconds),
    )
    _progress(
        "market_payload_read_boundary_inline_start",
        run_id=run_id,
        sku=sku,
        input_path=str(input_path),
        output_path=str(output_path),
        timeout_seconds=str(helper_timeout_seconds),
    )
    _owner_wait_mark_enter(
        run_id=run_id,
        sku=sku,
        subcall_pid=_norm(req.get("subcall_pid", "")),
        helper_pid="subprocess",
        timeout_seconds=helper_timeout_seconds,
    )
    _checkpoint(
        "owner_post_subcall_read_boundary_wait_enter",
        run_id=run_id,
        sku=sku,
        timeout_seconds=str(helper_timeout_seconds),
    )
    # If fast-path miss was timing or partial-write related, do one bounded
    # post-wait-enter handoff poll before falling to legacy helper loop.
    post_wait_handoff_wait_seconds = min(
        max(_env_float("H110_READ_BOUNDARY_POST_WAIT_HANDOFF_SECONDS", 2.0), 0.0),
        max(float(helper_timeout_seconds), 0.0),
    )
    ignored_signal_handlers: list[tuple[object, object]] = []
    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig_obj = getattr(signal, sig_name, None)
        if sig_obj is None:
            continue
        try:
            previous = signal.getsignal(sig_obj)
            signal.signal(sig_obj, signal.SIG_IGN)
            ignored_signal_handlers.append((sig_obj, previous))
        except BaseException:
            continue
    worker_rc = ""
    try:
        post_wait_handoff_contract = _try_fastpath_subcall_handoff(wait_seconds=post_wait_handoff_wait_seconds)
        if isinstance(post_wait_handoff_contract, dict):
            _atomic_write_text(output_path, json.dumps(post_wait_handoff_contract, ensure_ascii=True) + "\n")
            worker_rc = "0"
            _progress(
                "market_payload_read_boundary_post_wait_handoff_emitted",
                run_id=run_id,
                sku=sku,
                output_path=str(output_path),
                wait_seconds=f"{post_wait_handoff_wait_seconds:.2f}",
                checkpoint_last=_norm(post_wait_handoff_contract.get("checkpoint_last", "")),
            )
        else:
            creation_flags = 0
            creation_flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            creation_flags |= int(getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
            proc: subprocess.Popen[str] | None = None
            inline_boundary_fallback = False
            try:
                proc = _popen_hidden(
                    cmd,
                    cwd=str(ROOT),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    creationflags=creation_flags,
                    env=os.environ.copy(),
                )
            except PermissionError as exc:
                if creation_flags and os.name == "nt":
                    _progress(
                        "market_payload_read_boundary_creationflags_fallback",
                        run_id=run_id,
                        sku=sku,
                        reason=f"PermissionError:{exc}",
                        creationflags=str(creation_flags),
                    )
                    try:
                        proc = _popen_hidden(
                            cmd,
                            cwd=str(ROOT),
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            close_fds=True,
                            creationflags=0,
                            env=os.environ.copy(),
                        )
                    except PermissionError as inner_exc:
                        _progress(
                            "market_payload_read_boundary_spawn_inline_fallback",
                            run_id=run_id,
                            sku=sku,
                            reason=f"PermissionError:{inner_exc}",
                        )
                        inline_boundary_fallback = True
                else:
                    raise
            if inline_boundary_fallback:
                worker_rc = str(
                    int(
                        _run_market_payload_read_boundary_mode(
                            input_path=input_path,
                            output_path=output_path,
                        )
                    )
                )
            else:
                if proc is None:
                    raise RuntimeError("market_payload_read_boundary_spawn_missing_proc")
                worker_deadline = time.monotonic() + max(float(helper_timeout_seconds) + 5.0, 35.0)
                while True:
                    polled_rc = proc.poll()
                    if polled_rc is not None:
                        worker_rc = str(polled_rc)
                        break
                    if time.monotonic() >= worker_deadline:
                        with contextlib.suppress(Exception):
                            proc.terminate()
                        with contextlib.suppress(Exception):
                            proc.wait(timeout=2.0)
                        if proc.poll() is None:
                            with contextlib.suppress(Exception):
                                proc.kill()
                            with contextlib.suppress(Exception):
                                proc.wait(timeout=2.0)
                        worker_rc = "124"
                        _progress(
                            "market_payload_read_boundary_worker_timeout",
                            run_id=run_id,
                            sku=sku,
                            timeout_seconds=str(helper_timeout_seconds),
                        )
                        break
                    time.sleep(0.2)
    except BaseException:
        _owner_wait_mark_exit(
            run_id=run_id,
            sku=sku,
            state="abandoned",
            reason="read_boundary_inline_exception",
            worker_rc=worker_rc,
            output_exists="1" if output_path.exists() else "0",
        )
        raise
    finally:
        for sig_obj, previous in reversed(ignored_signal_handlers):
            try:
                signal.signal(sig_obj, previous)
            except BaseException:
                continue
    _owner_wait_mark_exit(
        run_id=run_id,
        sku=sku,
        state="wait_returned",
        reason=f"read_boundary_inline_returned_rc_{worker_rc or 'unknown'}",
        worker_rc=worker_rc,
        output_exists="1" if output_path.exists() else "0",
    )
    _checkpoint(
        "owner_post_subcall_read_boundary_wait_returned",
        run_id=run_id,
        sku=sku,
        worker_rc=_norm(worker_rc),
        output_exists="1" if output_path.exists() else "0",
    )
    if not output_path.exists():
        subcall_stderr_path_raw = _norm(subcall_spawn_contract.get("subcall_stderr_path", ""))
        subcall_stdout_path_raw = _norm(subcall_spawn_contract.get("subcall_stdout_path", ""))
        subcall_stderr_tail = ""
        subcall_stdout_tail = ""
        if subcall_stderr_path_raw:
            subcall_stderr_path = Path(subcall_stderr_path_raw)
            if subcall_stderr_path.exists():
                try:
                    raw_stderr = subcall_stderr_path.read_text(encoding="utf-8", errors="replace")
                    subcall_stderr_tail = raw_stderr[-8192:]
                except Exception:
                    subcall_stderr_tail = ""
        if subcall_stdout_path_raw:
            subcall_stdout_path = Path(subcall_stdout_path_raw)
            if subcall_stdout_path.exists():
                try:
                    raw_stdout = subcall_stdout_path.read_text(encoding="utf-8", errors="replace")
                    subcall_stdout_tail = raw_stdout[-8192:]
                except Exception:
                    subcall_stdout_tail = ""
        interrupt_fallback_enabled = _to_bool(
            os.environ.get("H110_READ_BOUNDARY_MISSING_OUTPUT_INTERRUPT_FALLBACK_ENABLED", "1"),
            default=True,
        )
        interrupt_marker_detected = ("KeyboardInterrupt" in subcall_stderr_tail) or (
            "KeyboardInterrupt" in subcall_stdout_tail
        )
        if interrupt_fallback_enabled and interrupt_marker_detected:
            _progress(
                "market_payload_read_boundary_missing_output_interrupt_fallback",
                run_id=run_id,
                sku=sku,
                reason="subcall_keyboard_interrupt_without_output",
                subcall_stderr_path=subcall_stderr_path_raw,
                subcall_stdout_path=subcall_stdout_path_raw,
            )
            try:
                fallback_contract = _inline_market_payload_fallback()
                fallback_contract["reason"] = "inline_fallback_after_subcall_interrupt_missing_output"
                fallback_contract["checkpoint_last"] = "market_payload_read_boundary_inline_fallback_after_subcall_interrupt_missing_output"
                _checkpoint(
                    "owner_post_subcall_read_boundary_wait_returned",
                    run_id=run_id,
                    sku=sku,
                    worker_rc="0",
                    output_exists="1",
                )
                _progress(
                    "market_payload_read_boundary_missing_output_interrupt_fallback_resolved",
                    run_id=run_id,
                    sku=sku,
                    checkpoint_last=_norm(fallback_contract.get("checkpoint_last", "")),
                )
                return fallback_contract
            except BaseException as fallback_exc:
                _progress(
                    "market_payload_read_boundary_missing_output_interrupt_fallback_failed",
                    run_id=run_id,
                    sku=sku,
                    error_type=type(fallback_exc).__name__,
                    reason=_norm(str(fallback_exc))[:240],
                )
        _progress("market_payload_read_boundary_invalid", run_id=run_id, sku=sku, reason="missing_output")
        raise RuntimeError("completion_convergence_failed:market_payload_read_boundary_invalid")
    _progress("market_payload_read_boundary_read", run_id=run_id, sku=sku, worker_rc=_norm(worker_rc), output_path=str(output_path))
    try:
        boundary_contract = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        _progress("market_payload_read_boundary_invalid", run_id=run_id, sku=sku, reason="invalid_json")
        raise RuntimeError("completion_convergence_failed:market_payload_read_boundary_invalid")
    if not isinstance(boundary_contract, dict):
        _progress("market_payload_read_boundary_invalid", run_id=run_id, sku=sku, reason="contract_not_object")
        raise RuntimeError("completion_convergence_failed:market_payload_read_boundary_invalid")
    contract_run_id = _norm(boundary_contract.get("run_id", ""))
    contract_sku = _norm(boundary_contract.get("sku", "")).upper()
    if contract_run_id != run_id or contract_sku != sku:
        _progress("market_payload_read_boundary_invalid", run_id=run_id, sku=sku, reason="identity_mismatch")
        raise RuntimeError("completion_convergence_failed:market_payload_read_boundary_invalid")
    contract_status = _norm(boundary_contract.get("contract_status", "")).lower()
    payload = boundary_contract.get("parsed_payload", {})
    if contract_status == "ok" and not isinstance(payload, dict):
        _progress("market_payload_read_boundary_invalid", run_id=run_id, sku=sku, reason="payload_not_object")
        raise RuntimeError("completion_convergence_failed:market_payload_read_boundary_invalid")
    if _norm(worker_rc) not in {"", "0"} and contract_status == "ok":
        _progress("market_payload_read_boundary_invalid", run_id=run_id, sku=sku, reason="worker_rc_mismatch")
        raise RuntimeError("completion_convergence_failed:market_payload_read_boundary_invalid")
    if contract_status != "ok":
        if _is_interrupt_contract(boundary_contract, worker_rc):
            _progress(
                "market_payload_read_boundary_interrupt_retry",
                run_id=run_id,
                sku=sku,
                reason=_norm(boundary_contract.get("reason", "")) or "interrupt_signal",
                checkpoint_last=_norm(boundary_contract.get("checkpoint_last", "")),
                error_class=_norm(boundary_contract.get("error_class", "")),
                worker_rc=str(worker_rc),
            )
            try:
                fallback_contract = _inline_market_payload_fallback()
                _checkpoint(
                    "owner_post_subcall_read_boundary_wait_returned",
                    run_id=run_id,
                    sku=sku,
                    worker_rc="0",
                    output_exists="1",
                )
                _progress(
                    "market_payload_read_boundary_interrupt_retry_resolved",
                    run_id=run_id,
                    sku=sku,
                    checkpoint_last=_norm(fallback_contract.get("checkpoint_last", "")),
                )
                return fallback_contract
            except BaseException as fallback_exc:
                _progress(
                    "market_payload_read_boundary_interrupt_retry_failed",
                    run_id=run_id,
                    sku=sku,
                    error_type=type(fallback_exc).__name__,
                    reason=_norm(str(fallback_exc))[:240],
                )
        _progress(
            "market_payload_read_boundary_failed",
            run_id=run_id,
            sku=sku,
            reason=_norm(boundary_contract.get("reason", "")) or "status_not_ok",
            checkpoint_last=_norm(boundary_contract.get("checkpoint_last", "")),
            error_class=_norm(boundary_contract.get("error_class", "")),
            worker_rc=str(worker_rc),
        )
        boundary_reason = _norm(boundary_contract.get("reason", "")) or "market_payload_read_boundary_failed"
        raise RuntimeError(f"completion_convergence_failed:market_payload_read_boundary_failed:{boundary_reason}")
    _progress(
        "market_payload_read_boundary_valid",
        run_id=run_id,
        sku=sku,
        checkpoint_last=_norm(boundary_contract.get("checkpoint_last", "")),
        error_class=_norm(boundary_contract.get("error_class", "")),
        worker_rc=str(worker_rc),
    )
    _checkpoint(
        "owner_post_subcall_read_boundary_wait_returned",
        run_id=run_id,
        sku=sku,
        worker_rc="0",
        output_exists="1",
    )
    return boundary_contract


def _run_direct_artifact_owner_mode(*, input_path: Path) -> int:
    run_id = ""
    sku = ""
    try:
        req = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req, dict):
            raise RuntimeError("input_json_not_object")
        run_id = _norm(req.get("root_run_id", ""))
        helper_req_raw = req.get("helper_req", {})
        if not isinstance(helper_req_raw, dict):
            raise RuntimeError("helper_req_not_object")
        sku = _norm(helper_req_raw.get("sku", "")).upper()
        _progress("direct_artifact_owner_enter", run_id=run_id, sku=sku, worker_pid=os.getpid())
        helper_contract = _run_sku_pre_result_helper_contract(helper_req_raw)
        status = _norm(helper_contract.get("status", "")).lower()
        reason = _norm(helper_contract.get("reason", ""))
        if status != "ok":
            fail_reason = f"direct_artifact_owner_contract_{status or 'invalid'}:{reason or 'missing'}"
            _write_completion_marker(
                status="failed",
                run_id=run_id,
                reason=fail_reason,
                payload_result_ok=False,
                fail_closed=True,
            )
            _progress("direct_artifact_owner_marker_failed", run_id=run_id, sku=sku, reason=fail_reason)
            _progress("direct_artifact_owner_exit", run_id=run_id, sku=sku, rc="1")
            return 1

        payload_raw = helper_contract.get("payload", {})
        if not isinstance(payload_raw, dict):
            fail_reason = "direct_artifact_owner_payload_not_object"
            _write_completion_marker(
                status="failed",
                run_id=run_id,
                reason=fail_reason,
                payload_result_ok=False,
                fail_closed=True,
            )
            _progress("direct_artifact_owner_marker_failed", run_id=run_id, sku=sku, reason=fail_reason)
            _progress("direct_artifact_owner_exit", run_id=run_id, sku=sku, rc="1")
            return 1

        state = {
            "phase1_pilot": "1",
            "phase1_sku": sku,
            "phase1_skus_processed_csv": sku,
            "phase1_skus_processed_count": "1",
            "phase1_direct_artifact_owner": "1",
            "phase1_market_data_present": _norm(helper_contract.get("market_data_present", "0")),
            "phase1_writer_mode": _norm(helper_contract.get("writer_mode", "READ_ONLY")),
            "phase1_write_effective": _norm(helper_contract.get("write_effective", "0")),
            "phase1_repricing_enabled": _norm(helper_contract.get("repricing_enabled", "0")),
            "phase1_listings_observed_price": _norm(helper_contract.get("listings_observed_price", "")),
            "run_id": run_id,
        }
        _progress("direct_artifact_owner_payload_ready", run_id=run_id, sku=sku, payload_keys=str(len(state.keys())))
        _progress("direct_artifact_owner_result_write_start", run_id=run_id, sku=sku)
        _finalize_success_contract(run_id=run_id, state=state)
        _progress("direct_artifact_owner_result_write_done", run_id=run_id, sku=sku)
        _progress("direct_artifact_owner_marker_success", run_id=run_id, sku=sku, reason="payload_emitted")
        _progress("direct_artifact_owner_exit", run_id=run_id, sku=sku, rc="0")
        return 0
    except BaseException as exc:
        fail_reason = f"direct_artifact_owner_exception:{type(exc).__name__}:{_norm(str(exc))[:180]}"
        if _norm(run_id):
            with contextlib.suppress(Exception):
                _write_completion_marker(
                    status="failed",
                    run_id=run_id,
                    reason=fail_reason,
                    payload_result_ok=False,
                    fail_closed=True,
                )
        _progress("direct_artifact_owner_marker_failed", run_id=run_id, sku=sku, reason=fail_reason)
        _progress("direct_artifact_owner_exit", run_id=run_id, sku=sku, rc="1")
        return 1


def _spawn_direct_artifact_owner_handoff(
    *,
    root_run_id: str,
    sku_run_id: str,
    sku: str,
    helper_req: dict[str, object],
) -> _DirectArtifactOwnershipHandoff:
    helper_dir = H_LIVE_DIR / "tmp_h110_direct_artifact_owner"
    helper_dir.mkdir(parents=True, exist_ok=True)
    token = f"{root_run_id}.{sku_run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
    input_path = helper_dir / f"in.{token}.json"
    stdout_path = helper_dir / f"stdout.{token}.log"
    stderr_path = helper_dir / f"stderr.{token}.log"
    payload = {
        "root_run_id": root_run_id,
        "sku_run_id": sku_run_id,
        "sku": sku,
        "helper_req": helper_req,
    }
    _atomic_write_text(input_path, json.dumps(payload, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--direct-artifact-owner",
        "--direct-owner-input",
        str(input_path),
    )
    with stdout_path.open("wb") as out_fh, stderr_path.open("wb") as err_fh:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            close_fds=True,
            env=os.environ.copy(),
        )
    _progress(
        "market_payload_subcall_spawned",
        run_id=sku_run_id,
        sku=sku,
        child_pid=str(proc.pid),
        input_path=str(input_path),
        output_path="direct_artifact_owner_mode",
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        timeout_seconds="handoff",
    )
    return _DirectArtifactOwnershipHandoff(owner_pid=int(proc.pid), root_run_id=root_run_id)


def _run_sku_pre_result_helper_mode(*, input_path: Path, output_path: Path) -> int:
    try:
        req = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req, dict):
            raise RuntimeError("input_json_not_object")
    except Exception as exc:
        payload = {
            "status": "failed",
            "reason": f"input_read_error:{type(exc).__name__}:{exc}",
            "run_id": "",
            "sku": "",
        }
        _atomic_write_text(output_path, json.dumps(payload, ensure_ascii=True) + "\n")
        return 1
    try:
        contract = _run_sku_pre_result_helper_contract(req)
    except BaseException as exc:
        contract = {
            "status": "failed",
            "reason": f"helper_exception:{type(exc).__name__}:{exc}",
            "run_id": _norm(req.get("run_id", "")),
            "sku": _norm(req.get("sku", "")).upper(),
        }
    _atomic_write_text(output_path, json.dumps(contract, ensure_ascii=True) + "\n")
    return 0 if _norm(contract.get("status", "")).lower() in {"ok", "skip"} else 1


def _run_owner_worker_pre_result_contract(
    *,
    run_id: str,
    sku: str,
    req: dict[str, object],
    mode: str,
) -> dict[str, object]:
    mode_norm = _norm(mode).lower()
    if mode_norm == "inline":
        contract = _run_sku_pre_result_helper_contract(req)
        if not isinstance(contract, dict):
            raise RuntimeError("owner_worker_continuation_failed:pre_result_inline_contract_not_object")
        return contract

    helper_dir = H_LIVE_DIR / "tmp_h110_owner_worker_pre_result"
    helper_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
    input_path = helper_dir / f"in.{token}.json"
    output_path = helper_dir / f"out.{token}.json"
    stdout_path = helper_dir / f"stdout.{token}.log"
    stderr_path = helper_dir / f"stderr.{token}.log"
    _atomic_write_text(input_path, json.dumps(req, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--sku-pre-result-helper",
        "--sku-helper-input",
        str(input_path),
        "--sku-helper-output",
        str(output_path),
    )
    with stdout_path.open("wb") as out_fh, stderr_path.open("wb") as err_fh:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            close_fds=True,
            env=os.environ.copy(),
        )
        timeout_seconds = max(_env_int("H110_OWNER_WORKER_PRE_RESULT_TIMEOUT_SECONDS", 90), 20)
        try:
            proc.wait(timeout=float(timeout_seconds))
        except Exception:
            with contextlib.suppress(Exception):
                proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=3.0)
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    proc.wait(timeout=3.0)
            raise RuntimeError(f"owner_worker_continuation_failed:pre_result_subprocess_timeout_after_{timeout_seconds}s")
    if not output_path.exists():
        raise RuntimeError("owner_worker_continuation_failed:pre_result_subprocess_missing_output")
    try:
        contract_raw = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"owner_worker_continuation_failed:pre_result_subprocess_invalid_json:{type(exc).__name__}:{exc}") from exc
    if not isinstance(contract_raw, dict):
        raise RuntimeError("owner_worker_continuation_failed:pre_result_subprocess_contract_not_object")
    contract_run_id = _norm(contract_raw.get("run_id", ""))
    contract_sku = _norm(contract_raw.get("sku", "")).upper()
    if contract_run_id != run_id:
        raise RuntimeError(
            f"owner_worker_continuation_failed:pre_result_subprocess_run_id_mismatch:{contract_run_id or 'missing'}"
        )
    if contract_sku != sku:
        raise RuntimeError(
            f"owner_worker_continuation_failed:pre_result_subprocess_sku_mismatch:{contract_sku or 'missing'}"
        )
    return contract_raw


def _run_payload_assembly_worker_mode(*, input_path: Path, output_path: Path) -> int:
    # Narrow worker for execution-owner payload assembly boundary only.
    return _run_pre_result_worker_mode(input_path=input_path, output_path=output_path)


def _run_owner_worker_payload_worker_mode(*, input_path: Path, output_path: Path) -> int:
    # Backward-compatible alias for legacy internal mode names.
    return _run_payload_assembly_worker_mode(input_path=input_path, output_path=output_path)


def _invoke_owner_worker_payload_worker(
    *,
    run_id: str,
    sku: str,
    cfg: dict[str, object],
    universe_row: dict[str, str],
    listing_row: dict[str, str],
    listing_snapshot_path: str,
    seller_snapshot_path: str,
) -> dict[str, object]:
    worker_dir = H_LIVE_DIR / "tmp_h110_owner_worker_payload"
    worker_dir.mkdir(parents=True, exist_ok=True)
    token = f"{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
    input_path = worker_dir / f"in.{token}.json"
    output_path = worker_dir / f"out.{token}.json"
    stdout_path = worker_dir / f"stdout.{token}.log"
    stderr_path = worker_dir / f"stderr.{token}.log"
    req = {
        "run_id": run_id,
        "sku": sku,
        "cfg_marketplace_id": _norm(_cfg_get(cfg, "marketplace_id", default="")),
        "cfg_sku": _norm(_cfg_get(cfg, "sku", default="")),
        "cfg_asin": _norm(_cfg_get(cfg, "asin", default="")),
        "cfg_seller_id": _norm(_cfg_get(cfg, "seller_id", default="")),
        "universe_row": universe_row,
        "listing_row": listing_row,
        "listing_snapshot_path": _norm(listing_snapshot_path),
        "seller_snapshot_path": _norm(seller_snapshot_path),
    }
    _atomic_write_text(input_path, json.dumps(req, ensure_ascii=True) + "\n")
    cmd = _self_python_cmd(
        "--payload-assembly-worker",
        "--payload-assembly-input",
        str(input_path),
        "--payload-assembly-output",
        str(output_path),
    )
    timeout_seconds = max(_env_int("H110_OWNER_WORKER_PAYLOAD_TIMEOUT_SECONDS", 120), 30)
    with stdout_path.open("wb") as out_fh, stderr_path.open("wb") as err_fh:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out_fh,
            stderr=err_fh,
            close_fds=True,
            env=os.environ.copy(),
        )
        _progress(
            "payload_worker_spawned",
            run_id=run_id,
            sku=sku,
            child_pid=str(proc.pid),
            worker_input_path=str(input_path),
            worker_output_path=str(output_path),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            timeout_seconds=str(timeout_seconds),
        )
        try:
            worker_rc = int(proc.wait(timeout=float(timeout_seconds)))
        except Exception:
            with contextlib.suppress(Exception):
                proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=3.0)
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    proc.wait(timeout=3.0)
            _progress(
                "payload_worker_failed",
                run_id=run_id,
                sku=sku,
                reason=f"timeout_after_{timeout_seconds}s",
            )
            raise RuntimeError(f"payload_worker_failed:timeout_after_{timeout_seconds}s")
    if not output_path.exists():
        _progress(
            "payload_worker_failed",
            run_id=run_id,
            sku=sku,
            reason="missing_worker_contract_output",
        )
        raise RuntimeError("payload_worker_failed:missing_contract_output")
    _progress(
        "payload_worker_read",
        run_id=run_id,
        sku=sku,
        worker_rc=str(worker_rc),
        worker_output_path=str(output_path),
    )
    try:
        contract_raw = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _progress(
            "payload_worker_failed",
            run_id=run_id,
            sku=sku,
            reason=f"contract_json_error:{type(exc).__name__}:{exc}",
        )
        raise RuntimeError(f"payload_worker_failed:contract_json_error:{type(exc).__name__}:{exc}") from exc
    if not isinstance(contract_raw, dict):
        _progress("payload_worker_failed", run_id=run_id, sku=sku, reason="contract_not_object")
        raise RuntimeError("payload_worker_failed:contract_not_object")
    contract_run_id = _norm(contract_raw.get("run_id", ""))
    contract_sku = _norm(contract_raw.get("sku", "")).upper()
    if contract_run_id != run_id:
        _progress(
            "payload_worker_failed",
            run_id=run_id,
            sku=sku,
            reason=f"run_id_mismatch:{contract_run_id or 'missing'}",
        )
        raise RuntimeError(f"payload_worker_failed:run_id_mismatch:{contract_run_id or 'missing'}")
    if contract_sku != sku:
        _progress(
            "payload_worker_failed",
            run_id=run_id,
            sku=sku,
            reason=f"sku_mismatch:{contract_sku or 'missing'}",
        )
        raise RuntimeError(f"payload_worker_failed:sku_mismatch:{contract_sku or 'missing'}")
    status = _norm(contract_raw.get("status", "")).lower()
    reason = _norm(contract_raw.get("reason", ""))
    payload_raw = contract_raw.get("payload", {})
    if status == "ok" and not isinstance(payload_raw, dict):
        _progress("payload_worker_failed", run_id=run_id, sku=sku, reason="payload_not_object")
        raise RuntimeError("payload_worker_failed:payload_not_object")
    if status != "ok":
        _progress(
            "payload_worker_failed",
            run_id=run_id,
            sku=sku,
            reason=reason or (status or "status_not_ok"),
            worker_rc=str(worker_rc),
        )
        raise RuntimeError(f"payload_worker_failed:{reason or (status or 'status_not_ok')}")
    helper_contract = payload_raw.get("helper_contract", {})
    if not isinstance(helper_contract, dict):
        _progress(
            "payload_worker_failed",
            run_id=run_id,
            sku=sku,
            reason="helper_contract_not_object",
        )
        raise RuntimeError("payload_worker_failed:helper_contract_not_object")
    _progress(
        "payload_worker_valid",
        run_id=run_id,
        sku=sku,
        worker_rc=str(worker_rc),
        worker_reason=reason or "ok",
        checkpoint_last=_norm(contract_raw.get("checkpoint_last", "")),
        error_class=_norm(contract_raw.get("error_class", "")),
    )
    return helper_contract


def _run_post_helper_acceptance_mode(
    *,
    input_path: Path,
    output_path: Path,
    run_id: str,
    sku: str,
) -> int:
    accepted: dict[str, object] = {
        "run_id": run_id,
        "sku": sku,
        "acceptance_status": "invalid",
        "reason": "uninitialized",
    }
    try:
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RuntimeError("helper_contract_not_object")
        status = _norm(raw.get("status", "")).lower()
        reason = _norm(raw.get("reason", ""))
        raw_run_id = _norm(raw.get("run_id", ""))
        raw_sku = _norm(raw.get("sku", "")).upper()
        if raw_run_id and raw_run_id != run_id:
            raise RuntimeError(f"run_id_mismatch:{raw_run_id}")
        if raw_sku and raw_sku != sku:
            raise RuntimeError(f"sku_mismatch:{raw_sku}")
        if status not in {"ok", "skip"}:
            raise RuntimeError(f"helper_status_invalid:{status or 'missing'}")
        if status == "ok":
            payload = raw.get("payload", {})
            if not isinstance(payload, dict):
                raise RuntimeError("payload_not_object")
            if not _norm(raw.get("seller_id", "")):
                raise RuntimeError("seller_id_missing")
            if not _norm(raw.get("marketplace_id", "")):
                raise RuntimeError("marketplace_id_missing")
        if status == "skip":
            out_row = raw.get("out_row", {})
            if not isinstance(out_row, dict):
                raise RuntimeError("skip_out_row_missing")
        accepted = {
            "run_id": run_id,
            "sku": sku,
            "acceptance_status": "valid",
            "reason": reason or "ok",
            "contract": raw,
        }
        _atomic_write_text(output_path, json.dumps(accepted, ensure_ascii=True) + "\n")
        return 0
    except Exception as exc:
        accepted = {
            "run_id": run_id,
            "sku": sku,
            "acceptance_status": "invalid",
            "reason": f"{type(exc).__name__}:{exc}",
        }
        _atomic_write_text(output_path, json.dumps(accepted, ensure_ascii=True) + "\n")
        return 1


def _invoke_post_helper_acceptance(
    *,
    run_id: str,
    sku: str,
    helper_output_path: Path,
    helper_dir: Path,
) -> dict[str, object]:
    accept_out = helper_dir / f"accept.{run_id}.{sku}.{os.getpid()}.{time.time_ns()}.json"
    cmd = _self_python_cmd(
        "--post-helper-acceptance",
        "--acceptance-input",
        str(helper_output_path),
        "--acceptance-output",
        str(accept_out),
        "--acceptance-run-id",
        run_id,
        "--acceptance-sku",
        sku,
    )
    proc = _popen_hidden(
        cmd,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        env=os.environ.copy(),
    )
    _progress(
        "post_helper_acceptance_spawned",
        run_id=run_id,
        sku=sku,
        child_pid=str(proc.pid),
        helper_output_path=str(helper_output_path),
        acceptance_output_path=str(accept_out),
    )
    timeout_seconds = max(_env_int("H110_POST_HELPER_ACCEPTANCE_TIMEOUT_SECONDS", 20), 5)
    try:
        rc = int(proc.wait(timeout=float(timeout_seconds)))
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        _progress(
            "post_helper_acceptance_failed",
            run_id=run_id,
            sku=sku,
            reason=f"timeout_after_{timeout_seconds}s",
        )
        raise RuntimeError(f"post_helper_acceptance_failed:timeout_after_{timeout_seconds}s")
    if not accept_out.exists():
        _progress(
            "post_helper_acceptance_failed",
            run_id=run_id,
            sku=sku,
            reason="missing_acceptance_output",
            rc=str(rc),
        )
        raise RuntimeError(f"post_helper_acceptance_failed:missing_acceptance_output:rc={rc}")
    try:
        acc = json.loads(accept_out.read_text(encoding="utf-8"))
    except Exception as exc:
        _progress(
            "post_helper_acceptance_invalid",
            run_id=run_id,
            sku=sku,
            reason=f"invalid_json:{type(exc).__name__}:{exc}",
            rc=str(rc),
        )
        raise RuntimeError(f"post_helper_acceptance_failed:invalid_json:rc={rc}")
    if not isinstance(acc, dict):
        _progress(
            "post_helper_acceptance_invalid",
            run_id=run_id,
            sku=sku,
            reason="acceptance_not_object",
            rc=str(rc),
        )
        raise RuntimeError(f"post_helper_acceptance_failed:acceptance_not_object:rc={rc}")
    status = _norm(acc.get("acceptance_status", "")).lower()
    reason = _norm(acc.get("reason", ""))
    _progress(
        "post_helper_acceptance_read",
        run_id=run_id,
        sku=sku,
        acceptance_status=status or "missing",
        reason=reason,
        rc=str(rc),
    )
    if rc != 0 or status != "valid":
        _progress(
            "post_helper_acceptance_invalid",
            run_id=run_id,
            sku=sku,
            reason=reason or "acceptance_invalid",
            rc=str(rc),
        )
        _progress(
            "post_helper_acceptance_failed",
            run_id=run_id,
            sku=sku,
            reason=reason or "acceptance_invalid",
            rc=str(rc),
        )
        raise RuntimeError(f"post_helper_acceptance_failed:{reason or 'acceptance_invalid'}:rc={rc}")
    _progress(
        "post_helper_acceptance_valid",
        run_id=run_id,
        sku=sku,
        reason=reason,
        rc=str(rc),
    )
    return acc


def _spawn_post_exit_terminalizer(
    *,
    run_id: str,
    marker_path: Path,
    result_path: Path,
    checkpoint_path: Path | None,
    liveness_pid: int = 0,
) -> None:
    def _terminalizer_liveness_pid(marker: Path) -> int:
        fallback_pid = int(os.getpid())
        try:
            parts = str(marker.name or "").strip().split(".")
            # phase1_pilot_step.complete.<run_id>.<parent_pid>.<token>.json
            if len(parts) >= 6 and parts[0] == "phase1_pilot_step" and parts[1] == "complete" and parts[-1] == "json":
                owner_pid_raw = str(parts[-3] or "").strip()
                if owner_pid_raw.isdigit():
                    owner_pid = int(owner_pid_raw)
                    if owner_pid > 0:
                        return owner_pid
        except Exception:
            pass
        return fallback_pid

    wait_seconds = max(_env_float("H110_POST_EXIT_TERMINALIZER_WAIT_SECONDS", 12.0), 1.0)
    liveness_pid_effective = int(liveness_pid) if int(liveness_pid or 0) > 0 else _terminalizer_liveness_pid(marker_path)
    cmd = _self_python_cmd(
        "--post-exit-terminalizer",
        "--terminalizer-run-id",
        run_id,
        "--terminalizer-parent-pid",
        str(liveness_pid_effective),
        "--terminalizer-marker-path",
        str(marker_path),
        "--terminalizer-result-path",
        str(result_path),
        "--terminalizer-checkpoint-path",
        str(checkpoint_path) if checkpoint_path is not None else "",
        "--terminalizer-wait-seconds",
        str(wait_seconds),
    )
    flags = 0
    flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        proc = _popen_hidden(
            cmd,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
            env=os.environ.copy(),
        )
        _progress(
            "post_exit_terminalizer_spawned",
            run_id=run_id,
            child_pid=str(proc.pid),
            parent_pid=str(liveness_pid_effective),
            marker_path=str(marker_path),
            result_path=str(result_path),
            checkpoint_path=str(checkpoint_path) if checkpoint_path is not None else "",
            wait_seconds=str(wait_seconds),
        )
    except Exception as exc:
        _progress(
            "post_exit_terminalizer_error",
            run_id=run_id,
            reason="spawn_failed",
            error=f"{type(exc).__name__}:{exc}",
        )


def _write_result_payload(payload: dict[str, object]) -> None:
    if PHASE1_RESULT_PATH is None:
        return
    payload_text = json.dumps(payload, ensure_ascii=True) + "\n"
    _progress(
        "full_worker_result_write_start",
        path=str(PHASE1_RESULT_PATH),
        bytes=len(payload_text.encode("utf-8")),
    )
    _progress(
        "completion_result_write_start",
        path=str(PHASE1_RESULT_PATH),
        bytes=len(payload_text.encode("utf-8")),
    )
    _progress(
        "completion_result_write_attempt",
        path=str(PHASE1_RESULT_PATH),
        bytes=len(payload_text.encode("utf-8")),
    )
    _progress(
        "h110 result_payload_write_start",
        path=str(PHASE1_RESULT_PATH),
        bytes=len(payload_text.encode("utf-8")),
    )
    _progress(
        "result_payload_write_start",
        path=str(PHASE1_RESULT_PATH),
        bytes=len(payload_text.encode("utf-8")),
    )
    try:
        _atomic_write_text(PHASE1_RESULT_PATH, payload_text)
        _progress(
            "full_worker_result_write_done",
            status="ok",
            path=str(PHASE1_RESULT_PATH),
            bytes=len(payload_text.encode("utf-8")),
        )
        _progress(
            "completion_result_write_done",
            status="ok",
            path=str(PHASE1_RESULT_PATH),
            bytes=len(payload_text.encode("utf-8")),
        )
        _progress(
            "h110 result_payload_write_done",
            status="ok",
            path=str(PHASE1_RESULT_PATH),
            bytes=len(payload_text.encode("utf-8")),
        )
        _progress(
            "result_payload_write_done",
            status="ok",
            path=str(PHASE1_RESULT_PATH),
            bytes=len(payload_text.encode("utf-8")),
        )
    except Exception as exc:
        try:
            _progress(
                "full_worker_result_write_done",
                status="fail",
                path=str(PHASE1_RESULT_PATH),
                error=f"{type(exc).__name__}:{exc}",
            )
            _progress(
                "completion_result_write_done",
                status="fail",
                path=str(PHASE1_RESULT_PATH),
                error=f"{type(exc).__name__}:{exc}",
            )
            _progress(
                "h110 result_payload_write_done",
                status="fail",
                path=str(PHASE1_RESULT_PATH),
                error=f"{type(exc).__name__}:{exc}",
            )
            _progress(
                "result_payload_write_done",
                status="fail",
                path=str(PHASE1_RESULT_PATH),
                error=f"{type(exc).__name__}:{exc}",
            )
        except Exception:
            pass
        raise RuntimeError(f"result_payload_write_failed:{type(exc).__name__}:{exc}") from exc


def _emit_success_payload(payload: dict[str, object]) -> None:
    _progress(
        "full_worker_result_build_start",
        run_id=_norm(payload.get("run_id", "")) if isinstance(payload, dict) else "",
        payload_keys=str(len(payload.keys())) if isinstance(payload, dict) else "0",
    )
    _progress(
        "result_payload_build_enter",
        run_id=_norm(payload.get("run_id", "")) if isinstance(payload, dict) else "",
        payload_keys=str(len(payload.keys())) if isinstance(payload, dict) else "0",
    )
    payload_text = json.dumps(payload, ensure_ascii=True)
    _progress(
        "full_worker_result_build_done",
        run_id=_norm(payload.get("run_id", "")) if isinstance(payload, dict) else "",
        bytes=len(payload_text.encode("utf-8")),
    )
    _progress(
        "result_payload_build_exit",
        run_id=_norm(payload.get("run_id", "")) if isinstance(payload, dict) else "",
        bytes=len(payload_text.encode("utf-8")),
    )
    result_ok = False
    stdout_ok = False
    result_error = ""
    stdout_error = ""
    if PHASE1_RESULT_PATH is not None:
        try:
            _write_result_payload(payload)
            result_ok = PHASE1_RESULT_PATH.exists() and PHASE1_RESULT_PATH.stat().st_size > 0
            if not result_ok:
                result_error = "result_file_missing_after_write"
        except Exception as exc:
            result_error = f"{type(exc).__name__}:{exc}"
    else:
        result_error = "result_path_missing"
    try:
        sys.stdout.write(payload_text + "\n")
        sys.stdout.flush()
        stdout_ok = True
    except Exception as exc:
        stdout_error = f"{type(exc).__name__}:{exc}"
    _progress(
        "h110 success_payload_emit",
        stdout_ok="1" if stdout_ok else "0",
        result_ok="1" if result_ok else "0",
        result_path=str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
        result_error=result_error,
        stdout_error=stdout_error,
    )
    if not stdout_ok and not result_ok:
        raise RuntimeError(
            "phase1 pilot success payload unavailable "
            f"(stdout_ok=0 result_ok=0 result_path={PHASE1_RESULT_PATH} "
            f"result_error={result_error} stdout_error={stdout_error})"
        )


def _write_completion_marker(
    *,
    status: str,
    run_id: str,
    reason: str = "",
    payload_result_ok: bool = False,
    fail_closed: bool = False,
) -> bool:
    _progress(
        "completion_marker_transition_attempt",
        status=_norm(status).lower() or "unknown",
        run_id=_norm(run_id),
        reason=_norm(reason),
        marker_path=str(PHASE1_COMPLETION_MARKER_PATH) if PHASE1_COMPLETION_MARKER_PATH else "",
        fail_closed="1" if fail_closed else "0",
    )
    if PHASE1_COMPLETION_MARKER_PATH is None:
        _progress(
            "completion_marker_transition_done",
            status="fail",
            marker_status=_norm(status).lower() or "unknown",
            run_id=_norm(run_id),
            reason="marker_path_missing",
        )
        if fail_closed:
            raise RuntimeError("h110 completion marker path missing")
        return False
    payload = {
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": _norm(status).lower() or "unknown",
        "run_id": _norm(run_id),
        "reason": _norm(reason),
        "result_path": str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
        "result_ok": "1" if payload_result_ok else "0",
    }
    text = json.dumps(payload, ensure_ascii=True) + "\n"
    try:
        _atomic_write_text(PHASE1_COMPLETION_MARKER_PATH, text)
        marker_exists = PHASE1_COMPLETION_MARKER_PATH.exists()
        marker_size = int(PHASE1_COMPLETION_MARKER_PATH.stat().st_size) if marker_exists else 0
        marker_ok = marker_exists and marker_size > 0
        _progress(
            "completion_marker_transition_done",
            status="ok" if marker_ok else "fail",
            marker_status=payload.get("status", ""),
            run_id=payload.get("run_id", ""),
            reason=payload.get("reason", ""),
            marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
            marker_size=str(marker_size),
            fail_closed="1" if fail_closed else "0",
        )
        _progress(
            "h110 completion_marker_write",
            status="ok" if marker_ok else "fail",
            marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
            marker_size=str(marker_size),
            marker_status=payload.get("status", ""),
            marker_run_id=payload.get("run_id", ""),
            fail_closed="1" if fail_closed else "0",
        )
        if payload.get("status", "") == "success":
            _progress(
                "h110 completion_marker_success_write",
                status="ok" if marker_ok else "fail",
                marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
                marker_run_id=payload.get("run_id", ""),
            )
        elif payload.get("status", "") == "failed":
            _progress(
                "h110 completion_marker_failed_write",
                status="ok" if marker_ok else "fail",
                marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
                marker_run_id=payload.get("run_id", ""),
                reason=payload.get("reason", ""),
            )
        if not marker_ok and fail_closed:
            raise RuntimeError(
                "h110 completion contract failed: completion marker missing after write "
                f"(completion_marker_path={PHASE1_COMPLETION_MARKER_PATH})"
            )
        return marker_ok
    except Exception as exc:
        _progress(
            "completion_marker_transition_done",
            status="fail",
            marker_status=payload.get("status", ""),
            run_id=payload.get("run_id", ""),
            reason=payload.get("reason", ""),
            marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
            error=f"{type(exc).__name__}:{exc}",
            fail_closed="1" if fail_closed else "0",
        )
        _progress(
            "h110 completion_marker_write",
            status="fail",
            marker_path=str(PHASE1_COMPLETION_MARKER_PATH),
            error=f"{type(exc).__name__}:{exc}",
            marker_status=payload.get("status", ""),
            marker_run_id=payload.get("run_id", ""),
            fail_closed="1" if fail_closed else "0",
        )
        if fail_closed:
            raise RuntimeError(
                "h110 completion contract failed: completion marker write error "
                f"(completion_marker_path={PHASE1_COMPLETION_MARKER_PATH} error={type(exc).__name__}:{exc})"
            ) from exc
        return False


def _set_active_completion_run_id(run_id: str) -> None:
    global _ACTIVE_COMPLETION_RUN_ID
    _ACTIVE_COMPLETION_RUN_ID = _norm(run_id)


def _mark_completion_success_written() -> None:
    global _SUCCESS_MARKER_WRITTEN
    _SUCCESS_MARKER_WRITTEN = True


def _ensure_failure_result_payload(*, run_id: str, reason: str) -> tuple[bool, str]:
    if PHASE1_RESULT_PATH is None:
        return False, "result_path_missing"
    try:
        if PHASE1_RESULT_PATH.exists() and int(PHASE1_RESULT_PATH.stat().st_size) > 0:
            return True, "already_present"
    except Exception:
        pass
    payload = {
        "utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": _norm(run_id),
        "phase1_pilot": "1",
        "phase1_terminal_status": "failed",
        "phase1_terminal_reason": _norm(reason) or "terminal_failure",
        "write_status": "PILOT_FAILED",
        "reason_codes_csv": _norm(reason) or "terminal_failure",
        "phase1_sku": "",
        "phase1_skus_processed_csv": "",
        "phase1_skus_processed_count": "0",
        "executioner_live_write_attempted": "0",
        "executioner_live_write_success": "0",
    }
    try:
        _write_result_payload(payload)
    except Exception:
        try:
            _atomic_write_text(PHASE1_RESULT_PATH, json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception as exc:
            return False, f"result_write_error:{type(exc).__name__}:{exc}"
    try:
        size = int(PHASE1_RESULT_PATH.stat().st_size) if PHASE1_RESULT_PATH.exists() else 0
        if size <= 0:
            return False, "result_payload_empty_after_write"
    except Exception as exc:
        return False, f"result_stat_error:{type(exc).__name__}:{exc}"
    return True, "written"


def _ensure_terminal_completion_marker(*, reason: str) -> None:
    global _TERMINAL_MARKER_ATTEMPTED
    with _MARKER_GUARD_LOCK:
        if _TERMINAL_MARKER_ATTEMPTED or _SUCCESS_MARKER_WRITTEN:
            return
        run_id = _norm(_ACTIVE_COMPLETION_RUN_ID or os.environ.get("H_RUN_ID", ""))
        if not run_id:
            return
    try:
        result_ok, result_reason = _ensure_failure_result_payload(
            run_id=run_id,
            reason=_norm(reason) or "terminal_exit_without_success_marker",
        )
        _progress(
            "terminalization_result_verified",
            run_id=run_id,
            status="ok" if result_ok else "fail",
            reason=result_reason,
            result_path=str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
        )
        _progress(
            "completion_marker_failed_start",
            run_id=run_id,
            reason=_norm(reason) or "terminal_exit_without_success_marker",
        )
        _write_completion_marker(
            status="failed",
            run_id=run_id,
            reason=_norm(reason) or "terminal_exit_without_success_marker",
            payload_result_ok=False,
        )
        _progress(
            "completion_marker_failed_done",
            run_id=run_id,
            status="ok",
            reason=_norm(reason) or "terminal_exit_without_success_marker",
        )
        with _MARKER_GUARD_LOCK:
            _TERMINAL_MARKER_ATTEMPTED = True
    except Exception as exc:
        _progress(
            "completion_marker_failed_done",
            run_id=run_id,
            status="fail",
            reason=_norm(reason) or "terminal_exit_without_success_marker",
            error=f"{type(exc).__name__}:{exc}",
        )


def _install_completion_exit_guards(run_id: str) -> None:
    _set_active_completion_run_id(run_id)

    def _atexit_guard() -> None:
        unresolved_owner_wait_reason = _owner_wait_unresolved_reason(run_id=run_id)
        if unresolved_owner_wait_reason:
            _progress(
                "owner_exit_reason",
                run_id=run_id,
                reason=unresolved_owner_wait_reason,
                state="atexit_unresolved_owner_wait",
            )
            _ensure_terminal_completion_marker(reason=unresolved_owner_wait_reason)
            # Avoid hard process abort here: let normal interpreter shutdown
            # complete so terminal marker updates are flushed to disk.
            return
        _emit_continuation_boundary_parent_exit_gap()
        _ensure_terminal_completion_marker(reason="atexit_without_success_marker")

    atexit.register(_atexit_guard)

    def _signal_guard(signum: int, _frame) -> None:  # type: ignore[no-untyped-def]
        sig_name = "SIGTERM"
        for candidate in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig_obj = getattr(signal, candidate, None)
            if sig_obj is not None and int(sig_obj) == int(signum):
                sig_name = candidate
                break
        # Do not terminalize immediately on SIGINT.
        # The owner post-subcall boundary has bounded reconcile/fail-closed
        # handling that must decide terminal truth before marker commit.
        if sig_name == "SIGINT":
            defer_only_when_owner_wait_active = _to_bool(
                os.environ.get("H110_SIGINT_DEFER_ONLY_WHEN_OWNER_WAIT_ACTIVE", "1"),
                default=True,
            )
            owner_wait_reason = (
                _owner_wait_unresolved_reason(run_id=run_id) if defer_only_when_owner_wait_active else ""
            )
            if defer_only_when_owner_wait_active and (not owner_wait_reason):
                _progress(
                    "signal_guard_sigint_ignored",
                    run_id=run_id,
                    reason="no_active_owner_wait_boundary",
                )
                return
            _progress(
                "signal_guard_sigint_deferred",
                run_id=run_id,
                reason="defer_terminalization_to_owner_reconcile",
                owner_wait_reason=owner_wait_reason,
            )
            raise SystemExit(130)
        _ensure_terminal_completion_marker(reason=f"signal_{sig_name.lower()}_before_success_marker")
        raise SystemExit(128 + int(signum))

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig_obj = getattr(signal, sig_name, None)
        if sig_obj is None:
            continue
        try:
            signal.signal(sig_obj, _signal_guard)
        except Exception:
            continue


def _completion_marker_success_for_run(run_id: str) -> tuple[bool, str]:
    marker_path = PHASE1_COMPLETION_MARKER_PATH
    if marker_path is None:
        return False, "completion_marker_path_missing"
    if not marker_path.exists():
        return False, "completion_marker_missing"
    try:
        raw = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"completion_marker_invalid_json:{type(exc).__name__}:{exc}"
    if not isinstance(raw, dict):
        return False, "completion_marker_not_object"
    status = _norm(raw.get("status", "")).lower()
    marker_run_id = _norm(raw.get("run_id", ""))
    result_ok = _norm(raw.get("result_ok", ""))
    if status != "success":
        return False, f"completion_marker_status_{status or 'missing'}"
    if run_id and marker_run_id and marker_run_id != run_id:
        return False, f"completion_marker_run_mismatch:{marker_run_id}"
    if result_ok not in {"1", "true"}:
        return False, f"completion_marker_result_not_ok:{result_ok or 'missing'}"
    return True, "ok"


def _completion_marker_status_for_run(run_id: str) -> tuple[str, str]:
    marker_path = PHASE1_COMPLETION_MARKER_PATH
    if marker_path is None:
        return "", "completion_marker_path_missing"
    if not marker_path.exists():
        return "", "completion_marker_missing"
    try:
        raw = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return "", f"completion_marker_invalid_json:{type(exc).__name__}:{exc}"
    if not isinstance(raw, dict):
        return "", "completion_marker_not_object"
    status = _norm(raw.get("status", "")).lower()
    marker_run_id = _norm(raw.get("run_id", ""))
    if run_id and marker_run_id and marker_run_id != run_id:
        return status, f"completion_marker_run_mismatch:{marker_run_id}"
    return status, "ok"


def _pilot_terminal_settle_reconcile(
    *,
    run_id: str,
    initial_marker_status: str = "",
    initial_marker_reason: str = "",
    initial_success_ok: bool | None = None,
    initial_success_reason: str = "",
    log_prefix: str = "pilot_terminal_settle",
) -> tuple[bool, str, str, str]:
    settle_seconds = max(_env_float("H110_PILOT_TERMINAL_SETTLE_SECONDS", 8.0), 1.0)
    interval_seconds = max(_env_float("H110_PILOT_TERMINAL_SETTLE_INTERVAL_SECONDS", 0.25), 0.1)
    _progress(
        f"{log_prefix}_enter",
        run_id=run_id,
        settle_seconds=f"{settle_seconds:.2f}",
        interval_seconds=f"{interval_seconds:.2f}",
        initial_marker_status=initial_marker_status,
        initial_marker_reason=initial_marker_reason,
        initial_success_ok="" if initial_success_ok is None else ("1" if initial_success_ok else "0"),
        initial_success_reason=initial_success_reason,
    )

    deadline = time.time() + float(settle_seconds)
    attempt = 0
    last_marker_status = _norm(initial_marker_status).lower()
    last_marker_reason = _norm(initial_marker_reason)
    last_success_ok = bool(initial_success_ok)
    last_success_reason = _norm(initial_success_reason)
    while True:
        attempt += 1
        marker_status, marker_reason = _completion_marker_status_for_run(run_id)
        success_ok, success_reason = _completion_marker_success_for_run(run_id)
        last_marker_status = _norm(marker_status).lower()
        last_marker_reason = _norm(marker_reason)
        last_success_ok = bool(success_ok)
        last_success_reason = _norm(success_reason)
        _progress(
            f"{log_prefix}_attempt",
            run_id=run_id,
            attempt=str(attempt),
            marker_status=last_marker_status,
            marker_reason=last_marker_reason,
            success_ok="1" if last_success_ok else "0",
            success_reason=last_success_reason,
        )
        if last_success_ok:
            _progress(
                f"{log_prefix}_success",
                run_id=run_id,
                attempt=str(attempt),
                marker_status=last_marker_status,
                success_reason=last_success_reason,
            )
            _progress(
                f"{log_prefix}_final_classification",
                run_id=run_id,
                final_classification="success",
                marker_status=last_marker_status,
                marker_reason=last_marker_reason,
                success_reason=last_success_reason,
            )
            return True, last_marker_status, last_marker_reason, last_success_reason
        if time.time() >= deadline:
            _progress(
                f"{log_prefix}_timeout",
                run_id=run_id,
                attempts=str(attempt),
                marker_status=last_marker_status,
                marker_reason=last_marker_reason,
                success_reason=last_success_reason,
            )
            final_class = "failed" if last_marker_status == "failed" else "missing_terminal_evidence"
            _progress(
                f"{log_prefix}_final_classification",
                run_id=run_id,
                final_classification=final_class,
                marker_status=last_marker_status,
                marker_reason=last_marker_reason,
                success_reason=last_success_reason,
            )
            return False, last_marker_status, last_marker_reason, last_success_reason
        time.sleep(interval_seconds)


def _marker_reason(prefix: str, *, run_id: str, exc: BaseException | None = None) -> str:
    parts = [prefix, _norm(run_id)]
    if exc is not None:
        parts.append(type(exc).__name__)
        msg = _norm(str(exc))[:180]
        if msg:
            parts.append(msg)
    return ":".join([p for p in parts if _norm(p)])


def _result_payload_contract_status() -> tuple[bool, str, int]:
    if PHASE1_RESULT_PATH is None:
        return False, "result_path_missing", 0
    try:
        if not PHASE1_RESULT_PATH.exists():
            return False, "result_path_missing", 0
        size = int(PHASE1_RESULT_PATH.stat().st_size)
        if size <= 0:
            return False, "result_payload_empty", size
        return True, "ok", size
    except Exception as exc:
        return False, f"result_stat_error:{type(exc).__name__}:{exc}", 0


def _install_os_exit_interceptor(run_id: str):
    original = os._exit

    def _intercept(code: object) -> None:
        _progress(
            "terminalization_os_exit_intercepted",
            run_id=run_id,
            code=str(code),
        )
        raise _TerminalizationOsExitIntercepted(code)

    os._exit = _intercept  # type: ignore[assignment]
    return original


def _restore_os_exit(original) -> None:
    os._exit = original  # type: ignore[assignment]


def _terminalization_funnel(
    *,
    run_id: str,
    payload: dict[str, object] | None,
    failure: BaseException | None,
    failure_reason: str,
) -> int:
    _progress(
        "terminalization_funnel_enter",
        run_id=run_id,
        payload_ready="1" if isinstance(payload, dict) else "0",
        failure_type=type(failure).__name__ if failure is not None else "",
    )
    reason = _norm(failure_reason)
    _checkpoint("terminalization_funnel_enter", run_id=run_id)

    if failure is None:
        _checkpoint("terminalization_success_candidate", run_id=run_id)
        try:
            _finalize_success_contract(run_id=run_id, state=payload)
            _mark_completion_success_written()
            _progress("terminalization_funnel_success", run_id=run_id, reason="ok")
            return 0
        except BaseException as exc:
            narrowed_reason = _norm(str(exc))
            _progress(
                "completion_convergence_failed",
                run_id=run_id,
                stage="result_write_or_success_marker",
                reason=f"{type(exc).__name__}:{_norm(str(exc))[:180]}",
            )
            _progress(
                "full_worker_convergence_failed",
                run_id=run_id,
                stage="result_write_or_success_marker",
                reason=f"{type(exc).__name__}:{_norm(str(exc))[:180]}",
            )
            _progress(
                "completion_result_write_done",
                run_id=run_id,
                status="fail",
                path=str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
                error=f"{type(exc).__name__}:{exc}",
            )
            _progress(
                "completion_marker_success_done",
                run_id=run_id,
                status="fail",
                reason="payload_emitted",
                error=f"{type(exc).__name__}:{exc}",
            )
            _progress(
                "full_worker_success_marker_done",
                run_id=run_id,
                status="fail",
                reason="payload_emitted",
                error=f"{type(exc).__name__}:{exc}",
            )
            _progress(
                "terminalization_contract_invalid",
                run_id=run_id,
                reason=f"success_path_exception:{type(exc).__name__}",
                error=_norm(str(exc))[:240],
            )
            if narrowed_reason.startswith("completion_convergence_failed:boundary_"):
                _progress(
                    "completion_convergence_boundary_failed",
                    run_id=run_id,
                    stage="result_write_or_success_marker",
                    reason=narrowed_reason[:240],
                )
                _checkpoint(
                    "completion_convergence_boundary_failed",
                    run_id=run_id,
                    stage="result_write_or_success_marker",
                )
                reason = narrowed_reason[:240]
            else:
                reason = _marker_reason("success_path_exception", run_id=run_id, exc=exc)
    else:
        if not reason:
            reason = _marker_reason("run_failure", run_id=run_id, exc=failure)
        _progress(
            "terminalization_contract_invalid",
            run_id=run_id,
            reason=reason,
        )
        _progress(
            "completion_convergence_failed",
            run_id=run_id,
            stage="run_failure",
            reason=reason,
            error_type=type(failure).__name__ if failure is not None else "",
        )
        _progress(
            "full_worker_convergence_failed",
            run_id=run_id,
            stage="run_failure",
            reason=reason,
            error_type=type(failure).__name__ if failure is not None else "",
        )

    if not reason:
        reason = "terminalization_contract_invalid_unspecified"
    try:
        result_ok, result_reason = _ensure_failure_result_payload(run_id=run_id, reason=reason)
        _progress(
            "terminalization_result_verified",
            run_id=run_id,
            status="ok" if result_ok else "fail",
            reason=result_reason,
            result_path=str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
        )
        _progress(
            "completion_marker_failed_start",
            run_id=run_id,
            reason=reason,
        )
        marker_written = _write_completion_marker(
            status="failed",
            run_id=run_id,
            reason=reason,
            payload_result_ok=False,
            fail_closed=True,
        )
        _progress(
            "terminalization_marker_written",
            run_id=run_id,
            marker_status="failed",
            status="ok" if marker_written else "fail",
            reason=reason,
        )
        _progress(
            "completion_marker_failed_done",
            run_id=run_id,
            status="ok" if marker_written else "fail",
            reason=reason,
        )
        _progress("owner_worker_continuation_failed", run_id=run_id, stage="terminalization", reason=reason)
        _progress("pilot_owner_worker_marker_failed", run_id=run_id, reason=reason)
        _progress("pilot_execution_owner_marker_failed", run_id=run_id, reason=reason)
        _progress("payload_worker_owner_marker_failed", run_id=run_id, reason=reason)
        _progress("market_payload_owner_marker_failed", run_id=run_id, reason=reason)
    except BaseException as marker_exc:
        _progress(
            "terminalization_marker_written",
            run_id=run_id,
            marker_status="failed",
            status="fail",
            reason=reason,
            error=f"{type(marker_exc).__name__}:{marker_exc}",
        )
        _progress(
            "completion_marker_failed_done",
            run_id=run_id,
            status="fail",
            reason=reason,
            error=f"{type(marker_exc).__name__}:{marker_exc}",
        )
        _progress(
            "owner_worker_continuation_failed",
            run_id=run_id,
            stage="terminalization_marker_write",
            reason=reason,
            error=f"{type(marker_exc).__name__}:{marker_exc}",
        )
        _progress(
            "pilot_owner_worker_marker_failed",
            run_id=run_id,
            reason=reason,
            error=f"{type(marker_exc).__name__}:{marker_exc}",
        )
        _progress(
            "pilot_execution_owner_marker_failed",
            run_id=run_id,
            reason=reason,
            error=f"{type(marker_exc).__name__}:{marker_exc}",
        )
        _progress(
            "payload_worker_owner_marker_failed",
            run_id=run_id,
            reason=reason,
            error=f"{type(marker_exc).__name__}:{marker_exc}",
        )
        _progress(
            "market_payload_owner_marker_failed",
            run_id=run_id,
            reason=reason,
            error=f"{type(marker_exc).__name__}:{marker_exc}",
        )
    _progress("terminalization_funnel_failure", run_id=run_id, reason=reason)
    return 1


def _finalize_success_contract(*, run_id: str, state: dict[str, object] | None) -> None:
    _progress("convergence_enter", run_id=run_id)
    _checkpoint("convergence_enter", run_id=run_id)

    state_failed, state_reason = _run_state_terminal_failed_for_run(run_id=run_id)
    if state_failed:
        _progress(
            "completion_convergence_blocked_by_failed_run_state",
            run_id=run_id,
            reason=state_reason[:240],
        )
        raise RuntimeError(f"completion_convergence_failed:run_state_terminal_failed:{state_reason[:180]}")

    if not isinstance(state, dict):
        raise RuntimeError("convergence_payload_missing")

    _progress(
        "convergence_payload_ready",
        run_id=run_id,
        payload_keys=str(len(state.keys())),
    )
    _progress(
        "market_payload_owner_payload_ready",
        run_id=run_id,
        payload_keys=str(len(state.keys())),
    )
    _checkpoint("convergence_payload_ready", run_id=run_id)

    _progress("convergence_write_start", run_id=run_id)
    _progress("owner_worker_result_write_start", run_id=run_id)
    _progress("pilot_owner_worker_result_write_start", run_id=run_id)
    _progress("pilot_execution_owner_result_write_start", run_id=run_id)
    _progress("payload_worker_owner_result_write_start", run_id=run_id)
    _progress("market_payload_owner_result_write_start", run_id=run_id)
    _progress("completion_convergence_result_write_start", run_id=run_id)
    _checkpoint("completion_convergence_result_write_start", run_id=run_id)
    _progress("completion_convergence_boundary_result_write_start", run_id=run_id)
    _checkpoint("completion_convergence_boundary_result_write_start", run_id=run_id)
    _checkpoint("completion_result_write_start", run_id=run_id)
    try:
        _emit_success_payload(state)
        result_ok, result_reason, result_size = _result_payload_contract_status()
        _progress(
            "terminalization_result_verified",
            run_id=run_id,
            status="ok" if result_ok else "fail",
            reason=result_reason,
            result_path=str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
            result_size=str(result_size),
        )
        if not result_ok:
            raise RuntimeError(f"result_contract_invalid:{result_reason}")
    except BaseException as exc:
        narrowed_reason = _norm(str(exc)) or type(exc).__name__
        _progress(
            "completion_convergence_boundary_failed",
            run_id=run_id,
            stage="result_write",
            reason=narrowed_reason[:240],
        )
        _checkpoint(
            "completion_convergence_boundary_failed",
            run_id=run_id,
            stage="result_write",
        )
        raise RuntimeError(f"completion_convergence_failed:boundary_result_write:{narrowed_reason[:180]}") from exc

    _progress(
        "convergence_write_done",
        run_id=run_id,
        result_size=str(result_size),
    )
    _progress(
        "owner_worker_result_write_done",
        run_id=run_id,
        result_size=str(result_size),
    )
    _progress(
        "pilot_owner_worker_result_write_done",
        run_id=run_id,
        result_size=str(result_size),
    )
    _progress(
        "pilot_execution_owner_result_write_done",
        run_id=run_id,
        result_size=str(result_size),
    )
    _progress(
        "payload_worker_owner_result_write_done",
        run_id=run_id,
        result_size=str(result_size),
    )
    _progress(
        "market_payload_owner_result_write_done",
        run_id=run_id,
        result_size=str(result_size),
    )
    _progress(
        "completion_convergence_result_write_done",
        run_id=run_id,
        status="ok",
        path=str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
    )
    _checkpoint("completion_convergence_result_write_done", run_id=run_id)
    _progress("completion_convergence_boundary_result_write_done", run_id=run_id)
    _checkpoint("completion_convergence_boundary_result_write_done", run_id=run_id)
    _progress(
        "completion_result_write_done",
        run_id=run_id,
        status="ok",
        path=str(PHASE1_RESULT_PATH) if PHASE1_RESULT_PATH else "",
    )

    _progress("convergence_marker_success", run_id=run_id)
    _progress("owner_worker_marker_success_start", run_id=run_id, reason="payload_emitted")
    _progress("completion_convergence_success_marker_start", run_id=run_id, reason="payload_emitted")
    _progress("full_worker_success_marker_start", run_id=run_id, reason="payload_emitted")
    _checkpoint("completion_convergence_success_marker_start", run_id=run_id)
    _progress("completion_convergence_boundary_marker_success_start", run_id=run_id, reason="payload_emitted")
    _checkpoint("completion_convergence_boundary_marker_success_start", run_id=run_id)
    _progress(
        "completion_marker_success_start",
        run_id=run_id,
        reason="payload_emitted",
    )
    try:
        marker_written = _write_completion_marker(
            status="success",
            run_id=run_id,
            reason="payload_emitted",
            payload_result_ok=True,
            fail_closed=True,
        )
    except BaseException as exc:
        narrowed_reason = _norm(str(exc)) or type(exc).__name__
        _progress(
            "completion_convergence_boundary_failed",
            run_id=run_id,
            stage="marker_success",
            reason=narrowed_reason[:240],
        )
        _checkpoint(
            "completion_convergence_boundary_failed",
            run_id=run_id,
            stage="marker_success",
        )
        raise RuntimeError(f"completion_convergence_failed:boundary_marker_success:{narrowed_reason[:180]}") from exc
    _progress(
        "terminalization_marker_written",
        run_id=run_id,
        marker_status="success",
        status="ok" if marker_written else "fail",
    )
    _progress(
        "full_worker_success_marker_done",
        run_id=run_id,
        status="ok" if marker_written else "fail",
        reason="payload_emitted",
    )
    _progress(
        "completion_marker_success_done",
        run_id=run_id,
        status="ok" if marker_written else "fail",
        reason="payload_emitted",
    )
    _progress(
        "completion_convergence_success_marker_done",
        run_id=run_id,
        status="ok" if marker_written else "fail",
        reason="payload_emitted",
    )
    _checkpoint("completion_convergence_success_marker_done", run_id=run_id)
    _progress(
        "completion_convergence_boundary_marker_success_done",
        run_id=run_id,
        status="ok" if marker_written else "fail",
        reason="payload_emitted",
    )
    _checkpoint("completion_convergence_boundary_marker_success_done", run_id=run_id)
    marker_ok, marker_reason = _completion_marker_success_for_run(run_id)
    if not marker_ok:
        _progress(
            "completion_convergence_boundary_failed",
            run_id=run_id,
            stage="marker_success",
            reason=f"marker_invalid:{marker_reason}",
        )
        _checkpoint(
            "completion_convergence_boundary_failed",
            run_id=run_id,
            stage="marker_success",
        )
        raise RuntimeError(f"completion_convergence_failed:boundary_marker_success:marker_invalid:{marker_reason}")
    _progress("owner_worker_marker_success_done", run_id=run_id, reason="payload_emitted")
    _progress("pilot_owner_worker_marker_success", run_id=run_id, reason="payload_emitted")
    _progress("pilot_execution_owner_marker_success", run_id=run_id, reason="payload_emitted")
    _progress("payload_worker_owner_marker_success", run_id=run_id, reason="payload_emitted")
    _progress("market_payload_owner_marker_success", run_id=run_id, reason="payload_emitted")

    _progress("convergence_exit", run_id=run_id, status="ok")
    _checkpoint("convergence_exit", run_id=run_id)


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _to_float(value: object) -> float | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        out = float(raw)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _resolve_vat_rate(row: pd.Series, fee_row: dict[str, str]) -> float:
    # Repricer VAT must be based on product/market VAT rates, not settlement withheld flags.
    vat_raw = _to_float(fee_row.get("last_vat_rate_pct", ""))
    if vat_raw is None:
        vat_raw = _to_float(fee_row.get("vat_rate", ""))
    if vat_raw is not None:
        if vat_raw > 1:
            vat_raw = vat_raw / 100.0
        if vat_raw < 0:
            vat_raw = 0.0
        return vat_raw

    price_ex = _to_float(row.get("Price_ExVAT_num", ""))
    price_vat = _to_float(row.get("Price_VAT_num", ""))
    if price_ex is not None and price_ex > 0 and price_vat is not None:
        candidate = abs(price_vat) / abs(price_ex)
        if candidate >= 0:
            return candidate
    return 0.2


def _to_int(value: object) -> int | None:
    try:
        raw = _norm(value)
        if not raw:
            return None
        return int(float(raw))
    except Exception:
        return None


def _round_half_up(value: float, ndigits: int = 2) -> float:
    q = Decimal("1").scaleb(-ndigits)
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def _csv_cell(value: object) -> str:
    text = _norm(value)
    if any(ch in text for ch in [",", "\"", "\n", "\r"]):
        text = "\"" + text.replace("\"", "\"\"") + "\""
    return text


def _append_csv_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    _apply_h110_log_retention(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        if fh.tell() == 0:
            fh.write(",".join(headers) + "\n")
        for row in rows:
            fh.write(",".join(_csv_cell(row.get(col, "")) for col in headers) + "\n")


def _h110_log_retention_config(path: Path) -> tuple[int, int, int]:
    if path == H110_SKU_LIFECYCLE_LOG_PATH:
        return (H110_LIFECYCLE_ROTATE_MAX_BYTES, H110_LIFECYCLE_ROTATE_MAX_FILES, H110_LIFECYCLE_FAMILY_MAX_BYTES)
    if path == H110_SKU_DECISION_LOG_PATH:
        return (H110_DECISION_ROTATE_MAX_BYTES, H110_DECISION_ROTATE_MAX_FILES, H110_DECISION_FAMILY_MAX_BYTES)
    # Keep non-H110 csv append paths unchanged.
    return (0, 0, 0)


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


def _file_size_bytes(path: Path) -> int:
    try:
        if path.exists():
            return int(path.stat().st_size)
    except Exception:
        pass
    return 0


def _prune_log_family_budget(base_path: Path, *, max_total_bytes: int, max_total_files: int) -> None:
    max_files = max(int(max_total_files), 1)
    max_bytes = max(int(max_total_bytes), 1)
    members = _log_family_members(base_path)
    rotated_desc = sorted([item for item in members if item[0] > 0], key=lambda item: item[0], reverse=True)

    while len(members) > max_files and rotated_desc:
        _, path = rotated_desc.pop(0)
        with contextlib.suppress(Exception):
            path.unlink(missing_ok=True)
        members = [item for item in members if item[1] != path]

    total_bytes = sum(_file_size_bytes(path) for _, path in members)
    while total_bytes > max_bytes and rotated_desc:
        _, path = rotated_desc.pop(0)
        with contextlib.suppress(Exception):
            path.unlink(missing_ok=True)
        members = [item for item in members if item[1] != path]
        total_bytes = sum(_file_size_bytes(path2) for _, path2 in members)


def _apply_h110_log_retention(path: Path) -> None:
    rotate_max_bytes, rotate_max_files, family_max_bytes = _h110_log_retention_config(path)
    if rotate_max_bytes <= 0 or rotate_max_files <= 1 or family_max_bytes <= 0:
        return
    try:
        _rotate_log_file(path, max_bytes=rotate_max_bytes, max_files=rotate_max_files)
        _prune_log_family_budget(
            path,
            max_total_bytes=family_max_bytes,
            max_total_files=rotate_max_files + 1,
        )
    except Exception:
        pass


def _append_temp_floor_snapshot(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    headers = [
        "asof_utc",
        "sku",
        "order_id",
        "order_date_utc",
        "candidate_price_gbp",
        "vat_rate_market",
        "cogs_total_gbp",
        "fba_total_gbp",
        "commission_total_gbp",
        "digital_fee_total_gbp",
        "fixed_total_gbp",
        "break_even_total_gbp",
        "temp_floor_10roi_gbp",
        "source_script",
    ]
    _append_csv_rows(
        TEMP_FLOOR_SNAPSHOT_PATH,
        headers,
        [{k: _norm(row.get(k, "")) for k in headers} for row in rows],
    )


def _to_dt(value: object) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    try:
        raw = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _parse_scalar(text: str) -> object:
    raw = str(text).strip()
    if raw == "":
        return ""
    low = raw.lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except Exception:
        return raw.strip("\"'")


def _simple_yaml_load(path: Path) -> dict:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        text = line.strip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            child: dict[str, object] = {}
            parent[key] = child
            stack.append((indent, child))
            continue
        parent[key] = _parse_scalar(value)
    return root


def _cfg_get(cfg: dict, *keys: str, default: object = "") -> object:
    cur: object = cfg
    for key in keys:
        if not isinstance(cur, dict):
            return default
        if key not in cur:
            return default
        cur = cur[key]
    return cur


def _to_num_text(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def _env_float(name: str, default: float) -> float:
    raw = _norm(os.environ.get(name, ""))
    if not raw:
        return default
    parsed = _to_float(raw)
    if parsed is None:
        return default
    return parsed


def _env_int(name: str, default: int) -> int:
    raw = _norm(os.environ.get(name, ""))
    if not raw:
        return default
    parsed = _to_int(raw)
    if parsed is None:
        return default
    return parsed


def _is_truthy_text(value: object) -> bool:
    text = _norm(value).lower()
    return text in {"1", "true", "yes", "y", "on"}


def _is_in_stock_listing_row(row: dict[str, str]) -> bool:
    # Use the same listing snapshot signal the repricer already relies on.
    # If our offer is present (or we have a positive current price), treat as in stock.
    if _is_truthy_text(row.get("we_present_flag", "")):
        return True
    our_price = _to_float(row.get("our_price", ""))
    return our_price is not None and our_price > 0


def _has_active_offer_price(row: dict[str, str]) -> bool:
    for col in ("our_price", "buy_box_price", "lowest_fba_price", "lowest_fbm_price"):
        price = _to_float(row.get(col, ""))
        if price is not None and price > 0:
            return True
    return False


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


def _write_scan_state_update(
    *,
    run_id: str,
    updates_by_sku: dict[str, str] | None,
    boundary_lock_date_utc: str | None = None,
    boundary_lock_by_sku: dict[str, object] | None = None,
) -> tuple[bool, str, int]:
    normalized_updates: dict[str, str] = {}
    if isinstance(updates_by_sku, dict):
        for raw_sku, raw_ts in updates_by_sku.items():
            sku = _norm(raw_sku).upper()
            ts_text = _norm(raw_ts)
            if not sku or not ts_text:
                continue
            if _to_dt(ts_text) is None:
                continue
            normalized_updates[sku] = ts_text

    latest_scan_state = _read_json(SKU_SCAN_STATE_PATH, default={"last_scan_utc": {}, "daily_boundary_lock": {}})
    latest_last_scan_utc = latest_scan_state.get("last_scan_utc", {})
    if not isinstance(latest_last_scan_utc, dict):
        latest_last_scan_utc = {}

    merged_last_scan_utc = dict(latest_last_scan_utc)
    advanced_count = 0
    for sku_key, ts_value in normalized_updates.items():
        incoming_ts = _to_dt(ts_value)
        existing_ts = _to_dt(merged_last_scan_utc.get(sku_key, ""))
        if incoming_ts is None:
            continue
        if existing_ts is None or incoming_ts > existing_ts:
            merged_last_scan_utc[sku_key] = ts_value
            advanced_count += 1

    should_write_boundary = bool(_norm(boundary_lock_date_utc)) or isinstance(boundary_lock_by_sku, dict)
    if advanced_count <= 0 and not should_write_boundary:
        _progress(
            "scan_state_write_skipped",
            run_id=run_id,
            reason="no_advanced_timestamps",
            path=str(SKU_SCAN_STATE_PATH),
            candidate_count=str(len(normalized_updates)),
        )
        return False, "no_advanced_timestamps", 0

    next_scan_state = dict(latest_scan_state) if isinstance(latest_scan_state, dict) else {}
    next_scan_state["last_scan_utc"] = merged_last_scan_utc
    if should_write_boundary:
        next_scan_state["daily_boundary_lock"] = {
            "date_utc": _norm(boundary_lock_date_utc),
            "by_sku": boundary_lock_by_sku if isinstance(boundary_lock_by_sku, dict) else {},
        }

    _progress(
        "scan_state_write_start",
        run_id=run_id,
        path=str(SKU_SCAN_STATE_PATH),
        candidate_count=str(len(normalized_updates)),
        advanced_count=str(advanced_count),
        boundary_applied="1" if should_write_boundary else "0",
    )
    try:
        _write_json(SKU_SCAN_STATE_PATH, next_scan_state)
    except Exception as exc:
        _progress(
            "scan_state_write_failed",
            run_id=run_id,
            path=str(SKU_SCAN_STATE_PATH),
            error_type=type(exc).__name__,
            reason=_norm(str(exc))[:240],
        )
        return False, f"write_failed:{type(exc).__name__}", 0

    _progress(
        "scan_state_write_done",
        run_id=run_id,
        path=str(SKU_SCAN_STATE_PATH),
        advanced_count=str(advanced_count),
        boundary_applied="1" if should_write_boundary else "0",
    )
    return True, "ok", advanced_count


def _result_payload_processed_skus(result_payload: dict[str, object]) -> tuple[list[str], int]:
    processed_count = _to_int(result_payload.get("phase1_skus_processed_count", "0")) or 0
    processed_csv = _norm(result_payload.get("phase1_skus_processed_csv", ""))
    phase1_sku = _norm(result_payload.get("phase1_sku", "")).upper()
    processed_skus: list[str] = []
    seen: set[str] = set()
    for raw in processed_csv.split(","):
        sku = _norm(raw).upper()
        if not sku or sku in seen:
            continue
        processed_skus.append(sku)
        seen.add(sku)
    if not processed_skus and phase1_sku and processed_count > 0:
        processed_skus.append(phase1_sku)
    return processed_skus, processed_count


def _write_scan_state_from_result_payload(*, run_id: str, now_utc_text: str) -> tuple[bool, str, int]:
    if PHASE1_RESULT_PATH is None:
        _progress(
            "scan_state_write_skipped",
            run_id=run_id,
            reason="result_path_missing",
            path=str(SKU_SCAN_STATE_PATH),
        )
        return False, "result_path_missing", 0

    result_payload = _read_json(PHASE1_RESULT_PATH, default={})
    if not isinstance(result_payload, dict):
        _progress(
            "scan_state_write_skipped",
            run_id=run_id,
            reason="result_payload_not_object",
            path=str(SKU_SCAN_STATE_PATH),
        )
        return False, "result_payload_not_object", 0

    processed_skus, processed_count = _result_payload_processed_skus(result_payload)
    if processed_count <= 0 or not processed_skus:
        _progress(
            "scan_state_write_skipped",
            run_id=run_id,
            reason="no_successful_sku_in_result_payload",
            path=str(SKU_SCAN_STATE_PATH),
            phase1_sku=_norm(result_payload.get("phase1_sku", "")).upper(),
            processed_skus_csv=",".join(processed_skus),
            processed_count=str(processed_count),
        )
        return False, "no_successful_sku_in_result_payload", 0

    scan_dt = _to_dt(now_utc_text)
    if scan_dt is None:
        scan_dt = datetime.now(timezone.utc).replace(microsecond=0)
    scan_ts = scan_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updates_by_sku = {sku: scan_ts for sku in processed_skus}
    return _write_scan_state_update(
        run_id=run_id,
        updates_by_sku=updates_by_sku,
    )


def _scan_due_priority_key(row: dict[str, str], last_scan_utc: dict[str, object]) -> tuple[int, float, str]:
    sku = _norm(row.get("sku", "")).upper()
    write_rank = 0 if _as_bool_text(row.get("write_effective", ""), "0") == "1" else 1
    last_dt = _to_dt(last_scan_utc.get(sku, ""))
    last_ts = float("-inf") if last_dt is None else last_dt.timestamp()
    return (write_rank, last_ts, sku)


def _sort_due_rows_by_oldest_scan(
    due_rows: list[dict[str, str]],
    last_scan_utc: dict[str, object],
) -> list[dict[str, str]]:
    return sorted(due_rows, key=lambda row: _scan_due_priority_key(row, last_scan_utc))


def _fmt_stock_qty(value: float | None) -> str:
    if value is None:
        return ""
    return f"{_round_half_up(float(value), 2):.2f}"


def _latest_listing_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_snapshot_*.csv"))
    if not files:
        raise RuntimeError("No listing snapshot found in out/")
    return files[-1]


def _latest_seller_snapshot() -> Path:
    files = sorted(OUT.glob("listing_offer_seller_snapshot_*.csv"))
    if not files:
        raise RuntimeError("No seller snapshot found in out/")
    return files[-1]


def _load_listing_row_map(path: Path | None = None) -> dict[str, dict[str, str]]:
    target = path or _latest_listing_snapshot()
    df = pd.read_csv(target, dtype=str).fillna("")
    if "sku" not in df.columns:
        raise RuntimeError(f"listing snapshot missing required column sku: {target.name}")
    out: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        rec = {str(k): _norm(v) for k, v in row.to_dict().items()}
        sku = _norm(rec.get("sku", "")).upper()
        if not sku or sku in out:
            continue
        out[sku] = rec
    return out


def _resolve_stock_source_path() -> Path:
    raw = _norm(os.environ.get(STOCK_SNAPSHOT_PATH_ENV, ""))
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        return path
    return DEFAULT_STOCK_SNAPSHOT_PATH


def _resolve_stock_glob_pattern() -> str:
    raw = _norm(os.environ.get(STOCK_SNAPSHOT_GLOB_ENV, ""))
    return raw or DEFAULT_STOCK_SNAPSHOT_GLOB


def _resolve_stock_max_age_hours() -> float:
    parsed = _to_float(os.environ.get(STOCK_SNAPSHOT_MAX_AGE_HOURS_ENV, DEFAULT_STOCK_SNAPSHOT_MAX_AGE_HOURS))
    if parsed is None:
        return DEFAULT_STOCK_SNAPSHOT_MAX_AGE_HOURS
    return max(float(parsed), 0.0)


def _resolve_stock_require_today() -> bool:
    return _to_bool(os.environ.get(STOCK_SNAPSHOT_REQUIRE_TODAY_ENV, "0"), default=False)


def _resolve_stock_row_stale_hours() -> float:
    parsed = _to_float(os.environ.get(STOCK_ROW_STALE_HOURS_ENV, DEFAULT_STOCK_ROW_STALE_HOURS))
    if parsed is None:
        return DEFAULT_STOCK_ROW_STALE_HOURS
    return max(float(parsed), 0.0)


def _resolve_glob_paths(pattern: str) -> list[Path]:
    candidate = Path(pattern)
    if candidate.is_absolute():
        base = candidate.parent
        glob_pat = candidate.name
    else:
        base = ROOT
        glob_pat = pattern
    try:
        return sorted(base.glob(glob_pat))
    except Exception:
        return []


def _is_dated_inventory_snapshot(path: Path) -> bool:
    name = _norm(path.name).lower()
    if not (name.startswith("inventory_snapshot_") and name.endswith(".csv")):
        return False
    token = name[len("inventory_snapshot_") : -4]
    if len(token) != 10:
        return False
    try:
        datetime.strptime(token, "%Y-%m-%d")
        return True
    except Exception:
        return False


def _collect_stock_snapshot_candidates() -> list[Path]:
    paths: list[Path] = []

    # 1) Canonical stock truth for runtime decisions: latest dated inventory snapshot.
    inv_snapshots = sorted(OUT.glob(INVENTORY_SNAPSHOT_GLOB))
    dated_inv_snapshots = [path for path in inv_snapshots if _is_dated_inventory_snapshot(path)]
    if dated_inv_snapshots:
        paths.append(sorted(dated_inv_snapshots)[-1])
    elif inv_snapshots:
        paths.append(inv_snapshots[-1])

    # 2) inventory_summaries.csv is compatibility fallback when snapshot is missing.
    if INVENTORY_SUMMARIES_PATH.exists():
        paths.append(INVENTORY_SUMMARIES_PATH)

    # 3) Parking stock snapshots are last resort.
    explicit = _resolve_stock_source_path()
    if explicit.exists():
        paths.append(explicit)

    for path in _resolve_glob_paths(_resolve_stock_glob_pattern()):
        if path.is_file():
            paths.append(path)

    parent = explicit.parent if explicit.parent.exists() else OUT / "parking"
    if parent.exists():
        for path in sorted(parent.glob("stock_snapshot*.csv"), reverse=True):
            if path.is_file():
                paths.append(path)

    dedup: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(path)
    return dedup


def _resolve_stock_column(
    df: pd.DataFrame,
    *,
    env_col: str,
    candidates: list[str],
    label: str,
) -> str:
    explicit = _norm(os.environ.get(env_col, ""))
    if explicit:
        if explicit in df.columns:
            return explicit
        raise RuntimeError(f"[H110] stock snapshot missing configured {label} column '{explicit}'")
    for col in candidates:
        if col in df.columns:
            return col
    raise RuntimeError(f"[H110] stock snapshot missing {label} column; tried {','.join(candidates)}")


def _parse_stock_qty(value: object) -> float | None:
    raw = _norm(value)
    if not raw:
        return None
    parsed = _to_float(raw)
    if parsed is None:
        return None
    return parsed


def _resolve_optional_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    return ""


def _parse_inbound_total_from_row(row: pd.Series, available_cols: set[str]) -> float | None:
    present_component_cols = [col for col in INBOUND_COMPONENT_COLS if col in available_cols]
    if present_component_cols:
        total = 0.0
        for col in present_component_cols:
            val = _parse_stock_qty(row.get(col, ""))
            if val is not None and val > 0:
                total += float(val)
        return total
    inbound_col = ""
    for col in INBOUND_UNITS_COL_CANDIDATES:
        if col in available_cols:
            inbound_col = col
            break
    if not inbound_col:
        return None
    return _parse_stock_qty(row.get(inbound_col, ""))


def _parse_snapshot_dt(value: object) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            day = datetime.fromisoformat(f"{text}T00:00:00+00:00")
            return day.astimezone(timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _infer_snapshot_datetime(df: pd.DataFrame, path: Path) -> tuple[datetime, str]:
    file_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    for col in ("timestamp_utc", "asof_utc", "date_utc", "asof_date"):
        if col not in df.columns:
            continue
        parsed_values = [_parse_snapshot_dt(v) for v in df[col].astype(str).tolist()]
        parsed_values = [v for v in parsed_values if v is not None]
        if parsed_values:
            parsed_max = max(parsed_values)
            if file_dt - parsed_max > timedelta(hours=48):
                return file_dt, f"{col}_stale_fallback_file_mtime"
            return parsed_max, col
    return file_dt, "file_mtime"


def _write_excluded_stock_file(
    *,
    today_utc: str,
    stock_source_path: str,
    excluded_rows: list[dict[str, str]],
) -> Path:
    out_path = H_LIVE_DIR / f"h_excluded_stock_{today_utc}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["sku", "stock_qty", "reason", "today_utc", "stock_source_path"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in excluded_rows:
            writer.writerow(
                {
                    "sku": _norm(row.get("sku", "")),
                    "stock_qty": _norm(row.get("stock_qty", "")) or ("0" if _norm(row.get("reason", "")) == "OUT_OF_STOCK" else ""),
                    "reason": _norm(row.get("reason", "")),
                    "today_utc": today_utc,
                    "stock_source_path": stock_source_path,
                }
            )
    return out_path


def _write_excluded_scope_file(
    *,
    today_utc: str,
    scope_source: str,
    excluded_rows: list[dict[str, str]],
) -> Path:
    out_path = H_LIVE_DIR / f"h_excluded_scope_{today_utc}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["sku", "sale_status", "parked_flag", "reason", "today_utc", "scope_source"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in excluded_rows:
            writer.writerow(
                {
                    "sku": _norm(row.get("sku", "")),
                    "sale_status": _norm(row.get("sale_status", "")),
                    "parked_flag": _norm(row.get("parked_flag", "")),
                    "reason": _norm(row.get("reason", "")),
                    "today_utc": today_utc,
                    "scope_source": scope_source,
                }
            )
    return out_path


def _write_exception_included_file(
    *,
    today_utc: str,
    rows: list[dict[str, str]],
) -> Path:
    out_path = H_LIVE_DIR / f"h_exception_included_{today_utc}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["sku", "total_qty", "reason", "sale_status", "parked_flag", "include_reason"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "sku": _norm(row.get("sku", "")).upper(),
                    "total_qty": _norm(row.get("total_qty", "")),
                    "reason": _norm(row.get("reason", "")),
                    "sale_status": _norm(row.get("sale_status", "")),
                    "parked_flag": _norm(row.get("parked_flag", "")),
                    "include_reason": "STOCKED_BUT_EXCLUDED",
                }
            )
    return out_path


def _load_stocked_excluded_rows(today_utc: str) -> list[dict[str, str]]:
    if not STOCKED_EXCLUDED_REPORT_PATH.exists():
        return []
    try:
        df = pd.read_csv(STOCKED_EXCLUDED_REPORT_PATH, dtype=str).fillna("")
    except Exception:
        return []
    if df.empty or "sku" not in df.columns:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, rec in df.iterrows():
        sku = _norm(rec.get("sku", "")).upper()
        if not sku or sku in seen:
            continue
        qty = _to_float(rec.get("total_qty", ""))
        if qty is None or qty <= 0:
            continue
        seen.add(sku)
        rows.append(
            {
                "sku": sku,
                "total_qty": f"{int(qty)}" if float(qty).is_integer() else f"{qty:.2f}",
                "reason": _norm(rec.get("reason", "")),
                "sale_status": _norm(rec.get("sale_status", "")),
                "parked_flag": _norm(rec.get("parked_flag", "")),
                "today_utc": today_utc,
            }
        )
    return rows


def _apply_scope_universe_filter(
    *,
    universe_rows: list[dict[str, str]],
    today_utc: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    excluded_rows: list[dict[str, str]] = []
    included_rows: list[dict[str, str]] = []
    excluded_dropped = 0
    excluded_parked = 0

    for row in universe_rows:
        parked_flag = _as_bool_text(row.get("parked_flag", ""), "0")
        is_parked = parked_flag == "1"

        if is_parked:
            if is_parked:
                excluded_parked += 1
            excluded_rows.append(
                {
                    "sku": _norm(row.get("sku", "")).upper(),
                    "sale_status": _norm(row.get("sale_status", "")),
                    "parked_flag": parked_flag,
                    "reason": "PARKED",
                }
            )
            continue
        included_rows.append(row)

    excluded_path = _write_excluded_scope_file(
        today_utc=today_utc,
        scope_source=str(CANONICAL_UNIVERSE_PATH),
        excluded_rows=excluded_rows,
    )
    summary = {
        "scope_total": str(len(universe_rows)),
        "excluded_dropped": str(excluded_dropped),
        "excluded_parked": str(excluded_parked),
        "remaining": str(len(included_rows)),
        "excluded_path": str(excluded_path),
        "scope_source": str(CANONICAL_UNIVERSE_PATH),
    }
    _progress(
        "h_universe_scope_filter",
        today_utc=today_utc,
        scope_total=summary["scope_total"],
        excluded_dropped=summary["excluded_dropped"],
        excluded_parked=summary["excluded_parked"],
        remaining=summary["remaining"],
    )
    return included_rows, summary


def _write_stock_snapshot_status(
    *,
    today_utc: str,
    chosen_path: str,
    chosen_date: str,
    age_hours: float,
    is_fallback: bool,
    status: str,
    stale_row_count: int = 0,
    stale_row_max_age_hours: float = 0.0,
) -> Path:
    out_path = H_LIVE_DIR / "h_stock_snapshot_status.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "today_utc",
                "chosen_path",
                "chosen_date",
                "age_hours",
                "is_fallback",
                "status",
                "stale_row_count",
                "stale_row_max_age_hours",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerow(
            {
                "today_utc": today_utc,
                "chosen_path": chosen_path,
                "chosen_date": chosen_date,
                "age_hours": f"{_round_half_up(age_hours, 2):.2f}",
                "is_fallback": "1" if is_fallback else "0",
                "status": status,
                "stale_row_count": str(max(int(stale_row_count), 0)),
                "stale_row_max_age_hours": f"{_round_half_up(max(float(stale_row_max_age_hours), 0.0), 2):.2f}",
            }
        )
    return out_path


def _stock_row_last_updated_by_sku(
    *,
    df: pd.DataFrame,
    sku_col: str,
) -> dict[str, datetime]:
    last_updated_col = _resolve_optional_column(df, ["last_updated_time", "last_updated", "updated_at", "updated_utc"])
    if not last_updated_col:
        return {}
    out: dict[str, datetime] = {}
    for _, row in df.iterrows():
        sku_key = _norm(row.get(sku_col, "")).upper()
        if not sku_key:
            continue
        updated_dt = _parse_snapshot_dt(row.get(last_updated_col, ""))
        if updated_dt is None:
            continue
        prev = out.get(sku_key)
        if prev is None or updated_dt > prev:
            out[sku_key] = updated_dt
    return out


def _load_available_token_units_by_sku() -> dict[str, int]:
    if not TOKEN_LEDGER_PATH.exists():
        return {}
    try:
        token_df = pd.read_csv(TOKEN_LEDGER_PATH, dtype=str).fillna("")
    except Exception:
        return {}
    if token_df.empty:
        return {}
    sku_col = _resolve_optional_column(token_df, ["seller_sku", "sku", "SellerSKU", "seller-sku"])
    status_col = _resolve_optional_column(token_df, ["status", "Status"])
    if not sku_col or not status_col:
        return {}
    work = token_df[[sku_col, status_col]].copy()
    work["sku_key"] = work[sku_col].astype(str).str.strip().str.upper()
    work["status_key"] = work[status_col].astype(str).str.strip().str.lower()
    work = work.loc[(work["sku_key"] != "") & (work["status_key"] == "available")]
    if work.empty:
        return {}
    grouped = work.groupby("sku_key", as_index=False).size()
    return {str(row["sku_key"]): int(row["size"]) for _, row in grouped.iterrows()}


def _load_post_update_sold_units_by_sku(cutoff_by_sku: dict[str, datetime]) -> dict[str, float]:
    if not cutoff_by_sku or not ORDER_MASTER_PATH.exists():
        return {}
    try:
        order_df = pd.read_csv(ORDER_MASTER_PATH, dtype=str).fillna("")
    except Exception:
        return {}
    if order_df.empty:
        return {}
    sku_col = _resolve_optional_column(order_df, ["SKU", "sku", "seller_sku", "SellerSKU"])
    qty_col = _resolve_optional_column(order_df, ["Quantity Ordered", "quantity_ordered", "qty", "quantity"])
    date_col = _resolve_optional_column(order_df, ["Date", "order_date", "purchase_date", "date_utc"])
    if not sku_col or not qty_col or not date_col:
        return {}
    sold_by_sku: dict[str, float] = {}
    for _, row in order_df.iterrows():
        sku_key = _norm(row.get(sku_col, "")).upper()
        if not sku_key:
            continue
        cutoff_dt = cutoff_by_sku.get(sku_key)
        if cutoff_dt is None:
            continue
        qty_val = _to_float(row.get(qty_col, ""))
        if qty_val is None or qty_val <= 0:
            continue
        order_dt = _parse_snapshot_dt(row.get(date_col, ""))
        if order_dt is None or order_dt <= cutoff_dt:
            continue
        sold_by_sku[sku_key] = float(sold_by_sku.get(sku_key, 0.0)) + float(qty_val)
    return sold_by_sku


def _apply_stock_universe_filter(
    *,
    due_rows: list[dict[str, str]],
    now_utc: datetime,
    today_utc: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    candidates = _collect_stock_snapshot_candidates()
    if not candidates:
        raise RuntimeError("[H110] stock snapshot missing: no candidate files found")

    parsed_candidates: list[dict[str, object]] = []
    parse_errors: list[str] = []
    for path in candidates:
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
            if df.empty:
                continue
            sku_col = _resolve_stock_column(
                df,
                env_col=STOCK_SNAPSHOT_SKU_COL_ENV,
                candidates=STOCK_SKU_COL_CANDIDATES,
                label="sku",
            )
            qty_col = _resolve_stock_column(
                df,
                env_col=STOCK_SNAPSHOT_QTY_COL_ENV,
                candidates=STOCK_QTY_COL_CANDIDATES,
                label="qty",
            )
            snapshot_dt, snapshot_basis = _infer_snapshot_datetime(df, path)
            parsed_candidates.append(
                {
                    "path": path,
                    "df": df,
                    "sku_col": sku_col,
                    "qty_col": qty_col,
                    "snapshot_dt": snapshot_dt,
                    "snapshot_date": snapshot_dt.date().isoformat(),
                    "snapshot_basis": snapshot_basis,
                }
            )
        except Exception as exc:
            parse_errors.append(f"{path}: {exc}")

    if not parsed_candidates:
        details = " | ".join(parse_errors[:5])
        raise RuntimeError(f"[H110] no readable stock snapshots ({details})")

    inv_snapshot_candidates = sorted(
        [rec for rec in parsed_candidates if _norm(Path(str(rec["path"])).name).lower().startswith("inventory_snapshot_")],
        key=lambda rec: (rec["snapshot_dt"], str(rec["path"])),
        reverse=True,
    )
    inventory_summaries_candidates = sorted(
        [rec for rec in parsed_candidates if Path(str(rec["path"])).resolve() == INVENTORY_SUMMARIES_PATH.resolve()],
        key=lambda rec: (rec["snapshot_dt"], str(rec["path"])),
        reverse=True,
    )
    parking_stock_candidates = sorted(
        [
            rec
            for rec in parsed_candidates
            if _norm(Path(str(rec["path"])).name).lower().startswith("stock_snapshot")
            and "parking" in {part.lower() for part in Path(str(rec["path"])).parts}
        ],
        key=lambda rec: (rec["snapshot_dt"], str(rec["path"])),
        reverse=True,
    )
    other_candidates = sorted(
        [
            rec
            for rec in parsed_candidates
            if rec not in inv_snapshot_candidates
            and rec not in inventory_summaries_candidates
            and rec not in parking_stock_candidates
        ],
        key=lambda rec: (rec["snapshot_dt"], str(rec["path"])),
        reverse=True,
    )

    source_priority: dict[str, int] = {}
    for rec in inv_snapshot_candidates:
        source_priority[str(rec["path"])] = 0
    for rec in inventory_summaries_candidates:
        source_priority[str(rec["path"])] = 1
    for rec in parking_stock_candidates:
        source_priority[str(rec["path"])] = 2
    for rec in other_candidates:
        source_priority[str(rec["path"])] = 3

    ordered_candidates = sorted(
        parsed_candidates,
        key=lambda rec: (
            source_priority.get(str(rec["path"]), 99),
            -float(rec["snapshot_dt"].timestamp()),
            str(rec["path"]),
        ),
    )

    require_today = _resolve_stock_require_today()
    max_age_hours = _resolve_stock_max_age_hours()
    stock_row_stale_hours = _resolve_stock_row_stale_hours()
    chosen = ordered_candidates[0]
    is_fallback = chosen["snapshot_date"] != today_utc
    chosen_dt = chosen["snapshot_dt"]
    age_hours = max((now_utc - chosen_dt).total_seconds() / 3600.0, 0.0)
    action = "ok"
    status = "OK"
    if is_fallback:
        action = "warn"
        status = "WARN"
    if require_today and is_fallback:
        action = "abort"
        status = "ABORT"
    if age_hours > max_age_hours:
        action = "abort"
        status = "ABORT"
    chosen_last_updated_by_sku = _stock_row_last_updated_by_sku(
        df=chosen["df"],
        sku_col=str(chosen["sku_col"]),
    )
    chosen_stale_age_by_sku: dict[str, float] = {}
    for sku_key, updated_dt in chosen_last_updated_by_sku.items():
        row_age_hours = max((now_utc - updated_dt).total_seconds() / 3600.0, 0.0)
        if row_age_hours >= stock_row_stale_hours:
            chosen_stale_age_by_sku[sku_key] = float(row_age_hours)
    chosen_stale_count = len(chosen_stale_age_by_sku)
    chosen_stale_max_age_hours = max(chosen_stale_age_by_sku.values()) if chosen_stale_age_by_sku else 0.0
    if action != "abort" and chosen_stale_count > 0:
        action = "warn"
        status = "WARN"

    status_path = _write_stock_snapshot_status(
        today_utc=today_utc,
        chosen_path=str(chosen["path"]),
        chosen_date=str(chosen["snapshot_date"]),
        age_hours=age_hours,
        is_fallback=bool(is_fallback),
        status=status,
        stale_row_count=chosen_stale_count,
        stale_row_max_age_hours=chosen_stale_max_age_hours,
    )
    _progress(
        "h_stock_snapshot_decision",
        today_utc=today_utc,
        chosen_path=str(chosen["path"]),
        chosen_date=str(chosen["snapshot_date"]),
        age_hours=f"{_round_half_up(age_hours, 2):.2f}",
        is_fallback="1" if is_fallback else "0",
        stale_row_count=str(chosen_stale_count),
        stale_row_max_age_hours=f"{_round_half_up(chosen_stale_max_age_hours, 2):.2f}",
        action=action,
    )
    if action == "abort":
        if require_today and is_fallback:
            raise RuntimeError(
                f"[H110] stock snapshot require-today violation: today={today_utc} "
                f"chosen_date={chosen['snapshot_date']} source={chosen['path']}"
            )
        raise RuntimeError(
            f"[H110] stock snapshot too old: age_hours={_round_half_up(age_hours, 2):.2f} "
            f"max_age_hours={_round_half_up(max_age_hours, 2):.2f} source={chosen['path']}"
        )

    stock_source_path = chosen["path"]
    stock_df = chosen["df"]
    sku_col = str(chosen["sku_col"])
    qty_col = str(chosen["qty_col"])
    last_updated_by_sku = _stock_row_last_updated_by_sku(df=stock_df, sku_col=sku_col)
    post_update_sold_by_sku = _load_post_update_sold_units_by_sku(last_updated_by_sku)
    token_available_by_sku = _load_available_token_units_by_sku()

    stock_by_source: list[dict[str, object]] = []
    for rec in ordered_candidates:
        source_path = str(rec["path"])
        source_sku_col = str(rec["sku_col"])
        source_qty_col = str(rec["qty_col"])
        source_df = rec["df"]
        source_cols = set(source_df.columns)
        source_last_updated_col = _resolve_optional_column(
            source_df,
            ["last_updated_time", "last_updated", "updated_at", "updated_utc"],
        )
        source_last_updated_by_sku = (
            _stock_row_last_updated_by_sku(df=source_df, sku_col=source_sku_col)
            if source_last_updated_col
            else {}
        )
        source_stale_skus: set[str] = set()
        for source_sku, source_updated_dt in source_last_updated_by_sku.items():
            source_age_hours = max((now_utc - source_updated_dt).total_seconds() / 3600.0, 0.0)
            if source_age_hours >= stock_row_stale_hours:
                source_stale_skus.add(source_sku)
        source_map: dict[str, float | None] = {}
        source_inbound_map: dict[str, float | None] = {}
        for _, row in source_df.iterrows():
            sku_key = _norm(row.get(source_sku_col, "")).upper()
            if not sku_key:
                continue
            qty_val = _parse_stock_qty(row.get(source_qty_col, ""))
            inbound_val = _parse_inbound_total_from_row(row, source_cols)
            prev = source_map.get(sku_key)
            prev_inbound = source_inbound_map.get(sku_key)
            if qty_val is None:
                if prev is None:
                    source_map[sku_key] = None
            elif prev is None:
                source_map[sku_key] = qty_val
            else:
                source_map[sku_key] = float(max(float(prev), float(qty_val)))
            if inbound_val is None:
                if prev_inbound is None:
                    source_inbound_map[sku_key] = None
                continue
            if prev_inbound is None:
                source_inbound_map[sku_key] = inbound_val
            else:
                source_inbound_map[sku_key] = float(max(float(prev_inbound), float(inbound_val)))
        stock_by_source.append(
            {
                "path": source_path,
                "qty_map": source_map,
                "inbound_map": source_inbound_map,
                "stale_skus": source_stale_skus,
                "has_row_timestamp": bool(source_last_updated_col),
            }
        )

    eligible_rows: list[dict[str, str]] = []
    available_stock_by_sku: dict[str, str] = {}
    inbound_units_by_sku: dict[str, str] = {}
    excluded_rows: list[dict[str, str]] = []
    excluded_oos = 0
    excluded_unknown = 0
    excluded_stale = 0
    stale_sales_overrides = 0
    stale_row_token_fallbacks = 0
    stale_row_unknown_quarantined = 0
    stale_authoritative_skus = 0
    stale_undercount_protections = 0
    for row in due_rows:
        sku = _norm(row.get("sku", "")).upper()
        token_available_units = int(token_available_by_sku.get(sku, 0))
        sold_after_update = float(post_update_sold_by_sku.get(sku, 0.0))
        qty: float | None = None
        inbound_qty: float | None = None
        fallback_qty_candidates: list[float] = []
        fallback_inbound_candidates: list[float] = []
        stale_authoritative_qty_candidates: list[float] = []
        saw_stale_authoritative = False
        stale_unknown_for_sku = False
        for source_rec in stock_by_source:
            source_map = source_rec.get("qty_map", {})
            source_inbound_map = source_rec.get("inbound_map", {})
            source_stale_skus = source_rec.get("stale_skus", set())
            has_row_timestamp = bool(source_rec.get("has_row_timestamp", False))
            is_source_stale_for_sku = isinstance(source_stale_skus, set) and sku in source_stale_skus
            if not isinstance(source_map, dict):
                source_map = {}
            if not isinstance(source_inbound_map, dict):
                source_inbound_map = {}
            if sku not in source_map:
                candidate_qty = None
            else:
                candidate_qty = source_map.get(sku)
            if candidate_qty is not None:
                if has_row_timestamp and is_source_stale_for_sku:
                    stale_authoritative_qty_candidates.append(float(candidate_qty))
                    saw_stale_authoritative = True
                elif has_row_timestamp:
                    if qty is None:
                        qty = float(candidate_qty)
                    else:
                        qty = float(max(float(qty), float(candidate_qty)))
                else:
                    fallback_qty_candidates.append(float(candidate_qty))
            if sku not in source_inbound_map:
                candidate_inbound = None
            else:
                candidate_inbound = source_inbound_map.get(sku)
            if candidate_inbound is None:
                continue
            if has_row_timestamp and is_source_stale_for_sku:
                saw_stale_authoritative = True
            elif has_row_timestamp:
                if inbound_qty is None:
                    inbound_qty = float(candidate_inbound)
                else:
                    inbound_qty = float(max(float(inbound_qty), float(candidate_inbound)))
            else:
                fallback_inbound_candidates.append(float(candidate_inbound))
        if qty is None and fallback_qty_candidates:
            qty = float(max(fallback_qty_candidates))
        if inbound_qty is None and fallback_inbound_candidates:
            inbound_qty = float(max(fallback_inbound_candidates))
        if qty is None and stale_authoritative_qty_candidates:
            stale_authoritative_skus += 1
            stale_candidate_qty = float(max(stale_authoritative_qty_candidates))
            if token_available_units > 0:
                qty = float(token_available_units)
                stale_row_token_fallbacks += 1
            elif sold_after_update >= stale_candidate_qty:
                qty = 0.0
                stale_sales_overrides += 1
            else:
                stale_unknown_for_sku = True
                stale_row_unknown_quarantined += 1
        elif qty is not None and saw_stale_authoritative and token_available_units > float(qty):
            qty = float(token_available_units)
            stale_row_token_fallbacks += 1
        if stale_authoritative_qty_candidates:
            stale_max_qty = float(max(stale_authoritative_qty_candidates))
            fresher_qty_candidates: list[float] = []
            if qty is not None:
                fresher_qty_candidates.append(float(qty))
            if fallback_qty_candidates:
                fresher_qty_candidates.append(float(max(fallback_qty_candidates)))
            if token_available_units > 0:
                fresher_qty_candidates.append(float(token_available_units))
            if fresher_qty_candidates:
                fresher_floor_qty = float(max(fresher_qty_candidates))
                if qty is None or fresher_floor_qty > float(qty):
                    qty = fresher_floor_qty
                if fresher_floor_qty > stale_max_qty:
                    stale_undercount_protections += 1
        if qty is not None and float(qty) > 0:
            updated_dt = last_updated_by_sku.get(sku)
            if updated_dt is not None:
                row_age_hours = max((now_utc - updated_dt).total_seconds() / 3600.0, 0.0)
                if row_age_hours >= stock_row_stale_hours:
                    if sold_after_update >= float(qty) and token_available_units <= 0:
                        qty = 0.0
                        stale_sales_overrides += 1
        if qty is None:
            if inbound_qty is not None and float(inbound_qty) > 0:
                available_stock_by_sku[sku] = "0.00"
                inbound_units_by_sku[sku] = _fmt_stock_qty(float(inbound_qty))
                eligible_rows.append(row)
                continue
            excluded_unknown += 1
            if stale_unknown_for_sku:
                excluded_stale += 1
                excluded_rows.append({"sku": sku, "stock_qty": "", "reason": "STALE_STOCK_UNTRUSTED"})
            else:
                excluded_rows.append({"sku": sku, "stock_qty": "", "reason": "STOCK_UNKNOWN"})
            continue
        if float(qty) <= 0:
            if inbound_qty is not None and float(inbound_qty) > 0:
                available_stock_by_sku[sku] = _fmt_stock_qty(float(qty))
                inbound_units_by_sku[sku] = _fmt_stock_qty(float(inbound_qty))
                eligible_rows.append(row)
                continue
            excluded_oos += 1
            excluded_rows.append({"sku": sku, "stock_qty": _norm(_round_half_up(float(qty), 2)), "reason": "OUT_OF_STOCK"})
            continue
        available_stock_by_sku[sku] = _fmt_stock_qty(float(qty))
        inbound_units_by_sku[sku] = _fmt_stock_qty(float(inbound_qty)) if inbound_qty is not None else ""
        eligible_rows.append(row)

    excluded_path = _write_excluded_stock_file(
        today_utc=today_utc,
        stock_source_path=str(stock_source_path),
        excluded_rows=excluded_rows,
    )

    summary = {
        "scope_total": str(len(due_rows)),
        "eligible": str(len(eligible_rows)),
        "excluded_oos": str(excluded_oos),
        "excluded_unknown": str(excluded_unknown),
        "excluded_stale": str(excluded_stale),
        "stock_source": str(stock_source_path),
        "stock_sku_col": sku_col,
        "stock_qty_col": qty_col,
        "stock_snapshot_date": str(chosen["snapshot_date"]),
        "stock_snapshot_age_hours": f"{_round_half_up(age_hours, 2):.2f}",
        "stock_row_stale_hours": f"{_round_half_up(stock_row_stale_hours, 2):.2f}",
        "stock_snapshot_stale_row_count": str(chosen_stale_count),
        "stock_snapshot_stale_row_max_age_hours": f"{_round_half_up(chosen_stale_max_age_hours, 2):.2f}",
        "stock_snapshot_is_fallback": "1" if is_fallback else "0",
        "stock_snapshot_status": status,
        "stock_snapshot_action": action,
        "stock_snapshot_status_path": str(status_path),
        "excluded_path": str(excluded_path),
        "stale_sales_overrides": str(stale_sales_overrides),
        "stale_row_token_fallbacks": str(stale_row_token_fallbacks),
        "stale_row_unknown_quarantined": str(stale_row_unknown_quarantined),
        "stale_authoritative_skus": str(stale_authoritative_skus),
        "stale_undercount_protections": str(stale_undercount_protections),
        "available_stock_by_sku": available_stock_by_sku,
        "inbound_units_by_sku": inbound_units_by_sku,
    }
    _progress(
        "h_universe_stock_decision",
        today_utc=today_utc,
        scope_total=summary["scope_total"],
        eligible=summary["eligible"],
        excluded_oos=summary["excluded_oos"],
        excluded_unknown=summary["excluded_unknown"],
        excluded_stale=summary["excluded_stale"],
        stale_sales_overrides=summary["stale_sales_overrides"],
        stale_row_token_fallbacks=summary["stale_row_token_fallbacks"],
        stale_row_unknown_quarantined=summary["stale_row_unknown_quarantined"],
        stale_undercount_protections=summary["stale_undercount_protections"],
        stock_source=summary["stock_source"],
        stock_col=summary["stock_qty_col"],
        sku_col=summary["stock_sku_col"],
    )
    return eligible_rows, summary


def _daily_intel_today_stats(*, today_utc_date: str, skus: set[str] | None = None) -> dict[str, int | str]:
    path = phase1_storage.phase1_table_path("sku_daily_intel")
    out: dict[str, int | str] = {
        "path": str(path),
        "rows_today": 0,
        "unique_skus_today": 0,
        "matched_skus_today": 0,
    }
    if not path.exists():
        return out
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return out
    if df.empty or "date_utc" not in df.columns or "sku" not in df.columns:
        return out
    today_df = df.loc[df["date_utc"].astype(str).str.strip().eq(today_utc_date)].copy()
    today_skus = {
        _norm(v).upper()
        for v in today_df.get("sku", "").astype(str).tolist()
        if _norm(v)
    }
    out["rows_today"] = int(len(today_df.index))
    out["unique_skus_today"] = int(len(today_skus))
    if skus:
        out["matched_skus_today"] = int(len({s for s in skus if _norm(s)} & today_skus))
    return out


def _as_bool_text(value: object, default: str = "0") -> str:
    text = _norm(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return "1"
    if text in {"0", "false", "no", "n", "off"}:
        return "0"
    return default


def _append_sku_decision_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    headers = [
        "decision_ts_utc",
        "run_id",
        "sku",
        "repricing_enabled",
        "observe_effective",
        "write_effective",
        "market_data_present",
        "decision",
        "reason_code",
    ]
    _append_csv_rows(
        H110_SKU_DECISION_LOG_PATH,
        headers,
        [{k: _norm(row.get(k, "")) for k in headers} for row in rows],
    )


def _append_sku_lifecycle_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    headers = [
        "event_ts_utc",
        "run_id",
        "sku",
        "event",
        "elapsed_ms",
        "decision",
        "write_status",
        "reason_codes_csv",
        "error",
    ]
    _append_csv_rows(
        H110_SKU_LIFECYCLE_LOG_PATH,
        headers,
        [{k: _norm(row.get(k, "")) for k in headers} for row in rows],
    )


def _load_canonical_universe(now_utc: datetime) -> list[dict[str, str]]:
    phase1_sku_scope.build_and_write_scope(asof_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))
    if not CANONICAL_UNIVERSE_PATH.exists():
        raise RuntimeError(f"[H110] universe missing: {CANONICAL_UNIVERSE_PATH}")
    try:
        scope_df = pd.read_csv(CANONICAL_UNIVERSE_PATH, dtype=str).fillna("")
    except Exception as exc:
        raise RuntimeError(f"[H110] universe unreadable: {exc}")
    if scope_df.empty:
        raise RuntimeError("[H110] universe empty")
    missing_cols = sorted([c for c in REQUIRED_UNIVERSE_COLUMNS if c not in scope_df.columns])
    if missing_cols:
        raise RuntimeError(f"[H110] universe schema missing columns: {','.join(missing_cols)}")

    sku_key = scope_df["sku"].astype(str).str.strip().str.upper()
    dupes = sku_key[sku_key.ne("") & sku_key.duplicated()].tolist()
    if dupes:
        raise RuntimeError(f"[H110] universe duplicate sku rows: {','.join(sorted(set(dupes))[:10])}")

    rows: list[dict[str, str]] = []
    for _, rec in scope_df.iterrows():
        row = {str(k): _norm(v) for k, v in rec.to_dict().items()}
        sku = _norm(row.get("sku", "")).upper()
        if not sku:
            continue
        row["sku"] = sku
        row["repricing_enabled"] = _as_bool_text(row.get("repricing_enabled", ""), "0")
        row["observe_effective"] = _as_bool_text(row.get("observe_effective", ""), "1")
        row["write_effective"] = _as_bool_text(row.get("write_effective", ""), "0")
        row["reason_code"] = _norm(row.get("reason_code", "")) or "unknown"
        rows.append(row)
    if not rows:
        raise RuntimeError("[H110] universe has no valid sku rows")
    return rows


def _load_manual_caps() -> tuple[dict[str, str], dict[str, str]]:
    by_sku: dict[str, str] = {}
    by_asin: dict[str, str] = {}
    if not MANUAL_CAPS_PATH.exists():
        return by_sku, by_asin
    try:
        df = pd.read_csv(MANUAL_CAPS_PATH, dtype=str).fillna("")
    except Exception:
        return by_sku, by_asin
    for _, row in df.iterrows():
        cap_raw = _norm(row.get("manual_max_price_gbp", ""))
        cap_val = _to_float(cap_raw)
        if cap_val is None or cap_val <= 0:
            continue
        cap_text = f"{cap_val:.2f}"
        sku_key = _norm(row.get("sku", "")).upper()
        asin_key = _norm(row.get("asin", "")).upper()
        if sku_key and sku_key not in by_sku:
            by_sku[sku_key] = cap_text
        if asin_key and asin_key not in by_asin:
            by_asin[asin_key] = cap_text
    return by_sku, by_asin


def _load_temp_floor_by_sku(allowed_skus: set[str] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    floor_by_sku: dict[str, str] = {}
    blocked_by_sku: dict[str, str] = {}
    snapshot_rows: list[dict[str, str]] = []
    trace_rows: list[dict[str, str]] = []
    asof_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        context = load_h_floor_context(
            product_db_path=PRODUCT_DB_PATH,
            token_ledger_path=TOKEN_LEDGER_PATH,
            token_cogs_path=TOKEN_COGS_LEDGER_PATH,
        )
    except Exception:
        context = HFloorContext(product_db_rows={}, token_cogs_by_sku={}, vat_policy=load_h_floor_vat_policy())

    sku_filter = {s.strip().upper() for s in (allowed_skus or set()) if s and s.strip()}
    for sku_key, row in context.product_db_rows.items():
        if not sku_key:
            continue
        if sku_filter and sku_key.upper() not in sku_filter:
            continue
        candidate_price = _to_float(row.get("live_listing_price", ""))
        if candidate_price is None or candidate_price <= 0:
            candidate_price = _to_float(row.get("last_sold_price", ""))
        if candidate_price is None:
            candidate_price = 0.0

        inputs, result = compute_h_floor_for_sku(sku_key, candidate_price, context=context)
        blocking = has_blocking_reason_codes(inputs.reason_codes)
        floor_total = _round_half_up(result.floor_total_gbp, 2)
        if (not blocking) and floor_total > 0:
            floor_by_sku[sku_key] = f"{floor_total:.2f}"
        elif blocking:
            blocked_by_sku[sku_key] = ",".join(inputs.reason_codes)

        snapshot_rows.append(
            {
                "asof_utc": asof_utc,
                "sku": sku_key,
                "order_id": "",
                "order_date_utc": "",
                "candidate_price_gbp": f"{_round_half_up(inputs.candidate_price_gbp, 2):.2f}",
                "vat_rate_market": f"{inputs.vat_rate:.6f}",
                "cogs_total_gbp": f"{_round_half_up(inputs.cogs_exvat_gbp, 2):.2f}",
                "fba_total_gbp": f"{_round_half_up(inputs.fba_exvat_gbp, 2):.2f}",
                "commission_total_gbp": f"{_round_half_up(inputs.referral_amount_gbp, 2):.2f}",
                "digital_fee_total_gbp": f"{_round_half_up(inputs.digital_fee_exvat_gbp, 2):.2f}",
                "fixed_total_gbp": "0.00",
                "break_even_total_gbp": f"{_round_half_up(result.break_even_total_gbp, 2):.2f}",
                "temp_floor_10roi_gbp": f"{floor_total:.2f}" if (not blocking and floor_total > 0) else "",
                "source_script": SOURCE,
            }
        )
        trace_rows.append(
            build_h_floor_trace_row(
                inputs=inputs,
                result=result,
                source_script=SOURCE,
                asof_utc=asof_utc,
            )
        )

    _append_temp_floor_snapshot(snapshot_rows)
    append_h_floor_trace_rows(trace_rows)
    return floor_by_sku, blocked_by_sku


def _resolve_marketplace_id(listing_row: dict[str, str], cfg_marketplace_id: str) -> str:
    explicit = _norm(cfg_marketplace_id) or _norm(listing_row.get("marketplace_id", ""))
    if explicit:
        return explicit
    code = _norm(listing_row.get("marketplace", "")).upper()
    mapped = MARKETPLACE_CODE_TO_ID.get(code, "")
    if mapped:
        return mapped
    return os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")


def _phase1_market_payload_from_snapshots(
    *,
    sku: str,
    asin: str,
    marketplace_id: str,
    our_seller_id: str,
    listing_row: dict[str, str],
) -> tuple[dict[str, object], str]:
    global _NORM_TRACE_ACTIVE, _NORM_TRACE_LABEL
    _market_payload_checkpoint_raw("callsite_to_entry_before_before_target_emission_instruction")
    _market_payload_checkpoint_raw("market_payload_callsite_to_entry_gap_before_target_emission_call")
    _market_payload_checkpoint_raw("callsite_to_entry_after_before_target_emission_instruction")
    _market_payload_checkpoint_raw("callsite_to_entry_before_entry_window_enter_emission")
    _market_payload_checkpoint("market_payload_entry_window_enter")
    _market_payload_checkpoint_raw("callsite_to_entry_after_entry_window_enter_emission_return")
    _market_payload_checkpoint_raw("market_payload_callsite_to_entry_gap_after_target_emission_return")
    _market_payload_checkpoint_raw("market_payload_entry_window_to_after_enter_gap_entry")
    _market_payload_checkpoint_raw("caller_pre_checkpoint_call_for_before_first_instruction_checkpoint")
    _market_payload_checkpoint_raw("market_payload_entry_window_to_after_enter_gap_before_first_instruction")
    _market_payload_checkpoint_raw("caller_post_checkpoint_call_for_before_first_instruction_checkpoint")
    _market_payload_checkpoint_raw("market_payload_entry_window_to_after_enter_gap_before_target_emission_call")
    _market_payload_checkpoint_raw("market_payload_entry_to_setup_gap_after_enter")
    _market_payload_checkpoint_raw("market_payload_entry_window_to_after_enter_gap_after_target_emission_return")
    _market_payload_checkpoint_raw("market_payload_after_enter_to_setup_before_gap_entry")
    _market_payload_checkpoint_raw("market_payload_after_enter_to_setup_before_gap_before_first_instruction")
    _market_payload_checkpoint_raw("market_payload_after_enter_to_setup_before_gap_before_target_emission_call")
    _market_payload_checkpoint_raw("market_payload_entry_to_setup_gap_before_setup_before_emission")
    _market_payload_checkpoint_raw("market_payload_after_enter_to_setup_before_gap_after_target_emission_return")
    _market_payload_checkpoint_raw("market_payload_before_setup_before_to_setup_before_gap_entry")
    _market_payload_checkpoint_raw("market_payload_before_setup_before_to_setup_before_gap_before_first_instruction")
    _market_payload_checkpoint_raw("market_payload_before_setup_before_to_setup_before_gap_before_target_emission_call")
    _market_payload_checkpoint("market_payload_entry_window_first_local_setup_before")
    _market_payload_checkpoint_raw("market_payload_before_setup_before_to_setup_before_gap_after_target_emission_return")
    _market_payload_checkpoint_raw("market_payload_setup_before_to_after_setup_gap_entry")
    _market_payload_checkpoint_raw("market_payload_setup_before_to_after_setup_gap_before_first_instruction")
    _market_payload_checkpoint_raw("market_payload_setup_before_to_after_setup_gap_before_target_emission_call")
    _market_payload_checkpoint_raw("market_payload_setup_to_sku_gap_after_setup_before")
    _market_payload_checkpoint_raw("market_payload_setup_before_to_after_setup_gap_after_target_emission_return")
    _market_payload_checkpoint_raw("market_payload_after_setup_before_to_pre_target_gap_entry")
    _market_payload_checkpoint_raw("market_payload_after_setup_before_to_pre_target_gap_before_first_instruction")
    _market_payload_checkpoint_raw("market_payload_after_setup_before_to_pre_target_gap_before_target_emission_call")
    _market_payload_checkpoint_raw("market_payload_final_pre_sku_before_target_emission")
    _market_payload_checkpoint_raw("market_payload_after_setup_before_to_pre_target_gap_after_target_emission_return")
    _market_payload_checkpoint_raw("market_payload_pre_sku_before_target_gap_entry")
    _market_payload_checkpoint_raw("market_payload_pre_sku_before_target_gap_before_first_instruction")
    _market_payload_checkpoint_raw("market_payload_pre_sku_before_target_gap_before_target_emission_call")
    _market_payload_checkpoint_raw("market_payload_setup_to_sku_gap_before_sku_before_emission")
    _market_payload_checkpoint_raw("market_payload_pre_sku_before_target_gap_after_target_emission_return")
    _market_payload_checkpoint_raw("market_payload_final_pre_sku_after_target_emission")
    _market_payload_checkpoint_raw("market_payload_entry_to_setup_gap_after_setup_before_emission")
    _market_payload_checkpoint_raw("market_payload_setup_to_sku_gap_probe_pre_first_instruction")
    _market_payload_checkpoint_raw("market_payload_setup_to_sku_gap_probe_before_norm_sku_before_emission")
    _market_payload_checkpoint("market_payload_entry_window_norm_sku_before")
    _market_payload_checkpoint_raw("market_payload_setup_to_sku_gap_probe_after_norm_sku_before_emission_return")
    _market_payload_checkpoint_raw("market_payload_setup_to_sku_gap_probe_before_next_instruction")
    _market_payload_checkpoint("market_payload_entry_window_norm_sku_call_enter")
    _market_payload_checkpoint_raw("market_payload_setup_to_sku_gap_probe_after_next_instruction")
    _NORM_TRACE_ACTIVE = True
    _NORM_TRACE_LABEL = "sku"
    try:
        sku_norm_tmp = _norm(sku)
    finally:
        _NORM_TRACE_ACTIVE = False
        _NORM_TRACE_LABEL = ""
    _market_payload_checkpoint("market_payload_entry_window_norm_sku_call_return")
    sku_norm = sku_norm_tmp
    _market_payload_checkpoint("market_payload_entry_window_norm_sku_return_use")
    _market_payload_checkpoint_raw("market_payload_setup_to_sku_gap_after_sku_before_emission")
    _market_payload_checkpoint("market_payload_entry_window_norm_sku_after")
    _market_payload_checkpoint_raw("market_payload_sku_to_asin_gap_after_sku_after")
    _market_payload_checkpoint_raw("market_payload_sku_to_asin_gap_before_asin_before_emission")
    _market_payload_checkpoint("market_payload_entry_window_norm_asin_before")
    _market_payload_checkpoint_raw("market_payload_sku_to_asin_gap_after_asin_before_emission")
    _market_payload_checkpoint_raw("market_payload_asin_precall_after_asin_before")
    _market_payload_checkpoint_raw("market_payload_asin_precall_before_call_enter_emission")
    _market_payload_checkpoint("market_payload_entry_window_norm_asin_call_enter")
    _market_payload_checkpoint_raw("market_payload_asin_precall_after_call_enter_emission")
    _NORM_TRACE_ACTIVE = True
    _NORM_TRACE_LABEL = "asin"
    try:
        asin_norm_tmp = _norm(asin)
    finally:
        _NORM_TRACE_ACTIVE = False
        _NORM_TRACE_LABEL = ""
    _market_payload_checkpoint("market_payload_entry_window_norm_asin_call_return")
    asin_norm = asin_norm_tmp
    _market_payload_checkpoint("market_payload_entry_window_norm_asin_return_use")
    _market_payload_checkpoint("market_payload_entry_window_norm_asin_after")
    _market_payload_checkpoint("market_payload_entry_window_norm_marketplace_before")
    marketplace_id_norm = _norm(marketplace_id)
    _market_payload_checkpoint("market_payload_entry_window_norm_marketplace_after")
    _market_payload_checkpoint_raw("market_payload_gap_after_marketplace_norm_statement")
    _market_payload_checkpoint_raw("market_payload_gap_before_seller_before_call")
    _market_payload_checkpoint("market_payload_entry_window_norm_seller_before")
    _market_payload_checkpoint_raw("market_payload_gap_after_seller_before_call")
    _market_payload_checkpoint("market_payload_entry_window_norm_seller_call_enter")
    _NORM_TRACE_ACTIVE = True
    _NORM_TRACE_LABEL = "our_seller_id"
    try:
        seller_norm_tmp = _norm(our_seller_id)
    finally:
        _NORM_TRACE_ACTIVE = False
        _NORM_TRACE_LABEL = ""
    _market_payload_checkpoint("market_payload_entry_window_norm_seller_call_return")
    our_seller_id_norm = seller_norm_tmp
    _market_payload_checkpoint("market_payload_entry_window_norm_seller_return_use")
    _market_payload_checkpoint("market_payload_entry_window_norm_seller_after")
    _market_payload_checkpoint("market_payload_entry_window_first_local_setup_before_after_checkpoint")
    _market_payload_checkpoint(
        "market_payload_entry_window_first_local_setup_after",
        sku=sku_norm,
        asin=asin_norm,
        marketplace_id=marketplace_id_norm,
        seller_id=our_seller_id_norm,
    )

    def _fallback_rival_offers_from_recent_snapshot() -> list[dict[str, object]]:
        if not OFFER_SNAPSHOT_FACTS_PATH.exists():
            return []
        try:
            df = pd.read_csv(OFFER_SNAPSHOT_FACTS_PATH, dtype=str).fillna("")
        except Exception:
            return []
        if df.empty or "sku" not in df.columns:
            return []
        scoped = df.loc[df.get("sku", "").astype(str).str.strip().str.upper().eq(sku.upper())].copy()
        if scoped.empty:
            return []
        if "snapshot_ts_utc" in scoped.columns:
            scoped = scoped.sort_values("snapshot_ts_utc", ascending=False)
            latest_ts = str(scoped.iloc[0].get("snapshot_ts_utc", "")).strip()
            if latest_ts:
                scoped = scoped.loc[scoped.get("snapshot_ts_utc", "").astype(str).str.strip().eq(latest_ts)].copy()
        rival_rows: list[dict[str, object]] = []
        for _, rec in scoped.iterrows():
            seller = _norm(rec.get("seller_id_canonical", ""))
            if not seller or seller.upper() == our_seller_id.upper():
                continue
            listing_price = _to_float(rec.get("listing_price_gbp", ""))
            shipping_price = _to_float(rec.get("shipping_gbp", ""))
            landed_price = _to_float(rec.get("landed_price_gbp", ""))
            if listing_price is None and landed_price is not None and shipping_price is not None:
                listing_price = landed_price - shipping_price
            listing_price = listing_price if listing_price is not None else 0.0
            shipping_price = shipping_price if shipping_price is not None else 0.0
            min_days = _to_int(rec.get("min_delivery_days", ""))
            max_days = _to_int(rec.get("max_delivery_days", ""))
            fulf = _norm(rec.get("fulfilment_channel", "")).upper()
            rival_rows.append(
                {
                    "SellerId": seller,
                    "ListingPrice": {"Amount": listing_price},
                    "Shipping": {"Amount": shipping_price},
                    "ShippingTime": {"minimumDays": min_days or 0, "maximumDays": max_days or (min_days or 0)},
                    "IsFulfilledByAmazon": fulf in {"FBA", "AFN", "AMAZON"},
                    "IsPrime": _to_bool(rec.get("is_prime", "")),
                    "IsFeaturedOfferWinner": str(rec.get("is_featured_offer_winner", "")).strip() == "1",
                }
            )
        return rival_rows

    _market_payload_checkpoint(
        "market_payload_entry_window_before_listing_guard",
        listing_row_present="1" if bool(listing_row) else "0",
    )
    if not listing_row:
        _market_payload_checkpoint("market_payload_entry_window_listing_guard_return")
        return {"asin": asin, "marketplaceId": marketplace_id, "offers": []}, ""
    _market_payload_checkpoint("market_payload_entry_window_after_listing_guard")
    try:
        _market_payload_checkpoint("market_payload_entry_window_before_seller_path_derivation")
        seller_path = _latest_seller_snapshot()
        _market_payload_checkpoint(
            "market_payload_entry_window_after_seller_path_derivation",
            seller_snapshot_path=str(seller_path),
        )
        _market_payload_checkpoint("market_payload_entry_window_gap_stmt1_before")
        seller_path_exists = seller_path.exists()
        _market_payload_checkpoint(
            "market_payload_entry_window_gap_stmt1_after",
            seller_path_exists="1" if seller_path_exists else "0",
        )
        _market_payload_checkpoint("market_payload_entry_window_gap_call_enter")
        seller_path_text = str(seller_path)
        _market_payload_checkpoint(
            "market_payload_entry_window_gap_call_return",
            seller_snapshot_path=seller_path_text,
        )
        _market_payload_checkpoint("market_payload_entry_window_gap_before_read_checkpoint_stmt")
        _market_payload_checkpoint("market_payload_entry_window_before_seller_read_checkpoint")
        _market_payload_checkpoint(
            "market_payload_before_seller_snapshot_read_csv",
            seller_snapshot_path=seller_path_text,
        )
        df = pd.read_csv(seller_path, dtype=str).fillna("")
        _market_payload_checkpoint(
            "market_payload_after_seller_snapshot_read_csv",
            seller_snapshot_path=str(seller_path),
            seller_snapshot_rows=str(int(len(df.index))),
        )
    except Exception as exc:
        _market_payload_checkpoint(
            "market_payload_seller_snapshot_read_csv_except",
            seller_snapshot_path=str(seller_path) if "seller_path" in locals() else "",
            error_class=type(exc).__name__,
            reason=_norm(str(exc)),
        )
        df = pd.DataFrame()
    offers: list[dict[str, object]] = []
    scoped_row_count = 0
    try:
        _market_payload_checkpoint(
            "market_payload_scoped_filter_before_sku_in_columns",
            df_cols_count=str(int(len(df.columns))),
        )
        has_sku_col = "sku" in df.columns
        _market_payload_checkpoint(
            "market_payload_scoped_filter_after_sku_in_columns",
            has_sku_col="1" if has_sku_col else "0",
        )
        if has_sku_col:
            _market_payload_checkpoint("market_payload_scoped_filter_true_branch_enter")
            _market_payload_checkpoint("market_payload_scoped_filter_before_get_sku_series")
            sku_series_raw = df.get("sku", "")
            _market_payload_checkpoint("market_payload_scoped_filter_after_get_sku_series")
            _market_payload_checkpoint("market_payload_scoped_filter_before_astype")
            sku_series_str = sku_series_raw.astype(str)
            _market_payload_checkpoint("market_payload_scoped_filter_after_astype")
            _market_payload_checkpoint("market_payload_scoped_filter_before_strip")
            sku_series_stripped = sku_series_str.str.strip()
            _market_payload_checkpoint("market_payload_scoped_filter_after_strip")
            _market_payload_checkpoint("market_payload_scoped_filter_before_upper")
            sku_series_upper = sku_series_stripped.str.upper()
            _market_payload_checkpoint("market_payload_scoped_filter_after_upper")
            _market_payload_checkpoint("market_payload_scoped_filter_before_eq")
            scoped_mask = sku_series_upper.eq(sku.upper())
            _market_payload_checkpoint("market_payload_scoped_filter_after_eq")
            _market_payload_checkpoint("market_payload_scoped_filter_before_loc")
            scoped = df.loc[scoped_mask]
            _market_payload_checkpoint(
                "market_payload_scoped_filter_after_loc",
                scoped_rows=str(int(len(scoped.index))),
            )
            _market_payload_checkpoint("market_payload_scoped_filter_before_copy")
            scoped = scoped.copy()
            scoped_row_count = int(len(scoped.index))
            _market_payload_checkpoint(
                "market_payload_scoped_filter_after_copy",
                scoped_rows=str(int(len(scoped.index))),
            )
        else:
            _market_payload_checkpoint("market_payload_scoped_filter_else_branch_enter")
            scoped = df.head(0).copy()
            scoped_row_count = 0
            _market_payload_checkpoint(
                "market_payload_scoped_filter_else_branch_after_assign",
                scoped_rows=str(int(len(scoped.index))),
            )
        _market_payload_checkpoint(
            "market_payload_scoped_filter_before_after_scoped_filter_checkpoint",
            scoped_rows=str(int(len(scoped.index))),
        )
        _market_payload_checkpoint(
            "market_payload_after_scoped_filter",
            scoped_rows=str(int(len(scoped.index))),
        )
        _market_payload_checkpoint(
            "market_payload_before_scoped_iterrows",
            scoped_rows=str(int(len(scoped.index))),
        )

        def _append_offer_from_scoped_row(rec: pd.Series) -> None:
            seller_id = _norm(rec.get("seller_id", ""))
            if not seller_id:
                return
            listing_price = _to_float(rec.get("offer_price_gbp", ""))
            shipping_price = _to_float(rec.get("offer_shipping_price_gbp", ""))
            landed_price = _to_float(rec.get("offer_landed_price_gbp", ""))
            if listing_price is None and landed_price is not None and shipping_price is not None:
                listing_price = landed_price - shipping_price
            listing_price = listing_price if listing_price is not None else 0.0
            shipping_price = shipping_price if shipping_price is not None else 0.0
            min_days = _to_int(rec.get("min_delivery_days", ""))
            max_days = _to_int(rec.get("max_delivery_days", ""))
            fulf = _norm(rec.get("fulfilment_channel", "")).upper()
            offers.append(
                {
                    "SellerId": seller_id,
                    "ListingPrice": {"Amount": listing_price},
                    "Shipping": {"Amount": shipping_price},
                    "ShippingTime": {"minimumDays": min_days or 0, "maximumDays": max_days or (min_days or 0)},
                    "IsFulfilledByAmazon": fulf in {"FBA", "AFN", "AMAZON"},
                    "IsPrime": _to_bool(rec.get("is_prime", "")),
                    "IsFeaturedOfferWinner": False,
                }
            )

        _market_payload_checkpoint(
            "market_payload_post_iterrows_iter_create_before",
            scoped_rows=str(int(len(scoped.index))),
        )
        scoped_iter = scoped.iterrows()
        _market_payload_checkpoint(
            "market_payload_post_iterrows_iter_create_after",
            scoped_rows=str(int(len(scoped.index))),
        )
        _market_payload_checkpoint(
            "market_payload_post_iterrows_first_advance_before",
            scoped_rows=str(int(len(scoped.index))),
        )
        first_pair = next(scoped_iter, None)
        if first_pair is None:
            _market_payload_checkpoint(
                "market_payload_post_iterrows_zero_row_branch_enter",
                scoped_rows=str(int(len(scoped.index))),
            )
            _market_payload_checkpoint(
                "market_payload_post_iterrows_zero_row_branch_after",
                offers_rows=str(int(len(offers))),
            )
        else:
            _, first_rec = first_pair
            _market_payload_checkpoint(
                "market_payload_post_iterrows_first_advance_after",
                seller_id=_norm(first_rec.get("seller_id", "")),
            )
            _market_payload_checkpoint(
                "market_payload_first_scoped_row_enter",
                seller_id=_norm(first_rec.get("seller_id", "")),
            )
            _market_payload_checkpoint(
                "market_payload_post_iterrows_first_return_use_before",
                seller_id=_norm(first_rec.get("seller_id", "")),
            )
            _append_offer_from_scoped_row(first_rec)
            _market_payload_checkpoint(
                "market_payload_post_iterrows_first_return_use_after",
                offers_rows=str(int(len(offers))),
            )
            for _, rec in scoped_iter:
                _append_offer_from_scoped_row(rec)
    except Exception as exc:
        _market_payload_checkpoint(
            "market_payload_scoped_loop_except",
            error_class=type(exc).__name__,
            reason=_norm(str(exc)),
        )
        raise

    our_price = _to_float(listing_row.get("our_price", ""))
    if our_price is not None and not any(_norm(o.get("SellerId", "")).upper() == our_seller_id.upper() for o in offers):
        offers.append(
            {
                "SellerId": our_seller_id,
                "ListingPrice": {"Amount": our_price},
                "Shipping": {"Amount": 0.0},
                "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                "IsFulfilledByAmazon": True,
                "IsPrime": True,
                "IsFeaturedOfferWinner": False,
            }
        )
    # If current seller snapshot only has our offer, reuse the latest known rival snapshot rows.
    has_rival = any(_norm(o.get("SellerId", "")).upper() != our_seller_id.upper() for o in offers)
    if not has_rival:
        offers.extend(_fallback_rival_offers_from_recent_snapshot())

    def _offer_landed_price(offer: dict[str, object]) -> float | None:
        listing_amt = _to_float((offer.get("ListingPrice", {}) or {}).get("Amount"))
        shipping_amt = _to_float((offer.get("Shipping", {}) or {}).get("Amount"))
        if listing_amt is None and shipping_amt is None:
            return None
        return (listing_amt or 0.0) + (shipping_amt or 0.0)

    def _has_external_offer_at_or_below(price_gbp: float, *, tolerance: float) -> bool:
        for offer in offers:
            if _norm(offer.get("SellerId", "")).upper() == our_seller_id.upper():
                continue
            landed = _offer_landed_price(offer)
            if landed is None:
                continue
            if landed <= (price_gbp + tolerance):
                return True
        return False

    # When seller-snapshot rows are missing for this SKU, trust listing snapshot floor signals
    # if they indicate a cheaper rival than current known rivals.
    if scoped_row_count == 0:
        our_price_for_listing = _to_float(listing_row.get("our_price", ""))
        buy_box_candidate = _to_float(listing_row.get("buy_box_price", ""))
        lowest_fba_candidate = _to_float(listing_row.get("lowest_fba_price", ""))
        listing_candidates = [p for p in (buy_box_candidate, lowest_fba_candidate) if p is not None and p > 0]
        if listing_candidates:
            listing_floor_candidate = min(listing_candidates)
            if (
                our_price_for_listing is not None
                and listing_floor_candidate + 0.005 < our_price_for_listing
                and not _has_external_offer_at_or_below(listing_floor_candidate, tolerance=0.02)
            ):
                offers.append(
                    {
                        "SellerId": "LISTING_SNAPSHOT_FLOOR_RIVAL",
                        "ListingPrice": {"Amount": listing_floor_candidate},
                        "Shipping": {"Amount": 0.0},
                        "ShippingTime": {"minimumDays": 1, "maximumDays": 2},
                        "IsFulfilledByAmazon": True,
                        "IsPrime": True,
                        "IsFeaturedOfferWinner": False,
                    }
                )

    buy_box_price = _to_float(listing_row.get("buy_box_price", ""))
    if buy_box_price is not None and offers:
        winner_idx = None
        winner_gap = 999999.0
        for idx, offer in enumerate(offers):
            landed = _offer_landed_price(offer) or 0.0
            gap = abs(landed - buy_box_price)
            if gap < winner_gap:
                winner_gap = gap
                winner_idx = idx
        if winner_idx is not None and winner_gap <= 0.02:
            offers[winner_idx]["IsFeaturedOfferWinner"] = True

    payload = {"asin": asin, "marketplaceId": marketplace_id, "offers": offers}
    listings_observed_price = _to_num_text(listing_row.get("our_price", ""), "")
    return payload, listings_observed_price


def _seller_id_from_env() -> str:
    return (
        os.environ.get("SELLER_ID")
        or os.environ.get("SELLER_PARTNER_ID")
        or os.environ.get("MERCHANT_ID")
        or os.environ.get("SELLING_PARTNER_ID")
        or ""
    ).strip()


def _phase1_write_submitter(*, sku: str, marketplace_id: str, run_id: str):
    def _submit(target_price_gbp: str) -> dict[str, str]:
        try:
            helper_dir = H_LIVE_DIR / "tmp_h110_spapi_write_submit"
            helper_dir.mkdir(parents=True, exist_ok=True)
            token = f"{run_id}.{sku}.{os.getpid()}.{time.time_ns()}"
            input_path = helper_dir / f"in.{token}.json"
            output_path = helper_dir / f"out.{token}.json"
            stdout_path = helper_dir / f"stdout.{token}.log"
            stderr_path = helper_dir / f"stderr.{token}.log"
            req = {
                "run_id": run_id,
                "sku": sku,
                "marketplace_id": marketplace_id,
                "target_price_gbp": _norm(target_price_gbp),
                "product_type": os.environ.get("H_DEFAULT_PRODUCT_TYPE", "PRODUCT"),
            }
            _atomic_write_text(input_path, json.dumps(req, ensure_ascii=True) + "\n")
            cmd = _self_python_cmd(
                "--spapi-write-subcall",
                "--spapi-write-input",
                str(input_path),
                "--spapi-write-output",
                str(output_path),
            )
            creation_flags = 0
            creation_flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            creation_flags |= int(getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
            proc: subprocess.Popen[str] | None = None
            try:
                with stdout_path.open("wb") as out_fh, stderr_path.open("wb") as err_fh:
                    proc = _popen_hidden(
                        cmd,
                        cwd=str(ROOT),
                        stdin=subprocess.DEVNULL,
                        stdout=out_fh,
                        stderr=err_fh,
                        close_fds=True,
                        creationflags=creation_flags,
                        env=os.environ.copy(),
                    )
            except PermissionError:
                with stdout_path.open("wb") as out_fh, stderr_path.open("wb") as err_fh:
                    proc = _popen_hidden(
                        cmd,
                        cwd=str(ROOT),
                        stdin=subprocess.DEVNULL,
                        stdout=out_fh,
                        stderr=err_fh,
                        close_fds=True,
                        creationflags=0,
                        env=os.environ.copy(),
                    )
            if proc is None:
                raise RuntimeError("spapi_write_subcall_spawn_missing_proc")
            timeout_seconds = max(_env_int("H110_SPAPI_WRITE_SUBCALL_TIMEOUT_SECONDS", 45), 10)
            try:
                rc = int(proc.wait(timeout=float(timeout_seconds)))
            except subprocess.TimeoutExpired:
                with contextlib.suppress(Exception):
                    proc.terminate()
                with contextlib.suppress(Exception):
                    proc.wait(timeout=2.0)
                if proc.poll() is None:
                    with contextlib.suppress(Exception):
                        proc.kill()
                    with contextlib.suppress(Exception):
                        proc.wait(timeout=2.0)
                rc = 124
            payload: dict[str, object] = {}
            if output_path.exists():
                try:
                    raw = json.loads(output_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        payload = raw
                except Exception:
                    payload = {}
            if rc == 0 and payload:
                return {
                    "ok": _norm(payload.get("ok", "0")),
                    "http_status": _norm(payload.get("http_status", "")),
                    "submission_id": _norm(payload.get("submission_id", "")),
                    "response_text": _norm(payload.get("response_text", "")),
                }
            stderr_tail = ""
            if stderr_path.exists():
                with contextlib.suppress(Exception):
                    stderr_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-500:]
            reason = (
                f"spapi_write_subcall_failed:rc={rc}:output_exists={'1' if output_path.exists() else '0'}"
            )
            if _norm(stderr_tail):
                reason = f"{reason}:stderr_tail={_norm(stderr_tail)[:180]}"
            return {"ok": "0", "http_status": "", "submission_id": "", "response_text": reason}
        except Exception as exc:
            return {"ok": "0", "http_status": "", "submission_id": "", "response_text": str(exc)}

    return _submit


def _run_spapi_write_subcall_mode(*, input_path: Path, output_path: Path) -> int:
    payload: dict[str, object]
    try:
        req_raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(req_raw, dict):
            raise RuntimeError("spapi_write_subcall_input_not_object")
        req = req_raw
    except Exception as exc:
        payload = {
            "status": "failed",
            "ok": "0",
            "http_status": "",
            "submission_id": "",
            "response_text": f"input_read_error:{type(exc).__name__}:{exc}",
        }
        _atomic_write_text(output_path, json.dumps(payload, ensure_ascii=True) + "\n")
        return 1

    run_id = _norm(req.get("run_id", ""))
    sku = _norm(req.get("sku", "")).upper()
    marketplace_id = _norm(req.get("marketplace_id", ""))
    target_price_gbp = _norm(req.get("target_price_gbp", ""))
    product_type = _norm(req.get("product_type", "")) or "PRODUCT"
    try:
        load_dotenv_if_missing()
        access_token = get_lwa_access_token()
        seller_id = _seller_id_from_env()
        if not seller_id:
            raise RuntimeError("SELLER_ID missing from environment")
        result = patch_listings_item_price(
            access_token=access_token,
            seller_id=seller_id,
            sku=sku,
            marketplace_id=marketplace_id,
            product_type=product_type,
            target_price_gbp=target_price_gbp,
            run_id=run_id,
            source_script=SOURCE,
            spapi_base_url=SPAPI_BASE_URL,
        )
        payload = {
            "status": "ok",
            "ok": _norm(result.get("ok", "0")),
            "http_status": _norm(result.get("http_status", "")),
            "submission_id": _norm(result.get("submission_id", "")),
            "response_text": _norm(result.get("response_text", "")),
        }
    except Exception as exc:
        payload = {
            "status": "failed",
            "ok": "0",
            "http_status": "",
            "submission_id": "",
            "response_text": f"{type(exc).__name__}:{exc}",
        }
    _atomic_write_text(output_path, json.dumps(payload, ensure_ascii=True) + "\n")
    return 0


def _phase1_post_write_price_lookup(*, sku: str, marketplace_id: str, run_id: str):
    def _lookup() -> str:
        try:
            load_dotenv_if_missing()
            access_token = get_lwa_access_token()
            seller_id = _seller_id_from_env()
            if not seller_id:
                return ""
            payload = fetch_our_offer_prices(
                [sku],
                marketplace_id=marketplace_id,
                access_token=access_token,
                seller_id=seller_id,
                run_id=run_id,
                script_name=SOURCE,
                sleep_sec=0.0,
                timeout=8,
            )
        except Exception:
            return ""
        row = payload.get(sku, {}) if isinstance(payload, dict) else {}
        return _norm(row.get("price", ""))

    return _lookup


def _run_one_sku(
    *,
    cfg: dict,
    sku: str,
    read_only: bool,
    run_id: str,
    now_utc: datetime,
    manual_cap_by_sku: dict[str, str],
    manual_cap_by_asin: dict[str, str],
    temp_floor_by_sku: dict[str, str],
    temp_floor_blockers_by_sku: dict[str, str],
    daily_boundary_lock_by_sku: dict[str, dict[str, str]],
    boundary_lock_date_utc: str,
    universe_row: dict[str, str],
    listing_map: dict[str, dict[str, str]],
    listing_snapshot_path: str,
    seller_snapshot_path: str,
    reentry_price_discovery_active: bool = False,
    reentry_event: bool = False,
    inbound_price_discovery_active: bool = False,
) -> dict[str, str]:
    sku = _norm(sku).upper()
    if not sku:
        raise RuntimeError("[H110] empty sku in run_one_sku")
    started_at = datetime.now(timezone.utc)
    _append_sku_lifecycle_rows(
        [
            {
                "event_ts_utc": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "run_id": run_id,
                "sku": sku,
                "event": "start",
            }
        ]
    )

    def _finalize_lifecycle(
        *,
        event: str,
        decision: str = "",
        write_status: str = "",
        reason_codes_csv: str = "",
        error: str = "",
    ) -> None:
        now = datetime.now(timezone.utc)
        elapsed_ms = max(int((now - started_at).total_seconds() * 1000), 0)
        _append_sku_lifecycle_rows(
            [
                {
                    "event_ts_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "run_id": run_id,
                    "sku": sku,
                    "event": event,
                    "elapsed_ms": str(elapsed_ms),
                    "decision": decision,
                    "write_status": write_status,
                    "reason_codes_csv": reason_codes_csv,
                    "error": error,
                }
            ]
        )

    def _return_out_row(out_row: dict[str, str]) -> dict[str, str]:
        _progress(
            "h110 sku_exec_exit_normal",
            sku=sku,
            run_id=run_id,
            decision=_norm(out_row.get("decision", "")),
            write_status=_norm(out_row.get("write_status", "")),
        )
        return out_row

    _progress("h110 run_one_sku start", sku=sku, run_id=run_id)
    _checkpoint("run_one_sku_start", sku=sku, run_id=run_id)
    _progress("h110 sku_exec_enter", sku=sku, run_id=run_id)
    _progress("parent_continuation_enter", sku=sku, run_id=run_id, stage="run_one_sku")
    _progress("completion_convergence_enter", sku=sku, run_id=run_id, stage="helper_boundary")
    _checkpoint("completion_convergence_enter", sku=sku, run_id=run_id)
    _progress("completion_convergence_boundary_enter", sku=sku, run_id=run_id, stage="post_enter")
    _checkpoint("completion_convergence_boundary_enter", sku=sku, run_id=run_id)
    _progress("owner_worker_continuation_enter", sku=sku, run_id=run_id, stage="post_pre_result")

    listing_row = listing_map.get(sku, {})
    pilot_owner_single_path = _to_bool(os.environ.get("H110_PILOT_OWNER_SINGLE_PATH", "1"), default=True)
    pre_result_worker_enabled = _to_bool(os.environ.get("H110_PRE_RESULT_WORKER_ENABLED", "0"), default=False)
    pre_result_worker_first_sku_only = _to_bool(
        os.environ.get("H110_PRE_RESULT_WORKER_FIRST_SKU_ONLY", "1"),
        default=True,
    )
    is_first_sku = bool(run_id.endswith("_01"))
    use_pre_result_worker = bool(
        (not pilot_owner_single_path)
        and pre_result_worker_enabled
        and ((not pre_result_worker_first_sku_only) or is_first_sku)
    )
    try:
        _progress(
            "completion_convergence_boundary_before_helper_dispatch",
            sku=sku,
            run_id=run_id,
            owner_payload_mode=_norm(os.environ.get("H110_EXECUTION_OWNER_PAYLOAD_MODE", "inline")).lower() or "inline",
        )
        _checkpoint(
            "completion_convergence_boundary_before_helper_dispatch",
            sku=sku,
            run_id=run_id,
        )
        if pilot_owner_single_path:
            _progress("owner_worker_payload_assembly_start", run_id=run_id, sku=sku, mode="single_owner")
            req_inline = {
                "run_id": run_id,
                "sku": sku,
                "cfg_marketplace_id": _norm(_cfg_get(cfg, "marketplace_id", default="")),
                "cfg_sku": _norm(_cfg_get(cfg, "sku", default="")),
                "cfg_asin": _norm(_cfg_get(cfg, "asin", default="")),
                "cfg_seller_id": _norm(_cfg_get(cfg, "seller_id", default="")),
                "universe_row": universe_row,
                "listing_row": listing_row,
                "listing_snapshot_path": _norm(listing_snapshot_path),
                "seller_snapshot_path": _norm(seller_snapshot_path),
            }
            # Active default: inline payload assembly inside payload-worker-owner.
            # Nested payload-worker remains rollback-only via explicit env override.
            owner_payload_mode = _norm(os.environ.get("H110_EXECUTION_OWNER_PAYLOAD_MODE", "inline")).lower() or "inline"
            direct_owner_enabled = _to_bool(os.environ.get("H110_DIRECT_ARTIFACT_OWNER_ENABLED", "0"), default=False)
            if owner_payload_mode == "inline":
                _progress("payload_worker_owner_payload_assembly_start", run_id=run_id, sku=sku, mode="inline")
                direct_owner_first_sku_handoff_enabled = _to_bool(
                    os.environ.get("H110_DIRECT_ARTIFACT_OWNER_FIRST_SKU_HANDOFF_ENABLED", "0"),
                    default=False,
                )
                direct_owner_first_sku_handoff_rollback_enabled = _to_bool(
                    os.environ.get("H110_DIRECT_ARTIFACT_OWNER_FIRST_SKU_HANDOFF_ROLLBACK_ENABLED", "0"),
                    default=False,
                )
                if (
                    direct_owner_enabled
                    and direct_owner_first_sku_handoff_enabled
                    and direct_owner_first_sku_handoff_rollback_enabled
                    and is_first_sku
                ):
                    root_run_id = _norm(run_id.split("_", 1)[0]) or run_id
                    raise _spawn_direct_artifact_owner_handoff(
                        root_run_id=root_run_id,
                        sku_run_id=run_id,
                        sku=sku,
                        helper_req=req_inline,
                    )
                _progress(
                    "helper_dispatch_call_enter",
                    run_id=run_id,
                    sku=sku,
                    helper_fn="_run_sku_pre_result_helper_contract",
                )
                _checkpoint(
                    "helper_dispatch_call_enter",
                    run_id=run_id,
                    sku=sku,
                )
                helper_contract = _run_sku_pre_result_helper_contract(req_inline)
                _progress(
                    "helper_dispatch_call_return",
                    run_id=run_id,
                    sku=sku,
                    helper_fn="_run_sku_pre_result_helper_contract",
                    contract_type=type(helper_contract).__name__,
                )
                _checkpoint(
                    "helper_dispatch_call_return",
                    run_id=run_id,
                    sku=sku,
                )
                _progress("payload_worker_valid", run_id=run_id, sku=sku, mode="inline_fallback")
                _progress("payload_worker_owner_payload_assembly_done", run_id=run_id, sku=sku, mode="inline")
            elif owner_payload_mode in {"payload_worker", "worker"}:
                helper_contract = _invoke_owner_worker_payload_worker(
                    run_id=run_id,
                    sku=sku,
                    cfg=cfg,
                    universe_row=universe_row,
                    listing_row=listing_row,
                    listing_snapshot_path=listing_snapshot_path,
                    seller_snapshot_path=seller_snapshot_path,
                )
            elif owner_payload_mode == "legacy":
                owner_pre_result_mode = _norm(os.environ.get("H110_OWNER_WORKER_PRE_RESULT_MODE", "subprocess")) or "subprocess"
                helper_contract = _run_owner_worker_pre_result_contract(
                    run_id=run_id,
                    sku=sku,
                    req=req_inline,
                    mode=owner_pre_result_mode,
                )
                _progress(
                    "payload_worker_valid",
                    run_id=run_id,
                    sku=sku,
                    mode=f"legacy_{owner_pre_result_mode}",
                )
            else:
                _progress(
                    "payload_worker_failed",
                    run_id=run_id,
                    sku=sku,
                    reason=f"invalid_mode:{owner_payload_mode}",
                )
                raise RuntimeError(f"payload_worker_failed:invalid_mode:{owner_payload_mode}")
            _progress(
                "helper_dispatch_return_before_use",
                run_id=run_id,
                sku=sku,
                contract_type=type(helper_contract).__name__,
            )
            _checkpoint(
                "helper_dispatch_return_before_use",
                run_id=run_id,
                sku=sku,
            )
            if not isinstance(helper_contract, dict):
                _progress("payload_worker_failed", run_id=run_id, sku=sku, reason="helper_contract_not_object")
                raise RuntimeError("completion_convergence_failed:helper_dispatch_return_use:helper_contract_not_object")
            _progress(
                "helper_dispatch_return_after_use",
                run_id=run_id,
                sku=sku,
                contract_type=type(helper_contract).__name__,
            )
            _checkpoint(
                "helper_dispatch_return_after_use",
                run_id=run_id,
                sku=sku,
            )
            _progress("owner_worker_payload_assembly_done", run_id=run_id, sku=sku, mode=owner_payload_mode)
            _progress(
                "full_worker_continuation_after_pre_result_worker",
                run_id=run_id,
                sku=sku,
                reason=f"single_owner_{owner_payload_mode}_mode",
            )
        elif use_pre_result_worker:
            helper_contract = _invoke_pre_result_worker(
                run_id=run_id,
                sku=sku,
                cfg=cfg,
                universe_row=universe_row,
                listing_row=listing_row,
                listing_snapshot_path=listing_snapshot_path,
                seller_snapshot_path=seller_snapshot_path,
            )
        else:
            helper_contract = _invoke_sku_pre_result_helper(
                run_id=run_id,
                sku=sku,
                cfg=cfg,
                universe_row=universe_row,
                listing_row=listing_row,
                listing_snapshot_path=listing_snapshot_path,
                seller_snapshot_path=seller_snapshot_path,
            )
        _progress(
            "completion_convergence_boundary_after_helper_dispatch",
            sku=sku,
            run_id=run_id,
            contract_type=type(helper_contract).__name__,
        )
        _checkpoint(
            "completion_convergence_boundary_after_helper_dispatch",
            sku=sku,
            run_id=run_id,
        )
    except _DirectArtifactOwnershipHandoff:
        raise
    except BaseException as exc:
        reason_text = _norm(str(exc))
        if _LAST_COMPLETION_CHECKPOINT == "helper_dispatch_call_enter":
            reason_text = (
                f"completion_convergence_failed:helper_dispatch_call:inline_helper_call_no_return:"
                f"{type(exc).__name__}:{reason_text[:160]}"
            )
        elif _LAST_COMPLETION_CHECKPOINT in {"helper_dispatch_call_return", "helper_dispatch_return_before_use"}:
            reason_text = (
                f"completion_convergence_failed:helper_dispatch_return_use:"
                f"{type(exc).__name__}:{reason_text[:160]}"
            )
        _progress(
            "helper_dispatch_return_failed",
            run_id=run_id,
            sku=sku,
            stage=_LAST_COMPLETION_CHECKPOINT or "unknown",
            error_type=type(exc).__name__,
            reason=reason_text[:240] or "helper_dispatch_return_exception",
        )
        _checkpoint(
            "helper_dispatch_return_failed",
            run_id=run_id,
            sku=sku,
            stage=_LAST_COMPLETION_CHECKPOINT or "unknown",
        )
        _progress(
            "completion_convergence_boundary_helper_failed",
            run_id=run_id,
            sku=sku,
            stage="helper_dispatch",
            error_type=type(exc).__name__,
            reason=reason_text[:240] or "helper_dispatch_exception",
        )
        _checkpoint(
            "completion_convergence_boundary_helper_failed",
            run_id=run_id,
            sku=sku,
            stage="helper_dispatch",
        )
        _progress(
            "owner_worker_continuation_failed",
            run_id=run_id,
            sku=sku,
            stage="pre_result_boundary",
            error_type=type(exc).__name__,
            reason=reason_text[:240] or "pre_result_boundary_exception",
        )
        if "pre_result_ready_contract_invalid" in reason_text or "pre_result_ready_contract_failed" in reason_text:
            _progress(
                "full_worker_terminalization_after_ready_reader_failure",
                run_id=run_id,
                sku=sku,
                error_type=type(exc).__name__,
                error=reason_text[:240],
            )
        if "pre_result_worker_contract_invalid" in reason_text or "pre_result_worker_contract_failed" in reason_text:
            _progress(
                "full_worker_terminalization_after_pre_result_worker_failure",
                run_id=run_id,
                sku=sku,
                error_type=type(exc).__name__,
                error=reason_text[:240],
            )
        if "payload_worker_failed" in reason_text:
            _progress(
                "owner_worker_terminalization_after_payload_contract_failure",
                run_id=run_id,
                sku=sku,
                error_type=type(exc).__name__,
                error=reason_text[:240],
            )
        if "completion_convergence_failed:market_payload_subcall_" in reason_text:
            _progress(
                "owner_worker_terminalization_after_market_payload_subcall_failure",
                run_id=run_id,
                sku=sku,
                error_type=type(exc).__name__,
                error=reason_text[:240],
            )
            raise RuntimeError(reason_text[:240]) from exc
        if "completion_convergence_failed:market_payload_probe_boundary_" in reason_text:
            _progress(
                "owner_terminalization_after_market_payload_probe_boundary_failure",
                run_id=run_id,
                sku=sku,
                error_type=type(exc).__name__,
                error=reason_text[:240],
            )
            raise RuntimeError(reason_text[:240]) from exc
        if "completion_convergence_failed:probe_boundary_read_" in reason_text:
            _progress(
                "owner_terminalization_after_probe_boundary_read_failure",
                run_id=run_id,
                sku=sku,
                error_type=type(exc).__name__,
                error=reason_text[:240],
            )
            raise RuntimeError(reason_text[:240]) from exc
        if "completion_convergence_failed:owner_post_subcall_boundary_failed:" in reason_text:
            _progress(
                "owner_post_subcall_failed",
                run_id=run_id,
                sku=sku,
                error_type=type(exc).__name__,
                reason=reason_text[:240],
            )
            raise RuntimeError(reason_text[:240]) from exc
        if "completion_convergence_failed:market_payload_read_boundary_" in reason_text:
            _progress(
                "owner_terminalization_after_market_payload_read_boundary_failure",
                run_id=run_id,
                sku=sku,
                error_type=type(exc).__name__,
                error=reason_text[:240],
            )
            raise RuntimeError(reason_text[:240]) from exc
        _progress(
            "completion_convergence_failed",
            sku=sku,
            run_id=run_id,
            stage="helper_acceptance_boundary",
            error_type=type(exc).__name__,
            error=reason_text[:240],
        )
        _progress(
            "parent_continuation_abnormal_exit",
            sku=sku,
            run_id=run_id,
            stage="helper_acceptance_boundary",
            error_type=type(exc).__name__,
            error=reason_text[:240],
        )
        if reason_text.startswith("completion_convergence_failed:"):
            raise RuntimeError(reason_text[:240]) from exc
        raise RuntimeError(
            f"completion_convergence_failed:boundary_helper_dispatch:{type(exc).__name__}:{reason_text[:180]}"
        ) from exc
    _progress(
        "completion_convergence_boundary_before_helper_accept",
        sku=sku,
        run_id=run_id,
        contract_type=type(helper_contract).__name__,
    )
    _checkpoint(
        "completion_convergence_boundary_before_helper_accept",
        sku=sku,
        run_id=run_id,
    )
    helper_status = _norm(helper_contract.get("status", "")).lower()
    helper_reason = _norm(helper_contract.get("reason", ""))
    _progress(
        "owner_post_subcall_before_convergence_after_helper",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status or "missing",
        helper_reason=helper_reason,
    )
    _progress(
        "parent_continuation_after_helper",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status or "missing",
        helper_reason=helper_reason,
    )
    _progress(
        "completion_convergence_after_helper",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status or "missing",
        helper_reason=helper_reason,
    )
    _checkpoint(
        "completion_convergence_after_helper",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status or "missing",
    )
    _progress(
        "completion_convergence_boundary_after_helper",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status or "missing",
        helper_reason=helper_reason,
    )
    _checkpoint(
        "completion_convergence_boundary_after_helper",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status or "missing",
    )
    _progress(
        "owner_post_subcall_after_convergence_after_helper",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status or "missing",
        helper_reason=helper_reason,
    )
    if helper_status == "skip":
        _progress(
            "completion_convergence_boundary_after_helper_accept",
            sku=sku,
            run_id=run_id,
            helper_status=helper_status,
            helper_reason=helper_reason,
        )
        _checkpoint(
            "completion_convergence_boundary_after_helper_accept",
            sku=sku,
            run_id=run_id,
            helper_status=helper_status,
        )
        out_row_raw = helper_contract.get("out_row", {})
        if not isinstance(out_row_raw, dict):
            _progress(
                "sku_helper_result_invalid",
                run_id=run_id,
                sku=sku,
                reason="skip_contract_missing_out_row",
            )
            _progress("sku_helper_stage_failed", run_id=run_id, sku=sku, reason="skip_contract_missing_out_row")
            raise RuntimeError("sku_helper_stage_failed:skip_contract_missing_out_row")
        out_row = {str(k): _norm(v) for k, v in out_row_raw.items()}
        out_row["phase1_boundary_lock_date"] = boundary_lock_date_utc
        if _norm(out_row.get("decision", "")).lower() == "skip_no_market_data":
            _progress(
                "h110 market_data_decision",
                sku=sku,
                today_utc=now_utc.strftime("%Y-%m-%d"),
                listing_snapshot_path=listing_snapshot_path,
                seller_snapshot_path=seller_snapshot_path,
                listing_row_exists="0",
                reason="SKIP_NO_MARKET_DATA",
            )
        elif _norm(out_row.get("decision", "")).lower() == "skip_no_active_offer":
            _progress(
                "h110 market_data_decision",
                sku=sku,
                today_utc=now_utc.strftime("%Y-%m-%d"),
                listing_snapshot_path=listing_snapshot_path,
                seller_snapshot_path=seller_snapshot_path,
                listing_row_exists="1",
                active_price_exists="0",
                reason="SKIP_NO_ACTIVE_OFFER",
            )
        _finalize_lifecycle(
            event="finish",
            decision=_norm(out_row.get("decision", "")),
            write_status=_norm(out_row.get("write_status", "")),
            reason_codes_csv=_norm(out_row.get("reason_codes_csv", "")),
        )
        return _return_out_row(out_row)
    if helper_status != "ok":
        narrowed_reason = helper_reason or "helper_status_not_ok"
        _progress(
            "completion_convergence_boundary_helper_failed",
            sku=sku,
            run_id=run_id,
            stage="helper_accept",
            reason=narrowed_reason,
        )
        _checkpoint(
            "completion_convergence_boundary_helper_failed",
            sku=sku,
            run_id=run_id,
            stage="helper_accept",
        )
        _progress(
            "completion_convergence_boundary_failed",
            sku=sku,
            run_id=run_id,
            stage="after_helper",
            reason=narrowed_reason,
        )
        _checkpoint(
            "completion_convergence_boundary_failed",
            sku=sku,
            run_id=run_id,
            stage="after_helper",
        )
        _progress(
            "completion_convergence_failed",
            sku=sku,
            run_id=run_id,
            stage="helper_status_validate",
            reason=narrowed_reason,
        )
        _progress(
            "sku_helper_stage_failed",
            run_id=run_id,
            sku=sku,
            reason=narrowed_reason,
        )
        raise RuntimeError(f"completion_convergence_failed:boundary_helper_accept:{narrowed_reason[:180]}")
    _progress(
        "completion_convergence_boundary_after_helper_accept",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status,
        helper_reason=helper_reason,
    )
    _checkpoint(
        "completion_convergence_boundary_after_helper_accept",
        sku=sku,
        run_id=run_id,
        helper_status=helper_status,
    )

    market_data_present = _norm(helper_contract.get("market_data_present", "0")) or "0"
    write_effective = _to_bool(_norm(helper_contract.get("write_effective", "0")), default=False)
    repricing_enabled = _to_bool(_norm(helper_contract.get("repricing_enabled", "0")), default=False)
    writer_mode = _norm(helper_contract.get("writer_mode", "READ_ONLY")) or "READ_ONLY"
    asin = _norm(helper_contract.get("asin", ""))
    marketplace_id = _norm(helper_contract.get("marketplace_id", ""))
    seller_id = _norm(helper_contract.get("seller_id", ""))
    _progress("owner_worker_result_build_start", sku=sku, run_id=run_id, stage="helper_payload_extract")
    _progress("completion_convergence_result_build_start", sku=sku, run_id=run_id, stage="helper_payload_extract")
    _checkpoint("completion_convergence_result_build_start", sku=sku, run_id=run_id)
    _progress("completion_convergence_boundary_result_build_start", sku=sku, run_id=run_id, stage="helper_payload_extract")
    _checkpoint("completion_convergence_boundary_result_build_start", sku=sku, run_id=run_id)
    try:
        payload_raw = helper_contract.get("payload", {})
        if not isinstance(payload_raw, dict):
            raise RuntimeError("payload_not_object")
        payload = payload_raw
    except BaseException as exc:
        narrowed_reason = _norm(str(exc)) or type(exc).__name__
        _progress(
            "completion_convergence_boundary_failed",
            sku=sku,
            run_id=run_id,
            stage="result_build",
            reason=narrowed_reason[:240],
        )
        _checkpoint(
            "completion_convergence_boundary_failed",
            sku=sku,
            run_id=run_id,
            stage="result_build",
        )
        _progress(
            "completion_convergence_failed",
            sku=sku,
            run_id=run_id,
            stage="result_build",
            reason=narrowed_reason[:240],
        )
        _progress(
            "sku_helper_result_invalid",
            run_id=run_id,
            sku=sku,
            reason=narrowed_reason[:240],
        )
        _progress("sku_helper_stage_failed", run_id=run_id, sku=sku, reason=narrowed_reason[:240])
        raise RuntimeError(f"completion_convergence_failed:boundary_result_build:{narrowed_reason[:180]}") from exc
    _progress("owner_worker_result_build_done", sku=sku, run_id=run_id, stage="helper_payload_extract")
    _progress("completion_convergence_result_build_done", sku=sku, run_id=run_id, stage="helper_payload_extract")
    _checkpoint("completion_convergence_result_build_done", sku=sku, run_id=run_id)
    _progress("completion_convergence_boundary_result_build_done", sku=sku, run_id=run_id, stage="helper_payload_extract")
    _checkpoint("completion_convergence_boundary_result_build_done", sku=sku, run_id=run_id)
    listings_observed_price = _norm(helper_contract.get("listings_observed_price", ""))
    _progress("result_payload_build_enter", sku=sku, run_id=run_id, stage="sku_market_payload_contract")
    _progress("result_payload_build_exit", sku=sku, run_id=run_id, stage="sku_market_payload_contract")

    default_hard_floor = _to_num_text(_cfg_get(cfg, "boundaries", "hard_floor_gbp", default="0.00"), "0.00")
    manual_cap_candidate = manual_cap_by_sku.get(sku) or manual_cap_by_asin.get(asin) or ""
    temp_floor_resolved = temp_floor_by_sku.get(sku, "")
    floor_blockers_csv = _norm(temp_floor_blockers_by_sku.get(sku, ""))
    if temp_floor_resolved:
        temp_floor_num = _to_float(temp_floor_resolved) or 0.0
        hard_floor_candidate = f"{temp_floor_num:.2f}"
    else:
        hard_floor_candidate = default_hard_floor

    lock_entry = daily_boundary_lock_by_sku.get(sku)
    lock_hard_floor = _norm((lock_entry or {}).get("hard_floor_gbp", ""))
    lock_manual_cap = _norm((lock_entry or {}).get("manual_cap_gbp", ""))
    using_daily_lock = bool(lock_hard_floor and lock_manual_cap)
    # Root-cause guard: if today's lock no longer matches fresh floor inputs, do not pin stale floor.
    if using_daily_lock and hard_floor_candidate:
        lock_floor_num = _to_float(lock_hard_floor)
        fresh_floor_num = _to_float(hard_floor_candidate)
        if lock_floor_num is not None and fresh_floor_num is not None:
            if abs(lock_floor_num - fresh_floor_num) >= 0.01:
                using_daily_lock = False
    if using_daily_lock:
        hard_floor_resolved = lock_hard_floor
        manual_cap_resolved = lock_manual_cap
    else:
        hard_floor_resolved = hard_floor_candidate
        manual_cap_resolved = manual_cap_candidate

    today = now_utc.strftime("%Y-%m-%d")
    if floor_blockers_csv:
        latest_daily_after = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
        daily_missing = "1" if _norm(latest_daily_after.get("date_utc", "")) != today else "0"
        out_row = {
            "phase1_pilot": "1",
            "phase1_sku": sku,
            "phase1_asin": asin,
            "daily_intel_missing_for_today": daily_missing,
            "last_executioner_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "executioner_probe_type": "hold",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "FLOOR_INPUT_MISSING_HOLD",
            "writer_mode": writer_mode,
            "hard_floor_applied_gbp": "",
            "manual_cap_applied_gbp": manual_cap_resolved,
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": ",".join([floor_blockers_csv, "H_FLOOR_INPUT_BLOCKED_NO_WRITE"]).strip(","),
            "phase1_boundary_lock_mode": "reused" if using_daily_lock else "set_pending",
            "phase1_boundary_lock_date": boundary_lock_date_utc,
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
            "market_data_present": market_data_present,
            "write_effective": "1" if write_effective else "0",
            "repricing_enabled": "1" if repricing_enabled else "0",
            "universe_reason_code": _norm(universe_row.get("reason_code", "")),
            "decision": "skip_floor_input_missing",
        }
        _finalize_lifecycle(
            event="finish",
            decision=_norm(out_row.get("decision", "")),
            write_status=_norm(out_row.get("write_status", "")),
            reason_codes_csv=_norm(out_row.get("reason_codes_csv", "")),
        )
        return _return_out_row(out_row)

    def _refresh_daily_intel_once() -> None:
        now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        phase1_main_loop.run_a_cycle(
            sku=sku,
            now_utc=now_iso,
            compliance_anchor_gbp=_cfg_get(
                cfg,
                "daily_intel",
                "compliance_anchor_gbp",
                default=_cfg_get(cfg, "boundaries", "manual_cap_gbp", default=listing_row.get("our_price", "0.00")),
            ),
            policy_buffer_pct=_cfg_get(cfg, "boundaries", "policy_buffer_pct", default="0.03"),
            manual_cap_gbp=manual_cap_resolved,
            foep_price_gbp=_cfg_get(cfg, "daily_intel", "foep_price_gbp", default=listing_row.get("buy_box_price", "")),
            foep_status=_cfg_get(cfg, "daily_intel", "foep_status", default="MISSING"),
            foep_last_refresh_utc=_cfg_get(cfg, "daily_intel", "foep_last_refresh_utc", default=now_iso),
            cpt_gbp=_cfg_get(cfg, "daily_intel", "cpt_gbp", default=""),
            cpt_last_refresh_utc=_cfg_get(cfg, "daily_intel", "cpt_last_refresh_utc", default=now_iso),
            cpt_status=_cfg_get(cfg, "daily_intel", "cpt_status", default="MISSING"),
            last_known_safe_gbp=_cfg_get(cfg, "daily_intel", "last_known_safe_gbp", default=listing_row.get("our_price", "")),
            foep_stale_hours=int(float(_cfg_get(cfg, "eligibility", "foep_stale_hours", default=48))),
            foep_sanity_min_mult=_cfg_get(cfg, "eligibility", "foep_sanity_min_mult", default="0.50"),
            foep_sanity_max_mult=_cfg_get(cfg, "eligibility", "foep_sanity_max_mult", default="2.00"),
            market_reference_price_gbp=_cfg_get(cfg, "daily_intel", "market_reference_price_gbp", default=listing_row.get("buy_box_price", "")),
        )

    allow_intraday_intel_refresh = _to_bool(
        _cfg_get(cfg, "allow_h_intraday_intel_refresh", default=False),
        default=False,
    )

    _progress("h110 run_one_sku market_payload_ready", sku=sku, offers=len(payload.get("offers", [])))
    cfg_live = _to_bool(_cfg_get(cfg, "enabled_live_writes", default=False), default=False)
    effective_live = bool(
        writer_mode == "CODEX_H"
        and not read_only
        and cfg_live
    )
    submitter = _phase1_write_submitter(sku=sku, marketplace_id=marketplace_id, run_id=run_id) if effective_live else None
    post_write_lookup = _phase1_post_write_price_lookup(sku=sku, marketplace_id=marketplace_id, run_id=run_id) if effective_live else None
    _progress(
        "h110 run_one_sku h_cycle_start",
        sku=sku,
        writer_mode=writer_mode,
        effective_live="1" if effective_live else "0",
    )
    _progress(
        "h110 sku_exec_pre_write",
        sku=sku,
        run_id=run_id,
        writer_mode=writer_mode,
        effective_live="1" if effective_live else "0",
    )
    _checkpoint("sku_exec_pre_write", sku=sku, run_id=run_id)
    try:
        h_out = phase1_main_loop.run_h_cycle(
            sku=sku,
            asin=asin,
            marketplace_id=marketplace_id,
            our_seller_id=seller_id,
            pricing_writer_mode=writer_mode,
            enabled_live_writes=effective_live,
            current_price_gbp=_to_num_text(listing_row.get("our_price", ""), "0.00"),
            hard_floor_gbp=hard_floor_resolved,
            manual_cap_gbp=manual_cap_resolved,
            max_step_down_gbp=_cfg_get(cfg, "guardrails", "max_step_down_gbp", default="0.20"),
            max_step_up_gbp=_cfg_get(cfg, "guardrails", "max_step_up_gbp", default="0.20"),
            max_daily_drop_gbp=_cfg_get(cfg, "guardrails", "max_daily_drop_gbp", default="0.60"),
            daily_drop_used_gbp=_cfg_get(cfg, "guardrails", "daily_drop_used_gbp", default="0.00"),
            delta_tolerance_gbp=_cfg_get(cfg, "learning", "delta_tolerance_gbp", default="0.02"),
            stable_buffer_gbp=_cfg_get(cfg, "learning", "stable_buffer_gbp", default="0.02"),
            min_clean_tests_for_confidence=int(float(_cfg_get(cfg, "learning", "min_clean_tests_for_confidence", default=5))),
            price_apply_tolerance_gbp=_cfg_get(cfg, "guardrails", "price_apply_tolerance_gbp", default="0.01"),
            policy_buffer_pct=_cfg_get(cfg, "boundaries", "policy_buffer_pct", default="0.03"),
            market_payload=payload,
            listings_observed_price_gbp=listings_observed_price,
            write_submitter=submitter,
            post_write_observed_price_lookup=post_write_lookup,
            now_utc=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            daily_intel_refresher=_refresh_daily_intel_once if allow_intraday_intel_refresh else None,
            reentry_price_discovery_active=reentry_price_discovery_active,
            reentry_event=reentry_event,
            inbound_price_discovery_active=inbound_price_discovery_active,
            seller_detail_status=_norm(listing_row.get("seller_detail_status", "")),
            seller_detail_resolution_status=_norm(listing_row.get("seller_detail_resolution_status", "")),
            seller_detail_snapshot_ts_utc=_norm(listing_row.get("seller_detail_snapshot_ts_utc", "")),
            snapshot_timestamp_utc=_norm(listing_row.get("timestamp_utc", "")),
            seller_detail_offer_row_count=_norm(listing_row.get("seller_detail_offer_row_count", "")),
        )
    except BaseException as exc:
        _progress(
            "owner_worker_continuation_failed",
            run_id=run_id,
            sku=sku,
            stage="run_h_cycle",
            error_type=type(exc).__name__,
            reason=_norm(str(exc))[:240] or "run_h_cycle_exception",
        )
        _progress(
            "completion_gap_abnormal_exit",
            run_id=run_id,
            checkpoint=_LAST_COMPLETION_CHECKPOINT,
            error_type=type(exc).__name__,
            error=_norm(str(exc))[:240],
        )
        _progress(
            "h110 sku_exec_abnormal_exit",
            sku=sku,
            run_id=run_id,
            error_type=type(exc).__name__,
            error=_norm(str(exc))[:240],
        )
        _progress(
            "parent_continuation_abnormal_exit",
            sku=sku,
            run_id=run_id,
            stage="run_h_cycle",
            error_type=type(exc).__name__,
            error=_norm(str(exc))[:240],
        )
        _finalize_lifecycle(event="error", error=_norm(str(exc))[:500])
        raise
    _progress(
        "h110 sku_exec_post_write",
        sku=sku,
        run_id=run_id,
        state=_norm(h_out.state),
        write_status=_norm(h_out.write_status),
    )
    _checkpoint("sku_exec_post_write", sku=sku, run_id=run_id)
    _progress("h110 run_one_sku h_cycle_done", sku=sku, state=_norm(h_out.state), write_status=_norm(h_out.write_status))
    if not using_daily_lock:
        daily_boundary_lock_by_sku[sku] = {
            "hard_floor_gbp": hard_floor_resolved,
            "manual_cap_gbp": manual_cap_resolved,
            "final_ceiling_landed_gbp": _norm(h_out.final_ceiling_landed_gbp),
            "locked_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    latest_daily_after = phase1_storage.read_latest("sku_daily_intel", {"sku": sku}) or {}
    daily_missing = "1" if _norm(latest_daily_after.get("date_utc", "")) != today else "0"

    out_row = {
        "phase1_pilot": "1",
        "phase1_sku": sku,
        "phase1_asin": asin,
        "daily_intel_missing_for_today": daily_missing,
        "last_executioner_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "executioner_ran_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "executioner_probe_type": _norm(h_out.state),
        "executioner_live_write_attempted": "1" if effective_live else "0",
        "executioner_live_write_success": "1" if _norm(h_out.write_status) == "APPLIED" else "0",
        "write_status": _norm(h_out.write_status),
        "writer_mode": writer_mode,
        "hard_floor_applied_gbp": hard_floor_resolved,
        "manual_cap_applied_gbp": manual_cap_resolved,
        "final_ceiling_landed_gbp": _norm(h_out.final_ceiling_landed_gbp),
        "reason_codes_csv": ",".join(h_out.reason_codes),
        "phase1_boundary_lock_mode": "reused" if using_daily_lock else "set",
        "phase1_boundary_lock_date": boundary_lock_date_utc,
        "phase1_boundary_lock_final_ceiling_gbp": _norm((daily_boundary_lock_by_sku.get(sku) or {}).get("final_ceiling_landed_gbp", "")),
        "blocked_due_to_missing_intel": _norm(h_out.blocked_due_to_missing_intel),
        "blocked_due_to_stale_intel": _norm(h_out.blocked_due_to_stale_intel),
        "refresh_attempted_count": _norm(h_out.refresh_attempted_count),
        "refresh_throttled_count": _norm(h_out.refresh_throttled_count),
        "seller_detail_status": _norm(getattr(h_out, "seller_detail_status", "")) or _norm(listing_row.get("seller_detail_status", "")),
        "seller_detail_resolution_status": _norm(getattr(h_out, "seller_detail_resolution_status", ""))
        or _norm(listing_row.get("seller_detail_resolution_status", "")),
        "seller_detail_retry_flag": _norm(listing_row.get("retry_next_run_flag", "")),
        "seller_detail_retry_attempt_count": _norm(listing_row.get("seller_detail_retry_attempt_count", "")),
        "seller_detail_rotation_skip_count": _norm(listing_row.get("seller_detail_rotation_skip_count", "")),
        "seller_detail_empty_response_count": _norm(listing_row.get("seller_detail_empty_response_count", "")),
        "seller_detail_api_error_count": _norm(listing_row.get("seller_detail_api_error_count", "")),
        "seller_detail_force_attempt_flag": _norm(listing_row.get("seller_detail_force_attempt_flag", "")),
        "seller_detail_retry_exhausted_flag": _norm(listing_row.get("seller_detail_retry_exhausted_flag", "")),
        "seller_detail_blocked": _norm(getattr(h_out, "seller_detail_blocked", "0")),
        "market_data_present": market_data_present,
        "write_effective": "1" if write_effective else "0",
        "repricing_enabled": "1" if repricing_enabled else "0",
        "universe_reason_code": _norm(universe_row.get("reason_code", "")),
        "decision": "execute",
    }
    _finalize_lifecycle(
        event="finish",
        decision=_norm(out_row.get("decision", "")),
        write_status=_norm(out_row.get("write_status", "")),
        reason_codes_csv=_norm(out_row.get("reason_codes_csv", "")),
    )
    return _return_out_row(out_row)


def _run_once(*, cfg: dict, read_only: bool, run_id: str, now_utc: datetime) -> dict[str, str]:
    cfg = dict(cfg or {})
    _progress("h110 run_once start", run_id=run_id, read_only="1" if read_only else "0")
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    today_utc = now_utc.strftime("%Y-%m-%d")
    universe_rows_raw = _load_canonical_universe(now_utc)
    universe_raw_by_sku = {
        _norm(r.get("sku", "")).upper(): r for r in universe_rows_raw if _norm(r.get("sku", ""))
    }
    universe_rows, scope_summary = _apply_scope_universe_filter(
        universe_rows=universe_rows_raw,
        today_utc=today_utc,
    )
    universe_by_sku = {r["sku"]: r for r in universe_rows}
    observe_rows = [r for r in universe_rows if _as_bool_text(r.get("observe_effective", ""), "1") == "1"]
    if not observe_rows:
        _append_sku_decision_rows(
            [
                {
                    "decision_ts_utc": now_iso,
                    "run_id": run_id,
                    "sku": "",
                    "repricing_enabled": "0",
                    "observe_effective": "0",
                    "write_effective": "0",
                    "market_data_present": "",
                    "decision": "skip_observe_disabled_all",
                    "reason_code": "observe_disabled_all",
                }
            ]
        )
        return {
            "phase1_pilot": "1",
            "phase1_sku": "",
            "phase1_skus_processed_csv": "",
            "phase1_skus_processed_count": "0",
            "phase1_skus_skipped_cooldown_count": "0",
            "phase1_skus_skipped_parked_count": str(
                sum(1 for r in universe_rows if _as_bool_text(r.get("repricing_enabled", ""), "0") == "0")
            ),
            "phase1_skus_skipped_out_of_stock_count": str(
                sum(1 for r in universe_rows if "out_of_stock" in _norm(r.get("reason_code", "")).lower())
            ),
            "phase1_scan_cooldown_minutes": "0",
            "phase1_next_due_sleep_seconds": "0",
            "phase1_next_due_sku": "",
            "phase1_target_universe_mode": "canonical_scope",
            "phase1_target_universe_source": str(CANONICAL_UNIVERSE_PATH),
            "phase1_target_universe_mode_source": "phase1_sku_scope",
            "phase1_target_universe_candidate_count": str(len(universe_rows)),
            "phase1_target_universe_resolved_count": str(len(observe_rows)),
            "phase1_target_universe_skipped_no_listing_count": "0",
            "phase1_target_universe_skipped_out_of_stock_count": str(
                sum(1 for r in universe_rows if "out_of_stock" in _norm(r.get("reason_code", "")).lower())
            ),
            "phase1_target_universe_notes_csv": "OBSERVE_DISABLED_ALL",
            "phase1_scope_total": scope_summary["scope_total"],
            "phase1_scope_excluded_dropped_count": scope_summary["excluded_dropped"],
            "phase1_scope_excluded_parked_count": scope_summary["excluded_parked"],
            "phase1_scope_remaining_count": scope_summary["remaining"],
            "phase1_scope_excluded_path": scope_summary["excluded_path"],
            "phase1_scope_source_path": scope_summary["scope_source"],
            "phase1_boundary_lock_date": now_utc.strftime("%Y-%m-%d"),
            "phase1_boundary_lock_sku_count": "0",
            "phase1_boundary_lock_mode": "",
            "phase1_boundary_lock_final_ceiling_gbp": "",
            "daily_intel_missing_for_today": "0",
            "daily_intel_normal_processed_count": "0",
            "daily_intel_normal_missing_count": "0",
            "daily_intel_exception_processed_count": "0",
            "daily_intel_exception_missing_count": "0",
            "daily_intel_gate_policy": "STRICT_ALL",
            "last_executioner_utc": now_iso,
            "executioner_ran_utc": "",
            "executioner_probe_type": "NO_SKU_OBSERVE_ENABLED",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": "NO_SKU_OBSERVE_ENABLED",
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": "NO_SKU_OBSERVE_ENABLED",
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
        }
    try:
        listing_snapshot_path_obj = _latest_listing_snapshot()
        listing_map = _load_listing_row_map(listing_snapshot_path_obj)
        listing_snapshot_path = str(listing_snapshot_path_obj)
        try:
            seller_snapshot_path = str(_latest_seller_snapshot())
        except Exception:
            seller_snapshot_path = ""
    except Exception as exc:
        raise RuntimeError(f"[H110] snapshot unreadable/corrupt: {exc}")

    scan_state = _read_json(SKU_SCAN_STATE_PATH, default={"last_scan_utc": {}, "daily_boundary_lock": {}})
    last_scan_utc = scan_state.get("last_scan_utc", {})
    if not isinstance(last_scan_utc, dict):
        last_scan_utc = {}
    boundary_lock = scan_state.get("daily_boundary_lock", {})
    if not isinstance(boundary_lock, dict):
        boundary_lock = {}
    if _norm(boundary_lock.get("date_utc", "")) != today_utc:
        boundary_lock = {"date_utc": today_utc, "by_sku": {}}
    boundary_lock_by_sku = boundary_lock.get("by_sku", {})
    if not isinstance(boundary_lock_by_sku, dict):
        boundary_lock_by_sku = {}

    cooldown_minutes = max(int(float(_cfg_get(cfg, "scan_cooldown_minutes", default=15))), 0)
    # Run-once should process the full current universe deterministically.
    if _to_bool(os.environ.get("H_RUN_ONCE", "0"), default=False):
        cooldown_minutes = 0
    spacing_seconds = max(float(_cfg_get(cfg, "sku_call_spacing_seconds", default=2.0)), 0.0)
    spacing_seconds = max(_env_float("H110_SKU_CALL_SPACING_SECONDS_OVERRIDE", spacing_seconds), 0.0)
    max_skus_raw = float(_cfg_get(cfg, "max_skus_per_run", default=0) or 0)
    # max_skus_per_run <= 0 means "no cap": process all due in-stock SKUs.
    max_skus_per_run = int(max_skus_raw) if max_skus_raw > 0 else 0
    max_skus_override = _env_int("H110_MAX_SKUS_PER_RUN_OVERRIDE", max_skus_per_run)
    if max_skus_override > 0:
        max_skus_per_run = max_skus_override
    single_sku_cap_rollback_enabled = _to_bool(
        os.environ.get("H110_SINGLE_SKU_CAP_ROLLBACK_ENABLED", "0"),
        default=False,
    )
    if max_skus_per_run == 1 and not single_sku_cap_rollback_enabled:
        # Active default must not collapse a run to first SKU only.
        max_skus_per_run = 0
    manual_cap_by_sku, manual_cap_by_asin = _load_manual_caps()
    _progress("h110 run_once manual_caps_loaded", sku_caps=len(manual_cap_by_sku), asin_caps=len(manual_cap_by_asin))
    universe_skus = {r.get("sku", "").strip().upper() for r in universe_rows if _norm(r.get("sku", ""))}
    temp_floor_by_sku, temp_floor_blockers_by_sku = _load_temp_floor_by_sku(universe_skus)
    _progress(
        "h110 run_once temp_floor_loaded",
        floor_count=len(temp_floor_by_sku),
        blocker_count=len(temp_floor_blockers_by_sku),
    )

    due_rows: list[dict[str, str]] = []
    skipped_cooldown: list[str] = []
    cooldown_wait_candidates: list[tuple[int, str]] = []
    decision_rows: list[dict[str, str]] = []
    skipped_out_of_stock = [
        r["sku"] for r in universe_rows if "out_of_stock" in _norm(r.get("reason_code", "")).lower()
    ]
    skipped_parked_count = sum(1 for r in universe_rows if _as_bool_text(r.get("repricing_enabled", ""), "0") == "0")
    for sku, urow in sorted(universe_by_sku.items()):
        if _as_bool_text(urow.get("observe_effective", ""), "1") == "1":
            continue
        decision_rows.append(
            {
                "decision_ts_utc": now_iso,
                "run_id": run_id,
                "sku": sku,
                "repricing_enabled": _as_bool_text(urow.get("repricing_enabled", ""), "0"),
                "observe_effective": "0",
                "write_effective": _as_bool_text(urow.get("write_effective", ""), "0"),
                "market_data_present": "1" if sku in listing_map else "0",
                "decision": "skip_observe_disabled",
                "reason_code": _norm(urow.get("reason_code", "")) or "observe_disabled",
            }
        )
    for urow in sorted(
        observe_rows,
        key=lambda r: (
            0 if _as_bool_text(r.get("write_effective", ""), "0") == "1" else 1,
            r.get("sku", ""),
        ),
    ):
        sku = _norm(urow.get("sku", "")).upper()
        if not sku:
            continue
        last_dt = _to_dt(last_scan_utc.get(sku, ""))
        if last_dt is None:
            due_rows.append(urow)
            continue
        elapsed_seconds = max((now_utc - last_dt).total_seconds(), 0.0)
        if elapsed_seconds >= float(cooldown_minutes) * 60.0:
            due_rows.append(urow)
        else:
            skipped_cooldown.append(sku)
            remaining_seconds = max(int(math.ceil(float(cooldown_minutes) * 60.0 - elapsed_seconds)), 1)
            cooldown_wait_candidates.append((remaining_seconds, sku))
            decision_rows.append(
                {
                    "decision_ts_utc": now_iso,
                    "run_id": run_id,
                    "sku": sku,
                    "repricing_enabled": _as_bool_text(urow.get("repricing_enabled", ""), "0"),
                    "observe_effective": "1",
                    "write_effective": _as_bool_text(urow.get("write_effective", ""), "0"),
                    "market_data_present": "1" if sku in listing_map else "0",
                    "decision": "skip_cooldown",
                    "reason_code": "cooldown",
                }
            )

    due_rows, stock_summary = _apply_stock_universe_filter(
        due_rows=due_rows,
        now_utc=now_utc,
        today_utc=today_utc,
    )
    # Apply cap after stock filtering so in-stock candidates are not starved
    # by out-of-stock rows that happened to appear earlier in the due list.
    # Within the capped set, oldest scan timestamps must win; otherwise the
    # alphabetically earliest SKUs can keep taking the whole batch.
    due_rows = _sort_due_rows_by_oldest_scan(due_rows, last_scan_utc)
    if max_skus_per_run > 0:
        due_rows = due_rows[:max_skus_per_run]
    normal_count = len(due_rows)
    include_stocked_excluded = _to_bool(os.environ.get(H_INCLUDE_STOCKED_EXCLUDED_ENV, "0"), default=False)
    exception_rows = _load_stocked_excluded_rows(today_utc) if include_stocked_excluded else []
    exception_included_rows: list[dict[str, str]] = []
    exception_by_sku = {r.get("sku", "").upper(): r for r in exception_rows if _norm(r.get("sku", ""))}
    exception_count = 0
    overlap_count = 0
    if include_stocked_excluded and exception_by_sku:
        due_by_sku = {_norm(r.get("sku", "")).upper(): r for r in due_rows if _norm(r.get("sku", ""))}
        exception_candidates: list[tuple[str, dict[str, str]]] = []
        for sku, exc_row in sorted(exception_by_sku.items()):
            raw_row = universe_raw_by_sku.get(sku)
            if raw_row is None:
                continue
            exception_candidates.append((sku, exc_row))
        exception_count = len(exception_candidates)
        overlap_count = sum(1 for sku, _ in exception_candidates if sku in due_by_sku)
        for sku, exc_row in exception_candidates:
            if sku in due_by_sku:
                continue
            raw_row = universe_raw_by_sku[sku]
            due_rows.append(raw_row)
            due_by_sku[sku] = raw_row
            exception_included_rows.append(exc_row)
    exception_path = ""
    if include_stocked_excluded:
        exception_path = str(_write_exception_included_file(today_utc=today_utc, rows=exception_included_rows))
    _progress(
        "h_universe_exception_decision",
        today_utc=today_utc,
        enabled="1" if include_stocked_excluded else "0",
        normal_count=normal_count,
        exception_count=exception_count,
        overlap_count=overlap_count,
        final_process_count=len(due_rows),
    )
    _progress(
        "h110 run_once due_scan_complete",
        due_count=len(due_rows),
        skipped_cooldown_count=len(skipped_cooldown),
        skipped_out_of_stock_count=len(skipped_out_of_stock),
        excluded_stock_oos=stock_summary["excluded_oos"],
        excluded_stock_unknown=stock_summary["excluded_unknown"],
    )
    stock_qty_by_sku_raw = stock_summary.get("available_stock_by_sku", {})
    stock_qty_by_sku = stock_qty_by_sku_raw if isinstance(stock_qty_by_sku_raw, dict) else {}
    inbound_units_by_sku_raw = stock_summary.get("inbound_units_by_sku", {})
    inbound_units_by_sku = inbound_units_by_sku_raw if isinstance(inbound_units_by_sku_raw, dict) else {}
    reentry_state = _read_json(H_REENTRY_STATE_PATH, default={"skus": {}})
    reentry_state_by_sku = reentry_state.get("skus", {}) if isinstance(reentry_state, dict) else {}
    if not isinstance(reentry_state_by_sku, dict):
        reentry_state_by_sku = {}
    inbound_state = _read_json(H_INBOUND_ACTIVATION_STATE_PATH, default={"skus": {}})
    inbound_state_by_sku = inbound_state.get("skus", {}) if isinstance(inbound_state, dict) else {}
    if not isinstance(inbound_state_by_sku, dict):
        inbound_state_by_sku = {}

    run_rows: list[dict[str, str]] = []
    direct_owner_enabled = _to_bool(os.environ.get("H110_DIRECT_ARTIFACT_OWNER_ENABLED", "0"), default=False)
    direct_owner_first_sku_handoff_enabled = _to_bool(
        os.environ.get("H110_DIRECT_ARTIFACT_OWNER_FIRST_SKU_HANDOFF_ENABLED", "0"),
        default=False,
    )
    direct_owner_first_sku_handoff_rollback_enabled = _to_bool(
        os.environ.get("H110_DIRECT_ARTIFACT_OWNER_FIRST_SKU_HANDOFF_ROLLBACK_ENABLED", "0"),
        default=False,
    )
    rollback_handoff_enabled = "1" if (
        direct_owner_enabled
        and direct_owner_first_sku_handoff_enabled
        and direct_owner_first_sku_handoff_rollback_enabled
    ) else "0"
    _progress(
        "multi_sku_handoff_bypass_enter",
        run_id=run_id,
        due_count=str(len(due_rows)),
        rollback_handoff_enabled=rollback_handoff_enabled,
    )
    _progress(
        "throughput_recovery_enter",
        run_id=run_id,
        due_count=str(len(due_rows)),
        max_skus_per_run=str(max_skus_per_run),
        single_sku_cap_rollback_enabled="1" if single_sku_cap_rollback_enabled else "0",
        rollback_handoff_enabled=rollback_handoff_enabled,
    )
    for idx, urow in enumerate(due_rows):
        sku = _norm(urow.get("sku", "")).upper()
        current_stock_qty = _to_float(stock_qty_by_sku.get(sku, ""))
        current_inbound_units = _to_float(inbound_units_by_sku.get(sku, ""))
        state_row = reentry_state_by_sku.get(sku, {})
        if not isinstance(state_row, dict):
            state_row = {}
        previous_stock_qty = _to_float(state_row.get("previous_available_stock", ""))
        reentry_started_utc = _norm(state_row.get("reentry_started_utc", ""))
        reentry_started_dt = _to_dt(reentry_started_utc)
        reentry_start_stock_qty = _to_float(state_row.get("reentry_start_stock", ""))
        reentry_active = _as_bool_text(state_row.get("reentry_active", "0"), "0") == "1"
        reentry_event = bool(
            previous_stock_qty is not None
            and previous_stock_qty <= 0.0
            and current_stock_qty is not None
            and current_stock_qty > 0.0
        )

        if reentry_event:
            reentry_active = True
            reentry_started_utc = now_iso
            reentry_start_stock_qty = current_stock_qty
            _progress(
                "h_reentry_event",
                sku=sku,
                previous_available_stock=_fmt_stock_qty(previous_stock_qty),
                current_available_stock=_fmt_stock_qty(current_stock_qty),
                marker="REENTRY_PRICE_DISCOVERY",
            )
        elif reentry_active:
            first_sale_detected = bool(
                reentry_start_stock_qty is not None
                and current_stock_qty is not None
                and current_stock_qty < reentry_start_stock_qty
            )
            elapsed_seconds = (
                (now_utc - reentry_started_dt).total_seconds()
                if reentry_started_dt is not None
                else 0.0
            )
            if first_sale_detected or elapsed_seconds >= 86400.0:
                reentry_active = False
                reentry_started_utc = ""
                reentry_start_stock_qty = None
                _progress(
                    "h_reentry_mode_exit",
                    sku=sku,
                    reason="first_sale" if first_sale_detected else "24h_elapsed",
                    current_available_stock=_fmt_stock_qty(current_stock_qty),
                )
        inbound_state_row = inbound_state_by_sku.get(sku, {})
        if not isinstance(inbound_state_row, dict):
            inbound_state_row = {}
        previous_inbound_units = _to_float(inbound_state_row.get("previous_inbound_units", "0"))
        previous_available_units = _to_float(inbound_state_row.get("previous_available_units", ""))
        inbound_activation_event = bool(
            previous_inbound_units is not None
            and previous_inbound_units <= 0.0
            and current_inbound_units is not None
            and current_inbound_units > 0.0
            and current_stock_qty is not None
            and current_stock_qty <= 0.0
        )
        inbound_discovery_active = bool(
            current_stock_qty is not None
            and current_stock_qty <= 0.0
            and current_inbound_units is not None
            and current_inbound_units > 0.0
        )
        if inbound_activation_event:
            _progress(
                "h_inbound_activation_event",
                sku=sku,
                previous_inbound_units=_fmt_stock_qty(previous_inbound_units),
                current_inbound_units=_fmt_stock_qty(current_inbound_units),
                previous_available_units=_fmt_stock_qty(previous_available_units),
                current_available_units=_fmt_stock_qty(current_stock_qty),
                marker="INBOUND_PRICE_DISCOVERY",
            )

        row_run_id = f"{run_id}_{idx+1:02d}"
        first_sku_worker_enabled = _to_bool(os.environ.get("H110_FIRST_SKU_EXEC_WORKER_ENABLED", "0"), default=False)
        use_first_sku_worker = bool(first_sku_worker_enabled and idx == 0)
        use_legacy_worker_boundary = _to_bool(
            os.environ.get("H110_FIRST_SKU_EXEC_WORKER_USE_LEGACY_BOUNDARY", "0"),
            default=False,
        )
        try:
            if use_first_sku_worker:
                if use_legacy_worker_boundary:
                    row = _run_first_sku_worker_boundary(
                        cfg=cfg,
                        sku=sku,
                        read_only=read_only,
                        run_id=row_run_id,
                        now_utc=now_utc,
                        manual_cap_by_sku=manual_cap_by_sku,
                        manual_cap_by_asin=manual_cap_by_asin,
                        temp_floor_by_sku=temp_floor_by_sku,
                        temp_floor_blockers_by_sku=temp_floor_blockers_by_sku,
                        daily_boundary_lock_by_sku=boundary_lock_by_sku,
                        boundary_lock_date_utc=today_utc,
                        universe_row=urow,
                        listing_row=listing_map.get(sku, {}),
                        listing_snapshot_path=listing_snapshot_path,
                        seller_snapshot_path=seller_snapshot_path,
                        reentry_price_discovery_active=reentry_active,
                        reentry_event=reentry_event,
                        inbound_price_discovery_active=inbound_discovery_active,
                    )
                else:
                    row = _run_first_sku_exec_worker(
                        cfg=cfg,
                        sku=sku,
                        read_only=read_only,
                        run_id=row_run_id,
                        now_utc=now_utc,
                        manual_cap_by_sku=manual_cap_by_sku,
                        manual_cap_by_asin=manual_cap_by_asin,
                        temp_floor_by_sku=temp_floor_by_sku,
                        temp_floor_blockers_by_sku=temp_floor_blockers_by_sku,
                        daily_boundary_lock_by_sku=boundary_lock_by_sku,
                        boundary_lock_date_utc=today_utc,
                        universe_row=urow,
                        listing_row=listing_map.get(sku, {}),
                        listing_snapshot_path=listing_snapshot_path,
                        seller_snapshot_path=seller_snapshot_path,
                        reentry_price_discovery_active=reentry_active,
                        reentry_event=reentry_event,
                        inbound_price_discovery_active=inbound_discovery_active,
                    )
                _progress(
                    "parent_aggregation_after_exec_worker",
                    run_id=row_run_id,
                    sku=sku,
                    decision=_norm(row.get("decision", "")),
                    write_status=_norm(row.get("write_status", "")),
                )
            else:
                row = _run_one_sku(
                    cfg=cfg,
                    sku=sku,
                    read_only=read_only,
                    run_id=row_run_id,
                    now_utc=now_utc,
                    manual_cap_by_sku=manual_cap_by_sku,
                    manual_cap_by_asin=manual_cap_by_asin,
                    temp_floor_by_sku=temp_floor_by_sku,
                    temp_floor_blockers_by_sku=temp_floor_blockers_by_sku,
                    daily_boundary_lock_by_sku=boundary_lock_by_sku,
                    boundary_lock_date_utc=today_utc,
                    universe_row=urow,
                    listing_map=listing_map,
                    listing_snapshot_path=listing_snapshot_path,
                    seller_snapshot_path=seller_snapshot_path,
                    reentry_price_discovery_active=reentry_active,
                    reentry_event=reentry_event,
                    inbound_price_discovery_active=inbound_discovery_active,
                )
        except BaseException as exc:
            _progress(
                "h110 sku_exec_abnormal_exit",
                sku=sku,
                run_id=run_id,
                stage="run_once_boundary",
                error_type=type(exc).__name__,
                error=_norm(str(exc))[:240],
            )
            raise
        row["reentry_event"] = "1" if reentry_event else "0"
        row["reentry_price_discovery_active"] = "1" if reentry_active else "0"
        row["current_available_stock"] = _fmt_stock_qty(current_stock_qty)
        row["current_inbound_units"] = _fmt_stock_qty(current_inbound_units)
        row["inbound_activation_event"] = "1" if inbound_activation_event else "0"
        row["inbound_discovery_active"] = "1" if inbound_discovery_active else "0"
        run_rows.append(row)
        if idx == 0:
            _progress(
                "multi_sku_handoff_bypass_first_sku_done",
                run_id=run_id,
                sku=sku,
                processed_count=str(len(run_rows)),
                due_count=str(len(due_rows)),
            )
            _progress(
                "throughput_recovery_first_sku_done",
                run_id=run_id,
                sku=sku,
                processed_count=str(len(run_rows)),
                due_count=str(len(due_rows)),
            )
            if len(due_rows) > 1:
                _progress(
                    "multi_sku_handoff_bypass_continue",
                    run_id=run_id,
                    remaining_count=str(len(due_rows) - 1),
                )
                _progress(
                    "throughput_recovery_continue_next_sku",
                    run_id=run_id,
                    next_sku=_norm(due_rows[1].get("sku", "")).upper(),
                    remaining_count=str(len(due_rows) - 1),
                )
        reentry_state_by_sku[sku] = {
            "previous_available_stock": _fmt_stock_qty(current_stock_qty),
            "reentry_active": "1" if reentry_active else "0",
            "reentry_started_utc": reentry_started_utc if reentry_active else "",
            "reentry_start_stock": _fmt_stock_qty(reentry_start_stock_qty) if reentry_active else "",
            "updated_utc": now_iso,
        }
        inbound_state_by_sku[sku] = {
            "previous_available_units": _fmt_stock_qty(current_stock_qty),
            "previous_inbound_units": _fmt_stock_qty(current_inbound_units),
            "updated_utc": now_iso,
        }
        last_scan_utc[sku] = now_iso
        decision_rows.append(
            {
                "decision_ts_utc": now_iso,
                "run_id": run_id,
                "sku": sku,
                "repricing_enabled": _norm(row.get("repricing_enabled", "")),
                "observe_effective": "1",
                "write_effective": _norm(row.get("write_effective", "")),
                "market_data_present": _norm(row.get("market_data_present", "0")),
                "decision": _norm(row.get("decision", "")) or "execute",
                "reason_code": _norm(row.get("universe_reason_code", "")) or _norm(row.get("reason_codes_csv", "")),
            }
        )
        _progress("h110 run_once sku_done", sku=sku, idx=f"{idx+1}/{len(due_rows)}", write_status=_norm(row.get("write_status", "")))
        if idx < len(due_rows) - 1 and spacing_seconds > 0:
            time.sleep(spacing_seconds)
    _append_sku_decision_rows(decision_rows)

    scan_state_ok, scan_state_reason, _scan_state_advanced_count = _write_scan_state_update(
        run_id=run_id,
        updates_by_sku=last_scan_utc,
        boundary_lock_date_utc=today_utc,
        boundary_lock_by_sku=boundary_lock_by_sku,
    )
    _progress(
        "throughput_recovery_scan_state_advanced_count",
        run_id=run_id,
        advanced_count=str(_scan_state_advanced_count),
        status="ok" if scan_state_ok else "failed",
        reason=scan_state_reason,
    )
    if not scan_state_ok:
        raise RuntimeError(f"scan_state_write_required_failed:{scan_state_reason}")
    _write_json(H_REENTRY_STATE_PATH, {"skus": reentry_state_by_sku})
    _write_json(H_INBOUND_ACTIVATION_STATE_PATH, {"skus": inbound_state_by_sku})

    next_due_sleep_seconds = 0
    next_due_sku = ""
    if cooldown_wait_candidates:
        next_due_sleep_seconds, next_due_sku = min(cooldown_wait_candidates, key=lambda pair: pair[0])

    # Keep strategy outcome resolution current every cycle, not only cooldown-only runs.
    # Use an end-of-cycle timestamp so long cycles can close outcomes that matured during processing.
    strategy_outcome_tick_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    phase1_main_loop.close_pending_strategy_outcomes_tick(
        observation_ts_utc=strategy_outcome_tick_ts,
    )

    if not run_rows:
        no_due_reason = "NO_SKU_DUE_COOLDOWN"
        if int(stock_summary["scope_total"]) > 0 and int(stock_summary["eligible"]) == 0:
            no_due_reason = "NO_SKU_DUE_STOCK_FILTER"
        _progress("multi_sku_handoff_bypass_processed_count", run_id=run_id, processed_count="0")
        _progress("multi_sku_handoff_bypass_payload_rows", run_id=run_id, payload_rows="0")
        _progress("multi_sku_handoff_bypass_exit", run_id=run_id, status="ok", reason=no_due_reason)
        _progress("throughput_recovery_processed_count", run_id=run_id, processed_count="0")
        _progress("throughput_recovery_payload_rows", run_id=run_id, payload_rows="0")
        _progress("throughput_recovery_exit", run_id=run_id, status="ok", reason=no_due_reason)
        _progress("h110 run_once done", processed_count=0, reason=no_due_reason)
        return {
            "phase1_pilot": "1",
            "phase1_sku": "",
            "phase1_skus_processed_csv": "",
            "phase1_skus_processed_count": "0",
            "phase1_skus_skipped_cooldown_count": str(len(skipped_cooldown)),
            "phase1_skus_skipped_parked_count": str(skipped_parked_count),
            "phase1_skus_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
            "phase1_scan_cooldown_minutes": str(cooldown_minutes),
            "phase1_next_due_sleep_seconds": str(next_due_sleep_seconds),
            "phase1_next_due_sku": next_due_sku,
            "phase1_target_universe_mode": "canonical_scope",
            "phase1_target_universe_source": str(CANONICAL_UNIVERSE_PATH),
            "phase1_target_universe_mode_source": "phase1_sku_scope",
            "phase1_target_universe_candidate_count": str(len(universe_rows)),
            "phase1_target_universe_resolved_count": str(len(observe_rows)),
            "phase1_target_universe_skipped_no_listing_count": str(sum(1 for r in observe_rows if r["sku"] not in listing_map)),
            "phase1_target_universe_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
            "phase1_target_universe_notes_csv": "canonical_universe",
            "phase1_scope_total": scope_summary["scope_total"],
            "phase1_scope_excluded_dropped_count": scope_summary["excluded_dropped"],
            "phase1_scope_excluded_parked_count": scope_summary["excluded_parked"],
            "phase1_scope_remaining_count": scope_summary["remaining"],
            "phase1_scope_excluded_path": scope_summary["excluded_path"],
            "phase1_scope_source_path": scope_summary["scope_source"],
            "phase1_exception_enabled": "1" if include_stocked_excluded else "0",
            "phase1_exception_count": str(exception_count),
            "phase1_exception_overlap_count": str(overlap_count),
            "phase1_exception_normal_count": str(normal_count),
            "phase1_exception_final_process_count": str(len(due_rows)),
            "phase1_exception_path": exception_path,
            "phase1_stock_scope_total": stock_summary["scope_total"],
            "phase1_stock_eligible_count": stock_summary["eligible"],
            "phase1_stock_excluded_oos_count": stock_summary["excluded_oos"],
            "phase1_stock_excluded_unknown_count": stock_summary["excluded_unknown"],
            "phase1_stock_source_path": stock_summary["stock_source"],
            "phase1_stock_sku_col": stock_summary["stock_sku_col"],
            "phase1_stock_qty_col": stock_summary["stock_qty_col"],
            "phase1_stock_snapshot_date": stock_summary["stock_snapshot_date"],
            "phase1_stock_snapshot_age_hours": stock_summary["stock_snapshot_age_hours"],
            "phase1_stock_snapshot_is_fallback": stock_summary["stock_snapshot_is_fallback"],
            "phase1_stock_snapshot_status": stock_summary["stock_snapshot_status"],
            "phase1_stock_snapshot_action": stock_summary["stock_snapshot_action"],
            "phase1_stock_snapshot_status_path": stock_summary["stock_snapshot_status_path"],
            "phase1_stock_excluded_path": stock_summary["excluded_path"],
            "phase1_boundary_lock_date": today_utc,
            "phase1_boundary_lock_sku_count": str(len(boundary_lock_by_sku)),
            "phase1_boundary_lock_mode": "",
            "phase1_boundary_lock_final_ceiling_gbp": "",
            "daily_intel_missing_for_today": "0",
            "daily_intel_normal_processed_count": "0",
            "daily_intel_normal_missing_count": "0",
            "daily_intel_exception_processed_count": "0",
            "daily_intel_exception_missing_count": "0",
            "daily_intel_gate_policy": "STRICT_ALL",
            "last_executioner_utc": now_iso,
            "executioner_ran_utc": "",
            "executioner_probe_type": "NO_SKU_DUE",
            "executioner_live_write_attempted": "0",
            "executioner_live_write_success": "0",
            "write_status": no_due_reason,
            "final_ceiling_landed_gbp": "",
            "reason_codes_csv": no_due_reason,
            "blocked_due_to_missing_intel": "0",
            "blocked_due_to_stale_intel": "0",
            "refresh_attempted_count": "0",
            "refresh_throttled_count": "0",
        }

    exception_only_skus = {
        _norm(r.get("sku", "")).upper() for r in exception_included_rows if _norm(r.get("sku", ""))
    }
    normal_processed_count = 0
    normal_missing_count = 0
    exception_processed_count = 0
    exception_missing_count = 0
    for row in run_rows:
        sku = _norm(row.get("phase1_sku", "")).upper()
        is_missing = row.get("daily_intel_missing_for_today", "0") == "1"
        if sku and sku in exception_only_skus:
            exception_processed_count += 1
            if is_missing:
                exception_missing_count += 1
        else:
            normal_processed_count += 1
            if is_missing:
                normal_missing_count += 1
    gate_policy = "EXEMPT_EXCEPTION" if include_stocked_excluded else "STRICT_ALL"
    gate_missing_count = normal_missing_count
    blocked_missing_count = sum(1 for row in run_rows if row.get("blocked_due_to_missing_intel", "0") == "1")
    blocked_stale_count = sum(1 for row in run_rows if row.get("blocked_due_to_stale_intel", "0") == "1")
    refresh_attempted_count = sum(int(_norm(row.get("refresh_attempted_count", "0")) or "0") for row in run_rows)
    refresh_throttled_count = sum(int(_norm(row.get("refresh_throttled_count", "0")) or "0") for row in run_rows)
    processed_skus = {_norm(row.get("phase1_sku", "")).upper() for row in run_rows if _norm(row.get("phase1_sku", ""))}
    intel_stats = _daily_intel_today_stats(today_utc_date=today_utc, skus=processed_skus)
    market_missing_count = sum(1 for row in run_rows if _norm(row.get("market_data_present", "0")) != "1")
    skip_no_market_count = sum(1 for row in run_rows if _norm(row.get("write_status", "")) == "SKIP_NO_MARKET_DATA")
    _progress(
        "h110 daily_intel_market_decision",
        today_utc=today_utc,
        daily_intel_path=str(intel_stats.get("path", "")),
        rows_today=str(intel_stats.get("rows_today", 0)),
        unique_skus_today=str(intel_stats.get("unique_skus_today", 0)),
        processed_skus=str(len(processed_skus)),
        processed_with_today_intel=str(intel_stats.get("matched_skus_today", 0)),
        processed_missing_today_intel=str(max(len(processed_skus) - int(intel_stats.get("matched_skus_today", 0)), 0)),
        market_data_missing_count=str(market_missing_count),
        skip_no_market_data_count=str(skip_no_market_count),
    )
    _progress(
        "h_daily_intel_gate_decision",
        today_utc=today_utc,
        normal_processed=normal_processed_count,
        normal_missing=normal_missing_count,
        exception_processed=exception_processed_count,
        exception_missing=exception_missing_count,
        policy=gate_policy,
    )
    last = run_rows[-1]
    payload_rows = len([_norm(r.get("phase1_sku", "")) for r in run_rows if _norm(r.get("phase1_sku", ""))])
    _progress("multi_sku_handoff_bypass_processed_count", run_id=run_id, processed_count=str(len(run_rows)))
    _progress("multi_sku_handoff_bypass_payload_rows", run_id=run_id, payload_rows=str(payload_rows))
    _progress("multi_sku_handoff_bypass_exit", run_id=run_id, status="ok", reason="payload_ready")
    _progress("throughput_recovery_processed_count", run_id=run_id, processed_count=str(len(run_rows)))
    _progress("throughput_recovery_payload_rows", run_id=run_id, payload_rows=str(payload_rows))
    _progress("throughput_recovery_exit", run_id=run_id, status="ok", reason="payload_ready")
    _progress("h110 run_once done", processed_count=len(run_rows), last_sku=_norm(last.get("phase1_sku", "")))
    return {
        "phase1_pilot": "1",
        "phase1_sku": _norm(last.get("phase1_sku", "")),
        "phase1_skus_processed_csv": ",".join([_norm(r.get("phase1_sku", "")) for r in run_rows]),
        "phase1_skus_processed_count": str(len(run_rows)),
        "phase1_skus_skipped_cooldown_count": str(len(skipped_cooldown)),
        "phase1_skus_skipped_parked_count": str(skipped_parked_count),
        "phase1_skus_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
        "phase1_scan_cooldown_minutes": str(cooldown_minutes),
        "phase1_next_due_sleep_seconds": str(next_due_sleep_seconds),
        "phase1_next_due_sku": next_due_sku,
        "phase1_target_universe_mode": "canonical_scope",
        "phase1_target_universe_source": str(CANONICAL_UNIVERSE_PATH),
        "phase1_target_universe_mode_source": "phase1_sku_scope",
        "phase1_target_universe_candidate_count": str(len(universe_rows)),
        "phase1_target_universe_resolved_count": str(len(observe_rows)),
        "phase1_target_universe_skipped_no_listing_count": str(sum(1 for r in observe_rows if r["sku"] not in listing_map)),
        "phase1_target_universe_skipped_out_of_stock_count": str(len(skipped_out_of_stock)),
        "phase1_target_universe_notes_csv": "canonical_universe",
        "phase1_scope_total": scope_summary["scope_total"],
        "phase1_scope_excluded_dropped_count": scope_summary["excluded_dropped"],
        "phase1_scope_excluded_parked_count": scope_summary["excluded_parked"],
        "phase1_scope_remaining_count": scope_summary["remaining"],
        "phase1_scope_excluded_path": scope_summary["excluded_path"],
        "phase1_scope_source_path": scope_summary["scope_source"],
        "phase1_exception_enabled": "1" if include_stocked_excluded else "0",
        "phase1_exception_count": str(exception_count),
        "phase1_exception_overlap_count": str(overlap_count),
        "phase1_exception_normal_count": str(normal_count),
        "phase1_exception_final_process_count": str(len(due_rows)),
        "phase1_exception_path": exception_path,
        "phase1_stock_scope_total": stock_summary["scope_total"],
        "phase1_stock_eligible_count": stock_summary["eligible"],
        "phase1_stock_excluded_oos_count": stock_summary["excluded_oos"],
        "phase1_stock_excluded_unknown_count": stock_summary["excluded_unknown"],
        "phase1_stock_source_path": stock_summary["stock_source"],
        "phase1_stock_sku_col": stock_summary["stock_sku_col"],
        "phase1_stock_qty_col": stock_summary["stock_qty_col"],
        "phase1_stock_snapshot_date": stock_summary["stock_snapshot_date"],
        "phase1_stock_snapshot_age_hours": stock_summary["stock_snapshot_age_hours"],
        "phase1_stock_snapshot_is_fallback": stock_summary["stock_snapshot_is_fallback"],
        "phase1_stock_snapshot_status": stock_summary["stock_snapshot_status"],
        "phase1_stock_snapshot_action": stock_summary["stock_snapshot_action"],
        "phase1_stock_snapshot_status_path": stock_summary["stock_snapshot_status_path"],
        "phase1_stock_excluded_path": stock_summary["excluded_path"],
        "phase1_boundary_lock_date": today_utc,
        "phase1_boundary_lock_sku_count": str(len(boundary_lock_by_sku)),
        "phase1_boundary_lock_mode": _norm(last.get("phase1_boundary_lock_mode", "")),
        "phase1_boundary_lock_final_ceiling_gbp": _norm(last.get("phase1_boundary_lock_final_ceiling_gbp", "")),
        "daily_intel_missing_for_today": "1" if gate_missing_count > 0 else "0",
        "daily_intel_missing_count": str(gate_missing_count),
        "daily_intel_normal_processed_count": str(normal_processed_count),
        "daily_intel_normal_missing_count": str(normal_missing_count),
        "daily_intel_exception_processed_count": str(exception_processed_count),
        "daily_intel_exception_missing_count": str(exception_missing_count),
        "daily_intel_gate_policy": gate_policy,
        "last_executioner_utc": now_iso,
        "executioner_ran_utc": _norm(last.get("executioner_ran_utc", "")),
        "executioner_probe_type": _norm(last.get("executioner_probe_type", "")),
        "executioner_live_write_attempted": _norm(last.get("executioner_live_write_attempted", "0")),
        "executioner_live_write_success": _norm(last.get("executioner_live_write_success", "0")),
        "write_status": _norm(last.get("write_status", "")),
        "final_ceiling_landed_gbp": _norm(last.get("final_ceiling_landed_gbp", "")),
        "reason_codes_csv": _norm(last.get("reason_codes_csv", "")),
        "blocked_due_to_missing_intel": str(blocked_missing_count),
        "blocked_due_to_stale_intel": str(blocked_stale_count),
        "refresh_attempted_count": str(refresh_attempted_count),
        "refresh_throttled_count": str(refresh_throttled_count),
    }


def _run_payload_worker_owner_runtime(
    *,
    cfg: dict[str, object],
    run_id: str,
    read_only: bool,
    now_utc_arg: str,
) -> int:
    _progress("payload_worker_owner_enter", run_id=run_id, worker_pid=os.getpid())

    if PHASE1_RESULT_PATH is None:
        raise RuntimeError("h110 completion contract requires H_PHASE1_RESULT_PATH")
    if PHASE1_COMPLETION_MARKER_PATH is None:
        raise RuntimeError("h110 completion contract requires H_PHASE1_COMPLETION_MARKER_PATH")

    checkpoint_state_path = PHASE1_COMPLETION_MARKER_PATH.with_name(
        PHASE1_COMPLETION_MARKER_PATH.name.replace("complete.", "checkpoint.")
    )
    _set_completion_checkpoint_context(run_id=run_id, checkpoint_path=checkpoint_state_path)
    _install_completion_exit_guards(run_id)
    _write_completion_marker(
        status="started",
        run_id=run_id,
        reason="run_started",
        payload_result_ok=False,
    )
    post_exit_terminalizer_enabled = _to_bool(
        os.environ.get("H110_POST_EXIT_TERMINALIZER_ENABLED", "0"),
        default=False,
    )
    if post_exit_terminalizer_enabled:
        _spawn_post_exit_terminalizer(
            run_id=run_id,
            marker_path=PHASE1_COMPLETION_MARKER_PATH,
            result_path=PHASE1_RESULT_PATH,
            checkpoint_path=checkpoint_state_path,
            liveness_pid=os.getpid(),
        )
    else:
        _progress(
            "post_exit_terminalizer_skipped",
            run_id=run_id,
            reason="disabled_single_owner_authority",
        )
    parent_cycle_pid = _to_int(os.environ.get("H_PHASE1_PARENT_PID", "")) or 0
    parent_cycle_watchdog_stop = threading.Event()
    parent_cycle_watchdog_thread: threading.Thread | None = None
    parent_dead_confirm_cycles = max(_env_int("H110_PARENT_DEAD_CONFIRM_CYCLES", 3), 1)
    consecutive_parent_dead = 0

    def _parent_cycle_watchdog() -> None:
        nonlocal consecutive_parent_dead
        if parent_cycle_pid <= 0:
            return
        while not parent_cycle_watchdog_stop.wait(1.0):
            if _SUCCESS_MARKER_WRITTEN:
                return
            if _pid_alive(parent_cycle_pid):
                consecutive_parent_dead = 0
                continue
            consecutive_parent_dead += 1
            if consecutive_parent_dead < parent_dead_confirm_cycles:
                continue
            if _owner_interrupt_reconcile_grace_active(run_id=run_id):
                continue
            handoff_grace_active, handoff_grace_reason = _parent_terminal_handoff_grace_active(
                run_id=run_id,
                parent_cycle_pid=parent_cycle_pid,
            )
            if handoff_grace_active:
                _progress(
                    "parent_cycle_watchdog_handoff_grace",
                    run_id=run_id,
                    parent_cycle_pid=str(parent_cycle_pid),
                    owner_pid=str(os.getpid()),
                    reason=handoff_grace_reason,
                    handoff_path=str(PHASE1_PARENT_HANDOFF_PATH) if PHASE1_PARENT_HANDOFF_PATH is not None else "",
                )
                continue
            _progress(
                "parent_cycle_watchdog_exit_detected",
                run_id=run_id,
                parent_cycle_pid=str(parent_cycle_pid),
                owner_pid=str(os.getpid()),
                reason="parent_cycle_dead_before_pilot_terminal",
                handoff_reason=handoff_grace_reason,
                handoff_path=str(PHASE1_PARENT_HANDOFF_PATH) if PHASE1_PARENT_HANDOFF_PATH is not None else "",
            )
            _set_parent_watchdog_abort(
                run_id=run_id,
                reason="parent_cycle_dead_before_pilot_terminal",
            )
            _ensure_terminal_completion_marker(reason="parent_cycle_dead_before_pilot_terminal")
            return

    if parent_cycle_pid > 0:
        parent_cycle_watchdog_thread = threading.Thread(
            target=_parent_cycle_watchdog,
            name="h110-parent-cycle-watchdog",
            daemon=True,
        )
        parent_cycle_watchdog_thread.start()
        _progress(
            "parent_cycle_watchdog_started",
            run_id=run_id,
            parent_cycle_pid=str(parent_cycle_pid),
            owner_pid=str(os.getpid()),
        )

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    if _norm(now_utc_arg):
        try:
            raw = _norm(now_utc_arg).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(raw)
            now_utc = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    payload: dict[str, object] | None = None
    run_failure: BaseException | None = None
    failure_reason = ""
    _progress("completion_finalize_enter", run_id=run_id, stage="run_once")
    _checkpoint("run_once_enter", run_id=run_id)
    original_os_exit = _install_os_exit_interceptor(run_id)
    owner_rc = 1
    _clear_parent_watchdog_abort()
    try:
        try:
            payload = _run_once(cfg=cfg, read_only=bool(read_only), run_id=run_id, now_utc=now_utc)
            abort_reason = _parent_watchdog_abort_reason()
            if abort_reason:
                raise RuntimeError(f"completion_convergence_failed:{abort_reason}")
        except _DirectArtifactOwnershipHandoff as handoff:
            observe_seconds = max(_env_int("H110_DIRECT_ARTIFACT_OWNER_OBSERVE_SECONDS", 30), 5)
            deadline = time.time() + float(observe_seconds)
            marker_status = "none"
            marker_reason = "pending"
            success_ok = False
            success_reason = "marker_not_ready"
            while time.time() < deadline:
                marker_status, marker_reason = _completion_marker_status_for_run(run_id)
                success_ok, success_reason = _completion_marker_success_for_run(run_id)
                if success_ok:
                    break
                time.sleep(0.25)
            settled_success, marker_status, marker_reason, success_reason = _pilot_terminal_settle_reconcile(
                run_id=run_id,
                initial_marker_status=marker_status,
                initial_marker_reason=marker_reason,
                initial_success_ok=success_ok,
                initial_success_reason=success_reason,
                log_prefix="pilot_parent_classifier_settle",
            )
            _progress(
                "owner_observe_direct_artifact_owner_exit",
                run_id=run_id,
                direct_artifact_owner_pid=str(handoff.owner_pid),
                observe_window_seconds=str(observe_seconds),
                marker_status=marker_status,
                marker_reason=marker_reason,
                success_ok="1" if settled_success else "0",
                success_reason=success_reason,
            )
            if settled_success:
                result_payload = _read_json(PHASE1_RESULT_PATH, default={})
                payload_processed_skus, payload_processed_count = (
                    _result_payload_processed_skus(result_payload) if isinstance(result_payload, dict) else ([], 0)
                )
                payload_due_count = _to_int((result_payload if isinstance(result_payload, dict) else {}).get("phase1_exception_final_process_count", "0")) or 0
                _progress(
                    "multi_sku_owner_enter",
                    run_id=run_id,
                    owner_mode="direct_artifact_owner_handoff",
                )
                _progress(
                    "multi_sku_owner_due_count",
                    run_id=run_id,
                    due_count=str(payload_due_count),
                )
                _progress(
                    "multi_sku_owner_processed_count",
                    run_id=run_id,
                    processed_count=str(payload_processed_count),
                )
                _progress(
                    "multi_sku_owner_payload_rows",
                    run_id=run_id,
                    payload_rows=str(len(payload_processed_skus)),
                )
                scan_state_ok, scan_state_reason, advanced_count = _write_scan_state_from_result_payload(
                    run_id=run_id,
                    now_utc_text=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
                _progress(
                    "multi_sku_owner_scan_state_advanced_count",
                    run_id=run_id,
                    advanced_count=str(advanced_count),
                )
                _progress(
                    "multi_sku_owner_exit",
                    run_id=run_id,
                    success_ok="1" if scan_state_ok else "0",
                    reason=scan_state_reason,
                )
                if not scan_state_ok:
                    owner_rc = 1
                    return owner_rc
                unresolved_owner_wait_reason = _owner_wait_unresolved_reason(run_id=run_id)
                if unresolved_owner_wait_reason:
                    _progress(
                        "owner_exit_reason",
                        run_id=run_id,
                        reason=unresolved_owner_wait_reason,
                        state="direct_owner_return_blocked_unresolved_owner_wait",
                    )
                    raise RuntimeError(f"completion_convergence_failed:{unresolved_owner_wait_reason}")
                owner_rc = 0
                return owner_rc
            if marker_status == "failed":
                owner_rc = 1
                return owner_rc
            run_failure = RuntimeError("direct_artifact_owner_terminal_evidence_missing")
            failure_reason = "direct_artifact_owner_terminal_evidence_missing"
        except BaseException as exc:
            run_failure = exc
            exc_reason = _norm(str(exc))
            _progress(
                "completion_convergence_failed",
                run_id=run_id,
                stage="run_once",
                error_type=type(exc).__name__,
                error=exc_reason[:240],
            )
            if exc_reason.startswith("completion_convergence_failed:boundary_"):
                failure_reason = exc_reason[:240]
                _progress(
                    "completion_convergence_boundary_failed",
                    run_id=run_id,
                    stage="run_once",
                    reason=failure_reason,
                )
                _checkpoint(
                    "completion_convergence_boundary_failed",
                    run_id=run_id,
                    stage="run_once",
                )
            elif exc_reason == "completion_convergence_failed:parent_cycle_dead_before_pilot_terminal":
                failure_reason = "parent_cycle_dead_before_pilot_terminal"
            else:
                failure_reason = _marker_reason("run_once_abnormal_exit", run_id=run_id, exc=exc)
            _progress(
                "completion_gap_abnormal_exit",
                run_id=run_id,
                checkpoint=_LAST_COMPLETION_CHECKPOINT,
                error_type=type(exc).__name__,
                error=exc_reason[:240],
            )
            _progress(
                "completion_finalize_abnormal_exit",
                run_id=run_id,
                stage="run_once",
                error_type=type(exc).__name__,
                error=exc_reason[:240],
            )

        _progress("h110 finalization_enter", run_id=run_id)
        _progress("completion_finalize_enter", run_id=run_id, stage="terminalization_funnel")
        _checkpoint("terminalization_funnel_dispatch", run_id=run_id)
        owner_rc = _terminalization_funnel(
            run_id=run_id,
            payload=payload,
            failure=run_failure,
            failure_reason=failure_reason,
        )
        unresolved_owner_wait_reason = _owner_wait_unresolved_reason(run_id=run_id)
        if owner_rc == 0 and unresolved_owner_wait_reason:
            _progress(
                "owner_exit_reason",
                run_id=run_id,
                reason=unresolved_owner_wait_reason,
                state="terminalization_return_blocked_unresolved_owner_wait",
            )
            raise RuntimeError(f"completion_convergence_failed:{unresolved_owner_wait_reason}")
        return owner_rc
    finally:
        parent_cycle_watchdog_stop.set()
        if parent_cycle_watchdog_thread is not None:
            with contextlib.suppress(Exception):
                parent_cycle_watchdog_thread.join(timeout=1.0)
        _clear_parent_watchdog_abort()
        _progress("payload_worker_owner_exit", run_id=run_id, rc=str(owner_rc))
        _restore_os_exit(original_os_exit)


def _run_market_payload_owner_runtime(
    *,
    cfg: dict[str, object],
    run_id: str,
    read_only: bool,
    now_utc_arg: str,
) -> int:
    _progress("market_payload_owner_enter", run_id=run_id, worker_pid=os.getpid())
    _owner_provenance_capture_start(
        run_id=run_id,
        sku="OWNER_SCOPE",
        owner_pid=str(os.getpid()),
        subcall_pid="",
        helper_pid="",
        timeout_seconds=str(max(_env_int("H110_OWNER_PROVENANCE_MAX_WAIT_SECONDS", 180), 30)),
    )
    owner_rc = 1
    try:
        owner_rc = _run_payload_worker_owner_runtime(
            cfg=cfg,
            run_id=run_id,
            read_only=read_only,
            now_utc_arg=now_utc_arg,
        )
        return owner_rc
    finally:
        _owner_provenance_capture_stop(
            run_id=run_id,
            sku="OWNER_SCOPE",
            owner_pid=str(os.getpid()),
            state="owner_runtime_exit",
            reason=f"market_payload_owner_exit_rc_{owner_rc}",
        )
        _progress("market_payload_owner_exit", run_id=run_id, rc=str(owner_rc))


def _run_full_worker_supervisor(
    *,
    cfg_path: Path,
    run_id: str,
    read_only: bool,
    now_utc_arg: str,
) -> int:
    continuation_owner_mode = _norm(os.environ.get("H110_CONTINUATION_OWNER_MODE", "market_payload_owner")).lower()
    use_market_payload_owner = continuation_owner_mode in {"market_payload_owner", "market_payload", "market"}
    use_payload_worker_owner = continuation_owner_mode in {"payload_worker_owner", "payload_worker", "legacy"}
    if not use_market_payload_owner and not use_payload_worker_owner:
        _progress(
            "owner_observe_market_payload_owner_exit",
            run_id=run_id,
            market_payload_owner_pid="",
            observed_rc="",
            observe_state="invalid_owner_mode",
            owner_mode=continuation_owner_mode,
        )
        use_market_payload_owner = True

    # Default to inline owner execution so full-worker lifetime fully covers
    # owner-side convergence windows. Legacy detached supervisor mode can be
    # re-enabled explicitly for rollback/testing.
    detached_owner_mode = _to_bool(
        os.environ.get("H110_SUPERVISOR_DETACHED_OWNER", "0"),
        default=False,
    )
    if not detached_owner_mode:
        cfg = _simple_yaml_load(cfg_path)
        owner_mode = "market_payload_owner" if use_market_payload_owner else "payload_worker_owner"
        _progress(
            "owner_supervisor_inline_owner_mode",
            run_id=run_id,
            owner_mode=owner_mode,
            detached_owner_mode="0",
            reason="default_inline_owner_to_preserve_convergence_lifetime",
        )
        if use_market_payload_owner:
            return _run_market_payload_owner_runtime(
                cfg=cfg,
                run_id=run_id,
                read_only=read_only,
                now_utc_arg=now_utc_arg,
            )
        return _run_payload_worker_owner_runtime(
            cfg=cfg,
            run_id=run_id,
            read_only=read_only,
            now_utc_arg=now_utc_arg,
        )

    _progress(
        "owner_supervisor_detached_owner_mode",
        run_id=run_id,
        detached_owner_mode="1",
        owner_mode=continuation_owner_mode,
    )

    owner_cmd: list[str] = _self_python_cmd(
        "--full-run-worker",
        "--market-payload-owner" if use_market_payload_owner else "--payload-worker-owner",
        "--phase1-config",
        str(cfg_path),
        "--run-id",
        run_id,
    )
    if read_only:
        owner_cmd.append("--read-only")
    if _norm(now_utc_arg):
        owner_cmd.extend(["--now-utc", _norm(now_utc_arg)])

    proc = _popen_hidden(
        owner_cmd,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        env=os.environ.copy(),
    )
    observe_seconds = max(_env_int("H110_PAYLOAD_WORKER_OWNER_OBSERVE_SECONDS", 20), 5)
    observed_rc = ""
    observe_state = "wait_timeout"
    try:
        observed_rc = str(int(proc.wait(timeout=float(observe_seconds))))
        observe_state = "wait_exit"
    except Exception:
        observe_state = f"wait_timeout_after_{observe_seconds}s"

    marker_status, marker_reason = _completion_marker_status_for_run(run_id)
    success_ok, success_reason = _completion_marker_success_for_run(run_id)
    settled_success, marker_status, marker_reason, success_reason = _pilot_terminal_settle_reconcile(
        run_id=run_id,
        initial_marker_status=marker_status,
        initial_marker_reason=marker_reason,
        initial_success_ok=success_ok,
        initial_success_reason=success_reason,
        log_prefix="pilot_parent_classifier_settle",
    )
    settle_seconds = max(_env_int("H110_SUPERVISOR_MARKER_SETTLE_SECONDS", 20), 5)

    if use_market_payload_owner:
        _progress(
            "owner_observe_market_payload_owner_exit",
            run_id=run_id,
            market_payload_owner_pid=str(proc.pid),
            observed_rc=observed_rc,
            observe_state=observe_state,
            marker_status=marker_status,
            marker_reason=marker_reason,
            success_ok="1" if settled_success else "0",
            success_reason=success_reason,
            owner_mode=continuation_owner_mode,
            settle_seconds=str(settle_seconds),
        )
        _progress(
            "owner_observe_direct_artifact_owner_exit",
            run_id=run_id,
            direct_artifact_owner_pid=str(proc.pid),
            observe_window_seconds=str(settle_seconds),
            marker_status=marker_status,
            marker_reason=marker_reason,
            success_ok="1" if settled_success else "0",
            success_reason=success_reason,
        )
    else:
        _progress(
            "owner_observe_payload_worker_exit",
            run_id=run_id,
            payload_worker_pid=str(proc.pid),
            observed_rc=observed_rc,
            observe_state=observe_state,
            marker_status=marker_status,
            marker_reason=marker_reason,
            success_ok="1" if settled_success else "0",
            success_reason=success_reason,
            owner_mode=continuation_owner_mode,
            settle_seconds=str(settle_seconds),
        )
    if settled_success:
        result_payload = _read_json(PHASE1_RESULT_PATH, default={})
        payload_processed_skus, payload_processed_count = (
            _result_payload_processed_skus(result_payload) if isinstance(result_payload, dict) else ([], 0)
        )
        payload_due_count = _to_int((result_payload if isinstance(result_payload, dict) else {}).get("phase1_exception_final_process_count", "0")) or 0
        _progress(
            "multi_sku_owner_enter",
            run_id=run_id,
            owner_mode=continuation_owner_mode,
        )
        _progress(
            "multi_sku_owner_due_count",
            run_id=run_id,
            due_count=str(payload_due_count),
        )
        _progress(
            "multi_sku_owner_processed_count",
            run_id=run_id,
            processed_count=str(payload_processed_count),
        )
        _progress(
            "multi_sku_owner_payload_rows",
            run_id=run_id,
            payload_rows=str(len(payload_processed_skus)),
        )
        scan_state_ok, scan_state_reason, advanced_count = _write_scan_state_from_result_payload(
            run_id=run_id,
            now_utc_text=now_utc_arg,
        )
        _progress(
            "multi_sku_owner_scan_state_advanced_count",
            run_id=run_id,
            advanced_count=str(advanced_count),
        )
        _progress(
            "multi_sku_owner_exit",
            run_id=run_id,
            success_ok="1" if scan_state_ok else "0",
            reason=scan_state_reason,
        )
        if not scan_state_ok:
            _progress(
                "scan_state_write_failed",
                run_id=run_id,
                path=str(SKU_SCAN_STATE_PATH),
                reason=scan_state_reason,
            )
            return 1
        return 0
    if marker_status == "failed":
        return 1
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="H110 - Run one Phase 1 H pilot step")
    parser.add_argument("--phase1-config", default="", help="Path to Phase 1 pilot YAML config")
    parser.add_argument("--read-only", action="store_true", help="Force read-only mode")
    parser.add_argument("--run-id", default="", help="Optional run id from orchestrator")
    parser.add_argument("--now-utc", default="", help="Optional fixed UTC timestamp, ISO")
    parser.add_argument("--full-run-worker", action="store_true", help="Run full H110 execution worker mode")
    parser.add_argument("--payload-worker-owner", action="store_true", help="Run payload-worker owner mode that writes final artifacts")
    parser.add_argument("--market-payload-owner", action="store_true", help="Run market-payload continuation owner mode that writes final artifacts")
    parser.add_argument("--first-sku-worker", action="store_true", help="Run first-SKU worker contract mode")
    parser.add_argument("--worker-input", default="", help="Input JSON path for first-SKU worker mode")
    parser.add_argument("--worker-output", default="", help="Output JSON path for first-SKU worker mode")
    parser.add_argument("--first-sku-exec-worker", action="store_true", help="Run first-SKU full exec worker mode")
    parser.add_argument("--exec-worker-input", default="", help="Input JSON path for first-SKU exec worker mode")
    parser.add_argument("--exec-worker-output", default="", help="Output JSON path for first-SKU exec worker mode")
    parser.add_argument("--first-sku-worker-boundary", action="store_true", help="Run first-SKU worker wait/read boundary")
    parser.add_argument("--first-worker-boundary-input", default="", help="Input JSON path for first-SKU worker boundary")
    parser.add_argument("--first-worker-boundary-output", default="", help="Output JSON path for first-SKU worker boundary")
    parser.add_argument("--first-worker-boundary-run-id", default="", help="Run id for first-SKU worker boundary")
    parser.add_argument("--first-worker-boundary-sku", default="", help="SKU for first-SKU worker boundary")
    parser.add_argument("--sku-pre-result-helper", action="store_true", help="Run isolated pre-result helper")
    parser.add_argument("--sku-helper-input", default="", help="Input JSON path for pre-result helper")
    parser.add_argument("--sku-helper-output", default="", help="Output JSON path for pre-result helper")
    parser.add_argument("--pre-result-worker", action="store_true", help="Run pre-result worker contract mode")
    parser.add_argument("--pre-result-input", default="", help="Input JSON path for pre-result worker")
    parser.add_argument("--pre-result-output", default="", help="Output JSON path for pre-result worker")
    parser.add_argument("--payload-assembly-worker", action="store_true", help="Run isolated payload assembly worker mode")
    parser.add_argument("--payload-assembly-input", default="", help="Input JSON path for payload assembly worker")
    parser.add_argument("--payload-assembly-output", default="", help="Output JSON path for payload assembly worker")
    parser.add_argument("--market-payload-subcall", action="store_true", help="Run isolated market payload subcall mode")
    parser.add_argument("--market-payload-input", default="", help="Input JSON path for market payload subcall mode")
    parser.add_argument("--market-payload-output", default="", help="Output JSON path for market payload subcall mode")
    parser.add_argument("--market-payload-read-boundary", action="store_true", help="Run isolated market payload read boundary mode")
    parser.add_argument("--market-payload-read-boundary-input", default="", help="Input JSON path for market payload read boundary mode")
    parser.add_argument("--market-payload-read-boundary-output", default="", help="Output JSON path for market payload read boundary mode")
    parser.add_argument("--market-payload-probe-boundary", action="store_true", help="Run isolated market payload probe boundary mode")
    parser.add_argument("--market-payload-probe-boundary-input", default="", help="Input JSON path for market payload probe boundary mode")
    parser.add_argument("--market-payload-probe-boundary-output", default="", help="Output JSON path for market payload probe boundary mode")
    parser.add_argument("--market-payload-probe-boundary-read-helper", action="store_true", help="Run isolated market payload probe boundary read helper mode")
    parser.add_argument("--market-payload-probe-boundary-read-input", default="", help="Input JSON path for market payload probe boundary read helper mode")
    parser.add_argument("--market-payload-probe-boundary-read-output", default="", help="Output JSON path for market payload probe boundary read helper mode")
    parser.add_argument("--direct-artifact-owner", action="store_true", help="Run direct artifact owner mode for first-SKU continuation")
    parser.add_argument("--direct-owner-input", default="", help="Input JSON path for direct artifact owner mode")
    parser.add_argument("--owner-worker-payload-worker", action="store_true", help="Run owner-worker payload assembly worker mode")
    parser.add_argument("--owner-worker-payload-input", default="", help="Input JSON path for owner-worker payload worker")
    parser.add_argument("--owner-worker-payload-output", default="", help="Output JSON path for owner-worker payload worker")
    parser.add_argument("--pre-result-ready-reader", action="store_true", help="Run pre-result ready-reader contract mode")
    parser.add_argument("--pre-result-ready-input", default="", help="Input JSON path for pre-result ready-reader")
    parser.add_argument("--pre-result-ready-output", default="", help="Output JSON path for pre-result ready-reader")
    parser.add_argument("--helper-wait-boundary", action="store_true", help="Run isolated helper wait/read boundary")
    parser.add_argument("--wait-boundary-input", default="", help="Input JSON path for helper wait boundary")
    parser.add_argument("--wait-boundary-output", default="", help="Output JSON path for helper wait boundary")
    parser.add_argument("--wait-boundary-run-id", default="", help="Run id for helper wait boundary")
    parser.add_argument("--wait-boundary-sku", default="", help="SKU for helper wait boundary")
    parser.add_argument("--join-isolation", action="store_true", help="Run isolated join/read boundary")
    parser.add_argument("--join-input", default="", help="Input JSON path for join isolation")
    parser.add_argument("--join-output", default="", help="Output JSON path for join isolation")
    parser.add_argument("--join-run-id", default="", help="Run id for join isolation")
    parser.add_argument("--join-sku", default="", help="SKU for join isolation")
    parser.add_argument("--post-helper-acceptance", action="store_true", help="Run post-helper acceptance parser")
    parser.add_argument("--acceptance-input", default="", help="Input helper output JSON path")
    parser.add_argument("--acceptance-output", default="", help="Output acceptance JSON path")
    parser.add_argument("--acceptance-run-id", default="", help="Run id for acceptance helper")
    parser.add_argument("--acceptance-sku", default="", help="SKU for acceptance helper")
    parser.add_argument("--spapi-write-subcall", action="store_true", help="Run isolated SPAPI write submit subcall mode")
    parser.add_argument("--spapi-write-input", default="", help="Input JSON path for SPAPI write submit subcall mode")
    parser.add_argument("--spapi-write-output", default="", help="Output JSON path for SPAPI write submit subcall mode")
    parser.add_argument("--post-exit-terminalizer", action="store_true", help="Run detached post-exit marker terminalizer")
    parser.add_argument("--terminalizer-run-id", default="", help="Run id for detached terminalizer")
    parser.add_argument("--terminalizer-parent-pid", default="", help="Parent pid to watch for detached terminalizer")
    parser.add_argument("--terminalizer-marker-path", default="", help="Completion marker path for detached terminalizer")
    parser.add_argument("--terminalizer-result-path", default="", help="Result payload path for detached terminalizer")
    parser.add_argument("--terminalizer-checkpoint-path", default="", help="Checkpoint state path for detached terminalizer")
    parser.add_argument("--terminalizer-wait-seconds", default="12", help="Detached terminalizer wait window")
    args = parser.parse_args()

    if bool(args.first_sku_exec_worker):
        worker_input = _norm(args.exec_worker_input)
        worker_output = _norm(args.exec_worker_output)
        if not worker_input or not worker_output:
            return 1
        return _run_first_sku_exec_worker_mode(
            input_path=Path(worker_input),
            output_path=Path(worker_output),
        )

    if bool(args.first_sku_worker):
        worker_input = _norm(args.worker_input)
        worker_output = _norm(args.worker_output)
        if not worker_input or not worker_output:
            return 1
        return _run_first_sku_worker_mode(
            input_path=Path(worker_input),
            output_path=Path(worker_output),
        )

    if bool(args.first_sku_worker_boundary):
        boundary_input = _norm(args.first_worker_boundary_input)
        boundary_output = _norm(args.first_worker_boundary_output)
        run_id = _norm(args.first_worker_boundary_run_id)
        sku = _norm(args.first_worker_boundary_sku).upper()
        if not boundary_input or not boundary_output:
            return 1
        return _run_first_sku_worker_boundary_mode(
            input_path=Path(boundary_input),
            output_path=Path(boundary_output),
            run_id=run_id,
            sku=sku,
        )

    if bool(args.sku_pre_result_helper):
        input_path_raw = _norm(args.sku_helper_input)
        output_path_raw = _norm(args.sku_helper_output)
        if not input_path_raw or not output_path_raw:
            _progress("sku_helper_result_invalid", reason="missing_helper_io_args")
            return 1
        return _run_sku_pre_result_helper_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.pre_result_worker):
        input_path_raw = _norm(args.pre_result_input)
        output_path_raw = _norm(args.pre_result_output)
        if not input_path_raw or not output_path_raw:
            _progress("pre_result_worker_contract_invalid", reason="missing_pre_result_worker_io_args")
            return 1
        return _run_pre_result_worker_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.payload_assembly_worker):
        input_path_raw = _norm(args.payload_assembly_input)
        output_path_raw = _norm(args.payload_assembly_output)
        if not input_path_raw or not output_path_raw:
            _progress("payload_worker_failed", reason="missing_payload_assembly_io_args")
            return 1
        return _run_payload_assembly_worker_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.market_payload_subcall):
        input_path_raw = _norm(args.market_payload_input)
        output_path_raw = _norm(args.market_payload_output)
        if not input_path_raw or not output_path_raw:
            _progress("market_payload_subcall_invalid", reason="missing_market_payload_subcall_io_args")
            return 1
        return _run_market_payload_subcall_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.market_payload_read_boundary):
        input_path_raw = _norm(args.market_payload_read_boundary_input)
        output_path_raw = _norm(args.market_payload_read_boundary_output)
        if not input_path_raw or not output_path_raw:
            _progress("market_payload_read_boundary_invalid", reason="missing_market_payload_read_boundary_io_args")
            return 1
        return _run_market_payload_read_boundary_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.market_payload_probe_boundary):
        input_path_raw = _norm(args.market_payload_probe_boundary_input)
        output_path_raw = _norm(args.market_payload_probe_boundary_output)
        if not input_path_raw or not output_path_raw:
            _progress("market_payload_probe_boundary_invalid", reason="missing_market_payload_probe_boundary_io_args")
            return 1
        return _run_market_payload_probe_boundary_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.market_payload_probe_boundary_read_helper):
        input_path_raw = _norm(args.market_payload_probe_boundary_read_input)
        output_path_raw = _norm(args.market_payload_probe_boundary_read_output)
        if not input_path_raw or not output_path_raw:
            _progress("probe_boundary_read_helper_invalid", reason="missing_probe_boundary_read_helper_io_args")
            return 1
        return _run_market_payload_probe_boundary_read_helper_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.direct_artifact_owner):
        input_path_raw = _norm(args.direct_owner_input)
        if not input_path_raw:
            _progress("direct_artifact_owner_marker_failed", reason="missing_direct_owner_input")
            return 1
        return _run_direct_artifact_owner_mode(
            input_path=Path(input_path_raw),
        )

    if bool(args.owner_worker_payload_worker):
        input_path_raw = _norm(args.owner_worker_payload_input)
        output_path_raw = _norm(args.owner_worker_payload_output)
        if not input_path_raw or not output_path_raw:
            _progress("payload_worker_failed", reason="missing_owner_worker_payload_io_args")
            return 1
        return _run_owner_worker_payload_worker_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.pre_result_ready_reader):
        input_path_raw = _norm(args.pre_result_ready_input)
        output_path_raw = _norm(args.pre_result_ready_output)
        if not input_path_raw or not output_path_raw:
            _progress("pre_result_ready_reader_invalid", reason="missing_pre_result_ready_reader_io_args")
            return 1
        return _run_pre_result_ready_reader_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.helper_wait_boundary):
        boundary_input = _norm(args.wait_boundary_input)
        boundary_output = _norm(args.wait_boundary_output)
        run_id = _norm(args.wait_boundary_run_id)
        sku = _norm(args.wait_boundary_sku).upper()
        if not boundary_input or not boundary_output:
            return 1
        return _run_helper_wait_boundary_mode(
            input_path=Path(boundary_input),
            output_path=Path(boundary_output),
            run_id=run_id,
            sku=sku,
        )

    if bool(args.join_isolation):
        join_input = _norm(args.join_input)
        join_output = _norm(args.join_output)
        join_run_id = _norm(args.join_run_id)
        join_sku = _norm(args.join_sku).upper()
        if not join_input or not join_output:
            return 1
        return _run_join_isolation_mode(
            input_path=Path(join_input),
            output_path=Path(join_output),
            run_id=join_run_id,
            sku=join_sku,
        )

    if bool(args.post_helper_acceptance):
        acceptance_input = _norm(args.acceptance_input)
        acceptance_output = _norm(args.acceptance_output)
        if not acceptance_input or not acceptance_output:
            return 1
        return _run_post_helper_acceptance_mode(
            input_path=Path(acceptance_input),
            output_path=Path(acceptance_output),
            run_id=_norm(args.acceptance_run_id),
            sku=_norm(args.acceptance_sku).upper(),
        )

    if bool(args.spapi_write_subcall):
        input_path_raw = _norm(args.spapi_write_input)
        output_path_raw = _norm(args.spapi_write_output)
        if not input_path_raw or not output_path_raw:
            return 1
        return _run_spapi_write_subcall_mode(
            input_path=Path(input_path_raw),
            output_path=Path(output_path_raw),
        )

    if bool(args.post_exit_terminalizer):
        run_id = _norm(args.terminalizer_run_id)
        marker_path_raw = _norm(args.terminalizer_marker_path)
        result_path_raw = _norm(args.terminalizer_result_path)
        checkpoint_path_raw = _norm(args.terminalizer_checkpoint_path)
        if not run_id or not marker_path_raw or not result_path_raw:
            _progress(
                "post_exit_terminalizer_error",
                run_id=run_id,
                reason="missing_terminalizer_args",
            )
            return 1
        parent_pid = _to_int(args.terminalizer_parent_pid)
        if parent_pid is None:
            parent_pid = 0
        wait_seconds = _to_float(args.terminalizer_wait_seconds)
        if wait_seconds is None:
            wait_seconds = 12.0
        return _run_post_exit_terminalizer(
            run_id=run_id,
            parent_pid=int(parent_pid),
            marker_path=Path(marker_path_raw),
            result_path=Path(result_path_raw),
            checkpoint_path=Path(checkpoint_path_raw) if checkpoint_path_raw else None,
            wait_seconds=float(wait_seconds),
        )

    if not _norm(args.phase1_config):
        raise SystemExit("[H110] --phase1-config is required")
    cfg_path = Path(args.phase1_config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    if not cfg_path.exists():
        raise SystemExit(f"[H110] phase1 config not found: {cfg_path}")
    cfg = _simple_yaml_load(cfg_path)
    run_id = _norm(args.run_id)
    if not run_id:
        raise SystemExit("[H110] --run-id is required (provided by H cycle run context)")
    if PHASE1_RESULT_PATH is None:
        raise RuntimeError("h110 completion contract requires H_PHASE1_RESULT_PATH")
    if PHASE1_COMPLETION_MARKER_PATH is None:
        raise RuntimeError("h110 completion contract requires H_PHASE1_COMPLETION_MARKER_PATH")

    if not bool(args.full_run_worker):
        self_exec_full_worker = _to_bool(
            os.environ.get("H110_SELF_EXECV_FULL_WORKER", "0"),
            default=False,
        )
        if not self_exec_full_worker:
            _progress(
                "pilot_owner_worker_inline_dispatch",
                run_id=run_id,
                parent_pid=os.getpid(),
                mode="inline_full_worker_supervisor",
                reason="default_inline_to_preserve_owner_lifetime",
            )
            return _run_full_worker_supervisor(
                cfg_path=cfg_path,
                run_id=run_id,
                read_only=bool(args.read_only),
                now_utc_arg=_norm(args.now_utc),
            )

        cfg_forward = str(cfg_path)
        try:
            cfg_forward = str(cfg_path.relative_to(ROOT))
        except Exception:
            cfg_forward = str(cfg_path)
        cfg_forward = cfg_forward.replace("/", "\\")
        _progress(
            "full_worker_launch_phase1_config",
            run_id=run_id,
            cfg_path=str(cfg_path),
            cfg_forward=cfg_forward,
        )
        worker_cmd: list[str] = _self_python_cmd(
            "--full-run-worker",
            "--phase1-config",
            cfg_forward,
            "--run-id",
            run_id,
        )
        if bool(args.read_only):
            worker_cmd.append("--read-only")
        if _norm(args.now_utc):
            worker_cmd.extend(["--now-utc", _norm(args.now_utc)])
        _progress(
            "full_worker_launch_args_built",
            run_id=run_id,
            argc=str(len(worker_cmd)),
            phase1_config_arg=cfg_forward,
        )
        if "--phase1-config" not in worker_cmd:
            _progress(
                "full_worker_launch_args_failed",
                run_id=run_id,
                reason="missing_phase1_config_flag",
            )
            raise RuntimeError("h110_full_worker_launch_args_invalid:missing_phase1_config_flag")
        try:
            cfg_arg_index = worker_cmd.index("--phase1-config") + 1
            cfg_arg_value = worker_cmd[cfg_arg_index]
        except Exception:
            _progress(
                "full_worker_launch_args_failed",
                run_id=run_id,
                reason="missing_phase1_config_value",
            )
            raise RuntimeError("h110_full_worker_launch_args_invalid:missing_phase1_config_value")
        if _norm(cfg_arg_value) == "":
            _progress(
                "full_worker_launch_args_failed",
                run_id=run_id,
                reason="empty_phase1_config_value",
            )
            raise RuntimeError("h110_full_worker_launch_args_invalid:empty_phase1_config_value")
        _progress(
            "full_worker_launch_args_validated",
            run_id=run_id,
            phase1_config_arg=cfg_arg_value,
            contains_space="1" if " " in cfg_arg_value else "0",
        )
        _progress(
            "h110_full_worker_spawned",
            run_id=run_id,
            parent_pid=os.getpid(),
            cmd=" ".join(worker_cmd),
        )
        _progress(
            "pilot_owner_worker_spawned",
            run_id=run_id,
            parent_pid=os.getpid(),
            launch_mode="self_execv_full_worker",
            cmd=" ".join(worker_cmd),
        )
        try:
            os.execv(sys.executable, worker_cmd)
        except Exception as exc:
            raise RuntimeError(f"h110_full_worker_spawn_failed:{type(exc).__name__}:{exc}") from exc

    if not bool(args.payload_worker_owner) and not bool(args.market_payload_owner):
        return _run_full_worker_supervisor(
            cfg_path=cfg_path,
            run_id=run_id,
            read_only=bool(args.read_only),
            now_utc_arg=_norm(args.now_utc),
        )

    _progress("h110_full_worker_enter", run_id=run_id, worker_pid=os.getpid())
    _progress("pilot_owner_worker_enter", run_id=run_id, worker_pid=os.getpid())
    if bool(args.market_payload_owner):
        return _run_market_payload_owner_runtime(
            cfg=cfg,
            run_id=run_id,
            read_only=bool(args.read_only),
            now_utc_arg=_norm(args.now_utc),
        )
    return _run_payload_worker_owner_runtime(
        cfg=cfg,
        run_id=run_id,
        read_only=bool(args.read_only),
        now_utc_arg=_norm(args.now_utc),
    )


if __name__ == "__main__":
    raise SystemExit(int(main()))



