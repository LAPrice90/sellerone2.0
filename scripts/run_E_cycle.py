from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
E_RUN_LOG = OUT / "e_run_log.jsonl"
E_DECISION_LOG = OUT / "e_decision_log.csv"
E_SPLIT_HEALTH_MODE = os.environ.get("E_SPLIT_HEALTH_MODE", "shadow").strip().lower() or "shadow"
E_SPLIT_CHECKLIST_PATH = Path(
    os.environ.get("E_SPLIT_CHECKLIST_PATH", OUT / "cycle_alerts" / "checklist_E_split.csv")
)
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
    ROOT / "scripts" / "E001_build_sales_velocity.py",
    ROOT / "scripts" / "E002_build_roi_snapshot.py",
    ROOT / "scripts" / "E003_build_restock_signals.py",
    ROOT / "scripts" / "E004_build_performance_summary.py",
    ROOT / "scripts" / "E005_build_study_report.py",
]


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
    E_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with E_RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")


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
    health_path = ROOT / "scripts" / "A015_build_system_health_check.py"
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
    run_id = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    started = _utc_now()
    status = "success"
    error = ""
    elapsed_total = 0.0
    tasks_run = []
    mode_requested = _normalize_split_mode(E_SPLIT_HEALTH_MODE, default="shadow")
    mode_effective = _effective_e_split_mode()

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
            # Allow one successful run per new UTC date even if 24h has not elapsed.
            if started.date() > last_success.date():
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
                        "error": note,
                    })
                    print({
                        "status": "skipped_cadence",
                        "run_id": run_id,
                        "cadence_hours": cadence_hours,
                        "next_allowed_utc": next_allowed.isoformat(),
                    })
                    return

    _ensure_decision_log()

    try:
        print(f"[E_cycle] split_health mode_requested={mode_requested} mode_effective={mode_effective}")
        for script in TASKS:
            tasks_run.append(script.name)
            elapsed_total += _run(script.name, script)

        if os.environ.get("E_WRITE_SHEETS", "0").strip() == "1":
            legacy_gate_block = False
            split_gate_block = False
            split_fail = -1
            split_warn = -1
            split_rc = 0
            split_fresh = False
            if mode_effective in {"shadow", "split"}:
                tasks_run.append("A015_build_system_health_check.py:profile=e")
                split_started = _utc_now()
                split_rc, split_fresh = _run_a015_profile_e()
                elapsed_total += (_utc_now() - split_started).total_seconds()
                split_counts = _health_counts(E_SPLIT_CHECKLIST_PATH)
                split_fail = split_counts[0] if split_counts is not None else -1
                split_warn = split_counts[1] if split_counts is not None else -1
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
                elapsed_total += _run("E010_publish_e_outputs.py", ROOT / "scripts" / "E010_publish_e_outputs.py")
    except Exception as exc:
        status = "fail"
        error = str(exc)
        raise
    finally:
        finished = _utc_now()
        _append_run_log({
            "run_id": run_id,
            "started_utc": started.isoformat(),
            "finished_utc": finished.isoformat(),
            "status": status,
            "tasks_run": ";".join(tasks_run),
            "elapsed_seconds": f"{elapsed_total:.3f}",
            "error": error,
        })


if __name__ == "__main__":
    main()
