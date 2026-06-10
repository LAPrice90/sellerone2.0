from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._scanner_state import (
    AUTH_STATE_BBP_LOGIN_REQUIRED,
    AUTH_STATE_DASHBOARD_LOGIN_REQUIRED,
    AUTH_STATE_LOGGED_IN,
    AUTH_STATE_LOGIN_REQUIRED,
    AUTH_STATES_REQUIRING_VISIBLE,
    BROWSER_STATE_HIDDEN,
    BROWSER_STATE_VISIBLE,
    active_row_queue_priority,
    active_row_requires_visible_browser,
    auth_state_for_browser_visibility,
    auth_state_from_log_text,
    browser_state_for_auth_state,
    browser_visibility_value,
)
from scripts.flows.F.price_list_manager.FPM010_check_acquisition_sources import check_acquisition_sources
from scripts.flows.F.price_list_manager.FPM011_import_ready_sources import import_ready_sources
from scripts.flows.F.price_list_manager.FPM012_enrich_batch_rows_for_f061 import enrich_batch_rows_for_f061
from scripts.flows.F.price_list_manager.FPM013_download_ready_url_sources import download_ready_url_sources
from scripts.flows.F.price_list_manager.FPM014_fetch_api_sources import fetch_api_sources
from scripts.flows.F.price_list_manager.FPM016_fetch_gmail_email_sources import fetch_gmail_email_sources
from scripts.flows.F.price_list_manager.FPM040_build_next_action import build_next_action
from scripts.flows.F.price_list_manager.FPM050_build_next_action_report import build_next_action_report
from scripts.flows.F.price_list_manager.FPM060_build_status_dashboard import build_status_dashboard
from scripts.flows.F.price_list_manager.FPM070_stage_f061_handoff import (
    source_shape_guard_reasons,
    stage_f061_handoff,
)
from scripts.flows.F.price_list_manager.FPM090_set_f061_handoff_approval import set_f061_handoff_approval
from scripts.flows.F.price_list_manager.FPM100_apply_f061_handoff import apply_f061_handoff
from scripts.flows.F.price_list_manager.FPM126_update_memory_from_f061_results import update_memory_from_f061_results
from scripts.flows.F.price_list_manager.FPM150_build_completed_review_pack import build_completed_review_pack
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import (
    F061_HANDOFF_PREVIEW_COLUMNS,
    LIVE_CYCLE_EVENT_COLUMNS,
    LIVE_CYCLE_STATUS_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
)


ScannerFunc = Callable[..., dict[str, Any]]
LOGIN_MODE_REQUEST_NAME = "f061_login_mode.requested"
LOGIN_MODE_DEFAULT_HOLD_SECONDS = 900
DEFAULT_F061_BBP_USER_DATA_DIR = r"C:\Users\Luke\AppData\Local\Chrome_UC136"
DEFAULT_F061_BBP_PROFILE_DIR = "Profile 2"
LOGIN_MODE_INACTIVE_STATUSES = {"canceled", "cancelled", "completed", "consumed", "drained", "still_required"}
AUTO_VISIBLE_AUTH_ATTENTION_ENV = "FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION"
F061_CHILD_STALL_SECONDS_ENV = "FPM_F061_CHILD_STALL_SECONDS"


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


def _truthy_env(name: str) -> bool:
    return normalize_text(os.environ.get(name, "")).lower() in {"1", "true", "yes", "on"}


def _auto_visible_auth_attention_enabled() -> bool:
    raw = normalize_text(os.environ.get(AUTO_VISIBLE_AUTH_ATTENTION_ENV, "")).lower()
    if raw == "":
        return True
    return raw in {"1", "true", "yes", "on"}


def _pid_alive(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        if os.name == "nt":
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return bool(normalize_text(completed.stdout))
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _parse_lock_pid(line: str) -> int | None:
    for part in [p.strip() for p in normalize_text(line).split("|") if p.strip()]:
        if part.startswith("pid="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return None
    return None


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return normalize_text(path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
    except Exception:
        return ""


def _parse_key_value_control_text(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in text.replace("\r", "\n").replace("|", "\n").splitlines():
        clean = normalize_text(part)
        if not clean or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        parsed[normalize_text(key).lower()] = normalize_text(value)
    return parsed


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="ascii", newline="\n")
    os.replace(tmp, path)


def _archive_path(path: Path, archive_dir: Path) -> str:
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = archive_dir / f"{path.name}.{stamp}"
    index = 1
    while target.exists():
        index += 1
        target = archive_dir / f"{path.name}.{stamp}.{index}"
    shutil.move(str(path), str(target))
    return str(target)


def _acquire_lock(lock_path: Path, *, stale_archive_dir: Path, heartbeat_utc: str) -> tuple[bool, str]:
    if lock_path.exists():
        line = _read_first_line(lock_path)
        pid = _parse_lock_pid(line)
        if _pid_alive(pid):
            return False, f"active_owner_pid={pid}"
        archive = _archive_path(lock_path, stale_archive_dir)
        reason = f"stale_lock_archived={archive}"
    else:
        reason = "lock_acquired"
    _write_text(
        lock_path,
        f"pid={os.getpid()}|start={heartbeat_utc}|heartbeat={heartbeat_utc}|owner=FPM130_live_cycle\n",
    )
    return True, reason


def _refresh_lock(lock_path: Path, *, started_utc: str, heartbeat_utc: str) -> None:
    _write_text(
        lock_path,
        f"pid={os.getpid()}|start={started_utc}|heartbeat={heartbeat_utc}|owner=FPM130_live_cycle\n",
    )


def _release_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists() and _parse_lock_pid(_read_first_line(lock_path)) == os.getpid():
            lock_path.unlink()
    except Exception:
        pass


def _active_f061_state(root: Path) -> dict[str, object]:
    active = read_f_contract_df(root, "supplier_price_list_active_run")
    run_state = read_f_contract_df(root, "supplier_price_list_run_state")
    scan_status = active["scan_status"].map(lambda value: normalize_text(value).lower())
    runnable_statuses = {"login_backtrack_pending", "login_backtrack_running", "pending"}
    pending = active[scan_status.isin(runnable_statuses)].copy()
    if not pending.empty:
        pending["_queue_priority"] = pending.apply(lambda row: str(active_row_queue_priority(row.to_dict())), axis=1)
        pending = pending.sort_values(
            by=["_queue_priority", "last_attempt_utc", "supplier_sku", "row_key"],
            ascending=[True, True, True, True],
            kind="stable",
        ).drop(columns=["_queue_priority"], errors="ignore")
    supplier_id = ""
    run_id = ""
    if not pending.empty:
        supplier_id = normalize_text(pending.iloc[0].get("supplier_id", ""))
        run_id = normalize_text(pending.iloc[0].get("run_id", ""))
    elif not run_state.empty:
        running = run_state[
            (run_state["run_status"].map(lambda value: normalize_text(value).lower()) == "running")
            | (run_state["pending_rows"].map(_price_list_int) > 0)
        ].copy()
        if not running.empty:
            supplier_id = normalize_text(running.iloc[0].get("supplier_id", ""))
            run_id = normalize_text(running.iloc[0].get("run_id", ""))
    return {
        "supplier_id": supplier_id,
        "run_id": run_id,
        "pending_rows": int(len(pending.index)),
        "active_rows": int(len(active.index)),
    }


def _latest_unmerged_login_backtrack_rows(ledger: pd.DataFrame) -> list[dict[str, str]]:
    if ledger.empty:
        return []
    work = ledger.copy()
    for column in [
        "candidate_id",
        "supplier_id",
        "original_run_id",
        "merged_into_candidate_flag",
        "backtrack_status",
        "backtrack_attempt_number",
        "backtrack_observed_utc",
    ]:
        if column not in work.columns:
            work[column] = ""
    work = work[
        work["candidate_id"].map(normalize_text).ne("")
        & work["supplier_id"].map(normalize_text).ne("")
        & work["original_run_id"].map(normalize_text).ne("")
    ].copy()
    if work.empty:
        return []
    work["_sort_ts"] = pd.to_datetime(work["backtrack_observed_utc"].map(normalize_text), errors="coerce")
    work["_attempt"] = pd.to_numeric(work["backtrack_attempt_number"].map(normalize_text), errors="coerce").fillna(0)
    latest = (
        work.sort_values(["_sort_ts", "_attempt"], ascending=[True, True], kind="stable")
        .groupby(["supplier_id", "original_run_id", "candidate_id"], dropna=False)
        .tail(1)
    )
    unresolved_statuses = {"blocked_login", "missing_dashboard_yes_no", "dashboard_yes_no_unresolved"}
    latest = latest[
        latest["merged_into_candidate_flag"].map(normalize_text).ne("1")
        & latest["backtrack_status"].map(lambda value: normalize_text(value).lower()).isin(unresolved_statuses)
    ].copy()
    return [
        {str(key): normalize_text(value) for key, value in row.items() if not str(key).startswith("_")}
        for row in latest.to_dict(orient="records")
    ]


def _promote_completed_login_backtrack_rows(
    *,
    root: Path,
    live_dir: Path,
    observed_utc: str,
    cycle_run_id: str,
) -> dict[str, object]:
    login_request = _read_login_mode_request(live_dir)
    auth_confirmed = _saved_auth_state(live_dir) == AUTH_STATE_LOGGED_IN
    if not _login_mode_request_active(login_request) and not auth_confirmed:
        return {"status": "skipped", "promoted_rows": 0, "reason": "login_mode_inactive"}
    if not auth_confirmed:
        return {"status": "skipped", "promoted_rows": 0, "reason": "auth_not_confirmed"}

    active = read_f_contract_df(root, "supplier_price_list_active_run")
    run_state = read_f_contract_df(root, "supplier_price_list_run_state")
    ledger = read_f_contract_df(root, "f_login_backtrack_evidence_live")
    latest_rows = _latest_unmerged_login_backtrack_rows(ledger)
    if not latest_rows:
        return {"status": "none", "promoted_rows": 0, "reason": "no_unmerged_backtrack"}

    active_key_to_index: dict[str, int] = {}
    if not active.empty:
        for idx, row in active.iterrows():
            active_key_to_index[
                "|".join(
                    [
                        normalize_text(row.get("supplier_id", "")).lower(),
                        normalize_text(row.get("run_id", "")),
                        normalize_text(row.get("row_key", "")),
                    ]
                )
            ] = int(idx)

    promoted_rows: list[dict[str, str]] = []
    promoted_by_run: dict[tuple[str, str], dict[str, str]] = {}
    for row in latest_rows:
        supplier_id = normalize_text(row.get("supplier_id", ""))
        run_id = normalize_text(row.get("original_run_id", ""))
        candidate_id = normalize_text(row.get("candidate_id", ""))
        if not supplier_id or not run_id or not candidate_id:
            continue
        key = "|".join([supplier_id.lower(), run_id, candidate_id])
        status = normalize_text(row.get("backtrack_status", "")).lower()
        block_reason = (
            "dashboard_yes_no_backtrack_required"
            if "dashboard" in status or "missing_dashboard" in status
            else "bbp_login_required"
        )
        promoted_row = {
            "run_id": run_id,
            "supplier_id": supplier_id,
            "supplier_name": normalize_text(row.get("supplier_name", "")),
            "row_key": candidate_id,
            "supplier_sku": normalize_text(row.get("supplier_sku", "")),
            "barcode": normalize_text(row.get("barcode", "")),
            "supplier_title": "",
            "unit_cost": normalize_text(row.get("unit_cost", "")),
            "currency": "GBP",
            "vat_rate": "20",
            "scan_status": "login_backtrack_pending",
            "scan_reason": "login_backtrack_required",
            "attempt_count": "0",
            "last_attempt_utc": normalize_text(row.get("backtrack_observed_utc", "")),
            "finished_utc": "",
            "source_seen_at_utc": normalize_text(row.get("original_observed_utc", "")),
            "completion_block_reason": block_reason,
            "backtrack_original_observed_utc": normalize_text(row.get("original_observed_utc", "")),
            "backtrack_attempt_count": normalize_text(row.get("backtrack_attempt_number", "")),
        }
        if key in active_key_to_index:
            idx = active_key_to_index[key]
            for column, value in promoted_row.items():
                if column not in active.columns:
                    active[column] = ""
                if value or column in {
                    "scan_status",
                    "scan_reason",
                    "attempt_count",
                    "last_attempt_utc",
                    "finished_utc",
                    "completion_block_reason",
                    "backtrack_original_observed_utc",
                    "backtrack_attempt_count",
                }:
                    active.at[idx, column] = value
        promoted_rows.append(promoted_row)
        promoted_by_run[(supplier_id.lower(), run_id)] = row

    if not promoted_rows:
        return {"status": "none", "promoted_rows": 0, "reason": "already_active"}

    new_rows = [
        promoted
        for promoted in promoted_rows
        if "|".join(
            [
                normalize_text(promoted.get("supplier_id", "")).lower(),
                normalize_text(promoted.get("run_id", "")),
                normalize_text(promoted.get("row_key", "")),
            ]
        )
        not in active_key_to_index
    ]
    active_out = pd.concat([active, pd.DataFrame(new_rows)], ignore_index=True)
    active_out["_queue_priority"] = active_out.apply(lambda row: str(active_row_queue_priority(row.to_dict())), axis=1)
    active_out = active_out.sort_values(
        by=["_queue_priority", "last_attempt_utc", "supplier_id", "supplier_sku", "row_key"],
        ascending=[True, True, True, True, True],
        kind="stable",
    ).drop(columns=["_queue_priority"], errors="ignore")
    write_f_contract_df(root, "supplier_price_list_active_run", active_out)

    state_rows = run_state.copy()
    for (supplier_key, run_id), ledger_row in promoted_by_run.items():
        match = state_rows[
            (state_rows["supplier_id"].map(lambda value: normalize_text(value).lower()) == supplier_key)
            & (state_rows["run_id"].map(normalize_text) == run_id)
        ].copy()
        pending_count = sum(
            1
            for promoted in promoted_rows
            if normalize_text(promoted.get("supplier_id", "")).lower() == supplier_key
            and normalize_text(promoted.get("run_id", "")) == run_id
        )
        if match.empty:
            state_rows = pd.concat(
                [
                    state_rows,
                    pd.DataFrame(
                        [
                            {
                                "supplier_id": normalize_text(ledger_row.get("supplier_id", "")),
                                "supplier_name": normalize_text(ledger_row.get("supplier_name", "")),
                                "run_id": run_id,
                                "run_status": "running",
                                "source_url": "",
                                "source_file_path": "",
                                "source_seen_at_utc": normalize_text(ledger_row.get("original_observed_utc", "")),
                                "normalized_utc": "",
                                "total_rows": str(pending_count),
                                "pending_rows": str(pending_count),
                                "done_rows": "0",
                                "failed_rows": "0",
                                "held_rows": "0",
                                "next_row_index": "1",
                                "updated_at_utc": observed_utc,
                                "completed_at_utc": "",
                            }
                        ]
                    ),
                ],
                ignore_index=True,
            )
            continue
        idx = match.index[-1]
        state_rows.at[idx, "run_status"] = "running"
        state_rows.at[idx, "pending_rows"] = str(max(_price_list_int(state_rows.at[idx, "pending_rows"]), pending_count))
        state_rows.at[idx, "next_row_index"] = "1"
        state_rows.at[idx, "updated_at_utc"] = observed_utc
        state_rows.at[idx, "completed_at_utc"] = ""
    write_f_contract_df(root, "supplier_price_list_run_state", state_rows)

    by_supplier = sorted({normalize_text(row.get("supplier_id", "")) for row in promoted_rows if normalize_text(row.get("supplier_id", ""))})
    _append_event(
        live_dir=live_dir,
        event_utc=observed_utc,
        cycle_run_id=cycle_run_id,
        event_type="completed_backtrack_promoted",
        status="promoted",
        rows=len(promoted_rows),
        notes=f"suppliers={','.join(by_supplier)};source=f_login_backtrack_evidence_live",
    )
    return {"status": "promoted", "promoted_rows": len(promoted_rows), "suppliers": by_supplier}


def _latest_handoff_preview(test_dir: Path) -> pd.Series | None:
    preview = read_csv(test_dir / "f061_handoff_preview.csv", F061_HANDOFF_PREVIEW_COLUMNS)
    if preview.empty:
        return None
    return preview.iloc[-1]


def _write_status(
    *,
    live_dir: Path,
    observed_utc: str,
    run_id: str,
    state: str,
    active_supplier_id: str = "",
    active_f061_run_id: str = "",
    pending_rows: int = 0,
    last_action: str = "",
    last_action_status: str = "",
    chunk_rows: int = 0,
    drain_ready: bool = False,
    notes: str = "",
) -> None:
    row = {
        "observed_utc": observed_utc,
        "run_id": run_id,
        "owner_pid": str(os.getpid()),
        "state": state,
        "active_supplier_id": active_supplier_id,
        "active_f061_run_id": active_f061_run_id,
        "pending_rows": str(max(int(pending_rows), 0)),
        "last_action": last_action,
        "last_action_status": last_action_status,
        "chunk_rows": str(max(int(chunk_rows), 0)),
        "drain_ready": "1" if drain_ready else "0",
        "notes": notes,
    }
    write_csv(live_dir / "live_cycle_status.csv", pd.DataFrame([row]), LIVE_CYCLE_STATUS_COLUMNS)
    health_status = "ok"
    if state in {"blocked", "already_running"} or state.startswith("blocked"):
        health_status = "warn"
    if last_action_status == "failed":
        health_status = "fail"
    health_path = live_dir / "live_cycle_health.csv"
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "fpm_live_cycle_status",
                "status": health_status,
                "value": state,
                "notes": f"last_action={last_action};last_action_status={last_action_status};pending_rows={pending_rows};notes={notes}",
                "observed_utc": observed_utc,
                "source_path": str(live_dir / "live_cycle_status.csv"),
            }
        ]
    )
    write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)


