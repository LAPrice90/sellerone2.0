from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


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
    normalized = {_normalize_lower(h): h for h in headers}
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
    if not raw:
        return ""
    return "".join(ch for ch in raw if ch.isdigit())


def _to_float(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = (
        raw.replace("EUR", "")
        .replace("€", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    try:
        out = float(cleaned)
    except ValueError:
        return None
    return out


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


def _read_excel(path: Path) -> pd.DataFrame:
    # raw_path is copied by F005 and may not carry .xlsx extension.
    all_sheets = pd.read_excel(path, sheet_name=None, dtype=str, engine="openpyxl")
    non_empty = [df.fillna("") for df in all_sheets.values() if not df.empty]
    if not non_empty:
        return pd.DataFrame()
    return non_empty[0]


def _latest_eur_to_gbp_from_cache() -> float | None:
    if not FX_RATES_PATH.exists():
        return None
    df = pd.read_csv(FX_RATES_PATH, dtype=str).fillna("")
    required = {"date", "currency", "rate_to_gbp"}
    if not required.issubset(df.columns):
        return None
    eur = df[df["currency"].map(_normalize_lower) == "eur"].copy()
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
    env_value = os.environ.get("F_STOCKLIST_EUR_GBP_RATE", "").strip()
    if env_value:
        parsed = _to_float(env_value)
        if parsed and parsed > 0:
            return parsed
    cached = _latest_eur_to_gbp_from_cache()
    if cached and cached > 0:
        return cached
    return DEFAULT_EUR_TO_GBP_RATE


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
    skips = {_normalize_text(s).upper() for s in (skip_sku_suffixes or []) if s}
    eur_to_gbp = _eur_to_gbp_rate()

    df = _read_excel(raw_path)
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
                "notes",
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
                "notes",
            ]
        )
        return empty_valid, empty_holds

    headers = list(df.columns)
    col_sku = _find_column(headers, ["ItemCode", "SKU", "Product ID"])
    col_title = _find_column(headers, ["ItemName", "Description", "Product Name"])
    col_brand = _find_column(headers, ["Brand"])
    col_barcode = _find_column(headers, ["CodeBars", "Barcode", "EAN", "UPC"])
    col_stock = _find_column(headers, ["Available", "Stock", "Stock Level"])
    col_eur = _find_column(headers, ["EUR", "Price", "Unit Cost", "Cost"])
    col_dept = _find_column(headers, ["Department", "Category"])
    col_platform = _find_column(headers, ["Platform"])

    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    for _, row in df.iterrows():
        sku = _normalize_text(row.get(col_sku, ""))
        title = _normalize_text(row.get(col_title, ""))
        brand = _normalize_text(row.get(col_brand, ""))
        barcode = _clean_barcode(row.get(col_barcode, ""))
        available = _to_int(row.get(col_stock, ""))
        eur_cost = _to_float(row.get(col_eur, ""))
        department = _normalize_text(row.get(col_dept, ""))
        platform = _normalize_text(row.get(col_platform, ""))
        category = department or platform

        reasons: list[str] = []
        if sku == "":
            reasons.append("missing_sku")
        if sku and any(sku.upper().endswith(suffix) for suffix in skips):
            reasons.append("sku_suffix_blocked")
        if barcode == "":
            reasons.append("missing_barcode")
        if eur_cost is None:
            reasons.append("missing_or_invalid_eur_cost")
        elif eur_cost <= 0:
            reasons.append("nonpositive_eur_cost")

        gbp_cost = ""
        if eur_cost is not None and eur_cost > 0:
            gbp_cost = f"{(eur_cost * eur_to_gbp):.2f}"

        payload_base = {
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
            hold_rows.append(
                {
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "supplier_sku": sku,
                    "supplier_title": title,
                    "barcode": barcode,
                    "unit_cost": gbp_cost,
                    "hold_reason_codes": "|".join(reasons),
                    "source_url": source_url,
                    "source_file_path": str(raw_path),
                    "source_seen_at_utc": source_seen,
                    "normalized_utc": normalized_utc,
                    "brand": brand,
                    "stock_available": "" if available is None else str(available),
                    "category": category,
                    "notes": payload_base["notes"],
                }
            )
            continue

        row_hash = _row_hash(
            [supplier_id, sku, barcode, gbp_cost, title, brand, payload_base["notes"]]
        )
        payload_base["row_hash"] = row_hash
        payload_base["is_valid_source_row"] = "1"
        valid_rows.append(payload_base)

    return pd.DataFrame(valid_rows), pd.DataFrame(hold_rows)
