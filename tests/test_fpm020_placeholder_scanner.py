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

from scripts.flows.F.price_list_manager.FPM001_build_test_fixtures import build_test_fixtures
from scripts.flows.F.price_list_manager.FPM020_run_placeholder_scanner import run_placeholder_scanner
from scripts.flows.F.price_list_manager._schemas import PLACEHOLDER_SCANNER_RESULT_COLUMNS, SUPPLIER_REGISTRY_COLUMNS


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


def test_fpm020_writes_ten_placeholder_results(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    build_test_fixtures(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        observed_utc="2026-04-30T09:00:00Z",
    )

    summary = run_placeholder_scanner(root=tmp_path, scanned_at_utc="2026-04-30T09:10:00Z")

    results_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "placeholder_scanner_results.csv"
    results = pd.read_csv(results_path, dtype=str).fillna("")

    assert summary["status"] == "success"
    assert summary["result_rows"] == 10
    assert summary["pass_rows"] == 1
    assert summary["fail_rows"] == 8
    assert summary["rescan_rows"] == 1
    assert list(results.columns) == PLACEHOLDER_SCANNER_RESULT_COLUMNS
    assert results["placeholder_outcome"].tolist() == [
        "PASS",
        "NOASIN",
        "OVER50K",
        "NOCOST",
        "ROIFAIL_NEAR",
        "ROIFAIL_FAR",
        "SCRAPEFAIL",
        "SELLERHISTORYFAIL",
        "BRANDFAIL",
        "MANUAL_REVIEW",
    ]
    assert results["result_status"].value_counts().to_dict() == {"FAIL": 8, "PASS": 1, "RESCAN": 1}
    cooldown_by_outcome = results.set_index("placeholder_outcome")["cooldown_days"].to_dict()
    assert cooldown_by_outcome["NOASIN"] == "90"
    assert cooldown_by_outcome["OVER50K"] == "90"
    assert cooldown_by_outcome["SCRAPEFAIL"] == "30"
    assert cooldown_by_outcome["SELLERHISTORYFAIL"] == "180"
    assert cooldown_by_outcome["BRANDFAIL"] == "180"
    assert set(results["scanned_at_utc"]) == {"2026-04-30T09:10:00Z"}
    assert not (tmp_path / "out" / "systems" / "F" / "inbox").exists()
    assert not (tmp_path / "out" / "systems" / "F" / "live").exists()
