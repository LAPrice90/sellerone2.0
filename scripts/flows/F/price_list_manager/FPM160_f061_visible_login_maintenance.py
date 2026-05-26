from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import get_manager_paths
from scripts.flows.F.price_list_manager._schemas import LIVE_CYCLE_EVENT_COLUMNS, LIVE_CYCLE_STATUS_COLUMNS


DEFAULT_LOGIN_URL = "https://www.amazon.co.uk/dp/B07BZ3L76B"
REQUEST_FILE_NAME = "f061_visible_login.requested"
DRAIN_READY_FILE_NAME = "F_restart_drain.ready"
DEFAULT_BBP_CHROME_EXE = r"C:\Chrome_UC136\bin\chrome.exe"
DEFAULT_BBP_USER_DATA_DIR = r"C:\Users\Luke\AppData\Local\Chrome_UC136"
DEFAULT_BBP_PROFILE_DIR = "Profile 2"


Launcher = Callable[[list[str], Path], Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _live_dir(root: Path) -> Path:
    return get_manager_paths(root=root).system_dir / "live"


def visible_login_request_path(root: Path) -> Path:
    return _live_dir(root) / REQUEST_FILE_NAME


def drain_ready_path(root: Path) -> Path:
    return _live_dir(root) / DRAIN_READY_FILE_NAME


def _append_event(root: Path, *, event_type: str, status: str, notes: str = "") -> None:
    live_dir = _live_dir(root)
    path = live_dir / "live_cycle_events.csv"
    existing = read_csv(path, LIVE_CYCLE_EVENT_COLUMNS)
    row = pd.DataFrame(
        [
            {
                "event_utc": _utc_now_iso(),
                "cycle_run_id": "fpm160_visible_login",
                "event_type": event_type,
                "supplier_id": "",
                "f061_run_id": "",
                "status": status,
                "rows": "0",
                "notes": notes,
            }
        ]
    )
    write_csv(path, pd.concat([existing, row], ignore_index=True), LIVE_CYCLE_EVENT_COLUMNS)


def _global_maintenance_request_path(root: Path) -> Path:
    return root / "out" / "locks" / "maintenance.requested"


def request_visible_login_maintenance(root: Path, *, legacy_global: bool = False) -> dict[str, str]:
    live_dir = _live_dir(root)
    live_dir.mkdir(parents=True, exist_ok=True)
    path = visible_login_request_path(root)
    requested_at = _utc_now_iso()
    request_text = (
        "\n".join(
            [
                "requested_by=FPM160_f061_visible_login_maintenance",
                "reason=visible_login",
                "action=visible_login",
                "exit_after_drain=0",
                f"requested_utc={requested_at}",
                "",
            ]
        )
    )
    path.write_text(
        request_text,
        encoding="ascii",
        newline="\n",
    )
    global_path = _global_maintenance_request_path(root)
    if legacy_global:
        global_path.parent.mkdir(parents=True, exist_ok=True)
        global_path.write_text(request_text, encoding="ascii", newline="\n")
    _append_event(
        root,
        event_type="visible_login_maintenance_request",
        status="requested",
        notes=f"path={path};legacy_global={int(legacy_global)}",
    )
    return {
        "status": "requested",
        "requested_utc": requested_at,
        "request_path": str(path),
        "legacy_global_request_path": str(global_path) if legacy_global else "",
    }


def clear_visible_login_maintenance(root: Path) -> dict[str, str]:
    request_path = visible_login_request_path(root)
    ready_path = drain_ready_path(root)
    global_path = _global_maintenance_request_path(root)
    request_removed = request_path.exists()
    ready_removed = ready_path.exists()
    global_removed = global_path.exists()
    request_path.unlink(missing_ok=True)
    ready_path.unlink(missing_ok=True)
    global_path.unlink(missing_ok=True)
    _append_event(
        root,
        event_type="visible_login_maintenance_clear",
        status="cleared",
        notes=(
            f"request_removed={int(request_removed)};"
            f"drain_ready_removed={int(ready_removed)};"
            f"global_removed={int(global_removed)}"
        ),
    )
    return {
        "status": "cleared",
        "request_removed": str(int(request_removed)),
        "drain_ready_removed": str(int(ready_removed)),
        "global_removed": str(int(global_removed)),
    }


def visible_login_status(root: Path) -> dict[str, str]:
    live_dir = _live_dir(root)
    request_path = visible_login_request_path(root)
    ready_path = drain_ready_path(root)
    live_status = read_csv(live_dir / "live_cycle_status.csv", LIVE_CYCLE_STATUS_COLUMNS)
    latest = live_status.iloc[-1].to_dict() if not live_status.empty else {}
    child_status = ""
    child_path = live_dir / "f061_child_status.txt"
    if child_path.exists():
        child_status = normalize_text(child_path.read_text(encoding="utf-8", errors="replace"))
    return {
        "request_exists": str(int(request_path.exists())),
        "legacy_global_request_exists": str(int(_global_maintenance_request_path(root).exists())),
        "drain_ready": str(int(ready_path.exists())),
        "live_state": normalize_text(latest.get("state", "")),
        "last_action": normalize_text(latest.get("last_action", "")),
        "last_action_status": normalize_text(latest.get("last_action_status", "")),
        "pending_rows": normalize_text(latest.get("pending_rows", "")),
        "notes": normalize_text(latest.get("notes", "")),
        "child_status": child_status,
        "request_path": str(request_path),
        "drain_ready_path": str(ready_path),
    }


def _default_launcher(cmd: list[str], cwd: Path) -> subprocess.Popen[str]:
    if os.name == "nt":
        return subprocess.Popen(["cmd", "/c", "start", "", *cmd], cwd=str(cwd))
    return subprocess.Popen(cmd, cwd=str(cwd))


def _file_version(path: str) -> str:
    if os.name != "nt":
        return ""
    literal = normalize_text(path).replace("'", "''")
    if literal == "":
        return ""
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Item -LiteralPath '{literal}' -ErrorAction SilentlyContinue).VersionInfo.ProductVersion",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return ""
    return normalize_text(completed.stdout)


