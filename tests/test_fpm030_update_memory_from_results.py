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
from scripts.flows.F.price_list_manager.FPM020_run_placeholder_scanner import run_placeholder_scanner
from scripts.flows.F.price_list_manager.FPM030_update_memory_from_results import update_memory_from_results
from scripts.flows.F.price_list_manager.FPM060_build_status_dashboard import build_status_dashboard
from scripts.flows.F.price_list_manager._schemas import BARCODE_SCAN_MEMORY_COLUMNS, SUPPLIER_REGISTRY_COLUMNS


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


def test_fpm030_updates_memory_and_dashboard_counts(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    build_test_fixtures(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        observed_utc="2026-04-30T09:00:00Z",
    )
    run_placeholder_scanner(root=tmp_path, scanned_at_utc="2026-04-30T09:10:00Z")

    summary = update_memory_from_results(root=tmp_path, observed_utc="2026-04-30T09:11:00Z")
    dashboard_summary = build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T09:12:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    memory = pd.read_csv(test_dir / "barcode_scan_memory.csv", dtype=str).fillna("")
    dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")

    assert summary["status"] == "success"
    assert summary["result_rows"] == 10
    assert summary["memory_rows"] == 10
    assert summary["unresolved_rows"] == 0
    assert summary["health_fail_rows"] == 0
    assert list(memory.columns) == BARCODE_SCAN_MEMORY_COLUMNS
    assert len(memory) == 10
    assert memory["memory_key"].nunique() == 10
    assert set(memory["last_result_status"]) == {"PASS", "FAIL", "RESCAN"}
    assert memory.loc[memory["cooldown_basis"] == "SELLERHISTORYFAIL", "cooldown_until_utc"].iloc[0] == "2026-10-27T09:10:00Z"
    assert memory.loc[memory["cooldown_basis"] == "BRANDFAIL", "cooldown_until_utc"].iloc[0] == "2026-10-27T09:10:00Z"
    assert memory.loc[memory["cooldown_basis"] == "PASS", "cooldown_until_utc"].iloc[0] == ""

    by_supplier = dashboard.set_index("supplier_name")
    assert dashboard_summary["dashboard_rows"] == 2
    assert dashboard_summary["web_unprocessed_total"] == 0
    assert by_supplier.loc["Shure Cosmetics", "web_unprocessed"] == "0"
    assert by_supplier.loc["Shure Cosmetics", "web_pass"] == "1"
    assert by_supplier.loc["Shure Cosmetics", "web_fail"] == "8"
    assert by_supplier.loc["Shure Cosmetics", "web_rescan"] == "1"
    assert by_supplier.loc["DHB", "queue_state"] == "Needs Manual File"
    assert int((health["status"].str.lower() == "fail").sum()) == 0
    assert not (tmp_path / "out" / "systems" / "F" / "inbox").exists()
    assert not (tmp_path / "out" / "systems" / "F" / "live").exists()
