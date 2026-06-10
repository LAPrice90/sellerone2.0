from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main
from sellerone_manager.current_work_markdown import build_current_work_markdown, write_current_work_markdown
from sellerone_manager.schemas import APPROVED_TASK_PACKET_COLUMNS


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_fixture(root: Path) -> None:
    control_dir = root / "sellerone_manager" / "CONTROL"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "QUEUE_CONTRACT.md").write_text("# Queue\n", encoding="utf-8")
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage Policy\n", encoding="utf-8")
    _write_csv(
        control_dir / "STORAGE_INDEX.csv",
        ["path", "proof_or_blocker"],
        [{"path": "out", "proof_or_blocker": "needs out subtree index"}],
    )
    _write_csv(
        root / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {
                "task_id": "MOT_F_AUTH_STATE",
                "job_ref": "F-SELLER-CENTRAL-ELIGIBILITY",
                "flow": "F",
                "status": "approved",
                "priority": "high",
                "title": "F MOT: seller central eligibility needs repair",
                "luke_action_required": "0",
                "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
                "allowed_scope": "Do not leak raw scope into the front desk file.",
            },
            {
                "task_id": "MOT_F_BROWSER_SESSION",
                "job_ref": "F-BROWSER-SESSION-DURABILITY",
                "flow": "F",
                "status": "fixed_needs_retest",
                "priority": "high",
                "title": "F Browser Session Durability",
                "luke_action_required": "0",
                "retest_command": "python -m pytest tests/test_f_login_controller.py -q",
            },
            {
                "task_id": "MOT_B_TOKEN_DECISION",
                "job_ref": "B-B008-TOKEN-STATE-CONFLICT",
                "flow": "B",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "B B008 Token State Conflict Decision",
                "luke_action_required": "1",
                "notes": "Luke must choose whether this protected token correction is approved.",
            },
            {
                "task_id": "MGR_H_OLD_CARD",
                "job_ref": "H-HISTORICAL-CARD",
                "flow": "H",
                "status": "parked",
                "priority": "normal",
                "title": "Historical card",
                "luke_action_required": "0",
                "notes": "Parked until a future H cleanup ticket is opened.",
            },
            {
                "task_id": "MGR_OLD_PROOF",
                "job_ref": "M-OLD-PROOF",
                "flow": "M",
                "status": "proved",
                "priority": "low",
                "title": "Old proof",
                "luke_action_required": "0",
            },
        ],
    )
    _write_csv(
        root / "out" / "systems" / "M" / "mot" / "mot_worklist.csv",
        [
            "work_item_id",
            "job_ref",
            "flow",
            "status",
            "priority",
            "title",
            "manager_action",
            "luke_action_required",
        ],
        [
            {
                "work_item_id": "MOT_O_READINESS",
                "job_ref": "O-USER-WORKING-READINESS",
                "flow": "O",
                "status": "new",
                "priority": "high",
                "title": "O user working readiness needs repair",
                "manager_action": "Create a bounded O user-working repair packet.",
                "luke_action_required": "0",
            },
            {
                "work_item_id": "MOT_F_AUTH_STATE",
                "job_ref": "F-SELLER-CENTRAL-ELIGIBILITY",
                "flow": "F",
                "status": "new",
                "priority": "high",
                "title": "Already packeted",
                "manager_action": "Do not duplicate this active packet.",
                "luke_action_required": "0",
            },
        ],
    )


