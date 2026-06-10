from __future__ import annotations

from pathlib import Path
from typing import Any


def build_f_price_list_report(result: dict[str, Any]) -> str:
    snapshot = result["snapshot_rows"][0]
    incidents = result["incident_rows"]
    repair_queue = [
        row
        for row in result.get("codex_repair_queue_rows", [])
        if row.get("status") not in {"cleared_pending_review", "completed", "resolved", "cancelled"}
    ]
    health = result["health_rows"]
    self_rows = result["self_organisation_rows"]
    warn_health = [row for row in health if row.get("status") == "warn"]
    fail_health = [row for row in health if row.get("status") == "fail"]
    self_warns = [row for row in self_rows if row.get("status") == "warn"]

    lines = [
        "# SellerOne Manager - F Price List Scanner",
        "",
        f"Observed UTC: {snapshot.get('observed_utc', '')}",
        "",
        "## Answer For Luke",
        _current_answer(snapshot),
        "",
        "## Needs Luke",
        _needs_luke(snapshot),
        "",
        "## Codex Queue",
        _codex_queue(snapshot, incidents, repair_queue),
        "",
        "## Evidence",
        f"- Queue says: {snapshot.get('queue_supplier_name') or snapshot.get('queue_supplier_id') or 'unknown supplier'} is `{snapshot.get('queue_state') or 'unknown'}` with `{snapshot.get('queue_web_unprocessed') or '0'}` unprocessed web rows.",
        f"- Live owner says: `{snapshot.get('live_state') or 'unknown'}` after `{snapshot.get('live_last_action') or 'unknown action'}`.",
        f"- Earliest blocker: `{snapshot.get('active_blocker_code') or 'none'}`.",
        f"- Stale evidence flag: `{snapshot.get('stale_evidence') or '0'}`.",
        "",
        "## Manager Health",
        f"- Manager execution errors: `{_health_value(health, 'manager_execution', default='unknown')}`.",
        f"- Health warnings: `{len(warn_health)}`.",
        f"- Health failures: `{len(fail_health)}`.",
        f"- Self-organisation warnings: `{len(self_warns)}`.",
        "",
        "## Output Rule",
        "- This report is read-only. It did not run A, B, E, H, F061, Google Sheets writes, local DB alignment, queue edits, or worker restarts.",
        "",
    ]
    return "\n".join(lines)


def write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_f_price_list_report(result), encoding="utf-8")


def _current_answer(snapshot: dict[str, str]) -> str:
    status = snapshot.get("status", "")
    if status == "blocked" and snapshot.get("active_blocker_code") == "storage_drift_preflight":
        supplier = snapshot.get("queue_supplier_name") or snapshot.get("queue_supplier_id") or "the queued supplier"
        return (
            f"The manager is not blaming {supplier}. {supplier} is the next queued supplier, "
            "but the scanner cannot start it because the live F manager is blocked by storage drift."
        )
    if status == "needs_user":
        return snapshot.get("active_blocker_summary", "The queue needs user input.")
    if status == "ok":
        return "No active F manager blocker was detected by the read-only manager."
    if status == "stale_evidence" and snapshot.get("active_blocker_code") == "live_owner_status_stale_after_storage_repair":
        return (
            "The storage drift repair evidence is now clear. The only remaining warning is that the live F owner "
            "has not refreshed its older blocked status yet."
        )
    return snapshot.get("active_blocker_summary", "The manager found an unclassified F state.")


def _needs_luke(snapshot: dict[str, str]) -> str:
    if snapshot.get("needs_user") == "1":
        return f"- User Task: {snapshot.get('user_action')}"
    if snapshot.get("status") == "ok":
        return "- No direct user task right now. No active Codex repair task."
    if snapshot.get("status") == "stale_evidence" and snapshot.get("active_blocker_code") == "live_owner_status_stale_after_storage_repair":
        return "- No direct user task right now. The repair evidence is clear; only the old live-owner status needs a later refresh."
    return "- No direct user task right now. Codex owns the technical follow-up."


def _codex_queue(
    snapshot: dict[str, str],
    incidents: list[dict[str, str]],
    repair_queue: list[dict[str, str]],
) -> str:
    if repair_queue:
        return "\n".join(
            f"- `{row.get('status')}` `{row.get('task_id')}`: {row.get('task_summary')}"
            for row in repair_queue
        )
    if incidents:
        return "\n".join(f"- Awaiting user decision: {row.get('summary')}" for row in incidents)
    if snapshot.get("status") == "ok":
        return "- No Codex task needed from this snapshot."
    if snapshot.get("status") == "stale_evidence" and snapshot.get("active_blocker_code") == "live_owner_status_stale_after_storage_repair":
        return "- No active Codex repair task from this snapshot. The storage drift task is cleared pending review."
    return "- Classify the live owner state first, then fix the earliest broken artifact."


def _health_value(health: list[dict[str, str]], check: str, default: str) -> str:
    for row in health:
        if row.get("check") == check:
            return row.get("value", default)
    return default
