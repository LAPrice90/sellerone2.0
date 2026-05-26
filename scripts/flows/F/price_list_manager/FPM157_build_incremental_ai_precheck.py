from __future__ import annotations

import argparse
import json
import os
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
from scripts.flows.F._review_intelligence import build_review_intelligence_cycle
from scripts.flows.F.price_list_manager.FPM155_apply_review_intelligence_gate import (
    AI_REVIEW_QUEUE_COLUMNS,
    CODEX_AI_DECISION_COLUMNS,
    STALE_CODEX_AI_DECISION_ARCHIVE_COLUMNS,
    VALID_CODEX_AI_ACTIONS,
    _archive_stale_codex_decisions,
    _build_ai_review_queue,
    _codex_decision_gaps,
    _load_codex_decisions,
    _write_decision_template,
    _write_raw_output,
)
from scripts.flows.F.price_list_manager.FPM158_ai_precheck_common import (
    PRECHECK_REGISTRY_COLUMNS,
    PRECHECK_STATUS_COLUMNS,
    ai_precheck_dir,
    finalize_columns,
    load_precheck_registry,
    queue_hash_lookup,
    read_any_csv,
    write_csv,
)
from scripts.flows.F.price_list_manager._io import normalize_text
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS
from scripts.one_off.F019_build_live_price_file_near_miss_pack import (
    NEAR_MISS_COLUMNS,
    build_live_price_file_near_miss_pack,
)


FPM_INCREMENTAL_AI_PRECHECK_ENABLED_ENV = "FPM_INCREMENTAL_AI_PRECHECK_ENABLED"
FPM_INCREMENTAL_AI_PRECHECK_SUPPLIERS_ENV = "FPM_INCREMENTAL_AI_PRECHECK_SUPPLIERS"
DEFAULT_PRECHECK_SUPPLIERS = "td_synnex"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truthy_env(name: str, *, default: bool) -> bool:
    raw = normalize_text(os.environ.get(name, "")).lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on"}


def _enabled_suppliers() -> set[str]:
    raw = normalize_text(os.environ.get(FPM_INCREMENTAL_AI_PRECHECK_SUPPLIERS_ENV, DEFAULT_PRECHECK_SUPPLIERS))
    return {normalize_text(part).lower() for part in raw.split(",") if normalize_text(part)}


def precheck_enabled_for_supplier(supplier_id: str) -> bool:
    if not _truthy_env(FPM_INCREMENTAL_AI_PRECHECK_ENABLED_ENV, default=True):
        return False
    supplier = normalize_text(supplier_id).lower()
    enabled = _enabled_suppliers()
    return "*" in enabled or supplier in enabled


def _int_value(value: object) -> int:
    raw = normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _active_run_from_state(root: Path, *, supplier_id: str = "", run_id: str = "") -> tuple[str, str, str]:
    run_state = read_f_contract_df(root, "supplier_price_list_run_state")
    if run_state.empty:
        return normalize_text(supplier_id), normalize_text(run_id), ""
    work = run_state.copy()
    if supplier_id:
        work = work[work["supplier_id"].map(lambda value: normalize_text(value).lower()) == normalize_text(supplier_id).lower()]
    if run_id:
        work = work[work["run_id"].map(normalize_text) == normalize_text(run_id)]
    if work.empty:
        return normalize_text(supplier_id), normalize_text(run_id), ""
    work["_active_rank"] = work.apply(
        lambda row: 1
        if normalize_text(row.get("run_status", "")).lower() == "running" or _int_value(row.get("pending_rows", "")) > 0
        else 0,
        axis=1,
    )
    work["_sort_value"] = work.apply(
        lambda row: normalize_text(row.get("updated_at_utc", ""))
        or normalize_text(row.get("completed_at_utc", ""))
        or normalize_text(row.get("source_seen_at_utc", "")),
        axis=1,
    )
    selected = work.sort_values(["_active_rank", "_sort_value"], ascending=[False, False], kind="stable").iloc[0]
    return (
        normalize_text(selected.get("supplier_id", supplier_id)),
        normalize_text(selected.get("run_id", run_id)),
        normalize_text(selected.get("source_seen_at_utc", "")),
    )


