"""
Build append-only Token_Events table from allocations, refunds, and adjustments.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.core.out_paths import resolve_compat_path
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path

try:
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
except ModuleNotFoundError:
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe

try:
    import gspread
except Exception:
    gspread = None

if TYPE_CHECKING:
    import gspread as gspread_types

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ALLOC_TAB = "Token_Allocations"
REFUND_TAB = "Refunds_Token_Events"
ADJUST_TAB = "Stock_Adjustments_Token_Events"
EVENTS_TAB = "Token_Events"

OUT_EVENTS = Path("out/token_events.csv")
OUT_REFUND_EVENTS = Path("out/refund_token_events.csv")
OUT_ADJUST_EVENTS = Path("out/stock_adjustment_token_events.csv")
SQL_TABLE = "b_token_events"
EVENT_COLUMNS = ["event_id", "event_ts", "event_type", "token_id", "order_id", "sku", "qty", "notes"]
WRITE_SHEETS = os.environ.get("TOKEN_EVENTS_WRITE_SHEETS", os.environ.get("STOCK_EVENTS_WRITE_SHEETS", "0")).strip() == "1"


def get_gspread_client() -> "gspread_types.Client":
    if gspread is None:
        raise RuntimeError("gspread not available")
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(ws: "gspread_types.Worksheet") -> pd.DataFrame:
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


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def _read_existing_csv() -> pd.DataFrame:
    if not OUT_EVENTS.exists():
        return _empty_events()
    existing = pd.read_csv(OUT_EVENTS, dtype=str).fillna("")
    for col in EVENT_COLUMNS:
        if col not in existing.columns:
            existing[col] = ""
    return existing[EVENT_COLUMNS].copy()


def _read_existing_sql() -> pd.DataFrame:
    store = connect_store(StorageConfig.from_env())
    try:
        if not store.table_exists(SQL_TABLE):
            return _empty_events()
        rows = store.query_all(f'SELECT * FROM "{SQL_TABLE}"')
    finally:
        store.close()
    if not rows:
        return _empty_events()
    existing = pd.DataFrame(rows).fillna("")
    for col in EVENT_COLUMNS:
        if col not in existing.columns:
            existing[col] = ""
    return existing[EVENT_COLUMNS].copy()


def _write_sql(df: pd.DataFrame) -> int:
    store = connect_store(StorageConfig.from_env())
    try:
        result = replace_table_from_dataframe(store, SQL_TABLE, df[EVENT_COLUMNS].copy())
    finally:
        store.close()
    return int(result["rows"])


def _write_events_output(events: pd.DataFrame, *, use_sheets: bool) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    if use_sheets:
        OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        if OUT_EVENTS.exists():
            events.to_csv(OUT_EVENTS, mode="a", index=False, header=False)
        else:
            events.to_csv(OUT_EVENTS, index=False)
        return {"mode": "csv", "sql_table": "", "sql_rows": 0, "new_events": int(len(events))}

    if mode == "sql_primary_csv_export":
        existing = _read_existing_sql()
        if existing.empty and OUT_EVENTS.exists():
            existing = _read_existing_csv()
        existing_ids = set(existing["event_id"].astype(str).tolist()) if "event_id" in existing.columns else set()
        new_events = events[~events["event_id"].astype(str).isin(existing_ids)].copy()
        combined = pd.concat([existing, new_events], ignore_index=True)[EVENT_COLUMNS]
        sql_rows = _write_sql(combined)
        OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(OUT_EVENTS, index=False)
        return {"mode": mode, "sql_table": SQL_TABLE, "sql_rows": sql_rows, "new_events": int(len(new_events))}

    existing = _read_existing_csv()
    existing_ids = set(existing["event_id"].astype(str).tolist()) if "event_id" in existing.columns else set()
    new_events = events[~events["event_id"].astype(str).isin(existing_ids)].copy()
    if new_events.empty:
        return {"mode": mode, "sql_table": SQL_TABLE if mode != "csv" else "", "sql_rows": len(existing), "new_events": 0}

    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    if OUT_EVENTS.exists():
        new_events.to_csv(OUT_EVENTS, mode="a", index=False, header=False)
    else:
        new_events.to_csv(OUT_EVENTS, index=False)

    if mode == "sql_shadow":
        combined = pd.concat([existing, new_events], ignore_index=True)[EVENT_COLUMNS]
        sql_rows = _write_sql(combined)

    return {"mode": mode, "sql_table": SQL_TABLE if mode != "csv" else "", "sql_rows": sql_rows, "new_events": int(len(new_events))}


def main() -> None:
    use_sheets = bool(WRITE_SHEETS and gspread is not None)
    sheet = None
    if use_sheets:
        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        alloc_df = load_sheet_df(sheet.worksheet(ALLOC_TAB))
        refund_df = load_sheet_df(sheet.worksheet(REFUND_TAB)) if _ws_exists(sheet, REFUND_TAB) else pd.DataFrame()
        adjust_df = load_sheet_df(sheet.worksheet(ADJUST_TAB)) if _ws_exists(sheet, ADJUST_TAB) else pd.DataFrame()
    else:
        alloc_paths = resolve_compat_path("token_allocations_live.csv", default_system="B")
        alloc_path = alloc_paths.live_path if alloc_paths.live_path.exists() else alloc_paths.legacy_path
        if not alloc_path.exists():
            print({"status": "skip", "reason": "missing_allocations"})
            return
        alloc_df = pd.read_csv(alloc_path, dtype=str).fillna("")
        refund_df = pd.read_csv(OUT_REFUND_EVENTS, dtype=str).fillna("") if OUT_REFUND_EVENTS.exists() else pd.DataFrame()
        adjust_df = pd.read_csv(OUT_ADJUST_EVENTS, dtype=str).fillna("") if OUT_ADJUST_EVENTS.exists() else pd.DataFrame()

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

    # Append-only: dedupe by event_id against existing Token_Events.
    if use_sheets:
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

    output = _write_events_output(events[EVENT_COLUMNS].copy(), use_sheets=use_sheets)
    if int(output.get("new_events", 0)) == 0:
        print({"status": "skip", "reason": "no_new_events", **output})
        return

    print({"status": "success", "events": int(output["new_events"]), "tab": EVENTS_TAB if use_sheets else "", "snapshot": str(OUT_EVENTS), "write_sheets": use_sheets, **output})


def _ws_exists(sheet: "gspread_types.Spreadsheet", tab_name: str) -> bool:
    try:
        sheet.worksheet(tab_name)
        return True
    except gspread.WorksheetNotFound:
        return False


if __name__ == "__main__":
    main()

