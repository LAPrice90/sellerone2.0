"""
Build an action list for unresolved stock adjustment partials.
Outputs a per-event row with remaining qty and context from ledger + Orders sheet.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import re

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ORDERS_SHEET_ID = "1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY"

EVENTS_CSV = Path("out/stock_adjustment_token_events.csv")
LEDGER_CSV = Path("out/token_ledger_live.csv")

ORDERS_TAB = "Orders"
OUTPUT_TAB = "Token_Adjustment_Partials"
OUT_PATH = Path("out/adjustment_partials_action.csv")


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    match = re.search(r"[-+]?[0-9]*\.?[0-9]+", str(value).replace(",", ""))
    return float(match.group()) if match else 0.0


def main() -> None:
    if not EVENTS_CSV.exists():
        print({"status": "skip", "reason": "missing_stock_adjustment_token_events"})
        return

    events = pd.read_csv(EVENTS_CSV, dtype=str).fillna("")
    if events.empty:
        print({"status": "skip", "reason": "empty_events"})
        return

    events["quantity"] = pd.to_numeric(events.get("quantity", 0), errors="coerce").fillna(0).astype(int)
    events["applied_qty"] = pd.to_numeric(events.get("applied_qty", 0), errors="coerce").fillna(0).astype(int)
    events["base_event_id"] = events["event_id"].astype(str).str.split("-retry").str[0]

    grouped = (
        events.groupby(["base_event_id", "sku", "disposition", "event_date"])
        .agg(
            original_qty=("quantity", lambda s: int(s.abs().max()) if len(s) else 0),
            applied_qty=("applied_qty", "sum"),
            status=("status", lambda s: ",".join(sorted(set([x for x in s if x])))),
        )
        .reset_index()
    )
    grouped["remaining_qty"] = grouped["original_qty"] - grouped["applied_qty"]
    open_partials = grouped[grouped["remaining_qty"] > 0].copy()

    if open_partials.empty:
        print({"status": "success", "rows": 0, "note": "no_open_partials"})
        return

    ledger = pd.read_csv(LEDGER_CSV, dtype=str).fillna("") if LEDGER_CSV.exists() else pd.DataFrame()
    ledger_counts = {}
    if not ledger.empty and "seller_sku" in ledger.columns:
        ledger_counts = ledger.groupby("seller_sku")["token_id"].count().to_dict()

    # Orders sheet coverage
    client = get_gspread_client()
    orders_ws = client.open_by_key(ORDERS_SHEET_ID).worksheet(ORDERS_TAB)
    orders_vals = orders_ws.get_all_values()
    orders_rows = orders_vals[1:] if orders_vals else []
    orders_map = {}
    for row in orders_rows:
        if len(row) < 10:
            continue
        sku = row[2].strip()
        if not sku:
            continue
        ordered = int(float(row[9] or 0))
        cost = parse_cost(row[7]) if len(row) > 7 else 0.0
        orders_map.setdefault(sku, {"ordered_total": 0, "cost_sample": cost})
        orders_map[sku]["ordered_total"] += ordered

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    open_partials["token_total"] = open_partials["sku"].map(ledger_counts).fillna(0).astype(int)
    open_partials["ordered_total"] = open_partials["sku"].map(
        {k: v["ordered_total"] for k, v in orders_map.items()}
    ).fillna(0).astype(int)
    open_partials["cost_sample"] = open_partials["sku"].map(
        {k: v["cost_sample"] for k, v in orders_map.items()}
    ).fillna(0.0)
    open_partials["action"] = open_partials.apply(
        lambda r: "add_purchase_rows" if r["ordered_total"] == 0 else "rebuild_tokens", axis=1
    )
    open_partials["updated_at"] = now_iso

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    open_partials.to_csv(OUT_PATH, index=False)

    token_sheet = client.open_by_key(TOKENS_SHEET_ID)
    try:
        ws = token_sheet.worksheet(OUTPUT_TAB)
    except gspread.WorksheetNotFound:
        ws = token_sheet.add_worksheet(title=OUTPUT_TAB, rows=max(len(open_partials) + 10, 2000), cols=20)
    else:
        ws.clear()
    ws.update(range_name="A1", values=[open_partials.columns.tolist()] + open_partials.astype(str).values.tolist())

    print({"status": "success", "rows": len(open_partials), "sheet_tab": OUTPUT_TAB, "snapshot": str(OUT_PATH)})


if __name__ == "__main__":
    main()
