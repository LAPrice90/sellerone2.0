from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


SQL_TABLE_PRODUCT_DB_PRODUCTS = "product_db_products"

PRODUCT_DB_REQUIRED_COLUMNS: tuple[str, ...] = (
    "seller_sku",
    "asin",
    "title",
    "brand_name",
    "main_image",
    "sale_status",
    "supplier_code",
    "supplier_name",
    "supplier_pack_size",
    "amazon_pack_size",
    "supplier_catalog_price",
    "last_purchase_price",
    "vat_rate",
    "fba_fee_10",
    "fba_fee_100",
    "referral_fee_10",
    "referral_fee_100",
    "live_listing_price",
    "stock_total",
    "stock_available",
    "stock_reserved",
    "stock_inbound",
    "last_updated",
)

PRODUCT_DB_NUMERIC_COLUMNS: tuple[str, ...] = (
    "supplier_pack_size",
    "amazon_pack_size",
    "supplier_catalog_price",
    "last_purchase_price",
    "vat_rate",
    "fba_fee_10",
    "fba_fee_100",
    "referral_fee_10",
    "referral_fee_100",
    "live_listing_price",
)

PRODUCT_DB_INTEGER_COLUMNS: tuple[str, ...] = (
    "stock_total",
    "stock_available",
    "stock_reserved",
    "stock_inbound",
)

PRODUCT_DB_AUDIT_COLUMNS: tuple[str, ...] = (
    "duplicate_asin_reason",
    "source_payload_json",
    "created_at_utc",
    "updated_at_utc",
)

PRODUCT_DB_TABLE_COLUMNS: tuple[str, ...] = (
    *PRODUCT_DB_REQUIRED_COLUMNS,
    *PRODUCT_DB_AUDIT_COLUMNS,
)


@dataclass(frozen=True)
class ProductDbValidationResult:
    status: str
    checks: list[dict[str, str]]
    duplicate_asin_rows: list[dict[str, str]]

    @property
    def fail_count(self) -> int:
        return sum(1 for row in self.checks if row.get("status") == "fail")

    @property
    def warn_count(self) -> int:
        return sum(1 for row in self.checks if row.get("status") == "warn")

    @property
    def ok_count(self) -> int:
        return sum(1 for row in self.checks if row.get("status") == "ok")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def normalize_key(value: object) -> str:
    return normalize_text(value).upper()


