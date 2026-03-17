from __future__ import annotations

import csv
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
LOCK_PATH = ROOT / "out" / "phase1.lock"
LOCK_EVENTS_PATH = ROOT / "out" / "systems" / "H" / "live" / "phase1_lock_events.log"
PHASE1_LOCK_FORCE_STALE_SECONDS = max(
    float(os.environ.get("PHASE1_LOCK_FORCE_STALE_SECONDS", "120") or 120.0),
    1.0,
)


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
        "compliance_ceiling_landed_gbp",
        "compliance_confidence",
    ],
    "sku_ceiling_events": [
        "event_ts_utc",
        "sku",
        "our_delivery_penalty_gbp",
        "compliance_ceiling_landed_gbp",
        "eligibility_ceiling_landed_gbp",
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
}

UPSERT_TABLE_KEYS: Dict[str, List[str]] = {
    "offer_variants": ["offer_variant_id"],
    "variant_delta_memory": ["sku", "rival_key"],
    "sku_daily_intel": ["date_utc", "sku"],
}


def phase1_table_path(table_name: str) -> Path:
    return DATA_DIR / f"{table_name}.csv"


def _table_schema(table_name: str) -> List[str]:
    if table_name not in PHASE1_TABLE_SCHEMAS:
        supported = ",".join(sorted(PHASE1_TABLE_SCHEMAS.keys()))
        raise ValueError(f"unsupported table '{table_name}', expected one of: {supported}")
    return PHASE1_TABLE_SCHEMAS[table_name]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_lock_event(event: str, **fields: object) -> None:
    try:
        LOCK_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        details = " ".join(f"{k}={str(v)}" for k, v in fields.items() if str(v) != "")
        line = f"{_utc_now_iso()} {event}"
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
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    while True:
        try:
            fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                payload = f"phase1|pid={os.getpid()}|utc={_utc_now_iso()}\n"
                os.write(fd, payload.encode("utf-8"))
            finally:
                os.close(fd)
            _log_lock_event(
                "PHASE1_LOCK_ACQUIRED",
                pid=os.getpid(),
                path=str(LOCK_PATH),
            )
            break
        except FileExistsError:
            # Recover stale lock when PID is gone.
            try:
                payload = LOCK_PATH.read_text(encoding="utf-8")
                pid = _parse_pid(payload)
                lock_utc = _parse_lock_utc(payload)
                lock_age_seconds = None
                if lock_utc is not None:
                    lock_age_seconds = max((datetime.now(timezone.utc) - lock_utc).total_seconds(), 0.0)
                if lock_age_seconds is not None and lock_age_seconds >= PHASE1_LOCK_FORCE_STALE_SECONDS:
                    LOCK_PATH.unlink(missing_ok=True)
                    _log_lock_event(
                        "PHASE1_LOCK_STALE_RECOVERED",
                        stale_pid=pid,
                        path=str(LOCK_PATH),
                        reason="age_force_recover",
                        age_seconds=f"{lock_age_seconds:.1f}",
                        threshold_seconds=f"{PHASE1_LOCK_FORCE_STALE_SECONDS:.1f}",
                    )
                    continue
                if pid is not None and not _is_pid_alive(pid):
                    LOCK_PATH.unlink(missing_ok=True)
                    _log_lock_event(
                        "PHASE1_LOCK_STALE_RECOVERED",
                        stale_pid=pid,
                        path=str(LOCK_PATH),
                        reason="dead_pid",
                    )
                    continue
            except Exception:
                pass
            if (time.time() - start) >= timeout_seconds:
                _log_lock_event(
                    "PHASE1_LOCK_TIMEOUT",
                    pid=os.getpid(),
                    path=str(LOCK_PATH),
                    timeout_seconds=f"{timeout_seconds:.1f}",
                )
                raise TimeoutError(f"Timed out acquiring lock: {LOCK_PATH}")
            time.sleep(0.1)
    try:
        yield
    finally:
        LOCK_PATH.unlink(missing_ok=True)
        _log_lock_event(
            "PHASE1_LOCK_RELEASED",
            pid=os.getpid(),
            path=str(LOCK_PATH),
        )


def _atomic_write_rows(csv_path: Path, rows: List[Dict[str, str]], schema: Sequence[str]) -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = csv_path.with_name(f".{csv_path.name}.tmp.{os.getpid()}.{_stamp()}")
    with tmp_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(schema), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: str(row.get(col, "")) for col in schema})
    os.replace(tmp_path, csv_path)


def _id_columns(schema: Sequence[str]) -> List[str]:
    return [c for c in schema if c == "id" or c.endswith("_id")]


def _timestamp_columns(schema: Sequence[str]) -> List[str]:
    out: List[str] = []
    for col in schema:
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
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return []
        return [{k: str(v or "") for k, v in row.items()} for row in reader]


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
        existing = read_table(path)
        # Append-only contract: never modify previous rows.
        merged = existing + new_rows
        _atomic_write_rows(path, merged, schema)


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

