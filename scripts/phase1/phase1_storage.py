from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "data"
DATA_DIR = Path(os.environ.get("PHASE1_DATA_DIR", str(DEFAULT_DATA_DIR)))
DEFAULT_LOCK_PATH = ROOT / "out" / "phase1.lock"
LOCK_PATH = Path(os.environ.get("PHASE1_LOCK_PATH", str(DEFAULT_LOCK_PATH)))
LOCK_EVENTS_PATH = ROOT / "out" / "systems" / "H" / "live" / "phase1_lock_events.log"
LOCK_EVENTS_ROTATE_MAX_BYTES = max(
    int(float(os.environ.get("PHASE1_LOCK_EVENTS_ROTATE_MAX_MB", "32") or "32") * 1024 * 1024),
    512 * 1024,
)
LOCK_EVENTS_ROTATE_MAX_FILES = max(
    int(float(os.environ.get("PHASE1_LOCK_EVENTS_ROTATE_MAX_FILES", "6") or "6")),
    2,
)
LOCK_EVENTS_DEDUP_INTERVAL_SECONDS = max(
    float(os.environ.get("PHASE1_LOCK_EVENTS_DEDUP_SECONDS", "5.0") or "5.0"),
    0.0,
)
H_SUPPRESSION_CASES_PATH = ROOT / "out" / "h_suppression_cases.csv"
H_SUPPRESSION_THRESHOLD_MEMORY_PATH = ROOT / "out" / "h_suppression_threshold_memory.csv"
H_SUPPRESSION_REACTIVATION_LOG_PATH = ROOT / "out" / "h_suppression_reactivation_log.csv"
H_CEILING_EVENTS_PATH = ROOT / "out" / "h_ceiling_events.csv"
H_STRATEGY_OUTCOME_LOG_PATH = ROOT / "out" / "h_strategy_outcome_log.csv"
H_STRATEGY_OUTCOME_DAILY_PATH = ROOT / "out" / "h_strategy_outcome_daily.csv"
H_STRATEGY_CONTROL_MEMORY_PATH = ROOT / "out" / "h_strategy_control_memory.csv"
H_DEFENSIVE_LISTING_ACTION_LOG_PATH = ROOT / "out" / "h_defensive_listing_action_log.csv"
H_DEFENSIVE_LISTING_CAMPAIGN_MEMORY_PATH = ROOT / "out" / "h_defensive_listing_campaign_memory.csv"
H_DEFENSIVE_LISTING_DAILY_PATH = ROOT / "out" / "h_defensive_listing_daily.csv"
PHASE1_LOCK_FORCE_STALE_SECONDS = max(
    float(os.environ.get("PHASE1_LOCK_FORCE_STALE_SECONDS", "120") or 120.0),
    1.0,
)
_LOCK_EVENT_DEDUP_CACHE: Dict[str, float] = {}


