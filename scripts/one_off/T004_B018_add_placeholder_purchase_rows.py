"""
Add placeholder purchase rows to Orders sheet for missing SKUs.
Quantities are set to expected_token_total from Token_Stock_Recon_Mismatches.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"

MISMATCH_TAB = "Token_Stock_Recon_Mismatches"
ORDERS_TAB = "Orders"

PLACEHOLDER_DATE = "01/11/2025"

SKU_COSTS = {
    "02-7AZG-O0CV": "0.59",
    "A1-KSU1-GZMS": "0.95",
    "JH-97NP-GJDG": "0.78",
}


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def main() -> None:
    print({"status": "skip", "reason": "placeholder_purchases_disabled_purchase_only_rule"})
    return
    client = get_gspread_client()
    token_sheet = client.open_by_key(TOKENS_SHEET_ID)
    orders_sheet = client.open_by_key(ORDERS_SHEET_ID)

    mismatch_ws = token_sheet.worksheet(MISMATCH_TAB)
    orders_ws = orders_sheet.worksheet(ORDERS_TAB)

    mismatches = load_sheet_df(mismatch_ws)
    if mismatches.empty:
        print({"status": "skip", "reason": "no_mismatches"})
        return

    if "expected_token_total" not in mismatches.columns:
        print({"status": "skip", "reason": "missing_expected_token_total"})
        return

    mismatches["expected_token_total"] = (
        pd.to_numeric(mismatches["expected_token_total"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    orders_vals = orders_ws.get_all_values()
    header = orders_vals[0] if orders_vals else []
    existing = set()
    if orders_vals:
        for row in orders_vals[1:]:
            if len(row) >= 3:
                existing.add(row[2].strip())

    rows_to_add = []
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    for sku, cost in SKU_COSTS.items():
        if sku in existing:
            continue
        exp = int(mismatches.loc[mismatches["seller_sku"] == sku, "expected_token_total"].sum())
        if exp <= 0:
            continue
        # Build row to match sheet columns.
        row = [""] * len(header)
        # Column positions are based on existing sheet structure.
        # ['', '', 'SKU', 'Name', 'Asin', 'Supplier', 'Supply Code', 'Cost PU',
        #  'Order Date', 'Ordered', 'Delivered', 'Sent to FBA', ...]
        if len(row) >= 3:
            row[2] = sku
        if len(row) >= 8:
            row[7] = cost
        if len(row) >= 9:
            row[8] = PLACEHOLDER_DATE
        if len(row) >= 10:
            row[9] = str(exp)
        if len(row) >= 11:
            row[10] = str(exp)
        if len(row) >= 12:
            row[11] = str(exp)
        rows_to_add.append(row)

    if not rows_to_add:
        print({"status": "skip", "reason": "no_rows_added", "timestamp": now_iso})
        return

    orders_ws.append_rows(rows_to_add, value_input_option="RAW")
    print({"status": "success", "rows_added": len(rows_to_add), "timestamp": now_iso})


if __name__ == "__main__":
    main()

