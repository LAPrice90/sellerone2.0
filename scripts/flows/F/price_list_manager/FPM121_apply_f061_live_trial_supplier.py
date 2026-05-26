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

from scripts.flows.F._contract_io import f_contract_columns, read_f_contract_df, write_f_contract_df
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    F061_HANDOFF_BACKUP_MANIFEST_COLUMNS,
    F061_LIVE_TRIAL_SAMPLE_COLUMNS,
    F061_STAGED_ACTIVE_RUN_COLUMNS,
    F061_STAGED_RUN_STATE_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_stamp(value: str) -> str:
    return value.replace("-", "").replace(":", "")


def _price_list_int(value: object) -> int:
    raw = normalize_text(value)
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _no_f061_owner_process() -> bool:
    try:
        import subprocess

        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | Where-Object { "
            "$_.CommandLine -match 'F061_run_legacy_first_checks_local.py|start_f061_finish_price_list' "
            "-and $_.CommandLine -notmatch 'Get-CimInstance Win32_Process' "
            "} | Measure-Object | Select-Object -ExpandProperty Count",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return normalize_text(result.stdout) in {"0", ""}
    except Exception:
        return False


def _latest_sample(summary: pd.DataFrame, *, trial_id: str | None, supplier_id: str) -> pd.Series | None:
    work = summary[summary["supplier_id"].map(normalize_text) == supplier_id].copy()
    if trial_id:
        work = work[work["trial_id"].map(normalize_text) == trial_id].copy()
    if work.empty:
        return None
    work["_built"] = work["built_at_utc"].map(normalize_text)
    work = work.sort_values("_built", ascending=False, kind="stable")
    return work.iloc[0]


def _backup_live_contracts(*, root_path: Path, system_dir: Path, built_at: str, apply_id: str) -> tuple[str, str]:
    backup_dir = system_dir / "live_trial_backups" / f"trial_apply_{apply_id}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for contract_name, filename in [
        ("supplier_price_list_active_run", "supplier_price_list_active_run.csv"),
        ("supplier_price_list_run_state", "supplier_price_list_run_state.csv"),
    ]:
        source_path = root_path / get_f_output_contract(contract_name).rel_path
        backup_path = backup_dir / filename
        current = read_f_contract_df(root_path, contract_name)
        write_csv(backup_path, current, f_contract_columns(contract_name))
        rows.append(
            {
                "backup_id": f"trial_apply_{apply_id}",
                "built_at_utc": built_at,
                "source_contract": contract_name,
                "source_path": str(source_path),
                "backup_path": str(backup_path),
                "row_count": str(len(current.index)),
                "notes": "pre_f061_live_trial_apply_snapshot",
            }
        )
    manifest_path = backup_dir / "manifest.csv"
    write_csv(manifest_path, pd.DataFrame(rows), F061_HANDOFF_BACKUP_MANIFEST_COLUMNS)
    return str(backup_dir), str(manifest_path)


