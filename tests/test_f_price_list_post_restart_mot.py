from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.tools import f_price_list_post_restart_mot as mot


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _seed_base(root: Path, *, observed_utc: str = "2026-05-21T08:00:00Z") -> Path:
    live_dir = root / "out" / "systems" / "F" / "price_list_manager" / "live"
    _write(
        root / "out" / "locks" / "restart_control" / "restart_controller.latest.json",
        json.dumps(
            {
                "started_utc": "2026-05-21T01:10:01Z",
                "finished_utc": "2026-05-21T01:20:13Z",
                "outcome": "reboot_command_submitted",
                "drain_cleared": True,
            }
        )
        + "\n",
    )
    _write(
        root / "out" / "manifests" / "A" / "2026-05-21" / "20260521T050103Z.json",
        json.dumps({"finished_utc": "2026-05-21T05:07:00Z", "final_state": "ok"}) + "\n",
    )
    _write(
        live_dir / "fpm_live_supervisor_state.txt",
        f"state=ok|reason=freshest_live_state_seconds=5.0|manager_pids=111|child_pids=222|updated_utc={observed_utc}\n",
    )
    _write(
        live_dir / "live_cycle_status.csv",
        "\n".join(
            [
                "observed_utc,run_id,owner_pid,state,active_supplier_id,active_f061_run_id,pending_rows,last_action,last_action_status,chunk_rows,drain_ready,notes",
                f"{observed_utc},fpm_live_1,111,running,td_synnex,f061_run,12,resume_f061_active_run,scanner_running,25,0,f061_child_started",
            ]
        )
        + "\n",
    )
    _write(
        live_dir / "live_cycle_events.csv",
        "event_utc,cycle_run_id,event_type,supplier_id,f061_run_id,status,rows,notes\n",
    )
    return live_dir


def test_f_post_restart_mot_passes_on_fresh_running_state(tmp_path: Path) -> None:
    _seed_base(tmp_path)

    summary = mot.run_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")

    assert summary["status"] == "ok"
    assert summary["fail_rows"] == 0
    output_path = Path(str(summary["output_path"]))
    with output_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert list(reader.fieldnames or []) == mot.CHECK_COLUMNS
    assert any(row["check"] == "f_supervisor_state" and row["status"] == "ok" for row in rows)


def test_f_post_restart_mot_fails_orphan_drain_marker_before_a(tmp_path: Path) -> None:
    live_dir = _seed_base(tmp_path)
    _write(
        live_dir / "F_restart_drain.ready",
        "launcher_pid=1234|utc=2026-05-21T01:20:02Z|state=drain_wait\n",
    )
    _write(
        live_dir / "live_cycle_status.csv",
        "\n".join(
            [
                "observed_utc,run_id,owner_pid,state,active_supplier_id,active_f061_run_id,pending_rows,last_action,last_action_status,chunk_rows,drain_ready,notes",
                "2026-05-21T01:20:02Z,fpm_live_1,111,drain_wait,td_synnex,f061_run,52270,drain_wait,pending,25,1,maintenance_requested_boundary_wait",
            ]
        )
        + "\n",
    )

    summary = mot.run_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")

    assert summary["status"] == "fail"
    assert summary["cause_anchor"] == "post_restart_or_f_owner_issue"
    rows = mot.build_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")["rows"]
    assert any(row["check"] == "f_orphan_restart_drain_marker" and row["status"] == "fail" for row in rows)


def test_f_post_restart_mot_fails_stale_supervisor_state(tmp_path: Path) -> None:
    live_dir = _seed_base(tmp_path)
    _write(
        live_dir / "fpm_live_supervisor_state.txt",
        "state=ok|reason=freshest_live_state_seconds=5.0|manager_pids=111|child_pids=222|updated_utc=2026-05-21T07:00:00Z\n",
    )

    summary = mot.run_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z", stale_seconds=900)

    assert summary["status"] == "fail"
    rows = mot.build_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z", stale_seconds=900)["rows"]
    assert any(row["check"] == "f_supervisor_state" and row["value"] == "stale" for row in rows)


def test_f_post_restart_mot_fails_active_login_request_without_child(tmp_path: Path) -> None:
    live_dir = _seed_base(tmp_path)
    _write(
        live_dir / "f061_login_mode.requested",
        "\n".join(
            [
                "requested_utc=2026-05-21T07:50:00Z",
                "requested_by=operator_ui",
                "status=requested",
                "hold_seconds=900",
            ]
        )
        + "\n",
    )

    summary = mot.run_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")

    assert summary["status"] == "fail"
    rows = mot.build_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")["rows"]
    assert any(
        row["check"] == "f_login_mode_child_started" and row["value"] == "active_request_without_child"
        for row in rows
    )


def test_f_post_restart_mot_accepts_login_child_started_after_request(tmp_path: Path) -> None:
    live_dir = _seed_base(tmp_path)
    _write(
        live_dir / "f061_login_mode.requested",
        "\n".join(
            [
                "requested_utc=2026-05-21T07:50:00Z",
                "requested_by=operator_ui",
                "status=holding",
                "hold_seconds=900",
            ]
        )
        + "\n",
    )
    _write(
        live_dir / "live_cycle_events.csv",
        "\n".join(
            [
                "event_utc,cycle_run_id,event_type,supplier_id,f061_run_id,status,rows,notes",
                "2026-05-21T07:51:00Z,fpm_live_1,login_mode_child_started,td_synnex,f061_run,started,3,hold_seconds=900",
            ]
        )
        + "\n",
    )

    summary = mot.run_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")

    assert summary["status"] == "ok"
    rows = mot.build_f_post_restart_mot(root=tmp_path, observed_utc="2026-05-21T08:00:00Z")["rows"]
    assert any(row["check"] == "f_login_mode_child_started" and row["status"] == "ok" for row in rows)
