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
from datetime import datetime, timezone

try:
    from scripts.core.runtime_owner_contract import (
        RuntimeOwnerContractError,
        assert_flow_owner_mapping,
        is_truthy,
    )
except ModuleNotFoundError:
    from core.runtime_owner_contract import (
        RuntimeOwnerContractError,
        assert_flow_owner_mapping,
        is_truthy,
    )

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


def _safe_stderr_print(message: str) -> None:
    try:
        print(message, file=sys.stderr, flush=True)
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
        powershell_exe = (
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        cmd = [
            str(powershell_exe),
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(capture_script),
            "-TargetPid",
            str(child_pid),
            "-LiveDir",
            str(live),
        ]
        popen_kwargs = {
            "cwd": str(root),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            creation_flags = 0
            creation_flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if creation_flags:
                popen_kwargs["creationflags"] = creation_flags
            startupinfo = None
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0))
                startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
            except Exception:
                startupinfo = None
            if startupinfo is not None:
                popen_kwargs["startupinfo"] = startupinfo
        proc = subprocess.Popen(cmd, **popen_kwargs)
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


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _read_h_run_state(path: Path) -> dict[str, str]:
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


def _read_h_worker_lifecycle(path: Path) -> dict[str, str]:
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


def _write_h_worker_lifecycle(path: Path, payload: dict[str, str]) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _parse_utc_ts(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        from datetime import datetime, timezone

        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except BaseException:
        return None


def _worker_heartbeat_age_seconds(worker_state: dict[str, str]) -> float | None:
    ts = _parse_utc_ts(worker_state.get("heartbeat_utc", ""))
    if ts is None:
        return None
    return max(time.time() - ts, 0.0)


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            probe = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            combined = f"{probe.stdout or ''}\n{probe.stderr or ''}".strip()
            if not combined:
                return False
            if "No tasks are running which match the specified criteria" in combined:
                return False
            return f"\"{int(pid)}\"" in combined
        except BaseException:
            return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except BaseException:
        return False


def _parse_lock_pid_run(path: Path) -> tuple[int, str]:
    line = _read_first_line(path)
    if not line:
        return 0, ""
    pid = 0
    run_id = ""
    if "pid=" in line:
        try:
            pid = int(line.split("pid=", 1)[1].split("|", 1)[0].strip())
        except BaseException:
            pid = 0
    if "run_id=" in line:
        try:
            run_id = line.split("run_id=", 1)[1].split("|", 1)[0].strip()
        except BaseException:
            run_id = ""
    return pid, run_id


def _normalize_stale_startup_context(
    *,
    root: Path,
    live: Path,
    current_run_id_path: Path,
    worker_lifecycle_path: Path,
    heartbeat: Path,
    stale_after_seconds: float,
) -> dict[str, str]:
    current_run_id = _read_first_line(current_run_id_path)
    worker = _read_h_worker_lifecycle(worker_lifecycle_path)
    worker_run_id = str(worker.get("run_id", "")).strip()
    worker_state = str(worker.get("state", "")).strip().lower()
    active_states = {"pending", "claimed", "running", "finalizing"}
    if worker_state not in active_states:
        return {"normalized": "0", "reason": "worker_state_not_active"}
    if not worker_run_id:
        return {"normalized": "0", "reason": "worker_run_id_missing"}
    if current_run_id and current_run_id != worker_run_id:
        return {"normalized": "0", "reason": "run_id_mismatch"}
    heartbeat_age = _worker_heartbeat_age_seconds(worker)
    if heartbeat_age is None or heartbeat_age <= stale_after_seconds:
        return {"normalized": "0", "reason": "heartbeat_not_stale"}

    lock_paths = [live / "H_pricing_cycle.lock", root / "out" / "H_pricing_cycle.lock"]
    owner_alive = False
    owner_pid = 0
    for lock_path in lock_paths:
        pid, lock_run_id = _parse_lock_pid_run(lock_path)
        if lock_run_id and lock_run_id != worker_run_id:
            continue
        if pid and _pid_is_alive(pid):
            owner_alive = True
            owner_pid = pid
            break
    if owner_alive:
        _append_text(
            heartbeat,
            (
                "startup_stale_context_preserved "
                f"run_id={worker_run_id} "
                f"reason=active_owner_present "
                f"owner_pid={owner_pid} "
                f"worker_state={worker_state} "
                f"heartbeat_age_seconds={heartbeat_age:.2f} "
                f"stale_after_seconds={stale_after_seconds:.2f}\n"
            ),
        )
        return {"normalized": "0", "reason": "active_owner_present", "owner_pid": str(owner_pid)}

    _append_text(
        heartbeat,
        (
            "startup_stale_context_detected "
            f"run_id={worker_run_id} "
            f"prior_state={worker_state} "
            f"heartbeat_age_seconds={heartbeat_age:.2f} "
            f"stale_after_seconds={stale_after_seconds:.2f} "
            "action=fail_closed_no_mutation\n"
        ),
    )
    return {
        "normalized": "0",
        "reason": "stale_context_detected_fail_closed",
        "run_id": worker_run_id,
    }


def _mark_worker_terminal(
    path: Path,
    *,
    run_id: str,
    state: str,
    reason_code: str,
    reason_detail: str = "",
) -> dict[str, str]:
    payload = _read_h_worker_lifecycle(path)
    payload["run_id"] = str(run_id or "").strip()
    payload["state"] = str(state or "").strip().lower()
    utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload["heartbeat_utc"] = utc
    payload["terminal_utc"] = utc
    payload["terminal_outcome"] = payload["state"]
    payload["reason_code"] = str(reason_code or "").strip()
    if reason_detail:
        payload["reason_detail"] = str(reason_detail or "").strip()[:1000]
    _write_h_worker_lifecycle(path, payload)
    return payload


def _archive_stale_startup_context(
    *,
    live: Path,
    run_id: str,
    run_state_path: Path,
    worker_lifecycle_path: Path,
    finalized_run_id_path: Path,
    heartbeat: Path,
) -> dict[str, str]:
    run_norm = str(run_id or "").strip()
    if not run_norm:
        return {"archived": "0", "reason": "missing_run_id"}

    run_in_progress_path = live / "H_run_in_progress.txt"
    run_in_progress = _read_first_line(run_in_progress_path)
    if run_in_progress and run_in_progress != run_norm:
        return {
            "archived": "0",
            "reason": "run_in_progress_mismatch",
            "run_in_progress": run_in_progress,
        }

    finalized_run_id = _read_first_line(finalized_run_id_path)
    run_state_existing = _read_h_run_state(run_state_path)
    worker_payload = _read_h_worker_lifecycle(worker_lifecycle_path)
    _append_text(
        heartbeat,
        (
            "startup_stale_context_observed "
            f"run_id={run_norm} "
            f"run_in_progress={run_in_progress or 'missing'} "
            f"finalized_run_id={finalized_run_id or 'missing'} "
            f"run_state_state={_norm(run_state_existing.get('state', '')) or 'missing'} "
            f"worker_state={_norm(worker_payload.get('state', '')) or 'missing'} "
            "action=fail_closed_no_state_mutation\n"
        ),
    )
    return {
        "archived": "0",
        "reason": "core_owned_truth_no_wrapper_mutation",
        "run_id": run_norm,
        "run_in_progress": run_in_progress,
        "finalized_run_id": finalized_run_id,
        "run_state_state": _norm(run_state_existing.get("state", "")),
        "worker_state": _norm(worker_payload.get("state", "")),
        "run_in_progress_cleared": "0",
    }


def _classify_publish_from_run_state(run_state: dict[str, str], run_id: str) -> dict[str, str]:
    run_id_norm = str(run_id or "").strip()
    state_run_id = str(run_state.get("run_id", "")).strip()
    state_value = str(run_state.get("state", "")).strip().lower()
    stage_value = str(run_state.get("stage", "")).strip().lower()
    publish_status = str(run_state.get("publish_status", "")).strip().lower()
    failure_code = str(run_state.get("failure_code", "")).strip()
    if not run_id_norm or not run_state:
        return {"usable": "0", "reason": "missing_run_state"}
    if state_run_id != run_id_norm:
        return {
            "usable": "0",
            "reason": "run_id_mismatch",
            "state_run_id": state_run_id,
            "state": state_value,
            "publish_status": publish_status,
        }
    publish_done_states = {"publish_done", "finalized", "succeeded", "success"}
    publish_started_states = {"publish_started", *publish_done_states}
    publish_status_started = {"started", "start", "running", "in_progress", "publishing"}
    publish_status_done = {"ok", "done", "success", "succeeded", "published", "publish_done", "finalized"}

    publish_started_for_run = state_value in publish_started_states
    publish_completed_for_run = state_value in publish_done_states
    post_pilot_transition_for_run = state_value in {"pilot_done", *publish_started_states}
    post_pilot_transition_status = (
        "publish_entered"
        if state_value in publish_started_states
        else ("pilot_completed" if state_value == "pilot_done" else ("pilot_started" if state_value == "pilot_started" else ""))
    )
    intel_started_for_run = state_value in {"snapshot_done", "pilot_started", "pilot_done", *publish_started_states}

    # Failed terminal states must be interpreted from explicit stage/publish_status
    # evidence, not assumed to be post-publish by default.
    if state_value == "failed":
        publish_completed_for_run = publish_status in publish_status_done
        publish_started_for_run = (
            publish_completed_for_run
            or publish_status in publish_status_started
            or stage_value == "phase1_publish"
        )
        if failure_code == "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH":
            post_pilot_transition_for_run = True
            post_pilot_transition_status = "pilot_completed"
        elif stage_value == "phase1_publish" or publish_started_for_run:
            post_pilot_transition_for_run = True
            post_pilot_transition_status = "publish_entered"
        elif stage_value == "phase1_pilot":
            post_pilot_transition_for_run = True
            post_pilot_transition_status = "pilot_started"
        else:
            post_pilot_transition_for_run = False
            post_pilot_transition_status = ""
        intel_started_for_run = (
            stage_value in {"snapshot_refresh", "phase1_intel", "phase1_pilot", "phase1_publish"}
            or post_pilot_transition_for_run
            or publish_started_for_run
            or publish_completed_for_run
        )

    return {
        "usable": "1",
        "reason": "ok",
        "state_run_id": state_run_id,
        "state": state_value,
        "stage": stage_value,
        "publish_status": publish_status,
        "failure_code": failure_code,
        "publish_attempted_for_run": "1" if publish_started_for_run else "0",
        "publish_started_for_run": "1" if publish_started_for_run else "0",
        "publish_completed_for_run": "1" if publish_completed_for_run else "0",
        "publish_entry_for_run": "1" if publish_started_for_run else "0",
        "post_pilot_transition_for_run": "1" if post_pilot_transition_for_run else "0",
        "post_pilot_transition_status": post_pilot_transition_status,
        "post_pilot_transition_status_raw": state_value,
        "post_pilot_transition_run_matches": "1",
        "intel_started_for_run": "1" if intel_started_for_run else "0",
    }


def _classify_wrapper_terminal_truth(
    *,
    run_id: str,
    run_state: dict[str, str],
    worker_lifecycle: dict[str, str],
    publish_proof: dict[str, str],
) -> dict[str, str]:
    run_norm = _norm(run_id)
    if not run_norm:
        return {
            "ok": "0",
            "boundary_code": "WRAPPER_MISSING_CURRENT_RUN_ID",
            "reason": "missing_current_run_id",
            "run_state_state": "",
            "run_state_stage": "",
            "run_state_publish_status": "",
            "run_state_failure_code": "",
            "worker_run_id": _norm(worker_lifecycle.get("run_id", "")),
            "worker_state": _norm(worker_lifecycle.get("state", "")).lower(),
            "publish_selected_run_id": _norm(publish_proof.get("selected_run_id", "")),
        }
    if not isinstance(run_state, dict) or not run_state:
        return {
            "ok": "0",
            "boundary_code": "RUN_STATE_MISSING_OR_UNUSABLE",
            "reason": "missing_or_unusable_run_state",
            "run_state_state": "",
            "run_state_stage": "",
            "run_state_publish_status": "",
            "run_state_failure_code": "",
            "worker_run_id": _norm(worker_lifecycle.get("run_id", "")),
            "worker_state": _norm(worker_lifecycle.get("state", "")).lower(),
            "publish_selected_run_id": _norm(publish_proof.get("selected_run_id", "")),
        }
    state_run_id = _norm(run_state.get("run_id", ""))
    state_value = _norm(run_state.get("state", "")).lower()
    stage_value = _norm(run_state.get("stage", "")).lower()
    publish_status = _norm(run_state.get("publish_status", "")).lower()
    failure_code = _norm(run_state.get("failure_code", ""))
    worker_run_id = _norm(worker_lifecycle.get("run_id", ""))
    worker_state = _norm(worker_lifecycle.get("state", "")).lower()
    publish_run_id = _norm(publish_proof.get("selected_run_id", ""))
    if state_run_id != run_norm:
        return {
            "ok": "0",
            "boundary_code": "RUN_STATE_RUN_ID_MISMATCH",
            "reason": "run_state_run_id_mismatch",
            "run_state_state": state_value,
            "run_state_stage": stage_value,
            "run_state_publish_status": publish_status,
            "run_state_failure_code": failure_code,
            "worker_run_id": worker_run_id,
            "worker_state": worker_state,
            "publish_selected_run_id": publish_run_id,
        }
    if state_value == "failed":
        return {
            "ok": "0",
            "boundary_code": failure_code or "RUN_STATE_FAILED_NO_CODE",
            "reason": "run_state_failed",
            "run_state_state": state_value,
            "run_state_stage": stage_value,
            "run_state_publish_status": publish_status,
            "run_state_failure_code": failure_code,
            "worker_run_id": worker_run_id,
            "worker_state": worker_state,
            "publish_selected_run_id": publish_run_id,
        }
    if state_value != "finalized":
        if state_value == "publish_done":
            boundary_code = "RUN_STATE_PUBLISH_DONE_NOT_FINALIZED"
        elif state_value in {"publish_started", "pilot_done", "pilot_started", "snapshot_done", "started", "collect_done"}:
            boundary_code = "RUN_STATE_NOT_TERMINAL"
        else:
            boundary_code = "RUN_STATE_UNKNOWN_TERMINAL_STATE"
        return {
            "ok": "0",
            "boundary_code": boundary_code,
            "reason": "run_state_not_finalized",
            "run_state_state": state_value,
            "run_state_stage": stage_value,
            "run_state_publish_status": publish_status,
            "run_state_failure_code": failure_code,
            "worker_run_id": worker_run_id,
            "worker_state": worker_state,
            "publish_selected_run_id": publish_run_id,
        }
    if worker_run_id != run_norm:
        return {
            "ok": "0",
            "boundary_code": "WORKER_LIFECYCLE_RUN_ID_MISMATCH",
            "reason": "worker_lifecycle_run_id_mismatch",
            "run_state_state": state_value,
            "run_state_stage": stage_value,
            "run_state_publish_status": publish_status,
            "run_state_failure_code": failure_code,
            "worker_run_id": worker_run_id,
            "worker_state": worker_state,
            "publish_selected_run_id": publish_run_id,
        }
    if worker_state != "succeeded":
        return {
            "ok": "0",
            "boundary_code": "WORKER_LIFECYCLE_NOT_SUCCEEDED",
            "reason": "worker_lifecycle_not_succeeded",
            "run_state_state": state_value,
            "run_state_stage": stage_value,
            "run_state_publish_status": publish_status,
            "run_state_failure_code": failure_code,
            "worker_run_id": worker_run_id,
            "worker_state": worker_state,
            "publish_selected_run_id": publish_run_id,
        }
    if publish_run_id != run_norm:
        return {
            "ok": "0",
            "boundary_code": "FINALIZED_WITHOUT_SAME_RUN_PUBLISH_PROOF",
            "reason": "publish_proof_run_id_mismatch",
            "run_state_state": state_value,
            "run_state_stage": stage_value,
            "run_state_publish_status": publish_status,
            "run_state_failure_code": failure_code,
            "worker_run_id": worker_run_id,
            "worker_state": worker_state,
            "publish_selected_run_id": publish_run_id,
        }
    return {
        "ok": "1",
        "boundary_code": "",
        "reason": "terminal_truth_verified",
        "run_state_state": state_value,
        "run_state_stage": stage_value,
        "run_state_publish_status": publish_status,
        "run_state_failure_code": failure_code,
        "worker_run_id": worker_run_id,
        "worker_state": worker_state,
        "publish_selected_run_id": publish_run_id,
    }


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


def _write_last_terminal_marker_from_wrapper(
    live: Path,
    *,
    run_id: str,
    terminal_state: str,
    stage: str,
    publish_status: str,
    failure_code: str = "",
    failure_detail: str = "",
) -> tuple[bool, str]:
    run_id_norm = str(run_id or "").strip()
    if not run_id_norm:
        return False, "missing_run_id"
    utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    text = (
        f"run_id={run_id_norm}\n"
        f"utc={utc}\n"
        f"state={_norm(terminal_state).lower()}\n"
        f"stage={_norm(stage)}\n"
        f"publish_status={_norm(publish_status)}\n"
        f"failure_code={_norm(failure_code)}\n"
        f"failure_detail={_norm(failure_detail)[:500]}\n"
    )
    try:
        marker_path = live / "H_cycle_last_terminal_info.txt"
        _write_text(marker_path, text)
        # Keep legacy marker path in sync for readers that still consume out/.
        legacy_marker_path = live.parents[2] / "H_cycle_last_terminal_info.txt"
        _write_text(legacy_marker_path, text)
    except BaseException as exc:
        return False, f"write_failed_{type(exc).__name__}"
    return True, "written"


def _wrapper_terminalize_failed_run(
    *,
    live: Path,
    run_id: str,
    run_state_path: Path,
    worker_lifecycle_path: Path,
    failure_code: str,
    failure_detail: str,
    stage_hint: str = "",
    publish_status_hint: str = "",
) -> dict[str, str]:
    # Wrapper is verifier-only. Core owns all run-state mutation.
    run_norm = _norm(run_id)
    run_in_progress_value = _read_first_line(live / "H_run_in_progress.txt") if run_norm else ""
    run_state_existing = _read_h_run_state(run_state_path)
    worker_existing = _read_h_worker_lifecycle(worker_lifecycle_path)
    stage_value = _norm(stage_hint) or _norm(run_state_existing.get("stage", "")) or "guard_wrapper"
    publish_status = _norm(publish_status_hint) or _norm(run_state_existing.get("publish_status", "")) or "unknown"
    failure_code_norm = _norm(failure_code) or "WRAPPER_TERMINAL_FAILURE"
    reason = "core_owned_truth_no_wrapper_mutation"
    return {
        "applied": "0",
        "reason": reason,
        "run_in_progress_value": run_in_progress_value,
        "run_in_progress_cleared": "0",
        "run_in_progress_clear_reason": reason,
        "run_state_written": "0",
        "worker_written": "0",
        "terminal_marker_written": "0",
        "terminal_marker_reason": reason,
        "stage": stage_value,
        "publish_status": publish_status,
        "failure_code": failure_code_norm,
        "run_state_run_id": _norm(run_state_existing.get("run_id", "")),
        "worker_run_id": _norm(worker_existing.get("run_id", "")),
    }


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


def _phase1_intel_wait_active_for_child(*, live: Path, run_id: str, child_pid: int) -> tuple[bool, str]:
    run_norm = str(run_id or "").strip()
    if not run_norm:
        return False, "run_id_missing"
    boundary = _read_phase1_intel_boundary_state(live, run_norm)
    status = str(boundary.get("status", "")).strip().lower()
    if not _boundary_is_unresolved(status):
        return False, f"boundary_status={status or 'missing'}"
    try:
        boundary_child_pid = int(str(boundary.get("child_pid", "")).strip())
    except BaseException:
        return False, "boundary_child_pid_missing"
    if boundary_child_pid != int(child_pid):
        return False, f"boundary_child_pid_mismatch:{boundary_child_pid}"
    return True, f"boundary_status={status}"


def _phase1_pilot_wait_active_for_child(
    *,
    live: Path,
    run_id: str,
    child_pid: int,
    max_handoff_age_seconds: float,
) -> tuple[bool, str]:
    run_norm = str(run_id or "").strip()
    if not run_norm:
        return False, "run_id_missing"
    try:
        candidates = sorted(
            live.glob(f"phase1_pilot_parent_handoff.{run_norm}.*.json"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
            reverse=True,
        )
    except BaseException:
        return False, "handoff_glob_failed"
    if not candidates:
        return False, "handoff_missing"
    for path in candidates:
        try:
            raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except BaseException:
            continue
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status", "")).strip().lower()
        if status not in {"pilot_wait_entered", "pilot_wait_heartbeat", "pilot_wait_active"}:
            return False, f"handoff_status={status or 'missing'}"
        try:
            parent_pid = int(str(raw.get("parent_pid", "")).strip())
        except BaseException:
            return False, "handoff_parent_pid_missing"
        if parent_pid != int(child_pid):
            continue
        age_seconds = 0.0
        try:
            age_seconds = max(time.time() - float(path.stat().st_mtime), 0.0)
        except BaseException:
            age_seconds = 0.0
        if age_seconds > float(max_handoff_age_seconds):
            return False, f"handoff_stale_age_seconds={age_seconds:.2f}"
        marker_path = str(raw.get("completion_marker_path", "")).strip()
        if marker_path:
            try:
                marker_raw = json.loads(Path(marker_path).read_text(encoding="utf-8", errors="replace"))
                if isinstance(marker_raw, dict):
                    marker_status = str(marker_raw.get("status", "")).strip().lower()
                    if marker_status and marker_status not in {"started", "running"}:
                        return False, f"marker_terminal_status={marker_status}"
            except BaseException:
                pass
        return True, f"handoff_status={status}:age_seconds={age_seconds:.2f}"
    return False, "handoff_parent_pid_mismatch"


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


def _read_snapshot_worker_contract_evidence(live: Path, run_id: str) -> dict[str, str]:
    evidence: dict[str, str] = {
        "contract_path": "",
        "contract_exists": "0",
        "contract_run_id": "",
        "contract_status": "",
        "contract_reason": "",
        "checkpoint_last": "",
        "refresh_status": "",
        "success_ok": "0",
    }
    run_norm = str(run_id or "").strip()
    if not run_norm:
        return evidence
    contract_path = _latest_matching_path(live, f"snapshot_refresh_worker.contract.{run_norm}.*.json")
    if contract_path is None:
        return evidence
    evidence["contract_path"] = str(contract_path)
    evidence["contract_exists"] = "1"
    try:
        raw = json.loads(contract_path.read_text(encoding="utf-8", errors="replace"))
    except BaseException as exc:
        evidence["contract_status"] = "invalid_json"
        evidence["contract_reason"] = f"{type(exc).__name__}:{exc}"
        return evidence
    if not isinstance(raw, dict):
        evidence["contract_status"] = "invalid_payload"
        return evidence
    evidence["contract_run_id"] = str(raw.get("run_id", "") or "").strip()
    evidence["contract_status"] = str(raw.get("status", "") or "").strip().lower()
    evidence["contract_reason"] = str(raw.get("reason", "") or "").strip()
    evidence["checkpoint_last"] = str(raw.get("checkpoint_last", "") or "").strip()
    refresh_state = raw.get("refresh_state", {})
    if isinstance(refresh_state, dict):
        evidence["refresh_status"] = str(refresh_state.get("snapshot_refresh_status", "") or "").strip().lower()
    run_matches = evidence.get("contract_run_id", "") == run_norm
    status_ok = evidence.get("contract_status", "") == "ok"
    refresh_ok = evidence.get("refresh_status", "") in {"", "ok"}
    evidence["success_ok"] = "1" if run_matches and status_ok and refresh_ok else "0"
    return evidence


def _wait_for_snapshot_worker_contract_evidence(
    *,
    live: Path,
    run_id: str,
    heartbeat: Path,
    max_wait_seconds: float,
    poll_seconds: float = 1.0,
) -> tuple[dict[str, str], bool]:
    def _is_transient(evidence: dict[str, str]) -> bool:
        if evidence.get("success_ok", "0") == "1":
            return False
        if evidence.get("contract_exists", "0") != "1":
            return True
        status = str(evidence.get("contract_status", "") or "").strip().lower()
        reason = str(evidence.get("contract_reason", "") or "").strip().lower()
        if status == "failed" and reason == "snapshot_worker_incomplete_before_finalization":
            return True
        return False

    evidence = _read_snapshot_worker_contract_evidence(live, run_id)
    if not _is_transient(evidence):
        return evidence, False
    started = time.time()
    rechecked = False
    _append_text(
        heartbeat,
        (
            "snapshot_worker_contract_wrapper_recheck "
            f"run_id={run_id} "
            f"max_wait_seconds={max_wait_seconds:.2f}\n"
        ),
    )
    while (time.time() - started) < max_wait_seconds:
        time.sleep(max(poll_seconds, 0.1))
        rechecked = True
        evidence = _read_snapshot_worker_contract_evidence(live, run_id)
        if not _is_transient(evidence):
            break
    _append_text(
        heartbeat,
        (
            "snapshot_worker_contract_wrapper_recheck_done "
            f"run_id={run_id} "
            f"rechecked={'1' if rechecked else '0'} "
            f"contract_exists={evidence.get('contract_exists', '0')} "
            f"contract_status={evidence.get('contract_status', '') or 'missing'} "
            f"contract_reason={evidence.get('contract_reason', '') or 'missing'} "
            f"refresh_status={evidence.get('refresh_status', '') or 'missing'} "
            f"success_ok={evidence.get('success_ok', '0')}\n"
        ),
    )
    return evidence, rechecked


def _snapshot_worker_no_publish_reconcile_eligible(
    *,
    run_id: str,
    run_state: dict[str, str],
    publish_attempt_state: dict[str, str],
    snapshot_contract_evidence: dict[str, str],
) -> tuple[bool, str]:
    run_norm = str(run_id or "").strip()
    if not run_norm:
        return False, "run_id_missing"
    if publish_attempt_state.get("publish_attempted_for_run", "0") == "1":
        return False, "publish_attempted_for_run"
    if publish_attempt_state.get("publish_entry_for_run", "0") == "1":
        return False, "publish_entry_for_run"
    if snapshot_contract_evidence.get("success_ok", "0") == "1":
        return True, "snapshot_worker_contract_success"
    failure_code = str(run_state.get("failure_code", "") or "").strip()
    failure_detail = str(run_state.get("failure_detail", "") or "").strip().lower()
    if (
        failure_code == "SNAPSHOT_WORKER_HANDOFF_PARENT_EXIT"
        and "parent_exit_after_snapshot_worker_success_before_contract_handoff" in failure_detail
    ):
        return True, "run_state_parent_exit_success_detail"
    return False, "snapshot_worker_contract_not_terminal_success"


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


def _wait_for_post_pilot_publish_state(
    *,
    cycle_state_path: Path,
    run_id: str,
    heartbeat: Path,
    max_wait_seconds: float,
    poll_seconds: float = 1.0,
    wait_for_publish_attempt_only: bool = False,
) -> tuple[dict[str, str], bool]:
    state = _publish_attempt_state_for_run(_read_cycle_state(cycle_state_path), run_id)
    if state.get("publish_attempted_for_run", "0") == "1":
        return state, False
    if (
        not wait_for_publish_attempt_only
        and (
            state.get("post_pilot_transition_for_run", "0") == "1"
            or state.get("publish_entry_for_run", "0") == "1"
        )
    ):
        return state, False
    started = time.time()
    rechecked = False
    _append_text(
        heartbeat,
        (
            "phase1_pilot_publish_reconcile_wait "
            f"run_id={run_id} "
            f"max_wait_seconds={max_wait_seconds:.2f} "
            f"wait_for_publish_attempt_only={'1' if wait_for_publish_attempt_only else '0'}\n"
        ),
    )
    while (time.time() - started) < max_wait_seconds:
        time.sleep(max(poll_seconds, 0.1))
        rechecked = True
        state = _publish_attempt_state_for_run(_read_cycle_state(cycle_state_path), run_id)
        if state.get("publish_attempted_for_run", "0") == "1":
            break
        if (
            not wait_for_publish_attempt_only
            and (
                state.get("post_pilot_transition_for_run", "0") == "1"
                or state.get("publish_entry_for_run", "0") == "1"
            )
        ):
            break
    _append_text(
        heartbeat,
        (
            "phase1_pilot_publish_reconcile_wait_done "
            f"run_id={run_id} "
            f"rechecked={'1' if rechecked else '0'} "
            f"publish_attempted_for_run={state.get('publish_attempted_for_run', '0')} "
            f"publish_started_for_run={state.get('publish_started_for_run', '0')} "
            f"publish_completed_for_run={state.get('publish_completed_for_run', '0')} "
            f"publish_entry_for_run={state.get('publish_entry_for_run', '0')} "
            f"post_pilot_transition_for_run={state.get('post_pilot_transition_for_run', '0')} "
            f"post_pilot_transition_status={state.get('post_pilot_transition_status', '') or 'missing'} "
            f"intel_started_for_run={state.get('intel_started_for_run', '0')}\n"
        ),
    )
    return state, rechecked


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
    try:
        stderr_age_seconds = float(str(evidence.get("stderr_age_seconds", "") or "nan"))
    except BaseException:
        stderr_age_seconds = float("nan")
    if marker_status in {"", "started", "running"}:
        if stderr_age_seconds == stderr_age_seconds and stderr_age_seconds <= 120.0:
            return "PHASE1_PILOT_STILL_ACTIVE_UNRESOLVED", "pilot_marker_non_terminal_with_recent_stderr_activity"
        return "PHASE1_PILOT_TERMINAL_EVIDENCE_MISSING", "pilot_marker_non_terminal_after_wait"
    if marker_status != "success":
        return "PHASE1_PILOT_TERMINAL_FAILURE", "pilot_terminal_failure_marker"
    if marker_run_id != str(run_id or "").strip():
        return "PHASE1_PILOT_COMPLETION_CONTRACT_FAILED", "pilot_completion_marker_run_mismatch"
    if marker_result_ok not in {"1", "true"}:
        return "PHASE1_PILOT_COMPLETION_CONTRACT_FAILED", "pilot_completion_marker_result_not_ok"
    if result_size <= 0:
        return "PHASE1_PILOT_COMPLETION_CONTRACT_FAILED", "pilot_result_payload_missing_after_success_marker"
    return (
        "PHASE1_PILOT_PARENT_EXIT_BEFORE_PUBLISH_CONTINUITY",
        "pilot_success_observed_but_parent_owner_lost_before_publish_continuity",
    )


def _truthy_env(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _allow_no_publish_terminal_ok(stage_phase1_publish: str) -> bool:
    _ = stage_phase1_publish
    # Freeze policy: wrapper never upgrades PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH
    # into terminal success. Only the core worker may advance terminal state.
    return False


def _enforce_owner_contract(root: Path) -> None:
    if not is_truthy(os.environ.get("H_OWNER_CONTRACT_ENFORCE", "1")):
        return
    assert_flow_owner_mapping(
        "H",
        runtime_owner=Path(__file__),
        worker_entry=root / "scripts" / "cycles" / "run_H_pricing_cycle.py",
        launcher_entrypoint=root / "run_H_cycle.bat",
    )


def main() -> int:
    root = _resolve_root()
    live = _live_dir(root)
    run_started_monotonic = time.monotonic()
    final_rc: int | None = None
    interruption_class = False
    interruption_signal = ""
    wrapper_exit_category = "normal_exit"
    try:
        _enforce_owner_contract(root)
    except RuntimeOwnerContractError as exc:
        _safe_stderr_print(f"owner_contract_violation {exc}")
        return 2

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
    run_state_path = live / "H_run_state.json"
    worker_lifecycle_path = live / "H_worker_lifecycle.json"
    cycle_state_path = live / "h_pricing_cycle_state.json"
    fault_log = live / "H_pricing_cycle.FAULT.log"
    _fault_fh = fault_log.open("a", encoding="utf-8", errors="replace")
    faulthandler.enable(_fault_fh)
    diagnostic_mode = os.environ.get("H_GUARD_DIAGNOSTIC_MODE", "0").strip() == "1"
    ignore_keyboard_interrupt = _truthy_env("H_GUARD_IGNORE_KEYBOARD_INTERRUPT", "1") and not diagnostic_mode
    worker_stale_seconds = max(float(os.environ.get("H_WORKER_LIFECYCLE_STALE_SECONDS", "120") or "120"), 30.0)
    pilot_wait_stale_grace_seconds = max(
        float(
            os.environ.get(
                "H_WRAPPER_PILOT_WAIT_STALE_GRACE_SECONDS",
                str(max(int(worker_stale_seconds * 8), 900)),
            )
            or str(max(int(worker_stale_seconds * 8), 900))
        ),
        worker_stale_seconds,
    )
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
    startup_context = _normalize_stale_startup_context(
        root=root,
        live=live,
        current_run_id_path=current_run_id_path,
        worker_lifecycle_path=worker_lifecycle_path,
        heartbeat=heartbeat,
        stale_after_seconds=worker_stale_seconds,
    )
    _append_text(
        heartbeat,
        (
            "startup_context_check "
            f"normalized={startup_context.get('normalized', '0')} "
            f"reason={startup_context.get('reason', '')}\n"
        ),
    )
    if startup_context.get("reason", "") == "stale_context_detected_fail_closed":
        stale_run_id = str(startup_context.get("run_id", "") or "").strip()
        stale_archive = _archive_stale_startup_context(
            live=live,
            run_id=stale_run_id,
            run_state_path=run_state_path,
            worker_lifecycle_path=worker_lifecycle_path,
            finalized_run_id_path=finalized_run_id_path,
            heartbeat=heartbeat,
        )
        stale_terminal_mutation = _wrapper_terminalize_failed_run(
            live=live,
            run_id=stale_run_id,
            run_state_path=run_state_path,
            worker_lifecycle_path=worker_lifecycle_path,
            failure_code="STARTUP_STALE_CONTEXT",
            failure_detail=(
                "startup_stale_context_detected "
                f"archive_reason={stale_archive.get('reason', '')} "
                "action=wrapper_observe_only_no_state_mutation"
            ),
            stage_hint="guard_wrapper_startup",
            publish_status_hint="not_started",
        )
        _append_text(
            heartbeat,
            (
                "startup_stale_context_resolution "
                f"run_id={stale_run_id or 'missing'} "
                f"archive_attempt_reason={stale_archive.get('reason', 'not_attempted')} "
                f"terminal_mutation_applied={stale_terminal_mutation.get('applied', '0')} "
                f"terminal_mutation_reason={stale_terminal_mutation.get('reason', '')} "
                "action=continue_to_core_authority\n"
            ),
        )
        startup_detail = "startup_stale_context_observed_no_wrapper_mutation"
        _write_runtime_status_from_wrapper(
            live,
            mode="RUNNING",
            run_id=stale_run_id,
            stage="guard_wrapper",
            detail=startup_detail,
            error="",
            interruption_class="false",
            interruption_signal="",
            wrapper_exit_category="startup_observe_only",
        )
        _safe_stderr_print(
            "STARTUP_STALE_CONTEXT_RESOLUTION "
            f"run_id={stale_run_id or 'missing'} "
            f"archive_attempt_reason={stale_archive.get('reason', 'not_attempted')} "
            f"terminal_mutation_applied={stale_terminal_mutation.get('applied', '0')} "
            f"terminal_mutation_reason={stale_terminal_mutation.get('reason', '')} "
            "action=continue_to_core"
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
        _safe_stderr_print(fatal_line)
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
        child_env = os.environ.copy()
        child_env["H_GUARD_WRAPPER_ACTIVE"] = "1"
        child_env["H_OWNER_CHAIN_SOURCE"] = "run_H_pricing_cycle_guarded.py"
        popen_kwargs = {"cwd": str(root), "env": child_env}
        if os.name == "nt":
            creation_flags = 0
            creation_flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            creation_flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
            # Keep the supervised core process isolated from launcher console/job
            # teardown so pilot waits cannot be interrupted by parent-shell exit.
            if os.environ.get("H_GUARDED_CHILD_DETACH", "0").strip() == "1":
                creation_flags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
                creation_flags |= int(getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
            if creation_flags:
                popen_kwargs["creationflags"] = creation_flags
            startupinfo = None
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0))
                startupinfo.wShowWindow = int(getattr(subprocess, "SW_HIDE", 0))
            except Exception:
                startupinfo = None
            if startupinfo is not None:
                popen_kwargs["startupinfo"] = startupinfo
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
        last_stale_defer_log = 0.0
        last_stale_observed_log = 0.0
        while True:
            try:
                rc = int(child.wait(timeout=1.0))
                break
            except subprocess.TimeoutExpired:
                current_run_for_liveness = _read_first_line(current_run_id_path)
                worker_lifecycle = _read_h_worker_lifecycle(worker_lifecycle_path)
                worker_run_id = str(worker_lifecycle.get("run_id", "")).strip()
                worker_state = str(worker_lifecycle.get("state", "")).strip().lower()
                heartbeat_age = _worker_heartbeat_age_seconds(worker_lifecycle)
                if (
                    current_run_for_liveness
                    and worker_run_id == current_run_for_liveness
                    and worker_state in {"pending", "claimed", "running", "finalizing"}
                    and heartbeat_age is not None
                    and heartbeat_age > worker_stale_seconds
                ):
                    intel_wait_active, intel_wait_reason = _phase1_intel_wait_active_for_child(
                        live=live,
                        run_id=current_run_for_liveness,
                        child_pid=child.pid,
                    )
                    pilot_wait_active, pilot_wait_reason = _phase1_pilot_wait_active_for_child(
                        live=live,
                        run_id=current_run_for_liveness,
                        child_pid=child.pid,
                        max_handoff_age_seconds=pilot_wait_stale_grace_seconds,
                    )
                    if intel_wait_active or pilot_wait_active:
                        defer_reason = intel_wait_reason if intel_wait_active else pilot_wait_reason
                        now_monotonic = time.monotonic()
                        if (now_monotonic - last_stale_defer_log) >= 15.0:
                            _append_text(
                                heartbeat,
                                (
                                    "worker_liveness_stale_deferred "
                                    f"run_id={current_run_for_liveness} "
                                    f"worker_state={worker_state} "
                                    f"heartbeat_age_seconds={heartbeat_age:.2f} "
                                    f"stale_after_seconds={worker_stale_seconds:.2f} "
                                    f"reason={defer_reason}\n"
                                ),
                            )
                            last_stale_defer_log = now_monotonic
                        continue
                    now_monotonic = time.monotonic()
                    if (now_monotonic - last_stale_observed_log) >= 15.0:
                        _append_text(
                            heartbeat,
                            (
                                "worker_liveness_stale_observed "
                                f"run_id={current_run_for_liveness} "
                                f"worker_state={worker_state} "
                                f"heartbeat_age_seconds={heartbeat_age:.2f} "
                                f"stale_after_seconds={worker_stale_seconds:.2f} "
                                "action=observe_only_no_child_terminate\n"
                            ),
                        )
                        last_stale_observed_log = now_monotonic
                    continue
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
            run_state = _read_h_run_state(run_state_path)
            worker_lifecycle = _read_h_worker_lifecycle(worker_lifecycle_path)
            publish_proof = _read_publish_proof_details(
                publish_info_path,
                expected_run_id=current_run_id,
            )
            terminal_truth = _classify_wrapper_terminal_truth(
                run_id=current_run_id,
                run_state=run_state,
                worker_lifecycle=worker_lifecycle,
                publish_proof=publish_proof,
            )
            _append_text(
                heartbeat,
                (
                    "wrapper_lifecycle_source "
                    "source=h_run_state_json "
                    f"path={run_state_path} "
                    f"run_id={current_run_id or 'missing'} "
                    f"state={terminal_truth.get('run_state_state', '') or 'missing'} "
                    f"publish_status={terminal_truth.get('run_state_publish_status', '') or 'missing'} "
                    f"reason={terminal_truth.get('reason', '') or 'missing'}\n"
                ),
            )
            if terminal_truth.get("ok", "0") == "1":
                _append_text(
                    heartbeat,
                    (
                        "wrapper_success_proof_verified "
                        f"run_id={current_run_id} "
                        f"run_state_state={terminal_truth.get('run_state_state', '') or 'missing'} "
                        f"worker_state={terminal_truth.get('worker_state', '') or 'missing'} "
                        f"publish_selected_run_id={terminal_truth.get('publish_selected_run_id', '') or 'missing'} "
                        "action=no_state_mutation\n"
                    ),
                )
            else:
                rc = 3
                boundary_code = _norm(terminal_truth.get("boundary_code", "")) or "WRAPPER_TERMINAL_TRUTH_UNRESOLVED"
                terminal_failure_detail = (
                    f"wrapper_boundary={boundary_code};"
                    f"reason={terminal_truth.get('reason', '') or 'missing'};"
                    f"run_state_state={terminal_truth.get('run_state_state', '') or 'missing'};"
                    f"run_state_stage={terminal_truth.get('run_state_stage', '') or 'missing'};"
                    f"run_state_publish_status={terminal_truth.get('run_state_publish_status', '') or 'missing'};"
                    f"worker_state={terminal_truth.get('worker_state', '') or 'missing'};"
                    f"publish_selected_run_id={terminal_truth.get('publish_selected_run_id', '') or 'missing'}"
                )[:500]
                terminal_mutation = _wrapper_terminalize_failed_run(
                    live=live,
                    run_id=current_run_id,
                    run_state_path=run_state_path,
                    worker_lifecycle_path=worker_lifecycle_path,
                    failure_code=boundary_code,
                    failure_detail=terminal_failure_detail,
                    stage_hint=_norm(terminal_truth.get("run_state_stage", "")),
                    publish_status_hint=_norm(terminal_truth.get("run_state_publish_status", "")),
                )
                run_in_progress_cleared = terminal_mutation.get("run_in_progress_cleared", "0")
                run_in_progress_clear_reason = terminal_mutation.get("run_in_progress_clear_reason", "missing")
                finalizer_line = (
                    f"{boundary_code} "
                    f"current={current_run_id or 'missing'} "
                    f"run_state_state={terminal_truth.get('run_state_state', '') or 'missing'} "
                    f"run_state_stage={terminal_truth.get('run_state_stage', '') or 'missing'} "
                    f"run_state_publish_status={terminal_truth.get('run_state_publish_status', '') or 'missing'} "
                    f"run_state_failure_code={terminal_truth.get('run_state_failure_code', '') or 'missing'} "
                    f"worker_run_id={terminal_truth.get('worker_run_id', '') or 'missing'} "
                    f"worker_state={terminal_truth.get('worker_state', '') or 'missing'} "
                    f"publish_selected_source={publish_proof.get('selected_source', '') or 'none'} "
                    f"publish_selected_run_id={terminal_truth.get('publish_selected_run_id', '') or 'missing'} "
                    f"publish_marker_path={publish_proof.get('publish_marker_path', '')} "
                    f"publish_marker_run_id={publish_proof.get('publish_marker_run_id', '') or 'missing'} "
                    f"publish_info_path={publish_proof.get('publish_info_path', '')} "
                    f"publish_info_run_id={publish_proof.get('publish_info_run_id', '') or 'missing'} "
                    f"terminal_mutation_applied={terminal_mutation.get('applied', '0')} "
                    f"terminal_mutation_reason={terminal_mutation.get('reason', '')} "
                    f"terminal_mutation_run_state_written={terminal_mutation.get('run_state_written', '0')} "
                    f"terminal_mutation_worker_written={terminal_mutation.get('worker_written', '0')} "
                    f"terminal_mutation_marker_written={terminal_mutation.get('terminal_marker_written', '0')} "
                    f"terminal_mutation_marker_reason={terminal_mutation.get('terminal_marker_reason', '')} "
                    f"run_in_progress_cleared={run_in_progress_cleared} "
                    f"run_in_progress_clear_reason={run_in_progress_clear_reason}"
                )
                _append_text(
                    heartbeat,
                    f"{finalizer_line}\n",
                )
                _append_text(
                    heartbeat,
                    (
                        "wrapper_terminal_state_no_mutation "
                        f"run_id={current_run_id or 'missing'} "
                        f"boundary_code={boundary_code} "
                        f"applied={terminal_mutation.get('applied', '0')} "
                        f"reason={terminal_mutation.get('reason', '')} "
                        f"run_state_written={terminal_mutation.get('run_state_written', '0')} "
                        f"worker_written={terminal_mutation.get('worker_written', '0')} "
                        f"marker_written={terminal_mutation.get('terminal_marker_written', '0')} "
                        f"run_in_progress_cleared={run_in_progress_cleared} "
                        f"run_in_progress_clear_reason={run_in_progress_clear_reason}\n"
                    ),
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
                    stage="guard_wrapper",
                    detail="wrapper_terminal_truth_failed",
                    error=boundary_code,
                    interruption_class="true" if interruption_class else "false",
                    interruption_signal=interruption_signal,
                    wrapper_exit_category=wrapper_exit_category,
                )
                _safe_stderr_print(finalizer_line)
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
                _safe_stderr_print(boundary_line)
            terminal_mutation = {
                "applied": "0",
                "reason": "missing_run_id",
                "run_state_written": "0",
                "worker_written": "0",
                "terminal_marker_written": "0",
                "run_in_progress_cleared": "0",
                "run_in_progress_clear_reason": "missing_run_id",
            }
            if current_run_id:
                failure_code = boundary_code if boundary_code != "child_rc" else f"CHILD_RC_{int(rc)}"
                failure_detail = (
                    boundary_line
                    or (
                        f"wrapper_child_exit "
                        f"boundary_code={boundary_code} "
                        f"child_rc={int(rc)} "
                        f"boundary_status={boundary_status or 'missing'} "
                        f"boundary_contract_stage={boundary_contract_stage or 'missing'}"
                    )
                )
                terminal_mutation = _wrapper_terminalize_failed_run(
                    live=live,
                    run_id=current_run_id,
                    run_state_path=run_state_path,
                    worker_lifecycle_path=worker_lifecycle_path,
                    failure_code=failure_code,
                    failure_detail=failure_detail,
                    stage_hint="phase1_intel",
                )
                _append_text(
                    heartbeat,
                    (
                        "wrapper_terminal_state_no_mutation "
                        f"run_id={current_run_id} "
                        f"boundary_code={boundary_code} "
                        f"child_rc={rc} "
                        f"applied={terminal_mutation.get('applied', '0')} "
                        f"reason={terminal_mutation.get('reason', '')} "
                        f"run_state_written={terminal_mutation.get('run_state_written', '0')} "
                        f"worker_written={terminal_mutation.get('worker_written', '0')} "
                        f"marker_written={terminal_mutation.get('terminal_marker_written', '0')} "
                        f"run_in_progress_cleared={terminal_mutation.get('run_in_progress_cleared', '0')} "
                        f"run_in_progress_clear_reason={terminal_mutation.get('run_in_progress_clear_reason', '')}\n"
                    ),
                )
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
                    f"terminal_mutation_applied={terminal_mutation.get('applied', '0')}\n"
                    f"terminal_mutation_reason={terminal_mutation.get('reason', '')}\n"
                    f"terminal_mutation_run_state_written={terminal_mutation.get('run_state_written', '0')}\n"
                    f"terminal_mutation_worker_written={terminal_mutation.get('worker_written', '0')}\n"
                    f"terminal_mutation_marker_written={terminal_mutation.get('terminal_marker_written', '0')}\n"
                    f"terminal_mutation_run_in_progress_cleared={terminal_mutation.get('run_in_progress_cleared', '0')}\n"
                    f"terminal_mutation_run_in_progress_clear_reason={terminal_mutation.get('run_in_progress_clear_reason', '')}\n"
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
