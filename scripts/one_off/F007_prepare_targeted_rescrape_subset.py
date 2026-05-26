from __future__ import annotations

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
DEFAULT_HF_ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"

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
class TargetedRescrapeSubsetResult:
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


def _read_alignment_missing_asins(path: Path) -> tuple[set[str], int]:
    alignment = _read_csv(path)
    if alignment.empty or "asin" not in alignment.columns:
        return set(), 0

    asin_series = alignment["asin"].map(_normalize_text)
    if "expected_units_source" in alignment.columns:
        source_series = alignment["expected_units_source"].map(_normalize_text)
    else:
        source_series = pd.Series([""] * len(alignment.index), index=alignment.index, dtype=str)

    mask = (asin_series != "") & source_series.isin({"", "no_source"})
    if not mask.any():
        return set(), 0

    asin_keys = set(asin_series[mask].map(_normalize_key).tolist())
    return asin_keys, int(mask.sum())


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


def _contract_columns(contract_name: str) -> list[str]:
    contract = get_f_output_contract(contract_name)
    return [*contract.required_columns, *contract.optional_columns]


def _read_contract_df(contract_name: str, root_path: Path) -> pd.DataFrame:
    path = root_path / get_f_output_contract(contract_name).rel_path
    if not path.exists():
        return pd.DataFrame(columns=_contract_columns(contract_name))
    return pd.read_csv(path, dtype=str).fillna("")


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
    work = scrape_df.copy()
    work = work[work.get("supplier_id", "").map(_normalize_lower) == supplier_key].copy()
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
    return work.drop(columns=["_observed_ts", "_dedupe_key"], errors="ignore").reset_index(drop=True)


def _missing_basis_rows(latest_scrape_df: pd.DataFrame) -> pd.DataFrame:
    if latest_scrape_df.empty:
        return latest_scrape_df
    work = latest_scrape_df.copy()
    asin = work.get("asin", "").map(_normalize_text)
    last_completed = work.get("bbp_sales_last_completed_month_label", "").map(_normalize_text)
    replay_source = work.get("bbp_sales_replay_demand_basis_source", "").map(_normalize_text)
    mask = (asin != "") & (last_completed == "") & (replay_source == "")
    out = work[mask].copy()
    if out.empty:
        return out
    out["rescrape_reason"] = "missing_bbp_demand_basis"
    out["_sort_ts"] = pd.to_datetime(out.get("observed_utc", "").map(_normalize_text), errors="coerce")
    out = out.sort_values("_sort_ts", ascending=False, kind="stable").drop(columns=["_sort_ts"], errors="ignore")
    return out.reset_index(drop=True)


def _missing_core_price_history_rows(latest_scrape_df: pd.DataFrame) -> pd.DataFrame:
    if latest_scrape_df.empty:
        return latest_scrape_df
    work = latest_scrape_df.copy()
    asin = work.get("asin", "").map(_normalize_text)
    scrape_attempted = work.get("scrape_attempted", "").map(_normalize_text).str.lower()
    price_points = pd.to_numeric(work.get("price_history_points_365d", "").map(_normalize_text), errors="coerce").fillna(0)
    price_series_cols = [
        "chart_price_daily_series",
        "chart_raw_amazon_daily_series",
        "chart_raw_fba_daily_series",
        "chart_raw_fbm_daily_series",
        "chart_raw_buy_box_daily_series",
    ]
    has_any_price_series = pd.Series(False, index=work.index)
    for column in price_series_cols:
        has_any_price_series = has_any_price_series | (work.get(column, "").map(_normalize_text) != "")
    mask = (asin != "") & (scrape_attempted == "true") & (price_points <= 0) & (~has_any_price_series)
    out = work[mask].copy()
    if out.empty:
        return out
    out["rescrape_reason"] = "missing_core_price_history"
    out["_sort_ts"] = pd.to_datetime(out.get("observed_utc", "").map(_normalize_text), errors="coerce")
    out = out.sort_values("_sort_ts", ascending=False, kind="stable").drop(columns=["_sort_ts"], errors="ignore")
    return out.reset_index(drop=True)


