from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .autonomy_policy import (
    controlled_technical_pause_allowed,
    is_controlled_technical_pause_text,
    is_quiet_autonomy_parked_decision_text,
    quiet_autonomy_active,
)
from .paths import get_manager_paths
from .schemas import (
    EXPECTATION_RECONCILIATION_COLUMNS,
    FLOW_MAINTENANCE_COLUMNS,
    HEALTH_COLUMNS,
    MANAGER_TASK_CANDIDATE_COLUMNS,
)


FLOW_ORDER = ["A", "B", "E", "H", "F", "O"]
A_PROOF_FRESH_HOURS = 36.0
B_LOCK_HEARTBEAT_FRESH_SECONDS = 900.0
H_MANAGER_LAYER_COMPLETE_PATH = Path("sellerone_manager/project_threads/PHASE_4_H_MANAGER_LAYER_COMPLETE.md")


@dataclass(frozen=True)
class FlowConfig:
    flow: str
    flow_name: str
    rollout_rank: int
    expectation_path: str
    checklist_path: str
    split_checklist_path: str
    manifest_root: str
    proof_rule: str
    allowed_scope: str
    forbidden_actions: str
    notes: str


FLOW_CONFIGS: dict[str, FlowConfig] = {
    "A": FlowConfig(
        flow="A",
        flow_name="A Daily Orchestration",
        rollout_rank=1,
        expectation_path="project_control/EXPECTATIONS/A_cycle_expectations.md",
        checklist_path="out/cycle_alerts/checklist_A.csv",
        split_checklist_path="out/cycle_alerts/checklist_A_split.csv",
        manifest_root="out/manifests/A",
        proof_rule="Use the next A-owned run or an explicitly approved A-owned proof window; do not run A015 ad hoc as proof.",
        allowed_scope="manager classification, A expectation mapping, A proof planning, and scoped Codex repair task creation",
        forbidden_actions="no ad hoc A015 proof; no worker cycle run; no B overlap; no legacy Sheet write; no local DB alignment; no pricing change",
        notes="A is the first rollout section because it is the daily upstream base.",
    ),
    "B": FlowConfig(
        flow="B",
        flow_name="B Daytime Orders And Tokens",
        rollout_rank=2,
        expectation_path="project_control/EXPECTATIONS/B_cycle_expectations.md",
        checklist_path="out/cycle_alerts/checklist_B.csv",
        split_checklist_path="out/cycle_alerts/checklist_B_split.csv",
        manifest_root="out/manifests/B",
        proof_rule="Use B independent MOT proof first. Use B maintenance handoff and a boundary-safe B_RUN_ONCE proof only when a manual B proof is approved.",
        allowed_scope="manager classification, B expectation mapping, B proof planning, and scoped Codex repair task creation",
        forbidden_actions="no overlapping B run; no worker restart; no legacy Sheet write; no token/data correction without approved task",
        notes="B must preserve maintenance handoff safety before any repair proof.",
    ),
    "E": FlowConfig(
        flow="E",
        flow_name="E Analytics",
        rollout_rank=3,
        expectation_path="project_control/EXPECTATIONS/E_cycle_expectations.md",
        checklist_path="out/systems/M/hourly_mot_E.csv",
        split_checklist_path="",
        manifest_root="out/manifests/E",
        proof_rule="Use E-owned run logs and E-scoped health; keep E proof separate from global health.",
        allowed_scope="manager classification, E expectation mapping, E proof summary planning, and scoped Codex repair task creation",
        forbidden_actions="no publish enablement; no legacy Sheet write; no worker run unless separately approved as E-owned proof",
        notes="E should separate clean analytics state from missing proof or stale output state.",
    ),
    "H": FlowConfig(
        flow="H",
        flow_name="H Repricing Runtime",
        rollout_rank=4,
        expectation_path="project_control/EXPECTATIONS/H_cycle_expectations.md",
        checklist_path="out/cycle_alerts/checklist_H.csv",
        split_checklist_path="out/cycle_alerts/checklist_H_split.csv",
        manifest_root="out/manifests/H",
        proof_rule="Use guarded H isolation or scheduler-owned proof; confirm terminal and publish truth before claiming success.",
        allowed_scope="manager classification, H expectation mapping, H repair package creation, and proof planning",
        forbidden_actions=(
            "no live H overlap outside a manager-approved proof window; no price write change; "
            "no scheduler ownership change outside controlled technical pause/resume proof; no worker run without approved H proof window"
        ),
        notes="H remains high-risk until stability evidence is current and clean.",
    ),
    "F": FlowConfig(
        flow="F",
        flow_name="F Price List Manager",
        rollout_rank=5,
        expectation_path="project_control/EXPECTATIONS/F_cycle_expectations.md",
        checklist_path="out/systems/M/hourly_mot_F.csv",
        split_checklist_path="",
        manifest_root="out/systems/M/self_organisation",
        proof_rule="Use manager-owned F report outputs and F-safe proof windows; do not edit F061 queue or run scanner from the manager.",
        allowed_scope="manager classification, F manifest registration, scanner maintenance task packaging, and login/handoff proof planning",
        forbidden_actions="no F061 queue edit; no scanner run; no worker restart; no legacy Sheet write; no pricing change",
        notes="F is controlled by the independent F MOT, not by scanner self-report alone.",
    ),
    "O": FlowConfig(
        flow="O",
        flow_name="O Operations Loop",
        rollout_rank=6,
        expectation_path="project_control/EXPECTATIONS/operations_loop_expectations.md",
        checklist_path="out/cycle_alerts/checklist_O.csv",
        split_checklist_path="",
        manifest_root="out/systems/O/live",
        proof_rule="Treat O as foundation/bridge/proof layers until the connected restock-to-send loop is proven.",
        allowed_scope="manager classification, O expectation mapping, O extension task creation, and proof planning",
        forbidden_actions=(
            "no receiving action; no send-to-Amazon action; no purchase commitment; no legacy Sheet write; "
            "no business decision; controlled H pause/resume is allowed only inside a manager-approved proof packet"
        ),
        notes="O must not be marked complete while it is only scaffolded, bridged, or proof-layered.",
    ),
}


