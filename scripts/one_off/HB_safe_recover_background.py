from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
LOCKS_DIR = OUT / "locks"
H_LIVE = OUT / "systems" / "H" / "live"
B_LIVE = OUT / "systems" / "B" / "live"
RECOVERY_DIR = LOCKS_DIR / "recovery"

H_LAUNCHER_BAT = ROOT / "run_H_cycle.bat"
B_LAUNCHER_BAT = ROOT / "run_B_cycle.bat"
MONITOR_SUPERVISOR_BAT = ROOT / "run_home_time_monitor_supervisor.bat"
H_TASK_NAME = "AMZ H Cycle"
B_TASK_NAME = "AMZ Orders"

ALERT_STATE_GLOBAL = OUT / "system_health_alert_state.csv"
ALERT_STATE_H = OUT / "system_health_alert_state_H.csv"
ALERT_HISTORY_GLOBAL = OUT / "system_health_alert_history.csv"
ALERT_HISTORY_H = OUT / "system_health_alert_history_H.csv"
CHECKLIST_H = OUT / "cycle_alerts" / "checklist_H.csv"
CHECKLIST_GLOBAL = OUT / "system_health_checklist.csv"
H_FRESHNESS_CHECKS = {
    "h_cycle_log_freshness",
    "h_phase1_runtime_floor_snapshot_latest_freshness",
    "h_terminal_marker_freshness",
    "h_publish_marker_freshness",
}

HISTORY_COLUMNS = [
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


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")


def _run(
    cmd: list[str],
    *,
    timeout: int = 30,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )


def _parse_utc(value: str) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return _norm(path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except Exception:
        return ""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _parse_lock_fields(payload: str) -> dict[str, str]:
    out: dict[str, str] = {}
    text = _norm(payload)
    if not text:
        return out
    for part in text.split("|"):
        token = _norm(part)
        if not token:
            continue
        if "=" in token:
            key, value = token.split("=", 1)
            out[_norm(key)] = _norm(value)
        elif "owner" not in out:
            out["owner"] = token
    return out


def _pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    completed = _run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
        ],
        timeout=8,
    )
    return bool(_norm(completed.stdout))


def _file_age_seconds(path: Path, now_utc: datetime) -> float | None:
    try:
        if not path.exists():
            return None
        return max((now_utc - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)).total_seconds(), 0.0)
    except Exception:
        return None


def _csv_read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            rows = []
            for row in reader:
                rows.append({str(k): _norm(v) for k, v in row.items() if k is not None})
            return fieldnames, rows
    except Exception:
        return [], []


def _csv_write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            payload = {name: _norm(row.get(name, "")) for name in fieldnames}
            writer.writerow(payload)


def _append_history_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HISTORY_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            payload = {name: _norm(row.get(name, "")) for name in HISTORY_COLUMNS}
            writer.writerow(payload)


def _query_repo_processes() -> list[dict[str, str]]:
    ps = (
        "$procs=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine };"
        "$rows=@();"
        "foreach($p in $procs){"
        "$cmd=[string]$p.CommandLine;"
        "$win='0';"
        "try{$gp=Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue; if($gp){$win=[string]([int64]$gp.MainWindowHandle)}}catch{};"
        "$rows+=[pscustomobject]@{pid=[string]$p.ProcessId;name=[string]$p.Name;command_line=$cmd;main_window_handle=$win}"
        "};"
        "$rows | ConvertTo-Json -Compress"
    )
    completed = _run(["powershell", "-NoProfile", "-Command", ps], timeout=40)
    raw = _norm(completed.stdout)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    rows: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "pid": _norm(item.get("pid", "")),
                "name": _norm(item.get("name", "")),
                "command_line": _norm(item.get("command_line", "")),
                "main_window_handle": _norm(item.get("main_window_handle", "0")),
            }
        )
    return rows


