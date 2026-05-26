from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
LOCKS = OUT / "locks"


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_first_line(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
    except Exception:
        return ""


def _parse_lock_line(line: str) -> dict[str, str]:
    pid_match = re.search(r"(?:^|\|)(?:pid|launcher_pid)=(\d+)", line)
    run_match = re.search(r"(?:^|\|)run_id=([^|\s]+)", line)
    heartbeat_match = re.search(r"(?:^|\|)heartbeat=([^|\s]+)", line)
    return {
        "pid": pid_match.group(1) if pid_match else "",
        "run_id": run_match.group(1) if run_match else "",
        "heartbeat": heartbeat_match.group(1) if heartbeat_match else "",
    }


def _pid_running(pid_text: str) -> bool | None:
    if not pid_text:
        return None
    try:
        pid = int(pid_text)
    except ValueError:
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        stdout = result.stdout or ""
        return str(pid) in stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _lock_state(root: Path, paths: list[Path]) -> dict[str, Any]:
    preferred = paths[0]
    for path in paths:
        if path.exists():
            line = _read_first_line(path)
            meta = _parse_lock_line(line)
            return {
                "exists": True,
                "path": _display_path(path, root),
                "line": line,
                "pid": meta["pid"],
                "pid_running": _pid_running(meta["pid"]),
                "run_id": meta["run_id"],
                "heartbeat": meta["heartbeat"],
            }
    return {
        "exists": False,
        "path": _display_path(preferred, root),
        "line": "",
        "pid": "",
        "pid_running": None,
        "run_id": "",
        "heartbeat": "",
    }


def _marker_state(root: Path, path: Path) -> dict[str, Any]:
    return {
        "exists": path.exists(),
        "path": _display_path(path, root),
        "line": _read_first_line(path),
    }


def _flow_state(flow: str, root: Path) -> dict[str, Any]:
    flow = flow.lower()
    state: dict[str, Any] = {
        "maintenance_requested": _marker_state(root, root / "out" / "locks" / "maintenance.requested"),
        "maintenance_ready": _marker_state(root, root / "out" / "locks" / "maintenance.ready"),
        "maintenance_active": _marker_state(root, root / "out" / "locks" / "maintenance.active"),
    }
    if flow in {"a", "b"}:
        state["b_cycle"] = _lock_state(
            root,
            [
                root / "out" / "systems" / "B" / "live" / "B_cycle.lock",
                root / "out" / "B_cycle.lock",
            ],
        )
        state["b_manual_maintenance"] = _marker_state(root, root / "out" / "locks" / "b_cycle.maintenance")
    if flow == "b":
        state["h_cycle"] = _lock_state(
            root,
            [
                root / "out" / "systems" / "H" / "live" / "H_cycle.lock",
                root / "out" / "systems" / "H" / "live" / "H_pricing_cycle.lock",
                root / "out" / "H_pricing_cycle.lock",
            ],
        )
        state["f_live_cycle"] = _lock_state(
            root,
            [
                root / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle.lock",
            ],
        )
    if flow == "e":
        state["e_cycle"] = _lock_state(
            root,
            [
                root / "out" / "systems" / "E" / "live" / "E_cycle.lock",
                root / "out" / "E_cycle.lock",
            ],
        )
    if flow == "h":
        state["h_cycle"] = _lock_state(
            root,
            [
                root / "out" / "systems" / "H" / "live" / "H_cycle.lock",
                root / "out" / "systems" / "H" / "live" / "H_pricing_cycle.lock",
                root / "out" / "H_pricing_cycle.lock",
            ],
        )
        state["h_run_in_progress"] = _marker_state(root, root / "out" / "systems" / "H" / "live" / "H_run_in_progress.txt")
        state["h_controlled_mode"] = _marker_state(root, root / "out" / "locks" / "h_controlled_mode.active")
    return state


def _a_plan(root: Path) -> dict[str, Any]:
    state = _flow_state("a", root)
    b_cycle = state["b_cycle"]
    maintenance_ready = state["maintenance_ready"]["exists"]
    if b_cycle["exists"] and b_cycle["pid_running"] is not False and not maintenance_ready:
        status = "boundary_or_pause_required"
        reason = "B ownership is still active or unresolved; use the A/B maintenance handoff and wait for maintenance.ready, not the next day."
    else:
        status = "ready_now"
        reason = "A proof can run at the owned A boundary."
    return {
        "flow": "a",
        "wait_for_next_scheduled_cycle_allowed": False,
        "can_proceed_without_next_cycle": True,
        "proof_mode": "owned_a_cycle",
        "proof_window_status": status,
        "state_reason": reason,
        "safe_boundary": "Run the owned A cycle path. If B is live, use maintenance.requested -> maintenance.ready -> maintenance.active first.",
        "preflight_checks": [
            "Confirm the change belongs to A-owned logic or A-owned outputs.",
            "Confirm B is idle or maintenance.ready exists for the current request.",
            "Do not use A015 alone as proof for A-owned behavior unless the user explicitly asked for that exact narrow run.",
            "Read fresh A outputs only after the A-owned run finalizes.",
        ],
        "command_sequence": [
            "python scripts/cycles/run_A_all.py",
            "Read out/system_health_checklist.csv and out/health_status.csv written by that A-owned run.",
        ],
        "disallowed_shortcuts": [
            "Do not use A015_build_system_health_check.py alone as proof for A-owned changes.",
            "Do not present a stale pre-change A snapshot as confirmation.",
        ],
        "fallback_rule": "If the B boundary cannot be obtained safely now, record the active lock or maintenance blocker and retry at the next safe maintenance boundary. Do not call it verified.",
        "current_state": state,
    }


def _b_plan(root: Path) -> dict[str, Any]:
    state = _flow_state("b", root)
    b_cycle = state["b_cycle"]
    h_cycle = state.get("h_cycle", {})
    f_live_cycle = state.get("f_live_cycle", {})
    cross_flow_owner_active = any(
        bool(owner.get("exists")) and owner.get("pid_running") is not False
        for owner in (h_cycle, f_live_cycle)
        if isinstance(owner, dict)
    )
    if b_cycle["exists"] and b_cycle["pid_running"] is not False:
        status = "boundary_or_pause_required"
        reason = "A live B owner is present or unresolved. Finish the current full cycle first, then use the scoped B maintenance marker for restart drain or run B_RUN_ONCE only after B ownership is idle."
    else:
        status = "ready_now"
        reason = "No active overlapping B owner is visible."
    if cross_flow_owner_active:
        reason += " Active H or F ownership is visible, so do not use the global maintenance.requested marker for B-only proof."
    return {
        "flow": "b",
        "wait_for_next_scheduled_cycle_allowed": False,
        "can_proceed_without_next_cycle": True,
        "proof_mode": "boundary_safe_b_run_once",
        "proof_window_status": status,
        "state_reason": reason,
        "safe_boundary": "If B is active, use out/locks/b_cycle.maintenance with action=restart_drain and let the current full B cycle finish. The B supervisor can then relaunch a fresh B owner without using the global maintenance.requested marker. If no B owner is active, run one full B proof cycle with B_RUN_ONCE=1 and read B-scoped health after finalization.",
        "preflight_checks": [
            "Confirm the change belongs to B-owned logic or B-owned outputs.",
            "Check out/systems/B/live/B_cycle.lock and out/B_cycle.lock for an active overlapping B owner.",
            "If B is active, prefer the scoped B maintenance marker out/locks/b_cycle.maintenance over global maintenance.requested.",
            "If active H or F ownership is visible, do not use the global maintenance.requested marker for B-only proof.",
            "Read B health only after the B run finalizes.",
        ],
        "command_sequence": [
            "Set out/locks/b_cycle.maintenance to target_flow=B|action=restart_drain|exit_after_drain=1|request_id=<unique_id>",
            "Wait for B_READY and for the B owner pid/start to change, then clear out/locks/b_cycle.maintenance.",
            "Read the next finalized B manifest from the fresh owner.",
            "$env:B_RUN_ONCE = \"1\"",
            "python scripts/cycles/run_B_cycle.py  # only when no live B owner is active",
            "python scripts/flows/A/A015_build_system_health_check.py --profile b --no-toast",
        ],
        "disallowed_shortcuts": [
            "Do not run overlapping B proof while a live B owner is active.",
            "Do not use global maintenance.requested for B-only proof while H or F ownership is active.",
            "Do not inspect COG or token health in the middle of the B loop.",
            "Do not treat a mid-cycle missing-cost state as a final failure.",
        ],
        "fallback_rule": "If B cannot be paused or handed off safely now, record the exact lock evidence and rerun at the next safe B boundary. Waiting for a vague next cycle is not proof.",
        "current_state": state,
    }


def _e_plan(root: Path) -> dict[str, Any]:
    state = _flow_state("e", root)
    e_cycle = state["e_cycle"]
    if e_cycle["exists"] and e_cycle["pid_running"] is not False:
        status = "boundary_or_pause_required"
        reason = "A live E owner is present or unresolved. Let the current E run finish before forcing proof."
    else:
        status = "ready_now"
        reason = "No active overlapping E owner is visible."
    return {
        "flow": "e",
        "wait_for_next_scheduled_cycle_allowed": False,
        "can_proceed_without_next_cycle": True,
        "proof_mode": "owned_e_cycle",
        "proof_window_status": status,
        "state_reason": reason,
        "safe_boundary": "Run one owned E cycle when no overlapping E owner is active, then use the E-scoped proof from that run.",
        "preflight_checks": [
            "Confirm the change belongs to E-owned logic or E-owned outputs.",
            "Check out/systems/E/live/E_cycle.lock and out/E_cycle.lock for an active overlapping E owner.",
            "Do not overlap a manual E proof run with a scheduler-owned E run.",
        ],
        "command_sequence": [
            "python scripts/cycles/run_E_cycle.py",
        ],
        "disallowed_shortcuts": [
            "Do not read stale pre-change E outputs as confirmation.",
            "Do not overlap the proof run with an active E owner.",
        ],
        "fallback_rule": "If the current E owner cannot yield a safe boundary now, record the exact active lock and retry at the next idle boundary. Do not describe that as generic next-cycle waiting.",
        "current_state": state,
    }


def _h_plan(root: Path) -> dict[str, Any]:
    state = _flow_state("h", root)
    h_cycle = state["h_cycle"]
    controlled = state["h_controlled_mode"]["exists"]
    run_in_progress = state["h_run_in_progress"]["exists"]
    if h_cycle["exists"] and h_cycle["pid_running"] is not False and not controlled:
        status = "pause_required"
        reason = "A live H owner is still present. Pause scheduler ownership before controlled proof."
    elif run_in_progress and not controlled:
        status = "stale_marker_review_required"
        reason = "H run markers exist without controlled mode. Reconcile stale lock and ownership evidence before proof."
    elif controlled:
        status = "ready_now"
        reason = "Controlled mode is active and H is ready for isolated proof."
    else:
        status = "pause_required"
        reason = "H proof should start with the standard pause step so controlled mode owns the run."
    return {
        "flow": "h",
        "wait_for_next_scheduled_cycle_allowed": False,
        "can_proceed_without_next_cycle": True,
        "proof_mode": "controlled_h_isolation",
        "proof_window_status": status,
        "state_reason": reason,
        "safe_boundary": "Pause scheduler ownership, run the guarded H controlled one-shot to terminal markers, run H-scoped health, then resume scheduler ownership and confirm a new owner process or run.",
        "preflight_checks": [
            "Confirm the change belongs to H-owned logic, H-owned outputs, or H-scoped health.",
            "Check out/systems/H/live/H_pricing_cycle.lock and out/H_pricing_cycle.lock for an overlapping H owner.",
            "Check out/systems/H/live/H_run_in_progress.txt and out/locks/h_controlled_mode.active before proof.",
            "Read H health only after the controlled run reaches terminal markers.",
            "After proof, resume scheduler ownership and confirm ownership restoration.",
        ],
        "command_sequence": [
            ".\\run_H_isolation_status.bat",
            ".\\run_H_isolation_pause.bat",
            ".\\run_H_isolation_success.bat",
            "python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast",
            ".\\run_H_isolation_resume.bat",
        ],
        "disallowed_shortcuts": [
            "Do not overlap the controlled proof with a live H owner.",
            "Do not read H health before the controlled run finalizes.",
            "Do not rely on history-wide append rows when the health rule should score the latest run only.",
        ],
        "fallback_rule": "If pause, stale-lock reconcile, or resume ownership cannot complete safely now, record the exact blocker and the exact artifact required to resume proof. Do not fall back to vague next-cycle wording.",
        "current_state": state,
    }


def build_plan(flow: str, root: Path = ROOT) -> dict[str, Any]:
    flow = flow.strip().lower()
    if flow == "a":
        return _a_plan(root)
    if flow == "b":
        return _b_plan(root)
    if flow == "e":
        return _e_plan(root)
    if flow == "h":
        return _h_plan(root)
    raise ValueError(f"Unsupported flow: {flow}")


def _text_plan(plan: dict[str, Any]) -> str:
    lines: list[str] = [
        f"Flow: {plan['flow'].upper()}",
        f"Proof mode: {plan['proof_mode']}",
        f"Proof window status: {plan['proof_window_status']}",
        f"Can proceed without next cycle: {'yes' if plan['can_proceed_without_next_cycle'] else 'no'}",
        f"Wait for next scheduled cycle allowed: {'yes' if plan['wait_for_next_scheduled_cycle_allowed'] else 'no'}",
        f"State reason: {plan['state_reason']}",
        f"Safe boundary: {plan['safe_boundary']}",
        "",
        "Preflight checks:",
    ]
    for item in plan["preflight_checks"]:
        lines.append(f"- {item}")
    lines.extend(["", "Command sequence:"])
    for idx, item in enumerate(plan["command_sequence"], start=1):
        lines.append(f"{idx}. {item}")
    lines.extend(["", "Disallowed shortcuts:"])
    for item in plan["disallowed_shortcuts"]:
        lines.append(f"- {item}")
    lines.extend(["", f"Fallback rule: {plan['fallback_rule']}", "", "Current state:"])
    for key, value in plan["current_state"].items():
        if isinstance(value, dict):
            compact = ", ".join(f"{k}={value[k]}" for k in value)
            lines.append(f"- {key}: {compact}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan a safe forced-proof window for A, B, E, or H runtime validation."
    )
    parser.add_argument(
        "--flow",
        required=True,
        choices=["a", "b", "e", "h"],
        help="Owner flow for the proof window.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan(args.flow, root=ROOT)
    if args.format == "json":
        print(json.dumps(plan, indent=2))
    else:
        print(_text_plan(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
