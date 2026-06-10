from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main
from sellerone_manager.app import run_manager
from sellerone_manager.f_price_list_snapshot import build_f_price_list_snapshot, merge_codex_repair_queue, output_headers_are_clean
from sellerone_manager.schemas import (
    CODEX_REPAIR_EVENT_COLUMNS,
    CODEX_REPAIR_QUEUE_COLUMNS,
    HEALTH_COLUMNS,
    INCIDENT_COLUMNS,
    SELF_ORGANISATION_COLUMNS,
    SNAPSHOT_COLUMNS,
    validate_manifest,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_manifest(root: Path, overrides: dict | None = None) -> dict:
    manifest = {
        "id": "F_price_list_manager",
        "display_name": "F Price List Manager",
        "flow": "F",
        "owner_entrypoint": "scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py",
        "worker_entrypoint": "scripts/flows/F/F061_run_legacy_first_checks_local.py",
        "health_sources": [
            {
                "name": "runtime_owner_contract",
                "path": "config/runtime_owner_contract.json",
                "required": True,
                "max_age_minutes": 100000,
            },
            {
                "name": "script_inventory",
                "path": "project_control/SCRIPT_INVENTORY.csv",
                "required": False,
                "max_age_minutes": 100000,
            },
        ],
        "status_sources": [
            {
                "name": "live_cycle_status",
                "path": "out/systems/F/price_list_manager/live/live_cycle_status.csv",
                "required": True,
                "max_age_minutes": 180,
            },
            {
                "name": "storage_drift_report",
                "path": "out/systems/F/price_list_manager/live/storage_drift_report.csv",
                "required": False,
                "max_age_minutes": 1440,
            },
            {
                "name": "status_dashboard",
                "path": "out/systems/F/price_list_manager/test_mode/status_dashboard.csv",
                "required": True,
                "max_age_minutes": 10080,
            },
        ],
        "outputs": [
            {
                "name": "active_run",
                "path": "out/systems/F/inbox/supplier_price_list_active_run.csv",
                "required": False,
                "max_age_minutes": 1440,
            }
        ],
        "freshness_rules": ["live_cycle_status_warn_after_180_minutes"],
        "needs_user_signals": ["manual_file_needed"],
        "safe_actions": ["read_status", "write_manager_report"],
        "forbidden_actions": ["run_worker", "edit_f061_live_queue"],
    }
    if overrides:
        manifest.update(overrides)
    path = root / "config" / "manager" / "modules" / "F_price_list_manager.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _write_minimum_context(root: Path) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "runtime_owner_contract.json").write_text(
        json.dumps({"flows": {"F_price_list_manager": {"runtime_owner": "FPM130"}}}) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        root / "project_control" / "SCRIPT_INVENTORY.csv",
        ["path", "extension", "top_area", "flow_group", "inferred_role", "has_python_main_guard", "mtime_utc", "size_bytes"],
        [
            {
                "path": "scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py",
                "extension": ".py",
                "top_area": "scripts",
                "flow_group": "F",
                "inferred_role": "flow_script",
            },
            {
                "path": "scripts/flows/F/F061_run_legacy_first_checks_local.py",
                "extension": ".py",
                "top_area": "scripts",
                "flow_group": "F",
                "inferred_role": "flow_script",
            },
            {
                "path": "scripts/flows/F/F099_run_new_worker.py",
                "extension": ".py",
                "top_area": "scripts",
                "flow_group": "F",
                "inferred_role": "flow_script",
            },
        ],
    )
    _write_csv(
        root / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "status_dashboard.csv",
        [
            "queue_position",
            "supplier_id",
            "supplier_name",
            "source_method",
            "source_location",
            "file_state",
            "queue_state",
            "operator_action",
            "control_state",
            "price_list_date",
            "bot_status",
            "web_unprocessed",
            "web_pass",
            "web_fail",
            "web_rescan",
            "second_unprocessed",
            "second_pass",
            "second_fail",
        ],
        [
            {
                "queue_position": "1",
                "supplier_id": "clf",
                "supplier_name": "CLF",
                "file_state": "Ready",
                "queue_state": "Recommended",
                "operator_action": "Recommended next scan",
                "control_state": "Prioritised #1",
                "bot_status": "Next Scan",
                "web_unprocessed": "16246",
            }
        ],
    )


