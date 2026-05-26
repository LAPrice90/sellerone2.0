from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.tools import controlled_restart_controller as controller
from scripts.tools import home_time_common
from scripts.tools import home_time_monitor


def test_restart_tools_observer_by_default(monkeypatch) -> None:
    monkeypatch.delenv(controller.DEFAULT_ESCALATION_MODE_ENV, raising=False)
    args = argparse.Namespace(escalation_mode=False)
    assert controller._escalation_mode_enabled(args) is False


def test_post_heal_recheck_cannot_approve_reboot_after_terminal_skip() -> None:
    assert (
        controller._post_heal_recheck_can_drive_restart_decision(
            execute_reboot=True,
            allow_reboot_action=True,
            pre_heal_decision="skipped",
        )
        is False
    )
    assert (
        controller._post_heal_recheck_can_drive_restart_decision(
            execute_reboot=True,
            allow_reboot_action=True,
            pre_heal_decision="approved",
        )
        is True
    )
    assert (
        controller._post_heal_recheck_can_drive_restart_decision(
            execute_reboot=False,
            allow_reboot_action=False,
            pre_heal_decision="skipped",
        )
        is True
    )


def test_controller_preserves_terminal_skip_after_post_heal_owner_relaunch(monkeypatch, tmp_path: Path) -> None:
    captured_payloads: list[dict[str, object]] = []
    gate_phases: list[str] = []

    def fake_run_gate(**kwargs):
        phase = "initial" if not gate_phases else "post_heal"
        gate_phases.append(phase)
        return {
            "rc": 0,
            "gate_result": {
                "phase": phase,
                "evidence_paths": {"eval_path": str(tmp_path / f"{phase}.json")},
            },
        }

    def fake_load_gate_eval(gate_result):
        phase = gate_result.get("phase")
        if phase == "initial":
            return {
                "decision": "skipped",
                "blockers": ["H_LAUNCHER_ACTIVE", "AMBIGUOUS_OWNERSHIP_HOLD"],
            }
        return {
            "decision": "skipped",
            "blockers": [
                "H_LAUNCHER_ACTIVE",
                "H_CYCLE_ACTIVE_LOCK",
                "B_ACTIVE_LOCK",
                "F_MANAGER_ACTIVE_LOCK",
                "AMBIGUOUS_OWNERSHIP_HOLD",
            ],
        }

    monkeypatch.setattr(controller, "_window_check", lambda **kwargs: (True, {"in_window": True}))
    monkeypatch.setattr(controller, "_simplification_freeze_active", lambda: False)
    monkeypatch.setattr(controller, "_write_ownership_transfer", lambda **kwargs: (True, "ownership_transfer_recorded"))
    monkeypatch.setattr(controller, "_append_jsonl", lambda path, payload: None)
    monkeypatch.setattr(controller, "_run_gate", fake_run_gate)
    monkeypatch.setattr(controller, "_load_gate_eval", fake_load_gate_eval)
    monkeypatch.setattr(controller, "_safe_remove_drain_marker", lambda: (True, "removed"))
    monkeypatch.setattr(controller, "_safe_clear_h_controlled_mode_flag", lambda: (True, "removed"))
    monkeypatch.setattr(controller, "_heal_and_start_task", lambda *args, **kwargs: (True, "started_verified"))
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(controller, "_home_time_mode_active", lambda: False)
    monkeypatch.setattr(
        controller,
        "_submit_windows_reboot",
        lambda comment: (_ for _ in ()).throw(AssertionError("reboot must not be submitted")),
    )
    monkeypatch.setattr(
        controller,
        "_write_controller_evidence",
        lambda *, payload, run_id: captured_payloads.append(payload) or {"latest_json": str(tmp_path / "latest.json")},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "controlled_restart_controller.py",
            "--caller-task-name",
            controller.DEFAULT_CONTROLLER_TASK_NAME,
            "--escalation-mode",
            "--execute-reboot",
            "--allow-reboot-action",
            "--request-drain",
            "--clear-drain-on-skip",
            "--max-wait-seconds",
            "0",
        ],
    )

    assert controller.main() == 0
    payload = captured_payloads[-1]
    assert payload["decision"] == "skipped"
    assert payload["final_blockers"] == ["H_LAUNCHER_ACTIVE", "AMBIGUOUS_OWNERSHIP_HOLD"]
    assert payload["post_heal_gate_recheck_blockers"] == [
        "H_LAUNCHER_ACTIVE",
        "H_CYCLE_ACTIVE_LOCK",
        "B_ACTIVE_LOCK",
        "F_MANAGER_ACTIVE_LOCK",
        "AMBIGUOUS_OWNERSHIP_HOLD",
    ]
    assert payload["post_heal_recheck_can_drive_decision"] is False
    assert payload["outcome"] == "skipped_not_approved_ownership_restored"