# Phase 1 table registry from the current phase_1.md spec.
PHASE1_TABLE_SCHEMAS: Dict[str, List[str]] = {
    "offer_snapshot_facts": [
        "offer_snapshot_id",
        "snapshot_ts_utc",
        "sku",
        "asin",
        "marketplace_id",
        "seller_id_raw",
        "seller_id_canonical",
        "offer_variant_id",
        "fulfilment_channel",
        "condition",
        "listing_price_gbp",
        "shipping_gbp",
        "landed_price_gbp",
        "min_delivery_days",
        "max_delivery_days",
        "is_prime",
        "is_featured_offer_winner",
        "is_our_offer",
        "promo_suspected_flag",
        "unknown_outcome_flag",
    ],
    "offer_variants": [
        "offer_variant_id",
        "sku",
        "seller_id_canonical",
        "fulfilment_channel",
        "condition",
        "shipping_template",
        "variant_first_seen_utc",
        "variant_last_seen_utc",
        "variant_active_flag",
    ],
    "sku_daily_intel": [
        "date_utc",
        "sku",
        "foep_price_gbp",
        "foep_status",
        "foep_last_refresh_utc",
        "bbp_max_sold_gbp",
        "cpt_gbp",
        "cpt_ceiling_input_gbp",
        "cpt_x1_2_gbp",
        "cpt_last_refresh_utc",
        "cpt_status",
        "cpt_risk_band",
        "cpt_delta_vs_buy_box_gbp",
        "cpt_delta_vs_buy_box_pct",
        "cpt_call_tier",
        "cpt_call_reason_codes_json",
        "ceiling_rule_value_gbp",
        "ceiling_source_used",
        "ceiling_inputs_missing_flag",
        "parked_flag",
        "park_reason_codes_json",
        "eligibility_ceiling_landed_gbp",
        "eligibility_source",
        "eligibility_confidence",
        "eligibility_reason_codes_json",
        "competitive_price_threshold_gbp",
        "competitive_price_gbp",
        "average_selling_price_gbp",
        "suppression_reactivation_target_landed_gbp",
        "suppression_target_source",
        "suppression_ceiling_landed_temp",
        "suppression_ceiling_source",
        "suppression_ceiling_confidence",
        "suppression_ceiling_expiry_utc",
        "anchor_floor_price_gbp",
        "compliance_ceiling_landed_gbp",
        "compliance_confidence",
        "compliance_status",
        "compliance_reason_code",
    ],
    "sku_ceiling_events": [
        "event_ts_utc",
        "sku",
        "our_delivery_penalty_gbp",
        "compliance_ceiling_landed_gbp",
        "eligibility_ceiling_landed_gbp",
        "suppression_ceiling_landed_temp",
        "demand_ceiling_landed_gbp",
        "final_ceiling_landed_gbp",
        "binding_ceiling_type",
        "ceiling_reason_codes_json",
    ],
    "variant_delta_memory": [
        "sku",
        "rival_key",
        "learned_delta_effective_gbp",
        "highest_delta_win_effective_gbp",
        "lowest_delta_loss_effective_gbp",
        "delta_confidence",
        "valid_test_count",
        "contaminated_test_count",
        "last_valid_test_utc",
    ],
    "execution_log": [
        "event_ts_utc",
        "sku",
        "state",
        "old_price_gbp",
        "new_price_gbp",
        "write_status",
        "write_error",
        "final_ceiling_landed_gbp",
        "hard_floor_gbp",
        "reason_codes_json",
    ],
    "decision_log": [
        "event_ts_utc",
        "ts_utc",
        "sku",
        "asin",
        "sku_or_asin",
        "buy_box_present",
        "outcome_known",
        "we_present",
        "action",
        "reason",
        "hold_reason",
        "proposed_price_gbp",
        "current_price_gbp",
        "best_rival_effective_price_gbp",
        "direct_competitor_variant_id",
        "writer_mode",
    ],
    "scenario_rollup": [
        "event_ts_utc",
        "sku",
        "asin",
        "hold_buy_box_missing_count",
        "hold_outcome_unknown_count",
        "allowed_to_act_count",
    ],
    "probe_windows": [
        "probe_id",
        "sku",
        "state_at_start",
        "start_ts_utc",
        "end_ts_utc",
        "start_snapshot_id",
        "end_snapshot_id",
        "start_featured_seller_id",
        "end_featured_seller_id",
        "observed_outcome",
        "market_structure_hash_start",
        "market_structure_hash_end",
        "oas_result",
    ],
    "oas_log": [
        "event_ts_utc",
        "probe_id",
        "sku",
        "context_quality_score",
        "admissible_flag",
        "hard_fail_reason_codes_json",
        "notes",
    ],
    "daily_intel_refresh_attempts": [
        "event_ts_utc",
        "date_utc",
        "sku",
        "status",
    ],
    "sku_phase_state": [
        "sku",
        "phase",
        "phase_entered_utc",
        "strategy_start_date",
        "phase_lock_until_utc",
        "below_floor_streak_days",
        "recovery_streak_days",
        "last_transition_reason_codes_json",
        "updated_utc",
    ],
    "suppression_threshold_memory": [
        "sku",
        "highest_eligible_price",
        "lowest_ineligible_price",
        "suppression_threshold_estimate",
        "suppression_threshold_confidence",
        "suppression_last_validated_utc",
        "anchor_floor_price",
        "suppression_ceiling_landed_temp",
        "suppression_ceiling_expiry_utc",
        "last_buy_box_state",
        "updated_utc",
    ],
    "strategy_control_memory": [
        "sku",
        "hold_until_utc",
        "retry_budget_remaining",
        "undercut_streak_count",
        "last_state",
        "last_target_price_gbp",
        "last_competitor_lowest_price_gbp",
        "last_stop_rule_code",
        "updated_utc",
    ],
    "sku_phase_transition_log": [
        "event_ts_utc",
        "sku",
        "from_phase",
        "to_phase",
        "transition_reason_codes_json",
        "diagnostics_snapshot_json",
    ],
}

# Phase 1 table behavior:
# - append-only event logs/snapshots
# - upsert dimensions/memory/intel state
APPEND_ONLY_TABLES = {
    "offer_snapshot_facts",
    "sku_ceiling_events",
    "execution_log",
    "decision_log",
    "scenario_rollup",
    "probe_windows",
    "oas_log",
    "daily_intel_refresh_attempts",
    "sku_phase_transition_log",
}

UPSERT_TABLE_KEYS: Dict[str, List[str]] = {
    "offer_variants": ["offer_variant_id"],
    "variant_delta_memory": ["sku", "rival_key"],
    "sku_daily_intel": ["date_utc", "sku"],
    "sku_phase_state": ["sku"],
    "suppression_threshold_memory": ["sku"],
    "strategy_control_memory": ["sku"],
}

