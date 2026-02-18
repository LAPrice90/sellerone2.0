"""
Run C001-C006 in order, then gate on A015 and optionally publish C outputs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
LOCK_PATH = Path(os.environ.get("RUN_LOCK_PATH", ROOT / "out" / "run_cycle.lock"))
C_FORCE = os.environ.get("C_CYCLE_FORCE", "0").strip() == "1"
C_PUBLISH_ALLOW_WARN = os.environ.get("C_PUBLISH_ALLOW_WARN", "0").strip() == "1"
C_SKIP_PUBLISH = os.environ.get("C_SKIP_PUBLISH", "0").strip() == "1"


def _write_lock() -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = f"C|pid={os.getpid()}|start={datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}"
    LOCK_PATH.write_text(payload, encoding="utf-8")


def _acquire_lock() -> None:
    if LOCK_PATH.exists() and not C_FORCE:
        try:
            payload = LOCK_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            payload = "unknown"
        print(f"[C_cycle] lock exists ({payload}). Exiting to avoid overlap.")
        raise SystemExit(2)
    _write_lock()


def _release_lock() -> None:
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def _alert_summary() -> None:
    path = ROOT / "out" / "system_health_checklist.csv"
    if not path.exists():
        return
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return
    if "status" not in df.columns:
        return
    status = df["status"].str.lower()
    fail = int((status == "fail").sum())
    warn = int((status == "warn").sum())
    if fail or warn:
        print(f"[C_cycle] Alert: health_check FAIL={fail} WARN={warn}")
    else:
        print("[C_cycle] Alert: health_check OK")


RUN_ORDER = [
    "C007_run_storage_fee_report.py",
    "C008_run_long_term_storage_fee_report.py",
    "C009_run_inbound_shipment_contents.py",
    "C001_build_inbound_delivery_status.py",
    "C002_build_inbound_missing_units.py",
    "C003_build_inbound_cost_events.py",
    "C004_build_inbound_cost_allocations.py",
    "C005_allocate_inbound_costs_to_sku.py",
    "C006_build_token_maturity_window.py",
    "A015_build_system_health_check.py",
    "C010_publish_c_outputs.py",
]


def main() -> int:
    _acquire_lock()
    try:
        run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        for name in RUN_ORDER:
            if name == "C010_publish_c_outputs.py" and C_SKIP_PUBLISH:
                print(f"[C_cycle {run_id}] skip publish (C_SKIP_PUBLISH=1)")
                continue
            path = SCRIPTS / name
            if not path.exists():
                print(f"[C_cycle {run_id}] missing: {path}")
                return 1
            print(f"[C_cycle {run_id}] running: {name}")
            started = time.time()
            result = subprocess.run([sys.executable, str(path)])
            elapsed = time.time() - started
            if result.returncode != 0:
                if name == "A015_build_system_health_check.py":
                    if result.returncode == 2:
                        print(f"[C_cycle {run_id}] health_check FAIL - blocking publish")
                        return result.returncode
                    if result.returncode == 1:
                        print(f"[C_cycle {run_id}] health_check WARN")
                        _alert_summary()
                        if not C_PUBLISH_ALLOW_WARN:
                            print(f"[C_cycle {run_id}] WARN - skipping publish")
                            return 0
                        continue
                print(f"[C_cycle {run_id}] failed: {name} (code {result.returncode}) after {elapsed:.1f}s")
                return result.returncode
        return 0
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
