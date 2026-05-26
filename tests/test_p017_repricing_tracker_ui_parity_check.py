from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import write_o_contract_df
from scripts.one_off.P017_repricing_tracker_ui_parity_check import run_check


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _tracker_row() -> dict[str, str]:
    return {
        "asof_utc": "2026-05-01T10:00:00Z",
        "source_snapshot_utc": "2026-05-01T10:00:00Z",
        "source_run_id": "RUN-1",
        "latest_terminal_run_id": "RUN-1",
        "sku": "SKU-1",
        "asin": "ASIN-1",
        "tracker_status": "READ_ONLY",
        "capability_status": "READ_ONLY_OR_BLOCKED",
        "eligible_to_write_flag": "0",
        "decision_to_change_price_flag": "0",
        "write_attempted_flag": "0",
        "write_applied_flag": "0",
        "raw_execution_write_status": "NO_WRITE_REQUIRED",
        "write_status_issue": "",
        "execution_state": "HOLD",
        "current_cycle_decision": "execute",
        "current_cycle_decision_reason_code": "eligible",
        "current_cycle_blocker_code": "",
        "old_price_gbp": "9.99",
        "new_price_gbp": "9.99",
        "hard_floor_gbp": "8.00",
        "ceiling_gbp": "12.00",
        "true_binding_ceiling_gbp": "12.00",
        "buy_box_state": "NORMAL",
        "strategy_state": "HOLD",
        "writer_outcome": "NO_WRITE_REQUIRED",
        "truth_status": "READ_ONLY",
        "source_path": "runtime.csv",
        "is_latest_terminal_run": "1",
    }


def test_p017_ready_with_stale_audit_warning(tmp_path: Path) -> None:
    p013 = tmp_path / "p013.json"
    p016 = tmp_path / "p016.json"
    _write_json(p013, {"terminal_run_id": "RUN-1", "terminal_utc": "2026-05-01T10:30:00Z"})
    _write_json(p016, {"status": "ready_with_stale_audit_warning", "fail_count": 0, "sheet_status": "temporary_fallback_until_explicit_operator_cutover"})
    write_o_contract_df(tmp_path, "repricer_tracker_view", pd.DataFrame([_tracker_row()]))
    write_o_contract_df(tmp_path, "repricer_tracker_health", pd.DataFrame([{"check": "ok", "status": "ok", "value": "0", "notes": "", "observed_utc": "", "source_path": ""}]))
    dashboard = tmp_path / "out" / "analysis_reports" / "phase1_observation_view_2026-05-01.csv"
    dashboard.parent.mkdir(parents=True)
    pd.DataFrame([{"SKU": "SKU-1", "Status": "OK", "Write Result": "NO_WRITE_REQUIRED", "Floor": "8", "Current": "9", "Ceiling": "12", "Buy Box": "NORMAL", "State": "HOLD"}]).to_csv(dashboard, index=False)

    payload = run_check(root=tmp_path, p013_summary_path=p013, p016_summary_path=p016, output_dir=tmp_path / "proof", observed_utc="2026-05-01T11:00:00Z")

    assert payload["status"] == "ready_with_stale_audit_warning"
    assert payload["fail_count"] == 0
    assert payload["missing_critical_field_count"] == 0


def test_p017_fails_when_critical_tracker_column_missing(tmp_path: Path) -> None:
    p013 = tmp_path / "p013.json"
    p016 = tmp_path / "p016.json"
    _write_json(p013, {"terminal_run_id": "RUN-1", "terminal_utc": "2026-05-01T10:30:00Z"})
    _write_json(p016, {"status": "ready", "fail_count": 0, "sheet_status": "temporary_fallback_until_explicit_operator_cutover"})
    row = _tracker_row()
    row.pop("raw_execution_write_status")
    path = tmp_path / "out" / "systems" / "O" / "live" / "repricer_tracker_view.csv"
    path.parent.mkdir(parents=True)
    pd.DataFrame([row]).to_csv(path, index=False)
    write_o_contract_df(tmp_path, "repricer_tracker_health", pd.DataFrame([{"check": "ok", "status": "ok", "value": "0", "notes": "", "observed_utc": "", "source_path": ""}]))

    payload = run_check(root=tmp_path, p013_summary_path=p013, p016_summary_path=p016, output_dir=tmp_path / "proof", observed_utc="2026-05-01T11:00:00Z")

    assert payload["status"] == "fail"
    checks = pd.read_csv(tmp_path / "proof" / "repricer_tracker_ui_parity_check.csv", dtype=str).fillna("")
    critical = checks[checks["check"].eq("critical_tracker_fields_present")].iloc[0]
    assert critical["status"] == "fail"
    assert "raw_execution_write_status" in critical["value"]
