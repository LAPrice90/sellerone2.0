"""
Attempt to recover Level 1 gaps when L3 orphans exist.

Behavior:
- If out/l3_orphans.csv has rows, run a bounded lookback B001 pull (default 14 days).
- Rebuild Order_Master and re-check out/l3_orphans.csv directly.
- If orphans remain, log a notification row to out/orphan_recovery_alerts.csv.

This script is safe to run in the B cycle and is idempotent.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    from scripts.core.script_locator import resolve_script_path
except ModuleNotFoundError:
    from core.script_locator import resolve_script_path

L3_ORPHANS_PATH = ROOT / "out" / "l3_orphans.csv"
ALERTS_PATH = ROOT / "out" / "orphan_recovery_alerts.csv"
LAST_RUN_PATH = ROOT / "out" / "orphan_recovery_last_run.txt"
BACKFILL_DONE_PATH = ROOT / "out" / "orphan_recovery_backfill_done.flag"
MAX_DAYS = int(os.environ.get("ORPHAN_RECOVERY_MAX_DAYS", "14"))
MIN_INTERVAL_MIN = int(os.environ.get("ORPHAN_RECOVERY_MIN_INTERVAL_MIN", "60"))
BACKFILL_START = os.environ.get("ORPHAN_RECOVERY_BACKFILL_START", "").strip()
FORCE_FULL_BACKFILL = os.environ.get("ORPHAN_RECOVERY_FORCE_BACKFILL", "0").strip() == "1"
try:
    B001_TIMEOUT_SEC = int(float(os.environ.get("ORPHAN_RECOVERY_B001_TIMEOUT_SEC", "900") or "900"))
except Exception:
    B001_TIMEOUT_SEC = 900


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_orphans() -> pd.DataFrame:
    if not L3_ORPHANS_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(L3_ORPHANS_PATH, dtype=str)
    except Exception:
        return pd.DataFrame()


def _load_marketplace_ids(window_start: datetime | None = None, window_end: datetime | None = None) -> list[str]:
    # Root-cause guardrail:
    # Prefer marketplaces that actually have order activity in the target window.
    # This avoids looping through every participation marketplace and stalling B011.
    orders_path = ROOT / "out" / "orders_all.csv"
    if orders_path.exists():
        try:
            orders = pd.read_csv(orders_path, usecols=["marketplace_id", "purchase_date"], dtype=str).fillna("")
            if not orders.empty and "marketplace_id" in orders.columns:
                if window_start is not None and window_end is not None and "purchase_date" in orders.columns:
                    dates = pd.to_datetime(orders["purchase_date"], errors="coerce", utc=True)
                    mask = dates.notna()
                    if window_start is not None:
                        mask = mask & dates.ge(window_start)
                    if window_end is not None:
                        mask = mask & dates.le(window_end)
                    orders = orders.loc[mask].copy()
                ids = sorted(
                    {
                        str(v).strip()
                        for v in orders.get("marketplace_id", pd.Series(dtype=str)).tolist()
                        if str(v).strip()
                    }
                )
                if ids:
                    return ids
        except Exception:
            pass

    path = ROOT / "out" / "marketplace_participations.csv"
    if not path.exists():
        return [os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")]
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception:
        return [os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")]
    if df.empty or "marketplace_id" not in df.columns:
        return [os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")]
    ids = [str(v).strip() for v in df["marketplace_id"].tolist() if str(v).strip()]
    return sorted(set(ids)) or [os.environ.get("MARKETPLACE_ID", "A1F83G8C2ARO7P")]


def _load_anchor_end() -> datetime | None:
    orders_path = ROOT / "out" / "orders_all.csv"
    if not orders_path.exists():
        return None
    try:
        df = pd.read_csv(orders_path, usecols=["purchase_date"], dtype=str)
    except Exception:
        return None
    if df.empty or "purchase_date" not in df.columns:
        return None
    dates = pd.to_datetime(df["purchase_date"], errors="coerce", utc=True)
    if dates.notna().any():
        return dates.max().to_pydatetime()
    return None


def _should_throttle(now: datetime) -> bool:
    if not LAST_RUN_PATH.exists():
        return False
    try:
        last_txt = LAST_RUN_PATH.read_text(encoding="utf-8").strip()
        if not last_txt:
            return False
        last_dt = datetime.fromisoformat(last_txt.replace("Z", "+00:00"))
        age_min = (now - last_dt).total_seconds() / 60.0
        return age_min < MIN_INTERVAL_MIN
    except Exception:
        return False


def _mark_run(now: datetime) -> None:
    LAST_RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_PATH.write_text(_iso_z(now), encoding="utf-8")


def _append_alert(row: dict[str, str]) -> None:
    ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ALERTS_PATH.exists():
        existing = pd.read_csv(ALERTS_PATH, dtype=str)
        out = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    else:
        out = pd.DataFrame([row])
    out.to_csv(ALERTS_PATH, index=False)


def _run_step(script_name: str, env: dict[str, str]) -> int:
    result = subprocess.run([sys.executable, str(resolve_script_path(SCRIPTS, script_name))], env=env)
    return int(result.returncode)


def main() -> int:
    now = _now()
    orphans = _load_orphans()
    orphan_count = len(orphans)
    if orphan_count == 0:
        print("[B011] no L3 orphans found; skip recovery")
        return 0

    if _should_throttle(now):
        print("[B011] recovery throttled; recent run detected")
        return 0

    anchor_end = _load_anchor_end() or now
    window_end = anchor_end
    window_start = anchor_end - timedelta(days=max(MAX_DAYS, 1))

    earliest_orphan = None
    if "Date" in orphans.columns:
        try:
            dates = pd.to_datetime(orphans["Date"], errors="coerce", utc=True)
            if dates.notna().any():
                earliest_orphan = dates.min()
        except Exception:
            earliest_orphan = None

    env = os.environ.copy()
    # One-time full backfill if configured.
    use_backfill = False
    if BACKFILL_START and (FORCE_FULL_BACKFILL or not BACKFILL_DONE_PATH.exists()):
        try:
            backfill_start_dt = datetime.fromisoformat(BACKFILL_START.replace("Z", "+00:00"))
            if backfill_start_dt.tzinfo is None:
                backfill_start_dt = backfill_start_dt.replace(tzinfo=timezone.utc)
            window_start = backfill_start_dt
            use_backfill = True
        except Exception:
            use_backfill = False
    env["ORDERS_CREATED_AFTER"] = _iso_z(window_start)
    env["ORDERS_CREATED_BEFORE"] = _iso_z(window_end)
    env["ORDERS_SKIP_MARKER_WRITE"] = "1"

    # Throttle for large backfills to avoid 429.
    if use_backfill:
        env.setdefault("ORDERS_MAX_PER_PAGE", "50")
        env.setdefault("ORDERS_PAGE_SLEEP", "10")
        env.setdefault("ORDERS_SLEEP_SEC", "5")
        env.setdefault("ITEM_SLEEP_SEC", "2")

    marketplace_ids = _load_marketplace_ids(window_start=window_start, window_end=window_end)
    print(f"[B011] L3 orphans={orphan_count}; running B001 lookback {env['ORDERS_CREATED_AFTER']} -> {env['ORDERS_CREATED_BEFORE']} across {len(marketplace_ids)} marketplaces")

    timed_out_marketplaces: list[str] = []
    failed_marketplaces: list[str] = []
    for mp_id in marketplace_ids:
        env["MARKETPLACE_ID"] = mp_id
        print(f"[B011] marketplace {mp_id}")
        try:
            b001 = subprocess.run(
                [sys.executable, str(resolve_script_path(SCRIPTS, "B001_run_orders_to_sheet.py"))],
                env=env,
                timeout=max(B001_TIMEOUT_SEC, 1),
            )
        except subprocess.TimeoutExpired:
            timed_out_marketplaces.append(mp_id)
            _append_alert(
                {
                    "timestamp": _iso_z(_now()),
                    "orphan_count": str(orphan_count),
                    "window_start": env["ORDERS_CREATED_AFTER"],
                    "window_end": env["ORDERS_CREATED_BEFORE"],
                    "action": f"b001_timeout_marketplace_{mp_id}",
                }
            )
            print(f"[B011] timeout marketplace {mp_id} after {max(B001_TIMEOUT_SEC, 1)}s; continuing")
            continue
        if b001.returncode != 0:
            failed_marketplaces.append(mp_id)
            _append_alert(
                {
                    "timestamp": _iso_z(_now()),
                    "orphan_count": str(orphan_count),
                    "window_start": env["ORDERS_CREATED_AFTER"],
                    "window_end": env["ORDERS_CREATED_BEFORE"],
                    "action": f"b001_failed_marketplace_{mp_id}",
                }
            )
            print(f"[B011] failed marketplace {mp_id} rc={b001.returncode}; continuing")
            continue

    # Re-allocate tokens after recovery pulls so newly recovered orders
    # can receive COGS before rebuilding Order_Master.
    env_b007 = os.environ.copy()
    env_b007["B_CYCLE_QUIET"] = "1"
    rc_b007 = _run_step("B007_allocate_tokens_live.py", env_b007)
    if rc_b007 != 0:
        _append_alert(
            {
                "timestamp": _iso_z(_now()),
                "orphan_count": str(orphan_count),
                "window_start": env["ORDERS_CREATED_AFTER"],
                "window_end": env["ORDERS_CREATED_BEFORE"],
                "action": f"b007_failed_after_recovery_rc_{rc_b007}",
            }
        )
        _mark_run(now)
        return rc_b007

    env_b025 = os.environ.copy()
    env_b025["B_CYCLE_QUIET"] = "1"
    rc_b025 = _run_step("B025_build_token_cogs_ledger.py", env_b025)
    if rc_b025 != 0:
        _append_alert(
            {
                "timestamp": _iso_z(_now()),
                "orphan_count": str(orphan_count),
                "window_start": env["ORDERS_CREATED_AFTER"],
                "window_end": env["ORDERS_CREATED_BEFORE"],
                "action": f"b025_failed_after_recovery_rc_{rc_b025}",
            }
        )
        _mark_run(now)
        return rc_b025

    # Rebuild Order_Master after the backfill + token refresh.
    env_b004 = os.environ.copy()
    env_b004["ORDER_MASTER_INCREMENTAL"] = "0"
    env_b004["ORDER_MASTER_SKIP_SHEETS"] = "1"
    env_b004["B_CYCLE_QUIET"] = "1"
    rc_b004 = _run_step("B004_build_order_master.py", env_b004)
    if rc_b004 != 0:
        _append_alert(
            {
                "timestamp": _iso_z(_now()),
                "orphan_count": str(orphan_count),
                "window_start": env["ORDERS_CREATED_AFTER"],
                "window_end": env["ORDERS_CREATED_BEFORE"],
                "action": f"b004_failed_after_recovery_rc_{rc_b004}",
            }
        )
        _mark_run(now)
        return rc_b004

    # Re-check orphan file directly to avoid mid-cycle health-check side effects.
    remaining = len(_load_orphans())
    if remaining > 0:
        action = "orphans_remain"
    else:
        action = "cleared"

    if action != "cleared":
        if use_backfill:
            action = "orphans_remain_after_backfill"
        else:
            action = "orphans_remain_after_lookback"
        _append_alert(
            {
                "timestamp": _iso_z(now),
                "orphan_count": str(remaining),
                "window_start": env["ORDERS_CREATED_AFTER"],
                "window_end": env["ORDERS_CREATED_BEFORE"],
                "action": action,
                "earliest_orphan": _iso_z(earliest_orphan) if isinstance(earliest_orphan, datetime) else "",
            }
        )

    if timed_out_marketplaces:
        _append_alert(
            {
                "timestamp": _iso_z(_now()),
                "orphan_count": str(orphan_count),
                "window_start": env["ORDERS_CREATED_AFTER"],
                "window_end": env["ORDERS_CREATED_BEFORE"],
                "action": "b001_timeout_summary",
                "marketplaces": ",".join(timed_out_marketplaces),
            }
        )
    if failed_marketplaces:
        _append_alert(
            {
                "timestamp": _iso_z(_now()),
                "orphan_count": str(orphan_count),
                "window_start": env["ORDERS_CREATED_AFTER"],
                "window_end": env["ORDERS_CREATED_BEFORE"],
                "action": "b001_failure_summary",
                "marketplaces": ",".join(failed_marketplaces),
            }
        )

    _mark_run(now)
    if use_backfill:
        BACKFILL_DONE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BACKFILL_DONE_PATH.write_text(_iso_z(now), encoding="utf-8")
    print(f"[B011] recovery complete; status={action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