def _write_health(
    *,
    precheck_dir: Path,
    observed_utc: str,
    status: str,
    value: object,
    notes: str,
    source_path: Path,
) -> None:
    write_csv(
        precheck_dir / "ai_precheck_health.csv",
        pd.DataFrame(
            [
                {
                    "check": "incremental_ai_precheck",
                    "status": status,
                    "value": str(value),
                    "notes": notes,
                    "observed_utc": observed_utc,
                    "source_path": str(source_path),
                }
            ]
        ),
        MANAGER_HEALTH_COLUMNS,
    )


def _append_stale_decisions(
    *,
    archive_path: Path,
    stale_rows: list[dict[str, str]],
) -> None:
    if not stale_rows:
        return
    existing = read_any_csv(archive_path)
    archive_df = pd.concat([existing, pd.DataFrame(stale_rows)], ignore_index=True).fillna("")
    archive_df = finalize_columns(archive_df, STALE_CODEX_AI_DECISION_ARCHIVE_COLUMNS)
    archive_df["_dedupe_key"] = archive_df.apply(
        lambda row: "|".join(
            [
                normalize_text(row.get("f032_decision_id", "")),
                normalize_text(row.get("codex_ai_action", "")),
                normalize_text(row.get("codex_ai_reviewed_utc", "")),
                normalize_text(row.get("archive_reason", "")),
            ]
        ),
        axis=1,
    )
    archive_df = archive_df.drop_duplicates("_dedupe_key", keep="last").drop(columns=["_dedupe_key"])
    _write_raw_output(archive_path, finalize_columns(archive_df, STALE_CODEX_AI_DECISION_ARCHIVE_COLUMNS))


def _remove_hash_changed_decisions(
    *,
    precheck_dir: Path,
    queue_df: pd.DataFrame,
    codex_df: pd.DataFrame,
    old_registry_df: pd.DataFrame,
    observed_utc: str,
) -> tuple[pd.DataFrame, int]:
    if queue_df.empty or codex_df.empty or old_registry_df.empty:
        return codex_df, 0
    current_hash_by_id = queue_hash_lookup(queue_df)
    old_hash_by_id = {
        normalize_text(row.get("f032_decision_id", "")): normalize_text(row.get("evidence_hash", ""))
        for row in old_registry_df.fillna("").to_dict("records")
        if normalize_text(row.get("f032_decision_id", ""))
    }
    active_rows: list[dict[str, str]] = []
    stale_rows: list[dict[str, str]] = []
    for _, row in codex_df.fillna("").iterrows():
        record = {column: normalize_text(row.get(column, "")) for column in CODEX_AI_DECISION_COLUMNS}
        decision_id = normalize_text(record.get("f032_decision_id", ""))
        old_hash = old_hash_by_id.get(decision_id, "")
        new_hash = current_hash_by_id.get(decision_id, "")
        if decision_id and old_hash and new_hash and old_hash != new_hash:
            stale = dict(record)
            stale["archived_utc"] = observed_utc
            stale["archive_reason"] = "precheck_evidence_hash_changed"
            stale["archived_from_path"] = str(precheck_dir / "codex_ai_review_decisions.csv")
            stale["active_ai_queue_path"] = str(precheck_dir / "ai_review_queue.csv")
            stale["active_queue_rows"] = str(len(queue_df.index))
            stale_rows.append(stale)
        else:
            active_rows.append(record)
    if stale_rows:
        _append_stale_decisions(
            archive_path=precheck_dir / "codex_ai_review_decisions_stale_archive.csv",
            stale_rows=stale_rows,
        )
    return finalize_columns(pd.DataFrame(active_rows), CODEX_AI_DECISION_COLUMNS), len(stale_rows)


