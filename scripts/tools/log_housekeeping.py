from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "project_control" / "log_housekeeping_registry.json"


@dataclass
class Rule:
    id: str
    class_id: str
    owner: str
    reason: str
    mandatory: bool
    path_globs: list[str]
    ttl_days: float | None
    max_file_count: int | None
    max_total_size_mb: float | None
    action_on_expiry: str
    protected: bool
    live_cleanup_allowed: bool
    safety_blockers: list[str]
    target_type: str = "file"
    flow: str = ""
    storage_class: str = ""
    cleanup_eligible: bool = False
    health_fail_over_cap: bool = False
    source_hash_required: bool = False


@dataclass
class Item:
    path: Path
    rel_path: str
    item_type: str
    size_bytes: int
    mtime_utc: datetime
    age_days: float


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_ts(now: datetime | None = None) -> str:
    ts = now or _utc_now()
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id(now: datetime | None = None) -> str:
    ts = now or _utc_now()
    return ts.strftime("%Y%m%dT%H%M%SZ")


def _load_registry(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(raw, dict):
        raise ValueError("registry_root_not_object")
    return raw


def _build_rules(registry: dict[str, Any]) -> list[Rule]:
    out: list[Rule] = []
    for raw in registry.get("rules", []):
        retention = raw.get("retention", {}) or {}
        health = raw.get("health", {}) or {}
        target_type = str(raw.get("target_type", "file")).strip().lower() or "file"
        if target_type not in {"file", "directory", "any"}:
            raise ValueError(f"invalid_target_type:{raw.get('id', '')}:{target_type}")
        out.append(
            Rule(
                id=str(raw.get("id", "")).strip(),
                class_id=str(raw.get("class", "")).strip(),
                owner=str(raw.get("owner", "")).strip(),
                reason=str(raw.get("reason", "")).strip(),
                mandatory=bool(raw.get("mandatory", False)),
                path_globs=[str(x) for x in (raw.get("path_globs", []) or [])],
                ttl_days=float(retention.get("ttl_days")) if retention.get("ttl_days") is not None else None,
                max_file_count=int(retention.get("max_file_count")) if retention.get("max_file_count") is not None else None,
                max_total_size_mb=float(retention.get("max_total_size_mb")) if retention.get("max_total_size_mb") is not None else None,
                action_on_expiry=str(raw.get("action_on_expiry", "keep")).strip().lower(),
                protected=bool(raw.get("protected", False)),
                live_cleanup_allowed=bool(raw.get("live_cleanup_allowed", False)),
                safety_blockers=[str(x) for x in (raw.get("safety_blockers", []) or [])],
                target_type=target_type,
                flow=str(raw.get("flow", "")).strip(),
                storage_class=str(raw.get("storage_class", "")).strip(),
                cleanup_eligible=bool(raw.get("cleanup_eligible", False)),
                health_fail_over_cap=bool(health.get("fail_over_cap", False)),
                source_hash_required=bool(raw.get("source_hash_required", False)),
            )
        )
    return out


def _directory_size_bytes(path: Path) -> int:
    total = 0
    try:
        iterator = path.rglob("*")
        for child in iterator:
            try:
                if child.is_file() and not child.is_symlink():
                    total += int(child.stat().st_size)
            except Exception:
                continue
    except Exception:
        return 0
    return total


def _safe_stat(path: Path) -> tuple[int, datetime] | None:
    try:
        st = path.stat()
    except Exception:
        return None
    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    if path.is_dir():
        return _directory_size_bytes(path), mtime
    return int(st.st_size), mtime


def _item_type(path: Path) -> str:
    if path.is_dir():
        return "directory"
    return "file"


def _iter_scan_root_paths(path: Path, recursive: bool, include_directories: bool) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    paths: list[Path] = []
    if recursive:
        iterator = path.rglob("*")
    else:
        iterator = path.glob("*")
    for p in iterator:
        try:
            if p.is_file() or (include_directories and p.is_dir()):
                paths.append(p)
        except Exception:
            continue
    return paths


def _rule_accepts_path(rule: Rule, path: Path) -> bool:
    if rule.target_type == "any":
        return path.is_file() or path.is_dir()
    if rule.target_type == "directory":
        return path.is_dir()
    return path.is_file()


def _collect_paths(
    registry: dict[str, Any],
    rules: list[Rule],
    flow_filter: str = "",
) -> tuple[set[Path], dict[str, list[Path]]]:
    files: set[Path] = set()
    by_root: dict[str, list[Path]] = {}
    flow_norm = flow_filter.strip().lower()

    for raw_root in registry.get("scan_roots", []) or []:
        root_flow = str(raw_root.get("flow", "")).strip().lower()
        if flow_norm and root_flow and root_flow not in {flow_norm, "shared"}:
            continue
        if flow_norm and not root_flow:
            continue
        root_path = ROOT / str(raw_root.get("path", "")).strip()
        recursive = bool(raw_root.get("recursive", True))
        include_directories = bool(raw_root.get("include_directories", False))
        root_files = _iter_scan_root_paths(root_path, recursive=recursive, include_directories=include_directories)
        by_root[str(root_path)] = root_files
        files.update(root_files)

    for rule in rules:
        for pattern in rule.path_globs:
            for p in ROOT.glob(pattern):
                if _rule_accepts_path(rule, p):
                    files.add(p)
    return files, by_root


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _match_rule(rel_path: str, rules: list[Rule]) -> Rule | None:
    for rule in rules:
        for pattern in rule.path_globs:
            if fnmatch(rel_path, pattern.replace("\\", "/")):
                return rule
    return None


def _infer_rule_flow(rule: Rule) -> str:
    if rule.flow:
        return rule.flow.strip().lower()
    patterns = [p.replace("\\", "/").lower() for p in rule.path_globs]
    if any(p.startswith("out/systems/f/") or p.startswith("out/backups/f_") for p in patterns):
        return "f"
    if any(p.startswith("out/systems/h/") or "checklist_h" in p or "health_status_h" in p for p in patterns):
        return "h"
    if any(p.startswith("out/sql/") or p.startswith("out/cycle_alerts/") or p.startswith("out/system_") for p in patterns):
        return "shared"
    if any(p.startswith("out/tmp_") or p.startswith("project_control/") or p == "work_log.md" for p in patterns):
        return "shared"
    return ""


def _rule_matches_flow(rule: Rule, flow_filter: str) -> bool:
    flow_norm = flow_filter.strip().lower()
    if not flow_norm:
        return True
    rule_flow = _infer_rule_flow(rule)
    return rule_flow in {flow_norm, "shared"}


def _load_context() -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "h_run_unfinalized": None,
        "h_run_unfinalized_reason": "unknown",
        "h_lock_active": None,
        "h_lock_active_reason": "unknown",
    }
    run_in_progress = ROOT / "out" / "systems" / "H" / "live" / "H_run_in_progress.txt"
    last_finalized = ROOT / "out" / "systems" / "H" / "live" / "H_last_finalized_run_id.txt"
    h_lock = ROOT / "out" / "systems" / "H" / "live" / "H_pricing_cycle.lock"

    try:
        in_prog = run_in_progress.read_text(encoding="utf-8", errors="replace").strip() if run_in_progress.exists() else ""
        finalized = last_finalized.read_text(encoding="utf-8", errors="replace").strip() if last_finalized.exists() else ""
        if not in_prog:
            ctx["h_run_unfinalized"] = False
            ctx["h_run_unfinalized_reason"] = "no_in_progress_marker"
        elif in_prog == finalized and finalized:
            ctx["h_run_unfinalized"] = False
            ctx["h_run_unfinalized_reason"] = "in_progress_equals_finalized"
        else:
            ctx["h_run_unfinalized"] = True
            ctx["h_run_unfinalized_reason"] = f"in_progress={in_prog} finalized={finalized or 'missing'}"
    except Exception as exc:
        ctx["h_run_unfinalized"] = None
        ctx["h_run_unfinalized_reason"] = f"state_read_error:{type(exc).__name__}"
    try:
        if not h_lock.exists():
            ctx["h_lock_active"] = False
            ctx["h_lock_active_reason"] = "missing_lock"
        else:
            line = h_lock.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
            ctx["h_lock_active"] = True
            ctx["h_lock_active_reason"] = line or "lock_exists"
    except Exception as exc:
        ctx["h_lock_active"] = None
        ctx["h_lock_active_reason"] = f"lock_read_error:{type(exc).__name__}"
    return ctx


