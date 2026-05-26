from __future__ import annotations

import argparse
import importlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from scripts.flows.F._contract_io import write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contract


CONFIG_DIR = Path("config") / "feeder" / "suppliers"

ACTIVE_RUN_COLUMNS = [
    "run_id",
    "supplier_id",
    "supplier_name",
    "row_key",
    "supplier_sku",
    "barcode",
    "supplier_title",
    "unit_cost",
    "currency",
    "vat_rate",
    "scan_status",
    "scan_reason",
    "attempt_count",
    "last_attempt_utc",
    "finished_utc",
    "source_seen_at_utc",
]

RUN_STATE_COLUMNS = [
    "supplier_id",
    "supplier_name",
    "run_id",
    "run_status",
    "source_url",
    "source_file_path",
    "source_seen_at_utc",
    "normalized_utc",
    "total_rows",
    "pending_rows",
    "done_rows",
    "failed_rows",
    "held_rows",
    "next_row_index",
    "updated_at_utc",
    "completed_at_utc",
]

QUEUE_STATE_COLUMNS = [
    "queue_id",
    "current_supplier_id",
    "current_run_id",
    "last_completed_supplier_id",
    "next_supplier_id",
    "queue_index",
    "status",
    "updated_at_utc",
    "notes",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=_contract_columns(contract_name))


def _finalize_contract_df(df: pd.DataFrame, contract_name: str) -> pd.DataFrame:
    ordered = _contract_columns(contract_name)
    out = df.copy()
    for column in ordered:
        if column not in out.columns:
            out[column] = ""
    out = out[ordered]
    for column in ordered:
        out[column] = out[column].map(_normalize_text)
    return out


def _type_mismatch_columns(df: pd.DataFrame, contract_name: str) -> list[str]:
    expected_types = get_f_output_column_types(contract_name)
    mismatches: list[str] = []
    for column, expected in expected_types.items():
        if expected == "string" and column in df.columns and not pd.api.types.is_object_dtype(df[column]):
            mismatches.append(column)
    return mismatches


def _write_contract_df(df: pd.DataFrame, contract_name: str, root_path: Path) -> pd.DataFrame:
    finalized = _finalize_contract_df(df, contract_name)
    mismatches = _type_mismatch_columns(finalized, contract_name)
    if mismatches:
        mismatch_text = ",".join(sorted(mismatches))
        raise ValueError(f"{contract_name} type mismatch for string columns: {mismatch_text}")
    out_path = root_path / get_f_output_contract(contract_name).rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_f_contract_df(root_path, contract_name, finalized)
    return finalized


def _load_supplier_configs(root_path: Path) -> list[dict]:
    config_dir = root_path / CONFIG_DIR
    if not config_dir.exists():
        return []
    configs: list[dict] = []
    for path in sorted(config_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["config_path"] = str(path)
        configs.append(payload)
    return configs


def _resolve_converter(supplier_id: str):
    module_name = f"scripts.flows.F.suppliers.{supplier_id}"
    module = importlib.import_module(module_name)
    if not hasattr(module, "convert_supplier"):
        raise ValueError(f"converter missing convert_supplier: {module_name}")
    return module.convert_supplier


def _rotate_file(current_path: Path, previous_path: Path) -> None:
    if current_path.exists():
        previous_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current_path), str(previous_path))


def _write_csv(path: Path, df: pd.DataFrame, columns: Iterable[str]) -> None:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = ""
    out = out[list(columns)]
    for col in columns:
        out[col] = out[col].map(_normalize_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _download_source(url: str, dest_path: Path, *, timeout_seconds: int = 60) -> None:
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(response.content)


def _build_active_run(
    df_valid: pd.DataFrame,
    *,
    supplier_id: str,
    supplier_name: str,
    run_id: str,
    source_seen_at_utc: str,
) -> pd.DataFrame:
    if df_valid.empty:
        return pd.DataFrame(columns=ACTIVE_RUN_COLUMNS)

    rows = []
    for _, row in df_valid.iterrows():
        rows.append(
            {
                "run_id": run_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "row_key": _normalize_text(row.get("row_hash")),
                "supplier_sku": _normalize_text(row.get("supplier_sku")),
                "barcode": _normalize_text(row.get("barcode")),
                "supplier_title": _normalize_text(row.get("supplier_title")),
                "unit_cost": _normalize_text(row.get("unit_cost")),
                "currency": _normalize_text(row.get("currency")),
                "vat_rate": _normalize_text(row.get("vat_rate")),
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": source_seen_at_utc,
            }
        )
    return pd.DataFrame(rows)


def _build_run_state(
    *,
    supplier_id: str,
    supplier_name: str,
    run_id: str,
    source_url: str,
    source_file_path: str,
    source_seen_at_utc: str,
    normalized_utc: str,
    active_run: pd.DataFrame,
    holds_df: pd.DataFrame,
) -> dict[str, str]:
    total_rows = int(len(active_run))
    pending_rows = int(len(active_run[active_run["scan_status"] == "pending"])) if total_rows else 0
    done_rows = int(len(active_run[active_run["scan_status"] == "done"])) if total_rows else 0
    failed_rows = int(len(active_run[active_run["scan_status"] == "failed"])) if total_rows else 0
    held_rows = int(len(holds_df))

    next_row_index = "0"
    if total_rows:
        pending = active_run[active_run["scan_status"] == "pending"]
        if not pending.empty:
            next_row_index = str(int(pending.index[0]) + 1)

    run_status = "running" if total_rows and pending_rows else "completed"
    completed_at = "" if run_status == "running" else _utc_now_iso()

    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "run_id": run_id,
        "run_status": run_status,
        "source_url": source_url,
        "source_file_path": source_file_path,
        "source_seen_at_utc": source_seen_at_utc,
        "normalized_utc": normalized_utc,
        "total_rows": str(total_rows),
        "pending_rows": str(pending_rows),
        "done_rows": str(done_rows),
        "failed_rows": str(failed_rows),
        "held_rows": str(held_rows),
        "next_row_index": next_row_index,
        "updated_at_utc": _utc_now_iso(),
        "completed_at_utc": completed_at,
    }


