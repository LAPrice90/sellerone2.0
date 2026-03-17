from __future__ import annotations

import argparse
import contextlib
import csv
import importlib
import io
import json
import os
import signal
import subprocess
import sys
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
H_FLOOR_TRACE_PATH = OUT / "h_floor_truth_trace.csv"
PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH = OUT / "phase1_runtime_floor_snapshot_latest.csv"
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
TOKEN_LEDGER_PATH = OUT / "token_ledger_live.csv"
MIN_REFERRAL_FEE_GBP = 0.25
# Terminology: "commission" in this repricer equals Amazon referral fee.
VAT_DEFAULT = 0.2
LISTINGS_ITEMS_READ_MIN_INTERVAL_SEC = max(float(os.environ.get("SPAPI_LISTINGS_ITEMS_MIN_INTERVAL_SEC", "0.25") or "0.25"), 0.0)
LISTINGS_ITEMS_PATCH_MIN_INTERVAL_SEC = max(float(os.environ.get("SPAPI_LISTINGS_PATCH_MIN_INTERVAL_SEC", "0.25") or "0.25"), 0.0)
H_FLOOR_VAT_POLICY = load_h_floor_vat_policy()

MARKETPLACE_CODE_TO_ID = {"UK": "A1F83G8C2ARO7P"}
MARKETPLACE_ID_TO_CODE = {"A1F83G8C2ARO7P": "UK"}
PHASE1_PILOT_TIMEOUT_SECONDS = max(float(os.environ.get("H_PHASE1_PILOT_TIMEOUT_SECONDS", "300") or "300"), 30.0)
H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_SNAPSHOT_REFRESH_TIMEOUT_SECONDS", "240") or "240"),
    60.0,
)
PHASE1_ALIGNMENT_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_PHASE1_ALIGNMENT_TIMEOUT_SECONDS", "2700") or "2700"),
    30.0,
)
PHASE1_OBSERVATION_PUBLISH_TIMEOUT_SECONDS = max(
    float(os.environ.get("H_PHASE1_OBSERVATION_PUBLISH_TIMEOUT_SECONDS", "300") or "300"),
    30.0,
)
PHASE1_OBSERVATION_PUBLISH_ENABLED = os.environ.get("H_PHASE1_OBSERVATION_PUBLISH_ENABLED", "1").strip() == "1"
PHASE1_OBSERVATION_SHEET_ID = os.environ.get("H_PHASE1_OBSERVATION_SHEET_ID", "").strip()
H_PHASE1_PILOT_MODE = os.environ.get("H_PHASE1_PILOT_MODE", "inline").strip().lower() or "inline"
H_PHASE1_INTEL_MODE = os.environ.get("H_PHASE1_INTEL_MODE", "inline").strip().lower() or "inline"
H_PHASE1_PUBLISH_MODE = os.environ.get("H_PHASE1_PUBLISH_MODE", "inline").strip().lower() or "inline"
H_BISECT_FORCE_INLINE = os.environ.get("H_BISECT_FORCE_INLINE", "0").strip() == "1"
H_STAGE_PROCESS_TREE_SNAPSHOT = os.environ.get("H_STAGE_PROCESS_TREE_SNAPSHOT", "0").strip() == "1"
H_LOOP_ERROR_SLEEP_SECONDS = max(float(os.environ.get("H_LOOP_ERROR_SLEEP_SECONDS", "30") or "30"), 1.0)
H_STEP_MAX_RETRIES = max(int(float(os.environ.get("H_STEP_MAX_RETRIES", "2") or "2")), 1)
H_STEP_BACKOFF_BASE = max(float(os.environ.get("H_STEP_BACKOFF_BASE", "2") or "2"), 1.0)
H_SPLIT_HEALTH_MODE = os.environ.get("H_SPLIT_HEALTH_MODE", "shadow").strip().lower() or "shadow"
H_SPLIT_CHECKLIST_PATH = Path(
    os.environ.get("H_SPLIT_CHECKLIST_PATH", OUT / "cycle_alerts" / "checklist_H_split.csv")
)
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
H_LOCK_STALE_SECONDS = max(float(os.environ.get("H_LOCK_STALE_SECONDS", "900") or "900"), 60.0)
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
    "phase1_pilot_step": ["data/execution_log.csv", "out/h_executioner_action_log.csv"],
    "phase1_runtime_floor_snapshot": ["out/phase1_runtime_floor_snapshot_latest.csv"],
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _effective_phase1_mode(value: object) -> str:
    mode = _normalize_phase1_mode(value, default="inline")
    if H_BISECT_FORCE_INLINE:
        return "inline"
    return mode


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
    _atomic_write_text(H_LIVE_DIR / f"STAGE_ENTER.{stage}.txt", _stage_context_line(stage=stage, run_id=run_id) + "\n")
    _write_process_tree_snapshot(stage=stage, phase="enter", run_id=run_id)
    _log(f"stage {stage} enter")
    return time.monotonic()


