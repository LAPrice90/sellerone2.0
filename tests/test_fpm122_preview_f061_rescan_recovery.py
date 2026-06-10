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
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_RESCAN_RECOVERY_PREVIEW_COLUMNS,
    F061_RESCAN_RECOVERY_SUMMARY_COLUMNS,
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
    columns = [*contract.required_columns, *contract.optional_columns]
    _write_csv(root / contract.rel_path, rows, columns)


def _batch(batch_id: str, supplier_id: str, received: str, status: str = "imported_from_source") -> dict[str, str]:
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "source_type": "api",
        "source_subtype": "csv",
        "source_received_at_utc": received,
        "source_file_path": "",
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


def _batch_row(batch_id: str, row_key: str, sku: str, barcode: str, cost: str = "1.00") -> dict[str, str]:
    return {
        "batch_id": batch_id,
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


def _screening_row(
    row_key: str,
    sku: str,
    barcode: str,
    *,
    attempt_count: str = "1",
    candidate_id: str | None = None,
) -> dict[str, str]:
    return {
        "observed_utc": "2026-06-04T10:00:00Z",
        "run_id": "fpm_stax_old",
        "supplier_id": "stax",
        "supplier_name": "Stax",
        "supplier_sku": sku,
        "supplier_title": f"Old Product {sku}",
        "barcode": barcode,
        "candidate_id": candidate_id or row_key,
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


def test_fpm122_previews_rescan_recovery_without_live_writes(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            _batch("stax_old", "stax", "2026-05-01T10:00:00Z", status="superseded"),
            _batch("stax_current", "stax", "2026-06-04T10:00:00Z"),
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _batch_row("stax_old", "missing_current", "OLD-SKU", "5000000000003"),
            _batch_row("stax_current", "clean_retry", "SKU-1", "5000000000001", "1.25"),
            _batch_row("stax_current", "exhausted_retry", "SKU-2", "5000000000002", "2.25"),
            _batch_row("stax_current", "new_row_key", "SKU-NEW", "5000000000004", "4.25"),
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_f_contract(
        tmp_path,
        "f_screening_row_state_live",
        [
            _screening_row("clean_retry", "SKU-1", "5000000000001"),
            _screening_row("exhausted_retry", "SKU-2", "5000000000002", attempt_count="2"),
            _screening_row("missing_current", "OLD-SKU", "5000000000003"),
            _screening_row("old_bad_key", "BAD-SKU", "5000000000004"),
        ],
    )
    _write_f_contract(tmp_path, "supplier_price_list_active_run", [])

    summary = build_rescan_recovery_preview(
        root=tmp_path,
        observed_utc="2026-06-04T12:00:00Z",
        max_active_rescan_attempts=2,
    )

    assert summary["status"] == "success"
    assert summary["preview_rows"] == 4
    assert summary["requeue_rows"] == 2
    assert summary["retry_exhausted_rows"] == 1
    assert summary["source_blocked_rows"] == 1
    assert summary["blocked_rows"] == 0

    preview_path = test_dir / "f061_rescan_recovery_preview.csv"
    preview = pd.read_csv(preview_path, dtype=str).fillna("")
    assert list(preview.columns) == F061_RESCAN_RECOVERY_PREVIEW_COLUMNS
    by_candidate = preview.set_index("candidate_id").to_dict("index")
    assert by_candidate["clean_retry"]["proposed_action"] == "requeue_from_current_source"
    assert by_candidate["clean_retry"]["proposed_unit_cost"] == "1.25"
    assert by_candidate["exhausted_retry"]["proposed_action"] == "mark_retry_exhausted"
    assert by_candidate["missing_current"]["proposed_action"] == "mark_source_blocked"
    assert by_candidate["missing_current"]["block_reason"] == "source_not_in_current_batch"
    assert by_candidate["old_bad_key"]["source_match_method"] == "current_barcode_only"
    assert by_candidate["old_bad_key"]["proposed_supplier_sku"] == "SKU-NEW"

    summary_path = test_dir / "f061_rescan_recovery_summary.csv"
    summary_rows = pd.read_csv(summary_path, dtype=str).fillna("")
    assert list(summary_rows.columns) == F061_RESCAN_RECOVERY_SUMMARY_COLUMNS
    summary_row = summary_rows.iloc[0]
    assert summary_row["live_write_attempted"] == "0"
    assert summary_row["live_write_succeeded"] == "0"
    assert summary_row["notes"] == "preview_only_no_queue_or_output_edit"


def test_fpm122_does_not_treat_already_active_missing_cost_as_clean(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("stax_current", "stax", "2026-06-04T10:00:00Z")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [_batch_row("missing_cost", "SKU-NOCOST", "5000000000005", "")],
        BATCH_ROW_COLUMNS,
    )
    _write_f_contract(
        tmp_path,
        "f_screening_row_state_live",
        [_screening_row("missing_cost", "SKU-NOCOST", "5000000000005")],
    )
    _write_f_contract(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "fpm_stax_current",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "missing_cost",
                "supplier_sku": "SKU-NOCOST",
                "supplier_title": "Product SKU-NOCOST",
                "barcode": "5000000000005",
                "unit_cost": "",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "rescan_retry_required",
                "attempt_count": "1",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-06-04T10:00:00Z",
                "completion_block_reason": "rescan_retry_pending",
                "backtrack_original_observed_utc": "",
                "backtrack_attempt_count": "",
            }
        ],
    )

    summary = build_rescan_recovery_preview(
        root=tmp_path,
        observed_utc="2026-06-04T12:00:00Z",
        max_active_rescan_attempts=2,
    )

    assert summary["already_active_rows"] == 1
    assert summary["blocked_rows"] == 1
    preview = pd.read_csv(test_dir / "f061_rescan_recovery_preview.csv", dtype=str).fillna("")
    row = preview.iloc[0]
    assert row["proposed_action"] == "already_active"
    assert row["eligible_apply_flag"] == "0"
    assert row["block_reason"] == "already_active_source_row_missing_unit_cost"
