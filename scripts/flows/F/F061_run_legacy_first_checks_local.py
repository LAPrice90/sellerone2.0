from __future__ import annotations

import argparse
import atexit
import hashlib
import inspect
import json
import logging
import math
import os
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._scanner_state import (
    ROW_QUEUE_NEEDS_LOGIN_RESCAN,
    ROW_QUEUE_NEEDS_YESNO_RESCAN,
    ROW_QUEUE_PENDING,
    active_row_is_rescan_retry,
    active_row_queue_priority,
    active_row_queue_state,
    has_required_dashboard_signal,
)
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract
from scripts.flows.F.f_scanner_timeout_policy import (
    build_timeout_policy_health_rows,
    read_timeout_policy_df,
    timeout_until_utc_for_policy,
)
from scripts.api.get_financial_events import load_dotenv_if_missing


logger = logging.getLogger(__name__)

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SPAPI_BASE_URL = os.environ.get("SPAPI_BASE_URL", "https://sellingpartnerapi-eu.amazon.com")
MARKETPLACE_ID_UK = "A1F83G8C2ARO7P"
PRICE_SOURCE_LEGACY = "legacy"
PRICE_SOURCE_NATIVE_COMP_SUMMARY = "native_comp_summary"
PRICE_SOURCE_ALLOWED = {PRICE_SOURCE_LEGACY, PRICE_SOURCE_NATIVE_COMP_SUMMARY}
F061_PRICE_SOURCE_ENV = "F061_PRICE_SOURCE"
F061_PRICING_MIN_INTERVAL_SECONDS_ENV = "F061_PRICING_MIN_INTERVAL_SEC"
F061_PRICING_RETRIES_ENV = "F061_PRICING_RETRIES"
F061_CATALOG_MIN_INTERVAL_SECONDS_ENV = "F061_CATALOG_MIN_INTERVAL_SEC"
F061_CATALOG_MAX_CANDIDATES_ENV = "F061_CATALOG_MAX_CANDIDATES"
F061_HAZMAT_MIN_INTERVAL_SECONDS_ENV = "F061_HAZMAT_MIN_INTERVAL_SEC"
F061_FEES_MIN_INTERVAL_SECONDS_ENV = "F061_FEES_MIN_INTERVAL_SEC"
F061_SCRAPE_PAGE_LOAD_TIMEOUT_SECONDS_ENV = "F061_SCRAPE_PAGE_LOAD_TIMEOUT_SEC"
F061_COOLDOWN_STATE_PATH_ENV = "F061_COOLDOWN_STATE_PATH"
F061_KILL_SPECIALIST_CHROME_BEFORE_START_ENV = "F061_KILL_SPECIALIST_CHROME_BEFORE_START"
F061_PRE_REVIEW_KILL_GATE_ENV = "F061_PRE_REVIEW_KILL_GATE"
F061_ECONOMIC_PRE_REVIEW_HARD_STOP_ENV = "F061_ECONOMIC_PRE_REVIEW_HARD_STOP"
F061_MODE_ENV = "F061_MODE"
F061_TIMEOUTS_JSON_ENV = "F061_TIMEOUTS_JSON"
F061_BACKGROUND_BROWSER_MODE_ENV = "F061_BACKGROUND_BROWSER_MODE"
F061_LOGIN_MODE_ENV = "F061_LOGIN_MODE"
F061_LOGIN_HOLD_SECONDS_ENV = "F061_LOGIN_HOLD_SECONDS"
F061_LOGIN_MODE_REQUEST_PATH_ENV = "F061_LOGIN_MODE_REQUEST_PATH"
F061_ALLOWLIST_PATH_ENV = "F061_ALLOWLIST_PATH"
F061_STAGE_MODE_ENV = "F061_STAGE_MODE"
F061_STAGE_MODE_LEGACY_FULL = "legacy_full"
F061_STAGE_MODE_API_ONLY = "api_only"
F061_STAGE_MODE_BROWSER_ONLY = "browser_only"
F061_STAGE_MODE_ALLOWED = {F061_STAGE_MODE_LEGACY_FULL, F061_STAGE_MODE_API_ONLY, F061_STAGE_MODE_BROWSER_ONLY}
F061_MODE_SCREENING = "screening"
F061_MODE_DATA_COLLECTION = "data_collection"
F061_MODE_LOGIN_BACKTRACK = "login_backtrack"
F061_MODE_ALLOWED = {F061_MODE_SCREENING, F061_MODE_DATA_COLLECTION, F061_MODE_LOGIN_BACKTRACK}
F061_SCAN_STATUS_PENDING = "pending"
F061_SCAN_STATUS_LOGIN_BACKTRACK_PENDING = "login_backtrack_pending"
F061_SCAN_STATUS_LOGIN_BACKTRACK_RUNNING = "login_backtrack_running"
F061_SCAN_STATUS_COMPLETED = "completed"
F061_LOGIN_BACKTRACK_STATUS_CODE = "LOGIN_BACKTRACK"
F061_LOGIN_BACKTRACK_REASON = "LOGIN_BACKTRACK_PENDING"
F061_LOGIN_BACKTRACK_SCAN_REASON = "login_backtrack_required"
F061_DASHBOARD_YES_NO_UNRESOLVED_SCAN_REASON = "dashboard_yes_no_backtrack_unresolved"
F061_DASHBOARD_YES_NO_MAX_BACKTRACK_ATTEMPTS = 3
F061_RESCAN_MAX_ACTIVE_ATTEMPTS_ENV = "F061_RESCAN_MAX_ACTIVE_ATTEMPTS"
F061_RESCAN_RETRY_SCAN_REASON = "rescan_retry_required"
F061_RESCAN_RETRY_BLOCK_REASON = "rescan_retry_pending"
F061_BROWSER_STAGE_READY_REASON = "browser_stage_ready"
F061_STATUS_BROWSER_READY = "BROWSER_READY"
F061_BROWSER_ONLY_MISSING_API_EVIDENCE_REASON = "browser_only_missing_api_evidence"

ENDPOINT_CATALOG = "catalog"
ENDPOINT_HAZMAT = "hazmat"
ENDPOINT_PRICING = "pricing"
ENDPOINT_FEES = "fees"
ENDPOINT_KEYS = (ENDPOINT_CATALOG, ENDPOINT_HAZMAT, ENDPOINT_PRICING, ENDPOINT_FEES)

FAIL_STATUS_CODES = {
    "NOASIN",
    "OVER50K",
    "HAZMATFAIL",
    "NOCOST",
    "ROIFAIL",
    "LOWROI",
    "BRANDFAIL",
    "NODATE",
    "REVIEWFAIL",
    "SCRAPEFAIL",
    "LOWSALESFAIL",
    "SELLERHISTORYFAIL",
    "PRICEHISTORYFAIL",
    "FAIL",
}

RETRY_STATUS_CODES = {"RESCAN"}

DEFAULT_TIMEOUT_MINUTES_BY_CODE: dict[str, int] = {
    "NOASIN": 240,
    "OVER50K": 720,
    "HAZMATFAIL": 1440,
    "NOCOST": 240,
    "ROIFAIL": 720,
    "LOWROI": 240,
    "BRANDFAIL": 1440,
    "NODATE": 240,
    "REVIEWFAIL": 180,
    "SCRAPEFAIL": 120,
    "LOWSALESFAIL": 720,
    "SELLERHISTORYFAIL": 1440,
    "PRICEHISTORYFAIL": 1440,
    "RESCAN": 60,
    "FAIL": 240,
}

SCRAPE_EVIDENCE_SCRAPED_KEYS = [
    "scan_date",
    "main_title",
    "monthly_sold",
    "rating",
    "product_info",
    "product_detail_text",
    "product_description",
    "product_feature_bullets",
    "variant_reviews",
    "reviews_text",
    "historical_uk_reviews",
    "parent_total_reviews",
    "estimated_variant_ratings",
    "variant_mode",
    "total_reviews_before_filter",
    "variant_filter_reviews",
    "matching_variant_reviews",
    "global_ratings",
    "amazon_bought_floor",
    "bbp_monthly_sales_current",
    "bbp_monthly_sales_recent_avg",
    "bbp_monthly_sales_history",
    "bbp_monthly_units_chosen",
    "bbp_dashboard_yes_or_no",
    "bbp_dashboard_delivery_classification",
    "bbp_dashboard_separate_delivery_required",
    "bbp_top_seller_names",
    "bbp_top_seller_count",
    "bbp_brand_match_seller",
    "bbp_brand_match_score",
    "bbp_brand_match_flag",
    "bbp_seller_rank_1_name",
    "bbp_seller_rank_1_price",
    "bbp_seller_rank_1_fulfilment",
    "bbp_seller_rank_1_delivery",
    "bbp_seller_rank_1_reviews",
    "bbp_seller_rank_1_feedback_pct",
    "bbp_seller_rank_1_brand_match_flag",
    "bbp_seller_rank_1_row_text",
    "bbp_seller_rank_1_row_html",
    "bbp_seller_rank_2_name",
    "bbp_seller_rank_2_price",
    "bbp_seller_rank_2_fulfilment",
    "bbp_seller_rank_2_delivery",
    "bbp_seller_rank_2_reviews",
    "bbp_seller_rank_2_feedback_pct",
    "bbp_seller_rank_2_brand_match_flag",
    "bbp_seller_rank_2_row_text",
    "bbp_seller_rank_2_row_html",
    "bbp_seller_rank_3_name",
    "bbp_seller_rank_3_price",
    "bbp_seller_rank_3_fulfilment",
    "bbp_seller_rank_3_delivery",
    "bbp_seller_rank_3_reviews",
    "bbp_seller_rank_3_feedback_pct",
    "bbp_seller_rank_3_brand_match_flag",
    "bbp_seller_rank_3_row_text",
    "bbp_seller_rank_3_row_html",
    "amazon_buybox_seller_name",
    "amazon_buybox_brand_match_score",
    "amazon_buybox_brand_match_flag",
    "bbp_sales_chart_source",
    "bbp_sales_chart_month_labels",
    "bbp_sales_chart_month_units",
    "bbp_sales_chart_series",
    "bbp_sales_last_completed_month_label",
    "bbp_sales_last_completed_month_units",
    "bbp_sales_current_month_label",
    "bbp_sales_current_month_units",
    "bbp_sales_future_month_count_ignored",
    "bbp_sales_replay_demand_basis_source",
    "bbp_sales_replay_demand_basis_label",
    "bbp_sales_replay_demand_basis_units",
    "bbp_section_snapshot_path",
    "bbp_section_snapshot_nodes",
    "bbp_section_snapshot_error",
    "demand_confidence_score",
    "demand_confidence_note",
    "avg_30_day_price",
    "profit_per_unit_30d",
    "estimated_monthly_turnover",
    "estimated_monthly_profit",
    "turnover_profit_history",
    "turnover_history_months",
    "turnover_current_month_profit",
    "turnover_short_avg_profit",
    "turnover_medium_avg_profit",
    "turnover_long_avg_profit",
    "turnover_history_score",
    "turnover_history_recommendation",
    "turnover_fail_code",
    "turnover_fail_reason",
    "economics_score",
    "history_score",
    "opportunity_score",
    "opportunity_recommendation",
    "history_pattern_note",
    "history_window_days",
    "history_data_points",
    "history_gap_fill_rate",
    "pricing_history_score",
    "ranking_history_score",
    "history_operational_score",
    "phase_profit_pct",
    "phase_low_roi_pct",
    "phase_break_even_pct",
    "phase_loss_pct",
    "phase_longest_profit_days",
    "phase_longest_low_roi_days",
    "phase_longest_break_even_days",
    "phase_longest_loss_days",
    "phase_current",
    "phase_recommendation",
    "exit_strategy",
    "bsr_recent_avg",
    "bsr_prev_avg",
    "bsr_trend",
    "chosen_price_recent_avg",
    "chosen_price_prev_avg",
    "price_trend_pct",
    "history_source",
    "history_recommendation",
    "history_blended_score",
    "price_history_span_days",
    "price_history_points_365d",
    "price_hist_table_raw",
    "chart_price_daily_series",
    "chart_bsr_daily_series",
    "chart_phase_daily_series",
    "chart_raw_amazon_daily_series",
    "chart_raw_fba_daily_series",
    "chart_raw_fbm_daily_series",
    "chart_raw_buy_box_daily_series",
    "chart_raw_bsr_daily_series",
    "price_hist_windows",
    "price_hist_amazon_30",
    "price_hist_amazon_90",
    "price_hist_amazon_180",
    "price_hist_amazon_365",
    "price_hist_fba_30",
    "price_hist_fba_90",
    "price_hist_fba_180",
    "price_hist_fba_365",
    "price_hist_buy_box_30",
    "price_hist_buy_box_90",
    "price_hist_buy_box_180",
    "price_hist_buy_box_365",
    "price_hist_fbm_30",
    "price_hist_fbm_90",
    "price_hist_fbm_180",
    "price_hist_fbm_365",
    "price_hist_new_30",
    "price_hist_new_90",
    "price_hist_new_180",
    "price_hist_new_365",
    "pricing_mode",
    "unavailable_detected",
    "price_history_365d_exists",
    "fallback_lane_used",
    "fallback_window_used",
    "fallback_price",
    "fallback_roi",
    "fallback_confidence",
    "fbm_undercut_flag",
    "pricing_decision_note",
    "bbp_auto_sell_price",
    "bbp_final_sell_price",
    "roi_check_source",
    "roi_check_value",
    "webscrape_mode",
    "checks_failed",
    "fail_codes",
    "hard_stop",
]

F061_BBP_USER_DATA_DIR = str(
    os.environ.get("F061_BBP_USER_DATA_DIR", r"C:\Users\Luke\AppData\Local\Chrome_UC136") or ""
).strip()
F061_BBP_PROFILE_DIR = str(os.environ.get("F061_BBP_PROFILE_DIR", "Profile 2") or "Profile 2").strip()
F061_DATE_USER_DATA_DIR = str(
    os.environ.get("F061_DATE_USER_DATA_DIR", r"C:\Users\Luke\AppData\Local\Chrome_91_F061") or ""
).strip()

SPECIALIST_CHROME_MATCH_TOKENS: tuple[str, ...] = (
    r"C:\Chrome_UC136\bin\chrome.exe",
    r"C:\Users\Luke\AppData\Local\Chrome_UC136",
    r"C:\Users\Luke\AppData\Local\Chrome_UC136v2",
    r"C:\Users\Luke\AppData\Local\Chrome_UC136_F061",
    r"C:\Users\Luke\AppData\Local\Chrome_91",
    r"C:\Users\Luke\AppData\Local\Chrome_91_F061",
    r"C:\Users\Luke\PortableApps\GoogleChromePortable\App\Chrome-bin\chrome.exe",
    r"C:\Users\Luke\PortableApps\GoogleChromePortable\App\Chrome-bin\chromedriver.exe",
    r"\selenium.webdriver.chromedriver\136.0.7103.4800-beta\driver\win32\chromedriver.exe",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _normalize_digits(value: object) -> str:
    return "".join(ch for ch in _normalize_text(value) if ch.isdigit())


def _normalize_words(value: object) -> list[str]:
    text = _normalize_lower(value)
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text)
    return [part for part in cleaned.split() if part]


def _file_version(path: str) -> str:
    if os.name != "nt":
        return ""
    literal = _normalize_text(path).replace("'", "''")
    if not literal:
        return ""
    try:
        proc = subprocess.run(
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
    return _normalize_text(proc.stdout)


def _cleanup_specialist_chrome_windows(*, force: bool = False) -> dict[str, Any]:
    if os.name != "nt":
        return {"cleanup_attempted": False, "cleanup_reason": "non_windows"}
    if not force and _normalize_lower(os.environ.get(F061_KILL_SPECIALIST_CHROME_BEFORE_START_ENV, "0")) in {
        "0",
        "false",
        "no",
    }:
        return {"cleanup_attempted": False, "cleanup_reason": "disabled_by_env"}

    tokens_json = json.dumps(list(SPECIALIST_CHROME_MATCH_TOKENS))
    tokens_json_escaped = tokens_json.replace("'", "''")
    ps_script = (
        "$ErrorActionPreference = 'SilentlyContinue';"
        f"$tokens = ConvertFrom-Json '{tokens_json_escaped}';"
        "$targets = @();"
        "Get-CimInstance Win32_Process | ForEach-Object {"
        "  if (($_.Name -eq 'chrome.exe' -or $_.Name -eq 'chromedriver.exe') -and $_.CommandLine) {"
        "    $cmd = $_.CommandLine;"
        "    $hit = $false;"
        "    foreach ($t in $tokens) {"
        "      if ($t -and $cmd -like ('*' + $t + '*')) { $hit = $true; break }"
        "    }"
        "    if ($hit) { $targets += $_ }"
        "  }"
        "};"
        "$killed = @();"
        "foreach ($p in $targets) {"
        "  try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; $killed += [int]$p.ProcessId } catch {}"
        "};"
        "$result = [pscustomobject]@{cleanup_attempted=$true; killed_count=$killed.Count; killed_ids=$killed};"
        "$result | ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return {"cleanup_attempted": True, "cleanup_error": f"powershell_invoke_error:{type(exc).__name__}:{_normalize_text(exc)}"}

    payload = _normalize_text(proc.stdout)
    if payload == "":
        if proc.returncode == 0:
            return {"cleanup_attempted": True, "killed_count": 0, "killed_ids": []}
        return {
            "cleanup_attempted": True,
            "cleanup_error": f"powershell_exit_{proc.returncode}",
            "stderr": _normalize_text(proc.stderr),
        }
    try:
        parsed = json.loads(payload)
    except Exception:
        parsed = {
            "cleanup_attempted": True,
            "killed_count": 0,
            "killed_ids": [],
            "raw_stdout": payload,
            "stderr": _normalize_text(proc.stderr),
        }
    return parsed if isinstance(parsed, dict) else {"cleanup_attempted": True, "killed_count": 0, "killed_ids": []}


def _clear_chrome_singleton_locks(profile_dir: str) -> dict[str, Any]:
    profile_text = _normalize_text(profile_dir)
    if profile_text == "":
        return {"profile_dir": "", "removed": [], "errors": []}
    base = Path(profile_text)
    removed: list[str] = []
    errors: list[str] = []
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"):
        target = base / name
        try:
            if target.exists():
                target.unlink()
                removed.append(str(target))
        except Exception as exc:
            errors.append(f"{name}:{type(exc).__name__}:{_normalize_text(exc)}")
    return {"profile_dir": str(base), "removed": removed, "errors": errors}


def _bbp_profile_extension_required() -> bool:
    return _normalize_lower(os.environ.get("F061_REQUIRE_BBP_EXTENSION", "0")) not in {"0", "false", "no"}


def _bbp_profile_extension_health(
    user_data_dir: str | None = None,
    profile_dir: str | None = None,
) -> dict[str, Any]:
    user_data = Path(_normalize_text(user_data_dir) or F061_BBP_USER_DATA_DIR)
    profile = _normalize_text(profile_dir) or F061_BBP_PROFILE_DIR
    extensions_dir = user_data / profile / "Extensions"
    if not extensions_dir.exists():
        return {
            "ok": False,
            "reason": "extensions_dir_missing",
            "user_data_dir": str(user_data),
            "profile_dir": profile,
            "extensions_dir": str(extensions_dir),
        }

    manifest_count = 0
    for manifest_path in extensions_dir.glob("*/*/manifest.json"):
        manifest_count += 1
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        text = " ".join(
            _normalize_text(payload.get(key, ""))
            for key in ("name", "short_name", "description")
        ).lower()
        if "buybotpro" in text or "buy bot pro" in text:
            return {
                "ok": True,
                "reason": "buybotpro_extension_found",
                "user_data_dir": str(user_data),
                "profile_dir": profile,
                "extension_id": manifest_path.parents[1].name,
                "extension_version": manifest_path.parent.name,
                "manifest_count": manifest_count,
            }

    return {
        "ok": False,
        "reason": "buybotpro_extension_missing",
        "user_data_dir": str(user_data),
        "profile_dir": profile,
        "extensions_dir": str(extensions_dir),
        "manifest_count": manifest_count,
    }


def _background_browser_mode() -> str:
    mode = _normalize_lower(os.environ.get(F061_BACKGROUND_BROWSER_MODE_ENV, "minimized"))
    if mode in {"visible", "minimized"}:
        return mode
    return "minimized"


def _apply_background_browser_options(options: Any) -> None:
    mode = _background_browser_mode()
    try:
        if mode == "minimized":
            options.add_argument("--start-minimized")
            options.add_argument("--window-position=-32000,-32000")
            return
        if mode == "visible":
            options.add_argument("--window-size=1400,900")
            options.add_argument("--window-position=80,80")
    except Exception:
        pass


def _command_text(command: object) -> str:
    if isinstance(command, (list, tuple)):
        return " ".join(str(part) for part in command)
    return str(command or "")


def _is_specialist_chrome_command(command: object) -> bool:
    if os.name != "nt":
        return False
    text = _command_text(command).lower()
    return (
        "chrome_uc136" in text
        or "chrome_91_f061" in text
        or "googlechromeportable" in text
    )


def _should_force_visible_bbp_chrome_startup(command: object) -> bool:
    return os.name == "nt" and _background_browser_mode() == "visible" and _is_specialist_chrome_command(command)


def _minimized_chrome_command(command: object) -> object:
    if os.name != "nt" or _background_browser_mode() != "minimized" or not _is_specialist_chrome_command(command):
        return command

    def keep_arg(part: object) -> bool:
        text = str(part).strip().lower()
        return not (
            text == "--start-maximized"
            or text == "--start-minimized"
            or text.startswith("--window-position=")
        )

    hidden_args = ["--start-minimized", "--window-position=-32000,-32000"]
    if isinstance(command, tuple):
        return tuple([part for part in command if keep_arg(part)] + hidden_args)
    if isinstance(command, list):
        return [part for part in command if keep_arg(part)] + hidden_args
    return command


def _visible_chrome_command(command: object) -> object:
    if os.name != "nt" or _background_browser_mode() != "visible" or not _is_specialist_chrome_command(command):
        return command

    def keep_arg(part: object) -> bool:
        text = str(part).strip().lower()
        return not (
            text == "--start-maximized"
            or text == "--start-minimized"
            or text.startswith("--window-position=")
            or text.startswith("--window-size=")
        )

    visible_args = ["--window-position=80,80", "--window-size=1400,900"]
    if isinstance(command, tuple):
        return tuple([part for part in command if keep_arg(part)] + visible_args)
    if isinstance(command, list):
        return [part for part in command if keep_arg(part)] + visible_args
    return command


def _visible_bbp_chrome_startup_kwargs(command: object, kwargs: dict[str, Any]) -> dict[str, Any]:
    if not _should_force_visible_bbp_chrome_startup(command):
        return kwargs
    updated = dict(kwargs)
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
    create_no_window = int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
    if startupinfo_factory is not None:
        startupinfo = updated.get("startupinfo") or startupinfo_factory()
        try:
            startupinfo.dwFlags |= use_show_window
            startupinfo.wShowWindow = 1
            updated["startupinfo"] = startupinfo
        except Exception:
            pass
    try:
        if create_no_window:
            updated["creationflags"] = int(updated.get("creationflags", 0) or 0) & ~create_no_window
    except Exception:
        pass
    return updated


def _minimized_chrome_startup_kwargs(command: object, kwargs: dict[str, Any]) -> dict[str, Any]:
    if os.name != "nt" or _background_browser_mode() != "minimized" or not _is_specialist_chrome_command(command):
        return kwargs
    updated = dict(kwargs)
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
    show_minimized = 6
    if startupinfo_factory is not None:
        startupinfo = updated.get("startupinfo") or startupinfo_factory()
        try:
            startupinfo.dwFlags |= use_show_window
            startupinfo.wShowWindow = show_minimized
            updated["startupinfo"] = startupinfo
        except Exception:
            pass
    return updated


@contextmanager
def _force_visible_bbp_chrome_startup():
    if os.name != "nt":
        yield
        return
    original_popen = subprocess.Popen

    def visible_popen(*args: Any, **kwargs: Any):
        command = args[0] if args else kwargs.get("args", "")
        if _background_browser_mode() == "minimized":
            command = _minimized_chrome_command(command)
            if args:
                args = (command, *args[1:])
            else:
                kwargs = dict(kwargs)
                kwargs["args"] = command
            kwargs = _minimized_chrome_startup_kwargs(command, kwargs)
            return original_popen(*args, **kwargs)
        command = _visible_chrome_command(command)
        if args:
            args = (command, *args[1:])
        else:
            kwargs = dict(kwargs)
            kwargs["args"] = command
        return original_popen(*args, **_visible_bbp_chrome_startup_kwargs(command, kwargs))

    subprocess.Popen = visible_popen  # type: ignore[assignment]
    try:
        yield
    finally:
        subprocess.Popen = original_popen  # type: ignore[assignment]


def _force_clean_specialist_chrome_for_visible_login() -> bool:
    return _truthy_env("F061_FORCE_CLEAN_SPECIALIST_CHROME_FOR_LOGIN")


def _bring_browser_window_to_front(driver: Any) -> None:
    target_id = ""
    try:
        targets = driver.execute_cdp_cmd("Target.getTargets", {})
        target_infos = targets.get("targetInfos", []) if isinstance(targets, dict) else []
        if isinstance(target_infos, list):
            pages = [info for info in target_infos if isinstance(info, dict) and info.get("type") == "page"]
            current_url = _normalize_text(getattr(driver, "current_url", ""))
            selected = pages[0] if pages else {}
            if current_url:
                selected = next((info for info in pages if _normalize_text(info.get("url", "")) == current_url), selected)
            target_id = _normalize_text(selected.get("targetId", "")) if isinstance(selected, dict) else ""
        if target_id:
            driver.execute_cdp_cmd("Target.activateTarget", {"targetId": target_id})
    except Exception:
        pass
    try:
        driver.execute_cdp_cmd("Page.bringToFront", {})
    except Exception:
        pass


def _place_hidden_browser_window(driver: Any) -> None:
    try:
        window = driver.execute_cdp_cmd("Browser.getWindowForTarget", {})
        window_id = window.get("windowId") if isinstance(window, dict) else None
        if window_id is not None:
            driver.execute_cdp_cmd(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {
                        "windowState": "normal",
                        "left": -32000,
                        "top": -32000,
                        "width": 1280,
                        "height": 720,
                    },
                },
            )
            driver.execute_cdp_cmd(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {"windowState": "minimized"},
                },
            )
    except Exception:
        pass
    try:
        driver.set_window_rect(x=-32000, y=-32000, width=1280, height=720)
    except Exception:
        try:
            driver.set_window_position(-32000, -32000)
            driver.set_window_size(1280, 720)
        except Exception:
            pass
    try:
        driver.minimize_window()
    except Exception:
        pass


def _place_browser_window(driver: Any, *, visible_x: int, visible_y: int) -> None:
    if _background_browser_mode() == "minimized":
        _place_hidden_browser_window(driver)
        return
    try:
        window = driver.execute_cdp_cmd("Browser.getWindowForTarget", {})
        window_id = window.get("windowId") if isinstance(window, dict) else None
        if window_id is not None:
            driver.execute_cdp_cmd(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {
                        "windowState": "normal",
                        "left": int(visible_x),
                        "top": int(visible_y),
                        "width": 1400,
                        "height": 900,
                    },
                },
            )
    except Exception:
        pass
    try:
        driver.set_window_rect(x=visible_x, y=visible_y, width=1400, height=900)
        _bring_browser_window_to_front(driver)
        return
    except Exception:
        pass
    try:
        driver.set_window_position(visible_x, visible_y)
        driver.set_window_size(1400, 900)
        _bring_browser_window_to_front(driver)
    except Exception:
        pass


