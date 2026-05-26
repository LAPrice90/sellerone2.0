from __future__ import annotations

import sqlite3

import pandas as pd

from scripts.flows.B import B014_build_token_daily_checklist as b014


def test_b014_sql_primary_writes_checklist_table_and_csv_export(monkeypatch, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    tests_path = out_dir / "token_tests_daily.csv"
    events_path = out_dir / "token_events.csv"
    recon_path = out_dir / "token_stock_recon_mismatches.csv"
    checklist_path = out_dir / "token_daily_checklist.csv"
    sqlite_path = tmp_path / "pilot.sqlite3"

    pd.DataFrame(
        [
            {"check": "example_pass", "status": "PASS"},
            {"check": "example_warn", "status": "WARN"},
            {"check": "example_fail", "status": "FAIL"},
        ]
    ).to_csv(tests_path, index=False)
    pd.DataFrame(
        [
            {"event_ts": "2026-04-03T12:01:00Z", "event_type": "Allocation"},
        ]
    ).to_csv(events_path, index=False)
    pd.DataFrame(columns=["status"]).to_csv(recon_path, index=False)

    monkeypatch.setattr(b014, "TESTS_CSV", tests_path)
    monkeypatch.setattr(b014, "EVENTS_CSV", events_path)
    monkeypatch.setattr(b014, "RECON_MISMATCH_CSV", recon_path)
    monkeypatch.setattr(b014, "OUT_CHECKLIST", checklist_path)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    b014.main()

    checklist = pd.read_csv(checklist_path, dtype=str).fillna("")
    values = dict(zip(checklist["check"], checklist["value"]))
    assert values["tests_fail_count"] == "1"
    assert values["tests_warn_count"] == "1"
    assert values["recon_mismatch_count"] == "0"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            'SELECT "check", "value" FROM b_token_daily_checklist'
        ).fetchall()
    finally:
        connection.close()

    sql_values = dict(rows)
    assert sql_values["tests_fail_count"] == "1"
    assert sql_values["tests_warn_count"] == "1"
    assert sql_values["recon_mismatch_count"] == "0"
