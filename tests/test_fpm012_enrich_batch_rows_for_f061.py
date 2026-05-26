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

from scripts.flows.F.price_list_manager.FPM012_enrich_batch_rows_for_f061 import enrich_batch_rows_for_f061
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)
from scripts.flows.F.suppliers.bliss_distribution import convert_supplier


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_fpm012_enriches_existing_rows_with_title_and_vat_from_source(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    source_path = tmp_path / "bliss_source.xlsx"
    pd.DataFrame(
        [
            {
                "Inventory ID": "SKU-1",
                "Inventory Barcode #": "9781568825328",
                "Description": "Example Product",
                "Price": "28.57",
                "RRP": "39.99",
            }
        ]
    ).to_excel(source_path, sheet_name="Data", index=False)
    valid_df, _ = convert_supplier(
        source_path,
        supplier_id="bliss_distribution",
        supplier_name="Bliss Distribution",
        source_url="",
        source_seen_at_utc="2026-04-30T10:00:00Z",
    )
    row_hash = str(valid_df.iloc[0]["row_hash"])

    _write_csv(
        test_dir / "supplier_registry.csv",
        [
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "bliss_distribution",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "test",
            }
        ],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": str(source_path),
                "source_file_hash": "hash",
                "converted_file_path": "converted.csv",
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
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "row_key": row_hash,
                "supplier_sku": "SKU-1",
                "supplier_title": "",
                "barcode": "9781568825328",
                "unit_cost": "28.57",
                "currency": "GBP",
                "vat_rate": "",
                "source_row_hash": row_hash,
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "supplier_converter_valid_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        BATCH_ROW_COLUMNS,
    )

    summary = enrich_batch_rows_for_f061(root=tmp_path, observed_utc="2026-04-30T13:30:00Z")

    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")
    row = rows.iloc[0]
    assert summary["status"] == "success"
    assert summary["before_missing_title"] == 1
    assert summary["after_missing_title"] == 0
    assert summary["timeout_scan_rows"] == 1
    assert summary["timeout_skip_rows"] == 0
    assert row["supplier_title"] == "Example Product"
    assert row["vat_rate"] == "20"
    assert list(rows.columns) == BATCH_ROW_COLUMNS
    assert list(eligibility.columns) == BATCH_SCAN_ELIGIBILITY_COLUMNS
    assert list(health.columns) == MANAGER_HEALTH_COLUMNS
    assert int(summary["health_fail_rows"]) == 0


def test_fpm012_does_not_require_titles_for_timeout_skipped_rows(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "bliss_distribution",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "test",
            }
        ],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": str(tmp_path / "missing_source.csv"),
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
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "row_key": "timed_out_row",
                "supplier_sku": "BLISS-001",
                "supplier_title": "",
                "barcode": "5012345678901",
                "unit_cost": "1.25",
                "currency": "GBP",
                "vat_rate": "",
                "source_row_hash": "timed_out_hash",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "imported_ready_source_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "row_key": "scan_row",
                "supplier_sku": "BLISS-002",
                "supplier_title": "Ready Product",
                "barcode": "5012345678902",
                "unit_cost": "2.50",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "scan_hash",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "imported_ready_source_row",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
        ],
        BATCH_ROW_COLUMNS,
    )
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

    summary = enrich_batch_rows_for_f061(root=tmp_path, observed_utc="2026-04-30T13:30:00Z")

    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    by_key = eligibility.set_index("row_key")

    assert summary["status"] == "success"
    assert summary["required_f061_rows"] == 1
    assert summary["before_missing_title"] == 0
    assert summary["timeout_scan_rows"] == 1
    assert summary["timeout_skip_rows"] == 1
    assert by_key.loc["timed_out_row", "scan_decision"] == "skip"
    assert by_key.loc["timed_out_row", "decision_reason"] == "timeout_active"
    assert rows.set_index("row_key").loc["timed_out_row", "supplier_title"] == ""
    assert batches.iloc[0]["eligible_row_count"] == "1"
    assert batches.iloc[0]["skipped_cooldown_row_count"] == "1"
