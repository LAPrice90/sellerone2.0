"""
Apply refund events to token ledger (FIFO per order_id+sku).

Observation-to-action step:
- Marks tokens as returned_pending with return_order_id/date.
- Does NOT resell tokens; sellable/unsellable handled by stock adjustments.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
TOKEN_LEDGER_TAB = "Token_Ledger"
TOKEN_ALLOC_TAB = "Token_Allocations"
REFUND_EVENTS_TAB = "Refunds_Token_Events"

REFUNDS_CSV = Path("out/financial_events_refunds_official.csv")
OUT_EVENTS = Path("out/refund_token_events.csv")


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def parse_int(value: str) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def refund_event_id(row: pd.Series) -> str:
    parts = [
        str(row.get("order_id", "")).strip(),
        str(row.get("sku", "")).strip(),
        str(row.get("refund_date", "")).strip(),
        str(row.get("Price_Total", "")).strip(),
        str(row.get("Shipping_Total", "")).strip(),
        str(row.get("Gift_Total", "")).strip(),
        str(row.get("Promotion_Total", "")).strip(),
    ]
    base = "|".join(parts)
    return str(pd.util.hash_pandas_object(pd.Series([base]), index=False).iloc[0])


def main() -> None:
    if not REFUNDS_CSV.exists():
        print({"status": "skip", "reason": "missing_refunds_csv"})
        return

    refunds = pd.read_csv(REFUNDS_CSV, dtype=str).fillna("")
    if refunds.empty:
        print({"status": "skip", "reason": "no_refunds"})
        return

    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    ledger_ws = sheet.worksheet(TOKEN_LEDGER_TAB)
    alloc_ws = sheet.worksheet(TOKEN_ALLOC_TAB)

    ledger = load_sheet_df(ledger_ws)
    alloc = load_sheet_df(alloc_ws)

    if ledger.empty or alloc.empty:
        print({"status": "skip", "reason": "missing_token_data"})
        return

    ledger = ledger.copy()
    alloc = alloc.copy()

    if "status" not in ledger.columns:
        ledger["status"] = ""
    if "return_order_id" not in ledger.columns:
        ledger["return_order_id"] = ""
    if "return_date" not in ledger.columns:
        ledger["return_date"] = ""
    if "return_event_id" not in ledger.columns:
        ledger["return_event_id"] = ""
    if "last_return_order_id" not in ledger.columns:
        ledger["last_return_order_id"] = ""
    if "last_return_date" not in ledger.columns:
        ledger["last_return_date"] = ""
    if "last_return_event_id" not in ledger.columns:
        ledger["last_return_event_id"] = ""

    # Normalize columns
    refunds = refunds.rename(
        columns={
            "Order ID": "order_id",
            "SKU": "sku",
            "Date": "refund_date",
            "Quantity Ordered": "refund_qty",
        }
    )

    refunds["refund_qty"] = refunds["refund_qty"].apply(parse_int)
    refunds.loc[refunds["refund_qty"] <= 0, "refund_qty"] = 1
    refunds["refund_event_id"] = refunds.apply(refund_event_id, axis=1)

    events = []
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    # Idempotency: load applied refund event ids
    try:
        ev_ws = sheet.worksheet(REFUND_EVENTS_TAB)
        prior = load_sheet_df(ev_ws)
        applied_ids = set(prior["refund_event_id"].tolist()) if "refund_event_id" in prior.columns else set()
    except gspread.WorksheetNotFound:
        applied_ids = set()

    for _, row in refunds.iterrows():
        order_id = str(row.get("order_id", "")).strip()
        sku = str(row.get("sku", "")).strip()
        refund_date = str(row.get("refund_date", "")).strip()
        qty = int(row.get("refund_qty", 1))
        event_id = str(row.get("refund_event_id", "")).strip()
        if not order_id or not sku or qty <= 0:
            continue
        if event_id and event_id in applied_ids:
            continue

        # Find allocated tokens for this order+sku
        alloc_tokens = alloc[(alloc["order_id"] == order_id) & (alloc["seller_sku"] == sku)]
        if alloc_tokens.empty:
            events.append(
                {
                    "order_id": order_id,
                    "sku": sku,
                    "refund_date": refund_date,
                    "requested_qty": qty,
                    "applied_qty": 0,
                    "status": "missing_allocations",
                    "note": "No allocations found for refund.",
                    "refund_event_id": event_id,
                    "event_ts": now_iso,
                }
            )
            continue

        token_ids = alloc_tokens["token_id"].tolist()
        applied = 0
        for token_id in token_ids:
            if applied >= qty:
                break
            idx = ledger.index[ledger["token_id"] == token_id]
            if idx.empty:
                continue
            # Skip if already marked for this refund event
            if ledger.loc[idx, "return_event_id"].astype(str).eq(event_id).iloc[0]:
                continue
            ledger.loc[idx, "status"] = "returned_pending"
            ledger.loc[idx, "return_order_id"] = order_id
            ledger.loc[idx, "return_date"] = refund_date or now_iso
            ledger.loc[idx, "return_event_id"] = event_id
            applied += 1

        events.append(
            {
                "order_id": order_id,
                "sku": sku,
                "refund_date": refund_date,
                "requested_qty": qty,
                "applied_qty": applied,
                "status": "ok" if applied == qty else "partial",
                "note": "",
                "refund_event_id": event_id,
                "event_ts": now_iso,
            }
        )

    events_df = pd.DataFrame(events)
    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    events_df.to_csv(OUT_EVENTS, index=False)

    # Write updated ledger to sheet
    rows = [ledger.columns.tolist()] + ledger.astype(object).where(pd.notnull(ledger), "").values.tolist()
    ledger_ws.clear()
    ledger_ws.update(rows, value_input_option="RAW")

    # Append refund events to sheet (append-only)
    try:
        ev_ws = sheet.worksheet(REFUND_EVENTS_TAB)
    except gspread.WorksheetNotFound:
        ev_ws = sheet.add_worksheet(title=REFUND_EVENTS_TAB, rows=max(len(events_df) + 10, 2000), cols=25)
        ev_ws.update(range_name="A1", values=[events_df.columns.tolist()])
    if not events_df.empty:
        ev_ws.append_rows(events_df.values.tolist(), value_input_option="RAW")

    print({"status": "success", "events": len(events_df), "snapshot": str(OUT_EVENTS), "sheet_tab": REFUND_EVENTS_TAB})


if __name__ == "__main__":
    main()

