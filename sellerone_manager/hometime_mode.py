from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .paths import get_manager_paths
from .task_board import TaskCard, load_task_board


HOMETIME_JOB_COLUMNS = [
    "session_id",
    "observed_utc",
    "job_ref",
    "task_id",
    "flow",
    "title",
    "task_status",
    "hometime_status",
    "priority",
    "safe_to_continue",
    "luke_action_required",
    "selected_for_evening",
    "reason",
    "proof_required",
    "retest_command",
    "stop_condition",
    "packet_path",
    "automation_key",
    "automation_prompt",
]

HOMETIME_NOTIFICATION_COLUMNS = [
    "session_id",
    "observed_utc",
    "job_ref",
    "task_id",
    "flow",
    "notification_type",
    "email_to",
    "email_status",
    "evidence_hash",
    "subject",
    "message",
    "suppression_reason",
]

TERMINAL_HOMETIME_STATUSES = {"proved", "parked", "blocked_needs_luke"}
RUNNABLE_TASK_STATUSES = {"queued", "in_progress", "waiting_proof", "retest_failed"}
PROTECTED_ACTION_WORDS = {
    "price",
    "prices",
    "pricing",
    "queue",
    "queues",
    "sheet",
    "sheets",
    "publish",
    "publishing",
    "local db",
    "product db",
    "delete",
    "deletion",
    "restart",
    "worker restart",
    "business judgement",
}


@dataclass(frozen=True)
class HometimePolicy:
    policy_id: str
    status: str
    mode: str
    pulse_minutes: int
    finish_rule: str
    autonomy_level: str
    notification_email: str
    duplicate_email_cooldown_minutes: int
    allowed_plain_english: tuple[str, ...]
    blocked_plain_english: tuple[str, ...]


@dataclass(frozen=True)
class HometimeJob:
    session_id: str
    observed_utc: str
    job_ref: str
    task_id: str
    flow: str
    title: str
    task_status: str
    hometime_status: str
    priority: str
    safe_to_continue: bool
    luke_action_required: bool
    selected_for_evening: bool
    reason: str
    proof_required: str
    retest_command: str
    stop_condition: str
    packet_path: str
    automation_key: str
    automation_prompt: str


@dataclass(frozen=True)
class HometimeNotification:
    session_id: str
    observed_utc: str
    job_ref: str
    task_id: str
    flow: str
    notification_type: str
    email_to: str
    email_status: str
    evidence_hash: str
    subject: str
    message: str
    suppression_reason: str


@dataclass(frozen=True)
class HometimeResult:
    session_id: str
    observed_utc: str
    command: str
    overall_status: str
    finish_rule: str
    pulse_minutes: int
    selected_job_count: int
    safe_job_count: int
    blocked_job_count: int
    settled_job_count: int
    preflight_permission_count: int
    email_required_count: int
    email_suppressed_count: int
    jobs: tuple[HometimeJob, ...]
    notifications: tuple[HometimeNotification, ...]
    output_paths: dict[str, str]


def start_hometime(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    dry_run: bool = False,
) -> HometimeResult:
    return _build_hometime_result(root=root, observed_utc=observed_utc, command="start", dry_run=dry_run)


def preflight_hometime(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    dry_run: bool = False,
) -> HometimeResult:
    return _build_hometime_result(root=root, observed_utc=observed_utc, command="preflight", dry_run=dry_run)


def pulse_hometime(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    dry_run: bool = False,
) -> HometimeResult:
    return _build_hometime_result(root=root, observed_utc=observed_utc, command="pulse", dry_run=dry_run)


def stop_hometime(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    dry_run: bool = False,
) -> HometimeResult:
    return _build_hometime_result(root=root, observed_utc=observed_utc, command="stop", force_stop=True, dry_run=dry_run)


def status_hometime(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    dry_run: bool = False,
) -> HometimeResult:
    return _build_hometime_result(root=root, observed_utc=observed_utc, command="status", dry_run=dry_run)


def write_hometime_outputs(result: HometimeResult, *, root: Path | str | None = None) -> dict[str, Path]:
    paths = get_manager_paths(root)
    output_dir = _hometime_output_dir(paths.root)
    output_dir.mkdir(parents=True, exist_ok=True)

    latest_json = output_dir / "hometime_latest.json"
    latest_md = output_dir / "hometime_latest.md"
    jobs_csv = output_dir / "hometime_jobs.csv"
    notifications_csv = output_dir / "hometime_notifications.csv"
    history_jsonl = output_dir / "hometime_history.jsonl"

    payload = _result_payload(result)
    latest_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_md.write_text(_format_hometime_markdown(result), encoding="utf-8")
    _write_csv(jobs_csv, HOMETIME_JOB_COLUMNS, [_job_row(job) for job in result.jobs])
    _write_csv(
        notifications_csv,
        HOMETIME_NOTIFICATION_COLUMNS,
        [_notification_row(notification) for notification in result.notifications],
    )
    with history_jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")

    return {
        "latest_json": latest_json,
        "latest_md": latest_md,
        "jobs_csv": jobs_csv,
        "notifications_csv": notifications_csv,
        "history_jsonl": history_jsonl,
    }


