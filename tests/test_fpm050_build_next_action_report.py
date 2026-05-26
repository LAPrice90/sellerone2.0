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
from scripts.flows.F.price_list_manager.FPM050_build_next_action_report import build_next_action_report
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    NEXT_ACTION_SKIP_REASON_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _registry_row(supplier_id: str) -> dict[str, str]:
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
        "priority_band": "monthly_manual",
        "active_flag": "1",
        "notes": "test",
    }


def _batch(batch_id: str, supplier_id: str, valid_rows: str) -> dict[str, str]:
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "source_type": "manual_request",
        "source_subtype": "email_request",
        "source_received_at_utc": "2026-04-30T10:00:00Z",
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
        "updated_at_utc": "2026-04-30T10:00:00Z",
    }


def _row(
    batch_id: str,
    supplier_id: str,
    index: int,
    *,
    scan_eligibility: str = "scan_now",
    eligibility_reason: str = "test",
) -> dict[str, str]:
    row_key = f"{batch_id}_row_{index}"
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "row_key": row_key,
        "supplier_sku": f"{supplier_id.upper()}-{index}",
        "barcode": f"500000000000{index}",
        "unit_cost": "1.00",
        "currency": "GBP",
        "source_row_hash": row_key,
        "row_change_status": "new",
        "scan_eligibility": scan_eligibility,
        "eligibility_reason": eligibility_reason,
        "last_memory_key": "",
        "cooldown_until_utc": "",
    }


def test_fpm050_builds_read_only_next_action_report(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [_registry_row("bliss_distribution"), _registry_row("dhb")],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("bliss_batch", "bliss_distribution", "3"), _batch("dhb_batch", "dhb", "1")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _row("bliss_batch", "bliss_distribution", 1),
            _row("bliss_batch", "bliss_distribution", 2),
            _row(
                "bliss_batch",
                "bliss_distribution",
                3,
                scan_eligibility="hold",
                eligibility_reason="missing_barcode",
            ),
            _row("dhb_batch", "dhb", 1),
        ],
        BATCH_ROW_COLUMNS,
    )

    build_next_action(root=tmp_path, observed_utc="2026-04-30T12:00:00Z")
    summary = build_next_action_report(root=tmp_path, built_at_utc="2026-04-30T12:05:00Z")

    report_path = test_dir / "next_action_report.md"
    reason_path = test_dir / "next_action_skip_reasons.csv"
    health_path = test_dir / "health.csv"
    report_text = report_path.read_text(encoding="utf-8")
    reasons = pd.read_csv(reason_path, dtype=str).fillna("")
    health = pd.read_csv(health_path, dtype=str).fillna("")

    assert summary["status"] == "success"
    assert summary["eligibility_rows"] == 4
    assert summary["scan_rows"] == 3
    assert summary["skip_rows"] == 1
    assert "Live F061 handoff: disabled" in report_text
    assert "- Supplier: Bliss Distribution" in report_text
    assert "- Estimated scan rows: 2" in report_text
    assert "- Safe to hand off to F061: 0" in report_text
    assert "Bliss Distribution: missing_barcode = 1" in report_text
    assert list(reasons.columns) == NEXT_ACTION_SKIP_REASON_COLUMNS
    assert list(health.columns) == MANAGER_HEALTH_COLUMNS
    assert int(summary["health_fail_rows"]) == 0


def test_fpm050_uses_latest_appended_decision_not_future_stale_timestamp(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [_registry_row("bliss_distribution"), _registry_row("dhb")],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [_batch("bliss_batch", "bliss_distribution", "2"), _batch("dhb_batch", "dhb", "1")],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _row("bliss_batch", "bliss_distribution", 1),
            _row("bliss_batch", "bliss_distribution", 2),
            _row("dhb_batch", "dhb", 1),
        ],
        BATCH_ROW_COLUMNS,
    )

    build_next_action(root=tmp_path, observed_utc="2026-04-30T12:00:00Z")
    decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    stale_future_decision = {
        "decision_id": "stale_future_dhb",
        "decided_at_utc": "2026-04-30T18:00:00Z",
        "recommended_action": "recommend_test_scan",
        "supplier_id": "dhb",
        "batch_id": "dhb_batch",
        "reason_code": "stale_future_test_seed",
        "estimated_scan_rows": "1",
        "estimated_skip_rows": "0",
        "f061_owner_status": "not_checked_test_mode",
        "safe_to_handoff_flag": "0",
        "notes": "stale decision should not override last appended manager decision",
    }
    _write_csv(
        test_dir / "manager_decisions.csv",
        [stale_future_decision, *decisions.to_dict("records")],
        MANAGER_DECISION_COLUMNS,
    )

    build_next_action_report(root=tmp_path, built_at_utc="2026-04-30T12:05:00Z")
    report_text = (test_dir / "next_action_report.md").read_text(encoding="utf-8")

    assert "- Supplier: Bliss Distribution" in report_text
    assert "- Batch: bliss_batch" in report_text
    assert "- Supplier: Dhb" not in report_text