def _classify_owned_processes(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        cmd = _norm(row.get("command_line", "")).lower()
        name = _norm(row.get("name", "")).lower()
        role = ""
        if "run_home_time_monitor_supervisor.bat" in cmd and name == "cmd.exe":
            role = "monitor_supervisor"
        elif "run_home_time_monitor.bat" in cmd and name == "cmd.exe":
            role = "monitor_launcher"
        elif "home_time_monitor.py" in cmd and name == "python.exe":
            role = "monitor_worker"
        elif "run_h_cycle.bat" in cmd and name == "cmd.exe":
            role = "H_launcher"
        elif ("run_h_pricing_cycle.py" in cmd or "run_h_pricing_cycle_guarded.py" in cmd or "h110_run_phase1_h_pilot.py" in cmd) and name == "python.exe":
            role = "H_worker"
        elif "run_b_cycle.bat" in cmd and name == "cmd.exe":
            role = "B_launcher"
        elif "run_b_supervisor.py" in cmd and name == "python.exe":
            role = "B_supervisor"
        elif "run_b_cycle.py" in cmd and name == "python.exe":
            role = "B_worker"
        elif "controlled_restart_controller.py" in cmd and name == "python.exe":
            role = "restart_controller"
        elif "controlled_restart_gate.py" in cmd and name == "python.exe":
            role = "restart_gate"
        if not role:
            continue
        proc = dict(row)
        proc["role"] = role
        out.append(proc)
    return out


def _owned_process_snapshot() -> dict[str, Any]:
    all_rows = _query_repo_processes()
    owned = _classify_owned_processes(all_rows)
    pid_role_keys = {( _norm(row.get("pid", "")), _norm(row.get("role", "")) ) for row in owned}
    lock_owner_hints = [
        ("H_launcher", H_LIVE / "H_launcher.lock", "launcher_pid"),
        ("H_worker", H_LIVE / "H_pricing_cycle.lock", "pid"),
        ("B_supervisor", B_LIVE / "B_supervisor.lock", "pid"),
        ("B_worker", B_LIVE / "B_cycle.lock", "pid"),
        ("H_launcher", H_LIVE / "H_restart_drain.ready", "launcher_pid"),
    ]
    for role, path, pid_key in lock_owner_hints:
        fields = _parse_lock_fields(_read_first_line(path))
        pid_text = _norm(fields.get(pid_key, ""))
        if not pid_text.isdigit():
            continue
        if not _pid_alive(int(pid_text)):
            continue
        marker = (pid_text, role)
        if marker in pid_role_keys:
            continue
        owned.append(
            {
                "pid": pid_text,
                "name": "derived",
                "command_line": f"derived_from_lock:{path}",
                "main_window_handle": "0",
                "role": role,
            }
        )
        pid_role_keys.add(marker)
    visible_monitor = [
        row
        for row in owned
        if row.get("role") in {"monitor_supervisor", "monitor_launcher"}
        and _norm(row.get("main_window_handle", "0")) not in {"", "0"}
    ]
    return {
        "owned_processes": owned,
        "owned_process_count": len(owned),
        "visible_monitor_consoles": visible_monitor,
        "visible_monitor_console_count": len(visible_monitor),
    }


def _lock_info(
    path: Path,
    *,
    pid_key: str = "pid",
    heartbeat_key: str = "heartbeat",
) -> dict[str, Any]:
    line = _read_first_line(path)
    fields = _parse_lock_fields(line)
    pid_raw = _norm(fields.get(pid_key, ""))
    pid = None
    try:
        pid = int(pid_raw) if pid_raw else None
    except Exception:
        pid = None
    hb_raw = _norm(fields.get(heartbeat_key, ""))
    hb_dt = _parse_utc(hb_raw)
    hb_age = None
    if hb_dt is not None:
        hb_age = max((_utc_now() - hb_dt).total_seconds(), 0.0)
    return {
        "path": str(path),
        "exists": path.exists(),
        "line": line,
        "pid": pid,
        "pid_alive": _pid_alive(pid),
        "heartbeat_utc": hb_raw,
        "heartbeat_age_seconds": hb_age,
        "fields": fields,
    }


def _lock_live(info: dict[str, Any], *, max_age_seconds: int) -> bool:
    if not bool(info.get("exists", False)):
        return False
    if not bool(info.get("pid_alive", False)):
        return False
    age = info.get("heartbeat_age_seconds")
    if age is None:
        return True
    return float(age) <= float(max(max_age_seconds, 1))


def _archive_remove(path: Path, archive_dir: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, ""
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_dir / f"{path.name}.{stamp}"
    idx = 1
    while target.exists():
        idx += 1
        target = archive_dir / f"{path.name}.{stamp}.{idx}"
    try:
        os.replace(path, target)
    except Exception:
        return False, ""
    return True, str(target)


def _stop_owned_processes(owned_rows: list[dict[str, str]], *, dry_run: bool) -> list[dict[str, Any]]:
    priority = {
        "monitor_supervisor": 10,
        "monitor_launcher": 11,
        "H_launcher": 20,
        "B_launcher": 21,
        "B_supervisor": 22,
        "H_worker": 30,
        "B_worker": 31,
        "monitor_worker": 32,
        "restart_controller": 40,
        "restart_gate": 41,
    }
    ordered = sorted(
        owned_rows,
        key=lambda item: (priority.get(_norm(item.get("role", "")), 99), int(_norm(item.get("pid", "0")) or "0")),
    )
    results: list[dict[str, Any]] = []
    for row in ordered:
        pid_text = _norm(row.get("pid", ""))
        if not pid_text.isdigit():
            continue
        pid = int(pid_text)
        role = _norm(row.get("role", ""))
        entry: dict[str, Any] = {"pid": pid, "role": role, "stopped": False, "method": "", "reason": ""}
        if dry_run:
            entry["reason"] = "dry_run"
            results.append(entry)
            continue
        if not _pid_alive(pid):
            entry["stopped"] = True
            entry["reason"] = "already_dead"
            results.append(entry)
            continue
        _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Stop-Process -Id {pid} -ErrorAction SilentlyContinue",
            ],
            timeout=10,
        )
        deadline = time.time() + 3.0
        while time.time() < deadline and _pid_alive(pid):
            time.sleep(0.2)
        if _pid_alive(pid):
            _run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=12)
            time.sleep(0.4)
            entry["method"] = "taskkill_force_tree"
        else:
            entry["method"] = "stop_process"
        entry["stopped"] = not _pid_alive(pid)
        entry["reason"] = "stopped" if entry["stopped"] else "still_alive"
        results.append(entry)
    return results


