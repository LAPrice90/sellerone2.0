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

from scripts.flows.F.price_list_manager.FPM040_build_next_action import build_next_action
from scripts.flows.F.f_scanner_timeout_policy import default_timeout_policy_df, write_timeout_policy_df
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    PLACEHOLDER_SCANNER_RESULT_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    QUEUE_CONTROL_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _batch(batch_id: str, supplier_id: str, valid_rows: str, *, received: str) -> dict[str, str]:
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "source_type": "manual_request",
        "source_subtype": "email_request",
        "source_received_at_utc": received,
        "source_file_path": f"{batch_id}.xlsx",
        "source_file_hash": f"{batch_id}_hash",
        "converted_file_path": f"{batch_id}.csv",
        "source_row_count": valid_rows,
        "valid_row_count": valid_rows,
        "held_row_count": "0",
        "new_row_count": valid_rows,
        "changed_row_count": "0",
        "eligible_row_count": valid_rows,
        "skipped_cooldown_row_count": "0",
        "batch_status": "imported_from_source",
        "status_reason": "ready_source_file_imported",
        "updated_at_utc": received,
    }


def _row(batch_id: str, supplier_id: str, index: int, barcode: str, cost: str = "1.00") -> dict[str, str]:
    row_key = f"{batch_id}_row_{index}"
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "row_key": row_key,
        "supplier_sku": f"{supplier_id.upper()}-{index}",
        "barcode": barcode,
        "unit_cost": cost,
        "currency": "GBP",
        "source_row_hash": row_key,
        "row_change_status": "new",
        "scan_eligibility": "scan_now",
        "eligibility_reason": "test",
        "last_memory_key": "",
        "cooldown_until_utc": "",
    }


def _registry_row(supplier_id: str, priority: str) -> dict[str, str]:
    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_id.replace("_", " ").title(),
        "source_type": "manual_request",
        "source_subtype": "email_request",
        "source_url": "",
        "source_folder_path": "",
        "existing_supplier_config_path": "",
        "converter_id": supplier_id,
        "normal_refresh_days": "30",
        "minimum_rescan_days": "30",
        "large_file_flag": "0",
        "manual_request_required_flag": "1",
        "priority_band": priority,
        "active_flag": "1",
        "notes": "test",
    }


def test_fpm040_selects_highest_eligible_batch_after_cooldowns(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [_registry_row("dhb", "monthly_manual"), _registry_row("bliss_distribution", "monthly_manual")],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            _batch("dhb_batch", "dhb", "3", received="2026-04-30T10:00:00Z"),
            _batch("bliss_batch", "bliss_distribution", "5", received="2026-04-30T11:00:00Z"),
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _row("dhb_batch", "dhb", 1, "5000000000001"),
            _row("dhb_batch", "dhb", 2, "5000000000002"),
            _row("dhb_batch", "dhb", 3, "5000000000003"),
            _row("bliss_batch", "bliss_distribution", 1, "6000000000001"),
            _row("bliss_batch", "bliss_distribution", 2, "6000000000002"),
            _row("bliss_batch", "bliss_distribution", 3, "6000000000003"),
            _row("bliss_batch", "bliss_distribution", 4, "6000000000004"),
            _row("bliss_batch", "bliss_distribution", 5, "6000000000005"),
        ],
        BATCH_ROW_COLUMNS,
    )

    summary = build_next_action(root=tmp_path, observed_utc="2026-04-30T12:00:00Z")

    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    assert summary["selected_supplier_id"] == "bliss_distribution"
    assert summary["estimated_scan_rows"] == 5
    assert summary["safe_to_handoff_flag"] == "0"
    assert list(eligibility.columns) == BATCH_SCAN_ELIGIBILITY_COLUMNS
    assert list(decisions.columns) == MANAGER_DECISION_COLUMNS
    assert (eligibility["scan_decision"] == "scan").sum() == 8
    assert decisions.iloc[-1]["recommended_action"] == "recommend_test_scan"


