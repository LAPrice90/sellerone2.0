from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.ai_usage_report import build_ai_usage_report, write_ai_usage_report
from sellerone_manager.app import main as app_main
from sellerone_manager.schemas import APPROVED_TASK_PACKET_COLUMNS


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_fixture(root: Path, automation_root: Path) -> None:
    control_dir = root / "sellerone_manager" / "CONTROL"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "BACKLOG.md").write_text(
        "\n".join(
            [
                "# Backlog",
                "",
                "| Job | Status | Why |",
                "|---|---|---|",
                "| `SO21-AI-USAGE-REPORT` | planned | usage |",
                "| `SO21-CODING-PLAN-ARCHIVE` | planned | archive |",
            ]
        ),
        encoding="utf-8",
    )
    (root / "sellerone_manager" / "CODING_PLAN.md").write_text("x" * 60000, encoding="utf-8")
    (root / "sellerone_manager" / "MANAGER_CHAT.md").write_text("x" * 15000, encoding="utf-8")
    (root / "plans" / "active" / "old_plan.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "plans" / "active" / "old_plan.md").write_text("x" * 100, encoding="utf-8")
    _write_csv(
        root / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {
                "task_id": "MOT_F_LOGIN",
                "job_ref": "F-BROWSER-SESSION-DURABILITY",
                "flow": "F",
                "status": "fixed_needs_retest",
                "priority": "high",
                "title": "F Login Session Durability",
                "luke_action_required": "0",
            },
            {
                "task_id": "MOT_B_ACTIVE",
                "job_ref": "B-ACTIVE-FAIL-GROUP",
                "flow": "B",
                "status": "approved",
                "priority": "high",
                "title": "Repair B active FAIL group",
                "luke_action_required": "0",
            },
            {
                "task_id": "MOT_B_DECISION",
                "job_ref": "B-B008-TOKEN-STATE-CONFLICT",
                "flow": "B",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "B token decision",
                "luke_action_required": "1",
            },
        ],
    )
    mot_dir = root / "out" / "systems" / "M" / "mot"
    mot_dir.mkdir(parents=True, exist_ok=True)
    (mot_dir / "mot_latest.json").write_text(
        json.dumps(
            {
                "status": "decision_needed",
                "fail_count": 8,
                "warn_count": 20,
                "decision_count": 1,
                "not_checked_count": 6,
            }
        ),
        encoding="utf-8",
    )
    (automation_root / "quiet").mkdir(parents=True, exist_ok=True)
    (automation_root / "quiet" / "automation.toml").write_text(
        'id = "quiet"\nname = "Quiet"\nstatus = "PAUSED"\n',
        encoding="utf-8",
    )


def test_ai_usage_report_builds_pressure_rows_without_claiming_cost(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)
    rows_by_job = {row["job_ref"]: row for row in result.rows}

    assert rows_by_job["AI-USAGE-RAW-COST-DATA"]["actual_cost_available"] == "no"
    assert rows_by_job["MOT-PRESSURE"]["risk_level"] == "high"
    assert rows_by_job["CODING-PLAN"]["risk_level"] == "high"
    assert rows_by_job["CODEX-AUTOMATIONS"]["risk_level"] == "low"
    assert rows_by_job["F-BROWSER-SESSION-DURABILITY"]["usage_signal"] == "retest_or_monitoring_loop"
    assert result.actual_cost_available is False
    assert result.recommended_next_task == "SO21-CODING-PLAN-ARCHIVE"
    assert "Stock-token and token-ledger business data is deliberately excluded" in result.markdown


def test_write_ai_usage_report_writes_csv_and_markdown(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)

    result = write_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.csv_path.exists()
    assert result.markdown_path.exists()
    csv_text = result.csv_path.read_text(encoding="utf-8")
    assert "AI-USAGE-RAW-COST-DATA" in csv_text
    assert "SO21-AI-USAGE-REPORT" in result.markdown_path.read_text(encoding="utf-8")


def test_ai_usage_report_cli_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))

    exit_code = app_main(["--root", str(tmp_path), "--ai-usage-report", "--observed-utc", "2026-06-08T13:00:00Z"])

    assert exit_code == 0
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "AI_USAGE.csv").exists()
    assert (tmp_path / "sellerone_manager" / "CONTROL" / "AI_USAGE.md").exists()


