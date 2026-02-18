"""
Export Token_Ledger sheet to out/token_ledger_live.csv.
Used to keep local snapshot in sync for tests.
"""

from __future__ import annotations

from pathlib import Path

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
LEDGER_TAB = "Token_Ledger"
OUT_PATH = Path("out/token_ledger_live.csv")


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
    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    ledger_ws = sheet.worksheet(LEDGER_TAB)
    ledger = load_sheet_df(ledger_ws)
    if ledger.empty:
        print({"status": "skip", "reason": "empty_token_ledger"})
        return
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(OUT_PATH, index=False)
    print({"status": "success", "rows": len(ledger), "snapshot": str(OUT_PATH)})


if __name__ == "__main__":
    main()
