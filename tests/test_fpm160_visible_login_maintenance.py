from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager import FPM160_f061_visible_login_maintenance as fpm160
from scripts.flows.F.price_list_manager._schemas import LIVE_CYCLE_EVENT_COLUMNS, LIVE_CYCLE_STATUS_COLUMNS


class FakeProcess:
    pid = 12345


def test_fpm160_request_writes_f_only_visible_login_marker(tmp_path: Path) -> None:
    result = fpm160.request_visible_login_maintenance(tmp_path)
    marker = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "live"
        / "f061_visible_login.requested"
    )
    text = marker.read_text(encoding="ascii")
    events = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv",
        dtype=str,
    ).fillna("")

    assert result["status"] == "requested"
    assert marker.exists()
    assert "reason=visible_login" in text
    assert "exit_after_drain=0" in text
    assert not (tmp_path / "out" / "locks" / "maintenance.requested").exists()
    assert list(events.columns) == LIVE_CYCLE_EVENT_COLUMNS
    assert events.iloc[-1]["event_type"] == "visible_login_maintenance_request"


def test_fpm160_open_blocks_until_drain_ready(tmp_path: Path) -> None:
    fpm160.request_visible_login_maintenance(tmp_path)

    result = fpm160.open_visible_login_browser(
        tmp_path,
        wait_seconds=0,
        launcher=lambda _cmd, _cwd: FakeProcess(),
    )

    assert result["status"] == "blocked"
    assert result["block_reason"] == "drain_ready_missing"


def test_fpm160_open_launches_after_drain_ready(monkeypatch, tmp_path: Path) -> None:
    launched: list[list[str]] = []
    monkeypatch.setenv("F061_BBP_CHROME_EXE", str(tmp_path / "chrome.exe"))
    monkeypatch.setenv("F061_BBP_USER_DATA_DIR", str(tmp_path / "Chrome_UC136"))
    monkeypatch.setenv("F061_VISIBLE_LOGIN_PROFILE_DIR", "Profile 2")
    (tmp_path / "chrome.exe").write_text("", encoding="ascii")
    fpm160.request_visible_login_maintenance(tmp_path)
    fpm160.drain_ready_path(tmp_path).write_text("state=drain_wait\n", encoding="ascii")

    result = fpm160.open_visible_login_browser(
        tmp_path,
        wait_seconds=0,
        launcher=lambda cmd, _cwd: launched.append(cmd) or FakeProcess(),
    )

    assert result["status"] == "launched"
    assert result["pid"] == "12345"
    assert launched[0][0] == str(tmp_path / "chrome.exe")
    assert "--profile-directory=Profile 2" in launched[0]


def test_fpm160_clear_removes_request_and_ready_marker(tmp_path: Path) -> None:
    fpm160.request_visible_login_maintenance(tmp_path)
    fpm160.drain_ready_path(tmp_path).write_text("state=drain_wait\n", encoding="ascii")

    result = fpm160.clear_visible_login_maintenance(tmp_path)

    assert result["status"] == "cleared"
    assert result["request_removed"] == "1"
    assert result["drain_ready_removed"] == "1"
    assert not fpm160.visible_login_request_path(tmp_path).exists()
    assert not fpm160.drain_ready_path(tmp_path).exists()


def test_fpm160_status_reads_live_state(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-05-01T12:00:00Z",
                "run_id": "run",
                "owner_pid": "111",
                "state": "drain_wait",
                "active_supplier_id": "entertainment_trading",
                "active_f061_run_id": "et_run",
                "pending_rows": "18000",
                "last_action": "restart_drain",
                "last_action_status": "ready",
                "chunk_rows": "5",
                "drain_ready": "1",
                "notes": "maintenance_requested_boundary_wait",
            }
        ],
        columns=LIVE_CYCLE_STATUS_COLUMNS,
    ).to_csv(live_dir / "live_cycle_status.csv", index=False)
    fpm160.request_visible_login_maintenance(tmp_path)
    fpm160.drain_ready_path(tmp_path).write_text("state=drain_wait\n", encoding="ascii")

    result = fpm160.visible_login_status(tmp_path)

    assert result["request_exists"] == "1"
    assert result["drain_ready"] == "1"
    assert result["live_state"] == "drain_wait"
    assert result["pending_rows"] == "18000"
