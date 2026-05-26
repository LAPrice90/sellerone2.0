from __future__ import annotations

import csv
from pathlib import Path
import json

from scripts.tools import due_check_register


def _write_register(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=due_check_register.REGISTER_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in due_check_register.REGISTER_COLUMNS})


def _base_row(**overrides: str) -> dict[str, str]:
    row = {
        "check_id": "CHECK_001",
        "title": "Check the thing",
        "owner_flow": "F",
        "status": "open",
        "due_utc": "2026-05-02T09:00:00Z",
        "trigger": "",
        "artifact_path": "out/example.csv",
        "success_condition": "expected row exists",
        "failure_action": "classify fix now",
        "created_utc": "2026-05-01T09:00:00Z",
        "updated_utc": "2026-05-01T09:00:00Z",
        "last_checked_utc": "",
        "last_result": "",
        "notes": "",
    }
    row.update(overrides)
    return row


def test_due_check_register_marks_due_rows_as_warn(tmp_path: Path) -> None:
    register_path = tmp_path / "register.csv"
    _write_register(register_path, [_base_row()])

    rows = due_check_register.build_due_check_status(
        register_path=register_path,
        observed_utc="2026-05-02T09:00:01Z",
    )

    assert rows[0]["due_state"] == "due"
    assert rows[0]["alert_status"] == "warn"


def test_due_check_register_keeps_future_rows_ok(tmp_path: Path) -> None:
    register_path = tmp_path / "register.csv"
    _write_register(register_path, [_base_row()])

    rows = due_check_register.build_due_check_status(
        register_path=register_path,
        observed_utc="2026-05-01T09:00:00Z",
    )

    assert rows[0]["due_state"] == "not_due"
    assert rows[0]["alert_status"] == "ok"


def test_due_check_register_accepts_bom_quoted_header(tmp_path: Path) -> None:
    register_path = tmp_path / "register.csv"
    register_path.write_text(
        "\ufeff\"check_id\",title,owner_flow,status,due_utc,trigger,artifact_path,"
        "success_condition,failure_action,created_utc,updated_utc,last_checked_utc,last_result,notes\n"
        "CHECK_BOM,Header check,F,open,2026-05-02T09:00:00Z,,out/example.csv,"
        "expected row exists,classify fix now,2026-05-01T09:00:00Z,"
        "2026-05-01T09:00:00Z,,,\n",
        encoding="utf-8",
    )

    rows = due_check_register.build_due_check_status(
        register_path=register_path,
        observed_utc="2026-05-01T09:00:00Z",
    )

    assert rows[0]["check_id"] == "CHECK_BOM"
    assert rows[0]["due_state"] == "not_due"
    assert rows[0]["alert_status"] == "ok"


def test_due_check_register_supports_trigger_based_rows(tmp_path: Path) -> None:
    register_path = tmp_path / "register.csv"
    _write_register(register_path, [_base_row(due_utc="", trigger="next batch boundary")])

    rows = due_check_register.build_due_check_status(
        register_path=register_path,
        observed_utc="2026-05-01T09:00:00Z",
    )

    assert rows[0]["due_state"] == "trigger_based"
    assert rows[0]["alert_status"] == "ok"


def test_due_check_register_flags_duplicate_ids_as_fail(tmp_path: Path) -> None:
    register_path = tmp_path / "register.csv"
    _write_register(
        register_path,
        [
            _base_row(check_id="DUPLICATE"),
            _base_row(check_id="DUPLICATE", title="Duplicate check"),
        ],
    )

    rows = due_check_register.build_due_check_status(
        register_path=register_path,
        observed_utc="2026-05-01T09:00:00Z",
    )

    assert [row["alert_status"] for row in rows] == ["fail", "fail"]
    assert all("duplicate_check_id" in row["notes"] for row in rows)


def test_due_check_register_flags_invalid_due_utc_as_fail(tmp_path: Path) -> None:
    register_path = tmp_path / "register.csv"
    _write_register(register_path, [_base_row(due_utc="tomorrow")])

    rows = due_check_register.build_due_check_status(
        register_path=register_path,
        observed_utc="2026-05-01T09:00:00Z",
    )

    assert rows[0]["due_state"] == "invalid_due_utc"
    assert rows[0]["alert_status"] == "fail"


def test_due_check_register_writes_status_csv(tmp_path: Path) -> None:
    register_path = tmp_path / "register.csv"
    output_path = tmp_path / "status.csv"
    _write_register(register_path, [_base_row()])

    summary = due_check_register.run_due_check_register(
        register_path=register_path,
        output_path=output_path,
        observed_utc="2026-05-01T09:00:00Z",
    )

    assert summary["status"] == "ok"
    assert summary["rows"] == 1
    with output_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert list(reader.fieldnames or []) == due_check_register.STATUS_COLUMNS
        status_rows = list(reader)
    assert status_rows[0]["check_id"] == "CHECK_001"


def test_due_check_register_executes_f_post_restart_mot_check(tmp_path: Path) -> None:
    register_path = tmp_path / "register.csv"
    _write_register(
        register_path,
        [
            _base_row(
                check_id="F_PRICE_LIST_POST_RESTART_MOT_DAILY",
                title="Run F price-list post-restart MOT check",
                owner_flow="F",
                due_utc="2026-05-21T08:00:00Z",
                artifact_path="out/cycle_alerts/f_price_list_post_restart_mot.csv",
            )
        ],
    )
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "out" / "locks" / "restart_control").mkdir(parents=True, exist_ok=True)
    (tmp_path / "out" / "locks" / "restart_control" / "restart_controller.latest.json").write_text(
        json.dumps(
            {
                "started_utc": "2026-05-21T01:10:01Z",
                "finished_utc": "2026-05-21T01:20:13Z",
                "outcome": "reboot_command_submitted",
                "drain_cleared": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "out" / "manifests" / "A" / "2026-05-21").mkdir(parents=True, exist_ok=True)
    (tmp_path / "out" / "manifests" / "A" / "2026-05-21" / "20260521T050103Z.json").write_text(
        json.dumps({"finished_utc": "2026-05-21T05:07:00Z", "final_state": "ok"}) + "\n",
        encoding="utf-8",
    )
    (live_dir / "fpm_live_supervisor_state.txt").write_text(
        "state=ok|reason=freshest_live_state_seconds=5.0|manager_pids=111|child_pids=222|updated_utc=2026-05-21T08:00:00Z\n",
        encoding="utf-8",
    )
    (live_dir / "live_cycle_status.csv").write_text(
        "\n".join(
            [
                "observed_utc,run_id,owner_pid,state,active_supplier_id,active_f061_run_id,pending_rows,last_action,last_action_status,chunk_rows,drain_ready,notes",
                "2026-05-21T08:00:00Z,fpm_live_1,111,running,td_synnex,f061_run,12,resume_f061_active_run,scanner_running,25,0,f061_child_started",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (live_dir / "live_cycle_events.csv").write_text(
        "event_utc,cycle_run_id,event_type,supplier_id,f061_run_id,status,rows,notes\n",
        encoding="utf-8",
    )

    rows = due_check_register.build_due_check_status(
        register_path=register_path,
        observed_utc="2026-05-21T08:00:01Z",
        root=tmp_path,
    )

    assert rows[0]["alert_status"] == "ok"
    assert rows[0]["last_result"] == "ok"
    assert "executable_check=1" in rows[0]["notes"]
    assert (tmp_path / "out" / "cycle_alerts" / "f_price_list_post_restart_mot.csv").exists()
