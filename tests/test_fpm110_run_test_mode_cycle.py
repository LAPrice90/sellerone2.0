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

from scripts.flows.F.price_list_manager.FPM110_run_test_mode_cycle import run_test_mode_cycle
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    PLACEHOLDER_SCANNER_RESULT_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
    TEST_MODE_CYCLE_RUN_COLUMNS,
    TEST_MODE_CYCLE_STEP_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


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


def _batch(batch_id: str, supplier_id: str, rows: int, received: str) -> dict[str, str]:
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "source_type": "manual_request",
        "source_subtype": "email_request",
        "source_received_at_utc": received,
        "source_file_path": f"{batch_id}.csv",
        "source_file_hash": f"{batch_id}_hash",
        "converted_file_path": f"{batch_id}_converted.csv",
        "source_row_count": str(rows),
        "valid_row_count": str(rows),
        "held_row_count": "0",
        "new_row_count": str(rows),
        "changed_row_count": "0",
        "eligible_row_count": str(rows),
        "skipped_cooldown_row_count": "0",
        "batch_status": "imported_from_source",
        "status_reason": "ready_source_file_imported",
        "updated_at_utc": received,
    }


def _rows(batch_id: str, supplier_id: str, count: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    barcode_prefix = "500000000" if supplier_id == "stax" else "600000000"
    for index in range(1, count + 1):
        row_key = f"{batch_id}_row_{index}"
        rows.append(
            {
                "batch_id": batch_id,
                "supplier_id": supplier_id,
                "row_key": row_key,
                "supplier_sku": f"{supplier_id.upper()}-{index:03d}",
                "supplier_title": f"{supplier_id} product {index}",
                "barcode": f"{barcode_prefix}{index:04d}",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": row_key,
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "test_ready",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            }
        )
    return rows


def test_fpm110_runs_fake_scan_once_per_supplier_and_moves_to_next(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [_registry_row("stax", "api"), _registry_row("heo", "api")],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            _batch("stax_batch", "stax", 12, "2026-04-30T10:00:00Z"),
            _batch("heo_batch", "heo", 12, "2026-04-30T09:00:00Z"),
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    _write_csv(
        test_dir / "batch_rows.csv",
        [*_rows("stax_batch", "stax", 12), *_rows("heo_batch", "heo", 12)],
        BATCH_ROW_COLUMNS,
    )

    summary = run_test_mode_cycle(
        root=tmp_path,
        started_at_utc="2026-04-30T15:00:00Z",
        max_iterations=2,
        run_acquisition=False,
    )

    runs = pd.read_csv(test_dir / "test_mode_cycle_runs.csv", dtype=str).fillna("")
    steps = pd.read_csv(test_dir / "test_mode_cycle_steps.csv", dtype=str).fillna("")
    results = pd.read_csv(test_dir / "placeholder_scanner_results.csv", dtype=str).fillna("")
    dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")

    assert summary["status"] == "success"
    assert summary["scanner_iterations"] == 2
    assert summary["result_rows"] == 20
    assert summary["cycle_health_status"] == "ok"
    assert summary["total_placeholder_results"] == 20
    assert summary["processed_suppliers"] == "heo,stax"
    assert list(runs.columns) == TEST_MODE_CYCLE_RUN_COLUMNS
    assert list(steps.columns) == TEST_MODE_CYCLE_STEP_COLUMNS
    assert list(results.columns) == PLACEHOLDER_SCANNER_RESULT_COLUMNS
    assert len(results.index) == 20
    assert set(results["supplier_id"].tolist()) == {"stax", "heo"}
    assert (results.groupby("supplier_id").size().to_dict()) == {"heo": 10, "stax": 10}
    by_supplier = dashboard.set_index("supplier_id")
    assert by_supplier.loc["stax", "web_unprocessed"] == "2"
    assert by_supplier.loc["heo", "web_unprocessed"] == "2"
    latest_cycle_health = health[health["check"] == "test_mode_cycle_reconciliation"].iloc[-1]
    assert latest_cycle_health["status"] == "ok"
    assert latest_cycle_health["value"] == "20"
