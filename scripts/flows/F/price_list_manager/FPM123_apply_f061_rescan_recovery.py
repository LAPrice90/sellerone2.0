from __future__ import annotations

import argparse
import shutil
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

from scripts.flows.F._contract_io import f_contract_columns, read_f_contract_df, write_f_contract_df
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    F061_RESCAN_RECOVERY_APPLY_ROW_COLUMNS,
    F061_RESCAN_RECOVERY_APPLY_SUMMARY_COLUMNS,
    F061_RESCAN_RECOVERY_PREVIEW_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
)


PREVIEW_FILENAME = "f061_rescan_recovery_preview.csv"
APPLY_ROWS_FILENAME = "f061_rescan_recovery_apply_rows.csv"
APPLY_SUMMARY_FILENAME = "f061_rescan_recovery_apply_summary.csv"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_stamp(value: str) -> str:
    return normalize_text(value).replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")


def _as_int(value: object, default: int = 0) -> int:
    raw = normalize_text(value).replace(",", "")
    if raw == "":
        return default
    try:
        return max(int(float(raw)), 0)
    except ValueError:
        return default


def _backup_file(source: Path, backup_root: Path, root_path: Path) -> str:
    if not source.exists():
        return ""
    try:
        rel = source.relative_to(root_path)
    except ValueError:
        rel = Path(source.name)
    target = backup_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


def _make_backup(
    *,
    root_path: Path,
    test_dir: Path,
    apply_id: str,
    touched_suppliers: set[str],
) -> Path:
    backup_dir = test_dir / "f061_rescan_recovery_backups" / apply_id
    for rel in (
        Path("out/systems/F/inbox/supplier_price_list_active_run.csv"),
        Path("out/systems/F/inbox/supplier_price_list_run_state.csv"),
        Path("out/systems/F/live/f_screening_row_state_live.csv"),
        Path("out/systems/F/price_list_manager/test_mode/f061_rescan_recovery_preview.csv"),
        Path("out/systems/F/price_list_manager/test_mode/f061_rescan_recovery_summary.csv"),
    ):
        _backup_file(root_path / rel, backup_dir, root_path)
    for supplier_id in sorted(touched_suppliers):
        supplier_dir = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id
        _backup_file(supplier_dir / "active_run.csv", backup_dir, root_path)
        _backup_file(supplier_dir / "run_state.csv", backup_dir, root_path)
    return backup_dir


def _active_row_from_preview(row: pd.Series, *, applied_at: str) -> dict[str, str]:
    return {
        "run_id": normalize_text(row.get("proposed_run_id", "")),
        "supplier_id": normalize_text(row.get("supplier_id", "")),
        "supplier_name": normalize_text(row.get("supplier_name", "")) or normalize_text(row.get("supplier_id", "")),
        "row_key": normalize_text(row.get("proposed_row_key", "")),
        "supplier_sku": normalize_text(row.get("proposed_supplier_sku", "")),
        "barcode": normalize_text(row.get("proposed_barcode", "")),
        "supplier_title": normalize_text(row.get("proposed_supplier_title", "")),
        "unit_cost": normalize_text(row.get("proposed_unit_cost", "")),
        "currency": normalize_text(row.get("proposed_currency", "")) or "GBP",
        "vat_rate": normalize_text(row.get("proposed_vat_rate", "")) or "20",
        "scan_status": "pending",
        "scan_reason": "rescan_retry_required",
        "attempt_count": normalize_text(row.get("original_attempt_count", "")) or "0",
        "last_attempt_utc": "",
        "finished_utc": "",
        "source_seen_at_utc": normalize_text(row.get("proposed_source_seen_at_utc", "")) or applied_at,
        "completion_block_reason": "rescan_retry_pending",
        "backtrack_original_observed_utc": "",
        "backtrack_attempt_count": "",
    }


def _active_payload_block_reason(row: dict[str, str]) -> str:
    if normalize_text(row.get("supplier_title", "")) == "":
        return "active_row_missing_supplier_title"
    unit_cost = normalize_text(row.get("unit_cost", ""))
    if unit_cost == "":
        return "active_row_missing_unit_cost"
    try:
        if float(unit_cost.replace(",", "")) <= 0:
            return "active_row_nonpositive_unit_cost"
    except ValueError:
        return "active_row_invalid_unit_cost"
    return ""


def _active_key(row: pd.Series | dict[str, str]) -> tuple[str, str, str]:
    return (
        normalize_text(row.get("supplier_id", "")),
        normalize_text(row.get("row_key", "")),
        normalize_text(row.get("barcode", "")),
    )


