from __future__ import annotations

import csv
import json
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

from scripts.flows.F.price_list_manager.FPM010_check_acquisition_sources import check_acquisition_sources
from scripts.flows.F.price_list_manager.FPM014_fetch_api_sources import fetch_api_sources
from scripts.flows.F.price_list_manager._schemas import SOURCE_ACQUISITION_COLUMNS, SUPPLIER_REGISTRY_COLUMNS


def _write_registry(root: Path, *, supplier_id: str = "heo") -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    if supplier_id == "clf":
        row = {
            "supplier_id": "clf",
            "supplier_name": "CLF",
            "source_type": "api_pull",
            "source_subtype": "api",
            "source_url": "http://services.clfdistribution.com:8080/CLFWebOrdering/WebOrdering.asmx",
            "source_folder_path": "",
            "existing_supplier_config_path": "",
            "converter_id": "clf",
            "normal_refresh_days": "1",
            "minimum_rescan_days": "1",
            "large_file_flag": "0",
            "manual_request_required_flag": "0",
            "priority_band": "api",
            "active_flag": "1",
            "notes": "test supplier",
        }
    else:
        row = {
            "supplier_id": "heo",
            "supplier_name": "Heo",
            "source_type": "api_pull",
            "source_subtype": "api",
            "source_url": "https://integrate.heo.com/retailer-api/v1/catalog",
            "source_folder_path": "",
            "existing_supplier_config_path": "",
            "converter_id": "heo",
            "normal_refresh_days": "1",
            "minimum_rescan_days": "1",
            "large_file_flag": "0",
            "manual_request_required_flag": "0",
            "priority_band": "api",
            "active_flag": "1",
            "notes": "test supplier",
        }
    with (config_dir / "suppliers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def test_fpm014_fetches_api_source_and_marks_it_ready(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    secret_dir = tmp_path / "secrets" / "price_list_manager"
    secret_dir.mkdir(parents=True)
    (secret_dir / "heo_api.json").write_text(
        json.dumps({"username": "user", "password": "pass", "base_url": "https://example.test/api"}),
        encoding="utf-8",
    )
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-04-30T15:00:00Z", check_remote=False)

    def fake_fetch(destination: Path, **kwargs: object) -> dict[str, object]:
        assert kwargs["username"] == "user"
        assert kwargs["password"] == "pass"
        assert kwargs["base_url"] == "https://example.test/api"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "productNumber,barcodes,basePricePerUnit,vatType,Supplier,supplierTitle\n"
            "H001,4005555000001,12.35,20,Heo,Board Game\n",
            encoding="utf-8",
        )
        return {"ok": True, "notes": "products=1;prices=1;expanded_rows=1", "bytes": destination.stat().st_size}

    summary = fetch_api_sources(
        root=tmp_path,
        supplier_id="heo",
        fetched_at_utc="2026-04-30T15:01:00Z",
        timeout_seconds=10,
        fetch_func=fake_fetch,
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")
    row = acquisition.iloc[0]
    latest_path = Path(row["latest_source_path"])

    assert summary["api_sources"] == 1
    assert summary["fetched_sources"] == 1
    assert summary["failed_sources"] == 0
    assert list(acquisition.columns) == SOURCE_ACQUISITION_COLUMNS
    assert row["source_state"] == "ready"
    assert row["status"] == "ok"
    assert row["operator_action"] == "Import latest file"
    assert latest_path.exists()
    assert latest_path.parent.name == "Inbox"
    assert "sha1=" in row["notes"]


def test_fpm014_requires_credentials(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-04-30T15:00:00Z", check_remote=False)

    summary = fetch_api_sources(root=tmp_path, supplier_id="heo", fetched_at_utc="2026-04-30T15:01:00Z")
    acquisition = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "source_acquisition_status.csv",
        dtype=str,
    ).fillna("")

    assert summary["failed_sources"] == 1
    assert acquisition.iloc[0]["source_state"] == "error"
    assert acquisition.iloc[0]["operator_action"] == "Add API credentials"


def test_fpm014_fetches_token_based_api_source(tmp_path: Path) -> None:
    _write_registry(tmp_path, supplier_id="clf")
    secret_dir = tmp_path / "secrets" / "price_list_manager"
    secret_dir.mkdir(parents=True)
    (secret_dir / "clf_api.json").write_text(
        json.dumps({"auth_token": "token-123", "base_url": "https://example.test/soap"}),
        encoding="utf-8",
    )
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-04-30T16:00:00Z", check_remote=False)

    def fake_fetch(destination: Path, **kwargs: object) -> dict[str, object]:
        assert kwargs["auth_token"] == "token-123"
        assert kwargs["base_url"] == "https://example.test/soap"
        assert "username" in kwargs
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("SKU,Barcode,Cost,VAT,CLF\nABC1,5012345678901,1.23,20,CLF\n", encoding="utf-8")
        return {"ok": True, "notes": "skus=1;rows=1;blank_barcode_rows=0", "bytes": destination.stat().st_size}

    summary = fetch_api_sources(
        root=tmp_path,
        supplier_id="clf",
        fetched_at_utc="2026-04-30T16:01:00Z",
        fetch_func=fake_fetch,
    )

    acquisition = pd.read_csv(
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "source_acquisition_status.csv",
        dtype=str,
    ).fillna("")

    assert summary["fetched_sources"] == 1
    assert summary["failed_sources"] == 0
    assert acquisition.iloc[0]["source_state"] == "ready"
    assert acquisition.iloc[0]["operator_action"] == "Import latest file"


def test_fpm014_requires_acquisition_status(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="source_acquisition_status.csv is required"):
        fetch_api_sources(root=tmp_path)
