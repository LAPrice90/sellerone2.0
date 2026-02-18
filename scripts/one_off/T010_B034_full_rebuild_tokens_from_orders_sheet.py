"""
Full rebuild of Token_Ledger + Token_Allocations from orders_sheet_orders.csv.

Rules:
- Use Sent to FBA as quantity.
- Process rows bottom-to-top (newest first).
- One lot_id format only (SKU-YYYYMMDD-row{idx}).
- Fail if duplicate lot_id would be created.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd


ORDERS_PATH = Path("out/orders_sheet_orders.csv")

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKENS_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"

TOKEN_LEDGER_OUT = Path("out/token_ledger_live.csv")
ALLOC_OUT = Path("out/token_allocations_live.csv")


def _parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    value = str(value).replace(",", "").replace("£", "").replace("Ł", "").strip()
    try:
        return float(value)
    except Exception:
        return 0.0


def _num(value: str) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _lot_id(row: pd.Series, idx: int) -> str:
    sku = str(row.get("SKU", "")).strip()
    date = str(row.get("Order Date", "")).strip().replace("/", "")
    return f"{sku}-{date}-row{idx}"


def _load_sheet_df(ws) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def main() -> None:
    if not ORDERS_PATH.exists():
        raise SystemExit("missing out/orders_sheet_orders.csv")

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    orders = pd.read_csv(ORDERS_PATH, dtype=str).fillna("")
    required = ["SKU", "Cost PU", "Order Date", "Sent to FBA"]
    for col in required:
        if col not in orders.columns:
            raise SystemExit(f"orders_sheet_orders.csv missing {col}")

    # Bottom-to-top (newest first).
    orders = orders.reset_index(drop=True)
    orders_rev = orders.iloc[::-1].copy()

    tokens: List[Dict[str, str]] = []
    seen_lots = set()

    for idx, row in orders_rev.iterrows():
        sku = str(row.get("SKU", "")).strip()
        if not sku:
            continue
        qty = _num(row.get("Sent to FBA", ""))
        if qty <= 0:
            continue
        cost = _parse_cost(row.get("Cost PU", ""))
        if cost <= 0:
            continue
        lot_id = _lot_id(row, idx)
        if lot_id in seen_lots:
            raise RuntimeError(f"Duplicate lot_id detected: {lot_id}")
        seen_lots.add(lot_id)
        received_date = str(row.get("Order Date", "")).strip()
        for seq in range(1, qty + 1):
            tokens.append(
                {
                    "token_id": f"{lot_id}-{seq:04d}",
                    "seller_sku": sku,
                    "asin": "",
                    "lot_id": lot_id,
                    "purchase_order_id": "",
                    "order_confirmation_id": "",
                    "invoice_id": "",
                    "shipment_id": "",
                    "cost_per_unit": f"{cost:.2f}",
                    "currency": "GBP",
                    "status": "available",
                    "received_date": received_date,
                    "allocated_order_id": "",
                    "allocated_date": "",
                    "return_order_id": "",
                    "return_date": "",
                    "notes": "full_rebuild_sent_to_fba",
                    "return_event_id": "",
                    "last_return_order_id": "",
                    "last_return_date": "",
                    "last_return_event_id": "",
                    "disposed_event_id": "",
                    "disposed_date": "",
                    "disposed_reason": "",
                    "source": "orders_sheet_rebuild",
                    "source_batch_id": lot_id,
                    "created_at": "",
                    "lot_rank": str(idx),
                    "lot_rank_num": str(idx),
                    "sort_rank": str(idx),
                }
            )

    if not tokens:
        raise SystemExit("No tokens built from orders sheet")

    token_df = pd.DataFrame(tokens)
    TOKEN_LEDGER_OUT.parent.mkdir(parents=True, exist_ok=True)
    token_df.to_csv(TOKEN_LEDGER_OUT, index=False)

    # Clear allocations locally
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

    # Push to sheets
    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    token_ws = sheet.worksheet(TOKENS_TAB)
    alloc_ws = sheet.worksheet(ALLOC_TAB)

    rows_out = [token_df.columns.tolist()] + token_df.astype(object).where(pd.notnull(token_df), "").values.tolist()
    token_ws.clear()
    token_ws.update(rows_out, value_input_option="RAW")

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

    print({"status": "success", "tokens": len(token_df), "lots": len(seen_lots)})


if __name__ == "__main__":
    main()