SUPPRESSION_CASES_SCHEMA: List[str] = [
    "event_ts_utc",
    "sku",
    "asin",
    "suppression_case_id",
    "buy_box_state",
    "buy_box_eligible_offers",
    "pricing_health_active_flag",
    "pricing_health_disqualified_flag",
    "suppression_target_source",
    "suppression_reactivation_target_landed_gbp",
    "suppression_ceiling_landed_temp",
    "suppression_ceiling_expiry_utc",
    "anchor_floor_price",
    "action",
    "notes",
]

SUPPRESSION_REACTIVATION_LOG_SCHEMA: List[str] = [
    "event_ts_utc",
    "sku",
    "asin",
    "buy_box_state",
    "state",
    "current_price_gbp",
    "target_price_gbp",
    "suppression_target_source",
    "suppression_reactivation_target_landed_gbp",
    "suppression_ceiling_landed_temp",
    "anchor_floor_price",
    "write_status",
    "reason_codes_json",
]

H_CEILING_EVENTS_SCHEMA: List[str] = [
    "event_ts_utc",
    "run_id",
    "sku",
    "ceiling_event_id",
    "compliance_ceiling_gbp",
    "eligibility_ceiling_gbp",
    "demand_ceiling_gbp",
    "suppression_ceiling_gbp",
    "true_binding_ceiling_gbp",
    "true_binding_ceiling_type",
    "target_price_gbp",
    "hard_floor_gbp",
    "ceiling_conflict_flag",
    "reason_codes_json",
]

H_STRATEGY_OUTCOME_LOG_SCHEMA: List[str] = [
    "event_ts_utc",
    "run_id",
    "sku",
    "asin",
    "scenario_type",
    "chosen_tactic",
    "buy_box_state_before",
    "buy_box_state_after",
    "seller_count",
    "lowest_price_1_gbp",
    "lowest_price_2_gbp",
    "lowest_price_3_gbp",
    "our_price_before_gbp",
    "target_price_gbp",
    "price_written_gbp",
    "hold_until_utc",
    "response_window_minutes",
    "retry_budget_remaining",
    "stop_rule_code",
    "writer_outcome",
    "tactic_success_state",
    "reason_codes_json",
    "tactic_case_id",
]

H_STRATEGY_OUTCOME_DAILY_SCHEMA: List[str] = [
    "asof_date",
    "scenario_type",
    "chosen_tactic",
    "decision_rows",
    "applied_rows",
    "no_write_rows",
    "resolved_rows",
    "pending_rows",
    "success_rows",
    "failed_rows",
    "expired_rows",
    "aborted_rows",
    "success_rate_pct",
    "failed_rate_pct",
    "sample_min_rows",
    "provisional_sample_flag",
    "avg_seller_count",
    "avg_price_gap_to_lowest_gbp",
    "below_break_even_rows",
    "at_floor_rows",
    "notes",
]

H_STRATEGY_OUTCOME_DAILY_ZERO_FILL_COLUMNS: List[str] = [
    "decision_rows",
    "applied_rows",
    "no_write_rows",
    "resolved_rows",
    "pending_rows",
    "success_rows",
    "failed_rows",
    "expired_rows",
    "aborted_rows",
    "sample_min_rows",
    "provisional_sample_flag",
    "below_break_even_rows",
    "at_floor_rows",
]

H_DEFENSIVE_LISTING_ACTION_LOG_SCHEMA: List[str] = [
    "event_ts_utc",
    "run_id",
    "sku",
    "asin",
    "mode",
    "phase",
    "buy_box_state",
    "seller_count",
    "lowest_rival_price_gbp",
    "current_price_gbp",
    "target_price_gbp",
    "hard_floor_gbp",
    "final_ceiling_gbp",
    "write_required",
    "live_write_enabled",
    "write_status",
    "write_error",
    "attempted_write",
    "wrote",
    "reason_codes_json",
]

H_DEFENSIVE_LISTING_CAMPAIGN_MEMORY_SCHEMA: List[str] = [
    "sku",
    "asin",
    "mode",
    "campaign_started_utc",
    "last_seen_rival_utc",
    "last_absent_utc",
    "reset_count",
    "failed_defend_count",
    "writes_date",
    "writes_today",
    "cooldown_until_utc",
    "phase",
    "last_target_price_gbp",
    "last_rival_price_gbp",
    "last_action",
    "live_write_enabled",
    "updated_utc",
]

H_DEFENSIVE_LISTING_DAILY_SCHEMA: List[str] = [
    "asof_date",
    "sku",
    "asin",
    "mode",
    "enabled",
    "live_write_enabled",
    "phase",
    "action_rows",
    "write_required_rows",
    "applied_rows",
    "blocked_live_rows",
    "hold_rows",
    "last_target_price_gbp",
    "last_rival_price_gbp",
    "last_reason",
    "updated_utc",
]


