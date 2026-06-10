from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import get_manager_paths


REVIEW_CSV_REL_PATH = Path("sellerone_manager") / "CONTROL" / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv"
REVIEW_MD_REL_PATH = Path("sellerone_manager") / "CONTROL" / "DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md"
SCHEDULER_DECISION_REL_PATH = Path("sellerone_manager") / "CONTROL" / "WINDOWS_SCHEDULER_PAUSE_DECISION.md"
AUTOMATION_REBUILD_MD_REL_PATH = Path("sellerone_manager") / "CONTROL" / "AUTOMATION_REBUILD.md"
REP_BRIEFING_ACTIVATION_REL_PATH = Path("sellerone_manager") / "CONTROL" / "SO21_REP_BRIEFING_ACTIVATION.md"

REVIEW_COLUMNS = [
    "source_type",
    "item_id",
    "name",
    "status",
    "kind",
    "target",
    "sellerone_scope",
    "recommendation",
    "luke_decision_required",
    "reason",
]

SELLERONE_AUTOMATION_HINTS = [
    "so21",
    "sellerone",
    "sellerboard",
    "f-scanner",
    "f032",
    "daily-f",
    "monday-restocking",
    "o-h-maintenance",
    "o-net-fee",
]

REPO_SCHEDULER_ENTRYPOINTS = [
    Path("sellerone_manager") / "install_manager_hourly_mot_task.ps1",
    Path("scripts") / "tools" / "install_h_maintenance_controller.ps1",
    Path("run_manager_hourly_mot.bat"),
    Path("run_morning_mot_system.bat"),
    Path("run_F_price_list_manager_cycle.bat"),
    Path("run_H_maintenance_controller_install.bat"),
]


@dataclass(frozen=True)
class DeadAutomationSchedulerReviewResult:
    csv_path: Path
    markdown_path: Path
    rows: list[dict[str, str]]
    markdown: str
    generated_utc: str
    codex_automation_count: int
    active_codex_automation_count: int
    paused_codex_automation_count: int
    windows_scheduler_count: int
    ready_windows_scheduler_count: int
    scheduler_pause_decision_required: bool
    recommended_next_task: str


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_dead_automation_scheduler_review(
    *,
    root: Path | str | None = None,
    generated_utc: str | None = None,
    automation_root: Path | str | None = None,
    scheduler_snapshot_path: Path | str | None = None,
    scheduler_rows: list[dict[str, str]] | None = None,
) -> DeadAutomationSchedulerReviewResult:
    paths = get_manager_paths(root)
    generated = generated_utc or utc_now_text()
    control_dir = paths.root / "sellerone_manager" / "CONTROL"
    automation_path = _resolve_automation_root(automation_root)
    scheduler_source_rows = (
        scheduler_rows
        if scheduler_rows is not None
        else _read_scheduler_snapshot(scheduler_snapshot_path)
        if scheduler_snapshot_path is not None
        else _query_windows_schedulers()
    )

    rows: list[dict[str, str]] = []
    rows.extend(_codex_automation_rows(automation_path, control_dir=control_dir))
    rows.extend(_windows_scheduler_rows(scheduler_source_rows))
    rows.extend(_repo_scheduler_entrypoint_rows(paths.root))

    counts = Counter(row["source_type"] for row in rows)
    codex_rows = [row for row in rows if row["source_type"] == "codex_automation"]
    windows_rows = [row for row in rows if row["source_type"] == "windows_scheduler"]
    scheduler_pause_decision_required = any(
        row["source_type"] == "windows_scheduler" and row["luke_decision_required"] == "yes" for row in rows
    ) and not (control_dir / SCHEDULER_DECISION_REL_PATH.name).exists()
    admin_pause_required = _windows_scheduler_admin_pause_needed(control_dir)
    recommended_next = (
        "SO21-WINDOWS-SCHEDULER-ADMIN-PAUSE"
        if admin_pause_required
        else
        "SO21-WINDOWS-SCHEDULER-PAUSE-DECISION"
        if scheduler_pause_decision_required
        else
        "SO21-REP-BRIEFING-FIRST-RUN-PROOF"
        if (control_dir / REP_BRIEFING_ACTIVATION_REL_PATH.name).exists()
        else
        "SO21-AUTOMATION-ACTIVATION-DECISION"
        if (control_dir / AUTOMATION_REBUILD_MD_REL_PATH.name).exists()
        else "SO21-AUTOMATION-REBUILD"
    )
    markdown = _build_markdown(
        generated_utc=generated,
        rows=rows,
        source_counts=counts,
        codex_rows=codex_rows,
        windows_rows=windows_rows,
        control_dir=control_dir,
        scheduler_pause_decision_required=scheduler_pause_decision_required,
        admin_pause_required=admin_pause_required,
        recommended_next=recommended_next,
    )
    return DeadAutomationSchedulerReviewResult(
        csv_path=paths.root / REVIEW_CSV_REL_PATH,
        markdown_path=paths.root / REVIEW_MD_REL_PATH,
        rows=rows,
        markdown=markdown,
        generated_utc=generated,
        codex_automation_count=len(codex_rows),
        active_codex_automation_count=sum(1 for row in codex_rows if row["status"] == "ACTIVE"),
        paused_codex_automation_count=sum(1 for row in codex_rows if row["status"] == "PAUSED"),
        windows_scheduler_count=len(windows_rows),
        ready_windows_scheduler_count=sum(1 for row in windows_rows if row["status"].lower() == "ready"),
        scheduler_pause_decision_required=scheduler_pause_decision_required,
        recommended_next_task=recommended_next,
    )


