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

from scripts.flows.F.price_list_manager.FPM010_check_acquisition_sources import check_acquisition_sources
from scripts.flows.F.price_list_manager.FPM013_download_ready_url_sources import (
    _download_request_headers,
    download_ready_url_sources,
)
from scripts.flows.F.price_list_manager._schemas import SOURCE_ACQUISITION_COLUMNS, SUPPLIER_REGISTRY_COLUMNS


def _write_registry(root: Path) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    with (config_dir / "suppliers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://example.test/product.csv",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "stax",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "1",
                "manual_request_required_flag": "0",
                "priority_band": "api",
                "active_flag": "1",
                "notes": "test supplier",
            }
        )


def test_fpm013_downloads_csv_link_and_marks_it_ready(tmp_path: Path) -> None:
    _write_registry(tmp_path)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-04-30T14:00:00Z", check_remote=False)

    def fake_download(url: str, destination: Path, timeout_seconds: int) -> dict[str, object]:
        assert url == "https://example.test/product.csv"
        assert timeout_seconds == 10
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("sku,barcode,cost\nS1,5012345678901,1.23\n", encoding="utf-8")
        return {"ok": True, "notes": "http_status=200;content_type=text/csv", "bytes": destination.stat().st_size}

    summary = download_ready_url_sources(
        root=tmp_path,
        supplier_id="stax",
        downloaded_at_utc="2026-04-30T14:01:00Z",
        timeout_seconds=10,
        download_func=fake_download,
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")
    row = acquisition.iloc[0]
    latest_path = Path(row["latest_source_path"])

    assert summary["download_ready_sources"] == 1
    assert summary["downloaded_sources"] == 1
    assert summary["failed_sources"] == 0
    assert list(acquisition.columns) == SOURCE_ACQUISITION_COLUMNS
    assert row["source_state"] == "ready"
    assert row["status"] == "ok"
    assert row["operator_action"] == "Import latest file"
    assert latest_path.exists()
    assert latest_path.parent.name == "Inbox"
    assert "sha1=" in row["notes"]


def test_fpm013_requires_acquisition_status(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="source_acquisition_status.csv is required"):
        download_ready_url_sources(root=tmp_path)


def test_fpm013_uses_we_stock_lots_cookie_without_storing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WE_STOCK_LOTS_COOKIE", "sessionid=secret")

    headers = _download_request_headers("https://westocklots.com/api/export/stocklist/?format=csv")

    assert headers["Cookie"] == "sessionid=secret"
    assert headers["User-Agent"] == "SellerOne-FPM/1.0"
