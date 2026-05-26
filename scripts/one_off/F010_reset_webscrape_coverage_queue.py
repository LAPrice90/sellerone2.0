import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_contract


CONFIG_DIR = Path("config") / "feeder" / "suppliers"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
PROCESSED_SCREENING_STATUSES = {"pass", "timeout"}
CLEAR_CONTRACTS = [
    "feeder_legacy_first_checks_live",
    "feeder_legacy_scrape_evidence_live",
    "feeder_legacy_chart_daily_raw_live",
    "feeder_legacy_second_checks_live",
    "feeder_legacy_bot_status_live",
    "feeder_legacy_sheet_health",
    "feeder_backtest_input_view_live",
    "feeder_backtest_replay_daily_live",
    "feeder_backtest_summary_live",
    "feeder_backtest_health",
]
QUEUE_ORDER_PRIORITY_FIRST = "priority-first"
QUEUE_ORDER_REMAINING_FIRST = "remaining-first"
QUEUE_ORDER_ALLOWED = {QUEUE_ORDER_PRIORITY_FIRST, QUEUE_ORDER_REMAINING_FIRST}

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


@dataclass(frozen=True)
class ResetWebscrapeCoverageResult:
    report_df: pd.DataFrame
    report_path: Path
    latest_path: Path
    summary: dict[str, object]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _amazon_link(asin: str) -> str:
    asin_key = _normalize_text(asin)
    if asin_key == "":
        return ""
    return f"https://www.amazon.co.uk/dp/{asin_key}"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _write_csv(path: Path, df: pd.DataFrame, columns: Iterable[str]) -> None:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[list(columns)]
    for column in columns:
        out[column] = out[column].map(_normalize_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def _contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def _read_contract_df(contract_name: str, root_path: Path) -> pd.DataFrame:
    path = root_path / get_f_output_contract(contract_name).rel_path
    if not path.exists():
        return pd.DataFrame(columns=_contract_columns(contract_name))
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=_contract_columns(contract_name))


def _write_contract_df(df: pd.DataFrame, contract_name: str, root_path: Path) -> pd.DataFrame:
    ordered = _contract_columns(contract_name)
    out = df.copy()
    for column in ordered:
        if column not in out.columns:
            out[column] = ""
    out = out[ordered]
    for column in ordered:
        out[column] = out[column].map(_normalize_text)
    path = root_path / get_f_output_contract(contract_name).rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return out


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return pd.DataFrame(columns=_contract_columns(contract_name))


