"""
Add lot_rank to Token_Ledger based on row order in orders_sheet_orders.csv.

Bottom row is newest; higher lot_rank means newer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat
from scripts.flows.B._finance_io import read_finance_frame


ORDERS_PATH = Path("out/orders_sheet_orders.csv")
TOKEN_LEDGER_REL = "token_ledger_live.csv"

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKENS_TAB = "Token_Ledger"


def _ensure_lot_id(row: pd.Series, idx: int) -> str:
    lot_id = str(row.get("Unnamed: 1", "")).strip()
    if lot_id:
        return lot_id
    sku = str(row.get("SKU", "")).strip()
    date = str(row.get("Order Date", "")).strip().replace("/", "")
    return f"{sku}-{date}-row{idx}"


def main() -> None:
    token_paths = resolve_compat_path(TOKEN_LEDGER_REL, default_system="B")
    token_path = token_paths.live_path if token_paths.live_path.exists() else token_paths.legacy_path
    if not token_path.exists():
        raise SystemExit("missing out/token_ledger_live.csv")

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    try:
        orders = read_finance_frame(ORDERS_PATH, "b_orders_sheet_orders", dtype=str).fillna("")
    except Exception:
        raise SystemExit("missing out/orders_sheet_orders.csv")
    if "SKU" not in orders.columns:
        raise SystemExit("orders_sheet_orders.csv missing SKU column")
    if "Unnamed: 1" not in orders.columns:
        orders["Unnamed: 1"] = ""

    orders = orders.reset_index(drop=True)
    lot_rank = {}
    for idx, row in orders.iterrows():
        lot_id = _ensure_lot_id(row, idx)
        if not lot_id:
            continue
        # Newer rows (bottom) should have higher rank.
        lot_rank[lot_id] = idx

    token_df = pd.read_csv(token_path, dtype=str).fillna("")
    if "lot_id" not in token_df.columns:
        raise SystemExit("token_ledger_live.csv missing lot_id column")
    token_df["lot_rank"] = token_df["lot_id"].map(lot_rank).fillna("")

    # Update local ledger
    write_csv_with_compat(
        token_df,
        path_or_rel=TOKEN_LEDGER_REL,
        default_system="B",
        index=False,
        mirror_legacy=True,
    )

    # Update sheet
    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    token_ws = sheet.worksheet(TOKENS_TAB)
    rows_out = [token_df.columns.tolist()] + token_df.astype(object).where(pd.notnull(token_df), "").values.tolist()
    token_ws.clear()
    token_ws.update(rows_out, value_input_option="RAW")

    print({"status": "success", "rows": len(token_df), "out": str(token_paths.live_path)})


if __name__ == "__main__":
    main()


