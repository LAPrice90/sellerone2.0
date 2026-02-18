"""
Build a settlement-scoped order totals report for reconciliation.

Inputs:
- reference/549081020474.txt (settlement statement)
- out/order_ledger_fx.csv

Outputs:
- out/settlement_order_scope_totals.csv
- out/settlement_order_scope_missing_orders.csv
- out/settlement_vs_order_scope_delta.csv
- out/settlement_order_item_scope_totals.csv
- out/settlement_vs_item_scope_delta.csv
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


SETTLEMENT_PATH = Path(os.environ.get("SETTLEMENT_STATEMENT_PATH", "reference/549081020474.txt"))
ORDER_LEDGER = Path("out/order_ledger_fx.csv")

OUT_TOTALS = Path("out/settlement_order_scope_totals.csv")
OUT_MISSING = Path("out/settlement_order_scope_missing_orders.csv")
OUT_DELTA = Path("out/settlement_vs_order_scope_delta.csv")
OUT_ITEM_TOTALS = Path("out/settlement_order_item_scope_totals.csv")
OUT_ITEM_DELTA = Path("out/settlement_vs_item_scope_delta.csv")

ITEM_MATCHES = Path("out/settlement_order_item_matches.csv")

ORDER_CATEGORIES = {
    "Price_Total": "Price_Total_GBP",
    "Price_VAT": "Price_VAT_GBP",
    "Shipping_Total": "Shipping_Total_GBP",
    "Shipping_VAT": "Shipping_VAT_GBP",
    "Promotion_Total": "Promotion_Total_GBP",
    "FBA_Fee_Total": "FBA_Fee_Total_GBP",
    "Commission_Total": "Commission_Total_GBP",
    "Digital_Fee_Total": "Digital_Fee_Total_GBP",
}


def _to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def main() -> None:
    if not SETTLEMENT_PATH.exists():
        print({"status": "skip", "reason": "missing_settlement_statement", "path": str(SETTLEMENT_PATH)})
        return
    if not ORDER_LEDGER.exists():
        print({"status": "skip", "reason": "missing_order_ledger_fx", "path": str(ORDER_LEDGER)})
        return

    settlement = pd.read_csv(SETTLEMENT_PATH, sep="\t", dtype=str).fillna("")
    orders = pd.read_csv(ORDER_LEDGER, dtype=str).fillna("")

    start_ts = ""
    end_ts = ""
    if "settlement-start-date" in settlement.columns:
        start_ts = next((s for s in settlement["settlement-start-date"].tolist() if s), "")
    if "settlement-end-date" in settlement.columns:
        end_ts = next((s for s in settlement["settlement-end-date"].tolist() if s), "")

    order_ids = set()
    if "order-id" in settlement.columns:
        for oid in settlement["order-id"].tolist():
            if oid:
                order_ids.add(oid)

    orders["Date_dt"] = pd.to_datetime(orders["Date"], errors="coerce", utc=True)
    if start_ts and end_ts:
        start_dt = pd.to_datetime(start_ts, utc=True, dayfirst=True)
        end_dt = pd.to_datetime(end_ts, utc=True, dayfirst=True)
        orders = orders[(orders["Date_dt"] >= start_dt) & (orders["Date_dt"] <= end_dt)]

    scoped = orders[orders["Order ID"].isin(order_ids)].copy()

    totals = []
    for name, col in ORDER_CATEGORIES.items():
        if col in scoped.columns:
            total = float(_to_float(scoped[col]).sum())
        else:
            total = 0.0
        totals.append({"pnl_category": name, "order_scope_total": total, "column": col})

    OUT_TOTALS.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(totals).to_csv(OUT_TOTALS, index=False)

    missing_in_orders = sorted([oid for oid in order_ids if oid not in set(orders["Order ID"].tolist())])
    extra_in_orders = sorted([oid for oid in set(orders["Order ID"].tolist()) if oid and oid not in order_ids])
    pd.DataFrame(
        {
            "missing_in_order_ledger": missing_in_orders,
            "extra_in_order_ledger": extra_in_orders[: len(missing_in_orders)] + [""] * max(0, len(missing_in_orders) - len(extra_in_orders)),
        }
    ).to_csv(OUT_MISSING, index=False)

    # Build delta vs settlement fee summary if available
    settlement_fee_path = Path("out/settlement_fee_summary.csv")
    if settlement_fee_path.exists():
        settlement_fee = pd.read_csv(settlement_fee_path, dtype=str).fillna("")
        settlement_fee["amount"] = pd.to_numeric(settlement_fee.get("amount"), errors="coerce").fillna(0.0)
        settlement_sum = settlement_fee.groupby("pnl_category", dropna=False)["amount"].sum().reset_index()
        merged = pd.merge(
            settlement_sum,
            pd.DataFrame(totals),
            left_on="pnl_category",
            right_on="pnl_category",
            how="left",
        )
        merged["order_scope_total"] = pd.to_numeric(merged.get("order_scope_total"), errors="coerce").fillna(0.0)
        merged["delta"] = merged["order_scope_total"] - merged["amount"]
        merged["window_start"] = start_ts
        merged["window_end"] = end_ts
        merged.to_csv(OUT_DELTA, index=False)

    # Item-scoped totals using settlement item-code matches.
    if ITEM_MATCHES.exists():
        matches = pd.read_csv(ITEM_MATCHES, dtype=str).fillna("")
        matches = matches[matches["order_item_id"].astype(str) != ""]
        item_ids = set(matches["order_item_id"].tolist())
        items = pd.read_csv(Path("out/order_items_all.csv"), dtype=str).fillna("")
        orders = pd.read_csv(ORDER_LEDGER, dtype=str).fillna("")
        items["order_item_id"] = items.get("order_item_id") if "order_item_id" in items.columns else items.get("order-item-id", "")
        items["order_id"] = (
            items.get("amazon_order_id")
            if "amazon_order_id" in items.columns
            else (items.get("order_id") if "order_id" in items.columns else items.get("order-id", ""))
        )
        items_scope = items[items["order_item_id"].isin(item_ids)].copy()

        # Build per-order-item totals directly from order item amounts.
        rows = []
        for _, r in items_scope.iterrows():
            def amt(col):
                return float(pd.to_numeric(r.get(col, 0.0), errors="coerce") or 0.0)
            rows.append({"pnl_category": "Price_Total", "order_item_id": r.get("order_item_id"), "amount": amt("item_price_amount")})
            rows.append({"pnl_category": "Price_VAT", "order_item_id": r.get("order_item_id"), "amount": amt("item_tax_amount")})
            rows.append({"pnl_category": "Shipping_Total", "order_item_id": r.get("order_item_id"), "amount": amt("shipping_price_amount")})
            rows.append({"pnl_category": "Shipping_VAT", "order_item_id": r.get("order_item_id"), "amount": amt("shipping_tax_amount")})
            rows.append({"pnl_category": "Gift_Total", "order_item_id": r.get("order_item_id"), "amount": amt("giftwrap_price_amount")})
            rows.append({"pnl_category": "Gift_VAT", "order_item_id": r.get("order_item_id"), "amount": amt("giftwrap_tax_amount")})
            rows.append({"pnl_category": "Promotion_Total", "order_item_id": r.get("order_item_id"), "amount": -amt("promotion_discount_amount")})

        item_df = pd.DataFrame(rows)
        if not item_df.empty:
            item_totals = (
                item_df.groupby("pnl_category", dropna=False)["amount"]
                .sum()
                .reset_index()
                .rename(columns={"amount": "item_scope_total"})
            )
        else:
            item_totals = pd.DataFrame(columns=["pnl_category", "item_scope_total"])
        item_totals.to_csv(OUT_ITEM_TOTALS, index=False)

        if settlement_fee_path.exists():
            settlement_sum = settlement_fee.groupby("pnl_category", dropna=False)["amount"].sum().reset_index()
            merged_items = pd.merge(settlement_sum, item_totals, on="pnl_category", how="left")
            merged_items["item_scope_total"] = pd.to_numeric(merged_items.get("item_scope_total"), errors="coerce").fillna(0.0)
            merged_items["delta"] = merged_items["item_scope_total"] - merged_items["amount"]
            merged_items["window_start"] = start_ts
            merged_items["window_end"] = end_ts
            merged_items.to_csv(OUT_ITEM_DELTA, index=False)

    print(
        {
            "status": "success",
            "orders_total": len(orders),
            "orders_scoped": len(scoped),
            "settlement_orders": len(order_ids),
            "out_totals": str(OUT_TOTALS),
            "out_missing": str(OUT_MISSING),
            "out_delta": str(OUT_DELTA),
            "out_item_totals": str(OUT_ITEM_TOTALS),
            "out_item_delta": str(OUT_ITEM_DELTA),
        }
    )


if __name__ == "__main__":
    main()
