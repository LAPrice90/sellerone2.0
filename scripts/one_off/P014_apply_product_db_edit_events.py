from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import (
    SQL_TABLE_PRODUCT_DB_PRODUCTS,
    load_product_db_for_validation,
    load_product_db_products_from_sqlite,
    normalize_key,
    normalize_text,
    stage_product_db_import_sqlite,
    utc_now_iso,
    validate_product_db_dataframe,
)
from scripts.flows.O.O420_product_database_edit_ui import validate_product_db_edit_payload
from scripts.flows.O._contract_io import read_o_contract_df


DEFAULT_PRODUCT_DB_SOURCE = ROOT / "out" / "product_db_preview.csv"
DEFAULT_SQLITE_PATH = ROOT / "out" / "sql" / "sellerone_dev.sqlite3"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_PLAN_PATH = DEFAULT_OUTPUT_DIR / "product_db_edit_event_apply_plan.csv"
DEFAULT_LOG_PATH = DEFAULT_OUTPUT_DIR / "product_db_edit_event_apply_log.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "product_db_edit_event_apply_summary.json"
VALID_SOURCE_MODES = {"auto", "sql", "csv"}

PLAN_COLUMNS: tuple[str, ...] = (
    "observed_utc",
    "event_id",
    "seller_sku",
    "asin",
    "apply_status",
    "reason",
    "notes",
)

LOG_COLUMNS: tuple[str, ...] = (
    "applied_utc",
    "event_id",
    "seller_sku",
    "asin",
    "apply_status",
    "reason",
)

EDIT_EVENT_UPDATE_COLUMNS: tuple[str, ...] = (
    "asin",
    "sale_status",
    "supplier_code",
    "supplier_name",
    "supplier_sku",
    "barcode",
    "supplier_pack_size",
    "amazon_pack_size",
    "order_qty_mode",
    "sell_pack_qty",
    "supplier_case_qty",
    "supplier_case_multiple",
    "valid_order_step",
    "repack_required",
    "bundle_required",
    "pack_conversion_note",
    "moq",
    "supplier_catalog_price",
    "last_purchase_price",
    "target_margin",
    "vat_rate",
    "notes",
)


def _read_csv_safe(path: Path, columns: tuple[str, ...]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=list(columns))
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=list(columns))


def _write_csv(path: Path, df: pd.DataFrame, columns: tuple[str, ...] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if columns is not None:
        for column in columns:
            if column not in out.columns:
                out[column] = ""
        out = out[list(columns)]
    out.to_csv(path, index=False)


def _sql_sku_set(sqlite_path: Path) -> set[str]:
    if not sqlite_path.exists():
        return set()
    conn = sqlite3.connect(sqlite_path)
    try:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            [SQL_TABLE_PRODUCT_DB_PRODUCTS],
        ).fetchone()
        if not table_exists:
            return set()
        rows = conn.execute(f'SELECT seller_sku FROM "{SQL_TABLE_PRODUCT_DB_PRODUCTS}"').fetchall()
        return {normalize_key(row[0]) for row in rows if normalize_key(row[0])}
    finally:
        conn.close()


def _sql_alignment(sqlite_path: Path, product_db: pd.DataFrame) -> dict[str, Any]:
    product_skus = {normalize_key(value) for value in product_db.get("seller_sku", pd.Series(dtype=str)).tolist()}
    product_skus.discard("")
    sql_skus = _sql_sku_set(sqlite_path)
    missing_in_sql = sorted(product_skus - sql_skus)
    extra_in_sql = sorted(sql_skus - product_skus)
    return {
        "status": "ok" if not missing_in_sql and not extra_in_sql and bool(sql_skus) else "fail",
        "product_db_rows": int(len(product_db.index)),
        "product_db_unique_seller_sku": int(len(product_skus)),
        "sql_rows": int(len(sql_skus)),
        "missing_in_sql": missing_in_sql[:25],
        "extra_in_sql": extra_in_sql[:25],
    }


