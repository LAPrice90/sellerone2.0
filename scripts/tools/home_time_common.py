from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
H_LIVE_DIR = ROOT / "out" / "systems" / "H" / "live"
LOCKS_DIR = ROOT / "out" / "locks"
ACTIVE_PATH = H_LIVE_DIR / "H_home_time_mode.active.json"
LOG_PATH = H_LIVE_DIR / "H_home_time_mode.log"
HOME_TIME_LOG_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("H_HOME_TIME_MODE_ROTATE_MAX_MB", "4") or "4") * 1024 * 1024),
    512 * 1024,
)
HOME_TIME_LOG_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("H_HOME_TIME_MODE_ROTATE_MAX_FILES", "3") or "3")),
    2,
)
HOME_TIME_LOG_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_HOME_TIME_MODE_FAMILY_MAX_MB", "12") or "12") * 1024 * 1024),
    1024 * 1024,
)
HOME_TIME_REPORT_RETENTION_DAYS = max(
    float(os.environ.get("H_HOME_TIME_REPORT_RETENTION_DAYS", "30") or "30"),
    1.0,
)
HOME_TIME_REPORT_MAX_FILES = max(
    int(float(os.environ.get("H_HOME_TIME_REPORT_MAX_FILES", "40") or "40")),
    5,
)
HOME_TIME_REPORT_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_HOME_TIME_REPORT_FAMILY_MAX_MB", "64") or "64") * 1024 * 1024),
    1024 * 1024,
)
HOME_TIME_DIAGNOSTIC_RETENTION_DAYS = max(
    float(os.environ.get("H_HOME_TIME_DIAGNOSTIC_RETENTION_DAYS", "14") or "14"),
    1.0,
)
HOME_TIME_DIAGNOSTIC_MAX_FILES = max(
    int(float(os.environ.get("H_HOME_TIME_DIAGNOSTIC_MAX_FILES", "80") or "80")),
    10,
)
HOME_TIME_DIAGNOSTIC_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_HOME_TIME_DIAGNOSTIC_FAMILY_MAX_MB", "64") or "64") * 1024 * 1024),
    1024 * 1024,
)
HOME_TIME_SAFETY_SNAPSHOT_RETENTION_DAYS = max(
    float(os.environ.get("H_HOME_TIME_SAFETY_SNAPSHOT_RETENTION_DAYS", "21") or "21"),
    1.0,
)
HOME_TIME_SAFETY_SNAPSHOT_MAX_FILES = max(
    int(float(os.environ.get("H_HOME_TIME_SAFETY_SNAPSHOT_MAX_FILES", "2") or "2")),
    2,
)
HOME_TIME_SAFETY_SNAPSHOT_FAMILY_MAX_BYTES = max(
    int(float(os.environ.get("H_HOME_TIME_SAFETY_SNAPSHOT_FAMILY_MAX_MB", "96") or "96") * 1024 * 1024),
    1024 * 1024,
)
H_LAUNCHER_LOCK_PATH = H_LIVE_DIR / "H_launcher.lock"
H_RUN_IN_PROGRESS_PATH = H_LIVE_DIR / "H_run_in_progress.txt"
H_LAST_FINALIZED_RUN_ID_PATH = H_LIVE_DIR / "H_last_finalized_run_id.txt"
H_RUNTIME_STATUS_PATH = H_LIVE_DIR / "H_runtime_status.json"
HOME_TIME_ARTIFACT_RETENTION_SWEEP_SECONDS = max(
    float(os.environ.get("H_HOME_TIME_ARTIFACT_RETENTION_SWEEP_SECONDS", "300") or "300"),
    15.0,
)
_LAST_HOME_TIME_RETENTION_SWEEP_MONO = 0.0