def _decision_status(record: dict[str, str]) -> str:
    action = normalize_text(record.get("codex_ai_action", ""))
    reason = normalize_text(record.get("codex_ai_reason", ""))
    if not action:
        return "pending"
    if action not in VALID_CODEX_AI_ACTIONS:
        return "invalid_action"
    if not reason:
        return "missing_reason"
    return "decided"


def _write_registry(
    *,
    precheck_dir: Path,
    queue_df: pd.DataFrame,
    codex_df: pd.DataFrame,
    old_registry_df: pd.DataFrame,
    observed_utc: str,
) -> pd.DataFrame:
    old_by_id = {
        normalize_text(row.get("f032_decision_id", "")): row
        for row in old_registry_df.fillna("").to_dict("records")
        if normalize_text(row.get("f032_decision_id", ""))
    }
    codex_by_id = {
        normalize_text(row.get("f032_decision_id", "")): row
        for row in codex_df.fillna("").to_dict("records")
        if normalize_text(row.get("f032_decision_id", ""))
    }
    hash_by_id = queue_hash_lookup(queue_df)
    rows: list[dict[str, str]] = []
    for _, row in queue_df.fillna("").iterrows():
        queue_record = {column: normalize_text(value) for column, value in row.to_dict().items()}
        decision_id = normalize_text(queue_record.get("f032_decision_id", ""))
        old = old_by_id.get(decision_id, {})
        codex = codex_by_id.get(decision_id, {})
        rows.append(
            {
                "observed_utc": observed_utc,
                "first_seen_utc": normalize_text(old.get("first_seen_utc", "")) or observed_utc,
                "last_seen_utc": observed_utc,
                "supplier_id": normalize_text(queue_record.get("active_supplier_id", "")),
                "run_id": normalize_text(queue_record.get("active_run_id", "")),
                "f032_decision_id": decision_id,
                "source_review_pack_type": normalize_text(queue_record.get("source_review_pack_type", "")),
                "candidate_id": normalize_text(queue_record.get("candidate_id", "")),
                "supplier_sku": normalize_text(queue_record.get("supplier_sku", "")),
                "asin": normalize_text(queue_record.get("asin", "")),
                "evidence_hash": hash_by_id.get(decision_id, ""),
                "decision_status": _decision_status(codex),
                "codex_ai_action": normalize_text(codex.get("codex_ai_action", "")),
                "hidden_until_completed_flag": "1",
                "notes": "hidden_incremental_ai_precheck",
            }
        )
    registry = finalize_columns(pd.DataFrame(rows), PRECHECK_REGISTRY_COLUMNS)
    write_csv(precheck_dir / "ai_precheck_registry.csv", registry, PRECHECK_REGISTRY_COLUMNS)
    return registry


