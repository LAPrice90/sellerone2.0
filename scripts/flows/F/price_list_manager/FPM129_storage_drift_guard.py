from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
from scripts.core.storage.pandas_bridge import quote_identifier, validate_identifier
from scripts.flows.F._contract_io import f_contract_columns, f_contract_table_name, finalize_f_contract_df
from scripts.flows.F._schemas import get_f_output_contract, get_f_output_contracts


DEFAULT_CRITICAL_CONTRACTS = [
    "supplier_price_list_active_run",
    "supplier_price_list_run_state",
    "f_scanner_speed_ledger_live",
    "f_screening_row_state_live",
    "feeder_legacy_chart_daily_raw_live",
    "feeder_legacy_first_checks_live",
    "feeder_legacy_scrape_evidence_live",
]

REPORT_COLUMNS = [
    "observed_utc",
    "contract_name",
    "csv_path",
    "sql_table",
    "csv_exists",
    "sql_exists_before",
    "csv_rows",
    "sql_rows_before",
    "row_delta_before",
    "csv_freshness_utc",
    "sql_freshness_utc_before",
    "csv_newer_flag",
    "status_before",
    "safe_to_apply",
    "action",
    "sql_exists_after",
    "sql_rows_after",
    "row_delta_after",
    "sql_freshness_utc_after",
    "status_after",
    "backup_dir",
    "notes",
]

STORAGE_DRIFT_BACKUP_MAX_DIRS_ENV = "FPM_STORAGE_DRIFT_BACKUP_MAX_DIRS"
STORAGE_DRIFT_BACKUP_MAX_TOTAL_GB_ENV = "FPM_STORAGE_DRIFT_BACKUP_MAX_TOTAL_GB"
DEFAULT_STORAGE_DRIFT_BACKUP_MAX_DIRS = 1
DEFAULT_STORAGE_DRIFT_BACKUP_MAX_TOTAL_GB = 5.0


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def report_path_for_root(root: Path) -> Path:
    return root / "out" / "systems" / "F" / "price_list_manager" / "live" / "storage_drift_report.csv"


def parse_contract_list(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_CRITICAL_CONTRACTS)
    contracts = [normalize_text(part) for part in raw.split(",") if normalize_text(part)]
    return contracts or list(DEFAULT_CRITICAL_CONTRACTS)


def storage_config_for_root(
    root: Path,
    *,
    sqlite_path: str | Path | None = None,
    require_sql_mode: bool = False,
) -> StorageConfig | None:
    mode_raw = os.environ.get("SELLERONE_STORAGE_MODE")
    mode = parse_storage_mode(mode_raw) if mode_raw else "csv"
    if require_sql_mode and mode not in {"sql_shadow", "sql_primary_csv_export"}:
        return None
    database_url = normalize_text(os.environ.get("SELLERONE_DATABASE_URL", ""))
    raw_path = Path(sqlite_path or os.environ.get("SELLERONE_SQLITE_PATH", "out/sql/sellerone_dev.sqlite3"))
    resolved_path = raw_path if raw_path.is_absolute() else root / raw_path
    return StorageConfig(mode=mode, database_url=database_url, sqlite_path=resolved_path)


def _iso_from_datetime(value: pd.Timestamp | datetime) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_mtime_utc(path: Path) -> str:
    try:
        return _iso_from_datetime(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))
    except Exception:
        return ""


def _max_timestamp_value(df: pd.DataFrame, fallback_path: Path | None = None) -> str:
    if df.empty:
        return _file_mtime_utc(fallback_path) if fallback_path is not None and fallback_path.exists() else ""
    candidates: list[pd.Timestamp] = []
    for column in df.columns:
        column_key = normalize_text(column).lower()
        if not (
            column_key.endswith("_utc")
            or column_key.endswith("_at_utc")
            or column_key in {"updated_at", "created_at", "observed_at"}
        ):
            continue
        parsed = pd.to_datetime(df[column], errors="coerce", utc=True)
        parsed = parsed.dropna()
        if not parsed.empty:
            candidates.append(parsed.max())
    if candidates:
        return _iso_from_datetime(max(candidates))
    return _file_mtime_utc(fallback_path) if fallback_path is not None and fallback_path.exists() else ""


