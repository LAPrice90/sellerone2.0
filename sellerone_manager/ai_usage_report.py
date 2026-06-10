from __future__ import annotations

import csv
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import get_manager_paths


AI_USAGE_CSV_REL_PATH = Path("sellerone_manager") / "CONTROL" / "AI_USAGE.csv"
AI_USAGE_MD_REL_PATH = Path("sellerone_manager") / "CONTROL" / "AI_USAGE.md"

AI_USAGE_COLUMNS = [
    "observed_utc",
    "scope",
    "job_ref",
    "source",
    "status",
    "usage_signal",
    "risk_level",
    "measurement",
    "actual_cost_available",
    "reason",
    "next_action",
]

ACTIVE_STATUSES = {"approved", "in_progress", "fixed_needs_retest", "retest_failed", "reopened"}


@dataclass(frozen=True)
class AIUsageReportResult:
    csv_path: Path
    markdown_path: Path
    rows: list[dict[str, str]]
    markdown: str
    observed_utc: str
    high_risk_count: int
    medium_risk_count: int
    actual_cost_available: bool
    recommended_next_task: str


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_ai_usage_report(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    automation_root: Path | str | None = None,
) -> AIUsageReportResult:
    paths = get_manager_paths(root)
    observed = observed_utc or utc_now_text()
    control_dir = paths.root / "sellerone_manager" / "CONTROL"
    packet_rows = _read_csv_rows(paths.output_dir / "approved_task_packets.csv")
    mot_summary = _read_mot_summary(paths.output_dir / "mot")
    automation_summary = _read_automation_summary(automation_root)

    active_rows = [
        row for row in packet_rows if row.get("status") in ACTIVE_STATUSES and _text(row.get("luke_action_required")) != "1"
    ]
    waiting_proof_rows = [row for row in active_rows if row.get("status") == "fixed_needs_retest"]
    blocked_rows = [row for row in packet_rows if row.get("status") == "blocked_needs_luke" or _text(row.get("luke_action_required")) == "1"]
    parked_rows = [row for row in packet_rows if row.get("status") == "parked" and _text(row.get("luke_action_required")) != "1"]

    rows: list[dict[str, str]] = []
    rows.append(
        _row(
            observed,
            scope="accounting",
            job_ref="AI-USAGE-RAW-COST-DATA",
            source="control_files",
            status="missing",
            usage_signal="real_token_or_billing_source_missing",
            risk_level="medium",
            measurement="actual_cost=not_available",
            actual_cost_available="no",
            reason="No local SellerOne 2.1 billing or token-spend source is configured. This report is usage-pressure visibility, not a bill.",
            next_action="Create a real billing/token source before treating AI usage as financial cost.",
        )
    )
    rows.append(
        _row(
            observed,
            scope="queue",
            job_ref="ALL-ACTIVE-TICKETS",
            source="approved_task_packets.csv",
            status="visible",
            usage_signal="active_non_luke_ticket_count",
            risk_level=_risk_for_count(len(active_rows), high=10, medium=4),
            measurement=f"active_tickets={len(active_rows)}",
            actual_cost_available="no",
            reason="Each active ticket can generate AI work, tests, review, and MOT proof.",
            next_action="Work from CURRENT_TICKETS.md and avoid opening duplicate chats for the same job_ref.",
        )
    )
    rows.append(
        _row(
            observed,
            scope="queue",
            job_ref="ALL-BLOCKED-TICKETS",
            source="approved_task_packets.csv",
            status="blocked",
            usage_signal="blocked_luke_decision_count",
            risk_level=_risk_for_count(len(blocked_rows), high=6, medium=2),
            measurement=f"blocked_tickets={len(blocked_rows)}",
            actual_cost_available="no",
            reason="Blocked tickets can waste AI time if workers keep investigating without a Luke decision.",
            next_action="Keep blocked work in BACKLOG.md until Luke approves the named protected choice.",
        )
    )
    rows.append(
        _row(
            observed,
            scope="queue",
            job_ref="ALL-PARKED-TICKETS",
            source="approved_task_packets.csv",
            status="parked",
            usage_signal="parked_ticket_count",
            risk_level=_risk_for_count(len(parked_rows), high=12, medium=5),
            measurement=f"parked_tickets={len(parked_rows)}",
            actual_cost_available="no",
            reason="Parked tickets should not keep generating chat or proof attempts until their trigger changes.",
            next_action="Keep parked work in BACKLOG.md and avoid routine progress chatter.",
        )
    )
    for row in sorted(waiting_proof_rows, key=lambda item: _text(item.get("job_ref")))[:8]:
        job_ref = _text(row.get("job_ref")) or _text(row.get("task_id"))
        title = _text(row.get("title")).upper()
        rows.append(
            _row(
                observed,
                scope="proof",
                job_ref=job_ref,
                source="approved_task_packets.csv",
                status="waiting_proof",
                usage_signal="retest_or_monitoring_loop",
                risk_level="high" if "F-" in job_ref and ("LOGIN" in title or "SESSION" in title) else "medium",
                measurement=f"status={_text(row.get('status'))}",
                actual_cost_available="no",
                reason="Waiting-proof work can create repeated AI monitoring unless the proof condition is bounded.",
                next_action="Use the named proof route and stop if the proof window is unavailable.",
            )
        )

    rows.append(
        _row(
            observed,
            scope="mot",
            job_ref="MOT-PRESSURE",
            source="out/systems/M/mot",
            status=mot_summary["status"],
            usage_signal="fail_warn_decision_count",
            risk_level=_mot_risk(mot_summary),
            measurement=(
                f"fails={mot_summary['fail_count']};warnings={mot_summary['warn_count']};"
                f"decisions={mot_summary['decision_count']};not_checked={mot_summary['not_checked_count']}"
            ),
            actual_cost_available="no",
            reason="High MOT pressure can create repeated manager and worker prompts if not converted into bounded packets.",
            next_action="Use MOT rows only as candidates until they are promoted into approved packets.",
        )
    )

    active_automations = automation_summary["active_count"]
    rows.append(
        _row(
            observed,
            scope="automation",
            job_ref="CODEX-AUTOMATIONS",
            source="Codex automation definitions",
            status="paused" if active_automations == 0 else "active",
            usage_signal="active_automation_count",
            risk_level="low" if active_automations == 0 else "high",
            measurement=f"active={active_automations};paused={automation_summary['paused_count']};total={automation_summary['total_count']}",
            actual_cost_available="no",
            reason="Active automations can spend AI in the background. Paused automations are no immediate spend risk.",
            next_action="Rebuild only specific automations after the 2.1 automation policy is approved.",
        )
    )

    rows.extend(_instruction_memory_rows(paths.root, observed))
    rows.extend(_control_backlog_rows(control_dir, observed))

    high_count = sum(1 for row in rows if row["risk_level"] == "high")
    medium_count = sum(1 for row in rows if row["risk_level"] == "medium")
    recommended_next = _recommended_next(rows, control_dir=control_dir)
    markdown = _build_markdown(
        observed_utc=observed,
        rows=rows,
        high_count=high_count,
        medium_count=medium_count,
        recommended_next=recommended_next,
        actual_cost_available=False,
    )
    return AIUsageReportResult(
        csv_path=paths.root / AI_USAGE_CSV_REL_PATH,
        markdown_path=paths.root / AI_USAGE_MD_REL_PATH,
        rows=rows,
        markdown=markdown,
        observed_utc=observed,
        high_risk_count=high_count,
        medium_risk_count=medium_count,
        actual_cost_available=False,
        recommended_next_task=recommended_next,
    )


