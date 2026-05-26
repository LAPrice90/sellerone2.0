from __future__ import annotations

import base64
import csv
import hashlib
import ast
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


SUPPORTED_SUFFIXES = {".csv", ".txt"}
DEFAULT_BASE_URL = "https://integrate.heo.com/retailer-api/v1/catalog"


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
        .replace("N/A", "")
        .replace("n/a", "")
        .strip()
    )
    try:
        parsed = float(cleaned)
    except ValueError:
        return ""
    if parsed <= 0:
        return ""
    return f"{parsed:.2f}"


def _transform_vat_type(value: object) -> str:
    raw = _normalize_text(value).upper()
    if raw == "REDUCED":
        return "0"
    if raw == "NORMAL":
        return "20"
    cleaned = _clean_price(raw)
    return cleaned if cleaned else ""


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _row_hash(parts: Iterable[str]) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _basic_auth_headers(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "User-Agent": "SellerOne-FPM/1.0",
    }


def _fetch_json(url: str, headers: dict[str, str], timeout_seconds: int) -> dict[str, object]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("heo_api_response_not_object")
    return data


def _fetch_all_pages(endpoint_url: str, headers: dict[str, str], timeout_seconds: int) -> list[dict[str, object]]:
    all_rows: list[dict[str, object]] = []
    current_page = 1
    total_pages = 1
    while current_page <= total_pages:
        separator = "&" if "?" in endpoint_url else "?"
        page_url = f"{endpoint_url}{separator}page={current_page}"
        data = _fetch_json(page_url, headers, timeout_seconds)
        content = data.get("content", [])
        if not isinstance(content, list):
            raise ValueError("heo_api_content_not_list")
        all_rows.extend(row for row in content if isinstance(row, dict))
        pagination = data.get("pagination", {})
        if isinstance(pagination, dict):
            try:
                total_pages = max(int(pagination.get("totalPages", 1) or 1), 1)
            except ValueError:
                total_pages = 1
        current_page += 1
    return all_rows


def _price_amount(price_row: dict[str, object]) -> str:
    value = price_row.get("basePricePerUnit", "")
    if isinstance(value, dict):
        return _clean_price(value.get("amount", ""))
    return _clean_price(value)


def _barcode_values(product_row: dict[str, object]) -> list[str]:
    barcodes = product_row.get("barcodes", [])
    if not isinstance(barcodes, list):
        return []
    values: list[str] = []
    for barcode_obj in barcodes:
        if isinstance(barcode_obj, dict):
            barcode = _clean_barcode(barcode_obj.get("barcode", ""))
        else:
            barcode = _clean_barcode(barcode_obj)
        if barcode:
            values.append(barcode)
    return values


def _product_title(product_row: dict[str, object]) -> str:
    for key in ["title", "name", "productName", "description"]:
        value = _title_from_value(product_row.get(key, ""))
        if value:
            return value
    return ""


def _title_from_value(value: object) -> str:
    if isinstance(value, list):
        translations = value
    else:
        raw = _normalize_text(value)
        if not raw:
            return ""
        if raw.startswith("[") and "translation" in raw:
            try:
                parsed = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                return raw
            translations = parsed if isinstance(parsed, list) else []
        else:
            return raw

    fallback = ""
    for item in translations:
        if not isinstance(item, dict):
            continue
        translation = _normalize_text(item.get("translation", ""))
        if not translation:
            continue
        if _normalize_text(item.get("langIso2", "")).upper() == "EN":
            return translation
        if not fallback:
            fallback = translation
    return fallback


def fetch_api_source(
    destination: Path,
    *,
    username: str,
    password: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    headers = _basic_auth_headers(username, password)
    clean_base = base_url.rstrip("/")
    products = _fetch_all_pages(f"{clean_base}/products", headers, timeout_seconds)
    prices = _fetch_all_pages(f"{clean_base}/prices", headers, timeout_seconds)
    price_map = {
        _normalize_text(price.get("productNumber", "")): _price_amount(price)
        for price in prices
        if _normalize_text(price.get("productNumber", ""))
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["productNumber", "barcodes", "basePricePerUnit", "vatType", "Supplier", "supplierTitle"]
    rows_written = 0
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for product in products:
            product_number = _normalize_text(product.get("productNumber", ""))
            vat_rate = _transform_vat_type(product.get("vatType", ""))
            title = _product_title(product)
            price = price_map.get(product_number, "")
            barcodes = _barcode_values(product)
            if not barcodes:
                barcodes = [""]
            for barcode in barcodes:
                writer.writerow(
                    {
                        "productNumber": product_number,
                        "barcodes": barcode,
                        "basePricePerUnit": price,
                        "vatType": vat_rate,
                        "Supplier": "Heo",
                        "supplierTitle": title,
                    }
                )
                rows_written += 1

    return {
        "ok": True,
        "notes": f"products={len(products)};prices={len(prices)};expanded_rows={rows_written}",
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
        sku = _normalize_text(row.get("productNumber", "")).upper()
        barcode = _clean_barcode(row.get("barcodes", ""))
        cost = _clean_price(row.get("basePricePerUnit", ""))
        source_vat_rate = _transform_vat_type(row.get("vatType", "")) or str(vat_rate)
        title = _title_from_value(row.get("supplierTitle", ""))

        reasons: list[str] = []
        if not sku:
            reasons.append("missing_sku")
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
            "notes": "source=heo_api",
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
