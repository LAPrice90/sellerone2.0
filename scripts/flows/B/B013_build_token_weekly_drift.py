"""
Build weekly drift and exception summaries for token system.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from scripts.core.out_paths import resolve_compat_path

try:
    import gspread
except Exception:
    gspread = None

if TYPE_CHECKING:
    import gspread as gspread_types

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
DRIFT_TAB = "Token_Drift_Weekly"
EXCEPTIONS_TAB = "Token_Exceptions_Weekly"

EVENTS_CSV = Path("out/token_events.csv")
RECON_TAB = "Token_Stock_Recon"
LEDGER_TAB = "Token_Ledger"
RECON_CSV = Path("out/token_stock_recon.csv")
TOKEN_LEDGER_REL = "token_ledger_live.csv"

OUT_DRIFT = Path("out/token_drift_weekly.csv")
OUT_EXCEPTIONS = Path("out/token_exceptions_weekly.csv")
WRITE_SHEETS = (
    os.environ.get(
        "TOKEN_WEEKLY_WRITE_SHEETS",
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


def main() -> None:
    now = datetime.now(timezone.utc)
    week_ago = now - pd.Timedelta(days=7)
    use_sheets = bool(WRITE_SHEETS and gspread is not None)

    if not EVENTS_CSV.exists():
        print({"status": "skip", "reason": "missing_token_events"})
        return

    events = pd.read_csv(EVENTS_CSV, dtype=str).fillna("")
    if events.empty:
        print({"status": "skip", "reason": "no_token_events"})
        return

    events["event_ts"] = pd.to_datetime(events.get("event_ts", ""), errors="coerce", utc=True)
    events = events[events["event_ts"].notna()]
    recent = events[events["event_ts"] >= week_ago]

    drift_rows = []
    if not recent.empty:
        recent["qty"] = pd.to_numeric(recent.get("qty", 0), errors="coerce").fillna(0)
        drift = (
            recent.groupby(["event_type", "sku"], dropna=False)["qty"]
            .sum()
            .reset_index()
            .sort_values(by=["event_type", "sku"])
        )
        drift["window_start"] = week_ago.date().isoformat()
        drift["window_end"] = now.date().isoformat()
        drift_rows = drift
    else:
        drift_rows = pd.DataFrame(columns=["event_type", "sku", "qty", "window_start", "window_end"])

    OUT_DRIFT.parent.mkdir(parents=True, exist_ok=True)
    drift_rows.to_csv(OUT_DRIFT, index=False)

    # Exceptions: top mismatches and returned_pending aging
    recon = load_sheet_df(RECON_TAB)
    if recon.empty and RECON_CSV.exists():
        recon = pd.read_csv(RECON_CSV, dtype=str).fillna("")
    exceptions = []
    if not recon.empty:
        for col in ["delta_available", "delta_unsellable", "delta_total"]:
            if col in recon.columns:
                recon[col] = pd.to_numeric(recon[col], errors="coerce").fillna(0)
        recon["abs_delta_total"] = recon.get("delta_total", 0).abs()
        top = recon.sort_values(by="abs_delta_total", ascending=False).head(20)
        for _, row in top.iterrows():
            exceptions.append(
                {
                    "type": "recon_mismatch",
                    "sku": row.get("seller_sku", ""),
                    "delta_available": row.get("delta_available", 0),
                    "delta_unsellable": row.get("delta_unsellable", 0),
                    "delta_total": row.get("delta_total", 0),
                }
            )

    ledger = load_sheet_df(LEDGER_TAB)
    if ledger.empty:
        ledger_paths = resolve_compat_path(TOKEN_LEDGER_REL, default_system="B")
        ledger_path = ledger_paths.live_path if ledger_paths.live_path.exists() else ledger_paths.legacy_path
        if ledger_path.exists():
            ledger = pd.read_csv(ledger_path, dtype=str).fillna("")
    if not ledger.empty and "status" in ledger.columns:
        pending = ledger[ledger["status"] == "returned_pending"].copy()
        if not pending.empty and "return_date" in pending.columns:
            pending["return_date"] = pd.to_datetime(pending["return_date"], errors="coerce", utc=True)
            pending["age_days"] = (now - pending["return_date"]).dt.days
            aged = pending[pending["age_days"] >= 7]
            for _, row in aged.iterrows():
                exceptions.append(
                    {
                        "type": "returned_pending_aging",
                        "sku": row.get("seller_sku", ""),
                        "token_id": row.get("token_id", ""),
                        "age_days": row.get("age_days", ""),
                    }
                )

    exc_df = pd.DataFrame(exceptions)
    OUT_EXCEPTIONS.parent.mkdir(parents=True, exist_ok=True)
    exc_df.to_csv(OUT_EXCEPTIONS, index=False)

    if use_sheets:
        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        _write_tab(sheet, DRIFT_TAB, drift_rows)
        _write_tab(sheet, EXCEPTIONS_TAB, exc_df)

    print(
        {
            "status": "success",
            "drift_rows": len(drift_rows),
            "exception_rows": len(exc_df),
            "tabs": [DRIFT_TAB, EXCEPTIONS_TAB] if use_sheets else [],
            "write_sheets": use_sheets,
        }
    )


def _write_tab(sheet: "gspread_types.Spreadsheet", tab: str, df: pd.DataFrame) -> None:
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=tab, rows=max(len(payload) + 10, 2000), cols=max(len(payload[0]) + 5, 20))
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)


if __name__ == "__main__":
    main()

