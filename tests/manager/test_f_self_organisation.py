from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.schemas import F_MANIFEST_PRIORITY_COLUMNS, F_SCRIPT_REGISTRATION_COLUMNS, validate_manifest
from sellerone_manager.self_organisation import (
    build_f_script_registration_report,
    write_f_self_organisation_outputs,
)


def _manifest() -> dict:
    return {
        "id": "F_price_list_manager",
        "display_name": "F Price List Manager",
        "flow": "F",
        "owner_entrypoint": "scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py",
        "worker_entrypoint": "scripts/flows/F/F061_run_legacy_first_checks_local.py",
        "health_sources": [{"name": "live", "path": "out/live.csv"}],
        "status_sources": [{"name": "status", "path": "out/status.csv"}],
        "outputs": [{"name": "active", "path": "out/active.csv"}],
        "freshness_rules": ["status_warn_after_180_minutes"],
        "needs_user_signals": ["manual_file_needed"],
        "safe_actions": ["read_status"],
        "forbidden_actions": ["run_worker"],
    }


def _write_manifest(root: Path, file_name: str, manifest: dict) -> None:
    path = root / "config" / "manager" / "modules" / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _script_manifest(script_id: str, script_path: str) -> dict:
    return {
        "id": script_id,
        "display_name": script_id.replace("_", " "),
        "flow": "F",
        "purpose": f"Register {script_id} for manager self-organisation.",
        "owner_entrypoint": script_path,
        "worker_entrypoint": script_path,
        "health_sources": [{"name": "health", "path": "out/systems/F/price_list_manager/test_mode/health.csv"}],
        "status_sources": [{"name": "status", "path": "out/systems/F/price_list_manager/test_mode/status_dashboard.csv"}],
        "outputs": [{"name": "output", "path": "out/systems/F/price_list_manager/test_mode/example.csv"}],
        "freshness_rules": ["status_warn_after_10080_minutes"],
        "needs_user_signals": ["manual_file_needed"],
        "safe_actions": ["read_status"],
        "forbidden_actions": [
            "edit_worker_logic",
            "run_worker_cycle",
            "write_google_sheets",
            "change_queue_state",
            "change_pricing",
            "delete_outputs",
        ],
        "manager_notes": "test manifest",
    }


def _write_script(root: Path, rel_path: str, body: str | None = None) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    script_body = body or "def main():\n    return 0\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n"
    path.write_text(script_body, encoding="utf-8")


def _rows_by_path(report: dict) -> dict[str, dict[str, str]]:
    return {row["script_path"]: row for row in report["rows"]}


def _priority_rows_by_path(report: dict) -> dict[str, dict[str, str]]:
    priority = report["manifest_priority_report"]
    return {row["script_path"]: row for row in priority["rows"]}


def test_registered_f_scripts_are_recognised_without_inventory(tmp_path: Path) -> None:
    _write_script(tmp_path, "scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py")
    _write_script(tmp_path, "scripts/flows/F/F061_run_legacy_first_checks_local.py")
    (tmp_path / "project_control").mkdir(parents=True, exist_ok=True)
    (tmp_path / "project_control" / "FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md").write_text(
        "# Guidebook\n",
        encoding="utf-8",
    )

    report = build_f_script_registration_report(
        root=tmp_path,
        manifest=_manifest(),
        observed_utc="2026-05-26T12:00:00Z",
    )

    rows = _rows_by_path(report)
    assert rows["scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py"]["classification"] == "registered"
    assert rows["scripts/flows/F/F061_run_legacy_first_checks_local.py"]["classification"] == "registered"
    assert rows["scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py"]["health_source"] == "1"
    assert report["summary"]["inventory_exists"] is False


def test_unregistered_and_needs_review_f_scripts_are_reported(tmp_path: Path) -> None:
    _write_script(tmp_path, "scripts/flows/F/F099_new_worker.py")
    _write_script(tmp_path, "scripts/flows/F/price_list_manager/FPM999_new_manager_step.py")

    report = build_f_script_registration_report(
        root=tmp_path,
        manifest=_manifest(),
        observed_utc="2026-05-26T12:00:00Z",
    )

    rows = _rows_by_path(report)
    assert rows["scripts/flows/F/F099_new_worker.py"]["classification"] == "unregistered"
    assert rows["scripts/flows/F/F099_new_worker.py"]["needs_codex_review"] == "1"
    assert rows["scripts/flows/F/price_list_manager/FPM999_new_manager_step.py"]["classification"] == "needs_review"
    assert "owner" in rows["scripts/flows/F/F099_new_worker.py"]["missing_fields"]


