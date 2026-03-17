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

try:
    from scripts.tools.home_time_common import (
        LOG_PATH,
        HomeTimeError,
        active_home_time_payload,
        active_h_python_processes,
        active_h_launcher_processes,
        append_jsonl,
        collect_home_time_snapshot,
        current_run_archive_candidate,
        norm,
        utc_now,
        write_diagnostic_snapshot,
    )
except ModuleNotFoundError:
    from home_time_common import (
        LOG_PATH,
        HomeTimeError,
        active_home_time_payload,
        active_h_python_processes,
        active_h_launcher_processes,
        append_jsonl,
        collect_home_time_snapshot,
        current_run_archive_candidate,
        norm,
        utc_now,
        write_diagnostic_snapshot,
    )


def _attempt_safe_archive(*, root: Path, session_id: str, snapshot: dict[str, object], log_path: Path) -> dict[str, object]:
    candidate = current_run_archive_candidate(snapshot, root=root)
    run_id = norm(candidate.get("run_id", ""))
    if not candidate.get("eligible", False):
        return {
            "status": "skipped",
            "reason": "not_archive_eligible",
            "candidate": candidate,
        }
    command = [
        "python",
        str(root / "scripts" / "tools" / "archive_failed_H_run.py"),
        "--run-id",
        run_id,
        "--archive-reason",
        "home_time_monitor_safe_archive",
    ]
    completed = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=60,
    )
    stdout = norm(completed.stdout)
    stderr = norm(completed.stderr)
    result = {
        "status": "ok" if int(completed.returncode) == 0 else "failed",
        "run_id": run_id,
        "rc": int(completed.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "candidate": candidate,
    }
    append_jsonl(
        log_path,
        {
            "event": "home_time_monitor_safe_archive",
            "check_utc": utc_now(),
            "session_id": session_id,
            "run_id": run_id,
            "rc": int(completed.returncode),
            "stdout": stdout,
            "stderr": stderr,
        },
    )
    return result


def _run_schtasks(task_name: str, action: str, *, timeout: int = 30) -> dict[str, object]:
    completed = subprocess.run(
        ["schtasks", action, "/TN", task_name],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    return {
        "rc": int(completed.returncode),
        "stdout": norm(completed.stdout),
        "stderr": norm(completed.stderr),
    }


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


def _attempt_safe_bootstrap(*, root: Path, session_id: str, snapshot: dict[str, object], log_path: Path) -> dict[str, object]:
    candidate = current_run_archive_candidate(snapshot, root=root)
    run_id = norm(candidate.get("run_id", ""))
    task_name = norm(os.environ.get("HOME_TIME_H_TASK_NAME", DEFAULT_H_TASK_NAME)) or DEFAULT_H_TASK_NAME
    archive_path = root / "out" / "systems" / "H" / "live" / f"H_failed_run_archived.{run_id}.json"
    launcher_processes = active_h_launcher_processes(root)
    active_h_processes = candidate.get("active_h_processes", [])
    if not isinstance(active_h_processes, list):
        active_h_processes = []
    if launcher_processes or active_h_processes or not run_id or not archive_path.exists():
        return {
            "status": "skipped",
            "reason": "not_bootstrap_eligible",
            "run_id": run_id,
            "archive_path": str(archive_path),
            "launcher_processes": launcher_processes,
            "active_h_processes": active_h_processes,
        }

    task_state_before = _task_state(task_name)
    stale_scheduler_running = task_state_before.lower() == "running"
    end_result: dict[str, object] = {"rc": 0, "stdout": "", "stderr": "", "skipped": True}
    if stale_scheduler_running:
        end_result = _run_schtasks(task_name, "/End", timeout=30)

    run_result = _run_schtasks(task_name, "/Run", timeout=30)
    time.sleep(3.0)
    post_snapshot = collect_home_time_snapshot(root)
    post_launcher = active_h_launcher_processes(root)
    post_launcher_pid = norm(post_snapshot.get("H_launcher_owner_pid", ""))
    runtime_status = post_snapshot.get("runtime_status_snapshot", {})
    runtime_pid = norm(runtime_status.get("pid", "")) if isinstance(runtime_status, dict) else ""
    bootstrap_verified = bool(post_launcher) or _pid_is_alive(post_launcher_pid) or _pid_is_alive(runtime_pid)
    result = {
        "status": "ok" if run_result.get("rc", 1) == 0 and bootstrap_verified else "failed",
        "run_id": run_id,
        "rc": int(run_result.get("rc", 1)),
        "stdout": norm(run_result.get("stdout", "")),
        "stderr": norm(run_result.get("stderr", "")),
        "archive_path": str(archive_path),
        "task_name": task_name,
        "task_state_before": task_state_before,
        "stale_scheduler_running_detected": stale_scheduler_running,
        "end_rc": int(end_result.get("rc", 0)) if isinstance(end_result, dict) else 0,
        "end_stdout": norm(end_result.get("stdout", "")) if isinstance(end_result, dict) else "",
        "end_stderr": norm(end_result.get("stderr", "")) if isinstance(end_result, dict) else "",
        "bootstrap_verified": bootstrap_verified,
        "post_launcher_owner_pid": post_launcher_pid,
    }
    append_jsonl(
        log_path,
        {
            "event": "home_time_monitor_safe_bootstrap",
            "check_utc": utc_now(),
            "session_id": session_id,
            "run_id": run_id,
            "rc": int(run_result.get("rc", 1)),
            "stdout": norm(run_result.get("stdout", "")),
            "stderr": norm(run_result.get("stderr", "")),
            "archive_path": str(archive_path),
            "task_name": task_name,
            "task_state_before": task_state_before,
            "stale_scheduler_running_detected": stale_scheduler_running,
            "end_rc": int(end_result.get("rc", 0)) if isinstance(end_result, dict) else 0,
            "end_stdout": norm(end_result.get("stdout", "")) if isinstance(end_result, dict) else "",
            "end_stderr": norm(end_result.get("stderr", "")) if isinstance(end_result, dict) else "",
            "bootstrap_verified": bootstrap_verified,
            "post_launcher_owner_pid": post_launcher_pid,
        },
    )
    return result


def _attempt_scheduler_recycle(*, root: Path, session_id: str, log_path: Path) -> dict[str, object]:
    task_name = norm(os.environ.get("HOME_TIME_H_TASK_NAME", DEFAULT_H_TASK_NAME)) or DEFAULT_H_TASK_NAME
    state_before = _task_state(task_name)
    end_result: dict[str, object] = {"rc": 0, "stdout": "", "stderr": "", "skipped": True}
    if state_before.lower() == "running":
        end_result = _run_schtasks(task_name, "/End", timeout=30)
    run_result = _run_schtasks(task_name, "/Run", timeout=30)
    time.sleep(3.0)
    launcher_processes = active_h_launcher_processes(root)
    h_python_processes = active_h_python_processes(root)
    post_snapshot = collect_home_time_snapshot(root)
    runtime_status = post_snapshot.get("runtime_status_snapshot", {})
    runtime_pid = norm(runtime_status.get("pid", "")) if isinstance(runtime_status, dict) else ""
    launcher_pid = norm(post_snapshot.get("H_launcher_owner_pid", ""))
    verified = bool(launcher_processes) or bool(h_python_processes) or _pid_is_alive(launcher_pid) or _pid_is_alive(runtime_pid)
    result = {
        "status": "ok" if run_result.get("rc", 1) == 0 and verified else "failed",
        "task_name": task_name,
        "task_state_before": state_before,
        "rc": int(run_result.get("rc", 1)),
        "stdout": norm(run_result.get("stdout", "")),
        "stderr": norm(run_result.get("stderr", "")),
        "end_rc": int(end_result.get("rc", 0)) if isinstance(end_result, dict) else 0,
        "end_stdout": norm(end_result.get("stdout", "")) if isinstance(end_result, dict) else "",
        "end_stderr": norm(end_result.get("stderr", "")) if isinstance(end_result, dict) else "",
        "verified": verified,
        "post_launcher_owner_pid": norm(post_snapshot.get("H_launcher_owner_pid", "")),
    }
    append_jsonl(
        log_path,
        {
            "event": "home_time_monitor_scheduler_recycle",
            "check_utc": utc_now(),
            "session_id": session_id,
            "task_name": task_name,
            "task_state_before": state_before,
            "rc": int(run_result.get("rc", 1)),
            "stdout": norm(run_result.get("stdout", "")),
            "stderr": norm(run_result.get("stderr", "")),
            "end_rc": int(end_result.get("rc", 0)) if isinstance(end_result, dict) else 0,
            "end_stdout": norm(end_result.get("stdout", "")) if isinstance(end_result, dict) else "",
            "end_stderr": norm(end_result.get("stderr", "")) if isinstance(end_result, dict) else "",
            "verified": verified,
            "post_launcher_owner_pid": norm(post_snapshot.get("H_launcher_owner_pid", "")),
        },
    )
    return result


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
                "runtime_run_id": norm(snapshot.get("runtime_status_snapshot", {}).get("run_id", "")) if isinstance(snapshot.get("runtime_status_snapshot", {}), dict) else "",
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
            if not active_remediation:
                append_jsonl(
                    log_path,
                    {
                        "event": "home_time_monitor_observer_only",
                        "check_utc": utc_now(),
                        "session_id": session_id,
                        "action": "remediation_skipped",
                        "reason": "observer_only_mode",
                    },
                )
            elif allow_safe_archive:
                remediation = _attempt_safe_archive(
                    root=root,
                    session_id=session_id,
                    snapshot=snapshot,
                    log_path=log_path,
                )
                remediations.append(remediation)
                if remediation.get("status") == "ok":
                    remediation_payload = {
                        "diagnostic_type": "home_time_monitor_safe_archive",
                        "diagnostic_utc": utc_now(),
                        "session_id": session_id,
                        "anomalies": anomalies,
                        "remediation": remediation,
                    }
                    remediation_path = write_diagnostic_snapshot(
                        root,
                        remediation_payload,
                        prefix="H_home_time_monitor_remediation",
                    )
                    diagnostics_written.append(str(remediation_path))
                    if allow_safe_bootstrap:
                        post_archive_snapshot = collect_home_time_snapshot(root)
                        bootstrap = _attempt_safe_bootstrap(
                            root=root,
                            session_id=session_id,
                            snapshot=post_archive_snapshot,
                            log_path=log_path,
                        )
                        remediations.append(bootstrap)
                elif allow_safe_bootstrap and (
                    "scheduler_running_without_h_owner" in anomalies or "runtime_error_mode" in anomalies
                ):
                    recycle = _attempt_scheduler_recycle(
                        root=root,
                        session_id=session_id,
                        log_path=log_path,
                    )
                    remediations.append(recycle)
            elif allow_safe_bootstrap:
                if "scheduler_running_without_h_owner" in anomalies or "runtime_error_mode" in anomalies:
                    recycle = _attempt_scheduler_recycle(
                        root=root,
                        session_id=session_id,
                        log_path=log_path,
                    )
                    remediations.append(recycle)
                else:
                    bootstrap = _attempt_safe_bootstrap(
                        root=root,
                        session_id=session_id,
                        snapshot=snapshot,
                        log_path=log_path,
                    )
                    remediations.append(bootstrap)
        if index + 1 < max(iterations, 1):
            time.sleep(max(interval_seconds, 0.1))

    return {
        "status": "ok",
        "session_id": session_id,
        "checks_run": checks_run,
        "anomalies_seen": anomalies_seen,
        "diagnostics_written": diagnostics_written,
        "remediations": remediations,
        "active_remediation": bool(active_remediation),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor an active home time session without mutating H runtime ownership.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--idle-interval-seconds", type=float, default=60.0)
    parser.add_argument("--allow-safe-archive", action="store_true")
    parser.add_argument("--allow-safe-bootstrap", action="store_true")
    parser.add_argument("--active-remediation", action="store_true")
    args = parser.parse_args()
    env_active = norm(os.environ.get(DEFAULT_ACTIVE_REMEDIATION_ENV, "0")) == "1"
    active_remediation = bool(args.active_remediation or env_active)

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
                allow_safe_archive=bool(args.allow_safe_archive),
                allow_safe_bootstrap=bool(args.allow_safe_bootstrap),
                active_remediation=active_remediation,
            )
            session_loops += 1
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "mode": "continuous",
                        "session_loops": session_loops,
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
        allow_safe_archive=bool(args.allow_safe_archive),
        allow_safe_bootstrap=bool(args.allow_safe_bootstrap),
        active_remediation=active_remediation,
    )
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