def _bbp_extension_health(user_data_dir: str, profile_dir: str) -> dict[str, str]:
    profile_path = Path(user_data_dir) / profile_dir
    extensions_dir = profile_path / "Extensions"
    if not extensions_dir.exists():
        return {
            "ok": "0",
            "reason": "extensions_dir_missing",
            "profile_path": str(profile_path),
            "extension_id": "",
        }
    expected = extensions_dir / "docdmgijbdlobilamkipaleciekbgbgl"
    if expected.exists():
        return {
            "ok": "1",
            "reason": "buybotpro_extension_id_found",
            "profile_path": str(profile_path),
            "extension_id": expected.name,
        }
    manifest_count = 0
    for manifest_path in extensions_dir.glob("*/*/manifest.json"):
        manifest_count += 1
        try:
            text = manifest_path.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        if "buybotpro" in text or "buy bot pro" in text:
            return {
                "ok": "1",
                "reason": "buybotpro_manifest_text_found",
                "profile_path": str(profile_path),
                "extension_id": manifest_path.parents[1].name,
            }
    return {
        "ok": "0",
        "reason": "buybotpro_extension_missing",
        "profile_path": str(profile_path),
        "extension_id": "",
        "manifest_count": str(manifest_count),
    }


def _chrome_snapshot(user_data_dir: str, profile_dir: str) -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    user_data = normalize_text(user_data_dir).replace("'", "''")
    profile = normalize_text(profile_dir).replace("'", "''")
    if user_data == "" or profile == "":
        return []
    ps_command = rf'''
$userData = '{user_data}'
$profileDir = '{profile}'
$rows = Get-CimInstance Win32_Process |
  Where-Object {{
    $_.Name -eq "chrome.exe" -and
    $_.CommandLine -and
    $_.CommandLine -like "*$userData*" -and
    $_.CommandLine -like "*--profile-directory=$profileDir*"
  }} |
  ForEach-Object {{
    $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
    [pscustomobject]@{{
      pid = [string]$_.ProcessId
      parent_pid = [string]$_.ParentProcessId
      executable_path = [string]$_.ExecutablePath
      main_window_handle = if ($p) {{ [string]$p.MainWindowHandle }} else {{ "0" }}
      main_window_title = if ($p) {{ [string]$p.MainWindowTitle }} else {{ "" }}
      command_line = [string]$_.CommandLine
    }}
  }}
@($rows) | ConvertTo-Json -Depth 4
'''
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    raw = normalize_text(completed.stdout)
    if raw == "":
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    rows = parsed if isinstance(parsed, list) else [parsed]
    return [
        {str(key): normalize_text(value) for key, value in row.items()}
        for row in rows
        if isinstance(row, dict) and normalize_text(row.get("pid", ""))
    ]