def build_incremental_ai_precheck(
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
    observed = observed_utc or _utc_now_iso()
    selected_supplier, selected_run, source_seen_at_utc = _active_run_from_state(
        root_path,
        supplier_id=supplier_id,
        run_id=run_id,
    )
    selected_dir = ai_precheck_dir(root_path, supplier_id=selected_supplier, run_id=selected_run)
    selected_dir.mkdir(parents=True, exist_ok=True)

    if not selected_supplier or not selected_run:
        status_row = {
            "observed_utc": observed,
            "supplier_id": selected_supplier,
            "run_id": selected_run,
            "status": "skipped",
            "hidden_until_completed_flag": "1",
            "notes": "active_supplier_or_run_missing",
        }
        write_csv(selected_dir / "ai_precheck_status.csv", pd.DataFrame([status_row]), PRECHECK_STATUS_COLUMNS)
        _write_health(
            precheck_dir=selected_dir,
            observed_utc=observed,
            status="ok",
            value="skipped",
            notes="active_supplier_or_run_missing",
            source_path=selected_dir / "ai_precheck_status.csv",
        )
        if emit_json:
            print(json.dumps(status_row, indent=2, sort_keys=True))
        return status_row

    if not precheck_enabled_for_supplier(selected_supplier):
        status_row = {
            "observed_utc": observed,
            "supplier_id": selected_supplier,
            "run_id": selected_run,
            "status": "skipped",
            "hidden_until_completed_flag": "1",
            "notes": "supplier_not_enabled_for_incremental_ai_precheck",
        }
        write_csv(selected_dir / "ai_precheck_status.csv", pd.DataFrame([status_row]), PRECHECK_STATUS_COLUMNS)
        _write_health(
            precheck_dir=selected_dir,
            observed_utc=observed,
            status="ok",
            value="skipped",
            notes="supplier_not_enabled_for_incremental_ai_precheck",
            source_path=selected_dir / "ai_precheck_status.csv",
        )
        if emit_json:
            print(json.dumps(status_row, indent=2, sort_keys=True))
        return status_row

    raw_dir = selected_dir / "raw_review_pack"
    result = build_live_price_file_near_miss_pack(
        baseline_path=root_path / "out" / "analysis_reports" / "f_live_price_file_launch_baseline_latest.csv",
        row_state_path=root_path / "out" / "systems" / "F" / "live" / "f_screening_row_state_live.csv",
        first_checks_path=root_path / "out" / "systems" / "F" / "live" / "feeder_legacy_first_checks_live.csv",
        scrape_evidence_path=root_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv",
        page_evidence_backfill_results_path=root_path
        / "out"
        / "systems"
        / "F"
        / "page_evidence_backfill"
        / "page_evidence_backfill_results.csv",
        backtest_summary_path=root_path / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv",
        profit_audit_path=root_path / "out" / "analysis_reports" / "f_profit_formula_conflict_audit_latest.csv",
        review_events_path=root_path / "out" / "systems" / "F" / "inbox" / "feeder_review_events.csv",
        supplier_inbox_dir=root_path / "out" / "systems" / "F" / "inbox" / "suppliers",
        output_dir=raw_dir,
        observed_utc=observed,
        active_supplier_id=selected_supplier,
        active_run_id=selected_run,
        source_seen_at_utc_override=source_seen_at_utc,
        write_sql_snapshots=False,
    )

    pass_df = result.pass_df.copy().fillna("")
    eligible_pass_rows = int(len(pass_df.index))
    pass_precheck_path = selected_dir / "precheck_pass_review.csv"
    near_empty_path = selected_dir / "precheck_near_miss_review.csv"
    _write_raw_output(pass_precheck_path, pass_df)
    _write_raw_output(near_empty_path, pd.DataFrame(columns=NEAR_MISS_COLUMNS))

    f032_result = build_review_intelligence_cycle(
        pass_review_path=pass_precheck_path,
        near_miss_review_path=near_empty_path,
        title_match_path=root_path / "out" / "analysis_reports" / "f_title_match_agent_decisions_latest.csv",
        supplier_inbox_dir=root_path / "out" / "systems" / "F" / "inbox" / "suppliers",
        evidence_output_path=selected_dir / "ai_review_intelligence_evidence_pack.csv",
        decision_output_path=selected_dir / "ai_review_intelligence_decisions.csv",
        fail_category_output_path=selected_dir / "ai_review_intelligence_fail_categories.csv",
        checklist_output_path=selected_dir / "ai_review_intelligence_checklist.csv",
        rule_suggestion_output_path=selected_dir / "ai_rule_tightening_suggestions.csv",
        health_output_path=selected_dir / "ai_review_intelligence_health.csv",
        summary_output_path=selected_dir / "ai_review_intelligence_summary.md",
        observed_utc=observed,
    )

    queue_df = _build_ai_review_queue(f032_result.evidence_df, f032_result.decision_df)
    queue_df = queue_df[queue_df["source_review_pack_type"].map(normalize_text).eq("passes")].copy()
    queue_df = finalize_columns(queue_df, AI_REVIEW_QUEUE_COLUMNS)
    queue_path = selected_dir / "ai_review_queue.csv"
    decision_template_path = selected_dir / "codex_ai_review_decision_template.csv"
    decision_path = selected_dir / "codex_ai_review_decisions.csv"
    _write_raw_output(queue_path, queue_df)
    _write_decision_template(decision_template_path, queue_df)

    old_registry = load_precheck_registry(selected_dir)
    codex_df = _load_codex_decisions(decision_path)
    codex_df, stale_removed_rows, _stale_archive_path = _archive_stale_codex_decisions(
        codex_decision_path=decision_path,
        ai_queue_path=queue_path,
        queue_df=queue_df,
        codex_df=codex_df,
        observed_utc=observed,
    )
    codex_df, hash_stale_rows = _remove_hash_changed_decisions(
        precheck_dir=selected_dir,
        queue_df=queue_df,
        codex_df=codex_df,
        old_registry_df=old_registry,
        observed_utc=observed,
    )
    if stale_removed_rows or hash_stale_rows:
        _write_raw_output(decision_path, codex_df)

    registry = _write_registry(
        precheck_dir=selected_dir,
        queue_df=queue_df,
        codex_df=codex_df,
        old_registry_df=old_registry,
        observed_utc=observed,
    )
    pending, invalid, missing_reason = _codex_decision_gaps(queue_df, codex_df)
    decided_rows = int(registry["decision_status"].eq("decided").sum()) if not registry.empty else 0
    stale_rows = int(stale_removed_rows) + int(hash_stale_rows)
    status = "pending_ai_decision" if pending else "ready_hidden"
    if eligible_pass_rows == 0:
        status = "no_eligible_rows"

    status_row = {
        "observed_utc": observed,
        "supplier_id": selected_supplier,
        "run_id": selected_run,
        "status": status,
        "eligible_pass_rows": str(eligible_pass_rows),
        "ai_queue_rows": str(len(queue_df.index)),
        "pending_ai_decision_rows": str(pending),
        "decided_rows": str(decided_rows),
        "invalid_action_rows": str(invalid),
        "missing_reason_rows": str(missing_reason),
        "stale_decision_rows": str(stale_rows),
        "reused_in_final_rows": "0",
        "hidden_until_completed_flag": "1",
        "ai_review_queue_path": str(queue_path),
        "codex_ai_decision_path": str(decision_path),
        "registry_path": str(selected_dir / "ai_precheck_registry.csv"),
        "notes": "hidden_until_supplier_run_completed",
    }
    write_csv(selected_dir / "ai_precheck_status.csv", pd.DataFrame([status_row]), PRECHECK_STATUS_COLUMNS)
    _write_health(
        precheck_dir=selected_dir,
        observed_utc=observed,
        status="warn" if invalid or missing_reason else "ok",
        value=status,
        notes=(
            f"eligible_pass_rows={eligible_pass_rows};queue_rows={len(queue_df.index)};"
            f"pending_ai_decision_rows={pending};hidden_until_completed=1"
        ),
        source_path=queue_path,
    )
    if emit_json:
        print(json.dumps(status_row, indent=2, sort_keys=True))
    return status_row


def main() -> None:
    parser = argparse.ArgumentParser(description="Build hidden incremental AI precheck rows for an active F supplier run.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--force-rebuild", action="store_true")
    args = parser.parse_args()
    build_incremental_ai_precheck(
        root=Path(args.root) if args.root else None,
        supplier_id=args.supplier_id,
        run_id=args.run_id,
        observed_utc=args.observed_utc,
        force_rebuild=bool(args.force_rebuild),
    )


if __name__ == "__main__":
    main()
