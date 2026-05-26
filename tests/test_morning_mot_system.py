from __future__ import annotations

import json
from pathlib import Path

from scripts.tools import morning_mot_system as mot


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _seed_f_ok(root: Path, observed: str = "2026-05-21T05:30:00Z") -> None:
    live = root / "out" / "systems" / "F" / "price_list_manager" / "live"
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
        live / "fpm_live_supervisor_state.txt",
        f"state=ok|reason=freshest_live_state_seconds=5.0|manager_pids=111|child_pids=222|updated_utc={observed}\n",
    )
    _write(
        live / "live_cycle_status.csv",
        "\n".join(
            [
                "observed_utc,run_id,owner_pid,state,active_supplier_id,active_f061_run_id,pending_rows,last_action,last_action_status,chunk_rows,drain_ready,notes",
                f"{observed},fpm_live_1,111,running,td_synnex,f061_run,12,resume_f061_active_run,scanner_running,25,0,f061_child_started",
            ]
        )
        + "\n",
    )
    _write(live / "live_cycle_events.csv", "event_utc,cycle_run_id,event_type,supplier_id,f061_run_id,status,rows,notes\n")


def _seed_register(root: Path) -> None:
    _write(
        root / "project_control" / "DUE_CHECK_REGISTER.csv",
        "\n".join(
            [
                "check_id,title,owner_flow,status,due_utc,trigger,artifact_path,success_condition,failure_action,created_utc,updated_utc,last_checked_utc,last_result,notes",
                "CHECK_001,Example,F,completed,2026-05-21T08:00:00Z,,out/example.csv,ok,none,2026-05-20T00:00:00Z,2026-05-20T00:00:00Z,,,",
            ]
        )
        + "\n",
    )


def _seed_current_a(root: Path) -> None:
    _write(
        root / "out" / "manifests" / "A" / "2026-05-21" / "20260521T050700Z.json",
        json.dumps({"finished_utc": "2026-05-21T05:07:00Z", "final_state": "ok"}) + "\n",
    )


def _seed_current_e(root: Path) -> None:
    _write(
        root / "out" / "manifests" / "E" / "2026-05-21" / "E_20260521T051000Z.json",
        json.dumps({"finished_utc": "2026-05-21T05:10:00Z", "final_state": "ok"}) + "\n",
    )


def test_post_a_flags_stale_a_without_auto_repair(tmp_path: Path, monkeypatch) -> None:
    _seed_register(tmp_path)
    _seed_f_ok(tmp_path)
    monkeypatch.setattr(mot, "_scheduled_task_state", lambda name: {"state": "Ready", "enabled": "True"})

    summary = mot.build_morning_mot_system_check(
        root=tmp_path,
        phase="post_a",
        observed_utc="2026-05-21T05:30:00Z",
    )

    a_row = next(row for row in summary["rows"] if row["system"] == "A")
    assert a_row["status"] == "fail"
    assert a_row["classification"] == "needs user decision"
    assert "requires_allow_a_repair" in a_row["repair_action"]


def test_stale_b_and_h_plan_scheduler_repairs(tmp_path: Path, monkeypatch) -> None:
    _seed_register(tmp_path)
    _seed_current_a(tmp_path)
    _seed_current_e(tmp_path)
    _seed_f_ok(tmp_path)
    monkeypatch.setattr(mot, "_scheduled_task_state", lambda name: {"state": "Ready", "enabled": "True"})
    monkeypatch.setattr(mot, "_pid_alive", lambda pid: False)

    summary = mot.build_morning_mot_system_check(
        root=tmp_path,
        phase="post_a",
        observed_utc="2026-05-21T05:30:00Z",
    )

    b_row = next(row for row in summary["rows"] if row["system"] == "B")
    h_row = next(row for row in summary["rows"] if row["system"] == "H")
    assert b_row["status"] == "fail"
    assert b_row["repair_action"] == "start_task:AMZ Orders"
    assert h_row["status"] == "fail"
    assert h_row["repair_action"] == "start_task:AMZ H Cycle"


def test_execute_repairs_skips_a_without_allow_flag(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(mot, "_start_scheduled_task", lambda task_name: calls.append(task_name) or {"status": "ok"})

    actions = mot.execute_repairs(
        [
            {
                "status": "fail",
                "repair_action": "start_task:AMZ Pricing Summary:requires_allow_a_repair",
            }
        ],
        allow_a_repair=False,
    )

    assert calls == []
    assert actions[0]["status"] == "skipped"
    assert "requires --allow-a-repair" in actions[0]["reason"]


def test_run_writes_schema_outputs(tmp_path: Path, monkeypatch) -> None:
    _seed_register(tmp_path)
    _seed_current_a(tmp_path)
    _seed_current_e(tmp_path)
    _seed_f_ok(tmp_path)
    monkeypatch.setattr(mot, "_scheduled_task_state", lambda name: {"state": "Ready", "enabled": "True"})
    monkeypatch.setattr(mot, "_pid_alive", lambda pid: False)

    summary = mot.run_morning_mot_system(
        root=tmp_path,
        phase="post_a",
        observed_utc="2026-05-21T05:30:00Z",
        proof_wait_seconds=0,
    )

    assert summary["output_path"].endswith("morning_mot_system_check.csv")
    assert summary["single_mot_path"].endswith("morning_mot_latest.md")
    assert (tmp_path / "out" / "cycle_alerts" / "morning_mot_system_check.csv").exists()
    assert (tmp_path / "out" / "cycle_alerts" / "morning_mot_system_check.json").exists()
    assert (tmp_path / "out" / "cycle_alerts" / "morning_mot_repair_actions.json").exists()
    mot_text = (tmp_path / "out" / "cycle_alerts" / "morning_mot_latest.md").read_text(encoding="utf-8")
    assert "SellerOne Morning MOT" in mot_text
    assert "## Restart" in mot_text
