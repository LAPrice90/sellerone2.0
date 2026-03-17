"""
One-time 30-day catch-up runner for B001 -> B002 -> B003 -> B005 -> B004.

Uses env overrides for B001 (orders) and B003 (financial events) to avoid
changing markers outside the run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from scripts.core.script_locator import resolve_script_path
except ModuleNotFoundError:
    from scripts.core.script_locator import resolve_script_path


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable or "python"


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def run_step(script_name: str, env: dict) -> None:
    script_path = resolve_script_path(ROOT / "scripts", script_name)
    print(f"[catchup] running {script_name}")
    subprocess.run([PY, str(script_path)], check=True, env=env)


def main() -> None:
    now = datetime.now(timezone.utc)
    posted_after = iso(now - timedelta(days=30))
    posted_before = iso(now - timedelta(minutes=5))

    env = os.environ.copy()

    # B001: backdate orders pull 30 days.
    env_b001 = env.copy()
    env_b001["ORDERS_CREATED_AFTER"] = posted_after
    run_step("B001_run_orders_to_sheet.py", env_b001)

    # B002: update pending orders based on current L1.
    run_step("B002_run_pending_orders_to_sheet.py", env.copy())

    # B003: backdate financial events 30 days (no marker overwrite).
    env_b003 = env.copy()
    env_b003["FIN_L3_POSTED_AFTER"] = posted_after
    env_b003["FIN_L3_POSTED_BEFORE"] = posted_before
    run_step("B003_run_financial_events_level3.py", env_b003)

    # B005: backdate v2024 transactions 30 days (no marker overwrite).
    env_b005 = env.copy()
    env_b005["FIN_L5_POSTED_AFTER"] = posted_after
    env_b005["FIN_L5_POSTED_BEFORE"] = posted_before
    run_step("B005_run_financial_transactions_v2024.py", env_b005)

    # B004: rebuild master.
    run_step("B004_build_order_master.py", env.copy())

    print("[catchup] done")


if __name__ == "__main__":
    main()

