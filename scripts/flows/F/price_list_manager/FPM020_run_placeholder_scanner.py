from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import BATCH_ROW_COLUMNS, PLACEHOLDER_SCANNER_RESULT_COLUMNS
from scripts.flows.F.price_list_manager._schemas import BATCH_SCAN_ELIGIBILITY_COLUMNS


OUTCOME_SEQUENCE = [
    ("PASS", "PASS", "", "webscrape", "supplier_offer", "0", "placeholder_pass"),
    ("NOASIN", "FAIL", "NOASIN", "catalog", "global_barcode", "90", "catalog_match_missing"),
    ("OVER50K", "FAIL", "OVER50K", "rank_gate", "global_barcode", "90", "rank_over_limit"),
    ("NOCOST", "FAIL", "NOCOST", "cost_gate", "supplier_offer", "90", "missing_or_invalid_cost"),
    ("ROIFAIL_NEAR", "FAIL", "ROIFAIL", "roi_gate", "supplier_offer", "60", "roi_near_threshold"),
    ("ROIFAIL_FAR", "FAIL", "ROIFAIL", "roi_gate", "supplier_offer", "90", "roi_far_below_threshold"),
    ("SCRAPEFAIL", "RESCAN", "SCRAPEFAIL", "webscrape", "global_barcode", "30", "transient_scrape_failure"),
    ("SELLERHISTORYFAIL", "FAIL", "SELLERHISTORYFAIL", "webscrape", "global_barcode", "180", "seller_history_block"),
    ("BRANDFAIL", "FAIL", "BRANDFAIL", "webscrape", "global_barcode", "180", "brand_or_direct_seller_block"),
    ("MANUAL_REVIEW", "FAIL", "MANUAL_REVIEW", "manual_review", "supplier_offer", "90", "manual_review_required"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _processed_row_keys(results: pd.DataFrame) -> set[str]:
    if results.empty:
        return set()
    return {normalize_text(value) for value in results["row_key"].tolist() if normalize_text(value)}


def _select_scan_rows(
    batch_rows: pd.DataFrame,
    *,
    eligibility: pd.DataFrame,
    existing_results: pd.DataFrame,
    batch_id: str = "",
) -> pd.DataFrame:
    work = batch_rows.copy()
    if batch_id:
        work = work[work["batch_id"].map(normalize_text) == batch_id].copy()
    processed = _processed_row_keys(existing_results)
    if processed:
        work = work[~work["row_key"].map(normalize_text).isin(processed)].copy()
    if not eligibility.empty:
        eligible_keys = {
            normalize_text(row.get("row_key", ""))
            for _, row in eligibility.iterrows()
            if normalize_text(row.get("scan_decision", "")).lower() == "scan"
            and (not batch_id or normalize_text(row.get("batch_id", "")) == batch_id)
        }
        work = work[work["row_key"].map(normalize_text).isin(eligible_keys)].copy()
    else:
        work = work[work["scan_eligibility"].map(lambda value: normalize_text(value).lower()) == "scan_now"].copy()
    return work.sort_values(["supplier_id", "supplier_sku"], kind="stable").head(len(OUTCOME_SEQUENCE)).reset_index(drop=True)


def run_placeholder_scanner(
    root: Path | None = None,
    *,
    batch_id: str = "",
    scanned_at_utc: str | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    scanned_at = scanned_at_utc or _utc_now_iso()
    batch_rows = read_csv(paths.test_mode_dir / "batch_rows.csv", BATCH_ROW_COLUMNS)
    eligibility = read_csv(paths.test_mode_dir / "batch_scan_eligibility.csv", BATCH_SCAN_ELIGIBILITY_COLUMNS)
    existing_results = read_csv(paths.test_mode_dir / "placeholder_scanner_results.csv", PLACEHOLDER_SCANNER_RESULT_COLUMNS)
    scan_rows = _select_scan_rows(
        batch_rows,
        eligibility=eligibility,
        existing_results=existing_results,
        batch_id=batch_id,
    )
    if len(scan_rows.index) < len(OUTCOME_SEQUENCE):
        raise ValueError(f"placeholder scanner requires 10 scan_now rows, found {len(scan_rows.index)}")

    results: list[dict[str, str]] = []
    for index, (_, row) in enumerate(scan_rows.iterrows()):
        outcome, result_status, fail_code, last_stage, memory_scope, cooldown_days, notes = OUTCOME_SEQUENCE[index]
        row_batch_id = normalize_text(row.get("batch_id", ""))
        row_key = normalize_text(row.get("row_key", ""))
        result_stamp = scanned_at.replace("-", "").replace(":", "")
        results.append(
            {
                "result_id": f"{row_batch_id}_{result_stamp}_{index + 1:03d}",
                "batch_id": row_batch_id,
                "supplier_id": normalize_text(row.get("supplier_id", "")),
                "row_key": row_key,
                "supplier_sku": normalize_text(row.get("supplier_sku", "")),
                "barcode": normalize_text(row.get("barcode", "")),
                "placeholder_outcome": outcome,
                "result_status": result_status,
                "fail_code": fail_code,
                "last_stage": last_stage,
                "memory_scope": memory_scope,
                "cooldown_days": cooldown_days,
                "scanned_at_utc": scanned_at,
                "notes": notes,
            }
        )

    new_results_df = pd.DataFrame(results)
    results_df = write_csv(
        paths.test_mode_dir / "placeholder_scanner_results.csv",
        pd.concat([existing_results, new_results_df], ignore_index=True),
        PLACEHOLDER_SCANNER_RESULT_COLUMNS,
    )

    status_counts = new_results_df["result_status"].value_counts().to_dict()
    summary = {
        "status": "success",
        "result_rows": int(len(new_results_df)),
        "total_result_rows": int(len(results_df)),
        "pass_rows": int(status_counts.get("PASS", 0)),
        "fail_rows": int(status_counts.get("FAIL", 0)),
        "rescan_rows": int(status_counts.get("RESCAN", 0)),
        "results_path": str(paths.test_mode_dir / "placeholder_scanner_results.csv"),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the price-list manager placeholder scanner.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--scanned-at-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    run_placeholder_scanner(root=root, batch_id=args.batch_id, scanned_at_utc=args.scanned_at_utc)


if __name__ == "__main__":
    main()
