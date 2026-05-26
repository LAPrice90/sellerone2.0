from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple

import pandas as pd


SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".csv", ".txt", ".zip"}
INNER_PRICE_FILE_SUFFIXES = {".xlsx", ".xls", ".csv", ".txt"}

SUPPLY_CODE_COLUMNS = (
    "Supply Code",
    "Supplier SKU",
    "Supplier Code",
    "Product Code",
    "Item Code",
    "ItemCode",
    "Item No",
    "Item Number",
    "Stock Code",
    "SKU",
    "Code",
)
TITLE_COLUMNS = (
    "Description",
    "Product Description",
    "Product Name",
    "Item Name",
    "Name",
    "Title",
)
BARCODE_COLUMNS = (
    "Barcode",
    "Bar Code",
    "EAN",
    "EAN13",
    "UPC",
    "GTIN",
    "CodeBars",
)
UNIT_CODE_COLUMNS = (
    "Unit Code",
    "Unit",
    "UnitCode",
    "Pack",
    "Pack Size",
    "PackSize",
    "Case Qty",
    "Case Quantity",
    "Qty Per Pack",
)
COST_COLUMNS = (
    "CPU",
    "Trade",
    "Trade Price",
    "Unit Cost",
    "Unit Price",
    "Cost Price",
    "Wholesale Price",
    "Net Price",
    "Nett Price",
    "Dealer Price",
    "Price",
    "Cost",
    "GBP",
)
STOCK_COLUMNS = (
    "Available",
    "Stock Available",
    "Free Stock",
    "Stock",
    "Qty",
    "Quantity",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_header(value: object) -> str:
    text = _normalize_text(value).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _find_column(headers: list[str], candidates: Iterable[str], *, required: bool = False) -> str:
    normalized = {_normalize_header(header): header for header in headers if _normalize_text(header)}
    for candidate in candidates:
        match = normalized.get(_normalize_header(candidate))
        if match:
            return match
    for candidate in candidates:
        key = _normalize_header(candidate)
        for header in headers:
            if key and key in _normalize_header(header):
                return header
    if required:
        raise ValueError(f"missing expected ABGee column. Tried: {', '.join(candidates)}")
    return ""


def _unique_headers(headers: Iterable[object]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for index, header in enumerate(headers):
        text = _normalize_text(header) or f"blank_{index}"
        count = seen.get(text, 0)
        seen[text] = count + 1
        out.append(text if count == 0 else f"{text}_{count + 1}")
    return out


def _table_from_raw(raw: pd.DataFrame, source_label: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    raw = raw.fillna("")
    best_index = -1
    best_score = -1
    max_scan_rows = min(len(raw.index), 30)
    for index in range(max_scan_rows):
        headers = _unique_headers(raw.iloc[index].tolist())
        score = 0
        if _find_column(headers, SUPPLY_CODE_COLUMNS):
            score += 2
        if _find_column(headers, COST_COLUMNS):
            score += 2
        if _find_column(headers, TITLE_COLUMNS):
            score += 1
        if _find_column(headers, BARCODE_COLUMNS):
            score += 1
        if score > best_score:
            best_score = score
            best_index = index
    if best_index < 0 or best_score < 4:
        raise ValueError(f"could not find ABGee price-list header row in {source_label}")

    headers = _unique_headers(raw.iloc[best_index].tolist())
    table = raw.iloc[best_index + 1 :].copy()
    table.columns = headers
    table = table[[column for column in table.columns if not column.startswith("blank_")]].copy()
    table = table.fillna("")
    table = table[
        table.apply(lambda row: any(_normalize_text(value) for value in row.tolist()), axis=1)
    ].reset_index(drop=True)
    return table


def _read_csv_bytes(data: bytes, source_label: str) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            raw = pd.read_csv(io.BytesIO(data), dtype=str, header=None, sep=None, engine="python", encoding=encoding).fillna("")
            return _table_from_raw(raw, source_label)
        except Exception as exc:  # pragma: no cover - final error is raised below with context.
            last_error = exc
    raise ValueError(f"could not read ABGee CSV source {source_label}: {type(last_error).__name__}")


def _read_excel_bytes(data: bytes, suffix: str, source_label: str) -> list[tuple[str, pd.DataFrame]]:
    engine = "openpyxl" if suffix.lower() == ".xlsx" else None
    workbook = pd.read_excel(io.BytesIO(data), sheet_name=None, dtype=str, header=None, engine=engine)
    tables: list[tuple[str, pd.DataFrame]] = []
    for sheet_name, raw in workbook.items():
        if raw.empty:
            continue
        tables.append((sheet_name, _table_from_raw(raw, f"{source_label}:{sheet_name}")))
    return tables


def _read_price_tables(path: Path) -> list[tuple[str, pd.DataFrame]]:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        tables: list[tuple[str, pd.DataFrame]] = []
        with zipfile.ZipFile(path) as archive:
            members = [
                info
                for info in archive.infolist()
                if not info.is_dir()
                and not Path(info.filename).name.startswith("__MACOSX")
                and Path(info.filename).suffix.lower() in INNER_PRICE_FILE_SUFFIXES
            ]
            if not members:
                raise ValueError(f"ABGee zip contains no supported price file: {path}")
            for member in members:
                name = Path(member.filename).name
                data = archive.read(member)
                inner_suffix = Path(name).suffix.lower()
                if inner_suffix in {".csv", ".txt"}:
                    tables.append((name, _read_csv_bytes(data, name)))
                else:
                    tables.extend(_read_excel_bytes(data, inner_suffix, name))
        return tables

    data = path.read_bytes()
    if suffix in {".csv", ".txt"}:
        return [(path.name, _read_csv_bytes(data, path.name))]
    return _read_excel_bytes(data, suffix, path.name)


def _clean_supply_code(value: object) -> str:
    return re.sub(r"\s+", " ", _normalize_text(value)).upper()


def _clean_barcode(value: object) -> str:
    raw = _normalize_text(value)
    if raw.endswith(".0") and raw[:-2].isdigit():
        raw = raw[:-2]
    return "".join(char for char in raw if char.isdigit())


def _is_valid_barcode(value: str) -> bool:
    return value.isdigit() and len(value) in {8, 12, 13, 14}


def _clean_price(value: object) -> tuple[str, str]:
    raw = _normalize_text(value)
    if raw == "":
        return "", "missing_or_invalid_cost"
    cleaned = raw.replace(chr(163), "").replace("GBP", "").replace("gbp", "").strip()
    if "," in cleaned and "." not in cleaned and cleaned.count(",") == 1:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    cleaned = re.sub(r"[^0-9.+-]", "", cleaned)
    if cleaned in {"", ".", "+", "-"}:
        return "", "missing_or_invalid_cost"
    try:
        parsed = float(cleaned)
    except ValueError:
        return "", "missing_or_invalid_cost"
    if parsed == 0:
        return "", "zero_cost"
    if parsed < 0:
        return "", "missing_or_invalid_cost"
    return f"{parsed:.2f}", ""


def _format_money(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def _clean_pack_size(value: object) -> tuple[str, str]:
    raw = _normalize_text(value)
    if raw == "":
        return "1", ""
    token = re.sub(r"\s+", "", raw.upper())
    if token in {"EA", "EACH", "UNIT", "UNITS", "SINGLE", "1"}:
        return "1", ""
    match = re.fullmatch(r"(?:PK|PACK|CASE|CS|CTN)(\d+)", token)
    if match:
        size = int(match.group(1))
        return (str(size), "") if size > 0 else ("", "invalid_pack_size")
    match = re.fullmatch(r"(\d+)(?:PK|PACK|CASE|CS|CTN)", token)
    if match:
        size = int(match.group(1))
        return (str(size), "") if size > 0 else ("", "invalid_pack_size")
    match = re.search(r"(\d+)", token)
    if match:
        size = int(match.group(1))
        return (str(size), "") if size > 0 else ("", "invalid_pack_size")
    return "", "invalid_pack_size"


def _clean_stock(value: object) -> str:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return ""
    try:
        parsed = int(float(raw))
    except ValueError:
        return ""
    return str(max(parsed, 0))


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
        "unit_code",
        "pack_size",
        "pack_cost",
        "moq",
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
        "unit_code",
        "pack_size",
        "pack_cost",
        "moq",
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
    tables = _read_price_tables(Path(raw_path))
    if not tables:
        return _empty_frames()

    parsed_rows: list[dict[str, object]] = []
    supply_code_counts: dict[str, int] = {}
    for source_label, table in tables:
        headers = list(table.columns)
        sku_col = _find_column(headers, SUPPLY_CODE_COLUMNS, required=True)
        title_col = _find_column(headers, TITLE_COLUMNS)
        barcode_col = _find_column(headers, BARCODE_COLUMNS)
        unit_code_col = _find_column(headers, UNIT_CODE_COLUMNS)
        cost_col = _find_column(headers, COST_COLUMNS, required=True)
        stock_col = _find_column(headers, STOCK_COLUMNS)

        for row_number, row in table.reset_index(drop=True).iterrows():
            sku = _clean_supply_code(row.get(sku_col, ""))
            title = _normalize_text(row.get(title_col, "")) if title_col else ""
            barcode = _clean_barcode(row.get(barcode_col, "")) if barcode_col else ""
            unit_code = _normalize_text(row.get(unit_code_col, "")) if unit_code_col else ""
            pack_size, pack_reason = _clean_pack_size(unit_code)
            pack_cost, cost_reason = _clean_price(row.get(cost_col, ""))
            unit_cost = pack_cost
            if not cost_reason and not pack_reason:
                pack_count = int(pack_size or "1")
                parsed_pack_cost = float(pack_cost)
                if pack_count > 1:
                    unit_cost = _format_money(parsed_pack_cost / pack_count)
            stock = _clean_stock(row.get(stock_col, "")) if stock_col else ""
            category = source_label
            reasons: list[str] = []
            if not sku:
                reasons.append("missing_supply_code")
            if sku and any(sku.endswith(suffix) for suffix in skips):
                reasons.append("sku_suffix_blocked")
            if not barcode:
                reasons.append("missing_barcode")
            elif not _is_valid_barcode(barcode):
                reasons.append("invalid_barcode_format")
            if pack_reason:
                reasons.append(pack_reason)
            if cost_reason:
                reasons.append(cost_reason)
            if sku:
                supply_code_counts[sku] = supply_code_counts.get(sku, 0) + 1
            note_parts = [f"source_table={source_label}", f"source_row={row_number + 1}"]
            if unit_code:
                note_parts.append(f"unit_code={unit_code}")
            if pack_size and pack_size != "1":
                note_parts.append(f"pack_size={pack_size}")
                note_parts.append(f"pack_cost={pack_cost}")
                note_parts.append("abgee_pack_cost_divided_to_unit_cost")
            parsed_rows.append(
                {
                    "sku": sku,
                    "title": title,
                    "barcode": barcode,
                    "unit_code": unit_code,
                    "pack_size": pack_size or "1",
                    "pack_cost": pack_cost,
                    "cost": unit_cost,
                    "moq": pack_size or "1",
                    "stock": stock,
                    "category": category,
                    "notes": ";".join(note_parts),
                    "reasons": reasons,
                }
            )

    valid_rows: list[dict[str, str]] = []
    hold_rows: list[dict[str, str]] = []
    for parsed in parsed_rows:
        sku = str(parsed["sku"])
        title = str(parsed["title"])
        barcode = str(parsed["barcode"])
        cost = str(parsed["cost"])
        unit_code = str(parsed["unit_code"])
        pack_size = str(parsed["pack_size"])
        pack_cost = str(parsed["pack_cost"])
        moq = str(parsed["moq"])
        stock = str(parsed["stock"])
        category = str(parsed["category"])
        notes = str(parsed["notes"])
        reasons = list(parsed["reasons"])
        if sku and supply_code_counts.get(sku, 0) > 1:
            reasons.append("duplicate_supply_code")

        base = {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_sku": sku,
            "supplier_title": title,
            "barcode": barcode,
            "unit_cost": cost,
            "unit_code": unit_code,
            "pack_size": pack_size,
            "pack_cost": pack_cost,
            "moq": moq,
            "currency": currency,
            "vat_rate": str(vat_rate),
            "source_url": source_url,
            "source_file_path": str(raw_path),
            "source_seen_at_utc": source_seen,
            "normalized_utc": normalized_utc,
            "brand": "",
            "stock_available": stock,
            "category": category,
            "notes": notes,
        }

        if reasons:
            hold = dict(base)
            hold.pop("currency", None)
            hold.pop("vat_rate", None)
            hold["hold_reason_codes"] = "|".join(dict.fromkeys(reasons))
            hold_rows.append(hold)
            continue

        base["row_hash"] = _row_hash([supplier_id, sku, barcode, cost, pack_size, pack_cost, title, category])
        base["is_valid_source_row"] = "1"
        valid_rows.append(base)

    if not valid_rows and not hold_rows:
        return _empty_frames()
    return pd.DataFrame(valid_rows), pd.DataFrame(hold_rows)
