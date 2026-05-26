from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import write_f_contract_df


DEFAULT_PASS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
DEFAULT_NEAR_MISS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_CANONICAL_PATH = (
    ROOT / "out" / "systems" / "F" / "inbox" / "suppliers" / "stocklist_supplier" / "canonical_current.csv"
)
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f_dashboard_yes_no_rescan_plan_latest.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "f_dashboard_yes_no_rescan_summary_latest.csv"

OUTPUT_COLUMNS = [
    "observed_utc",
    "review_pack_type",
    "reviewability_state",
    "rescan_priority",
    "selection_status",
    "recommended_action",
    "rescan_reason_code",
    "candidate_id",
    "supplier_id",
    "active_run_id",
    "supplier_sku",
    "barcode",
    "asin",
    "title",
    "brand",
    "seller_history_code",
    "seller_history_recommended_action",
    "seller_history_new_30",
    "seller_history_new_90",
    "seller_history_new_180",
    "seller_history_dashboard_yes_or_no",
    "queue_match_source",
    "queue_match_key",
    "supplier_title",
    "unit_cost",
    "source_seen_at_utc",
    "amazon_link",
]

SUMMARY_COLUMNS = ["observed_utc", "metric", "value"]

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
    "completion_block_reason",
    "backtrack_original_observed_utc",
    "backtrack_attempt_count",
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

SELLER_HISTORY_CODES_THAT_BENEFIT = {
    "seller_history_clear",
    "single_fba_seller_amazon_absent",
    "single_seller_owner_unclear",
}


@dataclass(frozen=True)
class DashboardYesNoRescanPlanResult:
    plan_df: pd.DataFrame
    summary_df: pd.DataFrame
    output_path: Path
    summary_path: Path
    summary: dict[str, object]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_review_pack(path: Path, pack_type: str) -> pd.DataFrame:
    return _read_csv(path)


