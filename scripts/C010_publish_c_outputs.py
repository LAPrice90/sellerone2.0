from __future__ import annotations

import os
from pathlib import Path

import gspread
import pandas as pd


OUT = Path("out")
SHEET_ID = "1z_0QuVvDBNrDwoOakpEV69ABugojt4loRhyTHSdIVw8"


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
    write_sheets = os.environ.get("C_WRITE_SHEETS", "0").strip() == "1"
    if not write_sheets:
        print({"status": "skipped", "reason": "C_WRITE_SHEETS=0"})
        return

    client = get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)

    tabs = [
        ("Inbound_Status", OUT / "inbound_delivery_status.csv"),
        ("Inbound_Missing_Units", OUT / "inbound_missing_units.csv"),
        ("Inbound_Costs_Summary", OUT / "inbound_costs_allocated.csv"),
        ("Inbound_Costs_Unallocated", OUT / "inbound_costs_unallocated.csv"),
        ("Storage_Fees_Monthly", OUT / "fba_storage_fee_charges_monthly.csv"),
        ("Long_Term_Storage_Fees", OUT / "fba_long_term_storage_fee_charges_monthly.csv"),
        ("Token_Maturity_Window", OUT / "token_maturity_window.csv"),
    ]

    written = []
    for title, path in tabs:
        df = _read_csv(path)
        if df.empty:
            continue
        _write_tab(sheet, title, df)
        written.append(title)

    print({"status": "success", "tabs_written": written})


if __name__ == "__main__":
    main()
