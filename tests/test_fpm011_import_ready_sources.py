from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM010_check_acquisition_sources import check_acquisition_sources
from scripts.flows.F.price_list_manager.FPM011_import_ready_sources import import_ready_sources
from scripts.flows.F.price_list_manager import FPM011_import_ready_sources as import_module
from scripts.flows.F.price_list_manager.FPM060_build_status_dashboard import build_status_dashboard
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    STATUS_DASHBOARD_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_registry(root: Path, folder: Path) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    with (config_dir / "suppliers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": str(folder),
                "existing_supplier_config_path": "",
                "converter_id": "bliss_distribution",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "test supplier",
            }
        )


def _write_dhb_registry(root: Path, folder: Path) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    with (config_dir / "suppliers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "supplier_id": "dhb",
                "supplier_name": "DHB",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": str(folder),
                "existing_supplier_config_path": "",
                "converter_id": "dhb",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "test supplier",
            }
        )


def _write_td_synnex_registry(root: Path, folder: Path) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    with (config_dir / "suppliers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "source_type": "email_attachment",
                "source_subtype": "daily_email",
                "source_url": "",
                "source_folder_path": str(folder),
                "existing_supplier_config_path": "",
                "converter_id": "td_synnex",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "7",
                "large_file_flag": "1",
                "manual_request_required_flag": "0",
                "priority_band": "daily_email",
                "active_flag": "1",
                "notes": "test supplier",
            }
        )


def _write_tropicana_registry(root: Path, folder: Path) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    with (config_dir / "suppliers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "supplier_id": "tropicana_wholesale",
                "supplier_name": "Tropicana Wholesale",
                "source_type": "email_attachment",
                "source_subtype": "daily_email",
                "source_url": "",
                "source_folder_path": str(folder),
                "existing_supplier_config_path": "",
                "converter_id": "tropicana_wholesale",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "3",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "parked",
                "active_flag": "1",
                "notes": "test supplier",
            }
        )


def _write_dhb_workbook(path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {"No.": "AMA006", "Description": "CB12", "Barcode": "5060035249282", "Trade Price": "2.955056"},
                {"No.": "AMA007", "Description": "No barcode", "Barcode": "", "Trade Price": "1.20"},
            ]
        ).to_excel(writer, index=False, sheet_name="Trade Price")
        pd.DataFrame(
            [
                {
                    "No.": "AUR112",
                    "Description": "Aurelia",
                    "Available Stock": "80",
                    "Clearance Price": "3.65",
                    "Barcode ": "9555002105211",
                }
            ]
        ).to_excel(writer, index=False, sheet_name="End of Line - Whilst Stocks Las")