def test_fpm040_ignores_superseded_batches(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(test_dir / "supplier_registry.csv", [_registry_row("dhb", "monthly_manual")], SUPPLIER_REGISTRY_COLUMNS)
    old_batch = _batch("dhb_old_batch", "dhb", "4", received="2026-04-30T10:00:00Z")
    old_batch["batch_status"] = "superseded"
    old_batch["status_reason"] = "replaced_by_newer_operator_file"
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            old_batch,
            _batch("dhb_may_batch", "dhb", "2", received="2026-05-05T10:00:00Z"),
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _row("dhb_old_batch", "dhb", 1, "5000000000001"),
            _row("dhb_old_batch", "dhb", 2, "5000000000002"),
            _row("dhb_old_batch", "dhb", 3, "5000000000003"),
            _row("dhb_old_batch", "dhb", 4, "5000000000004"),
            _row("dhb_may_batch", "dhb", 1, "6000000000001"),
            _row("dhb_may_batch", "dhb", 2, "6000000000002"),
        ],
        BATCH_ROW_COLUMNS,
    )

    summary = build_next_action(root=tmp_path, observed_utc="2026-05-06T12:00:00Z")

    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    latest = decisions.iloc[-1]
    old_eligibility = eligibility[eligibility["batch_id"] == "dhb_old_batch"]
    assert summary["selected_batch_id"] == "dhb_may_batch"
    assert summary["estimated_scan_rows"] == 2
    assert set(old_eligibility["scan_decision"]) == {"skip"}
    assert set(old_eligibility["decision_reason"]) == {"superseded_batch"}
    assert "skipped_batch_statuses=superseded" in latest["notes"]


