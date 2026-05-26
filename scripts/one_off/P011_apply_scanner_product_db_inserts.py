from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import (
    PRODUCT_DB_REQUIRED_COLUMNS,
    SQL_TABLE_PRODUCT_DB_PRODUCTS,
    build_product_db_import_rows,
    duplicate_header_names,
    load_product_db_for_validation,
    normalize_key,
    normalize_text,
    product_db_create_table_sql,
    product_db_indexes_sql,
    utc_now_iso,
    validate_product_db_dataframe,
)
from scripts.flows.F.F091_reserve_amazon_listing_skus import generate_expected_seller_sku


DEFAULT_SCANNER_SOURCE = ROOT / "out" / "scanner_latest.csv"
DEFAULT_PRODUCT_DB_SOURCE = ROOT / "out" / "product_db_preview.csv"
DEFAULT_SQLITE_PATH = ROOT / "out" / "sql" / "sellerone_dev.sqlite3"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_INSERT_EVENTS = DEFAULT_OUTPUT_DIR / "scanner_product_db_insert_events.csv"
DEFAULT_SUMMARY = DEFAULT_OUTPUT_DIR / "scanner_product_db_insert_summary.json"
DEFAULT_MARKETPLACE_ID = "A1F83G8C2ARO7P"
DUPLICATE_ASIN_REASON = "different_sku_separate_product_not_sold_together"

INSERT_EVENT_COLUMNS: tuple[str, ...] = (
    "event_utc",
    "event_id",
    "apply_status",
    "seller_sku",
    "asin",
    "supplier_sku",
    "supplier",
    "candidate_id",
    "reason",
    "source_reference",
)


def _clean_money(value: object) -> str:
    text = normalize_text(value).replace(",", "").replace("GBP", "").replace("£", "").strip()
    if not text:
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed < 0:
        return ""
    return f"{parsed:.2f}"


def _vat_rate(value: object) -> str:
    text = normalize_text(value).replace("%", "").strip()
    if not text:
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed < 0:
        return ""
    if parsed <= 1:
        parsed *= 100
    return str(int(parsed)) if parsed.is_integer() else f"{parsed:.2f}".rstrip("0").rstrip(".")


def _supplier_code(value: object) -> str:
    text = "".join(ch for ch in normalize_text(value).upper() if ch.isalnum())
    return (text[:3] or "SUP").ljust(3, "X")


