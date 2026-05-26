from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BBP_USER_DATA_DIR = r"C:\Users\Luke\AppData\Local\Chrome_UC136"
DEFAULT_BBP_PROFILE_DIR = "Profile 2"
DEFAULT_LEGACY_ROOT = Path("scripts") / "flows" / "F" / "legacy_scanner_2_1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(_normalize_text(value).replace(",", ""))
    except Exception:
        return default


def _latest_practice_list(root: Path) -> Path:
    diag = root / "out" / "systems" / "F" / "diagnostics"
    candidates = sorted(diag.glob("f061_success_scrape_practice_list_*.csv"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError("No f061_success_scrape_practice_list_*.csv file found")
    return candidates[-1]


def _read_rows(path: Path, limit: int) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    rows = [row for row in rows if _normalize_text(row.get("asin"))]
    if limit > 0:
        rows = rows[:limit]
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _prepare_f061_environment(args: argparse.Namespace) -> None:
    os.environ["F061_BBP_USER_DATA_DIR"] = args.bbp_user_data_dir
    os.environ["F061_BBP_PROFILE_DIR"] = args.bbp_profile_dir
    os.environ["F061_REQUIRE_BBP_EXTENSION"] = "1"
    browser_mode = _normalize_text(args.browser_mode).lower()
    if browser_mode not in {"visible", "minimized"}:
        browser_mode = "visible"
    os.environ["F061_BACKGROUND_BROWSER_MODE"] = browser_mode
    os.environ["F061_SHOW_WINDOWS"] = "1" if browser_mode == "visible" else "0"
    os.environ["FPM_LIVE_HIDE_SCRAPER_WINDOWS"] = "0" if browser_mode == "visible" else "1"
    os.environ["F061_WEBSCRAPE_MODE"] = "data"
    os.environ["F061_MANUAL_BBP_LOGIN_WAIT_SECONDS"] = str(max(float(args.login_hold_seconds), 0.0))
    os.environ.setdefault("F061_HUMAN_SLEEP_SCALE", "0.25")


def _import_adapter(root: Path):
    f_root = root / "scripts" / "flows" / "F"
    if str(f_root) not in sys.path:
        sys.path.insert(0, str(f_root))
    from F061_run_legacy_first_checks_local import LegacyCompatibleAmazonAdapter  # type: ignore

    return LegacyCompatibleAmazonAdapter


def _result_row(source: dict[str, str], result: dict[str, Any], started_utc: str, finished_utc: str) -> dict[str, Any]:
    scraped = result.get("scraped_data") if isinstance(result.get("scraped_data"), dict) else {}
    scrape_data_available = any(
        _normalize_text(scraped.get(key, "")).upper() not in {"", "N/A"}
        for key in (
            "bbp_final_sell_price",
            "bbp_sales_chart_source",
            "history_source",
            "bbp_sales_history_text",
        )
    )
    return {
        "practice_id": source.get("practice_id", ""),
        "source_observed_utc": source.get("source_observed_utc", ""),
        "supplier_sku": source.get("supplier_sku", ""),
        "asin": source.get("asin", ""),
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "business_pass": bool(result.get("success", False)),
        "scrape_data_available": scrape_data_available,
        "error": _normalize_text(result.get("error", "")),
        "dashboard_yes_no": _normalize_text(scraped.get("bbp_dashboard_yes_or_no", "")),
        "dashboard_delivery_classification": _normalize_text(
            scraped.get("bbp_dashboard_delivery_classification", "")
        ),
        "dashboard_separate_delivery_required": _normalize_text(
            scraped.get("bbp_dashboard_separate_delivery_required", "")
        ),
        "history_source": _normalize_text(scraped.get("history_source", "")),
        "bbp_sales_chart_source": _normalize_text(scraped.get("bbp_sales_chart_source", "")),
        "bbp_final_sell_price": _normalize_text(scraped.get("bbp_final_sell_price", "")),
        "checks_failed": _normalize_text(scraped.get("checks_failed", "")),
        "fail_codes": _normalize_text(scraped.get("fail_codes", "")),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = _root()
    input_path = Path(args.input) if args.input else _latest_practice_list(root)
    if not input_path.is_absolute():
        input_path = root / input_path
    rows = _read_rows(input_path, max(int(args.limit), 0))

    stamp = _utc_now_iso().replace("-", "").replace(":", "")
    out_dir = root / "out" / "systems" / "F" / "diagnostics"
    csv_out = out_dir / f"f061_practice_scrape_results_{stamp}.csv"
    json_out = out_dir / f"f061_practice_scrape_results_{stamp}.json"
    heartbeat_path = out_dir / "f061_practice_scrape_status.json"

    _prepare_f061_environment(args)
    Adapter = _import_adapter(root)
    adapter = Adapter(
        legacy_scanner_root=str(root / DEFAULT_LEGACY_ROOT),
        scrape_mode="legacy_module",
        root_path=root,
        scrape_page_load_timeout_seconds=float(args.page_load_timeout_seconds),
    )

    payload: dict[str, Any] = {
        "started_utc": _utc_now_iso(),
        "finished_utc": "",
        "mode": "f061_practice_list_normal_mode",
        "input": str(input_path),
        "bbp_user_data_dir": args.bbp_user_data_dir,
        "bbp_profile_dir": args.bbp_profile_dir,
        "browser_mode": _normalize_text(args.browser_mode).lower() or "visible",
        "login_hold_seconds": float(args.login_hold_seconds),
        "limit": len(rows),
        "rows": [],
        "business_pass_count": 0,
        "scrape_data_count": 0,
        "login_required_count": 0,
        "failure_count": 0,
    }
    _write_json(heartbeat_path, {**payload, "state": "started", "updated_utc": _utc_now_iso()})

    try:
        for index, row in enumerate(rows, start=1):
            started_utc = _utc_now_iso()
            _write_json(
                heartbeat_path,
                {
                    **payload,
                    "state": "running",
                    "updated_utc": started_utc,
                    "current_index": index,
                    "current_asin": row.get("asin", ""),
                    "current_supplier_sku": row.get("supplier_sku", ""),
                },
            )
            result = adapter.process_scrape(
                asin=_normalize_text(row.get("asin")),
                break_even_price=_safe_float(row.get("break_even")),
                min_sell_price=_safe_float(row.get("min_sell_price")),
                product_cost=_safe_float(row.get("practice_product_cost") or row.get("break_even"), 1.0),
                row_index=index,
                brand_name="",
                vat_rate=20.0,
                skip_date_scraping=True,
                old_chrome_forced=False,
            )
            finished_utc = _utc_now_iso()
            out_row = _result_row(row, result if isinstance(result, dict) else {}, started_utc, finished_utc)
            payload["rows"].append(out_row)
            if bool(out_row["business_pass"]):
                payload["business_pass_count"] = int(payload["business_pass_count"]) + 1
            if bool(out_row["scrape_data_available"]):
                payload["scrape_data_count"] = int(payload["scrape_data_count"]) + 1
            if bool(out_row["scrape_data_available"]):
                pass
            elif "BBP_LOGIN_REQUIRED" in _normalize_text(out_row.get("error")):
                payload["login_required_count"] = int(payload["login_required_count"]) + 1
            else:
                payload["failure_count"] = int(payload["failure_count"]) + 1
            _write_csv(csv_out, payload["rows"])
            _write_json(heartbeat_path, {**payload, "state": "running", "updated_utc": finished_utc})
            if args.stop_after_login_required and "BBP_LOGIN_REQUIRED" in _normalize_text(out_row.get("error")):
                break
            time.sleep(max(float(args.row_pause_seconds), 0.0))
    finally:
        final_hold_seconds = max(float(args.final_hold_seconds), 0.0)
        if final_hold_seconds > 0:
            hold_started_utc = _utc_now_iso()
            _write_json(
                heartbeat_path,
                {
                    **payload,
                    "state": "holding_browser_open",
                    "updated_utc": hold_started_utc,
                    "final_hold_seconds": final_hold_seconds,
                },
            )
            print(f"Holding scanner browser open for {final_hold_seconds:.0f} seconds. Started UTC: {hold_started_utc}")
            time.sleep(final_hold_seconds)
        adapter.close()

    payload["finished_utc"] = _utc_now_iso()
    payload["csv_output"] = str(csv_out)
    payload["json_output"] = str(json_out)
    payload["state"] = "finished"
    _write_csv(csv_out, payload["rows"])
    _write_json(json_out, payload)
    _write_json(heartbeat_path, {**payload, "updated_utc": _utc_now_iso()})
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a no-Sheets F061 normal-mode practice scrape list.")
    parser.add_argument("--input", default="")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--bbp-user-data-dir", default=DEFAULT_BBP_USER_DATA_DIR)
    parser.add_argument("--bbp-profile-dir", default=DEFAULT_BBP_PROFILE_DIR)
    parser.add_argument("--browser-mode", choices=["visible", "minimized"], default="visible")
    parser.add_argument("--login-hold-seconds", type=float, default=900.0)
    parser.add_argument("--page-load-timeout-seconds", type=float, default=45.0)
    parser.add_argument("--row-pause-seconds", type=float, default=1.0)
    parser.add_argument("--final-hold-seconds", type=float, default=0.0)
    parser.add_argument("--stop-after-login-required", action="store_true")
    args = parser.parse_args()
    result = run(args)
    print(
        json.dumps(
            {
                "state": result.get("state"),
                "business_pass_count": result.get("business_pass_count"),
                "scrape_data_count": result.get("scrape_data_count"),
                "login_required_count": result.get("login_required_count"),
                "failure_count": result.get("failure_count"),
                "csv_output": result.get("csv_output"),
                "json_output": result.get("json_output"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