def _write_csv(path: Path, df: pd.DataFrame, columns: list[str]) -> None:
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            out[column] = ""
    out = out[columns].copy()
    for column in columns:
        out[column] = out[column].map(_normalize_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def _backup_existing_queue_files(*, root: Path, supplier_id: str, observed_utc: str) -> Path:
    stamp = observed_utc.replace(":", "").replace("-", "")
    backup_dir = root / "out" / "systems" / "F" / "inbox" / "dashboard_yes_no_rescan_backups" / stamp
    paths = [
        root / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv",
        root / "out" / "systems" / "F" / "inbox" / "supplier_price_list_run_state.csv",
        root / "out" / "systems" / "F" / "inbox" / "supplier_price_list_queue_state.csv",
        root / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id / "active_run.csv",
        root / "out" / "systems" / "F" / "inbox" / "suppliers" / supplier_id / "run_state.csv",
    ]
    for src in paths:
        if not src.exists():
            continue
        dest = backup_dir / src.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return backup_dir


def _latest_by_key(df: pd.DataFrame, key_column: str) -> dict[str, dict[str, str]]:
    if df.empty or key_column not in df.columns:
        return {}
    work = df.copy()
    if "observed_utc" in work.columns:
        work["_sort_ts"] = pd.to_datetime(work["observed_utc"].map(_normalize_text), errors="coerce")
        work = work.sort_values("_sort_ts", ascending=False, kind="stable").drop(columns=["_sort_ts"], errors="ignore")
    out: dict[str, dict[str, str]] = {}
    for row in work.to_dict("records"):
        key = _normalize_key(row.get(key_column, ""))
        if key and key not in out:
            out[key] = {column: _normalize_text(value) for column, value in row.items()}
    return out


def _canonical_by_sku(canonical_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if canonical_df.empty or "supplier_sku" not in canonical_df.columns:
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in canonical_df.to_dict("records"):
        key = _normalize_key(row.get("supplier_sku", ""))
        if key and key not in out:
            out[key] = {column: _normalize_text(value) for column, value in row.items()}
    return out


def _canonical_value(canonical_row: dict[str, str], column: str, fallback: str = "") -> str:
    return _normalize_text(canonical_row.get(column, "")) or fallback


def _queue_match(
    *,
    row: dict[str, str],
    canonical_by_sku: dict[str, dict[str, str]],
    scrape_by_candidate: dict[str, dict[str, str]],
    scrape_by_sku: dict[str, dict[str, str]],
) -> tuple[str, str, dict[str, str]]:
    sku_key = _normalize_key(row.get("supplier_sku", ""))
    candidate_key = _normalize_key(row.get("candidate_id", ""))
    if sku_key and sku_key in canonical_by_sku:
        return "canonical_current:supplier_sku", sku_key, canonical_by_sku[sku_key]
    if candidate_key and candidate_key in scrape_by_candidate:
        return "scrape_evidence:candidate_id", candidate_key, scrape_by_candidate[candidate_key]
    if sku_key and sku_key in scrape_by_sku:
        return "scrape_evidence:supplier_sku", sku_key, scrape_by_sku[sku_key]
    return "", "", {}


def _build_active_queue_rows(
    *,
    selected_df: pd.DataFrame,
    canonical_by_sku: dict[str, dict[str, str]],
    run_id: str,
    observed_utc: str,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for row in selected_df.fillna("").to_dict("records"):
        sku = _normalize_text(row.get("supplier_sku", ""))
        canonical_row = canonical_by_sku.get(_normalize_key(sku), {})
        rows.append(
            {
                "run_id": run_id,
                "supplier_id": _normalize_text(row.get("supplier_id", "")) or _canonical_value(canonical_row, "supplier_id"),
                "supplier_name": _canonical_value(canonical_row, "supplier_name", "Stocklist Supplier"),
                "row_key": _normalize_text(row.get("candidate_id", "")) or _canonical_value(canonical_row, "row_hash", sku),
                "supplier_sku": sku,
                "barcode": _normalize_text(row.get("barcode", "")) or _canonical_value(canonical_row, "barcode"),
                "supplier_title": _normalize_text(row.get("supplier_title", "")) or _canonical_value(canonical_row, "supplier_title"),
                "unit_cost": _normalize_text(row.get("unit_cost", "")) or _canonical_value(canonical_row, "unit_cost"),
                "currency": _canonical_value(canonical_row, "currency", "GBP"),
                "vat_rate": _canonical_value(canonical_row, "vat_rate", "20"),
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": _normalize_text(row.get("source_seen_at_utc", ""))
                or _canonical_value(canonical_row, "source_seen_at_utc", observed_utc),
                "completion_block_reason": "dashboard_yes_no_backtrack_required",
                "backtrack_original_observed_utc": _normalize_text(row.get("observed_utc", "")) or observed_utc,
                "backtrack_attempt_count": "0",
            }
        )
    return pd.DataFrame(rows, columns=ACTIVE_RUN_COLUMNS)


def _apply_selected_queue(
    *,
    root: Path,
    plan_df: pd.DataFrame,
    canonical_by_sku: dict[str, dict[str, str]],
    observed_utc: str,
) -> dict[str, object]:
    selected = plan_df[plan_df["selection_status"].map(_normalize_text) == "selected_now"].copy()
    if selected.empty:
        raise ValueError("no selected_now dashboard YES/NO rows to apply")
    supplier_ids = sorted(set(selected["supplier_id"].map(_normalize_text)))
    supplier_ids = [value for value in supplier_ids if value]
    if len(supplier_ids) != 1:
        raise ValueError(f"expected exactly one supplier_id in selected rows, got: {supplier_ids}")
    missing_queue_match = selected[selected["queue_match_source"].map(_normalize_text) == ""]
    if not missing_queue_match.empty:
        raise ValueError("selected_now rows include missing queue matches")

    supplier_id = supplier_ids[0]
    original_run_ids = sorted(
        {
            _normalize_text(value)
            for value in selected.get("active_run_id", pd.Series(dtype=str)).tolist()
            if _normalize_text(value)
        }
    )
    run_id = original_run_ids[0] if len(original_run_ids) == 1 else f"{supplier_id}_dashboard_yes_no_rescan_{observed_utc.replace(':', '').replace('-', '')}"
    backup_dir = _backup_existing_queue_files(root=root, supplier_id=supplier_id, observed_utc=observed_utc)
    active_new_df = _build_active_queue_rows(
        selected_df=selected,
        canonical_by_sku=canonical_by_sku,
        run_id=run_id,
        observed_utc=observed_utc,
    )
    active_df = active_new_df.copy()
    supplier_name = _normalize_text(active_new_df.iloc[0]["supplier_name"]) if not active_new_df.empty else "Stocklist Supplier"
    source_seen_at_utc = _normalize_text(active_new_df.iloc[0]["source_seen_at_utc"]) if not active_new_df.empty else observed_utc
    first_sku = _normalize_key(active_new_df.iloc[0]["supplier_sku"]) if not active_new_df.empty else ""
    first_canonical = canonical_by_sku.get(first_sku, {})
    source_file_path = _canonical_value(first_canonical, "source_file_path")
    source_url = _canonical_value(first_canonical, "source_url")
    run_state = pd.DataFrame(
        [
            {
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "run_id": run_id,
                "run_status": "running",
                "source_url": source_url,
                "source_file_path": source_file_path,
                "source_seen_at_utc": source_seen_at_utc,
                "normalized_utc": observed_utc,
                "total_rows": str(len(active_new_df)),
                "pending_rows": str(len(active_new_df)),
                "done_rows": "0",
                "failed_rows": "0",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": observed_utc,
                "completed_at_utc": "",
            }
        ],
        columns=RUN_STATE_COLUMNS,
    )
    queue_state = pd.DataFrame(
        [
            {
                "queue_id": "default",
                "current_supplier_id": supplier_id,
                "current_run_id": run_id,
                "last_completed_supplier_id": "",
                "next_supplier_id": "",
                "queue_index": "0",
                "status": "ok",
                "updated_at_utc": observed_utc,
                "notes": "dashboard_yes_no_login_backtrack_selected_pass_rows",
            }
        ],
        columns=QUEUE_STATE_COLUMNS,
    )

    inbox = root / "out" / "systems" / "F" / "inbox"
    supplier_dir = inbox / "suppliers" / supplier_id
    existing_run_state = _read_csv(inbox / "supplier_price_list_run_state.csv")
    if not existing_run_state.empty:
        existing_run_state = existing_run_state[
            ~(
                (existing_run_state.get("supplier_id", pd.Series(dtype=str)).map(_normalize_text) == supplier_id)
                & (existing_run_state.get("run_id", pd.Series(dtype=str)).map(_normalize_text) == run_id)
            )
        ].copy()
    run_state_all = pd.concat([run_state, existing_run_state], ignore_index=True)
    write_f_contract_df(root, "supplier_price_list_active_run", active_df)
    write_f_contract_df(root, "supplier_price_list_run_state", run_state_all)
    _write_csv(inbox / "supplier_price_list_queue_state.csv", queue_state, QUEUE_STATE_COLUMNS)
    _write_csv(supplier_dir / "active_run.csv", active_new_df, ACTIVE_RUN_COLUMNS)
    _write_csv(supplier_dir / "run_state.csv", run_state, RUN_STATE_COLUMNS)
    return {
        "applied": True,
        "supplier_id": supplier_id,
        "run_id": run_id,
        "applied_rows": int(len(active_new_df)),
        "backup_dir": str(backup_dir),
    }


def _max_seller_count(row: dict[str, str]) -> float | None:
    values: list[float] = []
    for column in ("seller_history_new_30", "seller_history_new_90", "seller_history_new_180"):
        text = _normalize_text(row.get(column, ""))
        if text == "":
            continue
        try:
            values.append(float(text))
        except ValueError:
            continue
    if not values:
        return None
    return max(values)


def _plan_row(
    *,
    row: dict[str, str],
    review_pack_type: str,
    observed_utc: str,
    canonical_by_sku: dict[str, dict[str, str]],
    scrape_by_candidate: dict[str, dict[str, str]],
    scrape_by_sku: dict[str, dict[str, str]],
    include_near_miss_now: bool,
) -> dict[str, str] | None:
    asin = _normalize_text(row.get("asin", ""))
    seller_history_code = _normalize_text(row.get("seller_history_code", ""))
    dashboard_value = _normalize_text(row.get("seller_history_dashboard_yes_or_no", "")).upper()
    if asin == "":
        return None
    if dashboard_value != "":
        return None
    if seller_history_code not in SELLER_HISTORY_CODES_THAT_BENEFIT:
        return None

    reviewability_state = _normalize_text(row.get("reviewability_state", "clean_pass" if review_pack_type == "passes" else ""))
    max_sellers = _max_seller_count(row)
    if review_pack_type == "passes":
        priority = "1"
        selection_status = "selected_now"
        action = "targeted_rescan_now"
    elif include_near_miss_now and reviewability_state == "reviewable":
        priority = "2"
        selection_status = "selected_now"
        action = "targeted_rescan_now"
    elif reviewability_state == "reviewable":
        priority = "2"
        selection_status = "deferred_reviewable_near_miss"
        action = "defer_until_pass_batch_or_manual_review_batch"
    else:
        priority = "9"
        selection_status = "deferred_non_reviewable_near_miss"
        action = "defer_no_current_clean_pass_impact"

    if max_sellers is None:
        reason = "dashboard_missing_seller_history_count_missing"
    elif max_sellers < 2:
        reason = "dashboard_missing_low_seller_count_decision_risk"
    else:
        reason = "dashboard_missing_multi_seller_alert_risk"

    match_source, match_key, match_row = _queue_match(
        row=row,
        canonical_by_sku=canonical_by_sku,
        scrape_by_candidate=scrape_by_candidate,
        scrape_by_sku=scrape_by_sku,
    )
    supplier_id = _normalize_text(row.get("active_supplier_id", "")) or _normalize_text(match_row.get("supplier_id", ""))
    supplier_title = _normalize_text(match_row.get("supplier_title", "")) or _normalize_text(row.get("title", ""))
    return {
        "observed_utc": observed_utc,
        "review_pack_type": review_pack_type,
        "reviewability_state": reviewability_state,
        "rescan_priority": priority,
        "selection_status": selection_status,
        "recommended_action": action,
        "rescan_reason_code": reason,
        "candidate_id": _normalize_text(row.get("candidate_id", "")),
        "supplier_id": supplier_id,
        "active_run_id": _normalize_text(row.get("active_run_id", "")),
        "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
        "barcode": _normalize_text(match_row.get("barcode", "")),
        "asin": asin,
        "title": _normalize_text(row.get("title", "")),
        "brand": _normalize_text(row.get("brand", "")),
        "seller_history_code": seller_history_code,
        "seller_history_recommended_action": _normalize_text(row.get("seller_history_recommended_action", "")),
        "seller_history_new_30": _normalize_text(row.get("seller_history_new_30", "")),
        "seller_history_new_90": _normalize_text(row.get("seller_history_new_90", "")),
        "seller_history_new_180": _normalize_text(row.get("seller_history_new_180", "")),
        "seller_history_dashboard_yes_or_no": dashboard_value,
        "queue_match_source": match_source,
        "queue_match_key": match_key,
        "supplier_title": supplier_title,
        "unit_cost": _normalize_text(match_row.get("unit_cost", "")),
        "source_seen_at_utc": _normalize_text(match_row.get("source_seen_at_utc", "")),
        "amazon_link": f"https://www.amazon.co.uk/dp/{asin}",
    }


def _summary_rows(plan_df: pd.DataFrame, observed_utc: str) -> list[dict[str, str]]:
    rows = [{"observed_utc": observed_utc, "metric": "output_rows", "value": str(len(plan_df))}]
    if plan_df.empty:
        return rows
    for column in ("selection_status", "recommended_action", "rescan_reason_code", "review_pack_type", "queue_match_source"):
        counts = plan_df[column].map(_normalize_text).replace("", "<blank>").value_counts().to_dict()
        for key, count in sorted(counts.items()):
            rows.append({"observed_utc": observed_utc, "metric": f"{column}::{key}", "value": str(int(count))})
    selected = plan_df[plan_df["selection_status"] == "selected_now"].copy()
    rows.append({"observed_utc": observed_utc, "metric": "selected_now_rows", "value": str(len(selected))})
    if not selected.empty:
        rows.append(
            {
                "observed_utc": observed_utc,
                "metric": "selected_now_queue_match_rows",
                "value": str(int((selected["queue_match_source"].map(_normalize_text) != "").sum())),
            }
        )
        rows.append(
            {
                "observed_utc": observed_utc,
                "metric": "selected_now_queue_missing_rows",
                "value": str(int((selected["queue_match_source"].map(_normalize_text) == "").sum())),
            }
        )
    return rows


def build_dashboard_yes_no_rescan_plan(
    *,
    pass_path: Path = DEFAULT_PASS_PATH,
    near_miss_path: Path = DEFAULT_NEAR_MISS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    observed_utc: str | None = None,
    include_near_miss_now: bool = False,
    apply_selected: bool = False,
    root: Path = ROOT,
) -> DashboardYesNoRescanPlanResult:
    observed_utc_value = _normalize_text(observed_utc) or _utc_now_iso()
    pass_df = _read_review_pack(pass_path, "passes")
    near_miss_df = _read_review_pack(near_miss_path, "near_misses")
    scrape_df = _read_csv(scrape_evidence_path)
    canonical_df = _read_csv(canonical_path)

    canonical_index = _canonical_by_sku(canonical_df)
    scrape_by_candidate = _latest_by_key(scrape_df, "candidate_id")
    scrape_by_sku = _latest_by_key(scrape_df, "supplier_sku")

    plan_rows: list[dict[str, str]] = []
    for review_pack_type, df in (("passes", pass_df), ("near_misses", near_miss_df)):
        for source_row in df.fillna("").to_dict("records"):
            normalized = {column: _normalize_text(value) for column, value in source_row.items()}
            planned = _plan_row(
                row=normalized,
                review_pack_type=review_pack_type,
                observed_utc=observed_utc_value,
                canonical_by_sku=canonical_index,
                scrape_by_candidate=scrape_by_candidate,
                scrape_by_sku=scrape_by_sku,
                include_near_miss_now=include_near_miss_now,
            )
            if planned is not None:
                plan_rows.append(planned)

    plan_df = pd.DataFrame(plan_rows, columns=OUTPUT_COLUMNS)
    _write_csv(output_path, plan_df, OUTPUT_COLUMNS)
    summary_df = pd.DataFrame(_summary_rows(plan_df, observed_utc_value), columns=SUMMARY_COLUMNS)
    _write_csv(summary_path, summary_df, SUMMARY_COLUMNS)

    summary = {
        "status": "success",
        "observed_utc": observed_utc_value,
        "pass_input_rows": int(len(pass_df)),
        "near_miss_input_rows": int(len(near_miss_df)),
        "scrape_evidence_rows": int(len(scrape_df)),
        "canonical_rows": int(len(canonical_df)),
        "output_rows": int(len(plan_df)),
        "selected_now_rows": int((plan_df["selection_status"] == "selected_now").sum()) if not plan_df.empty else 0,
        "deferred_rows": int((plan_df["selection_status"] != "selected_now").sum()) if not plan_df.empty else 0,
        "output_path": str(output_path),
        "summary_path": str(summary_path),
        "applied": False,
    }
    if apply_selected:
        apply_summary = _apply_selected_queue(
            root=root,
            plan_df=plan_df,
            canonical_by_sku=canonical_index,
            observed_utc=observed_utc_value,
        )
        summary.update(apply_summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return DashboardYesNoRescanPlanResult(
        plan_df=plan_df,
        summary_df=summary_df,
        output_path=output_path,
        summary_path=summary_path,
        summary=summary,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only rescan plan for missing BBP dashboard YES/NO evidence.")
    parser.add_argument("--pass-path", default=str(DEFAULT_PASS_PATH))
    parser.add_argument("--near-miss-path", default=str(DEFAULT_NEAR_MISS_PATH))
    parser.add_argument("--scrape-evidence-path", default=str(DEFAULT_SCRAPE_EVIDENCE_PATH))
    parser.add_argument("--canonical-path", default=str(DEFAULT_CANONICAL_PATH))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument(
        "--apply-selected",
        action="store_true",
        help="Write selected_now clean Pass rows into the supplier active-run queue with backups.",
    )
    parser.add_argument(
        "--include-near-miss-now",
        action="store_true",
        help="Also mark reviewable near-miss rows as selected now. Default selects clean Pass only.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_dashboard_yes_no_rescan_plan(
        pass_path=Path(args.pass_path),
        near_miss_path=Path(args.near_miss_path),
        scrape_evidence_path=Path(args.scrape_evidence_path),
        canonical_path=Path(args.canonical_path),
        output_path=Path(args.output_path),
        summary_path=Path(args.summary_path),
        include_near_miss_now=bool(args.include_near_miss_now),
        apply_selected=bool(args.apply_selected),
        root=Path(args.root),
    )


if __name__ == "__main__":
    main()
