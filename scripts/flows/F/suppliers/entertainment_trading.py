from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


SUPPORTED_SUFFIXES = {".xlsx", ".xls"}
REPO_ROOT = Path(__file__).resolve().parents[4]
FX_RATES_PATH = REPO_ROOT / "out" / "fx_rates_daily.csv"
DEFAULT_EUR_TO_GBP_RATE = 0.87


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _find_column(headers: list[str], candidates: Iterable[str]) -> str:
    normalized = {_normalize_lower(header): header for header in headers}
    for candidate in candidates:
        key = _normalize_lower(candidate)
        if key in normalized:
            return normalized[key]
    for candidate in candidates:
        key = _normalize_lower(candidate)
        for header in headers:
            if key and key in _normalize_lower(header):
                return header
    raise ValueError(f"missing expected column. Tried: {', '.join(candidates)}")


def _clean_barcode(value: object) -> str:
    raw = _normalize_text(value)
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    return "".join(char for char in raw if char.isdigit())


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _to_float(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace("EUR", "").replace("€", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_int(value: object) -> int | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace(",", "")
    try:
        out = int(float(cleaned))
    except ValueError:
        return None
    return max(out, 0)


def _latest_eur_to_gbp_from_cache() -> float | None:
    if not FX_RATES_PATH.exists():
        return None
    fx = pd.read_csv(FX_RATES_PATH, dtype=str).fillna("")
    required = {"date", "currency", "rate_to_gbp"}
    if not required.issubset(fx.columns):
        return None
    eur = fx[fx["currency"].map(_normalize_lower) == "eur"].copy()
    if eur.empty:
        return None
    eur["date_dt"] = pd.to_datetime(eur["date"], errors="coerce")
    eur = eur.sort_values("date_dt", ascending=False)
    for _, row in eur.iterrows():
        rate = _to_float(row.get("rate_to_gbp", ""))
        if rate and rate > 0:
            return rate
    return None


def _eur_to_gbp_rate() -> float:
    for env_name in ["F_ENTERTAINMENT_TRADING_EUR_GBP_RATE", "F_STOCKLIST_EUR_GBP_RATE"]:
        env_value = os.environ.get(env_name, "").strip()
        if env_value:
            parsed = _to_float(env_value)
            if parsed and parsed > 0:
                return parsed
    cached = _latest_eur_to_gbp_from_cache()
    if cached and cached > 0:
        return cached
    return DEFAULT_EUR_TO_GBP_RATE


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
    eur_to_gbp = _eur_to_gbp_rate()

    df = pd.read_excel(raw_path, dtype=str, engine="openpyxl").fillna("")
    if df.empty:
        return _empty_frames()

    headers = list(df.columns)
    col_sku = _find_column(headers, ["ItemCode", "SKU", "Product ID"])
    col_title = _find_column(headers, ["ItemName", "Description", "Product Name"])
    col_dept = _find_column(headers, ["Department", "Category"])
    col_platform = _find_column(headers, ["Platform"])
    col_brand = _find_column(headers, ["Brand"])
    col_barcode = _find_column(headers, ["CodeBars", "Barcode", "EAN", "UPC"])
    col_available = _find_column(headers, ["Available", "Stock", "Stock Level"])
    col_eur = _find_column(headers, ["EUR", "Price", "Unit Cost", "Cost"])

    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    for source_index, row in df.reset_index(drop=True).iterrows():
        sku = _normalize_text(row.get(col_sku, ""))
        title = _normalize_text(row.get(col_title, ""))
        department = _normalize_text(row.get(col_dept, ""))
        platform = _normalize_text(row.get(col_platform, ""))
        brand = _normalize_text(row.get(col_brand, ""))
        barcode = _clean_barcode(row.get(col_barcode, ""))
        available = _to_int(row.get(col_available, ""))
        eur_cost = _to_float(row.get(col_eur, ""))
        category = department or platform

        reasons: list[str] = []
        if not sku:
            reasons.append("missing_sku")
        if sku and any(sku.upper().endswith(suffix) for suffix in skips):
            reasons.append("sku_suffix_blocked")
        if not barcode:
            reasons.append("missing_barcode")
        elif not _is_valid_barcode(barcode):
            reasons.append("invalid_barcode_format")
        if eur_cost is None or eur_cost <= 0:
            reasons.append("missing_or_invalid_cost")
        if available is None or available <= 0:
            reasons.append("no_available_stock")

        gbp_cost = ""
        if eur_cost is not None and eur_cost > 0:
            gbp_cost = f"{(eur_cost * eur_to_gbp):.2f}"

        base = {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_sku": sku,
            "supplier_title": title,
            "barcode": barcode,
            "unit_cost": gbp_cost,
            "currency": currency,
            "vat_rate": str(vat_rate),
            "source_url": source_url,
            "source_file_path": str(raw_path),
            "source_seen_at_utc": source_seen,
            "normalized_utc": normalized_utc,
            "brand": brand,
            "stock_available": "" if available is None else str(available),
            "category": category,
            "notes": f"source_currency=EUR|eur_to_gbp_rate={eur_to_gbp:.6f}",
        }

        if reasons:
            hold = dict(base)
            hold.pop("currency", None)
            hold.pop("vat_rate", None)
            hold["hold_reason_codes"] = "|".join(reasons)
            hold_rows.append(hold)
            continue

        base["row_hash"] = _row_hash([supplier_id, str(source_index), sku, barcode, gbp_cost, title, brand, base["notes"]])
        base["is_valid_source_row"] = "1"
        valid_rows.append(base)

    valid, holds = _empty_frames()
    if valid_rows:
        valid = pd.DataFrame(valid_rows)
    if hold_rows:
        holds = pd.DataFrame(hold_rows)
    return valid, holds
