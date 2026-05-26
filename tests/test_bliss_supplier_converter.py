from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.suppliers.bliss_distribution import convert_supplier


def _write_bliss_workbook(path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "Inventory ID": "cha2038h",
                    "Inventory Barcode #": "9781568825328",
                    "Description": "Age of Vikings",
                    "Price": "28.565",
                    "RRP": "52.99",
                },
                {
                    "Inventory ID": "badbarcode",
                    "Inventory Barcode #": "0000000000",
                    "Description": "Invalid barcode",
                    "Price": "1.23",
                    "RRP": "2.99",
                },
                {
                    "Inventory ID": "nocost",
                    "Inventory Barcode #": "672975032241",
                    "Description": "No cost",
                    "Price": "",
                    "RRP": "18.99",
                },
            ]
        ).to_excel(writer, index=False, sheet_name="Data")
        pd.DataFrame(
            [
                {"Title:": "Company:", "Inventory Items over 5 Available": "Bliss"},
                {"Title:": "Date:", "Inventory Items over 5 Available": "07 Jan 2026 08:36 AM GMT+00:00"},
            ]
        ).to_excel(writer, index=False, sheet_name="Parameters")


def test_bliss_converter_normalizes_excel_to_universal_rows(tmp_path: Path) -> None:
    raw_path = tmp_path / "bliss.xlsx"
    _write_bliss_workbook(raw_path)

    valid, holds = convert_supplier(
        raw_path,
        supplier_id="bliss_distribution",
        supplier_name="Bliss Distribution",
        source_url="",
        source_seen_at_utc="2026-04-30T12:30:00Z",
    )

    assert len(valid.index) == 1
    assert len(holds.index) == 2
    row = valid.iloc[0]
    assert row["supplier_sku"] == "CHA2038H"
    assert row["barcode"] == "9781568825328"
    assert row["unit_cost"] == "28.57"
    assert row["currency"] == "GBP"
    assert row["category"] == "stock_list"
    assert "rrp=52.99" in row["notes"]
    assert valid["row_hash"].nunique() == 1

    hold_by_sku = holds.set_index("supplier_sku")
    assert "invalid_barcode_format" in hold_by_sku.loc["BADBARCODE", "hold_reason_codes"]
    assert "missing_or_invalid_cost" in hold_by_sku.loc["NOCOST", "hold_reason_codes"]


def test_bliss_converter_handles_full_stock_export_without_barcode_column(tmp_path: Path) -> None:
    raw_path = tmp_path / "bliss_full_stock.xlsx"
    with pd.ExcelWriter(raw_path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "Inventory ID": "cha2038h",
                    "Description": "Age of Vikings",
                    "Release Date": "",
                    "Item Class": "RPG",
                    "MSRP": "52.99",
                    "Base Price": "28.565",
                }
            ]
        ).to_excel(writer, index=False, sheet_name="Data")

    valid, holds = convert_supplier(
        raw_path,
        supplier_id="bliss_distribution",
        supplier_name="Bliss Distribution",
        source_url="",
        source_seen_at_utc="2026-05-18T09:45:00Z",
    )

    assert len(valid.index) == 0
    assert len(holds.index) == 1
    row = holds.iloc[0]
    assert row["supplier_sku"] == "CHA2038H"
    assert row["unit_cost"] == "28.57"
    assert row["hold_reason_codes"] == "missing_barcode"
    assert "rrp=52.99" in row["notes"]
