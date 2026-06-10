from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import f_contract_table_name, read_f_contract_df, write_f_contract_df
from scripts.flows.F.price_list_manager.FPM129_storage_drift_guard import run_storage_drift_check


def _active_rows(count: int, *, updated: str = "2026-05-21T12:00:00Z") -> pd.DataFrame:
    rows = []
    for index in range(1, count + 1):
        rows.append(
            {
                "run_id": "run-1",
                "supplier_id": "supplier-a",
                "supplier_name": "Supplier A",
                "row_key": f"row-{index}",
                "supplier_sku": f"SKU-{index}",
                "barcode": f"50000000000{index:02d}",
                "supplier_title": f"Product {index}",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": updated,
            }
        )
    return pd.DataFrame(rows)


def _overwrite_active_csv(root: Path, count: int, *, updated: str = "2026-05-21T13:00:00Z") -> None:
    csv_path = root / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    _active_rows(count, updated=updated).to_csv(csv_path, index=False)


def test_storage_drift_detector_reports_mismatch_when_sql_csv_diverge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    root = tmp_path / "repo"
    write_f_contract_df(root, "supplier_price_list_active_run", _active_rows(1))
    _overwrite_active_csv(root, 2)

    summary = run_storage_drift_check(
        root=root,
        contracts=["supplier_price_list_active_run"],
        observed_utc="2026-05-21T14:00:00Z",
        apply=False,
        require_sql_mode=True,
    )

    row = summary["rows"][0]
    assert summary["status"] == "drift_found"
    assert row["status_before"] == "csv_newer_drift"
    assert row["csv_rows"] == "2"
    assert row["sql_rows_before"] == "1"


def test_storage_drift_apply_updates_sql_and_clears_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    root = tmp_path / "repo"
    write_f_contract_df(root, "supplier_price_list_active_run", _active_rows(1))
    _overwrite_active_csv(root, 3)

    summary = run_storage_drift_check(
        root=root,
        contracts=["supplier_price_list_active_run"],
        observed_utc="2026-05-21T14:05:00Z",
        apply=True,
        require_sql_mode=True,
        backup=True,
    )

    assert summary["status"] == "reconciled"
    assert summary["reconciled_rows"] == 1
    assert summary["rows"][0]["sql_rows_after"] == "3"
    assert Path(str(summary["backup_dir"])).exists()
    assert len(read_f_contract_df(root, "supplier_price_list_active_run").index) == 3

    with sqlite3.connect(tmp_path / "sellerone.sqlite3") as conn:
        table = f_contract_table_name("supplier_price_list_active_run")
        sql_rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    assert sql_rows == 3


def test_storage_drift_apply_blocks_when_sql_is_newer_than_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    root = tmp_path / "repo"
    sql_rows = _active_rows(3)
    sql_rows.loc[1:, "source_seen_at_utc"] = "2026-05-25T12:00:00Z"
    write_f_contract_df(root, "supplier_price_list_active_run", sql_rows)
    _overwrite_active_csv(root, 1, updated="2026-05-21T12:00:00Z")

    summary = run_storage_drift_check(
        root=root,
        contracts=["supplier_price_list_active_run"],
        observed_utc="2026-05-26T12:00:00Z",
        apply=True,
        require_sql_mode=True,
        backup=True,
    )

    assert summary["status"] == "blocked_storage_drift"
    assert summary["blocked_rows"] == 1
    assert summary["rows"][0]["status_before"] == "unsafe_sql_newer_drift"
    assert summary["rows"][0]["action"] == "blocked"
    csv_path = root / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv"
    assert len(pd.read_csv(csv_path, dtype=str).fillna("").index) == 1


def test_storage_drift_ok_check_does_not_create_full_backup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    root = tmp_path / "repo"
    write_f_contract_df(root, "supplier_price_list_active_run", _active_rows(2))

    summary = run_storage_drift_check(
        root=root,
        contracts=["supplier_price_list_active_run"],
        observed_utc="2026-05-21T14:10:00Z",
        apply=True,
        require_sql_mode=True,
        backup=True,
    )

    assert summary["status"] == "ok"
    assert summary["backup_dir"] == ""
    assert not (root / "out" / "backups").exists()
    assert summary["rows"][0]["backup_dir"] == ""


def test_storage_drift_retention_prunes_empty_and_old_backups(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    monkeypatch.setenv("FPM_STORAGE_DRIFT_BACKUP_MAX_DIRS", "1")
    root = tmp_path / "repo"
    write_f_contract_df(root, "supplier_price_list_active_run", _active_rows(2))
    backup_root = root / "out" / "backups"
    old_backup = backup_root / "f_storage_drift_reconcile_20260520T000000Z"
    newest_backup = backup_root / "f_storage_drift_reconcile_20260521T000000Z"
    empty_backup = backup_root / "f_storage_drift_reconcile_20260522T000000Z"
    old_backup.mkdir(parents=True)
    newest_backup.mkdir(parents=True)
    empty_backup.mkdir(parents=True)
    (old_backup / "sellerone_dev.sqlite3").write_text("old", encoding="ascii")
    (newest_backup / "sellerone_dev.sqlite3").write_text("new", encoding="ascii")
    os.utime(old_backup, (1000, 1000))
    os.utime(newest_backup, (2000, 2000))
    os.utime(empty_backup, (3000, 3000))

    summary = run_storage_drift_check(
        root=root,
        contracts=["supplier_price_list_active_run"],
        observed_utc="2026-05-21T14:15:00Z",
        apply=True,
        require_sql_mode=True,
        backup=True,
    )

    assert summary["status"] == "ok"
    assert newest_backup.exists()
    assert not old_backup.exists()
    assert not empty_backup.exists()
    assert summary["backup_retention"]["non_empty_after"] == 1
    assert summary["backup_retention"]["pruned_dirs"] == 2
