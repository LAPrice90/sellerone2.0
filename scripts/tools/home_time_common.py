from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
H_LIVE_DIR = ROOT / "out" / "systems" / "H" / "live"
LOCKS_DIR = ROOT / "out" / "locks"
ACTIVE_PATH = H_LIVE_DIR / "H_home_time_mode.active.json"
LOG_PATH = H_LIVE_DIR / "H_home_time_mode.log"
H_LAUNCHER_LOCK_PATH = H_LIVE_DIR / "H_launcher.lock"
H_RUN_IN_PROGRESS_PATH = H_LIVE_DIR / "H_run_in_progress.txt"
H_LAST_FINALIZED_RUN_ID_PATH = H_LIVE_DIR / "H_last_finalized_run_id.txt"
H_RUNTIME_STATUS_PATH = H_LIVE_DIR / "H_runtime_status.json"

UNRESOLVED_BOUNDARY_STATUSES = {"active", "unresolved_parent_exit", "stale_or_orphaned", "waiting"}
MAINTENANCE_MARKER_NAMES = [
    "maintenance.requested",
    "maintenance.ready",
    "maintenance.active",
    "b_cycle.maintenance",
    "h_controlled_mode.active",
]


class HomeTimeError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def session_id(prefix: str, now_utc: str | None = None) -> str:
    base = now_utc or utc_now()
    return f"{prefix}_{base.replace('-', '').replace(':', '')}"


def norm(value: object) -> str:
    return str(value or "").strip()


def read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return norm(path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except Exception:
        return ""


def read_json(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="ascii", errors="strict", newline="\n")
    os.replace(tmp, path)


def append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="ascii", newline="\n") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


def parse_launcher_owner_pid(lock_text: str) -> str:
    match = re.search(r"launcher_pid=(\d+)", lock_text)
    return norm(match.group(1) if match else "")


def load_runtime_status(path: Path) -> dict[str, str]:
    payload = read_json(path)
    return {key: norm(value) for key, value in payload.items()} if payload else {}


def boundary_state_summary(live_dir: Path) -> dict[str, object]:
    files = sorted(live_dir.glob("phase1_intel_alignment.boundary.*.json"))
    latest_run_id = ""
    latest_status = ""
    unresolved_runs: list[str] = []
    resolved_failure_runs: list[str] = []
    details: list[dict[str, str]] = []
    for path in files:
        payload = read_json(path)
        run_id = norm(payload.get("run_id", ""))
        status = norm(payload.get("status", "")).lower()
        if run_id:
            latest_run_id = run_id
        if status:
            latest_status = status
        if run_id and status in UNRESOLVED_BOUNDARY_STATUSES:
            unresolved_runs.append(run_id)
        if run_id and status == "resolved_failure":
            resolved_failure_runs.append(run_id)
        if run_id or status:
            details.append(
                {
                    "path": str(path),
                    "run_id": run_id,
                    "status": status,
                    "updated_utc": norm(payload.get("updated_utc", "")),
                    "state_reason": norm(payload.get("state_reason", "")),
                }
            )
    return {
        "total_boundary_files": len(files),
        "unresolved_exists": bool(unresolved_runs),
        "unresolved_count": len(unresolved_runs),
        "unresolved_runs": unresolved_runs,
        "resolved_failure_count": len(resolved_failure_runs),
        "latest_run_id": latest_run_id,
        "latest_status": latest_status,
        "details": details,
    }


def archive_state_summary(live_dir: Path) -> dict[str, object]:
    files = sorted(live_dir.glob("H_failed_run_archived.*.json"))
    archived_runs: list[str] = []
    details: list[dict[str, str]] = []
    for path in files:
        payload = read_json(path)
        run_id = norm(payload.get("run_id", ""))
        if not run_id:
            run_id = path.name.removeprefix("H_failed_run_archived.").removesuffix(".json")
        if run_id:
            archived_runs.append(run_id)
        details.append(
            {
                "path": str(path),
                "run_id": run_id,
                "archived_at_utc": norm(payload.get("archived_at_utc", "")),
            }
        )
    return {
        "archive_marker_exists": bool(files),
        "archive_marker_count": len(files),
        "archived_runs": archived_runs,
        "latest_archived_run": archived_runs[-1] if archived_runs else "",
        "details": details,
    }


def maintenance_state_summary(locks_dir: Path) -> dict[str, object]:
    present = [name for name in MAINTENANCE_MARKER_NAMES if (locks_dir / name).exists()]
    return {
        "maintenance_markers_present": present,
        "maintenance_markers_exist": bool(present),
    }


