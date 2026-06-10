from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager import FPM170_supervise_live_cycle as supervisor


def test_supervisor_decision_restarts_when_manager_missing() -> None:
    decision, reason = supervisor._supervisor_decision(
        manager_pids=[],
        manager_state={},
        child_state={},
        child_stdout_age_seconds=None,
        stale_seconds=900,
    )

    assert decision == "restart_manager"
    assert reason == "manager_process_missing"


def test_supervisor_decision_restarts_when_live_state_stale() -> None:
    now = datetime(2026, 5, 14, 13, 43, 0, tzinfo=timezone.utc)

    decision, reason = supervisor._supervisor_decision(
        manager_pids=[1234],
        manager_state={"updated_utc": "2026-05-14T11:33:32Z"},
        child_state={"heartbeat": "2026-05-14T11:33:32Z", "last_output_utc": "2026-05-14T11:33:30Z"},
        child_stdout_age_seconds=7800,
        stale_seconds=900,
        now=now,
    )

    assert decision == "restart_manager"
    assert reason.startswith("stale_live_state_seconds=")


def test_supervisor_decision_keeps_fresh_manager() -> None:
    now = datetime(2026, 5, 14, 13, 43, 0, tzinfo=timezone.utc)

    decision, reason = supervisor._supervisor_decision(
        manager_pids=[1234],
        manager_state={"updated_utc": "2026-05-14T13:42:32Z"},
        child_state={"heartbeat": "2026-05-14T13:42:32Z", "last_output_utc": "2026-05-14T13:42:30Z"},
        child_stdout_age_seconds=30,
        scanner_progress_age_seconds=25,
        stale_seconds=900,
        now=now,
    )

    assert decision == "ok"
    assert reason.startswith("process_alive_seconds=")
    assert "scanner_progress_seconds=" in reason


def test_supervisor_decision_does_not_call_fresh_heartbeat_real_progress() -> None:
    now = datetime(2026, 5, 14, 13, 43, 0, tzinfo=timezone.utc)

    decision, reason = supervisor._supervisor_decision(
        manager_pids=[1234],
        manager_state={"updated_utc": "2026-05-14T13:42:32Z"},
        child_state={"heartbeat": "2026-05-14T13:42:32Z", "last_output_utc": "2026-05-14T13:42:30Z"},
        child_stdout_age_seconds=30,
        scanner_progress_age_seconds=1900,
        stale_seconds=900,
        now=now,
    )

    assert decision == "alive_no_progress"
    assert "scanner_progress_seconds=1900.0" in reason


def test_supervise_once_launches_when_manager_missing(tmp_path: Path) -> None:
    launched: list[dict[str, object]] = []
    killed: list[list[int]] = []

    def fake_launch(root: Path, **kwargs: object) -> int:
        launched.append({"root": root, **kwargs})
        return 5678

    def fake_kill(root: Path, pids: list[int]) -> None:
        killed.append(pids)

    result = supervisor.supervise_once(
        root=tmp_path,
        process_finder=lambda _pattern: [],
        child_finder=lambda _pattern: [4321],
        launch_manager=fake_launch,
        terminate_pids=fake_kill,
        now=datetime(2026, 5, 14, 13, 43, 0, tzinfo=timezone.utc),
    )

    state_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "fpm_live_supervisor_state.txt"
    assert result["status"] == "restart_manager"
    assert result["launched_pid"] == 5678
    assert killed == [[4321]]
    assert launched
    assert "state=restart_manager" in state_path.read_text(encoding="ascii")


def test_supervise_once_pauses_when_drain_marker_present_and_manager_missing(tmp_path: Path) -> None:
    launched: list[dict[str, object]] = []
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_visible_login.requested").write_text(
        "requested_by=test|reason=state_repair|action=reload|exit_after_drain=1\n",
        encoding="ascii",
    )
    (live_dir / "F_restart_drain.ready").write_text(
        "launcher_pid=1234|utc=2026-05-15T09:53:06Z|state=drain_wait\n",
        encoding="ascii",
    )

    def fake_launch(root: Path, **kwargs: object) -> int:
        launched.append({"root": root, **kwargs})
        return 5678

    result = supervisor.supervise_once(
        root=tmp_path,
        process_finder=lambda _pattern: [],
        child_finder=lambda _pattern: [],
        launch_manager=fake_launch,
        now=datetime(2026, 5, 15, 9, 54, 0, tzinfo=timezone.utc),
    )

    state_path = live_dir / "fpm_live_supervisor_state.txt"
    assert result["status"] == "paused"
    assert result["launched_pid"] == 0
    assert launched == []
    assert "state=paused" in state_path.read_text(encoding="ascii")


