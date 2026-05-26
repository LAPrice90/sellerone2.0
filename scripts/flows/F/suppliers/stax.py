from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


SUPPORTED_SUFFIXES = {".csv", ".txt"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _first_existing(row: pd.Series, columns: Iterable[str]) -> str:
    for column in columns:
        if column in row.index:
            value = _normalize_text(row.get(column, ""))
            if value:
                return value
    return ""


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


def _clean_rate(value: object, fallback: str) -> str:
    cleaned = _clean_price(value)
    return cleaned if cleaned else str(fallback)


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _row_hash(parts: Iterable[str]) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _read_stax_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype=str, header=1, encoding="utf-8-sig").fillna("")
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, header=1, encoding="latin1").fillna("")


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
    df = _read_stax_csv(raw_path)
    if df.empty:
        return _empty_frames()

    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    for _, row in df.iterrows():
        action = _first_existing(row, ["Action"]).lower()
        sku = _first_existing(row, ["ProductCode", "Item"]).upper()
        barcode = _clean_barcode(_first_existing(row, ["Barcode"]))
        cost = _clean_price(_first_existing(row, ["YourPrice", "Price", "TradePrice"]))
        source_currency = _first_existing(row, ["YourPrice_currency", "Currency"]) or currency
        source_vat_rate = _clean_rate(_first_existing(row, ["VatPercentage", "VAT", "VatRate"]), vat_rate)
        brand = _first_existing(row, ["Brand"])
        title_parts = [
            brand,
            _first_existing(row, ["Title"]),
            _first_existing(row, ["Variant"]),
            _first_existing(row, ["Specification"]),
        ]
        title = " ".join(part for part in title_parts if part).strip()
        category = _first_existing(row, ["ProductType", "Category"]) or "stock_list"
        pack_quantity = _first_existing(row, ["PackQuantity"])
        discontinued = _first_existing(row, ["Discontinued"]).lower()
        exclude_discount = _first_existing(row, ["ExcludeDiscount"])

        # Stax puts a feed metadata row above the product rows. It has no real product code/barcode.
        if action not in {"", "insert", "update", "delete"}:
            continue
        if not sku and not barcode:
            continue

        reasons: list[str] = []
        if not sku:
            reasons.append("missing_sku")
        if sku and any(sku.endswith(suffix) for suffix in skips):
            reasons.append("sku_suffix_blocked")
        if action == "delete":
            reasons.append("delete_action")
        if discontinued in {"1", "true", "yes", "y"}:
            reasons.append("discontinued")
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
            "currency": source_currency,
            "vat_rate": source_vat_rate,
            "source_url": source_url,
            "source_file_path": str(raw_path),
            "source_seen_at_utc": source_seen,
            "normalized_utc": normalized_utc,
            "brand": brand,
            "stock_available": "",
            "category": category,
            "notes": f"action={action}|pack_quantity={pack_quantity}|exclude_discount={exclude_discount}",
        }

        if reasons:
            hold = dict(base)
            hold.pop("currency", None)
            hold.pop("vat_rate", None)
            hold["hold_reason_codes"] = "|".join(reasons)
            hold_rows.append(hold)
            continue

        base["row_hash"] = _row_hash([supplier_id, sku, barcode, cost, title, source_vat_rate])
        base["is_valid_source_row"] = "1"
        valid_rows.append(base)

    valid_df = pd.DataFrame(valid_rows)
    holds_df = pd.DataFrame(hold_rows)
    if valid_df.empty and holds_df.empty:
        return _empty_frames()
    return valid_df, holds_df
