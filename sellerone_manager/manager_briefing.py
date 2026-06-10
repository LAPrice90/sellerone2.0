from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .paths import get_manager_paths
from .task_board import TaskCard, load_task_board


FLOW_ORDER = ["A", "B", "E", "H", "F", "O", "M"]

FLOW_NAMES = {
    "A": ("A", "source facts"),
    "B": ("B", "orders, refunds, fees, token COGS"),
    "E": ("E", "sales velocity and confidence"),
    "H": ("H", "repricing safety"),
    "F": ("F", "supplier scanner"),
    "O": ("O", "restocking workspace"),
    "M": ("M", "main manager"),
}

FLOW_COLOURS = {
    "A": "#15803d",
    "B": "#2563eb",
    "E": "#7c3aed",
    "H": "#dc2626",
    "F": "#0f766e",
    "O": "#b45309",
    "M": "#374151",
}

GITHUB_BRIEFING_LATEST = "docs/manager-briefing/latest.md"
GITHUB_BRIEFING_HISTORY_DIR = "docs/manager-briefing/history"


@dataclass(frozen=True)
class BriefingJob:
    job_ref: str
    title: str
    flow: str
    status: str
    lane: str
    priority: str
    luke_action_required: bool
    note: str
    proof_required: str


@dataclass(frozen=True)
class MovementWatch:
    label: str
    state: str
    detail: str
    next_move: str


@dataclass(frozen=True)
class ManagerCard:
    flow: str
    name: str
    subtitle: str
    colour: str
    status: str
    progress_pct: int
    current_story: str
    next_move: str
    luke_action_required: bool
    luke_action: str
    active_job_count: int
    blocked_job_count: int
    parked_job_count: int
    waiting_proof_count: int
    proved_history_count: int
    jobs: tuple[BriefingJob, ...]


@dataclass(frozen=True)
class ManagerBriefing:
    observed_utc: str
    audience: str
    overall_status: str
    restocking_readiness_pct: int
    restocking_summary: str
    source_warning: str
    movement_watch: tuple[MovementWatch, ...]
    managers: tuple[ManagerCard, ...]
    decisions: tuple[BriefingJob, ...]


@dataclass(frozen=True)
class ManagerBriefingWriteResult:
    latest_json: Path
    latest_md: Path
    history_md: Path
    github_latest_md: Path | None = None
    github_history_md: Path | None = None
    github_manifest_json: Path | None = None


