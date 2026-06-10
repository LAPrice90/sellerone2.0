"""
Build a daily P&L (v2) starting from a fixed date using Order FX ledger.

Rows included (initial set):
- Quantity Ordered
- Price_Total
- Price_VAT
- Price_ExVAT
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
from scripts.core.safe_file_writes import safe_to_csv
try:
    import gspread
    from gspread.exceptions import APIError
except Exception:
    gspread = None
    APIError = Exception


ORDER_LEDGER_FX = Path("out/order_ledger_fx.csv")
ORDER_COGS = Path("out/order_cogs_from_tokens.csv")
PRODUCT_DB = Path("out/product_db_preview.csv")
OUT_PNL = Path("out/pnl_daily.csv")
TXN_BREAKDOWNS = Path("out/financial_transactions_v2024_breakdowns.csv")
TXN_CATEGORY_LEDGER = Path("out/transaction_category_ledger.csv")
REFUNDS_OFFICIAL = Path("out/financial_events_refunds_official.csv")
FEE_VAT_LEDGER = Path("out/fee_vat_ledger.csv")
RETURN_COGS = Path("out/token_return_ledger.csv")

PNL_SHEET_ID = os.environ.get("PNL_SHEET_ID", "1aT26UYnTBP6-oNz0RIWVCRbuuN1RmP4_VwHEeiNzxKc")
PNL_TAB = os.environ.get("PNL_TAB", "ProfitAndLoss_daily")
PNL_START_DATE = os.environ.get("PNL_START_DATE", "2025-11-01")
PNL_MONTHLY_TABS = os.environ.get("PNL_MONTHLY_TABS", "1").strip() == "1"
PNL_MONTHLY_PREFIX = os.environ.get("PNL_MONTHLY_PREFIX", "ProfitAndLoss_")
PNL_WRITE_DAILY = os.environ.get("PNL_WRITE_DAILY", "0").strip() == "1"
PNL_SUMMARY_TAB = os.environ.get("PNL_SUMMARY_TAB", "P&L_Summary")
PNL_FORMAT_SHEETS = os.environ.get("PNL_FORMAT_SHEETS", "1").strip() == "1"
PNL_SUMMARY_ONLY = os.environ.get("PNL_SUMMARY_ONLY", "0").strip() == "1"
PNL_PUBLISH = os.environ.get("PNL_PUBLISH", "0").strip() == "1"
PNL_WRITE_SHEETS = os.environ.get("PNL_WRITE_SHEETS", "1").strip() == "1"
if os.environ.get("B_CYCLE_QUIET", "0").strip() == "1" and not PNL_PUBLISH:
    PNL_WRITE_DAILY = False
    PNL_MONTHLY_TABS = False
    PNL_WRITE_SHEETS = False

SHEETS_MAX_RETRIES = int(os.environ.get("PNL_SHEETS_MAX_RETRIES", "8"))
SHEETS_BACKOFF = float(os.environ.get("PNL_SHEETS_BACKOFF", "5.0"))

ROWS = [
    "Quantity Ordered",
    "Cancelled_Orders_Seen",
    "Gross_Units_Sold",
    "Refund_Units",
    "Net_Units_Sold",
    "Refund_Unit_Rate",
    "Refunded_Order_Count",
    "Price_Total",
    "Price_VAT",
    "Price_ExVAT",
    "Shipping_Total",
    "Shipping_VAT",
    "Shipping_ExVAT",
    "Gift_Total",
    "Gift_VAT",
    "Gift_ExVAT",
    "Promotion_Total",
    "Promotion_VAT",
    "Promotion_ExVAT",
    "COGS_Total",
    "COGS_VAT",
    "COGS_ExVAT",
    "FBA_Fee_Total",
    "FBA_Fee_VAT",
    "FBA_Fee_ExVAT",
    "Commission_Total",
    "Commission_VAT",
    "Commission_ExVAT",
    "Digital_Fee_Total",
    "Digital_Fee_VAT",
    "Digital_Fee_ExVAT",
    "Gross_Profit_ExVAT",
    "Contribution_Profit_ExVAT",
    "Refund_Sales_Total",
    "Refund_Expenses_Total",
    "Inbound_Transportation_Fee",
    "Removal_Fee",
    "Disposal_Fee",
    "Customer_Returns_Fee",
    "Warehouse_Lost_Reimbursement",
    "Reversal_Reimbursement",
    "Retrocharge_Total",
    "Inventory_Reimbursement",
    "Compensated_Clawback",
    "Refund_Commission",
    "Shipping_Chargeback",
    "Storage_Charges",
    "Subscription_Fee_Total",
    "Subscription_Fee_VAT",
    "Subscription_Fee_ExVAT",
    "Service_Fee_VAT",
]


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def write_tab_with_retry(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.where(pd.notnull(df), "").values.tolist()
    for attempt in range(1, SHEETS_MAX_RETRIES + 1):
        try:
            try:
                ws = sheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
            else:
                ws.clear()
            ws.update(range_name="A1", values=payload, value_input_option="USER_ENTERED")
            return
        except APIError as exc:
            if attempt == SHEETS_MAX_RETRIES:
                raise
            msg = str(exc)
            delay = SHEETS_BACKOFF * attempt
            if "429" in msg or "Quota" in msg or "RESOURCE_EXHAUSTED" in msg:
                delay = max(delay, 15.0 * attempt)
            print({"status": "warn", "stage": "sheets_retry", "tab": tab_name, "attempt": attempt, "delay_s": delay, "error": msg})
            time.sleep(delay)


def _date_key(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.strftime("%Y-%m-%d")


def _build_monthly_tabs(df_out: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if df_out.empty or "Parameter/Date" not in df_out.columns:
        return {}
    date_cols = [c for c in df_out.columns if c not in ("Parameter/Date", "Total")]
    if not date_cols:
        return {}
    months = sorted({c[:7] for c in date_cols if len(c) >= 7})
    tabs: dict[str, pd.DataFrame] = {}
    for month in months:
        cols = ["Parameter/Date"] + [c for c in date_cols if c.startswith(month)] + ["Total"]
        sub = df_out[cols].copy()
        # Recompute Total for the month view only.
        totals = []
        for _, row in sub.iterrows():
            total = 0.0
            for c in cols:
                if c in ("Parameter/Date", "Total"):
                    continue
                total += float(pd.to_numeric(row.get(c, 0.0), errors="coerce") or 0.0)
            totals.append(round(total, 2))
        sub["Total"] = totals
        tabs[f"{PNL_MONTHLY_PREFIX}{month.replace('-', '_')}"] = sub
    return tabs


def _build_summary_tab(df_out: pd.DataFrame) -> pd.DataFrame:
    if df_out.empty or "Parameter/Date" not in df_out.columns:
        return pd.DataFrame()
    date_cols = [c for c in df_out.columns if c not in ("Parameter/Date", "Total")]
    if not date_cols:
        return pd.DataFrame()
    months = sorted({c[:7] for c in date_cols if len(c) >= 7})
    rows: list[dict[str, object]] = []
    for _, row in df_out.iterrows():
        out_row: dict[str, object] = {"Line Item": row.get("Parameter/Date", "")}
        total = 0.0
        for month in months:
            val = 0.0
            for c in date_cols:
                if c.startswith(month):
                    val += float(pd.to_numeric(row.get(c, 0.0), errors="coerce") or 0.0)
            out_row[month] = round(val, 2)
            total += val
        out_row["Total"] = round(total, 2)
        rows.append(out_row)
    cols = ["Line Item"] + months + ["Total"]
    return pd.DataFrame(rows, columns=cols)


def _apply_sheet_formatting(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    ws = sheet.worksheet(tab_name)
    sheet_id = ws.id
    rows_count = len(df) + 1
    cols_count = len(df.columns)
    first_col = df.columns[0] if df.columns.size else "Parameter/Date"

    def color(r: int, g: int, b: int) -> dict:
        return {"red": r / 255.0, "green": g / 255.0, "blue": b / 255.0}

    # Row style groups
    income_rows = {
        "Price_Total",
        "Price_VAT",
        "Price_ExVAT",
        "Shipping_Total",
        "Shipping_VAT",
        "Shipping_ExVAT",
        "Gift_Total",
        "Gift_VAT",
        "Gift_ExVAT",
    }
    expense_rows = {
        "Promotion_Total",
        "Promotion_VAT",
        "Promotion_ExVAT",
        "COGS_Total",
        "COGS_VAT",
        "COGS_ExVAT",
        "FBA_Fee_Total",
        "FBA_Fee_VAT",
        "FBA_Fee_ExVAT",
        "Commission_Total",
        "Commission_VAT",
        "Commission_ExVAT",
        "Digital_Fee_Total",
        "Digital_Fee_VAT",
        "Digital_Fee_ExVAT",
        "Refund_Sales_Total",
        "Refund_Expenses_Total",
        "Inbound_Transportation_Fee",
        "Removal_Fee",
        "Disposal_Fee",
        "Customer_Returns_Fee",
        "Warehouse_Lost_Reimbursement",
        "Reversal_Reimbursement",
        "Retrocharge_Total",
        "Inventory_Reimbursement",
        "Compensated_Clawback",
        "Refund_Commission",
        "Shipping_Chargeback",
        "Storage_Charges",
        "Subscription_Fee_Total",
        "Subscription_Fee_VAT",
        "Subscription_Fee_ExVAT",
        "Service_Fee_VAT",
    }
    sum_rows = {
        "Gross_Profit_ExVAT",
        "Contribution_Profit_ExVAT",
        "Net_Profit_ExVAT",
        "Payout_Estimate",
        "VAT_Difference",
        "Total",
    }
    group_rows = [
        ("Price_Total", "Price_ExVAT"),
        ("Shipping_Total", "Shipping_ExVAT"),
        ("Gift_Total", "Gift_ExVAT"),
        ("Promotion_Total", "Promotion_ExVAT"),
        ("COGS_Total", "COGS_ExVAT"),
        ("FBA_Fee_Total", "FBA_Fee_ExVAT"),
        ("Commission_Total", "Commission_ExVAT"),
        ("Digital_Fee_Total", "Digital_Fee_ExVAT"),
        ("Refund_Sales_Total", "Refund_Expenses_Total"),
        ("Inbound_Transportation_Fee", "Removal_Fee"),
        ("Disposal_Fee", "Customer_Returns_Fee"),
        ("Warehouse_Lost_Reimbursement", "Reversal_Reimbursement"),
        ("Retrocharge_Total", "Inventory_Reimbursement"),
        ("Compensated_Clawback", "Shipping_Chargeback"),
        ("Storage_Charges", "Storage_Charges"),
        ("Subscription_Fee_Total", "Subscription_Fee_ExVAT"),
        ("Service_Fee_VAT", "Service_Fee_VAT"),
        ("Gross_Units_Sold", "Refunded_Order_Count"),
        ("Gross_Profit_ExVAT", "Contribution_Profit_ExVAT"),
        ("Payout_Estimate", "VAT_Difference"),
    ]

    requests = []

    # Freeze header row and first column
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}},
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        }
    )

    # Header format
    requests.append(
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": cols_count},
                "cell": {"userEnteredFormat": {"backgroundColor": color(210, 230, 255), "textFormat": {"bold": True}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        }
    )

    # Alternating row colors for body (light)
    try:
        meta = sheet.fetch_sheet_metadata()
        banded = meta.get("sheets", [])
        for s in banded:
            props = s.get("properties", {})
            if props.get("sheetId") != sheet_id:
                continue
            for band in s.get("bandedRanges", []):
                band_id = band.get("bandedRangeId")
                if band_id:
                    requests.append({"deleteBanding": {"bandedRangeId": band_id}})
    except Exception:
        pass

    requests.append(
        {
            "addBanding": {
                "bandedRange": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": rows_count, "startColumnIndex": 0, "endColumnIndex": cols_count},
                    "rowProperties": {
                        "firstBandColor": color(245, 250, 255),
                        "secondBandColor": color(255, 255, 255),
                    },
                }
            }
        }
    )

    # Row-specific colors
    if first_col in df.columns and first_col == "Parameter/Date":
        row_names = df[first_col].tolist()
    else:
        row_names = []

    for i, row_name in enumerate(row_names, start=2):  # sheet rows are 1-based
        bg = None
        if row_name in income_rows:
            bg = color(210, 230, 255)  # light blue
        elif row_name in expense_rows:
            bg = color(255, 230, 230)  # light red
        elif row_name in sum_rows:
            bg = color(220, 245, 220)  # light green
        if bg:
            requests.append(
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": i - 1, "endRowIndex": i, "startColumnIndex": 0, "endColumnIndex": cols_count},
                        "cell": {"userEnteredFormat": {"backgroundColor": bg}},
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            )

    # Borders for full range
    requests.append(
        {
            "updateBorders": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": rows_count, "startColumnIndex": 0, "endColumnIndex": cols_count},
                "top": {"style": "SOLID", "width": 1, "color": color(200, 200, 200)},
                "bottom": {"style": "SOLID", "width": 1, "color": color(200, 200, 200)},
                "left": {"style": "SOLID", "width": 1, "color": color(200, 200, 200)},
                "right": {"style": "SOLID", "width": 1, "color": color(200, 200, 200)},
            }
        }
    )

    # Group separators: draw top/bottom borders around row groups
    row_index = {name: i for i, name in enumerate(row_names, start=2)}
    for start_name, end_name in group_rows:
        start_row = row_index.get(start_name)
        end_row = row_index.get(end_name)
        if not start_row or not end_row:
            continue
        top_idx = min(start_row, end_row) - 1
        bottom_idx = max(start_row, end_row)
        requests.append(
            {
                "updateBorders": {
                    "range": {"sheetId": sheet_id, "startRowIndex": top_idx, "endRowIndex": top_idx + 1, "startColumnIndex": 0, "endColumnIndex": cols_count},
                    "top": {"style": "SOLID", "width": 2, "color": color(120, 120, 120)},
                }
            }
        )
        requests.append(
            {
                "updateBorders": {
                    "range": {"sheetId": sheet_id, "startRowIndex": bottom_idx, "endRowIndex": bottom_idx + 1, "startColumnIndex": 0, "endColumnIndex": cols_count},
                    "bottom": {"style": "SOLID", "width": 2, "color": color(120, 120, 120)},
                }
            }
        )

    if requests:
        sheet.batch_update({"requests": requests})


def _build_daily_map(
    df: pd.DataFrame,
    cogs_df: pd.DataFrame,
    vat_rates: Dict[str, float],
    return_df: pd.DataFrame,
) -> Dict[str, Dict[str, float]]:
    data: Dict[str, Dict[str, float]] = {}
    subscription_vat_rate = 20.0
    fee_vat_rate = 20.0
    fee_categories_with_vat = {
        "Inbound_Transportation_Fee",
        "Removal_Fee",
        "Disposal_Fee",
        "Customer_Returns_Fee",
        "Shipping_Chargeback",
        "Storage_Charges",
    }

    def add(row_name: str, date_str: str, value: float) -> None:
        if row_name not in data:
            data[row_name] = {}
        data[row_name][date_str] = data[row_name].get(date_str, 0.0) + value

    df = df.copy()
    df["date"] = _date_key(df["Date"])
    df = df[df["date"].astype(str) >= PNL_START_DATE]
    df["Quantity Ordered"] = pd.to_numeric(df["Quantity Ordered"], errors="coerce").fillna(0.0)
    cancelled_by_date = (
        df.loc[df["Quantity Ordered"] <= 0, ["date", "Order ID"]]
        .groupby("date")["Order ID"]
        .nunique()
        .to_dict()
    )
    for date_str, count in cancelled_by_date.items():
        add("Cancelled_Orders_Seen", date_str, float(count))
    df = df[df["Quantity Ordered"] > 0].copy()
    df["Price_Total_GBP"] = pd.to_numeric(df["Price_Total_GBP"], errors="coerce").fillna(0.0)
    df["Price_VAT_GBP"] = pd.to_numeric(df["Price_VAT_GBP"], errors="coerce").fillna(0.0)
    df["Price_ExVAT_GBP"] = pd.to_numeric(df["Price_ExVAT_GBP"], errors="coerce").fillna(0.0)
    if "Shipping_Total_GBP" in df.columns:
        df["Shipping_Total_GBP"] = pd.to_numeric(df["Shipping_Total_GBP"], errors="coerce").fillna(0.0)
        df["Shipping_VAT_GBP"] = pd.to_numeric(df["Shipping_VAT_GBP"], errors="coerce").fillna(0.0)
        df["Shipping_ExVAT_GBP"] = pd.to_numeric(df["Shipping_ExVAT_GBP"], errors="coerce").fillna(0.0)
    if "Gift_Total_GBP" in df.columns:
        df["Gift_Total_GBP"] = pd.to_numeric(df["Gift_Total_GBP"], errors="coerce").fillna(0.0)
        df["Gift_VAT_GBP"] = pd.to_numeric(df["Gift_VAT_GBP"], errors="coerce").fillna(0.0)
        df["Gift_ExVAT_GBP"] = pd.to_numeric(df["Gift_ExVAT_GBP"], errors="coerce").fillna(0.0)
    if "Promotion_Total_GBP" in df.columns:
        df["Promotion_Total_GBP"] = pd.to_numeric(df["Promotion_Total_GBP"], errors="coerce").fillna(0.0)
        df["Promotion_VAT_GBP"] = pd.to_numeric(df["Promotion_VAT_GBP"], errors="coerce").fillna(0.0)
        df["Promotion_ExVAT_GBP"] = pd.to_numeric(df["Promotion_ExVAT_GBP"], errors="coerce").fillna(0.0)
    if "FBA_Fee_Total_GBP" in df.columns:
        df["FBA_Fee_Total_GBP"] = pd.to_numeric(df["FBA_Fee_Total_GBP"], errors="coerce").fillna(0.0)
        df["FBA_Fee_VAT_GBP"] = pd.to_numeric(df["FBA_Fee_VAT_GBP"], errors="coerce").fillna(0.0)
        df["FBA_Fee_ExVAT_GBP"] = pd.to_numeric(df["FBA_Fee_ExVAT_GBP"], errors="coerce").fillna(0.0)
    if "Commission_Total_GBP" in df.columns:
        df["Commission_Total_GBP"] = pd.to_numeric(df["Commission_Total_GBP"], errors="coerce").fillna(0.0)
        df["Commission_VAT_GBP"] = pd.to_numeric(df["Commission_VAT_GBP"], errors="coerce").fillna(0.0)
        df["Commission_ExVAT_GBP"] = pd.to_numeric(df["Commission_ExVAT_GBP"], errors="coerce").fillna(0.0)
    if "Digital_Fee_Total_GBP" in df.columns:
        df["Digital_Fee_Total_GBP"] = pd.to_numeric(df["Digital_Fee_Total_GBP"], errors="coerce").fillna(0.0)
        df["Digital_Fee_VAT_GBP"] = pd.to_numeric(df["Digital_Fee_VAT_GBP"], errors="coerce").fillna(0.0)
        df["Digital_Fee_ExVAT_GBP"] = pd.to_numeric(df["Digital_Fee_ExVAT_GBP"], errors="coerce").fillna(0.0)

    cogs_map: Dict[tuple[str, str], float] = {}
    if not cogs_df.empty:
        cogs_df = cogs_df.copy()
        cogs_df["order_id"] = cogs_df["order_id"].fillna("")
        cogs_df["sku"] = cogs_df["sku"].fillna("")
        cogs_df["cogs_total"] = pd.to_numeric(cogs_df["cogs_total"], errors="coerce").fillna(0.0)
        for _, row in cogs_df.iterrows():
            key = (row["order_id"], row["sku"])
            cogs_map[key] = cogs_map.get(key, 0.0) + float(row["cogs_total"])

    qty_by_key = (
        df.groupby(["Order ID", "SKU"])["Quantity Ordered"]
        .sum()
        .rename("qty_total")
        .to_dict()
    )

    for _, r in df.iterrows():
        if not r["date"]:
            continue
        total_gbp = r["Price_Total_GBP"]
        vat_gbp = r["Price_VAT_GBP"]
        ex_gbp = r["Price_ExVAT_GBP"]
        ship_total_gbp = r.get("Shipping_Total_GBP", 0.0)
        ship_vat_gbp = r.get("Shipping_VAT_GBP", 0.0)
        ship_ex_gbp = r.get("Shipping_ExVAT_GBP", 0.0)
        gift_total_gbp = r.get("Gift_Total_GBP", 0.0)
        gift_vat_gbp = r.get("Gift_VAT_GBP", 0.0)
        gift_ex_gbp = r.get("Gift_ExVAT_GBP", 0.0)
        promo_total_gbp = r.get("Promotion_Total_GBP", 0.0)
        promo_vat_gbp = r.get("Promotion_VAT_GBP", 0.0)
        promo_ex_gbp = r.get("Promotion_ExVAT_GBP", 0.0)
        fba_total_gbp = r.get("FBA_Fee_Total_GBP", 0.0)
        fba_vat_gbp = r.get("FBA_Fee_VAT_GBP", 0.0)
        fba_ex_gbp = r.get("FBA_Fee_ExVAT_GBP", 0.0)
        comm_total_gbp = r.get("Commission_Total_GBP", 0.0)
        comm_vat_gbp = r.get("Commission_VAT_GBP", 0.0)
        comm_ex_gbp = r.get("Commission_ExVAT_GBP", 0.0)
        dsf_total_gbp = r.get("Digital_Fee_Total_GBP", 0.0)
        dsf_vat_gbp = r.get("Digital_Fee_VAT_GBP", 0.0)
        dsf_ex_gbp = r.get("Digital_Fee_ExVAT_GBP", 0.0)
        key = (r.get("Order ID", ""), r.get("SKU", ""))
        cogs_ex_gbp = 0.0
        cogs_vat_gbp = 0.0
        if key in cogs_map:
            qty_total = qty_by_key.get(key, 0.0)
            if qty_total:
                cogs_ex_gbp = cogs_map[key] * (r["Quantity Ordered"] / qty_total)
            else:
                # If qty is missing in order ledger, apply full COGS to this line.
                cogs_ex_gbp = cogs_map[key]
            sku = r.get("SKU", "")
            if r.get("country_code") == "GB":
                rate = vat_rates.get(sku, 0.0)
                cogs_vat_gbp = round(cogs_ex_gbp * rate / 100.0, 2)
        cogs_ex_gbp = float(cogs_ex_gbp)
        cogs_vat_gbp = float(cogs_vat_gbp)
        cogs_ex_gbp_neg = -abs(cogs_ex_gbp)
        cogs_vat_gbp_neg = -abs(cogs_vat_gbp)
        cogs_total_gbp = cogs_ex_gbp_neg + cogs_vat_gbp_neg
        add("Quantity Ordered", r["date"], r["Quantity Ordered"])
        add("Price_Total", r["date"], total_gbp)
        add("Price_VAT", r["date"], vat_gbp)
        add("Price_ExVAT", r["date"], ex_gbp)
        add("Shipping_Total", r["date"], ship_total_gbp)
        add("Shipping_VAT", r["date"], ship_vat_gbp)
        add("Shipping_ExVAT", r["date"], ship_ex_gbp)
        add("Gift_Total", r["date"], gift_total_gbp)
        add("Gift_VAT", r["date"], gift_vat_gbp)
        add("Gift_ExVAT", r["date"], gift_ex_gbp)
        add("Promotion_Total", r["date"], promo_total_gbp)
        add("Promotion_VAT", r["date"], promo_vat_gbp)
        add("Promotion_ExVAT", r["date"], promo_ex_gbp)
        add("FBA_Fee_Total", r["date"], fba_total_gbp)
        add("FBA_Fee_VAT", r["date"], fba_vat_gbp)
        add("FBA_Fee_ExVAT", r["date"], fba_ex_gbp)
        add("Commission_Total", r["date"], comm_total_gbp)
        add("Commission_VAT", r["date"], comm_vat_gbp)
        add("Commission_ExVAT", r["date"], comm_ex_gbp)
        add("Digital_Fee_Total", r["date"], dsf_total_gbp)
        add("Digital_Fee_VAT", r["date"], dsf_vat_gbp)
        add("Digital_Fee_ExVAT", r["date"], dsf_ex_gbp)
        add("COGS_Total", r["date"], cogs_total_gbp)
        add("COGS_VAT", r["date"], cogs_vat_gbp_neg)
        add("COGS_ExVAT", r["date"], cogs_ex_gbp_neg)
        add("Gross_Profit_ExVAT", r["date"], ex_gbp + cogs_ex_gbp_neg)
        # Fees are stored as negatives, so add them to reduce profit.
        contrib = (
            ex_gbp
            + cogs_ex_gbp_neg
            + fba_ex_gbp
            + comm_ex_gbp
            + dsf_ex_gbp
            + ship_ex_gbp
            + gift_ex_gbp
            + promo_ex_gbp
        )
        add("Contribution_Profit_ExVAT", r["date"], contrib)

    # Add positive COGS when refunded items return to sellable inventory.
    if not return_df.empty:
        return_df = return_df.copy()
        return_df["return_date"] = _date_key(return_df.get("return_date"))
        return_df = return_df[return_df["return_date"].astype(str) >= PNL_START_DATE]
        return_df["token_cost"] = pd.to_numeric(return_df.get("token_cost"), errors="coerce").fillna(0.0)
        for _, row in return_df.iterrows():
            date_str = row.get("return_date") or ""
            if not date_str:
                continue
            sku = str(row.get("seller_sku", "")).strip()
            ex_val = float(row.get("token_cost") or 0.0)
            if ex_val == 0.0:
                continue
            vat_rate = vat_rates.get(sku, 0.0)
            vat_val = round(ex_val * vat_rate / 100.0, 2) if vat_rate > 0 else 0.0
            total_val = ex_val + vat_val
            add("COGS_ExVAT", date_str, ex_val)
            add("COGS_VAT", date_str, vat_val)
            add("COGS_Total", date_str, total_val)
            add("Gross_Profit_ExVAT", date_str, ex_val)
            add("Contribution_Profit_ExVAT", date_str, ex_val)

    return data


def main() -> None:
    if not ORDER_LEDGER_FX.exists():
        print({"status": "error", "error": "missing order_ledger_fx.csv", "path": str(ORDER_LEDGER_FX)})
        return

    df = pd.read_csv(ORDER_LEDGER_FX, dtype=str)
    required = ["Date", "Quantity Ordered", "Price_Total_GBP", "Price_VAT_GBP", "Price_ExVAT_GBP"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print({"status": "error", "error": "missing columns", "columns": missing})
        return

    cogs_df = pd.DataFrame()
    if ORDER_COGS.exists():
        cogs_df = pd.read_csv(ORDER_COGS, dtype=str)
    vat_rates: Dict[str, float] = {}
    if PRODUCT_DB.exists():
        prod = pd.read_csv(PRODUCT_DB, dtype=str).fillna("")
        rate_col = "last_vat_rate_pct" if "last_vat_rate_pct" in prod.columns else "vat_rate"
        if rate_col in prod.columns and "seller_sku" in prod.columns:
            for _, row in prod.iterrows():
                sku = str(row.get("seller_sku", "")).strip()
                rate_raw = str(row.get(rate_col, "")).strip().replace("%", "")
                if not sku:
                    continue
                try:
                    rate_val = float(rate_raw)
                except Exception:
                    rate_val = 0.0
                if rate_val > 0:
                    vat_rates[sku] = rate_val
    return_df = pd.DataFrame()
    if RETURN_COGS.exists():
        return_df = pd.read_csv(RETURN_COGS, dtype=str).fillna("")
    data_map = _build_daily_map(df, cogs_df, vat_rates, return_df)
    subscription_vat_rate = 20.0
    fee_vat_rate = 20.0
    fee_categories_with_vat = {
        "Inbound_Transportation_Fee",
        "Removal_Fee",
        "Disposal_Fee",
        "Customer_Returns_Fee",
        "Shipping_Chargeback",
        "Storage_Charges",
    }

    def _add_to_map(row_name: str, date_str: str, value: float) -> None:
        if row_name not in data_map:
            data_map[row_name] = {}
        data_map[row_name][date_str] = data_map[row_name].get(date_str, 0.0) + value

    # Add refunds from Level 3 official refunds (source of truth) to avoid window gaps.
    official_refunds_loaded = False
    if REFUNDS_OFFICIAL.exists():
        ref = pd.read_csv(REFUNDS_OFFICIAL, dtype=str).fillna("")
        if not ref.empty:
            official_refunds_loaded = True
            ref["date"] = _date_key(ref["Date"])
            ref = ref[ref["date"].astype(str) >= PNL_START_DATE]
            for col in [
                "Quantity Ordered",
                "Price_Total",
                "Shipping_Total",
                "Gift_Total",
                "Promotion_Total",
                "FBA_Fee_Total",
                "Commission_Total",
                "Digital_Fee_Total",
                "FixedClosingFee_Total",
            ]:
                if col in ref.columns:
                    ref[col] = pd.to_numeric(ref[col], errors="coerce").fillna(0.0)
            refund_sales = (
                ref.get("Price_Total", 0)
                + ref.get("Shipping_Total", 0)
                + ref.get("Gift_Total", 0)
                + ref.get("Promotion_Total", 0)
            )
            refund_expenses = (
                ref.get("FBA_Fee_Total", 0)
                + ref.get("Commission_Total", 0)
                + ref.get("Digital_Fee_Total", 0)
                + ref.get("FixedClosingFee_Total", 0)
            )
            for date_str, val in refund_sales.groupby(ref["date"]).sum().items():
                _add_to_map("Refund_Sales_Total", date_str, float(val))
            for date_str, val in refund_expenses.groupby(ref["date"]).sum().items():
                _add_to_map("Refund_Expenses_Total", date_str, float(val))
            if "Commission_Total" in ref.columns:
                for date_str, val in ref["Commission_Total"].groupby(ref["date"]).sum().items():
                    _add_to_map("Refund_Commission", date_str, float(val))
            if "Quantity Ordered" in ref.columns:
                ref["Refund_Units"] = pd.to_numeric(ref.get("Quantity Ordered"), errors="coerce").fillna(0.0).abs()
                ref.loc[ref["Refund_Units"] <= 0, "Refund_Units"] = 1.0
                for date_str, val in ref["Refund_Units"].groupby(ref["date"]).sum().items():
                    _add_to_map("Refund_Units", date_str, float(val))
                if "Order ID" in ref.columns:
                    for date_str, val in ref.groupby("date")["Order ID"].nunique().items():
                        _add_to_map("Refunded_Order_Count", date_str, float(val))

    # Add transaction-level expenses from normalized category ledger when available.
    cash_total_by_date: Dict[str, float] = {}
    if TXN_CATEGORY_LEDGER.exists():
        tx = pd.read_csv(TXN_CATEGORY_LEDGER, dtype=str).fillna("")
        if not tx.empty:
            tx["date"] = _date_key(tx["posted_date"])
            tx = tx[tx["date"].astype(str) >= PNL_START_DATE]
            tx["amount"] = pd.to_numeric(tx.get("amount_value"), errors="coerce").fillna(0.0)
            cash_total_by_date = tx.groupby("date")["amount"].sum().to_dict()
            cat_map = {
                "Inbound_Transportation_Fee": "Inbound_Transportation_Fee",
                "Removal_Fee": "Removal_Fee",
                "Disposal_Fee": "Disposal_Fee",
                "Customer_Returns_Fee": "Customer_Returns_Fee",
                "Warehouse_Lost_Reimbursement": "Warehouse_Lost_Reimbursement",
                "Reversal_Reimbursement": "Reversal_Reimbursement",
                "Retrocharge": "Retrocharge_Total",
                "Refund_Retrocharge": "Retrocharge_Total",
                "Inventory_Reimbursement": "Inventory_Reimbursement",
                "Compensated_Clawback": "Compensated_Clawback",
                "Shipping_Chargeback": "Shipping_Chargeback",
                "Storage_Charges": "Storage_Charges",
            }
            for _, r in tx.iterrows():
                date_str = r.get("date") or ""
                if not date_str:
                    continue
                category = str(r.get("category") or "")
                desc = str(r.get("description") or "")
                if category == "Subscription_Fee" or (category == "Service_Fee" and "Subscription" in desc):
                    amount = float(r.get("amount") or 0.0)
                    exvat = round(amount / (1.0 + subscription_vat_rate / 100.0), 2)
                    vat = round(amount - exvat, 2)
                    _add_to_map("Subscription_Fee_Total", date_str, amount)
                    _add_to_map("Subscription_Fee_ExVAT", date_str, exvat)
                    _add_to_map("Subscription_Fee_VAT", date_str, vat)
                    continue
                target = cat_map.get(category)
                if not target:
                    continue
                amt = float(r.get("amount") or 0.0)
                if target in fee_categories_with_vat:
                    exvat = round(amt / (1.0 + fee_vat_rate / 100.0), 2)
                    vat = round(amt - exvat, 2)
                    _add_to_map(target, date_str, exvat)
                    _add_to_map("Service_Fee_VAT", date_str, vat)
                else:
                    _add_to_map(target, date_str, amt)
    elif TXN_BREAKDOWNS.exists():
        # Fallback to raw breakdowns if category ledger not yet built.
        tx = pd.read_csv(TXN_BREAKDOWNS, dtype=str).fillna("")
        if not tx.empty:
            tx["date"] = _date_key(tx["posted_date"])
            tx = tx[tx["date"].astype(str) >= PNL_START_DATE]
            tx["amount"] = pd.to_numeric(tx.get("breakdown_amount"), errors="coerce").fillna(0.0)
            cash_total_by_date = tx.groupby("date")["amount"].sum().to_dict()
            for _, r in tx.iterrows():
                date_str = r.get("date") or ""
                if not date_str:
                    continue
                ttype = str(r.get("transaction_type") or "")
                btype = str(r.get("breakdown_type") or "")
                desc = str(r.get("description") or "")
                amt = float(r.get("amount") or 0.0)
                # Skip shipment sales/expenses to avoid double-counting order revenue.
                if ttype == "Shipment":
                    continue
                if ttype == "Refund":
                    if official_refunds_loaded:
                        continue
                    if btype == "Refunded Sales":
                        _add_to_map("Refund_Sales_Total", date_str, amt)
                    elif btype == "Refunded Expenses":
                        _add_to_map("Refund_Expenses_Total", date_str, amt)
                    continue
                if ttype == "ServiceFee":
                    if "FBAPostInboundTransportation" in desc:
                        _add_to_map("Inbound_Transportation_Fee", date_str, amt)
                    if "RemovalComplete" in desc:
                        _add_to_map("Removal_Fee", date_str, amt)
                    continue
                if ttype == "FBAInventoryReimbursement":
                    if "WAREHOUSE_LOST" in desc:
                        _add_to_map("Warehouse_Lost_Reimbursement", date_str, amt)
                    elif "REVERSAL_REIMBURSEMENT" in desc:
                        _add_to_map("Reversal_Reimbursement", date_str, amt)
                    continue
                if ttype == "Retrocharge":
                    _add_to_map("Retrocharge_Total", date_str, amt)

    # Add VAT on non-order service fees (from fee VAT ledger).
    if FEE_VAT_LEDGER.exists():
        fee_vat = pd.read_csv(FEE_VAT_LEDGER, dtype=str).fillna("")
        if not fee_vat.empty:
            fee_vat["date"] = pd.to_datetime(fee_vat.get("posted_date"), errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
            fee_vat = fee_vat[fee_vat["date"].astype(str) >= PNL_START_DATE]
            vat_col = "fee_vat" if "fee_vat" in fee_vat.columns else "amount_vat"
            fee_vat[vat_col] = pd.to_numeric(fee_vat.get(vat_col), errors="coerce").fillna(0.0)
            for date_str, val in fee_vat[vat_col].groupby(fee_vat["date"]).sum().items():
                _add_to_map("Service_Fee_VAT", date_str, float(val))
    all_dates = set()
    for row in data_map.values():
        all_dates.update(row.keys())
    date_cols = sorted(all_dates)
    for d in date_cols:
        gross_units = float(data_map.get("Quantity Ordered", {}).get(d, 0.0))
        refund_units = float(data_map.get("Refund_Units", {}).get(d, 0.0))
        data_map.setdefault("Gross_Units_Sold", {})[d] = gross_units
        data_map.setdefault("Net_Units_Sold", {})[d] = gross_units - refund_units
        data_map.setdefault("Refund_Unit_Rate", {})[d] = (refund_units / gross_units) if gross_units > 0 else 0.0

    rows: List[Dict[str, object]] = []
    for name in ROWS:
        row: Dict[str, object] = {"Parameter/Date": name}
        total = 0.0
        for d in date_cols:
            val = data_map.get(name, {}).get(d, 0.0)
            row[d] = round(val, 6) if name == "Refund_Unit_Rate" else round(val, 2)
            total += val
        if name == "Refund_Unit_Rate":
            total_refund_units = sum(float(data_map.get("Refund_Units", {}).get(d, 0.0)) for d in date_cols)
            total_gross_units = sum(float(data_map.get("Gross_Units_Sold", {}).get(d, 0.0)) for d in date_cols)
            row["Total"] = round((total_refund_units / total_gross_units) if total_gross_units > 0 else 0.0, 6)
        else:
            row["Total"] = round(total, 2)
        rows.append(row)

    profit_row = {"Parameter/Date": "Net_Profit_ExVAT"}
    total_profit = 0.0
    for d in date_cols:
        def get_val(key: str) -> float:
            return float(data_map.get(key, {}).get(d, 0.0))
        net_profit = (
            get_val("Price_ExVAT")
            + get_val("Shipping_ExVAT")
            + get_val("Gift_ExVAT")
            + get_val("Promotion_ExVAT")
            + get_val("COGS_ExVAT")
            + get_val("FBA_Fee_ExVAT")
            + get_val("Commission_ExVAT")
            + get_val("Digital_Fee_ExVAT")
            + get_val("Refund_Expenses_Total")
            + get_val("Refund_Sales_Total")
            + get_val("Warehouse_Lost_Reimbursement")
            + get_val("Reversal_Reimbursement")
            + get_val("Inventory_Reimbursement")
            + get_val("Compensated_Clawback")
            + get_val("Inbound_Transportation_Fee")
            + get_val("Removal_Fee")
            + get_val("Disposal_Fee")
            + get_val("Customer_Returns_Fee")
            + get_val("Retrocharge_Total")
            + get_val("Refund_Commission")
            + get_val("Shipping_Chargeback")
            + get_val("Subscription_Fee_ExVAT")
        )
        profit_row[d] = round(net_profit, 2)
        total_profit += net_profit
    profit_row["Total"] = round(total_profit, 2)
    rows.append(profit_row)

    payout_row = {"Parameter/Date": "Payout_Estimate"}
    total_payout = 0.0
    vat_diff_row = {"Parameter/Date": "VAT_Difference"}
    total_vat_diff = 0.0
    for d in date_cols:
        def get_val(key: str) -> float:
            return float(data_map.get(key, {}).get(d, 0.0))
        payout = (
            get_val("Price_Total")
            + get_val("Shipping_Total")
            + get_val("Gift_Total")
            + get_val("Promotion_Total")
            + get_val("Refund_Sales_Total")
            + get_val("Refund_Expenses_Total")
            + get_val("FBA_Fee_Total")
            + get_val("Commission_Total")
            + get_val("Digital_Fee_Total")
            + get_val("Inbound_Transportation_Fee")
            + get_val("Removal_Fee")
            + get_val("Disposal_Fee")
            + get_val("Customer_Returns_Fee")
            + get_val("Retrocharge_Total")
            + get_val("Refund_Commission")
            + get_val("Shipping_Chargeback")
            + get_val("Storage_Charges")
            + get_val("Subscription_Fee_Total")
            + get_val("Warehouse_Lost_Reimbursement")
            + get_val("Reversal_Reimbursement")
            + get_val("Inventory_Reimbursement")
            + get_val("Compensated_Clawback")
        )
        vat_diff = (
            get_val("Price_VAT")
            + get_val("Shipping_VAT")
            + get_val("Gift_VAT")
            + get_val("Promotion_VAT")
            + get_val("COGS_VAT")
            - get_val("FBA_Fee_VAT")
            - get_val("Commission_VAT")
            - get_val("Digital_Fee_VAT")
            - get_val("Subscription_Fee_VAT")
            - get_val("Service_Fee_VAT")
        )
        payout_row[d] = round(payout, 2)
        vat_diff_row[d] = round(vat_diff, 2)
        total_payout += payout
        total_vat_diff += vat_diff
    payout_row["Total"] = round(total_payout, 2)
    vat_diff_row["Total"] = round(total_vat_diff, 2)
    rows.append(payout_row)
    rows.append(vat_diff_row)

    out_cols = ["Parameter/Date"] + date_cols + ["Total"]
    df_out = pd.DataFrame(rows, columns=out_cols)
    OUT_PNL.parent.mkdir(parents=True, exist_ok=True)
    safe_to_csv(df_out, OUT_PNL, index=False)

    if PNL_WRITE_SHEETS:
        try:
            if gspread is None:
                raise RuntimeError("gspread not available")
            client = get_gspread_client()
            sheet = client.open_by_key(PNL_SHEET_ID)
            if PNL_WRITE_DAILY and not PNL_SUMMARY_ONLY:
                write_tab_with_retry(sheet, PNL_TAB, df_out)
                if PNL_FORMAT_SHEETS:
                    _apply_sheet_formatting(sheet, PNL_TAB, df_out)
            if PNL_MONTHLY_TABS and not PNL_SUMMARY_ONLY:
                monthly_tabs = _build_monthly_tabs(df_out)
                for tab_name, tab_df in monthly_tabs.items():
                    write_tab_with_retry(sheet, tab_name, tab_df)
                    if PNL_FORMAT_SHEETS:
                        _apply_sheet_formatting(sheet, tab_name, tab_df)
            summary_df = _build_summary_tab(df_out)
            if not summary_df.empty:
                write_tab_with_retry(sheet, PNL_SUMMARY_TAB, summary_df)
                if PNL_FORMAT_SHEETS:
                    _apply_sheet_formatting(sheet, PNL_SUMMARY_TAB, summary_df)
        except Exception as exc:
            print({"status": "warning", "alert": "sheets_error", "error": str(exc)})

    print({"status": "success", "rows": len(df_out), "snapshot": str(OUT_PNL), "start_date": PNL_START_DATE, "write_sheets": PNL_WRITE_SHEETS})


if __name__ == "__main__":
    main()