def _stage_exit(*, stage: str, run_id: str, started: float, rc: str, note: str = "") -> None:
    elapsed = max(time.monotonic() - started, 0.0)
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
        except Exception:
            pass
    print(f"[H_cycle] {message}")


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


def _pid_alive(pid: int) -> bool:
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


def _acquire_lock() -> None:
    force = os.environ.get("H_CYCLE_FORCE", "0").strip() == "1"
    now_utc = _utc_now()
    if not force:
        for path in _lock_probe_paths():
            if not path.exists():
                continue
            payload = _norm(path.read_text(encoding="utf-8"))
            pid = _parse_lock_pid(payload)
            stale = _lock_is_stale(payload, now_utc)
            if pid is not None and _pid_alive(pid):
                # Strict single-run guarantee: never recover/replace a lock owned by a live process.
                if stale:
                    _log(
                        "lock_blocked "
                        f"path={path} reason=stale_heartbeat_but_pid_alive pid={pid} "
                        f"stale_seconds>={int(H_LOCK_STALE_SECONDS)}"
                    )
                raise SystemExit(f"[H_cycle] lock exists (pid {pid})")
            if pid is not None and stale:
                _log(
                    "lock_recovered "
                    f"path={path} reason=stale_heartbeat_dead_pid pid={pid} "
                    f"stale_seconds>={int(H_LOCK_STALE_SECONDS)}"
                )
            elif pid is not None and not _pid_alive(pid):
                _log(f"lock_recovered path={path} reason=dead_pid pid={pid}")
            else:
                _log(f"lock_recovered path={path} reason=invalid_or_unknown_pid")
            path.unlink(missing_ok=True)
    _write_lock()


def _write_lock() -> None:
    now = _ts()
    payload = f"H|pid={os.getpid()}|start={now}|heartbeat={now}\n"
    for path in _lock_paths():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def _ensure_lock_ownership() -> None:
    had_any_lock = False
    stale_pids: List[str] = []
    for path in _lock_probe_paths():
        if not path.exists():
            continue
        had_any_lock = True
        payload = _norm(path.read_text(encoding="utf-8"))
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


def _release_lock() -> None:
    for path in _lock_probe_paths():
        try:
            if not path.exists():
                continue
            payload = _norm(path.read_text(encoding="utf-8"))
            pid = _parse_lock_pid(payload)
            if pid == os.getpid() or pid is None or not _pid_alive(pid):
                path.unlink(missing_ok=True)
        except Exception:
            # Never let cleanup failures on one path skip cleanup on others.
            continue


def _sleep_with_lock_heartbeat(total_seconds: float, *, chunk_seconds: float = 30.0) -> None:
    remaining = max(float(total_seconds), 0.0)
    step = max(float(chunk_seconds), 1.0)
    while remaining > 0:
        _write_lock()
        snooze = min(step, remaining)
        time.sleep(snooze)
        remaining -= snooze


def _run_with_retries(name: str, fn, *, attempts: int = H_STEP_MAX_RETRIES) -> object:
    max_attempts = max(int(attempts), 1)
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                raise
            if attempt >= max_attempts:
                _log(f"{name} failed after {attempt} attempts error={exc}")
                raise
            backoff = min(H_STEP_BACKOFF_BASE ** attempt, 60.0)
            _log(f"{name} retry attempt={attempt + 1} in {backoff:.1f}s error={exc}")
            time.sleep(backoff)


