from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scripts.one_off import HB_safe_recover_background as hb_recover


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _set_mtime(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    path.touch()
    path.stat()
    path.utime((ts, ts)) if hasattr(path, "utime") else None


def _patch_paths(monkeypatch, root: Path) -> None:
    out = root / "out"
    monkeypatch.setattr(hb_recover, "ROOT", root)
    monkeypatch.setattr(hb_recover, "OUT", out)
    monkeypatch.setattr(hb_recover, "LOCKS_DIR", out / "locks")
    monkeypatch.setattr(hb_recover, "H_LIVE", out / "systems" / "H" / "live")
    monkeypatch.setattr(hb_recover, "B_LIVE", out / "systems" / "B" / "live")
    monkeypatch.setattr(hb_recover, "RECOVERY_DIR", out / "locks" / "recovery")
    monkeypatch.setattr(hb_recover, "ALERT_STATE_GLOBAL", out / "system_health_alert_state.csv")
    monkeypatch.setattr(hb_recover, "ALERT_STATE_H", out / "system_health_alert_state_H.csv")
    monkeypatch.setattr(hb_recover, "ALERT_HISTORY_GLOBAL", out / "system_health_alert_history.csv")
    monkeypatch.setattr(hb_recover, "ALERT_HISTORY_H", out / "system_health_alert_history_H.csv")
    monkeypatch.setattr(hb_recover, "CHECKLIST_H", out / "cycle_alerts" / "checklist_H.csv")
    monkeypatch.setattr(hb_recover, "CHECKLIST_GLOBAL", out / "system_health_checklist.csv")


def test_clear_stale_runtime_artifacts_preserves_live_lock_and_clears_dead_lock(tmp_path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    now = datetime(2026, 4, 3, 9, 0, 0, tzinfo=timezone.utc)
    h_lock = hb_recover.H_LIVE / "H_pricing_cycle.lock"
    b_lock = hb_recover.B_LIVE / "B_cycle.lock"
    _write(h_lock, "H|pid=101|run_id=R1|start=2026-04-03T08:59:00Z|heartbeat=2026-04-03T08:59:50Z\n")
    _write(b_lock, "B|pid=202|start=2026-04-03T08:00:00Z|heartbeat=2026-04-03T08:00:10Z\n")
    _write(hb_recover.H_LIVE / "H_last_finalized_run_id.txt", "R0\n")

    monkeypatch.setattr(hb_recover, "_pid_alive", lambda pid: int(pid or 0) == 101)
    before_state = {"processes": {"owned_processes": []}}
    cleanup = hb_recover._clear_stale_runtime_artifacts(
        before_state=before_state,
        dry_run=False,
        archive_dir=hb_recover.RECOVERY_DIR / "archive" / "t1",
        heartbeat_max_age_seconds=180,
    )

    preserved = cleanup.get("preserved", [])
    removed = cleanup.get("removed", [])
    assert any(item.get("artifact") == "H_pricing_cycle.lock" and item.get("reason") == "owner_pid_alive" for item in preserved)
    assert any(item.get("artifact") == "B_cycle.lock" for item in removed)
    assert h_lock.exists()
    assert not b_lock.exists()


def test_clear_stale_runtime_artifacts_preserves_active_run_marker_when_owner_live(tmp_path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    now_utc = hb_recover._utc_ts()
    _write(hb_recover.H_LIVE / "H_run_in_progress.txt", "RUN123\n")
    _write(hb_recover.H_LIVE / "H_last_finalized_run_id.txt", "RUN122\n")
    _write(hb_recover.H_LIVE / "H_pricing_cycle.lock", f"H|pid=111|run_id=RUN123|start={now_utc}|heartbeat={now_utc}\n")
    monkeypatch.setattr(hb_recover, "_pid_alive", lambda pid: int(pid or 0) == 111)

    cleanup = hb_recover._clear_stale_runtime_artifacts(
        before_state={"processes": {"owned_processes": []}},
        dry_run=False,
        archive_dir=hb_recover.RECOVERY_DIR / "archive" / "t2",
        heartbeat_max_age_seconds=86400,
    )
    assert (hb_recover.H_LIVE / "H_run_in_progress.txt").exists()
    assert any(
        item.get("artifact") == "H_run_in_progress.txt" and item.get("reason") == "owner_evidence_still_live"
        for item in cleanup.get("preserved", [])
    )


def test_clear_stale_runtime_artifacts_clears_stale_run_marker_when_owner_dead(tmp_path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    _write(hb_recover.H_LIVE / "H_run_in_progress.txt", "RUN123\n")
    _write(hb_recover.H_LIVE / "H_last_finalized_run_id.txt", "RUN122\n")
    monkeypatch.setattr(hb_recover, "_pid_alive", lambda pid: False)

    cleanup = hb_recover._clear_stale_runtime_artifacts(
        before_state={"processes": {"owned_processes": []}},
        dry_run=False,
        archive_dir=hb_recover.RECOVERY_DIR / "archive" / "t3",
        heartbeat_max_age_seconds=180,
    )
    assert not (hb_recover.H_LIVE / "H_run_in_progress.txt").exists()
    assert any(item.get("artifact") == "H_run_in_progress.txt" for item in cleanup.get("removed", []))


def test_start_bat_hidden_uses_cmd_hidden_launcher(tmp_path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    bat = tmp_path / "run_example.bat"
    _write(bat, "@echo off\n")
    captured: dict[str, object] = {}

    class _FakeProc:
        pid = 4242

        @staticmethod
        def poll():
            return None

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["kwargs"] = dict(kwargs)
        return _FakeProc()

    monkeypatch.setattr(hb_recover.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(hb_recover.time, "sleep", lambda _seconds: None)
    result = hb_recover._start_bat_hidden(bat, dry_run=False)
    assert result.get("started") is True
    cmd = [str(part).lower() for part in captured.get("cmd", [])]
    assert cmd[:4] == ["cmd.exe", "/d", "/c", "call"]
    assert cmd[-1] == str(bat).lower()
    kwargs = dict(captured.get("kwargs", {}))
    assert kwargs.get("cwd") == str(hb_recover.ROOT)
    assert "creationflags" in kwargs


def test_query_repo_processes_uses_valid_hash_literal(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run(cmd, timeout=30, cwd=None):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    monkeypatch.setattr(hb_recover, "_run", _fake_run)
    rows = hb_recover._query_repo_processes()
    assert rows == []
    ps_script = str(captured.get("cmd", ["", "", "", ""])[-1])
    assert "[pscustomobject]@{pid=" in ps_script
    assert "@{{pid=" not in ps_script


def test_collect_state_marks_monitor_supervisor_running_from_process_snapshot(tmp_path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        hb_recover,
        "_query_repo_processes",
        lambda: [
            {
                "pid": "9001",
                "name": "cmd.exe",
                "command_line": "cmd.exe /d /c call C:\\repo\\run_home_time_monitor_supervisor.bat",
                "main_window_handle": "0",
            }
        ],
    )
    monkeypatch.setattr(hb_recover, "_pid_alive", lambda pid: False)
    state = hb_recover._collect_state(heartbeat_max_age_seconds=180)
    assert bool(state.get("truth", {}).get("monitor_supervisor_running", False)) is True
    assert int(state.get("truth", {}).get("visible_monitor_console_count", 0)) == 0


def test_collect_state_marks_h_owner_running_from_core_lock_without_launcher(tmp_path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    _write(
        hb_recover.H_LIVE / "H_pricing_cycle.lock",
        "H|pid=6408|run_id=R1|start=2026-04-03T13:00:00Z|heartbeat=2026-04-03T13:00:30Z\n",
    )
    monkeypatch.setattr(hb_recover, "_query_repo_processes", lambda: [])
    monkeypatch.setattr(hb_recover, "_pid_alive", lambda pid: int(pid or 0) == 6408)
    state = hb_recover._collect_state(heartbeat_max_age_seconds=180)
    assert bool(state.get("truth", {}).get("H_owner_running", False)) is True


def test_stop_scheduled_task_handles_not_running(monkeypatch, tmp_path) -> None:
    _patch_paths(monkeypatch, tmp_path)

    def _fake_run(cmd, timeout=30, cwd=None):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="ERROR: The task is not currently running.")

    monkeypatch.setattr(hb_recover, "_run", _fake_run)
    result = hb_recover._stop_scheduled_task("AMZ H Cycle", dry_run=False)
    assert result.get("stopped") is True
    assert result.get("reason") == "not_running"


def test_clear_resolved_alerts_with_live_evidence_clears_fail_and_writes_history(tmp_path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    now = datetime(2026, 4, 3, 9, 0, 0, tzinfo=timezone.utc)
    _write(hb_recover.H_LIVE / "H_cycle.log", "ok\n")
    _write(hb_recover.OUT / "phase1_runtime_floor_snapshot_latest.csv", "ok\n")
    _write(hb_recover.H_LIVE / "H_cycle_last_terminal_info.txt", "state=failed\nutc=2026-04-03T08:59:50Z\n")
    _write(hb_recover.H_LIVE / "H_cycle_last_publish_info.txt", "status=ok\nutc=2026-04-03T08:59:50Z\n")
    _write(
        hb_recover.ALERT_STATE_H,
        "check,status,first_seen_utc,last_seen_utc,consecutive_runs\nh_cycle_log_freshness,fail,2026-04-03T08:00:00Z,2026-04-03T08:50:00Z,5\n",
    )
    summary = hb_recover._clear_resolved_alerts_with_live_evidence(now_utc=now, dry_run=False)
    assert int(summary.get("total_cleared", 0)) == 1
    targets = list(summary.get("targets", []))
    h_target = next((row for row in targets if str(row.get("profile", "")).lower() == "h"), {})
    assert int(h_target.get("before_active_count", 0)) == 1
    assert int(h_target.get("after_active_count", 0)) == 0
    assert int(h_target.get("appended_history_count", 0)) == 1
    assert int(h_target.get("after_history_count", 0)) == int(h_target.get("before_history_count", 0)) + 1
    assert h_target.get("cleared")
    assert h_target.get("cleared")[0].get("clear_reason") == "contradicted_by_fresh_live_evidence"
    _cols, rows = hb_recover._csv_read_rows(hb_recover.ALERT_STATE_H)
    assert rows == []
    _hcols, hrows = hb_recover._csv_read_rows(hb_recover.ALERT_HISTORY_H)
    assert any(row.get("event_type") == "cleared" and row.get("check") == "h_cycle_log_freshness" for row in hrows)


def test_reconcile_stale_h_checklist_rows_with_live_evidence_marks_fail_as_ok(tmp_path, monkeypatch) -> None:
    _patch_paths(monkeypatch, tmp_path)
    now = datetime(2026, 4, 3, 9, 0, 0, tzinfo=timezone.utc)
    _write(hb_recover.H_LIVE / "H_cycle.log", "ok\n")
    _write(hb_recover.OUT / "phase1_runtime_floor_snapshot_latest.csv", "ok\n")
    _write(hb_recover.H_LIVE / "H_cycle_last_terminal_info.txt", "state=finalized\nutc=2026-04-03T08:59:50Z\n")
    _write(hb_recover.H_LIVE / "H_cycle_last_publish_info.txt", "status=ok\nutc=2026-04-03T08:59:50Z\n")
    _write(
        hb_recover.CHECKLIST_H,
        "check,status,value,notes\nh_cycle_log_freshness,fail,1,old_fail\nh_publish_marker_freshness,fail,1,old_fail\n",
    )
    summary = hb_recover._reconcile_stale_h_checklist_rows_with_live_evidence(now_utc=now, dry_run=False)
    assert int(summary.get("total_reconciled", 0)) == 2
    _cols, rows = hb_recover._csv_read_rows(hb_recover.CHECKLIST_H)
    statuses = {_norm_row.get("check", ""): _norm_row.get("status", "") for _norm_row in rows}
    assert statuses.get("h_cycle_log_freshness") == "ok"
    assert statuses.get("h_publish_marker_freshness") == "ok"