def _append_event(
    *,
    live_dir: Path,
    event_utc: str,
    cycle_run_id: str,
    event_type: str,
    supplier_id: str = "",
    f061_run_id: str = "",
    status: str = "",
    rows: int = 0,
    notes: str = "",
) -> None:
    path = live_dir / "live_cycle_events.csv"
    existing = read_csv(path, LIVE_CYCLE_EVENT_COLUMNS)
    row = pd.DataFrame(
        [
            {
                "event_utc": event_utc,
                "cycle_run_id": cycle_run_id,
                "event_type": event_type,
                "supplier_id": supplier_id,
                "f061_run_id": f061_run_id,
                "status": status,
                "rows": str(max(int(rows), 0)),
                "notes": notes,
            }
        ]
    )
    write_csv(path, pd.concat([existing, row], ignore_index=True), LIVE_CYCLE_EVENT_COLUMNS)


def _pending_after_from_notes(notes: object) -> int | None:
    match = re.search(r"(?:^|[;|,\s])pending_after=(\d+)", normalize_text(notes))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _latest_scanner_pending_after(live_dir: Path, *, supplier_id: str, f061_run_id: str) -> int | None:
    if not supplier_id or not f061_run_id:
        return None
    events = read_csv(live_dir / "live_cycle_events.csv", LIVE_CYCLE_EVENT_COLUMNS)
    if events.empty:
        return None
    work = events[
        (events["event_type"].map(normalize_text) == "scanner_chunk")
        & (events["supplier_id"].map(normalize_text) == supplier_id)
        & (events["f061_run_id"].map(normalize_text) == f061_run_id)
    ].copy()
    if work.empty:
        return None
    for _, row in work.iloc[::-1].iterrows():
        pending_after = _pending_after_from_notes(row.get("notes", ""))
        if pending_after is not None:
            return pending_after
    return None


def _state_regression_guard(
    *,
    live_dir: Path,
    observed_utc: str,
    cycle_run_id: str,
    supplier_id: str,
    f061_run_id: str,
    pending_rows: int,
    chunk_rows: int,
) -> dict[str, object]:
    latest_pending = _latest_scanner_pending_after(live_dir, supplier_id=supplier_id, f061_run_id=f061_run_id)
    if latest_pending is None:
        return {"status": "ok"}
    allowed_increase = max(int(chunk_rows) * 4, 100)
    if int(pending_rows) <= latest_pending + allowed_increase:
        return {"status": "ok", "latest_pending_after": latest_pending, "allowed_increase": allowed_increase}
    notes = (
        f"pending_rows={int(pending_rows)};latest_scanner_pending_after={latest_pending};"
        f"allowed_increase={allowed_increase};run_id={f061_run_id}"
    )
    _write_status(
        live_dir=live_dir,
        observed_utc=observed_utc,
        run_id=cycle_run_id,
        state="blocked_state_regression",
        active_supplier_id=supplier_id,
        active_f061_run_id=f061_run_id,
        pending_rows=int(pending_rows),
        last_action="state_regression_guard",
        last_action_status="blocked",
        chunk_rows=chunk_rows,
        notes=notes,
    )
    _append_event(
        live_dir=live_dir,
        event_utc=observed_utc,
        cycle_run_id=cycle_run_id,
        event_type="state_regression_blocked",
        supplier_id=supplier_id,
        f061_run_id=f061_run_id,
        status="blocked",
        rows=int(pending_rows),
        notes=notes,
    )
    return {
        "status": "blocked_state_regression",
        "action": "state_regression_guard",
        "supplier_id": supplier_id,
        "pending_rows": int(pending_rows),
        "latest_pending_after": latest_pending,
        "allowed_increase": allowed_increase,
        "notes": notes,
    }


def _active_source_shape_guard(
    *,
    root: Path,
    live_dir: Path,
    observed_utc: str,
    cycle_run_id: str,
    supplier_id: str,
    f061_run_id: str,
    pending_rows: int,
    chunk_rows: int,
) -> dict[str, object]:
    active = read_f_contract_df(root, "supplier_price_list_active_run")
    if active.empty or "supplier_id" not in active.columns:
        return {"status": "ok"}
    scan_status = active["scan_status"].map(lambda value: normalize_text(value).lower())
    runnable_statuses = {"login_backtrack_pending", "login_backtrack_running", "pending"}
    work = active[
        (active["supplier_id"].map(normalize_text) == supplier_id)
        & scan_status.isin(runnable_statuses)
    ].copy()
    if work.empty:
        return {"status": "ok"}

    reasons = source_shape_guard_reasons(work, supplier_id=supplier_id)
    if not reasons:
        return {"status": "ok"}

    notes = ";".join(reasons)
    _record_login_mode_request_health(
        live_dir=live_dir,
        observed_utc=observed_utc,
        request=_read_login_mode_request(live_dir),
        child_starting=False,
        pending_rows=int(pending_rows),
    )
    _write_status(
        live_dir=live_dir,
        observed_utc=observed_utc,
        run_id=cycle_run_id,
        state="blocked_source_shape_guard",
        active_supplier_id=supplier_id,
        active_f061_run_id=f061_run_id,
        pending_rows=int(pending_rows),
        last_action="source_shape_guard",
        last_action_status="blocked",
        chunk_rows=chunk_rows,
        notes=notes,
    )
    _append_event(
        live_dir=live_dir,
        event_utc=observed_utc,
        cycle_run_id=cycle_run_id,
        event_type="source_shape_guard_blocked",
        supplier_id=supplier_id,
        f061_run_id=f061_run_id,
        status="blocked",
        rows=int(pending_rows),
        notes=notes,
    )
    return {
        "status": "blocked_source_shape_guard",
        "action": "source_shape_guard",
        "supplier_id": supplier_id,
        "pending_rows": int(pending_rows),
        "shape_reasons": reasons,
        "notes": notes,
    }


def _live_loop_sleep_seconds(status: object, sleep_seconds: float) -> float:
    normalized = normalize_text(status)
    if normalized.startswith("blocked") or normalized == "already_running":
        return max(float(sleep_seconds), 1.0)
    return max(float(sleep_seconds), 0.0)


def _login_mode_request_path(live_dir: Path) -> Path:
    return live_dir / LOGIN_MODE_REQUEST_NAME


