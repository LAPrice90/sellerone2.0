from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
H_LIVE = ROOT / "out" / "systems" / "H" / "live"
H_RUN_IN_PROGRESS_PATH = H_LIVE / "H_run_in_progress.txt"
H_LAST_FINALIZED_RUN_ID_PATH = H_LIVE / "H_last_finalized_run_id.txt"
H_RUN_STATE_PATH = H_LIVE / "H_run_state.json"
H_WORKER_LIFECYCLE_PATH = H_LIVE / "H_worker_lifecycle.json"
H_CYCLE_CURRENT_RUN_PATH = H_LIVE / "H_cycle_current_run_id.txt"
H_CYCLE_LAST_TERMINAL_INFO_PATH = H_LIVE / "H_cycle_last_terminal_info.txt"
LEGACY_H_CYCLE_LAST_TERMINAL_INFO_PATH = OUT / "H_cycle_last_terminal_info.txt"
LOCK_ARCHIVE_DIR = OUT / "locks" / "archive"
TOOL_NAME = "archive_failed_H_run.py"
TOOL_VERSION = "2"
TERMINAL_STATES = {"failed", "finalized", "succeeded", "success"}
STARTUP_RELEASE_STATES = {"started"}
STARTUP_RELEASE_STAGES = {"cycle_start"}
STARTUP_RELEASE_PUBLISH_STATUSES = {"not_started"}
STARTUP_RELEASE_FAILURE_CODE = "STARTUP_STALE_OWNER_LOCK_ARCHIVE_HARD_PROOF"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return _norm(path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except Exception:
        return ""


def _read_json_dict(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="ascii", errors="strict", newline="\n")
    os.replace(tmp, path)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _h_boundary_path(run_id: str) -> Path:
    return H_LIVE / f"phase1_intel_alignment.boundary.{run_id}.json"


def _h_result_paths(run_id: str) -> list[Path]:
    return sorted(H_LIVE.glob(f"phase1_intel_alignment.result.{run_id}.*.json"))


def _h_wait_path(run_id: str) -> Path:
    return H_LIVE / f"phase1_intel_wait.{run_id}.json"


def _archive_marker_path(run_id: str) -> Path:
    return H_LIVE / f"H_failed_run_archived.{run_id}.json"


def _pid_alive(pid: object) -> bool:
    pid_text = _norm(pid)
    if not pid_text.isdigit():
        return False
    pid_int = int(pid_text)
    if pid_int <= 0:
        return False
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_int}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=10,
            )
        except Exception:
            return False
        return str(pid_int) in (completed.stdout or "")
    try:
        os.kill(pid_int, 0)
    except OSError:
        return False
    return True


def _active_h_processes() -> list[dict[str, str]]:
    repo = str(ROOT).replace("'", "''")
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
    raw = _norm(completed.stdout)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return [{"pid": "unknown", "command_line": raw[:500]}]
    if isinstance(parsed, dict):
        parsed = [parsed]
    out: list[dict[str, str]] = []
    if not isinstance(parsed, list):
        return [{"pid": "unknown", "command_line": raw[:500]}]
    for item in parsed:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "pid": _norm(item.get("pid")),
                "command_line": _norm(item.get("command_line")),
            }
        )
    return out


