from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import f_contract_columns, write_f_contract_df
from scripts.flows.F._schemas import get_f_output_contract
from scripts.one_off.F042_recover_sql_newer_storage_drift import run_sql_newer_recovery


CONTRACT = "feeder_legacy_chart_daily_raw_live"


def _chart_rows(count: int) -> pd.DataFrame:
    rows = []
    for index in range(1, count + 1):
        observed = "2026-05-21T12:00:00Z" if index == 1 else "2026-05-25T11:00:00Z"
        rows.append(
            {
                "observed_utc": observed,
                "run_id": "run-1",
                "supplier_id": "supplier-a",
                "supplier_name": "Supplier A",
                "supplier_sku": f"SKU-{index}",
                "candidate_id": f"candidate-{index}",
                "asin": f"B00000000{index}",
                "day": f"2026-05-{index:02d}",
                "chart_source": "buy_box",
                "amazon_price_raw": "10.00",
                "fba_price_raw": "11.00",
                "fbm_price_raw": "12.00",
                "buy_box_price_raw": "9.50",
                "bsr_raw": str(1000 + index),
            }
        )
    return pd.DataFrame(rows)


def _overwrite_csv(root: Path, rows: pd.DataFrame) -> Path:
    path = root / get_f_output_contract(CONTRACT).rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows.copy()
    for column in f_contract_columns(CONTRACT):
        if column not in rows.columns:
            rows[column] = ""
    rows = rows[f_contract_columns(CONTRACT)]
    rows.to_csv(path, index=False)
    return path


def test_sql_newer_recovery_dry_run_reports_clean_sql_authority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    root = tmp_path / "repo"
    sql_rows = _chart_rows(3)
    write_f_contract_df(root, CONTRACT, sql_rows)
    _overwrite_csv(root, sql_rows.head(1))

    summary = run_sql_newer_recovery(
        root=root,
        contract_name=CONTRACT,
        observed_utc="2026-05-26T12:00:00Z",
        apply=False,
    )

    row = summary["summary_row"]
    assert summary["status"] == "ready_sql_newer_recovery"
    assert row["csv_rows"] == "1"
    assert row["sql_rows"] == "3"
    assert row["sql_only_exact_rows"] == "2"
    assert row["csv_only_exact_rows"] == "0"
    assert Path(str(summary["summary_path"])).exists()
    assert Path(str(summary["diff_path"])).exists()

    with Path(str(summary["diff_path"])).open("r", newline="", encoding="utf-8") as handle:
        diff_rows = list(csv.DictReader(handle))
    assert {row["side"] for row in diff_rows} == {"sql_only"}


def test_sql_newer_recovery_apply_rebuilds_csv_from_sql_with_backup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    root = tmp_path / "repo"
    sql_rows = _chart_rows(3)
    write_f_contract_df(root, CONTRACT, sql_rows)
    csv_path = _overwrite_csv(root, sql_rows.head(1))

    summary = run_sql_newer_recovery(
        root=root,
        contract_name=CONTRACT,
        observed_utc="2026-05-26T12:05:00Z",
        apply=True,
    )

    assert summary["status"] == "applied_sql_to_csv_recovery"
    backup_dir = Path(str(summary["summary_row"]["backup_dir"]))
    assert backup_dir.exists()
    assert (backup_dir / "csv" / csv_path.relative_to(root)).exists()
    rebuilt = pd.read_csv(csv_path, dtype=str).fillna("")
    assert len(rebuilt.index) == 3
    assert list(rebuilt.columns) == f_contract_columns(CONTRACT)


def test_sql_newer_recovery_blocks_mixed_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    root = tmp_path / "repo"
    sql_rows = _chart_rows(3)
    write_f_contract_df(root, CONTRACT, sql_rows)
    csv_rows = pd.concat(
        [
            sql_rows.head(1),
            _chart_rows(1).assign(candidate_id="csv-only", supplier_sku="CSV-ONLY", observed_utc="2026-05-21T12:00:00Z"),
        ],
        ignore_index=True,
    )
    _overwrite_csv(root, csv_rows)

    summary = run_sql_newer_recovery(
        root=root,
        contract_name=CONTRACT,
        observed_utc="2026-05-26T12:10:00Z",
        apply=True,
    )

    assert summary["status"] == "blocked_apply_not_safe"
    assert summary["summary_row"]["csv_only_exact_rows"] == "1"
    live_csv = pd.read_csv(root / get_f_output_contract(CONTRACT).rel_path, dtype=str).fillna("")
    assert len(live_csv.index) == 2


def test_sql_newer_recovery_refuses_unknown_or_unapproved_contract(tmp_path: Path) -> None:
    summary = run_sql_newer_recovery(
        root=tmp_path,
        contract_name="supplier_price_list_active_run",
        observed_utc="2026-05-26T12:15:00Z",
        apply=True,
    )

    assert summary["status"] == "blocked_contract_not_approved"
