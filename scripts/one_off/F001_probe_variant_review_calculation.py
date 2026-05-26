from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import undetected_chromedriver as uc


ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIR = ROOT / "scripts" / "flows" / "F" / "legacy_scanner_2_1"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

from WebscraperS2 import scrape_main_page  # type: ignore  # noqa: E402


DEFAULT_ASINS = [
    "B08S8NGQ3J",
    "B007O7AZBG",
    "B01N0L42FZ",
    "B09PCC9RCR",
    "B07GDS948W",
    "B09XF8ZZG6",
    "B08CSTD1S2",
    "B07QF3J61F",
    "B0D8N6D886",
    "B07GFTX7TY",
]


def _build_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.binary_location = r"C:\Chrome_UC136\bin\chrome.exe"
    options.add_argument(r"--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136")
    options.add_argument(r"--profile-directory=BBPProfile")
    options.add_argument("--flag-switches-begin")
    options.add_argument("--flag-switches-end")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-infobars")
    options.add_argument("--remote-debugging-port=9222")

    return uc.Chrome(
        options=options,
        use_subprocess=True,
        driver_executable_path=r"C:\Users\Luke\.nuget\packages\selenium.webdriver.chromedriver\136.0.7103.4800-beta\driver\win32\chromedriver.exe",
    )


def _run_probe(asins: list[str]) -> list[dict[str, str]]:
    driver = _build_driver()
    rows: list[dict[str, str]] = []
    try:
        for index, asin in enumerate(asins, start=1):
            asin_clean = str(asin).strip().upper()
            if not asin_clean:
                continue
            driver.get(f"https://www.amazon.co.uk/dp/{asin_clean}")
            time.sleep(1)
            data = scrape_main_page(driver)
            rows.append(
                {
                    "index": str(index),
                    "asin": asin_clean,
                    "variant_mode": str(data.get("variant_mode", "N/A")),
                    "total_reviews_before_filter": str(data.get("total_reviews_before_filter", "N/A")),
                    "variant_filter_reviews": str(data.get("variant_filter_reviews", "N/A")),
                    "matching_variant_reviews": str(data.get("matching_variant_reviews", "N/A")),
                    "global_ratings": str(data.get("global_ratings", "N/A")),
                    "estimated_variant_ratings": str(data.get("estimated_variant_ratings", "N/A")),
                    "variant_reviews_scored": str(data.get("variant_reviews", "N/A")),
                    "historical_uk_reviews": str(data.get("historical_uk_reviews", "N/A")),
                    "three_month_uk_reviews": str(data.get("reviews_text", "N/A")),
                    "scan_date": str(data.get("scan_date", "N/A")),
                }
            )
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return rows


def _write_csv(rows: list[dict[str, str]]) -> Path:
    out_dir = ROOT / "out" / "systems" / "F" / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    out_path = out_dir / f"variant_review_probe_{ts}.csv"
    columns = [
        "index",
        "asin",
        "variant_mode",
        "total_reviews_before_filter",
        "variant_filter_reviews",
        "matching_variant_reviews",
        "global_ratings",
        "estimated_variant_ratings",
        "variant_reviews_scored",
        "historical_uk_reviews",
        "three_month_uk_reviews",
        "scan_date",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe variant review estimation for a fixed ASIN list.")
    parser.add_argument("--asin", action="append", dest="asins", default=[], help="ASIN to test (repeatable).")
    args = parser.parse_args()

    asins = [str(v).strip().upper() for v in (args.asins or []) if str(v).strip()]
    if not asins:
        asins = DEFAULT_ASINS

    rows = _run_probe(asins)
    out_path = _write_csv(rows)
    print(f"rows={len(rows)}")
    print(f"output={out_path}")
    for row in rows:
        print(
            f"{row['asin']} mode={row['variant_mode']} total={row['total_reviews_before_filter']} "
            f"filter={row['variant_filter_reviews']} match={row['matching_variant_reviews']} global={row['global_ratings']} "
            f"estimate={row['estimated_variant_ratings']}"
        )


if __name__ == "__main__":
    main()