def write_dead_automation_scheduler_review(
    *,
    root: Path | str | None = None,
    generated_utc: str | None = None,
    automation_root: Path | str | None = None,
    scheduler_snapshot_path: Path | str | None = None,
) -> DeadAutomationSchedulerReviewResult:
    result = build_dead_automation_scheduler_review(
        root=root,
        generated_utc=generated_utc,
        automation_root=automation_root,
        scheduler_snapshot_path=scheduler_snapshot_path,
    )
    result.csv_path.parent.mkdir(parents=True, exist_ok=True)
    with result.csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for row in result.rows:
            writer.writerow({column: row.get(column, "") for column in REVIEW_COLUMNS})
    result.markdown_path.write_text(result.markdown, encoding="utf-8")
    return result


def format_dead_automation_scheduler_review_status(result: DeadAutomationSchedulerReviewResult) -> str:
    return "\n".join(
        [
            "status=written",
            f"csv_path={result.csv_path}",
            f"markdown_path={result.markdown_path}",
            f"generated_utc={result.generated_utc}",
            f"codex_automations={result.codex_automation_count}",
            f"active_codex_automations={result.active_codex_automation_count}",
            f"paused_codex_automations={result.paused_codex_automation_count}",
            f"windows_schedulers={result.windows_scheduler_count}",
            f"ready_windows_schedulers={result.ready_windows_scheduler_count}",
            f"scheduler_pause_decision_required={'yes' if result.scheduler_pause_decision_required else 'no'}",
            f"recommended_next_task={result.recommended_next_task}",
        ]
    )


