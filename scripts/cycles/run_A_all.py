"""
Run A001-A004 in order.
"""

from __future__ import annotations

import os
import csv
import json
import re
import subprocess
import sys
import time
import signal
import traceback
import uuid
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

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
    from scripts.core.flow_health_gate import flow_gate_checklist_path
except ModuleNotFoundError:
    from core.flow_health_gate import flow_gate_checklist_path
try:
    from scripts.core.cycle_failure_events import (
        build_failure_event_from_manifest,
        tail_text,
        upsert_cycle_failure_event,
    )
except ModuleNotFoundError:
    from core.cycle_failure_events import (
        build_failure_event_from_manifest,
        tail_text,
        upsert_cycle_failure_event,
    )
try:
    from scripts.core.runtime_stream import (
        build_lock_payload,
        parse_lock_fields as parse_stream_lock_fields,
        parse_lock_pid as parse_stream_lock_pid,
    )
except ModuleNotFoundError:
    from core.runtime_stream import (
        build_lock_payload,
        parse_lock_fields as parse_stream_lock_fields,
        parse_lock_pid as parse_stream_lock_pid,
    )

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
LOCK_PATH = Path(os.environ.get("RUN_LOCK_PATH", ROOT / "out" / "run_cycle.lock"))
A_FORCE = os.environ.get("A_CYCLE_FORCE", "0").strip() == "1"
A_STEAL_LOCK = os.environ.get("A_CYCLE_STEAL_LOCK", "0").strip() == "1"
LOCKS_DIR = ROOT / "out" / "locks"
B_CYCLE_LOCK_PATH = Path(
    os.environ.get(
        "B_CYCLE_LOCK_PATH",
        ROOT / "out" / "systems" / "B" / "live" / "B_cycle.lock",
    )
)
B_LEGACY_CYCLE_LOCK_PATH = Path(
    os.environ.get(
        "B_LEGACY_CYCLE_LOCK_PATH",
        ROOT / "out" / "B_cycle.lock",
    )
)
MAINTENANCE_REQUEST_PATH = Path(
    os.environ.get("MAINTENANCE_REQUEST_PATH", LOCKS_DIR / "maintenance.requested")
)
MAINTENANCE_READY_PATH = Path(
    os.environ.get("MAINTENANCE_READY_PATH", LOCKS_DIR / "maintenance.ready")
)
MAINTENANCE_ACTIVE_PATH = Path(
    os.environ.get("MAINTENANCE_ACTIVE_PATH", LOCKS_DIR / "maintenance.active")
)
MAINTENANCE_REASON = os.environ.get("MAINTENANCE_REASON", "A_cycle_run").strip() or "A_cycle_run"
HEALTH_CHECKLIST_PATH = Path(os.environ.get("HEALTH_CHECKLIST_PATH", ROOT / "out" / "system_health_checklist.csv"))
A_SPLIT_CHECKLIST_PATH = flow_gate_checklist_path("A")
A_SPLIT_HEALTH_MODE = os.environ.get("A_SPLIT_HEALTH_MODE", "split").strip().lower() or "split"
FLOW_SELFTEST_COMPARE_PATH = ROOT / "out" / "cycle_alerts" / "flow_selftest_compare.csv"
FLOW_SELFTEST_STATE_PATH = ROOT / "out" / "cycle_alerts" / "flow_selftest_state.json"
FLOW_SELFTEST_COMPARE_FIELDS = [
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
    "a_match_streak",
    "b_match_streak",
    "e_match_streak",
    "ready_for_cutover",
    "legacy_source",
    "split_source",
    "notes",
]
_ensure_b_after_a_raw = os.environ.get("A_ENSURE_B_AFTER_A", "0").strip().lower()
ENSURE_B_AFTER_A = _ensure_b_after_a_raw in {"1", "true", "yes", "y", "on"}
LEGACY_SHEET_OUTPUT_STEPS = {
    "A001_run_listings_to_sheet.py",
    "A002_run_catalog_items_to_sheet.py",
    "A004_run_fees_to_sheet.py",
    "dedupe_product_db.py",
    "sync_product_db_to_main_sheet.py",
}
_skip_sheet_outputs_raw = os.environ.get("A_SKIP_LEGACY_SHEET_OUTPUT_STEPS", "0").strip().lower()
A_SKIP_LEGACY_SHEET_OUTPUT_STEPS = _skip_sheet_outputs_raw in {"1", "true", "yes", "y", "on"}
_stock_receipts_sheet_raw = os.environ.get("A_ENABLE_STOCK_RECEIPTS_SHEET", "1").strip().lower()
A_ENABLE_STOCK_RECEIPTS_SHEET = _stock_receipts_sheet_raw in {"1", "true", "yes", "y", "on"}
_extra_skip_steps_raw = os.environ.get("A_EXTRA_SKIP_STEPS", "")
A_EXTRA_SKIP_STEPS = {
    step.strip()
    for step in re.split(r"[;,]", _extra_skip_steps_raw)
    if step.strip()
}
try:
    MAINTENANCE_READY_TIMEOUT_SECONDS = int(
        float(
            os.environ.get(
                "A_MAINT_WAIT_READY_MAX_S",
                os.environ.get("MAINTENANCE_READY_TIMEOUT_SECONDS", "300"),
            )
            or "300"
        )
    )
except Exception:
    MAINTENANCE_READY_TIMEOUT_SECONDS = 300
try:
    MAINTENANCE_READY_POLL_SECONDS = float(
        os.environ.get(
            "A_MAINT_POLL_S",
            os.environ.get("MAINTENANCE_READY_POLL_SECONDS", "5"),
        )
        or "5"
    )
except Exception:
    MAINTENANCE_READY_POLL_SECONDS = 5.0
try:
    MAINTENANCE_WAIT_LOG_EVERY_SECONDS = float(
        os.environ.get(
            "A_MAINT_WAIT_LOG_EVERY_S",
            os.environ.get("MAINTENANCE_WAIT_LOG_EVERY_SECONDS", "10"),
        )
        or "10"
    )
except Exception:
    MAINTENANCE_WAIT_LOG_EVERY_SECONDS = 10.0
try:
    B_HEARTBEAT_MAX_AGE_SECONDS = int(float(os.environ.get("A_MAINT_HEARTBEAT_MAX_AGE_S", "90") or "90"))
except Exception:
    B_HEARTBEAT_MAX_AGE_SECONDS = 90
try:
    B_HEARTBEAT_STALE_ASSUME_DEAD_SECONDS = int(
        float(os.environ.get("A_MAINT_HEARTBEAT_STALE_ASSUME_DEAD_S", "600") or "600")
    )
except Exception:
    B_HEARTBEAT_STALE_ASSUME_DEAD_SECONDS = 600
try:
    MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS = float(
        os.environ.get("A_MAINT_B_NOT_RUNNING_STABLE_S", "30") or "30"
    )
except Exception:
    MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS = 30.0
try:
    B_RECOVERY_WAIT_SECONDS = float(os.environ.get("A_B_RECOVERY_WAIT_S", "60") or "60")
except Exception:
    B_RECOVERY_WAIT_SECONDS = 60.0
try:
    B_RECOVERY_POLL_SECONDS = float(os.environ.get("A_B_RECOVERY_POLL_S", "5") or "5")
except Exception:
    B_RECOVERY_POLL_SECONDS = 5.0
_b_recovery_use_scheduler_raw = os.environ.get("A_B_RECOVERY_USE_SCHEDULER", "1").strip().lower()
B_RECOVERY_USE_SCHEDULER = _b_recovery_use_scheduler_raw in {"1", "true", "yes", "y", "on"}
B_SCHEDULER_TASK_NAME = os.environ.get("A_B_SCHEDULER_TASK_NAME", "AMZ Orders").strip() or "AMZ Orders"


def _payload_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, bytes):
        try:
            return payload.decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""


def _parse_lock_pid(payload: object) -> int | None:
    return parse_stream_lock_pid(_payload_text(payload))


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = (result.stdout or "").strip().lower()
            err = (result.stderr or "").strip().lower()
            if "access denied" in out or "access denied" in err:
                return True
            if "no tasks are running" in out:
                return False
            return str(int(pid)) in out
        except Exception:
            return False
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def _parse_lock_field(payload: object, key: str) -> str | None:
    fields = parse_stream_lock_fields(_payload_text(payload))
    if not fields:
        return None
    value = str(fields.get(str(key or "").strip(), "")).strip()
    return value or None


