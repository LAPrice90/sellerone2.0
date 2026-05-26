from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM001_build_test_fixtures import build_test_fixtures
from scripts.flows.F.price_list_manager.FPM060_build_status_dashboard import build_status_dashboard
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_HANDOFF_PREVIEW_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    QUEUE_CONTROL_COLUMNS,
    SOURCE_ACQUISITION_COLUMNS,
    STATUS_DASHBOARD_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _write_registry(root: Path) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "suppliers.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_folder_path": "",
                "existing_supplier_config_path": "config/feeder/suppliers/shure_cosmetics.json",
                "converter_id": "shure_cosmetics",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "pilot",
                "active_flag": "1",
                "notes": "test row",
            }
        )
        writer.writerow(
            {
                "supplier_id": "dhb",
                "supplier_name": "DHB",
                "source_type": "manual_request",
                "source_subtype": "desktop_csv_folder",
                "source_url": "",
                "source_folder_path": r"C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox",
                "existing_supplier_config_path": "",
                "converter_id": "dhb",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "manual test row",
            }
        )


def test_fpm060_builds_read_only_status_dashboard_from_test_mode_rows(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    build_test_fixtures(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        observed_utc="2026-04-30T09:00:00Z",
    )

    summary = build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T09:05:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    csv_path = test_dir / "status_dashboard.csv"
    html_path = test_dir / "status_dashboard.html"

    assert summary["status"] == "success"
    assert summary["dashboard_rows"] == 2
    assert summary["web_unprocessed_total"] == 10
    assert csv_path.exists()
    assert html_path.exists()

    dashboard = pd.read_csv(csv_path, dtype=str).fillna("")
    assert list(dashboard.columns) == STATUS_DASHBOARD_COLUMNS
    by_supplier = dashboard.set_index("supplier_name")
    assert by_supplier.loc["Shure Cosmetics", "queue_position"] == "1"
    assert by_supplier.loc["Shure Cosmetics", "source_method"] == "CSV link"
    assert by_supplier.loc["Shure Cosmetics", "file_state"] == "Ready"
    assert by_supplier.loc["Shure Cosmetics", "queue_state"] == "Active"
    assert by_supplier.loc["Shure Cosmetics", "bot_status"] == "Test Ready"
    assert by_supplier.loc["Shure Cosmetics", "web_unprocessed"] == "10"
    assert by_supplier.loc["Shure Cosmetics", "web_pass"] == "0"
    assert by_supplier.loc["Shure Cosmetics", "web_fail"] == "0"
    assert by_supplier.loc["Shure Cosmetics", "web_rescan"] == "0"
    assert by_supplier.loc["Shure Cosmetics", "second_unprocessed"] == "0"
    assert by_supplier.loc["DHB", "queue_state"] == "Needs Manual File"
    assert by_supplier.loc["DHB", "file_state"] == "Missing"
    assert by_supplier.loc["DHB", "operator_action"] == "Request price file"

    html_text = html_path.read_text(encoding="utf-8")
    assert "Queue" in html_text
    assert "Manual File Alerts" in html_text
    assert "Pause" in html_text
    assert "Prioritise" in html_text
    assert "Bot Status" in html_text
    assert "Web Scraper" in html_text
    assert "Second Checks" in html_text
    assert "Shure Cosmetics" in html_text
    assert "DHB" in html_text
    assert "Missing files move down the queue" in html_text
    assert "Automatic handoff runs when the active scan finishes" in html_text
    assert "Preview not built" not in html_text
    assert not (tmp_path / "out" / "systems" / "F" / "inbox").exists()
    assert not (tmp_path / "out" / "systems" / "F" / "live").exists()


def test_fpm060_monthly_manual_supplier_rolls_over_next_month(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": r"C:\Users\Luke\Desktop\Amazon price files\Bliss\Inbox",
                "existing_supplier_config_path": "",
                "converter_id": "bliss_distribution",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "monthly",
            }
        ]
    ).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "bliss_april",
                "supplier_id": "bliss_distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": r"C:\Users\Luke\Desktop\Amazon price files\Bliss\Processed\april.xlsx",
                "source_file_hash": "hash",
                "converted_file_path": "converted.csv",
                "source_row_count": "2",
                "valid_row_count": "2",
                "held_row_count": "0",
                "new_row_count": "2",
                "changed_row_count": "0",
                "eligible_row_count": "2",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            }
        ],
        columns=PRICE_LIST_BATCH_COLUMNS,
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "bliss_april",
                "supplier_id": "bliss_distribution",
                "row_key": "r1",
                "supplier_sku": "B1",
                "barcode": "9781568825328",
                "unit_cost": "28.57",
                "currency": "GBP",
                "source_row_hash": "r1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "supplier_converter_valid_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        columns=BATCH_ROW_COLUMNS,
    ).to_csv(test_dir / "batch_rows.csv", index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_state": "missing",
                "status": "warn",
                "source_location": r"C:\Users\Luke\Desktop\Amazon price files\Bliss\Inbox",
                "latest_source_path": "",
                "latest_source_name": "",
                "latest_source_mtime_utc": "",
                "file_count": "0",
                "operator_action": "Request price file",
                "checked_at_utc": "2026-04-30T12:00:00Z",
                "notes": "folder_empty",
            }
        ],
        columns=SOURCE_ACQUISITION_COLUMNS,
    ).to_csv(test_dir / "source_acquisition_status.csv", index=False)

    build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T12:01:00Z")
    april_dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    april = april_dashboard.iloc[0]
    assert april["file_state"] == "Ready"
    assert april["queue_state"] == "Queued"
    assert april["bot_status"] == "Queued"
    assert april["web_unprocessed"] == "1"

    pd.DataFrame(
        [
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_state": "missing",
                "status": "warn",
                "source_location": r"C:\Users\Luke\Desktop\Amazon price files\Bliss\Inbox",
                "latest_source_path": "",
                "latest_source_name": "",
                "latest_source_mtime_utc": "",
                "file_count": "0",
                "operator_action": "Request price file",
                "checked_at_utc": "2026-05-01T08:00:00Z",
                "notes": "folder_empty",
            }
        ],
        columns=SOURCE_ACQUISITION_COLUMNS,
    ).to_csv(test_dir / "source_acquisition_status.csv", index=False)

    build_status_dashboard(root=tmp_path, built_at_utc="2026-05-01T08:01:00Z")
    may_dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    may = may_dashboard.iloc[0]
    assert may["file_state"] == "Missing"
    assert may["queue_state"] == "Needs Manual File"
    assert may["operator_action"] == "Request price file"
    assert may["bot_status"] == "Missing"