def _blocker_hit(rule: Rule, rel_path: str, ctx: dict[str, Any]) -> tuple[bool, str]:
    blockers = set(rule.safety_blockers)
    if "always_protected" in blockers:
        return True, "always_protected"
    if "current_cycle_health_evidence" in blockers:
        if rel_path == "out/system_health_checklist.csv" or rel_path.startswith("out/cycle_alerts/"):
            return True, "current_cycle_health_evidence"
    if "h_run_unfinalized" in blockers:
        v = ctx.get("h_run_unfinalized")
        if v is None:
            return True, "h_run_unfinalized_state_unknown"
        if v is True:
            return True, "h_run_unfinalized"
    if "h_lock_active" in blockers:
        v = ctx.get("h_lock_active")
        if v is None:
            return True, "h_lock_state_unknown"
        if v is True:
            return True, "h_lock_active"
    if "block_if_state_unknown" in blockers:
        if ctx.get("h_run_unfinalized") is None or ctx.get("h_lock_active") is None:
            return True, "block_if_state_unknown"
    return False, ""


def _tag_expiry_by_count(items: list[Item], max_count: int | None) -> set[str]:
    if max_count is None or max_count < 0:
        return set()
    if len(items) <= max_count:
        return set()
    ordered = sorted(items, key=lambda x: x.mtime_utc, reverse=True)
    overflow = ordered[max_count:]
    return {it.rel_path for it in overflow}


