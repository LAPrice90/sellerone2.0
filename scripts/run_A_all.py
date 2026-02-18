"""
Run A001-A004 in order.
"""

from __future__ import annotations

import os
import csv
import json
import subprocess
import sys
import time
import signal
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
LOCK_PATH = Path(os.environ.get("RUN_LOCK_PATH", ROOT / "out" / "run_cycle.lock"))
A_FORCE = os.environ.get("A_CYCLE_FORCE", "0").strip() == "1"
A_STEAL_LOCK = os.environ.get("A_CYCLE_STEAL_LOCK", "0").strip() == "1"
LOCKS_DIR = ROOT / "out" / "locks"
B_CYCLE_LOCK_PATH = Path(os.environ.get("B_CYCLE_LOCK_PATH", ROOT / "out" / "B_cycle.lock"))
MAINTENANCE_REQUEST_PATH = Path(
    os.environ.get("MAINTENANCE_REQUEST_PATH", LOCKS_DIR / "maintenance.requested")
)
MAINTENANCE_READY_PATH = Path(
    os.environ.get("MAINTENANCE_READY_PATH", LOCKS_DIR / "maintenance.ready")
)
MAINTENANCE_ACTIVE_PATH = Path(
    os.environ.get("MAINTENANCE_ACTIVE_PATH", LOCKS_DIR / "maintenance.active")
)
MAINTENANCE_REASON = os.environ.get("MAINTENANCE_REASON", "A_cycle_run").strip() or "A_cycle_run"
HEALTH_CHECKLIST_PATH = Path(os.environ.get("HEALTH_CHECKLIST_PATH", ROOT / "out" / "system_health_checklist.csv"))
A_SPLIT_CHECKLIST_PATH = Path(
    os.environ.get("A_SPLIT_CHECKLIST_PATH", ROOT / "out" / "cycle_alerts" / "checklist_A_split.csv")
)
A_SPLIT_HEALTH_MODE = os.environ.get("A_SPLIT_HEALTH_MODE", "shadow").strip().lower() or "shadow"
FLOW_SELFTEST_COMPARE_PATH = ROOT / "out" / "cycle_alerts" / "flow_selftest_compare.csv"
FLOW_SELFTEST_STATE_PATH = ROOT / "out" / "cycle_alerts" / "flow_selftest_state.json"
FLOW_SELFTEST_COMPARE_FIELDS = [
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
# Disabled by design: A cycle must not auto-start B cycle on exit.
ENSURE_B_AFTER_A = False
try:
    MAINTENANCE_READY_TIMEOUT_SECONDS = int(float(os.environ.get("MAINTENANCE_READY_TIMEOUT_SECONDS", "3600") or "3600"))
except Exception:
    MAINTENANCE_READY_TIMEOUT_SECONDS = 3600
try:
    MAINTENANCE_READY_POLL_SECONDS = float(os.environ.get("MAINTENANCE_READY_POLL_SECONDS", "5") or "5")
except Exception:
    MAINTENANCE_READY_POLL_SECONDS = 5.0


def _parse_lock_pid(payload: str) -> int | None:
    parts = [p.strip() for p in str(payload).split("|") if p.strip()]
    for part in parts:
        if part.startswith("pid="):
            raw = part.split("=", 1)[1].strip()
            try:
                return int(raw)
            except Exception:
                return None
    return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _terminate_pid(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        return not _pid_alive(pid)
    for _ in range(10):
        if not _pid_alive(pid):
            return True
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except Exception:
        return not _pid_alive(pid)
    for _ in range(10):
        if not _pid_alive(pid):
            return True
        time.sleep(0.2)
    return not _pid_alive(pid)


def _write_lock() -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = f"A|pid={os.getpid()}|start={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    LOCK_PATH.write_text(payload, encoding="utf-8")


def _acquire_lock() -> None:
    if LOCK_PATH.exists() and not A_FORCE:
        try:
            payload = LOCK_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            payload = "unknown"
        pid = _parse_lock_pid(payload)
        if pid is not None and not _pid_alive(pid):
            print(f"[A_all] stale lock detected (pid {pid} not running). Clearing lock.")
            _release_lock()
            _write_lock()
            return
        if pid is not None and A_STEAL_LOCK:
            print(f"[A_all] lock held by pid {pid}. A_CYCLE_STEAL_LOCK=1, attempting takeover.")
            if _terminate_pid(pid):
                _release_lock()
                _write_lock()
                print(f"[A_all] lock takeover success (terminated pid {pid}).")
                return
            print(f"[A_all] lock takeover failed (pid {pid} still running).")
        print(f"[A_all] lock exists ({payload}). Exiting to avoid overlap.")
        raise SystemExit(2)
    _write_lock()


def _release_lock() -> None:
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def _request_maintenance() -> None:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if MAINTENANCE_READY_PATH.exists():
            MAINTENANCE_READY_PATH.unlink()
    except Exception:
        pass
    payload = f"requested_by=A|pid={os.getpid()}|ts={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}|reason={MAINTENANCE_REASON}\n"
    MAINTENANCE_REQUEST_PATH.write_text(payload, encoding="utf-8")


def _b_cycle_running() -> bool:
    if not B_CYCLE_LOCK_PATH.exists():
        return False
    try:
        payload = B_CYCLE_LOCK_PATH.read_text(encoding="utf-8")
    except Exception:
        return True
    pid = _parse_lock_pid(payload)
    if pid is None:
        return True
    return _pid_alive(pid)


def _wait_for_b_maintenance_ready() -> str:
    started = time.time()
    while True:
        if MAINTENANCE_READY_PATH.exists():
            return "ready_signal"
        if not _b_cycle_running():
            return "b_not_running"
        elapsed = time.time() - started
        if elapsed > MAINTENANCE_READY_TIMEOUT_SECONDS:
            raise TimeoutError(
                f"Timed out waiting for B maintenance ready after {MAINTENANCE_READY_TIMEOUT_SECONDS}s"
            )
        print(
            f"[A_all] waiting for B cycle boundary... elapsed={elapsed:.0f}s "
            f"(poll {MAINTENANCE_READY_POLL_SECONDS:.0f}s)"
        )
        time.sleep(max(MAINTENANCE_READY_POLL_SECONDS, 1.0))


def _activate_maintenance() -> None:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    payload = f"active_by=A|pid={os.getpid()}|ts={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}|reason={MAINTENANCE_REASON}\n"
    MAINTENANCE_ACTIVE_PATH.write_text(payload, encoding="utf-8")


def _clear_maintenance() -> None:
    for path in (MAINTENANCE_ACTIVE_PATH, MAINTENANCE_REQUEST_PATH, MAINTENANCE_READY_PATH):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


def _clear_stale_b_lock_if_any() -> None:
    if not B_CYCLE_LOCK_PATH.exists():
        return
    try:
        payload = B_CYCLE_LOCK_PATH.read_text(encoding="utf-8")
    except Exception:
        payload = ""
    pid = _parse_lock_pid(payload)
    if pid is not None and _pid_alive(pid):
        return
    try:
        B_CYCLE_LOCK_PATH.unlink()
        print("[A_all] cleared stale B lock")
    except Exception:
        pass


def _ensure_b_cycle_running_after_a() -> None:
    if not ENSURE_B_AFTER_A:
        return
    if _b_cycle_running():
        print("[A_all] B cycle already running")
        return
    _clear_stale_b_lock_if_any()
    cmd = [sys.executable, str(SCRIPTS / "run_B_cycle.py")]
    kwargs = {
        "cwd": str(ROOT),
        "env": os.environ.copy(),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **kwargs)
        print(f"[A_all] started B cycle after A (pid {proc.pid})")
    except Exception as exc:
        print(f"[A_all] WARN could not restart B cycle after A: {exc}")


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


def _load_flow_selftest_state() -> dict:
    default = {
        "a_match_streak": 0,
        "b_match_streak": 0,
        "e_match_streak": 0,
        "ready_for_cutover": False,
        "updated_utc": "",
    }
    if not FLOW_SELFTEST_STATE_PATH.exists():
        return default
    try:
        payload = json.loads(FLOW_SELFTEST_STATE_PATH.read_text(encoding="utf-8"))
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


def _write_flow_selftest_state(state: dict) -> None:
    payload = {
        "a_match_streak": _safe_int(state.get("a_match_streak", 0), 0),
        "b_match_streak": _safe_int(state.get("b_match_streak", 0), 0),
        "e_match_streak": _safe_int(state.get("e_match_streak", 0), 0),
        "ready_for_cutover": bool(state.get("ready_for_cutover", False)),
        "updated_utc": str(state.get("updated_utc", "")).strip(),
    }
    FLOW_SELFTEST_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLOW_SELFTEST_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _append_flow_selftest_compare(row: dict) -> None:
    FLOW_SELFTEST_COMPARE_PATH.parent.mkdir(parents=True, exist_ok=True)
    need_header = not FLOW_SELFTEST_COMPARE_PATH.exists() or FLOW_SELFTEST_COMPARE_PATH.stat().st_size == 0
    with FLOW_SELFTEST_COMPARE_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FLOW_SELFTEST_COMPARE_FIELDS)
        if need_header:
            writer.writeheader()
        payload = {k: str(row.get(k, "")).strip() for k in FLOW_SELFTEST_COMPARE_FIELDS}
        writer.writerow(payload)


def _effective_a_split_mode() -> str:
    requested = _normalize_split_mode(A_SPLIT_HEALTH_MODE, default="shadow")
    if requested != "shadow":
        return requested
    state = _load_flow_selftest_state()
    if bool(state.get("ready_for_cutover", False)):
        print("[A_all] split_health auto_cutover active (ready_for_cutover=true)")
        return "split"
    return "shadow"


def _update_a_shadow_streak(match: bool) -> dict:
    state = _load_flow_selftest_state()
    if match:
        state["a_match_streak"] = _safe_int(state.get("a_match_streak", 0), 0) + 1
    else:
        state["a_match_streak"] = 0
    a_streak = _safe_int(state.get("a_match_streak", 0), 0)
    b_streak = _safe_int(state.get("b_match_streak", 0), 0)
    e_streak = _safe_int(state.get("e_match_streak", 0), 0)
    ready_before = bool(state.get("ready_for_cutover", False))
    state["ready_for_cutover"] = a_streak >= 10 and b_streak >= 10 and e_streak >= 10
    state["updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_flow_selftest_state(state)
    if state["ready_for_cutover"] and not ready_before:
        print(
            "[A_all] split_health ready_for_cutover=true "
            f"(a_match_streak={a_streak} b_match_streak={b_streak} e_match_streak={e_streak})"
        )
    return state


def _health_counts(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return None
    if "status" not in df.columns:
        return None
    status = df["status"].astype(str).str.lower()
    return int(status.eq("fail").sum()), int(status.eq("warn").sum())


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
        print(f"[A_all] Alert: health_check FAIL={fail} WARN={warn}")
    else:
        print("[A_all] Alert: health_check OK")


def _failed_health_checks() -> set[str]:
    path = ROOT / "out" / "system_health_checklist.csv"
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return set()
    if "check" not in df.columns or "status" not in df.columns:
        return set()
    failed = df[df["status"].str.lower() == "fail"]["check"].astype(str)
    return set(failed.tolist())


def _mtime_seconds(path: Path) -> float | None:
    try:
        if not path.exists():
            return None
        return float(path.stat().st_mtime)
    except Exception:
        return None


def _run_a015_with_freshness(
    path: Path,
    env: dict[str, str],
    *,
    extra_args: list[str] | None = None,
    freshness_path: Path | None = None,
) -> tuple[subprocess.CompletedProcess, bool]:
    target = freshness_path or HEALTH_CHECKLIST_PATH
    before_mtime = _mtime_seconds(target)
    cmd = [sys.executable, str(path)]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, env=env)
    after_mtime = _mtime_seconds(target)
    fresh = after_mtime is not None and (before_mtime is None or after_mtime > before_mtime)
    return result, fresh


def _run_a015_global_gate(run_id: str, path: Path, env: dict[str, str]) -> int:
    result, health_snapshot_fresh = _run_a015_with_freshness(path, env, freshness_path=HEALTH_CHECKLIST_PATH)
    if result.returncode == 2:
        failed_checks = _failed_health_checks()
        if failed_checks == {"l1_keys_missing_in_master"}:
            print(
                f"[A_all {run_id}] health_check FAIL on l1_keys_missing_in_master only; "
                "running B004 repair and retrying A015"
            )
            repair_env = os.environ.copy()
            if "ORDER_MASTER_WRITE_SHEETS" not in repair_env:
                repair_env["ORDER_MASTER_WRITE_SHEETS"] = "0"
            repair = subprocess.run([sys.executable, str(SCRIPTS / "B004_build_order_master.py")], env=repair_env)
            if repair.returncode == 0:
                result, health_snapshot_fresh = _run_a015_with_freshness(path, env, freshness_path=HEALTH_CHECKLIST_PATH)
    if result.returncode == 1 and not health_snapshot_fresh:
        print(f"[A_all {run_id}] health_check WARN with stale snapshot - treating as FAIL")
        return 2
    if result.returncode == 2:
        print(f"[A_all {run_id}] health_check FAIL - blocking publish")
        return 2
    if result.returncode == 1:
        print(f"[A_all {run_id}] health_check WARN - continuing")
        return 1
    return 0


def _run_a015_profile_a(path: Path, env: dict[str, str]) -> tuple[int, bool]:
    result, fresh = _run_a015_with_freshness(
        path,
        env,
        extra_args=["--profile", "a", "--checklist-path", str(A_SPLIT_CHECKLIST_PATH), "--no-toast"],
        freshness_path=A_SPLIT_CHECKLIST_PATH,
    )
    rc = int(result.returncode)
    if rc == 1 and not fresh:
        rc = 2
    return rc, fresh

RUN_ORDER = [
    "A001_run_listings_to_sheet.py",
    "A002_run_catalog_items_to_sheet.py",
    "A003_run_inventory_to_sheet.py",
    "A010_apply_researching_delta.py",
    "A005_run_inventory_adjustments_report.py",
    "A004_run_fees_to_sheet.py",
    "A016_refresh_phase1_daily_intel.py",
    "dedupe_product_db.py",
    "sync_product_db_to_main_sheet.py",
    "run_E_cycle.py",
    "A020_run_daily_finance.py",
    "process_stock_receipts_sheet.py",
    "A015_build_system_health_check.py",
]


def main() -> int:
    try:
        print("[A_all] requesting maintenance handoff from B cycle")
        _request_maintenance()
        handoff_mode = _wait_for_b_maintenance_ready()
        print(f"[A_all] maintenance handoff ready ({handoff_mode}); activating A maintenance")
        _activate_maintenance()
        _acquire_lock()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        inventory_ok = True
        for name in RUN_ORDER:
            path = SCRIPTS / name
            if not path.exists():
                print(f"[A_all {run_id}] missing: {path}")
                return 1
            # If inventory snapshot failed earlier, skip A010 before running it.
            if name == "A010_apply_researching_delta.py" and not inventory_ok:
                print(f"[A_all {run_id}] skipping A010 (inventory snapshot failed)")
                continue
            print(f"[A_all {run_id}] running: {name}")
            env = os.environ.copy()
            if name == "A003_run_inventory_to_sheet.py":
                # Default to no sheet writes to avoid quota issues unless explicitly enabled.
                if "INVENTORY_WRITE_SHEETS" not in env:
                    env["INVENTORY_WRITE_SHEETS"] = "0"
            if name == "A020_run_daily_finance.py":
                # Default to skipping Level 3 sheet writes to avoid 10M cell limits.
                if "FIN_L3_SKIP_SHEETS" not in env:
                    env["FIN_L3_SKIP_SHEETS"] = "1"
            if name == "A015_build_system_health_check.py":
                mode_requested = _normalize_split_mode(A_SPLIT_HEALTH_MODE, default="shadow")
                mode_effective = _effective_a_split_mode()
                print(
                    f"[A_all {run_id}] split_health mode_requested={mode_requested} "
                    f"mode_effective={mode_effective}"
                )
                if mode_effective == "legacy":
                    gate_rc = _run_a015_global_gate(run_id, path, env)
                    if gate_rc == 2:
                        return 2
                    _alert_summary()
                    continue

                if mode_effective == "shadow":
                    gate_rc = _run_a015_global_gate(run_id, path, env)
                    split_rc, split_fresh = _run_a015_profile_a(path, env)
                    legacy_counts = _health_counts(HEALTH_CHECKLIST_PATH)
                    split_counts = _health_counts(A_SPLIT_CHECKLIST_PATH)
                    legacy_fail = legacy_counts[0] if legacy_counts is not None else -1
                    legacy_warn = legacy_counts[1] if legacy_counts is not None else -1
                    split_fail = split_counts[0] if split_counts is not None else -1
                    split_warn = split_counts[1] if split_counts is not None else -1
                    legacy_gate_block = gate_rc == 2
                    split_gate_block = bool(split_rc == 2 or (split_counts is not None and split_counts[0] > 0))
                    decision_match = legacy_gate_block == split_gate_block
                    state = _update_a_shadow_streak(decision_match)
                    _append_flow_selftest_compare(
                        {
                            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "cycle_start_utc": run_id,
                            "cycle": "A",
                            "mode_requested": mode_requested,
                            "mode_effective": mode_effective,
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
                            "legacy_source": HEALTH_CHECKLIST_PATH.name,
                            "split_source": A_SPLIT_CHECKLIST_PATH.name,
                            "notes": f"split_rc={split_rc};split_fresh={'1' if split_fresh else '0'}",
                        }
                    )
                    print(
                        f"[A_all {run_id}] split_shadow_compare "
                        f"legacy_fail={legacy_fail} legacy_warn={legacy_warn} "
                        f"split_fail={split_fail} split_warn={split_warn} "
                        f"decision_match={'1' if decision_match else '0'} "
                        f"a_match_streak={_safe_int(state.get('a_match_streak', 0), 0)} "
                        f"b_match_streak={_safe_int(state.get('b_match_streak', 0), 0)} "
                        f"e_match_streak={_safe_int(state.get('e_match_streak', 0), 0)} "
                        f"ready_for_cutover={'1' if bool(state.get('ready_for_cutover', False)) else '0'}"
                    )
                    if gate_rc == 2:
                        return 2
                    _alert_summary()
                    continue

                # split mode: gate on A profile only, run global as observability-only
                split_gate_rc, split_fresh = _run_a015_profile_a(path, env)
                if split_gate_rc == 2:
                    print(
                        f"[A_all {run_id}] health_check profile=a FAIL "
                        f"(fresh={'1' if split_fresh else '0'}) - blocking A flow"
                    )
                    return 2
                if split_gate_rc == 1:
                    print(f"[A_all {run_id}] health_check profile=a WARN - continuing")
                global_result, _global_fresh = _run_a015_with_freshness(path, env, freshness_path=HEALTH_CHECKLIST_PATH)
                if global_result.returncode != 0:
                    print(
                        f"[A_all {run_id}] health_check global observability rc={global_result.returncode} "
                        "(non-blocking in split mode)"
                    )
                _alert_summary()
                continue

            started = time.time()
            result = subprocess.run([sys.executable, str(path)], env=env)
            elapsed = time.time() - started
            if result.returncode != 0:
                if name == "H001_capture_offer_snapshot.py":
                    print(f"[A_all {run_id}] WARN H001 failed (code {result.returncode}) after {elapsed:.1f}s - continuing")
                    continue
                # If inventory snapshot failed, skip the research/unsellable delta step.
                if name == "A003_run_inventory_to_sheet.py":
                    print(f"[A_all {run_id}] failed: {name} (code {result.returncode}) after {elapsed:.1f}s")
                    inventory_ok = False
                    continue
                # If stock receipts guardrail blocks, do not fail the whole A cycle.
                if name == "process_stock_receipts_sheet.py":
                    print(f"[A_all {run_id}] receipts guardrail active, skipping receipts step")
                    continue
                print(f"[A_all {run_id}] failed: {name} (code {result.returncode}) after {elapsed:.1f}s")
                return result.returncode
        print(f"[A_all {run_id}] done")
        return 0
    finally:
        _release_lock()
        _clear_maintenance()
        print("[A_all] maintenance cleared; B cycle may resume")
        # Intentionally do not auto-start B here.


if __name__ == "__main__":
    raise SystemExit(main())