def _heartbeat_age_seconds(heartbeat_utc: str | None) -> float:
    if not heartbeat_utc:
        return 1e9
    try:
        ts = datetime.strptime(heartbeat_utc.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return 1e9


def _terminate_pid(pid: int) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return not _pid_alive(pid)
        if result.returncode == 0:
            return True
        return not _pid_alive(pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        return not _pid_alive(pid)
    for _ in range(10):
        if not _pid_alive(pid):
            return True
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except Exception:
        return not _pid_alive(pid)
    for _ in range(10):
        if not _pid_alive(pid):
            return True
        time.sleep(0.2)
    return not _pid_alive(pid)


def _write_lock() -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = build_lock_payload(owner="A", pid=os.getpid(), start_utc=now, heartbeat_utc=now)
    LOCK_PATH.write_text(payload, encoding="utf-8")


def _acquire_lock() -> None:
    if LOCK_PATH.exists() and not A_FORCE:
        try:
            payload = LOCK_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            payload = "unknown"
        pid = _parse_lock_pid(payload)
        if pid is not None and not _pid_alive(pid):
            print(f"[A_all] stale lock detected (pid {pid} not running). Clearing lock.")
            _release_lock()
            _write_lock()
            return
        if pid is not None and A_STEAL_LOCK:
            print(f"[A_all] lock held by pid {pid}. A_CYCLE_STEAL_LOCK=1, attempting takeover.")
            if _terminate_pid(pid):
                _release_lock()
                _write_lock()
                print(f"[A_all] lock takeover success (terminated pid {pid}).")
                return
            print(f"[A_all] lock takeover failed (pid {pid} still running).")
        print(f"[A_all] lock exists ({payload}). Exiting to avoid overlap.")
        raise SystemExit(2)
    _write_lock()


def _release_lock() -> None:
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def _new_maintenance_request_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    token = uuid.uuid4().hex[:8]
    return f"A_{ts}_{os.getpid()}_{token}"


def _request_maintenance() -> str:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    request_id = _new_maintenance_request_id()
    if MAINTENANCE_REQUEST_PATH.exists():
        try:
            existing = MAINTENANCE_REQUEST_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            existing = ""
        existing_pid = _parse_lock_pid(existing)
        if existing_pid is None or not _pid_alive(existing_pid):
            try:
                MAINTENANCE_REQUEST_PATH.unlink()
                print("[A_all] cleared stale maintenance request marker")
            except Exception:
                pass
    try:
        if MAINTENANCE_READY_PATH.exists():
            MAINTENANCE_READY_PATH.unlink()
    except Exception:
        pass
    payload = (
        f"requested_by=A|pid={os.getpid()}|ts={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}|"
        f"reason={MAINTENANCE_REASON}|request_id={request_id}\n"
    )
    MAINTENANCE_REQUEST_PATH.write_text(payload, encoding="utf-8")
    return request_id


def _b_cycle_lock_paths() -> list[Path]:
    out = [B_CYCLE_LOCK_PATH]
    if B_LEGACY_CYCLE_LOCK_PATH not in out:
        out.append(B_LEGACY_CYCLE_LOCK_PATH)
    return out


def _b_cycle_status() -> dict:
    for lock_path in _b_cycle_lock_paths():
        if not lock_path.exists():
            continue
        try:
            payload = lock_path.read_text(encoding="utf-8")
        except Exception:
            return {
                "running": True,
                "healthy": False,
                "reason": "lock_unreadable",
                "lock_path": str(lock_path),
                "pid": None,
                "heartbeat_age_s": None,
            }
        pid = _parse_lock_pid(payload)
        if pid is None:
            continue
        if not _pid_alive(pid):
            continue
        heartbeat = _parse_lock_field(payload, "heartbeat")
        heartbeat_age_s = _heartbeat_age_seconds(heartbeat)
        running = heartbeat_age_s <= float(B_HEARTBEAT_STALE_ASSUME_DEAD_SECONDS)
        healthy = heartbeat_age_s <= float(B_HEARTBEAT_MAX_AGE_SECONDS)
        return {
            "running": running,
            "healthy": healthy,
            "reason": "lock_pid_alive",
            "lock_path": str(lock_path),
            "pid": pid,
            "heartbeat_age_s": heartbeat_age_s,
        }
    return {
        "running": False,
        "healthy": False,
        "reason": "no_active_b_lock",
        "lock_path": "",
        "pid": None,
        "heartbeat_age_s": None,
    }


def _b_cycle_running() -> bool:
    return bool(_b_cycle_status().get("running", False))


def _maintenance_ready_request_id() -> str:
    if not MAINTENANCE_READY_PATH.exists():
        return ""
    try:
        payload = MAINTENANCE_READY_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return _parse_lock_field(payload, "request_id") or ""


def _wait_for_b_maintenance_ready(request_id: str) -> str:
    started = time.time()
    last_log_elapsed = -1e9
    poll_seconds = max(MAINTENANCE_READY_POLL_SECONDS, 1.0)
    log_every_seconds = max(MAINTENANCE_WAIT_LOG_EVERY_SECONDS, poll_seconds)
    stable_not_running_since = None
    while True:
        if MAINTENANCE_READY_PATH.exists():
            ready_request_id = _maintenance_ready_request_id()
            if ready_request_id and ready_request_id == request_id:
                return "b_ready"
            # Stale ready marker from another request. Clear and keep waiting.
            try:
                MAINTENANCE_READY_PATH.unlink()
                print(
                    "[A_all] ignored stale maintenance ready marker "
                    f"(request_id={ready_request_id or '-'} expected={request_id})"
                )
            except Exception:
                pass
        status = _b_cycle_status()
        if not bool(status.get("running", False)):
            if stable_not_running_since is None:
                stable_not_running_since = time.time()
            down_for = time.time() - stable_not_running_since
            if down_for >= max(MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS, 0.0):
                return "b_not_running"
        else:
            stable_not_running_since = None
        elapsed = time.time() - started
        if elapsed > MAINTENANCE_READY_TIMEOUT_SECONDS:
            if bool(status.get("running", False)):
                return "timeout_b_running"
            return "timeout_b_not_running"
        if elapsed <= 0.1 or (elapsed - last_log_elapsed) >= log_every_seconds:
            heartbeat_age = status.get("heartbeat_age_s")
            heartbeat_note = (
                ""
                if heartbeat_age is None
                else f", hb_age={float(heartbeat_age):.1f}s"
            )
            print(
                f"[A_all] waiting for B cycle boundary... elapsed={elapsed:.0f}s "
                f"(poll {poll_seconds:.0f}s, timeout {MAINTENANCE_READY_TIMEOUT_SECONDS}s, "
                f"status={status.get('reason', '-')}{heartbeat_note})"
            )
            last_log_elapsed = elapsed
        time.sleep(poll_seconds)


def _activate_maintenance(request_id: str) -> None:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    payload = (
        f"active_by=A|pid={os.getpid()}|ts={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}|"
        f"reason={MAINTENANCE_REASON}|request_id={request_id}\n"
    )
    MAINTENANCE_ACTIVE_PATH.write_text(payload, encoding="utf-8")


def _clear_maintenance() -> None:
    for path in (MAINTENANCE_ACTIVE_PATH, MAINTENANCE_REQUEST_PATH, MAINTENANCE_READY_PATH):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


def _clear_stale_b_lock_if_any() -> None:
    for lock_path in _b_cycle_lock_paths():
        if not lock_path.exists():
            continue
        try:
            payload = lock_path.read_text(encoding="utf-8")
        except Exception:
            payload = ""
        pid = _parse_lock_pid(payload)
        if pid is not None and _pid_alive(pid):
            continue
        try:
            lock_path.unlink()
            print(f"[A_all] cleared stale B lock ({lock_path})")
        except Exception:
            pass


def _start_b_cycle_detached() -> bool:
    _clear_stale_b_lock_if_any()
    b_live_dir = ROOT / "out" / "systems" / "B" / "live"
    b_live_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        cmd = ["cmd.exe", "/d", "/c", f"\"{ROOT / 'run_B_cycle.bat'}\""]
    else:
        cmd = [sys.executable, str(resolve_script_path(SCRIPTS, "run_B_supervisor.py"))]
    env = os.environ.copy()
    b_lock_path = B_CYCLE_LOCK_PATH
    env["B_RUN_ONCE"] = "0"
    env["B_ALLOW_DIRECT_WORKER_START"] = "0"
    env["B_CYCLE_LOG_PATH"] = str(b_live_dir / "B_cycle.log")
    env["B_CYCLE_LOCK_PATH"] = str(b_lock_path)
    env["RUN_LOCK_PATH"] = str(b_lock_path)
    env["B002_STATE_PATH"] = str(b_live_dir / "B002_last_run.txt")
    env["REFUND_COLLECTION_STATE_PATH"] = str(b_live_dir / "refund_collection_last_run.txt")
    env["LISTING_COLLECTION_STATE_PATH"] = str(b_live_dir / "listing_offer_collection_last_run.txt")
    kwargs = {
        "cwd": str(ROOT),
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **kwargs)
        print(f"[A_all] started B cycle after A (pid {proc.pid})")
        return True
    except Exception as exc:
        print(f"[A_all] WARN could not restart B cycle after A: {exc}")
        return False


def _run_b_scheduler_once() -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", B_SCHEDULER_TASK_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        print(f"[A_all] WARN could not trigger scheduler task for B: {exc}")
        return False
    output = " ".join(
        part.strip()
        for part in [result.stdout or "", result.stderr or ""]
        if part and part.strip()
    ).strip()
    if result.returncode == 0:
        print(f"[A_all] scheduler trigger sent for B task ({B_SCHEDULER_TASK_NAME})")
        return True
    lowered = output.lower()
    if "already running" in lowered:
        print(f"[A_all] scheduler task already running for B ({B_SCHEDULER_TASK_NAME})")
        return True
    print(
        f"[A_all] WARN scheduler trigger for B failed rc={result.returncode} "
        f"task={B_SCHEDULER_TASK_NAME} detail={output[:280]}"
    )
    return False


def _scheduler_task_running(task_name: str) -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST", "/V"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    text = "\n".join([result.stdout or "", result.stderr or ""])
    match = re.search(r"^Status:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return False
    return match.group(1).strip().lower() == "running"


def _list_b_runtime_pids_windows() -> list[int]:
    if os.name != "nt":
        return []
    ps_cmd = (
        "$ErrorActionPreference='SilentlyContinue'; "
        "Get-CimInstance Win32_Process | Where-Object { "
        "($_.Name -ieq 'cmd.exe' -or $_.Name -ieq 'python.exe' -or $_.Name -ieq 'pythonw.exe') -and "
        "($_.CommandLine -like '*run_B_cycle.bat*' -or "
        "$_.CommandLine -like '*run_B_supervisor.py*' -or "
        "$_.CommandLine -like '*scripts\\\\cycles\\\\run_B_cycle.py*') "
        "} | Select-Object -ExpandProperty ProcessId"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return []
    pids: list[int] = []
    for line in (result.stdout or "").splitlines():
        token = str(line).strip()
        if not token:
            continue
        try:
            pid = int(token)
        except Exception:
            continue
        if pid > 0:
            pids.append(pid)
    return sorted(set(pids), reverse=True)


def _kill_stale_b_runtime_processes() -> int:
    if os.name != "nt":
        return 0
    pids = _list_b_runtime_pids_windows()
    if not pids:
        return 0
    killed = 0
    for pid in pids:
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            continue
        if result.returncode == 0:
            killed += 1
    return killed


def _restart_b_scheduler_task() -> bool:
    if os.name != "nt":
        return False
    try:
        end_result = subprocess.run(
            ["schtasks", "/End", "/TN", B_SCHEDULER_TASK_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        print(f"[A_all] WARN could not end stale B scheduler task: {exc}")
        return False
    end_output = " ".join(
        part.strip()
        for part in [end_result.stdout or "", end_result.stderr or ""]
        if part and part.strip()
    ).strip()
    if end_result.returncode == 0:
        print(f"[A_all] ended stale B scheduler task ({B_SCHEDULER_TASK_NAME})")
    else:
        lowered = end_output.lower()
        if "is not currently running" not in lowered and "there is no running instance" not in lowered:
            print(
                f"[A_all] WARN could not end stale B scheduler task rc={end_result.returncode} "
                f"task={B_SCHEDULER_TASK_NAME} detail={end_output[:280]}"
            )
            return False
    time.sleep(2.0)
    killed = _kill_stale_b_runtime_processes()
    if killed > 0:
        print(f"[A_all] killed stale B runtime processes count={killed}")
    _clear_stale_b_lock_if_any()
    time.sleep(1.0)
    return _run_b_scheduler_once()


def _wait_for_b_healthy_after_a(wait_seconds: float) -> bool:
    poll_seconds = max(B_RECOVERY_POLL_SECONDS, 1.0)
    deadline = time.time() + max(wait_seconds, 0.0)
    while time.time() <= deadline:
        status = _b_cycle_status()
        if bool(status.get("healthy", False)):
            heartbeat_age = status.get("heartbeat_age_s")
            age_note = "" if heartbeat_age is None else f", hb_age={float(heartbeat_age):.1f}s"
            print(
                f"[A_all] B recovery healthy after A "
                f"(pid={status.get('pid')}, source={status.get('lock_path')}{age_note})"
            )
            return True
        time.sleep(poll_seconds)
    status = _b_cycle_status()
    heartbeat_age = status.get("heartbeat_age_s")
    age_note = "" if heartbeat_age is None else f", hb_age={float(heartbeat_age):.1f}s"
    print(
        f"[A_all] B recovery not healthy yet after A "
        f"(status={status.get('reason')}, pid={status.get('pid')}{age_note})"
    )
    return False


def _ensure_b_cycle_running_after_a() -> None:
    if not ENSURE_B_AFTER_A and not B_RECOVERY_USE_SCHEDULER:
        print("[A_all] B recovery after A disabled by config")
        return

    if _wait_for_b_healthy_after_a(B_RECOVERY_WAIT_SECONDS):
        return

    print("[A_all] B not healthy after A clear; starting single recovery action")
    action_taken = False
    if ENSURE_B_AFTER_A:
        action_taken = _start_b_cycle_detached()
    elif B_RECOVERY_USE_SCHEDULER:
        if _scheduler_task_running(B_SCHEDULER_TASK_NAME):
            print("[A_all] B scheduler task is still marked running but B is unhealthy; forcing scheduler restart")
            action_taken = _restart_b_scheduler_task()
        else:
            action_taken = _run_b_scheduler_once()

    if not action_taken:
        print("[A_all] WARN no B recovery action succeeded after A")
        return

    if not _wait_for_b_healthy_after_a(B_RECOVERY_WAIT_SECONDS):
        print("[A_all] WARN B still not healthy after recovery action")


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _normalize_split_mode(value: object, *, default: str = "shadow") -> str:
    raw = str(value or "").strip().lower()
    if raw in {"legacy", "shadow", "split"}:
        return raw
    return default


def _load_flow_selftest_state() -> dict:
    default = {
        "a_match_streak": 0,
        "b_match_streak": 0,
        "e_match_streak": 0,
        "ready_for_cutover": False,
        "updated_utc": "",
    }
    if not FLOW_SELFTEST_STATE_PATH.exists():
        return default
    try:
        payload = json.loads(FLOW_SELFTEST_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default
    if not isinstance(payload, dict):
        return default
    out = default.copy()
    out["a_match_streak"] = _safe_int(payload.get("a_match_streak", 0), 0)
    out["b_match_streak"] = _safe_int(payload.get("b_match_streak", 0), 0)
    out["e_match_streak"] = _safe_int(payload.get("e_match_streak", payload.get("h_clean_streak", 0)), 0)
    out["ready_for_cutover"] = bool(payload.get("ready_for_cutover", False))
    out["updated_utc"] = str(payload.get("updated_utc", "")).strip()
    return out


def _write_flow_selftest_state(state: dict) -> None:
    payload = {
        "a_match_streak": _safe_int(state.get("a_match_streak", 0), 0),
        "b_match_streak": _safe_int(state.get("b_match_streak", 0), 0),
        "e_match_streak": _safe_int(state.get("e_match_streak", 0), 0),
        "ready_for_cutover": bool(state.get("ready_for_cutover", False)),
        "updated_utc": str(state.get("updated_utc", "")).strip(),
    }
    FLOW_SELFTEST_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLOW_SELFTEST_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _append_flow_selftest_compare(row: dict) -> None:
    FLOW_SELFTEST_COMPARE_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = not FLOW_SELFTEST_COMPARE_PATH.exists() or FLOW_SELFTEST_COMPARE_PATH.stat().st_size == 0
    with FLOW_SELFTEST_COMPARE_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FLOW_SELFTEST_COMPARE_FIELDS)
        if need_header:
            writer.writeheader()
        payload = {k: str(row.get(k, "")).strip() for k in FLOW_SELFTEST_COMPARE_FIELDS}
        writer.writerow(payload)


def _effective_a_split_mode() -> str:
    requested = _normalize_split_mode(A_SPLIT_HEALTH_MODE, default="shadow")
    if requested != "shadow":
        return requested
    state = _load_flow_selftest_state()
    if bool(state.get("ready_for_cutover", False)):
        print("[A_all] split_health auto_cutover active (ready_for_cutover=true)")
        return "split"
    return "shadow"


def _update_a_shadow_streak(match: bool) -> dict:
    state = _load_flow_selftest_state()
    if match:
        state["a_match_streak"] = _safe_int(state.get("a_match_streak", 0), 0) + 1
    else:
        state["a_match_streak"] = 0
    a_streak = _safe_int(state.get("a_match_streak", 0), 0)
    b_streak = _safe_int(state.get("b_match_streak", 0), 0)
    e_streak = _safe_int(state.get("e_match_streak", 0), 0)
    ready_before = bool(state.get("ready_for_cutover", False))
    state["ready_for_cutover"] = a_streak >= 10 and b_streak >= 10 and e_streak >= 10
    state["updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_flow_selftest_state(state)
    if state["ready_for_cutover"] and not ready_before:
        print(
            "[A_all] split_health ready_for_cutover=true "
            f"(a_match_streak={a_streak} b_match_streak={b_streak} e_match_streak={e_streak})"
        )
    return state


def _health_counts(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return None
    if "status" not in df.columns:
        return None
    status = df["status"].astype(str).str.lower()
    return int(status.eq("fail").sum()), int(status.eq("warn").sum())


def _alert_summary() -> None:
    path = ROOT / "out" / "system_health_checklist.csv"
    if not path.exists():
        return
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return
    if "status" not in df.columns:
        return
    status = df["status"].str.lower()
    fail = int((status == "fail").sum())
    warn = int((status == "warn").sum())
    if fail or warn:
        print(f"[A_all] Alert: health_check FAIL={fail} WARN={warn}")
    else:
        print("[A_all] Alert: health_check OK")


def _failed_health_checks() -> set[str]:
    path = ROOT / "out" / "system_health_checklist.csv"
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return set()
    if "check" not in df.columns or "status" not in df.columns:
        return set()
    failed = df[df["status"].str.lower() == "fail"]["check"].astype(str)
    return set(failed.tolist())


def _mtime_seconds(path: Path) -> float | None:
    try:
        if not path.exists():
            return None
        return float(path.stat().st_mtime)
    except Exception:
        return None


def _log_step_event(event: str, step_name: str, returncode: int | None = None) -> None:
    if returncode is None:
        print(f"[A_all] {event} {step_name}")
    else:
        print(f"[A_all] {event} {step_name} returncode={int(returncode)}")


def _run_step_subprocess(
    step_name: str,
    cmd: list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
) -> dict[str, object]:
    kwargs: dict[str, object] = {}
    resolved_cwd = str(cwd or ROOT)
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
        kwargs["text"] = True
    if creationflags:
        kwargs["creationflags"] = creationflags
    _log_step_event("STEP_START", step_name)
    proc = subprocess.Popen(cmd, cwd=resolved_cwd, env=env, **kwargs)
    try:
        if capture_output:
            stdout_text, stderr_text = proc.communicate()
            return_code = int(proc.returncode or 0)
        else:
            return_code = int(proc.wait())
            stdout_text = ""
            stderr_text = ""
        _log_step_event("STEP_COMPLETE", step_name, return_code)
        return {
            "started": True,
            "completed": True,
            "returncode": return_code,
            "interrupted": False,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }
    except KeyboardInterrupt:
        _log_step_event("STEP_INTERRUPT", step_name)
        try:
            if os.name == "nt":
                try:
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                except Exception:
                    pass
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
        if os.name == "nt" and proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except Exception:
                pass
        return {
            "started": True,
            "completed": False,
            "returncode": None,
            "interrupted": True,
            "stdout": "",
            "stderr": "",
        }


def _run_a015_with_freshness(
    path: Path,
    env: dict[str, str],
    *,
    extra_args: list[str] | None = None,
    freshness_path: Path | None = None,
    step_started_at: str | None = None,
) -> tuple[dict[str, object], bool]:
    target = freshness_path or HEALTH_CHECKLIST_PATH
    before_mtime = _mtime_seconds(target)
    cmd = [sys.executable, str(path)]
    if extra_args:
        cmd.extend(extra_args)
    result = _run_step_subprocess("A015_build_system_health_check.py", cmd, env=env)
    after_mtime = _mtime_seconds(target)
    start_epoch = _iso_to_epoch(step_started_at or "")
    threshold = (start_epoch - 1.0) if start_epoch is not None else None
    fresh = (
        after_mtime is not None
        and (before_mtime is None or after_mtime > before_mtime)
        and (threshold is None or after_mtime >= threshold)
    )
    return result, fresh


def _run_a015_global_gate(run_id: str, path: Path, env: dict[str, str], *, step_started_at: str) -> tuple[int, bool]:
    result, health_snapshot_fresh = _run_a015_with_freshness(
        path,
        env,
        freshness_path=HEALTH_CHECKLIST_PATH,
        step_started_at=step_started_at,
    )
    if bool(result.get("interrupted", False)):
        print(f"[A_all {run_id}] health_check interrupted - blocking publish")
        return 2, False
    result_rc = int(result.get("returncode", 0) or 0)
    if result_rc == 2:
        failed_checks = _failed_health_checks()
        if failed_checks == {"l1_keys_missing_in_master"}:
            print(
                f"[A_all {run_id}] health_check FAIL on l1_keys_missing_in_master only; "
                "running B004 repair and retrying A015"
            )
            repair_env = os.environ.copy()
            if "ORDER_MASTER_WRITE_SHEETS" not in repair_env:
                repair_env["ORDER_MASTER_WRITE_SHEETS"] = "0"
            repair = subprocess.run(
                [sys.executable, str(resolve_script_path(SCRIPTS, "B004_build_order_master.py"))],
                env=repair_env,
            )
            if repair.returncode == 0:
                result, health_snapshot_fresh = _run_a015_with_freshness(
                    path,
                    env,
                    freshness_path=HEALTH_CHECKLIST_PATH,
                    step_started_at=step_started_at,
                )
                result_rc = int(result.get("returncode", 0) or 0)
    if not health_snapshot_fresh:
        print(f"[A_all {run_id}] health_check did not produce fresh current-cycle checklist - treating as FAIL")
        return 2, False
    if result_rc == 2:
        print(f"[A_all {run_id}] health_check FAIL - blocking publish")
        return 2, True
    if result_rc == 1:
        print(f"[A_all {run_id}] health_check WARN - continuing")
        return 1, True
    return 0, True


def _run_a015_profile_a(path: Path, env: dict[str, str], *, step_started_at: str) -> tuple[int, bool]:
    result, fresh = _run_a015_with_freshness(
        path,
        env,
        extra_args=["--profile", "a", "--checklist-path", str(A_SPLIT_CHECKLIST_PATH), "--no-toast"],
        freshness_path=A_SPLIT_CHECKLIST_PATH,
        step_started_at=step_started_at,
    )
    rc = int(result.get("returncode", 0) or 0)
    if not fresh:
        rc = 2
    return rc, fresh

RUN_ORDER = [
    "A001_run_listings_to_sheet.py",
    "process_stock_receipts_sheet.py",
    "A002_run_catalog_items_to_sheet.py",
    "A003_run_inventory_to_sheet.py",
    "A004_run_fees_to_sheet.py",
    "A010_apply_researching_delta.py",
    "A005_run_inventory_adjustments_report.py",
    "A016_refresh_phase1_daily_intel.py",
    "dedupe_product_db.py",
    "sync_product_db_to_main_sheet.py",
    "run_E_cycle.py",
    "A020_run_daily_finance.py",
    "A015_build_system_health_check.py",
]

STEP_ARTIFACTS = {
    "A001_run_listings_to_sheet.py": ["out/listings_data_latest.csv", "out/merchant_listings_latest.csv"],
    "A002_run_catalog_items_to_sheet.py": ["out/catalog_items_flat.csv"],
    "A003_run_inventory_to_sheet.py": ["out/inventory_snapshot_latest.csv", "out/inventory_history.csv"],
    "A010_apply_researching_delta.py": ["out/inventory_summaries_prev.csv", "out/researching_delta_events.csv"],
    "A005_run_inventory_adjustments_report.py": ["out/inventory_adjustments_latest.csv"],
    "A004_run_fees_to_sheet.py": ["out/fees_latest.csv", "out/fees_failed.csv"],
    "A016_refresh_phase1_daily_intel.py": ["out/phase1_daily_intel_latest.csv"],
    "dedupe_product_db.py": ["out/product_db_preview.csv"],
    "sync_product_db_to_main_sheet.py": ["out/product_db_sync_log.csv"],
    "run_E_cycle.py": ["out/e_run_log.jsonl", "out/e_decision_log.csv"],
    "A020_run_daily_finance.py": ["out/token_cogs_ledger.csv", "out/token_ledger_live.csv"],
    "process_stock_receipts_sheet.py": ["out/stock_receipts_latest.csv"],
    "A015_build_system_health_check.py": ["out/system_health_checklist.csv"],
}

STEP_OPTIONAL_OUTPUTS = {
    "A004_run_fees_to_sheet.py": ["out/fees_failed.csv"],
    "A010_apply_researching_delta.py": ["out/researching_delta_events.csv"],
    "run_E_cycle.py": ["out/e_decision_log.csv"],
    "A020_run_daily_finance.py": ["out/token_cogs_ledger.csv", "out/token_ledger_live.csv"],
}

STALE_OUTPUT_RETRY_STEPS = {
    "A003_run_inventory_to_sheet.py",
    "A016_refresh_phase1_daily_intel.py",
}

A_STEP_OUTPUT_TAIL_CAPTURE_STEPS = {
    "process_stock_receipts_sheet.py",
    "A003_run_inventory_to_sheet.py",
    "A005_run_inventory_adjustments_report.py",
    "A016_refresh_phase1_daily_intel.py",
}


def _resolve_output_path(path_str: str) -> Path:
    raw = Path(str(path_str).strip())
    return raw if raw.is_absolute() else ROOT / raw


def _iso_to_epoch(value: str) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone(timezone.utc).timestamp()
    except Exception:
        return None


def _capture_output_mtimes(paths: list[str]) -> dict[str, float | None]:
    return {str(path).strip(): _mtime_seconds(_resolve_output_path(path)) for path in paths if str(path).strip()}


def _step_output_lists(name: str, outputs: list[str] | None = None) -> tuple[list[str], list[str], list[str]]:
    declared = [str(path).strip() for path in (outputs if outputs is not None else STEP_ARTIFACTS.get(name, [])) if str(path).strip()]
    optional_set = set(STEP_OPTIONAL_OUTPUTS.get(name, []))
    optional = [path for path in declared if path in optional_set]
    required = [path for path in declared if path not in optional_set]
    return declared, required, optional


def _verify_required_outputs(
    required_outputs: list[str],
    *,
    before_mtimes: dict[str, float | None],
    step_started_at: str,
) -> dict[str, object]:
    start_epoch = _iso_to_epoch(step_started_at)
    fresh_threshold = (start_epoch - 1.0) if start_epoch is not None else None
    fresh_outputs: list[str] = []
    missing_outputs: list[str] = []
    stale_outputs: list[str] = []
    for output in required_outputs:
        key = str(output).strip()
        if not key:
            continue
        after_mtime = _mtime_seconds(_resolve_output_path(key))
        before_mtime = before_mtimes.get(key)
        if after_mtime is None:
            missing_outputs.append(key)
            continue
        changed = before_mtime is None or after_mtime > (before_mtime + 1e-6)
        fresh_enough = fresh_threshold is None or after_mtime >= fresh_threshold
        if changed or fresh_enough:
            fresh_outputs.append(key)
        else:
            stale_outputs.append(key)
    verified = not missing_outputs and not stale_outputs
    if verified:
        verification_status = "verified"
        notes = f"fresh_outputs={len(fresh_outputs)}"
    elif missing_outputs:
        verification_status = "failed_missing_outputs"
        notes = f"missing={','.join(missing_outputs[:5])}"
    else:
        verification_status = "failed_stale_outputs"
        notes = f"stale={','.join(stale_outputs[:5])}"
    return {
        "verified": verified,
        "verification_status": verification_status,
        "fresh_outputs": fresh_outputs,
        "missing_outputs": missing_outputs,
        "stale_outputs": stale_outputs,
        "notes": notes,
    }


def _should_retry_stale_outputs(name: str, verification: dict[str, object]) -> bool:
    if name not in STALE_OUTPUT_RETRY_STEPS:
        return False
    status = str(verification.get("verification_status", "") or "").strip()
    return status in {"failed_missing_outputs", "failed_stale_outputs"}


def _result_output_tails(result: dict[str, object] | None) -> tuple[str, str]:
    if not isinstance(result, dict):
        return "", ""
    return (
        tail_text(result.get("stdout", ""), max_chars=2000),
        tail_text(result.get("stderr", ""), max_chars=2000),
    )


def _record_a_failure_event(
    *,
    run_id: str,
    final_state: str,
    cause_code: str,
    cause_detail: str,
    step_name: str = "",
    stage: str = "",
    rc: object = "",
    verification_status: str = "",
    manifest_path: Path | str = "",
    health_path: Path | str = "",
    recovery_action: str = "",
) -> None:
    try:
        upsert_cycle_failure_event(
            {
                "timestamp_utc": utc_now_iso(),
                "cycle": "A",
                "run_id": run_id,
                "final_state": final_state,
                "cause_code": cause_code,
                "cause_detail": cause_detail,
                "step_name": step_name,
                "stage": stage,
                "rc": str(rc),
                "verification_status": verification_status,
                "manifest_path": str(manifest_path) if manifest_path else "",
                "health_path": str(health_path) if health_path else "",
                "source_path": "scripts/cycles/run_A_all.py",
                "recovery_action": recovery_action,
            }
        )
    except Exception as exc:
        print(f"[A_all] WARN failure event write failed: {type(exc).__name__}: {exc}")


def _health_summary_payload(
    path: Path | None,
    *,
    status: str,
    current_cycle_evidence: bool,
    notes: str = "",
) -> dict:
    summary = {
        "source": str(path) if path is not None else "",
        "status": str(status).strip() or "missing",
        "current_cycle_evidence": bool(current_cycle_evidence),
        "fail_count": None,
        "warn_count": None,
        "ok_count": None,
        "notes": str(notes).strip(),
    }
    if not current_cycle_evidence or path is None or not path.exists():
        return summary
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        summary["status"] = "invalid"
        summary["current_cycle_evidence"] = False
        summary["notes"] = str(notes).strip() or f"checklist_read_error={type(exc).__name__}"
        return summary
    if "status" not in df.columns:
        summary["status"] = "invalid"
        summary["current_cycle_evidence"] = False
        summary["notes"] = str(notes).strip() or "missing_status_column"
        return summary
    status_col = df["status"].astype(str).str.lower()
    summary["fail_count"] = int(status_col.eq("fail").sum())
    summary["warn_count"] = int(status_col.eq("warn").sum())
    summary["ok_count"] = int(status_col.eq("ok").sum())
    return summary


def _append_a_step(
    manifest: dict,
    *,
    name: str,
    step_started: str,
    rc: int,
    notes: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    launched: bool = True,
    completed: bool = True,
    outputs_verified: bool = False,
    step_status: str = "",
    verification_status: str = "",
    required_outputs: list[str] | None = None,
    optional_outputs: list[str] | None = None,
    fresh_outputs: list[str] | None = None,
    missing_outputs: list[str] | None = None,
    stale_outputs: list[str] | None = None,
    stdout_tail: str = "",
    stderr_tail: str = "",
) -> None:
    all_outputs, default_required, default_optional = _step_output_lists(name, outputs)
    append_step(
        manifest,
        name=name,
        script_or_function=name,
        inputs=inputs or [],
        outputs=all_outputs,
        rc=int(rc),
        notes=notes,
        started_at=step_started,
        ended_at=utc_now_iso(),
        launched=launched,
        completed=completed,
        outputs_verified=outputs_verified,
        step_status=step_status,
        verification_status=verification_status,
        required_outputs=required_outputs if required_outputs is not None else default_required,
        optional_outputs=optional_outputs if optional_outputs is not None else default_optional,
        fresh_outputs=fresh_outputs or [],
        missing_outputs=missing_outputs or [],
        stale_outputs=stale_outputs or [],
        stdout_tail=tail_text(stdout_tail, max_chars=2000),
        stderr_tail=tail_text(stderr_tail, max_chars=2000),
    )


def main() -> int:
    manifest = None
    run_id = ""
    health_summary_payload = _health_summary_payload(
        None,
        status="missing",
        current_cycle_evidence=False,
        notes="A015 not completed in current run",
    )
    try:
        print("[A_all] requesting maintenance handoff from B cycle")
        request_id = _request_maintenance()
        handoff_mode = _wait_for_b_maintenance_ready(request_id)
        if handoff_mode == "timeout_b_running":
            print("[A_all] ERROR maintenance handoff timeout while B is still running; aborting A run to avoid overlap")
            _record_a_failure_event(
                run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                final_state="failed",
                cause_code="MAINTENANCE_ABORT",
                cause_detail="maintenance handoff timeout while B was still running",
                step_name="maintenance_handoff",
                stage="wait_for_b_maintenance_ready",
                rc=3,
                verification_status="maintenance_timeout",
                recovery_action="inspect B live lock and retry only at a safe maintenance boundary",
            )
            return 3
        if handoff_mode == "timeout_b_not_running":
            print("[A_all] maintenance handoff timeout with B not running; activating A maintenance")
        elif handoff_mode == "b_not_running":
            print("[A_all] maintenance handoff ready (b_not_running); activating A maintenance")
        else:
            print(f"[A_all] maintenance handoff ready ({handoff_mode}); activating A maintenance")
        _activate_maintenance(request_id)
        _acquire_lock()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest = new_manifest(cycle="A", run_id=run_id, start_time=utc_now_iso())
        manifest["configured_step_count"] = len(RUN_ORDER)
        exit_code = 0
        inventory_ok = True
        loop_completed = False
        for name in RUN_ORDER:
            step_started = utc_now_iso()
            path = resolve_script_path(SCRIPTS, name)
            if not path.exists():
                print(f"[A_all {run_id}] missing: {path}")
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=1,
                    notes=f"missing script path={path}",
                    launched=False,
                    completed=False,
                    outputs_verified=False,
                    step_status="failed",
                    verification_status="missing_script",
                )
                exit_code = 1
                break
            if name in A_EXTRA_SKIP_STEPS:
                print(f"[A_all {run_id}] skipping {name} (A_EXTRA_SKIP_STEPS)")
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=0,
                    notes="skipped because A_EXTRA_SKIP_STEPS includes this step",
                    launched=False,
                    completed=False,
                    outputs_verified=False,
                    step_status="skipped",
                    verification_status="skipped_by_config",
                )
                if name == "A003_run_inventory_to_sheet.py":
                    inventory_ok = True
                continue
            # If inventory snapshot failed earlier, skip A010 before running it.
            if name == "A010_apply_researching_delta.py" and not inventory_ok:
                print(f"[A_all {run_id}] skipping A010 (inventory snapshot failed)")
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=0,
                    notes="skipped because A003 inventory step failed earlier",
                    launched=False,
                    completed=False,
                    outputs_verified=False,
                    step_status="skipped",
                    verification_status="skipped_due_to_prior_failure",
                )
                continue
            if A_SKIP_LEGACY_SHEET_OUTPUT_STEPS and name in LEGACY_SHEET_OUTPUT_STEPS:
                print(f"[A_all {run_id}] skipping {name} (legacy sheet output disabled)")
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=0,
                    notes="skipped because A_SKIP_LEGACY_SHEET_OUTPUT_STEPS=1",
                    launched=False,
                    completed=False,
                    outputs_verified=False,
                    step_status="skipped",
                    verification_status="skipped_by_config",
                )
                if name == "A003_run_inventory_to_sheet.py":
                    inventory_ok = True
                continue
            if name == "process_stock_receipts_sheet.py" and not A_ENABLE_STOCK_RECEIPTS_SHEET:
                print(f"[A_all {run_id}] skipping {name} (stock receipts sheet disabled)")
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=0,
                    notes="skipped because A_ENABLE_STOCK_RECEIPTS_SHEET=0",
                    launched=False,
                    completed=False,
                    outputs_verified=False,
                    step_status="skipped",
                    verification_status="skipped_by_config",
                )
                continue
            print(f"[A_all {run_id}] running: {name}")
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                [
                    str(ROOT),
                    str(SCRIPTS),
                    env.get("PYTHONPATH", ""),
                ]
            ).rstrip(os.pathsep)
            if name == "A003_run_inventory_to_sheet.py":
                # Default to no sheet writes to avoid quota issues unless explicitly enabled.
                if "INVENTORY_WRITE_SHEETS" not in env:
                    env["INVENTORY_WRITE_SHEETS"] = "0"
                # Prefer direct collector in A cycle by default.
                # API-owner mode remains opt-in via A003_USE_API_OWNER=1.
                env["INVENTORY_USE_API_OWNER"] = str(env.get("A003_USE_API_OWNER", "0")).strip() or "0"
            if name == "A020_run_daily_finance.py":
                # Default to skipping Level 3 sheet writes to avoid 10M cell limits.
                if "FIN_L3_SKIP_SHEETS" not in env:
                    env["FIN_L3_SKIP_SHEETS"] = "1"
            if name == "process_stock_receipts_sheet.py":
                # Morning A cycle must explicitly enable receipts processing.
                if "RECEIPTS_RUN" not in env:
                    env["RECEIPTS_RUN"] = "YES"
            if name == "A015_build_system_health_check.py":
                mode_requested = _normalize_split_mode(A_SPLIT_HEALTH_MODE, default="shadow")
                mode_effective = _effective_a_split_mode()
                print(
                    f"[A_all {run_id}] split_health mode_requested={mode_requested} "
                    f"mode_effective={mode_effective}"
                )
                if mode_effective == "legacy":
                    gate_rc, global_fresh = _run_a015_global_gate(run_id, path, env, step_started_at=step_started)
                    outputs_verified = bool(global_fresh)
                    _append_a_step(
                        manifest,
                        name=name,
                        step_started=step_started,
                        rc=gate_rc,
                        notes=f"split_mode=legacy;global_fresh={'1' if global_fresh else '0'}",
                        inputs=[str(HEALTH_CHECKLIST_PATH)],
                        outputs_verified=outputs_verified,
                        step_status="completed" if gate_rc == 0 and outputs_verified else ("degraded" if gate_rc == 1 and outputs_verified else "failed"),
                        verification_status="verified" if outputs_verified else "failed_stale_outputs",
                        fresh_outputs=[str(HEALTH_CHECKLIST_PATH)] if outputs_verified else [],
                        stale_outputs=[] if outputs_verified else [str(HEALTH_CHECKLIST_PATH)],
                    )
                    health_summary_payload = _health_summary_payload(
                        HEALTH_CHECKLIST_PATH,
                        status="current" if outputs_verified else "stale",
                        current_cycle_evidence=outputs_verified,
                        notes="A015 legacy gate current-cycle evidence" if outputs_verified else "A015 legacy gate did not produce fresh current-cycle checklist",
                    )
                    if gate_rc == 2:
                        exit_code = 2
                        break
                    _alert_summary()
                    continue

                if mode_effective == "shadow":
                    gate_rc, global_fresh = _run_a015_global_gate(run_id, path, env, step_started_at=step_started)
                    split_rc, split_fresh = _run_a015_profile_a(path, env, step_started_at=step_started)
                    legacy_counts = _health_counts(HEALTH_CHECKLIST_PATH)
                    split_counts = _health_counts(A_SPLIT_CHECKLIST_PATH)
                    legacy_fail = legacy_counts[0] if legacy_counts is not None else -1
                    legacy_warn = legacy_counts[1] if legacy_counts is not None else -1
                    split_fail = split_counts[0] if split_counts is not None else -1
                    split_warn = split_counts[1] if split_counts is not None else -1
                    legacy_gate_block = gate_rc == 2
                    split_gate_block = bool(split_rc == 2 or (split_counts is not None and split_counts[0] > 0))
                    decision_match = legacy_gate_block == split_gate_block
                    state = _update_a_shadow_streak(decision_match)
                    _append_flow_selftest_compare(
                        {
                            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "cycle_start_utc": run_id,
                            "cycle": "A",
                            "mode_requested": mode_requested,
                            "mode_effective": mode_effective,
                            "legacy_fail_count": "" if legacy_fail < 0 else str(legacy_fail),
                            "legacy_warn_count": "" if legacy_warn < 0 else str(legacy_warn),
                            "legacy_gate_block": "1" if legacy_gate_block else "0",
                            "split_fail_count": "" if split_fail < 0 else str(split_fail),
                            "split_warn_count": "" if split_warn < 0 else str(split_warn),
                            "split_gate_block": "1" if split_gate_block else "0",
                            "decision_match": "1" if decision_match else "0",
                            "a_match_streak": str(_safe_int(state.get("a_match_streak", 0), 0)),
                            "b_match_streak": str(_safe_int(state.get("b_match_streak", 0), 0)),
                            "e_match_streak": str(_safe_int(state.get("e_match_streak", 0), 0)),
                            "ready_for_cutover": "1" if bool(state.get("ready_for_cutover", False)) else "0",
                            "legacy_source": HEALTH_CHECKLIST_PATH.name,
                            "split_source": A_SPLIT_CHECKLIST_PATH.name,
                            "notes": f"split_rc={split_rc};split_fresh={'1' if split_fresh else '0'}",
                        }
                    )
                    print(
                        f"[A_all {run_id}] split_shadow_compare "
                        f"legacy_fail={legacy_fail} legacy_warn={legacy_warn} "
                        f"split_fail={split_fail} split_warn={split_warn} "
                        f"decision_match={'1' if decision_match else '0'} "
                        f"a_match_streak={_safe_int(state.get('a_match_streak', 0), 0)} "
                        f"b_match_streak={_safe_int(state.get('b_match_streak', 0), 0)} "
                        f"e_match_streak={_safe_int(state.get('e_match_streak', 0), 0)} "
                        f"ready_for_cutover={'1' if bool(state.get('ready_for_cutover', False)) else '0'}"
                    )
                    outputs_verified = bool(global_fresh)
                    _append_a_step(
                        manifest,
                        name=name,
                        step_started=step_started,
                        rc=gate_rc,
                        notes=(
                            f"split_mode=shadow;global_fresh={'1' if global_fresh else '0'};"
                            f"split_rc={split_rc};split_fresh={'1' if split_fresh else '0'};"
                            f"legacy_fail={legacy_fail};legacy_warn={legacy_warn};"
                            f"split_fail={split_fail};split_warn={split_warn}"
                        ),
                        inputs=[str(HEALTH_CHECKLIST_PATH), str(A_SPLIT_CHECKLIST_PATH)],
                        outputs=STEP_ARTIFACTS.get(name, []) + [str(A_SPLIT_CHECKLIST_PATH)],
                        outputs_verified=outputs_verified,
                        step_status="completed" if gate_rc == 0 and outputs_verified else ("degraded" if gate_rc == 1 and outputs_verified else "failed"),
                        verification_status="verified" if outputs_verified else "failed_stale_outputs",
                        required_outputs=[str(HEALTH_CHECKLIST_PATH)],
                        optional_outputs=[str(A_SPLIT_CHECKLIST_PATH)],
                        fresh_outputs=[str(HEALTH_CHECKLIST_PATH)] if outputs_verified else [],
                        stale_outputs=[] if outputs_verified else [str(HEALTH_CHECKLIST_PATH)],
                    )
                    health_summary_payload = _health_summary_payload(
                        HEALTH_CHECKLIST_PATH,
                        status="current" if outputs_verified else "stale",
                        current_cycle_evidence=outputs_verified,
                        notes="A015 shadow gate current-cycle evidence from global checklist" if outputs_verified else "A015 shadow gate did not produce fresh current-cycle global checklist",
                    )
                    if gate_rc == 2:
                        exit_code = 2
                        break
                    _alert_summary()
                    continue

                # split mode: gate on A profile only, run global as observability-only
                split_gate_rc, split_fresh = _run_a015_profile_a(path, env, step_started_at=step_started)
                if split_gate_rc == 2:
                    print(
                        f"[A_all {run_id}] health_check profile=a FAIL "
                        f"(fresh={'1' if split_fresh else '0'}) - blocking A flow"
                    )
                    _append_a_step(
                        manifest,
                        name=name,
                        step_started=step_started,
                        rc=2,
                        notes=f"split_mode=split;split_fresh={'1' if split_fresh else '0'}",
                        inputs=[str(A_SPLIT_CHECKLIST_PATH)],
                        outputs=STEP_ARTIFACTS.get(name, []) + [str(A_SPLIT_CHECKLIST_PATH)],
                        outputs_verified=bool(split_fresh),
                        step_status="failed",
                        verification_status="verified" if split_fresh else "failed_stale_outputs",
                        required_outputs=[str(A_SPLIT_CHECKLIST_PATH)],
                        optional_outputs=[str(HEALTH_CHECKLIST_PATH)],
                        fresh_outputs=[str(A_SPLIT_CHECKLIST_PATH)] if split_fresh else [],
                        stale_outputs=[] if split_fresh else [str(A_SPLIT_CHECKLIST_PATH)],
                    )
                    health_summary_payload = _health_summary_payload(
                        A_SPLIT_CHECKLIST_PATH,
                        status="stale" if not split_fresh else "current",
                        current_cycle_evidence=bool(split_fresh),
                        notes="A015 split gate failed",
                    )
                    exit_code = 2
                    break
                if split_gate_rc == 1:
                    print(f"[A_all {run_id}] health_check profile=a WARN - continuing")
                global_result, _global_fresh = _run_a015_with_freshness(path, env, freshness_path=HEALTH_CHECKLIST_PATH)
                global_observability_rc = int(global_result.get("returncode", 0) or 0)
                if global_observability_rc != 0:
                    print(
                        f"[A_all {run_id}] health_check global observability rc={global_observability_rc} "
                        "(non-blocking in split mode)"
                    )
                outputs_verified = bool(split_fresh)
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=split_gate_rc,
                    notes=(
                        f"split_mode=split;split_fresh={'1' if split_fresh else '0'};"
                        f"global_observability_rc={global_observability_rc}"
                    ),
                    inputs=[str(HEALTH_CHECKLIST_PATH), str(A_SPLIT_CHECKLIST_PATH)],
                    outputs=STEP_ARTIFACTS.get(name, []) + [str(A_SPLIT_CHECKLIST_PATH)],
                    outputs_verified=outputs_verified,
                    step_status="completed" if split_gate_rc == 0 and outputs_verified else ("degraded" if split_gate_rc == 1 and outputs_verified else "failed"),
                    verification_status="verified" if outputs_verified else "failed_stale_outputs",
                    required_outputs=[str(A_SPLIT_CHECKLIST_PATH)],
                    optional_outputs=[str(HEALTH_CHECKLIST_PATH)],
                    fresh_outputs=[str(A_SPLIT_CHECKLIST_PATH)] if outputs_verified else [],
                    stale_outputs=[] if outputs_verified else [str(A_SPLIT_CHECKLIST_PATH)],
                )
                health_summary_payload = _health_summary_payload(
                    A_SPLIT_CHECKLIST_PATH,
                    status="current" if outputs_verified else "stale",
                    current_cycle_evidence=outputs_verified,
                    notes="A015 split gate current-cycle evidence from profile=a checklist" if outputs_verified else "A015 split gate did not produce fresh current-cycle profile=a checklist",
                )
                _alert_summary()
                continue

            cmd = [sys.executable, str(path)]
            if name == "A016_refresh_phase1_daily_intel.py":
                cmd.extend(["--mode", "full_universe"])
            declared_outputs, required_outputs, optional_outputs = _step_output_lists(name)
            before_mtimes = _capture_output_mtimes(declared_outputs)
            started = time.time()
            capture_step_output = name in A_STEP_OUTPUT_TAIL_CAPTURE_STEPS
            result = _run_step_subprocess(
                name,
                cmd,
                env=env,
                capture_output=capture_step_output,
            )
            elapsed = time.time() - started
            stdout_tail, stderr_tail = _result_output_tails(result)
            if bool(result.get("interrupted", False)):
                print(f"[A_all {run_id}] interrupted during step: {name} after {elapsed:.1f}s")
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=130,
                    notes=f"step interrupted elapsed={elapsed:.1f}s",
                    outputs_verified=False,
                    step_status="failed",
                    verification_status="interrupted",
                    required_outputs=required_outputs,
                    optional_outputs=optional_outputs,
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                )
                exit_code = 130
                break
            result_rc = int(result.get("returncode", 0) or 0)
            if result_rc != 0:
                if name == "H001_capture_offer_snapshot.py":
                    print(f"[A_all {run_id}] WARN H001 failed (code {result_rc}) after {elapsed:.1f}s - continuing")
                    _append_a_step(
                        manifest,
                        name=name,
                        step_started=step_started,
                        rc=result_rc,
                        notes="warning-only step failure",
                        outputs_verified=False,
                        step_status="degraded",
                        verification_status="child_rc_nonzero",
                        required_outputs=required_outputs,
                        optional_outputs=optional_outputs,
                        stdout_tail=stdout_tail,
                        stderr_tail=stderr_tail,
                    )
                    continue
                # If inventory snapshot failed, skip the research/unsellable delta step.
                if name == "A003_run_inventory_to_sheet.py":
                    print(f"[A_all {run_id}] failed: {name} (code {result_rc}) after {elapsed:.1f}s")
                    inventory_ok = False
                    _append_a_step(
                        manifest,
                        name=name,
                        step_started=step_started,
                        rc=result_rc,
                        notes="inventory failed; A010 will be skipped",
                        outputs_verified=False,
                        step_status="degraded",
                        verification_status="child_rc_nonzero",
                        required_outputs=required_outputs,
                        optional_outputs=optional_outputs,
                        stdout_tail=stdout_tail,
                        stderr_tail=stderr_tail,
                    )
                    continue
                # If stock receipts guardrail blocks, do not fail the whole A cycle.
                if name == "process_stock_receipts_sheet.py":
                    receipt_output = " ".join(
                        part.strip()
                        for part in [str(result.get("stdout", "") or ""), str(result.get("stderr", "") or "")]
                        if part and part.strip()
                    )
                    receipt_output = receipt_output.strip()
                    if "Guardrail:" in receipt_output:
                        print(f"[A_all {run_id}] receipts guardrail active, skipping receipts step")
                        _append_a_step(
                            manifest,
                            name=name,
                            step_started=step_started,
                            rc=result_rc,
                            notes=f"guardrail blocked receipts; non-fatal; detail={receipt_output[:300]}",
                            outputs_verified=False,
                            step_status="skipped",
                            verification_status="guardrail_blocked",
                            required_outputs=required_outputs,
                            optional_outputs=optional_outputs,
                            stdout_tail=stdout_tail,
                            stderr_tail=stderr_tail,
                        )
                        continue
                    print(
                        f"[A_all {run_id}] failed: {name} (code {result_rc}) "
                        f"after {elapsed:.1f}s detail={receipt_output[:300]}"
                    )
                    _append_a_step(
                        manifest,
                        name=name,
                        step_started=step_started,
                        rc=result_rc,
                        notes=f"fatal receipt failure elapsed={elapsed:.1f}s detail={receipt_output[:300]}",
                        outputs_verified=False,
                        step_status="failed",
                        verification_status="child_rc_nonzero",
                        required_outputs=required_outputs,
                        optional_outputs=optional_outputs,
                        stdout_tail=stdout_tail,
                        stderr_tail=stderr_tail,
                    )
                    exit_code = result_rc
                    break
                print(f"[A_all {run_id}] failed: {name} (code {result_rc}) after {elapsed:.1f}s")
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=result_rc,
                    notes=f"fatal step failure elapsed={elapsed:.1f}s",
                    outputs_verified=False,
                    step_status="failed",
                    verification_status="child_rc_nonzero",
                    required_outputs=required_outputs,
                    optional_outputs=optional_outputs,
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                )
                exit_code = result_rc
                break
            verification = _verify_required_outputs(
                required_outputs,
                before_mtimes=before_mtimes,
                step_started_at=step_started,
            )
            verification_notes = f"elapsed={elapsed:.1f}s;{verification['notes']}"
            if _should_retry_stale_outputs(name, verification):
                first_verification = str(verification.get("verification_status", "") or "")
                first_notes = str(verification.get("notes", "") or "")
                print(
                    f"[A_all {run_id}] retrying producer after stale output verification: "
                    f"{name} status={first_verification} detail={first_notes}"
                )
                retry_started_at = utc_now_iso()
                retry_before_mtimes = _capture_output_mtimes(declared_outputs)
                retry_started = time.time()
                retry_result = _run_step_subprocess(
                    name,
                    cmd,
                    env=env,
                    capture_output=capture_step_output,
                )
                retry_elapsed = time.time() - retry_started
                retry_stdout_tail, retry_stderr_tail = _result_output_tails(retry_result)
                if bool(retry_result.get("interrupted", False)):
                    print(f"[A_all {run_id}] interrupted during retry step: {name} after {retry_elapsed:.1f}s")
                    _append_a_step(
                        manifest,
                        name=name,
                        step_started=step_started,
                        rc=130,
                        notes=(
                            f"elapsed={elapsed:.1f}s;attempts=2;first={first_verification};"
                            f"retry_interrupted elapsed={retry_elapsed:.1f}s"
                        ),
                        outputs_verified=False,
                        step_status="failed",
                        verification_status="interrupted",
                        required_outputs=required_outputs,
                        optional_outputs=optional_outputs,
                        stdout_tail=retry_stdout_tail or stdout_tail,
                        stderr_tail=retry_stderr_tail or stderr_tail,
                    )
                    exit_code = 130
                    break
                retry_rc = int(retry_result.get("returncode", 0) or 0)
                if retry_rc != 0:
                    print(
                        f"[A_all {run_id}] retry failed: {name} "
                        f"(code {retry_rc}) after {retry_elapsed:.1f}s"
                    )
                    _append_a_step(
                        manifest,
                        name=name,
                        step_started=step_started,
                        rc=retry_rc,
                        notes=(
                            f"elapsed={elapsed:.1f}s;attempts=2;first={first_verification};"
                            f"retry_child_rc_nonzero elapsed={retry_elapsed:.1f}s"
                        ),
                        outputs_verified=False,
                        step_status="failed",
                        verification_status="child_rc_nonzero",
                        required_outputs=required_outputs,
                        optional_outputs=optional_outputs,
                        stdout_tail=retry_stdout_tail or stdout_tail,
                        stderr_tail=retry_stderr_tail or stderr_tail,
                    )
                    exit_code = retry_rc
                    break
                verification = _verify_required_outputs(
                    required_outputs,
                    before_mtimes=retry_before_mtimes,
                    step_started_at=retry_started_at,
                )
                verification_notes = (
                    f"elapsed={elapsed:.1f}s;attempts=2;first={first_verification};"
                    f"first_detail={first_notes};retry_elapsed={retry_elapsed:.1f}s;"
                    f"{verification['notes']}"
                )
                stdout_tail = retry_stdout_tail or stdout_tail
                stderr_tail = retry_stderr_tail or stderr_tail
            if not bool(verification["verified"]):
                print(
                    f"[A_all {run_id}] failed verification: {name} "
                    f"status={verification['verification_status']} detail={verification['notes']}"
                )
                _append_a_step(
                    manifest,
                    name=name,
                    step_started=step_started,
                    rc=0,
                    notes=verification_notes,
                    outputs_verified=False,
                    step_status="failed",
                    verification_status=str(verification["verification_status"]),
                    required_outputs=required_outputs,
                    optional_outputs=optional_outputs,
                    fresh_outputs=list(verification["fresh_outputs"]),
                    missing_outputs=list(verification["missing_outputs"]),
                    stale_outputs=list(verification["stale_outputs"]),
                    stdout_tail=stdout_tail,
                    stderr_tail=stderr_tail,
                )
                exit_code = 1
                break
            _append_a_step(
                manifest,
                name=name,
                step_started=step_started,
                rc=0,
                notes=verification_notes,
                outputs_verified=True,
                step_status="completed",
                verification_status="verified",
                required_outputs=required_outputs,
                optional_outputs=optional_outputs,
                fresh_outputs=list(verification["fresh_outputs"]),
                missing_outputs=list(verification["missing_outputs"]),
                stale_outputs=list(verification["stale_outputs"]),
            )
        else:
            loop_completed = True
        if manifest is not None:
            recorded_count = int(manifest.get("recorded_step_count", 0) or 0)
            configured_count = int(manifest.get("configured_step_count", len(RUN_ORDER)) or len(RUN_ORDER))
            if exit_code == 0 and (not loop_completed or recorded_count < configured_count):
                exit_code = 1
                health_summary_payload = _health_summary_payload(
                    None,
                    status="unverified",
                    current_cycle_evidence=False,
                    notes="configured step list not fully traversed",
                )
        if exit_code == 0:
            print(f"[A_all {run_id}] done")
        return exit_code
    finally:
        if manifest is not None:
            try:
                configured_count = int(manifest.get("configured_step_count", len(RUN_ORDER)) or len(RUN_ORDER))
                recorded_count = int(manifest.get("recorded_step_count", 0) or 0)
                launched_count = int(manifest.get("launched_step_count", 0) or 0)
                completed_count = int(manifest.get("completed_step_count", 0) or 0)
                final_state = ""
                if recorded_count < configured_count:
                    final_state = "partial"
                    if not health_summary_payload.get("current_cycle_evidence", False):
                        health_summary_payload = _health_summary_payload(
                            None,
                            status="unverified",
                            current_cycle_evidence=False,
                            notes=(
                                f"partial traversal recorded={recorded_count} launched={launched_count} "
                                f"completed={completed_count} configured={configured_count}"
                            ),
                        )
                elif exit_code != 0:
                    final_state = "failed"
                else:
                    final_state = "completed"
                finalize_manifest(
                    manifest,
                    health_checklist_path=None,
                    end_time=utc_now_iso(),
                    final_state=final_state or None,
                    health_summary=health_summary_payload,
                )
                manifest_path = write_manifest(ROOT, manifest)
                print(f"[A_all] manifest written: {manifest_path}")
                if final_state in {"failed", "partial"} or exit_code != 0:
                    try:
                        event = build_failure_event_from_manifest(
                            manifest,
                            manifest_path=manifest_path,
                            health_path=str(health_summary_payload.get("source", "") or ""),
                            source_path="scripts/cycles/run_A_all.py",
                            recovery_action="inspect A manifest failed step and rerun only through A-owned proof path",
                        )
                        upsert_cycle_failure_event(event)
                    except Exception as event_exc:
                        print(f"[A_all] WARN failure event write failed: {type(event_exc).__name__}: {event_exc}")
            except Exception as exc:
                print(f"[A_all] WARN manifest write failed: {exc}")
        _release_lock()
        _clear_maintenance()
        print("[A_all] maintenance cleared; B cycle may resume")
        try:
            _ensure_b_cycle_running_after_a()
        except Exception as exc:
            print(f"[A_all] WARN could not ensure B cycle resume after A: {exc!r}")
            traceback.print_exc()


if __name__ == "__main__":
    raise SystemExit(main())

