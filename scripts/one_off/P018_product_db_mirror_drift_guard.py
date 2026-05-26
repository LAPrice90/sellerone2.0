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
)
from scripts.flows.O._contract_io import read_o_contract_df
from scripts.one_off.P014_apply_product_db_edit_events import run_apply


DEFAULT_SQLITE_PATH = ROOT / "out" / "sql" / "sellerone_dev.sqlite3"
DEFAULT_PRODUCT_DB_MIRROR = ROOT / "out" / "product_db_preview.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "sql_migration" / "product_db_contract"
DEFAULT_CHECKS_PATH = DEFAULT_OUTPUT_DIR / "product_db_mirror_drift_guard.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "product_db_mirror_drift_guard_summary.json"

CHECK_COLUMNS: tuple[str, ...] = ("check", "status", "value", "notes", "observed_utc", "source_path")


def _text(value: object) -> str:
    return str(value or "").strip()


def _sku_set(df: pd.DataFrame, column: str = "seller_sku") -> set[str]:
    if df.empty or column not in df.columns:
        return set()
    return {normalize_key(value) for value in df[column].tolist() if normalize_key(value)}


def _read_mirror(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df, _headers = load_product_db_for_validation(path)
    return df


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
        "value": _text(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


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
    mirror_df = _read_mirror(product_db_mirror)
    o_view = read_o_contract_df(root, "product_db_operator_view")
    source_health = read_o_contract_df(root, "product_db_source_health")
    p014 = run_apply(
        root=root,
        product_db_path=product_db_mirror,
        sqlite_path=sqlite_path,
        output_dir=output_dir,
        source_mode="auto",
        apply=False,
        observed_utc=observed,
    )

    sql_skus = _sku_set(sql_df)
    mirror_skus = _sku_set(mirror_df)
    o_skus = _sku_set(o_view)
    mirror_matches_sql = mirror_skus == sql_skus and bool(sql_skus)
    mirror_authority_status = "mirror_current_not_authority" if mirror_matches_sql else "mirror_stale_not_authority"
    source_mode_sql = False
    if not source_health.empty:
        text_blob = " ".join(source_health.astype(str).fillna("").agg(" ".join, axis=1).tolist()).lower()
        source_mode_sql = "sql_product_db_products" in text_blob or str(sqlite_path).lower() in text_blob

    rows = [
        _check(
            check="sql_product_db_present",
            status="ok" if not sql_df.empty else "fail",
            value=len(sql_df.index),
            notes="SQL Product DB table present",
            observed_utc=observed,
            source_path=sqlite_path,
        ),
        _check(
            check="sql_seller_sku_unique",
            status="ok" if len(sql_skus) == len(sql_df.index) and bool(sql_skus) else "fail",
            value=len(sql_skus),
            notes="SQL seller_sku is unique",
            observed_utc=observed,
            source_path=sqlite_path,
        ),
        _check(
            check="o_product_db_view_matches_sql",
            status="ok" if o_skus == sql_skus and bool(sql_skus) else "fail",
            value=f"o={len(o_skus)};sql={len(sql_skus)}",
            notes="O Product DB view matches SQL authority",
            observed_utc=observed,
            source_path=root / "out" / "systems" / "O" / "live" / "product_db_operator_view.csv",
        ),
        _check(
            check="csv_mirror_authority_status",
            status="ok" if mirror_matches_sql else "warn",
            value=f"csv={len(mirror_skus)};sql={len(sql_skus)};{mirror_authority_status}",
            notes="CSV mirror is classified as non-authority evidence",
            observed_utc=observed,
            source_path=product_db_mirror,
        ),
        _check(
            check="o030_source_mode_sql",
            status="ok" if source_mode_sql else "fail",
            value=1 if source_mode_sql else 0,
            notes="O030 source health shows SQL source mode",
            observed_utc=observed,
            source_path=root / "out" / "systems" / "O" / "live" / "product_db_source_health.csv",
        ),
        _check(
            check="p014_dry_run_loads_sql",
            status="ok" if _text(p014.get("loaded_source_mode")) == "sql" else "fail",
            value=p014.get("loaded_source_mode", ""),
            notes="P014 edit-event dry-run loads SQL authority",
            observed_utc=observed,
            source_path=output_dir / "product_db_edit_event_apply_summary.json",
        ),
    ]
    checks_df = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    checks_df.to_csv(checks_path, index=False)
    fail_count = int(checks_df["status"].eq("fail").sum())
    warn_count = int(checks_df["status"].eq("warn").sum())
    payload = {
        "status": "fail" if fail_count else ("warn" if warn_count else "ok"),
        "observed_utc": observed,
        "sql_rows": int(len(sql_df.index)),
        "sql_unique_seller_sku": int(len(sql_skus)),
        "o_view_rows": int(len(o_view.index)),
        "csv_mirror_rows": int(len(mirror_df.index)),
        "csv_mirror_authority_status": mirror_authority_status,
        "p014_loaded_source_mode": _text(p014.get("loaded_source_mode", "")),
        "fail_count": fail_count,
        "warn_count": warn_count,
        "checks_path": str(checks_path),
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guard Product DB SQL authority from stale CSV mirror drift.")
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
