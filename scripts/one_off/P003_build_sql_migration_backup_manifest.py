from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]

BACKUP_ROOT_REL = Path("out") / "backups" / "sql_storage_migration_v1"
REGISTRY_REL = Path("project_control") / "DATA_BLUEPRINT_REGISTRY.csv"

CORE_SCOPE_PATHS = [
    "AGENTS.md",
    "CODEX.md",
    "README.md",
    "run_A_all.bat",
    "run_B_cycle.bat",
    "run_E_all.bat",
    "run_H_cycle.bat",
    "run_api_collection.py",
    "config",
    "data",
    "project_control",
    "scripts",
    "tests",
    "plans",
]

FULL_SCOPE_PATHS = CORE_SCOPE_PATHS + [
    "out",
    "reference",
]

LOCK_PATHS = [
    "out/B_cycle.lock",
    "out/systems/B/live/B_cycle.lock",
    "out/systems/B/live/B_supervisor.lock",
    "out/E_cycle.lock",
    "out/systems/E/live/E_cycle.lock",
    "out/systems/H/live/H_launcher.lock",
    "out/H_pricing_cycle.lock",
    "out/systems/H/live/H_pricing_cycle.lock",
    "out/H_cycle.lock",
    "out/systems/H/live/H_cycle.lock",
    "out/locks/maintenance.active",
    "out/locks/h_controlled_mode.active",
]

INFO_MARKER_PATHS = [
    "out/locks/maintenance.requested",
    "out/locks/maintenance.ready",
    "out/locks/b_cycle.maintenance",
    "out/locks/restart_control/restart_controller.latest.json",
    "out/H_cycle_last_terminal_info.txt",
    "out/h_pricing_cycle_state.json",
    "out/systems/H/live/H_runtime_status.json",
]

PROTECTED_CHANGE_PATHS = [
    "out/B_cycle.log",
    "out/H_cycle.log",
    "out/H_pricing_cycle.log",
    "out/e_run_log.jsonl",
    "out/api_call_log.jsonl",
    "out/api_run_log.csv",
    "data/sku_daily_intel.csv",
    "data/execution_log.csv",
    "data/offer_snapshot_facts.csv",
]

PROCESS_MATCH_TERMS = [
    "run_A_all.py",
    "run_B_cycle.py",
    "run_B_supervisor.py",
    "run_E_cycle.py",
    "run_H_pricing_cycle.py",
    "run_H_pricing_cycle_guarded.py",
    "run_O_cycle.py",
    "run_api_collection.py",
    "home_time_monitor.py",
    "home_time_supervisor",
    "controlled_restart_controller.py",
    "H_item_offers_lookup.py",
    "get_inventory_summaries.py",
    "get_orders.py",
    "get_pricing.py",
    "get_financial_events.py",
    "get_merchant_listings_report.py",
]

MANIFEST_COLUMNS = [
    "backup_bundle_id",
    "generated_at_utc",
    "scope",
    "path",
    "category",
    "owner_flow",
    "dataset_id",
    "dataset_family",
    "dataset_type",
    "registry_role",
    "exists",
    "size_bytes",
    "mtime_utc",
    "sha256",
    "hash_status",
    "row_count",
    "row_count_status",
    "header_hash",
    "header",
    "error",
]


@dataclass(frozen=True)
class RegistryTarget:
    dataset_id: str
    dataset_family: str
    owner_cycle: str
    dataset_type: str
    path_pattern: str
    role: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def display_path(path: Path, root: Path = ROOT) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_lock_line(line: str) -> dict[str, str]:
    pid_match = re.search(r"(?:^|\|)(?:pid|launcher_pid)=(\d+)", line)
    run_match = re.search(r"(?:^|\|)run_id=([^|\s]+)", line)
    heartbeat_match = re.search(r"(?:^|\|)heartbeat=([^|\s]+)", line)
    return {
        "pid": pid_match.group(1) if pid_match else "",
        "run_id": run_match.group(1) if run_match else "",
        "heartbeat": heartbeat_match.group(1) if heartbeat_match else "",
    }