def _write_live_status(root: Path, state: str, last_action: str, notes: str = "") -> None:
    _write_csv(
        root / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_status.csv",
        [
            "observed_utc",
            "run_id",
            "owner_pid",
            "state",
            "active_supplier_id",
            "active_f061_run_id",
            "pending_rows",
            "last_action",
            "last_action_status",
            "chunk_rows",
            "drain_ready",
            "notes",
        ],
        [
            {
                "observed_utc": "2026-05-26T10:42:45Z",
                "run_id": "fpm_live_test",
                "owner_pid": "123",
                "state": state,
                "pending_rows": "0",
                "last_action": last_action,
                "last_action_status": "blocked" if "blocked" in state else "ok",
                "notes": notes,
            }
        ],
    )


def _write_storage_drift_report(root: Path, rows: list[dict[str, str]]) -> None:
    _write_csv(
        root / "out" / "systems" / "F" / "price_list_manager" / "live" / "storage_drift_report.csv",
        [
            "observed_utc",
            "contract_name",
            "csv_path",
            "sql_table",
            "csv_exists",
            "sql_exists_before",
            "csv_rows",
            "sql_rows_before",
            "row_delta_before",
            "csv_freshness_utc",
            "sql_freshness_utc_before",
            "csv_newer_flag",
            "status_before",
            "safe_to_apply",
            "action",
            "sql_exists_after",
            "sql_rows_after",
            "row_delta_after",
            "sql_freshness_utc_after",
            "status_after",
            "backup_dir",
            "notes",
        ],
        rows,
    )


def test_manifest_validation_reports_missing_required_fields() -> None:
    errors = validate_manifest({"id": "F_price_list_manager"})

    assert "missing_field:display_name" in errors
    assert "missing_field:forbidden_actions" in errors


def test_clf_recommended_storage_drift_is_classified_as_blocker(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)
    _write_live_status(
        tmp_path,
        "blocked_storage_drift",
        "storage_drift_preflight",
        "storage_drift_status=blocked_storage_drift;blocked_rows=1",
    )

    result = build_f_price_list_snapshot(
        root=tmp_path,
        observed_utc="2026-05-26T11:00:00Z",
    )

    snapshot = result["snapshot_rows"][0]
    assert snapshot["status"] == "blocked"
    assert snapshot["queue_supplier_id"] == "clf"
    assert snapshot["active_blocker_code"] == "storage_drift_preflight"
    assert "storage drift" in snapshot["active_blocker_summary"].lower()
    assert snapshot["needs_user"] == "0"
    assert result["incident_rows"][0]["incident_code"] == "storage_drift_preflight"


def test_source_shape_guard_live_state_is_classified_as_blocker(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)
    _write_live_status(
        tmp_path,
        "blocked_source_shape_guard",
        "source_shape_guard",
        "source_shape_guard:unit_cost_not_positive_numeric|count=1|sample_supplier_sku=GCT019",
    )

    result = build_f_price_list_snapshot(
        root=tmp_path,
        observed_utc="2026-05-26T11:00:00Z",
    )

    snapshot = result["snapshot_rows"][0]
    assert snapshot["status"] == "needs_user"
    assert snapshot["active_blocker_code"] == "blocked_source_shape_guard"
    assert "unit_cost_not_positive_numeric" in snapshot["active_blocker_summary"]
    assert snapshot["needs_user"] == "1"
    assert result["incident_rows"][0]["incident_code"] == "blocked_source_shape_guard"
    assert result["incident_rows"][0]["needs_user"] == "1"