def _reset_supplier_scan_workspace(
    *,
    root_path: Path,
    supplier_dir: Path,
) -> None:
    for path in [supplier_dir / "active_run.csv", supplier_dir / "run_state.csv"]:
        if path.exists():
            path.unlink()

    reset_contracts = [
        "supplier_price_list_active_run",
        "supplier_price_list_run_state",
        "f_screening_row_state_live",
        "feeder_legacy_first_checks_live",
        "feeder_legacy_scrape_evidence_live",
        "feeder_legacy_chart_daily_raw_live",
        "feeder_legacy_second_checks_live",
        "feeder_legacy_bot_status_live",
    ]
    for contract_name in reset_contracts:
        _write_contract_df(_empty_contract_df(contract_name), contract_name, root_path)


def build_supplier_price_list_universal(
    root: Path | None = None,
    *,
    supplier_id: str,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    configs = _load_supplier_configs(root_path)
    if not configs:
        raise ValueError("no supplier configs found")
    if _normalize_text(supplier_id) == "":
        raise ValueError("supplier_id is required for single-supplier fresh runs")

    queue_state_path = root_path / get_f_output_contract("supplier_price_list_queue_state").rel_path
    config = next(
        (cfg for cfg in configs if _normalize_lower(cfg.get("supplier_id")) == _normalize_lower(supplier_id)),
        None,
    )
    if config is None:
        raise ValueError(f"supplier_id not found: {supplier_id}")

    supplier_id = _normalize_text(config.get("supplier_id"))
    supplier_name = _normalize_text(config.get("supplier_name"))
    source_url = _normalize_text(config.get("source_url"))
    source_override = _normalize_text(config.get("source_path_override"))
    currency = _normalize_text(config.get("currency") or "GBP")
    vat_rate = _normalize_text(config.get("default_vat_rate") or "20")
    skip_suffixes = config.get("skip_sku_suffixes") or []

    supplier_dir = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id
    raw_current = supplier_dir / "raw_current.csv"
    raw_previous = supplier_dir / "raw_previous.csv"
    canonical_current = supplier_dir / "canonical_current.csv"
    canonical_previous = supplier_dir / "canonical_previous.csv"

    source_seen_at_utc = _utc_now_iso()
    fetch_status = "ok"
    fetch_notes = "downloaded"

    try:
        if source_override:
            override_path = Path(source_override)
            if not override_path.exists():
                raise FileNotFoundError(f"source_path_override missing: {override_path}")
            _rotate_file(raw_current, raw_previous)
            raw_current.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(override_path, raw_current)
            fetch_notes = "local_override"
        else:
            _rotate_file(raw_current, raw_previous)
            _download_source(source_url, raw_current)
    except Exception as exc:
        fetch_status = "fail"
        fetch_notes = f"fetch_error:{type(exc).__name__}"
        health_rows = [
            {
                "check": "supplier_price_list_source_fetch",
                "status": fetch_status,
                "value": "0",
                "notes": fetch_notes,
                "observed_utc": _utc_now_iso(),
                "source_path": str(raw_current),
            },
            {
                "check": "supplier_price_list_conversion_quality",
                "status": "fail",
                "value": "0",
                "notes": "conversion_skipped_due_to_fetch_error",
                "observed_utc": _utc_now_iso(),
                "source_path": str(raw_current),
            },
        ]
        _write_contract_df(pd.DataFrame(health_rows), "supplier_price_list_health", root_path)
        raise

    try:
        convert = _resolve_converter(supplier_id)
        valid_df, holds_df = convert(
            raw_current,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            source_url=source_url,
            source_seen_at_utc=source_seen_at_utc,
            currency=currency,
            vat_rate=vat_rate,
            skip_sku_suffixes=skip_suffixes,
        )
    except Exception as exc:
        health_rows = [
            {
                "check": "supplier_price_list_source_fetch",
                "status": fetch_status,
                "value": "0",
                "notes": fetch_notes,
                "observed_utc": _utc_now_iso(),
                "source_path": str(raw_current),
            },
            {
                "check": "supplier_price_list_conversion_quality",
                "status": "fail",
                "value": "0",
                "notes": f"conversion_error:{type(exc).__name__}",
                "observed_utc": _utc_now_iso(),
                "source_path": str(raw_current),
            },
        ]
        _write_contract_df(pd.DataFrame(health_rows), "supplier_price_list_health", root_path)
        raise

    _reset_supplier_scan_workspace(
        root_path=root_path,
        supplier_dir=supplier_dir,
    )

    _rotate_file(canonical_current, canonical_previous)
    canonical_current.parent.mkdir(parents=True, exist_ok=True)
    valid_df.to_csv(canonical_current, index=False)

    run_id = f"{supplier_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    active_run = _build_active_run(
        valid_df,
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        run_id=run_id,
        source_seen_at_utc=source_seen_at_utc,
    )

    run_state_row = _build_run_state(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        run_id=run_id,
        source_url=source_url,
        source_file_path=str(raw_current),
        source_seen_at_utc=source_seen_at_utc,
        normalized_utc=_utc_now_iso(),
        active_run=active_run,
        holds_df=holds_df,
    )

    _write_csv(supplier_dir / "active_run.csv", active_run, ACTIVE_RUN_COLUMNS)
    _write_csv(supplier_dir / "run_state.csv", pd.DataFrame([run_state_row]), RUN_STATE_COLUMNS)

    _write_contract_df(valid_df, "supplier_price_list_universal_live", root_path)
    _write_contract_df(holds_df, "supplier_price_list_universal_holds", root_path)

    active_run_df = _write_contract_df(active_run, "supplier_price_list_active_run", root_path)
    run_state_df = _write_contract_df(pd.DataFrame([run_state_row]), "supplier_price_list_run_state", root_path)

    queue_state_row = {
        "queue_id": "default",
        "current_supplier_id": supplier_id,
        "current_run_id": run_id,
        "last_completed_supplier_id": "",
        "next_supplier_id": "",
        "queue_index": "0",
        "status": "ok",
        "updated_at_utc": _utc_now_iso(),
        "notes": "single_supplier_fresh_run",
    }
    queue_state_df = pd.DataFrame([queue_state_row])
    queue_state_df = _write_contract_df(queue_state_df, "supplier_price_list_queue_state", root_path)

    conversion_status = "ok"
    conversion_notes = "conversion_complete"
    if len(valid_df) == 0 and len(holds_df) > 0:
        conversion_status = "warn"
        conversion_notes = "no_valid_rows"
    elif len(holds_df) > 0:
        conversion_status = "warn"
        conversion_notes = "holds_present"

    health_rows = [
        {
            "check": "supplier_price_list_source_fetch",
            "status": fetch_status,
            "value": str(len(valid_df) + len(holds_df)),
            "notes": fetch_notes,
            "observed_utc": _utc_now_iso(),
            "source_path": str(raw_current),
        },
        {
            "check": "supplier_price_list_conversion_quality",
            "status": conversion_status,
            "value": str(len(valid_df)),
            "notes": conversion_notes,
            "observed_utc": _utc_now_iso(),
            "source_path": str(canonical_current),
        },
        {
            "check": "supplier_price_list_queue_state",
            "status": "ok",
            "value": "1",
            "notes": "queue_state_updated",
            "observed_utc": _utc_now_iso(),
            "source_path": str(queue_state_path),
        },
    ]
    health_df = _write_contract_df(pd.DataFrame(health_rows), "supplier_price_list_health", root_path)

    summary = {
        "status": "success",
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "source_rows": int(len(valid_df) + len(holds_df)),
        "valid_rows": int(len(valid_df)),
        "hold_rows": int(len(holds_df)),
        "queue_index": 0,
        "queue_state_path": str(queue_state_path),
        "active_run_path": str(supplier_dir / "active_run.csv"),
        "run_state_path": str(supplier_dir / "run_state.csv"),
        "universal_path": str(root_path / get_f_output_contract("supplier_price_list_universal_live").rel_path),
        "holds_path": str(root_path / get_f_output_contract("supplier_price_list_universal_holds").rel_path),
        "health_path": str(root_path / get_f_output_contract("supplier_price_list_health").rel_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build universal supplier price list output.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier", required=True)
    args = parser.parse_args()

    root_path = Path(args.root) if args.root else None
    build_supplier_price_list_universal(root=root_path, supplier_id=args.supplier)


if __name__ == "__main__":
    main()
