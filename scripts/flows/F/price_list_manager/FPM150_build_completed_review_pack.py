from __future__ import annotations

import argparse
import json
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

from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F.price_list_manager.FPM140_check_review_handoff_ready import check_review_handoff_ready
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import (
    MANAGER_HEALTH_COLUMNS,
    REVIEW_CANDIDATE_MANIFEST_COLUMNS,
)
from scripts.one_off.F019_build_live_price_file_near_miss_pack import build_live_price_file_near_miss_pack


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _metric(summary_df: pd.DataFrame, metric: str) -> str:
    if summary_df.empty or "metric" not in summary_df.columns or "value" not in summary_df.columns:
        return "0"
    rows = summary_df[summary_df["metric"].map(normalize_text) == metric]
    if rows.empty:
        return "0"
    return normalize_text(rows.iloc[0].get("value", "")) or "0"


def _snapshot_id(summary_path: Path) -> str:
    stem = summary_path.stem
    prefix = "f_live_price_file_review_summary_"
    if stem.startswith(prefix):
        return stem[len(prefix) :]
    return stem


def _root_f_path(root: Path, contract_name: str) -> Path:
    return root / get_f_output_contract(contract_name).rel_path


def _handoff_dir(root: Path, *, supplier_id: str, run_id: str) -> Path:
    paths = get_manager_paths(root=root)
    safe_supplier = normalize_text(supplier_id).replace("/", "_").replace("\\", "_") or "unknown_supplier"
    safe_run = normalize_text(run_id).replace("/", "_").replace("\\", "_") or "unknown_run"
    return paths.system_dir / "review_handoffs" / safe_supplier / safe_run


def _write_build_health(
    *,
    live_dir: Path,
    observed_utc: str,
    status: str,
    value: str,
    notes: str,
    source_path: Path,
) -> None:
    write_csv(
        live_dir / "review_pack_build_health.csv",
        pd.DataFrame(
            [
                {
                    "check": "scanner_to_review_pack_build",
                    "status": status,
                    "value": value,
                    "notes": notes,
                    "observed_utc": observed_utc,
                    "source_path": str(source_path),
                }
            ]
        ),
        MANAGER_HEALTH_COLUMNS,
    )


