from __future__ import annotations

import argparse
import csv
import json
import os
import random
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHROME_EXE = r"C:\Chrome_UC136\bin\chrome.exe"
USER_DATA_DIR = r"C:\Users\Luke\AppData\Local\Chrome_UC136"
PROFILE_DIR = "Profile 2"
DRIVER_EXE = (
    r"C:\Users\Luke\.nuget\packages\selenium.webdriver.chromedriver"
    r"\136.0.7103.4800-beta\driver\win32\chromedriver.exe"
)

PLAN_DESCRIPTIONS = {
    "uc_direct": "Current F061-style undetected_chromedriver launch, visible mode.",
    "selenium_direct": "Standard Selenium ChromeDriver launch, visible mode.",
    "raw_attach_subprocess": "Prelaunch raw Chrome from the script, then attach Selenium.",
    "raw_attach_explorer": "Prelaunch raw Chrome through Windows Explorer shell, then attach Selenium.",
    "raw_attach_scheduled": "Prelaunch raw Chrome through a temporary interactive Scheduled Task, then attach Selenium.",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _free_port() -> int:
    for _ in range(50):
        port = random.randint(61000, 64900)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free local port found")


def _ps_json(command: str, timeout: float = 10.0) -> Any:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    text = completed.stdout.strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except Exception:
        return {"stdout": completed.stdout, "stderr": completed.stderr, "rc": completed.returncode}


def _process_rows_for_label(label: str) -> list[dict[str, Any]]:
    pattern = label.replace("'", "''")
    command = f"""
$rows = Get-CimInstance Win32_Process | Where-Object {{
  $_.CommandLine -like '*{pattern}*' -and ($_.Name -eq 'chrome.exe' -or $_.Name -like '*chromedriver*')
}} | ForEach-Object {{
  $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
  [pscustomobject]@{{
    pid = [int]$_.ProcessId
    parent_pid = [int]$_.ParentProcessId
    name = [string]$_.Name
    executable_path = [string]$_.ExecutablePath
    main_window_handle = if ($p) {{ [int64]$p.MainWindowHandle }} else {{ 0 }}
    main_window_title = if ($p) {{ [string]$p.MainWindowTitle }} else {{ '' }}
    command_line = [string]$_.CommandLine
  }}
}}
@($rows) | ConvertTo-Json -Depth 5
"""
    payload = _ps_json(command)
    if isinstance(payload, dict):
        return [payload] if payload.get("pid") else []
    return payload if isinstance(payload, list) else []


def _cleanup_label(label: str) -> None:
    pattern = label.replace("'", "''")
    command = f"""
$rows = Get-CimInstance Win32_Process | Where-Object {{
  $_.CommandLine -like '*{pattern}*' -and ($_.Name -eq 'chrome.exe' -or $_.Name -like '*chromedriver*')
}} | Sort-Object ProcessId -Descending
foreach ($row in $rows) {{
  try {{ & taskkill.exe /PID $row.ProcessId /T /F | Out-Null }} catch {{ }}
  try {{ Stop-Process -Id $row.ProcessId -Force -ErrorAction SilentlyContinue }} catch {{ }}
}}
"""
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], capture_output=True)