def test_fpm040_skips_processed_rows_and_active_cooldowns(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(test_dir / "supplier_registry.csv", [_registry_row("dhb", "monthly_manual")], SUPPLIER_REGISTRY_COLUMNS)
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("dhb_batch", "dhb", "4", received="2026-04-30T10:00:00Z")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    rows = [
        _row("dhb_batch", "dhb", 1, "5000000000001", "1.00"),
        _row("dhb_batch", "dhb", 2, "5000000000002", "2.00"),
        _row("dhb_batch", "dhb", 3, "5000000000003", "3.00"),
        _row("dhb_batch", "dhb", 4, "5000000000004", "4.00"),
    ]
    rows[3]["scan_eligibility"] = "hold"
    rows[3]["eligibility_reason"] = "missing_barcode"
    _write_csv(test_dir / "batch_rows.csv", rows, BATCH_ROW_COLUMNS)
    _write_csv(
        test_dir / "barcode_scan_memory.csv",
        [
            {
                "memory_key": "barcode:5000000000002",
                "memory_scope": "global_barcode",
                "supplier_id": "dhb",
                "barcode": "5000000000002",
                "asin": "",
                "last_result_status": "FAIL",
                "last_fail_code": "SELLERHISTORYFAIL",
                "last_stage": "webscrape",
                "last_scanned_at_utc": "2026-04-01T00:00:00Z",
                "cooldown_until_utc": "2026-10-01T00:00:00Z",
                "cooldown_basis": "SELLERHISTORYFAIL",
                "attempt_count": "1",
                "last_batch_id": "old_batch",
                "last_row_hash": "old_hash",
                "updated_at_utc": "2026-04-01T00:00:00Z",
            }
        ],
        BARCODE_SCAN_MEMORY_COLUMNS,
    )
    _write_csv(
        test_dir / "placeholder_scanner_results.csv",
        [
            {
                "result_id": "done1",
                "batch_id": "dhb_batch",
                "supplier_id": "dhb",
                "row_key": "dhb_batch_row_3",
                "supplier_sku": "DHB-3",
                "barcode": "5000000000003",
                "placeholder_outcome": "PASS",
                "result_status": "PASS",
                "fail_code": "",
                "last_stage": "webscrape",
                "memory_scope": "supplier_offer",
                "cooldown_days": "0",
                "scanned_at_utc": "2026-04-30T11:00:00Z",
                "notes": "already done",
            }
        ],
        PLACEHOLDER_SCANNER_RESULT_COLUMNS,
    )

    summary = build_next_action(root=tmp_path, observed_utc="2026-04-30T12:00:00Z")

    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    by_key = eligibility.set_index("row_key")
    assert summary["scan_rows"] == 1
    assert summary["skip_rows"] == 3
    assert by_key.loc["dhb_batch_row_1", "scan_decision"] == "scan"
    assert by_key.loc["dhb_batch_row_2", "decision_reason"] == "timeout_active"
    assert by_key.loc["dhb_batch_row_2", "cooldown_until_utc"] == "2026-09-28T00:00:00Z"
    assert by_key.loc["dhb_batch_row_3", "decision_reason"] == "already_processed_in_placeholder_results"
    assert by_key.loc["dhb_batch_row_4", "decision_reason"] == "missing_barcode"
    assert summary["selected_supplier_id"] == "dhb"
    assert summary["estimated_scan_rows"] == 1


def test_fpm040_skips_exact_prior_pass_memory(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(test_dir / "supplier_registry.csv", [_registry_row("dhb", "monthly_manual")], SUPPLIER_REGISTRY_COLUMNS)
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("dhb_batch", "dhb", "3", received="2026-05-05T10:00:00Z")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _row("dhb_batch", "dhb", 1, "5000000000001", "1.00"),
            _row("dhb_batch", "dhb", 2, "5000000000002", "2.00"),
            _row("dhb_batch", "dhb", 3, "5000000000003", "3.00"),
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        test_dir / "barcode_scan_memory.csv",
        [
            {
                "memory_key": "supplier_offer:dhb:5000000000001:1.00",
                "memory_scope": "supplier_offer",
                "supplier_id": "dhb",
                "barcode": "5000000000001",
                "asin": "B00PASSED",
                "last_result_status": "PASS",
                "last_fail_code": "",
                "last_stage": "webscrape",
                "last_scanned_at_utc": "2026-05-05T00:00:00Z",
                "cooldown_until_utc": "",
                "cooldown_basis": "PASS",
                "attempt_count": "1",
                "last_batch_id": "old_batch",
                "last_row_hash": "old_hash",
                "updated_at_utc": "2026-05-05T00:00:00Z",
            },
            {
                "memory_key": "supplier_offer:dhb:5000000000002:1.50",
                "memory_scope": "supplier_offer",
                "supplier_id": "dhb",
                "barcode": "5000000000002",
                "asin": "B00OLDCOST",
                "last_result_status": "PASS",
                "last_fail_code": "",
                "last_stage": "webscrape",
                "last_scanned_at_utc": "2026-05-05T00:00:00Z",
                "cooldown_until_utc": "",
                "cooldown_basis": "PASS",
                "attempt_count": "1",
                "last_batch_id": "old_batch",
                "last_row_hash": "old_hash",
                "updated_at_utc": "2026-05-05T00:00:00Z",
            },
        ],
        BARCODE_SCAN_MEMORY_COLUMNS,
    )

    summary = build_next_action(root=tmp_path, observed_utc="2026-05-06T00:00:00Z")

    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    by_key = eligibility.set_index("row_key")
    assert summary["scan_rows"] == 2
    assert summary["skip_rows"] == 1
    assert by_key.loc["dhb_batch_row_1", "scan_decision"] == "skip"
    assert by_key.loc["dhb_batch_row_1", "decision_reason"] == "already_passed_in_memory"
    assert by_key.loc["dhb_batch_row_2", "scan_decision"] == "scan"
    assert by_key.loc["dhb_batch_row_2", "decision_reason"] == "pass_cost_changed_reset"
    assert by_key.loc["dhb_batch_row_3", "scan_decision"] == "scan"
    assert summary["selected_supplier_id"] == "dhb"
    assert summary["estimated_scan_rows"] == 2


def test_fpm040_cost_change_resets_policy_timeout(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(test_dir / "supplier_registry.csv", [_registry_row("dhb", "monthly_manual")], SUPPLIER_REGISTRY_COLUMNS)
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("dhb_batch", "dhb", "1", received="2026-05-01T10:00:00Z")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [_row("dhb_batch", "dhb", 1, "5000000000001", "4.50")],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        test_dir / "barcode_scan_memory.csv",
        [
            {
                "memory_key": "supplier_offer:dhb:5000000000001:5.00",
                "memory_scope": "supplier_offer",
                "supplier_id": "dhb",
                "barcode": "5000000000001",
                "asin": "",
                "last_result_status": "FAIL",
                "last_fail_code": "NOCOST",
                "last_stage": "cost_gate",
                "last_scanned_at_utc": "2026-05-01T00:00:00Z",
                "cooldown_until_utc": "2026-05-31T00:00:00Z",
                "cooldown_basis": "NOCOST",
                "attempt_count": "1",
                "last_batch_id": "old_batch",
                "last_row_hash": "old_hash",
                "updated_at_utc": "2026-05-01T00:00:00Z",
            }
        ],
        BARCODE_SCAN_MEMORY_COLUMNS,
    )

    summary = build_next_action(root=tmp_path, observed_utc="2026-05-02T00:00:00Z")

    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    row = eligibility.iloc[0]
    assert summary["scan_rows"] == 1
    assert row["scan_decision"] == "scan"
    assert row["decision_reason"] == "cost_changed_reset"
    assert row["memory_key"] == "supplier_offer:dhb:5000000000001:5.00"


def test_fpm040_prioritises_recovery_rows_after_timeout(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [_registry_row("fresh_supplier", "daily_email"), _registry_row("recovery_supplier", "manual_download")],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            _batch("fresh_batch", "fresh_supplier", "10", received="2026-05-01T08:00:00Z"),
            _batch("recovery_batch", "recovery_supplier", "1", received="2026-04-01T08:00:00Z"),
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    fresh_rows = [_row("fresh_batch", "fresh_supplier", index, f"5000000000{index:03d}") for index in range(1, 11)]
    recovery_row = _row("recovery_batch", "recovery_supplier", 1, "5010000000001")
    _write_csv(test_dir / "batch_rows.csv", fresh_rows + [recovery_row], BATCH_ROW_COLUMNS)
    _write_csv(
        test_dir / "barcode_scan_memory.csv",
        [
            {
                "memory_key": "barcode:5010000000001",
                "memory_scope": "barcode",
                "supplier_id": "recovery_supplier",
                "barcode": "5010000000001",
                "asin": "B00RECOVERY",
                "last_result_status": "RESCAN",
                "last_fail_code": "RESCAN",
                "last_stage": "retry",
                "last_scanned_at_utc": "2026-01-01T00:00:00Z",
                "cooldown_until_utc": "2026-01-31T00:00:00Z",
                "cooldown_basis": "RESCAN",
                "attempt_count": "1",
                "last_batch_id": "old_batch",
                "last_row_hash": "old_hash",
                "updated_at_utc": "2026-01-01T00:00:00Z",
            }
        ],
        BARCODE_SCAN_MEMORY_COLUMNS,
    )

    summary = build_next_action(root=tmp_path, observed_utc="2026-05-01T10:00:00Z")

    decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    latest = decisions.iloc[-1]
    assert summary["selected_supplier_id"] == "recovery_supplier"
    assert summary["estimated_scan_rows"] == 1
    assert latest["reason_code"] == "recovery_rows_prioritised_after_timeout"


def test_fpm040_manual_review_policy_blocks_automatic_rescan(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(test_dir / "supplier_registry.csv", [_registry_row("dhb", "monthly_manual")], SUPPLIER_REGISTRY_COLUMNS)
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("dhb_batch", "dhb", "1", received="2026-05-01T10:00:00Z")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [_row("dhb_batch", "dhb", 1, "5000000000001", "5.00")],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        test_dir / "barcode_scan_memory.csv",
        [
            {
                "memory_key": "supplier_offer:dhb:5000000000001:5.00",
                "memory_scope": "supplier_offer",
                "supplier_id": "dhb",
                "barcode": "5000000000001",
                "asin": "",
                "last_result_status": "FAIL",
                "last_fail_code": "BRANDFAIL",
                "last_stage": "webscrape",
                "last_scanned_at_utc": "2025-01-01T00:00:00Z",
                "cooldown_until_utc": "",
                "cooldown_basis": "BRANDFAIL",
                "attempt_count": "1",
                "last_batch_id": "old_batch",
                "last_row_hash": "old_hash",
                "updated_at_utc": "2025-01-01T00:00:00Z",
            }
        ],
        BARCODE_SCAN_MEMORY_COLUMNS,
    )
    policy = default_timeout_policy_df("2026-05-01T10:00:00Z")
    mask = policy["fail_code"] == "BRANDFAIL"
    policy.loc[mask, "timeout_mode"] = "manual_review"
    policy.loc[mask, "manual_review_required_flag"] = "1"
    write_timeout_policy_df(tmp_path, policy, observed_utc="2026-05-01T10:00:00Z")

    summary = build_next_action(root=tmp_path, observed_utc="2026-05-02T00:00:00Z")

    eligibility = pd.read_csv(test_dir / "batch_scan_eligibility.csv", dtype=str).fillna("")
    row = eligibility.iloc[0]
    assert summary["scan_rows"] == 0
    assert summary["skip_rows"] == 1
    assert row["scan_decision"] == "skip"
    assert row["decision_reason"] == "manual_review_required"


def test_fpm040_operator_prioritise_overrides_bigger_batch(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [_registry_row("stax", "api"), _registry_row("heo", "api")],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            _batch("stax_batch", "stax", "4", received="2026-04-30T10:00:00Z"),
            _batch("heo_batch", "heo", "1", received="2026-04-30T09:00:00Z"),
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _row("stax_batch", "stax", 1, "5000000000001"),
            _row("stax_batch", "stax", 2, "5000000000002"),
            _row("stax_batch", "stax", 3, "5000000000003"),
            _row("stax_batch", "stax", 4, "5000000000004"),
            _row("heo_batch", "heo", 1, "6000000000001"),
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        test_dir / "queue_controls.csv",
        [
            {
                "supplier_id": "heo",
                "control_state": "prioritised",
                "priority_rank": "1",
                "reason": "operator wants a smaller test first",
                "updated_at_utc": "2026-04-30T11:00:00Z",
            }
        ],
        QUEUE_CONTROL_COLUMNS,
    )

    summary = build_next_action(root=tmp_path, observed_utc="2026-04-30T12:00:00Z")

    decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    latest = decisions.iloc[-1]
    assert summary["selected_supplier_id"] == "heo"
    assert summary["estimated_scan_rows"] == 1
    assert latest["reason_code"] == "operator_prioritised_supplier"
    assert "prioritised_suppliers=heo" in latest["notes"]


def test_fpm040_operator_pause_removes_supplier_from_candidate_choice(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [_registry_row("stax", "api"), _registry_row("heo", "api")],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            _batch("stax_batch", "stax", "4", received="2026-04-30T10:00:00Z"),
            _batch("heo_batch", "heo", "1", received="2026-04-30T09:00:00Z"),
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _row("stax_batch", "stax", 1, "5000000000001"),
            _row("stax_batch", "stax", 2, "5000000000002"),
            _row("stax_batch", "stax", 3, "5000000000003"),
            _row("stax_batch", "stax", 4, "5000000000004"),
            _row("heo_batch", "heo", 1, "6000000000001"),
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        test_dir / "queue_controls.csv",
        [
            {
                "supplier_id": "stax",
                "control_state": "paused",
                "priority_rank": "",
                "reason": "operator pause",
                "updated_at_utc": "2026-04-30T11:00:00Z",
            }
        ],
        QUEUE_CONTROL_COLUMNS,
    )

    summary = build_next_action(root=tmp_path, observed_utc="2026-04-30T12:00:00Z")

    decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    latest = decisions.iloc[-1]
    assert summary["selected_supplier_id"] == "heo"
    assert summary["estimated_scan_rows"] == 1
    assert latest["reason_code"] == "highest_eligible_scan_rows_after_cooldown"
    assert "paused_suppliers=stax" in latest["notes"]