def _stop_scheduled_task(task_name: str, *, dry_run: bool) -> dict[str, Any]:
    task = _norm(task_name)
    out = {"task_name": task, "stopped": False, "reason": "", "stdout_tail": "", "stderr_tail": ""}
    if not task:
        out["reason"] = "missing_task_name"
        return out
    if dry_run:
        out["reason"] = "dry_run"
        return out
    completed = _run(
        ["schtasks", "/End", "/TN", task],
        timeout=30,
    )
    stdout = _norm(completed.stdout)
    stderr = _norm(completed.stderr)
    merged = f"{stdout}\n{stderr}".lower()
    if completed.returncode == 0:
        out["stopped"] = True
        out["reason"] = "stopped"
    elif "not currently running" in merged:
        out["stopped"] = True
        out["reason"] = "not_running"
    else:
        out["reason"] = f"failed_rc_{completed.returncode}"
    out["stdout_tail"] = stdout[-300:]
    out["stderr_tail"] = stderr[-500:]
    return out


def _collect_alert_snapshot() -> dict[str, list[dict[str, str]]]:
    out_map: dict[str, list[dict[str, str]]] = {}
    for name, path in [
        ("global", ALERT_STATE_GLOBAL),
        ("H", ALERT_STATE_H),
    ]:
        _cols, rows = _csv_read_rows(path)
        active = []
        for row in rows:
            status = _norm(row.get("status", "")).lower()
            if status in {"fail", "warn"}:
                active.append(
                    {
                        "check": _norm(row.get("check", "")),
                        "status": status,
                        "first_seen_utc": _norm(row.get("first_seen_utc", "")),
                        "last_seen_utc": _norm(row.get("last_seen_utc", "")),
                        "consecutive_runs": _norm(row.get("consecutive_runs", "")),
                    }
                )
        out_map[name] = active
    return out_map


def _read_kv_value(path: Path, key: str) -> str:
    key_norm = _norm(key)
    if not key_norm:
        return ""
    try:
        if not path.exists():
            return ""
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = _norm(raw_line)
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if _norm(k) == key_norm:
                return _norm(v)
    except Exception:
        return ""
    return ""


def _h_live_freshness_status_map(now_utc: datetime) -> dict[str, dict[str, str]]:
    checks: list[tuple[str, Path, float, float]] = [
        ("h_cycle_log_freshness", H_LIVE / "H_cycle.log", 20.0 * 60.0, 60.0 * 60.0),
        ("h_phase1_runtime_floor_snapshot_latest_freshness", OUT / "phase1_runtime_floor_snapshot_latest.csv", 30.0 * 60.0, 90.0 * 60.0),
        ("h_terminal_marker_freshness", H_LIVE / "H_cycle_last_terminal_info.txt", 30.0 * 60.0, 90.0 * 60.0),
    ]
    out_map: dict[str, dict[str, str]] = {}
    for check_name, path, warn_after, fail_after in checks:
        age = _file_age_seconds(path, now_utc)
        if age is None:
            out_map[check_name] = {"status": "fail", "detail": "missing"}
            continue
        if age > fail_after:
            out_map[check_name] = {"status": "fail", "detail": f"age_seconds={round(age,2)}"}
            continue
        if age > warn_after:
            out_map[check_name] = {"status": "warn", "detail": f"age_seconds={round(age,2)}"}
            continue
        out_map[check_name] = {"status": "ok", "detail": f"age_seconds={round(age,2)}"}

    publish_path = H_LIVE / "H_cycle_last_publish_info.txt"
    terminal_path = H_LIVE / "H_cycle_last_terminal_info.txt"
    publish_age = _file_age_seconds(publish_path, now_utc)
    terminal_age = _file_age_seconds(terminal_path, now_utc)
    if publish_age is None:
        out_map["h_publish_marker_freshness"] = {"status": "fail", "detail": "publish_marker_missing"}
    elif publish_age <= 30.0 * 60.0:
        out_map["h_publish_marker_freshness"] = {"status": "ok", "detail": f"publish_age_seconds={round(publish_age,2)}"}
    elif publish_age <= 90.0 * 60.0:
        out_map["h_publish_marker_freshness"] = {"status": "warn", "detail": f"publish_age_seconds={round(publish_age,2)}"}
    else:
        terminal_state = _read_kv_value(terminal_path, "state").lower()
        if terminal_age is not None and terminal_age <= 30.0 * 60.0 and terminal_state:
            out_map["h_publish_marker_freshness"] = {
                "status": "warn",
                "detail": f"terminal_fallback terminal_age_seconds={round(terminal_age,2)} state={terminal_state}",
            }
        else:
            out_map["h_publish_marker_freshness"] = {
                "status": "fail",
                "detail": (
                    f"publish_age_seconds={round(publish_age,2)};"
                    f"terminal_age_seconds={'' if terminal_age is None else round(terminal_age,2)}"
                ),
            }
    return out_map


