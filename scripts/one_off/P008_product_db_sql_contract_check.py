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

from scripts.core.storage.product_db_contract import (
    SQL_TABLE_PRODUCT_DB_PRODUCTS,
    load_product_db_for_validation,
    stage_product_db_import_sqlite,
    utc_now_iso,
    validate_product_db_dataframe,
)


DEFAULT_SOURCE = ROOT / "out" / "product_db_preview.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_STAGING_SQLITE = DEFAULT_OUTPUT_DIR / "product_db_contract_staging.sqlite3"

CHECK_COLUMNS = ["check", "status", "value", "notes", "observed_utc", "source_path"]
DUPLICATE_ASIN_COLUMNS = ["asin", "match_count", "seller_skus", "action", "reason"]


def run_contract_check(
    *,
    source_path: Path = DEFAULT_SOURCE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    staging_sqlite_path: Path = DEFAULT_STAGING_SQLITE,
    staged_import: bool = True,
) -> dict[str, Any]:
    observed = utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    checks_path = output_dir / "product_db_sql_contract_check.csv"
    duplicate_asin_path = output_dir / "product_db_duplicate_asin_review.csv"
    summary_path = output_dir / "product_db_sql_contract_summary.json"

    if not source_path.exists():
        checks = [
            {
                "check": "product_db_source_exists",
                "status": "fail",
                "value": "0",
                "notes": "source file missing",
                "observed_utc": observed,
                "source_path": str(source_path),
            }
        ]
        duplicate_rows: list[dict[str, str]] = []
        status = "fail"
        source_rows = 0
        source_columns = 0
    else:
        df, raw_headers = load_product_db_for_validation(source_path)
        validation = validate_product_db_dataframe(
            df,
            raw_headers=raw_headers,
            source_path=str(source_path),
            observed_utc=observed,
        )
        checks = validation.checks
        duplicate_rows = validation.duplicate_asin_rows
        status = validation.status
        source_rows = int(len(df.index))
        source_columns = int(len(raw_headers))

    pd.DataFrame(checks, columns=CHECK_COLUMNS).to_csv(checks_path, index=False)
    pd.DataFrame(duplicate_rows, columns=DUPLICATE_ASIN_COLUMNS).to_csv(duplicate_asin_path, index=False)

    staged_import_result: dict[str, str] = {
        "status": "skipped",
        "reason": "disabled" if not staged_import else "contract_failed",
        "sqlite_path": str(staging_sqlite_path),
        "table": SQL_TABLE_PRODUCT_DB_PRODUCTS,
        "rows": "0",
        "unique_seller_sku": "0",
    }
    if source_path.exists() and status != "fail" and staged_import:
        df, _ = load_product_db_for_validation(source_path)
        import_result = stage_product_db_import_sqlite(
            df=df,
            sqlite_path=staging_sqlite_path,
            observed_utc=observed,
        )
        staged_import_result = {
            "status": "passed",
            "reason": "",
            **import_result,
        }

    fail_count = sum(1 for row in checks if row.get("status") == "fail")
    warn_count = sum(1 for row in checks if row.get("status") == "warn")
    ok_count = sum(1 for row in checks if row.get("status") == "ok")
    payload = {
        "status": status,
        "source_path": str(source_path),
        "source_rows": source_rows,
        "source_columns": source_columns,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "ok_count": ok_count,
        "duplicate_asin_review_count": len(duplicate_rows),
        "staged_import": staged_import_result,
        "checks_path": str(checks_path),
        "duplicate_asin_path": str(duplicate_asin_path),
        "summary_path": str(summary_path),
        "observed_utc": observed,
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Product DB legacy source against the SQL Product DB contract.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Legacy Product DB CSV source to validate.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for local proof outputs.")
    parser.add_argument(
        "--staging-sqlite-path",
        default=str(DEFAULT_STAGING_SQLITE),
        help="Scratch SQLite DB for contract-valid staged import proof.",
    )
    parser.add_argument("--no-staged-import", action="store_true", help="Only write validation reports; do not stage import.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_contract_check(
        source_path=Path(args.source),
        output_dir=Path(args.output_dir),
        staging_sqlite_path=Path(args.staging_sqlite_path),
        staged_import=not bool(args.no_staged_import),
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            if isinstance(value, dict):
                print(f"{key}={json.dumps(value, ensure_ascii=True, sort_keys=True)}")
            else:
                print(f"{key}={value}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
