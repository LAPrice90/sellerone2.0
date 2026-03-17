import argparse
import os
import re
import sys

import pandas as pd
import gspread


ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"
TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ORDERS_TAB = "Orders"
TOKENS_TAB = "Token_Ledger"


def parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", value.replace(",", ""))
    return float(match.group()) if match else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", required=True)
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    client = get_gspread_client()
    orders_ws = client.open_by_key(ORDERS_SHEET_ID).worksheet(ORDERS_TAB)
    token_ws = client.open_by_key(TOKENS_SHEET_ID).worksheet(TOKENS_TAB)

    orders_rows = orders_ws.get_all_values()
    header = orders_rows[0]
    rows = orders_rows[1:]

    # Build lot_id -> cost mapping for the SKU.
    lot_cost = {}
    for row in rows:
        if len(row) < 10:
            continue
        if row[2].strip() != args.sku:
            continue
        lot_id = row[1].strip()
        if not lot_id:
            continue
        cost = parse_cost(row[7])
        if cost > 0:
            lot_cost[lot_id] = cost

    if not lot_cost:
        raise RuntimeError("No lot cost found for this SKU in Orders sheet.")

    token_values = token_ws.get_all_values()
    if not token_values:
        raise RuntimeError("Token_Ledger is empty.")

    token_header, token_rows = token_values[0], token_values[1:]
    token_df = pd.DataFrame(token_rows, columns=token_header)
    token_df["cost_per_unit"] = token_df["cost_per_unit"].replace("", "0").astype(float)

    # Update costs where missing/zero.
    updated = 0
    for idx, row in token_df.iterrows():
        if row["seller_sku"] != args.sku:
            continue
        if row["cost_per_unit"] > 0:
            continue
        lot_id = row["lot_id"]
        if lot_id in lot_cost:
            token_df.at[idx, "cost_per_unit"] = round(lot_cost[lot_id], 2)
            updated += 1

    if updated == 0:
        print("No token costs updated.")
        return

    out_path = "out/token_ledger_costs_updated.csv"
    token_df.to_csv(out_path, index=False)

    rows_out = [token_df.columns.tolist()] + token_df.astype(object).where(pd.notnull(token_df), "").values.tolist()
    token_ws.clear()
    token_ws.update(rows_out, value_input_option="RAW")
    print(f"Updated {updated} tokens. Saved {out_path}.")


if __name__ == "__main__":
    main()

