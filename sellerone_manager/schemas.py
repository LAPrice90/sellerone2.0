from __future__ import annotations

from collections import Counter
from typing import Any


RESULT_STATUSES = {
    "ok",
    "warn",
    "fail",
    "needs_user",
    "blocked",
    "stale_evidence",
    "not_checked",
}

CODEX_REPAIR_TASK_STATUSES = {
    "queued",
    "in_progress",
    "blocked_needs_user_decision",
    "cleared_pending_review",
    "completed",
    "reopened",
}

REQUIRED_MANIFEST_FIELDS = [
    "id",
    "display_name",
    "flow",
    "owner_entrypoint",
    "worker_entrypoint",
    "health_sources",
    "status_sources",
    "outputs",
    "freshness_rules",
    "needs_user_signals",
    "safe_actions",
    "forbidden_actions",
]

SNAPSHOT_COLUMNS = [
    "observed_utc",
    "flow",
    "module_id",
    "status",
    "queue_supplier_id",
    "queue_supplier_name",
    "queue_state",
    "queue_position",
    "queue_web_unprocessed",
    "live_state",
    "live_last_action",
    "live_last_action_status",
    "live_pending_rows",
    "live_active_supplier_id",
    "active_blocker_code",
    "active_blocker_summary",
    "needs_user",
    "user_action",
    "safe_to_do_nothing",
    "stale_evidence",
    "evidence_paths",
    "notes",
]

HEALTH_COLUMNS = [
    "check",
    "status",
    "value",
    "notes",
    "observed_utc",
    "source_path",
]

INCIDENT_COLUMNS = [
    "observed_utc",
    "flow",
    "severity",
    "incident_code",
    "summary",
    "needs_user",
    "root_artifact",
    "remediation_hint",
]

CODEX_REPAIR_QUEUE_COLUMNS = [
    "observed_utc",
    "created_utc",
    "updated_utc",
    "last_seen_utc",
    "seen_count",
    "flow",
    "task_id",
    "owner",
    "priority",
    "status",
    "source_incident_code",
    "task_summary",
    "root_artifact",
    "allowed_scope",
    "forbidden_actions",
    "proof_required",
]

CODEX_REPAIR_EVENT_COLUMNS = [
    "event_utc",
    "task_id",
    "event_type",
    "old_status",
    "new_status",
    "actor",
    "note",
    "source",
]

SELF_ORGANISATION_COLUMNS = [
    "observed_utc",
    "script_path",
    "flow_group",
    "inferred_role",
    "status",
    "notes",
]

F_SCRIPT_REGISTRATION_COLUMNS = [
    "observed_utc",
    "script_path",
    "discovery_sources",
    "classification",
    "classification_reason",
    "is_exempt",
    "needs_codex_review",
    "blocks_f_operation",
    "owner",
    "purpose",
    "entrypoint",
    "health_source",
    "expected_outputs",
    "runbook_notes_link",
    "safe_actions_declared",
    "forbidden_actions_declared",
    "missing_fields",
    "manager_module_id",
    "notes",
]

F_MANIFEST_PRIORITY_COLUMNS = [
    "observed_utc",
    "rank",
    "script_path",
    "classification",
    "priority_score",
    "priority_band",
    "recommended_action",
    "safe_to_manifest_without_worker_changes",
    "reason_codes",
    "reason_summary",
    "referenced_by_manifest",
    "referenced_by_status_or_runtime",
    "live_entrypoint",
    "writes_live_outputs",
    "queue_ownership",
    "storage_drift_or_preflight",
    "supplier_status_dashboard",
    "recently_modified",
    "mtime_utc",
    "defer_reason",
]

FLOW_MAINTENANCE_COLUMNS = [
    "observed_utc",
    "flow",
    "flow_name",
    "rollout_rank",
    "status",
    "classification",
    "needs_luke_decision",
    "luke_decision",
    "codex_task_available",
    "codex_task_title",
    "active_fail_count",
    "active_warn_count",
    "stale_evidence_count",
    "not_verified_count",
    "covered_expectations",
    "total_expectations",
    "first_blocker_code",
    "first_blocker_summary",
    "proof_rule",
    "evidence_paths",
    "notes",
]

EXPECTATION_RECONCILIATION_COLUMNS = [
    "observed_utc",
    "flow",
    "feature",
    "expected_status",
    "manager_status",
    "evidence_status",
    "evidence_checks",
    "notes",
    "source_path",
]

MANAGER_TASK_CANDIDATE_COLUMNS = [
    "observed_utc",
    "flow",
    "task_id",
    "job_ref",
    "task_type",
    "priority",
    "status",
    "title",
    "root_artifact",
    "allowed_scope",
    "forbidden_actions",
    "proof_required",
    "stop_condition",
    "needs_luke_decision",
    "notes",
]

HOURLY_MOT_COLUMNS = [
    "observed_utc",
    "flow",
    "check",
    "producer",
    "expected_output",
    "status",
    "severity",
    "value",
    "actual_proof",
    "age_hours",
    "row_count",
    "source_path",
    "summary",
    "root_cause_guess",
    "manager_action",
    "luke_action_required",
    "retest_command",
    "safe_repair_boundary",
    "changed_since_previous",
    "previous_status",
]

MOT_WORKLIST_COLUMNS = [
    "observed_utc",
    "created_utc",
    "updated_utc",
    "last_seen_utc",
    "seen_count",
    "work_item_id",
    "job_ref",
    "flow",
    "check",
    "producer",
    "title",
    "status",
    "priority",
    "source_path",
    "root_cause_guess",
    "manager_action",
    "allowed_scope",
    "forbidden_actions",
    "proof_required",
    "retest_command",
    "safe_repair_boundary",
    "luke_action_required",
    "notes",
]

MOT_RETEST_QUEUE_COLUMNS = [
    "observed_utc",
    "work_item_id",
    "flow",
    "check",
    "status",
    "retest_command",
    "expected_result",
    "source_path",
    "notes",
]

APPROVED_TASK_PACKET_COLUMNS = [
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


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            errors.append(f"missing_field:{field}")

    if errors:
        return errors

    for field in ["id", "display_name", "flow", "owner_entrypoint", "worker_entrypoint"]:
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"invalid_text_field:{field}")

    for field in [
        "health_sources",
        "status_sources",
        "outputs",
        "freshness_rules",
        "needs_user_signals",
        "safe_actions",
        "forbidden_actions",
    ]:
        if not isinstance(manifest.get(field), list):
            errors.append(f"invalid_list_field:{field}")

    for source_group in ["health_sources", "status_sources", "outputs"]:
        for index, source in enumerate(manifest.get(source_group, [])):
            if not isinstance(source, dict):
                errors.append(f"invalid_source:{source_group}[{index}]")
                continue
            if not source.get("name"):
                errors.append(f"missing_source_name:{source_group}[{index}]")
            if not source.get("path"):
                errors.append(f"missing_source_path:{source_group}[{index}]")

    return errors


def duplicate_headers(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        return []
    counts = Counter(fieldnames)
    return sorted(name for name, count in counts.items() if count > 1)


def blank_row(columns: list[str]) -> dict[str, str]:
    return {column: "" for column in columns}