def build_manager_briefing(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    include_proved_history: bool = False,
) -> ManagerBriefing:
    paths = get_manager_paths(root)
    manager_dir = paths.root / "sellerone_manager"
    state = _read_json(manager_dir / "current_state.json")
    flow_states = {
        str(row.get("flow") or "").upper(): row
        for row in state.get("flow_states", [])
        if isinstance(row, dict)
    }
    progress = _parse_progress_tracker(manager_dir / "MANAGER_PROGRESS_TRACKER.md")
    active_board = load_task_board(root=paths.root, active_only=True)
    proved_board = load_task_board(root=paths.root, active_only=False, statuses=["proved"])
    progress.setdefault("M", {})["story"] = _manager_board_story(active_board.lane_counts, active_board.total_cards)
    visible_jobs_by_flow = _jobs_by_flow(active_board.cards)
    proved_count_by_flow = _proved_counts(proved_board.cards)

    if include_proved_history:
        all_board = load_task_board(root=paths.root, active_only=False)
        visible_jobs_by_flow = _jobs_by_flow(all_board.cards)

    observed = (
        _clean_text(observed_utc)
        or _clean_text(state.get("generated_utc"))
        or _clean_text(state.get("source_observed_utc"))
        or _utc_now()
    )

    managers: list[ManagerCard] = []
    for flow in FLOW_ORDER:
        flow_state = flow_states.get(flow, {})
        jobs = visible_jobs_by_flow.get(flow, [])
        cards = _cards_for_flow(jobs)
        progress_pct = _progress_for_flow(flow, flow_state, progress)
        status = _status_for_flow(flow, flow_state, jobs)
        story = _story_for_flow(flow, flow_state, progress, jobs)
        next_move = _next_move_for_flow(flow, jobs, status)
        luke_job = next((job for job in jobs if job.luke_action_required), None)
        luke_action = _clean_text(flow_state.get("luke_decision")) or (luke_job.title if luke_job else "")
        managers.append(
            ManagerCard(
                flow=flow,
                name=FLOW_NAMES[flow][0],
                subtitle=FLOW_NAMES[flow][1],
                colour=FLOW_COLOURS[flow],
                status=status,
                progress_pct=progress_pct,
                current_story=story,
                next_move=next_move,
                luke_action_required=bool(luke_action),
                luke_action=_safe_public_text(luke_action),
                active_job_count=len([job for job in jobs if job.status != "proved"]),
                blocked_job_count=len([job for job in jobs if job.status == "blocked_needs_luke"]),
                parked_job_count=len([job for job in jobs if job.status == "parked"]),
                waiting_proof_count=len([job for job in jobs if job.status == "fixed_needs_retest"]),
                proved_history_count=proved_count_by_flow.get(flow, 0),
                jobs=tuple(cards),
            )
        )

    decisions = tuple(
        job
        for manager in managers
        for job in manager.jobs
        if job.luke_action_required and job.status == "blocked_needs_luke"
    )
    restocking_readiness = _restocking_readiness(managers)
    return ManagerBriefing(
        observed_utc=observed,
        audience="private_luke",
        overall_status=_overall_status(managers),
        restocking_readiness_pct=restocking_readiness,
        restocking_summary=_restocking_summary(managers, restocking_readiness),
        source_warning=(
            "Private Luke briefing. It hides raw paths and technical evidence by default, "
            "but still shows internal cycle names and job references."
        ),
        movement_watch=_movement_watch(paths.root, managers),
        managers=tuple(managers),
        decisions=decisions,
    )


