"""
Run B001-B005 in a continuous cycle with retries on failure.
"""

from __future__ import annotations

import atexit
import os
import csv
import json
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from datetime import datetime

BOOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

try:
    from scripts.core.run_manifest import (
        append_step,
        finalize_manifest,
        new_manifest,
        utc_now_iso,
        write_manifest,
    )
except ModuleNotFoundError:
    from core.run_manifest import (
        append_step,
        finalize_manifest,
        new_manifest,
        utc_now_iso,
        write_manifest,
    )
try:
    from scripts.core.script_locator import resolve_script_path
except ModuleNotFoundError:
    from core.script_locator import resolve_script_path
try:
    from scripts.core.flow_health_gate import flow_gate_checklist_path
except ModuleNotFoundError:
    from core.flow_health_gate import flow_gate_checklist_path
try:
    from scripts.core.runtime_owner_contract import (
        RuntimeOwnerContractError,
        assert_flow_owner_mapping,
        is_truthy,
    )
except ModuleNotFoundError:
    from core.runtime_owner_contract import (
        RuntimeOwnerContractError,
        assert_flow_owner_mapping,
        is_truthy,
    )
try:
    from scripts.core.runtime_stream import (
        build_lock_payload,
        parse_lock_fields as parse_stream_lock_fields,
        parse_lock_pid as parse_stream_lock_pid,
        replace_lock_heartbeat as replace_stream_lock_heartbeat,
    )
except ModuleNotFoundError:
    from core.runtime_stream import (
        build_lock_payload,
        parse_lock_fields as parse_stream_lock_fields,
        parse_lock_pid as parse_stream_lock_pid,
        replace_lock_heartbeat as replace_stream_lock_heartbeat,
    )


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
PARKING_DIR = ROOT / "out" / "parking"
INVENTORY_SUMMARIES_PATH = ROOT / "out" / "inventory_summaries.csv"
PHASE1_SCOPE_PATH = ROOT / "out" / "phase1_sku_scope.csv"
STOCK_SNAPSHOT_PATH = PARKING_DIR / "stock_snapshot_latest.csv"
PARKED_SKUS_PATH = PARKING_DIR / "parked_skus.csv"

RUN_ORDER = [
    "B001_run_orders_to_sheet.py",
    "B002_run_pending_orders_to_sheet.py",
    "B030_sync_token_allocations_from_sheet.py",
    "B007_allocate_tokens_live.py",
    "B025_build_token_cogs_ledger.py",
    "B004_build_order_master.py",
    "B006_build_fx_ledgers.py",
    "B011_recover_l3_orphans.py",
]