def _clear_resolved_alerts_with_live_evidence(*, now_utc: datetime, dry_run: bool) -> dict[str, Any]:
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    live_status = _h_live_freshness_status_map(now_utc)
    details: list[dict[str, Any]] = []
    total_cleared = 0
    for profile, state_path, history_path in [
        ("h", ALERT_STATE_H, ALERT_HISTORY_H),
        ("global", ALERT_STATE_GLOBAL, ALERT_HISTORY_GLOBAL),
    ]:
        fieldnames, rows = _csv_read_rows(state_path)
        _history_cols, history_existing_rows = _csv_read_rows(history_path)
        before_history_count = len(history_existing_rows)
        if not rows:
            details.append(
                {
                    "profile": profile,
                    "state_path": str(state_path),
                    "history_path": str(history_path),
                    "before_active_count": 0,
                    "after_active_count": 0,
                    "before_history_count": before_history_count,
                    "after_history_count": before_history_count,
                    "appended_history_count": 0,
                    "cleared": [],
                }
            )
            continue
        if not fieldnames:
            fieldnames = ["check", "status", "first_seen_utc", "last_seen_utc", "consecutive_runs"]
        keep_rows: list[dict[str, str]] = []
        cleared_rows: list[dict[str, str]] = []
        history_rows: list[dict[str, str]] = []
        for row in rows:
            check = _norm(row.get("check", ""))
            status = _norm(row.get("status", "")).lower()
            live = live_status.get(check)
            should_clear = False
            live_state = ""
            live_detail = ""
            if status in {"fail", "warn"} and live is not None:
                live_state = _norm(live.get("status", "")).lower()
                live_detail = _norm(live.get("detail", ""))
                if status == "fail" and live_state in {"ok", "warn"}:
                    should_clear = True
                elif status == "warn" and live_state == "ok":
                    should_clear = True
            if should_clear:
                cleared_payload = {
                    "check": check,
                    "status": status,
                    "live_status": live_state,
                    "live_detail": live_detail,
                    "clear_reason": "contradicted_by_fresh_live_evidence",
                }
                cleared_rows.append(cleared_payload)
                history_rows.append(
                    {
                        "event_utc": now_iso,
                        "event_type": "cleared",
                        "check": check,
                        "status": status,
                        "instance_first_seen_utc": _norm(row.get("first_seen_utc", "")),
                        "instance_last_seen_utc": _norm(row.get("last_seen_utc", "")) or now_iso,
                        "consecutive_runs": _norm(row.get("consecutive_runs", "")),
                        "cleared_by_status": live_state,
                        "clear_reason": "contradicted_by_fresh_live_evidence",
                        "evidence_source": "HB_safe_recover_background_live_probe",
                        "evidence_utc": now_iso,
                        "profile": profile,
                    }
                )
            else:
                keep_rows.append(row)
        if cleared_rows and not dry_run:
            _csv_write_rows(state_path, fieldnames, keep_rows)
            _append_history_rows(history_path, history_rows)
        total_cleared += len(cleared_rows)
        details.append(
            {
                "profile": profile,
                "state_path": str(state_path),
                "history_path": str(history_path),
                        "before_active_count": sum(1 for row in rows if _norm(row.get("status", "")).lower() in {"fail", "warn"}),
                        "after_active_count": (
                            sum(1 for row in keep_rows if _norm(row.get("status", "")).lower() in {"fail", "warn"})
                            if not dry_run
                            else sum(1 for row in rows if _norm(row.get("status", "")).lower() in {"fail", "warn"}) - len(cleared_rows)
                        ),
                        "before_history_count": before_history_count,
                        "after_history_count": before_history_count + len(history_rows),
                        "appended_history_count": len(history_rows),
                        "cleared": cleared_rows,
                    }
                )
    return {
        "evidence_utc": now_iso,
        "evidence_source": "HB_safe_recover_background_live_probe",
        "live_status": live_status,
        "targets": details,
        "total_cleared": total_cleared,
    }


def _reconcile_stale_h_checklist_rows_with_live_evidence(*, now_utc: datetime, dry_run: bool) -> dict[str, Any]:
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    live_status = _h_live_freshness_status_map(now_utc)
    targets: list[dict[str, Any]] = []
    total_reconciled = 0
    for profile, path in [("h", CHECKLIST_H), ("global", CHECKLIST_GLOBAL)]:
        fieldnames, rows = _csv_read_rows(path)
        before_fail_count = sum(1 for row in rows if _norm(row.get("status", "")).lower() == "fail")
        before_warn_count = sum(1 for row in rows if _norm(row.get("status", "")).lower() == "warn")
        if not rows:
            targets.append(
                {
                    "profile": profile,
                    "checklist_path": str(path),
                    "before_fail_count": before_fail_count,
                    "before_warn_count": before_warn_count,
                    "after_fail_count": before_fail_count,
                    "after_warn_count": before_warn_count,
                    "reconciled_count": 0,
                    "reconciled": [],
                }
            )
            continue
        if not fieldnames:
            fieldnames = list(rows[0].keys())
        if "status" not in fieldnames:
            fieldnames.append("status")
        if "notes" not in fieldnames:
            fieldnames.append("notes")
        reconciled_rows: list[dict[str, str]] = []
        reconciled_count = 0
        for row in rows:
            check = _norm(row.get("check", "")).lower()
            status = _norm(row.get("status", "")).lower()
            live = live_status.get(check)
            should_reconcile = False
            live_state = ""
            if check in H_FRESHNESS_CHECKS and status in {"fail", "warn"} and live is not None:
                live_state = _norm(live.get("status", "")).lower()
                if status == "fail" and live_state in {"ok", "warn"}:
                    should_reconcile = True
                elif status == "warn" and live_state == "ok":
                    should_reconcile = True
            if should_reconcile:
                row["status"] = "ok"
                notes = _norm(row.get("notes", ""))
                suffix = (
                    f"reconciled_utc={now_iso};reason=contradicted_by_fresh_live_evidence;"
                    f"prior_status={status};live_status={live_state}"
                )
                row["notes"] = f"{notes};{suffix}" if notes else suffix
                reconciled_count += 1
                reconciled_rows.append(
                    {
                        "check": check,
                        "prior_status": status,
                        "live_status": live_state,
                        "reason": "contradicted_by_fresh_live_evidence",
                    }
                )
        if reconciled_count > 0 and not dry_run:
            _csv_write_rows(path, fieldnames, rows)
        after_fail_count = sum(1 for row in rows if _norm(row.get("status", "")).lower() == "fail")
        after_warn_count = sum(1 for row in rows if _norm(row.get("status", "")).lower() == "warn")
        total_reconciled += reconciled_count
        targets.append(
            {
                "profile": profile,
                "checklist_path": str(path),
                "before_fail_count": before_fail_count,
                "before_warn_count": before_warn_count,
                "after_fail_count": after_fail_count,
                "after_warn_count": after_warn_count,
                "reconciled_count": reconciled_count,
                "reconciled": reconciled_rows,
            }
        )
    return {
        "evidence_utc": now_iso,
        "evidence_source": "HB_safe_recover_background_live_probe",
        "live_status": live_status,
        "targets": targets,
        "total_reconciled": total_reconciled,
    }


