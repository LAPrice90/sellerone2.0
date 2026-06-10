from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main
from sellerone_manager.dead_automation_scheduler_review import (
    REVIEW_COLUMNS,
    build_dead_automation_scheduler_review,
    write_dead_automation_scheduler_review,
)


SCHEDULER_COLUMNS = ["TaskName", "State", "TaskPath", "Actions"]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_automation(path: Path, *, item_id: str, name: str, status: str = "PAUSED", kind: str = "cron") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "automation.toml").write_text(
        "\n".join(
            [
                f'id = "{item_id}"',
                f'name = "{name}"',
                f'status = "{status}"',
                f'kind = "{kind}"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_fixture(root: Path, automation_root: Path) -> Path:
    _write_automation(
        automation_root / "sellerone-manager-coordinator-pulse",
        item_id="sellerone-manager-coordinator-pulse",
        name="SellerOne Weekend Hometime F Durability Pulse",
        kind="heartbeat",
    )
    _write_automation(
        automation_root / "sellerone-manager-briefing-github-pulse",
        item_id="sellerone-manager-briefing-github-pulse",
        name="SellerOne Manager Briefing GitHub Pulse",
    )
    _write_automation(
        automation_root / "diet-planner-weekly-press-play",
        item_id="diet-planner-weekly-press-play",
        name="Weekly Planner",
    )
    scheduler_snapshot = root / "scheduler_snapshot.csv"
    _write_csv(
        scheduler_snapshot,
        SCHEDULER_COLUMNS,
        [
            {
                "TaskName": "AMZ Morning MOT Post A",
                "State": "Ready",
                "TaskPath": "\\",
                "Actions": 'cmd.exe /d /c call "C:\\repo\\run_morning_mot_system.bat" --phase post_a --repair',
            },
            {
                "TaskName": "Codex_H_Phase1_OneShot",
                "State": "Disabled",
                "TaskPath": "\\",
                "Actions": "C:\\Temp\\codex_h_phase1_run.cmd",
            },
        ],
    )
    (root / "run_manager_hourly_mot.bat").write_text("@echo off\n", encoding="utf-8")
    return scheduler_snapshot


def test_dead_automation_scheduler_review_classifies_paused_and_ready_items(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    scheduler_snapshot = _write_fixture(tmp_path, automation_root)

    result = build_dead_automation_scheduler_review(
        root=tmp_path,
        generated_utc="2026-06-08T15:00:00Z",
        automation_root=automation_root,
        scheduler_snapshot_path=scheduler_snapshot,
    )
    rows_by_id = {row["item_id"]: row for row in result.rows}

    assert rows_by_id["sellerone-manager-coordinator-pulse"]["recommendation"] == "retire_old_heartbeat"
    assert rows_by_id["sellerone-manager-briefing-github-pulse"]["recommendation"] == "candidate_rebuild_from_scratch"
    assert rows_by_id["diet-planner-weekly-press-play"]["recommendation"] == "leave_paused_out_of_sellerone_scope"
    assert rows_by_id["AMZ Morning MOT Post A"]["recommendation"] == "disable_until_automation_rebuild"
    assert rows_by_id["AMZ Morning MOT Post A"]["luke_decision_required"] == "yes"
    assert rows_by_id["Codex_H_Phase1_OneShot"]["recommendation"] == "leave_disabled_or_inactive"
    assert result.active_codex_automation_count == 0
    assert result.paused_codex_automation_count == 3
    assert result.scheduler_pause_decision_required is True
    assert result.recommended_next_task == "SO21-WINDOWS-SCHEDULER-PAUSE-DECISION"
    assert "No automation or scheduler was restarted" in result.markdown


def test_write_dead_automation_scheduler_review_writes_csv_and_markdown(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    scheduler_snapshot = _write_fixture(tmp_path, automation_root)

    result = write_dead_automation_scheduler_review(
        root=tmp_path,
        generated_utc="2026-06-08T15:00:00Z",
        automation_root=automation_root,
        scheduler_snapshot_path=scheduler_snapshot,
    )

    assert result.csv_path.exists()
    assert result.markdown_path.exists()
    with result.csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == REVIEW_COLUMNS
        rows = list(reader)
    assert len(rows) == 6
    assert "Luke Decision Needed" in result.markdown_path.read_text(encoding="utf-8")


def test_dead_automation_scheduler_review_cli_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    automation_root = tmp_path / "automations"
    scheduler_snapshot = _write_fixture(tmp_path, automation_root)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))

    exit_code = app_main(
        [
            "--root",
            str(tmp_path),
            "--dead-automation-scheduler-review",
            "--scheduler-snapshot-file",
            str(scheduler_snapshot),
            "--observed-utc",
            "2026-06-08T15:00:00Z",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv").exists()
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").exists()


def test_dead_automation_scheduler_review_recommends_admin_pause_after_partial_pause(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    scheduler_snapshot = _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Ready,1\n",
        encoding="utf-8",
    )

    result = build_dead_automation_scheduler_review(
        root=tmp_path,
        generated_utc="2026-06-08T15:00:00Z",
        automation_root=automation_root,
        scheduler_snapshot_path=scheduler_snapshot,
    )

    assert result.recommended_next_task == "SO21-WINDOWS-SCHEDULER-ADMIN-PAUSE"
    assert "Admin Pause Still Required" in result.markdown


def test_dead_automation_scheduler_review_recommends_activation_after_rebuild_plan_exists(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_automation(
        automation_root / "sellerone-manager-coordinator-pulse",
        item_id="sellerone-manager-coordinator-pulse",
        name="SellerOne Weekend Hometime F Durability Pulse",
        kind="heartbeat",
    )
    scheduler_snapshot = tmp_path / "scheduler_snapshot.csv"
    _write_csv(
        scheduler_snapshot,
        SCHEDULER_COLUMNS,
        [
            {
                "TaskName": "AMZ Morning MOT Post A",
                "State": "Disabled",
                "TaskPath": "\\",
                "Actions": 'cmd.exe /d /c call "C:\\repo\\run_morning_mot_system.bat" --phase post_a --repair',
            },
        ],
    )
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ Morning MOT Post A,Disabled,0\n",
        encoding="utf-8",
    )
    (control_dir / "AUTOMATION_REBUILD.md").write_text("# Automation Rebuild\n", encoding="utf-8")

    result = build_dead_automation_scheduler_review(
        root=tmp_path,
        generated_utc="2026-06-08T15:00:00Z",
        automation_root=automation_root,
        scheduler_snapshot_path=scheduler_snapshot,
    )

    assert result.scheduler_pause_decision_required is False
    assert result.recommended_next_task == "SO21-AUTOMATION-ACTIVATION-DECISION"
    assert "SO21-AUTOMATION-ACTIVATION-DECISION" in result.markdown


def test_dead_automation_scheduler_review_classifies_so21_rep_briefing_as_paused_pilot(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_automation(
        automation_root / "so21-rep-briefing",
        item_id="so21-rep-briefing",
        name="SO21-REP-BRIEFING",
        status="PAUSED",
    )

    result = build_dead_automation_scheduler_review(
        root=tmp_path,
        generated_utc="2026-06-08T15:00:00Z",
        automation_root=automation_root,
        scheduler_rows=[],
    )
    rows_by_id = {row["item_id"]: row for row in result.rows}

    assert rows_by_id["so21-rep-briefing"]["sellerone_scope"] == "sellerone"
    assert rows_by_id["so21-rep-briefing"]["recommendation"] == "pilot_created_paused"
    assert rows_by_id["so21-rep-briefing"]["luke_decision_required"] == "no"


def test_dead_automation_scheduler_review_flags_active_so21_rep_briefing_without_activation_proof(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_automation(
        automation_root / "so21-rep-briefing",
        item_id="so21-rep-briefing",
        name="SO21-REP-BRIEFING",
        status="ACTIVE",
    )

    result = build_dead_automation_scheduler_review(
        root=tmp_path,
        generated_utc="2026-06-08T15:00:00Z",
        automation_root=automation_root,
        scheduler_rows=[],
    )
    rows_by_id = {row["item_id"]: row for row in result.rows}

    assert rows_by_id["so21-rep-briefing"]["recommendation"] == "pause_or_replace_before_2_1"
    assert rows_by_id["so21-rep-briefing"]["luke_decision_required"] == "yes"


def test_dead_automation_scheduler_review_accepts_active_so21_rep_briefing_with_activation_proof(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_automation(
        automation_root / "so21-rep-briefing",
        item_id="so21-rep-briefing",
        name="SO21-REP-BRIEFING",
        status="ACTIVE",
    )
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "SO21_REP_BRIEFING_ACTIVATION.md").write_text("# Activation\n", encoding="utf-8")

    result = build_dead_automation_scheduler_review(
        root=tmp_path,
        generated_utc="2026-06-08T15:00:00Z",
        automation_root=automation_root,
        scheduler_rows=[],
    )
    rows_by_id = {row["item_id"]: row for row in result.rows}

    assert rows_by_id["so21-rep-briefing"]["recommendation"] == "pilot_active_approved"
    assert rows_by_id["so21-rep-briefing"]["luke_decision_required"] == "no"
    assert result.recommended_next_task == "SO21-REP-BRIEFING-FIRST-RUN-PROOF"
