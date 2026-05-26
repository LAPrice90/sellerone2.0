from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.tools.home_time_common import detect_state_anomalies


def _base_snapshot() -> dict[str, object]:
    return {
        "H_launcher_owner_pid": "22908",
        "h_launcher_lock_exists": True,
        "runtime_status_snapshot": {
            "run_id": "20260401T134620Z",
            "mode": "RUNNING",
            "detail": "phase1_pilot",
            "error": "",
        },
        "H_run_in_progress": "",
        "H_last_finalized_run": "20260401T132817Z",
        "boundary_state_summary": {
            "unresolved_exists": False,
            "details": [
                {
                    "run_id": "20260401T134620Z",
                    "status": "resolved_success",
                    "state_reason": "",
                }
            ],
        },
    }


def test_running_without_run_in_progress_is_suppressed_for_finalized_no_publish_idle() -> None:
    snapshot = _base_snapshot()
    snapshot["runtime_status_snapshot"] = {
        "run_id": "20260401T134620Z",
        "mode": "RUNNING",
        "detail": "wrapper_no_publish_terminal_ok",
        "error": "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH",
    }
    snapshot["H_last_finalized_run"] = "20260401T134620Z"

    anomalies = detect_state_anomalies(snapshot)

    assert "runtime_running_without_run_in_progress" not in anomalies


def test_running_without_run_in_progress_still_flags_for_non_finalized_running_state() -> None:
    snapshot = _base_snapshot()
    snapshot["runtime_status_snapshot"] = {
        "run_id": "20260401T140001Z",
        "mode": "RUNNING",
        "detail": "phase1_pilot",
        "error": "",
    }
    snapshot["H_last_finalized_run"] = "20260401T134620Z"

    anomalies = detect_state_anomalies(snapshot)

    assert "runtime_running_without_run_in_progress" in anomalies


def test_running_without_run_in_progress_still_flags_when_boundary_unresolved() -> None:
    snapshot = _base_snapshot()
    snapshot["runtime_status_snapshot"] = {
        "run_id": "20260401T134620Z",
        "mode": "RUNNING",
        "detail": "wrapper_no_publish_terminal_ok",
        "error": "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH",
    }
    snapshot["H_last_finalized_run"] = "20260401T134620Z"
    snapshot["boundary_state_summary"] = {
        "unresolved_exists": True,
        "details": [
            {
                "run_id": "20260401T134620Z",
                "status": "unresolved_parent_exit",
                "state_reason": "parent_owner_lost",
            }
        ],
    }

    anomalies = detect_state_anomalies(snapshot)

    assert "runtime_running_without_run_in_progress" in anomalies

