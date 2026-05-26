from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_H_TASK_NAME = "AMZ H Cycle"
DEFAULT_ACTIVE_REMEDIATION_ENV = "H_RESTART_ESCALATION_MODE"
DEFAULT_RUNTIME_ACTIONS_ENV = "HOME_TIME_ALLOW_RUNTIME_ACTIONS"
SIMPLIFICATION_FREEZE_PATH = ROOT / "out" / "locks" / "simplification.freeze"
SIMPLIFICATION_FREEZE_OVERRIDE_ENV = "SIMPLIFICATION_FREEZE_OVERRIDE"

try:
    from scripts.tools.home_time_common import (
        HomeTimeError,
        active_home_time_payload,
        active_h_python_processes,
        active_h_launcher_processes,
        append_jsonl,
        collect_home_time_snapshot,
        norm,
        utc_now,
        write_diagnostic_snapshot,
    )
except ModuleNotFoundError:
    from home_time_common import (
        HomeTimeError,
        active_home_time_payload,
        active_h_python_processes,
        active_h_launcher_processes,
        append_jsonl,
        collect_home_time_snapshot,
        norm,
        utc_now,
        write_diagnostic_snapshot,
    )


def _truthy_env(value: str) -> bool:
    return norm(value).lower() in {"1", "true", "yes", "on"}


def _simplification_freeze_active() -> bool:
    if _truthy_env(os.environ.get(SIMPLIFICATION_FREEZE_OVERRIDE_ENV, "0")):
        return False
    return SIMPLIFICATION_FREEZE_PATH.exists()


def _task_state(task_name: str) -> str:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"(Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue).State",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    return norm(completed.stdout)


def _pid_is_alive(pid_text: str) -> bool:
    pid = norm(pid_text)
    if not pid.isdigit():
        return False
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ '1' }}",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    return norm(completed.stdout) == "1"


