from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.E import E007_build_sku_daily_sales_truth as e007


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(monkeypatch, tmp_path: Path) -> Path:
    out = tmp_path / "out"
    monkeypatch.setattr(e007, "OUT", out)
    monkeypatch.setattr(e007, "ORDER_MASTER", out / "order_master.csv")
    monkeypatch.setattr(e007, "ORDER_LEDGER_FX", out / "order_ledger_fx.csv")
    monkeypatch.setattr(e007, "FINANCIAL_EVENTS_LEVEL2", out / "financial_events_level2.csv")
    monkeypatch.setattr(e007, "TOKEN_COGS", out / "token_cogs_ledger.csv")
    monkeypatch.setattr(e007, "FX_RATES", out / "fx_rates_daily.csv")
    monkeypatch.setattr(e007, "MARKETPLACE_PARTICIPATIONS", out / "marketplace_participations.csv")
    monkeypatch.setattr(e007, "OUT_DAILY", out / "sku_daily_sales_truth_latest.csv")
    return out


def test_e007_builds_finalized_and_provisional_states(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "date": "2026-04-16T10:00:00Z",
                "SKU": "A2-T2AC-TW3L",
                "Quantity Ordered": "2",
                "Price_ExVAT_GBP": "18.16",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
                "COGS_ExVAT": "-10.0",
                "FBA_Fee_ExVAT_GBP": "-4.0",
                "Commission_ExVAT_GBP": "-2.0",
                "Digital_Fee_ExVAT_GBP": "0",
                "FixedClosingFee_ExVAT_GBP": "0",
            },
            {
                "date": "2026-04-16T12:00:00Z",
                "SKU": "A2-T2AC-TW3L",
                "Quantity Ordered": "1",
                "Price_ExVAT_GBP": "9.08",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
                "COGS_ExVAT": "-6.0",
                "FBA_Fee_ExVAT_GBP": "-2.0",
                "Commission_ExVAT_GBP": "-1.38",
                "Digital_Fee_ExVAT_GBP": "0",
                "FixedClosingFee_ExVAT_GBP": "0",
            },
        ],
        [
            "date",
            "SKU",
            "Quantity Ordered",
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
    _write_csv(
        out / "order_master.csv",
        [
            {
                "Date": "2026-04-16T19:00:00Z",
                "SKU": "A2-T2AC-TW3L",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "Price_ExVAT": "9.08",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-6.0",
                "FBA_Fee_ExVAT": "-2.0",
                "Commission_ExVAT": "-1.38",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
            {
                "Date": "2026-04-17T09:00:00Z",
                "SKU": "A2-T2AC-TW3L",
                "Quantity Ordered": "5",
                "currency_code": "GBP",
                "Price_ExVAT": "46.60",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-30.0",
                "FBA_Fee_ExVAT": "-8.0",
                "Commission_ExVAT": "-4.45",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
        ],
        [
            "Date",
            "SKU",
            "Quantity Ordered",
            "currency_code",
            "Price_ExVAT",
            "Shipping_ExVAT",
            "Gift_ExVAT",
            "Promotion_ExVAT",
            "COGS_ExVAT",
            "FBA_Fee_ExVAT",
            "Commission_ExVAT",
            "Digital_Fee_ExVAT",
            "FixedClosingFee_ExVAT",
        ],
    )
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])

    e007.main()

    out_df = pd.read_csv(out / "sku_daily_sales_truth_latest.csv")
    finalized = out_df.loc[
        (out_df["sku"] == "A2-T2AC-TW3L")
        & (out_df["date"] == "2026-04-16")
        & (out_df["source_state"] == "finalized_ledger")
    ].iloc[0]
    provisional = out_df.loc[
        (out_df["sku"] == "A2-T2AC-TW3L")
        & (out_df["date"] == "2026-04-17")
        & (out_df["source_state"] == "provisional_order_master")
    ].iloc[0]

    assert finalized["units"] == pytest.approx(3.0, abs=1e-6)
    assert finalized["revenue_gbp"] == pytest.approx(27.24, abs=1e-6)
    assert finalized["profit_gbp"] == pytest.approx(1.86, abs=1e-6)
    assert str(finalized["confidence_status"]) == "finalized"

    assert provisional["units"] == pytest.approx(5.0, abs=1e-6)
    assert provisional["revenue_gbp"] == pytest.approx(46.60, abs=1e-6)
    assert provisional["profit_gbp"] == pytest.approx(4.15, abs=1e-6)
    assert str(provisional["confidence_status"]) == "provisional"


def test_e007_uses_full_window_when_only_order_master_is_available(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_master.csv",
        [
            {
                "Date": "2026-04-16T09:00:00Z",
                "SKU": "SKU-A",
                "Quantity Ordered": "2",
                "currency_code": "GBP",
                "Price_ExVAT": "20",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-10",
                "FBA_Fee_ExVAT": "-3",
                "Commission_ExVAT": "-2",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
            {
                "Date": "2026-04-17T09:00:00Z",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "Price_ExVAT": "12",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-6",
                "FBA_Fee_ExVAT": "-2",
                "Commission_ExVAT": "-1",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
        ],
        [
            "Date",
            "SKU",
            "Quantity Ordered",
            "currency_code",
            "Price_ExVAT",
            "Shipping_ExVAT",
            "Gift_ExVAT",
            "Promotion_ExVAT",
            "COGS_ExVAT",
            "FBA_Fee_ExVAT",
            "Commission_ExVAT",
            "Digital_Fee_ExVAT",
            "FixedClosingFee_ExVAT",
        ],
    )
    _write_csv(out / "order_ledger_fx.csv", [], ["date", "SKU"])
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])

    e007.main()

    out_df = pd.read_csv(out / "sku_daily_sales_truth_latest.csv")
    assert set(out_df["date"]) == {"2026-04-16", "2026-04-17"}
    assert set(out_df["source_state"]) == {"provisional_order_master"}


def test_e007_marks_missing_fx_on_provisional_rows(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_master.csv",
        [
            {
                "Date": "2026-04-17T09:00:00Z",
                "SKU": "SKU-EUR",
                "Quantity Ordered": "1",
                "currency_code": "EUR",
                "Price_ExVAT": "10",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "COGS_ExVAT": "-5",
                "FBA_Fee_ExVAT": "-2",
                "Commission_ExVAT": "-1",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            }
        ],
        [
            "Date",
            "SKU",
            "Quantity Ordered",
            "currency_code",
            "Price_ExVAT",
            "Shipping_ExVAT",
            "Gift_ExVAT",
            "Promotion_ExVAT",
            "COGS_ExVAT",
            "FBA_Fee_ExVAT",
            "Commission_ExVAT",
            "Digital_Fee_ExVAT",
            "FixedClosingFee_ExVAT",
        ],
    )
    _write_csv(out / "order_ledger_fx.csv", [], ["date", "SKU"])
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])

    e007.main()

    row = pd.read_csv(out / "sku_daily_sales_truth_latest.csv").iloc[0]
    assert str(row["confidence_status"]) == "provisional_fx_missing"
    assert "basis=order_master_fallback" in str(row["notes"])
    assert "fx_missing_units=1" in str(row["notes"])


