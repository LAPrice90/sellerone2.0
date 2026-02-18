"""
Fix Order_Master COGS for cancelled/zero-qty rows without rebuilding from Level 2.
Sets COGS_Total/ExVAT/VAT to 0 where Quantity Ordered <= 0.
"""
from __future__ import annotations

import os
from pathlib import Path
import time

import pandas as pd
import gspread
from gspread.exceptions import APIError

ORDER_MASTER = Path("out/order_master.csv")
SHEET_ID = os.environ.get("ORDER_MASTER_SHEET_ID", "1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A")
TAB_NAME = os.environ.get("ORDER_MASTER_TAB", "Order_Master")
SKIP_SHEETS = os.environ.get("ORDER_MASTER_SKIP_SHEETS", "0").strip() == "1"

SHEETS_MAX_RETRIES = 5
SHEETS_BACKOFF = 2.0


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def write_tab_with_retry(sheet: gspread.Spreadsheet, tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    for attempt in range(1, SHEETS_MAX_RETRIES + 1):
        try:
            try:
                ws = sheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
            else:
                ws.clear()
            ws.update(range_name="A1", values=payload)
            return
        except APIError:
            if attempt == SHEETS_MAX_RETRIES:
                raise
            time.sleep(SHEETS_BACKOFF * attempt)


def main() -> None:
    if not ORDER_MASTER.exists():
        print({"status": "error", "error": "missing out/order_master.csv"})
        return
    df = pd.read_csv(ORDER_MASTER, dtype=str).fillna("")
    qty = pd.to_numeric(df.get("Quantity Ordered"), errors="coerce").fillna(0.0)
    cancelled = qty <= 0
    for col in ["COGS_Total", "COGS_ExVAT", "COGS_VAT"]:
        if col in df.columns:
            df.loc[cancelled, col] = "0"
    df.to_csv(ORDER_MASTER, index=False)

    if not SKIP_SHEETS:
        try:
            client = get_gspread_client()
            sheet = client.open_by_key(SHEET_ID)
            write_tab_with_retry(sheet, TAB_NAME, df)
        except Exception as exc:
            print({"status": "warning", "alert": "sheets_error", "error": str(exc)})

    print({"status": "success", "rows": len(df), "snapshot": str(ORDER_MASTER)})


if __name__ == "__main__":
    main()
