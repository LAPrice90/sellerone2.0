from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._schemas import get_f_output_contract
from scripts.one_off.F036_build_passed_product_page_evidence_backfill_queue import (
    BACKFILL_QUEUE_COLUMNS,
    F061_ACTIVE_RUN_COLUMNS,
)


DEFAULT_STATE_DIR = ROOT / "out" / "systems" / "F" / "page_evidence_backfill"
DEFAULT_QUEUE_PATH = ROOT / "out" / "analysis_reports" / "f_passed_product_page_evidence_backfill_queue_full_latest.csv"
DEFAULT_STATE_PATH = DEFAULT_STATE_DIR / "page_evidence_backfill_state.csv"
DEFAULT_RESULTS_PATH = DEFAULT_STATE_DIR / "page_evidence_backfill_results.csv"
DEFAULT_HEALTH_PATH = DEFAULT_STATE_DIR / "page_evidence_backfill_health.csv"
DEFAULT_MANIFEST_PATH = DEFAULT_STATE_DIR / "page_evidence_backfill_batch_manifest.csv"
DEFAULT_CURRENT_SCANNER_FAIL_EVIDENCE_PATH = DEFAULT_STATE_DIR / "current_scanner_fail_evidence.csv"
DEFAULT_PROOF_BASE = ROOT / "out" / "proof"


STATE_EXTRA_COLUMNS = [
    "backfill_status",
    "batch_id",
    "batch_started_utc",
    "batch_finished_utc",
    "proof_root",
    "scrape_attempted",
    "scrape_success",
    "page_evidence_captured_flag",
    "result_notes",
]
STATE_COLUMNS = [*BACKFILL_QUEUE_COLUMNS, *STATE_EXTRA_COLUMNS]

RESULT_COLUMNS = [
    "observed_utc",
    "batch_id",
    "backfill_id",
    "asin",
    "resolved_asin",
    "supplier_id",
    "supplier_sku",
    "barcode",
    "supplier_title",
    "amazon_title",
    "main_title",
    "backfill_status",
    "scrape_attempted",
    "scrape_success",
    "scrape_error",
    "page_evidence_captured_flag",
    "product_detail_text",
    "product_description",
    "product_feature_bullets",
    "proof_root",
    "evidence_source_path",
]

CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS = [
    "observed_utc",
    "batch_id",
    "backfill_id",
    "backfill_status",
    "supplier_id",
    "active_run_id",
    "review_batch_id",
    "candidate_id",
    "supplier_sku",
    "asin",
    "resolved_asin",
    "barcode",
    "supplier_title",
    "amazon_title",
    "scanner_fail_reason",
    "scrape_error",
    "scrape_attempted",
    "scrape_success",
    "page_evidence_captured_flag",
    "proof_root",
    "state_path",
    "evidence_source_path",
]

BATCH_MANIFEST_COLUMNS = [
    "observed_utc",
    "batch_id",
    "mode",
    "status",
    "batch_size",
    "staged_rows",
    "processed_rows",
    "succeeded_rows",
    "failed_rows",
    "captured_rows",
    "proof_root",
    "queue_path",
    "state_path",
    "results_path",
    "health_path",
    "notes",
]

HEALTH_COLUMNS = [
    "check",
    "status",
    "value",
    "notes",
    "observed_utc",
    "source_path",
]

PAGE_EVIDENCE_FIELDS = ["product_detail_text", "product_description", "product_feature_bullets"]
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_SKIPPED_CURRENT_SCANNER_FAIL = "skipped_current_scanner_fail"
STATUS_NEEDS_ASIN_RECHECK = "needs_asin_recheck"
TERMINAL_HANDLED_STATUSES = {STATUS_SUCCEEDED, STATUS_SKIPPED_CURRENT_SCANNER_FAIL, STATUS_NEEDS_ASIN_RECHECK}


@dataclass(frozen=True)
class BackfillBatchResult:
    status: str
    batch_id: str
    proof_root: str
    staged_rows: int
    processed_rows: int
    succeeded_rows: int
    failed_rows: int
    captured_rows: int
    state_path: str
    results_path: str
    health_path: str
    manifest_path: str
    notes: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _normalize_digits(value: object) -> str:
    return "".join(ch for ch in _normalize_text(value) if ch.isdigit())


def _truthy(value: object) -> bool:
    return _normalize_lower(value) in {"1", "true", "yes", "y"}


def _read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns or [])
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns or [])


def _write_csv(path: Path, df: pd.DataFrame, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns].fillna("")
    out.to_csv(path, index=False)


def _append_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> pd.DataFrame:
    existing = _read_csv(path, columns)
    incoming = pd.DataFrame(rows, columns=columns).fillna("") if rows else pd.DataFrame(columns=columns)
    out = pd.concat([existing, incoming], ignore_index=True).fillna("")
    _write_csv(path, out, columns)
    return out


