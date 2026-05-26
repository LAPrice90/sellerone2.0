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

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F.price_list_manager.FPM126_update_memory_from_f061_results import update_memory_from_f061_results
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _batch_row(row_key: str, barcode: str, unit_cost: str) -> dict[str, str]:
    return {
        "batch_id": "stax_batch",
        "supplier_id": "stax",
        "row_key": row_key,
        "supplier_sku": row_key.upper(),
        "supplier_title": f"Product {row_key}",
        "barcode": barcode,
        "unit_cost": unit_cost,
        "currency": "GBP",
        "vat_rate": "20",
        "source_row_hash": f"source_hash_{row_key}",
        "row_change_status": "new",
        "scan_eligibility": "scan_now",
        "eligibility_reason": "valid",
        "last_memory_key": "",
        "cooldown_until_utc": "",
    }


def _screening_row(
    *,
    row_key: str,
    barcode: str,
    row_status: str,
    fail_code: str = "",
    pf: str = "",
    asin: str = "",
) -> dict[str, str]:
    return {
        "observed_utc": "2026-05-01T10:00:00Z",
        "run_id": "stax_run",
        "supplier_id": "stax",
        "supplier_name": "Stax",
        "supplier_sku": row_key.upper(),
        "barcode": barcode,
        "candidate_id": row_key,
        "asin": asin,
        "row_status": row_status,
        "last_stage": "webscrape" if fail_code else "decision",
        "fail_code": fail_code,
        "attempt_count": "1",
        "timeout_until_utc": "2026-10-28T10:00:00Z" if fail_code else "",
        "mode": "legacy_module",
        "updated_at_utc": "2026-05-01T10:00:00Z",
        "source_seen_at_utc": "2026-05-01T09:00:00Z",
        "pf": pf,
        "status_reason": fail_code,
        "recommendation_status": "",
        "recommended_test_qty": "",
    }


def test_fpm126_imports_finalized_f061_screening_rows_into_timeout_memory(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "batch_rows.csv",
        [
            _batch_row("row_1", "5000000000001", "1.00"),
            _batch_row("row_2", "5000000000002", "5.00"),
            _batch_row("row_3", "5000000000003", "2.00"),
        ],
        BATCH_ROW_COLUMNS,
    )
    _write_csv(
        test_dir / "barcode_scan_memory.csv",
        [
            {
                "memory_key": "barcode:5000000000001",
                "memory_scope": "global_barcode",
                "supplier_id": "old_supplier",
                "barcode": "5000000000001",
                "asin": "",
                "last_result_status": "FAIL",
                "last_fail_code": "FAIL",
                "last_stage": "webscrape",
                "last_scanned_at_utc": "2026-01-01T00:00:00Z",
                "cooldown_until_utc": "2026-04-01T00:00:00Z",
                "cooldown_basis": "FAIL",
                "attempt_count": "1",
                "last_batch_id": "old_batch",
                "last_row_hash": "old_hash",
                "updated_at_utc": "2026-01-01T00:00:00Z",
            }
        ],
        BARCODE_SCAN_MEMORY_COLUMNS,
    )
    _write_csv(
        test_dir / "health.csv",
        [
            {
                "check": "older_unrelated_check",
                "status": "fail",
                "value": "1",
                "notes": "unrelated historical failure must not make this import blocked",
                "observed_utc": "2026-04-30T10:00:00Z",
                "source_path": "older.csv",
            }
        ],
        MANAGER_HEALTH_COLUMNS,
    )
    write_f_contract_df(
        tmp_path,
        "f_screening_row_state_live",
        pd.DataFrame(
            [
                _screening_row(row_key="row_1", barcode="5000000000001", row_status="timeout", fail_code="PRICEHISTORYFAIL", pf="FAIL"),
                _screening_row(row_key="row_2", barcode="5000000000002", row_status="timeout", fail_code="ROIFAIL", pf="FAIL"),
                _screening_row(row_key="row_3", barcode="5000000000003", row_status="pass", pf="PASS", asin="B000TEST01"),
                _screening_row(row_key="row_4", barcode="5000000000004", row_status="pending"),
            ]
        ),
    )

    summary = update_memory_from_f061_results(
        root=tmp_path,
        observed_utc="2026-05-01T10:05:00Z",
        supplier_id="stax",
        run_id="stax_run",
    )

    memory = pd.read_csv(test_dir / "barcode_scan_memory.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")
    by_key = memory.set_index("memory_key")

    assert summary["status"] == "success"
    assert summary["processed_rows"] == 3
    assert summary["imported_screening_rows"] == 3
    assert summary["new_memory_rows"] == 4
    assert summary["memory_rows"] == 4
    assert summary["unique_memory_keys"] == 4
    assert summary["skipped_pending_rows"] == 1
    assert summary["current_health_fail_rows"] == 0
    assert summary["health_fail_rows"] == 1
    assert list(memory.columns) == BARCODE_SCAN_MEMORY_COLUMNS
    assert by_key.loc["barcode:5000000000001", "last_fail_code"] == "PRICEHISTORYFAIL"
    assert by_key.loc["barcode:5000000000001", "supplier_id"] == "stax"
    assert by_key.loc["supplier_offer:stax:5000000000002:5.00", "last_fail_code"] == "ROIFAIL"
    assert by_key.loc["barcode:5000000000003", "last_result_status"] == "PASS"
    assert by_key.loc["supplier_offer:stax:5000000000003:2.00", "last_result_status"] == "PASS"
    assert list(health.columns) == MANAGER_HEALTH_COLUMNS
    memory_health = health[health["check"].str.startswith("f061_result_memory")]
    assert int((memory_health["status"].str.lower() == "fail").sum()) == 0