def _read_login_mode_request(live_dir: Path) -> dict[str, str]:
    path = _login_mode_request_path(live_dir)
    if not path.exists():
        return {}
    try:
        request = _parse_key_value_control_text(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        request = {}
    request["request_path"] = str(path)
    request["request_exists"] = "1"
    return request


def _login_mode_request_active(request: dict[str, str]) -> bool:
    if normalize_text(request.get("request_exists", "")) != "1":
        return False
    status = normalize_text(request.get("status", "requested")).lower()
    return status not in LOGIN_MODE_INACTIVE_STATUSES


def _login_mode_hold_seconds(request: dict[str, str]) -> int:
    raw = normalize_text(request.get("hold_seconds", ""))
    try:
        return max(int(float(raw)), 1)
    except ValueError:
        return LOGIN_MODE_DEFAULT_HOLD_SECONDS


def _active_login_backtrack_rows(active: pd.DataFrame) -> pd.DataFrame:
    if active.empty:
        return active.copy()
    work = active.copy()
    for column in ["scan_status", "scan_reason", "completion_block_reason"]:
        if column not in work.columns:
            work[column] = ""
    status = work["scan_status"].map(lambda value: normalize_text(value).lower())
    reason = work["scan_reason"].map(lambda value: normalize_text(value).lower())
    block_reason = work["completion_block_reason"].map(lambda value: normalize_text(value).lower())
    mask = (
        status.isin({"login_backtrack_pending", "login_backtrack_running"})
        | reason.eq("login_backtrack_required")
        | block_reason.isin({"bbp_login_required", "dashboard_yes_no_backtrack_required"})
    )
    return work[mask].copy()


def _ensure_login_mode_request_for_active_backtrack(
    *,
    live_dir: Path,
    active: pd.DataFrame,
    observed_utc: str,
) -> dict[str, str]:
    request = _read_login_mode_request(live_dir)
    if _login_mode_request_active(request):
        return request
    if _saved_auth_state(live_dir) != AUTH_STATE_LOGGED_IN:
        return request
    pending_backtrack = _active_login_backtrack_rows(active)
    if pending_backtrack.empty:
        return request

    path = _login_mode_request_path(live_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    request["request_path"] = str(path)
    request["request_exists"] = "1"
    request.setdefault("requested_utc", observed_utc)
    request.setdefault("requested_by", "fpm130")
    request.setdefault("mode", "login_recovery")
    request.setdefault("hold_seconds", str(LOGIN_MODE_DEFAULT_HOLD_SECONDS))
    request.setdefault("reason", "active_login_backtrack_recovery")
    request["status"] = "authenticated_backlog_remaining"
    request["last_observed_utc"] = observed_utc
    request["last_status_note"] = f"reactivated_for_active_login_backtrack_rows={len(pending_backtrack.index)}"
    ordered_keys = [
        "requested_utc",
        "requested_by",
        "mode",
        "supplier_id",
        "run_id",
        "status",
        "hold_seconds",
        "reason",
        "last_observed_utc",
        "last_status_note",
    ]
    lines = [f"{key}={normalize_text(request.get(key, ''))}" for key in ordered_keys if normalize_text(request.get(key, ""))]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return _read_login_mode_request(live_dir)


def _apply_login_mode_env(env: dict[str, str], request: dict[str, str]) -> None:
    if not _login_mode_request_active(request):
        for key in [
            "F061_LOGIN_MODE",
            "F061_LOGIN_HOLD_SECONDS",
            "F061_LOGIN_MODE_REQUEST_PATH",
            "F061_MANUAL_BBP_LOGIN_WAIT_SECONDS",
        ]:
            env.pop(key, None)
        if normalize_text(request.get("request_exists", "")) == "1":
            env["F061_BACKGROUND_BROWSER_MODE"] = "minimized"
            env["F061_SHOW_WINDOWS"] = "0"
            env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] = "1"
        return
    hold_seconds = _login_mode_hold_seconds(request)
    env["F061_BACKGROUND_BROWSER_MODE"] = "visible"
    env["F061_SHOW_WINDOWS"] = "1"
    env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] = "0"
    env["F061_LOGIN_MODE"] = "1"
    env["F061_LOGIN_HOLD_SECONDS"] = str(hold_seconds)
    env["F061_LOGIN_MODE_REQUEST_PATH"] = normalize_text(request.get("request_path", ""))
    env["F061_MANUAL_BBP_LOGIN_WAIT_SECONDS"] = str(hold_seconds)


def _apply_authenticated_login_mode_browser_policy(
    *,
    env: dict[str, str],
    live_dir: Path,
    request: dict[str, str],
) -> None:
    if not _login_mode_request_active(request):
        return
    if _saved_auth_state(live_dir) != AUTH_STATE_LOGGED_IN:
        return
    env["F061_BACKGROUND_BROWSER_MODE"] = "minimized"
    env["F061_SHOW_WINDOWS"] = "0"
    env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] = "1"


def _login_mode_child_browser_mode_note(live_dir: Path) -> str:
    if _saved_auth_state(live_dir) == AUTH_STATE_LOGGED_IN:
        return "minimized_authenticated"
    return "visible_from_start"


def _append_login_mode_child_started_event(
    *,
    live_dir: Path,
    event_utc: str,
    cycle_run_id: str,
    supplier_id: str,
    f061_run_id: str,
    rows: int,
    request: dict[str, str],
) -> None:
    hold_seconds = _login_mode_hold_seconds(request)
    child_browser_mode = _login_mode_child_browser_mode_note(live_dir)
    _append_event(
        live_dir=live_dir,
        event_utc=event_utc,
        cycle_run_id=cycle_run_id,
        event_type="login_mode_child_started",
        supplier_id=supplier_id,
        f061_run_id=f061_run_id,
        status="started",
        rows=rows,
        notes=(
            f"request_path={normalize_text(request.get('request_path', ''))};"
            f"hold_seconds={hold_seconds};browser_mode={child_browser_mode}"
        ),
    )


def _record_login_mode_request_health(
    *,
    live_dir: Path,
    observed_utc: str,
    request: dict[str, str],
    child_starting: bool,
    pending_rows: int,
) -> None:
    if not _login_mode_request_active(request):
        status = "ok"
        value = "no_request"
        notes = "login_mode_request=absent"
    elif child_starting:
        status = "ok"
        value = "child_starting"
        notes = (
            f"login_mode_request=active;pending_rows={max(int(pending_rows), 0)};"
            f"request_path={normalize_text(request.get('request_path', ''))};"
            f"hold_seconds={_login_mode_hold_seconds(request)}"
        )
    else:
        status = "warn"
        value = "request_waiting"
        notes = (
            f"login_mode_request=active_without_child;pending_rows={max(int(pending_rows), 0)};"
            f"request_path={normalize_text(request.get('request_path', ''))}"
        )
    health_path = live_dir / "live_cycle_health.csv"
    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    row = pd.DataFrame(
        [
            {
                "check": "f061_login_mode_request_state",
                "status": status,
                "value": value,
                "notes": notes,
                "observed_utc": observed_utc,
                "source_path": str(_login_mode_request_path(live_dir)),
            }
        ]
    )
    write_csv(health_path, pd.concat([existing_health, row], ignore_index=True), MANAGER_HEALTH_COLUMNS)


def _import_f061_memory_after_chunk(
    *,
    root: Path,
    live_dir: Path,
    event_utc: str,
    cycle_run_id: str,
    supplier_id: str,
    f061_run_id: str,
) -> dict[str, object]:
    try:
        summary = update_memory_from_f061_results(
            root=root,
            observed_utc=event_utc,
            supplier_id=supplier_id,
            run_id=f061_run_id,
        )
    except Exception as exc:
        summary = {"status": "blocked", "new_memory_rows": 0, "notes": str(exc)}

    status = normalize_text(summary.get("status", "")) or "unknown"
    notes = normalize_text(summary.get("notes", ""))
    if not notes:
        notes = (
            f"processed_rows={normalize_text(summary.get('processed_rows', '0')) or '0'};"
            f"memory_rows={normalize_text(summary.get('memory_rows', '0')) or '0'}"
        )
    _append_event(
        live_dir=live_dir,
        event_utc=event_utc,
        cycle_run_id=cycle_run_id,
        event_type="f061_memory_import",
        supplier_id=supplier_id,
        f061_run_id=f061_run_id,
        status=status,
        rows=_price_list_int(summary.get("new_memory_rows", "0")),
        notes=notes,
    )
    return summary


def _build_completed_review_pack_if_ready(
    *,
    root: Path,
    live_dir: Path,
    event_utc: str,
    cycle_run_id: str,
    supplier_id: str,
    f061_run_id: str,
) -> dict[str, object]:
    if not supplier_id or not f061_run_id:
        return {"status": "skipped", "notes": "missing_supplier_or_run"}
    try:
        summary = build_completed_review_pack(
            root=root,
            supplier_id=supplier_id,
            run_id=f061_run_id,
            observed_utc=event_utc,
            emit_json=False,
        )
    except Exception as exc:
        summary = {"status": "failed", "notes": str(exc)}

    status = normalize_text(summary.get("status", ""))
    rows = _price_list_int(summary.get("pass_review_rows", "0")) + _price_list_int(
        summary.get("near_miss_review_rows", "0")
    )
    notes = normalize_text(summary.get("block_reason", "")) or normalize_text(summary.get("notes", ""))
    if status in {"built", "already_built"}:
        notes = (
            f"pass_review_rows={normalize_text(summary.get('pass_review_rows', '0')) or '0'};"
            f"near_miss_review_rows={normalize_text(summary.get('near_miss_review_rows', '0')) or '0'}"
        )
    _append_event(
        live_dir=live_dir,
        event_utc=event_utc,
        cycle_run_id=cycle_run_id,
        event_type="review_pack_build",
        supplier_id=supplier_id,
        f061_run_id=f061_run_id,
        status=status or "unknown",
        rows=rows,
        notes=notes,
    )
    return summary


def _maintenance_requested(root: Path) -> bool:
    return any(path.exists() for path in _maintenance_request_paths(root))