def test_clear_storage_drift_report_downgrades_old_live_block_to_stale_evidence(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)
    _write_live_status(
        tmp_path,
        "blocked_storage_drift",
        "storage_drift_preflight",
        "storage_drift_status=blocked_storage_drift;blocked_rows=1",
    )
    _write_storage_drift_report(
        tmp_path,
        [
            {
                "observed_utc": "2026-05-26T11:10:00Z",
                "contract_name": "feeder_legacy_chart_daily_raw_live",
                "csv_exists": "1",
                "sql_exists_before": "1",
                "csv_rows": "3",
                "sql_rows_before": "3",
                "row_delta_before": "0",
                "status_before": "ok",
                "safe_to_apply": "0",
                "action": "none",
                "sql_rows_after": "3",
                "row_delta_after": "0",
                "status_after": "ok",
                "notes": "sql_aligned_or_newer",
            }
        ],
    )

    result = build_f_price_list_snapshot(
        root=tmp_path,
        observed_utc="2026-05-26T11:20:00Z",
    )

    snapshot = result["snapshot_rows"][0]
    assert snapshot["status"] == "stale_evidence"
    assert snapshot["active_blocker_code"] == "live_owner_status_stale_after_storage_repair"
    assert snapshot["needs_user"] == "0"
    assert result["incident_rows"] == []
    assert result["codex_repair_queue_rows"] == []

    summary = run_manager(
        root=tmp_path,
        flow="F_price_list_manager",
        read_only=True,
        write_report_flag=True,
        observed_utc="2026-05-26T11:20:00Z",
    )
    report_text = Path(summary["outputs"]["report"]).read_text(encoding="utf-8")
    assert "storage drift repair evidence is now clear" in report_text
    assert "No active Codex repair task" in report_text
    assert "Classify the live owner state" not in report_text


def test_missing_required_artifact_sets_fail_without_worker_action(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)

    result = build_f_price_list_snapshot(
        root=tmp_path,
        observed_utc="2026-05-26T11:00:00Z",
    )

    snapshot = result["snapshot_rows"][0]
    assert snapshot["status"] == "fail"
    assert snapshot["active_blocker_code"] == "missing_live_status"
    assert any(row["check"] == "source_exists:live_cycle_status" and row["status"] == "fail" for row in result["health_rows"])


def test_stale_artifact_is_warned_but_storage_drift_remains_root_blocker(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)
    _write_live_status(
        tmp_path,
        "blocked_storage_drift",
        "storage_drift_preflight",
        "storage_drift_status=blocked_storage_drift",
    )
    old_time = 1_700_000_000
    os.utime(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "status_dashboard.csv",
        (old_time, old_time),
    )

    result = build_f_price_list_snapshot(
        root=tmp_path,
        observed_utc="2026-05-26T11:00:00Z",
    )

    snapshot = result["snapshot_rows"][0]
    assert snapshot["status"] == "blocked"
    assert snapshot["stale_evidence"] == "1"
    assert any(row["check"] == "source_freshness:status_dashboard" and row["status"] == "warn" for row in result["health_rows"])


def test_run_manager_writes_outputs_with_clean_headers(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)
    _write_live_status(
        tmp_path,
        "blocked_storage_drift",
        "storage_drift_preflight",
        "storage_drift_status=blocked_storage_drift",
    )

    summary = run_manager(
        root=tmp_path,
        flow="F_price_list_manager",
        read_only=True,
        write_report_flag=True,
        observed_utc="2026-05-26T11:00:00Z",
    )

    assert summary["manager_execution_errors"] == 0
    assert summary["status"] == "blocked"
    outputs = {name: Path(path) for name, path in summary["outputs"].items()}
    assert outputs["snapshot_csv"].exists()
    assert outputs["health_csv"].exists()
    assert outputs["incidents_csv"].exists()
    assert outputs["codex_repair_queue_csv"].exists()
    assert outputs["codex_repair_events_csv"].exists()
    assert outputs["self_organisation_csv"].exists()
    assert outputs["report"].exists()
    assert output_headers_are_clean(
        [
            outputs["snapshot_csv"],
            outputs["health_csv"],
            outputs["incidents_csv"],
            outputs["codex_repair_queue_csv"],
            outputs["codex_repair_events_csv"],
            outputs["self_organisation_csv"],
        ]
    ) == []

    with outputs["snapshot_csv"].open("r", newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle).fieldnames or []) == SNAPSHOT_COLUMNS
    with outputs["health_csv"].open("r", newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle).fieldnames or []) == HEALTH_COLUMNS
    with outputs["incidents_csv"].open("r", newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle).fieldnames or []) == INCIDENT_COLUMNS
    with outputs["codex_repair_queue_csv"].open("r", newline="", encoding="utf-8") as handle:
        repair_reader = csv.DictReader(handle)
        assert list(repair_reader.fieldnames or []) == CODEX_REPAIR_QUEUE_COLUMNS
        repair_rows = list(repair_reader)
    assert repair_rows[0]["owner"] == "Codex"
    assert repair_rows[0]["source_incident_code"] == "storage_drift_preflight"
    assert repair_rows[0]["task_id"].startswith("F_storage_drift_preflight_")
    assert "20260526T" not in repair_rows[0]["task_id"]
    assert repair_rows[0]["created_utc"] == "2026-05-26T11:00:00Z"
    assert repair_rows[0]["last_seen_utc"] == "2026-05-26T11:00:00Z"
    assert repair_rows[0]["seen_count"] == "1"
    assert "no F061 queue edit" in repair_rows[0]["forbidden_actions"]
    with outputs["codex_repair_events_csv"].open("r", newline="", encoding="utf-8") as handle:
        event_reader = csv.DictReader(handle)
        assert list(event_reader.fieldnames or []) == CODEX_REPAIR_EVENT_COLUMNS
        event_rows = list(event_reader)
    assert len(event_rows) == 1
    assert event_rows[0]["event_type"] == "created"
    assert event_rows[0]["new_status"] == "queued"
    with outputs["self_organisation_csv"].open("r", newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle).fieldnames or []) == SELF_ORGANISATION_COLUMNS

    report_text = outputs["report"].read_text(encoding="utf-8")
    assert "The manager is not blaming CLF" in report_text
    assert "storage drift" in report_text.lower()
    assert "## Codex Queue" in report_text
    assert "Codex owns the technical follow-up" in report_text
    assert "read-only" in report_text