def _codex_automation_rows(automation_root: Path | None, *, control_dir: Path) -> list[dict[str, str]]:
    if automation_root is None or not automation_root.exists():
        return []
    rows: list[dict[str, str]] = []
    for path in sorted(automation_root.rglob("automation.toml")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        item_id = _toml_field(text, "id") or path.parent.name
        name = _toml_field(text, "name") or item_id
        status = _toml_field(text, "status") or "unknown"
        kind = _toml_field(text, "kind") or "unknown"
        target = _toml_field(text, "destination") or _toml_field(text, "executionEnvironment") or ""
        scope = "sellerone" if _is_sellerone_name(item_id, name) else "external"
        recommendation, decision, reason = _classify_codex_automation(
            item_id,
            name,
            status,
            scope,
            rep_briefing_activation_exists=(control_dir / REP_BRIEFING_ACTIVATION_REL_PATH.name).exists(),
        )
        rows.append(
            _review_row(
                source_type="codex_automation",
                item_id=item_id,
                name=name,
                status=status,
                kind=kind,
                target=target,
                sellerone_scope=scope,
                recommendation=recommendation,
                luke_decision_required=decision,
                reason=reason,
            )
        )
    return rows


def _classify_codex_automation(
    item_id: str,
    name: str,
    status: str,
    scope: str,
    *,
    rep_briefing_activation_exists: bool,
) -> tuple[str, str, str]:
    lowered = f"{item_id} {name}".lower()
    if scope == "external":
        return "leave_paused_out_of_sellerone_scope", "no", "Not a SellerOne control automation."
    if "so21-rep-briefing" in lowered:
        if status == "ACTIVE" and rep_briefing_activation_exists:
            return "pilot_active_approved", "no", "Approved 2.1 Rep briefing pilot is active."
        if status == "ACTIVE":
            return "pause_or_replace_before_2_1", "yes", "Rep briefing pilot is active without activation proof."
        return "pilot_created_paused", "no", "2.1 Rep briefing pilot exists but remains paused until activation approval."
    if status == "ACTIVE":
        return "pause_or_replace_before_2_1", "yes", "Active SellerOne automation would bypass the 2.1 pause."
    if "coordinator-pulse" in lowered or "hometime" in lowered or "weekend" in lowered:
        return "retire_old_heartbeat", "no", "Old weekend/hometime pulse should not be resumed as a standing manager."
    if "f-scanner" in lowered or "login" in lowered or "remaining-update" in lowered:
        return "retire_old_cycle_heartbeat", "no", "Old F login/session heartbeat should become ticketed work, not a standing loop."
    if "monday-restocking" in lowered or "o-readiness" in lowered or "o-net-fee" in lowered:
        return "retire_old_cycle_heartbeat", "no", "Old O/restocking pulse should become a bounded ticket or redesigned watcher."
    if "o-h-maintenance" in lowered:
        return "protected_do_not_resume", "no", "H/O maintenance automation touches protected scheduler territory."
    if "briefing" in lowered or "quiet-daily-log" in lowered:
        return "candidate_rebuild_from_scratch", "no", "Possible 2.1 Rep briefing or usage reporter, but rebuild rather than resume."
    if "sellerboard" in lowered:
        return "candidate_rebuild_from_scratch", "no", "Possible health watcher, but it must write control evidence only."
    if "f032" in lowered or "review" in lowered:
        return "candidate_rebuild_from_scratch", "no", "Possible review watcher, but should be rebuilt against the queue contract."
    return "review_before_resume", "no", "Paused SellerOne automation needs a 2.1 purpose before it can return."


def _windows_scheduler_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        item_id = _text(row.get("TaskName") or row.get("task_name") or row.get("name"))
        if not item_id:
            continue
        state = _text(row.get("State") or row.get("state")) or "unknown"
        actions = _text(row.get("Actions") or row.get("actions"))
        target = actions or _text(row.get("TaskPath") or row.get("task_path"))
        recommendation, decision, reason = _classify_windows_scheduler(item_id, state, actions)
        output.append(
            _review_row(
                source_type="windows_scheduler",
                item_id=item_id,
                name=item_id,
                status=state,
                kind="scheduled_task",
                target=target,
                sellerone_scope="sellerone",
                recommendation=recommendation,
                luke_decision_required=decision,
                reason=reason,
            )
        )
    return output


def _classify_windows_scheduler(name: str, state: str, actions: str) -> tuple[str, str, str]:
    lowered = f"{name} {actions}".lower()
    is_ready = state.lower() == "ready"
    if not is_ready:
        return "leave_disabled_or_inactive", "no", "Scheduler is not currently ready/running."
    if "run_morning_mot_system.bat" in lowered and "--repair" in lowered:
        return "disable_until_automation_rebuild", "yes", "Ready Windows task can run old MOT repair automation."
    if "controlled_restart" in lowered:
        return "disable_until_restart_policy", "yes", "Ready controlled-restart scheduler is outside the 2.1 queue."
    if "run_h_cycle.bat" in lowered or " h cycle" in lowered:
        return "disable_until_h_scheduler_plan", "yes", "Ready H runtime scheduler can change background ownership."
    if "run_b_cycle.bat" in lowered or " orders" in lowered:
        return "disable_until_b_scheduler_plan", "yes", "Ready B runtime scheduler can run outside the 2.1 queue."
    if "run_a_all.bat" in lowered or "pricing summary" in lowered:
        return "decide_keep_source_fact_or_disable", "yes", "Ready A/source-fact scheduler is outside the 2.1 pause."
    if "run_f_price_list_manager_cycle.bat" in lowered or "price list manager" in lowered:
        return "disable_until_f_login_plan", "yes", "Ready boot task can start the F price-list manager outside the 2.1 queue."
    if "run_manager_hourly_mot.bat" in lowered or "manager hourly mot" in lowered:
        return "decide_keep_read_only_or_disable", "yes", "Ready manager scheduler is outside Codex automation pause."
    return "review_before_resume", "yes", "Ready SellerOne-like scheduler needs Luke decision before 2.1 rebuild."


def _repo_scheduler_entrypoint_rows(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rel_path in REPO_SCHEDULER_ENTRYPOINTS:
        path = root / rel_path
        if not path.exists():
            continue
        rows.append(
            _review_row(
                source_type="repo_scheduler_entrypoint",
                item_id=str(rel_path).replace("\\", "/"),
                name=path.name,
                status="file_present",
                kind=path.suffix.lstrip(".").lower(),
                target=str(rel_path).replace("\\", "/"),
                sellerone_scope="sellerone",
                recommendation="do_not_run_without_approved_task",
                luke_decision_required="no",
                reason="Repo entrypoint exists but was not run or changed during this review.",
            )
        )
    return rows


def _build_markdown(
    *,
    generated_utc: str,
    rows: list[dict[str, str]],
    source_counts: Counter[str],
    codex_rows: list[dict[str, str]],
    windows_rows: list[dict[str, str]],
    control_dir: Path,
    scheduler_pause_decision_required: bool,
    admin_pause_required: bool,
    recommended_next: str,
) -> str:
    codex_status_counts = Counter(row["status"] for row in codex_rows)
    windows_ready = [row for row in windows_rows if row["status"].lower() == "ready"]
    lines = [
        "# SellerOne Dead Automation And Scheduler Review",
        "",
        "Job: `SO21-DEAD-AUTOMATION-AND-SCHEDULER-REVIEW`",
        f"Generated UTC: {generated_utc}",
        "Generated by: `sellerone_manager.dead_automation_scheduler_review`",
        "",
        "## Plain-English Status",
        "",
        (
            "Codex app automations are paused, but the Windows scheduler still has SellerOne-looking tasks registered. "
            "No automation or scheduler was restarted, disabled, deleted, or edited by this review."
        ),
        "",
        f"- Codex app automations found: {len(codex_rows)}",
        f"- Active Codex app automations: {codex_status_counts.get('ACTIVE', 0)}",
        f"- Paused Codex app automations: {codex_status_counts.get('PAUSED', 0)}",
        f"- Windows scheduler tasks found: {len(windows_rows)}",
        f"- Ready Windows scheduler tasks: {len(windows_ready)}",
        f"- Scheduler pause decision required: {'yes' if scheduler_pause_decision_required else 'no'}",
        f"- Administrator pause still required: {'yes' if admin_pause_required else 'no'}",
        f"- Recommended next task: `{recommended_next}`",
        "",
    ]
    if admin_pause_required:
        lines.extend(
            [
                "## Admin Pause Still Required",
                "",
                "Luke approved the temporary pause, and the non-elevated schedulers were paused where Windows allowed it. "
                "Some runtime schedulers still require an Administrator shell before they can be disabled.",
                "",
            ]
        )
        admin_rows = _admin_blocked_rows(control_dir)
        if admin_rows:
            lines.extend(_format_rows(admin_rows))
        lines.append("")
    if scheduler_pause_decision_required:
        lines.extend(
            [
                "## Luke Decision Needed",
                "",
                "The 2.1 app-level automation pause is incomplete unless Luke decides what to do with these ready Windows tasks:",
                "",
            ]
        )
        lines.extend(_format_rows(windows_ready))
        lines.extend(
            [
                "",
                "Recommended decision shape:",
                "",
                "- Disable old repair/startup scheduler tasks during SellerOne 2.1 stabilisation.",
                "- Rebuild only one approved read-only health watcher later, from the queue contract.",
                "- Do not resume F or repair schedulers until their specific task packet says so.",
                "",
            ]
        )
    lines.extend(["## Source Counts", ""])
    for source_type, count in sorted(source_counts.items()):
        lines.append(f"- `{source_type}`: {count}")
    lines.extend(["", "## SellerOne Codex Automations", ""])
    sellerone_codex = [row for row in codex_rows if row["sellerone_scope"] == "sellerone"]
    if not sellerone_codex:
        lines.append("No SellerOne Codex automations were found.")
    else:
        lines.extend(_format_rows(sellerone_codex))
    external = [row for row in codex_rows if row["sellerone_scope"] == "external"]
    lines.extend(["", "## External Codex Automations", ""])
    if not external:
        lines.append("No external paused automations were found.")
    else:
        lines.append(f"{len(external)} paused non-SellerOne automations were found and left out of SellerOne decisions.")
    lines.extend(["", "## Windows Scheduler Tasks", ""])
    if not windows_rows:
        lines.append("No SellerOne-like Windows scheduler tasks were found.")
    else:
        lines.extend(_format_rows(windows_rows))
    repo_rows = [row for row in rows if row["source_type"] == "repo_scheduler_entrypoint"]
    lines.extend(["", "## Repo Scheduler Entrypoints", ""])
    if not repo_rows:
        lines.append("No scheduler entrypoint files were found.")
    else:
        lines.extend(_format_rows(repo_rows))
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- This review does not approve any automation restart.",
            "- This review does not disable, delete, or change scheduled tasks.",
            "- Old heartbeat/cycle automations should be retired or rebuilt from scratch, not resumed blindly.",
            "- Any scheduler pause/disable action needs explicit Luke approval because it changes background ownership.",
            "- Any future automation must write to a control artifact and must not perform protected business work.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _format_rows(rows: list[dict[str, str]]) -> list[str]:
    lines = ["| Item | Status | Recommendation | Decision | Reason |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_code(row["item_id"]),
                    _md(row["status"]),
                    _md(row["recommendation"]),
                    _md(row["luke_decision_required"]),
                    _md(_short(row["reason"], 140)),
                ]
            )
            + " |"
        )
    return lines


