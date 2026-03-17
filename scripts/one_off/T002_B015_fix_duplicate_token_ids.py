"""
One-time repair: re-key duplicate token_id values in Token_Ledger and update
Token_Allocations + Token_Events to keep references consistent.

This is needed because legacy adjustment tokens were created with second-level
timestamps, causing many duplicates.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
LEDGER_TAB = "Token_Ledger"
ALLOC_TAB = "Token_Allocations"
EVENTS_TAB = "Token_Events"

OUT_LEDGER = Path("out/token_ledger_live.csv")
OUT_ALLOC = Path("out/token_allocations_live.csv")
OUT_EVENTS = Path("out/token_events.csv")


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def _build_mapping(ledger: pd.DataFrame) -> tuple[pd.DataFrame, dict[tuple[str, str, str], list[str]]]:
    token_counts = ledger["token_id"].value_counts()
    dup_ids = token_counts[token_counts > 1].index.tolist()
    if not dup_ids:
        return ledger, {}

    ledger = ledger.copy()
    mapping: dict[tuple[str, str, str], list[str]] = defaultdict(list)

    for token_id in dup_ids:
        idxs = ledger.index[ledger["token_id"] == token_id].tolist()
        for i, idx in enumerate(idxs, start=1):
            new_id = f"{token_id}-DUP{i:04d}"
            ledger.at[idx, "token_id"] = new_id
            order_id = str(ledger.at[idx, "allocated_order_id"]).strip()
            sku = str(ledger.at[idx, "seller_sku"]).strip()
            if order_id and sku:
                mapping[(token_id, order_id, sku)].append(new_id)

    return ledger, mapping


def _apply_mapping(df: pd.DataFrame, mapping: dict[tuple[str, str, str], list[str]], label: str) -> pd.DataFrame:
    if df.empty or not mapping:
        return df
    df = df.copy()
    used = 0
    missing = 0
    # Make a working copy of mapping queues so we can pop safely.
    queues = {k: v.copy() for k, v in mapping.items()}

    for i, row in df.iterrows():
        token_id = str(row.get("token_id", "")).strip()
        order_id = str(row.get("order_id", "")).strip()
        sku = str(row.get("seller_sku", row.get("sku", ""))).strip()
        key = (token_id, order_id, sku)
        if key in queues and queues[key]:
            df.at[i, "token_id"] = queues[key].pop(0)
            used += 1
        elif token_id in {k[0] for k in mapping.keys()}:
            # We saw a duplicate token_id but couldn't map it to a specific row.
            missing += 1

    print({"status": "mapping", "target": label, "updated": used, "unmapped": missing})
    return df


def main() -> None:
    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)

    ledger_ws = sheet.worksheet(LEDGER_TAB)
    alloc_ws = sheet.worksheet(ALLOC_TAB)
    events_ws = sheet.worksheet(EVENTS_TAB)

    ledger = load_sheet_df(ledger_ws)
    alloc = load_sheet_df(alloc_ws)
    events = load_sheet_df(events_ws)

    if ledger.empty:
        print({"status": "skip", "reason": "empty_ledger"})
        return

    updated_ledger, mapping = _build_mapping(ledger)
    if not mapping:
        print({"status": "skip", "reason": "no_duplicate_token_ids"})
        return

    updated_alloc = _apply_mapping(alloc, mapping, "Token_Allocations")

    # Update allocation events only (event_type == Allocation)
    if not events.empty and "event_type" in events.columns:
        alloc_events = events[events["event_type"] == "Allocation"]
        other_events = events[events["event_type"] != "Allocation"]
        alloc_events = _apply_mapping(alloc_events, mapping, "Token_Events")
        updated_events = pd.concat([alloc_events, other_events], ignore_index=True)
    else:
        updated_events = events

    # Write ledger
    ledger_rows = [updated_ledger.columns.tolist()] + updated_ledger.astype(object).where(pd.notnull(updated_ledger), "").values.tolist()
    ledger_ws.clear()
    ledger_ws.update(ledger_rows, value_input_option="RAW")
    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    updated_ledger.to_csv(OUT_LEDGER, index=False)

    # Write allocations
    if not updated_alloc.empty:
        alloc_rows = [updated_alloc.columns.tolist()] + updated_alloc.astype(object).where(pd.notnull(updated_alloc), "").values.tolist()
        alloc_ws.clear()
        alloc_ws.update(alloc_rows, value_input_option="RAW")
        updated_alloc.to_csv(OUT_ALLOC, index=False)

    # Write events
    if not updated_events.empty:
        events_rows = [updated_events.columns.tolist()] + updated_events.astype(object).where(pd.notnull(updated_events), "").values.tolist()
        events_ws.clear()
        events_ws.update(events_rows, value_input_option="RAW")
        updated_events.to_csv(OUT_EVENTS, index=False)

    print(
        {
            "status": "success",
            "duplicate_groups": len(mapping),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )


if __name__ == "__main__":
    main()

