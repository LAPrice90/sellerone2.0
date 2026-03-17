from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

import pandas as pd

OUT = Path("out")
DATA = Path("data")
CHECKLIST_CSV = OUT / "system_health_checklist.csv"
CYCLE_ALERT_DIR = OUT / "cycle_alerts"
ALERT_STATE_CSV = OUT / "system_health_alert_state.csv"
ALERT_STATE_A_CSV = OUT / "system_health_alert_state_A.csv"
ALERT_STATE_B_CSV = OUT / "system_health_alert_state_B.csv"
ALERT_STATE_E_CSV = OUT / "system_health_alert_state_E.csv"
ALERT_STATE_H_CSV = OUT / "system_health_alert_state_H.csv"
ALERT_SNOOZE_PATH = OUT / "locks" / "health_alert_snooze.json"
DETAIL_BLANK_COGS = OUT / "health_order_master_blank_cogs_lvl1plus.csv"
DETAIL_UNKNOWN_FEE_COUNTRIES = OUT / "health_unknown_fee_countries.csv"
FEE_RULES_PATH = Path("reference/fee_vat_rules.csv")
VAT_MODEL = OUT / "vat_country_model.csv"
FEE_MODEL = OUT / "fee_country_model.csv"
DETAIL_ORDERS_MISSING_ITEMS = OUT / "health_orders_missing_items_window.csv"
HEALTH_STATUS_CSV = OUT / "health_status.csv"
HEALTH_STATUS_A_CSV = OUT / "health_status_A.csv"
HEALTH_STATUS_B_CSV = OUT / "health_status_B.csv"
HEALTH_STATUS_E_CSV = OUT / "health_status_E.csv"
HEALTH_STATUS_H_CSV = OUT / "health_status_H.csv"
CHECKLIST_A_SPLIT_CSV = OUT / "cycle_alerts" / "checklist_A_split.csv"
CHECKLIST_B_SPLIT_CSV = OUT / "cycle_alerts" / "checklist_B_split.csv"
CHECKLIST_E_SPLIT_CSV = OUT / "cycle_alerts" / "checklist_E_split.csv"
CHECKLIST_H_SPLIT_CSV = OUT / "cycle_alerts" / "checklist_H_split.csv"
L1_MISSING_FEE_KEYS = OUT / "l1_missing_fee_keys.csv"
MISSING_TOKEN_ORDERS = OUT / "orders_missing_tokens.csv"
TRAINING_SET_PATH = Path("config/f_training_set.csv")
LAB_COHORT_PATH = Path("config/h_lab_cohort.csv")
HEAD_BOUNDARIES_PATH = Path("config/h_head_boundaries.csv")
SUPERVISOR_TACTICAL_RULES_PATH = Path("config/h_supervisor_tactical_rules.csv")
OFFICIAL_PILOT_SKU = os.environ.get("H_OFFICIAL_PILOT_SKU", "L1-54EX-56YC").strip() or "L1-54EX-56YC"
PROBE_EVENT_LOG_PATH = OUT / "h_worker_probe_event_log.csv"
PROBE_RESPONSE_LOG_PATH = OUT / "h_worker_probe_response_log.csv"
H_EXECUTIONER_ACTION_LOG_PATH = OUT / "h_executioner_action_log.csv"
H_SELLER_PROFILE_PATH = OUT / "h_seller_profiles.csv"
H_SELLER_SOI_PATH = OUT / "h_seller_of_interest.csv"
LISTING_OFFER_HISTORY = OUT / "listing_offer_history.csv"
LISTING_OFFER_SELLER_HISTORY = OUT / "listing_offer_seller_observation_history.csv"
PHASE1_SELLER_HISTORY = OUT / "phase1_seller_history.csv"
LISTING_OFFER_SNAPSHOT_GLOB = "listing_offer_snapshot_*.csv"
LISTING_OFFER_SELLER_SNAPSHOT_GLOB = "listing_offer_seller_snapshot_*.csv"
HOS_DAILY_MARKET_SNAPSHOT_GLOB = "hos_daily_market_snapshot_*.csv"
HOS_DAILY_REPORT_DIR = OUT / "reports" / "hos_daily"
HOS_DAILY_REPORT_CHART_DIR = HOS_DAILY_REPORT_DIR / "charts"
INVENTORY_HISTORY = OUT / "inventory_history.csv"
INBOUND_HISTORY = OUT / "inbound_history.csv"
INVENTORY_SNAPSHOT_GLOB = "inventory_snapshot_*.csv"
INBOUND_SNAPSHOT_GLOB = "inbound_snapshot_*.csv"
REFUND_ADJUSTMENT_HISTORY = OUT / "refund_adjustment_history.csv"
REFUND_ADJUSTMENT_SNAPSHOT_GLOB = "refund_adjustment_snapshot_*.csv"
API_CALL_LOG_JSONL = OUT / "api_call_log.jsonl"
API_RUN_LOG_CSV = OUT / "api_run_log.csv"
API_RATE_STATE_JSON = OUT / "api_rate_state.json"
SPAPI_LOCK_PATH = OUT / "locks" / "spapi.lock"
E_RUN_LOG_JSONL = OUT / "e_run_log.jsonl"
E_RUN_LOG_PATH_CANDIDATES = [
    OUT / "systems" / "E" / "live" / "e_run_log.jsonl",
    OUT / "e_run_log.jsonl",
]
PHASE1_SCOPE_PATH = OUT / "phase1_sku_scope.csv"
PHASE1_DAILY_INTEL_PATH = DATA / "sku_daily_intel.csv"
PHASE1_EXECUTION_LOG_PATH = DATA / "execution_log.csv"
FEES_FAILED_PATH = OUT / "fees_failed.csv"
H_PRICING_STATE_PATH_CANDIDATES = [
    OUT / "systems" / "H" / "live" / "h_pricing_cycle_state.json",
    OUT / "h_pricing_cycle_state.json",
]
B_CYCLE_LOG_PATH_CANDIDATES = [
    OUT / "systems" / "B" / "live" / "B_cycle.log",
    OUT / "B_cycle.log",
]
H_LOCK_PATH_CANDIDATES = [
    OUT / "systems" / "H" / "live" / "H_pricing_cycle.lock",
    OUT / "H_pricing_cycle.lock",
]
E_LOCK_PATH_CANDIDATES = [
    OUT / "systems" / "E" / "live" / "E_cycle.lock",
    OUT / "E_cycle.lock",
]
B_SHEET_SYNC_STATUS_PATH = OUT / "b_sheet_sync_status.csv"
H_CPT_ENDPOINT = "products_pricing_post_competitive_summary_batch"
H_FLOOR_VAT_POLICY_PATH = Path("config/h_floor_vat_policy.json")
H_TEMP_FLOOR_SNAPSHOT_PATH = OUT / "sku_temp_floor_snapshot.csv"
H_FLOOR_TRUTH_TRACE_PATH = OUT / "h_floor_truth_trace.csv"
H_LEGACY_EXECUTION_LOG_PATH = DATA / "repricing_live_execution_log.csv"
H_KILL_SWITCH_PATH = OUT / "locks" / "h_pricing_cycle.kill"
ORPHAN_SCOPE_START_DATE = os.environ.get("ORPHAN_SCOPE_START_DATE", "").strip()
# Default scope start to keep pre-window orphans from failing health checks.
if not ORPHAN_SCOPE_START_DATE:
    ORPHAN_SCOPE_START_DATE = "2025-11-01"
ORPHAN_IGNORE_ORDER_IDS_FILE = os.environ.get("ORPHAN_IGNORE_ORDER_IDS_FILE", "").strip()
# Default ignore list to standard file if env var is not set.
if not ORPHAN_IGNORE_ORDER_IDS_FILE:
    default_ignore = OUT / "orphan_ignore_orders_combined.csv"
    if default_ignore.exists():
        ORPHAN_IGNORE_ORDER_IDS_FILE = str(default_ignore)