def _tag_expiry_by_size(items: list[Item], max_size_mb: float | None) -> set[str]:
    if max_size_mb is None or max_size_mb <= 0:
        return set()
    max_bytes = int(max_size_mb * 1024 * 1024)
    total = sum(it.size_bytes for it in items)
    if total <= max_bytes:
        return set()
    ordered = sorted(items, key=lambda x: x.mtime_utc, reverse=True)
    keep: list[Item] = []
    running = 0
    for it in ordered:
        if running + it.size_bytes <= max_bytes:
            keep.append(it)
            running += it.size_bytes
    keep_set = {it.rel_path for it in keep}
    return {it.rel_path for it in items if it.rel_path not in keep_set}


def _action_for_expiry(rule: Rule) -> str:
    if rule.action_on_expiry == "archive":
        return "would_archive"
    if rule.action_on_expiry == "delete":
        return "would_delete"
    return "keep"


def _build_rows(
    all_files: set[Path],
    rules: list[Rule],
    classes: dict[str, str],
    ctx: dict[str, Any],
) -> list[dict[str, str]]:
    now = _utc_now()
    items_by_rule: dict[str, list[Item]] = defaultdict(list)
    base_rows: list[dict[str, str]] = []

    for path in sorted(all_files):
        rel = _relative(path)
        st = _safe_stat(path)
        if st is None:
            continue
        size, mtime = st
        age_days = max((now - mtime).total_seconds() / 86400.0, 0.0)
        rule = _match_rule(rel, rules)
        if rule is None:
            base_rows.append(
                {
                    "path": rel,
                    "item_type": _item_type(path),
                    "class": "",
                    "class_name": "",
                    "rule_id": "",
                    "flow": "",
                    "owner": "",
                    "protected": "0",
                    "mandatory": "0",
                    "decision": "unknown_unclassified",
                    "reason": "unclassified_scan_root",
                    "size_bytes": str(size),
                    "mtime_utc": _utc_ts(mtime),
                    "age_days": f"{age_days:.2f}",
                    "safety_blocker": "",
                    "live_cleanup_allowed": "0",
                    "action_taken": "none",
                    "action_error": "",
                }
            )
            continue

        item = Item(path=path, rel_path=rel, item_type=_item_type(path), size_bytes=size, mtime_utc=mtime, age_days=age_days)
        items_by_rule[rule.id].append(item)
        base_rows.append(
            {
                "path": rel,
                "item_type": item.item_type,
                "class": rule.class_id,
                "class_name": classes.get(rule.class_id, ""),
                "rule_id": rule.id,
                "flow": rule.flow,
                "owner": rule.owner,
                "protected": "1" if rule.protected else "0",
                "mandatory": "1" if rule.mandatory else "0",
                "decision": "",
                "reason": "",
                "size_bytes": str(size),
                "mtime_utc": _utc_ts(mtime),
                "age_days": f"{age_days:.2f}",
                "safety_blocker": "",
                "live_cleanup_allowed": "1" if rule.live_cleanup_allowed else "0",
                "action_taken": "none",
                "action_error": "",
            }
        )

    expiry_count: dict[str, set[str]] = {}
    expiry_size: dict[str, set[str]] = {}
    for rule in rules:
        scoped = items_by_rule.get(rule.id, [])
        expiry_count[rule.id] = _tag_expiry_by_count(scoped, rule.max_file_count)
        expiry_size[rule.id] = _tag_expiry_by_size(scoped, rule.max_total_size_mb)

    by_id = {rule.id: rule for rule in rules}

    for row in base_rows:
        rule_id = row["rule_id"]
        if not rule_id:
            continue
        rule = by_id[rule_id]
        rel = row["path"]

        blocked, blocker_reason = _blocker_hit(rule, rel, ctx)

        if rule.protected:
            row["decision"] = "keep"
            row["reason"] = "protected_policy"
            row["safety_blocker"] = blocker_reason
            continue

        if blocked:
            row["decision"] = "blocked_by_safety"
            row["reason"] = "safety_blocker"
            row["safety_blocker"] = blocker_reason
            continue

        if rule.class_id in {"L1", "L2", "L3", "L5"}:
            row["decision"] = "keep"
            row["reason"] = "non_cleanup_class"
            continue

        age_days = float(row["age_days"])
        expired_by_ttl = rule.ttl_days is not None and age_days > rule.ttl_days
        expired_by_count = rel in expiry_count.get(rule.id, set())
        expired_by_size = rel in expiry_size.get(rule.id, set())

        if expired_by_ttl or expired_by_count or expired_by_size:
            row["decision"] = _action_for_expiry(rule)
            reasons: list[str] = []
            if expired_by_ttl:
                reasons.append("ttl_expired")
            if expired_by_count:
                reasons.append("count_cap_exceeded")
            if expired_by_size:
                reasons.append("size_cap_exceeded")
            row["reason"] = "+".join(reasons)
        else:
            row["decision"] = "keep"
            row["reason"] = "within_retention"

    return base_rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "path",
        "item_type",
        "class",
        "class_name",
        "rule_id",
        "flow",
        "owner",
        "protected",
        "mandatory",
        "decision",
        "reason",
        "size_bytes",
        "mtime_utc",
        "age_days",
        "safety_blocker",
        "live_cleanup_allowed",
        "action_taken",
        "action_error",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in cols})


