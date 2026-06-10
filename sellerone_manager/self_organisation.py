from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .schemas import F_MANIFEST_PRIORITY_COLUMNS, F_SCRIPT_REGISTRATION_COLUMNS


SCRIPT_INVENTORY_REL_PATH = "project_control/SCRIPT_INVENTORY.csv"
SELF_ORG_OUTPUT_DIRNAME = "self_organisation"
F_PRICE_LIST_RUNBOOK = "project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md"
RECENT_SCRIPT_DAYS = 45

PRIORITY_CONTEXT_PATHS = [
    "config/runtime_owner_contract.json",
    "out/systems/F/price_list_manager/live/live_cycle_status.csv",
    "out/systems/F/price_list_manager/live/live_cycle_health.csv",
    "out/systems/F/price_list_manager/live/live_cycle_events.csv",
    "out/systems/F/price_list_manager/live/storage_drift_report.csv",
    "out/systems/F/price_list_manager/test_mode/status_dashboard.csv",
    "out/systems/F/inbox/supplier_price_list_active_run.csv",
    "out/systems/F/inbox/supplier_price_list_run_state.csv",
]

RegistrationEntry = dict[str, Any]


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    return rows, fieldnames


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return path


def _repo_rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/")


def _script_basename(path: str) -> str:
    return Path(path).name


