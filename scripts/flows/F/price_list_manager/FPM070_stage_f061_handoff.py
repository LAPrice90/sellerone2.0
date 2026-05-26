from __future__ import annotations

import argparse
import re
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
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    BATCH_SCAN_ELIGIBILITY_COLUMNS,
    F061_HANDOFF_APPROVAL_COLUMNS,
    F061_HANDOFF_PREVIEW_COLUMNS,
    F061_STAGED_ACTIVE_RUN_COLUMNS,
    F061_STAGED_RUN_STATE_COLUMNS,
    MANAGER_DECISION_COLUMNS,
    MANAGER_HEALTH_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _latest_decision(decisions: pd.DataFrame) -> pd.Series | None:
    if decisions.empty:
        return None
    work = decisions.copy()
    work = work[work.apply(lambda row: any(normalize_text(value) for value in row.values), axis=1)]
    return work.iloc[-1] if not work.empty else None


def _supplier_lookup(registry: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        normalize_text(row.get("supplier_id", "")): row
        for _, row in registry.iterrows()
        if normalize_text(row.get("supplier_id", ""))
    }


def _batch_lookup(batches: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        normalize_text(row.get("batch_id", "")): row
        for _, row in batches.iterrows()
        if normalize_text(row.get("batch_id", ""))
    }


def _price_list_int(value: object) -> int:
    raw = normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _f061_idle_status(root_path: Path) -> tuple[str, str]:
    active_df = read_f_contract_df(root_path, "supplier_price_list_active_run")
    run_state_df = read_f_contract_df(root_path, "supplier_price_list_run_state")
    pending_active = 0
    if not active_df.empty and "scan_status" in active_df.columns:
        pending_active = int((active_df["scan_status"].map(lambda value: normalize_text(value).lower()) == "pending").sum())
    running_state = 0
    pending_state = 0
    if not run_state_df.empty:
        running_state = int((run_state_df["run_status"].map(lambda value: normalize_text(value).lower()) == "running").sum())
        pending_state = int(run_state_df["pending_rows"].map(_price_list_int).sum())
    if pending_active or running_state or pending_state:
        return "busy", f"pending_active={pending_active};running_state={running_state};pending_state={pending_state}"
    return "idle", "no_pending_or_running_f061_rows"


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


def _active_handoff_approval(
    approvals: pd.DataFrame,
    *,
    supplier_id: str,
    batch_id: str,
    observed_dt: datetime,
) -> tuple[str, str]:
    if approvals.empty:
        return "required", ""
    work = approvals[
        (approvals["supplier_id"].map(normalize_text) == supplier_id)
        & (approvals["batch_id"].map(normalize_text) == batch_id)
    ].copy()
    if work.empty:
        return "required", ""
    work["_approved_at"] = work["approved_at_utc"].map(normalize_text)
    work = work.sort_values("_approved_at", ascending=False, kind="stable")
    latest = work.iloc[0]
    state = normalize_text(latest.get("approval_state", "")).lower()
    approval_id = normalize_text(latest.get("approval_id", ""))
    expires_dt = _parse_utc(latest.get("expires_at_utc", ""))
    if expires_dt is not None and expires_dt <= observed_dt:
        return "expired", approval_id
    if state == "approved":
        return "approved", approval_id
    if state == "revoked":
        return "revoked", approval_id
    return "required", approval_id


def _selected_rows(
    *,
    decision: pd.Series,
    eligibility: pd.DataFrame,
    batch_rows: pd.DataFrame,
) -> pd.DataFrame:
    batch_id = normalize_text(decision.get("batch_id", ""))
    if not batch_id:
        return pd.DataFrame(columns=BATCH_ROW_COLUMNS)
    eligible = eligibility[
        (eligibility["batch_id"].map(normalize_text) == batch_id)
        & (eligibility["scan_decision"].map(normalize_text) == "scan")
    ].copy()
    if eligible.empty:
        return pd.DataFrame(columns=BATCH_ROW_COLUMNS)
    selected_keys = {normalize_text(value) for value in eligible["row_key"].tolist()}
    rows = batch_rows[
        (batch_rows["batch_id"].map(normalize_text) == batch_id)
        & (batch_rows["row_key"].map(normalize_text).isin(selected_keys))
    ].copy()
    return rows.reset_index(drop=True)