def _status(severity: str, message: str) -> tuple[str, str]:
    return severity, message


def _build_storage_health_rows(
    rows: list[dict[str, str]],
    rules: list[Rule],
    registry: dict[str, Any],
) -> list[dict[str, str]]:
    cfg = registry.get("storage_health", {}) or {}
    warn_gb = float(cfg.get("free_space_warn_gb", 100))
    fail_gb = float(cfg.get("free_space_fail_gb", 50))
    generated = _utc_ts()
    health_rows: list[dict[str, str]] = []

    try:
        free_bytes = int(shutil.disk_usage(ROOT).free)
        free_gb = free_bytes / (1024**3)
        if free_gb < fail_gb:
            severity, message = _status("FAIL", "free space below fail reserve")
        elif free_gb < warn_gb:
            severity, message = _status("WARN", "free space below warn reserve")
        else:
            severity, message = _status("PASS", "free space reserve is healthy")
        health_rows.append(
            {
                "generated_utc": generated,
                "check_id": "free_space_reserve",
                "status": severity,
                "owner": "storage_housekeeping",
                "rule_id": "",
                "value": f"{free_gb:.2f}GB",
                "threshold": f"warn<{warn_gb:.2f}GB fail<{fail_gb:.2f}GB",
                "message": message,
            }
        )
    except Exception as exc:
        health_rows.append(
            {
                "generated_utc": generated,
                "check_id": "free_space_reserve",
                "status": "WARN",
                "owner": "storage_housekeeping",
                "rule_id": "",
                "value": "",
                "threshold": f"warn<{warn_gb:.2f}GB fail<{fail_gb:.2f}GB",
                "message": f"free space check failed:{type(exc).__name__}",
            }
        )

    unclassified = [row for row in rows if row.get("decision") == "unknown_unclassified"]
    unclassified_fail_age_days = float(cfg.get("unclassified_fail_age_days", 7))
    new_unclassified = [
        row
        for row in unclassified
        if float(row.get("age_days", "0") or 0) <= unclassified_fail_age_days
    ]
    if new_unclassified:
        unclassified_status = "FAIL"
        unclassified_message = "new undeclared output families found in scan roots"
    elif unclassified:
        unclassified_status = "WARN"
        unclassified_message = "legacy undeclared output families still need registry classification"
    else:
        unclassified_status = "PASS"
        unclassified_message = "all scanned items matched a registry rule"
    health_rows.append(
        {
            "generated_utc": generated,
            "check_id": "unclassified_scan_items",
            "status": unclassified_status,
            "owner": "storage_housekeeping",
            "rule_id": "",
            "value": str(len(unclassified)),
            "threshold": f"newer_than_or_equal_{unclassified_fail_age_days:.1f}_days=0",
            "message": unclassified_message,
        }
    )

    rows_by_rule: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rule_id = row.get("rule_id", "")
        if rule_id:
            rows_by_rule[rule_id].append(row)

    for rule in rules:
        scoped = rows_by_rule.get(rule.id, [])
        if rule.max_total_size_mb is not None and rule.health_fail_over_cap:
            total_bytes = sum(int(row.get("size_bytes", "0") or 0) for row in scoped)
            cap_bytes = int(rule.max_total_size_mb * 1024 * 1024)
            over_cap = total_bytes > cap_bytes
            health_rows.append(
                {
                    "generated_utc": generated,
                    "check_id": f"rule_size_cap:{rule.id}",
                    "status": "FAIL" if over_cap else "PASS",
                    "owner": rule.owner,
                    "rule_id": rule.id,
                    "value": str(total_bytes),
                    "threshold": str(cap_bytes),
                    "message": "registered family exceeds hard storage cap" if over_cap else "registered family is within hard storage cap",
                }
            )
        if rule.source_hash_required and scoped:
            missing = 0
            for row in scoped:
                target = ROOT / row.get("path", "")
                if not _source_hash_evidence_exists(target):
                    missing += 1
            health_rows.append(
                {
                    "generated_utc": generated,
                    "check_id": f"source_hash_dedupe:{rule.id}",
                    "status": "WARN" if missing else "PASS",
                    "owner": rule.owner,
                    "rule_id": rule.id,
                    "value": str(missing),
                    "threshold": "0",
                    "message": "raw source items are missing source-hash sidecar evidence" if missing else "raw source items have source-hash sidecar evidence",
                }
            )

    return health_rows