def _load_supplier_config(root_path: Path, supplier_id: str) -> dict[str, str]:
    supplier_key = _normalize_lower(supplier_id)
    config_dir = root_path / CONFIG_DIR
    if not config_dir.exists():
        raise FileNotFoundError(f"supplier config directory missing: {config_dir}")
    for path in sorted(config_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if _normalize_lower(payload.get("supplier_id", "")) == supplier_key:
            return payload
    raise ValueError(f"supplier_id not found in config/feeder/suppliers: {supplier_id}")


def _latest_scrape_rows(scrape_df: pd.DataFrame, *, supplier_id: str) -> pd.DataFrame:
    if scrape_df.empty:
        return scrape_df
    supplier_key = _normalize_lower(supplier_id)
    work = scrape_df[scrape_df.get("supplier_id", "").map(_normalize_lower) == supplier_key].copy()
    if work.empty:
        return work
    work["_observed_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")
    fallback_key = (
        work.get("supplier_sku", "").map(_normalize_key)
        + "|"
        + work.get("barcode", "").map(_normalize_key)
        + "|"
        + work.get("asin", "").map(_normalize_key)
    )
    work["_dedupe_key"] = work.get("candidate_id", "").map(_normalize_key)
    work.loc[work["_dedupe_key"] == "", "_dedupe_key"] = fallback_key
    work = work[work["_dedupe_key"] != ""].copy()
    if work.empty:
        return work
    work = work.drop_duplicates(subset=["_dedupe_key"], keep="first")
    work = work[
        (work.get("asin", "").map(_normalize_text) != "")
        | (work.get("scrape_attempted", "").map(_normalize_lower).isin({"true", "1", "yes"}))
    ].copy()
    return work.drop(columns=["_observed_ts", "_dedupe_key"], errors="ignore").reset_index(drop=True)


def _latest_processed_screening_rows(screening_df: pd.DataFrame, *, supplier_id: str) -> pd.DataFrame:
    if screening_df.empty:
        return screening_df
    supplier_key = _normalize_lower(supplier_id)
    work = screening_df[screening_df.get("supplier_id", "").map(_normalize_lower) == supplier_key].copy()
    if work.empty:
        return work
    work = work[work.get("row_status", "").map(_normalize_lower).isin(PROCESSED_SCREENING_STATUSES)].copy()
    if work.empty:
        return work
    work["_observed_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce")
    work = work.sort_values("_observed_ts", ascending=False, kind="stable")
    fallback_key = (
        work.get("candidate_id", "").map(_normalize_key)
        + "|"
        + work.get("supplier_sku", "").map(_normalize_key)
        + "|"
        + work.get("barcode", "").map(_normalize_key)
    )
    work["_dedupe_key"] = work.get("candidate_id", "").map(_normalize_key)
    work.loc[work["_dedupe_key"] == "", "_dedupe_key"] = fallback_key
    work = work[work["_dedupe_key"] != ""].copy()
    if work.empty:
        return work
    work = work.drop_duplicates(subset=["_dedupe_key"], keep="first")
    return work.drop(columns=["_observed_ts", "_dedupe_key"], errors="ignore").reset_index(drop=True)


def _queue_from_canonical(canonical_df: pd.DataFrame, *, supplier_id: str, supplier_name: str) -> pd.DataFrame:
    if canonical_df.empty:
        return pd.DataFrame(columns=ACTIVE_RUN_COLUMNS + ["source_file_path"])
    supplier_key = _normalize_lower(supplier_id)
    work = canonical_df[canonical_df.get("supplier_id", "").map(_normalize_lower) == supplier_key].copy()
    if work.empty:
        return work
    rows: list[dict[str, str]] = []
    for _, row in work.iterrows():
        rows.append(
            {
                "run_id": "",
                "supplier_id": _normalize_text(row.get("supplier_id", "")) or supplier_id,
                "supplier_name": _normalize_text(row.get("supplier_name", "")) or supplier_name,
                "row_key": _normalize_text(row.get("row_hash", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "supplier_title": _normalize_text(row.get("supplier_title", "")),
                "unit_cost": _normalize_text(row.get("unit_cost", "")),
                "currency": _normalize_text(row.get("currency", "")),
                "vat_rate": _normalize_text(row.get("vat_rate", "")),
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": _normalize_text(row.get("source_seen_at_utc", "")),
                "source_file_path": _normalize_text(row.get("source_file_path", "")),
            }
        )
    return pd.DataFrame(rows)


def _build_queue_indexes(queue_df: pd.DataFrame) -> dict[str, dict[str, int]]:
    by_row_key: dict[str, int] = {}
    by_sku_barcode: dict[str, int] = {}
    by_sku: dict[str, int] = {}
    by_barcode: dict[str, int] = {}
    for idx, row in queue_df.iterrows():
        row_key = _normalize_key(row.get("row_key", ""))
        supplier_sku = _normalize_key(row.get("supplier_sku", ""))
        barcode = _normalize_key(row.get("barcode", ""))
        sku_barcode = f"{supplier_sku}|{barcode}" if (supplier_sku or barcode) else ""
        if row_key and row_key not in by_row_key:
            by_row_key[row_key] = int(idx)
        if sku_barcode and sku_barcode not in by_sku_barcode:
            by_sku_barcode[sku_barcode] = int(idx)
        if supplier_sku and supplier_sku not in by_sku:
            by_sku[supplier_sku] = int(idx)
        if barcode and barcode not in by_barcode:
            by_barcode[barcode] = int(idx)
    return {
        "row_key": by_row_key,
        "sku_barcode": by_sku_barcode,
        "sku": by_sku,
        "barcode": by_barcode,
    }


def _match_queue_row(row: pd.Series, queue_indexes: dict[str, dict[str, int]]) -> tuple[int | None, str, str]:
    candidate_id = _normalize_text(row.get("candidate_id", ""))
    supplier_sku = _normalize_text(row.get("supplier_sku", ""))
    barcode = _normalize_text(row.get("barcode", ""))

    candidate_key = _normalize_key(candidate_id)
    supplier_sku_key = _normalize_key(supplier_sku)
    barcode_key = _normalize_key(barcode)
    sku_barcode_key = f"{supplier_sku_key}|{barcode_key}" if (supplier_sku_key or barcode_key) else ""

    if candidate_key and candidate_key in queue_indexes["row_key"]:
        return queue_indexes["row_key"][candidate_key], "candidate_id_to_row_key", candidate_id
    if sku_barcode_key and sku_barcode_key in queue_indexes["sku_barcode"]:
        return queue_indexes["sku_barcode"][sku_barcode_key], "supplier_sku_barcode", f"{supplier_sku}|{barcode}"
    if supplier_sku_key and supplier_sku_key in queue_indexes["sku"]:
        return queue_indexes["sku"][supplier_sku_key], "supplier_sku", supplier_sku
    if barcode_key and barcode_key in queue_indexes["barcode"]:
        return queue_indexes["barcode"][barcode_key], "barcode", barcode
    return None, "", ""


def _select_priority_indices(queue_df: pd.DataFrame, priority_df: pd.DataFrame) -> tuple[list[int], pd.DataFrame]:
    report_rows: list[dict[str, str]] = []
    if queue_df.empty or priority_df.empty:
        return [], pd.DataFrame(columns=["group", "selection_status"])

    queue_indexes = _build_queue_indexes(queue_df)
    selected_indices: list[int] = []
    selected_lookup: set[int] = set()
    for _, row in priority_df.iterrows():
        queue_idx, match_method, match_key = _match_queue_row(row, queue_indexes)
        selection_status = "unmatched"
        matched_row_key = ""
        if queue_idx is not None:
            matched_row_key = _normalize_text(queue_df.iloc[queue_idx].get("row_key", ""))
            if queue_idx in selected_lookup:
                selection_status = "duplicate_match"
            else:
                selection_status = "selected"
                selected_indices.append(queue_idx)
                selected_lookup.add(queue_idx)
        report_rows.append(
            {
                "group": "priority_scrape",
                "candidate_id": _normalize_text(row.get("candidate_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "amazon_link": _amazon_link(_normalize_text(row.get("asin", ""))),
                "selection_status": selection_status,
                "match_method": match_method,
                "match_key": match_key,
                "matched_row_key": matched_row_key,
                "scrape_observed_utc": _normalize_text(row.get("observed_utc", "")),
                "screening_row_status": "",
                "screening_fail_code": "",
            }
        )
    return selected_indices, pd.DataFrame(report_rows)


def _select_processed_exclusions(
    queue_df: pd.DataFrame,
    processed_df: pd.DataFrame,
    *,
    priority_lookup: set[int],
) -> tuple[set[int], pd.DataFrame]:
    report_rows: list[dict[str, str]] = []
    if queue_df.empty or processed_df.empty:
        return set(), pd.DataFrame(columns=["group", "selection_status"])

    queue_indexes = _build_queue_indexes(queue_df)
    excluded_lookup: set[int] = set()
    for _, row in processed_df.iterrows():
        queue_idx, match_method, match_key = _match_queue_row(row, queue_indexes)
        selection_status = "unmatched"
        matched_row_key = ""
        if queue_idx is not None:
            matched_row_key = _normalize_text(queue_df.iloc[queue_idx].get("row_key", ""))
            if queue_idx in priority_lookup:
                selection_status = "priority_reset_override"
            elif queue_idx in excluded_lookup:
                selection_status = "duplicate_exclusion"
            else:
                selection_status = "excluded_known_processed"
                excluded_lookup.add(queue_idx)
        report_rows.append(
            {
                "group": "processed_screening",
                "candidate_id": _normalize_text(row.get("candidate_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "amazon_link": _amazon_link(_normalize_text(row.get("asin", ""))),
                "selection_status": selection_status,
                "match_method": match_method,
                "match_key": match_key,
                "matched_row_key": matched_row_key,
                "scrape_observed_utc": "",
                "screening_row_status": _normalize_text(row.get("row_status", "")),
                "screening_fail_code": _normalize_text(row.get("fail_code", "")),
            }
        )
    return excluded_lookup, pd.DataFrame(report_rows)


def _build_active_run(
    queue_df: pd.DataFrame,
    *,
    supplier_id: str,
    supplier_name: str,
    run_id: str,
) -> pd.DataFrame:
    if queue_df.empty:
        return pd.DataFrame(columns=ACTIVE_RUN_COLUMNS)
    rows: list[dict[str, str]] = []
    for _, row in queue_df.iterrows():
        rows.append(
            {
                "run_id": run_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "row_key": _normalize_text(row.get("row_key", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "barcode": _normalize_text(row.get("barcode", "")),
                "supplier_title": _normalize_text(row.get("supplier_title", "")),
                "unit_cost": _normalize_text(row.get("unit_cost", "")),
                "currency": _normalize_text(row.get("currency", "")),
                "vat_rate": _normalize_text(row.get("vat_rate", "")),
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": _normalize_text(row.get("source_seen_at_utc", "")),
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
    active_run_rows: int,
) -> dict[str, str]:
    next_row_index = "1" if active_run_rows > 0 else "0"
    run_status = "running" if active_run_rows > 0 else "completed"
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
        "total_rows": str(active_run_rows),
        "pending_rows": str(active_run_rows),
        "done_rows": "0",
        "failed_rows": "0",
        "held_rows": "0",
        "next_row_index": next_row_index,
        "updated_at_utc": _utc_now_iso(),
        "completed_at_utc": completed_at,
    }


def _build_pending_screening_row(active_row: pd.Series, *, observed_utc: str) -> dict[str, str]:
    return {
        "observed_utc": observed_utc,
        "run_id": _normalize_text(active_row.get("run_id", "")),
        "supplier_id": _normalize_text(active_row.get("supplier_id", "")),
        "supplier_name": _normalize_text(active_row.get("supplier_name", "")),
        "supplier_sku": _normalize_text(active_row.get("supplier_sku", "")),
        "barcode": _normalize_text(active_row.get("barcode", "")),
        "candidate_id": _normalize_text(active_row.get("row_key", "")),
        "asin": "",
        "row_status": "pending",
        "last_stage": "start",
        "fail_code": "",
        "attempt_count": "0",
        "timeout_until_utc": "",
        "mode": "screening",
        "updated_at_utc": observed_utc,
        "source_seen_at_utc": _normalize_text(active_row.get("source_seen_at_utc", "")),
        "pf": "",
        "status_reason": "",
        "recommendation_status": "",
        "recommended_test_qty": "",
    }


def _rebuild_supplier_screening_state(
    existing_screening_df: pd.DataFrame,
    *,
    supplier_id: str,
    queue_df: pd.DataFrame,
    observed_utc: str,
) -> pd.DataFrame:
    supplier_key = _normalize_lower(supplier_id)
    queue_indexes = _build_queue_indexes(queue_df)
    retained_rows: list[dict[str, str]] = []
    if not existing_screening_df.empty:
        work = existing_screening_df[existing_screening_df.get("supplier_id", "").map(_normalize_lower) == supplier_key].copy()
        if not work.empty:
            work = work[work.get("row_status", "").map(_normalize_lower).isin(PROCESSED_SCREENING_STATUSES)].copy()
            for _, row in work.iterrows():
                queue_idx, _, _ = _match_queue_row(row, queue_indexes)
                if queue_idx is None:
                    retained_rows.append({column: _normalize_text(row.get(column, "")) for column in _contract_columns("f_screening_row_state_live")})
                    continue

    pending_rows = [_build_pending_screening_row(row, observed_utc=observed_utc) for _, row in queue_df.iterrows()]
    ordered_rows: list[dict[str, str]] = []
    seen_candidate_ids: set[str] = set()
    for payload in retained_rows + pending_rows:
        candidate_id = _normalize_key(payload.get("candidate_id", ""))
        if candidate_id == "" or candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate_id)
        ordered_rows.append(payload)

    if not ordered_rows:
        return _empty_contract_df("f_screening_row_state_live")
    return pd.DataFrame(ordered_rows)


def _archive_paths(root_path: Path, archive_dir: Path, paths: Iterable[Path]) -> list[str]:
    archived_rel_paths: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        rel = path.relative_to(root_path)
        dest = archive_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        archived_rel_paths.append(str(rel))
    return archived_rel_paths


def _empty_like_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.head(0).copy()


def _filter_contract_rows_for_supplier(df: pd.DataFrame, *, supplier_id: str, supplier_name: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    supplier_id_key = _normalize_lower(supplier_id)
    supplier_name_key = _normalize_lower(supplier_name)
    filters: list[pd.Series] = []

    if "supplier_id" in out.columns:
        filters.append(out["supplier_id"].map(_normalize_lower) != supplier_id_key)
    if "supplier_code" in out.columns:
        filters.append(out["supplier_code"].map(_normalize_lower) != supplier_id_key)
    if "supplier_name" in out.columns:
        filters.append(out["supplier_name"].map(_normalize_lower) != supplier_name_key)
    if "supplier" in out.columns:
        filters.append(out["supplier"].map(_normalize_lower) != supplier_name_key)

    if not filters:
        return _empty_like_df(out)
    keep_mask = filters[0]
    for mask in filters[1:]:
        keep_mask = keep_mask & mask
    return out[keep_mask].copy()


def reset_webscrape_coverage_queue(
    *,
    root: Path | None = None,
    supplier_id: str,
    apply_changes: bool = False,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    archive_dir: Path | None = None,
    queue_order: str = QUEUE_ORDER_PRIORITY_FIRST,
) -> ResetWebscrapeCoverageResult:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    queue_order_clean = _normalize_lower(queue_order) or QUEUE_ORDER_PRIORITY_FIRST
    if queue_order_clean not in QUEUE_ORDER_ALLOWED:
        raise ValueError(
            f"queue_order must be one of {sorted(QUEUE_ORDER_ALLOWED)}; got {queue_order}"
        )

    supplier_config = _load_supplier_config(root_path, supplier_id)
    supplier_id_clean = _normalize_text(supplier_config.get("supplier_id", "")) or _normalize_text(supplier_id)
    supplier_name = _normalize_text(supplier_config.get("supplier_name", ""))
    source_url = _normalize_text(supplier_config.get("source_url", ""))
    supplier_key = _normalize_lower(supplier_id_clean)
    observed_utc = _utc_now_iso()
    ts_slug = _timestamp_slug()

    scrape_df = _read_contract_df("feeder_legacy_scrape_evidence_live", root_path)
    screening_df = _read_contract_df("f_screening_row_state_live", root_path)
    active_contract_df = _read_contract_df("supplier_price_list_active_run", root_path)
    run_state_contract_df = _read_contract_df("supplier_price_list_run_state", root_path)
    canonical_path = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id_clean / "canonical_current.csv"
    canonical_df = _read_csv(canonical_path)
    canonical_queue = _queue_from_canonical(canonical_df, supplier_id=supplier_id_clean, supplier_name=supplier_name)

    latest_scrape = _latest_scrape_rows(scrape_df, supplier_id=supplier_id_clean)
    processed_screening = _latest_processed_screening_rows(screening_df, supplier_id=supplier_id_clean)

    priority_indices, priority_report = _select_priority_indices(canonical_queue, latest_scrape)
    priority_lookup = set(priority_indices)
    excluded_lookup, exclusion_report = _select_processed_exclusions(
        canonical_queue,
        processed_screening,
        priority_lookup=priority_lookup,
    )

    remaining_indices = [idx for idx in range(len(canonical_queue)) if idx not in priority_lookup and idx not in excluded_lookup]
    if queue_order_clean == QUEUE_ORDER_REMAINING_FIRST:
        queue_order_indices = remaining_indices + priority_indices
    else:
        queue_order_indices = priority_indices + remaining_indices
    final_queue = canonical_queue.iloc[queue_order_indices].copy().reset_index(drop=True) if queue_order_indices else canonical_queue.head(0).copy()

    report_df = pd.concat([priority_report, exclusion_report], ignore_index=True)
    if report_df.empty:
        report_df = pd.DataFrame(
            columns=[
                "group",
                "candidate_id",
                "supplier_sku",
                "barcode",
                "asin",
                "amazon_link",
                "selection_status",
                "match_method",
                "match_key",
                "matched_row_key",
                "scrape_observed_utc",
                "screening_row_status",
                "screening_fail_code",
            ]
        )
    report_df.insert(0, "observed_utc", observed_utc)
    report_df.insert(1, "supplier_id", supplier_id_clean)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"f_webscrape_reset_plan_{ts_slug}.csv"
    latest_path = output_dir / "f_webscrape_reset_plan_latest.csv"
    report_df.to_csv(report_path, index=False)
    report_df.to_csv(latest_path, index=False)

    run_id = f"{supplier_id_clean}_webscrape_reset_{ts_slug}"
    supplier_active = _build_active_run(final_queue, supplier_id=supplier_id_clean, supplier_name=supplier_name, run_id=run_id)
    source_file_candidates = [
        _normalize_text(value)
        for value in final_queue.get("source_file_path", pd.Series(dtype=str)).tolist()
        if _normalize_text(value) != ""
    ]
    source_file_path = source_file_candidates[0] if source_file_candidates else str(canonical_path)
    source_seen_candidates = [
        _normalize_text(value)
        for value in supplier_active.get("source_seen_at_utc", pd.Series(dtype=str)).tolist()
        if _normalize_text(value) != ""
    ]
    source_seen_at_utc = source_seen_candidates[0] if source_seen_candidates else observed_utc
    run_state_row = _build_run_state(
        supplier_id=supplier_id_clean,
        supplier_name=supplier_name,
        run_id=run_id,
        source_url=source_url,
        source_file_path=source_file_path,
        source_seen_at_utc=source_seen_at_utc,
        normalized_utc=observed_utc,
        active_run_rows=int(len(supplier_active)),
    )
    rebuilt_screening_supplier = _rebuild_supplier_screening_state(
        screening_df,
        supplier_id=supplier_id_clean,
        queue_df=supplier_active,
        observed_utc=observed_utc,
    )
    summary: dict[str, object] = {
        "status": "success",
        "observed_utc": observed_utc,
        "supplier_id": supplier_id_clean,
        "supplier_name": supplier_name,
        "canonical_rows": int(len(canonical_queue)),
        "scrape_rows_latest_supplier": int(len(latest_scrape)),
        "processed_screening_rows_latest": int(len(processed_screening)),
        "priority_rows_selected": int(len(priority_indices)),
        "priority_rows_unmatched": int(len(priority_report[priority_report["selection_status"] == "unmatched"])),
        "processed_rows_excluded_from_remainder": int(len(excluded_lookup)),
        "queue_rows_final": int(len(final_queue)),
        "queue_rows_priority": int(len(priority_indices)),
        "queue_rows_remaining": int(len(remaining_indices)),
        "queue_order": queue_order_clean,
        "screening_rows_rebuilt_supplier": int(len(rebuilt_screening_supplier)),
        "applied": bool(apply_changes),
        "report_path": str(report_path),
        "latest_path": str(latest_path),
        "archive_dir": "",
        "restore_command": f"python scripts/flows/F/F062_reset_supplier_test_mode.py --supplier-id {supplier_id_clean} --no-clear-review-live",
    }

    if not apply_changes:
        print(json.dumps(summary))
        return ResetWebscrapeCoverageResult(
            report_df=report_df,
            report_path=report_path,
            latest_path=latest_path,
            summary=summary,
        )

    archive_root = archive_dir or (root_path / "out" / "systems" / "F" / "history" / "webscrape_resets" / ts_slug)
    archive_root.mkdir(parents=True, exist_ok=True)
    supplier_dir = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id_clean
    supplier_dir.mkdir(parents=True, exist_ok=True)

    archive_paths = [
        root_path / get_f_output_contract("supplier_price_list_active_run").rel_path,
        root_path / get_f_output_contract("supplier_price_list_run_state").rel_path,
        root_path / get_f_output_contract("supplier_price_list_queue_state").rel_path,
        root_path / get_f_output_contract("f_screening_row_state_live").rel_path,
        supplier_dir / "active_run.csv",
        supplier_dir / "run_state.csv",
    ]
    archive_paths.extend(root_path / get_f_output_contract(name).rel_path for name in CLEAR_CONTRACTS)
    archived_rel_paths = _archive_paths(root_path, archive_root, archive_paths)

    active_without_supplier = active_contract_df[
        active_contract_df.get("supplier_id", "").map(_normalize_lower) != supplier_key
    ].copy()
    active_updated = pd.concat([active_without_supplier, supplier_active], ignore_index=True)
    active_written = _write_contract_df(active_updated, "supplier_price_list_active_run", root_path)
    _write_csv(supplier_dir / "active_run.csv", supplier_active, ACTIVE_RUN_COLUMNS)

    run_state_without_supplier = run_state_contract_df[
        run_state_contract_df.get("supplier_id", "").map(_normalize_lower) != supplier_key
    ].copy()
    run_state_written = pd.concat([run_state_without_supplier, pd.DataFrame([run_state_row])], ignore_index=True)
    _write_contract_df(run_state_written, "supplier_price_list_run_state", root_path)
    _write_csv(supplier_dir / "run_state.csv", pd.DataFrame([run_state_row]), RUN_STATE_COLUMNS)

    queue_state = pd.DataFrame(
        [
            {
                "queue_id": "default",
                "current_supplier_id": supplier_id_clean,
                "current_run_id": run_id,
                "last_completed_supplier_id": "",
                "next_supplier_id": "",
                "queue_index": "0",
                "status": "ok",
                "updated_at_utc": observed_utc,
                "notes": f"webscrape_coverage_reset_{queue_order_clean.replace('-', '_')}",
            }
        ]
    )
    _write_contract_df(queue_state, "supplier_price_list_queue_state", root_path)

    screening_other = screening_df[screening_df.get("supplier_id", "").map(_normalize_lower) != supplier_key].copy()
    screening_updated = pd.concat([screening_other, rebuilt_screening_supplier], ignore_index=True)
    screening_written = _write_contract_df(screening_updated, "f_screening_row_state_live", root_path)

    cleared_counts: dict[str, int] = {}
    for contract_name in CLEAR_CONTRACTS:
        contract_df = _read_contract_df(contract_name, root_path)
        if contract_name in {"feeder_backtest_replay_daily_live", "feeder_backtest_summary_live", "feeder_backtest_health", "feeder_legacy_sheet_health"}:
            cleared_df = _empty_contract_df(contract_name)
        else:
            cleared_df = _filter_contract_rows_for_supplier(
                contract_df,
                supplier_id=supplier_id_clean,
                supplier_name=supplier_name,
            )
            if cleared_df.empty:
                cleared_df = _empty_contract_df(contract_name)
        cleared_written = _write_contract_df(cleared_df, contract_name, root_path)
        cleared_counts[contract_name] = int(len(cleared_written))

    summary.update(
        {
            "applied": True,
            "archive_dir": str(archive_root),
            "archived_paths": archived_rel_paths,
            "active_supplier_rows_after": int(
                len(active_written[active_written.get("supplier_id", "").map(_normalize_lower) == supplier_key])
            ),
            "run_state_rows_after": int(
                len(run_state_written[run_state_written.get("supplier_id", "").map(_normalize_lower) == supplier_key])
            ),
            "screening_rows_supplier_after": int(
                len(screening_written[screening_written.get("supplier_id", "").map(_normalize_lower) == supplier_key])
            ),
            "cleared_contract_rows_after": cleared_counts,
        }
    )

    print(json.dumps(summary))
    return ResetWebscrapeCoverageResult(
        report_df=report_df,
        report_path=report_path,
        latest_path=latest_path,
        summary=summary,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Archive stale F webscrape outputs, clear old scrape/backtest state, and rebuild the next queue so "
            "previously scraped rows run first before the remaining unscreened supplier rows."
        )
    )
    parser.add_argument("--supplier-id", required=True, help="Supplier ID to reset and reprioritize.")
    parser.add_argument("--apply", action="store_true", help="Write the reset into the live F contracts.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for the reset report CSV.")
    parser.add_argument(
        "--archive-dir",
        default="",
        help="Optional override for the archive directory. Defaults to out/systems/F/history/webscrape_resets/<timestamp>/",
    )
    parser.add_argument(
        "--queue-order",
        default=QUEUE_ORDER_PRIORITY_FIRST,
        choices=sorted(QUEUE_ORDER_ALLOWED),
        help=(
            "Queue ordering. priority-first preserves the recovery default; "
            "remaining-first scans unprocessed supplier rows before rescraping prior evidence."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    reset_webscrape_coverage_queue(
        supplier_id=args.supplier_id,
        apply_changes=bool(args.apply),
        output_dir=Path(args.output_dir),
        archive_dir=Path(args.archive_dir) if args.archive_dir else None,
        queue_order=args.queue_order,
    )
