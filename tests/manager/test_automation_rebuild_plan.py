from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main
from sellerone_manager.automation_rebuild_plan import (
    PLAN_COLUMNS,
    build_automation_rebuild_plan,
    write_automation_rebuild_plan,
)


REVIEW_COLUMNS = [
    "source_type",
    "item_id",
    "name",
    "status",
    "kind",
    "target",
    "sellerone_scope",
    "recommendation",
    "luke_decision_required",
    "reason",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_fixture(root: Path) -> None:
    _write_csv(
        root / "sellerone_manager" / "CONTROL" / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv",
        REVIEW_COLUMNS,
        [
            {
                "source_type": "codex_automation",
                "item_id": "sellerone-manager-coordinator-pulse",
                "name": "SellerOne Weekend Hometime F Durability Pulse",
                "status": "PAUSED",
                "kind": "heartbeat",
                "sellerone_scope": "sellerone",
                "recommendation": "retire_old_heartbeat",
                "reason": "Old weekend/hometime pulse should not be resumed.",
            },
            {
                "source_type": "codex_automation",
                "item_id": "sellerone-manager-briefing-github-pulse",
                "name": "SellerOne Manager Briefing GitHub Pulse",
                "status": "PAUSED",
                "kind": "cron",
                "sellerone_scope": "sellerone",
                "recommendation": "candidate_rebuild_from_scratch",
                "reason": "Possible 2.1 Rep briefing.",
            },
            {
                "source_type": "codex_automation",
                "item_id": "diet-planner-weekly-press-play",
                "name": "Weekly Planner",
                "status": "PAUSED",
                "kind": "cron",
                "sellerone_scope": "external",
                "recommendation": "leave_paused_out_of_sellerone_scope",
                "reason": "Not SellerOne.",
            },
        ],
    )
    _write_csv(
        root / "sellerone_manager" / "CONTROL" / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv",
        ["task_name", "after_state", "exit_code"],
        [
            {"task_name": "AMZ Orders", "after_state": "Disabled", "exit_code": "0"},
            {"task_name": "AMZ Price List Manager", "after_state": "Disabled", "exit_code": "0"},
        ],
    )


def test_automation_rebuild_plan_builds_smaller_paused_candidate_set(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    result = build_automation_rebuild_plan(root=tmp_path, generated_utc="2026-06-08T16:00:00Z")
    rows_by_ref = {row["automation_ref"]: row for row in result.rows}

    assert result.proposed_count == 4
    assert result.deferred_count == 1
    assert result.created_paused_count == 0
    assert result.active_pilot_count == 0
    assert result.retired_old_count == 1
    assert result.active_old_count == 0
    assert result.windows_ready_count == 0
    assert rows_by_ref["SO21-REP-BRIEFING"]["status"] == "candidate_create_paused"
    assert rows_by_ref["SO21-REVIEW-WATCHER"]["status"] == "candidate_deferred"
    assert "Automations activated by this plan: 0" in result.markdown
    assert result.recommended_next_task == "SO21-AUTOMATION-ACTIVATION-DECISION"


def test_automation_rebuild_plan_marks_rep_briefing_created_paused_after_pilot_proof(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "SO21_REP_BRIEFING_PILOT.md").write_text("# Pilot\n", encoding="utf-8")

    result = build_automation_rebuild_plan(root=tmp_path, generated_utc="2026-06-08T16:00:00Z")
    rows_by_ref = {row["automation_ref"]: row for row in result.rows}

    assert rows_by_ref["SO21-REP-BRIEFING"]["status"] == "created_paused"
    assert result.proposed_count == 3
    assert result.created_paused_count == 1
    assert result.active_pilot_count == 0
    assert "Paused pilot automations already created: 1" in result.markdown


def test_automation_rebuild_plan_marks_rep_briefing_active_after_activation_proof(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "SO21_REP_BRIEFING_PILOT.md").write_text("# Pilot\n", encoding="utf-8")
    (control_dir / "SO21_REP_BRIEFING_ACTIVATION.md").write_text("# Activation\n", encoding="utf-8")

    result = build_automation_rebuild_plan(root=tmp_path, generated_utc="2026-06-08T16:00:00Z")
    rows_by_ref = {row["automation_ref"]: row for row in result.rows}

    assert rows_by_ref["SO21-REP-BRIEFING"]["status"] == "active_pilot"
    assert result.proposed_count == 3
    assert result.created_paused_count == 0
    assert result.active_pilot_count == 1
    assert result.recommended_next_task == "SO21-REP-BRIEFING-FIRST-RUN-PROOF"
    assert "Active approved pilot automations: 1" in result.markdown


def test_write_automation_rebuild_plan_writes_csv_and_markdown(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    result = write_automation_rebuild_plan(root=tmp_path, generated_utc="2026-06-08T16:00:00Z")

    assert result.csv_path.exists()
    assert result.markdown_path.exists()
    with result.csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == PLAN_COLUMNS
        rows = list(reader)
    assert len(rows) == 5
    assert "SO21-REP-BRIEFING" in result.markdown_path.read_text(encoding="utf-8")


def test_automation_rebuild_plan_cli_writes_outputs(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    exit_code = app_main(["--root", str(tmp_path), "--automation-rebuild-plan", "--observed-utc", "2026-06-08T16:00:00Z"])

    assert exit_code == 0
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "AUTOMATION_REBUILD_PLAN.csv").exists()
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "AUTOMATION_REBUILD.md").exists()