def phase1_table_path(table_name: str) -> Path:
    env_override = str(os.environ.get("PHASE1_DATA_DIR", "") or "").strip()
    if env_override:
        return Path(env_override) / f"{table_name}.csv"
    return DATA_DIR / f"{table_name}.csv"


def _active_lock_path() -> Path:
    env_override = str(os.environ.get("PHASE1_LOCK_PATH", "") or "").strip()
    if env_override:
        return Path(env_override)
    return LOCK_PATH


def _table_schema(table_name: str) -> List[str]:
    if table_name not in PHASE1_TABLE_SCHEMAS:
        supported = ",".join(sorted(PHASE1_TABLE_SCHEMAS.keys()))
        raise ValueError(f"unsupported table '{table_name}', expected one of: {supported}")
    return PHASE1_TABLE_SCHEMAS[table_name]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rotate_log_file(path: Path, *, max_bytes: int, max_files: int) -> bool:
    if max_bytes <= 0 or max_files <= 1:
        return False
    try:
        if not path.exists():
            return False
        if int(path.stat().st_size) < int(max_bytes):
            return False
    except Exception:
        return False
    try:
        oldest = Path(f"{path}.{max_files}")
        if oldest.exists():
            oldest.unlink(missing_ok=True)
        for idx in range(max_files - 1, 0, -1):
            src = Path(f"{path}.{idx}")
            dst = Path(f"{path}.{idx + 1}")
            if src.exists():
                src.replace(dst)
        path.replace(Path(f"{path}.1"))
        return True
    except Exception:
        return False


def _dedupe_emit(cache: Dict[str, float], key: str, min_interval_seconds: float) -> bool:
    if min_interval_seconds <= 0:
        return True
    now = time.monotonic()
    last = float(cache.get(key, 0.0) or 0.0)
    if last > 0.0 and (now - last) < min_interval_seconds:
        return False
    cache[key] = now
    if len(cache) > 4096:
        stale_before = now - max(min_interval_seconds * 4.0, 60.0)
        stale_keys = [k for k, ts in cache.items() if ts < stale_before]
        for stale_key in stale_keys[:2048]:
            cache.pop(stale_key, None)
    return True


def _log_lock_event(event: str, **fields: object) -> None:
    try:
        event_norm = str(event or "").strip()
        dedupe_basis = [
            event_norm,
            str(fields.get("pid", "") or "").strip(),
            str(fields.get("path", "") or "").strip(),
            str(fields.get("reason", "") or "").strip(),
        ]
        noisy_events = {"PHASE1_LOCK_ACQUIRED", "PHASE1_LOCK_RELEASED"}
        if event_norm in noisy_events:
            dedupe_key = "|".join(dedupe_basis)
            if not _dedupe_emit(_LOCK_EVENT_DEDUP_CACHE, dedupe_key, LOCK_EVENTS_DEDUP_INTERVAL_SECONDS):
                return
        LOCK_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _rotate_log_file(
            LOCK_EVENTS_PATH,
            max_bytes=LOCK_EVENTS_ROTATE_MAX_BYTES,
            max_files=LOCK_EVENTS_ROTATE_MAX_FILES,
        )
        details = " ".join(f"{k}={str(v)}" for k, v in fields.items() if str(v) != "")
        line = f"{_utc_now_iso()} {event_norm}"
        if details:
            line = f"{line} {details}"
        with LOCK_EVENTS_PATH.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _parse_pid(payload: str) -> int | None:
    for part in str(payload).split("|"):
        part = part.strip()
        if part.startswith("pid="):
            try:
                return int(part.split("=", 1)[1].strip())
            except Exception:
                return None
    return None


def _parse_lock_utc(payload: str) -> datetime | None:
    for part in str(payload).split("|"):
        part = part.strip()
        if part.startswith("utc="):
            raw = part.split("=", 1)[1].strip()
            if not raw:
                return None
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                return None
    return None