def _timestamp_compare(left: str, right: str) -> int:
    if not left and not right:
        return 0
    if left and not right:
        return 1
    if right and not left:
        return -1
    try:
        left_dt = pd.to_datetime(left, errors="raise", utc=True)
        right_dt = pd.to_datetime(right, errors="raise", utc=True)
    except Exception:
        return (left > right) - (left < right)
    return (left_dt > right_dt) - (left_dt < right_dt)


def _contract_csv_path(root: Path, contract_name: str) -> Path:
    contract = get_f_output_contract(contract_name)
    return root / contract.rel_path


def _read_csv_contract(root: Path, contract_name: str) -> tuple[pd.DataFrame, str]:
    path = _contract_csv_path(root, contract_name)
    columns = f_contract_columns(contract_name)
    if not path.exists():
        return pd.DataFrame(columns=columns), "missing_csv"
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=columns)
    return finalize_f_contract_df(df, contract_name), ""


def _metadata_columns(store, table_name: str) -> list[str]:
    if not store.table_exists("storage_column_metadata"):
        return []
    table = validate_identifier(table_name)
    rows = store.query_all(
        f"""
        SELECT original_column_name
        FROM storage_column_metadata
        WHERE table_name = {store._param()}
        ORDER BY ordinal
        """,
        [table],
    )
    return [str(row["original_column_name"]) for row in rows]


def _read_sql_table(store, table_name: str) -> tuple[pd.DataFrame, bool]:
    table = validate_identifier(table_name)
    if not store.table_exists(table):
        return pd.DataFrame(), False
    df = pd.read_sql_query(f"SELECT * FROM {quote_identifier(table)}", store.connection).fillna("")
    original_columns = _metadata_columns(store, table)
    if original_columns and len(original_columns) == len(df.columns):
        df.columns = original_columns
    return df.astype(str), True


def _sqlite_files(config: StorageConfig) -> list[Path]:
    if config.database_url:
        return []
    path = config.sqlite_path
    return [path, Path(str(path) + "-wal"), Path(str(path) + "-shm")]


def _backup_targets(root: Path, config: StorageConfig, contracts: Iterable[str], observed_utc: str) -> str:
    stamp = observed_utc.replace("-", "").replace(":", "").replace("Z", "Z")
    backup_dir = root / "out" / "backups" / f"f_storage_drift_reconcile_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for source in _sqlite_files(config):
        if source.exists():
            shutil.copy2(source, backup_dir / source.name)
    for contract_name in contracts:
        csv_path = _contract_csv_path(root, contract_name)
        if csv_path.exists():
            target = backup_dir / "csv" / csv_path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(csv_path, target)
    return str(backup_dir)


def _storage_drift_backup_root(root: Path) -> Path:
    return root / "out" / "backups"


def _int_env(name: str, default: int, minimum: int) -> int:
    raw = normalize_text(os.environ.get(name, ""))
    if not raw:
        return default
    try:
        return max(int(float(raw)), minimum)
    except ValueError:
        return default


def _float_env(name: str, default: float, minimum: float) -> float:
    raw = normalize_text(os.environ.get(name, ""))
    if not raw:
        return default
    try:
        return max(float(raw), minimum)
    except ValueError:
        return default


def _dir_tree_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += int(child.stat().st_size)
        except OSError:
            continue
    return total


def _safe_remove_storage_backup(path: Path, backup_root: Path) -> bool:
    try:
        resolved_root = backup_root.resolve()
        resolved_path = path.resolve()
    except OSError:
        return False
    if resolved_path.parent != resolved_root:
        return False
    if not resolved_path.name.startswith("f_storage_drift_reconcile_"):
        return False
    try:
        shutil.rmtree(resolved_path)
        return True
    except OSError:
        return False


