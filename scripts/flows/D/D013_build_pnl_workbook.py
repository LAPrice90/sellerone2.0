"""
Build a readable P&L workbook in Google Sheets:
00_Settings, 01_Raw_Daily, 02_Mapping, 03_PnL_Monthly, 04_PnL_Daily_View

Source: out/pnl_daily.csv (wide matrix).
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import gspread

PNL_DAILY = Path("out/pnl_daily.csv")
TXN_MAPPING = Path("out/transaction_category_mapping.csv")

PNL_SHEET_ID = os.environ.get("PNL_SHEET_ID", "1aT26UYnTBP6-oNz0RIWVCRbuuN1RmP4_VwHEeiNzxKc")
TAB_SETTINGS = os.environ.get("PNL_TAB_SETTINGS", "00_Settings")
TAB_RAW = os.environ.get("PNL_TAB_RAW", "01_Raw_Daily")
TAB_MAPPING = os.environ.get("PNL_TAB_MAPPING", "02_Mapping")
TAB_MONTHLY = os.environ.get("PNL_TAB_MONTHLY", "03_PnL_Monthly")
TAB_DAILY_VIEW = os.environ.get("PNL_TAB_DAILY_VIEW", "04_PnL_Daily_View")


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def write_tab(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> gspread.Worksheet:
    payload = [list(df.columns)] + df.where(pd.notnull(df), "").values.tolist()
    try:
        ws = sheet.worksheet(tab_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    ws.update(range_name="A1", values=payload, value_input_option="USER_ENTERED")
    return ws


def _color(r: int, g: int, b: int) -> dict:
    return {"red": r / 255.0, "green": g / 255.0, "blue": b / 255.0}


def _format_table(sheet: gspread.Spreadsheet, ws: gspread.Worksheet, df: pd.DataFrame, freeze_cols: int = 1) -> None:
    if df.empty:
        return
    rows = len(df) + 1
    cols = len(df.columns)
    sheet_id = ws.id
    requests: List[dict] = []

    # Remove existing banding on this sheet to avoid API errors
    try:
        meta = sheet.fetch_sheet_metadata()
        for s in meta.get("sheets", []):
            props = s.get("properties", {})
            if props.get("sheetId") != sheet_id:
                continue
            banded = s.get("bandedRanges", []) or []
            for b in banded:
                band_id = b.get("bandedRangeId")
                if band_id is not None:
                    requests.append({"deleteBanding": {"bandedRangeId": band_id}})
    except Exception:
        pass

    # Freeze header and first column(s)
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": freeze_cols}},
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        }
    )

    # Header style
    requests.append(
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": cols},
                "cell": {"userEnteredFormat": {"backgroundColor": _color(31, 41, 55), "textFormat": {"bold": True, "foregroundColor": _color(255, 255, 255)}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        }
    )

    # Light banding
    requests.append(
        {
            "addBanding": {
                "bandedRange": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": rows, "startColumnIndex": 0, "endColumnIndex": cols},
                    "rowProperties": {"firstBandColor": _color(245, 247, 250), "secondBandColor": _color(255, 255, 255)},
                }
            }
        }
    )

    sheet.batch_update({"requests": requests})


def _load_pnl_daily() -> pd.DataFrame:
    if not PNL_DAILY.exists():
        raise FileNotFoundError("out/pnl_daily.csv not found. Run D001_build_pnl_daily.py first.")
    df = pd.read_csv(PNL_DAILY, dtype=str).fillna("")
    return df


def _build_raw_daily(df_pnl: pd.DataFrame) -> pd.DataFrame:
    date_cols = [c for c in df_pnl.columns if c not in ("Parameter/Date", "Total")]
    date_cols = sorted(date_cols)
    row_map = {row["Parameter/Date"]: row for _, row in df_pnl.iterrows()}

    def val(row_name: str, date: str) -> float:
        v = row_map.get(row_name, {}).get(date, 0)
        try:
            return float(v)
        except Exception:
            return 0.0

    rows = []
    for d in date_cols:
        sales_ex = val("Price_ExVAT", d)
        sales_vat = val("Price_VAT", d)
        sales_inc = val("Price_Total", d)
        fees_ex = val("FBA_Fee_ExVAT", d) + val("Commission_ExVAT", d) + val("Digital_Fee_ExVAT", d) + val("Shipping_Chargeback", d)
        fees_vat = val("FBA_Fee_VAT", d) + val("Commission_VAT", d) + val("Digital_Fee_VAT", d) + val("Subscription_Fee_VAT", d) + val("Service_Fee_VAT", d)

        rows.append(
            {
                "Date": d,
                "Orders": val("Quantity Ordered", d),
                "Units": val("Quantity Ordered", d),
                "Sales_ExVAT": sales_ex,
                "Sales_VAT": sales_vat,
                "Sales_IncVAT": sales_inc,
                "COGS": val("COGS_ExVAT", d),
                "Amazon_Fees_ExVAT": fees_ex,
                "Amazon_Fees_VAT": fees_vat,
                "Refunds_ExVAT": val("Refund_Sales_Total", d),
                "Refunds_VAT": 0.0,
                "Inbound_Transport": val("Inbound_Transportation_Fee", d),
                "Storage_Fees": val("Storage_Charges", d),
                "Other_OpEx": val("Subscription_Fee_ExVAT", d),
                "Gross_Profit_ExVAT": val("Gross_Profit_ExVAT", d),
                "Contribution_Profit": val("Contribution_Profit_ExVAT", d),
                "Net_Profit_ExVAT": val("Net_Profit_ExVAT", d),
                "Payout_Estimate": val("Payout_Estimate", d),
                "VAT_Difference": val("VAT_Difference", d),
            }
        )
    df = pd.DataFrame(rows)
    return df


def _build_settings(df_raw: pd.DataFrame) -> pd.DataFrame:
    months = sorted({str(d)[:7] for d in df_raw["Date"].tolist() if len(str(d)) >= 7})
    selected = months[-1] if months else ""
    rows = [
        ["Month_Selected", selected],
        ["VAT_Rate", 0.20],
        ["Currency", "GBP"],
        ["Show_Daily_Columns", "No"],
    ]
    return pd.DataFrame(rows, columns=["Setting", "Value"])


def _build_mapping() -> pd.DataFrame:
    if TXN_MAPPING.exists():
        return pd.read_csv(TXN_MAPPING, dtype=str).fillna("")
    cols = ["Source_Field", "Source_Value", "P&L_Group", "P&L_Line", "Sign", "VAT_Treatment", "Notes"]
    return pd.DataFrame(columns=cols)


def _build_monthly(df_raw: pd.DataFrame) -> pd.DataFrame:
    if df_raw.empty:
        return pd.DataFrame()
    df_raw["month"] = df_raw["Date"].astype(str).str[:7]
    month = sorted(df_raw["month"].unique())[-1]
    month_df = df_raw[df_raw["month"] == month].copy()
    days = max(len(month_df), 1)

    sales = month_df["Sales_ExVAT"].sum()
    rows = []

    def add_line(label: str, value: float, group: str) -> None:
        pct = value / sales if sales else 0.0
        rows.append({"Line Item": label, "Month Total": round(value, 2), "% of Sales": round(pct, 4), "Daily Avg": round(value / days, 2), "Group": group})

    def add_header(label: str) -> None:
        rows.append({"Line Item": label, "Month Total": "", "% of Sales": "", "Daily Avg": "", "Group": "Header"})

    # Revenue
    add_header("REVENUE")
    add_line("Sales (Ex VAT)", sales, "Revenue")

    # Cost of Sales
    add_header("COST OF GOODS SOLD")
    add_line("COGS", month_df["COGS"].sum(), "Cost of Sales")
    add_line("Gross Profit (Ex VAT)", month_df["Gross_Profit_ExVAT"].sum(), "Subtotal")

    # Amazon Selling Fees
    add_header("AMAZON SELLING FEES")
    add_line("FBA Fees", month_df["Amazon_Fees_ExVAT"].sum(), "Amazon Fees")
    add_line("Subscription Fees", month_df["Other_OpEx"].sum(), "Amazon Fees")
    add_line("Total Amazon Fees", month_df["Amazon_Fees_ExVAT"].sum() + month_df["Other_OpEx"].sum(), "Subtotal")

    # Refunds & Adjustments
    add_header("REFUNDS & ADJUSTMENTS")
    add_line("Refunds (Sales)", month_df["Refunds_ExVAT"].sum(), "Refunds")
    add_line("Net Refund Impact", month_df["Refunds_ExVAT"].sum(), "Subtotal")

    # Fulfilment & Storage
    add_header("FULFILMENT & STORAGE")
    add_line("Inbound Transport", month_df["Inbound_Transport"].sum(), "Fulfilment")
    add_line("Storage Fees", month_df["Storage_Fees"].sum(), "Fulfilment")
    add_line("Total Fulfilment", month_df["Inbound_Transport"].sum() + month_df["Storage_Fees"].sum(), "Subtotal")

    # Operating Expenses
    add_header("OPERATING EXPENSES")
    add_line("Other OpEx", month_df["Other_OpEx"].sum(), "Operating Expenses")

    # Net Profit
    add_header("NET PROFIT")
    add_line("Net Profit (Ex VAT)", month_df["Net_Profit_ExVAT"].sum(), "Net")

    # VAT
    add_header("VAT")
    add_line("VAT on Sales", month_df["Sales_VAT"].sum(), "VAT")
    add_line("VAT on Fees", month_df["Amazon_Fees_VAT"].sum(), "VAT")
    add_line("VAT Difference", month_df["VAT_Difference"].sum(), "VAT")

    out = pd.DataFrame(rows)
    out = out[["Line Item", "Month Total", "% of Sales", "Daily Avg", "Group"]]
    return out


def _build_daily_view(df_raw: pd.DataFrame) -> pd.DataFrame:
    if df_raw.empty:
        return pd.DataFrame()
    keep = [
        "Sales_ExVAT",
        "COGS",
        "Amazon_Fees_ExVAT",
        "Refunds_ExVAT",
        "Net_Profit_ExVAT",
        "Payout_Estimate",
    ]
    pivot = df_raw.set_index("Date")[keep].T
    pivot.insert(0, "Line Item", pivot.index)
    pivot.reset_index(drop=True, inplace=True)
    return pivot


def _format_monthly(sheet: gspread.Spreadsheet, ws: gspread.Worksheet, df: pd.DataFrame, header_row: int = 1) -> None:
    if df.empty:
        return
    rows = len(df) + header_row
    cols = len(df.columns) - 1  # exclude Group column from display formatting
    sheet_id = ws.id
    requests: List[dict] = []

    # Hide Group column if present (last column)
    if "Group" in df.columns:
        group_col = df.columns.get_loc("Group")
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": group_col, "endIndex": group_col + 1},
                    "properties": {"hiddenByUser": True},
                    "fields": "hiddenByUser",
                }
            }
        )

    # Header
    requests.append(
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": header_row - 1, "endRowIndex": header_row, "startColumnIndex": 0, "endColumnIndex": cols},
                "cell": {"userEnteredFormat": {"backgroundColor": _color(31, 41, 55), "textFormat": {"bold": True, "foregroundColor": _color(255, 255, 255)}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        }
    )

    # Freeze
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": header_row, "frozenColumnCount": 1}},
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        }
    )

    # Section headers
    group_colors = {
        "Revenue": _color(55, 65, 81),
        "Cost of Sales": _color(55, 65, 81),
        "Amazon Fees": _color(55, 65, 81),
        "Refunds": _color(55, 65, 81),
        "Fulfilment": _color(55, 65, 81),
        "Operating Expenses": _color(55, 65, 81),
        "Net": _color(31, 41, 55),
        "VAT": _color(55, 65, 81),
        "Subtotal": _color(220, 245, 220),
    }

    # Apply light fill to subtotal lines
    for i, row in df.iterrows():
        group = row.get("Group", "")
        if group == "Header":
            requests.append(
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": header_row + i, "endRowIndex": header_row + i + 1, "startColumnIndex": 0, "endColumnIndex": cols},
                        "cell": {"userEnteredFormat": {"backgroundColor": _color(31, 41, 55), "textFormat": {"bold": True, "foregroundColor": _color(255, 255, 255)}}},
                        "fields": "userEnteredFormat(backgroundColor,textFormat)",
                    }
                }
            )
        elif group == "Subtotal" or row["Line Item"].startswith("Gross Profit") or row["Line Item"].startswith("Net Profit"):
            requests.append(
                {
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": header_row + i, "endRowIndex": header_row + i + 1, "startColumnIndex": 0, "endColumnIndex": cols},
                        "cell": {"userEnteredFormat": {"backgroundColor": _color(230, 245, 230), "textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat(backgroundColor,textFormat)",
                    }
                }
            )

    sheet.batch_update({"requests": requests})


def _write_monthly_with_kpi(sheet: gspread.Spreadsheet, df_monthly: pd.DataFrame, month_label: str) -> gspread.Worksheet:
    # KPI band (row 1-2), header row at 4, data starts row 5
    try:
        ws = sheet.worksheet(TAB_MONTHLY)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=TAB_MONTHLY, rows=200, cols=10)

    # KPI band
    if not df_monthly.empty:
        month_total = df_monthly
        def _val(label: str) -> float:
            try:
                return float(month_total.loc[month_total["Line Item"] == label, "Month Total"].values[0])
            except Exception:
                return 0.0
        sales = _val("Sales (Ex VAT)")
        gross = _val("Gross Profit (Ex VAT)")
        net = _val("Net Profit (Ex VAT)")
        orders = 0.0
        kpi = [
            ["Month", month_label, "", "Sales (Ex VAT)", sales, "", "Gross Profit", gross, "", "Net Profit", net],
        ]
        ws.update("A1", kpi, value_input_option="USER_ENTERED")

    # Table header and body
    header_row = 4
    payload = [list(df_monthly.columns)] + df_monthly.where(pd.notnull(df_monthly), "").values.tolist()
    ws.update(range_name=f"A{header_row}", values=payload, value_input_option="USER_ENTERED")
    return ws


def main() -> None:
    df_pnl = _load_pnl_daily()
    df_raw = _build_raw_daily(df_pnl)
    df_settings = _build_settings(df_raw)
    df_mapping = _build_mapping()
    df_monthly = _build_monthly(df_raw)
    df_daily_view = _build_daily_view(df_raw)

    client = get_gspread_client()
    sheet = client.open_by_key(PNL_SHEET_ID)

    ws_settings = write_tab(sheet, TAB_SETTINGS, df_settings)
    _format_table(sheet, ws_settings, df_settings, freeze_cols=1)

    ws_raw = write_tab(sheet, TAB_RAW, df_raw)
    _format_table(sheet, ws_raw, df_raw, freeze_cols=2)

    ws_map = write_tab(sheet, TAB_MAPPING, df_mapping)
    _format_table(sheet, ws_map, df_mapping, freeze_cols=1)

    ws_monthly = _write_monthly_with_kpi(sheet, df_monthly, df_settings.iloc[0]["Value"])
    _format_monthly(sheet, ws_monthly, df_monthly, header_row=4)

    ws_daily = write_tab(sheet, TAB_DAILY_VIEW, df_daily_view)
    _format_table(sheet, ws_daily, df_daily_view, freeze_cols=1)

    print({"status": "success", "rows_raw": len(df_raw), "month": df_settings.iloc[0]["Value"], "sheet": PNL_SHEET_ID})


if __name__ == "__main__":
    main()

