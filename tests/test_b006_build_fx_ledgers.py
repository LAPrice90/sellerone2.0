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

from scripts.flows.B import B006_build_fx_ledgers as b006


ORDER_FX_COLS = [
    "Price_Total",
    "Price_VAT",
    "Price_ExVAT",
    "Shipping_Total",
    "Shipping_VAT",
    "Shipping_ExVAT",
    "Gift_Total",
    "Gift_VAT",
    "Gift_ExVAT",
    "Promotion_Total",
    "Promotion_VAT",
    "Promotion_ExVAT",
    "FBA_Fee_Total",
    "FBA_Fee_VAT",
    "FBA_Fee_ExVAT",
    "Commission_Total",
    "Commission_VAT",
    "Commission_ExVAT",
    "Digital_Fee_Total",
    "Digital_Fee_VAT",
    "Digital_Fee_ExVAT",
]


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_b006_sql_primary_writes_fx_ledgers_and_rates_from_local_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    sqlite_path = tmp_path / "pilot.sqlite3"
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(sqlite_path))

    order_row = {
        "Date": "2026-04-28T10:00:00Z",
        "Order ID": "ORDER-1",
        "SKU": "SKU-EUR",
        "currency_code": "EUR",
    }
    for col in ORDER_FX_COLS:
        order_row[col] = "0"
    order_row["Price_Total"] = "10"
    order_row["Price_ExVAT"] = "8"
    order_row["Commission_Total"] = "-1"

    _write_csv(
        Path("out/order_master.csv"),
        [order_row],
        ["Date", "Order ID", "SKU", "currency_code"] + ORDER_FX_COLS,
    )
    _write_csv(
        Path("out/financial_events_level3_raw.csv"),
        [
            {
                "posted_date": "2026-04-28T11:00:00Z",
                "order_id": "ORDER-1",
                "sku": "SKU-EUR",
                "transaction_type": "Order",
                "amount": "12",
                "currency": "EUR",
                "tax_amount": "2",
                "tax_currency": "EUR",
            }
        ],
        ["posted_date", "order_id", "sku", "transaction_type", "amount", "currency", "tax_amount", "tax_currency"],
    )
    _write_csv(
        Path("out/fx_rates_daily.csv"),
        [
            {"date": "2026-04-28", "currency": "EUR", "rate_to_gbp": "0.80000000", "source": "fixture", "fx_date_used": "2026-04-28"},
            {"date": "2026-04-28", "currency": "GBP", "rate_to_gbp": "1.00000000", "source": "fixture", "fx_date_used": "2026-04-28"},
        ],
        ["date", "currency", "rate_to_gbp", "source", "fx_date_used"],
    )

    b006.main()

    order_fx = pd.read_csv("out/order_ledger_fx.csv", dtype=str).fillna("")
    fin_fx = pd.read_csv("out/financial_ledger_fx.csv", dtype=str).fillna("")
    assert float(order_fx.loc[0, "Price_Total_GBP"]) == pytest.approx(8.0, abs=1e-6)
    assert float(order_fx.loc[0, "Commission_Total_GBP"]) == pytest.approx(-0.8, abs=1e-6)
    assert float(fin_fx.loc[0, "amount_gbp"]) == pytest.approx(9.6, abs=1e-6)
    assert float(fin_fx.loc[0, "tax_amount_gbp"]) == pytest.approx(1.6, abs=1e-6)

    connection = sqlite3.connect(sqlite_path)
    try:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ["b_order_ledger_fx", "b_financial_ledger_fx", "b_fx_rates_daily"]
        }
        order_rows = connection.execute(
            "SELECT order_id, sku, price_total_gbp FROM b_order_ledger_fx"
        ).fetchall()
    finally:
        connection.close()

    assert counts == {
        "b_order_ledger_fx": 1,
        "b_financial_ledger_fx": 1,
        "b_fx_rates_daily": 2,
    }
    assert order_rows == [("ORDER-1", "SKU-EUR", "8.0")]


def test_b006_csv_mode_still_writes_order_ledger_csv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "csv")

    order_row = {
        "Date": "2026-04-28T10:00:00Z",
        "Order ID": "ORDER-GBP",
        "SKU": "SKU-GBP",
        "currency_code": "GBP",
    }
    for col in ORDER_FX_COLS:
        order_row[col] = "0"
    order_row["Price_Total"] = "10"
    _write_csv(
        Path("out/order_master.csv"),
        [order_row],
        ["Date", "Order ID", "SKU", "currency_code"] + ORDER_FX_COLS,
    )
    _write_csv(Path("out/financial_events_level3_raw.csv"), [], ["posted_date", "currency"])

    b006.main()

    order_fx = pd.read_csv("out/order_ledger_fx.csv", dtype=str).fillna("")
    assert len(order_fx) == 1
    assert float(order_fx.loc[0, "Price_Total_GBP"]) == pytest.approx(10.0, abs=1e-6)