def _wait_devtools(port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def _detect_bbp_state(driver: Any) -> dict[str, Any]:
    from selenium.webdriver.common.by import By

    result: dict[str, Any] = {
        "checked_utc": _utc_now_iso(),
        "current_url": "",
        "title": "",
        "default_bbp_frame_count": 0,
        "default_bbp_container_count": 0,
        "inside_frame": False,
        "login_email_count": 0,
        "login_password_count": 0,
        "login_button_count": 0,
        "cost_field_count": 0,
        "dashboard_yes_no": "",
        "body_contains_buybotpro": False,
        "error": "",
    }
    try:
        result["current_url"] = _safe_text(getattr(driver, "current_url", ""))
        result["title"] = _safe_text(getattr(driver, "title", ""))
    except Exception as exc:
        result["error"] = f"url_title:{type(exc).__name__}:{exc}"

    try:
        frames = driver.find_elements(By.ID, "bbp-frame")
        containers = driver.find_elements(By.ID, "bbp-container")
        result["default_bbp_frame_count"] = len(frames)
        result["default_bbp_container_count"] = len(containers)
        if frames:
            driver.switch_to.frame(frames[0])
            result["inside_frame"] = True
    except Exception as exc:
        result["error"] = f"frame_probe:{type(exc).__name__}:{exc}"

    try:
        result["login_email_count"] = len(driver.find_elements(By.CSS_SELECTOR, "#loginEmail"))
        result["login_password_count"] = len(driver.find_elements(By.CSS_SELECTOR, "#loginPassword"))
        result["login_button_count"] = len(driver.find_elements(By.CSS_SELECTOR, "#loginBtn"))
        result["cost_field_count"] = len(driver.find_elements(By.CSS_SELECTOR, "#txtBuyPrice"))
        dashboard = driver.find_elements(By.CSS_SELECTOR, "#dashboardYesOrNo")
        if dashboard:
            result["dashboard_yes_no"] = _safe_text(dashboard[0].text or dashboard[0].get_attribute("value")).upper()
        bodies = driver.find_elements(By.TAG_NAME, "body")
        body_text = " ".join(_safe_text(getattr(node, "text", "")) for node in bodies).lower()
        result["body_contains_buybotpro"] = "buybotpro" in body_text or "buy bot pro" in body_text
    except Exception as exc:
        result["error"] = f"field_probe:{type(exc).__name__}:{exc}"

    try:
        driver.switch_to.default_content()
    except Exception:
        pass

    result["bbp_login_fields_detected"] = (
        int(result["login_email_count"]) > 0
        and int(result["login_password_count"]) > 0
        and int(result["login_button_count"]) > 0
    )
    result["bbp_authenticated_fields_detected"] = int(result["cost_field_count"]) > 0
    result["bbp_panel_detected"] = (
        int(result["default_bbp_frame_count"]) > 0
        or int(result["default_bbp_container_count"]) > 0
        or bool(result["bbp_login_fields_detected"])
        or bool(result["bbp_authenticated_fields_detected"])
    )
    return result


def _common_chrome_args(label: str, port: int, user_data_dir: str, profile_dir: str) -> list[str]:
    return [
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile_dir}",
        f"--remote-debugging-port={port}",
        "--remote-debugging-host=127.0.0.1",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1400,900",
        "--window-position=80,80",
        "--start-maximized",
        "--log-level=3",
        f"--sellerone-hold-plan={label}",
    ]


def _open_page_and_detect(driver: Any, url: str, hold_seconds: float) -> dict[str, Any]:
    try:
        driver.set_window_position(80, 80)
        driver.set_window_size(1400, 900)
    except Exception:
        pass
    driver.get(url)
    time.sleep(3)
    try:
        driver.refresh()
        time.sleep(3)
    except Exception:
        pass
    detection = _detect_bbp_state(driver)
    time.sleep(max(float(hold_seconds), 0.0))
    return detection


def _launch_uc(label: str, port: int, args: argparse.Namespace):
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.binary_location = args.chrome_exe
    for item in _common_chrome_args(label, port, args.user_data_dir, args.profile_dir):
        options.add_argument(item)
    return uc.Chrome(options=options, version_main=136, driver_executable_path=args.driver_exe)


def _launch_selenium(label: str, port: int, args: argparse.Namespace):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    options = Options()
    options.binary_location = args.chrome_exe
    for item in _common_chrome_args(label, port, args.user_data_dir, args.profile_dir):
        options.add_argument(item)
    service = Service(args.driver_exe)
    return webdriver.Chrome(service=service, options=options)


def _launch_raw_subprocess(label: str, port: int, args: argparse.Namespace) -> subprocess.Popen:
    cmd = [args.chrome_exe, *_common_chrome_args(label, port, args.user_data_dir, args.profile_dir), args.url]
    return subprocess.Popen(cmd)


def _launch_raw_explorer(label: str, port: int, args: argparse.Namespace) -> None:
    chrome_args = " ".join(
        f'"{part}"' if " " in part else part for part in [*_common_chrome_args(label, port, args.user_data_dir, args.profile_dir), args.url]
    )
    command = f"""
$shell = New-Object -ComObject Shell.Application
$shell.ShellExecute('{args.chrome_exe}', '{chrome_args.replace("'", "''")}', '', 'open', 1)
"""
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], check=False)


