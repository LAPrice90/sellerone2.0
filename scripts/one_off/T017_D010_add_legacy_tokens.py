import argparse
import os
import sys
from datetime import datetime, UTC

import pandas as pd
import gspread

from scripts.core.storage import read_dataframe_with_sql_fallback


TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKENS_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"


def main() -> None:
    raise RuntimeError("Legacy token seeding disabled: tokens must be created only from purchases.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", action="append", required=True)
    parser.add_argument("--cost", action="append", required=True)
    args = parser.parse_args()

    if len(args.sku) != len(args.cost):
        raise RuntimeError("Provide equal counts of --sku and --cost.")

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.flows.A.A003_run_inventory_to_sheet import get_gspread_client

    if not os.path.exists("out/order_master.csv"):
        raise RuntimeError("Missing out/order_master.csv")
    order_master = pd.read_csv("out/order_master.csv")
    order_master = order_master[order_master["Quantity Ordered"] > 0]
    try:
        inventory = read_dataframe_with_sql_fallback(
            "out/inventory_summaries.csv",
            "a_inventory_summaries",
            dtype=str,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Missing out/inventory_summaries.csv") from exc

    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    token_ws = sheet.worksheet(TOKENS_TAB)
    alloc_ws = sheet.worksheet(ALLOC_TAB)

    token_rows = token_ws.get_all_values()
    token_header, token_data = token_rows[0], token_rows[1:]
    token_df = pd.DataFrame(token_data, columns=token_header)

    alloc_rows = alloc_ws.get_all_values()
    alloc_header, alloc_data = alloc_rows[0], alloc_rows[1:]
    alloc_df = pd.DataFrame(alloc_data, columns=alloc_header)

    now_iso = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    for sku, cost_str in zip(args.sku, args.cost):
        cost = float(cost_str)

        sold_qty = int(order_master.loc[order_master["SKU"] == sku, "Quantity Ordered"].sum())
        inv_row = inventory[inventory["seller_sku"] == sku]
        if inv_row.empty:
            raise RuntimeError(f"Missing inventory row for {sku}")
        inv_row = inv_row.iloc[0]
        available = int(inv_row.get("available", 0) or 0)
        inbound_shipped = int(inv_row.get("inbound_shipped", 0) or 0)
        inbound_receiving = int(inv_row.get("inbound_receiving", 0) or 0)
        available_total = available + inbound_shipped + inbound_receiving

        target_total = sold_qty + available_total

        existing_tokens = token_df[token_df["seller_sku"] == sku]
        if not existing_tokens.empty:
            continue  # already covered

        tokens = []
        for i in range(1, target_total + 1):
            token_id = f"LEGACY-{sku}-{i:04d}"
            status = "available" if i <= available_total else "allocated"
            tokens.append(
                {
                    "token_id": token_id,
                    "seller_sku": sku,
                    "asin": "",
                    "lot_id": f"LEGACY-{sku}",
                    "purchase_order_id": "",
                    "order_confirmation_id": "",
                    "invoice_id": "",
                    "shipment_id": "",
                    "cost_per_unit": round(cost, 2),
                    "currency": "GBP",
                    "status": status,
                    "received_date": "",
                    "allocated_order_id": "",
                    "allocated_date": "",
                    "return_order_id": "",
                    "return_date": "",
                    "notes": "legacy_placeholder",
                }
            )

        # allocate sold qty to earliest order IDs for traceability
        order_subset = order_master[order_master["SKU"] == sku].sort_values(by=["Date", "Order ID"])
        allocs = []
        token_iter = iter(tokens)
        for _, row in order_subset.iterrows():
            order_id = row["Order ID"]
            order_date = row["Date"]
            qty = int(row["Quantity Ordered"])
            for _ in range(qty):
                token = next(token_iter)
                token["status"] = "allocated"
                token["allocated_order_id"] = order_id
                token["allocated_date"] = order_date
                allocs.append(
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
                        "notes": "legacy_placeholder",
                    }
                )

        token_df = pd.concat([token_df, pd.DataFrame(tokens)], ignore_index=True)
        alloc_df = pd.concat([alloc_df, pd.DataFrame(allocs)], ignore_index=True)

    # write back
    token_rows_out = [token_df.columns.tolist()] + token_df.astype(object).where(pd.notnull(token_df), "").values.tolist()
    token_ws.clear()
    token_ws.update(token_rows_out, value_input_option="RAW")

    alloc_rows_out = [alloc_df.columns.tolist()] + alloc_df.astype(object).where(pd.notnull(alloc_df), "").values.tolist()
    alloc_ws.clear()
    alloc_ws.update(alloc_rows_out, value_input_option="RAW")

    print("Legacy tokens added.")


if __name__ == "__main__":
    main()