UNRESOLVED_BOUNDARY_STATUSES = {"active", "unresolved_parent_exit", "stale_or_orphaned", "waiting"}
MAINTENANCE_MARKER_NAMES = [
    "maintenance.requested",
    "maintenance.ready",
    "maintenance.active",
    "b_cycle.maintenance",
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
    _apply_home_time_log_retention(path)
    _maybe_run_home_time_artifact_retention()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="ascii", newline="\n") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


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
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        members = [item for item in members if item[1] != path]
    total_bytes = sum(_file_size_bytes(path) for _, path in members)
    while total_bytes > max_bytes and rotated_desc:
        _, path = rotated_desc.pop(0)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        members = [item for item in members if item[1] != path]
        total_bytes = sum(_file_size_bytes(path2) for _, path2 in members)


def _apply_home_time_log_retention(path: Path) -> None:
    if path != LOG_PATH:
        return
    try:
        _rotate_log_file(path, max_bytes=HOME_TIME_LOG_ROTATE_MAX_BYTES, max_files=HOME_TIME_LOG_ROTATE_MAX_FILES)
        _prune_log_family_budget(
            path,
            max_total_bytes=HOME_TIME_LOG_FAMILY_MAX_BYTES,
            max_total_files=HOME_TIME_LOG_ROTATE_MAX_FILES + 1,
        )
    except Exception:
        pass


def _utc_now_epoch() -> float:
    return time.time()


def _prune_home_time_artifact_group(
    *,
    live_dir: Path,
    pattern: str,
    ttl_days: float,
    max_files: int,
    max_total_bytes: int,
) -> dict[str, int]:
    files = [p for p in live_dir.glob(pattern) if p.is_file()]
    removed_files = 0
    removed_bytes = 0
    cutoff = _utc_now_epoch() - (max(float(ttl_days), 0.0) * 86400.0)

    # First drop stale files by TTL.
    for path in list(files):
        try:
            if path.stat().st_mtime >= cutoff:
                continue
            size = _file_size_bytes(path)
            path.unlink(missing_ok=True)
            removed_files += 1
            removed_bytes += max(size, 0)
        except Exception:
            continue

    files = [p for p in live_dir.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)

    # Then enforce file-count cap (keep most recent).
    while len(files) > max(int(max_files), 1):
        path = files.pop()
        try:
            size = _file_size_bytes(path)
            path.unlink(missing_ok=True)
            removed_files += 1
            removed_bytes += max(size, 0)
        except Exception:
            continue

    files = [p for p in live_dir.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)

    # Finally enforce retained-byte budget (drop oldest first).
    total_bytes = sum(_file_size_bytes(path) for path in files)
    max_bytes = max(int(max_total_bytes), 1)
    while total_bytes > max_bytes and files:
        path = files.pop()
        try:
            size = _file_size_bytes(path)
            path.unlink(missing_ok=True)
            removed_files += 1
            removed_bytes += max(size, 0)
        except Exception:
            pass
        files = [p for p in live_dir.glob(pattern) if p.is_file()]
        files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
        total_bytes = sum(_file_size_bytes(path2) for path2 in files)

    return {"removed_files": int(removed_files), "removed_bytes": int(removed_bytes)}


