from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.suppliers.stax import convert_supplier


def test_stax_converter_uses_second_csv_row_as_product_header(tmp_path: Path) -> None:
    source = tmp_path / "stax.csv"
    source.write_text(
        "DocumentVersion,MessageType,Author,Recipient_account,Recipient,PublishDateTime_canonical,PublishDateTime\n"
        "Action,Item,VatPercentage,ExcludeDiscount,Discontinued,ProductCode,Brand,Title,Variant,Specification,Barcode,ProductType,YourPrice_currency,YourPrice,PackQuantity\n"
        '"1.3","Product","Stax Trade Centres","4/18781","DRJ HARDWARE LTD",2026-04-30 11:36:18,\n'
        "Insert,,20.00,No,No,SCF12A,SupaCool,Oscillating Desk Fan,12 inch,,5017193424358,Cooling,GBP,12.37,1\n"
        "Insert,,20.00,No,No,BADBAR,Brand,Bad Barcode,,,123,Cooling,GBP,1.20,1\n"
        "Insert,,20.00,No,Yes,DISC1,Brand,Old Product,,,5017193424359,Cooling,GBP,1.20,1\n",
        encoding="utf-8",
    )

    valid, holds = convert_supplier(
        source,
        supplier_id="stax",
        supplier_name="Stax",
        source_url="https://example.test/product.csv",
        source_seen_at_utc="2026-04-30T14:00:00Z",
    )

    assert len(valid.index) == 1
    assert len(holds.index) == 2
    row = valid.iloc[0]
    assert row["supplier_sku"] == "SCF12A"
    assert row["supplier_title"] == "SupaCool Oscillating Desk Fan 12 inch"
    assert row["barcode"] == "5017193424358"
    assert row["unit_cost"] == "12.37"
    assert row["currency"] == "GBP"
    assert row["vat_rate"] == "20.00"
    assert row["category"] == "Cooling"
    assert set(holds["hold_reason_codes"]) == {"invalid_barcode_format", "discontinued"}
