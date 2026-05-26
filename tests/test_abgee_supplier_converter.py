from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.suppliers.abgee import convert_supplier


def _write_abgee_workbook(path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "Supply Code": "985 49830",
                    "Name": "Funko POP Leatherface",
                    "Barcode": "889698498302",
                    "CPU": "GBP 7.59",
                    "Available": "8",
                },
                {
                    "Supply Code": "888 PKW3402",
                    "Name": "Pokemon Figure",
                    "Barcode": "191726507185",
                    "CPU": "0",
                    "Available": "12",
                },
                {
                    "Supply Code": "541 61176",
                    "Name": "Shaun Backpack Clip",
                    "Barcode": "",
                    "CPU": "4.20",
                    "Available": "3",
                },
                {
                    "Supply Code": "DUP 1",
                    "Name": "Duplicate A",
                    "Barcode": "5012345678900",
                    "CPU": "2.50",
                    "Available": "1",
                },
                {
                    "Supply Code": "DUP 1",
                    "Name": "Duplicate B",
                    "Barcode": "5012345678901",
                    "CPU": "2.75",
                    "Available": "1",
                },
            ]
        ).to_excel(writer, index=False, sheet_name="Price List")


def test_abgee_converter_maps_good_rows_and_holds_bad_rows(tmp_path: Path) -> None:
    source = tmp_path / "abgee.xlsx"
    _write_abgee_workbook(source)

    valid, holds = convert_supplier(
        source,
        supplier_id="abgee",
        supplier_name="ABGee",
        source_url="",
        source_seen_at_utc="2026-05-22T09:00:00Z",
    )

    assert len(valid.index) == 1
    row = valid.iloc[0]
    assert row["supplier_sku"] == "985 49830"
    assert row["supplier_title"] == "Funko POP Leatherface"
    assert row["barcode"] == "889698498302"
    assert row["unit_cost"] == "7.59"
    assert row["stock_available"] == "8"
    assert row["currency"] == "GBP"

    hold_by_sku = holds.set_index("supplier_sku")
    assert "zero_cost" in hold_by_sku.loc["888 PKW3402", "hold_reason_codes"]
    assert "missing_barcode" in hold_by_sku.loc["541 61176", "hold_reason_codes"]
    assert "duplicate_supply_code" in hold_by_sku.loc["DUP 1", "hold_reason_codes"].iloc[0]
    assert "duplicate_supply_code" in hold_by_sku.loc["DUP 1", "hold_reason_codes"].iloc[1]


def test_abgee_converter_reads_csv_inside_zip(tmp_path: Path) -> None:
    csv_text = (
        "Supply Code,Name,Barcode,Trade Price,Stock\n"
        "333 SI5038,Mr Monopoly POP,810010991225,£4.16,6\n"
    )
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("abgee_daily.csv", csv_text)
    source = tmp_path / "abgee.zip"
    source.write_bytes(archive_bytes.getvalue())

    valid, holds = convert_supplier(
        source,
        supplier_id="abgee",
        supplier_name="ABGee",
        source_url="",
        source_seen_at_utc="2026-05-22T09:00:00Z",
    )

    assert holds.empty
    assert len(valid.index) == 1
    assert valid.iloc[0]["supplier_sku"] == "333 SI5038"
    assert valid.iloc[0]["barcode"] == "810010991225"
    assert valid.iloc[0]["unit_cost"] == "4.16"


def test_abgee_converter_divides_pack_trade_price_to_unit_cost(tmp_path: Path) -> None:
    source = tmp_path / "abgee_pack.xlsx"
    with pd.ExcelWriter(source, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "Product Code": "211 1910046",
                    "Product Name": "Bluey 2 in 1 Mega Bubble Wands",
                    "Unit Code": "PK12",
                    "Qty": "72",
                    "Barcode": "5015935004660",
                    "Trade": "39.96",
                }
            ]
        ).to_excel(writer, index=False, sheet_name="ABGee Stock Feed")

    valid, holds = convert_supplier(
        source,
        supplier_id="abgee",
        supplier_name="ABGee",
        source_url="",
        source_seen_at_utc="2026-05-21T14:47:06Z",
    )

    assert holds.empty
    row = valid.iloc[0]
    assert row["supplier_sku"] == "211 1910046"
    assert row["unit_code"] == "PK12"
    assert row["pack_size"] == "12"
    assert row["pack_cost"] == "39.96"
    assert row["unit_cost"] == "3.33"
    assert row["moq"] == "12"
    assert "abgee_pack_cost_divided_to_unit_cost" in row["notes"]