def _file_info(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {"exists": "no", "size_bytes": "0", "mtime_utc": ""}
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return {"exists": "yes", "size_bytes": str(stat.st_size), "mtime_utc": mtime}


def _h_cycle_pause_requested() -> bool:
    return H_KILL_SWITCH_PATH.exists()


def _h_cycle_running() -> bool:
    lock_path = _first_existing_path(H_LOCK_PATH_CANDIDATES)
    if lock_path is None:
        return False
    try:
        payload = lock_path.read_text(encoding="utf-8")
    except Exception:
        return False
    pid = _parse_lock_pid(payload)
    if pid is None:
        # Lock exists but pid is unreadable - treat as running to avoid false timing WARNs.
        return True
    return _pid_alive(pid)


def _read_csv(path: Path, usecols: List[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, usecols=usecols)


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_first_json(paths: List[Path]) -> Tuple[Dict[str, object], Path | None]:
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload, path
        except Exception:
            continue
    return {}, None


def _first_existing_path(paths: List[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _pid_alive(pid: int) -> bool:
    pid_int = int(pid)
    try:
        os.kill(pid_int, 0)
        return True
    except PermissionError:
        # Process exists but signal probe is not permitted on this platform/user.
        return True
    except Exception:
        pass
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_int}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = (result.stdout or "").strip().lower()
            if "no tasks are running" in out:
                return False
            return str(pid_int) in out
        except Exception:
            return False
    return False


def _parse_lock_pid(payload: str) -> int | None:
    parts = [p.strip() for p in str(payload or "").split("|") if p.strip()]
    for part in parts:
        if part.startswith("pid="):
            try:
                return int(part.split("=", 1)[1].strip())
            except Exception:
                return None
    return None


def _to_dt(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _add(rows: List[Dict[str, str]], check: str, status: str, value: str, notes: str = "") -> None:
    rows.append({"check": check, "status": status, "value": value, "notes": notes})


def _status_from_gap(hours_gap: float) -> str:
    if hours_gap <= 2:
        return "ok"
    if hours_gap <= 12:
        return "warn"
    return "fail"


def _cycle_for_check(check: str) -> str:
    name = str(check or "").strip().lower()
    if not name:
        return "shared"
    if name.startswith("a_"):
        return "A"
    if name.startswith("h_"):
        return "H"
    if name.startswith("e_"):
        return "E"
    if name.startswith("c_"):
        return "C"
    if name.startswith("f_"):
        return "F"
    if name.startswith("z_"):
        return "Z"
    b_prefixes = (
        "b_",
        "l1_",
        "l2_",
        "l3_",
        "order_master_",
        "orders_",
        "token_",
        "orphan_",
    )
    if name.startswith(b_prefixes):
        return "B"
    b_exact = {
        "l1_keys_missing_in_master",
        "order_master_orphans_count",
        "order_master_blank_cogs_lvl1plus",
        "l3_orphans_count",
    }
    if name in b_exact:
        return "B"
    return "shared"


def _write_cycle_alert_files(df_out: pd.DataFrame) -> None:
    CYCLE_ALERT_DIR.mkdir(parents=True, exist_ok=True)
    df_all = df_out.copy()
    df_all["cycle"] = df_all.get("check", "").map(_cycle_for_check)
    # canonical full snapshot in cycle folder
    df_all.to_csv(CYCLE_ALERT_DIR / "checklist_all.csv", index=False)

    for cycle in ["A", "B", "H", "E", "C", "F", "Z", "shared"]:
        scoped = df_all[df_all["cycle"] == cycle].copy()
        scoped.to_csv(CYCLE_ALERT_DIR / f"checklist_{cycle}.csv", index=False)

    summary_rows: List[Dict[str, str]] = []
    for cycle in ["all", "A", "B", "H", "E", "C", "F", "Z", "shared"]:
        scoped = df_all if cycle == "all" else df_all[df_all["cycle"] == cycle]
        status = scoped.get("status", pd.Series(dtype=str)).astype(str).str.lower()
        fail_count = int(status.eq("fail").sum())
        warn_count = int(status.eq("warn").sum())
        summary_rows.append(
            {
                "cycle": cycle,
                "rows": str(int(len(scoped.index))),
                "fail_count": str(fail_count),
                "warn_count": str(warn_count),
            }
        )
    pd.DataFrame(summary_rows).to_csv(CYCLE_ALERT_DIR / "summary.csv", index=False)


def _normalize_profile(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"global", "a", "b", "e", "h"}:
        return raw
    return "global"


def _default_checklist_for_profile(profile: str) -> Path:
    if profile == "a":
        return CHECKLIST_A_SPLIT_CSV
    if profile == "b":
        return CHECKLIST_B_SPLIT_CSV
    if profile == "e":
        return CHECKLIST_E_SPLIT_CSV
    if profile == "h":
        return CHECKLIST_H_SPLIT_CSV
    return CHECKLIST_CSV


def _default_alert_state_for_profile(profile: str) -> Path:
    if profile == "a":
        return ALERT_STATE_A_CSV
    if profile == "b":
        return ALERT_STATE_B_CSV
    if profile == "e":
        return ALERT_STATE_E_CSV
    if profile == "h":
        return ALERT_STATE_H_CSV
    return ALERT_STATE_CSV


def _default_health_status_for_profile(profile: str) -> Path:
    if profile == "a":
        return HEALTH_STATUS_A_CSV
    if profile == "b":
        return HEALTH_STATUS_B_CSV
    if profile == "e":
        return HEALTH_STATUS_E_CSV
    if profile == "h":
        return HEALTH_STATUS_H_CSV
    return HEALTH_STATUS_CSV


def _profile_filter_mask(df: pd.DataFrame, profile: str) -> pd.Series:
    if "check" not in df.columns:
        return pd.Series([False] * len(df.index), index=df.index)
    cycles = df["check"].astype(str).map(_cycle_for_check)
    if profile == "a":
        return cycles.eq("A")
    if profile == "b":
        return cycles.eq("B")
    if profile == "e":
        return cycles.eq("E")
    if profile == "h":
        return cycles.eq("H")
    return pd.Series([True] * len(df.index), index=df.index)


def _stabilize_index(df: pd.DataFrame) -> pd.DataFrame:
    """Force a plain Int64 index to avoid intermittent RangeIndex C-extension crashes."""
    out = df.copy()
    try:
        out.index = pd.Index([int(i) for i in range(int(out.shape[0]))], dtype="int64")
    except Exception:
        pass
    return out


def _build_arg_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build system health checklist", add_help=add_help)
    parser.add_argument(
        "--profile",
        choices=["global", "a", "b", "e", "h"],
        default="global",
        help="Health profile scope. global keeps existing full-system behavior.",
    )
    parser.add_argument(
        "--checklist-path",
        default="",
        help="Optional output path override for checklist CSV.",
    )
    parser.add_argument(
        "--alert-state-path",
        default="",
        help="Optional output path override for alert aging state CSV.",
    )
    parser.add_argument(
        "--health-status-path",
        default="",
        help="Optional output path override for health status CSV.",
    )
    parser.add_argument(
        "--no-toast",
        action="store_true",
        help="Disable toast notifications for this run.",
    )
    return parser


def _parse_cli_args(argv: List[str] | None = None, *, strict: bool = True) -> argparse.Namespace:
    parser = _build_arg_parser(add_help=strict)
    if strict:
        return parser.parse_args(argv)
    args, _unknown = parser.parse_known_args(argv)
    return args


def _resolve_runtime_paths(args: argparse.Namespace) -> dict:
    profile = _normalize_profile(getattr(args, "profile", "global"))
    checklist_path = Path(getattr(args, "checklist_path", "") or _default_checklist_for_profile(profile))
    alert_state_path = Path(getattr(args, "alert_state_path", "") or _default_alert_state_for_profile(profile))
    health_status_path = Path(getattr(args, "health_status_path", "") or _default_health_status_for_profile(profile))
    no_toast = bool(getattr(args, "no_toast", False))
    return {
        "profile": profile,
        "checklist_path": checklist_path,
        "alert_state_path": alert_state_path,
        "health_status_path": health_status_path,
        "no_toast": no_toast,
    }


def _schema_check(rows: List[Dict[str, str]], name: str, path: Path, required_cols: List[str], optional: bool = False) -> None:
    if not path.exists():
        status = "warn" if optional else "fail"
        _add(rows, name, status, "missing", f"path {path}")
        return
    try:
        df = pd.read_csv(path, nrows=1, dtype=str)
    except Exception as exc:
        _add(rows, name, "fail", "read_error", str(exc))
        return
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        _add(rows, name, "fail" if not optional else "warn", "missing_cols", ",".join(missing))
    else:
        _add(rows, name, "ok", "ok", "")


def _phase1_contract_checks(rows: List[Dict[str, str]], path: Path) -> None:
    if not path.exists():
        _add(rows, "h_phase1_contract_types", "warn", "missing", f"path {path}")
        _add(rows, "h_phase1_history_idempotent", "warn", "missing", f"path {path}")
        return

    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        _add(rows, "h_phase1_contract_types", "fail", "read_error", str(exc))
        _add(rows, "h_phase1_history_idempotent", "fail", "read_error", str(exc))
        return

    if df.empty:
        _add(rows, "h_phase1_contract_types", "warn", "empty", "")
        _add(rows, "h_phase1_history_idempotent", "warn", "empty", "")
        return

    required_non_null = [
        "timestamp_utc",
        "asof_date",
        "marketplace",
        "sku",
        "asin",
        "seller_id",
        "seller_seen_flag",
        "source",
    ]
    bad_non_null = 0
    for col in required_non_null:
        if col not in df.columns:
            bad_non_null += len(df)
            continue
        bad_non_null += int(df[col].astype(str).str.strip().eq("").sum())

    bad_date = 0
    if "asof_date" in df.columns:
        asof = df["asof_date"].astype(str).str.strip()
        non_blank = asof.ne("")
        bad_date = int((non_blank & pd.to_datetime(asof, format="%Y-%m-%d", errors="coerce").isna()).sum())
    else:
        bad_date = len(df)

    datetime_cols = ["timestamp_utc", "first_seen_timestamp", "last_seen_timestamp"]
    bad_datetime = 0
    for col in datetime_cols:
        if col not in df.columns:
            continue
        vals = df[col].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_datetime += int((non_blank & pd.to_datetime(vals, errors="coerce", utc=True).isna()).sum())

    numeric_cols = [
        "continuous_presence_hours",
        "absence_gap_hours",
        "offer_price_gbp",
        "min_price_seen_gbp",
        "max_price_seen_gbp",
        "median_price_seen_gbp",
        "time_at_min_price_hours",
        "time_at_max_price_hours",
        "price_move_initiations",
        "follow_events",
        "reaction_lag_minutes",
        "floor_set_events",
        "min_delivery_days",
        "max_delivery_days",
        "delivery_range_days",
        "delivery_delta_vs_fastest_days",
        "our_price",
        "our_price_changes",
        "manual_interventions",
    ]
    bad_numeric = 0
    for col in numeric_cols:
        if col not in df.columns:
            continue
        vals = df[col].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_numeric += int((non_blank & pd.to_numeric(vals, errors="coerce").isna()).sum())

    allowed_binary = {"0", "1"}
    binary_cols = ["seller_seen_flag", "reentry_after_absence_flag", "is_prime"]
    bad_binary = 0
    for col in binary_cols:
        if col not in df.columns:
            continue
        vals = df[col].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_binary += int((non_blank & ~vals.isin(allowed_binary)).sum())

    bad_direction = 0
    if "directional_bias" in df.columns:
        vals = df["directional_bias"].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_direction = int((non_blank & ~vals.isin({"up", "down", "flat"})).sum())

    bad_channel = 0
    if "fulfilment_channel" in df.columns:
        vals = df["fulfilment_channel"].astype(str).str.strip()
        non_blank = vals.ne("")
        bad_channel = int((non_blank & ~vals.isin({"FBA", "FBM", "Unknown"})).sum())

    bad_types_total = bad_non_null + bad_date + bad_datetime + bad_numeric + bad_binary + bad_direction + bad_channel
    type_notes = (
        f"non_null={bad_non_null};bad_date={bad_date};bad_datetime={bad_datetime};"
        f"bad_numeric={bad_numeric};bad_binary={bad_binary};bad_direction={bad_direction};bad_channel={bad_channel}"
    )
    _add(
        rows,
        "h_phase1_contract_types",
        "ok" if bad_types_total == 0 else "fail",
        str(bad_types_total),
        type_notes,
    )

    idempotent_keys = ["asof_date", "marketplace", "sku", "asin", "seller_id"]
    missing_keys = [c for c in idempotent_keys if c not in df.columns]
    if missing_keys:
        _add(rows, "h_phase1_history_idempotent", "fail", "missing_keys", ",".join(missing_keys))
    else:
        dup_count = int(df.duplicated(subset=idempotent_keys, keep=False).sum())
        _add(rows, "h_phase1_history_idempotent", "ok" if dup_count == 0 else "fail", str(dup_count), "global_key_check")


def _schema_check_jsonl(rows: List[Dict[str, str]], name: str, path: Path, required_cols: List[str], optional: bool = False) -> None:
    if not path.exists():
        status = "warn" if optional else "fail"
        _add(rows, name, status, "missing", f"path {path}")
        return
    try:
        last_payload: Dict[str, object] | None = None
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    last_payload = obj
    except Exception as exc:
        _add(rows, name, "fail", "read_error", str(exc))
        return
    if last_payload is None:
        status = "warn" if optional else "fail"
        _add(rows, name, status, "empty", "")
        return
    present = set([str(k) for k in last_payload.keys()])
    missing = [c for c in required_cols if c not in present]
    if missing:
        _add(rows, name, "fail" if not optional else "warn", "missing_cols", ",".join(missing))
    else:
        _add(rows, name, "ok", "ok", "")


def _schema_check_json_object(
    rows: List[Dict[str, str]],
    name: str,
    path: Path,
    required_keys: List[str],
    optional: bool = False,
) -> None:
    if not path.exists():
        status = "warn" if optional else "fail"
        _add(rows, name, status, "missing", f"path {path}")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _add(rows, name, "fail", "read_error", str(exc))
        return
    if not isinstance(payload, dict):
        _add(rows, name, "fail" if not optional else "warn", "invalid_type", type(payload).__name__)
        return
    missing = [k for k in required_keys if k not in payload]
    if missing:
        _add(rows, name, "fail" if not optional else "warn", "missing_keys", ",".join(missing))
        return
    _add(rows, name, "ok", "ok", "")


def _read_last_health_status(path: Path = HEALTH_STATUS_CSV) -> str:
    if not path.exists():
        return ""
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception:
        return ""
    if df.empty or "status" not in df.columns:
        return ""
    return str(df.iloc[-1]["status"]).strip().upper()


def _read_alert_state(path: Path) -> pd.DataFrame:
    cols = ["check", "status", "first_seen_utc", "last_seen_utc", "consecutive_runs"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.DataFrame(columns=cols)
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df[cols]


def _apply_alert_aging(df_out: pd.DataFrame, state_path: Path, now_utc: datetime) -> pd.DataFrame:
    prev = _read_alert_state(state_path)
    prev_map = {
        str(r["check"]).strip(): {
            "status": str(r["status"]).strip().lower(),
            "first_seen_utc": str(r["first_seen_utc"]).strip(),
            "last_seen_utc": str(r["last_seen_utc"]).strip(),
            "consecutive_runs": str(r["consecutive_runs"]).strip(),
        }
        for _, r in prev.iterrows()
    }

    first_seen_vals: List[str] = []
    last_seen_vals: List[str] = []
    streak_vals: List[str] = []
    age_hours_vals: List[str] = []
    next_state_rows: List[Dict[str, str]] = []
    now_iso = now_utc.isoformat()

    for _, row in df_out.iterrows():
        check = str(row.get("check", "")).strip()
        status = str(row.get("status", "")).strip().lower()
        if status not in {"fail", "warn"}:
            first_seen_vals.append("")
            last_seen_vals.append("")
            streak_vals.append("")
            age_hours_vals.append("")
            continue

        prev_row = prev_map.get(check, {})
        prev_status = str(prev_row.get("status", "")).strip().lower()
        prev_first = str(prev_row.get("first_seen_utc", "")).strip()
        prev_streak_raw = str(prev_row.get("consecutive_runs", "")).strip()
        try:
            prev_streak = int(prev_streak_raw) if prev_streak_raw else 0
        except Exception:
            prev_streak = 0

        if prev_status == status and prev_first:
            first_seen = prev_first
            streak = prev_streak + 1 if prev_streak > 0 else 1
        else:
            first_seen = now_iso
            streak = 1

        age_hours = ""
        try:
            first_dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
            if first_dt.tzinfo is None:
                first_dt = first_dt.replace(tzinfo=timezone.utc)
            age_hours = f"{max((now_utc - first_dt).total_seconds() / 3600.0, 0.0):.2f}"
        except Exception:
            age_hours = ""

        first_seen_vals.append(first_seen)
        last_seen_vals.append(now_iso)
        streak_vals.append(str(streak))
        age_hours_vals.append(age_hours)
        next_state_rows.append(
            {
                "check": check,
                "status": status,
                "first_seen_utc": first_seen,
                "last_seen_utc": now_iso,
                "consecutive_runs": str(streak),
            }
        )

    df_out = df_out.copy()
    df_out["alert_first_seen_utc"] = first_seen_vals
    df_out["alert_last_seen_utc"] = last_seen_vals
    df_out["alert_consecutive_runs"] = streak_vals
    df_out["alert_age_hours"] = age_hours_vals
    pd.DataFrame(next_state_rows, columns=["check", "status", "first_seen_utc", "last_seen_utc", "consecutive_runs"]).to_csv(
        state_path, index=False
    )
    return df_out


def _latest_snapshot(glob_name: str) -> Path | None:
    candidates = sorted(OUT.glob(glob_name))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _max_asof_date(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        df = pd.read_csv(path, usecols=["asof_date"], dtype=str).fillna("")
    except Exception:
        return ""
    if df.empty or "asof_date" not in df.columns:
        return ""
    vals = (
        df["asof_date"]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
    )
    if vals.empty:
        return ""
    return str(vals.max())


def _safe_int(value: object) -> int:
    try:
        text = str(value or "").strip()
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _safe_float(value: object) -> float | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        out = float(text)
        if out != out:
            return None
        return out
    except Exception:
        return None


def _safe_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _read_jsonl_rows(path: Path) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    if not path.exists():
        return out
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    out.append(payload)
    except Exception:
        return []
    return out


def _parse_utc_ts(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _iter_b_cycle_log_events(path: Path, cutoff: datetime) -> List[Dict[str, object]]:
    events: List[Dict[str, object]] = []
    if not path.exists():
        return events
    line_re = re.compile(r"^(?P<ts>\S+)\s+\[(?P<cycle>[^\]]+)\]\s+(?P<msg>.*)$")
    event_re = re.compile(r"^(ok|warn|fail|skip)\s+([^\s]+)", re.IGNORECASE)
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for idx, raw in enumerate(fh):
                line = raw.strip()
                if not line:
                    continue
                m = line_re.match(line)
                if not m:
                    continue
                ts = _parse_utc_ts(m.group("ts"))
                if ts is not None and ts < cutoff:
                    continue
                msg = m.group("msg").strip()
                em = event_re.match(msg)
                if not em:
                    continue
                event = str(em.group(1)).strip().lower()
                script = str(em.group(2)).strip()
                cycle = str(m.group("cycle")).strip()
                events.append(
                    {
                        "idx": idx,
                        "ts": ts.isoformat() if ts is not None else "",
                        "cycle": cycle,
                        "event": event,
                        "script": script,
                        "line": line,
                    }
                )
    except Exception:
        return []
    return events


def _fees_failed_rows_today(path: Path, now_utc: datetime) -> Dict[str, object]:
    result: Dict[str, object] = {
        "count": 0,
        "sample_skus": [],
        "notes": "",
        "read_error": False,
    }
    today = now_utc.strftime("%Y-%m-%d")
    if not path.exists():
        result["notes"] = f"path={path};missing"
        return result

    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception as exc:
        result["read_error"] = True
        result["notes"] = f"path={path};read_error={exc}"
        return result

    if df.empty:
        result["notes"] = f"path={path};total_rows=0"
        return result

    ts_col = ""
    for candidate in [
        "failure_recorded_utc",
        "recorded_utc",
        "generated_at_utc",
        "run_utc",
        "event_ts_utc",
        "timestamp_utc",
        "created_utc",
    ]:
        if candidate in df.columns:
            ts_col = candidate
            break

    if ts_col:
        ts = _to_dt(df[ts_col])
        mask_today = ts.notna() & ts.dt.strftime("%Y-%m-%d").eq(today)
        rows_today = df.loc[mask_today].copy()
    else:
        try:
            mtime_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except Exception:
            mtime_dt = None
        if mtime_dt is not None and mtime_dt.strftime("%Y-%m-%d") == today:
            rows_today = df.copy()
        else:
            rows_today = df.iloc[0:0].copy()

    sku_col = "seller_sku" if "seller_sku" in rows_today.columns else ("sku" if "sku" in rows_today.columns else "")
    sample_skus: List[str] = []
    if sku_col:
        for val in rows_today[sku_col].astype(str).str.strip().tolist():
            if val and val not in sample_skus:
                sample_skus.append(val)
            if len(sample_skus) >= 5:
                break

    count = int(len(rows_today.index))
    result["count"] = count
    result["sample_skus"] = sample_skus
    result["notes"] = (
        f"date={today};path={path};total_rows={len(df.index)};"
        f"rows_today={count};ts_source={ts_col or 'file_mtime'}"
    )
    return result


def _b_cycle_recent_fail_stats(path: Path, window_hours: float) -> Dict[str, object]:
    # Do not depend on rolling time windows for this check.
    # Evaluate only the latest completed B cycle so old fail lines cannot keep alerting.
    _ = window_hours
    cutoff = datetime.now(timezone.utc) - timedelta(days=3650)
    events_all = _iter_b_cycle_log_events(path, cutoff=cutoff)
    latest_cycle = str(events_all[-1].get("cycle", "")).strip() if events_all else ""
    events = [e for e in events_all if str(e.get("cycle", "")).strip() == latest_cycle] if latest_cycle else []
    fail_events: List[Dict[str, object]] = []
    ignored_non_actionable = 0
    for event in events:
        if str(event.get("event", "")).strip().lower() != "fail":
            continue
        script = str(event.get("script", "")).strip()
        line = str(event.get("line", "")).strip().lower()
        # Ignore legacy/global end-of-cycle A015 fail lines here.
        # They are health summaries, not actionable B step failures.
        if script == "A015_build_system_health_check.py" and "end_of_cycle" in line:
            ignored_non_actionable += 1
            continue
        fail_events.append(event)
    latest_non_fail_idx: Dict[Tuple[str, str], int] = {}
    for event in events:
        event_name = str(event.get("event", "")).strip().lower()
        if event_name not in {"ok", "warn", "skip"}:
            continue
        key = (str(event.get("cycle", "")), str(event.get("script", "")))
        latest_non_fail_idx[key] = int(event.get("idx", 0))

    unresolved_events: List[Dict[str, object]] = []
    recovered_count = 0
    for fail_event in fail_events:
        key = (str(fail_event.get("cycle", "")), str(fail_event.get("script", "")))
        fail_idx = int(fail_event.get("idx", 0))
        if int(latest_non_fail_idx.get(key, -1)) > fail_idx:
            recovered_count += 1
        else:
            unresolved_events.append(fail_event)

    unresolved_sample = [str(event.get("line", "")) for event in unresolved_events[:5]]
    return {
        "latest_cycle": latest_cycle,
        "raw_fail_count": len(fail_events),
        "recovered_count": recovered_count,
        "unresolved_count": len(unresolved_events),
        "unresolved_sample": unresolved_sample,
        "ignored_non_actionable": ignored_non_actionable,
    }


def _h_floor_policy_checks(rows: List[Dict[str, str]], now_utc: datetime) -> None:
    today = now_utc.strftime("%Y-%m-%d")
    policy_raw = _read_json(H_FLOOR_VAT_POLICY_PATH, default={})
    if not isinstance(policy_raw, dict) or not policy_raw:
        _add(
            rows,
            "h_floor_vat_policy_config",
            "fail",
            "missing_or_invalid",
            f"path={H_FLOOR_VAT_POLICY_PATH}",
        )
        _add(rows, "h_floor_phase1_cogs_basis_drift", "warn", "not_checked", "policy_missing")
        _add(rows, "h_floor_legacy_cogs_basis_drift", "warn", "not_checked", "policy_missing")
        return

    vat_registered = _safe_bool(policy_raw.get("vat_registered"), True)
    recover_cogs_vat = _safe_bool(policy_raw.get("recover_input_vat_on_cogs"), True)
    recover_fee_vat = _safe_bool(policy_raw.get("recover_input_vat_on_fees"), True)
    formula = str(policy_raw.get("formula_version", "") or "").strip()
    note = str(policy_raw.get("note", "") or "").strip()
    policy_ok = vat_registered and recover_cogs_vat and recover_fee_vat
    _add(
        rows,
        "h_floor_vat_policy_config",
        "ok" if policy_ok else "fail",
        "ok" if policy_ok else "unexpected_values",
        (
            f"vat_registered={int(vat_registered)};recover_input_vat_on_cogs={int(recover_cogs_vat)};"
            f"recover_input_vat_on_fees={int(recover_fee_vat)};formula_version={formula};note={note}"
        ),
    )

    if not recover_cogs_vat:
        _add(
            rows,
            "h_floor_phase1_cogs_basis_drift",
            "warn",
            "not_checked",
            "policy recover_input_vat_on_cogs=0; cogs drift check skipped",
        )
        _add(
            rows,
            "h_floor_legacy_cogs_basis_drift",
            "warn",
            "not_checked",
            "policy recover_input_vat_on_cogs=0; cogs drift check skipped",
        )
        return

    snapshot = _read_csv(H_TEMP_FLOOR_SNAPSHOT_PATH)
    if snapshot.empty:
        _add(
            rows,
            "h_floor_phase1_cogs_basis_drift",
            "warn",
            "missing_snapshot",
            f"path={H_TEMP_FLOOR_SNAPSHOT_PATH}",
        )
    else:
        required_snapshot_cols = {"asof_utc", "sku", "cogs_total_gbp"}
        if not required_snapshot_cols.issubset(set(snapshot.columns)):
            _add(
                rows,
                "h_floor_phase1_cogs_basis_drift",
                "warn",
                "missing_columns",
                f"snapshot_required={','.join(sorted(required_snapshot_cols))}",
            )
        else:
            token_lookup: Dict[str, float] = {}
            token_live = _read_csv(OUT / "token_ledger_live.csv")
            if not token_live.empty and {"seller_sku", "cost_per_unit"}.issubset(set(token_live.columns)):
                live = token_live.copy()
                live["sku_key"] = live["seller_sku"].astype(str).str.strip().str.upper()
                live["cost_num"] = pd.to_numeric(live["cost_per_unit"], errors="coerce")
                live["status_key"] = live.get("status", "").astype(str).str.strip().str.lower()
                live = live.loc[(live["sku_key"] != "") & live["cost_num"].notna() & live["cost_num"].gt(0.0)].copy()
                if not live.empty:
                    available = live.loc[live["status_key"].eq("available")].copy()
                    base = available if not available.empty else live
                    if "sort_rank" in base.columns:
                        base["sort_rank_num"] = pd.to_numeric(base.get("sort_rank", ""), errors="coerce")
                    elif "lot_rank_num" in base.columns:
                        base["sort_rank_num"] = pd.to_numeric(base.get("lot_rank_num", ""), errors="coerce")
                    else:
                        base["sort_rank_num"] = pd.Series([float("nan")] * len(base), index=base.index)
                    if "received_date" in base.columns:
                        base["received_dt"] = pd.to_datetime(
                            base.get("received_date", ""),
                            errors="coerce",
                            utc=True,
                            format="ISO8601",
                        )
                    else:
                        base["received_dt"] = pd.NaT
                    base["sort_rank_num"] = base["sort_rank_num"].fillna(10**12)
                    base["received_dt"] = base["received_dt"].fillna(pd.Timestamp("2262-04-11T00:00:00Z"))
                    base = base.sort_values(["sku_key", "sort_rank_num", "received_dt"], kind="stable")
                    first = base.groupby("sku_key", as_index=False).head(1).copy()
                    token_lookup = {
                        str(r["sku_key"]).strip().upper(): float(r["cost_num"])
                        for _, r in first.iterrows()
                    }

            token_hist = _read_csv(OUT / "token_cogs_ledger.csv")
            if not token_hist.empty and {"seller_sku", "cogs_exvat", "cogs_total"}.issubset(set(token_hist.columns)):
                hist = token_hist.copy()
                hist["sku_key"] = hist["seller_sku"].astype(str).str.strip().str.upper()
                hist["cogs_ex_num"] = pd.to_numeric(hist["cogs_exvat"], errors="coerce")
                hist["cogs_total_num"] = pd.to_numeric(hist["cogs_total"], errors="coerce")
                if recover_cogs_vat:
                    hist["basis_num"] = hist["cogs_ex_num"].where(hist["cogs_ex_num"].gt(0.0), hist["cogs_total_num"])
                else:
                    hist["basis_num"] = hist["cogs_total_num"].where(hist["cogs_total_num"].gt(0.0), hist["cogs_ex_num"])
                hist = hist.loc[(hist["sku_key"] != "") & hist["basis_num"].notna() & hist["basis_num"].gt(0.0)].copy()
                if not hist.empty:
                    med = hist.groupby("sku_key")["basis_num"].median().to_dict()
                    for sku_key, val in med.items():
                        if sku_key not in token_lookup:
                            token_lookup[str(sku_key).strip().upper()] = float(val)

            snap = snapshot.copy()
            snap["asof_utc_key"] = snap["asof_utc"].astype(str).str.strip()
            snap["asof_date"] = snap["asof_utc_key"].str[:10]
            snap = snap.loc[snap["asof_date"].eq(today)].copy()
            if snap.empty:
                _add(
                    rows,
                    "h_floor_phase1_cogs_basis_drift",
                    "ok",
                    "0",
                    f"date={today};rows_today=0",
                )
            else:
                latest_asof = str(snap["asof_utc_key"].max())
                snap = snap.loc[snap["asof_utc_key"].eq(latest_asof)].copy()
                compared = 0
                missing_expected = 0
                mismatches: List[str] = []
                for _, row in snap.iterrows():
                    sku_key = str(row.get("sku", "") or "").strip().upper()
                    if not sku_key:
                        continue
                    expected = token_lookup.get(sku_key)
                    observed = _safe_float(row.get("cogs_total_gbp", ""))
                    if observed is None:
                        continue
                    if expected is None:
                        missing_expected += 1
                        continue
                    compared += 1
                    if abs(observed - expected) > 0.01:
                        mismatches.append(f"{sku_key}:{observed:.2f}!={expected:.2f}")
                _add(
                    rows,
                    "h_floor_phase1_cogs_basis_drift",
                    "ok" if not mismatches else "fail",
                    str(len(mismatches)),
                    (
                        f"date={today};latest_asof={latest_asof};rows_in_run={len(snap.index)};compared={compared};"
                        f"missing_expected={missing_expected};sample={','.join(mismatches[:5])}"
                    ),
                )

    legacy = _read_csv(H_LEGACY_EXECUTION_LOG_PATH)
    required_legacy_cols = {"event_ts_utc", "profit_floor_cogs_exvat_gbp", "profit_floor_cogs_total_gbp"}
    if legacy.empty or not required_legacy_cols.issubset(set(legacy.columns)):
        _add(
            rows,
            "h_floor_legacy_cogs_basis_drift",
            "ok",
            "0",
            f"path={H_LEGACY_EXECUTION_LOG_PATH};rows={len(legacy.index)}",
        )
    else:
        leg = legacy.copy()
        leg["event_date"] = leg["event_ts_utc"].astype(str).str.strip().str[:10]
        leg = leg.loc[leg["event_date"].eq(today)].copy()
        leg["cogs_ex"] = pd.to_numeric(leg["profit_floor_cogs_exvat_gbp"], errors="coerce")
        leg["cogs_total"] = pd.to_numeric(leg["profit_floor_cogs_total_gbp"], errors="coerce")
        cmp = leg.loc[leg["cogs_ex"].notna() & leg["cogs_total"].notna()].copy()
        drift = cmp.loc[cmp["cogs_total"] > (cmp["cogs_ex"] + 0.01)].copy()
        _add(
            rows,
            "h_floor_legacy_cogs_basis_drift",
            "ok" if drift.empty else "fail",
            str(len(drift.index)),
            (
                f"date={today};rows_today={len(leg.index)};compared={len(cmp.index)};"
                f"sample={','.join(drift.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
            ),
        )

    trace = _read_csv(H_FLOOR_TRUTH_TRACE_PATH)
    required_trace_cols = {
        "asof_utc",
        "sku",
        "floor_total_gbp",
        "sale_exvat_gbp",
        "vat_rate",
        "cogs_exvat_gbp",
        "fba_exvat_gbp",
        "referral_amount_gbp",
        "digital_fee_exvat_gbp",
        "margin_exvat_gbp",
        "source_referral",
        "band_bucket",
        "reason_codes_csv",
        "used_order_data_flag",
    }
    h_paused = _h_cycle_pause_requested()
    h_running = _h_cycle_running()
    if trace.empty:
        msg = f"path={H_FLOOR_TRUTH_TRACE_PATH}"
        if h_paused:
            note = f"{msg}; h_cycle_pause_requested=1"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", note)
        elif h_running:
            note = f"{msg}; h_cycle_running=1; awaiting_trace_rows"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", note)
        else:
            _add(rows, "h_floor_no_order_inputs", "warn", "not_checked", msg)
            _add(rows, "h_floor_referral_band_integrity", "warn", "not_checked", msg)
            _add(rows, "h_floor_referral_source_coverage", "warn", "not_checked", msg)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "warn", "not_checked", msg)
            _add(rows, "h_floor_formula_consistency", "warn", "not_checked", msg)
        return

    if not required_trace_cols.issubset(set(trace.columns)):
        missing_cols = ",".join(sorted(required_trace_cols.difference(set(trace.columns))))
        _add(rows, "h_floor_no_order_inputs", "fail", "missing_columns", missing_cols)
        _add(rows, "h_floor_referral_band_integrity", "fail", "missing_columns", missing_cols)
        _add(rows, "h_floor_referral_source_coverage", "fail", "missing_columns", missing_cols)
        _add(rows, "h_floor_referral_source_coverage_parked_observability", "fail", "missing_columns", missing_cols)
        _add(rows, "h_floor_formula_consistency", "fail", "missing_columns", missing_cols)
        return

    tr = trace.copy()
    tr["asof_date"] = tr["asof_utc"].astype(str).str.strip().str[:10]
    tr = tr.loc[tr["asof_date"].eq(today)].copy()
    if tr.empty:
        note = f"date={today};path={H_FLOOR_TRUTH_TRACE_PATH};rows_today=0"
        if h_paused:
            paused_note = f"{note}; h_cycle_pause_requested=1"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", paused_note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", paused_note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", paused_note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", paused_note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", paused_note)
        elif h_running:
            running_note = f"{note}; h_cycle_running=1; awaiting_rows_today"
            _add(rows, "h_floor_no_order_inputs", "ok", "0", running_note)
            _add(rows, "h_floor_referral_band_integrity", "ok", "0", running_note)
            _add(rows, "h_floor_referral_source_coverage", "ok", "0", running_note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "ok", "0", running_note)
            _add(rows, "h_floor_formula_consistency", "ok", "0", running_note)
        else:
            _add(rows, "h_floor_no_order_inputs", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_band_integrity", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_source_coverage", "warn", "not_checked", note)
            _add(rows, "h_floor_referral_source_coverage_parked_observability", "warn", "not_checked", note)
            _add(rows, "h_floor_formula_consistency", "warn", "not_checked", note)
        return

    used_flag = tr["used_order_data_flag"].astype(str).str.strip().str.lower()
    source_cogs = tr.get("source_cogs", pd.Series([""] * len(tr), index=tr.index)).astype(str).str.strip().str.lower()
    source_ref = tr.get("source_referral", pd.Series([""] * len(tr), index=tr.index)).astype(str).str.strip().str.lower()
    source_fba = tr.get("source_fba", pd.Series([""] * len(tr), index=tr.index)).astype(str).str.strip().str.lower()
    order_like = used_flag.isin({"1", "true", "yes", "y", "on"}) | source_cogs.str.contains("order", na=False) | source_ref.str.contains("order", na=False) | source_fba.str.contains("order", na=False)
    order_rows = tr.loc[order_like].copy()
    _add(
        rows,
        "h_floor_no_order_inputs",
        "ok" if order_rows.empty else "fail",
        str(len(order_rows.index)),
        (
            f"date={today};rows_today={len(tr.index)};sample="
            f"{','.join(order_rows.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )

    bucket = tr["band_bucket"].astype(str).str.strip()
    src = tr["source_referral"].astype(str).str.strip()
    cross_band = tr.loc[
        (
            bucket.eq("10")
            & src.isin({"L3_BAND_100", "API_BAND_100"})
        )
        | (
            bucket.eq("100")
            & src.isin({"L3_BAND_10", "API_BAND_10"})
        )
    ].copy()
    _add(
        rows,
        "h_floor_referral_band_integrity",
        "ok" if cross_band.empty else "fail",
        str(len(cross_band.index)),
        (
            f"date={today};rows_today={len(tr.index)};sample="
            f"{','.join(cross_band.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )

    reason_codes = tr["reason_codes_csv"].astype(str).str.strip()
    missing_referral = src.eq("MISSING") | reason_codes.str.contains("REFERRAL_BAND_MISSING_", regex=False)
    scope = _read_csv(PHASE1_SCOPE_PATH)
    scope_map: Dict[str, str] = {}
    if not scope.empty and {"sku", "parked_flag"}.issubset(set(scope.columns)):
        scope_map = dict(
            zip(
                scope["sku"].astype(str).str.strip(),
                scope["parked_flag"].astype(str).str.strip().str.lower(),
            )
        )
    tr["parked_flag_scope"] = tr.get("sku", pd.Series([""] * len(tr), index=tr.index)).astype(str).str.strip().map(scope_map).fillna("")
    parked_mask = tr["parked_flag_scope"].isin({"1", "true", "yes", "y"})
    non_parked_mask = ~parked_mask
    non_parked_rows = tr.loc[non_parked_mask].copy()
    parked_rows = tr.loc[parked_mask].copy()
    missing_ref_rows_non_parked = tr.loc[missing_referral & non_parked_mask].copy()
    missing_ref_rows_parked = tr.loc[missing_referral & parked_mask].copy()
    missing_ref_count = len(missing_ref_rows_non_parked.index)
    coverage_status = "ok"
    non_parked_total = len(non_parked_rows.index)
    if missing_ref_count > 0 and non_parked_total > 0:
        coverage_status = "warn" if missing_ref_count < non_parked_total else "fail"
    _add(
        rows,
        "h_floor_referral_source_coverage",
        coverage_status,
        str(missing_ref_count),
        (
            f"date={today};rows_today={len(tr.index)};rows_non_parked={non_parked_total};"
            f"rows_parked={len(parked_rows.index)};sample="
            f"{','.join(missing_ref_rows_non_parked.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )
    _add(
        rows,
        "h_floor_referral_source_coverage_parked_observability",
        "warn" if len(missing_ref_rows_parked.index) > 0 else "ok",
        str(len(missing_ref_rows_parked.index)),
        (
            f"date={today};rows_parked={len(parked_rows.index)};sample="
            f"{','.join(missing_ref_rows_parked.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )

    sale_ex = pd.to_numeric(tr["sale_exvat_gbp"], errors="coerce")
    cogs_ex = pd.to_numeric(tr["cogs_exvat_gbp"], errors="coerce")
    fba_ex = pd.to_numeric(tr["fba_exvat_gbp"], errors="coerce")
    ref_ex = pd.to_numeric(tr["referral_amount_gbp"], errors="coerce")
    digital_ex = pd.to_numeric(tr["digital_fee_exvat_gbp"], errors="coerce")
    margin_ex = pd.to_numeric(tr["margin_exvat_gbp"], errors="coerce")
    floor_total = pd.to_numeric(tr["floor_total_gbp"], errors="coerce")
    vat_rate = pd.to_numeric(tr["vat_rate"], errors="coerce")

    recomputed_sale = cogs_ex + fba_ex + ref_ex + digital_ex + margin_ex
    recomputed_total = (recomputed_sale * (1.0 + vat_rate)).round(2)
    comparable = sale_ex.notna() & floor_total.notna() & recomputed_sale.notna() & recomputed_total.notna()
    sale_mismatch = (sale_ex - recomputed_sale).abs() > 0.02
    floor_mismatch = (floor_total - recomputed_total).abs() > 0.02
    mismatch_mask = comparable & (sale_mismatch | floor_mismatch)
    mismatch_rows = tr.loc[mismatch_mask].copy()
    _add(
        rows,
        "h_floor_formula_consistency",
        "ok" if mismatch_rows.empty else "fail",
        str(len(mismatch_rows.index)),
        (
            f"date={today};rows_today={len(tr.index)};comparable={int(comparable.sum())};sample="
            f"{','.join(mismatch_rows.get('sku', pd.Series([], dtype=str)).astype(str).head(5).tolist())}"
        ),
    )


def _phase1_rollout_checks(rows: List[Dict[str, str]], now_utc: datetime) -> None:
    today = now_utc.strftime("%Y-%m-%d")
    scope = _read_csv(PHASE1_SCOPE_PATH)
    daily = _read_csv(PHASE1_DAILY_INTEL_PATH)

    if scope.empty:
        _add(rows, "a_daily_intel_coverage_non_parked", "fail", "missing_scope", f"path {PHASE1_SCOPE_PATH}")
        _add(rows, "a_daily_intel_compliance_nonempty_non_parked", "fail", "missing_scope", f"path {PHASE1_SCOPE_PATH}")
        _add(rows, "h_parked_sku_write_attempts", "warn", "missing_scope", f"path {PHASE1_SCOPE_PATH}")
        _add(rows, "h_scope_non_parked_matches_targets", "fail", "missing_scope", f"path {PHASE1_SCOPE_PATH}")
    elif "sku" not in scope.columns or "parked_flag" not in scope.columns:
        _add(rows, "a_daily_intel_coverage_non_parked", "fail", "missing_scope_cols", "required=sku,parked_flag")
        _add(rows, "a_daily_intel_compliance_nonempty_non_parked", "fail", "missing_scope_cols", "required=sku,parked_flag")
        _add(rows, "h_parked_sku_write_attempts", "warn", "missing_scope_cols", "required=sku,parked_flag")
        _add(rows, "h_scope_non_parked_matches_targets", "fail", "missing_scope_cols", "required=sku,parked_flag")
    else:
        scoped = scope.copy()
        scoped["sku_key"] = scoped["sku"].astype(str).str.strip().str.upper()
        scoped["parked_key"] = scoped["parked_flag"].astype(str).str.strip()
        non_parked_skus = set(scoped.loc[~scoped["parked_key"].eq("1"), "sku_key"].tolist())
        parked_skus = set(scoped.loc[scoped["parked_key"].eq("1"), "sku_key"].tolist())

        if daily.empty or "sku" not in daily.columns or "date_utc" not in daily.columns:
            _add(
                rows,
                "a_daily_intel_coverage_non_parked",
                "fail",
                "missing_daily_intel",
                f"path {PHASE1_DAILY_INTEL_PATH}",
            )
            _add(
                rows,
                "a_daily_intel_compliance_nonempty_non_parked",
                "fail",
                "missing_daily_intel",
                f"path {PHASE1_DAILY_INTEL_PATH}",
            )
        else:
            daily_today = daily.copy()
            daily_today["sku_key"] = daily_today["sku"].astype(str).str.strip().str.upper()
            daily_today["date_key"] = daily_today["date_utc"].astype(str).str.strip()
            daily_today = daily_today.loc[daily_today["date_key"].eq(today)].copy()
            covered_skus = set(daily_today["sku_key"].tolist())
            covered_non_parked = non_parked_skus.intersection(covered_skus)
            missing_skus = sorted([s for s in non_parked_skus if s not in covered_skus])

            _add(
                rows,
                "a_daily_intel_coverage_non_parked",
                "ok" if not missing_skus else "fail",
                str(len(missing_skus)),
                (
                    f"date={today}; non_parked={len(non_parked_skus)}; covered={len(covered_non_parked)}; "
                    f"missing_sample={','.join(missing_skus[:5])}"
                ),
            )

            if "compliance_ceiling_landed_gbp" not in daily_today.columns:
                _add(
                    rows,
                    "a_daily_intel_compliance_nonempty_non_parked",
                    "fail",
                    "missing_daily_col",
                    "required=compliance_ceiling_landed_gbp",
                )
            else:
                missing_row_count = 0
                blank_compliance_count = 0
                for sku in non_parked_skus:
                    sku_rows = daily_today.loc[daily_today["sku_key"].eq(sku)].copy()
                    if sku_rows.empty:
                        missing_row_count += 1
                        continue
                    has_compliance = sku_rows["compliance_ceiling_landed_gbp"].astype(str).str.strip().ne("").any()
                    if not has_compliance:
                        blank_compliance_count += 1
                bad_total = missing_row_count + blank_compliance_count
                _add(
                    rows,
                    "a_daily_intel_compliance_nonempty_non_parked",
                    "ok" if bad_total == 0 else "fail",
                    str(bad_total),
                    (
                        f"date={today}; non_parked={len(non_parked_skus)}; missing_rows={missing_row_count}; "
                        f"blank_compliance={blank_compliance_count}"
                    ),
                )

            pilot_daily = daily_today.loc[daily_today["sku_key"].eq(OFFICIAL_PILOT_SKU)].copy()
            required_cols = {
                "bbp_max_sold_gbp",
                "cpt_gbp",
                "cpt_x1_2_gbp",
                "ceiling_rule_value_gbp",
                "ceiling_source_used",
                "ceiling_inputs_missing_flag",
            }
            if pilot_daily.empty:
                _add(rows, "h_ceiling_rule_bbp_missing_trial", "warn", "missing_row", f"sku={OFFICIAL_PILOT_SKU};date={today}")
                _add(rows, "h_ceiling_rule_cpt_missing_trial", "warn", "missing_row", f"sku={OFFICIAL_PILOT_SKU};date={today}")
                _add(rows, "h_ceiling_rule_inputs_missing_trial", "warn", "missing_row", f"sku={OFFICIAL_PILOT_SKU};date={today}")
            else:
                missing_cols = sorted([c for c in required_cols if c not in pilot_daily.columns])
                if missing_cols:
                    msg = f"required={','.join(missing_cols)}"
                    _add(rows, "h_ceiling_rule_bbp_missing_trial", "fail", "missing_columns", msg)
                    _add(rows, "h_ceiling_rule_cpt_missing_trial", "fail", "missing_columns", msg)
                    _add(rows, "h_ceiling_rule_inputs_missing_trial", "fail", "missing_columns", msg)
                else:
                    bbp_missing = pilot_daily["bbp_max_sold_gbp"].astype(str).str.strip().eq("").all()
                    cpt_missing = pilot_daily["cpt_x1_2_gbp"].astype(str).str.strip().eq("").all()
                    both_missing = pilot_daily["ceiling_inputs_missing_flag"].astype(str).str.strip().eq("1").any()
                    source_sample = pilot_daily["ceiling_source_used"].astype(str).str.strip().head(1).tolist()
                    source_used = source_sample[0] if source_sample else ""
                    _add(
                        rows,
                        "h_ceiling_rule_bbp_missing_trial",
                        "warn" if bbp_missing else "ok",
                        "1" if bbp_missing else "0",
                        f"sku={OFFICIAL_PILOT_SKU};date={today};source={source_used}",
                    )
                    _add(
                        rows,
                        "h_ceiling_rule_cpt_missing_trial",
                        "warn" if cpt_missing else "ok",
                        "1" if cpt_missing else "0",
                        f"sku={OFFICIAL_PILOT_SKU};date={today};source={source_used}",
                    )
                    _add(
                        rows,
                        "h_ceiling_rule_inputs_missing_trial",
                        "fail" if both_missing else "ok",
                        "1" if both_missing else "0",
                        f"sku={OFFICIAL_PILOT_SKU};date={today};source={source_used}",
                    )

        state_payload, state_path = _read_first_json(H_PRICING_STATE_PATH_CANDIDATES)
        if not state_payload:
            searched = "|".join(str(p).replace("\\", "/") for p in H_PRICING_STATE_PATH_CANDIDATES)
            _add(rows, "h_scope_non_parked_matches_targets", "warn", "missing_state", f"paths {searched}")
        else:
            processed_csv = str(state_payload.get("phase1_skus_processed_csv", "") or "").strip()
            processed_skus = {
                part.strip().upper()
                for part in processed_csv.split(",")
                if part.strip()
            }
            invalid_processed = sorted([s for s in processed_skus if s not in non_parked_skus])
            skipped_parked = _safe_int(state_payload.get("phase1_skus_skipped_parked_count", "0"))
            mismatch_total = len(invalid_processed) + skipped_parked
            resolved_state_path = str(state_path).replace("\\", "/") if state_path is not None else ""
            _add(
                rows,
                "h_scope_non_parked_matches_targets",
                "ok" if mismatch_total == 0 else "fail",
                str(mismatch_total),
                (
                    f"processed={len(processed_skus)}; non_parked_scope={len(non_parked_skus)}; "
                    f"skipped_parked={skipped_parked}; invalid_processed_sample={','.join(invalid_processed[:5])}; "
                    f"state_path={resolved_state_path}"
                ),
            )

        execution = _read_csv(PHASE1_EXECUTION_LOG_PATH)
        if execution.empty or "sku" not in execution.columns or "write_status" not in execution.columns:
            _add(rows, "h_parked_sku_write_attempts", "ok", "0", f"path {PHASE1_EXECUTION_LOG_PATH}; no_rows")
        else:
            exec_today = execution.copy()
            exec_today["sku_key"] = exec_today["sku"].astype(str).str.strip().str.upper()
            if "event_ts_utc" in exec_today.columns:
                exec_today["event_date"] = exec_today["event_ts_utc"].astype(str).str.strip().str[:10]
                exec_today = exec_today.loc[exec_today["event_date"].eq(today)].copy()
            parked_exec = exec_today.loc[exec_today["sku_key"].isin(parked_skus)].copy()
            non_attempt_status = {"", "NO_WRITE_REQUIRED", "READ_ONLY_NO_WRITE", "OBSERVABILITY_BLOCK_NO_WRITE"}
            parked_exec["write_status_key"] = parked_exec["write_status"].astype(str).str.strip().str.upper()
            attempts = parked_exec.loc[~parked_exec["write_status_key"].isin(non_attempt_status)].copy()
            _add(
                rows,
                "h_parked_sku_write_attempts",
                "ok" if attempts.empty else "fail",
                str(len(attempts.index)),
                (
                    f"date={today}; parked_skus={len(parked_skus)}; parked_rows_today={len(parked_exec.index)}; "
                    f"attempt_statuses={','.join(sorted(set(attempts['write_status_key'].tolist()))[:5])}"
                ),
            )

    api_rows = _read_jsonl_rows(API_CALL_LOG_JSONL)
    if not api_rows:
        _add(rows, "h_no_cpt_calls_in_h_cycle", "warn", "missing_or_empty", f"path {API_CALL_LOG_JSONL}")
    else:
        h_cpt_rows: List[Dict[str, object]] = []
        for row in api_rows:
            endpoint = str(row.get("endpoint", "") or "").strip()
            if endpoint != H_CPT_ENDPOINT:
                continue
            script_name = str(row.get("script_name", "") or "").strip()
            script_upper = script_name.upper()
            is_h_script = script_upper.startswith("RUN_H_") or script_upper.startswith("H110_")
            if not is_h_script:
                continue
            ts = _parse_utc_ts(row.get("timestamp_utc", ""))
            if ts is not None and ts.strftime("%Y-%m-%d") != today:
                continue
            h_cpt_rows.append(row)
        sample = []
        for row in h_cpt_rows[:5]:
            sample.append(f"{row.get('script_name', '')}@{row.get('timestamp_utc', '')}")
        _add(
            rows,
            "h_no_cpt_calls_in_h_cycle",
            "ok" if not h_cpt_rows else "fail",
            str(len(h_cpt_rows)),
            f"date={today}; endpoint={H_CPT_ENDPOINT}; sample={';'.join(sample)}",
        )

    _h_floor_policy_checks(rows, now_utc)


def _send_toast(title: str, body: str) -> None:
    # Windows toast via PowerShell (no external modules).
    ps = f"""
$ErrorActionPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$text = $template.GetElementsByTagName('text')
$text.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null
$text.Item(1).AppendChild($template.CreateTextNode('{body}')) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('SellerOne')
$notifier.Show($toast)
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        pass


def _read_alert_snooze(path: Path, now_utc: datetime) -> Dict[str, str]:
    out = {
        "active": "no",
        "status": "off",
        "snooze_until_utc": "",
        "reason": "",
        "error": "",
    }
    if not path.exists():
        return out
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        out["status"] = "invalid"
        out["error"] = f"read_error: {exc}"
        return out
    if not isinstance(payload, dict):
        out["status"] = "invalid"
        out["error"] = "payload_not_object"
        return out
    until_raw = str(payload.get("snooze_until_utc", "")).strip()
    reason = str(payload.get("reason", "")).strip()
    out["snooze_until_utc"] = until_raw
    out["reason"] = reason
    if not until_raw:
        out["status"] = "invalid"
        out["error"] = "missing_snooze_until_utc"
        return out
    try:
        until_dt = datetime.fromisoformat(until_raw.replace("Z", "+00:00"))
        if until_dt.tzinfo is None:
            until_dt = until_dt.replace(tzinfo=timezone.utc)
    except Exception:
        out["status"] = "invalid"
        out["error"] = "invalid_snooze_until_utc"
        return out
    if until_dt > now_utc:
        out["active"] = "yes"
        out["status"] = "active"
    else:
        out["status"] = "expired"
    return out


def main() -> None:
    args = _parse_cli_args()
    runtime = _resolve_runtime_paths(args)
    profile = str(runtime["profile"])
    checklist_path = Path(runtime["checklist_path"])
    alert_state_path = Path(runtime["alert_state_path"])
    health_status_path = Path(runtime["health_status_path"])
    no_toast = bool(runtime["no_toast"])

    def log(msg: str) -> None:
        print(f"[health_check] {msg}")

    rows: List[Dict[str, str]] = []
    OUT.mkdir(parents=True, exist_ok=True)
    checklist_path.parent.mkdir(parents=True, exist_ok=True)
    alert_state_path.parent.mkdir(parents=True, exist_ok=True)
    health_status_path.parent.mkdir(parents=True, exist_ok=True)
    now_utc_dt = datetime.now(timezone.utc)
    snooze = _read_alert_snooze(ALERT_SNOOZE_PATH, now_utc_dt)
    if snooze["error"]:
        _add(rows, "h_health_alert_snooze_config", "warn", "invalid", snooze["error"])
    else:
        snooze_notes = ""
        if snooze["snooze_until_utc"]:
            snooze_notes = f"until={snooze['snooze_until_utc']}"
            if snooze["reason"]:
                snooze_notes += f";reason={snooze['reason']}"
        _add(rows, "h_health_alert_snooze_config", "ok", snooze["status"], snooze_notes)

    if not health_status_path.exists():
        pd.DataFrame(columns=["timestamp_utc", "status", "fail_count", "warn_count", "notes"]).to_csv(
            health_status_path, index=False
        )

    log(
        "profile_config "
        f"profile={profile} "
        f"checklist_path={checklist_path} "
        f"alert_state_path={alert_state_path} "
        f"health_status_path={health_status_path} "
        f"no_toast={'1' if no_toast else '0'}"
    )

    log("loading orders_all.csv")
    orders_all = _read_csv(OUT / "orders_all.csv", usecols=["amazon_order_id", "purchase_date"])
    log(f"orders_all rows: {len(orders_all)}")

    log("loading order_items_all.csv")
    order_items_all = _read_csv(OUT / "order_items_all.csv", usecols=["amazon_order_id", "seller_sku", "quantity_shipped", "quantity_ordered"])
    log(f"order_items_all rows: {len(order_items_all)}")

    log("loading order_master.csv")
    order_master = _read_csv(
        OUT / "order_master.csv",
        usecols=["Date", "Order ID", "SKU", "lvl", "COGS_Total", "COGS_ExVAT", "Quantity Ordered"],
    )
    log("loading order_master_prev.csv")
    order_master_prev = _read_csv(OUT / "order_master_prev.csv", usecols=["Order ID", "SKU"])
    log(f"order_master rows: {len(order_master)}")

    log("loading financial_events_level1.csv")
    l1 = _read_csv(OUT / "financial_events_level1.csv", usecols=["Order ID", "SKU", "Date", "Quantity Ordered"])
    log("loading financial_events_level2.csv")
    l2 = _read_csv(OUT / "financial_events_level2.csv", usecols=["Order ID", "SKU", "Quantity Ordered"])
    log("loading financial_events_level3_official.csv")
    l3 = _read_csv(OUT / "financial_events_level3_official.csv", usecols=["Order ID", "SKU"])
    log(f"level1 rows: {len(l1)}")

    log("loading token_ledger_live.csv")
    token_ledger = _read_csv(OUT / "token_ledger_live.csv")
    for col in ["token_id", "seller_sku", "status"]:
        if col not in token_ledger.columns:
            token_ledger[col] = ""
    log(f"token_ledger rows: {len(token_ledger)}")

    log("loading token_cogs_ledger.csv")
    token_cogs_path = OUT / "token_cogs_ledger.csv"
    token_cogs = _read_csv(token_cogs_path)
    # Normalize column names for compatibility across versions
    token_cogs = token_cogs.rename(columns={
        "Order ID": "order_id",
        "SKU": "seller_sku",
    })
    if "order_id" not in token_cogs.columns or "seller_sku" not in token_cogs.columns:
        raise ValueError(f"token_cogs_ledger.csv missing required columns: order_id/seller_sku (found {list(token_cogs.columns)})")
    log(f"token_cogs rows: {len(token_cogs)}")

    log("loading inventory_summaries.csv")
    inventory = _read_csv(OUT / "inventory_summaries.csv", usecols=["seller_sku"])
    log(f"inventory rows: {len(inventory)}")

    # Orders overview
    orders_all_count = len(orders_all)
    _add(rows, "orders_all_rows", "ok" if orders_all_count > 0 else "fail", str(orders_all_count))
    if not orders_all.empty:
        max_order_dt = _to_dt(orders_all["purchase_date"]).max()
    else:
        max_order_dt = pd.NaT

    # Order items overview
    _add(rows, "order_items_all_rows", "ok" if len(order_items_all) > 0 else "warn", str(len(order_items_all)))
    # Orders missing items within recent window (default 24h from latest order)
    gap_window_hours = float(os.environ.get("ORDER_ITEMS_GAP_WINDOW_HOURS", "24"))
    if not orders_all.empty:
        orders_all = orders_all.copy()
        orders_all["purchase_date_dt"] = _to_dt(orders_all["purchase_date"])
        max_dt = orders_all["purchase_date_dt"].max()
        if pd.notna(max_dt):
            window_start = max_dt - pd.Timedelta(hours=gap_window_hours)
            window_orders = orders_all[
                orders_all["purchase_date_dt"].notna()
                & (orders_all["purchase_date_dt"] >= window_start)
                & (orders_all["purchase_date_dt"] <= max_dt)
            ]
        else:
            window_orders = orders_all.iloc[0:0]
        if not window_orders.empty:
            item_order_ids = set(order_items_all.get("amazon_order_id", pd.Series([], dtype=str)).astype(str).str.strip())
            window_orders = window_orders.copy()
            window_orders["amazon_order_id"] = window_orders["amazon_order_id"].astype(str).str.strip()
            missing_items = window_orders[~window_orders["amazon_order_id"].isin(item_order_ids)]
            missing_count = len(missing_items)
            _add(rows, "orders_missing_items_window", "fail" if missing_count > 0 else "ok", str(missing_count))
            if missing_count > 0:
                missing_items[["amazon_order_id", "purchase_date"]].to_csv(DETAIL_ORDERS_MISSING_ITEMS, index=False)
            else:
                pd.DataFrame(columns=["amazon_order_id", "purchase_date"]).to_csv(DETAIL_ORDERS_MISSING_ITEMS, index=False)
        else:
            _add(rows, "orders_missing_items_window", "ok", "0")
            pd.DataFrame(columns=["amazon_order_id", "purchase_date"]).to_csv(DETAIL_ORDERS_MISSING_ITEMS, index=False)
    else:
        _add(rows, "orders_missing_items_window", "warn", "n/a", "missing orders_all")

    # Order master completeness
    master_rows = len(order_master)
    _add(rows, "order_master_rows", "ok" if master_rows > 0 else "fail", str(master_rows))
    if not order_master_prev.empty:
        prev_rows = len(order_master_prev)
        if master_rows < prev_rows:
            drop = prev_rows - master_rows
            explained_drop = 0
            try:
                if L1_MISSING_FEE_KEYS.exists():
                    fee_hold = pd.read_csv(L1_MISSING_FEE_KEYS, dtype=str)
                    explained_drop += len(fee_hold)
            except Exception:
                pass
            try:
                if MISSING_TOKEN_ORDERS.exists():
                    token_hold = pd.read_csv(MISSING_TOKEN_ORDERS, dtype=str)
                    explained_drop += len(token_hold)
            except Exception:
                pass
            status = "ok" if explained_drop >= drop else "warn"
            note = f"prev={prev_rows}, current={master_rows}, explained_holdbacks={explained_drop}"
            _add(rows, "order_master_row_drop", status, str(drop), note)
        else:
            _add(rows, "order_master_row_drop", "ok", "0", f"prev={prev_rows}, current={master_rows}")
    if not order_master.empty:
        blank_sku = order_master["SKU"].isna() | (order_master["SKU"].astype(str).str.strip() == "")
        blank_date = order_master["Date"].isna() | (order_master["Date"].astype(str).str.strip() == "")
        _add(rows, "order_master_blank_sku", "fail" if blank_sku.sum() > 0 else "ok", str(int(blank_sku.sum())))
        _add(rows, "order_master_blank_date", "fail" if blank_date.sum() > 0 else "ok", str(int(blank_date.sum())))
        if "Quantity Ordered" in order_master.columns:
            qty_raw = order_master["Quantity Ordered"].astype(str).str.strip()
            blank_qty = qty_raw.isna() | qty_raw.eq("") | qty_raw.eq("nan")
            _add(rows, "order_master_blank_qty", "fail" if blank_qty.sum() > 0 else "ok", str(int(blank_qty.sum())))
        if blank_sku.any():
            bad_orders = order_master.loc[blank_sku, "Order ID"].astype(str).head(10).tolist()
            print("[health_check] blank SKU order ids (first 10):", bad_orders)
        if blank_date.any():
            bad_orders = order_master.loc[blank_date, "Order ID"].astype(str).head(10).tolist()
            print("[health_check] blank Date order ids (first 10):", bad_orders)

        max_master_dt = _to_dt(order_master["Date"]).max()
        if pd.notna(max_order_dt) and pd.notna(max_master_dt):
            gap_hours = (max_order_dt - max_master_dt).total_seconds() / 3600.0
            _add(
                rows,
                "order_master_date_gap_hours",
                _status_from_gap(gap_hours),
                f"{gap_hours:.2f}",
                f"orders_all max {max_order_dt}; master max {max_master_dt}",
            )
        else:
            _add(rows, "order_master_date_gap_hours", "warn", "n/a", "missing dates")

        # Blank COGS (lvl >=1)
        lvl = order_master.get("lvl", pd.Series([], dtype=str)).astype(str)
        cogs = order_master.get("COGS_ExVAT", pd.Series([], dtype=str)).astype(str)
        qty = order_master.get("Quantity Ordered", pd.Series([], dtype=str)).astype(str)
        blank_cogs = (cogs.str.strip().isin(["", "0", "0.0", "0.00"])) & (lvl != "0")
        # Ignore rows with zero quantity (no cost expected).
        blank_cogs = blank_cogs & (~qty.str.strip().isin(["", "0", "0.0", "0.00"]))
        blank_cogs_count = int(blank_cogs.sum())
        _add(rows, "order_master_blank_cogs_lvl1plus", "warn" if blank_cogs_count > 0 else "ok", str(blank_cogs_count))
        if blank_cogs_count > 0:
            cols = ["Order ID", "SKU", "Date", "lvl", "COGS_ExVAT", "COGS_VAT", "COGS_Total"]
            cols = [c for c in cols if c in order_master.columns]
            details = order_master.loc[blank_cogs, cols].copy()
            details.to_csv(DETAIL_BLANK_COGS, index=False)

    # L1 vs master key coverage
    if not l1.empty and not order_master.empty:
        l1_keys = set((l1["Order ID"].astype(str).str.strip() + "||" + l1["SKU"].astype(str).str.strip()).tolist())
        master_keys = set((order_master["Order ID"].astype(str).str.strip() + "||" + order_master["SKU"].astype(str).str.strip()).tolist())
        ignore_keys = set()
        missing_token_keys = set()
        dynamic_missing_token_keys = set()
        if L1_MISSING_FEE_KEYS.exists():
            try:
                drop_df = pd.read_csv(L1_MISSING_FEE_KEYS, dtype=str)
                if not drop_df.empty and "Order ID" in drop_df.columns and "SKU" in drop_df.columns:
                    ignore_keys = set(
                        (drop_df["Order ID"].astype(str).str.strip() + "||" + drop_df["SKU"].astype(str).str.strip()).tolist()
                    )
            except Exception:
                ignore_keys = set()
        if MISSING_TOKEN_ORDERS.exists():
            try:
                miss_df = pd.read_csv(MISSING_TOKEN_ORDERS, dtype=str)
                if not miss_df.empty and "Order ID" in miss_df.columns and "SKU" in miss_df.columns:
                    missing_token_keys = set(
                        (miss_df["Order ID"].astype(str).str.strip() + "||" + miss_df["SKU"].astype(str).str.strip()).tolist()
                    )
            except Exception:
                missing_token_keys = set()
        # Derive held-back missing-token keys directly from L1 + token ledger
        # so health does not rely solely on sidecar CSV timing.
        try:
            l1_qty = pd.to_numeric(l1.get("Quantity Ordered", pd.Series([], dtype=str)), errors="coerce").fillna(0.0)
            l1_has_qty = l1_qty.gt(0)
            l1_key_series = l1["Order ID"].astype(str).str.strip() + "||" + l1["SKU"].astype(str).str.strip()
            token_cogs = _read_csv(OUT / "token_cogs_ledger.csv")
            token_valid_keys = set()
            if not token_cogs.empty:
                if "Order ID" not in token_cogs.columns and "order_id" in token_cogs.columns:
                    token_cogs["Order ID"] = token_cogs["order_id"]
                if "SKU" not in token_cogs.columns and "seller_sku" in token_cogs.columns:
                    token_cogs["SKU"] = token_cogs["seller_sku"]
                if "Order ID" in token_cogs.columns and "SKU" in token_cogs.columns:
                    cogs_ex = pd.to_numeric(token_cogs.get("cogs_exvat", pd.Series([], dtype=str)), errors="coerce").fillna(0.0)
                    keys = token_cogs["Order ID"].astype(str).str.strip() + "||" + token_cogs["SKU"].astype(str).str.strip()
                    token_valid_keys = set(keys[cogs_ex.gt(0.0)].tolist())
            dynamic_missing_token_keys = set(l1_key_series[l1_has_qty & (~l1_key_series.isin(token_valid_keys))].tolist())
        except Exception:
            dynamic_missing_token_keys = set()

        missing_set = (l1_keys - master_keys) - ignore_keys - missing_token_keys - dynamic_missing_token_keys
        missing = len(missing_set)
        notes = []
        if ignore_keys:
            notes.append(f"ignored_missing_fee_keys={len(ignore_keys)}")
        if missing_token_keys:
            notes.append(f"held_back_missing_tokens={len(missing_token_keys)}")
        if dynamic_missing_token_keys:
            notes.append(f"held_back_missing_tokens_dynamic={len(dynamic_missing_token_keys)}")
        note = ";".join(notes)
        _add(rows, "l1_keys_missing_in_master", "fail" if missing > 0 else "ok", str(missing), note)
        if missing:
            missing_keys = list(missing_set)[:10]
            print("[health_check] missing L1 keys (first 10):", missing_keys)
        orphans = len(master_keys - l1_keys)
        _add(rows, "order_master_orphans_count", "fail" if orphans > 0 else "ok", str(orphans))
        if orphans:
            orphan_keys = list(master_keys - l1_keys)[:10]
            print("[health_check] master keys not in L1 (first 10):", orphan_keys)
    else:
        _add(rows, "l1_keys_missing_in_master", "warn", "n/a", "missing L1 or master")
        _add(rows, "order_master_orphans_count", "warn", "n/a", "missing L1 or master")

    # L3 orphans (L3 keys not in L1)
    if not l3.empty and not l1.empty:
        l1_keys = set((l1["Order ID"].astype(str).str.strip() + "||" + l1["SKU"].astype(str).str.strip()).tolist())
        l3_keys = set((l3["Order ID"].astype(str).str.strip() + "||" + l3["SKU"].astype(str).str.strip()).tolist())
        l3_orphan_keys = list(l3_keys - l1_keys)
        scoped_orphans = l3_orphan_keys
        missing_scope_dates = 0
        ignored_count = 0
        if ORPHAN_IGNORE_ORDER_IDS_FILE:
            ignore_path = Path(ORPHAN_IGNORE_ORDER_IDS_FILE)
            if ignore_path.exists():
                try:
                    try:
                        ignore_df = pd.read_csv(ignore_path, dtype=str)
                    except Exception:
                        ignore_df = pd.read_csv(ignore_path, dtype=str, sep=";")
                    ignore_ids = set()
                    if "Order number" in ignore_df.columns:
                        ids = (
                            ignore_df["Order number"]
                            .fillna("")
                            .astype(str)
                            .str.split(" / ", n=1, expand=False)
                            .str[0]
                            .str.strip()
                        )
                        ignore_ids.update([v for v in ids.tolist() if v])
                    else:
                        for col in ignore_df.columns:
                            if col.lower() in ("order id", "order_id", "amazon_order_id"):
                                ids = ignore_df[col].fillna("").astype(str).str.strip()
                                ignore_ids.update([v for v in ids.tolist() if v])
                                break
                    if ignore_ids:
                        filtered = []
                        for k in scoped_orphans:
                            order_id = k.split("||", 1)[0]
                            if order_id in ignore_ids:
                                ignored_count += 1
                                continue
                            filtered.append(k)
                        scoped_orphans = filtered
                except Exception:
                    pass
        if ORPHAN_SCOPE_START_DATE:
            try:
                scope_dt = pd.to_datetime(ORPHAN_SCOPE_START_DATE + "T00:00:00Z", utc=True)
                if not orders_all.empty and "amazon_order_id" in orders_all.columns and "purchase_date_dt" in orders_all.columns:
                    order_dates = orders_all[["amazon_order_id", "purchase_date_dt"]].dropna()
                    order_dates["amazon_order_id"] = order_dates["amazon_order_id"].astype(str).str.strip()
                    order_date_map = dict(zip(order_dates["amazon_order_id"], order_dates["purchase_date_dt"]))
                    filtered = []
                    for k in scoped_orphans:
                        order_id = k.split("||", 1)[0]
                        dt = order_date_map.get(order_id)
                        if dt is None or pd.isna(dt):
                            missing_scope_dates += 1
                            filtered.append(k)
                        elif dt >= scope_dt:
                            filtered.append(k)
                    scoped_orphans = filtered
            except Exception:
                pass
        l3_orphans = len(scoped_orphans)
        notes = ""
        if ORPHAN_SCOPE_START_DATE:
            notes = f"scope_start={ORPHAN_SCOPE_START_DATE}; missing_dates={missing_scope_dates}"
        if ignored_count:
            notes = (notes + "; " if notes else "") + f"ignored_orders={ignored_count}"
        # If an ignore list is provided, do not fail the health check on L3 orphans.
        l3_status = "ok" if (l3_orphans == 0 or ORPHAN_IGNORE_ORDER_IDS_FILE) else "fail"
        _add(rows, "l3_orphans_count", l3_status, str(l3_orphans), notes)
        if l3_orphans:
            print("[health_check] L3 keys not in L1 (first 10):", scoped_orphans[:10])
    else:
        _add(rows, "l3_orphans_count", "warn", "n/a", "missing L1 or L3")

    # Level 2 duplicate keys (Order ID + SKU)
    if not l2.empty:
        l2_keys = l2[["Order ID", "SKU"]].astype(str).agg("||".join, axis=1)
        dupes = int(l2_keys.duplicated().sum())
        _add(rows, "level2_duplicate_keys", "fail" if dupes > 0 else "ok", str(dupes))
    else:
        _add(rows, "level2_duplicate_keys", "warn", "n/a", "missing Level 2")

    # Tokens
    if not token_ledger.empty:
        total = len(token_ledger)
        available = (token_ledger["status"] == "available").sum()
        allocated = (token_ledger["status"] == "allocated").sum()
        _add(rows, "tokens_total", "ok", str(total))
        _add(rows, "tokens_available", "ok", str(int(available)))
        _add(rows, "tokens_allocated", "ok", str(int(allocated)))
        if "source" not in token_ledger.columns:
            _add(rows, "tokens_stock_receipt_missing_order_key", "warn", "missing_col", "source")
        else:
            stock_receipt = token_ledger[token_ledger["source"].astype(str).str.strip() == "stock_receipt"].copy()
            if stock_receipt.empty:
                _add(rows, "tokens_stock_receipt_missing_order_key", "ok", "0", "no_stock_receipt_rows")
            elif "source_order_key" not in token_ledger.columns:
                _add(rows, "tokens_stock_receipt_missing_order_key", "warn", "missing_col", "source_order_key")
            else:
                blank_order_key = int(stock_receipt["source_order_key"].astype(str).str.strip().eq("").sum())
                _add(
                    rows,
                    "tokens_stock_receipt_missing_order_key",
                    "warn" if blank_order_key > 0 else "ok",
                    str(blank_order_key),
                    f"stock_receipt_rows={len(stock_receipt)}",
                )
    else:
        _add(rows, "tokens_total", "fail", "0")

    # Token COGS ledger
    _add(rows, "token_cogs_rows", "ok" if len(token_cogs) > 0 else "warn", str(len(token_cogs)))

    # Inventory
    _add(rows, "inventory_rows", "ok" if len(inventory) > 0 else "warn", str(len(inventory)))

    # Token shortages (per SKU)
    shortage_path = OUT / "token_shortages_by_sku.csv"
    if shortage_path.exists():
        try:
            shortages = pd.read_csv(shortage_path, dtype=str)
            count = len(shortages)
            _add(rows, "token_shortages_by_sku", "fail" if count > 0 else "ok", str(count))
        except Exception as exc:
            _add(rows, "token_shortages_by_sku", "fail", "read_error", str(exc))
    else:
        _add(rows, "token_shortages_by_sku", "warn", "missing", f"path {shortage_path}")

    # Recent log health
    log_path = _first_existing_path(B_CYCLE_LOG_PATH_CANDIDATES)
    if log_path is None:
        _add(rows, "b_cycle_log_exists", "fail", "no", f"searched={','.join([str(p) for p in B_CYCLE_LOG_PATH_CANDIDATES])}")
    else:
        log_info = _file_info(log_path)
        _add(
            rows,
            "b_cycle_log_exists",
            "ok" if log_info["exists"] == "yes" else "fail",
            log_info["exists"],
            f"mtime {log_info['mtime_utc']}; path={log_path}",
        )
        window_hours = float(os.environ.get("B_CYCLE_FAIL_LOG_HOURS", "2"))
        fail_stats = _b_cycle_recent_fail_stats(log_path, window_hours=window_hours)
        latest_cycle = str(fail_stats.get("latest_cycle", "") or "").strip()
        unresolved_count = int(fail_stats.get("unresolved_count", 0))
        raw_fail_count = int(fail_stats.get("raw_fail_count", 0))
        recovered_count = int(fail_stats.get("recovered_count", 0))
        ignored_non_actionable = int(fail_stats.get("ignored_non_actionable", 0))
        unresolved_sample = fail_stats.get("unresolved_sample", [])
        sample_text = ""
        if isinstance(unresolved_sample, list) and unresolved_sample:
            sample_text = f"; unresolved_sample={';'.join([str(x) for x in unresolved_sample[:3]])}"
        _add(
            rows,
            "b_cycle_recent_fail_lines",
            "warn" if unresolved_count > 0 else "ok",
            str(unresolved_count),
            (
                f"latest_cycle={latest_cycle}; raw_fail_count={raw_fail_count}; "
                f"recovered_count={recovered_count}; unresolved_count={unresolved_count}; "
                f"ignored_non_actionable={ignored_non_actionable}; "
                f"path={log_path}{sample_text}"
            ),
        )
    try:
        if not B_SHEET_SYNC_STATUS_PATH.exists():
            _add(rows, "b_sheet_sync_external_health", "warn", "missing", f"path={B_SHEET_SYNC_STATUS_PATH}")
        else:
            sync = pd.read_csv(B_SHEET_SYNC_STATUS_PATH, dtype=str).fillna("")
            required = {"timestamp_utc", "step", "status", "severity"}
            if sync.empty or not required.issubset(set(sync.columns)):
                _add(rows, "b_sheet_sync_external_health", "warn", "invalid", f"path={B_SHEET_SYNC_STATUS_PATH}")
            else:
                ts = _to_dt(sync["timestamp_utc"])
                window_hours = float(os.environ.get("B_SHEET_SYNC_WARN_HOURS", "6"))
                cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
                recent = sync.loc[ts.notna() & (ts >= cutoff)].copy()
                degraded = recent[
                    recent["status"].astype(str).str.strip().str.lower().isin({"degraded_local", "hard_fail"})
                ]
                latest = sync.iloc[-1]
                _add(
                    rows,
                    "b_sheet_sync_external_health",
                    "warn" if not degraded.empty else "ok",
                    str(len(degraded.index)),
                    (
                        f"window_hours={window_hours};path={B_SHEET_SYNC_STATUS_PATH};"
                        f"latest_step={latest.get('step', '')};latest_status={latest.get('status', '')};"
                        f"latest_severity={latest.get('severity', '')}"
                    ),
                )
    except Exception as exc:
        _add(rows, "b_sheet_sync_external_health", "warn", "read_error", str(exc))

    fees_failed_stats = _fees_failed_rows_today(FEES_FAILED_PATH, now_utc_dt)
    fees_failed_notes = str(fees_failed_stats.get("notes", "") or "")
    sample_skus = fees_failed_stats.get("sample_skus", [])
    if isinstance(sample_skus, list) and sample_skus:
        fees_failed_notes = f"{fees_failed_notes};sample_skus={','.join([str(x) for x in sample_skus[:5]])}"
    if bool(fees_failed_stats.get("read_error", False)):
        _add(rows, "a_fees_failed_rows_today", "warn", "read_error", fees_failed_notes)
    else:
        unresolved_today = int(fees_failed_stats.get("count", 0))
        _add(
            rows,
            "a_fees_failed_rows_today",
            "warn" if unresolved_today > 0 else "ok",
            str(unresolved_today),
            fees_failed_notes,
        )

    _schema_check(
        rows,
        "b_schema_orders_missing_items_window",
        DETAIL_ORDERS_MISSING_ITEMS,
        ["amazon_order_id", "purchase_date"],
        optional=False,
    )
    # Ensure the unknown-fee-country detail file exists (empty is OK).
    if not DETAIL_UNKNOWN_FEE_COUNTRIES.exists():
        DETAIL_UNKNOWN_FEE_COUNTRIES.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["ship_country_code", "count"]).to_csv(
            DETAIL_UNKNOWN_FEE_COUNTRIES, index=False
        )
    _schema_check(
        rows,
        "b_schema_unknown_fee_countries",
        DETAIL_UNKNOWN_FEE_COUNTRIES,
        ["ship_country_code", "count"],
        optional=True,
    )

    # Unknown fee VAT rules (new country codes)
    try:
        known = set()
        if FEE_RULES_PATH.exists():
            rules_df = pd.read_csv(FEE_RULES_PATH, dtype=str).fillna("")
            if "country_code" in rules_df.columns:
                known = set(rules_df["country_code"].astype(str).str.strip().str.upper())
        orders = pd.read_csv(OUT / "orders_all.csv", dtype=str).fillna("")
        cc = orders.get("ship_country_code", pd.Series([], dtype=str)).astype(str).str.strip().str.upper()
        cc = cc[cc != ""]
        # Only alert on unknown countries that have recent orders (last 30 days from latest order date).
        recent_unknown = []
        try:
            if "purchase_date" in orders.columns:
                orders = orders.copy()
                orders["purchase_date_dt"] = _to_dt(orders["purchase_date"])
                max_dt = orders["purchase_date_dt"].max()
                if pd.notna(max_dt):
                    window_start = max_dt - pd.Timedelta(days=30)
                    recent = orders[orders["purchase_date_dt"].notna() & (orders["purchase_date_dt"] >= window_start)]
                else:
                    recent = orders.iloc[0:0]
            else:
                recent = orders
            recent_cc = recent.get("ship_country_code", pd.Series([], dtype=str)).astype(str).str.strip().str.upper()
            recent_cc = recent_cc[recent_cc != ""]
            recent_unknown = sorted([c for c in recent_cc.unique().tolist() if c not in known])
        except Exception:
            recent_unknown = sorted([c for c in cc.unique().tolist() if c not in known])
        if recent_unknown:
            counts = (
                orders[orders["ship_country_code"].astype(str).str.strip().str.upper().isin(recent_unknown)]
                .groupby("ship_country_code")
                .size()
                .reset_index(name="count")
            )
            DETAIL_UNKNOWN_FEE_COUNTRIES.parent.mkdir(parents=True, exist_ok=True)
            counts.to_csv(DETAIL_UNKNOWN_FEE_COUNTRIES, index=False)
            _add(
                rows,
                "fee_rules_unknown_countries",
                "warn",
                str(len(recent_unknown)),
                ",".join(recent_unknown[:10]),
            )
        else:
            # Always write a stub file so the schema check does not warn.
            DETAIL_UNKNOWN_FEE_COUNTRIES.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=["ship_country_code", "count"]).to_csv(
                DETAIL_UNKNOWN_FEE_COUNTRIES, index=False
            )
            _add(rows, "fee_rules_unknown_countries", "ok", "0")
    except Exception as exc:
        _add(rows, "fee_rules_unknown_countries", "warn", "error", str(exc))

    # C cycle schema checks (phase 1)
    _schema_check(
        rows,
        "c_schema_financial_events_shipments",
        OUT / "financial_events_shipments.csv",
        ["shipment_id", "inbound_shipment_id", "parsed_fba_shipment_id"],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_financial_events_inbound_summary",
        OUT / "financial_events_inbound_summary.csv",
        ["date", "amount_type", "total_amount"],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_inventory_ledger_raw",
        OUT / "inventory_ledger_raw.csv",
        ["Reference ID", "MSKU", "Event Type", "Quantity"],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_purchase_source",
        Path("reference/Amazon Supplier Process - Orders (3).csv"),
        ["SKU", "Cost PU", "Order Date", "Sent to FBA"],
        optional=False,
    )
    _schema_check(
        rows,
        "b_schema_l3_orphans",
        OUT / "l3_orphans.csv",
        ["Order ID", "SKU"],
        optional=False,
    )
    _schema_check(
        rows,
        "b_schema_token_allocation_skipped",
        OUT / "token_allocation_skipped.csv",
        ["Order ID", "SKU", "Date", "Quantity Ordered", "reason"],
        optional=False,
    )
    _schema_check(
        rows,
        "b_schema_orphan_recovery_alerts",
        OUT / "orphan_recovery_alerts.csv",
        ["timestamp", "orphan_count", "window_start", "window_end", "action"],
        optional=True,
    )
    _schema_check(
        rows,
        "b_schema_orphan_order_items_recovered",
        OUT / "orphan_order_items_recovered.csv",
        ["AmazonOrderId"],
        optional=True,
    )
    _schema_check(
        rows,
        "b_schema_orphan_order_items_failed",
        OUT / "orphan_order_items_failed.csv",
        ["order_id", "error"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_merchant_listings",
        OUT / "merchant_listings_latest.csv",
        ["seller-sku", "asin1", "product-id"],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_storage_fee_monthly",
        OUT / "fba_storage_fee_charges_monthly.csv",
        ["asin", "estimated_monthly_storage_fee"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_long_term_storage_fee_monthly",
        OUT / "fba_long_term_storage_fee_charges_monthly.csv",
        ["asin"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_delivery_status",
        OUT / "inbound_delivery_status.csv",
        ["inbound_shipment_id", "expected_qty", "received_qty", "pct_received"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_missing_units",
        OUT / "inbound_missing_units.csv",
        ["inbound_shipment_id", "sku", "missing_qty"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_cost_events",
        OUT / "inbound_cost_events.csv",
        ["shipment_id", "inbound_shipment_id", "parsed_fba_shipment_id", "amount", "currency"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_allocated",
        OUT / "inbound_costs_allocated.csv",
        ["shipment_id", "currency", "event_count", "total_amount", "total_tax", "total_with_tax"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_unallocated",
        OUT / "inbound_costs_unallocated.csv",
        ["shipment_key", "amount", "currency"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_allocated_sku",
        OUT / "inbound_costs_allocated_sku.csv",
        ["shipment_id", "sku", "allocated_total"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_unallocated_sku",
        OUT / "inbound_costs_unallocated_sku.csv",
        ["shipment_id", "unallocated_reason"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_inbound_costs_allocation_summary",
        OUT / "inbound_costs_allocation_summary.csv",
        ["shipment_id", "currency", "allocated_total"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_vat_country_model",
        VAT_MODEL,
        [
            "country_code",
            "marketplace_id",
            "currency",
            "sample_orders",
            "taxable_orders",
            "pct_taxable",
            "avg_vat_rate",
            "last_order_date",
            "built_at",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_fee_country_model",
        FEE_MODEL,
        [
            "country_code",
            "marketplace_id",
            "currency",
            "sample_orders",
            "fba_avg_ex_per_unit",
            "fba_taxable_pct",
            "fba_vat_rate",
            "commission_pct_avg",
            "commission_taxable_pct",
            "commission_vat_rate",
            "dsf_pct",
            "dsf_vat_rate",
            "last_order_date",
            "built_at",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "c_schema_token_maturity_window",
        OUT / "token_maturity_window.csv",
        ["inbound_shipment_id", "expected_qty", "received_qty", "in_flight_qty", "is_mature"],
        optional=True,
    )
    _schema_check(
        rows,
        "c_schema_token_maturity_window_sku",
        OUT / "token_maturity_window_sku.csv",
        ["inbound_shipment_id", "sku", "expected_qty"],
        optional=True,
    )
    # E cycle schema checks (optional until E is running daily)
    _schema_check(
        rows,
        "e_schema_sales_velocity",
        OUT / "sku_sales_velocity.csv",
        ["sku", "window_days", "units_sold", "velocity_units_per_day"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_roi_snapshot",
        OUT / "sku_roi_snapshot.csv",
        ["sku", "window_days", "units_sold", "roi_exvat"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_roi_snapshot_uk",
        OUT / "sku_roi_snapshot_uk.csv",
        ["sku", "window_days", "units_sold", "roi_exvat"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_roi_snapshot_non_uk",
        OUT / "sku_roi_snapshot_non_uk.csv",
        ["sku", "window_days", "units_sold", "roi_exvat"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_roi_snapshot_by_country",
        OUT / "sku_roi_snapshot_by_country.csv",
        ["sku", "country_code", "window_days", "units_sold", "roi_exvat"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_restock_signals",
        OUT / "sku_restock_signals.csv",
        ["sku", "velocity_30d", "days_of_stock_left", "reorder_flag"],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_performance_summary",
        OUT / "sku_performance_summary.csv",
        [
            "sku",
            "profit_per_unit_gbp_30d",
            "value_velocity_gbp_per_day",
            "current_token_cost_gbp",
            "break_even_price_gbp",
            "expected_refund_cost_per_unit_gbp",
            "roi_at_our_price_pct",
            "roi_at_buy_box_price_pct",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_study_report",
        OUT / "e_study_report.csv",
        [
            "study_rank",
            "sku",
            "reorder_flag",
            "value_velocity_gbp_per_day",
            "asof_date",
        ],
        optional=True,
    )
    e_run_log_path = _first_existing_path(E_RUN_LOG_PATH_CANDIDATES) or E_RUN_LOG_JSONL
    _schema_check_jsonl(
        rows,
        "e_schema_run_log",
        e_run_log_path,
        [
            "run_id",
            "started_utc",
            "finished_utc",
            "status",
            "tasks_run",
            "elapsed_seconds",
            "expected_input_asof",
            "output_asof",
            "asof_rerun_trigger",
            "error",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "e_schema_decision_log",
        OUT / "e_decision_log.csv",
        [
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
        ],
        optional=True,
    )
    input_asof = {
        "listing_offer_history": _max_asof_date(LISTING_OFFER_HISTORY),
        "inventory_history": _max_asof_date(INVENTORY_HISTORY),
        "inbound_history": _max_asof_date(INBOUND_HISTORY),
        "refund_adjustment_history": _max_asof_date(REFUND_ADJUSTMENT_HISTORY),
    }
    h_paused = _h_cycle_pause_requested()
    paused_relaxed_inputs = {"inventory_history", "inbound_history"} if h_paused else set()
    required_input_asof = {
        name: val for name, val in input_asof.items() if name not in paused_relaxed_inputs
    }
    missing_input_asof = [name for name, val in required_input_asof.items() if not val]
    missing_relaxed_asof = [name for name in paused_relaxed_inputs if not input_asof.get(name)]
    missing_all_asof = missing_input_asof + sorted(missing_relaxed_asof)
    if missing_input_asof:
        _add(rows, "h_e_inputs_fresh", "warn", "missing_asof", ",".join(missing_all_asof))
        expected_input_asof = ""
    else:
        compare_inputs = required_input_asof if required_input_asof else input_asof
        unique_input_dates = sorted(set(compare_inputs.values()))
        expected_input_asof = min(unique_input_dates)
        if len(unique_input_dates) > 1:
            _add(
                rows,
                "h_e_inputs_fresh",
                "warn",
                str(len(unique_input_dates)),
                "; ".join([f"{k}={v}" for k, v in compare_inputs.items()]),
            )
        else:
            try:
                expected_dt = datetime.fromisoformat(expected_input_asof).replace(tzinfo=timezone.utc)
                now_day = datetime.now(timezone.utc).date()
                age_days = (now_day - expected_dt.date()).days
                max_age_days = int(float(os.environ.get("E_INPUT_MAX_AGE_DAYS", "1")))
                freshness_status = "ok" if age_days <= max_age_days else "warn"
                pause_note = "; h_cycle_pause_requested=1" if h_paused else ""
                _add(
                    rows,
                    "h_e_inputs_fresh",
                    freshness_status,
                    str(age_days),
                    f"asof_date={expected_input_asof}; max_age_days={max_age_days}{pause_note}",
                )
            except Exception:
                _add(rows, "h_e_inputs_fresh", "warn", "bad_date", f"asof_date={expected_input_asof}")

    expected_output_asof = expected_input_asof
    allowed_output_asof = {expected_input_asof} if expected_input_asof else set()
    if h_paused:
        all_input_dates = [str(v).strip() for v in input_asof.values() if str(v).strip()]
        if len(all_input_dates) == len(input_asof):
            expected_output_asof = min(all_input_dates)
            allowed_output_asof.add(expected_output_asof)

    if not allowed_output_asof:
        _add(rows, "h_e_outputs_latest_asof", "warn", "n/a", "missing expected input asof_date")
    else:
        output_paths = {
            "sku_sales_velocity": OUT / "sku_sales_velocity.csv",
            "sku_roi_snapshot": OUT / "sku_roi_snapshot.csv",
            "sku_restock_signals": OUT / "sku_restock_signals.csv",
            "sku_performance_summary": OUT / "sku_performance_summary.csv",
            "e_study_report": OUT / "e_study_report.csv",
        }
        bad_outputs: List[str] = []
        notes: List[str] = []
        for name, path in output_paths.items():
            val = _max_asof_date(path)
            notes.append(f"{name}={val or 'missing'}")
            if val not in allowed_output_asof:
                bad_outputs.append(name)
        if bad_outputs:
            pause_note = "; h_cycle_pause_requested=1" if h_paused else ""
            _add(
                rows,
                "h_e_outputs_latest_asof",
                "warn",
                str(len(bad_outputs)),
                f"expected_any={','.join(sorted(allowed_output_asof))}; mismatch={','.join(bad_outputs)}{pause_note}; "
                + "; ".join(notes),
            )
        else:
            pause_note = "; h_cycle_pause_requested=1" if h_paused else ""
            _add(
                rows,
                "h_e_outputs_latest_asof",
                "ok",
                "0",
                f"expected_any={','.join(sorted(allowed_output_asof))}{pause_note}",
            )

    _schema_check(
        rows,
        "z_schema_health_status",
        HEALTH_STATUS_CSV,
        ["timestamp_utc", "status", "fail_count", "warn_count", "notes"],
        optional=True,
    )
    _schema_check(
        rows,
        "f_schema_training_set",
        TRAINING_SET_PATH,
        ["sku", "asin", "marketplace", "notes", "enabled"],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_lab_cohort",
        LAB_COHORT_PATH,
        ["sku", "lane", "enabled", "effective_utc", "note"],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_head_boundaries",
        HEAD_BOUNDARIES_PATH,
        [
            "sku",
            "lane",
            "enabled",
            "effective_utc",
            "expiry_utc",
            "hard_floor_gbp",
            "ceiling_gbp",
            "max_move_per_cycle_gbp",
            "max_daily_down_move_gbp",
            "cooldown_minutes",
            "max_probes_per_day",
            "max_active_probe_skus",
            "note",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_supervisor_tactical_rules",
        SUPERVISOR_TACTICAL_RULES_PATH,
        [
            "sku",
            "lane",
            "state",
            "trigger_code",
            "allowed_probe_type",
            "target_adjustment_gbp",
            "cooldown_minutes",
            "expiry_minutes",
            "priority",
            "enabled",
            "stop_condition",
            "escalation_action",
            "note",
        ],
        optional=False,
    )
    try:
        cohort = _read_csv(LAB_COHORT_PATH)
        if cohort.empty:
            _add(rows, "h_lab_cohort_active_rows", "fail", "0", "empty cohort file")
        else:
            required = ["sku", "enabled"]
            missing = [c for c in required if c not in cohort.columns]
            if missing:
                _add(rows, "h_lab_cohort_active_rows", "fail", "missing_cols", ",".join(missing))
            else:
                enabled = cohort["enabled"].astype(str).str.strip().str.lower()
                active_count = int(enabled.isin({"1", "true", "yes", "y"}).sum())
                _add(
                    rows,
                    "h_lab_cohort_active_rows",
                    "ok" if active_count > 0 else "fail",
                    str(active_count),
                    "expected_at_least=1",
                )
    except Exception as exc:
        _add(rows, "h_lab_cohort_active_rows", "fail", "read_error", str(exc))
    try:
        boundaries = _read_csv(HEAD_BOUNDARIES_PATH)
        if boundaries.empty:
            _add(rows, "h_head_boundaries_active_rows", "fail", "0", "empty head boundary file")
            _add(rows, "h_head_boundary_pilot_present", "fail", "0", f"missing_active_sku={OFFICIAL_PILOT_SKU}")
            _add(rows, "h_head_boundaries_numeric_valid", "fail", "0", "no rows to validate")
        else:
            required = [
                "sku",
                "enabled",
                "hard_floor_gbp",
                "ceiling_gbp",
                "max_move_per_cycle_gbp",
                "max_daily_down_move_gbp",
                "cooldown_minutes",
                "max_probes_per_day",
                "max_active_probe_skus",
            ]
            missing = [c for c in required if c not in boundaries.columns]
            if missing:
                _add(rows, "h_head_boundaries_active_rows", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_head_boundary_pilot_present", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_head_boundaries_numeric_valid", "fail", "missing_cols", ",".join(missing))
            else:
                enabled = boundaries["enabled"].astype(str).str.strip().str.lower()
                active = boundaries[enabled.isin({"1", "true", "yes", "y"})].copy()
                active_count = int(len(active.index))
                _add(
                    rows,
                    "h_head_boundaries_active_rows",
                    "ok" if active_count > 0 else "fail",
                    str(active_count),
                    "expected_at_least=1",
                )

                active_skus = active["sku"].astype(str).str.strip().str.upper()
                pilot_present = int(active_skus.eq(OFFICIAL_PILOT_SKU).any())
                _add(
                    rows,
                    "h_head_boundary_pilot_present",
                    "ok" if pilot_present == 1 else "fail",
                    str(pilot_present),
                    f"expected_active_sku={OFFICIAL_PILOT_SKU}",
                )

                if active.empty:
                    _add(rows, "h_head_boundaries_numeric_valid", "fail", "0", "no active rows")
                else:
                    for col in [
                        "hard_floor_gbp",
                        "ceiling_gbp",
                        "max_move_per_cycle_gbp",
                        "max_daily_down_move_gbp",
                        "cooldown_minutes",
                        "max_probes_per_day",
                        "max_active_probe_skus",
                    ]:
                        active[col] = pd.to_numeric(active[col], errors="coerce")
                    invalid = (
                        active["hard_floor_gbp"].isna()
                        | active["ceiling_gbp"].isna()
                        | active["max_move_per_cycle_gbp"].isna()
                        | active["max_daily_down_move_gbp"].isna()
                        | active["cooldown_minutes"].isna()
                        | active["max_probes_per_day"].isna()
                        | active["max_active_probe_skus"].isna()
                        | (active["hard_floor_gbp"] < 0)
                        | (active["ceiling_gbp"] < active["hard_floor_gbp"])
                        | (active["max_move_per_cycle_gbp"] <= 0)
                        | (active["max_daily_down_move_gbp"] < active["max_move_per_cycle_gbp"])
                        | (active["cooldown_minutes"] < 1)
                        | (active["max_probes_per_day"] < 0)
                        | (active["max_active_probe_skus"] < 1)
                    )
                    invalid_count = int(invalid.sum())
                    _add(
                        rows,
                        "h_head_boundaries_numeric_valid",
                        "ok" if invalid_count == 0 else "fail",
                        str(invalid_count),
                        "rules=ceiling>=floor,max_move>0,max_daily_down>=max_move,cooldown>=1,max_probes>=0,max_active_probe_skus>=1",
                    )
    except Exception as exc:
        _add(rows, "h_head_boundaries_active_rows", "fail", "read_error", str(exc))
        _add(rows, "h_head_boundary_pilot_present", "fail", "read_error", str(exc))
        _add(rows, "h_head_boundaries_numeric_valid", "fail", "read_error", str(exc))
    try:
        rules = _read_csv(SUPERVISOR_TACTICAL_RULES_PATH)
        if rules.empty:
            _add(rows, "h_supervisor_tactical_active_rows", "fail", "0", "empty supervisor tactical rules file")
            _add(rows, "h_supervisor_tactical_pilot_coverage", "fail", "0", f"missing_active_sku={OFFICIAL_PILOT_SKU}")
            _add(rows, "h_supervisor_tactical_rules_valid", "fail", "0", "no rows to validate")
        else:
            required = [
                "sku",
                "state",
                "allowed_probe_type",
                "target_adjustment_gbp",
                "cooldown_minutes",
                "expiry_minutes",
                "priority",
                "enabled",
            ]
            missing = [c for c in required if c not in rules.columns]
            if missing:
                _add(rows, "h_supervisor_tactical_active_rows", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_supervisor_tactical_pilot_coverage", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_supervisor_tactical_rules_valid", "fail", "missing_cols", ",".join(missing))
            else:
                enabled = rules["enabled"].astype(str).str.strip().str.lower()
                active = rules[enabled.isin({"1", "true", "yes", "y"})].copy()
                active_count = int(len(active.index))
                _add(
                    rows,
                    "h_supervisor_tactical_active_rows",
                    "ok" if active_count > 0 else "fail",
                    str(active_count),
                    "expected_at_least=1",
                )

                active_skus = active["sku"].astype(str).str.strip().str.upper()
                pilot_present = int(active_skus.eq(OFFICIAL_PILOT_SKU).any())
                _add(
                    rows,
                    "h_supervisor_tactical_pilot_coverage",
                    "ok" if pilot_present == 1 else "fail",
                    str(pilot_present),
                    f"expected_active_sku={OFFICIAL_PILOT_SKU}",
                )

                if active.empty:
                    _add(rows, "h_supervisor_tactical_rules_valid", "fail", "0", "no active rows")
                else:
                    for col in [
                        "target_adjustment_gbp",
                        "cooldown_minutes",
                        "expiry_minutes",
                        "priority",
                    ]:
                        active[col] = pd.to_numeric(active[col], errors="coerce")

                    valid_states = {"unknown", "stable", "follower", "aggressor_candidate"}
                    valid_probe_types = {"lower", "match", "raise", "hold"}

                    state_col = active["state"].astype(str).str.strip().str.lower()
                    probe_col = active["allowed_probe_type"].astype(str).str.strip().str.lower()
                    invalid = (
                        active["target_adjustment_gbp"].isna()
                        | active["cooldown_minutes"].isna()
                        | active["expiry_minutes"].isna()
                        | active["priority"].isna()
                        | (active["target_adjustment_gbp"] < 0)
                        | (active["cooldown_minutes"] < 1)
                        | (active["expiry_minutes"] < 1)
                        | (active["priority"] < 1)
                        | (~state_col.isin(valid_states))
                        | (~probe_col.isin(valid_probe_types))
                    )
                    invalid_count = int(invalid.sum())
                    _add(
                        rows,
                        "h_supervisor_tactical_rules_valid",
                        "ok" if invalid_count == 0 else "fail",
                        str(invalid_count),
                        "rules=state_enum,probe_enum,target_adjustment>=0,cooldown>=1,expiry>=1,priority>=1",
                    )
    except Exception as exc:
        _add(rows, "h_supervisor_tactical_active_rows", "fail", "read_error", str(exc))
        _add(rows, "h_supervisor_tactical_pilot_coverage", "fail", "read_error", str(exc))
        _add(rows, "h_supervisor_tactical_rules_valid", "fail", "read_error", str(exc))
    _schema_check(
        rows,
        "h_schema_worker_probe_event_log",
        PROBE_EVENT_LOG_PATH,
        [
            "probe_event_id",
            "asof_date",
            "event_utc",
            "marketplace",
            "sku",
            "asin",
            "lane",
            "supervisor_state",
            "trigger_code",
            "probe_type",
            "action_price_before_gbp",
            "action_price_target_gbp",
            "hard_floor_gbp",
            "ceiling_gbp",
            "max_move_per_cycle_gbp",
            "cooldown_minutes",
            "expiry_utc",
            "reason_codes",
            "approved_rule_id",
            "source",
            "notes",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_worker_probe_response_log",
        PROBE_RESPONSE_LOG_PATH,
        [
            "probe_event_id",
            "asof_date",
            "response_utc",
            "response_window_minutes",
            "marketplace",
            "sku",
            "asin",
            "competitor_moved_flag",
            "competitor_move_direction",
            "competitor_move_size_gbp",
            "reaction_lag_minutes",
            "buy_box_price_gbp_after",
            "buy_box_channel_after",
            "buy_box_owner_after",
            "our_price_gbp_after",
            "outcome_code",
            "source",
            "notes",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_executioner_action_log",
        H_EXECUTIONER_ACTION_LOG_PATH,
        [
            "run_id",
            "event_utc",
            "sku",
            "marketplace_id",
            "probe_event_id",
            "probe_type",
            "price_before_gbp",
            "price_target_gbp",
            "price_executed_gbp",
            "live_write_attempted",
            "live_write_success",
            "http_status",
            "submission_id",
            "reason_codes",
            "source",
            "notes",
        ],
        optional=False,
    )
    _schema_check(
        rows,
        "h_schema_seller_profiles",
        H_SELLER_PROFILE_PATH,
        [
            "snapshot_file",
            "asof_date",
            "marketplace",
            "sku",
            "seller_id",
            "offers_seen",
            "rank_by_landed_price",
            "best_landed_price_gbp",
            "seller_landed_price_latest_gbp",
            "gap_to_best_landed_gbp",
            "tier",
            "tier_reason",
            "source",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_seller_soi",
        H_SELLER_SOI_PATH,
        [
            "asof_date",
            "marketplace",
            "sku",
            "seller_id",
            "rank_by_landed_price",
            "seller_landed_price_latest_gbp",
            "tier",
            "tier_reason",
            "source",
        ],
        optional=True,
    )
    try:
        cohort = _read_csv(LAB_COHORT_PATH)
        soi = _read_csv(H_SELLER_SOI_PATH)
        if cohort.empty:
            _add(rows, "h_seller_soi_active_coverage", "warn", "n/a", "cohort file missing or empty")
        else:
            enabled = cohort.get("enabled", "").astype(str).str.strip().str.lower()
            active_skus = set(
                cohort.loc[enabled.isin({"1", "true", "yes", "y"}), "sku"]
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )
            if not active_skus:
                _add(rows, "h_seller_soi_active_coverage", "warn", "0", "no active cohort SKUs")
            elif soi.empty:
                _add(rows, "h_seller_soi_active_coverage", "warn", str(len(active_skus)), "soi file empty")
            else:
                soi_skus = set(soi.get("sku", "").astype(str).str.strip().str.upper().tolist())
                missing = sorted([s for s in active_skus if s not in soi_skus])
                _add(
                    rows,
                    "h_seller_soi_active_coverage",
                    "ok" if not missing else "warn",
                    str(len(missing)),
                    "missing_skus=" + ",".join(missing) if missing else "all_active_skus_have_soi",
                )
    except Exception as exc:
        _add(rows, "h_seller_soi_active_coverage", "warn", "read_error", str(exc))
    try:
        event_log = _read_csv(PROBE_EVENT_LOG_PATH)
        if event_log.empty:
            _add(rows, "h_worker_probe_event_idempotent", "ok", "0", "no rows yet")
            _add(rows, "h_worker_probe_event_numeric_valid", "ok", "0", "no rows yet")
        else:
            required = [
                "probe_event_id",
                "probe_type",
                "action_price_before_gbp",
                "action_price_target_gbp",
                "hard_floor_gbp",
                "ceiling_gbp",
                "max_move_per_cycle_gbp",
                "cooldown_minutes",
                "expiry_utc",
                "event_utc",
                "supervisor_state",
            ]
            missing = [c for c in required if c not in event_log.columns]
            if missing:
                _add(rows, "h_worker_probe_event_idempotent", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_worker_probe_event_numeric_valid", "fail", "missing_cols", ",".join(missing))
            else:
                dup_count = int(event_log.duplicated(subset=["probe_event_id"], keep=False).sum())
                _add(rows, "h_worker_probe_event_idempotent", "ok" if dup_count == 0 else "fail", str(dup_count), "key=probe_event_id")

                e = event_log.copy()
                for col in [
                    "action_price_before_gbp",
                    "action_price_target_gbp",
                    "hard_floor_gbp",
                    "ceiling_gbp",
                    "max_move_per_cycle_gbp",
                    "cooldown_minutes",
                ]:
                    e[col] = pd.to_numeric(e[col], errors="coerce")

                allowed_state = {"unknown", "stable", "follower", "aggressor_candidate"}
                allowed_probe = {"lower", "match", "raise", "hold", "learn_down", "learn_up"}
                state_col = event_log["supervisor_state"].astype(str).str.strip().str.lower()
                probe_col = event_log["probe_type"].astype(str).str.strip().str.lower()

                bad_time = int(pd.to_datetime(event_log["event_utc"], errors="coerce", utc=True).isna().sum())
                bad_time += int(pd.to_datetime(event_log["expiry_utc"], errors="coerce", utc=True).isna().sum())

                move_size = (e["action_price_target_gbp"] - e["action_price_before_gbp"]).abs()
                invalid = (
                    e["action_price_before_gbp"].isna()
                    | e["action_price_target_gbp"].isna()
                    | e["hard_floor_gbp"].isna()
                    | e["ceiling_gbp"].isna()
                    | e["max_move_per_cycle_gbp"].isna()
                    | e["cooldown_minutes"].isna()
                    | (e["hard_floor_gbp"] < 0)
                    | (e["ceiling_gbp"] < e["hard_floor_gbp"])
                    | (e["action_price_target_gbp"] < e["hard_floor_gbp"])
                    | (e["action_price_target_gbp"] > e["ceiling_gbp"])
                    | (move_size > e["max_move_per_cycle_gbp"])
                    | (e["max_move_per_cycle_gbp"] <= 0)
                    | (e["cooldown_minutes"] < 1)
                    | (~state_col.isin(allowed_state))
                    | (~probe_col.isin(allowed_probe))
                )
                invalid_count = int(invalid.sum()) + bad_time
                _add(
                    rows,
                    "h_worker_probe_event_numeric_valid",
                    "ok" if invalid_count == 0 else "fail",
                    str(invalid_count),
                    "rules=target_in_floor_ceiling,move_within_max,cooldown>=1,state_enum,probe_enum,valid_timestamps",
                )
    except Exception as exc:
        _add(rows, "h_worker_probe_event_idempotent", "fail", "read_error", str(exc))
        _add(rows, "h_worker_probe_event_numeric_valid", "fail", "read_error", str(exc))
    try:
        event_log = _read_csv(PROBE_EVENT_LOG_PATH)
        if event_log.empty:
            _add(rows, "h_safe_mode_pilot_event_present", "fail", "0", "no probe events found")
            _add(rows, "h_safe_mode_pilot_scope_pilot_only", "ok", "0", "no safe mode rows yet")
            _add(rows, "h_safe_mode_pilot_actions_allowed", "ok", "0", "no safe mode rows yet")
        else:
            e = event_log.copy()
            source_col = e.get("source", "").astype(str).str.strip()

            safe = e.loc[source_col.eq("H007_run_safe_mode_pilot")].copy()
            if safe.empty:
                _add(
                    rows,
                    "h_safe_mode_pilot_event_present",
                    "fail",
                    "0",
                    "missing source=H007_run_safe_mode_pilot",
                )
                _add(rows, "h_safe_mode_pilot_scope_pilot_only", "ok", "0", "no safe mode rows yet")
                _add(rows, "h_safe_mode_pilot_actions_allowed", "ok", "0", "no safe mode rows yet")
            else:
                # Evaluate safe-mode scope on recent rows only, so historical pilot swaps
                # do not keep tripping the current pilot guardrail forever.
                window_hours = 48.0
                event_dt = pd.to_datetime(safe.get("event_utc", ""), errors="coerce", utc=True)
                cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
                recent_mask = event_dt.notna() & event_dt.ge(cutoff)
                safe_recent = safe.loc[recent_mask].copy()
                if safe_recent.empty:
                    _add(
                        rows,
                        "h_safe_mode_pilot_event_present",
                        "ok",
                        "0",
                        f"no recent safe mode rows;window_hours={window_hours:.1f}",
                    )
                    _add(
                        rows,
                        "h_safe_mode_pilot_scope_pilot_only",
                        "ok",
                        "0",
                        f"no recent safe mode rows;window_hours={window_hours:.1f}",
                    )
                    _add(
                        rows,
                        "h_safe_mode_pilot_actions_allowed",
                        "ok",
                        "0",
                        f"no recent safe mode rows;window_hours={window_hours:.1f}",
                    )
                    safe_recent = pd.DataFrame()

                if not safe_recent.empty:
                    safe_sku = safe_recent["sku"].astype(str).str.strip().str.upper()
                    pilot_rows = int(safe_sku.eq(OFFICIAL_PILOT_SKU).sum())
                    scope_invalid = int((~safe_sku.eq(OFFICIAL_PILOT_SKU)).sum())
                    safe_probe = safe_recent.get("probe_type", "").astype(str).str.strip().str.lower()
                    action_invalid = int((~safe_probe.isin({"hold", "match"})).sum())

                    _add(
                        rows,
                        "h_safe_mode_pilot_event_present",
                        "ok" if pilot_rows > 0 else "fail",
                        str(pilot_rows),
                        f"required_sku={OFFICIAL_PILOT_SKU};window_hours={window_hours:.1f};rows_considered={len(safe_recent)}",
                    )
                    _add(
                        rows,
                        "h_safe_mode_pilot_scope_pilot_only",
                        "ok" if scope_invalid == 0 else "fail",
                        str(scope_invalid),
                        f"required_scope_sku={OFFICIAL_PILOT_SKU};window_hours={window_hours:.1f};rows_considered={len(safe_recent)}",
                    )
                    _add(
                        rows,
                        "h_safe_mode_pilot_actions_allowed",
                        "ok" if action_invalid == 0 else "fail",
                        str(action_invalid),
                        "allowed=hold|match",
                    )
    except Exception as exc:
        _add(rows, "h_safe_mode_pilot_event_present", "fail", "read_error", str(exc))
        _add(rows, "h_safe_mode_pilot_scope_pilot_only", "fail", "read_error", str(exc))
        _add(rows, "h_safe_mode_pilot_actions_allowed", "fail", "read_error", str(exc))
    try:
        action_log = _read_csv(H_EXECUTIONER_ACTION_LOG_PATH)
        if action_log.empty:
            _add(rows, "h_executioner_action_log_idempotent", "warn", "0", "no action rows yet")
            _add(rows, "h_executioner_live_write_guardrails", "warn", "0", "no attempted live writes yet")
        else:
            required = [
                "probe_event_id",
                "sku",
                "live_write_attempted",
                "live_write_success",
                "price_before_gbp",
                "price_target_gbp",
                "price_executed_gbp",
                "source",
            ]
            missing = [c for c in required if c not in action_log.columns]
            if missing:
                _add(rows, "h_executioner_action_log_idempotent", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_executioner_live_write_guardrails", "fail", "missing_cols", ",".join(missing))
            else:
                dup_count = int(action_log.duplicated(subset=["probe_event_id"], keep=False).sum())
                _add(
                    rows,
                    "h_executioner_action_log_idempotent",
                    "ok" if dup_count == 0 else "fail",
                    str(dup_count),
                    "key=probe_event_id",
                )

                a = action_log.copy()
                a["price_before_gbp"] = pd.to_numeric(a["price_before_gbp"], errors="coerce")
                a["price_target_gbp"] = pd.to_numeric(a["price_target_gbp"], errors="coerce")
                a["price_executed_gbp"] = pd.to_numeric(a["price_executed_gbp"], errors="coerce")
                attempted = a["live_write_attempted"].astype(str).str.strip()
                succeeded = a["live_write_success"].astype(str).str.strip()
                sku_col = a["sku"].astype(str).str.strip().str.upper()
                src_col = a["source"].astype(str).str.strip()
                attempted_rows = attempted.eq("1")

                bool_invalid = int((~attempted.isin({"0", "1"})).sum() + (~succeeded.isin({"0", "1"})).sum())
                numeric_invalid = int(
                    a["price_before_gbp"].isna().sum()
                    + a["price_target_gbp"].isna().sum()
                    + a["price_executed_gbp"].isna().sum()
                )
                scope_invalid = int((attempted_rows & ~sku_col.eq(OFFICIAL_PILOT_SKU)).sum())
                source_invalid = int((attempted_rows & ~src_col.eq("run_H_pricing_cycle")).sum())
                success_conflict = int((succeeded.eq("1") & ~attempted_rows).sum())

                invalid_count = bool_invalid + numeric_invalid + scope_invalid + source_invalid + success_conflict
                _add(
                    rows,
                    "h_executioner_live_write_guardrails",
                    "ok" if invalid_count == 0 else "fail",
                    str(invalid_count),
                    "rules=bool_flags_valid,numeric_prices_present,attempt_scope_pilot_only,attempt_source=run_H_pricing_cycle",
                )
    except Exception as exc:
        _add(rows, "h_executioner_action_log_idempotent", "fail", "read_error", str(exc))
        _add(rows, "h_executioner_live_write_guardrails", "fail", "read_error", str(exc))
    try:
        response_log = _read_csv(PROBE_RESPONSE_LOG_PATH)
        if response_log.empty:
            _add(rows, "h_worker_probe_response_idempotent", "ok", "0", "no rows yet")
            _add(rows, "h_worker_probe_response_types_valid", "ok", "0", "no rows yet")
        else:
            required = [
                "probe_event_id",
                "response_window_minutes",
                "response_utc",
                "competitor_moved_flag",
                "competitor_move_direction",
                "competitor_move_size_gbp",
                "reaction_lag_minutes",
            ]
            missing = [c for c in required if c not in response_log.columns]
            if missing:
                _add(rows, "h_worker_probe_response_idempotent", "fail", "missing_cols", ",".join(missing))
                _add(rows, "h_worker_probe_response_types_valid", "fail", "missing_cols", ",".join(missing))
            else:
                dup_count = int(
                    response_log.duplicated(subset=["probe_event_id", "response_window_minutes"], keep=False).sum()
                )
                _add(
                    rows,
                    "h_worker_probe_response_idempotent",
                    "ok" if dup_count == 0 else "fail",
                    str(dup_count),
                    "key=probe_event_id+response_window_minutes",
                )

                r = response_log.copy()
                r["response_window_minutes"] = pd.to_numeric(r["response_window_minutes"], errors="coerce")
                r["competitor_move_size_gbp"] = pd.to_numeric(r["competitor_move_size_gbp"], errors="coerce")
                r["reaction_lag_minutes"] = pd.to_numeric(r["reaction_lag_minutes"], errors="coerce")

                moved = response_log["competitor_moved_flag"].astype(str).str.strip()
                direction = response_log["competitor_move_direction"].astype(str).str.strip().str.lower()
                bad_time = int(pd.to_datetime(response_log["response_utc"], errors="coerce", utc=True).isna().sum())
                valid_windows = {5, 15, 60, 240}
                bad_window = int((r["response_window_minutes"].isna() | ~r["response_window_minutes"].isin(valid_windows)).sum())
                bad_moved = int((~moved.isin({"0", "1"})).sum())
                bad_direction = int((~direction.isin({"up", "down", "flat", "unknown"})).sum())
                bad_move_size = int((r["competitor_move_size_gbp"].isna() | (r["competitor_move_size_gbp"] < 0)).sum())
                bad_reaction = int((r["reaction_lag_minutes"].notna() & (r["reaction_lag_minutes"] < 0)).sum())
                conflict_static = int(((moved == "0") & direction.isin({"up", "down"})).sum())
                conflict_dynamic = int(((moved == "1") & ~direction.isin({"up", "down"})).sum())

                invalid_count = (
                    bad_time
                    + bad_window
                    + bad_moved
                    + bad_direction
                    + bad_move_size
                    + bad_reaction
                    + conflict_static
                    + conflict_dynamic
                )
                _add(
                    rows,
                    "h_worker_probe_response_types_valid",
                    "ok" if invalid_count == 0 else "fail",
                    str(invalid_count),
                    "rules=window_enum,moved_flag_binary,direction_enum,move_size>=0,reaction_lag>=0,valid_timestamps",
                )
    except Exception as exc:
        _add(rows, "h_worker_probe_response_idempotent", "fail", "read_error", str(exc))
        _add(rows, "h_worker_probe_response_types_valid", "fail", "read_error", str(exc))
    _schema_check(
        rows,
        "h_schema_listing_offer_history",
        LISTING_OFFER_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "our_price",
            "buy_box_price",
            "buy_box_channel",
            "lowest_fba_price",
            "lowest_fbm_price",
            "offer_count_fba",
            "offer_count_fbm",
            "bsr",
            "bsr_category",
            "source",
            "notes",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_listing_offer_seller_history",
        LISTING_OFFER_SELLER_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "seller_id",
            "seller_seen_flag",
            "offer_price_gbp",
            "offer_shipping_price_gbp",
            "offer_landed_price_gbp",
            "is_prime",
            "fulfilment_channel",
            "min_delivery_days",
            "max_delivery_days",
            "delivery_range_days",
            "source",
            "notes",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_phase1_seller_history",
        PHASE1_SELLER_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "seller_id",
            "seller_seen_flag",
            "first_seen_timestamp",
            "last_seen_timestamp",
            "continuous_presence_hours",
            "absence_gap_hours",
            "reentry_after_absence_flag",
            "offer_price_gbp",
            "min_price_seen_gbp",
            "max_price_seen_gbp",
            "median_price_seen_gbp",
            "time_at_min_price_hours",
            "time_at_max_price_hours",
            "price_move_initiations",
            "follow_events",
            "reaction_lag_minutes",
            "directional_bias",
            "floor_set_events",
            "min_delivery_days",
            "max_delivery_days",
            "delivery_range_days",
            "is_prime",
            "delivery_delta_vs_fastest_days",
            "fulfilment_channel",
            "our_price",
            "our_price_changes",
            "our_delivery_posture",
            "manual_interventions",
            "intent_notes",
            "source",
            "notes",
        ],
        optional=True,
    )
    _phase1_contract_checks(rows, PHASE1_SELLER_HISTORY)
    _schema_check_jsonl(
        rows,
        "h_schema_api_call_log",
        API_CALL_LOG_JSONL,
        [
            "run_id",
            "timestamp_utc",
            "script_name",
            "endpoint",
            "marketplace",
            "sku_count",
            "http_status",
            "retries",
            "throttled",
            "backoff_seconds",
            "error_code",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_api_run_log",
        API_RUN_LOG_CSV,
        [
            "run_id",
            "started_utc",
            "finished_utc",
            "status",
            "calls_products_pricing_get_price",
            "calls_listings_items_get_item",
            "calls_finances_get_financial_events",
            "notes",
        ],
        optional=True,
    )
    try:
        if API_RUN_LOG_CSV.exists():
            api_runs = pd.read_csv(API_RUN_LOG_CSV, dtype=str).fillna("")
            window_hours = float(os.environ.get("API_RUN_FAIL_LOG_HOURS", "24"))
            cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
            if api_runs.empty or "status" not in api_runs.columns:
                _add(rows, "h_api_recent_fail_runs", "warn", "n/a", "missing status column or no rows")
            else:
                finished = (
                    _to_dt(api_runs["finished_utc"]) if "finished_utc" in api_runs.columns
                    else pd.Series(pd.NaT, index=api_runs.index)
                )
                started = (
                    _to_dt(api_runs["started_utc"]) if "started_utc" in api_runs.columns
                    else pd.Series(pd.NaT, index=api_runs.index)
                )
                event_ts = finished.where(~finished.isna(), started)
                recent_mask = event_ts.isna() | (event_ts >= cutoff)
                recent = api_runs.loc[recent_mask].copy()
                recent["_status"] = recent["status"].astype(str).str.upper()
                recent["_event_ts"] = event_ts.loc[recent.index]
                ok_ts = recent.loc[recent["_status"] == "OK", "_event_ts"].dropna()
                if ok_ts.empty:
                    fail_runs = recent[recent["_status"] == "FAIL"]
                else:
                    last_ok_ts = ok_ts.max()
                    fail_runs = recent[
                        (recent["_status"] == "FAIL")
                        & (recent["_event_ts"].isna() | (recent["_event_ts"] > last_ok_ts))
                    ]
                _add(
                    rows,
                    "h_api_recent_fail_runs",
                    "warn" if not fail_runs.empty else "ok",
                    str(len(fail_runs)),
                    f"window_hours={window_hours}",
                )
        else:
            _add(rows, "h_api_recent_fail_runs", "warn", "missing", f"path {API_RUN_LOG_CSV}")
    except Exception as exc:
        _add(rows, "h_api_recent_fail_runs", "warn", "read_error", str(exc))

    _schema_check_json_object(
        rows,
        "h_schema_api_rate_state",
        API_RATE_STATE_JSON,
        [],
        optional=True,
    )
    if SPAPI_LOCK_PATH.exists():
        lock_info = _file_info(SPAPI_LOCK_PATH)
        try:
            lock_mtime = datetime.fromisoformat(lock_info["mtime_utc"].replace("Z", "+00:00"))
            lock_age_hours = max((datetime.now(timezone.utc) - lock_mtime).total_seconds() / 3600.0, 0.0)
            lock_status = "fail" if lock_age_hours > 2.0 else "warn"
            _add(rows, "h_spapi_lock_present", lock_status, f"{lock_age_hours:.2f}", f"path {SPAPI_LOCK_PATH}")
        except Exception:
            _add(rows, "h_spapi_lock_present", "warn", "n/a", f"path {SPAPI_LOCK_PATH}")
    else:
        _add(rows, "h_spapi_lock_present", "ok", "0", "")
    for check_name, candidates in [
        ("h_cycle_stale_lock", H_LOCK_PATH_CANDIDATES),
        ("e_cycle_stale_lock", E_LOCK_PATH_CANDIDATES),
    ]:
        existing = [p for p in candidates if p.exists()]
        if not existing:
            _add(rows, check_name, "ok", "0", f"searched={','.join([str(p) for p in candidates])}")
            continue
        stale_paths: List[str] = []
        unreadable_paths: List[str] = []
        for lock_path in existing:
            try:
                payload = lock_path.read_text(encoding="utf-8")
                pid = _parse_lock_pid(payload)
                if pid is None:
                    unreadable_paths.append(str(lock_path))
                    continue
                if not _pid_alive(pid):
                    stale_paths.append(f"{lock_path}|pid={pid}")
            except Exception:
                unreadable_paths.append(str(lock_path))
        if stale_paths:
            _add(rows, check_name, "fail", str(len(stale_paths)), f"stale={';'.join(stale_paths)}")
        elif unreadable_paths:
            _add(rows, check_name, "warn", str(len(unreadable_paths)), f"unreadable={';'.join(unreadable_paths)}")
        else:
            _add(rows, check_name, "ok", "0", f"path={existing[0]}")
    snapshot_path = _latest_snapshot(LISTING_OFFER_SNAPSHOT_GLOB)
    if snapshot_path is None:
        _add(rows, "h_schema_listing_offer_snapshot", "warn", "missing", "no snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_listing_offer_snapshot",
            snapshot_path,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "our_price",
                "buy_box_price",
                "buy_box_channel",
                "lowest_fba_price",
                "lowest_fbm_price",
                "offer_count_fba",
                "offer_count_fbm",
                "bsr",
                "bsr_category",
                "source",
                "notes",
            ],
            optional=True,
        )
        try:
            snap = pd.read_csv(snapshot_path, dtype=str).fillna("")
            if snap.empty:
                _add(rows, "h_market_context_fill_nonzero", "warn", "0", "snapshot empty")
            else:
                required_nonzero = [
                    "buy_box_channel",
                    "lowest_fba_price",
                    "lowest_fbm_price",
                    "offer_count_fba",
                    "offer_count_fbm",
                ]
                zero_cols = []
                filled_parts = []
                for col in required_nonzero:
                    filled = int(snap[col].astype(str).str.strip().ne("").sum()) if col in snap.columns else 0
                    if filled == 0:
                        zero_cols.append(col)
                    filled_parts.append(f"{col}={filled}")
                if zero_cols:
                    _add(
                        rows,
                        "h_market_context_fill_nonzero",
                        "fail",
                        str(len(zero_cols)),
                        "zero_fill_cols=" + ",".join(zero_cols) + "; " + "; ".join(filled_parts),
                    )
                else:
                    _add(rows, "h_market_context_fill_nonzero", "ok", "0", "; ".join(filled_parts))
        except Exception as exc:
            _add(rows, "h_market_context_fill_nonzero", "warn", "read_error", str(exc))
    seller_snapshot_path = _latest_snapshot(LISTING_OFFER_SELLER_SNAPSHOT_GLOB)
    if seller_snapshot_path is None:
        _add(rows, "h_schema_listing_offer_seller_snapshot", "warn", "missing", "no seller snapshot files found")
        _add(rows, "h_seller_snapshot_landed_non_null_training", "warn", "missing", "no seller snapshot files found")
        _add(rows, "h_seller_snapshot_landed_ge_listing", "warn", "missing", "no seller snapshot files found")
        _add(rows, "h_seller_snapshot_shipping_non_negative", "warn", "missing", "no seller snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_listing_offer_seller_snapshot",
            seller_snapshot_path,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "seller_id",
                "seller_seen_flag",
                "offer_price_gbp",
                "offer_shipping_price_gbp",
                "offer_landed_price_gbp",
                "is_prime",
                "fulfilment_channel",
                "min_delivery_days",
                "max_delivery_days",
                "delivery_range_days",
                "source",
                "notes",
            ],
            optional=True,
        )
        try:
            seller_snap = pd.read_csv(seller_snapshot_path, dtype=str).fillna("")
            if seller_snap.empty:
                _add(rows, "h_seller_snapshot_landed_non_null_training", "warn", "0", "snapshot empty")
                _add(rows, "h_seller_snapshot_landed_ge_listing", "warn", "0", "snapshot empty")
                _add(rows, "h_seller_snapshot_shipping_non_negative", "warn", "0", "snapshot empty")
            else:
                train = _read_csv(TRAINING_SET_PATH)
                if train.empty or "sku" not in train.columns:
                    training_skus = set(seller_snap.get("sku", pd.Series(dtype=str)).astype(str).str.strip().str.upper().tolist())
                else:
                    if "enabled" in train.columns:
                        enabled = train["enabled"].astype(str).str.strip().str.lower()
                        train = train[enabled.isin({"1", "true", "yes", "y"})].copy()
                    training_skus = set(train["sku"].astype(str).str.strip().str.upper().tolist())
                snap_sku = seller_snap.get("sku", pd.Series(dtype=str)).astype(str).str.strip().str.upper()
                train_rows = seller_snap.loc[snap_sku.isin(training_skus)].copy() if training_skus else seller_snap.copy()
                if train_rows.empty:
                    _add(rows, "h_seller_snapshot_landed_non_null_training", "warn", "0", "no training rows in snapshot")
                    _add(rows, "h_seller_snapshot_landed_ge_listing", "warn", "0", "no training rows in snapshot")
                    _add(rows, "h_seller_snapshot_shipping_non_negative", "warn", "0", "no training rows in snapshot")
                else:
                    listing_num = pd.to_numeric(train_rows.get("offer_price_gbp", ""), errors="coerce")
                    shipping_num = pd.to_numeric(train_rows.get("offer_shipping_price_gbp", ""), errors="coerce")
                    landed_num = pd.to_numeric(train_rows.get("offer_landed_price_gbp", ""), errors="coerce")

                    needs_landed = listing_num.notna()
                    landed_blank = int((needs_landed & landed_num.isna()).sum())
                    _add(
                        rows,
                        "h_seller_snapshot_landed_non_null_training",
                        "ok" if landed_blank == 0 else "fail",
                        str(landed_blank),
                        f"training_rows={len(train_rows.index)}",
                    )

                    comparable = listing_num.notna() & landed_num.notna()
                    landed_lt_listing = int((comparable & (landed_num + 1e-9 < listing_num)).sum())
                    _add(
                        rows,
                        "h_seller_snapshot_landed_ge_listing",
                        "ok" if landed_lt_listing == 0 else "fail",
                        str(landed_lt_listing),
                        f"comparable_rows={int(comparable.sum())}",
                    )

                    shipping_present = shipping_num.notna()
                    shipping_negative = int((shipping_present & (shipping_num < 0)).sum())
                    _add(
                        rows,
                        "h_seller_snapshot_shipping_non_negative",
                        "ok" if shipping_negative == 0 else "fail",
                        str(shipping_negative),
                        f"shipping_rows={int(shipping_present.sum())}",
                    )
        except Exception as exc:
            _add(rows, "h_seller_snapshot_landed_non_null_training", "warn", "read_error", str(exc))
            _add(rows, "h_seller_snapshot_landed_ge_listing", "warn", "read_error", str(exc))
            _add(rows, "h_seller_snapshot_shipping_non_negative", "warn", "read_error", str(exc))

    market_snapshot_path = _latest_snapshot(HOS_DAILY_MARKET_SNAPSHOT_GLOB)
    market_required_cols = [
        "asof_date",
        "marketplace",
        "sku",
        "asin",
        "buy_box_price_raw_gross",
        "buy_box_price_used_gross",
        "buy_box_channel",
        "buy_box_seller_id",
        "buy_box_missing_flag",
        "buy_box_fallback_used_flag",
        "lowest_offer_price_gross",
        "lowest_fba_price_gross",
        "lowest_fbm_price_gross",
        "highest_offer_price_gross",
        "median_offer_price_gross",
        "price_spread_gross",
        "offer_count_total",
        "offer_count_fba",
        "offer_count_fbm",
        "amazon_present_flag",
        "seller_entry_count_today",
        "seller_exit_count_today",
        "our_delivery_days",
        "buy_box_delivery_days",
        "delivery_parity_flag",
        "prime_eligible_flag",
        "break_even_exvat_gbp",
        "break_even_gross_gbp",
        "token_cost_exvat_gbp",
        "min_price_gross_10pct",
        "max_price_gross_current",
    ]
    if market_snapshot_path is None:
        _add(rows, "h_market_snapshot_exists", "fail", "missing", "no hos_daily_market_snapshot files found")
        _add(rows, "h_market_snapshot_rows_10", "fail", "missing", "")
        _add(rows, "h_market_snapshot_required_columns", "fail", "missing", "")
        _add(rows, "h_market_snapshot_no_null_core_fields", "fail", "missing", "")
        _add(rows, "h_market_snapshot_delivery_parity_binary", "fail", "missing", "")
        _add(rows, "h_market_snapshot_econ_anchors_filled", "fail", "missing", "")
        _add(rows, "h_market_report_html_exists", "fail", "missing", "market snapshot missing")
        _add(rows, "h_market_report_pdf_exists", "fail", "missing", "market snapshot missing")
        _add(rows, "h_market_report_price_charts_count", "fail", "missing", "market snapshot missing")
        _add(rows, "h_market_report_seller_mix_charts_count", "fail", "missing", "market snapshot missing")
    else:
        _add(rows, "h_market_snapshot_exists", "ok", "yes", f"path {market_snapshot_path}")
        try:
            market = pd.read_csv(market_snapshot_path, dtype=str).fillna("")
        except Exception as exc:
            _add(rows, "h_market_snapshot_rows_10", "fail", "read_error", str(exc))
            _add(rows, "h_market_snapshot_required_columns", "fail", "read_error", str(exc))
            _add(rows, "h_market_snapshot_no_null_core_fields", "fail", "read_error", str(exc))
            _add(rows, "h_market_snapshot_delivery_parity_binary", "fail", "read_error", str(exc))
            _add(rows, "h_market_snapshot_econ_anchors_filled", "fail", "read_error", str(exc))
        else:
            row_count = len(market.index)
            _add(
                rows,
                "h_market_snapshot_rows_10",
                "ok" if row_count == 10 else "fail",
                str(row_count),
                "expected=10",
            )

            missing_cols = [c for c in market_required_cols if c not in market.columns]
            if missing_cols:
                _add(rows, "h_market_snapshot_required_columns", "fail", str(len(missing_cols)), ",".join(missing_cols))
            else:
                _add(rows, "h_market_snapshot_required_columns", "ok", "0", "")

            core_fields = ["buy_box_price_used_gross", "offer_count_fba", "offer_count_fbm"]
            missing_core_counts: List[str] = []
            missing_core_total = 0
            for col in core_fields:
                if col not in market.columns:
                    missing_core_total += row_count
                    missing_core_counts.append(f"{col}=MISSING_COL")
                    continue
                blank_count = int(market[col].astype(str).str.strip().eq("").sum())
                missing_core_total += blank_count
                missing_core_counts.append(f"{col}={blank_count}")
            _add(
                rows,
                "h_market_snapshot_no_null_core_fields",
                "ok" if missing_core_total == 0 else "fail",
                str(missing_core_total),
                "; ".join(missing_core_counts),
            )

            if "delivery_parity_flag" not in market.columns:
                _add(rows, "h_market_snapshot_delivery_parity_binary", "fail", str(row_count), "delivery_parity_flag missing")
            else:
                parity = market["delivery_parity_flag"].astype(str).str.strip()
                invalid = int((parity.ne("") & ~parity.isin({"0", "1"})).sum())
                _add(
                    rows,
                    "h_market_snapshot_delivery_parity_binary",
                    "ok" if invalid == 0 else "fail",
                    str(invalid),
                    "allowed_values=0,1",
                )

            train = _read_csv(TRAINING_SET_PATH)
            if train.empty or "sku" not in train.columns:
                training_skus = set(market.get("sku", pd.Series(dtype=str)).astype(str).str.strip().str.upper().tolist())
            else:
                if "enabled" in train.columns:
                    enabled = train["enabled"].astype(str).str.strip().str.lower()
                    train = train[enabled.isin({"1", "true", "yes", "y"})].copy()
                training_skus = set(train["sku"].astype(str).str.strip().str.upper().tolist())
            if not training_skus:
                _add(rows, "h_market_snapshot_econ_anchors_filled", "warn", "0", "no training SKUs found")
            else:
                market_sku = market.get("sku", pd.Series(dtype=str)).astype(str).str.strip().str.upper()
                train_mask = market_sku.isin(training_skus)
                train_rows = market.loc[train_mask].copy()
                if train_rows.empty:
                    _add(rows, "h_market_snapshot_econ_anchors_filled", "fail", str(len(training_skus)), "training SKUs missing from snapshot")
                else:
                    econ_cols = [
                        "break_even_exvat_gbp",
                        "break_even_gross_gbp",
                        "token_cost_exvat_gbp",
                        "min_price_gross_10pct",
                        "max_price_gross_current",
                    ]
                    missing_econ_total = 0
                    missing_econ_parts: List[str] = []
                    for col in econ_cols:
                        if col not in train_rows.columns:
                            missing = len(train_rows.index)
                        else:
                            missing = int(train_rows[col].astype(str).str.strip().eq("").sum())
                        missing_econ_total += missing
                        missing_econ_parts.append(f"{col}={missing}")
                    _add(
                        rows,
                        "h_market_snapshot_econ_anchors_filled",
                        "ok" if missing_econ_total == 0 else "fail",
                        str(missing_econ_total),
                        f"training_rows={len(train_rows.index)}; " + "; ".join(missing_econ_parts),
                    )

            report_asof_date = _max_asof_date(market_snapshot_path)
            if not report_asof_date:
                report_asof_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            report_html = HOS_DAILY_REPORT_DIR / f"hos_daily_report_{report_asof_date}.html"
            report_pdf = HOS_DAILY_REPORT_DIR / f"hos_daily_report_{report_asof_date}.pdf"
            expected_skus = int(market.get("sku", pd.Series(dtype=str)).astype(str).str.strip().replace("", pd.NA).dropna().nunique())
            if expected_skus == 0:
                expected_skus = int(len(market.index))

            _add(
                rows,
                "h_market_report_html_exists",
                "ok" if report_html.exists() else "fail",
                "yes" if report_html.exists() else "missing",
                f"path {report_html}",
            )
            _add(
                rows,
                "h_market_report_pdf_exists",
                "ok" if report_pdf.exists() else "fail",
                "yes" if report_pdf.exists() else "missing",
                f"path {report_pdf}",
            )

            price_chart_count = 0
            mix_chart_count = 0
            if HOS_DAILY_REPORT_CHART_DIR.exists():
                price_chart_count = len(list(HOS_DAILY_REPORT_CHART_DIR.glob(f"{report_asof_date}_*_price_trend.png")))
                mix_chart_count = len(list(HOS_DAILY_REPORT_CHART_DIR.glob(f"{report_asof_date}_*_seller_mix.png")))

            _add(
                rows,
                "h_market_report_price_charts_count",
                "ok" if price_chart_count >= expected_skus else "fail",
                str(price_chart_count),
                f"expected_at_least={expected_skus}",
            )
            _add(
                rows,
                "h_market_report_seller_mix_charts_count",
                "ok" if mix_chart_count >= expected_skus else "fail",
                str(mix_chart_count),
                f"expected_at_least={expected_skus}",
            )

    _schema_check(
        rows,
        "h_schema_inventory_history",
        INVENTORY_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "available",
            "inbound_working",
            "inbound_shipped",
            "inbound_receiving",
            "inbound_total",
            "source",
            "notes",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_inbound_history",
        INBOUND_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "inbound_working",
            "inbound_shipped",
            "inbound_receiving",
            "inbound_total",
            "source",
            "notes",
        ],
        optional=True,
    )
    _schema_check(
        rows,
        "h_schema_refund_adjustment_history",
        REFUND_ADJUSTMENT_HISTORY,
        [
            "timestamp_utc",
            "asof_date",
            "marketplace",
            "sku",
            "asin",
            "refund_event_count",
            "adjustment_event_count",
            "refund_units",
            "adjustment_units",
            "refund_amount_gbp",
            "adjustment_amount_gbp",
            "source",
            "notes",
        ],
        optional=True,
    )

    inv_snapshot = _latest_snapshot(INVENTORY_SNAPSHOT_GLOB)
    if inv_snapshot is None:
        _add(rows, "h_schema_inventory_snapshot", "warn", "missing", "no snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_inventory_snapshot",
            inv_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "available",
                "inbound_working",
                "inbound_shipped",
                "inbound_receiving",
                "inbound_total",
                "source",
                "notes",
            ],
            optional=True,
        )

    inbound_snapshot = _latest_snapshot(INBOUND_SNAPSHOT_GLOB)
    if inbound_snapshot is None:
        _add(rows, "h_schema_inbound_snapshot", "warn", "missing", "no snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_inbound_snapshot",
            inbound_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "inbound_working",
                "inbound_shipped",
                "inbound_receiving",
                "inbound_total",
                "source",
                "notes",
            ],
            optional=True,
        )
    refund_snapshot = _latest_snapshot(REFUND_ADJUSTMENT_SNAPSHOT_GLOB)
    if refund_snapshot is None:
        _add(rows, "h_schema_refund_adjustment_snapshot", "warn", "missing", "no snapshot files found")
    else:
        _schema_check(
            rows,
            "h_schema_refund_adjustment_snapshot",
            refund_snapshot,
            [
                "timestamp_utc",
                "asof_date",
                "marketplace",
                "sku",
                "asin",
                "refund_event_count",
                "adjustment_event_count",
                "refund_units",
                "adjustment_units",
                "refund_amount_gbp",
                "adjustment_amount_gbp",
                "source",
                "notes",
            ],
            optional=True,
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        if LISTING_OFFER_HISTORY.exists():
            offer_hist = pd.read_csv(LISTING_OFFER_HISTORY, dtype=str).fillna("")
            if "asof_date" not in offer_hist.columns:
                _add(rows, "h_listing_offer_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                offer_hist_today = offer_hist[offer_hist["asof_date"].astype(str) == today].copy()
                if offer_hist_today.empty:
                    _add(rows, "h_listing_offer_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    offer_dup = int(
                        offer_hist_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum()
                    )
                    offer_status = "fail" if offer_dup > 0 else "ok"
                    _add(rows, "h_listing_offer_history_idempotent_today", offer_status, str(offer_dup), f"asof_date={today}")
        else:
            _add(rows, "h_listing_offer_history_idempotent_today", "warn", "missing", f"path {LISTING_OFFER_HISTORY}")
    except Exception as exc:
        _add(rows, "h_listing_offer_history_idempotent_today", "warn", "read_error", str(exc))
    try:
        if LISTING_OFFER_SELLER_HISTORY.exists():
            seller_hist = pd.read_csv(LISTING_OFFER_SELLER_HISTORY, dtype=str).fillna("")
            if "asof_date" not in seller_hist.columns:
                _add(rows, "h_listing_offer_seller_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                seller_today = seller_hist[seller_hist["asof_date"].astype(str) == today].copy()
                if seller_today.empty:
                    _add(rows, "h_listing_offer_seller_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    seller_dup = int(
                        seller_today.duplicated(
                            subset=["asof_date", "marketplace", "sku", "asin", "seller_id"],
                            keep=False,
                        ).sum()
                    )
                    seller_status = "fail" if seller_dup > 0 else "ok"
                    _add(
                        rows,
                        "h_listing_offer_seller_history_idempotent_today",
                        seller_status,
                        str(seller_dup),
                        f"asof_date={today}",
                    )
        else:
            _add(
                rows,
                "h_listing_offer_seller_history_idempotent_today",
                "warn",
                "missing",
                f"path {LISTING_OFFER_SELLER_HISTORY}",
            )
    except Exception as exc:
        _add(rows, "h_listing_offer_seller_history_idempotent_today", "warn", "read_error", str(exc))

    try:
        if INVENTORY_HISTORY.exists():
            inv_hist = pd.read_csv(INVENTORY_HISTORY, dtype=str).fillna("")
            if "asof_date" not in inv_hist.columns:
                _add(rows, "h_inventory_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                inv_hist_today = inv_hist[inv_hist["asof_date"].astype(str) == today].copy()
                if inv_hist_today.empty:
                    if h_paused:
                        _add(
                            rows,
                            "h_inventory_history_idempotent_today",
                            "ok",
                            "0",
                            f"no rows for {today}; h_cycle_pause_requested=1",
                        )
                    else:
                        _add(rows, "h_inventory_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    inv_dup = int(inv_hist_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum())
                    inv_status = "fail" if inv_dup > 0 else "ok"
                    _add(rows, "h_inventory_history_idempotent_today", inv_status, str(inv_dup), f"asof_date={today}")
        else:
            _add(rows, "h_inventory_history_idempotent_today", "warn", "missing", f"path {INVENTORY_HISTORY}")
    except Exception as exc:
        _add(rows, "h_inventory_history_idempotent_today", "warn", "read_error", str(exc))

    try:
        if INBOUND_HISTORY.exists():
            inbound_hist = pd.read_csv(INBOUND_HISTORY, dtype=str).fillna("")
            if "asof_date" not in inbound_hist.columns:
                _add(rows, "h_inbound_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                inbound_hist_today = inbound_hist[inbound_hist["asof_date"].astype(str) == today].copy()
                if inbound_hist_today.empty:
                    if h_paused:
                        _add(
                            rows,
                            "h_inbound_history_idempotent_today",
                            "ok",
                            "0",
                            f"no rows for {today}; h_cycle_pause_requested=1",
                        )
                    else:
                        _add(rows, "h_inbound_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    inb_dup = int(inbound_hist_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum())
                    inb_status = "fail" if inb_dup > 0 else "ok"
                    _add(rows, "h_inbound_history_idempotent_today", inb_status, str(inb_dup), f"asof_date={today}")
        else:
            _add(rows, "h_inbound_history_idempotent_today", "warn", "missing", f"path {INBOUND_HISTORY}")
    except Exception as exc:
        _add(rows, "h_inbound_history_idempotent_today", "warn", "read_error", str(exc))
    try:
        if REFUND_ADJUSTMENT_HISTORY.exists():
            ra_hist = pd.read_csv(REFUND_ADJUSTMENT_HISTORY, dtype=str).fillna("")
            if "asof_date" not in ra_hist.columns:
                _add(rows, "h_refund_adjustment_history_idempotent_today", "warn", "missing_col", "asof_date")
            else:
                ra_hist_today = ra_hist[ra_hist["asof_date"].astype(str) == today].copy()
                if ra_hist_today.empty:
                    _add(rows, "h_refund_adjustment_history_idempotent_today", "warn", "0", f"no rows for {today}")
                else:
                    ra_dup = int(ra_hist_today.duplicated(subset=["asof_date", "sku", "marketplace"], keep=False).sum())
                    ra_status = "fail" if ra_dup > 0 else "ok"
                    _add(rows, "h_refund_adjustment_history_idempotent_today", ra_status, str(ra_dup), f"asof_date={today}")
        else:
            _add(rows, "h_refund_adjustment_history_idempotent_today", "warn", "missing", f"path {REFUND_ADJUSTMENT_HISTORY}")
    except Exception as exc:
        _add(rows, "h_refund_adjustment_history_idempotent_today", "warn", "read_error", str(exc))

    _phase1_rollout_checks(rows, now_utc_dt)

    # Write output
    df_all = _stabilize_index(pd.DataFrame(rows))
    df_all = _apply_alert_aging(df_all, alert_state_path, now_utc_dt)
    df_profile = _stabilize_index(df_all.loc[_profile_filter_mask(df_all, profile)].copy())
    if "status" not in df_profile.columns:
        df_profile["status"] = ""
    if "check" not in df_profile.columns:
        df_profile["check"] = ""
    df_profile.to_csv(checklist_path, index=False)
    if profile == "global":
        _write_cycle_alert_files(df_all)

    # Console summary
    log("writing checklist output")
    row_count = int(df_profile.shape[0])
    print({"status": "success", "rows": row_count, "snapshot": str(checklist_path), "profile": profile})
    try:
        print(df_profile.to_string(index=False))
    except Exception as exc:
        print({"status": "warn", "check": "a015_console_summary_render", "notes": f"{exc.__class__.__name__}: {exc}"})

    # Write health status + optional toast
    status = df_profile["status"].astype(str).str.lower()
    fail_count = int((status == "fail").sum())
    warn_count = int((status == "warn").sum())
    overall = "FAIL" if fail_count > 0 else "WARN" if warn_count > 0 else "OK"
    fail_checks = df_profile.loc[status == "fail", "check"].tolist()
    warn_checks = df_profile.loc[status == "warn", "check"].tolist()
    notes = f"fail={fail_count} warn={warn_count}"
    now_utc = now_utc_dt.isoformat()
    last_status = _read_last_health_status(health_status_path)
    pd.DataFrame(
        [{
            "timestamp_utc": now_utc,
            "status": overall,
            "fail_count": fail_count,
            "warn_count": warn_count,
            "notes": notes,
        }]
    ).to_csv(health_status_path, mode="a", header=False, index=False)

    if overall == "FAIL" and last_status != "FAIL":
        top_fail = ", ".join(fail_checks[:3])
        detail = f"FAIL: {top_fail}" if top_fail else "FAIL detected"
        body = f"{notes}. {detail}"
        if snooze["active"] == "yes":
            reason_suffix = f" reason={snooze['reason']}" if snooze["reason"] else ""
            log(f"toast suppressed by snooze until {snooze['snooze_until_utc']}{reason_suffix}")
        elif no_toast:
            log("toast suppressed by --no-toast")
        else:
            _send_toast("SellerOne Health Check ALERT", body[:240])

    # Exit code: 2 if any FAIL, 1 if WARN only, 0 if OK.
    if (status == "fail").any():
        raise SystemExit(2)
    if (status == "warn").any():
        raise SystemExit(1)


def _write_runtime_exception_snapshot(
    exc: Exception,
    *,
    profile: str = "global",
    checklist_path: Path | None = None,
    alert_state_path: Path | None = None,
    health_status_path: Path | None = None,
) -> None:
    profile_norm = _normalize_profile(profile)
    checklist = checklist_path or _default_checklist_for_profile(profile_norm)
    alert_state = alert_state_path or _default_alert_state_for_profile(profile_norm)
    health_status = health_status_path or _default_health_status_for_profile(profile_norm)
    now_utc_dt = datetime.now(timezone.utc)
    notes = f"{exc.__class__.__name__}: {exc}"
    notes = notes.replace("\n", " ").strip()[:500]
    rows = [
        {
            "check": "a015_runtime_exception",
            "status": "fail",
            "value": "1",
            "notes": notes,
        }
    ]
    df_out = pd.DataFrame(rows)
    try:
        OUT.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    try:
        checklist.parent.mkdir(parents=True, exist_ok=True)
        alert_state.parent.mkdir(parents=True, exist_ok=True)
        health_status.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        df_out = _apply_alert_aging(df_out, alert_state, now_utc_dt)
    except Exception:
        pass

    try:
        df_out.to_csv(checklist, index=False)
    except Exception:
        pass
    try:
        if profile_norm == "global":
            _write_cycle_alert_files(df_out)
    except Exception:
        pass

    try:
        if not health_status.exists():
            pd.DataFrame(columns=["timestamp_utc", "status", "fail_count", "warn_count", "notes"]).to_csv(
                health_status, index=False
            )
        pd.DataFrame(
            [
                {
                    "timestamp_utc": now_utc_dt.isoformat(),
                    "status": "FAIL",
                    "fail_count": 1,
                    "warn_count": 0,
                    "notes": "runtime_exception",
                }
            ]
        ).to_csv(health_status, mode="a", header=False, index=False)
    except Exception:
        pass

    print(
        {
            "status": "fail",
            "check": "a015_runtime_exception",
            "profile": profile_norm,
            "snapshot": str(checklist),
            "notes": notes,
        }
    )


def _run_main_fail_closed(main_fn) -> int:
    try:
        main_fn()
        return 0
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 1 if code else 0
    except Exception as exc:
        runtime = _resolve_runtime_paths(_parse_cli_args(strict=False))
        _write_runtime_exception_snapshot(
            exc,
            profile=str(runtime["profile"]),
            checklist_path=Path(runtime["checklist_path"]),
            alert_state_path=Path(runtime["alert_state_path"]),
            health_status_path=Path(runtime["health_status_path"]),
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(_run_main_fail_closed(main))

