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

from scripts.flows.E import E005_build_study_report as e005


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    monkeypatch.setattr(e005, "OUT", out)
    monkeypatch.setattr(e005, "SUMMARY", out / "sku_performance_summary.csv")
    monkeypatch.setattr(e005, "DAILY_TRUTH", out / "sku_daily_sales_truth_latest.csv")
    monkeypatch.setattr(e005, "OUT_STUDY", out / "e_study_report.csv")
    return out


def test_e005_matches_performance_truth_and_surfaces_latest_daily_state(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "sku_performance_summary.csv",
        [
            {
                "sku": "SKU-A",
                "asof_date": "2026-04-17",
                "reorder_flag": "yes",
                "days_of_stock_left": "2",
                "suggested_reorder_qty": "20",
                "velocity_30d": "1.2",
                "units_sold": "5",
                "units_sold_truth_30d": "5",
                "units_sold_velocity_30d": "7",
                "units_sold_source": "roi",
                "revenue_exvat_gbp": "50",
                "profit_exvat_gbp": "10",
                "roi_exvat": "0.2",
                "profit_per_unit_gbp_30d": "2",
                "value_velocity_gbp_per_day": "2.4",
                "missing_cogs_units": "0",
                "fx_missing_units": "0",
                "current_token_cost_gbp": "5",
                "break_even_price_gbp": "7",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "roi_at_our_price_pct": "25",
                "roi_at_buy_box_price_pct": "30",
            }
        ],
        [
            "sku",
            "asof_date",
            "reorder_flag",
            "days_of_stock_left",
            "suggested_reorder_qty",
            "velocity_30d",
            "units_sold",
            "units_sold_truth_30d",
            "units_sold_velocity_30d",
            "units_sold_source",
            "revenue_exvat_gbp",
            "profit_exvat_gbp",
            "roi_exvat",
            "profit_per_unit_gbp_30d",
            "value_velocity_gbp_per_day",
            "missing_cogs_units",
            "fx_missing_units",
            "current_token_cost_gbp",
            "break_even_price_gbp",
            "expected_refund_cost_per_unit_gbp",
            "roi_at_our_price_pct",
            "roi_at_buy_box_price_pct",
        ],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [
            {
                "sku": "SKU-A",
                "date": "2026-04-16",
                "source_state": "finalized_ledger",
                "units": "3",
                "revenue_gbp": "27.24",
                "profit_gbp": "1.86",
                "fees_gbp": "-12.06",
                "cogs_gbp": "-13.32",
                "confidence_status": "finalized",
                "notes": "",
            },
            {
                "sku": "SKU-A",
                "date": "2026-04-17",
                "source_state": "provisional_order_master",
                "units": "6",
                "revenue_gbp": "55.92",
                "profit_gbp": "4.98",
                "fees_gbp": "-24.3",
                "cogs_gbp": "-26.64",
                "confidence_status": "provisional",
                "notes": "",
            },
        ],
        ["sku", "date", "source_state", "units", "revenue_gbp", "profit_gbp", "fees_gbp", "cogs_gbp", "confidence_status", "notes"],
    )

    e005.main()

    df = pd.read_csv(out / "e_study_report.csv")
    row = df.loc[df["sku"] == "SKU-A"].iloc[0]
    assert row["units_sold_30d"] == pytest.approx(5.0, abs=1e-6)
    assert row["units_sold_truth_30d"] == pytest.approx(5.0, abs=1e-6)
    assert row["units_sold_velocity_30d"] == pytest.approx(7.0, abs=1e-6)
    assert str(row["units_sold_source"]) == "roi"
    assert row["revenue_exvat_gbp_30d"] == pytest.approx(50.0, abs=1e-6)
    assert row["profit_exvat_gbp_30d"] == pytest.approx(10.0, abs=1e-6)
    assert str(row["latest_daily_truth_date"]) == "2026-04-17"
    assert str(row["latest_daily_truth_state"]) == "provisional_order_master"
    assert row["latest_daily_truth_units"] == pytest.approx(6.0, abs=1e-6)
    assert row["latest_daily_truth_profit_gbp"] == pytest.approx(4.98, abs=1e-6)


def test_e005_sorts_reorder_then_value_then_stock(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "sku_performance_summary.csv",
        [
            {
                "sku": "SKU-HIGH",
                "asof_date": "2026-04-17",
                "reorder_flag": "yes",
                "days_of_stock_left": "4",
                "suggested_reorder_qty": "10",
                "velocity_30d": "1.0",
                "units_sold": "4",
                "units_sold_truth_30d": "4",
                "units_sold_velocity_30d": "4",
                "units_sold_source": "roi",
                "revenue_exvat_gbp": "40",
                "profit_exvat_gbp": "12",
                "roi_exvat": "0.3",
                "profit_per_unit_gbp_30d": "3",
                "value_velocity_gbp_per_day": "3.0",
            },
            {
                "sku": "SKU-LOW",
                "asof_date": "2026-04-17",
                "reorder_flag": "no",
                "days_of_stock_left": "1",
                "suggested_reorder_qty": "0",
                "velocity_30d": "1.5",
                "units_sold": "6",
                "units_sold_truth_30d": "6",
                "units_sold_velocity_30d": "6",
                "units_sold_source": "roi",
                "revenue_exvat_gbp": "30",
                "profit_exvat_gbp": "4",
                "roi_exvat": "0.1",
                "profit_per_unit_gbp_30d": "0.666",
                "value_velocity_gbp_per_day": "1.0",
            },
        ],
        [
            "sku",
            "asof_date",
            "reorder_flag",
            "days_of_stock_left",
            "suggested_reorder_qty",
            "velocity_30d",
            "units_sold",
            "units_sold_truth_30d",
            "units_sold_velocity_30d",
            "units_sold_source",
            "revenue_exvat_gbp",
            "profit_exvat_gbp",
            "roi_exvat",
            "profit_per_unit_gbp_30d",
            "value_velocity_gbp_per_day",
        ],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [],
        ["sku", "date", "source_state", "units", "revenue_gbp", "profit_gbp", "fees_gbp", "cogs_gbp", "confidence_status", "notes"],
    )

    e005.main()

    df = pd.read_csv(out / "e_study_report.csv")
    assert df.iloc[0]["sku"] == "SKU-HIGH"
    assert df.iloc[0]["study_rank"] == 1


def test_e005_sql_primary_writes_study_table_and_csv_export(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    _write_csv(
        out / "sku_performance_summary.csv",
        [
            {
                "sku": "SKU-A",
                "asof_date": "2026-04-17",
                "reorder_flag": "yes",
                "days_of_stock_left": "2",
                "suggested_reorder_qty": "20",
                "velocity_30d": "1.2",
                "units_sold": "5",
                "value_velocity_gbp_per_day": "2.4",
            }
        ],
        [
            "sku",
            "asof_date",
            "reorder_flag",
            "days_of_stock_left",
            "suggested_reorder_qty",
            "velocity_30d",
            "units_sold",
            "value_velocity_gbp_per_day",
        ],
    )
    _write_csv(
        out / "sku_daily_sales_truth_latest.csv",
        [],
        ["sku", "date", "source_state", "units", "revenue_gbp", "profit_gbp"],
    )
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    e005.main()

    built = pd.read_csv(out / "e_study_report.csv", dtype=str).fillna("")
    assert built.loc[0, "sku"] == "SKU-A"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT sku, study_rank FROM e_study_report"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("SKU-A", "1")]