def detect_state_anomalies(snapshot: dict[str, object], *, activation_payload: dict[str, object] | None = None) -> list[str]:
    anomalies: list[str] = []
    launcher_owner_pid = norm(snapshot.get("H_launcher_owner_pid", ""))
    runtime_status = snapshot.get("runtime_status_snapshot", {})
    if not isinstance(runtime_status, dict):
        runtime_status = {}
    runtime_run_id = norm(runtime_status.get("run_id", ""))
    runtime_mode = norm(runtime_status.get("mode", "")).upper()
    h_run_in_progress = norm(snapshot.get("H_run_in_progress", ""))
    h_last_finalized_run = norm(snapshot.get("H_last_finalized_run", ""))
    boundary_summary = snapshot.get("boundary_state_summary", {})
    if not isinstance(boundary_summary, dict):
        boundary_summary = {}
    boundary_details = boundary_summary.get("details", [])
    if not isinstance(boundary_details, list):
        boundary_details = []
    if not launcher_owner_pid:
        anomalies.append("launcher_owner_pid_missing")
    if not snapshot.get("h_launcher_lock_exists", False):
        anomalies.append("launcher_lock_missing")
    if not runtime_status:
        anomalies.append("runtime_status_missing")
    if runtime_status and not runtime_run_id:
        anomalies.append("runtime_run_id_missing")
    if h_run_in_progress and h_last_finalized_run and h_run_in_progress == h_last_finalized_run:
        anomalies.append("run_in_progress_equals_finalized")
    if runtime_mode == "RUNNING" and not h_run_in_progress:
        anomalies.append("runtime_running_without_run_in_progress")
    if h_run_in_progress and runtime_run_id and h_run_in_progress != runtime_run_id:
        anomalies.append("runtime_run_id_mismatch")
    if bool(boundary_summary.get("unresolved_exists", False)):
        anomalies.append("unresolved_boundary_present")
    current_run_boundary = None
    for item in boundary_details:
        if not isinstance(item, dict):
            continue
        if norm(item.get("run_id", "")) == runtime_run_id:
            current_run_boundary = item
    if current_run_boundary:
        current_run_boundary_status = norm(current_run_boundary.get("status", "")).lower()
        current_run_boundary_reason = norm(current_run_boundary.get("state_reason", "")).lower()
        if runtime_mode == "RUNNING" and current_run_boundary_status == "resolved_failure":
            anomalies.append("runtime_running_with_resolved_failure_boundary")
        if current_run_boundary_reason == "parent_owner_lost":
            anomalies.append("current_run_boundary_parent_owner_lost")
    if activation_payload:
        activation_launcher_pid = norm(activation_payload.get("H_launcher_owner_pid", ""))
        if activation_launcher_pid and launcher_owner_pid and activation_launcher_pid != launcher_owner_pid:
            anomalies.append("launcher_pid_changed_since_activation")
    return anomalies


def collect_home_time_snapshot(root: Path = ROOT) -> dict[str, object]:
    live_dir = root / "out" / "systems" / "H" / "live"
    locks_dir = root / "out" / "locks"
    launcher_lock_path = live_dir / "H_launcher.lock"
    runtime_status_path = live_dir / "H_runtime_status.json"
    h_run_in_progress_path = live_dir / "H_run_in_progress.txt"
    h_last_finalized_run_id_path = live_dir / "H_last_finalized_run_id.txt"

    launcher_lock_line = read_first_line(launcher_lock_path)
    runtime_status = load_runtime_status(runtime_status_path)
    snapshot: dict[str, object] = {
        "snapshot_utc": utc_now(),
        "h_launcher_lock_exists": launcher_lock_path.exists(),
        "h_launcher_lock_line": launcher_lock_line,
        "H_launcher_owner_pid": parse_launcher_owner_pid(launcher_lock_line),
        "H_run_in_progress": read_first_line(h_run_in_progress_path),
        "H_last_finalized_run": read_first_line(h_last_finalized_run_id_path),
        "runtime_status_snapshot": runtime_status,
        "boundary_state_summary": boundary_state_summary(live_dir),
        "archive_state_summary": archive_state_summary(live_dir),
        "maintenance_state_summary": maintenance_state_summary(locks_dir),
    }
    snapshot["anomalies"] = detect_state_anomalies(snapshot)
    return snapshot


def active_home_time_payload(root: Path = ROOT) -> dict[str, object]:
    return read_json(root / "out" / "systems" / "H" / "live" / "H_home_time_mode.active.json")


def write_home_time_report(root: Path, payload: dict[str, object], *, timestamp_utc: str | None = None) -> Path:
    live_dir = root / "out" / "systems" / "H" / "live"
    stamp = (timestamp_utc or utc_now()).replace("-", "").replace(":", "")
    path = live_dir / f"H_home_time_report.{stamp}.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    return path


