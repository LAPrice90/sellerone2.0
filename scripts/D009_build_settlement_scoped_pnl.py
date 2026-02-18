"""
Build a settlement-scoped P&L view by combining:
- Orders API item-level revenue/tax/shipping for settlement order-item IDs
- Finances API category ledger for fees/reimbursements

Outputs:
- out/settlement_scoped_pnl.csv
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


SETTLEMENT_PATH = Path(os.environ.get("SETTLEMENT_STATEMENT_PATH", "reference/549081020474.txt"))
ITEM_MATCHES = Path("out/settlement_order_item_matches.csv")
ORDER_ITEMS = Path("out/order_items_all.csv")
TXN_CATEGORY = Path("out/transaction_category_ledger.csv")
OUT_PNL = Path("out/settlement_scoped_pnl.csv")


def _to_float(val) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def main() -> None:
    if not SETTLEMENT_PATH.exists() or not ITEM_MATCHES.exists() or not ORDER_ITEMS.exists():
        print({"status": "skip", "reason": "missing_inputs"})
        return

    settlement = pd.read_csv(SETTLEMENT_PATH, sep="\t", dtype=str).fillna("")
    matches = pd.read_csv(ITEM_MATCHES, dtype=str).fillna("")
    items = pd.read_csv(ORDER_ITEMS, dtype=str).fillna("")

    start_ts = ""
    end_ts = ""
    if "settlement-start-date" in settlement.columns:
        start_ts = next((s for s in settlement["settlement-start-date"].tolist() if s), "")
    if "settlement-end-date" in settlement.columns:
        end_ts = next((s for s in settlement["settlement-end-date"].tolist() if s), "")

    item_ids = set(matches["order_item_id"].tolist())
    items["order_item_id"] = items.get("order_item_id", "")
    items_scope = items[items["order_item_id"].isin(item_ids)].copy()

    def amt(col: str) -> float:
        return float(pd.to_numeric(items_scope.get(col, 0.0), errors="coerce").fillna(0.0).sum())

    pnl_rows = {
        "Price_Total": amt("item_price_amount"),
        "Price_VAT": amt("item_tax_amount"),
        "Shipping_Total": amt("shipping_price_amount"),
        "Shipping_VAT": amt("shipping_tax_amount"),
        "Gift_Total": amt("giftwrap_price_amount"),
        "Gift_VAT": amt("giftwrap_tax_amount"),
        "Promotion_Total": -amt("promotion_discount_amount"),
    }

    if TXN_CATEGORY.exists():
        tx = pd.read_csv(TXN_CATEGORY, dtype=str).fillna("")
        tx["amount_value"] = pd.to_numeric(tx.get("amount_value"), errors="coerce").fillna(0.0)
        if start_ts and end_ts:
            tx["posted_date"] = pd.to_datetime(tx["posted_date"], errors="coerce", utc=True)
            start_dt = pd.to_datetime(start_ts, utc=True, dayfirst=True)
            end_dt = pd.to_datetime(end_ts, utc=True, dayfirst=True)
            tx = tx[(tx["posted_date"] >= start_dt) & (tx["posted_date"] <= end_dt)]

        cat_map = {
            "Inbound_Transportation_Fee": "Inbound_Transportation_Fee",
            "Removal_Fee": "Removal_Fee",
            "Warehouse_Lost_Reimbursement": "Warehouse_Lost_Reimbursement",
            "Reversal_Reimbursement": "Reversal_Reimbursement",
            "Inventory_Reimbursement": "Inventory_Reimbursement",
            "Compensated_Clawback": "Compensated_Clawback",
            "Refund_Sales": "Refund_Sales_Total",
            "Refund_Expenses": "Refund_Expenses_Total",
            "Refund_Commission": "Refund_Commission",
            "Shipping_Chargeback": "Shipping_Chargeback",
            "Retrocharge": "Retrocharge_Total",
            "Refund_Retrocharge": "Retrocharge_Total",
        }
        for cat, pnl_key in cat_map.items():
            pnl_rows[pnl_key] = float(tx[tx["category"] == cat]["amount_value"].sum())

        # Include shipment expenses as a single line (non-itemized fee bucket).
        pnl_rows["Shipment_Expenses_Total"] = float(tx[tx["category"] == "Shipment_Expenses"]["amount_value"].sum())

    out = pd.DataFrame(
        [{"Parameter/Date": k, "Total": round(v, 2), "window_start": start_ts, "window_end": end_ts} for k, v in pnl_rows.items()]
    )
    OUT_PNL.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PNL, index=False)
    print({"status": "success", "rows": len(out), "out": str(OUT_PNL)})


if __name__ == "__main__":
    main()
