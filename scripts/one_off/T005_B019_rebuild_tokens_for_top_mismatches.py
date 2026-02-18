"""
Rebuild tokens for top mismatch SKUs (positive delta_total_effective).
Uses Orders sheet purchase data and replaces Token_Ledger + clears allocations for those SKUs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import re

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"

MISMATCH_PATH = Path("out/token_stock_recon_mismatches.csv")
RECON_PATH = Path("out/token_stock_recon.csv")
ORDERS_TAB = "Orders"
ORDERS_CSV = Path(os.environ.get("ORDERS_CSV", "out/orders_sheet_orders.csv"))
TOKEN_LEDGER_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"
SUMMARY_TAB = "Token_Rebuild_Summary"

OUT_SUMMARY = Path("out/token_rebuild_summary.csv")

TOP_N = 5


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def _parse_cost(value: str) -> float:
    match = re.search(r"[-+]?[0-9]*\\.?[0-9]+", str(value).replace(",", ""))
    return float(match.group()) if match else 0.0


def _parse_date(value: str):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def load_orders_rows() -> list[dict]:
    if ORDERS_CSV.exists():
        df = pd.read_csv(ORDERS_CSV, dtype=str).fillna("")
        rows = []
        for _, r in df.iterrows():
            rows.append(
                {
                    "sku": r.get("SKU", "").strip(),
                    "lot_id": (r.get("Lot ID") or r.get("Batch") or r.get("Unnamed: 1") or r.get("Unnamed: 0") or "").strip(),
                    "order_date": r.get("Order Date", "").strip(),
                    "ordered": r.get("Ordered", ""),
                    "delivered": r.get("Delivered", ""),
                    "sent_to_fba": r.get("Sent to FBA", ""),
                    "cost": r.get("Cost PU", ""),
                    "asin": r.get("Asin", "").strip(),
                }
            )
        return rows
    return []


def parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(value).replace(",", ""))
    return float(match.group()) if match else 0.0


def parse_date(value: str):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def main() -> None:
    if not MISMATCH_PATH.exists():
        print({"status": "skip", "reason": "missing_mismatch_file"})
        return

    mismatches = pd.read_csv(MISMATCH_PATH, dtype=str).fillna("")
    if mismatches.empty:
        print({"status": "skip", "reason": "empty_mismatch_file"})
        return

    mismatches["delta_total_effective"] = pd.to_numeric(
        mismatches.get("delta_total_effective", 0), errors="coerce"
    ).fillna(0)
    top = mismatches[mismatches["delta_total_effective"] > 0].sort_values(
        "delta_total_effective", ascending=False
    ).head(TOP_N)
    if top.empty:
        print({"status": "skip", "reason": "no_positive_mismatches"})
        return

    client = get_gspread_client()
    token_sheet = client.open_by_key(TOKENS_SHEET_ID)
    orders_sheet = client.open_by_key(ORDERS_SHEET_ID)

    ledger_ws = token_sheet.worksheet(TOKEN_LEDGER_TAB)
    alloc_ws = token_sheet.worksheet(ALLOC_TAB)

    orders_rows = load_orders_rows()
    if not orders_rows:
        orders_ws = orders_sheet.worksheet(ORDERS_TAB)
        orders_vals = orders_ws.get_all_values()
        orders_rows = orders_vals[1:] if orders_vals else []
    ledger = load_sheet_df(ledger_ws)
    alloc = load_sheet_df(alloc_ws)

    summary_rows = []
    new_tokens = []
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    for _, row in top.iterrows():
        sku = str(row.get("seller_sku", "")).strip()
        if not sku:
            continue

        # Status split is observational; token counts come only from purchases.
        available_count = 0
        warehouse_count = 0
        unsellable_count = 0
        if RECON_PATH.exists():
            recon = pd.read_csv(RECON_PATH, dtype=str).fillna("")
            rec = recon[recon["seller_sku"] == sku]
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

        batches = []
        ordered_total = 0
        for row_num, o in enumerate(orders_rows, start=2):
            if isinstance(o, dict):
                if str(o.get("sku", "")).strip() != sku:
                    continue
                ordered = int(float(o.get("ordered") or 0))
                if ordered <= 0:
                    continue
                lot_id = str(o.get("lot_id", "")).strip()
                if not lot_id:
                    order_date = _parse_date(o.get("order_date", ""))
                    date_str = order_date.date().isoformat() if order_date else f"row{row_num}"
                    lot_id = f"{sku}-{date_str}-row{row_num}"
                delivered = int(float(o.get("delivered") or 0))
                sent_to_fba = int(float(o.get("sent_to_fba") or 0))
                batches.append(
                    {
                        "lot_id": lot_id,
                        "order_date": _parse_date(o.get("order_date", "")),
                        "ordered": ordered,
                        "delivered": delivered,
                        "sent_to_fba": sent_to_fba,
                        "cost": _parse_cost(o.get("cost", "")),
                        "asin": str(o.get("asin", "")).strip(),
                    }
                )
                ordered_total += ordered
                continue

            if len(o) < 12 or o[2].strip() != sku:
                continue
            ordered = int(float(o[9] or 0))
            if ordered <= 0:
                continue
            lot_id = o[1].strip()
            if not lot_id:
                order_date = parse_date(o[8])
                date_str = order_date.date().isoformat() if order_date else f"row{row_num}"
                lot_id = f"{sku}-{date_str}-row{row_num}"
            delivered = int(float(o[10] or 0))
            sent_to_fba = int(float(o[11] or 0))
            batches.append(
                {
                    "lot_id": lot_id,
                    "order_date": parse_date(o[8]),
                    "ordered": ordered,
                    "delivered": delivered,
                    "sent_to_fba": sent_to_fba,
                    "cost": parse_cost(o[7]),
                    "asin": o[4].strip(),
                }
            )
            ordered_total += ordered

        if ordered_total <= 0:
            summary_rows.append(
                {
                    "seller_sku": sku,
                    "ordered_total": ordered_total,
                    "created_tokens": 0,
                    "status": "skip_no_orders",
                    "updated_at": now_iso,
                }
            )
            continue

        batches.sort(key=lambda b: (b["order_date"] or datetime.min))
        created = 0
        remaining = ordered_total
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch["ordered"], remaining)
            for i in range(1, take + 1):
                token_id = f"{batch['lot_id']}-{i:04d}"
                status = "available"
                new_tokens.append(
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
                        "received_date": batch["order_date"].date().isoformat() if batch["order_date"] else "",
                        "allocated_order_id": "",
                        "allocated_date": "",
                        "return_order_id": "",
                        "return_date": "",
                        "notes": "rebuild_top_mismatch",
                        "return_event_id": "",
                        "last_return_order_id": "",
                        "last_return_date": "",
                        "last_return_event_id": "",
                        "disposed_event_id": "",
                        "disposed_date": "",
                        "disposed_reason": "",
                    }
                )
                created += 1
            remaining -= take

        # Apply status split based on stock + net sold.
        start_idx = len(new_tokens) - created
        total = created
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
                new_tokens[start_idx + idx]["status"] = status
                idx += 1

        summary_rows.append(
            {
                "seller_sku": sku,
                "ordered_total": ordered_total,
                "created_tokens": created,
                "status": "ok" if created == ordered_total else "partial",
                "updated_at": now_iso,
            }
        )

    if not new_tokens:
        print({"status": "skip", "reason": "no_tokens_created"})
        return

    # Replace ledger rows for affected SKUs
    affected = {r["seller_sku"] for r in summary_rows if r["status"] == "ok"}
    ledger_kept = ledger[~ledger["seller_sku"].isin(affected)] if not ledger.empty else pd.DataFrame()
    updated_ledger = pd.concat([ledger_kept, pd.DataFrame(new_tokens)], ignore_index=True)

    ledger_rows = [updated_ledger.columns.tolist()] + updated_ledger.astype(object).where(pd.notnull(updated_ledger), "").values.tolist()
    ledger_ws.clear()
    ledger_ws.update(ledger_rows, value_input_option="RAW")

    # Remove allocations for affected SKUs
    if not alloc.empty and affected:
        alloc_kept = alloc[~alloc["seller_sku"].isin(affected)]
        alloc_rows = [alloc_kept.columns.tolist()] + alloc_kept.astype(object).where(pd.notnull(alloc_kept), "").values.tolist()
        alloc_ws.clear()
        alloc_ws.update(alloc_rows, value_input_option="RAW")

    summary_df = pd.DataFrame(summary_rows)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(OUT_SUMMARY, index=False)

    try:
        sum_ws = token_sheet.worksheet(SUMMARY_TAB)
    except gspread.WorksheetNotFound:
        sum_ws = token_sheet.add_worksheet(title=SUMMARY_TAB, rows=max(len(summary_df) + 10, 2000), cols=20)
    else:
        sum_ws.clear()
    sum_ws.update(range_name="A1", values=[summary_df.columns.tolist()] + summary_df.astype(str).values.tolist())

    print({"status": "success", "skus": len(affected), "summary": str(OUT_SUMMARY), "sheet_tab": SUMMARY_TAB})


if __name__ == "__main__":
    main()
