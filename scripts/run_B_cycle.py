"""
Run B001-B005 in a continuous cycle with retries on failure.
"""

from __future__ import annotations

import os
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

RUN_ORDER = [
    "B001_run_orders_to_sheet.py",
    "B002_run_pending_orders_to_sheet.py",
    "B030_sync_token_allocations_from_sheet.py",
    "B007_allocate_tokens_live.py",
    "B025_build_token_cogs_ledger.py",
    "B004_build_order_master.py",
    "B011_recover_l3_orphans.py",
]

LOG_PATH = Path(os.environ.get("B_CYCLE_LOG_PATH", ROOT / "out" / "B_cycle.log"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOCK_PATH = Path(os.environ.get("RUN_LOCK_PATH", os.environ.get("B_CYCLE_LOCK_PATH", ROOT / "out" / "B_cycle.lock")))
LOCKS_DIR = ROOT / "out" / "locks"

MAX_RETRIES = int(os.environ.get("B_CYCLE_MAX_RETRIES", "5"))
BACKOFF_BASE = float(os.environ.get("B_CYCLE_BACKOFF_BASE", "2"))
CYCLE_SLEEP_SECONDS = float(os.environ.get("B_CYCLE_SLEEP_SECONDS", "30"))
B002_INTERVAL_MINUTES = float(os.environ.get("B002_INTERVAL_MINUTES", "60"))
B002_MAX_SECONDS_DEFAULT = os.environ.get("B002_MAX_SECONDS_DEFAULT", "1200")  # 20 minutes
B002_STATE_PATH = Path(os.environ.get("B002_STATE_PATH", ROOT / "out" / "B002_last_run.txt"))
REFUND_COLLECTION_INTERVAL_MINUTES = float(os.environ.get("REFUND_COLLECTION_INTERVAL_MINUTES", "240"))
REFUND_COLLECTION_STATE_PATH = Path(
    os.environ.get("REFUND_COLLECTION_STATE_PATH", ROOT / "out" / "refund_collection_last_run.txt")
)
LISTING_COLLECTION_ENABLED = os.environ.get("LISTING_COLLECTION_ENABLED", "1").strip() == "1"
LISTING_COLLECTION_STATE_PATH = Path(
    os.environ.get("LISTING_COLLECTION_STATE_PATH", ROOT / "out" / "listing_offer_collection_last_run.txt")
)
HEALTH_CHECKLIST_PATH = Path(os.environ.get("HEALTH_CHECKLIST_PATH", ROOT / "out" / "system_health_checklist.csv"))
HEALTH_CHECKLIST_B_PATH = Path(
    os.environ.get("HEALTH_CHECKLIST_B_PATH", ROOT / "out" / "cycle_alerts" / "checklist_B.csv")
)
B_SPLIT_CHECKLIST_PATH = Path(
    os.environ.get("B_SPLIT_CHECKLIST_PATH", ROOT / "out" / "cycle_alerts" / "checklist_B_split.csv")
)
B_SPLIT_HEALTH_MODE = os.environ.get("B_SPLIT_HEALTH_MODE", "shadow").strip().lower() or "shadow"
SPLIT_SHADOW_COMPARE_PATH = ROOT / "out" / "cycle_alerts" / "flow_selftest_compare.csv"
SPLIT_SHADOW_STATE_PATH = ROOT / "out" / "cycle_alerts" / "flow_selftest_state.json"
SPLIT_SHADOW_COMPARE_FIELDS = [
    "timestamp_utc",
    "cycle_start_utc",
    "cycle",
    "mode_requested",
    "mode_effective",
    "legacy_fail_count",
    "legacy_warn_count",
    "legacy_gate_block",
    "split_fail_count",
    "split_warn_count",
    "split_gate_block",
    "decision_match",
    "a_match_streak",
    "b_match_streak",
    "e_match_streak",
    "ready_for_cutover",
    "legacy_source",
    "split_source",
    "notes",
]
B_CYCLE_QUIET = os.environ.get("B_CYCLE_QUIET", "1").strip() == "1"
LOCK_FORCE = os.environ.get("B_CYCLE_FORCE", "0").strip() == "1"
B_RUN_ONCE = os.environ.get("B_RUN_ONCE", "0").strip() == "1"
MAINTENANCE_MODE = os.environ.get("B_CYCLE_MAINTENANCE_MODE", "0").strip() == "1"
MAINTENANCE_FLAG_PATH = Path(
    os.environ.get("B_CYCLE_MAINTENANCE_FLAG_PATH", LOCKS_DIR / "b_cycle.maintenance")
)
MAINTENANCE_REQUEST_PATH = Path(
    os.environ.get("MAINTENANCE_REQUEST_PATH", LOCKS_DIR / "maintenance.requested")
)
MAINTENANCE_READY_PATH = Path(
    os.environ.get("MAINTENANCE_READY_PATH", LOCKS_DIR / "maintenance.ready")
)
MAINTENANCE_ACTIVE_PATH = Path(
    os.environ.get("MAINTENANCE_ACTIVE_PATH", LOCKS_DIR / "maintenance.active")
)
MAINTENANCE_REASON = os.environ.get("B_CYCLE_MAINTENANCE_REASON", "").strip()
try:
    MAINTENANCE_ETA_MINUTES = int(float(os.environ.get("B_CYCLE_MAINTENANCE_ETA_MINUTES", "13") or "13"))
except Exception:
    MAINTENANCE_ETA_MINUTES = 13
try:
    MAINTENANCE_SLEEP_SECONDS = float(os.environ.get("B_CYCLE_MAINTENANCE_SLEEP_SECONDS", "900") or "900")
except Exception:
    MAINTENANCE_SLEEP_SECONDS = 900.0
CURRENT_CYCLE_ID = None


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _normalize_split_mode(value: object, *, default: str = "shadow") -> str:
    raw = str(value or "").strip().lower()
    if raw in {"legacy", "shadow", "split"}:
        return raw
    return default


def _load_split_shadow_state() -> dict:
    default = {
        "a_match_streak": 0,
        "b_match_streak": 0,
        "e_match_streak": 0,
        "ready_for_cutover": False,
        "updated_utc": "",
    }
    if not SPLIT_SHADOW_STATE_PATH.exists():
        return default
    try:
        payload = json.loads(SPLIT_SHADOW_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default
    if not isinstance(payload, dict):
        return default
    out = default.copy()
    out["a_match_streak"] = _safe_int(payload.get("a_match_streak", 0), 0)
    out["b_match_streak"] = _safe_int(payload.get("b_match_streak", 0), 0)
    out["e_match_streak"] = _safe_int(payload.get("e_match_streak", payload.get("h_clean_streak", 0)), 0)
    out["ready_for_cutover"] = bool(payload.get("ready_for_cutover", False))
    out["updated_utc"] = str(payload.get("updated_utc", "")).strip()
    return out


def _write_split_shadow_state(state: dict) -> None:
    payload = {
        "a_match_streak": _safe_int(state.get("a_match_streak", 0), 0),
        "b_match_streak": _safe_int(state.get("b_match_streak", 0), 0),
        "e_match_streak": _safe_int(state.get("e_match_streak", 0), 0),
        "ready_for_cutover": bool(state.get("ready_for_cutover", False)),
        "updated_utc": str(state.get("updated_utc", "")).strip(),
    }
    SPLIT_SHADOW_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_SHADOW_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _append_split_shadow_compare(row: dict) -> None:
    SPLIT_SHADOW_COMPARE_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = not SPLIT_SHADOW_COMPARE_PATH.exists() or SPLIT_SHADOW_COMPARE_PATH.stat().st_size == 0
    with SPLIT_SHADOW_COMPARE_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SPLIT_SHADOW_COMPARE_FIELDS)
        if need_header:
            writer.writeheader()
        payload = {k: str(row.get(k, "")).strip() for k in SPLIT_SHADOW_COMPARE_FIELDS}
        writer.writerow(payload)


def _effective_b_split_mode() -> str:
    requested = _normalize_split_mode(B_SPLIT_HEALTH_MODE, default="shadow")
    if requested != "shadow":
        return requested
    state = _load_split_shadow_state()
    if bool(state.get("ready_for_cutover", False)):
        _log("split_health auto_cutover active (ready_for_cutover=true)")
        return "split"
    return "shadow"


def _update_b_shadow_streak(match: bool) -> dict:
    state = _load_split_shadow_state()
    if match:
        state["b_match_streak"] = _safe_int(state.get("b_match_streak", 0), 0) + 1
    else:
        state["b_match_streak"] = 0
    a_streak = _safe_int(state.get("a_match_streak", 0), 0)
    b_streak = _safe_int(state.get("b_match_streak", 0), 0)
    e_streak = _safe_int(state.get("e_match_streak", 0), 0)
    ready_before = bool(state.get("ready_for_cutover", False))
    state["ready_for_cutover"] = a_streak >= 10 and b_streak >= 10 and e_streak >= 10
    state["updated_utc"] = _ts()
    _write_split_shadow_state(state)
    if state["ready_for_cutover"] and not ready_before:
        _log(
            "split_health ready_for_cutover=true "
            f"(a_match_streak={a_streak} b_match_streak={b_streak} e_match_streak={e_streak})"
        )
    return state


def _health_snapshot_counts(path: Path | None = None) -> tuple[int, int] | None:
    gate_path = path or (HEALTH_CHECKLIST_B_PATH if HEALTH_CHECKLIST_B_PATH.exists() else HEALTH_CHECKLIST_PATH)
    if not gate_path.exists():
        return None
    fail = 0
    warn = 0
    try:
        with gate_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = str(row.get("status", "")).strip().lower()
                if status == "fail":
                    fail += 1
                elif status == "warn":
                    warn += 1
        return (fail, warn)
    except Exception:
        return None


def _health_snapshot_details(path: Path = HEALTH_CHECKLIST_PATH) -> dict | None:
    if not path.exists():
        return None
    fail_checks: list[str] = []
    warn_checks: list[str] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                check = str(row.get("check", "")).strip()
                status = str(row.get("status", "")).strip().lower()
                if not check:
                    continue
                if status == "fail":
                    fail_checks.append(check)
                elif status == "warn":
                    warn_checks.append(check)
        mtime_utc = datetime.utcfromtimestamp(path.stat().st_mtime).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return {
            "health_snapshot_utc": mtime_utc,
            "path": str(path),
            "fail": len(fail_checks),
            "warn": len(warn_checks),
            "fail_checks": sorted(fail_checks),
            "warn_checks": sorted(warn_checks),
        }
    except Exception:
        return None


def _failed_health_checks(path: Path = HEALTH_CHECKLIST_PATH) -> set[str]:
    if not path.exists():
        return set()
    failed: set[str] = set()
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                check = str(row.get("check", "")).strip()
                status = str(row.get("status", "")).strip().lower()
                if check and status == "fail":
                    failed.add(check)
    except Exception:
        return set()
    return failed


def _mtime_seconds(path: Path) -> float | None:
    try:
        if not path.exists():
            return None
        return float(path.stat().st_mtime)
    except Exception:
        return None


def _run_health_check_once(
    health_path: Path,
    *,
    extra_args: list[str] | None = None,
    freshness_path: Path | None = None,
) -> tuple[int, bool]:
    target_path = freshness_path or HEALTH_CHECKLIST_PATH
    before_mtime = _mtime_seconds(target_path)
    cmd = [sys.executable, str(health_path)]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd)
    after_mtime = _mtime_seconds(target_path)
    fresh = after_mtime is not None and (before_mtime is None or after_mtime > before_mtime)
    return result.returncode, fresh


def _run_global_health_check_end_of_cycle(health_path: Path) -> int:
    _log("run A015_build_system_health_check.py end_of_cycle attempt 1")
    rc, health_snapshot_fresh = _run_health_check_once(health_path, freshness_path=HEALTH_CHECKLIST_PATH)
    stale_warn_promoted = False
    if rc == 1 and not health_snapshot_fresh:
        _log("health_check warn with stale snapshot - treating as fail")
        rc = 2
        stale_warn_promoted = True
    if rc == 2 and not stale_warn_promoted:
        failed_checks = _failed_health_checks(HEALTH_CHECKLIST_PATH)
        if failed_checks == {"l1_keys_missing_in_master"}:
            _log("health_check fail on l1_keys_missing_in_master only - run B004 repair and retry A015")
            repair = _run_with_retries(
                SCRIPTS / "B004_build_order_master.py",
                env_override={
                    "ORDER_MASTER_INCREMENTAL": "1",
                    "ORDER_MASTER_SKIP_SHEETS": "1",
                },
            )
            if repair == 0:
                _log("run A015_build_system_health_check.py end_of_cycle attempt 2")
                rc, health_snapshot_fresh = _run_health_check_once(
                    health_path,
                    freshness_path=HEALTH_CHECKLIST_PATH,
                )
                if rc == 1 and not health_snapshot_fresh:
                    _log("health_check warn with stale snapshot after retry - treating as fail")
                    rc = 2
    if rc == 0:
        _log("ok A015_build_system_health_check.py end_of_cycle")
    elif rc == 1:
        _log("warn A015_build_system_health_check.py end_of_cycle")
    else:
        _log(f"fail A015_build_system_health_check.py end_of_cycle rc={rc}")
    return rc


def _log_health_snapshot(*, path: Path, tag: str) -> dict | None:
    snapshot = _health_snapshot_details(path)
    if snapshot is None:
        _log(
            f'{tag} {{"event":"{tag}","cycle_start_utc":"{CURRENT_CYCLE_ID or "-"}","status":"missing_or_unreadable"}}'
        )
        return None
    payload = {
        "event": tag,
        "cycle_start_utc": CURRENT_CYCLE_ID or "-",
        "health_snapshot_utc": snapshot["health_snapshot_utc"],
        "fail": snapshot["fail"],
        "warn": snapshot["warn"],
        "fail_checks": snapshot["fail_checks"],
        "warn_checks": snapshot["warn_checks"],
        "path": snapshot.get("path", str(path)),
    }
    _log(f"{tag} {json.dumps(payload, separators=(',', ':'))}")
    return snapshot


def _run_health_check_end_of_cycle(*, mode_effective: str, mode_requested: str) -> int:
    health_path = SCRIPTS / "A015_build_system_health_check.py"
    if not health_path.exists():
        _log("skip A015_build_system_health_check.py (missing)")
        return 0
    mode = _normalize_split_mode(mode_effective, default="shadow")
    if mode == "legacy":
        rc = _run_global_health_check_end_of_cycle(health_path)
        _log_health_snapshot(path=HEALTH_CHECKLIST_B_PATH if HEALTH_CHECKLIST_B_PATH.exists() else HEALTH_CHECKLIST_PATH, tag="health_snapshot")
        return rc

    if mode == "split":
        _log("run A015_build_system_health_check.py profile=b end_of_cycle")
        rc, split_fresh = _run_health_check_once(
            health_path,
            extra_args=["--profile", "b", "--checklist-path", str(B_SPLIT_CHECKLIST_PATH), "--no-toast"],
            freshness_path=B_SPLIT_CHECKLIST_PATH,
        )
        if rc == 1 and not split_fresh:
            _log("split_health warn with stale snapshot - treating as fail")
            rc = 2
        if rc == 0:
            _log("ok A015_build_system_health_check.py profile=b end_of_cycle")
        elif rc == 1:
            _log("warn A015_build_system_health_check.py profile=b end_of_cycle")
        else:
            _log(f"fail A015_build_system_health_check.py profile=b end_of_cycle rc={rc}")
        _log_health_snapshot(path=B_SPLIT_CHECKLIST_PATH, tag="split_health_snapshot")
        return rc

    # shadow mode: keep legacy result, run split candidate for comparison.
    rc_legacy = _run_global_health_check_end_of_cycle(health_path)
    legacy_path = HEALTH_CHECKLIST_B_PATH if HEALTH_CHECKLIST_B_PATH.exists() else HEALTH_CHECKLIST_PATH
    _log_health_snapshot(path=legacy_path, tag="health_snapshot")
    _log("run A015_build_system_health_check.py profile=b shadow_compare")
    rc_split, split_fresh = _run_health_check_once(
        health_path,
        extra_args=["--profile", "b", "--checklist-path", str(B_SPLIT_CHECKLIST_PATH), "--no-toast"],
        freshness_path=B_SPLIT_CHECKLIST_PATH,
    )
    if rc_split == 1 and not split_fresh:
        _log("split_health warn with stale snapshot - treating as fail")
        rc_split = 2
    split_snapshot = _log_health_snapshot(path=B_SPLIT_CHECKLIST_PATH, tag="split_health_snapshot")
    legacy_counts = _health_snapshot_counts(legacy_path)
    split_counts = _health_snapshot_counts(B_SPLIT_CHECKLIST_PATH)
    legacy_fail = legacy_counts[0] if legacy_counts is not None else -1
    legacy_warn = legacy_counts[1] if legacy_counts is not None else -1
    split_fail = split_counts[0] if split_counts is not None else -1
    split_warn = split_counts[1] if split_counts is not None else -1
    legacy_gate_block = bool(legacy_counts is not None and legacy_counts[0] > 0)
    split_gate_block = bool(split_counts is not None and split_counts[0] > 0)
    decision_match = legacy_gate_block == split_gate_block
    state = _update_b_shadow_streak(decision_match)
    _append_split_shadow_compare(
        {
            "timestamp_utc": _ts(),
            "cycle_start_utc": CURRENT_CYCLE_ID or "-",
            "cycle": "B",
            "mode_requested": mode_requested,
            "mode_effective": mode,
            "legacy_fail_count": "" if legacy_fail < 0 else str(legacy_fail),
            "legacy_warn_count": "" if legacy_warn < 0 else str(legacy_warn),
            "legacy_gate_block": "1" if legacy_gate_block else "0",
            "split_fail_count": "" if split_fail < 0 else str(split_fail),
            "split_warn_count": "" if split_warn < 0 else str(split_warn),
            "split_gate_block": "1" if split_gate_block else "0",
            "decision_match": "1" if decision_match else "0",
            "a_match_streak": str(_safe_int(state.get("a_match_streak", 0), 0)),
            "b_match_streak": str(_safe_int(state.get("b_match_streak", 0), 0)),
            "e_match_streak": str(_safe_int(state.get("e_match_streak", 0), 0)),
            "ready_for_cutover": "1" if bool(state.get("ready_for_cutover", False)) else "0",
            "legacy_source": legacy_path.name,
            "split_source": B_SPLIT_CHECKLIST_PATH.name,
            "notes": f"split_rc={rc_split};split_fresh={'1' if split_fresh else '0'}",
        }
    )
    _log(
        "split_shadow_compare "
        f"legacy_fail={legacy_fail} legacy_warn={legacy_warn} "
        f"split_fail={split_fail} split_warn={split_warn} "
        f"decision_match={'1' if decision_match else '0'} "
        f"a_match_streak={_safe_int(state.get('a_match_streak', 0), 0)} "
        f"b_match_streak={_safe_int(state.get('b_match_streak', 0), 0)} "
        f"e_match_streak={_safe_int(state.get('e_match_streak', 0), 0)} "
        f"ready_for_cutover={'1' if bool(state.get('ready_for_cutover', False)) else '0'}"
    )
    if split_snapshot is None:
        _log("split_shadow_compare split snapshot missing_or_unreadable")
    return rc_legacy


def _run_with_retries(path: Path, env_override: dict | None = None) -> int:
    attempt = 0
    while True:
        attempt += 1
        _log(f"run {path.name} attempt {attempt}")
        env = os.environ.copy()
        if B_CYCLE_QUIET:
            env["B_CYCLE_QUIET"] = "1"
        if env_override:
            env.update(env_override)
        started = time.time()
        print(f"[B_cycle] start {path.name}")
        result = subprocess.run([sys.executable, str(path)], env=env)
        print(f"[B_cycle] end {path.name} rc={result.returncode} elapsed={time.time() - started:.1f}s")
        if result.returncode == 0:
            _log(f"ok {path.name}")
            return 0
        if MAX_RETRIES > 0 and attempt >= MAX_RETRIES:
            print(f"[B_cycle] failed after {attempt} attempts: {path.name}")
            _log(f"fail {path.name} after {attempt}")
            return result.returncode
        backoff = min(BACKOFF_BASE ** attempt, 60)
        print(f"[B_cycle] retry {attempt} for {path.name} in {backoff:.1f}s")
        _log(f"retry {path.name} in {backoff:.1f}s")
        time.sleep(backoff)


def _run_refund_collection_if_due() -> None:
    if REFUND_COLLECTION_INTERVAL_MINUTES <= 0:
        _log("skip refunds_adjustments collection (interval disabled)")
        return
    if REFUND_COLLECTION_STATE_PATH.exists():
        try:
            last_ts = REFUND_COLLECTION_STATE_PATH.read_text(encoding="utf-8").strip()
            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            age_sec = (datetime.utcnow() - last_dt.replace(tzinfo=None)).total_seconds()
            if age_sec < REFUND_COLLECTION_INTERVAL_MINUTES * 60:
                _log(f"skip refunds_adjustments collection (last run {age_sec:.0f}s ago)")
                return
        except Exception:
            pass

    path = ROOT / "run_api_collection.py"
    if not path.exists():
        _log("skip refunds_adjustments collection (run_api_collection.py missing)")
        return

    _log("run refunds_adjustments collection attempt 1")
    env = os.environ.copy()
    env["API_COLLECTION_DATASETS"] = "refunds_adjustments"
    if B_CYCLE_QUIET:
        env["B_CYCLE_QUIET"] = "1"
    started = time.time()
    print("[B_cycle] start refunds_adjustments collection")
    result = subprocess.run([sys.executable, str(path)], env=env)
    print(
        "[B_cycle] end refunds_adjustments collection "
        f"rc={result.returncode} elapsed={time.time() - started:.1f}s"
    )
    if result.returncode == 0:
        _log("ok refunds_adjustments collection")
        try:
            REFUND_COLLECTION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            REFUND_COLLECTION_STATE_PATH.write_text(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), encoding="utf-8")
        except Exception:
            pass
    elif result.returncode == 3:
        _log("skip refunds_adjustments collection (spapi lock busy)")
    else:
        _log(f"fail refunds_adjustments collection rc={result.returncode}")


