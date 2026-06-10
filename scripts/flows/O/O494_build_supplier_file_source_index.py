from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


INDEX_CONTRACT = "restock_supplier_file_source_index_live"
HEALTH_CONTRACT = "restock_supplier_file_source_index_health"
READABLE_PRICE_FILE_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xls"}
ZERO_FLAG_COLUMNS = (
    "clears_supplier_proof",
    "imports_supplier_file",
    "updates_f_status",
    "creates_live_action",
)
ALLOWED_HANDOFF_STATES = {
    "local_file_available_no_f_status",
    "local_file_newer_than_f_status",
    "f_status_failed_local_file_available",
    "f_status_matches_local_file",
    "f_status_ready_but_local_file_missing",
    "no_local_supplier_file",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def supplier_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value).lower())


def default_price_files_root() -> Path:
    env_root = normalize_text(os.environ.get("SELLERONE_PRICE_FILES_ROOT", ""))
    if env_root:
        return Path(env_root)
    return Path.home() / "Desktop" / "SellerOne Price Files"


def _mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object) -> datetime | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _f_status_path(root: Path) -> Path:
    return root / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "source_acquisition_status.csv"


def _read_f_source_status(root: Path) -> pd.DataFrame:
    path = _f_status_path(root)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _latest_f_rows(source_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if source_df.empty:
        return {}
    work = source_df.copy()
    for col in ("supplier_id", "supplier_name", "checked_at_utc"):
        if col not in work.columns:
            work[col] = ""
    rows: dict[str, tuple[datetime, int, dict[str, str]]] = {}
    for idx, row in work.iterrows():
        raw = row.to_dict()
        keys = {supplier_key(raw.get("supplier_id", "")), supplier_key(raw.get("supplier_name", ""))}
        keys.discard("")
        checked = _parse_utc(raw.get("checked_at_utc", "")) or datetime.min.replace(tzinfo=timezone.utc)
        for key in keys:
            existing = rows.get(key)
            candidate = (checked, int(idx), {str(k): normalize_text(v) for k, v in raw.items()})
            if existing is None or (candidate[0], candidate[1]) > (existing[0], existing[1]):
                rows[key] = candidate
    return {key: row for key, (_checked, _idx, row) in rows.items()}


def _scan_latest_local_file(supplier_folder: Path) -> tuple[Path | None, int]:
    if not supplier_folder.exists() or not supplier_folder.is_dir():
        return None, 0
    files = [
        path
        for path in supplier_folder.rglob("*")
        if path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.lower() in READABLE_PRICE_FILE_SUFFIXES
    ]
    if not files:
        return None, 0
    return max(files, key=lambda path: path.stat().st_mtime), len(files)


def _local_supplier_folders(price_files_root: Path) -> dict[str, Path]:
    if not price_files_root.exists() or not price_files_root.is_dir():
        return {}
    return {
        supplier_key(path.name): path
        for path in price_files_root.iterdir()
        if path.is_dir() and supplier_key(path.name)
    }


def _path_exists(path_text: object) -> str:
    text = normalize_text(path_text)
    if not text:
        return "0"
    return "1" if Path(text).exists() else "0"


def _handoff_state(*, f_row: dict[str, str], latest_file: Path | None) -> tuple[str, str]:
    f_status = normalize_text(f_row.get("status", "")).lower()
    f_state = normalize_text(f_row.get("source_state", "")).lower()
    f_latest_path = normalize_text(f_row.get("latest_source_path", ""))
    f_latest_mtime = _parse_utc(f_row.get("latest_source_mtime_utc", ""))
    local_mtime = _parse_utc(_mtime_utc(latest_file)) if latest_file else None

    if latest_file is None:
        if f_latest_path and _path_exists(f_latest_path) == "1":
            return (
                "f_status_ready_but_local_file_missing",
                "F has a source path, but O did not find a matching readable local supplier file folder.",
            )
        return "no_local_supplier_file", "No readable local supplier price file was found for this supplier."

    if not f_row:
        return "local_file_available_no_f_status", "A readable local supplier file exists, but F has no matching source-status row."

    if f_status == "fail" or f_state in {"error", "fail"}:
        return "f_status_failed_local_file_available", "F source status is failed, but O found a readable local supplier file."

    if f_latest_mtime is None or (local_mtime is not None and local_mtime > f_latest_mtime):
        return "local_file_newer_than_f_status", "O found a newer local supplier file than the file recorded in F source status."

    return "f_status_matches_local_file", "F source status and O local file scan agree closely enough for presence probing."


def _build_index_rows(index_utc: str, *, root: Path, price_files_root: Path) -> pd.DataFrame:
    f_rows = _latest_f_rows(_read_f_source_status(root))
    folders = _local_supplier_folders(price_files_root)
    all_keys = sorted({*f_rows.keys(), *folders.keys()})
    rows: list[dict[str, str]] = []
    for key in all_keys:
        f_row = f_rows.get(key, {})
        supplier_name = normalize_text(f_row.get("supplier_name", "")) or (folders.get(key).name if folders.get(key) else key)
        supplier_id = normalize_text(f_row.get("supplier_id", "")) or key
        folder = folders.get(key)
        latest_file, file_count = _scan_latest_local_file(folder) if folder is not None else (None, 0)
        handoff_state, explanation = _handoff_state(f_row=f_row, latest_file=latest_file)
        row = {
            "index_utc": index_utc,
            "supplier_key": key,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "f_source_status": normalize_text(f_row.get("status", "")),
            "f_source_state": normalize_text(f_row.get("source_state", "")),
            "f_source_location": normalize_text(f_row.get("source_location", "")),
            "f_latest_source_path": normalize_text(f_row.get("latest_source_path", "")),
            "f_latest_source_name": normalize_text(f_row.get("latest_source_name", "")),
            "f_latest_source_mtime_utc": normalize_text(f_row.get("latest_source_mtime_utc", "")),
            "f_latest_source_path_exists": _path_exists(f_row.get("latest_source_path", "")),
            "f_checked_at_utc": normalize_text(f_row.get("checked_at_utc", "")),
            "local_price_files_root": str(price_files_root),
            "local_supplier_folder_path": str(folder or ""),
            "local_latest_file_path": str(latest_file or ""),
            "local_latest_file_name": latest_file.name if latest_file else "",
            "local_latest_file_mtime_utc": _mtime_utc(latest_file) if latest_file else "",
            "local_file_count": str(file_count),
            "source_handoff_state": handoff_state,
            "handoff_explanation": explanation,
            "can_be_used_for_presence_probe": "1" if latest_file else "0",
            "f_notes": normalize_text(f_row.get("notes", "")),
            "local_search_scope": "supplier_folder_recursive_readable_price_files",
        }
        for column in ZERO_FLAG_COLUMNS:
            row[column] = "0"
        rows.append(row)
    return pd.DataFrame(rows)


def latest_source_for_supplier(index_df: pd.DataFrame, supplier_name: str, supplier_code: str = "") -> dict[str, str]:
    if index_df.empty:
        return {}
    keys = {supplier_key(supplier_name), supplier_key(supplier_code)}
    keys.discard("")
    if not keys:
        return {}
    work = index_df.copy()
    for col in ("supplier_key", "supplier_name", "supplier_id", "local_latest_file_mtime_utc"):
        if col not in work.columns:
            work[col] = ""
    matches = work[
        work.apply(
            lambda row: bool(
                {
                    supplier_key(row.get("supplier_key", "")),
                    supplier_key(row.get("supplier_name", "")),
                    supplier_key(row.get("supplier_id", "")),
                }
                & keys
            ),
            axis=1,
        )
    ].copy()
    if matches.empty:
        return {}
    matches["_sort_mtime"] = matches["local_latest_file_mtime_utc"].map(lambda value: _parse_utc(value) or datetime.min.replace(tzinfo=timezone.utc))
    row = matches.sort_values("_sort_mtime").iloc[-1].drop(labels=["_sort_mtime"], errors="ignore")
    return {str(k): normalize_text(v) for k, v in row.to_dict().items()}


def _build_health(index_utc: str, index_df: pd.DataFrame, *, root: Path, price_files_root: Path) -> pd.DataFrame:
    unknown_state_rows: list[str] = []
    unsafe_rows: list[str] = []
    missing_explanation_rows: list[str] = []
    for _, row in index_df.iterrows():
        label = normalize_text(row.get("supplier_key", "")) or normalize_text(row.get("supplier_name", "")) or "unknown_supplier"
        if normalize_text(row.get("source_handoff_state", "")) not in ALLOWED_HANDOFF_STATES:
            unknown_state_rows.append(label)
        if normalize_text(row.get("handoff_explanation", "")) == "":
            missing_explanation_rows.append(label)
        if any(normalize_text(row.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
            unsafe_rows.append(label)
    local_file_rows = int(index_df.get("local_latest_file_path", pd.Series(dtype=str)).map(normalize_text).ne("").sum())
    f_failed_local_available_rows = int(
        index_df.get("source_handoff_state", pd.Series(dtype=str))
        .map(normalize_text)
        .eq("f_status_failed_local_file_available")
        .sum()
    )
    local_newer_rows = int(
        index_df.get("source_handoff_state", pd.Series(dtype=str))
        .map(normalize_text)
        .eq("local_file_newer_than_f_status")
        .sum()
    )
    source_path_text = ";".join(
        [
            str(_f_status_path(root)),
            str(price_files_root),
        ]
    )
    checks = [
        (
            "source_index_contract_guard",
            not unknown_state_rows and not missing_explanation_rows,
            f"index_rows={len(index_df.index)};unknown_state_rows={len(unknown_state_rows)};missing_explanation_rows={len(missing_explanation_rows)}",
            "Every O supplier-file source-index row must have a known state and plain-English explanation.",
        ),
        (
            "local_only_guard",
            not unsafe_rows,
            f"unsafe_rows={len(unsafe_rows)}",
            "Source index rows must not import files, rewrite F status, clear supplier proof, or create live actions.",
        ),
        (
            "local_folder_scan_summary",
            True,
            f"local_file_rows={local_file_rows};f_failed_local_available_rows={f_failed_local_available_rows};local_newer_rows={local_newer_rows}",
            "Missing or stale F source status is proof context only; it does not fail O when a local file can be checked safely.",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "check_utc": index_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
            for check, passed, value, notes in checks
        ]
    )


def build_supplier_file_source_index(
    root: Path | None = None,
    *,
    index_utc: str | None = None,
    write_outputs: bool = True,
    price_files_root: Path | str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = index_utc or utc_now_iso()
    price_root = Path(price_files_root) if price_files_root is not None else default_price_files_root()
    index_df = _build_index_rows(observed, root=root_path, price_files_root=price_root)
    health_df = _build_health(observed, index_df, root=root_path, price_files_root=price_root)
    if write_outputs:
        index_df = write_o_contract_df(root_path, INDEX_CONTRACT, index_df)
        health_df = write_o_contract_df(root_path, HEALTH_CONTRACT, health_df)
        history_dir = paths.history_dir / f"supplier_file_source_index_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        index_df.to_csv(history_dir / "restock_supplier_file_source_index_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_supplier_file_source_index_health.csv", index=False)
    return index_df, health_df


def read_supplier_file_source_index(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    return read_o_contract_df(root_path, INDEX_CONTRACT)


def main() -> int:
    index_df, health_df = build_supplier_file_source_index()
    bad_health = health_df[health_df.get("status", pd.Series(dtype=str)).map(normalize_text).ne("ok")]
    local_file_rows = int(index_df.get("local_latest_file_path", pd.Series(dtype=str)).map(normalize_text).ne("").sum())
    f_failed_local_available_rows = int(
        index_df.get("source_handoff_state", pd.Series(dtype=str))
        .map(normalize_text)
        .eq("f_status_failed_local_file_available")
        .sum()
    )
    print(f"supplier_file_source_index_rows={len(index_df.index)}")
    print(f"supplier_file_source_index_local_file_rows={local_file_rows}")
    print(f"supplier_file_source_index_f_failed_local_available_rows={f_failed_local_available_rows}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
