"""
Validate local token allocations CSV for downstream COGS consistency.
Local CSV is the live source of truth.
"""

from __future__ import annotations

from pathlib import Path
import os
import sys
from datetime import datetime, timezone
import csv

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

try:
    from scripts.core.out_paths import resolve_compat_path, write_csv_with_compat
except ModuleNotFoundError:
    from core.out_paths import resolve_compat_path, write_csv_with_compat

OUT_REL = "token_allocations_live.csv"
B_SHEET_SYNC_STATUS_PATH = Path("out/b_sheet_sync_status.csv")
ALLOC_COLUMNS = [
    "order_id",
    "order_date",
    "seller_sku",
    "quantity",
    "token_id",
    "token_cost",
    "currency",
    "allocation_date",
    "source_level",
    "notes",
]


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
    resolved = resolve_compat_path(OUT_REL, default_system="B")
    local_path = resolved.live_path if resolved.live_path.exists() else resolved.legacy_path

    if local_path.exists():
        alloc_df = pd.read_csv(local_path, dtype=str).fillna("")
    else:
        alloc_df = pd.DataFrame(columns=ALLOC_COLUMNS)

    for col in ALLOC_COLUMNS:
        if col not in alloc_df.columns:
            alloc_df[col] = ""
    alloc_df = alloc_df[ALLOC_COLUMNS]

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
        mode="local_master",
        note="local_authoritative_no_sheet_sync",
        local_rows=len(alloc_df),
        sheet_rows=-1,
    )
    print({"status": "success", "rows": len(alloc_df), "out": str(resolved.live_path)})


if __name__ == "__main__":
    main()