def apply_f061_live_trial_supplier(
    root: Path | None = None,
    *,
    supplier_id: str,
    trial_id: str | None = None,
    built_at_utc: str | None = None,
    apply_live: bool = False,
    confirm_live_trial: bool = False,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    root_path = paths.root
    test_dir = paths.test_mode_dir
    built_at = built_at_utc or _utc_now_iso()
    apply_id = f"{normalize_text(supplier_id)}_{_safe_stamp(built_at)}"

    summary = read_csv(test_dir / "f061_live_trial_samples.csv", F061_LIVE_TRIAL_SAMPLE_COLUMNS)
    sample = _latest_sample(summary, trial_id=trial_id, supplier_id=supplier_id)

    block_reasons: list[str] = []
    sample_active_path = Path("")
    sample_state_path = Path("")
    selected_rows = 0
    run_id = ""
    if sample is None:
        block_reasons.append("no_live_trial_sample_for_supplier")
    else:
        sample_active_path = Path(normalize_text(sample.get("sample_active_run_path", "")))
        sample_state_path = Path(normalize_text(sample.get("sample_run_state_path", "")))
        selected_rows = _price_list_int(sample.get("selected_rows", ""))

    active = read_csv(sample_active_path, F061_STAGED_ACTIVE_RUN_COLUMNS) if sample_active_path else pd.DataFrame()
    state = read_csv(sample_state_path, F061_STAGED_RUN_STATE_COLUMNS) if sample_state_path else pd.DataFrame()
    if selected_rows <= 0:
        block_reasons.append("sample_has_no_rows")
    if len(active.index) != selected_rows:
        block_reasons.append(f"sample_active_row_count_mismatch:expected={selected_rows};actual={len(active.index)}")
    if len(state.index) != 1:
        block_reasons.append(f"sample_state_row_count_mismatch:actual={len(state.index)}")
    if not active.empty:
        run_ids = {normalize_text(value) for value in active["run_id"].tolist()}
        if len(run_ids) != 1:
            block_reasons.append("sample_active_multiple_run_ids")
        else:
            run_id = next(iter(run_ids))
        if {normalize_text(value).lower() for value in active["scan_status"].tolist()} != {"pending"}:
            block_reasons.append("sample_active_not_all_pending")
        if {normalize_text(value) for value in active["supplier_id"].tolist()} != {supplier_id}:
            block_reasons.append("sample_active_supplier_mismatch")
    if not state.empty:
        state_row = state.iloc[0]
        if normalize_text(state_row.get("supplier_id", "")) != supplier_id:
            block_reasons.append("sample_state_supplier_mismatch")
        if _price_list_int(state_row.get("pending_rows", "")) != selected_rows:
            block_reasons.append("sample_state_pending_rows_mismatch")
        if run_id and normalize_text(state_row.get("run_id", "")) != run_id:
            block_reasons.append("sample_state_run_id_mismatch")
    if not _no_f061_owner_process():
        block_reasons.append("f061_owner_process_still_running")
    if apply_live and not confirm_live_trial:
        block_reasons.append("confirm_live_trial_required")

    apply_ready = not block_reasons
    backup_dir = ""
    backup_manifest_path = ""
    live_write_attempted = False
    live_write_succeeded = False
    if apply_live and confirm_live_trial and apply_ready:
        backup_dir, backup_manifest_path = _backup_live_contracts(
            root_path=root_path,
            system_dir=paths.system_dir,
            built_at=built_at,
            apply_id=apply_id,
        )
        live_write_attempted = True
        write_f_contract_df(root_path, "supplier_price_list_active_run", active)
        write_f_contract_df(root_path, "supplier_price_list_run_state", state)
        live_write_succeeded = True

    health_path = test_dir / "health.csv"
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_status = "ok" if (not apply_live or live_write_succeeded) and apply_ready else "fail"
    health_row = pd.DataFrame(
        [
            {
                "check": "f061_live_trial_apply_guard",
                "status": health_status,
                "value": "1" if live_write_succeeded else "0",
                "notes": (
                    f"supplier_id={supplier_id};trial_id={trial_id or ''};selected_rows={selected_rows};"
                    f"apply_ready={int(apply_ready)};live_write_attempted={int(live_write_attempted)};"
                    f"live_write_succeeded={int(live_write_succeeded)};block_reason={';'.join(block_reasons)}"
                ),
                "observed_utc": built_at,
                "source_path": str(sample_active_path),
            }
        ]
    )
    write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    result = {
        "status": "applied" if live_write_succeeded else ("ready" if apply_ready else "blocked"),
        "supplier_id": supplier_id,
        "trial_id": trial_id or (normalize_text(sample.get("trial_id", "")) if sample is not None else ""),
        "run_id": run_id,
        "selected_rows": selected_rows,
        "apply_ready_flag": "1" if apply_ready else "0",
        "live_write_attempted": "1" if live_write_attempted else "0",
        "live_write_succeeded": "1" if live_write_succeeded else "0",
        "block_reason": ";".join(block_reasons),
        "backup_dir": backup_dir,
        "backup_manifest_path": backup_manifest_path,
    }
    print(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply one prepared F061 live trial supplier sample to the live inbox.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", required=True)
    parser.add_argument("--trial-id", default=None)
    parser.add_argument("--built-at-utc", default=None)
    parser.add_argument("--apply-live", action="store_true")
    parser.add_argument("--confirm-live-trial", action="store_true")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    apply_f061_live_trial_supplier(
        root=root,
        supplier_id=args.supplier_id,
        trial_id=args.trial_id,
        built_at_utc=args.built_at_utc,
        apply_live=bool(args.apply_live),
        confirm_live_trial=bool(args.confirm_live_trial),
    )


if __name__ == "__main__":
    main()