def _collect_state(*, heartbeat_max_age_seconds: int) -> dict[str, Any]:
    process_state = _owned_process_snapshot()
    lock_state = {
        "H_launcher.lock": _lock_info(H_LIVE / "H_launcher.lock", pid_key="launcher_pid", heartbeat_key="utc"),
        "H_pricing_cycle.lock": _lock_info(H_LIVE / "H_pricing_cycle.lock"),
        "H_pricing_cycle.legacy.lock": _lock_info(OUT / "H_pricing_cycle.lock"),
        "H_restart_drain.ready": _lock_info(H_LIVE / "H_restart_drain.ready", pid_key="launcher_pid", heartbeat_key="ts"),
        "B_cycle.lock": _lock_info(B_LIVE / "B_cycle.lock"),
        "B_cycle.legacy.lock": _lock_info(OUT / "B_cycle.lock"),
        "B_supervisor.lock": _lock_info(B_LIVE / "B_supervisor.lock"),
        "A_run_cycle.lock": _lock_info(OUT / "systems" / "A" / "live" / "run_cycle.lock"),
    }
    marker_state = {
        "H_run_in_progress": _read_first_line(H_LIVE / "H_run_in_progress.txt"),
        "H_last_finalized_run_id": _read_first_line(H_LIVE / "H_last_finalized_run_id.txt"),
        "maintenance.requested": _read_first_line(LOCKS_DIR / "maintenance.requested"),
        "maintenance.ready": _read_first_line(LOCKS_DIR / "maintenance.ready"),
        "maintenance.active_exists": (LOCKS_DIR / "maintenance.active").exists(),
        "b_cycle.maintenance_exists": (LOCKS_DIR / "b_cycle.maintenance").exists(),
    }
    runtime_status = _read_json(H_LIVE / "H_runtime_status.json")
    alerts = _collect_alert_snapshot()

    h_lock_live = _lock_live(lock_state["H_pricing_cycle.lock"], max_age_seconds=heartbeat_max_age_seconds)
    b_lock_live = _lock_live(lock_state["B_cycle.lock"], max_age_seconds=heartbeat_max_age_seconds)
    h_owner_running = bool(lock_state["H_pricing_cycle.lock"].get("pid_alive", False)) or bool(
        lock_state["H_launcher.lock"].get("pid_alive", False)
    ) or any(
        row.get("role") in {"H_worker", "H_launcher"} for row in process_state["owned_processes"]
    )
    b_owner_running = bool(lock_state["B_supervisor.lock"].get("pid_alive", False)) or any(
        row.get("role") == "B_supervisor" for row in process_state["owned_processes"]
    )
    monitor_running = any(
        row.get("role") == "monitor_supervisor" for row in process_state["owned_processes"]
    )

    return {
        "captured_utc": _utc_ts(),
        "processes": process_state,
        "locks": lock_state,
        "markers": marker_state,
        "runtime_status": runtime_status,
        "alerts": alerts,
        "truth": {
            "H_owner_running": h_owner_running,
            "B_owner_running": b_owner_running,
            "H_lock_fresh": h_lock_live,
            "B_lock_fresh": b_lock_live,
            "monitor_supervisor_running": monitor_running,
            "visible_monitor_console_count": process_state["visible_monitor_console_count"],
        },
    }


