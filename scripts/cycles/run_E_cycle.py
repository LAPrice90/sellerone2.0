from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import json
import pandas as pd

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
    from scripts.core.runtime_stream import (
        build_lock_payload,
        parse_lock_pid as parse_stream_lock_pid,
    )
except ModuleNotFoundError:
    from core.runtime_stream import (
        build_lock_payload,
        parse_lock_pid as parse_stream_lock_pid,
    )

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
E_LIVE_DIR = OUT / "systems" / "E" / "live"
E_RUN_LOG = Path(os.environ.get("E_RUN_LOG_PATH", str(E_LIVE_DIR / "e_run_log.jsonl")))
E_RUN_LOG_LEGACY = OUT / "e_run_log.jsonl"
E_DECISION_LOG = Path(os.environ.get("E_DECISION_LOG_PATH", str(OUT / "e_decision_log.csv")))
E_LOCK_PATH = Path(os.environ.get("E_CYCLE_LOCK_PATH", str(E_LIVE_DIR / "E_cycle.lock")))
E_LOCK_LEGACY_PATH = OUT / "E_cycle.lock"
E_SPLIT_HEALTH_MODE = os.environ.get("E_SPLIT_HEALTH_MODE", "shadow").strip().lower() or "shadow"
E_SPLIT_CHECKLIST_PATH = flow_gate_checklist_path("E")
E_HEALTH_FAIL_CLOSED = os.environ.get("E_HEALTH_FAIL_CLOSED", "1").strip() == "1"
FLOW_SELFTEST_COMPARE_PATH = OUT / "cycle_alerts" / "flow_selftest_compare.csv"
FLOW_SELFTEST_STATE_PATH = OUT / "cycle_alerts" / "flow_selftest_state.json"
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

TASKS = [
    resolve_script_path(ROOT / "scripts", "E001_build_sales_velocity.py"),
    resolve_script_path(ROOT / "scripts", "E002_build_roi_snapshot.py"),
    resolve_script_path(ROOT / "scripts", "E003_build_restock_signals.py"),
    resolve_script_path(ROOT / "scripts", "E004_build_performance_summary.py"),
    resolve_script_path(ROOT / "scripts", "E005_build_study_report.py"),
    resolve_script_path(ROOT / "scripts", "E006_build_sales_truth_reconciliation.py"),
    resolve_script_path(ROOT / "scripts", "E007_build_sku_daily_sales_truth.py"),
]

