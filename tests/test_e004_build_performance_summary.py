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

from scripts.flows.E import E004_build_performance_summary as e004


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    monkeypatch.setattr(e004, "OUT", out)
    monkeypatch.setattr(e004, "VELOCITY", out / "sku_sales_velocity.csv")
    monkeypatch.setattr(e004, "ROI", out / "sku_roi_snapshot.csv")
    monkeypatch.setattr(e004, "RESTOCK", out / "sku_restock_signals.csv")
    monkeypatch.setattr(e004, "OUT_SUMMARY", out / "sku_performance_summary.csv")
    monkeypatch.setattr(e004, "TOKEN_COGS", out / "token_cogs_ledger.csv")
    monkeypatch.setattr(e004, "REFUND_HISTORY", out / "refund_adjustment_history.csv")
    monkeypatch.setattr(e004, "FIN_L3", out / "financial_events_level3_official.csv")
    monkeypatch.setattr(e004, "LISTING_HISTORY", out / "listing_offer_history.csv")
    return out


def test_e004_aligns_units_to_roi_truth_and_preserves_velocity(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "sku_sales_velocity.csv",
        [
            {
                "sku": "SKU-A",
                "window_days": "30",
                "units_sold": "7",
                "velocity_30d": "1.2",
                "asof_date": "2026-04-17",
            }
        ],
        ["sku", "window_days", "units_sold", "velocity_30d", "asof_date"],
    )
    _write_csv(
        out / "sku_roi_snapshot.csv",
        [
            {
                "sku": "SKU-A",
                "units_sold": "5",
                "revenue_exvat_gbp": "50",
                "profit_exvat_gbp": "10",
                "asof_date": "2026-04-17",
            }
        ],
        ["sku", "units_sold", "revenue_exvat_gbp", "profit_exvat_gbp", "asof_date"],
    )
    _write_csv(
        out / "sku_restock_signals.csv",
        [{"sku": "SKU-A"}],
        ["sku"],
    )

    e004.main()

    df = pd.read_csv(out / "sku_performance_summary.csv")
    row = df.loc[df["sku"] == "SKU-A"].iloc[0]
    assert row["units_sold"] == pytest.approx(5.0, abs=1e-6)
    assert row["units_sold_truth_30d"] == pytest.approx(5.0, abs=1e-6)
    assert row["units_sold_velocity_30d"] == pytest.approx(7.0, abs=1e-6)
    assert str(row["units_sold_source"]) == "roi"
    assert row["revenue_exvat_gbp"] == pytest.approx(50.0, abs=1e-6)
    assert row["profit_exvat_gbp"] == pytest.approx(10.0, abs=1e-6)


def test_e004_falls_back_to_velocity_units_when_roi_missing(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "sku_sales_velocity.csv",
        [
            {
                "sku": "SKU-B",
                "window_days": "30",
                "units_sold": "4",
                "velocity_30d": "0.8",
                "asof_date": "2026-04-17",
            }
        ],
        ["sku", "window_days", "units_sold", "velocity_30d", "asof_date"],
    )
    _write_csv(
        out / "sku_roi_snapshot.csv",
        [],
        ["sku", "units_sold", "revenue_exvat_gbp", "profit_exvat_gbp", "asof_date"],
    )
    _write_csv(
        out / "sku_restock_signals.csv",
        [{"sku": "SKU-B"}],
        ["sku"],
    )

    e004.main()

    df = pd.read_csv(out / "sku_performance_summary.csv")
    row = df.loc[df["sku"] == "SKU-B"].iloc[0]
    assert row["units_sold"] == pytest.approx(4.0, abs=1e-6)
    assert row["units_sold_truth_30d"] == pytest.approx(4.0, abs=1e-6)
    assert row["units_sold_velocity_30d"] == pytest.approx(4.0, abs=1e-6)
    assert str(row["units_sold_source"]) == "velocity"


def test_e004_sql_primary_writes_summary_table_and_csv_export(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    _write_csv(
        out / "sku_sales_velocity.csv",
        [
            {
                "sku": "SKU-A",
                "window_days": "30",
                "units_sold": "7",
                "velocity_30d": "1.2",
                "asof_date": "2026-04-17",
            }
        ],
        ["sku", "window_days", "units_sold", "velocity_30d", "asof_date"],
    )
    _write_csv(
        out / "sku_roi_snapshot.csv",
        [
            {
                "sku": "SKU-A",
                "units_sold": "5",
                "revenue_exvat_gbp": "50",
                "profit_exvat_gbp": "10",
                "asof_date": "2026-04-17",
            }
        ],
        ["sku", "units_sold", "revenue_exvat_gbp", "profit_exvat_gbp", "asof_date"],
    )
    _write_csv(out / "sku_restock_signals.csv", [{"sku": "SKU-A"}], ["sku"])
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    e004.main()

    built = pd.read_csv(out / "sku_performance_summary.csv", dtype=str).fillna("")
    assert built.loc[0, "sku"] == "SKU-A"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT sku, units_sold_source FROM e_sku_performance_summary"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("SKU-A", "roi")]