def _kill_switch_active() -> bool:
    if os.environ.get("H_KILL_SWITCH", "0").strip() == "1":
        return True
    return KILL_SWITCH_PATH.exists()


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
    merged.to_csv(path, index=False)


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
    run_id = now_utc.strftime("%Y%m%dT%H%M%SZ")

    try:
        rows_out: List[Dict[str, str]] = []
        seller_rows_out: List[Dict[str, str]] = []
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
            own_map = run_own_offer_price_lookup(
                skus=skus,
                marketplace_id=mp_id,
                run_id=run_id,
                script_name=SOURCE,
                progress_callback=_refresh_progress,
            )
            progress_state["stage"] = "own_offer_lookup_done"
            _ensure_refresh_not_timed_out("after_own_offer_lookup")
            progress_state["stage"] = "item_offers"
            if item_offers_enabled:
                item_stage_start = _stage_enter(stage="item_offers", run_id=stage_run_id or run_id)
                try:
                    bb_map, offer_rows = run_market_context_lookup_with_offers(
                        sku_asin_rows=sku_asins,
                        marketplace_id=mp_id,
                        snapshot_timestamp_utc=snapshot_ts,
                        snapshot_asof_date=snapshot_date,
                        run_id=run_id,
                        script_name=SOURCE,
                        progress_callback=_refresh_progress,
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
            for sku in skus:
                sku_key = str(sku).strip().upper()
                bb = bb_map.get(sku_key, {})
                our_price = _norm((own_map.get(sku_key) or {}).get("price", ""))
                buy_box_price = _norm(bb.get("price", ""))
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
                    "buy_box_channel": (_norm(bb.get("buy_box_channel", "")) or "Unknown"),
                    "lowest_fba_price": _norm(bb.get("lowest_fba_price", "")),
                    "lowest_fbm_price": _norm(bb.get("lowest_fbm_price", "")),
                    "offer_count_fba": _norm(bb.get("offer_count_fba", "")),
                    "offer_count_fbm": _norm(bb.get("offer_count_fbm", "")),
                    "bsr": "",
                    "bsr_category": "",
                    "source": "SPAPI",
                    "notes": notes_by_sku.get(sku_key, ""),
                }
                rows_out.append(row)

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

        _upsert_snapshot_rows(OUT / f"listing_offer_snapshot_{snapshot_date}.csv", listing_df, ["marketplace", "sku"])
        if not seller_df.empty:
            _upsert_snapshot_rows(
                OUT / f"listing_offer_seller_snapshot_{snapshot_date}.csv",
                seller_df,
                ["marketplace", "sku", "asin", "seller_id"],
            )
        _log(f"snapshot_refresh ok listing_rows={len(listing_df.index)} seller_rows={len(seller_df.index)}")
        _log(f"snapshot_refresh timing elapsed_seconds={_fmt(_r2(time.monotonic() - refresh_started))}")
        status = "ok"
        return {
            "last_snapshot_refresh_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot_refresh_attempted": "1",
            "snapshot_refresh_status": status,
        }
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
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

    df["sku_key"] = df["sku"].astype(str).str.strip().str.upper()
    df["seller_key"] = df["seller_id"].astype(str).str.strip()
    scoped = df.loc[df["sku_key"].isin([s.upper() for s in active_skus])].copy()
    scoped = scoped.loc[scoped["seller_key"].ne("")].copy()
    if scoped.empty:
        raise RuntimeError("Seller profile build failed: no seller rows for active lab SKUs in latest snapshot")

    our_seller = _optional_seller_partner_id()
    if our_seller:
        scoped = scoped.loc[~scoped["seller_key"].eq(our_seller)].copy()
    if scoped.empty:
        raise RuntimeError("Seller profile build failed: all seller rows filtered as self rows")

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
        raise RuntimeError("Seller profile build failed: no profile rows produced")

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
        raise RuntimeError(f"Executioner guardrail fail: pilot SKU not in snapshot {snapshot_path.name}")
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


