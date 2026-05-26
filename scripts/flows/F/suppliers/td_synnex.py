from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


TD_COLUMNS_20 = [
    "Product ID",
    "SKU",
    "Brand",
    "Description",
    "Cost Price",
    "Selling Price",
    "Currency",
    "Timestamp",
    "Stock Level",
    "Stock Date",
    "Category Code",
    "Availability",
    "Category Description",
    "End User",
    "EAN",
    "Special",
    "Department",
    "Subcategory",
    "Restricted",
    "Weight (kg)",
]
TD_COLUMNS_21 = [
    "Product ID",
    "SKU",
    "Brand",
    "Description",
    "Cost Price",
    "Selling Price",
    "Currency",
    "Timestamp",
    "Stock Level",
    "Stock Date",
    "Category Code",
    "Availability",
    "Category Description",
    "End User",
    "End User Flag",
    "EAN",
    "Special",
    "Department",
    "Subcategory",
    "Restricted",
    "Weight (kg)",
]

SUPPORTED_SUFFIXES = {".csv", ".tsv", ".txt"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _read_tsv_with_fallback(path: Path) -> pd.DataFrame:
    def _read(encoding: str) -> pd.DataFrame:
        raw = pd.read_csv(path, sep="\t", header=None, dtype=str, encoding=encoding).fillna("")
        if raw.empty:
            return raw
        column_count = len(raw.columns)
        if column_count == len(TD_COLUMNS_21):
            raw.columns = TD_COLUMNS_21
        elif column_count == len(TD_COLUMNS_20):
            raw.columns = TD_COLUMNS_20
        else:
            names = TD_COLUMNS_21 if column_count > len(TD_COLUMNS_20) else TD_COLUMNS_20
            raw = pd.read_csv(path, sep="\t", header=None, names=names, dtype=str, encoding=encoding).fillna("")
        return raw

    try:
        df = _read("utf-8-sig")
    except UnicodeDecodeError:
        df = _read("latin1")
    if df.empty:
        return df

    first = df.iloc[0]
    looks_like_header = _normalize_lower(first.get("SKU", "")) == "sku" and _normalize_lower(
        first.get("Description", "")
    ) in {"description", "product name"}
    if looks_like_header:
        df = df.iloc[1:].copy()
    return df


def _clean_barcode(value: object) -> str:
    raw = _normalize_text(value)
    if not raw:
        return ""
    raw = raw.replace("EAN", "").replace("UPC", "")
    raw = raw.replace("ean", "").replace("upc", "")
    return "".join(ch for ch in raw if ch.isdigit())


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _parse_cost(value: object) -> str:
    raw = _normalize_text(value)
    if not raw:
        return ""
    cleaned = raw.replace("Â£", "").replace("$", "").replace("â‚¬", "")
    cleaned = cleaned.replace(",", "").strip()
    try:
        parsed = float(cleaned)
    except ValueError:
        return ""
    if parsed <= 0:
        return ""
    return f"{parsed:.2f}"


def _parse_stock(value: object) -> str:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return ""
    try:
        amount = int(float(raw))
    except ValueError:
        return ""
    return str(max(amount, 0))


def _row_hash(parts: Iterable[str]) -> str:
    joined = "|".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


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
    skips = {(_normalize_text(suffix).upper()) for suffix in (skip_sku_suffixes or []) if suffix}

    df = _read_tsv_with_fallback(raw_path)
    if df.empty:
        empty_valid = pd.DataFrame(
            columns=[
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
            ]
        )
        empty_holds = pd.DataFrame(
            columns=[
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
            ]
        )
        return empty_valid, empty_holds

    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    for _, row in df.iterrows():
        sku = _normalize_text(row.get("SKU", "")).upper()
        title = _normalize_text(row.get("Description", ""))
        brand = _normalize_text(row.get("Brand", ""))
        category = _normalize_text(row.get("Category Description", ""))
        stock_available = _parse_stock(row.get("Stock Level", ""))
        barcode = _clean_barcode(row.get("EAN", ""))
        cost = _parse_cost(row.get("Cost Price", ""))

        reasons: list[str] = []
        if not sku:
            reasons.append("missing_sku")
        if sku and any(sku.endswith(suffix) for suffix in skips):
            reasons.append("sku_suffix_blocked")
        if barcode and not _is_valid_barcode(barcode):
            barcode = ""
        if not cost:
            reasons.append("missing_cost")

        row_payload = {
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
            "brand": brand,
            "stock_available": stock_available,
            "category": category,
        }

        if reasons:
            hold_rows.append(
                {
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "supplier_sku": sku,
                    "supplier_title": title,
                    "barcode": barcode,
                    "unit_cost": cost,
                    "hold_reason_codes": "|".join(reasons),
                    "source_url": source_url,
                    "source_file_path": str(raw_path),
                    "source_seen_at_utc": source_seen,
                    "normalized_utc": normalized_utc,
                    "brand": brand,
                    "stock_available": stock_available,
                    "category": category,
                }
            )
            continue

        row_hash = _row_hash([supplier_id, sku, barcode, cost, title, brand])
        row_payload["row_hash"] = row_hash
        row_payload["is_valid_source_row"] = "1"
        valid_rows.append(row_payload)

    valid_df = pd.DataFrame(valid_rows)
    holds_df = pd.DataFrame(hold_rows)
    return valid_df, holds_df
