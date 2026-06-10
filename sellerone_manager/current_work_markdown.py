from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import get_manager_paths


CURRENT_TICKETS_REL_PATH = Path("sellerone_manager") / "CONTROL" / "CURRENT_TICKETS.md"
BACKLOG_REL_PATH = Path("sellerone_manager") / "CONTROL" / "BACKLOG.md"

ACTIVE_STATUSES = {"approved", "in_progress", "fixed_needs_retest", "retest_failed", "reopened"}
BLOCKED_STATUSES = {"blocked_needs_luke"}
PARKED_STATUSES = {"parked"}
TERMINAL_STATUSES = {"proved"}

STATUS_LABELS = {
    "approved": "Ready for Builder",
    "in_progress": "Builder working",
    "fixed_needs_retest": "Waiting proof",
    "retest_failed": "Proof failed",
    "reopened": "Reopened",
    "blocked_needs_luke": "Luke decision needed",
    "parked": "Parked",
    "proved": "Proved history",
}
STATUS_SORT = {
    "fixed_needs_retest": 0,
    "retest_failed": 1,
    "in_progress": 2,
    "reopened": 3,
    "approved": 4,
    "blocked_needs_luke": 5,
    "parked": 6,
    "proved": 7,
}
PRIORITY_SORT = {"critical": 0, "high": 1, "normal": 2, "medium": 2, "low": 3}


@dataclass(frozen=True)
class CurrentWorkMarkdownResult:
    current_tickets_path: Path
    backlog_path: Path
    current_tickets_markdown: str
    backlog_markdown: str
    generated_utc: str
    active_count: int
    blocked_count: int
    parked_count: int
    mot_candidate_count: int
    control_backlog_count: int


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_current_work_markdown(
    *,
    root: Path | str | None = None,
    generated_utc: str | None = None,
) -> CurrentWorkMarkdownResult:
    paths = get_manager_paths(root)
    generated = generated_utc or utc_now_text()
    control_dir = paths.root / "sellerone_manager" / "CONTROL"
    current_tickets_path = paths.root / CURRENT_TICKETS_REL_PATH
    backlog_path = paths.root / BACKLOG_REL_PATH

    packet_rows = _read_csv_rows(paths.output_dir / "approved_task_packets.csv")
    mot_rows = _read_csv_rows(paths.output_dir / "mot" / "mot_worklist.csv")
    status_counts = Counter(row.get("status", "").strip() or "missing" for row in packet_rows)

    active_rows = sorted(
        [
            row
            for row in packet_rows
            if row.get("status") in ACTIVE_STATUSES and _text(row.get("luke_action_required")) != "1"
        ],
        key=_work_sort_key,
    )
    blocked_rows = sorted(
        [
            row
            for row in packet_rows
            if row.get("status") in BLOCKED_STATUSES or _text(row.get("luke_action_required")) == "1"
        ],
        key=_work_sort_key,
    )
    parked_rows = sorted(
        [
            row
            for row in packet_rows
            if row.get("status") in PARKED_STATUSES and _text(row.get("luke_action_required")) != "1"
        ],
        key=_work_sort_key,
    )
    active_job_refs = {_text(row.get("job_ref")) for row in packet_rows if _text(row.get("job_ref"))}
    mot_candidate_rows = sorted(
        [
            row
            for row in mot_rows
            if row.get("status") in {"new", "assigned", "retest_failed", "fixed_needs_retest"}
            and _text(row.get("luke_action_required")) != "1"
            and _text(row.get("job_ref")) not in active_job_refs
        ],
        key=_mot_sort_key,
    )
    control_backlog = _build_control_backlog(control_dir)

    current_tickets_markdown = _build_current_tickets_markdown(
        generated_utc=generated,
        packet_count=len(packet_rows),
        status_counts=status_counts,
        active_rows=active_rows,
        blocked_rows=blocked_rows,
    )
    backlog_markdown = _build_backlog_markdown(
        generated_utc=generated,
        blocked_rows=blocked_rows,
        parked_rows=parked_rows,
        mot_candidate_rows=mot_candidate_rows,
        control_backlog=control_backlog,
        proved_count=status_counts.get("proved", 0),
    )

    return CurrentWorkMarkdownResult(
        current_tickets_path=current_tickets_path,
        backlog_path=backlog_path,
        current_tickets_markdown=current_tickets_markdown,
        backlog_markdown=backlog_markdown,
        generated_utc=generated,
        active_count=len(active_rows),
        blocked_count=len(blocked_rows),
        parked_count=len(parked_rows),
        mot_candidate_count=len(mot_candidate_rows),
        control_backlog_count=len(control_backlog),
    )


