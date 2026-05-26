from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from scripts.one_off.P013_repricing_write_status_proof import (
    run_repricing_write_status_proof,
    write_outputs,
)


def _write_kv(path: Path, rows: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{key}={value}\n" for key, value in rows.items()), encoding="utf-8")


def _write_pricing_like(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        rows,
        columns=[
            "sku",
            "current_cycle_run_id",
            "execution_write_status",
            "truth_status",
            "current_cycle_decision",
            "current_cycle_blocker_code",
            "unified_writer_outcome",
        ],
    ).to_csv(path, index=False)


def test_repricing_write_status_proof_classifies_known_blank_causes(tmp_path: Path) -> None:
    runtime = tmp_path / "phase1_runtime_floor_snapshot_latest.csv"
    pricing = tmp_path / "pricing_output.csv"
    terminal = tmp_path / "H_cycle_last_terminal_info.txt"
    publish = tmp_path / "H_cycle_last_publish_info.txt"
    rows = [
        {
            "sku": "SKU-NO-MARKET",
            "current_cycle_run_id": "RUN-1",
            "execution_write_status": "",
            "truth_status": "READ_ONLY",
            "current_cycle_decision": "skip_no_market_data",
            "current_cycle_blocker_code": "MARKET_DATA_MISSING_CURRENT_CYCLE",
            "unified_writer_outcome": "",
        },
        {
            "sku": "SKU-PARKED",
            "current_cycle_run_id": "RUN-1",
            "execution_write_status": "",
            "truth_status": "PARKED",
            "current_cycle_decision": "execute",
            "current_cycle_blocker_code": "",
            "unified_writer_outcome": "NO_WRITE_REQUIRED",
        },
        {
            "sku": "SKU-OK",
            "current_cycle_run_id": "RUN-1",
            "execution_write_status": "NO_WRITE_REQUIRED",
            "truth_status": "NO_WRITE_REQUIRED",
            "current_cycle_decision": "execute",
            "current_cycle_blocker_code": "",
            "unified_writer_outcome": "NO_WRITE_REQUIRED",
        },
        {
            "sku": "SKU-NOT-APPLIED",
            "current_cycle_run_id": "RUN-1",
            "execution_write_status": "WRITE_NOT_APPLIED",
            "truth_status": "READ_ONLY",
            "current_cycle_decision": "skip_cooldown",
            "current_cycle_blocker_code": "",
            "unified_writer_outcome": "WRITE_NOT_APPLIED",
        },
    ]
    _write_pricing_like(runtime, rows)
    _write_pricing_like(pricing, rows)
    _write_kv(terminal, {"run_id": "RUN-1", "state": "finalized", "publish_status": "ok"})
    _write_kv(publish, {"run_id": "RUN-1", "status": "ok", "rows": "3"})

    payload = run_repricing_write_status_proof(
        runtime_source=runtime,
        pricing_source=pricing,
        terminal_info_path=terminal,
        publish_info_path=publish,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert payload["status"] == "warn"
    assert payload["runtime_blank_execution_write_status_rows"] == 2
    assert payload["pricing_blank_execution_write_status_rows"] == 2
    assert payload["invalid_execution_write_status_rows"] == 0
    assert payload["unknown_blank_root_cause_rows"] == 0
    causes = {row["root_cause"]: row["row_count"] for row in payload["root_cause_rows"]}
    assert causes == {
        "no_market_data_execution_context_cleared": "1",
        "parked_execution_context_cleared": "1",
    }


def test_repricing_write_status_proof_fails_unknown_blank_status(tmp_path: Path) -> None:
    runtime = tmp_path / "phase1_runtime_floor_snapshot_latest.csv"
    pricing = tmp_path / "pricing_output.csv"
    terminal = tmp_path / "H_cycle_last_terminal_info.txt"
    publish = tmp_path / "H_cycle_last_publish_info.txt"
    _write_pricing_like(
        runtime,
        [
            {
                "sku": "SKU-UNKNOWN",
                "current_cycle_run_id": "RUN-1",
                "execution_write_status": "",
                "truth_status": "",
                "current_cycle_decision": "",
                "current_cycle_blocker_code": "",
                "unified_writer_outcome": "",
            }
        ],
    )
    _write_pricing_like(pricing, [])
    _write_kv(terminal, {"run_id": "RUN-1", "state": "finalized", "publish_status": "ok"})
    _write_kv(publish, {"run_id": "RUN-1", "status": "ok", "rows": "1"})

    payload = run_repricing_write_status_proof(
        runtime_source=runtime,
        pricing_source=pricing,
        terminal_info_path=terminal,
        publish_info_path=publish,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert payload["status"] == "fail"
    assert payload["unknown_blank_root_cause_rows"] == 1


def test_repricing_write_status_proof_marks_old_pricing_output_as_stale(tmp_path: Path) -> None:
    runtime = tmp_path / "phase1_runtime_floor_snapshot_latest.csv"
    pricing = tmp_path / "pricing_output.csv"
    terminal = tmp_path / "H_cycle_last_terminal_info.txt"
    publish = tmp_path / "H_cycle_last_publish_info.txt"
    _write_pricing_like(
        runtime,
        [
            {
                "sku": "SKU-HISTORICAL-APPLIED",
                "current_cycle_run_id": "RUN-1",
                "execution_write_status": "APPLIED",
                "truth_status": "WRITE_APPLIED",
                "current_cycle_decision": "execute",
                "current_cycle_blocker_code": "",
                "unified_writer_outcome": "APPLIED",
            },
            {
                "sku": "SKU-OK",
                "current_cycle_run_id": "RUN-2",
                "execution_write_status": "NO_WRITE_REQUIRED",
                "truth_status": "NO_WRITE_REQUIRED",
                "current_cycle_decision": "execute",
                "current_cycle_blocker_code": "",
                "unified_writer_outcome": "NO_WRITE_REQUIRED",
            }
        ],
    )
    _write_pricing_like(
        pricing,
        [
            {
                "sku": "SKU-OLD-BLANK",
                "current_cycle_run_id": "RUN-1",
                "execution_write_status": "",
                "truth_status": "",
                "current_cycle_decision": "",
                "current_cycle_blocker_code": "",
                "unified_writer_outcome": "",
            }
        ],
    )
    os.utime(pricing, (1000, 1000))
    os.utime(runtime, (2000, 2000))
    _write_kv(terminal, {"run_id": "RUN-2", "state": "finalized", "publish_status": "ok"})
    _write_kv(publish, {"run_id": "RUN-2", "status": "ok", "rows": "1"})

    payload = run_repricing_write_status_proof(
        runtime_source=runtime,
        pricing_source=pricing,
        terminal_info_path=terminal,
        publish_info_path=publish,
        observed_utc="2026-05-01T10:00:00Z",
    )

    assert payload["status"] == "warn"
    assert payload["pricing_output_stale"] is True
    assert payload["pricing_output_stale_reason"] == "pricing_output_older_than_runtime_and_missing_latest_runtime_run"
    assert payload["pricing_blank_execution_write_status_rows"] == 1
    assert payload["current_pricing_blank_execution_write_status_rows"] == 0
    assert payload["runtime_write_status_counts"] == {"APPLIED": 1, "NO_WRITE_REQUIRED": 1}
    assert payload["runtime_proof_run_write_status_counts"] == {"NO_WRITE_REQUIRED": 1}
    assert payload["unknown_blank_root_cause_rows"] == 0
    assert payload["root_cause_rows"][0]["source_name"] == "pricing_output_stale"


def test_repricing_write_status_proof_writes_outputs(tmp_path: Path) -> None:
    runtime = tmp_path / "phase1_runtime_floor_snapshot_latest.csv"
    pricing = tmp_path / "pricing_output.csv"
    output_dir = tmp_path / "proof"
    _write_pricing_like(
        runtime,
        [
            {
                "sku": "SKU-OK",
                "current_cycle_run_id": "RUN-1",
                "execution_write_status": "NO_WRITE_REQUIRED",
                "truth_status": "NO_WRITE_REQUIRED",
                "current_cycle_decision": "execute",
                "current_cycle_blocker_code": "",
                "unified_writer_outcome": "NO_WRITE_REQUIRED",
            }
        ],
    )
    _write_pricing_like(pricing, [])
    payload = run_repricing_write_status_proof(
        runtime_source=runtime,
        pricing_source=pricing,
        observed_utc="2026-05-01T10:00:00Z",
    )

    outputs = write_outputs(payload, output_dir=output_dir)

    assert Path(outputs["root_cause"]).exists()
    assert Path(outputs["summary"]).exists()
