import argparse
import os
import sys
from datetime import datetime

import pandas as pd
import gspread


TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKENS_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"


def parse_date(value: str) -> datetime | None:
    if not value or pd.isna(value):
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def normalize_token_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    if "status" not in df:
        df["status"] = ""
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", required=True)
    parser.add_argument("--from-date", default=None)
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    token_ws = sheet.worksheet(TOKENS_TAB)
    alloc_ws = sheet.worksheet(ALLOC_TAB)

    token_df = normalize_token_df(load_sheet_df(token_ws))
    alloc_df = load_sheet_df(alloc_ws)

    if token_df.empty:
        raise RuntimeError("Token_Ledger is empty.")

    token_df["received_date_dt"] = token_df["received_date"].apply(parse_date)
    token_df["token_seq"] = range(len(token_df))

    token_df["status"] = token_df["status"].fillna("")
    available_tokens = token_df[
        (token_df["seller_sku"] == args.sku) & (token_df["status"] == "available")
    ].sort_values(by=["received_date_dt", "token_seq", "token_id"])

    if available_tokens.empty:
        raise RuntimeError("No available tokens to allocate for this SKU.")

    alloc_map = {}
    if not alloc_df.empty:
        alloc_df = alloc_df[alloc_df["seller_sku"] == args.sku]
        for _, row in alloc_df.iterrows():
            key = (row.get("order_id", ""), row.get("seller_sku", ""))
            alloc_map[key] = alloc_map.get(key, 0) + 1

    order_df = pd.read_csv("out/order_master.csv")
    order_df = order_df[order_df["SKU"] == args.sku]
    order_df = order_df[order_df["Quantity Ordered"] > 0]
    if args.from_date:
        order_df = order_df[order_df["Date"] >= args.from_date]
    order_df = order_df.sort_values(by=["Date", "Order ID"])

    token_iter = iter(available_tokens.itertuples(index=False))
    new_allocations = []
    updated_tokens = token_df.copy()

    for _, row in order_df.iterrows():
        order_id = row["Order ID"]
        order_date = row["Date"]
        qty = int(row["Quantity Ordered"])
        allocated = alloc_map.get((order_id, args.sku), 0)
        remaining = qty - allocated
        if remaining <= 0:
            continue
        for _ in range(remaining):
            try:
                token = next(token_iter)
            except StopIteration:
                raise RuntimeError("Ran out of available tokens before covering orders.")

            new_allocations.append(
                {
                    "order_id": order_id,
                    "order_date": order_date,
                    "seller_sku": args.sku,
                    "quantity": 1,
                    "token_id": token.token_id,
                    "token_cost": token.cost_per_unit,
                    "currency": token.currency,
                    "allocation_date": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "source_level": str(row.get("lvl", "")),
                    "notes": "backfill_fifo",
                }
            )

            idx = updated_tokens.index[updated_tokens["token_id"] == token.token_id]
            updated_tokens.loc[idx, "status"] = "allocated"
            updated_tokens.loc[idx, "allocated_order_id"] = order_id
            updated_tokens.loc[idx, "allocated_date"] = order_date

    if not new_allocations:
        print("No new allocations needed.")
        return

    new_alloc_df = pd.DataFrame(new_allocations)
    new_alloc_df.to_csv("out/token_allocations_backfill.csv", index=False)
    updated_tokens.drop(columns=["received_date_dt", "token_seq"], errors="ignore").to_csv(
        "out/token_ledger_updated.csv", index=False
    )

    # Append allocations
    alloc_ws.append_rows(new_alloc_df.values.tolist(), value_input_option="RAW")

    # Replace token ledger with updated status
    token_out = updated_tokens.drop(columns=["received_date_dt", "token_seq"], errors="ignore")
    rows = [token_out.columns.tolist()] + token_out.astype(object).where(pd.notnull(token_out), "").values.tolist()
    token_ws.clear()
    token_ws.update(rows, value_input_option="RAW")

    print(f"Allocated {len(new_alloc_df)} units for {args.sku}.")


if __name__ == "__main__":
    main()
