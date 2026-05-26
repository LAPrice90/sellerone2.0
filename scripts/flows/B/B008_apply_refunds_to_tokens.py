"""
Apply refund events to token ledger (FIFO per order_id+sku).

Observation-to-action step:
- Marks tokens as returned_pending with return_order_id/date.
- Does NOT resell tokens; sellable/unsellable handled by stock adjustments.
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
    from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path, write_csv_with_compat

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
TOKEN_LEDGER_TAB = "Token_Ledger"
TOKEN_ALLOC_TAB = "Token_Allocations"
REFUND_EVENTS_TAB = "Refunds_Token_Events"

REFUNDS_CSV = Path("out/financial_events_refunds_official.csv")
OUT_EVENTS = Path("out/refund_token_events.csv")
TOKEN_LEDGER_REL = "token_ledger_live.csv"
TOKEN_ALLOC_REL = "token_allocations_live.csv"
SQL_TABLE_REFUND_EVENTS = "b_refund_token_events"
EVENT_COLUMNS = [
    "order_id",
    "sku",
    "refund_date",
    "requested_qty",
    "applied_qty",
    "status",
    "note",
    "refund_event_id",
    "event_ts",
]
WRITE_SHEETS = os.environ.get("REFUND_EVENTS_WRITE_SHEETS", os.environ.get("STOCK_EVENTS_WRITE_SHEETS", "0")).strip() == "1"


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


def _normalize_events(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    out = df.copy()
    for col in EVENT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[EVENT_COLUMNS].copy()


def _read_prior_local_events() -> pd.DataFrame:
    if not OUT_EVENTS.exists():
        return pd.DataFrame(columns=EVENT_COLUMNS)
    try:
        return _normalize_events(pd.read_csv(OUT_EVENTS, dtype=str).fillna(""))
    except Exception:
        return pd.DataFrame(columns=EVENT_COLUMNS)


def _write_refund_events_output(prior: pd.DataFrame, events: pd.DataFrame, *, use_sheets: bool) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    prior = _normalize_events(prior)
    events = _normalize_events(events)
    combined = pd.concat([prior, events], ignore_index=True)
    if not combined.empty and "refund_event_id" in combined.columns:
        combined = combined.drop_duplicates(subset=["refund_event_id"], keep="last").reset_index(drop=True)
    sql_rows = 0

    def write_csv() -> None:
        OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(OUT_EVENTS, index=False)

    def write_sql() -> None:
        nonlocal sql_rows
        store = connect_store(StorageConfig.from_env())
        try:
            result = replace_table_from_dataframe(store, SQL_TABLE_REFUND_EVENTS, combined)
        finally:
            store.close()
        sql_rows = int(result["rows"])

    if use_sheets:
        write_csv()
    elif mode == "sql_primary_csv_export":
        write_sql()
        write_csv()
    elif mode == "sql_shadow":
        write_csv()
        write_sql()
    else:
        write_csv()

    return {
        "mode": "csv" if use_sheets else mode,
        "sql_table": "" if use_sheets or mode == "csv" else SQL_TABLE_REFUND_EVENTS,
        "sql_rows": sql_rows,
        "total_events": int(len(combined)),
    }


def main() -> None:
    if not REFUNDS_CSV.exists():
        print({"status": "skip", "reason": "missing_refunds_csv"})
        return

    refunds = pd.read_csv(REFUNDS_CSV, dtype=str).fillna("")
    if refunds.empty:
        print({"status": "skip", "reason": "no_refunds"})
        return

    use_sheets = bool(WRITE_SHEETS and gspread is not None)
    sheet = None
    ledger_ws = None
    if use_sheets:
        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        ledger_ws = sheet.worksheet(TOKEN_LEDGER_TAB)
        alloc_ws = sheet.worksheet(TOKEN_ALLOC_TAB)
        ledger = load_sheet_df(ledger_ws)
        alloc = load_sheet_df(alloc_ws)
    else:
        ledger_paths = resolve_compat_path(TOKEN_LEDGER_REL, default_system="B")
        alloc_paths = resolve_compat_path(TOKEN_ALLOC_REL, default_system="B")
        ledger_path = ledger_paths.live_path if ledger_paths.live_path.exists() else ledger_paths.legacy_path
        alloc_path = alloc_paths.live_path if alloc_paths.live_path.exists() else alloc_paths.legacy_path
        if not ledger_path.exists() or not alloc_path.exists():
            print({"status": "skip", "reason": "missing_token_data_local"})
            return
        ledger = pd.read_csv(ledger_path, dtype=str).fillna("")
        alloc = pd.read_csv(alloc_path, dtype=str).fillna("")

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
    prior = pd.DataFrame()
    if use_sheets:
        try:
            ev_ws = sheet.worksheet(REFUND_EVENTS_TAB)
            prior = load_sheet_df(ev_ws)
            applied_ids = set(prior["refund_event_id"].tolist()) if "refund_event_id" in prior.columns else set()
        except gspread.WorksheetNotFound:
            applied_ids = set()
            prior = pd.DataFrame()
    else:
        prior = _read_prior_local_events()
        applied_ids = set(prior["refund_event_id"].tolist()) if "refund_event_id" in prior.columns else set()

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

    events_df = _normalize_events(pd.DataFrame(events))
    output = _write_refund_events_output(prior, events_df, use_sheets=use_sheets)

    if use_sheets:
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
    else:
        write_csv_with_compat(ledger, path_or_rel=TOKEN_LEDGER_REL, index=False, default_system="B")

    print(
        {
            "status": "success",
            "events": len(events_df),
            "snapshot": str(OUT_EVENTS),
            "sheet_tab": REFUND_EVENTS_TAB if use_sheets else "",
            "write_sheets": use_sheets,
            **output,
        }
    )


if __name__ == "__main__":
    main()