def write_diagnostic_snapshot(root: Path, payload: dict[str, object], *, prefix: str = "H_home_time_diagnostic", timestamp_utc: str | None = None) -> Path:
    live_dir = root / "out" / "systems" / "H" / "live"
    stamp = (timestamp_utc or utc_now()).replace("-", "").replace(":", "")
    path = live_dir / f"{prefix}.{stamp}.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    return path


def active_h_python_processes(root: Path = ROOT) -> list[dict[str, str]]:
    repo = str(root).replace("'", "''")
    ps_script = (
        "$repo=[regex]::Escape('{repo}');"
        "$procs=Get-CimInstance Win32_Process | Where-Object {{ "
        "$_.Name -eq 'python.exe' -and $_.CommandLine -match $repo -and ( "
        "$_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle.py*' -or "
        "$_.CommandLine -like '*scripts\\cycles\\run_H_pricing_cycle_guarded.py*' ) }};"
        "$rows=@();"
        "foreach($p in $procs){{"
        "$rows += [pscustomobject]@{{ pid=[string]$p.ProcessId; command_line=[string]$p.CommandLine }};"
        "}};"
        "$rows | ConvertTo-Json -Compress"
    ).format(repo=repo)
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
    except Exception:
        return [{"pid": "unknown", "command_line": "process_check_failed"}]
    raw = norm(completed.stdout)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return [{"pid": "unknown", "command_line": raw[:500]}]
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return [{"pid": "unknown", "command_line": raw[:500]}]
    out: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "pid": norm(item.get("pid", "")),
                "command_line": norm(item.get("command_line", "")),
            }
        )
    return out


def active_h_launcher_processes(root: Path = ROOT) -> list[dict[str, str]]:
    repo = str(root).replace("'", "''")
    ps_script = (
        "$repo=[regex]::Escape('{repo}');"
        "$procs=Get-CimInstance Win32_Process | Where-Object {{ "
        "$_.Name -eq 'cmd.exe' -and $_.CommandLine -match $repo -and $_.CommandLine -like '*run_H_cycle.bat*' }};"
        "$rows=@();"
        "foreach($p in $procs){{"
        "$rows += [pscustomobject]@{{ pid=[string]$p.ProcessId; command_line=[string]$p.CommandLine }};"
        "}};"
        "$rows | ConvertTo-Json -Compress"
    ).format(repo=repo)
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
    except Exception:
        return [{"pid": "unknown", "command_line": "launcher_process_check_failed"}]
    raw = norm(completed.stdout)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return [{"pid": "unknown", "command_line": raw[:500]}]
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return [{"pid": "unknown", "command_line": raw[:500]}]
    out: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "pid": norm(item.get("pid", "")),
                "command_line": norm(item.get("command_line", "")),
            }
        )
    return out


def current_run_archive_candidate(snapshot: dict[str, object], *, root: Path = ROOT) -> dict[str, object]:
    live_dir = root / "out" / "systems" / "H" / "live"
    runtime_status = snapshot.get("runtime_status_snapshot", {})
    if not isinstance(runtime_status, dict):
        runtime_status = {}
    boundary_summary = snapshot.get("boundary_state_summary", {})
    if not isinstance(boundary_summary, dict):
        boundary_summary = {}
    boundary_details = boundary_summary.get("details", [])
    if not isinstance(boundary_details, list):
        boundary_details = []
    current_run_id = norm(snapshot.get("H_run_in_progress", "")) or norm(runtime_status.get("run_id", ""))
    finalized_run_id = norm(snapshot.get("H_last_finalized_run", ""))
    result_exists = False
    result_path = ""
    boundary_status = ""
    boundary_reason = ""
    for item in boundary_details:
        if not isinstance(item, dict):
            continue
        if norm(item.get("run_id", "")) != current_run_id:
            continue
        boundary_status = norm(item.get("status", "")).lower()
        boundary_reason = norm(item.get("state_reason", "")).lower()
        break
    if current_run_id:
        result_files = sorted(live_dir.glob(f"phase1_intel_alignment.result.{current_run_id}.*.json"))
        if result_files:
            result_exists = True
            result_path = str(result_files[-1])
    active_processes = active_h_python_processes(root)
    eligible = bool(current_run_id) and current_run_id != finalized_run_id and not active_processes
    eligible = eligible and boundary_status == "resolved_failure" and result_exists
    return {
        "run_id": current_run_id,
        "finalized_run_id": finalized_run_id,
        "boundary_status": boundary_status,
        "boundary_reason": boundary_reason,
        "result_exists": result_exists,
        "result_path": result_path,
        "active_h_processes": active_processes,
        "eligible": eligible,
    }
