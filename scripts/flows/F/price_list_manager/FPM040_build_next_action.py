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

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BARCODE_SCAN_MEMORY_COLUMNS,
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PLACEHOLDER_SCANNER_RESULT_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    QUEUE_CONTROL_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)
from scripts.flows.F.price_list_manager.timeout_queue import _apply_batch_status_skips, build_timeout_queue_eligibility
from scripts.flows.F.f_scanner_timeout_policy import (
    build_timeout_policy_health_rows,
    read_timeout_policy_df,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object) -> datetime | None:
    raw = normalize_text(value)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        parsed = pd.to_datetime(raw, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()


def _batch_status_lookup(batches: pd.DataFrame) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    if batches.empty:
        return out
    work = batches.copy()
    work["_updated"] = work["updated_at_utc"].map(normalize_text)
    work = work.sort_values("_updated", ascending=False, kind="stable")
    for _, row in work.iterrows():
        batch_id = normalize_text(row.get("batch_id", ""))
        if batch_id and batch_id not in out:
            out[batch_id] = row
    return out


def _supplier_priority_lookup(registry: pd.DataFrame) -> dict[str, int]:
    priority_scores = {
        "pilot": 100,
        "monthly_manual": 80,
        "daily_email_large": 60,
        "daily_email": 55,
        "api": 50,
        "csv_link": 50,
        "manual_download": 45,
    }
    out: dict[str, int] = {}
    for _, row in registry.iterrows():
        supplier_id = normalize_text(row.get("supplier_id", ""))
        priority = normalize_text(row.get("priority_band", "")).lower()
        out[supplier_id] = priority_scores.get(priority, 40)
    return out


def _queue_control_lookup(controls: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if controls.empty:
        return out
    work = controls.copy()
    work["_updated"] = work["updated_at_utc"].map(normalize_text)
    work = work.sort_values("_updated", ascending=False, kind="stable")
    for _, row in work.iterrows():
        supplier_id = normalize_text(row.get("supplier_id", ""))
        if not supplier_id or supplier_id in out:
            continue
        state = normalize_text(row.get("control_state", "")).lower()
        if state in {"paused", "prioritised"}:
            out[supplier_id] = {
                "control_state": state,
                "priority_rank": normalize_text(row.get("priority_rank", "")),
                "reason": normalize_text(row.get("reason", "")),
            }
    return out


def _priority_rank(value: object) -> int:
    raw = normalize_text(value)
    if not raw:
        return 999
    try:
        rank = int(float(raw))
    except ValueError:
        return 999
    return rank if rank >= 1 else 999


def _candidate_sort_key(item: dict[str, object]) -> tuple[int, int, int, float, str]:
    source_dt = _parse_utc(item.get("source_received_at_utc", ""))
    source_ts = source_dt.timestamp() if source_dt is not None else 0.0
    priority_flag = 0 if normalize_text(item.get("control_state", "")).lower() == "prioritised" else 1
    return (
        priority_flag,
        int(item.get("priority_rank", 999)),
        -int(item["score"]),
        -source_ts,
        normalize_text(item.get("supplier_id", "")),
    )


RECOVERY_DECISION_REASONS = {
    "timeout_expired_or_missing",
    "cost_changed_reset",
    "pass_cost_changed_reset",
    "source_changed_reset",
    "policy_disabled",
}

SKIP_BATCH_STATUSES = {"superseded"}


def _recovery_scan_rows(group: pd.DataFrame) -> int:
    if group.empty or "scan_decision" not in group.columns or "decision_reason" not in group.columns:
        return 0
    scan_mask = group["scan_decision"].map(normalize_text).str.lower() == "scan"
    reason_mask = group["decision_reason"].map(normalize_text).str.lower().isin(RECOVERY_DECISION_REASONS)
    return int((scan_mask & reason_mask).sum())


def build_next_action(root: Path | None = None, *, observed_utc: str | None = None) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    observed = observed_utc or _utc_now_iso()
    observed_dt = _parse_utc(observed) or datetime.now(timezone.utc)

    batches_path = paths.test_mode_dir / "price_list_batches.csv"
    rows_path = paths.test_mode_dir / "batch_rows.csv"
    eligibility_path = paths.test_mode_dir / "batch_scan_eligibility.csv"
    decisions_path = paths.test_mode_dir / "manager_decisions.csv"
    health_path = paths.test_mode_dir / "health.csv"
    controls_path = paths.test_mode_dir / "queue_controls.csv"

    batches = read_csv(batches_path, PRICE_LIST_BATCH_COLUMNS)
    batch_rows = read_csv(rows_path, BATCH_ROW_COLUMNS)
    memory = read_csv(paths.test_mode_dir / "barcode_scan_memory.csv", BARCODE_SCAN_MEMORY_COLUMNS)
    results = read_csv(paths.test_mode_dir / "placeholder_scanner_results.csv", PLACEHOLDER_SCANNER_RESULT_COLUMNS)
    registry = read_csv(paths.test_mode_dir / "supplier_registry.csv", SUPPLIER_REGISTRY_COLUMNS)
    controls = read_csv(controls_path, QUEUE_CONTROL_COLUMNS)
    existing_decisions = read_csv(decisions_path, MANAGER_DECISION_COLUMNS)
    timeout_policy = read_timeout_policy_df(root=paths.root, create_if_missing=True, observed_utc=observed)

    if batches.empty or batch_rows.empty:
        raise FileNotFoundError("price-list batches and batch rows are required before next-action scoring")

    eligibility_df = build_timeout_queue_eligibility(
        batch_rows=batch_rows,
        memory=memory,
        results=results,
        timeout_policy=timeout_policy,
        observed_utc=observed_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    eligibility_df = _apply_batch_status_skips(eligibility_df, batches)
    eligibility = write_csv(eligibility_path, eligibility_df, BATCH_SCAN_ELIGIBILITY_COLUMNS)

    batch_lookup = _batch_status_lookup(batches)
    supplier_priority = _supplier_priority_lookup(registry)
    control_lookup = _queue_control_lookup(controls)
    paused_suppliers: set[str] = set()
    prioritised_suppliers: set[str] = set()
    skipped_batch_statuses: set[str] = set()
    candidates: list[dict[str, object]] = []
    for batch_id, group in eligibility.groupby("batch_id", dropna=False):
        batch_key = normalize_text(batch_id)
        if not batch_key:
            continue
        batch = batch_lookup.get(batch_key)
        batch_status = normalize_text(batch.get("batch_status", "") if batch is not None else "").lower()
        if batch_status in SKIP_BATCH_STATUSES:
            skipped_batch_statuses.add(batch_status)
            continue
        supplier_id = normalize_text(group.iloc[0].get("supplier_id", ""))
        scan_rows = int((group["scan_decision"] == "scan").sum())
        skip_rows = int((group["scan_decision"] == "skip").sum())
        recovery_rows = _recovery_scan_rows(group)
        if scan_rows <= 0:
            continue
        control = control_lookup.get(supplier_id, {})
        control_state = normalize_text(control.get("control_state", "")).lower()
        if control_state == "paused":
            paused_suppliers.add(supplier_id)
            continue
        if control_state == "prioritised":
            prioritised_suppliers.add(supplier_id)
        source_received = normalize_text(batch.get("source_received_at_utc", "")) if batch is not None else ""
        score = scan_rows + supplier_priority.get(supplier_id, 40) + (recovery_rows * 25)
        candidates.append(
            {
                "batch_id": batch_key,
                "supplier_id": supplier_id,
                "scan_rows": scan_rows,
                "skip_rows": skip_rows,
                "recovery_rows": recovery_rows,
                "source_received_at_utc": source_received,
                "score": score,
                "control_state": control_state,
                "priority_rank": _priority_rank(control.get("priority_rank", "")),
            }
        )

    candidates = sorted(candidates, key=_candidate_sort_key)
    notes_parts = [f"candidate_batches={len(candidates)}"]
    if paused_suppliers:
        notes_parts.append(f"paused_suppliers={','.join(sorted(paused_suppliers))}")
    if prioritised_suppliers:
        notes_parts.append(f"prioritised_suppliers={','.join(sorted(prioritised_suppliers))}")
    if skipped_batch_statuses:
        notes_parts.append(f"skipped_batch_statuses={','.join(sorted(skipped_batch_statuses))}")
    notes_parts.append("handoff_disabled")

    if candidates:
        selected = candidates[0]
        reason_code = (
            "operator_prioritised_supplier"
            if normalize_text(selected.get("control_state", "")).lower() == "prioritised"
            else "recovery_rows_prioritised_after_timeout"
            if int(selected.get("recovery_rows", 0)) > 0
            else "highest_eligible_scan_rows_after_cooldown"
        )
        decision = {
            "decision_id": f"next_action_{observed_dt.strftime('%Y%m%dT%H%M%SZ')}",
            "decided_at_utc": observed_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "recommended_action": "recommend_test_scan",
            "supplier_id": str(selected["supplier_id"]),
            "batch_id": str(selected["batch_id"]),
            "reason_code": reason_code,
            "estimated_scan_rows": str(selected["scan_rows"]),
            "estimated_skip_rows": str(selected["skip_rows"]),
            "f061_owner_status": "not_checked_test_mode",
            "safe_to_handoff_flag": "0",
            "notes": ";".join(notes_parts),
        }
    else:
        decision = {
            "decision_id": f"next_action_{observed_dt.strftime('%Y%m%dT%H%M%SZ')}",
            "decided_at_utc": observed_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "recommended_action": "no_scan_ready",
            "supplier_id": "",
            "batch_id": "",
            "reason_code": "no_rows_eligible_after_cooldown",
            "estimated_scan_rows": "0",
            "estimated_skip_rows": str(len(eligibility.index)),
            "f061_owner_status": "not_checked_test_mode",
            "safe_to_handoff_flag": "0",
            "notes": ";".join(notes_parts) if notes_parts else "handoff_disabled",
        }

    decisions = write_csv(
        decisions_path,
        pd.concat([existing_decisions, pd.DataFrame([decision])], ignore_index=True),
        MANAGER_DECISION_COLUMNS,
    )

    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    scan_total = int((eligibility["scan_decision"] == "scan").sum())
    skip_total = int((eligibility["scan_decision"] == "skip").sum())
    policy_screening_state = pd.DataFrame(
        [
            {"fail_code": normalize_text(row.get("last_fail_code", ""))}
            for _, row in memory.iterrows()
            if normalize_text(row.get("last_fail_code", ""))
        ]
    )
    health_rows = [
        {
            "check": "next_action_reconciliation",
            "status": "ok" if scan_total + skip_total == len(eligibility.index) else "fail",
            "value": str(len(eligibility.index)),
            "notes": f"scan_rows={scan_total};skip_rows={skip_total};candidate_batches={len(candidates)};selected={decision['supplier_id']}",
            "observed_utc": observed_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_path": str(eligibility_path),
        },
        *build_timeout_policy_health_rows(
            root=paths.root,
            screening_state_df=policy_screening_state,
            observed_utc=observed_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    ]
    health = write_csv(
        health_path,
        pd.concat([existing_health, pd.DataFrame(health_rows)], ignore_index=True),
        MANAGER_HEALTH_COLUMNS,
    )

    summary = {
        "status": "success",
        "eligibility_rows": int(len(eligibility.index)),
        "scan_rows": scan_total,
        "skip_rows": skip_total,
        "candidate_batches": int(len(candidates)),
        "selected_supplier_id": decision["supplier_id"],
        "selected_batch_id": decision["batch_id"],
        "estimated_scan_rows": int(decision["estimated_scan_rows"]),
        "safe_to_handoff_flag": decision["safe_to_handoff_flag"],
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "eligibility_path": str(eligibility_path),
        "decisions_path": str(decisions_path),
        "decision_rows": int(len(decisions.index)),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the price-list manager next-action recommendation.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--observed-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    build_next_action(root=root, observed_utc=args.observed_utc)


if __name__ == "__main__":
    main()
