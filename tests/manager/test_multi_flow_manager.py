from __future__ import annotations

import csv
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.current_state import build_current_state
from sellerone_manager.multi_flow import build_multi_flow_manager, write_multi_flow_outputs


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_expectations(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Expectations",
        "",
        "| Feature | Description | Status | Notes |",
        "|---|---|---|---|",
    ]
    for feature, status in rows:
        lines.append(f"| {feature} | Test description | {status} | Test notes |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manifest(
    path: Path,
    *,
    cycle: str,
    final_state: str = "completed",
    steps: list[dict[str, object]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": f"{cycle}_test",
                "cycle": cycle,
                "final_state": final_state,
                "steps": steps or [
                    {
                        "name": f"{cycle}_cycle_step",
                        "script_or_function": f"run_{cycle}.py",
                        "rc": 0,
                        "step_status": "completed",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_active_autonomy_policy(root: Path) -> None:
    path = root / "config" / "manager" / "autonomy_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "active",
                "controlled_technical_pause_resume_allowed": True,
                "business_decisions_delegated": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_quiet_autonomy_policy(root: Path) -> None:
    path = root / "config" / "manager" / "autonomy_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "active",
                "mode": "quiet_autonomy",
                "controlled_technical_pause_resume_allowed": True,
                "controlled_technical_pause_requires_controller": True,
                "business_decisions_delegated": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_floor_table(root: Path) -> None:
    path = root / "out" / "phase1_floor_table_latest.csv"
    _write_csv(path, ["sku", "floor_gbp"], [{"sku": "SKU1", "floor_gbp": "10.00"}])
    db_path = root / "out" / "sql" / "sellerone_dev.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute('CREATE TABLE "a_phase1_floor_table_latest" (sku TEXT)')
        con.execute('INSERT INTO "a_phase1_floor_table_latest" VALUES ("SKU1")')
        con.commit()
    finally:
        con.close()


def _write_a_handoff_proof(
    root: Path,
    *,
    final_run_id: str = "A_test",
    proof_status: str = "ok",
    final_state: str | None = None,
    final_exit_code: int | None = None,
    include_handoff_evidence: bool = False,
) -> None:
    path = root / "out" / "systems" / "A" / "live" / "a_maintenance_handoff_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "proof_status": proof_status,
                "request_id": "REQ_A",
                "handoff_mode": "b_ready",
                "final_run_id": final_run_id,
                "final_state": final_state or ("completed" if proof_status == "ok" else "failed"),
                "final_exit_code": final_exit_code if final_exit_code is not None else (0 if proof_status == "ok" else 3),
                "cleanup_evidence": {"all_clear": True},
                **(
                    {
                        "b_ready_evidence": {"exists": True},
                        "a_active_evidence": {"exists": True},
                    }
                    if include_handoff_evidence
                    else {}
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_b_lock(path: Path, *, label: str, heartbeat_utc: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{label}|pid=123|start=2026-05-26T11:00:00Z|heartbeat={heartbeat_utc}\n", encoding="utf-8")


def _write_b_locks(root: Path, *, observed_utc: str = "2026-05-26T12:00:00Z", duplicate: bool = False) -> None:
    observed = datetime.fromisoformat(observed_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    heartbeat = (observed - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    _write_b_lock(root / "out" / "systems" / "B" / "live" / "B_cycle.lock", label="B", heartbeat_utc=heartbeat)
    _write_b_lock(root / "out" / "systems" / "B" / "live" / "B_supervisor.lock", label="B_SUPERVISOR", heartbeat_utc=heartbeat)
    if duplicate:
        _write_b_lock(root / "out" / "B_cycle.lock", label="B", heartbeat_utc=heartbeat)


def test_multi_flow_manager_uses_a_first_rollout_and_records_h_fail(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "A_cycle_expectations.md",
        [("Daily orchestration runner", "In Progress")],
    )
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "H_cycle_expectations.md",
        [("H launcher and guard runtime", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_A.csv",
        ["check", "status", "value", "notes"],
        [{"check": "a_stock_receipts_collection_health", "status": "warn", "value": "1", "notes": "nonfatal guardrail"}],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_H.csv",
        ["check", "status", "value", "notes"],
        [{"check": "h_terminal_marker_freshness", "status": "fail", "value": "1", "notes": "terminal stale"}],
    )
    _write_csv(
        tmp_path / "project_control" / "DUE_CHECK_REGISTER.csv",
        ["owner_flow", "status", "last_result", "title", "artifact_path", "notes"],
        [
            {
                "owner_flow": "H",
                "status": "open",
                "last_result": "needs_user_decision",
                "title": "Choose H proof window",
                "artifact_path": "project_control/DUE_CHECK_REGISTER.csv",
                "notes": "Test decision",
            }
        ],
    )
    _write_manifest(tmp_path / "out" / "manifests" / "A" / "2026-05-26" / "A_test.json", cycle="A")
    _write_manifest(tmp_path / "out" / "manifests" / "H" / "2026-05-26" / "H_test.json", cycle="H")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    paths = write_multi_flow_outputs(result, tmp_path / "out" / "systems" / "M")
    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    rows = {row["flow"]: row for row in result["flow_rows"]}
    assert rows["A"]["status"] == "warn"
    assert rows["H"]["status"] == "blocked"
    assert paths["flow_maintenance_csv"].exists()
    assert state["active_flow"] == "A -> B -> E -> H -> F -> O"
    assert state["luke_action_required"] is False
    assert state["codex_task_available"] is True
    assert state["codex_task_title"] == "Classify A active WARN group"


def test_multi_flow_manager_does_not_treat_controlled_h_pause_as_luke_decision_when_authorised(tmp_path: Path) -> None:
    _write_active_autonomy_policy(tmp_path)
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "operations_loop_expectations.md",
        [("Restock Advisor", "Not Started")],
    )
    _write_csv(
        tmp_path / "project_control" / "DUE_CHECK_REGISTER.csv",
        ["owner_flow", "status", "last_result", "title", "artifact_path", "notes"],
        [
            {
                "owner_flow": "O,H",
                "status": "open",
                "last_result": "blocked_waiting_user_decision_active_h_lock",
                "title": "Pause H before controlled restock-candidate market proof scan",
                "artifact_path": "project_control/DUE_CHECK_REGISTER.csv",
                "notes": "Waiting for controlled H isolation proof window.",
            }
        ],
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")

    rows = {row["flow"]: row for row in result["flow_rows"]}
    assert rows["O"]["needs_luke_decision"] == "0"
    assert rows["H"]["needs_luke_decision"] == "0"
    assert not any(row["task_type"] == "user_decision" for row in result["task_candidate_rows"])


def test_quiet_autonomy_parks_h_failures_until_independent_manager_layer_exists(tmp_path: Path) -> None:
    _write_quiet_autonomy_policy(tmp_path)
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "H_cycle_expectations.md",
        [("H launcher and guard runtime", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_H.csv",
        ["check", "status", "value", "notes"],
        [{"check": "h_terminal_marker_freshness", "status": "fail", "value": "1", "notes": "terminal stale"}],
    )
    _write_csv(
        tmp_path / "project_control" / "DUE_CHECK_REGISTER.csv",
        ["owner_flow", "status", "last_result", "title", "artifact_path", "notes"],
        [
            {
                "owner_flow": "H",
                "status": "open",
                "last_result": "needs_user_decision",
                "title": "Confirm repricer tracker UI can replace Sheet after one normal operating day",
                "artifact_path": "project_control/DUE_CHECK_REGISTER.csv",
                "notes": "Business decision parked during Quiet Autonomy.",
            }
        ],
    )
    _write_manifest(tmp_path / "out" / "manifests" / "H" / "2026-05-26" / "H_test.json", cycle="H")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")

    rows = {row["flow"]: row for row in result["flow_rows"]}
    h_tasks = [row for row in result["task_candidate_rows"] if row["flow"] == "H"]
    assert rows["H"]["status"] == "parked"
    assert rows["H"]["classification"] == "high_risk_needs_manager_layer"
    assert rows["H"]["needs_luke_decision"] == "0"
    assert h_tasks[0]["title"] == "Plan H independent manager/MOT layer"
    assert h_tasks[0]["task_type"] == "proof_gap"


def test_quiet_autonomy_stops_reopening_h_manager_layer_after_phase_4_completion(tmp_path: Path) -> None:
    _write_quiet_autonomy_policy(tmp_path)
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "H_cycle_expectations.md",
        [("H launcher and guard runtime", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_H.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {
                "check": "h_latest_manifest_state",
                "status": "fail",
                "value": "failed",
                "summary": "",
                "actual_proof": "",
                "source_path": "out/manifests/H/H_test.json",
            }
        ],
    )
    completion = tmp_path / "sellerone_manager" / "project_threads" / "PHASE_4_H_MANAGER_LAYER_COMPLETE.md"
    completion.parent.mkdir(parents=True, exist_ok=True)
    completion.write_text("# Phase 4 H Manager Layer Complete\n", encoding="utf-8")
    _write_manifest(tmp_path / "out" / "manifests" / "H" / "2026-05-26" / "H_test.json", cycle="H")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")

    rows = {row["flow"]: row for row in result["flow_rows"]}
    h_tasks = [row for row in result["task_candidate_rows"] if row["flow"] == "H"]
    assert rows["H"]["status"] == "parked"
    assert rows["H"]["classification"] == "high_risk_bounded_repair_only"
    assert rows["H"]["needs_luke_decision"] == "0"
    assert not any(row["title"] == "Plan H independent manager/MOT layer" for row in h_tasks)


def test_h_warn_classification_packet_stops_reopening_warn_task(tmp_path: Path) -> None:
    _write_quiet_autonomy_policy(tmp_path)
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "H_cycle_expectations.md",
        [("Health reporting", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_H.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {
                "check": "h_health_snapshot_as_clue",
                "status": "warn",
                "value": "old_fail_count=1",
                "summary": "",
                "actual_proof": "",
                "source_path": "out/cycle_alerts/checklist_H.csv",
            }
        ],
    )
    package = (
        tmp_path
        / "plans"
        / "active"
        / "sellerone-manager-control-plane-v1"
        / "H_REPAIR_PACKAGE_MGR_H_classification_out_systems_M_hourly_mot_20260530_warns.md"
    )
    package.parent.mkdir(parents=True, exist_ok=True)
    package.write_text("# H Classification Package\n", encoding="utf-8")
    _write_manifest(tmp_path / "out" / "manifests" / "H" / "2026-05-26" / "H_test.json", cycle="H")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")

    h_flow = next(row for row in result["flow_rows"] if row["flow"] == "H")
    h_tasks = [row for row in result["task_candidate_rows"] if row["flow"] == "H"]
    assert h_flow["status"] == "warn"
    assert h_flow["codex_task_available"] == "0"
    assert not any(row["title"] == "Classify H active WARN group" for row in h_tasks)


def test_o_foundation_outputs_are_not_marked_as_full_loop_completion(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "operations_loop_expectations.md",
        [("Restock Advisor", "Not Started")],
    )
    (tmp_path / "out" / "systems" / "O" / "live").mkdir(parents=True, exist_ok=True)
    (tmp_path / "out" / "systems" / "O" / "live" / "restock_source_view.csv").write_text("sku\nA\n", encoding="utf-8")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    o_rows = [row for row in result["expectation_rows"] if row["flow"] == "O"]

    restock = next(row for row in o_rows if row["feature"] == "Restock Advisor")
    foundation = next(row for row in o_rows if row["feature"] == "O foundation restock source view")
    assert restock["manager_status"] == "not_started"
    assert foundation["manager_status"] == "covered"
    assert "not full operations-loop completion" in foundation["notes"]


def test_a_floor_and_handoff_proof_can_close_manager_expectations(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "A_cycle_expectations.md",
        [("Floor table support", "In Progress"), ("Maintenance handoff safety", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_A.csv",
        ["check", "status", "value", "notes"],
        [{"check": "a_stock_receipts_collection_health", "status": "ok", "value": "0", "notes": "ok"}],
    )
    _write_manifest(tmp_path / "out" / "manifests" / "A" / "2026-05-26" / "A_test.json", cycle="A")
    _write_floor_table(tmp_path)
    _write_a_handoff_proof(tmp_path, final_run_id="A_test", proof_status="ok")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    a_rows = {row["feature"]: row for row in result["expectation_rows"] if row["flow"] == "A"}
    flow = next(row for row in result["flow_rows"] if row["flow"] == "A")

    assert a_rows["Floor table support"]["manager_status"] == "covered"
    assert a_rows["Maintenance handoff safety"]["manager_status"] == "covered"
    assert flow["covered_expectations"] == "2"


def test_a_missing_floor_table_is_not_verified_not_blocked(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "A_cycle_expectations.md",
        [("Floor table support", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_A.csv",
        ["check", "status", "value", "notes"],
        [{"check": "a_stock_receipts_collection_health", "status": "ok", "value": "0", "notes": "ok"}],
    )
    _write_manifest(tmp_path / "out" / "manifests" / "A" / "2026-05-26" / "A_test.json", cycle="A")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    a_row = next(row for row in result["expectation_rows"] if row["flow"] == "A" and row["feature"] == "Floor table support")
    flow = next(row for row in result["flow_rows"] if row["flow"] == "A")

    assert a_row["manager_status"] == "not_verified"
    assert flow["status"] == "ok"


def test_a_failed_handoff_proof_blocks_flow(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "A_cycle_expectations.md",
        [("Maintenance handoff safety", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_A.csv",
        ["check", "status", "value", "notes"],
        [{"check": "a_stock_receipts_collection_health", "status": "ok", "value": "0", "notes": "ok"}],
    )
    _write_manifest(tmp_path / "out" / "manifests" / "A" / "2026-05-26" / "A_test.json", cycle="A")
    _write_a_handoff_proof(tmp_path, final_run_id="A_test", proof_status="fail")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    a_row = next(row for row in result["expectation_rows"] if row["flow"] == "A" and row["feature"] == "Maintenance handoff safety")
    flow = next(row for row in result["flow_rows"] if row["flow"] == "A")

    assert a_row["manager_status"] == "blocked"
    assert flow["status"] == "blocked"
    assert flow["first_blocker_code"] == "a_maintenance_handoff_proof"


def test_a_interrupted_handoff_proof_is_not_verified_not_blocked(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "A_cycle_expectations.md",
        [("Maintenance handoff safety", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_A.csv",
        ["check", "status", "value", "notes"],
        [{"check": "a_stock_receipts_collection_health", "status": "ok", "value": "0", "notes": "ok"}],
    )
    _write_manifest(
        tmp_path / "out" / "manifests" / "A" / "2026-05-26" / "A_test.json",
        cycle="A",
        final_state="partial",
        steps=[
            {
                "name": "A016_refresh_phase1_daily_intel.py",
                "script_or_function": "A016_refresh_phase1_daily_intel.py",
                "rc": 130,
                "step_status": "failed",
                "verification_status": "interrupted",
            }
        ],
    )
    _write_a_handoff_proof(
        tmp_path,
        final_run_id="A_test",
        proof_status="fail",
        final_state="partial",
        final_exit_code=130,
        include_handoff_evidence=True,
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    a_row = next(row for row in result["expectation_rows"] if row["flow"] == "A" and row["feature"] == "Maintenance handoff safety")
    flow = next(row for row in result["flow_rows"] if row["flow"] == "A")

    assert a_row["manager_status"] == "not_verified"
    assert a_row["evidence_status"] == "interrupted"
    assert flow["status"] == "ok"


def test_b_lock_and_heartbeat_expectation_uses_independent_owner_proof(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "B_cycle_expectations.md",
        [("Lock and heartbeat safety", "In Progress")],
    )
    _write_b_locks(tmp_path)

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    b_row = next(row for row in result["expectation_rows"] if row["flow"] == "B" and row["feature"] == "Lock and heartbeat safety")
    flow = next(row for row in result["flow_rows"] if row["flow"] == "B")

    assert b_row["manager_status"] == "covered"
    assert b_row["evidence_checks"] == "b_worker_owner,b_supervisor_owner"
    assert flow["covered_expectations"] == "1"


def test_b_duplicate_worker_lock_blocks_manager_ownership_proof(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "B_cycle_expectations.md",
        [("Lock and heartbeat safety", "In Progress")],
    )
    _write_b_locks(tmp_path, duplicate=True)

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    b_row = next(row for row in result["expectation_rows"] if row["flow"] == "B" and row["feature"] == "Lock and heartbeat safety")
    flow = next(row for row in result["flow_rows"] if row["flow"] == "B")

    assert b_row["manager_status"] == "blocked"
    assert flow["status"] == "blocked"


def test_b_expectation_mapping_uses_exact_mot_rows_not_broad_gate_text(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "B_cycle_expectations.md",
        [
            ("Order collection", "In Progress"),
            ("Token ledger allocation", "In Progress"),
            ("Per-marketplace future order coverage", "In Progress"),
            ("B Management readiness gate", "Manager Ready"),
            ("B order truth completion gate", "In Progress"),
        ],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_B.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {"check": "b_orders_all", "status": "ok", "value": "fresh", "summary": "", "actual_proof": "", "source_path": "out/orders_all.csv"},
            {"check": "b_order_items_all", "status": "ok", "value": "fresh", "summary": "", "actual_proof": "", "source_path": "out/order_items_all.csv"},
            {"check": "b_token_ledger_live", "status": "ok", "value": "fresh", "summary": "", "actual_proof": "", "source_path": "out/token_ledger_live.csv"},
            {"check": "b_token_cogs_ledger", "status": "ok", "value": "fresh", "summary": "", "actual_proof": "", "source_path": "out/token_cogs_ledger.csv"},
            {"check": "b_token_shortages_by_sku", "status": "ok", "value": "fresh", "summary": "", "actual_proof": "", "source_path": "out/token_shortages_by_sku.csv"},
            {"check": "b_future_marketplace_order_cursors", "status": "fail", "value": "stale", "summary": "", "actual_proof": "", "source_path": "out/systems/B/order_cursors/b_marketplace_order_cursors.csv"},
            {"check": "b_marketplace_shared_cursor_risk", "status": "ok", "value": "0", "summary": "", "actual_proof": "", "source_path": "out/systems/M/b_marketplace_coverage/b_marketplace_coverage_summary.csv"},
            {"check": "b_management_ready_for_maintenance", "status": "fail", "value": "not_ready", "summary": "", "actual_proof": "", "source_path": "out/systems/M/hourly_mot_B.csv"},
            {"check": "b_order_truth_completion", "status": "fail", "value": "not_complete", "summary": "", "actual_proof": "", "source_path": "out/systems/M/hourly_mot_B.csv"},
        ],
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    b_rows = {row["feature"]: row for row in result["expectation_rows"] if row["flow"] == "B"}

    assert b_rows["Order collection"]["manager_status"] == "covered"
    assert b_rows["Token ledger allocation"]["manager_status"] == "covered"
    assert b_rows["Per-marketplace future order coverage"]["manager_status"] == "blocked"
    assert b_rows["Per-marketplace future order coverage"]["evidence_checks"] == (
        "b_future_marketplace_order_cursors,b_marketplace_shared_cursor_risk"
    )
    assert b_rows["B Management readiness gate"]["manager_status"] == "blocked"
    assert b_rows["B Management readiness gate"]["evidence_checks"] == "b_management_ready_for_maintenance"
    assert b_rows["B order truth completion gate"]["manager_status"] == "blocked"
    assert b_rows["B order truth completion gate"]["evidence_checks"] == "b_order_truth_completion"


def test_b_protected_mot_decision_becomes_user_decision_not_repair_candidate(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "B_cycle_expectations.md",
        [("P and L daily build", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_B.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path", "luke_action_required"],
        [
            {
                "check": "b_pnl_daily",
                "status": "decision_needed",
                "value": "blocked_by_protected_token_shortage",
                "summary": "",
                "actual_proof": "sku=AK-OB6V-HIYD,missing_qty=3",
                "source_path": "out/token_shortages_by_sku.csv",
                "luke_action_required": "1",
            }
        ],
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    b_row = next(row for row in result["expectation_rows"] if row["flow"] == "B" and row["feature"] == "P and L daily build")
    b_tasks = [row for row in result["task_candidate_rows"] if row["flow"] == "B"]

    assert b_row["manager_status"] == "blocked"
    assert b_row["evidence_status"] == "decision_needed"
    assert len(b_tasks) == 1
    assert b_tasks[0]["status"] == "blocked_needs_user_decision"
    assert b_tasks[0]["needs_luke_decision"] == "1"
    assert b_tasks[0]["title"] == "Decide B protected proof evidence"


def test_b_proof_gap_package_stops_reopening_generic_proof_task(tmp_path: Path) -> None:
    _write_quiet_autonomy_policy(tmp_path)
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "B_cycle_expectations.md",
        [("Refund fee shipping ROI bridge", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_B.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {
                "check": "b_sellerboard_refund_fee_roi_bridge",
                "status": "warn",
                "value": "return_refund_gap=3",
                "summary": "",
                "actual_proof": "",
                "source_path": "out/systems/M/sellerboard_bridge/b_sellerboard_bridge_summary.csv",
            }
        ],
    )
    package = (
        tmp_path
        / "plans"
        / "active"
        / "sellerone-manager-control-plane-v1"
        / "B_PROOF_PACKAGE_MGR_B_proof_gap_project_control_EXPECTAT_20260531.md"
    )
    package.parent.mkdir(parents=True, exist_ok=True)
    package.write_text("# B Proof Package\n", encoding="utf-8")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-31T07:00:00Z")

    b_flow = next(row for row in result["flow_rows"] if row["flow"] == "B")
    b_tasks = [row for row in result["task_candidate_rows"] if row["flow"] == "B"]
    assert b_flow["status"] == "warn"
    assert b_flow["codex_task_available"] == "0"
    assert not any(row["title"] == "Add or confirm B manager proof coverage" for row in b_tasks)


def test_h_expectation_mapping_uses_independent_mot_not_old_checklist(tmp_path: Path) -> None:
    _write_quiet_autonomy_policy(tmp_path)
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "H_cycle_expectations.md",
        [
            ("H launcher and guard runtime", "In Progress"),
            ("Offer and market collection", "In Progress"),
            ("Publish updates", "In Progress"),
            ("Boundary truth handling", "In Progress"),
            ("Storage self-cleaning", "In Progress"),
        ],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_H.csv",
        ["check", "status", "value", "notes"],
        [{"check": "h_terminal_marker_freshness", "status": "ok", "value": "old", "notes": "old clue"}],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_H.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {"check": "h_latest_manifest_state", "status": "fail", "value": "failed", "summary": "", "actual_proof": "", "source_path": "out/manifests/H/H_test.json"},
            {"check": "h_lock_and_heartbeat_state", "status": "ok", "value": "fresh", "summary": "", "actual_proof": "", "source_path": "out/H_pricing_cycle.lock"},
            {"check": "h_market_context_proof", "status": "fail", "value": "missing_context", "summary": "", "actual_proof": "", "source_path": "out/listing_offer_history.csv"},
            {"check": "h_terminal_publish_truth", "status": "fail", "value": "terminal_failed", "summary": "", "actual_proof": "", "source_path": "out/systems/H/live/H_cycle_last_terminal_info.txt"},
            {"check": "h_boundary_finalizer_truth", "status": "fail", "value": "finalizer_failed", "summary": "", "actual_proof": "", "source_path": "out/manifests/H/H_test.json"},
            {"check": "h_storage_cleanup_safety", "status": "warn", "value": "staged_entries=225", "summary": "", "actual_proof": "", "source_path": "out/systems/H/staged"},
        ],
    )
    _write_manifest(tmp_path / "out" / "manifests" / "H" / "2026-05-26" / "H_test.json", cycle="H")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    h_rows = {row["feature"]: row for row in result["expectation_rows"] if row["flow"] == "H"}
    flow = next(row for row in result["flow_rows"] if row["flow"] == "H")

    assert h_rows["H launcher and guard runtime"]["manager_status"] == "blocked"
    assert h_rows["H launcher and guard runtime"]["evidence_checks"] == "h_latest_manifest_state,h_lock_and_heartbeat_state"
    assert h_rows["Offer and market collection"]["manager_status"] == "blocked"
    assert h_rows["Publish updates"]["manager_status"] == "blocked"
    assert h_rows["Boundary truth handling"]["manager_status"] == "blocked"
    assert h_rows["Storage self-cleaning"]["manager_status"] == "not_verified"
    assert flow["status"] == "parked"
    assert flow["active_fail_count"] == "4"


def test_f_expectation_mapping_uses_independent_mot_not_old_snapshot(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "F_cycle_expectations.md",
        [
            ("Manager front door and snapshot", "In Progress"),
            ("Supplier source intake proof", "In Progress"),
        ],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "f_price_list_manager_snapshot.csv",
        ["check", "status", "value", "notes"],
        [{"check": "f_manager_snapshot_current", "status": "ok", "value": "old_snapshot_ok", "notes": "old snapshot"}],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_F.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {"check": "f_manager_snapshot_current", "status": "ok", "value": "ok", "summary": "", "actual_proof": "", "source_path": "out/systems/M/f_price_list_manager_snapshot.csv"},
            {"check": "f_manager_registration_coverage", "status": "ok", "value": "registered", "summary": "", "actual_proof": "", "source_path": "config/manager/modules"},
            {"check": "f_source_intake_chain_proof", "status": "fail", "value": "failed=1", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
            {"check": "f_email_price_list_source_proof", "status": "ok", "value": "ready=1", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
            {"check": "f_url_source_download_proof", "status": "ok", "value": "ready=2", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
        ],
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-06-04T12:00:00Z")
    f_rows = {row["feature"]: row for row in result["expectation_rows"] if row["flow"] == "F"}
    flow = next(row for row in result["flow_rows"] if row["flow"] == "F")

    assert f_rows["Manager front door and snapshot"]["manager_status"] == "covered"
    assert f_rows["Supplier source intake proof"]["manager_status"] == "blocked"
    assert f_rows["Supplier source intake proof"]["evidence_checks"] == (
        "f_source_intake_chain_proof,f_email_price_list_source_proof,f_url_source_download_proof"
    )
    assert flow["status"] == "blocked"
    assert flow["classification"] == "blocker"
    assert flow["active_fail_count"] == "1"
    assert flow["first_blocker_code"] == "f_source_intake_chain_proof"
    assert "hourly_mot_F.csv" in flow["evidence_paths"]
    assert "F_cycle_expectations.md" in flow["evidence_paths"]
    assert "FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md" not in flow["evidence_paths"]


def test_f_front_door_surfaces_independent_mot_warnings(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "F_cycle_expectations.md",
        [
            ("Supplier source intake proof", "In Progress"),
            ("Queue recommendation and handoff controls", "In Progress"),
        ],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_F.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {"check": "f_source_intake_chain_proof", "status": "warn", "value": "source_failed_import_fallback=1", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
            {"check": "f_email_price_list_source_proof", "status": "ok", "value": "ready=1", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
            {"check": "f_url_source_download_proof", "status": "ok", "value": "ready=2", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
            {"check": "f_queue_recommendation_explainable", "status": "warn", "value": "clf:Recommended", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/status_dashboard.csv"},
            {"check": "f_queue_handoff_control_proof", "status": "ok", "value": "controls=2", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/queue_controls.csv"},
        ],
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-06-04T12:00:00Z")
    f_rows = {row["feature"]: row for row in result["expectation_rows"] if row["flow"] == "F"}
    flow = next(row for row in result["flow_rows"] if row["flow"] == "F")

    assert f_rows["Supplier source intake proof"]["manager_status"] == "not_verified"
    assert f_rows["Queue recommendation and handoff controls"]["manager_status"] == "not_verified"
    assert flow["status"] == "warn"
    assert flow["classification"] == "warning"
    assert flow["active_warn_count"] == "2"
    assert flow["codex_task_available"] == "1"
    assert flow["codex_task_title"] == "Classify F active WARN group"


def test_f_warn_classification_packet_prevents_repeat_task_loop(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "F_cycle_expectations.md",
        [("Supplier source intake proof", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_F.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {"check": "f_source_intake_chain_proof", "status": "warn", "value": "source_failed_import_fallback=1", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
            {"check": "f_email_price_list_source_proof", "status": "ok", "value": "ready=1", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
            {"check": "f_url_source_download_proof", "status": "ok", "value": "ready=2", "summary": "", "actual_proof": "", "source_path": "out/systems/F/price_list_manager/test_mode/source_acquisition_status.csv"},
        ],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        ["task_id", "status"],
        [{"task_id": "MGR_F_classification_out_systems_M_hourly_mot", "status": "proved"}],
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-06-04T12:00:00Z")
    flow = next(row for row in result["flow_rows"] if row["flow"] == "F")
    task_rows = [row for row in result["task_candidate_rows"] if row["flow"] == "F"]

    assert flow["status"] == "warn"
    assert flow["active_warn_count"] == "1"
    assert flow["codex_task_available"] == "0"
    assert not task_rows


def test_luke_blocked_fail_does_not_create_codex_repair_group(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "F_cycle_expectations.md",
        [("RESCAN priority proof", "In Progress")],
    )
    _write_manifest(tmp_path / "out" / "manifests" / "F" / "2026-06-04" / "F_test.json", cycle="F")
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_F.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path", "luke_action_required", "notes"],
        [
            {
                "check": "f_rescan_priority_proof",
                "status": "fail",
                "value": "parked_timeout=223",
                "summary": "F RESCAN rows need a protected apply decision.",
                "actual_proof": "rescan_timeout_rows=223",
                "source_path": "out/systems/F/live/f_screening_row_state_live.csv",
                "luke_action_required": "1",
                "notes": "protected quiet-window apply required",
            }
        ],
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-06-04T12:00:00Z")
    flow = next(row for row in result["flow_rows"] if row["flow"] == "F")
    task_rows = [row for row in result["task_candidate_rows"] if row["flow"] == "F"]

    assert flow["status"] == "blocked"
    assert flow["needs_luke_decision"] == "1"
    assert flow["codex_task_available"] == "0"
    assert not task_rows


def test_e_manager_expectations_use_independent_mot_not_old_checklist(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "E_cycle_expectations.md",
        [("Sales velocity output", "In Progress"), ("Optional publishing path", "In Progress")],
    )
    _write_csv(
        tmp_path / "out" / "cycle_alerts" / "checklist_E.csv",
        ["check", "status", "value", "notes"],
        [{"check": "e_schema_sales_velocity", "status": "fail", "value": "old", "notes": "old clue"}],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_E.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {
                "check": "e_core_outputs_fresh",
                "status": "ok",
                "value": "fresh_enough",
                "summary": "sales_velocity output is fresh",
                "actual_proof": "sales_velocity:rows=2",
                "source_path": "out/sku_sales_velocity.csv",
            },
            {
                "check": "e_core_row_counts_believable",
                "status": "ok",
                "value": "believable",
                "summary": "row counts line up",
                "actual_proof": "sales_velocity=2",
                "source_path": "out/sku_sales_velocity.csv",
            },
            {
                "check": "e_schema_contracts",
                "status": "ok",
                "value": "contracts_ok",
                "summary": "schema ok",
                "actual_proof": "missing_columns=",
                "source_path": "out/sku_sales_velocity.csv",
            },
            {
                "check": "e_optional_publish_proof",
                "status": "not_checked",
                "value": "not_verified",
                "summary": "Optional publish proof is not required yet",
                "actual_proof": "exists=0",
                "source_path": "out/e_publish_log.csv",
            },
        ],
    )
    _write_manifest(tmp_path / "out" / "manifests" / "E" / "2026-05-26" / "E_test.json", cycle="E")

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    e_rows = {row["feature"]: row for row in result["expectation_rows"] if row["flow"] == "E"}
    flow = next(row for row in result["flow_rows"] if row["flow"] == "E")

    assert e_rows["Sales velocity output"]["manager_status"] == "covered"
    assert e_rows["Optional publishing path"]["manager_status"] == "covered"
    assert e_rows["Optional publishing path"]["evidence_status"] == "not_required"
    assert flow["status"] == "ok"


def test_e_expectation_mapping_separates_business_warnings_from_output_proof(tmp_path: Path) -> None:
    _write_expectations(
        tmp_path / "project_control" / "EXPECTATIONS" / "E_cycle_expectations.md",
        [
            ("Performance summary output", "In Progress"),
            ("Study report output", "In Progress"),
            ("Cadence control", "In Progress"),
        ],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "hourly_mot_E.csv",
        ["check", "status", "value", "summary", "actual_proof", "source_path"],
        [
            {"check": "e_core_outputs_fresh", "status": "ok", "value": "fresh_enough", "summary": "", "actual_proof": "", "source_path": "out/sku_performance_summary.csv"},
            {"check": "e_core_row_counts_believable", "status": "ok", "value": "believable", "summary": "", "actual_proof": "", "source_path": "out/sku_performance_summary.csv"},
            {"check": "e_schema_contracts", "status": "ok", "value": "contracts_ok", "summary": "", "actual_proof": "", "source_path": "out/sku_performance_summary.csv"},
            {"check": "e_cross_output_alignment", "status": "ok", "value": "aligned", "summary": "", "actual_proof": "", "source_path": "out/sku_performance_summary.csv"},
            {"check": "e_confidence_fields_live", "status": "ok", "value": "confidence_fields_present", "summary": "", "actual_proof": "", "source_path": "out/sku_performance_summary.csv"},
            {"check": "e_coverage_summary_live", "status": "ok", "value": "coverage_summary_present", "summary": "", "actual_proof": "", "source_path": "out/e_coverage_summary.csv"},
            {"check": "e_restock_profit_guard", "status": "ok", "value": "restock_ready_without_clean_profit=0", "summary": "", "actual_proof": "", "source_path": "out/sku_performance_summary.csv"},
            {"check": "e_cadence_control", "status": "ok", "value": "cadence_run_proved", "summary": "", "actual_proof": "", "source_path": "out/systems/E/live/e_run_log.jsonl"},
            {"check": "e_roi_coverage", "status": "warn", "value": "roi_skus=1;total_skus=4", "summary": "", "actual_proof": "", "source_path": "out/sku_performance_summary.csv"},
            {"check": "e_daily_truth_coverage", "status": "warn", "value": "unexplained_truth_rows=1", "summary": "", "actual_proof": "", "source_path": "out/e_study_report.csv"},
        ],
    )

    result = build_multi_flow_manager(root=tmp_path, observed_utc="2026-05-26T12:00:00Z")
    e_rows = {row["feature"]: row for row in result["expectation_rows"] if row["flow"] == "E"}
    flow = next(row for row in result["flow_rows"] if row["flow"] == "E")

    assert e_rows["Performance summary output"]["manager_status"] == "covered"
    assert "e_roi_coverage" in e_rows["Performance summary output"]["notes"]
    assert e_rows["Study report output"]["manager_status"] == "covered"
    assert "e_daily_truth_coverage" in e_rows["Study report output"]["notes"]
    assert e_rows["Cadence control"]["manager_status"] == "covered"
    assert flow["status"] == "warn"
    assert flow["not_verified_count"] == "0"
