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

from scripts.flows.F.price_list_manager.FPM125_import_f061_recovery_progress import (
    import_f061_recovery_progress,
)
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_RECOVERY_PROGRESS_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _batch_row(
    *,
    row_key: str,
    sku: str,
    barcode: str,
    scan_eligibility: str = "scan_now",
    reason: str = "supplier_converter_valid_row",
) -> dict[str, str]:
    return {
        "batch_id": "entertainment_batch",
        "supplier_id": "entertainment_trading",
        "row_key": row_key,
        "supplier_sku": sku,
        "supplier_title": f"Product {sku}",
        "barcode": barcode,
        "unit_cost": "1.00",
        "currency": "GBP",
        "vat_rate": "20",
        "source_row_hash": row_key,
        "row_change_status": "new",
        "scan_eligibility": scan_eligibility,
        "eligibility_reason": reason,
        "last_memory_key": "",
        "cooldown_until_utc": "",
    }


def _legacy_pending_row(sku: str, barcode: str) -> dict[str, str]:
    return {
        "run_id": "stocklist_supplier_webscrape_reset_20260429T164504Z",
        "supplier_id": "stocklist_supplier",
        "supplier_name": "Stocklist Supplier",
        "row_key": f"old_{sku}_{barcode}",
        "supplier_sku": sku,
        "barcode": barcode,
        "supplier_title": f"Product {sku}",
        "unit_cost": "0.95",
        "currency": "GBP",
        "vat_rate": "20",
        "scan_status": "pending",
        "scan_reason": "",
        "attempt_count": "0",
        "last_attempt_utc": "",
        "finished_utc": "",
        "source_seen_at_utc": "2026-04-10T15:26:58Z",
    }


def test_fpm125_marks_only_legacy_pending_rows_as_scan_now(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    legacy_dir = tmp_path / "legacy"
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            {
                "batch_id": "entertainment_batch",
                "supplier_id": "entertainment_trading",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T14:13:50Z",
                "source_file_path": "Stocklist.xlsx",
                "source_file_hash": "hash",
                "converted_file_path": "converted.csv",
                "source_row_count": "5",
                "valid_row_count": "4",
                "held_row_count": "1",
                "new_row_count": "4",
                "changed_row_count": "0",
                "eligible_row_count": "4",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T14:14:00Z",
            }
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _batch_row(row_key="r1", sku="SKU1", barcode="1111111111111"),
            _batch_row(row_key="r2", sku="SKU2", barcode="2222222222222"),
            _batch_row(row_key="r3", sku="SKU3", barcode="3333333333333"),
            _batch_row(row_key="r4", sku="SKU4", barcode="4444444444444"),
            _batch_row(
                row_key="r5",
                sku="SKU5",
                barcode="",
                scan_eligibility="hold",
                reason="missing_barcode",
            ),
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        legacy_dir / "active_run.csv",
        [
            _legacy_pending_row("SKU2", "2222222222222"),
            _legacy_pending_row("SKU4", "4444444444444"),
        ],
        [
            "run_id",
            "supplier_id",
            "supplier_name",
            "row_key",
            "supplier_sku",
            "barcode",
            "supplier_title",
            "unit_cost",
            "currency",
            "vat_rate",
            "scan_status",
            "scan_reason",
            "attempt_count",
            "last_attempt_utc",
            "finished_utc",
            "source_seen_at_utc",
        ],
    )
    _write_csv(
        legacy_dir / "run_state.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "run_id": "stocklist_supplier_webscrape_reset_20260429T164504Z",
                "run_status": "running",
                "source_url": "local://Stocklist.xlsx",
                "source_file_path": "raw_current.csv",
                "source_seen_at_utc": "2026-04-10T15:26:58Z",
                "normalized_utc": "2026-04-29T16:45:04Z",
                "total_rows": "4",
                "pending_rows": "2",
                "done_rows": "2",
                "failed_rows": "1",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-30T10:34:25Z",
                "completed_at_utc": "",
            }
        ],
        [
            "supplier_id",
            "supplier_name",
            "run_id",
            "run_status",
            "source_url",
            "source_file_path",
            "source_seen_at_utc",
            "normalized_utc",
            "total_rows",
            "pending_rows",
            "done_rows",
            "failed_rows",
            "held_rows",
            "next_row_index",
            "updated_at_utc",
            "completed_at_utc",
        ],
    )

    summary = import_f061_recovery_progress(
        root=tmp_path,
        legacy_active_run_path=legacy_dir / "active_run.csv",
        legacy_run_state_path=legacy_dir / "run_state.csv",
        imported_at_utc="2026-04-30T15:00:00Z",
    )

    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    progress = pd.read_csv(test_dir / "f061_recovery_progress.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")

    by_sku = rows.set_index("supplier_sku")
    assert summary["status"] == "success"
    assert summary["manager_scan_now_rows"] == 2
    assert summary["manager_recovery_skipped_rows"] == 2
    assert summary["manager_held_rows"] == 1
    assert by_sku.loc["SKU2", "scan_eligibility"] == "scan_now"
    assert by_sku.loc["SKU4", "scan_eligibility"] == "scan_now"
    assert by_sku.loc["SKU1", "scan_eligibility"] == "skip_cooldown"
    assert by_sku.loc["SKU3", "eligibility_reason"] == "f061_recovery_not_pending"
    assert by_sku.loc["SKU5", "scan_eligibility"] == "hold"
    assert batches.iloc[0]["batch_status"] == "recovery_resume_ready"
    assert batches.iloc[0]["eligible_row_count"] == "2"
    assert list(progress.columns) == F061_RECOVERY_PROGRESS_COLUMNS
    assert progress.iloc[-1]["legacy_pending_rows"] == "2"
    assert progress.iloc[-1]["pending_matched_rows"] == "2"
    assert progress.iloc[-1]["pending_held_rows"] == "0"
    assert list(health.columns) == MANAGER_HEALTH_COLUMNS
    assert health.iloc[-1]["check"] == "f061_recovery_progress_import_reconciliation"
    assert health.iloc[-1]["status"] == "ok"


