from __future__ import annotations

import sys
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.suppliers.heo import convert_supplier


def test_heo_converter_normalizes_expanded_api_csv(tmp_path: Path) -> None:
    source = tmp_path / "heo.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["productNumber", "barcodes", "basePricePerUnit", "vatType", "Supplier", "supplierTitle"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "productNumber": "H001",
                "barcodes": "4005555000001",
                "basePricePerUnit": "12.345",
                "vatType": "NORMAL",
                "Supplier": "Heo",
                "supplierTitle": "Board Game",
            }
        )
        writer.writerow(
            {
                "productNumber": "H002",
                "barcodes": "4005555000002",
                "basePricePerUnit": "4.5",
                "vatType": "REDUCED",
                "Supplier": "Heo",
                "supplierTitle": "[{'langIso2': 'DE', 'translation': 'Kartenspiel'}, {'langIso2': 'EN', 'translation': 'Card Game'}]",
            }
        )
        writer.writerow(
            {
                "productNumber": "H003",
                "barcodes": "",
                "basePricePerUnit": "2.00",
                "vatType": "NORMAL",
                "Supplier": "Heo",
                "supplierTitle": "Missing Barcode",
            }
        )
        writer.writerow(
            {
                "productNumber": "H004",
                "barcodes": "123",
                "basePricePerUnit": "1.00",
                "vatType": "NORMAL",
                "Supplier": "Heo",
                "supplierTitle": "Bad Barcode",
            }
        )
        writer.writerow(
            {
                "productNumber": "H005",
                "barcodes": "4005555000005",
                "basePricePerUnit": "N/A",
                "vatType": "NORMAL",
                "Supplier": "Heo",
                "supplierTitle": "Missing Price",
            }
        )

    valid, holds = convert_supplier(
        source,
        supplier_id="heo",
        supplier_name="Heo",
        source_url="https://integrate.heo.com/retailer-api/v1/catalog",
        source_seen_at_utc="2026-04-30T15:00:00Z",
    )

    assert len(valid.index) == 2
    assert len(holds.index) == 3
    by_sku = valid.set_index("supplier_sku")
    assert by_sku.loc["H001", "unit_cost"] == "12.35"
    assert by_sku.loc["H001", "vat_rate"] == "20"
    assert by_sku.loc["H002", "unit_cost"] == "4.50"
    assert by_sku.loc["H002", "vat_rate"] == "0"
    assert by_sku.loc["H002", "supplier_title"] == "Card Game"
    assert set(holds["hold_reason_codes"]) == {
        "missing_barcode",
        "invalid_barcode_format",
        "missing_or_invalid_cost",
    }
