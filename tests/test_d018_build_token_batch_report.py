from __future__ import annotations

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

from scripts.flows.D import D018_build_token_batch_report as d018


def _write_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "source_batch_id": "BATCH-1",
                "status": "allocated",
                "return_order_id": "",
                "return_date": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
                "allocated_order_id": "ORDER-1",
            },
            {
                "source_batch_id": "BATCH-1",
                "status": "available",
                "return_order_id": "",
                "return_date": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
                "allocated_order_id": "",
            },
        ]
    ).to_csv(path, index=False)


def test_d018_build_token_batch_report_writes_daily_and_weekly(tmp_path: Path) -> None:
    ledger_path = tmp_path / "out" / "token_ledger_live.csv"
    report_dir = tmp_path / "out" / "reports"
    _write_ledger(ledger_path)

    result = d018.build_token_batch_report(
        ledger_path=ledger_path,
        report_dir=report_dir,
        stamp="2026-05-26",
    )

    assert result["status"] == "success"
    assert result["batches"] == 1
    assert result["rows"] == 1
    daily = pd.read_csv(report_dir / "token_batch_daily_report_2026-05-26.csv", dtype=str).fillna("")
    weekly = pd.read_csv(report_dir / "token_batch_weekly_log.csv", dtype=str).fillna("")
    assert daily.loc[0, "batch_id"] == "BATCH-1"
    assert daily.loc[0, "tokens_total"] == "2"
    assert weekly.loc[0, "report_date"] == "2026-05-26"


def test_d018_safe_to_csv_retries_transient_windows_replace_error(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "token_batch_weekly_log.csv"
    real_replace = d018.os.replace
    attempts = {"count": 0}

    def flaky_replace(src: Path, dst: Path) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError(22, "Invalid argument")
        real_replace(src, dst)

    monkeypatch.setattr(d018.os, "replace", flaky_replace)

    d018._safe_to_csv(pd.DataFrame([{"batch_id": "BATCH-1"}]), output_path)

    assert attempts["count"] == 2
    assert output_path.exists()


def test_d018_safe_to_csv_raises_after_repeated_replace_errors(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "token_batch_weekly_log.csv"
    monkeypatch.setattr(
        d018.os,
        "replace",
        lambda src, dst: (_ for _ in ()).throw(OSError(22, "Invalid argument")),
    )

    with pytest.raises(OSError):
        d018._safe_to_csv(pd.DataFrame([{"batch_id": "BATCH-1"}]), output_path)
