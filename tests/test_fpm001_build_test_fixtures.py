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

from scripts.flows.F.price_list_manager.FPM001_build_test_fixtures import build_test_fixtures
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _write_registry(root: Path) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "suppliers.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "source_folder_path": "",
                "existing_supplier_config_path": "config/feeder/suppliers/shure_cosmetics.json",
                "converter_id": "shure_cosmetics",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "pilot",
                "active_flag": "1",
                "notes": "test row",
            }
        )
        writer.writerow(
            {
                "supplier_id": "dhb",
                "supplier_name": "DHB",
                "source_type": "manual_request",
                "source_subtype": "desktop_csv_folder",
                "source_url": "",
                "source_folder_path": r"C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox",
                "existing_supplier_config_path": "",
                "converter_id": "dhb",
                "normal_refresh_days": "30",
                "minimum_rescan_days": "30",
                "large_file_flag": "0",
                "manual_request_required_flag": "1",
                "priority_band": "monthly_manual",
                "active_flag": "1",
                "notes": "manual test row",
            }
        )


def test_fpm001_builds_shure_test_mode_fixtures_without_live_f_writes(tmp_path: Path) -> None:
    _write_registry(tmp_path)

    summary = build_test_fixtures(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        observed_utc="2026-04-30T09:00:00Z",
    )

    test_mode_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    registry_path = test_mode_dir / "supplier_registry.csv"
    batches_path = test_mode_dir / "price_list_batches.csv"
    batch_rows_path = test_mode_dir / "batch_rows.csv"
    decisions_path = test_mode_dir / "manager_decisions.csv"
    health_path = test_mode_dir / "health.csv"

    assert summary["status"] == "success"
    assert summary["supplier_id"] == "shure_cosmetics"
    assert summary["source_type"] == "api_pull"
    assert summary["source_subtype"] == "csv_link"
    assert summary["source_rows"] == 10
    assert summary["valid_rows"] == 10
    assert summary["eligible_rows"] == 10
    assert summary["health_fail_rows"] == 0

    assert registry_path.exists()
    assert batches_path.exists()
    assert batch_rows_path.exists()
    assert decisions_path.exists()
    assert health_path.exists()

    registry = pd.read_csv(registry_path, dtype=str).fillna("")
    batches = pd.read_csv(batches_path, dtype=str).fillna("")
    batch_rows = pd.read_csv(batch_rows_path, dtype=str).fillna("")
    decisions = pd.read_csv(decisions_path, dtype=str).fillna("")
    health = pd.read_csv(health_path, dtype=str).fillna("")

    assert list(registry.columns) == SUPPLIER_REGISTRY_COLUMNS
    assert list(batches.columns) == PRICE_LIST_BATCH_COLUMNS
    assert list(batch_rows.columns) == BATCH_ROW_COLUMNS
    assert list(decisions.columns) == MANAGER_DECISION_COLUMNS
    assert list(health.columns) == MANAGER_HEALTH_COLUMNS

    assert len(registry) == 2
    assert len(batches) == 1
    assert len(batch_rows) == 10
    assert len(decisions) == 1
    assert set(health["status"]) == {"ok"}

    assert set(batch_rows["supplier_id"]) == {"shure_cosmetics"}
    assert set(batch_rows["scan_eligibility"]) == {"scan_now"}
    assert set(batch_rows["row_change_status"]) == {"new"}
    assert batch_rows["source_row_hash"].nunique() == 10
    assert decisions.iloc[0]["recommended_action"] == "run_test_scan"
    assert decisions.iloc[0]["safe_to_handoff_flag"] == "0"
    assert batches.iloc[0]["batch_status"] == "recommendation_ready"

    assert not (tmp_path / "out" / "systems" / "F" / "inbox").exists()
    assert not (tmp_path / "out" / "systems" / "F" / "live").exists()


def test_fpm001_requires_registered_supplier(tmp_path: Path) -> None:
    _write_registry(tmp_path)

    with pytest.raises(ValueError, match="supplier_id not registered"):
        build_test_fixtures(root=tmp_path, supplier_id="missing_supplier")


def test_fpm001_requires_registry_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="supplier registry missing"):
        build_test_fixtures(root=tmp_path, supplier_id="shure_cosmetics")
