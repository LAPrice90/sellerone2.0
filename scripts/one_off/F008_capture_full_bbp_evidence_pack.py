from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F061_run_legacy_first_checks_local import LegacyCompatibleAmazonAdapter


DEFAULT_ASIN_PACK_PATH = ROOT / "out" / "analysis_reports" / "f_live_asin_validation_pack_latest.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_LEGACY_SCANNER_ROOT = ROOT / "scripts" / "flows" / "F" / "legacy_scanner_2_1"
DEFAULT_BREAK_EVEN_GBP = 25.0
DEFAULT_MIN_SELL_GBP = 26.0
DEFAULT_PRODUCT_COST_GBP = 15.0
DEFAULT_VAT_RATE = 0.2

_ENV_SNAPSHOT_KEYS = (
    "BBP_SECTION_SNAPSHOT_ENABLED",
    "BBP_SECTION_SNAPSHOT_DIR",
    "BBP_SECTION_SNAPSHOT_INCLUDE_OUTER_HTML",
    "F061_WEBSCRAPE_MODE",
)


@dataclass(frozen=True)
class FullBbpCaptureBuildResult:
    manifest_df: pd.DataFrame
    manifest_path: Path
    latest_path: Path
    raw_dir: Path
    screenshot_dir: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_timestamp_slug(observed_utc: str) -> str:
    dt = datetime.strptime(observed_utc, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _safe_filename_piece(value: object, *, fallback: str) -> str:
    raw = _normalize_text(value)
    if raw == "":
        return fallback
    chars = [ch if (ch.isalnum() or ch in {".", "_", "-"}) else "_" for ch in raw]
    cleaned = "".join(chars).strip("._-")
    if cleaned == "":
        return fallback
    return cleaned[:80]


def _asin_rows_from_pack(pack_df: pd.DataFrame, *, max_asins: int) -> list[dict[str, str]]:
    if pack_df.empty:
        return []
    work = pack_df.copy()
    if "sample_rank" in work.columns:
        work["_sample_rank_num"] = pd.to_numeric(work["sample_rank"], errors="coerce")
        work = work.sort_values(["_sample_rank_num", "sample_rank"], ascending=[True, True], kind="stable")
    seen_asins: set[str] = set()
    rows: list[dict[str, str]] = []
    for _, row in work.iterrows():
        asin = _normalize_text(row.get("asin", ""))
        asin_key = _normalize_key(asin)
        if asin_key == "" or asin_key in seen_asins:
            continue
        seen_asins.add(asin_key)
        rows.append(
            {
                "asin": asin,
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "validation_case": _normalize_text(row.get("validation_case", "")),
                "sample_rank": _normalize_text(row.get("sample_rank", "")),
                "amazon_link": _normalize_text(row.get("amazon_link", "")),
            }
        )
        if max_asins > 0 and len(rows) >= max_asins:
            break
    return rows


def _set_capture_env(snapshot_dir: Path, *, webscrape_mode: str) -> dict[str, str | None]:
    previous = {key: os.environ.get(key) for key in _ENV_SNAPSHOT_KEYS}
    os.environ["BBP_SECTION_SNAPSHOT_ENABLED"] = "1"
    os.environ["BBP_SECTION_SNAPSHOT_DIR"] = str(snapshot_dir)
    os.environ["BBP_SECTION_SNAPSHOT_INCLUDE_OUTER_HTML"] = "1"
    os.environ["F061_WEBSCRAPE_MODE"] = _normalize_text(webscrape_mode) or "data"
    return previous


def _restore_capture_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _capture_screenshots_from_adapter(
    adapter: Any,
    *,
    asin: str,
    pass_index: int,
    screenshot_dir: Path,
) -> dict[str, str]:
    out = {
        "bbp_full_screenshot_path": "",
        "bbp_section_screenshot_path": "",
        "bbp_sales_chart_screenshot_path": "",
        "amazon_sold_screenshot_path": "",
        "screenshot_error": "",
    }
    driver = getattr(adapter, "_bbp_driver", None)
    if driver is None:
        out["screenshot_error"] = "missing_bbp_driver"
        return out

    asin_slug = _safe_filename_piece(asin, fallback="asin")
    base = f"{asin_slug}_p{pass_index}"
    errors: list[str] = []

    try:
        full_path = screenshot_dir / f"{base}_bbp_full.png"
        driver.save_screenshot(str(full_path))
        out["bbp_full_screenshot_path"] = str(full_path)
    except Exception as exc:
        errors.append(f"bbp_full:{type(exc).__name__}")

    def _capture_bbp_frame_artifacts() -> bool:
        driver.switch_to.default_content()
        frames = driver.find_elements("id", "bbp-frame")
        if not frames:
            return False
        driver.switch_to.frame(frames[0])

        section_found = False
        sections = driver.find_elements("id", "llpSectionContainer")
        if sections:
            section_path = screenshot_dir / f"{base}_bbp_section.png"
            sections[0].screenshot(str(section_path))
            out["bbp_section_screenshot_path"] = str(section_path)
            section_found = True

        chart_found = False
        chart_elem = None
        for selector in ("#estSalesContent", "#estSalesMonthlyChart"):
            elems = driver.find_elements("css selector", selector)
            if elems:
                chart_elem = elems[0]
                break
        if chart_elem is not None:
            chart_path = screenshot_dir / f"{base}_bbp_sales_chart.png"
            chart_elem.screenshot(str(chart_path))
            out["bbp_sales_chart_screenshot_path"] = str(chart_path)
            chart_found = True

        driver.switch_to.default_content()
        return section_found or chart_found

    try:
        found = _capture_bbp_frame_artifacts()
        if (not found) and asin:
            product_url = f"https://www.amazon.co.uk/dp/{asin}"
            driver.switch_to.default_content()
            driver.get(product_url)
            time.sleep(2.5)
            driver.refresh()
            time.sleep(2.0)
            _capture_bbp_frame_artifacts()
    except Exception as exc:
        errors.append(f"bbp_section_or_chart:{type(exc).__name__}")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    try:
        driver.switch_to.default_content()
        sold_nodes = driver.find_elements(
            "xpath",
            (
                "//*[contains(translate(normalize-space(.),"
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'bought in past month')"
                " or contains(translate(normalize-space(.),"
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sold in past month')"
                " or contains(translate(normalize-space(.),"
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'bought in the last 30 days')]"
            ),
        )
        if sold_nodes:
            sold_path = screenshot_dir / f"{base}_amazon_sold_text.png"
            sold_nodes[0].screenshot(str(sold_path))
            out["amazon_sold_screenshot_path"] = str(sold_path)
    except Exception as exc:
        errors.append(f"amazon_sold:{type(exc).__name__}")
    finally:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    if errors:
        out["screenshot_error"] = "|".join(errors)
    return out


