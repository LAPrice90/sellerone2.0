from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

try:
    from scripts.tools.home_time_common import (
        ACTIVE_PATH,
        LOG_PATH,
        HomeTimeError,
        active_home_time_payload,
        append_jsonl,
        collect_home_time_snapshot,
        norm,
        utc_now,
        write_home_time_report,
    )
except ModuleNotFoundError:
    from home_time_common import (
        ACTIVE_PATH,
        LOG_PATH,
        HomeTimeError,
        active_home_time_payload,
        append_jsonl,
        collect_home_time_snapshot,
        norm,
        utc_now,
        write_home_time_report,
    )


def stop_home_time_mode(*, root: Path, operator: str, completion_reason: str) -> dict[str, object]:
    active_path = root / "out" / "systems" / "H" / "live" / "H_home_time_mode.active.json"
    log_path = root / "out" / "systems" / "H" / "live" / "H_home_time_mode.log"

    activation_payload = active_home_time_payload(root)
    if not activation_payload:
        raise HomeTimeError(f"home_time_mode_not_active path={active_path}")

    final_snapshot = collect_home_time_snapshot(root)
    anomalies = list(final_snapshot.get("anomalies", []))
    stop_utc = utc_now()
    report_payload: dict[str, object] = {
        "report_type": "home_time_mode_completion_report",
        "report_utc": stop_utc,
        "completion_reason": completion_reason,
        "operator": operator,
        "original_activation_session": {
            "session_id": norm(activation_payload.get("session_id", "")),
            "start_utc": norm(activation_payload.get("start_utc", "")),
            "issue_label": norm(activation_payload.get("issue_label", "")),
            "operator": norm(activation_payload.get("operator", "")),
        },
        "system_state_at_shutdown": final_snapshot,
        "H_run_ownership_state": {
            "H_run_in_progress": final_snapshot.get("H_run_in_progress", ""),
            "H_last_finalized_run": final_snapshot.get("H_last_finalized_run", ""),
            "H_launcher_owner_pid": final_snapshot.get("H_launcher_owner_pid", ""),
        },
        "boundary_state_summary": final_snapshot.get("boundary_state_summary", {}),
        "archive_state_summary": final_snapshot.get("archive_state_summary", {}),
        "maintenance_state_summary": final_snapshot.get("maintenance_state_summary", {}),
        "runtime_snapshot": final_snapshot.get("runtime_status_snapshot", {}),
        "anomalies_detected": anomalies,
        "activation_artifact_path": str(active_path),
    }
    report_path = write_home_time_report(root, report_payload, timestamp_utc=stop_utc)

    active_path.unlink(missing_ok=True)
    removed = not active_path.exists()
    append_jsonl(
        log_path,
        {
            "event": "home_time_mode_stopped",
            "stop_time_utc": stop_utc,
            "session_id": norm(activation_payload.get("session_id", "")),
            "issue_label": norm(activation_payload.get("issue_label", "")),
            "operator": operator,
            "completion_reason": completion_reason,
            "report_path": str(report_path),
            "active_marker_removed": removed,
            "anomalies_detected": anomalies,
        },
    )
    return {
        "status": "ok",
        "report_path": str(report_path),
        "active_marker_removed": removed,
        "session_id": norm(activation_payload.get("session_id", "")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stop home time mode without mutating H runtime ownership.")
    parser.add_argument("--operator", default="unknown")
    parser.add_argument("--completion-reason", default="operator_stop")
    args = parser.parse_args()

    result = stop_home_time_mode(
        root=ROOT,
        operator=norm(args.operator) or "unknown",
        completion_reason=norm(args.completion_reason) or "operator_stop",
    )
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
