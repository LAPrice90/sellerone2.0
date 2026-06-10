from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import f_contract_columns, f_contract_table_name, finalize_f_contract_df
from scripts.flows.F._schemas import get_f_output_contract, get_f_output_contracts
from scripts.flows.F.price_list_manager.FPM129_storage_drift_guard import (
    _contract_csv_path,
    _max_timestamp_value,
    _read_csv_contract,
    _read_sql_table,
    _timestamp_compare,
    normalize_text,
    storage_config_for_root,
    utc_now_iso,
)
from scripts.core.storage import connect_store


APPROVED_SQL_TO_CSV_CONTRACTS = {
    "feeder_legacy_chart_daily_raw_live": (
        "run_id",
        "supplier_id",
        "supplier_sku",
        "candidate_id",
        "asin",
        "day",
        "chart_source",
    )
}

SUMMARY_COLUMNS = [
    "observed_utc",
    "contract_name",
    "status",
    "apply_flag",
    "csv_path",
    "sql_table",
    "csv_rows",
    "sql_rows",
    "row_delta_sql_minus_csv",
    "csv_freshness_utc",
    "sql_freshness_utc",
    "sql_newer_flag",
    "shared_exact_rows",
    "sql_only_exact_rows",
    "csv_only_exact_rows",
    "csv_duplicate_identity_keys",
    "sql_duplicate_identity_keys",
    "csv_supplier_count",
    "sql_supplier_count",
    "csv_run_count",
    "sql_run_count",
    "csv_candidate_count",
    "sql_candidate_count",
    "csv_day_min",
    "csv_day_max",
    "sql_day_min",
    "sql_day_max",
    "backup_dir",
    "output_path",
    "notes",
]

DIFF_COLUMNS = [
    "observed_utc",
    "contract_name",
    "side",
    "identity_key",
    "row_hash",
    "run_id",
    "supplier_id",
    "supplier_name",
    "supplier_sku",
    "candidate_id",
    "asin",
    "day",
    "chart_source",
]


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: normalize_text(row.get(column, "")) for column in columns})
    return path


def _read_sql_contract(root: Path, contract_name: str, sqlite_path: str | Path | None) -> tuple[pd.DataFrame, bool]:
    config = storage_config_for_root(root, sqlite_path=sqlite_path, require_sql_mode=False)
    if config is None:
        return pd.DataFrame(columns=f_contract_columns(contract_name)), False
    store = connect_store(config)
    try:
        df, exists = _read_sql_table(store, f_contract_table_name(contract_name))
    finally:
        store.close()
    if not exists:
        return pd.DataFrame(columns=f_contract_columns(contract_name)), False
    return finalize_f_contract_df(df, contract_name), True