def _launch_raw_scheduled(label: str, port: int, args: argparse.Namespace, root: Path) -> str:
    diag = root / "out" / "systems" / "F" / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    bat = diag / f"{label}.cmd"
    chrome_args = " ".join(
        f'"{part}"' if " " in part else part for part in [*_common_chrome_args(label, port, args.user_data_dir, args.profile_dir), args.url]
    )
    bat.write_text(f'@echo off\r\nstart "" "{args.chrome_exe}" {chrome_args}\r\n', encoding="utf-8")
    task_name = f"SellerOne F064 {label}"
    start_time = (datetime.now().replace(second=0, microsecond=0)).strftime("%H:%M")
    create = [
        "schtasks",
        "/Create",
        "/TN",
        task_name,
        "/TR",
        f'cmd.exe /c "{bat}"',
        "/SC",
        "ONCE",
        "/ST",
        start_time,
        "/F",
        "/IT",
    ]
    subprocess.run(create, capture_output=True, text=True)
    subprocess.run(["schtasks", "/Run", "/TN", task_name], capture_output=True, text=True)
    return task_name


def _attach_selenium(port: int, args: argparse.Namespace):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    options = Options()
    options.debugger_address = f"127.0.0.1:{port}"
    service = Service(args.driver_exe)
    return webdriver.Chrome(service=service, options=options)


