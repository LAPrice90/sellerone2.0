from __future__ import annotations

import csv
import hashlib
import html
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


SUPPORTED_SUFFIXES = {".csv", ".txt"}
DEFAULT_BASE_URL = "http://services.clfdistribution.com:8080/CLFWebOrdering/WebOrdering.asmx"
NAMESPACE = "http://services.clfdistribution.com/CLFWebOrdering"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _clean_barcode(value: object) -> str:
    raw = _normalize_text(value)
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    return "".join(char for char in raw if char.isdigit())


def _clean_price(value: object) -> str:
    raw = _normalize_text(value)
    if not raw:
        return ""
    cleaned = (
        raw.replace(",", "")
        .replace(chr(163), "")
        .replace("$", "")
        .replace("GBP", "")
        .replace("gbp", "")
        .strip()
    )
    try:
        parsed = float(cleaned)
    except ValueError:
        return ""
    if parsed <= 0:
        return ""
    return f"{parsed:.2f}"


def _convert_vat(value: object) -> str:
    raw = _normalize_text(value).upper()
    if raw == "STD":
        return "20"
    if raw == "ZERO":
        return "0"
    cleaned = _clean_price(raw)
    return cleaned if cleaned else raw


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _row_hash(parts: Iterable[str]) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _soap_envelope(token: str, body: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        "<soap:Header>"
        f'<WebServiceHeader xmlns="{NAMESPACE}">'
        f"<AuthenticationToken>{html.escape(token)}</AuthenticationToken>"
        "</WebServiceHeader>"
        "</soap:Header>"
        f"<soap:Body>{body}</soap:Body>"
        "</soap:Envelope>"
    )


def _auth_soap_envelope(username: str, password: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
        "<soap:Header>"
        f'<WebServiceHeader xmlns="{NAMESPACE}" />'
        "</soap:Header>"
        "<soap:Body>"
        f'<GetAuthenticationToken xmlns="{NAMESPACE}">'
        f"<Username>{html.escape(username)}</Username>"
        f"<Password>{html.escape(password)}</Password>"
        "</GetAuthenticationToken>"
        "</soap:Body>"
        "</soap:Envelope>"
    )