def _storage_drift_backup_retention(root: Path, *, apply_cleanup: bool) -> dict[str, object]:
    backup_root = _storage_drift_backup_root(root)
    max_dirs = _int_env(
        STORAGE_DRIFT_BACKUP_MAX_DIRS_ENV,
        DEFAULT_STORAGE_DRIFT_BACKUP_MAX_DIRS,
        1,
    )
    max_total_gb = _float_env(
        STORAGE_DRIFT_BACKUP_MAX_TOTAL_GB_ENV,
        DEFAULT_STORAGE_DRIFT_BACKUP_MAX_TOTAL_GB,
        0.1,
    )
    max_total_bytes = int(max_total_gb * 1024 * 1024 * 1024)
    if not backup_root.exists():
        return {
            "before_dirs": 0,
            "after_dirs": 0,
            "before_bytes": 0,
            "after_bytes": 0,
            "pruned_dirs": 0,
            "pruned_empty_dirs": 0,
            "prune_failures": 0,
            "max_dirs": max_dirs,
            "max_total_gb": max_total_gb,
            "cap_exceeded": False,
        }

    candidates = [p for p in backup_root.iterdir() if p.is_dir() and p.name.startswith("f_storage_drift_reconcile_")]
    infos: list[dict[str, object]] = []
    for path in candidates:
        size = _dir_tree_size_bytes(path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        infos.append({"path": path, "size": int(size), "mtime": float(mtime), "empty": size <= 0})

    before_bytes = sum(int(info["size"]) for info in infos)
    before_dirs = len(infos)
    pruned_dirs = 0
    pruned_empty_dirs = 0
    prune_failures = 0

    if apply_cleanup:
        for info in [item for item in infos if bool(item["empty"])]:
            if _safe_remove_storage_backup(Path(info["path"]), backup_root):
                pruned_dirs += 1
                pruned_empty_dirs += 1
            else:
                prune_failures += 1

        non_empty = sorted(
            [item for item in infos if not bool(item["empty"])],
            key=lambda item: float(item["mtime"]),
            reverse=True,
        )
        for info in non_empty[max_dirs:]:
            if _safe_remove_storage_backup(Path(info["path"]), backup_root):
                pruned_dirs += 1
            else:
                prune_failures += 1

    remaining = [p for p in backup_root.iterdir() if p.is_dir() and p.name.startswith("f_storage_drift_reconcile_")]
    after_bytes = sum(_dir_tree_size_bytes(path) for path in remaining)
    after_dirs = len(remaining)
    non_empty_after = sum(1 for path in remaining if _dir_tree_size_bytes(path) > 0)
    return {
        "before_dirs": before_dirs,
        "after_dirs": after_dirs,
        "before_bytes": int(before_bytes),
        "after_bytes": int(after_bytes),
        "non_empty_after": int(non_empty_after),
        "pruned_dirs": int(pruned_dirs),
        "pruned_empty_dirs": int(pruned_empty_dirs),
        "prune_failures": int(prune_failures),
        "max_dirs": int(max_dirs),
        "max_total_gb": float(max_total_gb),
        "cap_exceeded": bool(non_empty_after > max_dirs or after_bytes > max_total_bytes or prune_failures > 0),
    }


def _retention_block_rows(observed: str, retention: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "observed_utc": observed,
            "contract_name": "_storage_drift_backup_retention",
            "status_before": "backup_retention_exceeded",
            "status_after": "backup_retention_exceeded",
            "safe_to_apply": "0",
            "action": "blocked",
            "notes": (
                f"after_dirs={retention.get('after_dirs', 0)};"
                f"non_empty_after={retention.get('non_empty_after', 0)};"
                f"after_bytes={retention.get('after_bytes', 0)};"
                f"max_dirs={retention.get('max_dirs', 0)};"
                f"max_total_gb={retention.get('max_total_gb', 0)};"
                f"prune_failures={retention.get('prune_failures', 0)}"
            ),
        }
    ]