def _run_listing_offer_collection_if_due() -> None:
    if not LISTING_COLLECTION_ENABLED:
        _log("skip listing_offer collection (disabled)")
        return

    now_utc = datetime.utcnow()
    if LISTING_COLLECTION_STATE_PATH.exists():
        try:
            last_ts = LISTING_COLLECTION_STATE_PATH.read_text(encoding="utf-8").strip()
            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            if last_dt.date() >= now_utc.date():
                _log(f"skip listing_offer collection (already ran for {now_utc.date().isoformat()})")
                return
        except Exception:
            pass

    path = ROOT / "run_api_collection.py"
    if not path.exists():
        _log("skip listing_offer collection (run_api_collection.py missing)")
        return

    _log("run listing_offer collection attempt 1")
    env = os.environ.copy()
    env["API_COLLECTION_DATASETS"] = "listing_offer"
    if B_CYCLE_QUIET:
        env["B_CYCLE_QUIET"] = "1"
    started = time.time()
    print("[B_cycle] start listing_offer collection")
    result = subprocess.run([sys.executable, str(path)], env=env)
    print(
        "[B_cycle] end listing_offer collection "
        f"rc={result.returncode} elapsed={time.time() - started:.1f}s"
    )
    if result.returncode == 0:
        _log("ok listing_offer collection")
        try:
            LISTING_COLLECTION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            LISTING_COLLECTION_STATE_PATH.write_text(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), encoding="utf-8")
        except Exception:
            pass
    elif result.returncode == 3:
        _log("skip listing_offer collection (spapi lock busy)")
    else:
        _log(f"fail listing_offer collection rc={result.returncode}")


