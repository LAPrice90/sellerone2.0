from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core.storage.pandas_bridge import quote_identifier, validate_identifier


EXPORT_TARGETS: dict[str, str] = {
    "a_fees_estimates": "out/fees_estimates.csv",
    "a_fees_failed": "out/fees_failed.csv",
    "a_fees_latest": "out/fees_latest.csv",
    "a_inventory_adjustments_latest": "out/inventory_adjustments_latest.csv",
    "a_inventory_history": "out/inventory_history.csv",
    "a_inventory_ledger_raw": "out/inventory_ledger_raw.csv",
    "a_inventory_summaries": "out/inventory_summaries.csv",
    "a_stock_events_raw": "out/stock_events_raw.csv",
    "a_stock_receipt_summary": "out/stock_receipt_summary.csv",
    "a_stock_receipts_latest": "out/stock_receipts_latest.csv",
    "b_financial_events_level3_official": "out/financial_events_level3_official.csv",
    "b_financial_ledger_fx": "out/financial_ledger_fx.csv",
    "b_fx_rates_daily": "out/fx_rates_daily.csv",
    "b_l1_missing_fee_keys": "out/l1_missing_fee_keys.csv",
    "b_l3_orphans": "out/l3_orphans.csv",
    "b_order_cogs_from_tokens": "out/order_cogs_from_tokens.csv",
    "b_order_items_all": "out/order_items_all.csv",
    "b_order_ledger_fx": "out/order_ledger_fx.csv",
    "b_order_master": "out/order_master.csv",
    "b_orders_all": "out/orders_all.csv",
    "b_orders_missing_tokens": "out/orders_missing_tokens.csv",
    "b_phase1_sku_scope": "out/phase1_sku_scope.csv",
    "b_refund_token_events": "out/refund_token_events.csv",
    "b_stock_adjustment_token_events": "out/stock_adjustment_token_events.csv",
    "b_token_allocations_live": "out/token_allocations_live.csv",
    "b_token_cogs_ledger": "out/token_cogs_ledger.csv",
    "b_token_daily_checklist": "out/token_daily_checklist.csv",
    "b_token_events": "out/token_events.csv",
    "b_token_ledger_live": "out/token_ledger_live.csv",
    "b_token_movement_log": "out/token_movement_log.csv",
    "e_sales_truth_reconciliation": "out/sales_truth_reconciliation_latest.csv",
    "e_sales_truth_sku_30d": "out/sales_truth_sku_30d_latest.csv",
    "e_sku_daily_sales_truth": "out/sku_daily_sales_truth_latest.csv",
    "e_sku_performance_summary": "out/sku_performance_summary.csv",
    "e_sku_restock_signals": "out/sku_restock_signals.csv",
    "e_sku_roi_snapshot": "out/sku_roi_snapshot.csv",
    "e_sku_roi_snapshot_by_country": "out/sku_roi_snapshot_by_country.csv",
    "e_sku_roi_snapshot_non_uk": "out/sku_roi_snapshot_non_uk.csv",
    "e_sku_roi_snapshot_uk": "out/sku_roi_snapshot_uk.csv",
    "e_sku_sales_velocity": "out/sku_sales_velocity.csv",
    "e_study_report": "out/e_study_report.csv",
    "h_hos_daily_market_history": "out/hos_daily_market_history.csv",
    "h_hos_daily_market_snapshot": "out/hos_daily_market_snapshot_latest.csv",
    "h_listing_offer_history": "out/listing_offer_history.csv",
    "h_seller_of_interest": "out/h_seller_of_interest.csv",
    "sys_inbound_shipment_contents": "out/inbound_shipment_contents.csv",
    "sys_inbound_shipment_contents_raw": "out/inbound_shipment_contents_raw.csv",
    "sys_product_db_preview": "out/product_db_preview.csv",
}


@dataclass(frozen=True)
class ValidationResult:
    status: str
    checked_count: int
    pass_count: int
    fail_count: int
    missing_csv_count: int
    missing_table_count: int
    export_dir: Path
    report_path: Path
    summary_path: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        [table],
    ).fetchone()
    return bool(row)


def _metadata_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    if not _table_exists(conn, "storage_column_metadata"):
        return []
    rows = conn.execute(
        """
        SELECT original_column_name
        FROM storage_column_metadata
        WHERE table_name = ?
        ORDER BY ordinal
        """,
        [table],
    ).fetchall()
    return [str(row[0]) for row in rows]


def _read_sql_table(conn: sqlite3.Connection, table: str, csv_path: Path | None = None) -> pd.DataFrame:
    table = validate_identifier(table)
    df = pd.read_sql_query(f"SELECT * FROM {quote_identifier(table)}", conn)
    original_columns = _metadata_columns(conn, table)
    if original_columns and len(original_columns) == len(df.columns):
        df.columns = original_columns
    elif csv_path is not None and csv_path.exists():
        csv_columns = pd.read_csv(csv_path, nrows=0, dtype=str, keep_default_na=False).columns.tolist()
        if len(csv_columns) == len(df.columns):
            df.columns = csv_columns
    return df.fillna("").astype(str)


