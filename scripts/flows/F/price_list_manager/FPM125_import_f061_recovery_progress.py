from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    F061_RECOVERY_PROGRESS_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
)


DEFAULT_LEGACY_ACTIVE_RUN = (
    "out/systems/F/inbox/suppliers/stocklist_supplier/active_run.csv"
)
DEFAULT_LEGACY_RUN_STATE = (
    "out/systems/F/inbox/suppliers/stocklist_supplier/run_state.csv"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_key(row: pd.Series) -> str:
    return "|".join(
        [
            normalize_text(row.get("supplier_sku", "")),
            normalize_text(row.get("barcode", "")),
        ]
    )


def _latest_batch_id(batches: pd.DataFrame, supplier_id: str) -> str:
    work = batches[batches["supplier_id"].map(normalize_text) == supplier_id].copy()
    if work.empty:
        return ""
    work["_updated"] = work["updated_at_utc"].map(normalize_text)
    work = work.sort_values("_updated", ascending=False, kind="stable")
    return normalize_text(work.iloc[0].get("batch_id", ""))


def _int_value(value: object) -> int:
    raw = normalize_text(value)
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _make_row_keys_unique(rows: pd.DataFrame, target_index: pd.Index) -> pd.DataFrame:
    out = rows.copy()
    seen: dict[str, int] = {}
    for row_index in target_index:
        row_key = normalize_text(out.at[row_index, "row_key"])
        if not row_key:
            continue
        seen[row_key] = seen.get(row_key, 0) + 1
        if seen[row_key] > 1:
            out.at[row_index, "row_key"] = f"{row_key}__dup{seen[row_key]}"
    return out


def import_f061_recovery_progress(
    root: Path | None = None,
    *,
    supplier_id: str = "entertainment_trading",
    batch_id: str = "",
    legacy_active_run_path: Path | None = None,
    legacy_run_state_path: Path | None = None,
    imported_at_utc: str | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    root_path = paths.root
    test_dir = paths.test_mode_dir
    imported_at = imported_at_utc or _utc_now_iso()

    active_path = legacy_active_run_path or root_path / DEFAULT_LEGACY_ACTIVE_RUN
    run_state_path = legacy_run_state_path or root_path / DEFAULT_LEGACY_RUN_STATE
    rows_path = test_dir / "batch_rows.csv"
    batches_path = test_dir / "price_list_batches.csv"
    progress_path = test_dir / "f061_recovery_progress.csv"
    health_path = test_dir / "health.csv"

    batch_rows = read_csv(rows_path, BATCH_ROW_COLUMNS)
    batches = read_csv(batches_path, PRICE_LIST_BATCH_COLUMNS)
    legacy_pending = pd.read_csv(active_path, dtype=str).fillna("") if active_path.exists() else pd.DataFrame()
    legacy_state = pd.read_csv(run_state_path, dtype=str).fillna("") if run_state_path.exists() else pd.DataFrame()

    target_batch_id = normalize_text(batch_id) or _latest_batch_id(batches, supplier_id)
    if not target_batch_id:
        raise FileNotFoundError(f"No manager batch found for supplier_id={supplier_id}")
    if legacy_pending.empty:
        raise FileNotFoundError(f"Legacy active-run progress file has no pending rows: {active_path}")

    target_mask = batch_rows["batch_id"].map(normalize_text) == target_batch_id
    target_rows = batch_rows[target_mask].copy()
    if target_rows.empty:
        raise FileNotFoundError(f"No manager batch rows found for batch_id={target_batch_id}")

    pending_counts = Counter(_row_key(row) for _, row in legacy_pending.iterrows())
    pending_source_rows = sum(pending_counts.values())
    unmatched_counts = pending_counts.copy()
    matched_rows = 0
    pending_held_rows = 0
    scan_now_rows = 0
    recovery_skipped_rows = 0
    held_rows = 0

    updated = batch_rows.copy()
    for row_index in target_rows.index:
        base = normalize_text(updated.at[row_index, "scan_eligibility"]).lower()
        key = _row_key(updated.loc[row_index])
        if unmatched_counts.get(key, 0) > 0:
            unmatched_counts[key] -= 1
            if base == "hold":
                pending_held_rows += 1
                held_rows += 1
                continue
            matched_rows += 1
            scan_now_rows += 1
            updated.at[row_index, "scan_eligibility"] = "scan_now"
            updated.at[row_index, "eligibility_reason"] = "f061_recovery_pending"
            continue
        if base == "hold":
            held_rows += 1
            continue
        recovery_skipped_rows += 1
        updated.at[row_index, "scan_eligibility"] = "skip_cooldown"
        updated.at[row_index, "eligibility_reason"] = "f061_recovery_not_pending"

    updated = _make_row_keys_unique(updated, target_rows.index)
    pending_unmatched_rows = sum(unmatched_counts.values())
    manager_valid_rows = int(
        (
            target_rows["scan_eligibility"].map(lambda value: normalize_text(value).lower())
            == "scan_now"
        ).sum()
    )

    batch_index = batches[batches["batch_id"].map(normalize_text) == target_batch_id].index
    if len(batch_index) > 0:
        idx = batch_index[-1]
        batches.at[idx, "eligible_row_count"] = str(scan_now_rows)
        batches.at[idx, "skipped_cooldown_row_count"] = str(recovery_skipped_rows)
        batches.at[idx, "batch_status"] = "recovery_resume_ready"
        batches.at[idx, "status_reason"] = "f061_recovery_progress_imported"
        batches.at[idx, "updated_at_utc"] = imported_at

    updated = write_csv(rows_path, updated, BATCH_ROW_COLUMNS)
    batches = write_csv(batches_path, batches, PRICE_LIST_BATCH_COLUMNS)

    legacy_run_id = ""
    legacy_total_rows = ""
    legacy_pending_rows = ""
    legacy_done_rows = ""
    legacy_failed_rows = ""
    if not legacy_state.empty:
        state = legacy_state.iloc[-1]
        legacy_run_id = normalize_text(state.get("run_id", ""))
        legacy_total_rows = normalize_text(state.get("total_rows", ""))
        legacy_pending_rows = normalize_text(state.get("pending_rows", ""))
        legacy_done_rows = normalize_text(state.get("done_rows", ""))
        legacy_failed_rows = normalize_text(state.get("failed_rows", ""))

    existing_progress = read_csv(progress_path, F061_RECOVERY_PROGRESS_COLUMNS)
    progress_row = pd.DataFrame(
        [
            {
                "imported_at_utc": imported_at,
                "supplier_id": supplier_id,
                "batch_id": target_batch_id,
                "legacy_run_id": legacy_run_id,
                "legacy_total_rows": legacy_total_rows,
                "legacy_pending_rows": legacy_pending_rows,
                "legacy_done_rows": legacy_done_rows,
                "legacy_failed_rows": legacy_failed_rows,
                "pending_source_rows": str(pending_source_rows),
                "pending_matched_rows": str(matched_rows),
                "pending_held_rows": str(pending_held_rows),
                "pending_unmatched_rows": str(pending_unmatched_rows),
                "manager_valid_rows": str(manager_valid_rows),
                "manager_scan_now_rows": str(scan_now_rows),
                "manager_recovery_skipped_rows": str(recovery_skipped_rows),
                "manager_held_rows": str(held_rows),
                "legacy_active_run_path": str(active_path),
                "legacy_run_state_path": str(run_state_path),
            }
        ]
    )
    progress = write_csv(
        progress_path,
        pd.concat([existing_progress, progress_row], ignore_index=True),
        F061_RECOVERY_PROGRESS_COLUMNS,
    )

    expected_pending = _int_value(legacy_pending_rows) or pending_source_rows
    accounted_pending = matched_rows + pending_held_rows
    health_status = "ok" if pending_unmatched_rows == 0 and accounted_pending == expected_pending else "fail"
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "f061_recovery_progress_import_reconciliation",
                "status": health_status,
                "value": str(scan_now_rows),
                "notes": (
                    f"batch_id={target_batch_id};legacy_run_id={legacy_run_id};"
                    f"legacy_pending_rows={legacy_pending_rows};pending_source_rows={pending_source_rows};"
                    f"pending_matched_rows={matched_rows};pending_held_rows={pending_held_rows};"
                    f"pending_unmatched_rows={pending_unmatched_rows};"
                    f"recovery_skipped_rows={recovery_skipped_rows};held_rows={held_rows}"
                ),
                "observed_utc": imported_at,
                "source_path": str(progress_path),
            }
        ]
    )
    health = write_csv(
        health_path,
        pd.concat([existing_health, health_row], ignore_index=True),
        MANAGER_HEALTH_COLUMNS,
    )

    summary = {
        "status": "success" if health_status == "ok" else "failed_reconciliation",
        "supplier_id": supplier_id,
        "batch_id": target_batch_id,
        "legacy_run_id": legacy_run_id,
        "legacy_total_rows": legacy_total_rows,
        "legacy_pending_rows": legacy_pending_rows,
        "legacy_done_rows": legacy_done_rows,
        "legacy_failed_rows": legacy_failed_rows,
        "pending_source_rows": pending_source_rows,
        "pending_matched_rows": matched_rows,
        "pending_held_rows": pending_held_rows,
        "pending_unmatched_rows": pending_unmatched_rows,
        "manager_valid_rows": manager_valid_rows,
        "manager_scan_now_rows": scan_now_rows,
        "manager_recovery_skipped_rows": recovery_skipped_rows,
        "manager_held_rows": held_rows,
        "progress_rows": int(len(progress.index)),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "progress_path": str(progress_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy F061 pending rows as manager recovery progress.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="entertainment_trading")
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--legacy-active-run-path", default="")
    parser.add_argument("--legacy-run-state-path", default="")
    parser.add_argument("--imported-at-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    active_path = Path(args.legacy_active_run_path) if args.legacy_active_run_path else None
    run_state_path = Path(args.legacy_run_state_path) if args.legacy_run_state_path else None
    import_f061_recovery_progress(
        root=root,
        supplier_id=args.supplier_id,
        batch_id=args.batch_id,
        legacy_active_run_path=active_path,
        legacy_run_state_path=run_state_path,
        imported_at_utc=args.imported_at_utc,
    )


if __name__ == "__main__":
    main()
