import argparse
import os
import re
import sys
from datetime import datetime, UTC
from pathlib import Path

import gspread
import pandas as pd


ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"
TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ORDERS_TAB = "Orders"
TOKENS_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"
ORDER_MASTER_PATH = Path("out/order_master.csv")
INVENTORY_PATH = Path("out/inventory_summaries.csv")
DEFAULT_START_DATE = os.environ.get("PNL_START_DATE", "2026-01-01")


def parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", value.replace(",", ""))
    return float(match.group()) if match else 0.0


def parse_sheet_date(value: str) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_order_date(value: str) -> datetime | None:
    if not value or pd.isna(value):
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-sku", default=None)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    if not ORDER_MASTER_PATH.exists():
        raise RuntimeError("Missing out/order_master.csv")
    if not INVENTORY_PATH.exists():
        raise RuntimeError("Missing out/inventory_summaries.csv")

    order_master = pd.read_csv(ORDER_MASTER_PATH)
    order_master = order_master[order_master["Quantity Ordered"] > 0]
    if args.start_date:
        order_master["Date"] = pd.to_datetime(order_master["Date"], errors="coerce", utc=True)
        start_dt = pd.to_datetime(args.start_date, errors="coerce", utc=True)
        if pd.notna(start_dt):
            order_master = order_master[order_master["Date"] >= start_dt]
        order_master["Date"] = order_master["Date"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.limit_sku:
        order_master = order_master[order_master["SKU"] == args.limit_sku]

    sold_by_sku = (
        order_master.groupby("SKU")["Quantity Ordered"].sum().astype(int).to_dict()
    )

    inventory = pd.read_csv(INVENTORY_PATH)
    inventory = inventory.set_index("seller_sku")
    available_by_sku = inventory["available"].fillna(0).astype(int).to_dict()
    inbound_shipped_by_sku = inventory["inbound_shipped"].fillna(0).astype(int).to_dict()
    inbound_receiving_by_sku = inventory["inbound_receiving"].fillna(0).astype(int).to_dict()
    unsellable_by_sku = inventory.get("unsellable", pd.Series(dtype=int)).fillna(0).astype(int).to_dict()

    client = get_gspread_client()
    orders_ws = client.open_by_key(ORDERS_SHEET_ID).worksheet(ORDERS_TAB)
    token_ws = client.open_by_key(TOKENS_SHEET_ID).worksheet(TOKENS_TAB)
    alloc_ws = client.open_by_key(TOKENS_SHEET_ID).worksheet(ALLOC_TAB)

    orders_rows = orders_ws.get_all_values()
    rows = orders_rows[1:]

    batches_by_sku: dict[str, list[dict]] = {}
    for row_num, row in enumerate(rows, start=2):
        if len(row) < 10:
            continue
        sku = row[2].strip()
        if not sku:
            continue
        if args.limit_sku and sku != args.limit_sku:
            continue
        ordered = int(float(row[9] or 0))
        if ordered <= 0:
            continue
        lot_id = row[1].strip()
        if not lot_id:
            order_date = parse_sheet_date(row[8])
            date_str = order_date.date().isoformat() if order_date else f"row{row_num}"
            lot_id = f"{sku}-{date_str}-row{row_num}"
        delivered = int(float(row[10] or 0))
        sent_to_fba = int(float(row[11] or 0))
        batch = {
            "lot_id": lot_id,
            "order_date": parse_sheet_date(row[8]),
            "ordered": ordered,
            "delivered": delivered,
            "sent_to_fba": sent_to_fba,
            "cost": parse_cost(row[7]),
            "asin": row[4].strip(),
        }
        batches_by_sku.setdefault(sku, []).append(batch)

    tokens = []
    allocations = []
    summary = []

    now_iso = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    order_master = order_master.sort_values(by=["Date", "Order ID"])

    for sku, batches in batches_by_sku.items():
        sold_qty = int(sold_by_sku.get(sku, 0))
        available_qty = int(available_by_sku.get(sku, 0))
        inbound_shipped = int(inbound_shipped_by_sku.get(sku, 0))
        inbound_receiving = int(inbound_receiving_by_sku.get(sku, 0))
        unsellable_qty = int(unsellable_by_sku.get(sku, 0))
        ordered_total = sum(int(b["ordered"]) for b in batches)
        target = ordered_total
        if target <= 0:
            continue

        batches.sort(key=lambda x: (x["order_date"] or datetime.min))

        sku_tokens = []
        remaining = target
        available_count = available_qty + sold_qty
        warehouse_count = inbound_shipped + inbound_receiving
        unsellable_count = unsellable_qty
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch["ordered"], remaining)
            for i in range(1, take + 1):
                token_id = f"{batch['lot_id']}-{i:04d}"
                status = "available"
                sku_tokens.append(
                    {
                        "token_id": token_id,
                        "seller_sku": sku,
                        "asin": batch["asin"],
                        "lot_id": batch["lot_id"],
                        "purchase_order_id": "",
                        "order_confirmation_id": "",
                        "invoice_id": "",
                        "shipment_id": "",
                        "cost_per_unit": round(batch["cost"], 2),
                        "currency": "GBP",
                        "status": status,
                        "received_date": batch["order_date"].date().isoformat()
                        if batch["order_date"]
                        else "",
                        "allocated_order_id": "",
                        "allocated_date": "",
                        "return_order_id": "",
                        "return_date": "",
                        "notes": "backdate_all",
                    }
                )
            remaining -= take

        # Apply status split after token creation.
        total = len(sku_tokens)
        status_limits = [
            ("available", max(available_count, 0)),
            ("warehouse", max(warehouse_count, 0)),
            ("unsellable", max(unsellable_count, 0)),
        ]
        idx = 0
        for status, count in status_limits:
            for _ in range(count):
                if idx >= total:
                    break
                sku_tokens[idx]["status"] = status
                idx += 1

        tokens.extend(sku_tokens)

        # Allocate sold units using available tokens only.
        sku_orders = order_master[order_master["SKU"] == sku]
        token_iter = (t for t in sku_tokens if t["status"] == "available")
        allocated_units = 0
        shortage = 0
        for _, row in sku_orders.iterrows():
            order_id = row["Order ID"]
            order_date = row["Date"]
            qty = int(row["Quantity Ordered"])
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
                        "source_level": str(row.get("lvl", "")),
                        "notes": "backdate_all",
                    }
                )
                token["status"] = "allocated"
                token["allocated_order_id"] = order_id
                token["allocated_date"] = order_date
                allocated_units += 1

        summary.append(
            {
                "sku": sku,
                "sold_qty": sold_qty,
                "available_qty": available_qty,
                "inbound_shipped": inbound_shipped,
                "inbound_receiving": inbound_receiving,
                "target_units": target,
                "tokens_created": len(sku_tokens),
                "allocated_units": allocated_units,
                "allocation_shortfall": shortage,
            }
        )

    if not tokens:
        raise RuntimeError("No tokens created.")

    token_df = pd.DataFrame(tokens)
    alloc_df = pd.DataFrame(allocations)
    summary_df = pd.DataFrame(summary).sort_values(by="sku")

    token_df.to_csv("out/token_ledger_backdate_all.csv", index=False)
    alloc_df.to_csv("out/token_allocations_backdate_all.csv", index=False)
    summary_df.to_csv("out/token_backdate_summary.csv", index=False)

    token_rows = [token_df.columns.tolist()] + token_df.astype(object).where(pd.notnull(token_df), "").values.tolist()
    token_ws.clear()
    token_ws.update(token_rows, value_input_option="RAW")

    if alloc_df.empty:
        alloc_rows = [alloc_df.columns.tolist()]
    else:
        alloc_rows = [alloc_df.columns.tolist()] + alloc_df.astype(object).where(pd.notnull(alloc_df), "").values.tolist()
    alloc_ws.clear()
    alloc_ws.update(alloc_rows, value_input_option="RAW")

    print(f"Backdated tokens for {len(summary_df)} SKUs. Summary saved to out/token_backdate_summary.csv")


if __name__ == "__main__":
    main()