def test_ai_usage_report_treats_archived_prompt_folders_as_low_pressure(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)
    rows_by_job = {row["job_ref"]: row for row in result.rows}

    assert rows_by_job["PLANS"]["risk_level"] == "low"
    assert rows_by_job["PLANS"]["status"] == "template_or_history"
    assert rows_by_job["PLANS"]["usage_signal"] == "archived_prompt_or_plan_folder"
    assert result.recommended_next_task == "SO21-ROLE-FILE-TRIM"


def test_ai_usage_report_recommends_skill_specs_after_role_files_trimmed(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md").write_text("# Progress pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.recommended_next_task == "SO21-SKILL-SPECS"


def test_ai_usage_report_recommends_out_subtree_after_skill_specs_exist(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,needs out subtree index\n",
        encoding="utf-8",
    )
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md").write_text("# Progress pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.recommended_next_task == "SO21-STORAGE-INDEX-OUT-SUBTREE"


def test_ai_usage_report_recommends_manifest_after_out_subtree_classified(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "STORAGE_INDEX.csv").write_text(
        "path,proof_or_blocker\nout,out subtree classified\n",
        encoding="utf-8",
    )
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md").write_text("# Progress pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.recommended_next_task == "SO21-CUSTODIAN-DRY-RUN-MANIFEST"


def test_ai_usage_report_recommends_dead_automation_review_after_manifest_exists(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md").write_text("# Progress pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.recommended_next_task == "SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW"


def test_ai_usage_report_recommends_windows_scheduler_pause_decision_after_review_finds_ready_task(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv").write_text(
        "source_type,item_id,luke_decision_required\nwindows_scheduler,AMZ Morning MOT Post A,yes\n",
        encoding="utf-8",
    )
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md").write_text("# Progress pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.recommended_next_task == "SO21-WINDOWS-SCHEDULER-PAUSE-DECISION"


def test_ai_usage_report_recommends_admin_pause_after_scheduler_pause_is_partial(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
    (control_dir / "ROLE_FILE_TRIM.md").write_text("# Role File Trim\n", encoding="utf-8")
    (control_dir / "SKILL_SPECS.md").write_text("# Skill Specs\n", encoding="utf-8")
    (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").write_text("# Manifest\n", encoding="utf-8")
    (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").write_text("# Review\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").write_text("# Decision\n", encoding="utf-8")
    (control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv").write_text(
        "task_name,after_state,exit_code\nAMZ H Cycle,Ready,1\n",
        encoding="utf-8",
    )
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md").write_text("# Progress pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.recommended_next_task == "SO21-WINDOWS-SCHEDULER-ADMIN-PAUSE"


def test_ai_usage_report_recommends_activation_decision_after_automation_rebuild_plan_exists(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
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
    (control_dir / "AUTOMATION_REBUILD_PLAN.csv").write_text(
        "automation_ref,status\nSO21-REP-BRIEFING,candidate_create_paused\n",
        encoding="utf-8",
    )
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md").write_text("# Progress pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.recommended_next_task == "SO21-AUTOMATION-ACTIVATION-DECISION"


def test_ai_usage_report_recommends_rep_briefing_first_run_proof_after_activation(tmp_path: Path) -> None:
    automation_root = tmp_path / "automations"
    _write_fixture(tmp_path, automation_root)
    control_dir = tmp_path / "sellerone_manager" / "CONTROL"
    (control_dir / "PROMPT_FOLDER_ARCHIVE.md").write_text("# Prompt Archive\n", encoding="utf-8")
    (control_dir / "CODING_PLAN_ARCHIVE.md").write_text("# Coding Plan Archive\n", encoding="utf-8")
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
    (control_dir / "AUTOMATION_REBUILD_PLAN.csv").write_text(
        "automation_ref,status\nSO21-REP-BRIEFING,active_pilot\n",
        encoding="utf-8",
    )
    (control_dir / "AUTOMATION_ACTIVATION_DECISION.md").write_text("# Activation Decision\n", encoding="utf-8")
    (control_dir / "SO21_REP_BRIEFING_ACTIVATION.md").write_text("# Activation\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "CODING_PLAN.md").write_text("# Live pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_CHAT.md").write_text("# Manager pointer\n", encoding="utf-8")
    (tmp_path / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md").write_text("# Progress pointer\n", encoding="utf-8")

    result = build_ai_usage_report(root=tmp_path, observed_utc="2026-06-08T13:00:00Z", automation_root=automation_root)

    assert result.recommended_next_task == "SO21-REP-BRIEFING-FIRST-RUN-PROOF"
