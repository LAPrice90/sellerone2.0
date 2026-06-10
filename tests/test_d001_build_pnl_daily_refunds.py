from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.D import D001_build_pnl_daily as d001


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _pnl_value(df: pd.DataFrame, row_name: str, date_col: str) -> float:
    row = df.loc[df["Parameter/Date"] == row_name].iloc[0]
    return float(row[date_col])


def test_d001_adds_refund_unit_rows_without_double_counting_transaction_refunds(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "out"
    monkeypatch.setattr(d001, "ORDER_LEDGER_FX", out / "order_ledger_fx.csv")
    monkeypatch.setattr(d001, "ORDER_COGS", out / "order_cogs_from_tokens.csv")
    monkeypatch.setattr(d001, "PRODUCT_DB", out / "product_db_preview.csv")
    monkeypatch.setattr(d001, "OUT_PNL", out / "pnl_daily.csv")
    monkeypatch.setattr(d001, "TXN_BREAKDOWNS", out / "financial_transactions_v2024_breakdowns.csv")
    monkeypatch.setattr(d001, "TXN_CATEGORY_LEDGER", out / "missing_transaction_category_ledger.csv")
    monkeypatch.setattr(d001, "REFUNDS_OFFICIAL", out / "financial_events_refunds_official.csv")
    monkeypatch.setattr(d001, "FEE_VAT_LEDGER", out / "fee_vat_ledger.csv")
    monkeypatch.setattr(d001, "RETURN_COGS", out / "token_return_ledger.csv")
    monkeypatch.setattr(d001, "PNL_WRITE_SHEETS", False)
    monkeypatch.setattr(d001, "PNL_START_DATE", "2026-05-01")

    _write_csv(
        out / "order_ledger_fx.csv",
        [
            {
                "Date": "2026-05-01T10:00:00Z",
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "country_code": "GB",
                "Quantity Ordered": "2",
                "Price_Total_GBP": "24",
                "Price_VAT_GBP": "4",
                "Price_ExVAT_GBP": "20",
            }
        ],
        ["Date", "Order ID", "SKU", "country_code", "Quantity Ordered", "Price_Total_GBP", "Price_VAT_GBP", "Price_ExVAT_GBP"],
    )
    _write_csv(
        out / "financial_events_refunds_official.csv",
        [
            {
                "Date": "2026-05-02T10:00:00Z",
                "Order ID": "ORDER-1",
                "SKU": "SKU-A",
                "Quantity Ordered": "1",
                "Price_Total": "-12",
                "Shipping_Total": "0",
                "Gift_Total": "0",
                "Promotion_Total": "0",
                "FBA_Fee_Total": "2",
                "Commission_Total": "1",
                "Digital_Fee_Total": "0",
                "FixedClosingFee_Total": "0",
            }
        ],
        [
            "Date",
            "Order ID",
            "SKU",
            "Quantity Ordered",
            "Price_Total",
            "Shipping_Total",
            "Gift_Total",
            "Promotion_Total",
            "FBA_Fee_Total",
            "Commission_Total",
            "Digital_Fee_Total",
            "FixedClosingFee_Total",
        ],
    )
    _write_csv(
        out / "financial_transactions_v2024_breakdowns.csv",
        [
            {
                "posted_date": "2026-05-02T10:00:00Z",
                "transaction_type": "Refund",
                "breakdown_type": "Refunded Sales",
                "description": "",
                "breakdown_amount": "-12",
            }
        ],
        ["posted_date", "transaction_type", "breakdown_type", "description", "breakdown_amount"],
    )

    d001.main()

    pnl = pd.read_csv(out / "pnl_daily.csv")
    assert _pnl_value(pnl, "Refund_Sales_Total", "2026-05-02") == pytest.approx(-12.0)
    assert _pnl_value(pnl, "Refund_Expenses_Total", "2026-05-02") == pytest.approx(3.0)
    assert _pnl_value(pnl, "Gross_Units_Sold", "2026-05-01") == pytest.approx(2.0)
    assert _pnl_value(pnl, "Refund_Units", "2026-05-02") == pytest.approx(1.0)
    assert _pnl_value(pnl, "Refund_Unit_Rate", "Total") == pytest.approx(0.5)

