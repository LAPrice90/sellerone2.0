from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df
from scripts.flows.F.price_list_manager._io import normalize_text
from scripts.flows.F.price_list_manager._paths import get_manager_paths


PRODUCTION_LINE_STAGES = [
    "intake_enrichment",
    "catalog_identity",
    "pricing_api",
    "fee_hazmat_api",
    "browser_webscrape",
]

PIPELINE_ROW_COLUMNS = [
    "supplier_id",
    "supplier_name",
    "run_id",
    "candidate_id",
    "supplier_sku",
    "barcode",
    "asin",
    "unit_cost",
    "source_file_path",
    "source_seen_at_utc",
    "pipeline_stage",
    "stage_decision",
    "stage_reason",
    "earliest_block_stage",
    "earliest_block_reason",
    "scan_status",
    "scan_reason",
    "pf",
    "status_reason",
    "fail_code",
    "last_stage",
    "browser_attempted_flag",
    "browser_blocked_flag",
    "api_429_count",
    "updated_at_utc",
]

PIPELINE_STAGE_MANIFEST_COLUMNS = [
    "stage_id",
    "stage_status",
    "supplier_id",
    "run_id",
    "input_rows",
    "passed_rows",
    "blocked_rows",
    "retry_rows",
    "source_hash",
    "previous_manifest_path",
    "rows_path",
    "next_stage_input_path",
    "status_path",
    "observed_utc",
    "completed_at_utc",
    "notes",
]

PIPELINE_STAGE_STATUS_COLUMNS = [
    "stage_id",
    "status",
    "supplier_id",
    "run_id",
    "input_rows",
    "passed_rows",
    "blocked_rows",
    "retry_rows",
    "observed_utc",
    "notes",
    "manifest_path",
    "rows_path",
]

PIPELINE_RUN_STATUS_COLUMNS = [
    "observed_utc",
    "supplier_id",
    "run_id",
    "status",
    "stage_count",
    "input_rows",
    "final_pass_rows",
    "final_blocked_rows",
    "final_retry_rows",
    "pipeline_run_dir",
    "notes",
]

PIPELINE_ROUTING_MANIFEST_COLUMNS = [
    "routing_status",
    "supplier_id",
    "run_id",
    "source_stage_id",
    "source_manifest_path",
    "browser_input_path",
    "browser_input_rows",
    "source_hash",
    "observed_utc",
    "completed_at_utc",
    "notes",
]

PRODUCTION_LINE_SPEED_LEDGER_COLUMNS = [
    "observed_utc",
    "supplier_id",
    "run_id",
    "cycle_run_id",
    "api_rows_checked",
    "api_stopped_rows",
    "retry_rows",
    "browser_ready_rows",
    "browser_rows_attempted",
    "login_rows",
    "api_429_count",
    "endpoint_calls",
    "elapsed_seconds",
    "notes",
]