def test_run_manager_refuses_non_read_only_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="read-only"):
        run_manager(root=tmp_path, read_only=False)


def test_codex_repair_queue_merges_repeated_blockers_without_duplicate_tasks(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)
    _write_live_status(
        tmp_path,
        "blocked_storage_drift",
        "storage_drift_preflight",
        "storage_drift_status=blocked_storage_drift",
    )

    first = run_manager(
        root=tmp_path,
        flow="F_price_list_manager",
        read_only=True,
        write_report_flag=True,
        observed_utc="2026-05-26T11:00:00Z",
    )
    second = run_manager(
        root=tmp_path,
        flow="F_price_list_manager",
        read_only=True,
        write_report_flag=True,
        observed_utc="2026-05-26T11:05:00Z",
    )

    assert first["manager_execution_errors"] == 0
    assert second["manager_execution_errors"] == 0
    queue_path = Path(second["outputs"]["codex_repair_queue_csv"])
    with queue_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["status"] == "queued"
    assert rows[0]["created_utc"] == "2026-05-26T11:00:00Z"
    assert rows[0]["updated_utc"] == "2026-05-26T11:05:00Z"
    assert rows[0]["last_seen_utc"] == "2026-05-26T11:05:00Z"
    assert rows[0]["seen_count"] == "2"

    event_path = Path(second["outputs"]["codex_repair_events_csv"])
    with event_path.open("r", newline="", encoding="utf-8") as handle:
        event_rows = list(csv.DictReader(handle))
    assert len(event_rows) == 1
    assert event_rows[0]["event_type"] == "created"


def test_codex_repair_queue_records_clear_event_when_blocker_vanishes(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)
    _write_live_status(
        tmp_path,
        "blocked_storage_drift",
        "storage_drift_preflight",
        "storage_drift_status=blocked_storage_drift",
    )

    first = run_manager(
        root=tmp_path,
        flow="F_price_list_manager",
        read_only=True,
        write_report_flag=True,
        observed_utc="2026-05-26T11:00:00Z",
    )
    _write_live_status(tmp_path, "completed", "cycle_complete", "")
    second = run_manager(
        root=tmp_path,
        flow="F_price_list_manager",
        read_only=True,
        write_report_flag=True,
        observed_utc="2026-05-26T11:10:00Z",
    )

    queue_path = Path(second["outputs"]["codex_repair_queue_csv"])
    with queue_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["status"] == "cleared_pending_review"

    event_path = Path(first["outputs"]["codex_repair_events_csv"])
    with event_path.open("r", newline="", encoding="utf-8") as handle:
        event_rows = list(csv.DictReader(handle))
    assert [row["event_type"] for row in event_rows] == ["created", "status_changed"]
    assert event_rows[-1]["old_status"] == "queued"
    assert event_rows[-1]["new_status"] == "cleared_pending_review"


