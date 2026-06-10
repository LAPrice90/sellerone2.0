"""
One-click runner with mode toggle:
- MODE="sheet": fetch listings report and save local CSV snapshots. Legacy Sheet writing is opt-in.
- MODE="sku": fetch listings report, save snapshot, and print the target SKU rows.
- A001_WRITE_LEGACY_SHEETS=1: opt in to the old Google Sheets update path.

Focus columns for summary:
item-name, listing-id, seller-sku, price, open-date, item-condition, product-id, fulfillment-channel
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import gspread
import pandas as pd

# Ensure project root is on path for package imports when run directly
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_merchant_listings_report import run_live, load_dotenv_if_missing
from scripts.api.get_marketplace_participations import list_marketplace_participations
from scripts.core.storage import coalesce_duplicate_header_rows, dataframe_from_product_db_sheet_rows, write_dataframe_with_sql_compat
 
MODE = os.environ.get("RUN_MODE", "sheet").lower()
TARGET_SKU = os.environ.get("TARGET_SKU", "0G-JB6S-PN34")

SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
RAW_TAB = "MerchantListings_raw"
SUMMARY_TAB = "Listings_focus_summary"
RUN_STATUS_TAB = "Run_Status"
MARKETPLACE_ID = os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")
POLL_INTERVAL = int(os.environ.get("A001_POLL_INTERVAL", os.environ.get("POLL_INTERVAL", "20")))
MAX_ATTEMPTS = int(os.environ.get("A001_MAX_ATTEMPTS", os.environ.get("MAX_ATTEMPTS", "40")))
PRODUCT_DB_PREVIEW = Path("out/product_db_preview.csv")
SQL_TABLE_PRODUCT_DB_PREVIEW = "sys_product_db_preview"

FOCUS_COLUMNS: List[str] = [
    "item-name",
    "listing-id",
    "seller-sku",
    "price",
    "open-date",
    "item-condition",
    "product-id",
    "fulfillment-channel",
]


def env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def write_legacy_sheets_enabled() -> bool:
    return env_flag("A001_WRITE_LEGACY_SHEETS", "0")


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def export_product_db(sheet: gspread.Spreadsheet) -> None:
    """Dump the Product_DB sheet to out/product_db_preview.csv for downstream use."""
    try:
        ws = sheet.worksheet("Product_DB")
    except gspread.WorksheetNotFound:
        return
    rows = ws.get_all_values()
    if not rows:
        return
    df, repaired_headers = dataframe_from_product_db_sheet_rows(rows)
    Path("out").mkdir(parents=True, exist_ok=True)
    write_dataframe_with_sql_compat(
        df,
        PRODUCT_DB_PREVIEW,
        SQL_TABLE_PRODUCT_DB_PREVIEW,
    )
    if repaired_headers:
        print("Repaired duplicate Product_DB headers for export: " + ",".join(repaired_headers))
    print("Saved Product_DB preview to out/product_db_preview.csv")


def update_product_db_listings(sheet: gspread.Spreadsheet, df: pd.DataFrame, run_ts: str) -> None:
    """Mark rows in Product_DB with last_updated_A001 for matched SKUs/ASINs."""
    try:
        ws = sheet.worksheet("Product_DB")
    except gspread.WorksheetNotFound:
        return
    prod_rows = ws.get_all_values()
    if not prod_rows:
        return
    prod_rows, repaired_headers = coalesce_duplicate_header_rows(prod_rows)
    if repaired_headers:
        print("Repaired duplicate Product_DB headers before A001 update: " + ",".join(repaired_headers))
    headers = prod_rows[0]
    idx_map = {h: i for i, h in enumerate(headers)}
    # Ensure required columns exist
    required_cols = [
        "last_updated_A001",
        "live_listing_price",
        "live_listing_price_currency",
        "live_price_last_updated",
        "last_sold_price",
        "last_sold_price_currency",
        "last_sold_price_updated",
    ]
    for col in required_cols:
        if col not in idx_map:
            idx_map[col] = len(headers)
            headers.append(col)
            for row in prod_rows[1:]:
                while len(row) < len(headers):
                    row.append("")

    sku_idx = idx_map.get("seller_sku", -1)
    asin_idx = idx_map.get("asin", -1)
    sku_lookup = {}
    asin_lookup = {}
    for i, row in enumerate(prod_rows[1:], start=1):
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        sku_val = row[sku_idx] if sku_idx >= 0 else ""
        asin_val = row[asin_idx] if asin_idx >= 0 else ""
        if sku_val:
            sku_lookup[sku_val] = i
        if asin_val:
            asin_lookup.setdefault(asin_val, []).append(i)

    def set_live_fields(row, price_val: str, price_currency: str, updated_ts: str) -> None:
        row[idx_map["last_updated_A001"]] = run_ts
        row[idx_map["live_listing_price"]] = price_val
        row[idx_map["live_listing_price_currency"]] = price_currency
        row[idx_map["live_price_last_updated"]] = updated_ts

    def set_if_present(row, field: str, value: str) -> None:
        if field not in idx_map:
            return
        col = idx_map[field]
        while len(row) <= col:
            row.append("")
        row[col] = value

    for _, r in df.iterrows():
        sku = str(r.get("seller-sku", "") or r.get("seller_sku", ""))
        asin = ""
        pid_type = str(r.get("product-id-type", ""))
        if pid_type == "1":
            asin = str(r.get("product-id", ""))
        if not asin and "asin1" in df.columns:
            asin = str(r.get("asin1", ""))
        target_rows = []
        if sku and sku in sku_lookup:
            target_rows.append(sku_lookup[sku])
        if not target_rows and asin and asin in asin_lookup:
            target_rows.extend(asin_lookup[asin])
        if not target_rows and (sku or asin):
            new_row = [""] * len(headers)
            set_if_present(new_row, "seller_sku", sku)
            set_if_present(new_row, "asin", asin)
            set_if_present(new_row, "title", str(r.get("item-name", "")))
            prod_rows.append(new_row)
            new_idx = len(prod_rows) - 1
            if sku:
                sku_lookup[sku] = new_idx
            if asin:
                asin_lookup.setdefault(asin, []).append(new_idx)
            target_rows.append(new_idx)
        for idx in target_rows:
            row = prod_rows[idx]
            price_val = str(r.get("price", ""))
            # Merchant Listings report lacks currency; derive deterministically from marketplace.
            price_currency = "GBP" if MARKETPLACE_ID == "A1F83G8C2ARO7P" else ""
            set_if_present(row, "seller_sku", sku)
            set_if_present(row, "asin", asin)
            if str(row[idx_map.get("title", -1)]).strip() == "" if "title" in idx_map else False:
                set_if_present(row, "title", str(r.get("item-name", "")))
            set_live_fields(row, price_val, price_currency, run_ts)

    ws.clear()
    ws.update(range_name="A1", values=[headers] + prod_rows[1:])


def load_prev_focus_counts(sheet: gspread.Spreadsheet) -> dict:
    try:
        ws = sheet.worksheet(SUMMARY_TAB)
    except gspread.WorksheetNotFound:
        return {}
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return {}
    prev = {}
    for row in values[1:]:
        if len(row) < 3 or row[0] != "A001":
            continue
        col = row[1]
        try:
            prev_count = int(row[2])
        except Exception:
            prev_count = 0
        prev[col] = prev_count
    return prev


def summarize_focus(df: pd.DataFrame, prev_counts: dict) -> list[list[str]]:
    rows: list[list[str]] = [["script", "column", "prev_non_empty", "curr_non_empty", "delta", "percent_change", "flag"]]
    script_name = "A001"
    for col in FOCUS_COLUMNS:
        curr = int((df[col].astype(str).str.len() > 0).sum()) if col in df.columns else 0
        prev = prev_counts.get(col, 0)
        delta = curr - prev
        pct = ""
        if prev > 0:
            pct = f"{(delta / prev) * 100:.1f}%"
        if prev > 0 and curr == 0:
            flag = "drop_to_zero"
        elif prev > 0 and curr < prev * 0.8:
            flag = "drop_over_20pct"
        else:
            flag = "ok"
        rows.append([script_name, col, str(prev), str(curr), str(delta), pct, flag])
    return rows


def write_raw_and_focus_summary(df: pd.DataFrame) -> None:
    client = get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)
    run_ts = datetime.now(timezone.utc).isoformat()

    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws_raw = sheet.worksheet(RAW_TAB)
    except gspread.WorksheetNotFound:
        ws_raw = sheet.add_worksheet(title=RAW_TAB, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    else:
        ws_raw.clear()
    ws_raw.update(range_name="A1", values=payload)

    prev_counts = load_prev_focus_counts(sheet)
    summary_rows = summarize_focus(df, prev_counts)
    summary_rows = [row + [""] * (7 - len(row)) if len(row) < 7 else row for row in summary_rows]
    try:
        ws_summary = sheet.worksheet(SUMMARY_TAB)
        existing = ws_summary.get_all_values()
    except gspread.WorksheetNotFound:
        ws_summary = sheet.add_worksheet(title=SUMMARY_TAB, rows=max(len(summary_rows) + 5, 50), cols=7)
        existing = []
    # Preserve other scripts' rows, replace A001 rows
    header = summary_rows[0]
    other_rows = [r for r in (existing[1:] if existing else []) if r and r[0] != "A001"]
    merged = [header] + other_rows + summary_rows[1:]
    ws_summary.clear()
    ws_summary.update(range_name="A1", values=merged)
    update_product_db_listings(sheet, df, run_ts)
    export_product_db(sheet)


def save_snapshot(df: pd.DataFrame) -> str:
    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)
    primary_path = out_dir / "merchant_listings_latest.csv"
    legacy_path = out_dir / "listings_data_latest.csv"
    df.to_csv(primary_path, index=False)
    # Keep legacy snapshot path for A-cycle compatibility checks.
    df.to_csv(legacy_path, index=False)
    return str(primary_path)


def append_run_status(sheet: gspread.Spreadsheet, row: list[str]) -> None:
    headers = [
        "script",
        "mode",
        "marketplace_id",
        "status",
        "alert",
        "run_id",
        "started_at",
        "ended_at",
        "duration_seconds",
        "attempts",
        "records_count",
        "col_count",
        "snapshot_path",
        "sheet_tabs",
        "poll_interval",
        "max_attempts",
        "consecutive_failures",
        "consecutive_successes",
        "env",
        "version",
        "last_error",
    ]
    try:
        ws = sheet.worksheet(RUN_STATUS_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=RUN_STATUS_TAB, rows=100, cols=len(headers))
        ws.update(range_name="A1", values=[headers])
    else:
        if ws.row_values(1) != headers:
            ws.clear()
            ws.update(range_name="A1", values=[headers])

    existing = ws.get_all_values()
    index = {}
    for idx, r in enumerate(existing[1:], start=2):
        if len(r) < 3:
            continue
        index[(r[0], r[1], r[2])] = idx

    key = (row[0], row[1], row[2])
    if key in index:
        ws.update(range_name=f"A{index[key]}:U{index[key]}", values=[row])
    else:
        ws.append_row(row, value_input_option="RAW")


def main() -> None:
    load_dotenv_if_missing()
    try:
        participations = list_marketplace_participations()
        rows = []
        for entry in participations:
            marketplace = entry.get("marketplace") or {}
            participation = entry.get("participation") or {}
            rows.append(
                {
                    "marketplace_id": marketplace.get("id"),
                    "name": marketplace.get("name"),
                    "country_code": marketplace.get("countryCode"),
                    "domain_name": marketplace.get("domainName"),
                    "default_currency": marketplace.get("defaultCurrencyCode"),
                    "default_language": marketplace.get("defaultLanguageCode"),
                    "is_participating": participation.get("isParticipating"),
                    "has_suspended_listings": participation.get("hasSuspendedListings"),
                }
            )
        if rows:
            out_path = Path("out/marketplace_participations.csv")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_csv(out_path, index=False)
    except Exception as exc:
        print({"status": "warning", "alert": "marketplace_participations_error", "error": str(exc)})
    started_at = datetime.now(timezone.utc)
    ts = started_at.isoformat()
    script_name = "A001_run_listings_to_sheet.py"
    mode = MODE
    sheet_tabs_written: list[str] = []
    snapshot_path = ""
    status = "success"
    last_error = ""
    row_count = 0
    col_count = 0
    attempts_used = 0
    consecutive_failures = 0
    consecutive_successes = 0
    alert = ""
    run_id = f"{script_name}-{ts}"
    env_name = os.environ.get("ENV", "prod")
    git_version = os.environ.get("GIT_COMMIT", "")

    write_legacy_sheets = write_legacy_sheets_enabled()
    sheet = None
    if write_legacy_sheets:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)

    try:
        result = run_live(
            marketplace_id=MARKETPLACE_ID,
            poll_interval=POLL_INTERVAL,
            max_attempts=MAX_ATTEMPTS,
        )
        df = result["data"]
        row_count = result["row_count"]
        col_count = len(result["columns"])
        attempts_used = result.get("attempts_used", 0)
    except Exception as exc:
        status = "error"
        last_error = str(exc)
        alert = "error"
        df = pd.DataFrame()
    else:
        snapshot_path = save_snapshot(df)

        if mode == "sheet":
            if write_legacy_sheets:
                write_raw_and_focus_summary(df)
                sheet_tabs_written = [RAW_TAB, SUMMARY_TAB]
                if sheet is not None:
                    export_product_db(sheet)
            else:
                sheet_tabs_written = []
        elif mode == "sku":
            matches = df[df["seller-sku"] == TARGET_SKU].fillna("")
            if matches.empty:
                print({"sku": TARGET_SKU, "message": "No rows found"})
            else:
                print(matches.to_json(orient="records", indent=2))
            sheet_tabs_written = []

    if status == "success" and row_count == 0:
        alert = "drop_to_zero"

    # Load existing consecutive counters
    if write_legacy_sheets and sheet is not None:
        try:
            ws_status = sheet.worksheet(RUN_STATUS_TAB)
            existing = ws_status.get_all_values()
        except gspread.WorksheetNotFound:
            existing = []
            ws_status = None
    else:
        existing = []
        ws_status = None
    headers = [
        "script",
        "mode",
        "marketplace_id",
        "status",
        "alert",
        "run_id",
        "started_at",
        "ended_at",
        "duration_seconds",
        "attempts",
        "records_count",
        "col_count",
        "snapshot_path",
        "sheet_tabs",
        "poll_interval",
        "max_attempts",
        "consecutive_failures",
        "consecutive_successes",
        "env",
        "version",
        "last_error",
    ]
    if existing and existing[0] == headers:
        index = {(r[0], r[1], r[2]): r for r in existing[1:] if len(r) >= 3}
        key = (script_name, mode, MARKETPLACE_ID)
        prev = index.get(key, [])
        try:
            consecutive_failures = int(prev[16]) if len(prev) > 16 else 0
        except Exception:
            consecutive_failures = 0
        try:
            consecutive_successes = int(prev[17]) if len(prev) > 17 else 0
        except Exception:
            consecutive_successes = 0
    if status == "success":
        consecutive_successes += 1
        consecutive_failures = 0
    else:
        consecutive_failures += 1
        consecutive_successes = 0

    ended_at = datetime.now(timezone.utc)
    duration_seconds = str(int((ended_at - started_at).total_seconds()))

    status_row = [
        script_name,
        mode,
        MARKETPLACE_ID,
        status,
        alert,
        run_id,
        ts,
        ended_at.isoformat(),
        duration_seconds,
        str(attempts_used),
        str(row_count),
        str(col_count),
        snapshot_path,
        ";".join(sheet_tabs_written),
        str(POLL_INTERVAL),
        str(MAX_ATTEMPTS),
        str(consecutive_failures),
        str(consecutive_successes),
        env_name,
        git_version,
        last_error,
    ]
    if write_legacy_sheets and sheet is not None:
        append_run_status(sheet, status_row)

    print(
        {
            "timestamp": ts,
            "status": status,
            "row_count": row_count,
            "columns": col_count,
            "snapshot": snapshot_path,
            "sheet_tabs": sheet_tabs_written,
            "mode": mode,
            "legacy_sheet_writes": write_legacy_sheets,
            "alert": alert,
            "error": last_error,
        }
    )
    if status != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()


