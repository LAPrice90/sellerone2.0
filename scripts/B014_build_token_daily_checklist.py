"""
Build a daily verification checklist for the token system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
CHECKLIST_TAB = "Token_Daily_Checklist"

TESTS_CSV = Path("out/token_tests_daily.csv")
EVENTS_CSV = Path("out/token_events.csv")
RECON_TAB = "Token_Stock_Recon_Mismatches"
LEDGER_TAB = "Token_Ledger"

OUT_CHECKLIST = Path("out/token_daily_checklist.csv")


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def load_sheet_df(tab_name: str) -> pd.DataFrame:
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


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    checks = []

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
    if not ledger.empty and "status" in ledger.columns:
        pending = (ledger["status"] == "returned_pending").sum()
        checks.append({"timestamp": now, "check": "returned_pending_count", "value": str(pending)})

    df = pd.DataFrame(checks)
    if df.empty:
        print({"status": "skip", "reason": "no_checks"})
        return

    OUT_CHECKLIST.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CHECKLIST, index=False)

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

    print({"status": "success", "rows": len(df), "tab": CHECKLIST_TAB, "snapshot": str(OUT_CHECKLIST)})


if __name__ == "__main__":
    main()
