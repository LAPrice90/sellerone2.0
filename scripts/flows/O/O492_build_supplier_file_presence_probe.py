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

from scripts.flows.O.O464_build_restock_supplier_batch_drafts import build_restock_supplier_batch_drafts
from scripts.flows.O.O494_build_supplier_file_source_index import (
    build_supplier_file_source_index,
    default_price_files_root as default_source_index_price_files_root,
    latest_source_for_supplier,
    read_supplier_file_source_index,
)
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


PROBE_CONTRACT = "restock_supplier_file_presence_probe_live"
HEALTH_CONTRACT = "restock_supplier_file_presence_probe_health"
ALLOWED_FILE_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xls"}
FOUND_STATE = "exact_supplier_sku_or_barcode_found"
NOT_FOUND_STATE = "not_found_in_latest_local_supplier_file"
NO_IDENTITY_STATE = "not_checked_no_supplier_identity"
NO_FILE_STATE = "not_checked_no_local_supplier_file"
READ_ERROR_STATE = "not_checked_supplier_file_read_error"
ALLOWED_MATCH_STATES = {
    FOUND_STATE,
    NOT_FOUND_STATE,
    NO_IDENTITY_STATE,
    NO_FILE_STATE,
    READ_ERROR_STATE,
}
ZERO_FLAG_COLUMNS = (
    "clears_supplier_proof",
    "purchase_approval_allowed",
    "po_creation_allowed",
    "purchase_commitment_allowed",
    "creates_live_action",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _compact_identity(value: object) -> str:
    text = _normalize_text(value)
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    return re.sub(r"[^A-Za-z0-9]+", "", text).upper()


def _safe_id(value: object) -> str:
    text = _compact_identity(value).lower()
    return text or "unknown"


def _mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_price_files_root() -> Path:
    return default_source_index_price_files_root()


def _supplier_folder(price_files_root: Path, supplier_name: str, supplier_code: str) -> Path | None:
    candidates = [supplier_name, supplier_code]
    for candidate in candidates:
        text = _normalize_text(candidate)
        if text and (price_files_root / text).exists():
            return price_files_root / text
    if not price_files_root.exists():
        return None
    wanted = {_compact_identity(value) for value in candidates if _compact_identity(value)}
    for folder in price_files_root.iterdir():
        if folder.is_dir() and _compact_identity(folder.name) in wanted:
            return folder
    return None


def _latest_supplier_file(supplier_folder: Path) -> Path | None:
    files = [
        path
        for child in ("inbox", "Processed", "processed", "")
        for path in ((supplier_folder / child) if child else supplier_folder).glob("*")
        if path.is_file()
        and not path.name.startswith("~$")
        and path.suffix.lower() in ALLOWED_FILE_SUFFIXES
    ]
    if not files:
        return None
    return sorted(files, key=lambda path: path.stat().st_mtime)[-1]


def _read_supplier_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str).fillna("")
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", dtype=str).fillna("")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding="latin1").fillna("")


def _identity_columns(df: pd.DataFrame, *, barcode: str, supplier_sku: str) -> dict[str, list[str]]:
    barcode_columns: list[str] = []
    supplier_sku_columns: list[str] = []
    for column in df.columns:
        name = _normalize_text(column).lower().replace("_", " ")
        if any(token in name for token in ("barcode", "bar code", "ean", "upc", "gtin")):
            barcode_columns.append(column)
        if (
            any(token in name for token in ("sku", "code", "item", "model", "part"))
            and not any(skip in name for skip in ("name", "description", "title"))
        ):
            supplier_sku_columns.append(column)
    return {
        "barcode": barcode_columns if _compact_identity(barcode) else [],
        "supplier_sku": supplier_sku_columns if _compact_identity(supplier_sku) else [],
    }