def write_current_work_markdown(
    *,
    root: Path | str | None = None,
    generated_utc: str | None = None,
) -> CurrentWorkMarkdownResult:
    result = build_current_work_markdown(root=root, generated_utc=generated_utc)
    result.current_tickets_path.parent.mkdir(parents=True, exist_ok=True)
    result.current_tickets_path.write_text(result.current_tickets_markdown, encoding="utf-8")
    result.backlog_path.write_text(result.backlog_markdown, encoding="utf-8")
    return result


def format_current_work_markdown_status(result: CurrentWorkMarkdownResult) -> str:
    return "\n".join(
        [
            "status=written",
            f"current_tickets_path={result.current_tickets_path}",
            f"backlog_path={result.backlog_path}",
            f"generated_utc={result.generated_utc}",
            f"active_tickets={result.active_count}",
            f"blocked_tickets={result.blocked_count}",
            f"parked_tickets={result.parked_count}",
            f"mot_candidates={result.mot_candidate_count}",
            f"control_backlog={result.control_backlog_count}",
        ]
    )


def _build_current_tickets_markdown(
    *,
    generated_utc: str,
    packet_count: int,
    status_counts: Counter[str],
    active_rows: list[dict[str, str]],
    blocked_rows: list[dict[str, str]],
) -> str:
    lines = [
        "# SellerOne Current Tickets",
        "",
        "Job: `SO21-CURRENT-TICKETS-AND-BACKLOG`",
        f"Generated UTC: {generated_utc}",
        "Generated by: `sellerone_manager.current_work_markdown`",
        "",
        "## Plain-English Status",
        "",
        (
            f"There are {len(active_rows)} active non-Luke tickets. "
            f"{len(blocked_rows)} tickets need Luke or protected approval and are kept out of the Builder queue."
        ),
        "",
        "This file is a read-only view. It does not move task packets, change queue state, or start worker cycles.",
        "",
        "## Queue Counts",
        "",
        f"- Packet index rows: {packet_count}",
        f"- Ready for Builder: {status_counts.get('approved', 0)}",
        f"- Builder working: {status_counts.get('in_progress', 0)}",
        f"- Waiting proof: {status_counts.get('fixed_needs_retest', 0)}",
        f"- Proof failed: {status_counts.get('retest_failed', 0)}",
        f"- Reopened: {status_counts.get('reopened', 0)}",
        f"- Luke-blocked: {status_counts.get('blocked_needs_luke', 0)}",
        f"- Parked: {status_counts.get('parked', 0)}",
        f"- Proved history: {status_counts.get('proved', 0)}",
        "",
        "## Active Builder And Reviewer Tickets",
        "",
    ]
    if not active_rows:
        lines.append("No active non-Luke Builder or Reviewer tickets are visible in the packet index.")
    else:
        lines.extend(_format_ticket_table(active_rows))
    lines.extend(
        [
            "",
            "## Work Order Rule",
            "",
            "- Waiting-proof tickets should be reviewed before new Builder work starts.",
            "- Approved tickets can be claimed by one Builder at a time.",
            "- Luke-blocked and parked tickets belong in `BACKLOG.md`, not in the active Builder queue.",
            "- This file does not override task packet boundaries.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _build_backlog_markdown(
    *,
    generated_utc: str,
    blocked_rows: list[dict[str, str]],
    parked_rows: list[dict[str, str]],
    mot_candidate_rows: list[dict[str, str]],
    control_backlog: list[dict[str, str]],
    proved_count: int,
) -> str:
    lines = [
        "# SellerOne Backlog",
        "",
        "Job: `SO21-CURRENT-TICKETS-AND-BACKLOG`",
        f"Generated UTC: {generated_utc}",
        "Generated by: `sellerone_manager.current_work_markdown`",
        "",
        "## Plain-English Status",
        "",
        (
            "The backlog is work that exists but is not active Builder work today. "
            "It includes Luke decisions, parked work, MOT candidates, and SellerOne 2.1 control follow-ups."
        ),
        "",
        "This file is a read-only view. It does not approve protected actions or edit task packets.",
        "",
        "## Luke-Blocked Decisions",
        "",
    ]
    lines.extend(_format_backlog_section(blocked_rows, empty_message="No Luke-blocked packets are visible."))
    lines.extend(["", "## Parked Work", ""])
    lines.extend(_format_backlog_section(parked_rows, empty_message="No parked packets are visible."))
    lines.extend(["", "## MOT Candidate Work Not Yet In Active Queue", ""])
    if not mot_candidate_rows:
        lines.append("No unpromoted non-Luke MOT candidates are visible.")
    else:
        lines.extend(_format_mot_candidate_table(mot_candidate_rows[:12]))
        if len(mot_candidate_rows) > 12:
            lines.append(f"- Plus {len(mot_candidate_rows) - 12} more MOT candidate rows.")
    lines.extend(["", "## SellerOne 2.1 Control Backlog", ""])
    if not control_backlog:
        lines.append("No 2.1 control backlog items are currently missing.")
    else:
        lines.extend(_format_control_backlog(control_backlog))
    lines.extend(
        [
            "",
            "## Proved History",
            "",
            f"- Proved packet rows remain historical evidence: {proved_count}",
            "- Proved history is not active work unless fresh evidence reopens it.",
            "",
            "## Backlog Rules",
            "",
            "- Backlog is not approval to start protected work.",
            "- MOT candidates become active only when promoted into approved task packets.",
            "- Parked work stays parked until its trigger or decision changes.",
            "- Luke-blocked decisions need a clear human choice before Builder work can continue.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _format_ticket_table(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Job | Flow | Stage | Plain-English Work | Proof Route |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_code(_text(row.get("job_ref")) or _text(row.get("task_id"))),
                    _text(row.get("flow")) or "?",
                    STATUS_LABELS.get(_text(row.get("status")), _text(row.get("status")) or "unknown"),
                    _short(_text(row.get("title")), 120),
                    _proof_route(row),
                ]
            )
            + " |"
        )
    return lines


