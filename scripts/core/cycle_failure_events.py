from __future__ import annotations

import csv
import contextlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER_PATH = ROOT / "out" / "cycle_alerts" / "cycle_failure_events.csv"

FAILURE_EVENT_COLUMNS = [
    "event_id",
    "timestamp_utc",
    "cycle",
    "run_id",
    "final_state",
    "cause_code",
    "cause_detail",
    "step_name",
    "stage",
    "rc",
    "verification_status",
    "manifest_path",
    "health_path",
    "source_path",
    "recovery_action",
]

VALID_CAUSE_CODES = {
    "OUTPUT_STALE",
    "OUTPUT_MISSING",
    "CHILD_RC_NONZERO",
    "TIMEOUT_STALLED",
    "TIMEOUT_PROGRESSING",
    "MAINTENANCE_ABORT",
    "PUBLISH_PROOF_MISSING",
    "OWNER_CONTRACT_VIOLATION",
    "LOCK_STALE",
    "CREDENTIAL_ACCESS_DENIED",
    "SHEET_GUARDRAIL",
    "EXTERNAL_API_ERROR",
    "INTERRUPTED_SIGNAL",
    "FINALIZE_BLOCKED",
    "REQUIRED_OUTPUTS_MISSING",
    "UNKNOWN_FAILURE",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tail_text(value: object, *, max_chars: int = 2000) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return "..." + text[-max_chars:]


def validate_cycle_failure_events_schema(path: Path | str = DEFAULT_LEDGER_PATH) -> tuple[bool, str]:
    ledger_path = Path(path)
    if not ledger_path.exists():
        return True, "missing_ok"
    try:
        with ledger_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
    except Exception as exc:
        return False, f"read_error={type(exc).__name__}:{exc}"
    duplicates = sorted({name for name in header if header.count(name) > 1})
    if duplicates:
        return False, f"duplicate_columns={','.join(duplicates)}"
    missing = [column for column in FAILURE_EVENT_COLUMNS if column not in header]
    if missing:
        return False, f"missing_columns={','.join(missing)}"
    return True, "ok"


def classify_failure_cause(
    *,
    verification_status: str = "",
    rc: object = "",
    failure_code: str = "",
    detail: str = "",
) -> str:
    verification_norm = _norm(verification_status).lower()
    code_norm = _norm(failure_code).upper()
    detail_norm = _norm(detail)
    combined = f"{verification_norm} {code_norm} {detail_norm}".lower()

    if "access denied" in combined and ("secret" in combined or ".env" in combined):
        return "CREDENTIAL_ACCESS_DENIED"
    if "phase1 pilot step timeout" in combined:
        if "reason=max_runtime" in combined:
            return "TIMEOUT_PROGRESSING"
        if "reason=stall" in combined or "reason=stalled" in combined:
            return "TIMEOUT_STALLED"
        return "TIMEOUT_STALLED"
    if verification_norm == "failed_stale_outputs":
        return "OUTPUT_STALE"
    if verification_norm == "failed_missing_outputs":
        return "OUTPUT_MISSING"
    if verification_norm == "interrupted" or "keyboardinterrupt" in combined:
        return "INTERRUPTED_SIGNAL"
    if verification_norm == "guardrail_blocked" or "guardrail" in combined:
        return "SHEET_GUARDRAIL"
    if code_norm in {"PUBLISH_SKIPPED", "FINALIZE_BLOCKED_NO_PUBLISH"}:
        return "PUBLISH_PROOF_MISSING"
    if code_norm == "REQUIRED_OUTPUTS_MISSING":
        return "REQUIRED_OUTPUTS_MISSING"
    if code_norm in {"FINALIZE_BLOCKED", "PRE_PUBLISH_EARLY_EXIT_NO_PUBLISH"}:
        return "FINALIZE_BLOCKED"
    if "owner_contract" in combined or "owner contract" in combined:
        return "OWNER_CONTRACT_VIOLATION"
    if "stale" in combined and "lock" in combined:
        return "LOCK_STALE"
    if "maintenance" in combined and ("timeout" in combined or "abort" in combined):
        return "MAINTENANCE_ABORT"
    if "external api" in combined or "spapi" in combined or "amazon api" in combined:
        return "EXTERNAL_API_ERROR"
    if code_norm in VALID_CAUSE_CODES and code_norm != "UNKNOWN_FAILURE":
        return code_norm
    if _safe_int(rc, 0) != 0 or verification_norm == "child_rc_nonzero":
        return "CHILD_RC_NONZERO"
    return "UNKNOWN_FAILURE"


def build_failure_event_from_manifest(
    manifest: dict,
    *,
    manifest_path: Path | str = "",
    health_path: Path | str = "",
    source_path: Path | str = "",
    recovery_action: str = "",
) -> dict[str, str]:
    failure_step = _first_failure_step(manifest)
    step_detail = _step_detail(failure_step) if failure_step else ""
    verification_status = _norm(failure_step.get("verification_status", "")) if failure_step else ""
    rc = _norm(failure_step.get("rc", "")) if failure_step else ""
    cause_code = classify_failure_cause(
        verification_status=verification_status,
        rc=rc,
        detail=step_detail,
    )
    return normalize_failure_event(
        {
            "timestamp_utc": utc_now_iso(),
            "cycle": _norm(manifest.get("cycle", "")),
            "run_id": _norm(manifest.get("run_id", "")),
            "final_state": _norm(manifest.get("final_state", "")),
            "cause_code": cause_code,
            "cause_detail": step_detail,
            "step_name": _norm(failure_step.get("name", "")) if failure_step else "",
            "stage": _norm(failure_step.get("script_or_function", "")) if failure_step else "",
            "rc": rc,
            "verification_status": verification_status,
            "manifest_path": str(manifest_path) if manifest_path else "",
            "health_path": str(health_path) if health_path else "",
            "source_path": str(source_path) if source_path else "",
            "recovery_action": recovery_action,
        }
    )


def normalize_failure_event(event: dict[str, object]) -> dict[str, str]:
    row = {column: "" for column in FAILURE_EVENT_COLUMNS}
    for column in FAILURE_EVENT_COLUMNS:
        if column in event:
            row[column] = _norm(event.get(column, ""))
    row["timestamp_utc"] = row["timestamp_utc"] or utc_now_iso()
    row["cycle"] = row["cycle"].upper()
    row["cause_code"] = _normalize_cause_code(row["cause_code"])
    row["cause_detail"] = tail_text(row["cause_detail"], max_chars=1000)
    row["event_id"] = row["event_id"] or _event_id(row)
    return row


def upsert_cycle_failure_event(
    event: dict[str, object],
    *,
    path: Path | str = DEFAULT_LEDGER_PATH,
) -> Path:
    ledger_path = Path(path)
    row = normalize_failure_event(event)
    ok, reason = validate_cycle_failure_events_schema(ledger_path)
    if not ok:
        raise ValueError(f"cycle_failure_events schema invalid: {reason}")

    rows: list[dict[str, str]] = []
    if ledger_path.exists():
        with ledger_path.open("r", encoding="utf-8", newline="") as handle:
            for existing in csv.DictReader(handle):
                existing_row = {column: _norm(existing.get(column, "")) for column in FAILURE_EVENT_COLUMNS}
                if existing_row.get("event_id") != row["event_id"]:
                    rows.append(existing_row)
    rows.append(row)
    rows.sort(key=lambda item: (item.get("timestamp_utc", ""), item.get("event_id", "")))
    _atomic_write_csv(ledger_path, rows)
    return ledger_path


def _atomic_write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FAILURE_EVENT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({column: _norm(row.get(column, "")) for column in FAILURE_EVENT_COLUMNS})
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(Exception):
            Path(tmp_name).unlink()


def _first_failure_step(manifest: dict) -> dict[str, object] | None:
    steps = manifest.get("steps", [])
    if not isinstance(steps, list):
        return None
    fallback: dict[str, object] | None = None
    for step in steps:
        if not isinstance(step, dict):
            continue
        status = _norm(step.get("step_status", "")).lower()
        verification = _norm(step.get("verification_status", "")).lower()
        rc = _safe_int(step.get("rc", 0), 0)
        if status in {"failed", "verification_failed", "interrupted"}:
            return step
        if verification in {"failed_stale_outputs", "failed_missing_outputs", "interrupted", "child_rc_nonzero"}:
            return step
        if rc != 0 and status not in {"skipped", "degraded"} and fallback is None:
            fallback = step
    return fallback


def _step_detail(step: dict[str, object]) -> str:
    parts = []
    for key in ("notes", "stdout_tail", "stderr_tail"):
        value = _norm(step.get(key, ""))
        if value:
            parts.append(f"{key}={value}")
    missing = step.get("missing_outputs", [])
    stale = step.get("stale_outputs", [])
    if isinstance(missing, list) and missing:
        parts.append(f"missing_outputs={','.join(_norm(item) for item in missing if _norm(item))}")
    if isinstance(stale, list) and stale:
        parts.append(f"stale_outputs={','.join(_norm(item) for item in stale if _norm(item))}")
    return tail_text(";".join(parts), max_chars=1000)


def _event_id(row: dict[str, str]) -> str:
    cycle = row.get("cycle", "") or "UNKNOWN"
    run_id = row.get("run_id", "") or row.get("timestamp_utc", "")
    source = row.get("source_path", "") or row.get("manifest_path", "") or "terminal"
    return f"{cycle}:{run_id}:{source}"


def _normalize_cause_code(value: str) -> str:
    code = _norm(value).upper()
    return code if code in VALID_CAUSE_CODES else "UNKNOWN_FAILURE"


def _norm(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default
