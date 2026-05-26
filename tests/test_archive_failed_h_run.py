from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.tools import archive_failed_H_run as archive_tool


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _write(path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _patch_paths(monkeypatch, root: Path) -> tuple[Path, Path]:
    out = root / "out"
    live = out / "systems" / "H" / "live"
    lock_archive = out / "locks" / "archive"
    monkeypatch.setattr(archive_tool, "ROOT", root)
    monkeypatch.setattr(archive_tool, "OUT", out)
    monkeypatch.setattr(archive_tool, "H_LIVE", live)
    monkeypatch.setattr(archive_tool, "H_RUN_IN_PROGRESS_PATH", live / "H_run_in_progress.txt")
    monkeypatch.setattr(archive_tool, "H_LAST_FINALIZED_RUN_ID_PATH", live / "H_last_finalized_run_id.txt")
    monkeypatch.setattr(archive_tool, "H_RUN_STATE_PATH", live / "H_run_state.json")
    monkeypatch.setattr(archive_tool, "H_WORKER_LIFECYCLE_PATH", live / "H_worker_lifecycle.json")
    monkeypatch.setattr(archive_tool, "H_CYCLE_CURRENT_RUN_PATH", live / "H_cycle_current_run_id.txt")
    monkeypatch.setattr(archive_tool, "H_CYCLE_LAST_TERMINAL_INFO_PATH", live / "H_cycle_last_terminal_info.txt")
    monkeypatch.setattr(archive_tool, "LEGACY_H_CYCLE_LAST_TERMINAL_INFO_PATH", out / "H_cycle_last_terminal_info.txt")
    monkeypatch.setattr(archive_tool, "LOCK_ARCHIVE_DIR", lock_archive)
    monkeypatch.setattr(archive_tool, "_active_h_processes", lambda: [])
    return out, live


def _run_tool(monkeypatch, run_id: str, reason: str = "test_archive") -> int:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "archive_failed_H_run.py",
            "--run-id",
            run_id,
            "--archive-reason",
            reason,
        ],
    )
    return archive_tool.main()


def test_phase1_boundary_archive_keeps_existing_marker_behavior(tmp_path, monkeypatch) -> None:
    _, live = _patch_paths(monkeypatch, tmp_path)
    run_id = "RUN_PHASE_001"
    _write(live / "H_run_in_progress.txt", run_id + "\n")
    _write(live / "H_last_finalized_run_id.txt", "RUN_OLD\n")
    _write(live / f"phase1_intel_alignment.boundary.{run_id}.json", "{}\n")

    rc = _run_tool(monkeypatch, run_id)

    archive_path = live / f"H_failed_run_archived.{run_id}.json"
    payload = _read_json(archive_path)
    assert rc == 0
    assert payload["evidence_type"] == "phase1_boundary_or_result"
    assert (live / "H_run_in_progress.txt").read_text(encoding="utf-8").strip() == run_id
    assert not (live / "H_run_state.json").exists()


def test_startup_stale_lock_archive_marks_failed_and_clears_run_marker(tmp_path, monkeypatch) -> None:
    out, live = _patch_paths(monkeypatch, tmp_path)
    run_id = "RUN_STARTUP_002"
    owner_pid = "11111"
    _write(live / "H_run_in_progress.txt", run_id + "\n")
    _write(live / "H_last_finalized_run_id.txt", "RUN_OLD\n")
    _write(live / "H_cycle_current_run_id.txt", run_id + "\n")
    _write_json(
        live / "H_run_state.json",
        {
            "run_id": run_id,
            "state": "started",
            "utc": "2026-04-30T16:15:23Z",
            "owner_pid": owner_pid,
            "stage": "cycle_start",
            "publish_status": "not_started",
            "failure_code": "",
            "failure_detail": "",
        },
    )
    _write_json(
        live / "H_worker_lifecycle.json",
        {
            "run_id": run_id,
            "worker_id": owner_pid,
            "state": "running",
            "heartbeat_utc": "2026-04-30T16:15:44Z",
            "claim_owner_pid": owner_pid,
        },
    )
    _write(
        out / "locks" / "archive" / "H.lock.20260430T161643Z",
        f"H|pid={owner_pid}|run_id={run_id}|start=2026-04-30T16:15:23Z|heartbeat=2026-04-30T16:15:29Z\n",
    )
    monkeypatch.setattr(archive_tool, "_pid_alive", lambda _pid: False)

    rc = _run_tool(monkeypatch, run_id, reason="post_restart_startup_archive")

    archive_path = live / f"H_failed_run_archived.{run_id}.json"
    archive_payload = _read_json(archive_path)
    run_state = _read_json(live / "H_run_state.json")
    worker_state = _read_json(live / "H_worker_lifecycle.json")
    terminal_text = (live / "H_cycle_last_terminal_info.txt").read_text(encoding="utf-8")
    assert rc == 0
    assert archive_payload["evidence_type"] == "startup_stale_lock_dead_owner"
    assert archive_payload["startup_release_applied"] is True
    assert archive_payload["startup_release"]["run_in_progress_cleared"] is True
    assert not (live / "H_run_in_progress.txt").exists()
    assert (live / "H_last_finalized_run_id.txt").read_text(encoding="utf-8").strip() == "RUN_OLD"
    assert run_state["state"] == "failed"
    assert run_state["stage"] == "startup_archive"
    assert run_state["publish_status"] == "not_started"
    assert run_state["failure_code"] == archive_tool.STARTUP_RELEASE_FAILURE_CODE
    assert worker_state["state"] == "failed"
    assert worker_state["failure_code"] == archive_tool.STARTUP_RELEASE_FAILURE_CODE
    assert f"run_id={run_id}" in terminal_text
    assert "state=failed" in terminal_text
    assert "publish_status=not_started" in terminal_text


def test_startup_stale_lock_archive_refuses_when_owner_pid_is_alive(tmp_path, monkeypatch, capsys) -> None:
    out, live = _patch_paths(monkeypatch, tmp_path)
    run_id = "RUN_STARTUP_003"
    owner_pid = "22222"
    _write(live / "H_run_in_progress.txt", run_id + "\n")
    _write(live / "H_last_finalized_run_id.txt", "RUN_OLD\n")
    _write(live / "H_cycle_current_run_id.txt", run_id + "\n")
    _write_json(
        live / "H_run_state.json",
        {
            "run_id": run_id,
            "state": "started",
            "utc": "2026-04-30T16:15:23Z",
            "owner_pid": owner_pid,
            "stage": "cycle_start",
            "publish_status": "not_started",
        },
    )
    _write_json(live / "H_worker_lifecycle.json", {"run_id": run_id, "state": "running"})
    _write(
        out / "locks" / "archive" / "H.lock.20260430T161643Z",
        f"H|pid={owner_pid}|run_id={run_id}|start=2026-04-30T16:15:23Z|heartbeat=2026-04-30T16:15:29Z\n",
    )
    monkeypatch.setattr(archive_tool, "_pid_alive", lambda _pid: True)

    rc = _run_tool(monkeypatch, run_id)
    output = capsys.readouterr().out

    assert rc == 6
    assert "startup_reason=owner_pid_alive" in output
    assert (live / "H_run_in_progress.txt").read_text(encoding="utf-8").strip() == run_id
    assert not (live / f"H_failed_run_archived.{run_id}.json").exists()
