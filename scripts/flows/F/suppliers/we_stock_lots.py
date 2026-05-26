from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


SUPPORTED_SUFFIXES = {".csv", ".txt", ".xlsx", ".xls"}
ROOT = Path(__file__).resolve().parents[4]
FX_CACHE = ROOT / "out" / "fx_rates_daily.csv"


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


def _clean_barcode(value: object) -> str:
    raw = _normalize_text(value)
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    return "".join(char for char in raw if char.isdigit())


def _clean_price_number(value: object) -> float | None:
    raw = _normalize_text(value)
    if not raw:
        return None
    cleaned = (
        raw.replace(",", "")
        .replace(chr(8364), "")
        .replace("EUR", "")
        .replace("eur", "")
        .replace(chr(163), "")
        .replace("GBP", "")
        .replace("gbp", "")
        .strip()
    )
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _format_price(value: float | None) -> str:
    if value is None or value <= 0:
        return ""
    return f"{value:.2f}"


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _row_hash(parts: Iterable[str]) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()


def _read_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    try:
        return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding="latin1").fillna("")


def _find_column(columns: list[str], candidates: Iterable[str]) -> str:
    normalized = {_normalize_key(column): column for column in columns}
    for candidate in candidates:
        key = _normalize_key(candidate)
        if key in normalized:
            return normalized[key]
    for candidate in candidates:
        key = _normalize_key(candidate)
        for column in columns:
            if key and key in _normalize_key(column):
                return column
    return ""


def _row_value(row: pd.Series, columns: list[str], candidates: Iterable[str], fallback_index: int) -> str:
    column = _find_column(columns, candidates)
    if column:
        return _normalize_text(row.get(column, ""))
    if fallback_index < len(columns):
        return _normalize_text(row.get(columns[fallback_index], ""))
    return ""


def _fetch_current_eur_gbp_rate() -> tuple[float | None, str]:
    url = "https://api.frankfurter.app/latest?" + urllib.parse.urlencode({"from": "EUR", "to": "GBP"})
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "SellerOne-FPM/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None, "online_unavailable"
    try:
        rate = float((payload.get("rates") or {}).get("GBP"))
    except (TypeError, ValueError, AttributeError):
        return None, "online_missing_gbp"
    if rate <= 0:
        return None, "online_invalid_gbp"
    date_used = _normalize_text(payload.get("date", ""))
    return rate, f"frankfurter_latest:{date_used}"


def _cached_eur_gbp_rate() -> tuple[float | None, str]:
    if not FX_CACHE.exists():
        return None, "fx_cache_missing"
    try:
        fx = pd.read_csv(FX_CACHE, dtype=str).fillna("")
    except Exception:
        return None, "fx_cache_unreadable"
    if fx.empty:
        return None, "fx_cache_empty"
    work = fx[
        fx.get("currency", "").map(lambda value: _normalize_text(value).upper()) == "EUR"
    ].copy()
    if work.empty:
        return None, "fx_cache_eur_missing"
    work = work.sort_values(["date", "fx_date_used"], kind="stable")
    row = work.tail(1).iloc[0]
    try:
        rate = float(row.get("rate_to_gbp", ""))
    except ValueError:
        return None, "fx_cache_eur_invalid"
    if rate <= 0:
        return None, "fx_cache_eur_invalid"
    return rate, f"fx_cache:{row.get('date', '')}:{row.get('fx_date_used', '')}"


def _eur_gbp_rate() -> tuple[float, str]:
    env_rate = _normalize_text(os.environ.get("WE_STOCK_LOTS_EUR_GBP_RATE", ""))
    if env_rate:
        try:
            parsed = float(env_rate)
        except ValueError as exc:
            raise ValueError("WE_STOCK_LOTS_EUR_GBP_RATE must be numeric") from exc
        if parsed <= 0:
            raise ValueError("WE_STOCK_LOTS_EUR_GBP_RATE must be greater than zero")
        return parsed, "env:WE_STOCK_LOTS_EUR_GBP_RATE"

    online_rate, online_source = _fetch_current_eur_gbp_rate()
    if online_rate is not None:
        return online_rate, online_source

    cached_rate, cached_source = _cached_eur_gbp_rate()
    if cached_rate is not None:
        return cached_rate, cached_source

    raise RuntimeError(f"eur_gbp_rate_unavailable:{online_source}:{cached_source}")


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
    eur_gbp_rate, fx_source = _eur_gbp_rate()
    df = _read_source(raw_path)
    if df.empty:
        return _empty_frames()

    columns = list(df.columns)
    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    for index, row in df.reset_index(drop=True).iterrows():
        description = _row_value(row, columns, ["Description", "Title", "Product Description"], 1)
        moq = _row_value(row, columns, ["Pieces MOQ", "MOQ", "Pieces", "Minimum Order Quantity"], 5)
        sku = f"MOQ - {moq or 'N/A'}"
        title = f"We Stock Lots - {description}".strip()
        barcode = _clean_barcode(_row_value(row, columns, ["EAN", "Barcode", "GTIN", "UPC"], 3))
        eur_price = _clean_price_number(_row_value(row, columns, ["Our Price", "Price", "EUR Price"], 7))
        gbp_price = _format_price(eur_price * eur_gbp_rate if eur_price is not None else None)

        reasons: list[str] = []
        if not sku:
            reasons.append("missing_sku")
        if sku and any(sku.upper().endswith(suffix) for suffix in skips):
            reasons.append("sku_suffix_blocked")
        if not barcode:
            reasons.append("missing_barcode")
        elif not _is_valid_barcode(barcode):
            reasons.append("invalid_barcode_format")
        if not gbp_price:
            reasons.append("missing_or_invalid_cost")

        base = {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_sku": sku,
            "supplier_title": title,
            "barcode": barcode,
            "unit_cost": gbp_price,
            "currency": currency,
            "vat_rate": str(vat_rate),
            "source_url": source_url,
            "source_file_path": str(raw_path),
            "source_seen_at_utc": source_seen,
            "normalized_utc": normalized_utc,
            "brand": "We Stock Lots",
            "stock_available": "",
            "category": "stock_list",
            "notes": f"source_price_currency=EUR|eur_gbp_rate={eur_gbp_rate:.8f}|fx_source={fx_source}|source_row={index + 2}",
        }

        if reasons:
            hold = dict(base)
            hold.pop("currency", None)
            hold.pop("vat_rate", None)
            hold["hold_reason_codes"] = "|".join(reasons)
            hold_rows.append(hold)
            continue

        base["row_hash"] = _row_hash([supplier_id, sku, barcode, gbp_price, title, f"{eur_gbp_rate:.8f}"])
        base["is_valid_source_row"] = "1"
        valid_rows.append(base)

    return pd.DataFrame(valid_rows), pd.DataFrame(hold_rows)