def _upsert_current_scanner_fail_evidence(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    existing = _read_csv(path, CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS)
    incoming = pd.DataFrame(rows, columns=CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS).fillna("")
    out = pd.concat([existing, incoming], ignore_index=True).fillna("")
    if not out.empty:
        out["_dedupe_key"] = out.apply(
            lambda row: "|".join(
                [
                    _normalize_text(row.get("active_run_id", "")),
                    _normalize_text(row.get("candidate_id", "")),
                    _normalize_text(row.get("supplier_sku", "")).upper(),
                    _normalize_text(row.get("asin", "")).upper(),
                    _normalize_text(row.get("backfill_id", "")),
                ]
            ),
            axis=1,
        )
        out["_observed_ts"] = pd.to_datetime(out["observed_utc"], errors="coerce", utc=True, format="mixed")
        out = out.sort_values("_observed_ts", ascending=True, kind="stable")
        out = out.drop_duplicates("_dedupe_key", keep="last")
        out = out.drop(columns=["_dedupe_key", "_observed_ts"])
    _write_csv(path, out, CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS)


def _to_float(value: object, default: float = 0.0) -> float:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _parse_state_line(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except Exception:
        return {}
    parsed: dict[str, str] = {}
    for part in line.replace("|", "\n").splitlines():
        clean = _normalize_text(part)
        if "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        parsed[_normalize_lower(key)] = _normalize_text(value)
    return parsed


def _pid_alive(root: Path, pid: object) -> bool:
    try:
        pid_int = int(_normalize_text(pid))
    except ValueError:
        return False
    if pid_int <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid_int, 0)
            return True
        except OSError:
            return False
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-Process -Id {pid_int} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return False
    return _normalize_text(completed.stdout) != ""


def _live_f_active(root: Path) -> tuple[bool, str]:
    live_dir = root / "out" / "systems" / "F" / "price_list_manager" / "live"
    lock_state = _parse_state_line(live_dir / "live_cycle.lock")
    child_state = _parse_state_line(live_dir / "f061_child_status.txt")
    lock_pid = lock_state.get("pid", "")
    child_pid = child_state.get("pid", "")
    lock_alive = _pid_alive(root, lock_pid)
    child_alive = _pid_alive(root, child_pid)
    if child_alive:
        return True, f"f061_child_pid={child_pid}"
    if lock_alive:
        return True, f"fpm_manager_pid={lock_pid}"
    return False, "not_active"


def _write_maintenance_request(root: Path, *, observed_utc: str, batch_id: str) -> tuple[bool, Path]:
    path = root / "out" / "locks" / "maintenance.requested"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False, path
    path.write_text(
        "\n".join(
            [
                f"requested_utc={observed_utc}",
                f"reason=f037_page_evidence_backfill_batch_{batch_id}",
                "exit_after_drain=1",
                "action=reload",
                "owner=F037_run_passed_product_page_evidence_backfill_batch",
                "",
            ]
        ),
        encoding="ascii",
    )
    return True, path


def _wait_for_forced_idle(root: Path, *, timeout_seconds: int, poll_seconds: int = 10) -> tuple[bool, str]:
    live_dir = root / "out" / "systems" / "F" / "price_list_manager" / "live"
    deadline = time.time() + max(int(timeout_seconds), 1)
    last_reason = ""
    while time.time() < deadline:
        active, reason = _live_f_active(root)
        drain_ready = (live_dir / "F_restart_drain.ready").exists()
        last_reason = f"{reason};drain_ready={int(drain_ready)}"
        if not active and drain_ready:
            return True, last_reason
        time.sleep(max(int(poll_seconds), 1))
    return False, last_reason or "timeout"


def _clear_maintenance_request(root: Path, proof_root: Path, *, created_by_this_run: bool) -> None:
    if not created_by_this_run:
        return
    restore_dir = proof_root / "restore_artifacts"
    restore_dir.mkdir(parents=True, exist_ok=True)
    request_path = root / "out" / "locks" / "maintenance.requested"
    drain_path = root / "out" / "systems" / "F" / "price_list_manager" / "live" / "F_restart_drain.ready"
    if request_path.exists():
        (restore_dir / "maintenance.requested.cleared").write_text(
            request_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
        request_path.unlink()
    if drain_path.exists():
        (restore_dir / "F_restart_drain.ready.cleared").write_text(
            drain_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
        drain_path.unlink()


def _page_evidence_captured(row: dict[str, str]) -> str:
    return "1" if any(_normalize_text(row.get(field, "")) for field in PAGE_EVIDENCE_FIELDS) else "0"


def _is_current_scanner_fail(evidence: dict[str, str]) -> bool:
    """Return true when F061 intentionally rejected the row before page evidence."""
    if not evidence:
        return False
    joined = " ".join(
        _normalize_text(evidence.get(field, "")).upper()
        for field in [
            "pf",
            "first_check_status_code",
            "status_reason",
            "fail_code",
            "fail_codes",
            "scrape_error",
        ]
    )
    if "LOGIN" in joined or "CAPTCHA" in joined:
        return False
    return _normalize_text(evidence.get("pf", "")).upper() == "FAIL" and (
        _truthy(evidence.get("hard_stop", ""))
        or bool(_normalize_text(evidence.get("status_reason", "")))
        or bool(_normalize_text(evidence.get("fail_codes", "")))
    )


def _needs_asin_recheck(evidence: dict[str, str]) -> bool:
    if not evidence:
        return False
    joined = " ".join(
        _normalize_text(evidence.get(field, "")).upper()
        for field in [
            "pf",
            "first_check_status_code",
            "status_reason",
            "fail_code",
            "fail_codes",
            "scrape_error",
        ]
    )
    return "NOASIN" in joined


def _current_scanner_fail_note(evidence: dict[str, str]) -> str:
    pieces = [
        _normalize_text(evidence.get("first_check_status_code", "")),
        _normalize_text(evidence.get("status_reason", "")),
        _normalize_text(evidence.get("fail_code", "")),
        _normalize_text(evidence.get("fail_codes", "")),
        _normalize_text(evidence.get("scrape_error", "")),
    ]
    clean = [piece for piece in pieces if piece]
    return "current_scanner_fail:" + "|".join(clean) if clean else "current_scanner_fail"


def load_or_create_state(
    *,
    queue_path: Path,
    state_path: Path,
    results_path: Path,
    observed_utc: str,
) -> pd.DataFrame:
    queue_df = _read_csv(queue_path, BACKFILL_QUEUE_COLUMNS)
    missing = [column for column in BACKFILL_QUEUE_COLUMNS if column not in queue_df.columns]
    if missing:
        raise ValueError(f"queue missing required columns: {','.join(missing)}")

    existing_state = _read_csv(state_path, STATE_COLUMNS)
    existing_by_id = {
        _normalize_text(row.get("backfill_id", "")): row
        for row in existing_state.fillna("").to_dict("records")
        if _normalize_text(row.get("backfill_id", ""))
    }
    result_df = _read_csv(results_path, RESULT_COLUMNS)
    succeeded_asins = {
        _normalize_text(row.get("asin", "")).upper()
        for row in result_df.to_dict("records")
        if _normalize_text(row.get("asin", "")) and _normalize_text(row.get("page_evidence_captured_flag", "")) == "1"
    }
    terminal_status_by_id = {
        _normalize_text(row.get("backfill_id", "")): _normalize_text(row.get("backfill_status", ""))
        for row in result_df.to_dict("records")
        if _normalize_text(row.get("backfill_id", ""))
        and _normalize_text(row.get("backfill_status", "")) in TERMINAL_HANDLED_STATUSES
    }

    rows: list[dict[str, str]] = []
    for queue_row in queue_df.fillna("").to_dict("records"):
        backfill_id = _normalize_text(queue_row.get("backfill_id", ""))
        existing = existing_by_id.get(backfill_id, {})
        row = {column: _normalize_text(queue_row.get(column, "")) for column in BACKFILL_QUEUE_COLUMNS}
        for column in STATE_EXTRA_COLUMNS:
            row[column] = _normalize_text(existing.get(column, ""))
        asin = _normalize_text(row.get("asin", "")).upper()
        if row["backfill_status"] == "":
            terminal_status = terminal_status_by_id.get(backfill_id, "")
            if terminal_status:
                row["backfill_status"] = terminal_status
                row["result_notes"] = "already_present_in_backfill_results"
            elif asin in succeeded_asins:
                row["backfill_status"] = STATUS_SUCCEEDED
                row["page_evidence_captured_flag"] = "1"
                row["result_notes"] = "already_present_in_backfill_results"
            elif _normalize_text(row.get("f061_ready_flag", "")) != "1":
                row["backfill_status"] = "blocked_missing_barcode"
                row["result_notes"] = "not_f061_ready"
            else:
                row["backfill_status"] = "pending"
                row["result_notes"] = "ready_for_batch"
        row["observed_utc"] = row["observed_utc"] or observed_utc
        rows.append(row)

    state_df = pd.DataFrame(rows, columns=STATE_COLUMNS).fillna("")
    _write_csv(state_path, state_df, STATE_COLUMNS)
    return state_df


def _build_f061_active_rows(batch_rows: pd.DataFrame, batch_id: str, observed_utc: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for row in batch_rows.fillna("").to_dict("records"):
        supplier_id = _normalize_text(row.get("supplier_id", ""))
        run_id = f"{batch_id}_{supplier_id}" if supplier_id else batch_id
        rows.append(
            {
                "run_id": run_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_id,
                "row_key": _normalize_text(row.get("backfill_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_digits(row.get("barcode", "")),
                "supplier_title": _normalize_text(row.get("supplier_title", "")) or _normalize_text(row.get("amazon_title", "")),
                "unit_cost": _normalize_text(row.get("unit_cost", "")),
                "currency": _normalize_text(row.get("currency", "")) or "GBP",
                "vat_rate": _normalize_text(row.get("vat_rate", "")),
                "scan_status": "pending",
                "scan_reason": "passed_product_page_evidence_backfill",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": observed_utc,
                "completion_block_reason": "",
                "backtrack_original_observed_utc": "",
                "backtrack_attempt_count": "",
            }
        )
    return pd.DataFrame(rows, columns=F061_ACTIVE_RUN_COLUMNS).fillna("")


def _select_pending_rows(state_df: pd.DataFrame, batch_size: int) -> pd.DataFrame:
    if state_df.empty:
        return pd.DataFrame(columns=STATE_COLUMNS)
    work = state_df[state_df["backfill_status"].map(_normalize_text).eq("pending")].copy()
    if work.empty:
        return pd.DataFrame(columns=STATE_COLUMNS)
    work["_priority_float"] = work["backfill_priority"].map(_to_float)
    work = work.sort_values(["_priority_float", "asin"], ascending=[False, True], kind="stable")
    return work.head(max(int(batch_size), 1)).drop(columns=["_priority_float"]).reset_index(drop=True)


def stage_next_batch(
    *,
    root: Path,
    queue_path: Path,
    state_path: Path,
    results_path: Path,
    manifest_path: Path,
    proof_base: Path,
    batch_size: int,
    batch_id: str,
    observed_utc: str,
) -> tuple[pd.DataFrame, Path, pd.DataFrame]:
    state_df = load_or_create_state(
        queue_path=queue_path,
        state_path=state_path,
        results_path=results_path,
        observed_utc=observed_utc,
    )
    existing_batch_rows = state_df[
        state_df["batch_id"].map(_normalize_text).eq(batch_id)
        & state_df["backfill_status"].map(_normalize_text).eq("staged")
    ].copy()
    existing_proof_root = proof_base / batch_id
    existing_active_run = existing_proof_root / get_f_output_contract("supplier_price_list_active_run").rel_path
    if not existing_batch_rows.empty and existing_active_run.exists():
        manifest_row = {
            "observed_utc": observed_utc,
            "batch_id": batch_id,
            "mode": "prepare",
            "status": "staged_existing",
            "batch_size": str(batch_size),
            "staged_rows": str(len(existing_batch_rows.index)),
            "processed_rows": "0",
            "succeeded_rows": "0",
            "failed_rows": "0",
            "captured_rows": "0",
            "proof_root": str(existing_proof_root),
            "queue_path": str(queue_path),
            "state_path": str(state_path),
            "results_path": str(results_path),
            "health_path": "",
            "notes": "reusing previously staged batch",
        }
        _append_csv(manifest_path, [manifest_row], BATCH_MANIFEST_COLUMNS)
        return state_df, existing_proof_root, existing_batch_rows.reset_index(drop=True)
    batch_rows = _select_pending_rows(state_df, batch_size)
    proof_root = proof_base / batch_id
    if batch_rows.empty:
        manifest_row = {
            "observed_utc": observed_utc,
            "batch_id": batch_id,
            "mode": "prepare",
            "status": "no_pending_rows",
            "batch_size": str(batch_size),
            "staged_rows": "0",
            "processed_rows": "0",
            "succeeded_rows": "0",
            "failed_rows": "0",
            "captured_rows": "0",
            "proof_root": str(proof_root),
            "queue_path": str(queue_path),
            "state_path": str(state_path),
            "results_path": str(results_path),
            "health_path": "",
            "notes": "no pending rows available",
        }
        _append_csv(manifest_path, [manifest_row], BATCH_MANIFEST_COLUMNS)
        return state_df, proof_root, batch_rows

    proof_root.mkdir(parents=True, exist_ok=True)
    active_run_df = _build_f061_active_rows(batch_rows, batch_id, observed_utc)
    inbox_path = proof_root / get_f_output_contract("supplier_price_list_active_run").rel_path
    supplier_id = _normalize_text(batch_rows.iloc[0].get("supplier_id", "")) or "mixed_supplier"
    supplier_active_path = proof_root / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id / "active_run.csv"
    queue_slice_path = proof_root / "page_evidence_backfill_batch_queue.csv"
    _write_csv(inbox_path, active_run_df, F061_ACTIVE_RUN_COLUMNS)
    _write_csv(supplier_active_path, active_run_df, F061_ACTIVE_RUN_COLUMNS)
    _write_csv(queue_slice_path, batch_rows, STATE_COLUMNS)

    selected_ids = set(batch_rows["backfill_id"].map(_normalize_text).tolist())
    state_df = state_df.copy()
    mask = state_df["backfill_id"].map(_normalize_text).isin(selected_ids)
    state_df.loc[mask, "backfill_status"] = "staged"
    state_df.loc[mask, "batch_id"] = batch_id
    state_df.loc[mask, "batch_started_utc"] = observed_utc
    state_df.loc[mask, "proof_root"] = str(proof_root)
    state_df.loc[mask, "result_notes"] = "staged_for_f061"
    _write_csv(state_path, state_df, STATE_COLUMNS)

    manifest_row = {
        "observed_utc": observed_utc,
        "batch_id": batch_id,
        "mode": "prepare",
        "status": "staged",
        "batch_size": str(batch_size),
        "staged_rows": str(len(batch_rows.index)),
        "processed_rows": "0",
        "succeeded_rows": "0",
        "failed_rows": "0",
        "captured_rows": "0",
        "proof_root": str(proof_root),
        "queue_path": str(queue_path),
        "state_path": str(state_path),
        "results_path": str(results_path),
        "health_path": "",
        "notes": f"active_run={inbox_path}",
    }
    _append_csv(manifest_path, [manifest_row], BATCH_MANIFEST_COLUMNS)
    return state_df, proof_root, batch_rows


def _run_f061(
    *,
    root: Path,
    proof_root: Path,
    supplier_id: str,
    max_rows: int,
    observed_utc: str,
    timeout_seconds: int,
) -> int:
    stdout_path = proof_root / "f061_stdout.log"
    stderr_path = proof_root / "f061_stderr.log"
    env = os.environ.copy()
    env["F061_MODE"] = "data_collection"
    env["SELLERONE_STORAGE_MODE"] = "csv"
    env["F061_BACKGROUND_BROWSER_MODE"] = "minimized"
    env["F061_KILL_SPECIALIST_CHROME_BEFORE_START"] = "0"
    env.setdefault("F061_CATALOG_MIN_INTERVAL_SECONDS", "0.5")
    env.setdefault("F061_HAZMAT_MIN_INTERVAL_SECONDS", "1.0")
    env.setdefault("F061_FEES_MIN_INTERVAL_SECONDS", "1.0")
    command = [
        sys.executable,
        str(root / "scripts" / "flows" / "F" / "F061_run_legacy_first_checks_local.py"),
        "--root",
        str(proof_root),
        "--supplier-id",
        supplier_id,
        "--max-rows",
        str(max_rows),
        "--scan-utc",
        observed_utc,
        "--scrape-mode",
        "legacy_module",
        "--price-source",
        "legacy",
        "--pricing-min-interval-seconds",
        "1",
        "--catalog-max-candidates",
        "3",
    ]
    completed = subprocess.run(
        command,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=max(int(timeout_seconds), 60),
        check=False,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(completed.stderr, encoding="utf-8", errors="replace")
    return int(completed.returncode)


def apply_batch_outputs(
    *,
    proof_root: Path,
    batch_rows: pd.DataFrame,
    state_path: Path,
    results_path: Path,
    observed_utc: str,
    batch_id: str,
    current_scanner_fail_evidence_path: Path | None = None,
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    state_df = _read_csv(state_path, STATE_COLUMNS)
    evidence_path = proof_root / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
    evidence_df = _read_csv(evidence_path)
    evidence_by_asin = {
        _normalize_text(row.get("asin", "")).upper(): row
        for row in evidence_df.fillna("").to_dict("records")
        if _normalize_text(row.get("asin", ""))
    }
    evidence_by_backfill_id = {
        _normalize_text(row.get("candidate_id", "")): row
        for row in evidence_df.fillna("").to_dict("records")
        if _normalize_text(row.get("candidate_id", ""))
    }
    screening_path = proof_root / get_f_output_contract("f_screening_row_state_live").rel_path
    screening_df = _read_csv(screening_path)
    screening_by_backfill_id = {
        _normalize_text(row.get("candidate_id", "")): row
        for row in screening_df.fillna("").to_dict("records")
        if _normalize_text(row.get("candidate_id", ""))
    }

    result_rows: list[dict[str, str]] = []
    current_scanner_fail_rows: list[dict[str, str]] = []
    for batch_row in batch_rows.fillna("").to_dict("records"):
        backfill_id = _normalize_text(batch_row.get("backfill_id", ""))
        asin = _normalize_text(batch_row.get("asin", "")).upper()
        evidence = evidence_by_backfill_id.get(backfill_id, {}) or evidence_by_asin.get(asin, {})
        screening = screening_by_backfill_id.get(backfill_id, {})
        resolved_asin = _normalize_text(evidence.get("asin", "")).upper()
        captured = _page_evidence_captured(evidence)
        scrape_attempted = _normalize_text(evidence.get("scrape_attempted", ""))
        scrape_success = _normalize_text(evidence.get("scrape_success", ""))
        if not evidence:
            if _needs_asin_recheck(screening):
                status = STATUS_NEEDS_ASIN_RECHECK
                notes = _current_scanner_fail_note(screening)
            elif _is_current_scanner_fail(screening):
                status = STATUS_SKIPPED_CURRENT_SCANNER_FAIL
                notes = _current_scanner_fail_note(screening)
            else:
                status = STATUS_FAILED
                notes = "no_matching_scrape_evidence"
        elif _truthy(scrape_success) and captured == "1":
            status = STATUS_SUCCEEDED
            notes = "captured_page_evidence"
        elif _needs_asin_recheck(evidence):
            status = STATUS_NEEDS_ASIN_RECHECK
            notes = _current_scanner_fail_note(evidence)
        elif _is_current_scanner_fail(evidence):
            status = STATUS_SKIPPED_CURRENT_SCANNER_FAIL
            notes = _current_scanner_fail_note(evidence)
        elif _truthy(scrape_success):
            status = STATUS_FAILED
            notes = "scrape_succeeded_no_page_text"
        else:
            status = STATUS_FAILED
            notes = _normalize_text(evidence.get("scrape_error", "")) or "scrape_not_successful"
        if resolved_asin and resolved_asin != asin:
            notes = f"{notes};resolved_asin_changed:{asin}->{resolved_asin}"

        state_mask = state_df["backfill_id"].map(_normalize_text).eq(backfill_id)
        state_df.loc[state_mask, "backfill_status"] = status
        state_df.loc[state_mask, "batch_finished_utc"] = observed_utc
        state_df.loc[state_mask, "scrape_attempted"] = scrape_attempted
        state_df.loc[state_mask, "scrape_success"] = scrape_success
        state_df.loc[state_mask, "page_evidence_captured_flag"] = captured
        state_df.loc[state_mask, "result_notes"] = notes

        result_rows.append(
            {
                "observed_utc": observed_utc,
                "batch_id": batch_id,
                "backfill_id": backfill_id,
                "asin": asin,
                "resolved_asin": resolved_asin or asin,
                "supplier_id": _normalize_text(batch_row.get("supplier_id", "")),
                "supplier_sku": _normalize_text(batch_row.get("supplier_sku", "")),
                "barcode": _normalize_digits(batch_row.get("barcode", "")),
                "supplier_title": _normalize_text(evidence.get("supplier_title", "")) or _normalize_text(batch_row.get("supplier_title", "")),
                "amazon_title": _normalize_text(evidence.get("main_title", "")) or _normalize_text(batch_row.get("amazon_title", "")),
                "main_title": _normalize_text(evidence.get("main_title", "")),
                "backfill_status": status,
                "scrape_attempted": scrape_attempted,
                "scrape_success": scrape_success,
                "scrape_error": _normalize_text(evidence.get("scrape_error", "")),
                "page_evidence_captured_flag": captured,
                "product_detail_text": _normalize_text(evidence.get("product_detail_text", "")),
                "product_description": _normalize_text(evidence.get("product_description", "")),
                "product_feature_bullets": _normalize_text(evidence.get("product_feature_bullets", "")),
                "proof_root": str(proof_root),
                "evidence_source_path": str(evidence_path),
            }
        )
        if status in {STATUS_SKIPPED_CURRENT_SCANNER_FAIL, STATUS_NEEDS_ASIN_RECHECK}:
            current_scanner_fail_rows.append(
                {
                    "observed_utc": observed_utc,
                    "batch_id": batch_id,
                    "backfill_id": backfill_id,
                    "backfill_status": status,
                    "supplier_id": _normalize_text(batch_row.get("supplier_id", "")),
                    "active_run_id": _normalize_text(batch_row.get("active_run_id", "")),
                    "review_batch_id": _normalize_text(batch_row.get("review_batch_id", "")),
                    "candidate_id": _normalize_text(batch_row.get("candidate_id", "")),
                    "supplier_sku": _normalize_text(batch_row.get("supplier_sku", "")),
                    "asin": asin,
                    "resolved_asin": resolved_asin or asin,
                    "barcode": _normalize_digits(batch_row.get("barcode", "")),
                    "supplier_title": _normalize_text(evidence.get("supplier_title", ""))
                    or _normalize_text(batch_row.get("supplier_title", "")),
                    "amazon_title": _normalize_text(evidence.get("main_title", ""))
                    or _normalize_text(batch_row.get("amazon_title", "")),
                    "scanner_fail_reason": notes,
                    "scrape_error": _normalize_text(evidence.get("scrape_error", "")) or notes,
                    "scrape_attempted": scrape_attempted,
                    "scrape_success": scrape_success,
                    "page_evidence_captured_flag": captured,
                    "proof_root": str(proof_root),
                    "state_path": str(state_path),
                    "evidence_source_path": str(evidence_path),
                }
            )

    _write_csv(state_path, state_df, STATE_COLUMNS)
    _append_csv(results_path, result_rows, RESULT_COLUMNS)
    audit_path = current_scanner_fail_evidence_path or (state_path.parent / DEFAULT_CURRENT_SCANNER_FAIL_EVIDENCE_PATH.name)
    _upsert_current_scanner_fail_evidence(audit_path, current_scanner_fail_rows)
    return state_df, result_rows


def _health_row(
    *,
    check: str,
    status: str,
    value: object,
    notes: str,
    observed_utc: str,
    source_path: Path,
) -> dict[str, str]:
    return {
        "check": check,
        "status": status,
        "value": str(value),
        "notes": notes,
        "observed_utc": observed_utc,
        "source_path": str(source_path),
    }


def write_health(*, state_df: pd.DataFrame, health_path: Path, manifest_path: Path, observed_utc: str) -> pd.DataFrame:
    status_counts = state_df["backfill_status"].map(_normalize_text).value_counts().to_dict() if not state_df.empty else {}
    current_scanner_fail_evidence_path = health_path.parent / DEFAULT_CURRENT_SCANNER_FAIL_EVIDENCE_PATH.name
    current_scanner_fail_evidence_df = _read_csv(
        current_scanner_fail_evidence_path,
        CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS,
    )
    current_scanner_fail_evidence_missing_columns = [
        column for column in CURRENT_SCANNER_FAIL_EVIDENCE_COLUMNS if column not in current_scanner_fail_evidence_df.columns
    ]
    rows = [
        _health_row(
            check="page_evidence_backfill_state_schema",
            status="ok" if all(column in state_df.columns for column in STATE_COLUMNS) else "fail",
            value="present",
            notes="durable row status schema",
            observed_utc=observed_utc,
            source_path=health_path,
        ),
        _health_row(
            check="page_evidence_backfill_total_rows",
            status="ok",
            value=len(state_df.index),
            notes=json.dumps(status_counts, sort_keys=True),
            observed_utc=observed_utc,
            source_path=health_path,
        ),
        _health_row(
            check="page_evidence_backfill_pending_rows",
            status="ok",
            value=status_counts.get("pending", 0),
            notes="rows still waiting for a controlled F061 batch",
            observed_utc=observed_utc,
            source_path=health_path,
        ),
        _health_row(
            check="page_evidence_backfill_succeeded_rows",
            status="ok",
            value=status_counts.get(STATUS_SUCCEEDED, 0),
            notes="rows completed by backfill batches",
            observed_utc=observed_utc,
            source_path=health_path,
        ),
        _health_row(
            check="current_scanner_fail_evidence_schema",
            status="fail" if current_scanner_fail_evidence_missing_columns else "ok",
            value="present" if current_scanner_fail_evidence_path.exists() else "not_present",
            notes="missing_columns="
            + ("|".join(current_scanner_fail_evidence_missing_columns) if current_scanner_fail_evidence_missing_columns else "0"),
            observed_utc=observed_utc,
            source_path=current_scanner_fail_evidence_path,
        ),
        _health_row(
            check="current_scanner_fail_evidence_rows",
            status="ok",
            value=len(current_scanner_fail_evidence_df.index),
            notes="audit rows available for FPM155 current scanner fail guard",
            observed_utc=observed_utc,
            source_path=current_scanner_fail_evidence_path,
        ),
        _health_row(
            check="page_evidence_backfill_skipped_current_scanner_fail_rows",
            status="ok",
            value=status_counts.get(STATUS_SKIPPED_CURRENT_SCANNER_FAIL, 0),
            notes="historical passes now rejected by the current scanner before page evidence",
            observed_utc=observed_utc,
            source_path=health_path,
        ),
        _health_row(
            check="page_evidence_backfill_needs_asin_recheck_rows",
            status="warn" if status_counts.get(STATUS_NEEDS_ASIN_RECHECK, 0) else "ok",
            value=status_counts.get(STATUS_NEEDS_ASIN_RECHECK, 0),
            notes="old pass rows where current barcode lookup did not resolve an ASIN",
            observed_utc=observed_utc,
            source_path=health_path,
        ),
        _health_row(
            check="page_evidence_backfill_failed_rows",
            status="warn" if status_counts.get(STATUS_FAILED, 0) else "ok",
            value=status_counts.get(STATUS_FAILED, 0),
            notes="failed rows stay in state for retry or diagnosis",
            observed_utc=observed_utc,
            source_path=health_path,
        ),
        _health_row(
            check="page_evidence_backfill_manifest_exists",
            status="ok" if manifest_path.exists() else "warn",
            value=int(manifest_path.exists()),
            notes="batch manifest records each prepare or execute attempt",
            observed_utc=observed_utc,
            source_path=manifest_path,
        ),
    ]
    health_df = pd.DataFrame(rows, columns=HEALTH_COLUMNS)
    _write_csv(health_path, health_df, HEALTH_COLUMNS)
    return health_df


def run_backfill_batch(
    *,
    root: Path | None = None,
    queue_path: Path | None = None,
    state_path: Path | None = None,
    results_path: Path | None = None,
    health_path: Path | None = None,
    manifest_path: Path | None = None,
    proof_base: Path | None = None,
    batch_size: int = 5,
    batch_id: str | None = None,
    observed_utc: str | None = None,
    execute: bool = False,
    force_maintenance: bool = False,
    force_timeout_seconds: int = 1800,
    f061_timeout_seconds: int = 7200,
) -> BackfillBatchResult:
    root_path = Path(root) if root is not None else ROOT
    observed = observed_utc or _utc_now_iso()
    batch = batch_id or f"f037_page_evidence_backfill_{observed.replace('-', '').replace(':', '').replace('Z', 'Z')}"
    queue = Path(queue_path) if queue_path is not None else DEFAULT_QUEUE_PATH
    state = Path(state_path) if state_path is not None else DEFAULT_STATE_PATH
    results = Path(results_path) if results_path is not None else DEFAULT_RESULTS_PATH
    health = Path(health_path) if health_path is not None else DEFAULT_HEALTH_PATH
    manifest = Path(manifest_path) if manifest_path is not None else DEFAULT_MANIFEST_PATH
    proof_root_base = Path(proof_base) if proof_base is not None else DEFAULT_PROOF_BASE

    state_df, proof_root, batch_rows = stage_next_batch(
        root=root_path,
        queue_path=queue,
        state_path=state,
        results_path=results,
        manifest_path=manifest,
        proof_base=proof_root_base,
        batch_size=batch_size,
        batch_id=batch,
        observed_utc=observed,
    )
    if batch_rows.empty:
        health_df = write_health(state_df=state_df, health_path=health, manifest_path=manifest, observed_utc=observed)
        return BackfillBatchResult(
            status="no_pending_rows",
            batch_id=batch,
            proof_root=str(proof_root),
            staged_rows=0,
            processed_rows=0,
            succeeded_rows=int((state_df["backfill_status"] == STATUS_SUCCEEDED).sum()) if not state_df.empty else 0,
            failed_rows=int((state_df["backfill_status"] == STATUS_FAILED).sum()) if not state_df.empty else 0,
            captured_rows=int((state_df["page_evidence_captured_flag"] == "1").sum()) if not state_df.empty else 0,
            state_path=str(state),
            results_path=str(results),
            health_path=str(health),
            manifest_path=str(manifest),
            notes=f"health_rows={len(health_df.index)}",
        )

    created_maintenance = False
    if execute:
        live_active, live_reason = _live_f_active(root_path)
        if live_active and not force_maintenance:
            state_df.loc[state_df["backfill_id"].isin(batch_rows["backfill_id"]), "backfill_status"] = "pending"
            state_df.loc[state_df["backfill_id"].isin(batch_rows["backfill_id"]), "result_notes"] = "execute_blocked_live_f_active"
            _write_csv(state, state_df, STATE_COLUMNS)
            health_df = write_health(state_df=state_df, health_path=health, manifest_path=manifest, observed_utc=observed)
            _append_csv(
                manifest,
                [
                    {
                        "observed_utc": observed,
                        "batch_id": batch,
                        "mode": "execute",
                        "status": "blocked_live_f_active",
                        "batch_size": str(batch_size),
                        "staged_rows": str(len(batch_rows.index)),
                        "processed_rows": "0",
                        "succeeded_rows": "0",
                        "failed_rows": "0",
                        "captured_rows": "0",
                        "proof_root": str(proof_root),
                        "queue_path": str(queue),
                        "state_path": str(state),
                        "results_path": str(results),
                        "health_path": str(health),
                        "notes": live_reason,
                    }
                ],
                BATCH_MANIFEST_COLUMNS,
            )
            return BackfillBatchResult(
                status="blocked_live_f_active",
                batch_id=batch,
                proof_root=str(proof_root),
                staged_rows=len(batch_rows.index),
                processed_rows=0,
                succeeded_rows=0,
                failed_rows=0,
                captured_rows=0,
                state_path=str(state),
                results_path=str(results),
                health_path=str(health),
                manifest_path=str(manifest),
                notes=f"{live_reason};health_rows={len(health_df.index)}",
            )
        if live_active and force_maintenance:
            created_maintenance, _ = _write_maintenance_request(root_path, observed_utc=observed, batch_id=batch)
            idle, idle_reason = _wait_for_forced_idle(root_path, timeout_seconds=force_timeout_seconds)
            if not idle:
                state_df.loc[state_df["backfill_id"].isin(batch_rows["backfill_id"]), "backfill_status"] = "pending"
                state_df.loc[state_df["backfill_id"].isin(batch_rows["backfill_id"]), "result_notes"] = "force_maintenance_timeout"
                _write_csv(state, state_df, STATE_COLUMNS)
                write_health(state_df=state_df, health_path=health, manifest_path=manifest, observed_utc=observed)
                return BackfillBatchResult(
                    status="force_maintenance_timeout",
                    batch_id=batch,
                    proof_root=str(proof_root),
                    staged_rows=len(batch_rows.index),
                    processed_rows=0,
                    succeeded_rows=0,
                    failed_rows=0,
                    captured_rows=0,
                    state_path=str(state),
                    results_path=str(results),
                    health_path=str(health),
                    manifest_path=str(manifest),
                    notes=idle_reason,
                )

        supplier_id = _normalize_text(batch_rows.iloc[0].get("supplier_id", "")) or "stocklist_supplier"
        rc = _run_f061(
            root=root_path,
            proof_root=proof_root,
            supplier_id=supplier_id,
            max_rows=len(batch_rows.index),
            observed_utc=observed,
            timeout_seconds=f061_timeout_seconds,
        )
        state_df, result_rows = apply_batch_outputs(
            proof_root=proof_root,
            batch_rows=batch_rows,
            state_path=state,
            results_path=results,
            observed_utc=observed,
            batch_id=batch,
        )
        if force_maintenance:
            _clear_maintenance_request(root_path, proof_root, created_by_this_run=created_maintenance)
        succeeded = sum(1 for row in result_rows if row.get("backfill_status") == STATUS_SUCCEEDED)
        skipped_current_scanner_fail = sum(
            1 for row in result_rows if row.get("backfill_status") == STATUS_SKIPPED_CURRENT_SCANNER_FAIL
        )
        needs_asin_recheck = sum(1 for row in result_rows if row.get("backfill_status") == STATUS_NEEDS_ASIN_RECHECK)
        failed = sum(1 for row in result_rows if row.get("backfill_status") == STATUS_FAILED)
        captured = sum(1 for row in result_rows if row.get("page_evidence_captured_flag") == "1")
        status = "executed" if rc == 0 else f"f061_exit_{rc}"
        notes = f"f061_rc={rc};skipped_current_scanner_fail={skipped_current_scanner_fail};needs_asin_recheck={needs_asin_recheck}"
        _append_csv(
            manifest,
            [
                {
                    "observed_utc": observed,
                    "batch_id": batch,
                    "mode": "execute",
                    "status": status,
                    "batch_size": str(batch_size),
                    "staged_rows": str(len(batch_rows.index)),
                    "processed_rows": str(len(result_rows)),
                    "succeeded_rows": str(succeeded),
                    "failed_rows": str(failed),
                    "captured_rows": str(captured),
                    "proof_root": str(proof_root),
                    "queue_path": str(queue),
                    "state_path": str(state),
                    "results_path": str(results),
                    "health_path": str(health),
                    "notes": notes,
                }
            ],
            BATCH_MANIFEST_COLUMNS,
        )
        write_health(state_df=state_df, health_path=health, manifest_path=manifest, observed_utc=observed)
        return BackfillBatchResult(
            status=status,
            batch_id=batch,
            proof_root=str(proof_root),
            staged_rows=len(batch_rows.index),
            processed_rows=len(result_rows),
            succeeded_rows=succeeded,
            failed_rows=failed,
            captured_rows=captured,
            state_path=str(state),
            results_path=str(results),
            health_path=str(health),
            manifest_path=str(manifest),
            notes=notes,
        )

    health_df = write_health(state_df=state_df, health_path=health, manifest_path=manifest, observed_utc=observed)
    return BackfillBatchResult(
        status="prepared",
        batch_id=batch,
        proof_root=str(proof_root),
        staged_rows=len(batch_rows.index),
        processed_rows=0,
        succeeded_rows=int((state_df["backfill_status"] == STATUS_SUCCEEDED).sum()) if not state_df.empty else 0,
        failed_rows=int((state_df["backfill_status"] == STATUS_FAILED).sum()) if not state_df.empty else 0,
        captured_rows=int((state_df["page_evidence_captured_flag"] == "1").sum()) if not state_df.empty else 0,
        state_path=str(state),
        results_path=str(results),
        health_path=str(health),
        manifest_path=str(manifest),
        notes=f"health_rows={len(health_df.index)}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or stage controlled batches for passed-product page-evidence backfill.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--queue-path", default=None)
    parser.add_argument("--state-path", default=None)
    parser.add_argument("--results-path", default=None)
    parser.add_argument("--health-path", default=None)
    parser.add_argument("--manifest-path", default=None)
    parser.add_argument("--proof-base", default=None)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force-maintenance", action="store_true")
    parser.add_argument("--force-timeout-seconds", type=int, default=1800)
    parser.add_argument("--f061-timeout-seconds", type=int, default=7200)
    args = parser.parse_args()

    result = run_backfill_batch(
        root=Path(args.root) if args.root else None,
        queue_path=Path(args.queue_path) if args.queue_path else None,
        state_path=Path(args.state_path) if args.state_path else None,
        results_path=Path(args.results_path) if args.results_path else None,
        health_path=Path(args.health_path) if args.health_path else None,
        manifest_path=Path(args.manifest_path) if args.manifest_path else None,
        proof_base=Path(args.proof_base) if args.proof_base else None,
        batch_size=args.batch_size,
        batch_id=args.batch_id,
        observed_utc=args.observed_utc,
        execute=bool(args.execute),
        force_maintenance=bool(args.force_maintenance),
        force_timeout_seconds=args.force_timeout_seconds,
        f061_timeout_seconds=args.f061_timeout_seconds,
    )
    payload = {
        "status": result.status,
        "batch_id": result.batch_id,
        "proof_root": result.proof_root,
        "staged_rows": result.staged_rows,
        "processed_rows": result.processed_rows,
        "succeeded_rows": result.succeeded_rows,
        "failed_rows": result.failed_rows,
        "captured_rows": result.captured_rows,
        "state_path": result.state_path,
        "results_path": result.results_path,
        "health_path": result.health_path,
        "manifest_path": result.manifest_path,
        "notes": result.notes,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if result.status.startswith("f061_exit_") or result.status in {"force_maintenance_timeout"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