def _load_product_db_source(
    *,
    product_db_path: Path,
    sqlite_path: Path,
    source_mode: str,
) -> tuple[pd.DataFrame, list[str], str, str]:
    mode = normalize_text(source_mode).lower() or "auto"
    if mode not in VALID_SOURCE_MODES:
        allowed = ", ".join(sorted(VALID_SOURCE_MODES))
        raise ValueError(f"unsupported source_mode {source_mode!r}; expected one of: {allowed}")

    sql_df = load_product_db_products_from_sqlite(sqlite_path) if mode in {"auto", "sql"} else pd.DataFrame()
    if not sql_df.empty:
        return sql_df, list(sql_df.columns), "sql", str(sqlite_path)
    if mode == "sql":
        return pd.DataFrame(), [], "sql_missing", str(sqlite_path)
    if product_db_path.exists():
        product_db, raw_headers = load_product_db_for_validation(product_db_path)
        return product_db, raw_headers, "csv", str(product_db_path)
    return pd.DataFrame(), [], "missing", str(product_db_path)


def _event_key_series(df: pd.DataFrame) -> pd.Series:
    if df.empty or "event_id" not in df.columns:
        return pd.Series(dtype=str)
    return df["event_id"].map(normalize_text)


def _asin_series(df: pd.DataFrame) -> pd.Series:
    if df.empty or "asin" not in df.columns:
        return pd.Series(dtype=str)
    return df["asin"].map(normalize_key)


def _find_product_row(product_db: pd.DataFrame, seller_sku: str) -> tuple[str, int | None]:
    sku = normalize_key(seller_sku)
    if not sku:
        return "missing_seller_sku", None
    if "seller_sku" not in product_db.columns:
        return "product_db_missing_seller_sku_column", None
    matches = product_db.index[product_db["seller_sku"].map(normalize_key).eq(sku)].tolist()
    if not matches:
        return "product_row_missing", None
    if len(matches) > 1:
        return "duplicate_seller_sku_in_product_db", None
    return "", int(matches[0])


def _asin_change_reason(product_db: pd.DataFrame, row_index: int, new_asin: str) -> str:
    asin = normalize_key(new_asin)
    if not asin:
        return ""
    current_asin = normalize_key(product_db.at[row_index, "asin"] if "asin" in product_db.columns else "")
    if current_asin == asin:
        return ""
    if current_asin:
        return "unsafe_asin_change_requires_review"
    duplicate_mask = _asin_series(product_db).eq(asin)
    if bool(duplicate_mask.any()):
        return "duplicate_asin_requires_classification"
    return ""


def _validate_event(product_db: pd.DataFrame, event: dict[str, str]) -> tuple[str, int | None, str]:
    errors = validate_product_db_edit_payload(event)
    if errors:
        return "validation_failed", None, "; ".join(errors)
    reason, row_index = _find_product_row(product_db, event.get("seller_sku", ""))
    if reason:
        return reason, None, reason
    assert row_index is not None
    asin_reason = _asin_change_reason(product_db, row_index, event.get("asin", ""))
    if asin_reason:
        return asin_reason, None, asin_reason
    return "", row_index, "ready"


def _apply_event_to_product_db(product_db: pd.DataFrame, row_index: int, event: dict[str, str], observed_utc: str) -> None:
    for column in EDIT_EVENT_UPDATE_COLUMNS:
        if column not in product_db.columns:
            product_db[column] = ""
        value = normalize_text(event.get(column, ""))
        if column == "asin" and value == "":
            continue
        product_db.at[row_index, column] = value
    if "last_updated" not in product_db.columns:
        product_db["last_updated"] = ""
    product_db.at[row_index, "last_updated"] = observed_utc


def _summary_status(*, base_status: str, held_rows: int) -> str:
    if base_status in {"fail", "confirmation_missing"}:
        return base_status
    if held_rows:
        return f"{base_status}_with_holds"
    return base_status


