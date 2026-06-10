from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_RESCAN_RECOVERY_PREVIEW_COLUMNS,
    F061_RESCAN_RECOVERY_SUMMARY_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
)


PREVIEW_FILENAME = "f061_rescan_recovery_preview.csv"
SUMMARY_FILENAME = "f061_rescan_recovery_summary.csv"
DEFAULT_MAX_ACTIVE_RESCAN_ATTEMPTS = 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_int(value: object, default: int = 0) -> int:
    raw = normalize_text(value).replace(",", "")
    if raw == "":
        return default
    try:
        return max(int(float(raw)), 0)
    except ValueError:
        return default


def _base_candidate_id(value: object) -> str:
    raw = normalize_text(value)
    if "__alt" in raw:
        return raw.split("__alt", 1)[0]
    return raw


def _latest_batch_by_supplier(batches: pd.DataFrame) -> dict[str, pd.Series]:
    if batches.empty:
        return {}
    work = batches.copy()
    work = work[work["batch_status"].map(normalize_text).str.lower() != "superseded"].copy()
    if work.empty:
        return {}
    work["_received_dt"] = pd.to_datetime(work["source_received_at_utc"], errors="coerce", utc=True)
    work["_updated_dt"] = pd.to_datetime(work["updated_at_utc"], errors="coerce", utc=True)
    work = work.sort_values(["supplier_id", "_received_dt", "_updated_dt", "batch_id"], kind="stable")
    latest: dict[str, pd.Series] = {}
    for supplier_id, group in work.groupby("supplier_id", sort=False):
        latest[normalize_text(supplier_id)] = group.iloc[-1]
    return latest


def _parked_rescan_rows(screening: pd.DataFrame) -> pd.DataFrame:
    if screening.empty:
        return pd.DataFrame(columns=screening.columns)
    fail_code = screening["fail_code"].map(normalize_text).str.upper() if "fail_code" in screening.columns else pd.Series(dtype=str)
    pf = screening["pf"].map(normalize_text).str.upper() if "pf" in screening.columns else pd.Series(dtype=str)
    timeout = screening["timeout_until_utc"].map(normalize_text) if "timeout_until_utc" in screening.columns else pd.Series(dtype=str)
    return screening[((fail_code == "RESCAN") | (pf == "RESCAN")) & (timeout != "")].copy()


def _candidate_active_count(active: pd.DataFrame, supplier_id: str, candidate_base: str, barcode: str) -> int:
    if active.empty:
        return 0
    work = active[active["supplier_id"].map(normalize_text) == supplier_id].copy()
    if work.empty:
        return 0
    row_key = work["row_key"].map(normalize_text) if "row_key" in work.columns else pd.Series(dtype=str)
    active_barcode = work["barcode"].map(normalize_text) if "barcode" in work.columns else pd.Series(dtype=str)
    return int(((row_key == candidate_base) | ((active_barcode == barcode) & (barcode != ""))).sum())


def _candidate_active_row(active: pd.DataFrame, supplier_id: str, candidate_base: str, barcode: str) -> pd.Series | None:
    if active.empty:
        return None
    work = active[active["supplier_id"].map(normalize_text) == supplier_id].copy()
    if work.empty:
        return None
    row_key = work["row_key"].map(normalize_text) if "row_key" in work.columns else pd.Series(dtype=str)
    active_barcode = work["barcode"].map(normalize_text) if "barcode" in work.columns else pd.Series(dtype=str)
    matches = work[(row_key == candidate_base) | ((active_barcode == barcode) & (barcode != ""))].copy()
    if len(matches.index) != 1:
        return None
    return matches.iloc[0]


def _single_source_match(matches: pd.DataFrame, method: str) -> tuple[pd.Series | None, str, int]:
    count = int(len(matches.index))
    if count == 1:
        return matches.iloc[0], method, count
    if count > 1:
        return None, f"ambiguous_{method}", count
    return None, "", 0


def _norm_column(df: pd.DataFrame, column: str) -> pd.Series:
    normalized = f"_{column}_norm"
    if normalized in df.columns:
        return df[normalized]
    if column in df.columns:
        return df[column].map(normalize_text)
    return pd.Series(dtype=str)


def _source_match(
    *,
    current_batch_rows: pd.DataFrame,
    historical_batch_rows: pd.DataFrame,
    candidate_base: str,
    supplier_sku: str,
    barcode: str,
) -> tuple[pd.Series | None, str, int, str]:
    exact = current_batch_rows[_norm_column(current_batch_rows, "row_key") == candidate_base].copy()
    source, method, count = _single_source_match(exact, "current_row_key")
    if source is not None or method:
        return source, method, count, ""

    sku_barcode = current_batch_rows[
        (_norm_column(current_batch_rows, "supplier_sku") == supplier_sku)
        & (_norm_column(current_batch_rows, "barcode") == barcode)
    ].copy()
    source, method, count = _single_source_match(sku_barcode, "current_sku_barcode")
    if source is not None or method:
        return source, method, count, ""

    barcode_only = current_batch_rows[_norm_column(current_batch_rows, "barcode") == barcode].copy()
    source, method, count = _single_source_match(barcode_only, "current_barcode_only")
    if source is not None or method:
        return source, method, count, ""

    historical = historical_batch_rows[
        (_norm_column(historical_batch_rows, "row_key") == candidate_base)
        | ((_norm_column(historical_batch_rows, "barcode") == barcode) & (barcode != ""))
    ].copy()
    historical_count = int(len(historical.index))
    if historical_count:
        return None, "no_current_source_match_historical_exists", historical_count, "source_not_in_current_batch"
    return None, "no_source_match", 0, "source_row_missing"