def test_fpm060_shows_recommended_next_scan_decision(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": r"C:\Users\Luke\Desktop\Amazon price files\Bliss\Inbox",
                "existing_supplier_config_path": "",
                "converter_id": "bliss_distribution",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "monthly",
            }
        ],
        columns=SUPPLIER_REGISTRY_COLUMNS,
    ).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "processed.xlsx",
                "source_file_hash": "hash",
                "converted_file_path": "converted.csv",
                "source_row_count": "2",
                "valid_row_count": "2",
                "held_row_count": "0",
                "new_row_count": "2",
                "changed_row_count": "0",
                "eligible_row_count": "2",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            }
        ],
        columns=PRICE_LIST_BATCH_COLUMNS,
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "row_key": "r1",
                "supplier_sku": "B1",
                "barcode": "9781568825328",
                "unit_cost": "28.57",
                "currency": "GBP",
                "source_row_hash": "r1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "supplier_converter_valid_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        columns=BATCH_ROW_COLUMNS,
    ).to_csv(test_dir / "batch_rows.csv", index=False)
    pd.DataFrame(
        [
            {
                "decision_id": "next",
                "decided_at_utc": "2026-04-30T12:00:00Z",
                "recommended_action": "recommend_test_scan",
                "supplier_id": "bliss_distribution",
                "batch_id": "bliss_batch",
                "reason_code": "highest_eligible_scan_rows_after_cooldown",
                "estimated_scan_rows": "1",
                "estimated_skip_rows": "0",
                "f061_owner_status": "not_checked_test_mode",
                "safe_to_handoff_flag": "0",
                "notes": "handoff_disabled",
            }
        ],
    ).to_csv(test_dir / "manager_decisions.csv", index=False)

    build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T12:01:00Z")
    dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    row = dashboard.iloc[0]
    assert row["queue_state"] == "Recommended"
    assert row["bot_status"] == "Next Scan"
    assert row["operator_action"] == "Recommended next scan"