def read_csv_header_raw(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def duplicate_header_names(headers: Iterable[str]) -> list[str]:
    names = [normalize_text(header) for header in headers]
    counts = Counter(names)
    return sorted(name for name, count in counts.items() if name and count > 1)


def coalesce_duplicate_header_rows(rows: list[list[object]]) -> tuple[list[list[str]], list[str]]:
    """Merge duplicate Product DB headers before writing the source/export surface.

    The rightmost duplicate is treated as canonical because Product_DB audit fields
    sit near the right side of the sheet. Earlier duplicate values are copied into
    the canonical column only when the canonical value is blank, then the earlier
    duplicate columns are removed.
    """
    if not rows:
        return [], []
    headers = [normalize_text(header) for header in rows[0]]
    duplicate_names = duplicate_header_names(headers)
    if not duplicate_names:
        return [[normalize_text(cell) for cell in row] for row in rows], []

    width = len(headers)
    normalized_rows: list[list[str]] = []
    for row in rows:
        normalized = [normalize_text(cell) for cell in row]
        if len(normalized) < width:
            normalized.extend([""] * (width - len(normalized)))
        normalized_rows.append(normalized[:width])

    remove_indices: set[int] = set()
    for name in duplicate_names:
        indices = [idx for idx, header in enumerate(headers) if header == name]
        if len(indices) < 2:
            continue
        canonical_idx = indices[-1]
        for row in normalized_rows[1:]:
            if row[canonical_idx]:
                continue
            for source_idx in reversed(indices[:-1]):
                if row[source_idx]:
                    row[canonical_idx] = row[source_idx]
                    break
        remove_indices.update(indices[:-1])

    keep_indices = [idx for idx in range(width) if idx not in remove_indices]
    repaired_rows = [[row[idx] for idx in keep_indices] for row in normalized_rows]
    return repaired_rows, duplicate_names


def dataframe_from_product_db_sheet_rows(rows: list[list[object]]) -> tuple[pd.DataFrame, list[str]]:
    repaired_rows, repaired_headers = coalesce_duplicate_header_rows(rows)
    if not repaired_rows:
        return pd.DataFrame(), repaired_headers
    return pd.DataFrame(repaired_rows[1:], columns=repaired_rows[0]), repaired_headers


def product_db_create_table_sql(*, backend: str = "sqlite") -> str:
    backend_norm = normalize_text(backend).lower() or "sqlite"
    if backend_norm not in {"sqlite", "postgres"}:
        raise ValueError(f"unsupported product DB contract backend: {backend}")

    text_type = "TEXT"
    numeric_type = "NUMERIC" if backend_norm == "postgres" else "REAL"
    integer_type = "INTEGER"
    timestamp_type = "TIMESTAMPTZ" if backend_norm == "postgres" else "TEXT"

    column_defs: list[str] = []
    for column in PRODUCT_DB_REQUIRED_COLUMNS:
        if column == "seller_sku":
            column_defs.append('"seller_sku" TEXT PRIMARY KEY')
        elif column in PRODUCT_DB_NUMERIC_COLUMNS:
            column_defs.append(f'"{column}" {numeric_type}')
        elif column in PRODUCT_DB_INTEGER_COLUMNS:
            column_defs.append(f'"{column}" {integer_type}')
        elif column == "last_updated":
            column_defs.append(f'"{column}" {timestamp_type}')
        else:
            column_defs.append(f'"{column}" {text_type}')

    column_defs.extend(
        [
            '"duplicate_asin_reason" TEXT NOT NULL DEFAULT \'\'',
            '"source_payload_json" TEXT NOT NULL DEFAULT \'{}\'',
            f'"created_at_utc" {timestamp_type} NOT NULL',
            f'"updated_at_utc" {timestamp_type} NOT NULL',
        ]
    )
    return (
        f'CREATE TABLE IF NOT EXISTS "{SQL_TABLE_PRODUCT_DB_PRODUCTS}" (\n    '
        + ",\n    ".join(column_defs)
        + "\n);"
    )


def product_db_indexes_sql(*, backend: str = "sqlite") -> list[str]:
    backend_norm = normalize_text(backend).lower() or "sqlite"
    if backend_norm not in {"sqlite", "postgres"}:
        raise ValueError(f"unsupported product DB contract backend: {backend}")
    return [
        (
            f'CREATE INDEX IF NOT EXISTS "idx_{SQL_TABLE_PRODUCT_DB_PRODUCTS}_asin" '
            f'ON "{SQL_TABLE_PRODUCT_DB_PRODUCTS}" ("asin");'
        ),
        (
            f'CREATE INDEX IF NOT EXISTS "idx_{SQL_TABLE_PRODUCT_DB_PRODUCTS}_supplier_code" '
            f'ON "{SQL_TABLE_PRODUCT_DB_PRODUCTS}" ("supplier_code");'
        ),
    ]


def _check_row(
    *,
    check: str,
    status: str,
    value: object,
    notes: str,
    observed_utc: str,
    source_path: str,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": normalize_text(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": source_path,
    }


def validate_product_db_dataframe(
    df: pd.DataFrame,
    *,
    raw_headers: Iterable[str] | None = None,
    source_path: str = "",
    observed_utc: str | None = None,
) -> ProductDbValidationResult:
    observed = observed_utc or utc_now_iso()
    source = normalize_text(source_path)
    checks: list[dict[str, str]] = []
    headers = [normalize_text(c) for c in (raw_headers if raw_headers is not None else df.columns)]
    duplicate_headers = duplicate_header_names(headers)
    checks.append(
        _check_row(
            check="product_db_unique_headers",
            status="fail" if duplicate_headers else "ok",
            value=len(duplicate_headers),
            notes="duplicate headers: " + "|".join(duplicate_headers) if duplicate_headers else "headers are unique",
            observed_utc=observed,
            source_path=source,
        )
    )

    missing_required = [column for column in PRODUCT_DB_REQUIRED_COLUMNS if column not in df.columns]
    checks.append(
        _check_row(
            check="product_db_required_columns",
            status="fail" if missing_required else "ok",
            value=len(missing_required),
            notes="missing required columns: " + "|".join(missing_required) if missing_required else "all required columns present",
            observed_utc=observed,
            source_path=source,
        )
    )

    if "seller_sku" in df.columns:
        sku_series = df["seller_sku"].map(normalize_text)
        blank_sku_count = int(sku_series.eq("").sum())
        duplicate_sku_values = sorted(sku for sku, count in Counter(sku_series[sku_series != ""]).items() if count > 1)
    else:
        sku_series = pd.Series(dtype=str)
        blank_sku_count = 0
        duplicate_sku_values = []

    checks.append(
        _check_row(
            check="product_db_seller_sku_present",
            status="fail" if blank_sku_count else "ok",
            value=blank_sku_count,
            notes="blank seller_sku rows" if blank_sku_count else "seller_sku populated",
            observed_utc=observed,
            source_path=source,
        )
    )
    checks.append(
        _check_row(
            check="product_db_seller_sku_unique",
            status="fail" if duplicate_sku_values else "ok",
            value=len(duplicate_sku_values),
            notes="duplicate seller_sku: " + "|".join(duplicate_sku_values[:25]) if duplicate_sku_values else "seller_sku is unique",
            observed_utc=observed,
            source_path=source,
        )
    )

    duplicate_asin_rows: list[dict[str, str]] = []
    if "asin" in df.columns and "seller_sku" in df.columns:
        asin_work = pd.DataFrame(
            {
                "asin": df["asin"].map(normalize_key),
                "seller_sku": df["seller_sku"].map(normalize_text),
            }
        )
        asin_work = asin_work[(asin_work["asin"] != "") & (asin_work["seller_sku"] != "")]
        if "duplicate_asin_reason" in df.columns:
            asin_work["duplicate_asin_reason"] = df["duplicate_asin_reason"].map(normalize_text)
        else:
            asin_work["duplicate_asin_reason"] = ""
        grouped = asin_work.groupby("asin", sort=True)
        for asin, group in grouped:
            unique_skus = sorted(set(group["seller_sku"].tolist()))
            if len(unique_skus) > 1:
                reasons = [normalize_text(value) for value in group["duplicate_asin_reason"].tolist()]
                if not all(reasons):
                    duplicate_asin_rows.append(
                        {
                            "asin": asin,
                            "match_count": str(len(unique_skus)),
                            "seller_skus": "|".join(unique_skus),
                            "action": "REVIEW",
                            "reason": "duplicate_product_db_asin_requires_classification",
                        }
                    )
        blank_asin_count = int(pd.Series(df["asin"]).map(normalize_text).eq("").sum())
    else:
        blank_asin_count = 0

    checks.append(
        _check_row(
            check="product_db_asin_controlled_non_unique",
            status="warn" if duplicate_asin_rows else "ok",
            value=len(duplicate_asin_rows),
            notes=(
                "duplicate ASINs require reason classification before automated linking: "
                + "|".join(row["asin"] for row in duplicate_asin_rows[:25])
                if duplicate_asin_rows
                else "no duplicate nonblank ASINs found"
            ),
            observed_utc=observed,
            source_path=source,
        )
    )
    checks.append(
        _check_row(
            check="product_db_blank_asin_allowed_review",
            status="warn" if blank_asin_count else "ok",
            value=blank_asin_count,
            notes="blank ASIN rows are not automatic link candidates" if blank_asin_count else "all rows have ASIN",
            observed_utc=observed,
            source_path=source,
        )
    )

    fail_count = sum(1 for row in checks if row["status"] == "fail")
    warn_count = sum(1 for row in checks if row["status"] == "warn")
    status = "fail" if fail_count else ("warn" if warn_count else "ok")
    return ProductDbValidationResult(status=status, checks=checks, duplicate_asin_rows=duplicate_asin_rows)


def load_product_db_for_validation(path: Path) -> tuple[pd.DataFrame, list[str]]:
    raw_headers = read_csv_header_raw(path)
    df = pd.read_csv(path, dtype=str).fillna("")
    return df, raw_headers


def _to_numeric_or_none(value: object) -> float | None:
    text = normalize_text(value).replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int_or_none(value: object) -> int | None:
    numeric = _to_numeric_or_none(value)
    if numeric is None:
        return None
    return int(numeric)


def build_product_db_import_rows(df: pd.DataFrame, *, observed_utc: str | None = None) -> list[dict[str, object]]:
    observed = observed_utc or utc_now_iso()
    rows: list[dict[str, object]] = []
    for _, source_row in df.iterrows():
        row: dict[str, object] = {}
        for column in PRODUCT_DB_REQUIRED_COLUMNS:
            value = source_row.get(column, "")
            if column in PRODUCT_DB_NUMERIC_COLUMNS:
                row[column] = _to_numeric_or_none(value)
            elif column in PRODUCT_DB_INTEGER_COLUMNS:
                row[column] = _to_int_or_none(value)
            else:
                row[column] = normalize_text(value)
        row["duplicate_asin_reason"] = normalize_text(source_row.get("duplicate_asin_reason", ""))
        row["source_payload_json"] = json.dumps(
            {str(key): normalize_text(value) for key, value in source_row.to_dict().items()},
            ensure_ascii=True,
            sort_keys=True,
        )
        row["created_at_utc"] = observed
        row["updated_at_utc"] = observed
        rows.append(row)
    return rows


def _sql_value_to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return normalize_text(value)


def load_product_db_products_from_sqlite(sqlite_path: Path) -> pd.DataFrame:
    if not sqlite_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            [SQL_TABLE_PRODUCT_DB_PRODUCTS],
        ).fetchone()
        if not table_exists:
            return pd.DataFrame()
        cursor = conn.execute(f'SELECT * FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}"')
        sql_rows = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    rows: list[dict[str, str]] = []
    for sql_row in sql_rows:
        payload: dict[str, str] = {}
        raw_payload = normalize_text(sql_row.get("source_payload_json", ""))
        if raw_payload:
            try:
                parsed = json.loads(raw_payload)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                payload = {str(key): normalize_text(value) for key, value in parsed.items()}
        merged = dict(payload)
        for column in PRODUCT_DB_TABLE_COLUMNS:
            if column == "source_payload_json":
                continue
            if column in sql_row:
                merged[column] = _sql_value_to_text(sql_row.get(column))
        rows.append(merged)
    return pd.DataFrame(rows).fillna("")


