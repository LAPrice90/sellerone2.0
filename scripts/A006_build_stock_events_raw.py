"""
Build raw stock event rows from inventory ledger report for observation only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd

SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
RAW_TAB = "Stock_Events_raw"
TOKENS_RAW_TAB = "Stock_Adjustments_raw"
LEDGER_CSV = Path("out/inventory_ledger_raw.csv")
OUT_CSV = Path("out/stock_events_raw.csv")


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def main() -> None:
    if not LEDGER_CSV.exists():
        raise RuntimeError("Missing out/inventory_ledger_raw.csv")

    df = pd.read_csv(LEDGER_CSV, dtype=str).fillna("")
    if df.empty:
        print({"status": "success", "row_count": 0, "snapshot": str(OUT_CSV)})
        OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_CSV, index=False)
        return

    out = pd.DataFrame(
        {
            "event_id": df.get("Reference ID", ""),
            "event_date": df.get("Date and Time", df.get("Date", "")),
            "sku": df.get("MSKU", ""),
            "asin": df.get("ASIN", ""),
            "fnsku": df.get("FNSKU", ""),
            "event_type": df.get("Event Type", ""),
            "quantity": df.get("Quantity", ""),
            "disposition": df.get("Disposition", ""),
            "reason_code": df.get("Reason", ""),
            "country": df.get("Country", ""),
            "fulfillment_center": df.get("Fulfillment Center", ""),
            "reconciled_qty": df.get("Reconciled Quantity", ""),
            "unreconciled_qty": df.get("Unreconciled Quantity", ""),
            "source_report": "Inventory_Ledger",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    client = get_gspread_client()
    payload = [list(out.columns)] + out.fillna("").astype(str).values.tolist()

    sheet = client.open_by_key(SHEET_ID)
    try:
        ws = sheet.worksheet(RAW_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=RAW_TAB, rows=max(len(payload) + 10, 2000), cols=max(len(out.columns) + 5, 40))
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)

    token_sheet = client.open_by_key(TOKENS_SHEET_ID)
    try:
        t_ws = token_sheet.worksheet(TOKENS_RAW_TAB)
    except gspread.WorksheetNotFound:
        t_ws = token_sheet.add_worksheet(title=TOKENS_RAW_TAB, rows=max(len(payload) + 10, 2000), cols=max(len(out.columns) + 5, 40))
    else:
        t_ws.clear()
    t_ws.update(range_name="A1", values=payload)

    print(
        {
            "status": "success",
            "row_count": len(out),
            "snapshot": str(OUT_CSV),
            "sheet_tabs": [RAW_TAB, TOKENS_RAW_TAB],
        }
    )


if __name__ == "__main__":
    main()