def pid_running(pid_text: str) -> bool | None:
    if not pid_text:
        return None
    try:
        pid = int(pid_text)
    except ValueError:
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        return str(pid) in (result.stdout or "")
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_first_line(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip()
    except Exception:
        return ""


def lock_state(path: Path, root: Path = ROOT) -> dict[str, Any]:
    exists = path.exists()
    line = read_first_line(path) if exists else ""
    parsed = parse_lock_line(line)
    return {
        "path": display_path(path, root),
        "exists": exists,
        "line": line,
        "pid": parsed["pid"],
        "pid_running": pid_running(parsed["pid"]) if exists else None,
        "run_id": parsed["run_id"],
        "heartbeat": parsed["heartbeat"],
    }


def marker_state(path: Path, root: Path = ROOT) -> dict[str, Any]:
    return {
        "path": display_path(path, root),
        "exists": path.exists(),
        "line": read_first_line(path),
    }


def process_rows() -> list[dict[str, str]]:
    if os.name == "nt":
        command = (
            "Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,CommandLine | "
            "ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return []
        if result.returncode != 0 or not result.stdout.strip():
            return []
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, dict):
            parsed = [parsed]
        rows: list[dict[str, str]] = []
        for item in parsed:
            rows.append(
                {
                    "pid": str(item.get("ProcessId", "")),
                    "command": str(item.get("CommandLine", "") or ""),
                }
            )
        return rows

    try:
        result = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True, check=False)
    except OSError:
        return []
    rows = []
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.strip().split(maxsplit=1)
        if not parts:
            continue
        rows.append({"pid": parts[0], "command": parts[1] if len(parts) > 1 else ""})
    return rows


def find_process_matches(rows: Iterable[dict[str, str]] | None = None) -> list[dict[str, str]]:
    rows = list(process_rows() if rows is None else rows)
    matches: list[dict[str, str]] = []
    own_pid = str(os.getpid())
    for row in rows:
        command = row.get("command", "")
        if not command or row.get("pid") == own_pid:
            continue
        for term in PROCESS_MATCH_TERMS:
            if term.lower() in command.lower():
                matches.append({"pid": row.get("pid", ""), "term": term, "command": command})
                break
    return matches


def _snapshot_mtimes(root: Path, rel_paths: Iterable[str]) -> dict[str, float | None]:
    snapshot: dict[str, float | None] = {}
    for rel in rel_paths:
        path = root / rel
        try:
            snapshot[rel] = path.stat().st_mtime if path.exists() else None
        except OSError:
            snapshot[rel] = None
    return snapshot


def changed_protected_paths(root: Path, quiet_seconds: int) -> list[dict[str, Any]]:
    if quiet_seconds <= 0:
        return []
    before = _snapshot_mtimes(root, PROTECTED_CHANGE_PATHS)
    time.sleep(quiet_seconds)
    after = _snapshot_mtimes(root, PROTECTED_CHANGE_PATHS)
    changes: list[dict[str, Any]] = []
    for rel, before_mtime in before.items():
        after_mtime = after.get(rel)
        if before_mtime != after_mtime:
            changes.append(
                {
                    "path": rel,
                    "before_mtime": before_mtime,
                    "after_mtime": after_mtime,
                }
            )
    return changes


def collect_pause_state(
    root: Path = ROOT,
    *,
    quiet_seconds: int = 0,
    scan_processes: bool = True,
    injected_process_rows: Iterable[dict[str, str]] | None = None,
) -> dict[str, Any]:
    locks = [lock_state(root / rel, root=root) for rel in LOCK_PATHS]
    markers = [marker_state(root / rel, root=root) for rel in INFO_MARKER_PATHS]
    matches = find_process_matches(injected_process_rows) if scan_processes else []
    changes = changed_protected_paths(root, quiet_seconds=quiet_seconds)

    blockers: list[str] = []
    for item in locks:
        if item["exists"]:
            state = "running" if item["pid_running"] else "unresolved"
            blockers.append(f"lock_present:{item['path']}:{state}")
    for match in matches:
        blockers.append(f"process_match:{match['term']}:pid={match['pid']}")
    for change in changes:
        blockers.append(f"protected_path_changed:{change['path']}")

    return {
        "generated_at_utc": utc_now_iso(),
        "safe_to_backup": not blockers,
        "quiet_seconds": quiet_seconds,
        "blockers": blockers,
        "locks": locks,
        "markers": markers,
        "process_matches": matches,
        "protected_path_changes": changes,
    }