def _read_scanner(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _dedupe_scanner(scanner: pd.DataFrame) -> pd.DataFrame:
    if scanner.empty:
        return scanner.copy()
    work = scanner.copy()
    for column in ("asin", "supplier_sku", "candidate_id"):
        if column not in work.columns:
            work[column] = ""
    work["_asin_key"] = work["asin"].map(normalize_key)
    work["_supplier_sku_key"] = work["supplier_sku"].map(normalize_text)
    work["_candidate_id_key"] = work["candidate_id"].map(normalize_text)
    work = work.loc[work["_asin_key"].ne("") & work["_supplier_sku_key"].ne("")].copy()
    work = work.drop_duplicates(subset=["_asin_key", "_supplier_sku_key", "_candidate_id_key"], keep="first")
    return work.drop(columns=["_asin_key", "_supplier_sku_key", "_candidate_id_key"], errors="ignore")


def _existing_asin_counts(product_db: pd.DataFrame) -> Counter[str]:
    if product_db.empty or "asin" not in product_db.columns:
        return Counter()
    return Counter(normalize_key(value) for value in product_db["asin"].tolist() if normalize_key(value))


def _existing_skus(product_db: pd.DataFrame) -> set[str]:
    if product_db.empty or "seller_sku" not in product_db.columns:
        return set()
    return {normalize_key(value) for value in product_db["seller_sku"].tolist() if normalize_key(value)}


def _scanner_asin_counts(scanner: pd.DataFrame) -> Counter[str]:
    if scanner.empty or "asin" not in scanner.columns:
        return Counter()
    return Counter(normalize_key(value) for value in scanner["asin"].tolist() if normalize_key(value))


def _build_insert_row(
    *,
    scanner_row: dict[str, str],
    observed_utc: str,
    marketplace_id: str,
    scanner_asin_counts: Counter[str],
) -> dict[str, str]:
    supplier = normalize_text(scanner_row.get("supplier", ""))
    supplier_sku = normalize_text(scanner_row.get("supplier_sku", ""))
    candidate_id = normalize_text(scanner_row.get("candidate_id", ""))
    asin = normalize_key(scanner_row.get("asin", ""))
    scan_day = normalize_text(scanner_row.get("scan_day", ""))
    seller_sku = generate_expected_seller_sku(
        supplier_id=supplier,
        active_run_id=scan_day,
        candidate_id=candidate_id,
        asin=asin,
        marketplace_id=marketplace_id,
    )
    duplicate_reason = DUPLICATE_ASIN_REASON if scanner_asin_counts.get(asin, 0) > 1 else ""
    cost = _clean_money(scanner_row.get("cost", ""))
    return {
        "seller_sku": seller_sku,
        "asin": asin,
        "title": normalize_text(scanner_row.get("title", "")),
        "brand_name": normalize_text(scanner_row.get("brand", "")),
        "main_image": "",
        "sale_status": "inactive",
        "supplier_code": _supplier_code(supplier),
        "supplier_name": supplier,
        "supplier_pack_size": "1",
        "amazon_pack_size": "1",
        "supplier_catalog_price": cost,
        "last_purchase_price": cost,
        "vat_rate": _vat_rate(scanner_row.get("vat", "")) or "20",
        "fba_fee_10": "",
        "fba_fee_100": "",
        "referral_fee_10": "",
        "referral_fee_100": "",
        "live_listing_price": "",
        "stock_total": "0",
        "stock_available": "0",
        "stock_reserved": "0",
        "stock_inbound": "0",
        "last_updated": observed_utc,
        "duplicate_asin_reason": duplicate_reason,
        "supplier_sku": supplier_sku,
        "barcode": normalize_text(scanner_row.get("barcode", "")),
        "candidate_id": candidate_id,
        "scanner_buy_box_price": _clean_money(scanner_row.get("buy_box_price", "")),
        "scanner_pf": normalize_text(scanner_row.get("pf", "")),
        "scanner_recommendation_status": normalize_text(scanner_row.get("recommendation_status", "")),
        "scanner_scan_day": scan_day,
        "notes": (
            "Inserted from scanner review; inactive until Amazon listing and operations approval. "
            f"supplier_sku={supplier_sku}; not_sold_together_reason={duplicate_reason or 'single_scanner_asin'}"
        ),
    }


def build_insert_plan(
    *,
    scanner: pd.DataFrame,
    product_db: pd.DataFrame,
    observed_utc: str,
    marketplace_id: str = DEFAULT_MARKETPLACE_ID,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    scanner_rows = _dedupe_scanner(scanner)
    existing_asins = _existing_asin_counts(product_db)
    existing_skus = _existing_skus(product_db)
    scanner_asins = _scanner_asin_counts(scanner_rows)
    planned_rows: list[dict[str, str]] = []
    event_rows: list[dict[str, str]] = []
    seen_skus: set[str] = set()
    for _, source_row in scanner_rows.iterrows():
        source = {str(key): normalize_text(value) for key, value in source_row.to_dict().items()}
        asin = normalize_key(source.get("asin", ""))
        if not asin or existing_asins.get(asin, 0) > 0:
            continue
        row = _build_insert_row(
            scanner_row=source,
            observed_utc=observed_utc,
            marketplace_id=marketplace_id,
            scanner_asin_counts=scanner_asins,
        )
        sku_key = normalize_key(row["seller_sku"])
        if not sku_key or sku_key in existing_skus or sku_key in seen_skus:
            event_rows.append(
                {
                    "event_utc": observed_utc,
                    "event_id": f"scanner-product-db-insert-{source.get('candidate_id', '')[:12]}",
                    "apply_status": "held",
                    "seller_sku": row.get("seller_sku", ""),
                    "asin": asin,
                    "supplier_sku": source.get("supplier_sku", ""),
                    "supplier": source.get("supplier", ""),
                    "candidate_id": source.get("candidate_id", ""),
                    "reason": "seller_sku_collision",
                    "source_reference": "P011_apply_scanner_product_db_inserts.py",
                }
            )
            continue
        planned_rows.append(row)
        seen_skus.add(sku_key)
        event_rows.append(
            {
                "event_utc": observed_utc,
                "event_id": f"scanner-product-db-insert-{source.get('candidate_id', '')[:12]}",
                "apply_status": "planned",
                "seller_sku": row.get("seller_sku", ""),
                "asin": asin,
                "supplier_sku": source.get("supplier_sku", ""),
                "supplier": source.get("supplier", ""),
                "candidate_id": source.get("candidate_id", ""),
                "reason": row.get("duplicate_asin_reason", "") or "new_scanner_asin_not_in_product_db",
                "source_reference": "P011_apply_scanner_product_db_inserts.py",
            }
        )
    return pd.DataFrame(planned_rows), event_rows


def _classify_existing_duplicate_asins(product_db: pd.DataFrame) -> pd.DataFrame:
    if product_db.empty or "asin" not in product_db.columns or "seller_sku" not in product_db.columns:
        return product_db.copy()
    out = product_db.copy()
    if "duplicate_asin_reason" not in out.columns:
        out["duplicate_asin_reason"] = ""
    asin_counts = _existing_asin_counts(out)
    for idx, row in out.iterrows():
        asin = normalize_key(row.get("asin", ""))
        if asin and asin_counts.get(asin, 0) > 1:
            out.at[idx, "duplicate_asin_reason"] = DUPLICATE_ASIN_REASON
    return out


def _write_sql_table(sqlite_path: Path, df: pd.DataFrame, observed_utc: str) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_product_db_import_rows(df, observed_utc=observed_utc)
    columns = [
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
        "duplicate_asin_reason",
        "source_payload_json",
        "created_at_utc",
        "updated_at_utc",
    ]
    placeholders = ", ".join(["?"] * len(columns))
    quoted = ", ".join(f'"{column}"' for column in columns)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute(product_db_create_table_sql(backend="sqlite"))
        for sql in product_db_indexes_sql(backend="sqlite"):
            conn.execute(sql)
        conn.execute(f'DELETE FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}"')
        conn.executemany(
            f'INSERT INTO "{SQL_TABLE_PRODUCT_DB_PRODUCTS}" ({quoted}) VALUES ({placeholders})',
            [[row.get(column) for column in columns] for row in rows],
        )
        conn.commit()
    finally:
        conn.close()


def _export_preview_mirror(path: Path, df: pd.DataFrame, original_columns: list[str]) -> None:
    export_columns = list(original_columns)
    for column in PRODUCT_DB_REQUIRED_COLUMNS:
        if column not in export_columns:
            export_columns.append(column)
    for column in (
        "duplicate_asin_reason",
        "supplier_sku",
        "barcode",
        "candidate_id",
        "scanner_buy_box_price",
        "scanner_pf",
        "scanner_recommendation_status",
        "scanner_scan_day",
    ):
        if column in df.columns and column not in export_columns:
            export_columns.append(column)
    export_df = df.copy()
    for column in export_columns:
        if column not in export_df.columns:
            export_df[column] = ""
    path.parent.mkdir(parents=True, exist_ok=True)
    export_df[export_columns].to_csv(path, index=False)


def _query_sql_counts(sqlite_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(sqlite_path)
    try:
        total = conn.execute(f'SELECT COUNT(*) FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}"').fetchone()[0]
        unique_skus = conn.execute(
            f'SELECT COUNT(DISTINCT seller_sku) FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}"'
        ).fetchone()[0]
        duplicate_reason_rows = conn.execute(
            f'SELECT COUNT(*) FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}" WHERE duplicate_asin_reason != ""'
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "sql_rows": int(total),
        "sql_unique_seller_sku": int(unique_skus),
        "sql_duplicate_asin_reason_rows": int(duplicate_reason_rows),
    }


def run_apply(
    *,
    scanner_path: Path = DEFAULT_SCANNER_SOURCE,
    product_db_path: Path = DEFAULT_PRODUCT_DB_SOURCE,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    marketplace_id: str = DEFAULT_MARKETPLACE_ID,
    apply: bool = False,
    confirm_scanner_product_db_insert: bool = False,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    events_path = output_dir / DEFAULT_INSERT_EVENTS.name
    summary_path = output_dir / DEFAULT_SUMMARY.name
    if not scanner_path.exists() or not product_db_path.exists():
        payload = {
            "status": "fail",
            "reason": "missing_source_file",
            "scanner_path": str(scanner_path),
            "product_db_path": str(product_db_path),
            "observed_utc": observed,
        }
        summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    product_db, raw_headers = load_product_db_for_validation(product_db_path)
    validation = validate_product_db_dataframe(
        product_db,
        raw_headers=raw_headers,
        source_path=str(product_db_path),
        observed_utc=observed,
    )
    if validation.status == "fail":
        payload = {
            "status": "fail",
            "reason": "product_db_contract_failed",
            "product_db_contract_status": validation.status,
            "observed_utc": observed,
        }
        summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    scanner = _read_scanner(scanner_path)
    planned, event_rows = build_insert_plan(
        scanner=scanner,
        product_db=product_db,
        observed_utc=observed,
        marketplace_id=marketplace_id,
    )
    pd.DataFrame(event_rows, columns=INSERT_EVENT_COLUMNS).to_csv(events_path, index=False)
    status = "dry_run"
    sql_counts: dict[str, int] = {}
    final_rows = int(len(product_db.index))
    if apply and confirm_scanner_product_db_insert:
        base = _classify_existing_duplicate_asins(product_db)
        combined = pd.concat([base, planned], ignore_index=True, sort=False).fillna("")
        _write_sql_table(sqlite_path, combined, observed)
        _export_preview_mirror(product_db_path, combined, raw_headers)
        status = "applied"
        sql_counts = _query_sql_counts(sqlite_path)
        final_rows = int(len(combined.index))
        for row in event_rows:
            if row.get("apply_status") == "planned":
                row["apply_status"] = "applied"
        pd.DataFrame(event_rows, columns=INSERT_EVENT_COLUMNS).to_csv(events_path, index=False)
    elif apply:
        status = "confirmation_missing"

    payload = {
        "status": status,
        "observed_utc": observed,
        "scanner_path": str(scanner_path),
        "product_db_path": str(product_db_path),
        "sqlite_path": str(sqlite_path),
        "product_db_contract_status": validation.status,
        "starting_product_db_rows": int(len(product_db.index)),
        "planned_insert_rows": int(len(planned.index)),
        "held_rows": sum(1 for row in event_rows if row.get("apply_status") == "held"),
        "final_product_db_rows": final_rows,
        "duplicate_asin_reason": DUPLICATE_ASIN_REASON,
        "events_path": str(events_path),
        **sql_counts,
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply approved scanner Product DB inserts to the SQL Product DB table.")
    parser.add_argument("--scanner", default=str(DEFAULT_SCANNER_SOURCE))
    parser.add_argument("--product-db", default=str(DEFAULT_PRODUCT_DB_SOURCE))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--marketplace-id", default=DEFAULT_MARKETPLACE_ID)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-scanner-product-db-insert", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_apply(
        scanner_path=Path(args.scanner),
        product_db_path=Path(args.product_db),
        sqlite_path=Path(args.sqlite_path),
        output_dir=Path(args.output_dir),
        marketplace_id=args.marketplace_id,
        apply=bool(args.apply),
        confirm_scanner_product_db_insert=bool(args.confirm_scanner_product_db_insert),
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        for key, value in payload.items():
            print(f"{key}={json.dumps(value, ensure_ascii=True) if isinstance(value, dict) else value}")
    return 0 if payload["status"] not in {"fail", "confirmation_missing"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