def _screening_match_mask(screening: pd.DataFrame, row: pd.Series) -> pd.Series:
    supplier_id = normalize_text(row.get("supplier_id", ""))
    candidate_id = normalize_text(row.get("candidate_id", ""))
    barcode = normalize_text(row.get("original_barcode", ""))
    supplier = screening["supplier_id"].map(normalize_text) == supplier_id
    candidate = screening["candidate_id"].map(normalize_text) == candidate_id
    if candidate.any():
        return supplier & candidate
    return supplier & (screening["barcode"].map(normalize_text) == barcode)


def _update_screening_row(screening: pd.DataFrame, preview_row: pd.Series, *, applied_at: str) -> int:
    mask = _screening_match_mask(screening, preview_row)
    if not mask.any():
        return 0
    action = normalize_text(preview_row.get("proposed_action", ""))
    indexes = list(screening[mask].index)
    for idx in indexes:
        screening.at[idx, "observed_utc"] = applied_at
        screening.at[idx, "updated_at_utc"] = applied_at
        screening.at[idx, "timeout_until_utc"] = ""
        screening.at[idx, "pf"] = "RESCAN"
        screening.at[idx, "fail_code"] = "RESCAN"
        screening.at[idx, "last_stage"] = "retry"
        if action == "requeue_from_current_source":
            screening.at[idx, "run_id"] = normalize_text(preview_row.get("proposed_run_id", ""))
            screening.at[idx, "supplier_sku"] = normalize_text(preview_row.get("proposed_supplier_sku", ""))
            screening.at[idx, "supplier_title"] = normalize_text(preview_row.get("proposed_supplier_title", ""))
            screening.at[idx, "barcode"] = normalize_text(preview_row.get("proposed_barcode", ""))
            screening.at[idx, "candidate_id"] = normalize_text(preview_row.get("proposed_row_key", "")) or normalize_text(
                preview_row.get("candidate_id", "")
            )
            screening.at[idx, "row_status"] = "retry"
            screening.at[idx, "status_reason"] = "RESCAN|retry_pending"
            screening.at[idx, "source_seen_at_utc"] = normalize_text(preview_row.get("proposed_source_seen_at_utc", ""))
        elif action == "mark_retry_exhausted":
            screening.at[idx, "row_status"] = "timeout"
            screening.at[idx, "status_reason"] = "RESCAN|retry_exhausted"
        elif action == "mark_source_blocked":
            screening.at[idx, "row_status"] = "timeout"
            reason = normalize_text(preview_row.get("block_reason", "")) or "source_blocked"
            screening.at[idx, "status_reason"] = f"RESCAN|{reason}"
    return len(indexes)


def _latest_batch_by_supplier(batches: pd.DataFrame) -> dict[str, pd.Series]:
    if batches.empty:
        return {}
    work = batches.copy()
    work = work[work["batch_status"].map(normalize_text).str.lower() != "superseded"].copy()
    work["_received_dt"] = pd.to_datetime(work["source_received_at_utc"], errors="coerce", utc=True)
    work["_updated_dt"] = pd.to_datetime(work["updated_at_utc"], errors="coerce", utc=True)
    latest: dict[str, pd.Series] = {}
    for supplier_id, group in work.sort_values(["_received_dt", "_updated_dt", "batch_id"], kind="stable").groupby("supplier_id"):
        latest[normalize_text(supplier_id)] = group.iloc[-1]
    return latest


def _run_state_row(
    *,
    supplier_id: str,
    supplier_active: pd.DataFrame,
    previous: pd.Series | None,
    latest_batch: pd.Series | None,
    observed_utc: str,
) -> dict[str, str]:
    pending_rows = int(len(supplier_active.index))
    first_active = supplier_active.iloc[0] if pending_rows else None
    prev_total = _as_int(previous.get("total_rows", "0") if previous is not None else "0")
    prev_done = _as_int(previous.get("done_rows", "0") if previous is not None else "0")
    prev_failed = _as_int(previous.get("failed_rows", "0") if previous is not None else "0")
    total_rows = max(prev_total, prev_done + prev_failed + pending_rows)
    supplier_name = (
        normalize_text(first_active.get("supplier_name", ""))
        if first_active is not None
        else normalize_text(previous.get("supplier_name", "") if previous is not None else supplier_id)
    )
    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name or supplier_id,
        "run_id": normalize_text(first_active.get("run_id", "")) if first_active is not None else normalize_text(previous.get("run_id", "") if previous is not None else ""),
        "run_status": "running" if pending_rows else "completed",
        "source_url": normalize_text(previous.get("source_url", "") if previous is not None else ""),
        "source_file_path": normalize_text(latest_batch.get("source_file_path", "") if latest_batch is not None else ""),
        "source_seen_at_utc": normalize_text(
            latest_batch.get("source_received_at_utc", "") if latest_batch is not None else previous.get("source_seen_at_utc", "") if previous is not None else ""
        ),
        "normalized_utc": normalize_text(previous.get("normalized_utc", "") if previous is not None else ""),
        "total_rows": str(total_rows),
        "pending_rows": str(pending_rows),
        "done_rows": str(prev_done),
        "failed_rows": str(prev_failed),
        "held_rows": normalize_text(previous.get("held_rows", "0") if previous is not None else "0") or "0",
        "next_row_index": "1" if pending_rows else "0",
        "updated_at_utc": observed_utc,
        "completed_at_utc": "" if pending_rows else observed_utc,
    }


