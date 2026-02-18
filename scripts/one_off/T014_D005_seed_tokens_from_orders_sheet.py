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
RECON_PATH = Path("out/token_stock_recon.csv")


def parse_int(value: str) -> int:
    if value is None:
        return 0
    value = value.strip()
    if not value:
        return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", value.replace(",", ""))
    return float(match.group()) if match else 0.0


def parse_date(value: str) -> str:
    if not value:
        return ""
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return value.strip()


def iter_order_rows(rows: list[list[str]], sku: str, lot_id: str | None) -> list[tuple[int, list[str]]]:
    matches = []
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) < 10:
            continue
        if row[2].strip() != sku:
            continue
        ordered = parse_int(row[9])
        if ordered <= 0:
            continue
        if lot_id and row[1].strip() != lot_id:
            continue
        matches.append((idx, row))
    return matches


def load_existing_token_ids(ws: gspread.Worksheet) -> set[str]:
    values = ws.get_all_values()
    if len(values) <= 1:
        return set()
    return {row[0] for row in values[1:] if row and row[0]}


def seed_tokens_from_row(row: list[str], sku: str, lot_id_override: str | None, row_num: int) -> dict:
    lot_id = lot_id_override or row[1].strip()
    if not lot_id:
        order_date = parse_date(row[8])
        lot_id = f"{sku}-{order_date}-row{row_num}"
    return {
        "lot_id": lot_id,
        "order_date": parse_date(row[8]),
        "ordered": parse_int(row[9]),
        "cost": parse_cost(row[7]),
        "asin": row[4].strip(),
    }


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts.A003_run_inventory_to_sheet import get_gspread_client

    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", required=True)
    parser.add_argument("--lot-id", default=None)
    parser.add_argument("--all-lots", action="store_true")
    args = parser.parse_args()

    client = get_gspread_client()
    orders_ws = client.open_by_key(ORDERS_SHEET_ID).worksheet(ORDERS_TAB)
    token_ws = client.open_by_key(TOKENS_SHEET_ID).worksheet(TOKENS_TAB)

    rows = orders_ws.get_all_values()
    matches = iter_order_rows(rows, args.sku, args.lot_id)
    if not matches:
        raise RuntimeError("No matching order batch found for that SKU/lot.")

    batches = []
    if args.all_lots:
        batches = [seed_tokens_from_row(r, args.sku, None, n) for n, r in matches]
    else:
        row_num, row = matches[-1]
        batches = [seed_tokens_from_row(row, args.sku, args.lot_id, row_num)]

    # Status split is observational (inventory explains where purchased units went).
    available_count = 0
    warehouse_count = 0
    unsellable_count = 0
    if RECON_PATH.exists():
        recon = pd.read_csv(RECON_PATH, dtype=str).fillna("")
        rec = recon[recon["seller_sku"] == args.sku]
        if not rec.empty:
            def _to_int(val) -> int:
                try:
                    return int(float(val))
                except Exception:
                    return 0
            inv_available = _to_int(rec.iloc[0].get("inventory_available", 0))
            inv_total = _to_int(rec.iloc[0].get("inventory_total", 0))
            inv_unsellable = _to_int(rec.iloc[0].get("inventory_unsellable", 0))
            net_sold = _to_int(rec.iloc[0].get("net_sold_qty", 0))
            available_count = inv_available + net_sold
            warehouse_count = max(inv_total - inv_available, 0)
            unsellable_count = inv_unsellable

    tokens = []
    for batch in batches:
        for i in range(1, batch["ordered"] + 1):
            token_id = f"{batch['lot_id']}-{i:04d}"
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
                    "status": "available",
                    "received_date": batch["order_date"].date().isoformat() if batch["order_date"] else "",
                    "allocated_order_id": "",
                    "allocated_date": "",
                    "return_order_id": "",
                    "return_date": "",
                    "notes": "seed_from_orders_sheet",
                }
            )

    total = len(tokens)
    if total > 0 and any([available_count, warehouse_count, unsellable_count]):
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

    tokens_df = pd.DataFrame(tokens)
    existing = load_existing_token_ids(token_ws)
    tokens_df = tokens_df[~tokens_df["token_id"].isin(existing)]

    out_path = "out/token_ledger_seed.csv"
    tokens_df.to_csv(out_path, index=False)

    if tokens_df.empty:
        print("No new tokens to write (all tokens already exist).")
        return

    token_ws.append_rows(tokens_df.values.tolist(), value_input_option="RAW")
    print(f"Seeded {len(tokens_df)} tokens to {TOKENS_TAB}. Saved {out_path}.")


if __name__ == "__main__":
    main()