def _place_date_browser_window(driver: Any) -> None:
    if _truthy_env(F061_LOGIN_MODE_ENV) and _background_browser_mode() == "visible":
        _place_hidden_browser_window(driver)
        return
    _place_browser_window(driver, visible_x=1280, visible_y=0)


def _parse_float(value: object, default: float = 0.0) -> float:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return default
    try:
        num = float(raw)
    except ValueError:
        return default
    if math.isnan(num) or math.isinf(num):
        return default
    return num


def _parse_optional_float(value: object) -> float | None:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return None
    try:
        num = float(raw)
    except ValueError:
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def _parse_nonnegative_int(value: object, default: int = 0) -> int:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return default
    try:
        num = int(float(raw))
    except ValueError:
        return default
    return max(num, 0)


def _max_active_rescan_attempts() -> int:
    return max(_parse_nonnegative_int(os.environ.get(F061_RESCAN_MAX_ACTIVE_ATTEMPTS_ENV, "2"), default=2), 1)


def _stage_mode_from_value(value: object) -> str:
    mode = _normalize_lower(value)
    if mode in F061_STAGE_MODE_ALLOWED:
        return mode
    return F061_STAGE_MODE_LEGACY_FULL


def _row_is_browser_stage_ready(row: dict[str, object] | pd.Series) -> bool:
    return (
        _normalize_lower(row.get("scan_status", "")) == F061_SCAN_STATUS_PENDING
        and _normalize_lower(row.get("scan_reason", "")) == F061_BROWSER_STAGE_READY_REASON
    )


def _rescan_retry_allowed(active_row: dict[str, object] | pd.Series) -> bool:
    next_attempt_count = _parse_nonnegative_int(active_row.get("attempt_count", "0"), default=0) + 1
    return next_attempt_count < _max_active_rescan_attempts()


def _parse_positive_float(value: object, default: float) -> float:
    raw = _normalize_text(value).replace(",", "")
    if raw == "":
        return default
    try:
        num = float(raw)
    except ValueError:
        return default
    if math.isnan(num) or math.isinf(num) or num <= 0:
        return default
    return num


def _missing_core_price_history_reason(scraped_data: dict[str, Any] | None) -> str:
    if not isinstance(scraped_data, dict):
        return "INCOMPLETE_PRICE_HISTORY_CAPTURE"

    price_points_365d = _parse_nonnegative_int(scraped_data.get("price_history_points_365d", "0"), default=0)
    if price_points_365d > 0:
        return ""

    price_history_fields = (
        "chart_price_daily_series",
        "chart_raw_amazon_daily_series",
        "chart_raw_fba_daily_series",
        "chart_raw_fbm_daily_series",
        "chart_raw_buy_box_daily_series",
    )
    for field_name in price_history_fields:
        if _normalize_text(scraped_data.get(field_name, "")) != "":
            return ""

    return "INCOMPLETE_PRICE_HISTORY_CAPTURE"


def _parse_observed_utc(value: object) -> datetime:
    raw = _normalize_text(value)
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _timeout_minutes_by_code() -> dict[str, int]:
    configured = dict(DEFAULT_TIMEOUT_MINUTES_BY_CODE)
    raw = _normalize_text(os.environ.get(F061_TIMEOUTS_JSON_ENV, ""))
    if raw == "":
        return configured
    try:
        payload = json.loads(raw)
    except Exception:
        return configured
    if not isinstance(payload, dict):
        return configured
    for key, value in payload.items():
        code = _normalize_text(key).upper()
        if code == "":
            continue
        minutes = _parse_nonnegative_int(value, default=configured.get(code, 0))
        configured[code] = minutes
    return configured


def _timeout_until_utc_for_status(
    *,
    observed_utc: str,
    pf_value: str,
    fail_code: str,
    timeout_policy_df: pd.DataFrame | None = None,
    root_path: Path | None = None,
) -> str:
    pf_upper = _normalize_text(pf_value).upper()
    if pf_upper == "PASS":
        return ""
    policy_df = timeout_policy_df
    if policy_df is None:
        policy_df = read_timeout_policy_df(root=root_path, create_if_missing=True, observed_utc=observed_utc)
    return timeout_until_utc_for_policy(
        observed_utc=observed_utc,
        fail_code=fail_code,
        policy_df=policy_df,
    )


