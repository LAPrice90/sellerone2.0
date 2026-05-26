from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.suppliers.clf import _find_result_text, _parse_products, _parse_skus, convert_supplier


def test_clf_parses_sku_and_product_xml() -> None:
    skus = _parse_skus("<ProductCodes><Code><sku>ABC1</sku></Code><Code><sku>ABC2</sku></Code></ProductCodes>")
    products = _parse_products(
        "<Products>"
        "<Product><sku>ABC1</sku><description>Alpha Product</description><barcode>5012345678901</barcode><price>1.23</price><taxcode>STD</taxcode></Product>"
        "<Product><sku>ABC2</sku><description>Beta Product</description><barcode>5012345678902</barcode><price>2.34</price><taxcode>ZERO</taxcode></Product>"
        "</Products>"
    )

    assert skus == ["ABC1", "ABC2"]
    assert products == [
        {"SKU": "ABC1", "Title": "Alpha Product", "Barcode": "5012345678901", "Cost": "1.23", "VAT": "20", "CLF": "CLF"},
        {"SKU": "ABC2", "Title": "Beta Product", "Barcode": "5012345678902", "Cost": "2.34", "VAT": "0", "CLF": "CLF"},
    ]


def test_clf_parses_auth_token_response() -> None:
    response = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soap:Body>"
        '<GetAuthenticationTokenResponse xmlns="http://services.clfdistribution.com/CLFWebOrdering">'
        "<GetAuthenticationTokenResult>token-123</GetAuthenticationTokenResult>"
        "</GetAuthenticationTokenResponse>"
        "</soap:Body>"
        "</soap:Envelope>"
    )

    assert _find_result_text(response, "GetAuthenticationTokenResult") == "token-123"


def test_clf_repairs_raw_ampersand_in_product_xml() -> None:
    products = _parse_products(
        "<Products>"
        "<Product>"
        "<sku>A10</sku>"
        "<description>PinkRose & Vanilla Body Wash</description>"
        "<barcode>5055177534914</barcode>"
        "<price>1.23</price>"
        "<taxcode>STD</taxcode>"
        "</Product>"
        "</Products>"
    )

    assert products == [
        {"SKU": "A10", "Title": "PinkRose & Vanilla Body Wash", "Barcode": "5055177534914", "Cost": "1.23", "VAT": "20", "CLF": "CLF"}
    ]


def test_clf_converter_normalizes_generated_csv(tmp_path: Path) -> None:
    source = tmp_path / "clf.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["SKU", "Title", "Barcode", "Cost", "VAT", "CLF"])
        writer.writeheader()
        writer.writerow({"SKU": "ABC1", "Title": "Alpha Product", "Barcode": "5012345678901", "Cost": "1.234", "VAT": "STD", "CLF": "CLF"})
        writer.writerow({"SKU": "ABC2", "Title": "Bad barcode", "Barcode": "123", "Cost": "2.34", "VAT": "ZERO", "CLF": "CLF"})
        writer.writerow({"SKU": "ABC3", "Title": "Missing barcode", "Barcode": "", "Cost": "2.34", "VAT": "20", "CLF": "CLF"})
        writer.writerow({"SKU": "ABC4", "Title": "Missing cost", "Barcode": "5012345678904", "Cost": "", "VAT": "20", "CLF": "CLF"})
        writer.writerow({"SKU": "ABC5", "Title": "", "Barcode": "5012345678905", "Cost": "4.56", "VAT": "20", "CLF": "CLF"})

    valid, holds = convert_supplier(
        source,
        supplier_id="clf",
        supplier_name="CLF",
        source_url="http://services.clfdistribution.com:8080/CLFWebOrdering/WebOrdering.asmx",
        source_seen_at_utc="2026-04-30T16:00:00Z",
    )

    assert len(valid.index) == 1
    assert len(holds.index) == 4
    row = valid.iloc[0]
    assert row["supplier_sku"] == "ABC1"
    assert row["supplier_title"] == "Alpha Product"
    assert row["barcode"] == "5012345678901"
    assert row["unit_cost"] == "1.23"
    assert row["vat_rate"] == "20"
    assert set(holds["hold_reason_codes"]) == {
        "invalid_barcode_format",
        "missing_barcode",
        "missing_or_invalid_cost",
        "missing_title",
    }
