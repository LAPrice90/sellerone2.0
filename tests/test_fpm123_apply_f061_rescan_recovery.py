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

from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F.price_list_manager.FPM122_preview_f061_rescan_recovery import (
    build_rescan_recovery_preview,
)
from scripts.flows.F.price_list_manager.FPM123_apply_f061_rescan_recovery import (
    apply_rescan_recovery_preview,
)
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_RESCAN_RECOVERY_APPLY_ROW_COLUMNS,
    F061_RESCAN_RECOVERY_APPLY_SUMMARY_COLUMNS,
    F061_RESCAN_RECOVERY_PREVIEW_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_f_contract(root: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_f_output_contract(contract_name)
    _write_csv(root / contract.rel_path, rows, [*contract.required_columns, *contract.optional_columns])


def _batch(batch_id: str, supplier_id: str, received: str, status: str = "imported_from_source") -> dict[str, str]:
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "source_type": "api",
        "source_subtype": "csv",
        "source_received_at_utc": received,
        "source_file_path": f"/tmp/{batch_id}.csv",
        "source_file_hash": "",
        "converted_file_path": "",
        "source_row_count": "10",
        "valid_row_count": "10",
        "held_row_count": "0",
        "new_row_count": "10",
        "changed_row_count": "0",
        "eligible_row_count": "10",
        "skipped_cooldown_row_count": "0",
        "batch_status": status,
        "status_reason": "test",
        "updated_at_utc": received,
    }


def _batch_row(row_key: str, sku: str, barcode: str, cost: str = "1.00") -> dict[str, str]:
    return {
        "batch_id": "stax_current",
        "supplier_id": "stax",
        "row_key": row_key,
        "supplier_sku": sku,
        "supplier_title": f"Product {sku}",
        "barcode": barcode,
        "unit_cost": cost,
        "currency": "GBP",
        "vat_rate": "20",
        "unit_code": "",
        "pack_size": "",
        "pack_cost": "",
        "moq": "",
        "source_row_hash": f"hash_{row_key}",
        "row_change_status": "new",
        "scan_eligibility": "scan_now",
        "eligibility_reason": "valid",
        "last_memory_key": "",
        "cooldown_until_utc": "",
    }


def _screening_row(row_key: str, sku: str, barcode: str, attempt_count: str = "1") -> dict[str, str]:
    return {
        "observed_utc": "2026-06-04T10:00:00Z",
        "run_id": "fpm_stax_old",
        "supplier_id": "stax",
        "supplier_name": "Stax",
        "supplier_sku": sku,
        "supplier_title": f"Old Product {sku}",
        "barcode": barcode,
        "candidate_id": row_key,
        "asin": "",
        "row_status": "timeout",
        "last_stage": "retry",
        "fail_code": "RESCAN",
        "attempt_count": attempt_count,
        "timeout_until_utc": "2026-07-04T10:00:00Z",
        "mode": "screening",
        "updated_at_utc": "2026-06-04T10:00:00Z",
        "source_seen_at_utc": "2026-06-04T09:00:00Z",
        "pf": "RESCAN",
        "status_reason": "RESCAN",
        "recommendation_status": "",
        "recommended_test_qty": "",
    }