def _query_windows_schedulers() -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    command = r"""
$rows = Get-ScheduledTask | Where-Object {
    $_.TaskName -match 'SellerOne|sellerone|Morning MOT|AMZ|Price List Manager|Codex_H' -or
    $_.TaskPath -match 'SellerOne|sellerone'
} | ForEach-Object {
    $actions = @()
    foreach ($action in $_.Actions) {
        $actions += (($action.Execute + ' ' + $action.Arguments).Trim())
    }
    [PSCustomObject]@{
        TaskName = $_.TaskName
        State = [string]$_.State
        TaskPath = [string]$_.TaskPath
        Actions = ($actions -join ' || ')
    }
}
@($rows) | ConvertTo-Json -Depth 4
"""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        payload: Any = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    return [
        {key: _text(value) for key, value in item.items()}
        for item in payload
        if isinstance(item, dict) and _text(item.get("TaskName"))
    ]


def _read_scheduler_snapshot(path: Path | str | None) -> list[dict[str, str]]:
    if path is None:
        return []
    snapshot = Path(path)
    if not snapshot.exists():
        return []
    with snapshot.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items()} for row in reader]


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


def _windows_scheduler_admin_pause_needed(control_dir: Path) -> bool:
    rows = _read_csv_rows(control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv")
    return any(
        row.get("after_state") == "Ready"
        and row.get("exit_code") not in {"", "0"}
        for row in rows
    )


def _admin_blocked_rows(control_dir: Path) -> list[dict[str, str]]:
    rows = _read_csv_rows(control_dir / "WINDOWS_SCHEDULER_PAUSE_PROOF.csv")
    return [
        _review_row(
            source_type="windows_scheduler_pause_proof",
            item_id=row.get("task_name", ""),
            name=row.get("task_name", ""),
            status=row.get("after_state", ""),
            kind="scheduled_task",
            target="",
            sellerone_scope="sellerone",
            recommendation="run_pause_from_admin_shell",
            luke_decision_required="yes",
            reason="Windows returned access denied from a non-admin shell.",
        )
        for row in rows
        if row.get("after_state") == "Ready" and row.get("exit_code") not in {"", "0"}
    ]


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _toml_field(text: str, field: str) -> str:
    match = re.search(rf'^{re.escape(field)}\s*=\s*"([^"]*)"', text, flags=re.MULTILINE)
    return match.group(1) if match else ""


def _is_sellerone_name(*values: str) -> bool:
    lowered = " ".join(values).lower()
    return any(hint in lowered for hint in SELLERONE_AUTOMATION_HINTS)


def _review_row(
    *,
    source_type: str,
    item_id: str,
    name: str,
    status: str,
    kind: str,
    target: str,
    sellerone_scope: str,
    recommendation: str,
    luke_decision_required: str,
    reason: str,
) -> dict[str, str]:
    return {
        "source_type": source_type,
        "item_id": item_id,
        "name": name,
        "status": status,
        "kind": kind,
        "target": target,
        "sellerone_scope": sellerone_scope,
        "recommendation": recommendation,
        "luke_decision_required": luke_decision_required,
        "reason": reason,
    }


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
