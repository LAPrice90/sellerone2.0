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
from scripts.flows.F.price_list_manager.FPM070_stage_f061_handoff import stage_f061_handoff
from scripts.flows.F.price_list_manager.FPM090_set_f061_handoff_approval import set_f061_handoff_approval
from scripts.flows.F.price_list_manager.FPM100_apply_f061_handoff import apply_f061_handoff
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    F061_HANDOFF_APPLY_PREVIEW_COLUMNS,
    F061_HANDOFF_BACKUP_MANIFEST_COLUMNS,
    F061_HANDOFF_PREVIEW_COLUMNS,
    F061_STAGED_ACTIVE_RUN_COLUMNS,
    F061_STAGED_RUN_STATE_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_f_contract(root: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_f_output_contract(contract_name)
    columns = [*contract.required_columns, *contract.optional_columns]
    _write_csv(root / contract.rel_path, rows, columns)


def _seed_manager_selection(tmp_path: Path) -> Path:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api",
                "source_subtype": "csv_link",
                "source_url": "https://example.test/stax.csv",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "stax",
                "normal_refresh_days": "7",
                "minimum_rescan_days": "3",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "api",
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
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "source_type": "api",
                "source_subtype": "csv_link",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "stax.csv",
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
                "updated_at_utc": "2026-04-30T10:01:00Z",
            }
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    rows = []
    eligibility = []
    for index in range(1, 4):
        row_key = f"row_{index}"
        rows.append(
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "row_key": row_key,
                "supplier_sku": f"SKU-{index}",
                "supplier_title": f"Product {index}",
                "barcode": f"500000000000{index}",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": row_key,
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        )
        eligibility.append(
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "row_key": row_key,
                "supplier_sku": f"SKU-{index}",
                "barcode": f"500000000000{index}",
                "unit_cost": "1.00",
                "base_eligibility": "scan_now",
                "scan_decision": "scan",
                "decision_reason": "new_or_no_active_memory",
                "memory_key": "",
                "cooldown_until_utc": "",
                "observed_utc": "2026-04-30T12:00:00Z",
            }
        )
    _write_csv(test_dir / "batch_rows.csv", rows, BATCH_ROW_COLUMNS)
    _write_csv(test_dir / "batch_scan_eligibility.csv", eligibility, BATCH_SCAN_ELIGIBILITY_COLUMNS)
    _write_csv(
        test_dir / "manager_decisions.csv",
        [
            {
                "decision_id": "next",
                "decided_at_utc": "2026-04-30T12:00:00Z",
                "recommended_action": "recommend_test_scan",
                "supplier_id": "stax",
                "batch_id": "stax_batch",
                "reason_code": "highest_eligible_scan_rows_after_cooldown",
                "estimated_scan_rows": "3",
                "estimated_skip_rows": "0",
                "f061_owner_status": "not_checked_test_mode",
                "safe_to_handoff_flag": "0",
                "notes": "handoff_disabled",
            }
        ],
        MANAGER_DECISION_COLUMNS,
    )
    return test_dir


def _seed_approved_staged_handoff(tmp_path: Path) -> Path:
    test_dir = _seed_manager_selection(tmp_path)
    set_f061_handoff_approval(
        supplier_id="stax",
        batch_id="stax_batch",
        approval_state="approved",
        approved_by="operator",
        reason="test approval",
        root=tmp_path,
        approved_at_utc="2026-04-30T13:30:00Z",
    )
    stage_f061_handoff(root=tmp_path, built_at_utc="2026-04-30T13:40:00Z")
    return test_dir


def _seed_busy_f061(root: Path) -> None:
    _write_f_contract(
        root,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "busy_run",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "row_key": "busy_1",
                "supplier_sku": "BUSY-1",
                "barcode": "9999999999999",
                "supplier_title": "Busy Product",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-30T09:00:00Z",
            }
        ],
    )
    _write_f_contract(
        root,
        "supplier_price_list_run_state",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "run_id": "busy_run",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "",
                "source_seen_at_utc": "2026-04-30T09:00:00Z",
                "normalized_utc": "2026-04-30T09:00:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-30T09:00:00Z",
                "completed_at_utc": "",
            }
        ],
    )