def main() -> int:
    _acquire_lock()
    try:
        return _main_loop()
    finally:
        _release_lock()


def _main_loop() -> int:
    for name in RUN_ORDER:
        path = SCRIPTS / name
        if not path.exists():
            print(f"[B_cycle] missing: {path}")
            return 1

    global CURRENT_CYCLE_ID
    while True:
        _pause_for_maintenance_at_boundary("before cycle start")
        CURRENT_CYCLE_ID = _ts()
        mode_requested = _normalize_split_mode(B_SPLIT_HEALTH_MODE, default="shadow")
        mode_effective = _effective_b_split_mode()
        _log(f"split_health mode_requested={mode_requested} mode_effective={mode_effective}")
        for name in RUN_ORDER:
            path = SCRIPTS / name
            print(f"[B_cycle] running: {name}")
            if name == "B001_run_orders_to_sheet.py":
                # Default to our offer price for Level 1 unless explicitly disabled.
                env_override = {}
                if "LEVEL1_USE_OWN_OFFER_PRICE" not in os.environ:
                    env_override["LEVEL1_USE_OWN_OFFER_PRICE"] = "1"
                if "PRICE_API_SLEEP_SEC" not in os.environ:
                    env_override["PRICE_API_SLEEP_SEC"] = "31"
                _run_with_retries(path, env_override=env_override)
                continue
            if name == "B002_run_pending_orders_to_sheet.py":
                if B002_INTERVAL_MINUTES > 0 and B002_STATE_PATH.exists():
                    try:
                        last_ts = B002_STATE_PATH.read_text(encoding="utf-8").strip()
                        last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                        age_sec = (datetime.utcnow() - last_dt.replace(tzinfo=None)).total_seconds()
                        if age_sec < B002_INTERVAL_MINUTES * 60:
                            _log(f"skip {name} (last run {age_sec:.0f}s ago)")
                            continue
                    except Exception:
                        pass
                env_override = {}
                if "B002_MAX_SECONDS" not in os.environ:
                    env_override["B002_MAX_SECONDS"] = B002_MAX_SECONDS_DEFAULT
                rc = _run_with_retries(path, env_override=env_override)
                if rc == 0:
                    try:
                        B002_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                        B002_STATE_PATH.write_text(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), encoding="utf-8")
                    except Exception:
                        pass
                continue
            if name == "B004_build_order_master.py":
                env_override = {}
                if "ORDER_MASTER_INCREMENTAL" not in os.environ:
                    env_override["ORDER_MASTER_INCREMENTAL"] = "1"
                _run_with_retries(path, env_override=env_override)
                continue
            _run_with_retries(path)
        _run_listing_offer_collection_if_due()
        _run_refund_collection_if_due()
        # Publish once per cycle if running quiet mode (no partial sheet updates).
        if B_CYCLE_QUIET:
            # Gate publish using the last completed health snapshot.
            if mode_effective == "split":
                gate_path = B_SPLIT_CHECKLIST_PATH
            else:
                gate_path = HEALTH_CHECKLIST_B_PATH if HEALTH_CHECKLIST_B_PATH.exists() else HEALTH_CHECKLIST_PATH
            snapshot = _health_snapshot_counts(gate_path)
            gate_block = False
            if snapshot is None:
                _log("health_gate snapshot missing or unreadable - allow publish")
            else:
                fail_count, warn_count = snapshot
                _log(f"health_gate snapshot FAIL={fail_count} WARN={warn_count} source={gate_path.name}")
                if fail_count > 0:
                    gate_block = True

            if gate_block:
                print("[B_cycle] health_gate snapshot FAIL - skipping publish")
                _log("health_gate snapshot FAIL - skip publish")
            else:
                print("[B_cycle] publish: Order_Master")
                _log("publish Order_Master")
                _run_with_retries(
                    SCRIPTS / "B004_build_order_master.py",
                    env_override={
                        "ORDER_MASTER_SKIP_SHEETS": "0",
                        "B_CYCLE_QUIET": "0",
                        "ORDER_MASTER_INCREMENTAL": "1",
                    },
                )
                print("[B_cycle] publish: P&L")
                _log("publish P&L")
                _run_with_retries(
                    SCRIPTS / "D001_build_pnl_daily.py",
                    env_override={
                        "PNL_PUBLISH": "1",
                        "PNL_SUMMARY_ONLY": "1",
                        "PNL_WRITE_DAILY": "0",
                        "PNL_MONTHLY_TABS": "0",
                        "PNL_FORMAT_SHEETS": "0",
                        "PNL_SHEETS_MAX_RETRIES": "8",
                        "PNL_SHEETS_BACKOFF": "5.0",
                        "B_CYCLE_QUIET": "0",
                    },
                )
            _run_health_check_end_of_cycle(mode_effective=mode_effective, mode_requested=mode_requested)
        if CYCLE_SLEEP_SECONDS > 0:
            print(f"[B_cycle] cycle sleep {CYCLE_SLEEP_SECONDS:.0f}s")
            _log(f"cycle sleep {CYCLE_SLEEP_SECONDS:.0f}s")
            time.sleep(CYCLE_SLEEP_SECONDS)
        if B_RUN_ONCE:
            _log("run_once enabled, exiting after single cycle")
            break
        _pause_for_maintenance_at_boundary("after cycle end")


