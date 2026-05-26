from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


SUPPORTED_SUFFIXES = {".csv", ".txt"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _read_csv_with_fallback(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding="latin1").fillna("")


def _find_column(headers: list[str], candidates: Iterable[str]) -> int:
    normalized = [_normalize_lower(h) for h in headers]
    for candidate in candidates:
        target = _normalize_lower(candidate)
        for idx, header in enumerate(normalized):
            if header == target:
                return idx
    for candidate in candidates:
        target = _normalize_lower(candidate)
        for idx, header in enumerate(normalized):
            if target and target in header:
                return idx
    raise ValueError(f"Missing expected column. Tried: {', '.join(candidates)}")


def _find_optional_column(headers: list[str], candidates: Iterable[str]) -> int | None:
    try:
        return _find_column(headers, candidates)
    except ValueError:
        return None


def _clean_barcode(value: object) -> str:
    raw = _normalize_text(value)
    if not raw:
        return ""
    # Match original Apps Script:
    # s = s.replace(/^\s*(EAN|UPC)\s*:?\s*/i, "");
    raw = re.sub(r"^\s*(EAN|UPC)\s*:?\s*", "", raw, flags=re.IGNORECASE)
    return "".join(ch for ch in raw if ch.isdigit())


def _parse_cost(value: object) -> str:
    # Keep source text for parity with original processData() output.
    return _normalize_text(value)


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
    skips = {_normalize_text(suffix) for suffix in (skip_sku_suffixes or []) if suffix}

    df = _read_csv_with_fallback(raw_path)
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
            ]
        )
        return empty_valid, empty_holds

    headers = list(df.columns)
    sku_idx = _find_column(headers, ["sku", "product id", "product code", "item code"])
    barcode_idx = _find_column(headers, ["barcode", "ean", "ean/upc", "ean / upc", "upc"])
    cost_idx = _find_column(headers, ["price", "cost", "unit cost", "buying cost", "net cost"])
    title_idx = _find_optional_column(headers, ["title", "description", "product name", "name"])

    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []

    for _, row in df.iterrows():
        sku = _normalize_text(row.iloc[sku_idx])
        title = _normalize_text(row.iloc[title_idx]) if title_idx is not None else ""
        barcode = _clean_barcode(row.iloc[barcode_idx])
        cost = _parse_cost(row.iloc[cost_idx])

        # Match original Apps Script processData() continue rules.
        if not sku:
            continue
        if sku and any(sku.endswith(suffix) for suffix in skips):
            continue
        if not barcode:
            continue

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
        }

        row_hash = _row_hash([supplier_id, sku, barcode, cost, title])
        row_payload["row_hash"] = row_hash
        row_payload["is_valid_source_row"] = "1"
        valid_rows.append(row_payload)

    valid_df = pd.DataFrame(valid_rows)
    holds_df = pd.DataFrame(hold_rows)
    return valid_df, holds_df
