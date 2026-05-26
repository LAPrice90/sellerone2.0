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
    load_product_db_for_validation,
    load_product_db_products_from_sqlite,
    normalize_key,
    utc_now_iso,
    validate_product_db_dataframe,
)
from scripts.flows.O._contract_io import read_o_contract_df


DEFAULT_SQLITE_PATH = ROOT / "out" / "sql" / "sellerone_dev.sqlite3"
DEFAULT_PRODUCT_DB_MIRROR = ROOT / "out" / "product_db_preview.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_CHECKS_PATH = DEFAULT_OUTPUT_DIR / "product_db_sql_authority_rehearsal.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "product_db_sql_authority_rehearsal_summary.json"

CHECK_COLUMNS: tuple[str, ...] = (
    "check",
    "status",
    "value",
    "notes",
    "observed_utc",
    "source_path",
)


def _check(
    *,
    check: str,
    status: str,
    value: object,
    notes: str,
    observed_utc: str,
    source_path: Path,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": str(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _sku_set(df: pd.DataFrame, column: str = "seller_sku") -> set[str]:
    if df.empty or column not in df.columns:
        return set()
    return {normalize_key(value) for value in df[column].tolist() if normalize_key(value)}


def _read_csv_safe(path: Path) -> tuple[pd.DataFrame, list[str]]:
    if not path.exists():
        return pd.DataFrame(), []
    return load_product_db_for_validation(path)


def run_check(
    *,
    root: Path = ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    product_db_mirror: Path = DEFAULT_PRODUCT_DB_MIRROR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> dict[str, Any]:
    observed = observed_utc or utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    checks_path = output_dir / DEFAULT_CHECKS_PATH.name
    summary_path = output_dir / DEFAULT_SUMMARY_PATH.name

    sql_df = load_product_db_products_from_sqlite(sqlite_path)
    mirror_df, mirror_headers = _read_csv_safe(product_db_mirror)
    o_view = read_o_contract_df(root, "product_db_operator_view")

    sql_skus = _sku_set(sql_df)
    mirror_skus = _sku_set(mirror_df)
    o_skus = _sku_set(o_view)

    rows: list[dict[str, str]] = []
    rows.append(
        _check(
            check="sql_product_db_source_present",
            status="ok" if not sql_df.empty else "fail",
            value=len(sql_df.index),
            notes="SQL Product DB table is the rehearsal authority" if not sql_df.empty else "SQL Product DB table missing or empty",
            observed_utc=observed,
            source_path=sqlite_path,
        )
    )
    rows.append(
        _check(
            check="sql_product_db_seller_sku_unique",
            status="ok" if len(sql_skus) == len(sql_df.index) and bool(sql_skus) else "fail",
            value=len(sql_skus),
            notes="SQL seller_sku count matches SQL rows" if len(sql_skus) == len(sql_df.index) and bool(sql_skus) else "SQL seller_sku count mismatch",
            observed_utc=observed,
            source_path=sqlite_path,
        )
    )

    if not sql_df.empty:
        validation = validate_product_db_dataframe(
            sql_df,
            raw_headers=list(sql_df.columns),
            source_path=str(sqlite_path),
            observed_utc=observed,
        )
        rows.append(
            _check(
                check="sql_product_db_contract",
                status=validation.status,
                value=f"fail={validation.fail_count};warn={validation.warn_count};ok={validation.ok_count}",
                notes="SQL Product DB contract validation result",
                observed_utc=observed,
                source_path=sqlite_path,
            )
        )

    if product_db_mirror.exists():
        rows.append(
            _check(
                check="csv_mirror_rows_match_sql",
                status="ok" if mirror_skus == sql_skus else "warn",
                value=f"csv={len(mirror_skus)};sql={len(sql_skus)}",
                notes=(
                    "CSV mirror matches SQL seller_sku set"
                    if mirror_skus == sql_skus
                    else "CSV mirror is stale or divergent from SQL authority"
                ),
                observed_utc=observed,
                source_path=product_db_mirror,
            )
        )
        mirror_validation = validate_product_db_dataframe(
            mirror_df,
            raw_headers=mirror_headers,
            source_path=str(product_db_mirror),
            observed_utc=observed,
        )
        rows.append(
            _check(
                check="csv_mirror_contract",
                status=mirror_validation.status,
                value=f"fail={mirror_validation.fail_count};warn={mirror_validation.warn_count};ok={mirror_validation.ok_count}",
                notes="CSV mirror contract validation result; mirror is not authority during rehearsal",
                observed_utc=observed,
                source_path=product_db_mirror,
            )
        )
    else:
        rows.append(
            _check(
                check="csv_mirror_rows_match_sql",
                status="warn",
                value=f"csv=missing;sql={len(sql_skus)}",
                notes="CSV mirror missing; SQL remains rehearsal authority",
                observed_utc=observed,
                source_path=product_db_mirror,
            )
        )

    rows.append(
        _check(
            check="o_product_db_operator_view_rows_match_sql",
            status="ok" if o_skus == sql_skus and bool(sql_skus) else "fail",
            value=f"o={len(o_skus)};sql={len(sql_skus)}",
            notes=(
                "O Product DB operator view matches SQL seller_sku set"
                if o_skus == sql_skus and bool(sql_skus)
                else "O Product DB operator view does not match SQL seller_sku set"
            ),
            observed_utc=observed,
            source_path=root / "out" / "systems" / "O" / "live" / "product_db_operator_view.csv",
        )
    )

    checks_df = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    checks_df.to_csv(checks_path, index=False)
    fail_count = int(checks_df["status"].eq("fail").sum())
    warn_count = int(checks_df["status"].eq("warn").sum())
    status = "fail" if fail_count else ("warn" if warn_count else "ok")
    payload = {
        "status": status,
        "observed_utc": observed,
        "sql_rows": int(len(sql_df.index)),
        "sql_unique_seller_sku": int(len(sql_skus)),
        "csv_mirror_rows": int(len(mirror_df.index)),
        "csv_mirror_unique_seller_sku": int(len(mirror_skus)),
        "o_view_rows": int(len(o_view.index)),
        "o_view_unique_seller_sku": int(len(o_skus)),
        "fail_count": fail_count,
        "warn_count": warn_count,
        "checks_path": str(checks_path),
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local SQL Product DB authority rehearsal against mirror and O view.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--product-db-mirror", default=str(DEFAULT_PRODUCT_DB_MIRROR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = run_check(
        root=Path(args.root),
        sqlite_path=Path(args.sqlite_path),
        product_db_mirror=Path(args.product_db_mirror),
        output_dir=Path(args.output_dir),
    )
    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0 if payload["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