def _persist_activation_owner(*, root: Path, activation_payload: dict[str, object], launcher_pid: str) -> dict[str, object]:
    updated = dict(activation_payload)
    updated["H_launcher_owner_pid"] = norm(launcher_pid)
    updated["owner_reconciled_utc"] = utc_now()
    active_path = root / "out" / "systems" / "H" / "live" / "H_home_time_mode.active.json"
    active_path.write_text(json.dumps(updated, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return updated


def _observer_only_event_payload(
    *,
    allow_safe_archive: bool,
    allow_safe_bootstrap: bool,
    active_remediation: bool,
) -> dict[str, object]:
    return {
        "action": "remediation_blocked",
        "reason": "observer_only_design",
        "requested_active_remediation": bool(active_remediation),
        "requested_allow_safe_archive": bool(allow_safe_archive),
        "requested_allow_safe_bootstrap": bool(allow_safe_bootstrap),
    }


def monitor_home_time(
    *,
    root: Path,
    iterations: int,
    interval_seconds: float,
    allow_safe_archive: bool,
    allow_safe_bootstrap: bool,
    active_remediation: bool,
) -> dict[str, object]:
    log_path = root / "out" / "systems" / "H" / "live" / "H_home_time_mode.log"
    activation_payload = active_home_time_payload(root)
    if not activation_payload:
        raise HomeTimeError("home_time_mode_not_active")

    session_id = norm(activation_payload.get("session_id", ""))
    checks_run = 0
    anomalies_seen: list[str] = []
    diagnostics_written: list[str] = []
    remediations: list[dict[str, object]] = []

    for index in range(max(iterations, 1)):
        snapshot = collect_home_time_snapshot(root)
        task_state = _task_state(DEFAULT_H_TASK_NAME)
        launcher_processes = active_h_launcher_processes(root)
        h_python_processes = active_h_python_processes(root)
        activation_launcher_pid = norm(activation_payload.get("H_launcher_owner_pid", ""))
        current_launcher_pid = norm(snapshot.get("H_launcher_owner_pid", ""))
        anomalies = list(snapshot.get("anomalies", []))
        runtime_status = snapshot.get("runtime_status_snapshot", {})
        runtime_mode = ""
        runtime_pid = ""
        if isinstance(runtime_status, dict):
            runtime_mode = norm(runtime_status.get("mode", "")).upper()
            runtime_pid = norm(runtime_status.get("pid", ""))
        launcher_pid_alive = _pid_is_alive(current_launcher_pid)
        runtime_pid_alive = _pid_is_alive(runtime_pid)
        if runtime_mode == "ERROR" and "runtime_error_mode" not in anomalies:
            anomalies.append("runtime_error_mode")
        owner_present = bool(launcher_processes) or bool(h_python_processes) or launcher_pid_alive or runtime_pid_alive
        if task_state.lower() == "running" and not owner_present:
            if "scheduler_running_without_h_owner" not in anomalies:
                anomalies.append("scheduler_running_without_h_owner")
        if activation_launcher_pid and current_launcher_pid and activation_launcher_pid != current_launcher_pid:
            if launcher_pid_alive:
                activation_payload = _persist_activation_owner(
                    root=root,
                    activation_payload=activation_payload,
                    launcher_pid=current_launcher_pid,
                )
                anomalies = [item for item in anomalies if item != "launcher_pid_changed_since_activation"]
                append_jsonl(
                    log_path,
                    {
                        "event": "home_time_monitor_owner_reconciled",
                        "check_utc": utc_now(),
                        "session_id": session_id,
                        "previous_launcher_pid": activation_launcher_pid,
                        "current_launcher_pid": current_launcher_pid,
                    },
                )
            elif "launcher_pid_changed_since_activation" not in anomalies:
                anomalies.append("launcher_pid_changed_since_activation")
        checks_run += 1
        append_jsonl(
            log_path,
            {
                "event": "home_time_monitor_check",
                "check_utc": utc_now(),
                "session_id": session_id,
                "iteration": index + 1,
                "launcher_pid": current_launcher_pid,
                "launcher_pid_alive": launcher_pid_alive,
                "runtime_pid": runtime_pid,
                "runtime_pid_alive": runtime_pid_alive,
                "task_state": task_state,
                "runtime_run_id": norm(snapshot.get("runtime_status_snapshot", {}).get("run_id", ""))
                if isinstance(snapshot.get("runtime_status_snapshot", {}), dict)
                else "",
                "anomalies": anomalies,
            },
        )
        if anomalies:
            for item in anomalies:
                if item not in anomalies_seen:
                    anomalies_seen.append(item)
            diagnostic_payload = {
                "diagnostic_type": "home_time_monitor_anomaly",
                "diagnostic_utc": utc_now(),
                "session_id": session_id,
                "anomalies": anomalies,
                "snapshot": snapshot,
            }
            diagnostic_path = write_diagnostic_snapshot(root, diagnostic_payload, prefix="H_home_time_monitor_diagnostic")
            diagnostics_written.append(str(diagnostic_path))
            append_jsonl(
                log_path,
                {
                    "event": "home_time_monitor_anomaly",
                    "check_utc": utc_now(),
                    "session_id": session_id,
                    "anomalies": anomalies,
                    "diagnostic_path": str(diagnostic_path),
                },
            )
            append_jsonl(
                log_path,
                {
                    "event": "home_time_monitor_observer_only",
                    "check_utc": utc_now(),
                    "session_id": session_id,
                    **_observer_only_event_payload(
                        allow_safe_archive=allow_safe_archive,
                        allow_safe_bootstrap=allow_safe_bootstrap,
                        active_remediation=active_remediation,
                    ),
                },
            )
        if index + 1 < max(iterations, 1):
            time.sleep(max(interval_seconds, 0.1))

    return {
        "status": "ok",
        "session_id": session_id,
        "checks_run": checks_run,
        "anomalies_seen": anomalies_seen,
        "diagnostics_written": diagnostics_written,
        "remediations": remediations,
        "active_remediation": False,
        "observer_only_enforced": True,
        "requested_active_remediation": bool(active_remediation),
        "requested_allow_safe_archive": bool(allow_safe_archive),
        "requested_allow_safe_bootstrap": bool(allow_safe_bootstrap),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor an active home time session in observer-only mode.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--idle-interval-seconds", type=float, default=60.0)
    parser.add_argument("--allow-safe-archive", action="store_true")
    parser.add_argument("--allow-safe-bootstrap", action="store_true")
    parser.add_argument("--active-remediation", action="store_true")
    parser.add_argument("--allow-runtime-actions", action="store_true")
    args = parser.parse_args()
    runtime_actions_env = _truthy_env(os.environ.get(DEFAULT_RUNTIME_ACTIONS_ENV, "0"))
    runtime_actions_requested = bool(args.allow_runtime_actions or runtime_actions_env)
    active_remediation_env = _truthy_env(os.environ.get(DEFAULT_ACTIVE_REMEDIATION_ENV, "0"))
    requested_active_remediation = bool(args.active_remediation or active_remediation_env)
    requested_allow_safe_archive = bool(args.allow_safe_archive)
    requested_allow_safe_bootstrap = bool(args.allow_safe_bootstrap)
    simplification_freeze_active = _simplification_freeze_active()

    if args.continuous:
        session_loops = 0
        while True:
            activation_payload = active_home_time_payload(ROOT)
            if not activation_payload:
                time.sleep(max(args.idle_interval_seconds, 1.0))
                continue
            result = monitor_home_time(
                root=ROOT,
                iterations=1,
                interval_seconds=max(args.interval_seconds, 0.1),
                allow_safe_archive=requested_allow_safe_archive,
                allow_safe_bootstrap=requested_allow_safe_bootstrap,
                active_remediation=requested_active_remediation,
            )
            session_loops += 1
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "mode": "continuous",
                        "session_loops": session_loops,
                        "runtime_actions_requested": runtime_actions_requested,
                        "runtime_actions_enabled": False,
                        "simplification_freeze_active": simplification_freeze_active,
                        "observer_only_enforced": True,
                        "last_result": result,
                    },
                    ensure_ascii=True,
                )
            )
            time.sleep(max(args.interval_seconds, 0.1))

    iterations = 1 if args.once else max(int(args.iterations), 1)
    result = monitor_home_time(
        root=ROOT,
        iterations=iterations,
        interval_seconds=max(args.interval_seconds, 0.1),
        allow_safe_archive=requested_allow_safe_archive,
        allow_safe_bootstrap=requested_allow_safe_bootstrap,
        active_remediation=requested_active_remediation,
    )
    result["runtime_actions_requested"] = runtime_actions_requested
    result["runtime_actions_enabled"] = False
    result["simplification_freeze_active"] = simplification_freeze_active
    result["observer_only_enforced"] = True
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