def test_fpm100_preview_only_reports_ready_without_live_write(tmp_path: Path) -> None:
    test_dir = _seed_approved_staged_handoff(tmp_path)

    summary = apply_f061_handoff(root=tmp_path, built_at_utc="2026-04-30T14:00:00Z")

    preview = pd.read_csv(test_dir / "f061_handoff_apply_preview.csv", dtype=str).fillna("")
    live_active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    assert summary["status"] == "ready"
    assert summary["apply_ready_flag"] == "1"
    assert summary["live_write_attempted"] == "0"
    assert summary["live_write_succeeded"] == "0"
    assert summary["block_reason"] == ""
    assert list(preview.columns) == F061_HANDOFF_APPLY_PREVIEW_COLUMNS
    assert not live_active_path.exists()


def test_fpm100_apply_live_requires_confirm_flag(tmp_path: Path) -> None:
    test_dir = _seed_approved_staged_handoff(tmp_path)

    summary = apply_f061_handoff(
        root=tmp_path,
        built_at_utc="2026-04-30T14:00:00Z",
        apply_live=True,
    )

    preview = pd.read_csv(test_dir / "f061_handoff_apply_preview.csv", dtype=str).fillna("")
    live_active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    assert summary["status"] == "blocked"
    assert summary["apply_ready_flag"] == "0"
    assert summary["live_write_attempted"] == "0"
    assert summary["live_write_succeeded"] == "0"
    assert "confirm_approved_handoff_required" in summary["block_reason"]
    assert preview.iloc[0]["live_write_succeeded"] == "0"
    assert not live_active_path.exists()


def test_fpm100_apply_live_writes_staged_batch_and_backs_up_existing_files(tmp_path: Path) -> None:
    test_dir = _seed_approved_staged_handoff(tmp_path)

    summary = apply_f061_handoff(
        root=tmp_path,
        built_at_utc="2026-04-30T14:00:00Z",
        apply_live=True,
        confirm_approved_handoff=True,
    )

    live_active = pd.read_csv(
        tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path,
        dtype=str,
    ).fillna("")
    live_state = pd.read_csv(
        tmp_path / get_f_output_contract("supplier_price_list_run_state").rel_path,
        dtype=str,
    ).fillna("")
    manifest = pd.read_csv(Path(summary["backup_manifest_path"]), dtype=str).fillna("")
    backup_log = pd.read_csv(test_dir / "f061_handoff_apply_backups.csv", dtype=str).fillna("")
    assert summary["status"] == "applied"
    assert summary["live_write_attempted"] == "1"
    assert summary["live_write_succeeded"] == "1"
    assert len(live_active.index) == 3
    assert set(live_active["supplier_id"].tolist()) == {"stax"}
    assert set(live_active["scan_status"].tolist()) == {"pending"}
    assert live_state.iloc[0]["pending_rows"] == "3"
    assert list(manifest.columns) == F061_HANDOFF_BACKUP_MANIFEST_COLUMNS
    assert len(manifest.index) == 2
    assert len(backup_log.index) == 2