class PipelineStageNotReady(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_part(value: object) -> str:
    text = normalize_text(value).lower()
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    return safe.strip("_") or "unknown"


def pipeline_run_dir(root: Path, *, supplier_id: str, run_id: str) -> Path:
    paths = get_manager_paths(root=root)
    return paths.system_dir / "pipeline_runs" / _safe_part(supplier_id) / _safe_part(run_id)


def _finalize(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns]
    for column in columns:
        out[column] = out[column].map(normalize_text)
    return out


def _atomic_write_csv(path: Path, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    finalized = _finalize(df, columns)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    finalized.to_csv(tmp_path, index=False)
    tmp_path.replace(path)
    return finalized


def _hash_frame(df: pd.DataFrame) -> str:
    if df.empty:
        return "empty"
    stable = df.fillna("").astype(str)
    payload = stable.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _rows_from_contract(df: pd.DataFrame, *, supplier_id: str, run_id: str, run_meta: dict[str, str]) -> list[dict[str, str]]:
    if df.empty:
        return []
    work = df.copy().fillna("")
    scoped = False
    if "supplier_id" in work.columns:
        work = work[work["supplier_id"].map(lambda value: normalize_text(value).lower()) == supplier_id.lower()]
        scoped = True
    if "run_id" in work.columns:
        work = work[work["run_id"].map(normalize_text) == run_id]
        scoped = True
    supplier_name = normalize_text(run_meta.get("supplier_name", "")).lower()
    if "supplier" in work.columns and supplier_name:
        work = work[work["supplier"].map(lambda value: normalize_text(value).lower()) == supplier_name]
        scoped = True
    if not scoped:
        return []
    rows: list[dict[str, str]] = []
    for _, raw in work.iterrows():
        row = {column: normalize_text(raw.get(column, "")) for column in work.columns}
        candidate_id = normalize_text(row.get("candidate_id", "")) or normalize_text(row.get("row_key", ""))
        if not candidate_id:
            candidate_id = "|".join(
                part
                for part in [
                    normalize_text(row.get("supplier_sku", "")),
                    normalize_text(row.get("barcode", "")),
                    normalize_text(row.get("asin", "")),
                ]
                if part
            )
        if not candidate_id:
            continue
        rows.append(
            {
                "supplier_id": normalize_text(row.get("supplier_id", "")) or supplier_id,
                "supplier_name": normalize_text(row.get("supplier_name", "")) or normalize_text(run_meta.get("supplier_name", "")),
                "run_id": normalize_text(row.get("run_id", "")) or run_id,
                "candidate_id": candidate_id,
                "supplier_sku": normalize_text(row.get("supplier_sku", "")),
                "barcode": normalize_text(row.get("barcode", "")),
                "asin": normalize_text(row.get("asin", "")),
                "unit_cost": normalize_text(row.get("unit_cost", "")) or normalize_text(row.get("cost", "")),
                "source_file_path": normalize_text(row.get("source_file_path", "")) or normalize_text(run_meta.get("source_file_path", "")),
                "source_seen_at_utc": normalize_text(row.get("source_seen_at_utc", "")) or normalize_text(run_meta.get("source_seen_at_utc", "")),
                "scan_status": normalize_text(row.get("scan_status", "")) or normalize_text(row.get("row_status", "")),
                "scan_reason": normalize_text(row.get("scan_reason", "")),
                "pf": normalize_text(row.get("pf", "")),
                "status_reason": normalize_text(row.get("status_reason", "")),
                "fail_code": normalize_text(row.get("fail_code", "")),
                "last_stage": normalize_text(row.get("last_stage", "")),
                "browser_attempted_flag": normalize_text(row.get("browser_attempted_flag", "")),
                "browser_blocked_flag": normalize_text(row.get("browser_blocked_flag", "")),
                "api_429_count": normalize_text(row.get("api_429_count", "")),
                "updated_at_utc": normalize_text(row.get("updated_at_utc", "")),
            }
        )
    return rows


def _run_meta(root: Path, *, supplier_id: str, run_id: str) -> dict[str, str]:
    state = read_f_contract_df(root, "supplier_price_list_run_state")
    if state.empty:
        return {}
    work = state[
        (state["supplier_id"].map(lambda value: normalize_text(value).lower()) == supplier_id.lower())
        & (state["run_id"].map(normalize_text) == run_id)
    ].copy()
    if work.empty:
        work = state[state["supplier_id"].map(lambda value: normalize_text(value).lower()) == supplier_id.lower()].copy()
    if work.empty:
        return {}
    selected = work.iloc[0]
    return {column: normalize_text(selected.get(column, "")) for column in work.columns}


def _source_rows(root: Path, *, supplier_id: str, run_id: str) -> pd.DataFrame:
    meta = _run_meta(root, supplier_id=supplier_id, run_id=run_id)
    records_by_id: dict[str, dict[str, str]] = {}
    contract_names = [
        "supplier_price_list_active_run",
        "f_screening_row_state_live",
        "feeder_legacy_first_checks_live",
        "feeder_legacy_scrape_evidence_live",
        "f_scanner_speed_ledger_live",
    ]
    for contract_name in contract_names:
        try:
            records = _rows_from_contract(
                read_f_contract_df(root, contract_name),
                supplier_id=supplier_id,
                run_id=run_id,
                run_meta=meta,
            )
        except KeyError:
            records = []
        for record in records:
            candidate_id = normalize_text(record.get("candidate_id", ""))
            if not candidate_id:
                continue
            current = records_by_id.get(candidate_id, {})
            merged = current.copy()
            for key, value in record.items():
                if normalize_text(value):
                    merged[key] = normalize_text(value)
                elif key not in merged:
                    merged[key] = ""
            records_by_id[candidate_id] = merged
    rows = list(records_by_id.values())
    return _finalize(pd.DataFrame(rows), PIPELINE_ROW_COLUMNS)


def _active_pending_candidate_ids(root: Path, *, supplier_id: str, run_id: str, browser_ready_only: bool = False) -> set[str]:
    meta = _run_meta(root, supplier_id=supplier_id, run_id=run_id)
    records = _rows_from_contract(
        read_f_contract_df(root, "supplier_price_list_active_run"),
        supplier_id=supplier_id,
        run_id=run_id,
        run_meta=meta,
    )
    pending_ids: set[str] = set()
    for record in records:
        if not _is_pending(pd.Series(record)):
            continue
        if browser_ready_only and normalize_text(record.get("scan_reason", "")).lower() != "browser_stage_ready":
            continue
        candidate_id = normalize_text(record.get("candidate_id", ""))
        if candidate_id:
            pending_ids.add(candidate_id)
    return pending_ids


def _fail_signal(row: pd.Series) -> str:
    return normalize_text(row.get("fail_code", "")) or normalize_text(row.get("status_reason", ""))


def _is_pending(row: pd.Series) -> bool:
    return normalize_text(row.get("scan_status", "")).lower() in {"", "pending", "running", "timeout"}


def _stage_decision(row: pd.Series, stage_id: str) -> tuple[str, str]:
    fail_signal = _fail_signal(row).upper()
    pf = normalize_text(row.get("pf", "")).upper()
    last_stage = normalize_text(row.get("last_stage", "")).lower()
    if stage_id == "intake_enrichment":
        required = [
            "supplier_id",
            "run_id",
            "candidate_id",
            "supplier_sku",
            "barcode",
            "unit_cost",
            "source_file_path",
            "source_seen_at_utc",
        ]
        missing = [field for field in required if not normalize_text(row.get(field, ""))]
        if missing:
            return "blocked", f"missing_required_intake_field:{'|'.join(missing)}"
        return "passed", "intake_fields_present"
    if stage_id == "catalog_identity":
        if fail_signal in {"NOASIN", "OVER50K"} or last_stage in {"catalog", "rank_gate"} and pf == "FAIL":
            return "blocked", fail_signal or f"{last_stage}_failed"
        if normalize_text(row.get("asin", "")):
            return "passed", "asin_present"
        return "retry_later", "waiting_for_catalog_identity"
    if stage_id == "pricing_api":
        if fail_signal in {"NOCOST", "ROIFAIL", "LOWROI"}:
            return "blocked", fail_signal
        if pf == "FAIL" and last_stage in {"pricing", "roi_gate", "price_gate"}:
            return "blocked", fail_signal or f"{last_stage}_failed"
        return "passed", "pricing_not_blocked"
    if stage_id == "fee_hazmat_api":
        if fail_signal in {"HAZMATFAIL", "BRANDFAIL"}:
            return "blocked", fail_signal
        return "passed", "fee_hazmat_not_blocked"
    if stage_id == "browser_webscrape":
        if normalize_text(row.get("browser_blocked_flag", "")) == "1" or fail_signal in {
            "LOGIN_BACKTRACK_PENDING",
            "BBP_LOGIN_REQUIRED",
            "AMAZON_LOGIN_REQUIRED",
        }:
            return "retry_later", fail_signal or "browser_login_required"
        if pf == "PASS":
            return "passed", "browser_evidence_passed"
        if pf == "FAIL" and last_stage == "webscrape":
            return "blocked", fail_signal or "webscrape_failed"
        if normalize_text(row.get("browser_attempted_flag", "")) == "1":
            return "passed", "browser_attempted_no_block"
        return "retry_later", "waiting_for_browser_stage"
    raise ValueError(f"Unknown production-line stage: {stage_id}")


def _apply_stage(input_df: pd.DataFrame, *, stage_id: str, observed_utc: str) -> pd.DataFrame:
    out = _finalize(input_df, PIPELINE_ROW_COLUMNS)
    rows: list[dict[str, str]] = []
    for _, row in out.iterrows():
        decision, reason = _stage_decision(row, stage_id)
        payload = {column: normalize_text(row.get(column, "")) for column in PIPELINE_ROW_COLUMNS}
        payload["pipeline_stage"] = stage_id
        payload["stage_decision"] = decision
        payload["stage_reason"] = reason
        if decision == "blocked" and not normalize_text(payload.get("earliest_block_stage", "")):
            payload["earliest_block_stage"] = stage_id
            payload["earliest_block_reason"] = reason
        payload["updated_at_utc"] = observed_utc
        rows.append(payload)
    return _finalize(pd.DataFrame(rows), PIPELINE_ROW_COLUMNS)


def _write_stage(
    *,
    stage_dir: Path,
    stage_id: str,
    supplier_id: str,
    run_id: str,
    input_df: pd.DataFrame,
    output_df: pd.DataFrame,
    previous_manifest_path: Path | None,
    observed_utc: str,
) -> dict[str, str]:
    rows_path = stage_dir / "rows.csv"
    next_input_path = stage_dir / "next_stage_input.csv"
    status_path = stage_dir / "status.csv"
    manifest_path = stage_dir / "manifest.csv"
    passed_df = output_df[output_df["stage_decision"] == "passed"].copy()
    blocked_rows = int((output_df["stage_decision"] == "blocked").sum())
    retry_rows = int((output_df["stage_decision"] == "retry_later").sum())
    passed_rows = int(len(passed_df.index))
    input_rows = int(len(input_df.index))
    if input_rows != passed_rows + blocked_rows + retry_rows:
        raise ValueError(
            f"{stage_id} reconciliation failed: input={input_rows} passed={passed_rows} "
            f"blocked={blocked_rows} retry={retry_rows}"
        )
    _atomic_write_csv(rows_path, output_df, PIPELINE_ROW_COLUMNS)
    _atomic_write_csv(next_input_path, passed_df, PIPELINE_ROW_COLUMNS)
    status_row = {
        "stage_id": stage_id,
        "status": "completed",
        "supplier_id": supplier_id,
        "run_id": run_id,
        "input_rows": str(input_rows),
        "passed_rows": str(passed_rows),
        "blocked_rows": str(blocked_rows),
        "retry_rows": str(retry_rows),
        "observed_utc": observed_utc,
        "notes": "stage_completed",
        "manifest_path": str(manifest_path),
        "rows_path": str(rows_path),
    }
    _atomic_write_csv(status_path, pd.DataFrame([status_row]), PIPELINE_STAGE_STATUS_COLUMNS)
    manifest_row = {
        "stage_id": stage_id,
        "stage_status": "completed",
        "supplier_id": supplier_id,
        "run_id": run_id,
        "input_rows": str(input_rows),
        "passed_rows": str(passed_rows),
        "blocked_rows": str(blocked_rows),
        "retry_rows": str(retry_rows),
        "source_hash": _hash_frame(input_df),
        "previous_manifest_path": str(previous_manifest_path or ""),
        "rows_path": str(rows_path),
        "next_stage_input_path": str(next_input_path),
        "status_path": str(status_path),
        "observed_utc": observed_utc,
        "completed_at_utc": observed_utc,
        "notes": "stage_completed",
    }
    _atomic_write_csv(manifest_path, pd.DataFrame([manifest_row]), PIPELINE_STAGE_MANIFEST_COLUMNS)
    return {column: normalize_text(manifest_row.get(column, "")) for column in PIPELINE_STAGE_MANIFEST_COLUMNS}


def read_completed_stage_input(manifest_path: Path) -> pd.DataFrame:
    if not manifest_path.exists():
        raise PipelineStageNotReady(f"missing_manifest:{manifest_path}")
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    manifest = _finalize(manifest, PIPELINE_STAGE_MANIFEST_COLUMNS)
    if manifest.empty:
        raise PipelineStageNotReady(f"empty_manifest:{manifest_path}")
    row = manifest.iloc[0]
    if normalize_text(row.get("stage_status", "")) != "completed":
        raise PipelineStageNotReady(f"incomplete_manifest:{manifest_path}")
    next_path = Path(normalize_text(row.get("next_stage_input_path", "")))
    rows_path = Path(normalize_text(row.get("rows_path", "")))
    if not next_path.exists():
        raise PipelineStageNotReady(f"missing_next_stage_input:{next_path}")
    if not rows_path.exists():
        raise PipelineStageNotReady(f"missing_rows:{rows_path}")
    rows = pd.read_csv(rows_path, dtype=str).fillna("")
    rows = _finalize(rows, PIPELINE_ROW_COLUMNS)
    passed_rows = int(float(normalize_text(row.get("passed_rows", "0")) or 0))
    blocked_rows = int(float(normalize_text(row.get("blocked_rows", "0")) or 0))
    retry_rows = int(float(normalize_text(row.get("retry_rows", "0")) or 0))
    input_rows = int(float(normalize_text(row.get("input_rows", "0")) or 0))
    if input_rows != passed_rows + blocked_rows + retry_rows:
        raise PipelineStageNotReady(f"manifest_reconciliation_failed:{manifest_path}")
    next_df = pd.read_csv(next_path, dtype=str).fillna("")
    if int(len(next_df.index)) != passed_rows:
        raise PipelineStageNotReady(f"next_stage_input_count_mismatch:{manifest_path}")
    return _finalize(next_df, PIPELINE_ROW_COLUMNS)


def _write_browser_routing(
    *,
    run_dir: Path,
    supplier_id: str,
    run_id: str,
    source_manifest_path: Path,
    browser_input_df: pd.DataFrame,
    observed_utc: str,
    notes: str = "browser_input_from_fee_hazmat_passed_rows",
) -> dict[str, str]:
    browser_input_path = run_dir / "browser_input.csv"
    routing_manifest_path = run_dir / "browser_routing_manifest.csv"
    routed = _atomic_write_csv(browser_input_path, browser_input_df, PIPELINE_ROW_COLUMNS)
    manifest_row = {
        "routing_status": "completed",
        "supplier_id": supplier_id,
        "run_id": run_id,
        "source_stage_id": "fee_hazmat_api",
        "source_manifest_path": str(source_manifest_path),
        "browser_input_path": str(browser_input_path),
        "browser_input_rows": str(len(routed.index)),
        "source_hash": _hash_frame(routed),
        "observed_utc": observed_utc,
        "completed_at_utc": observed_utc,
        "notes": notes,
    }
    _atomic_write_csv(routing_manifest_path, pd.DataFrame([manifest_row]), PIPELINE_ROUTING_MANIFEST_COLUMNS)
    return {column: normalize_text(manifest_row.get(column, "")) for column in PIPELINE_ROUTING_MANIFEST_COLUMNS}


def _write_production_line_speed_ledger(
    *,
    run_dir: Path,
    supplier_id: str,
    run_id: str,
    cycle_run_id: str,
    observed_utc: str,
    stage_manifests: list[dict[str, str]],
    browser_input_rows: int,
    source_rows: pd.DataFrame,
) -> None:
    by_stage = {normalize_text(row.get("stage_id", "")): row for row in stage_manifests}
    catalog = by_stage.get("catalog_identity", {})
    pricing = by_stage.get("pricing_api", {})
    fees = by_stage.get("fee_hazmat_api", {})
    browser = by_stage.get("browser_webscrape", {})
    api_stopped = sum(
        int(float(normalize_text(stage.get("blocked_rows", "0")) or 0))
        for stage in [catalog, pricing, fees]
    )
    retry_rows = sum(
        int(float(normalize_text(stage.get("retry_rows", "0")) or 0))
        for stage in [catalog, pricing, fees, browser]
    )
    browser_rows_attempted = 0
    login_rows = 0
    api_429_count = 0
    if not source_rows.empty:
        browser_rows_attempted = int((source_rows["browser_attempted_flag"].map(normalize_text) == "1").sum())
        api_429_count = int(
            sum(
                int(float(normalize_text(value) or 0))
                for value in source_rows["api_429_count"].tolist()
            )
        )
        fail_text = source_rows["stage_reason"].map(normalize_text).str.lower() if "stage_reason" in source_rows.columns else pd.Series(dtype=str)
        if not fail_text.empty:
            login_rows = int(fail_text.str.contains("login|captcha|bbp", regex=True).sum())
    row = {
        "observed_utc": observed_utc,
        "supplier_id": supplier_id,
        "run_id": run_id,
        "cycle_run_id": normalize_text(cycle_run_id),
        "api_rows_checked": normalize_text(catalog.get("input_rows", "0")) or "0",
        "api_stopped_rows": str(api_stopped),
        "retry_rows": str(retry_rows),
        "browser_ready_rows": str(int(browser_input_rows)),
        "browser_rows_attempted": str(browser_rows_attempted),
        "login_rows": str(login_rows),
        "api_429_count": str(api_429_count),
        "endpoint_calls": "0",
        "elapsed_seconds": "0.000",
        "notes": "stage_totals_from_pipeline_manifests",
    }
    _atomic_write_csv(run_dir / "production_line_speed_ledger.csv", pd.DataFrame([row]), PRODUCTION_LINE_SPEED_LEDGER_COLUMNS)


def read_completed_browser_routing(run_dir: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    manifest_path = run_dir / "browser_routing_manifest.csv"
    if not manifest_path.exists():
        raise PipelineStageNotReady(f"missing_browser_routing_manifest:{manifest_path}")
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    manifest = _finalize(manifest, PIPELINE_ROUTING_MANIFEST_COLUMNS)
    if manifest.empty:
        raise PipelineStageNotReady(f"empty_browser_routing_manifest:{manifest_path}")
    row = manifest.iloc[0]
    if normalize_text(row.get("routing_status", "")) != "completed":
        raise PipelineStageNotReady(f"incomplete_browser_routing_manifest:{manifest_path}")
    browser_input_path = Path(normalize_text(row.get("browser_input_path", "")))
    if not browser_input_path.exists():
        raise PipelineStageNotReady(f"missing_browser_input:{browser_input_path}")
    browser_input = pd.read_csv(browser_input_path, dtype=str).fillna("")
    browser_input = _finalize(browser_input, PIPELINE_ROW_COLUMNS)
    expected_rows = int(float(normalize_text(row.get("browser_input_rows", "0")) or 0))
    if len(browser_input.index) != expected_rows:
        raise PipelineStageNotReady(f"browser_input_count_mismatch:{manifest_path}")
    return browser_input, {column: normalize_text(row.get(column, "")) for column in PIPELINE_ROUTING_MANIFEST_COLUMNS}


def build_production_line_run(
    root: Path | None = None,
    *,
    supplier_id: str,
    run_id: str,
    observed_utc: str | None = None,
    cycle_run_id: str = "",
) -> dict[str, object]:
    root_path = Path(root) if root is not None else ROOT
    observed = observed_utc or _utc_now_iso()
    selected_supplier = normalize_text(supplier_id)
    selected_run = normalize_text(run_id)
    run_dir = pipeline_run_dir(root_path, supplier_id=selected_supplier, run_id=selected_run)
    run_dir.mkdir(parents=True, exist_ok=True)

    stage_input = _source_rows(root_path, supplier_id=selected_supplier, run_id=selected_run)
    first_input_count = int(len(stage_input.index))
    previous_manifest: Path | None = None
    manifests: list[dict[str, str]] = []
    manifest_paths_by_stage: dict[str, Path] = {}
    for stage_id in PRODUCTION_LINE_STAGES:
        if previous_manifest is not None:
            stage_input = read_completed_stage_input(previous_manifest)
        stage_output = _apply_stage(stage_input, stage_id=stage_id, observed_utc=observed)
        stage_dir = run_dir / stage_id
        manifest = _write_stage(
            stage_dir=stage_dir,
            stage_id=stage_id,
            supplier_id=selected_supplier,
            run_id=selected_run,
            input_df=stage_input,
            output_df=stage_output,
            previous_manifest_path=previous_manifest,
            observed_utc=observed,
        )
        manifests.append(manifest)
        previous_manifest = stage_dir / "manifest.csv"
        manifest_paths_by_stage[stage_id] = previous_manifest

    routing_manifest: dict[str, str] = {}
    fee_manifest_path = manifest_paths_by_stage.get("fee_hazmat_api")
    if fee_manifest_path is not None:
        browser_input_source_df = read_completed_stage_input(fee_manifest_path)
        active_pending_ids = _active_pending_candidate_ids(
            root_path,
            supplier_id=selected_supplier,
            run_id=selected_run,
            browser_ready_only=True,
        )
        browser_input_df = browser_input_source_df[
            browser_input_source_df["candidate_id"].map(normalize_text).isin(active_pending_ids)
        ].copy()
        routing_manifest = _write_browser_routing(
            run_dir=run_dir,
            supplier_id=selected_supplier,
            run_id=selected_run,
            source_manifest_path=fee_manifest_path,
            browser_input_df=browser_input_df,
            observed_utc=observed,
            notes=(
                "browser_input_from_fee_hazmat_passed_rows;"
                f"source_browser_rows={len(browser_input_source_df.index)};"
                f"active_pending_browser_ready_rows={len(active_pending_ids)}"
            ),
        )
    browser_input_count = int(float(normalize_text(routing_manifest.get("browser_input_rows", "0")) or 0))
    final_source_rows = read_completed_stage_input(manifest_paths_by_stage["browser_webscrape"]) if "browser_webscrape" in manifest_paths_by_stage else pd.DataFrame()
    _write_production_line_speed_ledger(
        run_dir=run_dir,
        supplier_id=selected_supplier,
        run_id=selected_run,
        cycle_run_id=cycle_run_id,
        observed_utc=observed,
        stage_manifests=manifests,
        browser_input_rows=browser_input_count,
        source_rows=final_source_rows,
    )
    final_manifest = manifests[-1] if manifests else {}
    status_row = {
        "observed_utc": observed,
        "supplier_id": selected_supplier,
        "run_id": selected_run,
        "status": "completed",
        "stage_count": str(len(manifests)),
        "input_rows": str(first_input_count),
        "final_pass_rows": normalize_text(final_manifest.get("passed_rows", "0")),
        "final_blocked_rows": normalize_text(final_manifest.get("blocked_rows", "0")),
        "final_retry_rows": normalize_text(final_manifest.get("retry_rows", "0")),
        "pipeline_run_dir": str(run_dir),
        "notes": (
            f"hybrid_staged_v1;cycle_run_id={normalize_text(cycle_run_id)};"
            f"browser_input_rows={browser_input_count}"
        ),
    }
    _atomic_write_csv(run_dir / "pipeline_run_status.csv", pd.DataFrame([status_row]), PIPELINE_RUN_STATUS_COLUMNS)
    return {
        "status": "completed",
        "supplier_id": selected_supplier,
        "run_id": selected_run,
        "stage_count": len(manifests),
        "input_rows": first_input_count,
        "final_pass_rows": int(float(normalize_text(final_manifest.get("passed_rows", "0")) or 0)),
        "final_blocked_rows": int(float(normalize_text(final_manifest.get("blocked_rows", "0")) or 0)),
        "final_retry_rows": int(float(normalize_text(final_manifest.get("retry_rows", "0")) or 0)),
        "pipeline_run_dir": str(run_dir),
        "browser_input_rows": browser_input_count,
        "browser_input_path": normalize_text(routing_manifest.get("browser_input_path", "")),
        "browser_routing_manifest_path": str(run_dir / "browser_routing_manifest.csv"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the F scanner production-line handoff manifests.")
    parser.add_argument("--supplier-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--observed-utc", default="")
    args = parser.parse_args()
    build_production_line_run(
        root=Path(args.root),
        supplier_id=args.supplier_id,
        run_id=args.run_id,
        observed_utc=args.observed_utc or None,
    )


if __name__ == "__main__":
    main()
