from __future__ import annotations

import os
from pathlib import Path

import gspread
import pandas as pd

OUT = Path("out")
TAB_SPECS = [
    ("E_Sales_Velocity", OUT / "sku_sales_velocity.csv"),
    ("E_ROI_Snapshot", OUT / "sku_roi_snapshot.csv"),
    ("E_Restock_Signals", OUT / "sku_restock_signals.csv"),
    ("E_Performance_Summary", OUT / "sku_performance_summary.csv"),
    ("E_Study_Report", OUT / "e_study_report.csv"),
    ("E_Sales_Truth_Reconciliation", OUT / "sales_truth_reconciliation_latest.csv"),
    ("E_Daily_Sales_Truth", OUT / "sku_daily_sales_truth_latest.csv"),
]


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _write_tab(sheet: gspread.Spreadsheet, title: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    values = [list(df.columns)] + df.values.tolist()
    try:
        ws = sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=max(len(values) + 10, 2000), cols=max(len(df.columns) + 2, 8))
    else:
        ws.clear()
    ws.update(range_name="A1", values=values)


def main() -> None:
    write_sheets = os.environ.get("E_WRITE_SHEETS", "0").strip() == "1"
    if not write_sheets:
        print({"status": "skipped", "reason": "E_WRITE_SHEETS=0"})
        return

    sheet_id = os.environ.get("E_SHEET_ID", "").strip()
    if not sheet_id:
        print({"status": "skipped", "reason": "E_SHEET_ID not set"})
        return

    client = get_gspread_client()
    sheet = client.open_by_key(sheet_id)

    written = []
    for title, path in TAB_SPECS:
        df = _read_csv(path)
        if df.empty:
            continue
        _write_tab(sheet, title, df)
        written.append(title)

    print({"status": "success", "tabs_written": written})


if __name__ == "__main__":
    main()