def _clear_stale_runtime_artifacts(
    *,
    before_state: dict[str, Any],
    dry_run: bool,
    archive_dir: Path,
    heartbeat_max_age_seconds: int,
) -> dict[str, Any]:
    removed: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []

    lock_targets = [
        ("H_pricing_cycle.lock", H_LIVE / "H_pricing_cycle.lock", "pid", "heartbeat"),
        ("H_pricing_cycle.legacy.lock", OUT / "H_pricing_cycle.lock", "pid", "heartbeat"),
        ("H_launcher.lock", H_LIVE / "H_launcher.lock", "launcher_pid", "utc"),
        ("H_restart_drain.ready", H_LIVE / "H_restart_drain.ready", "launcher_pid", "ts"),
        ("B_cycle.lock", B_LIVE / "B_cycle.lock", "pid", "heartbeat"),
        ("B_cycle.legacy.lock", OUT / "B_cycle.lock", "pid", "heartbeat"),
        ("B_supervisor.lock", B_LIVE / "B_supervisor.lock", "pid", "heartbeat"),
    ]
    for label, path, pid_key, heartbeat_key in lock_targets:
        info = _lock_info(path, pid_key=pid_key, heartbeat_key=heartbeat_key)
        if not info.get("exists", False):
            continue
        if info.get("pid_alive", False):
            preserved.append({"artifact": label, "path": str(path), "reason": "owner_pid_alive"})
            continue
        reason = "stale_lock_pid_dead_or_missing"
        if dry_run:
            removed.append({"artifact": label, "path": str(path), "reason": reason, "dry_run": True})
            continue
        ok, archive_path = _archive_remove(path, archive_dir)
        if ok:
            removed.append(
                {
                    "artifact": label,
                    "path": str(path),
                    "reason": reason,
                    "archive_path": archive_path,
                }
            )
        else:
            preserved.append({"artifact": label, "path": str(path), "reason": "remove_failed"})

    run_marker_path = H_LIVE / "H_run_in_progress.txt"
    finalized = _read_first_line(H_LIVE / "H_last_finalized_run_id.txt")
    run_in_progress = _read_first_line(run_marker_path)
    runtime_status = _read_json(H_LIVE / "H_runtime_status.json")
    runtime_pid_raw = _norm(runtime_status.get("pid", ""))
    runtime_pid = int(runtime_pid_raw) if runtime_pid_raw.isdigit() else None
    runtime_pid_alive = _pid_alive(runtime_pid)
    h_lock_live = _lock_live(_lock_info(H_LIVE / "H_pricing_cycle.lock"), max_age_seconds=heartbeat_max_age_seconds)
    h_launcher_live = bool(_lock_info(H_LIVE / "H_launcher.lock", pid_key="launcher_pid", heartbeat_key="utc").get("pid_alive", False))

    if run_in_progress:
        if run_in_progress == finalized:
            preserved.append(
                {
                    "artifact": "H_run_in_progress.txt",
                    "path": str(run_marker_path),
                    "reason": "already_finalized_marker",
                }
            )
        elif h_lock_live or h_launcher_live or runtime_pid_alive:
            preserved.append(
                {
                    "artifact": "H_run_in_progress.txt",
                    "path": str(run_marker_path),
                    "reason": "owner_evidence_still_live",
                }
            )
        else:
            reason = "stale_run_marker_no_live_owner"
            if dry_run:
                removed.append({"artifact": "H_run_in_progress.txt", "path": str(run_marker_path), "reason": reason, "dry_run": True})
            else:
                ok, archive_path = _archive_remove(run_marker_path, archive_dir)
                if ok:
                    removed.append(
                        {
                            "artifact": "H_run_in_progress.txt",
                            "path": str(run_marker_path),
                            "reason": reason,
                            "archive_path": archive_path,
                            "run_id": run_in_progress,
                            "finalized": finalized,
                        }
                    )
                else:
                    preserved.append({"artifact": "H_run_in_progress.txt", "path": str(run_marker_path), "reason": "remove_failed"})

    maintenance_requested = LOCKS_DIR / "maintenance.requested"
    maintenance_ready = LOCKS_DIR / "maintenance.ready"
    maintenance_active = LOCKS_DIR / "maintenance.active"
    b_maintenance = LOCKS_DIR / "b_cycle.maintenance"

    a_lock_live = bool(_lock_info(OUT / "systems" / "A" / "live" / "run_cycle.lock").get("pid_alive", False))
    b_lock_live = _lock_live(_lock_info(B_LIVE / "B_cycle.lock"), max_age_seconds=heartbeat_max_age_seconds)

    if maintenance_active.exists():
        if a_lock_live or b_lock_live:
            preserved.append({"artifact": "maintenance.active", "path": str(maintenance_active), "reason": "maintenance_owner_still_live"})
        else:
            if dry_run:
                removed.append({"artifact": "maintenance.active", "path": str(maintenance_active), "reason": "stale_marker_no_live_owner", "dry_run": True})
            else:
                ok, archive_path = _archive_remove(maintenance_active, archive_dir)
                if ok:
                    removed.append({"artifact": "maintenance.active", "path": str(maintenance_active), "reason": "stale_marker_no_live_owner", "archive_path": archive_path})
                else:
                    preserved.append({"artifact": "maintenance.active", "path": str(maintenance_active), "reason": "remove_failed"})

    requested_text = _read_first_line(maintenance_requested)
    if maintenance_requested.exists():
        owned_by_restart_gate = ("requested_by=controlled_restart_gate" in requested_text and "reason=overnight_restart_eval" in requested_text)
        restart_control_alive = any(
            row.get("role") in {"restart_controller", "restart_gate"}
            for row in before_state.get("processes", {}).get("owned_processes", [])
        )
        if owned_by_restart_gate and not restart_control_alive and not maintenance_active.exists():
            if dry_run:
                removed.append({"artifact": "maintenance.requested", "path": str(maintenance_requested), "reason": "stale_restart_gate_marker", "dry_run": True})
            else:
                ok, archive_path = _archive_remove(maintenance_requested, archive_dir)
                if ok:
                    removed.append({"artifact": "maintenance.requested", "path": str(maintenance_requested), "reason": "stale_restart_gate_marker", "archive_path": archive_path})
                else:
                    preserved.append({"artifact": "maintenance.requested", "path": str(maintenance_requested), "reason": "remove_failed"})
        else:
            preserved.append({"artifact": "maintenance.requested", "path": str(maintenance_requested), "reason": "ownership_or_state_uncertain"})

    if maintenance_ready.exists():
        if maintenance_active.exists():
            preserved.append({"artifact": "maintenance.ready", "path": str(maintenance_ready), "reason": "maintenance_active_present"})
        elif maintenance_requested.exists():
            preserved.append({"artifact": "maintenance.ready", "path": str(maintenance_ready), "reason": "request_still_present"})
        else:
            if dry_run:
                removed.append({"artifact": "maintenance.ready", "path": str(maintenance_ready), "reason": "orphan_ready_marker", "dry_run": True})
            else:
                ok, archive_path = _archive_remove(maintenance_ready, archive_dir)
                if ok:
                    removed.append({"artifact": "maintenance.ready", "path": str(maintenance_ready), "reason": "orphan_ready_marker", "archive_path": archive_path})
                else:
                    preserved.append({"artifact": "maintenance.ready", "path": str(maintenance_ready), "reason": "remove_failed"})

    if b_maintenance.exists():
        if b_lock_live:
            preserved.append({"artifact": "b_cycle.maintenance", "path": str(b_maintenance), "reason": "b_cycle_lock_live"})
        else:
            if dry_run:
                removed.append({"artifact": "b_cycle.maintenance", "path": str(b_maintenance), "reason": "stale_pause_marker", "dry_run": True})
            else:
                ok, archive_path = _archive_remove(b_maintenance, archive_dir)
                if ok:
                    removed.append({"artifact": "b_cycle.maintenance", "path": str(b_maintenance), "reason": "stale_pause_marker", "archive_path": archive_path})
                else:
                    preserved.append({"artifact": "b_cycle.maintenance", "path": str(b_maintenance), "reason": "remove_failed"})

    return {"removed": removed, "preserved": preserved}