def build_completed_review_pack(
    *,
    root: Path | None = None,
    supplier_id: str = "",
    run_id: str = "",
    observed_utc: str | None = None,
    force_rebuild: bool = False,
    emit_json: bool = True,
) -> dict[str, object]:
    paths = get_manager_paths(root=root)
    root_path = paths.root
    live_dir = paths.system_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    observed = observed_utc or _utc_now_iso()

    readiness = check_review_handoff_ready(
        root=root_path,
        supplier_id=supplier_id,
        run_id=run_id,
        observed_utc=observed,
        emit=emit_json,
    )
    ready = normalize_text(readiness.get("ready_to_publish_flag", "")) == "1"
    selected_supplier = normalize_text(readiness.get("supplier_id", ""))
    selected_run = normalize_text(readiness.get("run_id", ""))
    selected_dir = _handoff_dir(root_path, supplier_id=selected_supplier, run_id=selected_run)
    candidate_manifest_path = selected_dir / "candidate_manifest.csv"

    if not ready:
        state = normalize_text(readiness.get("handoff_state", "")) or "not_ready"
        block_reason = normalize_text(readiness.get("block_reason", ""))
        _write_build_health(
            live_dir=live_dir,
            observed_utc=observed,
            status="ok" if state == "not_ready" else "warn",
            value=state,
            notes=block_reason or "not_ready",
            source_path=live_dir / "review_handoff_status.csv",
        )
        summary = {
            "status": "blocked",
            "handoff_state": state,
            "supplier_id": selected_supplier,
            "run_id": selected_run,
            "ready_to_publish_flag": "0",
            "block_reason": block_reason,
            "manifest_path": "",
            "candidate_manifest_path": "",
            "notes": "review_pack_not_built",
        }
        if emit_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    if candidate_manifest_path.exists() and not force_rebuild:
        manifest = read_csv(candidate_manifest_path, REVIEW_CANDIDATE_MANIFEST_COLUMNS)
        row = manifest.iloc[0].to_dict() if not manifest.empty else {}
        _write_build_health(
            live_dir=live_dir,
            observed_utc=observed,
            status="ok",
            value="already_built",
            notes=f"supplier_id={selected_supplier};run_id={selected_run}",
            source_path=candidate_manifest_path,
        )
        summary = {
            "status": "already_built",
            "handoff_state": "ready",
            "supplier_id": selected_supplier,
            "run_id": selected_run,
            "ready_to_publish_flag": "1",
            "manifest_path": "",
            "candidate_manifest_path": str(candidate_manifest_path),
            "pass_review_rows": normalize_text(row.get("raw_pass_review_rows", "0")) or "0",
            "near_miss_review_rows": normalize_text(row.get("raw_near_miss_review_rows", "0")) or "0",
            "raw_pass_review_path": normalize_text(row.get("raw_pass_review_path", "")),
            "raw_near_miss_review_path": normalize_text(row.get("raw_near_miss_review_path", "")),
        }
        if emit_json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    selected_dir.mkdir(parents=True, exist_ok=True)
    result = build_live_price_file_near_miss_pack(
        baseline_path=root_path / "out" / "analysis_reports" / "f_live_price_file_launch_baseline_latest.csv",
        row_state_path=_root_f_path(root_path, "f_screening_row_state_live"),
        first_checks_path=_root_f_path(root_path, "feeder_legacy_first_checks_live"),
        scrape_evidence_path=_root_f_path(root_path, "feeder_legacy_scrape_evidence_live"),
        page_evidence_backfill_results_path=root_path
        / "out"
        / "systems"
        / "F"
        / "page_evidence_backfill"
        / "page_evidence_backfill_results.csv",
        backtest_summary_path=_root_f_path(root_path, "feeder_backtest_summary_live"),
        profit_audit_path=root_path / "out" / "analysis_reports" / "f_profit_formula_conflict_audit_latest.csv",
        review_events_path=_root_f_path(root_path, "feeder_review_events"),
        output_dir=selected_dir,
        observed_utc=observed,
        active_supplier_id=selected_supplier,
        active_run_id=selected_run,
        source_seen_at_utc_override=normalize_text(readiness.get("source_seen_at_utc", "")),
    )

    review_snapshot = _snapshot_id(result.summary_path)
    pass_rows = str(len(result.pass_df.index))
    near_miss_rows = str(len(result.near_miss_df.index))
    hard_reject_rows = _metric(result.summary_df, "hard_reject_rows")
    manifest_row = {
        "built_at_utc": observed,
        "supplier_id": selected_supplier,
        "supplier_name": normalize_text(readiness.get("supplier_name", "")),
        "run_id": selected_run,
        "review_snapshot_id": review_snapshot,
        "source_file_path": normalize_text(readiness.get("source_file_path", "")),
        "source_seen_at_utc": normalize_text(readiness.get("source_seen_at_utc", "")),
        "completed_at_utc": normalize_text(readiness.get("completed_at_utc", "")),
        "raw_pass_review_rows": pass_rows,
        "raw_near_miss_review_rows": near_miss_rows,
        "hard_reject_rows": hard_reject_rows,
        "raw_pass_review_path": str(result.pass_path),
        "raw_near_miss_review_path": str(result.near_miss_path),
        "raw_summary_path": str(result.summary_path),
        "handoff_dir": str(selected_dir),
        "operator_ready_flag": "0",
        "block_reason": "",
        "notes": "raw_candidate_review_pack_built",
    }
    write_csv(candidate_manifest_path, pd.DataFrame([manifest_row]), REVIEW_CANDIDATE_MANIFEST_COLUMNS)
    _write_build_health(
        live_dir=live_dir,
        observed_utc=observed,
        status="ok",
        value="raw_candidate_built",
        notes=f"pass_review_rows={pass_rows};near_miss_review_rows={near_miss_rows};hard_reject_rows={hard_reject_rows}",
        source_path=candidate_manifest_path,
    )

    summary = {
        "status": "built",
        "handoff_state": "ready",
        "supplier_id": selected_supplier,
        "run_id": selected_run,
        "ready_to_publish_flag": "1",
        "manifest_path": "",
        "candidate_manifest_path": str(candidate_manifest_path),
        "pass_review_rows": pass_rows,
        "near_miss_review_rows": near_miss_rows,
        "hard_reject_rows": hard_reject_rows,
        "operator_ready_flag": "0",
        "raw_pass_review_path": str(result.pass_path),
        "raw_near_miss_review_path": str(result.near_miss_path),
    }
    if emit_json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a New Product Review pack for a completed F061 supplier run.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_completed_review_pack(
        root=root,
        supplier_id=args.supplier_id,
        run_id=args.run_id,
        observed_utc=args.observed_utc,
        force_rebuild=bool(args.force_rebuild),
    )


if __name__ == "__main__":
    main()