def _build_staged_active_run(
    *,
    rows: pd.DataFrame,
    run_id: str,
    supplier_name: str,
    source_seen_at_utc: str,
) -> pd.DataFrame:
    out_rows: list[dict[str, str]] = []
    for _, row in rows.iterrows():
        out_rows.append(
            {
                "run_id": run_id,
                "supplier_id": normalize_text(row.get("supplier_id", "")),
                "supplier_name": supplier_name,
                "row_key": normalize_text(row.get("row_key", "")),
                "supplier_sku": normalize_text(row.get("supplier_sku", "")),
                "barcode": normalize_text(row.get("barcode", "")),
                "supplier_title": normalize_text(row.get("supplier_title", "")),
                "unit_cost": normalize_text(row.get("unit_cost", "")),
                "currency": normalize_text(row.get("currency", "")) or "GBP",
                "vat_rate": normalize_text(row.get("vat_rate", "")) or "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": source_seen_at_utc,
            }
        )
    return pd.DataFrame(out_rows)


def _missing_required_rows(rows: pd.DataFrame) -> dict[str, int]:
    required = ["supplier_sku", "supplier_title", "barcode", "unit_cost", "currency", "vat_rate"]
    return {
        column: int((rows[column].map(normalize_text) == "").sum()) if column in rows.columns else len(rows.index)
        for column in required
    }


def _is_positive_number(value: object) -> bool:
    raw = normalize_text(value)
    if not raw:
        return False
    cleaned = raw.replace(",", "").replace("£", "").strip()
    try:
        return float(cleaned) > 0
    except ValueError:
        return False


def _looks_like_standalone_number(value: object) -> bool:
    raw = normalize_text(value)
    if not raw:
        return False
    cleaned = raw.replace(",", "").replace("£", "").strip()
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", cleaned):
        return False
    return _is_positive_number(cleaned)


def _is_td_synnex_numeric_code_title(row: pd.Series) -> bool:
    supplier_sku = normalize_text(row.get("supplier_sku", ""))
    supplier_title = normalize_text(row.get("supplier_title", ""))
    return bool(
        supplier_sku
        and supplier_title
        and supplier_sku == supplier_title
        and re.fullmatch(r"\d+", supplier_sku)
    )


def _shape_sample_note(rows: pd.DataFrame) -> str:
    if rows.empty:
        return ""
    sample = rows.iloc[0]
    return (
        f"sample_row_key={normalize_text(sample.get('row_key', ''))}|"
        f"sample_supplier_sku={normalize_text(sample.get('supplier_sku', ''))}|"
        f"sample_supplier_title={normalize_text(sample.get('supplier_title', ''))}"
    )


def source_shape_guard_reasons(rows: pd.DataFrame, *, supplier_id: str) -> list[str]:
    reasons: list[str] = []
    if rows.empty:
        return reasons

    supplier = normalize_text(supplier_id)
    if "supplier_id" in rows.columns and supplier:
        mismatched = rows[rows["supplier_id"].map(normalize_text) != supplier].copy()
        if not mismatched.empty:
            reasons.append(
                "source_shape_guard:supplier_id_mismatch|"
                f"count={len(mismatched.index)}|{_shape_sample_note(mismatched)}"
            )

    if "unit_cost" in rows.columns:
        bad_cost = rows[~rows["unit_cost"].map(_is_positive_number)].copy()
        if not bad_cost.empty:
            reasons.append(
                "source_shape_guard:unit_cost_not_positive_numeric|"
                f"count={len(bad_cost.index)}|{_shape_sample_note(bad_cost)}"
            )

    if supplier == "td_synnex" and "supplier_title" in rows.columns:
        numeric_title = rows[rows["supplier_title"].map(_looks_like_standalone_number)].copy()
        if not numeric_title.empty and "supplier_sku" in numeric_title.columns:
            numeric_title = numeric_title[
                ~numeric_title.apply(_is_td_synnex_numeric_code_title, axis=1)
            ].copy()
        if not numeric_title.empty:
            reasons.append(
                "source_shape_guard:td_synnex_supplier_title_numeric_like|"
                f"count={len(numeric_title.index)}|{_shape_sample_note(numeric_title)}"
            )

    return reasons


