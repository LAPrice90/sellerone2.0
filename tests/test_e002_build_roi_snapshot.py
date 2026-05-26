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

from scripts.flows.E import E002_build_roi_snapshot as e002


ORDER_COLUMNS = [
    "Date",
    "SKU",
    "Quantity Ordered",
    "currency_code",
    "country_code",
    "Price_ExVAT",
    "Shipping_ExVAT",
    "Gift_ExVAT",
    "Promotion_ExVAT",
    "COGS_ExVAT",
    "FBA_Fee_ExVAT",
    "Commission_ExVAT",
    "Digital_Fee_ExVAT",
    "FixedClosingFee_ExVAT",
]


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    monkeypatch.setattr(e002, "OUT", out)
    monkeypatch.setattr(e002, "ORDERS", out / "order_master.csv")
    monkeypatch.setattr(e002, "ORDER_LEDGER_FX", out / "order_ledger_fx.csv")
    monkeypatch.setattr(e002, "FINANCIAL_EVENTS_LEVEL2", out / "financial_events_level2.csv")
    monkeypatch.setattr(e002, "TOKEN_COGS", out / "token_cogs_ledger.csv")
    monkeypatch.setattr(e002, "OUT_ROI", out / "sku_roi_snapshot.csv")
    monkeypatch.setattr(e002, "OUT_ROI_UK", out / "sku_roi_snapshot_uk.csv")
    monkeypatch.setattr(e002, "OUT_ROI_NON_UK", out / "sku_roi_snapshot_non_uk.csv")
    monkeypatch.setattr(e002, "OUT_ROI_BY_COUNTRY", out / "sku_roi_snapshot_by_country.csv")
    monkeypatch.setattr(e002, "FX_RATES", out / "fx_rates_daily.csv")
    monkeypatch.setattr(e002, "MARKETPLACE_PARTICIPATIONS", out / "marketplace_participations.csv")
    return out


def test_e002_non_contiguous_window_indexes_do_not_zero_revenue(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_master.csv",
        [
            {
                "Date": "2026-01-01",
                "SKU": "OLD-SKU",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "country_code": "GB",
                "Price_ExVAT": "3",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-2",
                "FBA_Fee_ExVAT": "-0.5",
                "Commission_ExVAT": "-0.5",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
            {
                "Date": "2026-04-20",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "country_code": "GB",
                "Price_ExVAT": "10",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-6",
                "FBA_Fee_ExVAT": "-1",
                "Commission_ExVAT": "-1",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
            {
                "Date": "2026-04-20",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "currency_code": "EUR",
                "country_code": "DE",
                "Price_ExVAT": "10",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-6",
                "FBA_Fee_ExVAT": "-1",
                "Commission_ExVAT": "-1",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
        ],
        ORDER_COLUMNS,
    )
    _write_csv(
        out / "fx_rates_daily.csv",
        [{"date": "2026-04-20", "currency": "EUR", "rate_to_gbp": "0.8"}],
        ["date", "currency", "rate_to_gbp"],
    )
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])

    e002.main()

    roi = pd.read_csv(out / "sku_roi_snapshot.csv")
    row = roi.loc[roi["sku"] == "SKU-A"].iloc[0]
    assert row["revenue_exvat_gbp"] == pytest.approx(18.0, abs=1e-6)
    assert row["cogs_exvat_gbp"] == pytest.approx(-12.0, abs=1e-6)
    assert row["profit_exvat_gbp"] == pytest.approx(2.4, abs=1e-6)
    assert int(row["missing_cogs_units"]) == 0
    assert int(row["fx_missing_units"]) == 0


def test_e002_flags_missing_fx_for_non_gbp_rows(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_master.csv",
        [
            {
                "Date": "2026-04-21",
                "SKU": "SKU-C",
                "Quantity Ordered": "1",
                "currency_code": "EUR",
                "country_code": "DE",
                "Price_ExVAT": "10",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-5",
                "FBA_Fee_ExVAT": "-1",
                "Commission_ExVAT": "0",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            }
        ],
        ORDER_COLUMNS,
    )
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])

    e002.main()

    roi = pd.read_csv(out / "sku_roi_snapshot.csv")
    row = roi.loc[roi["sku"] == "SKU-C"].iloc[0]
    assert row["revenue_exvat_gbp"] == pytest.approx(10.0, abs=1e-6)
    assert row["profit_exvat_gbp"] == pytest.approx(4.0, abs=1e-6)
    assert int(row["fx_missing_units"]) == 1


def test_e002_missing_cogs_units_only_counts_zero_cogs(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_master.csv",
        [
            {
                "Date": "2026-04-22",
                "SKU": "SKU-NEG",
                "Quantity Ordered": "2",
                "currency_code": "GBP",
                "country_code": "GB",
                "Price_ExVAT": "8",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-3",
                "FBA_Fee_ExVAT": "-1",
                "Commission_ExVAT": "0",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
            {
                "Date": "2026-04-22",
                "SKU": "SKU-ZERO",
                "Quantity Ordered": "3",
                "currency_code": "GBP",
                "country_code": "GB",
                "Price_ExVAT": "6",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "0",
                "FBA_Fee_ExVAT": "-1",
                "Commission_ExVAT": "0",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
        ],
        ORDER_COLUMNS,
    )
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])

    e002.main()

    roi = pd.read_csv(out / "sku_roi_snapshot.csv").set_index("sku")
    assert int(roi.loc["SKU-NEG", "missing_cogs_units"]) == 0
    assert int(roi.loc["SKU-ZERO", "missing_cogs_units"]) == 3