def test_fpm060_uses_latest_global_decision_for_queue_state(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "shure_cosmetics",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "pilot",
                "active_flag": "1",
                "notes": "old active decision",
            },
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": r"C:\Users\Luke\Desktop\Amazon price files\Bliss\Inbox",
                "existing_supplier_config_path": "",
                "converter_id": "bliss_distribution",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "latest recommended decision",
            },
        ],
        columns=SUPPLIER_REGISTRY_COLUMNS,
    ).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "shure_batch",
                "supplier_id": "shure_cosmetics",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_received_at_utc": "2026-04-30T09:00:00Z",
                "source_file_path": "shure.csv",
                "source_file_hash": "hash_s",
                "converted_file_path": "shure_converted.csv",
                "source_row_count": "1",
                "valid_row_count": "1",
                "held_row_count": "0",
                "new_row_count": "1",
                "changed_row_count": "0",
                "eligible_row_count": "1",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T09:01:00Z",
            },
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "bliss.xlsx",
                "source_file_hash": "hash_b",
                "converted_file_path": "bliss_converted.csv",
                "source_row_count": "1",
                "valid_row_count": "1",
                "held_row_count": "0",
                "new_row_count": "1",
                "changed_row_count": "0",
                "eligible_row_count": "1",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            },
        ],
        columns=PRICE_LIST_BATCH_COLUMNS,
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "shure_batch",
                "supplier_id": "shure_cosmetics",
                "row_key": "s1",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "unit_cost": "1.00",
                "currency": "GBP",
                "source_row_hash": "s1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "row_key": "b1",
                "supplier_sku": "B1",
                "barcode": "5000000000002",
                "unit_cost": "1.00",
                "currency": "GBP",
                "source_row_hash": "b1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
        ],
        columns=BATCH_ROW_COLUMNS,
    ).to_csv(test_dir / "batch_rows.csv", index=False)
    pd.DataFrame(
        [
            {
                "decision_id": "old_shure",
                "decided_at_utc": "2026-04-30T18:05:00Z",
                "recommended_action": "run_test_scan",
                "supplier_id": "shure_cosmetics",
                "batch_id": "shure_batch",
                "reason_code": "old_test_seed",
                "estimated_scan_rows": "1",
                "estimated_skip_rows": "0",
                "f061_owner_status": "not_checked_test_mode",
                "safe_to_handoff_flag": "0",
                "notes": "old decision",
            },
            {
                "decision_id": "latest_bliss",
                "decided_at_utc": "2026-04-30T12:00:00Z",
                "recommended_action": "recommend_test_scan",
                "supplier_id": "bliss_distribution",
                "batch_id": "bliss_batch",
                "reason_code": "highest_eligible_scan_rows_after_cooldown",
                "estimated_scan_rows": "1",
                "estimated_skip_rows": "0",
                "f061_owner_status": "not_checked_test_mode",
                "safe_to_handoff_flag": "0",
                "notes": "latest decision",
            },
        ],
        columns=MANAGER_DECISION_COLUMNS,
    ).to_csv(test_dir / "manager_decisions.csv", index=False)

    build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T12:01:00Z")
    dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    by_supplier = dashboard.set_index("supplier_id")

    assert by_supplier.loc["bliss_distribution", "queue_position"] == "1"
    assert by_supplier.loc["bliss_distribution", "queue_state"] == "Recommended"
    assert by_supplier.loc["shure_cosmetics", "queue_state"] == "Queued"


