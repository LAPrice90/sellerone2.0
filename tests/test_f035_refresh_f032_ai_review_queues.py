from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.one_off.F035_refresh_f032_ai_review_queues import refresh_f032_ai_review_queues


def test_f035_summary_keeps_ai_gate_green_while_showing_upstream_blocked(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-05-22T05:00:00Z",
                "run_id": "cycle-1",
                "owner_pid": "123",
                "state": "blocked_state_regression",
                "active_supplier_id": "td_synnex",
                "active_f061_run_id": "fpm_td_synnex_20260519T095000Z",
                "pending_rows": "46067",
                "last_action": "state_regression_guard",
                "last_action_status": "blocked",
                "chunk_rows": "50",
                "drain_ready": "0",
                "notes": "latest_scanner_pending_after=44709",
            }
        ]
    ).to_csv(live_dir / "live_cycle_status.csv", index=False)
    pd.DataFrame(
        [
            {
                "event_utc": "2026-05-21T16:00:00Z",
                "cycle_run_id": "cycle-before",
                "event_type": "scanner_chunk",
                "supplier_id": "td_synnex",
                "f061_run_id": "fpm_td_synnex_20260519T095000Z",
                "status": "success",
                "rows": "50",
                "notes": "pending_after=44709",
            }
        ]
    ).to_csv(live_dir / "live_cycle_events.csv", index=False)

    summary = refresh_f032_ai_review_queues(
        root=tmp_path,
        observed_utc="2026-05-22T05:10:00Z",
    )

    assert summary["candidate_manifest_count"] == 0
    assert summary["quality_summary"]["status"] == "ok"
    assert summary["status_counts"]["upstream_blocked"] == 1
    upstream = summary["upstream_throughput_summary"]
    assert upstream["upstream_status"] == "blocked"
    assert upstream["live_cycle_state"] == "blocked_state_regression"
    assert upstream["latest_scanner_chunk_pending_after"] == "44709"
    precheck = summary["precheck_summary"]
    assert precheck["catchup_status"] in {"no_eligible_rows", "pending_ai_decision", "ready_hidden"}
    assert precheck["precheck_pending_ai_decision_rows"] == 0
    assert precheck["final_handoff_pending_ai_decision_rows"] == 0


def test_f035_precheck_catchup_uses_scanner_fallback_when_status_is_already_running(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-05-22T08:00:00Z",
                "run_id": "duplicate-owner",
                "owner_pid": "999",
                "state": "already_running",
                "active_supplier_id": "",
                "active_f061_run_id": "",
                "pending_rows": "0",
                "last_action": "acquire_lock",
                "last_action_status": "blocked",
                "chunk_rows": "25",
                "drain_ready": "0",
                "notes": "lock_held",
            }
        ]
    ).to_csv(live_dir / "live_cycle_status.csv", index=False)
    pd.DataFrame(
        [
            {
                "event_utc": "2026-05-22T07:55:10Z",
                "cycle_run_id": "cycle-active",
                "event_type": "scanner_chunk",
                "supplier_id": "td_synnex",
                "f061_run_id": "fpm_td_synnex_20260519T095000Z",
                "status": "success",
                "rows": "25",
                "notes": "pending_after=44609",
            }
        ]
    ).to_csv(live_dir / "live_cycle_events.csv", index=False)
    (live_dir / "f061_child_status.txt").write_text(
        "pid=123|supplier_id=td_synnex|manager_mode=Scanning Hidden|heartbeat=2026-05-22T08:01:00Z\n",
        encoding="ascii",
    )

    summary = refresh_f032_ai_review_queues(
        root=tmp_path,
        observed_utc="2026-05-22T08:02:00Z",
    )

    upstream = summary["upstream_throughput_summary"]
    assert upstream["live_cycle_active_supplier_id"] == "td_synnex"
    assert upstream["live_cycle_active_f061_run_id"] == "fpm_td_synnex_20260519T095000Z"
    assert summary["precheck_summary"]["catchup_status"] in {"no_eligible_rows", "pending_ai_decision", "ready_hidden"}
