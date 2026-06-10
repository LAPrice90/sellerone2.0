from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .autonomy_policy import controlled_technical_pause_allowed, is_controlled_technical_pause_text, quiet_autonomy_active
from .hourly_mot import update_mot_work_item_status
from .paths import get_manager_paths
from .schemas import APPROVED_TASK_PACKET_COLUMNS


SAFE_ACTIVE_STATUSES = {"approved", "in_progress", "fixed_needs_retest", "retest_failed", "reopened"}
BLOCKED_STATUSES = {"blocked_needs_luke"}
TERMINAL_STATUSES = {"proved", "parked"}
PACKET_STATUSES = SAFE_ACTIVE_STATUSES | BLOCKED_STATUSES | TERMINAL_STATUSES
MANUAL_TASK_SOURCE_TYPE = "manual_task_file"

MOT_SOURCE_ACTIVE_STATUSES = {"new", "assigned", "in_progress", "fixed_needs_retest", "retest_failed"}
MANAGER_SOURCE_ACTIVE_STATUSES = {"proposed", "in_progress", "reopened"}

PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}
REF_WORD_LIMIT = 3
REF_STOP_WORDS = {
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "H",
    "M",
    "O",
    "MGR",
    "MOT",
    "TASK",
    "JOB",
    "MANAGER",
    "CODEX",
    "WORK",
    "WORKLIST",
    "ITEM",
    "REPAIR",
    "PACKAGE",
    "NEEDS",
    "NEED",
    "RETEST",
    "WAITING",
    "BLOCKED",
    "PROVED",
    "PARKED",
    "DECISION",
    "DECISIONS",
    "PROTECTED",
    "STATUS",
    "STATE",
    "APPLY",
    "APPLIED",
    "LIVE",
    "RETURN",
    "RETURNED",
    "PROOF",
    "PRICE",
    "PRICES",
    "LIST",
    "LATEST",
    "CURRENT",
    "CHECK",
    "FAIL",
    "WARN",
    "OK",
    "V1",
    "V2",
}
REF_TOKEN_REPLACEMENTS = {
    "RETURNEDTOKEN": ["RETURNED", "TOKEN"],
    "RETURNSTATUS": ["RETURN", "STATUS"],
    "ORIGINALTOKEN": ["ORIGINAL", "TOKEN"],
    "SOURCING": ["SOURCE"],
}


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [{key: value or "" for key, value in row.items() if key is not None} for row in reader]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def approved_task_index_path(root: Path | str | None = None) -> Path:
    return get_manager_paths(root).output_dir / "approved_task_packets.csv"


def _task_dir(root: Path, status: str) -> Path:
    folder = "blocked" if status == "blocked_needs_luke" else "approved"
    return root / "sellerone_manager" / "tasks" / folder


def _safe_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return text[:96] or "manager_task"


def _normalise_job_ref(value: str, flow: str = "") -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").upper()).strip("-")
    text = re.sub(r"-+", "-", text)
    flow = str(flow or "").upper().strip()
    if flow and text and not text.startswith(f"{flow}-"):
        text = f"{flow}-{text}"
    return text[:80].strip("-")


def _job_ref_tokens(*parts: str) -> list[str]:
    raw_text = " ".join(str(part or "") for part in parts)
    raw_text = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw_text)
    raw_tokens = re.findall(r"[A-Za-z0-9]+", raw_text.upper())
    tokens: list[str] = []
    for token in raw_tokens:
        replacement = REF_TOKEN_REPLACEMENTS.get(token, [token])
        for word in replacement:
            if word in REF_STOP_WORDS:
                continue
            if len(word) == 1 and word.isalpha():
                continue
            if word not in tokens:
                tokens.append(word)
    return tokens


def _generated_job_ref(row: dict[str, str]) -> str:
    flow = (row.get("flow") or _flow_from_task_id(row.get("task_id", "")) or "M").upper()
    tokens = _job_ref_tokens(
        row.get("title", ""),
        row.get("check", ""),
        row.get("source_id", ""),
        row.get("task_id", ""),
    )
    if "EMAIL" in tokens and "SOURCE" in tokens:
        tokens = ["EMAIL", "SOURCE"]
    elif "ORIGINAL" in tokens and "TOKEN" in tokens:
        tokens = ["ORIGINAL", "TOKEN"]
    else:
        tokens = tokens[:REF_WORD_LIMIT]
    return _normalise_job_ref("-".join([flow] + (tokens or ["JOB"])))


def _assign_unique_job_refs(rows: list[dict[str, str]]) -> None:
    used: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: item.get("task_id", "")):
        flow = row.get("flow") or _flow_from_task_id(row.get("task_id", ""))
        desired = _normalise_job_ref(row.get("job_ref", ""), flow) or _generated_job_ref(row)
        count = used.get(desired, 0) + 1
        used[desired] = count
        row["job_ref"] = desired if count == 1 else f"{desired}-{count:02d}"


def _resolve_task_identifier(rows: list[dict[str, str]], identifier: str) -> dict[str, str]:
    identifier_text = str(identifier or "").strip()
    for row in rows:
        if row.get("task_id") == identifier_text:
            return row
    matches = [row for row in rows if row.get("job_ref") == identifier_text]
    if not matches:
        normalised = _normalise_job_ref(identifier_text)
        matches = [row for row in rows if _normalise_job_ref(row.get("job_ref", "")) == normalised]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        task_ids = ", ".join(sorted(row.get("task_id", "") for row in matches))
        raise ValueError(f"ambiguous job_ref {identifier_text}: use full task_id ({task_ids})")
    raise ValueError(f"approved manager task not found by task_id or job_ref: {identifier_text}")


