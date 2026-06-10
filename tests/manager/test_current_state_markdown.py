from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main
from sellerone_manager.current_state_markdown import build_current_state_markdown, write_current_state_markdown
from sellerone_manager.schemas import APPROVED_TASK_PACKET_COLUMNS


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_fixture(root: Path, automation_root: Path) -> None:
    (root / "sellerone_manager" / "CONTROL").mkdir(parents=True, exist_ok=True)
    (root / "sellerone_manager" / "CONTROL" / "QUEUE_CONTRACT.md").write_text("# Queue\n", encoding="utf-8")
    (root / "sellerone_manager" / "CONTROL" / "ARCHITECTURE_DECISIONS.md").write_text(
        "\n".join(
            [
                "# ADR",
                "",
                "## ADR-0001 - SellerOne 2.1 Is Control Desk Stabilisation",
                "",
                "## ADR-0007 - Rep And Operations Are Separated",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "sellerone_manager" / "tasks" / "archive").mkdir(parents=True, exist_ok=True)
    mot_dir = root / "out" / "systems" / "M" / "mot"
    mot_dir.mkdir(parents=True, exist_ok=True)
    (mot_dir / "mot_latest.json").write_text(
        json.dumps(
            {
                "observed_utc": "2026-06-08T11:00:46Z",
                "status": "decision_needed",
                "fail_count": 2,
                "warn_count": 3,
                "decision_count": 1,
                "not_checked_count": 0,
                "rows": [
                    {
                        "flow": "F",
                        "check": "f_rescan_priority_proof",
                        "status": "fail",
                        "summary": "Needs protected decision before queue rows can move.",
                        "luke_action_required": "1",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        root / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {
                "task_id": "MOT_F_SCANNER_PROGRESS",
                "job_ref": "F-SCANNER-PROGRESS",
                "flow": "F",
                "status": "approved",
                "priority": "high",
                "title": "F MOT: f_live_owner_status needs repair",
                "luke_action_required": "0",
                "allowed_scope": "Do not leak this raw scope into CURRENT_STATE.md.",
            },
            {
                "task_id": "MOT_F_RESCAN_PRIORITY",
                "job_ref": "F-RESCAN-PRIORITY",
                "flow": "F",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "F MOT: f_rescan_priority_proof needs Luke decision",
                "luke_action_required": "1",
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
    (automation_root / "sellerone-quiet-daily-log").mkdir(parents=True, exist_ok=True)
    (automation_root / "sellerone-quiet-daily-log" / "automation.toml").write_text(
        'id = "sellerone-quiet-daily-log"\nname = "SellerOne Quiet Daily Log"\nstatus = "PAUSED"\n',
        encoding="utf-8",
    )


def test_build_current_state_markdown_summarises_evidence_without_raw_dump(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    markdown = result.markdown
    assert "## Current Phase" in markdown
    assert "## Queue Summary" in markdown
    assert "## Health Summary" in markdown
    assert "## Active Work" in markdown
    assert "## Blocked Work" in markdown
    assert "## Recommended Next Task" in markdown
    assert "F-SCANNER-PROGRESS" in markdown
    assert "F-RESCAN-PRIORITY" in markdown
    assert "Active automations: 0" in markdown
    assert "Architecture decisions recorded: 2" in markdown
    assert "1 decision" in markdown
    assert "Do not leak this raw scope" not in markdown
    assert result.recommended_next_task == "SO21-CUSTODIAN-POLICY"


def test_write_current_state_markdown_writes_control_file(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)

    result = write_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.path == tmp_path / "sellerone_manager" / "CONTROL" / "CURRENT_STATE.md"
    assert result.path.exists()
    assert "Generated UTC: 2026-06-08T12:00:00Z" in result.path.read_text(encoding="utf-8")


def test_current_state_md_cli_writes_file(tmp_path: Path, monkeypatch) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "automations").mkdir(exist_ok=True)

    exit_code = app_main(["--root", str(tmp_path), "--current-state-md", "--observed-utc", "2026-06-08T12:00:00Z"])

    assert exit_code == 0
    current_state = tmp_path / "sellerone_manager" / "CONTROL" / "CURRENT_STATE.md"
    assert current_state.exists()
    assert "Recommended Next Task" in current_state.read_text(encoding="utf-8")


def test_current_state_recommends_ai_usage_after_instruction_cleanup(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-AI-USAGE-REPORT"
    assert "AI usage report missing" in result.markdown


def test_current_state_recommends_automation_rebuild_after_ai_usage_exists(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("ticket,usage\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Dead Automation Review\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-AUTOMATION-REBUILD"
    assert "careful automation rebuild" in result.markdown


def test_current_state_recommends_coding_plan_archive_when_ai_usage_finds_legacy_plan(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("ticket,usage\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("x" * 60000, encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-CODING-PLAN-ARCHIVE"
    assert "oversized legacy coding plan" in result.markdown


def test_current_state_recommends_prompt_archive_after_coding_plan_is_archived(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text(
        "job_ref,risk_level\nPLANS,high\n",
        encoding="utf-8",
    )
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("x" * 60000, encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-PROMPT-FOLDER-ARCHIVE"
    assert "old plans and prompt folders" in result.markdown


def test_current_state_recommends_role_trim_after_prompt_folders_are_archived(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("x" * 15000, encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-ROLE-FILE-TRIM"
    assert "role detail files" in result.markdown


def test_current_state_recommends_skill_specs_after_role_files_are_trimmed(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-SKILL-SPECS"
    assert "skill/template specs" in result.markdown


def test_current_state_recommends_out_subtree_after_skill_specs_exist(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,needs out subtree index\n",
        encoding="utf-8",
    )

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-STORAGE-INDEX-OUT-SUBTREE"
    assert "subtree classification" in result.markdown


def test_current_state_recommends_dry_run_manifest_after_out_subtree_is_classified(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,out subtree classified\n",
        encoding="utf-8",
    )

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-CUSTODIAN-DRY-RUN-MANIFEST"
    assert "preview-only manifest" in result.markdown


def test_current_state_recommends_dead_automation_review_after_manifest_exists(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW"
    assert "dead automations and schedulers" in result.markdown


def test_current_state_recommends_windows_scheduler_pause_decision_after_review_finds_ready_task(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv").write_text(
        "source_type,item_id,luke_decision_required\nwindows_scheduler,AMZ Morning MOT Post A,yes\n",
        encoding="utf-8",
    )
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-WINDOWS-SCHEDULER-PAUSE-DECISION"
    assert "pause decision needed" in result.markdown


def test_current_state_recommends_admin_pause_after_scheduler_pause_is_partial(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Ready,1\n",
        encoding="utf-8",
    )
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-WINDOWS-SCHEDULER-ADMIN-PAUSE"
    assert "admin pause" in result.markdown.lower()


def test_current_state_recommends_activation_decision_after_automation_rebuild_plan_exists(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Disabled,0\n",
        encoding="utf-8",
    )
    (control_dir / "AUTOMATION_REBUILD.md").write_text("# Automation Rebuild\n", encoding="utf-8")
    (control_dir / "AUTOMATION_REBUILD_PLAN.csv").write_text("automation_ref,status\nSO21-REP-BRIEFING,candidate_create_paused\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-AUTOMATION-ACTIVATION-DECISION"
    assert "first pilot creation or activation decision" in result.markdown


def test_current_state_says_paused_rep_briefing_pilot_exists_when_proof_exists(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Disabled,0\n",
        encoding="utf-8",
    )
    (control_dir / "AUTOMATION_REBUILD.md").write_text("# Automation Rebuild\n", encoding="utf-8")
    (control_dir / "AUTOMATION_REBUILD_PLAN.csv").write_text("automation_ref,status\nSO21-REP-BRIEFING,created_paused\n", encoding="utf-8")
    (control_dir / "SO21_REP_BRIEFING_PILOT.md").write_text("# Pilot\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-AUTOMATION-ACTIVATION-DECISION"
    assert "paused Rep briefing pilot exists; activation decision is needed" in result.markdown


def test_current_state_accepts_approved_active_rep_briefing_pilot(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    rep_dir = automation_root / "so21-rep-briefing"
    rep_dir.mkdir(parents=True, exist_ok=True)
    (rep_dir / "automation.toml").write_text(
        'id = "so21-rep-briefing"\nname = "SO21-REP-BRIEFING"\nstatus = "ACTIVE"\n',
        encoding="utf-8",
    )
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "STORAGE_POLICY.md").write_text("# Storage\n", encoding="utf-8")
    (control_dir / "CURRENT_TICKETS.md").write_text("# Current Tickets\n", encoding="utf-8")
    (control_dir / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
    (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").write_text("# Instruction Cleanup\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Archived Coding Plan\n", encoding="utf-8")
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Folder Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Disabled,0\n",
        encoding="utf-8",
    )
    (control_dir / "AUTOMATION_REBUILD.md").write_text("# Automation Rebuild\n", encoding="utf-8")
    (control_dir / "AUTOMATION_REBUILD_PLAN.csv").write_text("automation_ref,status\nSO21-REP-BRIEFING,active_pilot\n", encoding="utf-8")
    (control_dir / "AUTOMATION_ACTIVATION_DECISION.md").write_text("# Activation Decision\n", encoding="utf-8")
    (control_dir / "SO21_REP_BRIEFING_PILOT.md").write_text("# Pilot\n", encoding="utf-8")
    (control_dir / "SO21_REP_BRIEFING_ACTIVATION.md").write_text("# Activation\n", encoding="utf-8")
    (control_dir / "AI_USAGE.csv").write_text("job_ref,risk_level\nPLANS,low\n", encoding="utf-8")

    result = build_current_state_markdown(
        root=tmp_path,
        generated_utc="2026-06-08T12:00:00Z",
        automation_root=automation_root,
    )

    assert result.recommended_next_task == "SO21-REP-BRIEFING-FIRST-RUN-PROOF"
    assert "There is 1 approved active pilot automation." in result.markdown
    assert "Unapproved active automations: 0" in result.markdown
    assert "SO21-REP-BRIEFING-FIRST-RUN-PROOF" in result.markdown