def _source_hash_evidence_exists(target: Path) -> bool:
    candidates = [
        target.with_suffix(target.suffix + ".sha256") if target.suffix else target.with_name(target.name + ".sha256"),
        target.with_suffix(target.suffix + ".manifest.json") if target.suffix else target / "manifest.json",
        target / "manifest.json" if target.is_dir() else target.with_name(target.name + ".manifest.json"),
    ]
    if any(p.exists() for p in candidates):
        return True
    run_state = target / "run_state.csv" if target.is_dir() else None
    if run_state is None or not run_state.exists():
        return False
    try:
        with run_state.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except Exception:
        return False
    if not rows:
        return False
    for row in rows:
        explicit = str(row.get("source_hash", "") or row.get("source_sha256", "") or "").strip()
        if explicit:
            return True
        source_path = str(row.get("source_file_path", "") or "").strip()
        if re.search(r"(?i)(?:^|[_\\.-])[a-f0-9]{8,64}(?:[_\\.-]|$)", source_path):
            return True
    return False


def _write_storage_health(out_dir: Path, run_token: str, rows: list[dict[str, str]]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_path = out_dir / f"storage_health.{run_token}.csv"
    latest_path = out_dir / "storage_health.latest.csv"
    cols = ["generated_utc", "check_id", "status", "owner", "rule_id", "value", "threshold", "message"]
    for p in (run_path, latest_path):
        with p.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in cols})
    return run_path, latest_path


def _safe_action_target(rel_path: str, out_dir: Path) -> bool:
    p = ROOT / rel_path
    try:
        resolved = p.resolve()
        root_resolved = ROOT.resolve()
        resolved.relative_to(root_resolved)
    except Exception:
        return False
    if resolved == root_resolved:
        return False
    if str(resolved).startswith(str(out_dir.resolve())):
        return False
    return True