def run_apply(
    *,
    root: Path = ROOT,
    product_db_path: Path = DEFAULT_PRODUCT_DB_SOURCE,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    source_mode: str = "auto",
    apply: bool = False,
    confirm_product_db_edit_apply: bool = False,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / DEFAULT_PLAN_PATH.name
    log_path = output_dir / DEFAULT_LOG_PATH.name
    summary_path = output_dir / DEFAULT_SUMMARY_PATH.name

    if apply and not confirm_product_db_edit_apply:
        payload = {
            "status": "confirmation_missing",
            "reason": "apply_requires_confirm_product_db_edit_apply",
            "observed_utc": observed,
            "product_db_path": str(product_db_path),
            "sqlite_path": str(sqlite_path),
        }
        summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    product_db, raw_headers, loaded_source_mode, loaded_source_path = _load_product_db_source(
        product_db_path=product_db_path,
        sqlite_path=sqlite_path,
        source_mode=source_mode,
    )
    if product_db.empty and loaded_source_mode in {"missing", "sql_missing"}:
        payload = {
            "status": "fail",
            "reason": "missing_product_db_source" if loaded_source_mode == "missing" else "missing_sql_product_db_source",
            "observed_utc": observed,
            "source_mode": source_mode,
            "loaded_source_mode": loaded_source_mode,
            "loaded_source_path": loaded_source_path,
            "product_db_path": str(product_db_path),
            "sqlite_path": str(sqlite_path),
        }
        summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    validation = validate_product_db_dataframe(
        product_db,
        raw_headers=raw_headers,
        source_path=loaded_source_path,
        observed_utc=observed,
    )
    if validation.status == "fail":
        payload = {
            "status": "fail",
            "reason": "product_db_contract_failed",
            "observed_utc": observed,
            "source_mode": source_mode,
            "loaded_source_mode": loaded_source_mode,
            "loaded_source_path": loaded_source_path,
            "product_db_contract_status": validation.status,
            "product_db_path": str(product_db_path),
            "sqlite_path": str(sqlite_path),
        }
        summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    alignment = _sql_alignment(sqlite_path, product_db)
    if apply and alignment["status"] != "ok":
        payload = {
            "status": "fail",
            "reason": "sql_product_db_mirror_mismatch",
            "observed_utc": observed,
            "source_mode": source_mode,
            "loaded_source_mode": loaded_source_mode,
            "loaded_source_path": loaded_source_path,
            "sql_alignment": alignment,
            "product_db_path": str(product_db_path),
            "sqlite_path": str(sqlite_path),
        }
        summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        return payload

    events = read_o_contract_df(root, "product_db_edit_events")
    apply_log = _read_csv_safe(log_path, LOG_COLUMNS)
    already_applied = {
        event_id
        for event_id in _event_key_series(apply_log).tolist()
        if event_id
        and apply_log.loc[_event_key_series(apply_log).eq(event_id), "apply_status"].astype(str).str.lower().eq("applied").any()
    }

    working = product_db.copy()
    plan_rows: list[dict[str, str]] = []
    log_rows: list[dict[str, str]] = []
    seen_event_ids: set[str] = set()

    for _, event_row in events.iterrows():
        event = {str(key): normalize_text(value) for key, value in event_row.to_dict().items()}
        event_id = normalize_text(event.get("event_id", ""))
        seller_sku = normalize_text(event.get("seller_sku", ""))
        asin = normalize_text(event.get("asin", ""))

        if not event_id:
            status = "held"
            reason = "missing_event_id"
            notes = reason
            row_index = None
        elif event_id in seen_event_ids:
            status = "skipped"
            reason = "duplicate_event_id_in_inbox"
            notes = reason
            row_index = None
        elif event_id in already_applied:
            status = "skipped"
            reason = "already_applied"
            notes = reason
            row_index = None
        else:
            reason, row_index, notes = _validate_event(working, event)
            status = "held" if reason else ("applied" if apply else "applicable")

        seen_event_ids.add(event_id)
        if status == "applied" and row_index is not None:
            _apply_event_to_product_db(working, row_index, event, observed)
            log_rows.append(
                {
                    "applied_utc": observed,
                    "event_id": event_id,
                    "seller_sku": seller_sku,
                    "asin": asin,
                    "apply_status": "applied",
                    "reason": "local_sql_and_mirror_updated",
                }
            )

        plan_rows.append(
            {
                "observed_utc": observed,
                "event_id": event_id,
                "seller_sku": seller_sku,
                "asin": asin,
                "apply_status": status,
                "reason": reason,
                "notes": notes,
            }
        )

    plan_df = pd.DataFrame(plan_rows, columns=PLAN_COLUMNS)
    _write_csv(plan_path, plan_df, PLAN_COLUMNS)

    held_rows = int(plan_df["apply_status"].eq("held").sum()) if not plan_df.empty else 0
    applicable_rows = int(plan_df["apply_status"].eq("applicable").sum()) if not plan_df.empty else 0
    applied_rows = int(plan_df["apply_status"].eq("applied").sum()) if not plan_df.empty else 0
    skipped_rows = int(plan_df["apply_status"].eq("skipped").sum()) if not plan_df.empty else 0

    sql_stage: dict[str, str] = {}
    if apply and applied_rows:
        post_validation = validate_product_db_dataframe(
            working,
            raw_headers=list(working.columns),
            source_path=str(product_db_path),
            observed_utc=observed,
        )
        if post_validation.status == "fail":
            payload = {
                "status": "fail",
                "reason": "post_apply_product_db_contract_failed",
                "observed_utc": observed,
                "held_rows": held_rows,
                "applied_rows": applied_rows,
                "product_db_path": str(product_db_path),
                "sqlite_path": str(sqlite_path),
                "plan_path": str(plan_path),
            }
            summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
            return payload
        working.to_csv(product_db_path, index=False)
        sql_stage = stage_product_db_import_sqlite(df=working, sqlite_path=sqlite_path, observed_utc=observed)
        if log_rows:
            existing_log = _read_csv_safe(log_path, LOG_COLUMNS)
            combined_log = pd.concat([existing_log, pd.DataFrame(log_rows)], ignore_index=True)
            _write_csv(log_path, combined_log, LOG_COLUMNS)

    base_status = "applied" if apply else "dry_run"
    payload = {
        "status": _summary_status(base_status=base_status, held_rows=held_rows),
        "observed_utc": observed,
        "event_rows": int(len(events.index)),
        "applicable_rows": applicable_rows,
        "applied_rows": applied_rows,
        "held_rows": held_rows,
        "skipped_rows": skipped_rows,
        "product_db_rows": int(len(product_db.index)),
        "final_product_db_rows": int(len(working.index)),
        "product_db_contract_status": validation.status,
        "source_mode": source_mode,
        "loaded_source_mode": loaded_source_mode,
        "loaded_source_path": loaded_source_path,
        "sql_alignment": alignment,
        "product_db_path": str(product_db_path),
        "sqlite_path": str(sqlite_path),
        "plan_path": str(plan_path),
        "log_path": str(log_path),
        "summary_path": str(summary_path),
        "sql_stage": sql_stage,
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply staged Product DB edit events to local SQL and mirror outputs.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--product-db", default=str(DEFAULT_PRODUCT_DB_SOURCE))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--source-mode", choices=sorted(VALID_SOURCE_MODES), default="auto")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-product-db-edit-apply", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_apply(
        root=Path(args.root),
        product_db_path=Path(args.product_db),
        sqlite_path=Path(args.sqlite_path),
        output_dir=Path(args.output_dir),
        source_mode=args.source_mode,
        apply=bool(args.apply),
        confirm_product_db_edit_apply=bool(args.confirm_product_db_edit_apply),
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        for key, value in payload.items():
            print(f"{key}={json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else value}")
    return 0 if payload["status"] not in {"fail", "confirmation_missing"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