def test_cli_status_update_marks_codex_task_and_logs_event(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    _write_minimum_context(tmp_path)
    _write_live_status(
        tmp_path,
        "blocked_storage_drift",
        "storage_drift_preflight",
        "storage_drift_status=blocked_storage_drift",
    )
    summary = run_manager(
        root=tmp_path,
        flow="F_price_list_manager",
        read_only=True,
        write_report_flag=True,
        observed_utc="2026-05-26T11:00:00Z",
    )
    queue_path = Path(summary["outputs"]["codex_repair_queue_csv"])
    with queue_path.open("r", newline="", encoding="utf-8") as handle:
        task_id = list(csv.DictReader(handle))[0]["task_id"]

    exit_code = app_main(
        [
            "--root",
            str(tmp_path),
            "--task-status",
            task_id,
            "--status",
            "in_progress",
            "--note",
            "Started investigation",
            "--observed-utc",
            "2026-05-26T11:15:00Z",
        ]
    )

    assert exit_code == 0
    with queue_path.open("r", newline="", encoding="utf-8") as handle:
        queue_rows = list(csv.DictReader(handle))
    assert queue_rows[0]["status"] == "in_progress"
    assert queue_rows[0]["updated_utc"] == "2026-05-26T11:15:00Z"

    event_path = Path(summary["outputs"]["codex_repair_events_csv"])
    with event_path.open("r", newline="", encoding="utf-8") as handle:
        event_rows = list(csv.DictReader(handle))
    assert event_rows[-1]["event_type"] == "manual_status_update"
    assert event_rows[-1]["old_status"] == "queued"
    assert event_rows[-1]["new_status"] == "in_progress"
    assert event_rows[-1]["note"] == "Started investigation"


def test_codex_repair_queue_marks_missing_blocker_as_cleared_pending_review() -> None:
    existing = [
        {
            "observed_utc": "2026-05-26T11:00:00Z",
            "created_utc": "2026-05-26T11:00:00Z",
            "updated_utc": "2026-05-26T11:00:00Z",
            "last_seen_utc": "2026-05-26T11:00:00Z",
            "seen_count": "2",
            "flow": "F",
            "task_id": "F_storage_drift_preflight_abc123",
            "owner": "Codex",
            "priority": "high",
            "status": "queued",
            "source_incident_code": "storage_drift_preflight",
            "task_summary": "blocked",
            "root_artifact": "out/status.csv",
            "allowed_scope": "manager",
            "forbidden_actions": "none",
            "proof_required": "proof",
        }
    ]

    merged = merge_codex_repair_queue(existing, [], "2026-05-26T11:10:00Z")

    assert len(merged) == 1
    assert merged[0]["status"] == "cleared_pending_review"
    assert merged[0]["updated_utc"] == "2026-05-26T11:10:00Z"
    assert merged[0]["last_seen_utc"] == "2026-05-26T11:00:00Z"


def test_codex_repair_queue_migrates_old_timestamped_task_to_stable_id() -> None:
    old_row = {
        "observed_utc": "2026-05-26T11:00:00Z",
        "created_utc": "",
        "updated_utc": "",
        "last_seen_utc": "",
        "seen_count": "",
        "flow": "F",
        "task_id": "F_storage_drift_preflight_20260526T110000Z",
        "owner": "Codex",
        "priority": "high",
        "status": "queued",
        "source_incident_code": "storage_drift_preflight",
        "task_summary": "old blocked",
        "root_artifact": "out/status.csv",
        "allowed_scope": "manager",
        "forbidden_actions": "none",
        "proof_required": "proof",
    }
    current_row = dict(old_row)
    current_row.update(
        {
            "observed_utc": "2026-05-26T11:05:00Z",
            "created_utc": "2026-05-26T11:05:00Z",
            "updated_utc": "2026-05-26T11:05:00Z",
            "last_seen_utc": "2026-05-26T11:05:00Z",
            "seen_count": "1",
            "task_id": "F_storage_drift_preflight_stable1234",
            "task_summary": "current blocked",
        }
    )

    merged = merge_codex_repair_queue([old_row], [current_row], "2026-05-26T11:05:00Z")

    assert len(merged) == 1
    assert merged[0]["task_id"] == "F_storage_drift_preflight_stable1234"
    assert merged[0]["created_utc"] == "2026-05-26T11:00:00Z"
    assert merged[0]["last_seen_utc"] == "2026-05-26T11:05:00Z"
