from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_key(value: object) -> str:
    raw = _normalize_text(value).lower()
    out = []
    for char in raw:
        out.append(char if char.isalnum() else "_")
    return "_".join(part for part in "".join(out).split("_") if part)


def _find_column(headers: list[str], candidates: Iterable[str]) -> str:
    normalized = {_normalize_key(header): header for header in headers}
    for candidate in candidates:
        key = _normalize_key(candidate)
        if key in normalized:
            return normalized[key]
    for candidate in candidates:
        key = _normalize_key(candidate)
        for header in headers:
            if key and key in _normalize_key(header):
                return header
    raise ValueError(f"missing expected Bliss column. Tried: {', '.join(candidates)}")


def _find_optional_column(headers: list[str], candidates: Iterable[str]) -> str:
    try:
        return _find_column(headers, candidates)
    except ValueError:
        return ""


def _clean_barcode(value: object) -> str:
    raw = _normalize_text(value)
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    return "".join(char for char in raw if char.isdigit())


def _clean_price(value: object) -> str:
    raw = _normalize_text(value)
    if raw == "":
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


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _row_hash(parts: Iterable[str]) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


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


def _read_data_sheet(path: Path) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, dtype=str, engine="openpyxl")
    for sheet_name, df in sheets.items():
        if sheet_name.strip().lower() == "data" and not df.empty:
            return df.fillna("")
    non_empty = [df.fillna("") for df in sheets.values() if not df.empty]
    return non_empty[0] if non_empty else pd.DataFrame()


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
    df = _read_data_sheet(raw_path)
    if df.empty:
        return _empty_frames()

    headers = list(df.columns)
    sku_col = _find_column(headers, ["Inventory ID", "SKU", "Product Code", "Item Code"])
    barcode_col = _find_optional_column(headers, ["Inventory Barcode #", "Barcode", "EAN", "UPC"])
    title_col = _find_column(headers, ["Description", "Title", "Product Description"])
    price_col = _find_column(headers, ["Base Price", "Price", "Trade Price", "Cost", "Unit Cost"])
    rrp_col = _find_optional_column(headers, ["RRP", "MSRP"])

    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    for _, row in df.iterrows():
        sku = _normalize_text(row.get(sku_col, "")).upper()
        title = _normalize_text(row.get(title_col, ""))
        barcode = _clean_barcode(row.get(barcode_col, "")) if barcode_col else ""
        cost = _clean_price(row.get(price_col, ""))
        rrp = _clean_price(row.get(rrp_col, "")) if rrp_col else ""

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
            "vat_rate": str(vat_rate),
            "source_url": source_url,
            "source_file_path": str(raw_path),
            "source_seen_at_utc": source_seen,
            "normalized_utc": normalized_utc,
            "brand": "",
            "stock_available": "",
            "category": "stock_list",
            "notes": f"source_sheet=Data|rrp={rrp}",
        }

        if reasons:
            hold = dict(base)
            hold.pop("currency", None)
            hold.pop("vat_rate", None)
            hold["hold_reason_codes"] = "|".join(reasons)
            hold_rows.append(hold)
            continue

        base["row_hash"] = _row_hash([supplier_id, sku, barcode, cost, title])
        base["is_valid_source_row"] = "1"
        valid_rows.append(base)

    return pd.DataFrame(valid_rows), pd.DataFrame(hold_rows)
