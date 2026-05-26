from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM190_build_split_rollout_readiness import (
    SPLIT_ROLLOUT_READINESS_COLUMNS,
    build_split_rollout_readiness,
)
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, REVIEW_HANDOFF_MANIFEST_COLUMNS


OBSERVED = "2026-05-22T12:45:00Z"


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _seed_ready_root(tmp_path: Path, *, quality_fail_checks: str = "0", quality_status: str = "ok") -> Path:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "live_cycle.lock").write_text(
        "pid=1234|start=2026-05-22T12:40:00Z|heartbeat=2026-05-22T12:44:00Z|owner=FPM130_live_cycle",
        encoding="utf-8",
    )
    _write_csv(
        live_dir / "live_cycle_status.csv",
        [
            {
                "observed_utc": OBSERVED,
                "run_id": "fpm_live_test",
                "owner_pid": "1234",
                "state": "running",
                "active_supplier_id": "supplier_a",
                "active_f061_run_id": "run_1",
                "pending_rows": "10",
            }
        ],
    )
    _write_csv(
        live_dir / "storage_drift_report.csv",
        [
            {
                "observed_utc": OBSERVED,
                "contract_name": "supplier_price_list_active_run",
                "row_delta_after": "0",
                "status_after": "ok",
            }
        ],
    )
    _write_csv(
        live_dir / "production_line_health.csv",
        [
            {
                "check": "f_production_line_stage_contract_runtime",
                "status": "ok",
                "value": "completed",
                "notes": "stage_count=5;browser_input_rows=2",
                "observed_utc": OBSERVED,
                "source_path": str(live_dir / "production_line_health.csv"),
            },
            {
                "check": "f_production_line_routing_runtime",
                "status": "ok",
                "value": "ready",
                "notes": "routing_mode=enforced;browser_input_rows=2",
                "observed_utc": OBSERVED,
                "source_path": str(live_dir / "production_line_health.csv"),
            },
        ],
        MANAGER_HEALTH_COLUMNS,
    )
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    manifest_row = {
        "built_at_utc": OBSERVED,
        "supplier_id": "supplier_a",
        "supplier_name": "Supplier A",
        "run_id": "run_1",
        "review_snapshot_id": "snapshot_1",
        "pass_review_rows": "1",
        "near_miss_review_rows": "0",
        "hard_reject_rows": "0",
        "pass_review_path": str(handoff_dir / "pass.csv"),
        "near_miss_review_path": str(handoff_dir / "near.csv"),
        "summary_path": str(handoff_dir / "summary.csv"),
        "handoff_dir": str(handoff_dir),
        "ai_gate_status": "passed",
        "ai_gate_quality_status": quality_status,
        "ai_gate_quality_fail_checks": quality_fail_checks,
        "ai_gate_quality_warn_checks": "0",
        "ai_gate_quality_report_path": str(live_dir / "ai_gate_quality_report.csv"),
        "operator_ready_flag": "1",
        "block_reason": "",
    }
    _write_csv(handoff_dir / "manifest.csv", [manifest_row], REVIEW_HANDOFF_MANIFEST_COLUMNS)
    _write_csv(live_dir / "review_handoff_manifest.csv", [manifest_row], REVIEW_HANDOFF_MANIFEST_COLUMNS)
    _write_csv(
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "pipeline_runs"
        / "supplier_a"
        / "run_1"
        / "production_line_speed_ledger.csv",
        [
            {
                "observed_utc": OBSERVED,
                "supplier_id": "supplier_a",
                "run_id": "run_1",
                "cycle_run_id": "fpm_live_test",
                "api_rows_checked": "10",
                "api_stopped_rows": "8",
                "retry_rows": "0",
                "browser_ready_rows": "2",
                "browser_rows_attempted": "2",
                "login_rows": "0",
                "api_429_count": "0",
                "endpoint_calls": "4",
                "elapsed_seconds": "12.5",
                "notes": "unit_test",
            }
        ],
    )
    return live_dir


def test_fpm190_writes_default_off_readiness_report(tmp_path: Path, monkeypatch) -> None:
    live_dir = _seed_ready_root(tmp_path)
    monkeypatch.delenv("FPM_PRODUCTION_LINE_EXECUTION_MODE", raising=False)
    monkeypatch.delenv("FPM_PRODUCTION_LINE_ROUTING_MODE", raising=False)

    summary = build_split_rollout_readiness(root=tmp_path, observed_utc=OBSERVED, emit_json=False)

    readiness = pd.read_csv(summary["readiness_path"], dtype=str).fillna("")
    production_health = pd.read_csv(live_dir / "production_line_health.csv", dtype=str).fillna("")
    execution_row = readiness[readiness["check"].eq("f_split_rollout_execution_default_off")].iloc[0]
    manifest_row = readiness[readiness["check"].eq("f_split_rollout_manifest_quality_gate")].iloc[0]
    summary_row = readiness[readiness["check"].eq("f_split_rollout_readiness")].iloc[0]

    assert summary["status"] == "ok"
    assert list(readiness.columns) == SPLIT_ROLLOUT_READINESS_COLUMNS
    assert execution_row["status"] == "ok"
    assert execution_row["value"] == "legacy_full"
    assert manifest_row["status"] == "ok"
    assert summary_row["value"] == "ready_default_off"
    assert "f_split_rollout_readiness" in set(production_health["check"])


def test_fpm190_blocks_when_operator_manifest_quality_failed(tmp_path: Path, monkeypatch) -> None:
    live_dir = _seed_ready_root(tmp_path, quality_fail_checks="1", quality_status="fail")
    monkeypatch.delenv("FPM_PRODUCTION_LINE_EXECUTION_MODE", raising=False)
    monkeypatch.delenv("FPM_PRODUCTION_LINE_ROUTING_MODE", raising=False)

    summary = build_split_rollout_readiness(root=tmp_path, observed_utc=OBSERVED, emit_json=False)

    readiness = pd.read_csv(summary["readiness_path"], dtype=str).fillna("")
    production_health = pd.read_csv(live_dir / "production_line_health.csv", dtype=str).fillna("")
    manifest_row = readiness[readiness["check"].eq("f_split_rollout_manifest_quality_gate")].iloc[0]
    summary_row = readiness[readiness["check"].eq("f_split_rollout_readiness")].iloc[0]
    health_summary = production_health[production_health["check"].eq("f_split_rollout_readiness")].iloc[-1]

    assert summary["status"] == "fail"
    assert summary["fail_checks"] == 1
    assert manifest_row["status"] == "fail"
    assert manifest_row["value"] == "blocked"
    assert summary_row["status"] == "fail"
    assert health_summary["status"] == "fail"