STEP_ARTIFACTS = {
    "E001_build_sales_velocity.py": ["out/sku_sales_velocity.csv"],
    "E002_build_roi_snapshot.py": ["out/sku_roi_snapshot.csv", "out/sku_roi_snapshot_by_country.csv"],
    "E003_build_restock_signals.py": ["out/sku_restock_signals.csv"],
    "E004_build_performance_summary.py": ["out/sku_performance_summary.csv"],
    "E005_build_study_report.py": ["out/e_study_report.csv"],
    "E006_build_sales_truth_reconciliation.py": [
        "out/sales_truth_sku_30d_latest.csv",
        "out/sales_truth_reconciliation_latest.csv",
    ],
    "E007_build_sku_daily_sales_truth.py": ["out/sku_daily_sales_truth_latest.csv"],
    "A015_build_system_health_check.py:profile=e": ["out/cycle_alerts/checklist_E_split.csv"],
    "E010_publish_e_outputs.py": ["out/e_publish_log.csv"],
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dt(value: str) -> datetime | None:
    s = str(value or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _last_success_finished_utc() -> datetime | None:
    if not E_RUN_LOG.exists():
        return None
    last_dt: datetime | None = None
    with E_RUN_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if str(row.get("status", "")).strip().lower() != "success":
                continue
            dt = _to_dt(str(row.get("finished_utc", "")))
            if dt is None:
                dt = _to_dt(str(row.get("started_utc", "")))
            if dt is None:
                continue
            if last_dt is None or dt > last_dt:
                last_dt = dt
    return last_dt


def _max_asof_date(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        df = pd.read_csv(path, dtype=str, usecols=["asof_date"]).fillna("")
    except Exception:
        return ""
    if df.empty or "asof_date" not in df.columns:
        return ""
    vals = [str(v).strip() for v in df["asof_date"].tolist() if str(v).strip()]
    return max(vals) if vals else ""


def _expected_input_asof() -> str:
    dates = []
    for path in (
        OUT / "listing_offer_history.csv",
        OUT / "inventory_history.csv",
        OUT / "inbound_history.csv",
        OUT / "refund_adjustment_history.csv",
    ):
        val = _max_asof_date(path)
        if not val:
            return ""
        dates.append(val)
    return min(dates) if dates else ""


def _latest_output_asof() -> str:
    out_dates = []
    for path in (
        OUT / "sku_sales_velocity.csv",
        OUT / "sku_roi_snapshot.csv",
        OUT / "sku_restock_signals.csv",
        OUT / "sku_performance_summary.csv",
        OUT / "e_study_report.csv",
        OUT / "sales_truth_reconciliation_latest.csv",
    ):
        val = _max_asof_date(path)
        if not val:
            return ""
        out_dates.append(val)
    return min(out_dates) if out_dates else ""


def _run(label: str, script: Path) -> float:
    print(f"[E_cycle] running: {label}")
    started = _utc_now()
    subprocess.run([sys.executable, str(script)], check=True)
    elapsed = (_utc_now() - started).total_seconds()
    print(f"[E_cycle] ok {label} elapsed={elapsed:.1f}s")
    return elapsed


def _ensure_decision_log() -> None:
    headers = [
        "run_id",
        "sku",
        "decision_type",
        "decision_value",
        "reason_code",
        "note",
        "profit_per_unit_gbp_30d",
        "value_velocity_gbp_per_day",
        "created_utc",
        "source",
        "asof_date",
    ]
    if E_DECISION_LOG.exists():
        try:
            df = pd.read_csv(E_DECISION_LOG, dtype=str).fillna("")
        except Exception:
            df = pd.DataFrame(columns=headers)
        missing = [c for c in headers if c not in df.columns]
        if missing:
            for col in missing:
                df[col] = ""
            df = df[headers]
            df.to_csv(E_DECISION_LOG, index=False)
        return

    E_DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with E_DECISION_LOG.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)


def _append_run_log(row: dict) -> None:
    payload = json.dumps(row, ensure_ascii=True) + "\n"
    seen: set[Path] = set()
    for path in (E_RUN_LOG, E_RUN_LOG_LEGACY):
        if path in seen:
            continue
        seen.add(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(payload)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _parse_lock_pid(payload: str) -> int | None:
    return parse_stream_lock_pid(payload)


def _lock_paths() -> list[Path]:
    out: list[Path] = []
    for path in (E_LOCK_PATH, E_LOCK_LEGACY_PATH):
        if path not in out:
            out.append(path)
    return out


def _acquire_lock() -> None:
    force = os.environ.get("E_CYCLE_FORCE", "0").strip() == "1"
    if not force:
        for path in _lock_paths():
            if not path.exists():
                continue
            payload = path.read_text(encoding="utf-8")
            pid = _parse_lock_pid(payload)
            if pid is not None and _pid_alive(pid):
                raise SystemExit(f"[E_cycle] lock exists (pid {pid})")
            path.unlink(missing_ok=True)
    now = _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = build_lock_payload(owner="E", pid=os.getpid(), start_utc=now, heartbeat_utc=now)
    for path in _lock_paths():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def _release_lock() -> None:
    for path in _lock_paths():
        try:
            if not path.exists():
                continue
            payload = path.read_text(encoding="utf-8")
            pid = _parse_lock_pid(payload)
            if pid == os.getpid() or pid is None:
                path.unlink(missing_ok=True)
        except Exception:
            continue


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


def _mtime_seconds(path: Path) -> float | None:
    try:
        if not path.exists():
            return None
        return float(path.stat().st_mtime)
    except Exception:
        return None


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


def _run_a015_profile_e() -> tuple[int, bool]:
    health_path = resolve_script_path(ROOT / "scripts", "A015_build_system_health_check.py")
    if not health_path.exists():
        return 2, False
    before_mtime = _mtime_seconds(E_SPLIT_CHECKLIST_PATH)
    cmd = [
        sys.executable,
        str(health_path),
        "--profile",
        "e",
        "--checklist-path",
        str(E_SPLIT_CHECKLIST_PATH),
        "--no-toast",
    ]
    proc = subprocess.run(cmd)
    after_mtime = _mtime_seconds(E_SPLIT_CHECKLIST_PATH)
    fresh = after_mtime is not None and (before_mtime is None or after_mtime > before_mtime)
    rc = int(proc.returncode)
    if rc == 1 and not fresh:
        rc = 2
    return rc, fresh


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
        "updated_utc": _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
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


def _effective_e_split_mode() -> str:
    requested = _normalize_split_mode(E_SPLIT_HEALTH_MODE, default="shadow")
    if requested != "shadow":
        return requested
    state = _load_flow_selftest_state()
    if bool(state.get("ready_for_cutover", False)):
        print("[E_cycle] split_health auto_cutover active (ready_for_cutover=true)")
        return "split"
    return "shadow"


def _update_e_shadow_streak(match: bool) -> dict:
    state = _load_flow_selftest_state()
    if match:
        state["e_match_streak"] = _safe_int(state.get("e_match_streak", 0), 0) + 1
    else:
        state["e_match_streak"] = 0
    a_streak = _safe_int(state.get("a_match_streak", 0), 0)
    b_streak = _safe_int(state.get("b_match_streak", 0), 0)
    e_streak = _safe_int(state.get("e_match_streak", 0), 0)
    state["ready_for_cutover"] = a_streak >= 10 and b_streak >= 10 and e_streak >= 10
    state["updated_utc"] = _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_flow_selftest_state(state)
    return state


def main() -> None:
    _acquire_lock()
    run_id = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    manifest = new_manifest(cycle="E", run_id=run_id, start_time=utc_now_iso())
    started = _utc_now()
    status = "success"
    error = ""
    elapsed_total = 0.0
    tasks_run = []
    mode_requested = _normalize_split_mode(E_SPLIT_HEALTH_MODE, default="shadow")
    mode_effective = _effective_e_split_mode()
    expected_input_asof = _expected_input_asof()
    latest_output_asof = _latest_output_asof()
    asof_rerun_trigger = False

    enforce_cadence = os.environ.get("E_ENFORCE_CADENCE", "1").strip() != "0"
    try:
        cadence_hours = float(os.environ.get("E_CADENCE_HOURS", "24").strip() or "24")
    except Exception:
        cadence_hours = 24.0
    if cadence_hours < 0:
        cadence_hours = 0.0

    if enforce_cadence and cadence_hours > 0:
        last_success = _last_success_finished_utc()
        if last_success is not None:
            asof_rerun_trigger = bool(
                expected_input_asof
                and latest_output_asof
                and expected_input_asof > latest_output_asof
            )
            # Allow one successful run per new UTC date even if 24h has not elapsed.
            if started.date() > last_success.date():
                pass
            elif asof_rerun_trigger:
                pass
            else:
                next_allowed = last_success + timedelta(hours=cadence_hours)
                if started < next_allowed:
                    wait_seconds = max((next_allowed - started).total_seconds(), 0.0)
                    note = (
                        f"cadence_hours={cadence_hours:.3f}; "
                        f"last_success_finished_utc={last_success.isoformat()}; "
                        f"next_allowed_utc={next_allowed.isoformat()}; "
                        f"wait_seconds={wait_seconds:.0f}"
                    )
                    _append_run_log({
                        "run_id": run_id,
                        "started_utc": started.isoformat(),
                        "finished_utc": started.isoformat(),
                        "status": "skipped_cadence",
                        "tasks_run": "",
                        "elapsed_seconds": "0.000",
                        "expected_input_asof": expected_input_asof,
                        "output_asof": latest_output_asof,
                        "asof_rerun_trigger": "0",
                        "error": note,
                    })
                    print({
                        "status": "skipped_cadence",
                        "run_id": run_id,
                        "cadence_hours": cadence_hours,
                        "next_allowed_utc": next_allowed.isoformat(),
                    })
                    _release_lock()
                    return

    try:
        _ensure_decision_log()
        print(f"[E_cycle] split_health mode_requested={mode_requested} mode_effective={mode_effective}")
        for script in TASKS:
            tasks_run.append(script.name)
            step_started = utc_now_iso()
            elapsed_total += _run(script.name, script)
            append_step(
                manifest,
                name=script.name,
                script_or_function=script.name,
                inputs=[],
                outputs=STEP_ARTIFACTS.get(script.name, []),
                rc=0,
                notes="",
                started_at=step_started,
                ended_at=utc_now_iso(),
            )

        legacy_gate_block = False
        split_gate_block = False
        split_fail = -1
        split_warn = -1
        split_rc = 0
        split_fresh = False
        if mode_effective in {"shadow", "split"}:
            tasks_run.append("A015_build_system_health_check.py:profile=e")
            split_started = _utc_now()
            split_step_started = utc_now_iso()
            split_rc, split_fresh = _run_a015_profile_e()
            elapsed_total += (_utc_now() - split_started).total_seconds()
            split_counts = _health_counts(E_SPLIT_CHECKLIST_PATH)
            split_fail = split_counts[0] if split_counts is not None else -1
            split_warn = split_counts[1] if split_counts is not None else -1
            append_step(
                manifest,
                name="A015_build_system_health_check.py:profile=e",
                script_or_function="A015_build_system_health_check.py",
                inputs=[str(E_SPLIT_CHECKLIST_PATH)],
                outputs=STEP_ARTIFACTS.get("A015_build_system_health_check.py:profile=e", []),
                rc=split_rc,
                notes=f"split_mode={mode_effective};split_fresh={'1' if split_fresh else '0'}",
                started_at=split_step_started,
                ended_at=utc_now_iso(),
            )
            if mode_effective == "split":
                if split_counts is None:
                    split_gate_block = bool(E_HEALTH_FAIL_CLOSED)
                else:
                    split_gate_block = bool(split_fail > 0)
                if split_rc == 2:
                    split_gate_block = True
            else:
                split_gate_block = bool(split_rc == 2 or (split_counts is not None and split_fail > 0))

            if mode_effective == "shadow":
                decision_match = legacy_gate_block == split_gate_block
                state = _update_e_shadow_streak(decision_match)
                _append_flow_selftest_compare(
                    {
                        "timestamp_utc": _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "cycle_start_utc": run_id,
                        "cycle": "E",
                        "mode_requested": mode_requested,
                        "mode_effective": mode_effective,
                        "legacy_fail_count": "",
                        "legacy_warn_count": "",
                        "legacy_gate_block": "0",
                        "split_fail_count": "" if split_fail < 0 else str(split_fail),
                        "split_warn_count": "" if split_warn < 0 else str(split_warn),
                        "split_gate_block": "1" if split_gate_block else "0",
                        "decision_match": "1" if decision_match else "0",
                        "a_match_streak": str(_safe_int(state.get("a_match_streak", 0), 0)),
                        "b_match_streak": str(_safe_int(state.get("b_match_streak", 0), 0)),
                        "e_match_streak": str(_safe_int(state.get("e_match_streak", 0), 0)),
                        "ready_for_cutover": "1" if bool(state.get("ready_for_cutover", False)) else "0",
                        "legacy_source": "none",
                        "split_source": E_SPLIT_CHECKLIST_PATH.name,
                        "notes": f"split_rc={split_rc};split_fresh={'1' if split_fresh else '0'}",
                    }
                )
                print(
                    "[E_cycle] split_shadow_compare "
                    f"split_fail={split_fail} split_warn={split_warn} "
                    f"candidate_gate_block={'1' if split_gate_block else '0'} "
                    f"a_match_streak={_safe_int(state.get('a_match_streak', 0), 0)} "
                    f"b_match_streak={_safe_int(state.get('b_match_streak', 0), 0)} "
                    f"e_match_streak={_safe_int(state.get('e_match_streak', 0), 0)} "
                    f"ready_for_cutover={'1' if bool(state.get('ready_for_cutover', False)) else '0'}"
                )

        if os.environ.get("E_WRITE_SHEETS", "0").strip() == "1":
            if mode_effective == "split" and split_gate_block:
                status = "gated_fail"
                error = (
                    f"e_split_gate_block fail_count={'' if split_fail < 0 else split_fail} "
                    f"warn_count={'' if split_warn < 0 else split_warn} "
                    f"fail_closed={'1' if E_HEALTH_FAIL_CLOSED else '0'} "
                    f"split_rc={split_rc} split_fresh={'1' if split_fresh else '0'}"
                )
                print(f"[E_cycle] split gate blocked publish: {error}")
            else:
                tasks_run.append("E010_publish_e_outputs.py")
                publish_started = utc_now_iso()
                elapsed_total += _run(
                    "E010_publish_e_outputs.py",
                    resolve_script_path(ROOT / "scripts", "E010_publish_e_outputs.py"),
                )
                append_step(
                    manifest,
                    name="E010_publish_e_outputs.py",
                    script_or_function="E010_publish_e_outputs.py",
                    inputs=[],
                    outputs=STEP_ARTIFACTS.get("E010_publish_e_outputs.py", []),
                    rc=0,
                    notes="",
                    started_at=publish_started,
                    ended_at=utc_now_iso(),
                )
    except Exception as exc:
        status = "fail"
        error = str(exc)
        append_step(
            manifest,
            name="E_cycle_exception",
            script_or_function="run_E_cycle.py",
            inputs=[],
            outputs=[],
            rc=1,
            notes=error,
            started_at=utc_now_iso(),
            ended_at=utc_now_iso(),
        )
        raise
    finally:
        finished = _utc_now()
        final_output_asof = _latest_output_asof()
        _append_run_log({
            "run_id": run_id,
            "started_utc": started.isoformat(),
            "finished_utc": finished.isoformat(),
            "status": status,
            "tasks_run": ";".join(tasks_run),
            "elapsed_seconds": f"{elapsed_total:.3f}",
            "expected_input_asof": expected_input_asof,
            "output_asof": final_output_asof,
            "asof_rerun_trigger": "1" if asof_rerun_trigger else "0",
            "error": error,
        })
        manifest_final_state = "completed" if str(status).strip().lower() == "success" else "failed"
        finalize_manifest(
            manifest,
            health_checklist_path=E_SPLIT_CHECKLIST_PATH,
            end_time=utc_now_iso(),
            final_state=manifest_final_state,
        )
        write_manifest(ROOT, manifest)
        _release_lock()


if __name__ == "__main__":
    main()