def _default_adapter_factory(
    *,
    legacy_scanner_root: Path,
) -> Callable[[int], LegacyCompatibleAmazonAdapter]:
    def _factory(session_id: int) -> LegacyCompatibleAmazonAdapter:
        _ = session_id
        return LegacyCompatibleAmazonAdapter(
            legacy_scanner_root=str(legacy_scanner_root),
            scrape_mode="legacy_module",
            root_path=ROOT,
        )

    return _factory


def capture_full_bbp_evidence_pack(
    *,
    asin_pack_path: Path = DEFAULT_ASIN_PACK_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    max_asins: int = 10,
    passes: int = 3,
    observed_utc: str | None = None,
    break_even_gbp: float = DEFAULT_BREAK_EVEN_GBP,
    min_sell_gbp: float = DEFAULT_MIN_SELL_GBP,
    product_cost_gbp: float = DEFAULT_PRODUCT_COST_GBP,
    vat_rate: float = DEFAULT_VAT_RATE,
    skip_date_scraping: bool = True,
    webscrape_mode: str = "data",
    legacy_scanner_root: Path = DEFAULT_LEGACY_SCANNER_ROOT,
    adapter_factory: Callable[[int], Any] | None = None,
    screenshot_captor: Callable[[Any, str, int, Path], dict[str, str]] | None = None,
) -> FullBbpCaptureBuildResult:
    capture_utc = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(capture_utc)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / f"f_full_capture_{ts_slug}"
    raw_dir = run_dir / "raw_json"
    screenshot_dir = run_dir / "screenshots"
    snapshot_dir = run_dir / "bbp_section_snapshots"
    raw_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / f"f_full_capture_manifest_{ts_slug}.csv"
    latest_path = output_dir / "f_full_capture_manifest_latest.csv"

    pack_df = _read_csv(asin_pack_path)
    asin_rows = _asin_rows_from_pack(pack_df, max_asins=max(max_asins, 0))

    manifest_rows: list[dict[str, str]] = []
    previous_env = _set_capture_env(snapshot_dir=snapshot_dir, webscrape_mode=webscrape_mode)
    factory = adapter_factory or _default_adapter_factory(legacy_scanner_root=legacy_scanner_root)
    screenshot_fn = screenshot_captor or (lambda adapter, asin, pass_index, out_dir: _capture_screenshots_from_adapter(
        adapter,
        asin=asin,
        pass_index=pass_index,
        screenshot_dir=out_dir,
    ))
    adapters: dict[int, Any] = {}

    try:
        for pass_index in range(1, max(passes, 1) + 1):
            session_id = 1 if pass_index <= 2 else pass_index
            if session_id != 1 and 1 in adapters:
                try:
                    adapters[1].close()
                except Exception:
                    pass
                adapters.pop(1, None)
            if session_id not in adapters:
                adapters[session_id] = factory(session_id)
            adapter = adapters[session_id]

            for row_index, row in enumerate(asin_rows, start=1):
                asin = _normalize_text(row.get("asin", ""))
                if asin == "":
                    continue
                run_id = f"{ts_slug}_{_safe_filename_piece(asin, fallback='asin')}_p{pass_index}"
                capture_status = "success"
                capture_error = ""
                scraped_data: dict[str, Any] = {}
                try:
                    scrape_result = adapter.process_scrape(
                        asin=asin,
                        break_even_price=float(break_even_gbp),
                        min_sell_price=float(min_sell_gbp),
                        product_cost=float(product_cost_gbp),
                        row_index=row_index,
                        brand_name="",
                        vat_rate=float(vat_rate),
                        skip_date_scraping=bool(skip_date_scraping),
                        old_chrome_forced=False,
                    )
                    if not isinstance(scrape_result, dict):
                        capture_status = "failed"
                        capture_error = "invalid_scrape_result"
                    else:
                        capture_status = "success" if bool(scrape_result.get("success", False)) else "failed"
                        capture_error = _normalize_text(scrape_result.get("error", ""))
                        payload = scrape_result.get("scraped_data", {})
                        if isinstance(payload, dict):
                            scraped_data = payload
                except Exception as exc:
                    capture_status = "failed"
                    capture_error = f"SCRAPE_EXCEPTION:{type(exc).__name__}"

                screenshot_payload = screenshot_fn(adapter, asin, pass_index, screenshot_dir)
                bbp_snapshot_path = _normalize_text(scraped_data.get("bbp_section_snapshot_path", ""))
                snapshot_json = {}
                if bbp_snapshot_path != "":
                    snapshot_json = _load_json(Path(bbp_snapshot_path))

                raw_payload = {
                    "run_metadata": {
                        "observed_utc": capture_utc,
                        "run_id": run_id,
                        "asin": asin,
                        "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                        "validation_case": _normalize_text(row.get("validation_case", "")),
                        "sample_rank": _normalize_text(row.get("sample_rank", "")),
                        "pass_index": pass_index,
                        "session_id": session_id,
                        "capture_status": capture_status,
                        "capture_error": capture_error,
                        "skip_date_scraping": "1" if skip_date_scraping else "0",
                        "break_even_gbp": f"{float(break_even_gbp):.2f}",
                        "min_sell_gbp": f"{float(min_sell_gbp):.2f}",
                        "product_cost_gbp": f"{float(product_cost_gbp):.2f}",
                    },
                    "scraped_data": scraped_data,
                    "bbp_section_snapshot_json": snapshot_json,
                    "screenshot_paths": screenshot_payload,
                }
                raw_path = raw_dir / f"{run_id}.json"
                raw_path.write_text(json.dumps(raw_payload, ensure_ascii=True, indent=2), encoding="utf-8")

                manifest_rows.append(
                    {
                        "observed_utc": capture_utc,
                        "run_id": run_id,
                        "asin": asin,
                        "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                        "validation_case": _normalize_text(row.get("validation_case", "")),
                        "sample_rank": _normalize_text(row.get("sample_rank", "")),
                        "pass_index": str(pass_index),
                        "session_id": str(session_id),
                        "capture_status": capture_status,
                        "capture_error": capture_error,
                        "raw_json_path": str(raw_path),
                        "bbp_section_snapshot_path": bbp_snapshot_path,
                        "bbp_snapshot_loaded": "1" if snapshot_json else "0",
                        "bbp_full_screenshot_path": _normalize_text(screenshot_payload.get("bbp_full_screenshot_path", "")),
                        "bbp_section_screenshot_path": _normalize_text(
                            screenshot_payload.get("bbp_section_screenshot_path", "")
                        ),
                        "bbp_sales_chart_screenshot_path": _normalize_text(
                            screenshot_payload.get("bbp_sales_chart_screenshot_path", "")
                        ),
                        "amazon_sold_screenshot_path": _normalize_text(
                            screenshot_payload.get("amazon_sold_screenshot_path", "")
                        ),
                        "screenshot_error": _normalize_text(screenshot_payload.get("screenshot_error", "")),
                        "bbp_sales_chart_source": _normalize_text(scraped_data.get("bbp_sales_chart_source", "")),
                        "bbp_sales_last_completed_month_label": _normalize_text(
                            scraped_data.get("bbp_sales_last_completed_month_label", "")
                        ),
                        "bbp_sales_last_completed_month_units": _normalize_text(
                            scraped_data.get("bbp_sales_last_completed_month_units", "")
                        ),
                        "bbp_sales_current_month_label": _normalize_text(
                            scraped_data.get("bbp_sales_current_month_label", "")
                        ),
                        "bbp_sales_current_month_units": _normalize_text(
                            scraped_data.get("bbp_sales_current_month_units", "")
                        ),
                        "bbp_sales_future_month_count_ignored": _normalize_text(
                            scraped_data.get("bbp_sales_future_month_count_ignored", "")
                        ),
                        "bbp_sales_replay_demand_basis_source": _normalize_text(
                            scraped_data.get("bbp_sales_replay_demand_basis_source", "")
                        ),
                        "bbp_sales_replay_demand_basis_units": _normalize_text(
                            scraped_data.get("bbp_sales_replay_demand_basis_units", "")
                        ),
                    }
                )
    finally:
        for adapter in adapters.values():
            try:
                adapter.close()
            except Exception:
                pass
        _restore_capture_env(previous_env)

    manifest_df = pd.DataFrame(manifest_rows)
    if manifest_df.empty:
        manifest_df = pd.DataFrame(
            columns=[
                "observed_utc",
                "run_id",
                "asin",
                "supplier_sku",
                "validation_case",
                "sample_rank",
                "pass_index",
                "session_id",
                "capture_status",
                "capture_error",
                "raw_json_path",
            ]
        )
    else:
        manifest_df = manifest_df.sort_values(
            ["asin", "pass_index"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)
    manifest_df.to_csv(manifest_path, index=False)
    manifest_df.to_csv(latest_path, index=False)

    success_rows = int((manifest_df.get("capture_status", "").map(_normalize_text) == "success").sum())
    failed_rows = int((manifest_df.get("capture_status", "").map(_normalize_text) == "failed").sum())
    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": capture_utc,
                "asin_pack_path": str(asin_pack_path),
                "asins_selected": int(len(asin_rows)),
                "passes": int(max(passes, 1)),
                "manifest_rows": int(len(manifest_df)),
                "success_rows": success_rows,
                "failed_rows": failed_rows,
                "manifest_path": str(manifest_path),
                "latest_path": str(latest_path),
                "raw_dir": str(raw_dir),
                "screenshot_dir": str(screenshot_dir),
                "snapshot_dir": str(snapshot_dir),
            }
        )
    )
    return FullBbpCaptureBuildResult(
        manifest_df=manifest_df,
        manifest_path=manifest_path,
        latest_path=latest_path,
        raw_dir=raw_dir,
        screenshot_dir=screenshot_dir,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one-off live Chrome BBP full capture for a sampled ASIN pack. "
            "Writes raw JSON artifacts, screenshots, and a manifest."
        )
    )
    parser.add_argument("--asin-pack-path", default=str(DEFAULT_ASIN_PACK_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-asins", type=int, default=10)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    parser.add_argument("--break-even-gbp", type=float, default=DEFAULT_BREAK_EVEN_GBP)
    parser.add_argument("--min-sell-gbp", type=float, default=DEFAULT_MIN_SELL_GBP)
    parser.add_argument("--product-cost-gbp", type=float, default=DEFAULT_PRODUCT_COST_GBP)
    parser.add_argument("--vat-rate", type=float, default=DEFAULT_VAT_RATE)
    parser.add_argument("--skip-date-scraping", action="store_true")
    parser.add_argument("--webscrape-mode", default="data", choices=["data", "decision"])
    parser.add_argument("--legacy-scanner-root", default=str(DEFAULT_LEGACY_SCANNER_ROOT))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    capture_full_bbp_evidence_pack(
        asin_pack_path=Path(args.asin_pack_path),
        output_dir=Path(args.output_dir),
        max_asins=args.max_asins,
        passes=args.passes,
        observed_utc=args.observed_utc,
        break_even_gbp=args.break_even_gbp,
        min_sell_gbp=args.min_sell_gbp,
        product_cost_gbp=args.product_cost_gbp,
        vat_rate=args.vat_rate,
        skip_date_scraping=bool(args.skip_date_scraping),
        webscrape_mode=args.webscrape_mode,
        legacy_scanner_root=Path(args.legacy_scanner_root),
    )


if __name__ == "__main__":
    main()