def _format_backlog_section(rows: list[dict[str, str]], *, empty_message: str) -> list[str]:
    if not rows:
        return [empty_message]
    lines = ["| Job | Flow | Stage | Why It Is Not Active Today |", "|---|---|---|---|"]
    for row in rows:
        reason = _text(row.get("notes")) or _text(row.get("title")) or _text(row.get("allowed_scope"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_code(_text(row.get("job_ref")) or _text(row.get("task_id"))),
                    _text(row.get("flow")) or "?",
                    STATUS_LABELS.get(_text(row.get("status")), _text(row.get("status")) or "unknown"),
                    _short(reason, 140),
                ]
            )
            + " |"
        )
    return lines


def _format_mot_candidate_table(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Candidate | Flow | MOT Stage | Next Safe Shape |", "|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_code(_text(row.get("job_ref")) or _text(row.get("work_item_id"))),
                    _text(row.get("flow")) or "?",
                    _text(row.get("status")) or "unknown",
                    _short(_text(row.get("manager_action")) or _text(row.get("title")), 140),
                ]
            )
            + " |"
        )
    return lines


def _format_control_backlog(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Job | Status | Why It Matters |", "|---|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_code(row["job_ref"]),
                    row["status"],
                    row["reason"],
                ]
            )
            + " |"
        )
    return lines