def test_fpm123_applies_preview_with_backup_and_no_scanner_run(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("stax_current", "stax", "2026-06-04T10:00:00Z")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _batch_row("clean_retry", "SKU-1", "5000000000001", "1.25"),
            _batch_row("exhausted_retry", "SKU-2", "5000000000002", "2.25"),
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_f_contract(
        tmp_path,
        "f_screening_row_state_live",
        [
            _screening_row("clean_retry", "SKU-1", "5000000000001", attempt_count="1"),
            _screening_row("exhausted_retry", "SKU-2", "5000000000002", attempt_count="2"),
        ],
    )
    _write_f_contract(tmp_path, "supplier_price_list_active_run", [])
    _write_f_contract(tmp_path, "supplier_price_list_run_state", [])

    preview = build_rescan_recovery_preview(
        root=tmp_path,
        observed_utc="2026-06-04T12:00:00Z",
        max_active_rescan_attempts=2,
    )
    assert preview["preview_rows"] == 2

    summary = apply_rescan_recovery_preview(
        root=tmp_path,
        observed_utc="2026-06-04T12:30:00Z",
        require_preview_total=2,
    )

    assert summary["status"] == "success"
    assert summary["active_rows_added"] == 1
    assert summary["screening_rows_updated"] == 2
    assert Path(summary["backup_dir"]).exists()
    assert (Path(summary["backup_dir"]) / "out" / "systems" / "F" / "live" / "f_screening_row_state_live.csv").exists()

    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert len(active.index) == 1
    active_row = active.iloc[0]
    assert active_row["scan_status"] == "pending"
    assert active_row["scan_reason"] == "rescan_retry_required"
    assert active_row["completion_block_reason"] == "rescan_retry_pending"
    assert active_row["attempt_count"] == "1"

    screening = pd.read_csv(tmp_path / get_f_output_contract("f_screening_row_state_live").rel_path, dtype=str).fillna("")
    by_candidate = screening.set_index("candidate_id").to_dict("index")
    assert by_candidate["clean_retry"]["row_status"] == "retry"
    assert by_candidate["clean_retry"]["timeout_until_utc"] == ""
    assert by_candidate["clean_retry"]["status_reason"] == "RESCAN|retry_pending"
    assert by_candidate["exhausted_retry"]["row_status"] == "timeout"
    assert by_candidate["exhausted_retry"]["timeout_until_utc"] == ""
    assert by_candidate["exhausted_retry"]["status_reason"] == "RESCAN|retry_exhausted"

    run_state = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path, dtype=str).fillna("")
    assert run_state.iloc[0]["supplier_id"] == "stax"
    assert run_state.iloc[0]["run_status"] == "running"
    assert run_state.iloc[0]["pending_rows"] == "1"

    apply_rows = pd.read_csv(test_dir / "f061_rescan_recovery_apply_rows.csv", dtype=str).fillna("")
    assert list(apply_rows.columns) == F061_RESCAN_RECOVERY_APPLY_ROW_COLUMNS
    apply_summary = pd.read_csv(test_dir / "f061_rescan_recovery_apply_summary.csv", dtype=str).fillna("")
    assert list(apply_summary.columns) == F061_RESCAN_RECOVERY_APPLY_SUMMARY_COLUMNS
    assert apply_summary.iloc[0]["live_write_attempted"] == "1"
    assert apply_summary.iloc[0]["live_write_succeeded"] == "1"
    assert apply_summary.iloc[0]["notes"] == "protected_rescan_recovery_applied_no_f061_run_no_worker_restart"


def test_fpm123_refuses_stale_preview_missing_unit_cost(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("stax_current", "stax", "2026-06-04T10:00:00Z")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "f061_rescan_recovery_preview.csv",
        [
            {
                "preview_id": "rescan_preview_00001",
                "built_at_utc": "2026-06-04T12:00:00Z",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "run_id": "fpm_stax_old",
                "candidate_id": "missing_cost",
                "candidate_base": "missing_cost",
                "asin": "",
                "original_supplier_sku": "SKU-NOCOST",
                "original_barcode": "5000000000005",
                "original_status_reason": "RESCAN",
                "original_attempt_count": "1",
                "original_timeout_until_utc": "2026-07-04T10:00:00Z",
                "latest_batch_id": "stax_current",
                "source_match_method": "current_row_key",
                "source_match_count": "1",
                "proposed_action": "requeue_from_current_source",
                "eligible_apply_flag": "1",
                "block_reason": "",
                "proposed_run_id": "fpm_stax_old",
                "proposed_row_key": "missing_cost",
                "proposed_supplier_sku": "SKU-NOCOST",
                "proposed_supplier_title": "Product SKU-NOCOST",
                "proposed_barcode": "5000000000005",
                "proposed_unit_cost": "",
                "proposed_currency": "GBP",
                "proposed_vat_rate": "20",
                "proposed_source_seen_at_utc": "2026-06-04T10:00:00Z",
            }
        ],
        F061_RESCAN_RECOVERY_PREVIEW_COLUMNS,
    )
    _write_f_contract(
        tmp_path,
        "f_screening_row_state_live",
        [_screening_row("missing_cost", "SKU-NOCOST", "5000000000005", attempt_count="1")],
    )
    _write_f_contract(tmp_path, "supplier_price_list_active_run", [])
    _write_f_contract(tmp_path, "supplier_price_list_run_state", [])

    summary = apply_rescan_recovery_preview(
        root=tmp_path,
        observed_utc="2026-06-04T12:30:00Z",
        require_preview_total=1,
    )

    assert summary["active_rows_added"] == 0
    assert summary["screening_rows_updated"] == 0
    active = pd.read_csv(tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path, dtype=str).fillna("")
    assert active.empty
    apply_rows = pd.read_csv(test_dir / "f061_rescan_recovery_apply_rows.csv", dtype=str).fillna("")
    assert apply_rows.iloc[0]["apply_status"] == "blocked"
    assert apply_rows.iloc[0]["block_reason"] == "active_row_missing_unit_cost"