FLOW_FEATURE_PATTERNS: dict[str, dict[str, list[str]]] = {
    "A": {
        "Daily orchestration runner": ["final_state", "recorded_step_count"],
        "Listings refresh": ["a001", "listings"],
        "Catalog refresh": ["a002", "catalog"],
        "Inventory refresh": ["a003", "inventory"],
        "Fees refresh": ["a004", "fees"],
        "Daily intel refresh": ["a016", "daily_intel"],
        "Floor table support": ["a018", "floor"],
        "E cycle trigger": ["run_e_cycle", "e cycle"],
        "Health gate run": ["checklist", "health"],
        "Maintenance handoff safety": ["maintenance"],
    },
    "B": {
        "Daytime loop runner": ["b_cycle", "final_state"],
        "Order collection": ["orders", "b001", "b002"],
        "Backdate order recovery": ["backdate", "recovery", "quarantine"],
        "Per-marketplace future order coverage": ["marketplace", "cursor", "coverage"],
        "Recovery quarantine and duplicate guard": ["quarantine", "duplicate", "merge"],
        "Sellerboard outside comparison": ["sellerboard", "bridge", "reconciliation"],
        "Refund fee shipping ROI bridge": ["refund", "fee", "shipping", "roi"],
        "Token ledger allocation": ["token", "b007"],
        "Order master build": ["order_master", "b004"],
        "P and L daily build": ["pnl", "d001"],
        "Stock and parking refresh": ["stock", "parking"],
        "End-of-cycle health gate": ["checklist", "health"],
        "Maintenance pause and resume": ["maintenance"],
        "Lock and heartbeat safety": ["lock", "heartbeat"],
    },
    "E": {
        "E cycle runner": ["final_state", "e_cycle"],
        "Sales velocity output": ["sales_velocity", "e001"],
        "ROI snapshot output": ["roi_snapshot", "e002"],
        "Restock signal output": ["restock", "e003"],
        "Performance summary output": ["performance_summary", "e004"],
        "Study report output": ["study_report", "e005"],
        "Cadence control": ["cadence"],
        "Optional publishing path": ["publish", "e010"],
        "Health profile evidence": ["checklist", "health"],
    },
    "H": {
        "H launcher and guard runtime": ["h_cycle", "guard", "launcher"],
        "Offer and market collection": ["offer", "market", "listing_offer"],
        "Repricing decision logic": ["repricing", "h110", "strategy"],
        "Publish updates": ["publish", "terminal"],
        "Runtime lock safety": ["lock", "heartbeat"],
        "Boundary truth handling": ["boundary", "finalization", "terminal"],
        "Health reporting": ["checklist", "health"],
        "Storage self-cleaning": ["storage", "staged"],
    },
    "O": {
        "Restock Advisor": ["restock", "o001", "o002", "o003"],
        "Human approval gate": ["approval", "decision"],
        "Purchase order creation": ["purchase_order", "o100"],
        "Ordered stock tracking": ["ordered", "receiving"],
        "Inventory receiving": ["receiving"],
        "Send To Amazon flow": ["send_to_amazon", "o300"],
        "Closed-loop feedback": ["feedback", "a/b/e"],
        "Single workflow view": ["ui", "workflow"],
    },
}

B_EXACT_FEATURE_CHECKS: dict[str, list[str]] = {
    "Daytime loop runner": [
        "b_latest_manifest",
        "b_worker_owner",
        "b_supervisor_owner",
        "b_maintenance_marker_state",
    ],
    "Order collection": [
        "b_orders_all",
        "b_order_items_all",
    ],
    "Backdate order recovery": [
        "b_backdate_recovery_quarantine",
        "b_recovery_duplicate_and_merge_guard",
        "b_recovery_proof_labels",
        "b_order_promotion_preview",
        "b_order_promotion_live_chain",
    ],
    "Per-marketplace future order coverage": [
        "b_future_marketplace_order_cursors",
        "b_marketplace_shared_cursor_risk",
    ],
    "Recovery quarantine and duplicate guard": [
        "b_backdate_recovery_quarantine",
        "b_recovery_duplicate_and_merge_guard",
        "b_recovery_proof_labels",
        "b_order_promotion_preview",
    ],
    "Sellerboard outside comparison": [
        "b_sellerboard_bridge_report",
        "b_sellerboard_bridge_schema",
        "b_sellerboard_order_reconciliation",
        "b_marketplace_coverage_report",
        "b_marketplace_sellerboard_gaps",
    ],
    "Sellerboard daily email intake": [
        "b_sellerboard_email_admin_inbox_access",
        "b_sellerboard_email_attachment_arrived",
        "b_sellerboard_email_attachment_format",
        "b_sellerboard_email_attachment_freshness",
        "b_sellerboard_email_storage_cleanup_guard",
    ],
    "Refund fee shipping ROI bridge": [
        "b_refund_pnl_roi_api_proof",
        "b_refund_return_token_bridge",
        "b_return_token_matching_audit",
        "b_return_token_repair_preview",
        "b_refund_token_reproof_preview",
        "b_sellerboard_refund_fee_roi_bridge",
    ],
    "Token ledger allocation": [
        "b_token_ledger_live",
        "b_token_cogs_ledger",
        "b_token_shortages_by_sku",
    ],
    "Order master build": [
        "b_order_master",
    ],
    "P and L daily build": [
        "b_pnl_daily",
    ],
    "Stock and parking refresh": [
        "b_stock_snapshot_latest",
        "b_parked_skus",
    ],
    "End-of-cycle health gate": [
        "b_manifest_gate",
        "b_old_checklist_clue",
    ],
    "Maintenance pause and resume": [
        "b_maintenance_marker_state",
    ],
    "B Management readiness gate": [
        "b_management_ready_for_maintenance",
    ],
    "B order truth completion gate": [
        "b_order_truth_completion",
    ],
}

H_EXACT_FEATURE_CHECKS: dict[str, list[str]] = {
    "H launcher and guard runtime": [
        "h_latest_manifest_state",
        "h_lock_and_heartbeat_state",
    ],
    "Offer and market collection": [
        "h_market_context_proof",
    ],
    "Repricing decision logic": [
        "h_decision_execution_rows",
        "h_floor_ceiling_safety_fields",
        "h_market_context_proof",
    ],
    "Publish updates": [
        "h_terminal_publish_truth",
    ],
    "Runtime lock safety": [
        "h_lock_and_heartbeat_state",
    ],
    "Boundary truth handling": [
        "h_boundary_finalizer_truth",
        "h_terminal_publish_truth",
    ],
    "10-run reliability window": [
        "h_reliability_window",
    ],
    "Health reporting": [
        "h_health_snapshot_as_clue",
    ],
    "Storage self-cleaning": [
        "h_storage_cleanup_safety",
    ],
}

E_EXACT_FEATURE_CHECKS: dict[str, list[str]] = {
    "E cycle runner": [
        "e_latest_manifest",
        "e_run_log_success",
        "e_cadence_control",
        "e_input_readiness",
        "e_core_outputs_fresh",
        "e_lock_state",
    ],
    "Sales velocity output": [
        "e_core_outputs_fresh",
        "e_core_row_counts_believable",
        "e_schema_contracts",
    ],
    "ROI snapshot output": [
        "e_core_outputs_fresh",
        "e_core_row_counts_believable",
        "e_schema_contracts",
        "e_cross_output_alignment",
        "e_refund_roi_proof_fields",
    ],
    "Restock signal output": [
        "e_core_outputs_fresh",
        "e_core_row_counts_believable",
        "e_schema_contracts",
        "e_cross_output_alignment",
        "e_confidence_fields_live",
        "e_coverage_summary_live",
        "e_restock_profit_guard",
    ],
    "Performance summary output": [
        "e_core_outputs_fresh",
        "e_core_row_counts_believable",
        "e_schema_contracts",
        "e_cross_output_alignment",
        "e_confidence_fields_live",
        "e_refund_roi_proof_fields",
        "e_restock_profit_guard",
    ],
    "Study report output": [
        "e_core_outputs_fresh",
        "e_core_row_counts_believable",
        "e_schema_contracts",
        "e_cross_output_alignment",
        "e_confidence_fields_live",
        "e_coverage_summary_live",
    ],
    "Cadence control": [
        "e_cadence_control",
    ],
    "Optional publishing path": [
        "e_optional_publish_proof",
    ],
    "Health profile evidence": [
        "e_health_profile_current",
    ],
}

F_EXACT_FEATURE_CHECKS: dict[str, list[str]] = {
    "Manager front door and snapshot": [
        "f_manager_snapshot_current",
        "f_manager_registration_coverage",
    ],
    "Live owner and scanner heartbeat": [
        "f_live_owner_status",
        "f_child_scanner_heartbeat",
    ],
    "Storage drift safety": [
        "f_storage_drift_clear",
    ],
    "Supplier source intake proof": [
        "f_source_intake_chain_proof",
        "f_email_price_list_source_proof",
        "f_url_source_download_proof",
    ],
    "Queue recommendation and handoff controls": [
        "f_queue_recommendation_explainable",
        "f_queue_handoff_control_proof",
    ],
    "Login and browser control": [
        "f_login_mode_state",
        "f_bbp_account_login_state",
        "f_seller_central_eligibility_auth_state",
        "f_visible_login_control_proof",
    ],
    "Recovery and parked-row protection": [
        "f_recovery_progress_proof",
        "f_parked_decision_rows",
    ],
    "Review and production-line readiness": [
        "f_review_handoff_ai_gate",
        "f_review_ai_production_readiness",
        "f_production_line_stage_health",
    ],
}

