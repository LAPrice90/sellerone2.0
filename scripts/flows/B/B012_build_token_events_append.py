"""
Build append-only Token_Events table from allocations, refunds, and adjustments.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ALLOC_TAB = "Token_Allocations"
REFUND_TAB = "Refunds_Token_Events"
ADJUST_TAB = "Stock_Adjustments_Token_Events"
EVENTS_TAB = "Token_Events"

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


def make_id(parts: list[str]) -> str:
    base = "|".join(parts)
    return str(pd.util.hash_pandas_object(pd.Series([base]), index=False).iloc[0])


def build_from_alloc(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["event_type"] = "Allocation"
    df["event_ts"] = df.get("allocation_date", "")
    df["order_id"] = df.get("order_id", "")
    df["sku"] = df.get("seller_sku", "")
    df["token_id"] = df.get("token_id", "")
    df["qty"] = df.get("quantity", "1")
    df["notes"] = df.get("notes", "")
    df["event_id"] = df.apply(
        lambda r: make_id(
            [
                "ALLOC",
                str(r.get("order_id", "")),
                str(r.get("sku", "")),
                str(r.get("token_id", "")),
                str(r.get("event_ts", "")),
            ]
        ),
        axis=1,
    )
    return df[["event_id", "event_ts", "event_type", "token_id", "order_id", "sku", "qty", "notes"]]


def build_from_refunds(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["event_type"] = "Refund"
    df["event_ts"] = df.get("event_ts", "")
    df["order_id"] = df.get("order_id", "")
    df["sku"] = df.get("sku", "")
    df["token_id"] = df.get("token_id", "")
    df["qty"] = df.get("applied_qty", "0")
    df["notes"] = df.get("note", "")
    if "refund_event_id" in df.columns:
        df["event_id"] = df["refund_event_id"]
    else:
        df["event_id"] = df.apply(
            lambda r: make_id(
                [
                    "REFUND",
                    str(r.get("order_id", "")),
                    str(r.get("sku", "")),
                    str(r.get("event_ts", "")),
                    str(r.get("qty", "")),
                ]
            ),
            axis=1,
        )
    return df[["event_id", "event_ts", "event_type", "token_id", "order_id", "sku", "qty", "notes"]]


def build_from_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["event_type"] = df.get("event_type", "StockAdjustment")
    df["event_ts"] = df.get("event_ts", "")
    df["order_id"] = ""
    df["sku"] = df.get("sku", "")
    df["token_id"] = df.get("token_id", "")
    df["qty"] = df.get("applied_qty", "0")
    df["notes"] = df.get("note", "")
    df["event_id"] = df.get("event_id", "")
    return df[["event_id", "event_ts", "event_type", "token_id", "order_id", "sku", "qty", "notes"]]


def main() -> None:
    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)

    alloc_df = load_sheet_df(sheet.worksheet(ALLOC_TAB))
    refund_df = load_sheet_df(sheet.worksheet(REFUND_TAB)) if _ws_exists(sheet, REFUND_TAB) else pd.DataFrame()
    adjust_df = load_sheet_df(sheet.worksheet(ADJUST_TAB)) if _ws_exists(sheet, ADJUST_TAB) else pd.DataFrame()

    events = pd.concat(
        [
            build_from_alloc(alloc_df),
            build_from_refunds(refund_df),
            build_from_adjustments(adjust_df),
        ],
        ignore_index=True,
    )
    if events.empty:
        print({"status": "skip", "reason": "no_events"})
        return

    # Append-only: dedupe by event_id against existing Token_Events
    if _ws_exists(sheet, EVENTS_TAB):
        existing = load_sheet_df(sheet.worksheet(EVENTS_TAB))
        existing_ids = set(existing["event_id"].tolist()) if "event_id" in existing.columns else set()
    else:
        existing_ids = set()

    events = events[~events["event_id"].isin(existing_ids)]
    if events.empty:
        print({"status": "skip", "reason": "no_new_events"})
        return

    try:
        ws = sheet.worksheet(EVENTS_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=EVENTS_TAB, rows=2000, cols=20)
        ws.update(range_name="A1", values=[events.columns.tolist()])
    ws.append_rows(events.values.tolist(), value_input_option="RAW")

    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    if OUT_EVENTS.exists():
        events.to_csv(OUT_EVENTS, mode="a", index=False, header=False)
    else:
        events.to_csv(OUT_EVENTS, index=False)

    print({"status": "success", "events": len(events), "tab": EVENTS_TAB, "snapshot": str(OUT_EVENTS)})


def _ws_exists(sheet: gspread.Spreadsheet, tab_name: str) -> bool:
    try:
        sheet.worksheet(tab_name)
        return True
    except gspread.WorksheetNotFound:
        return False


if __name__ == "__main__":
    main()