def format_hometime_status(result: HometimeResult) -> str:
    lines = [
        f"session_id={result.session_id}",
        f"status={result.overall_status}",
        f"selected_jobs={result.selected_job_count}",
        f"safe_jobs={result.safe_job_count}",
        f"blocked_jobs={result.blocked_job_count}",
        f"preflight_permissions={result.preflight_permission_count}",
        f"email_required={result.email_required_count}",
        f"email_suppressed={result.email_suppressed_count}",
    ]
    for name, path in sorted(result.output_paths.items()):
        lines.append(f"{name}={path}")
    return "\n".join(lines)


def _build_hometime_result(
    *,
    root: Path | str | None,
    observed_utc: str | None,
    command: str,
    force_stop: bool = False,
    dry_run: bool = False,
) -> HometimeResult:
    paths = get_manager_paths(root)
    observed = _observed_utc(observed_utc)
    policy = _load_policy(paths.root)
    session_id = _session_id(paths.root, observed)
    board = load_task_board(root=paths.root, active_only=True)
    hometime_dir = _hometime_output_dir(paths.root)
    session_state_exists = (hometime_dir / "hometime_latest.json").exists()
    previous_notifications = _read_csv_rows(hometime_dir / "hometime_notifications.csv")

    jobs = tuple(_job_from_card(card, session_id=session_id, observed_utc=observed, policy=policy) for card in board.cards)
    selected_jobs = tuple(job for job in jobs if job.selected_for_evening)
    notifications = tuple(
        _notification_for_job(
            job,
            command=command,
            policy=policy,
            session_state_exists=session_state_exists,
            previous_notifications=previous_notifications,
        )
        for job in selected_jobs
        if job.luke_action_required or job.hometime_status == "blocked_needs_luke"
    )

    selected_count = len(selected_jobs)
    safe_count = sum(1 for job in selected_jobs if job.safe_to_continue)
    blocked_count = sum(1 for job in selected_jobs if job.hometime_status == "blocked_needs_luke")
    settled_count = sum(1 for job in selected_jobs if job.hometime_status in TERMINAL_HOMETIME_STATUSES)
    preflight_count = sum(1 for item in notifications if item.email_status == "preflight_permission_required")
    required_count = sum(1 for item in notifications if item.email_status == "pending_codex_email")
    suppressed_count = sum(1 for item in notifications if item.email_status == "suppressed_duplicate")

    if force_stop:
        overall_status = "stopped"
    elif selected_count == 0:
        overall_status = "settled"
    elif settled_count == selected_count:
        overall_status = "settled"
    elif blocked_count and safe_count == 0:
        overall_status = "blocked_needs_luke"
    else:
        overall_status = "running"

    result = HometimeResult(
        session_id=session_id,
        observed_utc=observed,
        command=command,
        overall_status=overall_status,
        finish_rule=policy.finish_rule,
        pulse_minutes=policy.pulse_minutes,
        selected_job_count=selected_count,
        safe_job_count=safe_count,
        blocked_job_count=blocked_count,
        settled_job_count=settled_count,
        preflight_permission_count=preflight_count,
        email_required_count=required_count,
        email_suppressed_count=suppressed_count,
        jobs=selected_jobs,
        notifications=notifications,
        output_paths={},
    )
    if dry_run:
        return result
    output_paths = write_hometime_outputs(result, root=paths.root)
    return replace(result, output_paths={key: str(value) for key, value in output_paths.items()})


def _job_from_card(card: TaskCard, *, session_id: str, observed_utc: str, policy: HometimePolicy) -> HometimeJob:
    hometime_status = _hometime_status(card)
    luke_needed = bool(card.luke_action_required) or hometime_status == "blocked_needs_luke"
    selected = _selected_for_evening(card, hometime_status)
    safe_to_continue = selected and not luke_needed and hometime_status in RUNNABLE_TASK_STATUSES and _safe_for_hometime(card, policy)
    reason = _job_reason(card, hometime_status, safe_to_continue, luke_needed)
    automation_key = _automation_key(card)
    return HometimeJob(
        session_id=session_id,
        observed_utc=observed_utc,
        job_ref=card.job_ref or card.task_id,
        task_id=card.task_id,
        flow=card.flow,
        title=card.title,
        task_status=card.status,
        hometime_status=hometime_status,
        priority=card.priority or "normal",
        safe_to_continue=safe_to_continue,
        luke_action_required=luke_needed,
        selected_for_evening=selected,
        reason=reason,
        proof_required=card.proof_required,
        retest_command=card.retest_command,
        stop_condition=_stop_condition(card, hometime_status),
        packet_path=card.packet_path,
        automation_key=automation_key,
        automation_prompt=_automation_prompt(card, automation_key=automation_key, stop_condition=_stop_condition(card, hometime_status)),
    )


