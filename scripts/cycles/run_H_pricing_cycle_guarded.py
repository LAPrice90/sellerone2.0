from __future__ import annotations

import os
import sys
import time
import traceback
import signal
import faulthandler
import threading
import subprocess
import json
from pathlib import Path

# IMPORTANT:
# This wrapper does NOT change your cycle logic.
# It forces unbuffered output + writes a guaranteed traceback file if anything goes wrong,
# even if your normal logger never flushes.


def _resolve_root() -> Path:
    # This file is scripts/cycles/run_H_pricing_cycle_guarded.py
    # Repo root is two parents up from scripts/
    return Path(__file__).resolve().parents[2]


def _live_dir(root: Path) -> Path:
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    return live


def _write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")
    except BaseException:
        pass


def _append_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(text)
    except BaseException:
        pass


def _start_core_exit_capture(*, root: Path, live: Path, child_pid: int, heartbeat: Path) -> subprocess.Popen | None:
    capture_script = root / "scripts" / "tools" / "h_capture_process_exit.ps1"
    if not capture_script.exists():
        _append_text(
            heartbeat,
            (
                "core_exit_capture_skip "
                f"pid={child_pid} "
                f"reason=missing_script path={capture_script}\n"
            ),
        )
        return None
    try:
        if os.name == "nt":
            proc = subprocess.Popen(
                [
                    "cmd.exe",
                    "/c",
                    "start",
                    "",
                    "/min",
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(capture_script),
                    "-TargetPid",
                    str(child_pid),
                    "-LiveDir",
                    str(live),
                ],
                cwd=str(root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc = subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(capture_script),
                    "-TargetPid",
                    str(child_pid),
                    "-LiveDir",
                    str(live),
                ],
                cwd=str(root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except BaseException as exc:
        _append_text(
            heartbeat,
            (
                "core_exit_capture_start_failed "
                f"pid={child_pid} "
                f"error={type(exc).__name__}:{exc}\n"
            ),
        )
        return None
    _append_text(
        heartbeat,
        (
            "core_exit_capture_started "
            f"pid={child_pid} "
            f"monitor_pid={proc.pid} "
            f"script={capture_script}\n"
        ),
    )
    return proc


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return str(fh.readline() or "").strip()
    except BaseException:
        return ""


def _read_publish_proof_details(path: Path, expected_run_id: str = "") -> dict[str, str]:
    expected_run_id = str(expected_run_id or "").strip()
    publish_marker_path = path.parent / "H_cycle_last_publish_run_id.txt"
    details = {
        "selected_run_id": "",
        "selected_source": "",
        "publish_marker_path": str(publish_marker_path),
        "publish_marker_run_id": "",
        "publish_info_path": str(path),
        "publish_info_run_id": "",
        "expected_run_id": expected_run_id,
    }
    try:
        if publish_marker_path.exists():
            with publish_marker_path.open("r", encoding="utf-8", errors="replace") as fh:
                marker_run_id = str(fh.readline() or "").strip()
                if marker_run_id:
                    details["publish_marker_run_id"] = marker_run_id
    except BaseException:
        return details
    try:
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for raw_line in fh:
                    line = str(raw_line or "").strip()
                    if not line or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if str(key or "").strip() == "run_id":
                        details["publish_info_run_id"] = str(value or "").strip()
                        break
    except BaseException:
        return details
    marker_run_id = str(details.get("publish_marker_run_id", "") or "").strip()
    info_run_id = str(details.get("publish_info_run_id", "") or "").strip()
    if expected_run_id:
        if marker_run_id == expected_run_id:
            details["selected_run_id"] = marker_run_id
            details["selected_source"] = "publish_run_file_expected_match"
        elif info_run_id == expected_run_id:
            details["selected_run_id"] = info_run_id
            details["selected_source"] = "publish_info_file_expected_match"
    elif marker_run_id:
        details["selected_run_id"] = marker_run_id
        details["selected_source"] = "publish_run_file"
    elif info_run_id:
        details["selected_run_id"] = info_run_id
        details["selected_source"] = "publish_info_file"
    return details


def _read_publish_proof_run_id(path: Path, expected_run_id: str = "") -> str:
    return _read_publish_proof_details(path, expected_run_id=expected_run_id).get("selected_run_id", "")


def _read_cycle_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except BaseException:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        out[str(key)] = str(value or "").strip()
    return out


def _publish_attempt_state_for_run(state: dict[str, str], run_id: str) -> dict[str, str]:
    run_id_norm = str(run_id or "").strip()
    publish_started_for_run = (
        run_id_norm
        and str(state.get("phase1_publish_started_run_id", "")).strip() == run_id_norm
    )
    publish_completed_for_run = (
        run_id_norm
        and str(state.get("phase1_observation_publish_run_id", "")).strip() == run_id_norm
        and str(state.get("phase1_publish_completed", "")).strip() == "1"
    )
    publish_entry_for_run = (
        run_id_norm
        and str(state.get("phase1_publish_entry_run_id", "")).strip() == run_id_norm
        and str(state.get("phase1_publish_entry_status", "")).strip() == "entered"
    )
    transition_run_id = str(state.get("phase1_post_pilot_transition_run_id", "")).strip()
    transition_status_raw = str(state.get("phase1_post_pilot_transition_status", "")).strip()
    transition_status = transition_status_raw if (run_id_norm and transition_run_id == run_id_norm) else ""
    post_pilot_transition_for_run = bool(
        run_id_norm
        and transition_run_id == run_id_norm
        and transition_status in {"pilot_completed", "publish_entered"}
    )
    intel_started_for_run = (
        run_id_norm
        and str(state.get("phase1_intel_started_run_id", "")).strip() == run_id_norm
    )
    publish_attempted_for_run = bool(publish_started_for_run or publish_completed_for_run)
    return {
        "publish_attempted_for_run": "1" if publish_attempted_for_run else "0",
        "publish_started_for_run": "1" if publish_started_for_run else "0",
        "publish_completed_for_run": "1" if publish_completed_for_run else "0",
        "publish_entry_for_run": "1" if publish_entry_for_run else "0",
        "post_pilot_transition_for_run": "1" if post_pilot_transition_for_run else "0",
        "post_pilot_transition_status": transition_status,
        "post_pilot_transition_status_raw": transition_status_raw,
        "post_pilot_transition_run_matches": "1" if (run_id_norm and transition_run_id == run_id_norm) else "0",
        "intel_started_for_run": "1" if intel_started_for_run else "0",
    }


def _clear_terminal_run_in_progress(live: Path, run_id: str) -> tuple[bool, str]:
    run_id_norm = str(run_id or "").strip()
    run_in_progress_path = live / "H_run_in_progress.txt"
    if not run_id_norm:
        return False, "missing_run_id"
    marker = _read_first_line(run_in_progress_path)
    if marker != run_id_norm:
        return False, "marker_not_current_run"
    try:
        run_in_progress_path.unlink(missing_ok=True)
    except BaseException as exc:
        return False, f"unlink_failed_{type(exc).__name__}"
    return (not run_in_progress_path.exists()), "cleared" if not run_in_progress_path.exists() else "unlink_failed"


def _write_runtime_status_from_wrapper(
    live: Path,
    *,
    mode: str,
    run_id: str = "",
    stage: str = "",
    detail: str = "",
    error: str = "",
    interruption_class: str = "",
    interruption_signal: str = "",
    wrapper_exit_category: str = "",
) -> None:
    utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    payload = {
        "utc": utc,
        "pid": str(os.getpid()),
        "run_id": str(run_id or "").strip(),
        "mode": str(mode or "").strip().upper() or "ERROR",
        "stage": str(stage or "").strip(),
        "detail": str(detail or "").strip(),
        "wake_at_utc": "",
        "next_due_sku": "",
        "next_due_seconds": "",
        "publish_status": "",
        "error": str(error or "").strip(),
        "interruption_class": str(interruption_class or "").strip(),
        "interruption_signal": str(interruption_signal or "").strip(),
        "wrapper_exit_category": str(wrapper_exit_category or "").strip(),
    }
    path = live / "H_runtime_status.json"
    _write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    lines = [
        f"utc={payload['utc']}",
        f"pid={payload['pid']}",
        f"run_id={payload['run_id']}",
        f"mode={payload['mode']}",
        f"stage={payload['stage']}",
    ]
    if payload["detail"]:
        lines.append(f"detail={payload['detail']}")
    if payload["error"]:
        lines.append(f"error={payload['error']}")
    if payload["interruption_class"]:
        lines.append(f"interruption_class={payload['interruption_class']}")
    if payload["interruption_signal"]:
        lines.append(f"interruption_signal={payload['interruption_signal']}")
    if payload["wrapper_exit_category"]:
        lines.append(f"wrapper_exit_category={payload['wrapper_exit_category']}")
    _write_text(live / "H_runtime_status.txt", "\n".join(lines) + "\n")
    phase_parts = [payload["mode"]]
    if payload["stage"]:
        phase_parts.append(f"stage={payload['stage']}")
    if payload["detail"]:
        phase_parts.append(f"detail={payload['detail']}")
    _write_text(live / "H_pricing_cycle.PHASE.txt", " ".join(phase_parts) + "\n")


def _detect_wrapper_interruption(
    *,
    heartbeat: Path,
    exit_status: Path,
    rc: int,
) -> tuple[bool, str, str]:
    combined = ""
    for path in (heartbeat, exit_status):
        try:
            if path.exists():
                combined += "\n" + path.read_text(encoding="utf-8", errors="replace")
        except BaseException:
            continue
    combined_lower = combined.lower()
    signal_name = ""
    try:
        import re
        signal_match = re.search(r"signum=(SIG[A-Z0-9]+)", combined)
        if signal_match:
            signal_name = str(signal_match.group(1) or "").strip()
    except BaseException:
        signal_name = ""
    if rc == 130:
        return True, signal_name or "SIGINT", "keyboard_interrupt_rc130"
    if signal_name:
        return True, signal_name, "signal_interruption"
    if "interruption_class=true" in combined_lower or "interruption_class=1" in combined_lower:
        return True, signal_name, "interruption_marker"
    if "external_interruption" in combined_lower:
        return True, signal_name, "external_interruption"
    if "parent_owner_lost" in combined_lower:
        return True, signal_name, "parent_owner_lost"
    return False, signal_name, "normal_exit"


def _read_phase1_intel_boundary_state(live: Path, run_id: str) -> dict[str, str]:
    if not run_id:
        return {}
    path = live / f"phase1_intel_alignment.boundary.{run_id}.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except BaseException:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {"boundary_state_path": str(path)}
    for key, value in raw.items():
        out[str(key)] = str(value or "").strip()
    return out


def _boundary_is_unresolved(status: str) -> bool:
    return str(status or "").strip().lower() in {"active", "unresolved_parent_exit", "stale_or_orphaned"}


def _pid_alive(pid_text: str) -> bool:
    try:
        pid = int(str(pid_text or "").strip())
    except BaseException:
        return False
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            kernel32 = __import__("ctypes").windll.kernel32
            synchronize = 0x00100000
            query_limited = 0x1000
            handle = kernel32.OpenProcess(synchronize | query_limited, False, pid)
            if not handle:
                return False
            try:
                wait_timeout = 0x00000102
                return int(kernel32.WaitForSingleObject(handle, 0)) == wait_timeout
            finally:
                kernel32.CloseHandle(handle)
        os.kill(pid, 0)
        return True
    except BaseException:
        return False


def _cleanup_phase1_intel_orphan(boundary: dict[str, str]) -> tuple[bool, str]:
    child_pid = boundary.get("child_pid", "")
    if not _pid_alive(child_pid):
        return False, ""
    try:
        subprocess.run(
            ["taskkill", "/PID", str(int(child_pid)), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except BaseException as exc:
        return False, f"{type(exc).__name__}:{exc}"
    return True, ""


def _phase1_intel_parent_exit_code(boundary: dict[str, str]) -> str:
    reason = str(boundary.get("state_reason", "") or boundary.get("reason", "")).strip().lower()
    status = str(boundary.get("status", "")).strip().lower()
    if reason == "parent_owner_lost":
        return "PHASE1_INTEL_PARENT_EXIT_DURING_WAIT"
    if status in {"active", "unresolved_parent_exit", "stale_or_orphaned"}:
        return "PHASE1_INTEL_PARENT_EXIT_DURING_WAIT"
    return "child_rc"


def _read_phase1_intel_result_payload(live: Path, run_id: str) -> dict[str, str]:
    if not run_id:
        return {}
    pattern = f"phase1_intel_alignment.result.{run_id}.*.json"
    candidates = sorted(live.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
    for path in candidates:
        try:
            raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except BaseException:
            continue
        if not isinstance(raw, dict):
            continue
        out = {"result_path": str(path)}
        for key, value in raw.items():
            out[str(key)] = str(value or "").strip()
        return out
    return {}


def _result_implies_parent_loss(result_payload: dict[str, str]) -> bool:
    error_type = str(result_payload.get("phase1_daily_intel_alignment_error_type", "")).strip().lower()
    error_text = str(result_payload.get("phase1_daily_intel_alignment_error", "")).strip().lower()
    if error_type == "parentownerlost":
        return True
    return "parent_owner_lost" in error_text


def _wait_for_boundary_resolution(
    *,
    live: Path,
    run_id: str,
    heartbeat: Path,
    initial_boundary: dict[str, str],
    max_wait_seconds: float = 3.0,
    poll_seconds: float = 0.25,
) -> tuple[dict[str, str], dict[str, str], bool]:
    if not run_id:
        return initial_boundary, {}, False
    boundary = dict(initial_boundary)
    result_payload = _read_phase1_intel_result_payload(live, run_id)
    if _phase1_intel_parent_exit_code(boundary) != "child_rc" or _result_implies_parent_loss(result_payload):
        return boundary, result_payload, False
    if not _boundary_is_unresolved(boundary.get("status", "")):
        return boundary, result_payload, False
    started = time.time()
    rechecked = False
    _append_text(
        heartbeat,
        (
            "phase1_intel_wrapper_recheck "
            f"run_id={run_id} "
            f"initial_boundary_status={boundary.get('status', '') or 'missing'} "
            f"initial_reason={boundary.get('state_reason', boundary.get('reason', '')) or 'missing'} "
            f"max_wait_seconds={max_wait_seconds:.2f}\n"
        ),
    )
    while (time.time() - started) < max_wait_seconds:
        time.sleep(poll_seconds)
        rechecked = True
        boundary = _read_phase1_intel_boundary_state(live, run_id)
        result_payload = _read_phase1_intel_result_payload(live, run_id)
        if _phase1_intel_parent_exit_code(boundary) != "child_rc":
            break
        if _result_implies_parent_loss(result_payload):
            break
        if not _boundary_is_unresolved(boundary.get("status", "")) and result_payload:
            break
    _append_text(
        heartbeat,
        (
            "phase1_intel_wrapper_recheck_done "
            f"run_id={run_id} "
            f"rechecked={'1' if rechecked else '0'} "
            f"boundary_status={boundary.get('status', '') or 'missing'} "
            f"boundary_reason={boundary.get('state_reason', boundary.get('reason', '')) or 'missing'} "
            f"result_path={result_payload.get('result_path', '')} "
            f"result_error_type={result_payload.get('phase1_daily_intel_alignment_error_type', '')} "
            f"result_error={result_payload.get('phase1_daily_intel_alignment_error', '')}\n"
        ),
    )
    return boundary, result_payload, rechecked


def _latest_matching_path(live: Path, pattern: str) -> Path | None:
    candidates = sorted(
        live.glob(pattern),
        key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        reverse=True,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_pilot_handoff_evidence(live: Path, run_id: str) -> dict[str, str]:
    evidence: dict[str, str] = {
        "marker_path": "",
        "marker_exists": "0",
        "marker_status": "",
        "marker_reason": "",
        "marker_run_id": "",
        "marker_result_ok": "",
        "result_path": "",
        "result_exists": "0",
        "result_size": "0",
        "stderr_path": "",
        "stderr_mtime_utc": "",
        "stderr_age_seconds": "",
    }
    if not run_id:
        return evidence
    marker_path = _latest_matching_path(live, f"phase1_pilot_step.complete.{run_id}.*.json")
    if marker_path is not None:
        evidence["marker_path"] = str(marker_path)
        evidence["marker_exists"] = "1"
        try:
            marker_raw = json.loads(marker_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(marker_raw, dict):
                evidence["marker_status"] = str(marker_raw.get("status", "") or "").strip().lower()
                evidence["marker_reason"] = str(marker_raw.get("reason", "") or "").strip()
                evidence["marker_run_id"] = str(marker_raw.get("run_id", "") or "").strip()
                evidence["marker_result_ok"] = str(marker_raw.get("result_ok", "") or "").strip().lower()
        except BaseException as exc:
            evidence["marker_status"] = "invalid_json"
            evidence["marker_reason"] = f"{type(exc).__name__}:{exc}"
    result_path = _latest_matching_path(live, f"phase1_pilot_step.result.{run_id}.*.json")
    if result_path is not None:
        evidence["result_path"] = str(result_path)
        evidence["result_exists"] = "1"
        try:
            evidence["result_size"] = str(int(result_path.stat().st_size))
        except BaseException:
            evidence["result_size"] = "0"
    stderr_path = _latest_matching_path(live, f"phase1_pilot_step.stderr.{run_id}.*.log")
    if stderr_path is not None:
        evidence["stderr_path"] = str(stderr_path)
        try:
            stderr_mtime = float(stderr_path.stat().st_mtime)
            evidence["stderr_mtime_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stderr_mtime))
            evidence["stderr_age_seconds"] = f"{max(time.time() - stderr_mtime, 0.0):.2f}"
        except BaseException:
            evidence["stderr_mtime_utc"] = ""
            evidence["stderr_age_seconds"] = ""
    return evidence


def _wait_for_pilot_handoff_evidence(
    *,
    live: Path,
    run_id: str,
    heartbeat: Path,
    max_wait_seconds: float,
    poll_seconds: float = 1.0,
) -> tuple[dict[str, str], bool]:
    def _is_terminal_marker(e: dict[str, str]) -> bool:
        if e.get("marker_exists", "0") != "1":
            return False
        status = str(e.get("marker_status", "") or "").strip().lower()
        if status in {"", "started", "running"}:
            return False
        return True

    evidence = _read_pilot_handoff_evidence(live, run_id)
    if _is_terminal_marker(evidence):
        return evidence, False
    started = time.time()
    rechecked = False
    _append_text(
        heartbeat,
        (
            "phase1_pilot_wrapper_recheck "
            f"run_id={run_id} "
            f"max_wait_seconds={max_wait_seconds:.2f}\n"
        ),
    )
    while (time.time() - started) < max_wait_seconds:
        time.sleep(max(poll_seconds, 0.1))
        rechecked = True
        evidence = _read_pilot_handoff_evidence(live, run_id)
        if _is_terminal_marker(evidence):
            break
    _append_text(
        heartbeat,
        (
            "phase1_pilot_wrapper_recheck_done "
            f"run_id={run_id} "
            f"rechecked={'1' if rechecked else '0'} "
            f"marker_exists={evidence.get('marker_exists', '0')} "
            f"marker_status={evidence.get('marker_status', '') or 'missing'} "
            f"marker_run_id={evidence.get('marker_run_id', '')} "
            f"result_exists={evidence.get('result_exists', '0')} "
            f"result_size={evidence.get('result_size', '0')} "
            f"stderr_path={evidence.get('stderr_path', '')} "
            f"stderr_mtime_utc={evidence.get('stderr_mtime_utc', '')} "
            f"stderr_age_seconds={evidence.get('stderr_age_seconds', '')}\n"
        ),
    )
    return evidence, rechecked


def _classify_pilot_handoff_terminal(run_id: str, evidence: dict[str, str]) -> tuple[str, str]:
    marker_exists = evidence.get("marker_exists", "0") == "1"
    if not marker_exists:
        try:
            stderr_age_seconds = float(str(evidence.get("stderr_age_seconds", "") or "nan"))
        except BaseException:
            stderr_age_seconds = float("nan")
        if stderr_age_seconds == stderr_age_seconds and stderr_age_seconds <= 60.0:
            return "PHASE1_PILOT_STILL_ACTIVE_UNRESOLVED", "pilot_stderr_recent_activity_no_terminal_marker"
        return "PHASE1_PILOT_TERMINAL_EVIDENCE_MISSING", "pilot_completion_marker_missing_after_wait"
    marker_status = str(evidence.get("marker_status", "") or "").strip().lower()
    marker_run_id = str(evidence.get("marker_run_id", "") or "").strip()
    marker_result_ok = str(evidence.get("marker_result_ok", "") or "").strip().lower()
    result_size = int(str(evidence.get("result_size", "0") or "0") or "0")
    if marker_status != "success":
        return "PHASE1_PILOT_TERMINAL_FAILURE", "pilot_terminal_failure_marker"
    if marker_run_id != str(run_id or "").strip():
        return "PHASE1_PILOT_COMPLETION_CONTRACT_FAILED", "pilot_completion_marker_run_mismatch"
    if marker_result_ok not in {"1", "true"}:
        return "PHASE1_PILOT_COMPLETION_CONTRACT_FAILED", "pilot_completion_marker_result_not_ok"
    if result_size <= 0:
        return "PHASE1_PILOT_COMPLETION_CONTRACT_FAILED", "pilot_result_payload_missing_after_success_marker"
    return "PHASE1_PILOT_PARENT_EXIT_DURING_WAIT", "pilot_success_after_parent_exit"


def _truthy_env(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    root = _resolve_root()
    live = _live_dir(root)
    run_started_monotonic = time.monotonic()
    final_rc: int | None = None
    interruption_class = False
    interruption_signal = ""
    wrapper_exit_category = "normal_exit"

    # Make Python behave like a "real service" process
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["PYTHONFAULTHANDLER"] = "1"

    crash_log = live / "H_pricing_cycle.CRASH.log"
    heartbeat = live / "H_pricing_cycle.HEARTBEAT.txt"
    exit_status = live / "H_pricing_cycle.EXIT_STATUS.txt"
    phase = live / "H_pricing_cycle.PHASE.txt"
    current_run_id_path = live / "H_cycle_current_run_id.txt"
    finalized_run_id_path = live / "H_last_finalized_run_id.txt"
    publish_info_path = live / "H_cycle_last_publish_info.txt"
    cycle_state_path = live / "h_pricing_cycle_state.json"
    fault_log = live / "H_pricing_cycle.FAULT.log"
    _fault_fh = fault_log.open("a", encoding="utf-8", errors="replace")
    faulthandler.enable(_fault_fh)
    diagnostic_mode = os.environ.get("H_GUARD_DIAGNOSTIC_MODE", "0").strip() == "1"
    ignore_keyboard_interrupt = _truthy_env("H_GUARD_IGNORE_KEYBOARD_INTERRUPT", "1") and not diagnostic_mode
    if diagnostic_mode:
        # Diagnostic mode is intentionally noisy and can affect runtime behavior.
        faulthandler.dump_traceback_later(30, repeat=True, file=_fault_fh)

    # Heartbeat at process start
    pilot_mode = (os.environ.get("H_PHASE1_PILOT_MODE", "inline").strip().lower() or "inline")
    intel_mode = (os.environ.get("H_PHASE1_INTEL_MODE", "inline").strip().lower() or "inline")
    publish_mode = (os.environ.get("H_PHASE1_PUBLISH_MODE", "inline").strip().lower() or "inline")
    bisect_force_inline = "1" if os.environ.get("H_BISECT_FORCE_INLINE", "0").strip() == "1" else "0"
    stage_snapshot_refresh = "1" if os.environ.get("H_STAGE_SNAPSHOT_REFRESH", "1").strip() == "1" else "0"
    stage_item_offers = "1" if os.environ.get("H_STAGE_ITEM_OFFERS", "1").strip() == "1" else "0"
    stage_phase1_pilot = "1" if os.environ.get("H_STAGE_PHASE1_PILOT", "1").strip() == "1" else "0"
    stage_phase1_intel = "1" if os.environ.get("H_STAGE_PHASE1_INTEL", "1").strip() == "1" else "0"
    stage_phase1_publish = "1" if os.environ.get("H_STAGE_PHASE1_PUBLISH", "1").strip() == "1" else "0"
    _write_text(
        heartbeat,
        (
            f"START utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            f"argv={sys.argv!r}\n"
            f"MODE={'diagnostic' if diagnostic_mode else 'steady'}\n"
            f"PHASE=phase1_pilot({pilot_mode}) phase1_intel({intel_mode}) phase1_publish({publish_mode})\n"
            f"GUARD_DIAGNOSTIC_MODE={'1' if diagnostic_mode else '0'}\n"
            f"BISECT_FORCE_INLINE={bisect_force_inline}\n"
            f"STAGES snapshot_refresh={stage_snapshot_refresh} item_offers={stage_item_offers} "
            f"phase1_pilot={stage_phase1_pilot} phase1_intel={stage_phase1_intel} "
            f"phase1_publish={stage_phase1_publish}\n"
        ),
    )
    _write_text(
        exit_status,
        (
            f"START utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            f"status=running\n"
        ),
    )
    _write_runtime_status_from_wrapper(
        live,
        mode="RUNNING",
        stage="guard_wrapper",
        detail="wrapper_started",
        interruption_class="false",
        wrapper_exit_category="startup",
    )

    _real_os_exit = os._exit

    # Always record hard exits so launcher checks can catch non-graceful paths.
    def _patched_os_exit(code: int = 0) -> None:
        requested_rc = code
        try:
            rc = int(code)
        except Exception:
            rc = 1
        if rc == 0:
            rc = 3
        utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        fatal_line = (
            "FATAL hard_exit "
            "path=run_H_pricing_cycle_guarded._patched_os_exit "
            f"requested_rc={requested_rc!r} "
            f"forced_rc={rc}"
        )
        _append_text(
            heartbeat,
            (
                f"{fatal_line}\n"
                f"OS_EXIT utc={utc}\n"
                f"rc={rc}\n"
            ),
        )
        _write_text(
            exit_status,
            (
                f"{fatal_line}\n"
                f"OS_EXIT utc={utc}\n"
                f"rc={rc}\n"
            ),
        )
        _fault_fh.flush()
        print(fatal_line, file=sys.stderr, flush=True)
        raise SystemExit(rc)

    os._exit = _patched_os_exit  # type: ignore

    if diagnostic_mode:

        def _on_signal(signum, frame):  # type: ignore
            nonlocal interruption_class, interruption_signal, wrapper_exit_category
            interruption_class = True
            wrapper_exit_category = "signal_interruption"
            try:
                interruption_signal = signal.Signals(signum).name
            except Exception:
                interruption_signal = f"SIG{int(signum)}"
            _append_text(
                heartbeat,
                (
                    f"SIGNAL utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                    f"signum={signum}\n"
                ),
            )
            _fault_fh.flush()
            raise SystemExit(128 + int(signum))

        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)
    elif ignore_keyboard_interrupt:
        # In steady state, ignore external console-style interrupts so launcher loops stay resilient.
        def _ignore_signal(signum, _frame):  # type: ignore
            _append_text(
                heartbeat,
                (
                    f"SIGNAL utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                    f"signum={signum}\n"
                    "ignored=1\n"
                ),
            )

        for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, _ignore_signal)
            except Exception:
                continue

    stop_flag = threading.Event()

    if diagnostic_mode:
        def _ticker() -> None:
            while not stop_flag.is_set():
                _append_text(
                    heartbeat,
                    f"ALIVE utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n",
                )
                time.sleep(2)

        t = threading.Thread(target=_ticker, daemon=True)
        t.start()

    try:
        # Run the real cycle in a supervised child process so wrapper markers survive child crashes.
        child_cmd = [
            sys.executable,
            "-u",
            str(root / "scripts" / "cycles" / "run_H_pricing_cycle.py"),
            *sys.argv[1:],
        ]
        _write_text(phase, "before_real_main_subprocess\n")
        popen_kwargs = {"cwd": str(root)}
        if os.name == "nt":
            create_new_group = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            if create_new_group:
                popen_kwargs["creationflags"] = create_new_group
        child = subprocess.Popen(child_cmd, **popen_kwargs)
        _write_runtime_status_from_wrapper(
            live,
            mode="RUNNING",
            run_id=_read_first_line(current_run_id_path),
            stage="child_wait",
            detail=f"child_pid={child.pid}",
            interruption_class="false",
            wrapper_exit_category="child_wait",
        )
        _start_core_exit_capture(root=root, live=live, child_pid=child.pid, heartbeat=heartbeat)
        last_wait_status_write = time.monotonic()
        while True:
            try:
                rc = int(child.wait(timeout=1.0))
                break
            except subprocess.TimeoutExpired:
                if (time.monotonic() - last_wait_status_write) >= 15.0:
                    _write_runtime_status_from_wrapper(
                        live,
                        mode="RUNNING",
                        run_id=_read_first_line(current_run_id_path),
                        stage="child_wait",
                        detail=f"child_pid={child.pid}",
                        interruption_class="false",
                        wrapper_exit_category="child_wait",
                    )
                    last_wait_status_write = time.monotonic()
                continue
            except KeyboardInterrupt:
                interruption_class = True
                interruption_signal = "SIGINT"
                wrapper_exit_category = "keyboard_interrupt"
                utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                _append_text(
                    heartbeat,
                    (
                        f"SIGNAL utc={utc}\n"
                        "signum=SIGINT\n"
                        f"ignored={'1' if ignore_keyboard_interrupt else '0'}\n"
                    ),
                )
                if ignore_keyboard_interrupt:
                    continue
                raise
        _write_text(phase, "after_real_main_subprocess\n")
        stop_flag.set()
        utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        detected_interruption, detected_signal, detected_category = _detect_wrapper_interruption(
            heartbeat=heartbeat,
            exit_status=exit_status,
            rc=int(rc),
        )
        if detected_interruption:
            interruption_class = True
        if detected_signal:
            interruption_signal = detected_signal
        if detected_category:
            wrapper_exit_category = detected_category
        if rc == 0:
            current_run_id = _read_first_line(current_run_id_path)
            publish_proof = _read_publish_proof_details(
                publish_info_path,
                expected_run_id=current_run_id,
            )
            publish_run_id = publish_proof.get("selected_run_id", "")
            if current_run_id and publish_run_id == current_run_id:
                _write_text(finalized_run_id_path, current_run_id + "\n")
            else:
                rc = 3
                cycle_state = _read_cycle_state(cycle_state_path)
                publish_attempt_state = _publish_attempt_state_for_run(cycle_state, current_run_id)
                publish_attempted_for_run = publish_attempt_state.get("publish_attempted_for_run", "0") == "1"
                boundary = _read_phase1_intel_boundary_state(live, current_run_id)
                result_payload = {}
                boundary_status = boundary.get("status", "")
                boundary_reason = boundary.get("state_reason", boundary.get("reason", ""))
                _append_text(
                    heartbeat,
                    (
                        "phase1_intel_wrapper_finalize_check "
                        f"run_id={current_run_id} "
                        f"publish_run_id={publish_run_id} "
                        f"publish_attempted_for_run={publish_attempt_state.get('publish_attempted_for_run', '0')} "
                        f"publish_started_for_run={publish_attempt_state.get('publish_started_for_run', '0')} "
                        f"publish_completed_for_run={publish_attempt_state.get('publish_completed_for_run', '0')} "
                        f"publish_entry_for_run={publish_attempt_state.get('publish_entry_for_run', '0')} "
                        f"post_pilot_transition_for_run={publish_attempt_state.get('post_pilot_transition_for_run', '0')} "
                        f"post_pilot_transition_status={publish_attempt_state.get('post_pilot_transition_status', '') or 'missing'} "
                        f"intel_started_for_run={publish_attempt_state.get('intel_started_for_run', '0')} "
                        f"cycle_state_path={cycle_state_path} "
                        f"initial_boundary_status={boundary_status or 'missing'} "
                        f"initial_boundary_reason={boundary_reason or 'missing'}\n"
                    ),
                )
                boundary, result_payload, _ = _wait_for_boundary_resolution(
                    live=live,
                    run_id=current_run_id,
                    heartbeat=heartbeat,
                    initial_boundary=boundary,
                )
                cycle_state = _read_cycle_state(cycle_state_path)
                publish_attempt_state = _publish_attempt_state_for_run(cycle_state, current_run_id)
                boundary_status = boundary.get("status", "")
                boundary_reason = boundary.get("state_reason", boundary.get("reason", ""))
                publish_attempted_for_run = (
                    publish_attempt_state.get("publish_attempted_for_run", "0") == "1"
                )
                post_pilot_transition_for_run = (
                    publish_attempt_state.get("post_pilot_transition_for_run", "0") == "1"
                )
                publish_entry_for_run = (
                    publish_attempt_state.get("publish_entry_for_run", "0") == "1"
                )
                intel_started_for_run = (
                    publish_attempt_state.get("intel_started_for_run", "0") == "1"
                )
                if publish_attempted_for_run:
                    boundary_code = "FINALIZE_BLOCKED_NO_PUBLISH"
                elif post_pilot_transition_for_run or publish_entry_for_run:
                    boundary_code = "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH"
                elif intel_started_for_run:
                    boundary_code = "EARLY_CORE_EXIT_BEFORE_PUBLISH_EVIDENCE"
                else:
                    boundary_code = "EARLY_CORE_EXIT_BEFORE_PILOT_EVIDENCE"
                pilot_handoff_reason = ""
                pilot_handoff_evidence: dict[str, str] = {}
                if (
                    current_run_id
                    and boundary_code == "EARLY_CORE_EXIT_BEFORE_PILOT_EVIDENCE"
                    and str(publish_attempt_state.get("post_pilot_transition_status", "")).strip() == "pilot_started"
                ):
                    pilot_wait_seconds = max(
                        float(os.environ.get("H_WRAPPER_PILOT_HANDOFF_WAIT_SECONDS", "180") or "180"),
                        0.0,
                    )
                    pilot_handoff_evidence, _ = _wait_for_pilot_handoff_evidence(
                        live=live,
                        run_id=current_run_id,
                        heartbeat=heartbeat,
                        max_wait_seconds=pilot_wait_seconds,
                    )
                    boundary_code, pilot_handoff_reason = _classify_pilot_handoff_terminal(
                        current_run_id,
                        pilot_handoff_evidence,
                    )
                if current_run_id and (
                    _phase1_intel_parent_exit_code(boundary) == "PHASE1_INTEL_PARENT_EXIT_DURING_WAIT"
                    or _result_implies_parent_loss(result_payload)
                ):
                    boundary_code = "PHASE1_INTEL_PARENT_EXIT_DURING_WAIT"
                elif current_run_id and _boundary_is_unresolved(boundary_status):
                    boundary_code = "UNRESOLVED_PHASE1_INTEL_BOUNDARY"
                run_in_progress_cleared = "0"
                run_in_progress_clear_reason = ""
                if boundary_code == "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH" and current_run_id:
                    cleared, clear_reason = _clear_terminal_run_in_progress(live, current_run_id)
                    run_in_progress_cleared = "1" if cleared else "0"
                    run_in_progress_clear_reason = clear_reason
                finalizer_line = (
                    f"{boundary_code} "
                    f"current={current_run_id} "
                    f"publish_run_id={publish_run_id} "
                    f"publish_attempted_for_run={publish_attempt_state.get('publish_attempted_for_run', '0')} "
                    f"publish_started_for_run={publish_attempt_state.get('publish_started_for_run', '0')} "
                    f"publish_completed_for_run={publish_attempt_state.get('publish_completed_for_run', '0')} "
                    f"publish_entry_for_run={publish_attempt_state.get('publish_entry_for_run', '0')} "
                    f"post_pilot_transition_for_run={publish_attempt_state.get('post_pilot_transition_for_run', '0')} "
                    f"post_pilot_transition_status={publish_attempt_state.get('post_pilot_transition_status', '') or 'missing'} "
                    f"post_pilot_transition_status_raw={publish_attempt_state.get('post_pilot_transition_status_raw', '') or 'missing'} "
                    f"post_pilot_transition_run_matches={publish_attempt_state.get('post_pilot_transition_run_matches', '0')} "
                    f"intel_started_for_run={publish_attempt_state.get('intel_started_for_run', '0')} "
                    f"cycle_state_path={cycle_state_path} "
                    f"boundary_status={boundary_status or 'missing'} "
                    f"boundary_contract_stage={boundary.get('contract_stage', '') or 'missing'} "
                    f"boundary_state_path={boundary.get('boundary_state_path', '')} "
                    f"boundary_result_path={result_payload.get('result_path', '')} "
                    f"boundary_child_pid={boundary.get('child_pid', '')} "
                    f"boundary_reason={boundary_reason} "
                    f"boundary_result_error_type={result_payload.get('phase1_daily_intel_alignment_error_type', '')} "
                    f"boundary_result_error={result_payload.get('phase1_daily_intel_alignment_error', '')} "
                    f"pilot_handoff_reason={pilot_handoff_reason} "
                    f"pilot_marker_path={pilot_handoff_evidence.get('marker_path', '')} "
                    f"pilot_marker_status={pilot_handoff_evidence.get('marker_status', '') or 'missing'} "
                    f"pilot_marker_run_id={pilot_handoff_evidence.get('marker_run_id', '')} "
                    f"pilot_marker_result_ok={pilot_handoff_evidence.get('marker_result_ok', '')} "
                    f"pilot_result_path={pilot_handoff_evidence.get('result_path', '')} "
                    f"pilot_result_exists={pilot_handoff_evidence.get('result_exists', '0')} "
                    f"pilot_result_size={pilot_handoff_evidence.get('result_size', '0')} "
                    f"pilot_stderr_path={pilot_handoff_evidence.get('stderr_path', '')} "
                    f"pilot_stderr_mtime_utc={pilot_handoff_evidence.get('stderr_mtime_utc', '')} "
                    f"pilot_stderr_age_seconds={pilot_handoff_evidence.get('stderr_age_seconds', '')} "
                    f"run_in_progress_cleared={run_in_progress_cleared} "
                    f"run_in_progress_clear_reason={run_in_progress_clear_reason} "
                    f"selected_source={publish_proof.get('selected_source', '') or 'none'} "
                    f"publish_marker_path={publish_proof.get('publish_marker_path', '')} "
                    f"publish_marker_run_id={publish_proof.get('publish_marker_run_id', '')} "
                    f"publish_info_path={publish_proof.get('publish_info_path', '')} "
                    f"publish_info_run_id={publish_proof.get('publish_info_run_id', '')}"
                )
                _append_text(
                    heartbeat,
                    f"{finalizer_line}\n",
                )
                _write_text(
                    exit_status,
                    (
                        f"{finalizer_line}\n"
                        f"SYSTEMEXIT utc={utc}\n"
                        "rc=3\n"
                        f"code={boundary_code}\n"
                    ),
                )
                _write_runtime_status_from_wrapper(
                    live,
                    mode="ERROR",
                    run_id=current_run_id,
                    stage="phase1_intel",
                    detail=(
                        "wrapper_early_core_exit"
                        if boundary_code in {"EARLY_CORE_EXIT_BEFORE_PILOT_EVIDENCE", "EARLY_CORE_EXIT_BEFORE_PUBLISH_EVIDENCE"}
                        else (
                        "wrapper_pre_publish_exit"
                        if boundary_code == "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH"
                        else (
                            "wrapper_pilot_publish_transition_missing"
                            if boundary_code == "PILOT_TO_PUBLISH_TRANSITION_NOT_REACHED"
                            else (
                                "wrapper_pilot_handoff_failure"
                                if boundary_code.startswith("PHASE1_PILOT_")
                                else "wrapper_finalize_blocked"
                            )
                        )
                        )
                    ),
                    error=boundary_code,
                    interruption_class="true" if interruption_class else "false",
                    interruption_signal=interruption_signal,
                    wrapper_exit_category=wrapper_exit_category,
                )
                print(finalizer_line, file=sys.stderr, flush=True)
                final_rc = 3
                return 3
            _append_text(
                heartbeat,
                f"EXIT_OK utc={utc}\nrc={rc}\n",
            )
            _write_text(
                exit_status,
                (
                    f"EXIT_OK utc={utc}\n"
                    f"rc={rc}\n"
                ),
            )
            _write_runtime_status_from_wrapper(
                live,
                mode="IDLE",
                run_id=_read_first_line(current_run_id_path),
                stage="child_exit",
                detail="wrapper_exit_ok",
                interruption_class="false",
                interruption_signal=interruption_signal,
                wrapper_exit_category="normal_exit",
            )
        else:
            current_run_id = _read_first_line(current_run_id_path)
            boundary = _read_phase1_intel_boundary_state(live, current_run_id)
            result_payload = {}
            boundary_status = boundary.get("status", "")
            boundary_contract_stage = boundary.get("contract_stage", "")
            boundary_child_pid = boundary.get("child_pid", "")
            boundary_child_alive = _pid_alive(boundary_child_pid)
            boundary_code = "child_rc"
            boundary_line = ""
            orphan_killed = False
            orphan_kill_error = ""
            if current_run_id:
                boundary, result_payload, _ = _wait_for_boundary_resolution(
                    live=live,
                    run_id=current_run_id,
                    heartbeat=heartbeat,
                    initial_boundary=boundary,
                )
                boundary_status = boundary.get("status", "")
                boundary_contract_stage = boundary.get("contract_stage", "")
                boundary_child_pid = boundary.get("child_pid", "")
                boundary_child_alive = _pid_alive(boundary_child_pid)
                boundary_code = _phase1_intel_parent_exit_code(boundary)
                if boundary_code == "child_rc" and _result_implies_parent_loss(result_payload):
                    boundary_code = "PHASE1_INTEL_PARENT_EXIT_DURING_WAIT"
            if boundary_code != "child_rc":
                if boundary_child_alive:
                    orphan_killed, orphan_kill_error = _cleanup_phase1_intel_orphan(boundary)
                    boundary_child_alive = _pid_alive(boundary_child_pid)
                boundary_line = (
                    f"{boundary_code} "
                    f"current={current_run_id} "
                    f"child_rc={rc} "
                    f"boundary_status={boundary_status or 'missing'} "
                    f"boundary_contract_stage={boundary_contract_stage or 'missing'} "
                    f"boundary_state_path={boundary.get('boundary_state_path', '')} "
                    f"boundary_result_path={result_payload.get('result_path', '')} "
                    f"boundary_child_pid={boundary_child_pid} "
                    f"boundary_child_alive={'1' if boundary_child_alive else '0'} "
                    f"boundary_reason={boundary.get('state_reason', boundary.get('reason', ''))} "
                    f"boundary_result_error_type={result_payload.get('phase1_daily_intel_alignment_error_type', '')} "
                    f"boundary_result_error={result_payload.get('phase1_daily_intel_alignment_error', '')} "
                    f"orphan_killed={'1' if orphan_killed else '0'} "
                    f"orphan_kill_error={orphan_kill_error}"
                )
                _append_text(heartbeat, boundary_line + "\n")
                _write_runtime_status_from_wrapper(
                    live,
                    mode="ERROR",
                    run_id=current_run_id,
                    stage="phase1_intel",
                    detail="wrapper_boundary_failure",
                    error=boundary_code,
                    interruption_class="true" if interruption_class else "false",
                    interruption_signal=interruption_signal,
                    wrapper_exit_category=wrapper_exit_category,
                )
                print(boundary_line, file=sys.stderr, flush=True)
            _append_text(
                heartbeat,
                f"SYSTEMEXIT utc={utc}\nrc={rc}\ncode={boundary_code}\n",
            )
            _write_text(
                exit_status,
                (
                    f"{boundary_line}\n" if boundary_line else ""
                    f"SYSTEMEXIT utc={utc}\n"
                    f"rc={rc}\n"
                    f"code={boundary_code}\n"
                ),
            )
            _write_runtime_status_from_wrapper(
                live,
                mode="ERROR",
                run_id=_read_first_line(current_run_id_path),
                stage="child_exit",
                detail="wrapper_system_exit",
                error=boundary_code,
                interruption_class="true" if interruption_class else "false",
                interruption_signal=interruption_signal,
                wrapper_exit_category=wrapper_exit_category,
            )
        _append_text(
            heartbeat,
            (
                "interruption_evidence_written "
                f"interruption_class={'1' if interruption_class else '0'} "
                f"signal={interruption_signal or 'none'} "
                f"wrapper_exit_category={wrapper_exit_category}\n"
            ),
        )
        _append_text(
            exit_status,
            (
                f"interruption_class={'1' if interruption_class else '0'}\n"
                f"interruption_signal={interruption_signal}\n"
                f"wrapper_exit_category={wrapper_exit_category}\n"
                f"interruption_hold_candidate={'1' if interruption_class else '0'}\n"
            ),
        )
        final_rc = rc
        return rc

    except SystemExit as e:
        # Some code uses SystemExit for control flow. Capture it explicitly.
        code = e.code
        rc = int(code) if isinstance(code, int) else 1
        if rc == 130:
            interruption_class = True
            interruption_signal = interruption_signal or "SIGINT"
            wrapper_exit_category = "keyboard_interrupt_rc130"
        stop_flag.set()
        utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        _append_text(
            heartbeat,
            (
                f"SYSTEMEXIT utc={utc}\n"
                f"rc={rc}\ncode={code!r}\n"
            ),
        )
        _write_text(
            exit_status,
            (
                f"SYSTEMEXIT utc={utc}\n"
                f"rc={rc}\n"
                f"code={code!r}\n"
            ),
        )
        final_rc = rc
        return rc

    except BaseException:
        # Guaranteed traceback, even if logging is dead/buffered
        interruption_class = False
        wrapper_exit_category = "wrapper_crash"
        tb = traceback.format_exc()
        stop_flag.set()
        utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        _write_text(
            crash_log,
            f"UTC={utc}\n"
            f"argv={sys.argv!r}\n\n"
            f"{tb}\n",
        )
        _append_text(
            heartbeat,
            f"EXIT_CRASH utc={utc}\nrc=2\n",
        )
        _write_text(
            exit_status,
            (
                f"EXIT_CRASH utc={utc}\n"
                "rc=2\n"
            ),
        )
        final_rc = 2
        return 2
    finally:
        elapsed_seconds = max(time.monotonic() - run_started_monotonic, 0.0)
        short_threshold_raw = os.environ.get("H_SHORT_FAILURE_SECONDS", "180")
        try:
            short_threshold_seconds = int(float(str(short_threshold_raw or "180").strip()))
        except BaseException:
            short_threshold_seconds = 180
        if short_threshold_seconds < 1:
            short_threshold_seconds = 1
        short_failure_hint = (
            "1"
            if final_rc is not None and int(final_rc) != 0 and elapsed_seconds <= float(short_threshold_seconds)
            else "0"
        )
        if final_rc is not None and int(final_rc) == 130:
            interruption_class = True
            interruption_signal = interruption_signal or "SIGINT"
            if wrapper_exit_category == "normal_exit":
                wrapper_exit_category = "keyboard_interrupt_rc130"
        _append_text(
            heartbeat,
            (
                "WRAPPER_RUN_SUMMARY "
                f"run_duration_seconds={elapsed_seconds:.2f} "
                f"short_failure_threshold_seconds={short_threshold_seconds} "
                f"short_failure_hint={short_failure_hint} "
                f"rc={'' if final_rc is None else final_rc}\n"
            ),
        )
        _append_text(
            heartbeat,
            (
                "interruption_evidence_written "
                f"interruption_class={'1' if interruption_class else '0'} "
                f"signal={interruption_signal or 'none'} "
                f"wrapper_exit_category={wrapper_exit_category}\n"
            ),
        )
        _append_text(
            exit_status,
            (
                f"run_duration_seconds={elapsed_seconds:.2f}\n"
                f"short_failure_threshold_seconds={short_threshold_seconds}\n"
                f"short_failure_hint={short_failure_hint}\n"
                f"final_rc={'' if final_rc is None else final_rc}\n"
                f"interruption_class={'1' if interruption_class else '0'}\n"
                f"interruption_signal={interruption_signal}\n"
                f"wrapper_exit_category={wrapper_exit_category}\n"
                f"interruption_hold_candidate={'1' if interruption_class else '0'}\n"
            ),
        )
        stop_flag.set()
        if diagnostic_mode:
            faulthandler.cancel_dump_traceback_later()
        _fault_fh.flush()
        _fault_fh.close()
        os._exit = _real_os_exit  # type: ignore


if __name__ == "__main__":
    raise SystemExit(main())
