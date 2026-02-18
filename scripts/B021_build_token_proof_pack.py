"""
Build a proof-pack snapshot for token system health.
Writes a compact table of row counts, columns, and latest timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gspread
import pandas as pd

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
PROOF_TAB = "Token_Proof_Pack"

OUT_PROOF = Path("out/token_proof_pack.csv")

CSV_FILES = [
    "out/token_ledger_live.csv",
    "out/token_events.csv",
    "out/token_allocations_live.csv",
    "out/refund_token_events.csv",
    "out/stock_adjustment_token_events.csv",
    "out/token_tests_daily.csv",
    "out/token_daily_checklist.csv",
    "out/token_stock_recon.csv",
    "out/token_stock_recon_mismatches.csv",
    "out/token_drift_weekly.csv",
    "out/token_exceptions_weekly.csv",
    "out/token_movement_log.csv",
    "out/order_cogs_from_tokens.csv",
]

TIMESTAMP_COLUMNS = [
    "event_ts",
    "updated_at",
    "timestamp",
    "event_date",
    "date",
    "return_date",
]


def get_gspread_client() -> gspread.Client:
    cred_path = Path("secrets/sellerone-2-0d3642b951a0.json")
    return gspread.service_account(filename=str(cred_path))


def _latest_timestamp(df: pd.DataFrame) -> str:
    for col in TIMESTAMP_COLUMNS:
        if col in df.columns:
            series = pd.to_datetime(df[col], errors="coerce", utc=True)
            if series.notna().any():
                return series.max().isoformat()
    return ""


def _file_stats(path: Path) -> dict[str, str]:
    if not path.exists():
        return {
            "file": str(path),
            "status": "missing",
            "row_count": "0",
            "columns": "0",
            "latest_ts": "",
            "file_mtime": "",
        }

    if path.stat().st_size == 0:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        return {
            "file": str(path),
            "status": "empty",
            "row_count": "0",
            "columns": "0",
            "latest_ts": "",
            "file_mtime": mtime,
        }
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        return {
            "file": str(path),
            "status": "empty",
            "row_count": "0",
            "columns": "0",
            "latest_ts": "",
            "file_mtime": mtime,
        }
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "file": str(path),
        "status": "ok",
        "row_count": str(len(df)),
        "columns": str(len(df.columns)),
        "latest_ts": _latest_timestamp(df),
        "file_mtime": mtime,
    }


def _append_test_summary(rows: list[dict[str, str]]) -> None:
    tests_path = Path("out/token_tests_daily.csv")
    if not tests_path.exists():
        return
    tests = pd.read_csv(tests_path, dtype=str).fillna("")
    if tests.empty or "status" not in tests.columns:
        return
    fails = (tests["status"] == "FAIL").sum()
    warns = (tests["status"] == "WARN").sum()
    now = datetime.now(timezone.utc).isoformat()
    rows.append(
        {
            "file": "token_tests_summary",
            "status": "ok",
            "row_count": "",
            "columns": "",
            "latest_ts": now,
            "file_mtime": "",
            "tests_fail_count": str(fails),
            "tests_warn_count": str(warns),
        }
    )


def main() -> None:
    rows = []
    for path_str in CSV_FILES:
        rows.append(_file_stats(Path(path_str)))
    _append_test_summary(rows)

    df = pd.DataFrame(rows)
    OUT_PROOF.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PROOF, index=False)

    client = get_gspread_client()
    sheet = client.open_by_key(TOKENS_SHEET_ID)
    payload = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
    try:
        ws = sheet.worksheet(PROOF_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=PROOF_TAB, rows=max(len(payload) + 10, 2000), cols=max(len(payload[0]) + 5, 20))
    else:
        ws.clear()
    ws.update(range_name="A1", values=payload)

    print({"status": "success", "rows": len(df), "tab": PROOF_TAB, "snapshot": str(OUT_PROOF)})


if __name__ == "__main__":
    main()
