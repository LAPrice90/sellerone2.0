from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.suppliers.entertainment_trading import convert_supplier


def _write_workbook(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "ItemCode": "1001",
                "ItemName": "Nintendo Switch Game",
                "Department": "Games",
                "Platform": "Switch",
                "Brand": "Nintendo",
                "CodeBars": "0501234567890",
                "Available": "12",
                "EUR": "10.00",
            },
            {
                "ItemCode": "1002",
                "ItemName": "Missing barcode",
                "Department": "Games",
                "Platform": "Switch",
                "Brand": "Brand",
                "CodeBars": "",
                "Available": "4",
                "EUR": "5.00",
            },
            {
                "ItemCode": "1003",
                "ItemName": "Bad cost",
                "Department": "Games",
                "Platform": "Switch",
                "Brand": "Brand",
                "CodeBars": "5012345678912",
                "Available": "3",
                "EUR": "bad",
            },
            {
                "ItemCode": "1004",
                "ItemName": "No stock",
                "Department": "Games",
                "Platform": "Switch",
                "Brand": "Brand",
                "CodeBars": "5012345678913",
                "Available": "0",
                "EUR": "3.00",
            },
            {
                "ItemCode": "1005",
                "ItemName": "Invalid barcode",
                "Department": "Games",
                "Platform": "Switch",
                "Brand": "Brand",
                "CodeBars": "123",
                "Available": "1",
                "EUR": "3.00",
            },
        ]
    ).to_excel(path, index=False, engine="openpyxl")


def test_entertainment_trading_converter_maps_stocklist_xlsx_and_converts_eur_to_gbp(tmp_path: Path) -> None:
    source = tmp_path / "Stocklist.xlsx"
    _write_workbook(source)
    old_rate = os.environ.get("F_ENTERTAINMENT_TRADING_EUR_GBP_RATE")
    os.environ["F_ENTERTAINMENT_TRADING_EUR_GBP_RATE"] = "0.80"
    try:
        valid, holds = convert_supplier(
            source,
            supplier_id="entertainment_trading",
            supplier_name="Entertainment Trading",
            source_url="",
            source_seen_at_utc="2026-04-30T14:00:00Z",
        )
    finally:
        if old_rate is None:
            os.environ.pop("F_ENTERTAINMENT_TRADING_EUR_GBP_RATE", None)
        else:
            os.environ["F_ENTERTAINMENT_TRADING_EUR_GBP_RATE"] = old_rate

    assert len(valid.index) == 1
    assert len(holds.index) == 4
    row = valid.iloc[0]
    assert row["supplier_id"] == "entertainment_trading"
    assert row["supplier_name"] == "Entertainment Trading"
    assert row["supplier_sku"] == "1001"
    assert row["supplier_title"] == "Nintendo Switch Game"
    assert row["barcode"] == "0501234567890"
    assert row["stock_available"] == "12"
    assert row["unit_cost"] == "8.00"
    assert row["currency"] == "GBP"
    assert row["vat_rate"] == "20"
    assert row["brand"] == "Nintendo"
    assert row["category"] == "Games"
    assert "source_currency=EUR" in row["notes"]

    reasons = set(holds["hold_reason_codes"].tolist())
    assert "missing_barcode" in reasons
    assert "missing_or_invalid_cost" in reasons
    assert "no_available_stock" in reasons
    assert "invalid_barcode_format" in reasons


def test_entertainment_trading_converter_keeps_duplicate_products_as_unique_rows(tmp_path: Path) -> None:
    source = tmp_path / "Stocklist.xlsx"
    pd.DataFrame(
        [
            {
                "ItemCode": "DUP1",
                "ItemName": "Duplicate Product",
                "Department": "Games",
                "Platform": "Switch",
                "Brand": "Brand",
                "CodeBars": "5012345678901",
                "Available": "1",
                "EUR": "10.00",
            },
            {
                "ItemCode": "DUP1",
                "ItemName": "Duplicate Product",
                "Department": "Games",
                "Platform": "Switch",
                "Brand": "Brand",
                "CodeBars": "5012345678901",
                "Available": "1",
                "EUR": "10.00",
            },
        ]
    ).to_excel(source, index=False, engine="openpyxl")

    valid, holds = convert_supplier(
        source,
        supplier_id="entertainment_trading",
        supplier_name="Entertainment Trading",
        source_url="",
        source_seen_at_utc="2026-04-30T14:00:00Z",
    )

    assert len(holds.index) == 0
    assert len(valid.index) == 2
    assert valid["row_hash"].is_unique
