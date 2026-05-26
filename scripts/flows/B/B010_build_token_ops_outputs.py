"""
Build operational outputs for tokens:
- Token_Movement_Log (allocations, refunds, stock adjustments)
- Order_COGS_from_Tokens (per order+SKU COGS rollup)
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
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_tables_from_dataframes
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_tables_from_dataframes

try:
    import gspread
except Exception:
    gspread = None

if TYPE_CHECKING:
    import gspread as gspread_types

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
MOVEMENT_TAB = "Token_Movement_Log"
COGS_TAB = "Order_COGS_from_Tokens"
EVENTS_TAB = "Token_Events"

OUT_MOVEMENT = Path("out/token_movement_log.csv")
OUT_COGS = Path("out/order_cogs_from_tokens.csv")
OUT_EVENTS = Path("out/token_events.csv")
SQL_TABLE_MOVEMENT = "b_token_movement_log"
SQL_TABLE_COGS = "b_order_cogs_from_tokens"
TOKEN_LEDGER_REL = "token_ledger_live.csv"
TOKEN_COGS_LEDGER = Path("out/token_cogs_ledger.csv")
WRITE_SHEETS = (
    os.environ.get(
        "TOKEN_OPS_WRITE_SHEETS",
        os.environ.get(
            "TOKEN_EVENTS_WRITE_SHEETS",
            os.environ.get("STOCK_EVENTS_WRITE_SHEETS", "0"),
        ),
    ).strip()
    == "1"
)


def get_gspread_client() -> "gspread_types.Client":
    if gspread is None:
        raise RuntimeError("gspread not available")
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def parse_float(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def load_events_from_sheet() -> pd.DataFrame:
    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    try:
        ws = sheet.worksheet(EVENTS_TAB)
    except gspread.WorksheetNotFound:
        return pd.DataFrame()
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0]).fillna("")


def load_events_local() -> pd.DataFrame:
    if not OUT_EVENTS.exists():
        return pd.DataFrame()
    df = pd.read_csv(OUT_EVENTS, dtype=str).fillna("")
    return df


def load_ledger_costs() -> pd.DataFrame:
    ledger_paths = resolve_compat_path(TOKEN_LEDGER_REL, default_system="B")
    ledger_path = ledger_paths.live_path if ledger_paths.live_path.exists() else ledger_paths.legacy_path
    if not ledger_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(ledger_path, dtype=str).fillna("")
    if "token_id" not in df.columns:
        return pd.DataFrame()
    df["token_cost"] = df.get("cost_per_unit", "").apply(parse_float)
    df["currency"] = df.get("currency", "")
    return df[["token_id", "token_cost", "currency"]]


def load_token_cogs_ledger() -> pd.DataFrame:
    if not TOKEN_COGS_LEDGER.exists():
        return pd.DataFrame()
    df = pd.read_csv(TOKEN_COGS_LEDGER, dtype=str).fillna("")
    if df.empty:
        return pd.DataFrame()
    df["token_cost"] = df.get("token_cost", "").apply(parse_float)
    df["quantity"] = df.get("quantity", "1").apply(lambda v: int(float(v)) if str(v).strip() else 1)
    df["line_cogs"] = df["token_cost"] * df["quantity"].astype(int)
    cogs = (
        df.groupby(["order_id", "seller_sku", "currency"], dropna=False)
        .agg(quantity=("quantity", "sum"), cogs_total=("line_cogs", "sum"))
        .reset_index()
        .rename(columns={"seller_sku": "sku"})
        .sort_values(by=["order_id", "sku"])
    )
    return cogs


def write_sheet(sheet: "gspread_types.Spreadsheet", tab_name: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab_name, rows=max(len(payload) + 10, 2000), cols=max(len(df.columns) + 5, 40))
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)


def _write_outputs(movement: pd.DataFrame, cogs: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = {"movement": 0, "cogs": 0}

    def write_csv_exports() -> None:
        OUT_MOVEMENT.parent.mkdir(parents=True, exist_ok=True)
        movement.to_csv(OUT_MOVEMENT, index=False)
        OUT_COGS.parent.mkdir(parents=True, exist_ok=True)
        cogs.to_csv(OUT_COGS, index=False)

    def write_sql_tables() -> None:
        config = StorageConfig.from_env()
        store = connect_store(config)
        try:
            results = replace_tables_from_dataframes(
                store,
                {
                    SQL_TABLE_MOVEMENT: movement,
                    SQL_TABLE_COGS: cogs,
                },
            )
        finally:
            store.close()
        for result in results:
            table = str(result["table"])
            if table == SQL_TABLE_MOVEMENT:
                sql_rows["movement"] = int(result["rows"])
            elif table == SQL_TABLE_COGS:
                sql_rows["cogs"] = int(result["rows"])

    if mode == "sql_primary_csv_export":
        write_sql_tables()
        write_csv_exports()
    elif mode == "sql_shadow":
        write_csv_exports()
        write_sql_tables()
    else:
        write_csv_exports()

    return {
        "mode": mode,
        "sql_tables": [SQL_TABLE_MOVEMENT, SQL_TABLE_COGS] if any(sql_rows.values()) else [],
        "sql_movement_rows": sql_rows["movement"],
        "sql_cogs_rows": sql_rows["cogs"],
    }


def main() -> None:
    use_sheets = bool(WRITE_SHEETS and gspread is not None)
    movement = load_events_from_sheet() if use_sheets else load_events_local()
    if movement.empty:
        print({"status": "skip", "reason": "no_token_events"})
        return
    movement = movement.sort_values(by=["event_ts", "event_type", "sku"], na_position="last")

    # Build COGS hook from token COGS ledger (preferred)
    cogs = load_token_cogs_ledger()
    if cogs.empty:
        # Fallback to allocation events
        alloc = movement[movement["event_type"] == "Allocation"].copy()
        if not alloc.empty:
            if "qty" not in alloc.columns:
                alloc["qty"] = "1"
            if "token_cost" not in alloc.columns:
                alloc["token_cost"] = ""
            if "currency" not in alloc.columns:
                alloc["currency"] = ""
            # Enrich allocation rows with cost + currency from ledger snapshot
            ledger_costs = load_ledger_costs()
            if not ledger_costs.empty:
                alloc = alloc.merge(ledger_costs, on="token_id", how="left", suffixes=("", "_ledger"))
                alloc["token_cost"] = alloc["token_cost"].apply(parse_float)
                alloc["token_cost_ledger"] = alloc["token_cost_ledger"].apply(parse_float)
                alloc["token_cost"] = alloc["token_cost"].where(alloc["token_cost"] > 0, alloc["token_cost_ledger"])
                alloc["currency"] = alloc["currency"].where(alloc["currency"].astype(str).str.len() > 0, alloc["currency_ledger"])
                alloc = alloc.drop(columns=[c for c in ["token_cost_ledger", "currency_ledger"] if c in alloc.columns])
            alloc["qty"] = alloc["qty"].apply(lambda v: int(float(v)) if str(v).strip() else 1)
            alloc["token_cost"] = alloc["token_cost"].apply(parse_float)
            alloc["line_cogs"] = alloc["token_cost"] * alloc["qty"].astype(int)
            cogs = (
                alloc.groupby(["order_id", "sku", "currency"], dropna=False)
                .agg(quantity=("qty", "sum"), cogs_total=("line_cogs", "sum"))
                .reset_index()
                .sort_values(by=["order_id", "sku"])
            )
        else:
            cogs = pd.DataFrame(columns=["order_id", "sku", "currency", "quantity", "cogs_total"])

    output = _write_outputs(movement, cogs)

    if use_sheets:
        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        write_sheet(sheet, MOVEMENT_TAB, movement)
        write_sheet(sheet, COGS_TAB, cogs)

    print(
        {
            "status": "success",
            "movement_rows": len(movement),
            "cogs_rows": len(cogs),
            "snapshot": str(OUT_MOVEMENT),
            "cogs_snapshot": str(OUT_COGS),
            "tabs": [MOVEMENT_TAB, COGS_TAB] if use_sheets else [],
            "write_sheets": use_sheets,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **output,
        }
    )


if __name__ == "__main__":
    main()

