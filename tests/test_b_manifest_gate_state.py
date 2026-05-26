from __future__ import annotations

import csv
from pathlib import Path

from scripts.cycles import run_B_cycle as b_cycle


def _write_checklist(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status"])
        writer.writeheader()
        writer.writerows(rows)


def test_b_gate_state_payload_marks_completed_with_gate_fail(tmp_path: Path) -> None:
    checklist = tmp_path / "checklist_B.csv"
    _write_checklist(
        checklist,
        [
            {"check": "orders_fresh", "status": "ok"},
            {"check": "token_shortages_by_sku", "status": "fail"},
            {"check": "collector_warning", "status": "warn"},
        ],
    )

    payload = b_cycle._b_gate_state_payload(checklist, health_rc=2)

    assert payload["gate_state"] == "fail"
    assert payload["gate_fail_count"] == 1
    assert payload["gate_warn_count"] == 1
    assert payload["blocking_checks"] == ["token_shortages_by_sku"]


def test_manifest_flush_records_gate_truth_without_changing_completed_state(tmp_path: Path, monkeypatch) -> None:
    checklist = tmp_path / "checklist_B.csv"
    manifest_root = tmp_path / "repo"
    _write_checklist(checklist, [{"check": "token_shortages_by_sku", "status": "fail"}])

    monkeypatch.setattr(b_cycle, "ROOT", manifest_root)
    monkeypatch.setattr(b_cycle, "B_GATE_CHECKLIST_PATH", checklist)
    b_cycle.CURRENT_MANIFEST = b_cycle.new_manifest(
        cycle="B",
        run_id="B_TEST_GATE_STATE",
        start_time="2026-05-18T12:00:00Z",
    )
    b_cycle.CURRENT_MANIFEST["configured_step_count"] = 0

    b_cycle._manifest_flush(final_state="completed", gate_path=checklist, health_rc=2)

    manifest_path = manifest_root / "out" / "manifests" / "B" / "2026-05-18" / "B_TEST_GATE_STATE.json"
    payload = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["final_state"] == "completed"
    assert payload["gate_state"] == "fail"
    assert payload["completed_with_gate_fail"] is True
    assert payload["blocking_checks"] == ["token_shortages_by_sku"]


def test_b_maintenance_abort_step_is_not_a_failed_step() -> None:
    b_cycle.CURRENT_MANIFEST = b_cycle.new_manifest(cycle="B", run_id="B_TEST_MAINT_ABORT")
    try:
        b_cycle._manifest_add_step(
            name="B011_recover_l3_orphans.py",
            script_or_function="B011_recover_l3_orphans.py",
            rc=125,
            started_at="2026-05-18T12:00:00Z",
            notes="maintenance_abort_no_retry",
            step_status="maintenance_aborted",
            verification_status="maintenance_abort",
        )
        step = b_cycle.CURRENT_MANIFEST["steps"][0]
        assert step["step_status"] == "maintenance_aborted"
        assert step["verification_status"] == "maintenance_abort"
    finally:
        b_cycle.CURRENT_MANIFEST = None


def test_b_only_maintenance_marker_can_request_restart_drain(tmp_path: Path, monkeypatch) -> None:
    b_marker = tmp_path / "out" / "locks" / "b_cycle.maintenance"
    global_marker = tmp_path / "out" / "locks" / "maintenance.requested"
    b_marker.parent.mkdir(parents=True, exist_ok=True)
    b_marker.write_text(
        "target_flow=B|action=restart_drain|exit_after_drain=1|request_id=B_RELOAD_TEST\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(b_cycle, "MAINTENANCE_FLAG_PATH", b_marker)
    monkeypatch.setattr(b_cycle, "MAINTENANCE_REQUEST_PATH", global_marker)

    assert b_cycle._maintenance_requested() is True
    assert b_cycle._restart_drain_requested() is True
    assert b_cycle._parse_marker_field(b_cycle._maintenance_request_text(), "request_id") == "B_RELOAD_TEST"
