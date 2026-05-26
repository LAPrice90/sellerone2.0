from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.tools.due_check_register import run_due_check_register
from scripts.tools.f_price_list_post_restart_mot import run_f_post_restart_mot


DEFAULT_OUTPUT_PATH = ROOT / "out" / "cycle_alerts" / "morning_mot_system_check.csv"
DEFAULT_JSON_PATH = ROOT / "out" / "cycle_alerts" / "morning_mot_system_check.json"
DEFAULT_REPAIR_PATH = ROOT / "out" / "cycle_alerts" / "morning_mot_repair_actions.json"
DEFAULT_SINGLE_PATH = ROOT / "out" / "cycle_alerts" / "morning_mot_latest.md"

CHECK_COLUMNS = [
    "observed_utc",
    "phase",
    "system",
    "check",
    "status",
    "value",
    "classification",
    "repair_action",
    "notes",
    "source_path",
]

TASKS = {
    "A": "AMZ Pricing Summary",
    "B": "AMZ Orders",
    "H": "AMZ H Cycle",
    "F": "AMZ Price List Manager",
}


def _norm(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_ts() -> str:
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object) -> datetime | None:
    raw = _norm(value)
    if raw == "":
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dt_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_mtime_utc(path: Path) -> datetime | None:
    try:
        if not path.exists():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _age_seconds(value: datetime | None, *, now: datetime) -> float | None:
    if value is None:
        return None
    return max((now - value).total_seconds(), 0.0)


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return _norm(path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except Exception:
        return ""


def _read_text(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [{str(key): _norm(value) for key, value in row.items() if key is not None} for row in reader]
    except Exception:
        return []


def _parse_key_values(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in text.replace("\r", "\n").replace("|", "\n").splitlines():
        clean = _norm(part)
        if clean == "" or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        parsed[_norm(key).lower().lstrip("\ufeff")] = _norm(value)
    return parsed


def _pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        if os.name == "nt":
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
                timeout=10,
                check=False,
            )
            return bool(_norm(completed.stdout))
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _int_or_none(value: object) -> int | None:
    raw = _norm(value)
    if raw == "":
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _lock_state(path: Path, *, now: datetime, stale_seconds: int) -> dict[str, Any]:
    line = _read_first_line(path)
    fields = _parse_key_values(line)
    pid = _int_or_none(fields.get("pid", ""))
    heartbeat = _parse_utc(fields.get("heartbeat", "")) or _parse_utc(fields.get("utc", ""))
    age = _age_seconds(heartbeat, now=now)
    alive = _pid_alive(pid)
    fresh = bool(path.exists() and alive and age is not None and age <= stale_seconds)
    return {
        "path": str(path),
        "exists": path.exists(),
        "line": line,
        "pid": pid,
        "alive": alive,
        "heartbeat_utc": _dt_iso(heartbeat),
        "age_seconds": age,
        "fresh": fresh,
    }


def _latest_manifest(root: Path, flow: str) -> tuple[Path | None, datetime | None, dict[str, Any]]:
    manifest_root = root / "out" / "manifests" / flow
    latest_path: Path | None = None
    latest_dt: datetime | None = None
    latest_payload: dict[str, Any] = {}
    if not manifest_root.exists():
        return None, None, {}
    for path in manifest_root.rglob("*.json"):
        payload = _read_json(path)
        dt = (
            _parse_utc(payload.get("finished_utc"))
            or _parse_utc(payload.get("completed_utc"))
            or _parse_utc(payload.get("ended_utc"))
            or _file_mtime_utc(path)
        )
        if dt is None:
            continue
        if latest_dt is None or dt > latest_dt:
            latest_path = path
            latest_dt = dt
            latest_payload = payload
    return latest_path, latest_dt, latest_payload


def _latest_jsonl(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    latest: dict[str, Any] = {}
    for line in text.splitlines():
        clean = _norm(line)
        if clean == "":
            continue
        try:
            parsed = json.loads(clean)
        except Exception:
            continue
        if isinstance(parsed, dict):
            latest = parsed
    return latest


def _scheduled_task_state(task_name: str) -> dict[str, str]:
    if os.name != "nt":
        return {"task_name": task_name, "exists": "unknown", "state": "unknown", "enabled": "unknown"}
    safe_task_name = task_name.replace("'", "''")
    ps = (
        f"$task=Get-ScheduledTask -TaskName '{safe_task_name}' -ErrorAction SilentlyContinue;"
        "if(-not $task){[pscustomobject]@{exists='0';state='missing';enabled='0'}|ConvertTo-Json -Compress; exit 0};"
        "[pscustomobject]@{exists='1';state=[string]$task.State;enabled=[string]$task.Settings.Enabled}|ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        raw = _norm(completed.stdout)
        parsed = json.loads(raw) if raw else {}
    except Exception:
        parsed = {}
    return {
        "task_name": task_name,
        "exists": _norm(parsed.get("exists", "unknown")),
        "state": _norm(parsed.get("state", "unknown")),
        "enabled": _norm(parsed.get("enabled", "unknown")),
    }


def _add_row(
    rows: list[dict[str, str]],
    *,
    observed_utc: str,
    phase: str,
    system: str,
    check: str,
    status: str,
    value: str,
    classification: str,
    repair_action: str = "",
    notes: str = "",
    source_path: Path | str = "",
) -> None:
    rows.append(
        {
            "observed_utc": observed_utc,
            "phase": phase,
            "system": system,
            "check": check,
            "status": status,
            "value": value,
            "classification": classification,
            "repair_action": repair_action,
            "notes": notes,
            "source_path": str(source_path),
        }
    )


def _is_current_day(dt: datetime | None, observed_dt: datetime) -> bool:
    return dt is not None and dt.astimezone(timezone.utc).date() == observed_dt.astimezone(timezone.utc).date()


def _check_a(root: Path, rows: list[dict[str, str]], *, observed: str, observed_dt: datetime, phase: str, stale_seconds: int) -> bool:
    manifest_path, manifest_dt, payload = _latest_manifest(root, "A")
    lock = _lock_state(root / "out" / "systems" / "A" / "live" / "run_cycle.lock", now=observed_dt, stale_seconds=stale_seconds)
    current = _is_current_day(manifest_dt, observed_dt)
    if phase == "post_restart":
        status = "ok" if lock["fresh"] or manifest_dt is not None else "warn"
        value = "running" if lock["fresh"] else "latest_manifest_seen" if manifest_dt else "missing_manifest"
        classification = "monitor in MOT only"
        repair_action = ""
    elif lock["fresh"]:
        status = "warn"
        value = "a_running"
        classification = "monitor in MOT only"
        repair_action = ""
    elif current:
        status = "ok"
        value = "current_day_manifest"
        classification = "normal"
        repair_action = ""
    else:
        status = "fail"
        value = "stale_after_a_window"
        classification = "needs user decision"
        repair_action = "start_task:AMZ Pricing Summary:requires_allow_a_repair"
    _add_row(
        rows,
        observed_utc=observed,
        phase=phase,
        system="A",
        check="a_cycle_current",
        status=status,
        value=value,
        classification=classification,
        repair_action=repair_action,
        notes=(
            f"latest_manifest_utc={_dt_iso(manifest_dt)};"
            f"current_day={int(current)};final_state={_norm(payload.get('final_state', payload.get('status', '')))};"
            f"lock_fresh={int(bool(lock['fresh']))}"
        ),
        source_path=manifest_path or root / "out" / "manifests" / "A",
    )
    return current


def _check_e(root: Path, rows: list[dict[str, str]], *, observed: str, observed_dt: datetime, phase: str, a_current: bool) -> None:
    manifest_path, manifest_dt, payload = _latest_manifest(root, "E")
    log_path = root / "out" / "systems" / "E" / "live" / "e_run_log.jsonl"
    latest_log = _latest_jsonl(log_path)
    log_dt = (
        _parse_utc(latest_log.get("finished_utc"))
        or _parse_utc(latest_log.get("completed_utc"))
        or _parse_utc(latest_log.get("observed_utc"))
        or _file_mtime_utc(log_path)
    )
    latest_dt = max([dt for dt in [manifest_dt, log_dt] if dt is not None], default=None)
    current = _is_current_day(latest_dt, observed_dt)
    if phase == "post_restart":
        status = "ok" if latest_dt is not None else "warn"
        value = "latest_e_seen" if latest_dt else "missing"
        classification = "monitor in MOT only"
        repair_action = ""
    elif current:
        status = "ok"
        value = "current_day_evidence"
        classification = "normal"
        repair_action = ""
    elif a_current:
        status = "fail"
        value = "stale_after_current_a"
        classification = "fix now"
        repair_action = "start_e_cycle"
    else:
        status = "warn"
        value = "waiting_for_current_a"
        classification = "monitor in MOT only"
        repair_action = ""
    _add_row(
        rows,
        observed_utc=observed,
        phase=phase,
        system="E",
        check="e_cycle_current",
        status=status,
        value=value,
        classification=classification,
        repair_action=repair_action,
        notes=(
            f"latest_manifest_utc={_dt_iso(manifest_dt)};latest_log_utc={_dt_iso(log_dt)};"
            f"final_state={_norm(payload.get('final_state', payload.get('status', '')))};a_current={int(a_current)}"
        ),
        source_path=manifest_path or log_path,
    )


def _check_b(root: Path, rows: list[dict[str, str]], *, observed: str, observed_dt: datetime, phase: str, stale_seconds: int) -> None:
    live = root / "out" / "systems" / "B" / "live"
    supervisor = _lock_state(live / "B_supervisor.lock", now=observed_dt, stale_seconds=stale_seconds)
    worker = _lock_state(live / "B_cycle.lock", now=observed_dt, stale_seconds=stale_seconds)
    fresh = bool(supervisor["fresh"] or worker["fresh"])
    task = _scheduled_task_state(TASKS["B"])
    if fresh:
        status = "ok"
        value = "running"
        classification = "normal"
        repair_action = ""
    else:
        status = "fail"
        value = "stale_or_not_running"
        classification = "fix now"
        repair_action = "start_task:AMZ Orders"
    _add_row(
        rows,
        observed_utc=observed,
        phase=phase,
        system="B",
        check="b_owner_running",
        status=status,
        value=value,
        classification=classification,
        repair_action=repair_action,
        notes=(
            f"supervisor_fresh={int(bool(supervisor['fresh']))};worker_fresh={int(bool(worker['fresh']))};"
            f"supervisor_pid={supervisor.get('pid')};worker_pid={worker.get('pid')};"
            f"task_state={task.get('state')};task_enabled={task.get('enabled')}"
        ),
        source_path=live / "B_supervisor.lock",
    )


def _check_h(root: Path, rows: list[dict[str, str]], *, observed: str, observed_dt: datetime, phase: str, stale_seconds: int) -> None:
    live = root / "out" / "systems" / "H" / "live"
    launcher_hb_text = _read_first_line(live / "H_launcher.heartbeat")
    launcher_fields = _parse_key_values(launcher_hb_text)
    launcher_dt = _parse_utc(launcher_fields.get("utc", "")) or _file_mtime_utc(live / "H_launcher.heartbeat")
    launcher_age = _age_seconds(launcher_dt, now=observed_dt)
    launcher_fresh = launcher_age is not None and launcher_age <= max(stale_seconds, 420)
    cycle_lock = _lock_state(live / "H_pricing_cycle.lock", now=observed_dt, stale_seconds=stale_seconds)
    root_lock = _lock_state(root / "out" / "H_pricing_cycle.lock", now=observed_dt, stale_seconds=stale_seconds)
    runtime = _read_json(live / "H_runtime_status.json")
    runtime_dt = _parse_utc(runtime.get("utc", "")) or _file_mtime_utc(live / "H_runtime_status.json")
    runtime_age = _age_seconds(runtime_dt, now=observed_dt)
    runtime_fresh = runtime_age is not None and runtime_age <= max(stale_seconds, 420)
    fresh = bool(launcher_fresh or cycle_lock["fresh"] or root_lock["fresh"] or runtime_fresh)
    task = _scheduled_task_state(TASKS["H"])
    if fresh:
        status = "ok"
        value = "running_or_recent"
        classification = "normal"
        repair_action = ""
    else:
        status = "fail"
        value = "stale_or_not_running"
        classification = "fix now"
        repair_action = "start_task:AMZ H Cycle"
    _add_row(
        rows,
        observed_utc=observed,
        phase=phase,
        system="H",
        check="h_owner_running",
        status=status,
        value=value,
        classification=classification,
        repair_action=repair_action,
        notes=(
            f"launcher_fresh={int(bool(launcher_fresh))};cycle_lock_fresh={int(bool(cycle_lock['fresh']))};"
            f"root_lock_fresh={int(bool(root_lock['fresh']))};runtime_fresh={int(bool(runtime_fresh))};"
            f"runtime_mode={_norm(runtime.get('mode', ''))};task_state={task.get('state')};task_enabled={task.get('enabled')}"
        ),
        source_path=live / "H_launcher.heartbeat",
    )


def _check_f(root: Path, rows: list[dict[str, str]], *, observed: str, phase: str) -> None:
    summary = run_f_post_restart_mot(root=root, observed_utc=observed)
    status = _norm(summary.get("status", "warn")).lower() or "warn"
    if status == "fail":
        classification = "fix now"
        repair_action = "run_f_supervisor_once"
    elif status == "warn":
        classification = "monitor in MOT only"
        repair_action = ""
    else:
        classification = "normal"
        repair_action = ""
    _add_row(
        rows,
        observed_utc=observed,
        phase=phase,
        system="F",
        check="f_price_list_post_restart",
        status=status,
        value=_norm(summary.get("cause_anchor", "")) or status,
        classification=classification,
        repair_action=repair_action,
        notes=f"row_count={summary.get('row_count')};fail_rows={summary.get('fail_rows')};warn_rows={summary.get('warn_rows')}",
        source_path=_norm(summary.get("output_path", "")),
    )


def _check_due_register(root: Path, rows: list[dict[str, str]], *, observed: str, phase: str) -> None:
    summary = run_due_check_register(root=root, observed_utc=observed)
    status = _norm(summary.get("status", "warn")).lower() or "warn"
    classification = "monitor in MOT only" if status == "warn" else "fix now" if status == "fail" else "normal"
    _add_row(
        rows,
        observed_utc=observed,
        phase=phase,
        system="System",
        check="due_check_register",
        status=status,
        value=f"due_rows={summary.get('due_rows')}",
        classification=classification,
        repair_action="",
        notes=f"rows={summary.get('rows')};warn_rows={summary.get('warn_rows')};fail_rows={summary.get('fail_rows')}",
        source_path=_norm(summary.get("output_path", "")),
    )


def _overall_status(rows: list[dict[str, str]]) -> str:
    statuses = {_norm(row.get("status", "")).lower() for row in rows}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "ok"


def build_morning_mot_system_check(
    *,
    root: Path = ROOT,
    phase: str = "post_a",
    observed_utc: str | None = None,
    stale_seconds: int = 300,
) -> dict[str, Any]:
    observed = observed_utc or _utc_ts()
    observed_dt = _parse_utc(observed) or _utc_now()
    rows: list[dict[str, str]] = []
    clean_phase = phase if phase in {"post_restart", "post_a", "manual"} else "manual"
    a_current = _check_a(root, rows, observed=observed, observed_dt=observed_dt, phase=clean_phase, stale_seconds=stale_seconds)
    _check_e(root, rows, observed=observed, observed_dt=observed_dt, phase=clean_phase, a_current=a_current)
    _check_b(root, rows, observed=observed, observed_dt=observed_dt, phase=clean_phase, stale_seconds=stale_seconds)
    _check_h(root, rows, observed=observed, observed_dt=observed_dt, phase=clean_phase, stale_seconds=stale_seconds)
    _check_f(root, rows, observed=observed, phase=clean_phase)
    _check_due_register(root, rows, observed=observed, phase=clean_phase)
    return {
        "status": _overall_status(rows),
        "observed_utc": observed,
        "phase": clean_phase,
        "rows": rows,
        "row_count": len(rows),
        "fail_rows": sum(1 for row in rows if row.get("status") == "fail"),
        "warn_rows": sum(1 for row in rows if row.get("status") == "warn"),
    }


def write_check_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHECK_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: _norm(row.get(column, "")) for column in CHECK_COLUMNS} for row in rows])


def _markdown_cell(value: object) -> str:
    return _norm(value).replace("|", "/").replace("\r", " ").replace("\n", " ")


def _restart_summary(root: Path) -> dict[str, str]:
    latest = _read_json(root / "out" / "locks" / "restart_control" / "restart_controller.latest.json")
    flags = latest.get("reboot_requested_flags", {}) if isinstance(latest.get("reboot_requested_flags"), dict) else {}
    blockers = latest.get("final_blockers", [])
    blocker_text = ", ".join(_norm(item) for item in blockers if _norm(item)) if isinstance(blockers, list) else _norm(blockers)
    controller_bat = _read_text(root / "run_controlled_restart_controller.bat")
    current_force_default = "enabled" if 'CONTROLLED_RESTART_FORCE_REBOOT_ON_SKIP=1' in controller_bat else "disabled"
    return {
        "started_utc": _norm(latest.get("started_utc", "")),
        "finished_utc": _norm(latest.get("finished_utc", "")),
        "outcome": _norm(latest.get("outcome", "")),
        "decision": _norm(latest.get("decision", "")),
        "reboot_attempted": _norm(latest.get("reboot_attempted", "")),
        "reboot_status": _norm(latest.get("reboot_status", "")),
        "force_reboot_on_skip": _norm(flags.get("force_reboot_on_skip", "")),
        "current_force_reboot_default": current_force_default,
        "stale_h_override": "enabled",
        "h_cycle_task_relaunch_reason": _norm(latest.get("h_cycle_task_relaunch_reason", "")),
        "final_blockers": blocker_text,
    }


def write_single_mot_file(
    path: Path,
    *,
    root: Path,
    payload: dict[str, Any],
    rows: list[dict[str, str]],
    actions: list[dict[str, Any]],
) -> None:
    restart = _restart_summary(root)
    fail_rows = [row for row in rows if _norm(row.get("status", "")).lower() == "fail"]
    warn_rows = [row for row in rows if _norm(row.get("status", "")).lower() == "warn"]
    lines = [
        "# SellerOne Morning MOT",
        "",
        f"- Observed UTC: {_markdown_cell(payload.get('observed_utc', ''))}",
        f"- Phase: {_markdown_cell(payload.get('phase', ''))}",
        f"- Overall status: {_markdown_cell(payload.get('status', ''))}",
        f"- Checks: {_markdown_cell(payload.get('row_count', ''))}",
        f"- FAIL rows: {_markdown_cell(payload.get('fail_rows', ''))}",
        f"- WARN rows: {_markdown_cell(payload.get('warn_rows', ''))}",
        "",
        "## Restart",
        "",
        f"- Latest restart started UTC: {_markdown_cell(restart.get('started_utc', ''))}",
        f"- Latest restart finished UTC: {_markdown_cell(restart.get('finished_utc', ''))}",
        f"- Latest restart outcome: {_markdown_cell(restart.get('outcome', ''))}",
        f"- Restart decision: {_markdown_cell(restart.get('decision', ''))}",
        f"- Reboot attempted: {_markdown_cell(restart.get('reboot_attempted', ''))}",
        f"- Reboot status: {_markdown_cell(restart.get('reboot_status', ''))}",
        f"- Force reboot on skip in latest run: {_markdown_cell(restart.get('force_reboot_on_skip', ''))}",
        f"- Current force reboot fallback: {_markdown_cell(restart.get('current_force_reboot_default', ''))}",
        f"- Current stale H marker override: {_markdown_cell(restart.get('stale_h_override', ''))}",
        f"- H relaunch reason: {_markdown_cell(restart.get('h_cycle_task_relaunch_reason', ''))}",
        f"- Final blockers: {_markdown_cell(restart.get('final_blockers', ''))}",
        "",
        "## Checks",
        "",
        "| System | Check | Status | Value | Classification | Repair | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(row.get("system", "")),
                    _markdown_cell(row.get("check", "")),
                    _markdown_cell(row.get("status", "")),
                    _markdown_cell(row.get("value", "")),
                    _markdown_cell(row.get("classification", "")),
                    _markdown_cell(row.get("repair_action", "")),
                    _markdown_cell(row.get("notes", "")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Active Attention", ""])
    if not fail_rows and not warn_rows:
        lines.append("- No FAIL or WARN rows.")
    for row in fail_rows + warn_rows:
        lines.append(
            f"- {_markdown_cell(row.get('status', '')).upper()} "
            f"{_markdown_cell(row.get('system', ''))}.{_markdown_cell(row.get('check', ''))}: "
            f"{_markdown_cell(row.get('value', ''))}"
        )
    lines.extend(["", "## Repair Actions", ""])
    if not actions:
        lines.append("- No repair actions were run.")
    else:
        for action in actions:
            action_name = action.get("action", action.get("task_name", ""))
            lines.append(
                f"- {_markdown_cell(action_name)}: status={_markdown_cell(action.get('status', ''))} "
                f"reason={_markdown_cell(action.get('reason', action.get('stderr', '')))}"
            )
    lines.extend(
        [
            "",
            "## Source Files",
            "",
            f"- CSV detail: {_markdown_cell(payload.get('output_path', ''))}",
            f"- JSON summary: {_markdown_cell(payload.get('json_path', ''))}",
            f"- Repair log: {_markdown_cell(payload.get('repair_path', ''))}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _start_scheduled_task(task_name: str) -> dict[str, Any]:
    if os.name != "nt":
        return {"action": "start_task", "task_name": task_name, "status": "skipped", "reason": "not_windows"}
    safe_task_name = task_name.replace("'", "''")
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Start-ScheduledTask -TaskName '{safe_task_name}'"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    return {
        "action": "start_task",
        "task_name": task_name,
        "status": "ok" if completed.returncode == 0 else "failed",
        "rc": completed.returncode,
        "stdout": _norm(completed.stdout),
        "stderr": _norm(completed.stderr),
    }


def _start_e_cycle(root: Path) -> dict[str, Any]:
    script = root / "scripts" / "cycles" / "run_E_cycle.py"
    if not script.exists():
        return {"action": "start_e_cycle", "status": "failed", "reason": "missing_script", "path": str(script)}
    kwargs: dict[str, Any] = {
        "cwd": str(root),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen([sys.executable, "-u", str(script)], **kwargs)
    return {"action": "start_e_cycle", "status": "started", "pid": proc.pid, "path": str(script)}


def _run_f_supervisor_once(root: Path) -> dict[str, Any]:
    script = root / "scripts" / "flows" / "F" / "price_list_manager" / "FPM170_supervise_live_cycle.py"
    completed = subprocess.run(
        [sys.executable, "-u", str(script), "--once"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    return {
        "action": "run_f_supervisor_once",
        "status": "ok" if completed.returncode == 0 else "failed",
        "rc": completed.returncode,
        "stdout": _norm(completed.stdout),
        "stderr": _norm(completed.stderr),
    }


def execute_repairs(
    rows: list[dict[str, str]],
    *,
    root: Path = ROOT,
    allow_a_repair: bool = False,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if _norm(row.get("status", "")).lower() != "fail":
            continue
        action = _norm(row.get("repair_action", ""))
        if action == "" or action in seen:
            continue
        seen.add(action)
        if action.startswith("start_task:AMZ Pricing Summary"):
            if not allow_a_repair:
                actions.append(
                    {
                        "action": action,
                        "status": "skipped",
                        "reason": "A repair requires --allow-a-repair because A can touch external sheet/API paths.",
                    }
                )
            else:
                actions.append(_start_scheduled_task(TASKS["A"]))
        elif action.startswith("start_task:"):
            task_name = action.split(":", 1)[1]
            actions.append(_start_scheduled_task(task_name))
        elif action == "start_e_cycle":
            actions.append(_start_e_cycle(root))
        elif action == "run_f_supervisor_once":
            actions.append(_run_f_supervisor_once(root))
        else:
            actions.append({"action": action, "status": "skipped", "reason": "unknown_repair_action"})
    return actions


def run_morning_mot_system(
    *,
    root: Path = ROOT,
    phase: str = "post_a",
    observed_utc: str | None = None,
    stale_seconds: int = 300,
    repair: bool = False,
    allow_a_repair: bool = False,
    proof_wait_seconds: int = 30,
    output_path: Path | None = None,
    json_path: Path | None = None,
    repair_path: Path | None = None,
    single_path: Path | None = None,
) -> dict[str, Any]:
    out_csv = output_path or (root / "out" / "cycle_alerts" / "morning_mot_system_check.csv")
    out_json = json_path or (root / "out" / "cycle_alerts" / "morning_mot_system_check.json")
    out_repair = repair_path or (root / "out" / "cycle_alerts" / "morning_mot_repair_actions.json")
    out_single = single_path or (root / "out" / "cycle_alerts" / "morning_mot_latest.md")
    summary = build_morning_mot_system_check(
        root=root,
        phase=phase,
        observed_utc=observed_utc,
        stale_seconds=stale_seconds,
    )
    actions: list[dict[str, Any]] = []
    if repair:
        actions = execute_repairs(summary["rows"], root=root, allow_a_repair=allow_a_repair)
        if proof_wait_seconds > 0 and actions:
            time.sleep(float(max(proof_wait_seconds, 0)))
            summary = build_morning_mot_system_check(root=root, phase=phase, stale_seconds=stale_seconds)
    write_check_csv(out_csv, summary["rows"])
    payload = {key: value for key, value in summary.items() if key != "rows"}
    payload["output_path"] = str(out_csv)
    payload["json_path"] = str(out_json)
    payload["repair_enabled"] = bool(repair)
    payload["allow_a_repair"] = bool(allow_a_repair)
    payload["repair_path"] = str(out_repair)
    payload["single_mot_path"] = str(out_single)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    repair_payload = {
        "observed_utc": payload["observed_utc"],
        "phase": payload["phase"],
        "repair_enabled": bool(repair),
        "allow_a_repair": bool(allow_a_repair),
        "actions": actions,
    }
    out_repair.parent.mkdir(parents=True, exist_ok=True)
    out_repair.write_text(json.dumps(repair_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_single_mot_file(out_single, root=root, payload=payload, rows=summary["rows"], actions=actions)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the system-wide morning MOT check and guarded stale repair.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--phase", choices=["post_restart", "post_a", "manual"], default="post_a")
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--stale-seconds", type=int, default=300)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--allow-a-repair", action="store_true")
    parser.add_argument("--proof-wait-seconds", type=int, default=30)
    parser.add_argument("--output-path", default="")
    parser.add_argument("--json-path", default="")
    parser.add_argument("--repair-path", default="")
    parser.add_argument("--single-path", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_morning_mot_system(
        root=Path(args.root),
        phase=args.phase,
        observed_utc=_norm(args.observed_utc) or None,
        stale_seconds=max(int(args.stale_seconds), 30),
        repair=bool(args.repair),
        allow_a_repair=bool(args.allow_a_repair),
        proof_wait_seconds=max(int(args.proof_wait_seconds), 0),
        output_path=Path(args.output_path) if _norm(args.output_path) else None,
        json_path=Path(args.json_path) if _norm(args.json_path) else None,
        repair_path=Path(args.repair_path) if _norm(args.repair_path) else None,
        single_path=Path(args.single_path) if _norm(args.single_path) else None,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 1 if summary["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
