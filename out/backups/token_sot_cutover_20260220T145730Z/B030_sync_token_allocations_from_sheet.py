"""
Sync Token_Allocations sheet to local CSV so downstream COGS is consistent.
"""

from __future__ import annotations

from pathlib import Path
import os
import sys
from datetime import datetime, timezone
import csv

try:
    import gspread
except Exception:  # pragma: no cover - optional dependency in degraded mode
    gspread = None
import pandas as pd
from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat

TOKENS_SHEET_ID = "1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw"
ALLOC_TAB = "Token_Allocations"
OUT_REL = "token_allocations_live.csv"
FORCE_SYNC = os.environ.get("TOKEN_ALLOC_SYNC_FORCE", "0").strip() == "1"
B_SHEET_SYNC_STATUS_PATH = Path("out/b_sheet_sync_status.csv")


def load_sheet_df(ws: gspread.Worksheet) -> pd.DataFrame:
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_sync_status(
    *,
    step: str,
    status: str,
    severity: str,
    mode: str,
    note: str,
    local_rows: int = -1,
    sheet_rows: int = -1,
) -> None:
    headers = [
        "timestamp_utc",
        "step",
        "status",
        "severity",
        "mode",
        "local_rows",
        "sheet_rows",
        "note",
    ]
    B_SHEET_SYNC_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = (not B_SHEET_SYNC_STATUS_PATH.exists()) or B_SHEET_SYNC_STATUS_PATH.stat().st_size == 0
    with B_SHEET_SYNC_STATUS_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if need_header:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp_utc": _ts(),
                "step": step,
                "status": status,
                "severity": severity,
                "mode": mode,
                "local_rows": str(local_rows if local_rows >= 0 else ""),
                "sheet_rows": str(sheet_rows if sheet_rows >= 0 else ""),
                "note": str(note or "").strip(),
            }
        )


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    resolved = resolve_compat_path(OUT_REL, default_system="B")
    local_path = resolved.live_path if resolved.live_path.exists() else resolved.legacy_path

    try:
        if gspread is None:
            raise RuntimeError("gspread_unavailable")
        try:
            from scripts.flows.A.A003_run_inventory_to_sheet import get_gspread_client
        except ModuleNotFoundError:
            from flows.A.A003_run_inventory_to_sheet import get_gspread_client

        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        alloc_ws = sheet.worksheet(ALLOC_TAB)
        alloc_df = load_sheet_df(alloc_ws)
    except Exception as exc:
        local_rows = -1
        if local_path.exists():
            try:
                local_rows = len(pd.read_csv(local_path, dtype=str).fillna(""))
            except Exception:
                local_rows = -1
        if local_path.exists() and local_rows >= 0:
            _append_sync_status(
                step="B030_sync_token_allocations_from_sheet",
                status="degraded_local",
                severity="warn",
                mode="local_fallback",
                note=f"sheet_sync_failed={type(exc).__name__}:{exc}",
                local_rows=local_rows,
            )
            print(
                {
                    "status": "degraded_local",
                    "reason": f"sheet_sync_failed:{type(exc).__name__}",
                    "local_rows": local_rows,
                    "local_path": str(local_path),
                }
            )
            return
        _append_sync_status(
            step="B030_sync_token_allocations_from_sheet",
            status="hard_fail",
            severity="fail",
            mode="sheet_required",
            note=f"sheet_sync_failed_no_local={type(exc).__name__}:{exc}",
        )
        raise

    if alloc_df.empty:
        _append_sync_status(
            step="B030_sync_token_allocations_from_sheet",
            status="ok",
            severity="ok",
            mode="sheet_sync",
            note="sheet_empty_noop",
            sheet_rows=0,
        )
        print("Token_Allocations empty; nothing to sync.")
        return

    if local_path.exists() and not FORCE_SYNC:
        try:
            local_df = pd.read_csv(local_path, dtype=str).fillna("")
        except Exception:
            local_df = pd.DataFrame()
        local_rows = len(local_df)
        sheet_rows = len(alloc_df)
        if local_rows > sheet_rows:
            _append_sync_status(
                step="B030_sync_token_allocations_from_sheet",
                status="ok",
                severity="ok",
                mode="sheet_sync_skipped_local_newer",
                note="local_newer_than_sheet",
                local_rows=local_rows,
                sheet_rows=sheet_rows,
            )
            print(
                {
                    "status": "skip",
                    "reason": "local_newer_than_sheet",
                    "local_rows": local_rows,
                    "sheet_rows": sheet_rows,
                }
            )
            return

    write_csv_with_compat(
        alloc_df,
        path_or_rel=OUT_REL,
        default_system="B",
        index=False,
        mirror_legacy=True,
    )
    _append_sync_status(
        step="B030_sync_token_allocations_from_sheet",
        status="ok",
        severity="ok",
        mode="sheet_sync",
        note="synced_from_sheet",
        local_rows=len(alloc_df),
        sheet_rows=len(alloc_df),
    )
    print({"status": "success", "rows": len(alloc_df), "out": str(resolved.live_path)})


if __name__ == "__main__":
    main()


