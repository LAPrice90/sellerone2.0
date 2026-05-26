from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.core.storage import write_dataframe_with_sql_compat
from scripts.one_off.P007_validate_sql_rollback_exports import validate_exports


def test_validate_exports_passes_matching_sql_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    csv_path = tmp_path / "out" / "demo.csv"
    df = pd.DataFrame([{"seller-sku": "SKU-1", "Total Quantity": "3"}])
    write_dataframe_with_sql_compat(df, csv_path, "demo_table")

    result = validate_exports(
        sqlite_path=tmp_path / "sellerone.sqlite3",
        output_dir=tmp_path / "exports",
        targets={"demo_table": "out/demo.csv"},
        root=tmp_path,
    )

    assert result.status == "passed"
    assert result.pass_count == 1
    assert result.fail_count == 0
    assert (result.export_dir / "files" / "out" / "demo.csv").exists()


def test_validate_exports_fails_on_hash_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    csv_path = tmp_path / "out" / "demo.csv"
    write_dataframe_with_sql_compat(pd.DataFrame([{"sku": "SKU-1"}]), csv_path, "demo_table")
    pd.DataFrame([{"sku": "SKU-2"}]).to_csv(csv_path, index=False)

    result = validate_exports(
        sqlite_path=tmp_path / "sellerone.sqlite3",
        output_dir=tmp_path / "exports",
        targets={"demo_table": "out/demo.csv"},
        root=tmp_path,
    )

    assert result.status == "failed"
    assert result.fail_count == 1


def test_validate_exports_uses_csv_header_when_metadata_is_absent(tmp_path: Path) -> None:
    import sqlite3

    csv_path = tmp_path / "out" / "demo.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"seller-sku": "SKU-1"}]).to_csv(csv_path, index=False)
    conn = sqlite3.connect(tmp_path / "sellerone.sqlite3")
    try:
        conn.execute("create table demo_table (seller_sku text)")
        conn.execute("insert into demo_table (seller_sku) values (?)", ["SKU-1"])
        conn.commit()
    finally:
        conn.close()

    result = validate_exports(
        sqlite_path=tmp_path / "sellerone.sqlite3",
        output_dir=tmp_path / "exports",
        targets={"demo_table": "out/demo.csv"},
        root=tmp_path,
    )

    assert result.status == "passed"
