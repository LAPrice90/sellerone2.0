from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import write_o_contract_df
from scripts.one_off.P016_repricing_tracker_ui_cutover_check import run_check


def _write_proof(path: Path, **overrides: object) -> None:
    payload = {
        "terminal_run_id": "20260501T183549Z",
        "terminal_state": "finalized",
        "terminal_publish_status": "ok",
        "runtime_blank_execution_write_status_rows": 0,
        "invalid_execution_write_status_rows": 0,
        "pricing_output_stale": True,
        "pricing_output_stale_reason": "pricing_output_older_than_runtime_and_missing_latest_runtime_run",
    }
    payload.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_tracker_outputs(root: Path, *, fail_health: bool = False) -> None:
    write_o_contract_df(
        root,
        "repricer_tracker_view",
        pd.DataFrame(
            [
                {
                    "sku": "SKU-1",
                    "asin": "ASIN-1",
                    "source_run_id": "20260501T183549Z",
                    "tracker_status": "no_write_required",
                    "raw_execution_write_status": "NO_WRITE_REQUIRED",
                }
            ]
        ),
    )
    health_rows = [
        {
            "check": "repricer_tracker_blank_execution_write_status",
            "status": "ok",
            "value": "0",
            "notes": "runtime blank status ok",
        },
        {
            "check": "repricer_tracker_pricing_output_freshness",
            "status": "warn",
            "value": "1",
            "notes": "stale audit",
        },
    ]
    if fail_health:
        health_rows.append(
            {
                "check": "repricer_tracker_latest_terminal_state",
                "status": "fail",
                "value": "failed",
                "notes": "terminal failed",
            }
        )
    write_o_contract_df(root, "repricer_tracker_health", pd.DataFrame(health_rows))


def test_p016_ready_with_stale_audit_warning(tmp_path: Path) -> None:
    proof_path = tmp_path / "proof.json"
    _write_proof(proof_path)
    _write_tracker_outputs(tmp_path)

    payload = run_check(
        root=tmp_path,
        proof_summary_path=proof_path,
        output_dir=tmp_path / "proof",
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "ready_with_stale_audit_warning"
    assert payload["fail_count"] == 0
    assert payload["tracker_rows"] == 1
    assert payload["sheet_status"] == "temporary_fallback_until_explicit_operator_cutover"


def test_p016_fails_when_o050_health_has_fail(tmp_path: Path) -> None:
    proof_path = tmp_path / "proof.json"
    _write_proof(proof_path)
    _write_tracker_outputs(tmp_path, fail_health=True)

    payload = run_check(
        root=tmp_path,
        proof_summary_path=proof_path,
        output_dir=tmp_path / "proof",
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "fail"
    checks = pd.read_csv(tmp_path / "proof" / "repricer_tracker_ui_cutover_check.csv", dtype=str).fillna("")
    no_fail = checks[checks["check"].eq("o050_tracker_health_no_fail")].iloc[0]
    assert no_fail["status"] == "fail"


def test_p016_fails_when_runtime_blank_status_remains(tmp_path: Path) -> None:
    proof_path = tmp_path / "proof.json"
    _write_proof(proof_path, runtime_blank_execution_write_status_rows=2)
    _write_tracker_outputs(tmp_path)

    payload = run_check(
        root=tmp_path,
        proof_summary_path=proof_path,
        output_dir=tmp_path / "proof",
        observed_utc="2026-05-01T11:00:00Z",
    )

    assert payload["status"] == "fail"