def _parse_lock_line(line: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in str(line or "").strip().split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key_norm = _norm(key)
        if key_norm:
            out[key_norm] = _norm(value)
    if "pid" not in out:
        match = re.search(r"(?:^|\|)pid=(\d+)", str(line or ""))
        if match:
            out["pid"] = match.group(1)
    if "run_id" not in out:
        match = re.search(r"(?:^|\|)run_id=([^|\s]+)", str(line or ""))
        if match:
            out["run_id"] = match.group(1)
    return out


def _matching_stale_lock_archives(run_id: str, owner_pid: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    try:
        paths = sorted(LOCK_ARCHIVE_DIR.glob("H.lock.*"))
    except Exception:
        paths = []
    for path in paths:
        line = _read_first_line(path)
        meta = _parse_lock_line(line)
        if _norm(meta.get("run_id")) != run_id:
            continue
        if _norm(meta.get("pid")) != _norm(owner_pid):
            continue
        matches.append(
            {
                "path": str(path),
                "line": line,
                "pid": _norm(meta.get("pid")),
                "run_id": _norm(meta.get("run_id")),
                "heartbeat": _norm(meta.get("heartbeat")),
                "start": _norm(meta.get("start")),
            }
        )
    return matches


def _startup_stale_lock_evidence(run_id: str) -> dict[str, object]:
    run_state = _read_json_dict(H_RUN_STATE_PATH)
    worker_state = _read_json_dict(H_WORKER_LIFECYCLE_PATH)
    run_state_run_id = _norm(run_state.get("run_id"))
    worker_run_id = _norm(worker_state.get("run_id"))
    state_name = _norm(run_state.get("state")).lower()
    stage_name = _norm(run_state.get("stage")).lower()
    publish_status = _norm(run_state.get("publish_status")).lower()
    owner_pid = _norm(run_state.get("owner_pid")) or _norm(worker_state.get("claim_owner_pid"))
    current_cycle_run_id = _read_first_line(H_CYCLE_CURRENT_RUN_PATH)
    base: dict[str, object] = {
        "eligible": False,
        "evidence_type": "startup_stale_lock_dead_owner",
        "reason": "",
        "run_state_path": str(H_RUN_STATE_PATH),
        "worker_lifecycle_path": str(H_WORKER_LIFECYCLE_PATH),
        "current_cycle_run_id": current_cycle_run_id,
        "run_state_run_id": run_state_run_id,
        "worker_run_id": worker_run_id,
        "state": state_name,
        "stage": stage_name,
        "publish_status": publish_status,
        "owner_pid": owner_pid,
        "owner_pid_alive": False,
        "stale_lock_archive_path": "",
        "stale_lock_archive_line": "",
    }
    if run_state_run_id != run_id:
        base["reason"] = "run_state_mismatch"
        return base
    if state_name in TERMINAL_STATES:
        base["reason"] = "run_state_already_terminal"
        return base
    if state_name not in STARTUP_RELEASE_STATES:
        base["reason"] = "run_state_not_startup_release_state"
        return base
    if stage_name not in STARTUP_RELEASE_STAGES:
        base["reason"] = "stage_not_startup_release_stage"
        return base
    if publish_status not in STARTUP_RELEASE_PUBLISH_STATUSES:
        base["reason"] = "publish_status_not_startup_release_status"
        return base
    if not owner_pid:
        base["reason"] = "owner_pid_missing"
        return base
    owner_alive = _pid_alive(owner_pid)
    base["owner_pid_alive"] = owner_alive
    if owner_alive:
        base["reason"] = "owner_pid_alive"
        return base
    if current_cycle_run_id and current_cycle_run_id != run_id:
        base["reason"] = "current_cycle_run_id_mismatch"
        return base
    archives = _matching_stale_lock_archives(run_id, owner_pid)
    if not archives:
        base["reason"] = "matching_stale_lock_archive_missing"
        return base
    latest_archive = archives[-1]
    base["eligible"] = True
    base["reason"] = "startup_stale_lock_dead_owner_hard_proof"
    base["stale_lock_archive_path"] = latest_archive["path"]
    base["stale_lock_archive_line"] = latest_archive["line"]
    base["stale_lock_archive_count"] = len(archives)
    return base


def _terminal_marker_text(
    *,
    run_id: str,
    terminal_state: str,
    stage: str,
    publish_status: str,
    failure_code: str = "",
    failure_detail: str = "",
) -> str:
    return (
        f"run_id={run_id}\n"
        f"utc={_utc_now()}\n"
        f"state={_norm(terminal_state).lower()}\n"
        f"stage={_norm(stage)}\n"
        f"publish_status={_norm(publish_status)}\n"
        f"failure_code={_norm(failure_code)}\n"
        f"failure_detail={_norm(failure_detail)[:500]}\n"
    )


def _write_terminal_marker(
    *,
    run_id: str,
    terminal_state: str,
    stage: str,
    publish_status: str,
    failure_code: str,
    failure_detail: str,
) -> None:
    text = _terminal_marker_text(
        run_id=run_id,
        terminal_state=terminal_state,
        stage=stage,
        publish_status=publish_status,
        failure_code=failure_code,
        failure_detail=failure_detail,
    )
    _atomic_write_text(H_CYCLE_LAST_TERMINAL_INFO_PATH, text)
    _atomic_write_text(LEGACY_H_CYCLE_LAST_TERMINAL_INFO_PATH, text)


def _apply_startup_stale_lock_release(
    run_id: str,
    *,
    archive_path: Path,
    archive_reason: str,
    evidence: dict[str, object],
) -> dict[str, object]:
    now_utc = _utc_now()
    failure_detail = (
        f"archive_reason={archive_reason};"
        f"evidence_type=startup_stale_lock_dead_owner;"
        f"stale_lock_archive_path={_norm(evidence.get('stale_lock_archive_path'))}"
    )
    run_state = _read_json_dict(H_RUN_STATE_PATH)
    run_state.update(
        {
            "run_id": run_id,
            "state": "failed",
            "utc": now_utc,
            "owner_pid": _norm(evidence.get("owner_pid")),
            "stage": "startup_archive",
            "publish_status": "not_started",
            "failure_code": STARTUP_RELEASE_FAILURE_CODE,
            "failure_detail": failure_detail,
            "archive_marker_path": str(archive_path),
        }
    )
    _write_json(H_RUN_STATE_PATH, run_state)

    worker_state = _read_json_dict(H_WORKER_LIFECYCLE_PATH)
    worker_state.update(
        {
            "run_id": run_id,
            "worker_id": _norm(worker_state.get("worker_id")) or _norm(evidence.get("owner_pid")),
            "state": "failed",
            "terminal_utc": now_utc,
            "failure_code": STARTUP_RELEASE_FAILURE_CODE,
            "failure_detail": failure_detail,
            "archive_marker_path": str(archive_path),
        }
    )
    _write_json(H_WORKER_LIFECYCLE_PATH, worker_state)
    _write_terminal_marker(
        run_id=run_id,
        terminal_state="failed",
        stage="startup_archive",
        publish_status="not_started",
        failure_code=STARTUP_RELEASE_FAILURE_CODE,
        failure_detail=failure_detail,
    )

    current_marker = _read_first_line(H_RUN_IN_PROGRESS_PATH)
    cleared = False
    clear_reason = "marker_not_current_run"
    if current_marker == run_id:
        try:
            H_RUN_IN_PROGRESS_PATH.unlink(missing_ok=True)
            cleared = not H_RUN_IN_PROGRESS_PATH.exists()
            clear_reason = "cleared" if cleared else "unlink_failed"
        except Exception as exc:
            clear_reason = f"unlink_failed_{type(exc).__name__}"

    return {
        "release_applied": True,
        "release_utc": now_utc,
        "run_state_written": True,
        "worker_lifecycle_written": True,
        "terminal_marker_written": True,
        "run_in_progress_value_before_clear": current_marker,
        "run_in_progress_cleared": cleared,
        "run_in_progress_clear_reason": clear_reason,
        "failure_code": STARTUP_RELEASE_FAILURE_CODE,
    }


def _write_archive_marker(
    run_id: str,
    *,
    archive_reason: str,
    evidence_type: str = "phase1_boundary_or_result",
    extra: dict[str, object] | None = None,
) -> Path:
    boundary_path = _h_boundary_path(run_id)
    result_paths = _h_result_paths(run_id)
    wait_path = _h_wait_path(run_id)
    payload = {
        "run_id": run_id,
        "archived_at_utc": _utc_now(),
        "archive_reason": archive_reason,
        "evidence_type": evidence_type,
        "run_in_progress_value": _read_first_line(H_RUN_IN_PROGRESS_PATH),
        "finalized_run_value": _read_first_line(H_LAST_FINALIZED_RUN_ID_PATH),
        "boundary_exists": boundary_path.exists(),
        "boundary_path": str(boundary_path),
        "result_exists": bool(result_paths),
        "result_path": str(result_paths[-1]) if result_paths else "",
        "wait_artifact_exists": wait_path.exists(),
        "wait_artifact_path": str(wait_path),
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
    }
    if extra:
        payload.update(extra)
    path = _archive_marker_path(run_id)
    _write_json(path, payload)
    return path


def _update_archive_marker(path: Path, updates: dict[str, object]) -> None:
    payload = _read_json_dict(path)
    payload.update(updates)
    _write_json(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive and release a failed H run for launcher gating.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--archive-reason", default="operator_failed_run_archive")
    args = parser.parse_args()

    run_id = _norm(args.run_id)
    archive_reason = _norm(args.archive_reason) or "operator_failed_run_archive"
    if not run_id:
        print("archive_failed_h_run rejected: missing_run_id")
        return 2

    run_in_progress_value = _read_first_line(H_RUN_IN_PROGRESS_PATH)
    if run_in_progress_value != run_id:
        print(
            "archive_failed_h_run rejected: run_in_progress_mismatch "
            f"requested={run_id} current={run_in_progress_value or 'missing'}"
        )
        return 3

    finalized_run_value = _read_first_line(H_LAST_FINALIZED_RUN_ID_PATH)
    if finalized_run_value == run_id:
        print(
            "archive_failed_h_run rejected: already_finalized "
            f"run_id={run_id} finalized={finalized_run_value}"
        )
        return 4

    active_processes = _active_h_processes()
    if active_processes:
        active_pids = ",".join(_norm(item.get("pid")) or "unknown" for item in active_processes)
        print(
            "archive_failed_h_run rejected: active_h_python "
            f"run_id={run_id} pids={active_pids}"
        )
        return 5

    boundary_path = _h_boundary_path(run_id)
    result_paths = _h_result_paths(run_id)
    if not boundary_path.exists() and not result_paths:
        startup_evidence = _startup_stale_lock_evidence(run_id)
        if not startup_evidence.get("eligible"):
            print(
                "archive_failed_h_run rejected: missing_failure_evidence "
                f"run_id={run_id} boundary_exists=false result_exists=false "
                f"startup_release_eligible=false startup_reason={_norm(startup_evidence.get('reason')) or 'missing'}"
            )
            return 6
    else:
        startup_evidence = {}

    archive_path = _archive_marker_path(run_id)
    if archive_path.exists():
        print(
            "archive_failed_h_run rejected: archive_marker_exists "
            f"run_id={run_id} path={archive_path}"
        )
        return 7

    if startup_evidence.get("eligible"):
        written = _write_archive_marker(
            run_id,
            archive_reason=archive_reason,
            evidence_type="startup_stale_lock_dead_owner",
            extra={
                "startup_release_eligible": True,
                "startup_release_reason": _norm(startup_evidence.get("reason")),
                "startup_release_applied": False,
                "startup_evidence": startup_evidence,
            },
        )
        release = _apply_startup_stale_lock_release(
            run_id,
            archive_path=written,
            archive_reason=archive_reason,
            evidence=startup_evidence,
        )
        _update_archive_marker(
            written,
            {
                "startup_release_applied": bool(release.get("release_applied")),
                "startup_release": release,
            },
        )
        print(
            "archive_failed_h_run ok "
            f"run_id={run_id} "
            f"archive_path={written} "
            "evidence_type=startup_stale_lock_dead_owner "
            f"run_in_progress_cleared={'true' if release.get('run_in_progress_cleared') else 'false'} "
            f"clear_reason={_norm(release.get('run_in_progress_clear_reason'))} "
            f"finalized_run_value={finalized_run_value or 'missing'}"
        )
        return 0 if release.get("run_in_progress_cleared") else 9

    written = _write_archive_marker(run_id, archive_reason=archive_reason)
    print(
        "archive_failed_h_run ok "
        f"run_id={run_id} "
        f"archive_path={written} "
        "evidence_type=phase1_boundary_or_result "
        f"boundary_exists={'true' if boundary_path.exists() else 'false'} "
        f"result_exists={'true' if result_paths else 'false'} "
        f"run_in_progress_value={run_in_progress_value} "
        f"finalized_run_value={finalized_run_value or 'missing'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