def _maintenance_request_text(root: Path) -> str:
    parts = []
    for path in _maintenance_request_paths(root):
        try:
            if path.exists():
                parts.append(normalize_text(path.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            continue
    return "\n".join(part for part in parts if part)


def _maintenance_request_paths(root: Path) -> list[Path]:
    return [
        root / "out" / "systems" / "F" / "price_list_manager" / "live" / "f061_visible_login.requested",
        root / "out" / "locks" / "maintenance.requested",
    ]


def _maintenance_exit_after_drain(root: Path) -> bool:
    text = _maintenance_request_text(root).lower()
    return "exit_after_drain=1" in text or "action=reload" in text


def _write_drain_ready(live_dir: Path) -> Path:
    ready = live_dir / "F_restart_drain.ready"
    _write_text(ready, f"launcher_pid={os.getpid()}|utc={_utc_now_iso()}|state=drain_wait\n")
    return ready


def _clear_drain_ready(live_dir: Path) -> None:
    ready = live_dir / "F_restart_drain.ready"
    try:
        ready.unlink(missing_ok=True)
    except Exception:
        pass


def _auth_attention_active(live_dir: Path) -> bool:
    events = read_csv(live_dir / "live_cycle_events.csv", LIVE_CYCLE_EVENT_COLUMNS)
    if events.empty:
        return False
    auth_events = events[events["event_type"] == "f061_auth_attention"]
    if auth_events.empty:
        return False
    status = normalize_text(auth_events.iloc[-1].get("status", "")).lower()
    return status in {"attention_needed", "visible_requested"}


def _browser_visibility_parts(live_dir: Path) -> dict[str, str]:
    path = live_dir / "f061_browser_visibility_state.txt"
    line = _read_first_line(path)
    if not line:
        return {}
    parts = {}
    for item in [part.strip() for part in line.split("|") if part.strip()]:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        clean_key = normalize_text(key).lstrip("\ufeff")
        parts[clean_key] = normalize_text(value)
    return parts


def _browser_visibility_state(live_dir: Path) -> str:
    parts = _browser_visibility_parts(live_dir)
    browser_state = normalize_text(parts.get("browser_state", "")).upper()
    if browser_state in {BROWSER_STATE_HIDDEN, BROWSER_STATE_VISIBLE}:
        return browser_visibility_value(browser_state)
    state = normalize_text(parts.get("state", "")).lower()
    return state if state in {"visible", "hidden"} else ""


def _saved_auth_state(live_dir: Path) -> str:
    parts = _browser_visibility_parts(live_dir)
    reason = normalize_text(parts.get("reason", "")).lower()
    auth_state = normalize_text(parts.get("auth_state", "")).upper()
    if reason in {"child_started_minimized", "child_started_hidden"}:
        return ""
    if auth_state in {AUTH_STATE_LOGGED_IN, AUTH_STATE_LOGIN_REQUIRED, *AUTH_STATES_REQUIRING_VISIBLE}:
        return auth_state
    return auth_state_for_browser_visibility(_browser_visibility_state(live_dir))


def _scanner_browser_blocked_rows(scanner_summary: dict[str, object]) -> int:
    return _price_list_int(scanner_summary.get("scanner_speed_browser_blocked_rows", "0"))


def _scanner_summary_requires_login_wait(live_dir: Path, scanner_summary: dict[str, object]) -> bool:
    if normalize_text(scanner_summary.get("status", "")).lower() != "failed":
        return False
    notes = normalize_text(scanner_summary.get("notes", "")).lower()
    if "f061_child_timeout_seconds" not in notes and "timed out" not in notes:
        return False
    return _saved_auth_state(live_dir) in AUTH_STATES_REQUIRING_VISIBLE


def _record_auth_attention_after_chunk(
    *,
    live_dir: Path,
    event_utc: str,
    cycle_run_id: str,
    scanner_summary: dict[str, object],
) -> str:
    blocked_rows = _scanner_browser_blocked_rows(scanner_summary)
    processed_rows = _price_list_int(scanner_summary.get("processed_rows", "0"))
    login_mode_active = normalize_text(scanner_summary.get("login_mode_active", "")).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    login_mode_runtime_status = normalize_text(scanner_summary.get("login_mode_runtime_status", "")).lower()
    if login_mode_active and login_mode_runtime_status in {"authenticated_backlog_remaining", "backlog_drained"}:
        _write_browser_visibility_state(live_dir, state="hidden", reason="login_mode_authenticated")
        _append_event(
            live_dir=live_dir,
            event_utc=event_utc,
            cycle_run_id=cycle_run_id,
            event_type="f061_auth_attention",
            status="cleared",
            rows=0,
            notes=f"login_mode_authenticated;runtime_status={login_mode_runtime_status};next_child_browser_mode=minimized",
        )
        return "cleared"
    if blocked_rows > 0:
        visibility_parts = _browser_visibility_parts(live_dir)
        visibility_reason = normalize_text(visibility_parts.get("reason", "")).lower()
        if _saved_auth_state(live_dir) == AUTH_STATE_LOGGED_IN and visibility_reason in {
            "auth_confirmed",
            "login_mode_authenticated",
        }:
            _write_browser_visibility_state(live_dir, state="hidden", reason="auth_attention_recovered")
            _append_event(
                live_dir=live_dir,
                event_utc=event_utc,
                cycle_run_id=cycle_run_id,
                event_type="f061_auth_attention",
                status="cleared",
                rows=0,
                notes="browser_block_signal_seen_but_auth_confirmed;next_child_browser_mode=minimized",
            )
            return "cleared"
        if login_mode_active or not _auto_visible_auth_attention_enabled():
            _write_browser_visibility_state(live_dir, state="hidden", reason="auth_attention_deferred_login_mode")
            note_reason = "login_mode_still_required" if login_mode_active else "login_mode_button_required"
            _append_event(
                live_dir=live_dir,
                event_utc=event_utc,
                cycle_run_id=cycle_run_id,
                event_type="f061_auth_attention",
                status="deferred_login_mode",
                rows=blocked_rows,
                notes=f"browser_block_signal_seen;{note_reason};next_child_browser_mode=minimized",
            )
            return "deferred_login_mode"
        _write_browser_visibility_state(live_dir, state="visible", reason="auth_attention_required")
        _append_event(
            live_dir=live_dir,
            event_utc=event_utc,
            cycle_run_id=cycle_run_id,
            event_type="f061_auth_attention",
            status="attention_needed",
            rows=blocked_rows,
            notes="browser_block_signal_seen;next_child_browser_mode=visible",
        )
        return "attention_needed"
    if processed_rows > 0 and _auth_attention_active(live_dir):
        _write_browser_visibility_state(live_dir, state="hidden", reason="auth_attention_cleared")
        _append_event(
            live_dir=live_dir,
            event_utc=event_utc,
            cycle_run_id=cycle_run_id,
            event_type="f061_auth_attention",
            status="cleared",
            rows=0,
            notes="clean_child_seen;next_child_browser_mode=minimized",
        )
        return "cleared"
    return "unchanged"


def _refresh_manager_outputs(root: Path, observed_utc: str) -> None:
    check_acquisition_sources(root=root, checked_at_utc=observed_utc)
    download_ready_url_sources(root=root, downloaded_at_utc=observed_utc)
    fetch_api_sources(root=root, fetched_at_utc=observed_utc)
    fetch_gmail_email_sources(root=root, fetched_at_utc=observed_utc)
    import_ready_sources(root=root, imported_at_utc=observed_utc)
    enrich_batch_rows_for_f061(root=root, observed_utc=observed_utc)
    build_next_action(root=root, observed_utc=observed_utc)
    build_next_action_report(root=root, built_at_utc=observed_utc)
    build_status_dashboard(root=root, built_at_utc=observed_utc)


def _scanner_browser_mode_for_next_child(root: Path | None = None) -> str:
    auto_visible = _auto_visible_auth_attention_enabled()
    if root is not None:
        live_dir = get_manager_paths(root=root).system_dir / "live"
        if _login_mode_request_active(_read_login_mode_request(live_dir)):
            if _saved_auth_state(live_dir) in AUTH_STATES_REQUIRING_VISIBLE:
                return "visible"
            return "minimized"
    raw = normalize_text(os.environ.get("F061_BACKGROUND_BROWSER_MODE", "")).lower()
    if raw in {"visible", "minimized"}:
        return raw
    if root is not None:
        live_dir = get_manager_paths(root=root).system_dir / "live"
        if auto_visible and _auth_attention_active(live_dir):
            return "visible"
        auth_state = _saved_auth_state(live_dir)
        if auth_state == AUTH_STATE_LOGGED_IN:
            return "minimized"
        if auto_visible and auth_state in AUTH_STATES_REQUIRING_VISIBLE:
            return "visible"
        visibility_state = _browser_visibility_state(live_dir)
        if visibility_state == "hidden":
            return "minimized"
        if auto_visible and visibility_state == "visible":
            return "visible"
        active = read_f_contract_df(root, "supplier_price_list_active_run")
        if not active.empty and "scan_status" in active.columns:
            if auto_visible and active.apply(lambda row: active_row_requires_visible_browser(row.to_dict()), axis=1).any():
                return "visible"
    return "minimized"


def _build_scanner_child_env(root: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    login_request: dict[str, str] = {}
    if root is not None:
        login_request = _read_login_mode_request(get_manager_paths(root=root).system_dir / "live")
    mode = _scanner_browser_mode_for_next_child(root)
    env["F061_BACKGROUND_BROWSER_MODE"] = mode
    if mode == "visible":
        env["F061_SHOW_WINDOWS"] = "1"
        env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] = "0"
    else:
        env["F061_SHOW_WINDOWS"] = "0"
        env["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] = "1"
    _apply_login_mode_env(env, login_request)
    if root is not None:
        _apply_authenticated_login_mode_browser_policy(
            env=env,
            live_dir=get_manager_paths(root=root).system_dir / "live",
            request=login_request,
        )
    return env


def _child_env_hides_scraper_windows(env: dict[str, str]) -> bool:
    return normalize_text(env.get("FPM_LIVE_HIDE_SCRAPER_WINDOWS", "1")).lower() not in {"0", "false", "no"}


def _scraper_window_hider_running(root: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "$self=$PID; "
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.ProcessId -ne $self -and $_.CommandLine -like '*f_hide_scraper_windows.ps1*' } | "
                    "Select-Object -First 1 -ExpandProperty ProcessId"
                ),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return bool(normalize_text(completed.stdout))
    except Exception:
        return False


def _stop_scraper_window_hider(root: Path) -> None:
    if os.name != "nt":
        return
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "$self=$PID; "
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.ProcessId -ne $self -and $_.CommandLine -like '*f_hide_scraper_windows.ps1*' } | "
                    "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }"
                ),
            ],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except Exception:
        pass


def _ensure_scraper_window_hider(root: Path, *, force: bool = False) -> None:
    if os.name != "nt":
        return
    if not force and normalize_text(os.environ.get("FPM_LIVE_HIDE_SCRAPER_WINDOWS", "1")).lower() in {"0", "false", "no"}:
        return
    script_path = root / "scripts" / "tools" / "f_hide_scraper_windows.ps1"
    if not script_path.exists() or _scraper_window_hider_running(root):
        return
    try:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass


def _show_scraper_windows_once(
    root: Path,
    *,
    login_mode: bool = False,
    user_data_dir: str = "",
    profile_dir: str = "",
) -> bool:
    if os.name != "nt":
        return False
    if login_mode:
        user_data_value = (
            normalize_text(user_data_dir)
            or normalize_text(os.environ.get("F061_BBP_USER_DATA_DIR", ""))
            or DEFAULT_F061_BBP_USER_DATA_DIR
        )
        profile_value = (
            normalize_text(profile_dir)
            or normalize_text(os.environ.get("F061_BBP_PROFILE_DIR", ""))
            or DEFAULT_F061_BBP_PROFILE_DIR
        )
        user_data_pattern = re.escape(user_data_value)
        profile_pattern = re.escape(profile_value)
        if not user_data_pattern or not profile_pattern:
            return False
        target_filter = rf'''
        $_.Name -eq "chrome.exe" -and
        $_.CommandLine -match "{user_data_pattern}" -and
        $_.CommandLine -match "--profile-directory={profile_pattern}(\s|`"|$)"
'''
    else:
        target_filter = r'''
        $_.Name -eq "chrome.exe" -and
        (
          $_.CommandLine -match "Chrome_UC136|Chrome_91_F061|Chrome_91" -or
          $_.ExecutablePath -match "Chrome_UC136|Chrome_91_F061|Chrome_91|GoogleChromePortable"
        )
'''
    ps_command = r'''
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class WinApiShowOnce {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [StructLayout(LayoutKind.Sequential)]
  public struct POINT { public int X; public int Y; }
  [StructLayout(LayoutKind.Sequential)]
  public struct WINDOWPLACEMENT {
    public int length;
    public int flags;
    public int showCmd;
    public POINT ptMinPosition;
    public POINT ptMaxPosition;
    public RECT rcNormalPosition;
  }
  [DllImport("user32.dll")]
  public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")]
  public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")]
  public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  [DllImport("user32.dll")]
  public static extern bool SetWindowPlacement(IntPtr hWnd, ref WINDOWPLACEMENT lpwndpl);
  [DllImport("user32.dll")]
  public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  [DllImport("user32.dll")]
  public static extern bool BringWindowToTop(IntPtr hWnd);
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll", EntryPoint="GetWindowLongPtr", SetLastError=true)]
  public static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);
  [DllImport("user32.dll", EntryPoint="SetWindowLongPtr", SetLastError=true)]
  public static extern IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong);
}
"@
$targets = Get-CimInstance Win32_Process |
  Where-Object {
__TARGET_FILTER__
  } |
  Select-Object -ExpandProperty ProcessId
$callback = [WinApiShowOnce+EnumWindowsProc]{
  param($hWnd, $lParam)
  [uint32]$outPid = 0
  [WinApiShowOnce]::GetWindowThreadProcessId($hWnd, [ref]$outPid) | Out-Null
  if ($targets -contains [int]$outPid) {
    try {
      $titleBuilder = New-Object System.Text.StringBuilder 512
      [WinApiShowOnce]::GetWindowText($hWnd, $titleBuilder, $titleBuilder.Capacity) | Out-Null
      $title = $titleBuilder.ToString()
      if ($title -notmatch "Chromium|Chrome|Amazon|Restore pages") {
        return $true
      }
      $style = [WinApiShowOnce]::GetWindowLongPtr($hWnd, -16).ToInt64()
      $newStyle = ($style -bor 0x10000000L) -band (-bnot 0x20000000L)
      [WinApiShowOnce]::SetWindowLongPtr($hWnd, -16, [IntPtr]::new($newStyle)) | Out-Null
      $placement = New-Object WinApiShowOnce+WINDOWPLACEMENT
      $placement.length = [System.Runtime.InteropServices.Marshal]::SizeOf([type][WinApiShowOnce+WINDOWPLACEMENT])
      $placement.flags = 0
      $placement.showCmd = 1
      $placement.ptMinPosition = New-Object WinApiShowOnce+POINT
      $placement.ptMaxPosition = New-Object WinApiShowOnce+POINT
      $placement.rcNormalPosition = New-Object WinApiShowOnce+RECT
      $placement.rcNormalPosition.Left = 20
      $placement.rcNormalPosition.Top = 20
      $placement.rcNormalPosition.Right = 1620
      $placement.rcNormalPosition.Bottom = 970
      [WinApiShowOnce]::SetWindowPlacement($hWnd, [ref]$placement) | Out-Null
      foreach ($cmd in @(9, 1, 5, 3)) {
        [WinApiShowOnce]::ShowWindow($hWnd, $cmd) | Out-Null
        [WinApiShowOnce]::ShowWindowAsync($hWnd, $cmd) | Out-Null
      }
      [WinApiShowOnce]::SetWindowPos($hWnd, [IntPtr](-1), 20, 20, 1600, 950, 0x0040 -bor 0x0020) | Out-Null
      Start-Sleep -Milliseconds 100
      [WinApiShowOnce]::BringWindowToTop($hWnd) | Out-Null
      [WinApiShowOnce]::SetForegroundWindow($hWnd) | Out-Null
      [WinApiShowOnce]::SetWindowPos($hWnd, [IntPtr](-2), 20, 20, 1600, 950, 0x0040 -bor 0x0020) | Out-Null
    } catch {
    }
  }
  return $true
}
[WinApiShowOnce]::EnumWindows($callback, [IntPtr]::Zero) | Out-Null
'''.replace("__TARGET_FILTER__", target_filter)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except Exception:
        pass
    return _show_scraper_windows_via_devtools(
        root,
        login_mode=login_mode,
        user_data_dir=user_data_dir,
        profile_dir=profile_dir,
    )


