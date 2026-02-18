"""
Reset all token allocations and re-run allocation with current rules.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKENS_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"

TOKEN_LEDGER_OUT = Path("out/token_ledger_live.csv")
ALLOC_OUT = Path("out/token_allocations_live.csv")


def _load_sheet_df(ws) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    token_ws = sheet.worksheet(TOKENS_TAB)
    alloc_ws = sheet.worksheet(ALLOC_TAB)

    token_df = _load_sheet_df(token_ws)
    if token_df.empty:
        raise SystemExit("Token_Ledger is empty")

    # Reset allocation fields.
    for col in ["allocated_order_id", "allocated_date"]:
        if col in token_df.columns:
            token_df[col] = ""
    if "status" in token_df.columns:
        token_df["status"] = token_df["status"].replace({"allocated": "available"})

    # Clear allocations sheet and local CSV.
    alloc_ws.clear()
    alloc_ws.append_row(
        [
            "order_id",
            "order_date",
            "seller_sku",
            "quantity",
            "token_id",
            "token_cost",
            "currency",
            "allocation_date",
            "source_level",
            "notes",
        ],
        value_input_option="RAW",
    )

    # Write token ledger back to sheet and local CSV.
    rows_out = [token_df.columns.tolist()] + token_df.astype(object).where(pd.notnull(token_df), "").values.tolist()
    token_ws.clear()
    token_ws.update(rows_out, value_input_option="RAW")

    TOKEN_LEDGER_OUT.parent.mkdir(parents=True, exist_ok=True)
    token_df.to_csv(TOKEN_LEDGER_OUT, index=False)

    ALLOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=[
        "order_id",
        "order_date",
        "seller_sku",
        "quantity",
        "token_id",
        "token_cost",
        "currency",
        "allocation_date",
        "source_level",
        "notes",
    ]).to_csv(ALLOC_OUT, index=False)

    print({"status": "success", "tokens": len(token_df)})


if __name__ == "__main__":
    main()
