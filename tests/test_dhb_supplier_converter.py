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

from scripts.flows.F.suppliers.dhb import convert_supplier


def _write_dhb_workbook(path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "No.": "ama006",
                    "Description": "CB12 SENSITIVE MOUTHRINSE 250ML",
                    "Barcode": "EAN: 5060035249282",
                    "Trade Price": "2.955056179775281",
                    "Unnamed: 4": "",
                },
                {
                    "No.": "ama007",
                    "Description": "Missing barcode product",
                    "Barcode": "",
                    "Trade Price": "GBP 1.20",
                    "Unnamed: 4": "",
                },
            ]
        ).to_excel(writer, index=False, sheet_name="Trade Price")
        pd.DataFrame(
            [
                {
                    "No.": "aur112",
                    "Description": "AURELIA BOLD BLACK NITRILE PF MEDIUM 100 BOX",
                    "Available Stock": "80",
                    "Clearance Price": "3.65",
                    "Barcode ": "9555002105211",
                },
                {
                    "No.": "car100",
                    "Description": "DISPOSABLE ISOLATION GOWN",
                    "Available Stock": "145",
                    "Clearance Price": "bad",
                    "Barcode ": "",
                },
            ]
        ).to_excel(writer, index=False, sheet_name="End of Line - Whilst Stocks Las")


def test_dhb_converter_normalizes_excel_to_universal_rows(tmp_path: Path) -> None:
    raw_path = tmp_path / "dhb.xlsx"
    _write_dhb_workbook(raw_path)

    valid, holds = convert_supplier(
        raw_path,
        supplier_id="dhb",
        supplier_name="DHB",
        source_url="",
        source_seen_at_utc="2026-04-30T12:00:00Z",
    )

    assert len(valid.index) == 2
    assert len(holds.index) == 2
    by_sku = valid.set_index("supplier_sku")
    assert by_sku.loc["AMA006", "barcode"] == "5060035249282"
    assert by_sku.loc["AMA006", "unit_cost"] == "2.96"
    assert by_sku.loc["AMA006", "currency"] == "GBP"
    assert by_sku.loc["AMA006", "category"] == "trade_price"
    assert by_sku.loc["AUR112", "unit_cost"] == "3.65"
    assert by_sku.loc["AUR112", "stock_available"] == "80"
    assert by_sku.loc["AUR112", "category"] == "clearance"
    assert valid["row_hash"].nunique() == 2

    hold_by_sku = holds.set_index("supplier_sku")
    assert "missing_barcode" in hold_by_sku.loc["AMA007", "hold_reason_codes"]
    assert "missing_barcode" in hold_by_sku.loc["CAR100", "hold_reason_codes"]
    assert "missing_or_invalid_cost" in hold_by_sku.loc["CAR100", "hold_reason_codes"]