def _technical_rescrape_rows(latest_scrape_df: pd.DataFrame) -> pd.DataFrame:
    if latest_scrape_df.empty:
        return latest_scrape_df
    work = latest_scrape_df.copy()
    asin = work.get("asin", "").map(_normalize_text)
    scrape_attempted = work.get("scrape_attempted", "").map(_normalize_text).str.lower()
    scrape_success = work.get("scrape_success", "").map(_normalize_text).str.lower()
    mask = (asin != "") & (scrape_attempted == "true") & (scrape_success != "true")
    out = work[mask].copy()
    if out.empty:
        return out
    out["rescrape_reason"] = "scrape_not_successful"
    out["_sort_ts"] = pd.to_datetime(out.get("observed_utc", "").map(_normalize_text), errors="coerce")
    out = out.sort_values("_sort_ts", ascending=False, kind="stable").drop(columns=["_sort_ts"], errors="ignore")
    return out.reset_index(drop=True)


def _alignment_missing_baseline_rows(latest_scrape_df: pd.DataFrame, alignment_missing_asins: set[str]) -> pd.DataFrame:
    if latest_scrape_df.empty or not alignment_missing_asins:
        return latest_scrape_df.head(0).copy()

    work = latest_scrape_df.copy()
    asin_text = work.get("asin", "").map(_normalize_text)
    asin_key = asin_text.map(_normalize_key)
    mask = (asin_text != "") & asin_key.isin(alignment_missing_asins)
    out = work[mask].copy()
    if out.empty:
        return out
    out["rescrape_reason"] = "alignment_missing_expected_baseline"
    out["_sort_ts"] = pd.to_datetime(out.get("observed_utc", "").map(_normalize_text), errors="coerce")
    out = out.sort_values("_sort_ts", ascending=False, kind="stable").drop(columns=["_sort_ts"], errors="ignore")
    return out.reset_index(drop=True)