def write_manager_briefing_outputs(
    briefing: ManagerBriefing,
    *,
    root: Path | str | None = None,
    write_github_snapshot: bool = False,
) -> ManagerBriefingWriteResult:
    paths = get_manager_paths(root)
    communications_dir = paths.output_dir / "communications"
    communications_dir.mkdir(parents=True, exist_ok=True)
    stamp = _stamp_from_observed(briefing.observed_utc)
    latest_json = communications_dir / "manager_briefing_latest.json"
    latest_md = communications_dir / "manager_briefing_latest.md"
    history_md = communications_dir / f"manager_briefing_{stamp}.md"
    markdown = render_manager_briefing_markdown(briefing)
    latest_json.write_text(json.dumps(_briefing_to_dict(briefing), indent=2) + "\n", encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")
    history_md.write_text(markdown, encoding="utf-8")

    github_latest_md: Path | None = None
    github_history_md: Path | None = None
    github_manifest_json: Path | None = None
    if write_github_snapshot:
        docs_dir = paths.root / "docs" / "manager-briefing"
        history_dir = docs_dir / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        github_latest_md = docs_dir / "latest.md"
        github_history_md = history_dir / f"{stamp}.md"
        latest_changed = (not github_latest_md.exists()) or github_latest_md.read_text(encoding="utf-8") != markdown
        history_changed = (not github_history_md.exists()) or github_history_md.read_text(encoding="utf-8") != markdown
        github_latest_md.write_text(markdown, encoding="utf-8")
        github_history_md.write_text(markdown, encoding="utf-8")
        github_manifest_json = communications_dir / "github_publish_manifest.json"
        github_manifest_json.write_text(
            json.dumps(
                _github_publish_manifest(
                    paths.root,
                    briefing,
                    latest_path=github_latest_md,
                    history_path=github_history_md,
                    latest_content=markdown,
                    history_content=markdown,
                    latest_changed=latest_changed,
                    history_changed=history_changed,
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return ManagerBriefingWriteResult(
        latest_json=latest_json,
        latest_md=latest_md,
        history_md=history_md,
        github_latest_md=github_latest_md,
        github_history_md=github_history_md,
        github_manifest_json=github_manifest_json,
    )


def build_and_write_manager_briefing(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    write_github_snapshot: bool = False,
    include_proved_history: bool = False,
) -> tuple[ManagerBriefing, ManagerBriefingWriteResult]:
    briefing = build_manager_briefing(
        root=root,
        observed_utc=observed_utc,
        include_proved_history=include_proved_history,
    )
    result = write_manager_briefing_outputs(
        briefing,
        root=root,
        write_github_snapshot=write_github_snapshot,
    )
    return briefing, result


def format_manager_briefing_status(briefing: ManagerBriefing, result: ManagerBriefingWriteResult | None = None) -> str:
    lines = [
        f"status={briefing.overall_status}",
        f"restocking_readiness_pct={briefing.restocking_readiness_pct}",
        f"observed_utc={briefing.observed_utc}",
    ]
    for manager in briefing.managers:
        lines.append(f"{manager.flow}={manager.status};progress={manager.progress_pct};jobs={manager.active_job_count}")
    if result is not None:
        for key, value in asdict(result).items():
            if value:
                lines.append(f"{key}={value}")
    return "\n".join(lines)


def render_manager_briefing_markdown(briefing: ManagerBriefing) -> str:
    lines = [
        "# SellerOne Manager Briefing",
        "",
        f"Observed UTC: {briefing.observed_utc}",
        "",
        "## Today At A Glance",
        "",
        f"- Overall status: {_title_status(briefing.overall_status)}",
        f"- Restocking readiness: {briefing.restocking_readiness_pct}%",
        f"- Summary: {briefing.restocking_summary}",
        "",
        "## Manager Progress",
        "",
        "| Manager | Role | Status | Progress | What matters | Next move |",
        "|---|---|---:|---:|---|---|",
    ]
    for manager in briefing.managers:
        lines.append(
            "| {flow} | {role} | {status} | {progress}% | {story} | {next_move} |".format(
                flow=manager.flow,
                role=_md_cell(manager.subtitle),
                status=_md_cell(_title_status(manager.status)),
                progress=manager.progress_pct,
                story=_md_cell(manager.current_story),
                next_move=_md_cell(manager.next_move),
            )
        )

    lines.extend(["", "## Visible Decisions", ""])
    if not briefing.decisions:
        lines.append("- No active Luke decision is required from this briefing.")
    else:
        for decision in briefing.decisions:
            lines.append(f"- {decision.job_ref}: {_safe_public_text(decision.title)}")

    lines.extend(["", "## Movement Watch", ""])
    if not briefing.movement_watch:
        lines.append("- No active movement watch rows are available yet.")
    else:
        for item in briefing.movement_watch:
            lines.append(
                f"- {item.label}: {item.state}. {_safe_public_text(item.detail)} Next: {_safe_public_text(item.next_move)}"
            )

    lines.extend(["", "## Active Job Breakdown", ""])
    for manager in briefing.managers:
        if not manager.jobs:
            lines.append(f"### {manager.flow} - {manager.subtitle}")
            lines.append("")
            lines.append("- No visible active jobs.")
            lines.append("")
            continue
        lines.append(f"### {manager.flow} - {manager.subtitle}")
        lines.append("")
        for job in manager.jobs:
            label = "Luke gate" if job.luke_action_required else _title_status(job.status)
            lines.append(f"- {job.job_ref}: {label}. {_safe_public_text(job.title)}")
        lines.append("")

    lines.extend(
        [
            "## Safety",
            "",
            "- This briefing is read-only.",
            "- It must not run workers, change prices, edit queues, write Sheets, align database facts, delete outputs, or change task status.",
            "- Raw file paths and technical proof details stay out of the briefing unless Luke opens technical details in the local UI.",
            "",
        ]
    )
    return "\n".join(lines)


def _briefing_to_dict(briefing: ManagerBriefing) -> dict[str, object]:
    return asdict(briefing)


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [{key: value or "" for key, value in row.items() if key is not None} for row in csv.DictReader(handle)]


def _movement_watch(root: Path, managers: tuple[ManagerCard, ...]) -> tuple[MovementWatch, ...]:
    rows: list[MovementWatch] = []
    f_rows = _read_csv_rows(root / "out" / "systems" / "M" / "hourly_mot_F.csv")
    f_live = next((row for row in f_rows if row.get("check") == "f_live_owner_status"), {})
    f_detail = _f_scanner_movement_detail(f_live)
    if f_detail:
        rows.append(f_detail)

    job_rows = _read_csv_rows(root / "out" / "systems" / "M" / "approved_task_packets.csv")
    for job_ref in ("F-DHB-FORWARD-PROGRESS", "F-SCANNER-PROGRESS"):
        job = next((row for row in job_rows if row.get("job_ref") == job_ref), {})
        if job:
            status = _title_status(_clean_text(job.get("status")) or "unknown")
            rows.append(
                MovementWatch(
                    label=job_ref,
                    state=status,
                    detail=_job_movement_detail(job),
                    next_move=_job_movement_next_move(job),
                )
            )

    for manager in managers:
        if manager.flow not in {"B", "O"}:
            continue
        rows.append(
            MovementWatch(
                label=f"{manager.flow} manager lane",
                state=_title_status(manager.status),
                detail=f"{manager.active_job_count} active jobs, {manager.waiting_proof_count} waiting proof, {manager.blocked_job_count} Luke gates.",
                next_move=manager.next_move,
            )
        )
    return tuple(rows)


def _f_scanner_movement_detail(row: dict[str, str]) -> MovementWatch | None:
    if not row:
        return None
    proof = _parse_semicolon_fields(row.get("actual_proof", ""))
    supplier = proof.get("active_supplier_id") or "unknown supplier"
    forward_state = proof.get("scanner_forward_state") or "unknown"
    chunks = proof.get("recent_scanner_chunks") or "?"
    span = proof.get("scanner_span_minutes") or "?"
    first_pending = proof.get("first_pending_after") or "?"
    latest_pending = proof.get("latest_pending_after") or "?"
    pending_drop = proof.get("pending_drop") or "?"
    processed = proof.get("processed_rows") or "?"
    memory_blocks = proof.get("memory_import_blocked_recent") or "?"
    if forward_state == "stalled" or row.get("status") == "fail":
        state = "Stalled"
        next_move = "Worker must repair the approved F-DHB package; Luke is not needed unless the repair crosses a protected boundary."
    elif forward_state == "progressing":
        state = "Moving"
        next_move = "Keep watching until F MOT clears or the worker marks proof ready."
    else:
        state = _title_status(forward_state or row.get("status") or "Unknown")
        next_move = "Keep watching the next manager pulse."
    detail = (
        f"{supplier} over {chunks} chunks and {span} minutes: pending {first_pending} to {latest_pending}, "
        f"drop {pending_drop}, processed rows {processed}, memory blocks {memory_blocks}."
    )
    return MovementWatch(
        label="F live scanner movement",
        state=state,
        detail=detail,
        next_move=next_move,
    )


def _parse_semicolon_fields(value: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in str(value or "").split(";"):
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        key = key.strip()
        if key:
            fields[key] = raw_value.strip()
    return fields


def _job_movement_detail(job: dict[str, str]) -> str:
    status = _clean_text(job.get("status")) or "unknown"
    note = _safe_public_text(job.get("notes") or job.get("title"))
    if status in {"fixed_needs_retest", "retest_failed"}:
        return f"Job has moved to {status}; proof status changed."
    if status in {"approved", "in_progress"}:
        return f"Job is {status}; no Luke gate is active."
    return note or f"Job is {status}."


def _job_movement_next_move(job: dict[str, str]) -> str:
    status = _clean_text(job.get("status"))
    if status == "fixed_needs_retest":
        return "Run/read the approved MOT retest and mark proved only after evidence clears."
    if status == "retest_failed":
        return "Reopen with failed proof and continue inside the packet."
    if status == "in_progress":
        return "Continue worker repair until proof is ready."
    if status == "approved":
        return "Start or continue the approved worker packet."
    if status == "blocked_needs_luke":
        return "Keep visible as a protected decision."
    return "Keep watching in the next manager pulse."


def _parse_progress_tracker(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    progress: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|") or "---" in line or "Owner" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        owner = cells[1].lower()
        flow = _flow_from_owner(owner)
        if not flow:
            continue
        pct_match = re.search(r"(\d{1,3})\s*%", cells[-1])
        if pct_match:
            progress.setdefault(flow, {})["progress_pct"] = pct_match.group(1)
        if len(cells) >= 4:
            progress.setdefault(flow, {})["story"] = _safe_public_text(cells[3])
        if cells[0]:
            progress.setdefault(flow, {})["lane"] = _safe_public_text(cells[0])

    overall_match = re.search(r"Overall Manager Takeover.*?\[(?:#|-)+\]\s*(\d{1,3})%", text, re.DOTALL)
    if overall_match:
        progress.setdefault("M", {})["progress_pct"] = overall_match.group(1)
    return progress


def _flow_from_owner(owner: str) -> str:
    if "main manager" in owner:
        return "M"
    for flow in FLOW_ORDER:
        if owner.startswith(flow.lower() + " ") or owner == flow.lower():
            return flow
    return ""


def _jobs_by_flow(cards: Iterable[TaskCard]) -> dict[str, list[TaskCard]]:
    grouped: dict[str, list[TaskCard]] = {flow: [] for flow in FLOW_ORDER}
    for card in cards:
        flow = _clean_text(card.flow).upper() or "M"
        grouped.setdefault(flow, []).append(card)
    return grouped


def _proved_counts(cards: Iterable[TaskCard]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in cards:
        flow = _clean_text(card.flow).upper() or "M"
        counts[flow] = counts.get(flow, 0) + 1
    return counts


def _cards_for_flow(cards: list[TaskCard]) -> tuple[BriefingJob, ...]:
    jobs: list[BriefingJob] = []
    for card in cards:
        jobs.append(
            BriefingJob(
                job_ref=_safe_public_text(card.job_ref or card.task_id),
                title=_safe_public_text(card.title),
                flow=_clean_text(card.flow).upper() or "M",
                status=_clean_text(card.status),
                lane=_safe_public_text(card.lane),
                priority=_clean_text(card.priority) or "normal",
                luke_action_required=bool(card.luke_action_required),
                note=_safe_public_text(card.notes),
                proof_required=_safe_public_text(card.proof_required),
            )
        )
    return tuple(jobs)


def _progress_for_flow(flow: str, flow_state: dict[str, object], progress: dict[str, dict[str, str]]) -> int:
    raw = progress.get(flow, {}).get("progress_pct", "")
    if raw:
        return _clamp_pct(raw)
    status = _clean_text(flow_state.get("status")).lower()
    if status == "ok":
        return 100
    if status == "warn":
        return 70
    if status == "parked":
        return 55
    if status in {"blocked", "fail"}:
        return 35
    covered = _to_int(flow_state.get("covered_expectations"))
    total = _to_int(flow_state.get("total_expectations"))
    if total > 0:
        return _clamp_pct(round((covered / total) * 100))
    return 0


def _status_for_flow(flow: str, flow_state: dict[str, object], jobs: list[TaskCard]) -> str:
    status = _clean_text(flow_state.get("status")).lower()
    if any(job.status == "blocked_needs_luke" for job in jobs):
        return "blocked"
    if status in {"blocked", "fail", "decision_needed"}:
        return "blocked"
    if any(job.status == "retest_failed" for job in jobs):
        return "blocked"
    if any(job.status == "fixed_needs_retest" for job in jobs):
        return "waiting proof"
    if any(job.status == "in_progress" for job in jobs):
        return "working"
    if any(job.status == "approved" for job in jobs):
        return "working"
    if status in {"warn", "warning", "not_checked"}:
        return "warning"
    if status == "parked" or any(job.status == "parked" for job in jobs):
        return "parked"
    if status == "ok":
        return "calm"
    if flow == "M":
        return "working" if jobs else "warning"
    return "not started"


def _story_for_flow(
    flow: str,
    flow_state: dict[str, object],
    progress: dict[str, dict[str, str]],
    jobs: list[TaskCard],
) -> str:
    if progress.get(flow, {}).get("story"):
        return _safe_public_text(progress[flow]["story"])
    blocker = _clean_text(flow_state.get("first_blocker_summary"))
    if blocker:
        return _safe_public_text(blocker)
    notes = _clean_text(flow_state.get("notes"))
    if notes:
        return _safe_public_text(notes)
    if jobs:
        first = jobs[0]
        return _safe_public_text(first.notes or first.title)
    if flow == "M":
        return "Main manager is combining the cycle states into one control briefing."
    return "No active issue is visible from the current manager files."


def _next_move_for_flow(flow: str, jobs: list[TaskCard], status: str) -> str:
    for wanted in ("in_progress", "approved", "fixed_needs_retest", "retest_failed"):
        job = next((item for item in jobs if item.status == wanted and not item.luke_action_required), None)
        if job:
            if wanted == "fixed_needs_retest":
                return f"Retest {job.job_ref or job.task_id} through MOT."
            if wanted == "retest_failed":
                return f"Reopen {job.job_ref or job.task_id} with the failed proof."
            return f"Continue {job.job_ref or job.task_id} inside its approved packet."
    luke_job = next((item for item in jobs if item.luke_action_required), None)
    if luke_job:
        return f"Keep {luke_job.job_ref or luke_job.task_id} visible as a protected Luke decision."
    if status == "calm":
        return "No further action needed now."
    if status == "warning":
        return "Keep warning visible and continue only if it blocks today's restocking work."
    if status == "parked":
        return "Stay parked unless new proof changes the manager state."
    return "Refresh the manager board before assigning new work."


def _overall_status(managers: Iterable[ManagerCard]) -> str:
    statuses = {manager.status for manager in managers}
    if "blocked" in statuses:
        return "blocked"
    if "working" in statuses or "waiting proof" in statuses:
        return "working"
    if "warning" in statuses or "parked" in statuses:
        return "warning"
    return "calm"


def _restocking_readiness(managers: Iterable[ManagerCard]) -> int:
    by_flow = {manager.flow: manager.progress_pct for manager in managers}
    weighted = (
        by_flow.get("B", 0) * 0.30
        + by_flow.get("O", 0) * 0.30
        + by_flow.get("E", 0) * 0.15
        + by_flow.get("H", 0) * 0.15
        + by_flow.get("F", 0) * 0.10
    )
    return _clamp_pct(round(weighted))


def _restocking_summary(managers: Iterable[ManagerCard], pct: int) -> str:
    by_flow = {manager.flow: manager for manager in managers}
    blockers = [flow for flow in ("B", "O", "H", "F") if by_flow.get(flow) and by_flow[flow].status == "blocked"]
    if blockers:
        return f"Restocking is not clean yet. The main blocker managers are {', '.join(blockers)}."
    warnings = [flow for flow in ("B", "O", "H", "E") if by_flow.get(flow) and by_flow[flow].status in {"warning", "parked"}]
    if warnings:
        return f"Restocking can be reviewed carefully, but {', '.join(warnings)} still need warning labels."
    if pct >= 85:
        return "Restocking evidence is close to ready for a controlled buying review."
    return "Restocking evidence is still being organised before it should drive buying decisions."


def _manager_board_story(lane_counts: dict[str, int], total_cards: int) -> str:
    parts = [
        f"{total_cards} active cards",
        f"{lane_counts.get('Not Started', 0)} not started",
        f"{lane_counts.get('In Progress', 0)} in progress",
        f"{lane_counts.get('Blocked', 0)} blocked",
        f"{lane_counts.get('Parked', 0)} parked",
    ]
    return "Current Manager Task Board: " + ", ".join(parts) + "."


def _github_publish_manifest(
    root: Path,
    briefing: ManagerBriefing,
    *,
    latest_path: Path,
    history_path: Path,
    latest_content: str,
    history_content: str,
    latest_changed: bool,
    history_changed: bool,
) -> dict[str, object]:
    latest_rel = _repo_relative(root, latest_path)
    history_rel = _repo_relative(root, history_path)
    return {
        "status": "prepared_for_github_connector",
        "repository_full_name": _repository_full_name(root),
        "branch": _current_branch(root),
        "observed_utc": briefing.observed_utc,
        "files": [
            _publish_file_payload(root, latest_path, latest_rel, latest_content, latest_changed),
            _publish_file_payload(root, history_path, history_rel, history_content, history_changed),
        ],
        "safety": {
            "allowed_paths": [GITHUB_BRIEFING_LATEST, f"{GITHUB_BRIEFING_HISTORY_DIR}/"],
            "forbidden_actions": [
                "no worker cycles",
                "no prices",
                "no queues",
                "no Sheets",
                "no local DB alignment",
                "no output deletion",
                "no task status changes",
            ],
        },
    }


def _publish_file_payload(root: Path, local_path: Path, repo_path: str, content: str, changed: bool) -> dict[str, object]:
    return {
        "path": repo_path,
        "local_path": str(local_path),
        "content": content,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "changed_from_local_before_write": changed,
        "commit_message": f"Update SellerOne manager briefing {Path(repo_path).name}",
    }


def _repository_full_name(root: Path) -> str:
    config_path = root / ".git" / "config"
    if not config_path.exists():
        return "LAPrice90/sellerone2.0"
    text = config_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        match = re.search(r"url\s*=\s*(?:https://github\.com/|git@github\.com:)([^\s]+?)(?:\.git)?$", line.strip())
        if match:
            return match.group(1)
    return "LAPrice90/sellerone2.0"


def _current_branch(root: Path) -> str:
    head = root / ".git" / "HEAD"
    if not head.exists():
        return ""
    text = head.read_text(encoding="utf-8", errors="replace").strip()
    if text.startswith("ref: refs/heads/"):
        return text.removeprefix("ref: refs/heads/")
    return ""


def _repo_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _stamp_from_observed(observed_utc: str) -> str:
    cleaned = _clean_text(observed_utc)
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(UTC)
    return parsed.astimezone(UTC).strftime("%Y%m%d-%H%M")


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _safe_public_text(value: object) -> str:
    text = _clean_text(value)
    text = re.sub(r"[A-Za-z]:\\[^\n\r\t|;]+", "[local file]", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _md_cell(value: object) -> str:
    return _safe_public_text(value).replace("|", "/")


def _title_status(value: str) -> str:
    return _clean_text(value).replace("_", " ").title()


def _to_int(value: object) -> int:
    try:
        return int(float(_clean_text(value) or "0"))
    except ValueError:
        return 0


def _clamp_pct(value: object) -> int:
    return max(0, min(100, _to_int(value)))


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