def _mtime_utc(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except OSError:
        return ""


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _starts_with_numbered_f_script(name: str) -> bool:
    return bool(re.match(r"^(?:FPM|F)\d+_", name))


def _is_f_related_inventory_row(row: dict[str, str]) -> bool:
    path = _normalize_path(row.get("path", ""))
    name = _script_basename(path)
    if not path:
        return False
    if row.get("flow_group", "") == "F":
        return True
    if path.startswith("scripts/flows/F/"):
        return True
    if path.startswith("scripts/one_off/") and _starts_with_numbered_f_script(name):
        return True
    if path.startswith("run_F_"):
        return True
    return False


def _is_worker_like_path(path: str, inventory_row: dict[str, str] | None = None) -> bool:
    normalized = _normalize_path(path)
    name = _script_basename(normalized)
    extension = Path(normalized).suffix.lower()
    if not normalized:
        return False
    if normalized.startswith("scripts/flows/F/legacy_scanner_2_1/"):
        return True
    if normalized.startswith("scripts/one_off/") and _starts_with_numbered_f_script(name):
        return True
    if normalized.startswith("scripts/flows/F/") and _starts_with_numbered_f_script(name):
        return True
    if normalized.startswith("run_F_"):
        return True
    if inventory_row and inventory_row.get("flow_group") == "F":
        if extension in {".bat", ".ps1"}:
            return True
        if extension == ".py" and inventory_row.get("has_python_main_guard") == "1":
            return True
    return False


def _discover_f_scripts(root: Path) -> tuple[dict[str, dict[str, str]], bool]:
    discovered: dict[str, dict[str, str]] = {}
    inventory_path = root / SCRIPT_INVENTORY_REL_PATH
    inventory_exists = inventory_path.exists()
    if inventory_exists:
        rows, _fieldnames = _read_csv_rows(inventory_path)
        for row in rows:
            path = _normalize_path(row.get("path", ""))
            if not _is_f_related_inventory_row(row):
                continue
            if not _is_worker_like_path(path, row):
                continue
            discovered[path] = {
                "path": path,
                "extension": row.get("extension", ""),
                "flow_group": row.get("flow_group", ""),
                "inferred_role": row.get("inferred_role", ""),
                "has_python_main_guard": row.get("has_python_main_guard", ""),
                "mtime_utc": row.get("mtime_utc", ""),
                "size_bytes": row.get("size_bytes", ""),
                "discovery_sources": "script_inventory",
            }

    scan_patterns = [
        "scripts/flows/F/**/*.py",
        "scripts/one_off/F*.py",
        "scripts/one_off/FPM*.py",
    ]
    for pattern in scan_patterns:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            rel_path = _repo_rel(path, root)
            if not _is_worker_like_path(rel_path):
                continue
            existing = discovered.get(rel_path, {"path": rel_path})
            sources = set(filter(None, existing.get("discovery_sources", "").split(";")))
            sources.add("filesystem")
            existing.update(
                {
                    "path": rel_path,
                    "extension": path.suffix,
                    "flow_group": existing.get("flow_group", "F") or "F",
                    "inferred_role": existing.get("inferred_role", "flow_script") or "flow_script",
                    "mtime_utc": existing.get("mtime_utc", "") or _mtime_utc(path),
                    "size_bytes": existing.get("size_bytes", "") or str(path.stat().st_size),
                    "discovery_sources": ";".join(sorted(sources)),
                }
            )
            discovered[rel_path] = existing

    return discovered, inventory_exists


def _load_f_manager_manifests(root: Path, primary_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = [primary_manifest]
    seen_ids = {str(primary_manifest.get("id", ""))}
    modules_dir = root / "config" / "manager" / "modules"
    if not modules_dir.exists():
        return manifests
    for path in sorted(modules_dir.glob("*.json")):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(manifest.get("flow", "")).strip() != "F":
            continue
        manifest_id = str(manifest.get("id", ""))
        if manifest_id in seen_ids:
            continue
        seen_ids.add(manifest_id)
        manifests.append(manifest)
    return manifests


def _registered_paths(manifest: dict[str, Any]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for field in ["owner_entrypoint", "worker_entrypoint"]:
        value = _normalize_path(str(manifest.get(field, "")))
        if value:
            paths[value] = field
    for field in ["registered_scripts", "entrypoints"]:
        raw_entries = manifest.get(field, [])
        if not isinstance(raw_entries, list):
            continue
        for entry in raw_entries:
            if isinstance(entry, str):
                value = _normalize_path(entry)
            elif isinstance(entry, dict):
                value = _normalize_path(str(entry.get("path", "")))
            else:
                value = ""
            if value:
                paths[value] = field
    return paths


def _registered_entries(manifests: list[dict[str, Any]]) -> dict[str, RegistrationEntry]:
    entries: dict[str, RegistrationEntry] = {}
    for manifest in manifests:
        for path, field in _registered_paths(manifest).items():
            entries[path] = {"field": field, "manifest": manifest}
    return entries


def _has_text(value: object) -> str:
    return "1" if str(value or "").strip() else "0"


def _has_list(value: object) -> str:
    return "1" if isinstance(value, list) and len(value) > 0 else "0"


def _runbook_link_for(root: Path, script_path: str, classification: str) -> str:
    runbook_path = root / F_PRICE_LIST_RUNBOOK
    if not runbook_path.exists():
        return ""
    if classification == "registered" or "/price_list_manager/" in script_path:
        return F_PRICE_LIST_RUNBOOK
    return ""


def _classify_script(
    *,
    root: Path,
    script: dict[str, str],
    manifest: dict[str, Any],
    registered: dict[str, RegistrationEntry],
    observed_utc: str,
) -> dict[str, str]:
    script_path = script["path"]
    registration = registered.get(script_path, {})
    registered_manifest = registration.get("manifest", manifest)
    registered_field = str(registration.get("field", ""))
    is_registered = bool(registration)
    is_one_off = script_path.startswith("scripts/one_off/")
    is_legacy = script_path.startswith("scripts/flows/F/legacy_scanner_2_1/")
    is_price_manager = script_path.startswith("scripts/flows/F/price_list_manager/")

    if is_registered:
        classification = "registered"
        reason = f"covered_by_manager_manifest:{registered_manifest.get('id', '')}:{registered_field}"
    elif is_one_off:
        classification = "one_off_exempt"
        reason = "one_off_scripts_are_not_daily_manager_contracts"
    elif is_legacy:
        classification = "legacy_exempt"
        reason = "legacy_scanner_folder_is_currently_exempt_from_manager_v1_1_registration"
    elif is_price_manager:
        classification = "needs_review"
        reason = "price_list_manager_script_not_registered_in_manager_manifest"
    else:
        classification = "unregistered"
        reason = "f_worker_like_script_not_registered_in_manager_manifest"

    exempt = classification in {"one_off_exempt", "legacy_exempt"}
    needs_review = classification in {"unregistered", "needs_review"}
    runbook_link = _runbook_link_for(root, script_path, classification)

    owner = _has_text(registered_manifest.get("display_name")) if is_registered else "0"
    purpose = _has_text(registered_manifest.get("purpose") or registered_manifest.get("display_name")) if is_registered else "0"
    entrypoint = "1" if is_registered else "0"
    health_source = _has_list(registered_manifest.get("health_sources")) if is_registered else "0"
    expected_outputs = _has_list(registered_manifest.get("outputs")) if is_registered else "0"
    safe_actions = _has_list(registered_manifest.get("safe_actions")) if is_registered else "0"
    forbidden_actions = _has_list(registered_manifest.get("forbidden_actions")) if is_registered else "0"
    runbook = "1" if runbook_link else "0"

    if exempt:
        owner = purpose = entrypoint = health_source = expected_outputs = safe_actions = forbidden_actions = "exempt"
        runbook = "exempt" if not runbook_link else "1"

    missing_fields: list[str] = []
    if not exempt:
        field_values = {
            "owner": owner,
            "purpose": purpose,
            "entrypoint": entrypoint,
            "health_source": health_source,
            "expected_outputs": expected_outputs,
            "runbook_notes_link": runbook,
            "safe_actions_declared": safe_actions,
            "forbidden_actions_declared": forbidden_actions,
        }
        missing_fields = [field for field, value in field_values.items() if value != "1"]

    return {
        "observed_utc": observed_utc,
        "script_path": script_path,
        "discovery_sources": script.get("discovery_sources", ""),
        "classification": classification,
        "classification_reason": reason,
        "is_exempt": "1" if exempt else "0",
        "needs_codex_review": "1" if needs_review else "0",
        "blocks_f_operation": "0",
        "owner": owner,
        "purpose": purpose,
        "entrypoint": entrypoint,
        "health_source": health_source,
        "expected_outputs": expected_outputs,
        "runbook_notes_link": runbook_link if runbook_link else runbook,
        "safe_actions_declared": safe_actions,
        "forbidden_actions_declared": forbidden_actions,
        "missing_fields": ";".join(missing_fields),
        "manager_module_id": str(registered_manifest.get("id", "")) if is_registered else "",
        "notes": "manager_v1_1_report_only_no_worker_changes",
    }


def build_f_script_registration_report(
    *,
    root: Path,
    manifest: dict[str, Any],
    observed_utc: str,
) -> dict[str, Any]:
    base = Path(root)
    discovered, inventory_exists = _discover_f_scripts(base)
    manager_manifests = _load_f_manager_manifests(base, manifest)
    registered = _registered_entries(manager_manifests)
    rows = [
        _classify_script(
            root=base,
            script=script,
            manifest=manifest,
            registered=registered,
            observed_utc=observed_utc,
        )
        for script in discovered.values()
    ]
    rows.sort(key=lambda row: (row["classification"], row["script_path"]))

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    needs_review_count = sum(1 for row in rows if row["needs_codex_review"] == "1")
    non_exempt_missing_count = sum(1 for row in rows if row["is_exempt"] != "1" and row["missing_fields"])
    summary = {
        "observed_utc": observed_utc,
        "flow": "F",
        "inventory_exists": bool(inventory_exists),
        "script_count": len(rows),
        "classification_counts": counts,
        "needs_codex_review_count": needs_review_count,
        "non_exempt_missing_contract_count": non_exempt_missing_count,
        "blocks_f_operation": False,
        "next_codex_task": (
            "Review unregistered and needs_review F scripts and decide which ones should become manager manifests."
            if needs_review_count
            else "No Codex self-organisation task from this snapshot."
        ),
    }
    priority_report = build_f_manifest_priority_report(
        root=base,
        manifest=manifest,
        manager_manifests=manager_manifests,
        registration_rows=rows,
        discovered=discovered,
        observed_utc=observed_utc,
    )
    return {"rows": rows, "summary": summary, "manifest_priority_report": priority_report}


def build_f_manifest_priority_report(
    *,
    root: Path,
    manifest: dict[str, Any],
    registration_rows: list[dict[str, str]],
    discovered: dict[str, dict[str, str]] | None = None,
    manager_manifests: list[dict[str, Any]] | None = None,
    observed_utc: str,
) -> dict[str, Any]:
    manifests = manager_manifests or _load_f_manager_manifests(Path(root), manifest)
    metadata = discovered or _discover_f_scripts(Path(root))[0]
    registered = _registered_entries(manifests)
    manifest_text = json.dumps(manifests, sort_keys=True).lower()
    context_text = "\n".join(_priority_context_text(Path(root), item) for item in manifests)
    observed_dt = _parse_utc(observed_utc)
    rows = [
        _priority_row(
            root=Path(root),
            manifest=manifest,
            registered=registered,
            registration_row=row,
            metadata=metadata.get(row["script_path"], {}),
            context_text=context_text,
            manifest_text=manifest_text,
            observed_utc=observed_utc,
            observed_dt=observed_dt,
        )
        for row in registration_rows
    ]

    candidates = [row for row in rows if row["recommended_action"] == "candidate_manifest"]
    candidates.sort(key=lambda row: (-int(row["priority_score"]), row["script_path"]))
    deferred = [row for row in rows if row["recommended_action"] != "candidate_manifest"]
    deferred.sort(key=lambda row: (row["recommended_action"], row["script_path"]))

    ranked_rows: list[dict[str, str]] = []
    for index, row in enumerate(candidates, start=1):
        row["rank"] = str(index)
        row["priority_band"] = _candidate_priority_band(index, int(row["priority_score"]))
        ranked_rows.append(row)
    for index, row in enumerate(deferred, start=len(ranked_rows) + 1):
        row["rank"] = str(index)
        row["priority_band"] = "deferred"
        ranked_rows.append(row)

    top_three = [row for row in ranked_rows if row["recommended_action"] == "candidate_manifest"][:3]
    summary = {
        "observed_utc": observed_utc,
        "flow": "F",
        "candidate_count": len(candidates),
        "deferred_count": len(deferred),
        "top_3_scripts": [row["script_path"] for row in top_three],
        "blocks_f_operation": False,
        "next_codex_task": (
            "Create manager manifests for the top 3 ranked F scripts in a separate batch, without editing worker logic."
            if top_three
            else "No F manifest priority task from this snapshot."
        ),
    }
    return {"rows": ranked_rows, "summary": summary}


def _priority_context_text(root: Path, manifest: dict[str, Any]) -> str:
    paths = list(PRIORITY_CONTEXT_PATHS)
    for group in ["health_sources", "status_sources", "outputs"]:
        for source in manifest.get(group, []):
            if isinstance(source, dict) and source.get("path"):
                paths.append(str(source["path"]))
    chunks: list[str] = []
    for rel_path in sorted(set(_normalize_path(path) for path in paths if path)):
        source_path = root / rel_path
        if not source_path.exists() or not source_path.is_file():
            continue
        chunks.append(_read_limited_text(source_path).lower())
    return "\n".join(chunks)


def _read_limited_text(path: Path, limit: int = 200_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _script_source_text(root: Path, script_path: str) -> str:
    path = root / script_path
    if path.suffix.lower() != ".py":
        return ""
    return _read_limited_text(path, limit=120_000).lower()


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _recently_modified(mtime_utc: str, observed_dt: datetime | None) -> bool:
    modified = _parse_utc(mtime_utc)
    if not modified or not observed_dt:
        return False
    return modified >= observed_dt - timedelta(days=RECENT_SCRIPT_DAYS)


def _priority_row(
    *,
    root: Path,
    manifest: dict[str, Any],
    registered: dict[str, RegistrationEntry],
    registration_row: dict[str, str],
    metadata: dict[str, str],
    context_text: str,
    manifest_text: str,
    observed_utc: str,
    observed_dt: datetime | None,
) -> dict[str, str]:
    script_path = registration_row["script_path"]
    script_name = _script_basename(script_path)
    script_lower = script_path.lower()
    name_lower = script_name.lower()
    source_text = _script_source_text(root, script_path)
    combined_text = "\n".join([script_lower, name_lower, source_text])
    classification = registration_row["classification"]
    mtime_utc = metadata.get("mtime_utc", "")
    in_price_manager_folder = "/price_list_manager/" in script_lower
    price_list_manager_scope = (
        in_price_manager_folder
        or "supplier_price_list" in combined_text
        or "price_list_manager" in combined_text
        or "f061_" in name_lower
    )
    test_or_fixture_support = _contains_any(name_lower, ["test_mode", "placeholder", "fixture"])

    referenced_by_manifest = script_path in registered or script_lower in manifest_text
    referenced_by_status_or_runtime = (
        price_list_manager_scope
        and (
            script_lower in context_text
            or name_lower in context_text
            or _contains_any(name_lower, ["fpm170_", "fpm130_", "f061_"])
        )
    )
    live_entrypoint = referenced_by_manifest or (
        price_list_manager_scope
        and _contains_any(
            name_lower,
            ["fpm130_run_live_cycle", "fpm170_supervise_live_cycle", "f061_run_legacy_first_checks_local"],
        )
    )
    writes_live_outputs = price_list_manager_scope and _contains_any(
        combined_text,
        [
            "out/systems/f/price_list_manager",
            "out/systems/f/inbox/supplier_price_list",
            "supplier_price_list_active_run",
            "supplier_price_list_run_state",
            "live_cycle_status",
            "live_cycle_health",
            "storage_drift_report",
            "price_list_manager/test_mode/status_dashboard",
            "write_f_contract_df",
        ],
    )
    queue_ownership = price_list_manager_scope and _contains_any(
        combined_text,
        [
            "price_list_queue",
            "next_action",
            "f061_handoff",
            "supplier_price_list_active_run",
            "supplier_price_list_run_state",
            "active_run",
            "run_state",
            "supervise",
            "live_cycle",
            "queue_control",
            "handoff",
        ],
    )
    storage_drift_or_preflight = price_list_manager_scope and _contains_any(
        "\n".join([script_lower, name_lower]),
        ["storage_drift", "drift", "preflight", "fpm129_"],
    )
    supplier_status_dashboard = price_list_manager_scope and _contains_any(
        combined_text,
        [
            "price_list_manager/test_mode/status_dashboard",
            "supplier_price_list_status",
            "supplier_status",
            "next_action_report",
            "acquisition_sources",
            "ready_sources",
            "fpm050_",
            "fpm060_",
        ],
    )
    recently_modified = _recently_modified(mtime_utc, observed_dt)
    is_exempt = classification in {"one_off_exempt", "legacy_exempt"}
    is_registered = classification == "registered"

    reason_codes: list[str] = []
    score = 0
    if live_entrypoint:
        score += 50
        reason_codes.append("live_entrypoint")
    if referenced_by_manifest:
        score += 40
        reason_codes.append("referenced_by_manifest")
    if referenced_by_status_or_runtime:
        score += 25
        reason_codes.append("referenced_by_status_or_runtime")
    if writes_live_outputs:
        score += 20
        reason_codes.append("writes_live_outputs")
    if queue_ownership:
        score += 18
        reason_codes.append("queue_ownership")
    if storage_drift_or_preflight:
        score += 35
        reason_codes.append("storage_drift_or_preflight")
    if supplier_status_dashboard:
        score += 24
        reason_codes.append("supplier_status_dashboard")
    if recently_modified:
        score += 8
        reason_codes.append("recently_modified")
    if in_price_manager_folder:
        score += 30
        reason_codes.append("price_list_manager_folder")
    elif price_list_manager_scope:
        score += 10
        reason_codes.append("price_list_related_scope")
    if not is_exempt:
        score += 5
        reason_codes.append("non_exempt_worker")
    if test_or_fixture_support and not is_registered:
        score -= 25
        reason_codes.append("test_or_fixture_deprioritised")

    recommended_action = "candidate_manifest"
    defer_reason = ""
    safe_to_manifest = "1"
    if is_registered:
        recommended_action = "defer_already_registered"
        defer_reason = "already covered by the current F manager manifest"
        safe_to_manifest = "not_needed"
    elif classification == "one_off_exempt":
        recommended_action = "defer_one_off_exempt"
        defer_reason = "one-off scripts are not daily manager contracts in V1.2"
        safe_to_manifest = "not_needed"
        score = 0
    elif classification == "legacy_exempt":
        recommended_action = "defer_legacy_exempt"
        defer_reason = "legacy scanner folder is deliberately exempt in V1.2"
        safe_to_manifest = "not_needed"
        score = 0

    score = max(score, 0)

    return {
        "observed_utc": observed_utc,
        "rank": "",
        "script_path": script_path,
        "classification": classification,
        "priority_score": str(score),
        "priority_band": "",
        "recommended_action": recommended_action,
        "safe_to_manifest_without_worker_changes": safe_to_manifest,
        "reason_codes": ";".join(reason_codes) if reason_codes else "deferred",
        "reason_summary": _priority_reason_summary(reason_codes, recommended_action),
        "referenced_by_manifest": "1" if referenced_by_manifest else "0",
        "referenced_by_status_or_runtime": "1" if referenced_by_status_or_runtime else "0",
        "live_entrypoint": "1" if live_entrypoint else "0",
        "writes_live_outputs": "1" if writes_live_outputs else "0",
        "queue_ownership": "1" if queue_ownership else "0",
        "storage_drift_or_preflight": "1" if storage_drift_or_preflight else "0",
        "supplier_status_dashboard": "1" if supplier_status_dashboard else "0",
        "recently_modified": "1" if recently_modified else "0",
        "mtime_utc": mtime_utc,
        "defer_reason": defer_reason,
    }


def _candidate_priority_band(rank: int, score: int) -> str:
    if rank <= 3:
        return "top_3"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _priority_reason_summary(reason_codes: list[str], recommended_action: str) -> str:
    if recommended_action == "defer_already_registered":
        return "Already registered in the current F manager manifest."
    if recommended_action == "defer_one_off_exempt":
        return "Deferred because one-off scripts are not daily manager contracts."
    if recommended_action == "defer_legacy_exempt":
        return "Deferred because the legacy scanner folder is exempt in this F-only pass."
    readable = {
        "live_entrypoint": "it controls or supervises the live F path",
        "referenced_by_manifest": "it is already named by the F manager manifest",
        "referenced_by_status_or_runtime": "it appears in current F status or runtime evidence",
        "writes_live_outputs": "it writes live F evidence or output files",
        "queue_ownership": "it is involved in queue ownership or handoff",
        "storage_drift_or_preflight": "it protects the storage drift or preflight gate",
        "supplier_status_dashboard": "it builds supplier status or dashboard evidence",
        "recently_modified": "it changed recently",
        "price_list_manager_folder": "it is inside the current price-list manager folder",
        "price_list_related_scope": "it is related to the current price-list manager scope",
        "non_exempt_worker": "it is a non-exempt F worker-like script",
        "test_or_fixture_deprioritised": "it is test or fixture support, so it is ranked lower",
    }
    parts = [readable[code] for code in reason_codes if code in readable]
    return "; ".join(parts) if parts else "Low evidence priority in this snapshot."


def build_f_self_organisation_markdown(report: dict[str, Any]) -> str:
    rows: list[dict[str, str]] = report["rows"]
    summary: dict[str, Any] = report["summary"]
    registered = [row for row in rows if row["classification"] == "registered"]
    unregistered = [row for row in rows if row["classification"] == "unregistered"]
    needs_review = [row for row in rows if row["classification"] == "needs_review"]
    exempt = [row for row in rows if row["is_exempt"] == "1"]

    lines = [
        "# F Self-Organisation Report",
        "",
        f"Observed UTC: {summary.get('observed_utc', '')}",
        "",
        "## Answer",
        _summary_sentence(summary),
        "",
        "## Properly Registered",
        *_script_lines(registered, "No F scripts are fully registered in the manager manifest yet."),
        "",
        "## Unregistered",
        *_script_lines(unregistered, "No unregistered non-exempt F scripts found."),
        "",
        "## Exempt",
        *_script_lines(exempt, "No exempt F scripts found."),
        "",
        "## Needs Codex Review",
        *_script_lines(needs_review, "No F scripts need Codex review from this snapshot."),
        "",
        "## Does This Block F Operation",
        "- No. This is a manager-owned organisation report only. It does not block the live F scanner.",
        "",
        "## Next Codex Task",
        f"- {summary.get('next_codex_task', '')}",
        "",
        "## Safety",
        "- This report did not edit worker scripts, run worker cycles, write Google Sheets, add dispatching, or move the manager repo.",
        "",
    ]
    return "\n".join(lines)


def _summary_sentence(summary: dict[str, Any]) -> str:
    counts = summary.get("classification_counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return (
        f"The manager found {summary.get('script_count', 0)} F worker-like scripts: "
        f"{counts.get('registered', 0)} registered, "
        f"{counts.get('unregistered', 0)} unregistered, "
        f"{counts.get('needs_review', 0)} needing review, and "
        f"{counts.get('one_off_exempt', 0) + counts.get('legacy_exempt', 0)} exempt."
    )


def _script_lines(rows: list[dict[str, str]], empty_text: str) -> list[str]:
    if not rows:
        return [f"- {empty_text}"]
    return [
        f"- `{row['script_path']}` - {row['classification_reason']}"
        for row in rows[:50]
    ] + ([f"- Additional rows omitted from markdown: {len(rows) - 50}"] if len(rows) > 50 else [])


def build_f_manifest_priority_markdown(priority_report: dict[str, Any]) -> str:
    rows: list[dict[str, str]] = priority_report["rows"]
    summary: dict[str, Any] = priority_report["summary"]
    top_three = [row for row in rows if row["priority_band"] == "top_3"]
    deferred = [row for row in rows if row["recommended_action"].startswith("defer_")]
    candidates_after_top = [
        row
        for row in rows
        if row["recommended_action"] == "candidate_manifest" and row["priority_band"] != "top_3"
    ]

    lines = [
        "# F Manifest Priority Ranking",
        "",
        f"Observed UTC: {summary.get('observed_utc', '')}",
        "",
        "## Answer",
        _priority_answer(summary),
        "",
        "## Top 3 Scripts To Register Next",
        *_priority_lines(top_three, "No top F manifest candidates found."),
        "",
        "## Safe To Manifest Without Worker Changes",
        *_safe_manifest_lines(top_three),
        "",
        "## Deliberately Deferred",
        *_deferred_priority_lines(deferred, candidates_after_top),
        "",
        "## Does This Block F Operation",
        "- No. This ranking only sorts manager registration work. It does not block the live F scanner.",
        "",
        "## Recommended Next Codex Batch",
        f"- {summary.get('next_codex_task', '')}",
        "",
        "## Safety",
        "- This report did not create manifests, edit worker scripts, run worker cycles, write Google Sheets, add dispatching, or expand beyond F.",
        "",
    ]
    return "\n".join(lines)


def _priority_answer(summary: dict[str, Any]) -> str:
    top = summary.get("top_3_scripts", [])
    if not isinstance(top, list) or not top:
        return "The manager did not find a non-exempt F script that needs priority manifest registration."
    return (
        "The manager ranked the F review backlog and picked the next three manifest candidates: "
        + ", ".join(f"`{script}`" for script in top[:3])
        + ". Luke does not need to choose from the full list."
    )


def _priority_lines(rows: list[dict[str, str]], empty_text: str) -> list[str]:
    if not rows:
        return [f"- {empty_text}"]
    return [
        (
            f"- {row['rank']}. `{row['script_path']}` - score {row['priority_score']}; "
            f"{row['reason_summary']}"
        )
        for row in rows
    ]


def _safe_manifest_lines(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- No candidate safety checks to report."]
    lines: list[str] = []
    for row in rows:
        if row["safe_to_manifest_without_worker_changes"] == "1":
            lines.append(f"- `{row['script_path']}` - yes, registration can be planned without changing worker logic.")
        else:
            lines.append(f"- `{row['script_path']}` - {row['safe_to_manifest_without_worker_changes']}.")
    return lines


def _deferred_priority_lines(deferred: list[dict[str, str]], lower_candidates: list[dict[str, str]]) -> list[str]:
    lines: list[str] = []
    already_registered = [row for row in deferred if row["recommended_action"] == "defer_already_registered"]
    one_off_count = sum(1 for row in deferred if row["recommended_action"] == "defer_one_off_exempt")
    legacy_count = sum(1 for row in deferred if row["recommended_action"] == "defer_legacy_exempt")
    if already_registered:
        lines.extend(f"- Already registered: `{row['script_path']}`" for row in already_registered[:10])
    if one_off_count:
        lines.append(f"- One-off exempt scripts deferred: {one_off_count}")
    if legacy_count:
        lines.append(f"- Legacy exempt scripts deferred: {legacy_count}")
    if lower_candidates:
        lines.append(f"- Lower-ranked non-exempt scripts deferred until after the top 3: {len(lower_candidates)}")
    return lines or ["- No deliberately deferred F scripts found."]


def write_f_self_organisation_outputs(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    target_dir = output_dir / SELF_ORG_OUTPUT_DIRNAME
    paths = {
        "f_script_registration_csv": target_dir / "latest_f_script_registration_report.csv",
        "f_script_registration_json": target_dir / "latest_f_script_registration_report.json",
        "f_self_organisation_report": target_dir / "latest_f_self_organisation_report.md",
        "f_manifest_priority_csv": target_dir / "latest_f_manifest_priority_ranking.csv",
        "f_manifest_priority_json": target_dir / "latest_f_manifest_priority_ranking.json",
        "f_manifest_priority_report": target_dir / "latest_f_manifest_priority_report.md",
    }
    _write_csv(paths["f_script_registration_csv"], F_SCRIPT_REGISTRATION_COLUMNS, report["rows"])
    paths["f_script_registration_json"].parent.mkdir(parents=True, exist_ok=True)
    paths["f_script_registration_json"].write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["f_self_organisation_report"].write_text(build_f_self_organisation_markdown(report), encoding="utf-8")
    priority_report = report.get("manifest_priority_report", {"rows": [], "summary": {}})
    _write_csv(paths["f_manifest_priority_csv"], F_MANIFEST_PRIORITY_COLUMNS, priority_report.get("rows", []))
    paths["f_manifest_priority_json"].write_text(
        json.dumps(priority_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["f_manifest_priority_report"].write_text(
        build_f_manifest_priority_markdown(priority_report),
        encoding="utf-8",
    )
    return paths
