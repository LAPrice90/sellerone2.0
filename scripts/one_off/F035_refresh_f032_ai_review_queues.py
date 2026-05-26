from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM155_apply_review_intelligence_gate import apply_review_intelligence_gate
from scripts.flows.F.price_list_manager.FPM156_build_ai_gate_quality_report import build_ai_gate_quality_report
from scripts.flows.F.price_list_manager.FPM157_build_incremental_ai_precheck import build_incremental_ai_precheck
from scripts.flows.F.price_list_manager.FPM158_ai_precheck_common import ai_precheck_root
from scripts.flows.F.price_list_manager._io import normalize_text
from scripts.flows.F.price_list_manager._paths import get_manager_paths


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _candidate_manifests(root: Path) -> list[Path]:
    paths = get_manager_paths(root=root)
    handoff_root = paths.system_dir / "review_handoffs"
    if not handoff_root.exists():
        return []
    return sorted(handoff_root.glob("*/*/candidate_manifest.csv"))


def _read_csv_safely(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _pending_after_from_notes(notes: object) -> str:
    match = re.search(r"(?:^|[;|,\s])pending_after=(\d+)", normalize_text(notes))
    return match.group(1) if match else ""


def _int_value(value: object) -> int:
    raw = normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _truthy_env(name: str, *, default: bool) -> bool:
    raw = normalize_text(os.environ.get(name, "")).lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on"}


def _first_present(row: pd.Series, names: list[str]) -> str:
    for name in names:
        if name in row.index:
            value = normalize_text(row.get(name, ""))
            if value:
                return value
    return ""


def _parse_state_line(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except Exception:
        return {}
    out: dict[str, str] = {}
    for part in [item.strip() for item in normalize_text(text).split("|") if item.strip()]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[normalize_text(key)] = normalize_text(value)
    return out


def _upstream_throughput_summary(root: Path) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    live_dir = paths.system_dir / "live"
    status_df = _read_csv_safely(live_dir / "live_cycle_status.csv")
    events_df = _read_csv_safely(live_dir / "live_cycle_events.csv")
    handoff_df = _read_csv_safely(live_dir / "review_handoff_manifest.csv")

    latest_status = status_df.iloc[-1] if not status_df.empty else pd.Series(dtype=str)
    state = _first_present(latest_status, ["state"])
    upstream_status = "unknown"
    if state:
        upstream_status = "blocked" if state.startswith("blocked") else "ok"

    scanner_events = pd.DataFrame()
    if not events_df.empty and "event_type" in events_df.columns:
        scanner_events = events_df[events_df["event_type"].map(normalize_text) == "scanner_chunk"].copy()
    latest_scanner = scanner_events.iloc[-1] if not scanner_events.empty else pd.Series(dtype=str)
    if upstream_status == "unknown" and not latest_scanner.empty:
        upstream_status = "ok"

    latest_handoff = handoff_df.iloc[-1] if not handoff_df.empty else pd.Series(dtype=str)
    child_status = _parse_state_line(live_dir / "f061_child_status.txt")
    live_supplier = (
        _first_present(latest_status, ["active_supplier_id"])
        or normalize_text(child_status.get("supplier_id", ""))
        or _first_present(latest_scanner, ["supplier_id"])
    )
    live_run = (
        _first_present(latest_status, ["active_f061_run_id"])
        or _first_present(latest_scanner, ["f061_run_id"])
    )
    return {
        "upstream_status": upstream_status,
        "live_cycle_state": state,
        "live_cycle_observed_utc": _first_present(latest_status, ["observed_utc"]),
        "live_cycle_last_action": _first_present(latest_status, ["last_action"]),
        "live_cycle_last_action_status": _first_present(latest_status, ["last_action_status"]),
        "live_cycle_pending_rows": _first_present(latest_status, ["pending_rows"]),
        "live_cycle_active_supplier_id": live_supplier,
        "live_cycle_active_f061_run_id": live_run,
        "latest_scanner_chunk_utc": _first_present(latest_scanner, ["event_utc"]),
        "latest_scanner_chunk_supplier_id": _first_present(latest_scanner, ["supplier_id"]),
        "latest_scanner_chunk_run_id": _first_present(latest_scanner, ["f061_run_id"]),
        "latest_scanner_chunk_pending_after": _pending_after_from_notes(_first_present(latest_scanner, ["notes"])),
        "current_live_handoff_supplier_id": _first_present(
            latest_handoff,
            ["supplier_id", "active_supplier_id"],
        ),
        "current_live_handoff_run_id": _first_present(
            latest_handoff,
            ["run_id", "active_run_id", "f061_run_id"],
        ),
        "current_live_handoff_built_at_utc": _first_present(
            latest_handoff,
            ["built_at_utc", "observed_utc", "completed_at_utc"],
        ),
    }


def _refresh_active_precheck_if_enabled(root: Path, observed_utc: str, upstream_summary: dict[str, object]) -> dict[str, object]:
    if not _truthy_env("FPM_INCREMENTAL_AI_PRECHECK_DAILY_CATCHUP", default=True):
        return {"status": "skipped", "notes": "daily_catchup_disabled"}
    supplier_id = normalize_text(upstream_summary.get("live_cycle_active_supplier_id", ""))
    run_id = normalize_text(upstream_summary.get("live_cycle_active_f061_run_id", ""))
    if not supplier_id or not run_id:
        return {"status": "skipped", "notes": "active_supplier_or_run_missing"}
    try:
        return build_incremental_ai_precheck(
            root=root,
            supplier_id=supplier_id,
            run_id=run_id,
            observed_utc=observed_utc,
            emit_json=False,
        )
    except Exception as exc:
        return {
            "status": "warn",
            "supplier_id": supplier_id,
            "run_id": run_id,
            "notes": f"precheck_daily_catchup_failed={type(exc).__name__}:{normalize_text(exc)}",
        }


def _precheck_rollup(root: Path) -> dict[str, object]:
    root_dir = ai_precheck_root(root)
    status_paths = sorted(root_dir.glob("*/*/ai_precheck_status.csv")) if root_dir.exists() else []
    pending = 0
    decided = 0
    stale = 0
    reused = 0
    queue_rows = 0
    latest_status = ""
    latest_supplier = ""
    latest_run = ""
    latest_observed = ""
    for status_path in status_paths:
        df = _read_csv_safely(status_path)
        if df.empty:
            continue
        row = df.iloc[-1]
        pending += _int_value(row.get("pending_ai_decision_rows", "0"))
        decided += _int_value(row.get("decided_rows", "0"))
        stale += _int_value(row.get("stale_decision_rows", "0"))
        reused += _int_value(row.get("reused_in_final_rows", "0"))
        queue_rows += _int_value(row.get("ai_queue_rows", "0"))
        observed = normalize_text(row.get("observed_utc", ""))
        if observed >= latest_observed:
            latest_observed = observed
            latest_status = normalize_text(row.get("status", ""))
            latest_supplier = normalize_text(row.get("supplier_id", ""))
            latest_run = normalize_text(row.get("run_id", ""))
    return {
        "precheck_status_files": len(status_paths),
        "precheck_ai_queue_rows": queue_rows,
        "precheck_pending_ai_decision_rows": pending,
        "precheck_decided_rows": decided,
        "precheck_stale_decision_rows": stale,
        "precheck_reused_in_final_rows": reused,
        "latest_precheck_status": latest_status,
        "latest_precheck_supplier_id": latest_supplier,
        "latest_precheck_run_id": latest_run,
        "latest_precheck_observed_utc": latest_observed,
    }


def refresh_f032_ai_review_queues(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
    force_rebuild: bool = False,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else ROOT
    observed = observed_utc or _utc_now_iso()
    summaries: list[dict[str, object]] = []
    for candidate_manifest_path in _candidate_manifests(root_path):
        run_dir = candidate_manifest_path.parent
        supplier_id = normalize_text(run_dir.parent.name)
        run_id = normalize_text(run_dir.name)
        summary = apply_review_intelligence_gate(
            root=root_path,
            supplier_id=supplier_id,
            run_id=run_id,
            observed_utc=observed,
            force_rebuild=force_rebuild,
            emit_json=False,
        )
        summaries.append(summary)

    status_counts: dict[str, int] = {}
    for summary in summaries:
        status = normalize_text(summary.get("status", "")) or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    quality_summary = build_ai_gate_quality_report(root=root_path, observed_utc=observed)
    if normalize_text(quality_summary.get("status", "")) == "fail":
        status_counts["quality_failed"] = status_counts.get("quality_failed", 0) + 1

    upstream_summary = _upstream_throughput_summary(root_path)
    precheck_catchup_summary = _refresh_active_precheck_if_enabled(root_path, observed, upstream_summary)
    precheck_summary = _precheck_rollup(root_path)
    precheck_summary["catchup_status"] = normalize_text(precheck_catchup_summary.get("status", ""))
    precheck_summary["catchup_supplier_id"] = normalize_text(precheck_catchup_summary.get("supplier_id", ""))
    precheck_summary["catchup_run_id"] = normalize_text(precheck_catchup_summary.get("run_id", ""))
    precheck_summary["catchup_notes"] = normalize_text(precheck_catchup_summary.get("notes", ""))
    precheck_summary["final_handoff_pending_ai_decision_rows"] = sum(
        _int_value(summary.get("pending_decision_rows", "0"))
        for summary in summaries
        if normalize_text(summary.get("status", "")) == "pending_ai_decision"
    )
    if normalize_text(upstream_summary.get("upstream_status", "")) == "blocked":
        status_counts["upstream_blocked"] = status_counts.get("upstream_blocked", 0) + 1

    return {
        "observed_utc": observed,
        "candidate_manifest_count": len(summaries),
        "status_counts": status_counts,
        "quality_summary": quality_summary,
        "upstream_throughput_summary": upstream_summary,
        "precheck_summary": precheck_summary,
        "summaries": summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh F032 Codex AI review queues and finalize decided handoffs.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args()
    root = Path(args.root) if args.root else None
    report = refresh_f032_ai_review_queues(
        root=root,
        observed_utc=args.observed_utc,
        force_rebuild=bool(args.force_rebuild),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    failed = (
        int(report["status_counts"].get("failed", 0))
        + int(report["status_counts"].get("blocked", 0))
        + int(report["status_counts"].get("quality_failed", 0))
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