def test_e002_prefers_order_ledger_fx_when_available(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_master.csv",
        [
            {
                "Date": "2026-04-23",
                "SKU": "SKU-LEDGER",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "country_code": "GB",
                "Price_ExVAT": "99",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-10",
                "FBA_Fee_ExVAT": "-1",
                "Commission_ExVAT": "0",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            }
        ],
        ORDER_COLUMNS,
    )
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "date": "2026-04-23",
                "SKU": "SKU-LEDGER",
                "Quantity Ordered": "2",
                "country_code": "GB",
                "Price_ExVAT_GBP": "20",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
                "COGS_ExVAT": "-10",
                "FBA_Fee_ExVAT_GBP": "-4",
                "Commission_ExVAT_GBP": "-2",
                "Digital_Fee_ExVAT_GBP": "0",
                "FixedClosingFee_ExVAT_GBP": "0",
            }
        ],
        [
            "date",
            "SKU",
            "Quantity Ordered",
            "country_code",
            "Price_ExVAT_GBP",
            "Shipping_ExVAT_GBP",
            "Gift_ExVAT_GBP",
            "Promotion_ExVAT_GBP",
            "COGS_ExVAT",
            "FBA_Fee_ExVAT_GBP",
            "Commission_ExVAT_GBP",
            "Digital_Fee_ExVAT_GBP",
            "FixedClosingFee_ExVAT_GBP",
        ],
    )
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])

    e002.main()

    roi = pd.read_csv(out / "sku_roi_snapshot.csv")
    assert set(roi["sku"].tolist()) == {"SKU-LEDGER"}
    row = roi.iloc[0]
    assert row["units_sold"] == pytest.approx(2.0, abs=1e-6)
    assert row["revenue_exvat_gbp"] == pytest.approx(20.0, abs=1e-6)
    assert row["profit_exvat_gbp"] == pytest.approx(4.0, abs=1e-6)


def test_e002_uses_level2_rows_when_token_cogs_are_missing(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(out / "order_master.csv", [], ORDER_COLUMNS)
    _write_csv(out / "order_ledger_fx.csv", [], ["date", "SKU"])
    _write_csv(
        out / "financial_events_level2.csv",
        [
            {
                "Date": "2026-04-23T10:00:00Z",
                "Order ID": "ORDER-1",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-L2",
                "Quantity Ordered": "2",
                "Price_ExVAT": "20",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "FBA_Fee_ExVAT": "-4",
                "Commission_ExVAT": "-2",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            }
        ],
        [
            "Date",
            "Order ID",
            "marketplace_id",
            "SKU",
            "Quantity Ordered",
            "Price_ExVAT",
            "Shipping_ExVAT",
            "Gift_ExVAT",
            "Promotion_ExVAT",
            "FBA_Fee_ExVAT",
            "Commission_ExVAT",
            "Digital_Fee_ExVAT",
            "FixedClosingFee_ExVAT",
        ],
    )
    _write_csv(
        out / "marketplace_participations.csv",
        [{"marketplace_id": "A1F83G8C2ARO7P", "country_code": "GB", "default_currency": "GBP"}],
        ["marketplace_id", "country_code", "default_currency"],
    )
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])

    e002.main()

    roi = pd.read_csv(out / "sku_roi_snapshot.csv").set_index("sku")
    assert roi.loc["SKU-L2", "units_sold"] == pytest.approx(2.0, abs=1e-6)
    assert roi.loc["SKU-L2", "revenue_exvat_gbp"] == pytest.approx(20.0, abs=1e-6)
    assert roi.loc["SKU-L2", "profit_exvat_gbp"] == pytest.approx(0.0, abs=1e-6)
    assert int(roi.loc["SKU-L2", "missing_cogs_units"]) == 2


def test_e002_sql_primary_writes_roi_tables_and_csv_exports(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    _write_csv(
        out / "order_master.csv",
        [
            {
                "Date": "2026-04-20",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "country_code": "GB",
                "Price_ExVAT": "10",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-6",
                "FBA_Fee_ExVAT": "-1",
                "Commission_ExVAT": "-1",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            }
        ],
        ORDER_COLUMNS,
    )
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    e002.main()

    roi = pd.read_csv(out / "sku_roi_snapshot.csv", dtype=str).fillna("")
    by_country = pd.read_csv(out / "sku_roi_snapshot_by_country.csv", dtype=str).fillna("")
    assert len(roi) == 1
    assert len(by_country) == 1

    connection = sqlite3.connect(sqlite_path)
    try:
        roi_rows = connection.execute(
            "SELECT sku, units_sold FROM e_sku_roi_snapshot"
        ).fetchall()
        by_country_rows = connection.execute(
            "SELECT sku, country_code, units_sold FROM e_sku_roi_snapshot_by_country"
        ).fetchall()
    finally:
        connection.close()

    assert roi_rows == [("SKU-A", "1.0")]
    assert by_country_rows == [("SKU-A", "GB", "1.0")]
