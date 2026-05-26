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

from scripts.flows.F.price_list_manager.FPM120_build_f061_live_trial_samples import (
    build_f061_live_trial_samples,
)
from scripts.flows.F.price_list_manager.FPM121_apply_f061_live_trial_supplier import (
    apply_f061_live_trial_supplier,
)
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_LIVE_TRIAL_SAMPLE_COLUMNS,
    F061_STAGED_ACTIVE_RUN_COLUMNS,
    F061_STAGED_RUN_STATE_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _seed_trial_inputs(tmp_path: Path) -> Path:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    _write_csv(
        test_dir / "supplier_registry.csv",
        [
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api_pull",
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
            },
            {
                "supplier_id": "dhb",
                "supplier_name": "DHB",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_url": "",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "dhb",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "test",
            },
        ],
        SUPPLIER_REGISTRY_COLUMNS,
    )
    _write_csv(
        test_dir / "price_list_batches.csv",
        [
            {
                "batch_id": "stax_old",
                "supplier_id": "stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_received_at_utc": "2026-04-29T10:00:00Z",
                "source_file_path": "old.csv",
                "source_file_hash": "old",
                "converted_file_path": "old_converted.csv",
                "source_row_count": "60",
                "valid_row_count": "60",
                "held_row_count": "0",
                "new_row_count": "60",
                "changed_row_count": "0",
                "eligible_row_count": "60",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready",
                "updated_at_utc": "2026-04-29T10:01:00Z",
            },
            {
                "batch_id": "stax_new",
                "supplier_id": "stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "new.csv",
                "source_file_hash": "new",
                "converted_file_path": "new_converted.csv",
                "source_row_count": "60",
                "valid_row_count": "60",
                "held_row_count": "0",
                "new_row_count": "60",
                "changed_row_count": "0",
                "eligible_row_count": "60",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            },
            {
                "batch_id": "dhb_batch",
                "supplier_id": "dhb",
                "source_type": "manual_request",
                "source_subtype": "email_request",
                "source_received_at_utc": "2026-04-30T09:00:00Z",
                "source_file_path": "dhb.xlsx",
                "source_file_hash": "dhb",
                "converted_file_path": "dhb_converted.csv",
                "source_row_count": "55",
                "valid_row_count": "49",
                "held_row_count": "6",
                "new_row_count": "49",
                "changed_row_count": "0",
                "eligible_row_count": "49",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready",
                "updated_at_utc": "2026-04-30T09:01:00Z",
            },
        ],
        PRICE_LIST_BATCH_COLUMNS,
    )
    rows: list[dict[str, str]] = []
    for batch_id, supplier_id, count in [("stax_old", "stax", 60), ("stax_new", "stax", 60), ("dhb_batch", "dhb", 49)]:
        for index in range(1, count + 1):
            rows.append(
                {
                    "batch_id": batch_id,
                    "supplier_id": supplier_id,
                    "row_key": f"{batch_id}_{index:03d}",
                    "supplier_sku": f"{supplier_id.upper()}-{index:03d}",
                    "supplier_title": f"{supplier_id} Product {index}",
                    "barcode": f"500000000{index:04d}",
                    "unit_cost": "1.23",
                    "currency": "GBP",
                    "vat_rate": "20",
                    "source_row_hash": f"hash-{batch_id}-{index}",
                    "row_change_status": "new",
                    "scan_eligibility": "scan_now",
                    "eligibility_reason": "valid",
                    "last_memory_key": "",
                    "cooldown_until_utc": "",
                }
            )
    _write_csv(test_dir / "batch_rows.csv", rows, BATCH_ROW_COLUMNS)
    return test_dir


def test_fpm120_builds_exact_50_row_sample_from_latest_ready_batch(tmp_path: Path) -> None:
    test_dir = _seed_trial_inputs(tmp_path)

    summary = build_f061_live_trial_samples(
        root=tmp_path,
        trial_id="trial_one",
        built_at_utc="2026-04-30T13:00:00Z",
        sample_rows=50,
        supplier_ids=["stax"],
    )

    sample_log = pd.read_csv(test_dir / "f061_live_trial_samples.csv", dtype=str).fillna("")
    active = pd.read_csv(sample_log.iloc[0]["sample_active_run_path"], dtype=str).fillna("")
    state = pd.read_csv(sample_log.iloc[0]["sample_run_state_path"], dtype=str).fillna("")
    assert summary["status"] == "built"
    assert summary["supplier_rows"] == 1
    assert list(sample_log.columns) == F061_LIVE_TRIAL_SAMPLE_COLUMNS
    assert sample_log.iloc[0]["batch_id"] == "stax_new"
    assert sample_log.iloc[0]["selected_rows"] == "50"
    assert list(active.columns) == F061_STAGED_ACTIVE_RUN_COLUMNS
    assert list(state.columns) == F061_STAGED_RUN_STATE_COLUMNS
    assert len(active.index) == 50
    assert set(active["supplier_id"].tolist()) == {"stax"}
    assert set(active["scan_status"].tolist()) == {"pending"}
    assert state.iloc[0]["pending_rows"] == "50"


def test_fpm120_records_short_supplier_without_failing_schema(tmp_path: Path) -> None:
    test_dir = _seed_trial_inputs(tmp_path)

    summary = build_f061_live_trial_samples(
        root=tmp_path,
        trial_id="trial_short",
        built_at_utc="2026-04-30T13:00:00Z",
        sample_rows=50,
        supplier_ids=["dhb"],
    )

    sample_log = pd.read_csv(test_dir / "f061_live_trial_samples.csv", dtype=str).fillna("")
    assert summary["short_suppliers"] == 1
    assert sample_log.iloc[0]["selected_rows"] == "49"
    assert sample_log.iloc[0]["held_reason"] == "only_49_ready_rows"


def test_fpm121_preview_and_live_apply_write_one_supplier_sample_with_backup(tmp_path: Path) -> None:
    _seed_trial_inputs(tmp_path)
    build_f061_live_trial_samples(
        root=tmp_path,
        trial_id="trial_apply",
        built_at_utc="2026-04-30T13:00:00Z",
        sample_rows=50,
        supplier_ids=["stax"],
    )

    preview = apply_f061_live_trial_supplier(
        root=tmp_path,
        supplier_id="stax",
        trial_id="trial_apply",
        built_at_utc="2026-04-30T13:05:00Z",
    )
    applied = apply_f061_live_trial_supplier(
        root=tmp_path,
        supplier_id="stax",
        trial_id="trial_apply",
        built_at_utc="2026-04-30T13:06:00Z",
        apply_live=True,
        confirm_live_trial=True,
    )

    active = pd.read_csv(tmp_path / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv", dtype=str).fillna("")
    state = pd.read_csv(tmp_path / "out" / "systems" / "F" / "inbox" / "supplier_price_list_run_state.csv", dtype=str).fillna("")
    manifest = pd.read_csv(Path(applied["backup_manifest_path"]), dtype=str).fillna("")
    assert preview["status"] == "ready"
    assert preview["live_write_succeeded"] == "0"
    assert applied["status"] == "applied"
    assert applied["live_write_succeeded"] == "1"
    assert len(active.index) == 50
    assert set(active["supplier_id"].tolist()) == {"stax"}
    assert state.iloc[0]["pending_rows"] == "50"
    assert len(manifest.index) == 2
