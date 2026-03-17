from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
H_LIVE = ROOT / "out" / "systems" / "H" / "live"
H_RUN_IN_PROGRESS_PATH = H_LIVE / "H_run_in_progress.txt"
H_LAST_FINALIZED_RUN_ID_PATH = H_LIVE / "H_last_finalized_run_id.txt"
TOOL_NAME = "archive_failed_H_run.py"
TOOL_VERSION = "1"


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


def _h_boundary_path(run_id: str) -> Path:
    return H_LIVE / f"phase1_intel_alignment.boundary.{run_id}.json"


def _h_result_paths(run_id: str) -> list[Path]:
    return sorted(H_LIVE.glob(f"phase1_intel_alignment.result.{run_id}.*.json"))


def _h_wait_path(run_id: str) -> Path:
    return H_LIVE / f"phase1_intel_wait.{run_id}.json"


def _archive_marker_path(run_id: str) -> Path:
    return H_LIVE / f"H_failed_run_archived.{run_id}.json"


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


def _write_archive_marker(run_id: str, *, archive_reason: str) -> Path:
    boundary_path = _h_boundary_path(run_id)
    result_paths = _h_result_paths(run_id)
    wait_path = _h_wait_path(run_id)
    payload = {
        "run_id": run_id,
        "archived_at_utc": _utc_now(),
        "archive_reason": archive_reason,
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
    path = _archive_marker_path(run_id)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return path


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
        print(
            "archive_failed_h_run rejected: missing_failure_evidence "
            f"run_id={run_id} boundary_exists=false result_exists=false"
        )
        return 6

    archive_path = _archive_marker_path(run_id)
    if archive_path.exists():
        print(
            "archive_failed_h_run rejected: archive_marker_exists "
            f"run_id={run_id} path={archive_path}"
        )
        return 7

    written = _write_archive_marker(run_id, archive_reason=archive_reason)
    print(
        "archive_failed_h_run ok "
        f"run_id={run_id} "
        f"archive_path={written} "
        f"boundary_exists={'true' if boundary_path.exists() else 'false'} "
        f"result_exists={'true' if result_paths else 'false'} "
        f"run_in_progress_value={run_in_progress_value} "
        f"finalized_run_value={finalized_run_value or 'missing'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