def _write_launch_status(root: Path, payload: dict[str, Any]) -> None:
    path = root / "out" / "systems" / "F" / "diagnostics" / "fpm160_visible_login_launch_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def stop_scraper_window_hider(root: Path) -> dict[str, str]:
    if os.name != "nt":
        return {"status": "skipped", "reason": "not_windows", "stopped_pids": ""}
    ps_command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -like '*f_hide_scraper_windows.ps1*' } | "
        "ForEach-Object { "
        "$pidValue = $_.ProcessId; "
        "try { Stop-Process -Id $pidValue -Force -ErrorAction Stop; Write-Output $pidValue } catch {} "
        "}"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        return {"status": "failed", "reason": f"{type(exc).__name__}:{normalize_text(exc)}", "stopped_pids": ""}
    stopped = ",".join(line.strip() for line in completed.stdout.splitlines() if line.strip())
    status = "stopped" if stopped else "not_running"
    _append_event(root, event_type="visible_login_window_hider_stop", status=status, notes=f"pids={stopped}")
    return {"status": status, "reason": "", "stopped_pids": stopped}


def _chrome_command(url: str) -> list[str]:
    chrome_exe = normalize_text(os.environ.get("F061_BBP_CHROME_EXE", DEFAULT_BBP_CHROME_EXE))
    user_data_dir = normalize_text(
        os.environ.get("F061_BBP_USER_DATA_DIR", DEFAULT_BBP_USER_DATA_DIR)
    )
    profile_dir = (
        normalize_text(os.environ.get("F061_VISIBLE_LOGIN_PROFILE_DIR", ""))
        or normalize_text(os.environ.get("F061_BBP_PROFILE_DIR", ""))
        or DEFAULT_BBP_PROFILE_DIR
    )
    return [
        chrome_exe,
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile_dir}",
        url,
    ]


