"""
Build a daily verification checklist for the token system.
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
    from scripts.core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path
    from core.storage import StorageConfig, connect_store, parse_storage_mode, replace_table_from_dataframe

try:
    import gspread
except Exception:
    gspread = None

if TYPE_CHECKING:
    import gspread as gspread_types

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
CHECKLIST_TAB = "Token_Daily_Checklist"

TESTS_CSV = Path("out/token_tests_daily.csv")
EVENTS_CSV = Path("out/token_events.csv")
RECON_TAB = "Token_Stock_Recon_Mismatches"
LEDGER_TAB = "Token_Ledger"
RECON_MISMATCH_CSV = Path("out/token_stock_recon_mismatches.csv")
TOKEN_LEDGER_REL = "token_ledger_live.csv"

OUT_CHECKLIST = Path("out/token_daily_checklist.csv")
SQL_TABLE_CHECKLIST = "b_token_daily_checklist"
WRITE_SHEETS = (
    os.environ.get(
        "TOKEN_DAILY_CHECKLIST_WRITE_SHEETS",
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


def load_sheet_df(tab_name: str) -> pd.DataFrame:
    if not WRITE_SHEETS or gspread is None:
        return pd.DataFrame()
    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    try:
        ws = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return pd.DataFrame()
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])


def _write_checklist_output(df: pd.DataFrame) -> dict[str, object]:
    mode = parse_storage_mode(os.environ.get("SELLERONE_STORAGE_MODE", "csv"))
    sql_rows = 0

    def write_csv() -> None:
        OUT_CHECKLIST.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_CHECKLIST, index=False)

    def write_sql() -> None:
        nonlocal sql_rows
        config = StorageConfig.from_env()
        store = connect_store(config)
        try:
            result = replace_table_from_dataframe(store, SQL_TABLE_CHECKLIST, df)
        finally:
            store.close()
        sql_rows = int(result["rows"])

    if mode == "sql_primary_csv_export":
        write_sql()
        write_csv()
    elif mode == "sql_shadow":
        write_csv()
        write_sql()
    else:
        write_csv()

    return {
        "mode": mode,
        "sql_table": SQL_TABLE_CHECKLIST if sql_rows else "",
        "sql_rows": sql_rows,
    }


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    checks = []
    use_sheets = bool(WRITE_SHEETS and gspread is not None)

    # Tests summary
    if TESTS_CSV.exists():
        tests = pd.read_csv(TESTS_CSV, dtype=str).fillna("")
        if not tests.empty:
            fails = (tests["status"] == "FAIL").sum()
            warns = (tests["status"] == "WARN").sum()
            checks.append({"timestamp": now, "check": "tests_fail_count", "value": str(fails)})
            checks.append({"timestamp": now, "check": "tests_warn_count", "value": str(warns)})
    else:
        checks.append({"timestamp": now, "check": "tests_present", "value": "missing"})

    # Events count today (last 24h)
    if EVENTS_CSV.exists():
        ev = pd.read_csv(EVENTS_CSV, dtype=str).fillna("")
        if not ev.empty and "event_ts" in ev.columns:
            ev["event_ts"] = pd.to_datetime(ev["event_ts"], errors="coerce", utc=True)
            recent = ev[ev["event_ts"] >= (datetime.now(timezone.utc) - pd.Timedelta(days=1))]
            checks.append({"timestamp": now, "check": "events_last_24h", "value": str(len(recent))})
    else:
        checks.append({"timestamp": now, "check": "events_present", "value": "missing"})

    # Recon mismatches count
    recon = load_sheet_df(RECON_TAB)
    if recon.empty and RECON_MISMATCH_CSV.exists():
        recon = pd.read_csv(RECON_MISMATCH_CSV, dtype=str).fillna("")
    if recon.empty:
        checks.append({"timestamp": now, "check": "recon_mismatch_count", "value": "0"})
    else:
        # ignore placeholder row
        if "status" in recon.columns and len(recon.columns) == 1:
            checks.append({"timestamp": now, "check": "recon_mismatch_count", "value": "0"})
        else:
            checks.append({"timestamp": now, "check": "recon_mismatch_count", "value": str(len(recon))})

    # Returned_pending count
    ledger = load_sheet_df(LEDGER_TAB)
    if ledger.empty:
        ledger_paths = resolve_compat_path(TOKEN_LEDGER_REL, default_system="B")
        ledger_path = ledger_paths.live_path if ledger_paths.live_path.exists() else ledger_paths.legacy_path
        if ledger_path.exists():
            ledger = pd.read_csv(ledger_path, dtype=str).fillna("")
    if not ledger.empty and "status" in ledger.columns:
        pending = (ledger["status"] == "returned_pending").sum()
        checks.append({"timestamp": now, "check": "returned_pending_count", "value": str(pending)})

    df = pd.DataFrame(checks)
    if df.empty:
        print({"status": "skip", "reason": "no_checks"})
        return

    output = _write_checklist_output(df)

    if use_sheets:
        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
        try:
            ws = sheet.worksheet(CHECKLIST_TAB)
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(title=CHECKLIST_TAB, rows=max(len(payload) + 10, 2000), cols=10)
        else:
            ws.clear()
        ws.update(range_name="A1", values=payload)

    print(
        {
            "status": "success",
            "rows": len(df),
            "tab": CHECKLIST_TAB if use_sheets else "",
            "snapshot": str(OUT_CHECKLIST),
            "write_sheets": use_sheets,
            **output,
        }
    )


if __name__ == "__main__":
    main()

