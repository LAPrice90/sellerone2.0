from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import get_manager_paths


PLAN_CSV_REL_PATH = Path("sellerone_manager") / "CONTROL" / "AUTOMATION_REBUILD_PLAN.csv"
PLAN_MD_REL_PATH = Path("sellerone_manager") / "CONTROL" / "AUTOMATION_REBUILD.md"
REVIEW_CSV_REL_PATH = Path("sellerone_manager") / "CONTROL" / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv"
PAUSE_PROOF_REL_PATH = Path("sellerone_manager") / "CONTROL" / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv"
REP_BRIEFING_PILOT_REL_PATH = Path("sellerone_manager") / "CONTROL" / "SO21_REP_BRIEFING_PILOT.md"
REP_BRIEFING_ACTIVATION_REL_PATH = Path("sellerone_manager") / "CONTROL" / "SO21_REP_BRIEFING_ACTIVATION.md"

PLAN_COLUMNS = [
    "automation_ref",
    "role",
    "status",
    "cadence",
    "inputs",
    "outputs",
    "allowed_actions",
    "forbidden_actions",
    "source_old_items",
    "activation_gate",
    "reason",
]

PROPOSED_AUTOMATIONS = [
    {
        "automation_ref": "SO21-REP-BRIEFING",
        "role": "Rep briefing",
        "status": "candidate_create_paused",
        "cadence": "twice daily or on demand",
        "inputs": "CONTROL/CURRENT_STATE.md; CONTROL/CURRENT_TICKETS.md; CONTROL/BACKLOG.md; CONTROL/OPERATIONS.md",
        "outputs": "brief user-facing summary only when decisions or material blockers exist",
        "allowed_actions": "read control files; summarize decisions; notify Luke only for real decisions or material change",
        "forbidden_actions": "no worker runs; no scheduler changes; no prices; no queues; no Sheets; no DB writes; no runtime restarts",
        "source_old_items": "sellerone-manager-briefing-github-pulse; sellerone-quiet-daily-log",
        "activation_gate": "Luke approves first pilot automation",
        "reason": "Best first 2.1 automation because it talks through the Rep and reads only control files.",
    },
    {
        "automation_ref": "SO21-HEALTH-WATCHER",
        "role": "Health watcher",
        "status": "candidate_create_paused",
        "cadence": "hourly during working window",
        "inputs": "out/systems/M/mot/; CONTROL/CURRENT_STATE.md; CONTROL/CURRENT_TICKETS.md",
        "outputs": "control summary or notification only for new fail, worsened fail, or Luke decision",
        "allowed_actions": "read MOT evidence; refresh control summaries; report material health changes",
        "forbidden_actions": "no MOT repair; no worker runs; no task starts; no scheduler changes; no business writes",
        "source_old_items": "sellerboard-daily-email-mot-intake; o-net-fee-restock-mot-check; AMZ Morning MOT Post A; AMZ Morning MOT Post Restart",
        "activation_gate": "Rep briefing proves useful or Luke explicitly approves health watcher pilot",
        "reason": "Useful, but old MOT repair behavior must not return.",
    },
    {
        "automation_ref": "SO21-REVIEW-WATCHER",
        "role": "Reviewer",
        "status": "candidate_deferred",
        "cadence": "triggered by review-ready ticket state",
        "inputs": "CONTROL/CURRENT_TICKETS.md; approved task packet proof routes",
        "outputs": "review summary and proof status only",
        "allowed_actions": "read diffs and proof outputs; summarize review findings",
        "forbidden_actions": "no code edits; no worker runs; no protected actions",
        "source_old_items": "daily-f-ai-review-queue-manager; f032-codex-ai-review-gate",
        "activation_gate": "Queue exposes a stable review-ready state",
        "reason": "Correct role, but needs a clean review state before automation.",
    },
    {
        "automation_ref": "SO21-STORAGE-CUSTODIAN",
        "role": "Custodian",
        "status": "candidate_create_paused",
        "cadence": "weekly",
        "inputs": "CONTROL/STORAGE_POLICY.md; CONTROL/STORAGE_INDEX*.csv; CONTROL/CUSTODIAN_DRY_RUN_MANIFEST.csv",
        "outputs": "storage pressure summary and cleanup ticket recommendations only",
        "allowed_actions": "measure storage; write reports; propose cleanup manifests",
        "forbidden_actions": "no deletion; no move; no compression; no purge; no archive apply without explicit approval",
        "source_old_items": "none",
        "activation_gate": "Luke approves storage reporting automation after Rep briefing pilot",
        "reason": "Prevents future storage drift without allowing destructive cleanup.",
    },
    {
        "automation_ref": "SO21-USAGE-REPORTER",
        "role": "Custodian",
        "status": "candidate_create_paused",
        "cadence": "weekly",
        "inputs": "CONTROL/AI_USAGE.csv; CONTROL/AI_USAGE.md; automation review evidence",
        "outputs": "usage-pressure summary only",
        "allowed_actions": "read usage-pressure report; summarize high-risk loops",
        "forbidden_actions": "no billing claims; no automation restarts; no task starts; no runtime changes",
        "source_old_items": "sellerone-quiet-daily-log",
        "activation_gate": "Luke approves after first briefing pilot",
        "reason": "Keeps AI pressure visible without pretending to know real billing cost.",
    },
]