def test_fpm125_reconciles_duplicate_pending_keys_by_count(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    legacy_dir = tmp_path / "legacy"
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            {
                "batch_id": "entertainment_batch",
                "supplier_id": "entertainment_trading",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T14:13:50Z",
                "source_file_path": "Stocklist.xlsx",
                "source_file_hash": "hash",
                "converted_file_path": "converted.csv",
                "source_row_count": "3",
                "valid_row_count": "3",
                "held_row_count": "0",
                "new_row_count": "3",
                "changed_row_count": "0",
                "eligible_row_count": "3",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T14:14:00Z",
            }
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _batch_row(row_key="r1", sku="DUP", barcode="1111111111111"),
            _batch_row(row_key="r2", sku="DUP", barcode="1111111111111"),
            _batch_row(row_key="r3", sku="OTHER", barcode="2222222222222"),
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        legacy_dir / "active_run.csv",
        [_legacy_pending_row("DUP", "1111111111111")],
        [
            "run_id",
            "supplier_id",
            "supplier_name",
            "row_key",
            "supplier_sku",
            "barcode",
            "supplier_title",
            "unit_cost",
            "currency",
            "vat_rate",
            "scan_status",
            "scan_reason",
            "attempt_count",
            "last_attempt_utc",
            "finished_utc",
            "source_seen_at_utc",
        ],
    )
    _write_csv(
        legacy_dir / "run_state.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "run_id": "legacy",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "",
                "normalized_utc": "",
                "total_rows": "3",
                "pending_rows": "1",
                "done_rows": "2",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "",
                "completed_at_utc": "",
            }
        ],
        [
            "supplier_id",
            "supplier_name",
            "run_id",
            "run_status",
            "source_url",
            "source_file_path",
            "source_seen_at_utc",
            "normalized_utc",
            "total_rows",
            "pending_rows",
            "done_rows",
            "failed_rows",
            "held_rows",
            "next_row_index",
            "updated_at_utc",
            "completed_at_utc",
        ],
    )

    summary = import_f061_recovery_progress(
        root=tmp_path,
        legacy_active_run_path=legacy_dir / "active_run.csv",
        legacy_run_state_path=legacy_dir / "run_state.csv",
    )

    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    dup_rows = rows[rows["supplier_sku"] == "DUP"]
    assert summary["manager_scan_now_rows"] == 1
    assert list(dup_rows["scan_eligibility"]).count("scan_now") == 1
    assert list(dup_rows["scan_eligibility"]).count("skip_cooldown") == 1
    assert rows["row_key"].is_unique


def test_fpm125_counts_legacy_pending_rows_held_by_new_converter(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    legacy_dir = tmp_path / "legacy"
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            {
                "batch_id": "entertainment_batch",
                "supplier_id": "entertainment_trading",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T14:13:50Z",
                "source_file_path": "Stocklist.xlsx",
                "source_file_hash": "hash",
                "converted_file_path": "converted.csv",
                "source_row_count": "1",
                "valid_row_count": "0",
                "held_row_count": "1",
                "new_row_count": "0",
                "changed_row_count": "0",
                "eligible_row_count": "0",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T14:14:00Z",
            }
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _batch_row(
                row_key="held1",
                sku="BAD",
                barcode="123",
                scan_eligibility="hold",
                reason="invalid_barcode_format",
            )
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        legacy_dir / "active_run.csv",
        [_legacy_pending_row("BAD", "123")],
        [
            "run_id",
            "supplier_id",
            "supplier_name",
            "row_key",
            "supplier_sku",
            "barcode",
            "supplier_title",
            "unit_cost",
            "currency",
            "vat_rate",
            "scan_status",
            "scan_reason",
            "attempt_count",
            "last_attempt_utc",
            "finished_utc",
            "source_seen_at_utc",
        ],
    )
    _write_csv(
        legacy_dir / "run_state.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "run_id": "legacy",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "",
                "normalized_utc": "",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "",
                "completed_at_utc": "",
            }
        ],
        [
            "supplier_id",
            "supplier_name",
            "run_id",
            "run_status",
            "source_url",
            "source_file_path",
            "source_seen_at_utc",
            "normalized_utc",
            "total_rows",
            "pending_rows",
            "done_rows",
            "failed_rows",
            "held_rows",
            "next_row_index",
            "updated_at_utc",
            "completed_at_utc",
        ],
    )

    summary = import_f061_recovery_progress(
        root=tmp_path,
        legacy_active_run_path=legacy_dir / "active_run.csv",
        legacy_run_state_path=legacy_dir / "run_state.csv",
    )

    progress = pd.read_csv(test_dir / "f061_recovery_progress.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")
    assert summary["status"] == "success"
    assert summary["manager_scan_now_rows"] == 0
    assert summary["pending_held_rows"] == 1
    assert summary["pending_unmatched_rows"] == 0
    assert progress.iloc[-1]["pending_held_rows"] == "1"
    assert health.iloc[-1]["status"] == "ok"