def open_visible_login_browser(
    root: Path,
    *,
    url: str = DEFAULT_LOGIN_URL,
    wait_seconds: int = 0,
    verify_seconds: int = 0,
    launcher: Launcher = _default_launcher,
    stop_hider: bool = False,
) -> dict[str, str]:
    started_utc = _utc_now_iso()
    started_monotonic = time.monotonic()
    request_path = visible_login_request_path(root)
    ready_path = drain_ready_path(root)
    if not request_path.exists():
        return {"status": "blocked", "block_reason": "visible_login_request_missing"}

    deadline = time.monotonic() + max(int(wait_seconds), 0)
    while not ready_path.exists() and time.monotonic() < deadline:
        time.sleep(5)

    if not ready_path.exists():
        return {"status": "blocked", "block_reason": "drain_ready_missing"}
    ready_seen_monotonic = time.monotonic()

    cmd = _chrome_command(url)
    chrome_exe = Path(cmd[0])
    if os.name == "nt" and not chrome_exe.exists():
        return {"status": "blocked", "block_reason": f"chrome_not_found:{chrome_exe}"}
    user_data_dir = normalize_text(next((item.split("=", 1)[1] for item in cmd if item.startswith("--user-data-dir=")), ""))
    profile_dir = normalize_text(next((item.split("=", 1)[1] for item in cmd if item.startswith("--profile-directory=")), ""))
    chrome_version = _file_version(str(chrome_exe))
    extension_health = _bbp_extension_health(user_data_dir, profile_dir)
    existing_snapshots = _chrome_snapshot(user_data_dir, profile_dir)
    if existing_snapshots:
        alive_after_verify = True
        visible_window = any(int(row.get("main_window_handle") or 0) != 0 for row in existing_snapshots)
        status_payload: dict[str, Any] = {
            "status": "already_open",
            "started_utc": started_utc,
            "updated_utc": _utc_now_iso(),
            "pid": normalize_text(existing_snapshots[0].get("pid", "")),
            "url": url,
            "chrome_exe": str(chrome_exe),
            "chrome_version": chrome_version,
            "user_data_dir": user_data_dir,
            "profile_dir": profile_dir,
            "bbp_extension_health": extension_health,
            "ready_wait_seconds": round(ready_seen_monotonic - started_monotonic, 3),
            "launch_elapsed_seconds": 0.0,
            "verify_seconds": 0,
            "alive_after_verify": alive_after_verify,
            "visible_window": visible_window,
            "process_snapshot": existing_snapshots,
            "notes": "matching_profile_browser_already_open_no_new_launch",
        }
        _write_launch_status(root, status_payload)
        _append_event(
            root,
            event_type="visible_login_browser_launch",
            status="already_open",
            notes=(
                f"pid={status_payload['pid']};url={url};chrome_exe={chrome_exe};chrome_version={chrome_version};"
                f"user_data_dir={user_data_dir};profile_dir={profile_dir};"
                f"bbp_extension_ok={extension_health.get('ok', '0')};"
                f"ready_wait_seconds={ready_seen_monotonic - started_monotonic:.3f};"
                "launch_elapsed_seconds=0.000;verify_seconds=0;"
                f"alive_after_verify={int(alive_after_verify)};visible_window={int(visible_window)};"
                "existing_browser_reused=1"
            ),
        )
        return {
            "status": "already_open",
            "pid": normalize_text(existing_snapshots[0].get("pid", "")),
            "url": url,
            "chrome_exe": str(chrome_exe),
            "chrome_version": chrome_version,
            "user_data_dir": user_data_dir,
            "profile_dir": profile_dir,
            "bbp_extension_ok": extension_health.get("ok", "0"),
            "bbp_extension_reason": extension_health.get("reason", ""),
            "ready_wait_seconds": f"{ready_seen_monotonic - started_monotonic:.3f}",
            "launch_elapsed_seconds": "0.000",
            "alive_after_verify": str(int(alive_after_verify)),
            "visible_window": str(int(visible_window)),
            "existing_browser_reused": "1",
        }

    hider_result = {"status": "not_requested", "stopped_pids": ""}
    if stop_hider:
        hider_result = stop_scraper_window_hider(root)

    launch_started = time.monotonic()
    proc = launcher(cmd, root)
    launch_elapsed_seconds = time.monotonic() - launch_started
    pid = normalize_text(getattr(proc, "pid", ""))
    snapshots: list[dict[str, str]] = []
    verify_deadline = time.monotonic() + max(int(verify_seconds), 0)
    while time.monotonic() < verify_deadline:
        snapshots = _chrome_snapshot(user_data_dir, profile_dir)
        if snapshots:
            break
        time.sleep(1)
    if max(int(verify_seconds), 0) > 0 and not snapshots:
        snapshots = _chrome_snapshot(user_data_dir, profile_dir)
    alive_after_verify = bool(snapshots)
    visible_window = any(int(row.get("main_window_handle") or 0) != 0 for row in snapshots)
    status_payload: dict[str, Any] = {
        "status": "launched",
        "started_utc": started_utc,
        "updated_utc": _utc_now_iso(),
        "pid": pid,
        "url": url,
        "chrome_exe": str(chrome_exe),
        "chrome_version": chrome_version,
        "user_data_dir": user_data_dir,
        "profile_dir": profile_dir,
        "bbp_extension_health": extension_health,
        "ready_wait_seconds": round(ready_seen_monotonic - started_monotonic, 3),
        "launch_elapsed_seconds": round(launch_elapsed_seconds, 3),
        "verify_seconds": max(int(verify_seconds), 0),
        "alive_after_verify": alive_after_verify,
        "visible_window": visible_window,
        "process_snapshot": snapshots,
    }
    _write_launch_status(root, status_payload)
    _append_event(
        root,
        event_type="visible_login_browser_launch",
        status="launched",
        notes=(
            f"pid={pid};url={url};chrome_exe={chrome_exe};chrome_version={chrome_version};"
            f"user_data_dir={user_data_dir};profile_dir={profile_dir};"
            f"bbp_extension_ok={extension_health.get('ok', '0')};"
            f"ready_wait_seconds={ready_seen_monotonic - started_monotonic:.3f};"
            f"launch_elapsed_seconds={launch_elapsed_seconds:.3f};"
            f"verify_seconds={max(int(verify_seconds), 0)};"
            f"alive_after_verify={int(alive_after_verify)};visible_window={int(visible_window)};"
            f"hider_status={hider_result.get('status', '')}"
        ),
    )
    return {
        "status": "launched",
        "pid": pid,
        "url": url,
        "chrome_exe": str(chrome_exe),
        "chrome_version": chrome_version,
        "user_data_dir": user_data_dir,
        "profile_dir": profile_dir,
        "bbp_extension_ok": extension_health.get("ok", "0"),
        "bbp_extension_reason": extension_health.get("reason", ""),
        "ready_wait_seconds": f"{ready_seen_monotonic - started_monotonic:.3f}",
        "launch_elapsed_seconds": f"{launch_elapsed_seconds:.3f}",
        "alive_after_verify": str(int(alive_after_verify)),
        "visible_window": str(int(visible_window)),
        "hider_status": normalize_text(hider_result.get("status", "")),
        "hider_stopped_pids": normalize_text(hider_result.get("stopped_pids", "")),
    }