def _remote_debugging_ports_from_command_lines(command_lines: list[str]) -> list[int]:
    ports: list[int] = []
    seen: set[int] = set()
    for command_line in command_lines:
        for match in re.finditer(r"--remote-debugging-port=(\d+)", normalize_text(command_line)):
            port = int(match.group(1))
            if port > 0 and port not in seen:
                seen.add(port)
                ports.append(port)
    return ports


def _target_chrome_command_lines_for_devtools(*, login_mode: bool, user_data_dir: str = "", profile_dir: str = "") -> list[str]:
    if os.name != "nt":
        return []
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.Name -eq 'chrome.exe' -and $_.CommandLine -and $_.CommandLine -notmatch ' --type=' } | "
                    "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    raw = normalize_text(getattr(completed, "stdout", ""))
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    rows = parsed if isinstance(parsed, list) else [parsed]
    commands = [normalize_text(row.get("CommandLine", "")) for row in rows if isinstance(row, dict)]
    if login_mode:
        user_data_value = (
            normalize_text(user_data_dir)
            or normalize_text(os.environ.get("F061_BBP_USER_DATA_DIR", ""))
            or DEFAULT_F061_BBP_USER_DATA_DIR
        )
        profile_value = (
            normalize_text(profile_dir)
            or normalize_text(os.environ.get("F061_BBP_PROFILE_DIR", ""))
            or DEFAULT_F061_BBP_PROFILE_DIR
        )
        user_data_lower = user_data_value.lower()
        profile_token = f"--profile-directory={profile_value}".lower()
        return [
            command
            for command in commands
            if user_data_lower in command.lower() and profile_token in command.lower()
        ]
    return [
        command
        for command in commands
        if any(token.lower() in command.lower() for token in ("Chrome_UC136", "Chrome_91_F061", "Chrome_91"))
    ]


def _surface_devtools_port(port: int) -> bool:
    try:
        import websocket  # type: ignore

        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/json/version", timeout=2) as response:
            version = json.loads(response.read().decode("utf-8", errors="replace"))
        ws = websocket.create_connection(
            normalize_text(version.get("webSocketDebuggerUrl", "")),
            timeout=2,
            suppress_origin=True,
        )
        command_id = 0

        def cdp(method: str, params: dict[str, object] | None = None, session_id: str = "") -> dict[str, object]:
            nonlocal command_id
            command_id += 1
            payload: dict[str, object] = {"id": command_id, "method": method, "params": params or {}}
            if session_id:
                payload["sessionId"] = session_id
            ws.send(json.dumps(payload))
            while True:
                message = json.loads(ws.recv())
                if message.get("id") == command_id:
                    return message if isinstance(message, dict) else {}

        targets = cdp("Target.getTargets").get("result", {}).get("targetInfos", [])  # type: ignore[union-attr]
        pages = [info for info in targets if isinstance(info, dict) and info.get("type") == "page"]
        selected = pages[0] if pages else {}
        target_id = normalize_text(selected.get("targetId", "")) if isinstance(selected, dict) else ""
        if not target_id:
            ws.close()
            return False
        window_info = cdp("Browser.getWindowForTarget", {"targetId": target_id}).get("result", {})  # type: ignore[union-attr]
        window_id = window_info.get("windowId") if isinstance(window_info, dict) else None
        if window_id is not None:
            cdp(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {
                        "windowState": "normal",
                        "left": 80,
                        "top": 80,
                        "width": 1400,
                        "height": 900,
                    },
                },
            )
        cdp("Target.activateTarget", {"targetId": target_id})
        session = cdp("Target.attachToTarget", {"targetId": target_id, "flatten": True}).get("result", {}).get("sessionId", "")  # type: ignore[union-attr]
        if session:
            cdp("Page.bringToFront", {}, session_id=normalize_text(session))
        ws.close()
        return True
    except Exception:
        return False


def _show_scraper_windows_via_devtools(
    root: Path,
    *,
    login_mode: bool = False,
    user_data_dir: str = "",
    profile_dir: str = "",
) -> bool:
    del root
    command_lines = _target_chrome_command_lines_for_devtools(
        login_mode=login_mode,
        user_data_dir=user_data_dir,
        profile_dir=profile_dir,
    )
    for port in _remote_debugging_ports_from_command_lines(command_lines):
        if _surface_devtools_port(port):
            return True
    return False


def _apply_child_start_browser_visibility(root: Path, child_env: dict[str, str]) -> None:
    if _child_env_hides_scraper_windows(child_env):
        _ensure_scraper_window_hider(root, force=True)
    else:
        _stop_scraper_window_hider(root)
        browser_mode = normalize_text(child_env.get("F061_BACKGROUND_BROWSER_MODE", "")).lower()
        if browser_mode in {"", "visible"}:
            _show_scraper_windows_once(
                root,
                login_mode=normalize_text(child_env.get("F061_LOGIN_MODE", "")) == "1",
                user_data_dir=child_env.get("F061_BBP_USER_DATA_DIR", ""),
                profile_dir=child_env.get("F061_BBP_PROFILE_DIR", ""),
            )


def _scanner_child_startupinfo(browser_mode: str) -> subprocess.STARTUPINFO | None:
    if os.name != "nt" or normalize_text(browser_mode).lower() != "visible":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    startupinfo.wShowWindow = 1
    return startupinfo


def _auth_visibility_signal_from_text(text: str) -> tuple[str, str]:
    auth_state = auth_state_from_log_text(text)
    browser_state = browser_state_for_auth_state(auth_state)
    signal = browser_visibility_value(browser_state)
    if auth_state == AUTH_STATE_BBP_LOGIN_REQUIRED:
        return signal, "bbp_login_required"
    if auth_state == AUTH_STATE_DASHBOARD_LOGIN_REQUIRED:
        return signal, "amazon_dashboard_login_required"
    if auth_state == AUTH_STATE_LOGIN_REQUIRED:
        return signal, "auth_required"
    if auth_state == AUTH_STATE_LOGGED_IN:
        return signal, "auth_confirmed"
    return "", ""


def _read_log_since(path: Path, start_offset: int) -> str:
    try:
        with path.open("rb") as fh:
            fh.seek(max(int(start_offset), 0))
            return fh.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _auth_state_for_visibility_reason(state: str, reason: str) -> str:
    reason_l = normalize_text(reason).lower()
    if reason_l in {"child_started_minimized", "child_started_hidden"}:
        return ""
    if "amazon_dashboard_login_required" in reason_l or "dashboard_login_required" in reason_l:
        return AUTH_STATE_DASHBOARD_LOGIN_REQUIRED
    if "bbp_login_required" in reason_l:
        return AUTH_STATE_BBP_LOGIN_REQUIRED
    if reason_l in {"auth_confirmed", "login_mode_authenticated", "auth_attention_recovered", "auth_attention_cleared"}:
        return AUTH_STATE_LOGGED_IN
    return auth_state_for_browser_visibility(state)


def _write_browser_visibility_state(live_dir: Path, *, state: str, reason: str) -> None:
    path = live_dir / "f061_browser_visibility_state.txt"
    browser_state = BROWSER_STATE_HIDDEN if state == "hidden" else BROWSER_STATE_VISIBLE if state == "visible" else ""
    auth_state = _auth_state_for_visibility_reason(state, reason)
    path.write_text(
        f"state={state}|browser_state={browser_state}|auth_state={auth_state}|reason={reason}|updated_utc={_utc_now_iso()}\n",
        encoding="utf-8",
        newline="\n",
    )


def _child_started_visibility_reason(live_dir: Path, *, browser_visibility_state: str, browser_mode: str) -> str:
    reason = f"child_started_{normalize_text(browser_mode).lower() or 'minimized'}"
    if normalize_text(browser_visibility_state).lower() == "hidden" and _saved_auth_state(live_dir) == AUTH_STATE_LOGGED_IN:
        return "auth_confirmed"
    return reason


def _login_mode_show_marker_path(live_dir: Path) -> Path:
    return live_dir / "f061_login_mode_window_shown.marker"


def _mark_login_mode_window_shown(live_dir: Path) -> None:
    _login_mode_show_marker_path(live_dir).write_text(_utc_now_iso() + "\n", encoding="utf-8", newline="\n")


def _clear_login_mode_window_shown(live_dir: Path) -> None:
    try:
        _login_mode_show_marker_path(live_dir).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _login_mode_window_already_shown(live_dir: Path) -> bool:
    return _login_mode_show_marker_path(live_dir).exists()


def _apply_browser_visibility_signal(
    *,
    root: Path,
    live_dir: Path,
    state: str,
    reason: str,
    cycle_run_id: str = "f061_child",
) -> None:
    if state == "hidden":
        _ensure_scraper_window_hider(root, force=True)
    elif state == "visible":
        _stop_scraper_window_hider(root)
        _show_scraper_windows_once(root)
    else:
        return
    _write_browser_visibility_state(live_dir, state=state, reason=reason)
    _append_event(
        live_dir=live_dir,
        event_utc=_utc_now_iso(),
        cycle_run_id=cycle_run_id,
        event_type="f061_browser_visibility",
        status=state,
        rows=0,
        notes=reason,
    )


