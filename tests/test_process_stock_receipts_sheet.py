from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scripts.tools import process_stock_receipts_sheet as receipts


def test_summarize_token_rows_builds_order_key_counts() -> None:
    header = ["token_id", "seller_sku", "source_batch_id", "source_order_key"]
    rows = [
        ["SR-1-0001", "SKU-1", "SR-1", "ORDER-KEY-1"],
        ["SR-1-0002", "SKU-1", "SR-1", "ORDER-KEY-1"],
        ["SR-2-0001", "SKU-1", "SR-2", "ORDER-KEY-1"],
        ["SR-3-0001", "SKU-2", "SR-3", "ORDER-KEY-2"],
    ]

    token_ids, batch_counts, order_key_counts = receipts._summarize_token_rows(header, rows)

    assert len(token_ids) == 4
    assert batch_counts == {"SR-1": 2, "SR-2": 1, "SR-3": 1}
    key = ("ORDER-KEY-1", "SKU-1")
    assert key in order_key_counts
    assert int(order_key_counts[key]["count"]) == 3
    assert set(order_key_counts[key]["batch_ids"]) == {"SR-1", "SR-2"}


def test_build_batch_id_uses_sheet_row_for_split_shipments() -> None:
    intake_dt = receipts.parse_date_uk("05/06/2026")

    assert intake_dt is not None
    assert receipts.build_batch_id(intake_dt, {"SR-20260605-001"}, row_num=91) == "SR-20260605-ROW0091"


def test_split_shipment_batch_id_is_stable_when_tokens_already_exist() -> None:
    intake_dt = receipts.parse_date_uk("05/06/2026")

    assert intake_dt is not None
    assert (
        receipts.build_batch_id(intake_dt, {"SR-20260605-ROW0091"}, row_num=91)
        == "SR-20260605-ROW0091"
    )


def test_duplicate_batch_guard_should_ignore_applied_rows() -> None:
    row_statuses = [receipts.STATUS_APPLIED, receipts.STATUS_APPLIED, ""]
    batch_ids = ["SR-20260318-014", "SR-20260318-014", "SR-20260605-ROW0091"]
    active_seen: dict[str, int] = {}
    duplicates: list[str] = []

    for index, (status, batch_id) in enumerate(zip(row_statuses, batch_ids), start=2):
        if status in (receipts.STATUS_APPLIED, receipts.STATUS_CANCELLED):
            continue
        if batch_id in active_seen:
            duplicates.append(str(index))
        else:
            active_seen[batch_id] = index

    assert duplicates == []


def test_summary_columns_keep_empty_output_schema() -> None:
    df = pd.DataFrame([], columns=receipts.SUMMARY_COLUMNS)

    assert list(df.columns) == receipts.SUMMARY_COLUMNS
    assert len(df) == 0


def test_write_output_frame_sql_primary_exports_empty_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    out_csv = tmp_path / "stock_receipts_latest.csv"
    df = pd.DataFrame([], columns=receipts.SUMMARY_COLUMNS)

    result = receipts._write_output_frame(df, out_csv, receipts.SQL_TABLE_STOCK_RECEIPTS_LATEST)

    assert result["mode"] == "sql_primary_csv_export"
    assert result["csv_rows"] == 0
    assert result["sql_rows"] == 0
    assert pd.read_csv(out_csv, dtype=str).columns.tolist() == receipts.SUMMARY_COLUMNS
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        count = conn.execute(f"select count(*) from {receipts.SQL_TABLE_STOCK_RECEIPTS_LATEST}").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_write_output_frame_csv_mode_does_not_create_sql(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "sellerone.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(db_path))
    out_csv = tmp_path / "stock_receipt_summary.csv"
    df = pd.DataFrame([], columns=receipts.SUMMARY_COLUMNS)

    result = receipts._write_output_frame(df, out_csv, receipts.SQL_TABLE_STOCK_RECEIPT_SUMMARY)

    assert result["mode"] == "csv"
    assert result["csv_rows"] == 0
    assert result["sql_rows"] == 0
    assert result["sql_table"] == ""
    assert out_csv.exists()
    assert not db_path.exists()