def _packet_path(root: Path, task_id: str, status: str) -> Path:
    return _task_dir(root, status) / f"{_safe_id(task_id)}.md"


def _field_value(markdown: str, field_name: str) -> str:
    pattern = rf"^\s*-?\s*{re.escape(field_name)}\s*:\s*(?P<value>.*)$"
    match = re.search(pattern, markdown, flags=re.MULTILINE)
    return match.group("value").strip() if match else ""


def _flow_from_task_id(task_id: str) -> str:
    match = re.match(r"^(?:MGR|MOT)_([A-Z])(?:_|$)", task_id)
    return match.group(1) if match else ""


def _manual_task_files(root: Path) -> list[Path]:
    task_root = root / "sellerone_manager" / "tasks"
    paths: list[Path] = []
    for folder in ("approved", "blocked"):
        folder_path = task_root / folder
        if folder_path.exists():
            paths.extend(folder_path.glob("*.md"))
    return sorted(paths)


def _is_generated_packet(markdown: str) -> bool:
    source_type = _field_value(markdown, "source_type")
    return source_type in {"mot", "manager_candidate", "repair_package"}


def _manual_task_packet(path: Path, *, root: Path, observed_utc: str, previous: dict[str, str]) -> dict[str, str] | None:
    markdown = path.read_text(encoding="utf-8")
    if _is_generated_packet(markdown):
        return None
    task_id = _safe_id(_field_value(markdown, "task_id") or path.stem)
    file_status = _field_value(markdown, "status")
    default_status = "blocked_needs_luke" if path.parent.name == "blocked" else "approved"
    status = previous.get("status") if previous.get("status") in PACKET_STATUSES else file_status
    if status not in PACKET_STATUSES:
        status = default_status
    luke_action = _field_value(markdown, "luke_action_required")
    if status in BLOCKED_STATUSES:
        luke_action = "1"
    elif luke_action not in {"0", "1"}:
        luke_action = "0"
    return {
        "observed_utc": observed_utc,
        "created_utc": previous.get("created_utc") or observed_utc,
        "updated_utc": observed_utc,
        "task_id": task_id,
        "job_ref": _field_value(markdown, "job_ref") or previous.get("job_ref", ""),
        "source_type": MANUAL_TASK_SOURCE_TYPE,
        "source_id": task_id,
        "source_path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "flow": _field_value(markdown, "flow") or _flow_from_task_id(task_id),
        "task_type": _field_value(markdown, "task_type") or "manual_approved_task",
        "authority": _field_value(markdown, "authority") or "manual_manager_packet",
        "status": status,
        "priority": _field_value(markdown, "priority") or "normal",
        "title": _markdown_title(markdown, task_id),
        "allowed_scope": _field_value(markdown, "allowed_scope") or _section_text(markdown, "Allowed Work"),
        "forbidden_actions": _field_value(markdown, "forbidden_actions") or _section_text(markdown, "Forbidden Work"),
        "proof_required": _field_value(markdown, "proof_required") or _section_text(markdown, "Acceptance Proof"),
        "retest_command": _field_value(markdown, "retest_command"),
        "rollback_path": _field_value(markdown, "rollback_path") or "Use git diff for code rollback.",
        "stop_condition": _field_value(markdown, "stop_condition") or _section_text(markdown, "Worker Stop Conditions"),
        "luke_action_required": luke_action,
        "packet_path": str(path),
        "notes": previous.get("notes") or "Created from a manually approved manager task packet.",
    }


def _priority_key(row: dict[str, str]) -> tuple[int, str, str]:
    return (PRIORITY_RANK.get(row.get("priority", ""), 9), row.get("flow", ""), row.get("task_id", ""))


def _existing_map(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("task_id", ""): row for row in rows if row.get("task_id")}


def _is_luke_blocked(row: dict[str, str], source_type: str) -> bool:
    if source_type == "mot":
        return row.get("luke_action_required") == "1" or row.get("status") == "blocked_needs_luke"
    return row.get("needs_luke_decision") == "1" or row.get("status") == "blocked_needs_user_decision"