def test_e007_uses_level2_rows_when_order_master_is_missing(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "date": "2026-04-16T10:00:00Z",
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_ExVAT_GBP": "10",
                "Shipping_ExVAT_GBP": "0",
                "Gift_ExVAT_GBP": "0",
                "Promotion_ExVAT_GBP": "0",
                "COGS_ExVAT": "-4",
                "FBA_Fee_ExVAT_GBP": "-2",
                "Commission_ExVAT_GBP": "-1",
                "Digital_Fee_ExVAT_GBP": "0",
                "FixedClosingFee_ExVAT_GBP": "0",
            }
        ],
        [
            "date",
            "Order ID",
            "SKU",
            "Quantity Ordered",
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
    _write_csv(
        out / "financial_events_level2.csv",
        [
            {
                "Date": "2026-04-16T10:00:00Z",
                "Order ID": "ORDER-1",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_ExVAT": "10",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "FBA_Fee_ExVAT": "-2",
                "Commission_ExVAT": "-1",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
            {
                "Date": "2026-04-17T10:00:00Z",
                "Order ID": "ORDER-2",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_ExVAT": "12",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "FBA_Fee_ExVAT": "-2",
                "Commission_ExVAT": "-1",
                "Digital_Fee_ExVAT": "0",
                "FixedClosingFee_ExVAT": "0",
            },
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
    _write_csv(out / "order_master.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])

    e007.main()

    out_df = pd.read_csv(out / "sku_daily_sales_truth_latest.csv")
    provisional = out_df.loc[
        (out_df["sku"] == "SKU-A")
        & (out_df["date"] == "2026-04-17")
        & (out_df["source_state"] == "provisional_order_master")
    ].iloc[0]

    assert provisional["units"] == pytest.approx(1.0, abs=1e-6)
    assert provisional["revenue_gbp"] == pytest.approx(12.0, abs=1e-6)
    assert provisional["profit_gbp"] == pytest.approx(0.0, abs=1e-6)
    assert str(provisional["confidence_status"]) == "provisional_cogs_missing"
    assert "basis=financial_events_level2" in str(provisional["notes"])
    assert "cogs_missing_units=1" in str(provisional["notes"])


def test_e007_marks_placeholder_cogs_on_level2_rows(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    _write_csv(out / "order_ledger_fx.csv", [], ["date", "Order ID", "SKU"])
    _write_csv(
        out / "financial_events_level2.csv",
        [
            {
                "Date": "2026-04-17T10:00:00Z",
                "Order ID": "ORDER-2",
                "marketplace_id": "A1F83G8C2ARO7P",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_ExVAT": "12",
                "Shipping_ExVAT": "0",
                "Gift_ExVAT": "0",
                "Promotion_ExVAT": "0",
                "FBA_Fee_ExVAT": "-2",
                "Commission_ExVAT": "-1",
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
        out / "order_master.csv",
        [
            {
                "Date": "2026-04-17T10:00:00Z",
                "Order ID": "ORDER-2",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "country_code": "GB",
                "COGS_ExVAT": "-6",
                "COGS_Placeholder_Applied": "1",
                "COGS_Basis_Source": "token_cogs_ledger_last_actual",
                "COGS_Basis_Date": "2026-04-13",
                "Missing_Token_Flag": "1",
                "Missing_Token_Reason": "missing_token_placeholder_applied",
            }
        ],
        [
            "Date",
            "Order ID",
            "SKU",
            "Quantity Ordered",
            "currency_code",
            "country_code",
            "COGS_ExVAT",
            "COGS_Placeholder_Applied",
            "COGS_Basis_Source",
            "COGS_Basis_Date",
            "Missing_Token_Flag",
            "Missing_Token_Reason",
        ],
    )
    _write_csv(
        out / "marketplace_participations.csv",
        [{"marketplace_id": "A1F83G8C2ARO7P", "country_code": "GB", "default_currency": "GBP"}],
        ["marketplace_id", "country_code", "default_currency"],
    )
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])

    e007.main()

    row = pd.read_csv(out / "sku_daily_sales_truth_latest.csv").iloc[0]
    assert row["units"] == pytest.approx(1.0, abs=1e-6)
    assert row["revenue_gbp"] == pytest.approx(12.0, abs=1e-6)
    assert row["profit_gbp"] == pytest.approx(3.0, abs=1e-6)
    assert str(row["confidence_status"]) == "provisional_cogs_placeholder"
    assert "cogs_placeholder_units=1" in str(row["notes"])
    assert "placeholder_source=token_cogs_ledger_last_actual" in str(row["notes"])


def test_e007_sql_primary_writes_daily_truth_table_and_csv_export(monkeypatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "date": "2026-04-16T10:00:00Z",
                "SKU": "SKU-SQL",
                "Quantity Ordered": "2",
                "Price_ExVAT_GBP": "18",
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
    _write_csv(out / "order_master.csv", [], ["Date", "SKU"])
    _write_csv(out / "financial_events_level2.csv", [], ["Date", "Order ID", "SKU"])
    _write_csv(out / "token_cogs_ledger.csv", [], ["order_id", "seller_sku", "quantity", "currency", "cogs_exvat", "order_date"])
    _write_csv(out / "marketplace_participations.csv", [], ["marketplace_id", "country_code", "default_currency"])
    _write_csv(out / "fx_rates_daily.csv", [], ["date", "currency", "rate_to_gbp"])
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    e007.main()

    built = pd.read_csv(out / "sku_daily_sales_truth_latest.csv", dtype=str).fillna("")
    assert built.loc[0, "sku"] == "SKU-SQL"
    assert built.loc[0, "confidence_status"] == "finalized"

    connection = sqlite3.connect(sqlite_path)
    try:
        rows = connection.execute(
            "SELECT sku, source_state, units FROM e_sku_daily_sales_truth"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("SKU-SQL", "finalized_ledger", "2.0")]
