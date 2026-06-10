from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import get_manager_paths, resolve_repo_path
from .schemas import (
    CODEX_REPAIR_EVENT_COLUMNS,
    CODEX_REPAIR_QUEUE_COLUMNS,
    CODEX_REPAIR_TASK_STATUSES,
    HEALTH_COLUMNS,
    INCIDENT_COLUMNS,
    SELF_ORGANISATION_COLUMNS,
    SNAPSHOT_COLUMNS,
    blank_row,
    duplicate_headers,
    validate_manifest,
)
from .self_organisation import build_f_script_registration_report, write_f_self_organisation_outputs


def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    return rows, fieldnames


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def append_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _load_manifest(root: Path, module_id: str) -> tuple[dict[str, Any], Path]:
    path = root / "config" / "manager" / "modules" / f"{module_id}.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle), path


def _health_row(
    *,
    check: str,
    status: str,
    value: str,
    notes: str,
    observed_utc: str,
    source_path: Path | str,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": value,
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _incident_row(
    *,
    observed_utc: str,
    flow: str,
    severity: str,
    incident_code: str,
    summary: str,
    needs_user: str,
    root_artifact: str,
    remediation_hint: str,
) -> dict[str, str]:
    return {
        "observed_utc": observed_utc,
        "flow": flow,
        "severity": severity,
        "incident_code": incident_code,
        "summary": summary,
        "needs_user": needs_user,
        "root_artifact": root_artifact,
        "remediation_hint": remediation_hint,
    }


def _repair_task_from_incident(row: dict[str, str]) -> dict[str, str]:
    flow = row.get("flow", "X")
    incident_code = row.get("incident_code", "incident")
    root_artifact = row.get("root_artifact", "")
    stable_key = hashlib.sha1(f"{flow}|{incident_code}|{root_artifact}".encode("utf-8")).hexdigest()[:10]
    observed = row.get("observed_utc", "")
    return {
        "observed_utc": observed,
        "created_utc": observed,
        "updated_utc": observed,
        "last_seen_utc": observed,
        "seen_count": "1",
        "flow": flow,
        "task_id": f"{flow}_{incident_code}_{stable_key}",
        "owner": "Codex",
        "priority": "high" if row.get("severity") in {"blocked", "fail"} else "normal",
        "status": "queued",
        "source_incident_code": incident_code,
        "task_summary": row.get("summary", ""),
        "root_artifact": root_artifact,
        "allowed_scope": "manager planning and scoped Codex repair investigation only until user approves worker changes",
        "forbidden_actions": "no Google Sheets writes; no local DB alignment; no F061 queue edit; no A/B/E/H/F worker run; no worker restart",
        "proof_required": "manager report updated with root cause, allowed repair scope, and no user task unless a real decision is needed",
    }


def _repair_event_row(
    *,
    event_utc: str,
    task_id: str,
    event_type: str,
    old_status: str,
    new_status: str,
    actor: str,
    note: str,
    source: str,
) -> dict[str, str]:
    return {
        "event_utc": event_utc,
        "task_id": task_id,
        "event_type": event_type,
        "old_status": old_status,
        "new_status": new_status,
        "actor": actor,
        "note": note,
        "source": source,
    }


def merge_codex_repair_queue(existing_rows: list[dict[str, str]], current_rows: list[dict[str, str]], observed_utc: str) -> list[dict[str, str]]:
    by_id = {row.get("task_id", ""): dict(row) for row in existing_rows if row.get("task_id")}
    by_semantic_key = {
        _repair_semantic_key(row): dict(row)
        for row in existing_rows
        if _repair_semantic_key(row)
    }
    current_ids = {row.get("task_id", "") for row in current_rows if row.get("task_id")}
    current_semantic_keys = {_repair_semantic_key(row) for row in current_rows if _repair_semantic_key(row)}
    merged: dict[str, dict[str, str]] = {}
    closed_statuses = {"completed", "resolved", "cancelled", "cleared_pending_review"}

    for row in current_rows:
        task_id = row.get("task_id", "")
        if not task_id:
            continue
        previous = by_id.get(task_id) or by_semantic_key.get(_repair_semantic_key(row), {})
        seen_count_raw = previous.get("seen_count", "0")
        try:
            seen_count = int(float(seen_count_raw or "0")) + 1
        except ValueError:
            seen_count = 1
        status = previous.get("status") or row.get("status", "queued")
        if status in closed_statuses:
            status = "reopened"
        merged_row = dict(row)
        merged_row.update(
            {
                "created_utc": previous.get("created_utc") or previous.get("observed_utc") or row.get("created_utc") or observed_utc,
                "updated_utc": observed_utc,
                "last_seen_utc": observed_utc,
                "seen_count": str(seen_count),
                "status": status,
                "owner": previous.get("owner") or row.get("owner", "Codex"),
            }
        )
        merged[task_id] = merged_row

    for task_id, previous in by_id.items():
        if task_id in current_ids:
            continue
        if _repair_semantic_key(previous) in current_semantic_keys:
            continue
        carried = dict(previous)
        if carried.get("status") in {"queued", "in_progress", "reopened"}:
            carried["status"] = "cleared_pending_review"
            carried["updated_utc"] = observed_utc
        merged[task_id] = carried

    return sorted(merged.values(), key=lambda row: (row.get("status", ""), row.get("created_utc", ""), row.get("task_id", "")))


def build_codex_repair_events(
    existing_rows: list[dict[str, str]],
    merged_rows: list[dict[str, str]],
    current_rows: list[dict[str, str]],
    observed_utc: str,
    *,
    actor: str = "manager",
    source: str = "read_only_snapshot",
) -> list[dict[str, str]]:
    by_id = {row.get("task_id", ""): dict(row) for row in existing_rows if row.get("task_id")}
    by_semantic_key = {
        _repair_semantic_key(row): dict(row)
        for row in existing_rows
        if _repair_semantic_key(row)
    }
    current_ids = {row.get("task_id", "") for row in current_rows if row.get("task_id")}
    current_semantic_keys = {_repair_semantic_key(row) for row in current_rows if _repair_semantic_key(row)}
    events: list[dict[str, str]] = []

    for row in merged_rows:
        task_id = row.get("task_id", "")
        if not task_id:
            continue
        semantic_key = _repair_semantic_key(row)
        previous = by_id.get(task_id) or by_semantic_key.get(semantic_key, {})
        previous_status = previous.get("status", "")
        new_status = row.get("status", "")

        event_type = ""
        note = row.get("task_summary", "")
        if not previous:
            event_type = "created"
        elif previous.get("task_id") != task_id:
            event_type = "migrated_to_stable_id"
            note = f"Task ID changed from {previous.get('task_id')} to {task_id}."
        elif previous_status != new_status:
            event_type = "status_changed"
        elif task_id in current_ids or semantic_key in current_semantic_keys:
            continue

        if not event_type:
            continue
        events.append(
            _repair_event_row(
                event_utc=observed_utc,
                task_id=task_id,
                event_type=event_type,
                old_status=previous_status,
                new_status=new_status,
                actor=actor,
                note=note,
                source=source,
            )
        )

    return events


def _repair_semantic_key(row: dict[str, str]) -> str:
    flow = row.get("flow", "")
    incident = row.get("source_incident_code", "")
    root_artifact = row.get("root_artifact", "")
    if not flow or not incident or not root_artifact:
        return ""
    return f"{flow}|{incident}|{root_artifact}"


def update_codex_repair_task_status(
    *,
    output_dir: Path,
    task_id: str,
    status: str,
    note: str = "",
    actor: str = "Codex",
    observed_utc: str | None = None,
) -> dict[str, str]:
    if status not in CODEX_REPAIR_TASK_STATUSES:
        allowed = ", ".join(sorted(CODEX_REPAIR_TASK_STATUSES))
        raise ValueError(f"unsupported task status: {status}; allowed: {allowed}")

    observed = observed_utc or utc_now_text()
    queue_path = output_dir / "codex_repair_queue.csv"
    event_path = output_dir / "codex_repair_events.csv"
    if not queue_path.exists():
        raise FileNotFoundError(f"repair queue not found: {queue_path}")

    rows, _fieldnames = read_csv_rows(queue_path)
    matched = False
    old_status = ""
    for row in rows:
        if row.get("task_id") != task_id:
            continue
        matched = True
        old_status = row.get("status", "")
        row["status"] = status
        row["updated_utc"] = observed
        break

    if not matched:
        raise ValueError(f"task not found in repair queue: {task_id}")

    write_csv(queue_path, CODEX_REPAIR_QUEUE_COLUMNS, rows)
    append_csv(
        event_path,
        CODEX_REPAIR_EVENT_COLUMNS,
        [
            _repair_event_row(
                event_utc=observed,
                task_id=task_id,
                event_type="manual_status_update",
                old_status=old_status,
                new_status=status,
                actor=actor,
                note=note,
                source="manager_cli",
            )
        ],
    )
    return {
        "task_id": task_id,
        "old_status": old_status,
        "new_status": status,
        "queue_path": str(queue_path),
        "event_path": str(event_path),
    }


def _source_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for group in ["status_sources", "health_sources", "outputs"]:
        for source in manifest.get(group, []):
            if isinstance(source, dict):
                merged = dict(source)
                merged["group"] = group
                entries.append(merged)
    return entries


def _source_by_name(manifest: dict[str, Any], name: str) -> dict[str, Any] | None:
    for source in _source_entries(manifest):
        if source.get("name") == name:
            return source
    return None


def _age_minutes(path: Path, observed_dt: datetime) -> float:
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return max((observed_dt - modified).total_seconds() / 60.0, 0.0)


def _check_manifest_sources(
    root: Path,
    manifest: dict[str, Any],
    observed_utc: str,
    observed_dt: datetime,
) -> tuple[list[dict[str, str]], bool]:
    health: list[dict[str, str]] = []
    stale_evidence = False
    for source in _source_entries(manifest):
        name = str(source.get("name", "unnamed_source"))
        source_path = resolve_repo_path(root, str(source.get("path", "")))
        required = bool(source.get("required", False))
        max_age_minutes = source.get("max_age_minutes")

        if not source_path.exists():
            status = "fail" if required else "warn"
            stale_evidence = True
            health.append(
                _health_row(
                    check=f"source_exists:{name}",
                    status=status,
                    value="missing",
                    notes=f"required={int(required)}",
                    observed_utc=observed_utc,
                    source_path=source_path,
                )
            )
            continue

        health.append(
            _health_row(
                check=f"source_exists:{name}",
                status="ok",
                value="exists",
                notes=f"required={int(required)}",
                observed_utc=observed_utc,
                source_path=source_path,
            )
        )
        if max_age_minutes is None:
            continue
        try:
            age = _age_minutes(source_path, observed_dt)
            age_text = f"{age:.1f}"
            if age > float(max_age_minutes):
                stale_evidence = True
                health.append(
                    _health_row(
                        check=f"source_freshness:{name}",
                        status="warn",
                        value=age_text,
                        notes=f"age_minutes>{max_age_minutes}",
                        observed_utc=observed_utc,
                        source_path=source_path,
                    )
                )
            else:
                health.append(
                    _health_row(
                        check=f"source_freshness:{name}",
                        status="ok",
                        value=age_text,
                        notes=f"age_minutes<={max_age_minutes}",
                        observed_utc=observed_utc,
                        source_path=source_path,
                    )
                )
        except (OSError, ValueError) as exc:
            stale_evidence = True
            health.append(
                _health_row(
                    check=f"source_freshness:{name}",
                    status="warn",
                    value="unknown",
                    notes=f"freshness_check_error:{exc}",
                    observed_utc=observed_utc,
                    source_path=source_path,
                )
            )
    return health, stale_evidence


def _read_optional_csv(
    root: Path,
    manifest: dict[str, Any],
    name: str,
    observed_utc: str,
    health: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str], Path | None]:
    source = _source_by_name(manifest, name)
    if not source:
        health.append(
            _health_row(
                check=f"source_configured:{name}",
                status="fail",
                value="missing",
                notes="manifest_source_not_found",
                observed_utc=observed_utc,
                source_path="manifest",
            )
        )
        return [], [], None
    path = resolve_repo_path(root, str(source["path"]))
    if not path.exists():
        return [], [], path
    try:
        rows, fieldnames = read_csv_rows(path)
    except OSError as exc:
        health.append(
            _health_row(
                check=f"source_readable:{name}",
                status="fail",
                value="error",
                notes=str(exc),
                observed_utc=observed_utc,
                source_path=path,
            )
        )
        return [], [], path

    duplicates = duplicate_headers(fieldnames)
    health.append(
        _health_row(
            check=f"schema_duplicate_headers:{name}",
            status="fail" if duplicates else "ok",
            value=",".join(duplicates) if duplicates else "0",
            notes="duplicate headers found" if duplicates else "no duplicate headers",
            observed_utc=observed_utc,
            source_path=path,
        )
    )
    return rows, fieldnames, path