def _update_child_auth_visibility_from_logs(
    *,
    root: Path,
    live_dir: Path,
    stdout_path: Path,
    stderr_path: Path,
    stdout_start_offset: int,
    stderr_start_offset: int,
    current_state: str,
    allow_visible_auth_required: bool | None = None,
    login_mode: bool = False,
) -> str:
    text = "\n".join(
        [
            _read_log_since(stdout_path, stdout_start_offset),
            _read_log_since(stderr_path, stderr_start_offset),
        ]
    )
    signal, reason = _auth_visibility_signal_from_text(text)
    if not signal:
        return current_state
    if login_mode and signal == "visible":
        already_shown = _login_mode_window_already_shown(live_dir)
        if not already_shown:
            surfaced = _show_scraper_windows_once(root, login_mode=True)
            if surfaced:
                _mark_login_mode_window_shown(live_dir)
        if current_state != "visible" or not already_shown:
            _write_browser_visibility_state(live_dir, state="visible", reason=f"{reason}_scanner_owned")
            _append_event(
                live_dir=live_dir,
                event_utc=_utc_now_iso(),
                cycle_run_id="f061_child",
                event_type="f061_browser_visibility",
                status="visible",
                rows=0,
                notes=f"{reason}_scanner_owned",
            )
        return "visible"
    if signal == current_state:
        if signal == "hidden" and reason == "auth_confirmed":
            visibility_reason = normalize_text(_browser_visibility_parts(live_dir).get("reason", "")).lower()
            if _saved_auth_state(live_dir) != AUTH_STATE_LOGGED_IN or visibility_reason in {
                "",
                "child_started_minimized",
                "child_started_hidden",
            }:
                _apply_browser_visibility_signal(root=root, live_dir=live_dir, state=signal, reason=reason)
        if signal == "visible" and reason in {"auth_required", "bbp_login_required", "amazon_dashboard_login_required"}:
            visibility_reason = normalize_text(_browser_visibility_parts(live_dir).get("reason", "")).lower()
            if visibility_reason.startswith(reason):
                return current_state
            if allow_visible_auth_required is None:
                allow_visible_auth_required = _auto_visible_auth_attention_enabled()
            if allow_visible_auth_required and not (login_mode and _login_mode_window_already_shown(live_dir)):
                surfaced = _show_scraper_windows_once(root, login_mode=login_mode)
                if login_mode and surfaced:
                    _mark_login_mode_window_shown(live_dir)
        return current_state
    if signal == "visible" and reason in {"auth_required", "bbp_login_required", "amazon_dashboard_login_required"}:
        if allow_visible_auth_required is None:
            allow_visible_auth_required = _auto_visible_auth_attention_enabled()
        if not allow_visible_auth_required:
            return current_state
    _apply_browser_visibility_signal(root=root, live_dir=live_dir, state=signal, reason=reason)
    return signal


def _scanner_child_timeout_seconds(chunk_rows: int) -> float:
    raw = normalize_text(os.environ.get("FPM_F061_CHILD_TIMEOUT_SECONDS", ""))
    if raw:
        try:
            return max(float(raw), 0.0)
        except ValueError:
            pass
    return max(1800.0, float(max(int(chunk_rows), 1)) * 360.0)


def _scanner_child_stall_seconds() -> float:
    raw = normalize_text(os.environ.get(F061_CHILD_STALL_SECONDS_ENV, ""))
    if raw:
        try:
            return max(float(raw), 0.0)
        except ValueError:
            pass
    return 600.0


def _manager_mode_for_child(
    *,
    auth_state: str,
    browser_mode: str,
    browser_visibility_state: str,
    login_mode_child: bool,
    child_status: str = "running",
) -> str:
    clean_status = normalize_text(child_status).lower()
    if clean_status in {"stalled", "timed_out", "restarting"}:
        return "Restarting Scanner"
    auth = normalize_text(auth_state).upper()
    mode = normalize_text(browser_mode).lower()
    visibility = normalize_text(browser_visibility_state).lower()
    if login_mode_child and auth in AUTH_STATES_REQUIRING_VISIBLE and (mode == "visible" or visibility == "visible"):
        return "Login Window Open"
    if login_mode_child and auth == AUTH_STATE_LOGGED_IN:
        return "Catching Up"
    if auth == AUTH_STATE_LOGGED_IN and mode == "minimized":
        return "Scanning Hidden"
    if auth in AUTH_STATES_REQUIRING_VISIBLE:
        return "Login Required"
    if mode == "visible" or visibility == "visible":
        return "Scanner Visible"
    return "Scanning Hidden"


def _write_manager_mode_state(
    live_dir: Path,
    *,
    mode: str,
    auth_state: str = "",
    browser_mode: str = "",
    browser_visibility_state: str = "",
    child_pid: int | None = None,
    supplier_id: str = "",
    f061_run_id: str = "",
    notes: str = "",
    observed_utc: str | None = None,
) -> None:
    parts = [
        f"mode={normalize_text(mode)}",
        f"auth_state={normalize_text(auth_state).upper()}",
        f"browser_mode={normalize_text(browser_mode).lower()}",
        f"browser_visibility={normalize_text(browser_visibility_state).lower()}",
        f"pid={int(child_pid or 0)}",
        f"supplier_id={normalize_text(supplier_id)}",
        f"run_id={normalize_text(f061_run_id)}",
        f"notes={normalize_text(notes)}",
        f"updated_utc={observed_utc or _utc_now_iso()}",
    ]
    _write_text(live_dir / "f061_manager_mode_state.txt", "|".join(parts) + "\n")


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
            if proc.poll() is not None or int(completed.returncode or 0) == 0:
                return
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass


def _parse_latest_child_summary(stdout_path: Path, *, start_offset: int) -> dict[str, object]:
    try:
        with stdout_path.open("rb") as fh:
            fh.seek(max(int(start_offset), 0))
            text = fh.read().decode("utf-8", errors="replace")
    except Exception:
        return {}
    latest: dict[str, object] = {}
    for line in text.splitlines():
        raw = line.strip()
        if not raw.startswith("{") or "'status'" not in raw:
            continue
        try:
            parsed = ast.literal_eval(raw)
        except Exception:
            continue
        if isinstance(parsed, dict) and normalize_text(parsed.get("status", "")):
            latest = parsed
    return latest