def test_supervise_once_launches_when_only_orphan_drain_marker_exists(tmp_path: Path) -> None:
    launched: list[dict[str, object]] = []
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "F_restart_drain.ready").write_text(
        "launcher_pid=1234|utc=2026-05-20T01:20:02Z|state=drain_wait\n",
        encoding="ascii",
    )

    def fake_launch(root: Path, **kwargs: object) -> int:
        launched.append({"root": root, **kwargs})
        return 5678

    result = supervisor.supervise_once(
        root=tmp_path,
        process_finder=lambda _pattern: [],
        child_finder=lambda _pattern: [],
        launch_manager=fake_launch,
        now=datetime(2026, 5, 20, 12, 34, 0, tzinfo=timezone.utc),
    )

    state_path = live_dir / "fpm_live_supervisor_state.txt"
    assert result["status"] == "restart_manager"
    assert result["launched_pid"] == 5678
    assert launched
    assert "state=restart_manager" in state_path.read_text(encoding="ascii")


def test_supervise_once_uses_lock_pid_when_command_line_lookup_is_empty(tmp_path: Path, monkeypatch) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "live_cycle.lock").write_text(
        "pid=2468|start=2026-05-15T10:06:28Z|heartbeat=2026-05-15T10:06:58Z|owner=FPM130_live_cycle\n",
        encoding="ascii",
    )
    (live_dir / "f061_manager_mode_state.txt").write_text(
        "mode=Scanning Hidden|updated_utc=2026-05-15T10:06:58Z\n",
        encoding="ascii",
    )
    monkeypatch.setattr(supervisor, "_pid_alive", lambda root, pid: pid == 2468)

    result = supervisor.supervise_once(
        root=tmp_path,
        process_finder=lambda _pattern: [],
        child_finder=lambda _pattern: [],
        launch_manager=lambda root, **kwargs: 9999,
        now=datetime(2026, 5, 15, 10, 7, 0, tzinfo=timezone.utc),
    )

    assert result["status"] == "alive_no_progress"
    assert result["manager_pids"] == [2468]
    assert result["launched_pid"] == 0


def test_supervise_once_uses_fresh_lock_heartbeat_when_mode_state_is_idle_stale(
    tmp_path: Path, monkeypatch
) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "live_cycle.lock").write_text(
        "pid=2468|start=2026-05-18T08:41:49Z|heartbeat=2026-05-18T08:42:51Z|owner=FPM130_live_cycle\n",
        encoding="ascii",
    )
    (live_dir / "f061_manager_mode_state.txt").write_text(
        "mode=Scanning Hidden|updated_utc=2026-05-17T09:20:35Z\n",
        encoding="ascii",
    )
    monkeypatch.setattr(supervisor, "_pid_alive", lambda root, pid: pid == 2468)

    result = supervisor.supervise_once(
        root=tmp_path,
        process_finder=lambda _pattern: [],
        child_finder=lambda _pattern: [],
        launch_manager=lambda root, **kwargs: 9999,
        now=datetime(2026, 5, 18, 8, 43, 0, tzinfo=timezone.utc),
    )

    state_path = live_dir / "fpm_live_supervisor_state.txt"
    assert result["status"] == "alive_no_progress"
    assert result["manager_pids"] == [2468]
    assert result["launched_pid"] == 0
    state_text = state_path.read_text(encoding="ascii")
    assert "state=alive_no_progress" in state_text
    assert "progress_state=progress_missing" in state_text


def test_supervise_once_keeps_ok_only_when_scanner_chunk_progress_is_fresh(
    tmp_path: Path, monkeypatch
) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "live_cycle.lock").write_text(
        "pid=2468|start=2026-05-18T08:41:49Z|heartbeat=2026-05-18T08:42:51Z|owner=FPM130_live_cycle\n",
        encoding="ascii",
    )
    (live_dir / "f061_manager_mode_state.txt").write_text(
        "mode=Scanning Hidden|updated_utc=2026-05-18T08:42:51Z\n",
        encoding="ascii",
    )
    (live_dir / "live_cycle_events.csv").write_text(
        "event_utc,event_type,status,supplier_id,rows\n"
        "2026-05-18T08:42:40Z,scanner_chunk,success,td_synnex,25\n",
        encoding="ascii",
    )
    monkeypatch.setattr(supervisor, "_pid_alive", lambda root, pid: pid == 2468)

    result = supervisor.supervise_once(
        root=tmp_path,
        process_finder=lambda _pattern: [],
        child_finder=lambda _pattern: [],
        launch_manager=lambda root, **kwargs: 9999,
        now=datetime(2026, 5, 18, 8, 43, 0, tzinfo=timezone.utc),
    )

    state_path = live_dir / "fpm_live_supervisor_state.txt"
    state_text = state_path.read_text(encoding="ascii")
    assert result["status"] == "ok"
    assert result["launched_pid"] == 0
    assert "progress_state=scanner_progressing" in state_text
    assert "scanner_progress_utc=2026-05-18T08:42:40Z" in state_text
