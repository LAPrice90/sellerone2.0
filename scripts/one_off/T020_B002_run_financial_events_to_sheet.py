"""
Fetch financial events (posted) and flatten shipment events into fee buckets per order.
Writes raw tab + per-order summary + CSV snapshot, updates Run_Status.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import gspread
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api.get_financial_events import (
    get_lwa_access_token,
    list_financial_events,
    load_dotenv_if_missing,
)

SHEET_ID = "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A"
RAW_TAB = "FinancialEvents_raw"
SUMMARY_TAB = "FinancialFees_summary"
RUN_STATUS_TAB = "Run_Status"
POSTED_AFTER = os.environ.get("FIN_POSTED_AFTER")  # ISO
POSTED_BEFORE = os.environ.get("FIN_POSTED_BEFORE")  # ISO
MARKER_PATH = Path("out/financial_events_last_posted.txt")
MAX_RETRIES = int(os.environ.get("FIN_MAX_RETRIES", "3"))
SLEEP_SEC = float(os.environ.get("FIN_SLEEP_SEC", "1.0"))

HEADERS_SUMMARY = [
    "order_id",
    "currency",
    "principal",
    "shipping",
    "giftwrap",
    "tax",
    "shipping_tax",
    "giftwrap_tax",
    "referral_fee",
    "referral_fee_tax",
    "fba_fee",
    "fba_fee_tax",
    "dsf_fee",
    "dsf_fee_tax",
    "fixed_fee",
    "other_fee",
    "posted_date",
    "settlement_id",
]

AMOUNT_MAP = {
    "Principal": ("principal", False),
    "Tax": ("tax", False),
    "Shipping": ("shipping", False),
    "ShippingTax": ("shipping_tax", False),
    "GiftWrap": ("giftwrap", False),
    "GiftWrapTax": ("giftwrap_tax", False),
    "Commission": ("referral_fee", False),
    "FBAPerOrderFulfillmentFee": ("fba_fee", False),
    "FBAPerUnitFulfillmentFee": ("fba_fee", False),
    "FBAWeightBasedFee": ("fba_fee", False),
    "FBAPromotionAmount": ("other_fee", False),
    "DirectPaymentAdjustment": ("other_fee", False),
    "DirectPaymentAdvance": ("other_fee", False),
    "DirectPaymentAdvanceRecovery": ("other_fee", False),
    "CollectableSalesTax": ("tax", False),
    "Goodwill": ("other_fee", False),
    "GiftwrapChargeback": ("other_fee", False),
    "Handling": ("other_fee", False),
    "LightningDealFee": ("other_fee", False),
    "FixedClosingFee": ("fixed_fee", False),
    "PointsFee": ("other_fee", False),
    "Points": ("other_fee", False),
    "Retrocharge": ("other_fee", False),
    "RetrochargeTax": ("other_fee", False),
    "SAFE-TReimbursement": ("other_fee", False),
    "ServiceFee": ("other_fee", False),
    "ShippingChargeback": ("other_fee", False),
    "ShippingHB": ("shipping", False),
    "ShippingHBAdjustment": ("other_fee", False),
    "StorageFee": ("other_fee", False),
    "WarehouseDamage": ("other_fee", False),
    "RestockingFee": ("other_fee", False),
    "ReturnShipping": ("other_fee", False),
    "ReturnShippingAdjustment": ("other_fee", False),
    "LowValueGoods": ("tax", False),
    "CouponMoney": ("promotion_component", False),
    "CouponRedemptionFee": ("other_fee", False),
    "CouponRedemptionTax": ("other_fee", False),
    "HighlandFee": ("other_fee", False),
    "NSK": ("other_fee", False),
    "Other": ("other_fee", False),
    "DirectSellingFee": ("dsf_fee", False),
}


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def write_tab(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)


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


def load_marker() -> Optional[str]:
    if POSTED_AFTER:
        return POSTED_AFTER
    if MARKER_PATH.exists():
        txt = MARKER_PATH.read_text().strip()
        if txt:
            return txt
    return None


def save_marker(latest_iso: str) -> None:
    try:
        dt = datetime.fromisoformat(latest_iso.replace("Z", "+00:00"))
        latest_iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKER_PATH.write_text(latest_iso)


def flatten_events(events: Dict[str, object]) -> pd.DataFrame:
    rows = []
    shipments = events.get("ShipmentEventList") or []
    for ev in shipments:
        order_id = ev.get("AmazonOrderId", "")
        posted_date = ev.get("PostedDate", "")
        settlement_id = ev.get("SellerOrderId", "")
        charges = ev.get("ShipmentItemList") or []
        for item in charges:
            for charge in item.get("ItemChargeList") or []:
                rows.append(
                    {
                        "order_id": order_id,
                        "posted_date": posted_date,
                        "settlement_id": settlement_id,
                        "amount_type": charge.get("ChargeType", ""),
                        "amount": (charge.get("ChargeAmount") or {}).get("Amount", ""),
                        "currency": (charge.get("ChargeAmount") or {}).get("CurrencyCode", ""),
                    }
                )
            for fee in item.get("ItemFeeList") or []:
                rows.append(
                    {
                        "order_id": order_id,
                        "posted_date": posted_date,
                        "settlement_id": settlement_id,
                        "amount_type": fee.get("FeeType", ""),
                        "amount": (fee.get("FeeAmount") or {}).get("Amount", ""),
                        "currency": (fee.get("FeeAmount") or {}).get("CurrencyCode", ""),
                    }
                )
            for adj in item.get("ItemFeeAdjustmentList") or []:
                rows.append(
                    {
                        "order_id": order_id,
                        "posted_date": posted_date,
                        "settlement_id": settlement_id,
                        "amount_type": adj.get("FeeType", ""),
                        "amount": (adj.get("FeeAmount") or {}).get("Amount", ""),
                        "currency": (adj.get("FeeAmount") or {}).get("CurrencyCode", ""),
                    }
                )
    return pd.DataFrame(rows)


def aggregate_fees(df: pd.DataFrame) -> pd.DataFrame:
    agg_rows = []
    if df.empty:
        return pd.DataFrame(columns=HEADERS_SUMMARY)
    grouped = df.groupby(["order_id", "currency"])
    for (order_id, currency), grp in grouped:
        totals = {k: 0.0 for k in HEADERS_SUMMARY}
        totals["order_id"] = order_id
        totals["currency"] = currency
        for _, row in grp.iterrows():
            amt_type = row.get("amount_type", "")
            amt = float(row.get("amount") or 0)
            mapped = AMOUNT_MAP.get(amt_type)
            if mapped:
                bucket, has_tax = mapped
                if bucket == "dsf_fee" and amt > 0:
                    totals["other_fee"] += amt
                    continue
                totals[bucket] += amt
            else:
                totals["other_fee"] += amt
        posted_dates = grp["posted_date"].tolist()
        settlements = grp["settlement_id"].tolist()
        totals["posted_date"] = max([d for d in posted_dates if d] + [""])
        totals["settlement_id"] = ";".join(sorted(set([s for s in settlements if s])))
        agg_rows.append(totals)
    return pd.DataFrame(agg_rows, columns=HEADERS_SUMMARY)


def main() -> None:
    load_dotenv_if_missing()
    token = get_lwa_access_token()

    started_at = datetime.now(timezone.utc)
    script_name = "B002_run_financial_events_to_sheet.py"
    mode = "default"
    status = "success"
    alert = ""
    last_error = ""
    env_name = os.environ.get("ENV", "prod")
    git_version = os.environ.get("GIT_COMMIT", "")
    sheet_tabs_written: List[str] = []
    snapshot_path = ""
    attempts_used = 0
    row_count = 0
    col_count = 0

    client = get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)

    try:
        effective_after = load_marker()
        events_rows: List[Dict[str, object]] = []
        next_token = None
        page = 0
        latest_posted = effective_after
        while True:
            page += 1
            attempts_used = page
            retries = 0
            while True:
                try:
                    ev_batch, next_token = list_financial_events(
                        access_token=token,
                        posted_after=effective_after,
                        posted_before=POSTED_BEFORE,
                        next_token=next_token,
                    )
                    break
                except Exception as exc:
                    retries += 1
                    if retries < MAX_RETRIES:
                        time.sleep(SLEEP_SEC * retries)
                        continue
                    raise

            df_flat = flatten_events(ev_batch)
            events_rows.extend(df_flat.to_dict(orient="records"))
            if not df_flat.empty:
                latest_vals = [d for d in df_flat["posted_date"].tolist() if d]
                if latest_vals:
                    latest_posted = max(latest_vals)
            if next_token:
                continue
            break

        df_events = pd.DataFrame(events_rows)
        df_summary = aggregate_fees(df_events)
        row_count = len(df_events) + len(df_summary)
        col_count = max(len(df_events.columns), len(df_summary.columns))

        out_events = Path("out/financial_events_raw.csv")
        out_summary = Path("out/financial_fees_summary.csv")
        out_events.parent.mkdir(parents=True, exist_ok=True)
        df_events.to_csv(out_events, index=False)
        df_summary.to_csv(out_summary, index=False)
        snapshot_path = f"{out_events};{out_summary}"

        write_tab(sheet, RAW_TAB, df_events)
        write_tab(sheet, SUMMARY_TAB, df_summary)
        sheet_tabs_written = [RAW_TAB, SUMMARY_TAB]

        if latest_posted:
            save_marker(latest_posted)
    except Exception as exc:
        status = "error"
        alert = "error"
        last_error = str(exc)
        df_events = pd.DataFrame()
        df_summary = pd.DataFrame()

    ended_at = datetime.now(timezone.utc)
    duration_seconds = str(int((ended_at - started_at).total_seconds()))

    consecutive_failures = 0
    consecutive_successes = 0
    try:
        ws_status = sheet.worksheet(RUN_STATUS_TAB)
        existing = ws_status.get_all_values()
    except gspread.WorksheetNotFound:
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
        key = (script_name, mode, "n/a")
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

    run_id = f"{script_name}-{started_at.isoformat()}"
    status_row = [
        script_name,
        mode,
        "n/a",
        status,
        alert,
        run_id,
        started_at.isoformat(),
        ended_at.isoformat(),
        duration_seconds,
        str(attempts_used),
        str(row_count),
        str(col_count),
        snapshot_path,
        ";".join(sheet_tabs_written),
        "",
        "",
        str(consecutive_failures),
        str(consecutive_successes),
        env_name,
        git_version,
        last_error,
    ]
    append_run_status(sheet, status_row)

    print(
        {
            "timestamp": ended_at.isoformat(),
            "status": status,
            "row_count": row_count,
            "columns": col_count,
            "snapshot": snapshot_path,
            "sheet_tabs": sheet_tabs_written,
            "alert": alert,
            "error": last_error,
        }
    )


if __name__ == "__main__":
    main()