def test_fpm060_renders_latest_handoff_readiness_panel(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://example.test/stax.csv",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "stax",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "1",
                "manual_request_required_flag": "0",
                "priority_band": "api",
                "active_flag": "1",
                "notes": "stax",
            }
        ],
        columns=SUPPLIER_REGISTRY_COLUMNS,
    ).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "stax.csv",
                "source_file_hash": "hash",
                "converted_file_path": "stax_converted.csv",
                "source_row_count": "1",
                "valid_row_count": "1",
                "held_row_count": "0",
                "new_row_count": "1",
                "changed_row_count": "0",
                "eligible_row_count": "1",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            }
        ],
        columns=PRICE_LIST_BATCH_COLUMNS,
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "row_key": "s1",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "unit_cost": "1.00",
                "currency": "GBP",
                "source_row_hash": "s1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        columns=BATCH_ROW_COLUMNS,
    ).to_csv(test_dir / "batch_rows.csv", index=False)
    pd.DataFrame(
        [
            {
                "handoff_id": "handoff_old",
                "built_at_utc": "2026-04-30T09:00:00Z",
                "mode": "stage_only",
                "supplier_id": "old",
                "supplier_name": "Old",
                "batch_id": "old_batch",
                "run_id": "old_run",
                "staged_rows": "1",
                "live_apply_allowed": "1",
                "f061_idle_status": "idle",
                "block_reason": "",
                "staged_active_run_path": "old.csv",
                "staged_run_state_path": "old_state.csv",
            },
            {
                "handoff_id": "handoff_latest",
                "built_at_utc": "2026-04-30T12:00:00Z",
                "mode": "stage_only",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "batch_id": "stax_batch",
                "run_id": "stax_run",
                "staged_rows": "24231",
                "live_apply_allowed": "0",
                "f061_idle_status": "busy",
                "block_reason": "f061_not_idle:pending_active=20216",
                "staged_active_run_path": "staged.csv",
                "staged_run_state_path": "state.csv",
            },
        ],
        columns=F061_HANDOFF_PREVIEW_COLUMNS,
    ).to_csv(test_dir / "f061_handoff_preview.csv", index=False)

    build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T12:01:00Z")

    html_text = (test_dir / "status_dashboard.html").read_text(encoding="utf-8")
    assert "Blocked - F061 busy" not in html_text
    assert "24231 staged" not in html_text
    assert "f061_not_idle:pending_active=20216" not in html_text


def test_fpm060_displays_queue_controls(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://example.test/stax.csv",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "stax",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "1",
                "manual_request_required_flag": "0",
                "priority_band": "api",
                "active_flag": "1",
                "notes": "paused",
            },
            {
                "supplier_id": "heo",
                "supplier_name": "Heo",
                "source_type": "api_pull",
                "source_subtype": "api_json",
                "source_url": "https://example.test/heo",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "heo",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "api",
                "active_flag": "1",
                "notes": "prioritised",
            },
        ],
        columns=SUPPLIER_REGISTRY_COLUMNS,
    ).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "stax.csv",
                "source_file_hash": "hash_s",
                "converted_file_path": "stax_converted.csv",
                "source_row_count": "1",
                "valid_row_count": "1",
                "held_row_count": "0",
                "new_row_count": "1",
                "changed_row_count": "0",
                "eligible_row_count": "1",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            },
            {
                "batch_id": "heo_batch",
                "supplier_id": "heo",
                "source_type": "api_pull",
                "source_subtype": "api_json",
                "source_received_at_utc": "2026-04-30T10:05:00Z",
                "source_file_path": "heo.csv",
                "source_file_hash": "hash_h",
                "converted_file_path": "heo_converted.csv",
                "source_row_count": "1",
                "valid_row_count": "1",
                "held_row_count": "0",
                "new_row_count": "1",
                "changed_row_count": "0",
                "eligible_row_count": "1",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:06:00Z",
            },
        ],
        columns=PRICE_LIST_BATCH_COLUMNS,
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "row_key": "s1",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "s1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "heo_batch",
                "supplier_id": "heo",
                "row_key": "h1",
                "supplier_sku": "H1",
                "barcode": "5000000000002",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "h1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
        ],
        columns=BATCH_ROW_COLUMNS,
    ).to_csv(test_dir / "batch_rows.csv", index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": "stax",
                "control_state": "paused",
                "priority_rank": "",
                "reason": "operator pause",
                "updated_at_utc": "2026-04-30T11:00:00Z",
            },
            {
                "supplier_id": "heo",
                "control_state": "prioritised",
                "priority_rank": "1",
                "reason": "operator priority",
                "updated_at_utc": "2026-04-30T11:01:00Z",
            },
        ],
        columns=QUEUE_CONTROL_COLUMNS,
    ).to_csv(test_dir / "queue_controls.csv", index=False)

    build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T12:01:00Z")

    dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    by_supplier = dashboard.set_index("supplier_id")
    assert by_supplier.loc["heo", "queue_position"] == "1"
    assert by_supplier.loc["heo", "queue_state"] == "Prioritised"
    assert by_supplier.loc["heo", "control_state"] == "Prioritised #1"
    assert by_supplier.loc["stax", "queue_state"] == "Paused"
    assert by_supplier.loc["stax", "bot_status"] == "Paused"
    assert by_supplier.loc["stax", "operator_action"] == "Paused by operator"

    html_text = (test_dir / "status_dashboard.html").read_text(encoding="utf-8")
    assert "Prioritised #1" in html_text
    assert "Paused by operator" in html_text
