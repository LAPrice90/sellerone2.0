from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.hometime_mode import (
    preflight_hometime,
    pulse_hometime,
    start_hometime,
    status_hometime,
    write_hometime_outputs,
)


APPROVED_COLUMNS = [
    "observed_utc",
    "created_utc",
    "updated_utc",
    "task_id",
    "job_ref",
    "source_type",
    "source_id",
    "source_path",
    "flow",
    "task_type",
    "authority",
    "status",
    "priority",
    "title",
    "allowed_scope",
    "forbidden_actions",
    "proof_required",
    "retest_command",
    "rollback_path",
    "stop_condition",
    "luke_action_required",
    "packet_path",
    "notes",
]


def _write_policy(root: Path) -> None:
    path = root / "config" / "manager" / "hometime_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "policy_id": "test_hometime",
                "status": "active",
                "mode": "hometime",
                "pulse_minutes": 30,
                "finish_rule": "jobs_settled",
                "autonomy_level": "maximum_safe",
                "notification_email": "laprice90@gmail.com",
                "duplicate_email_cooldown_minutes": 240,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_approved_packets(root: Path, rows: list[dict[str, str]]) -> None:
    path = root / "out" / "systems" / "M" / "approved_task_packets.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=APPROVED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in APPROVED_COLUMNS})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_hometime_selects_safe_evening_jobs(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_approved_packets(
        tmp_path,
        [
            {
                "observed_utc": "2026-06-05T18:00:00Z",
                "task_id": "MGR_B_FALLBACK_COST_PROOF_RECONCILIATION_V1",
                "job_ref": "B-FALLBACK-PROOF-RECONCILE",
                "flow": "B",
                "status": "approved",
                "priority": "high",
                "title": "B fallback cost proof reconciliation",
                "proof_required": "Run read-only B proof reconciliation and B MOT.",
                "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
                "luke_action_required": "0",
            }
        ],
    )

    result = start_hometime(root=tmp_path, observed_utc="2026-06-05T18:00:00Z")

    assert result.overall_status == "running"
    assert result.selected_job_count == 1
    assert result.safe_job_count == 1
    assert result.jobs[0].hometime_status == "queued"
    assert result.jobs[0].safe_to_continue is True
    assert "hometime_latest.md" in result.output_paths["latest_md"]


def test_hometime_preflight_lists_known_permissions_without_email(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_approved_packets(
        tmp_path,
        [
            {
                "observed_utc": "2026-06-05T18:00:00Z",
                "task_id": "MGR_B_FALLBACK_TOKEN_DATA_CORRECTION_DECISION_V1",
                "job_ref": "B-FALLBACK-DATA-CORRECTION",
                "flow": "B",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "B fallback token data correction decision",
                "proof_required": "Luke must approve any local token data correction.",
                "luke_action_required": "1",
            }
        ],
    )

    result = preflight_hometime(root=tmp_path, observed_utc="2026-06-05T17:00:00Z")

    assert result.overall_status == "settled"
    assert result.blocked_job_count == 1
    assert result.preflight_permission_count == 1
    assert result.email_required_count == 0
    assert result.notifications[0].email_to == "laprice90@gmail.com"
    assert result.notifications[0].email_status == "preflight_permission_required"


def test_hometime_suppresses_duplicate_blocker_email(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    row = {
        "observed_utc": "2026-06-05T18:00:00Z",
        "task_id": "MGR_B_FALLBACK_TOKEN_DATA_CORRECTION_DECISION_V1",
        "job_ref": "B-FALLBACK-DATA-CORRECTION",
        "flow": "B",
        "status": "blocked_needs_luke",
        "priority": "high",
        "title": "B fallback token data correction decision",
        "proof_required": "Luke must approve any local token data correction.",
        "luke_action_required": "1",
    }
    _write_approved_packets(tmp_path, [row])

    first = start_hometime(root=tmp_path, observed_utc="2026-06-05T18:00:00Z")
    second = pulse_hometime(root=tmp_path, observed_utc="2026-06-05T18:30:00Z")
    third = pulse_hometime(root=tmp_path, observed_utc="2026-06-05T19:00:00Z")

    assert first.preflight_permission_count == 1
    assert first.email_required_count == 0
    assert second.email_required_count == 0
    assert second.email_suppressed_count == 1
    assert second.notifications[0].email_status == "suppressed_duplicate"
    assert third.email_required_count == 0
    assert third.email_suppressed_count == 1


def test_hometime_pulse_emails_only_new_surprise_blocker(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_approved_packets(tmp_path, [])
    start = start_hometime(root=tmp_path, observed_utc="2026-06-05T18:00:00Z")
    assert start.email_required_count == 0

    _write_approved_packets(
        tmp_path,
        [
            {
                "observed_utc": "2026-06-05T18:30:00Z",
                "task_id": "MGR_F_SURPRISE_LOGIN_DECISION_V1",
                "job_ref": "F-SURPRISE-LOGIN",
                "flow": "F",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "F surprise login decision",
                "proof_required": "Luke must log in through the script-owned browser.",
                "luke_action_required": "1",
            }
        ],
    )

    pulse = pulse_hometime(root=tmp_path, observed_utc="2026-06-05T18:30:00Z")

    assert pulse.preflight_permission_count == 0
    assert pulse.email_required_count == 1
    assert pulse.notifications[0].job_ref == "F-SURPRISE-LOGIN"
    assert pulse.notifications[0].email_status == "pending_codex_email"


def test_hometime_writes_manager_visibility_files(tmp_path: Path) -> None:
    _write_policy(tmp_path)
    _write_approved_packets(
        tmp_path,
        [
            {
                "task_id": "MGR_O_TOKEN_COST_TRUST_GATE_V1",
                "job_ref": "O-TOKEN-COST-TRUST-GATE",
                "flow": "O",
                "status": "fixed_needs_retest",
                "priority": "high",
                "title": "O token cost trust gate",
                "proof_required": "Retest O MOT and confirm bad B token evidence is not trusted.",
                "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow O",
                "luke_action_required": "0",
            }
        ],
    )

    result = status_hometime(root=tmp_path, observed_utc="2026-06-05T19:00:00Z")
    paths = {name: Path(path) for name, path in result.output_paths.items()}

    assert paths["latest_json"].exists()
    assert paths["latest_md"].exists()
    assert paths["jobs_csv"].exists()
    rows = _read_csv(paths["jobs_csv"])
    assert rows[0]["job_ref"] == "O-TOKEN-COST-TRUST-GATE"
    assert rows[0]["hometime_status"] == "waiting_proof"
