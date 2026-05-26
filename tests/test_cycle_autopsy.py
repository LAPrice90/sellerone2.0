from __future__ import annotations

import json
from pathlib import Path

from scripts.tools import cycle_autopsy


def test_cycle_autopsy_summarizes_latest_failed_manifest(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "out" / "manifests" / "A" / "2026-05-18"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / "20260518T120000Z.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cycle": "A",
                "run_id": "20260518T120000Z",
                "start_time": "2026-05-18T12:00:00Z",
                "end_time": "2026-05-18T12:10:00Z",
                "final_state": "partial",
                "configured_step_count": 13,
                "recorded_step_count": 4,
                "health_summary": {"status": "missing", "fail_count": None, "warn_count": None},
                "steps": [
                    {
                        "name": "A003_run_inventory_to_sheet.py",
                        "script_or_function": "A003_run_inventory_to_sheet.py",
                        "rc": 0,
                        "step_status": "failed",
                        "verification_status": "failed_stale_outputs",
                        "notes": "stale=out/inventory_snapshot_latest.csv",
                        "stale_outputs": ["out/inventory_snapshot_latest.csv"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = cycle_autopsy.run_autopsy(tmp_path, ["A"], "latest")

    assert payload["status"] == "issue_found"
    summary = payload["summaries"][0]
    assert summary["run_id"] == "20260518T120000Z"
    assert summary["cause_code"] == "OUTPUT_STALE"
    assert "inventory_snapshot_latest.csv" in summary["cause_detail"]


def test_cycle_autopsy_can_write_completed_with_gate_fail_to_ledger(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "out" / "manifests" / "B" / "2026-05-18"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / "B_20260518T120000Z.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cycle": "B",
                "run_id": "B_20260518T120000Z",
                "start_time": "2026-05-18T12:00:00Z",
                "end_time": "2026-05-18T12:10:00Z",
                "final_state": "completed",
                "gate_state": "fail",
                "gate_rc": 2,
                "completed_with_gate_fail": True,
                "blocking_checks": ["token_shortages_by_sku"],
                "health_summary": {"status": "current", "fail_count": 1, "warn_count": 0},
                "steps": [],
            }
        ),
        encoding="utf-8",
    )

    payload = cycle_autopsy.run_autopsy(tmp_path, ["B"], "latest", write_ledger=True)

    assert payload["status"] == "issue_found"
    ledger = tmp_path / "out" / "cycle_alerts" / "cycle_failure_events.csv"
    assert ledger.exists()
    assert "token_shortages_by_sku" in ledger.read_text(encoding="utf-8")
