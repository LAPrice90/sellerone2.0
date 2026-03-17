from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    from scripts.tools.home_time_common import (
        ACTIVE_PATH,
        LOG_PATH,
        HomeTimeError,
        append_jsonl,
        atomic_write_text,
        collect_home_time_snapshot,
        norm,
        session_id,
        utc_now,
    )
except ModuleNotFoundError:
    from home_time_common import (
        ACTIVE_PATH,
        LOG_PATH,
        HomeTimeError,
        append_jsonl,
        atomic_write_text,
        collect_home_time_snapshot,
        norm,
        session_id,
        utc_now,
    )


def _operator_default() -> str:
    for name in ("CODEX_OPERATOR", "USERNAME", "USER"):
        value = norm(os.environ.get(name, ""))
        if value:
            return value
    return "unknown"


def activate_home_time_mode(*, root: Path, issue_label: str, operator: str) -> dict[str, object]:
    active_path = root / "out" / "systems" / "H" / "live" / "H_home_time_mode.active.json"
    log_path = root / "out" / "systems" / "H" / "live" / "H_home_time_mode.log"
    if active_path.exists():
        raise HomeTimeError(f"home_time_mode_already_active path={active_path}")

    snapshot = collect_home_time_snapshot(root)
    anomalies = list(snapshot.get("anomalies", []))
    if anomalies:
        raise HomeTimeError("activation_blocked " + ",".join(anomalies))

    start_utc = utc_now()
    session_token = session_id("home_time_session", start_utc)
    payload: dict[str, object] = {
        "session_id": session_token,
        "start_utc": start_utc,
        "issue_label": issue_label,
        "operator": operator,
        "H_run_in_progress": snapshot["H_run_in_progress"],
        "H_last_finalized_run": snapshot["H_last_finalized_run"],
        "H_launcher_owner_pid": snapshot["H_launcher_owner_pid"],
        "boundary_state_summary": snapshot["boundary_state_summary"],
        "archive_state_summary": snapshot["archive_state_summary"],
        "maintenance_state_summary": snapshot["maintenance_state_summary"],
        "runtime_status_snapshot": snapshot["runtime_status_snapshot"],
        "activation_artifact_path": str(active_path),
        "log_path": str(log_path),
    }

    atomic_write_text(active_path, json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    append_jsonl(
        log_path,
        {
            "event": "home_time_mode_activated",
            "activation_time_utc": start_utc,
            "session_id": session_token,
            "issue_label": issue_label,
            "operator": operator,
            "H_run_in_progress": snapshot["H_run_in_progress"],
            "H_last_finalized_run": snapshot["H_last_finalized_run"],
            "H_launcher_owner_pid": snapshot["H_launcher_owner_pid"],
            "boundary_state_summary": snapshot["boundary_state_summary"],
            "archive_state_summary": snapshot["archive_state_summary"],
            "maintenance_state_summary": snapshot["maintenance_state_summary"],
        },
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Activate home time mode without mutating H runtime ownership.")
    parser.add_argument("--issue-label", required=True)
    parser.add_argument("--operator", default=_operator_default())
    args = parser.parse_args()

    issue_label = norm(args.issue_label)
    operator = norm(args.operator) or _operator_default()
    if not issue_label:
        raise SystemExit("issue_label_required")

    payload = activate_home_time_mode(root=ROOT, issue_label=issue_label, operator=operator)
    print(
        json.dumps(
            {
                "status": "ok",
                "session_id": payload["session_id"],
                "activation_artifact_path": payload["activation_artifact_path"],
                "log_path": payload["log_path"],
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