def stage_product_db_import_sqlite(*, df: pd.DataFrame, sqlite_path: Path, observed_utc: str | None = None) -> dict[str, str]:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_product_db_import_rows(df, observed_utc=observed_utc)
    columns = list(PRODUCT_DB_TABLE_COLUMNS)
    placeholders = ", ".join(["?"] * len(columns))
    quoted_cols = ", ".join(f'"{column}"' for column in columns)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute(product_db_create_table_sql(backend="sqlite"))
        for sql in product_db_indexes_sql(backend="sqlite"):
            conn.execute(sql)
        conn.execute(f'DELETE FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}"')
        conn.executemany(
            f'INSERT INTO "{SQL_TABLE_PRODUCT_DB_PRODUCTS}" ({quoted_cols}) VALUES ({placeholders})',
            [[row.get(column) for column in columns] for row in rows],
        )
        count = conn.execute(f'SELECT COUNT(*) FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}"').fetchone()[0]
        unique_sku_count = conn.execute(
            f'SELECT COUNT(DISTINCT seller_sku) FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}"'
        ).fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return {
        "sqlite_path": str(sqlite_path),
        "table": SQL_TABLE_PRODUCT_DB_PRODUCTS,
        "rows": str(count),
        "unique_seller_sku": str(unique_sku_count),
    }
