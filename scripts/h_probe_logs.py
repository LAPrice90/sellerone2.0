from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

OUT = Path("out")
LOCKS = OUT / "locks"
WAITING_ROOM_H = OUT / "waiting_room" / "h"
PROBE_EVENT_LOG_PATH = OUT / "h_worker_probe_event_log.csv"
PROBE_RESPONSE_LOG_PATH = OUT / "h_worker_probe_response_log.csv"

PROBE_EVENT_REQUIRED_COLUMNS: List[str] = [
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
]

PROBE_RESPONSE_REQUIRED_COLUMNS: List[str] = [
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
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _ensure_columns(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns].copy()


def _has_exact_columns(df: pd.DataFrame, columns: List[str]) -> bool:
    return list(df.columns) == list(columns)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp_for_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


@contextmanager
def _writer_lock(lock_name: str, timeout_seconds: float = 30.0):
    LOCKS.mkdir(parents=True, exist_ok=True)
    lock_path = LOCKS / lock_name
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"pid={os.getpid()} utc={_utc_now_iso()}\n".encode("utf-8"))
            finally:
                os.close(fd)
            break
        except FileExistsError:
            if (time.time() - start) >= timeout_seconds:
                raise TimeoutError(f"Timed out acquiring lock: {lock_path}")
            time.sleep(0.1)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _atomic_write_csv(df: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp.{os.getpid()}.{_stamp_for_id()}")
    df.to_csv(tmp, index=False)
    os.replace(tmp, target)


def _write_waiting_room_and_promote(
    df: pd.DataFrame,
    target: Path,
    required_columns: List[str],
) -> None:
    artifact = target.stem
    batch_id = f"{_stamp_for_id()}_{os.getpid()}"
    batch_dir = WAITING_ROOM_H / artifact / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    staged = _ensure_columns(df.copy(), required_columns)
    waiting_file = batch_dir / f"{artifact}.csv"
    manifest = batch_dir / "manifest.json"
    created_utc = _utc_now_iso()

    _atomic_write_csv(staged, waiting_file)
    manifest.write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "artifact": artifact,
                "state": "amber",
                "created_utc": created_utc,
                "row_count": int(len(staged.index)),
                "column_count": int(len(staged.columns)),
                "required_columns": list(required_columns),
                "target_path": str(target).replace("\\", "/"),
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    missing_cols = [c for c in required_columns if c not in staged.columns]
    final_state = "green" if not missing_cols else "red"
    validated_utc = _utc_now_iso()
    manifest.write_text(
        json.dumps(
            {
                "batch_id": batch_id,
                "artifact": artifact,
                "state": final_state,
                "created_utc": created_utc,
                "validated_utc": validated_utc,
                "row_count": int(len(staged.index)),
                "column_count": int(len(staged.columns)),
                "required_columns": list(required_columns),
                "missing_columns": missing_cols,
                "target_path": str(target).replace("\\", "/"),
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    if final_state != "green":
        raise ValueError(f"Waiting room validation failed for {target}: missing columns={','.join(missing_cols)}")

    _atomic_write_csv(staged, target)


def initialize_probe_logs(
    event_path: Path | None = None,
    response_path: Path | None = None,
) -> None:
    event_target = event_path or PROBE_EVENT_LOG_PATH
    response_target = response_path or PROBE_RESPONSE_LOG_PATH

    event_target.parent.mkdir(parents=True, exist_ok=True)
    response_target.parent.mkdir(parents=True, exist_ok=True)

    with _writer_lock("h_probe_event_log.write.lock"):
        event_df = _read_csv(event_target)
        if (not event_target.exists()) or (not _has_exact_columns(event_df, PROBE_EVENT_REQUIRED_COLUMNS)):
            _write_waiting_room_and_promote(
                _ensure_columns(event_df, PROBE_EVENT_REQUIRED_COLUMNS),
                event_target,
                PROBE_EVENT_REQUIRED_COLUMNS,
            )
    with _writer_lock("h_probe_response_log.write.lock"):
        response_df = _read_csv(response_target)
        if (not response_target.exists()) or (not _has_exact_columns(response_df, PROBE_RESPONSE_REQUIRED_COLUMNS)):
            _write_waiting_room_and_promote(
                _ensure_columns(response_df, PROBE_RESPONSE_REQUIRED_COLUMNS),
                response_target,
                PROBE_RESPONSE_REQUIRED_COLUMNS,
            )


def load_probe_event_log(path: Path | None = None) -> pd.DataFrame:
    target = path or PROBE_EVENT_LOG_PATH
    df = _read_csv(target)
    return _ensure_columns(df, PROBE_EVENT_REQUIRED_COLUMNS)


def load_probe_response_log(path: Path | None = None) -> pd.DataFrame:
    target = path or PROBE_RESPONSE_LOG_PATH
    df = _read_csv(target)
    return _ensure_columns(df, PROBE_RESPONSE_REQUIRED_COLUMNS)


def append_probe_events(
    records: List[Dict[str, str]],
    path: Path | None = None,
) -> pd.DataFrame:
    target = path or PROBE_EVENT_LOG_PATH
    initialize_probe_logs(event_path=target, response_path=PROBE_RESPONSE_LOG_PATH)
    with _writer_lock("h_probe_event_log.write.lock"):
        existing = load_probe_event_log(target)

        new_rows = pd.DataFrame(records, dtype=str).fillna("")
        new_rows = _ensure_columns(new_rows, PROBE_EVENT_REQUIRED_COLUMNS)
        if not new_rows.empty and new_rows["probe_event_id"].astype(str).str.strip().eq("").any():
            raise ValueError("probe_event_id is required for all event rows")

        combined = pd.concat([existing, new_rows], ignore_index=True)
        combined = combined.drop_duplicates(subset=["probe_event_id"], keep="last")
        combined = _ensure_columns(combined, PROBE_EVENT_REQUIRED_COLUMNS)
        combined = combined.sort_values(["event_utc", "probe_event_id"], kind="stable")
        _write_waiting_room_and_promote(combined, target, PROBE_EVENT_REQUIRED_COLUMNS)
        return combined


def append_probe_responses(
    records: List[Dict[str, str]],
    path: Path | None = None,
) -> pd.DataFrame:
    target = path or PROBE_RESPONSE_LOG_PATH
    initialize_probe_logs(event_path=PROBE_EVENT_LOG_PATH, response_path=target)
    with _writer_lock("h_probe_response_log.write.lock"):
        existing = load_probe_response_log(target)

        new_rows = pd.DataFrame(records, dtype=str).fillna("")
        new_rows = _ensure_columns(new_rows, PROBE_RESPONSE_REQUIRED_COLUMNS)
        if not new_rows.empty and new_rows["probe_event_id"].astype(str).str.strip().eq("").any():
            raise ValueError("probe_event_id is required for all response rows")
        if not new_rows.empty and new_rows["response_window_minutes"].astype(str).str.strip().eq("").any():
            raise ValueError("response_window_minutes is required for all response rows")

        combined = pd.concat([existing, new_rows], ignore_index=True)
        combined = combined.drop_duplicates(subset=["probe_event_id", "response_window_minutes"], keep="last")
        combined = _ensure_columns(combined, PROBE_RESPONSE_REQUIRED_COLUMNS)
        combined = combined.sort_values(["response_utc", "probe_event_id", "response_window_minutes"], kind="stable")
        _write_waiting_room_and_promote(combined, target, PROBE_RESPONSE_REQUIRED_COLUMNS)
        return combined