@dataclass(frozen=True)
class AutomationRebuildPlanResult:
    csv_path: Path
    markdown_path: Path
    rows: list[dict[str, str]]
    markdown: str
    generated_utc: str
    proposed_count: int
    deferred_count: int
    created_paused_count: int
    active_pilot_count: int
    retired_old_count: int
    active_old_count: int
    windows_ready_count: int
    recommended_next_task: str


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_automation_rebuild_plan(
    *,
    root: Path | str | None = None,
    generated_utc: str | None = None,
) -> AutomationRebuildPlanResult:
    paths = get_manager_paths(root)
    generated = generated_utc or utc_now_text()
    control_dir = paths.root / "sellerone_manager" / "CONTROL"
    review_rows = _read_csv_rows(paths.root / REVIEW_CSV_REL_PATH)
    pause_rows = _read_csv_rows(paths.root / PAUSE_PROOF_REL_PATH)

    rows = [dict(row) for row in PROPOSED_AUTOMATIONS]
    pilot_created = (paths.root / REP_BRIEFING_PILOT_REL_PATH).exists()
    pilot_active = (paths.root / REP_BRIEFING_ACTIVATION_REL_PATH).exists()
    if pilot_created:
        for row in rows:
            if row.get("automation_ref") == "SO21-REP-BRIEFING":
                if pilot_active:
                    row["status"] = "active_pilot"
                    row["activation_gate"] = "First scheduled briefing run proves the pilot"
                    row["reason"] = "First 2.1 automation pilot is active under the approved Rep briefing boundary."
                else:
                    row["status"] = "created_paused"
                    row["activation_gate"] = "Luke explicitly approves activation after reviewing the paused pilot"
                    row["reason"] = "First 2.1 automation shell exists and remains paused until activation approval."
    status_counts = Counter(row.get("status", "") for row in rows)
    old_sellerone_rows = [
        row
        for row in review_rows
        if row.get("source_type") == "codex_automation" and row.get("sellerone_scope") == "sellerone"
        and not _is_new_so21_automation(row)
    ]
    active_old_count = sum(1 for row in old_sellerone_rows if row.get("status") == "ACTIVE")
    retired_old_count = sum(1 for row in old_sellerone_rows if row.get("recommendation", "").startswith("retire"))
    windows_ready_count = sum(1 for row in pause_rows if row.get("after_state") == "Ready")
    recommended_next = (
        "SO21-WINDOWS-SCHEDULER-ADMIN-PAUSE"
        if windows_ready_count
        else
        "SO21-REP-BRIEFING-FIRST-RUN-PROOF"
        if pilot_active
        else "SO21-AUTOMATION-ACTIVATION-DECISION"
    )
    markdown = _build_markdown(
        generated_utc=generated,
        rows=rows,
        review_rows=review_rows,
        pause_rows=pause_rows,
        status_counts=status_counts,
        active_old_count=active_old_count,
        retired_old_count=retired_old_count,
        windows_ready_count=windows_ready_count,
        recommended_next=recommended_next,
    )
    return AutomationRebuildPlanResult(
        csv_path=paths.root / PLAN_CSV_REL_PATH,
        markdown_path=paths.root / PLAN_MD_REL_PATH,
        rows=rows,
        markdown=markdown,
        generated_utc=generated,
        proposed_count=status_counts.get("candidate_create_paused", 0),
        deferred_count=status_counts.get("candidate_deferred", 0),
        created_paused_count=status_counts.get("created_paused", 0),
        active_pilot_count=status_counts.get("active_pilot", 0),
        retired_old_count=retired_old_count,
        active_old_count=active_old_count,
        windows_ready_count=windows_ready_count,
        recommended_next_task=recommended_next,
    )


def write_automation_rebuild_plan(
    *,
    root: Path | str | None = None,
    generated_utc: str | None = None,
) -> AutomationRebuildPlanResult:
    result = build_automation_rebuild_plan(root=root, generated_utc=generated_utc)
    result.csv_path.parent.mkdir(parents=True, exist_ok=True)
    with result.csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAN_COLUMNS)
        writer.writeheader()
        for row in result.rows:
            writer.writerow({column: row.get(column, "") for column in PLAN_COLUMNS})
    result.markdown_path.write_text(result.markdown, encoding="utf-8")
    return result


