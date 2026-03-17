"""
Create essential tabs in the C workbook (minimal, user-facing).

No data is written beyond headers.
"""

from __future__ import annotations

import os
from pathlib import Path

import gspread


C_SHEET_ID = "1z_0QuVvDBNrDwoOakpEV69ABugojt4loRhyTHSdIVw8"


def get_gspread_client() -> gspread.Client:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        cred_path = str(Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=cred_path)


def _ensure_tab(sheet: gspread.Spreadsheet, title: str, headers: list[str]) -> None:
    try:
        ws = sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=2000, cols=max(len(headers) + 2, 8))
        ws.update(range_name="A1", values=[headers])
        return
    # If empty, set headers once.
    existing = ws.get_all_values()
    if not existing:
        ws.update(range_name="A1", values=[headers])


def main() -> None:
    client = get_gspread_client()
    sheet = client.open_by_key(C_SHEET_ID)

    tabs = {
        "C_Run_Log": ["run_ts_utc", "status", "notes"],
        "Inbound_Status": ["inbound_shipment_id", "expected_qty", "received_qty", "missing_qty", "pct_received", "status", "updated_at_utc"],
        "Inbound_Missing_Units": ["inbound_shipment_id", "sku", "expected_qty", "received_qty", "missing_qty"],
        "Inbound_Costs_Summary": ["shipment_id", "currency", "event_count", "total_amount", "total_tax", "total_with_tax"],
        "Inbound_Costs_Unallocated": ["shipment_key", "amount", "currency", "unallocated_reason"],
        "Storage_Fees_Monthly": ["month_of_charge", "asin", "estimated_monthly_storage_fee", "currency"],
        "Long_Term_Storage_Fees": ["snapshot_date", "asin", "long_term_storage_fee", "currency"],
        "Token_Maturity_Window": ["inbound_shipment_id", "expected_qty", "received_qty", "in_flight_qty", "status", "updated_at_utc", "mature_on_utc", "is_mature"],
    }

    for title, headers in tabs.items():
        _ensure_tab(sheet, title, headers)

    print({"status": "success", "tabs": list(tabs.keys())})


if __name__ == "__main__":
    main()

