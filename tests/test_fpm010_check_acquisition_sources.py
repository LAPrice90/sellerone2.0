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

from scripts.flows.F.price_list_manager.FPM010_check_acquisition_sources import (
    _remote_response_is_price_file,
    check_acquisition_sources,
)
from scripts.flows.F.price_list_manager._schemas import SOURCE_ACQUISITION_COLUMNS, SUPPLIER_REGISTRY_COLUMNS


def _supplier_row(
    *,
    supplier_id: str,
    supplier_name: str,
    source_type: str,
    source_subtype: str,
    source_url: str = "",
    source_folder_path: str = "",
) -> dict[str, str]:
    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "source_type": source_type,
        "source_subtype": source_subtype,
        "source_url": source_url,
        "source_folder_path": source_folder_path,
        "existing_supplier_config_path": "",
        "converter_id": supplier_id,
        "normal_refresh_days": "1",
        "minimum_rescan_days": "1",
        "large_file_flag": "0",
        "manual_request_required_flag": "1" if source_type in {"manual_request", "manual_download"} else "0",
        "priority_band": "test",
        "active_flag": "1",
        "notes": "test supplier",
    }


def _write_registry(root: Path, rows: list[dict[str, str]]) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    with (config_dir / "suppliers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_fpm010_checks_manual_email_api_and_csv_link_states(tmp_path: Path) -> None:
    bliss_folder = tmp_path / "price_files" / "Bliss Distribution" / "inbox"
    td_folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    bliss_folder.mkdir(parents=True)
    td_folder.mkdir(parents=True)
    (bliss_folder / "bliss_price_list.csv").write_text("sku,barcode,cost\nA,5012345678901,1.23\n", encoding="utf-8")
    _write_registry(
        tmp_path,
        [
            _supplier_row(
                supplier_id="bliss_distribution",
                supplier_name="Bliss Distribution",
                source_type="manual_request",
                source_subtype="email_request",
                source_folder_path=str(bliss_folder),
            ),
            _supplier_row(
                supplier_id="td_synnex",
                supplier_name="TD Synnex",
                source_type="email_attachment",
                source_subtype="daily_email",
                source_folder_path=str(td_folder),
            ),
            _supplier_row(
                supplier_id="stax",
                supplier_name="Stax",
                source_type="api_pull",
                source_subtype="api",
            ),
            _supplier_row(
                supplier_id="we_stock_lots",
                supplier_name="We Stock Lots",
                source_type="api_pull",
                source_subtype="csv_link",
            ),
            _supplier_row(
                supplier_id="shure_cosmetics",
                supplier_name="Shure Cosmetics",
                source_type="api_pull",
                source_subtype="csv_link",
                source_url="https://example.test/price.csv",
            ),
        ],
    )

    summary = check_acquisition_sources(
        root=tmp_path,
        checked_at_utc="2026-04-30T10:00:00Z",
        check_remote=False,
    )

    assert summary["status"] == "success"
    assert summary["supplier_rows"] == 5
    assert summary["ready_rows"] == 3
    assert summary["waiting_rows"] == 1
    assert summary["config_needed_rows"] == 1
    assert summary["fail_rows"] == 0

    path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "source_acquisition_status.csv"
    acquisition = pd.read_csv(path, dtype=str).fillna("")
    assert list(acquisition.columns) == SOURCE_ACQUISITION_COLUMNS
    by_supplier = acquisition.set_index("supplier_id")
    assert by_supplier.loc["bliss_distribution", "source_state"] == "ready"
    assert by_supplier.loc["bliss_distribution", "latest_source_name"] == "bliss_price_list.csv"
    assert by_supplier.loc["bliss_distribution", "operator_action"] == "Import latest file"
    assert by_supplier.loc["td_synnex", "source_state"] == "waiting"
    assert by_supplier.loc["td_synnex", "operator_action"] == "Await email file"
    assert by_supplier.loc["stax", "source_state"] == "green"
    assert by_supplier.loc["we_stock_lots", "source_state"] == "config_needed"
    assert by_supplier.loc["we_stock_lots", "operator_action"] == "Add CSV link"
    assert by_supplier.loc["shure_cosmetics", "source_state"] == "download_ready"
    assert by_supplier.loc["shure_cosmetics", "notes"] == "remote_check_skipped"


def test_fpm010_requires_registry(tmp_path: Path) -> None:
    try:
        check_acquisition_sources(root=tmp_path, check_remote=False)
    except FileNotFoundError as exc:
        assert "supplier registry missing or empty" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_fpm010_rejects_login_html_as_remote_price_file() -> None:
    ok, reason = _remote_response_is_price_file(
        content_type="text/html",
        sample=b"<!doctype html><html><title>Login</title><body>Please sign in. Resellers must log-in to view prices.</body></html>",
    )

    assert ok is False
    assert reason == "auth_required_html_response"


def test_fpm010_accepts_csv_like_remote_response() -> None:
    ok, reason = _remote_response_is_price_file(
        content_type="text/csv;charset=UTF-8",
        sample=b"sku,barcode,cost\nA,5012345678901,1.23\n",
    )

    assert ok is True
    assert reason == "price_file_like_response"