def apply_rescan_recovery_preview(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    require_preview_total: int | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=Path(root) if root is not None else None)
    root_path = paths.root
    applied_at = observed_utc or _utc_now_iso()
    apply_id = f"rescan_recovery_apply_{_safe_stamp(applied_at)}"
    preview_path = paths.test_mode_dir / PREVIEW_FILENAME
    preview = read_csv(preview_path, F061_RESCAN_RECOVERY_PREVIEW_COLUMNS)
    if require_preview_total is not None and int(len(preview.index)) != int(require_preview_total):
        raise RuntimeError(f"preview row count mismatch: expected {require_preview_total}, found {len(preview.index)}")
    if preview.empty:
        raise RuntimeError("rescan recovery preview is missing or empty")

    touched_suppliers = {normalize_text(value) for value in preview["supplier_id"].tolist() if normalize_text(value)}
    backup_dir = _make_backup(root_path=root_path, test_dir=paths.test_mode_dir, apply_id=apply_id, touched_suppliers=touched_suppliers)

    active = read_f_contract_df(root_path, "supplier_price_list_active_run")
    run_state = read_f_contract_df(root_path, "supplier_price_list_run_state")
    screening = read_f_contract_df(root_path, "f_screening_row_state_live")
    batches = read_csv(paths.test_mode_dir / "price_list_batches.csv", PRICE_LIST_BATCH_COLUMNS)
    latest_batches = _latest_batch_by_supplier(batches)

    active_rows = active.to_dict("records") if not active.empty else []
    active_keys = {_active_key(row) for row in active_rows}
    apply_rows: list[dict[str, str]] = []
    active_rows_added = 0
    screening_rows_updated = 0

    for _, preview_row in preview.iterrows():
        action = normalize_text(preview_row.get("proposed_action", ""))
        active_written = "0"
        apply_status = "applied"
        block_reason = normalize_text(preview_row.get("block_reason", ""))
        if action == "requeue_from_current_source":
            new_active = _active_row_from_preview(preview_row, applied_at=applied_at)
            payload_block_reason = _active_payload_block_reason(new_active)
            if payload_block_reason:
                apply_status = "blocked"
                block_reason = block_reason or payload_block_reason
            else:
                key = _active_key(new_active)
                if key in active_keys:
                    apply_status = "already_active"
                else:
                    active_rows.append(new_active)
                    active_keys.add(key)
                    active_rows_added += 1
                    active_written = "1"
        elif action not in {"mark_retry_exhausted", "mark_source_blocked", "already_active"}:
            apply_status = "blocked"
            block_reason = block_reason or "unsupported_preview_action"

        updated_count = 0 if apply_status == "blocked" else _update_screening_row(screening, preview_row, applied_at=applied_at)
        screening_rows_updated += updated_count
        apply_rows.append(
            {
                "apply_id": apply_id,
                "applied_at_utc": applied_at,
                "preview_id": normalize_text(preview_row.get("preview_id", "")),
                "supplier_id": normalize_text(preview_row.get("supplier_id", "")),
                "candidate_id": normalize_text(preview_row.get("candidate_id", "")),
                "proposed_action": action,
                "apply_status": apply_status,
                "active_row_written": active_written,
                "screening_row_updated": str(updated_count),
                "block_reason": block_reason,
                "backup_dir": str(backup_dir),
            }
        )

    active_out = pd.DataFrame(active_rows, columns=f_contract_columns("supplier_price_list_active_run"))
    if not active_out.empty:
        active_out["_queue_priority"] = active_out.apply(
            lambda row: "0" if normalize_text(row.get("scan_reason", "")) == "rescan_retry_required" else "1",
            axis=1,
        )
        active_out = active_out.sort_values(
            by=["_queue_priority", "last_attempt_utc", "supplier_id", "supplier_sku", "row_key"],
            ascending=[True, True, True, True, True],
            kind="stable",
        ).drop(columns=["_queue_priority"], errors="ignore")
    active_written = write_f_contract_df(root_path, "supplier_price_list_active_run", active_out)

    run_state_rows: list[dict[str, str]] = []
    run_state_by_supplier = {
        normalize_text(row.get("supplier_id", "")): row for _, row in run_state.iterrows()
    } if not run_state.empty else {}
    all_state_suppliers = set(run_state_by_supplier) | touched_suppliers
    for supplier_id in sorted(supplier for supplier in all_state_suppliers if supplier):
        supplier_active = active_written[active_written["supplier_id"].map(normalize_text) == supplier_id].copy()
        previous = run_state_by_supplier.get(supplier_id)
        latest_batch = latest_batches.get(supplier_id)
        if supplier_active.empty and previous is None:
            continue
        run_state_rows.append(
            _run_state_row(
                supplier_id=supplier_id,
                supplier_active=supplier_active,
                previous=previous,
                latest_batch=latest_batch,
                observed_utc=applied_at,
            )
        )
    run_state_out = pd.DataFrame(run_state_rows, columns=f_contract_columns("supplier_price_list_run_state"))
    run_state_written = write_f_contract_df(root_path, "supplier_price_list_run_state", run_state_out)
    screening_written = write_f_contract_df(root_path, "f_screening_row_state_live", screening)

    active_columns = f_contract_columns("supplier_price_list_active_run")
    run_state_columns = f_contract_columns("supplier_price_list_run_state")
    for supplier_id in sorted(touched_suppliers):
        supplier_dir = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id
        supplier_dir.mkdir(parents=True, exist_ok=True)
        supplier_active = active_written[active_written["supplier_id"].map(normalize_text) == supplier_id].copy()
        supplier_active.to_csv(supplier_dir / "active_run.csv", columns=active_columns, index=False)
        supplier_state = run_state_written[run_state_written["supplier_id"].map(normalize_text) == supplier_id].copy()
        supplier_state.to_csv(supplier_dir / "run_state.csv", columns=run_state_columns, index=False)

    apply_rows_df = pd.DataFrame(apply_rows, columns=F061_RESCAN_RECOVERY_APPLY_ROW_COLUMNS)
    apply_rows_path = paths.test_mode_dir / APPLY_ROWS_FILENAME
    write_csv(apply_rows_path, apply_rows_df, F061_RESCAN_RECOVERY_APPLY_ROW_COLUMNS)

    action_counts = preview["proposed_action"].value_counts().to_dict()
    blocked_apply_rows = int((apply_rows_df["apply_status"].map(normalize_text) == "blocked").sum()) if not apply_rows_df.empty else 0
    apply_summary = pd.DataFrame(
        [
            {
                "apply_id": apply_id,
                "applied_at_utc": applied_at,
                "preview_rows": str(len(preview.index)),
                "requeue_rows": str(int(action_counts.get("requeue_from_current_source", 0))),
                "retry_exhausted_rows": str(int(action_counts.get("mark_retry_exhausted", 0))),
                "source_blocked_rows": str(int(action_counts.get("mark_source_blocked", 0))),
                "active_rows_added": str(active_rows_added),
                "screening_rows_updated": str(screening_rows_updated),
                "live_write_attempted": "1",
                "live_write_succeeded": "0" if blocked_apply_rows else "1",
                "backup_dir": str(backup_dir),
                "apply_rows_path": str(apply_rows_path),
                "notes": "protected_rescan_recovery_applied_no_f061_run_no_worker_restart",
            }
        ],
        columns=F061_RESCAN_RECOVERY_APPLY_SUMMARY_COLUMNS,
    )
    apply_summary_path = paths.test_mode_dir / APPLY_SUMMARY_FILENAME
    write_csv(apply_summary_path, apply_summary, F061_RESCAN_RECOVERY_APPLY_SUMMARY_COLUMNS)

    return {
        "status": "success",
        "apply_id": apply_id,
        "preview_rows": int(len(preview.index)),
        "active_rows_added": active_rows_added,
        "screening_rows_updated": screening_rows_updated,
        "backup_dir": str(backup_dir),
        "apply_rows_path": str(apply_rows_path),
        "apply_summary_path": str(apply_summary_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply approved F061 RESCAN recovery preview.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--require-preview-total", type=int, default=None)
    args = parser.parse_args()
    summary = apply_rescan_recovery_preview(
        root=Path(args.root) if args.root else None,
        observed_utc=args.observed_utc,
        require_preview_total=args.require_preview_total,
    )
    for key in (
        "status",
        "apply_id",
        "preview_rows",
        "active_rows_added",
        "screening_rows_updated",
        "backup_dir",
        "apply_rows_path",
        "apply_summary_path",
    ):
        print(f"{key}={summary[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
