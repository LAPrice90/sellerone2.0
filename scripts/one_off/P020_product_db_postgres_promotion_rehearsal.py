from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.core.storage.product_db_contract import PRODUCT_DB_REQUIRED_COLUMNS, utc_now_iso


DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_CHECKS_PATH = DEFAULT_OUTPUT_DIR / "product_db_postgres_promotion_rehearsal.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "product_db_postgres_promotion_rehearsal_summary.json"

PRODUCT_DB_POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS product_db_products (
    seller_sku TEXT PRIMARY KEY,
    asin TEXT,
    title TEXT,
    source_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at_utc TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_db_products_asin ON product_db_products (asin);
""".strip()

CHECK_COLUMNS: tuple[str, ...] = ("check", "status", "value", "notes", "observed_utc", "source_path")


def _check(check: str, status: str, value: object, notes: str, observed_utc: str, source_path: Path) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": str(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def run_check(*, output_dir: Path = DEFAULT_OUTPUT_DIR, observed_utc: str | None = None) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    checks_path = output_dir / DEFAULT_CHECKS_PATH.name
    summary_path = output_dir / DEFAULT_SUMMARY_PATH.name
    ddl_lower = PRODUCT_DB_POSTGRES_DDL.lower()
    rows = [
        _check("ddl_table_present", "ok" if "create table" in ddl_lower and "product_db_products" in ddl_lower else "fail", "product_db_products", "DDL creates Product DB table", observed, checks_path),
        _check("ddl_seller_sku_primary_key", "ok" if "seller_sku text primary key" in ddl_lower else "fail", "seller_sku", "seller_sku is the primary key", observed, checks_path),
        _check("ddl_asin_non_unique_index", "ok" if "create index" in ddl_lower and "asin" in ddl_lower and "create unique index" not in ddl_lower else "fail", "idx_product_db_products_asin", "ASIN index is non-unique", observed, checks_path),
        _check("required_columns_named", "ok" if {"seller_sku", "asin"}.issubset(set(PRODUCT_DB_REQUIRED_COLUMNS)) else "fail", len(PRODUCT_DB_REQUIRED_COLUMNS), "Product DB required columns available to seed/export", observed, ROOT / "scripts" / "core" / "storage" / "product_db_contract.py"),
        _check("seed_export_reconcile_plan", "ok", "defined", "Seed from SQLite/SQL authority, export mirror only after reconciliation, compare row count and seller_sku set", observed, checks_path),
        _check("rollback_plan", "ok", "defined", "Keep pre-promotion backup and retain CSV export as rollback artifact", observed, checks_path),
        _check("production_promotion_status", "ok", "not_run_requires_explicit_approval", "No production PostgreSQL connection or write is attempted by this rehearsal", observed, checks_path),
    ]
    checks_df = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    checks_df.to_csv(checks_path, index=False)
    fail_count = int(checks_df["status"].eq("fail").sum())
    payload = {
        "status": "fail" if fail_count else "ok",
        "observed_utc": observed,
        "fail_count": fail_count,
        "promotion_status": "not_run_requires_explicit_approval",
        "required_env_vars": ["SELLERONE_DATABASE_URL"],
        "ddl": PRODUCT_DB_POSTGRES_DDL,
        "checks_path": str(checks_path),
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline Product DB PostgreSQL promotion rehearsal.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_check(output_dir=Path(args.output_dir))
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
