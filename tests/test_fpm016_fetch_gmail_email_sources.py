from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM010_check_acquisition_sources import check_acquisition_sources
from scripts.flows.F.price_list_manager.FPM011_import_ready_sources import import_ready_sources
from scripts.flows.F.price_list_manager.FPM016_fetch_gmail_email_sources import (
    GmailAttachment,
    fetch_gmail_email_sources,
)
from scripts.flows.F.price_list_manager._schemas import BATCH_ROW_COLUMNS, PRICE_LIST_BATCH_COLUMNS, SUPPLIER_REGISTRY_COLUMNS


def _write_registry(
    root: Path,
    folder: Path,
    *,
    active_flag: str = "1",
    supplier_id: str = "td_synnex",
    supplier_name: str = "TD Synnex",
    converter_id: str = "td_synnex",
) -> None:
    config_dir = root / "config" / "feeder" / "price_list_manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    with (config_dir / "suppliers.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLIER_REGISTRY_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "source_type": "email_attachment",
                "source_subtype": "daily_email",
                "source_url": "",
                "source_folder_path": str(folder),
                "existing_supplier_config_path": "",
                "converter_id": converter_id,
                "normal_refresh_days": "1",
                "minimum_rescan_days": "7",
                "large_file_flag": "1",
                "manual_request_required_flag": "0",
                "priority_band": "daily_email",
                "active_flag": active_flag,
                "notes": "test supplier",
            }
        )


def _td_zip_bytes() -> bytes:
    tsv_text = (
        "Product ID\tSKU\tBrand\tDescription\tCost Price\tSelling Price\tCurrency\tTimestamp\tStock Level\t"
        "Stock Date\tCategory Code\tAvailability\tCategory Description\tEnd User\tEAN\tSpecial\tDepartment\t"
        "Subcategory\tRestricted\tWeight (kg)\n"
        "P1\tTD-GMAIL-001\tTD Brand\tGmail ready item\t31.25\t35.00\tGBP\t2026-05-19\t8\t2026-05-19\t"
        "C1\tY\tToys\tN\t5012345678905\tN\tD\tS\tN\t1\n"
    )
    import io

    handle = io.BytesIO()
    with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("td_synnex_daily.tsv", tsv_text)
    return handle.getvalue()


def _xlsx_bytes() -> bytes:
    import io

    handle = io.BytesIO()
    with pd.ExcelWriter(handle, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "SKU": "TROP-001",
                    "Description": "Tropicana item",
                    "Barcode": "5012345678910",
                    "Cost": "4.25",
                }
            ]
        ).to_excel(writer, index=False, sheet_name="Stock")
    return handle.getvalue()


def _abgee_xlsx_bytes() -> bytes:
    import io

    handle = io.BytesIO()
    with pd.ExcelWriter(handle, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "Supply Code": "985 49830",
                    "Name": "Funko POP Leatherface",
                    "Barcode": "889698498302",
                    "CPU": "7.59",
                    "Available": "8",
                }
            ]
        ).to_excel(writer, index=False, sheet_name="ABGee")
    return handle.getvalue()