def _hometime_status(card: TaskCard) -> str:
    if card.status == "approved":
        return "queued"
    if card.status == "fixed_needs_retest":
        return "waiting_proof"
    if card.status in {"in_progress", "retest_failed", "blocked_needs_luke", "parked", "proved"}:
        return card.status
    return card.status or "queued"


def _selected_for_evening(card: TaskCard, hometime_status: str) -> bool:
    if hometime_status in {"proved"}:
        return False
    text = " ".join([card.job_ref, card.title, card.notes, card.proof_required]).lower()
    if card.flow in {"B", "O", "F", "H"}:
        return True
    priority_clue = any(word in text for word in ("token", "fallback", "trust gate", "scanner", "login", "proof"))
    return priority_clue and hometime_status not in {"proved"}


def _safe_for_hometime(card: TaskCard, policy: HometimePolicy) -> bool:
    if card.flow == "H":
        text = " ".join([card.proof_required, card.retest_command, card.notes, card.allowed_scope]).lower()
        if "pause" in text or "scheduler" in text or "publish" in text:
            return "restore" in text and "proof" in text
        return True
    if card.luke_action_required:
        return False
    text = " ".join([card.title, card.notes, card.allowed_scope, card.proof_required, card.retest_command]).lower()
    if "--approve-protected" in text or "apply" in card.retest_command.lower():
        return False
    if any(word in text for word in ("business decision", "luke decision", "protected approval")):
        return False
    return policy.autonomy_level == "maximum_safe"


def _job_reason(card: TaskCard, hometime_status: str, safe_to_continue: bool, luke_needed: bool) -> str:
    if luke_needed:
        return "Needs Luke because the manager row has a real decision or protected boundary."
    if hometime_status == "parked":
        return "Parked by the manager, so Hometime keeps it visible but quiet."
    if hometime_status == "waiting_proof":
        return "Waiting for the named proof or MOT retest."
    if safe_to_continue:
        return "Safe manager-approved work can continue in Hometime Mode."
    return "Visible for Hometime, but not safe to advance automatically."


def _stop_condition(card: TaskCard, hometime_status: str) -> str:
    if hometime_status == "waiting_proof":
        return "Stop when the named retest proves the task or reopens it with new evidence."
    if hometime_status == "blocked_needs_luke":
        return "Stop until Luke gives the protected decision."
    if hometime_status == "parked":
        return "Stay parked unless new evidence changes the manager status."
    return "Stop when the task is proved, parked, or blocked by a real Luke decision."


def _automation_key(card: TaskCard) -> str:
    safe_ref = re.sub(r"[^a-z0-9]+", "-", (card.job_ref or card.task_id).lower()).strip("-")
    return f"hometime-{safe_ref}"[:80] or "hometime-manager-job"


def _automation_prompt(card: TaskCard, *, automation_key: str, stop_condition: str) -> str:
    return (
        "Act as a SellerOne Hometime child manager for one approved job only. "
        "Read sellerone_manager/MANAGER_CHAT.md, then inspect the approved task packet and manager board rows for "
        f"{card.job_ref or card.task_id}. "
        "Do not run worker cycles, change prices, edit queues, write Sheets, publish, align local DB facts, delete outputs, "
        "restart workers, change scheduler ownership without restore proof, or make business decisions. "
        "Continue only safe manager-approved work inside the packet boundary. "
        f"Retest requirement: {card.retest_command or card.proof_required or 'manager MOT retest'}. "
        f"Stop condition: {stop_condition}. "
        "Email Luke only if a real protected decision is required and the evidence changed."
    )