def _mot_packet(row: dict[str, str], *, root: Path, observed_utc: str, previous: dict[str, str]) -> dict[str, str]:
    source_id = row.get("work_item_id", "")
    blocked = _is_luke_blocked(row, "mot")
    task_id = _safe_id(source_id)
    source_status = row.get("status", "")
    if blocked:
        status = "blocked_needs_luke"
    elif source_status in TERMINAL_STATUSES:
        status = source_status
    else:
        status = _preserved_status(previous, "approved", preserve_terminal=False)
    packet_path = _packet_path(root, task_id, status)
    job_ref = previous.get("job_ref") or row.get("job_ref", "")
    if source_id == "MOT_F_F_LIVE_OWNER_STATUS":
        job_ref = row.get("job_ref") or "F-SCANNER-PROGRESS"
    return {
        "observed_utc": observed_utc,
        "created_utc": previous.get("created_utc") or observed_utc,
        "updated_utc": observed_utc,
        "task_id": task_id,
        "job_ref": job_ref,
        "source_type": "mot",
        "source_id": source_id,
        "source_path": row.get("source_path", ""),
        "flow": row.get("flow", ""),
        "task_type": "bounded_code_repair" if not blocked else "blocked_decision",
        "authority": "standing_safe_code_repair" if not blocked else "needs_luke_decision",
        "status": status,
        "priority": row.get("priority", "normal"),
        "title": row.get("title", ""),
        "allowed_scope": row.get("allowed_scope") or row.get("safe_repair_boundary", ""),
        "forbidden_actions": row.get("forbidden_actions", ""),
        "proof_required": row.get("proof_required", ""),
        "retest_command": row.get("retest_command", ""),
        "rollback_path": "Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.",
        "stop_condition": "Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.",
        "luke_action_required": "1" if blocked else "0",
        "packet_path": str(packet_path),
        "notes": row.get("manager_action", "") if blocked else row.get("notes") or row.get("manager_action", ""),
    }


def _manager_packet(row: dict[str, str], *, root: Path, observed_utc: str, previous: dict[str, str]) -> dict[str, str]:
    source_id = row.get("task_id", "")
    blocked = _is_luke_blocked(row, "manager")
    task_id = _safe_id(f"MGR_{source_id}")
    if blocked:
        status = "blocked_needs_luke"
    elif _repair_package_covers_manager_candidate(root, task_id, row):
        status = "proved"
    else:
        status = _preserved_status(
            previous,
            "approved",
            preserve_terminal=row.get("task_type", "") != "repair",
        )
    packet_path = _packet_path(root, task_id, status)
    return {
        "observed_utc": observed_utc,
        "created_utc": previous.get("created_utc") or observed_utc,
        "updated_utc": observed_utc,
        "task_id": task_id,
        "job_ref": previous.get("job_ref") or row.get("job_ref", ""),
        "source_type": "manager_candidate",
        "source_id": source_id,
        "source_path": row.get("root_artifact", ""),
        "flow": row.get("flow", ""),
        "task_type": "task_packaging_only" if not blocked else "blocked_decision",
        "authority": "manager_task_packaging_only" if not blocked else "needs_luke_decision",
        "status": status,
        "priority": row.get("priority", "normal"),
        "title": row.get("title", ""),
        "allowed_scope": row.get("allowed_scope", ""),
        "forbidden_actions": row.get("forbidden_actions", ""),
        "proof_required": row.get("proof_required", ""),
        "retest_command": "",
        "rollback_path": "No worker rollback path. This task may only package manager scope, proof, and stop conditions.",
        "stop_condition": row.get("stop_condition") or "Stop after the manager task packet is clear enough for a future bounded repair.",
        "luke_action_required": "1" if blocked else "0",
        "packet_path": str(packet_path),
        "notes": row.get("notes", ""),
    }


def _preserved_status(previous: dict[str, str], default: str, *, preserve_terminal: bool) -> str:
    status = previous.get("status", "")
    if status in SAFE_ACTIVE_STATUSES:
        return status
    if preserve_terminal and status in TERMINAL_STATUSES:
        return status
    return default


def _repair_package_paths_for_manager_task(root: Path, manager_task_id: str) -> list[Path]:
    package_pattern = f"H_REPAIR_PACKAGE_{_safe_id(manager_task_id)}*.md"
    return sorted((root / "plans" / "active").glob(f"**/{package_pattern}"))


def _repair_package_exists(root: Path, manager_task_id: str) -> bool:
    return bool(_repair_package_paths_for_manager_task(root, manager_task_id))


def _repair_package_covers_manager_candidate(root: Path, manager_task_id: str, row: dict[str, str]) -> bool:
    package_paths = _repair_package_paths_for_manager_task(root, manager_task_id)
    if not package_paths:
        return False

    notes = str(row.get("notes", "") or "").strip().lower()
    match = re.search(r"(\d+)\s+active\s+fail", notes)
    if not match:
        return True

    expected_fail_count = int(match.group(1))
    package_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore").lower() for path in package_paths)
    if expected_fail_count == 1 and ("one checklist row" in package_text or "1 active fail" in package_text):
        return True
    return (
        f"{expected_fail_count} active fail" in package_text
        or f"{expected_fail_count} active fail/blocker" in package_text
    )


