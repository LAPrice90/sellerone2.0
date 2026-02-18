"""
Backfill tokens from the orders sheet using Sent to FBA quantities.

Rules:
- Use Sent to FBA as the quantity source.
- Process rows from bottom to top (latest rows first).
- Generate lot_id when missing.
- Append tokens to Token_Ledger sheet and update local token_ledger_live.csv.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


ORDERS_PATH = Path("out/orders_sheet_orders.csv")
TOKEN_LEDGER_OUT = Path("out/token_ledger_live.csv")
REPORT_OUT = Path("out/token_backfill_from_orders_sheet.csv")

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKENS_TAB = "Token_Ledger"


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    value = str(value).replace(",", "").replace("£", "").replace("Ł", "").strip()
    try:
        return float(value)
    except Exception:
        return 0.0


def _load_sheet_df(ws) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def _ensure_lot_id(row: pd.Series, idx: int) -> str:
    lot_id = str(row.get("Unnamed: 1", "")).strip()
    if lot_id:
        return lot_id
    sku = str(row.get("SKU", "")).strip()
    date = str(row.get("Order Date", "")).strip().replace("/", "")
    return f"{sku}-{date}-row{idx}"


def main() -> None:
    if not ORDERS_PATH.exists():
        raise SystemExit("missing out/orders_sheet_orders.csv")

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    orders = pd.read_csv(ORDERS_PATH, dtype=str).fillna("")
    if orders.empty:
        print({"status": "skip", "reason": "orders_sheet_empty"})
        return

    # Require base columns.
    for col in ["SKU", "Cost PU", "Order Date", "Sent to FBA"]:
        if col not in orders.columns:
            raise SystemExit(f"missing column {col} in orders_sheet_orders.csv")
    if "Unnamed: 1" not in orders.columns:
        orders["Unnamed: 1"] = ""

    # Process bottom-to-top (latest rows first).
    orders = orders.reset_index(drop=True)
    orders_rev = orders.iloc[::-1].copy()

    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    token_ws = sheet.worksheet(TOKENS_TAB)
    token_df = _load_sheet_df(token_ws)
    if token_df.empty:
        raise SystemExit("Token_Ledger sheet is empty")

    # Build existing token_id set + counts per lot_id.
    existing_ids = set(token_df.get("token_id", pd.Series()).astype(str).tolist())
    lot_counts: Dict[str, int] = {}
    if "lot_id" in token_df.columns:
        lot_counts = token_df["lot_id"].astype(str).value_counts().to_dict()

    new_rows: List[List[str]] = []
    report_rows: List[Dict[str, object]] = []

    for idx, row in orders_rev.iterrows():
        sku = str(row.get("SKU", "")).strip()
        if not sku:
            continue
        qty = int(_num(pd.Series([row.get("Sent to FBA", "")])).iloc[0])
        if qty <= 0:
            continue
        cost = _parse_cost(row.get("Cost PU", ""))
        if cost <= 0:
            continue

        lot_id = _ensure_lot_id(row, idx)
        existing = lot_counts.get(lot_id, 0)
        needed = qty - existing
        if needed <= 0:
            continue

        received_date = str(row.get("Order Date", "")).strip()
        # Append needed tokens for this lot.
        for seq in range(existing + 1, existing + needed + 1):
            token_id = f"{lot_id}-{seq:04d}"
            if token_id in existing_ids:
                continue
            token_row = {
                "token_id": token_id,
                "seller_sku": sku,
                "cost_per_unit": f"{cost:.2f}",
                "currency": "GBP",
                "status": "available",
                "received_date": received_date,
                "source": "orders_sheet_backfill",
                "source_batch_id": lot_id,
                "created_at": "",
                "allocated_order_id": "",
                "allocated_date": "",
                "lot_id": lot_id,
            }
            # Build row in sheet column order.
            new_rows.append([token_row.get(c, "") for c in token_df.columns])
            existing_ids.add(token_id)
        lot_counts[lot_id] = existing + needed
        report_rows.append(
            {
                "sku": sku,
                "lot_id": lot_id,
                "sent_to_fba": qty,
                "existing_tokens": existing,
                "tokens_created": needed,
                "cost_per_unit": cost,
                "order_date": received_date,
            }
        )

    if not new_rows:
        print({"status": "skip", "reason": "no_tokens_needed"})
        return

    # Append rows to sheet and update local ledger.
    token_ws.append_rows(new_rows, value_input_option="RAW")

    token_df = pd.concat([token_df, pd.DataFrame(new_rows, columns=token_df.columns)], ignore_index=True)
    TOKEN_LEDGER_OUT.parent.mkdir(parents=True, exist_ok=True)
    token_df.to_csv(TOKEN_LEDGER_OUT, index=False)

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report_rows).to_csv(REPORT_OUT, index=False)

    print(
        {
            "status": "success",
            "rows_added": len(new_rows),
            "lots_updated": len(report_rows),
            "ledger": str(TOKEN_LEDGER_OUT),
            "report": str(REPORT_OUT),
        }
    )


if __name__ == "__main__":
    main()