def _log(msg: str) -> None:
    ts = _ts()
    cycle = CURRENT_CYCLE_ID or "-"
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{ts} [{cycle}] {msg}\n")


def _maintenance_requested() -> bool:
    if MAINTENANCE_MODE:
        return True
    return MAINTENANCE_FLAG_PATH.exists() or MAINTENANCE_REQUEST_PATH.exists()


def _maintenance_reason() -> str:
    if MAINTENANCE_REASON:
        return MAINTENANCE_REASON
    if not MAINTENANCE_FLAG_PATH.exists():
        return ""
    try:
        text = MAINTENANCE_FLAG_PATH.read_text(encoding="utf-8").strip()
        first = text.splitlines()[0].strip() if text else ""
        return first
    except Exception:
        return ""


def _pause_for_maintenance_at_boundary(context: str) -> None:
    if not _maintenance_requested():
        return
    MAINTENANCE_READY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ready_payload = f"B_READY|pid={os.getpid()}|ts={_ts()}|context={context}\n"
    try:
        MAINTENANCE_READY_PATH.write_text(ready_payload, encoding="utf-8")
    except Exception:
        pass
    _log(f"maintenance ready ({context}); current cycle finished")
    while _maintenance_requested() or MAINTENANCE_ACTIVE_PATH.exists():
        reason = _maintenance_reason()
        reason_suffix = f"; reason={reason}" if reason else ""
        msg = (
            f"maintenance pause ({context}); sleeping {MAINTENANCE_SLEEP_SECONDS:.0f}s, "
            f"check back in {MAINTENANCE_ETA_MINUTES} minutes{reason_suffix}"
        )
        print(f"[B_cycle] {msg}")
        _log(msg)
        time.sleep(max(MAINTENANCE_SLEEP_SECONDS, 1.0))
    try:
        if MAINTENANCE_READY_PATH.exists():
            MAINTENANCE_READY_PATH.unlink()
    except Exception:
        pass
    _log(f"maintenance clear ({context}); resuming cycle")


def _acquire_lock() -> None:
    if LOCK_FORCE:
        _write_lock()
        return
    if LOCK_PATH.exists():
        try:
            data = LOCK_PATH.read_text(encoding="utf-8").strip().splitlines()
            first = data[0] if data else ""
            if "pid=" in first:
                pid = int(first.split("pid=")[-1].split("|")[0])
            else:
                pid = int(first) if first else None
        except Exception:
            pid = None
        if pid and _pid_alive(pid):
            print(f"[B_cycle] lock exists (pid {pid}). Exiting to avoid double-run.")
            raise SystemExit(1)
    _write_lock()


def _write_lock() -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = f"B|pid={os.getpid()}|start={_ts()}\n"
    LOCK_PATH.write_text(payload, encoding="utf-8")


def _release_lock() -> None:
    try:
        if not LOCK_PATH.exists():
            return
        data = LOCK_PATH.read_text(encoding="utf-8").strip().splitlines()
        first = data[0] if data else ""
        if "pid=" in first:
            pid = int(first.split("pid=")[-1].split("|")[0])
        else:
            pid = int(first) if first else None
        if pid == os.getpid():
            LOCK_PATH.unlink()
    except Exception:
        pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
