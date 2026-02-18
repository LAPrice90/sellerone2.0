"""
Build November-anchored, demand-bounded tokens from CSVs only.

Rule summary:
- Demand = net shipped units since cutoff (orders since cutoff minus refunds).
- Stock = current sellable available only.
- Tokens are created newest purchases first, up to target = demand + stock.
- Stock tokens use Sent to FBA capacity; order tokens use Ordered capacity.
- Orders are allocated newest first.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

import pandas as pd


OUT_DIR = Path("out")

PURCHASES_CSV = OUT_DIR / "orders_sheet_orders.csv"
ORDERS_CSV = OUT_DIR / "order_master.csv"
INVENTORY_CSV = OUT_DIR / "inventory_summaries.csv"
REFUNDS_CSV = OUT_DIR / "financial_events_refunds_official.csv"

TOKEN_LEDGER_OUT = OUT_DIR / "token_ledger_live.csv"
ALLOC_OUT = OUT_DIR / "token_allocations_live.csv"
SUMMARY_OUT = OUT_DIR / "token_november_build_summary.csv"
PURCHASE_USAGE_OUT = OUT_DIR / "token_november_purchase_usage.csv"
ORDER_GAPS_OUT = OUT_DIR / "token_november_order_shortfalls.csv"

CUTOFF_DATE = "2025-11-01"


def parse_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def parse_cost(value) -> float:
    if value is None:
        return 0.0
    txt = str(value)
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", txt.replace(",", ""))
    return float(match.group()) if match else 0.0


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def load_purchases() -> pd.DataFrame:
    if not PURCHASES_CSV.exists():
        raise RuntimeError("Missing out/orders_sheet_orders.csv")
    df = pd.read_csv(PURCHASES_CSV, dtype=str).fillna("")
    df["_row_idx"] = df.index.astype(int)
    # Normalize columns by expected names.
    cols = {c.strip(): c for c in df.columns}
    def _col(name: str, fallback_idx: int) -> str:
        if name in cols:
            return cols[name]
        return df.columns[fallback_idx] if fallback_idx < len(df.columns) else name

    sku_col = _col("SKU", 2)
    asin_col = _col("Asin", 4)
    cost_col = _col("Cost PU", 7)
    date_col = _col("Order Date", 8)
    ordered_col = _col("Ordered", 9)
    sent_col = _col("Sent to FBA", 11)

    out = df[[sku_col, asin_col, cost_col, date_col, ordered_col, sent_col, "_row_idx"]].copy()
    out.columns = ["sku", "asin", "cost", "order_date", "ordered", "sent_to_fba", "row_idx"]
    out["ordered"] = out["ordered"].apply(parse_int)
    out["sent_to_fba"] = out["sent_to_fba"].apply(parse_int)
    out["cost"] = out["cost"].apply(parse_cost)
    out["order_date_dt"] = out["order_date"].apply(parse_date)
    out = out[out["sku"].astype(str).str.strip() != ""]
    out = out[out["ordered"] > 0]
    return out.reset_index(drop=True)


def load_orders() -> pd.DataFrame:
    if not ORDERS_CSV.exists():
        raise RuntimeError("Missing out/order_master.csv")
    df = pd.read_csv(ORDERS_CSV, dtype=str).fillna("")
    df["Quantity Ordered"] = df["Quantity Ordered"].apply(parse_int)
    df = df[df["Quantity Ordered"] > 0].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True)
    cutoff = pd.to_datetime(CUTOFF_DATE, utc=True)
    df = df[df["Date"] >= cutoff]
    return df


def load_refunds() -> pd.DataFrame:
    if not REFUNDS_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(REFUNDS_CSV, dtype=str).fillna("")
    if df.empty:
        return df
    df["Quantity Ordered"] = df["Quantity Ordered"].apply(parse_int)
    df = df[df["Quantity Ordered"] > 0]
    return df


def load_inventory() -> pd.DataFrame:
    if not INVENTORY_CSV.exists():
        raise RuntimeError("Missing out/inventory_summaries.csv")
    df = pd.read_csv(INVENTORY_CSV, dtype=str).fillna("")
    if "available" not in df.columns:
        raise RuntimeError("inventory_summaries.csv missing 'available'")
    # Treat inbound + FC processing/transfer as stock for token coverage.
    for col in [
        "available",
        "inbound_working",
        "inbound_shipped",
        "inbound_receiving",
        "reserved_processing",
        "reserved_transfers",
    ]:
        if col in df.columns:
            df[col] = df[col].apply(parse_int)
    return df


def main() -> None:
    purchases = load_purchases()
    orders = load_orders()
    refunds = load_refunds()
    inventory = load_inventory()

    if purchases.empty:
        raise RuntimeError("No purchase rows found in orders_sheet_orders.csv")

    # Refunds map for orders since cutoff only
    refund_map = {}
    if not refunds.empty:
        refunds = refunds.rename(
            columns={
                "Order ID": "order_id",
                "SKU": "sku",
                "Quantity Ordered": "qty",
            }
        )
        refunds["qty"] = refunds["qty"].apply(parse_int)
        refunds = refunds[refunds["qty"] > 0]
        for _, r in refunds.iterrows():
            key = (str(r.get("order_id", "")).strip(), str(r.get("sku", "")).strip())
            if not key[0] or not key[1]:
                continue
            refund_map[key] = refund_map.get(key, 0) + int(r["qty"])

    # Orders per SKU, newest first
    orders = orders.rename(
        columns={
            "Order ID": "order_id",
            "SKU": "sku",
            "Quantity Ordered": "qty",
        }
    )
    orders["qty"] = orders["qty"].apply(parse_int)
    orders = orders[orders["qty"] > 0]
    orders = orders.sort_values(by=["Date", "order_id"], ascending=[False, False])

    # Net demand per order (order qty - refunds)
    orders["refund_qty"] = orders.apply(
        lambda r: refund_map.get((str(r["order_id"]).strip(), str(r["sku"]).strip()), 0),
        axis=1,
    )
    orders["net_qty"] = (orders["qty"] - orders["refund_qty"]).clip(lower=0)
    orders = orders[orders["net_qty"] > 0]

    net_demand_by_sku = orders.groupby("sku")["net_qty"].sum().to_dict()
    stock_cols = [
        "available",
        "inbound_working",
        "inbound_shipped",
        "inbound_receiving",
        "reserved_processing",
        "reserved_transfers",
    ]
    available_cols = [c for c in stock_cols if c in inventory.columns]
    if not available_cols:
        raise RuntimeError("inventory_summaries.csv missing stock columns")
    inventory["stock_needed"] = inventory[available_cols].sum(axis=1)
    stock_by_sku = inventory.set_index("seller_sku")["stock_needed"].to_dict()

    tokens = []
    allocations = []
    summary_rows = []
    purchase_usage_rows = []
    shortfall_rows = []

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    # Build tokens per SKU
    for sku in sorted(set(list(net_demand_by_sku.keys()) + list(stock_by_sku.keys()))):
        net_demand = int(net_demand_by_sku.get(sku, 0))
        stock_needed = int(stock_by_sku.get(sku, 0))
        target = net_demand + stock_needed
        if target <= 0:
            continue

        sku_purchases = purchases[purchases["sku"] == sku].copy()
        if sku_purchases.empty:
            summary_rows.append(
                {
                    "seller_sku": sku,
                    "net_demand": net_demand,
                    "stock_needed": stock_needed,
                    "target_tokens": target,
                    "tokens_created": 0,
                    "orders_allocated": 0,
                    "stock_shortfall": stock_needed,
                    "order_shortfall": net_demand,
                    "status": "skip_no_purchases",
                    "updated_at": now_iso,
                }
            )
            continue

        # Use sheet row order (bottom-up) to pick newest purchase batches first.
        sku_purchases = sku_purchases.sort_values(by=["row_idx"], ascending=[False])

        created = 0
        stock_remaining = stock_needed
        demand_remaining = net_demand
        order_token_pool = []

        for _, row in sku_purchases.iterrows():
            if stock_remaining + demand_remaining <= 0:
                break
            ordered = int(row["ordered"])
            sent = int(row["sent_to_fba"])
            if ordered <= 0:
                continue

            batch_remaining = ordered
            sent_remaining = max(min(sent, ordered), 0)
            order_date = row["order_date_dt"]
            row_idx = int(row["row_idx"])
            date_label = order_date.date().isoformat() if order_date else f"row{row_idx+1}"
            lot_id = f"{sku}-{date_label}-row{row_idx+1}"
            batch_cost = float(row["cost"])
            asin = row["asin"]

            stock_take = min(stock_remaining, sent_remaining, batch_remaining)
            for i in range(1, stock_take + 1):
                token_id = f"{lot_id}-{i:04d}"
                tokens.append(
                    {
                        "token_id": token_id,
                        "seller_sku": sku,
                        "asin": asin,
                        "lot_id": lot_id,
                        "purchase_order_id": "",
                        "order_confirmation_id": "",
                        "invoice_id": "",
                        "shipment_id": "",
                        "cost_per_unit": round(batch_cost, 2),
                        "currency": "GBP",
                        "status": "available",
                        "received_date": order_date.date().isoformat() if order_date else "",
                        "allocated_order_id": "",
                        "allocated_date": "",
                        "return_order_id": "",
                        "return_date": "",
                        "notes": "nov_anchor_stock",
                    }
                )
            stock_remaining -= stock_take
            batch_remaining -= stock_take

            demand_take = min(demand_remaining, batch_remaining)
            for j in range(1, demand_take + 1):
                token_id = f"{lot_id}-{stock_take + j:04d}"
                token = {
                    "token_id": token_id,
                    "seller_sku": sku,
                    "asin": asin,
                    "lot_id": lot_id,
                    "purchase_order_id": "",
                    "order_confirmation_id": "",
                    "invoice_id": "",
                    "shipment_id": "",
                    "cost_per_unit": round(batch_cost, 2),
                    "currency": "GBP",
                    "status": "available",
                    "received_date": order_date.date().isoformat() if order_date else "",
                    "allocated_order_id": "",
                    "allocated_date": "",
                    "return_order_id": "",
                    "return_date": "",
                    "notes": "nov_anchor_order",
                }
                tokens.append(token)
                order_token_pool.append(token)
            demand_remaining -= demand_take
            created += stock_take + demand_take

            purchase_usage_rows.append(
                {
                    "seller_sku": sku,
                    "lot_id": lot_id,
                    "order_date": order_date.date().isoformat() if order_date else "",
                    "ordered": ordered,
                    "sent_to_fba": sent,
                    "used_for_stock": stock_take,
                    "used_for_orders": demand_take,
                    "unused": ordered - stock_take - demand_take,
                    "cost_per_unit": round(batch_cost, 2),
                }
            )

        # Allocate newest orders with available order tokens
        sku_orders = orders[orders["sku"] == sku].copy()
        allocated_units = 0
        shortage = 0
        if not sku_orders.empty and order_token_pool:
            token_iter = iter(order_token_pool)
            for _, o in sku_orders.iterrows():
                order_id = o["order_id"]
                order_date = o["Date"]
                qty = int(o["net_qty"])
                for _ in range(qty):
                    token = next(token_iter, None)
                    if token is None:
                        shortage += 1
                        continue
                    allocations.append(
                        {
                            "order_id": order_id,
                            "order_date": order_date,
                            "seller_sku": sku,
                            "quantity": 1,
                            "token_id": token["token_id"],
                            "token_cost": token["cost_per_unit"],
                            "currency": token["currency"],
                            "allocation_date": now_iso,
                            "source_level": str(o.get("lvl", "")),
                            "notes": "nov_anchor_allocation",
                        }
                    )
                    token["status"] = "allocated"
                    token["allocated_order_id"] = order_id
                    token["allocated_date"] = order_date
                    allocated_units += 1

        if demand_remaining > 0:
            shortage += demand_remaining

        if shortage > 0:
            shortfall_rows.append(
                {
                    "seller_sku": sku,
                    "net_demand": net_demand,
                    "allocated_units": allocated_units,
                    "order_shortfall": shortage,
                }
            )

        summary_rows.append(
            {
                "seller_sku": sku,
                "net_demand": net_demand,
                "stock_needed": stock_needed,
                "target_tokens": target,
                "tokens_created": created,
                "orders_allocated": allocated_units,
                "stock_shortfall": max(stock_remaining, 0),
                "order_shortfall": max(shortage, 0),
                "status": "ok" if created == target else "partial",
                "updated_at": now_iso,
            }
        )

    if not tokens:
        raise RuntimeError("No tokens created.")

    token_df = pd.DataFrame(tokens)
    alloc_df = pd.DataFrame(allocations)
    summary_df = pd.DataFrame(summary_rows)
    usage_df = pd.DataFrame(purchase_usage_rows)
    shortfalls_df = pd.DataFrame(shortfall_rows)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    token_df.to_csv(TOKEN_LEDGER_OUT, index=False)
    alloc_df.to_csv(ALLOC_OUT, index=False)
    summary_df.to_csv(SUMMARY_OUT, index=False)
    usage_df.to_csv(PURCHASE_USAGE_OUT, index=False)
    shortfalls_df.to_csv(ORDER_GAPS_OUT, index=False)

    print(
        {
            "status": "success",
            "token_ledger": str(TOKEN_LEDGER_OUT),
            "allocations": str(ALLOC_OUT),
            "summary": str(SUMMARY_OUT),
            "purchase_usage": str(PURCHASE_USAGE_OUT),
            "order_shortfalls": str(ORDER_GAPS_OUT),
        }
    )


if __name__ == "__main__":
    main()
