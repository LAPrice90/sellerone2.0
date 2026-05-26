"""
Build raw stock event rows from inventory ledger report for observation only.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
except ModuleNotFoundError:
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe

try:
    import gspread
except Exception:
    gspread = None

if TYPE_CHECKING:
    import gspread as gspread_types

SHEET_ID = "1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s"
TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
RAW_TAB = "Stock_Events_raw"
TOKENS_RAW_TAB = "Stock_Adjustments_raw"
LEDGER_CSV = Path("out/inventory_ledger_raw.csv")
OUT_CSV = Path("out/stock_events_raw.csv")
SQL_TABLE = "a_stock_events_raw"


def get_gspread_client() -> "gspread_types.Client":
    if gspread is None:
        raise RuntimeError("gspread not available")
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def _write_sheets_enabled() -> bool:
    return os.environ.get("A006_WRITE_SHEETS", "1").strip() == "1" and gspread is not None


def _write_local_output(df: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_CSV, index=False)

    def write_sql() -> None:
        nonlocal sql_rows
        config = StorageConfig.from_env()
        store = connect_store(config)
        try:
            result = replace_table_from_dataframe(store, SQL_TABLE, df)
        finally:
            store.close()
        sql_rows = int(result["rows"])

    if mode == "sql_primary_csv_export":
        write_sql()
        write_csv()
    elif mode == "sql_shadow":
        write_csv()
        write_sql()
    else:
        write_csv()

    return {
        "mode": mode,
        "sql_table": SQL_TABLE if sql_rows or mode != "csv" else "",
        "sql_rows": sql_rows,
    }


def _publish_sheets(out: pd.DataFrame) -> list[str]:
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
    return [RAW_TAB, TOKENS_RAW_TAB]


def main() -> None:
    if not LEDGER_CSV.exists():
        raise RuntimeError("Missing out/inventory_ledger_raw.csv")

    df = pd.read_csv(LEDGER_CSV, dtype=str).fillna("")
    if df.empty:
        output = _write_local_output(df)
        print({"status": "success", "row_count": 0, "snapshot": str(OUT_CSV), "sheet_tabs": [], "write_sheets": False, **output})
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

    output = _write_local_output(out)
    sheet_tabs = _publish_sheets(out) if _write_sheets_enabled() else []

    print(
        {
            "status": "success",
            "row_count": len(out),
            "snapshot": str(OUT_CSV),
            "sheet_tabs": sheet_tabs,
            "write_sheets": bool(sheet_tabs),
            **output,
        }
    )


if __name__ == "__main__":
    main()