def test_one_off_and_legacy_scripts_are_exempted(tmp_path: Path) -> None:
    _write_script(tmp_path, "scripts/one_off/F999_temp_repair.py")
    _write_script(tmp_path, "scripts/flows/F/legacy_scanner_2_1/Webscrape.py")

    report = build_f_script_registration_report(
        root=tmp_path,
        manifest=_manifest(),
        observed_utc="2026-05-26T12:00:00Z",
    )

    rows = _rows_by_path(report)
    assert rows["scripts/one_off/F999_temp_repair.py"]["classification"] == "one_off_exempt"
    assert rows["scripts/one_off/F999_temp_repair.py"]["is_exempt"] == "1"
    assert rows["scripts/flows/F/legacy_scanner_2_1/Webscrape.py"]["classification"] == "legacy_exempt"
    assert rows["scripts/flows/F/legacy_scanner_2_1/Webscrape.py"]["needs_codex_review"] == "0"


def test_missing_script_inventory_does_not_crash_manager_report(tmp_path: Path) -> None:
    _write_script(tmp_path, "scripts/flows/F/F099_new_worker.py")

    report = build_f_script_registration_report(
        root=tmp_path,
        manifest=_manifest(),
        observed_utc="2026-05-26T12:00:00Z",
    )

    assert report["summary"]["inventory_exists"] is False
    assert report["summary"]["script_count"] == 1


def test_self_organisation_outputs_have_stable_headers(tmp_path: Path) -> None:
    _write_script(
        tmp_path,
        "scripts/flows/F/F099_new_worker.py",
        "OUTPUT = 'out/systems/F/example.csv'\n"
        "def main():\n"
        "    return OUTPUT\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0)\n",
    )
    report = build_f_script_registration_report(
        root=tmp_path,
        manifest=_manifest(),
        observed_utc="2026-05-26T12:00:00Z",
    )

    paths = write_f_self_organisation_outputs(report, tmp_path / "out" / "systems" / "M")

    with paths["f_script_registration_csv"].open("r", newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle).fieldnames or []) == F_SCRIPT_REGISTRATION_COLUMNS

    with paths["f_manifest_priority_csv"].open("r", newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle).fieldnames or []) == F_MANIFEST_PRIORITY_COLUMNS

    payload = json.loads(paths["f_script_registration_json"].read_text(encoding="utf-8"))
    assert payload["summary"]["script_count"] == 1
    priority_payload = json.loads(paths["f_manifest_priority_json"].read_text(encoding="utf-8"))
    assert priority_payload["summary"]["top_3_scripts"] == ["scripts/flows/F/F099_new_worker.py"]
    markdown = paths["f_self_organisation_report"].read_text(encoding="utf-8")
    assert "Does This Block F Operation" in markdown
    assert "No. This is a manager-owned organisation report only." in markdown
    priority_markdown = paths["f_manifest_priority_report"].read_text(encoding="utf-8")
    assert "Top 3 Scripts To Register Next" in priority_markdown