def run_home_time_artifact_retention(root: Path = ROOT) -> dict[str, dict[str, int]]:
    live_dir = root / "out" / "systems" / "H" / "live"
    groups = {
        "home_time_reports": _prune_home_time_artifact_group(
            live_dir=live_dir,
            pattern="H_home_time_report.*.json",
            ttl_days=HOME_TIME_REPORT_RETENTION_DAYS,
            max_files=HOME_TIME_REPORT_MAX_FILES,
            max_total_bytes=HOME_TIME_REPORT_FAMILY_MAX_BYTES,
        ),
        "home_time_diagnostics": _prune_home_time_artifact_group(
            live_dir=live_dir,
            pattern="H_home_time_*diagnostic*.json",
            ttl_days=HOME_TIME_DIAGNOSTIC_RETENTION_DAYS,
            max_files=HOME_TIME_DIAGNOSTIC_MAX_FILES,
            max_total_bytes=HOME_TIME_DIAGNOSTIC_FAMILY_MAX_BYTES,
        ),
        "home_time_remediations": _prune_home_time_artifact_group(
            live_dir=live_dir,
            pattern="H_home_time_*remediation*.json",
            ttl_days=HOME_TIME_DIAGNOSTIC_RETENTION_DAYS,
            max_files=HOME_TIME_DIAGNOSTIC_MAX_FILES,
            max_total_bytes=HOME_TIME_DIAGNOSTIC_FAMILY_MAX_BYTES,
        ),
        "home_time_safety_snapshots": _prune_home_time_artifact_group(
            live_dir=live_dir,
            pattern="H_home_time_safety_snapshot.*.json",
            ttl_days=HOME_TIME_SAFETY_SNAPSHOT_RETENTION_DAYS,
            max_files=HOME_TIME_SAFETY_SNAPSHOT_MAX_FILES,
            max_total_bytes=HOME_TIME_SAFETY_SNAPSHOT_FAMILY_MAX_BYTES,
        ),
    }
    return groups


def _maybe_run_home_time_artifact_retention(root: Path = ROOT) -> None:
    global _LAST_HOME_TIME_RETENTION_SWEEP_MONO
    now = time.monotonic()
    if _LAST_HOME_TIME_RETENTION_SWEEP_MONO > 0.0 and (now - _LAST_HOME_TIME_RETENTION_SWEEP_MONO) < HOME_TIME_ARTIFACT_RETENTION_SWEEP_SECONDS:
        return
    _LAST_HOME_TIME_RETENTION_SWEEP_MONO = now
    try:
        run_home_time_artifact_retention(root)
    except Exception:
        pass


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
    runtime_detail = norm(runtime_status.get("detail", "")).lower()
    runtime_error = norm(runtime_status.get("error", "")).upper()
    h_run_in_progress = norm(snapshot.get("H_run_in_progress", ""))
    h_last_finalized_run = norm(snapshot.get("H_last_finalized_run", ""))
    boundary_summary = snapshot.get("boundary_state_summary", {})
    if not isinstance(boundary_summary, dict):
        boundary_summary = {}
    boundary_details = boundary_summary.get("details", [])
    if not isinstance(boundary_details, list):
        boundary_details = []
    boundary_status_by_run: dict[str, str] = {}
    for item in boundary_details:
        if not isinstance(item, dict):
            continue
        item_run_id = norm(item.get("run_id", ""))
        if not item_run_id:
            continue
        boundary_status_by_run[item_run_id] = norm(item.get("status", "")).lower()
    runtime_boundary_status = boundary_status_by_run.get(runtime_run_id, "")
    runtime_boundary_unresolved = runtime_boundary_status in UNRESOLVED_BOUNDARY_STATUSES
    runtime_run_is_finalized = bool(runtime_run_id and h_last_finalized_run and runtime_run_id == h_last_finalized_run)
    terminal_idle_no_publish = (
        runtime_detail == "wrapper_no_publish_terminal_ok"
        and runtime_error in {
            "",
            "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH",
        }
        and not runtime_boundary_unresolved
    )
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
        # In home-time wrapper mode, the runtime can remain process-alive after a no-publish terminal.
        # If the run is already finalized and no unresolved boundary exists, this is an expected idle state.
        runtime_expected_idle = (runtime_run_is_finalized and not runtime_boundary_unresolved) or terminal_idle_no_publish
        if not runtime_expected_idle:
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
    run_home_time_artifact_retention(root)
    return path


def write_diagnostic_snapshot(root: Path, payload: dict[str, object], *, prefix: str = "H_home_time_diagnostic", timestamp_utc: str | None = None) -> Path:
    live_dir = root / "out" / "systems" / "H" / "live"
    stamp = (timestamp_utc or utc_now()).replace("-", "").replace(":", "")
    path = live_dir / f"{prefix}.{stamp}.json"
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    run_home_time_artifact_retention(root)
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