def stage_f061_handoff(
    root: Path | None = None,
    *,
    built_at_utc: str | None = None,
    apply_live: bool = False,
    confirm_live_handoff: bool = False,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    root_path = paths.root
    test_dir = paths.test_mode_dir
    built_at = built_at_utc or _utc_now_iso()
    built_dt = _parse_utc(built_at) or datetime.now(timezone.utc)

    decisions = read_csv(test_dir / "manager_decisions.csv", MANAGER_DECISION_COLUMNS)
    eligibility = read_csv(test_dir / "batch_scan_eligibility.csv", BATCH_SCAN_ELIGIBILITY_COLUMNS)
    batch_rows = read_csv(test_dir / "batch_rows.csv", BATCH_ROW_COLUMNS)
    batches = read_csv(test_dir / "price_list_batches.csv", PRICE_LIST_BATCH_COLUMNS)
    registry = read_csv(test_dir / "supplier_registry.csv", SUPPLIER_REGISTRY_COLUMNS)
    approvals = read_csv(test_dir / "f061_handoff_approvals.csv", F061_HANDOFF_APPROVAL_COLUMNS)
    health_path = test_dir / "health.csv"

    decision = _latest_decision(decisions)
    if decision is None:
        raise FileNotFoundError("manager_decisions.csv has no decision to stage")

    supplier_id = normalize_text(decision.get("supplier_id", ""))
    batch_id = normalize_text(decision.get("batch_id", ""))
    supplier = _supplier_lookup(registry).get(supplier_id)
    batch = _batch_lookup(batches).get(batch_id)
    supplier_name = (
        normalize_text(supplier.get("supplier_name", "")) if supplier is not None else supplier_id
    )
    source_seen_at_utc = normalize_text(batch.get("source_received_at_utc", "")) if batch is not None else built_at
    source_file_path = normalize_text(batch.get("source_file_path", "")) if batch is not None else ""
    source_url = normalize_text(supplier.get("source_url", "")) if supplier is not None else ""

    selected = _selected_rows(decision=decision, eligibility=eligibility, batch_rows=batch_rows)
    missing = _missing_required_rows(selected)
    missing_total = sum(missing.values())
    shape_reasons = source_shape_guard_reasons(selected, supplier_id=supplier_id)
    idle_status, idle_notes = _f061_idle_status(root_path)
    technical_ready = bool(
        idle_status == "idle"
        and missing_total == 0
        and not shape_reasons
        and len(selected.index) > 0
    )
    approval_state, approval_id = _active_handoff_approval(
        approvals,
        supplier_id=supplier_id,
        batch_id=batch_id,
        observed_dt=built_dt,
    )
    approval_ready = approval_state == "approved"
    live_apply_allowed = bool(technical_ready and approval_ready)

    run_id = f"fpm_{supplier_id}_{built_dt.strftime('%Y%m%dT%H%M%SZ')}"
    staged_active_path = test_dir / "f061_handoff_staged_active_run.csv"
    staged_run_state_path = test_dir / "f061_handoff_staged_run_state.csv"
    preview_path = test_dir / "f061_handoff_preview.csv"

    staged_active = pd.DataFrame(columns=F061_STAGED_ACTIVE_RUN_COLUMNS)
    if missing_total == 0 and not shape_reasons and len(selected.index) > 0:
        staged_active = _build_staged_active_run(
            rows=selected,
            run_id=run_id,
            supplier_name=supplier_name,
            source_seen_at_utc=source_seen_at_utc,
        )
    staged_active = write_csv(staged_active_path, staged_active, F061_STAGED_ACTIVE_RUN_COLUMNS)

    run_state_row = {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "run_id": run_id,
        "run_status": "running" if len(staged_active.index) > 0 else "blocked",
        "source_url": source_url,
        "source_file_path": source_file_path,
        "source_seen_at_utc": source_seen_at_utc,
        "normalized_utc": built_at,
        "total_rows": str(len(staged_active.index)),
        "pending_rows": str(len(staged_active.index)),
        "done_rows": "0",
        "failed_rows": "0",
        "held_rows": "0",
        "next_row_index": "1" if len(staged_active.index) > 0 else "0",
        "updated_at_utc": built_at,
        "completed_at_utc": "",
    }
    staged_run_state = write_csv(
        staged_run_state_path,
        pd.DataFrame([run_state_row]),
        F061_STAGED_RUN_STATE_COLUMNS,
    )

    block_reasons: list[str] = []
    if len(selected.index) == 0:
        block_reasons.append("no_selected_scan_rows")
    if missing_total:
        missing_notes = "|".join(f"{key}={value}" for key, value in missing.items() if value)
        block_reasons.append(f"missing_f061_required_fields:{missing_notes}")
    block_reasons.extend(shape_reasons)
    if idle_status != "idle":
        block_reasons.append(f"f061_not_idle:{idle_notes}")
    if technical_ready and not approval_ready:
        block_reasons.append(f"handoff_approval_{approval_state}")
    if apply_live and not confirm_live_handoff:
        block_reasons.append("confirm_live_handoff_required")
    if apply_live:
        block_reasons.append("live_apply_not_enabled_in_phase6_stage")

    preview_row = {
        "handoff_id": f"handoff_{built_at.replace('-', '').replace(':', '')}",
        "built_at_utc": built_at,
        "mode": "apply_requested" if apply_live else "stage_only",
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "batch_id": batch_id,
        "run_id": run_id,
        "staged_rows": str(len(staged_active.index)),
        "technical_ready_flag": "1" if technical_ready else "0",
        "approval_state": approval_state,
        "approval_id": approval_id,
        "live_apply_allowed": "1" if live_apply_allowed else "0",
        "f061_idle_status": idle_status,
        "block_reason": ";".join(block_reasons),
        "staged_active_run_path": str(staged_active_path),
        "staged_run_state_path": str(staged_run_state_path),
    }
    preview = write_csv(preview_path, pd.DataFrame([preview_row]), F061_HANDOFF_PREVIEW_COLUMNS)

    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health_row = pd.DataFrame(
        [
            {
                "check": "f061_handoff_stage_guard",
                "status": "ok" if len(staged_active.index) > 0 and not apply_live else "fail",
                "value": str(len(staged_active.index)),
                "notes": (
                    f"idle_status={idle_status};live_apply_allowed={int(live_apply_allowed)};"
                    f"technical_ready={int(technical_ready)};approval_state={approval_state};"
                    f"apply_live={int(apply_live)};block_reason={preview_row['block_reason']}"
                ),
                "observed_utc": built_at,
                "source_path": str(preview_path),
            }
        ]
    )
    health = write_csv(health_path, pd.concat([existing_health, health_row], ignore_index=True), MANAGER_HEALTH_COLUMNS)

    if apply_live:
        raise RuntimeError("live F061 handoff apply is not enabled in this phase; staged files were written only")

    summary = {
        "status": "staged" if len(staged_active.index) > 0 else "blocked",
        "supplier_id": supplier_id,
        "batch_id": batch_id,
        "run_id": run_id,
        "staged_rows": int(len(staged_active.index)),
        "live_apply_allowed": "1" if live_apply_allowed else "0",
        "technical_ready_flag": "1" if technical_ready else "0",
        "approval_state": approval_state,
        "approval_id": approval_id,
        "f061_idle_status": idle_status,
        "block_reason": preview_row["block_reason"],
        "staged_active_run_path": str(staged_active_path),
        "staged_run_state_path": str(staged_run_state_path),
        "preview_rows": int(len(preview.index)),
        "run_state_rows": int(len(staged_run_state.index)),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "live_active_run_path": str(root_path / get_f_output_contract("supplier_price_list_active_run").rel_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage a manager-selected batch for future F061 handoff.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--built-at-utc", default=None)
    parser.add_argument("--apply-live", action="store_true")
    parser.add_argument("--confirm-live-handoff", action="store_true")
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    stage_f061_handoff(
        root=root,
        built_at_utc=args.built_at_utc,
        apply_live=bool(args.apply_live),
        confirm_live_handoff=bool(args.confirm_live_handoff),
    )


if __name__ == "__main__":
    main()
