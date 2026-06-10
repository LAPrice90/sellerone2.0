from __future__ import annotations

import sqlite3
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

from scripts.flows.B import B003_run_financial_events_level3 as b003


def test_b003_official_output_sql_primary_writes_table_and_csv(monkeypatch, tmp_path: Path) -> None:
    sqlite_path = tmp_path / "pilot.sqlite3"
    out_path = tmp_path / "out" / "financial_events_level3_official.csv"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))
    df = pd.DataFrame(
        [
            {
                "Date": "2026-04-28T10:00:00Z",
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "Price_Total": "10.00",
            }
        ]
    )

    result = b003._write_output_frame(df, out_path, b003.SQL_TABLE_OFFICIAL)

    assert result["sql_rows"] == 1
    built = pd.read_csv(out_path, dtype=str).fillna("")
    assert built.loc[0, "Order ID"] == "ORDER-1"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT date, order_id, sku, price_total FROM b_financial_events_level3_official"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("2026-04-28T10:00:00Z", "ORDER-1", "SKU-A", "10.00")]


def test_b003_official_output_csv_mode_writes_only_csv(monkeypatch, tmp_path: Path) -> None:
    out_path = tmp_path / "out" / "financial_events_level3_official.csv"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")
    df = pd.DataFrame([{"Order ID": "ORDER-CSV", "SKU": "SKU-C"}])

    result = b003._write_output_frame(df, out_path, b003.SQL_TABLE_OFFICIAL)

    assert result["sql_rows"] == 0
    built = pd.read_csv(out_path, dtype=str).fillna("")
    assert built.loc[0, "Order ID"] == "ORDER-CSV"


def test_b003_save_marker_writes_normalised_utc_marker(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "financial_events_level3_last_posted.txt"
    monkeypatch.setattr(b003, "MARKER_PATH", marker_path)

    b003._save_marker("2026-05-26T17:31:36+00:00")

    assert marker_path.read_text(encoding="utf-8") == "2026-05-26T17:31:36Z"


def test_b003_save_marker_retries_transient_windows_replace_error(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "financial_events_level3_last_posted.txt"
    real_replace = b003.os.replace
    attempts = {"count": 0}
    monkeypatch.setattr(b003, "MARKER_PATH", marker_path)

    def flaky_replace(src: Path, dst: Path) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError(22, "Invalid argument")
        real_replace(src, dst)

    monkeypatch.setattr(b003.os, "replace", flaky_replace)

    b003._save_marker("2026-05-26T17:31:36Z")

    assert attempts["count"] == 2
    assert marker_path.read_text(encoding="utf-8") == "2026-05-26T17:31:36Z"


def test_b003_save_marker_raises_after_repeated_replace_errors(monkeypatch, tmp_path: Path) -> None:
    marker_path = tmp_path / "out" / "financial_events_level3_last_posted.txt"
    monkeypatch.setattr(b003, "MARKER_PATH", marker_path)
    monkeypatch.setattr(
        b003.os,
        "replace",
        lambda src, dst: (_ for _ in ()).throw(OSError(22, "Invalid argument")),
    )

    with pytest.raises(OSError):
        b003._save_marker("2026-05-26T17:31:36Z")