def _read_csv_frame(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False).fillna("").astype(str)


def _canonical_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = StringIO()
    df.fillna("").astype(str).to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue().encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_export(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.fillna("").astype(str).to_csv(path, index=False, lineterminator="\n")


def validate_exports(
    *,
    sqlite_path: Path,
    output_dir: Path,
    targets: dict[str, str] | None = None,
    root: Path = ROOT,
) -> ValidationResult:
    target_map = EXPORT_TARGETS if targets is None else targets
    run_id = utc_now_iso().replace(":", "").replace("-", "")
    export_dir = output_dir / f"rollback_exports_{run_id}"
    files_dir = export_dir / "files"
    report_path = export_dir / "rollback_export_report.csv"
    summary_path = export_dir / "rollback_export_summary.json"
    export_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    conn = sqlite3.connect(sqlite_path)
    try:
        for table, rel_path in sorted(target_map.items()):
            csv_path = root / rel_path
            export_path = files_dir / rel_path
            status = "pass"
            detail = "row_count_header_and_canonical_hash_match"
            csv_rows = ""
            sql_rows = ""
            csv_columns = ""
            sql_columns = ""
            csv_hash = ""
            sql_hash = ""

            if not csv_path.exists():
                status = "missing_csv"
                detail = f"missing {rel_path}"
            elif not _table_exists(conn, table):
                status = "missing_table"
                detail = f"missing SQL table {table}"
            else:
                csv_df = _read_csv_frame(csv_path)
                sql_df = _read_sql_table(conn, table, csv_path)
                _write_export(sql_df, export_path)
                csv_rows = str(len(csv_df.index))
                sql_rows = str(len(sql_df.index))
                csv_columns = str(len(csv_df.columns))
                sql_columns = str(len(sql_df.columns))
                csv_hash = _sha256(_canonical_csv_bytes(csv_df))
                sql_hash = _sha256(_canonical_csv_bytes(sql_df))
                failures: list[str] = []
                if len(csv_df.index) != len(sql_df.index):
                    failures.append("row_count_mismatch")
                if list(csv_df.columns) != list(sql_df.columns):
                    failures.append("header_mismatch")
                if csv_hash != sql_hash:
                    failures.append("canonical_hash_mismatch")
                if failures:
                    status = "fail"
                    detail = "|".join(failures)

            rows.append(
                {
                    "table_name": table,
                    "csv_path": rel_path,
                    "export_path": str(export_path.relative_to(export_dir)).replace("\\", "/") if export_path.exists() else "",
                    "status": status,
                    "detail": detail,
                    "csv_rows": csv_rows,
                    "sql_rows": sql_rows,
                    "csv_columns": csv_columns,
                    "sql_columns": sql_columns,
                    "csv_canonical_sha256": csv_hash,
                    "sql_canonical_sha256": sql_hash,
                }
            )
    finally:
        conn.close()

    fieldnames = [
        "table_name",
        "csv_path",
        "export_path",
        "status",
        "detail",
        "csv_rows",
        "sql_rows",
        "csv_columns",
        "sql_columns",
        "csv_canonical_sha256",
        "sql_canonical_sha256",
    ]
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    pass_count = sum(1 for row in rows if row["status"] == "pass")
    fail_count = sum(1 for row in rows if row["status"] == "fail")
    missing_csv_count = sum(1 for row in rows if row["status"] == "missing_csv")
    missing_table_count = sum(1 for row in rows if row["status"] == "missing_table")
    status = "passed" if fail_count == 0 and missing_csv_count == 0 and missing_table_count == 0 else "failed"
    payload = {
        "status": status,
        "checked_count": len(rows),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "missing_csv_count": missing_csv_count,
        "missing_table_count": missing_table_count,
        "sqlite_path": str(sqlite_path),
        "export_dir": str(export_dir),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "checked_at_utc": utc_now_iso(),
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return ValidationResult(
        status=status,
        checked_count=len(rows),
        pass_count=pass_count,
        fail_count=fail_count,
        missing_csv_count=missing_csv_count,
        missing_table_count=missing_table_count,
        export_dir=export_dir,
        report_path=report_path,
        summary_path=summary_path,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate SQL rollback CSV exports against live compatibility CSVs.")
    parser.add_argument("--sqlite-path", default="out/sql/sellerone_dev.sqlite3")
    parser.add_argument("--output-dir", default="out/sql_migration")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_exports(sqlite_path=Path(args.sqlite_path), output_dir=Path(args.output_dir))
    payload = {
        "status": result.status,
        "checked_count": result.checked_count,
        "pass_count": result.pass_count,
        "fail_count": result.fail_count,
        "missing_csv_count": result.missing_csv_count,
        "missing_table_count": result.missing_table_count,
        "export_dir": str(result.export_dir),
        "report_path": str(result.report_path),
        "summary_path": str(result.summary_path),
    }
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
