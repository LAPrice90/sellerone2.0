from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("CONTROLLED_RESTART_ROOT", Path(__file__).resolve().parents[2]))
OUT = ROOT / "out"
LOCKS_DIR = OUT / "locks"
RESTART_DIR = LOCKS_DIR / "restart_control"
MAINT_REQUEST_PATH = LOCKS_DIR / "maintenance.requested"
MAINT_READY_PATH = LOCKS_DIR / "maintenance.ready"
MAINT_ACTIVE_PATH = LOCKS_DIR / "maintenance.active"
H_CONTROLLED_MODE_PATH = LOCKS_DIR / "h_controlled_mode.active"
GATE_SCRIPT = Path(
    os.environ.get(
        "CONTROLLED_RESTART_GATE_SCRIPT",
        str(ROOT / "scripts" / "tools" / "controlled_restart_gate.py"),
    )
)

DEFAULT_WINDOW_START_HOUR = 2
DEFAULT_WINDOW_END_HOUR = 3
DEFAULT_WINDOW_MINUTE_SPAN = 60
DEFAULT_MAX_WAIT_SECONDS = 900
DEFAULT_POLL_SECONDS = 30
DEFAULT_B_HEARTBEAT_MAX_AGE_SECONDS = 180
DEFAULT_H_HEARTBEAT_MAX_AGE_SECONDS = 180
DEFAULT_H_TASK_NAME = os.environ.get("CONTROLLED_RESTART_H_TASK_NAME", "AMZ H Cycle")
DEFAULT_B_TASK_NAME = os.environ.get("CONTROLLED_RESTART_B_TASK_NAME", "AMZ Orders")
DEFAULT_CONTROLLER_TASK_NAME = os.environ.get("CONTROLLED_RESTART_CONTROLLER_TASK_NAME", "AMZ Controlled Restart")
DEFAULT_POST_HEAL_RECHECK_DELAY_SECONDS = 5
DEFAULT_POST_HEAL_SETTLE_SECONDS = 45
DEFAULT_POST_HEAL_SETTLE_POLL_SECONDS = 5
DEFAULT_DRAINABLE_LOCK_IDLE_SECONDS = 120
H_LIVE = OUT / "systems" / "H" / "live"
B_LIVE = OUT / "systems" / "B" / "live"
HOME_TIME_ACTIVE_PATH = H_LIVE / "H_home_time_mode.active.json"
DEFAULT_ESCALATION_MODE_ENV = "H_RESTART_ESCALATION_MODE"
OWNERSHIP_TRANSFER_PATH = RESTART_DIR / "h_restart_ownership_transfer.json"
TRANSIENT_POST_HEAL_BLOCKERS = {
    "H_RUN_IN_PROGRESS_NOT_FINALIZED",
    "H_LAUNCHER_ACTIVE",
    "H_LAUNCHER_PID_STALE",
    "H_LAUNCHER_HEARTBEAT_STALE",
    "H_CYCLE_ACTIVE_LOCK",
    "H_CYCLE_STALE_LOCK_PRESENT",
    "B_ACTIVE_LOCK",
}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, text: str) -> None:
    _ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return _norm(path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except Exception:
        return ""


def _parse_lock_value(payload: str, key: str) -> str:
    for part in [p.strip() for p in payload.split("|") if p.strip()]:
        if part.startswith(f"{key}="):
            return _norm(part.split("=", 1)[1])
    return ""


def _parse_lock_pid(payload: str) -> int | None:
    raw = _parse_lock_value(payload, "pid")
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _parse_utc(value: str) -> datetime | None:
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


def _pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    return bool(_norm(completed.stdout))


def _lock_activity(path: Path, max_age_s: int) -> dict[str, Any]:
    line = _read_first_line(path)
    pid = _parse_lock_pid(line)
    heartbeat_utc = _parse_lock_value(line, "heartbeat")
    heartbeat_dt = _parse_utc(heartbeat_utc)
    age_seconds = None
    if heartbeat_dt is not None:
        age_seconds = max((_utc_now() - heartbeat_dt).total_seconds(), 0.0)
    alive = _pid_alive(pid)
    fresh = alive and (age_seconds is not None) and (age_seconds <= float(max(max_age_s, 1)))
    return {
        "path": str(path),
        "exists": path.exists(),
        "line": line,
        "pid": pid,
        "alive": alive,
        "heartbeat_utc": heartbeat_utc,
        "heartbeat_age_seconds": age_seconds,
        "fresh": fresh,
    }


def _post_heal_runtime_progressing(*, h_heartbeat_max_age_s: int, b_heartbeat_max_age_s: int) -> tuple[bool, dict[str, Any]]:
    h_runtime = _read_json(H_LIVE / "H_runtime_status.json")
    h_mode = _norm(h_runtime.get("mode", "")).upper()
    h_runtime_pid_raw = _norm(h_runtime.get("pid", ""))
    try:
        h_runtime_pid = int(h_runtime_pid_raw) if h_runtime_pid_raw else None
    except Exception:
        h_runtime_pid = None
    h_runtime_pid_alive = _pid_alive(h_runtime_pid)
    run_in_progress = _read_first_line(H_LIVE / "H_run_in_progress.txt")
    finalized = _read_first_line(H_LIVE / "H_last_finalized_run_id.txt")
    h_cycle_lock = _lock_activity(H_LIVE / "H_pricing_cycle.lock", h_heartbeat_max_age_s)
    b_cycle_lock = _lock_activity(B_LIVE / "B_cycle.lock", b_heartbeat_max_age_s)
    h_expected_in_progress = bool(run_in_progress) and (run_in_progress != finalized)
    h_mode_ok = h_mode in {"RUNNING", "SLEEPING", "STOPPING"}
    h_activity_ok = bool(h_cycle_lock.get("fresh", False)) or h_runtime_pid_alive
    h_ok = h_activity_ok and h_mode_ok and h_expected_in_progress
    b_ok = bool(b_cycle_lock.get("fresh", False))
    diag = {
        "h_runtime_mode": h_mode,
        "h_runtime_pid": h_runtime_pid,
        "h_runtime_pid_alive": h_runtime_pid_alive,
        "h_run_in_progress": run_in_progress,
        "h_last_finalized": finalized,
        "h_expected_in_progress": h_expected_in_progress,
        "h_cycle_lock": h_cycle_lock,
        "b_cycle_lock": b_cycle_lock,
        "h_progress_ok": h_ok,
        "b_progress_ok": b_ok,
    }
    return h_ok and b_ok, diag


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def _escalation_mode_enabled(args: argparse.Namespace) -> bool:
    env_flag = _norm(os.environ.get(DEFAULT_ESCALATION_MODE_ENV, "0"))
    return bool(getattr(args, "escalation_mode", False)) or env_flag == "1"


def _write_ownership_transfer(*, active: bool, reason: str, run_id: str) -> tuple[bool, str]:
    payload = {
        "owner": "controlled_restart",
        "active": bool(active),
        "reason": _norm(reason),
        "run_id": _norm(run_id),
        "updated_utc": _utc_ts(),
        "pid": os.getpid(),
    }
    try:
        _write_json(OWNERSHIP_TRANSFER_PATH, payload)
    except Exception:
        return False, "ownership_transfer_write_failed"
    return True, "ownership_transfer_recorded" if active else "ownership_transfer_released"


def _read_text(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _home_time_mode_active() -> bool:
    return HOME_TIME_ACTIVE_PATH.exists()


def _submit_windows_reboot(comment: str) -> tuple[bool, str]:
    message = _norm(comment) or "SellerOne controlled restart"
    completed = subprocess.run(
        ["shutdown", "/r", "/f", "/t", "0", "/c", message],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    merged = f"{_norm(completed.stdout)}\n{_norm(completed.stderr)}".strip().lower()
    if completed.returncode == 0:
        return True, "reboot_command_executed"
    if "already been scheduled" in merged or "shutdown has already been scheduled" in merged:
        return True, "reboot_already_scheduled"
    return False, f"reboot_command_failed_rc_{completed.returncode}"


def _lock_has_recent_activity(lock_path: Path, max_age_s: int, idle_threshold_s: int) -> tuple[bool, dict[str, Any]]:
    lock_info = _lock_activity(lock_path, max_age_s)
    age = lock_info.get("heartbeat_age_seconds")
    alive = bool(lock_info.get("alive", False))
    recent = bool(lock_info.get("exists", False)) and alive and (age is not None) and (float(age) <= float(max(idle_threshold_s, 1)))
    return recent, lock_info


def _window_check(start_hour: int, end_hour: int, minute_span: int) -> tuple[bool, dict[str, Any]]:
    local = _local_now()
    minute_span_safe = max(int(minute_span), 1)
    total_minutes = local.hour * 60 + local.minute
    start_total = max(int(start_hour), 0) * 60
    end_total = max(int(end_hour), 0) * 60
    in_window = False
    if start_total <= end_total:
        if start_total <= total_minutes < end_total:
            in_window = True
    else:
        if total_minutes >= start_total or total_minutes < end_total:
            in_window = True
    if in_window and minute_span_safe < 60:
        in_window = local.minute < minute_span_safe
    return in_window, {
        "local_time": local.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "local_tz": str(local.tzinfo),
        "start_hour": int(start_hour),
        "end_hour": int(end_hour),
        "minute_span": minute_span_safe,
        "in_window": in_window,
    }


def _run_gate(
    *,
    request_drain: bool,
    ignore_window: bool,
    execute_reboot: bool,
    allow_reboot_action: bool,
    b_heartbeat_max_age_s: int,
    h_heartbeat_max_age_s: int,
) -> dict[str, Any]:
    cmd = [sys.executable, str(GATE_SCRIPT)]
    if request_drain:
        cmd.append("--request-drain")
    if ignore_window:
        cmd.append("--ignore-window")
    if execute_reboot:
        cmd.append("--execute-reboot")
    if allow_reboot_action:
        cmd.append("--allow-reboot-action")
    cmd.extend(["--b-heartbeat-max-age-s", str(int(b_heartbeat_max_age_s))])
    cmd.extend(["--h-heartbeat-max-age-s", str(int(h_heartbeat_max_age_s))])
    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    lines = [ln.strip() for ln in (completed.stdout or "").splitlines() if ln.strip()]
    gate_json: dict[str, Any] = {}
    if lines:
        try:
            gate_json = json.loads(lines[-1])
        except Exception:
            gate_json = {}
    return {
        "rc": int(completed.returncode),
        "cmd": cmd,
        "stdout_tail": "\n".join(lines[-5:]),
        "stderr_tail": "\n".join([ln for ln in (completed.stderr or "").splitlines()[-8:] if ln.strip()]),
        "gate_result": gate_json,
    }


def _load_gate_eval(gate_result: dict[str, Any]) -> dict[str, Any]:
    paths = gate_result.get("evidence_paths", {}) if isinstance(gate_result, dict) else {}
    eval_path = Path(_norm(paths.get("eval_path", "")))
    if not eval_path.exists():
        return {}
    try:
        payload = json.loads(eval_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_remove_drain_marker() -> tuple[bool, str]:
    if not MAINT_REQUEST_PATH.exists():
        return False, "not_present"
    if MAINT_ACTIVE_PATH.exists():
        return False, "maintenance_active_present"
    marker_text = _read_text(MAINT_REQUEST_PATH)
    owner_ok = "requested_by=controlled_restart_gate" in marker_text and "reason=overnight_restart_eval" in marker_text
    if not owner_ok:
        return False, "ownership_not_restart_gate"
    if MAINT_READY_PATH.exists():
        ready_text = _read_text(MAINT_READY_PATH)
        ready_ok = _norm(ready_text).startswith("B_READY|")
        if not ready_ok:
            return False, "maintenance_ready_unowned"
    try:
        MAINT_REQUEST_PATH.unlink(missing_ok=True)
    except Exception:
        return False, "unlink_failed"
    if MAINT_READY_PATH.exists():
        try:
            MAINT_READY_PATH.unlink(missing_ok=True)
        except Exception:
            return False, "maintenance_ready_unlink_failed"
    removed = (not MAINT_REQUEST_PATH.exists()) and (not MAINT_READY_PATH.exists())
    return removed, "removed" if removed else "unlink_failed"


def _safe_clear_h_controlled_mode_flag() -> tuple[bool, str]:
    if not H_CONTROLLED_MODE_PATH.exists():
        return False, "not_present"
    try:
        H_CONTROLLED_MODE_PATH.unlink(missing_ok=True)
    except Exception:
        return False, "unlink_failed"
    return not H_CONTROLLED_MODE_PATH.exists(), "removed" if not H_CONTROLLED_MODE_PATH.exists() else "unlink_failed"


def _safe_start_h_cycle_task(task_name: str) -> tuple[bool, str]:
    task = _norm(task_name)
    if not task:
        return False, "missing_task_name"
    completed = subprocess.run(
        ["schtasks", "/Run", "/TN", task],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    stdout_text = _norm(completed.stdout)
    stderr_text = _norm(completed.stderr)
    merged = f"{stdout_text}\n{stderr_text}".strip().lower()
    if completed.returncode == 0:
        return True, "started"
    if "already running" in merged or "instance of the task is already running" in merged:
        return True, "already_running"
    return False, f"failed_rc_{completed.returncode}"


def _safe_stop_task(task_name: str) -> tuple[bool, str]:
    task = _norm(task_name)
    if not task:
        return False, "missing_task_name"
    completed = subprocess.run(
        ["schtasks", "/End", "/TN", task],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    merged = f"{_norm(completed.stdout)}\n{_norm(completed.stderr)}".strip().lower()
    if completed.returncode == 0:
        return True, "stopped"
    if "not currently running" in merged:
        return True, "not_running"
    return False, f"failed_rc_{completed.returncode}"


def _task_state(task_name: str) -> str:
    task = _norm(task_name)
    if not task:
        return ""
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-ScheduledTask -TaskName '{task}' -ErrorAction SilentlyContinue).State",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    return _norm(completed.stdout)


def _process_any_running(command_fragments: list[str]) -> bool:
    frags = [frag for frag in [_norm(x) for x in command_fragments] if frag]
    if not frags:
        return False
    terms = ",".join(["'" + frag.replace("'", "''") + "'" for frag in frags])
    ps = (
        "$terms=@(" + terms + ");"
        "$procs=Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -or $_.Name -eq 'cmd.exe' };"
        "$found=$false;"
        "foreach($p in $procs){$cmd=[string]$p.CommandLine; foreach($t in $terms){ if($cmd -like ('*' + $t + '*')){$found=$true; break}}; if($found){break}};"
        "if($found){'1'}else{'0'}"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    return _norm(completed.stdout) == "1"


def _flow_lock_fresh(lock_path: Path, max_age_s: int) -> bool:
    lock = _lock_activity(lock_path, max_age_s)
    return bool(lock.get("fresh", False))


def _heal_and_start_task(
    task_name: str,
    process_fragments: list[str],
    *,
    flow_lock_path: Path,
    heartbeat_max_age_s: int,
) -> tuple[bool, str]:
    def _verify_live() -> bool:
        return _flow_lock_fresh(flow_lock_path, heartbeat_max_age_s)

    state = _task_state(task_name).lower()
    proc_alive = _process_any_running(process_fragments)
    lock_live = _verify_live()
    if state == "running" and (not proc_alive) and (not lock_live):
        _safe_stop_task(task_name)
        time.sleep(1.0)
        ok, reason = _safe_start_h_cycle_task(task_name)
        if not ok:
            return ok, "healed_stale_running_" + reason
        time.sleep(2.0)
        if _verify_live():
            return True, "healed_stale_running_" + reason + "_verified"
        _safe_stop_task(task_name)
        time.sleep(1.0)
        ok2, reason2 = _safe_start_h_cycle_task(task_name)
        if not ok2:
            return False, "healed_stale_running_retry_" + reason2
        time.sleep(2.0)
        return (_verify_live(), "healed_stale_running_retry_" + reason2 + ("_verified" if _verify_live() else "_unverified"))
    ok, reason = _safe_start_h_cycle_task(task_name)
    if not ok:
        return ok, reason
    time.sleep(2.0)
    if _verify_live():
        return True, reason + "_verified"
    # If scheduler says already running but no fresh lock, force one recycle.
    _safe_stop_task(task_name)
    time.sleep(1.0)
    ok2, reason2 = _safe_start_h_cycle_task(task_name)
    if not ok2:
        return False, reason + "_recycle_" + reason2
    time.sleep(2.0)
    verified = _verify_live()
    return verified, reason + "_recycle_" + reason2 + ("_verified" if verified else "_unverified")


def _write_controller_evidence(*, payload: dict[str, Any], run_id: str) -> dict[str, str]:
    _ensure_dir(RESTART_DIR)
    event_log = RESTART_DIR / "restart_controller.log.jsonl"
    run_json = RESTART_DIR / f"restart_controller.{run_id}.json"
    latest_json = RESTART_DIR / "restart_controller.latest.json"
    latest_txt = RESTART_DIR / "restart_controller.latest.txt"
    _write_json(run_json, payload)
    _write_json(latest_json, payload)
    summary = [
        f"run_id={payload.get('run_id', '')}",
        f"started_utc={payload.get('started_utc', '')}",
        f"finished_utc={payload.get('finished_utc', '')}",
        f"decision={payload.get('decision', '')}",
        f"outcome={payload.get('outcome', '')}",
        f"poll_attempts={payload.get('poll_attempts', 0)}",
        f"reboot_attempted={'1' if payload.get('reboot_attempted', False) else '0'}",
        f"drain_requested={'1' if payload.get('drain_requested', False) else '0'}",
        f"drain_cleared={'1' if payload.get('drain_cleared', False) else '0'}",
    ]
    blockers = payload.get("final_blockers", [])
    if isinstance(blockers, list) and blockers:
        summary.append("final_blockers=" + "|".join([_norm(x) for x in blockers if _norm(x)]))
    _write_text(latest_txt, "\n".join(summary) + "\n")

    _append_jsonl(event_log, {"event": "controller_finished", "utc": _utc_ts(), "run_id": run_id, "outcome": payload.get("outcome", "")})
    for attempt in payload.get("attempts", []):
        if not isinstance(attempt, dict):
            continue
        _append_jsonl(
            event_log,
            {
                "event": "poll_attempt",
                "utc": _utc_ts(),
                "run_id": run_id,
                "attempt": attempt.get("attempt", 0),
                "decision": attempt.get("decision", ""),
                "blocker_count": attempt.get("blocker_count", 0),
            },
        )
    return {
        "run_json": str(run_json),
        "latest_json": str(latest_json),
        "latest_txt": str(latest_txt),
        "event_log": str(event_log),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scheduler-facing controlled overnight restart controller.")
    parser.add_argument("--window-start-hour", type=int, default=DEFAULT_WINDOW_START_HOUR)
    parser.add_argument("--window-end-hour", type=int, default=DEFAULT_WINDOW_END_HOUR)
    parser.add_argument("--window-minute-span", type=int, default=DEFAULT_WINDOW_MINUTE_SPAN)
    parser.add_argument("--ignore-window", action="store_true")
    parser.add_argument("--max-wait-seconds", type=int, default=DEFAULT_MAX_WAIT_SECONDS)
    parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--request-drain", action="store_true")
    parser.add_argument("--clear-drain-on-skip", action="store_true")
    parser.add_argument("--escalation-mode", action="store_true")
    parser.add_argument("--execute-reboot", action="store_true")
    parser.add_argument("--allow-reboot-action", action="store_true")
    parser.add_argument("--force-reboot-on-skip", action="store_true")
    parser.add_argument("--caller-task-name", default=DEFAULT_CONTROLLER_TASK_NAME)
    parser.add_argument("--drainable-lock-idle-seconds", type=int, default=DEFAULT_DRAINABLE_LOCK_IDLE_SECONDS)
    parser.add_argument("--b-heartbeat-max-age-s", type=int, default=DEFAULT_B_HEARTBEAT_MAX_AGE_SECONDS)
    parser.add_argument("--h-heartbeat-max-age-s", type=int, default=DEFAULT_H_HEARTBEAT_MAX_AGE_SECONDS)
    return parser


def main() -> int:
    args = _parser().parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + f".pid{os.getpid()}"
    started_utc = _utc_ts()
    in_window, window_artifacts = _window_check(
        start_hour=args.window_start_hour,
        end_hour=args.window_end_hour,
        minute_span=args.window_minute_span,
    )
    caller_task_name = _norm(args.caller_task_name)
    task_match = caller_task_name.lower() == DEFAULT_CONTROLLER_TASK_NAME.lower()
    restart_window_active = bool(in_window and task_match)
    window_artifacts["caller_task_name"] = caller_task_name
    window_artifacts["expected_task_name"] = DEFAULT_CONTROLLER_TASK_NAME
    window_artifacts["task_match"] = task_match
    window_artifacts["restart_window_active"] = restart_window_active
    if args.ignore_window:
        window_artifacts["override_flag"] = "ignore_window=1"

    request_marker_exists_before = MAINT_REQUEST_PATH.exists()
    poll_wait_seconds = max(int(args.poll_seconds), 1)
    max_wait_seconds = max(int(args.max_wait_seconds), 0)
    deadline_monotonic = time.monotonic() + float(max_wait_seconds)
    attempts: list[dict[str, Any]] = []
    final_blockers: list[str] = []
    pre_heal_decision = ""
    pre_heal_blockers: list[str] = []
    final_decision = "skipped"
    reboot_attempted = False
    reboot_status = "not_attempted"
    drain_requested = False
    drain_cleared = False
    drain_clear_reason = "not_applicable"
    h_controlled_mode_cleared = False
    h_controlled_mode_clear_reason = "not_applicable"
    h_cycle_task_relaunch_ok = False
    h_cycle_task_relaunch_reason = "not_attempted"
    b_cycle_task_relaunch_ok = False
    b_cycle_task_relaunch_reason = "not_attempted"
    post_heal_gate_recheck_performed = False
    post_heal_gate_recheck_decision = ""
    post_heal_gate_recheck_blockers: list[str] = []
    post_heal_gate_eval_path = ""
    post_heal_gate_rc = -1
    post_heal_settle_attempts: list[dict[str, Any]] = []
    post_heal_transient_reconciled = False
    force_reboot_on_skip_requested = bool(args.force_reboot_on_skip)
    force_reboot_on_skip_used = False
    home_time_mode_active = _home_time_mode_active()
    outcome = "skipped_outside_window"
    escalation_mode = restart_window_active
    requested_escalation_override = _escalation_mode_enabled(args)
    active_actions_permitted = restart_window_active
    ownership_transfer_active = False
    ownership_transfer_status = "observer_only_mode"

    event_log_path = RESTART_DIR / "restart_controller.log.jsonl"
    _append_jsonl(event_log_path, {"event": "controller_started", "utc": started_utc, "run_id": run_id})
    _append_jsonl(
        event_log_path,
        {
            "event": "restart_role_state",
            "utc": _utc_ts(),
            "run_id": run_id,
            "restart_owner": "launcher_loop",
            "controller_role": "escalation_only" if escalation_mode else "observer_only",
            "escalation_mode": escalation_mode,
            "restart_window_active": restart_window_active,
            "requested_escalation_override": requested_escalation_override,
        },
    )
    if restart_window_active:
        _append_jsonl(
            event_log_path,
            {
                "event": "restart_window_active",
                "utc": _utc_ts(),
                "run_id": run_id,
                "window": window_artifacts,
            },
        )
    elif requested_escalation_override:
        _append_jsonl(
            event_log_path,
            {
                "event": "observer_only_mode",
                "utc": _utc_ts(),
                "run_id": run_id,
                "action": "requested_escalation_ignored_outside_restart_window",
            },
        )

    if restart_window_active:
        ownership_transfer_active, ownership_transfer_status = _write_ownership_transfer(
            active=True,
            reason="controlled_restart_escalation_window",
            run_id=run_id,
        )
        if not ownership_transfer_active:
            ownership_transfer_status = "ownership_transfer_write_failed_window_override"
        _append_jsonl(
            event_log_path,
            {
                "event": "ownership_transfer_to_controller",
                "utc": _utc_ts(),
                "run_id": run_id,
                "ownership_transfer_active": ownership_transfer_active,
                "ownership_transfer_status": ownership_transfer_status,
            },
        )
    else:
        active_actions_permitted = False
    if not active_actions_permitted:
        max_wait_seconds = 0
        deadline_monotonic = time.monotonic() + float(max_wait_seconds)

    _append_jsonl(
        event_log_path,
        {
            "event": "scheduler_time_control_enforced",
            "utc": _utc_ts(),
            "run_id": run_id,
            "window_gate_disabled": False,
            "restart_window_active": restart_window_active,
        },
    )
    drain_request_performed = bool(args.request_drain) and active_actions_permitted
    if bool(args.request_drain) and not active_actions_permitted:
        _append_jsonl(
            event_log_path,
            {
                "event": "observer_only_mode",
                "utc": _utc_ts(),
                "run_id": run_id,
                "action": "request_drain_ignored",
            },
        )
    if drain_request_performed:
        _append_jsonl(event_log_path, {"event": "drain_requested", "utc": _utc_ts(), "run_id": run_id})
    initial = _run_gate(
        request_drain=drain_request_performed,
        ignore_window=True,
        execute_reboot=False,
        allow_reboot_action=False,
        b_heartbeat_max_age_s=args.b_heartbeat_max_age_s,
        h_heartbeat_max_age_s=args.h_heartbeat_max_age_s,
    )
    eval_payload = _load_gate_eval(initial.get("gate_result", {}))
    blockers = eval_payload.get("blockers", []) if isinstance(eval_payload.get("blockers", []), list) else []
    decision = _norm(eval_payload.get("decision", "")) or _norm(initial.get("gate_result", {}).get("decision", ""))
    if "H_LAUNCHER_ACTIVE" in blockers and active_actions_permitted and (not restart_window_active):
        active_actions_permitted = False
        _append_jsonl(
            event_log_path,
            {
                "event": "ambiguous_ownership_hold",
                "utc": _utc_ts(),
                "run_id": run_id,
                "reason": "launcher_owner_active_during_escalation",
            },
        )
    elif "H_LAUNCHER_ACTIVE" in blockers and restart_window_active:
        _append_jsonl(
            event_log_path,
            {
                "event": "ownership_transfer_to_controller",
                "utc": _utc_ts(),
                "run_id": run_id,
                "reason": "restart_window_override_launcher_owner_observed",
            },
        )
    if not active_actions_permitted and escalation_mode:
        outcome = "ambiguous_ownership_hold"
    attempts.append(
        {
            "attempt": 1,
            "utc": _utc_ts(),
            "decision": decision or "unknown",
            "blocker_count": len(blockers),
            "blockers": blockers,
            "gate_rc": initial.get("rc", -1),
            "gate_eval_path": _norm(initial.get("gate_result", {}).get("evidence_paths", {}).get("eval_path", "")),
            "request_drain": drain_request_performed,
        }
    )
    drain_requested = drain_request_performed
    approved = decision == "approved"

    while not approved and time.monotonic() < deadline_monotonic:
        time.sleep(float(poll_wait_seconds))
        poll = _run_gate(
            request_drain=False,
            ignore_window=True,
            execute_reboot=False,
            allow_reboot_action=False,
            b_heartbeat_max_age_s=args.b_heartbeat_max_age_s,
            h_heartbeat_max_age_s=args.h_heartbeat_max_age_s,
        )
        eval_payload = _load_gate_eval(poll.get("gate_result", {}))
        blockers = eval_payload.get("blockers", []) if isinstance(eval_payload.get("blockers", []), list) else []
        decision = _norm(eval_payload.get("decision", "")) or _norm(poll.get("gate_result", {}).get("decision", ""))
        attempts.append(
            {
                "attempt": len(attempts) + 1,
                "utc": _utc_ts(),
                "decision": decision or "unknown",
                "blocker_count": len(blockers),
                "blockers": blockers,
                "gate_rc": poll.get("rc", -1),
                "gate_eval_path": _norm(poll.get("gate_result", {}).get("evidence_paths", {}).get("eval_path", "")),
                "request_drain": False,
            }
        )
        approved = decision == "approved"

    if approved:
        _append_jsonl(event_log_path, {"event": "restart_approval_reached", "utc": _utc_ts(), "run_id": run_id, "attempts": len(attempts)})
    else:
        _append_jsonl(event_log_path, {"event": "restart_timeout_or_blocked", "utc": _utc_ts(), "run_id": run_id, "attempts": len(attempts)})

    last = attempts[-1] if attempts else {}
    final_decision = _norm(last.get("decision", "")) or "skipped"
    last_blockers = last.get("blockers", [])
    final_blockers = last_blockers if isinstance(last_blockers, list) else []
    pre_heal_decision = final_decision
    pre_heal_blockers = list(final_blockers)

    if restart_window_active and ("H_CYCLE_ACTIVE_LOCK" in final_blockers):
        lock_idle_seconds = max(int(args.drainable_lock_idle_seconds), 1)
        has_recent_h_activity, h_lock_info = _lock_has_recent_activity(
            H_LIVE / "H_pricing_cycle.lock",
            args.h_heartbeat_max_age_s,
            lock_idle_seconds,
        )
        explicit_shutdown_requested = True
        if explicit_shutdown_requested or (not has_recent_h_activity):
            final_blockers = [b for b in final_blockers if b != "H_CYCLE_ACTIVE_LOCK"]
            if (final_decision != "approved") and (not final_blockers):
                final_decision = "approved"
            _append_jsonl(
                event_log_path,
                {
                    "event": "restart_override_conditions_applied",
                    "utc": _utc_ts(),
                    "run_id": run_id,
                    "reason": "override_active_lock_due_to_restart_window",
                    "lock_idle_seconds": lock_idle_seconds,
                    "has_recent_h_activity": has_recent_h_activity,
                    "explicit_shutdown_requested": explicit_shutdown_requested,
                    "h_lock": h_lock_info,
                },
            )

    if final_decision == "approved":
        if active_actions_permitted and args.execute_reboot and args.allow_reboot_action:
            execute = _run_gate(
                request_drain=False,
                ignore_window=True,
                execute_reboot=True,
                allow_reboot_action=True,
                b_heartbeat_max_age_s=args.b_heartbeat_max_age_s,
                h_heartbeat_max_age_s=args.h_heartbeat_max_age_s,
            )
            execute_eval = _load_gate_eval(execute.get("gate_result", {}))
            final_decision = _norm(execute_eval.get("decision", "")) or _norm(execute.get("gate_result", {}).get("decision", ""))
            final_blockers = (
                execute_eval.get("blockers", [])
                if isinstance(execute_eval.get("blockers", []), list)
                else final_blockers
            )
            reboot_attempted = bool(execute.get("gate_result", {}).get("reboot_attempted", False))
            reboot_status = _norm(execute.get("gate_result", {}).get("reboot_status", ""))
            attempts.append(
                {
                    "attempt": len(attempts) + 1,
                    "utc": _utc_ts(),
                    "decision": final_decision or "unknown",
                    "blocker_count": len(final_blockers),
                    "blockers": final_blockers,
                    "gate_rc": execute.get("rc", -1),
                    "gate_eval_path": _norm(execute.get("gate_result", {}).get("evidence_paths", {}).get("eval_path", "")),
                    "request_drain": False,
                    "execute_reboot": True,
                    "allow_reboot_action": True,
                    "reboot_attempted": reboot_attempted,
                    "reboot_status": reboot_status,
                }
            )
            if reboot_attempted:
                outcome = "reboot_command_submitted"
            else:
                reboot_attempted, reboot_status = _submit_windows_reboot(
                    "SellerOne controlled restart approved window reboot"
                )
                if reboot_attempted:
                    outcome = "reboot_command_submitted"
                else:
                    outcome = "approved_but_reboot_not_submitted"
            _append_jsonl(
                event_log_path,
                {
                    "event": "reboot_action_result",
                    "utc": _utc_ts(),
                    "run_id": run_id,
                    "reboot_attempted": reboot_attempted,
                    "reboot_status": reboot_status,
                },
            )
            _append_jsonl(
                event_log_path,
                {
                    "event": "reboot_command_executed",
                    "utc": _utc_ts(),
                    "run_id": run_id,
                    "reboot_attempted": reboot_attempted,
                    "reboot_status": reboot_status,
                },
            )
        else:
            reboot_status = "approved_execute_flags_missing" if active_actions_permitted else "observer_only_mode_no_reboot_action"
            outcome = "approved_no_reboot_flags" if active_actions_permitted else "observer_only_mode_no_active_action"
            _append_jsonl(
                event_log_path,
                {
                    "event": "reboot_action_skipped",
                    "utc": _utc_ts(),
                    "run_id": run_id,
                    "reason": reboot_status,
                },
            )
    else:
        if max_wait_seconds == 0:
            outcome = "skipped_not_approved"
        elif time.monotonic() >= deadline_monotonic:
            outcome = "skipped_timeout_not_approved"
        else:
            outcome = "skipped_not_approved"

    # Always clear controller-owned restart drain markers after an approved terminal decision.
    # This covers both non-reboot runs and successful reboot submissions, preventing post-reboot
    # maintenance marker latch that would keep B/H in boundary-exit loops.
    should_clear_drain = active_actions_permitted and ((final_decision == "approved") or args.clear_drain_on_skip)
    if should_clear_drain:
        # Clear controller-owned drain markers after approved terminal restart decisions.
        # This prevents stale maintenance.requested from forcing perpetual boundary drain exits.
        drain_cleared, drain_clear_reason = _safe_remove_drain_marker()
        if request_marker_exists_before and not drain_cleared:
            drain_clear_reason = f"preexisting_marker_{drain_clear_reason}"
        h_controlled_mode_cleared, h_controlled_mode_clear_reason = _safe_clear_h_controlled_mode_flag()

    # If reboot was not attempted, ensure H launcher can return to normal mode and relaunch.
    if active_actions_permitted and not reboot_attempted:
        if not h_controlled_mode_cleared:
            h_controlled_mode_cleared, h_controlled_mode_clear_reason = _safe_clear_h_controlled_mode_flag()
        h_cycle_task_relaunch_ok, h_cycle_task_relaunch_reason = _heal_and_start_task(
            DEFAULT_H_TASK_NAME,
            ["run_H_cycle.bat", "scripts\\cycles\\run_H_pricing_cycle.py", "scripts\\cycles\\run_H_pricing_cycle_guarded.py"],
            flow_lock_path=H_LIVE / "H_pricing_cycle.lock",
            heartbeat_max_age_s=args.h_heartbeat_max_age_s,
        )
        b_cycle_task_relaunch_ok, b_cycle_task_relaunch_reason = _heal_and_start_task(
            DEFAULT_B_TASK_NAME,
            ["run_B_cycle.bat", "scripts\\cycles\\run_B_cycle.py"],
            flow_lock_path=B_LIVE / "B_cycle.lock",
            heartbeat_max_age_s=args.b_heartbeat_max_age_s,
        )
        _append_jsonl(
            event_log_path,
            {
                "event": "post_heal_gate_recheck_started",
                "utc": _utc_ts(),
                "run_id": run_id,
                "pre_heal_decision": pre_heal_decision,
                "pre_heal_blockers": pre_heal_blockers,
                "h_cycle_task_relaunch_ok": h_cycle_task_relaunch_ok,
                "h_cycle_task_relaunch_reason": h_cycle_task_relaunch_reason,
                "b_cycle_task_relaunch_ok": b_cycle_task_relaunch_ok,
                "b_cycle_task_relaunch_reason": b_cycle_task_relaunch_reason,
            },
        )
        time.sleep(float(DEFAULT_POST_HEAL_RECHECK_DELAY_SECONDS))
        post_heal_gate_recheck_performed = True
        post_heal_eval = _run_gate(
            request_drain=False,
            ignore_window=True,
            execute_reboot=False,
            allow_reboot_action=False,
            b_heartbeat_max_age_s=args.b_heartbeat_max_age_s,
            h_heartbeat_max_age_s=args.h_heartbeat_max_age_s,
        )
        post_heal_gate_rc = int(post_heal_eval.get("rc", -1))
        post_heal_gate_payload = _load_gate_eval(post_heal_eval.get("gate_result", {}))
        post_heal_gate_recheck_decision = (
            _norm(post_heal_gate_payload.get("decision", ""))
            or _norm(post_heal_eval.get("gate_result", {}).get("decision", ""))
            or "unknown"
        )
        post_heal_gate_eval_path = _norm(
            post_heal_eval.get("gate_result", {}).get("evidence_paths", {}).get("eval_path", "")
        )
        post_heal_blockers_raw = post_heal_gate_payload.get("blockers", [])
        post_heal_gate_recheck_blockers = (
            post_heal_blockers_raw if isinstance(post_heal_blockers_raw, list) else []
        )
        final_decision = post_heal_gate_recheck_decision
        final_blockers = list(post_heal_gate_recheck_blockers)
        transient_only = bool(final_blockers) and set(final_blockers).issubset(TRANSIENT_POST_HEAL_BLOCKERS)
        if final_decision != "approved" and transient_only:
            _append_jsonl(
                event_log_path,
                {
                    "event": "post_heal_transient_settle_started",
                    "utc": _utc_ts(),
                    "run_id": run_id,
                    "blockers": final_blockers,
                    "settle_seconds": DEFAULT_POST_HEAL_SETTLE_SECONDS,
                    "poll_seconds": DEFAULT_POST_HEAL_SETTLE_POLL_SECONDS,
                },
            )
            settle_deadline = time.monotonic() + float(DEFAULT_POST_HEAL_SETTLE_SECONDS)
            while time.monotonic() < settle_deadline and final_decision != "approved":
                progress_ok, progress_diag = _post_heal_runtime_progressing(
                    h_heartbeat_max_age_s=args.h_heartbeat_max_age_s,
                    b_heartbeat_max_age_s=args.b_heartbeat_max_age_s,
                )
                settle_record = {
                    "utc": _utc_ts(),
                    "final_decision_before": final_decision,
                    "final_blockers_before": list(final_blockers),
                    "progress_ok": progress_ok,
                    "progress_diag": progress_diag,
                }
                if progress_ok and set(final_blockers).issubset(TRANSIENT_POST_HEAL_BLOCKERS):
                    final_decision = "approved"
                    final_blockers = []
                    post_heal_gate_recheck_decision = "approved"
                    post_heal_gate_recheck_blockers = []
                    post_heal_transient_reconciled = True
                    settle_record["action"] = "approved_transient_reconciled"
                    post_heal_settle_attempts.append(settle_record)
                    break
                time.sleep(float(DEFAULT_POST_HEAL_SETTLE_POLL_SECONDS))
                settle_eval = _run_gate(
                    request_drain=False,
                    ignore_window=True,
                    execute_reboot=False,
                    allow_reboot_action=False,
                    b_heartbeat_max_age_s=args.b_heartbeat_max_age_s,
                    h_heartbeat_max_age_s=args.h_heartbeat_max_age_s,
                )
                post_heal_gate_rc = int(settle_eval.get("rc", -1))
                settle_payload = _load_gate_eval(settle_eval.get("gate_result", {}))
                settle_decision = (
                    _norm(settle_payload.get("decision", ""))
                    or _norm(settle_eval.get("gate_result", {}).get("decision", ""))
                    or "unknown"
                )
                settle_blockers_raw = settle_payload.get("blockers", [])
                settle_blockers = settle_blockers_raw if isinstance(settle_blockers_raw, list) else []
                post_heal_gate_eval_path = _norm(
                    settle_eval.get("gate_result", {}).get("evidence_paths", {}).get("eval_path", "")
                )
                final_decision = settle_decision
                final_blockers = list(settle_blockers)
                post_heal_gate_recheck_decision = settle_decision
                post_heal_gate_recheck_blockers = list(settle_blockers)
                settle_record["action"] = "gate_recheck"
                settle_record["gate_decision_after"] = settle_decision
                settle_record["gate_blockers_after"] = settle_blockers
                settle_record["gate_eval_path"] = post_heal_gate_eval_path
                settle_record["gate_rc"] = post_heal_gate_rc
                post_heal_settle_attempts.append(settle_record)
                if final_decision == "approved":
                    break
        if final_decision == "approved":
            outcome = "approved_post_heal_transient_reconciled" if post_heal_transient_reconciled else "approved_post_heal_recheck"
        else:
            outcome = "skipped_post_heal_blocked"
        _append_jsonl(
            event_log_path,
            {
                "event": "post_heal_gate_recheck_result",
                "utc": _utc_ts(),
                "run_id": run_id,
                "post_heal_decision": post_heal_gate_recheck_decision,
                "post_heal_blockers": post_heal_gate_recheck_blockers,
                "post_heal_gate_rc": post_heal_gate_rc,
                "post_heal_gate_eval_path": post_heal_gate_eval_path,
                "final_decision": final_decision,
                "final_blockers": final_blockers,
                "post_heal_transient_reconciled": post_heal_transient_reconciled,
                "post_heal_settle_attempts": post_heal_settle_attempts,
                "outcome": outcome,
            },
        )

    # If approval is reached only after post-heal reconciliation, we still must
    # execute the reboot action when enabled. Without this, scheduled runs can
    # report approved while never issuing the OS restart.
    if active_actions_permitted and (not reboot_attempted) and final_decision == "approved":
        if args.execute_reboot and args.allow_reboot_action:
            execute = _run_gate(
                request_drain=False,
                ignore_window=True,
                execute_reboot=True,
                allow_reboot_action=True,
                b_heartbeat_max_age_s=args.b_heartbeat_max_age_s,
                h_heartbeat_max_age_s=args.h_heartbeat_max_age_s,
            )
            execute_eval = _load_gate_eval(execute.get("gate_result", {}))
            execute_decision = _norm(execute_eval.get("decision", "")) or _norm(execute.get("gate_result", {}).get("decision", ""))
            execute_blockers = (
                execute_eval.get("blockers", [])
                if isinstance(execute_eval.get("blockers", []), list)
                else final_blockers
            )
            reboot_attempted = bool(execute.get("gate_result", {}).get("reboot_attempted", False))
            reboot_status = _norm(execute.get("gate_result", {}).get("reboot_status", ""))
            final_decision = execute_decision or final_decision
            final_blockers = execute_blockers
            attempts.append(
                {
                    "attempt": len(attempts) + 1,
                    "utc": _utc_ts(),
                    "decision": final_decision or "unknown",
                    "blocker_count": len(final_blockers),
                    "blockers": final_blockers,
                    "gate_rc": execute.get("rc", -1),
                    "gate_eval_path": _norm(execute.get("gate_result", {}).get("evidence_paths", {}).get("eval_path", "")),
                    "request_drain": False,
                    "execute_reboot": True,
                    "allow_reboot_action": True,
                    "reboot_attempted": reboot_attempted,
                    "reboot_status": reboot_status,
                    "path": "post_heal_approved_execute",
                }
            )
            if reboot_attempted:
                outcome = "reboot_command_submitted"
            else:
                reboot_attempted, reboot_status = _submit_windows_reboot(
                    "SellerOne controlled restart approved window reboot post-heal"
                )
                if reboot_attempted:
                    outcome = "reboot_command_submitted"
                else:
                    outcome = "approved_but_reboot_not_submitted"
            _append_jsonl(
                event_log_path,
                {
                    "event": "reboot_action_result",
                    "utc": _utc_ts(),
                    "run_id": run_id,
                    "reboot_attempted": reboot_attempted,
                    "reboot_status": reboot_status,
                    "path": "post_heal_approved_execute",
                },
            )
            _append_jsonl(
                event_log_path,
                {
                    "event": "reboot_command_executed",
                    "utc": _utc_ts(),
                    "run_id": run_id,
                    "reboot_attempted": reboot_attempted,
                    "reboot_status": reboot_status,
                    "path": "post_heal_approved_execute",
                },
            )
        else:
            reboot_status = "approved_execute_flags_missing"

    # Home-time fallback: if restart gate remains blocked through the full cycle,
    # and operator explicitly enabled forced reboot fallback, submit OS reboot.
    if (
        active_actions_permitted
        and
        (not reboot_attempted)
        and force_reboot_on_skip_requested
        and home_time_mode_active
        and args.execute_reboot
        and args.allow_reboot_action
        and final_decision != "approved"
    ):
        force_reboot_on_skip_used = True
        reboot_attempted, reboot_status = _submit_windows_reboot(
            "SellerOne controlled restart fallback - home time mode forced reboot on skip"
        )
        if reboot_attempted:
            outcome = "reboot_command_submitted_forced_home_mode"
        else:
            outcome = "forced_home_mode_reboot_submit_failed"
        _append_jsonl(
            event_log_path,
            {
                "event": "reboot_action_result",
                "utc": _utc_ts(),
                "run_id": run_id,
                "reboot_attempted": reboot_attempted,
                "reboot_status": reboot_status,
                "path": "forced_home_mode_on_skip",
            },
        )

    finished_utc = _utc_ts()
    payload = {
        "run_id": run_id,
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "controller": "controlled_restart_controller",
        "window": window_artifacts,
        "caller_task_name": caller_task_name,
        "restart_window_active": restart_window_active,
        "max_wait_seconds": max_wait_seconds,
        "poll_seconds": poll_wait_seconds,
        "drain_requested": drain_requested,
        "request_marker_existed_before": request_marker_exists_before,
        "drain_cleared": drain_cleared,
        "drain_clear_reason": drain_clear_reason,
        "h_controlled_mode_cleared": h_controlled_mode_cleared,
        "h_controlled_mode_clear_reason": h_controlled_mode_clear_reason,
        "h_cycle_task_relaunch_ok": h_cycle_task_relaunch_ok,
        "h_cycle_task_relaunch_reason": h_cycle_task_relaunch_reason,
        "h_cycle_task_name": DEFAULT_H_TASK_NAME,
        "b_cycle_task_relaunch_ok": b_cycle_task_relaunch_ok,
        "b_cycle_task_relaunch_reason": b_cycle_task_relaunch_reason,
        "b_cycle_task_name": DEFAULT_B_TASK_NAME,
        "poll_attempts": len(attempts),
        "attempts": attempts,
        "pre_heal_decision": pre_heal_decision,
        "pre_heal_blockers": pre_heal_blockers,
        "decision": final_decision,
        "final_blockers": final_blockers,
        "post_heal_gate_recheck_performed": post_heal_gate_recheck_performed,
        "post_heal_gate_recheck_decision": post_heal_gate_recheck_decision,
        "post_heal_gate_recheck_blockers": post_heal_gate_recheck_blockers,
        "post_heal_gate_eval_path": post_heal_gate_eval_path,
        "post_heal_gate_rc": post_heal_gate_rc,
        "post_heal_transient_reconciled": post_heal_transient_reconciled,
        "post_heal_settle_attempts": post_heal_settle_attempts,
        "home_time_mode_active": home_time_mode_active,
        "force_reboot_on_skip_requested": force_reboot_on_skip_requested,
        "force_reboot_on_skip_used": force_reboot_on_skip_used,
        "reboot_requested_flags": {
            "execute_reboot": bool(args.execute_reboot),
            "allow_reboot_action": bool(args.allow_reboot_action),
            "force_reboot_on_skip": force_reboot_on_skip_requested,
        },
        "reboot_attempted": reboot_attempted,
        "reboot_status": reboot_status,
        "escalation_mode": escalation_mode,
        "requested_escalation_override": requested_escalation_override,
        "active_actions_permitted": active_actions_permitted,
        "ownership_transfer_active": ownership_transfer_active,
        "ownership_transfer_status": ownership_transfer_status,
        "outcome": outcome,
    }
    if escalation_mode:
        released, release_status = _write_ownership_transfer(
            active=False,
            reason="controlled_restart_window_complete",
            run_id=run_id,
        )
        payload["ownership_transfer_released"] = released
        payload["ownership_transfer_release_status"] = release_status
        _append_jsonl(
            event_log_path,
            {
                "event": "returning_to_observer_mode",
                "utc": _utc_ts(),
                "run_id": run_id,
                "ownership_transfer_released": released,
                "ownership_transfer_release_status": release_status,
            },
        )
    paths = _write_controller_evidence(payload=payload, run_id=run_id)
    result = {
        "status": "ok",
        "run_id": run_id,
        "decision": final_decision,
        "outcome": outcome,
        "final_blockers": final_blockers,
        "poll_attempts": len(attempts),
        "pre_heal_decision": pre_heal_decision,
        "pre_heal_blockers": pre_heal_blockers,
        "drain_requested": drain_requested,
        "drain_cleared": drain_cleared,
        "h_controlled_mode_cleared": h_controlled_mode_cleared,
        "h_cycle_task_relaunch_ok": h_cycle_task_relaunch_ok,
        "h_cycle_task_relaunch_reason": h_cycle_task_relaunch_reason,
        "b_cycle_task_relaunch_ok": b_cycle_task_relaunch_ok,
        "b_cycle_task_relaunch_reason": b_cycle_task_relaunch_reason,
        "post_heal_gate_recheck_performed": post_heal_gate_recheck_performed,
        "post_heal_gate_recheck_decision": post_heal_gate_recheck_decision,
        "post_heal_gate_recheck_blockers": post_heal_gate_recheck_blockers,
        "post_heal_gate_eval_path": post_heal_gate_eval_path,
        "post_heal_gate_rc": post_heal_gate_rc,
        "post_heal_transient_reconciled": post_heal_transient_reconciled,
        "post_heal_settle_attempts": post_heal_settle_attempts,
        "home_time_mode_active": home_time_mode_active,
        "force_reboot_on_skip_requested": force_reboot_on_skip_requested,
        "force_reboot_on_skip_used": force_reboot_on_skip_used,
        "reboot_attempted": reboot_attempted,
        "reboot_status": reboot_status,
        "escalation_mode": escalation_mode,
        "requested_escalation_override": requested_escalation_override,
        "caller_task_name": caller_task_name,
        "restart_window_active": restart_window_active,
        "active_actions_permitted": active_actions_permitted,
        "ownership_transfer_active": ownership_transfer_active,
        "ownership_transfer_status": ownership_transfer_status,
        "evidence_paths": paths,
    }
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