def _match_supplier_identity(
    df: pd.DataFrame,
    *,
    supplier_sku: str,
    barcode: str,
) -> tuple[int, str, str]:
    columns_by_identity = _identity_columns(df, barcode=barcode, supplier_sku=supplier_sku)
    searched_columns = sorted({column for columns in columns_by_identity.values() for column in columns})
    matched_by: list[str] = []
    match_mask = pd.Series(False, index=df.index)
    for identity_name, identity_value in (("supplier_sku", supplier_sku), ("barcode", barcode)):
        compact_value = _compact_identity(identity_value)
        if not compact_value:
            continue
        identity_mask = pd.Series(False, index=df.index)
        for column in columns_by_identity[identity_name]:
            values = df[column].map(_compact_identity)
            identity_mask = identity_mask | values.eq(compact_value)
        if bool(identity_mask.any()):
            matched_by.append(identity_name)
            match_mask = match_mask | identity_mask
    return int(match_mask.sum()), "|".join(matched_by), "|".join(searched_columns)


def _probe_row(
    probe_utc: str,
    batch_row: pd.Series,
    *,
    price_files_root: Path,
    source_index_df: pd.DataFrame,
) -> dict[str, str]:
    supplier_name = _normalize_text(batch_row.get("supplier_name", ""))
    supplier_code = _normalize_text(batch_row.get("supplier_code", ""))
    supplier_sku = _normalize_text(batch_row.get("supplier_sku", ""))
    barcode = _normalize_text(batch_row.get("barcode", ""))
    source_index_row = latest_source_for_supplier(source_index_df, supplier_name, supplier_code)
    supplier_folder = Path(source_index_row.get("local_supplier_folder_path", "")) if _normalize_text(source_index_row.get("local_supplier_folder_path", "")) else None
    latest_file = Path(source_index_row.get("local_latest_file_path", "")) if _normalize_text(source_index_row.get("local_latest_file_path", "")) else None
    if latest_file is not None and not latest_file.exists():
        latest_file = None
    if supplier_folder is None or not supplier_folder.exists():
        supplier_folder = _supplier_folder(price_files_root, supplier_name, supplier_code)
    latest_file_state = "local_supplier_folder_missing"
    identity_match_state = NO_FILE_STATE
    matched_by = ""
    matched_row_count = "0"
    searched_row_count = "0"
    searched_identity_columns = ""
    read_error = ""

    if not price_files_root.exists():
        latest_file_state = "local_price_files_root_missing"
        explanation = "No local supplier price-file root was found. Row stays not verified."
    elif supplier_folder is None:
        explanation = "No local supplier folder was found. Row stays not verified."
    else:
        latest_file = latest_file or _latest_supplier_file(supplier_folder)
        if latest_file is None:
            latest_file_state = "local_supplier_file_missing"
            explanation = "No local supplier price file was found. Row stays not verified."
        elif not _compact_identity(supplier_sku) and not _compact_identity(barcode):
            latest_file_state = "latest_local_supplier_file_available"
            identity_match_state = NO_IDENTITY_STATE
            explanation = "A latest local supplier file exists, but the O row has no supplier SKU or barcode to search."
        else:
            latest_file_state = "latest_local_supplier_file_checked"
            try:
                supplier_df = _read_supplier_file(latest_file)
                searched_row_count = str(len(supplier_df.index))
                matched_count, matched_by, searched_identity_columns = _match_supplier_identity(
                    supplier_df,
                    supplier_sku=supplier_sku,
                    barcode=barcode,
                )
                matched_row_count = str(matched_count)
                if matched_count > 0:
                    identity_match_state = FOUND_STATE
                    explanation = (
                        "Exact supplier SKU or barcode was found in the latest local supplier file. "
                        "This does not clear supplier proof by itself."
                    )
                else:
                    identity_match_state = NOT_FOUND_STATE
                    explanation = "Latest local supplier file was checked; exact supplier SKU or barcode was not found."
            except Exception as exc:  # pragma: no cover - exact parser failures vary by local file engine
                latest_file_state = "latest_local_supplier_file_read_error"
                identity_match_state = READ_ERROR_STATE
                read_error = f"{type(exc).__name__}: {_normalize_text(exc)}"
                explanation = "Latest local supplier file could not be read. Row stays not verified."

    row = {
        "probe_utc": probe_utc,
        "probe_id": f"o_supplier_file_probe_v1:{_safe_id(batch_row.get('row_id', ''))}",
        "batch_id": _normalize_text(batch_row.get("batch_id", "")),
        "session_id": _normalize_text(batch_row.get("session_id", "")),
        "row_id": _normalize_text(batch_row.get("row_id", "")),
        "supplier_name": supplier_name,
        "supplier_code": supplier_code,
        "seller_sku": _normalize_text(batch_row.get("seller_sku", "")),
        "asin": _normalize_text(batch_row.get("asin", "")),
        "title": _normalize_text(batch_row.get("title", "")),
        "supplier_sku": supplier_sku,
        "barcode": barcode,
        "draft_order_qty": _normalize_text(batch_row.get("draft_order_qty", "")),
        "price_files_root": str(price_files_root),
        "supplier_folder_path": str(supplier_folder or ""),
        "latest_supplier_file_path": str(latest_file or ""),
        "latest_supplier_file_name": latest_file.name if latest_file else "",
        "latest_supplier_file_mtime_utc": _mtime_utc(latest_file) if latest_file else "",
        "latest_supplier_file_state": latest_file_state,
        "identity_match_state": identity_match_state,
        "matched_by": matched_by,
        "matched_row_count": matched_row_count,
        "searched_row_count": searched_row_count,
        "searched_identity_columns": searched_identity_columns,
        "probe_explanation": explanation,
        "read_error": read_error,
        "source_index_handoff_state": _normalize_text(source_index_row.get("source_handoff_state", "")),
        "source_index_handoff_explanation": _normalize_text(source_index_row.get("handoff_explanation", "")),
    }
    for column in ZERO_FLAG_COLUMNS:
        row[column] = "0"
    return row