def _cleanup_allowed_for_rule(rule: Rule) -> bool:
    return bool(rule.live_cleanup_allowed and (rule.class_id in {"L4", "L6"} or rule.cleanup_eligible))


def _apply_guard(ctx: dict[str, Any]) -> tuple[bool, str]:
    # Phase-1 safety contract: no live apply when H run ownership is active or unknown.
    h_lock_active = ctx.get("h_lock_active")
    if h_lock_active is None:
        return False, "h_lock_state_unknown"
    if bool(h_lock_active):
        return False, "h_lock_active"
    h_unfinalized = ctx.get("h_run_unfinalized")
    if h_unfinalized is None:
        return False, "h_state_unknown"
    if bool(h_unfinalized):
        return False, "h_run_unfinalized"
    return True, ""


def _apply_actions(
    rows: list[dict[str, str]],
    rules: list[Rule],
    out_dir: Path,
    ctx: dict[str, Any],
) -> list[dict[str, str]]:
    by_id = {rule.id: rule for rule in rules}
    archive_root = out_dir / "archive" / _run_id()
    allowed, blocked_reason = _apply_guard(ctx)
    ledger_rows: list[dict[str, str]] = []

    for row in rows:
        decision = row.get("decision", "")
        if decision not in {"would_delete", "would_archive"}:
            continue
        if not allowed:
            row["action_taken"] = "skipped"
            row["action_error"] = f"apply_blocked:{blocked_reason}"
            ledger_rows.append(
                {
                    "timestamp_utc": _utc_ts(),
                    "path": row.get("path", ""),
                    "rule_id": row.get("rule_id", ""),
                    "decision": decision,
                    "action_taken": row["action_taken"],
                    "action_error": row["action_error"],
                }
            )
            continue
        rule = by_id.get(row.get("rule_id", ""))
        if rule is None:
            row["action_taken"] = "skipped"
            row["action_error"] = "missing_rule"
            ledger_rows.append(
                {
                    "timestamp_utc": _utc_ts(),
                    "path": row.get("path", ""),
                    "rule_id": row.get("rule_id", ""),
                    "decision": decision,
                    "action_taken": row["action_taken"],
                    "action_error": row["action_error"],
                }
            )
            continue
        if not _cleanup_allowed_for_rule(rule):
            row["action_taken"] = "skipped"
            row["action_error"] = "live_cleanup_not_allowed"
            ledger_rows.append(
                {
                    "timestamp_utc": _utc_ts(),
                    "path": row.get("path", ""),
                    "rule_id": row.get("rule_id", ""),
                    "decision": decision,
                    "action_taken": row["action_taken"],
                    "action_error": row["action_error"],
                }
            )
            continue

        rel = row.get("path", "")
        if not _safe_action_target(rel, out_dir):
            row["action_taken"] = "skipped"
            row["action_error"] = "unsafe_target"
            ledger_rows.append(
                {
                    "timestamp_utc": _utc_ts(),
                    "path": row.get("path", ""),
                    "rule_id": row.get("rule_id", ""),
                    "decision": decision,
                    "action_taken": row["action_taken"],
                    "action_error": row["action_error"],
                }
            )
            continue

        target = ROOT / rel
        if not target.exists():
            row["action_taken"] = "skipped"
            row["action_error"] = "missing_target"
            ledger_rows.append(
                {
                    "timestamp_utc": _utc_ts(),
                    "path": row.get("path", ""),
                    "rule_id": row.get("rule_id", ""),
                    "decision": decision,
                    "action_taken": row["action_taken"],
                    "action_error": row["action_error"],
                }
            )
            continue

        try:
            if decision == "would_delete":
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.is_file():
                    target.unlink()
                else:
                    raise RuntimeError("unsupported_target_type")
                row["action_taken"] = "deleted"
            else:
                dest = archive_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(dest))
                row["action_taken"] = "archived"
        except Exception as exc:
            row["action_taken"] = "error"
            row["action_error"] = f"{type(exc).__name__}:{exc}"
        ledger_rows.append(
            {
                "timestamp_utc": _utc_ts(),
                "path": row.get("path", ""),
                "rule_id": row.get("rule_id", ""),
                "decision": decision,
                "action_taken": row.get("action_taken", ""),
                "action_error": row.get("action_error", ""),
            }
        )
    return ledger_rows