def write_ai_usage_report(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    automation_root: Path | str | None = None,
) -> AIUsageReportResult:
    result = build_ai_usage_report(root=root, observed_utc=observed_utc, automation_root=automation_root)
    result.csv_path.parent.mkdir(parents=True, exist_ok=True)
    with result.csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=AI_USAGE_COLUMNS)
        writer.writeheader()
        for row in result.rows:
            writer.writerow({column: row.get(column, "") for column in AI_USAGE_COLUMNS})
    result.markdown_path.write_text(result.markdown, encoding="utf-8")
    return result


def format_ai_usage_report_status(result: AIUsageReportResult) -> str:
    return "\n".join(
        [
            "status=written",
            f"csv_path={result.csv_path}",
            f"markdown_path={result.markdown_path}",
            f"observed_utc={result.observed_utc}",
            f"rows={len(result.rows)}",
            f"high_risk={result.high_risk_count}",
            f"medium_risk={result.medium_risk_count}",
            f"actual_cost_available={'yes' if result.actual_cost_available else 'no'}",
            f"recommended_next_task={result.recommended_next_task}",
        ]
    )


def _build_markdown(
    *,
    observed_utc: str,
    rows: list[dict[str, str]],
    high_count: int,
    medium_count: int,
    recommended_next: str,
    actual_cost_available: bool,
) -> str:
    sorted_rows = sorted(rows, key=_row_sort_key)
    lines = [
        "# SellerOne AI Usage Report",
        "",
        "Job: `SO21-AI-USAGE-REPORT`",
        f"Generated UTC: {observed_utc}",
        "Generated by: `sellerone_manager.ai_usage_report`",
        "",
        "## Plain-English Status",
        "",
        (
            "SellerOne does not yet have real AI billing or token-spend data connected to the control desk. "
            "This report tracks usage pressure: the places most likely to burn AI time if they are allowed to loop."
        ),
        "",
        f"- Actual AI cost available: {'yes' if actual_cost_available else 'no'}",
        f"- High-risk usage-pressure signals: {high_count}",
        f"- Medium-risk usage-pressure signals: {medium_count}",
        f"- Recommended next task: `{recommended_next}`",
        "",
        "## Highest Risk Signals",
        "",
    ]
    high_rows = [row for row in sorted_rows if row["risk_level"] == "high"]
    if not high_rows:
        lines.append("No high-risk usage-pressure signals are visible.")
    else:
        lines.extend(_format_rows(high_rows[:8]))
    lines.extend(["", "## Full Usage-Pressure Register", ""])
    lines.extend(_format_rows(sorted_rows))
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- This is not a billing statement.",
            "- Do not infer pounds, dollars, or model cost from this file.",
            "- Stock-token and token-ledger business data is deliberately excluded from AI usage accounting.",
            "- Use this report to reduce duplicate chats, repeated proof loops, oversized instruction memory, and unnecessary automations.",
            "- Do not restart automations from this report. Automation rebuild needs its own approved task.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _format_rows(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Scope | Job | Risk | Signal | Measurement | Next Action |", "|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(row["scope"]),
                    _md_code(row["job_ref"]),
                    _md(row["risk_level"]),
                    _md(row["usage_signal"]),
                    _md(row["measurement"]),
                    _md(_short(row["next_action"], 120)),
                ]
            )
            + " |"
        )
    return lines


