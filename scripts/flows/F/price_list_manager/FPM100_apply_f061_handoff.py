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

from scripts.flows.F._contract_io import (
    f_contract_columns,
    read_f_contract_df,
    write_f_contract_df,
)
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F.price_list_manager.FPM070_stage_f061_handoff import (
    _f061_idle_status,
    source_shape_guard_reasons,
)
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    F061_HANDOFF_APPLY_PREVIEW_COLUMNS,
    F061_HANDOFF_BACKUP_MANIFEST_COLUMNS,
    F061_HANDOFF_PREVIEW_COLUMNS,
    F061_STAGED_ACTIVE_RUN_COLUMNS,
    F061_STAGED_RUN_STATE_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _price_list_int(value: object) -> int:
    raw = normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _latest_preview(preview: pd.DataFrame) -> pd.Series | None:
    if preview.empty:
        return None
    work = preview.copy()
    work["_built_at"] = work["built_at_utc"].map(normalize_text)
    work = work.sort_values("_built_at", ascending=False, kind="stable")
    return work.iloc[0] if not work.empty else None


def _validate_staged_files(
    *,
    preview_row: pd.Series,
    staged_active: pd.DataFrame,
    staged_run_state: pd.DataFrame,
) -> list[str]:
    reasons: list[str] = []
    supplier_id = normalize_text(preview_row.get("supplier_id", ""))
    batch_id = normalize_text(preview_row.get("batch_id", ""))
    run_id = normalize_text(preview_row.get("run_id", ""))
    staged_rows = _price_list_int(preview_row.get("staged_rows", ""))

    if not supplier_id:
        reasons.append("preview_missing_supplier_id")
    if not batch_id:
        reasons.append("preview_missing_batch_id")
    if not run_id:
        reasons.append("preview_missing_run_id")
    if staged_rows <= 0:
        reasons.append("preview_has_no_staged_rows")
    if normalize_text(preview_row.get("technical_ready_flag", "")) != "1":
        reasons.append("technical_ready_flag_not_1")
    if normalize_text(preview_row.get("approval_state", "")).lower() != "approved":
        reasons.append("approval_state_not_approved")
    if normalize_text(preview_row.get("live_apply_allowed", "")) != "1":
        reasons.append("live_apply_allowed_not_1")

    if len(staged_active.index) != staged_rows:
        reasons.append(f"staged_active_row_count_mismatch:expected={staged_rows};actual={len(staged_active.index)}")
    if staged_active.empty:
        reasons.append("staged_active_empty")
    elif "run_id" in staged_active.columns:
        run_ids = {normalize_text(value) for value in staged_active["run_id"].tolist()}
        if run_ids != {run_id}:
            reasons.append("staged_active_run_id_mismatch")
        statuses = {normalize_text(value).lower() for value in staged_active["scan_status"].tolist()}
        if statuses != {"pending"}:
            reasons.append("staged_active_not_all_pending")
        reasons.extend(source_shape_guard_reasons(staged_active, supplier_id=supplier_id))

    if len(staged_run_state.index) != 1:
        reasons.append(f"staged_run_state_row_count_mismatch:actual={len(staged_run_state.index)}")
    else:
        state = staged_run_state.iloc[0]
        if normalize_text(state.get("run_id", "")) != run_id:
            reasons.append("staged_run_state_run_id_mismatch")
        if normalize_text(state.get("supplier_id", "")) != supplier_id:
            reasons.append("staged_run_state_supplier_id_mismatch")
        if normalize_text(state.get("run_status", "")).lower() != "running":
            reasons.append("staged_run_state_not_running")
        if _price_list_int(state.get("total_rows", "")) != staged_rows:
            reasons.append("staged_run_state_total_rows_mismatch")
        if _price_list_int(state.get("pending_rows", "")) != staged_rows:
            reasons.append("staged_run_state_pending_rows_mismatch")

    return reasons