def _write_action_ledger(out_dir: Path, run_token: str, rows: list[dict[str, str]]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_path = out_dir / f"housekeeping_actions.{run_token}.csv"
    latest_path = out_dir / "housekeeping_actions.latest.csv"
    storage_run_path = out_dir / f"storage_housekeeping_actions.{run_token}.csv"
    storage_latest_path = out_dir / "storage_housekeeping_actions.latest.csv"
    cols = ["timestamp_utc", "path", "rule_id", "decision", "action_taken", "action_error"]
    for p in (run_path, latest_path, storage_run_path, storage_latest_path):
        with p.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in cols})
    return run_path, latest_path


def _summary(
    rows: list[dict[str, str]],
    registry_path: Path,
    apply_mode: bool,
    ctx: dict[str, Any],
    apply_allowed: bool,
    apply_block_reason: str,
    action_ledger_path: Path | None,
    flow_filter: str = "",
) -> dict[str, Any]:
    by_decision = Counter(row.get("decision", "") for row in rows)
    by_class = Counter((row.get("class", "") or "UNCLASSIFIED") for row in rows)
    actions = Counter(row.get("action_taken", "none") for row in rows)
    candidate_delete_recovery_bytes = sum(
        int(row.get("size_bytes", "0") or 0)
        for row in rows
        if row.get("decision") == "would_delete"
    )
    return {
        "generated_utc": _utc_ts(),
        "registry_path": _relative(registry_path),
        "mode": "apply" if apply_mode else "dry_run",
        "flow_filter": flow_filter,
        "total_items": len(rows),
        "decision_counts": dict(sorted(by_decision.items())),
        "class_counts": dict(sorted(by_class.items())),
        "action_counts": dict(sorted(actions.items())),
        "candidate_delete_recovery_bytes": candidate_delete_recovery_bytes,
        "context": {
            "h_run_unfinalized": ctx.get("h_run_unfinalized"),
            "h_run_unfinalized_reason": ctx.get("h_run_unfinalized_reason"),
            "h_lock_active": ctx.get("h_lock_active"),
            "h_lock_active_reason": ctx.get("h_lock_active_reason"),
        },
        "apply_allowed": bool(apply_allowed),
        "apply_block_reason": apply_block_reason,
        "action_ledger": _relative(action_ledger_path) if action_ledger_path else "",
    }


def _write_summary(out_dir: Path, run_token: str, payload: dict[str, Any]) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_json = out_dir / f"housekeeping_summary.{run_token}.json"
    latest_json = out_dir / "housekeeping_summary.latest.json"
    storage_run_json = out_dir / f"storage_housekeeping_summary.{run_token}.json"
    storage_latest_json = out_dir / "storage_housekeeping_summary.latest.json"
    txt_path = out_dir / f"housekeeping_summary.{run_token}.txt"

    for p in (run_json, latest_json, storage_run_json, storage_latest_json):
        p.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"generated_utc={payload.get('generated_utc', '')}",
        f"mode={payload.get('mode', '')}",
        f"flow_filter={payload.get('flow_filter', '')}",
        f"total_items={payload.get('total_items', 0)}",
        f"candidate_delete_recovery_bytes={payload.get('candidate_delete_recovery_bytes', 0)}",
    ]
    for key, val in sorted((payload.get("decision_counts", {}) or {}).items()):
        lines.append(f"decision_{key}={val}")
    for key, val in sorted((payload.get("action_counts", {}) or {}).items()):
        lines.append(f"action_{key}={val}")
    lines.append(f"h_run_unfinalized={payload.get('context', {}).get('h_run_unfinalized')}")
    lines.append(f"h_run_unfinalized_reason={payload.get('context', {}).get('h_run_unfinalized_reason')}")
    lines.append(f"h_lock_active={payload.get('context', {}).get('h_lock_active')}")
    lines.append(f"h_lock_active_reason={payload.get('context', {}).get('h_lock_active_reason')}")
    lines.append(f"apply_allowed={payload.get('apply_allowed')}")
    lines.append(f"apply_block_reason={payload.get('apply_block_reason', '')}")
    lines.append(f"action_ledger={payload.get('action_ledger', '')}")
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return run_json, latest_json, txt_path


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Policy-backed log housekeeping dry-run and limited cleanup tool.")
    p.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Path to housekeeping registry JSON")
    p.add_argument("--apply", action="store_true", help="Apply actions for allowed classes (L4/L6) only")
    p.add_argument("--apply-safe", action="store_true", help="Alias for --apply with safety gate enforcement")
    p.add_argument("--output-dir", default="", help="Override output directory (default from registry)")
    p.add_argument("--flow", default="", help="Optional owner flow filter for safe end-of-run housekeeping hooks")
    return p