def _looks_scan_ready(source_row: pd.Series | None) -> tuple[bool, str]:
    if source_row is None:
        return False, "source_row_missing"
    supplier_title = normalize_text(source_row.get("supplier_title", ""))
    unit_cost = normalize_text(source_row.get("unit_cost", ""))
    if not unit_cost:
        return False, "source_row_missing_unit_cost"
    try:
        if float(unit_cost.replace(",", "")) <= 0:
            return False, "source_row_nonpositive_unit_cost"
    except ValueError:
        return False, "source_row_invalid_unit_cost"
    if not supplier_title:
        return False, "source_row_missing_supplier_title"
    return True, ""


def build_rescan_recovery_preview(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    max_active_rescan_attempts: int = DEFAULT_MAX_ACTIVE_RESCAN_ATTEMPTS,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=Path(root) if root is not None else None)
    root_path = paths.root
    built_at = observed_utc or _utc_now_iso()
    max_attempts = max(int(max_active_rescan_attempts), 1)

    screening = read_f_contract_df(root_path, "f_screening_row_state_live")
    active = read_f_contract_df(root_path, "supplier_price_list_active_run")
    batches = read_csv(paths.test_mode_dir / "price_list_batches.csv", PRICE_LIST_BATCH_COLUMNS)
    batch_rows = read_csv(paths.test_mode_dir / "batch_rows.csv", BATCH_ROW_COLUMNS)
    for column in ("supplier_id", "batch_id", "row_key", "supplier_sku", "barcode"):
        batch_rows[f"_{column}_norm"] = batch_rows[column].map(normalize_text)
    latest_batches = _latest_batch_by_supplier(batches)
    current_rows_by_supplier: dict[str, pd.DataFrame] = {}
    historical_rows_by_supplier: dict[str, pd.DataFrame] = {}
    for supplier_id, group in batch_rows.groupby("_supplier_id_norm", sort=False):
        supplier_key = normalize_text(supplier_id)
        historical_rows_by_supplier[supplier_key] = group.copy()
        latest_batch = latest_batches.get(supplier_key)
        latest_batch_id = normalize_text(latest_batch.get("batch_id", "")) if latest_batch is not None else ""
        current_rows_by_supplier[supplier_key] = group[group["_batch_id_norm"] == latest_batch_id].copy()
    parked = _parked_rescan_rows(screening)

    preview_rows: list[dict[str, str]] = []
    for index, row in parked.reset_index(drop=True).iterrows():
        supplier_id = normalize_text(row.get("supplier_id", ""))
        supplier_name = normalize_text(row.get("supplier_name", ""))
        candidate_id = normalize_text(row.get("candidate_id", ""))
        candidate_base = _base_candidate_id(candidate_id)
        barcode = normalize_text(row.get("barcode", ""))
        supplier_sku = normalize_text(row.get("supplier_sku", ""))
        attempt_count = _as_int(row.get("attempt_count", "0"), default=0)
        latest_batch = latest_batches.get(supplier_id)
        latest_batch_id = normalize_text(latest_batch.get("batch_id", "")) if latest_batch is not None else ""
        current_batch_rows = current_rows_by_supplier.get(supplier_id, pd.DataFrame(columns=batch_rows.columns))
        historical_batch_rows = historical_rows_by_supplier.get(supplier_id, pd.DataFrame(columns=batch_rows.columns))
        active_count = _candidate_active_count(active, supplier_id, candidate_base, barcode)
        active_row = _candidate_active_row(active, supplier_id, candidate_base, barcode)
        source_row, match_method, match_count, source_block_reason = _source_match(
            current_batch_rows=current_batch_rows,
            historical_batch_rows=historical_batch_rows,
            candidate_base=candidate_base,
            supplier_sku=supplier_sku,
            barcode=barcode,
        )

        if active_count:
            proposed_action = "already_active"
            active_ready, active_ready_reason = _looks_scan_ready(active_row)
            source_ready, source_ready_reason = _looks_scan_ready(source_row)
            if active_ready and source_ready:
                block_reason = ""
            elif not active_ready:
                block_reason = f"already_active_{active_ready_reason or 'active_row_not_scan_ready'}"
            else:
                block_reason = f"already_active_{source_ready_reason or source_block_reason or 'source_row_not_scan_ready'}"
        elif attempt_count >= max_attempts:
            proposed_action = "mark_retry_exhausted"
            block_reason = ""
        else:
            source_ready, source_ready_reason = _looks_scan_ready(source_row)
            if source_ready:
                proposed_action = "requeue_from_current_source"
                block_reason = ""
            elif source_row is not None:
                proposed_action = "mark_source_blocked"
                block_reason = source_ready_reason or "source_row_not_scan_ready"
            else:
                proposed_action = "mark_source_blocked"
                block_reason = source_block_reason or match_method or "source_match_blocked"

        proposed_run_id = normalize_text(row.get("run_id", ""))
        proposed_source_seen = normalize_text(latest_batch.get("source_received_at_utc", "")) if latest_batch is not None else ""
        preview_rows.append(
            {
                "preview_id": f"rescan_preview_{index + 1:05d}",
                "built_at_utc": built_at,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "run_id": normalize_text(row.get("run_id", "")),
                "candidate_id": candidate_id,
                "candidate_base": candidate_base,
                "asin": normalize_text(row.get("asin", "")),
                "original_supplier_sku": supplier_sku,
                "original_barcode": barcode,
                "original_status_reason": normalize_text(row.get("status_reason", "")),
                "original_attempt_count": str(attempt_count),
                "original_timeout_until_utc": normalize_text(row.get("timeout_until_utc", "")),
                "latest_batch_id": latest_batch_id,
                "source_match_method": match_method,
                "source_match_count": str(match_count),
                "proposed_action": proposed_action,
                "eligible_apply_flag": "1" if proposed_action in {"requeue_from_current_source", "mark_retry_exhausted", "mark_source_blocked"} else "0",
                "block_reason": block_reason,
                "proposed_run_id": proposed_run_id,
                "proposed_row_key": normalize_text(source_row.get("row_key", "")) if source_row is not None else candidate_base,
                "proposed_supplier_sku": normalize_text(source_row.get("supplier_sku", "")) if source_row is not None else supplier_sku,
                "proposed_supplier_title": normalize_text(source_row.get("supplier_title", "")) if source_row is not None else normalize_text(row.get("supplier_title", "")),
                "proposed_barcode": normalize_text(source_row.get("barcode", "")) if source_row is not None else barcode,
                "proposed_unit_cost": normalize_text(source_row.get("unit_cost", "")) if source_row is not None else "",
                "proposed_currency": normalize_text(source_row.get("currency", "")) if source_row is not None else "",
                "proposed_vat_rate": normalize_text(source_row.get("vat_rate", "")) if source_row is not None else "",
                "proposed_source_seen_at_utc": proposed_source_seen,
            }
        )

    preview = pd.DataFrame(preview_rows, columns=F061_RESCAN_RECOVERY_PREVIEW_COLUMNS)
    preview_path = paths.test_mode_dir / PREVIEW_FILENAME
    write_csv(preview_path, preview, F061_RESCAN_RECOVERY_PREVIEW_COLUMNS)

    action_counts = preview["proposed_action"].value_counts().to_dict() if not preview.empty else {}
    summary = pd.DataFrame(
        [
            {
                "built_at_utc": built_at,
                "total_parked_rows": str(len(preview.index)),
                "requeue_rows": str(int(action_counts.get("requeue_from_current_source", 0))),
                "retry_exhausted_rows": str(int(action_counts.get("mark_retry_exhausted", 0))),
                "source_blocked_rows": str(int(action_counts.get("mark_source_blocked", 0))),
                "already_active_rows": str(int(action_counts.get("already_active", 0))),
                "blocked_rows": str(int((preview["eligible_apply_flag"] != "1").sum())) if not preview.empty else "0",
                "live_write_attempted": "0",
                "live_write_succeeded": "0",
                "preview_path": str(preview_path),
                "notes": "preview_only_no_queue_or_output_edit",
            }
        ],
        columns=F061_RESCAN_RECOVERY_SUMMARY_COLUMNS,
    )
    summary_path = paths.test_mode_dir / SUMMARY_FILENAME
    write_csv(summary_path, summary, F061_RESCAN_RECOVERY_SUMMARY_COLUMNS)

    return {
        "status": "success",
        "preview_rows": int(len(preview.index)),
        "requeue_rows": int(action_counts.get("requeue_from_current_source", 0)),
        "retry_exhausted_rows": int(action_counts.get("mark_retry_exhausted", 0)),
        "source_blocked_rows": int(action_counts.get("mark_source_blocked", 0)),
        "already_active_rows": int(action_counts.get("already_active", 0)),
        "blocked_rows": int((preview["eligible_apply_flag"] != "1").sum()) if not preview.empty else 0,
        "preview_path": str(preview_path),
        "summary_path": str(summary_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview recovery for parked F061 RESCAN timeout rows.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--max-active-rescan-attempts", type=int, default=DEFAULT_MAX_ACTIVE_RESCAN_ATTEMPTS)
    args = parser.parse_args()
    summary = build_rescan_recovery_preview(
        root=Path(args.root) if args.root else None,
        observed_utc=args.observed_utc,
        max_active_rescan_attempts=args.max_active_rescan_attempts,
    )
    for key in (
        "status",
        "preview_rows",
        "requeue_rows",
        "retry_exhausted_rows",
        "source_blocked_rows",
        "already_active_rows",
        "blocked_rows",
        "preview_path",
        "summary_path",
    ):
        print(f"{key}={summary[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