def _print_result(result: dict[str, str], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    for key, value in result.items():
        print(f"{key}: {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pause F061 safely and open a visible Amazon login browser.")
    parser.add_argument("--root", default=str(ROOT), help="Repository root. Defaults to the current repo.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    request_parser = subparsers.add_parser("request", help="Request F061 visible-login maintenance at the next chunk boundary.")
    request_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    request_parser.add_argument(
        "--legacy-global",
        action="store_true",
        help="Also write the old global maintenance marker for an already-running FPM130 owner.",
    )
    status_parser = subparsers.add_parser("status", help="Show request, drain, and live scanner status.")
    status_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    open_parser = subparsers.add_parser("open", help="Open the visible Chrome login window after drain-ready.")
    open_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    open_parser.add_argument("--url", default=DEFAULT_LOGIN_URL)
    open_parser.add_argument("--wait-seconds", type=int, default=0)
    open_parser.add_argument("--verify-seconds", type=int, default=10)
    clear_parser = subparsers.add_parser("clear", help="Clear visible-login maintenance and let FPM130 resume.")
    clear_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.command == "request":
        result = request_visible_login_maintenance(root, legacy_global=bool(getattr(args, "legacy_global", False)))
    elif args.command == "status":
        result = visible_login_status(root)
    elif args.command == "open":
        result = open_visible_login_browser(
            root,
            url=args.url,
            wait_seconds=args.wait_seconds,
            verify_seconds=args.verify_seconds,
            stop_hider=True,
        )
    elif args.command == "clear":
        result = clear_visible_login_maintenance(root)
    else:
        parser.error(f"unknown command: {args.command}")

    _print_result(result, as_json=bool(args.json))
    return 0 if result.get("status") != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