def test_manifest_priority_ranking_picks_live_f_control_scripts(tmp_path: Path) -> None:
    _write_script(tmp_path, "scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py")
    _write_script(tmp_path, "scripts/flows/F/F061_run_legacy_first_checks_local.py")
    _write_script(
        tmp_path,
        "scripts/flows/F/price_list_manager/FPM170_supervise_live_cycle.py",
        "LIVE = 'out/systems/F/price_list_manager/live/live_cycle_status.csv'\n"
        "QUEUE = 'supplier_price_list_active_run.csv'\n"
        "def main():\n"
        "    return LIVE, QUEUE\n",
    )
    _write_script(
        tmp_path,
        "scripts/flows/F/price_list_manager/FPM129_storage_drift_guard.py",
        "REPORT = 'out/systems/F/price_list_manager/live/storage_drift_report.csv'\n"
        "def main():\n"
        "    return 'storage_drift_preflight', REPORT\n",
    )
    _write_script(
        tmp_path,
        "scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py",
        "DASHBOARD = 'out/systems/F/price_list_manager/test_mode/status_dashboard.csv'\n"
        "def main():\n"
        "    return 'supplier_status_dashboard', DASHBOARD\n",
    )
    runtime_path = tmp_path / "config" / "runtime_owner_contract.json"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        '{"F": "scripts/flows/F/price_list_manager/FPM170_supervise_live_cycle.py"}',
        encoding="utf-8",
    )

    report = build_f_script_registration_report(
        root=tmp_path,
        manifest=_manifest(),
        observed_utc="2026-05-26T12:00:00Z",
    )

    priority = report["manifest_priority_report"]
    top_three = [row["script_path"] for row in priority["rows"] if row["priority_band"] == "top_3"]
    assert top_three == [
        "scripts/flows/F/price_list_manager/FPM170_supervise_live_cycle.py",
        "scripts/flows/F/price_list_manager/FPM129_storage_drift_guard.py",
        "scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py",
    ]
    rows = _priority_rows_by_path(report)
    assert rows["scripts/flows/F/price_list_manager/FPM170_supervise_live_cycle.py"]["live_entrypoint"] == "1"
    assert rows["scripts/flows/F/price_list_manager/FPM129_storage_drift_guard.py"]["storage_drift_or_preflight"] == "1"
    assert rows["scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py"]["supplier_status_dashboard"] == "1"


def test_manifest_priority_defers_registered_one_off_and_legacy_scripts(tmp_path: Path) -> None:
    _write_script(tmp_path, "scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py")
    _write_script(tmp_path, "scripts/flows/F/F061_run_legacy_first_checks_local.py")
    _write_script(tmp_path, "scripts/one_off/F042_recover_sql_newer_storage_drift.py")
    _write_script(tmp_path, "scripts/flows/F/legacy_scanner_2_1/Webscrape.py")

    report = build_f_script_registration_report(
        root=tmp_path,
        manifest=_manifest(),
        observed_utc="2026-05-26T12:00:00Z",
    )

    rows = _priority_rows_by_path(report)
    assert rows["scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py"]["recommended_action"] == "defer_already_registered"
    assert rows["scripts/flows/F/F061_run_legacy_first_checks_local.py"]["recommended_action"] == "defer_already_registered"
    assert rows["scripts/one_off/F042_recover_sql_newer_storage_drift.py"]["recommended_action"] == "defer_one_off_exempt"
    assert rows["scripts/flows/F/legacy_scanner_2_1/Webscrape.py"]["recommended_action"] == "defer_legacy_exempt"


def test_additional_f_manifests_register_top_three_and_rerank(tmp_path: Path) -> None:
    top_three = {
        "FPM170_supervise_live_cycle": "scripts/flows/F/price_list_manager/FPM170_supervise_live_cycle.py",
        "FPM129_storage_drift_guard": "scripts/flows/F/price_list_manager/FPM129_storage_drift_guard.py",
        "FPM050_build_next_action_report": "scripts/flows/F/price_list_manager/FPM050_build_next_action_report.py",
    }
    _write_script(tmp_path, "scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py")
    _write_script(tmp_path, "scripts/flows/F/F061_run_legacy_first_checks_local.py")
    for script_path in top_three.values():
        _write_script(tmp_path, script_path)
    _write_script(
        tmp_path,
        "scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py",
        "DASHBOARD = 'out/systems/F/price_list_manager/test_mode/status_dashboard.csv'\n"
        "def main():\n"
        "    return 'supplier_status_dashboard', DASHBOARD\n",
    )
    for script_id, script_path in top_three.items():
        _write_manifest(tmp_path, f"{script_id}.json", _script_manifest(script_id, script_path))

    report = build_f_script_registration_report(
        root=tmp_path,
        manifest=_manifest(),
        observed_utc="2026-05-26T12:00:00Z",
    )

    rows = _rows_by_path(report)
    for script_id, script_path in top_three.items():
        assert rows[script_path]["classification"] == "registered"
        assert rows[script_path]["manager_module_id"] == script_id

    top_scripts = report["manifest_priority_report"]["summary"]["top_3_scripts"]
    for script_path in top_three.values():
        assert script_path not in top_scripts
    assert top_scripts[0] == "scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py"