def _instruction_memory_rows(root: Path, observed_utc: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    prompt_folders_archived = (root / "sellerone_manager" / "CONTROL" / "PROMPT_FOLDER_ARCHIVE.md").exists()
    file_targets = [
        root / "sellerone_manager" / "CODING_PLAN.md",
        root / "sellerone_manager" / "MANAGER_CHAT.md",
        root / "sellerone_manager" / "MANAGER_PROGRESS_TRACKER.md",
    ]
    for path in file_targets:
        if not path.exists():
            continue
        size = path.stat().st_size
        if size < 10_000:
            continue
        rows.append(
            _row(
                observed_utc,
                scope="instruction_memory",
                job_ref=_path_job_ref(path),
                source=str(path.relative_to(root)),
                status="large_file",
                usage_signal="large_instruction_context",
                risk_level="high" if size >= 50_000 else "medium",
                measurement=f"bytes={size}",
                actual_cost_available="no",
                reason="Large instruction files increase context load and make future chats slower and noisier.",
                next_action="Archive or trim after the 2.1 control files preserve the current truth.",
            )
        )
    directory_targets = [
        root / "plans",
        root / "sellerone_manager" / "thread_prompts",
        root / "sellerone_manager" / "agent_launch_prompts",
        root / "sellerone_manager" / "thread_starters",
        root / "sellerone_manager" / "project_threads",
        root / "sellerone_manager" / "goals",
    ]
    for path in directory_targets:
        if not path.exists():
            continue
        files = [item for item in path.rglob("*") if item.is_file()]
        total_bytes = sum(item.stat().st_size for item in files)
        if not files:
            continue
        raw_risk = "high" if total_bytes >= 10_000_000 or len(files) >= 250 else "medium" if len(files) >= 5 else "low"
        risk = "low" if prompt_folders_archived else raw_risk
        rows.append(
            _row(
                observed_utc,
                scope="instruction_memory",
                job_ref=_path_job_ref(path),
                source=str(path.relative_to(root)),
                status="template_or_history" if prompt_folders_archived else "legacy_context",
                usage_signal="archived_prompt_or_plan_folder" if prompt_folders_archived else "legacy_prompt_or_plan_folder",
                risk_level=risk,
                measurement=f"files={len(files)};bytes={total_bytes}",
                actual_cost_available="no",
                reason=(
                    "Prompt and plan folders are marked as history/template material, so they should not create active AI work."
                    if prompt_folders_archived
                    else "Legacy plans and prompt folders can cause duplicated AI work when treated as live instructions."
                ),
                next_action=(
                    "Convert useful patterns into skill specs; keep these folders out of the active queue."
                    if prompt_folders_archived
                    else "Mark as template/history or archive after current work is captured in CONTROL files."
                ),
            )
        )
    return rows


def _control_backlog_rows(control_dir: Path, observed_utc: str) -> list[dict[str, str]]:
    backlog_path = control_dir / "BACKLOG.md"
    if not backlog_path.exists():
        return []
    text = backlog_path.read_text(encoding="utf-8", errors="ignore")
    control_count = text.count("| `SO21-")
    return [
        _row(
            observed_utc,
            scope="control_backlog",
            job_ref="SO21-CONTROL-BACKLOG",
            source="CONTROL/BACKLOG.md",
            status="visible",
            usage_signal="control_backlog_item_count",
            risk_level=_risk_for_count(control_count, high=10, medium=4),
            measurement=f"control_backlog_items={control_count}",
            actual_cost_available="no",
            reason="Control backlog items are useful, but too many simultaneous control tasks can create scattered AI work.",
            next_action="Work one 2.1 control task at a time and update CURRENT_STATE.md after each.",
        )
    ]


def _read_mot_summary(mot_dir: Path) -> dict[str, str]:
    payload = _read_json(mot_dir / "mot_latest.json")
    if payload:
        return {
            "status": _text(payload.get("status")) or "unknown",
            "fail_count": _int_text(payload.get("fail_count")),
            "warn_count": _int_text(payload.get("warn_count")),
            "decision_count": _int_text(payload.get("decision_count")),
            "not_checked_count": _int_text(payload.get("not_checked_count")),
        }
    rows = _read_csv_rows(mot_dir / "mot_latest.csv")
    counts = Counter(row.get("status", "missing") for row in rows)
    decisions = counts.get("decision_needed", 0) + sum(1 for row in rows if row.get("luke_action_required") == "1")
    return {
        "status": "missing" if not rows else "from_csv",
        "fail_count": str(counts.get("fail", 0)),
        "warn_count": str(counts.get("warn", 0)),
        "decision_count": str(decisions),
        "not_checked_count": str(counts.get("not_checked", 0)),
    }


def _read_automation_summary(automation_root: Path | str | None) -> dict[str, int]:
    root = _resolve_automation_root(automation_root)
    statuses: list[str] = []
    if root and root.exists():
        for path in sorted(root.rglob("automation.toml")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            statuses.append(_toml_field(text, "status") or "unknown")
    counts = Counter(statuses)
    return {
        "total_count": len(statuses),
        "active_count": counts.get("ACTIVE", 0),
        "paused_count": counts.get("PAUSED", 0),
    }


def _resolve_automation_root(automation_root: Path | str | None) -> Path | None:
    if automation_root is not None:
        return Path(automation_root)
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "automations"
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return Path(user_profile) / ".codex" / "automations"
    return None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _toml_field(text: str, field: str) -> str:
    prefix = f"{field} = "
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip().strip('"')
    return ""


def _row(
    observed_utc: str,
    *,
    scope: str,
    job_ref: str,
    source: str,
    status: str,
    usage_signal: str,
    risk_level: str,
    measurement: str,
    actual_cost_available: str,
    reason: str,
    next_action: str,
) -> dict[str, str]:
    return {
        "observed_utc": observed_utc,
        "scope": scope,
        "job_ref": job_ref,
        "source": source,
        "status": status,
        "usage_signal": usage_signal,
        "risk_level": risk_level,
        "measurement": measurement,
        "actual_cost_available": actual_cost_available,
        "reason": reason,
        "next_action": next_action,
    }


def _risk_for_count(count: int, *, high: int, medium: int) -> str:
    if count >= high:
        return "high"
    if count >= medium:
        return "medium"
    return "low"


def _mot_risk(summary: dict[str, str]) -> str:
    fails = int(summary["fail_count"] or "0")
    warnings = int(summary["warn_count"] or "0")
    decisions = int(summary["decision_count"] or "0")
    if fails >= 5 or warnings >= 20 or decisions >= 3:
        return "high"
    if fails or warnings >= 5 or decisions:
        return "medium"
    return "low"


def _recommended_next(rows: list[dict[str, str]], *, control_dir: Path) -> str:
    by_job = {row["job_ref"]: row for row in rows}
    coding_plan = by_job.get("CODING-PLAN")
    if coding_plan and coding_plan["risk_level"] == "high":
        return "SO21-CODING-PLAN-ARCHIVE"
    plans = by_job.get("PLANS")
    if plans and plans["risk_level"] == "high":
        return "SO21-PROMPT-FOLDER-ARCHIVE"
    for job_ref in ("MANAGER-CHAT", "MANAGER-PROGRESS-TRACKER"):
        row = by_job.get(job_ref)
        if row and row["risk_level"] in {"high", "medium"}:
            return "SO21-ROLE-FILE-TRIM"
    if not (control_dir / "SKILL_SPECS.md").exists():
        return "SO21-SKILL-SPECS"
    if _storage_index_out_subtree_needed(control_dir):
        return "SO21-STORAGE-INDEX-OUT-SUBTREE"
    if _custodian_dry_run_manifest_needed(control_dir):
        return "SO21-CUSTODIAN-DRY-RUN-MANIFEST"
    if _dead_automation_and_scheduler_review_needed(control_dir):
        return "SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW"
    if _windows_scheduler_admin_pause_needed(control_dir):
        return "SO21-WINDOWS-SCHEDULER-ADMIN-PAUSE"
    if _windows_scheduler_pause_decision_needed(control_dir):
        return "SO21-WINDOWS-SCHEDULER-PAUSE-DECISION"
    if _automation_rebuild_needed(control_dir):
        return "SO21-AUTOMATION-REBUILD"
    if _automation_activation_decision_needed(control_dir):
        return "SO21-AUTOMATION-ACTIVATION-DECISION"
    if _rep_briefing_first_run_proof_needed(control_dir):
        return "SO21-REP-BRIEFING-FIRST-RUN-PROOF"
    return "SO21-GIT-SYSTEM-CATCH-UP"


def _storage_index_out_subtree_needed(control_dir: Path) -> bool:
    path = control_dir / "STORAGE_INDEX.csv"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return "needs out subtree index" in text or "needs out/ subtree index" in text


def _custodian_dry_run_manifest_needed(control_dir: Path) -> bool:
    return not (
        (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.csv").exists()
        or (control_dir / "CUSTODIAN_DRY_RUN_MANIFEST.md").exists()
    )


def _dead_automation_and_scheduler_review_needed(control_dir: Path) -> bool:
    return not (control_dir / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md").exists()


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


def _row_sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    risk_order = {"high": 0, "medium": 1, "low": 2}
    return (risk_order.get(row["risk_level"], 9), row["scope"], row["job_ref"])


def _path_job_ref(path: Path) -> str:
    stem = path.stem if path.is_file() else path.name
    return stem.upper().replace("_", "-").replace(" ", "-")


def _text(value: object) -> str:
    return str(value or "").strip()


def _int_text(value: object) -> str:
    try:
        return str(int(value or 0))
    except (TypeError, ValueError):
        return "0"


def _short(value: str, limit: int) -> str:
    cleaned = " ".join(_text(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _md(value: str) -> str:
    return _text(value).replace("|", "\\|")


def _md_code(value: str) -> str:
    safe = _md(value).replace("`", "")
    return f"`{safe}`" if safe else "`unknown`"