E_BUSINESS_WARNING_CHECKS: dict[str, list[str]] = {
    "Performance summary output": ["e_roi_coverage"],
    "Study report output": ["e_daily_truth_coverage"],
}

E_OPTIONAL_NOT_REQUIRED_CHECKS = {
    "Optional publishing path": {"e_optional_publish_proof"},
}


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items()} for row in reader], list(reader.fieldnames or [])


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _health_row(check: str, status: str, value: str, notes: str, observed_utc: str, source_path: str | Path) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": value,
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _path(root: Path, rel_path: str) -> Path:
    return root / rel_path if rel_path else root / "__not_configured__"


def _parse_expectations(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 4 or cells[0].lower() == "feature":
            continue
        rows.append(
            {
                "feature": cells[0],
                "description": cells[1],
                "expected_status": cells[2],
                "notes": cells[3],
            }
        )
    return rows


def _latest_manifest(root: Path, flow: str) -> tuple[dict[str, Any], Path | None]:
    manifest_root = root / FLOW_CONFIGS[flow].manifest_root
    if not manifest_root.exists() or not manifest_root.is_dir():
        return {}, None
    candidates = sorted(manifest_root.rglob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if flow == "F":
            return payload, candidate
        if str(payload.get("cycle", "")).upper() == flow:
            return payload, candidate
    return {}, candidates[0] if candidates else None


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _file_age_hours(path: Path, observed_utc: str) -> float | None:
    if not path.exists():
        return None
    now = _parse_utc(observed_utc) or datetime.now(timezone.utc)
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None
    return max((now - mtime).total_seconds() / 3600.0, 0.0)


def _csv_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            return sum(1 for _row in reader)
    except OSError:
        return None


def _sqlite_table_count(root: Path, table: str) -> tuple[str, str]:
    db_path = root / "out" / "sql" / "sellerone_dev.sqlite3"
    if not db_path.exists():
        return "missing_database", ""
    try:
        con = sqlite3.connect(str(db_path))
    except sqlite3.Error as exc:
        return f"open_error:{exc.__class__.__name__}", ""
    try:
        table_row = con.execute(
            "select name from sqlite_master where type='table' and name=?",
            (table,),
        ).fetchone()
        if table_row is None:
            return "missing_table", ""
        count = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        return "rows_present" if count > 0 else "empty_table", str(count)
    except sqlite3.Error as exc:
        return f"read_error:{exc.__class__.__name__}", ""
    finally:
        con.close()


def _row_status_counts(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fail_statuses = {"fail", "failed", "blocked"}
    warn_statuses = {"warn", "warning", "stale_evidence"}
    fail_rows: list[dict[str, str]] = []
    warn_rows: list[dict[str, str]] = []
    stale_rows: list[dict[str, str]] = []
    for row in rows:
        status = row.get("status", "").strip().lower()
        if status in fail_statuses:
            fail_rows.append(row)
        elif status in warn_statuses:
            warn_rows.append(row)
        notes = row.get("notes", "").lower()
        check = row.get("check", "").lower()
        if "stale" in notes or "freshness" in check and status in warn_statuses:
            stale_rows.append(row)
    return fail_rows, warn_rows, stale_rows


def _row_requires_luke(row: dict[str, str]) -> bool:
    status = row.get("status", "").strip().lower()
    return (
        row.get("luke_action_required", "").strip() == "1"
        or row.get("needs_luke_decision", "").strip() == "1"
        or status in {"blocked_needs_luke", "blocked_needs_user_decision", "decision_needed"}
    )


def _manifest_steps(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    steps = manifest.get("steps", [])
    return steps if isinstance(steps, list) else []


def _step_search_text(step: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ["name", "script_or_function", "notes", "step_status", "verification_status"]:
        parts.append(str(step.get(key, "")))
    outputs = step.get("outputs", [])
    if isinstance(outputs, list):
        parts.extend(str(output) for output in outputs)
    return " ".join(parts).lower()


def _row_search_text(row: dict[str, str]) -> str:
    return " ".join(str(value) for value in row.values()).lower()


def _feature_patterns(flow: str, feature: str) -> list[str]:
    for key, patterns in FLOW_FEATURE_PATTERNS.get(flow, {}).items():
        if key.lower() == feature.lower():
            return patterns
    words = re.findall(r"[a-z0-9]+", feature.lower())
    return [word for word in words if len(word) > 3]


def _feature_reconciliation(
    *,
    root: Path,
    flow: str,
    expectation: dict[str, str],
    checklist_rows: list[dict[str, str]],
    manifest: dict[str, Any],
    manifest_path: Path | None,
    source_path: Path,
    observed_utc: str,
) -> dict[str, str]:
    feature = expectation.get("feature", "")
    if flow == "A" and feature == "Floor table support":
        return _a_floor_table_reconciliation(
            root=root,
            expectation=expectation,
            source_path=source_path,
            observed_utc=observed_utc,
        )
    if flow == "A" and feature == "Maintenance handoff safety":
        return _a_maintenance_handoff_reconciliation(
            root=root,
            expectation=expectation,
            manifest=manifest,
            manifest_path=manifest_path,
            source_path=source_path,
            observed_utc=observed_utc,
        )
    if flow == "B" and feature == "Lock and heartbeat safety":
        return _b_lock_heartbeat_reconciliation(
            root=root,
            expectation=expectation,
            source_path=source_path,
            observed_utc=observed_utc,
        )
    if flow == "B" and feature in B_EXACT_FEATURE_CHECKS:
        return _exact_feature_reconciliation(
            flow="B",
            exact_feature_checks=B_EXACT_FEATURE_CHECKS,
            expectation=expectation,
            checklist_rows=checklist_rows,
            source_path=source_path,
            observed_utc=observed_utc,
        )
    if flow == "E" and feature in E_EXACT_FEATURE_CHECKS:
        return _exact_feature_reconciliation(
            flow="E",
            exact_feature_checks=E_EXACT_FEATURE_CHECKS,
            expectation=expectation,
            checklist_rows=checklist_rows,
            source_path=source_path,
            observed_utc=observed_utc,
        )
    if flow == "H" and feature in H_EXACT_FEATURE_CHECKS:
        return _exact_feature_reconciliation(
            flow="H",
            exact_feature_checks=H_EXACT_FEATURE_CHECKS,
            expectation=expectation,
            checklist_rows=checklist_rows,
            source_path=source_path,
            observed_utc=observed_utc,
        )
    if flow == "F" and feature in F_EXACT_FEATURE_CHECKS:
        return _exact_feature_reconciliation(
            flow="F",
            exact_feature_checks=F_EXACT_FEATURE_CHECKS,
            expectation=expectation,
            checklist_rows=checklist_rows,
            source_path=source_path,
            observed_utc=observed_utc,
        )
    expected_status = expectation.get("expected_status", "")
    expected_lower = expected_status.strip().lower()
    patterns = _feature_patterns(flow, feature)
    matched_checks = [
        row for row in checklist_rows if any(pattern.lower() in _row_search_text(row) for pattern in patterns)
    ]
    matched_steps = [
        step for step in _manifest_steps(manifest) if any(pattern.lower() in _step_search_text(step) for pattern in patterns)
    ]

    if expected_lower in {"planned", "not started"}:
        manager_status = "not_started"
        evidence_status = "not_started"
        notes = "Expectation file does not mark this as delivered runtime yet."
    elif matched_checks:
        statuses = {row.get("status", "").strip().lower() for row in matched_checks}
        if statuses & {"fail", "failed", "blocked"}:
            manager_status = "blocked"
            evidence_status = "fail"
            notes = "Matching health evidence has an active fail/blocker."
        elif statuses & {"warn", "warning", "stale_evidence"}:
            manager_status = "not_verified"
            evidence_status = "warn"
            notes = "Matching health evidence is warning or stale."
        elif statuses == {"ok"} or "ok" in statuses:
            manager_status = "covered"
            evidence_status = "ok"
            notes = "Matching health evidence is ok."
        elif statuses & {"not_checked"}:
            manager_status = "not_verified"
            evidence_status = "not_verified"
            notes = "Matching manager evidence is not yet proven."
        else:
            manager_status = "not_verified"
            evidence_status = "unknown"
            notes = "Matching health evidence has an unclassified status."
    elif matched_steps:
        bad_steps = [
            step
            for step in matched_steps
            if str(step.get("rc", "0")) not in {"", "0"} or str(step.get("step_status", "")).lower() in {"failed", "error"}
        ]
        skipped_steps = [step for step in matched_steps if "skipped" in str(step.get("step_status", "")).lower()]
        if bad_steps:
            manager_status = "incorrect"
            evidence_status = "fail"
            notes = "Matching manifest step has nonzero return code or failed status."
        elif skipped_steps:
            manager_status = "not_verified"
            evidence_status = "skipped"
            notes = "Matching manifest step exists but was skipped, so it is not counted as covered."
        else:
            manager_status = "covered"
            evidence_status = "manifest"
            notes = "Matching manifest step completed without a recorded fail."
    else:
        manager_status = "not_verified"
        evidence_status = "missing"
        notes = "No manager-readable evidence is mapped to this expectation yet."

    evidence_checks = ",".join(row.get("check", "") for row in matched_checks if row.get("check"))
    if not evidence_checks and matched_steps:
        evidence_checks = ",".join(str(step.get("name", "")) for step in matched_steps if step.get("name"))
    return {
        "observed_utc": observed_utc,
        "flow": flow,
        "feature": feature,
        "expected_status": expected_status,
        "manager_status": manager_status,
        "evidence_status": evidence_status,
        "evidence_checks": evidence_checks,
        "notes": notes,
        "source_path": str(source_path),
    }


def _exact_feature_reconciliation(
    *,
    flow: str,
    exact_feature_checks: dict[str, list[str]],
    expectation: dict[str, str],
    checklist_rows: list[dict[str, str]],
    source_path: Path,
    observed_utc: str,
) -> dict[str, str]:
    feature = expectation.get("feature", "")
    expected_status = expectation.get("expected_status", "")
    checks = exact_feature_checks.get(feature, [])
    by_check = {row.get("check", ""): row for row in checklist_rows if row.get("check")}
    matched_rows = [by_check[check] for check in checks if check in by_check]
    missing_checks = [check for check in checks if check not in by_check]
    statuses = {row.get("status", "").strip().lower() for row in matched_rows}
    luke_decision_rows = [
        row.get("check", "")
        for row in matched_rows
        if row.get("luke_action_required") == "1" or row.get("status", "").strip().lower() == "decision_needed"
    ]
    not_checked_rows = [
        row.get("check", "")
        for row in matched_rows
        if row.get("status", "").strip().lower() == "not_checked"
    ]
    optional_not_required = E_OPTIONAL_NOT_REQUIRED_CHECKS.get(feature, set()) if flow == "E" else set()

    if not checks:
        manager_status = "not_verified"
        evidence_status = "missing"
        notes = f"No exact {flow} manager proof mapping exists for this expectation yet."
    elif not matched_rows:
        manager_status = "not_verified"
        evidence_status = "missing"
        notes = f"Mapped {flow} MOT rows are not present yet."
    elif luke_decision_rows:
        manager_status = "blocked"
        evidence_status = "decision_needed"
        notes = f"Mapped {flow} MOT row needs a protected decision: {','.join(luke_decision_rows)}."
    elif statuses & {"fail", "failed", "blocked"}:
        manager_status = "blocked"
        evidence_status = "fail"
        failed = [row.get("check", "") for row in matched_rows if row.get("status", "").strip().lower() in {"fail", "failed", "blocked"}]
        notes = f"Exact {flow} MOT proof has an active fail/blocker: {','.join(failed)}."
    elif statuses & {"warn", "warning", "stale_evidence"}:
        manager_status = "not_verified"
        evidence_status = "warn"
        warned = [row.get("check", "") for row in matched_rows if row.get("status", "").strip().lower() in {"warn", "warning", "stale_evidence"}]
        notes = f"Exact {flow} MOT proof is warning or stale: {','.join(warned)}."
    elif not_checked_rows and set(not_checked_rows).issubset(optional_not_required) and not missing_checks:
        manager_status = "covered"
        evidence_status = "not_required"
        notes = "Optional E publish proof is visible and safely not required until publishing is enabled."
    elif statuses & {"not_checked"} or missing_checks:
        manager_status = "not_verified"
        evidence_status = "not_verified"
        details = []
        if not_checked_rows:
            details.append(f"not_checked={','.join(not_checked_rows)}")
        if missing_checks:
            details.append(f"missing={','.join(missing_checks)}")
        notes = f"Exact {flow} MOT proof is not fully active yet." + (f" {';'.join(details)}." if details else "")
    elif "ok" in statuses:
        manager_status = "covered"
        evidence_status = "ok"
        notes = f"Exact {flow} MOT proof is ok."
    else:
        manager_status = "not_verified"
        evidence_status = "unknown"
        notes = f"Exact {flow} MOT proof has an unclassified status."

    business_warnings = [
        check
        for check in (E_BUSINESS_WARNING_CHECKS.get(feature, []) if flow == "E" else [])
        if by_check.get(check, {}).get("status", "").strip().lower() in {"warn", "warning", "stale_evidence"}
    ]
    if manager_status == "covered" and business_warnings:
        notes = f"{notes} Business confidence warning remains tracked separately: {','.join(business_warnings)}."

    return {
        "observed_utc": observed_utc,
        "flow": flow,
        "feature": feature,
        "expected_status": expected_status,
        "manager_status": manager_status,
        "evidence_status": evidence_status,
        "evidence_checks": ",".join(check for check in checks if check in by_check),
        "notes": notes,
        "source_path": str(source_path),
    }


def _a_floor_table_reconciliation(
    *,
    root: Path,
    expectation: dict[str, str],
    source_path: Path,
    observed_utc: str,
) -> dict[str, str]:
    floor_path = root / "out" / "phase1_floor_table_latest.csv"
    rows = _csv_row_count(floor_path)
    age = _file_age_hours(floor_path, observed_utc)
    sql_status, sql_rows = _sqlite_table_count(root, "a_phase1_floor_table_latest")
    evidence_checks = "a018_phase1_floor_table,a018_sql_phase1_floor_table"
    if rows is None:
        manager_status = "not_verified"
        evidence_status = "missing"
        notes = "A018 is proof-only in this batch and no floor-table CSV proof is available yet."
    elif rows < 1:
        manager_status = "not_verified"
        evidence_status = "empty"
        notes = "A018 floor-table CSV exists but has no rows."
    elif age is None or age >= A_PROOF_FRESH_HOURS:
        manager_status = "not_verified"
        evidence_status = "stale"
        notes = f"A018 floor-table CSV is stale or unreadable; age_hours={'' if age is None else f'{age:.2f}'}."
    elif sql_status != "rows_present":
        manager_status = "not_verified"
        evidence_status = sql_status
        notes = "A018 CSV is fresh, but the optional SQL proof is not present with rows."
    else:
        manager_status = "covered"
        evidence_status = "ok"
        notes = f"A018 proof-only CSV is fresh with {rows} rows and SQL table has {sql_rows} rows."
    return {
        "observed_utc": observed_utc,
        "flow": "A",
        "feature": expectation.get("feature", ""),
        "expected_status": expectation.get("expected_status", ""),
        "manager_status": manager_status,
        "evidence_status": evidence_status,
        "evidence_checks": evidence_checks,
        "notes": notes,
        "source_path": str(source_path),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_read_error": "1"}
    return payload if isinstance(payload, dict) else {"_read_error": "1"}


def _parse_pipe_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for index, token in enumerate(str(text or "").replace("\n", "|").split("|")):
        part = token.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            fields[key.strip()] = value.strip()
        elif index == 0:
            fields["owner_label"] = part
    return fields


def _read_lock_fields(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return _parse_pipe_fields(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return {"_read_error": "1"}


def _heartbeat_age_seconds(fields: dict[str, str], observed_utc: str) -> float | None:
    heartbeat = fields.get("heartbeat") or fields.get("utc") or fields.get("ts")
    parsed = _parse_utc(heartbeat)
    now = _parse_utc(observed_utc) or datetime.now(timezone.utc)
    if parsed is None:
        return None
    return max((now - parsed).total_seconds(), 0.0)


def _b_lock_heartbeat_reconciliation(
    *,
    root: Path,
    expectation: dict[str, str],
    source_path: Path,
    observed_utc: str,
) -> dict[str, str]:
    worker_paths = [
        root / "out" / "systems" / "B" / "live" / "B_cycle.lock",
        root / "out" / "B_cycle.lock",
    ]
    worker_states: list[tuple[Path, dict[str, str], float | None]] = []
    for path in worker_paths:
        fields = _read_lock_fields(path)
        if fields:
            worker_states.append((path, fields, _heartbeat_age_seconds(fields, observed_utc)))
    live_workers = [
        (path, fields, age)
        for path, fields, age in worker_states
        if age is not None and age < B_LOCK_HEARTBEAT_FRESH_SECONDS
    ]
    supervisor_path = root / "out" / "systems" / "B" / "live" / "B_supervisor.lock"
    supervisor_fields = _read_lock_fields(supervisor_path)
    supervisor_age = _heartbeat_age_seconds(supervisor_fields, observed_utc) if supervisor_fields else None
    supervisor_live = supervisor_age is not None and supervisor_age < B_LOCK_HEARTBEAT_FRESH_SECONDS

    if len(live_workers) > 1:
        manager_status = "blocked"
        evidence_status = "fail"
        notes = "More than one fresh B worker lock exists, so single ownership is not proven."
    elif not live_workers:
        manager_status = "not_verified"
        evidence_status = "missing"
        notes = "No fresh B worker heartbeat proof exists yet."
    elif not supervisor_live:
        manager_status = "not_verified"
        evidence_status = "missing"
        notes = "B worker heartbeat is fresh, but supervisor heartbeat proof is missing or stale."
    else:
        manager_status = "covered"
        evidence_status = "ok"
        worker_path, _fields, worker_age = live_workers[0]
        notes = (
            "B has one fresh worker heartbeat and one fresh supervisor heartbeat "
            f"(worker_age_seconds={worker_age:.2f};supervisor_age_seconds={supervisor_age:.2f})."
        )
    return {
        "observed_utc": observed_utc,
        "flow": "B",
        "feature": expectation.get("feature", ""),
        "expected_status": expectation.get("expected_status", ""),
        "manager_status": manager_status,
        "evidence_status": evidence_status,
        "evidence_checks": "b_worker_owner,b_supervisor_owner",
        "notes": notes,
        "source_path": ";".join(str(path) for path in [*worker_paths, supervisor_path]) or str(source_path),
    }


def _a_maintenance_handoff_reconciliation(
    *,
    root: Path,
    expectation: dict[str, str],
    manifest: dict[str, Any],
    manifest_path: Path | None,
    source_path: Path,
    observed_utc: str,
) -> dict[str, str]:
    proof_path = root / "out" / "systems" / "A" / "live" / "a_maintenance_handoff_latest.json"
    payload = _read_json(proof_path)
    latest_run_id = str(manifest.get("run_id", "") or "").strip()
    proof_run_id = str(payload.get("final_run_id", "") or "").strip()
    proof_status = str(payload.get("proof_status", "") or "").strip()
    cleanup = payload.get("cleanup_evidence", {})
    cleanup_clear = bool(cleanup.get("all_clear", False)) if isinstance(cleanup, dict) else False
    if not payload:
        manager_status = "not_verified"
        evidence_status = "missing"
        notes = "No durable A maintenance handoff proof exists yet."
    elif payload.get("_read_error") == "1":
        manager_status = "blocked"
        evidence_status = "fail"
        notes = "A maintenance handoff proof exists but cannot be read."
    elif _a_interrupted_pending_normal_proof(manifest, payload):
        manager_status = "not_verified"
        evidence_status = "interrupted"
        notes = "A proof run was interrupted after safe handoff evidence and cleanup; next normal A-owned run must prove completion."
    elif proof_status != "ok":
        manager_status = "blocked"
        evidence_status = "fail"
        notes = "A maintenance handoff proof recorded an unsafe or failed handoff."
    elif latest_run_id and proof_run_id != latest_run_id:
        manager_status = "not_verified"
        evidence_status = "stale"
        notes = "A maintenance handoff proof does not match the latest A manifest run id."
    elif not cleanup_clear:
        manager_status = "blocked"
        evidence_status = "fail"
        notes = "A maintenance handoff proof says maintenance markers were not fully cleared."
    else:
        manager_status = "covered"
        evidence_status = "ok"
        notes = "Latest A manifest has matching maintenance handoff proof and cleanup evidence."
    evidence_path = str(proof_path if proof_path.exists() else (manifest_path or proof_path))
    return {
        "observed_utc": observed_utc,
        "flow": "A",
        "feature": expectation.get("feature", ""),
        "expected_status": expectation.get("expected_status", ""),
        "manager_status": manager_status,
        "evidence_status": evidence_status,
        "evidence_checks": "a_maintenance_handoff_proof",
        "notes": notes,
        "source_path": evidence_path or str(source_path),
    }


def _a_interrupted_pending_normal_proof(manifest: dict[str, Any], payload: dict[str, Any]) -> bool:
    if not manifest or not payload or payload.get("_read_error") == "1":
        return False
    latest_run_id = str(manifest.get("run_id", "") or "").strip()
    proof_run_id = str(payload.get("final_run_id", "") or "").strip()
    if latest_run_id and proof_run_id and latest_run_id != proof_run_id:
        return False
    manifest_state = str(manifest.get("final_state", "") or "").strip().lower()
    payload_state = str(payload.get("final_state", "") or "").strip().lower()
    final_exit_code = str(payload.get("final_exit_code", "") or "").strip()
    cleanup = payload.get("cleanup_evidence", {})
    cleanup_clear = bool(cleanup.get("all_clear", False)) if isinstance(cleanup, dict) else False
    b_ready = payload.get("b_ready_evidence", {})
    a_active = payload.get("a_active_evidence", {})
    b_ready_seen = bool(b_ready.get("exists", False)) if isinstance(b_ready, dict) else False
    a_active_seen = bool(a_active.get("exists", False)) if isinstance(a_active, dict) else False
    interrupted_step = False
    for step in manifest.get("steps", []):
        if not isinstance(step, dict):
            continue
        step_text = " ".join(
            str(step.get(key, "") or "")
            for key in ("rc", "notes", "step_status", "verification_status")
        ).lower()
        if "interrupted" in step_text or str(step.get("rc", "")).strip() in {"130", "-1073741510"}:
            interrupted_step = True
            break
    return (
        manifest_state in {"partial", "interrupted"}
        and payload_state in {"partial", "interrupted", "failed", ""}
        and cleanup_clear
        and b_ready_seen
        and a_active_seen
        and (final_exit_code == "130" or interrupted_step)
    )


def _extra_o_reconciliation(root: Path, observed_utc: str) -> list[dict[str, str]]:
    outputs = {
        "O foundation restock source view": "out/systems/O/live/restock_source_view.csv",
        "O legacy purchase bridge": "out/systems/O/live/legacy_purchase_list_bridge.csv",
        "O price-proof layer": "out/systems/O/live/restock_profit_checks_live.csv",
        "O market-refresh bridge": "out/systems/O/live/restock_market_refresh_candidates_live.csv",
    }
    rows: list[dict[str, str]] = []
    for feature, rel_path in outputs.items():
        path = root / rel_path
        rows.append(
            {
                "observed_utc": observed_utc,
                "flow": "O",
                "feature": feature,
                "expected_status": "foundation_or_bridge",
                "manager_status": "covered" if path.exists() else "not_verified",
                "evidence_status": "exists" if path.exists() else "missing",
                "evidence_checks": rel_path,
                "notes": "This is not full operations-loop completion; it is a foundation, bridge, or proof layer.",
                "source_path": rel_path,
            }
        )
    return rows


def _flow_due_decisions(root: Path, flow: str) -> list[dict[str, str]]:
    path = root / "project_control" / "DUE_CHECK_REGISTER.csv"
    rows, _fields = read_csv_rows(path)
    decisions: list[dict[str, str]] = []
    for row in rows:
        owner_flow = row.get("owner_flow", "")
        if flow not in [part.strip() for part in owner_flow.split(",")]:
            continue
        if row.get("status", "") != "open":
            continue
        result = row.get("last_result", "").lower()
        if "needs_user_decision" in result or "blocked_waiting_user_decision" in result:
            decision_text = " ".join(
                str(row.get(column, "") or "")
                for column in ("check_id", "title", "trigger", "success_condition", "failure_action", "last_result", "notes")
            )
            if quiet_autonomy_active(root) and (
                is_controlled_technical_pause_text(decision_text)
                or is_quiet_autonomy_parked_decision_text(decision_text)
            ):
                continue
            if controlled_technical_pause_allowed(root) and is_controlled_technical_pause_text(decision_text):
                continue
            decisions.append(row)
    return decisions


def _h_manager_layer_complete(root: Path) -> bool:
    return (root / H_MANAGER_LAYER_COMPLETE_PATH).exists()


def _h_warn_classification_packaged(root: Path) -> bool:
    package_root = root / "plans" / "active"
    if not package_root.exists():
        return False
    return any(package_root.glob("**/H_REPAIR_PACKAGE_MGR_H_classification_out_systems_M_hourly_mot*.md"))


def _flow_warn_classification_packet_exists(root: Path, flow: str) -> bool:
    path = root / "out" / "systems" / "M" / "approved_task_packets.csv"
    rows, _fields = read_csv_rows(path)
    target_id = f"MGR_{flow.upper()}_classification_out_systems_M_hourly_mot"
    active_or_recorded = {
        "approved",
        "in_progress",
        "fixed_needs_retest",
        "retest_failed",
        "proved",
        "parked",
    }
    return any(
        row.get("task_id", "") == target_id and row.get("status", "") in active_or_recorded
        for row in rows
    )


def _manager_proof_gap_packaged(root: Path, flow: str) -> bool:
    package_root = root / "plans" / "active"
    if not package_root.exists():
        return False
    flow_upper = flow.upper()
    return any(package_root.glob(f"**/{flow_upper}_PROOF_PACKAGE_MGR_{flow_upper}_proof_gap_*.md"))


def _choose_checklist_rows(
    *,
    checklist_path: Path,
    split_path: Path,
    checklist_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], Path]:
    if not split_rows:
        return checklist_rows, checklist_path
    if not checklist_rows:
        return split_rows, split_path
    try:
        split_mtime = split_path.stat().st_mtime
        checklist_mtime = checklist_path.stat().st_mtime
    except OSError:
        return split_rows, split_path
    if checklist_mtime > split_mtime:
        return checklist_rows, checklist_path
    return split_rows, split_path


def _flow_task_id(flow: str, task_type: str, root_artifact: str) -> str:
    clean_artifact = re.sub(r"[^a-zA-Z0-9]+", "_", root_artifact).strip("_")[:24] or "artifact"
    return f"{flow}_{task_type}_{clean_artifact}"


def _job_ref(flow: str, title: str, task_id: str) -> str:
    flow = str(flow or "M").upper()
    words = re.findall(r"[A-Za-z0-9]+", f"{title} {task_id}".upper().replace("RETURNEDTOKEN", "RETURNED TOKEN"))
    stop = {
        "MOT",
        "MGR",
        "TASK",
        "MANAGER",
        "NEEDS",
        "REPAIR",
        "LUKE",
        "DECISION",
        "PROTECTED",
        "STATUS",
        "STATE",
        "APPLY",
        "LIVE",
        "RETURN",
        "RETURNED",
        "PROOF",
        "PRICE",
        "LIST",
        "LATEST",
        flow,
    }
    tokens: list[str] = []
    for word in words:
        if word in stop or (len(word) == 1 and word.isalpha()):
            continue
        if word not in tokens:
            tokens.append(word)
    if "EMAIL" in tokens and "SOURCE" in tokens:
        tokens = ["EMAIL", "SOURCE"]
    elif "ORIGINAL" in tokens and "TOKEN" in tokens:
        tokens = ["ORIGINAL", "TOKEN"]
    else:
        tokens = tokens[:3]
    return "-".join([flow] + (tokens or ["JOB"]))


def _task_candidate(
    *,
    observed_utc: str,
    flow: str,
    task_type: str,
    priority: str,
    status: str,
    title: str,
    root_artifact: str,
    config: FlowConfig,
    needs_luke_decision: str = "0",
    notes: str = "",
) -> dict[str, str]:
    task_id = _flow_task_id(flow, task_type, root_artifact)
    return {
        "observed_utc": observed_utc,
        "flow": flow,
        "task_id": task_id,
        "job_ref": _job_ref(flow, title, task_id),
        "task_type": task_type,
        "priority": priority,
        "status": status,
        "title": title,
        "root_artifact": root_artifact,
        "allowed_scope": config.allowed_scope,
        "forbidden_actions": config.forbidden_actions,
        "proof_required": config.proof_rule,
        "stop_condition": "Stop after manager classification, task packaging, and proof path are recorded for this flow.",
        "needs_luke_decision": needs_luke_decision,
        "notes": notes,
    }


def _build_flow(
    *,
    root: Path,
    config: FlowConfig,
    observed_utc: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    expectation_path = _path(root, config.expectation_path)
    checklist_path = _path(root, config.checklist_path)
    split_path = _path(root, config.split_checklist_path)
    checklist_rows, _fields = read_csv_rows(checklist_path)
    split_rows, _split_fields = read_csv_rows(split_path) if config.split_checklist_path else ([], [])
    if config.flow == "B":
        b_mot_path = root / "out" / "systems" / "M" / "hourly_mot_B.csv"
        b_mot_rows, _mot_fields = read_csv_rows(b_mot_path)
        evidence_rows, evidence_path = (b_mot_rows, b_mot_path)
    elif config.flow == "H":
        h_mot_path = root / "out" / "systems" / "M" / "hourly_mot_H.csv"
        h_mot_rows, _mot_fields = read_csv_rows(h_mot_path)
        if h_mot_rows:
            evidence_rows, evidence_path = (h_mot_rows, h_mot_path)
        else:
            evidence_rows, evidence_path = _choose_checklist_rows(
                checklist_path=checklist_path,
                split_path=split_path,
                checklist_rows=checklist_rows,
                split_rows=split_rows,
            )
    else:
        evidence_rows, evidence_path = _choose_checklist_rows(
            checklist_path=checklist_path,
            split_path=split_path,
            checklist_rows=checklist_rows,
            split_rows=split_rows,
        )
    try:
        evidence_rel_path = str(evidence_path.relative_to(root))
    except ValueError:
        evidence_rel_path = str(evidence_path)
    manifest, manifest_path = _latest_manifest(root, config.flow)
    expectations = _parse_expectations(expectation_path)

    health_rows = [
        _health_row(
            f"manager_flow_expectations:{config.flow}",
            "ok" if expectations else "warn",
            str(len(expectations)),
            "expectations loaded" if expectations else "expectations missing or no table rows found",
            observed_utc,
            expectation_path,
        ),
        _health_row(
            f"manager_flow_evidence:{config.flow}",
            "ok" if evidence_rows else "warn",
            str(len(evidence_rows)),
            "manager evidence rows loaded" if evidence_rows else "manager evidence missing or empty",
            observed_utc,
            evidence_path,
        ),
    ]
    if manifest_path:
        health_rows.append(
            _health_row(
                f"manager_flow_manifest:{config.flow}",
                "ok",
                manifest.get("final_state", "loaded") if isinstance(manifest, dict) else "loaded",
                "latest manifest loaded",
                observed_utc,
                manifest_path,
            )
        )
    else:
        health_rows.append(
            _health_row(
                f"manager_flow_manifest:{config.flow}",
                "warn",
                "missing",
                "latest manifest not found",
                observed_utc,
                root / config.manifest_root,
            )
        )

    fail_rows, warn_rows, stale_rows = _row_status_counts(evidence_rows)
    repair_fail_rows = [row for row in fail_rows if not _row_requires_luke(row)]
    luke_blocked_fail_rows = [row for row in fail_rows if _row_requires_luke(row)]
    luke_blocked_checks = {row.get("check", "") for row in luke_blocked_fail_rows if row.get("check", "")}
    recon_rows = [
        _feature_reconciliation(
            root=root,
            flow=config.flow,
            expectation=expectation,
            checklist_rows=evidence_rows,
            manifest=manifest,
            manifest_path=manifest_path,
            source_path=expectation_path,
            observed_utc=observed_utc,
        )
        for expectation in expectations
    ]
    if config.flow == "O":
        recon_rows.extend(_extra_o_reconciliation(root, observed_utc))

    not_verified_count = sum(1 for row in recon_rows if row.get("manager_status") in {"not_verified", "incorrect", "blocked"})
    covered_count = sum(1 for row in recon_rows if row.get("manager_status") == "covered")
    blocked_recon_rows = [row for row in recon_rows if row.get("manager_status") == "blocked"]
    decision_recon_rows = [row for row in blocked_recon_rows if row.get("evidence_status") == "decision_needed"]
    repair_blocked_recon_rows = [
        row
        for row in blocked_recon_rows
        if row.get("evidence_status") != "decision_needed"
        and not any(
            check.strip() in luke_blocked_checks
            for check in row.get("evidence_checks", "").split(",")
            if check.strip()
        )
    ]
    due_decisions = _flow_due_decisions(root, config.flow)
    quiet_autonomy = quiet_autonomy_active(root)
    h_repair_parked = quiet_autonomy and config.flow == "H" and bool(fail_rows)
    h_manager_layer_complete = config.flow == "H" and _h_manager_layer_complete(root)
    watch_only_warning = quiet_autonomy and config.flow in {"B", "E"} and bool(warn_rows) and not fail_rows
    f_warn_classification_packet_exists = (
        config.flow == "F" and _flow_warn_classification_packet_exists(root, config.flow)
    )

    status = "ok"
    classification = "calm"
    first_blocker_code = ""
    first_blocker_summary = ""
    if h_repair_parked:
        status = "parked"
        classification = "high_risk_bounded_repair_only" if h_manager_layer_complete else "high_risk_needs_manager_layer"
        first = fail_rows[0]
        first_blocker_code = first.get("check", "active_fail")
        if h_manager_layer_complete:
            first_blocker_summary = (
                "H has independent MOT FAIL evidence. The H manager layer exists, so broad H repair stays parked and only bounded H MOT proof packets should be handled."
            )
        else:
            first_blocker_summary = (
                "H has independent MOT FAIL evidence, so Quiet Autonomy keeps broad H repair parked until bounded H proof packets are handled."
            )
    elif fail_rows:
        status = "blocked"
        classification = "blocker"
        first = fail_rows[0]
        first_blocker_code = first.get("check", "active_fail")
        first_blocker_summary = first.get("notes", "") or f"{config.flow} has active FAIL evidence."
    elif blocked_recon_rows:
        status = "blocked"
        classification = "blocker"
        first = blocked_recon_rows[0]
        first_blocker_code = first.get("evidence_checks", "manager_proof_blocker")
        first_blocker_summary = first.get("notes", "") or f"{config.flow} has blocked manager proof evidence."
    elif warn_rows:
        status = "warn"
        classification = "warning"
        first = warn_rows[0]
        first_blocker_code = first.get("check", "active_warn")
        first_blocker_summary = first.get("notes", "") or f"{config.flow} has active WARN evidence."
    elif not evidence_rows and not manifest:
        status = "not_checked"
        classification = "missing_proof"
        first_blocker_code = "manager_evidence_missing"
        first_blocker_summary = f"No manager-readable runtime evidence is available for {config.flow}."

    task_rows: list[dict[str, str]] = []
    if due_decisions:
        decision = due_decisions[0]
        task_rows.append(
            _task_candidate(
                observed_utc=observed_utc,
                flow=config.flow,
                task_type="user_decision",
                priority="high",
                status="blocked_needs_user_decision",
                title=decision.get("title", f"{config.flow} needs a user decision"),
                root_artifact=decision.get("artifact_path", "project_control/DUE_CHECK_REGISTER.csv"),
                config=config,
                needs_luke_decision="1",
                notes=decision.get("notes", ""),
            )
        )
    if h_repair_parked:
        if not h_manager_layer_complete:
            task_rows.append(
                _task_candidate(
                    observed_utc=observed_utc,
                    flow=config.flow,
                    task_type="proof_gap",
                    priority="high",
                    status="proposed",
                    title="Plan H independent manager/MOT layer",
                    root_artifact=config.expectation_path,
                    config=config,
                    notes=(
                        "H repair remains parked during Quiet Autonomy. The safe work is to use individual H MOT rows "
                        "as bounded proof packets before any broad H repair or scheduler/publish proof."
                    ),
                )
            )
    elif repair_fail_rows:
        task_rows.append(
            _task_candidate(
                observed_utc=observed_utc,
                flow=config.flow,
                task_type="repair",
                priority="high",
                status="proposed",
                title=f"Repair {config.flow} active FAIL group",
                root_artifact=evidence_rel_path,
                config=config,
                notes=f"{len(repair_fail_rows)} active FAIL/blocker rows found.",
            )
        )
    elif decision_recon_rows:
        first_decision = decision_recon_rows[0]
        task_rows.append(
            _task_candidate(
                observed_utc=observed_utc,
                flow=config.flow,
                task_type="user_decision",
                priority="high",
                status="blocked_needs_user_decision",
                title=f"Decide {config.flow} protected proof evidence",
                root_artifact=first_decision.get("source_path", config.expectation_path),
                config=config,
                needs_luke_decision="1",
                notes=first_decision.get("notes", "Protected manager proof decision found."),
            )
        )
    elif repair_blocked_recon_rows:
        first_blocked = repair_blocked_recon_rows[0]
        task_rows.append(
            _task_candidate(
                observed_utc=observed_utc,
                flow=config.flow,
                task_type="repair",
                priority="high",
                status="proposed",
                title=f"Repair {config.flow} blocked proof evidence",
                root_artifact=first_blocked.get("source_path", config.expectation_path),
                config=config,
                notes=first_blocked.get("notes", "Blocked manager proof evidence found."),
            )
        )
    elif (
        warn_rows
        and not watch_only_warning
        and not (config.flow == "H" and _h_warn_classification_packaged(root))
        and not f_warn_classification_packet_exists
    ):
        task_rows.append(
            _task_candidate(
                observed_utc=observed_utc,
                flow=config.flow,
                task_type="classification",
                priority="normal",
                status="proposed",
                title=f"Classify {config.flow} active WARN group",
                root_artifact=evidence_rel_path,
                config=config,
                notes=f"{len(warn_rows)} active WARN/stale rows found.",
            )
        )
    elif not_verified_count and config.flow in {"A", "B", "E", "O"} and not _manager_proof_gap_packaged(root, config.flow):
        task_rows.append(
            _task_candidate(
                observed_utc=observed_utc,
                flow=config.flow,
                task_type="proof_gap",
                priority="low",
                status="proposed",
                title=f"Add or confirm {config.flow} manager proof coverage",
                root_artifact=config.expectation_path,
                config=config,
                notes=f"{not_verified_count} expectations are not yet manager-verified.",
            )
        )

    codex_task_available = "1" if any(row.get("needs_luke_decision") != "1" for row in task_rows) else "0"
    codex_task_title = next((row["title"] for row in task_rows if row.get("needs_luke_decision") != "1"), "")
    luke_decision = due_decisions[0].get("title", "") if due_decisions else ""
    if not luke_decision and luke_blocked_fail_rows:
        first_luke_blocked = luke_blocked_fail_rows[0]
        luke_decision = first_luke_blocked.get("summary", "") or first_luke_blocked.get("check", "")
    evidence_paths = ";".join(
            str(path)
            for path in [evidence_path if evidence_rows else None, manifest_path, expectation_path]
            if path
    )
    flow_row = {
        "observed_utc": observed_utc,
        "flow": config.flow,
        "flow_name": config.flow_name,
        "rollout_rank": str(config.rollout_rank),
        "status": status,
        "classification": classification,
        "needs_luke_decision": "1" if due_decisions or luke_blocked_fail_rows else "0",
        "luke_decision": luke_decision,
        "codex_task_available": codex_task_available,
        "codex_task_title": codex_task_title,
        "active_fail_count": str(len(fail_rows)),
        "active_warn_count": str(len(warn_rows)),
        "stale_evidence_count": str(len(stale_rows)),
        "not_verified_count": str(not_verified_count),
        "covered_expectations": str(covered_count),
        "total_expectations": str(len(recon_rows)),
        "first_blocker_code": first_blocker_code,
        "first_blocker_summary": first_blocker_summary,
        "proof_rule": config.proof_rule,
        "evidence_paths": evidence_paths,
        "notes": config.notes,
    }
    return flow_row, recon_rows, task_rows, health_rows


def build_multi_flow_manager(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    flow_rows: list[dict[str, str]] = []
    expectation_rows: list[dict[str, str]] = []
    task_rows: list[dict[str, str]] = []
    health_rows: list[dict[str, str]] = []

    for flow in FLOW_ORDER:
        flow_row, recon_rows, flow_task_rows, flow_health_rows = _build_flow(
            root=base,
            config=FLOW_CONFIGS[flow],
            observed_utc=observed,
        )
        flow_rows.append(flow_row)
        expectation_rows.extend(recon_rows)
        task_rows.extend(flow_task_rows)
        health_rows.extend(flow_health_rows)

    health_rows.append(
        _health_row(
            "multi_flow_manager_execution",
            "ok",
            "0",
            "0 active multi-flow manager execution errors",
            observed,
            "sellerone_manager",
        )
    )
    return {
        "observed_utc": observed,
        "flow_rows": sorted(flow_rows, key=lambda row: int(row.get("rollout_rank", "99") or "99")),
        "expectation_rows": expectation_rows,
        "task_candidate_rows": sorted(
            task_rows,
            key=lambda row: (
                int(FLOW_CONFIGS.get(row.get("flow", ""), FLOW_CONFIGS["O"]).rollout_rank),
                {"blocked_needs_user_decision": 0, "proposed": 1}.get(row.get("status", ""), 9),
                row.get("priority", ""),
            ),
        ),
        "health_rows": health_rows,
    }


def build_manager_control_markdown(result: dict[str, Any]) -> str:
    flow_rows = result.get("flow_rows", [])
    task_rows = result.get("task_candidate_rows", [])
    lines = [
        "# SellerOne Manager Control Desk",
        "",
        f"Observed UTC: {result.get('observed_utc', '')}",
        "",
        "## Purpose",
        "Maintenance and extension control only. This is not the business data UI.",
        "",
        "## Flow Maintenance State",
    ]
    for row in flow_rows:
        status = row.get("status", "")
        classification = row.get("classification", "")
        counts = f"FAIL {row.get('active_fail_count', '0')}, WARN {row.get('active_warn_count', '0')}, not verified {row.get('not_verified_count', '0')}"
        lines.append(f"- {row.get('flow')}: {status} / {classification} ({counts})")
    lines.extend(["", "## Next Manager Tasks"])
    if task_rows:
        for row in task_rows[:8]:
            decision = " needs Luke decision" if row.get("needs_luke_decision") == "1" else ""
            lines.append(f"- {row.get('flow')}: {row.get('title')} [{row.get('status')}{decision}]")
    else:
        lines.append("- No manager task candidate from this snapshot.")
    lines.extend(
        [
            "",
            "## Safety",
            "- This report did not run workers, edit queues, change pricing, write legacy Sheets, or dispatch jobs.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_multi_flow_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "flow_maintenance_csv": output_dir / "flow_maintenance_state.csv",
        "flow_maintenance_json": output_dir / "flow_maintenance_state.json",
        "flow_expectations_csv": output_dir / "flow_expectation_reconciliation.csv",
        "manager_task_candidates_csv": output_dir / "manager_task_candidates.csv",
        "multi_flow_health_csv": output_dir / "multi_flow_manager_health.csv",
        "manager_control_report": output_dir / "latest_manager_control_report.md",
    }
    write_csv(paths["flow_maintenance_csv"], FLOW_MAINTENANCE_COLUMNS, result["flow_rows"])
    write_csv(paths["flow_expectations_csv"], EXPECTATION_RECONCILIATION_COLUMNS, result["expectation_rows"])
    write_csv(paths["manager_task_candidates_csv"], MANAGER_TASK_CANDIDATE_COLUMNS, result["task_candidate_rows"])
    write_csv(paths["multi_flow_health_csv"], HEALTH_COLUMNS, result["health_rows"])
    paths["manager_control_report"].write_text(build_manager_control_markdown(result), encoding="utf-8")
    with paths["flow_maintenance_json"].open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    return paths