@contextmanager
def _phase1_lock(timeout_seconds: float = 30.0):
    lock_path = _active_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                payload = f"phase1|pid={os.getpid()}|utc={_utc_now_iso()}\n"
                os.write(fd, payload.encode("utf-8"))
            finally:
                os.close(fd)
            _log_lock_event(
                "PHASE1_LOCK_ACQUIRED",
                pid=os.getpid(),
                path=str(lock_path),
            )
            break
        except FileExistsError:
            # Recover stale lock when PID is gone.
            try:
                payload = lock_path.read_text(encoding="utf-8")
                pid = _parse_pid(payload)
                lock_utc = _parse_lock_utc(payload)
                lock_age_seconds = None
                if lock_utc is not None:
                    lock_age_seconds = max((datetime.now(timezone.utc) - lock_utc).total_seconds(), 0.0)
                if lock_age_seconds is not None and lock_age_seconds >= PHASE1_LOCK_FORCE_STALE_SECONDS:
                    lock_path.unlink(missing_ok=True)
                    _log_lock_event(
                        "PHASE1_LOCK_STALE_RECOVERED",
                        stale_pid=pid,
                        path=str(lock_path),
                        reason="age_force_recover",
                        age_seconds=f"{lock_age_seconds:.1f}",
                        threshold_seconds=f"{PHASE1_LOCK_FORCE_STALE_SECONDS:.1f}",
                    )
                    continue
                if pid is not None and not _is_pid_alive(pid):
                    lock_path.unlink(missing_ok=True)
                    _log_lock_event(
                        "PHASE1_LOCK_STALE_RECOVERED",
                        stale_pid=pid,
                        path=str(lock_path),
                        reason="dead_pid",
                    )
                    continue
            except Exception:
                pass
            if (time.time() - start) >= timeout_seconds:
                _log_lock_event(
                    "PHASE1_LOCK_TIMEOUT",
                    pid=os.getpid(),
                    path=str(lock_path),
                    timeout_seconds=f"{timeout_seconds:.1f}",
                )
                raise TimeoutError(f"Timed out acquiring lock: {lock_path}")
            time.sleep(0.1)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)
        _log_lock_event(
            "PHASE1_LOCK_RELEASED",
            pid=os.getpid(),
            path=str(lock_path),
        )


