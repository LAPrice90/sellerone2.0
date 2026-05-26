from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F.price_list_manager.FPM070_stage_f061_handoff import stage_f061_handoff
from scripts.flows.F.price_list_manager.FPM090_set_f061_handoff_approval import set_f061_handoff_approval
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
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


def _seed_manager_selection(tmp_path: Path, *, missing_title: bool = False) -> Path:
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
                "source_file_path": "bliss.xlsx",
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
    rows = []
    eligibility = []
    for index in range(1, 3):
        row_key = f"row_{index}"
        rows.append(
            {
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
                "row_key": row_key,
                "supplier_sku": f"SKU-{index}",
                "supplier_title": "" if missing_title and index == 1 else f"Product {index}",
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
                "batch_id": "bliss_batch",
                "supplier_id": "bliss_distribution",
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
                "supplier_id": "bliss_distribution",
                "batch_id": "bliss_batch",
                "reason_code": "highest_eligible_scan_rows_after_cooldown",
                "estimated_scan_rows": "2",
                "estimated_skip_rows": "0",
                "f061_owner_status": "not_checked_test_mode",
                "safe_to_handoff_flag": "0",
                "notes": "handoff_disabled",
            }
        ],
        MANAGER_DECISION_COLUMNS,
    )
    return test_dir