def test_fpm016_downloads_td_synnex_gmail_zip_then_imports_it(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    _write_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-19T09:00:00Z", check_remote=False)

    calls: list[dict[str, object]] = []

    def fake_fetcher(**kwargs) -> GmailAttachment:
        calls.append(kwargs)
        return GmailAttachment(
            message_id="msg-td-1",
            attachment_id="att-td-1",
            filename="td_synnex_daily.zip",
            message_ts_utc="2026-05-19T07:15:00Z",
            data=_td_zip_bytes(),
        )

    fetched = fetch_gmail_email_sources(
        root=tmp_path,
        supplier_id="td_synnex",
        fetched_at_utc="2026-05-19T09:01:00Z",
        fetcher=fake_fetcher,
    )
    imported = import_ready_sources(root=tmp_path, supplier_id="td_synnex", imported_at_utc="2026-05-19T09:02:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")
    batches = pd.read_csv(test_dir / "price_list_batches.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")

    assert fetched["fetched_sources"] == 1
    assert fetched["failed_sources"] == 0
    assert imported["imported_batches"] == 1
    assert list(batches.columns) == PRICE_LIST_BATCH_COLUMNS
    assert list(rows.columns) == BATCH_ROW_COLUMNS
    assert calls[0]["label_name"] == "TD Synnex"
    assert str(calls[0]["target_date"]) == "2026-05-19"
    assert acquisition.iloc[0]["source_state"] == "ready"
    assert acquisition.iloc[0]["latest_source_name"].endswith(".zip")
    assert "gmail_attachment_downloaded" in acquisition.iloc[0]["notes"]
    assert batches.iloc[0]["source_file_path"].endswith(".zip")
    assert rows.iloc[0]["supplier_sku"] == "TD-GMAIL-001"
    assert rows.iloc[0]["scan_eligibility"] == "scan_now"
    assert len(list((folder.parent / "Processed").glob("*.zip"))) == 1
    latest_gmail_health = health[health["check"] == "gmail_email_attachment_fetch_reconciliation"].iloc[-1]
    assert latest_gmail_health["status"] == "ok"
    assert latest_gmail_health["value"] == "1"


def test_fpm016_downloads_abgee_gmail_attachment_with_default_label_and_suffixes(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "ABGee" / "inbox"
    folder.mkdir(parents=True)
    _write_registry(
        tmp_path,
        folder,
        active_flag="0",
        supplier_id="abgee",
        supplier_name="ABGee",
        converter_id="abgee",
    )

    calls: list[dict[str, object]] = []

    def fake_fetcher(**kwargs) -> GmailAttachment:
        calls.append(kwargs)
        return GmailAttachment(
            message_id="msg-abgee",
            attachment_id="att-abgee",
            filename="ABGee price list.xlsx",
            message_ts_utc="2026-05-22T07:15:00Z",
            data=_abgee_xlsx_bytes(),
        )

    fetched = fetch_gmail_email_sources(
        root=tmp_path,
        supplier_id="abgee",
        fetched_at_utc="2026-05-22T09:00:00Z",
        fetcher=fake_fetcher,
    )
    imported = import_ready_sources(root=tmp_path, supplier_id="abgee", imported_at_utc="2026-05-22T09:01:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")

    assert fetched["email_sources"] == 1
    assert fetched["fetched_sources"] == 1
    assert fetched["failed_sources"] == 0
    assert imported["imported_batches"] == 1
    assert calls[0]["label_name"] == "ABGee"
    assert calls[0]["filename_query"] == ""
    assert calls[0]["allowed_suffixes"] == {".xlsx", ".xls", ".csv", ".zip"}
    assert calls[0]["lookback_days"] == 7
    assert acquisition.iloc[0]["source_location"] == "gmail_label:ABGee"
    assert acquisition.iloc[0]["latest_source_name"].endswith(".xlsx")
    assert rows.iloc[0]["supplier_id"] == "abgee"
    assert rows.iloc[0]["supplier_sku"] == "985 49830"
    assert rows.iloc[0]["barcode"] == "889698498302"
    assert rows.iloc[0]["unit_cost"] == "7.59"


def test_fpm016_records_waiting_when_abgee_has_no_today_attachment(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "ABGee" / "inbox"
    folder.mkdir(parents=True)
    _write_registry(
        tmp_path,
        folder,
        active_flag="0",
        supplier_id="abgee",
        supplier_name="ABGee",
        converter_id="abgee",
    )

    fetched = fetch_gmail_email_sources(
        root=tmp_path,
        supplier_id="abgee",
        fetched_at_utc="2026-05-22T09:05:00Z",
        fetcher=lambda **kwargs: None,
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")

    assert fetched["fetched_sources"] == 0
    assert fetched["skipped_sources"] == 1
    assert fetched["failed_sources"] == 0
    assert acquisition.iloc[0]["source_state"] == "waiting"
    assert "gmail_no_matching_attachment;label=ABGee" in acquisition.iloc[0]["notes"]


def test_fpm016_downloads_tropicana_gmail_xlsx_from_label(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "Tropicana Wholesale" / "inbox"
    folder.mkdir(parents=True)
    _write_registry(
        tmp_path,
        folder,
        active_flag="0",
        supplier_id="tropicana_wholesale",
        supplier_name="Tropicana Wholesale",
        converter_id="tropicana_wholesale",
    )

    fetched = fetch_gmail_email_sources(
        root=tmp_path,
        supplier_id="tropicana_wholesale",
        fetched_at_utc="2026-05-19T10:12:00Z",
        fetcher=lambda **kwargs: GmailAttachment(
            message_id="msg-tropicana",
            attachment_id="att-tropicana",
            filename="StockExport_190526_090831.xlsx",
            message_ts_utc="2026-05-19T08:08:32Z",
            data=_xlsx_bytes(),
        ),
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")

    assert fetched["email_sources"] == 1
    assert fetched["fetched_sources"] == 1
    assert fetched["failed_sources"] == 0
    assert acquisition.iloc[0]["supplier_id"] == "tropicana_wholesale"
    assert acquisition.iloc[0]["source_location"] == "gmail_label:Tropicana"
    assert acquisition.iloc[0]["latest_source_name"].endswith(".xlsx")
    assert list(folder.glob("*.xlsx"))


def test_fpm016_records_waiting_when_td_synnex_has_no_today_zip(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    _write_registry(tmp_path, folder)
    check_acquisition_sources(root=tmp_path, checked_at_utc="2026-05-19T09:10:00Z", check_remote=False)

    fetched = fetch_gmail_email_sources(
        root=tmp_path,
        supplier_id="td_synnex",
        fetched_at_utc="2026-05-19T09:11:00Z",
        fetcher=lambda **kwargs: None,
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")

    assert fetched["fetched_sources"] == 0
    assert fetched["skipped_sources"] == 1
    assert fetched["failed_sources"] == 0
    assert acquisition.iloc[0]["source_state"] == "waiting"
    assert acquisition.iloc[0]["operator_action"] == "Await email file"
    assert "gmail_no_matching_attachment" in acquisition.iloc[0]["notes"]


def test_fpm016_manual_supplier_fetch_can_use_parked_td_synnex_registry_row(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    _write_registry(tmp_path, folder, active_flag="0")

    fetched = fetch_gmail_email_sources(
        root=tmp_path,
        supplier_id="td_synnex",
        fetched_at_utc="2026-05-19T09:20:00Z",
        fetcher=lambda **kwargs: GmailAttachment(
            message_id="msg-td-parked",
            attachment_id="att-td-parked",
            filename="td_synnex_daily.zip",
            message_ts_utc="2026-05-19T08:15:00Z",
            data=_td_zip_bytes(),
        ),
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")

    assert fetched["email_sources"] == 1
    assert fetched["fetched_sources"] == 1
    assert fetched["failed_sources"] == 0
    assert acquisition.iloc[0]["supplier_id"] == "td_synnex"
    assert acquisition.iloc[0]["source_state"] == "ready"
    assert acquisition.iloc[0]["latest_source_path"].startswith(str(folder))


def test_fpm016_parked_td_synnex_manual_fetch_then_import_uses_registry_converter(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    _write_registry(tmp_path, folder, active_flag="0")

    fetch_gmail_email_sources(
        root=tmp_path,
        supplier_id="td_synnex",
        fetched_at_utc="2026-05-19T09:30:00Z",
        fetcher=lambda **kwargs: GmailAttachment(
            message_id="msg-td-parked-import",
            attachment_id="att-td-parked-import",
            filename="td_synnex_daily.zip",
            message_ts_utc="2026-05-19T08:20:00Z",
            data=_td_zip_bytes(),
        ),
    )
    imported = import_ready_sources(root=tmp_path, supplier_id="td_synnex", imported_at_utc="2026-05-19T09:31:00Z")

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    rows = pd.read_csv(test_dir / "batch_rows.csv", dtype=str).fillna("")

    assert imported["imported_batches"] == 1
    assert imported["failed_sources"] == 0
    assert rows.iloc[0]["supplier_sku"] == "TD-GMAIL-001"
    assert rows.iloc[0]["scan_eligibility"] == "scan_now"


def test_fpm016_reuses_existing_same_hash_zip_in_inbox(tmp_path: Path) -> None:
    folder = tmp_path / "price_files" / "TD Synnex" / "inbox"
    folder.mkdir(parents=True)
    _write_registry(tmp_path, folder, active_flag="0")
    existing = folder / "798126_A_20260519_20260519T090242Z_697fd87dcd.zip"
    existing.write_bytes(_td_zip_bytes())

    fetched = fetch_gmail_email_sources(
        root=tmp_path,
        supplier_id="td_synnex",
        fetched_at_utc="2026-05-19T09:40:00Z",
        fetcher=lambda **kwargs: GmailAttachment(
            message_id="msg-td-existing",
            attachment_id="att-td-existing",
            filename="td_synnex_daily.zip",
            message_ts_utc="2026-05-19T08:40:00Z",
            data=_td_zip_bytes(),
        ),
    )

    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    acquisition = pd.read_csv(test_dir / "source_acquisition_status.csv", dtype=str).fillna("")

    assert fetched["fetched_sources"] == 1
    assert len(list(folder.glob("*.zip"))) == 1
    assert acquisition.iloc[0]["latest_source_path"] == str(existing)