def test_home_time_never_claims_runtime_ownership(monkeypatch, tmp_path: Path) -> None:
    log_events: list[dict[str, object]] = []

    monkeypatch.setattr(
        home_time_monitor,
        "active_home_time_payload",
        lambda root: {"session_id": "test_session", "H_launcher_owner_pid": "111"},
    )
    monkeypatch.setattr(
        home_time_monitor,
        "collect_home_time_snapshot",
        lambda root: {
            "anomalies": ["runtime_error_mode"],
            "H_launcher_owner_pid": "111",
            "runtime_status_snapshot": {"mode": "ERROR", "pid": "222", "run_id": "RUNX"},
        },
    )
    monkeypatch.setattr(home_time_monitor, "_task_state", lambda task_name: "Running")
    monkeypatch.setattr(home_time_monitor, "active_h_launcher_processes", lambda root: [])
    monkeypatch.setattr(home_time_monitor, "active_h_python_processes", lambda root: [])
    monkeypatch.setattr(home_time_monitor, "_pid_is_alive", lambda pid_text: False)
    monkeypatch.setattr(home_time_monitor, "append_jsonl", lambda path, payload: log_events.append(dict(payload)))
    monkeypatch.setattr(
        home_time_monitor,
        "write_diagnostic_snapshot",
        lambda root, payload, prefix="H_home_time_diagnostic", timestamp_utc=None: root / f"{prefix}.json",
    )

    result = home_time_monitor.monitor_home_time(
        root=tmp_path,
        iterations=1,
        interval_seconds=0.1,
        allow_safe_archive=True,
        allow_safe_bootstrap=True,
        active_remediation=True,
    )

    assert "runtime_error_mode" in result["anomalies_seen"]
    assert result["remediations"] == []
    assert result["observer_only_enforced"] is True
    assert result["requested_active_remediation"] is True
    assert result["requested_allow_safe_archive"] is True
    assert result["requested_allow_safe_bootstrap"] is True

    observer_events = [item for item in log_events if item.get("event") == "home_time_monitor_observer_only"]
    assert observer_events
    latest = observer_events[-1]
    assert latest.get("reason") == "observer_only_design"
    assert latest.get("requested_active_remediation") is True
    assert latest.get("requested_allow_safe_archive") is True
    assert latest.get("requested_allow_safe_bootstrap") is True


def test_maintenance_scope_a_b_only(tmp_path: Path) -> None:
    expected = {
        "maintenance.requested",
        "maintenance.ready",
        "maintenance.active",
        "b_cycle.maintenance",
    }
    assert set(home_time_common.MAINTENANCE_MARKER_NAMES) == expected

    locks_dir = tmp_path / "out" / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    (locks_dir / "maintenance.requested").write_text("A_REQ\n", encoding="utf-8")
    (locks_dir / "h_controlled_mode.active").write_text("legacy\n", encoding="utf-8")

    summary = home_time_common.maintenance_state_summary(locks_dir)
    present = summary.get("maintenance_markers_present", [])

    assert "maintenance.requested" in present
    assert "h_controlled_mode.active" not in present


def test_home_time_monitor_supervisor_launches_hidden() -> None:
    text = (ROOT / "run_home_time_monitor_supervisor.bat").read_text(encoding="utf-8", errors="replace")
    assert "HOME_TIME_MONITOR_SUPERVISOR_DETACHED" in text
    assert "Start-Process -WindowStyle Hidden -FilePath 'cmd.exe'" in text