def _seed_td_synnex_shifted_selection(tmp_path: Path) -> Path:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [
            {
                "supplier_id": "td_synnex",
                "supplier_name": "TD Synnex",
                "source_type": "api",
                "source_subtype": "price_list",
                "source_url": "",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "td_synnex",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "1",
                "manual_request_required_flag": "0",
                "priority_band": "daily_api",
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
                "batch_id": "td_batch",
                "supplier_id": "td_synnex",
                "source_type": "api",
                "source_subtype": "price_list",
                "source_received_at_utc": "2026-05-19T09:50:00Z",
                "source_file_path": "td_synnex.csv",
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
                "updated_at_utc": "2026-05-19T09:51:00Z",
            }
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            {
                "batch_id": "td_batch",
                "supplier_id": "td_synnex",
                "row_key": "td_row_1",
                "supplier_sku": "ADDON NETWORKING",
                "supplier_title": "104.75",
                "barcode": "731304002727",
                "unit_cost": "177.55",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "td_row_1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_scan_eligibility.csv",
        [
            {
                "batch_id": "td_batch",
                "supplier_id": "td_synnex",
                "row_key": "td_row_1",
                "supplier_sku": "ADDON NETWORKING",
                "barcode": "731304002727",
                "unit_cost": "177.55",
                "base_eligibility": "scan_now",
                "scan_decision": "scan",
                "decision_reason": "new_or_no_active_memory",
                "memory_key": "",
                "cooldown_until_utc": "",
                "observed_utc": "2026-05-19T09:52:00Z",
            }
        ],
        BATCH_SCAN_ELIGIBILITY_COLUMNS,
    )
    _write_csv(
        test_dir / "manager_decisions.csv",
        [
            {
                "decision_id": "next",
                "decided_at_utc": "2026-05-19T09:52:00Z",
                "recommended_action": "recommend_test_scan",
                "supplier_id": "td_synnex",
                "batch_id": "td_batch",
                "reason_code": "highest_eligible_scan_rows_after_cooldown",
                "estimated_scan_rows": "1",
                "estimated_skip_rows": "0",
                "f061_owner_status": "not_checked_test_mode",
                "safe_to_handoff_flag": "0",
                "notes": "shifted row should be blocked",
            }
        ],
        MANAGER_DECISION_COLUMNS,
    )
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


def test_fpm070_stages_selected_batch_but_marks_live_apply_blocked_when_f061_busy(tmp_path: Path) -> None:
    test_dir = _seed_manager_selection(tmp_path)
    _seed_busy_f061(tmp_path)

    summary = stage_f061_handoff(root=tmp_path, built_at_utc="2026-04-30T13:40:00Z")

    staged = pd.read_csv(test_dir / "f061_handoff_staged_active_run.csv", dtype=str).fillna("")
    run_state = pd.read_csv(test_dir / "f061_handoff_staged_run_state.csv", dtype=str).fillna("")
    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    assert summary["status"] == "staged"
    assert summary["staged_rows"] == 2
    assert summary["live_apply_allowed"] == "0"
    assert summary["technical_ready_flag"] == "0"
    assert summary["approval_state"] == "required"
    assert summary["f061_idle_status"] == "busy"
    assert "f061_not_idle" in summary["block_reason"]
    assert list(staged.columns) == F061_STAGED_ACTIVE_RUN_COLUMNS
    assert list(run_state.columns) == F061_STAGED_RUN_STATE_COLUMNS
    assert list(preview.columns) == F061_HANDOFF_PREVIEW_COLUMNS
    assert preview.iloc[0]["technical_ready_flag"] == "0"
    assert preview.iloc[0]["approval_state"] == "required"
    assert set(staged["scan_status"].tolist()) == {"pending"}
    assert staged.iloc[0]["supplier_title"] == "Product 1"
    assert run_state.iloc[0]["pending_rows"] == "2"


def test_fpm070_stages_latest_appended_decision_not_future_stale_timestamp(tmp_path: Path) -> None:
    test_dir = _seed_manager_selection(tmp_path)
    current_decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    stale_future_decision = {
        "decision_id": "stale_future_stax",
        "decided_at_utc": "2026-04-30T18:00:00Z",
        "recommended_action": "recommend_test_scan",
        "supplier_id": "stax",
        "batch_id": "stax_batch",
        "reason_code": "stale_future_test_seed",
        "estimated_scan_rows": "99",
        "estimated_skip_rows": "0",
        "f061_owner_status": "not_checked_test_mode",
        "safe_to_handoff_flag": "0",
        "notes": "stale decision should not override last appended manager decision",
    }
    _write_csv(
        test_dir / "manager_decisions.csv",
        [stale_future_decision, *current_decisions.to_dict("records")],
        MANAGER_DECISION_COLUMNS,
    )

    summary = stage_f061_handoff(root=tmp_path, built_at_utc="2026-04-30T13:40:00Z")

    staged = pd.read_csv(test_dir / "f061_handoff_staged_active_run.csv", dtype=str).fillna("")
    assert summary["supplier_id"] == "bliss_distribution"
    assert summary["batch_id"] == "bliss_batch"
    assert summary["staged_rows"] == 2
    assert set(staged["supplier_id"].tolist()) == {"bliss_distribution"}


def test_fpm070_blocks_staging_when_f061_required_fields_are_missing(tmp_path: Path) -> None:
    test_dir = _seed_manager_selection(tmp_path, missing_title=True)

    summary = stage_f061_handoff(root=tmp_path, built_at_utc="2026-04-30T13:40:00Z")

    staged = pd.read_csv(test_dir / "f061_handoff_staged_active_run.csv", dtype=str).fillna("")
    assert summary["status"] == "blocked"
    assert summary["staged_rows"] == 0
    assert "missing_f061_required_fields" in summary["block_reason"]
    assert staged.empty


def test_fpm070_blocks_td_synnex_shifted_price_column_before_staging(tmp_path: Path) -> None:
    test_dir = _seed_td_synnex_shifted_selection(tmp_path)

    summary = stage_f061_handoff(root=tmp_path, built_at_utc="2026-05-19T10:00:00Z")

    staged = pd.read_csv(test_dir / "f061_handoff_staged_active_run.csv", dtype=str).fillna("")
    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    assert summary["status"] == "blocked"
    assert summary["supplier_id"] == "td_synnex"
    assert summary["staged_rows"] == 0
    assert summary["technical_ready_flag"] == "0"
    assert "source_shape_guard:td_synnex_supplier_title_numeric_like" in summary["block_reason"]
    assert staged.empty
    assert preview.iloc[0]["staged_rows"] == "0"


def test_fpm070_allows_td_synnex_numeric_code_title_when_sku_matches(tmp_path: Path) -> None:
    test_dir = _seed_td_synnex_shifted_selection(tmp_path)
    batch_rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    batch_rows.loc[0, "supplier_sku"] = "10101577"
    batch_rows.loc[0, "supplier_title"] = "10101577"
    batch_rows.loc[0, "barcode"] = "8700101015775"
    batch_rows.loc[0, "unit_cost"] = "1955.79"
    batch_rows.to_csv(test_dir / "batch_rows.csv", index=False)
    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    eligibility.loc[0, "supplier_sku"] = "10101577"
    eligibility.loc[0, "barcode"] = "8700101015775"
    eligibility.loc[0, "unit_cost"] = "1955.79"
    eligibility.to_csv(test_dir / "batch_scan_eligibility.csv", index=False)

    summary = stage_f061_handoff(root=tmp_path, built_at_utc="2026-05-19T10:00:00Z")

    staged = pd.read_csv(test_dir / "f061_handoff_staged_active_run.csv", dtype=str).fillna("")
    assert summary["staged_rows"] == 1
    assert summary["technical_ready_flag"] == "1"
    assert "td_synnex_supplier_title_numeric_like" not in summary["block_reason"]
    assert staged.iloc[0]["supplier_sku"] == "10101577"
    assert staged.iloc[0]["supplier_title"] == "10101577"


def test_fpm070_idle_staged_batch_requires_explicit_matching_approval(tmp_path: Path) -> None:
    test_dir = _seed_manager_selection(tmp_path)

    summary = stage_f061_handoff(root=tmp_path, built_at_utc="2026-04-30T13:40:00Z")

    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    assert summary["status"] == "staged"
    assert summary["technical_ready_flag"] == "1"
    assert summary["approval_state"] == "required"
    assert summary["live_apply_allowed"] == "0"
    assert "handoff_approval_required" in summary["block_reason"]
    assert preview.iloc[0]["technical_ready_flag"] == "1"
    assert preview.iloc[0]["approval_state"] == "required"


def test_fpm070_matching_approval_allows_guard_readiness_without_live_write(tmp_path: Path) -> None:
    test_dir = _seed_manager_selection(tmp_path)
    approval = set_f061_handoff_approval(
        supplier_id="bliss_distribution",
        batch_id="bliss_batch",
        approval_state="approved",
        approved_by="operator",
        reason="test approval",
        root=tmp_path,
        approved_at_utc="2026-04-30T13:30:00Z",
    )

    summary = stage_f061_handoff(root=tmp_path, built_at_utc="2026-04-30T13:40:00Z")

    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    live_active_path = tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    assert summary["status"] == "staged"
    assert summary["technical_ready_flag"] == "1"
    assert summary["approval_state"] == "approved"
    assert summary["approval_id"] == approval["approval_id"]
    assert summary["live_apply_allowed"] == "1"
    assert summary["block_reason"] == ""
    assert preview.iloc[0]["approval_id"] == approval["approval_id"]
    assert not live_active_path.exists()


def test_fpm070_apply_live_refuses_and_leaves_live_active_run_unchanged(tmp_path: Path) -> None:
    _seed_manager_selection(tmp_path)
    _seed_busy_f061(tmp_path)

    with pytest.raises(RuntimeError):
        stage_f061_handoff(
            root=tmp_path,
            built_at_utc="2026-04-30T13:40:00Z",
            apply_live=True,
            confirm_live_handoff=True,
        )

    live_active = pd.read_csv(
        tmp_path / get_f_output_contract("supplier_price_list_active_run").rel_path,
        dtype=str,
    ).fillna("")
    assert len(live_active.index) == 1
    assert live_active.iloc[0]["supplier_id"] == "stocklist_supplier"
    assert live_active.iloc[0]["run_id"] == "busy_run"