def _run_phase1_pilot_subprocess(*, now_utc: datetime, run_id: str, config_path: str, read_only: bool) -> dict[str, str]:
    pilot_mode = _effective_phase1_mode(H_PHASE1_PILOT_MODE)
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
    try:
        if progress_path.exists():
            progress_path.unlink()
    except Exception:
        pass

    if pilot_mode == "inline":
        _log(
            "phase1 pilot_step inline_start "
            f"timeout_seconds={int(PHASE1_PILOT_TIMEOUT_SECONDS)} "
            f"read_only={'1' if read_only else '0'} "
            f"progress_path={progress_path}"
        )
        start_monotonic = time.monotonic()
        _write_watchdog_marker(
            name="WATCHDOG_ENTER.txt",
            log_prefix="phase1_pilot_step",
            details=f"mode=inline cmd={' '.join(str(part) for part in pilot_argv)}",
        )
        proc = _run_module_inline_capture(
            module_path="scripts.flows.H.H110_run_phase1_h_pilot",
            argv=pilot_argv,
            env_updates={"H_PHASE1_PROGRESS_PATH": str(progress_path)},
        )
        elapsed = max(time.monotonic() - start_monotonic, 0.0)
        stderr_tail = (_norm(proc.stderr) or "").strip().splitlines()[-1:] or [""]
        progress_tail = _tail_line(progress_path)
        _log(
            "phase1 pilot_step inline_end "
            f"rc={proc.returncode} "
            f"duration_s={_fmt(_r2(elapsed))} "
            f"stderr_tail={stderr_tail[0]} "
            f"progress_tail={progress_tail}"
        )
        _write_watchdog_marker(
            name="WATCHDOG_EXIT.txt",
            log_prefix="phase1_pilot_step",
            details=f"mode=inline rc={int(proc.returncode)} reason=inline_return",
        )
        if proc.returncode != 0:
            stderr = (_norm(proc.stderr) or "").strip()
            stdout = (_norm(proc.stdout) or "").strip()
            details = stderr or stdout or f"rc={proc.returncode}"
            raise RuntimeError(f"phase1 pilot step failed: {details}")
        lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
        if not lines:
            raise RuntimeError("phase1 pilot step returned no output")
        try:
            payload = json.loads(lines[-1])
        except Exception as exc:
            raise RuntimeError(f"phase1 pilot step returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("phase1 pilot step payload is not a JSON object")
        return {str(k): str(v) for k, v in payload.items()}

    cmd = [sys.executable, *pilot_argv]
    heartbeat_every_seconds = 30.0
    poll_seconds = 5.0
    _log(
        "phase1 pilot_step start "
        f"mode=subprocess "
        f"timeout_seconds={int(PHASE1_PILOT_TIMEOUT_SECONDS)} "
        f"read_only={'1' if read_only else '0'} "
        f"progress_path={progress_path}"
    )
    start_monotonic = time.monotonic()
    last_heartbeat = start_monotonic
    env = os.environ.copy()
    env["H_PHASE1_PROGRESS_PATH"] = str(progress_path)
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    _write_watchdog_marker(
        name="WATCHDOG_ENTER.txt",
        log_prefix="phase1_pilot_step",
        details=f"pid={proc.pid} cmd={' '.join(str(part) for part in cmd)}",
    )
    _log(f"phase1 pilot_step child_started pid={proc.pid} run_id={run_id}")
    stdout_text = ""
    stderr_text = ""
    while True:
        try:
            stdout_text, stderr_text = proc.communicate(timeout=poll_seconds)
            break
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start_monotonic
            if elapsed >= PHASE1_PILOT_TIMEOUT_SECONDS:
                _write_watchdog_kill_marker(
                    log_prefix="phase1_pilot_step",
                    pid=proc.pid,
                    elapsed_seconds=elapsed,
                    timeout_seconds=PHASE1_PILOT_TIMEOUT_SECONDS,
                    cmd=cmd,
                )
                proc.kill()
                stdout_text, stderr_text = proc.communicate()
                _write_watchdog_marker(
                    name="WATCHDOG_EXIT.txt",
                    log_prefix="phase1_pilot_step",
                    details="rc=124 reason=timeout_kill",
                )
                stderr_tail = (stderr_text or "").strip().splitlines()[-1:] or [""]
                progress_tail = _tail_line(progress_path)
                raise RuntimeError(
                    "phase1 pilot step timeout "
                    f"after {int(PHASE1_PILOT_TIMEOUT_SECONDS)}s "
                    f"stderr_tail={stderr_tail[0]} "
                    f"progress_tail={progress_tail}"
                )
            if elapsed - last_heartbeat >= heartbeat_every_seconds:
                progress_tail = _tail_line(progress_path)
                _log(
                    "phase1 pilot_step waiting "
                    f"elapsed_seconds={_fmt(_r2(elapsed))} "
                    f"child_pid={proc.pid} "
                    f"progress_tail={progress_tail}"
                )
                last_heartbeat = time.monotonic()

    elapsed = time.monotonic() - start_monotonic
    stderr_tail = (stderr_text or "").strip().splitlines()[-1:] or [""]
    progress_tail = _tail_line(progress_path)
    _log(
        "phase1 pilot_step done "
        f"rc={proc.returncode} "
        f"elapsed_seconds={_fmt(_r2(elapsed))} "
        f"stderr_tail={stderr_tail[0]} "
        f"progress_tail={progress_tail}"
    )
    _write_watchdog_marker(
        name="WATCHDOG_EXIT.txt",
        log_prefix="phase1_pilot_step",
        details=f"rc={int(proc.returncode)} reason=communicate_done",
    )
    if proc.returncode != 0:
        stderr = (stderr_text or "").strip()
        stdout = (stdout_text or "").strip()
        details = stderr or stdout or f"rc={proc.returncode}"
        raise RuntimeError(f"phase1 pilot step failed: {details}")
    lines = [ln.strip() for ln in (stdout_text or "").splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("phase1 pilot step returned no output")
    try:
        payload = json.loads(lines[-1])
    except Exception as exc:
        raise RuntimeError(f"phase1 pilot step returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("phase1 pilot step payload is not a JSON object")
    return {str(k): str(v) for k, v in payload.items()}


def _run_subprocess_with_watchdog(
    cmd: List[str],
    *,
    timeout_seconds: float,
    cwd: Path | None = None,
    log_prefix: str = "",
    heartbeat_every_seconds: float = 30.0,
    poll_seconds: float = 5.0,
) -> subprocess.CompletedProcess:
    start_monotonic = time.monotonic()
    last_heartbeat = start_monotonic
    _write_watchdog_marker(
        name="WATCHDOG_ENTER.txt",
        log_prefix=log_prefix or "subprocess",
        details=f"timeout_seconds={int(timeout_seconds)} cmd={' '.join(str(part) for part in cmd)}",
    )
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd or ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout_text = ""
    stderr_text = ""
    while True:
        try:
            stdout_text, stderr_text = proc.communicate(timeout=poll_seconds)
            rc = int(proc.returncode)
            _write_watchdog_marker(
                name="WATCHDOG_EXIT.txt",
                log_prefix=log_prefix or "subprocess",
                details=f"rc={rc} reason=communicate_done",
            )
            return subprocess.CompletedProcess(cmd, rc, stdout_text, stderr_text)
        except subprocess.TimeoutExpired:
            elapsed = max(time.monotonic() - start_monotonic, 0.0)
            if elapsed >= float(timeout_seconds):
                _write_watchdog_kill_marker(
                    log_prefix=log_prefix or "subprocess",
                    pid=proc.pid,
                    elapsed_seconds=elapsed,
                    timeout_seconds=timeout_seconds,
                    cmd=cmd,
                )
                proc.kill()
                stdout_text, stderr_text = proc.communicate()
                _write_watchdog_marker(
                    name="WATCHDOG_EXIT.txt",
                    log_prefix=log_prefix or "subprocess",
                    details="rc=124 reason=timeout_kill",
                )
                _log(
                    "WATCHDOG_KILL "
                    f"log_prefix={log_prefix or 'subprocess'} "
                    f"pid={proc.pid} "
                    f"elapsed_seconds={_fmt(_r2(elapsed))} "
                    f"timeout_seconds={int(timeout_seconds)} "
                    f"rc=124"
                )
                timeout_note = (
                    f"watchdog_timeout_seconds={int(timeout_seconds)};"
                    f"log_prefix={log_prefix or 'subprocess'}"
                )
                stderr_joined = (stderr_text or "").strip()
                if stderr_joined:
                    stderr_joined = f"{stderr_joined}\n{timeout_note}"
                else:
                    stderr_joined = timeout_note
                return subprocess.CompletedProcess(cmd, 124, stdout_text, stderr_joined)
            if elapsed - last_heartbeat >= heartbeat_every_seconds:
                _write_lock()
                if log_prefix:
                    _log(f"{log_prefix} waiting elapsed_seconds={_fmt(_r2(elapsed))}")
                last_heartbeat = time.monotonic()


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
    argv_backup = list(sys.argv)
    try:
        from scripts.flows.A import A015_build_system_health_check as a015_health

        sys.argv = [
            str(health_path),
            "--profile",
            "h",
            "--checklist-path",
            str(H_SPLIT_CHECKLIST_PATH),
            "--no-toast",
        ]
        proc_returncode = int(a015_health._run_main_fail_closed(a015_health.main))
    except Exception as exc:
        return {"rc": "2", "fresh": "0", "error": f"run_error: {exc}"}
    finally:
        sys.argv = argv_backup
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

    counts = _checklist_counts(H_SPLIT_CHECKLIST_PATH)
    snapshot_utc = _checklist_snapshot_utc(H_SPLIT_CHECKLIST_PATH)
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
                    "split_source": H_SPLIT_CHECKLIST_PATH.name,
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


def _run_module_inline(module_path: str, argv: list[str]) -> int:
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
                return int(code)
            return 0
        if rc_raw is None:
            return 0
        return int(rc_raw)
    finally:
        sys.argv = argv_backup


def _run_module_inline_capture(
    *,
    module_path: str,
    argv: list[str],
    env_updates: dict[str, str] | None = None,
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
            rc = _run_module_inline(module_path, argv)
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


def _run_phase1_daily_intel_alignment_subprocess(*, now_utc: datetime, run_id: str, config_path: str) -> dict[str, str]:
    intel_mode = _effective_phase1_mode(H_PHASE1_INTEL_MODE)
    intel_script = resolve_script_path(ROOT / "scripts", "A016_refresh_phase1_daily_intel.py")
    intel_argv = [
        str(intel_script),
        "--phase1-config",
        str(config_path),
    ]
    if intel_mode == "inline":
        _log(
            "phase1 daily_intel alignment inline_start "
            f"timeout_seconds={int(PHASE1_ALIGNMENT_TIMEOUT_SECONDS)}"
        )
        start_monotonic = time.monotonic()
        _write_watchdog_marker(
            name="WATCHDOG_ENTER.txt",
            log_prefix="phase1_daily_intel_alignment",
            details=f"mode=inline cmd={' '.join(str(part) for part in intel_argv)}",
        )
        proc = _run_module_inline_capture(
            module_path="scripts.flows.A.A016_refresh_phase1_daily_intel",
            argv=intel_argv,
        )
        elapsed = max(time.monotonic() - start_monotonic, 0.0)
        _log(
            "phase1 daily_intel alignment inline_end "
            f"rc={proc.returncode} "
            f"duration_s={_fmt(_r2(elapsed))}"
        )
        _write_watchdog_marker(
            name="WATCHDOG_EXIT.txt",
            log_prefix="phase1_daily_intel_alignment",
            details=f"mode=inline rc={int(proc.returncode)} reason=inline_return",
        )
    else:
        cmd = [sys.executable, *intel_argv]
        proc = _run_subprocess_with_watchdog(
            cmd,
            timeout_seconds=PHASE1_ALIGNMENT_TIMEOUT_SECONDS,
            cwd=ROOT,
            log_prefix="phase1 daily_intel alignment",
        )
    parsed = _parse_key_value_lines(proc.stdout or "")
    status = "ok" if proc.returncode == 0 else "failed"
    stderr_text = _norm(proc.stderr or "")
    stdout_text = _norm(proc.stdout or "")
    error_summary = stderr_text or stdout_text

    payload = {
        "phase1_daily_intel_alignment_status": status,
        "phase1_daily_intel_alignment_run_id": run_id,
        "phase1_daily_intel_alignment_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase1_daily_intel_alignment_scope": parsed.get("a016_scope", "full_db"),
        "phase1_daily_intel_alignment_target_mode": parsed.get("a016_target_universe_mode", ""),
        "phase1_daily_intel_alignment_target_source": parsed.get("a016_target_universe_source", ""),
        "phase1_daily_intel_alignment_target_resolved_count": parsed.get("a016_target_universe_resolved_count", ""),
        "phase1_daily_intel_alignment_target_candidate_count": parsed.get("a016_target_universe_candidate_count", ""),
        "phase1_daily_intel_alignment_processed_count": parsed.get("a016_processed", ""),
        "phase1_daily_intel_alignment_missing_compliance_rows": parsed.get("a016_missing_compliance_rows", ""),
        "phase1_daily_intel_alignment_cpt_calls": parsed.get("a016_cpt_calls", ""),
        "phase1_daily_intel_alignment_scope_file": parsed.get("a016_scope_file", ""),
    }
    if status != "ok":
        payload["phase1_daily_intel_alignment_error"] = error_summary[:400]
    return payload


def _run_phase1_observation_publish_subprocess(*, now_utc: datetime, run_id: str) -> dict[str, str]:
    if not PHASE1_OBSERVATION_PUBLISH_ENABLED:
        return {
            "phase1_observation_publish_status": "skipped_disabled",
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
        )
    parsed = _parse_key_value_lines(proc.stdout or "")
    status = "ok" if proc.returncode == 0 else "failed"
    stderr_text = _norm(proc.stderr or "")
    stdout_text = _norm(proc.stdout or "")
    error_summary = stderr_text or stdout_text
    payload = {
        "phase1_observation_publish_status": status,
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


def _write_phase1_runtime_floor_snapshot(now_utc: datetime) -> dict[str, str]:
    event_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "phase1_runtime_floor_snapshot_file": PHASE1_RUNTIME_FLOOR_SNAPSHOT_PATH.name,
        "phase1_runtime_floor_snapshot_utc": event_ts,
        "phase1_runtime_floor_snapshot_rows": "0",
        "phase1_runtime_floor_snapshot_trace_rows": "0",
        "phase1_runtime_floor_snapshot_status": "missing_inputs",
    }

    if not PHASE1_EXECUTION_LOG_PATH.exists():
        payload["phase1_runtime_floor_snapshot_status"] = "missing_execution_log"
        return payload

    try:
        exec_df = pd.read_csv(PHASE1_EXECUTION_LOG_PATH, dtype=str).fillna("")
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
            "hard_floor_gbp": "execution_hard_floor_gbp",
            "final_ceiling_landed_gbp": "execution_final_ceiling_landed_gbp",
            "reason_codes_json": "execution_reason_codes_json",
        }
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
        "execution_hard_floor_gbp",
        "execution_final_ceiling_landed_gbp",
        "execution_reason_codes_json",
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
    args = _parse_cli_args()
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

    _acquire_lock()
    _ensure_action_log()
    _ensure_live_test_execution_log()
    try:
        while True:
            cycle_manifest = None
            cycle_started = utc_now_iso()
            cycle_run_id = ""
            try:
                _ensure_lock_ownership()
                now_utc = _utc_now()
                run_id = now_utc.strftime("%Y%m%dT%H%M%SZ")
                cycle_run_id = run_id
                cycle_manifest = new_manifest(cycle="H", run_id=f"H_{run_id}", start_time=cycle_started)
                mode_requested = _normalize_split_mode(H_SPLIT_HEALTH_MODE, default="shadow")
                mode_effective = _effective_h_split_mode()
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
                state = _read_state(default={})
                state["h_split_health_mode"] = mode_effective
                if args.phase1_pilot:
                    _log("phase1 snapshot_refresh start")
                    snapshot_stage_started = _stage_enter(stage="snapshot_refresh", run_id=run_id)
                    if stage_enabled.get("snapshot_refresh", True):
                        try:
                            refresh_state = _run_with_retries(
                                "phase1_snapshot_refresh",
                                lambda: _refresh_offer_snapshots(
                                    now_utc,
                                    state,
                                    None,
                                    item_offers_enabled=stage_enabled.get("item_offers", True),
                                    stage_run_id=run_id,
                                ),
                            )
                            _stage_exit(stage="snapshot_refresh", run_id=run_id, started=snapshot_stage_started, rc="0")
                        except Exception:
                            _stage_exit(stage="snapshot_refresh", run_id=run_id, started=snapshot_stage_started, rc="1")
                            raise
                    else:
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
                    if _norm(state.get("phase1_daily_intel_alignment_date", "")) != today_key:
                        intel_stage_started = _stage_enter(stage="phase1_intel", run_id=run_id)
                        if stage_enabled.get("phase1_intel", True):
                            try:
                                alignment_state = _run_with_retries(
                                    "phase1_daily_intel_alignment",
                                    lambda: _run_phase1_daily_intel_alignment_subprocess(
                                        now_utc=now_utc,
                                        run_id=run_id,
                                        config_path=phase1_cfg_path,
                                    ),
                                )
                                _stage_exit(stage="phase1_intel", run_id=run_id, started=intel_stage_started, rc="0")
                            except Exception:
                                _stage_exit(stage="phase1_intel", run_id=run_id, started=intel_stage_started, rc="1")
                                raise
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
                        state["phase1_daily_intel_alignment_date"] = today_key
                        _log(
                            "phase1 daily_intel alignment "
                            f"status={alignment_state.get('phase1_daily_intel_alignment_status', '')} "
                            f"target_mode={alignment_state.get('phase1_daily_intel_alignment_target_mode', '')} "
                            f"resolved_count={alignment_state.get('phase1_daily_intel_alignment_target_resolved_count', '')} "
                            f"processed={alignment_state.get('phase1_daily_intel_alignment_processed_count', '')} "
                            f"missing_compliance={alignment_state.get('phase1_daily_intel_alignment_missing_compliance_rows', '')}"
                        )
                    # Keep seller profile + SOI coverage aligned with active Phase 1 cohort on every pilot cycle.
                    _log("phase1 build_seller_profiles start")
                    seller_state = _run_with_retries("phase1_build_seller_profiles", _build_seller_profiles)
                    state.update(seller_state)
                    _log(
                        "phase1 build_seller_profiles done "
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
                    if stage_enabled.get("phase1_pilot", True):
                        try:
                            pilot_state = _run_with_retries(
                                "phase1_pilot_step",
                                lambda: _run_phase1_pilot_subprocess(
                                    now_utc=now_utc,
                                    run_id=run_id,
                                    config_path=phase1_cfg_path,
                                    read_only=pilot_read_only,
                                ),
                            )
                            _stage_exit(stage="phase1_pilot", run_id=run_id, started=pilot_stage_started, rc="0")
                        except Exception:
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
                    pilot_state["phase1_split_gate_read_only"] = "1" if pilot_read_only else "0"
                    pilot_state["phase1_split_gate_mode"] = mode_effective
                    state.update(pilot_state)
                    floor_snapshot_state = _run_with_retries(
                        "phase1_runtime_floor_snapshot",
                        lambda: _write_phase1_runtime_floor_snapshot(now_utc),
                    )
                    state.update(floor_snapshot_state)
                    if pilot_state.get("daily_intel_missing_for_today", "0") == "1":
                        _log("phase1 h_cycle daily_intel missing for today; run A016_refresh_phase1_daily_intel.py")
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
                    _log("phase1 publish_start")
                    publish_stage_started = _stage_enter(stage="phase1_publish", run_id=run_id)
                    if stage_enabled.get("phase1_publish", True):
                        try:
                            observation_state = _run_phase1_observation_publish_subprocess(now_utc=now_utc, run_id=run_id)
                            _stage_exit(stage="phase1_publish", run_id=run_id, started=publish_stage_started, rc="0")
                        except Exception:
                            _stage_exit(stage="phase1_publish", run_id=run_id, started=publish_stage_started, rc="1")
                            raise
                    else:
                        observation_state = {
                            "phase1_observation_publish_status": "skipped_disabled",
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
                    _write_state(state)
                    if run_once:
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
                _sleep_with_lock_heartbeat(loop_sleep_seconds)
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
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
                if run_once:
                    raise
                _log(f"cycle_recover sleep_seconds={_fmt(_r2(H_LOOP_ERROR_SLEEP_SECONDS))}")
                _sleep_with_lock_heartbeat(H_LOOP_ERROR_SLEEP_SECONDS)
            finally:
                if cycle_manifest is not None:
                    if not cycle_manifest.get("steps"):
                        append_step(
                            cycle_manifest,
                            name="h_cycle_iteration",
                            script_or_function="run_H_pricing_cycle.py",
                            inputs=[],
                            outputs=[
                                "out/h_pricing_cycle_state.json",
                                "out/h_executioner_action_log.csv",
                                "out/phase1_runtime_floor_snapshot_latest.csv",
                            ],
                            rc=0,
                            notes=f"cycle_run_id={cycle_run_id}",
                            started_at=cycle_started,
                            ended_at=utc_now_iso(),
                        )
                    health_path = H_SPLIT_CHECKLIST_PATH if H_SPLIT_CHECKLIST_PATH.exists() else (OUT / "system_health_checklist.csv")
                    finalize_manifest(cycle_manifest, health_checklist_path=health_path, end_time=utc_now_iso())
                    write_manifest(ROOT, cycle_manifest)
    finally:
        _release_lock()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        _release_lock()
        sys.exit(130)