def _build_probe_rows(
    probe_utc: str,
    batch_lines_df: pd.DataFrame,
    *,
    price_files_root: Path,
    source_index_df: pd.DataFrame,
) -> pd.DataFrame:
    if batch_lines_df.empty:
        return pd.DataFrame()
    rows = [
        _probe_row(probe_utc, row, price_files_root=price_files_root, source_index_df=source_index_df)
        for _, row in batch_lines_df.iterrows()
        if _normalize_text(row.get("draft_order_qty", ""))
    ]
    return pd.DataFrame(rows)


def _build_health(
    probe_utc: str,
    probe_df: pd.DataFrame,
    batch_lines_df: pd.DataFrame,
    *,
    price_files_root: Path,
    source_paths: list[Path],
) -> pd.DataFrame:
    unsafe_rows: list[str] = []
    bad_claim_rows: list[str] = []
    unknown_state_rows: list[str] = []
    missing_explanation_rows: list[str] = []
    if not probe_df.empty:
        for _, row in probe_df.iterrows():
            label = _normalize_text(row.get("row_id", "")) or _normalize_text(row.get("seller_sku", "")) or "missing_row"
            if any(_normalize_text(row.get(column, "")) != "0" for column in ZERO_FLAG_COLUMNS):
                unsafe_rows.append(label)
            match_state = _normalize_text(row.get("identity_match_state", ""))
            if match_state not in ALLOWED_MATCH_STATES:
                unknown_state_rows.append(label)
            if match_state == FOUND_STATE and int(_normalize_text(row.get("matched_row_count", "0")) or "0") <= 0:
                bad_claim_rows.append(label)
            if _normalize_text(row.get("probe_explanation", "")) == "":
                missing_explanation_rows.append(label)
    file_found_rows = int(
        probe_df.get("latest_supplier_file_state", pd.Series(dtype=str))
        .map(_normalize_text)
        .isin({"latest_local_supplier_file_checked", "latest_local_supplier_file_available"})
        .sum()
    )
    found_rows = int(probe_df.get("identity_match_state", pd.Series(dtype=str)).map(_normalize_text).eq(FOUND_STATE).sum())
    not_found_rows = int(probe_df.get("identity_match_state", pd.Series(dtype=str)).map(_normalize_text).eq(NOT_FOUND_STATE).sum())
    not_checked_rows = int(len(probe_df.index) - found_rows - not_found_rows)
    source_path_text = ";".join(str(path) for path in source_paths)
    checks = [
        (
            "probe_contract_guard",
            not unknown_state_rows and not missing_explanation_rows,
            f"probe_rows={len(probe_df.index)};batch_line_rows={len(batch_lines_df.index)}",
            "Every supplier file probe row must have a known state and a plain-English explanation.",
        ),
        (
            "local_only_guard",
            not unsafe_rows,
            f"unsafe_rows={len(unsafe_rows)}",
            "Supplier file probes are read-only and must not clear proof, approve buying, create POs, or create live actions.",
        ),
        (
            "match_claim_guard",
            not bad_claim_rows,
            f"bad_claim_rows={len(bad_claim_rows)}",
            "A supplier file probe must not claim an exact match unless at least one identity row was found.",
        ),
        (
            "file_presence_summary",
            True,
            (
                f"file_found_rows={file_found_rows};found_rows={found_rows};"
                f"not_found_rows={not_found_rows};not_checked_rows={not_checked_rows}"
            ),
            f"Read-only latest-file check using price root {price_files_root}. Missing rows stay blocked, not failed.",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "check_utc": probe_utc,
                "check": check,
                "status": "ok" if passed else "fail",
                "value": value,
                "notes": notes,
                "source_path": source_path_text,
            }
            for check, passed, value, notes in checks
        ]
    )