def _build_control_backlog(control_dir: Path) -> list[dict[str, str]]:
    backlog: list[dict[str, str]] = []
    if not (control_dir / "AI_USAGE.csv").exists():
        backlog.append(
            {
                "job_ref": "SO21-AI-USAGE-REPORT",
                "status": "planned",
                "reason": "track high-level AI spend, repeated failed loops, and noisy tasks by ticket",
            }
        )
    if not (control_dir / "INSTRUCTION_CLEANUP_PLAN.md").exists():
        backlog.append(
            {
                "job_ref": "SO21-INSTRUCTION-CLEANUP",
                "status": "recommended next",
                "reason": "reduce overlapping rulebooks and move repeat workflows into templates or skills",
            }
        )
    else:
        if _coding_plan_archive_needed(control_dir):
            backlog.append(
                {
                    "job_ref": "SO21-CODING-PLAN-ARCHIVE",
                    "status": "planned",
                    "reason": "move the oversized legacy F login coding plan into history and keep current work in control files",
                }
            )
        backlog.extend(
            [
                row
                for row in [
                    {
                        "job_ref": "SO21-ROLE-FILE-TRIM",
                        "status": "planned",
                        "reason": "trim manager, worker, and cycle role files now that the 2.1 role bootstrap exists",
                    }
                    if _role_file_trim_needed(control_dir)
                    else None,
                    {
                        "job_ref": "SO21-SKILL-SPECS",
                        "status": "planned",
                        "reason": "turn repeat manager, worker, MOT, and Custodian workflows into reusable skill or template specs",
                    }
                    if not (control_dir / "SKILL_SPECS.md").exists()
                    else None,
                    {
                        "job_ref": "SO21-PROMPT-FOLDER-ARCHIVE",
                        "status": "planned",
                        "reason": "mark old prompt folders as template/history only so they stop competing with the queue",
                    }
                    if _prompt_folder_archive_needed(control_dir)
                    else None,
                ]
                if row is not None
            ]
        )
    if _storage_index_mentions_out_subtree(control_dir / "STORAGE_INDEX.csv"):
        backlog.append(
            {
                "job_ref": "SO21-STORAGE-INDEX-OUT-SUBTREE",
                "status": "planned",
                "reason": "classify the mixed `out/` folder before any cleanup manifest is proposed",
            }
        )
    if (control_dir / "STORAGE_POLICY.md").exists() and _custodian_dry_run_manifest_needed(control_dir):
        backlog.append(
            {
                "job_ref": "SO21-CUSTODIAN-DRY-RUN-MANIFEST",
                "status": "planned",
                "reason": "preview cleanup candidates without deleting files",
            }
        )
    if not (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").exists():
        backlog.append(
            {
                "job_ref": "SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW",
                "status": "planned",
                "reason": "separate paused/retired automations from future useful watchers",
            }
        )
    elif _windows_scheduler_pause_decision_needed(control_dir):
        backlog.append(
            {
                "job_ref": "SO21-WINDOWS-SCHEDULER-PAUSE-DECISION",
                "status": "needs Luke decision",
                "reason": "ready Windows scheduled tasks still exist outside the Codex app automation pause",
            }
        )
    elif _windows_scheduler_admin_pause_needed(control_dir):
        backlog.append(
            {
                "job_ref": "SO21-WINDOWS-SCHEDULER-ADMIN-PAUSE",
                "status": "needs admin shell",
                "reason": "pause was approved and partially applied, but elevated Windows tasks are still ready",
            }
        )
    elif _automation_rebuild_needed(control_dir):
        backlog.append(
            {
                "job_ref": "SO21-AUTOMATION-REBUILD",
                "status": "planned",
                "reason": "design the smaller 2.1 automation set before any background work is reintroduced",
            }
        )
    elif _automation_activation_decision_needed(control_dir):
        backlog.append(
            {
                "job_ref": "SO21-AUTOMATION-ACTIVATION-DECISION",
                "status": "needs Luke decision",
                "reason": "automation rebuild plan exists; first pilot automation needs explicit activation choice",
            }
        )
    elif _rep_briefing_first_run_proof_needed(control_dir):
        backlog.append(
            {
                "job_ref": "SO21-REP-BRIEFING-FIRST-RUN-PROOF",
                "status": "waiting proof",
                "reason": "Rep briefing pilot is active; first scheduled read-only briefing run still needs proof",
            }
        )
    return backlog


def _storage_index_mentions_out_subtree(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return "needs out subtree index" in text or "needs out/ subtree index" in text


def _coding_plan_archive_needed(control_dir: Path) -> bool:
    root = control_dir.parents[1]
    coding_plan = root / "sellerone_manager" / "CODING_PLAN.md"
    archive_marker = control_dir / "CODING_PLAN_ARCHIVE.md"
    return coding_plan.exists() and coding_plan.stat().st_size >= 50_000 and not archive_marker.exists()


def _prompt_folder_archive_needed(control_dir: Path) -> bool:
    return not (control_dir / "PROMPT_FOLDER_ARCHIVE.md").exists()


def _role_file_trim_needed(control_dir: Path) -> bool:
    if (control_dir / "ROLE_FILE_TRIM.md").exists():
        return False
    root = control_dir.parents[1]
    targets = [
        root / "sellerone_manager" / "MANAGER_CHAT.md",
        root / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md",
        root / "sellerone_manager" / "CYCLE_SUB_MANAGER_CHAT.md",
        root / "sellerone_manager" / "WORKER_CHAT.md",
    ]
    return any(path.exists() and path.stat().st_size >= 10_000 for path in targets)


def _custodian_dry_run_manifest_needed(control_dir: Path) -> bool:
    return not (
        (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.csv").exists()
        or (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").exists()
    )


def _windows_scheduler_pause_decision_needed(control_dir: Path) -> bool:
    if (control_dir / "WINDOWS_SCHEDULER_PAUSE_DECISION.md").exists():
        return False
    rows = _read_csv_rows(control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv")
    return any(
        row.get("source_type") == "windows_scheduler"
        and row.get("luke_decision_required") == "yes"
        for row in rows
    )


def _windows_scheduler_admin_pause_needed(control_dir: Path) -> bool:
    rows = _read_csv_rows(control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv")
    return any(
        row.get("after_state") == "Ready"
        and row.get("exit_code") not in {"", "0"}
        for row in rows
    )


def _automation_rebuild_needed(control_dir: Path) -> bool:
    return not (
        (control_dir / "AUTOMATION_REBUILD.md").exists()
        and (control_dir / "AUTOMATION_REBUILD_PLAN.csv").exists()
    )


def _automation_activation_decision_needed(control_dir: Path) -> bool:
    return not (control_dir / "AUTOMATION_ACTIVATION_DECISION.md").exists()


def _rep_briefing_first_run_proof_needed(control_dir: Path) -> bool:
    return (
        (control_dir / "SO21_REP_BRIEFING_ACTIVATION.md").exists()
        and not (control_dir / "SO21_REP_BRIEFING_FIRST_RUN_PROOF.md").exists()
    )


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _work_sort_key(row: dict[str, str]) -> tuple[int, int, str, str]:
    status = _text(row.get("status"))
    priority = _text(row.get("priority")).lower()
    return (
        STATUS_SORT.get(status, 99),
        PRIORITY_SORT.get(priority, 9),
        _text(row.get("flow")),
        _text(row.get("job_ref")) or _text(row.get("task_id")),
    )


def _mot_sort_key(row: dict[str, str]) -> tuple[int, int, str, str]:
    priority = _text(row.get("priority")).lower()
    return (
        PRIORITY_SORT.get(priority, 9),
        0 if _text(row.get("status")) in {"new", "retest_failed"} else 1,
        _text(row.get("flow")),
        _text(row.get("job_ref")) or _text(row.get("work_item_id")),
    )


def _proof_route(row: dict[str, str]) -> str:
    command = _text(row.get("retest_command"))
    flow = _text(row.get("flow"))
    if "--hourly-mot" in command and flow:
        return f"{flow} MOT retest"
    if "pytest" in command:
        return "focused tests"
    if command:
        return "packet proof command"
    if _text(row.get("proof_required")):
        return "packet proof required"
    return "proof path not listed"


def _text(value: object) -> str:
    return str(value or "").strip()


def _short(value: str, limit: int) -> str:
    cleaned = " ".join(_text(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _md_code(value: str) -> str:
    safe = _text(value).replace("`", "")
    return f"`{safe}`" if safe else "`unknown`"