def _merge_retention_results(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    merged = dict(after)
    merged["before_dirs"] = before.get("before_dirs", after.get("before_dirs", 0))
    merged["before_bytes"] = before.get("before_bytes", after.get("before_bytes", 0))
    merged["pruned_dirs"] = int(before.get("pruned_dirs", 0) or 0) + int(after.get("pruned_dirs", 0) or 0)
    merged["pruned_empty_dirs"] = int(before.get("pruned_empty_dirs", 0) or 0) + int(after.get("pruned_empty_dirs", 0) or 0)
    merged["prune_failures"] = int(before.get("prune_failures", 0) or 0) + int(after.get("prune_failures", 0) or 0)
    merged["cap_exceeded"] = bool(before.get("cap_exceeded") or after.get("cap_exceeded"))
    return merged


def _status_for_contract(
    *,
    csv_exists: bool,
    sql_exists: bool,
    csv_rows: int,
    sql_rows: int,
    csv_freshness: str,
    sql_freshness: str,
    csv_error: str,
) -> tuple[str, bool, str]:
    if csv_error:
        return csv_error, False, "csv_contract_missing_or_unreadable"
    if not csv_exists:
        return "missing_csv", False, "csv_contract_missing"
    if not sql_exists:
        return "csv_newer_drift", csv_rows >= 0, "sql_table_missing"
    if csv_rows == sql_rows and (not sql_freshness or _timestamp_compare(sql_freshness, csv_freshness) >= 0):
        return "ok", False, "sql_aligned_or_newer"
    if _timestamp_compare(sql_freshness, csv_freshness) > 0:
        return "unsafe_sql_newer_drift", False, "sql_timestamp_newer_than_csv"
    return "csv_newer_drift", True, "csv_authority_assumed_for_f_runtime_contract"


def _summarize_rows(rows: list[dict[str, object]]) -> dict[str, int]:
    drift_rows = sum(1 for row in rows if normalize_text(row.get("status_before", "")) not in {"", "ok", "skipped"})
    reconciled_rows = sum(1 for row in rows if normalize_text(row.get("action", "")) == "reconciled_sql_from_csv")
    blocked_rows = sum(
        1
        for row in rows
        if normalize_text(row.get("action", "")) == "blocked"
        or normalize_text(row.get("status_after", "")).startswith("unsafe")
    )
    return {
        "drift_rows": int(drift_rows),
        "reconciled_rows": int(reconciled_rows),
        "blocked_rows": int(blocked_rows),
    }


def write_storage_drift_report(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    for column in REPORT_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[REPORT_COLUMNS]
    df.to_csv(path, index=False)
    return path


def run_storage_drift_check(
    *,
    root: Path,
    contracts: Iterable[str] | None = None,
    observed_utc: str | None = None,
    apply: bool = False,
    sqlite_path: str | Path | None = None,
    report_path: Path | None = None,
    require_sql_mode: bool = False,
    backup: bool = False,
) -> dict[str, object]:
    root_path = Path(root)
    observed = observed_utc or utc_now_iso()
    contract_names = [normalize_text(contract) for contract in (contracts or DEFAULT_CRITICAL_CONTRACTS) if normalize_text(contract)]
    known_contracts = get_f_output_contracts()
    unknown = [contract for contract in contract_names if contract not in known_contracts]
    target_report_path = report_path or report_path_for_root(root_path)
    if unknown:
        rows = [
            {
                "observed_utc": observed,
                "contract_name": contract,
                "status_before": "unknown_contract",
                "status_after": "unknown_contract",
                "safe_to_apply": "0",
                "action": "blocked",
                "notes": "contract_not_registered",
            }
            for contract in unknown
        ]
        write_storage_drift_report(target_report_path, rows)
        return {
            "status": "blocked_storage_drift",
            "checked_contracts": len(contract_names),
            "drift_rows": len(rows),
            "reconciled_rows": 0,
            "blocked_rows": len(rows),
            "report_path": str(target_report_path),
            "rows": rows,
        }

    config = storage_config_for_root(root_path, sqlite_path=sqlite_path, require_sql_mode=require_sql_mode)
    if config is None:
        rows = [
            {
                "observed_utc": observed,
                "contract_name": contract,
                "csv_path": str(_contract_csv_path(root_path, contract)),
                "sql_table": f_contract_table_name(contract),
                "status_before": "skipped",
                "status_after": "skipped",
                "safe_to_apply": "0",
                "action": "skipped",
                "notes": "storage_mode_not_sql_enabled",
            }
            for contract in contract_names
        ]
        write_storage_drift_report(target_report_path, rows)
        return {
            "status": "skipped",
            "checked_contracts": len(contract_names),
            "drift_rows": 0,
            "reconciled_rows": 0,
            "blocked_rows": 0,
            "report_path": str(target_report_path),
            "rows": rows,
        }

    retention = _storage_drift_backup_retention(root_path, apply_cleanup=bool(apply and backup))
    if retention.get("cap_exceeded"):
        rows = _retention_block_rows(observed, retention)
        write_storage_drift_report(target_report_path, rows)
        return {
            "status": "blocked_storage_drift",
            "checked_contracts": len(contract_names),
            "drift_rows": len(rows),
            "reconciled_rows": 0,
            "blocked_rows": len(rows),
            "report_path": str(target_report_path),
            "backup_dir": "",
            "backup_retention": retention,
            "rows": rows,
        }

    backup_dir = ""

    rows: list[dict[str, object]] = []
    store = connect_store(config)
    try:
        for contract_name in contract_names:
            csv_path = _contract_csv_path(root_path, contract_name)
            csv_df, csv_error = _read_csv_contract(root_path, contract_name)
            csv_exists = csv_path.exists() and not csv_error
            sql_table = f_contract_table_name(contract_name)
            sql_df_before, sql_exists_before = _read_sql_table(store, sql_table)
            csv_rows = int(len(csv_df.index))
            sql_rows_before = int(len(sql_df_before.index)) if sql_exists_before else 0
            csv_freshness = _max_timestamp_value(csv_df, csv_path)
            sql_freshness_before = _max_timestamp_value(sql_df_before, None)
            status_before, safe_to_apply, reason = _status_for_contract(
                csv_exists=csv_exists,
                sql_exists=sql_exists_before,
                csv_rows=csv_rows,
                sql_rows=sql_rows_before,
                csv_freshness=csv_freshness,
                sql_freshness=sql_freshness_before,
                csv_error=csv_error,
            )
            action = "none"
            sql_exists_after = sql_exists_before
            sql_rows_after = sql_rows_before
            sql_freshness_after = sql_freshness_before
            status_after = status_before
            notes = reason
            if apply and status_before != "ok":
                if safe_to_apply:
                    if backup and not backup_dir:
                        backup_dir = _backup_targets(root_path, config, contract_names, observed)
                        retention = _storage_drift_backup_retention(root_path, apply_cleanup=True)
                        if retention.get("cap_exceeded"):
                            status_after = "backup_retention_exceeded"
                            action = "blocked"
                            notes = (
                                "backup_retention_exceeded_before_reconcile;"
                                f"after_dirs={retention.get('after_dirs', 0)};"
                                f"non_empty_after={retention.get('non_empty_after', 0)};"
                                f"after_bytes={retention.get('after_bytes', 0)}"
                            )
                            rows.extend(_retention_block_rows(observed, retention))
                            break
                    replace_table_from_dataframe(store, sql_table, csv_df)
                    sql_df_after, sql_exists_after = _read_sql_table(store, sql_table)
                    sql_rows_after = int(len(sql_df_after.index)) if sql_exists_after else 0
                    sql_freshness_after = _max_timestamp_value(sql_df_after, None)
                    if sql_rows_after == csv_rows:
                        status_after = "ok"
                        action = "reconciled_sql_from_csv"
                        notes = "sql_replaced_from_csv_contract"
                    else:
                        status_after = "unsafe_after_reconcile"
                        action = "attempted_reconcile_failed"
                        notes = "sql_row_count_still_mismatched_after_reconcile"
                else:
                    action = "blocked"
            rows.append(
                {
                    "observed_utc": observed,
                    "contract_name": contract_name,
                    "csv_path": str(csv_path),
                    "sql_table": sql_table,
                    "csv_exists": "1" if csv_exists else "0",
                    "sql_exists_before": "1" if sql_exists_before else "0",
                    "csv_rows": str(csv_rows),
                    "sql_rows_before": str(sql_rows_before),
                    "row_delta_before": str(csv_rows - sql_rows_before),
                    "csv_freshness_utc": csv_freshness,
                    "sql_freshness_utc_before": sql_freshness_before,
                    "csv_newer_flag": "1" if _timestamp_compare(csv_freshness, sql_freshness_before) >= 0 else "0",
                    "status_before": status_before,
                    "safe_to_apply": "1" if safe_to_apply else "0",
                    "action": action,
                    "sql_exists_after": "1" if sql_exists_after else "0",
                    "sql_rows_after": str(sql_rows_after),
                    "row_delta_after": str(csv_rows - sql_rows_after),
                    "sql_freshness_utc_after": sql_freshness_after,
                    "status_after": status_after,
                    "backup_dir": backup_dir,
                    "notes": notes,
                }
            )
    finally:
        store.close()

    retention = _merge_retention_results(
        retention,
        _storage_drift_backup_retention(root_path, apply_cleanup=bool(apply and backup)),
    )
    write_storage_drift_report(target_report_path, rows)
    counts = _summarize_rows(rows)
    if counts["blocked_rows"] > 0:
        status = "blocked_storage_drift"
    elif counts["reconciled_rows"] > 0:
        status = "reconciled"
    elif counts["drift_rows"] > 0:
        status = "drift_found"
    else:
        status = "ok"
    return {
        "status": status,
        "checked_contracts": len(contract_names),
        **counts,
        "report_path": str(target_report_path),
        "backup_dir": backup_dir,
        "backup_retention": retention,
        "rows": rows,
    }