def _start_bat_hidden(path: Path, *, dry_run: bool) -> dict[str, Any]:
    payload = {"path": str(path), "started": False, "reason": ""}
    if not path.exists():
        payload["reason"] = "missing_launcher"
        return payload
    if dry_run:
        payload["reason"] = "dry_run"
        return payload
    try:
        popen_kwargs: dict[str, Any] = {
            "cwd": str(ROOT),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(getattr(subprocess, "DETACHED_PROCESS", 0))
            if flags:
                popen_kwargs["creationflags"] = flags
        proc = subprocess.Popen(
            ["cmd.exe", "/d", "/c", "call", str(path)],
            **popen_kwargs,
        )
        time.sleep(0.5)
        rc = proc.poll()
        payload["pid"] = int(proc.pid) if proc.pid else 0
        if rc is None:
            payload["started"] = True
            payload["reason"] = "started_hidden"
        else:
            payload["reason"] = f"child_exited_early_rc_{int(rc)}"
    except Exception as exc:
        payload["reason"] = f"start_exception_{type(exc).__name__}"
    return payload


def _wait_for_background_proof(
    *,
    before_state: dict[str, Any],
    restart_started_utc: datetime,
    timeout_seconds: int,
    heartbeat_max_age_seconds: int,
) -> tuple[bool, dict[str, Any]]:
    before_run = _norm(before_state.get("markers", {}).get("H_run_in_progress", ""))
    before_h_lock_run = _norm(
        _parse_lock_fields(_norm(before_state.get("locks", {}).get("H_pricing_cycle.lock", {}).get("line", ""))).get("run_id", "")
    )
    deadline = time.time() + float(max(timeout_seconds, 10))
    attempts: list[dict[str, Any]] = []
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        state = _collect_state(heartbeat_max_age_seconds=heartbeat_max_age_seconds)
        last_state = state
        locks = state.get("locks", {})
        truth = state.get("truth", {})
        markers = state.get("markers", {})
        h_lock = locks.get("H_pricing_cycle.lock", {})
        b_lock = locks.get("B_cycle.lock", {})
        h_lock_run = _norm(_parse_lock_fields(_norm(h_lock.get("line", ""))).get("run_id", ""))
        h_run = _norm(markers.get("H_run_in_progress", ""))
        h_hb_dt = _parse_utc(_norm(h_lock.get("heartbeat_utc", "")))
        b_hb_dt = _parse_utc(_norm(b_lock.get("heartbeat_utc", "")))
        h_new_run_observed = bool(
            (h_run and (h_run != before_run or (h_lock_run and h_lock_run != before_h_lock_run)))
            or (h_hb_dt is not None and h_hb_dt >= restart_started_utc)
        )
        b_new_cycle_observed = bool(b_hb_dt is not None and b_hb_dt >= restart_started_utc)
        proof = {
            "H_owner_running": bool(truth.get("H_owner_running", False)),
            "B_owner_running": bool(truth.get("B_owner_running", False)),
            "H_heartbeat_fresh": bool(truth.get("H_lock_fresh", False)),
            "B_heartbeat_fresh": bool(truth.get("B_lock_fresh", False)),
            "H_new_run_observed": h_new_run_observed,
            "B_new_cycle_observed": b_new_cycle_observed,
            "monitor_supervisor_running": bool(truth.get("monitor_supervisor_running", False)),
            "no_visible_monitor_console": int(truth.get("visible_monitor_console_count", 0)) == 0,
            "H_run_in_progress": h_run,
            "H_lock_run_id": h_lock_run,
            "B_heartbeat_utc": _norm(b_lock.get("heartbeat_utc", "")),
        }
        attempts.append({"checked_utc": _utc_ts(), "proof": proof})
        all_ok = all(
            [
                proof["H_owner_running"],
                proof["B_owner_running"],
                proof["H_heartbeat_fresh"],
                proof["B_heartbeat_fresh"],
                proof["H_new_run_observed"],
                proof["B_new_cycle_observed"],
                proof["no_visible_monitor_console"],
            ]
        )
        if all_ok:
            return True, {"attempts": attempts, "final_proof": proof, "final_state": state}
        time.sleep(4.0)
    return False, {"attempts": attempts, "final_proof": attempts[-1]["proof"] if attempts else {}, "final_state": last_state}


def _write_report(payload: dict[str, Any]) -> Path:
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = RECOVERY_DIR / f"HB_safe_recover_background.{stamp}.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    latest = RECOVERY_DIR / "HB_safe_recover_background.latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely recover H/B into hidden background ownership and clear resolved stale alerts with proof."
    )
    parser.add_argument("--dry-run", action="store_true", help="Inspect and report without mutating state.")
    parser.add_argument("--timeout-seconds", type=int, default=240, help="Max wait time for post-restart proof.")
    parser.add_argument("--heartbeat-max-age-seconds", type=int, default=180, help="Freshness threshold for lock heartbeats.")
    args = parser.parse_args()

    started_utc_dt = _utc_now()
    started_utc = started_utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    archive_dir = RECOVERY_DIR / "archive" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    before_state = _collect_state(heartbeat_max_age_seconds=max(int(args.heartbeat_max_age_seconds), 30))
    scheduler_stops = [
        _stop_scheduled_task(H_TASK_NAME, dry_run=bool(args.dry_run)),
        _stop_scheduled_task(B_TASK_NAME, dry_run=bool(args.dry_run)),
    ]
    if not args.dry_run:
        time.sleep(2.0)
    owned_processes = list(_owned_process_snapshot().get("owned_processes", []))
    stop_results = _stop_owned_processes(owned_processes, dry_run=bool(args.dry_run))

    cleanup = _clear_stale_runtime_artifacts(
        before_state=before_state,
        dry_run=bool(args.dry_run),
        archive_dir=archive_dir,
        heartbeat_max_age_seconds=max(int(args.heartbeat_max_age_seconds), 30),
    )
    alert_clear = _clear_resolved_alerts_with_live_evidence(
        now_utc=_utc_now(),
        dry_run=bool(args.dry_run),
    )
    checklist_reconcile = _reconcile_stale_h_checklist_rows_with_live_evidence(
        now_utc=_utc_now(),
        dry_run=bool(args.dry_run),
    )

    launcher_start_results = [
        _start_bat_hidden(H_LAUNCHER_BAT, dry_run=bool(args.dry_run)),
        _start_bat_hidden(B_LAUNCHER_BAT, dry_run=bool(args.dry_run)),
        _start_bat_hidden(MONITOR_SUPERVISOR_BAT, dry_run=bool(args.dry_run)),
    ]

    proof_ok = False
    proof: dict[str, Any] = {}
    if args.dry_run:
        proof = {"status": "dry_run_no_restart_wait"}
    else:
        proof_ok, proof = _wait_for_background_proof(
            before_state=before_state,
            restart_started_utc=_utc_now(),
            timeout_seconds=max(int(args.timeout_seconds), 20),
            heartbeat_max_age_seconds=max(int(args.heartbeat_max_age_seconds), 30),
        )

    after_state = _collect_state(heartbeat_max_age_seconds=max(int(args.heartbeat_max_age_seconds), 30))
    finished_utc = _utc_ts()

    report = {
        "tool": "HB_safe_recover_background",
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "dry_run": bool(args.dry_run),
        "code_fix_scope": "safe_recovery_runtime",
        "before": before_state,
        "actions": {
            "scheduler_stops": scheduler_stops,
            "stopped_owned_processes": stop_results,
            "runtime_artifact_cleanup": cleanup,
            "resolved_alert_clears": alert_clear,
            "stale_checklist_reconcile": checklist_reconcile,
            "launcher_starts": launcher_start_results,
        },
        "proof": proof,
        "proof_confirmed": proof_ok,
        "after": after_state,
    }
    report_path = _write_report(report)

    summary = {
        "status": "ok" if (args.dry_run or proof_ok) else "not_proven",
        "dry_run": bool(args.dry_run),
        "proof_confirmed": bool(proof_ok),
        "report_path": str(report_path),
        "cleared_alert_count": int(alert_clear.get("total_cleared", 0)),
        "reconciled_checklist_rows": int(checklist_reconcile.get("total_reconciled", 0)),
        "visible_monitor_console_before": int(before_state.get("truth", {}).get("visible_monitor_console_count", 0)),
        "visible_monitor_console_after": int(after_state.get("truth", {}).get("visible_monitor_console_count", 0)),
        "H_owner_running_after": bool(after_state.get("truth", {}).get("H_owner_running", False)),
        "B_owner_running_after": bool(after_state.get("truth", {}).get("B_owner_running", False)),
    }
    print(json.dumps(summary, ensure_ascii=True))
    return 0 if summary["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
