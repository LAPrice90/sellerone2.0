from __future__ import annotations

from scripts.tools import controlled_restart_controller as controller


def test_stale_h_marker_only_blockers_are_overridden_in_restart_window() -> None:
    decision, blockers, applied, reason, overridden = controller._stale_h_restart_override(
        active_actions_permitted=True,
        restart_window_active=True,
        final_decision="skipped",
        final_blockers=["H_RUN_IN_PROGRESS_NOT_FINALIZED", "H_LAUNCHER_HEARTBEAT_STALE"],
    )

    assert decision == "approved"
    assert blockers == []
    assert applied is True
    assert reason == "stale_h_marker_only_restart_override"
    assert overridden == ["H_RUN_IN_PROGRESS_NOT_FINALIZED", "H_LAUNCHER_HEARTBEAT_STALE"]


def test_stale_h_restart_override_does_not_hide_non_h_blockers() -> None:
    decision, blockers, applied, reason, overridden = controller._stale_h_restart_override(
        active_actions_permitted=True,
        restart_window_active=True,
        final_decision="skipped",
        final_blockers=["H_RUN_IN_PROGRESS_NOT_FINALIZED", "B_ACTIVE_LOCK"],
    )

    assert decision == "skipped"
    assert blockers == ["H_RUN_IN_PROGRESS_NOT_FINALIZED", "B_ACTIVE_LOCK"]
    assert applied is False
    assert reason == ""
    assert overridden == []
