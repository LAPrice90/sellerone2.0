"""
Sync Token_Allocations sheet to local CSV so downstream COGS is consistent.
"""

from __future__ import annotations

from pathlib import Path
import os
import sys

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ALLOC_TAB = "Token_Allocations"
OUT_PATH = Path("out/token_allocations_live.csv")
FORCE_SYNC = os.environ.get("TOKEN_ALLOC_SYNC_FORCE", "0").strip() == "1"


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
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
    alloc_ws = sheet.worksheet(ALLOC_TAB)
    alloc_df = load_sheet_df(alloc_ws)

    if alloc_df.empty:
        print("Token_Allocations empty; nothing to sync.")
        return

    if OUT_PATH.exists() and not FORCE_SYNC:
        try:
            local_df = pd.read_csv(OUT_PATH, dtype=str).fillna("")
        except Exception:
            local_df = pd.DataFrame()
        local_rows = len(local_df)
        sheet_rows = len(alloc_df)
        if local_rows > sheet_rows:
            print(
                {
                    "status": "skip",
                    "reason": "local_newer_than_sheet",
                    "local_rows": local_rows,
                    "sheet_rows": sheet_rows,
                }
            )
            return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    alloc_df.to_csv(OUT_PATH, index=False)
    print({"status": "success", "rows": len(alloc_df), "out": str(OUT_PATH)})


if __name__ == "__main__":
    main()