def _targeted_rescrape_rows(
    latest_scrape_df: pd.DataFrame,
    *,
    alignment_missing_asins: set[str] | None = None,
) -> pd.DataFrame:
    frames = [
        _missing_basis_rows(latest_scrape_df),
        _missing_core_price_history_rows(latest_scrape_df),
        _technical_rescrape_rows(latest_scrape_df),
        _alignment_missing_baseline_rows(latest_scrape_df, alignment_missing_asins or set()),
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return latest_scrape_df.head(0).copy()

    combined = pd.concat(frames, ignore_index=True)
    key_series = combined.get("candidate_id", "").map(_normalize_key)
    fallback_key = (
        combined.get("supplier_sku", "").map(_normalize_key)
        + "|"
        + combined.get("barcode", "").map(_normalize_key)
        + "|"
        + combined.get("asin", "").map(_normalize_key)
    )
    combined["_dedupe_key"] = key_series
    combined.loc[combined["_dedupe_key"] == "", "_dedupe_key"] = fallback_key
    combined["_sort_ts"] = pd.to_datetime(combined.get("observed_utc", "").map(_normalize_text), errors="coerce")
    combined = combined.sort_values(["_sort_ts", "_dedupe_key"], ascending=[False, True], kind="stable")

    reason_by_key: dict[str, list[str]] = {}
    first_rows: dict[str, dict[str, str]] = {}
    for _, row in combined.iterrows():
        dedupe_key = _normalize_text(row.get("_dedupe_key", ""))
        if dedupe_key == "":
            continue
        reason = _normalize_text(row.get("rescrape_reason", ""))
        if dedupe_key not in reason_by_key:
            reason_by_key[dedupe_key] = []
        if reason and reason not in reason_by_key[dedupe_key]:
            reason_by_key[dedupe_key].append(reason)
        if dedupe_key not in first_rows:
            first_rows[dedupe_key] = {col: _normalize_text(row.get(col, "")) for col in combined.columns}

    rows: list[dict[str, str]] = []
    for dedupe_key, payload in first_rows.items():
        reasons = reason_by_key.get(dedupe_key, [])
        payload["rescrape_reason"] = "|".join(reasons)
        rows.append(payload)

    out = pd.DataFrame(rows)
    return out.drop(columns=["_dedupe_key", "_sort_ts"], errors="ignore").reset_index(drop=True)


def _queue_from_active(active_df: pd.DataFrame, *, supplier_id: str) -> pd.DataFrame:
    if active_df.empty:
        return pd.DataFrame()
    supplier_key = _normalize_lower(supplier_id)
    work = active_df[active_df.get("supplier_id", "").map(_normalize_lower) == supplier_key].copy()
    if work.empty:
        return work
    work["row_key"] = work.get("row_key", "").map(_normalize_text)
    work["supplier_sku"] = work.get("supplier_sku", "").map(_normalize_text)
    work["barcode"] = work.get("barcode", "").map(_normalize_text)
    work["source_file_path"] = ""
    return work.reset_index(drop=True)


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


def _match_candidates(queue_df: pd.DataFrame, missing_df: pd.DataFrame) -> tuple[int, list[dict[str, str]]]:
    if queue_df.empty or missing_df.empty:
        return 0, []

    by_row_key: dict[str, int] = {}
    by_sku_barcode: dict[str, int] = {}
    by_sku: dict[str, int] = {}
    by_barcode: dict[str, int] = {}
    for idx, row in queue_df.iterrows():
        row_key = _normalize_key(row.get("row_key", ""))
        sku = _normalize_key(row.get("supplier_sku", ""))
        barcode = _normalize_key(row.get("barcode", ""))
        sku_barcode = f"{sku}|{barcode}" if (sku or barcode) else ""
        if row_key and row_key not in by_row_key:
            by_row_key[row_key] = int(idx)
        if sku_barcode and sku_barcode not in by_sku_barcode:
            by_sku_barcode[sku_barcode] = int(idx)
        if sku and sku not in by_sku:
            by_sku[sku] = int(idx)
        if barcode and barcode not in by_barcode:
            by_barcode[barcode] = int(idx)

    matched = 0
    report_rows: list[dict[str, str]] = []
    for _, row in missing_df.iterrows():
        supplier_sku = _normalize_text(row.get("supplier_sku", ""))
        barcode = _normalize_text(row.get("barcode", ""))
        candidate_id = _normalize_text(row.get("candidate_id", ""))
        asin = _normalize_text(row.get("asin", ""))
        sku_key = _normalize_key(supplier_sku)
        barcode_key = _normalize_key(barcode)
        sku_barcode_key = f"{sku_key}|{barcode_key}" if (sku_key or barcode_key) else ""
        candidate_key = _normalize_key(candidate_id)

        match_method = ""
        match_key = ""
        if candidate_key and candidate_key in by_row_key:
            matched += 1
            match_method = "candidate_id_to_row_key"
            match_key = candidate_id
        elif sku_barcode_key and sku_barcode_key in by_sku_barcode:
            matched += 1
            match_method = "supplier_sku_barcode"
            match_key = f"{supplier_sku}|{barcode}"
        elif sku_key and sku_key in by_sku:
            matched += 1
            match_method = "supplier_sku"
            match_key = supplier_sku
        elif barcode_key and barcode_key in by_barcode:
            matched += 1
            match_method = "barcode"
            match_key = barcode

        report_rows.append(
            {
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "barcode": barcode,
                "asin": asin,
                "amazon_link": _amazon_link(asin),
                "rescrape_reason": _normalize_text(row.get("rescrape_reason", "")),
                "selection_status": "matchable" if match_method else "unmatched",
                "match_method": match_method,
                "match_key": match_key,
                "scrape_observed_utc": _normalize_text(row.get("observed_utc", "")),
            }
        )
    return matched, report_rows


def _select_subset_rows(
    queue_df: pd.DataFrame,
    missing_df: pd.DataFrame,
    *,
    max_rows: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if queue_df.empty or missing_df.empty:
        report_cols = [
            "candidate_id",
            "supplier_sku",
            "barcode",
            "asin",
            "amazon_link",
            "rescrape_reason",
            "selection_status",
            "match_method",
            "match_key",
            "matched_row_key",
            "scrape_observed_utc",
        ]
        return pd.DataFrame(columns=queue_df.columns), pd.DataFrame(columns=report_cols)

    by_row_key: dict[str, int] = {}
    by_sku_barcode: dict[str, int] = {}
    by_sku: dict[str, int] = {}
    by_barcode: dict[str, int] = {}
    for idx, row in queue_df.iterrows():
        row_key = _normalize_key(row.get("row_key", ""))
        sku = _normalize_key(row.get("supplier_sku", ""))
        barcode = _normalize_key(row.get("barcode", ""))
        sku_barcode = f"{sku}|{barcode}" if (sku or barcode) else ""
        if row_key and row_key not in by_row_key:
            by_row_key[row_key] = int(idx)
        if sku_barcode and sku_barcode not in by_sku_barcode:
            by_sku_barcode[sku_barcode] = int(idx)
        if sku and sku not in by_sku:
            by_sku[sku] = int(idx)
        if barcode and barcode not in by_barcode:
            by_barcode[barcode] = int(idx)

    selected_indices: list[int] = []
    selected_lookup: set[int] = set()
    report_rows: list[dict[str, str]] = []
    row_limit = max(max_rows, 0)
    for _, row in missing_df.iterrows():
        supplier_sku = _normalize_text(row.get("supplier_sku", ""))
        barcode = _normalize_text(row.get("barcode", ""))
        candidate_id = _normalize_text(row.get("candidate_id", ""))
        asin = _normalize_text(row.get("asin", ""))
        sku_key = _normalize_key(supplier_sku)
        barcode_key = _normalize_key(barcode)
        sku_barcode_key = f"{sku_key}|{barcode_key}" if (sku_key or barcode_key) else ""
        candidate_key = _normalize_key(candidate_id)

        queue_idx: int | None = None
        match_method = ""
        match_key = ""

        if candidate_key and candidate_key in by_row_key:
            queue_idx = by_row_key[candidate_key]
            match_method = "candidate_id_to_row_key"
            match_key = candidate_id
        elif sku_barcode_key and sku_barcode_key in by_sku_barcode:
            queue_idx = by_sku_barcode[sku_barcode_key]
            match_method = "supplier_sku_barcode"
            match_key = f"{supplier_sku}|{barcode}"
        elif sku_key and sku_key in by_sku:
            queue_idx = by_sku[sku_key]
            match_method = "supplier_sku"
            match_key = supplier_sku
        elif barcode_key and barcode_key in by_barcode:
            queue_idx = by_barcode[barcode_key]
            match_method = "barcode"
            match_key = barcode

        selection_status = "unmatched"
        matched_row_key = ""
        if queue_idx is not None:
            matched_row_key = _normalize_text(queue_df.iloc[queue_idx].get("row_key", ""))
            if queue_idx in selected_lookup:
                selection_status = "duplicate_match"
            elif row_limit > 0 and len(selected_indices) >= row_limit:
                selection_status = "capped_by_max_rows"
            else:
                selected_indices.append(queue_idx)
                selected_lookup.add(queue_idx)
                selection_status = "selected"

        report_rows.append(
            {
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "barcode": barcode,
                "asin": asin,
                "amazon_link": _amazon_link(asin),
                "rescrape_reason": _normalize_text(row.get("rescrape_reason", "")),
                "selection_status": selection_status,
                "match_method": match_method,
                "match_key": match_key,
                "matched_row_key": matched_row_key,
                "scrape_observed_utc": _normalize_text(row.get("observed_utc", "")),
            }
        )

    subset_df = queue_df.iloc[selected_indices].copy().reset_index(drop=True) if selected_indices else queue_df.head(0).copy()
    report_df = pd.DataFrame(report_rows)
    return subset_df, report_df


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


def _create_backup(
    *,
    root_path: Path,
    supplier_id: str,
    backup_dir_override: Path | None,
) -> Path:
    timestamp = _timestamp_slug()
    supplier_dir = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id
    backup_dir = backup_dir_override or (supplier_dir / "rescrape_subset_backups" / timestamp)
    backup_dir.mkdir(parents=True, exist_ok=True)

    files = [
        root_path / get_f_output_contract("supplier_price_list_active_run").rel_path,
        root_path / get_f_output_contract("supplier_price_list_run_state").rel_path,
        root_path / get_f_output_contract("supplier_price_list_queue_state").rel_path,
        supplier_dir / "active_run.csv",
        supplier_dir / "run_state.csv",
    ]
    for src in files:
        if not src.exists():
            continue
        rel = src.relative_to(root_path)
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return backup_dir


def prepare_targeted_rescrape_subset(
    *,
    root: Path | None = None,
    supplier_id: str,
    queue_source: str = "auto",
    apply_changes: bool = False,
    max_rows: int = 0,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    backup_dir: Path | None = None,
    include_alignment_missing: bool = False,
    alignment_missing_path: Path = DEFAULT_HF_ALIGNMENT_PATH,
) -> TargetedRescrapeSubsetResult:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)

    supplier_config = _load_supplier_config(root_path, supplier_id)
    supplier_id_clean = _normalize_text(supplier_config.get("supplier_id", "")) or _normalize_text(supplier_id)
    supplier_name = _normalize_text(supplier_config.get("supplier_name", ""))
    source_url = _normalize_text(supplier_config.get("source_url", ""))
    supplier_key = _normalize_lower(supplier_id_clean)

    scrape_df = _read_contract_df("feeder_legacy_scrape_evidence_live", root_path)
    latest_scrape = _latest_scrape_rows(scrape_df, supplier_id=supplier_id_clean)

    alignment_missing_path_resolved = Path(alignment_missing_path)
    if not alignment_missing_path_resolved.is_absolute():
        alignment_missing_path_resolved = root_path / alignment_missing_path_resolved
    alignment_missing_asins: set[str] = set()
    alignment_missing_rows = 0
    if include_alignment_missing:
        alignment_missing_asins, alignment_missing_rows = _read_alignment_missing_asins(alignment_missing_path_resolved)

    missing_df = _targeted_rescrape_rows(latest_scrape, alignment_missing_asins=alignment_missing_asins)

    active_contract_df = _read_contract_df("supplier_price_list_active_run", root_path)
    active_queue = _queue_from_active(active_contract_df, supplier_id=supplier_id_clean)

    canonical_path = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id_clean / "canonical_current.csv"
    canonical_df = _read_csv(canonical_path)
    canonical_queue = _queue_from_canonical(canonical_df, supplier_id=supplier_id_clean, supplier_name=supplier_name)

    queue_source_norm = _normalize_lower(queue_source)
    if queue_source_norm not in {"auto", "active_run", "canonical_current"}:
        raise ValueError("queue_source must be one of: auto, active_run, canonical_current")

    active_matchable, _ = _match_candidates(active_queue, missing_df)
    canonical_matchable, _ = _match_candidates(canonical_queue, missing_df)

    queue_source_used = queue_source_norm
    selected_queue = active_queue
    if queue_source_norm == "active_run":
        selected_queue = active_queue
    elif queue_source_norm == "canonical_current":
        selected_queue = canonical_queue
    else:
        if canonical_matchable > active_matchable:
            queue_source_used = "canonical_current"
            selected_queue = canonical_queue
        else:
            queue_source_used = "active_run"
            selected_queue = active_queue

    subset_df, report_df = _select_subset_rows(selected_queue, missing_df, max_rows=max_rows)
    snapshot_utc = _utc_now_iso()
    ts_slug = _timestamp_slug()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"f_targeted_rescrape_subset_{ts_slug}.csv"
    latest_path = output_dir / "f_targeted_rescrape_subset_latest.csv"
    report_df = report_df.copy()
    if report_df.empty:
        report_df = pd.DataFrame(
            columns=[
                "candidate_id",
                "supplier_sku",
                "barcode",
                "asin",
                "amazon_link",
                "rescrape_reason",
                "selection_status",
                "match_method",
                "match_key",
                "matched_row_key",
                "scrape_observed_utc",
            ]
        )
    report_df.insert(0, "observed_utc", snapshot_utc)
    report_df.insert(1, "supplier_id", supplier_id_clean)
    report_df.insert(2, "queue_source_used", queue_source_used)
    report_df.to_csv(report_path, index=False)
    report_df.to_csv(latest_path, index=False)

    active_supplier_before = int(
        len(active_contract_df[active_contract_df.get("supplier_id", "").map(_normalize_lower) == supplier_key])
    )
    active_total_before = int(len(active_contract_df))

    active_supplier_after = active_supplier_before
    active_total_after = active_total_before
    backup_path = None
    run_id = f"{supplier_id_clean}_rescrape_subset_{ts_slug}"
    if apply_changes:
        backup_path = _create_backup(root_path=root_path, supplier_id=supplier_id_clean, backup_dir_override=backup_dir)
        subset_active = subset_df.copy()
        for column in ACTIVE_RUN_COLUMNS:
            if column not in subset_active.columns:
                subset_active[column] = ""
        subset_active["run_id"] = run_id
        subset_active["supplier_id"] = supplier_id_clean
        subset_active["supplier_name"] = supplier_name
        subset_active["scan_status"] = "pending"
        subset_active["scan_reason"] = ""
        subset_active["attempt_count"] = "0"
        subset_active["last_attempt_utc"] = ""
        subset_active["finished_utc"] = ""
        subset_active = subset_active[ACTIVE_RUN_COLUMNS].copy()

        active_without_supplier = active_contract_df[
            active_contract_df.get("supplier_id", "").map(_normalize_lower) != supplier_key
        ].copy()
        active_updated = pd.concat([active_without_supplier, subset_active], ignore_index=True)
        active_written = _write_contract_df(active_updated, "supplier_price_list_active_run", root_path)

        supplier_dir = root_path / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id_clean
        _write_csv(supplier_dir / "active_run.csv", subset_active, ACTIVE_RUN_COLUMNS)

        source_file_candidates = [
            _normalize_text(value)
            for value in subset_df.get("source_file_path", pd.Series(dtype=str)).tolist()
            if _normalize_text(value) != ""
        ]
        source_file_path = source_file_candidates[0] if source_file_candidates else str(canonical_path)
        source_seen_candidates = [
            _normalize_text(value)
            for value in subset_active.get("source_seen_at_utc", pd.Series(dtype=str)).tolist()
            if _normalize_text(value) != ""
        ]
        source_seen_at_utc = source_seen_candidates[0] if source_seen_candidates else snapshot_utc
        run_state_row = _build_run_state(
            supplier_id=supplier_id_clean,
            supplier_name=supplier_name,
            run_id=run_id,
            source_url=source_url,
            source_file_path=source_file_path,
            source_seen_at_utc=source_seen_at_utc,
            normalized_utc=snapshot_utc,
            active_run_rows=int(len(subset_active)),
        )
        run_state_contract_df = _read_contract_df("supplier_price_list_run_state", root_path)
        run_state_contract_df = run_state_contract_df[
            run_state_contract_df.get("supplier_id", "").map(_normalize_lower) != supplier_key
        ].copy()
        run_state_contract_df = pd.concat([run_state_contract_df, pd.DataFrame([run_state_row])], ignore_index=True)
        _write_contract_df(run_state_contract_df, "supplier_price_list_run_state", root_path)
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
                    "updated_at_utc": snapshot_utc,
                    "notes": f"targeted_rescrape_subset_from_{queue_source_used}",
                }
            ]
        )
        _write_contract_df(queue_state, "supplier_price_list_queue_state", root_path)
        active_supplier_after = int(
            len(active_written[active_written.get("supplier_id", "").map(_normalize_lower) == supplier_key])
        )
        active_total_after = int(len(active_written))

    selection_counts = report_df["selection_status"].map(_normalize_text).value_counts().to_dict()
    reason_counts: dict[str, int] = {}
    if not report_df.empty and "rescrape_reason" in report_df.columns:
        for value in report_df["rescrape_reason"].map(_normalize_text):
            if value == "":
                continue
            for reason in value.split("|"):
                reason_key = _normalize_text(reason)
                if reason_key == "":
                    continue
                reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1
    summary = {
        "status": "success",
        "observed_utc": snapshot_utc,
        "supplier_id": supplier_id_clean,
        "supplier_name": supplier_name,
        "queue_source_used": queue_source_used,
        "queue_source_requested": queue_source_norm,
        "queue_rows_active_run": int(len(active_queue)),
        "queue_rows_canonical_current": int(len(canonical_queue)),
        "matchable_rows_active_run": int(active_matchable),
        "matchable_rows_canonical_current": int(canonical_matchable),
        "scrape_rows_latest_supplier": int(len(latest_scrape)),
        "targeted_rows_with_asin": int(len(missing_df)),
        "missing_rows_with_asin": int(len(missing_df)),
        "rescrape_reason_counts": reason_counts,
        "selection_counts": selection_counts,
        "subset_rows_selected": int(len(subset_df)),
        "include_alignment_missing": bool(include_alignment_missing),
        "alignment_missing_path": str(alignment_missing_path_resolved) if include_alignment_missing else "",
        "alignment_missing_rows_source": int(alignment_missing_rows),
        "alignment_missing_asins_source": int(len(alignment_missing_asins)),
        "applied": bool(apply_changes),
        "active_supplier_rows_before": int(active_supplier_before),
        "active_supplier_rows_after": int(active_supplier_after),
        "active_total_rows_before": int(active_total_before),
        "active_total_rows_after": int(active_total_after),
        "backup_dir": str(backup_path) if backup_path is not None else "",
        "canonical_path": str(canonical_path),
        "report_path": str(report_path),
        "latest_path": str(latest_path),
        "restore_command": f"python scripts/flows/F/F062_reset_supplier_test_mode.py --supplier-id {supplier_id_clean} --no-clear-review-live",
    }
    print(json.dumps(summary))
    return TargetedRescrapeSubsetResult(
        report_df=report_df,
        report_path=report_path,
        latest_path=latest_path,
        summary=summary,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a targeted supplier rescrape subset for rows that already have ASINs but are missing "
            "completed-month BBP demand basis fields."
        )
    )
    parser.add_argument("--root", default=None)
    parser.add_argument("--supplier-id", required=True)
    parser.add_argument(
        "--queue-source",
        default="auto",
        choices=["auto", "active_run", "canonical_current"],
        help="Choose subset source rows from active_run, canonical_current, or auto-select by match coverage.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply subset queue changes to active supplier queue files.")
    parser.add_argument("--max-rows", type=int, default=0, help="Optional hard cap for selected subset rows. 0 = no cap.")
    parser.add_argument(
        "--include-alignment-missing",
        action="store_true",
        help=(
            "Also include rows whose ASIN appears in HF alignment with expected_units_source blank/no_source, "
            "using reason alignment_missing_expected_baseline."
        ),
    )
    parser.add_argument(
        "--alignment-missing-path",
        default=str(DEFAULT_HF_ALIGNMENT_PATH),
        help="Path to HF alignment CSV used when --include-alignment-missing is enabled.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--backup-dir", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if args.root else None
    backup_dir = Path(args.backup_dir) if args.backup_dir else None
    prepare_targeted_rescrape_subset(
        root=root,
        supplier_id=args.supplier_id,
        queue_source=args.queue_source,
        apply_changes=bool(args.apply),
        max_rows=args.max_rows,
        include_alignment_missing=bool(args.include_alignment_missing),
        alignment_missing_path=Path(args.alignment_missing_path),
        output_dir=Path(args.output_dir),
        backup_dir=backup_dir,
    )


if __name__ == "__main__":
    main()