def _existing_run_progress_notes(*, root_path: Path, supplier_id: str, run_id: str) -> str:
    if not supplier_id or not run_id:
        return ""
    screening = read_f_contract_df(root_path, "f_screening_row_state_live")
    if screening.empty or "run_id" not in screening.columns or "supplier_id" not in screening.columns:
        return ""
    work = screening[
        (screening["supplier_id"].map(normalize_text) == supplier_id)
        & (screening["run_id"].map(normalize_text) == run_id)
    ].copy()
    if work.empty:
        return ""
    row_status = work["row_status"].map(lambda value: normalize_text(value).lower()) if "row_status" in work.columns else pd.Series(dtype=str)
    pf = work["pf"].map(lambda value: normalize_text(value).upper()) if "pf" in work.columns else pd.Series(dtype=str)
    processed = work[row_status.isin({"pass", "timeout"}) | pf.isin({"PASS", "FAIL", "RESCAN"})].copy()
    latest_updated = ""
    if "updated_at_utc" in work.columns:
        latest_updated = max([normalize_text(value) for value in work["updated_at_utc"].tolist()] or [""])
    return (
        f"run_reapply_blocked:screening_rows={len(work.index)};"
        f"processed_rows={len(processed.index)};latest_updated_at_utc={latest_updated}"
    )


def _backup_live_contracts(
    *,
    root_path: Path,
    test_dir: Path,
    built_at: str,
    apply_id: str,
) -> tuple[str, str, pd.DataFrame]:
    backup_id = f"backup_{apply_id}"
    backup_dir = test_dir / "f061_handoff_backups" / backup_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []

    for contract_name, filename in [
        ("supplier_price_list_active_run", "supplier_price_list_active_run.csv"),
        ("supplier_price_list_run_state", "supplier_price_list_run_state.csv"),
    ]:
        source_path = root_path / get_f_output_contract(contract_name).rel_path
        backup_path = backup_dir / filename
        current = read_f_contract_df(root_path, contract_name)
        write_csv(backup_path, current, f_contract_columns(contract_name))
        manifest_rows.append(
            {
                "backup_id": backup_id,
                "built_at_utc": built_at,
                "source_contract": contract_name,
                "source_path": str(source_path),
                "backup_path": str(backup_path),
                "row_count": str(len(current.index)),
                "notes": "pre_f061_handoff_apply_snapshot",
            }
        )

    manifest = pd.DataFrame(manifest_rows)
    backup_manifest_path = backup_dir / "manifest.csv"
    write_csv(backup_manifest_path, manifest, F061_HANDOFF_BACKUP_MANIFEST_COLUMNS)

    backup_log_path = test_dir / "f061_handoff_apply_backups.csv"
    existing = read_csv(backup_log_path, F061_HANDOFF_BACKUP_MANIFEST_COLUMNS)
    backup_log = pd.concat([existing, manifest], ignore_index=True)
    write_csv(backup_log_path, backup_log, F061_HANDOFF_BACKUP_MANIFEST_COLUMNS)
    return str(backup_dir), str(backup_manifest_path), manifest