def build_supplier_file_presence_probe(
    root: Path | None = None,
    *,
    probe_utc: str | None = None,
    write_outputs: bool = True,
    refresh_batches: bool = True,
    refresh_source_index: bool = True,
    price_files_root: Path | str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    paths = ensure_o_directories(root=root_path)
    observed = probe_utc or _utc_now_iso()
    if refresh_batches:
        build_restock_supplier_batch_drafts(
            root=root_path,
            batch_utc=observed,
            write_outputs=write_outputs,
            refresh_session=True,
        )
    batch_lines_df = read_o_contract_df(root_path, "restock_session_supplier_batch_lines_live")
    price_root = Path(price_files_root) if price_files_root is not None else default_price_files_root()
    if refresh_source_index:
        source_index_df, _source_index_health_df = build_supplier_file_source_index(
            root=root_path,
            index_utc=observed,
            write_outputs=write_outputs,
            price_files_root=price_root,
        )
    else:
        source_index_df = read_supplier_file_source_index(root_path)
    probe_df = _build_probe_rows(
        observed,
        batch_lines_df,
        price_files_root=price_root,
        source_index_df=source_index_df,
    )
    source_paths = [
        root_path / "out" / "systems" / "O" / "live" / "restock_session_supplier_batch_lines_live.csv",
        root_path / "out" / "systems" / "O" / "live" / "restock_supplier_file_source_index_live.csv",
        price_root,
    ]
    health_df = _build_health(
        observed,
        probe_df,
        batch_lines_df,
        price_files_root=price_root,
        source_paths=source_paths,
    )
    if write_outputs:
        probe_df = write_o_contract_df(root_path, PROBE_CONTRACT, probe_df)
        health_df = write_o_contract_df(root_path, HEALTH_CONTRACT, health_df)
        history_dir = paths.history_dir / f"supplier_file_presence_probe_v1_{observed.replace(':', '').replace('-', '')}"
        history_dir.mkdir(parents=True, exist_ok=True)
        probe_df.to_csv(history_dir / "restock_supplier_file_presence_probe_live.csv", index=False)
        health_df.to_csv(history_dir / "restock_supplier_file_presence_probe_health.csv", index=False)
    return probe_df, health_df


def main() -> int:
    probe_df, health_df = build_supplier_file_presence_probe()
    bad_health = health_df[health_df.get("status", pd.Series(dtype=str)).map(_normalize_text).ne("ok")]
    found_rows = int(probe_df.get("identity_match_state", pd.Series(dtype=str)).map(_normalize_text).eq(FOUND_STATE).sum())
    not_found_rows = int(probe_df.get("identity_match_state", pd.Series(dtype=str)).map(_normalize_text).eq(NOT_FOUND_STATE).sum())
    print(f"supplier_file_probe_rows={len(probe_df.index)}")
    print(f"supplier_file_probe_found_rows={found_rows}")
    print(f"supplier_file_probe_not_found_rows={not_found_rows}")
    print(f"health_status={'ok' if bad_health.empty else 'fail'}")
    return 0 if bad_health.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