def _run_scanner_subprocess(root: Path, *, supplier_id: str, chunk_rows: int) -> dict[str, object]:
    py = sys.executable
    paths = get_manager_paths(root=root)
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    lock_path = live_dir / "live_cycle.lock"
    scanner_stdout = live_dir / "f061_child_stdout.log"
    scanner_stderr = live_dir / "f061_child_stderr.log"
    cmd = [
        py,
        "-u",
        str(root / "scripts" / "flows" / "F" / "F061_run_legacy_first_checks_local.py"),
        "--supplier-id",
        supplier_id,
        "--max-rows",
        str(int(chunk_rows)),
        "--scrape-mode",
        "legacy_module",
        "--price-source",
        "legacy",
        "--catalog-max-candidates",
        normalize_text(os.environ.get("FPM_F061_CATALOG_MAX_CANDIDATES", "3")) or "3",
    ]
    scanner_started_utc = _utc_now_iso()
    child_timeout_seconds = _scanner_child_timeout_seconds(chunk_rows)
    child_stall_seconds = _scanner_child_stall_seconds()
    scanner_started_monotonic = time.monotonic()
    timed_out = False
    stalled = False
    stdout_start_offset = scanner_stdout.stat().st_size if scanner_stdout.exists() else 0
    stderr_start_offset = scanner_stderr.stat().st_size if scanner_stderr.exists() else 0
    last_output_size = stdout_start_offset + stderr_start_offset
    last_output_monotonic = scanner_started_monotonic
    last_output_utc = scanner_started_utc
    with scanner_stdout.open("a", encoding="utf-8", newline="\n") as stdout_fh, scanner_stderr.open(
        "a", encoding="utf-8", newline="\n"
    ) as stderr_fh:
        child_env = _build_scanner_child_env(root)
        browser_mode = normalize_text(child_env.get("F061_BACKGROUND_BROWSER_MODE", "minimized")) or "minimized"
        browser_visibility_state = "visible" if browser_mode == "visible" else "hidden"
        child_started_reason = _child_started_visibility_reason(
            live_dir,
            browser_visibility_state=browser_visibility_state,
            browser_mode=browser_mode,
        )
        _write_browser_visibility_state(live_dir, state=browser_visibility_state, reason=child_started_reason)
        stdout_fh.write(
            f"[{scanner_started_utc}] starting F061 supplier_id={supplier_id} "
            f"chunk_rows={chunk_rows} browser_mode={browser_mode} "
            f"bbp_user_data_dir={child_env.get('F061_BBP_USER_DATA_DIR', '')} "
            f"bbp_profile_dir={child_env.get('F061_BBP_PROFILE_DIR', '')}\n"
        )
        stdout_fh.flush()
        _apply_child_start_browser_visibility(root, child_env)
        proc = subprocess.Popen(
            cmd,
            cwd=str(root),
            env=child_env,
            startupinfo=_scanner_child_startupinfo(browser_mode),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=stdout_fh,
            stderr=stderr_fh,
        )
        login_mode_child = normalize_text(child_env.get("F061_LOGIN_MODE", "")) == "1"
        if login_mode_child:
            _clear_login_mode_window_shown(live_dir)
        if browser_mode == "visible" and login_mode_child:
            time.sleep(2.0)
            _show_scraper_windows_once(
                root,
                login_mode=True,
                user_data_dir=child_env.get("F061_BBP_USER_DATA_DIR", ""),
                profile_dir=child_env.get("F061_BBP_PROFILE_DIR", ""),
            )
        while proc.poll() is None:
            now = _utc_now_iso()
            try:
                current_output_size = (
                    (scanner_stdout.stat().st_size if scanner_stdout.exists() else 0)
                    + (scanner_stderr.stat().st_size if scanner_stderr.exists() else 0)
                )
            except OSError:
                current_output_size = last_output_size
            if current_output_size > last_output_size:
                last_output_size = current_output_size
                last_output_monotonic = time.monotonic()
                last_output_utc = now
            browser_visibility_state = _update_child_auth_visibility_from_logs(
                root=root,
                live_dir=live_dir,
                stdout_path=scanner_stdout,
                stderr_path=scanner_stderr,
                stdout_start_offset=stdout_start_offset,
                stderr_start_offset=stderr_start_offset,
                current_state=browser_visibility_state,
                allow_visible_auth_required=_auto_visible_auth_attention_enabled() or browser_mode == "visible",
                login_mode=normalize_text(child_env.get("F061_LOGIN_MODE", "")) == "1",
            )
            auth_state = _saved_auth_state(live_dir)
            manager_mode = _manager_mode_for_child(
                auth_state=auth_state,
                browser_mode=browser_mode,
                browser_visibility_state=browser_visibility_state,
                login_mode_child=login_mode_child,
            )
            _write_manager_mode_state(
                live_dir,
                mode=manager_mode,
                auth_state=auth_state,
                browser_mode=browser_mode,
                browser_visibility_state=browser_visibility_state,
                child_pid=proc.pid,
                supplier_id=supplier_id,
                f061_run_id=normalize_text(_active_f061_state(root).get("run_id", "")),
                notes=f"last_output_utc={last_output_utc}",
                observed_utc=now,
            )
            _refresh_lock(lock_path, started_utc=scanner_started_utc, heartbeat_utc=now)
            (live_dir / "f061_child_status.txt").write_text(
                (
                    f"pid={proc.pid}|supplier_id={supplier_id}|chunk_rows={chunk_rows}|"
                    f"browser_mode={browser_mode}|browser_visibility={browser_visibility_state}|"
                    f"manager_mode={manager_mode}|started={scanner_started_utc}|heartbeat={now}|"
                    f"last_output_utc={last_output_utc}\n"
                ),
                encoding="utf-8",
                newline="\n",
            )
            elapsed_seconds = time.monotonic() - scanner_started_monotonic
            output_idle_seconds = time.monotonic() - last_output_monotonic
            if (
                browser_mode == "visible"
                and login_mode_child
                and elapsed_seconds >= 15.0
                and not _login_mode_window_already_shown(live_dir)
            ):
                surfaced = _show_scraper_windows_once(
                    root,
                    login_mode=True,
                    user_data_dir=child_env.get("F061_BBP_USER_DATA_DIR", ""),
                    profile_dir=child_env.get("F061_BBP_PROFILE_DIR", ""),
                )
                if surfaced:
                    _mark_login_mode_window_shown(live_dir)
            visible_login_hold = (
                browser_mode == "visible"
                and login_mode_child
                and _saved_auth_state(live_dir) in AUTH_STATES_REQUIRING_VISIBLE
            )
            if child_stall_seconds > 0 and not visible_login_hold and output_idle_seconds >= child_stall_seconds:
                stalled = True
                stdout_fh.write(
                    f"[{now}] stalled F061 pid={proc.pid} "
                    f"output_idle_seconds={output_idle_seconds:.1f} stall_seconds={child_stall_seconds:.1f}\n"
                )
                stdout_fh.flush()
                auth_state = _saved_auth_state(live_dir)
                _write_manager_mode_state(
                    live_dir,
                    mode="Restarting Scanner",
                    auth_state=auth_state,
                    browser_mode=browser_mode,
                    browser_visibility_state=browser_visibility_state,
                    child_pid=proc.pid,
                    supplier_id=supplier_id,
                    f061_run_id=normalize_text(_active_f061_state(root).get("run_id", "")),
                    notes=f"f061_child_stall_seconds={child_stall_seconds:.1f};last_output_utc={last_output_utc}",
                    observed_utc=now,
                )
                (live_dir / "f061_child_status.txt").write_text(
                    (
                        f"pid={proc.pid}|supplier_id={supplier_id}|chunk_rows={chunk_rows}|"
                        f"browser_mode={browser_mode}|browser_visibility={browser_visibility_state}|"
                        f"manager_mode=Restarting Scanner|started={scanner_started_utc}|heartbeat={now}|"
                        f"last_output_utc={last_output_utc}|status=stalled\n"
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                _terminate_process_tree(proc)
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                break
            if child_timeout_seconds > 0 and elapsed_seconds >= child_timeout_seconds:
                timed_out = True
                stdout_fh.write(
                    f"[{now}] timed out F061 pid={proc.pid} "
                    f"elapsed_seconds={elapsed_seconds:.1f} timeout_seconds={child_timeout_seconds:.1f}\n"
                )
                stdout_fh.flush()
                (live_dir / "f061_child_status.txt").write_text(
                    (
                        f"pid={proc.pid}|supplier_id={supplier_id}|chunk_rows={chunk_rows}|"
                        f"browser_mode={browser_mode}|manager_mode=Restarting Scanner|"
                        f"started={scanner_started_utc}|heartbeat={now}|last_output_utc={last_output_utc}|"
                        "status=timed_out\n"
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                _terminate_process_tree(proc)
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                break
            time.sleep(2)
        rc = int(proc.returncode or 0)
        finished_utc = _utc_now_iso()
        elapsed_seconds = time.monotonic() - scanner_started_monotonic
        _refresh_lock(lock_path, started_utc=scanner_started_utc, heartbeat_utc=finished_utc)
        stdout_fh.write(f"[{finished_utc}] finished F061 rc={rc} elapsed_seconds={elapsed_seconds:.1f}\n")
        stdout_fh.flush()

    stderr_tail = ""
    try:
        stderr_tail = scanner_stderr.read_text(encoding="utf-8", errors="replace")[-500:]
    except Exception:
        stderr_tail = ""
    if timed_out:
        return {
            "status": "failed",
            "processed_rows": 0,
            "pending_rows": _active_f061_state(root).get("pending_rows", 0),
            "notes": f"f061_child_timeout_seconds={child_timeout_seconds:.1f};pid={proc.pid}",
        }
    if stalled:
        return {
            "status": "failed",
            "processed_rows": 0,
            "pending_rows": _active_f061_state(root).get("pending_rows", 0),
            "notes": (
                f"f061_child_stall_seconds={child_stall_seconds:.1f};"
                f"pid={proc.pid};last_output_utc={last_output_utc}"
            ),
        }
    if rc != 0:
        return {
            "status": "failed",
            "processed_rows": 0,
            "pending_rows": _active_f061_state(root).get("pending_rows", 0),
            "notes": f"f061_rc={rc};stderr_tail={stderr_tail}",
        }
    child_summary = _parse_latest_child_summary(scanner_stdout, start_offset=stdout_start_offset)
    if child_summary:
        child_summary["notes"] = "f061_subprocess_completed"
        return child_summary
    return {
        "status": "success",
        "processed_rows": chunk_rows,
        "pending_rows": _active_f061_state(root).get("pending_rows", 0),
        "notes": "f061_subprocess_completed",
    }


def run_live_cycle_once(
    root: Path | None = None,
    *,
    chunk_rows: int = 50,
    apply_next: bool = False,
    auto_approve_next: bool = False,
    refresh_before_select: bool = True,
    scanner_func: ScannerFunc | None = None,
    observed_utc: str | None = None,
    cycle_run_id: str | None = None,
) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    root_path = paths.root
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    observed = observed_utc or _utc_now_iso()
    run_id = cycle_run_id or f"fpm_live_{observed.replace('-', '').replace(':', '')}"
    chunk = max(int(chunk_rows), 1)

    if _maintenance_requested(root_path):
        exit_after_drain = _maintenance_exit_after_drain(root_path)
        _write_drain_ready(live_dir)
        active = _active_f061_state(root_path)
        state = "drain_exit" if exit_after_drain else "drain_wait"
        notes = "maintenance_requested_exit_after_drain" if exit_after_drain else "maintenance_requested_boundary_wait"
        _write_status(
            live_dir=live_dir,
            observed_utc=observed,
            run_id=run_id,
            state=state,
            active_supplier_id=normalize_text(active.get("supplier_id", "")),
            active_f061_run_id=normalize_text(active.get("run_id", "")),
            pending_rows=int(active.get("pending_rows", 0) or 0),
            last_action="restart_drain",
            last_action_status="ready",
            chunk_rows=chunk,
            drain_ready=True,
            notes=notes,
        )
        _append_event(
            live_dir=live_dir,
            event_utc=observed,
            cycle_run_id=run_id,
            event_type="restart_drain_ready",
            status="ready",
            notes=notes,
        )
        return {"status": state, "pending_rows": int(active.get("pending_rows", 0) or 0)}
    _clear_drain_ready(live_dir)

    _promote_completed_login_backtrack_rows(
        root=root_path,
        live_dir=live_dir,
        observed_utc=observed,
        cycle_run_id=run_id,
    )
    active = _active_f061_state(root_path)
    supplier_id = normalize_text(active.get("supplier_id", ""))
    f061_run_id = normalize_text(active.get("run_id", ""))
    pending_rows = int(active.get("pending_rows", 0) or 0)
    if supplier_id and pending_rows > 0:
        shape_guard = _active_source_shape_guard(
            root=root_path,
            live_dir=live_dir,
            observed_utc=observed,
            cycle_run_id=run_id,
            supplier_id=supplier_id,
            f061_run_id=f061_run_id,
            pending_rows=pending_rows,
            chunk_rows=chunk,
        )
        if normalize_text(shape_guard.get("status", "")) != "ok":
            return shape_guard
        regression = _state_regression_guard(
            live_dir=live_dir,
            observed_utc=observed,
            cycle_run_id=run_id,
            supplier_id=supplier_id,
            f061_run_id=f061_run_id,
            pending_rows=pending_rows,
            chunk_rows=chunk,
        )
        if normalize_text(regression.get("status", "")) != "ok":
            return regression
        active_rows = read_f_contract_df(root_path, "supplier_price_list_active_run")
        login_request = _ensure_login_mode_request_for_active_backtrack(
            live_dir=live_dir,
            active=active_rows,
            observed_utc=observed,
        )
        login_mode_active = _login_mode_request_active(login_request)
        start_notes = "f061_child_started"
        if login_mode_active:
            start_notes = "f061_child_started;login_mode=1"
            _append_login_mode_child_started_event(
                live_dir=live_dir,
                event_utc=observed,
                cycle_run_id=run_id,
                supplier_id=supplier_id,
                f061_run_id=f061_run_id,
                rows=pending_rows,
                request=login_request,
            )
        _record_login_mode_request_health(
            live_dir=live_dir,
            observed_utc=observed,
            request=login_request,
            child_starting=login_mode_active,
            pending_rows=pending_rows,
        )
        _write_status(
            live_dir=live_dir,
            observed_utc=observed,
            run_id=run_id,
            state="running",
            active_supplier_id=supplier_id,
            active_f061_run_id=f061_run_id,
            pending_rows=pending_rows,
            last_action="resume_f061_active_run",
            last_action_status="scanner_running",
            chunk_rows=chunk,
            notes=start_notes,
        )
        runner = scanner_func or _run_scanner_subprocess
        scanner_summary = runner(root_path, supplier_id=supplier_id, chunk_rows=chunk)
        auth_attention_status = _record_auth_attention_after_chunk(
            live_dir=live_dir,
            event_utc=observed,
            cycle_run_id=run_id,
            scanner_summary=scanner_summary,
        )
        status = normalize_text(scanner_summary.get("status", ""))
        after = _active_f061_state(root_path)
        after_pending = int(after.get("pending_rows", 0) or 0)
        processed = _price_list_int(scanner_summary.get("processed_rows", "0"))
        if _scanner_summary_requires_login_wait(live_dir, scanner_summary):
            login_wait_notes = (
                f"{_saved_auth_state(live_dir).lower()}_waiting_for_operator;"
                f"{normalize_text(scanner_summary.get('notes', ''))}"
            )
            _write_status(
                live_dir=live_dir,
                observed_utc=observed,
                run_id=run_id,
                state="login_wait",
                active_supplier_id=supplier_id,
                active_f061_run_id=f061_run_id,
                pending_rows=after_pending,
                last_action="resume_f061_active_run",
                last_action_status="attention_needed",
                chunk_rows=chunk,
                notes=login_wait_notes,
            )
            _append_event(
                live_dir=live_dir,
                event_utc=observed,
                cycle_run_id=run_id,
                event_type="f061_login_wait",
                supplier_id=supplier_id,
                f061_run_id=f061_run_id,
                status="attention_needed",
                rows=0,
                notes=login_wait_notes,
            )
            return {
                "status": "login_wait",
                "action": "resume_f061_active_run",
                "supplier_id": supplier_id,
                "pending_before": pending_rows,
                "pending_after": after_pending,
                "processed_rows": processed,
                "auth_attention_status": auth_attention_status,
            }
        _write_status(
            live_dir=live_dir,
            observed_utc=observed,
            run_id=run_id,
            state="running" if after_pending > 0 else "idle",
            active_supplier_id=supplier_id,
            active_f061_run_id=f061_run_id,
            pending_rows=after_pending,
            last_action="resume_f061_active_run",
            last_action_status=status,
            chunk_rows=chunk,
            notes=normalize_text(scanner_summary.get("notes", "")),
        )
        _append_event(
            live_dir=live_dir,
            event_utc=observed,
            cycle_run_id=run_id,
            event_type="scanner_chunk",
            supplier_id=supplier_id,
            f061_run_id=f061_run_id,
            status=status,
            rows=processed,
            notes=f"pending_after={after_pending}",
        )
        memory_import_status = ""
        if status == "success":
            memory_summary = _import_f061_memory_after_chunk(
                root=root_path,
                live_dir=live_dir,
                event_utc=observed,
                cycle_run_id=run_id,
                supplier_id=supplier_id,
                f061_run_id=f061_run_id,
            )
            memory_import_status = normalize_text(memory_summary.get("status", ""))
            if memory_import_status == "blocked":
                status = "failed"
        review_pack_summary: dict[str, object] | None = None
        if after_pending <= 0 and status == "success":
            review_pack_summary = _build_completed_review_pack_if_ready(
                root=root_path,
                live_dir=live_dir,
                event_utc=observed,
                cycle_run_id=run_id,
                supplier_id=supplier_id,
                f061_run_id=f061_run_id,
            )
        return {
            "status": status,
            "action": "resume_f061_active_run",
            "supplier_id": supplier_id,
            "pending_before": pending_rows,
            "pending_after": after_pending,
            "processed_rows": processed,
            "auth_attention_status": auth_attention_status,
            "memory_import_status": memory_import_status,
            "review_pack_status": normalize_text((review_pack_summary or {}).get("status", "")),
        }

    if refresh_before_select:
        _refresh_manager_outputs(root_path, observed)
    stage = stage_f061_handoff(root=root_path, built_at_utc=observed)
    preview = _latest_handoff_preview(paths.test_mode_dir)
    selected_supplier = normalize_text(stage.get("supplier_id", ""))
    selected_batch = normalize_text(stage.get("batch_id", ""))

    if not apply_next:
        _record_login_mode_request_health(
            live_dir=live_dir,
            observed_utc=observed,
            request=_read_login_mode_request(live_dir),
            child_starting=False,
            pending_rows=0,
        )
        _write_status(
            live_dir=live_dir,
            observed_utc=observed,
            run_id=run_id,
            state="idle",
            active_supplier_id=selected_supplier,
            pending_rows=0,
            last_action="stage_next_batch",
            last_action_status="preview_only",
            chunk_rows=chunk,
            notes=normalize_text(stage.get("block_reason", "")),
        )
        return {"status": "preview_only", "action": "stage_next_batch", "supplier_id": selected_supplier}

    if auto_approve_next and selected_supplier and selected_batch:
        set_f061_handoff_approval(
            supplier_id=selected_supplier,
            batch_id=selected_batch,
            approval_state="approved",
            approved_by="FPM130_live_cycle",
            reason="live_cycle_auto_approve_exact_selected_batch",
            root=root_path,
            approved_at_utc=observed,
        )
        stage = stage_f061_handoff(root=root_path, built_at_utc=observed)
        preview = _latest_handoff_preview(paths.test_mode_dir)

    apply = apply_f061_handoff(
        root=root_path,
        built_at_utc=observed,
        apply_live=True,
        confirm_approved_handoff=True,
    )
    if normalize_text(apply.get("status", "")) != "applied":
        notes = normalize_text(apply.get("block_reason", ""))
        no_scan_ready = not selected_supplier and not selected_batch
        state = "idle" if no_scan_ready else "blocked"
        action_status = "no_scan_ready" if no_scan_ready else "blocked"
        if no_scan_ready:
            notes = normalize_text(stage.get("block_reason", "")) or notes or "no_scan_ready"
        _record_login_mode_request_health(
            live_dir=live_dir,
            observed_utc=observed,
            request=_read_login_mode_request(live_dir),
            child_starting=False,
            pending_rows=0,
        )
        _write_status(
            live_dir=live_dir,
            observed_utc=observed,
            run_id=run_id,
            state=state,
            active_supplier_id=selected_supplier,
            pending_rows=0,
            last_action="apply_next_batch",
            last_action_status=action_status,
            chunk_rows=chunk,
            notes=notes,
        )
        _append_event(
            live_dir=live_dir,
            event_utc=observed,
            cycle_run_id=run_id,
            event_type="apply_next_batch",
            supplier_id=selected_supplier,
            f061_run_id=normalize_text(preview.get("run_id", "")) if preview is not None else "",
            status=action_status,
            rows=_price_list_int(stage.get("staged_rows", "0")),
            notes=notes,
        )
        return {
            "status": action_status,
            "action": "apply_next_batch",
            "supplier_id": selected_supplier,
            "notes": notes,
        }

    active_after_apply = _active_f061_state(root_path)
    supplier_after_apply = normalize_text(active_after_apply.get("supplier_id", ""))
    f061_run_after_apply = normalize_text(active_after_apply.get("run_id", ""))
    if not supplier_after_apply:
        _record_login_mode_request_health(
            live_dir=live_dir,
            observed_utc=observed,
            request=_read_login_mode_request(live_dir),
            child_starting=False,
            pending_rows=0,
        )
        _write_status(
            live_dir=live_dir,
            observed_utc=observed,
            run_id=run_id,
            state="idle",
            active_supplier_id=selected_supplier,
            active_f061_run_id=normalize_text(preview.get("run_id", "")) if preview is not None else "",
            pending_rows=0,
            last_action="apply_next_batch",
            last_action_status="applied_no_pending",
            chunk_rows=chunk,
            notes="no_active_rows_after_apply",
        )
        return {"status": "applied_no_pending", "action": "apply_next_batch", "supplier_id": selected_supplier}
    shape_guard = _active_source_shape_guard(
        root=root_path,
        live_dir=live_dir,
        observed_utc=observed,
        cycle_run_id=run_id,
        supplier_id=supplier_after_apply,
        f061_run_id=f061_run_after_apply,
        pending_rows=int(active_after_apply.get("pending_rows", 0) or 0),
        chunk_rows=chunk,
    )
    if normalize_text(shape_guard.get("status", "")) != "ok":
        return shape_guard
    regression = _state_regression_guard(
        live_dir=live_dir,
        observed_utc=observed,
        cycle_run_id=run_id,
        supplier_id=supplier_after_apply,
        f061_run_id=f061_run_after_apply,
        pending_rows=int(active_after_apply.get("pending_rows", 0) or 0),
        chunk_rows=chunk,
    )
    if normalize_text(regression.get("status", "")) != "ok":
        return regression
    active_rows = read_f_contract_df(root_path, "supplier_price_list_active_run")
    login_request = _ensure_login_mode_request_for_active_backtrack(
        live_dir=live_dir,
        active=active_rows,
        observed_utc=observed,
    )
    login_mode_active = _login_mode_request_active(login_request)
    start_notes = "f061_child_started"
    if login_mode_active:
        start_notes = "f061_child_started;login_mode=1"
        _append_login_mode_child_started_event(
            live_dir=live_dir,
            event_utc=observed,
            cycle_run_id=run_id,
            supplier_id=supplier_after_apply,
            f061_run_id=f061_run_after_apply,
            rows=int(active_after_apply.get("pending_rows", 0) or 0),
            request=login_request,
        )
    _record_login_mode_request_health(
        live_dir=live_dir,
        observed_utc=observed,
        request=login_request,
        child_starting=login_mode_active,
        pending_rows=int(active_after_apply.get("pending_rows", 0) or 0),
    )
    _write_status(
        live_dir=live_dir,
        observed_utc=observed,
        run_id=run_id,
        state="running",
        active_supplier_id=supplier_after_apply,
        active_f061_run_id=f061_run_after_apply,
        pending_rows=int(active_after_apply.get("pending_rows", 0) or 0),
        last_action="apply_and_scan_next_batch",
        last_action_status="scanner_running",
        chunk_rows=chunk,
        notes=start_notes,
    )
    runner = scanner_func or _run_scanner_subprocess
    scanner_summary = runner(root_path, supplier_id=supplier_after_apply, chunk_rows=chunk)
    auth_attention_status = _record_auth_attention_after_chunk(
        live_dir=live_dir,
        event_utc=observed,
        cycle_run_id=run_id,
        scanner_summary=scanner_summary,
    )
    after = _active_f061_state(root_path)
    after_pending = int(after.get("pending_rows", 0) or 0)
    processed = _price_list_int(scanner_summary.get("processed_rows", "0"))
    if _scanner_summary_requires_login_wait(live_dir, scanner_summary):
        login_wait_notes = (
            f"{_saved_auth_state(live_dir).lower()}_waiting_for_operator;"
            f"{normalize_text(scanner_summary.get('notes', ''))}"
        )
        _write_status(
            live_dir=live_dir,
            observed_utc=observed,
            run_id=run_id,
            state="login_wait",
            active_supplier_id=supplier_after_apply,
            active_f061_run_id=f061_run_after_apply,
            pending_rows=after_pending,
            last_action="apply_and_scan_next_batch",
            last_action_status="attention_needed",
            chunk_rows=chunk,
            notes=login_wait_notes,
        )
        _append_event(
            live_dir=live_dir,
            event_utc=observed,
            cycle_run_id=run_id,
            event_type="f061_login_wait",
            supplier_id=supplier_after_apply,
            f061_run_id=f061_run_after_apply,
            status="attention_needed",
            rows=0,
            notes=login_wait_notes,
        )
        return {
            "status": "login_wait",
            "action": "apply_and_scan_next_batch",
            "supplier_id": supplier_after_apply,
            "pending_after": after_pending,
            "processed_rows": processed,
            "auth_attention_status": auth_attention_status,
        }
    _write_status(
        live_dir=live_dir,
        observed_utc=observed,
        run_id=run_id,
        state="running" if after_pending > 0 else "idle",
        active_supplier_id=supplier_after_apply,
        active_f061_run_id=f061_run_after_apply,
        pending_rows=after_pending,
        last_action="apply_and_scan_next_batch",
        last_action_status=normalize_text(scanner_summary.get("status", "")),
        chunk_rows=chunk,
        notes=normalize_text(scanner_summary.get("notes", "")),
    )
    _append_event(
        live_dir=live_dir,
        event_utc=observed,
        cycle_run_id=run_id,
        event_type="apply_and_scan_next_batch",
        supplier_id=supplier_after_apply,
        f061_run_id=f061_run_after_apply,
        status=normalize_text(scanner_summary.get("status", "")),
        rows=processed,
        notes=f"pending_after={after_pending}",
    )
    memory_import_status = ""
    scanner_status = normalize_text(scanner_summary.get("status", ""))
    if scanner_status == "success":
        memory_summary = _import_f061_memory_after_chunk(
            root=root_path,
            live_dir=live_dir,
            event_utc=observed,
            cycle_run_id=run_id,
            supplier_id=supplier_after_apply,
            f061_run_id=f061_run_after_apply,
        )
        memory_import_status = normalize_text(memory_summary.get("status", ""))
        if memory_import_status == "blocked":
            scanner_status = "failed"
    review_pack_summary = None
    if after_pending <= 0 and scanner_status == "success":
        review_pack_summary = _build_completed_review_pack_if_ready(
            root=root_path,
            live_dir=live_dir,
            event_utc=observed,
            cycle_run_id=run_id,
            supplier_id=supplier_after_apply,
            f061_run_id=f061_run_after_apply,
        )
    return {
        "status": scanner_status,
        "action": "apply_and_scan_next_batch",
        "supplier_id": supplier_after_apply,
        "pending_after": after_pending,
        "processed_rows": processed,
        "auth_attention_status": auth_attention_status,
        "memory_import_status": memory_import_status,
        "review_pack_status": normalize_text((review_pack_summary or {}).get("status", "")),
    }


def run_live_cycle(
    root: Path | None = None,
    *,
    chunk_rows: int = 50,
    apply_next: bool = False,
    auto_approve_next: bool = False,
    refresh_before_select: bool = True,
    run_once: bool = False,
    sleep_seconds: float = 10.0,
) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    root_path = paths.root
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    lock_path = live_dir / "live_cycle.lock"
    started = _utc_now_iso()
    acquired, reason = _acquire_lock(lock_path, stale_archive_dir=live_dir / "lock_archive", heartbeat_utc=started)
    if not acquired:
        _write_status(
            live_dir=live_dir,
            observed_utc=started,
            run_id=f"fpm_live_{started.replace('-', '').replace(':', '')}",
            state="already_running",
            last_action="acquire_lock",
            last_action_status="blocked",
            chunk_rows=chunk_rows,
            notes=reason,
        )
        return {"status": "already_running", "notes": reason}
    cycle_run_id = f"fpm_live_{started.replace('-', '').replace(':', '')}"
    try:
        while True:
            now = _utc_now_iso()
            _refresh_lock(lock_path, started_utc=started, heartbeat_utc=now)
            _write_manager_mode_state(
                live_dir,
                mode="Idle",
                auth_state=_saved_auth_state(live_dir),
                browser_mode="minimized",
                browser_visibility_state="hidden",
                notes="manager_heartbeat",
                observed_utc=now,
            )
            summary = run_live_cycle_once(
                root=root_path,
                chunk_rows=chunk_rows,
                apply_next=apply_next,
                auto_approve_next=auto_approve_next,
                refresh_before_select=refresh_before_select,
                observed_utc=now,
                cycle_run_id=cycle_run_id,
            )
            if run_once:
                return summary
            summary_status = normalize_text(summary.get("status", ""))
            if summary_status in {"drain_exit", "login_wait"}:
                return summary
            time.sleep(_live_loop_sleep_seconds(summary_status, sleep_seconds))
    finally:
        _release_lock(lock_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live owner for the F price-list manager and F061 scanner handoff.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--chunk-rows", type=int, default=int(os.environ.get("FPM_LIVE_CHUNK_ROWS", "50")))
    parser.add_argument("--sleep-seconds", type=float, default=float(os.environ.get("FPM_LIVE_SLEEP_SECONDS", "10")))
    parser.add_argument("--run-once", action="store_true")
    parser.add_argument("--apply-next", action="store_true")
    parser.add_argument("--auto-approve-next", action="store_true")
    parser.add_argument("--skip-refresh-before-select", action="store_true")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    summary = run_live_cycle(
        root=root,
        chunk_rows=args.chunk_rows,
        apply_next=bool(args.apply_next),
        auto_approve_next=bool(args.auto_approve_next),
        refresh_before_select=not bool(args.skip_refresh_before_select),
        run_once=bool(args.run_once),
        sleep_seconds=args.sleep_seconds,
    )
    print(summary)


if __name__ == "__main__":
    main()
