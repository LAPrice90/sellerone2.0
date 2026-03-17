"""
Backfill missing tokens for SKUs where token_total == 0 and expected_token_total > 0.
Uses the Orders sheet as the purchase source and creates tokens up to expected units.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"

MISMATCH_TAB = "Token_Stock_Recon_Mismatches"
LEDGER_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"
ORDERS_TAB = "Orders"
SUMMARY_TAB = "Token_Backfill_Missing"

OUT_SUMMARY = Path("out/token_backfill_missing_summary.csv")
RECON_PATH = Path("out/token_stock_recon.csv")


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    match = re.search(r"[-+]?[0-9]*\\.?[0-9]+", str(value).replace(",", ""))
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
    client = get_gspread_client()
    token_sheet = client.open_by_key(TOKENS_SHEET_ID)
    orders_sheet = client.open_by_key(ORDERS_SHEET_ID)

    mismatch_ws = token_sheet.worksheet(MISMATCH_TAB)
    ledger_ws = token_sheet.worksheet(LEDGER_TAB)
    alloc_ws = token_sheet.worksheet(ALLOC_TAB)
    orders_ws = orders_sheet.worksheet(ORDERS_TAB)

    mismatches = load_sheet_df(mismatch_ws)
    if mismatches.empty:
        print({"status": "skip", "reason": "no_mismatches"})
        return

    for col in ["token_total", "expected_token_total"]:
        if col in mismatches.columns:
            mismatches[col] = pd.to_numeric(mismatches[col], errors="coerce").fillna(0).astype(int)

    targets = mismatches[mismatches["token_total"] == 0]
    if targets.empty:
        print({"status": "skip", "reason": "no_missing_token_targets"})
        return

    ledger = load_sheet_df(ledger_ws)
    alloc = load_sheet_df(alloc_ws)
    orders_rows = orders_ws.get_all_values()
    orders = orders_rows[1:] if orders_rows else []

    summary_rows = []
    tokens_out = []

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    for _, row in targets.iterrows():
        sku = str(row.get("seller_sku", "")).strip()
        expected_units = 0
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
        if not sku:
            continue

        # Skip if tokens already exist for this SKU
        if not ledger.empty and (ledger["seller_sku"] == sku).any():
            summary_rows.append(
                {
                    "seller_sku": sku,
                    "expected_units": expected_units,
                    "ordered_units": 0,
                    "created_units": 0,
                    "status": "skip_existing_tokens",
                    "note": "",
                    "updated_at": now_iso,
                }
            )
            continue

        # Build purchase batches from Orders sheet
        batches = []
        ordered_total = 0
        for row_num, o in enumerate(orders, start=2):
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

        batches.sort(key=lambda b: (b["order_date"] or datetime.min))

        if ordered_total <= 0:
            summary_rows.append(
                {
                    "seller_sku": sku,
                    "expected_units": 0,
                    "ordered_units": 0,
                    "created_units": 0,
                    "status": "skip_no_orders",
                    "note": "",
                    "updated_at": now_iso,
                }
            )
            continue

        expected_units = ordered_total
        remaining = expected_units
        created = 0
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch["ordered"], remaining)

            for i in range(1, take + 1):
                token_id = f"{batch['lot_id']}-{i:04d}"
                status = "available"
                tokens_out.append(
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
                        "notes": "backfill_missing",
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
        start_idx = len(tokens_out) - created
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
                tokens_out[start_idx + idx]["status"] = status
                idx += 1

        summary_rows.append(
            {
                "seller_sku": sku,
                "expected_units": expected_units,
                "ordered_units": ordered_total,
                "created_units": created,
                "status": "ok" if created == expected_units else "partial",
                "note": "",
                "updated_at": now_iso,
            }
        )

    if not tokens_out:
        print({"status": "skip", "reason": "no_tokens_created"})
        return

    # Update ledger: keep existing, add new tokens
    if ledger.empty:
        updated_ledger = pd.DataFrame(tokens_out)
    else:
        updated_ledger = pd.concat([ledger, pd.DataFrame(tokens_out)], ignore_index=True)

    ledger_rows = [updated_ledger.columns.tolist()] + updated_ledger.astype(object).where(pd.notnull(updated_ledger), "").values.tolist()
    ledger_ws.clear()
    ledger_ws.update(ledger_rows, value_input_option="RAW")

    # Remove allocations for affected SKUs (none expected, but keep consistent)
    affected = {r["seller_sku"] for r in summary_rows if r["status"] in {"ok", "partial"}}
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

    print({"status": "success", "created_tokens": len(tokens_out), "summary": str(OUT_SUMMARY), "sheet_tab": SUMMARY_TAB})


if __name__ == "__main__":
    main()

