from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OLD_BBP_CHROME_EXE = r"C:\Chrome_UC136\bin\chrome.exe"
OLD_BBP_USER_DATA_DIR = r"C:\Users\Luke\AppData\Local\Chrome_UC136"
OLD_BBP_PROFILE_DIR = "BBPProfile"
OLD_DRIVER_EXE = (
    r"C:\Users\Luke\.nuget\packages\selenium.webdriver.chromedriver"
    r"\136.0.7103.4800-beta\driver\win32\chromedriver.exe"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def _safe_text(value: object) -> str:
    return str(value or "").strip()


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
        "cdp_targets": [],
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
        switch_to = getattr(driver, "switch_to", None)
        default_content = getattr(switch_to, "default_content", None)
        if callable(default_content):
            default_content()
    except Exception:
        pass

    try:
        targets = driver.execute_cdp_cmd("Target.getTargets", {})
        target_infos = targets.get("targetInfos", []) if isinstance(targets, dict) else []
        compact = []
        for info in target_infos:
            if not isinstance(info, dict):
                continue
            compact.append(
                {
                    "type": _safe_text(info.get("type", "")),
                    "title": _safe_text(info.get("title", ""))[:120],
                    "url": _safe_text(info.get("url", ""))[:240],
                }
            )
        result["cdp_targets"] = compact
    except Exception as exc:
        result["cdp_error"] = f"{type(exc).__name__}:{exc}"

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


def run_probe(
    asin: str,
    hold_seconds: float,
    output_path: Path,
    *,
    chrome_exe: str = OLD_BBP_CHROME_EXE,
    user_data_dir: str = OLD_BBP_USER_DATA_DIR,
    profile_dir: str = OLD_BBP_PROFILE_DIR,
) -> dict[str, Any]:
    import undetected_chromedriver as uc

    payload: dict[str, Any] = {
        "started_utc": _utc_now_iso(),
        "mode": "old_bbp_driver_launch_probe",
        "asin": asin,
        "url": f"https://www.amazon.co.uk/dp/{asin}",
        "chrome_exe": chrome_exe,
        "user_data_dir": user_data_dir,
        "profile_dir": profile_dir,
        "driver_exe": OLD_DRIVER_EXE,
        "success": False,
        "failure_reason": "",
        "detection": {},
    }
    driver = None
    try:
        options = uc.ChromeOptions()
        options.binary_location = chrome_exe
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_dir}")
        options.add_argument("--log-level=3")
        driver = uc.Chrome(
            options=options,
            version_main=136,
            driver_executable_path=OLD_DRIVER_EXE,
        )
        driver.set_window_position(0, 0)
        driver.set_window_size(1280, 720)
        driver.get(payload["url"])
        time.sleep(3)
        try:
            driver.refresh()
            time.sleep(3)
        except Exception:
            pass
        payload["detection"] = _detect_bbp_state(driver)
        payload["success"] = bool(payload["detection"].get("bbp_panel_detected"))
        if not payload["success"]:
            payload["failure_reason"] = "bbp_panel_not_detected"
        if hold_seconds > 0:
            time.sleep(hold_seconds)
    except Exception as exc:
        payload["failure_reason"] = f"{type(exc).__name__}:{exc}"
        payload["traceback"] = traceback.format_exc()
    finally:
        try:
            if driver is not None:
                driver.quit()
        except Exception:
            pass
        payload["finished_utc"] = _utc_now_iso()
        _write_json(output_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="No-Sheets probe for the old BBP Chrome driver launch.")
    parser.add_argument("--asin", default="B08BMN2MYN")
    parser.add_argument("--hold-seconds", type=float, default=10.0)
    parser.add_argument("--chrome-exe", default=OLD_BBP_CHROME_EXE)
    parser.add_argument("--user-data-dir", default=OLD_BBP_USER_DATA_DIR)
    parser.add_argument("--profile-dir", default=OLD_BBP_PROFILE_DIR)
    parser.add_argument("--label", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    out_dir = _root() / "out" / "systems" / "F" / "diagnostics"
    stamp = _utc_now_iso().replace("-", "").replace(":", "")
    label = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in args.label.strip())
    stem = f"old_bbp_driver_probe_{label}_{stamp}" if label else f"old_bbp_driver_probe_{stamp}"
    output = Path(args.output) if args.output else out_dir / f"{stem}.json"
    result = run_probe(
        args.asin.strip() or "B08BMN2MYN",
        max(float(args.hold_seconds), 0.0),
        output,
        chrome_exe=args.chrome_exe,
        user_data_dir=args.user_data_dir,
        profile_dir=args.profile_dir,
    )
    print(json.dumps({"success": result.get("success"), "failure_reason": result.get("failure_reason"), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