def _row_hashes(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    ordered = list(columns)
    hashes: list[str] = []
    for row in df[ordered].fillna("").astype(str).itertuples(index=False, name=None):
        payload = "\x1f".join(row)
        hashes.append(hashlib.sha1(payload.encode("utf-8")).hexdigest())
    return hashes


def _identity_keys(df: pd.DataFrame, key_columns: Iterable[str]) -> list[str]:
    keys: list[str] = []
    for row in df[list(key_columns)].fillna("").astype(str).itertuples(index=False, name=None):
        keys.append("\x1f".join(row))
    return keys


def _multiset_diff(left: Counter[str], right: Counter[str]) -> Counter[str]:
    out: Counter[str] = Counter()
    for key, count in left.items():
        delta = count - right.get(key, 0)
        if delta > 0:
            out[key] = delta
    return out


def _coverage(df: pd.DataFrame) -> dict[str, str]:
    def unique_count(column: str) -> str:
        if column not in df.columns:
            return "0"
        return str(int(df[column].astype(str).str.strip().replace("", pd.NA).dropna().nunique()))

    day_min = ""
    day_max = ""
    if "day" in df.columns and not df.empty:
        days = df["day"].astype(str).str.strip()
        days = days[days.ne("")]
        if not days.empty:
            day_min = str(days.min())
            day_max = str(days.max())
    return {
        "supplier_count": unique_count("supplier_id"),
        "run_count": unique_count("run_id"),
        "candidate_count": unique_count("candidate_id"),
        "day_min": day_min,
        "day_max": day_max,
    }


def _sample_rows(
    *,
    observed_utc: str,
    contract_name: str,
    side: str,
    df: pd.DataFrame,
    row_hashes: list[str],
    selected_hashes: Counter[str],
    identity_keys: list[str],
    limit: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    remaining = Counter(selected_hashes)
    for index, row_hash in enumerate(row_hashes):
        if remaining.get(row_hash, 0) <= 0:
            continue
        source = df.iloc[index].to_dict()
        rows.append(
            {
                "observed_utc": observed_utc,
                "contract_name": contract_name,
                "side": side,
                "identity_key": identity_keys[index],
                "row_hash": row_hash,
                "run_id": source.get("run_id", ""),
                "supplier_id": source.get("supplier_id", ""),
                "supplier_name": source.get("supplier_name", ""),
                "supplier_sku": source.get("supplier_sku", ""),
                "candidate_id": source.get("candidate_id", ""),
                "asin": source.get("asin", ""),
                "day": source.get("day", ""),
                "chart_source": source.get("chart_source", ""),
            }
        )
        remaining[row_hash] -= 1
        if len(rows) >= limit:
            break
    return rows


def _backup_before_apply(
    *,
    root: Path,
    contract_name: str,
    csv_path: Path,
    observed_utc: str,
    summary_row: dict[str, object],
) -> Path:
    stamp = observed_utc.replace("-", "").replace(":", "").replace("Z", "Z")
    backup_dir = root / "out" / "backups" / f"f_sql_newer_csv_recovery_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if csv_path.exists():
        target = backup_dir / "csv" / csv_path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(csv_path, target)
    drift_report = root / "out" / "systems" / "F" / "price_list_manager" / "live" / "storage_drift_report.csv"
    if drift_report.exists():
        target = backup_dir / "reports" / "storage_drift_report.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(drift_report, target)
    manifest = {
        "observed_utc": observed_utc,
        "contract_name": contract_name,
        "csv_path": str(csv_path),
        "summary": summary_row,
        "rollback_note": "Restore the copied CSV over the live CSV to roll back this one-off recovery.",
    }
    (backup_dir / "backup_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return backup_dir


def run_sql_newer_recovery(
    *,
    root: Path,
    contract_name: str,
    observed_utc: str | None = None,
    sqlite_path: str | Path | None = None,
    apply: bool = False,
    sample_limit: int = 50,
) -> dict[str, object]:
    root_path = Path(root)
    observed = observed_utc or utc_now_iso()
    contract = normalize_text(contract_name)
    report_dir = root_path / "out" / "systems" / "F" / "price_list_manager" / "recovery"
    summary_path = report_dir / "sql_newer_recovery_summary.csv"
    diff_path = report_dir / "sql_newer_recovery_diff_sample.csv"

    if not contract:
        summary = {
            "observed_utc": observed,
            "contract_name": "",
            "status": "blocked_missing_contract",
            "apply_flag": "1" if apply else "0",
            "notes": "contract_name_required",
        }
        _write_csv(summary_path, SUMMARY_COLUMNS, [summary])
        _write_csv(diff_path, DIFF_COLUMNS, [])
        return {"status": "blocked_missing_contract", "summary_path": str(summary_path), "diff_path": str(diff_path), "summary_row": summary}

    if contract not in get_f_output_contracts() or contract not in APPROVED_SQL_TO_CSV_CONTRACTS:
        summary = {
            "observed_utc": observed,
            "contract_name": contract,
            "status": "blocked_contract_not_approved",
            "apply_flag": "1" if apply else "0",
            "notes": "contract_not_approved_for_sql_newer_csv_recovery",
        }
        _write_csv(summary_path, SUMMARY_COLUMNS, [summary])
        _write_csv(diff_path, DIFF_COLUMNS, [])
        return {"status": "blocked_contract_not_approved", "summary_path": str(summary_path), "diff_path": str(diff_path), "summary_row": summary}

    csv_df, csv_error = _read_csv_contract(root_path, contract)
    sql_df, sql_exists = _read_sql_contract(root_path, contract, sqlite_path)
    csv_path = _contract_csv_path(root_path, contract)
    sql_table = f_contract_table_name(contract)
    columns = f_contract_columns(contract)
    key_columns = APPROVED_SQL_TO_CSV_CONTRACTS[contract]
    csv_freshness = _max_timestamp_value(csv_df, csv_path)
    sql_freshness = _max_timestamp_value(sql_df, None)
    csv_hashes = _row_hashes(csv_df, columns)
    sql_hashes = _row_hashes(sql_df, columns)
    csv_counter = Counter(csv_hashes)
    sql_counter = Counter(sql_hashes)
    csv_only = _multiset_diff(csv_counter, sql_counter)
    sql_only = _multiset_diff(sql_counter, csv_counter)
    shared_rows = sum(min(count, sql_counter.get(key, 0)) for key, count in csv_counter.items())
    csv_identity_keys = _identity_keys(csv_df, key_columns)
    sql_identity_keys = _identity_keys(sql_df, key_columns)
    csv_identity_counts = Counter(csv_identity_keys)
    sql_identity_counts = Counter(sql_identity_keys)
    csv_duplicate_keys = sum(1 for count in csv_identity_counts.values() if count > 1)
    sql_duplicate_keys = sum(1 for count in sql_identity_counts.values() if count > 1)
    csv_cov = _coverage(csv_df)
    sql_cov = _coverage(sql_df)
    sql_newer = _timestamp_compare(sql_freshness, csv_freshness) > 0

    if csv_error:
        status = "blocked_csv_unreadable"
        notes = csv_error
    elif not sql_exists:
        status = "blocked_sql_table_missing"
        notes = "sql_table_missing"
    elif int(sum(csv_only.values())) > 0:
        status = "blocked_mixed_drift"
        notes = "csv_has_rows_not_present_in_sql"
    elif not sql_newer:
        status = "blocked_sql_not_newer"
        notes = "sql_timestamp_not_newer_than_csv"
    elif len(sql_df.index) <= len(csv_df.index):
        status = "blocked_sql_not_fuller"
        notes = "sql_row_count_not_greater_than_csv"
    elif int(sum(sql_only.values())) <= 0:
        status = "blocked_no_sql_only_rows"
        notes = "no_sql_only_rows_to_recover"
    else:
        status = "ready_sql_newer_recovery"
        notes = "sql_is_newer_fuller_and_contains_all_csv_exact_rows"

    summary_row: dict[str, object] = {
        "observed_utc": observed,
        "contract_name": contract,
        "status": status,
        "apply_flag": "1" if apply else "0",
        "csv_path": str(csv_path),
        "sql_table": sql_table,
        "csv_rows": str(len(csv_df.index)),
        "sql_rows": str(len(sql_df.index)),
        "row_delta_sql_minus_csv": str(len(sql_df.index) - len(csv_df.index)),
        "csv_freshness_utc": csv_freshness,
        "sql_freshness_utc": sql_freshness,
        "sql_newer_flag": "1" if sql_newer else "0",
        "shared_exact_rows": str(shared_rows),
        "sql_only_exact_rows": str(sum(sql_only.values())),
        "csv_only_exact_rows": str(sum(csv_only.values())),
        "csv_duplicate_identity_keys": str(csv_duplicate_keys),
        "sql_duplicate_identity_keys": str(sql_duplicate_keys),
        "csv_supplier_count": csv_cov["supplier_count"],
        "sql_supplier_count": sql_cov["supplier_count"],
        "csv_run_count": csv_cov["run_count"],
        "sql_run_count": sql_cov["run_count"],
        "csv_candidate_count": csv_cov["candidate_count"],
        "sql_candidate_count": sql_cov["candidate_count"],
        "csv_day_min": csv_cov["day_min"],
        "csv_day_max": csv_cov["day_max"],
        "sql_day_min": sql_cov["day_min"],
        "sql_day_max": sql_cov["day_max"],
        "backup_dir": "",
        "output_path": "",
        "notes": notes,
    }

    diff_rows = []
    diff_rows.extend(
        _sample_rows(
            observed_utc=observed,
            contract_name=contract,
            side="sql_only",
            df=sql_df,
            row_hashes=sql_hashes,
            selected_hashes=sql_only,
            identity_keys=sql_identity_keys,
            limit=sample_limit,
        )
    )
    remaining_sample = max(sample_limit - len(diff_rows), 0)
    diff_rows.extend(
        _sample_rows(
            observed_utc=observed,
            contract_name=contract,
            side="csv_only",
            df=csv_df,
            row_hashes=csv_hashes,
            selected_hashes=csv_only,
            identity_keys=csv_identity_keys,
            limit=remaining_sample,
        )
    )

    if apply:
        if status != "ready_sql_newer_recovery":
            summary_row["status"] = "blocked_apply_not_safe"
            summary_row["notes"] = f"{notes};dry_run_status={status}"
        else:
            backup_dir = _backup_before_apply(
                root=root_path,
                contract_name=contract,
                csv_path=csv_path,
                observed_utc=observed,
                summary_row=summary_row,
            )
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            finalized_sql = finalize_f_contract_df(sql_df, contract)
            finalized_sql.to_csv(csv_path, index=False)
            summary_row["status"] = "applied_sql_to_csv_recovery"
            summary_row["backup_dir"] = str(backup_dir)
            summary_row["output_path"] = str(csv_path)
            summary_row["notes"] = "csv_rebuilt_from_sql_contract_table"

    _write_csv(summary_path, SUMMARY_COLUMNS, [summary_row])
    _write_csv(diff_path, DIFF_COLUMNS, diff_rows)
    return {
        "status": summary_row["status"],
        "summary_path": str(summary_path),
        "diff_path": str(diff_path),
        "summary_row": summary_row,
        "diff_sample_rows": len(diff_rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recover one approved F CSV contract from newer SQL evidence.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--contract", required=True)
    parser.add_argument("--sqlite-path", default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sample-limit", type=int, default=50)
    args = parser.parse_args(argv)

    summary = run_sql_newer_recovery(
        root=Path(args.root),
        contract_name=args.contract,
        observed_utc=args.observed_utc,
        sqlite_path=args.sqlite_path,
        apply=bool(args.apply),
        sample_limit=max(args.sample_limit, 0),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    status = str(summary["status"])
    if status.startswith("blocked"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