def test_v1_3_top_three_repo_manifests_validate() -> None:
    manifest_names = [
        "F005_build_supplier_price_list_universal.json",
        "F010_build_feeder_candidate_intake.json",
        "F020_build_feeder_candidate_classification.json",
        "F030_build_shared_feeder_pass_logic.json",
        "F040_build_feeder_candidate_approval_queue.json",
        "F050_build_feeder_po_handoff.json",
        "F060_build_legacy_sheet_review_pack.json",
        "F070_build_backtest_policy_snapshot.json",
        "F062_reset_supplier_test_mode.json",
        "F071_build_backtest_input_view.json",
        "F072_run_backtest_replay.json",
        "F073_build_backtest_summary.json",
        "F074_build_backtest_health.json",
        "F075_apply_backtest_policy_updates.json",
        "F080_build_feedback_calibration_shadow.json",
        "F090_build_amazon_listing_intake.json",
        "F091_reserve_amazon_listing_skus.json",
        "F092_build_amazon_listing_drafts.json",
        "F093_run_amazon_listing_preview.json",
        "F094_submit_amazon_listing_drafts.json",
        "F095_check_amazon_listing_submission_status.json",
        "F096_reconcile_amazon_listing_submissions.json",
        "F097_check_amazon_listing_restrictions.json",
        "F098_build_brand_approval_queue.json",
        "FPM001_build_test_fixtures.json",
        "FPM010_check_acquisition_sources.json",
        "FPM011_import_ready_sources.json",
        "FPM012_enrich_batch_rows_for_f061.json",
        "FPM013_download_ready_url_sources.json",
        "FPM014_fetch_api_sources.json",
        "FPM015_fetch_google_sheet_sources.json",
        "FPM016_fetch_gmail_email_sources.json",
        "FPM020_run_placeholder_scanner.json",
        "FPM030_update_memory_from_results.json",
        "FPM170_supervise_live_cycle.json",
        "FPM129_storage_drift_guard.json",
        "FPM040_build_next_action.json",
        "FPM050_build_next_action_report.json",
        "FPM060_build_status_dashboard.json",
        "FPM070_stage_f061_handoff.json",
        "FPM080_set_queue_control.json",
        "FPM090_set_f061_handoff_approval.json",
        "FPM100_apply_f061_handoff.json",
        "FPM110_run_test_mode_cycle.json",
        "FPM120_build_f061_live_trial_samples.json",
        "FPM121_apply_f061_live_trial_supplier.json",
        "FPM125_import_f061_recovery_progress.json",
        "FPM126_update_memory_from_f061_results.json",
        "FPM140_check_review_handoff_ready.json",
        "FPM150_build_completed_review_pack.json",
        "FPM155_apply_review_intelligence_gate.json",
        "FPM156_build_ai_gate_quality_report.json",
        "FPM157_build_incremental_ai_precheck.json",
        "FPM158_ai_precheck_common.json",
        "FPM160_f061_visible_login_maintenance.json",
        "FPM180_build_production_line_run.json",
        "FPM190_build_split_rollout_readiness.json",
        "FPM191_backfill_ai_quality_stamps.json",
        "run_F_price_list_manager_cycle.json",
        "run_F_shure_test_mode_scan_once.json",
        "run_F_supplier_test_mode_scan_once.json",
        "run_F_shure_full_legacy_scan.json",
        "run_F_supplier_full_legacy_scan.json",
    ]
    required_forbidden = {
        "edit_worker_logic",
        "run_worker_cycle",
        "write_google_sheets",
        "change_queue_state",
        "change_pricing",
        "delete_outputs",
    }
    for manifest_name in manifest_names:
        path = ROOT / "config" / "manager" / "modules" / manifest_name
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert validate_manifest(manifest) == []
        assert manifest.get("purpose")
        assert manifest.get("manager_notes")
        assert set(manifest.get("forbidden_actions", [])) >= required_forbidden
        assert set(manifest.get("safe_actions", [])) <= {"read_status", "read_report", "read_snapshot"}