def _pre_review_gate_health_row(*, observed_utc: str, source_path: Path) -> dict[str, str]:
    raw_value = _normalize_lower(os.environ.get(F061_PRE_REVIEW_KILL_GATE_ENV, "1"))
    enabled = raw_value not in {"0", "false", "no", "off"}
    return {
        "check": "feeder_pre_review_kill_gate_runtime",
        "status": "ok" if enabled else "warn",
        "value": "enabled" if enabled else "disabled",
        "notes": "pre_review_gate_enabled" if enabled else "pre_review_gate_disabled",
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def _economic_pre_review_hard_stop_health_row(*, observed_utc: str, source_path: Path) -> dict[str, str]:
    raw_value = _normalize_lower(os.environ.get(F061_ECONOMIC_PRE_REVIEW_HARD_STOP_ENV, "1"))
    enabled = raw_value not in {"0", "false", "no", "off"}
    return {
        "check": "feeder_economic_pre_review_hard_stop_runtime",
        "status": "ok" if enabled else "warn",
        "value": "enabled" if enabled else "disabled",
        "notes": "economic_pre_review_hard_stop_enabled" if enabled else "economic_pre_review_hard_stop_disabled",
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


class _EndpointCooldownStore:
    def __init__(self, *, state_path: Path, default_intervals_seconds: dict[str, float]) -> None:
        self._state_path = state_path
        self._default_intervals = {
            key: max(_parse_positive_float(value, 0.1), 0.1) for key, value in default_intervals_seconds.items()
        }
        self._state: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._state_path.exists():
            self._state = {}
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            self._state = {}
            return
        if not isinstance(payload, dict):
            self._state = {}
            return
        endpoint_state = payload.get("endpoints")
        self._state = endpoint_state if isinstance(endpoint_state, dict) else {}

    def _write(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "endpoints": self._state}
        for attempt in range(5):
            temp_path = self._state_path.with_suffix(f"{self._state_path.suffix}.tmp.{uuid.uuid4().hex}")
            try:
                temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
                temp_path.replace(self._state_path)
                return
            except PermissionError:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                if attempt >= 4:
                    raise
                time.sleep(0.1 * (attempt + 1))
            except Exception:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                raise

    def _endpoint(self, endpoint: str) -> dict[str, Any]:
        self._load()
        base = self._state.get(endpoint)
        if not isinstance(base, dict):
            base = {}
        cooldown_seconds = _parse_positive_float(
            base.get("cooldown_seconds", self._default_intervals.get(endpoint, 0.1)),
            self._default_intervals.get(endpoint, 0.1),
        )
        item = {
            "cooldown_seconds": cooldown_seconds,
            "last_attempt_epoch": _parse_float(base.get("last_attempt_epoch", 0.0), 0.0),
            "throttle_until_epoch": _parse_float(base.get("throttle_until_epoch", 0.0), 0.0),
            "last_status_code": _normalize_text(base.get("last_status_code", "")),
            "last_error": _normalize_text(base.get("last_error", "")),
            "last_rate_limit_limit": _normalize_text(base.get("last_rate_limit_limit", "")),
            "updated_at_utc": _normalize_text(base.get("updated_at_utc", "")),
        }
        self._state[endpoint] = item
        return item

    def wait_for_slot(self, endpoint: str) -> float:
        item = self._endpoint(endpoint)
        now_epoch = time.time()
        due_epoch = max(
            _parse_float(item.get("last_attempt_epoch", 0.0), 0.0) + _parse_float(item.get("cooldown_seconds", 0.1), 0.1),
            _parse_float(item.get("throttle_until_epoch", 0.0), 0.0),
        )
        wait_seconds = max(due_epoch - now_epoch, 0.0)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        return wait_seconds

    def mark_call(
        self,
        endpoint: str,
        *,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
        error: str = "",
    ) -> None:
        item = self._endpoint(endpoint)
        now_epoch = time.time()
        item["last_attempt_epoch"] = now_epoch
        item["last_status_code"] = str(status_code) if status_code is not None else ""
        item["last_error"] = _normalize_text(error)
        item["updated_at_utc"] = _utc_now_iso()

        normalized_headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        rate_limit_limit = _normalize_text(normalized_headers.get("x-amzn-ratelimit-limit", ""))
        if rate_limit_limit:
            item["last_rate_limit_limit"] = rate_limit_limit
            rps = _parse_optional_float(rate_limit_limit)
            if rps is not None and rps > 0:
                item["cooldown_seconds"] = max(round(1.0 / rps, 4), 0.1)

        if status_code == 429:
            retry_after = _parse_optional_float(normalized_headers.get("retry-after", ""))
            base_cooldown = _parse_float(item.get("cooldown_seconds", 0.1), 0.1)
            throttle_seconds = max(retry_after if retry_after is not None else 0.0, base_cooldown, 1.0)
            item["throttle_until_epoch"] = now_epoch + throttle_seconds
        elif status_code is not None and 200 <= status_code < 300:
            item["throttle_until_epoch"] = 0.0

        self._write()


def _parse_status_code(value: object) -> int | None:
    status = value
    if isinstance(status, dict):
        status = status.get("statusCode") or status.get("code")
    if status is None:
        return None
    try:
        return int(float(str(status).strip()))
    except Exception:
        return None


def _format_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _parse_release_date_years(date_text: str, today_utc: datetime) -> float:
    parsed = pd.to_datetime(_normalize_text(date_text), dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return 0.0
    years = (today_utc.date() - parsed.date()).days / 365.0
    return max(years, 0.0)


def _parse_positive_cost(value: object) -> float | None:
    num = _parse_optional_float(value)
    if num is None or num <= 0:
        return None
    return round(num, 2)


def _build_row_hash_fallback(parts: list[str]) -> str:
    key = "|".join(parts)
    return str(abs(hash(key)))


def _contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=_contract_columns(contract_name))


def _finalize_contract_df(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    ordered = _contract_columns(contract_name)
    out = df.copy()
    for column in ordered:
        if column not in out.columns:
            out[column] = ""
    out = out[ordered]
    for column in ordered:
        out[column] = out[column].map(_normalize_text)
    return out


def _type_mismatch_columns(df: pd.DataFrame, contract_name: str) -> list[str]:
    expected_types = get_f_output_column_types(contract_name)
    mismatches: list[str] = []
    for column, expected in expected_types.items():
        if expected == "string" and column in df.columns and not pd.api.types.is_object_dtype(df[column]):
            mismatches.append(column)
    return mismatches


def _write_contract_df(df: pd.DataFrame, contract_name: str, root_path: Path) -> pd.DataFrame:
    finalized = _finalize_contract_df(df, contract_name)
    mismatches = _type_mismatch_columns(finalized, contract_name)
    if mismatches:
        mismatch_text = ",".join(sorted(mismatches))
        raise ValueError(f"{contract_name} type mismatch for string columns: {mismatch_text}")
    out_path = root_path / get_f_output_contract(contract_name).rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_f_contract_df(root_path, contract_name, finalized)
    return finalized


def _call_adapter_process_scrape(adapter: Any, **kwargs: Any) -> dict[str, Any]:
    process_scrape = getattr(adapter, "process_scrape")
    try:
        signature = inspect.signature(process_scrape)
    except (TypeError, ValueError):
        result = process_scrape(**kwargs)
    else:
        accepts_var_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
        )
        if accepts_var_kwargs:
            result = process_scrape(**kwargs)
        else:
            accepted = {key: value for key, value in kwargs.items() if key in signature.parameters}
            result = process_scrape(**accepted)
    return result if isinstance(result, dict) else {"success": False, "error": "SCRAPE_INVALID_RESULT"}


def _read_contract_df(contract_name: str, root_path: Path) -> pd.DataFrame:
    return read_f_contract_df(root_path, contract_name)


def _write_raw_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns]
    for column in columns:
        out[column] = out[column].map(_normalize_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def _truthy_env(name: str) -> bool:
    return _normalize_lower(os.environ.get(name, "")) in {"1", "true", "yes", "on"}


def _parse_key_value_control_text(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in text.replace("\r", "\n").replace("|", "\n").splitlines():
        clean = _normalize_text(part)
        if not clean or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        parsed[_normalize_lower(key)] = _normalize_text(value)
    return parsed


def _write_key_value_control_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={_normalize_text(value)}" for key, value in values.items()]
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    os.replace(tmp, path)


def _login_mode_request_path_from_env() -> Path | None:
    raw = _normalize_text(os.environ.get(F061_LOGIN_MODE_REQUEST_PATH_ENV, ""))
    if not raw:
        return None
    return Path(raw)


def _update_login_mode_request_status(*, status: str, observed_utc: str, notes: str = "") -> None:
    path = _login_mode_request_path_from_env()
    if path is None:
        return
    try:
        existing = _parse_key_value_control_text(path.read_text(encoding="utf-8", errors="replace")) if path.exists() else {}
        existing["status"] = _normalize_text(status)
        existing["last_observed_utc"] = observed_utc
        if notes:
            existing["last_status_note"] = _normalize_text(notes)
        _write_key_value_control_file(path, existing)
    except Exception:
        return


PRICE_LIST_LIVE_EVENT_COLUMNS = [
    "event_utc",
    "cycle_run_id",
    "event_type",
    "supplier_id",
    "f061_run_id",
    "status",
    "rows",
    "notes",
]


def _append_price_list_live_event(
    *,
    root_path: Path,
    event_utc: str,
    event_type: str,
    supplier_id: str,
    f061_run_id: str,
    status: str,
    rows: int,
    notes: str = "",
) -> None:
    path = root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "live_cycle_events.csv"
    try:
        if path.exists():
            existing = pd.read_csv(path, dtype=str).fillna("")
        else:
            existing = pd.DataFrame(columns=PRICE_LIST_LIVE_EVENT_COLUMNS)
        for column in PRICE_LIST_LIVE_EVENT_COLUMNS:
            if column not in existing.columns:
                existing[column] = ""
        row = pd.DataFrame(
            [
                {
                    "event_utc": event_utc,
                    "cycle_run_id": "f061_login_mode",
                    "event_type": event_type,
                    "supplier_id": supplier_id,
                    "f061_run_id": f061_run_id,
                    "status": status,
                    "rows": str(max(int(rows), 0)),
                    "notes": notes,
                }
            ]
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.concat([existing[PRICE_LIST_LIVE_EVENT_COLUMNS], row], ignore_index=True).to_csv(path, index=False)
    except Exception:
        return


def _f061_row_queue_priority(row: dict[str, object] | pd.Series, *, login_mode_active: bool) -> int:
    payload = _row_dict_from_df_row(row) if isinstance(row, pd.Series) else dict(row)
    if login_mode_active:
        return active_row_queue_priority(payload)
    state = active_row_queue_state(payload)
    if active_row_is_rescan_retry(payload):
        return 0
    if state == ROW_QUEUE_PENDING:
        return 1
    if state in {ROW_QUEUE_NEEDS_LOGIN_RESCAN, ROW_QUEUE_NEEDS_YESNO_RESCAN}:
        return 2
    return 9


def _row_is_login_backtrack(row: dict[str, object] | pd.Series) -> bool:
    payload = _row_dict_from_df_row(row) if isinstance(row, pd.Series) else dict(row)
    return active_row_queue_state(payload) in {ROW_QUEUE_NEEDS_LOGIN_RESCAN, ROW_QUEUE_NEEDS_YESNO_RESCAN}


def _row_is_bbp_login_backtrack(row: dict[str, object] | pd.Series) -> bool:
    payload = _row_dict_from_df_row(row) if isinstance(row, pd.Series) else dict(row)
    return active_row_queue_state(payload) == ROW_QUEUE_NEEDS_LOGIN_RESCAN


def _count_login_backtrack_rows(df: pd.DataFrame, *, bbp_only: bool = False) -> int:
    if df.empty:
        return 0
    checker = _row_is_bbp_login_backtrack if bbp_only else _row_is_login_backtrack
    return int(df.apply(lambda row: checker(row), axis=1).sum())


def _endpoint_stats_snapshot(adapter: Any) -> dict[str, dict[str, float]]:
    if not hasattr(adapter, "endpoint_stats"):
        return {}
    try:
        raw = adapter.endpoint_stats()
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, float]] = {}
    for endpoint in ENDPOINT_KEYS:
        payload = raw.get(endpoint, {})
        if not isinstance(payload, dict):
            payload = {}
        out[endpoint] = {
            "calls_total": _parse_float(payload.get("calls_total", 0.0), 0.0),
            "throttle_429_total": _parse_float(payload.get("throttle_429_total", 0.0), 0.0),
            "wait_seconds_total": _parse_float(payload.get("wait_seconds_total", 0.0), 0.0),
        }
    return out


def _endpoint_delta(
    before: dict[str, dict[str, float]],
    after: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for endpoint in ENDPOINT_KEYS:
        before_payload = before.get(endpoint, {})
        after_payload = after.get(endpoint, {})
        out[endpoint] = {
            "calls_total": max(
                _parse_float(after_payload.get("calls_total", 0.0), 0.0)
                - _parse_float(before_payload.get("calls_total", 0.0), 0.0),
                0.0,
            ),
            "throttle_429_total": max(
                _parse_float(after_payload.get("throttle_429_total", 0.0), 0.0)
                - _parse_float(before_payload.get("throttle_429_total", 0.0), 0.0),
                0.0,
            ),
            "wait_seconds_total": max(
                _parse_float(after_payload.get("wait_seconds_total", 0.0), 0.0)
                - _parse_float(before_payload.get("wait_seconds_total", 0.0), 0.0),
                0.0,
            ),
        }
    return out


def _merge_endpoint_deltas(*deltas: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out = {endpoint: {"calls_total": 0.0, "throttle_429_total": 0.0, "wait_seconds_total": 0.0} for endpoint in ENDPOINT_KEYS}
    for delta in deltas:
        for endpoint in ENDPOINT_KEYS:
            payload = delta.get(endpoint, {})
            for key in ("calls_total", "throttle_429_total", "wait_seconds_total"):
                out[endpoint][key] += _parse_float(payload.get(key, 0.0), 0.0)
    return out


def _speed_timing_payload(
    *,
    total_seconds: float,
    endpoint_delta: dict[str, dict[str, float]],
    browser_attempted: bool,
    browser_blocked: bool,
) -> dict[str, object]:
    return {
        "total_seconds": max(total_seconds, 0.0),
        "catalog_wait_seconds": _parse_float(endpoint_delta.get(ENDPOINT_CATALOG, {}).get("wait_seconds_total", 0.0), 0.0),
        "hazmat_wait_seconds": _parse_float(endpoint_delta.get(ENDPOINT_HAZMAT, {}).get("wait_seconds_total", 0.0), 0.0),
        "pricing_wait_seconds": _parse_float(endpoint_delta.get(ENDPOINT_PRICING, {}).get("wait_seconds_total", 0.0), 0.0),
        "fees_wait_seconds": _parse_float(endpoint_delta.get(ENDPOINT_FEES, {}).get("wait_seconds_total", 0.0), 0.0),
        "browser_attempted_flag": "1" if browser_attempted else "0",
        "browser_blocked_flag": "1" if browser_blocked else "0",
        "api_429_count": int(
            sum(_parse_float(endpoint_delta.get(endpoint, {}).get("throttle_429_total", 0.0), 0.0) for endpoint in ENDPOINT_KEYS)
        ),
        "endpoint_call_count": int(
            sum(_parse_float(endpoint_delta.get(endpoint, {}).get("calls_total", 0.0), 0.0) for endpoint in ENDPOINT_KEYS)
        ),
    }


def _scrape_evidence_is_blocked(scrape_evidence_row: dict[str, str] | None) -> bool:
    if not isinstance(scrape_evidence_row, dict):
        return False
    text = _normalize_lower(
        " ".join(
            [
                scrape_evidence_row.get("scrape_error", ""),
                scrape_evidence_row.get("status_reason", ""),
                scrape_evidence_row.get("fail_codes", ""),
                scrape_evidence_row.get("checks_failed", ""),
            ]
        )
    )
    blocked_tokens = (
        "captcha",
        "blocked",
        "blocked_or_signin",
        "bbp_login_required",
        "login_required",
        " login ",
        "login",
        "no bbp iframe",
        "bbp iframe preflight failed",
        "bbp unavailable",
        "buybotpro unavailable",
        "buybotpro error",
        "extension failed",
        "extension failed to load",
        "failed to load properly",
        "intercept network requests",
        "bbp extension",
        "sign-in",
        "signin",
        "robot",
        "access denied",
    )
    return any(token in text for token in blocked_tokens)


def _scrape_evidence_needs_login_backtrack(scrape_evidence_row: dict[str, str] | None) -> bool:
    if not isinstance(scrape_evidence_row, dict):
        return False
    text = _normalize_lower(
        " ".join(
            [
                scrape_evidence_row.get("scrape_error", ""),
                scrape_evidence_row.get("status_reason", ""),
                scrape_evidence_row.get("fail_codes", ""),
                scrape_evidence_row.get("checks_failed", ""),
            ]
        )
    )
    return any(
        token in text
        for token in (
            "bbp_login_required",
            "login_required",
            " login ",
            "login",
            "no bbp iframe",
            "bbp iframe preflight failed",
            "bbp unavailable",
            "buybotpro unavailable",
            "buybotpro error",
            "extension failed",
            "extension failed to load",
            "failed to load properly",
            "intercept network requests",
            "bbp extension",
        )
    )


def _scrape_evidence_missing_required_dashboard_yes_no(scrape_evidence_row: dict[str, str] | None) -> bool:
    if not isinstance(scrape_evidence_row, dict):
        return False
    if _normalize_lower(scrape_evidence_row.get("scrape_success", "")) != "true":
        return False
    return not _valid_dashboard_yes_no(scrape_evidence_row.get("bbp_dashboard_yes_or_no", ""))


def _scrape_evidence_missing_dashboard_on_hard_fail(
    scrape_evidence_row: dict[str, str] | None,
    status_code: str,
) -> bool:
    if not isinstance(scrape_evidence_row, dict):
        return False
    if _normalize_text(status_code).upper() not in FAIL_STATUS_CODES:
        return False
    if _valid_dashboard_yes_no(scrape_evidence_row.get("bbp_dashboard_yes_or_no", "")):
        return False
    return any(
        _normalize_text(scrape_evidence_row.get(key, ""))
        for key in (
            "bbp_monthly_sales_current",
            "bbp_monthly_sales_recent_avg",
            "bbp_sales_chart_source",
            "bbp_top_seller_names",
            "avg_30_day_price",
            "price_hist_table_raw",
        )
    )


def _valid_dashboard_yes_no(value: object) -> bool:
    return has_required_dashboard_signal(value)


def _scanner_speed_ledger_row(
    *,
    active_row: pd.Series,
    first_row: dict[str, str],
    timing: dict[str, object],
    observed_utc: str,
) -> dict[str, str]:
    return {
        "observed_utc": observed_utc,
        "run_id": _normalize_text(active_row.get("run_id", "")),
        "supplier_id": _normalize_text(active_row.get("supplier_id", "")),
        "supplier_name": _normalize_text(active_row.get("supplier_name", "")),
        "supplier_sku": _normalize_text(active_row.get("supplier_sku", "")),
        "barcode": _normalize_digits(active_row.get("barcode", "")),
        "candidate_id": _normalize_text(first_row.get("candidate_id", "")) or _row_identity(active_row),
        "asin": _normalize_text(first_row.get("asin", "")),
        "status_reason": _normalize_text(first_row.get("status_reason", "")),
        "pf": _normalize_text(first_row.get("pf", "")),
        "total_seconds": _format_float(_parse_float(timing.get("total_seconds", 0.0), 0.0), 3),
        "catalog_wait_seconds": _format_float(_parse_float(timing.get("catalog_wait_seconds", 0.0), 0.0), 3),
        "hazmat_wait_seconds": _format_float(_parse_float(timing.get("hazmat_wait_seconds", 0.0), 0.0), 3),
        "pricing_wait_seconds": _format_float(_parse_float(timing.get("pricing_wait_seconds", 0.0), 0.0), 3),
        "fees_wait_seconds": _format_float(_parse_float(timing.get("fees_wait_seconds", 0.0), 0.0), 3),
        "browser_attempted_flag": _normalize_text(timing.get("browser_attempted_flag", "0")) or "0",
        "browser_blocked_flag": _normalize_text(timing.get("browser_blocked_flag", "0")) or "0",
        "api_429_count": str(int(_parse_float(timing.get("api_429_count", 0), 0.0))),
        "endpoint_call_count": str(int(_parse_float(timing.get("endpoint_call_count", 0), 0.0))),
        "source_cache_hit_flags": "",
        "updated_at_utc": observed_utc,
        "source_seen_at_utc": _normalize_text(active_row.get("source_seen_at_utc", "")),
    }


def _merge_speed_ledger(
    existing: pd.DataFrame,
    new_rows: list[dict[str, str]],
) -> pd.DataFrame:
    if not new_rows:
        return existing.copy()
    new_df = pd.DataFrame(new_rows)
    new_keys = {
        "|".join(
            [
                _normalize_lower(row.get("supplier_id", "")),
                _normalize_text(row.get("run_id", "")),
                _normalize_text(row.get("candidate_id", "")),
            ]
        )
        for row in new_rows
    }
    keep = existing.copy()
    if not keep.empty:
        keep = keep[
            ~keep.apply(
                lambda row: "|".join(
                    [
                        _normalize_lower(row.get("supplier_id", "")),
                        _normalize_text(row.get("run_id", "")),
                        _normalize_text(row.get("candidate_id", "")),
                    ]
                )
                in new_keys,
                axis=1,
            )
        ].copy()
    return pd.concat([keep, new_df], ignore_index=True)


def _row_identity(row: pd.Series) -> str:
    row_key = _normalize_text(row.get("row_key", ""))
    if row_key:
        return row_key
    return _build_row_hash_fallback(
        [
            _normalize_text(row.get("supplier_id", "")),
            _normalize_text(row.get("supplier_sku", "")),
            _normalize_text(row.get("barcode", "")),
            _normalize_text(row.get("supplier_title", "")),
            _normalize_text(row.get("unit_cost", "")),
        ]
    )


def _row_allowlist_identity(row: pd.Series) -> str:
    return _normalize_text(row.get("candidate_id", "")) or _normalize_text(row.get("row_key", "")) or _row_identity(row)


def _read_allowlist_ids(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    allowlist = pd.read_csv(path, dtype=str).fillna("")
    id_columns = [column for column in ["candidate_id", "row_key"] if column in allowlist.columns]
    if not id_columns:
        raise ValueError("allowlist_missing_candidate_id_or_row_key")
    ids: set[str] = set()
    for column in id_columns:
        ids.update(_normalize_text(value) for value in allowlist[column].tolist() if _normalize_text(value))
    return ids


def _candidate_identity(base_candidate_id: str, asin: str, candidate_index: int) -> str:
    safe_base = _normalize_text(base_candidate_id)
    safe_asin = _normalize_text(asin)
    if candidate_index <= 0:
        return safe_base
    if safe_asin:
        return f"{safe_base}__alt{candidate_index + 1}_{safe_asin}"
    return f"{safe_base}__alt{candidate_index + 1}"


def _catalog_rank_value(candidate: dict[str, Any]) -> int:
    rank_raw = candidate.get("rank", "")
    rank_val = _parse_optional_float(rank_raw)
    return int(rank_val) if rank_val is not None else -1


def _catalog_rank_is_in_gate(candidate: dict[str, Any]) -> bool:
    rank = _catalog_rank_value(candidate)
    return rank > 0 and rank <= 50000


def _dedupe_catalog_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_asins: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        asin = _normalize_text(candidate.get("asin", "")).upper()
        if asin == "":
            continue
        if asin in seen_asins:
            continue
        seen_asins.add(asin)
        out.append(candidate)
    return out


def _catalog_candidate_identifier_digits(candidate: dict[str, Any]) -> set[str]:
    raw_identifiers = candidate.get("identifiers")
    if not isinstance(raw_identifiers, list):
        return set()

    out: set[str] = set()
    for marketplace_block in raw_identifiers:
        if not isinstance(marketplace_block, dict):
            continue
        identifiers = marketplace_block.get("identifiers")
        if not isinstance(identifiers, list):
            continue
        for identifier_row in identifiers:
            if not isinstance(identifier_row, dict):
                continue
            digits = _normalize_digits(identifier_row.get("identifier", ""))
            if digits:
                out.add(digits)
    return out


def _extract_size_tokens(text: object) -> set[str]:
    out: set[str] = set()
    for token in _normalize_words(text):
        if token.endswith("ml") and any(ch.isdigit() for ch in token):
            out.add(token)
    return out


def _extract_match_metadata(candidate: dict[str, Any], supplier_title: str, search_barcode: str) -> dict[str, str | int]:
    supplier_title_norm = _normalize_text(supplier_title)
    supplier_title_lower = _normalize_lower(supplier_title_norm)
    supplier_words = set(_normalize_words(supplier_title_norm))

    candidate_brand = _normalize_text(candidate.get("brand", ""))
    candidate_title = _normalize_text(candidate.get("title", ""))
    candidate_brand_lower = _normalize_lower(candidate_brand)
    candidate_title_lower = _normalize_lower(candidate_title)
    candidate_identifiers = _catalog_candidate_identifier_digits(candidate)
    search_digits = _normalize_digits(search_barcode)

    score = 0
    reasons: list[str] = []

    if search_digits and search_digits in candidate_identifiers:
        score += 70
        reasons.append("exact_barcode")
    elif candidate_identifiers:
        reasons.append("barcode_conflict")
    else:
        score += 20
        reasons.append("barcode_unknown")

    if candidate_brand_lower and candidate_brand_lower in supplier_title_lower:
        score += 15
        reasons.append("brand_match")

    supplier_sizes = _extract_size_tokens(supplier_title_norm)
    candidate_sizes = _extract_size_tokens(candidate_title) | _extract_size_tokens(candidate_brand)
    if supplier_sizes and candidate_sizes and supplier_sizes.intersection(candidate_sizes):
        score += 10
        reasons.append("size_match")

    shared_words = supplier_words.intersection(set(_normalize_words(candidate_title)))
    significant_shared = {word for word in shared_words if len(word) >= 5 and not word.isdigit()}
    if significant_shared:
        score += 5
        reasons.append("title_overlap")

    score = min(score, 100)
    if "exact_barcode" in reasons:
        grade = "EXACT"
    elif score >= 80:
        grade = "EXACT"
    elif score >= 45:
        grade = "LIKELY"
    elif score >= 20:
        grade = "WEAK"
    else:
        grade = "VERY_WEAK"

    return {
        "score": score,
        "grade": grade,
        "reasons": ",".join(reasons),
    }


def _select_catalog_candidates_for_processing(
    *,
    candidates: list[dict[str, Any]],
    max_candidates: int,
    search_barcode: str,
    supplier_title: str,
) -> list[dict[str, Any]]:
    deduped = _dedupe_catalog_candidates(candidates)
    if not deduped:
        return []

    for candidate in deduped:
        metadata = _extract_match_metadata(candidate, supplier_title, search_barcode)
        candidate["_match_score"] = int(metadata["score"])
        candidate["_match_grade"] = str(metadata["grade"])
        candidate["_match_reasons"] = str(metadata["reasons"])

    max_allowed = max(int(max_candidates), 1)
    rank_pass_candidates = [candidate for candidate in deduped if _catalog_rank_is_in_gate(candidate)]
    if not rank_pass_candidates:
        ordered_candidates = deduped
    else:
        ordered_candidates = rank_pass_candidates

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, candidate in enumerate(ordered_candidates):
        rank_val = _catalog_rank_value(candidate)
        match_score = -_parse_nonnegative_int(candidate.get("_match_score", 0), default=0)
        scored.append((match_score, rank_val if rank_val > 0 else 999999999, index, candidate))
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    ordered = [payload for _, _, _, payload in scored]
    return ordered[:max_allowed]


def _catalog_candidates_from_adapter(
    *,
    adapter: Any,
    barcode: str,
    access_token: str,
) -> list[dict[str, Any]] | None:
    if hasattr(adapter, "get_catalog_candidates"):
        payload = adapter.get_catalog_candidates(barcode, access_token)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]

    payload = adapter.get_catalog_details(barcode, access_token)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return None


def _safe_cache_part(value: object) -> str:
    text = _normalize_lower(value)
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    return safe.strip("_") or "unknown"


def _api_cache_dir(root_path: Path, *, supplier_id: str, run_id: str) -> Path:
    return (
        root_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "pipeline_runs"
        / _safe_cache_part(supplier_id)
        / _safe_cache_part(run_id)
        / "api_cache"
    )


def _api_cache_path(cache_dir: Path, *, endpoint: str, key: str) -> Path:
    digest = hashlib.sha256(f"{endpoint}|{key}".encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"{_safe_cache_part(endpoint)}_{digest}.json"


def _read_api_cache(cache_dir: Path | None, *, endpoint: str, key: str) -> dict[str, Any] | None:
    if cache_dir is None:
        return None
    path = _api_cache_path(cache_dir, endpoint=endpoint, key=key)
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("payload")
    if not isinstance(value, dict):
        return None
    return value


def _write_api_cache(cache_dir: Path | None, *, endpoint: str, key: str, payload: dict[str, Any]) -> None:
    if cache_dir is None or not isinstance(payload, dict):
        return
    if _normalize_text(payload.get("error", "")):
        return
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = _api_cache_path(cache_dir, endpoint=endpoint, key=key)
        tmp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        tmp_path.write_text(
            json.dumps(
                {
                    "endpoint": endpoint,
                    "key": key,
                    "payload": payload,
                    "cached_at_utc": _utc_now_iso(),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
    except Exception:
        return


def _cached_api_call(
    cache_dir: Path | None,
    *,
    endpoint: str,
    key: str,
    call: Any,
) -> dict[str, Any]:
    cached = _read_api_cache(cache_dir, endpoint=endpoint, key=key)
    if cached is not None:
        return cached
    payload = call()
    if isinstance(payload, dict):
        _write_api_cache(cache_dir, endpoint=endpoint, key=key, payload=payload)
        return payload
    return {}


def _map_scrape_error_to_status(error_text: str) -> str:
    err = _normalize_text(error_text)
    if err == "ROI < 20%":
        return "LOWROI"
    if err == "LOWROI":
        return "LOWROI"
    if err == "NO_PRICE_HISTORY_365D":
        return "PRICEHISTORYFAIL"
    if err == "LOW_SALES_CAPITAL_IDLE_RISK":
        return "LOWSALESFAIL"
    if err == "DASHBOARD_NO_LOW_SELLER_COUNT":
        return "SELLERHISTORYFAIL"
    if err == "CHROMEVERSIONFAIL" or err.startswith("CHROMEVERSIONFAIL:"):
        return "RESCAN"
    if err == "REVIEWS_TIMEOUT" or err.startswith("REVIEWS_TIMEOUT:"):
        return "RESCAN"
    if err == "INCOMPLETE_PRICE_HISTORY_CAPTURE":
        return "RESCAN"
    if err == "Seller ~ brand":
        return "BRANDFAIL"
    if err == "NODATE_OLDCHROME":
        return "NODATE"
    if err == "REVIEWS_NO_UK":
        return "REVIEWFAIL"
    if err == "SCRAPE_DISABLED":
        return "RESCAN"
    return "SCRAPEFAIL"


def _status_to_pf(status_code: str) -> str:
    if status_code == "PASS":
        return "PASS"
    if status_code == F061_STATUS_BROWSER_READY:
        return ""
    if status_code in RETRY_STATUS_CODES:
        return "RESCAN"
    if status_code == "":
        return ""
    return "FAIL"


def _row_status_from_pf(pf_value: str) -> str:
    pf_upper = _normalize_text(pf_value).upper()
    if pf_upper == "PASS":
        return "pass"
    if pf_upper in {"FAIL", "RESCAN"}:
        return "timeout"
    return "pending"


def _row_status_from_processed_row(first_row: dict[str, str]) -> str:
    status_reason = _normalize_text(first_row.get("status_reason", "")).upper()
    if status_reason == F061_LOGIN_BACKTRACK_REASON:
        return F061_SCAN_STATUS_LOGIN_BACKTRACK_PENDING
    return _row_status_from_pf(_normalize_text(first_row.get("pf", "")))


def _first_check_row_kept_live(row: dict[str, object] | pd.Series) -> bool:
    if _normalize_text(row.get("pf", "")).upper() == "PASS":
        return True
    return _normalize_lower(row.get("status_reason", "")) == F061_BROWSER_STAGE_READY_REASON


def _fail_code_from_status_reason(status_reason: str, pf_value: str) -> str:
    pf_upper = _normalize_text(pf_value).upper()
    if pf_upper == "PASS":
        return ""
    reason = _normalize_text(status_reason)
    if reason == "":
        return pf_upper if pf_upper in {"FAIL", "RESCAN"} else ""
    return _normalize_text(reason.split("|", 1)[0]).upper()


def _last_stage_for_fail_code(*, fail_code: str, pf_value: str) -> str:
    pf_upper = _normalize_text(pf_value).upper()
    if pf_upper == "PASS":
        return "webscrape"

    stage_map = {
        "NOASIN": "catalog",
        "OVER50K": "rank_gate",
        "HAZMATFAIL": "hazmat_gate",
        "NOCOST": "cost_gate",
        "ROIFAIL": "roi_gate",
        "LOWROI": "webscrape",
        "LOWSALESFAIL": "webscrape",
        "SELLERHISTORYFAIL": "webscrape",
        "PRICEHISTORYFAIL": "webscrape",
        "BRANDFAIL": "webscrape",
        "NODATE": "webscrape",
        "REVIEWFAIL": "webscrape",
        "SCRAPEFAIL": "webscrape",
        F061_STATUS_BROWSER_READY: "fee_hazmat_api",
        F061_BROWSER_STAGE_READY_REASON.upper(): "fee_hazmat_api",
        F061_LOGIN_BACKTRACK_STATUS_CODE: "webscrape",
        "RESCAN": "retry",
        "FAIL": "webscrape",
    }
    return stage_map.get(_normalize_text(fail_code).upper(), "unknown")


def _build_screening_row_state_processed(
    *,
    active_row: dict[str, str],
    first_row: dict[str, str],
    observed_utc: str,
    mode: str,
    timeout_policy_df: pd.DataFrame | None = None,
) -> dict[str, str]:
    pf_value = _normalize_text(first_row.get("pf", "")).upper()
    status_reason = _normalize_text(first_row.get("status_reason", ""))
    fail_code = _fail_code_from_status_reason(status_reason, pf_value)
    attempt_count = _parse_nonnegative_int(active_row.get("attempt_count", "0"), default=0) + 1
    row_status = _row_status_from_processed_row(first_row)
    timeout_until_utc = _timeout_until_utc_for_status(
        observed_utc=observed_utc,
        pf_value=pf_value,
        fail_code=fail_code,
        timeout_policy_df=timeout_policy_df,
    )
    return {
        "observed_utc": observed_utc,
        "run_id": _normalize_text(active_row.get("run_id", "")),
        "supplier_id": _normalize_text(active_row.get("supplier_id", "")),
        "supplier_name": _normalize_text(active_row.get("supplier_name", "")),
        "supplier_sku": _normalize_text(first_row.get("supplier_sku", active_row.get("supplier_sku", ""))),
        "supplier_title": _normalize_text(active_row.get("supplier_title", "")),
        "barcode": _normalize_digits(first_row.get("barcode", active_row.get("barcode", ""))),
        "candidate_id": _normalize_text(first_row.get("candidate_id", "")),
        "asin": _normalize_text(first_row.get("asin", "")),
        "row_status": row_status,
        "last_stage": _last_stage_for_fail_code(fail_code=fail_code, pf_value=pf_value),
        "fail_code": fail_code,
        "attempt_count": str(attempt_count),
        "timeout_until_utc": timeout_until_utc,
        "mode": _normalize_text(mode),
        "updated_at_utc": observed_utc,
        "source_seen_at_utc": _normalize_text(active_row.get("source_seen_at_utc", "")),
        "pf": pf_value,
        "status_reason": status_reason,
        "recommendation_status": _normalize_text(first_row.get("recommendation_status", "")),
        "recommended_test_qty": _normalize_text(first_row.get("recommended_test_qty", "")),
    }


def _build_screening_row_state_pending(
    *,
    active_row: dict[str, str],
    candidate_id: str,
    observed_utc: str,
    mode: str,
) -> dict[str, str]:
    return {
        "observed_utc": observed_utc,
        "run_id": _normalize_text(active_row.get("run_id", "")),
        "supplier_id": _normalize_text(active_row.get("supplier_id", "")),
        "supplier_name": _normalize_text(active_row.get("supplier_name", "")),
        "supplier_sku": _normalize_text(active_row.get("supplier_sku", "")),
        "supplier_title": _normalize_text(active_row.get("supplier_title", "")),
        "barcode": _normalize_digits(active_row.get("barcode", "")),
        "candidate_id": _normalize_text(candidate_id),
        "asin": "",
        "row_status": "pending",
        "last_stage": "start",
        "fail_code": "",
        "attempt_count": str(_parse_nonnegative_int(active_row.get("attempt_count", "0"), default=0)),
        "timeout_until_utc": "",
        "mode": _normalize_text(mode),
        "updated_at_utc": observed_utc,
        "source_seen_at_utc": _normalize_text(active_row.get("source_seen_at_utc", "")),
        "pf": "",
        "status_reason": "",
        "recommendation_status": "",
        "recommended_test_qty": "",
    }


def _compute_point_score(*, date_value: str, rating_value: str, variant_reviews_value: str, reviews_list_value: str) -> float:
    today = datetime.now(timezone.utc)
    years_since_release = _parse_release_date_years(date_value, today)
    variant_reviews = max(_parse_float(variant_reviews_value), 0.0)
    rating = max(_parse_float(rating_value), 0.0)
    reviews_list = max(_parse_float(reviews_list_value), 0.0)

    score = 1.0

    threshold_40 = years_since_release * 40.0
    threshold_50 = years_since_release * 50.0
    if variant_reviews > threshold_40:
        score += 1.0 if variant_reviews > threshold_50 else 0.5

    if rating >= 3.5:
        score += 1.0 if rating >= 4.0 else 0.5

    if reviews_list >= 6:
        score += 1.0

    if variant_reviews >= 6:
        score += 1.0

    return round(score, 2)


class LegacyCompatibleAmazonAdapter:
    def __init__(
        self,
        *,
        legacy_scanner_root: str | None = None,
        scrape_mode: str = "legacy_module",
        timeout_seconds: int = 30,
        price_source: str = PRICE_SOURCE_LEGACY,
        pricing_retries: int = 3,
        root_path: Path | None = None,
        catalog_min_interval_seconds: float = 0.5,
        hazmat_min_interval_seconds: float = 1.0,
        pricing_min_interval_seconds: float = 30.0,
        fees_min_interval_seconds: float = 1.0,
        scrape_page_load_timeout_seconds: float = 45.0,
    ) -> None:
        self._legacy_scanner_root = Path(legacy_scanner_root) if legacy_scanner_root else None
        self._root_path = Path(root_path) if root_path is not None else ROOT
        self._scrape_mode = _normalize_lower(scrape_mode) or "disabled"
        self._timeout_seconds = timeout_seconds
        normalized_price_source = _normalize_lower(price_source) or PRICE_SOURCE_LEGACY
        if normalized_price_source not in PRICE_SOURCE_ALLOWED:
            normalized_price_source = PRICE_SOURCE_LEGACY
        self._price_source = normalized_price_source
        self._pricing_retries = max(int(pricing_retries), 1)
        self._catalog_retries = max(int(pricing_retries), 1)
        self._pricing_stats: dict[str, int | str] = {
            "source": self._price_source,
            "calls_total": 0,
            "errors_total": 0,
            "throttle_429_total": 0,
        }
        self._endpoint_intervals_seconds = {
            ENDPOINT_CATALOG: _parse_positive_float(catalog_min_interval_seconds, 0.5),
            ENDPOINT_HAZMAT: _parse_positive_float(hazmat_min_interval_seconds, 1.0),
            ENDPOINT_PRICING: _parse_positive_float(pricing_min_interval_seconds, 30.0),
            ENDPOINT_FEES: _parse_positive_float(fees_min_interval_seconds, 1.0),
        }
        self._scrape_page_load_timeout_seconds = _parse_positive_float(scrape_page_load_timeout_seconds, 45.0)
        cooldown_path_env = _normalize_text(os.environ.get(F061_COOLDOWN_STATE_PATH_ENV, ""))
        cooldown_path = (
            Path(cooldown_path_env)
            if cooldown_path_env
            else self._root_path / "out" / "systems" / "F" / "live" / "f061_spapi_endpoint_cooldowns.json"
        )
        self._endpoint_cooldowns = _EndpointCooldownStore(
            state_path=cooldown_path,
            default_intervals_seconds=self._endpoint_intervals_seconds,
        )
        self._endpoint_stats: dict[str, dict[str, float | int]] = {
            key: {
                "calls_total": 0,
                "errors_total": 0,
                "throttle_429_total": 0,
                "wait_seconds_total": 0.0,
            }
            for key in ENDPOINT_KEYS
        }

        self._cached_token = ""
        self._cached_expiry_utc = 0.0

        self._legacy_token_func = None
        self._legacy_catalog_func = None
        self._legacy_hazmat_func = None
        self._legacy_pricing_func = None
        self._legacy_fees_func = None
        self._legacy_scrape_func = None
        self._legacy_load_errors: dict[str, str] = {}

        self._bbp_driver = None
        self._date_driver = None
        self._driver_init_error = ""

        self._load_legacy_modules()
        atexit.register(self.close)

    def _load_legacy_modules(self) -> None:
        if self._legacy_scanner_root is None:
            return
        if not self._legacy_scanner_root.exists():
            self._legacy_load_errors["legacy_scanner_root"] = "missing_path"
            return

        root_str = str(self._legacy_scanner_root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        try:
            from tokenCall import get_access_token as legacy_get_token  # type: ignore

            self._legacy_token_func = legacy_get_token
        except Exception as exc:
            self._legacy_token_func = None
            self._legacy_load_errors["tokenCall.get_access_token"] = type(exc).__name__

        try:
            from amazonCatalogCall import get_catalog_details as legacy_get_catalog  # type: ignore

            self._legacy_catalog_func = legacy_get_catalog
        except Exception as exc:
            self._legacy_catalog_func = None
            self._legacy_load_errors["amazonCatalogCall.get_catalog_details"] = type(exc).__name__

        try:
            from hazmatCall import check_eligibility_for_asin as legacy_hazmat  # type: ignore

            self._legacy_hazmat_func = legacy_hazmat
        except Exception as exc:
            self._legacy_hazmat_func = None
            self._legacy_load_errors["hazmatCall.check_eligibility_for_asin"] = type(exc).__name__

        try:
            from pricingCall import get_pricing_details_for_asin as legacy_pricing  # type: ignore

            self._legacy_pricing_func = legacy_pricing
        except Exception as exc:
            self._legacy_pricing_func = None
            self._legacy_load_errors["pricingCall.get_pricing_details_for_asin"] = type(exc).__name__

        try:
            from feeCall import get_fees_estimate_for_asin as legacy_fees  # type: ignore

            self._legacy_fees_func = legacy_fees
        except Exception as exc:
            self._legacy_fees_func = None
            self._legacy_load_errors["feeCall.get_fees_estimate_for_asin"] = type(exc).__name__

        try:
            from Webscrape import process_passed_product as legacy_scrape  # type: ignore

            self._legacy_scrape_func = legacy_scrape
        except Exception as exc:
            self._legacy_scrape_func = None
            self._legacy_load_errors["Webscrape.process_passed_product"] = type(exc).__name__

    def missing_legacy_modules(self) -> list[str]:
        if self._legacy_scanner_root is None:
            return []
        if not self._legacy_scanner_root.exists():
            return ["legacy_scanner_root"]

        missing: list[str] = []
        if self._legacy_token_func is None:
            missing.append("tokenCall.get_access_token")
        if self._legacy_catalog_func is None:
            missing.append("amazonCatalogCall.get_catalog_details")
        if self._legacy_hazmat_func is None:
            missing.append("hazmatCall.check_eligibility_for_asin")
        if self._price_source == PRICE_SOURCE_LEGACY and self._legacy_pricing_func is None:
            missing.append("pricingCall.get_pricing_details_for_asin")
        if self._legacy_fees_func is None:
            missing.append("feeCall.get_fees_estimate_for_asin")
        if self._legacy_scrape_func is None:
            missing.append("Webscrape.process_passed_product")
        return missing

    def legacy_module_load_errors(self) -> dict[str, str]:
        return dict(self._legacy_load_errors)

    def pricing_stats(self) -> dict[str, int | str]:
        return dict(self._pricing_stats)

    def endpoint_stats(self) -> dict[str, dict[str, float | int]]:
        out: dict[str, dict[str, float | int]] = {}
        for endpoint, payload in self._endpoint_stats.items():
            out[endpoint] = {
                "calls_total": int(payload.get("calls_total", 0)),
                "errors_total": int(payload.get("errors_total", 0)),
                "throttle_429_total": int(payload.get("throttle_429_total", 0)),
                "wait_seconds_total": round(float(payload.get("wait_seconds_total", 0.0)), 3),
            }
        return out

    def endpoint_intervals_seconds(self) -> dict[str, float]:
        return {k: round(float(v), 3) for k, v in self._endpoint_intervals_seconds.items()}

    def _endpoint_wait(self, endpoint: str) -> None:
        wait_seconds = self._endpoint_cooldowns.wait_for_slot(endpoint)
        bucket = self._endpoint_stats.setdefault(
            endpoint,
            {"calls_total": 0, "errors_total": 0, "throttle_429_total": 0, "wait_seconds_total": 0.0},
        )
        bucket["wait_seconds_total"] = float(bucket.get("wait_seconds_total", 0.0)) + float(wait_seconds)

    def _endpoint_mark(
        self,
        endpoint: str,
        *,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
        error: str = "",
    ) -> None:
        bucket = self._endpoint_stats.setdefault(
            endpoint,
            {"calls_total": 0, "errors_total": 0, "throttle_429_total": 0, "wait_seconds_total": 0.0},
        )
        bucket["calls_total"] = int(bucket.get("calls_total", 0)) + 1
        if status_code == 429:
            bucket["throttle_429_total"] = int(bucket.get("throttle_429_total", 0)) + 1
        if error or (status_code is not None and status_code >= 400):
            bucket["errors_total"] = int(bucket.get("errors_total", 0)) + 1
        self._endpoint_cooldowns.mark_call(endpoint, status_code=status_code, headers=headers, error=error)

    def _token_from_env(self) -> str:
        current_epoch = datetime.now(timezone.utc).timestamp()
        if self._cached_token and current_epoch < self._cached_expiry_utc - 120:
            return self._cached_token

        refresh_token = os.environ.get("LWA_REFRESH_TOKEN", "").strip()
        client_id = os.environ.get("LWA_CLIENT_ID", "").strip()
        client_secret = os.environ.get("LWA_CLIENT_SECRET", "").strip()
        if not refresh_token or not client_id or not client_secret:
            return ""

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
        response = requests.post(
            LWA_TOKEN_URL,
            data=payload,
            headers=headers,
            timeout=self._timeout_seconds,
        )
        if response.status_code != 200:
            return ""
        body = response.json()
        access_token = _normalize_text(body.get("access_token", ""))
        if access_token == "":
            return ""

        expires_in = _parse_float(body.get("expires_in"), default=1800.0)
        self._cached_token = access_token
        self._cached_expiry_utc = current_epoch + max(expires_in, 300.0)
        return self._cached_token

    def get_access_token(self) -> str:
        load_dotenv_if_missing()
        token = self._token_from_env()
        if token:
            return token
        if self._legacy_token_func is not None:
            try:
                legacy_token = _normalize_text(self._legacy_token_func())
                if legacy_token:
                    return legacy_token
            except Exception:
                pass
        return ""

    def _catalog_identifier_types(self, barcode: str) -> list[str]:
        digits = _normalize_digits(barcode)
        if len(digits) == 13:
            candidates = ["EAN", "UPC"]
        elif len(digits) == 12:
            candidates = ["UPC", "EAN"]
        elif len(digits) == 14:
            candidates = ["GTIN", "EAN", "UPC"]
        elif len(digits) == 8:
            candidates = ["EAN", "UPC"]
        else:
            candidates = ["UPC", "EAN"]

        ordered: list[str] = []
        for value in candidates:
            if value not in ordered:
                ordered.append(value)
        return ordered

    def _catalog_item_to_details(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        dimensions = ((item.get("dimensions") or [{}])[0] or {}).get("package", {})
        weight_data = dimensions.get("weight", {}) if isinstance(dimensions, dict) else {}
        weight = ""
        if isinstance(weight_data, dict):
            unit = _normalize_lower(weight_data.get("unit", ""))
            if unit == "pounds":
                weight = _normalize_text(weight_data.get("value", ""))
        if not weight:
            attrs = item.get("attributes") or {}
            if isinstance(attrs, dict):
                iw = attrs.get("item_weight") or [{}]
                if isinstance(iw, list) and iw and isinstance(iw[0], dict):
                    weight = _normalize_text(iw[0].get("value", ""))

        rank_value: Any = ""
        sales_ranks = item.get("salesRanks") or []
        if isinstance(sales_ranks, list) and sales_ranks and isinstance(sales_ranks[0], dict):
            groups = sales_ranks[0].get("displayGroupRanks") or []
            if isinstance(groups, list) and groups and isinstance(groups[0], dict):
                rank_value = groups[0].get("rank", "")

        attributes = item.get("attributes") or {}
        brand = "Unknown"
        if isinstance(attributes, dict):
            brand_rows = attributes.get("brand") or []
            if isinstance(brand_rows, list) and brand_rows and isinstance(brand_rows[0], dict):
                brand = _normalize_text(brand_rows[0].get("value", "Unknown")) or "Unknown"

        summaries = item.get("summaries") or []
        release_date = "N/A"
        title = ""
        if isinstance(summaries, list) and summaries and isinstance(summaries[0], dict):
            release_date = _normalize_text(summaries[0].get("releaseDate", "N/A")) or "N/A"
            title = _normalize_text(summaries[0].get("itemName", ""))

        return {
            "asin": _normalize_text(item.get("asin", "")),
            "rank": rank_value,
            "brand": brand,
            "title": title,
            "dimensions": dimensions if isinstance(dimensions, dict) else {},
            "weight": weight,
            "release_date": release_date,
            "identifiers": item.get("identifiers") if isinstance(item.get("identifiers"), list) else [],
        }

    def _catalog_payload_to_candidates(self, payload: object) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        items = payload.get("items") or []
        if not isinstance(items, list) or not items:
            return []

        out: list[dict[str, Any]] = []
        for item in items:
            parsed = self._catalog_item_to_details(item if isinstance(item, dict) else {})
            if isinstance(parsed, dict):
                out.append(parsed)
        return out

    def _catalog_payload_to_details(self, payload: object) -> dict[str, Any] | None:
        candidates = self._catalog_payload_to_candidates(payload)
        if not candidates:
            return None
        return candidates[0]

    def _native_get_catalog_candidates(self, barcode: str, access_token: str) -> list[dict[str, Any]] | None:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-amz-access-token": access_token,
            "Accept": "application/json",
        }
        lookup_error = ""
        for identifiers_type in self._catalog_identifier_types(barcode):
            for attempt in range(self._catalog_retries):
                params = {
                    "identifiers": barcode,
                    "identifiersType": identifiers_type,
                    "marketplaceIds": MARKETPLACE_ID_UK,
                    "includedData": "attributes,dimensions,identifiers,salesRanks,classifications,summaries",
                }
                self._endpoint_wait(ENDPOINT_CATALOG)
                try:
                    response = requests.get(
                        f"{SPAPI_BASE_URL}/catalog/2022-04-01/items",
                        headers=headers,
                        params=params,
                        timeout=self._timeout_seconds,
                    )
                except Exception as exc:
                    lookup_error = f"request_exception:{type(exc).__name__}"
                    self._endpoint_mark(ENDPOINT_CATALOG, error=lookup_error)
                    if attempt < self._catalog_retries - 1:
                        time.sleep(min(1.0 + float(attempt), 3.0))
                    continue
                self._endpoint_mark(
                    ENDPOINT_CATALOG,
                    status_code=int(response.status_code),
                    headers=dict(getattr(response, "headers", {}) or {}),
                )

                if response.status_code == 429:
                    lookup_error = "http_429"
                    if attempt < self._catalog_retries - 1:
                        time.sleep(min(2.0 + float(attempt), 5.0))
                    continue
                if response.status_code >= 500:
                    lookup_error = f"http_{int(response.status_code)}"
                    if attempt < self._catalog_retries - 1:
                        time.sleep(min(1.0 + float(attempt), 3.0))
                    continue
                if response.status_code != 200:
                    lookup_error = f"http_{int(response.status_code)}"
                    break

                try:
                    body = response.json()
                except Exception:
                    lookup_error = "invalid_json"
                    if attempt < self._catalog_retries - 1:
                        time.sleep(min(1.0 + float(attempt), 3.0))
                    continue

                candidates = self._catalog_payload_to_candidates(body)
                if candidates:
                    return candidates
                break

        if lookup_error:
            return [{"asin": "", "error": lookup_error}]
        return None

    def _native_get_catalog_details(self, barcode: str, access_token: str) -> dict[str, Any] | None:
        candidates = self._native_get_catalog_candidates(barcode, access_token)
        if not candidates:
            return None
        return candidates[0]

    def get_catalog_candidates(self, barcode: str, access_token: str) -> list[dict[str, Any]] | None:
        native_payload = self._native_get_catalog_candidates(barcode, access_token)
        if isinstance(native_payload, list):
            return native_payload
        return None

    def get_catalog_details(self, barcode: str, access_token: str) -> dict[str, Any] | None:
        candidates = self.get_catalog_candidates(barcode, access_token)
        if isinstance(candidates, list) and candidates:
            return candidates[0]
        return None

    def check_hazmat(self, asin: str, access_token: str) -> dict[str, Any]:
        if self._legacy_hazmat_func is not None:
            self._endpoint_wait(ENDPOINT_HAZMAT)
            try:
                payload = self._legacy_hazmat_func(asin, access_token)
                self._endpoint_mark(ENDPOINT_HAZMAT, error="" if isinstance(payload, dict) else "legacy_payload_invalid")
                if isinstance(payload, dict):
                    return payload
            except Exception:
                self._endpoint_mark(ENDPOINT_HAZMAT, error="legacy_hazmat_exception")
                pass
            return {"asin": asin, "eligible": False, "error": "legacy_hazmat_error"}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-amz-access-token": access_token,
            "Accept": "application/json",
        }
        params = {
            "asin": asin,
            "program": "INBOUND",
            "marketplaceIds": MARKETPLACE_ID_UK,
        }
        self._endpoint_wait(ENDPOINT_HAZMAT)
        response = requests.get(
            f"{SPAPI_BASE_URL}/fba/inbound/v1/eligibility/itemPreview",
            headers=headers,
            params=params,
            timeout=self._timeout_seconds,
        )
        self._endpoint_mark(
            ENDPOINT_HAZMAT,
            status_code=int(response.status_code),
            headers=dict(getattr(response, "headers", {}) or {}),
        )
        if response.status_code != 200:
            return {"asin": asin, "eligible": False, "error": f"http_{response.status_code}"}
        body = response.json()
        payload = body.get("payload") if isinstance(body, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "asin": asin,
            "eligible": bool(payload.get("isEligibleForProgram")),
            "reasons": payload.get("ineligibilityReasonList", []),
        }

    def _extract_comp_summary_prices(self, payload: object) -> tuple[str, str, str]:
        if not isinstance(payload, dict):
            return "0", "0", "empty_responses"
        responses = payload.get("responses")
        if not isinstance(responses, list) or not responses:
            return "0", "0", "empty_responses"

        first = responses[0] if isinstance(responses[0], dict) else {}
        status_code = _parse_status_code(first.get("status"))
        if status_code is None:
            return "0", "0", "batch_status_unknown"
        if status_code < 200 or status_code >= 300:
            return "0", "0", f"batch_status_{status_code}"

        body_obj = first.get("body") if isinstance(first.get("body"), dict) else {}
        featured = body_obj.get("featuredBuyingOptions") if isinstance(body_obj, dict) else []
        low_offers = body_obj.get("lowestPricedOffers") if isinstance(body_obj, dict) else []

        buy_box_price = "0"
        if isinstance(featured, list) and featured and isinstance(featured[0], dict):
            segmented = featured[0].get("segmentedFeaturedOffers") or []
            if isinstance(segmented, list) and segmented and isinstance(segmented[0], dict):
                lp = segmented[0].get("listingPrice") or {}
                if isinstance(lp, dict):
                    buy_box_price = _normalize_text(lp.get("amount", "0")) or "0"

        lowest_afn_price = "0"
        if isinstance(low_offers, list) and low_offers and isinstance(low_offers[0], dict):
            offers = low_offers[0].get("offers") or []
            if isinstance(offers, list) and offers and isinstance(offers[0], dict):
                lp = offers[0].get("listingPrice") or {}
                if isinstance(lp, dict):
                    lowest_afn_price = _normalize_text(lp.get("amount", "0")) or "0"

        return buy_box_price, lowest_afn_price, ""

    def _native_comp_summary_get_pricing(self, asin: str, access_token: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-amz-access-token": access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        body = {
            "requests": [
                {
                    "method": "GET",
                    "uri": "/products/pricing/2022-05-01/items/competitiveSummary",
                    "marketplaceId": MARKETPLACE_ID_UK,
                    "asin": asin,
                    "includedData": ["featuredBuyingOptions", "lowestPricedOffers"],
                    "lowestPricedOffersInputs": [
                        {
                            "itemCondition": "New",
                            "offerType": "Consumer",
                        }
                    ],
                }
            ]
        }

        response_error = ""
        for attempt in range(self._pricing_retries):
            self._endpoint_wait(ENDPOINT_PRICING)
            try:
                response = requests.post(
                    f"{SPAPI_BASE_URL}/batches/products/pricing/2022-05-01/items/competitiveSummary",
                    headers=headers,
                    json=body,
                    timeout=self._timeout_seconds,
                )
            except Exception as exc:
                response_error = f"request_exception:{type(exc).__name__}"
                self._pricing_stats["errors_total"] = int(self._pricing_stats["errors_total"]) + 1
                self._endpoint_mark(ENDPOINT_PRICING, error=response_error)
                if attempt < self._pricing_retries - 1:
                    time.sleep(min(1.0 + float(attempt), 3.0))
                continue
            self._endpoint_mark(
                ENDPOINT_PRICING,
                status_code=int(response.status_code),
                headers=dict(getattr(response, "headers", {}) or {}),
            )

            if response.status_code == 429:
                self._pricing_stats["throttle_429_total"] = int(self._pricing_stats["throttle_429_total"]) + 1
                response_error = "http_429"
                if attempt < self._pricing_retries - 1:
                    time.sleep(min(2.0 + float(attempt), 5.0))
                continue
            if response.status_code < 200 or response.status_code >= 300:
                self._pricing_stats["errors_total"] = int(self._pricing_stats["errors_total"]) + 1
                response_error = f"http_{int(response.status_code)}"
                if response.status_code >= 500 and attempt < self._pricing_retries - 1:
                    time.sleep(min(1.0 + float(attempt), 3.0))
                    continue
                break

            try:
                payload = response.json()
            except Exception:
                self._pricing_stats["errors_total"] = int(self._pricing_stats["errors_total"]) + 1
                response_error = "invalid_json"
                if attempt < self._pricing_retries - 1:
                    time.sleep(min(1.0 + float(attempt), 3.0))
                continue

            buy_box_price, lowest_afn_price, parse_error = self._extract_comp_summary_prices(payload)
            if parse_error:
                self._pricing_stats["errors_total"] = int(self._pricing_stats["errors_total"]) + 1
                response_error = parse_error
                if parse_error.startswith("batch_status_5") and attempt < self._pricing_retries - 1:
                    time.sleep(min(1.0 + float(attempt), 3.0))
                    continue
                return {
                    "asin": asin,
                    "buy_box_price": "0",
                    "lowest_afn_price": "0",
                    "error": parse_error,
                }

            return {
                "asin": asin,
                "buy_box_price": buy_box_price,
                "lowest_afn_price": lowest_afn_price,
            }

        if response_error == "":
            response_error = "pricing_failed_after_retries"
        return {
            "asin": asin,
            "buy_box_price": "0",
            "lowest_afn_price": "0",
            "error": response_error,
        }

    def get_pricing(self, asin: str, access_token: str) -> dict[str, Any]:
        self._pricing_stats["calls_total"] = int(self._pricing_stats["calls_total"]) + 1
        if self._price_source == PRICE_SOURCE_LEGACY and self._legacy_pricing_func is not None:
            self._endpoint_wait(ENDPOINT_PRICING)
            try:
                payload = self._legacy_pricing_func(asin, access_token)
                self._endpoint_mark(ENDPOINT_PRICING, error="" if isinstance(payload, dict) else "legacy_payload_invalid")
                if isinstance(payload, dict):
                    return payload
            except Exception:
                self._endpoint_mark(ENDPOINT_PRICING, error="legacy_pricing_exception")
                pass
            self._pricing_stats["errors_total"] = int(self._pricing_stats["errors_total"]) + 1
            return {"asin": asin, "buy_box_price": "0", "lowest_afn_price": "0", "error": "legacy_pricing_error"}
        return self._native_comp_summary_get_pricing(asin, access_token)

    def get_fees(self, asin: str, final_price: float, access_token: str) -> dict[str, Any]:
        if self._legacy_fees_func is not None:
            self._endpoint_wait(ENDPOINT_FEES)
            try:
                payload = self._legacy_fees_func(asin, final_price, access_token)
                self._endpoint_mark(ENDPOINT_FEES, error="" if isinstance(payload, dict) else "legacy_payload_invalid")
                if isinstance(payload, dict):
                    return payload
            except Exception:
                self._endpoint_mark(ENDPOINT_FEES, error="legacy_fees_exception")
                pass
            return {"asin": asin, "referral_fee": 0.0, "fba_fee": 0.0, "error": "legacy_fees_error"}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-amz-access-token": access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        body = {
            "FeesEstimateRequest": {
                "MarketplaceId": MARKETPLACE_ID_UK,
                "IsAmazonFulfilled": True,
                "PriceToEstimateFees": {
                    "ListingPrice": {"Amount": final_price, "CurrencyCode": "GBP"},
                    "Shipping": {"Amount": 0.0, "CurrencyCode": "GBP"},
                },
                "Identifier": "SellerOneLegacyFirstChecks",
            }
        }
        self._endpoint_wait(ENDPOINT_FEES)
        response = requests.post(
            f"{SPAPI_BASE_URL}/products/fees/v0/items/{asin}/feesEstimate",
            headers=headers,
            json=body,
            timeout=self._timeout_seconds,
        )
        self._endpoint_mark(
            ENDPOINT_FEES,
            status_code=int(response.status_code),
            headers=dict(getattr(response, "headers", {}) or {}),
        )
        if response.status_code != 200:
            return {"asin": asin, "referral_fee": 0.0, "fba_fee": 0.0, "error": f"http_{response.status_code}"}

        payload = response.json()
        top = payload.get("payload") if isinstance(payload, dict) else {}
        if not isinstance(top, dict):
            return {"asin": asin, "referral_fee": 0.0, "fba_fee": 0.0, "error": "missing_payload"}
        estimate = top.get("FeesEstimateResult") if isinstance(top.get("FeesEstimateResult"), dict) else {}
        details = estimate.get("FeesEstimate") if isinstance(estimate, dict) else {}
        fee_list = details.get("FeeDetailList") if isinstance(details, dict) else []
        referral_fee = 0.0
        fba_fee = 0.0
        if isinstance(fee_list, list):
            for fee_item in fee_list:
                if not isinstance(fee_item, dict):
                    continue
                fee_type = _normalize_text(fee_item.get("FeeType", ""))
                amount = _parse_float(((fee_item.get("FeeAmount") or {}).get("Amount", 0.0)))
                if fee_type == "ReferralFee":
                    referral_fee += amount
                if fee_type == "FBAFees":
                    fba_fee += amount

        return {"asin": asin, "referral_fee": round(referral_fee, 2), "fba_fee": round(fba_fee, 2)}

    def _ensure_drivers(self) -> bool:
        if self._bbp_driver is not None and self._date_driver is not None:
            return True

        # Import failures are terminal for this process; launch failures are retriable.
        if self._driver_init_error.startswith("driver_import_error:"):
            return False

        try:
            import undetected_chromedriver as uc  # type: ignore
            from selenium import webdriver  # type: ignore
            from selenium.webdriver.chrome.options import Options  # type: ignore
            from selenium.webdriver.chrome.service import Service  # type: ignore
        except Exception as exc:
            self._driver_init_error = f"driver_import_error:{type(exc).__name__}"
            return False

        profile_health = _bbp_profile_extension_health()
        logger.info(
            "F061_BBP_PROFILE_HEALTH ok=%s reason=%s user_data_dir=%s profile_dir=%s extension_id=%s manifest_count=%s",
            bool(profile_health.get("ok")),
            _normalize_text(profile_health.get("reason", "")),
            _normalize_text(profile_health.get("user_data_dir", "")),
            _normalize_text(profile_health.get("profile_dir", "")),
            _normalize_text(profile_health.get("extension_id", "")),
            _normalize_text(profile_health.get("manifest_count", "")),
        )
        if _bbp_profile_extension_required() and not bool(profile_health.get("ok")):
            self._driver_init_error = (
                "bbp_profile_extension_missing:"
                f"user_data_dir={_normalize_text(profile_health.get('user_data_dir', ''))};"
                f"profile_dir={_normalize_text(profile_health.get('profile_dir', ''))};"
                f"reason={_normalize_text(profile_health.get('reason', 'unknown'))}"
            )
            return False

        # Pre-launch cleanup to avoid stale profile/session locks from orphaned automation browsers.
        _cleanup_specialist_chrome_windows(force=_force_clean_specialist_chrome_for_visible_login())
        _clear_chrome_singleton_locks(F061_BBP_USER_DATA_DIR)
        _clear_chrome_singleton_locks(F061_DATE_USER_DATA_DIR)

        last_launch_error = ""
        bbp_chrome_exe = r"C:\Chrome_UC136\bin\chrome.exe"
        bbp_chrome_version = _file_version(bbp_chrome_exe)
        for launch_attempt in range(2):
            bbp_driver = None
            date_driver = None
            attempt_started = time.monotonic()
            try:
                logger.info(
                    "F061_DRIVER_LAUNCH_BEGIN attempt=%s chrome_exe=%s chrome_version=%s user_data_dir=%s profile_dir=%s browser_mode=%s",
                    launch_attempt + 1,
                    bbp_chrome_exe,
                    bbp_chrome_version,
                    F061_BBP_USER_DATA_DIR,
                    F061_BBP_PROFILE_DIR,
                    _background_browser_mode(),
                )
                bbp_options = uc.ChromeOptions()
                bbp_options.binary_location = bbp_chrome_exe
                bbp_options.add_argument(f"--user-data-dir={F061_BBP_USER_DATA_DIR}")
                bbp_options.add_argument(f"--profile-directory={F061_BBP_PROFILE_DIR}")
                bbp_options.add_argument("--log-level=3")
                _apply_background_browser_options(bbp_options)
                with _force_visible_bbp_chrome_startup():
                    bbp_driver = uc.Chrome(
                        options=bbp_options,
                        version_main=136,
                        driver_executable_path=r"C:\Users\Luke\.nuget\packages\selenium.webdriver.chromedriver\136.0.7103.4800-beta\driver\win32\chromedriver.exe",
                    )
                bbp_driver.set_page_load_timeout(self._scrape_page_load_timeout_seconds)
                bbp_driver.set_script_timeout(self._scrape_page_load_timeout_seconds)
                _place_browser_window(bbp_driver, visible_x=0, visible_y=0)
                logger.info(
                    "F061_BBP_DRIVER_READY attempt=%s elapsed_seconds=%.3f debugger_address=%s",
                    launch_attempt + 1,
                    time.monotonic() - attempt_started,
                    _normalize_text(
                        ((getattr(bbp_driver, "capabilities", {}) or {}).get("goog:chromeOptions", {}) or {}).get(
                            "debuggerAddress", ""
                        )
                    ),
                )

                date_started = time.monotonic()
                date_options = Options()
                date_options.binary_location = r"C:\Users\Luke\PortableApps\GoogleChromePortable\App\Chrome-bin\chrome.exe"
                # Use a dedicated automation profile to avoid collisions with any human-led Chrome session.
                date_options.add_argument(f"--user-data-dir={F061_DATE_USER_DATA_DIR}")
                date_options.add_argument(r"--profile-directory=F061Profile")
                date_options.add_argument("--log-level=3")
                _apply_background_browser_options(date_options)
                service = Service(
                    r"C:\Users\Luke\PortableApps\GoogleChromePortable\App\Chrome-bin\chromedriver.exe",
                    log_output=os.devnull,
                )
                with _force_visible_bbp_chrome_startup():
                    date_driver = webdriver.Chrome(service=service, options=date_options)
                date_driver.set_page_load_timeout(self._scrape_page_load_timeout_seconds)
                date_driver.set_script_timeout(self._scrape_page_load_timeout_seconds)
                _place_date_browser_window(date_driver)
                logger.info(
                    "F061_DATE_DRIVER_READY attempt=%s elapsed_seconds=%.3f user_data_dir=%s profile_dir=F061Profile",
                    launch_attempt + 1,
                    time.monotonic() - date_started,
                    F061_DATE_USER_DATA_DIR,
                )
            except Exception as exc:
                last_launch_error = f"driver_launch_error:{type(exc).__name__}:{_normalize_text(exc)}"
                logger.warning(
                    "F061_DRIVER_LAUNCH_FAILED attempt=%s elapsed_seconds=%.3f error=%s",
                    launch_attempt + 1,
                    time.monotonic() - attempt_started,
                    last_launch_error,
                )
                try:
                    if bbp_driver is not None:
                        bbp_driver.quit()
                except Exception:
                    pass
                try:
                    if date_driver is not None:
                        date_driver.quit()
                except Exception:
                    pass
                _cleanup_specialist_chrome_windows(force=True)
                _clear_chrome_singleton_locks(F061_BBP_USER_DATA_DIR)
                _clear_chrome_singleton_locks(F061_DATE_USER_DATA_DIR)
                if launch_attempt == 0:
                    time.sleep(2)
                    continue
                self._driver_init_error = last_launch_error
                return False

            self._bbp_driver = bbp_driver
            self._date_driver = date_driver
            self._driver_init_error = ""
            return True

        self._driver_init_error = last_launch_error or "driver_launch_error:unknown"
        return False

    def close(self) -> None:
        try:
            if self._bbp_driver is not None:
                self._bbp_driver.quit()
        except Exception:
            pass
        try:
            if self._date_driver is not None:
                self._date_driver.quit()
        except Exception:
            pass
        self._bbp_driver = None
        self._date_driver = None

    def _is_recoverable_scrape_window_error(self, *, error_text: object = "", exc: Exception | None = None) -> bool:
        parts = [_normalize_lower(error_text)]
        if exc is not None:
            parts.append(_normalize_lower(type(exc).__name__))
            parts.append(_normalize_lower(str(exc)))
        text = " ".join(part for part in parts if part)
        if text == "":
            return False
        recoverable_tokens = (
            "no such window",
            "target window already closed",
            "web view not found",
            "browsing context has been discarded",
        )
        return any(token in text for token in recoverable_tokens)

    def _driver_start_failure_response(self) -> dict[str, Any]:
        if self._driver_init_error:
            if self._driver_init_error.startswith("bbp_profile_extension_missing:"):
                return {
                    "success": False,
                    "error": f"BBP_LOGIN_REQUIRED:{self._driver_init_error}",
                    "driver_error": self._driver_init_error,
                }
            return {
                "success": False,
                "error": f"CHROMEVERSIONFAIL:{self._driver_init_error}",
                "driver_error": self._driver_init_error,
            }
        return {"success": False, "error": "CHROMEVERSIONFAIL"}

    def process_scrape(
        self,
        *,
        asin: str,
        break_even_price: float,
        min_sell_price: float,
        product_cost: float,
        row_index: int,
        brand_name: str,
        vat_rate: float,
        skip_date_scraping: bool,
        old_chrome_forced: bool,
        fba_fee: float = 0.0,
        referral_fee: float = 0.0,
        digital_fee: float = 0.0,
        est_shipping: float = 0.0,
        referral_fee_basis_price: float = 0.0,
    ) -> dict[str, Any]:
        if self._scrape_mode == "disabled":
            return {"success": False, "error": "SCRAPE_DISABLED"}
        if self._scrape_mode != "legacy_module":
            return {"success": False, "error": "SCRAPE_DISABLED"}
        if self._legacy_scrape_func is None:
            return {"success": False, "error": "SCRAPE_DISABLED"}
        if not self._ensure_drivers():
            return self._driver_start_failure_response()

        retried_window_recovery = False
        while True:
            try:
                result = self._legacy_scrape_func(
                    asin=asin,
                    break_even_price=break_even_price,
                    min_sell_price=min_sell_price,
                    product_cost=product_cost,
                    fba_fee=fba_fee,
                    referral_fee=referral_fee,
                    digital_fee=digital_fee,
                    est_shipping=est_shipping,
                    referral_fee_basis_price=referral_fee_basis_price,
                    row_index=row_index,
                    brand_name=brand_name,
                    vat_rate=vat_rate,
                    skip_date_scraping=skip_date_scraping,
                    old_chrome_forced=old_chrome_forced,
                    bbp_driver=self._bbp_driver,
                    date_driver=self._date_driver,
                )
            except Exception as exc:
                if (not retried_window_recovery) and self._is_recoverable_scrape_window_error(exc=exc):
                    retried_window_recovery = True
                    self.close()
                    if self._ensure_drivers():
                        continue
                    return self._driver_start_failure_response()
                return {"success": False, "error": f"SCRAPE_EXCEPTION:{type(exc).__name__}"}

            if not isinstance(result, dict):
                return {"success": False, "error": "SCRAPE_INVALID_RESULT"}

            if bool(result.get("success", False)):
                return result

            scrape_error = _normalize_text(result.get("error", ""))
            if (not retried_window_recovery) and self._is_recoverable_scrape_window_error(error_text=scrape_error):
                retried_window_recovery = True
                self.close()
                if self._ensure_drivers():
                    continue
                return self._driver_start_failure_response()
            return result


def _base_first_checks_row(
    active_row: pd.Series,
    existing_row: dict[str, str] | None,
    observed_utc: str,
    *,
    candidate_id: str | None = None,
) -> dict[str, str]:
    row = dict(existing_row) if existing_row else {}
    supplier_sku = _normalize_text(active_row.get("supplier_sku", ""))
    barcode = _normalize_digits(active_row.get("barcode", ""))
    unit_cost = _normalize_text(active_row.get("unit_cost", ""))
    vat = _normalize_text(active_row.get("vat_rate", ""))
    supplier_name = _normalize_text(active_row.get("supplier_name", ""))
    resolved_candidate_id = _normalize_text(candidate_id) or _row_identity(active_row)

    row.setdefault("completed", supplier_sku)
    row.setdefault("barcode", barcode)
    row.setdefault("cost", unit_cost)
    row.setdefault("vat", vat)
    row.setdefault("supplier", supplier_name)
    row.setdefault("asin", "")
    row.setdefault("main_rank", "")
    row.setdefault("start_date", "")
    row.setdefault("brand", "")
    row.setdefault("size_1", "")
    row.setdefault("size_2", "")
    row.setdefault("size_3", "")
    row.setdefault("weight", "")
    row.setdefault("dg_ok", "")
    row.setdefault("hazmat", "")
    row.setdefault("buy_box_price", "")
    row.setdefault("lowest_afn_price", "")
    row.setdefault("lowest_mfn_price", "")
    row.setdefault("reasonable_price", "")
    row.setdefault("api_live_price", "")
    row.setdefault("bbp_live_sell_price", "")
    row.setdefault("bbp_30d_avg_price", "")
    row.setdefault("fba_fee", "")
    row.setdefault("referral_fee", "")
    row.setdefault("digital_fee", "")
    row.setdefault("est_shipping", "")
    row.setdefault("vat_adjusted_price", "")
    row.setdefault("break_even", "")
    row.setdefault("min_sell_price", "")
    row.setdefault("scan_day", observed_utc)
    row.setdefault("title", _normalize_text(active_row.get("supplier_title", "")))
    row.setdefault("sales", "")
    row.setdefault("rating", "")
    row.setdefault("date", "")
    row.setdefault("variant_reviews", "")
    row.setdefault("reviews_list", "")
    row.setdefault("point_score", "")
    row.setdefault("history_score", "")
    row.setdefault("pf", "")
    row.setdefault("status_reason", "")
    row.setdefault("candidate_id", resolved_candidate_id)
    row.setdefault("supplier_sku", supplier_sku)
    row.setdefault("recommendation_status", "")
    row.setdefault("recommended_test_qty", "")

    row["completed"] = supplier_sku
    row["barcode"] = barcode
    row["cost"] = unit_cost
    row["vat"] = vat
    row["supplier"] = supplier_name
    row["title"] = _normalize_text(active_row.get("supplier_title", ""))
    row["candidate_id"] = resolved_candidate_id
    row["supplier_sku"] = supplier_sku
    row["scan_day"] = observed_utc
    return row


def _row_dict_from_df_row(row: pd.Series) -> dict[str, str]:
    return {k: _normalize_text(v) for k, v in row.to_dict().items()}


def _build_scrape_evidence_row(
    *,
    active_row: pd.Series,
    first_row: dict[str, str],
    observed_utc: str,
    scraped_data: dict[str, Any],
    scrape_success: bool,
    scrape_error: str,
) -> dict[str, str]:
    row: dict[str, str] = {
        "observed_utc": observed_utc,
        "scan_day": _normalize_text(first_row.get("scan_day", observed_utc)) or observed_utc,
        "run_id": _normalize_text(active_row.get("run_id", "")),
        "candidate_id": _normalize_text(first_row.get("candidate_id", "")),
        "supplier_id": _normalize_text(active_row.get("supplier_id", "")),
        "supplier_name": _normalize_text(active_row.get("supplier_name", "")),
        "supplier_sku": _normalize_text(first_row.get("supplier_sku", "")),
        "supplier_title": _normalize_text(active_row.get("supplier_title", "")),
        "barcode": _normalize_digits(first_row.get("barcode", "")),
        "asin": _normalize_text(first_row.get("asin", "")),
        "title": _normalize_text(first_row.get("title", "")),
        "catalog_match_scorecard": _normalize_text(first_row.get("history_score", "")),
        "first_check_status_code": "",
        "pf": _normalize_text(first_row.get("pf", "")),
        "status_reason": _normalize_text(first_row.get("status_reason", "")),
        "scrape_attempted": "True",
        "scrape_success": "True" if scrape_success else "False",
        "scrape_error": _normalize_text(scrape_error),
        "api_live_price": _normalize_text(first_row.get("api_live_price", "")),
        "bbp_live_sell_price": _normalize_text(first_row.get("bbp_live_sell_price", "")),
        "bbp_30d_avg_price": _normalize_text(first_row.get("bbp_30d_avg_price", "")),
        "break_even": _normalize_text(first_row.get("break_even", "")),
        "min_sell_price": _normalize_text(first_row.get("min_sell_price", "")),
        "checks_failed": "",
        "fail_codes": "",
        "hard_stop": "",
        "source_seen_at_utc": _normalize_text(active_row.get("source_seen_at_utc", "")),
    }
    for key in SCRAPE_EVIDENCE_SCRAPED_KEYS:
        row[key] = _normalize_text(scraped_data.get(key, ""))

    if row.get("main_title", "") == "":
        row["main_title"] = row.get("title", "")
    if row.get("scan_date", "") == "":
        row["scan_date"] = row.get("scan_day", "")
    return row


def _finalize_scrape_evidence_row(
    row: dict[str, str] | None,
    *,
    first_row: dict[str, str],
    status_code: str,
) -> dict[str, str] | None:
    if row is None:
        return None
    out = dict(row)
    out["first_check_status_code"] = _normalize_text(status_code)
    out["pf"] = _normalize_text(first_row.get("pf", ""))
    out["status_reason"] = _normalize_text(first_row.get("status_reason", ""))

    for key in ("scan_day", "title", "api_live_price", "bbp_live_sell_price", "bbp_30d_avg_price", "break_even", "min_sell_price"):
        value = _normalize_text(first_row.get(key, ""))
        if value:
            out[key] = value
    return out


PRICE_CONTEXT_COLUMNS = (
    "api_live_price",
    "bbp_live_sell_price",
    "bbp_30d_avg_price",
    "break_even",
    "min_sell_price",
)


def _login_backtrack_id(*, run_id: str, candidate_id: str, observed_utc: str, attempt_number: str) -> str:
    seed = "|".join([_normalize_text(run_id), _normalize_text(candidate_id), _normalize_text(observed_utc), _normalize_text(attempt_number)])
    return uuid.uuid5(uuid.NAMESPACE_URL, f"sellerone:f-login-backtrack:{seed}").hex


def _latest_login_backtrack_by_candidate(ledger_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if ledger_df.empty or "candidate_id" not in ledger_df.columns:
        return {}
    work = ledger_df.copy()
    if "backtrack_observed_utc" in work.columns:
        work["_sort_ts"] = pd.to_datetime(work["backtrack_observed_utc"].map(_normalize_text), errors="coerce")
        work = work.sort_values("_sort_ts", ascending=False, kind="stable").drop(columns=["_sort_ts"], errors="ignore")
    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        payload = _row_dict_from_df_row(row)
        candidate_id = _normalize_text(payload.get("candidate_id", ""))
        if candidate_id and candidate_id not in out:
            out[candidate_id] = payload
    return out


def _build_login_backtrack_ledger_row(
    *,
    active_row: pd.Series,
    first_row: dict[str, str],
    scrape_evidence_row: dict[str, str] | None,
    observed_utc: str,
    status: str,
    existing_original: dict[str, str] | None = None,
) -> dict[str, str]:
    existing = existing_original or {}
    candidate_id = _normalize_text(first_row.get("candidate_id", "")) or _row_identity(active_row)
    attempt_number = str(_parse_nonnegative_int(active_row.get("backtrack_attempt_count", "0"), default=0) + 1)
    run_id = _normalize_text(active_row.get("run_id", ""))
    scrape = scrape_evidence_row or {}
    source = scrape if scrape else first_row
    original_observed = (
        _normalize_text(existing.get("original_observed_utc", ""))
        or _normalize_text(existing.get("backtrack_observed_utc", ""))
        or _normalize_text(scrape.get("observed_utc", ""))
        or observed_utc
    )
    return {
        "backtrack_id": _login_backtrack_id(
            run_id=run_id,
            candidate_id=candidate_id,
            observed_utc=observed_utc,
            attempt_number=attempt_number,
        ),
        "backtrack_observed_utc": observed_utc,
        "original_observed_utc": original_observed,
        "original_run_id": run_id,
        "supplier_id": _normalize_text(active_row.get("supplier_id", "")),
        "supplier_name": _normalize_text(active_row.get("supplier_name", "")),
        "supplier_sku": _normalize_text(first_row.get("supplier_sku", active_row.get("supplier_sku", ""))),
        "barcode": _normalize_digits(first_row.get("barcode", active_row.get("barcode", ""))),
        "candidate_id": candidate_id,
        "asin": _normalize_text(first_row.get("asin", "")),
        "unit_cost": _normalize_text(active_row.get("unit_cost", "")),
        "api_live_price": _normalize_text(existing.get("api_live_price", "")) or _normalize_text(source.get("api_live_price", "")),
        "bbp_live_sell_price": _normalize_text(existing.get("bbp_live_sell_price", "")) or _normalize_text(source.get("bbp_live_sell_price", "")),
        "bbp_30d_avg_price": _normalize_text(existing.get("bbp_30d_avg_price", "")) or _normalize_text(source.get("bbp_30d_avg_price", "")),
        "break_even": _normalize_text(existing.get("break_even", "")) or _normalize_text(source.get("break_even", "")),
        "min_sell_price": _normalize_text(existing.get("min_sell_price", "")) or _normalize_text(source.get("min_sell_price", "")),
        "original_pf": _normalize_text(existing.get("original_pf", "")) or _normalize_text(first_row.get("pf", "")),
        "original_status_reason": _normalize_text(existing.get("original_status_reason", "")) or _normalize_text(first_row.get("status_reason", "")),
        "original_scrape_error": _normalize_text(existing.get("original_scrape_error", "")) or _normalize_text(scrape.get("scrape_error", "")),
        "backtrack_attempt_number": attempt_number,
        "backtrack_status": _normalize_text(status),
        "backtrack_error": _normalize_text(scrape.get("scrape_error", "")),
        "backtrack_bbp_dashboard_yes_or_no": _normalize_text(scrape.get("bbp_dashboard_yes_or_no", "")),
        "backtrack_bbp_dashboard_delivery_classification": _normalize_text(
            scrape.get("bbp_dashboard_delivery_classification", "")
        ),
        "backtrack_bbp_dashboard_separate_delivery_required": _normalize_text(
            scrape.get("bbp_dashboard_separate_delivery_required", "")
        ),
        "backtrack_bbp_top_seller_names": _normalize_text(scrape.get("bbp_top_seller_names", "")),
        "backtrack_bbp_top_seller_count": _normalize_text(scrape.get("bbp_top_seller_count", "")),
        "backtrack_bbp_brand_match_seller": _normalize_text(scrape.get("bbp_brand_match_seller", "")),
        "backtrack_bbp_brand_match_score": _normalize_text(scrape.get("bbp_brand_match_score", "")),
        "backtrack_bbp_brand_match_flag": _normalize_text(scrape.get("bbp_brand_match_flag", "")),
        "backtrack_profile_mode": _normalize_text(active_row.get("scan_reason", "")) or _normalize_text(active_row.get("scan_status", "")),
        "merged_into_candidate_flag": "1" if _normalize_text(status) == "merged" else "0",
        "merge_observed_utc": observed_utc if _normalize_text(status) == "merged" else "",
    }


def _restore_original_price_context(
    *,
    first_row: dict[str, str],
    scrape_evidence_row: dict[str, str] | None,
    original: dict[str, str] | None,
    backtrack_id: str,
    observed_utc: str,
) -> None:
    if not original:
        return
    for column in PRICE_CONTEXT_COLUMNS:
        value = _normalize_text(original.get(column, ""))
        if value:
            first_row[column] = value
            if scrape_evidence_row is not None:
                scrape_evidence_row[column] = value
    if scrape_evidence_row is not None:
        scrape_evidence_row["dashboard_yes_no_source"] = "login_backtrack"
        scrape_evidence_row["dashboard_yes_no_original_observed_utc"] = _normalize_text(original.get("original_observed_utc", ""))
        scrape_evidence_row["dashboard_yes_no_backtrack_observed_utc"] = observed_utc
        scrape_evidence_row["dashboard_yes_no_backtrack_id"] = backtrack_id


def _parse_day_value_series(series_text: object) -> dict[str, str]:
    text = _normalize_text(series_text)
    if text == "":
        return {}
    out: dict[str, str] = {}
    for chunk in text.split(";"):
        part = chunk.strip()
        if part == "" or "=" not in part:
            continue
        day, value = part.split("=", 1)
        day_key = _normalize_text(day)
        if day_key == "":
            continue
        out[day_key] = _normalize_text(value)
    return out


def _build_chart_daily_raw_rows(
    *,
    active_row: pd.Series,
    first_row: dict[str, str],
    scrape_evidence_row: dict[str, str],
    observed_utc: str,
    status_code: str,
) -> list[dict[str, str]]:
    amazon_map = _parse_day_value_series(scrape_evidence_row.get("chart_raw_amazon_daily_series", ""))
    fba_map = _parse_day_value_series(scrape_evidence_row.get("chart_raw_fba_daily_series", ""))
    fbm_map = _parse_day_value_series(scrape_evidence_row.get("chart_raw_fbm_daily_series", ""))
    buy_box_map = _parse_day_value_series(scrape_evidence_row.get("chart_raw_buy_box_daily_series", ""))
    bsr_map = _parse_day_value_series(scrape_evidence_row.get("chart_raw_bsr_daily_series", ""))

    if not bsr_map:
        bsr_map = _parse_day_value_series(scrape_evidence_row.get("chart_bsr_daily_series", ""))
    chosen_map = _parse_day_value_series(scrape_evidence_row.get("chart_price_daily_series", ""))
    phase_map = _parse_day_value_series(scrape_evidence_row.get("chart_phase_daily_series", ""))

    all_days = sorted(
        set(amazon_map.keys())
        | set(fba_map.keys())
        | set(fbm_map.keys())
        | set(buy_box_map.keys())
        | set(bsr_map.keys())
    )
    if not all_days:
        return []

    rows: list[dict[str, str]] = []
    for day in all_days:
        rows.append(
            {
                "observed_utc": observed_utc,
                "run_id": _normalize_text(active_row.get("run_id", "")),
                "supplier_id": _normalize_text(active_row.get("supplier_id", "")),
                "supplier_name": _normalize_text(active_row.get("supplier_name", "")),
                "supplier_sku": _normalize_text(first_row.get("supplier_sku", "")),
                "candidate_id": _normalize_text(first_row.get("candidate_id", "")),
                "asin": _normalize_text(first_row.get("asin", "")),
                "day": day,
                "chart_source": _normalize_text(scrape_evidence_row.get("history_source", "")),
                "amazon_price_raw": _normalize_text(amazon_map.get(day, "")),
                "fba_price_raw": _normalize_text(fba_map.get(day, "")),
                "fbm_price_raw": _normalize_text(fbm_map.get(day, "")),
                "buy_box_price_raw": _normalize_text(buy_box_map.get(day, "")),
                "bsr_raw": _normalize_text(bsr_map.get(day, "")),
                "barcode": _normalize_digits(first_row.get("barcode", "")),
                "title": _normalize_text(first_row.get("title", "")),
                "first_check_status_code": _normalize_text(status_code),
                "pf": _normalize_text(first_row.get("pf", "")),
                "status_reason": _normalize_text(first_row.get("status_reason", "")),
                "price_chosen_processed": _normalize_text(chosen_map.get(day, "")),
                "phase_processed": _normalize_text(phase_map.get(day, "")),
                "price_history_span_days": _normalize_text(scrape_evidence_row.get("price_history_span_days", "")),
                "history_window_days": _normalize_text(scrape_evidence_row.get("history_window_days", "")),
                "source_seen_at_utc": _normalize_text(active_row.get("source_seen_at_utc", "")),
            }
        )
    return rows


def _browser_only_missing_api_result(first_row: dict[str, str]) -> tuple[dict[str, str], str, None]:
    status_code = "RESCAN"
    first_row["pf"] = _status_to_pf(status_code)
    first_row["status_reason"] = F061_BROWSER_ONLY_MISSING_API_EVIDENCE_REASON
    return first_row, status_code, None


def _match_grade_from_first_row(first_row: dict[str, str]) -> str:
    parts = _normalize_text(first_row.get("history_score", "")).split("|")
    if len(parts) >= 2 and _normalize_text(parts[1]).upper():
        return _normalize_text(parts[1]).upper()
    return "LIKELY"


def _run_browser_stage_from_api_evidence(
    *,
    active_row: pd.Series,
    first_row: dict[str, str],
    existing_first_row: dict[str, str] | None,
    adapter: Any,
    row_index_1_based: int,
    observed_utc: str,
    mode: str,
) -> tuple[dict[str, str], str, dict[str, str] | None]:
    asin = _normalize_text(first_row.get("asin", ""))
    if asin == "":
        return _browser_only_missing_api_result(first_row)

    product_cost = _parse_positive_cost(active_row.get("unit_cost", "")) or _parse_positive_cost(first_row.get("cost", ""))
    break_even = _parse_float(first_row.get("break_even", 0.0), default=0.0)
    min_sell = _parse_float(first_row.get("min_sell_price", 0.0), default=0.0)
    fba_fee = _parse_float(first_row.get("fba_fee", 0.0), default=0.0)
    referral_fee = _parse_float(first_row.get("referral_fee", 0.0), default=0.0)
    digital_fee = _parse_float(first_row.get("digital_fee", 0.0), default=0.0)
    shipping_est = _parse_float(first_row.get("est_shipping", 0.0), default=0.0)
    final_price = _parse_float(
        first_row.get("reasonable_price", "")
        or first_row.get("api_live_price", "")
        or first_row.get("buy_box_price", "")
        or first_row.get("lowest_afn_price", ""),
        default=0.0,
    )
    if product_cost is None or break_even <= 0 or min_sell <= 0:
        return _browser_only_missing_api_result(first_row)

    vat_pct = _parse_float(active_row.get("vat_rate", "0"), default=0.0)
    brand_name = _normalize_text(first_row.get("brand", "")) or "Unknown"
    amazon_title = _normalize_text(first_row.get("title", ""))
    match_grade = _match_grade_from_first_row(first_row)
    current_start_date = _normalize_text(first_row.get("start_date", ""))
    skip_date_scraping = current_start_date not in {"", "N/A", "n/a"}
    prior_points = _parse_float((existing_first_row or {}).get("point_score", "0"), default=0.0)
    old_chrome_forced = prior_points >= 2.5
    roi_gate_override = _normalize_lower(mode) == F061_MODE_DATA_COLLECTION and min_sell > final_price and final_price > 0

    scraped = _call_adapter_process_scrape(
        adapter,
        asin=asin,
        break_even_price=break_even,
        min_sell_price=min_sell,
        product_cost=product_cost,
        fba_fee=fba_fee,
        referral_fee=referral_fee,
        digital_fee=digital_fee,
        est_shipping=shipping_est,
        referral_fee_basis_price=final_price,
        row_index=row_index_1_based,
        brand_name=brand_name,
        vat_rate=vat_pct,
        skip_date_scraping=skip_date_scraping,
        old_chrome_forced=old_chrome_forced,
    )
    if not isinstance(scraped, dict):
        scraped = {"success": False, "error": "SCRAPEFAIL"}

    scraped_data = scraped.get("scraped_data")
    if not isinstance(scraped_data, dict):
        scraped_data = {}
    if skip_date_scraping:
        scraped_data["product_info"] = current_start_date
    scrape_evidence_base = _build_scrape_evidence_row(
        active_row=active_row,
        first_row=first_row,
        observed_utc=observed_utc,
        scraped_data=scraped_data,
        scrape_success=bool(scraped.get("success")),
        scrape_error=_normalize_text(scraped.get("error", "")),
    )

    if bool(scraped.get("success")):
        updated_break_even = _parse_float(scraped_data.get("updated_break_even", 0.0), default=0.0)
        if updated_break_even > 0:
            break_even = round(updated_break_even, 2)
            first_row["break_even"] = _format_float(break_even, 2)
            min_sell = round(break_even * 1.20, 2)
            first_row["min_sell_price"] = _format_float(min_sell, 2)

        final_date = _normalize_text(scraped_data.get("product_info", "N/A")) or "N/A"
        first_row["scan_day"] = _normalize_text(scraped_data.get("scan_date", observed_utc)) or observed_utc
        first_row["title"] = _normalize_text(scraped_data.get("main_title", amazon_title or first_row.get("title", "")))
        first_row["sales"] = _normalize_text(scraped_data.get("monthly_sold", ""))
        first_row["rating"] = _normalize_text(scraped_data.get("rating", ""))
        first_row["date"] = final_date
        first_row["variant_reviews"] = _normalize_text(scraped_data.get("variant_reviews", ""))
        first_row["reviews_list"] = _normalize_text(scraped_data.get("reviews_text", ""))
        bbp_live_sell_price = _normalize_text(
            scraped_data.get("bbp_final_sell_price", "")
            or scraped_data.get("bbp_auto_sell_price", "")
        )
        if bbp_live_sell_price:
            first_row["bbp_live_sell_price"] = bbp_live_sell_price
        first_row["bbp_30d_avg_price"] = _normalize_text(scraped_data.get("avg_30_day_price", ""))

        incomplete_capture_reason = _missing_core_price_history_reason(scraped_data)
        if incomplete_capture_reason:
            status_code = "RESCAN"
            first_row["pf"] = _status_to_pf(status_code)
            first_row["status_reason"] = status_code if match_grade in {"EXACT", "LIKELY"} else f"{status_code}|MATCH_{match_grade}"
            incomplete_row = _finalize_scrape_evidence_row(
                scrape_evidence_base,
                first_row=first_row,
                status_code=status_code,
            )
            if incomplete_row is not None:
                incomplete_row["scrape_success"] = "False"
                incomplete_row["scrape_error"] = incomplete_capture_reason
            return first_row, status_code, incomplete_row

        if _normalize_lower(final_date) == "n/a":
            status_code = "NODATE"
            first_row["pf"] = _status_to_pf(status_code)
            first_row["status_reason"] = status_code
            return first_row, status_code, _finalize_scrape_evidence_row(
                scrape_evidence_base,
                first_row=first_row,
                status_code=status_code,
            )

        point_score = _compute_point_score(
            date_value=final_date,
            rating_value=first_row.get("rating", ""),
            variant_reviews_value=first_row.get("variant_reviews", ""),
            reviews_list_value=first_row.get("reviews_list", ""),
        )
        first_row["point_score"] = _format_float(point_score, 2)
        status_code = "PASS" if point_score >= 3.5 else "FAIL"
        if roi_gate_override:
            status_code = "ROIFAIL"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code if match_grade in {"EXACT", "LIKELY"} else f"{status_code}|MATCH_{match_grade}"
        return first_row, status_code, _finalize_scrape_evidence_row(
            scrape_evidence_base,
            first_row=first_row,
            status_code=status_code,
        )

    status_code = _map_scrape_error_to_status(scraped.get("error", "SCRAPEFAIL"))
    first_row["pf"] = _status_to_pf(status_code)
    first_row["status_reason"] = status_code if match_grade in {"EXACT", "LIKELY"} else f"{status_code}|MATCH_{match_grade}"
    scrape_fail_row = _finalize_scrape_evidence_row(
        scrape_evidence_base,
        first_row=first_row,
        status_code=status_code,
    )
    if _scrape_evidence_needs_login_backtrack(scrape_fail_row):
        status_code = F061_LOGIN_BACKTRACK_STATUS_CODE
        first_row["pf"] = ""
        first_row["status_reason"] = F061_LOGIN_BACKTRACK_REASON
        if scrape_fail_row is not None:
            scrape_fail_row["first_check_status_code"] = status_code
            scrape_fail_row["pf"] = ""
            scrape_fail_row["status_reason"] = F061_LOGIN_BACKTRACK_REASON
            scrape_fail_row["dashboard_yes_no_source"] = "login_backtrack_pending"
    return first_row, status_code, scrape_fail_row


def _process_single_row(
    *,
    active_row: pd.Series,
    existing_first_row: dict[str, str] | None,
    adapter: Any,
    access_token: str,
    row_index_1_based: int,
    observed_utc: str,
    pricing_min_interval_seconds: float,
    row_runtime: dict[str, Any] | None = None,
    catalog_details: dict[str, Any] | None = None,
    candidate_id: str | None = None,
    mode: str = F061_MODE_SCREENING,
    stage_mode: str = F061_STAGE_MODE_LEGACY_FULL,
    api_cache_dir: Path | None = None,
) -> tuple[dict[str, str], str, dict[str, str] | None]:
    first_row = _base_first_checks_row(active_row, existing_first_row, observed_utc, candidate_id=candidate_id)
    effective_stage_mode = _stage_mode_from_value(stage_mode)
    if effective_stage_mode == F061_STAGE_MODE_BROWSER_ONLY:
        return _run_browser_stage_from_api_evidence(
            active_row=active_row,
            first_row=first_row,
            existing_first_row=existing_first_row,
            adapter=adapter,
            row_index_1_based=row_index_1_based,
            observed_utc=observed_utc,
            mode=mode,
        )
    barcode = _normalize_digits(active_row.get("barcode", ""))
    supplier_title = _normalize_text(active_row.get("supplier_title", ""))
    if barcode == "":
        status_code = "NOASIN"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code
        return first_row, status_code, None

    details = catalog_details if isinstance(catalog_details, dict) else adapter.get_catalog_details(barcode, access_token)
    if not isinstance(details, dict):
        status_code = "NOASIN"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code
        return first_row, status_code, None
    catalog_error = _normalize_lower(details.get("error", ""))
    if catalog_error == "http_429" or catalog_error.startswith("request_exception:") or catalog_error.startswith("http_5"):
        status_code = "RESCAN"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code
        return first_row, status_code, None

    asin = _normalize_text(details.get("asin", ""))
    if asin == "":
        status_code = "NOASIN"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code
        return first_row, status_code, None

    rank_raw = details.get("rank", "")
    rank_val = _parse_optional_float(rank_raw)
    rank = int(rank_val) if rank_val is not None else -1
    brand_name = _normalize_text(details.get("brand", "Unknown")) or "Unknown"
    amazon_title = _normalize_text(details.get("title", ""))
    release_date = _normalize_text(details.get("release_date", "N/A")) or "N/A"
    dims = details.get("dimensions", {})
    if not isinstance(dims, dict):
        dims = {}

    def _mm(path: tuple[str, str]) -> int:
        unit_obj = dims.get(path[0], {}) if isinstance(dims.get(path[0], {}), dict) else {}
        inches = _parse_float(unit_obj.get(path[1], 0.0))
        return round(inches * 25.4)

    height = _mm(("height", "value"))
    width = _mm(("width", "value"))
    length = _mm(("length", "value"))

    weight_lbs = _parse_float(details.get("weight", 0.0))
    weight_grams = round(weight_lbs * 453.592, 2) if weight_lbs > 0 else 0.0

    first_row["asin"] = asin
    first_row["main_rank"] = str(rank) if rank > 0 else _normalize_text(rank_raw)
    first_row["start_date"] = release_date
    first_row["brand"] = brand_name
    match_metadata = _extract_match_metadata(details, supplier_title, barcode)
    match_score = int(match_metadata["score"])
    match_grade = str(match_metadata["grade"])
    match_reasons = str(match_metadata["reasons"])
    first_row["history_score"] = f"{match_score}|{match_grade}|{match_reasons}"
    if match_grade in {"WEAK", "VERY_WEAK"}:
        first_row["status_reason"] = f"MATCH_{match_grade}"
    first_row["size_1"] = str(height) if height > 0 else ""
    first_row["size_2"] = str(width) if width > 0 else ""
    first_row["size_3"] = str(length) if length > 0 else ""
    first_row["weight"] = _format_float(weight_grams, 2) if weight_grams > 0 else ""

    if rank <= 0 or rank > 50000:
        status_code = "OVER50K"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code
        return first_row, status_code, None

    hazmat = _cached_api_call(
        api_cache_dir,
        endpoint=ENDPOINT_HAZMAT,
        key=asin,
        call=lambda: adapter.check_hazmat(asin, access_token),
    )
    if not isinstance(hazmat, dict) or not bool(hazmat.get("eligible")):
        status_code = "HAZMATFAIL"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code
        return first_row, status_code, None

    first_row["hazmat"] = "Yes"
    first_row["dg_ok"] = "Yes"

    product_cost = _parse_positive_cost(active_row.get("unit_cost", ""))
    if product_cost is None:
        status_code = "NOCOST"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code
        return first_row, status_code, None

    vat_pct = _parse_float(active_row.get("vat_rate", "0"), default=0.0)
    vat_dec = vat_pct / 100.0

    pricing = _cached_api_call(
        api_cache_dir,
        endpoint=ENDPOINT_PRICING,
        key=asin,
        call=lambda: adapter.get_pricing(asin, access_token),
    )
    if not isinstance(pricing, dict):
        pricing = {}
    buy_box = _parse_float(pricing.get("buy_box_price", 0.0), default=0.0)
    lowest_afn = _parse_float(pricing.get("lowest_afn_price", 0.0), default=0.0)
    final_price = max(buy_box, lowest_afn, 0.0)

    first_row["buy_box_price"] = _format_float(buy_box, 2) if buy_box > 0 else "0.00"
    first_row["lowest_afn_price"] = _format_float(lowest_afn, 2) if lowest_afn > 0 else "0.00"
    first_row["reasonable_price"] = _format_float(final_price, 2) if final_price > 0 else "0.00"
    first_row["api_live_price"] = first_row["reasonable_price"]

    fee_payload: dict[str, Any] = {}
    for attempt in range(3):
        candidate = _cached_api_call(
            api_cache_dir,
            endpoint=ENDPOINT_FEES,
            key=f"{asin}|{final_price:.2f}",
            call=lambda: adapter.get_fees(asin, final_price, access_token),
        )
        if isinstance(candidate, dict):
            fee_payload = candidate
            if _normalize_text(candidate.get("error", "")) == "":
                break
        else:
            fee_payload = {}
        if attempt < 2:
            time.sleep(1)

    referral_fee = round(_parse_float(fee_payload.get("referral_fee", 0.0), default=0.0), 2)
    fba_fee = round(_parse_float(fee_payload.get("fba_fee", 0.0), default=0.0), 2)
    ref_pct = round((referral_fee / final_price) * 100.0, 0) if final_price > 0 else 0.0
    digital_fee = round((fba_fee + referral_fee) * 0.02, 2)
    shipping_est = round(weight_grams * 0.0002045, 2) if weight_grams > 0 else 0.0

    vat_adjusted = round(buy_box / (1.0 + vat_dec), 2) if buy_box > 0 else 0.0
    total_costs = round(product_cost + fba_fee + digital_fee + shipping_est, 2) * 1.03
    break_even = round((total_costs * (1.0 + vat_dec)) * (1.0 + (ref_pct / 100.0)), 2)
    min_sell = round(break_even * 1.20, 2)

    first_row["fba_fee"] = _format_float(fba_fee, 2)
    first_row["referral_fee"] = _format_float(referral_fee, 2)
    first_row["digital_fee"] = _format_float(digital_fee, 2)
    first_row["est_shipping"] = _format_float(shipping_est, 2)
    first_row["vat_adjusted_price"] = _format_float(vat_adjusted, 2)
    first_row["break_even"] = _format_float(break_even, 2)
    first_row["min_sell_price"] = _format_float(min_sell, 2)

    roi_gate_failed = min_sell > final_price and final_price > 0
    roi_gate_override = roi_gate_failed and _normalize_lower(mode) == F061_MODE_DATA_COLLECTION
    if roi_gate_failed and not roi_gate_override:
        status_code = "ROIFAIL"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code
        return first_row, status_code, None

    if effective_stage_mode == F061_STAGE_MODE_API_ONLY:
        status_code = F061_STATUS_BROWSER_READY
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = F061_BROWSER_STAGE_READY_REASON
        return first_row, status_code, None

    current_start_date = _normalize_text(first_row.get("start_date", ""))
    skip_date_scraping = current_start_date not in {"", "N/A", "n/a"}
    prior_points = _parse_float((existing_first_row or {}).get("point_score", "0"), default=0.0)
    old_chrome_forced = prior_points >= 2.5

    scraped = _call_adapter_process_scrape(
        adapter,
        asin=asin,
        break_even_price=break_even,
        min_sell_price=min_sell,
        product_cost=product_cost,
        fba_fee=fba_fee,
        referral_fee=referral_fee,
        digital_fee=digital_fee,
        est_shipping=shipping_est,
        referral_fee_basis_price=final_price,
        row_index=row_index_1_based,
        brand_name=brand_name,
        vat_rate=vat_pct,
        skip_date_scraping=skip_date_scraping,
        old_chrome_forced=old_chrome_forced,
    )
    if not isinstance(scraped, dict):
        scraped = {"success": False, "error": "SCRAPEFAIL"}

    scraped_data = scraped.get("scraped_data")
    if not isinstance(scraped_data, dict):
        scraped_data = {}
    if skip_date_scraping:
        scraped_data["product_info"] = current_start_date
    scrape_evidence_base = _build_scrape_evidence_row(
        active_row=active_row,
        first_row=first_row,
        observed_utc=observed_utc,
        scraped_data=scraped_data,
        scrape_success=bool(scraped.get("success")),
        scrape_error=_normalize_text(scraped.get("error", "")),
    )

    if bool(scraped.get("success")):

        updated_break_even = _parse_float(scraped_data.get("updated_break_even", 0.0), default=0.0)
        if updated_break_even > 0:
            break_even = round(updated_break_even, 2)
            first_row["break_even"] = _format_float(break_even, 2)
            min_sell = round(break_even * 1.20, 2)
            first_row["min_sell_price"] = _format_float(min_sell, 2)

        final_date = _normalize_text(scraped_data.get("product_info", "N/A")) or "N/A"
        first_row["scan_day"] = _normalize_text(scraped_data.get("scan_date", observed_utc)) or observed_utc
        first_row["title"] = _normalize_text(scraped_data.get("main_title", amazon_title or first_row.get("title", "")))
        first_row["sales"] = _normalize_text(scraped_data.get("monthly_sold", ""))
        first_row["rating"] = _normalize_text(scraped_data.get("rating", ""))
        first_row["date"] = final_date
        first_row["variant_reviews"] = _normalize_text(scraped_data.get("variant_reviews", ""))
        first_row["reviews_list"] = _normalize_text(scraped_data.get("reviews_text", ""))
        bbp_live_sell_price = _normalize_text(
            scraped_data.get("bbp_final_sell_price", "")
            or scraped_data.get("bbp_auto_sell_price", "")
        )
        if bbp_live_sell_price:
            first_row["bbp_live_sell_price"] = bbp_live_sell_price
        first_row["bbp_30d_avg_price"] = _normalize_text(scraped_data.get("avg_30_day_price", ""))

        incomplete_capture_reason = _missing_core_price_history_reason(scraped_data)
        if incomplete_capture_reason:
            status_code = "RESCAN"
            first_row["pf"] = _status_to_pf(status_code)
            first_row["status_reason"] = status_code if match_grade in {"EXACT", "LIKELY"} else f"{status_code}|MATCH_{match_grade}"
            incomplete_row = _finalize_scrape_evidence_row(
                scrape_evidence_base,
                first_row=first_row,
                status_code=status_code,
            )
            if incomplete_row is not None:
                incomplete_row["scrape_success"] = "False"
                incomplete_row["scrape_error"] = incomplete_capture_reason
            return first_row, status_code, incomplete_row

        if _normalize_lower(final_date) == "n/a":
            status_code = "NODATE"
            first_row["pf"] = _status_to_pf(status_code)
            first_row["status_reason"] = status_code
            return first_row, status_code, _finalize_scrape_evidence_row(
                scrape_evidence_base,
                first_row=first_row,
                status_code=status_code,
            )

        point_score = _compute_point_score(
            date_value=final_date,
            rating_value=first_row.get("rating", ""),
            variant_reviews_value=first_row.get("variant_reviews", ""),
            reviews_list_value=first_row.get("reviews_list", ""),
        )
        first_row["point_score"] = _format_float(point_score, 2)
        status_code = "PASS" if point_score >= 3.5 else "FAIL"
        if roi_gate_override:
            status_code = "ROIFAIL"
        first_row["pf"] = _status_to_pf(status_code)
        first_row["status_reason"] = status_code if match_grade in {"EXACT", "LIKELY"} else f"{status_code}|MATCH_{match_grade}"
        return first_row, status_code, _finalize_scrape_evidence_row(
            scrape_evidence_base,
            first_row=first_row,
            status_code=status_code,
        )

    status_code = _map_scrape_error_to_status(scraped.get("error", "SCRAPEFAIL"))
    first_row["pf"] = _status_to_pf(status_code)
    first_row["status_reason"] = status_code if match_grade in {"EXACT", "LIKELY"} else f"{status_code}|MATCH_{match_grade}"
    scrape_fail_row = _finalize_scrape_evidence_row(
        scrape_evidence_base,
        first_row=first_row,
        status_code=status_code,
    )
    if _scrape_evidence_needs_login_backtrack(scrape_fail_row):
        status_code = F061_LOGIN_BACKTRACK_STATUS_CODE
        first_row["pf"] = ""
        first_row["status_reason"] = F061_LOGIN_BACKTRACK_REASON
        if scrape_fail_row is not None:
            scrape_fail_row["first_check_status_code"] = status_code
            scrape_fail_row["pf"] = ""
            scrape_fail_row["status_reason"] = F061_LOGIN_BACKTRACK_REASON
            scrape_fail_row["dashboard_yes_no_source"] = "login_backtrack_pending"
    return first_row, status_code, scrape_fail_row


def _build_run_state_row(
    *,
    supplier_queue_rows: pd.DataFrame,
    previous_row: dict[str, str],
    observed_utc: str,
    processed_rows: int,
    failed_rows_delta: int,
) -> dict[str, str]:
    pending_rows = int(len(supplier_queue_rows))
    prev_done_rows = _parse_nonnegative_int(previous_row.get("done_rows", "0"))
    prev_failed_rows = _parse_nonnegative_int(previous_row.get("failed_rows", "0"))
    prev_total_rows = _parse_nonnegative_int(previous_row.get("total_rows", "0"))

    done_rows = prev_done_rows + max(processed_rows, 0)
    failed_rows = prev_failed_rows + max(failed_rows_delta, 0)
    total_rows = max(prev_total_rows, done_rows + pending_rows)
    next_row_index = "1" if pending_rows > 0 else "0"

    run_status = "running" if pending_rows > 0 else "completed"
    completed_at = "" if run_status == "running" else observed_utc

    return {
        "supplier_id": _normalize_text(previous_row.get("supplier_id", "")),
        "supplier_name": _normalize_text(previous_row.get("supplier_name", "")),
        "run_id": _normalize_text(previous_row.get("run_id", "")),
        "run_status": run_status,
        "source_url": _normalize_text(previous_row.get("source_url", "")),
        "source_file_path": _normalize_text(previous_row.get("source_file_path", "")),
        "source_seen_at_utc": _normalize_text(previous_row.get("source_seen_at_utc", "")),
        "normalized_utc": _normalize_text(previous_row.get("normalized_utc", "")),
        "total_rows": str(total_rows),
        "pending_rows": str(pending_rows),
        "done_rows": str(done_rows),
        "failed_rows": str(failed_rows),
        "held_rows": _normalize_text(previous_row.get("held_rows", "0")) or "0",
        "next_row_index": next_row_index,
        "updated_at_utc": observed_utc,
        "completed_at_utc": completed_at,
    }


def _upsert_by_supplier(df: pd.DataFrame, supplier_id: str, new_df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return new_df.copy()
    if "supplier_id" not in df.columns:
        return new_df.copy()
    keep = df[df["supplier_id"].map(_normalize_lower) != _normalize_lower(supplier_id)].copy()
    if new_df.empty:
        return keep
    return pd.concat([keep, new_df], ignore_index=True)


def run_legacy_first_checks_local(
    root: Path | None = None,
    *,
    supplier_id: str,
    max_rows: int = 100,
    scan_utc: str | None = None,
    scrape_mode: str = "legacy_module",
    legacy_scanner_root: str | None = None,
    price_source: str | None = None,
    pricing_min_interval_seconds: float | None = None,
    catalog_max_candidates: int | None = None,
    adapter: Any | None = None,
    allowlist_path: str | Path | None = None,
    stage_mode: str | None = None,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed_utc = scan_utc or _utc_now_iso()
    supplier_key = _normalize_lower(supplier_id)
    if supplier_key == "":
        raise ValueError("supplier_id is required")
    requested_price_source = _normalize_lower(
        price_source if price_source is not None else os.environ.get(F061_PRICE_SOURCE_ENV, PRICE_SOURCE_LEGACY)
    )
    if requested_price_source not in PRICE_SOURCE_ALLOWED:
        raise ValueError(
            f"unsupported price_source '{requested_price_source}', expected one of: {','.join(sorted(PRICE_SOURCE_ALLOWED))}"
        )
    effective_pricing_min_interval = (
        _parse_positive_float(
            pricing_min_interval_seconds,
            default=_parse_positive_float(os.environ.get(F061_PRICING_MIN_INTERVAL_SECONDS_ENV, "30"), default=30.0),
        )
        if pricing_min_interval_seconds is not None
        else _parse_positive_float(os.environ.get(F061_PRICING_MIN_INTERVAL_SECONDS_ENV, "30"), default=30.0)
    )
    effective_catalog_min_interval = _parse_positive_float(
        os.environ.get(F061_CATALOG_MIN_INTERVAL_SECONDS_ENV, "0.5"),
        default=0.5,
    )
    effective_hazmat_min_interval = _parse_positive_float(
        os.environ.get(F061_HAZMAT_MIN_INTERVAL_SECONDS_ENV, "1.0"),
        default=1.0,
    )
    effective_fees_min_interval = _parse_positive_float(
        os.environ.get(F061_FEES_MIN_INTERVAL_SECONDS_ENV, "1.0"),
        default=1.0,
    )
    effective_scrape_page_load_timeout = _parse_positive_float(
        os.environ.get(F061_SCRAPE_PAGE_LOAD_TIMEOUT_SECONDS_ENV, "45"),
        default=45.0,
    )
    effective_catalog_max_candidates = (
        max(_parse_nonnegative_int(catalog_max_candidates, default=3), 1)
        if catalog_max_candidates is not None
        else max(_parse_nonnegative_int(os.environ.get(F061_CATALOG_MAX_CANDIDATES_ENV, "3"), default=3), 1)
    )
    requested_mode = _normalize_lower(os.environ.get(F061_MODE_ENV, F061_MODE_SCREENING))
    if requested_mode not in F061_MODE_ALLOWED:
        requested_mode = F061_MODE_SCREENING
    requested_stage_mode = _stage_mode_from_value(
        stage_mode if stage_mode is not None else os.environ.get(F061_STAGE_MODE_ENV, F061_STAGE_MODE_LEGACY_FULL)
    )
    login_mode_active = _truthy_env(F061_LOGIN_MODE_ENV)
    login_mode_hold_seconds = _parse_positive_float(
        os.environ.get(F061_LOGIN_HOLD_SECONDS_ENV, "60"),
        default=60.0,
    )
    allowlist_path_text = _normalize_text(allowlist_path) or _normalize_text(os.environ.get(F061_ALLOWLIST_PATH_ENV, ""))
    allowlist_ids: set[str] = set()
    allowlist_status = "not_configured"
    allowlist_notes = ""
    if allowlist_path_text:
        try:
            allowlist_ids = _read_allowlist_ids(Path(allowlist_path_text))
            if not allowlist_ids:
                raise ValueError("allowlist_empty")
            allowlist_status = "loaded"
            allowlist_notes = f"allowlist_rows={len(allowlist_ids)}"
        except Exception as exc:
            allowlist_status = "blocked"
            allowlist_notes = f"allowlist_not_ready={type(exc).__name__}:{_normalize_text(exc)}"
    if (
        requested_stage_mode == F061_STAGE_MODE_BROWSER_ONLY
        and not login_mode_active
        and allowlist_status == "not_configured"
    ):
        allowlist_status = "blocked"
        allowlist_notes = "browser_only_requires_allowlist"

    active_df = _read_contract_df("supplier_price_list_active_run", root_path)
    run_state_df = _read_contract_df("supplier_price_list_run_state", root_path)
    first_checks_df = _read_contract_df("feeder_legacy_first_checks_live", root_path)
    scrape_evidence_df = _read_contract_df("feeder_legacy_scrape_evidence_live", root_path)
    login_backtrack_df = _read_contract_df("f_login_backtrack_evidence_live", root_path)
    chart_daily_raw_df = _read_contract_df("feeder_legacy_chart_daily_raw_live", root_path)
    screening_row_state_df = _read_contract_df("f_screening_row_state_live", root_path)
    speed_ledger_df = _read_contract_df("f_scanner_speed_ledger_live", root_path)
    timeout_policy_df = read_timeout_policy_df(root=root_path, create_if_missing=True, observed_utc=observed_utc)

    if allowlist_status == "blocked":
        health_rows = [
            {
                "check": "feeder_legacy_first_checks_source_contract",
                "status": "ok",
                "value": str(len(active_df.index)),
                "notes": "active_run_contract_valid",
                "observed_utc": observed_utc,
                "source_path": str(root_path / get_f_output_contract("supplier_price_list_active_run").rel_path),
            },
            {
                "check": "feeder_legacy_first_checks_runtime",
                "status": "warn",
                "value": "0",
                "notes": allowlist_notes,
                "observed_utc": observed_utc,
                "source_path": allowlist_path_text,
            },
            {
                "check": "feeder_legacy_scrape_evidence_runtime",
                "status": "warn",
                "value": "0",
                "notes": "run_blocked_before_scan",
                "observed_utc": observed_utc,
                "source_path": str(root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path),
            },
            *build_timeout_policy_health_rows(
                root=root_path,
                screening_state_df=screening_row_state_df,
                observed_utc=observed_utc,
            ),
        ]
        _write_contract_df(pd.DataFrame(health_rows), "feeder_legacy_sheet_health", root_path)
        summary = {
            "status": "blocked",
            "supplier_id": supplier_id,
            "stage_mode": requested_stage_mode,
            "processed_rows": 0,
            "pending_rows": 0,
            "pass_rows": 0,
            "fail_rows": 0,
            "retry_rows": 0,
            "allowlist_status": allowlist_status,
            "allowlist_path": allowlist_path_text,
            "notes": allowlist_notes,
        }
        print(summary)
        return summary

    if active_df.empty:
        health_rows = [
            {
                "check": "feeder_legacy_first_checks_source_contract",
                "status": "warn",
                "value": "0",
                "notes": "supplier_price_list_active_run_missing_or_empty",
                "observed_utc": observed_utc,
                "source_path": str(root_path / get_f_output_contract("supplier_price_list_active_run").rel_path),
            },
            {
                "check": "feeder_legacy_first_checks_runtime",
                "status": "warn",
                "value": "0",
                "notes": "no_rows_processed",
                "observed_utc": observed_utc,
                "source_path": "",
            },
            {
                "check": "feeder_legacy_first_checks_pass_balance",
                "status": "warn",
                "value": "0",
                "notes": "no_supplier_rows",
                "observed_utc": observed_utc,
                "source_path": "",
            },
            {
                "check": "feeder_legacy_scrape_evidence_runtime",
                "status": "warn",
                "value": "0",
                "notes": "no_rows_processed",
                "observed_utc": observed_utc,
                "source_path": str(root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path),
            },
            {
                "check": "feeder_legacy_chart_daily_raw_runtime",
                "status": "warn",
                "value": "0",
                "notes": "no_rows_processed",
                "observed_utc": observed_utc,
                "source_path": str(root_path / get_f_output_contract("feeder_legacy_chart_daily_raw_live").rel_path),
            },
            *build_timeout_policy_health_rows(
                root=root_path,
                screening_state_df=screening_row_state_df,
                observed_utc=observed_utc,
            ),
        ]
        _write_contract_df(pd.DataFrame(health_rows), "feeder_legacy_sheet_health", root_path)
        summary = {
            "status": "success",
            "supplier_id": supplier_id,
            "processed_rows": 0,
            "pending_rows": 0,
            "pass_rows": 0,
            "fail_rows": 0,
            "retry_rows": 0,
            "notes": "active run missing or empty",
        }
        print(summary)
        return summary

    active_work = active_df.copy()
    supplier_mask = active_work["supplier_id"].map(_normalize_lower) == supplier_key
    supplier_rows_all = active_work[supplier_mask].copy().reset_index(drop=False)
    if supplier_rows_all.empty:
        health_rows = [
            {
                "check": "feeder_legacy_first_checks_source_contract",
                "status": "warn",
                "value": "0",
                "notes": "supplier_not_present_in_active_run",
                "observed_utc": observed_utc,
                "source_path": str(root_path / get_f_output_contract("supplier_price_list_active_run").rel_path),
            },
            {
                "check": "feeder_legacy_first_checks_runtime",
                "status": "warn",
                "value": "0",
                "notes": "no_rows_processed",
                "observed_utc": observed_utc,
                "source_path": "",
            },
            {
                "check": "feeder_legacy_first_checks_pass_balance",
                "status": "warn",
                "value": "0",
                "notes": "no_supplier_rows",
                "observed_utc": observed_utc,
                "source_path": "",
            },
            {
                "check": "feeder_legacy_scrape_evidence_runtime",
                "status": "warn",
                "value": "0",
                "notes": "no_rows_processed",
                "observed_utc": observed_utc,
                "source_path": str(root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path),
            },
            {
                "check": "feeder_legacy_chart_daily_raw_runtime",
                "status": "warn",
                "value": "0",
                "notes": "no_rows_processed",
                "observed_utc": observed_utc,
                "source_path": str(root_path / get_f_output_contract("feeder_legacy_chart_daily_raw_live").rel_path),
            },
            *build_timeout_policy_health_rows(
                root=root_path,
                screening_state_df=screening_row_state_df,
                observed_utc=observed_utc,
            ),
        ]
        _write_contract_df(pd.DataFrame(health_rows), "feeder_legacy_sheet_health", root_path)
        summary = {
            "status": "success",
            "supplier_id": supplier_id,
            "processed_rows": 0,
            "pending_rows": 0,
            "pass_rows": 0,
            "fail_rows": 0,
            "retry_rows": 0,
            "notes": "supplier not found in active run",
        }
        print(summary)
        return summary

    queue_status = supplier_rows_all["scan_status"].map(_normalize_lower)
    supplier_queue_all = supplier_rows_all[
        queue_status.isin(
            [
                F061_SCAN_STATUS_LOGIN_BACKTRACK_PENDING,
                F061_SCAN_STATUS_LOGIN_BACKTRACK_RUNNING,
                F061_SCAN_STATUS_PENDING,
            ]
        )
    ].copy()
    if not supplier_queue_all.empty:
        supplier_queue_all["_queue_priority"] = supplier_queue_all.apply(
            lambda row: str(_f061_row_queue_priority(row, login_mode_active=login_mode_active)),
            axis=1,
        )
        supplier_queue_all = supplier_queue_all.sort_values(
            by=["_queue_priority", "last_attempt_utc", "supplier_sku", "row_key"],
            ascending=[True, True, True, True],
            kind="stable",
        ).drop(columns=["_queue_priority"], errors="ignore")
    login_backtrack_waiting_rows = _count_login_backtrack_rows(supplier_queue_all)
    login_mode_bbp_backtrack_waiting_rows = _count_login_backtrack_rows(supplier_queue_all, bbp_only=True)
    supplier_queue_for_run = supplier_queue_all
    if not login_mode_active and login_backtrack_waiting_rows > 0:
        normal_queue = supplier_queue_all[
            supplier_queue_all.apply(lambda row: active_row_queue_state(_row_dict_from_df_row(row)) == ROW_QUEUE_PENDING, axis=1)
        ].copy()
        supplier_queue_for_run = normal_queue
    if requested_stage_mode == F061_STAGE_MODE_API_ONLY and not supplier_queue_for_run.empty:
        supplier_queue_for_run = supplier_queue_for_run[
            ~supplier_queue_for_run.apply(lambda row: _row_is_browser_stage_ready(row), axis=1)
        ].copy()
    elif requested_stage_mode == F061_STAGE_MODE_BROWSER_ONLY and not login_mode_active and not supplier_queue_for_run.empty:
        supplier_queue_for_run = supplier_queue_for_run[
            supplier_queue_for_run.apply(lambda row: _row_is_browser_stage_ready(row), axis=1)
        ].copy()
    allowlist_selected_rows = 0
    if allowlist_status == "loaded" and not login_mode_active:
        supplier_queue_for_run = supplier_queue_for_run[
            supplier_queue_for_run.apply(lambda row: _row_allowlist_identity(row) in allowlist_ids, axis=1)
        ].copy()
        allowlist_selected_rows = int(len(supplier_queue_for_run.index))
    elif allowlist_status == "loaded" and login_mode_active:
        allowlist_status = "bypassed_login_mode"
        allowlist_notes = f"{allowlist_notes};login_mode_bypass=1"
    pending_rows = supplier_queue_for_run.head(max(max_rows, 0))
    processed_target = int(len(pending_rows))
    login_mode_selected_rows = _count_login_backtrack_rows(pending_rows)
    login_mode_bbp_selected_rows = _count_login_backtrack_rows(pending_rows, bbp_only=True)
    visible_login_hold_active = login_mode_active and _background_browser_mode() == "visible"
    if visible_login_hold_active and login_mode_selected_rows > 0:
        active_run_id = _normalize_text(pending_rows.iloc[0].get("run_id", "")) if not pending_rows.empty else ""
        _append_price_list_live_event(
            root_path=root_path,
            event_utc=observed_utc,
            event_type="login_mode_hold_started",
            supplier_id=supplier_id,
            f061_run_id=active_run_id,
            status="started",
            rows=login_mode_selected_rows,
            notes=(
                f"hold_seconds={login_mode_hold_seconds:.0f};selected_rows={processed_target};"
                f"bbp_selected_rows={login_mode_bbp_selected_rows}"
            ),
        )
        _update_login_mode_request_status(
            status="holding",
            observed_utc=observed_utc,
            notes=(
                f"selected_login_rows={login_mode_selected_rows};"
                f"selected_bbp_login_rows={login_mode_bbp_selected_rows};"
                f"hold_seconds={login_mode_hold_seconds:.0f}"
            ),
        )
        if adapter is None and login_mode_hold_seconds > 0:
            time.sleep(login_mode_hold_seconds)

    adapter_local_created = False
    if adapter is None:
        if legacy_scanner_root is None:
            legacy_scanner_root = str(root_path / "scripts" / "flows" / "F" / "legacy_scanner_2_1")
        adapter = LegacyCompatibleAmazonAdapter(
            legacy_scanner_root=legacy_scanner_root,
            scrape_mode=scrape_mode,
            price_source=requested_price_source,
            pricing_retries=_parse_nonnegative_int(os.environ.get(F061_PRICING_RETRIES_ENV, "3"), default=3),
            root_path=root_path,
            catalog_min_interval_seconds=effective_catalog_min_interval,
            hazmat_min_interval_seconds=effective_hazmat_min_interval,
            pricing_min_interval_seconds=effective_pricing_min_interval,
            fees_min_interval_seconds=effective_fees_min_interval,
            scrape_page_load_timeout_seconds=effective_scrape_page_load_timeout,
        )
        adapter_local_created = True

    if processed_target > 0 and scrape_mode == "legacy_module" and hasattr(adapter, "missing_legacy_modules"):
        missing_modules = adapter.missing_legacy_modules()  # type: ignore[attr-defined]
        if requested_stage_mode == F061_STAGE_MODE_API_ONLY:
            missing_modules = [name for name in missing_modules if name != "Webscrape.process_passed_product"]
        elif requested_stage_mode == F061_STAGE_MODE_BROWSER_ONLY:
            missing_modules = [name for name in missing_modules if name == "Webscrape.process_passed_product"]
        if missing_modules:
            missing_text = ",".join(sorted(missing_modules))
            error_notes = ""
            if hasattr(adapter, "legacy_module_load_errors"):
                load_errors = adapter.legacy_module_load_errors()  # type: ignore[attr-defined]
                if isinstance(load_errors, dict) and load_errors:
                    error_parts = [f"{k}:{v}" for k, v in sorted(load_errors.items())]
                    error_notes = ";errors=" + "|".join(error_parts)

            health_rows = [
                {
                    "check": "feeder_legacy_first_checks_source_contract",
                    "status": "ok",
                    "value": str(len(supplier_rows_all)),
                    "notes": "active_run_contract_valid",
                    "observed_utc": observed_utc,
                    "source_path": str(root_path / get_f_output_contract("supplier_price_list_active_run").rel_path),
                },
                {
                    "check": "feeder_legacy_first_checks_runtime",
                    "status": "fail",
                    "value": "0",
                    "notes": f"missing_legacy_modules={missing_text}{error_notes}",
                    "observed_utc": observed_utc,
                    "source_path": str(root_path / "scripts" / "flows" / "F" / "legacy_scanner_2_1"),
                },
                {
                    "check": "feeder_legacy_first_checks_pass_balance",
                    "status": "warn",
                    "value": "0",
                    "notes": "run_blocked_before_scan",
                    "observed_utc": observed_utc,
                    "source_path": "",
                },
                {
                    "check": "feeder_legacy_scrape_evidence_runtime",
                    "status": "warn",
                    "value": "0",
                    "notes": "run_blocked_before_scan",
                    "observed_utc": observed_utc,
                    "source_path": str(root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path),
                },
                {
                    "check": "feeder_legacy_chart_daily_raw_runtime",
                    "status": "warn",
                    "value": "0",
                    "notes": "run_blocked_before_scan",
                    "observed_utc": observed_utc,
                    "source_path": str(root_path / get_f_output_contract("feeder_legacy_chart_daily_raw_live").rel_path),
                },
            ]
            _write_contract_df(pd.DataFrame(health_rows), "feeder_legacy_sheet_health", root_path)
            summary = {
                "status": "blocked",
                "supplier_id": supplier_id,
                "processed_rows": 0,
                "pending_rows": int(len(supplier_queue_all)),
                "pass_rows": 0,
                "fail_rows": 0,
                "retry_rows": 0,
                "notes": f"missing_legacy_modules={missing_text}",
            }
            print(summary)
            if adapter_local_created and hasattr(adapter, "close"):
                try:
                    adapter.close()
                except Exception:
                    pass
            return summary

    supplier_name = _normalize_text(supplier_rows_all.iloc[0].get("supplier_name", ""))
    supplier_name_key = _normalize_lower(supplier_name)
    existing_first_supplier = first_checks_df[first_checks_df["supplier"].map(_normalize_lower) == supplier_name_key].copy()
    existing_first_map: dict[str, dict[str, str]] = {}
    if not existing_first_supplier.empty:
        for _, row in existing_first_supplier.iterrows():
            payload = _row_dict_from_df_row(row)
            candidate_id = payload.get("candidate_id", "")
            if candidate_id:
                existing_first_map[candidate_id] = payload
    if "supplier_id" in scrape_evidence_df.columns:
        existing_scrape_supplier = scrape_evidence_df[
            scrape_evidence_df["supplier_id"].map(_normalize_lower) == supplier_key
        ].copy()
    else:
        existing_scrape_supplier = _empty_contract_df("feeder_legacy_scrape_evidence_live")
    if "supplier_id" in chart_daily_raw_df.columns:
        existing_chart_daily_supplier = chart_daily_raw_df[
            chart_daily_raw_df["supplier_id"].map(_normalize_lower) == supplier_key
        ].copy()
    else:
        existing_chart_daily_supplier = _empty_contract_df("feeder_legacy_chart_daily_raw_live")

    updates_map: dict[str, dict[str, str]] = {}
    scrape_updates_map: dict[str, dict[str, str]] = {}
    chart_daily_new_rows: list[dict[str, str]] = []
    speed_ledger_new_rows: list[dict[str, str]] = []
    login_backtrack_new_rows: list[dict[str, str]] = []
    latest_login_backtrack = _latest_login_backtrack_by_candidate(login_backtrack_df)
    processed_candidate_ids: set[str] = set()
    status_counter: dict[str, int] = {}
    processed_rows = 0
    completed_indices: set[int] = set()
    source_failed_rows_delta = 0
    login_backtrack_pending_rows = 0
    login_backtrack_merged_rows = 0
    rescan_retry_pending_rows = 0
    rescan_retry_exhausted_rows = 0
    browser_stage_ready_rows = 0
    dashboard_yes_no_unresolved_rows = 0
    dashboard_missing_on_hard_fail_rows = 0
    expanded_candidate_rows = 0
    scrape_attempted_rows = 0
    scrape_success_rows = 0
    chart_daily_rows_captured = 0
    row_runtime: dict[str, Any] = {}
    processed_indices: set[int] = set()
    login_backtrack_active_rows: dict[int, dict[str, str]] = {}
    rescan_retry_active_rows: dict[int, dict[str, str]] = {}
    browser_stage_ready_active_rows: dict[int, dict[str, str]] = {}
    candidate_active_rows: dict[str, dict[str, str]] = {}

    for _, pending_row in pending_rows.iterrows():
        base_started = time.perf_counter()
        global_index = int(pending_row["index"])
        processed_indices.add(global_index)
        active_row = active_work.iloc[global_index]
        base_candidate_id = _row_identity(active_row)
        access_token = _normalize_text(adapter.get_access_token())
        barcode = _normalize_digits(active_row.get("barcode", ""))
        active_run_id = _normalize_text(active_row.get("run_id", ""))
        api_cache_dir = _api_cache_dir(root_path, supplier_id=supplier_id, run_id=active_run_id)

        source_statuses: list[str] = []
        source_rows: list[dict[str, str]] = []
        source_scrape_rows: list[dict[str, str] | None] = []
        source_speed_rows: list[dict[str, object]] = []
        source_requeued_for_rescan = False

        if barcode == "":
            first_row = _base_first_checks_row(
                active_row,
                existing_first_map.get(base_candidate_id),
                observed_utc,
                candidate_id=base_candidate_id,
            )
            status_code = "NOASIN"
            first_row["pf"] = _status_to_pf(status_code)
            first_row["status_reason"] = status_code
            source_rows.append(first_row)
            source_statuses.append(status_code)
            source_scrape_rows.append(None)
            source_speed_rows.append(
                _speed_timing_payload(
                    total_seconds=time.perf_counter() - base_started,
                    endpoint_delta={},
                    browser_attempted=False,
                    browser_blocked=False,
                )
            )
        elif requested_stage_mode == F061_STAGE_MODE_BROWSER_ONLY:
            existing_row = existing_first_map.get(base_candidate_id)
            first_row, status_code, scrape_evidence_row = _process_single_row(
                active_row=active_row,
                existing_first_row=existing_row,
                adapter=adapter,
                access_token=access_token,
                row_index_1_based=global_index + 1,
                observed_utc=observed_utc,
                pricing_min_interval_seconds=effective_pricing_min_interval,
                row_runtime=row_runtime,
                candidate_id=base_candidate_id,
                mode=requested_mode,
                stage_mode=requested_stage_mode,
                api_cache_dir=api_cache_dir,
            )
            source_speed_rows.append(
                _speed_timing_payload(
                    total_seconds=time.perf_counter() - base_started,
                    endpoint_delta={},
                    browser_attempted=scrape_evidence_row is not None,
                    browser_blocked=_scrape_evidence_is_blocked(scrape_evidence_row),
                )
            )
            source_rows.append(first_row)
            source_statuses.append(status_code)
            source_scrape_rows.append(scrape_evidence_row)
        else:
            catalog_started = time.perf_counter()
            catalog_before = _endpoint_stats_snapshot(adapter)
            catalog_candidates_raw = _catalog_candidates_from_adapter(
                adapter=adapter,
                barcode=barcode,
                access_token=access_token,
            )
            catalog_after = _endpoint_stats_snapshot(adapter)
            catalog_delta = _endpoint_delta(catalog_before, catalog_after)
            catalog_elapsed = time.perf_counter() - catalog_started
            catalog_candidates = (
                [candidate for candidate in catalog_candidates_raw if isinstance(candidate, dict)]
                if isinstance(catalog_candidates_raw, list)
                else []
            )
            selected_candidates = _select_catalog_candidates_for_processing(
                candidates=catalog_candidates,
                max_candidates=effective_catalog_max_candidates,
                search_barcode=barcode,
                supplier_title=_normalize_text(active_row.get("supplier_title", "")),
            )

            if not selected_candidates:
                lookup_error = ""
                if catalog_candidates:
                    lookup_error = _normalize_lower(catalog_candidates[0].get("error", ""))
                status_code = (
                    "RESCAN"
                    if lookup_error == "http_429"
                    or lookup_error.startswith("request_exception:")
                    or lookup_error.startswith("http_5")
                    else "NOASIN"
                )
                first_row = _base_first_checks_row(
                    active_row,
                    existing_first_map.get(base_candidate_id),
                    observed_utc,
                    candidate_id=base_candidate_id,
                )
                first_row["pf"] = _status_to_pf(status_code)
                first_row["status_reason"] = status_code
                source_rows.append(first_row)
                source_statuses.append(status_code)
                source_scrape_rows.append(None)
                source_speed_rows.append(
                    _speed_timing_payload(
                        total_seconds=time.perf_counter() - base_started,
                        endpoint_delta=catalog_delta,
                        browser_attempted=False,
                        browser_blocked=False,
                    )
                )
            else:
                for candidate_index, catalog_details in enumerate(selected_candidates):
                    asin = _normalize_text(catalog_details.get("asin", ""))
                    candidate_id = _candidate_identity(base_candidate_id, asin, candidate_index)
                    existing_row = existing_first_map.get(candidate_id)
                    process_started = time.perf_counter()
                    process_before = _endpoint_stats_snapshot(adapter)
                    first_row, status_code, scrape_evidence_row = _process_single_row(
                        active_row=active_row,
                        existing_first_row=existing_row,
                        adapter=adapter,
                        access_token=access_token,
                        row_index_1_based=global_index + 1,
                        observed_utc=observed_utc,
                        pricing_min_interval_seconds=effective_pricing_min_interval,
                        row_runtime=row_runtime,
                        catalog_details=catalog_details,
                        candidate_id=candidate_id,
                        mode=requested_mode,
                        stage_mode=requested_stage_mode,
                        api_cache_dir=api_cache_dir,
                    )
                    process_after = _endpoint_stats_snapshot(adapter)
                    process_delta = _endpoint_delta(process_before, process_after)
                    timing_delta = (
                        _merge_endpoint_deltas(catalog_delta, process_delta)
                        if candidate_index == 0
                        else process_delta
                    )
                    source_speed_rows.append(
                        _speed_timing_payload(
                            total_seconds=(time.perf_counter() - process_started)
                            + (catalog_elapsed if candidate_index == 0 else 0.0),
                            endpoint_delta=timing_delta,
                            browser_attempted=scrape_evidence_row is not None,
                            browser_blocked=_scrape_evidence_is_blocked(scrape_evidence_row),
                        )
                    )
                    source_rows.append(first_row)
                    source_statuses.append(status_code)
                    source_scrape_rows.append(scrape_evidence_row)

        for first_row, status_code, scrape_evidence_row, speed_timing in zip(
            source_rows,
            source_statuses,
            source_scrape_rows,
            source_speed_rows,
        ):
            candidate_id = _normalize_text(first_row.get("candidate_id", ""))
            active_status = _normalize_lower(active_row.get("scan_status", ""))
            is_login_backtrack_attempt = active_status in {
                F061_SCAN_STATUS_LOGIN_BACKTRACK_PENDING,
                F061_SCAN_STATUS_LOGIN_BACKTRACK_RUNNING,
            } or _normalize_lower(active_row.get("scan_reason", "")) == F061_LOGIN_BACKTRACK_SCAN_REASON
            needs_auth_backtrack = status_code == F061_LOGIN_BACKTRACK_STATUS_CODE or _scrape_evidence_needs_login_backtrack(scrape_evidence_row)
            hard_fail_missing_dashboard = _scrape_evidence_missing_dashboard_on_hard_fail(scrape_evidence_row, status_code)
            needs_dashboard_yes_no_backtrack = (
                _scrape_evidence_missing_required_dashboard_yes_no(scrape_evidence_row)
                and not hard_fail_missing_dashboard
            )
            needs_login_backtrack = needs_auth_backtrack or needs_dashboard_yes_no_backtrack
            if not needs_login_backtrack and hard_fail_missing_dashboard:
                dashboard_missing_on_hard_fail_rows += 1
                if scrape_evidence_row is not None:
                    scrape_evidence_row["dashboard_yes_no_source"] = "dashboard_missing_on_hard_fail"
            rescan_retry_requeued = False
            merged_login_backtrack = (
                is_login_backtrack_attempt
                and scrape_evidence_row is not None
                and _valid_dashboard_yes_no(scrape_evidence_row.get("bbp_dashboard_yes_or_no", ""))
                and status_code != F061_LOGIN_BACKTRACK_STATUS_CODE
            )
            resolved_without_bbp_backtrack = (
                is_login_backtrack_attempt
                and not needs_login_backtrack
                and status_code != F061_LOGIN_BACKTRACK_STATUS_CODE
            )
            if merged_login_backtrack:
                merge_preview = _build_login_backtrack_ledger_row(
                    active_row=active_row,
                    first_row=first_row,
                    scrape_evidence_row=scrape_evidence_row,
                    observed_utc=observed_utc,
                    status="merged",
                    existing_original=latest_login_backtrack.get(candidate_id),
                )
                _restore_original_price_context(
                    first_row=first_row,
                    scrape_evidence_row=scrape_evidence_row,
                    original=latest_login_backtrack.get(candidate_id),
                    backtrack_id=merge_preview["backtrack_id"],
                    observed_utc=observed_utc,
                )
                login_backtrack_new_rows.append(merge_preview)
                login_backtrack_merged_rows += 1
            elif resolved_without_bbp_backtrack:
                merge_preview = _build_login_backtrack_ledger_row(
                    active_row=active_row,
                    first_row=first_row,
                    scrape_evidence_row=scrape_evidence_row,
                    observed_utc=observed_utc,
                    status="merged",
                    existing_original=latest_login_backtrack.get(candidate_id),
                )
                _restore_original_price_context(
                    first_row=first_row,
                    scrape_evidence_row=scrape_evidence_row,
                    original=latest_login_backtrack.get(candidate_id),
                    backtrack_id=merge_preview["backtrack_id"],
                    observed_utc=observed_utc,
                )
                login_backtrack_new_rows.append(merge_preview)
                login_backtrack_merged_rows += 1
            elif needs_login_backtrack:
                first_row["pf"] = ""
                first_row["status_reason"] = F061_LOGIN_BACKTRACK_REASON
                if scrape_evidence_row is not None:
                    scrape_evidence_row["first_check_status_code"] = F061_LOGIN_BACKTRACK_STATUS_CODE
                    scrape_evidence_row["pf"] = ""
                    scrape_evidence_row["status_reason"] = F061_LOGIN_BACKTRACK_REASON
                    scrape_evidence_row["dashboard_yes_no_source"] = "login_backtrack_pending"
                pending_payload = _row_dict_from_df_row(active_row)
                next_backtrack_attempt_count = _parse_nonnegative_int(
                    active_row.get("backtrack_attempt_count", "0"), default=0
                ) + 1
                unresolved_dashboard_yes_no = (
                    needs_dashboard_yes_no_backtrack
                    and not needs_auth_backtrack
                    and next_backtrack_attempt_count >= F061_DASHBOARD_YES_NO_MAX_BACKTRACK_ATTEMPTS
                )
                pending_payload["scan_status"] = F061_SCAN_STATUS_LOGIN_BACKTRACK_PENDING
                pending_payload["scan_reason"] = F061_LOGIN_BACKTRACK_SCAN_REASON
                pending_payload["completion_block_reason"] = (
                    "bbp_login_required" if needs_auth_backtrack else "dashboard_yes_no_backtrack_required"
                )
                if unresolved_dashboard_yes_no:
                    pending_payload["scan_status"] = "dashboard_yes_no_unresolved"
                    pending_payload["scan_reason"] = F061_DASHBOARD_YES_NO_UNRESOLVED_SCAN_REASON
                    pending_payload["completion_block_reason"] = F061_DASHBOARD_YES_NO_UNRESOLVED_SCAN_REASON
                pending_payload["last_attempt_utc"] = observed_utc
                pending_payload["backtrack_original_observed_utc"] = _normalize_text(
                    (scrape_evidence_row or {}).get("observed_utc", "")
                ) or observed_utc
                pending_payload["backtrack_attempt_count"] = str(next_backtrack_attempt_count)
                if not unresolved_dashboard_yes_no:
                    login_backtrack_active_rows[global_index] = pending_payload
                    login_backtrack_pending_rows += 1
                login_backtrack_new_rows.append(
                    _build_login_backtrack_ledger_row(
                        active_row=active_row,
                        first_row=first_row,
                        scrape_evidence_row=scrape_evidence_row,
                        observed_utc=observed_utc,
                        status=(
                            "blocked_login"
                            if needs_auth_backtrack
                            else (
                                "dashboard_yes_no_unresolved"
                                if unresolved_dashboard_yes_no
                                else "missing_dashboard_yes_no"
                            )
                        ),
                        existing_original=latest_login_backtrack.get(candidate_id),
                    )
                )
                if unresolved_dashboard_yes_no:
                    candidate_active_rows[candidate_id] = pending_payload
                    dashboard_yes_no_unresolved_rows += 1
            elif status_code in RETRY_STATUS_CODES:
                if _rescan_retry_allowed(active_row):
                    if global_index not in rescan_retry_active_rows:
                        pending_payload = _row_dict_from_df_row(active_row)
                        pending_payload["scan_status"] = F061_SCAN_STATUS_PENDING
                        pending_payload["scan_reason"] = F061_RESCAN_RETRY_SCAN_REASON
                        pending_payload["completion_block_reason"] = F061_RESCAN_RETRY_BLOCK_REASON
                        pending_payload["attempt_count"] = str(
                            _parse_nonnegative_int(active_row.get("attempt_count", "0"), default=0) + 1
                        )
                        pending_payload["last_attempt_utc"] = observed_utc
                        pending_payload["backtrack_original_observed_utc"] = ""
                        pending_payload["backtrack_attempt_count"] = ""
                        rescan_retry_active_rows[global_index] = pending_payload
                        rescan_retry_pending_rows += 1
                    rescan_retry_requeued = True
                    source_requeued_for_rescan = True
                else:
                    rescan_retry_exhausted_rows += 1
            elif status_code == F061_STATUS_BROWSER_READY:
                pending_payload = _row_dict_from_df_row(active_row)
                pending_payload["scan_status"] = F061_SCAN_STATUS_PENDING
                pending_payload["scan_reason"] = F061_BROWSER_STAGE_READY_REASON
                pending_payload["completion_block_reason"] = ""
                pending_payload["last_attempt_utc"] = observed_utc
                pending_payload["backtrack_original_observed_utc"] = ""
                pending_payload["backtrack_attempt_count"] = ""
                browser_stage_ready_active_rows[global_index] = pending_payload
                browser_stage_ready_rows += 1
            if candidate_id:
                updates_map[candidate_id] = first_row
                processed_candidate_ids.add(candidate_id)
                candidate_active_rows[candidate_id] = candidate_active_rows.get(
                    candidate_id,
                    login_backtrack_active_rows.get(
                        global_index,
                        rescan_retry_active_rows.get(
                            global_index,
                            browser_stage_ready_active_rows.get(global_index, _row_dict_from_df_row(active_row)),
                        ),
                    ),
                )
                speed_ledger_new_rows.append(
                    _scanner_speed_ledger_row(
                        active_row=active_row,
                        first_row=first_row,
                        timing=speed_timing,
                        observed_utc=observed_utc,
                    )
                )
            status_counter[status_code] = status_counter.get(status_code, 0) + 1
            if (
                status_code not in {F061_LOGIN_BACKTRACK_STATUS_CODE, F061_STATUS_BROWSER_READY}
                and not needs_login_backtrack
                and not rescan_retry_requeued
            ):
                completed_indices.add(global_index)
            expanded_candidate_rows += 1
            if scrape_evidence_row is not None:
                scrape_attempted_rows += 1
                if _normalize_lower(scrape_evidence_row.get("scrape_success", "")) == "true":
                    scrape_success_rows += 1
                scrape_candidate_id = _normalize_text(scrape_evidence_row.get("candidate_id", "")) or candidate_id
                if scrape_candidate_id:
                    scrape_updates_map[scrape_candidate_id] = scrape_evidence_row
                chart_rows = _build_chart_daily_raw_rows(
                    active_row=active_row,
                    first_row=first_row,
                    scrape_evidence_row=scrape_evidence_row,
                    observed_utc=observed_utc,
                    status_code=status_code,
                )
                if chart_rows:
                    chart_daily_rows_captured += len(chart_rows)
                    chart_daily_new_rows.extend(chart_rows)

        if F061_LOGIN_BACKTRACK_STATUS_CODE in source_statuses:
            pass
        elif source_requeued_for_rescan:
            pass
        elif F061_STATUS_BROWSER_READY in source_statuses:
            pass
        elif "PASS" not in source_statuses:
            source_failed_rows_delta += 1
        processed_rows += 1
    remaining_supplier_queue = supplier_queue_all[~supplier_queue_all["index"].isin(processed_indices)].copy()
    if "index" in remaining_supplier_queue.columns:
        remaining_supplier_queue = remaining_supplier_queue.drop(columns=["index"])
    if login_backtrack_active_rows:
        backtrack_df = pd.DataFrame(list(login_backtrack_active_rows.values()))
        remaining_supplier_queue = pd.concat([backtrack_df, remaining_supplier_queue], ignore_index=True)
    if rescan_retry_active_rows:
        retry_df = pd.DataFrame(list(rescan_retry_active_rows.values()))
        remaining_supplier_queue = pd.concat([remaining_supplier_queue, retry_df], ignore_index=True)
    if browser_stage_ready_active_rows:
        ready_df = pd.DataFrame(list(browser_stage_ready_active_rows.values()))
        remaining_supplier_queue = pd.concat([remaining_supplier_queue, ready_df], ignore_index=True)
    if login_backtrack_active_rows or rescan_retry_active_rows or browser_stage_ready_active_rows:
        remaining_supplier_queue["_queue_priority"] = remaining_supplier_queue.apply(
            lambda row: str(active_row_queue_priority(row.to_dict())),
            axis=1,
        )
        remaining_supplier_queue = remaining_supplier_queue.sort_values(
            by=["_queue_priority", "last_attempt_utc", "supplier_sku", "row_key"],
            ascending=[True, True, True, True],
            kind="stable",
        ).drop(columns=["_queue_priority"], errors="ignore")
    supplier_rows_updated_reset = remaining_supplier_queue.reset_index(drop=True)

    other_active_rows = active_work[~supplier_mask].copy()
    if "index" in other_active_rows.columns:
        other_active_rows = other_active_rows.drop(columns=["index"], errors="ignore")
    active_output_df = pd.concat([other_active_rows, supplier_rows_updated_reset], ignore_index=True)
    if not active_output_df.empty:
        active_output_df["_queue_priority"] = active_output_df.apply(
            lambda row: str(active_row_queue_priority(row.to_dict())),
            axis=1,
        )
        active_output_df = active_output_df.sort_values(
            by=["_queue_priority", "last_attempt_utc", "supplier_id", "supplier_sku", "row_key"],
            ascending=[True, True, True, True, True],
            kind="stable",
        ).drop(columns=["_queue_priority"], errors="ignore")
    active_written = _write_contract_df(active_output_df, "supplier_price_list_active_run", root_path)

    supplier_dir = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id
    supplier_active_path = supplier_dir / "active_run.csv"
    active_columns = _contract_columns("supplier_price_list_active_run")
    _write_raw_csv(supplier_rows_updated_reset, supplier_active_path, active_columns)

    run_state_columns = _contract_columns("supplier_price_list_run_state")
    run_state_existing_supplier = run_state_df[run_state_df["supplier_id"].map(_normalize_lower) == supplier_key].copy()
    previous_state_row = (
        _row_dict_from_df_row(run_state_existing_supplier.iloc[0])
        if not run_state_existing_supplier.empty
        else {
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "run_id": _normalize_text(supplier_rows_all.iloc[0].get("run_id", "")),
            "run_status": "",
            "source_url": "",
            "source_file_path": "",
            "source_seen_at_utc": _normalize_text(supplier_rows_all.iloc[0].get("source_seen_at_utc", "")),
            "normalized_utc": "",
            "held_rows": "0",
        }
    )
    pass_rows = sum(1 for row in updates_map.values() if _normalize_text(row.get("pf", "")).upper() == "PASS")
    fail_rows = sum(1 for row in updates_map.values() if _normalize_text(row.get("pf", "")).upper() == "FAIL")
    retry_rows = sum(1 for row in updates_map.values() if _normalize_text(row.get("pf", "")).upper() == "RESCAN")
    run_state_row = _build_run_state_row(
        supplier_queue_rows=supplier_rows_updated_reset,
        previous_row=previous_state_row,
        observed_utc=observed_utc,
        processed_rows=len(completed_indices),
        failed_rows_delta=source_failed_rows_delta,
    )
    run_state_other = run_state_df[run_state_df["supplier_id"].map(_normalize_lower) != supplier_key].copy()
    run_state_written = _write_contract_df(
        pd.concat([run_state_other, pd.DataFrame([run_state_row])], ignore_index=True),
        "supplier_price_list_run_state",
        root_path,
    )
    _write_raw_csv(pd.DataFrame([run_state_row]), supplier_dir / "run_state.csv", run_state_columns)

    if "supplier_id" in screening_row_state_df.columns:
        existing_screening_supplier = screening_row_state_df[
            screening_row_state_df["supplier_id"].map(_normalize_lower) == supplier_key
        ].copy()
    else:
        existing_screening_supplier = _empty_contract_df("f_screening_row_state_live")

    supplier_screening_map: dict[str, dict[str, str]] = {}
    if not existing_screening_supplier.empty:
        for _, row in existing_screening_supplier.iterrows():
            payload = _row_dict_from_df_row(row)
            candidate_id = _normalize_text(payload.get("candidate_id", ""))
            if candidate_id == "":
                continue
            if candidate_id in processed_candidate_ids:
                continue
            supplier_screening_map[candidate_id] = payload

    for payload in updates_map.values():
        candidate_id = _normalize_text(payload.get("candidate_id", ""))
        if candidate_id == "":
            continue
        active_payload = candidate_active_rows.get(candidate_id, {})
        supplier_screening_map[candidate_id] = _build_screening_row_state_processed(
            active_row=active_payload,
            first_row=payload,
            observed_utc=observed_utc,
            mode=requested_mode,
            timeout_policy_df=timeout_policy_df,
        )

    for _, pending_row in remaining_supplier_queue.iterrows():
        candidate_id = _row_identity(pending_row)
        if candidate_id == "":
            continue
        if candidate_id in supplier_screening_map:
            continue
        supplier_screening_map[candidate_id] = _build_screening_row_state_pending(
            active_row=_row_dict_from_df_row(pending_row),
            candidate_id=candidate_id,
            observed_utc=observed_utc,
            mode=requested_mode,
        )

    supplier_screening_rows = list(supplier_screening_map.values())
    supplier_screening_df = (
        pd.DataFrame(supplier_screening_rows)
        if supplier_screening_rows
        else _empty_contract_df("f_screening_row_state_live")
    )
    screening_other = (
        screening_row_state_df[screening_row_state_df["supplier_id"].map(_normalize_lower) != supplier_key].copy()
        if "supplier_id" in screening_row_state_df.columns
        else _empty_contract_df("f_screening_row_state_live")
    )
    screening_state_written = _write_contract_df(
        pd.concat([screening_other, supplier_screening_df], ignore_index=True),
        "f_screening_row_state_live",
        root_path,
    )

    existing_pass_supplier = existing_first_supplier[
        existing_first_supplier.apply(lambda row: _first_check_row_kept_live(row), axis=1)
    ].copy()
    supplier_pass_map: dict[str, dict[str, str]] = {}
    if not existing_pass_supplier.empty:
        for _, row in existing_pass_supplier.iterrows():
            payload = _row_dict_from_df_row(row)
            candidate_id = payload.get("candidate_id", "")
            if candidate_id:
                # Drop stale PASS rows for candidates processed in this run.
                if candidate_id in processed_candidate_ids:
                    continue
                supplier_pass_map[candidate_id] = payload

    for payload in updates_map.values():
        if not _first_check_row_kept_live(payload):
            continue
        candidate_id = _normalize_text(payload.get("candidate_id", ""))
        if candidate_id:
            supplier_pass_map[candidate_id] = payload

    supplier_pass_rows = list(supplier_pass_map.values())
    supplier_pass_df = pd.DataFrame(supplier_pass_rows) if supplier_pass_rows else _empty_contract_df("feeder_legacy_first_checks_live")
    first_other = (
        first_checks_df[first_checks_df["supplier"].map(_normalize_lower) != supplier_name_key].copy()
        if "supplier" in first_checks_df.columns
        else _empty_contract_df("feeder_legacy_first_checks_live")
    )
    first_written = _write_contract_df(
        pd.concat([first_other, supplier_pass_df], ignore_index=True),
        "feeder_legacy_first_checks_live",
        root_path,
    )

    supplier_scrape_map: dict[str, dict[str, str]] = {}
    if not existing_scrape_supplier.empty:
        for _, row in existing_scrape_supplier.iterrows():
            payload = _row_dict_from_df_row(row)
            candidate_id = payload.get("candidate_id", "")
            if candidate_id:
                if candidate_id in processed_candidate_ids:
                    continue
                supplier_scrape_map[candidate_id] = payload
    for payload in scrape_updates_map.values():
        candidate_id = _normalize_text(payload.get("candidate_id", ""))
        if candidate_id:
            supplier_scrape_map[candidate_id] = payload
    supplier_scrape_rows = list(supplier_scrape_map.values())
    supplier_scrape_df = (
        pd.DataFrame(supplier_scrape_rows)
        if supplier_scrape_rows
        else _empty_contract_df("feeder_legacy_scrape_evidence_live")
    )
    scrape_other = (
        scrape_evidence_df[scrape_evidence_df["supplier_id"].map(_normalize_lower) != supplier_key].copy()
        if "supplier_id" in scrape_evidence_df.columns
        else _empty_contract_df("feeder_legacy_scrape_evidence_live")
    )
    scrape_evidence_written = _write_contract_df(
        pd.concat([scrape_other, supplier_scrape_df], ignore_index=True),
        "feeder_legacy_scrape_evidence_live",
        root_path,
    )

    existing_chart_keep = existing_chart_daily_supplier.copy()
    if not existing_chart_keep.empty and "candidate_id" in existing_chart_keep.columns:
        existing_chart_keep = existing_chart_keep[
            ~existing_chart_keep["candidate_id"].map(_normalize_text).isin(processed_candidate_ids)
        ].copy()
    new_chart_df = (
        pd.DataFrame(chart_daily_new_rows)
        if chart_daily_new_rows
        else _empty_contract_df("feeder_legacy_chart_daily_raw_live")
    )
    chart_other = (
        chart_daily_raw_df[chart_daily_raw_df["supplier_id"].map(_normalize_lower) != supplier_key].copy()
        if "supplier_id" in chart_daily_raw_df.columns
        else _empty_contract_df("feeder_legacy_chart_daily_raw_live")
    )
    supplier_chart_daily_df = pd.concat([chart_other, existing_chart_keep, new_chart_df], ignore_index=True)
    chart_daily_written = _write_contract_df(
        supplier_chart_daily_df,
        "feeder_legacy_chart_daily_raw_live",
        root_path,
    )
    speed_ledger_written = _write_contract_df(
        _merge_speed_ledger(speed_ledger_df, speed_ledger_new_rows),
        "f_scanner_speed_ledger_live",
        root_path,
    )
    if login_backtrack_new_rows:
        login_backtrack_written = _write_contract_df(
            pd.concat([login_backtrack_df, pd.DataFrame(login_backtrack_new_rows)], ignore_index=True),
            "f_login_backtrack_evidence_live",
            root_path,
        )
    else:
        login_backtrack_written = _write_contract_df(
            login_backtrack_df,
            "f_login_backtrack_evidence_live",
            root_path,
        )

    pending_after = int(len(supplier_rows_updated_reset))
    login_backtrack_pending_after = _count_login_backtrack_rows(supplier_rows_updated_reset)
    bbp_login_backtrack_pending_after = _count_login_backtrack_rows(supplier_rows_updated_reset, bbp_only=True)

    login_mode_runtime_status = "ok"
    login_mode_runtime_value = "inactive"
    login_mode_runtime_notes = (
        f"active=0;waiting_rows={login_backtrack_waiting_rows};"
        f"bbp_waiting_rows={login_mode_bbp_backtrack_waiting_rows};skipped_rows=0"
    )
    if login_mode_active:
        if login_mode_selected_rows <= 0:
            login_mode_runtime_status = "warn"
            login_mode_runtime_value = "active_no_selected_rows"
            login_mode_runtime_notes = (
                f"active=1;selected_rows=0;waiting_rows={login_backtrack_waiting_rows};"
                f"bbp_waiting_rows={login_mode_bbp_backtrack_waiting_rows}"
            )
            _append_price_list_live_event(
                root_path=root_path,
                event_utc=observed_utc,
                event_type="login_mode_still_required",
                supplier_id=supplier_id,
                f061_run_id=_normalize_text(supplier_rows_all.iloc[0].get("run_id", "")),
                status="no_login_rows_selected",
                rows=login_backtrack_pending_after,
                notes=login_mode_runtime_notes,
            )
            _update_login_mode_request_status(
                status="still_required",
                observed_utc=observed_utc,
                notes=login_mode_runtime_notes,
            )
        elif F061_LOGIN_BACKTRACK_STATUS_CODE in status_counter or login_backtrack_pending_rows > 0:
            login_mode_runtime_status = "warn"
            login_mode_runtime_value = "still_required"
            login_mode_runtime_notes = (
                f"active=1;selected_rows={login_mode_selected_rows};"
                f"bbp_selected_rows={login_mode_bbp_selected_rows};"
                f"pending_after={login_backtrack_pending_after};"
                f"new_pending_rows={login_backtrack_pending_rows}"
            )
            _append_price_list_live_event(
                root_path=root_path,
                event_utc=observed_utc,
                event_type="login_mode_still_required",
                supplier_id=supplier_id,
                f061_run_id=_normalize_text(supplier_rows_all.iloc[0].get("run_id", "")),
                status="still_required",
                rows=login_backtrack_pending_after,
                notes=login_mode_runtime_notes,
            )
            _update_login_mode_request_status(
                status="still_required",
                observed_utc=observed_utc,
                notes=login_mode_runtime_notes,
            )
        elif login_backtrack_merged_rows > 0 or login_mode_selected_rows > 0:
            if login_backtrack_pending_after > 0:
                login_mode_runtime_value = "authenticated_backlog_remaining"
                login_mode_runtime_notes = (
                    f"active=1;merged_rows={login_backtrack_merged_rows};"
                    f"pending_after={login_backtrack_pending_after};"
                    f"bbp_pending_after={bbp_login_backtrack_pending_after}"
                )
                _append_price_list_live_event(
                    root_path=root_path,
                    event_utc=observed_utc,
                    event_type="login_mode_authenticated",
                    supplier_id=supplier_id,
                    f061_run_id=_normalize_text(supplier_rows_all.iloc[0].get("run_id", "")),
                    status="authenticated",
                    rows=login_backtrack_merged_rows,
                    notes=login_mode_runtime_notes,
                )
                _update_login_mode_request_status(
                    status="authenticated_backlog_remaining",
                    observed_utc=observed_utc,
                    notes=login_mode_runtime_notes,
                )
            else:
                login_mode_runtime_value = "backlog_drained"
                login_mode_runtime_notes = (
                    f"active=1;merged_rows={login_backtrack_merged_rows};"
                    f"pending_after=0;normal_pending_after={pending_after}"
                )
                if login_backtrack_merged_rows > 0:
                    _append_price_list_live_event(
                        root_path=root_path,
                        event_utc=observed_utc,
                        event_type="login_mode_authenticated",
                        supplier_id=supplier_id,
                        f061_run_id=_normalize_text(supplier_rows_all.iloc[0].get("run_id", "")),
                        status="authenticated",
                        rows=login_backtrack_merged_rows,
                        notes=login_mode_runtime_notes,
                    )
                _append_price_list_live_event(
                    root_path=root_path,
                    event_utc=observed_utc,
                    event_type="login_mode_backlog_drained",
                    supplier_id=supplier_id,
                    f061_run_id=_normalize_text(supplier_rows_all.iloc[0].get("run_id", "")),
                    status="drained",
                    rows=login_backtrack_merged_rows,
                    notes=login_mode_runtime_notes,
                )
                _update_login_mode_request_status(
                    status="drained",
                    observed_utc=observed_utc,
                    notes=login_mode_runtime_notes,
                )
    elif login_backtrack_waiting_rows > 0:
        skipped_rows = max(login_backtrack_waiting_rows - login_mode_selected_rows, 0)
        login_mode_runtime_status = "warn"
        login_mode_runtime_value = "login_backtrack_waiting"
        login_mode_runtime_notes = (
            f"active=0;waiting_rows={login_backtrack_waiting_rows};"
            f"bbp_waiting_rows={login_mode_bbp_backtrack_waiting_rows};"
            f"skipped_rows={skipped_rows};normal_rows_selected={processed_target}"
        )

    evaluated_rows = pass_rows + fail_rows + retry_rows
    pass_ratio = (pass_rows / evaluated_rows) if evaluated_rows > 0 else 0.0
    pass_balance_status = "ok"
    pass_balance_notes = f"pass_ratio={pass_ratio:.4f}"
    if evaluated_rows == 0:
        pass_balance_status = "warn"
        pass_balance_notes = "no_evaluated_rows"
    elif pass_ratio >= 0.95 and evaluated_rows >= 20:
        pass_balance_status = "warn"
        pass_balance_notes = f"pass_ratio_high={pass_ratio:.4f}"

    runtime_status = "ok"
    runtime_notes = (
        f"processed_rows={processed_rows};"
        f"expanded_candidate_rows={expanded_candidate_rows};"
        f"stage_mode={requested_stage_mode};"
        f"price_source={requested_price_source};"
        f"catalog_max_candidates={effective_catalog_max_candidates};"
        f"scrape_page_load_timeout_seconds={effective_scrape_page_load_timeout:.1f};"
        f"pricing_min_interval_seconds={effective_pricing_min_interval:.2f}"
    )
    if processed_rows == 0:
        runtime_status = "warn"
        runtime_notes = (
            "no_pending_rows_processed;"
            f"expanded_candidate_rows={expanded_candidate_rows};"
            f"stage_mode={requested_stage_mode};"
            f"price_source={requested_price_source};"
            f"catalog_max_candidates={effective_catalog_max_candidates};"
            f"scrape_page_load_timeout_seconds={effective_scrape_page_load_timeout:.1f};"
            f"pricing_min_interval_seconds={effective_pricing_min_interval:.2f}"
        )

    scrape_failed_rows = max(scrape_attempted_rows - scrape_success_rows, 0)
    scrape_captured_rows = int(len(scrape_updates_map))
    evidence_status = "ok"
    evidence_notes = (
        f"attempted={scrape_attempted_rows};"
        f"captured={scrape_captured_rows};"
        f"success={scrape_success_rows};"
        f"failed={scrape_failed_rows}"
    )
    if scrape_attempted_rows > 0 and scrape_captured_rows == 0:
        evidence_status = "fail"
        evidence_notes = f"{evidence_notes};capture_failed"
    elif scrape_attempted_rows == 0:
        evidence_status = "warn"
        evidence_notes = f"{evidence_notes};no_rows_reached_scrape_stage"
    if requested_stage_mode == F061_STAGE_MODE_API_ONLY and processed_rows > 0:
        evidence_status = "ok"
        evidence_notes = f"{evidence_notes};api_only_browser_skipped"

    chart_daily_status = "ok"
    chart_daily_notes = (
        f"attempted={scrape_attempted_rows};"
        f"captured_rows={chart_daily_rows_captured}"
    )
    if scrape_attempted_rows > 0 and chart_daily_rows_captured == 0:
        chart_daily_status = "fail"
        chart_daily_notes = f"{chart_daily_notes};capture_failed"
    elif scrape_attempted_rows == 0:
        chart_daily_status = "warn"
        chart_daily_notes = f"{chart_daily_notes};no_rows_reached_scrape_stage"
    if requested_stage_mode == F061_STAGE_MODE_API_ONLY and processed_rows > 0:
        chart_daily_status = "ok"
        chart_daily_notes = f"{chart_daily_notes};api_only_browser_skipped"

    seller_rank_populated_rows = sum(
        1 for payload in scrape_updates_map.values() if _normalize_text(payload.get("bbp_seller_rank_1_name", "")) != ""
    )
    seller_rank_status = "ok"
    seller_rank_notes = f"scrape_captured={scrape_captured_rows};rank_1_populated={seller_rank_populated_rows}"
    if scrape_captured_rows > 0 and seller_rank_populated_rows == 0:
        seller_rank_status = "warn"
        seller_rank_notes = f"{seller_rank_notes};rank_1_not_populated"
    elif scrape_captured_rows == 0:
        seller_rank_status = "warn"
        seller_rank_notes = f"{seller_rank_notes};no_scrape_evidence_rows"
    if requested_stage_mode == F061_STAGE_MODE_API_ONLY and processed_rows > 0:
        seller_rank_status = "ok"
        seller_rank_notes = f"{seller_rank_notes};api_only_browser_skipped"

    speed_ledger_path = root_path / get_f_output_contract("f_scanner_speed_ledger_live").rel_path
    speed_ledger_rows = len(speed_ledger_new_rows)
    speed_total_seconds = sum(_parse_float(row.get("total_seconds", 0.0), 0.0) for row in speed_ledger_new_rows)
    speed_pricing_wait_seconds = sum(
        _parse_float(row.get("pricing_wait_seconds", 0.0), 0.0) for row in speed_ledger_new_rows
    )
    speed_browser_blocked_rows = sum(
        1 for row in speed_ledger_new_rows if _normalize_text(row.get("browser_blocked_flag", "")) == "1"
    )
    speed_429_count = sum(_parse_nonnegative_int(row.get("api_429_count", 0), default=0) for row in speed_ledger_new_rows)
    pricing_wait_ratio = (speed_pricing_wait_seconds / speed_total_seconds) if speed_total_seconds > 0 else 0.0
    speed_ledger_status = "ok"
    speed_ledger_notes = (
        f"ledger_rows={speed_ledger_rows};"
        f"processed_rows={processed_rows};"
        f"total_seconds={speed_total_seconds:.3f};"
        f"api_429_count={speed_429_count}"
    )
    if processed_rows > 0 and speed_ledger_rows == 0:
        speed_ledger_status = "fail"
        speed_ledger_notes = f"{speed_ledger_notes};missing_speed_rows"
    elif processed_rows == 0:
        speed_ledger_status = "warn"
        speed_ledger_notes = f"{speed_ledger_notes};no_rows_processed"

    speed_bottleneck_status = "ok"
    speed_bottleneck_notes = (
        f"pricing_wait_seconds={speed_pricing_wait_seconds:.3f};"
        f"pricing_wait_ratio={pricing_wait_ratio:.4f};"
        f"browser_blocked_rows={speed_browser_blocked_rows}"
    )
    if speed_browser_blocked_rows > 0:
        speed_bottleneck_status = "warn"
        speed_bottleneck_notes = f"{speed_bottleneck_notes};browser_block_signal_seen"
    elif processed_rows > 0 and pricing_wait_ratio > 0.4:
        speed_bottleneck_status = "warn"
        speed_bottleneck_notes = f"{speed_bottleneck_notes};pricing_wait_above_40pct"

    health_rows = [
        {
            "check": "feeder_legacy_first_checks_source_contract",
            "status": "ok",
            "value": str(len(supplier_queue_all)),
            "notes": "active_run_contract_valid",
            "observed_utc": observed_utc,
            "source_path": str(root_path / get_f_output_contract("supplier_price_list_active_run").rel_path),
        },
        {
            "check": "feeder_legacy_first_checks_runtime",
            "status": runtime_status,
            "value": str(processed_rows),
            "notes": runtime_notes,
            "observed_utc": observed_utc,
            "source_path": str(supplier_active_path),
        },
        {
            "check": "feeder_legacy_first_checks_pass_balance",
            "status": pass_balance_status,
            "value": str(pass_rows),
            "notes": pass_balance_notes,
            "observed_utc": observed_utc,
            "source_path": str(root_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path),
        },
        {
            "check": "feeder_legacy_scrape_evidence_runtime",
            "status": evidence_status,
            "value": str(scrape_captured_rows),
            "notes": evidence_notes,
            "observed_utc": observed_utc,
            "source_path": str(root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path),
        },
        {
            "check": "feeder_legacy_chart_daily_raw_runtime",
            "status": chart_daily_status,
            "value": str(chart_daily_rows_captured),
            "notes": chart_daily_notes,
            "observed_utc": observed_utc,
            "source_path": str(root_path / get_f_output_contract("feeder_legacy_chart_daily_raw_live").rel_path),
        },
        {
            "check": "feeder_bbp_seller_rank_capture_runtime",
            "status": seller_rank_status,
            "value": str(seller_rank_populated_rows),
            "notes": seller_rank_notes,
            "observed_utc": observed_utc,
            "source_path": str(root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path),
        },
        {
            "check": "f_scanner_speed_ledger_runtime",
            "status": speed_ledger_status,
            "value": str(speed_ledger_rows),
            "notes": speed_ledger_notes,
            "observed_utc": observed_utc,
            "source_path": str(speed_ledger_path),
        },
        {
            "check": "f_scanner_speed_bottleneck_runtime",
            "status": speed_bottleneck_status,
            "value": _format_float(pricing_wait_ratio, 4),
            "notes": speed_bottleneck_notes,
            "observed_utc": observed_utc,
            "source_path": str(speed_ledger_path),
        },
        {
            "check": "login_backtrack_pending_rows",
            "status": "warn" if login_backtrack_pending_after > 0 else "ok",
            "value": str(login_backtrack_pending_after),
            "notes": (
                f"new_pending_rows={login_backtrack_pending_rows};"
                f"merged_rows={login_backtrack_merged_rows};ledger_rows={len(login_backtrack_written)}"
            ),
            "observed_utc": observed_utc,
            "source_path": str(root_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path),
        },
        {
            "check": "f061_login_mode_runtime",
            "status": login_mode_runtime_status,
            "value": login_mode_runtime_value,
            "notes": login_mode_runtime_notes,
            "observed_utc": observed_utc,
            "source_path": _normalize_text(os.environ.get(F061_LOGIN_MODE_REQUEST_PATH_ENV, "")),
        },
        {
            "check": "dashboard_yes_no_unresolved_rows",
            "status": "warn" if dashboard_yes_no_unresolved_rows > 0 else "ok",
            "value": str(dashboard_yes_no_unresolved_rows),
            "notes": f"max_attempts={F061_DASHBOARD_YES_NO_MAX_BACKTRACK_ATTEMPTS};not_completed={dashboard_yes_no_unresolved_rows}",
            "observed_utc": observed_utc,
            "source_path": str(root_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path),
        },
        {
            "check": "dashboard_missing_on_hard_fail_rows",
            "status": "warn" if dashboard_missing_on_hard_fail_rows > 0 else "ok",
            "value": str(dashboard_missing_on_hard_fail_rows),
            "notes": "hard_fail_rows_kept_failed;dashboard_yes_no_missing;pass_requires_dashboard_signal",
            "observed_utc": observed_utc,
            "source_path": str(root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path),
        },
        _pre_review_gate_health_row(
            observed_utc=observed_utc,
            source_path=root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path,
        ),
        _economic_pre_review_hard_stop_health_row(
            observed_utc=observed_utc,
            source_path=root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path,
        ),
        *build_timeout_policy_health_rows(
            root=root_path,
            screening_state_df=supplier_screening_df,
            observed_utc=observed_utc,
        ),
    ]
    _write_contract_df(pd.DataFrame(health_rows), "feeder_legacy_sheet_health", root_path)
    pricing_stats = adapter.pricing_stats() if hasattr(adapter, "pricing_stats") else {}
    endpoint_stats = adapter.endpoint_stats() if hasattr(adapter, "endpoint_stats") else {}
    endpoint_intervals = (
        adapter.endpoint_intervals_seconds() if hasattr(adapter, "endpoint_intervals_seconds") else {}
    )

    summary = {
        "status": "success",
        "supplier_id": supplier_id,
        "mode": requested_mode,
        "stage_mode": requested_stage_mode,
        "price_source": requested_price_source,
        "pricing_min_interval_seconds": round(effective_pricing_min_interval, 2),
        "catalog_min_interval_seconds": round(effective_catalog_min_interval, 2),
        "catalog_max_candidates": int(effective_catalog_max_candidates),
        "scrape_page_load_timeout_seconds": round(effective_scrape_page_load_timeout, 1),
        "hazmat_min_interval_seconds": round(effective_hazmat_min_interval, 2),
        "fees_min_interval_seconds": round(effective_fees_min_interval, 2),
        "processed_rows": processed_rows,
        "expanded_candidate_rows": expanded_candidate_rows,
        "pending_rows": pending_after,
        "pass_rows": pass_rows,
        "fail_rows": fail_rows,
        "retry_rows": retry_rows,
        "allowlist_status": allowlist_status,
        "allowlist_path": allowlist_path_text,
        "allowlist_rows": int(len(allowlist_ids)),
        "allowlist_selected_rows": int(allowlist_selected_rows),
        "scrape_attempted_rows": scrape_attempted_rows,
        "scrape_success_rows": scrape_success_rows,
        "scrape_failed_rows": scrape_failed_rows,
        "chart_daily_rows_captured": chart_daily_rows_captured,
        "status_counts": status_counter,
        "pricing_stats": pricing_stats,
        "endpoint_stats": endpoint_stats,
        "endpoint_intervals_seconds": endpoint_intervals,
        "scanner_speed_ledger_rows": int(speed_ledger_rows),
        "scanner_speed_total_seconds": round(speed_total_seconds, 3),
        "scanner_speed_pricing_wait_ratio": round(pricing_wait_ratio, 4),
        "scanner_speed_browser_blocked_rows": int(speed_browser_blocked_rows),
        "login_backtrack_pending_rows": int(login_backtrack_pending_after),
        "login_backtrack_new_pending_rows": int(login_backtrack_pending_rows),
        "login_backtrack_merged_rows": int(login_backtrack_merged_rows),
        "login_backtrack_ledger_rows": int(len(login_backtrack_written)),
        "rescan_retry_pending_rows": int(rescan_retry_pending_rows),
        "rescan_retry_exhausted_rows": int(rescan_retry_exhausted_rows),
        "browser_stage_ready_rows": int(browser_stage_ready_rows),
        "rescan_max_active_attempts": int(_max_active_rescan_attempts()),
        "login_mode_active": bool(login_mode_active),
        "login_mode_selected_rows": int(login_mode_selected_rows),
        "login_mode_bbp_selected_rows": int(login_mode_bbp_selected_rows),
        "login_backtrack_skipped_rows": int(
            max(login_backtrack_waiting_rows - login_mode_selected_rows, 0) if not login_mode_active else 0
        ),
        "login_mode_runtime_status": login_mode_runtime_value,
        "dashboard_yes_no_unresolved_rows": int(dashboard_yes_no_unresolved_rows),
        "dashboard_missing_on_hard_fail_rows": int(dashboard_missing_on_hard_fail_rows),
        "active_run_rows": int(len(active_written)),
        "run_state_rows": int(len(run_state_written)),
        "screening_row_state_rows": int(len(screening_state_written)),
        "first_checks_rows": int(len(first_written)),
        "scrape_evidence_rows": int(len(scrape_evidence_written)),
        "chart_daily_raw_rows": int(len(chart_daily_written)),
        "scanner_speed_ledger_path": str(root_path / get_f_output_contract("f_scanner_speed_ledger_live").rel_path),
        "screening_row_state_path": str(root_path / get_f_output_contract("f_screening_row_state_live").rel_path),
        "first_checks_path": str(root_path / get_f_output_contract("feeder_legacy_first_checks_live").rel_path),
        "scrape_evidence_path": str(root_path / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path),
        "chart_daily_raw_path": str(root_path / get_f_output_contract("feeder_legacy_chart_daily_raw_live").rel_path),
        "active_run_path": str(root_path / get_f_output_contract("supplier_price_list_active_run").rel_path),
        "login_backtrack_evidence_path": str(root_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path),
    }
    print(summary)
    if adapter_local_created and hasattr(adapter, "close"):
        try:
            adapter.close()
        except Exception:
            pass
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run legacy First Checks style Amazon prechecks on local supplier active-run rows."
    )
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", required=True)
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--scan-utc", default=None)
    parser.add_argument("--scrape-mode", default="legacy_module", choices=["disabled", "legacy_module"])
    parser.add_argument(
        "--price-source",
        default=os.environ.get(F061_PRICE_SOURCE_ENV, PRICE_SOURCE_LEGACY),
        choices=sorted(PRICE_SOURCE_ALLOWED),
    )
    parser.add_argument("--pricing-min-interval-seconds", type=float, default=None)
    parser.add_argument(
        "--legacy-scanner-root",
        default=str(ROOT / "scripts" / "flows" / "F" / "legacy_scanner_2_1"),
    )
    parser.add_argument("--catalog-max-candidates", type=int, default=None)
    parser.add_argument("--allowlist-path", default=None)
    parser.add_argument(
        "--stage-mode",
        default=os.environ.get(F061_STAGE_MODE_ENV, F061_STAGE_MODE_LEGACY_FULL),
        choices=sorted(F061_STAGE_MODE_ALLOWED),
    )
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--loop-sleep-seconds", type=float, default=15.0)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    startup_cleanup = _cleanup_specialist_chrome_windows()
    print({"startup_cleanup": startup_cleanup})
    shared_adapter = None
    try:
        if args.loop:
            shared_adapter = LegacyCompatibleAmazonAdapter(
                legacy_scanner_root=args.legacy_scanner_root,
                scrape_mode=args.scrape_mode,
                price_source=args.price_source,
                pricing_retries=_parse_nonnegative_int(os.environ.get(F061_PRICING_RETRIES_ENV, "3"), default=3),
                root_path=root if root is not None else get_f_path_contract().root,
                catalog_min_interval_seconds=_parse_positive_float(
                    os.environ.get(F061_CATALOG_MIN_INTERVAL_SECONDS_ENV, "0.5"),
                    default=0.5,
                ),
                hazmat_min_interval_seconds=_parse_positive_float(
                    os.environ.get(F061_HAZMAT_MIN_INTERVAL_SECONDS_ENV, "1.0"),
                    default=1.0,
                ),
                pricing_min_interval_seconds=(
                    _parse_positive_float(
                        args.pricing_min_interval_seconds,
                        default=_parse_positive_float(
                            os.environ.get(F061_PRICING_MIN_INTERVAL_SECONDS_ENV, "30"),
                            default=30.0,
                        ),
                    )
                    if args.pricing_min_interval_seconds is not None
                    else _parse_positive_float(
                        os.environ.get(F061_PRICING_MIN_INTERVAL_SECONDS_ENV, "30"),
                        default=30.0,
                    )
                ),
                fees_min_interval_seconds=_parse_positive_float(
                    os.environ.get(F061_FEES_MIN_INTERVAL_SECONDS_ENV, "1.0"),
                    default=1.0,
                ),
                scrape_page_load_timeout_seconds=_parse_positive_float(
                    os.environ.get(F061_SCRAPE_PAGE_LOAD_TIMEOUT_SECONDS_ENV, "45"),
                    default=45.0,
                ),
            )
            sleep_seconds = max(args.loop_sleep_seconds, 0.0)
            while True:
                summary = run_legacy_first_checks_local(
                    root=root,
                    supplier_id=args.supplier_id,
                    max_rows=args.max_rows,
                    scan_utc=args.scan_utc,
                    scrape_mode=args.scrape_mode,
                    legacy_scanner_root=args.legacy_scanner_root,
                    price_source=args.price_source,
                    pricing_min_interval_seconds=args.pricing_min_interval_seconds,
                    catalog_max_candidates=args.catalog_max_candidates,
                    adapter=shared_adapter,
                    allowlist_path=args.allowlist_path,
                    stage_mode=args.stage_mode,
                )
                if int(summary.get("pending_rows", 0) or 0) <= 0:
                    break
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
        else:
            run_legacy_first_checks_local(
                root=root,
                supplier_id=args.supplier_id,
                max_rows=args.max_rows,
                scan_utc=args.scan_utc,
                scrape_mode=args.scrape_mode,
                legacy_scanner_root=args.legacy_scanner_root,
                price_source=args.price_source,
                pricing_min_interval_seconds=args.pricing_min_interval_seconds,
                catalog_max_candidates=args.catalog_max_candidates,
                allowlist_path=args.allowlist_path,
                stage_mode=args.stage_mode,
            )
    finally:
        if shared_adapter is not None:
            try:
                shared_adapter.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