def _post_auth_soap(base_url: str, username: str, password: str, timeout_seconds: int) -> str:
    payload = _auth_soap_envelope(username, password).encode("utf-8")
    request = urllib.request.Request(
        base_url,
        data=payload,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"{NAMESPACE}/GetAuthenticationToken",
            "User-Agent": "SellerOne-FPM/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def _post_soap(base_url: str, action: str, body: str, token: str, timeout_seconds: int) -> str:
    payload = _soap_envelope(token, body).encode("utf-8")
    request = urllib.request.Request(
        base_url,
        data=payload,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"{NAMESPACE}/{action}",
            "User-Agent": "SellerOne-FPM/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml_fragment(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError:
        repaired = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;|#x[0-9A-Fa-f]+;)", "&amp;", xml_text)
        return ET.fromstring(repaired)


def _find_result_text(response_text: str, result_tag: str) -> str:
    root = _parse_xml_fragment(response_text)
    for element in root.iter():
        if _local_name(element.tag) == result_tag:
            return html.unescape(element.text or "")
    raise ValueError(f"missing_{result_tag}")


def _get_auth_token(base_url: str, username: str, password: str, timeout_seconds: int) -> str:
    response_text = _post_auth_soap(base_url, username, password, timeout_seconds)
    token = _normalize_text(_find_result_text(response_text, "GetAuthenticationTokenResult"))
    if not token:
        raise ValueError("clf_auth_token_empty")
    return token


def _text_child(element: ET.Element, name: str) -> str:
    for child in element:
        if _local_name(child.tag).lower() == name.lower():
            return _normalize_text(child.text or "")
    return ""


def _first_text_child(element: ET.Element, names: Iterable[str]) -> str:
    for name in names:
        value = _text_child(element, name)
        if value:
            return value
    return ""


def _parse_skus(product_codes_xml: str) -> list[str]:
    root = _parse_xml_fragment(product_codes_xml)
    skus: list[str] = []
    for code in root.iter():
        if _local_name(code.tag) != "Code":
            continue
        sku = _text_child(code, "sku")
        if sku:
            skus.append(sku)
    return skus


def _parse_products(product_data_xml: str) -> list[dict[str, str]]:
    root = _parse_xml_fragment(product_data_xml)
    rows: list[dict[str, str]] = []
    for product in root.iter():
        if _local_name(product.tag) != "Product":
            continue
        rows.append(
            {
                "SKU": _text_child(product, "sku"),
                "Title": _first_text_child(
                    product,
                    (
                        "description",
                        "productdescription",
                        "product_description",
                        "productname",
                        "product_name",
                        "name",
                    ),
                ),
                "Barcode": _text_child(product, "barcode"),
                "Cost": _text_child(product, "price"),
                "VAT": _convert_vat(_text_child(product, "taxcode")),
                "CLF": "CLF",
            }
        )
    return rows


def _product_codes_xml(skus: list[str]) -> str:
    inner = "".join(f"<Code><sku>{html.escape(sku)}</sku></Code>" for sku in skus)
    return f"<ProductCodes>{inner}</ProductCodes>"


def fetch_api_source(
    destination: Path,
    *,
    username: str = "",
    password: str = "",
    auth_token: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: int = 60,
    batch_size: int = 250,
    sleep_seconds: float = 1.5,
) -> dict[str, object]:
    token = _normalize_text(auth_token)
    if not token:
        if not _normalize_text(username) or not _normalize_text(password):
            raise ValueError("clf_api_credentials_missing")
        token = _get_auth_token(base_url, username, password, timeout_seconds)

    codes_body = f'<GetProductCodes xmlns="{NAMESPACE}"/>'
    codes_response = _post_soap(base_url, "GetProductCodes", codes_body, token, timeout_seconds)
    codes_xml = _find_result_text(codes_response, "GetProductCodesResult")
    skus = _parse_skus(codes_xml)

    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["SKU", "Title", "Barcode", "Cost", "VAT", "CLF"]
    rows_written = 0
    blank_barcode_rows = 0
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for start in range(0, len(skus), batch_size):
            batch = skus[start : start + batch_size]
            product_codes = _product_codes_xml(batch)
            data_body = (
                f'<GetProductData xmlns="{NAMESPACE}">'
                f"<productCodesXml><![CDATA[{product_codes}]]></productCodesXml>"
                "</GetProductData>"
            )
            data_response = _post_soap(base_url, "GetProductData", data_body, token, timeout_seconds)
            data_xml = _find_result_text(data_response, "GetProductDataResult")
            for row in _parse_products(data_xml):
                if not _clean_barcode(row.get("Barcode", "")):
                    blank_barcode_rows += 1
                    continue
                writer.writerow(row)
                rows_written += 1
            if sleep_seconds > 0 and start + batch_size < len(skus):
                time.sleep(sleep_seconds)

    return {
        "ok": True,
        "notes": f"skus={len(skus)};rows={rows_written};blank_barcode_rows={blank_barcode_rows}",
        "bytes": destination.stat().st_size,
        "rows": rows_written,
    }


def _empty_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    valid_columns = [
        "supplier_id",
        "supplier_name",
        "supplier_sku",
        "supplier_title",
        "barcode",
        "unit_cost",
        "currency",
        "vat_rate",
        "source_url",
        "source_file_path",
        "source_seen_at_utc",
        "row_hash",
        "is_valid_source_row",
        "normalized_utc",
        "brand",
        "stock_available",
        "category",
        "notes",
    ]
    hold_columns = [
        "supplier_id",
        "supplier_name",
        "supplier_sku",
        "supplier_title",
        "barcode",
        "unit_cost",
        "hold_reason_codes",
        "source_url",
        "source_file_path",
        "source_seen_at_utc",
        "normalized_utc",
        "brand",
        "stock_available",
        "category",
        "notes",
    ]
    return pd.DataFrame(columns=valid_columns), pd.DataFrame(columns=hold_columns)


def convert_supplier(
    raw_path: Path,
    *,
    supplier_id: str,
    supplier_name: str,
    source_url: str,
    source_seen_at_utc: str | None = None,
    currency: str = "GBP",
    vat_rate: str = "20",
    skip_sku_suffixes: Iterable[str] | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    source_seen = source_seen_at_utc or _utc_now_iso()
    normalized_utc = _utc_now_iso()
    skips = {_normalize_text(suffix).upper() for suffix in (skip_sku_suffixes or []) if suffix}
    df = pd.read_csv(raw_path, dtype=str, encoding="utf-8-sig").fillna("")
    if df.empty:
        return _empty_frames()

    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    for _, row in df.iterrows():
        sku = _normalize_text(row.get("SKU", "")).upper()
        title = (
            _normalize_text(row.get("Title", ""))
            or _normalize_text(row.get("Description", ""))
            or _normalize_text(row.get("Product Description", ""))
            or _normalize_text(row.get("Product Name", ""))
        )
        barcode = _clean_barcode(row.get("Barcode", ""))
        cost = _clean_price(row.get("Cost", ""))
        source_vat_rate = _convert_vat(row.get("VAT", "")) or str(vat_rate)

        reasons: list[str] = []
        if not sku:
            reasons.append("missing_sku")
        if not title:
            reasons.append("missing_title")
        if sku and any(sku.endswith(suffix) for suffix in skips):
            reasons.append("sku_suffix_blocked")
        if not barcode:
            reasons.append("missing_barcode")
        elif not _is_valid_barcode(barcode):
            reasons.append("invalid_barcode_format")
        if not cost:
            reasons.append("missing_or_invalid_cost")

        base = {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_sku": sku,
            "supplier_title": title,
            "barcode": barcode,
            "unit_cost": cost,
            "currency": currency,
            "vat_rate": source_vat_rate,
            "source_url": source_url,
            "source_file_path": str(raw_path),
            "source_seen_at_utc": source_seen,
            "normalized_utc": normalized_utc,
            "brand": "",
            "stock_available": "",
            "category": "catalog",
            "notes": "source=clf_api",
        }

        if reasons:
            hold = dict(base)
            hold.pop("currency", None)
            hold.pop("vat_rate", None)
            hold["hold_reason_codes"] = "|".join(reasons)
            hold_rows.append(hold)
            continue

        base["row_hash"] = _row_hash([supplier_id, sku, barcode, cost, source_vat_rate, title])
        base["is_valid_source_row"] = "1"
        valid_rows.append(base)

    return pd.DataFrame(valid_rows), pd.DataFrame(hold_rows)
