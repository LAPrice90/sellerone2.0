from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .autonomy_policy import controlled_technical_pause_allowed, is_controlled_technical_pause_text
from .paths import get_manager_paths


CURRENT_STATE_REL_PATH = Path("sellerone_manager") / "current_state.json"

DO_NOT_TOUCH = [
    "worker scripts",
    "worker cycles outside manager-approved proof windows",
    "safe dispatching beyond approved task packets",
    "F061 queue state",
    "legacy Sheet writes unless explicitly approved",
    "local database alignment",
    "pricing changes",
    "output deletion",
    "scheduler ownership changes outside controlled technical pause/resume proof packets",
    "worker expansion beyond approved manager tasks",
]

ACTIVE_REPAIR_STATUSES = {"queued", "in_progress", "blocked_needs_user_decision", "reopened"}
TASK_CANDIDATE_STATUSES = {"proposed", "in_progress", "blocked_needs_user_decision", "reopened"}
MOT_ACTIVE_WORK_STATUSES = {"new", "assigned", "in_progress", "fixed_needs_retest", "retest_failed", "blocked_needs_luke"}
APPROVED_TASK_ACTIVE_STATUSES = {"approved", "in_progress", "fixed_needs_retest", "retest_failed", "reopened"}
APPROVED_TASK_BLOCKED_STATUSES = {"blocked_needs_luke"}
APPROVED_TASK_TERMINAL_STATUSES = {"proved", "parked"}


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def build_current_state(*, root: Path | str | None = None, generated_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    output_dir = paths.output_dir
    snapshot_path = output_dir / "f_price_list_manager_snapshot.csv"
    health_path = output_dir / "manager_health.csv"
    incidents_path = output_dir / "manager_incidents.csv"
    repair_queue_path = output_dir / "codex_repair_queue.csv"
    priority_path = output_dir / "self_organisation" / "latest_f_manifest_priority_ranking.csv"
    manager_report_path = output_dir / "latest_f_price_list_manager_report.md"
    flow_state_path = output_dir / "flow_maintenance_state.csv"
    task_candidate_path = output_dir / "manager_task_candidates.csv"
    approved_task_path = output_dir / "approved_task_packets.csv"
    expectation_path = output_dir / "flow_expectation_reconciliation.csv"
    control_report_path = output_dir / "latest_manager_control_report.md"
    mot_dir = output_dir / "mot"
    mot_latest_path = mot_dir / "mot_latest.csv"
    mot_worklist_path = mot_dir / "mot_worklist.csv"
    mot_retest_path = mot_dir / "mot_retest_queue.csv"
    mot_report_path = mot_dir / "mot_latest.md"

    snapshot_rows = read_csv_rows(snapshot_path)
    health_rows = read_csv_rows(health_path)
    incident_rows = read_csv_rows(incidents_path)
    repair_rows = read_csv_rows(repair_queue_path)
    priority_rows = read_csv_rows(priority_path)
    flow_rows = read_csv_rows(flow_state_path)
    task_candidate_rows = read_csv_rows(task_candidate_path)
    approved_task_rows = read_csv_rows(approved_task_path)
    mot_rows = read_csv_rows(mot_latest_path)
    mot_worklist_rows = read_csv_rows(mot_worklist_path)

    snapshot = snapshot_rows[0] if snapshot_rows else {}
    terminal_approved_manager_sources = _terminal_approved_manager_sources(approved_task_rows)
    active_repair_rows = [row for row in repair_rows if row.get("status") in ACTIVE_REPAIR_STATUSES]
    active_task_candidates = [
        row
        for row in task_candidate_rows
        if row.get("status") in TASK_CANDIDATE_STATUSES and not _candidate_is_already_terminal(row, terminal_approved_manager_sources)
    ]
    active_approved_tasks = [row for row in approved_task_rows if row.get("status") in APPROVED_TASK_ACTIVE_STATUSES and row.get("luke_action_required") != "1"]
    blocked_approved_tasks = [
        row
        for row in approved_task_rows
        if (row.get("status") in APPROVED_TASK_BLOCKED_STATUSES or row.get("luke_action_required") == "1")
        and _blocked_approved_task_should_block_state(row, mot_rows, root=paths.root)
    ]
    active_mot_worklist = [row for row in mot_worklist_rows if row.get("status") in MOT_ACTIVE_WORK_STATUSES]
    active_incidents = [row for row in incident_rows if row.get("severity") or row.get("incident_code")]
    top_priority_rows = [
        row
        for row in priority_rows
        if row.get("recommended_action") == "candidate_manifest" and row.get("priority_band") == "top_3"
    ][:3]

    manager_execution_errors = _manager_execution_errors(health_rows)
    if flow_rows:
        system_status = _status_with_mot(
            _multi_flow_system_status(flow_rows, manager_execution_errors),
            active_mot_worklist,
            manager_execution_errors,
        )
        if blocked_approved_tasks:
            system_status = "BLOCKED" if not manager_execution_errors else system_status
            luke_required, luke_action = _luke_action_with_approved(blocked_approved_tasks)
            if active_approved_tasks:
                codex_available, codex_task = _codex_task_with_approved(active_approved_tasks)
                current_summary = "Manager has a protected admin or user gate parked, but Codex has separate approved work it can continue safely."
                next_safe_batch = _next_safe_batch_with_approved(active_approved_tasks)
            else:
                codex_available, codex_task = False, "No Codex task can start until Luke decides the blocked manager task."
                current_summary = "Manager has a blocked approved task packet that needs Luke before repair can continue."
                next_safe_batch = "needs user decision on the blocked manager-approved task packet"
        elif active_approved_tasks:
            system_status = _status_with_approved(system_status, active_approved_tasks, manager_execution_errors)
            luke_required, luke_action = False, "No Luke decision needed. Codex has a manager-approved task packet."
            codex_available, codex_task = _codex_task_with_approved(active_approved_tasks)
            current_summary = _current_summary_with_approved(active_approved_tasks)
            next_safe_batch = _next_safe_batch_with_approved(active_approved_tasks)
        else:
            luke_required, luke_action = _luke_action_with_mot(active_mot_worklist)
            if not luke_required:
                luke_required, luke_action = _multi_flow_luke_action(flow_rows, active_task_candidates)
            codex_available, codex_task = _codex_task_with_mot(active_mot_worklist)
            if not codex_available:
                codex_available, codex_task = _multi_flow_codex_task(active_repair_rows, active_task_candidates, top_priority_rows)
            current_summary = _current_summary_with_mot(active_mot_worklist, luke_required)
            if not current_summary:
                current_summary = _multi_flow_current_summary(flow_rows, luke_required, active_task_candidates)
            next_safe_batch = _next_safe_batch_with_mot(active_mot_worklist)
            if not next_safe_batch:
                next_safe_batch = _multi_flow_next_safe_batch(active_repair_rows, active_task_candidates, top_priority_rows)
        active_flow = "A -> B -> E -> H -> F -> O"
    else:
        system_status = _status_with_mot(_system_status(snapshot, active_incidents, manager_execution_errors), active_mot_worklist, manager_execution_errors)
        if blocked_approved_tasks:
            system_status = "BLOCKED" if not manager_execution_errors else system_status
            luke_required, luke_action = _luke_action_with_approved(blocked_approved_tasks)
            if active_approved_tasks:
                codex_available, codex_task = _codex_task_with_approved(active_approved_tasks)
                current_summary = "Manager has a protected admin or user gate parked, but Codex has separate approved work it can continue safely."
                next_safe_batch = _next_safe_batch_with_approved(active_approved_tasks)
            else:
                codex_available, codex_task = False, "No Codex task can start until Luke decides the blocked manager task."
                current_summary = "Manager has a blocked approved task packet that needs Luke before repair can continue."
                next_safe_batch = "needs user decision on the blocked manager-approved task packet"
        elif active_approved_tasks:
            system_status = _status_with_approved(system_status, active_approved_tasks, manager_execution_errors)
            luke_required, luke_action = False, "No Luke decision needed. Codex has a manager-approved task packet."
            codex_available, codex_task = _codex_task_with_approved(active_approved_tasks)
            current_summary = _current_summary_with_approved(active_approved_tasks)
            next_safe_batch = _next_safe_batch_with_approved(active_approved_tasks)
        else:
            luke_required, luke_action = _luke_action_with_mot(active_mot_worklist)
            if not luke_required:
                luke_required, luke_action = _luke_action(snapshot, active_incidents)
            codex_available, codex_task = _codex_task_with_mot(active_mot_worklist)
            if not codex_available:
                codex_available, codex_task = _codex_task(active_repair_rows, top_priority_rows)
            current_summary = _current_summary_with_mot(active_mot_worklist, luke_required)
            if not current_summary:
                current_summary = _current_summary(snapshot, system_status, luke_required, active_repair_rows)
            next_safe_batch = _next_safe_batch_with_mot(active_mot_worklist)
            if not next_safe_batch:
                next_safe_batch = _next_safe_batch(active_repair_rows, top_priority_rows)
        active_flow = "F Price List Manager"

    return {
        "generated_utc": generated_utc or utc_now_text(),
        "source_observed_utc": _latest_observed(flow_rows) or snapshot.get("observed_utc", ""),
        "system_status": system_status,
        "active_flow": active_flow,
        "current_state": current_summary,
        "luke_action_required": luke_required,
        "luke_action": luke_action,
        "codex_task_available": codex_available,
        "codex_task_title": codex_task,
        "next_safe_batch": next_safe_batch,
        "do_not_touch": DO_NOT_TOUCH,
        "manager_execution_errors": manager_execution_errors,
        "flow_states": flow_rows,
        "latest_evidence": {
            "manager_report": str(control_report_path if flow_rows else manager_report_path),
            "incidents": str(incidents_path),
            "health": str(health_path),
            "snapshot": str(snapshot_path),
            "priority_ranking": str(priority_path),
            "flow_maintenance": str(flow_state_path),
            "expectation_reconciliation": str(expectation_path),
            "manager_task_candidates": str(task_candidate_path),
            "approved_task_packets": str(approved_task_path),
            "mot_report": str(mot_report_path),
            "mot_latest": str(mot_latest_path),
            "mot_worklist": str(mot_worklist_path),
            "mot_retest_queue": str(mot_retest_path),
        },
    }


def write_current_state(state: dict[str, Any], *, root: Path | str | None = None) -> Path:
    path = current_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_and_write_current_state(*, root: Path | str | None = None, generated_utc: str | None = None) -> tuple[dict[str, Any], Path]:
    state = build_current_state(root=root, generated_utc=generated_utc)
    path = current_state_path(root)
    state["current_state_path"] = str(path)
    write_current_state(state, root=root)
    return state, path


def current_state_path(root: Path | str | None = None) -> Path:
    base = Path(root).resolve() if root is not None else get_manager_paths(None).root
    return base / CURRENT_STATE_REL_PATH


def format_what_next(state: dict[str, Any]) -> str:
    luke_required = "yes" if state.get("luke_action_required") else "no"
    codex_available = "yes" if state.get("codex_task_available") else "no"
    evidence = state.get("latest_evidence", {})
    do_not_touch = state.get("do_not_touch", [])
    lines = [
        "========================================",
        "SELLERONE MANAGER",
        "========================================",
        "",
        "SYSTEM STATUS:",
        str(state.get("system_status", "WARN")),
        "",
        "ACTIVE FLOW:",
        str(state.get("active_flow", "F Price List Manager")),
        "",
        "CURRENT STATE:",
        str(state.get("current_state", "Manager state is not available.")),
        "",
        "LUKE ACTION REQUIRED:",
        luke_required,
    ]
    if state.get("luke_action_required"):
        lines.append(str(state.get("luke_action", "")))
    lines.extend(
        [
            "",
            "CODEX TASK AVAILABLE:",
            codex_available,
        ]
    )
    if state.get("codex_task_available"):
        lines.append(str(state.get("codex_task_title", "")))
    flow_states = state.get("flow_states") or []
    if flow_states:
        lines.extend(["", "FLOW MAINTENANCE:"])
        for row in flow_states:
            counts = f"FAIL {row.get('active_fail_count', '0')}, WARN {row.get('active_warn_count', '0')}"
            lines.append(f"- {row.get('flow')}: {row.get('status')} / {row.get('classification')} ({counts})")
    lines.extend(
        [
            "",
            "NEXT SAFE BATCH:",
            str(state.get("next_safe_batch", "No safe batch available from current manager outputs.")),
            "",
            "DO NOT TOUCH:",
        ]
    )
    lines.extend(f"- {item}" for item in do_not_touch)
    lines.extend(
        [
            "",
            "LATEST EVIDENCE:",
            f"- manager report: {evidence.get('manager_report', '')}",
            f"- incidents: {evidence.get('incidents', '')}",
            f"- health: {evidence.get('health', '')}",
            f"- flow maintenance: {evidence.get('flow_maintenance', '')}",
            f"- approved tasks: {evidence.get('approved_task_packets', '')}",
            f"- MOT worklist: {evidence.get('mot_worklist', '')}",
            "",
            "========================================",
        ]
    )
    return "\n".join(lines)


def _manager_execution_errors(health_rows: list[dict[str, str]]) -> int:
    for row in health_rows:
        if row.get("check") != "manager_execution":
            continue
        try:
            return int(float(row.get("value", "0") or "0"))
        except ValueError:
            return 1
    return 1


def _terminal_approved_manager_sources(rows: list[dict[str, str]]) -> dict[str, str]:
    terminal: dict[str, str] = {}
    for row in rows:
        if row.get("source_type") != "manager_candidate":
            continue
        if row.get("status") not in APPROVED_TASK_TERMINAL_STATUSES:
            continue
        source_id = row.get("source_id", "")
        if source_id:
            terminal[source_id] = max(terminal.get(source_id, ""), row.get("observed_utc", ""))
    return terminal


def _candidate_is_already_terminal(row: dict[str, str], terminal_sources: dict[str, str]) -> bool:
    terminal_observed = terminal_sources.get(row.get("task_id", ""))
    if not terminal_observed:
        return False
    candidate_observed = row.get("observed_utc", "")
    return not candidate_observed or terminal_observed >= candidate_observed


def _system_status(snapshot: dict[str, str], incidents: list[dict[str, str]], manager_execution_errors: int) -> str:
    if manager_execution_errors:
        return "BLOCKED"
    status = (snapshot.get("status") or "").lower()
    if status in {"blocked", "fail", "needs_user"}:
        return "BLOCKED"
    if incidents:
        return "BLOCKED"
    if status in {"warn", "stale_evidence", "not_checked"} or not snapshot:
        return "WARN"
    return "OK"


def _luke_action(snapshot: dict[str, str], incidents: list[dict[str, str]]) -> tuple[bool, str]:
    if snapshot.get("needs_user") == "1":
        return True, snapshot.get("user_action") or "Manager says Luke input is needed."
    for row in incidents:
        if row.get("needs_user") == "1":
            return True, row.get("remediation_hint") or row.get("summary") or "Manager says Luke input is needed."
    return False, "No Luke decision needed from this manager snapshot."


def _codex_task(active_repair_rows: list[dict[str, str]], top_priority_rows: list[dict[str, str]]) -> tuple[bool, str]:
    if active_repair_rows:
        row = active_repair_rows[0]
        task_id = row.get("task_id", "")
        summary = row.get("task_summary", "")
        return True, f"{task_id}: {summary}".strip(": ")
    if top_priority_rows:
        script_names = [_script_stem(row.get("script_path", "")) for row in top_priority_rows]
        return True, "Create manager manifests for: " + ", ".join(script_names)
    return False, "No Codex task needed from this snapshot."


def _next_safe_batch(active_repair_rows: list[dict[str, str]], top_priority_rows: list[dict[str, str]]) -> str:
    if active_repair_rows:
        return "Continue the active Codex-owned manager task only. Keep it read-only until a separate repair batch is approved."
    if top_priority_rows:
        script_names = [_script_stem(row.get("script_path", "")) for row in top_priority_rows]
        return "Create manager manifests for the next ranked F scripts only: " + ", ".join(script_names) + "."
    return "No safe batch available from current manager outputs."


def _current_summary(
    snapshot: dict[str, str],
    system_status: str,
    luke_required: bool,
    active_repair_rows: list[dict[str, str]],
) -> str:
    if not snapshot:
        return "Manager outputs are missing or not ready. Run the read-only manager report before using the front door."
    summary = snapshot.get("active_blocker_summary") or "No manager summary was available."
    if system_status == "OK" and not luke_required and not active_repair_rows:
        return "No Luke decision needed from this manager snapshot. " + summary
    return summary


def _script_stem(script_path: str) -> str:
    return Path(script_path).stem if script_path else "unknown_script"


def _latest_observed(rows: list[dict[str, str]]) -> str:
    values = [row.get("observed_utc", "") for row in rows if row.get("observed_utc")]
    return max(values) if values else ""


def _rollout_sorted(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    def key(row: dict[str, str]) -> tuple[int, str]:
        try:
            rank = int(row.get("rollout_rank", "99") or "99")
        except ValueError:
            rank = 99
        return rank, row.get("flow", "")

    return sorted(rows, key=key)


def _multi_flow_system_status(flow_rows: list[dict[str, str]], manager_execution_errors: int) -> str:
    if manager_execution_errors:
        return "BLOCKED"
    statuses = {row.get("status", "").lower() for row in flow_rows}
    if "blocked" in statuses or "fail" in statuses:
        return "BLOCKED"
    if statuses & {"warn", "stale_evidence", "not_checked"}:
        return "WARN"
    return "OK"


def _multi_flow_luke_action(
    flow_rows: list[dict[str, str]],
    task_rows: list[dict[str, str]],
) -> tuple[bool, str]:
    codex_can_continue = any(
        row.get("needs_luke_decision") != "1" and row.get("status") in TASK_CANDIDATE_STATUSES
        for row in task_rows
    )
    if codex_can_continue:
        return False, "No Luke decision needed from this manager snapshot."
    for row in task_rows:
        if row.get("needs_luke_decision") == "1":
            return True, row.get("title") or f"{row.get('flow')} needs a user decision."
    for row in _rollout_sorted(flow_rows):
        if row.get("needs_luke_decision") == "1":
            return True, row.get("luke_decision") or f"{row.get('flow')} needs a user decision."
    return False, "No Luke decision needed from this manager snapshot."


def _multi_flow_codex_task(
    active_repair_rows: list[dict[str, str]],
    task_rows: list[dict[str, str]],
    top_priority_rows: list[dict[str, str]],
) -> tuple[bool, str]:
    if active_repair_rows:
        return _codex_task(active_repair_rows, top_priority_rows)
    for row in task_rows:
        if row.get("needs_luke_decision") == "1":
            continue
        if row.get("status") in TASK_CANDIDATE_STATUSES:
            return True, row.get("title", "")
    return _codex_task([], top_priority_rows)


def _multi_flow_current_summary(
    flow_rows: list[dict[str, str]],
    luke_required: bool,
    task_rows: list[dict[str, str]],
) -> str:
    blocked = [row for row in flow_rows if row.get("status") == "blocked"]
    warned = [row for row in flow_rows if row.get("status") in {"warn", "not_checked"}]
    if luke_required:
        return "Luke decision needed before the manager can continue safely."
    if blocked:
        flows = ", ".join(row.get("flow", "") for row in _rollout_sorted(blocked))
        return f"No Luke decision needed. Manager found repair blockers in: {flows}."
    if task_rows:
        next_task = next((row for row in task_rows if row.get("needs_luke_decision") != "1"), {})
        if next_task:
            return f"No Luke decision needed. Next manager task is {next_task.get('flow')}: {next_task.get('title')}."
    if warned:
        flows = ", ".join(row.get("flow", "") for row in _rollout_sorted(warned))
        return f"No Luke decision needed. Manager found warning or missing-proof work in: {flows}."
    return "No Luke decision needed. Manager maintenance state is calm for all covered flows."


def _multi_flow_next_safe_batch(
    active_repair_rows: list[dict[str, str]],
    task_rows: list[dict[str, str]],
    top_priority_rows: list[dict[str, str]],
) -> str:
    if active_repair_rows:
        return "Continue the active Codex-owned manager task only. Keep it scoped to the approved repair boundary."
    for row in task_rows:
        if row.get("needs_luke_decision") == "1":
            continue
        if row.get("status") in TASK_CANDIDATE_STATUSES:
            return f"{row.get('flow')}: {row.get('title')}."
    return _next_safe_batch([], top_priority_rows)


def _mot_non_luke_work(active_mot_worklist: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in active_mot_worklist
        if row.get("luke_action_required") != "1" and row.get("status") != "blocked_needs_luke"
    ]


def _status_with_mot(base_status: str, active_mot_worklist: list[dict[str, str]], manager_execution_errors: int) -> str:
    if manager_execution_errors:
        return "BLOCKED"
    if active_mot_worklist:
        return "BLOCKED"
    return base_status


def _luke_action_with_mot(active_mot_worklist: list[dict[str, str]]) -> tuple[bool, str]:
    if _mot_non_luke_work(active_mot_worklist):
        return False, "No Luke decision needed from this manager snapshot."
    for row in active_mot_worklist:
        if row.get("luke_action_required") == "1" or row.get("status") == "blocked_needs_luke":
            return True, row.get("manager_action") or row.get("title") or "MOT worklist needs a Luke decision."
    return False, "No Luke decision needed from this manager snapshot."


def _codex_task_with_mot(active_mot_worklist: list[dict[str, str]]) -> tuple[bool, str]:
    actionable = _mot_non_luke_work(active_mot_worklist)
    if not actionable:
        return False, ""
    row = actionable[0]
    return True, f"{_job_label(row, id_key='work_item_id')}: {row.get('title')}".strip(": ")


def _current_summary_with_mot(active_mot_worklist: list[dict[str, str]], luke_required: bool) -> str:
    if not active_mot_worklist:
        return ""
    if luke_required:
        return "MOT found a blocked item that needs Luke before repair can continue."
    actionable = _mot_non_luke_work(active_mot_worklist)
    if actionable:
        first = actionable[0]
        return f"No Luke decision needed. MOT created Codex work: {_job_label(first, id_key='work_item_id')} - {first.get('title')}."
    return ""


def _next_safe_batch_with_mot(active_mot_worklist: list[dict[str, str]]) -> str:
    actionable = _mot_non_luke_work(active_mot_worklist)
    if not actionable:
        return ""
    first = actionable[0]
    return f"MOT: {_job_label(first, id_key='work_item_id')} - {first.get('title')}. Keep within: {first.get('safe_repair_boundary')}."


def _status_with_approved(base_status: str, active_tasks: list[dict[str, str]], manager_execution_errors: int) -> str:
    if manager_execution_errors:
        return "BLOCKED"
    if active_tasks:
        return "WARN" if base_status == "OK" else base_status
    return base_status


def _codex_task_with_approved(active_tasks: list[dict[str, str]]) -> tuple[bool, str]:
    if not active_tasks:
        return False, ""
    row = active_tasks[0]
    return True, f"{_job_label(row)}: {row.get('title')}".strip(": ")


def _current_summary_with_approved(active_tasks: list[dict[str, str]]) -> str:
    if not active_tasks:
        return ""
    row = active_tasks[0]
    return f"No Luke decision needed. Codex owns {_job_label(row)} from the approved task packet."


def _next_safe_batch_with_approved(active_tasks: list[dict[str, str]]) -> str:
    if not active_tasks:
        return ""
    row = active_tasks[0]
    return f"Claim or continue approved manager task {_job_label(row)}: {row.get('title')}. Keep within: {row.get('allowed_scope')}."


def _luke_action_with_approved(blocked_tasks: list[dict[str, str]]) -> tuple[bool, str]:
    if not blocked_tasks:
        return False, "No Luke decision needed from this manager snapshot."
    row = sorted(blocked_tasks, key=_blocked_approved_priority_key)[0]
    label = _job_label(row)
    message = row.get("notes") or row.get("title") or "A manager-approved task packet is blocked and needs Luke."
    return True, f"{label} - {message}" if label not in message else message


def _blocked_approved_task_should_block_state(
    row: dict[str, str],
    mot_rows: list[dict[str, str]],
    *,
    root: Path,
) -> bool:
    if _blocked_approved_task_resolved_by_mot(row, mot_rows):
        return False
    if _is_f_parked_decision_task(row):
        return False
    if controlled_technical_pause_allowed(root) and _is_controlled_technical_pause_task(row):
        return False
    if _is_parked_business_decision_task(row):
        return False
    return True


def _blocked_approved_task_resolved_by_mot(row: dict[str, str], mot_rows: list[dict[str, str]]) -> bool:
    if not _is_f_parked_decision_task(row):
        return False
    proof_rows = [
        mot_row
        for mot_row in mot_rows
        if mot_row.get("flow") == "F" and mot_row.get("check") == "f_parked_decision_rows"
    ]
    if not proof_rows:
        return False
    proof = sorted(proof_rows, key=lambda proof_row: proof_row.get("observed_utc", ""))[-1]
    return (
        proof.get("status") == "ok"
        and proof.get("value") == "0"
        and proof.get("luke_action_required") != "1"
    )


def _is_f_parked_decision_task(row: dict[str, str]) -> bool:
    if row.get("flow") != "F" or row.get("task_type") != "blocked_decision":
        return False
    text = " ".join(
        [
            row.get("task_id", ""),
            row.get("source_id", ""),
            row.get("title", ""),
            row.get("notes", ""),
        ]
    ).lower()
    return "entertainment trading" in text or "dashboard_yes_no_unresolved" in text


def _is_controlled_technical_pause_task(row: dict[str, str]) -> bool:
    text = " ".join(
        [
            row.get("task_id", ""),
            row.get("source_id", ""),
            row.get("title", ""),
            row.get("notes", ""),
            row.get("allowed_scope", ""),
            row.get("proof_required", ""),
            row.get("stop_condition", ""),
        ]
    )
    return is_controlled_technical_pause_text(text)


def _is_parked_business_decision_task(row: dict[str, str]) -> bool:
    text = " ".join(
        [
            row.get("task_id", ""),
            row.get("source_id", ""),
            row.get("title", ""),
            row.get("notes", ""),
            row.get("allowed_scope", ""),
            row.get("proof_required", ""),
        ]
    ).lower()
    if any(word in text for word in ("credential", "authorize", "authorise", "admin inbox", "missing supplier file")):
        return False
    parked_markers = (
        "manual-review exception",
        "do not publish",
        "order promotion",
        "promotion approval",
        "live promotion",
        "feed bridge data into roi",
        "protected b decision",
        "protected merge",
        "ui can replace sheet",
        "operator decision",
        "business decision",
    )
    return any(marker in text for marker in parked_markers)


def _blocked_approved_priority_key(row: dict[str, str]) -> tuple[int, str, str]:
    source_rank = 0 if row.get("source_type") == "repair_package" else 1
    return (source_rank, row.get("flow", ""), row.get("job_ref") or row.get("task_id", ""))


def _job_label(row: dict[str, str], *, id_key: str = "task_id") -> str:
    return row.get("job_ref") or row.get(id_key) or row.get("task_id") or "unreferenced-job"