def _notification_for_job(
    job: HometimeJob,
    *,
    command: str,
    policy: HometimePolicy,
    session_state_exists: bool,
    previous_notifications: list[dict[str, str]],
) -> HometimeNotification:
    message = (
        f"{job.job_ref} needs a decision. "
        f"Codex cannot continue safely because: {job.reason} "
        "If you do nothing, this job will stay parked and Hometime Mode will continue other safe jobs."
    )
    evidence_hash = _evidence_hash(job)
    duplicate = any(row.get("evidence_hash") == evidence_hash for row in previous_notifications)
    first_view_of_session = not previous_notifications and not session_state_exists
    if duplicate:
        status = "suppressed_duplicate"
        suppression_reason = "same blocker already known"
    elif command in {"start", "preflight", "status"} or first_view_of_session:
        status = "preflight_permission_required"
        suppression_reason = "known before evening work starts"
    else:
        status = "pending_codex_email"
        suppression_reason = ""
    return HometimeNotification(
        session_id=job.session_id,
        observed_utc=job.observed_utc,
        job_ref=job.job_ref,
        task_id=job.task_id,
        flow=job.flow,
        notification_type="protected_decision",
        email_to=policy.notification_email,
        email_status=status,
        evidence_hash=evidence_hash,
        subject=f"SellerOne decision needed: {job.job_ref}",
        message=message,
        suppression_reason=suppression_reason,
    )


def _evidence_hash(job: HometimeJob) -> str:
    text = "|".join([job.job_ref, job.task_id, job.hometime_status, job.reason, job.proof_required])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_policy(root: Path) -> HometimePolicy:
    path = root / "config" / "manager" / "hometime_policy.json"
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    return HometimePolicy(
        policy_id=str(data.get("policy_id") or "hometime_mode_manager_v1"),
        status=str(data.get("status") or "active"),
        mode=str(data.get("mode") or "hometime"),
        pulse_minutes=int(data.get("pulse_minutes") or 30),
        finish_rule=str(data.get("finish_rule") or "jobs_settled"),
        autonomy_level=str(data.get("autonomy_level") or "maximum_safe"),
        notification_email=str(data.get("notification_email") or "laprice90@gmail.com"),
        duplicate_email_cooldown_minutes=int(data.get("duplicate_email_cooldown_minutes") or 240),
        allowed_plain_english=tuple(str(item) for item in data.get("allowed_plain_english", [])),
        blocked_plain_english=tuple(str(item) for item in data.get("blocked_plain_english", [])),
    )


def _session_id(root: Path, observed_utc: str) -> str:
    existing = _hometime_output_dir(root) / "hometime_latest.json"
    if existing.exists():
        try:
            data = json.loads(existing.read_text(encoding="utf-8"))
            session_id = str(data.get("session_id") or "")
            if session_id and str(data.get("overall_status") or "") not in {"settled", "stopped"}:
                return session_id
        except json.JSONDecodeError:
            pass
    return "HOMETIME_" + observed_utc[:10].replace("-", "")


def _hometime_output_dir(root: Path) -> Path:
    return root / "out" / "systems" / "M" / "hometime"


def _observed_utc(value: str | None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _result_payload(result: HometimeResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["jobs"] = [_job_row(job) for job in result.jobs]
    payload["notifications"] = [_notification_row(notification) for notification in result.notifications]
    return payload


def _format_hometime_markdown(result: HometimeResult) -> str:
    lines = [
        "# SellerOne Hometime Mode",
        "",
        f"- session_id: {result.session_id}",
        f"- observed_utc: {result.observed_utc}",
        f"- status: {result.overall_status}",
        f"- selected_jobs: {result.selected_job_count}",
        f"- safe_jobs: {result.safe_job_count}",
        f"- blocked_jobs: {result.blocked_job_count}",
        f"- preflight_permissions: {result.preflight_permission_count}",
        f"- email_required: {result.email_required_count}",
        "",
        "## Jobs",
    ]
    if not result.jobs:
        lines.append("- No evening jobs selected.")
    for job in result.jobs:
        safe = "yes" if job.safe_to_continue else "no"
        luke = "yes" if job.luke_action_required else "no"
        lines.append(f"- {job.job_ref}: {job.hometime_status}, safe_to_continue={safe}, luke_needed={luke}. {job.reason}")
    lines.extend(["", "## Notifications"])
    if not result.notifications:
        lines.append("- No email notification needed.")
    for notification in result.notifications:
        lines.append(f"- {notification.job_ref}: {notification.email_status} to {notification.email_to}.")
    lines.append("")
    return "\n".join(lines)


def _write_csv(path: Path, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items() if key is not None} for row in reader]


def _job_row(job: HometimeJob) -> dict[str, Any]:
    row = asdict(job)
    row["safe_to_continue"] = "1" if job.safe_to_continue else "0"
    row["luke_action_required"] = "1" if job.luke_action_required else "0"
    row["selected_for_evening"] = "1" if job.selected_for_evening else "0"
    return row


def _notification_row(notification: HometimeNotification) -> dict[str, str]:
    return asdict(notification)