def _section_text(markdown: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, markdown, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return ""
    lines: list[str] = []
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lines.append(line)
    return " ".join(lines)


def _first_backticked_value(markdown: str, prefix: str) -> str:
    match = re.search(rf"`({re.escape(prefix)}[A-Za-z0-9_]+)`", markdown)
    if match:
        return match.group(1)
    plain_match = re.search(rf"\b({re.escape(prefix)}[A-Za-z0-9_]+)\b", markdown)
    return plain_match.group(1) if plain_match else ""


def _repair_package_task_suffix(markdown: str, *, prefix: str, fallback: str) -> str:
    for heading in ["Approved Check", "Task Id", "Task ID", "Manager Task Id", "Manager Task ID"]:
        explicit_section = _section_text(markdown, heading)
        explicit_value = _first_backticked_value(explicit_section, prefix)
        if explicit_value:
            return explicit_value
    return _first_backticked_value(markdown, prefix) or fallback


def _markdown_title(markdown: str, fallback: str) -> str:
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def _repair_package_packet(path: Path, *, root: Path, observed_utc: str, previous: dict[str, str]) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    failed_check = _repair_package_task_suffix(markdown, prefix="h_", fallback=path.stem)
    task_suffix = failed_check or path.stem
    task_id = _safe_id(f"MGR_H_repair_{task_suffix}")
    title = _markdown_title(markdown, f"Repair H {failed_check or path.stem}")
    previous_text = " ".join(
        [
            previous.get("task_id", ""),
            previous.get("title", ""),
            previous.get("notes", ""),
            previous.get("allowed_scope", ""),
            previous.get("proof_required", ""),
        ]
    )
    if quiet_autonomy_active(root) and previous.get("status") != "proved":
        status = "parked"
    elif (
        previous.get("status") in BLOCKED_STATUSES
        and not (
            controlled_technical_pause_allowed(root)
            and is_controlled_technical_pause_text(previous_text)
        )
    ):
        status = previous["status"]
    else:
        status = _preserved_status(previous, "approved", preserve_terminal=True)
    packet_path = _packet_path(root, task_id, status)
    allowed_scope = _section_text(markdown, "Allowed Files For A Future Repair Batch")
    forbidden_actions = _section_text(markdown, "Forbidden Files And Actions")
    proof_required = _section_text(markdown, "Proof Path For A Future Repair") or _section_text(markdown, "Proof Path For Future Repair")
    retest_command = _section_text(markdown, "Retest Command")
    rollback_path = _section_text(markdown, "Rollback Path")
    stop_condition = _section_text(markdown, "Stop Condition")
    return {
        "observed_utc": observed_utc,
        "created_utc": previous.get("created_utc") or observed_utc,
        "updated_utc": observed_utc,
        "task_id": task_id,
        "job_ref": _field_value(markdown, "job_ref") or previous.get("job_ref", ""),
        "source_type": "repair_package",
        "source_id": path.stem,
        "source_path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "flow": "H",
        "task_type": "bounded_code_repair",
        "authority": "standing_safe_code_repair",
        "status": status,
        "priority": "high",
        "title": title,
        "allowed_scope": allowed_scope,
        "forbidden_actions": forbidden_actions,
        "proof_required": proof_required,
        "retest_command": retest_command or "python -m pytest tests/test_phase1_storage.py tests/test_phase1_main_loop.py -q",
        "rollback_path": rollback_path or "Restore timestamped backups before reverting the narrow rollup code changes.",
        "stop_condition": stop_condition or "Stop if the repair crosses a protected boundary or the root-cause evidence changes.",
        "luke_action_required": "1" if status in BLOCKED_STATUSES else "0",
        "packet_path": str(packet_path),
        "notes": _repair_package_notes(status=status, previous=previous),
    }


def _repair_package_notes(*, status: str, previous: dict[str, str]) -> str:
    if status in BLOCKED_STATUSES and previous.get("notes"):
        return previous.get("notes", "")
    if status == "parked":
        return (
            "Parked during Quiet Autonomy. H repair waits until the independent H manager/MOT layer exists "
            "or a separate approved H proof packet is opened."
        )
    return "Created from manager repair package. Safe code repair is standing-approved inside this boundary."


def _repair_package_rows(root: Path) -> list[Path]:
    active_root = root / "plans" / "active"
    if not active_root.exists():
        return []
    return sorted(
        list(active_root.glob("**/H_REPAIR_PACKAGE_*.md"))
        + list(active_root.glob("**/B_REPAIR_PACKAGE_*.md"))
        + list(active_root.glob("**/E_REPAIR_PACKAGE_*.md"))
        + list(active_root.glob("**/F_REPAIR_PACKAGE_*.md"))
    )


def _e_repair_package_packet(path: Path, *, root: Path, observed_utc: str, previous: dict[str, str]) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    failed_check = _repair_package_task_suffix(markdown, prefix="e_", fallback=path.stem)
    task_suffix = failed_check or path.stem
    task_id = _safe_id(f"MGR_E_repair_{task_suffix}")
    title = _markdown_title(markdown, f"Repair E {failed_check or path.stem}")
    if previous.get("status") in BLOCKED_STATUSES:
        status = previous["status"]
    else:
        status = _preserved_status(previous, "approved", preserve_terminal=True)
    packet_path = _packet_path(root, task_id, status)
    allowed_scope = _section_text(markdown, "Allowed Files For A Future Repair Batch") or _section_text(markdown, "Allowed Scope")
    forbidden_actions = _section_text(markdown, "Forbidden Files And Actions")
    proof_required = _section_text(markdown, "Proof Path For A Future Repair") or _section_text(markdown, "Proof Path For Future Repair")
    retest_command = _section_text(markdown, "Retest Command")
    rollback_path = _section_text(markdown, "Rollback Path")
    stop_condition = _section_text(markdown, "Stop Condition")
    return {
        "observed_utc": observed_utc,
        "created_utc": previous.get("created_utc") or observed_utc,
        "updated_utc": observed_utc,
        "task_id": task_id,
        "job_ref": _field_value(markdown, "job_ref") or previous.get("job_ref", ""),
        "source_type": "repair_package",
        "source_id": path.stem,
        "source_path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "flow": "E",
        "task_type": "bounded_code_repair",
        "authority": "standing_safe_code_repair",
        "status": status,
        "priority": "high",
        "title": title,
        "allowed_scope": allowed_scope,
        "forbidden_actions": forbidden_actions,
        "proof_required": proof_required,
        "retest_command": retest_command or "python -m sellerone_manager.app --hourly-mot --mot-flow E",
        "rollback_path": rollback_path or "Use git diff for code rollback. Do not alter live E data outputs to satisfy proof.",
        "stop_condition": stop_condition or "Stop if the work crosses a protected E boundary or the proof source changes.",
        "luke_action_required": "1" if status in BLOCKED_STATUSES else "0",
        "packet_path": str(packet_path),
        "notes": previous.get("notes", "") if status in BLOCKED_STATUSES else "Created from E manager proof package. Safe code/proof work is standing-approved inside this boundary.",
    }


def _f_repair_package_packet(path: Path, *, root: Path, observed_utc: str, previous: dict[str, str]) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    failed_check = _repair_package_task_suffix(markdown, prefix="f_", fallback=path.stem)
    task_suffix = failed_check or path.stem
    task_id = _safe_id(f"MGR_F_repair_{task_suffix}")
    title = _markdown_title(markdown, f"Repair F {failed_check or path.stem}")
    if previous.get("status") in BLOCKED_STATUSES:
        status = previous["status"]
    else:
        status = _preserved_status(previous, "approved", preserve_terminal=True)
    packet_path = _packet_path(root, task_id, status)
    allowed_scope = _section_text(markdown, "Allowed Files For A Future Repair Batch") or _section_text(markdown, "Allowed Scope")
    forbidden_actions = _section_text(markdown, "Forbidden Files And Actions")
    proof_required = _section_text(markdown, "Proof Path For A Future Repair") or _section_text(markdown, "Proof Path For Future Repair")
    retest_command = _section_text(markdown, "Retest Command")
    rollback_path = _section_text(markdown, "Rollback Path")
    stop_condition = _section_text(markdown, "Stop Condition")
    return {
        "observed_utc": observed_utc,
        "created_utc": previous.get("created_utc") or observed_utc,
        "updated_utc": observed_utc,
        "task_id": task_id,
        "job_ref": _field_value(markdown, "job_ref") or previous.get("job_ref", ""),
        "source_type": "repair_package",
        "source_id": path.stem,
        "source_path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "flow": "F",
        "task_type": "bounded_code_repair",
        "authority": "standing_safe_code_repair",
        "status": status,
        "priority": "high",
        "title": title,
        "allowed_scope": allowed_scope,
        "forbidden_actions": forbidden_actions,
        "proof_required": proof_required,
        "retest_command": retest_command or "python -m sellerone_manager.app --hourly-mot --mot-flow F",
        "rollback_path": rollback_path or "Use git diff for code rollback. Do not alter live F queue or scanner outputs to satisfy proof.",
        "stop_condition": stop_condition or "Stop if the work crosses a protected F boundary or the proof source changes.",
        "luke_action_required": "1" if status in BLOCKED_STATUSES else "0",
        "packet_path": str(packet_path),
        "notes": previous.get("notes", "") if status in BLOCKED_STATUSES else "Created from F manager proof package. Safe code/proof work is standing-approved inside this boundary.",
    }


def _b_repair_package_packet(path: Path, *, root: Path, observed_utc: str, previous: dict[str, str]) -> dict[str, str]:
    markdown = path.read_text(encoding="utf-8")
    failed_check = _repair_package_task_suffix(markdown, prefix="b_", fallback=path.stem)
    task_suffix = failed_check or path.stem
    task_id = _safe_id(f"MGR_B_repair_{task_suffix}")
    title = _markdown_title(markdown, f"Repair B {failed_check or path.stem}")
    if previous.get("status") in BLOCKED_STATUSES:
        status = previous["status"]
    else:
        status = _preserved_status(previous, "approved", preserve_terminal=True)
    packet_path = _packet_path(root, task_id, status)
    allowed_scope = _section_text(markdown, "Allowed Files For A Future Repair Batch") or _section_text(markdown, "Allowed Scope")
    forbidden_actions = _section_text(markdown, "Forbidden Files And Actions")
    proof_required = _section_text(markdown, "Proof Path For A Future Repair") or _section_text(markdown, "Proof Path For Future Repair")
    retest_command = _section_text(markdown, "Retest Command")
    rollback_path = _section_text(markdown, "Rollback Path")
    stop_condition = _section_text(markdown, "Stop Condition")
    return {
        "observed_utc": observed_utc,
        "created_utc": previous.get("created_utc") or observed_utc,
        "updated_utc": observed_utc,
        "task_id": task_id,
        "job_ref": _field_value(markdown, "job_ref") or previous.get("job_ref", ""),
        "source_type": "repair_package",
        "source_id": path.stem,
        "source_path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "flow": "B",
        "task_type": "bounded_code_repair",
        "authority": "standing_safe_code_repair",
        "status": status,
        "priority": "high",
        "title": title,
        "allowed_scope": allowed_scope,
        "forbidden_actions": forbidden_actions,
        "proof_required": proof_required,
        "retest_command": retest_command or "python -m sellerone_manager.app --hourly-mot --mot-flow B",
        "rollback_path": rollback_path or "Use git diff for code rollback. Do not alter live B data outputs to satisfy proof.",
        "stop_condition": stop_condition or "Stop if the work crosses a protected B boundary or the proof source changes.",
        "luke_action_required": "1" if status in BLOCKED_STATUSES else "0",
        "packet_path": str(packet_path),
        "notes": previous.get("notes", "") if status in BLOCKED_STATUSES else "Created from B manager proof package. Safe code/proof work is standing-approved inside this boundary.",
    }


def _source_payload(
    source_type: str,
    source_id: str,
    mot_rows: list[dict[str, str]],
    manager_rows: list[dict[str, str]],
    repair_package_rows: list[dict[str, str]],
) -> dict[str, Any]:
    if source_type == "mot":
        rows = mot_rows
        key = "work_item_id"
    elif source_type == "manager_candidate":
        rows = manager_rows
        key = "task_id"
    else:
        rows = repair_package_rows
        key = "source_id"
    for row in rows:
        if row.get(key) == source_id:
            return row
    return {}


def _packet_markdown(row: dict[str, str], source_payload: dict[str, Any]) -> str:
    lines = [
        f"# {row.get('title', row.get('task_id', 'Approved Manager Task'))}",
        "",
        "## Manager Authority",
        f"- task_id: {row.get('task_id', '')}",
        f"- job_ref: {row.get('job_ref', '')}",
        f"- status: {row.get('status', '')}",
        f"- authority: {row.get('authority', '')}",
        f"- luke_action_required: {row.get('luke_action_required', '')}",
        "",
        "## Boundary",
        f"- allowed_scope: {row.get('allowed_scope', '')}",
        f"- forbidden_actions: {row.get('forbidden_actions', '')}",
        f"- proof_required: {row.get('proof_required', '')}",
        f"- retest_command: {row.get('retest_command', '')}",
        f"- rollback_path: {row.get('rollback_path', '')}",
        f"- stop_condition: {row.get('stop_condition', '')}",
        "",
        "## Source",
        f"- source_type: {row.get('source_type', '')}",
        f"- source_id: {row.get('source_id', '')}",
        f"- source_path: {row.get('source_path', '')}",
        "",
        "## Exact Source Row",
        "```json",
        json.dumps(source_payload, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def _write_packets(
    root: Path,
    rows: list[dict[str, str]],
    mot_rows: list[dict[str, str]],
    manager_rows: list[dict[str, str]],
    repair_package_sources: list[dict[str, str]],
) -> None:
    for row in rows:
        if row.get("source_type") == MANUAL_TASK_SOURCE_TYPE:
            continue
        path = Path(row.get("packet_path", ""))
        if not path:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _source_payload(
            row.get("source_type", ""),
            row.get("source_id", ""),
            mot_rows,
            manager_rows,
            repair_package_sources,
        )
        path.write_text(_packet_markdown(row, payload), encoding="utf-8")


def refresh_approved_task_packets(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    index_path = approved_task_index_path(base)
    previous = _existing_map(read_csv_rows(index_path))

    mot_path = paths.output_dir / "mot" / "mot_worklist.csv"
    manager_path = paths.output_dir / "manager_task_candidates.csv"
    mot_rows = read_csv_rows(mot_path)
    manager_rows = read_csv_rows(manager_path)
    repair_paths = _repair_package_rows(base)
    repair_package_sources = [
        {"source_id": path.stem, "source_path": str(path.relative_to(base)) if path.is_relative_to(base) else str(path)}
        for path in repair_paths
    ]

    packet_rows: list[dict[str, str]] = []
    for source in mot_rows:
        status = source.get("status", "")
        if status not in MOT_SOURCE_ACTIVE_STATUSES and status not in TERMINAL_STATUSES and status != "blocked_needs_luke":
            continue
        task_id = _safe_id(source.get("work_item_id", ""))
        packet_rows.append(_mot_packet(source, root=base, observed_utc=observed, previous=previous.get(task_id, {})))

    for source in manager_rows:
        status = source.get("status", "")
        if status not in MANAGER_SOURCE_ACTIVE_STATUSES and status != "blocked_needs_user_decision":
            continue
        task_id = _safe_id(f"MGR_{source.get('task_id', '')}")
        packet_rows.append(_manager_packet(source, root=base, observed_utc=observed, previous=previous.get(task_id, {})))

    for package_path in repair_paths:
        package_text = package_path.read_text(encoding="utf-8")
        if package_path.name.startswith("B_REPAIR_PACKAGE_"):
            task_suffix = _repair_package_task_suffix(package_text, prefix="b_", fallback=package_path.stem)
            task_id = _safe_id(f"MGR_B_repair_{task_suffix}")
            packet_rows.append(
                _b_repair_package_packet(package_path, root=base, observed_utc=observed, previous=previous.get(task_id, {}))
            )
        elif package_path.name.startswith("E_REPAIR_PACKAGE_"):
            task_suffix = _repair_package_task_suffix(package_text, prefix="e_", fallback=package_path.stem)
            task_id = _safe_id(f"MGR_E_repair_{task_suffix}")
            packet_rows.append(
                _e_repair_package_packet(package_path, root=base, observed_utc=observed, previous=previous.get(task_id, {}))
            )
        elif package_path.name.startswith("F_REPAIR_PACKAGE_"):
            task_suffix = _repair_package_task_suffix(package_text, prefix="f_", fallback=package_path.stem)
            task_id = _safe_id(f"MGR_F_repair_{task_suffix}")
            packet_rows.append(
                _f_repair_package_packet(package_path, root=base, observed_utc=observed, previous=previous.get(task_id, {}))
            )
        else:
            task_suffix = _repair_package_task_suffix(package_text, prefix="h_", fallback=package_path.stem)
            task_id = _safe_id(f"MGR_H_repair_{task_suffix}")
            packet_rows.append(
                _repair_package_packet(package_path, root=base, observed_utc=observed, previous=previous.get(task_id, {}))
            )

    existing_ids = {row.get("task_id", "") for row in packet_rows}
    for manual_path in _manual_task_files(base):
        manual_row = _manual_task_packet(
            manual_path,
            root=base,
            observed_utc=observed,
            previous=previous.get(_safe_id(_field_value(manual_path.read_text(encoding="utf-8"), "task_id") or manual_path.stem), {}),
        )
        if manual_row is None or manual_row.get("task_id") in existing_ids:
            continue
        packet_rows.append(manual_row)
        existing_ids.add(manual_row.get("task_id", ""))

    _assign_unique_job_refs(packet_rows)
    for row in packet_rows:
        if row.get("source_type") == MANUAL_TASK_SOURCE_TYPE:
            _rewrite_manual_packet_status(row)

    packet_rows = sorted(packet_rows, key=_priority_key)
    write_csv(index_path, APPROVED_TASK_PACKET_COLUMNS, packet_rows)
    _write_packets(base, packet_rows, mot_rows, manager_rows, repair_package_sources)
    _backfill_existing_packet_markdown_job_refs(base, packet_rows)
    return {
        "index_path": index_path,
        "approved_count": sum(1 for row in packet_rows if row.get("status") in SAFE_ACTIVE_STATUSES),
        "blocked_count": sum(1 for row in packet_rows if row.get("status") in BLOCKED_STATUSES),
        "rows": packet_rows,
    }


def active_safe_task_packets(*, root: Path | str | None = None) -> list[dict[str, str]]:
    rows = read_csv_rows(approved_task_index_path(root))
    return sorted([row for row in rows if row.get("status") in SAFE_ACTIVE_STATUSES], key=_priority_key)


def blocked_task_packets(*, root: Path | str | None = None) -> list[dict[str, str]]:
    rows = read_csv_rows(approved_task_index_path(root))
    return sorted([row for row in rows if row.get("status") in BLOCKED_STATUSES], key=_priority_key)


def claim_next_approved_task(*, root: Path | str | None = None, observed_utc: str | None = None) -> dict[str, str]:
    paths = get_manager_paths(root)
    index_path = approved_task_index_path(paths.root)
    rows = read_csv_rows(index_path)
    observed = observed_utc or utc_now_text()
    candidates = [row for row in rows if row.get("status") in {"approved", "retest_failed", "reopened"} and row.get("luke_action_required") != "1"]
    if not candidates:
        raise ValueError("No approved manager task is available to claim.")
    chosen_id = sorted(candidates, key=_priority_key)[0]["task_id"]
    changed = _update_packet_row(paths.root, rows, chosen_id, "in_progress", observed, "Claimed by Codex from manager-approved task packet.")
    write_csv(index_path, APPROVED_TASK_PACKET_COLUMNS, rows)
    _sync_mot_status_if_needed(paths.output_dir, changed, "in_progress", observed)
    _rewrite_single_packet(paths.root, changed)
    return changed


def update_approved_task_status(
    *,
    root: Path | str | None = None,
    task_id: str,
    status: str,
    note: str = "",
    observed_utc: str | None = None,
) -> dict[str, str]:
    if status not in PACKET_STATUSES:
        raise ValueError(f"unsupported approved task status: {status}")
    paths = get_manager_paths(root)
    index_path = approved_task_index_path(paths.root)
    rows = read_csv_rows(index_path)
    observed = observed_utc or utc_now_text()
    changed = _update_packet_row(paths.root, rows, task_id, status, observed, note)
    write_csv(index_path, APPROVED_TASK_PACKET_COLUMNS, rows)
    _sync_mot_status_if_needed(paths.output_dir, changed, status, observed)
    _rewrite_single_packet(paths.root, changed)
    return changed


def _update_packet_row(root: Path, rows: list[dict[str, str]], task_id: str, status: str, observed: str, note: str) -> dict[str, str]:
    row = _resolve_task_identifier(rows, task_id)
    row["status"] = status
    row["updated_utc"] = observed
    if status == "blocked_needs_luke":
        row["luke_action_required"] = "1"
    elif status in SAFE_ACTIVE_STATUSES or status in TERMINAL_STATUSES:
        row["luke_action_required"] = "0"
    if note:
        row["notes"] = note
    if row.get("source_type") != MANUAL_TASK_SOURCE_TYPE:
        row["packet_path"] = str(_packet_path(root, row.get("task_id", ""), status))
    return row


def _sync_mot_status_if_needed(output_dir: Path, row: dict[str, str], status: str, observed: str) -> None:
    if row.get("source_type") != "mot":
        return
    mot_status = status
    if mot_status == "approved":
        mot_status = "assigned"
    if mot_status not in {"assigned", "in_progress", "fixed_needs_retest", "retest_failed", "proved", "parked", "blocked_needs_luke"}:
        return
    update_mot_work_item_status(
        output_dir=output_dir,
        work_item_id=row.get("source_id", ""),
        status=mot_status,
        note=row.get("notes", ""),
        observed_utc=observed,
    )


def _rewrite_single_packet(root: Path, row: dict[str, str]) -> None:
    if row.get("source_type") == MANUAL_TASK_SOURCE_TYPE:
        _rewrite_manual_packet_status(row)
        return
    path = _packet_path(root, row.get("task_id", ""), row.get("status", "approved"))
    row["packet_path"] = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output_dir = get_manager_paths(root).output_dir
    mot_rows = read_csv_rows(output_dir / "mot" / "mot_worklist.csv")
    manager_rows = read_csv_rows(output_dir / "manager_task_candidates.csv")
    repair_package_sources = [
        {"source_id": path.stem, "source_path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path)}
        for path in _repair_package_rows(root)
    ]
    payload = _source_payload(
        row.get("source_type", ""),
        row.get("source_id", ""),
        mot_rows,
        manager_rows,
        repair_package_sources,
    )
    path.write_text(_packet_markdown(row, payload), encoding="utf-8")


def _rewrite_manual_packet_status(row: dict[str, str]) -> None:
    path_text = row.get("packet_path", "")
    if not path_text:
        return
    path = Path(path_text)
    if not path.exists():
        return
    markdown = path.read_text(encoding="utf-8")
    markdown = re.sub(r"^(\s*-\s*status\s*:\s*).*$", rf"\g<1>{row.get('status', '')}", markdown, flags=re.MULTILINE)
    markdown = re.sub(
        r"^(\s*-\s*luke_action_required\s*:\s*).*$",
        rf"\g<1>{row.get('luke_action_required', '')}",
        markdown,
        flags=re.MULTILINE,
    )
    job_ref = row.get("job_ref", "")
    if re.search(r"^\s*-\s*job_ref\s*:", markdown, flags=re.MULTILINE):
        markdown = re.sub(
            r"^(\s*-\s*job_ref\s*:\s*).*$",
            rf"\g<1>{job_ref}",
            markdown,
            flags=re.MULTILINE,
        )
    else:
        markdown = re.sub(
            r"^(\s*-\s*task_id\s*:\s*.*)$",
            rf"\1\n- job_ref: {job_ref}",
            markdown,
            count=1,
            flags=re.MULTILINE,
        )
        if "- job_ref:" not in markdown and "## Manager Authority" in markdown:
            markdown = markdown.replace("## Manager Authority", f"## Manager Authority\n- job_ref: {job_ref}", 1)
    path.write_text(markdown, encoding="utf-8")


def _backfill_existing_packet_markdown_job_refs(root: Path, packet_rows: list[dict[str, str]]) -> None:
    rows_by_task_id = {row.get("task_id", ""): row for row in packet_rows if row.get("task_id")}
    used: dict[str, int] = {}
    for row in packet_rows:
        ref = _normalise_job_ref(row.get("job_ref", ""), row.get("flow", ""))
        if ref:
            used[ref] = max(used.get(ref, 0), 1)

    for path in _manual_task_files(root):
        markdown = path.read_text(encoding="utf-8", errors="ignore")
        task_id = _safe_id(_field_value(markdown, "task_id") or path.stem)
        flow = _field_value(markdown, "flow") or _flow_from_task_id(task_id)
        current_ref = _normalise_job_ref(_field_value(markdown, "job_ref"), flow)
        if current_ref:
            used[current_ref] = max(used.get(current_ref, 0), 1)
            continue
        row = rows_by_task_id.get(task_id, {})
        ref = row.get("job_ref") or _generated_job_ref(
            {
                "task_id": task_id,
                "flow": row.get("flow") or flow,
                "title": row.get("title") or _markdown_title(markdown, task_id),
                "source_id": row.get("source_id") or _field_value(markdown, "source_id"),
            }
        )
        ref = _normalise_job_ref(ref, row.get("flow") or flow)
        count = used.get(ref, 0) + 1
        used[ref] = count
        if count > 1:
            ref = f"{ref}-{count:02d}"
        updated = _insert_or_update_job_ref(markdown, ref)
        if updated != markdown:
            path.write_text(updated, encoding="utf-8")


def _insert_or_update_job_ref(markdown: str, job_ref: str) -> str:
    if re.search(r"^\s*-\s*job_ref\s*:", markdown, flags=re.MULTILINE):
        return re.sub(
            r"^(\s*-\s*job_ref\s*:\s*).*$",
            rf"\g<1>{job_ref}",
            markdown,
            flags=re.MULTILINE,
        )
    updated = re.sub(
        r"^(\s*-\s*task_id\s*:\s*.*)$",
        rf"\1\n- job_ref: {job_ref}",
        markdown,
        count=1,
        flags=re.MULTILINE,
    )
    if updated != markdown:
        return updated
    if "## Manager Authority" in markdown:
        return markdown.replace("## Manager Authority", f"## Manager Authority\n- job_ref: {job_ref}", 1)
    return f"- job_ref: {job_ref}\n{markdown}"