def run_plan(plan: str, index: int, args: argparse.Namespace, root: Path) -> dict[str, Any]:
    port = _free_port()
    label = f"f064_{index}_{plan}_{_utc_now_iso().replace('-', '').replace(':', '')}"
    output: dict[str, Any] = {
        "plan": plan,
        "description": PLAN_DESCRIPTIONS.get(plan, ""),
        "label": label,
        "port": port,
        "started_utc": _utc_now_iso(),
        "finished_utc": "",
        "url": args.url,
        "chrome_exe": args.chrome_exe,
        "user_data_dir": args.user_data_dir,
        "profile_dir": args.profile_dir,
        "held_seconds": args.hold_seconds,
        "launch_ok": False,
        "attach_ok": False,
        "page_ok": False,
        "visible_window": False,
        "bbp_panel_detected": False,
        "bbp_authenticated_fields_detected": False,
        "bbp_login_fields_detected": False,
        "detection": {},
        "processes_before_hold": [],
        "processes_after_hold": [],
        "error": "",
        "traceback": "",
    }
    driver = None
    raw_proc = None
    scheduled_task = ""
    try:
        _cleanup_label(label)
        if plan == "uc_direct":
            driver = _launch_uc(label, port, args)
            output["launch_ok"] = True
            output["attach_ok"] = True
        elif plan == "selenium_direct":
            driver = _launch_selenium(label, port, args)
            output["launch_ok"] = True
            output["attach_ok"] = True
        elif plan == "raw_attach_subprocess":
            raw_proc = _launch_raw_subprocess(label, port, args)
            output["launch_ok"] = True
            if _wait_devtools(port, args.launch_timeout_seconds):
                driver = _attach_selenium(port, args)
                output["attach_ok"] = True
        elif plan == "raw_attach_explorer":
            _launch_raw_explorer(label, port, args)
            output["launch_ok"] = True
            if _wait_devtools(port, args.launch_timeout_seconds):
                driver = _attach_selenium(port, args)
                output["attach_ok"] = True
        elif plan == "raw_attach_scheduled":
            scheduled_task = _launch_raw_scheduled(label, port, args, root)
            output["scheduled_task"] = scheduled_task
            output["launch_ok"] = True
            if _wait_devtools(port, args.launch_timeout_seconds):
                driver = _attach_selenium(port, args)
                output["attach_ok"] = True
        else:
            output["error"] = "unknown_plan"

        if driver is not None:
            output["detection"] = _open_page_and_detect(driver, args.url, max(float(args.hold_seconds), 0.0))
            output["page_ok"] = bool(output["detection"].get("current_url"))
            output["bbp_panel_detected"] = bool(output["detection"].get("bbp_panel_detected"))
            output["bbp_authenticated_fields_detected"] = bool(output["detection"].get("bbp_authenticated_fields_detected"))
            output["bbp_login_fields_detected"] = bool(output["detection"].get("bbp_login_fields_detected"))
        else:
            time.sleep(max(float(args.hold_seconds), 0.0))

        output["processes_after_hold"] = _process_rows_for_label(label)
        output["visible_window"] = any(int(row.get("main_window_handle") or 0) != 0 for row in output["processes_after_hold"])
        if not output["attach_ok"] and not output["error"]:
            output["error"] = "attach_failed"
    except Exception as exc:
        output["error"] = f"{type(exc).__name__}:{exc}"
        output["traceback"] = traceback.format_exc()
    finally:
        output["processes_before_cleanup"] = _process_rows_for_label(label)
        try:
            if driver is not None:
                driver.quit()
        except Exception:
            pass
        try:
            if raw_proc is not None and raw_proc.poll() is None:
                raw_proc.terminate()
        except Exception:
            pass
        _cleanup_label(label)
        if scheduled_task:
            subprocess.run(["schtasks", "/Delete", "/TN", scheduled_task, "/F"], capture_output=True, text=True)
        time.sleep(2)
        output["remaining_processes_after_cleanup"] = _process_rows_for_label(label)
        output["finished_utc"] = _utc_now_iso()
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run five visible BBP browser hold launch-plan tests.")
    parser.add_argument("--asin", default="B0046A3Z3O")
    parser.add_argument("--hold-seconds", type=float, default=20.0)
    parser.add_argument("--launch-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--chrome-exe", default=CHROME_EXE)
    parser.add_argument("--user-data-dir", default=USER_DATA_DIR)
    parser.add_argument("--profile-dir", default=PROFILE_DIR)
    parser.add_argument("--driver-exe", default=DRIVER_EXE)
    parser.add_argument(
        "--plans",
        nargs="*",
        default=["uc_direct", "selenium_direct", "raw_attach_subprocess", "raw_attach_explorer", "raw_attach_scheduled"],
    )
    args = parser.parse_args()
    args.url = f"https://www.amazon.co.uk/dp/{args.asin.strip() or 'B0046A3Z3O'}"

    root = _root()
    stamp = _utc_now_iso().replace("-", "").replace(":", "")
    out_dir = root / "out" / "systems" / "F" / "diagnostics"
    json_path = out_dir / f"f064_visible_hold_plan_matrix_{stamp}.json"
    csv_path = out_dir / f"f064_visible_hold_plan_matrix_{stamp}.csv"
    status_path = out_dir / "f064_visible_hold_plan_matrix_status.json"

    results: list[dict[str, Any]] = []
    for index, plan in enumerate(args.plans, start=1):
        _write_json(status_path, {"state": "running", "current_plan": plan, "updated_utc": _utc_now_iso(), "results": results})
        result = run_plan(plan, index, args, root)
        results.append(result)
        _write_json(status_path, {"state": "running", "current_plan": "", "updated_utc": _utc_now_iso(), "results": results})

    summary_rows: list[dict[str, Any]] = []
    for item in results:
        summary_rows.append(
            {
                "plan": item.get("plan", ""),
                "description": item.get("description", ""),
                "launch_ok": item.get("launch_ok", False),
                "attach_ok": item.get("attach_ok", False),
                "page_ok": item.get("page_ok", False),
                "visible_window": item.get("visible_window", False),
                "bbp_panel_detected": item.get("bbp_panel_detected", False),
                "bbp_authenticated_fields_detected": item.get("bbp_authenticated_fields_detected", False),
                "bbp_login_fields_detected": item.get("bbp_login_fields_detected", False),
                "error": item.get("error", ""),
            }
        )
    payload = {
        "state": "finished",
        "started_utc": results[0]["started_utc"] if results else _utc_now_iso(),
        "finished_utc": _utc_now_iso(),
        "json_output": str(json_path),
        "csv_output": str(csv_path),
        "results": results,
        "summary": summary_rows,
    }
    _write_json(json_path, payload)
    _write_csv(csv_path, summary_rows)
    _write_json(status_path, payload)
    print(json.dumps({"json_output": str(json_path), "csv_output": str(csv_path), "summary": summary_rows}, indent=2))


if __name__ == "__main__":
    main()