def test_fpm011_imports_ready_local_csv_once_and_dedupes_hash(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "Bliss Distribution" / "inbox"
    folder.mkdir(parents=True)
    source_file = folder / "bliss_prices.csv"
    source_file.write_text(
        "sku,barcode,cost,currency\n"
        "BLISS-001,5012345678901,1.25,GBP\n"
        "BLISS-002,5012345678902,2.50,GBP\n"
        "BLISS-003,,3.75,GBP\n",
        encoding="utf-8",
    )
    source_text = source_file.read_text(encoding="utf-8")
    _write_registry(tmp_path, folder)
    check_acquisition_sources(
        root=tmp_path,
        checked_at_utc="2026-04-30T11:00:00Z",
        check_remote=False,
    )

    first = import_ready_sources(
        root=tmp_path,
        imported_at_utc="2026-04-30T11:01:00Z",
    )
    second = import_ready_sources(
        root=tmp_path,
        imported_at_utc="2026-04-30T11:02:00Z",
    )
    source_file.write_text(source_text, encoding="utf-8")
    check_acquisition_sources(
        root=tmp_path,
        checked_at_utc="2026-04-30T11:03:00Z",
        check_remote=False,
    )
    third = import_ready_sources(
        root=tmp_path,
        imported_at_utc="2026-04-30T11:04:00Z",
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")

    assert first["status"] == "success"
    assert first["ready_sources"] == 1
    assert first["imported_batches"] == 1
    assert first["duplicate_sources"] == 0
    assert first["health_fail_rows"] == 0
    assert second["imported_batches"] == 0
    assert second["stale_sources"] == 1
    assert second["health_fail_rows"] == 0
    assert third["imported_batches"] == 0
    assert third["duplicate_sources"] == 1
    assert third["health_fail_rows"] == 0
    assert not source_file.exists()
    processed_files = list((folder.parent / "Processed").glob("*.csv"))
    assert len(processed_files) == 2

    assert list(batches.columns) == PRICE_LIST_BATCH_COLUMNS
    assert list(rows.columns) == BATCH_ROW_COLUMNS
    assert len(batches.index) == 1
    assert len(rows.index) == 3
    assert batches.iloc[0]["batch_status"] == "imported_from_source"
    assert batches.iloc[0]["source_row_count"] == "3"
    assert batches.iloc[0]["valid_row_count"] == "2"
    assert batches.iloc[0]["held_row_count"] == "1"
    assert "Processed" in batches.iloc[0]["source_file_path"]
    assert (rows["scan_eligibility"] == "scan_now").sum() == 2
    assert (rows["scan_eligibility"] == "hold").sum() == 1
    assert rows["row_key"].nunique() == 3


def test_fpm011_supersedes_prior_unscanned_supplier_batch_when_new_source_imports(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "Bliss Distribution" / "inbox"
    folder.mkdir(parents=True)
    first_source = folder / "bliss_prices_first.csv"
    first_source.write_text(
        "sku,barcode,cost,currency\n"
        "BLISS-001,5012345678901,1.25,GBP\n",
        encoding="utf-8",
    )
    _write_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-22T10:00:00Z", check_remote=False)
    first = import_ready_sources(root=tmp_path, imported_at_utc="2026-05-22T10:01:00Z")

    second_source = folder / "bliss_prices_second.csv"
    second_source.write_text(
        "sku,barcode,cost,currency\n"
        "BLISS-002,5012345678902,2.50,GBP\n",
        encoding="utf-8",
    )
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-22T10:02:00Z", check_remote=False)
    second = import_ready_sources(root=tmp_path, imported_at_utc="2026-05-22T10:03:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")

    assert first["imported_batches"] == 1
    assert first["superseded_prior_batches"] == 0
    assert second["imported_batches"] == 1
    assert second["superseded_prior_batches"] == 1
    assert len(batches.index) == 2
    first_batch = batches.sort_values("source_received_at_utc", kind="stable").iloc[0]
    second_batch = batches.sort_values("source_received_at_utc", kind="stable").iloc[1]
    assert first_batch["batch_status"] == "superseded"
    assert first_batch["status_reason"] == "superseded_by_newer_source_batch"
    assert second_batch["batch_status"] == "imported_from_source"
    first_batch_eligibility = eligibility[eligibility["batch_id"] == first_batch["batch_id"]]
    assert set(first_batch_eligibility["scan_decision"]) == {"skip"}
    assert set(first_batch_eligibility["decision_reason"]) == {"superseded_batch"}


def test_fpm011_backfills_converter_missing_barcode_from_prior_supplier_sku(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "Bliss Distribution" / "inbox"
    folder.mkdir(parents=True)
    source_file = folder / "bliss_full_stock.xlsx"
    with pd.ExcelWriter(source_file, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "Inventory ID": "BLISS-001",
                    "Description": "Known SKU",
                    "MSRP": "4.99",
                    "Base Price": "1.25",
                },
                {
                    "Inventory ID": "BLISS-002",
                    "Description": "Unknown SKU",
                    "MSRP": "6.99",
                    "Base Price": "2.50",
                },
            ]
        ).to_excel(writer, index=False, sheet_name="Data")
    _write_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-18T09:45:00Z", check_remote=False)

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            {
                "batch_id": "old_bliss_batch",
                "supplier_id": "bliss_distribution",
                "row_key": "old-row",
                "supplier_sku": "BLISS-001",
                "supplier_title": "Old known SKU",
                "barcode": "5012345678901",
                "unit_cost": "1.10",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "old-row",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "supplier_converter_valid_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        BATCH_ROW_COLUMNS,
    )

    summary = import_ready_sources(root=tmp_path, imported_at_utc="2026-05-18T09:46:00Z")

    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    batch_id = batches.iloc[0]["batch_id"]
    imported_rows = rows[rows["batch_id"] == batch_id].set_index("supplier_sku")

    assert summary["imported_batches"] == 1
    assert batches.iloc[0]["source_row_count"] == "2"
    assert batches.iloc[0]["valid_row_count"] == "1"
    assert batches.iloc[0]["held_row_count"] == "1"
    assert imported_rows.loc["BLISS-001", "barcode"] == "5012345678901"
    assert imported_rows.loc["BLISS-001", "scan_eligibility"] == "scan_now"
    assert imported_rows.loc["BLISS-001", "eligibility_reason"] == "supplier_converter_valid_row_barcode_backfilled"
    assert imported_rows.loc["BLISS-002", "scan_eligibility"] == "hold"
    assert imported_rows.loc["BLISS-002", "eligibility_reason"] == "missing_barcode"


def test_fpm011_builds_timeout_queue_after_import_and_skips_active_memory(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "Bliss Distribution" / "inbox"
    folder.mkdir(parents=True)
    (folder / "bliss_prices.csv").write_text(
        "sku,barcode,cost,currency\n"
        "BLISS-001,5012345678901,1.25,GBP\n"
        "BLISS-002,5012345678902,2.50,GBP\n",
        encoding="utf-8",
    )
    _write_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-04-30T11:00:00Z", check_remote=False)

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "barcode_scan_memory.csv",
        [
            {
                "memory_key": "barcode:5012345678901",
                "memory_scope": "global_barcode",
                "supplier_id": "older_supplier",
                "barcode": "5012345678901",
                "asin": "",
                "last_result_status": "FAIL",
                "last_fail_code": "PRICEHISTORYFAIL",
                "last_stage": "webscrape",
                "last_scanned_at_utc": "2026-04-01T00:00:00Z",
                "cooldown_until_utc": "",
                "cooldown_basis": "PRICEHISTORYFAIL",
                "attempt_count": "1",
                "last_batch_id": "old_batch",
                "last_row_hash": "old_hash",
                "updated_at_utc": "2026-04-01T00:00:00Z",
            }
        ],
        BARCODE_SCAN_MEMORY_COLUMNS,
    )

    summary = import_ready_sources(root=tmp_path, imported_at_utc="2026-04-30T11:01:00Z")

    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    by_barcode = eligibility.set_index("barcode")

    assert summary["timeout_scan_rows"] == 1
    assert summary["timeout_skip_rows"] == 1
    assert list(eligibility.columns) == BATCH_SCAN_ELIGIBILITY_COLUMNS
    assert (rows["scan_eligibility"] == "scan_now").sum() == 2
    assert by_barcode.loc["5012345678901", "scan_decision"] == "skip"
    assert by_barcode.loc["5012345678901", "decision_reason"] == "timeout_active"
    assert by_barcode.loc["5012345678901", "cooldown_until_utc"] == "2026-09-28T00:00:00Z"
    assert by_barcode.loc["5012345678902", "scan_decision"] == "scan"
    assert batches.iloc[0]["eligible_row_count"] == "1"
    assert batches.iloc[0]["skipped_cooldown_row_count"] == "1"


def test_fpm011_imported_batch_updates_dashboard_counts(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "Bliss Distribution" / "inbox"
    folder.mkdir(parents=True)
    (folder / "bliss_prices.csv").write_text(
        "sku,ean,trade_price\nBLISS-001,5012345678901,1.25\nBLISS-002,5012345678902,2.50\n",
        encoding="utf-8",
    )
    _write_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-04-30T11:00:00Z", check_remote=False)
    import_ready_sources(root=tmp_path, imported_at_utc="2026-04-30T11:01:00Z")

    summary = build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T11:02:00Z")
    dashboard = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "status_dashboard.csv",
        dtype=str,
    ).fillna("")

    assert summary["dashboard_rows"] == 1
    assert list(dashboard.columns) == STATUS_DASHBOARD_COLUMNS
    row = dashboard.iloc[0]
    assert row["supplier_name"] == "Bliss Distribution"
    assert row["file_state"] == "Ready"
    assert row["queue_state"] == "Queued"
    assert row["bot_status"] == "Queued"
    assert row["operator_action"] == "Price file registered"
    assert row["web_unprocessed"] == "2"

    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-04-30T11:03:00Z", check_remote=False)
    build_status_dashboard(root=tmp_path, built_at_utc="2026-04-30T11:04:00Z")
    dashboard_after_move = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "status_dashboard.csv",
        dtype=str,
    ).fillna("")
    assert dashboard_after_move.iloc[0]["file_state"] == "Ready"
    assert dashboard_after_move.iloc[0]["bot_status"] == "Queued"


def test_fpm011_uses_dhb_converter_for_excel_files(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "DHB" / "Inbox"
    folder.mkdir(parents=True)
    source_file = folder / "Trade Price January 2026.xlsx"
    _write_dhb_workbook(source_file)
    _write_dhb_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-04-30T12:00:00Z", check_remote=False)

    summary = import_ready_sources(root=tmp_path, imported_at_utc="2026-04-30T12:01:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")

    assert summary["imported_batches"] == 1
    assert summary["failed_sources"] == 0
    assert len(batches.index) == 1
    assert batches.iloc[0]["source_row_count"] == "3"
    assert batches.iloc[0]["valid_row_count"] == "2"
    assert batches.iloc[0]["held_row_count"] == "1"
    assert (rows["scan_eligibility"] == "scan_now").sum() == 2
    assert (rows["scan_eligibility"] == "hold").sum() == 1
    by_sku = rows.set_index("supplier_sku")
    assert by_sku.loc["AMA006", "unit_cost"] == "2.96"
    assert by_sku.loc["AUR112", "unit_cost"] == "3.65"
    assert by_sku.loc["AMA007", "eligibility_reason"] == "missing_barcode"
    assert not source_file.exists()
    assert len(list((folder.parent / "Processed").glob("*.xlsx"))) == 1


def test_fpm011_imports_td_synnex_tsv_email_attachment_with_converter(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    source_file = folder / "td_synnex_daily.tsv"
    source_file.write_text(
        (
            "Product ID\tSKU\tBrand\tDescription\tCost Price\tSelling Price\tCurrency\tTimestamp\tStock Level\t"
            "Stock Date\tCategory Code\tAvailability\tCategory Description\tEnd User\tEAN\tSpecial\tDepartment\t"
            "Subcategory\tRestricted\tWeight (kg)\n"
            "P1\tTD-001\tTD Brand\tReady barcode item\t12.34\t15.00\tGBP\t2026-05-19\t5\t2026-05-19\t"
            "C1\tY\tToys\tN\t5012345678901\tN\tD\tS\tN\t1\n"
            "P2\tTD-002\tTD Brand\tMissing cost item\t\t15.00\tGBP\t2026-05-19\t2\t2026-05-19\t"
            "C1\tY\tToys\tN\t5012345678902\tN\tD\tS\tN\t1\n"
        ),
        encoding="utf-8",
    )
    _write_td_synnex_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-19T08:30:00Z", check_remote=False)

    summary = import_ready_sources(root=tmp_path, imported_at_utc="2026-05-19T08:31:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    by_sku = rows.set_index("supplier_sku")

    assert summary["imported_batches"] == 1
    assert summary["failed_sources"] == 0
    assert batches.iloc[0]["source_row_count"] == "2"
    assert batches.iloc[0]["valid_row_count"] == "1"
    assert batches.iloc[0]["held_row_count"] == "1"
    assert by_sku.loc["TD-001", "scan_eligibility"] == "scan_now"
    assert by_sku.loc["TD-001", "unit_cost"] == "12.34"
    assert by_sku.loc["TD-001", "barcode"] == "5012345678901"
    assert by_sku.loc["TD-002", "scan_eligibility"] == "hold"
    assert by_sku.loc["TD-002", "eligibility_reason"] == "missing_cost"
    assert not source_file.exists()
    assert len(list((folder.parent / "Processed").glob("*.tsv"))) == 1


def test_fpm011_imports_real_td_synnex_21_column_tsv_without_shift(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    source_file = folder / "Enhanced-GB.tsv"
    source_file.write_text(
        (
            "127693\tAP9815\tAPC\tUPS INTERFACE EXTENSION\t30.93\t43.73\tGBP\t19/05/2026 02:45:18\t"
            "0\t05/06/2026\tUPSACC\tY\tEnd User Opportunity over 7.5K\tUPS\tN\t731304002727\tFalse\t"
            "Peripherals\tUPS Accessories\tN\t.340\n"
            "429754\tAR8129\tAPC\tCable Management Arm\t117.17\t157.46\tGBP\t19/05/2026 02:45:18\t"
            "32\t\tNWCABSYST\tY\tEnd User Opportunity over 7.5K\tNetworking Cables\tN\t731304003557\tFalse\t"
            "Networking\tCable Systems & Accessories\tN\t.540\n"
        ),
        encoding="utf-8",
    )
    _write_td_synnex_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-19T10:40:00Z", check_remote=False)

    summary = import_ready_sources(root=tmp_path, imported_at_utc="2026-05-19T10:41:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    by_sku = rows.set_index("supplier_sku")

    assert summary["imported_batches"] == 1
    assert summary["failed_sources"] == 0
    assert len(rows.index) == 2
    assert "APC" not in set(rows["supplier_sku"])
    assert by_sku.loc["AP9815", "supplier_title"] == "UPS INTERFACE EXTENSION"
    assert by_sku.loc["AP9815", "unit_cost"] == "30.93"
    assert by_sku.loc["AP9815", "barcode"] == "731304002727"
    assert by_sku.loc["AR8129", "supplier_title"] == "Cable Management Arm"
    assert by_sku.loc["AR8129", "unit_cost"] == "117.17"
    assert by_sku.loc["AR8129", "barcode"] == "731304003557"


def test_fpm011_imports_tropicana_stock_export_as_missing_cost_holds(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "Tropicana Wholesale" / "inbox"
    folder.mkdir(parents=True)
    source_file = folder / "StockExport_190526_090831.xlsx"
    with pd.ExcelWriter(source_file, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "Brand name": "10x Athletic",
                    "Sku code": "10X002",
                    "Name": "10X Athletic Whey Protein 700g Strawberry Milkshake",
                    "Actual quantity": "0",
                    "Product group description": "10X Athletic Whey Protein 700g",
                    "Barcode": "5060685930028",
                },
                {
                    "Brand name": "10x Athletic",
                    "Sku code": "10X004",
                    "Name": "10X Athletic Vegan Protein 540g Chocolate Strawberry",
                    "Actual quantity": "5",
                    "Product group description": "10X Athletic Vegan Protein 540g",
                    "Barcode": "5060685930769",
                },
            ]
        ).to_excel(writer, index=False, sheet_name="Sheet1")
    _write_tropicana_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-19T10:20:00Z", check_remote=False)

    summary = import_ready_sources(root=tmp_path, imported_at_utc="2026-05-19T10:21:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    by_sku = rows.set_index("supplier_sku")

    assert summary["imported_batches"] == 1
    assert summary["failed_sources"] == 0
    assert batches.iloc[0]["supplier_id"] == "tropicana_wholesale"
    assert batches.iloc[0]["source_row_count"] == "2"
    assert batches.iloc[0]["valid_row_count"] == "0"
    assert batches.iloc[0]["held_row_count"] == "2"
    assert by_sku.loc["10X002", "supplier_title"] == "10X Athletic Whey Protein 700g Strawberry Milkshake"
    assert by_sku.loc["10X002", "barcode"] == "5060685930028"
    assert by_sku.loc["10X002", "eligibility_reason"] == "missing_cost"
    assert by_sku.loc["10X004", "scan_eligibility"] == "hold"
    assert not source_file.exists()
    assert len(list((folder.parent / "Processed").glob("*.xlsx"))) == 1


def test_fpm011_imports_td_synnex_zip_email_attachment_with_tsv_inside(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    source_file = folder / "td_synnex_daily.zip"
    tsv_text = (
        "Product ID\tSKU\tBrand\tDescription\tCost Price\tSelling Price\tCurrency\tTimestamp\tStock Level\t"
        "Stock Date\tCategory Code\tAvailability\tCategory Description\tEnd User\tEAN\tSpecial\tDepartment\t"
        "Subcategory\tRestricted\tWeight (kg)\n"
        "P1\tTD-ZIP-001\tTD Brand\tZip ready item\t22.10\t25.00\tGBP\t2026-05-19\t7\t2026-05-19\t"
        "C1\tY\tToys\tN\t5012345678903\tN\tD\tS\tN\t1\n"
        "P2\tTD-ZIP-002\tTD Brand\tZip missing cost item\t\t25.00\tGBP\t2026-05-19\t3\t2026-05-19\t"
        "C1\tY\tToys\tN\t5012345678904\tN\tD\tS\tN\t1\n"
    )
    with zipfile.ZipFile(source_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("td_synnex_daily.tsv", tsv_text)
    _write_td_synnex_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-19T08:40:00Z", check_remote=False)

    summary = import_ready_sources(root=tmp_path, imported_at_utc="2026-05-19T08:41:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    by_sku = rows.set_index("supplier_sku")

    assert summary["imported_batches"] == 1
    assert summary["failed_sources"] == 0
    assert batches.iloc[0]["source_row_count"] == "2"
    assert batches.iloc[0]["valid_row_count"] == "1"
    assert batches.iloc[0]["held_row_count"] == "1"
    assert batches.iloc[0]["source_file_path"].endswith(".zip")
    assert by_sku.loc["TD-ZIP-001", "scan_eligibility"] == "scan_now"
    assert by_sku.loc["TD-ZIP-001", "unit_cost"] == "22.10"
    assert by_sku.loc["TD-ZIP-001", "barcode"] == "5012345678903"
    assert by_sku.loc["TD-ZIP-002", "scan_eligibility"] == "hold"
    assert by_sku.loc["TD-ZIP-002", "eligibility_reason"] == "missing_cost"
    assert not source_file.exists()
    assert len(list((folder.parent / "Processed").glob("*.zip"))) == 1
    assert len(list((test_dir / "extracted_sources").glob("**/*.tsv"))) == 1


def test_fpm011_restores_new_batch_header_if_timeout_refresh_drops_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    source_file = folder / "td_synnex_daily.zip"
    tsv_text = (
        "Product ID\tSKU\tBrand\tDescription\tCost Price\tSelling Price\tCurrency\tTimestamp\tStock Level\t"
        "Stock Date\tCategory Code\tAvailability\tCategory Description\tEnd User\tEAN\tSpecial\tDepartment\t"
        "Subcategory\tRestricted\tWeight (kg)\n"
        "P1\tTD-RESTORE-001\tTD Brand\tRestore ready item\t12.00\t15.00\tGBP\t2026-05-19\t5\t2026-05-19\t"
        "C1\tY\tToys\tN\t5012345678906\tN\tD\tS\tN\t1\n"
    )
    with zipfile.ZipFile(source_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("td_synnex_daily.tsv", tsv_text)
    _write_td_synnex_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-19T09:50:00Z", check_remote=False)

    real_refresh = import_module.refresh_timeout_queue_files
    call_count = {"value": 0}

    def dropping_refresh(*args, **kwargs):
        result = real_refresh(*args, **kwargs)
        call_count["value"] += 1
        if call_count["value"] == 1:
            batches_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "price_list_batches.csv"
            pd.DataFrame(columns=PRICE_LIST_BATCH_COLUMNS).to_csv(batches_path, index=False)
        return result

    monkeypatch.setattr(import_module, "refresh_timeout_queue_files", dropping_refresh)

    summary = import_ready_sources(root=tmp_path, supplier_id="td_synnex", imported_at_utc="2026-05-19T09:51:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")

    assert summary["imported_batches"] == 1
    assert call_count["value"] == 2
    assert len(batches.index) == 1
    assert batches.iloc[0]["supplier_id"] == "td_synnex"
    assert rows.iloc[0]["supplier_sku"] == "TD-RESTORE-001"


def test_fpm011_requires_acquisition_status(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="source_acquisition_status.csv is required"):
        import_ready_sources(root=tmp_path)
