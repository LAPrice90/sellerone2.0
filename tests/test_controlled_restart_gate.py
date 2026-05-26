from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.tools import controlled_restart_gate as gate


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _set_mtime(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def test_b_gate_blocks_on_current_non_ok_checklist() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out = root / "out"
        b_live = out / "systems" / "B" / "live"
        locks = out / "locks"
        checklist = out / "cycle_alerts" / "checklist_B.csv"

        _write(checklist, "check,status,value,notes\nb_health,fail,1,broken\n")
        _write(b_live / "B_cycle.log", "2026-04-03T09:00:00Z [x] info\n")
        now = datetime(2026, 4, 3, 9, 0, 0, tzinfo=timezone.utc)
        _set_mtime(checklist, now)
        _set_mtime(b_live / "B_cycle.log", now)

        old_out = gate.OUT
        old_b_live = gate.B_LIVE
        old_locks = gate.LOCKS_DIR
        try:
            gate.OUT = out
            gate.B_LIVE = b_live
            gate.LOCKS_DIR = locks
            blockers, artifacts, _notes = gate._collect_b_state(
                180,
                restart_drain_owned=False,
                maintenance_ready_text="",
            )
        finally:
            gate.OUT = old_out
            gate.B_LIVE = old_b_live
            gate.LOCKS_DIR = old_locks

        assert "B_HEALTH_NOT_CLEAN" in blockers
        assert artifacts.get("checklist_B_stale_vs_runtime") is False


def test_b_gate_treats_stale_non_ok_checklist_as_non_blocking_context() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out = root / "out"
        b_live = out / "systems" / "B" / "live"
        locks = out / "locks"
        checklist = out / "cycle_alerts" / "checklist_B.csv"
        b_log = b_live / "B_cycle.log"

        _write(checklist, "check,status,value,notes\nb_health,fail,1,broken\n")
        _write(b_log, "2026-04-03T09:10:00Z [x] info\n")
        stale = datetime(2026, 4, 3, 8, 0, 0, tzinfo=timezone.utc)
        fresh = datetime(2026, 4, 3, 9, 10, 0, tzinfo=timezone.utc)
        _set_mtime(checklist, stale)
        _set_mtime(b_log, fresh)

        old_out = gate.OUT
        old_b_live = gate.B_LIVE
        old_locks = gate.LOCKS_DIR
        try:
            gate.OUT = out
            gate.B_LIVE = b_live
            gate.LOCKS_DIR = locks
            blockers, artifacts, notes = gate._collect_b_state(
                180,
                restart_drain_owned=False,
                maintenance_ready_text="",
            )
        finally:
            gate.OUT = old_out
            gate.B_LIVE = old_b_live
            gate.LOCKS_DIR = old_locks

        assert "B_HEALTH_NOT_CLEAN" not in blockers
        assert artifacts.get("checklist_B_stale_vs_runtime") is True
        assert int(artifacts.get("checklist_B_pending_stale_fail", 0)) == 1
        assert any("stale context" in note for note in notes)


def test_f_gate_accepts_manager_boundary_drain_ready() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out = root / "out"
        f_live = out / "systems" / "F" / "price_list_manager" / "live"
        f_live.mkdir(parents=True, exist_ok=True)
        now = gate._utc_ts()
        _write(f_live / "live_cycle.lock", f"pid={os.getpid()}|heartbeat={now}|owner=FPM130_live_cycle\n")
        _write(f_live / "F_restart_drain.ready", f"launcher_pid=123|utc={now}|state=drain_wait\n")

        old_f_live = gate.F_LIVE
        try:
            gate.F_LIVE = f_live
            blockers, artifacts, notes = gate._collect_f_state(180, restart_drain_owned=True)
        finally:
            gate.F_LIVE = old_f_live

        assert "F_MANAGER_ACTIVE_LOCK" not in blockers
        assert artifacts.get("restart_ready_boundary_pause") is True
        assert any("F manager in restart drain" in note for note in notes)


def test_f_gate_blocks_active_manager_without_drain_ready() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out = root / "out"
        f_live = out / "systems" / "F" / "price_list_manager" / "live"
        f_live.mkdir(parents=True, exist_ok=True)
        now = gate._utc_ts()
        _write(f_live / "live_cycle.lock", f"pid={os.getpid()}|heartbeat={now}|owner=FPM130_live_cycle\n")

        old_f_live = gate.F_LIVE
        try:
            gate.F_LIVE = f_live
            blockers, _artifacts, _notes = gate._collect_f_state(180, restart_drain_owned=True)
        finally:
            gate.F_LIVE = old_f_live

        assert "F_MANAGER_ACTIVE_LOCK" in blockers


def test_h_gate_infers_restart_boundary_from_notice_and_idle_finalized_state() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        h_live = root / "out" / "systems" / "H" / "live"
        h_live.mkdir(parents=True, exist_ok=True)
        now = gate._utc_ts()
        _write(
            h_live / "H_runtime_status.json",
            '{"mode":"IDLE","detail":"wrapper_exit_ok","error":"","run_id":"20260430T155103Z"}\n',
        )
        _write(h_live / "H_last_finalized_run_id.txt", "20260430T155103Z\n")
        _write(h_live / "H_launcher.lock", f"launcher_pid={os.getpid()}|utc={now}\n")
        _write(h_live / "H_launcher.heartbeat", f"launcher_pid={os.getpid()}|utc={now}|state=loop_ready\n")
        _write(h_live / "H_pricing_cycle.lock", f"H|pid={os.getpid()}|run_id=|start={now}|heartbeat={now}\n")
        _write(
            h_live / "H_restart_drain.notice.after_safe_cycle_boundary_wait.txt",
            "requested_by=controlled_restart_gate|reason=overnight_restart_eval\n",
        )

        old_h_live = gate.H_LIVE
        try:
            gate.H_LIVE = h_live
            blockers, artifacts, notes = gate._collect_h_state(180, restart_drain_owned=True)
        finally:
            gate.H_LIVE = old_h_live

        assert "H_LAUNCHER_ACTIVE" not in blockers
        assert "H_CYCLE_ACTIVE_LOCK" not in blockers
        assert artifacts.get("restart_drain_boundary_inferred") is True
        assert any("boundary inferred" in note for note in notes)


def test_h_gate_does_not_infer_restart_boundary_with_unfinalized_run() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        h_live = root / "out" / "systems" / "H" / "live"
        h_live.mkdir(parents=True, exist_ok=True)
        now = gate._utc_ts()
        _write(
            h_live / "H_runtime_status.json",
            '{"mode":"IDLE","detail":"wrapper_exit_ok","error":"","run_id":"20260430T155103Z"}\n',
        )
        _write(h_live / "H_run_in_progress.txt", "20260430T161200Z\n")
        _write(h_live / "H_last_finalized_run_id.txt", "20260430T155103Z\n")
        _write(h_live / "H_launcher.lock", f"launcher_pid={os.getpid()}|utc={now}\n")
        _write(h_live / "H_pricing_cycle.lock", f"H|pid={os.getpid()}|run_id=20260430T161200Z|start={now}|heartbeat={now}\n")
        _write(
            h_live / "H_restart_drain.notice.after_safe_cycle_boundary_wait.txt",
            "requested_by=controlled_restart_gate|reason=overnight_restart_eval\n",
        )

        old_h_live = gate.H_LIVE
        try:
            gate.H_LIVE = h_live
            blockers, artifacts, _notes = gate._collect_h_state(180, restart_drain_owned=True)
        finally:
            gate.H_LIVE = old_h_live

        assert "H_RUN_IN_PROGRESS_NOT_FINALIZED" in blockers
        assert "H_LAUNCHER_ACTIVE" in blockers
        assert "H_CYCLE_ACTIVE_LOCK" in blockers
        assert artifacts.get("restart_drain_boundary_inferred") is False