LOG_PATH = Path(os.environ.get("B_CYCLE_LOG_PATH", ROOT / "out" / "B_cycle.log"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
B_FATAL_PATH = Path(os.environ.get("B_FATAL_PATH", ROOT / "out" / "systems" / "B" / "live" / "B_FATAL.txt"))
B_LIVE_DIR = ROOT / "out" / "systems" / "B" / "live"
LOCK_PATH = Path(
    os.environ.get(
        "RUN_LOCK_PATH",
        os.environ.get("B_CYCLE_LOCK_PATH", B_LIVE_DIR / "B_cycle.lock"),
    )
)
LEGACY_LOCK_PATH = ROOT / "out" / "B_cycle.lock"
B_WRITE_LEGACY_LOCK = os.environ.get("B_WRITE_LEGACY_LOCK", "0").strip() == "1"
LOCKS_DIR = ROOT / "out" / "locks"

MAX_RETRIES = int(os.environ.get("B_CYCLE_MAX_RETRIES", "5"))
BACKOFF_BASE = float(os.environ.get("B_CYCLE_BACKOFF_BASE", "2"))
CYCLE_SLEEP_SECONDS = float(os.environ.get("B_CYCLE_SLEEP_SECONDS", "30"))
SUBPROCESS_HEARTBEAT_SECONDS = max(
    float(os.environ.get("B_SUBPROCESS_HEARTBEAT_SECONDS", "20") or "20"),
    1.0,
)
STEP_TIMEOUT_SECONDS_DEFAULT = max(
    float(os.environ.get("B_STEP_TIMEOUT_SECONDS_DEFAULT", "1800") or "1800"),
    0.0,
)
STEP_TIMEOUT_SECONDS = {
    "B001_run_orders_to_sheet.py": max(float(os.environ.get("B_STEP_TIMEOUT_B001_SECONDS", "1800") or "1800"), 0.0),
    "B002_run_pending_orders_to_sheet.py": max(
        float(os.environ.get("B_STEP_TIMEOUT_B002_SECONDS", "1800") or "1800"), 0.0
    ),
    "B004_build_order_master.py": max(float(os.environ.get("B_STEP_TIMEOUT_B004_SECONDS", "1800") or "1800"), 0.0),
    "B006_build_fx_ledgers.py": max(float(os.environ.get("B_STEP_TIMEOUT_B006_SECONDS", "900") or "900"), 0.0),
    "B007_allocate_tokens_live.py": max(float(os.environ.get("B_STEP_TIMEOUT_B007_SECONDS", "900") or "900"), 0.0),
    "B011_recover_l3_orphans.py": max(float(os.environ.get("B_STEP_TIMEOUT_B011_SECONDS", "900") or "900"), 0.0),
    "B025_build_token_cogs_ledger.py": max(float(os.environ.get("B_STEP_TIMEOUT_B025_SECONDS", "900") or "900"), 0.0),
    "B030_sync_token_allocations_from_sheet.py": max(
        float(os.environ.get("B_STEP_TIMEOUT_B030_SECONDS", "900") or "900"), 0.0
    ),
    "A015_build_system_health_check.py": max(
        float(os.environ.get("B_STEP_TIMEOUT_A015_SECONDS", "600") or "600"), 0.0
    ),
    "run_api_collection.py:listing_offer": max(
        float(os.environ.get("B_STEP_TIMEOUT_LISTING_COLLECTION_SECONDS", "1800") or "1800"), 0.0
    ),
    "run_api_collection.py:refunds_adjustments": max(
        float(os.environ.get("B_STEP_TIMEOUT_REFUND_COLLECTION_SECONDS", "1200") or "1200"), 0.0
    ),
    "D001_build_pnl_daily.py": max(float(os.environ.get("B_STEP_TIMEOUT_D001_SECONDS", "900") or "900"), 0.0),
}
ORDER_MASTER_PREWAIT_SECONDS = float(os.environ.get("ORDER_MASTER_PREWAIT_SECONDS", "60"))
ORDER_MASTER_PREWAIT_POLL_SECONDS = float(os.environ.get("ORDER_MASTER_PREWAIT_POLL_SECONDS", "5"))
ORDER_MASTER_L1_STABLE_SECONDS = max(
    float(os.environ.get("ORDER_MASTER_L1_STABLE_SECONDS", "60") or "60"),
    0.0,
)
B002_INTERVAL_MINUTES = float(os.environ.get("B002_INTERVAL_MINUTES", "60"))
B002_MAX_SECONDS_DEFAULT = os.environ.get("B002_MAX_SECONDS_DEFAULT", "1200")  # 20 minutes
B002_STATE_PATH = Path(os.environ.get("B002_STATE_PATH", ROOT / "out" / "B002_last_run.txt"))
REFUND_COLLECTION_INTERVAL_MINUTES = float(os.environ.get("REFUND_COLLECTION_INTERVAL_MINUTES", "240"))
REFUND_COLLECTION_STATE_PATH = Path(
    os.environ.get("REFUND_COLLECTION_STATE_PATH", ROOT / "out" / "refund_collection_last_run.txt")
)
LISTING_COLLECTION_ENABLED = os.environ.get("LISTING_COLLECTION_ENABLED", "1").strip() == "1"
LISTING_COLLECTION_INTERVAL_MINUTES = float(os.environ.get("LISTING_COLLECTION_INTERVAL_MINUTES", "15"))
LISTING_COLLECTION_STATE_PATH = Path(
    os.environ.get("LISTING_COLLECTION_STATE_PATH", ROOT / "out" / "listing_offer_collection_last_run.txt")
)
LISTING_COLLECTION_STATUS_PATH = Path(
    os.environ.get(
        "LISTING_COLLECTION_STATUS_PATH",
        ROOT / "out" / "systems" / "B" / "live" / "listing_offer_collection_status.json",
    )
)
HEALTH_CHECKLIST_PATH = Path(os.environ.get("HEALTH_CHECKLIST_PATH", ROOT / "out" / "system_health_checklist.csv"))
HEALTH_CHECKLIST_B_PATH = Path(
    os.environ.get("HEALTH_CHECKLIST_B_PATH", ROOT / "out" / "cycle_alerts" / "checklist_B.csv")
)
B_GATE_CHECKLIST_PATH = flow_gate_checklist_path("B")
L1_PATH = ROOT / "out" / "financial_events_level1.csv"
B004_GUARD_INPUTS = [
    ROOT / "out" / "financial_events_level1.csv",
    ROOT / "out" / "financial_events_level2.csv",
    ROOT / "out" / "financial_events_level3_official.csv",
    ROOT / "out" / "orders_all.csv",
    ROOT / "out" / "token_cogs_ledger.csv",
    ROOT / "out" / "l3_orphans.csv",
]
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
B_LOCK_STALE_SECONDS = max(float(os.environ.get("B_LOCK_STALE_SECONDS", "900") or "900"), 60.0)
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
A_RUN_LOCK_PATH = Path(
    os.environ.get(
        "A_RUN_LOCK_PATH",
        ROOT / "out" / "systems" / "A" / "live" / "run_cycle.lock",
    )
)
A_LEGACY_RUN_LOCK_PATH = Path(
    os.environ.get("A_LEGACY_RUN_LOCK_PATH", ROOT / "out" / "run_cycle.lock")
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
CURRENT_MANIFEST = None
EXIT_CODE = 0
_FATAL_RECORDED = False
_HEARTBEAT_THREAD: threading.Thread | None = None
_HEARTBEAT_STOP = threading.Event()
HEARTBEAT_THREAD_SECONDS = max(float(os.environ.get("B_LOCK_HEARTBEAT_SECONDS", "5") or "5"), 1.0)
_SIGNAL_EXIT_CODE: int | None = None
STEP_ARTIFACTS = {
    "B001_run_orders_to_sheet.py": ["out/orders_all.csv", "out/order_items_all.csv"],
    "B002_run_pending_orders_to_sheet.py": ["out/orders_pending_raw.csv", "out/order_items_pending_raw.csv"],
    "B030_sync_token_allocations_from_sheet.py": ["out/token_allocation_queue.csv"],
    "B007_allocate_tokens_live.py": ["out/token_ledger_live.csv", "out/token_allocation_skipped.csv"],
    "B025_build_token_cogs_ledger.py": ["out/token_cogs_ledger.csv"],
    "B004_build_order_master.py": ["out/order_master.csv"],
    "B006_build_fx_ledgers.py": ["out/order_ledger_fx.csv", "out/financial_ledger_fx.csv", "out/fx_rates_daily.csv"],
    "B011_recover_l3_orphans.py": ["out/l3_orphans.csv", "out/orphan_order_items_recovered.csv"],
    "A015_build_system_health_check.py": ["out/cycle_alerts/checklist_B.csv"],
    "run_api_collection.py:listing_offer": [
        "out/listing_offer_snapshot_latest.csv",
        "out/listing_offer_seller_snapshot_latest.csv",
    ],
    "run_api_collection.py:refunds_adjustments": ["out/refund_adjustment_snapshot_latest.csv"],
    "D001_build_pnl_daily.py": ["out/pnl_daily.csv"],
}


def _ignore_sigint_enabled() -> bool:
    raw = str(os.environ.get("B_IGNORE_SIGINT", "")).strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return str(os.environ.get("B_SUPERVISOR_ACTIVE", "")).strip() == "1"


def _owner_contract_enforced() -> bool:
    return is_truthy(os.environ.get("B_OWNER_CONTRACT_ENFORCE", "1"))


def _direct_worker_override_enabled() -> bool:
    return is_truthy(os.environ.get("B_ALLOW_DIRECT_WORKER_START", "0"))


def _enforce_owner_start_chain() -> None:
    if _owner_contract_enforced():
        assert_flow_owner_mapping(
            "B",
            runtime_owner=ROOT / "scripts" / "cycles" / "run_B_supervisor.py",
            worker_entry=Path(__file__),
            launcher_entrypoint=ROOT / "run_B_cycle.bat",
        )

    if _direct_worker_override_enabled():
        _log("owner_chain override=B_ALLOW_DIRECT_WORKER_START")
        return

    supervisor_pid = str(os.environ.get("B_SUPERVISOR_PID", "")).strip()
    supervisor_active = str(os.environ.get("B_SUPERVISOR_ACTIVE", "")).strip()
    if not supervisor_pid and supervisor_active != "1":
        raise RuntimeError(
            "direct_worker_start_blocked missing_supervisor_owner; "
            "use run_B_cycle.bat or set B_ALLOW_DIRECT_WORKER_START=1"
        )
    if supervisor_pid:
        try:
            pid_int = int(supervisor_pid)
        except Exception:
            raise RuntimeError(
                "direct_worker_start_blocked invalid_supervisor_pid; "
                "use run_B_cycle.bat or set B_ALLOW_DIRECT_WORKER_START=1"
            )
        if pid_int <= 0 or not _pid_alive(pid_int):
            raise RuntimeError(
                "direct_worker_start_blocked supervisor_pid_not_alive; "
                "use run_B_cycle.bat or set B_ALLOW_DIRECT_WORKER_START=1"
            )


def _tail(text: str | None, lines: int, max_chars: int = 4000) -> str:
    if not text:
        return ""
    parts = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    if not parts:
        return ""
    out = " | ".join(parts[-lines:])
    if len(out) > max_chars:
        out = out[-max_chars:]
    return out


def _console_write(message: str, *, error: bool = False, end: str = "\n") -> None:
    stream = sys.stderr if error else sys.stdout
    try:
        stream.write(str(message))
        if end:
            stream.write(end)
        stream.flush()
    except OSError as exc:
        try:
            _log(
                "console_write_suppressed "
                f"stream={'stderr' if error else 'stdout'} "
                f"error={type(exc).__name__}:{exc}"
            )
        except Exception:
            pass
    except Exception:
        pass


def _write_fatal(exc_type: type[BaseException], exc_value: BaseException, exc_tb) -> None:
    global _FATAL_RECORDED
    if _FATAL_RECORDED:
        return
    _FATAL_RECORDED = True
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    stamp = _ts()
    payload = (
        f"{stamp} [B_FATAL] uncaught_exception type={getattr(exc_type, '__name__', str(exc_type))} "
        f"message={exc_value}\n{tb_text}\n"
    )
    try:
        B_FATAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with B_FATAL_PATH.open("a", encoding="utf-8") as f:
            f.write(payload)
    except Exception:
        pass
    try:
        _log(
            "fatal uncaught_exception "
            f"type={getattr(exc_type, '__name__', str(exc_type))} "
            f"message={exc_value}"
        )
        _log(f"fatal traceback={tb_text.strip()}")
    except Exception:
        pass


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    global EXIT_CODE
    EXIT_CODE = 1
    try:
        _write_fatal(exc_type, exc_value, exc_tb)
    finally:
        sys.__excepthook__(exc_type, exc_value, exc_tb)


def _log_exit() -> None:
    try:
        _log(f"B_EXIT rc={int(EXIT_CODE)}")
    except Exception:
        pass


def _install_process_lifecycle_hooks() -> None:
    sys.excepthook = _excepthook
    atexit.register(_log_exit)


def _heartbeat_loop() -> None:
    while not _HEARTBEAT_STOP.wait(HEARTBEAT_THREAD_SECONDS):
        _touch_lock_heartbeat()


def _start_heartbeat_thread() -> None:
    global _HEARTBEAT_THREAD
    _HEARTBEAT_STOP.clear()
    _HEARTBEAT_THREAD = threading.Thread(target=_heartbeat_loop, name="BLockHeartbeat", daemon=True)
    _HEARTBEAT_THREAD.start()


def _stop_heartbeat_thread() -> None:
    _HEARTBEAT_STOP.set()
    t = _HEARTBEAT_THREAD
    if t is not None:
        try:
            t.join(timeout=2.0)
        except Exception:
            pass


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
    gate_path = path or B_GATE_CHECKLIST_PATH
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


def _b_gate_state_payload(path: Path | None = None, *, health_rc: int | None = None) -> dict[str, object]:
    gate_path = path or B_GATE_CHECKLIST_PATH
    counts = _health_snapshot_counts(gate_path)
    failed_checks = sorted(_failed_health_checks(gate_path)) if counts is not None else []
    if counts is None:
        gate_state = "not_run"
        fail_count = None
        warn_count = None
    else:
        fail_count, warn_count = counts
        if int(health_rc if health_rc is not None else 0) >= 2 or fail_count > 0:
            gate_state = "fail"
        elif int(health_rc if health_rc is not None else 0) == 1 or warn_count > 0:
            gate_state = "warn"
        else:
            gate_state = "pass"
    return {
        "gate_state": gate_state,
        "gate_path": str(gate_path),
        "gate_rc": "" if health_rc is None else int(health_rc),
        "gate_fail_count": fail_count,
        "gate_warn_count": warn_count,
        "completed_with_gate_fail": False,
        "blocking_checks": failed_checks,
    }


def _health_snapshot_details(path: Path = B_GATE_CHECKLIST_PATH) -> dict | None:
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


def _failed_health_checks(path: Path = B_GATE_CHECKLIST_PATH) -> set[str]:
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


def _resolve_step_timeout_seconds(step_name: str) -> float:
    return float(STEP_TIMEOUT_SECONDS.get(step_name, STEP_TIMEOUT_SECONDS_DEFAULT))


def _run_subprocess_with_watchdog(
    cmd: list[str],
    *,
    step_name: str,
    env: dict | None = None,
    capture_output: bool = False,
    text: bool = True,
    timeout_seconds: float = 0.0,
) -> subprocess.CompletedProcess:
    started = time.time()
    timeout_seconds = max(float(timeout_seconds), 0.0)
    kwargs: dict = {"env": env, "text": text}
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    proc = subprocess.Popen(cmd, **kwargs)
    while True:
        signal_exit_code = _SIGNAL_EXIT_CODE
        if signal_exit_code is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
            out_text, err_text = proc.communicate()
            signal_note = f"aborted_for_signal;signal_rc={int(signal_exit_code)};step={step_name}"
            if capture_output:
                err_text = ((err_text or "") + ("\n" if err_text else "") + signal_note).strip()
            else:
                _console_write(f"[B_cycle] {signal_note}", error=True)
            return subprocess.CompletedProcess(
                cmd,
                returncode=int(signal_exit_code),
                stdout=out_text,
                stderr=err_text,
            )
        wait_seconds = SUBPROCESS_HEARTBEAT_SECONDS
        if timeout_seconds > 0:
            remaining = timeout_seconds - (time.time() - started)
            if remaining <= 0:
                proc.kill()
                out_text, err_text = proc.communicate()
                timeout_note = f"watchdog_timeout_seconds={int(timeout_seconds)};step={step_name}"
                if capture_output:
                    err_text = ((err_text or "") + ("\n" if err_text else "") + timeout_note).strip()
                else:
                    _console_write(f"[B_cycle] {timeout_note}", error=True)
                return subprocess.CompletedProcess(cmd, returncode=124, stdout=out_text, stderr=err_text)
            wait_seconds = min(wait_seconds, max(remaining, 0.1))
        try:
            out_text, err_text = proc.communicate(timeout=wait_seconds)
            return subprocess.CompletedProcess(cmd, returncode=int(proc.returncode or 0), stdout=out_text, stderr=err_text)
        except subprocess.TimeoutExpired:
            _touch_lock_heartbeat()
            signal_exit_code = _SIGNAL_EXIT_CODE
            if signal_exit_code is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
                out_text, err_text = proc.communicate()
                signal_note = f"aborted_for_signal;signal_rc={int(signal_exit_code)};step={step_name}"
                if capture_output:
                    err_text = ((err_text or "") + ("\n" if err_text else "") + signal_note).strip()
                else:
                    _console_write(f"[B_cycle] {signal_note}", error=True)
                return subprocess.CompletedProcess(
                    cmd,
                    returncode=int(signal_exit_code),
                    stdout=out_text,
                    stderr=err_text,
                )
            # If maintenance is requested mid-step, abort promptly so the cycle can enter
            # the boundary-safe maintenance pause instead of appearing "not running" to A.
            try:
                if _maintenance_requested():
                    proc.kill()
                    out_text, err_text = proc.communicate()
                    note = f"aborted_for_maintenance;step={step_name}"
                    if capture_output:
                        err_text = ((err_text or "") + ("\n" if err_text else "") + note).strip()
                    else:
                        _console_write(f"[B_cycle] {note}", error=True)
                    return subprocess.CompletedProcess(cmd, returncode=125, stdout=out_text, stderr=err_text)
            except Exception:
                # Never let maintenance detection break the supervisor loop.
                pass


def _run_health_check_once(
    health_path: Path,
    *,
    extra_args: list[str] | None = None,
    freshness_path: Path | None = None,
) -> tuple[int, bool]:
    target_path = freshness_path or B_GATE_CHECKLIST_PATH
    before_mtime = _mtime_seconds(target_path)
    cmd = [sys.executable, str(health_path)]
    if extra_args:
        cmd.extend(extra_args)
    result = _run_subprocess_with_watchdog(
        cmd,
        step_name="A015_build_system_health_check.py",
        capture_output=False,
        text=True,
        timeout_seconds=_resolve_step_timeout_seconds("A015_build_system_health_check.py"),
    )
    if int(getattr(result, "returncode", 0) or 0) == 125:
        _log("A015 aborted_for_maintenance; treating as ok")
        return 0, False
    after_mtime = _mtime_seconds(target_path)
    fresh = after_mtime is not None and (before_mtime is None or after_mtime > before_mtime)
    return result.returncode, fresh


def _run_global_health_check_end_of_cycle(health_path: Path, *, emit_event_lines: bool = True) -> int:
    _log("run A015_build_system_health_check.py end_of_cycle attempt 1")
    rc, health_snapshot_fresh = _run_health_check_once(health_path, freshness_path=B_GATE_CHECKLIST_PATH)
    stale_warn_promoted = False
    if rc == 1 and not health_snapshot_fresh:
        _log("health_check warn with stale snapshot - treating as fail")
        rc = 2
        stale_warn_promoted = True
    if rc == 2 and not stale_warn_promoted:
        failed_checks = _failed_health_checks(B_GATE_CHECKLIST_PATH)
        if failed_checks == {"l1_keys_missing_in_master"}:
            _log("health_check fail on l1_keys_missing_in_master only - run B004 repair and retry A015")
            repair = _run_with_retries(
                resolve_script_path(SCRIPTS, "B004_build_order_master.py"),
                env_override={
                    "ORDER_MASTER_INCREMENTAL": "1",
                    "ORDER_MASTER_SKIP_SHEETS": "1",
                },
            )
            if repair == 0:
                _log("run A015_build_system_health_check.py end_of_cycle attempt 2")
                rc, health_snapshot_fresh = _run_health_check_once(
                    health_path,
                    freshness_path=B_GATE_CHECKLIST_PATH,
                )
                if rc == 1 and not health_snapshot_fresh:
                    _log("health_check warn with stale snapshot after retry - treating as fail")
                    rc = 2
    if emit_event_lines:
        if rc == 0:
            _log("ok A015_build_system_health_check.py end_of_cycle")
        elif rc == 1:
            _log("warn A015_build_system_health_check.py end_of_cycle")
        else:
            _log(f"fail A015_build_system_health_check.py end_of_cycle rc={rc}")
    else:
        if rc == 0:
            _log("health_check_end_of_cycle class=ok rc=0")
        elif rc == 1:
            _log("health_check_end_of_cycle class=warn rc=1")
        else:
            _log(f"health_check_end_of_cycle class=fail rc={rc}")
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
    health_path = resolve_script_path(SCRIPTS, "A015_build_system_health_check.py")
    step_started = utc_now_iso()
    if not health_path.exists():
        _log("skip A015_build_system_health_check.py (missing)")
        _manifest_add_step(
            name="A015_build_system_health_check.py",
            script_or_function="A015_build_system_health_check.py",
            rc=1,
            started_at=step_started,
            notes="missing script",
        )
        return 0
    mode = _normalize_split_mode(mode_effective, default="shadow")
    if mode == "legacy":
        rc = _run_global_health_check_end_of_cycle(health_path, emit_event_lines=True)
        _log_health_snapshot(path=B_GATE_CHECKLIST_PATH, tag="health_snapshot")
        _manifest_add_step(
            name="A015_build_system_health_check.py",
            script_or_function="A015_build_system_health_check.py",
            rc=rc,
            started_at=step_started,
            notes="split_mode=legacy",
        )
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
        _manifest_add_step(
            name="A015_build_system_health_check.py",
            script_or_function="A015_build_system_health_check.py",
            rc=rc,
            started_at=step_started,
            notes=f"split_mode=split;split_fresh={'1' if split_fresh else '0'}",
            inputs=[str(B_SPLIT_CHECKLIST_PATH)],
            outputs=[str(B_SPLIT_CHECKLIST_PATH)],
        )
        return rc

    # shadow mode: evaluate B-scoped health on both paths (legacy + split)
    # so B gating is isolated from non-B flow timing.
    _log("run A015_build_system_health_check.py profile=b end_of_cycle shadow_legacy")
    rc_legacy, legacy_fresh = _run_health_check_once(
        health_path,
        extra_args=["--profile", "b", "--checklist-path", str(B_GATE_CHECKLIST_PATH), "--no-toast"],
        freshness_path=B_GATE_CHECKLIST_PATH,
    )
    if rc_legacy == 1 and not legacy_fresh:
        _log("health_check warn with stale B snapshot - treating as fail")
        rc_legacy = 2
    if rc_legacy == 0:
        _log("ok A015_build_system_health_check.py profile=b end_of_cycle shadow_legacy")
    elif rc_legacy == 1:
        _log("warn A015_build_system_health_check.py profile=b end_of_cycle shadow_legacy")
    else:
        _log(f"fail A015_build_system_health_check.py profile=b end_of_cycle shadow_legacy rc={rc_legacy}")
    legacy_path = B_GATE_CHECKLIST_PATH
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
    _manifest_add_step(
        name="A015_build_system_health_check.py",
        script_or_function="A015_build_system_health_check.py",
        rc=rc_legacy,
        started_at=step_started,
        notes=(
            f"split_mode=shadow;split_rc={rc_split};split_fresh={'1' if split_fresh else '0'};"
            f"legacy_fail={legacy_fail};legacy_warn={legacy_warn};split_fail={split_fail};split_warn={split_warn}"
        ),
        inputs=[str(B_GATE_CHECKLIST_PATH), str(B_SPLIT_CHECKLIST_PATH)],
        outputs=[str(B_GATE_CHECKLIST_PATH), str(B_SPLIT_CHECKLIST_PATH)],
    )
    return rc_legacy


def _run_with_retries(path: Path, env_override: dict | None = None) -> int:
    attempt = 0
    step_started = utc_now_iso()
    detailed_tail = path.name in {"B001_run_orders_to_sheet.py", "B002_run_pending_orders_to_sheet.py"}
    while True:
        attempt += 1
        _log(f"run {path.name} attempt {attempt}")
        env = os.environ.copy()
        if B_CYCLE_QUIET:
            env["B_CYCLE_QUIET"] = "1"
        if env_override:
            env.update(env_override)
        started = time.time()
        timeout_seconds = _resolve_step_timeout_seconds(path.name)
        _console_write(f"[B_cycle] start {path.name}")
        result = _run_subprocess_with_watchdog(
            [sys.executable, str(path)],
            step_name=path.name,
            env=env,
            capture_output=True,
            text=True,
            timeout_seconds=timeout_seconds,
        )
        if result.stdout:
            _console_write(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            _console_write(result.stderr, error=True, end="" if result.stderr.endswith("\n") else "\n")
        _console_write(
            f"[B_cycle] end {path.name} rc={result.returncode} "
            f"elapsed={time.time() - started:.1f}s timeout={timeout_seconds:.0f}s"
        )
        if int(result.returncode) != 0 and detailed_tail:
            stderr_tail = _tail(result.stderr, 50, max_chars=8000)
            stdout_tail = _tail(result.stdout, 20, max_chars=4000)
            parts = [f"rc={int(result.returncode)}", f"attempt={attempt}"]
            if int(result.returncode) == 124:
                parts.append(f"watchdog_timeout_seconds={int(timeout_seconds)}")
            if stderr_tail:
                parts.append(f"stderr_tail={stderr_tail}")
            if stdout_tail:
                parts.append(f"stdout_tail={stdout_tail}")
            _log(f"step_failure_detail {path.name}; " + "; ".join(parts))
        if result.returncode == 0:
            _log(f"ok {path.name}")
            _manifest_add_step(
                name=path.name,
                script_or_function=path.name,
                rc=0,
                started_at=step_started,
                notes=f"attempts={attempt}",
            )
            return 0
        signal_abort = _SIGNAL_EXIT_CODE is not None and int(result.returncode) == int(_SIGNAL_EXIT_CODE)
        if signal_abort:
            _log(f"signal_abort {path.name} no_retry rc={int(result.returncode)}")
            _manifest_add_step(
                name=path.name,
                script_or_function=path.name,
                rc=int(result.returncode),
                started_at=step_started,
                notes=f"attempts={attempt};signal_abort_no_retry",
            )
            raise SystemExit(int(result.returncode))
        stderr_text = str(result.stderr or "")
        maintenance_abort = int(result.returncode) == 125 or "aborted_for_maintenance" in stderr_text
        if maintenance_abort and _maintenance_requested():
            _log(f"maintenance_abort {path.name} no_retry rc={int(result.returncode)}")
            _manifest_add_step(
                name=path.name,
                script_or_function=path.name,
                rc=int(result.returncode),
                started_at=step_started,
                notes=f"attempts={attempt};maintenance_abort_no_retry",
                step_status="maintenance_aborted",
                verification_status="maintenance_abort",
            )
            return int(result.returncode)
        if MAX_RETRIES > 0 and attempt >= MAX_RETRIES:
            _console_write(f"[B_cycle] failed after {attempt} attempts: {path.name}")
            stderr_tail = _tail(result.stderr, 50 if detailed_tail else 3)
            stdout_tail = _tail(result.stdout, 20 if detailed_tail else 3)
            snippet_parts = []
            if stderr_tail:
                snippet_parts.append(f"stderr_tail={stderr_tail}")
            if stdout_tail:
                snippet_parts.append(f"stdout_tail={stdout_tail}")
            if int(result.returncode) == 124:
                snippet_parts.append(f"watchdog_timeout_seconds={int(timeout_seconds)}")
            snippet = "; ".join(snippet_parts)
            _log(f"fail {path.name} after {attempt}" + (f"; {snippet}" if snippet else ""))
            _manifest_add_step(
                name=path.name,
                script_or_function=path.name,
                rc=int(result.returncode),
                started_at=step_started,
                notes=f"attempts={attempt};max_retries={MAX_RETRIES}" + (f";{snippet}" if snippet else ""),
            )
            return result.returncode
        backoff = min(BACKOFF_BASE ** attempt, 60)
        _console_write(f"[B_cycle] retry {attempt} for {path.name} in {backoff:.1f}s")
        stderr_tail = _tail(result.stderr, 20 if detailed_tail else 2)
        stdout_tail = _tail(result.stdout, 10 if detailed_tail else 2)
        snippet = []
        if stderr_tail:
            snippet.append(f"stderr_tail={stderr_tail}")
        if stdout_tail:
            snippet.append(f"stdout_tail={stdout_tail}")
        if int(result.returncode) == 124:
            snippet.append(f"watchdog_timeout_seconds={int(timeout_seconds)}")
        _log(f"retry {path.name} in {backoff:.1f}s" + (f"; {'; '.join(snippet)}" if snippet else ""))
        time.sleep(backoff)


def _wait_for_order_master_l1_stability() -> None:
    max_wait = max(float(ORDER_MASTER_PREWAIT_SECONDS), 0.0)
    required_stable_seconds = max(float(ORDER_MASTER_L1_STABLE_SECONDS), 0.0)
    poll = max(float(ORDER_MASTER_PREWAIT_POLL_SECONDS), 1.0)

    if max_wait <= 0:
        _log("order_master prewait_skipped reason=disabled max_wait_seconds=0.0")
        return
    if required_stable_seconds <= 0:
        _log("order_master prewait_skipped reason=stable_threshold_disabled required_stable_seconds=0.0")
        return
    if not L1_PATH.exists():
        _log("order_master prewait_skipped reason=l1_missing")
        return

    started = time.time()
    deadline = time.time() + max_wait
    while True:
        try:
            age_seconds = time.time() - L1_PATH.stat().st_mtime
        except Exception:
            _log("order_master prewait_skipped reason=l1_stat_failed")
            return

        waited_seconds = max(time.time() - started, 0.0)
        if age_seconds >= required_stable_seconds:
            if waited_seconds <= 0.01:
                _log(
                    "order_master prewait_skipped "
                    f"reason=already_ready l1_age_seconds={age_seconds:.1f} "
                    f"required_stable_seconds={required_stable_seconds:.1f}"
                )
            else:
                _log(
                    "order_master prewait_shortened "
                    f"waited_seconds={waited_seconds:.1f} "
                    f"l1_age_seconds={age_seconds:.1f} "
                    f"required_stable_seconds={required_stable_seconds:.1f}"
                )
            return

        remaining = deadline - time.time()
        if remaining <= 0:
            _log(
                "order_master prewait timeout "
                f"l1_age_seconds={age_seconds:.1f} "
                f"required_stable_seconds={required_stable_seconds:.1f} "
                f"max_wait_seconds={max_wait:.1f}"
            )
            return

        remaining_until_ready = max(required_stable_seconds - age_seconds, 0.0)
        sleep_for = min(poll, max(remaining, 0.0), max(remaining_until_ready, 0.0))
        if sleep_for <= 0:
            sleep_for = min(poll, max(remaining, 0.0))
        _log(
            "order_master prewait "
            f"l1_age_seconds={age_seconds:.1f} "
            f"required_stable_seconds={required_stable_seconds:.1f} "
            f"sleep_seconds={sleep_for:.1f}"
        )
        time.sleep(sleep_for)


def _fingerprint_file(path: Path) -> str:
    try:
        st = path.stat()
        return f"{path.name}:1:{int(st.st_mtime_ns)}:{int(st.st_size)}"
    except FileNotFoundError:
        return f"{path.name}:0:0:0"
    except Exception:
        return f"{path.name}:error:0:0"


def _b004_inputs_fingerprint() -> str:
    return "|".join(_fingerprint_file(path) for path in B004_GUARD_INPUTS)


def _run_refund_collection_if_due() -> None:
    step_started = utc_now_iso()
    if REFUND_COLLECTION_INTERVAL_MINUTES <= 0:
        _log("skip refunds_adjustments collection (interval disabled)")
        _manifest_add_step(
            name="run_api_collection.py:refunds_adjustments",
            script_or_function="run_api_collection.py",
            rc=0,
            started_at=step_started,
            notes="skipped interval disabled",
            outputs=STEP_ARTIFACTS.get("run_api_collection.py:refunds_adjustments", []),
        )
        return
    if REFUND_COLLECTION_STATE_PATH.exists():
        try:
            last_ts = REFUND_COLLECTION_STATE_PATH.read_text(encoding="utf-8").strip()
            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            age_sec = (datetime.utcnow() - last_dt.replace(tzinfo=None)).total_seconds()
            if age_sec < REFUND_COLLECTION_INTERVAL_MINUTES * 60:
                _log(f"skip refunds_adjustments collection (last run {age_sec:.0f}s ago)")
                _manifest_add_step(
                    name="run_api_collection.py:refunds_adjustments",
                    script_or_function="run_api_collection.py",
                    rc=0,
                    started_at=step_started,
                    notes=f"skipped interval not due age_sec={age_sec:.0f}",
                    outputs=STEP_ARTIFACTS.get("run_api_collection.py:refunds_adjustments", []),
                )
                return
        except Exception:
            pass

    path = ROOT / "run_api_collection.py"
    if not path.exists():
        _log("skip refunds_adjustments collection (run_api_collection.py missing)")
        _manifest_add_step(
            name="run_api_collection.py:refunds_adjustments",
            script_or_function="run_api_collection.py",
            rc=1,
            started_at=step_started,
            notes="missing run_api_collection.py",
            outputs=STEP_ARTIFACTS.get("run_api_collection.py:refunds_adjustments", []),
        )
        return

    _log("run refunds_adjustments collection attempt 1")
    env = os.environ.copy()
    env["API_COLLECTION_DATASETS"] = "refunds_adjustments"
    if B_CYCLE_QUIET:
        env["B_CYCLE_QUIET"] = "1"
    started = time.time()
    timeout_seconds = _resolve_step_timeout_seconds("run_api_collection.py:refunds_adjustments")
    _console_write("[B_cycle] start refunds_adjustments collection")
    result = _run_subprocess_with_watchdog(
        [sys.executable, str(path)],
        step_name="run_api_collection.py:refunds_adjustments",
        env=env,
        capture_output=False,
        text=True,
        timeout_seconds=timeout_seconds,
    )
    _console_write(
        "[B_cycle] end refunds_adjustments collection "
        f"rc={result.returncode} elapsed={time.time() - started:.1f}s timeout={timeout_seconds:.0f}s"
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
    elif result.returncode == 130:
        _log("info refunds_adjustments collection interrupted system_exit_code=130; class=nonfatal")
    else:
        _log(f"fail refunds_adjustments collection rc={result.returncode}")
    _manifest_add_step(
        name="run_api_collection.py:refunds_adjustments",
        script_or_function="run_api_collection.py",
        rc=int(result.returncode),
        started_at=step_started,
        notes="dataset=refunds_adjustments",
        outputs=STEP_ARTIFACTS.get("run_api_collection.py:refunds_adjustments", []),
    )


def _run_listing_offer_collection_if_due() -> int:
    step_started = utc_now_iso()
    if not LISTING_COLLECTION_ENABLED:
        _log("skip listing_offer collection (disabled)")
        _manifest_add_step(
            name="run_api_collection.py:listing_offer",
            script_or_function="run_api_collection.py",
            rc=0,
            started_at=step_started,
            notes="skipped disabled",
            outputs=STEP_ARTIFACTS.get("run_api_collection.py:listing_offer", []),
        )
        _write_listing_collection_status(status="skip", rc=0, notes="disabled")
        return 0

    if LISTING_COLLECTION_INTERVAL_MINUTES <= 0:
        _log("skip listing_offer collection (interval disabled)")
        _manifest_add_step(
            name="run_api_collection.py:listing_offer",
            script_or_function="run_api_collection.py",
            rc=0,
            started_at=step_started,
            notes="skipped interval disabled",
            outputs=STEP_ARTIFACTS.get("run_api_collection.py:listing_offer", []),
        )
        _write_listing_collection_status(status="skip", rc=0, notes="interval_disabled")
        return 0

    if LISTING_COLLECTION_STATE_PATH.exists():
        try:
            last_ts = LISTING_COLLECTION_STATE_PATH.read_text(encoding="utf-8").strip()
            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            age_sec = (datetime.utcnow() - last_dt.replace(tzinfo=None)).total_seconds()
            if age_sec < LISTING_COLLECTION_INTERVAL_MINUTES * 60:
                _log(f"skip listing_offer collection (last run {age_sec:.0f}s ago)")
                _manifest_add_step(
                    name="run_api_collection.py:listing_offer",
                    script_or_function="run_api_collection.py",
                    rc=0,
                    started_at=step_started,
                    notes=f"skipped interval not due age_sec={age_sec:.0f}",
                    outputs=STEP_ARTIFACTS.get("run_api_collection.py:listing_offer", []),
                )
                _write_listing_collection_status(
                    status="skip",
                    rc=0,
                    notes=f"interval_not_due age_sec={age_sec:.0f}",
                )
                return 0
        except Exception:
            pass

    path = ROOT / "run_api_collection.py"
    if not path.exists():
        _log("skip listing_offer collection (run_api_collection.py missing)")
        _manifest_add_step(
            name="run_api_collection.py:listing_offer",
            script_or_function="run_api_collection.py",
            rc=1,
            started_at=step_started,
            notes="missing run_api_collection.py",
            outputs=STEP_ARTIFACTS.get("run_api_collection.py:listing_offer", []),
        )
        _write_listing_collection_status(status="warn", rc=1, notes="missing run_api_collection.py")
        return 1

    _log("run listing_offer collection attempt 1")
    env = os.environ.copy()
    env["API_COLLECTION_DATASETS"] = "listing_offer"
    if B_CYCLE_QUIET:
        env["B_CYCLE_QUIET"] = "1"
    started = time.time()
    timeout_seconds = _resolve_step_timeout_seconds("run_api_collection.py:listing_offer")
    _console_write("[B_cycle] start listing_offer collection")
    result = _run_subprocess_with_watchdog(
        [sys.executable, str(path)],
        step_name="run_api_collection.py:listing_offer",
        env=env,
        capture_output=False,
        text=True,
        timeout_seconds=timeout_seconds,
    )
    _console_write(
        "[B_cycle] end listing_offer collection "
        f"rc={result.returncode} elapsed={time.time() - started:.1f}s timeout={timeout_seconds:.0f}s"
    )
    if result.returncode == 0:
        _log("ok listing_offer collection")
        try:
            LISTING_COLLECTION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            LISTING_COLLECTION_STATE_PATH.write_text(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), encoding="utf-8")
        except Exception:
            pass
        _write_listing_collection_status(status="ok", rc=0, notes="dataset=listing_offer")
    elif result.returncode == 3:
        _log("skip listing_offer collection (spapi lock busy)")
        _write_listing_collection_status(status="warn", rc=3, notes="spapi lock busy")
    elif result.returncode == 130:
        _log("info listing_offer collection interrupted system_exit_code=130; class=nonfatal")
        _write_listing_collection_status(status="info", rc=130, notes="system_exit_nonfatal code=130")
    else:
        _log(f"fail listing_offer collection rc={result.returncode}")
        _write_listing_collection_status(
            status="warn",
            rc=int(result.returncode),
            notes=f"dataset=listing_offer rc={int(result.returncode)}",
        )
    _manifest_add_step(
        name="run_api_collection.py:listing_offer",
        script_or_function="run_api_collection.py",
        rc=int(result.returncode),
        started_at=step_started,
        notes="dataset=listing_offer",
        outputs=STEP_ARTIFACTS.get("run_api_collection.py:listing_offer", []),
    )
    return int(result.returncode)


def _write_listing_collection_status(*, status: str, rc: int, notes: str) -> None:
    payload = {
        "timestamp_utc": _ts(),
        "cycle_start_utc": CURRENT_CYCLE_ID or "-",
        "status": str(status).strip().lower(),
        "rc": int(rc),
        "notes": str(notes or "").strip(),
    }
    try:
        LISTING_COLLECTION_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        LISTING_COLLECTION_STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception as exc:
        _log(f"warn listing_offer status write failed error={exc}")


def _refresh_stock_and_parking_state() -> None:
    step_started = utc_now_iso()
    asof_utc = _ts()
    try:
        PARKING_DIR.mkdir(parents=True, exist_ok=True)

        stock_by_sku: dict[str, int] = {}

        def _to_int(value: object) -> int:
            try:
                return int(float(str(value).strip() or "0"))
            except Exception:
                return 0

        def _to_flag(value: object) -> str:
            text = _norm(value).lower()
            if text in {"1", "true", "yes", "y", "on"}:
                return "1"
            return "0"

        if INVENTORY_SUMMARIES_PATH.exists():
            with INVENTORY_SUMMARIES_PATH.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sku = _norm(row.get("seller_sku") or row.get("sku"))
                    if not sku:
                        continue
                    total_qty = _to_int(row.get("total_quantity", 0))
                    stock_by_sku[sku] = stock_by_sku.get(sku, 0) + total_qty
        else:
            _log(f"warn stock_parking missing_source path={INVENTORY_SUMMARIES_PATH}")

        universe_skus: set[str] = set()
        if PHASE1_SCOPE_PATH.exists():
            with PHASE1_SCOPE_PATH.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sku = _norm(row.get("sku"))
                    if not sku:
                        continue
                    sale_status = _norm(row.get("sale_status")).lower()
                    parked_flag = _to_flag(row.get("parked_flag"))
                    if sale_status == "dropped":
                        continue
                    if parked_flag == "1":
                        continue
                    universe_skus.add(sku)
        else:
            _log(f"warn stock_parking missing_scope path={PHASE1_SCOPE_PATH}")

        source_cycle_run_id = ""
        if isinstance(CURRENT_MANIFEST, dict):
            source_cycle_run_id = str(CURRENT_MANIFEST.get("run_id", "") or "")

        snapshot_headers = [
            "sku",
            "merchant_qty",
            "fba_qty",
            "total_qty",
            "asof_utc",
            "source_cycle_run_id",
            "reason_code",
            "stock_source",
        ]
        snapshot_rows: list[list[str]] = []
        missing_filled_count = 0
        target_skus = sorted(universe_skus) if universe_skus else sorted(stock_by_sku.keys())
        for sku in target_skus:
            total_qty = int(stock_by_sku.get(sku, 0))
            reason_code = "OK"
            if sku not in stock_by_sku:
                reason_code = "STOCK_MISSING_FILLED"
                missing_filled_count += 1
            # Inventory summaries are FBA-based today; keep merchant qty explicit as 0.
            snapshot_rows.append(
                [
                    sku,
                    "0",
                    str(total_qty),
                    str(total_qty),
                    asof_utc,
                    source_cycle_run_id,
                    reason_code,
                    INVENTORY_SUMMARIES_PATH.name,
                ]
            )

        with STOCK_SNAPSHOT_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(snapshot_headers)
            writer.writerows(snapshot_rows)

        parked_headers = ["sku", "reason", "asof_utc", "unpark_condition"]
        parked_rows = [
            [row[0], "sold_out", asof_utc, "total_qty>0"]
            for row in snapshot_rows
            if _to_int(row[3]) <= 0
        ]
        with PARKED_SKUS_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(parked_headers)
            writer.writerows(parked_rows)

        _log(
            f"stock_parking refreshed snapshot_rows={len(snapshot_rows)} parked_rows={len(parked_rows)} "
            f"source={INVENTORY_SUMMARIES_PATH.name} "
            f"universe_count={len(universe_skus)} output_unique_skus={len(snapshot_rows)} "
            f"missing_filled_count={missing_filled_count}"
        )
        _manifest_add_step(
            name="B901_refresh_stock_parking_state",
            script_or_function="run_B_cycle.py::_refresh_stock_and_parking_state",
            rc=0,
            started_at=step_started,
            notes=(
                f"snapshot_rows={len(snapshot_rows)};parked_rows={len(parked_rows)};"
                f"universe_count={len(universe_skus)};missing_filled_count={missing_filled_count}"
            ),
            outputs=["out/parking/stock_snapshot_latest.csv", "out/parking/parked_skus.csv"],
        )
    except Exception as exc:
        _log(f"warn stock_parking refresh_failed error={exc}")
        _manifest_add_step(
            name="B901_refresh_stock_parking_state",
            script_or_function="run_B_cycle.py::_refresh_stock_and_parking_state",
            rc=1,
            started_at=step_started,
            notes=f"error={exc}",
            outputs=["out/parking/stock_snapshot_latest.csv", "out/parking/parked_skus.csv"],
        )


def main() -> int:
    global EXIT_CODE
    try:
        _enforce_owner_start_chain()
    except RuntimeOwnerContractError as exc:
        _console_write(f"[B_cycle] owner contract violation: {exc}")
        _log(f"FATAL owner_contract_violation detail={exc}")
        return 2
    except RuntimeError as exc:
        _console_write(f"[B_cycle] {exc}")
        _log(f"FATAL {exc}")
        return 2
    _install_process_lifecycle_hooks()
    _acquire_lock()
    _install_lock_cleanup_handlers()
    _start_heartbeat_thread()
    try:
        EXIT_CODE = int(_main_loop())
        return EXIT_CODE
    except Exception:
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_type is not None and exc_value is not None:
            _write_fatal(exc_type, exc_value, exc_tb)
        EXIT_CODE = 1
        raise
    finally:
        _stop_heartbeat_thread()
        _release_lock()


def _main_loop() -> int:
    for name in RUN_ORDER:
        path = resolve_script_path(SCRIPTS, name)
        if not path.exists():
            _console_write(f"[B_cycle] missing: {path}")
            return 1

    global CURRENT_CYCLE_ID
    global CURRENT_MANIFEST
    while True:
        cycle_rc = 1
        finalize_reason = "cycle_incomplete"
        _touch_lock_heartbeat()
        if _pause_for_maintenance_at_boundary("before cycle start"):
            finalize_reason = "restart_drain_boundary_exit_before_cycle"
            cycle_rc = 0
            return 0
        CURRENT_CYCLE_ID = _ts()
        CURRENT_MANIFEST = new_manifest(cycle="B", run_id=f"B_{CURRENT_CYCLE_ID.replace(':', '').replace('-', '')}", start_time=utc_now_iso())
        mode_requested = _normalize_split_mode(B_SPLIT_HEALTH_MODE, default="shadow")
        mode_effective = _effective_b_split_mode()
        _log(f"split_health mode_requested={mode_requested} mode_effective={mode_effective}")
        wrote_health = False
        first_b004_succeeded = False
        first_b004_inputs_fingerprint = ""
        try:
            for name in RUN_ORDER:
                path = resolve_script_path(SCRIPTS, name)
                _console_write(f"[B_cycle] running: {name}")
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
                    _wait_for_order_master_l1_stability()
                    env_override = {}
                    if "ORDER_MASTER_INCREMENTAL" not in os.environ:
                        env_override["ORDER_MASTER_INCREMENTAL"] = "1"
                    rc_b004_first = _run_with_retries(path, env_override=env_override)
                    if rc_b004_first == 0:
                        first_b004_succeeded = True
                        first_b004_inputs_fingerprint = _b004_inputs_fingerprint()
                    else:
                        first_b004_succeeded = False
                        first_b004_inputs_fingerprint = ""
                    continue
                _run_with_retries(path)
            try:
                _run_listing_offer_collection_if_due()
            except SystemExit as exc:
                code = int(exc.code) if isinstance(exc.code, int) else 1
                if _restart_drain_requested():
                    _log(
                        "restart_drain listing_offer collection interrupted "
                        f"system_exit_code={code}; treating as boundary_skip"
                    )
                    _write_listing_collection_status(
                        status="skip",
                        rc=0,
                        notes=f"restart_drain_boundary_skip code={code}",
                    )
                else:
                    if code == 130:
                        _log(
                            "info listing_offer collection interrupted "
                            "system_exit_code=130; class=nonfatal; continuing cycle"
                        )
                        _write_listing_collection_status(
                            status="info",
                            rc=130,
                            notes="system_exit_nonfatal code=130",
                        )
                    else:
                        _log(
                            "warn listing_offer collection interrupted "
                            f"system_exit_code={code}; treating as nonfatal and continuing cycle"
                        )
                        _write_listing_collection_status(
                            status="warn",
                            rc=code,
                            notes=f"system_exit_nonfatal code={code}",
                        )
            try:
                _run_refund_collection_if_due()
            except SystemExit as exc:
                code = int(exc.code) if isinstance(exc.code, int) else 1
                if _restart_drain_requested():
                    _log(
                        "restart_drain refunds_adjustments collection interrupted "
                        f"system_exit_code={code}; treating as boundary_skip"
                    )
                else:
                    if code == 130:
                        _log(
                            "info refunds_adjustments collection interrupted "
                            "system_exit_code=130; class=nonfatal; continuing cycle"
                        )
                    else:
                        _log(
                            "warn refunds_adjustments collection interrupted "
                            f"system_exit_code={code}; treating as nonfatal and continuing cycle"
                        )
            _refresh_stock_and_parking_state()
            # Publish once per cycle if running quiet mode (no partial sheet updates).
            if B_CYCLE_QUIET:
                # Gate publish using the last completed health snapshot.
                if mode_effective == "split":
                    gate_path = B_SPLIT_CHECKLIST_PATH
                else:
                    gate_path = B_GATE_CHECKLIST_PATH
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
                    _console_write("[B_cycle] health_gate snapshot FAIL - skipping publish")
                    _log("health_gate snapshot FAIL - skip publish")
                else:
                    _console_write("[B_cycle] publish: Order_Master")
                    _log("publish Order_Master")
                    b004_publish_env = {
                        "ORDER_MASTER_SKIP_SHEETS": "0",
                        "B_CYCLE_QUIET": "0",
                        "ORDER_MASTER_INCREMENTAL": "1",
                    }
                    if first_b004_succeeded and first_b004_inputs_fingerprint:
                        publish_fingerprint = _b004_inputs_fingerprint()
                        if publish_fingerprint == first_b004_inputs_fingerprint:
                            _log(
                                "b004_second_run_skipped reason=no_input_change "
                                "publish_mode=existing_artifact "
                                f"run_id={CURRENT_CYCLE_ID or '-'}"
                            )
                            b004_publish_env["ORDER_MASTER_PUBLISH_EXISTING_ONLY"] = "1"
                        else:
                            _log(
                                "b004_second_run_required reason=input_changed "
                                f"run_id={CURRENT_CYCLE_ID or '-'}"
                            )
                    else:
                        _log(
                            "b004_second_run_required reason=first_run_unavailable "
                            f"run_id={CURRENT_CYCLE_ID or '-'}"
                        )
                    _wait_for_order_master_l1_stability()
                    _run_with_retries(
                        resolve_script_path(SCRIPTS, "B004_build_order_master.py"),
                        env_override=b004_publish_env,
                    )
                    _console_write("[B_cycle] publish: Order_Ledger_FX")
                    _log("publish Order_Ledger_FX")
                    _run_with_retries(resolve_script_path(SCRIPTS, "B006_build_fx_ledgers.py"))
                    _console_write("[B_cycle] publish: P&L")
                    _log("publish P&L")
                    _run_with_retries(
                        resolve_script_path(SCRIPTS, "D001_build_pnl_daily.py"),
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
            cycle_rc = 0
            finalize_reason = "cycle_complete"
            if CYCLE_SLEEP_SECONDS > 0:
                _console_write(f"[B_cycle] cycle sleep {CYCLE_SLEEP_SECONDS:.0f}s")
                _log(f"cycle sleep {CYCLE_SLEEP_SECONDS:.0f}s")
                _touch_lock_heartbeat()
                time.sleep(CYCLE_SLEEP_SECONDS)
            if B_RUN_ONCE:
                finalize_reason = "run_once_exit"
                _log("run_once enabled, exiting after single cycle")
                return 0
            if _pause_for_maintenance_at_boundary("after cycle end"):
                finalize_reason = "restart_drain_boundary_exit_after_cycle"
                return 0
        finally:
            manifest_final_state = "completed" if cycle_rc == 0 else "failed"
            health_rc = None
            gate_path = B_SPLIT_CHECKLIST_PATH if mode_effective == "split" else B_GATE_CHECKLIST_PATH
            if cycle_rc == 0:
                health_rc = _run_health_check_end_of_cycle(mode_effective=mode_effective, mode_requested=mode_requested)
                wrote_health = True
            _log(
                "B_FINALIZE "
                f"ran rc={cycle_rc} wrote_health={'true' if wrote_health else 'false'} "
                f"reason={finalize_reason} gate_rc={health_rc if health_rc is not None else 'not_run'}"
            )
            _manifest_flush(final_state=manifest_final_state, gate_path=gate_path, health_rc=health_rc)
    _manifest_flush(final_state="completed")
    return 0


def _log(msg: str) -> None:
    ts = _ts()
    cycle = CURRENT_CYCLE_ID or "-"
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{ts} [{cycle}] {msg}\n")


def _maintenance_requested() -> bool:
    if MAINTENANCE_MODE:
        return True
    return _path_exists_safe(MAINTENANCE_FLAG_PATH) or _path_exists_safe(MAINTENANCE_REQUEST_PATH)


def _maintenance_request_text() -> str:
    parts: list[str] = []
    for path in (MAINTENANCE_FLAG_PATH, MAINTENANCE_REQUEST_PATH):
        if not _path_exists_safe(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if text:
            parts.append(text)
    return "\n".join(parts)


def _restart_drain_requested() -> bool:
    global_text = _read_marker_text(MAINTENANCE_REQUEST_PATH)
    if "requested_by=controlled_restart_gate" in global_text and "reason=overnight_restart_eval" in global_text:
        return True
    b_text = _read_marker_text(MAINTENANCE_FLAG_PATH).lower()
    if not b_text:
        return False
    return (
        "action=restart_drain" in b_text
        or "exit_after_drain=1" in b_text
        or "restart_drain=1" in b_text
    )


def _maintenance_reason() -> str:
    if MAINTENANCE_REASON:
        return MAINTENANCE_REASON
    if not _path_exists_safe(MAINTENANCE_FLAG_PATH):
        return ""
    try:
        text = MAINTENANCE_FLAG_PATH.read_text(encoding="utf-8").strip()
        first = text.splitlines()[0].strip() if text else ""
        return first
    except Exception:
        return ""


def _path_exists_safe(path: Path) -> bool:
    try:
        return path.exists()
    except Exception as exc:
        _log(f"warn path_exists_failed path={path} error={exc}")
        return False


def _read_marker_text(path: Path) -> str:
    if not _path_exists_safe(path):
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _parse_marker_field(payload: str, key: str) -> str:
    parts = [p.strip() for p in str(payload).split("|") if p.strip()]
    for part in parts:
        part_clean = str(part).lstrip("\ufeff").strip()
        if part_clean.startswith(f"{key}="):
            return part_clean.split("=", 1)[1].strip()
    return ""


def _a_run_lock_alive() -> bool:
    seen: set[Path] = set()
    for lock_path in (A_RUN_LOCK_PATH, A_LEGACY_RUN_LOCK_PATH):
        if lock_path in seen:
            continue
        seen.add(lock_path)
        payload = _read_marker_text(lock_path)
        if not payload:
            continue
        pid = _parse_lock_pid(payload)
        if pid is not None and _pid_alive(pid):
            return True
    return False


def _recover_stale_a_maintenance(context: str) -> bool:
    request_text = _read_marker_text(MAINTENANCE_REQUEST_PATH)
    active_text = _read_marker_text(MAINTENANCE_ACTIVE_PATH)
    if not request_text and not active_text:
        return False

    request_owner = _parse_marker_field(request_text, "requested_by")
    active_owner = _parse_marker_field(active_text, "active_by")
    # Never clear non-A ownership markers from B.
    if request_owner not in {"", "A"}:
        return False
    if active_owner not in {"", "A"}:
        return False
    if request_owner != "A" and active_owner != "A":
        return False

    owner_pids: list[int] = []
    for marker_text in (request_text, active_text):
        pid = _parse_lock_pid(marker_text)
        if pid is not None:
            owner_pids.append(pid)
    if any(_pid_alive(pid) for pid in owner_pids):
        return False
    if _a_run_lock_alive():
        return False

    for path in (MAINTENANCE_ACTIVE_PATH, MAINTENANCE_REQUEST_PATH, MAINTENANCE_READY_PATH):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
    _log(
        "maintenance stale_owner_recovered "
        f"context={context} owners=requested_by:{request_owner or '-'} "
        f"active_by:{active_owner or '-'} owner_pids={','.join(str(pid) for pid in owner_pids) or '-'}"
    )
    return True


def _pause_for_maintenance_at_boundary(context: str) -> bool:
    if not _maintenance_requested():
        return False
    MAINTENANCE_READY_PATH.parent.mkdir(parents=True, exist_ok=True)
    request_id = _parse_marker_field(_maintenance_request_text(), "request_id")
    ready_payload = f"B_READY|pid={os.getpid()}|ts={_ts()}|context={context}"
    if request_id:
        ready_payload += f"|request_id={request_id}"
    ready_payload += "\n"
    try:
        MAINTENANCE_READY_PATH.write_text(ready_payload, encoding="utf-8")
    except Exception:
        pass
    request_id_suffix = f" request_id={request_id}" if request_id else ""
    _log(f"maintenance ready ({context}); current cycle finished{request_id_suffix}")
    if _restart_drain_requested():
        _log(f"restart_drain boundary_ready ({context}); exiting B loop for controlled restart")
        return True
    while _maintenance_requested() or _path_exists_safe(MAINTENANCE_ACTIVE_PATH):
        if _recover_stale_a_maintenance(context):
            continue
        reason = _maintenance_reason()
        reason_suffix = f"; reason={reason}" if reason else ""
        msg = (
            f"maintenance pause ({context}); sleeping {MAINTENANCE_SLEEP_SECONDS:.0f}s, "
            f"check back in {MAINTENANCE_ETA_MINUTES} minutes{reason_suffix}"
        )
        _console_write(f"[B_cycle] {msg}")
        _log(msg)
        time.sleep(max(MAINTENANCE_SLEEP_SECONDS, 1.0))
    try:
        if _path_exists_safe(MAINTENANCE_READY_PATH):
            MAINTENANCE_READY_PATH.unlink()
    except Exception:
        pass
    _log(f"maintenance clear ({context}); resuming cycle")
    return False


def _acquire_lock() -> None:
    if LOCK_FORCE:
        _write_lock()
        return
    now_utc = datetime.utcnow()
    for path in _lock_probe_paths():
        if not path.exists():
            continue
        payload = _norm(path.read_text(encoding="utf-8"))
        pid = _parse_lock_pid(payload)
        stale = _lock_is_stale(payload, now_utc)
        if pid is not None and _pid_alive(pid) and not stale:
            _console_write(f"[B_cycle] lock exists (pid {pid}). Exiting to avoid double-run.")
            raise SystemExit(1)
        if pid is not None and _pid_alive(pid) and stale:
            _log(
                "lock_recovered "
                f"path={path} reason=stale_heartbeat pid={pid} stale_seconds>={int(B_LOCK_STALE_SECONDS)}"
            )
        elif pid is not None and not _pid_alive(pid):
            _log(f"lock_recovered path={path} reason=dead_pid pid={pid}")
        else:
            _log(f"lock_recovered path={path} reason=invalid_or_unknown_pid")
        path.unlink(missing_ok=True)
    _write_lock()


def _write_lock(*, heartbeat_only: bool = False) -> None:
    now = _ts()
    for path in _lock_paths():
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = ""
        if heartbeat_only:
            try:
                existing = _norm(path.read_text(encoding="utf-8"))
            except Exception:
                existing = ""
            if existing:
                existing_pid = _parse_lock_pid(existing)
                if existing_pid == os.getpid():
                    payload = replace_stream_lock_heartbeat(existing, heartbeat_utc=now)
        if not payload:
            payload = build_lock_payload(owner="B", pid=os.getpid(), start_utc=now, heartbeat_utc=now)
        path.write_text(payload, encoding="utf-8")


def _release_lock() -> None:
    for path in _lock_probe_paths():
        try:
            if not path.exists():
                continue
            payload = _norm(path.read_text(encoding="utf-8"))
            pid = _parse_lock_pid(payload)
            if pid == os.getpid() or pid is None or not _pid_alive(pid):
                path.unlink(missing_ok=True)
        except Exception:
            continue


def _touch_lock_heartbeat() -> None:
    try:
        _write_lock(heartbeat_only=True)
    except Exception:
        pass


def _lock_paths() -> list[Path]:
    out = [LOCK_PATH]
    if B_WRITE_LEGACY_LOCK and LEGACY_LOCK_PATH != LOCK_PATH:
        out.append(LEGACY_LOCK_PATH)
    return out


def _lock_probe_paths() -> list[Path]:
    out = list(_lock_paths())
    if LEGACY_LOCK_PATH not in out:
        out.append(LEGACY_LOCK_PATH)
    return out


def _parse_lock_pid(payload: str) -> int | None:
    return parse_stream_lock_pid(payload)


def _parse_lock_utc(payload: str, key: str) -> datetime | None:
    fields = parse_stream_lock_fields(payload)
    raw = str(fields.get(str(key or "").strip(), "")).strip()
    if raw:
        text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        try:
            return datetime.fromisoformat(text)
        except Exception:
            return None
    return None


def _lock_is_stale(payload: str, now_utc: datetime) -> bool:
    lock_dt = _parse_lock_utc(payload, "heartbeat") or _parse_lock_utc(payload, "start")
    if lock_dt is None:
        return False
    if lock_dt.tzinfo is not None:
        lock_dt = lock_dt.replace(tzinfo=None)
    age = max((now_utc - lock_dt).total_seconds(), 0.0)
    return age >= B_LOCK_STALE_SECONDS


def _norm(value: object) -> str:
    return str(value or "").strip()


def _install_lock_cleanup_handlers() -> None:
    atexit.register(_release_lock)

    def _handle_runtime_signal(signum: int) -> None:
        global _SIGNAL_EXIT_CODE
        signum_int = int(signum)
        sigint_value = int(getattr(signal, "SIGINT", 2))
        if signum_int == sigint_value and _ignore_sigint_enabled():
            try:
                _log(f"signal_received signum={signum_int}; ignored")
            except Exception:
                pass
            return
        _SIGNAL_EXIT_CODE = 128 + signum_int
        try:
            _log(f"signal_received signum={signum_int}; graceful_shutdown_requested")
        except Exception:
            pass

    def _handle_signal(signum, _frame) -> None:
        _handle_runtime_signal(int(signum))

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _handle_signal)
        except Exception:
            continue


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return False
        out = (result.stdout or "").strip().lower()
        if "no tasks are running" in out:
            return False
        return str(int(pid)) in out
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _manifest_add_step(
    *,
    name: str,
    script_or_function: str,
    rc: int,
    started_at: str,
    notes: str = "",
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    step_status: str = "",
    verification_status: str = "",
) -> None:
    global CURRENT_MANIFEST
    if CURRENT_MANIFEST is None:
        return
    artifacts = outputs if outputs is not None else STEP_ARTIFACTS.get(name, [])
    append_step(
        CURRENT_MANIFEST,
        name=name,
        script_or_function=script_or_function,
        inputs=inputs or [],
        outputs=artifacts,
        rc=int(rc),
        notes=notes,
        started_at=started_at,
        ended_at=utc_now_iso(),
        step_status=step_status,
        verification_status=verification_status,
    )


def _manifest_flush(
    *,
    final_state: str | None = None,
    gate_path: Path | None = None,
    health_rc: int | None = None,
) -> None:
    global CURRENT_MANIFEST
    if CURRENT_MANIFEST is None:
        return
    try:
        gate_payload = _b_gate_state_payload(gate_path or B_GATE_CHECKLIST_PATH, health_rc=health_rc)
        gate_payload["completed_with_gate_fail"] = (
            str(final_state or "").strip().lower() == "completed"
            and str(gate_payload.get("gate_state", "")).lower() == "fail"
        )
        CURRENT_MANIFEST["gate_state"] = gate_payload["gate_state"]
        CURRENT_MANIFEST["gate_path"] = gate_payload["gate_path"]
        CURRENT_MANIFEST["gate_rc"] = gate_payload["gate_rc"]
        CURRENT_MANIFEST["gate_fail_count"] = gate_payload["gate_fail_count"]
        CURRENT_MANIFEST["gate_warn_count"] = gate_payload["gate_warn_count"]
        CURRENT_MANIFEST["completed_with_gate_fail"] = gate_payload["completed_with_gate_fail"]
        CURRENT_MANIFEST["blocking_checks"] = gate_payload["blocking_checks"]
        finalize_manifest(
            CURRENT_MANIFEST,
            health_checklist_path=B_GATE_CHECKLIST_PATH,
            end_time=utc_now_iso(),
            final_state=final_state,
        )
        path = write_manifest(ROOT, CURRENT_MANIFEST)
        _log(f"manifest written {path}")
    except Exception as exc:
        _log(f"warn manifest write failed error={exc}")
    finally:
        CURRENT_MANIFEST = None


if __name__ == "__main__":
    rc = int(main())
    EXIT_CODE = rc
    raise SystemExit(rc)

