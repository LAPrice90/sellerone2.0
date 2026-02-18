import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import gspread


ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"
TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ORDERS_TAB = "Orders"
TOKENS_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"


def parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", value.replace(",", ""))
    return float(match.group()) if match else 0.0


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", required=True)
    parser.add_argument("--target-units", type=int, default=None)
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    client = get_gspread_client()
    orders_ws = client.open_by_key(ORDERS_SHEET_ID).worksheet(ORDERS_TAB)
    token_ws = client.open_by_key(TOKENS_SHEET_ID).worksheet(TOKENS_TAB)
    alloc_ws = client.open_by_key(TOKENS_SHEET_ID).worksheet(ALLOC_TAB)
    recon_path = Path("out/token_stock_recon.csv")

    orders_rows = orders_ws.get_all_values()
    rows = orders_rows[1:]

    batches = []
    for row_num, row in enumerate(rows, start=2):
        if len(row) < 10 or row[2].strip() != args.sku:
            continue
        ordered = int(float(row[9] or 0))
        if ordered <= 0:
            continue
        lot_id = row[1].strip()
        if not lot_id:
            order_date = parse_date(row[8])
            date_str = order_date.date().isoformat() if order_date else f"row{row_num}"
            lot_id = f"{args.sku}-{date_str}-row{row_num}"
        delivered = int(float(row[10] or 0))
        sent_to_fba = int(float(row[11] or 0))
        batches.append(
            {
                "lot_id": lot_id,
                "order_date": parse_date(row[8]),
                "ordered": ordered,
                "delivered": delivered,
                "sent_to_fba": sent_to_fba,
                "cost": parse_cost(row[7]),
                "asin": row[4].strip(),
            }
        )

    if not batches:
        raise RuntimeError("No purchase batches found for that SKU.")

    batches.sort(key=lambda x: (x["order_date"] or datetime.min))

    # Status split is observational; token counts come only from purchases.
    target_units = None
    available_count = 0
    warehouse_count = 0
    unsellable_count = 0
    if recon_path.exists():
        recon = pd.read_csv(recon_path, dtype=str).fillna("")
        recon_row = recon[recon["seller_sku"] == args.sku]
        if not recon_row.empty:
            def _to_int(val) -> int:
                try:
                    return int(float(val))
                except Exception:
                    return 0
            inv_available = _to_int(recon_row.iloc[0].get("inventory_available", 0))
            inv_total = _to_int(recon_row.iloc[0].get("inventory_total", 0))
            inv_unsellable = _to_int(recon_row.iloc[0].get("inventory_unsellable", 0))
            net_sold = _to_int(recon_row.iloc[0].get("net_sold_qty", 0))
            available_count = inv_available + net_sold
            warehouse_count = max(inv_total - inv_available, 0)
            unsellable_count = inv_unsellable

    tokens = []
    ordered_total = sum(int(b["ordered"]) for b in batches)
    target_units = ordered_total
    if args.target_units is not None and args.target_units != ordered_total:
        raise RuntimeError(
            f"Requested target_units={args.target_units} but purchases_total={ordered_total}."
        )
    remaining = target_units
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch["ordered"], remaining)

        for i in range(1, take + 1):
            token_id = f"{batch['lot_id']}-{i:04d}"
            status = "available"
            tokens.append(
                {
                    "token_id": token_id,
                    "seller_sku": args.sku,
                    "asin": batch["asin"],
                    "lot_id": batch["lot_id"],
                    "purchase_order_id": "",
                    "order_confirmation_id": "",
                    "invoice_id": "",
                    "shipment_id": "",
                    "cost_per_unit": round(batch["cost"], 2),
                    "currency": "GBP",
                    "status": status,
                    "received_date": batch["order_date"].date().isoformat() if batch["order_date"] else "",
                    "allocated_order_id": "",
                    "allocated_date": "",
                    "return_order_id": "",
                    "return_date": "",
                    "notes": "rebuild_target",
                }
            )
        remaining -= take

    # Apply status split (available includes net_sold to allow allocation).
    total = len(tokens)
    desired_total = target_units
    if desired_total != total:
        raise RuntimeError("Token build count mismatch.")
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
            tokens[idx]["status"] = status
            idx += 1

    # Replace Token_Ledger rows for this SKU
    token_values = token_ws.get_all_values()
    header = token_values[0] if token_values else []
    existing = token_values[1:] if token_values else []
    kept = [r for r in existing if len(r) > 1 and r[1] != args.sku]
    out_rows = [header] + kept + [list(t.values()) for t in tokens]
    token_ws.clear()
    token_ws.update(out_rows, value_input_option="RAW")

    # Remove existing allocations for this SKU
    alloc_values = alloc_ws.get_all_values()
    a_header = alloc_values[0] if alloc_values else []
    a_rows = alloc_values[1:] if alloc_values else []
    a_kept = [r for r in a_rows if len(r) > 2 and r[2] != args.sku]
    alloc_ws.clear()
    alloc_ws.update([a_header] + a_kept, value_input_option="RAW")

    pd.DataFrame(tokens).to_csv("out/token_ledger_rebuild.csv", index=False)
    print(f"Rebuilt {len(tokens)} tokens for {args.sku}.")


if __name__ == "__main__":
    main()
