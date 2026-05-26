from __future__ import annotations

import argparse
import os
import subprocess
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
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, REVIEW_HANDOFF_STATUS_COLUMNS


EXPECTED_NOT_READY_REASONS = {
    "run_not_completed",
    "run_pending_rows_not_zero",
    "active_pending_rows_not_zero",
    "f061_child_active",
}
EXPECTED_SCAN_ACTIVE_EXTRA_REASONS = {
    "scanner_evidence_missing",
    "screening_pending_rows_not_zero",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_lower(value: object) -> str:
    return normalize_text(value).lower()


def _int_value(value: object) -> int:
    raw = normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


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


def _parts_from_status_line(line: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for part in [item.strip() for item in normalize_text(line).split("|") if item.strip()]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parts[normalize_text(key)] = normalize_text(value)
    return parts


def _read_first_line(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return normalize_text(lines[0]) if lines else ""
    except Exception:
        return ""


def _run_state_sort_value(row: pd.Series) -> str:
    return (
        normalize_text(row.get("updated_at_utc", ""))
        or normalize_text(row.get("completed_at_utc", ""))
        or normalize_text(row.get("normalized_utc", ""))
        or normalize_text(row.get("source_seen_at_utc", ""))
    )


def _select_run_state(run_state: pd.DataFrame, *, supplier_id: str = "", run_id: str = "") -> pd.Series | None:
    if run_state.empty:
        return None
    work = run_state.copy()
    supplier = _normalize_lower(supplier_id)
    run = _normalize_lower(run_id)
    if supplier:
        work = work[work["supplier_id"].map(_normalize_lower) == supplier].copy()
    if run:
        work = work[work["run_id"].map(_normalize_lower) == run].copy()
    if work.empty:
        return None

    work["_pending_rows_num"] = work["pending_rows"].map(_int_value)
    work["_active_rank"] = work.apply(
        lambda row: 1
        if _normalize_lower(row.get("run_status", "")) == "running" or _int_value(row.get("pending_rows", "")) > 0
        else 0,
        axis=1,
    )
    work["_sort_value"] = work.apply(_run_state_sort_value, axis=1)
    work = work.sort_values(["_active_rank", "_sort_value"], ascending=[False, False], kind="stable")
    return work.iloc[0]


def _filter_supplier_run(df: pd.DataFrame, *, supplier_id: str, run_id: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if supplier_id and "supplier_id" in out.columns:
        out = out[out["supplier_id"].map(_normalize_lower) == _normalize_lower(supplier_id)].copy()
    if run_id and "run_id" in out.columns:
        out = out[out["run_id"].map(_normalize_lower) == _normalize_lower(run_id)].copy()
    return out


def _live_cycle_state(live_status: pd.DataFrame, *, supplier_id: str) -> str:
    if live_status.empty:
        return ""
    row = live_status.iloc[-1]
    if supplier_id and _normalize_lower(row.get("active_supplier_id", "")) != _normalize_lower(supplier_id):
        return normalize_text(row.get("state", ""))
    return normalize_text(row.get("state", ""))


def _f061_child_active(live_dir: Path, *, supplier_id: str) -> bool:
    status_line = _read_first_line(live_dir / "f061_child_status.txt")
    if not status_line:
        return False
    parts = _parts_from_status_line(status_line)
    status_supplier = _normalize_lower(parts.get("supplier_id", ""))
    if supplier_id and status_supplier and status_supplier != _normalize_lower(supplier_id):
        return False
    try:
        pid = int(parts.get("pid", "0"))
    except ValueError:
        pid = None
    return _pid_alive(pid)


def _count_first_check_passes(first_checks: pd.DataFrame, candidate_ids: set[str]) -> int:
    if first_checks.empty or not candidate_ids or "candidate_id" not in first_checks.columns:
        return 0
    work = first_checks[first_checks["candidate_id"].map(normalize_text).isin(candidate_ids)].copy()
    if work.empty or "pf" not in work.columns:
        return 0
    return int((work["pf"].map(lambda value: normalize_text(value).upper()) == "PASS").sum())


def check_review_handoff_ready(
    *,
    root: Path | None = None,
    supplier_id: str = "",
    run_id: str = "",
    observed_utc: str | None = None,
    emit: bool = True,
) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    root_path = paths.root
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    observed = observed_utc or _utc_now_iso()

    run_state = read_f_contract_df(root_path, "supplier_price_list_run_state")
    active_run = read_f_contract_df(root_path, "supplier_price_list_active_run")
    screening = read_f_contract_df(root_path, "f_screening_row_state_live")
    first_checks = read_f_contract_df(root_path, "feeder_legacy_first_checks_live")
    scrape_evidence = read_f_contract_df(root_path, "feeder_legacy_scrape_evidence_live")
    live_status = read_csv(live_dir / "live_cycle_status.csv", ["observed_utc", "run_id", "owner_pid", "state", "active_supplier_id", "active_f061_run_id", "pending_rows", "last_action", "last_action_status", "chunk_rows", "drain_ready", "notes"])

    selected = _select_run_state(run_state, supplier_id=supplier_id, run_id=run_id)
    if selected is None:
        row = {
            "observed_utc": observed,
            "supplier_id": normalize_text(supplier_id),
            "supplier_name": "",
            "run_id": normalize_text(run_id),
            "handoff_state": "no_run_state",
            "ready_to_publish_flag": "0",
            "block_reason": "run_state_missing",
            "health_status": "warn",
            "run_status": "",
            "total_rows": "0",
            "pending_rows": "0",
            "done_rows": "0",
            "failed_rows": "0",
            "held_rows": "0",
            "active_pending_rows": "0",
            "active_run_rows": "0",
            "f061_child_active_flag": "0",
            "live_cycle_state": _live_cycle_state(live_status, supplier_id=supplier_id),
            "screening_rows": "0",
            "screening_completed_rows": "0",
            "screening_pending_rows": "0",
            "screening_login_backtrack_rows": "0",
            "screening_pass_rows": "0",
            "screening_timeout_rows": "0",
            "first_check_pass_rows": "0",
            "scrape_evidence_rows": "0",
            "completed_at_utc": "",
            "source_file_path": "",
            "source_seen_at_utc": "",
            "notes": "No supplier run state found for review handoff readiness check.",
        }
        status = write_csv(live_dir / "review_handoff_status.csv", pd.DataFrame([row]), REVIEW_HANDOFF_STATUS_COLUMNS)
        _write_health(live_dir, observed, status.iloc[0].to_dict())
        if emit:
            print(row)
        return row

    selected_supplier_id = normalize_text(selected.get("supplier_id", ""))
    selected_run_id = normalize_text(selected.get("run_id", ""))
    selected_supplier_name = normalize_text(selected.get("supplier_name", ""))
    selected_run_status = _normalize_lower(selected.get("run_status", ""))
    selected_pending_rows = _int_value(selected.get("pending_rows", ""))

    active_matching = _filter_supplier_run(active_run, supplier_id=selected_supplier_id, run_id=selected_run_id)
    active_statuses = active_matching["scan_status"].map(lambda value: normalize_text(value).lower())
    active_pending = active_matching[
        active_statuses.isin(["pending", "login_backtrack_pending", "login_backtrack_running"])
    ].copy()
    screening_matching = _filter_supplier_run(screening, supplier_id=selected_supplier_id, run_id=selected_run_id)
    scrape_matching = _filter_supplier_run(scrape_evidence, supplier_id=selected_supplier_id, run_id=selected_run_id)
    child_active = _f061_child_active(live_dir, supplier_id=selected_supplier_id)

    row_status = screening_matching["row_status"].map(_normalize_lower) if "row_status" in screening_matching.columns else pd.Series(dtype=str)
    screening_login_backtrack_rows = int(row_status.isin(["login_backtrack_pending", "login_backtrack_running"]).sum())
    screening_pending_rows = int(((row_status == "pending") | row_status.isin(["login_backtrack_pending", "login_backtrack_running"])).sum())
    screening_pass_rows = int((row_status == "pass").sum())
    screening_timeout_rows = int((row_status == "timeout").sum())
    screening_completed_rows = int((row_status.isin(["pass", "timeout"])).sum())
    candidate_ids = {
        normalize_text(value)
        for value in screening_matching.get("candidate_id", pd.Series(dtype=str)).tolist()
        if normalize_text(value)
    }

    block_reasons: list[str] = []
    if not selected_supplier_id:
        block_reasons.append("supplier_id_missing")
    if not selected_run_id:
        block_reasons.append("run_id_missing")
    if selected_run_status != "completed":
        block_reasons.append("run_not_completed")
    if selected_pending_rows != 0:
        block_reasons.append("run_pending_rows_not_zero")
    if selected_run_status == "completed" and not normalize_text(selected.get("completed_at_utc", "")):
        block_reasons.append("completed_at_missing")
    if len(active_pending.index) > 0:
        block_reasons.append("active_pending_rows_not_zero")
    if child_active:
        block_reasons.append("f061_child_active")
    if len(screening_matching.index) == 0:
        block_reasons.append("scanner_evidence_missing")
    if screening_pending_rows > 0:
        block_reasons.append("screening_pending_rows_not_zero")
    if screening_login_backtrack_rows > 0:
        block_reasons.append("login_backtrack_pending_rows_not_zero")

    ready = len(block_reasons) == 0
    active_not_ready_reasons = set(block_reasons).intersection(EXPECTED_NOT_READY_REASONS)
    expected_while_active = set(block_reasons).issubset(
        EXPECTED_NOT_READY_REASONS.union(EXPECTED_SCAN_ACTIVE_EXTRA_REASONS)
    )
    if ready:
        handoff_state = "ready"
    elif active_not_ready_reasons and expected_while_active:
        handoff_state = "not_ready"
    else:
        handoff_state = "blocked"
    health_status = "ok" if handoff_state in {"ready", "not_ready"} else "warn"
    block_reason = ";".join(block_reasons)

    row = {
        "observed_utc": observed,
        "supplier_id": selected_supplier_id,
        "supplier_name": selected_supplier_name,
        "run_id": selected_run_id,
        "handoff_state": handoff_state,
        "ready_to_publish_flag": "1" if ready else "0",
        "block_reason": block_reason,
        "health_status": health_status,
        "run_status": normalize_text(selected.get("run_status", "")),
        "total_rows": str(_int_value(selected.get("total_rows", ""))),
        "pending_rows": str(selected_pending_rows),
        "done_rows": str(_int_value(selected.get("done_rows", ""))),
        "failed_rows": str(_int_value(selected.get("failed_rows", ""))),
        "held_rows": str(_int_value(selected.get("held_rows", ""))),
        "active_pending_rows": str(int(len(active_pending.index))),
        "active_run_rows": str(int(len(active_matching.index))),
        "f061_child_active_flag": "1" if child_active else "0",
        "live_cycle_state": _live_cycle_state(live_status, supplier_id=selected_supplier_id),
        "screening_rows": str(int(len(screening_matching.index))),
        "screening_completed_rows": str(screening_completed_rows),
        "screening_pending_rows": str(screening_pending_rows),
        "screening_login_backtrack_rows": str(screening_login_backtrack_rows),
        "screening_pass_rows": str(screening_pass_rows),
        "screening_timeout_rows": str(screening_timeout_rows),
        "first_check_pass_rows": str(_count_first_check_passes(first_checks, candidate_ids)),
        "scrape_evidence_rows": str(int(len(scrape_matching.index))),
        "completed_at_utc": normalize_text(selected.get("completed_at_utc", "")),
        "source_file_path": normalize_text(selected.get("source_file_path", "")),
        "source_seen_at_utc": normalize_text(selected.get("source_seen_at_utc", "")),
        "notes": "read_only_check_no_review_pack_written",
    }
    status = write_csv(live_dir / "review_handoff_status.csv", pd.DataFrame([row]), REVIEW_HANDOFF_STATUS_COLUMNS)
    _write_health(live_dir, observed, status.iloc[0].to_dict())
    if emit:
        print(row)
    return row


def _write_health(live_dir: Path, observed_utc: str, status_row: dict[str, object]) -> None:
    health_path = live_dir / "review_handoff_health.csv"
    handoff_state = normalize_text(status_row.get("handoff_state", ""))
    block_reason = normalize_text(status_row.get("block_reason", ""))
    health_status = normalize_text(status_row.get("health_status", "warn")) or "warn"
    health_row = {
        "check": "scanner_to_review_handoff_ready",
        "status": health_status,
        "value": handoff_state,
        "notes": block_reason or "ready",
        "observed_utc": observed_utc,
        "source_path": str(live_dir / "review_handoff_status.csv"),
    }
    write_csv(health_path, pd.DataFrame([health_row]), MANAGER_HEALTH_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether a completed F061 supplier run is ready for New Product Review.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--observed-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    check_review_handoff_ready(
        root=root,
        supplier_id=args.supplier_id,
        run_id=args.run_id,
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
