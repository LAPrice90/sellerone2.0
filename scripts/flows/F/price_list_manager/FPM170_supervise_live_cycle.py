from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text
from scripts.flows.F.price_list_manager._paths import get_manager_paths


MANAGER_SCRIPT = "scripts\\flows\\F\\price_list_manager\\FPM130_run_live_cycle.py"
CHILD_SCRIPT = "scripts\\flows\\F\\F061_run_legacy_first_checks_local.py"
SUPERVISOR_STATE_NAME = "fpm_live_supervisor_state.txt"
SUPERVISOR_LOG_NAME = "fpm_live_supervisor.log"
LIVE_EVENTS_NAME = "live_cycle_events.csv"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: str) -> datetime | None:
    raw = normalize_text(value)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _age_seconds(value: str, *, now: datetime | None = None) -> float | None:
    dt = _parse_utc(value)
    if dt is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max((current - dt).total_seconds(), 0.0)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="ascii", newline="\n")
    os.replace(tmp, path)


def _append_log(live_dir: Path, message: str) -> None:
    path = live_dir / SUPERVISOR_LOG_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="ascii", newline="\n") as fh:
        fh.write(f"{_utc_now_iso()} {message}\n")


def _parse_state_line(line: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in [part.strip() for part in normalize_text(line).split("|") if part.strip()]:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parsed[normalize_text(key).lower().lstrip("\ufeff")] = normalize_text(value)
    return parsed


def _read_state_file(path: Path) -> dict[str, str]:
    try:
        if not path.exists():
            return {}
        return _parse_state_line(path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except Exception:
        return {}


def _manager_mode_state(live_dir: Path) -> dict[str, str]:
    return _read_state_file(live_dir / "f061_manager_mode_state.txt")


def _child_status_state(live_dir: Path) -> dict[str, str]:
    return _read_state_file(live_dir / "f061_child_status.txt")


def _int_field(parts: dict[str, str], key: str) -> int:
    try:
        return int(parts.get(key, "0"))
    except ValueError:
        return 0


def _pid_alive(root: Path, pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return False
    return bool(normalize_text(completed.stdout))


def _append_live_pid_fallbacks(root: Path, live_dir: Path, manager_pids: list[int], child_pids: list[int]) -> tuple[list[int], list[int]]:
    lock_state = _read_state_file(live_dir / "live_cycle.lock")
    child_state = _child_status_state(live_dir)
    lock_pid = _int_field(lock_state, "pid")
    child_pid = _int_field(child_state, "pid")
    out_manager = list(manager_pids)
    out_child = list(child_pids)
    if lock_pid and lock_pid not in out_manager and _pid_alive(root, lock_pid):
        out_manager.append(lock_pid)
    if child_pid and child_pid not in out_child and _pid_alive(root, child_pid):
        out_child.append(child_pid)
    return sorted(set(out_manager)), sorted(set(out_child))


def _pause_request_reason(root: Path, live_dir: Path) -> str:
    f_only_request = live_dir / "f061_visible_login.requested"
    global_request = root / "out" / "locks" / "maintenance.requested"
    drain_ready = live_dir / "F_restart_drain.ready"
    reasons: list[str] = []
    if f_only_request.exists():
        reasons.append("f_only_request")
    if global_request.exists():
        reasons.append("global_maintenance_request")
    if drain_ready.exists() and reasons:
        reasons.append("drain_ready")
    return ",".join(reasons)


def _file_age_seconds(path: Path, *, now: datetime | None = None) -> float | None:
    try:
        if not path.exists():
            return None
        current = now or datetime.now(timezone.utc)
        return max(current.timestamp() - path.stat().st_mtime, 0.0)
    except OSError:
        return None


def _latest_scanner_progress(live_dir: Path, *, now: datetime | None = None) -> tuple[float | None, str]:
    path = live_dir / LIVE_EVENTS_NAME
    if not path.exists():
        return None, ""
    current = now or datetime.now(timezone.utc)
    latest: datetime | None = None
    latest_raw = ""
    try:
        with path.open(newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                if normalize_text(row.get("event_type", "")).lower() != "scanner_chunk":
                    continue
                status = normalize_text(row.get("status", "")).lower()
                if status and status != "success":
                    continue
                raw = normalize_text(row.get("event_utc", "") or row.get("observed_utc", ""))
                parsed = _parse_utc(raw)
                if parsed is None:
                    continue
                if latest is None or parsed > latest:
                    latest = parsed
                    latest_raw = raw
    except (OSError, csv.Error):
        return None, ""
    if latest is None:
        return None, ""
    return max((current - latest).total_seconds(), 0.0), latest_raw


def _powershell_process_ids(pattern: str, *, root: Path) -> list[int]:
    if os.name != "nt":
        return []
    command = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.Name -like 'python*' -and $_.CommandLine -like '*{pattern}*' }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    pids: list[int] = []
    for line in completed.stdout.splitlines():
        try:
            pids.append(int(line.strip()))
        except ValueError:
            continue
    return pids


ProcessFinder = Callable[[str], list[int]]


def _manager_pids(root: Path) -> list[int]:
    return _powershell_process_ids("FPM130_run_live_cycle.py", root=root)


def _child_pids(root: Path) -> list[int]:
    return _powershell_process_ids("F061_run_legacy_first_checks_local.py", root=root)


def _supervisor_decision(
    *,
    manager_pids: list[int],
    manager_state: dict[str, str],
    child_state: dict[str, str],
    child_stdout_age_seconds: float | None,
    scanner_progress_age_seconds: float | None = None,
    stale_seconds: float,
    now: datetime | None = None,
) -> tuple[str, str]:
    if not manager_pids:
        return "restart_manager", "manager_process_missing"

    state_age = _age_seconds(manager_state.get("updated_utc", ""), now=now)
    heartbeat_age = _age_seconds(child_state.get("heartbeat", ""), now=now)
    output_age = _age_seconds(child_state.get("last_output_utc", ""), now=now)
    if output_age is None:
        output_age = child_stdout_age_seconds
    freshest = min(
        [age for age in [state_age, heartbeat_age, output_age, child_stdout_age_seconds] if age is not None],
        default=None,
    )
    if freshest is None:
        return "restart_manager", "no_live_heartbeat_files"
    if freshest > stale_seconds:
        return "restart_manager", f"stale_live_state_seconds={freshest:.1f}"
    if scanner_progress_age_seconds is None:
        return "alive_no_progress", f"process_alive_seconds={freshest:.1f};scanner_progress=missing"
    if scanner_progress_age_seconds > stale_seconds:
        return (
            "alive_no_progress",
            f"process_alive_seconds={freshest:.1f};scanner_progress_seconds={scanner_progress_age_seconds:.1f}",
        )
    return "ok", f"process_alive_seconds={freshest:.1f};scanner_progress_seconds={scanner_progress_age_seconds:.1f}"


def _scanner_progress_state(decision: str, scanner_progress_age_seconds: float | None) -> str:
    if decision == "restart_manager":
        return "process_missing_or_stale"
    if scanner_progress_age_seconds is None:
        return "progress_missing"
    if decision == "alive_no_progress":
        return "no_row_progress"
    return "scanner_progressing"


def _terminate_pids(root: Path, pids: list[int]) -> None:
    if os.name != "nt":
        return
    for pid in sorted(set(int(pid) for pid in pids if int(pid) > 0)):
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                cwd=str(root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
        except Exception:
            continue


def _launch_manager(
    root: Path,
    *,
    chunk_rows: int,
    sleep_seconds: int,
    apply_next: bool,
    auto_approve_next: bool,
    refresh_before_select: bool,
) -> int:
    cmd = [
        sys.executable,
        "-u",
        str(root / MANAGER_SCRIPT),
        "--chunk-rows",
        str(int(chunk_rows)),
        "--sleep-seconds",
        str(int(sleep_seconds)),
    ]
    if apply_next:
        cmd.append("--apply-next")
    if auto_approve_next:
        cmd.append("--auto-approve-next")
    if not refresh_before_select:
        cmd.append("--skip-refresh-before-select")
    proc = subprocess.Popen(
        cmd,
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return int(proc.pid)


def supervise_once(
    root: Path | None = None,
    *,
    chunk_rows: int = 25,
    sleep_seconds: int = 10,
    apply_next: bool = True,
    auto_approve_next: bool = True,
    refresh_before_select: bool = True,
    stale_seconds: float = 900.0,
    process_finder: ProcessFinder | None = None,
    child_finder: ProcessFinder | None = None,
    launch_manager: Callable[..., int] | None = None,
    terminate_pids: Callable[[Path, list[int]], None] | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    root_path = paths.root
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)

    find_manager = process_finder or (lambda _pattern: _manager_pids(root_path))
    find_child = child_finder or (lambda _pattern: _child_pids(root_path))
    manager_pids = find_manager("FPM130_run_live_cycle.py")
    child_pids = find_child("F061_run_legacy_first_checks_local.py")
    manager_pids, child_pids = _append_live_pid_fallbacks(root_path, live_dir, manager_pids, child_pids)
    manager_state = _manager_mode_state(live_dir)
    lock_state = _read_state_file(live_dir / "live_cycle.lock")
    lock_heartbeat = normalize_text(lock_state.get("heartbeat", ""))
    lock_age = _age_seconds(lock_heartbeat, now=now) if lock_heartbeat else None
    state_age = _age_seconds(manager_state.get("updated_utc", ""), now=now)
    if lock_age is not None and (state_age is None or lock_age < state_age):
        manager_state = {**manager_state, "updated_utc": lock_heartbeat}
    child_state = _child_status_state(live_dir)
    stdout_age = _file_age_seconds(live_dir / "f061_child_stdout.log", now=now)
    scanner_progress_age, scanner_progress_utc = _latest_scanner_progress(live_dir, now=now)
    pause_reason = _pause_request_reason(root_path, live_dir)
    if pause_reason and not manager_pids:
        decision, reason = "paused", pause_reason
    else:
        decision, reason = _supervisor_decision(
            manager_pids=manager_pids,
            manager_state=manager_state,
            child_state=child_state,
            child_stdout_age_seconds=stdout_age,
            scanner_progress_age_seconds=scanner_progress_age,
            stale_seconds=stale_seconds,
            now=now,
        )

    launched_pid = 0
    if decision == "restart_manager":
        killer = terminate_pids or _terminate_pids
        killer(root_path, manager_pids + child_pids)
        launcher = launch_manager or _launch_manager
        launched_pid = launcher(
            root_path,
            chunk_rows=chunk_rows,
            sleep_seconds=sleep_seconds,
            apply_next=apply_next,
            auto_approve_next=auto_approve_next,
            refresh_before_select=refresh_before_select,
        )
        _append_log(live_dir, f"action=restart_manager reason={reason} launched_pid={launched_pid}")

    observed = _utc_now_iso()
    progress_state = _scanner_progress_state(decision, scanner_progress_age)
    progress_age_text = "" if scanner_progress_age is None else f"{scanner_progress_age:.1f}"
    state_line = (
        f"state={decision}|reason={reason}|manager_pids={','.join(str(pid) for pid in manager_pids)}|"
        f"child_pids={','.join(str(pid) for pid in child_pids)}|launched_pid={launched_pid}|"
        f"progress_state={progress_state}|scanner_progress_age_seconds={progress_age_text}|"
        f"scanner_progress_utc={scanner_progress_utc}|"
        f"stale_seconds={float(stale_seconds):.1f}|updated_utc={observed}\n"
    )
    _write_text(live_dir / SUPERVISOR_STATE_NAME, state_line)
    return {
        "status": decision,
        "reason": reason,
        "manager_pids": manager_pids,
        "child_pids": child_pids,
        "launched_pid": launched_pid,
        "progress_state": progress_state,
        "scanner_progress_age_seconds": scanner_progress_age,
        "state_path": str(live_dir / SUPERVISOR_STATE_NAME),
    }


def supervise_loop(
    root: Path | None = None,
    *,
    chunk_rows: int = 25,
    sleep_seconds: int = 10,
    apply_next: bool = True,
    auto_approve_next: bool = True,
    refresh_before_select: bool = True,
    stale_seconds: float = 900.0,
    check_seconds: float = 30.0,
) -> None:
    while True:
        supervise_once(
            root=root,
            chunk_rows=chunk_rows,
            sleep_seconds=sleep_seconds,
            apply_next=apply_next,
            auto_approve_next=auto_approve_next,
            refresh_before_select=refresh_before_select,
            stale_seconds=stale_seconds,
        )
        time.sleep(max(float(check_seconds), 1.0))


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent supervisor for the F price-list live cycle.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--chunk-rows", type=int, default=int(os.environ.get("FPM_LIVE_CHUNK_ROWS", "25")))
    parser.add_argument("--sleep-seconds", type=int, default=int(os.environ.get("FPM_LIVE_SLEEP_SECONDS", "10")))
    parser.add_argument("--stale-seconds", type=float, default=float(os.environ.get("FPM_SUPERVISOR_STALE_SECONDS", "900")))
    parser.add_argument("--check-seconds", type=float, default=float(os.environ.get("FPM_SUPERVISOR_CHECK_SECONDS", "30")))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-apply-next", action="store_true")
    parser.add_argument("--no-auto-approve-next", action="store_true")
    parser.add_argument("--skip-refresh-before-select", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    kwargs = {
        "chunk_rows": args.chunk_rows,
        "sleep_seconds": args.sleep_seconds,
        "apply_next": not args.no_apply_next,
        "auto_approve_next": not args.no_auto_approve_next,
        "refresh_before_select": not args.skip_refresh_before_select,
        "stale_seconds": args.stale_seconds,
    }
    if args.once:
        print(supervise_once(root=root, **kwargs))
        return
    supervise_loop(root=root, check_seconds=args.check_seconds, **kwargs)


if __name__ == "__main__":
    main()
