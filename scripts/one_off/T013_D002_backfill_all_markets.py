"""
Backfill orders and financials across all participating marketplaces.

Flow:
- Load marketplaces from out/marketplace_participations.csv (is_participating == True).
- For each marketplace: run B001 with a fixed window and skip marker writes.
- After all marketplaces: run B002 (pending/backfill) once.
- Run B003 once for the posted-date window.
- Rebuild Order_Master (B004).
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable or "python"

MARKETPLACE_CSV = ROOT / "out" / "marketplace_participations.csv"
START_DATE = "2025-11-01T00:00:00Z"
EXCLUDE_COUNTRY = os.environ.get("D002_EXCLUDE_COUNTRY", "GB")


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_marketplaces() -> List[str]:
    if not MARKETPLACE_CSV.exists():
        return []
    df = pd.read_csv(MARKETPLACE_CSV, dtype=str)
    if df.empty or "marketplace_id" not in df.columns:
        return []
    if "is_participating" in df.columns:
        df["is_participating"] = df["is_participating"].astype(str).str.lower().isin(["true", "1", "yes"])
        df = df[df["is_participating"]]
    if EXCLUDE_COUNTRY and "country_code" in df.columns:
        df = df[df["country_code"].astype(str).str.upper() != EXCLUDE_COUNTRY.upper()]
    return [str(v) for v in df["marketplace_id"].tolist() if str(v)]


def _run_step(script_name: str, env: dict) -> None:
    script_path = ROOT / "scripts" / script_name
    print(f"[D002] running {script_name}")
    subprocess.run([PY, str(script_path)], check=True, env=env)


def main() -> None:
    markets = _load_marketplaces()
    if not markets:
        print({"status": "error", "error": "no marketplaces found", "path": str(MARKETPLACE_CSV)})
        return

    now = datetime.now(timezone.utc)
    posted_before = _iso(now - timedelta(minutes=5))

    base_env = os.environ.copy()
    base_env["ORDERS_CREATED_AFTER"] = START_DATE
    base_env["ORDERS_CREATED_BEFORE"] = posted_before
    base_env["ORDERS_SKIP_MARKER_WRITE"] = "1"

    # Orders backfill per marketplace
    for marketplace_id in markets:
        env = base_env.copy()
        env["MARKETPLACE_ID"] = marketplace_id
        _run_step("B001_run_orders_to_sheet.py", env)

    # Pending/official backfill once after all orders are present
    _run_step("B002_run_pending_orders_to_sheet.py", base_env.copy())

    # Financial events backfill (posted-date window)
    env_fin = base_env.copy()
    env_fin["FIN_L3_POSTED_AFTER"] = START_DATE
    env_fin["FIN_L3_POSTED_BEFORE"] = posted_before
    _run_step("B003_run_financial_events_level3.py", env_fin)

    # Rebuild order master
    _run_step("B004_build_order_master.py", base_env.copy())

    print({"status": "success", "marketplaces": len(markets), "start": START_DATE, "end": posted_before})


if __name__ == "__main__":
    main()