def apply_f061_handoff(
    root: Path | None = None,
    *,
    built_at_utc: str | None = None,
    apply_live: bool = False,
    confirm_approved_handoff: bool = False,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    root_path = paths.root
    test_dir = paths.test_mode_dir
    built_at = built_at_utc or _utc_now_iso()
    apply_id = f"apply_{built_at.replace('-', '').replace(':', '')}"

    preview_df = read_csv(test_dir / "f061_handoff_preview.csv", F061_HANDOFF_PREVIEW_COLUMNS)
    staged_active = read_csv(test_dir / "f061_handoff_staged_active_run.csv", F061_STAGED_ACTIVE_RUN_COLUMNS)
    staged_run_state = read_csv(test_dir / "f061_handoff_staged_run_state.csv", F061_STAGED_RUN_STATE_COLUMNS)
    health_path = test_dir / "health.csv"
    preview_row = _latest_preview(preview_df)

    block_reasons: list[str] = []
    supplier_id = ""
    supplier_name = ""
    batch_id = ""
    run_id = ""
    staged_rows = 0
    if preview_row is None:
        block_reasons.append("no_f061_handoff_preview")
    else:
        supplier_id = normalize_text(preview_row.get("supplier_id", ""))
        supplier_name = normalize_text(preview_row.get("supplier_name", ""))
        batch_id = normalize_text(preview_row.get("batch_id", ""))
        run_id = normalize_text(preview_row.get("run_id", ""))
        staged_rows = _price_list_int(preview_row.get("staged_rows", ""))
        block_reasons.extend(
            _validate_staged_files(
                preview_row=preview_row,
                staged_active=staged_active,
                staged_run_state=staged_run_state,
            )
        )

    idle_status, idle_notes = _f061_idle_status(root_path)
    if idle_status != "idle":
        block_reasons.append(f"f061_not_idle:{idle_notes}")
    progress_notes = _existing_run_progress_notes(root_path=root_path, supplier_id=supplier_id, run_id=run_id)
    if progress_notes:
        block_reasons.append(progress_notes)
    if apply_live and not confirm_approved_handoff:
        block_reasons.append("confirm_approved_handoff_required")

    apply_ready = len(block_reasons) == 0
    backup_dir = ""
    backup_manifest_path = ""
    live_write_attempted = False
    live_write_succeeded = False

    if apply_live and apply_ready and confirm_approved_handoff:
        backup_dir, backup_manifest_path, _ = _backup_live_contracts(
            root_path=root_path,
            test_dir=test_dir,
            built_at=built_at,
            apply_id=apply_id,
        )
        live_write_attempted = True
        write_f_contract_df(root_path, "supplier_price_list_active_run", staged_active)
        write_f_contract_df(root_path, "supplier_price_list_run_state", staged_run_state)
        live_write_succeeded = True

    live_active_run_path = root_path / get_f_output_contract("supplier_price_list_active_run").rel_path
    live_run_state_path = root_path / get_f_output_contract("supplier_price_list_run_state").rel_path
    apply_preview_row = {
        "apply_id": apply_id,
        "built_at_utc": built_at,
        "mode": "apply_live" if apply_live else "preview_only",
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "batch_id": batch_id,
        "run_id": run_id,
        "staged_rows": str(staged_rows),
        "apply_ready_flag": "1" if apply_ready else "0",
        "live_write_attempted": "1" if live_write_attempted else "0",
        "live_write_succeeded": "1" if live_write_succeeded else "0",
        "block_reason": ";".join(block_reasons),
        "backup_dir": backup_dir,
        "backup_manifest_path": backup_manifest_path,
        "live_active_run_path": str(live_active_run_path),
        "live_run_state_path": str(live_run_state_path),
    }
    apply_preview_path = test_dir / "f061_handoff_apply_preview.csv"
    apply_preview = write_csv(apply_preview_path, pd.DataFrame([apply_preview_row]), F061_HANDOFF_APPLY_PREVIEW_COLUMNS)

    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_status = "ok"
    if apply_live and not live_write_succeeded:
        health_status = "fail"
    health_row = pd.DataFrame(
        [
            {
                "check": "f061_handoff_apply_guard",
                "status": health_status,
                "value": "1" if live_write_succeeded else "0",
                "notes": (
                    f"mode={apply_preview_row['mode']};apply_ready={apply_preview_row['apply_ready_flag']};"
                    f"live_write_attempted={apply_preview_row['live_write_attempted']};"
                    f"live_write_succeeded={apply_preview_row['live_write_succeeded']};"
                    f"block_reason={apply_preview_row['block_reason']}"
                ),
                "observed_utc": built_at,
                "source_path": str(apply_preview_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    summary = {
        "status": "applied" if live_write_succeeded else ("ready" if apply_ready else "blocked"),
        "apply_id": apply_id,
        "supplier_id": supplier_id,
        "batch_id": batch_id,
        "run_id": run_id,
        "staged_rows": staged_rows,
        "apply_ready_flag": apply_preview_row["apply_ready_flag"],
        "live_write_attempted": apply_preview_row["live_write_attempted"],
        "live_write_succeeded": apply_preview_row["live_write_succeeded"],
        "block_reason": apply_preview_row["block_reason"],
        "backup_dir": backup_dir,
        "backup_manifest_path": backup_manifest_path,
        "apply_preview_rows": int(len(apply_preview.index)),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded apply path for a staged F061 price-list handoff.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--built-at-utc", default=None)
    parser.add_argument("--apply-live", action="store_true")
    parser.add_argument("--confirm-approved-handoff", action="store_true")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    apply_f061_handoff(
        root=root,
        built_at_utc=args.built_at_utc,
        apply_live=bool(args.apply_live),
        confirm_approved_handoff=bool(args.confirm_approved_handoff),
    )


if __name__ == "__main__":
    main()