def format_automation_rebuild_plan_status(result: AutomationRebuildPlanResult) -> str:
    return "\n".join(
        [
            "status=written",
            f"csv_path={result.csv_path}",
            f"markdown_path={result.markdown_path}",
            f"generated_utc={result.generated_utc}",
            f"candidate_create_paused={result.proposed_count}",
            f"candidate_deferred={result.deferred_count}",
            f"created_paused={result.created_paused_count}",
            f"active_pilot={result.active_pilot_count}",
            f"retired_old_automations={result.retired_old_count}",
            f"active_old_automations={result.active_old_count}",
            f"windows_ready_after_pause={result.windows_ready_count}",
            f"recommended_next_task={result.recommended_next_task}",
        ]
    )


def _build_markdown(
    *,
    generated_utc: str,
    rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    pause_rows: list[dict[str, str]],
    status_counts: Counter[str],
    active_old_count: int,
    retired_old_count: int,
    windows_ready_count: int,
    recommended_next: str,
) -> str:
    codex_count = sum(1 for row in review_rows if row.get("source_type") == "codex_automation")
    windows_disabled_count = sum(1 for row in pause_rows if row.get("after_state") == "Disabled")
    created_paused_count = status_counts.get("created_paused", 0)
    active_pilot_count = status_counts.get("active_pilot", 0)
    lines = [
        "# SellerOne Automation Rebuild Plan",
        "",
        "Job: `SO21-AUTOMATION-REBUILD`",
        f"Generated UTC: {generated_utc}",
        "Generated by: `sellerone_manager.automation_rebuild_plan`",
        "",
        "## Plain-English Status",
        "",
        (
            "SellerOne 2.1 should not resume the old automation pile. "
            "This plan replaces old cycle heartbeats and repair schedulers with a smaller reviewable set."
        ),
        "",
        "- Automations activated by this plan: 0",
        "- Runtime or business actions performed: 0",
        f"- Codex automations found in review: {codex_count}",
        f"- Old active SellerOne Codex automations: {active_old_count}",
        f"- Old SellerOne automations marked retire/do-not-resume: {retired_old_count}",
        f"- Windows scheduled tasks disabled in pause proof: {windows_disabled_count}",
        f"- Windows scheduled tasks still ready after pause: {windows_ready_count}",
        f"- Candidate automations to create paused: {status_counts.get('candidate_create_paused', 0)}",
        f"- Paused pilot automations already created: {created_paused_count}",
        f"- Active approved pilot automations: {active_pilot_count}",
        f"- Candidate automations deferred: {status_counts.get('candidate_deferred', 0)}",
        f"- Recommended next task: `{recommended_next}`",
        "",
        "## Proposed 2.1 Automation Set",
        "",
    ]
    lines.extend(_format_plan_rows(rows))
    lines.extend(
        [
            "",
            "## Rebuild Rules",
            "",
            "- Create new 2.1 automations paused first; do not resume old automation IDs blindly.",
            "- Pilot one automation first: `SO21-REP-BRIEFING`.",
            "- Do not re-enable Windows scheduled tasks during this automation rebuild.",
            "- No automation may run worker cycles, change prices, edit queues, write Sheets, align databases, delete outputs, or touch Amazon security.",
            "- Every automation must read control artifacts and either write a control summary or notify only for a real decision/material change.",
            "- If an automation would need protected powers, it becomes a ticket, not an automation.",
            "",
            "## Retired Or Rebuilt Old Items",
            "",
        ]
    )
    old_sellerone = [
        row
        for row in review_rows
        if row.get("source_type") == "codex_automation" and row.get("sellerone_scope") == "sellerone"
        and not _is_new_so21_automation(row)
    ]
    if not old_sellerone:
        lines.append("No old SellerOne Codex automations were visible.")
    else:
        lines.extend(_format_old_rows(old_sellerone))
    lines.extend(
        [
            "",
            "## Activation Decision",
            "",
            (
                "The safe next decision is whether to activate the paused `SO21-REP-BRIEFING` pilot for its first scheduled briefing run."
                if created_paused_count
                else "The safe next step is to let the active `SO21-REP-BRIEFING` pilot produce its first scheduled briefing, then review the result."
                if active_pilot_count
                else "The safe next decision is whether to create `SO21-REP-BRIEFING` as a paused Codex automation proposal, then activate it as the first pilot only after Luke confirms the exact behavior."
            ),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _format_plan_rows(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Automation | Role | Status | Cadence | Activation Gate |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_code(row["automation_ref"]),
                    _md(row["role"]),
                    _md(row["status"]),
                    _md(row["cadence"]),
                    _md(row["activation_gate"]),
                ]
            )
            + " |"
        )
    return lines


def _is_new_so21_automation(row: dict[str, str]) -> bool:
    value = f"{row.get('item_id', '')} {row.get('name', '')}".lower()
    return "so21-" in value


def _format_old_rows(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Old Item | Status | Recommendation | Reason |", "|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_code(row.get("item_id", "")),
                    _md(row.get("status", "")),
                    _md(row.get("recommendation", "")),
                    _md(_short(row.get("reason", ""), 120)),
                ]
            )
            + " |"
        )
    return lines


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _text(value: object) -> str:
    return str(value or "").strip()


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