def load_registry(root: Path = ROOT) -> list[dict[str, str]]:
    path = root / REGISTRY_REL
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def registry_targets(root: Path = ROOT) -> list[RegistryTarget]:
    targets: list[RegistryTarget] = []
    for row in load_registry(root):
        base = {
            "dataset_id": row.get("dataset_id", ""),
            "dataset_family": row.get("dataset_family", ""),
            "owner_cycle": row.get("owner_cycle", ""),
            "dataset_type": row.get("dataset_type", ""),
        }
        canonical = row.get("canonical_path", "").strip()
        if canonical:
            targets.append(RegistryTarget(path_pattern=canonical, role="canonical", **base))
        mirrors = row.get("allowed_mirror_paths", "")
        for mirror in [item.strip() for item in mirrors.split("|") if item.strip()]:
            targets.append(RegistryTarget(path_pattern=mirror, role="mirror", **base))
    return targets


def path_category(path_rel: str) -> str:
    if path_rel.startswith("out/"):
        return "runtime_output"
    if path_rel.startswith("data/"):
        return "runtime_data"
    if path_rel.startswith("config/"):
        return "config"
    if path_rel.startswith("reference/"):
        return "reference_input"
    if path_rel.startswith("scripts/"):
        return "code"
    if path_rel.startswith("tests/"):
        return "tests"
    if path_rel.startswith("project_control/"):
        return "governance"
    if path_rel.startswith("plans/"):
        return "plan"
    return "repo_file"