def _atomic_write_rows(csv_path: Path, rows: List[Dict[str, str]], schema: Sequence[str]) -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = csv_path.with_name(f".{csv_path.name}.tmp.{os.getpid()}.{_stamp()}")
    normalized_rows = [{col: str(row.get(col, "")) for col in schema} for row in rows]
    def _csv_cell(value: object) -> str:
        text = str(value or "")
        if any(ch in text for ch in [",", "\"", "\n", "\r"]):
            text = "\"" + text.replace("\"", "\"\"") + "\""
        return text

    with tmp_path.open("w", encoding="utf-8", newline="\n") as fh:
        headers = [str(col) for col in schema]
        fh.write(",".join(headers) + "\n")
        for row in normalized_rows:
            fh.write(",".join(_csv_cell(row.get(col, "")) for col in headers) + "\n")
    # On Windows, another process may briefly hold the target file handle.
    # Retry replace a few times instead of failing the whole cycle on transient locks.
    retries = 20
    sleep_seconds = 0.1
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            os.replace(tmp_path, csv_path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(sleep_seconds)
    if last_error is not None:
        raise last_error
    os.replace(tmp_path, csv_path)


def _csv_cell(value: object) -> str:
    text = str(value or "")
    if any(ch in text for ch in [",", "\"", "\n", "\r"]):
        text = "\"" + text.replace("\"", "\"\"") + "\""
    return text


def _append_rows_in_place(csv_path: Path, rows: List[Dict[str, str]], schema: Sequence[str]) -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [str(col) for col in schema]
    file_exists = csv_path.exists()
    write_header = True
    if file_exists:
        try:
            write_header = csv_path.stat().st_size == 0
        except OSError:
            write_header = True

    with csv_path.open("a", encoding="utf-8", newline="\n") as fh:
        if write_header:
            fh.write(",".join(headers) + "\n")
        for row in rows:
            fh.write(",".join(_csv_cell(row.get(col, "")) for col in headers) + "\n")


def _id_columns(schema: Sequence[str]) -> List[str]:
    return [c for c in schema if c == "id" or c.endswith("_id")]


def _timestamp_columns(schema: Sequence[str]) -> List[str]:
    out: List[str] = []
    nullable_utc_cols = {"phase_lock_until_utc"}
    for col in schema:
        if col in nullable_utc_cols:
            continue
        if col.endswith("_utc") or col in {"timestamp_utc"}:
            out.append(col)
    return out


def _normalize_rows(
    rows: Iterable[Dict[str, object]],
    schema: Sequence[str],
    key_cols: Sequence[str] | None = None,
) -> List[Dict[str, str]]:
    key_set = set(key_cols or [])
    id_cols = _id_columns(schema)
    ts_cols = _timestamp_columns(schema)
    now_iso = _utc_now_iso()
    normalized: List[Dict[str, str]] = []
    for src in rows:
        out: Dict[str, str] = {col: str(src.get(col, "") if src.get(col, "") is not None else "") for col in schema}
        for col in ts_cols:
            if out.get(col, "").strip() == "":
                out[col] = now_iso
        for col in id_cols:
            if col in key_set:
                continue
            if out.get(col, "").strip() == "":
                out[col] = str(uuid.uuid4())
        normalized.append(out)
    return normalized


def read_table(csv_path: Path | str) -> List[Dict[str, str]]:
    path = Path(csv_path)
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        return []

    def _parse_csv_line(line: str) -> List[str]:
        values: List[str] = []
        cell_chars: List[str] = []
        in_quotes = False
        i = 0
        while i < len(line):
            ch = line[i]
            if in_quotes:
                if ch == "\"":
                    if i + 1 < len(line) and line[i + 1] == "\"":
                        cell_chars.append("\"")
                        i += 1
                    else:
                        in_quotes = False
                else:
                    cell_chars.append(ch)
            else:
                if ch == ",":
                    values.append("".join(cell_chars))
                    cell_chars = []
                elif ch == "\"":
                    in_quotes = True
                else:
                    cell_chars.append(ch)
            i += 1
        values.append("".join(cell_chars))
        return values

    headers = [str(col) for col in _parse_csv_line(lines[0])]
    if not headers:
        return []
    out: List[Dict[str, str]] = []
    for line in lines[1:]:
        if line == "":
            continue
        values = _parse_csv_line(line)
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        elif len(values) > len(headers):
            values = values[: len(headers)]
        out.append({headers[idx]: str(values[idx] or "") for idx in range(len(headers))})
    return out


SUPPRESSION_TARGET_SOURCE_FALLBACK = "NONE_UNAVAILABLE"
SUPPRESSION_CEILING_FALLBACK = "UNAVAILABLE"


def _text_cell(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_non_empty_text(*values: object) -> str:
    for value in values:
        text = _text_cell(value)
        if text != "":
            return text
    return ""


def _normalize_suppression_target_source(value: object) -> str:
    text = _text_cell(value).upper()
    if text != "":
        return text
    return SUPPRESSION_TARGET_SOURCE_FALLBACK


def _normalize_suppression_case_row(row: Mapping[str, object]) -> Dict[str, object]:
    out: Dict[str, object] = dict(row)
    out["suppression_target_source"] = _normalize_suppression_target_source(out.get("suppression_target_source", ""))
    ceiling = _first_non_empty_text(
        out.get("suppression_ceiling_landed_temp", ""),
        out.get("suppression_reactivation_target_landed_gbp", ""),
        out.get("anchor_floor_price", ""),
    )
    out["suppression_ceiling_landed_temp"] = ceiling if ceiling != "" else SUPPRESSION_CEILING_FALLBACK
    if _text_cell(out.get("suppression_reactivation_target_landed_gbp", "")) == "":
        out["suppression_reactivation_target_landed_gbp"] = str(out.get("suppression_ceiling_landed_temp", ""))
    return out


def _normalize_suppression_reactivation_row(row: Mapping[str, object]) -> Dict[str, object]:
    out: Dict[str, object] = dict(row)
    out["suppression_target_source"] = _normalize_suppression_target_source(out.get("suppression_target_source", ""))
    ceiling = _first_non_empty_text(
        out.get("suppression_ceiling_landed_temp", ""),
        out.get("suppression_reactivation_target_landed_gbp", ""),
        out.get("target_price_gbp", ""),
        out.get("current_price_gbp", ""),
        out.get("anchor_floor_price", ""),
    )
    out["suppression_ceiling_landed_temp"] = ceiling if ceiling != "" else SUPPRESSION_CEILING_FALLBACK
    if _text_cell(out.get("suppression_reactivation_target_landed_gbp", "")) == "":
        out["suppression_reactivation_target_landed_gbp"] = str(out.get("suppression_ceiling_landed_temp", ""))
    return out


def _normalize_h_strategy_outcome_daily_row(row: Mapping[str, object]) -> Dict[str, object]:
    out: Dict[str, object] = {col: row.get(col, "") for col in H_STRATEGY_OUTCOME_DAILY_SCHEMA}
    for col in H_STRATEGY_OUTCOME_DAILY_ZERO_FILL_COLUMNS:
        if _text_cell(out.get(col, "")) == "":
            out[col] = "0"
    try:
        decision_rows = max(int(float(str(out.get("decision_rows", "0") or "0"))), 0)
    except Exception:
        decision_rows = 0
    try:
        at_floor_rows = max(int(float(str(out.get("at_floor_rows", "0") or "0"))), 0)
    except Exception:
        at_floor_rows = 0
    try:
        below_break_even_rows = max(int(float(str(out.get("below_break_even_rows", "0") or "0"))), 0)
    except Exception:
        below_break_even_rows = 0
    out["at_floor_rows"] = str(min(at_floor_rows, decision_rows))
    out["below_break_even_rows"] = str(min(below_break_even_rows, decision_rows))
    return out


def _normalize_h_strategy_outcome_daily_file_in_place() -> None:
    with _phase1_lock():
        rows = read_table(H_STRATEGY_OUTCOME_DAILY_PATH)
        if not rows:
            return
        normalized = [_normalize_h_strategy_outcome_daily_row(row) for row in rows]
        _atomic_write_rows(H_STRATEGY_OUTCOME_DAILY_PATH, [{k: str(v or "") for k, v in row.items()} for row in normalized], H_STRATEGY_OUTCOME_DAILY_SCHEMA)


def append_rows(
    csv_path: Path | str,
    rows: Iterable[Dict[str, object]],
    schema: Sequence[str],
) -> None:
    path = Path(csv_path)
    schema = list(schema)
    new_rows = _normalize_rows(rows, schema)
    if not new_rows:
        return
    with _phase1_lock():
        _append_rows_in_place(path, new_rows, schema)


def upsert_rows(
    csv_path: Path | str,
    rows: Iterable[Dict[str, object]],
    key_cols: Sequence[str],
    schema: Sequence[str],
) -> None:
    path = Path(csv_path)
    schema = list(schema)
    key_cols = list(key_cols)
    if not key_cols:
        raise ValueError("key_cols is required for upsert_rows")
    for key in key_cols:
        if key not in schema:
            raise ValueError(f"key column not in schema: {key}")

    incoming = _normalize_rows(rows, schema, key_cols=key_cols)
    if not incoming:
        return

    for row in incoming:
        missing_keys = [k for k in key_cols if row.get(k, "").strip() == ""]
        if missing_keys:
            raise ValueError(f"upsert row missing key(s): {','.join(missing_keys)}")

    with _phase1_lock():
        existing = read_table(path)
        index: Dict[tuple[str, ...], Dict[str, str]] = {}
        order: List[tuple[str, ...]] = []
        for row in existing:
            k = tuple(row.get(c, "").strip() for c in key_cols)
            index[k] = row
            order.append(k)
        for row in incoming:
            k = tuple(row.get(c, "").strip() for c in key_cols)
            if k not in index:
                order.append(k)
            index[k] = row
        merged = [index[k] for k in order]
        _atomic_write_rows(path, merged, schema)


def append(table: str, rows: Iterable[Dict[str, object]]) -> None:
    if table not in APPEND_ONLY_TABLES:
        expected = ",".join(sorted(APPEND_ONLY_TABLES))
        raise ValueError(f"table '{table}' is not append-only, expected one of: {expected}")
    schema = _table_schema(table)
    append_rows(phase1_table_path(table), rows, schema)


def upsert(table: str, key_cols: Sequence[str], rows: Iterable[Dict[str, object]]) -> None:
    schema = _table_schema(table)
    upsert_rows(phase1_table_path(table), rows, key_cols=key_cols, schema=schema)


def write_table(table: str, rows: Iterable[Dict[str, object]]) -> None:
    # Task 1 adapter entrypoint:
    # - append-only tables use append
    # - dimensions/memory/intel use upsert with pinned keys
    if table in APPEND_ONLY_TABLES:
        append(table, rows)
        return
    key_cols = UPSERT_TABLE_KEYS.get(table)
    if key_cols:
        upsert(table, key_cols=key_cols, rows=rows)
        return
    raise ValueError(f"table '{table}' has no configured write mode")


def read_latest(table: str, where: Mapping[str, object] | None = None) -> Dict[str, str] | None:
    schema = _table_schema(table)
    path = phase1_table_path(table)
    rows = read_table(path)
    if not rows:
        return None
    where = where or {}
    filtered: List[Dict[str, str]] = []
    for row in rows:
        ok = True
        for key, val in where.items():
            key_s = str(key)
            if key_s not in schema:
                raise ValueError(f"where key '{key_s}' is not in schema for table '{table}'")
            if str(row.get(key_s, "")) != str(val):
                ok = False
                break
        if ok:
            filtered.append(row)
    if not filtered:
        return None

    ts_cols = [c for c in schema if c.endswith("_utc") or c == "timestamp_utc"]
    if not ts_cols:
        return filtered[-1]

    def _row_sort_key(r: Dict[str, str]) -> tuple:
        values = [str(r.get(c, "")) for c in ts_cols]
        return tuple(values + [str(r.get(c, "")) for c in schema])

    return sorted(filtered, key=_row_sort_key)[-1]


def read_where(table: str, where: Mapping[str, object] | None = None) -> List[Dict[str, str]]:
    schema = _table_schema(table)
    where = where or {}
    rows = read_table(phase1_table_path(table))
    if not where:
        return rows
    out: List[Dict[str, str]] = []
    for row in rows:
        matched = True
        for key, val in where.items():
            key_s = str(key)
            if key_s not in schema:
                raise ValueError(f"where key '{key_s}' is not in schema for table '{table}'")
            if str(row.get(key_s, "")) != str(val):
                matched = False
                break
        if matched:
            out.append(row)
    return out


def read_by_keys(table: str, key_values: Mapping[str, object]) -> Dict[str, str] | None:
    key_cols = UPSERT_TABLE_KEYS.get(table)
    if not key_cols:
        raise ValueError(f"table '{table}' has no configured key lookup")
    where = {key: key_values.get(key, "") for key in key_cols}
    rows = read_where(table, where=where)
    if not rows:
        return None
    return rows[-1]


def ensure_table(table: str) -> Path:
    schema = _table_schema(table)
    path = phase1_table_path(table)
    with _phase1_lock():
        if not path.exists():
            _atomic_write_rows(path, [], schema)
            return path
        existing_rows = read_table(path)
        _atomic_write_rows(path, existing_rows, schema)
    return path


def ensure_phase_engine_tables() -> None:
    ensure_table("sku_phase_state")
    ensure_table("sku_phase_transition_log")


def upsert_sku_phase_state(row: Mapping[str, object]) -> None:
    upsert("sku_phase_state", key_cols=["sku"], rows=[dict(row)])


def append_sku_phase_transition(row: Mapping[str, object]) -> None:
    append("sku_phase_transition_log", [dict(row)])


def append_suppression_cases(rows: Iterable[Dict[str, object]]) -> None:
    normalized = [_normalize_suppression_case_row(row) for row in rows]
    append_rows(H_SUPPRESSION_CASES_PATH, normalized, SUPPRESSION_CASES_SCHEMA)


def upsert_suppression_threshold_memory(rows: Iterable[Dict[str, object]]) -> None:
    upsert("suppression_threshold_memory", key_cols=["sku"], rows=rows)
    upsert_rows(
        H_SUPPRESSION_THRESHOLD_MEMORY_PATH,
        rows,
        key_cols=["sku"],
        schema=PHASE1_TABLE_SCHEMAS["suppression_threshold_memory"],
    )


def upsert_strategy_control_memory(rows: Iterable[Dict[str, object]]) -> None:
    upsert("strategy_control_memory", key_cols=["sku"], rows=rows)
    upsert_rows(
        H_STRATEGY_CONTROL_MEMORY_PATH,
        rows,
        key_cols=["sku"],
        schema=PHASE1_TABLE_SCHEMAS["strategy_control_memory"],
    )


def append_suppression_reactivation_log(rows: Iterable[Dict[str, object]]) -> None:
    normalized = [_normalize_suppression_reactivation_row(row) for row in rows]
    append_rows(H_SUPPRESSION_REACTIVATION_LOG_PATH, normalized, SUPPRESSION_REACTIVATION_LOG_SCHEMA)


def append_h_ceiling_events(rows: Iterable[Dict[str, object]]) -> None:
    append_rows(H_CEILING_EVENTS_PATH, rows, H_CEILING_EVENTS_SCHEMA)


def append_h_strategy_outcome_log(rows: Iterable[Dict[str, object]]) -> None:
    append_rows(H_STRATEGY_OUTCOME_LOG_PATH, rows, H_STRATEGY_OUTCOME_LOG_SCHEMA)


def upsert_h_strategy_outcome_log(rows: Iterable[Dict[str, object]]) -> None:
    upsert_rows(
        H_STRATEGY_OUTCOME_LOG_PATH,
        rows,
        key_cols=["tactic_case_id"],
        schema=H_STRATEGY_OUTCOME_LOG_SCHEMA,
    )


def upsert_h_strategy_outcome_daily(rows: Iterable[Dict[str, object]]) -> None:
    normalized_rows = [_normalize_h_strategy_outcome_daily_row(row) for row in rows]
    upsert_rows(
        H_STRATEGY_OUTCOME_DAILY_PATH,
        normalized_rows,
        key_cols=["asof_date", "scenario_type", "chosen_tactic"],
        schema=H_STRATEGY_OUTCOME_DAILY_SCHEMA,
    )
    # Keep legacy rows compatible when schema expands with new count columns.
    _normalize_h_strategy_outcome_daily_file_in_place()


def read_h_defensive_listing_memory(sku: str) -> Dict[str, str]:
    sku_text = str(sku or "").strip()
    if not sku_text:
        return {}
    rows = read_table(H_DEFENSIVE_LISTING_CAMPAIGN_MEMORY_PATH)
    matches = [row for row in rows if str(row.get("sku", "")).strip() == sku_text]
    return dict(matches[-1]) if matches else {}


def upsert_h_defensive_listing_memory(rows: Iterable[Dict[str, object]]) -> None:
    upsert_rows(
        H_DEFENSIVE_LISTING_CAMPAIGN_MEMORY_PATH,
        rows,
        key_cols=["sku"],
        schema=H_DEFENSIVE_LISTING_CAMPAIGN_MEMORY_SCHEMA,
    )


def append_h_defensive_listing_action_log(rows: Iterable[Dict[str, object]]) -> None:
    append_rows(
        H_DEFENSIVE_LISTING_ACTION_LOG_PATH,
        rows,
        H_DEFENSIVE_LISTING_ACTION_LOG_SCHEMA,
    )


def upsert_h_defensive_listing_daily(rows: Iterable[Dict[str, object]]) -> None:
    upsert_rows(
        H_DEFENSIVE_LISTING_DAILY_PATH,
        rows,
        key_cols=["asof_date", "sku", "asin", "mode"],
        schema=H_DEFENSIVE_LISTING_DAILY_SCHEMA,
    )