def test_current_work_markdown_splits_active_backlog_and_candidates(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    current = result.current_tickets_markdown
    backlog = result.backlog_markdown
    assert "## Active Builder And Reviewer Tickets" in current
    assert "`F-BROWSER-SESSION-DURABILITY`" in current
    assert "`F-SELLER-CENTRAL-ELIGIBILITY`" in current
    assert "Do not leak raw scope" not in current
    assert "Waiting proof" in current
    assert "F MOT retest" in current
    assert "focused tests" in current

    assert "## Luke-Blocked Decisions" in backlog
    assert "`B-B008-TOKEN-STATE-CONFLICT`" in backlog
    assert "`H-HISTORICAL-CARD`" in backlog
    assert "`O-USER-WORKING-READINESS`" in backlog
    assert "`SO21-INSTRUCTION-CLEANUP`" in backlog
    assert "`SO21-STORAGE-INDEX-OUT-SUBTREE`" in backlog
    assert "Do not duplicate this active packet" not in backlog

    assert result.active_count == 2
    assert result.blocked_count == 1
    assert result.parked_count == 1
    assert result.mot_candidate_count == 1


def test_write_current_work_markdown_writes_both_control_files(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    result = write_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert result.current_tickets_path == tmp_path / "sellerone_manager" / "CONTROL" / "CURRENT_TICKETS.md"
    assert result.backlog_path == tmp_path / "sellerone_manager" / "CONTROL" / "BACKLOG.md"
    assert result.current_tickets_path.exists()
    assert result.backlog_path.exists()


def test_current_work_md_cli_writes_files(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    exit_code = app_main(["--root", str(tmp_path), "--current-work-md", "--observed-utc", "2026-06-08T12:30:00Z"])

    assert exit_code == 0
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "CURRENT_TICKETS.md").exists()
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "BACKLOG.md").exists()


def test_control_backlog_drops_coding_plan_archive_after_archive_marker_exists(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,high\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("x" * 60000, encoding="utf-8")

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-CODING-PLAN-ARCHIVE`" not in result.backlog_markdown
    assert "`SO21-PROMPT-FOLDER-ARCHIVE`" in result.backlog_markdown


def test_control_backlog_drops_prompt_archive_after_prompt_marker_exists(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("x" * 15000, encoding="utf-8")

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-PROMPT-FOLDER-ARCHIVE`" not in result.backlog_markdown
    assert "`SO21-ROLE-FILE-TRIM`" in result.backlog_markdown


def test_control_backlog_drops_role_trim_after_role_marker_exists(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-ROLE-FILE-TRIM`" not in result.backlog_markdown
    assert "`SO21-SKILL-SPECS`" in result.backlog_markdown


def test_control_backlog_drops_storage_index_after_out_subtree_is_classified(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,out subtree classified\n",
        encoding="utf-8",
    )

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-STORAGE-INDEX-OUT-SUBTREE`" not in result.backlog_markdown
    assert "`SO21-CUSTODIAN-DRY-RUN-MANIFEST`" in result.backlog_markdown


def test_control_backlog_drops_dry_run_manifest_after_manifest_exists(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,out subtree classified\n",
        encoding="utf-8",
    )
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-CUSTODIAN-DRY-RUN-MANIFEST`" not in result.backlog_markdown
    assert "`SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW`" in result.backlog_markdown


def test_control_backlog_shows_windows_scheduler_pause_decision_after_review_finds_ready_task(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,out subtree classified\n",
        encoding="utf-8",
    )
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv").write_text(
        "source_type,item_id,luke_decision_required\nwindows_scheduler,AMZ Morning MOT Post A,yes\n",
        encoding="utf-8",
    )

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW`" not in result.backlog_markdown
    assert "`SO21-WINDOWS-SCHEDULER-PAUSE-DECISION`" in result.backlog_markdown


def test_control_backlog_shows_admin_pause_after_scheduler_pause_is_partial(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,out subtree classified\n",
        encoding="utf-8",
    )
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Ready,1\n",
        encoding="utf-8",
    )

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-WINDOWS-SCHEDULER-PAUSE-DECISION`" not in result.backlog_markdown
    assert "`SO21-WINDOWS-SCHEDULER-ADMIN-PAUSE`" in result.backlog_markdown


def test_control_backlog_shows_activation_decision_after_automation_rebuild_plan_exists(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,out subtree classified\n",
        encoding="utf-8",
    )
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Disabled,0\n",
        encoding="utf-8",
    )
    (control_dir / "AUTOMATION_REBUILD.md").write_text("# Automation Rebuild\n", encoding="utf-8")
    (control_dir / "AUTOMATION_REBUILD_PLAN.csv").write_text(
        "automation_ref,status\nSO21-REP-BRIEFING,candidate_create_paused\n",
        encoding="utf-8",
    )

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-AUTOMATION-REBUILD`" not in result.backlog_markdown
    assert "`SO21-AUTOMATION-ACTIVATION-DECISION`" in result.backlog_markdown


def test_current_work_backlog_adds_rep_briefing_first_run_proof_after_activation(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,out subtree classified\n",
        encoding="utf-8",
    )
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Disabled,0\n",
        encoding="utf-8",
    )
    (control_dir / "AUTOMATION_REBUILD.md").write_text("# Automation Rebuild\n", encoding="utf-8")
    (control_dir / "AUTOMATION_REBUILD_PLAN.csv").write_text(
        "automation_ref,status\nSO21-REP-BRIEFING,active_pilot\n",
        encoding="utf-8",
    )
    (control_dir / "AUTOMATION_ACTIVATION_DECISION.md").write_text("# Activation Decision\n", encoding="utf-8")
    (control_dir / "SO21_REP_BRIEFING_ACTIVATION.md").write_text("# Activation\n", encoding="utf-8")

    result = build_current_work_markdown(root=tmp_path, generated_utc="2026-06-08T12:30:00Z")

    assert "`SO21-AUTOMATION-ACTIVATION-DECISION`" not in result.backlog_markdown
    assert "`SO21-REP-BRIEFING-FIRST-RUN-PROOF`" in result.backlog_markdown
