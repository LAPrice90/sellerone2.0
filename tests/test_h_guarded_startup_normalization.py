from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cycles import run_H_pricing_cycle_guarded as guarded


def _write_worker(path: Path, *, run_id: str, state: str, heartbeat_seconds_ago: int) -> None:
    heartbeat_utc = (datetime.now(timezone.utc) - timedelta(seconds=heartbeat_seconds_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "run_id": run_id,
        "state": state,
        "heartbeat_utc": heartbeat_utc,
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def test_stale_current_run_marker_is_fail_closed_when_no_live_owner(tmp_path: Path) -> None:
    root = tmp_path
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (root / "out").mkdir(parents=True, exist_ok=True)
    current_run = live / "H_cycle_current_run_id.txt"
    lifecycle = live / "H_worker_lifecycle.json"
    heartbeat = live / "H_pricing_cycle.HEARTBEAT.txt"
    current_run.write_text("RUN_OLD_001\n", encoding="utf-8")
    _write_worker(lifecycle, run_id="RUN_OLD_001", state="running", heartbeat_seconds_ago=600)

    result = guarded._normalize_stale_startup_context(
        root=root,
        live=live,
        current_run_id_path=current_run,
        worker_lifecycle_path=lifecycle,
        heartbeat=heartbeat,
        stale_after_seconds=120.0,
    )

    unchanged = guarded._read_h_worker_lifecycle(lifecycle)
    assert result.get("normalized") == "0"
    assert result.get("reason") == "stale_context_detected_fail_closed"
    assert current_run.exists()
    assert unchanged.get("state") == "running"


def test_stale_active_lifecycle_without_current_run_is_fail_closed(tmp_path: Path) -> None:
    root = tmp_path
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (root / "out").mkdir(parents=True, exist_ok=True)
    current_run = live / "H_cycle_current_run_id.txt"
    lifecycle = live / "H_worker_lifecycle.json"
    heartbeat = live / "H_pricing_cycle.HEARTBEAT.txt"
    _write_worker(lifecycle, run_id="RUN_OLD_002", state="claimed", heartbeat_seconds_ago=900)

    result = guarded._normalize_stale_startup_context(
        root=root,
        live=live,
        current_run_id_path=current_run,
        worker_lifecycle_path=lifecycle,
        heartbeat=heartbeat,
        stale_after_seconds=120.0,
    )

    unchanged = guarded._read_h_worker_lifecycle(lifecycle)
    assert result.get("normalized") == "0"
    assert result.get("reason") == "stale_context_detected_fail_closed"
    assert unchanged.get("state") == "claimed"


def test_active_owner_conflict_stays_fail_closed(tmp_path: Path) -> None:
    root = tmp_path
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (root / "out").mkdir(parents=True, exist_ok=True)
    current_run = live / "H_cycle_current_run_id.txt"
    lifecycle = live / "H_worker_lifecycle.json"
    heartbeat = live / "H_pricing_cycle.HEARTBEAT.txt"
    current_run.write_text("RUN_ACTIVE_003\n", encoding="utf-8")
    _write_worker(lifecycle, run_id="RUN_ACTIVE_003", state="running", heartbeat_seconds_ago=900)
    (live / "H_pricing_cycle.lock").write_text(
        "H|pid=43210|run_id=RUN_ACTIVE_003|start=2026-03-21T19:00:00Z|heartbeat=2026-03-21T19:00:05Z\n",
        encoding="utf-8",
    )
    with mock.patch.object(guarded, "_pid_is_alive", return_value=True):
        result = guarded._normalize_stale_startup_context(
            root=root,
            live=live,
            current_run_id_path=current_run,
            worker_lifecycle_path=lifecycle,
            heartbeat=heartbeat,
            stale_after_seconds=120.0,
        )

    unchanged = guarded._read_h_worker_lifecycle(lifecycle)
    assert result.get("normalized") == "0"
    assert result.get("reason") == "active_owner_present"
    assert current_run.exists()
    assert unchanged.get("state") == "running"


def test_archive_stale_startup_context_stays_observe_only_no_mutation(tmp_path: Path) -> None:
    root = tmp_path
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (root / "out").mkdir(parents=True, exist_ok=True)
    run_id = "RUN_STALE_004"
    run_state_path = live / "H_run_state.json"
    worker_path = live / "H_worker_lifecycle.json"
    finalized_path = live / "H_last_finalized_run_id.txt"
    run_in_progress_path = live / "H_run_in_progress.txt"
    heartbeat_path = live / "H_pricing_cycle.HEARTBEAT.txt"

    run_state_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "state": "started",
                "utc": "2026-04-02T12:00:00Z",
                "owner_pid": "11111",
                "stage": "cycle_start",
                "publish_status": "not_started",
                "failure_code": "",
                "failure_detail": "",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_worker(worker_path, run_id=run_id, state="running", heartbeat_seconds_ago=900)
    finalized_path.write_text("RUN_OLD_FINALIZED\n", encoding="utf-8")
    run_in_progress_path.write_text(run_id + "\n", encoding="utf-8")

    result = guarded._archive_stale_startup_context(
        live=live,
        run_id=run_id,
        run_state_path=run_state_path,
        worker_lifecycle_path=worker_path,
        finalized_run_id_path=finalized_path,
        heartbeat=heartbeat_path,
    )

    run_state = guarded._read_h_run_state(run_state_path)
    worker = guarded._read_h_worker_lifecycle(worker_path)
    archive_path = live / f"H_failed_run_archived.{run_id}.json"
    assert result.get("archived") == "0"
    assert result.get("reason") == "core_owned_truth_no_wrapper_mutation"
    assert run_in_progress_path.exists()
    assert run_in_progress_path.read_text(encoding="utf-8").strip() == run_id
    assert not archive_path.exists()
    assert run_state.get("run_id") == run_id
    assert run_state.get("state") == "started"
    assert worker.get("run_id") == run_id
    assert worker.get("state") == "running"


def test_archive_stale_startup_context_blocks_on_run_marker_mismatch(tmp_path: Path) -> None:
    root = tmp_path
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (root / "out").mkdir(parents=True, exist_ok=True)
    run_id = "RUN_STALE_005"
    run_state_path = live / "H_run_state.json"
    worker_path = live / "H_worker_lifecycle.json"
    finalized_path = live / "H_last_finalized_run_id.txt"
    run_in_progress_path = live / "H_run_in_progress.txt"
    heartbeat_path = live / "H_pricing_cycle.HEARTBEAT.txt"

    run_state_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "state": "started",
                "utc": "2026-04-02T12:00:00Z",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_worker(worker_path, run_id=run_id, state="running", heartbeat_seconds_ago=900)
    finalized_path.write_text("RUN_OLD_FINALIZED\n", encoding="utf-8")
    run_in_progress_path.write_text("OTHER_RUN\n", encoding="utf-8")

    result = guarded._archive_stale_startup_context(
        live=live,
        run_id=run_id,
        run_state_path=run_state_path,
        worker_lifecycle_path=worker_path,
        finalized_run_id_path=finalized_path,
        heartbeat=heartbeat_path,
    )

    run_state = guarded._read_h_run_state(run_state_path)
    worker = guarded._read_h_worker_lifecycle(worker_path)
    assert result.get("archived") == "0"
    assert result.get("reason") == "run_in_progress_mismatch"
    assert run_in_progress_path.exists()
    assert run_state.get("state") == "started"
    assert worker.get("state") == "running"


def test_wrapper_terminalize_failed_run_is_verifier_only_same_run(tmp_path: Path) -> None:
    root = tmp_path
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (root / "out").mkdir(parents=True, exist_ok=True)
    run_id = "RUN_FAIL_006"
    run_state_path = live / "H_run_state.json"
    worker_path = live / "H_worker_lifecycle.json"
    run_in_progress_path = live / "H_run_in_progress.txt"
    run_state_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "state": "started",
                "utc": "2026-04-02T12:00:00Z",
                "owner_pid": "12345",
                "stage": "cycle_start",
                "publish_status": "not_started",
                "failure_code": "",
                "failure_detail": "",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_worker(worker_path, run_id=run_id, state="running", heartbeat_seconds_ago=10)
    run_in_progress_path.write_text(run_id + "\n", encoding="utf-8")

    result = guarded._wrapper_terminalize_failed_run(
        live=live,
        run_id=run_id,
        run_state_path=run_state_path,
        worker_lifecycle_path=worker_path,
        failure_code="EARLY_CORE_EXIT_BEFORE_PILOT_EVIDENCE",
        failure_detail="wrapper_boundary=EARLY_CORE_EXIT_BEFORE_PILOT_EVIDENCE",
        stage_hint="cycle_start",
        publish_status_hint="not_started",
    )

    run_state = guarded._read_h_run_state(run_state_path)
    worker = guarded._read_h_worker_lifecycle(worker_path)
    assert result.get("applied") == "0"
    assert result.get("reason") == "core_owned_truth_no_wrapper_mutation"
    assert result.get("run_state_written") == "0"
    assert result.get("worker_written") == "0"
    assert result.get("terminal_marker_written") == "0"
    assert result.get("run_in_progress_cleared") == "0"
    assert run_in_progress_path.exists()
    assert run_in_progress_path.read_text(encoding="utf-8").strip() == run_id
    assert run_state.get("run_id") == run_id
    assert run_state.get("state") == "started"
    assert run_state.get("failure_code") == ""
    assert worker.get("run_id") == run_id
    assert worker.get("state") == "running"
    assert not (live / "H_cycle_last_terminal_info.txt").exists()


def test_wrapper_terminalize_failed_run_is_verifier_only_on_run_marker_mismatch(tmp_path: Path) -> None:
    root = tmp_path
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    run_id = "RUN_FAIL_007"
    run_state_path = live / "H_run_state.json"
    worker_path = live / "H_worker_lifecycle.json"
    run_in_progress_path = live / "H_run_in_progress.txt"
    run_state_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "state": "started",
                "utc": "2026-04-02T12:00:00Z",
                "owner_pid": "12345",
                "stage": "cycle_start",
                "publish_status": "not_started",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_worker(worker_path, run_id=run_id, state="running", heartbeat_seconds_ago=10)
    run_in_progress_path.write_text("OTHER_RUN\n", encoding="utf-8")

    result = guarded._wrapper_terminalize_failed_run(
        live=live,
        run_id=run_id,
        run_state_path=run_state_path,
        worker_lifecycle_path=worker_path,
        failure_code="EARLY_CORE_EXIT_BEFORE_PILOT_EVIDENCE",
        failure_detail="wrapper_boundary=EARLY_CORE_EXIT_BEFORE_PILOT_EVIDENCE",
    )

    run_state = guarded._read_h_run_state(run_state_path)
    worker = guarded._read_h_worker_lifecycle(worker_path)
    assert result.get("applied") == "0"
    assert result.get("reason") == "core_owned_truth_no_wrapper_mutation"
    assert result.get("terminal_marker_written") == "0"
    assert run_in_progress_path.exists()
    assert run_in_progress_path.read_text(encoding="utf-8").strip() == "OTHER_RUN"
    assert run_state.get("state") == "started"
    assert worker.get("state") == "running"


def test_snapshot_worker_contract_evidence_marks_success_when_contract_is_ok(tmp_path: Path) -> None:
    live = tmp_path / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    run_id = "RUN_ABC_001"
    contract = live / f"snapshot_refresh_worker.contract.{run_id}.123.1.json"
    contract.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "ok",
                "reason": "",
                "checkpoint_last": "snapshot_worker_refresh_done",
                "refresh_state": {
                    "snapshot_refresh_status": "ok",
                },
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    evidence = guarded._read_snapshot_worker_contract_evidence(live, run_id)

    assert evidence.get("contract_exists") == "1"
    assert evidence.get("contract_status") == "ok"
    assert evidence.get("contract_run_id") == run_id
    assert evidence.get("success_ok") == "1"


def test_snapshot_worker_contract_evidence_requires_payload_run_id_match(tmp_path: Path) -> None:
    live = tmp_path / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    requested_run_id = "RUN_ABC_002"
    contract = live / f"snapshot_refresh_worker.contract.{requested_run_id}.123.1.json"
    contract.write_text(
        json.dumps(
            {
                "run_id": "RUN_DIFFERENT",
                "status": "ok",
                "refresh_state": {
                    "snapshot_refresh_status": "ok",
                },
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    evidence = guarded._read_snapshot_worker_contract_evidence(live, requested_run_id)

    assert evidence.get("contract_exists") == "1"
    assert evidence.get("contract_status") == "ok"
    assert evidence.get("success_ok") == "0"


def test_snapshot_worker_reconcile_eligible_from_parent_exit_success_detail() -> None:
    ok, reason = guarded._snapshot_worker_no_publish_reconcile_eligible(
        run_id="RUN_ABC_003",
        run_state={
            "failure_code": "SNAPSHOT_WORKER_HANDOFF_PARENT_EXIT",
            "failure_detail": "parent_exit_after_snapshot_worker_success_before_contract_handoff:worker_rc=0",
        },
        publish_attempt_state={
            "publish_attempted_for_run": "0",
            "publish_entry_for_run": "0",
        },
        snapshot_contract_evidence={"success_ok": "0"},
    )

    assert ok
    assert reason == "run_state_parent_exit_success_detail"


def test_snapshot_worker_reconcile_not_eligible_after_publish_attempt() -> None:
    ok, reason = guarded._snapshot_worker_no_publish_reconcile_eligible(
        run_id="RUN_ABC_004",
        run_state={},
        publish_attempt_state={
            "publish_attempted_for_run": "1",
            "publish_entry_for_run": "0",
        },
        snapshot_contract_evidence={"success_ok": "1"},
    )

    assert not ok
    assert reason == "publish_attempted_for_run"


def test_wrapper_terminal_marker_write_writes_canonical_and_legacy_paths(tmp_path: Path) -> None:
    live = tmp_path / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)

    ok, reason = guarded._write_last_terminal_marker_from_wrapper(
        live,
        run_id="RUN_ABC_005",
        terminal_state="succeeded",
        stage="phase1_intel",
        publish_status="not_started",
    )

    assert ok
    assert reason == "written"

    canonical = live / "H_cycle_last_terminal_info.txt"
    legacy = tmp_path / "out" / "H_cycle_last_terminal_info.txt"
    assert canonical.exists()
    assert legacy.exists()


def test_wrapper_terminal_marker_requires_run_id(tmp_path: Path) -> None:
    live = tmp_path / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)

    ok, reason = guarded._write_last_terminal_marker_from_wrapper(
        live,
        run_id="",
        terminal_state="succeeded",
        stage="phase1_intel",
        publish_status="not_started",
    )

    assert not ok
    assert reason == "missing_run_id"


def test_classify_publish_from_failed_pilot_stage_does_not_assume_publish_attempt() -> None:
    view = guarded._classify_publish_from_run_state(
        {
            "run_id": "RUN_FAIL_PILOT_001",
            "state": "failed",
            "stage": "phase1_pilot",
            "publish_status": "not_started",
            "failure_code": "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH",
        },
        "RUN_FAIL_PILOT_001",
    )

    assert view.get("usable") == "1"
    assert view.get("publish_attempted_for_run") == "0"
    assert view.get("publish_started_for_run") == "0"
    assert view.get("publish_completed_for_run") == "0"
    assert view.get("post_pilot_transition_for_run") == "1"
    assert view.get("post_pilot_transition_status") == "pilot_completed"


def test_classify_publish_from_failed_publish_stage_preserves_publish_attempt_truth() -> None:
    view = guarded._classify_publish_from_run_state(
        {
            "run_id": "RUN_FAIL_PUBLISH_001",
            "state": "failed",
            "stage": "phase1_publish",
            "publish_status": "started",
            "failure_code": "LOOP_RC_3",
        },
        "RUN_FAIL_PUBLISH_001",
    )

    assert view.get("usable") == "1"
    assert view.get("publish_attempted_for_run") == "1"
    assert view.get("publish_started_for_run") == "1"
    assert view.get("publish_completed_for_run") == "0"
    assert view.get("post_pilot_transition_for_run") == "1"
    assert view.get("post_pilot_transition_status") == "publish_entered"


def test_classify_pilot_handoff_success_is_fail_closed_parent_exit_boundary() -> None:
    code, reason = guarded._classify_pilot_handoff_terminal(
        "RUN_PARENT_EXIT_001",
        {
            "marker_exists": "1",
            "marker_status": "success",
            "marker_run_id": "RUN_PARENT_EXIT_001",
            "marker_result_ok": "1",
            "result_size": "128",
        },
    )

    assert code == "PHASE1_PILOT_PARENT_EXIT_BEFORE_PUBLISH_CONTINUITY"
    assert reason == "pilot_success_observed_but_parent_owner_lost_before_publish_continuity"


def test_wrapper_terminal_truth_requires_finalized_success_and_same_run_publish() -> None:
    view = guarded._classify_wrapper_terminal_truth(
        run_id="RUN_FINAL_001",
        run_state={
            "run_id": "RUN_FINAL_001",
            "state": "finalized",
            "stage": "phase1_publish",
            "publish_status": "ok",
            "failure_code": "",
        },
        worker_lifecycle={
            "run_id": "RUN_FINAL_001",
            "state": "succeeded",
        },
        publish_proof={
            "selected_run_id": "RUN_FINAL_001",
        },
    )

    assert view.get("ok") == "1"
    assert view.get("reason") == "terminal_truth_verified"
    assert view.get("run_state_state") == "finalized"


def test_wrapper_terminal_truth_rejects_publish_done_without_finalized() -> None:
    view = guarded._classify_wrapper_terminal_truth(
        run_id="RUN_FINAL_002",
        run_state={
            "run_id": "RUN_FINAL_002",
            "state": "publish_done",
            "stage": "phase1_publish",
            "publish_status": "ok",
            "failure_code": "",
        },
        worker_lifecycle={
            "run_id": "RUN_FINAL_002",
            "state": "succeeded",
        },
        publish_proof={
            "selected_run_id": "RUN_FINAL_002",
        },
    )

    assert view.get("ok") == "0"
    assert view.get("boundary_code") == "RUN_STATE_PUBLISH_DONE_NOT_FINALIZED"
    assert view.get("reason") == "run_state_not_finalized"


def test_wrapper_terminal_truth_rejects_non_succeeded_worker_state() -> None:
    view = guarded._classify_wrapper_terminal_truth(
        run_id="RUN_FINAL_003",
        run_state={
            "run_id": "RUN_FINAL_003",
            "state": "finalized",
            "stage": "phase1_publish",
            "publish_status": "ok",
            "failure_code": "",
        },
        worker_lifecycle={
            "run_id": "RUN_FINAL_003",
            "state": "running",
        },
        publish_proof={
            "selected_run_id": "RUN_FINAL_003",
        },
    )

    assert view.get("ok") == "0"
    assert view.get("boundary_code") == "WORKER_LIFECYCLE_NOT_SUCCEEDED"
    assert view.get("reason") == "worker_lifecycle_not_succeeded"


def test_wrapper_terminal_truth_rejects_publish_proof_mismatch() -> None:
    view = guarded._classify_wrapper_terminal_truth(
        run_id="RUN_FINAL_004",
        run_state={
            "run_id": "RUN_FINAL_004",
            "state": "finalized",
            "stage": "phase1_publish",
            "publish_status": "ok",
            "failure_code": "",
        },
        worker_lifecycle={
            "run_id": "RUN_FINAL_004",
            "state": "succeeded",
        },
        publish_proof={
            "selected_run_id": "RUN_OLD",
        },
    )

    assert view.get("ok") == "0"
    assert view.get("boundary_code") == "FINALIZED_WITHOUT_SAME_RUN_PUBLISH_PROOF"
    assert view.get("reason") == "publish_proof_run_id_mismatch"