def _latest_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return rows[-1] if rows else {}


def _recommended_dashboard_row(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if row.get("queue_state", "").strip().lower() == "recommended":
            return row
    for row in rows:
        if row.get("queue_position", "").strip() == "1":
            return row
    return rows[0] if rows else {}


def _is_storage_drift_block(live_row: dict[str, str]) -> bool:
    haystack = " ".join(
        [
            live_row.get("state", ""),
            live_row.get("last_action", ""),
            live_row.get("last_action_status", ""),
            live_row.get("notes", ""),
        ]
    ).lower()
    return "storage_drift" in haystack


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _storage_drift_report_clear_after_live_block(storage_rows: list[dict[str, str]], live_row: dict[str, str]) -> bool:
    if not storage_rows:
        return False
    live_observed = _parse_utc(live_row.get("observed_utc", ""))
    latest_storage_observed = max(
        (parsed for parsed in (_parse_utc(row.get("observed_utc", "")) for row in storage_rows) if parsed is not None),
        default=None,
    )
    if live_observed is not None and latest_storage_observed is not None and latest_storage_observed < live_observed:
        return False
    for row in storage_rows:
        status_after = row.get("status_after", "").strip().lower()
        action = row.get("action", "").strip().lower()
        if status_after not in {"ok", "skipped"}:
            return False
        if action == "blocked":
            return False
    return True


def _classify_f_state(
    *,
    manifest: dict[str, Any],
    dashboard_row: dict[str, str],
    live_row: dict[str, str],
    live_path: Path | None,
    dashboard_path: Path | None,
    storage_rows: list[dict[str, str]],
    storage_path: Path | None,
    stale_evidence: bool,
    observed_utc: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    flow = str(manifest.get("flow", "F"))
    module_id = str(manifest.get("id", "F_price_list_manager"))
    supplier_name = dashboard_row.get("supplier_name", "")
    supplier_id = dashboard_row.get("supplier_id", "")
    queue_state = dashboard_row.get("queue_state", "")
    live_state = live_row.get("state", "")
    evidence_paths = ";".join(str(path) for path in [dashboard_path, live_path, storage_path] if path)
    incidents: list[dict[str, str]] = []
    health: list[dict[str, str]] = []

    row = blank_row(SNAPSHOT_COLUMNS)
    row.update(
        {
            "observed_utc": observed_utc,
            "flow": flow,
            "module_id": module_id,
            "queue_supplier_id": supplier_id,
            "queue_supplier_name": supplier_name,
            "queue_state": queue_state,
            "queue_position": dashboard_row.get("queue_position", ""),
            "queue_web_unprocessed": dashboard_row.get("web_unprocessed", ""),
            "live_state": live_state,
            "live_last_action": live_row.get("last_action", ""),
            "live_last_action_status": live_row.get("last_action_status", ""),
            "live_pending_rows": live_row.get("pending_rows", ""),
            "live_active_supplier_id": live_row.get("active_supplier_id", ""),
            "stale_evidence": "1" if stale_evidence else "0",
            "evidence_paths": evidence_paths,
        }
    )

    if not dashboard_row:
        row.update(
            {
                "status": "fail",
                "active_blocker_code": "missing_dashboard",
                "active_blocker_summary": "The manager cannot read the F queue dashboard.",
                "needs_user": "0",
                "user_action": "No user action. Codex needs to restore the F dashboard artifact first.",
                "safe_to_do_nothing": "0",
                "notes": "status_dashboard_missing_or_empty",
            }
        )
        incidents.append(
            _incident_row(
                observed_utc=observed_utc,
                flow=flow,
                severity="fail",
                incident_code="missing_dashboard",
                summary="The F queue dashboard is missing or empty.",
                needs_user="0",
                root_artifact=str(dashboard_path or ""),
                remediation_hint="Rebuild the F status dashboard from the F price-list manager at a safe boundary.",
            )
        )
        return row, health, incidents

    if not live_row:
        row.update(
            {
                "status": "fail",
                "active_blocker_code": "missing_live_status",
                "active_blocker_summary": "The manager cannot read the live F owner status.",
                "needs_user": "0",
                "user_action": "No user action. Codex needs to restore live owner status evidence first.",
                "safe_to_do_nothing": "0",
                "notes": "live_cycle_status_missing_or_empty",
            }
        )
        incidents.append(
            _incident_row(
                observed_utc=observed_utc,
                flow=flow,
                severity="fail",
                incident_code="missing_live_status",
                summary="The F live owner status is missing or empty.",
                needs_user="0",
                root_artifact=str(live_path or ""),
                remediation_hint="Restore the F live status writer before making queue decisions.",
            )
        )
        return row, health, incidents

    if _is_storage_drift_block(live_row):
        if _storage_drift_report_clear_after_live_block(storage_rows, live_row):
            row.update(
                {
                    "status": "stale_evidence",
                    "active_blocker_code": "live_owner_status_stale_after_storage_repair",
                    "active_blocker_summary": (
                        "The storage drift report is now clear, but the live F owner has not refreshed its "
                        "older blocked status yet."
                    ),
                    "needs_user": "0",
                    "user_action": "No Luke action required. Codex should wait for the next F owner status refresh or run a separately approved proof.",
                    "safe_to_do_nothing": "1",
                    "notes": "storage_drift_report_clear_live_status_stale",
                }
            )
            return row, health, incidents

        summary = (
            f"F price-list manager is blocked by storage drift before it can start "
            f"the recommended {supplier_name or supplier_id or 'supplier'} scan."
        )
        row.update(
            {
                "status": "blocked",
                "active_blocker_code": "storage_drift_preflight",
                "active_blocker_summary": summary,
                "needs_user": "0",
                "user_action": "No Luke action required unless Codex asks for repair approval.",
                "safe_to_do_nothing": "0",
                "notes": "live_owner_blocker_beats_supplier_queue_state",
            }
        )
        incidents.append(
            _incident_row(
                observed_utc=observed_utc,
                flow=flow,
                severity="blocked",
                incident_code="storage_drift_preflight",
                summary=summary,
                needs_user="0",
                root_artifact=str(live_path or ""),
                remediation_hint="Fix the F storage drift root cause before retrying CLF or any other supplier scan.",
            )
        )
        return row, health, incidents

    if "needs manual file" in queue_state.lower():
        summary = f"{supplier_name or supplier_id or 'A supplier'} needs a manual price file."
        row.update(
            {
                "status": "needs_user",
                "active_blocker_code": "manual_file_needed",
                "active_blocker_summary": summary,
                "needs_user": "1",
                "user_action": f"Supply the missing price file for {supplier_name or supplier_id}.",
                "safe_to_do_nothing": "0",
                "notes": "queue_needs_manual_file",
            }
        )
        incidents.append(
            _incident_row(
                observed_utc=observed_utc,
                flow=flow,
                severity="needs_user",
                incident_code="manual_file_needed",
                summary=summary,
                needs_user="1",
                root_artifact=str(dashboard_path or ""),
                remediation_hint="Add the supplier file to the configured inbox, then let the normal F manager import it.",
            )
        )
        return row, health, incidents

    if live_state.lower() in {"running", "idle", "completed"}:
        row.update(
            {
                "status": "ok",
                "active_blocker_code": "",
                "active_blocker_summary": "No active F manager blocker detected by the read-only manager.",
                "needs_user": "0",
                "user_action": "No user action.",
                "safe_to_do_nothing": "1",
                "notes": "live_owner_state_clear",
            }
        )
        return row, health, incidents

    if live_state.lower().startswith("blocked_") or live_state.lower() == "blocked":
        summary = (
            live_row.get("notes", "").strip()
            or f"F live owner state is {live_state} and needs a bounded manager repair path."
        )
        needs_protected_decision = live_state.lower() == "blocked_source_shape_guard"
        row.update(
            {
                "status": "needs_user" if needs_protected_decision else "blocked",
                "active_blocker_code": live_state.lower(),
                "active_blocker_summary": summary,
                "needs_user": "1" if needs_protected_decision else "0",
                "user_action": (
                    "Approve a bounded F source-shape recovery preview for the active row, or leave F parked."
                    if needs_protected_decision
                    else "No Luke action required unless Codex asks for a protected repair decision."
                ),
                "safe_to_do_nothing": "0",
                "notes": "live_owner_blocked_state_classified",
            }
        )
        incidents.append(
            _incident_row(
                observed_utc=observed_utc,
                flow=flow,
                severity="needs_user" if needs_protected_decision else "blocked",
                incident_code=live_state.lower(),
                summary=summary,
                needs_user="1" if needs_protected_decision else "0",
                root_artifact=str(live_path or ""),
                remediation_hint=(
                    "Create a protected preview-only F source-shape recovery packet before changing scanner data."
                    if needs_protected_decision
                    else "Package the live F blocker into a bounded manager task before touching scanner data."
                ),
            )
        )
        return row, health, incidents

    row.update(
        {
            "status": "warn",
            "active_blocker_code": "unclassified_live_state",
            "active_blocker_summary": f"F live owner state is {live_state or 'blank'} and needs classification.",
            "needs_user": "0",
            "user_action": "No user action. Codex should classify this live state before changing worker behavior.",
            "safe_to_do_nothing": "0",
            "notes": "manager_v1_unclassified_state",
        }
    )
    incidents.append(
        _incident_row(
            observed_utc=observed_utc,
            flow=flow,
            severity="warn",
            incident_code="unclassified_live_state",
            summary=row["active_blocker_summary"],
            needs_user="0",
            root_artifact=str(live_path or ""),
            remediation_hint="Add a deterministic classification for this live owner state.",
        )
    )
    return row, health, incidents


def _is_worker_like(row: dict[str, str], manifest: dict[str, Any]) -> bool:
    path = row.get("path", "")
    flow_group = row.get("flow_group", "")
    inferred_role = row.get("inferred_role", "")
    if not path:
        return False
    if path in {manifest.get("owner_entrypoint", ""), manifest.get("worker_entrypoint", "")}:
        return True
    if flow_group == "F" and re.search(r"(?:^|/)(FPM|F)\d+_run|(?:^|/)run_", path):
        return True
    if path.startswith("run_F_") and inferred_role == "batch_entrypoint":
        return True
    return False


def build_self_organisation_rows(
    *,
    root: Path,
    manifest: dict[str, Any],
    observed_utc: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    inventory_path = root / "project_control" / "SCRIPT_INVENTORY.csv"
    if not inventory_path.exists():
        return [], _health_row(
            check="self_organisation_guard",
            status="warn",
            value="inventory_missing",
            notes="project_control/SCRIPT_INVENTORY.csv not found",
            observed_utc=observed_utc,
            source_path=inventory_path,
        )

    rows, _fieldnames = read_csv_rows(inventory_path)
    covered = {str(manifest.get("owner_entrypoint", "")), str(manifest.get("worker_entrypoint", ""))}
    gap_rows: list[dict[str, str]] = []
    for row in rows:
        path = row.get("path", "")
        if not _is_worker_like(row, manifest):
            continue
        if path in covered:
            status = "ok"
            notes = "covered_by_manager_manifest"
        else:
            status = "warn"
            notes = "worker_like_script_not_yet_manifested_in_manager_v1"
        gap_rows.append(
            {
                "observed_utc": observed_utc,
                "script_path": path,
                "flow_group": row.get("flow_group", ""),
                "inferred_role": row.get("inferred_role", ""),
                "status": status,
                "notes": notes,
            }
        )

    warn_count = sum(1 for row in gap_rows if row["status"] == "warn")
    return gap_rows, _health_row(
        check="self_organisation_guard",
        status="warn" if warn_count else "ok",
        value=str(warn_count),
        notes="worker-like F scripts not yet covered by manager manifests",
        observed_utc=observed_utc,
        source_path=inventory_path,
    )


def build_f_price_list_snapshot(
    *,
    root: Path | str | None = None,
    observed_utc: str | None = None,
    module_id: str = "F_price_list_manager",
) -> dict[str, Any]:
    paths = get_manager_paths(root)
    base = paths.root
    observed = observed_utc or utc_now_text()
    observed_dt = datetime.fromisoformat(observed.replace("Z", "+00:00"))

    health: list[dict[str, str]] = []
    incidents: list[dict[str, str]] = []
    self_rows: list[dict[str, str]] = []

    try:
        manifest, manifest_path = _load_manifest(base, module_id)
    except (OSError, json.JSONDecodeError) as exc:
        row = blank_row(SNAPSHOT_COLUMNS)
        row.update(
            {
                "observed_utc": observed,
                "flow": "F",
                "module_id": module_id,
                "status": "fail",
                "active_blocker_code": "manifest_unreadable",
                "active_blocker_summary": f"Manager manifest could not be read: {exc}",
                "needs_user": "0",
                "safe_to_do_nothing": "0",
                "stale_evidence": "1",
            }
        )
        health.append(
            _health_row(
                check="manifest_contract",
                status="fail",
                value="unreadable",
                notes=str(exc),
                observed_utc=observed,
                source_path=base / "config" / "manager" / "modules" / f"{module_id}.json",
            )
        )
        return {
            "manifest": {},
            "snapshot_rows": [row],
            "health_rows": health,
            "incident_rows": incidents,
            "self_organisation_rows": self_rows,
            "codex_repair_queue_rows": [],
        }

    manifest_errors = validate_manifest(manifest)
    health.append(
        _health_row(
            check="manifest_contract",
            status="fail" if manifest_errors else "ok",
            value=str(len(manifest_errors)),
            notes=";".join(manifest_errors) if manifest_errors else "manifest valid",
            observed_utc=observed,
            source_path=manifest_path,
        )
    )

    source_health, stale_evidence = _check_manifest_sources(base, manifest, observed, observed_dt)
    health.extend(source_health)

    dashboard_rows, _dashboard_fields, dashboard_path = _read_optional_csv(
        base,
        manifest,
        "status_dashboard",
        observed,
        health,
    )
    live_rows, _live_fields, live_path = _read_optional_csv(
        base,
        manifest,
        "live_cycle_status",
        observed,
        health,
    )
    storage_rows, _storage_fields, storage_path = _read_optional_csv(
        base,
        manifest,
        "storage_drift_report",
        observed,
        health,
    )

    snapshot_row, classifier_health, classifier_incidents = _classify_f_state(
        manifest=manifest,
        dashboard_row=_recommended_dashboard_row(dashboard_rows),
        live_row=_latest_row(live_rows),
        live_path=live_path,
        dashboard_path=dashboard_path,
        storage_rows=storage_rows,
        storage_path=storage_path,
        stale_evidence=stale_evidence,
        observed_utc=observed,
    )
    health.extend(classifier_health)
    incidents.extend(classifier_incidents)

    if manifest_errors:
        snapshot_row["status"] = "fail"
        snapshot_row["active_blocker_code"] = "manifest_contract"
        snapshot_row["active_blocker_summary"] = "The manager manifest is incomplete or invalid."
        snapshot_row["safe_to_do_nothing"] = "0"

    self_rows, self_health = build_self_organisation_rows(root=base, manifest=manifest, observed_utc=observed)
    f_script_registration_report = build_f_script_registration_report(
        root=base,
        manifest=manifest,
        observed_utc=observed,
    )
    health.append(self_health)
    health.append(
        _health_row(
            check="manager_execution",
            status="ok",
            value="0",
            notes="0 active manager execution errors",
            observed_utc=observed,
            source_path="sellerone_manager",
        )
    )

    return {
        "manifest": manifest,
        "snapshot_rows": [snapshot_row],
        "health_rows": health,
        "incident_rows": incidents,
        "self_organisation_rows": self_rows,
        "f_script_registration_report": f_script_registration_report,
        "codex_repair_queue_rows": [_repair_task_from_incident(row) for row in incidents if row.get("needs_user") != "1"],
    }


def write_f_price_list_outputs(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "snapshot_csv": output_dir / "f_price_list_manager_snapshot.csv",
        "snapshot_json": output_dir / "f_price_list_manager_snapshot.json",
        "health_csv": output_dir / "manager_health.csv",
        "incidents_csv": output_dir / "manager_incidents.csv",
        "codex_repair_queue_csv": output_dir / "codex_repair_queue.csv",
        "codex_repair_events_csv": output_dir / "codex_repair_events.csv",
        "self_organisation_csv": output_dir / "self_organisation_gaps.csv",
    }
    existing_repair_rows: list[dict[str, str]] = []
    if paths["codex_repair_queue_csv"].exists():
        try:
            existing_repair_rows, _fieldnames = read_csv_rows(paths["codex_repair_queue_csv"])
        except OSError:
            existing_repair_rows = []
    event_log_has_rows = False
    if paths["codex_repair_events_csv"].exists():
        try:
            existing_event_rows, _event_fields = read_csv_rows(paths["codex_repair_events_csv"])
            event_log_has_rows = bool(existing_event_rows)
        except OSError:
            event_log_has_rows = False
    observed_utc = result["snapshot_rows"][0].get("observed_utc", utc_now_text()) if result["snapshot_rows"] else utc_now_text()
    repair_rows = merge_codex_repair_queue(
        existing_repair_rows,
        result["codex_repair_queue_rows"],
        observed_utc,
    )
    repair_events = build_codex_repair_events(
        existing_repair_rows,
        repair_rows,
        result["codex_repair_queue_rows"],
        observed_utc,
    )
    if not event_log_has_rows and existing_repair_rows:
        repair_events = [
            _repair_event_row(
                event_utc=observed_utc,
                task_id=row.get("task_id", ""),
                event_type="backfilled_existing_task",
                old_status="",
                new_status=row.get("status", ""),
                actor="manager",
                note="Event log was created after this queue task already existed.",
                source="event_log_backfill",
            )
            for row in existing_repair_rows
            if row.get("task_id")
        ] + repair_events
    result["codex_repair_queue_rows"] = repair_rows
    result["codex_repair_event_rows"] = repair_events

    write_csv(paths["snapshot_csv"], SNAPSHOT_COLUMNS, result["snapshot_rows"])
    write_csv(paths["health_csv"], HEALTH_COLUMNS, result["health_rows"])
    write_csv(paths["incidents_csv"], INCIDENT_COLUMNS, result["incident_rows"])
    write_csv(paths["codex_repair_queue_csv"], CODEX_REPAIR_QUEUE_COLUMNS, result["codex_repair_queue_rows"])
    append_csv(paths["codex_repair_events_csv"], CODEX_REPAIR_EVENT_COLUMNS, repair_events)
    write_csv(paths["self_organisation_csv"], SELF_ORGANISATION_COLUMNS, result["self_organisation_rows"])
    if result.get("f_script_registration_report"):
        paths.update(write_f_self_organisation_outputs(result["f_script_registration_report"], output_dir))
    with paths["snapshot_json"].open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "snapshot": result["snapshot_rows"],
                "health": result["health_rows"],
                "incidents": result["incident_rows"],
                "codex_repair_queue": result["codex_repair_queue_rows"],
                "codex_repair_events": result["codex_repair_event_rows"],
                "self_organisation": result["self_organisation_rows"],
                "f_script_registration": result.get("f_script_registration_report", {}),
            },
            handle,
            indent=2,
        )
        handle.write("\n")
    return paths


def output_headers_are_clean(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        _rows, fieldnames = read_csv_rows(path)
        duplicates = duplicate_headers(fieldnames)
        if duplicates:
            errors.append(f"{path}:{','.join(duplicates)}")
    return errors