def main() -> int:
    args = _parser().parse_args()
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = ROOT / registry_path
    if not registry_path.exists():
        raise SystemExit(f"missing_registry:{registry_path}")

    registry = _load_registry(registry_path)
    rules = _build_rules(registry)
    flow_filter = str(args.flow or "").strip().lower()
    if flow_filter:
        rules = [rule for rule in rules if _rule_matches_flow(rule, flow_filter)]
    classes = {str(k): str(v) for k, v in (registry.get("classes", {}) or {}).items()}

    out_dir = Path(args.output_dir) if args.output_dir else Path(str(registry.get("housekeeping_output_dir", "out/housekeeping")))
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    all_files, _ = _collect_paths(registry, rules, flow_filter=flow_filter)
    ctx = _load_context()
    rows = _build_rows(all_files, rules, classes, ctx)

    run_token = _run_id()
    apply_requested = bool(args.apply or args.apply_safe)
    apply_allowed, apply_block_reason = _apply_guard(ctx)
    action_rows: list[dict[str, str]] = []
    if apply_requested:
        action_rows = _apply_actions(rows, rules, out_dir, ctx)
    action_run, action_latest = _write_action_ledger(out_dir, run_token, action_rows)

    report_run = out_dir / f"housekeeping_report.{run_token}.csv"
    report_latest = out_dir / "housekeeping_report.latest.csv"
    storage_report_run = out_dir / f"storage_housekeeping_report.{run_token}.csv"
    storage_report_latest = out_dir / "storage_housekeeping_report.latest.csv"
    _write_csv(report_run, rows)
    _write_csv(report_latest, rows)
    _write_csv(storage_report_run, rows)
    _write_csv(storage_report_latest, rows)

    health_rows = _build_storage_health_rows(rows, rules, registry)
    health_run, health_latest = _write_storage_health(out_dir, run_token, health_rows)

    summary_payload = _summary(
        rows,
        registry_path,
        apply_requested,
        ctx,
        apply_allowed,
        apply_block_reason,
        action_run,
        flow_filter,
    )
    summary_payload["storage_health"] = _relative(health_run)
    summary_payload["storage_health_latest"] = _relative(health_latest)
    summary_run, summary_latest, summary_txt = _write_summary(out_dir, run_token, summary_payload)

    print(f"housekeeping_report={_relative(report_run)}")
    print(f"housekeeping_report_latest={_relative(report_latest)}")
    print(f"storage_housekeeping_report={_relative(storage_report_run)}")
    print(f"storage_housekeeping_report_latest={_relative(storage_report_latest)}")
    print(f"housekeeping_actions={_relative(action_run)}")
    print(f"housekeeping_actions_latest={_relative(action_latest)}")
    print(f"storage_housekeeping_actions_latest={_relative(out_dir / 'storage_housekeeping_actions.latest.csv')}")
    print(f"housekeeping_summary={_relative(summary_run)}")
    print(f"housekeeping_summary_latest={_relative(summary_latest)}")
    print(f"storage_housekeeping_summary_latest={_relative(out_dir / 'storage_housekeeping_summary.latest.json')}")
    print(f"storage_health_latest={_relative(health_latest)}")
    print(f"housekeeping_summary_text={_relative(summary_txt)}")
    print(f"mode={summary_payload.get('mode')}")
    print(f"flow_filter={summary_payload.get('flow_filter')}")
    print(f"total_items={summary_payload.get('total_items')}")
    print(f"candidate_delete_recovery_bytes={summary_payload.get('candidate_delete_recovery_bytes')}")
    for key, val in sorted((summary_payload.get("decision_counts", {}) or {}).items()):
        print(f"decision_{key}={val}")
    for key, val in sorted((summary_payload.get("action_counts", {}) or {}).items()):
        print(f"action_{key}={val}")
    print(f"apply_allowed={summary_payload.get('apply_allowed')}")
    if summary_payload.get("apply_block_reason"):
        print(f"apply_block_reason={summary_payload.get('apply_block_reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