def _iter_existing_files(root: Path, rel_paths: Iterable[str]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    errors: list[str] = []

    def onerror(error: OSError) -> None:
        errors.append(str(error))

    for rel in rel_paths:
        path = root / rel
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for dirpath, dirnames, filenames in os.walk(path, onerror=onerror):
                dirnames[:] = [name for name in dirnames if name not in {".git", "__pycache__", ".pytest_cache"}]
                for filename in filenames:
                    files.append(Path(dirpath) / filename)
        elif any(ch in rel for ch in "*?[]"):
            for match in root.glob(rel):
                if match.is_file():
                    files.append(match)
    return sorted(set(files)), errors


def _target_matches(root: Path, target: RegistryTarget) -> list[Path]:
    pattern = target.path_pattern.strip()
    if not pattern:
        return []
    if any(ch in pattern for ch in "*?[]"):
        return sorted(path for path in root.glob(pattern) if path.is_file())
    return [root / pattern]


def sha256_file(path: Path, *, max_hash_bytes: int | None) -> tuple[str, str]:
    try:
        size = path.stat().st_size
        if max_hash_bytes is not None and size > max_hash_bytes:
            return "", "skipped_large"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest(), "ok"
    except Exception as exc:
        return "", f"error:{exc.__class__.__name__}"


def tabular_counts(path: Path, *, required: bool, max_count_bytes: int | None) -> tuple[str, str, str, str]:
    suffix = path.suffix.lower()
    if suffix not in {".csv", ".tsv"}:
        return "", "not_tabular", "", ""
    try:
        size = path.stat().st_size
        if not required and max_count_bytes is not None and size > max_count_bytes:
            return "", "skipped_large", "", ""
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            first_line = handle.readline()
            header = first_line.rstrip("\r\n")
            header_hash = hashlib.sha256(header.encode("utf-8", errors="replace")).hexdigest() if header else ""
            count = sum(1 for _ in handle)
        row_count = max(count, 0)
        return str(row_count), "ok", header_hash, header
    except Exception as exc:
        return "", f"error:{exc.__class__.__name__}", "", ""


def _blank_row(
    *,
    backup_bundle_id: str,
    generated_at_utc: str,
    scope: str,
    path_rel: str,
    target: RegistryTarget | None,
    registry_role: str,
    exists: bool,
    error: str = "",
) -> dict[str, str]:
    return {
        "backup_bundle_id": backup_bundle_id,
        "generated_at_utc": generated_at_utc,
        "scope": scope,
        "path": path_rel,
        "category": path_category(path_rel),
        "owner_flow": target.owner_cycle if target else "",
        "dataset_id": target.dataset_id if target else "",
        "dataset_family": target.dataset_family if target else "",
        "dataset_type": target.dataset_type if target else "",
        "registry_role": registry_role,
        "exists": "true" if exists else "false",
        "size_bytes": "",
        "mtime_utc": "",
        "sha256": "",
        "hash_status": "missing" if not exists else "",
        "row_count": "",
        "row_count_status": "missing" if not exists else "",
        "header_hash": "",
        "header": "",
        "error": error,
    }


def manifest_row_for_file(
    path: Path,
    *,
    root: Path,
    backup_bundle_id: str,
    generated_at_utc: str,
    scope: str,
    target: RegistryTarget | None = None,
    registry_role: str = "",
    max_hash_bytes: int | None = 100 * 1024 * 1024,
    max_count_bytes: int | None = 250 * 1024 * 1024,
) -> dict[str, str]:
    path_rel = display_path(path, root)
    row = _blank_row(
        backup_bundle_id=backup_bundle_id,
        generated_at_utc=generated_at_utc,
        scope=scope,
        path_rel=path_rel,
        target=target,
        registry_role=registry_role,
        exists=path.exists(),
    )
    if not path.exists():
        return row
    try:
        stat = path.stat()
        row["size_bytes"] = str(stat.st_size)
        row["mtime_utc"] = (
            datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        digest, hash_status = sha256_file(path, max_hash_bytes=max_hash_bytes)
        row["sha256"] = digest
        row["hash_status"] = hash_status
        required = target is not None
        row_count, count_status, header_hash, header = tabular_counts(
            path,
            required=required,
            max_count_bytes=max_count_bytes,
        )
        row["row_count"] = row_count
        row["row_count_status"] = count_status
        row["header_hash"] = header_hash
        row["header"] = header
    except Exception as exc:
        row["error"] = f"{exc.__class__.__name__}: {exc}"
    return row


def build_manifest_rows(
    *,
    root: Path = ROOT,
    scope: str = "registry",
    backup_bundle_id: str | None = None,
    generated_at_utc: str | None = None,
    max_hash_mb: float | None = 100.0,
    max_count_mb: float | None = 250.0,
) -> tuple[list[dict[str, str]], list[str]]:
    backup_bundle_id = backup_bundle_id or f"sql_storage_migration_v1_{utc_now_iso().replace(':', '').replace('-', '')}"
    generated_at_utc = generated_at_utc or utc_now_iso()
    max_hash_bytes = None if max_hash_mb is None else int(max_hash_mb * 1024 * 1024)
    max_count_bytes = None if max_count_mb is None else int(max_count_mb * 1024 * 1024)

    rows: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()

    targets = registry_targets(root)
    if scope in {"registry", "core", "full"}:
        for target in targets:
            matches = _target_matches(root, target)
            if not matches:
                path_rel = target.path_pattern
                rows.append(
                    _blank_row(
                        backup_bundle_id=backup_bundle_id,
                        generated_at_utc=generated_at_utc,
                        scope=scope,
                        path_rel=path_rel,
                        target=target,
                        registry_role=target.role,
                        exists=False,
                    )
                )
                seen.add(path_rel)
                continue
            for path in matches:
                path_rel = display_path(path, root)
                rows.append(
                    manifest_row_for_file(
                        path,
                        root=root,
                        backup_bundle_id=backup_bundle_id,
                        generated_at_utc=generated_at_utc,
                        scope=scope,
                        target=target,
                        registry_role=target.role,
                        max_hash_bytes=max_hash_bytes,
                        max_count_bytes=max_count_bytes,
                    )
                )
                seen.add(path_rel)

    if scope in {"core", "full"}:
        file_scope = CORE_SCOPE_PATHS if scope == "core" else FULL_SCOPE_PATHS
        files, walk_errors = _iter_existing_files(root, file_scope)
        errors.extend(walk_errors)
        for path in files:
            path_rel = display_path(path, root)
            if path_rel in seen:
                continue
            rows.append(
                manifest_row_for_file(
                    path,
                    root=root,
                    backup_bundle_id=backup_bundle_id,
                    generated_at_utc=generated_at_utc,
                    scope=scope,
                    target=None,
                    registry_role="",
                    max_hash_bytes=max_hash_bytes,
                    max_count_bytes=max_count_bytes,
                )
            )
            seen.add(path_rel)

    rows.sort(key=lambda row: (row["category"], row["path"], row["dataset_id"]))
    return rows, errors


def write_manifest_outputs(
    *,
    root: Path = ROOT,
    output_root: Path | None = None,
    scope: str = "registry",
    backup_bundle_id: str | None = None,
    max_hash_mb: float | None = 100.0,
    max_count_mb: float | None = 250.0,
    quiet_seconds: int = 0,
    scan_processes: bool = True,
) -> dict[str, Any]:
    generated_at_utc = utc_now_iso()
    backup_bundle_id = backup_bundle_id or f"sql_storage_migration_v1_{generated_at_utc.replace(':', '').replace('-', '')}"
    output_root = output_root or (root / BACKUP_ROOT_REL)
    bundle_dir = output_root / backup_bundle_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    pause_state = collect_pause_state(
        root,
        quiet_seconds=quiet_seconds,
        scan_processes=scan_processes,
    )
    rows, scan_errors = build_manifest_rows(
        root=root,
        scope=scope,
        backup_bundle_id=backup_bundle_id,
        generated_at_utc=generated_at_utc,
        max_hash_mb=max_hash_mb,
        max_count_mb=max_count_mb,
    )

    manifest_path = bundle_dir / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "backup_bundle_id": backup_bundle_id,
        "generated_at_utc": generated_at_utc,
        "scope": scope,
        "bundle_dir": display_path(bundle_dir, root),
        "manifest_path": display_path(manifest_path, root),
        "row_count": len(rows),
        "existing_file_count": sum(1 for row in rows if row["exists"] == "true"),
        "missing_registry_target_count": sum(1 for row in rows if row["exists"] == "false"),
        "hash_ok_count": sum(1 for row in rows if row["hash_status"] == "ok"),
        "hash_skipped_large_count": sum(1 for row in rows if row["hash_status"] == "skipped_large"),
        "scan_error_count": len(scan_errors),
        "scan_errors": scan_errors,
        "pause_state": pause_state,
        "safe_to_start_backup": pause_state["safe_to_backup"],
        "note": "This tool writes a manifest only. It does not stop processes, copy data, migrate storage, or change Sheets.",
    }
    summary_path = bundle_dir / "summary.json"
    summary["summary_path"] = display_path(summary_path, root)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _text_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"backup_bundle_id={summary['backup_bundle_id']}",
        f"scope={summary['scope']}",
        f"manifest_path={summary.get('manifest_path', '')}",
        f"summary_path={summary.get('summary_path', '')}",
        f"row_count={summary.get('row_count', '')}",
        f"existing_file_count={summary.get('existing_file_count', '')}",
        f"missing_registry_target_count={summary.get('missing_registry_target_count', '')}",
        f"safe_to_start_backup={'yes' if summary.get('safe_to_start_backup') else 'no'}",
    ]
    pause_state = summary.get("pause_state", {})
    blockers = pause_state.get("blockers", [])
    if blockers:
        lines.append("blockers:")
        for blocker in blockers:
            lines.append(f"- {blocker}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the SQL storage migration pause check and backup manifest."
    )
    parser.add_argument("--root", default=str(ROOT), help="Repo root. Defaults to current SellerOne repo.")
    parser.add_argument(
        "--scope",
        choices=["registry", "core", "full"],
        default="registry",
        help="Manifest scope. Use full only during an approved pause window.",
    )
    parser.add_argument("--backup-id", default="", help="Optional explicit backup bundle id.")
    parser.add_argument("--output-root", default="", help="Optional output root for manifest bundle.")
    parser.add_argument("--max-hash-mb", type=float, default=100.0, help="Skip hashes above this size. Use -1 for no limit.")
    parser.add_argument("--max-count-mb", type=float, default=250.0, help="Skip non-registry row counts above this size. Use -1 for no limit.")
    parser.add_argument("--quiet-seconds", type=int, default=0, help="Watch protected files for changes for this many seconds.")
    parser.add_argument("--skip-process-scan", action="store_true", help="Skip process command-line scan.")
    parser.add_argument("--write-manifest", action="store_true", help="Write manifest.csv and summary.json.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    max_hash_mb = None if args.max_hash_mb < 0 else args.max_hash_mb
    max_count_mb = None if args.max_count_mb < 0 else args.max_count_mb
    output_root = Path(args.output_root).resolve() if args.output_root else None

    if args.write_manifest:
        summary = write_manifest_outputs(
            root=root,
            output_root=output_root,
            scope=args.scope,
            backup_bundle_id=args.backup_id or None,
            max_hash_mb=max_hash_mb,
            max_count_mb=max_count_mb,
            quiet_seconds=args.quiet_seconds,
            scan_processes=not args.skip_process_scan,
        )
    else:
        pause_state = collect_pause_state(
            root,
            quiet_seconds=args.quiet_seconds,
            scan_processes=not args.skip_process_scan,
        )
        summary = {
            "backup_bundle_id": args.backup_id or "",
            "generated_at_utc": pause_state["generated_at_utc"],
            "scope": args.scope,
            "manifest_path": "",
            "summary_path": "",
            "row_count": "",
            "existing_file_count": "",
            "missing_registry_target_count": "",
            "pause_state": pause_state,
            "safe_to_start_backup": pause_state["safe_to_backup"],
            "note": "Pause check only. Add --write-manifest to write manifest outputs.",
        }

    if args.format == "json":
        print(json.dumps(summary, indent=2))
    else:
        print(_text_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