def test_fpm100_blocks_td_synnex_shifted_staged_rows_before_live_write(tmp_path: Path) -> None:
    test_dir = _seed_approved_staged_handoff(tmp_path)
    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("").iloc[-1].to_dict()
    preview.update(
        {
            "supplier_id": "td_synnex",
            "supplier_name": "TD Synnex",
            "batch_id": "td_batch",
            "run_id": "fpm_td_synnex_20260519T095000Z",
            "staged_rows": "1",
            "technical_ready_flag": "1",
            "approval_state": "approved",
            "live_apply_allowed": "1",
            "block_reason": "",
        }
    )
    _write_csv(test_dir / "f061_handoff_preview.csv", [preview], F061_HANDOFF_PREVIEW_COLUMNS)
    _write_csv(
        test_dir / "f061_handoff_staged_active_run.csv",
        [
            {
                "run_id": "fpm_td_synnex_20260519T095000Z",
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "row_key": "td_row_1",
                "supplier_sku": "ADDON NETWORKING",
                "barcode": "731304002727",
                "supplier_title": "104.75",
                "unit_cost": "177.55",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-19T09:50:00Z",
            }
        ],
        F061_STAGED_ACTIVE_RUN_COLUMNS,
    )
    _write_csv(
        test_dir / "f061_handoff_staged_run_state.csv",
        [
            {
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "run_id": "fpm_td_synnex_20260519T095000Z",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "td_synnex.csv",
                "source_seen_at_utc": "2026-05-19T09:50:00Z",
                "normalized_utc": "2026-05-19T09:50:00Z",
                "total_rows": "1",
                "pending_rows": "1",
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-05-19T09:50:00Z",
                "completed_at_utc": "",
            }
        ],
        F061_STAGED_RUN_STATE_COLUMNS,
    )

    summary = apply_f061_handoff(
        root=tmp_path,
        built_at_utc="2026-05-19T10:05:00Z",
        apply_live=True,
        confirm_approved_handoff=True,
    )

    live_active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    assert summary["status"] == "blocked"
    assert summary["live_write_attempted"] == "0"
    assert summary["live_write_succeeded"] == "0"
    assert "source_shape_guard:td_synnex_supplier_title_numeric_like" in summary["block_reason"]
    assert not live_active_path.exists()


def test_fpm100_blocks_if_f061_becomes_busy_after_stage(tmp_path: Path) -> None:
    _seed_approved_staged_handoff(tmp_path)
    _seed_busy_f061(tmp_path)

    summary = apply_f061_handoff(
        root=tmp_path,
        built_at_utc="2026-04-30T14:00:00Z",
        apply_live=True,
        confirm_approved_handoff=True,
    )

    live_active = pd.read_csv(
        tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path,
        dtype=str,
    ).fillna("")
    assert summary["status"] == "blocked"
    assert summary["live_write_attempted"] == "0"
    assert summary["live_write_succeeded"] == "0"
    assert "f061_not_idle" in summary["block_reason"]
    assert len(live_active.index) == 1
    assert live_active.iloc[0]["run_id"] == "busy_run"


def test_fpm100_blocks_reapply_when_run_already_has_screening_progress(tmp_path: Path) -> None:
    test_dir = _seed_approved_staged_handoff(tmp_path)
    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("").iloc[-1]
    run_id = preview["run_id"]
    _write_f_contract(
        tmp_path,
        "f_screening_row_state_live",
        [
            {
                "observed_utc": "2026-04-30T13:50:00Z",
                "run_id": run_id,
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "SKU-1",
                "barcode": "5000000000001",
                "candidate_id": "row_1",
                "asin": "B000TEST",
                "row_status": "timeout",
                "last_stage": "webscrape",
                "fail_code": "PRICEHISTORYFAIL",
                "attempt_count": "1",
                "timeout_until_utc": "2026-05-01T13:50:00Z",
                "mode": "legacy_module",
                "updated_at_utc": "2026-04-30T13:50:00Z",
                "source_seen_at_utc": "2026-04-30T10:00:00Z",
                "pf": "FAIL",
                "status_reason": "PRICEHISTORYFAIL",
                "recommendation_status": "",
                "recommended_test_qty": "",
            }
        ],
    )

    summary = apply_f061_handoff(
        root=tmp_path,
        built_at_utc="2026-04-30T14:00:00Z",
        apply_live=True,
        confirm_approved_handoff=True,
    )

    live_active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    assert summary["status"] == "blocked"
    assert summary["live_write_attempted"] == "0"
    assert summary["live_write_succeeded"] == "0"
    assert "run_reapply_blocked" in summary["block_reason"]
    assert not live_active_path.exists()
