from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.core.storage import (
    SQL_TABLE_FEEDER_REVIEW_EVENTS,
    read_dataframe_with_sql_fallback,
    write_review_pack_snapshots_sql_compat,
)
from scripts.flows.F._title_match_agent import classify_title_match
from scripts.flows.F._scanner_state import (
    dashboard_delivery_classification,
    dashboard_separate_delivery_required,
)


DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_BASELINE_PATH = DEFAULT_OUTPUT_DIR / "f_live_price_file_launch_baseline_latest.csv"
DEFAULT_ROW_STATE_PATH = ROOT / "out" / "systems" / "F" / "live" / "f_screening_row_state_live.csv"
DEFAULT_FIRST_CHECKS_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_first_checks_live.csv"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_PAGE_EVIDENCE_BACKFILL_RESULTS_PATH = (
    ROOT / "out" / "systems" / "F" / "page_evidence_backfill" / "page_evidence_backfill_results.csv"
)
DEFAULT_BACKTEST_SUMMARY_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
DEFAULT_PROFIT_AUDIT_PATH = DEFAULT_OUTPUT_DIR / "f_profit_formula_conflict_audit_latest.csv"
DEFAULT_REVIEW_EVENTS_PATH = ROOT / "out" / "systems" / "F" / "inbox" / "feeder_review_events.csv"
DEFAULT_SUPPLIER_INBOX_DIR = ROOT / "out" / "systems" / "F" / "inbox" / "suppliers"
DEFAULT_REVIEW_BATCH_SIZE = 20
DEFAULT_PROFIT_FLOOR_GBP = 20.0
DEFAULT_NEAR_MISS_PROFIT_FLOOR_GBP = 10.0
AMAZON_BLANK_CEILING = 49.0
AMAZON_50_REASONABLE_MAX = 100.0
AMAZON_50_WARN_MAX = 250.0
WEAK_UK_REVIEW_THRESHOLD = 6.0
VERY_WEAK_UK_REVIEW_THRESHOLD = 3.0
STRONG_UK_REVIEW_THRESHOLD = 10.0
LOW_SALES_CLEAN_PASS_MAX_UNITS = 2.0
MAIN_RANK_CLEAN_PASS_MAX = 50000.0

MISSING_TEXT_MARKERS = {"", "na", "n/a", "none", "null", "nan"}
DEMAND_RISK_CODES = {
    "amazon_blank_bbp_high",
    "amazon_50_bbp_warn",
    "amazon_50_bbp_inflated",
}
DEMAND_RECOMMENDED_ACTIONS = {
    "amazon_blank_bbp_high": "remove_from_clean_pass",
    "amazon_blank_bbp_low": "allow_if_other_checks_pass",
    "amazon_50_bbp_reasonable": "allow_if_other_checks_pass",
    "amazon_50_bbp_warn": "manual_review",
    "amazon_50_bbp_inflated": "remove_from_clean_pass",
}
HISTORY_RECOMMENDED_ACTIONS = {
    "history_fail_phase_avoid": "remove_from_clean_pass",
    "backtest_avoid_commercial_avoid_or_exit": "remove_from_clean_pass",
    "exit_only_clean_pass": "remove_from_clean_pass",
    "failure_events_100_plus": "manual_review",
    "selloff_days_exceed_normal_days": "manual_review",
    "history_recent_recovery_override": "allow_if_other_checks_pass",
    "history_risk_clear": "allow_if_other_checks_pass",
}
HISTORY_RULE_PRIORITY = {
    "history_fail_phase_avoid": 10,
    "exit_only_clean_pass": 20,
    "backtest_avoid_commercial_avoid_or_exit": 30,
    "failure_events_100_plus": 40,
    "selloff_days_exceed_normal_days": 50,
    "history_recent_recovery_override": 80,
    "history_risk_clear": 90,
}
UK_REVIEW_RECOMMENDED_ACTIONS = {
    "uk_reviews_lt3": "remove_from_clean_pass",
    "uk_reviews_3_to_5": "manual_review",
    "uk_reviews_6_to_9": "supporting_evidence_only",
    "uk_reviews_10_plus": "allow_if_other_checks_pass",
    "uk_reviews_missing": "targeted_rescan_needed",
}
IDENTITY_RECOMMENDED_ACTIONS = {
    "identity_clear": "allow_if_other_checks_pass",
    "identity_weak_manual_review": "manual_review",
    "identity_supplier_asin_mismatch": "remove_from_clean_pass",
}
PROFIT_RECOMMENDED_ACTIONS = {
    "profit_clear": "allow_if_other_checks_pass",
    "profit_low_upside_manual_review": "manual_review",
    "profit_too_weak": "remove_from_clean_pass",
    "profit_missing_inputs_rescan_needed": "targeted_rescan_needed",
    "profit_formula_review_needed": "manual_review",
    "profit_inflated_break_even_subtraction": "remove_from_clean_pass",
}
SELLER_HISTORY_RECOMMENDED_ACTIONS = {
    "dashboard_no_low_seller_count": "remove_from_clean_pass",
    "dashboard_no_multi_seller_count": "allow_if_other_checks_pass",
    "brand_owner_top_seller": "remove_from_clean_pass",
    "brand_owner_single_seller": "remove_from_clean_pass",
    "amazon_only_single_seller": "remove_from_clean_pass",
    "single_fba_seller_amazon_absent": "allow_if_other_checks_pass",
    "single_seller_owner_unclear": "manual_review",
    "seller_history_clear": "allow_if_other_checks_pass",
    "seller_history_missing": "missing_evidence_only",
}
ROUTING_ACTION_PRIORITY = {
    "remove_from_clean_pass": 10,
    "manual_review": 20,
    "targeted_rescan_needed": 30,
    "allow_if_other_checks_pass": 90,
    "missing_evidence_only": 95,
}
SELLER_STOCK_COUNT_COLUMNS = (
    "seller_stock_count",
    "seller_stock",
    "stock_count",
    "amazon_seller_stock_count",
    "seller_qty",
    "seller_inventory_count",
    "seller_stock_total",
    "total_seller_stock",
)
AMAZON_SOLD_PATTERN = re.compile(r"(?P<number>\d+(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)(?P<suffix>\s*[Kk])?\s*\+?")

PASS_COLUMNS = [
    "observed_utc",
    "active_supplier_id",
    "active_run_id",
    "review_batch_id",
    "review_priority_score",
    "candidate_id",
    "supplier_sku",
    "asin",
    "supplier_title",
    "amazon_title",
    "amazon_product_detail_text",
    "amazon_product_description",
    "amazon_feature_bullets",
    "title",
    "supplier_brand",
    "amazon_brand",
    "brand",
    "main_rank",
    "original_point_score",
    "original_test_result",
    "original_test_status_reason",
    "original_test_gate",
    "screening_status_reason",
    "title_match_action",
    "title_match_decision_bucket",
    "title_match_reason_code",
    "title_match_confidence",
    "title_match_evidence",
    "title_match_high_roi_flag",
    "title_match_profit_on_cost_pct",
    "identity_match_code",
    "identity_recommended_action",
    "identity_supporting_codes",
    "identity_evidence_source",
    "backtest_decision_state",
    "expected_units_next_30d",
    "sales_lower_30d",
    "sales_upper_30d",
    "expected_profit_next_30d_gbp",
    "estimated_monthly_profit_gbp",
    "profit_per_unit_30d_gbp",
    "profit_formula_code",
    "profit_recommended_action",
    "corrected_profit_per_unit_gbp",
    "corrected_expected_profit_next_30d_gbp",
    "profit_delta_per_unit_gbp",
    "profit_delta_total_gbp",
    "profit_evidence_source",
    "conservative_starter_qty",
    "demand_conflict_code",
    "demand_recommended_action",
    "demand_supporting_codes",
    "demand_evidence_source",
    "history_risk_code",
    "history_recommended_action",
    "history_supporting_codes",
    "history_evidence_source",
    "uk_review_code",
    "uk_review_recommended_action",
    "uk_review_supporting_codes",
    "uk_review_evidence_source",
    "seller_history_code",
    "seller_history_recommended_action",
    "seller_history_supporting_codes",
    "seller_history_evidence_source",
    "seller_history_new_30",
    "seller_history_new_90",
    "seller_history_new_180",
    "seller_history_dashboard_yes_or_no",
    "seller_history_dashboard_delivery_classification",
    "seller_history_dashboard_separate_delivery_required",
    "seller_history_top_seller_names",
    "seller_history_brand_match_seller",
    "seller_history_brand_match_score",
    "seller_history_rank_1_seller_name",
    "seller_history_rank_1_brand_match_flag",
    "seller_history_buybox_seller_name",
    "seller_history_buybox_brand_match_score",
    "review_memory_event_id",
    "review_memory_decision",
    "review_memory_note",
    "review_memory_event_utc",
    "why_data_summary",
    "watch_data_summary",
    "pass_reason_summary",
    "commercial_note",
]

NEAR_MISS_COLUMNS = [
    "observed_utc",
    "active_supplier_id",
    "active_run_id",
    "review_batch_id",
    "review_priority_score",
    "near_miss_type",
    "reviewability_state",
    "candidate_id",
    "supplier_sku",
    "asin",
    "supplier_title",
    "amazon_title",
    "amazon_product_detail_text",
    "amazon_product_description",
    "amazon_feature_bullets",
    "title",
    "supplier_brand",
    "amazon_brand",
    "brand",
    "original_point_score",
    "original_test_result",
    "original_test_status_reason",
    "original_test_gate",
    "screening_fail_code",
    "screening_status_reason",
    "title_match_action",
    "title_match_decision_bucket",
    "title_match_reason_code",
    "title_match_confidence",
    "title_match_evidence",
    "title_match_high_roi_flag",
    "title_match_profit_on_cost_pct",
    "identity_match_code",
    "identity_recommended_action",
    "identity_supporting_codes",
    "identity_evidence_source",
    "last_stage",
    "main_rank",
    "backtest_decision_state",
    "expected_units_next_30d",
    "sales_lower_30d",
    "sales_upper_30d",
    "expected_profit_next_30d_gbp",
    "estimated_monthly_profit_gbp",
    "profit_per_unit_30d_gbp",
    "profit_formula_code",
    "profit_recommended_action",
    "corrected_profit_per_unit_gbp",
    "corrected_expected_profit_next_30d_gbp",
    "profit_delta_per_unit_gbp",
    "profit_delta_total_gbp",
    "profit_evidence_source",
    "conservative_starter_qty",
    "demand_conflict_code",
    "demand_recommended_action",
    "demand_supporting_codes",
    "demand_evidence_source",
    "history_risk_code",
    "history_recommended_action",
    "history_supporting_codes",
    "history_evidence_source",
    "uk_review_code",
    "uk_review_recommended_action",
    "uk_review_supporting_codes",
    "uk_review_evidence_source",
    "seller_history_code",
    "seller_history_recommended_action",
    "seller_history_supporting_codes",
    "seller_history_evidence_source",
    "seller_history_new_30",
    "seller_history_new_90",
    "seller_history_new_180",
    "seller_history_dashboard_yes_or_no",
    "seller_history_dashboard_delivery_classification",
    "seller_history_dashboard_separate_delivery_required",
    "seller_history_top_seller_names",
    "seller_history_brand_match_seller",
    "seller_history_brand_match_score",
    "seller_history_rank_1_seller_name",
    "seller_history_rank_1_brand_match_flag",
    "seller_history_buybox_seller_name",
    "seller_history_buybox_brand_match_score",
    "review_memory_event_id",
    "review_memory_decision",
    "review_memory_note",
    "review_memory_event_utc",
    "why_data_summary",
    "watch_data_summary",
    "recovery_hint",
    "commercial_note",
]

SUMMARY_COLUMNS = ["observed_utc", "metric", "value"]


@dataclass(frozen=True)
class LivePriceFileReviewPackResult:
    pass_df: pd.DataFrame
    near_miss_df: pd.DataFrame
    summary_df: pd.DataFrame
    pass_path: Path
    pass_latest_path: Path
    near_miss_path: Path
    near_miss_latest_path: Path
    summary_path: Path
    summary_latest_path: Path
    report: dict[str, Any]


@dataclass(frozen=True)
class DemandRangeClassification:
    primary_code: str
    recommended_action: str
    supporting_codes: tuple[str, ...]
    evidence_source: str


@dataclass(frozen=True)
class HistoryRiskClassification:
    primary_code: str
    recommended_action: str
    supporting_codes: tuple[str, ...]
    evidence_source: str


@dataclass(frozen=True)
class UkReviewClassification:
    primary_code: str
    recommended_action: str
    supporting_codes: tuple[str, ...]
    evidence_source: str


@dataclass(frozen=True)
class IdentityMatchClassification:
    primary_code: str
    recommended_action: str
    supporting_codes: tuple[str, ...]
    evidence_source: str


@dataclass(frozen=True)
class ProfitRoutingClassification:
    primary_code: str
    recommended_action: str
    supporting_codes: tuple[str, ...]
    evidence_source: str


@dataclass(frozen=True)
class SellerHistoryClassification:
    primary_code: str
    recommended_action: str
    supporting_codes: tuple[str, ...]
    evidence_source: str
    new_30: float | None
    new_90: float | None
    new_180: float | None
    dashboard_yes_or_no: str
    dashboard_delivery_classification: str
    dashboard_separate_delivery_required: str
    top_seller_names: str
    brand_match_seller: str
    brand_match_score: float | None
    rank_1_seller_name: str
    rank_1_brand_match_flag: str
    buybox_seller_name: str
    buybox_brand_match_score: float | None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_timestamp_slug(observed_utc: str) -> str:
    dt = datetime.strptime(observed_utc, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _candidate_id_base(value: object) -> str:
    token = _normalize_text(value)
    if token == "":
        return ""
    if "__" in token:
        return token.split("__", 1)[0]
    return token


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _load_supplier_title_index(supplier_inbox_dir: Path, active_supplier_id: str) -> dict[tuple[str, str], dict[str, str]]:
    index: dict[tuple[str, str], dict[str, str]] = {}
    supplier_dirs: list[Path] = []
    active_dir = supplier_inbox_dir / active_supplier_id if active_supplier_id else None
    if active_dir is not None and active_dir.exists():
        supplier_dirs.append(active_dir)
    if supplier_inbox_dir.exists():
        for supplier_dir in supplier_inbox_dir.iterdir():
            if supplier_dir.is_dir() and supplier_dir not in supplier_dirs:
                supplier_dirs.append(supplier_dir)

    for supplier_dir in supplier_dirs:
        path = supplier_dir / "canonical_current.csv"
        df = _read_csv(path)
        if df.empty or "supplier_sku" not in df.columns:
            continue
        if "supplier_id" not in df.columns:
            df["supplier_id"] = supplier_dir.name
        for _, row in df.iterrows():
            supplier_id = _normalize_text(row.get("supplier_id", "")) or supplier_dir.name
            supplier_sku = _normalize_text(row.get("supplier_sku", ""))
            if supplier_sku == "":
                continue
            record = {
                "supplier_id": supplier_id,
                "supplier_sku": supplier_sku,
                "supplier_title": _normalize_text(row.get("supplier_title", "")),
                "supplier_brand": _normalize_text(row.get("brand", "")),
                "unit_cost": _normalize_text(row.get("unit_cost", "")),
                "currency": _normalize_text(row.get("currency", "")),
            }
            exact_key = (_normalize_key(supplier_id), _normalize_key(supplier_sku))
            fallback_key = ("", _normalize_key(supplier_sku))
            index[exact_key] = record
            index.setdefault(fallback_key, record)
    return index


def _has_page_evidence(record: dict[str, str]) -> bool:
    return any(
        _evidence_text_value(record.get(column, ""))
        for column in ("product_detail_text", "product_description", "product_feature_bullets")
    )


def _build_page_evidence_backfill_indexes(
    path: Path | None,
) -> tuple[int, int, dict[tuple[str, str], dict[str, str]], dict[tuple[str], dict[str, str]]]:
    if path is None:
        return 0, 0, {}, {}
    df = _read_csv(path)
    source_rows = int(len(df.index))
    if df.empty:
        return source_rows, 0, {}, {}
    for column in ("backfill_status", "page_evidence_captured_flag", "supplier_sku", "asin", "resolved_asin"):
        if column not in df.columns:
            df[column] = ""
    work = df.loc[
        (df["backfill_status"].map(lambda value: _normalize_text(value).lower()) == "succeeded")
        & (df["page_evidence_captured_flag"].map(_normalize_text) == "1")
    ].copy()
    if work.empty:
        return source_rows, 0, {}, {}
    work["effective_asin"] = work.apply(
        lambda row: _normalize_text(row.get("resolved_asin", "")) or _normalize_text(row.get("asin", "")),
        axis=1,
    )
    work = work.loc[
        work.apply(lambda row: _normalize_text(row.get("effective_asin", "")) != "" and _has_page_evidence(row), axis=1)
    ].copy()
    usable_rows = int(len(work.index))
    if work.empty:
        return source_rows, usable_rows, {}, {}
    by_supplier_asin = _latest_by_keys(work, ["supplier_sku", "effective_asin"], ["observed_utc"])
    by_asin = _latest_by_keys(work, ["effective_asin"], ["observed_utc"])
    return source_rows, usable_rows, by_supplier_asin, by_asin


def _page_evidence_text(
    scrape: dict[str, str],
    backfill: dict[str, str],
    column: str,
) -> tuple[str, bool]:
    scrape_text = _evidence_text_value(scrape.get(column, ""))
    if scrape_text:
        return scrape_text, False
    backfill_text = _evidence_text_value(backfill.get(column, ""))
    return backfill_text, bool(backfill_text)


def _supplier_title_values(
    *,
    supplier_title_index: dict[tuple[str, str], dict[str, str]],
    active_supplier_id: str,
    supplier_sku: str,
    first_checks: dict[str, str],
    scrape: dict[str, str],
) -> dict[str, str]:
    exact_key = (_normalize_key(active_supplier_id), _normalize_key(supplier_sku))
    fallback_key = ("", _normalize_key(supplier_sku))
    record = supplier_title_index.get(exact_key) or supplier_title_index.get(fallback_key) or {}
    supplier_title = (
        _normalize_text(record.get("supplier_title", ""))
        or _normalize_text(first_checks.get("supplier_title", ""))
        or _normalize_text(scrape.get("supplier_title", ""))
    )
    supplier_brand = (
        _normalize_text(record.get("supplier_brand", ""))
        or _normalize_text(first_checks.get("supplier_brand", ""))
        or _normalize_text(scrape.get("supplier_brand", ""))
    )
    return {
        "supplier_title": supplier_title,
        "supplier_brand": supplier_brand,
        "unit_cost": _normalize_text(record.get("unit_cost", "")),
        "currency": _normalize_text(record.get("currency", "")),
    }


def _read_review_events(path: Path) -> pd.DataFrame:
    try:
        return read_dataframe_with_sql_fallback(path, SQL_TABLE_FEEDER_REVIEW_EVENTS, dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace(",", "").replace("GBP", "").replace("gbp", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _value_is_missing(value: object) -> bool:
    return _normalize_text(value).lower() in MISSING_TEXT_MARKERS


def _evidence_text_value(value: object) -> str:
    text = _normalize_text(value)
    return "" if text.lower() in MISSING_TEXT_MARKERS else text


def _num_to_text(value: float | int | None) -> str:
    if value is None:
        return ""
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _latest_by_keys(df: pd.DataFrame, keys: list[str], utc_columns: list[str]) -> dict[tuple[str, ...], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    for idx, key in enumerate(keys):
        work[f"_key_{idx}"] = work.get(key, "").map(_normalize_key)
    utc_series = None
    for column in utc_columns:
        if column not in work.columns:
            continue
        parsed = pd.to_datetime(work[column].map(_normalize_text), format="mixed", errors="coerce", utc=True)
        utc_series = parsed if utc_series is None else utc_series.fillna(parsed)
    if utc_series is not None:
        work["_obs_ts"] = utc_series
        work = work.sort_values("_obs_ts", ascending=False, kind="stable")

    out: dict[tuple[str, ...], dict[str, str]] = {}
    for _, row in work.iterrows():
        key_tuple = tuple(_normalize_key(row.get(f"_key_{idx}", "")) for idx in range(len(keys)))
        if any(token == "" for token in key_tuple):
            continue
        if key_tuple in out:
            continue
        out[key_tuple] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _build_latest_review_event_index(
    events_df: pd.DataFrame,
) -> tuple[
    dict[tuple[str, str], dict[str, str]],
    dict[tuple[str, str], dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
]:
    by_pack_candidate: dict[tuple[str, str], dict[str, str]] = {}
    by_pack_asin: dict[tuple[str, str], dict[str, str]] = {}
    by_candidate: dict[str, dict[str, str]] = {}
    by_asin: dict[str, dict[str, str]] = {}
    if events_df.empty:
        return by_pack_candidate, by_pack_asin, by_candidate, by_asin

    work = events_df.copy()
    for col in (
        "event_utc",
        "event_id",
        "review_decision",
        "review_pack_type",
        "candidate_id",
        "asin_padded",
        "asin_raw",
        "review_note",
    ):
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].map(_normalize_text)

    work = work[work["review_decision"].map(lambda value: value.lower() in {"pass", "fail"})].copy()
    if work.empty:
        return by_pack_candidate, by_pack_asin, by_candidate, by_asin

    work["_event_utc_ts"] = pd.to_datetime(work["event_utc"], errors="coerce", utc=True, format="mixed")
    work = work.sort_values(by=["_event_utc_ts", "event_id"], ascending=[False, False], kind="stable")

    for _, row in work.iterrows():
        event = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        pack_type = _normalize_key(event.get("review_pack_type", ""))
        candidate = _normalize_key(event.get("candidate_id", ""))
        asin = _normalize_key(event.get("asin_padded", "")) or _normalize_key(event.get("asin_raw", ""))

        if candidate != "":
            by_candidate.setdefault(candidate, event)
            if pack_type != "":
                by_pack_candidate.setdefault((pack_type, candidate), event)

        if asin != "":
            by_asin.setdefault(asin, event)
            if pack_type != "":
                by_pack_asin.setdefault((pack_type, asin), event)

    return by_pack_candidate, by_pack_asin, by_candidate, by_asin


def _find_latest_review_event(
    *,
    review_pack_type: str,
    candidate_id: str,
    asin: str,
    by_pack_candidate: dict[tuple[str, str], dict[str, str]],
    by_pack_asin: dict[tuple[str, str], dict[str, str]],
    by_candidate: dict[str, dict[str, str]],
    by_asin: dict[str, dict[str, str]],
) -> dict[str, str] | None:
    pack = _normalize_key(review_pack_type)
    candidate = _normalize_key(candidate_id)
    asin_key = _normalize_key(asin)

    if pack != "" and candidate != "" and (pack, candidate) in by_pack_candidate:
        return by_pack_candidate[(pack, candidate)]
    if pack != "" and asin_key != "" and (pack, asin_key) in by_pack_asin:
        return by_pack_asin[(pack, asin_key)]
    if candidate != "" and candidate in by_candidate:
        return by_candidate[candidate]
    if asin_key != "" and asin_key in by_asin:
        return by_asin[asin_key]
    return None


def _review_memory_values(event: dict[str, str] | None) -> dict[str, str]:
    if not event:
        return {
            "review_memory_event_id": "",
            "review_memory_decision": "",
            "review_memory_note": "",
            "review_memory_event_utc": "",
        }
    return {
        "review_memory_event_id": _normalize_text(event.get("event_id", "")),
        "review_memory_decision": _normalize_text(event.get("review_decision", "")).lower(),
        "review_memory_note": _normalize_text(event.get("review_note", "")),
        "review_memory_event_utc": _normalize_text(event.get("event_utc", "")),
    }


def _lookup_with_fallback(
    primary: dict[tuple[str, ...], dict[str, str]],
    primary_key: tuple[str, ...],
    secondary: dict[tuple[str, ...], dict[str, str]] | None = None,
    secondary_key: tuple[str, ...] | None = None,
) -> dict[str, str]:
    if primary_key in primary:
        return primary[primary_key]
    if secondary is not None and secondary_key is not None and secondary_key in secondary:
        return secondary[secondary_key]
    return {}


def _profit_audit_values(record: dict[str, str]) -> dict[str, str]:
    if not record:
        return {
            "profit_formula_code": "",
            "profit_recommended_action": "",
            "corrected_profit_per_unit_gbp": "",
            "corrected_expected_profit_next_30d_gbp": "",
            "profit_delta_per_unit_gbp": "",
            "profit_delta_total_gbp": "",
            "profit_evidence_source": "",
        }
    return {
        "profit_formula_code": _normalize_text(record.get("profit_formula_code", "")),
        "profit_recommended_action": _normalize_text(record.get("recommended_action", "")),
        "corrected_profit_per_unit_gbp": _normalize_text(record.get("corrected_profit_per_unit_gbp", "")),
        "corrected_expected_profit_next_30d_gbp": _normalize_text(record.get("corrected_expected_profit_next_30d_gbp", "")),
        "profit_delta_per_unit_gbp": _normalize_text(record.get("profit_delta_per_unit_gbp", "")),
        "profit_delta_total_gbp": _normalize_text(record.get("profit_delta_total_gbp", "")),
        "profit_evidence_source": _normalize_text(record.get("evidence_source", "")),
    }


def _title_match_values(title_match: dict[str, Any]) -> dict[str, str]:
    return {
        "title_match_action": _normalize_text(title_match.get("title_match_action", "")),
        "title_match_decision_bucket": _normalize_text(title_match.get("agent_decision_bucket", "")),
        "title_match_reason_code": _normalize_text(title_match.get("agent_reason_code", "")),
        "title_match_confidence": _normalize_text(title_match.get("agent_confidence", "")),
        "title_match_evidence": _normalize_text(title_match.get("agent_evidence", "")),
        "title_match_high_roi_flag": _normalize_text(title_match.get("high_roi_flag", "")),
        "title_match_profit_on_cost_pct": _num_to_text(_num_or_none(title_match.get("profit_on_cost_pct", ""))),
    }


def _title_match_routing_values(title_match_fields: dict[str, str]) -> tuple[str, str, str, str] | None:
    action = _normalize_text(title_match_fields.get("title_match_action", ""))
    reason_code = _normalize_text(title_match_fields.get("title_match_reason_code", ""))
    if action == "remove_from_clean_pass":
        return (
            "title_match_identity_suspicion",
            "remove_from_clean_pass",
            "TITLE_MATCH_BLOCK",
            reason_code or "remove_from_clean_pass_due_to_title_match_ai_check",
        )
    if action == "manual_review":
        return (
            "title_match_manual_review",
            "manual_review",
            "TITLE_MATCH_REVIEW",
            reason_code or "manual_review_due_to_title_match_ai_check",
        )
    return None


def _sales_band(expected_units: float | None, confidence: str, stability: str) -> tuple[int | None, int | None]:
    if expected_units is None or expected_units <= 0:
        return None, None
    low_mult = 0.55
    high_mult = 1.55
    if confidence == "high":
        low_mult = 0.75
        high_mult = 1.30
    elif confidence == "medium":
        low_mult = 0.65
        high_mult = 1.40
    if stability == "too_new":
        low_mult = min(low_mult, 0.50)
        high_mult = max(high_mult, 1.70)
    lower = max(0, int(expected_units * low_mult))
    upper = max(lower, int(ceil(expected_units * high_mult)))
    if expected_units > 0 and upper == lower:
        upper = lower + 1
    return lower, upper


def _starter_qty(lower_units: int | None) -> int:
    if lower_units is None or lower_units <= 0:
        return 0
    if lower_units <= 2:
        return 1
    if lower_units <= 6:
        return 2
    if lower_units <= 12:
        return 3
    if lower_units <= 25:
        return 5
    return 8


def _pass_reason_summary(backtest: dict[str, str], scrape: dict[str, str]) -> str:
    reasons: list[str] = ["screening_pass"]
    if _normalize_text(backtest.get("decision_state", "")) == "pass":
        reasons.append("backtest_pass")
    expected_profit = _num_or_none(backtest.get("expected_profit_next_30d_gbp", ""))
    est_profit = _num_or_none(scrape.get("estimated_monthly_profit", ""))
    profit_basis = expected_profit if expected_profit is not None else est_profit
    if profit_basis is not None and profit_basis >= DEFAULT_PROFIT_FLOOR_GBP:
        reasons.append("profit_floor_met")
    if _normalize_text(scrape.get("demand_confidence_note", "")) != "":
        reasons.append("demand_evidence_present")
    return "|".join(reasons)


def _commercial_note(backtest: dict[str, str], scrape: dict[str, str]) -> str:
    parts: list[str] = []
    for candidate in [
        backtest.get("recommendation", ""),
        backtest.get("decision_reason_codes", ""),
        scrape.get("opportunity_recommendation", ""),
        scrape.get("history_recommendation", ""),
        scrape.get("demand_confidence_note", ""),
    ]:
        text = _normalize_text(candidate)
        if text != "" and text not in parts:
            parts.append(text)
    return " | ".join(parts[:3])


def _join_nonempty(parts: list[str]) -> str:
    return " | ".join([part for part in parts if _normalize_text(part) != ""])


def _pass_data_summaries(
    *,
    status_reason: str,
    main_rank: str,
    original_point_score: str,
    original_test_result: str,
    expected_units: float | None,
    lower_units: int | None,
    upper_units: int | None,
    expected_profit: float | None,
    est_profit: float | None,
    starter_qty: int,
    backtest: dict[str, str],
    scrape: dict[str, str],
) -> tuple[str, str]:
    profit_basis = expected_profit if expected_profit is not None else est_profit
    why_summary = _join_nonempty(
        [
            f"screen_status={_normalize_text(status_reason) or 'PASS'}",
            f"original_score={_normalize_text(original_point_score) or 'NA'}",
            f"original_result={_normalize_text(original_test_result) or 'NA'}",
            f"rank={_normalize_text(main_rank) or 'NA'}",
            f"units_likely_30d={_num_to_text(expected_units) or 'NA'}",
            f"units_band_30d={_num_to_text(lower_units) or 'NA'}..{_num_to_text(upper_units) or 'NA'}",
            f"profit_likely_gbp={_num_to_text(profit_basis) or 'NA'}",
            f"starter_qty={_num_to_text(starter_qty) or '0'}",
            f"backtest_state={_normalize_text(backtest.get('decision_state', '')) or 'missing'}",
        ]
    )
    watch_summary = _join_nonempty(
        [
            f"decision_confidence={_normalize_text(backtest.get('decision_confidence', '')) or 'NA'}",
            f"stability_state={_normalize_text(backtest.get('stability_state', '')) or 'NA'}",
            f"seasonality_state={_normalize_text(backtest.get('seasonality_state', '')) or 'NA'}",
            f"recent_vs_baseline_state={_normalize_text(backtest.get('recent_vs_baseline_state', '')) or 'NA'}",
            f"opportunity_recommendation={_normalize_text(scrape.get('opportunity_recommendation', '')) or 'NA'}",
            f"history_recommendation={_normalize_text(scrape.get('history_recommendation', '')) or 'NA'}",
            f"demand_confidence_note={_normalize_text(scrape.get('demand_confidence_note', '')) or 'NA'}",
        ]
    )
    return why_summary, watch_summary


def _near_miss_data_summaries(
    *,
    status_reason: str,
    fail_code: str,
    last_stage: str,
    main_rank: str,
    original_point_score: str,
    original_test_result: str,
    expected_units: float | None,
    lower_units: int | None,
    upper_units: int | None,
    expected_profit: float | None,
    est_profit: float | None,
    starter_qty: int,
    recovery_hint: str,
    backtest: dict[str, str],
    scrape: dict[str, str],
) -> tuple[str, str]:
    profit_basis = expected_profit if expected_profit is not None else est_profit
    why_summary = _join_nonempty(
        [
            f"screen_status={_normalize_text(status_reason) or 'timeout'}",
            f"fail_code={_normalize_text(fail_code) or 'UNKNOWN'}",
            f"last_stage={_normalize_text(last_stage) or 'NA'}",
            f"original_score={_normalize_text(original_point_score) or 'NA'}",
            f"original_result={_normalize_text(original_test_result) or 'NA'}",
            f"rank={_normalize_text(main_rank) or 'NA'}",
            f"units_likely_30d={_num_to_text(expected_units) or 'NA'}",
            f"units_band_30d={_num_to_text(lower_units) or 'NA'}..{_num_to_text(upper_units) or 'NA'}",
            f"profit_likely_gbp={_num_to_text(profit_basis) or 'NA'}",
            f"starter_qty={_num_to_text(starter_qty) or '0'}",
        ]
    )
    watch_summary = _join_nonempty(
        [
            f"recovery_hint={_normalize_text(recovery_hint) or 'NA'}",
            f"decision_confidence={_normalize_text(backtest.get('decision_confidence', '')) or 'NA'}",
            f"stability_state={_normalize_text(backtest.get('stability_state', '')) or 'NA'}",
            f"seasonality_state={_normalize_text(backtest.get('seasonality_state', '')) or 'NA'}",
            f"recent_vs_baseline_state={_normalize_text(backtest.get('recent_vs_baseline_state', '')) or 'NA'}",
            f"opportunity_recommendation={_normalize_text(scrape.get('opportunity_recommendation', '')) or 'NA'}",
            f"history_recommendation={_normalize_text(scrape.get('history_recommendation', '')) or 'NA'}",
        ]
    )
    return why_summary, watch_summary


def _original_test_fields(first_checks: dict[str, str]) -> tuple[str, str, str, str]:
    point_score_num = _num_or_none(first_checks.get("point_score", ""))
    point_score = _num_to_text(point_score_num)
    test_result = _normalize_text(first_checks.get("pf", "")).upper()
    status_reason = _normalize_text(first_checks.get("status_reason", ""))
    if test_result == "" and point_score_num is not None:
        test_result = "PASS" if point_score_num >= 3.5 else "FAIL"
    if status_reason == "" and test_result != "":
        status_reason = test_result
    test_gate = "3.5" if (point_score != "" or test_result != "") else ""
    return point_score, test_result, status_reason, test_gate


def _identity_evidence_source(
    row_state: dict[str, str],
    first_checks: dict[str, str],
    scrape: dict[str, str],
) -> str:
    sources: list[str] = []
    if _normalize_text(row_state.get("status_reason", "")):
        sources.append("f_screening_row_state_live.csv:status_reason")
    if _normalize_text(first_checks.get("status_reason", "")):
        sources.append("feeder_legacy_first_checks_live.csv:status_reason")
    if _normalize_text(scrape.get("status_reason", "")):
        sources.append("feeder_legacy_scrape_evidence_live.csv:status_reason")
    if _normalize_text(scrape.get("catalog_match_scorecard", "")):
        sources.append("feeder_legacy_scrape_evidence_live.csv:catalog_match_scorecard")
    return "|".join(sources)


def _identity_match_classification(
    *,
    row_state: dict[str, str],
    first_checks: dict[str, str],
    scrape: dict[str, str],
) -> IdentityMatchClassification:
    evidence_parts = [
        row_state.get("status_reason", ""),
        first_checks.get("status_reason", ""),
        scrape.get("status_reason", ""),
        scrape.get("catalog_match_scorecard", ""),
    ]
    evidence_text = " | ".join(_normalize_key(part) for part in evidence_parts if _normalize_text(part) != "")
    supporting: list[str] = []

    if "BARCODE_CONFLICT" in evidence_text:
        supporting.append("barcode_conflict")
    if "MATCH_VERY_WEAK" in evidence_text or "VERY_WEAK" in evidence_text:
        supporting.append("very_weak_match")
    if "MATCH_WEAK" in evidence_text or "|WEAK|" in evidence_text:
        supporting.append("weak_match")

    if "BARCODE_CONFLICT" in evidence_text or "MATCH_VERY_WEAK" in evidence_text or "VERY_WEAK" in evidence_text:
        primary_code = "identity_supplier_asin_mismatch"
    elif "MATCH_WEAK" in evidence_text or "|WEAK|" in evidence_text:
        primary_code = "identity_weak_manual_review"
    else:
        primary_code = "identity_clear"

    return IdentityMatchClassification(
        primary_code=primary_code,
        recommended_action=IDENTITY_RECOMMENDED_ACTIONS[primary_code],
        supporting_codes=tuple(supporting or [primary_code]),
        evidence_source=_identity_evidence_source(row_state, first_checks, scrape),
    )


def _identity_values(identity: IdentityMatchClassification) -> dict[str, str]:
    return {
        "identity_match_code": identity.primary_code,
        "identity_recommended_action": identity.recommended_action,
        "identity_supporting_codes": "|".join(identity.supporting_codes),
        "identity_evidence_source": identity.evidence_source,
    }


def _identity_routing_values(identity: IdentityMatchClassification) -> tuple[str, str, str, str] | None:
    if identity.recommended_action == "remove_from_clean_pass":
        return (
            "identity_mismatch",
            "remove_from_clean_pass",
            "IDENTITY_MISMATCH",
            "remove_from_clean_pass_due_to_supplier_asin_identity_mismatch",
        )
    if identity.recommended_action == "manual_review":
        return (
            "identity_manual_review",
            "reviewable",
            "IDENTITY_WARN",
            "manual_review_due_to_weak_supplier_asin_identity_match",
        )
    return None


def _near_miss_classification(
    *,
    fail_code: str,
    expected_profit: float | None,
    est_profit: float | None,
    opportunity_recommendation: str,
    history_recommendation: str,
) -> tuple[str, str, str]:
    fail_key = _normalize_key(fail_code)
    if fail_key in {"RESCAN", "NODATE", "SCRAPEFAIL"}:
        return (
            "evidence_gap_near_miss",
            "reviewable",
            "technical_or_missing_evidence_rescan",
        )
    profit_basis = expected_profit if expected_profit is not None else est_profit
    if fail_key in {"ROIFAIL", "FAIL"}:
        if profit_basis is not None and profit_basis >= DEFAULT_NEAR_MISS_PROFIT_FLOOR_GBP:
            return (
                "commercial_near_miss",
                "reviewable",
                "economics_below_pass_floor_but_close_enough_for_manual_review",
            )
        if _normalize_key(opportunity_recommendation) in {"REVIEW", "PASS"} or _normalize_key(history_recommendation) in {
            "REVIEW",
            "PASS",
        }:
            return (
                "commercial_near_miss",
                "reviewable",
                "supporting_history_signal_keeps_row_reviewable",
            )
    return ("hard_reject", "hard_reject", "fail_code_not_reviewable_in_batch_002")


def _parse_amazon_sold_floor(value: object) -> float | None:
    text = _normalize_text(value)
    if _value_is_missing(text):
        return None
    direct = _num_or_none(text)
    if direct is not None:
        return direct

    match = AMAZON_SOLD_PATTERN.search(text)
    if not match:
        return None
    parsed = _num_or_none(match.group("number"))
    if parsed is None:
        return None
    suffix = _normalize_text(match.group("suffix"))
    if suffix.lower() == "k":
        parsed *= 1000.0
    return parsed


def _amazon_range(scrape: dict[str, str]) -> tuple[str, float, float | None]:
    raw_signal = _normalize_text(scrape.get("monthly_sold", ""))
    signal_floor = _parse_amazon_sold_floor(raw_signal)
    floor_column = _parse_amazon_sold_floor(scrape.get("amazon_bought_floor", ""))

    floor = signal_floor if signal_floor is not None else floor_column
    if floor is None or floor < 50:
        return "", 0.0, AMAZON_BLANK_CEILING

    signal = raw_signal or f"{_num_to_text(floor)}+ bought in past month"
    return signal, floor, None


def _pick_bbp_units(scrape: dict[str, str], backtest: dict[str, str]) -> float | None:
    for value in (
        scrape.get("bbp_sales_replay_demand_basis_units", ""),
        backtest.get("raw_monthly_units", ""),
        scrape.get("bbp_monthly_units_chosen", ""),
        backtest.get("qualified_monthly_units", ""),
    ):
        parsed = _num_or_none(value)
        if parsed is not None:
            return parsed
    return None


def _classify_primary_demand(
    *,
    amazon_floor: float,
    bbp_units: float | None,
    expected_units: float | None,
) -> str:
    demand_basis_values = [value for value in (bbp_units, expected_units) if value is not None]
    demand_basis = max(demand_basis_values) if demand_basis_values else 0.0

    if amazon_floor < 50:
        if demand_basis > AMAZON_BLANK_CEILING:
            return "amazon_blank_bbp_high"
        return "amazon_blank_bbp_low"

    bbp_basis = bbp_units if bbp_units is not None else expected_units
    if bbp_basis is None:
        bbp_basis = 0.0
    if bbp_basis <= AMAZON_50_REASONABLE_MAX:
        return "amazon_50_bbp_reasonable"
    if bbp_basis <= AMAZON_50_WARN_MAX:
        return "amazon_50_bbp_warn"
    return "amazon_50_bbp_inflated"


def _seller_stock_count_columns_found(frames: list[pd.DataFrame]) -> list[str]:
    found = {
        column
        for frame in frames
        for column in SELLER_STOCK_COUNT_COLUMNS
        if not frame.empty and column in frame.columns
    }
    return sorted(found)


def _seller_stock_missing_for_record(
    *,
    rows: list[dict[str, str]],
    seller_stock_columns_found: list[str],
) -> bool:
    if not seller_stock_columns_found:
        return True
    for column in seller_stock_columns_found:
        for row in rows:
            if column in row and not _value_is_missing(row.get(column, "")):
                return False
    return True


def _demand_evidence_source(scrape: dict[str, str], backtest: dict[str, str]) -> str:
    parts = ["f_screening_row_state_live.csv"]
    parts.append("feeder_legacy_scrape_evidence_live.csv" if scrape else "scrape_evidence_missing")
    parts.append("feeder_backtest_summary_live.csv" if backtest else "backtest_summary_missing")
    return "|".join(parts)


def _demand_classification(
    *,
    row_state: dict[str, str],
    first_checks: dict[str, str],
    scrape: dict[str, str],
    backtest: dict[str, str],
    expected_units: float | None,
    seller_stock_columns_found: list[str],
) -> DemandRangeClassification:
    _amazon_signal, amazon_floor, _amazon_ceiling = _amazon_range(scrape)
    bbp_units = _pick_bbp_units(scrape, backtest)
    primary_code = _classify_primary_demand(
        amazon_floor=amazon_floor,
        bbp_units=bbp_units,
        expected_units=expected_units,
    )
    supporting_codes = [primary_code]

    demand_risk = primary_code in DEMAND_RISK_CODES
    uk_reviews = _num_or_none(scrape.get("historical_uk_reviews", ""))
    if demand_risk and uk_reviews is not None and uk_reviews < WEAK_UK_REVIEW_THRESHOLD:
        supporting_codes.append("weak_uk_review_confirms_demand_risk")

    if demand_risk and _seller_stock_missing_for_record(
        rows=[row_state, first_checks, scrape, backtest],
        seller_stock_columns_found=seller_stock_columns_found,
    ):
        supporting_codes.append("seller_stock_missing_for_demand_check")

    deduped_supporting: list[str] = []
    for code in supporting_codes:
        if code and code not in deduped_supporting:
            deduped_supporting.append(code)

    return DemandRangeClassification(
        primary_code=primary_code,
        recommended_action=DEMAND_RECOMMENDED_ACTIONS[primary_code],
        supporting_codes=tuple(deduped_supporting),
        evidence_source=_demand_evidence_source(scrape, backtest),
    )


def _demand_values(demand: DemandRangeClassification) -> dict[str, str]:
    return {
        "demand_conflict_code": demand.primary_code,
        "demand_recommended_action": demand.recommended_action,
        "demand_supporting_codes": "|".join(demand.supporting_codes),
        "demand_evidence_source": demand.evidence_source,
    }


def _demand_routing_values(demand: DemandRangeClassification) -> tuple[str, str, str, str] | None:
    if demand.recommended_action == "remove_from_clean_pass":
        return (
            "demand_range_conflict",
            "remove_from_clean_pass",
            "DEMAND_RANGE_BLOCK",
            "remove_from_clean_pass_due_to_demand_range_conflict",
        )
    if demand.recommended_action == "manual_review":
        return (
            "demand_range_manual_review",
            "reviewable",
            "DEMAND_RANGE_WARN",
            "manual_review_due_to_demand_range_warning",
        )
    return None


def _recommendation_label(value: object) -> str:
    text = _normalize_key(value).replace("-", "_").replace(" ", "_")
    if text.startswith("EXIT"):
        return "EXIT_ONLY"
    if text.startswith("AVOID"):
        return "AVOID"
    if text.startswith("PASS"):
        return "PASS"
    if text.startswith("REVIEW"):
        return "REVIEW"
    if text.startswith("FAIL"):
        return "FAIL"
    return text


def _commercial_label(note: str, scrape: dict[str, str], backtest: dict[str, str]) -> str:
    labels: list[str] = []
    note_text = _normalize_text(note)
    for token in note_text.split("|"):
        label = _recommendation_label(token)
        if label in {"EXIT_ONLY", "AVOID"}:
            labels.append(label)
    if "EXIT_ONLY" in labels:
        return "EXIT_ONLY"
    if "AVOID" in labels:
        return "AVOID"
    for candidate in (
        scrape.get("opportunity_recommendation", ""),
        backtest.get("recommendation", ""),
    ):
        label = _recommendation_label(candidate)
        if label in {"EXIT_ONLY", "AVOID"}:
            labels.append(label)
    if "EXIT_ONLY" in labels:
        return "EXIT_ONLY"
    if "AVOID" in labels:
        return "AVOID"
    return _recommendation_label(note_text)


def _history_evidence_source(scrape: dict[str, str], backtest: dict[str, str]) -> str:
    parts = ["f_screening_row_state_live.csv"]
    parts.append("feeder_legacy_scrape_evidence_live.csv" if scrape else "scrape_evidence_missing")
    parts.append("feeder_backtest_summary_live.csv" if backtest else "backtest_summary_missing")
    return "|".join(parts)


def _parse_phase_series(value: object) -> list[tuple[date, str]]:
    records: list[tuple[date, str]] = []
    for part in _normalize_text(value).split(";"):
        if "=" not in part:
            continue
        raw_day, raw_phase = part.split("=", 1)
        parsed = pd.to_datetime(raw_day, errors="coerce")
        phase = _normalize_text(raw_phase).lower()
        if pd.isna(parsed) or phase == "":
            continue
        records.append((parsed.date(), phase))
    return records


def _parse_price_series(value: object) -> list[tuple[date, float]]:
    records: list[tuple[date, float]] = []
    for part in _normalize_text(value).split(";"):
        if "=" not in part:
            continue
        raw_day, raw_price = part.split("=", 1)
        parsed = pd.to_datetime(raw_day, errors="coerce")
        price = _num_or_none(raw_price)
        if pd.isna(parsed) or price is None or price <= 0:
            continue
        records.append((parsed.date(), price))
    return records


def _pct(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round((part / total) * 100.0, 6)


def _phase_window_metrics(records: list[tuple[date, str]], *, anchor: date | None, days: int) -> dict[str, float | int | None]:
    if anchor is None:
        return {"days": 0, "profit_pct": None, "loss_pct": None, "weak_pct": None}
    start = anchor - timedelta(days=days - 1)
    values = [phase for observed_day, phase in records if observed_day >= start]
    total = len(values)
    loss = sum(1 for phase in values if phase == "loss")
    weak = sum(1 for phase in values if phase in {"loss", "low_roi", "break_even"})
    profit = sum(1 for phase in values if phase == "profit")
    return {"days": total, "profit_pct": _pct(profit, total), "loss_pct": _pct(loss, total), "weak_pct": _pct(weak, total)}


def _amazon_window_metrics(
    records: list[tuple[date, float]],
    *,
    break_even: float | None,
    anchor: date | None,
    days: int,
) -> dict[str, float | int | None]:
    if break_even is None or break_even <= 0 or anchor is None:
        return {"days": 0, "below_be_pct": None, "good_above_be20_pct": None}
    start = anchor - timedelta(days=days - 1)
    values = [price for observed_day, price in records if observed_day >= start]
    total = len(values)
    below = sum(1 for price in values if price < break_even)
    good = sum(1 for price in values if price >= break_even * 1.2)
    return {"days": total, "below_be_pct": _pct(below, total), "good_above_be20_pct": _pct(good, total)}


def _history_rule_metrics(scrape: dict[str, str]) -> dict[str, float | int | None]:
    phase_records = _parse_phase_series(scrape.get("chart_phase_daily_series", ""))
    amazon_records = _parse_price_series(scrape.get("chart_raw_amazon_daily_series", ""))
    phase_anchor = max((observed_day for observed_day, _ in phase_records), default=None)
    amazon_anchor = max(
        [observed_day for observed_day, _ in phase_records] + [observed_day for observed_day, _ in amazon_records],
        default=None,
    )
    break_even = _num_or_none(scrape.get("break_even", ""))

    metrics: dict[str, float | int | None] = {
        "phase_records": len(phase_records),
        "amazon_price_days": len(amazon_records),
    }
    for days in (180, 90, 30):
        window = _phase_window_metrics(phase_records, anchor=phase_anchor, days=days)
        metrics[f"phase_profit_pct_{days}d"] = window["profit_pct"]
        metrics[f"phase_loss_pct_{days}d"] = window["loss_pct"]
        metrics[f"phase_weak_pct_{days}d"] = window["weak_pct"]
        metrics[f"phase_days_{days}d"] = window["days"]

    for days in (365, 90):
        window = _amazon_window_metrics(amazon_records, break_even=break_even, anchor=amazon_anchor, days=days)
        metrics[f"amazon_days_{days}d"] = window["days"]
        metrics[f"amazon_below_be_pct_{days}d"] = window["below_be_pct"]
        metrics[f"amazon_good_above_be20_pct_{days}d"] = window["good_above_be20_pct"]
    return metrics


def _metric_float(metrics: dict[str, float | int | None], key: str) -> float | None:
    value = metrics.get(key)
    if value is None:
        return None
    return float(value)


def _metric_int(metrics: dict[str, float | int | None], key: str) -> int:
    value = metrics.get(key)
    if value is None:
        return 0
    return int(value)


def _avg_price_vs_break_even_pct(scrape: dict[str, str]) -> float | None:
    avg_price = _num_or_none(scrape.get("avg_30_day_price", ""))
    break_even = _num_or_none(scrape.get("break_even", ""))
    if avg_price is None or break_even is None or break_even <= 0:
        return None
    return ((avg_price - break_even) / break_even) * 100.0


def _recent_history_recovery_supported(
    scrape: dict[str, str],
    *,
    profit_per_unit: float | None,
) -> bool:
    if profit_per_unit is None or profit_per_unit < 3:
        return False
    metrics = _history_rule_metrics(scrape)
    if _metric_int(metrics, "phase_records") <= 0:
        return False

    phase_30_profit = _metric_float(metrics, "phase_profit_pct_30d")
    phase_30_loss = _metric_float(metrics, "phase_loss_pct_30d")
    phase_90_profit = _metric_float(metrics, "phase_profit_pct_90d")
    phase_90_loss = _metric_float(metrics, "phase_loss_pct_90d")
    phase_90_weak = _metric_float(metrics, "phase_weak_pct_90d")
    phase_180_profit = _metric_float(metrics, "phase_profit_pct_180d")
    phase_180_loss = _metric_float(metrics, "phase_loss_pct_180d")
    amazon_days_365 = _metric_int(metrics, "amazon_days_365d")
    amazon_days_90 = _metric_int(metrics, "amazon_days_90d")
    amazon_below_90 = _metric_float(metrics, "amazon_below_be_pct_90d")
    amazon_below_365 = _metric_float(metrics, "amazon_below_be_pct_365d") or 0.0
    amazon_good_90 = _metric_float(metrics, "amazon_good_above_be20_pct_90d")
    upside_pct = _avg_price_vs_break_even_pct(scrape)

    if (
        phase_90_profit is not None
        and phase_90_profit >= 95
        and phase_90_loss == 0
        and phase_90_weak is not None
        and phase_90_weak <= 5
        and phase_30_profit is not None
        and phase_30_profit >= 95
        and phase_30_loss == 0
    ):
        return True

    if (
        phase_30_profit is not None
        and phase_30_profit >= 95
        and phase_30_loss == 0
        and phase_180_profit is not None
        and phase_180_profit >= 70
        and phase_180_loss is not None
        and phase_180_loss <= 5
        and amazon_days_365 < 30
        and upside_pct is not None
        and upside_pct >= 40
    ):
        return True

    return (
        amazon_days_90 >= 20
        and amazon_below_90 == 0
        and amazon_good_90 is not None
        and amazon_good_90 >= 75
        and amazon_below_365 < 15
        and upside_pct is not None
        and upside_pct >= 30
    )


def _history_classification(
    *,
    scrape: dict[str, str],
    backtest: dict[str, str],
    commercial_note: str,
    profit_per_unit: float | None,
) -> HistoryRiskClassification:
    history_recommendation = _recommendation_label(scrape.get("history_recommendation", ""))
    phase_recommendation = _recommendation_label(scrape.get("phase_recommendation", ""))
    backtest_recommendation = _recommendation_label(backtest.get("recommendation", ""))
    commercial_label = _commercial_label(commercial_note, scrape, backtest)
    failure_event_count = _num_or_none(backtest.get("failure_event_count", ""))
    time_normal_sell_days = _num_or_none(backtest.get("time_normal_sell_days", ""))
    time_selloff_days = _num_or_none(backtest.get("time_selloff_days", ""))

    triggered_codes: list[str] = []
    recent_recovery_supported = _recent_history_recovery_supported(scrape, profit_per_unit=profit_per_unit)
    if history_recommendation == "FAIL" and phase_recommendation == "AVOID" and not recent_recovery_supported:
        triggered_codes.append("history_fail_phase_avoid")
    if backtest_recommendation == "AVOID" and commercial_label in {"AVOID", "EXIT_ONLY"}:
        triggered_codes.append("backtest_avoid_commercial_avoid_or_exit")
    if backtest_recommendation == "EXIT_ONLY" or commercial_label == "EXIT_ONLY":
        triggered_codes.append("exit_only_clean_pass")
    if failure_event_count is not None and failure_event_count >= 100:
        triggered_codes.append("failure_events_100_plus")
    if (
        time_normal_sell_days is not None
        and time_selloff_days is not None
        and time_selloff_days > time_normal_sell_days
    ):
        triggered_codes.append("selloff_days_exceed_normal_days")
    if not triggered_codes:
        triggered_codes.append("history_risk_clear")
    if recent_recovery_supported:
        triggered_codes.append("history_recent_recovery_override")

    deduped_codes: list[str] = []
    for code in sorted(triggered_codes, key=lambda item: HISTORY_RULE_PRIORITY.get(item, 999)):
        if code not in deduped_codes:
            deduped_codes.append(code)

    primary_code = deduped_codes[0]
    return HistoryRiskClassification(
        primary_code=primary_code,
        recommended_action=HISTORY_RECOMMENDED_ACTIONS[primary_code],
        supporting_codes=tuple(deduped_codes),
        evidence_source=_history_evidence_source(scrape, backtest),
    )


def _history_values(history: HistoryRiskClassification) -> dict[str, str]:
    return {
        "history_risk_code": history.primary_code,
        "history_recommended_action": history.recommended_action,
        "history_supporting_codes": "|".join(history.supporting_codes),
        "history_evidence_source": history.evidence_source,
    }


def _history_routing_values(history: HistoryRiskClassification) -> tuple[str, str, str, str] | None:
    if history.recommended_action == "remove_from_clean_pass":
        return (
            "history_risk_conflict",
            "remove_from_clean_pass",
            "HISTORY_RISK_BLOCK",
            "remove_from_clean_pass_due_to_history_risk_conflict",
        )
    if history.recommended_action == "manual_review":
        return (
            "history_risk_manual_review",
            "reviewable",
            "HISTORY_RISK_WARN",
            "manual_review_due_to_history_risk_warning",
        )
    return None


def _uk_review_evidence_source(scrape: dict[str, str]) -> str:
    return (
        "feeder_legacy_scrape_evidence_live.csv:historical_uk_reviews"
        if _normalize_text(scrape.get("historical_uk_reviews", "")) != ""
        else "feeder_legacy_scrape_evidence_live.csv:historical_uk_reviews_missing"
    )


def _classify_uk_review_code(uk_reviews: float | None) -> str:
    if uk_reviews is None:
        return "uk_reviews_missing"
    if uk_reviews < VERY_WEAK_UK_REVIEW_THRESHOLD:
        return "uk_reviews_lt3"
    if uk_reviews < WEAK_UK_REVIEW_THRESHOLD:
        return "uk_reviews_3_to_5"
    if uk_reviews < STRONG_UK_REVIEW_THRESHOLD:
        return "uk_reviews_6_to_9"
    return "uk_reviews_10_plus"


def _uk_review_classification(*, scrape: dict[str, str]) -> UkReviewClassification:
    uk_reviews = _num_or_none(scrape.get("historical_uk_reviews", ""))
    primary_code = _classify_uk_review_code(uk_reviews)
    return UkReviewClassification(
        primary_code=primary_code,
        recommended_action=UK_REVIEW_RECOMMENDED_ACTIONS[primary_code],
        supporting_codes=(primary_code,),
        evidence_source=_uk_review_evidence_source(scrape),
    )


def _uk_review_values(uk_review: UkReviewClassification) -> dict[str, str]:
    return {
        "uk_review_code": uk_review.primary_code,
        "uk_review_recommended_action": uk_review.recommended_action,
        "uk_review_supporting_codes": "|".join(uk_review.supporting_codes),
        "uk_review_evidence_source": uk_review.evidence_source,
    }


def _uk_review_routing_values(uk_review: UkReviewClassification) -> tuple[str, str, str, str] | None:
    if uk_review.recommended_action == "remove_from_clean_pass":
        return (
            "uk_review_conflict",
            "remove_from_clean_pass",
            "UK_REVIEW_BLOCK",
            "remove_from_clean_pass_due_to_uk_review_signal",
        )
    if uk_review.recommended_action == "manual_review":
        return (
            "uk_review_manual_review",
            "reviewable",
            "UK_REVIEW_WARN",
            "manual_review_due_to_weak_uk_review_signal",
        )
    if uk_review.recommended_action == "targeted_rescan_needed":
        return (
            "uk_review_targeted_rescan_needed",
            "targeted_rescan_needed",
            "UK_REVIEW_MISSING",
            "targeted_rescan_needed_due_to_missing_uk_review_signal",
        )
    return None


def _profit_evidence_source(profit_fields: dict[str, str], expected_profit: float | None, per_unit_profit: float | None) -> str:
    if _normalize_text(profit_fields.get("profit_evidence_source", "")):
        return _normalize_text(profit_fields.get("profit_evidence_source", ""))
    sources: list[str] = []
    if expected_profit is not None:
        sources.append("feeder_backtest_summary_live.csv:expected_profit_next_30d_gbp")
    if per_unit_profit is not None:
        sources.append("feeder_legacy_scrape_evidence_live.csv:profit_per_unit_30d")
    return "|".join(sources)


def _profit_classification(
    *,
    profit_fields: dict[str, str],
    expected_profit: float | None,
    per_unit_profit: float | None,
) -> ProfitRoutingClassification:
    audit_code = _normalize_text(profit_fields.get("profit_formula_code", ""))
    audit_action = _normalize_text(profit_fields.get("profit_recommended_action", ""))
    supporting: list[str] = []

    if audit_code:
        primary_code = audit_code
        recommended_action = audit_action or PROFIT_RECOMMENDED_ACTIONS.get(primary_code, "manual_review")
        supporting.append(primary_code)
    elif per_unit_profit is not None and per_unit_profit <= 0:
        primary_code = "profit_too_weak"
        recommended_action = "remove_from_clean_pass"
        supporting.append("non_positive_profit_per_unit")
    elif expected_profit is not None and expected_profit < DEFAULT_NEAR_MISS_PROFIT_FLOOR_GBP:
        primary_code = "profit_too_weak"
        recommended_action = "remove_from_clean_pass"
        supporting.append("expected_profit_below_near_miss_floor")
    elif expected_profit is not None and expected_profit < DEFAULT_PROFIT_FLOOR_GBP:
        primary_code = "profit_low_upside_manual_review"
        recommended_action = "manual_review"
        supporting.append("expected_profit_below_clean_pass_floor")
    else:
        primary_code = "profit_clear"
        recommended_action = "allow_if_other_checks_pass"
        supporting.append(primary_code)

    return ProfitRoutingClassification(
        primary_code=primary_code,
        recommended_action=recommended_action,
        supporting_codes=tuple(supporting),
        evidence_source=_profit_evidence_source(profit_fields, expected_profit, per_unit_profit),
    )


def _profit_routing_values(profit: ProfitRoutingClassification) -> tuple[str, str, str, str] | None:
    if profit.recommended_action == "remove_from_clean_pass":
        return (
            "profit_conflict",
            "remove_from_clean_pass",
            "PROFIT_BLOCK",
            "remove_from_clean_pass_due_to_profit_or_upside_risk",
        )
    if profit.recommended_action == "manual_review":
        return (
            "profit_manual_review",
            "reviewable",
            "PROFIT_WARN",
            "manual_review_due_to_profit_or_upside_risk",
        )
    if profit.recommended_action == "targeted_rescan_needed":
        return (
            "profit_targeted_rescan_needed",
            "targeted_rescan_needed",
            "PROFIT_MISSING",
            "targeted_rescan_needed_due_to_missing_profit_inputs",
        )
    return None


def _seller_history_evidence_source(scrape: dict[str, str]) -> str:
    required = ("price_hist_new_30", "price_hist_new_90", "price_hist_new_180")
    seller_names = _normalize_text(scrape.get("bbp_top_seller_names", ""))
    source = "feeder_legacy_scrape_evidence_live.csv:price_hist_new_30_90_180"
    if seller_names:
        source = f"{source}+bbp_top_seller_names"
    if all(_normalize_text(scrape.get(column, "")) != "" for column in required):
        return source
    return f"{source}_missing"


def _seller_history_classification(*, scrape: dict[str, str]) -> SellerHistoryClassification:
    new_30 = _num_or_none(scrape.get("price_hist_new_30", ""))
    new_90 = _num_or_none(scrape.get("price_hist_new_90", ""))
    new_180 = _num_or_none(scrape.get("price_hist_new_180", ""))
    dashboard_yes_or_no = _normalize_text(scrape.get("bbp_dashboard_yes_or_no", "")).upper()
    dashboard_delivery = _normalize_text(scrape.get("bbp_dashboard_delivery_classification", ""))
    if dashboard_delivery == "":
        dashboard_delivery = dashboard_delivery_classification(dashboard_yes_or_no)
    dashboard_delivery_required = _normalize_text(scrape.get("bbp_dashboard_separate_delivery_required", ""))
    if dashboard_delivery_required == "":
        dashboard_delivery_required = "1" if dashboard_separate_delivery_required(dashboard_yes_or_no) else "0"
    top_seller_names = _normalize_text(scrape.get("bbp_top_seller_names", ""))
    brand_match_seller = _normalize_text(scrape.get("bbp_brand_match_seller", ""))
    brand_match_flag = _normalize_text(scrape.get("bbp_brand_match_flag", "")).lower() in {"true", "1", "yes"}
    brand_match_score = _num_or_none(scrape.get("bbp_brand_match_score", ""))
    rank_1_seller_name = _normalize_text(scrape.get("bbp_seller_rank_1_name", ""))
    if rank_1_seller_name == "" and top_seller_names:
        rank_1_seller_name = _normalize_text(top_seller_names.split("|", 1)[0])
    rank_1_brand_match_flag = _normalize_text(scrape.get("bbp_seller_rank_1_brand_match_flag", "")).lower() in {
        "true",
        "1",
        "yes",
    }
    if not rank_1_brand_match_flag and rank_1_seller_name and brand_match_seller:
        rank_1_brand_match_flag = _normalize_key(rank_1_seller_name) == _normalize_key(brand_match_seller)
    buybox_seller_name = _normalize_text(scrape.get("amazon_buybox_seller_name", ""))
    buybox_brand_match_flag = _normalize_text(scrape.get("amazon_buybox_brand_match_flag", "")).lower() in {
        "true",
        "1",
        "yes",
    }
    buybox_brand_match_score = _num_or_none(scrape.get("amazon_buybox_brand_match_score", ""))
    values = [new_30, new_90, new_180]
    if all(value is not None for value in values):
        max_sellers = max(float(value) for value in values if value is not None)
        if (rank_1_brand_match_flag and rank_1_seller_name) or (buybox_brand_match_flag and buybox_seller_name):
            primary_code = "brand_owner_top_seller" if max_sellers >= 2.0 else "brand_owner_single_seller"
        elif dashboard_yes_or_no == "NO" and max_sellers < 2.0:
            primary_code = "dashboard_no_low_seller_count"
        elif dashboard_yes_or_no == "NO":
            primary_code = "dashboard_no_multi_seller_count"
        elif max_sellers < 2.0:
            amazon_values = [
                _num_or_none(scrape.get("price_hist_amazon_30", "")),
                _num_or_none(scrape.get("price_hist_amazon_90", "")),
                _num_or_none(scrape.get("price_hist_amazon_180", "")),
            ]
            fba_values = [
                _num_or_none(scrape.get("price_hist_fba_30", "")),
                _num_or_none(scrape.get("price_hist_fba_90", "")),
                _num_or_none(scrape.get("price_hist_fba_180", "")),
            ]
            buy_box_values = [
                _num_or_none(scrape.get("price_hist_buy_box_30", "")),
                _num_or_none(scrape.get("price_hist_buy_box_90", "")),
                _num_or_none(scrape.get("price_hist_buy_box_180", "")),
            ]
            amazon_present = any(value is not None and value > 0 for value in amazon_values)
            fba_present = any(value is not None and value > 0 for value in fba_values)
            buy_box_present = any(value is not None and value > 0 for value in buy_box_values)
            if (rank_1_brand_match_flag and rank_1_seller_name) or (buybox_brand_match_flag and buybox_seller_name):
                primary_code = "brand_owner_single_seller"
            elif amazon_present and not fba_present:
                primary_code = "amazon_only_single_seller"
            elif not amazon_present and fba_present and buy_box_present:
                primary_code = "single_fba_seller_amazon_absent"
            else:
                primary_code = "single_seller_owner_unclear"
        else:
            primary_code = "seller_history_clear"
    else:
        primary_code = "seller_history_missing"
    return SellerHistoryClassification(
        primary_code=primary_code,
        recommended_action=SELLER_HISTORY_RECOMMENDED_ACTIONS[primary_code],
        supporting_codes=(primary_code,),
        evidence_source=_seller_history_evidence_source(scrape),
        new_30=new_30,
        new_90=new_90,
        new_180=new_180,
        dashboard_yes_or_no=dashboard_yes_or_no,
        dashboard_delivery_classification=dashboard_delivery,
        dashboard_separate_delivery_required=dashboard_delivery_required,
        top_seller_names=top_seller_names,
        brand_match_seller=brand_match_seller,
        brand_match_score=brand_match_score,
        rank_1_seller_name=rank_1_seller_name,
        rank_1_brand_match_flag="True" if rank_1_brand_match_flag else "False",
        buybox_seller_name=buybox_seller_name,
        buybox_brand_match_score=buybox_brand_match_score,
    )


def _seller_history_values(seller_history: SellerHistoryClassification) -> dict[str, str]:
    return {
        "seller_history_code": seller_history.primary_code,
        "seller_history_recommended_action": seller_history.recommended_action,
        "seller_history_supporting_codes": "|".join(seller_history.supporting_codes),
        "seller_history_evidence_source": seller_history.evidence_source,
        "seller_history_new_30": _num_to_text(seller_history.new_30),
        "seller_history_new_90": _num_to_text(seller_history.new_90),
        "seller_history_new_180": _num_to_text(seller_history.new_180),
        "seller_history_dashboard_yes_or_no": seller_history.dashboard_yes_or_no,
        "seller_history_dashboard_delivery_classification": seller_history.dashboard_delivery_classification,
        "seller_history_dashboard_separate_delivery_required": seller_history.dashboard_separate_delivery_required,
        "seller_history_top_seller_names": seller_history.top_seller_names,
        "seller_history_brand_match_seller": seller_history.brand_match_seller,
        "seller_history_brand_match_score": _num_to_text(seller_history.brand_match_score),
        "seller_history_rank_1_seller_name": seller_history.rank_1_seller_name,
        "seller_history_rank_1_brand_match_flag": seller_history.rank_1_brand_match_flag,
        "seller_history_buybox_seller_name": seller_history.buybox_seller_name,
        "seller_history_buybox_brand_match_score": _num_to_text(seller_history.buybox_brand_match_score),
    }


def _seller_history_routing_values(seller_history: SellerHistoryClassification) -> tuple[str, str, str, str] | None:
    if seller_history.recommended_action == "remove_from_clean_pass":
        if seller_history.primary_code == "dashboard_no_low_seller_count":
            return (
                "seller_history_dashboard_no_conflict",
                "remove_from_clean_pass",
                "SELLER_HISTORY_DASHBOARD_NO_LOW_SELLERS",
                "remove_from_clean_pass_due_to_dashboard_no_and_low_seller_count",
            )
        if seller_history.primary_code in {"brand_owner_single_seller", "brand_owner_top_seller"}:
            return (
                "seller_history_brand_owner_conflict",
                "remove_from_clean_pass",
                "BRAND_OWNER_TOP_SELLER",
                "remove_from_clean_pass_due_to_top_seller_matching_brand",
            )
        return (
            "seller_history_amazon_only_conflict",
            "remove_from_clean_pass",
            "SELLER_HISTORY_AMAZON_ONLY_BLOCK",
            "remove_from_clean_pass_due_to_amazon_only_single_seller_history",
        )
    if seller_history.recommended_action == "manual_review":
        return (
            "seller_history_manual_review",
            "reviewable",
            "SELLER_HISTORY_OWNER_UNCLEAR",
            "manual_review_due_to_unclear_single_seller_ownership",
        )
    return None


def _low_sales_routing_values(expected_units: float | None) -> tuple[str, str, str, str] | None:
    if expected_units is None or expected_units > LOW_SALES_CLEAN_PASS_MAX_UNITS:
        return None
    return (
        "low_sales_capital_idle_risk",
        "remove_from_clean_pass",
        "LOW_SALES_CAPITAL_IDLE_RISK",
        "remove_from_clean_pass_due_to_low_sales_capital_idle_risk",
    )


def _rank_routing_values(main_rank: str) -> tuple[str, str, str, str] | None:
    rank = _num_or_none(main_rank)
    if rank is None or rank <= MAIN_RANK_CLEAN_PASS_MAX:
        return None
    return (
        "rank_over_50k_review_pack_gate",
        "remove_from_clean_pass",
        "OVER50K_REVIEW_PACK_GATE",
        "remove_from_clean_pass_due_to_rank_over_50k",
    )


def _select_pass_routing(
    *,
    main_rank: str,
    expected_units: float | None,
    title_match_fields: dict[str, str],
    identity: IdentityMatchClassification,
    profit: ProfitRoutingClassification,
    demand: DemandRangeClassification,
    history: HistoryRiskClassification,
    uk_review: UkReviewClassification,
    seller_history: SellerHistoryClassification,
) -> tuple[str, str, str, str, str, str] | None:
    candidates: list[tuple[str, str, str, str, str, str]] = []
    title_match_route = _title_match_routing_values(title_match_fields)
    if title_match_route is not None:
        candidates.append(
            (
                "title_match",
                title_match_fields.get("title_match_action", ""),
                title_match_fields.get("title_match_reason_code", ""),
                *title_match_route,
            )
        )
    identity_route = _identity_routing_values(identity)
    if identity_route is not None:
        candidates.append(("identity", identity.recommended_action, identity.primary_code, *identity_route))
    rank_route = _rank_routing_values(main_rank)
    if rank_route is not None:
        candidates.append(("rank", "remove_from_clean_pass", "rank_over_50k_review_pack_gate", *rank_route))
    low_sales_route = _low_sales_routing_values(expected_units)
    if low_sales_route is not None:
        candidates.append(("low_sales", "remove_from_clean_pass", "low_sales_capital_idle_risk", *low_sales_route))
    profit_route = _profit_routing_values(profit)
    if profit_route is not None:
        candidates.append(("profit", profit.recommended_action, profit.primary_code, *profit_route))
    demand_route = _demand_routing_values(demand)
    if demand_route is not None:
        candidates.append(("demand", demand.recommended_action, demand.primary_code, *demand_route))
    history_route = _history_routing_values(history)
    if history_route is not None:
        candidates.append(("history", history.recommended_action, history.primary_code, *history_route))
    uk_review_route = _uk_review_routing_values(uk_review)
    if uk_review_route is not None:
        candidates.append(("uk_review", uk_review.recommended_action, uk_review.primary_code, *uk_review_route))
    seller_history_route = _seller_history_routing_values(seller_history)
    if seller_history_route is not None:
        candidates.append(
            ("seller_history", seller_history.recommended_action, seller_history.primary_code, *seller_history_route)
        )
    if not candidates:
        return None

    source_priority = {
        "title_match": 0,
        "identity": 1,
        "seller_history": 2,
        "history": 3,
        "profit": 4,
        "demand": 5,
        "uk_review": 6,
        "rank": 7,
        "low_sales": 8,
    }
    best = min(
        candidates,
        key=lambda item: (
            ROUTING_ACTION_PRIORITY.get(item[1], 999),
            source_priority.get(item[0], 99),
            item[2],
        ),
    )
    source, _action, status_reason, near_miss_type, reviewability_state, fail_code, recovery_hint = best
    return source, near_miss_type, reviewability_state, fail_code, recovery_hint, status_reason


def _increment(counter: dict[str, int], key: str) -> None:
    if key == "":
        return
    counter[key] = counter.get(key, 0) + 1


def _batch_id(prefix: str, index: int, batch_size: int) -> str:
    batch_num = int(index / max(batch_size, 1)) + 1
    return f"{prefix}_{batch_num:03d}"


def build_live_price_file_near_miss_pack(
    *,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
    row_state_path: Path = DEFAULT_ROW_STATE_PATH,
    first_checks_path: Path = DEFAULT_FIRST_CHECKS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    page_evidence_backfill_results_path: Path | None = None,
    backtest_summary_path: Path = DEFAULT_BACKTEST_SUMMARY_PATH,
    profit_audit_path: Path = DEFAULT_PROFIT_AUDIT_PATH,
    review_events_path: Path | None = None,
    supplier_inbox_dir: Path = DEFAULT_SUPPLIER_INBOX_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
    review_batch_size: int = DEFAULT_REVIEW_BATCH_SIZE,
    active_supplier_id: str = "",
    active_run_id: str = "",
    source_seen_at_utc_override: str = "",
    write_sql_snapshots: bool = True,
) -> LivePriceFileReviewPackResult:
    observed_utc_value = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(observed_utc_value)
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_df = _read_csv(baseline_path)
    baseline_row = baseline_df.iloc[0].to_dict() if not baseline_df.empty else {}
    active_supplier_id = _normalize_text(active_supplier_id) or _normalize_text(baseline_row.get("active_supplier_id", ""))
    active_run_id = _normalize_text(active_run_id) or _normalize_text(baseline_row.get("active_run_id", ""))

    row_state_df = _read_csv(row_state_path)
    row_state_source_rows = int(len(row_state_df.index))
    if not row_state_df.empty and "supplier_id" in row_state_df.columns:
        row_state_df = row_state_df.loc[row_state_df["supplier_id"].map(_normalize_key) == _normalize_key(active_supplier_id)].copy()
    row_state_supplier_rows = int(len(row_state_df.index))
    if active_run_id and not row_state_df.empty and "run_id" in row_state_df.columns:
        row_state_df = row_state_df.loc[row_state_df["run_id"].map(_normalize_key) == _normalize_key(active_run_id)].copy()
    row_state_window_rows = int(len(row_state_df.index))

    pass_path = output_dir / f"f_live_price_file_pass_review_{ts_slug}.csv"
    pass_latest_path = output_dir / "f_live_price_file_pass_review_latest.csv"
    near_miss_path = output_dir / f"f_live_price_file_near_miss_review_{ts_slug}.csv"
    near_miss_latest_path = output_dir / "f_live_price_file_near_miss_review_latest.csv"
    summary_path = output_dir / f"f_live_price_file_review_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "f_live_price_file_review_summary_latest.csv"

    existing_pass_df = _read_csv(pass_latest_path)
    existing_near_miss_df = _read_csv(near_miss_latest_path)
    existing_review_rows = int(len(existing_pass_df.index) + len(existing_near_miss_df.index))
    if row_state_window_rows == 0 and existing_review_rows > 0:
        summary_df = pd.DataFrame(
            [
                {"observed_utc": observed_utc_value, "metric": "f019_write_state", "value": "blocked_source_window_empty"},
                {"observed_utc": observed_utc_value, "metric": "active_supplier_id", "value": active_supplier_id},
                {"observed_utc": observed_utc_value, "metric": "active_run_id", "value": active_run_id},
                {"observed_utc": observed_utc_value, "metric": "row_state_source_rows", "value": _num_to_text(row_state_source_rows)},
                {
                    "observed_utc": observed_utc_value,
                    "metric": "row_state_supplier_rows",
                    "value": _num_to_text(row_state_supplier_rows),
                },
                {"observed_utc": observed_utc_value, "metric": "row_state_window_rows", "value": "0"},
                {
                    "observed_utc": observed_utc_value,
                    "metric": "preserved_existing_pass_review_rows",
                    "value": _num_to_text(len(existing_pass_df.index)),
                },
                {
                    "observed_utc": observed_utc_value,
                    "metric": "preserved_existing_near_miss_review_rows",
                    "value": _num_to_text(len(existing_near_miss_df.index)),
                },
            ],
            columns=SUMMARY_COLUMNS,
        )
        report = {
            "status": "blocked_source_window_empty",
            "observed_utc": observed_utc_value,
            "active_supplier_id": active_supplier_id,
            "active_run_id": active_run_id,
            "row_state_source_rows": row_state_source_rows,
            "row_state_supplier_rows": row_state_supplier_rows,
            "row_state_window_rows": row_state_window_rows,
            "preserved_existing_pass_review_rows": int(len(existing_pass_df.index)),
            "preserved_existing_near_miss_review_rows": int(len(existing_near_miss_df.index)),
            "block_reason": (
                "selected supplier/run has zero row_state rows; "
                "existing non-empty review outputs were preserved"
            ),
            "pass_latest_path": str(pass_latest_path),
            "near_miss_latest_path": str(near_miss_latest_path),
            "summary_latest_path": str(summary_latest_path),
        }
        return LivePriceFileReviewPackResult(
            pass_df=existing_pass_df,
            near_miss_df=existing_near_miss_df,
            summary_df=summary_df,
            pass_path=pass_path,
            pass_latest_path=pass_latest_path,
            near_miss_path=near_miss_path,
            near_miss_latest_path=near_miss_latest_path,
            summary_path=summary_path,
            summary_latest_path=summary_latest_path,
            report=report,
        )

    first_checks_df = _read_csv(first_checks_path)
    scrape_df = _read_csv(scrape_evidence_path)
    if not scrape_df.empty and "supplier_id" in scrape_df.columns:
        scrape_df = scrape_df.loc[scrape_df["supplier_id"].map(_normalize_key) == _normalize_key(active_supplier_id)].copy()
    if active_run_id and not scrape_df.empty and "run_id" in scrape_df.columns:
        scrape_df = scrape_df.loc[scrape_df["run_id"].map(_normalize_key) == _normalize_key(active_run_id)].copy()
    backtest_df = _read_csv(backtest_summary_path)
    profit_audit_df = _read_csv(profit_audit_path)
    review_events_df = _read_review_events(review_events_path) if review_events_path is not None else pd.DataFrame()
    (
        page_evidence_backfill_source_rows,
        page_evidence_backfill_usable_rows,
        page_evidence_backfill_by_supplier_asin,
        page_evidence_backfill_by_asin,
    ) = _build_page_evidence_backfill_indexes(page_evidence_backfill_results_path)
    seller_stock_columns_found = _seller_stock_count_columns_found([row_state_df, first_checks_df, scrape_df, backtest_df])
    source_seen_at_utc = ""
    for source_df in (row_state_df, first_checks_df, scrape_df):
        if source_df.empty or "source_seen_at_utc" not in source_df.columns:
            continue
        values = [_normalize_text(value) for value in source_df["source_seen_at_utc"].tolist()]
        source_seen_at_utc = next((value for value in values if value), "")
        if source_seen_at_utc:
            break
    source_seen_at_utc = _normalize_text(source_seen_at_utc_override) or source_seen_at_utc
    price_file_batch_id = _normalize_text(source_seen_at_utc).replace(":", "").replace("-", "")
    if price_file_batch_id:
        price_file_batch_id = f"{active_supplier_id}_{price_file_batch_id}"

    first_checks_candidate_base_df = first_checks_df.copy()
    if not first_checks_candidate_base_df.empty:
        first_checks_candidate_base_df["candidate_id_base"] = first_checks_candidate_base_df.get("candidate_id", "").map(
            _candidate_id_base
        )
    first_checks_by_candidate = _latest_by_keys(first_checks_df, ["candidate_id"], ["scan_day", "completed"])
    first_checks_by_candidate_base = _latest_by_keys(first_checks_candidate_base_df, ["candidate_id_base"], ["scan_day", "completed"])
    first_checks_by_supplier_asin = _latest_by_keys(first_checks_df, ["supplier_sku", "asin"], ["scan_day", "completed"])
    scrape_by_candidate = _latest_by_keys(scrape_df, ["candidate_id"], ["observed_utc", "scan_day"])
    scrape_by_supplier_asin = _latest_by_keys(scrape_df, ["supplier_sku", "asin"], ["observed_utc", "scan_day"])
    backtest_by_supplier_asin = _latest_by_keys(backtest_df, ["seller_sku", "asin"], ["observed_utc"])
    backtest_by_asin = _latest_by_keys(backtest_df, ["asin"], ["observed_utc"])
    profit_by_pack_candidate = _latest_by_keys(profit_audit_df, ["review_pack_type", "candidate_id"], ["observed_utc"])
    profit_by_pack_asin = _latest_by_keys(profit_audit_df, ["review_pack_type", "asin"], ["observed_utc"])
    profit_by_candidate = _latest_by_keys(profit_audit_df, ["candidate_id"], ["observed_utc"])
    profit_by_asin = _latest_by_keys(profit_audit_df, ["asin"], ["observed_utc"])
    (
        review_event_by_pack_candidate,
        review_event_by_pack_asin,
        review_event_by_candidate,
        review_event_by_asin,
    ) = _build_latest_review_event_index(review_events_df)
    supplier_title_index = _load_supplier_title_index(supplier_inbox_dir, active_supplier_id)

    pass_rows: list[dict[str, str]] = []
    timeout_review_rows: list[dict[str, str]] = []
    hard_reject_count = 0
    hard_reject_by_fail: dict[str, int] = {}
    title_match_action_counts: dict[str, int] = {}
    title_match_decision_bucket_counts: dict[str, int] = {}
    title_match_routed_remove_from_clean_pass_count = 0
    title_match_routed_manual_review_count = 0
    identity_action_counts: dict[str, int] = {}
    identity_supporting_code_counts: dict[str, int] = {}
    identity_routed_remove_from_clean_pass_count = 0
    identity_routed_manual_review_count = 0
    profit_action_counts: dict[str, int] = {}
    profit_supporting_code_counts: dict[str, int] = {}
    profit_routed_remove_from_clean_pass_count = 0
    profit_routed_manual_review_count = 0
    profit_routed_targeted_rescan_needed_count = 0
    demand_action_counts: dict[str, int] = {}
    demand_supporting_code_counts: dict[str, int] = {}
    demand_routed_remove_from_clean_pass_count = 0
    demand_routed_manual_review_count = 0
    history_action_counts: dict[str, int] = {}
    history_supporting_code_counts: dict[str, int] = {}
    history_routed_remove_from_clean_pass_count = 0
    history_routed_manual_review_count = 0
    uk_review_action_counts: dict[str, int] = {}
    uk_review_supporting_code_counts: dict[str, int] = {}
    uk_review_routed_remove_from_clean_pass_count = 0
    uk_review_routed_manual_review_count = 0
    uk_review_routed_targeted_rescan_needed_count = 0
    seller_history_action_counts: dict[str, int] = {}
    seller_history_supporting_code_counts: dict[str, int] = {}
    seller_history_routed_remove_from_clean_pass_count = 0
    seller_history_routed_manual_review_count = 0
    rank_routed_remove_from_clean_pass_count = 0
    low_sales_routed_remove_from_clean_pass_count = 0
    review_memory_routed_remove_from_clean_pass_count = 0
    page_evidence_backfill_used_count = 0

    for _, row in row_state_df.iterrows():
        row_state_record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        candidate_id = _normalize_text(row.get("candidate_id", ""))
        supplier_sku = _normalize_text(row.get("supplier_sku", ""))
        asin = _normalize_text(row.get("asin", ""))
        candidate_key = (_normalize_key(candidate_id),)
        candidate_base_key = (_normalize_key(_candidate_id_base(candidate_id)),)
        supplier_asin_key = (_normalize_key(supplier_sku), _normalize_key(asin))
        asin_key = (_normalize_key(asin),)

        first_checks = _lookup_with_fallback(first_checks_by_candidate, candidate_key, first_checks_by_supplier_asin, supplier_asin_key)
        if not first_checks and candidate_base_key[0] != "" and candidate_base_key != candidate_key:
            first_checks = _lookup_with_fallback(
                first_checks_by_candidate_base,
                candidate_base_key,
                first_checks_by_supplier_asin,
                supplier_asin_key,
            )
        scrape = _lookup_with_fallback(scrape_by_candidate, candidate_key, scrape_by_supplier_asin, supplier_asin_key)
        page_evidence_backfill = _lookup_with_fallback(
            page_evidence_backfill_by_supplier_asin,
            supplier_asin_key,
            page_evidence_backfill_by_asin,
            asin_key,
        )
        backtest = _lookup_with_fallback(backtest_by_supplier_asin, supplier_asin_key, backtest_by_asin, asin_key)
        audit_pack_type = "passes" if _normalize_text(row.get("row_status", "")) == "pass" else "near_misses"
        profit_record = _lookup_with_fallback(
            profit_by_pack_candidate,
            (_normalize_key(audit_pack_type), _normalize_key(candidate_id)),
            profit_by_pack_asin,
            (_normalize_key(audit_pack_type), _normalize_key(asin)),
        )
        if not profit_record:
            profit_record = _lookup_with_fallback(
                profit_by_candidate,
                (_normalize_key(candidate_id),),
                profit_by_asin,
                (_normalize_key(asin),),
            )
        profit_fields = _profit_audit_values(profit_record)

        title = (
            _normalize_text(first_checks.get("title", ""))
            or _normalize_text(scrape.get("title", ""))
            or _normalize_text(scrape.get("main_title", ""))
        )
        brand = _normalize_text(first_checks.get("brand", ""))
        main_rank = _normalize_text(first_checks.get("main_rank", "")) or _normalize_text(scrape.get("bsr_recent_avg", ""))
        row_status = _normalize_text(row.get("row_status", ""))
        status_reason = _normalize_text(row.get("status_reason", ""))
        fail_code = _normalize_text(row.get("fail_code", "")) or status_reason
        original_point_score, original_test_result, original_test_status_reason, original_test_gate = _original_test_fields(
            first_checks
        )
        identity = _identity_match_classification(row_state=row_state_record, first_checks=first_checks, scrape=scrape)
        identity_fields = _identity_values(identity)

        expected_units = _num_or_none(backtest.get("expected_units_next_30d", ""))
        if expected_units is None:
            expected_units = _num_or_none(scrape.get("bbp_sales_replay_demand_basis_units", ""))
        if expected_units is None:
            expected_units = _num_or_none(scrape.get("bbp_monthly_units_chosen", ""))

        expected_profit = _num_or_none(backtest.get("expected_profit_next_30d_gbp", ""))
        est_profit = _num_or_none(scrape.get("estimated_monthly_profit", ""))
        per_unit_profit = _num_or_none(scrape.get("profit_per_unit_30d", ""))
        corrected_expected_profit = _num_or_none(profit_fields.get("corrected_expected_profit_next_30d_gbp", ""))
        corrected_per_unit_profit = _num_or_none(profit_fields.get("corrected_profit_per_unit_gbp", ""))
        if corrected_expected_profit is not None:
            expected_profit = corrected_expected_profit
        if corrected_per_unit_profit is not None:
            per_unit_profit = corrected_per_unit_profit
        profit = _profit_classification(
            profit_fields=profit_fields,
            expected_profit=expected_profit,
            per_unit_profit=per_unit_profit,
        )
        profit_fields = {**profit_fields, "profit_recommended_action": profit.recommended_action}
        supplier_title_fields = _supplier_title_values(
            supplier_title_index=supplier_title_index,
            active_supplier_id=active_supplier_id,
            supplier_sku=supplier_sku,
            first_checks=first_checks,
            scrape=scrape,
        )
        title_match = classify_title_match(
            {
                "supplier_sku": supplier_sku,
                "asin": asin,
                "supplier_title": supplier_title_fields["supplier_title"],
                "amazon_title": title,
                "supplier_brand": supplier_title_fields["supplier_brand"],
                "amazon_brand": brand,
                "unit_cost": supplier_title_fields["unit_cost"],
                "profit_per_unit_30d_gbp": _num_to_text(per_unit_profit),
                "expected_profit_next_30d_gbp": _num_to_text(expected_profit),
                "estimated_monthly_profit_gbp": _num_to_text(est_profit),
                "review_priority_score": _num_to_text(expected_profit or est_profit),
                "why_data_summary": "",
            }
        )
        title_match_fields = _title_match_values(title_match)
        supplier_title = _normalize_text(title_match.get("supplier_title", supplier_title_fields["supplier_title"]))
        amazon_title = _normalize_text(title_match.get("amazon_title", title))
        detail_text, detail_from_backfill = _page_evidence_text(
            scrape,
            page_evidence_backfill,
            "product_detail_text",
        )
        description_text, description_from_backfill = _page_evidence_text(
            scrape,
            page_evidence_backfill,
            "product_description",
        )
        bullets_text, bullets_from_backfill = _page_evidence_text(
            scrape,
            page_evidence_backfill,
            "product_feature_bullets",
        )
        if detail_from_backfill or description_from_backfill or bullets_from_backfill:
            page_evidence_backfill_used_count += 1
        amazon_page_text_fields = {
            "amazon_product_detail_text": detail_text,
            "amazon_product_description": description_text,
            "amazon_feature_bullets": bullets_text,
        }
        supplier_brand = _normalize_text(title_match.get("supplier_brand", supplier_title_fields["supplier_brand"]))
        amazon_brand = _normalize_text(title_match.get("amazon_brand", brand))
        _increment(title_match_action_counts, title_match_fields["title_match_action"])
        _increment(title_match_decision_bucket_counts, title_match_fields["title_match_decision_bucket"])
        decision_confidence = _normalize_text(backtest.get("decision_confidence", ""))
        stability = _normalize_text(backtest.get("stability_state", ""))
        lower_units, upper_units = _sales_band(expected_units, decision_confidence, stability)
        starter_qty = _starter_qty(lower_units)
        note = _commercial_note(backtest, scrape)
        why_data_summary, watch_data_summary = _pass_data_summaries(
            status_reason=status_reason,
            main_rank=main_rank,
            original_point_score=original_point_score,
            original_test_result=original_test_result,
            expected_units=expected_units,
            lower_units=lower_units,
            upper_units=upper_units,
            expected_profit=expected_profit,
            est_profit=est_profit,
            starter_qty=starter_qty,
            backtest=backtest,
            scrape=scrape,
        )
        demand = _demand_classification(
            row_state=row_state_record,
            first_checks=first_checks,
            scrape=scrape,
            backtest=backtest,
            expected_units=expected_units,
            seller_stock_columns_found=seller_stock_columns_found,
        )
        demand_fields = _demand_values(demand)
        history = _history_classification(
            scrape=scrape,
            backtest=backtest,
            commercial_note=note,
            profit_per_unit=per_unit_profit,
        )
        history_fields = _history_values(history)
        uk_review = _uk_review_classification(scrape=scrape)
        uk_review_fields = _uk_review_values(uk_review)
        seller_history = _seller_history_classification(scrape=scrape)
        seller_history_fields = _seller_history_values(seller_history)
        latest_review_event = _find_latest_review_event(
            review_pack_type="passes" if row_status == "pass" else "near_misses",
            candidate_id=candidate_id,
            asin=asin,
            by_pack_candidate=review_event_by_pack_candidate,
            by_pack_asin=review_event_by_pack_asin,
            by_candidate=review_event_by_candidate,
            by_asin=review_event_by_asin,
        )
        review_memory_fields = _review_memory_values(latest_review_event)

        if row_status == "pass":
            priority_score = (expected_profit or est_profit or 0.0)
            if review_memory_fields["review_memory_decision"] == "fail":
                review_memory_routed_remove_from_clean_pass_count += 1
                why_data_summary_nm, watch_data_summary_nm = _near_miss_data_summaries(
                    status_reason="review_memory_fail_decision",
                    fail_code="REVIEW_MEMORY_FAIL",
                    last_stage=_normalize_text(row.get("last_stage", "")),
                    main_rank=main_rank,
                    original_point_score=original_point_score,
                    original_test_result=original_test_result,
                    expected_units=expected_units,
                    lower_units=lower_units,
                    upper_units=upper_units,
                    expected_profit=expected_profit,
                    est_profit=est_profit,
                    starter_qty=starter_qty,
                    recovery_hint="operator_fail_memory_prevents_reappearing_in_clean_pass",
                    backtest=backtest,
                    scrape=scrape,
                )
                timeout_review_rows.append(
                    {
                        "observed_utc": observed_utc_value,
                        "active_supplier_id": active_supplier_id,
                        "active_run_id": active_run_id,
                        "review_batch_id": "",
                        "review_priority_score": _num_to_text(priority_score),
                        "near_miss_type": "review_memory_fail",
                        "reviewability_state": "known_fail",
                        "candidate_id": candidate_id,
                        "supplier_sku": supplier_sku,
                        "asin": asin,
                        "supplier_title": supplier_title,
                        "amazon_title": amazon_title,
                        **amazon_page_text_fields,
                        "title": title,
                        "supplier_brand": supplier_brand,
                        "amazon_brand": amazon_brand,
                        "brand": brand,
                        "original_point_score": original_point_score,
                        "original_test_result": original_test_result,
                        "original_test_status_reason": original_test_status_reason,
                        "original_test_gate": original_test_gate,
                        "screening_fail_code": "REVIEW_MEMORY_FAIL",
                        "screening_status_reason": "review_memory_fail_decision",
                        **title_match_fields,
                        **identity_fields,
                        "last_stage": _normalize_text(row.get("last_stage", "")),
                        "main_rank": main_rank,
                        "backtest_decision_state": _normalize_text(backtest.get("decision_state", "")),
                        "expected_units_next_30d": _num_to_text(expected_units),
                        "sales_lower_30d": _num_to_text(lower_units),
                        "sales_upper_30d": _num_to_text(upper_units),
                        "expected_profit_next_30d_gbp": _num_to_text(expected_profit),
                        "estimated_monthly_profit_gbp": _num_to_text(est_profit),
                        "profit_per_unit_30d_gbp": _num_to_text(per_unit_profit),
                        **profit_fields,
                        "conservative_starter_qty": _num_to_text(starter_qty),
                        **demand_fields,
                        **history_fields,
                        **uk_review_fields,
                        **seller_history_fields,
                        **review_memory_fields,
                        "why_data_summary": why_data_summary_nm,
                        "watch_data_summary": watch_data_summary_nm,
                        "recovery_hint": "operator_fail_memory_prevents_reappearing_in_clean_pass",
                        "commercial_note": note,
                    }
                )
                _increment(demand_action_counts, demand.recommended_action)
                _increment(identity_action_counts, identity.recommended_action)
                for code in identity.supporting_codes:
                    _increment(identity_supporting_code_counts, code)
                _increment(profit_action_counts, profit.recommended_action)
                for code in profit.supporting_codes:
                    _increment(profit_supporting_code_counts, code)
                for code in demand.supporting_codes:
                    _increment(demand_supporting_code_counts, code)
                _increment(history_action_counts, history.recommended_action)
                for code in history.supporting_codes:
                    _increment(history_supporting_code_counts, code)
                _increment(uk_review_action_counts, uk_review.recommended_action)
                for code in uk_review.supporting_codes:
                    _increment(uk_review_supporting_code_counts, code)
                _increment(seller_history_action_counts, seller_history.recommended_action)
                for code in seller_history.supporting_codes:
                    _increment(seller_history_supporting_code_counts, code)
                continue

            selected_routing = _select_pass_routing(
                main_rank=main_rank,
                expected_units=expected_units,
                title_match_fields=title_match_fields,
                identity=identity,
                profit=profit,
                demand=demand,
                history=history,
                uk_review=uk_review,
                seller_history=seller_history,
            )
            if selected_routing is not None:
                (
                    routing_source,
                    near_miss_type,
                    reviewability_state,
                    routing_fail_code,
                    recovery_hint,
                    routing_status_reason,
                ) = selected_routing
                if routing_source == "title_match":
                    if title_match_fields["title_match_action"] == "remove_from_clean_pass":
                        title_match_routed_remove_from_clean_pass_count += 1
                    elif title_match_fields["title_match_action"] == "manual_review":
                        title_match_routed_manual_review_count += 1
                elif routing_source == "demand":
                    if demand.recommended_action == "remove_from_clean_pass":
                        demand_routed_remove_from_clean_pass_count += 1
                    elif demand.recommended_action == "manual_review":
                        demand_routed_manual_review_count += 1
                elif routing_source == "history":
                    if history.recommended_action == "remove_from_clean_pass":
                        history_routed_remove_from_clean_pass_count += 1
                    elif history.recommended_action == "manual_review":
                        history_routed_manual_review_count += 1
                elif routing_source == "uk_review":
                    if uk_review.recommended_action == "remove_from_clean_pass":
                        uk_review_routed_remove_from_clean_pass_count += 1
                    elif uk_review.recommended_action == "manual_review":
                        uk_review_routed_manual_review_count += 1
                    elif uk_review.recommended_action == "targeted_rescan_needed":
                        uk_review_routed_targeted_rescan_needed_count += 1
                elif routing_source == "seller_history":
                    if seller_history.recommended_action == "remove_from_clean_pass":
                        seller_history_routed_remove_from_clean_pass_count += 1
                    elif seller_history.recommended_action == "manual_review":
                        seller_history_routed_manual_review_count += 1
                elif routing_source == "identity":
                    if identity.recommended_action == "remove_from_clean_pass":
                        identity_routed_remove_from_clean_pass_count += 1
                    elif identity.recommended_action == "manual_review":
                        identity_routed_manual_review_count += 1
                elif routing_source == "profit":
                    if profit.recommended_action == "remove_from_clean_pass":
                        profit_routed_remove_from_clean_pass_count += 1
                    elif profit.recommended_action == "manual_review":
                        profit_routed_manual_review_count += 1
                    elif profit.recommended_action == "targeted_rescan_needed":
                        profit_routed_targeted_rescan_needed_count += 1
                elif routing_source == "rank":
                    rank_routed_remove_from_clean_pass_count += 1
                elif routing_source == "low_sales":
                    low_sales_routed_remove_from_clean_pass_count += 1

                why_data_summary_nm, watch_data_summary_nm = _near_miss_data_summaries(
                    status_reason=routing_status_reason,
                    fail_code=routing_fail_code,
                    last_stage=_normalize_text(row.get("last_stage", "")),
                    main_rank=main_rank,
                    original_point_score=original_point_score,
                    original_test_result=original_test_result,
                    expected_units=expected_units,
                    lower_units=lower_units,
                    upper_units=upper_units,
                    expected_profit=expected_profit,
                    est_profit=est_profit,
                    starter_qty=starter_qty,
                    recovery_hint=recovery_hint,
                    backtest=backtest,
                    scrape=scrape,
                )
                timeout_review_rows.append(
                    {
                        "observed_utc": observed_utc_value,
                        "active_supplier_id": active_supplier_id,
                        "active_run_id": active_run_id,
                        "review_batch_id": "",
                        "review_priority_score": _num_to_text(priority_score),
                        "near_miss_type": near_miss_type,
                        "reviewability_state": reviewability_state,
                        "candidate_id": candidate_id,
                        "supplier_sku": supplier_sku,
                        "asin": asin,
                        "supplier_title": supplier_title,
                        "amazon_title": amazon_title,
                        **amazon_page_text_fields,
                        "title": title,
                        "supplier_brand": supplier_brand,
                        "amazon_brand": amazon_brand,
                        "brand": brand,
                        "original_point_score": original_point_score,
                        "original_test_result": original_test_result,
                        "original_test_status_reason": original_test_status_reason,
                        "original_test_gate": original_test_gate,
                        "screening_fail_code": routing_fail_code,
                        "screening_status_reason": routing_status_reason,
                        **title_match_fields,
                        **identity_fields,
                        "last_stage": _normalize_text(row.get("last_stage", "")),
                        "main_rank": main_rank,
                        "backtest_decision_state": _normalize_text(backtest.get("decision_state", "")),
                        "expected_units_next_30d": _num_to_text(expected_units),
                        "sales_lower_30d": _num_to_text(lower_units),
                        "sales_upper_30d": _num_to_text(upper_units),
                        "expected_profit_next_30d_gbp": _num_to_text(expected_profit),
                        "estimated_monthly_profit_gbp": _num_to_text(est_profit),
                        "profit_per_unit_30d_gbp": _num_to_text(per_unit_profit),
                        **profit_fields,
                        "conservative_starter_qty": _num_to_text(starter_qty),
                        **demand_fields,
                        **history_fields,
                        **uk_review_fields,
                        **seller_history_fields,
                        **review_memory_fields,
                        "why_data_summary": why_data_summary_nm,
                        "watch_data_summary": watch_data_summary_nm,
                        "recovery_hint": recovery_hint,
                        "commercial_note": note,
                    }
                )
                _increment(demand_action_counts, demand.recommended_action)
                _increment(identity_action_counts, identity.recommended_action)
                for code in identity.supporting_codes:
                    _increment(identity_supporting_code_counts, code)
                _increment(profit_action_counts, profit.recommended_action)
                for code in profit.supporting_codes:
                    _increment(profit_supporting_code_counts, code)
                for code in demand.supporting_codes:
                    _increment(demand_supporting_code_counts, code)
                _increment(history_action_counts, history.recommended_action)
                for code in history.supporting_codes:
                    _increment(history_supporting_code_counts, code)
                _increment(uk_review_action_counts, uk_review.recommended_action)
                for code in uk_review.supporting_codes:
                    _increment(uk_review_supporting_code_counts, code)
                _increment(seller_history_action_counts, seller_history.recommended_action)
                for code in seller_history.supporting_codes:
                    _increment(seller_history_supporting_code_counts, code)
                continue

            pass_rows.append(
                {
                    "observed_utc": observed_utc_value,
                    "active_supplier_id": active_supplier_id,
                    "active_run_id": active_run_id,
                    "review_batch_id": "",
                    "review_priority_score": _num_to_text(priority_score),
                    "candidate_id": candidate_id,
                    "supplier_sku": supplier_sku,
                    "asin": asin,
                    "supplier_title": supplier_title,
                    "amazon_title": amazon_title,
                    **amazon_page_text_fields,
                    "title": title,
                    "supplier_brand": supplier_brand,
                    "amazon_brand": amazon_brand,
                    "brand": brand,
                    "main_rank": main_rank,
                    "original_point_score": original_point_score,
                    "original_test_result": original_test_result,
                    "original_test_status_reason": original_test_status_reason,
                    "original_test_gate": original_test_gate,
                    "screening_status_reason": status_reason or "PASS",
                    **title_match_fields,
                    **identity_fields,
                    "backtest_decision_state": _normalize_text(backtest.get("decision_state", "")),
                    "expected_units_next_30d": _num_to_text(expected_units),
                    "sales_lower_30d": _num_to_text(lower_units),
                    "sales_upper_30d": _num_to_text(upper_units),
                    "expected_profit_next_30d_gbp": _num_to_text(expected_profit),
                    "estimated_monthly_profit_gbp": _num_to_text(est_profit),
                    "profit_per_unit_30d_gbp": _num_to_text(per_unit_profit),
                    **profit_fields,
                    "conservative_starter_qty": _num_to_text(starter_qty),
                    **demand_fields,
                    **history_fields,
                    **uk_review_fields,
                    **seller_history_fields,
                    **review_memory_fields,
                    "why_data_summary": why_data_summary,
                    "watch_data_summary": watch_data_summary,
                    "pass_reason_summary": _pass_reason_summary(backtest, scrape),
                    "commercial_note": note,
                }
            )
            _increment(demand_action_counts, demand.recommended_action)
            _increment(identity_action_counts, identity.recommended_action)
            for code in identity.supporting_codes:
                _increment(identity_supporting_code_counts, code)
            _increment(profit_action_counts, profit.recommended_action)
            for code in profit.supporting_codes:
                _increment(profit_supporting_code_counts, code)
            for code in demand.supporting_codes:
                _increment(demand_supporting_code_counts, code)
            _increment(history_action_counts, history.recommended_action)
            for code in history.supporting_codes:
                _increment(history_supporting_code_counts, code)
            _increment(uk_review_action_counts, uk_review.recommended_action)
            for code in uk_review.supporting_codes:
                _increment(uk_review_supporting_code_counts, code)
            _increment(seller_history_action_counts, seller_history.recommended_action)
            for code in seller_history.supporting_codes:
                _increment(seller_history_supporting_code_counts, code)
            continue

        if row_status != "timeout":
            continue

        opp = _normalize_text(scrape.get("opportunity_recommendation", ""))
        hist = _normalize_text(scrape.get("history_recommendation", ""))
        near_miss_type, reviewability_state, recovery_hint = _near_miss_classification(
            fail_code=fail_code,
            expected_profit=expected_profit,
            est_profit=est_profit,
            opportunity_recommendation=opp,
            history_recommendation=hist,
        )
        why_data_summary_nm, watch_data_summary_nm = _near_miss_data_summaries(
            status_reason=status_reason,
            fail_code=fail_code,
            last_stage=_normalize_text(row.get("last_stage", "")),
            main_rank=main_rank,
            original_point_score=original_point_score,
            original_test_result=original_test_result,
            expected_units=expected_units,
            lower_units=lower_units,
            upper_units=upper_units,
            expected_profit=expected_profit,
            est_profit=est_profit,
            starter_qty=starter_qty,
            recovery_hint=recovery_hint,
            backtest=backtest,
            scrape=scrape,
        )
        if reviewability_state == "hard_reject":
            hard_reject_count += 1
            fail_bucket = _normalize_text(fail_code) or "UNKNOWN"
            hard_reject_by_fail[fail_bucket] = hard_reject_by_fail.get(fail_bucket, 0) + 1
            continue

        priority_score = 100.0 if near_miss_type == "evidence_gap_near_miss" else float(expected_profit or est_profit or 0.0)
        timeout_review_rows.append(
            {
                "observed_utc": observed_utc_value,
                "active_supplier_id": active_supplier_id,
                "active_run_id": active_run_id,
                "review_batch_id": "",
                "review_priority_score": _num_to_text(priority_score),
                "near_miss_type": near_miss_type,
                "reviewability_state": reviewability_state,
                "candidate_id": candidate_id,
                "supplier_sku": supplier_sku,
                "asin": asin,
                "supplier_title": supplier_title,
                "amazon_title": amazon_title,
                **amazon_page_text_fields,
                "title": title,
                "supplier_brand": supplier_brand,
                "amazon_brand": amazon_brand,
                "brand": brand,
                "original_point_score": original_point_score,
                "original_test_result": original_test_result,
                "original_test_status_reason": original_test_status_reason,
                "original_test_gate": original_test_gate,
                "screening_fail_code": fail_code,
                "screening_status_reason": status_reason,
                **title_match_fields,
                **identity_fields,
                "last_stage": _normalize_text(row.get("last_stage", "")),
                "main_rank": main_rank,
                "backtest_decision_state": _normalize_text(backtest.get("decision_state", "")),
                "expected_units_next_30d": _num_to_text(expected_units),
                "sales_lower_30d": _num_to_text(lower_units),
                "sales_upper_30d": _num_to_text(upper_units),
                "expected_profit_next_30d_gbp": _num_to_text(expected_profit),
                "estimated_monthly_profit_gbp": _num_to_text(est_profit),
                "profit_per_unit_30d_gbp": _num_to_text(per_unit_profit),
                **profit_fields,
                "conservative_starter_qty": _num_to_text(starter_qty),
                **demand_fields,
                **history_fields,
                **uk_review_fields,
                **seller_history_fields,
                **review_memory_fields,
                "why_data_summary": why_data_summary_nm,
                "watch_data_summary": watch_data_summary_nm,
                "recovery_hint": recovery_hint,
                "commercial_note": note,
            }
        )
        _increment(demand_action_counts, demand.recommended_action)
        _increment(identity_action_counts, identity.recommended_action)
        for code in identity.supporting_codes:
            _increment(identity_supporting_code_counts, code)
        _increment(profit_action_counts, profit.recommended_action)
        for code in profit.supporting_codes:
            _increment(profit_supporting_code_counts, code)
        for code in demand.supporting_codes:
            _increment(demand_supporting_code_counts, code)
        _increment(history_action_counts, history.recommended_action)
        for code in history.supporting_codes:
            _increment(history_supporting_code_counts, code)
        _increment(uk_review_action_counts, uk_review.recommended_action)
        for code in uk_review.supporting_codes:
            _increment(uk_review_supporting_code_counts, code)
        _increment(seller_history_action_counts, seller_history.recommended_action)
        for code in seller_history.supporting_codes:
            _increment(seller_history_supporting_code_counts, code)

    pass_df = pd.DataFrame(pass_rows, columns=PASS_COLUMNS)
    if not pass_df.empty:
        pass_df["_sort_profit"] = pd.to_numeric(pass_df["expected_profit_next_30d_gbp"], errors="coerce").fillna(
            pd.to_numeric(pass_df["estimated_monthly_profit_gbp"], errors="coerce")
        ).fillna(0)
        pass_df = pass_df.sort_values(
            by=["_sort_profit", "review_priority_score", "asin", "supplier_sku"],
            ascending=[False, False, True, True],
            kind="stable",
        ).drop(columns=["_sort_profit"], errors="ignore")
        pass_df = pass_df.reset_index(drop=True)
        pass_df["review_batch_id"] = [_batch_id("pass_batch", idx, review_batch_size) for idx in range(len(pass_df.index))]

    near_miss_df = pd.DataFrame(timeout_review_rows, columns=NEAR_MISS_COLUMNS)
    if not near_miss_df.empty:
        near_miss_df["_sort_priority"] = pd.to_numeric(near_miss_df["review_priority_score"], errors="coerce").fillna(0)
        near_miss_df = near_miss_df.sort_values(
            by=["near_miss_type", "_sort_priority", "asin", "supplier_sku"],
            ascending=[True, False, True, True],
            kind="stable",
        ).drop(columns=["_sort_priority"], errors="ignore")
        near_miss_df = near_miss_df.reset_index(drop=True)
        near_miss_df["review_batch_id"] = [
            _batch_id("near_miss_batch", idx, review_batch_size) for idx in range(len(near_miss_df.index))
        ]

    summary_rows: list[dict[str, str]] = [
        {"observed_utc": observed_utc_value, "metric": "active_supplier_id", "value": active_supplier_id},
        {"observed_utc": observed_utc_value, "metric": "active_run_id", "value": active_run_id},
        {"observed_utc": observed_utc_value, "metric": "source_seen_at_utc", "value": source_seen_at_utc},
        {"observed_utc": observed_utc_value, "metric": "price_file_batch_id", "value": price_file_batch_id},
        {
            "observed_utc": observed_utc_value,
            "metric": "page_evidence_backfill_source_rows",
            "value": _num_to_text(page_evidence_backfill_source_rows),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "page_evidence_backfill_usable_rows",
            "value": _num_to_text(page_evidence_backfill_usable_rows),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "page_evidence_backfill_used_rows",
            "value": _num_to_text(page_evidence_backfill_used_count),
        },
        {"observed_utc": observed_utc_value, "metric": "pass_review_rows", "value": _num_to_text(len(pass_df.index))},
        {
            "observed_utc": observed_utc_value,
            "metric": "near_miss_review_rows",
            "value": _num_to_text(len(near_miss_df.index)),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "near_miss_evidence_gap_rows",
            "value": _num_to_text(int((near_miss_df.get("near_miss_type", pd.Series(dtype=str)) == "evidence_gap_near_miss").sum())),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "near_miss_commercial_rows",
            "value": _num_to_text(int((near_miss_df.get("near_miss_type", pd.Series(dtype=str)) == "commercial_near_miss").sum())),
        },
        {"observed_utc": observed_utc_value, "metric": "hard_reject_rows", "value": _num_to_text(hard_reject_count)},
        {
            "observed_utc": observed_utc_value,
            "metric": "title_match_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(title_match_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "title_match_routed_manual_review_rows",
            "value": _num_to_text(title_match_routed_manual_review_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "pass_review_batches",
            "value": _num_to_text(int(ceil(len(pass_df.index) / max(review_batch_size, 1)))) if len(pass_df.index) else "0",
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "near_miss_review_batches",
            "value": _num_to_text(int(ceil(len(near_miss_df.index) / max(review_batch_size, 1)))) if len(near_miss_df.index) else "0",
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "identity_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(identity_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "identity_routed_manual_review_rows",
            "value": _num_to_text(identity_routed_manual_review_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "profit_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(profit_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "profit_routed_manual_review_rows",
            "value": _num_to_text(profit_routed_manual_review_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "profit_routed_targeted_rescan_needed_rows",
            "value": _num_to_text(profit_routed_targeted_rescan_needed_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "demand_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(demand_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "demand_routed_manual_review_rows",
            "value": _num_to_text(demand_routed_manual_review_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "history_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(history_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "history_routed_manual_review_rows",
            "value": _num_to_text(history_routed_manual_review_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "uk_review_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(uk_review_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "uk_review_routed_manual_review_rows",
            "value": _num_to_text(uk_review_routed_manual_review_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "uk_review_routed_targeted_rescan_needed_rows",
            "value": _num_to_text(uk_review_routed_targeted_rescan_needed_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "seller_history_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(seller_history_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "seller_history_routed_manual_review_rows",
            "value": _num_to_text(seller_history_routed_manual_review_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "rank_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(rank_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "low_sales_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(low_sales_routed_remove_from_clean_pass_count),
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "review_memory_routed_remove_from_clean_pass_rows",
            "value": _num_to_text(review_memory_routed_remove_from_clean_pass_count),
        },
    ]
    for action, count in sorted(title_match_action_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"title_match_action::{action}",
                "value": _num_to_text(count),
            }
        )
    for bucket, count in sorted(title_match_decision_bucket_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"title_match_decision_bucket::{bucket}",
                "value": _num_to_text(count),
            }
        )
    for action, count in sorted(identity_action_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"identity_action::{action}",
                "value": _num_to_text(count),
            }
        )
    for code, count in sorted(identity_supporting_code_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"identity_supporting_code::{code}",
                "value": _num_to_text(count),
            }
        )
    for action, count in sorted(profit_action_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"profit_action::{action}",
                "value": _num_to_text(count),
            }
        )
    for code, count in sorted(profit_supporting_code_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"profit_supporting_code::{code}",
                "value": _num_to_text(count),
            }
        )
    for action, count in sorted(demand_action_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"demand_action::{action}",
                "value": _num_to_text(count),
            }
        )
    for code, count in sorted(demand_supporting_code_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"demand_supporting_code::{code}",
                "value": _num_to_text(count),
            }
        )
    for action, count in sorted(history_action_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"history_action::{action}",
                "value": _num_to_text(count),
            }
        )
    for code, count in sorted(history_supporting_code_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"history_supporting_code::{code}",
                "value": _num_to_text(count),
            }
        )
    for action, count in sorted(uk_review_action_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"uk_review_action::{action}",
                "value": _num_to_text(count),
            }
        )
    for code, count in sorted(uk_review_supporting_code_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"uk_review_supporting_code::{code}",
                "value": _num_to_text(count),
            }
        )
    for action, count in sorted(seller_history_action_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"seller_history_action::{action}",
                "value": _num_to_text(count),
            }
        )
    for code, count in sorted(seller_history_supporting_code_counts.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"seller_history_supporting_code::{code}",
                "value": _num_to_text(count),
            }
        )
    for fail_code, count in sorted(hard_reject_by_fail.items()):
        summary_rows.append(
            {
                "observed_utc": observed_utc_value,
                "metric": f"hard_reject::{fail_code}",
                "value": _num_to_text(count),
            }
        )
    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)

    if write_sql_snapshots:
        write_review_pack_snapshots_sql_compat(
            pass_df=pass_df,
            near_miss_df=near_miss_df,
            summary_df=summary_df,
            snapshot_id=ts_slug,
        )

    pass_df.to_csv(pass_path, index=False)
    pass_df.to_csv(pass_latest_path, index=False)
    near_miss_df.to_csv(near_miss_path, index=False)
    near_miss_df.to_csv(near_miss_latest_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    summary_df.to_csv(summary_latest_path, index=False)

    report = {
        "status": "built",
        "observed_utc": observed_utc_value,
        "active_supplier_id": active_supplier_id,
        "active_run_id": active_run_id,
        "pass_review_rows": int(len(pass_df.index)),
        "near_miss_review_rows": int(len(near_miss_df.index)),
        "page_evidence_backfill_source_rows": int(page_evidence_backfill_source_rows),
        "page_evidence_backfill_usable_rows": int(page_evidence_backfill_usable_rows),
        "page_evidence_backfill_used_rows": int(page_evidence_backfill_used_count),
        "near_miss_evidence_gap_rows": int(
            (near_miss_df.get("near_miss_type", pd.Series(dtype=str)) == "evidence_gap_near_miss").sum()
        ),
        "near_miss_commercial_rows": int(
            (near_miss_df.get("near_miss_type", pd.Series(dtype=str)) == "commercial_near_miss").sum()
        ),
        "hard_reject_rows": int(hard_reject_count),
        "title_match_routed_remove_from_clean_pass_rows": int(title_match_routed_remove_from_clean_pass_count),
        "title_match_routed_manual_review_rows": int(title_match_routed_manual_review_count),
        "identity_routed_remove_from_clean_pass_rows": int(identity_routed_remove_from_clean_pass_count),
        "identity_routed_manual_review_rows": int(identity_routed_manual_review_count),
        "profit_routed_remove_from_clean_pass_rows": int(profit_routed_remove_from_clean_pass_count),
        "profit_routed_manual_review_rows": int(profit_routed_manual_review_count),
        "profit_routed_targeted_rescan_needed_rows": int(profit_routed_targeted_rescan_needed_count),
        "demand_routed_remove_from_clean_pass_rows": int(demand_routed_remove_from_clean_pass_count),
        "demand_routed_manual_review_rows": int(demand_routed_manual_review_count),
        "history_routed_remove_from_clean_pass_rows": int(history_routed_remove_from_clean_pass_count),
        "history_routed_manual_review_rows": int(history_routed_manual_review_count),
        "uk_review_routed_remove_from_clean_pass_rows": int(uk_review_routed_remove_from_clean_pass_count),
        "uk_review_routed_manual_review_rows": int(uk_review_routed_manual_review_count),
        "uk_review_routed_targeted_rescan_needed_rows": int(uk_review_routed_targeted_rescan_needed_count),
        "seller_history_routed_remove_from_clean_pass_rows": int(seller_history_routed_remove_from_clean_pass_count),
        "seller_history_routed_manual_review_rows": int(seller_history_routed_manual_review_count),
        "rank_routed_remove_from_clean_pass_rows": int(rank_routed_remove_from_clean_pass_count),
        "low_sales_routed_remove_from_clean_pass_rows": int(low_sales_routed_remove_from_clean_pass_count),
        "review_memory_routed_remove_from_clean_pass_rows": int(review_memory_routed_remove_from_clean_pass_count),
        "title_match_action_counts": {key: int(value) for key, value in sorted(title_match_action_counts.items())},
        "title_match_decision_bucket_counts": {
            key: int(value) for key, value in sorted(title_match_decision_bucket_counts.items())
        },
        "identity_action_counts": {key: int(value) for key, value in sorted(identity_action_counts.items())},
        "identity_supporting_code_counts": {
            key: int(value) for key, value in sorted(identity_supporting_code_counts.items())
        },
        "profit_action_counts": {key: int(value) for key, value in sorted(profit_action_counts.items())},
        "profit_supporting_code_counts": {
            key: int(value) for key, value in sorted(profit_supporting_code_counts.items())
        },
        "demand_action_counts": {key: int(value) for key, value in sorted(demand_action_counts.items())},
        "demand_supporting_code_counts": {
            key: int(value) for key, value in sorted(demand_supporting_code_counts.items())
        },
        "history_action_counts": {key: int(value) for key, value in sorted(history_action_counts.items())},
        "history_supporting_code_counts": {
            key: int(value) for key, value in sorted(history_supporting_code_counts.items())
        },
        "uk_review_action_counts": {key: int(value) for key, value in sorted(uk_review_action_counts.items())},
        "uk_review_supporting_code_counts": {
            key: int(value) for key, value in sorted(uk_review_supporting_code_counts.items())
        },
        "seller_history_action_counts": {
            key: int(value) for key, value in sorted(seller_history_action_counts.items())
        },
        "seller_history_supporting_code_counts": {
            key: int(value) for key, value in sorted(seller_history_supporting_code_counts.items())
        },
        "pass_latest_path": str(pass_latest_path),
        "near_miss_latest_path": str(near_miss_latest_path),
        "summary_latest_path": str(summary_latest_path),
    }

    return LivePriceFileReviewPackResult(
        pass_df=pass_df,
        near_miss_df=near_miss_df,
        summary_df=summary_df,
        pass_path=pass_path,
        pass_latest_path=pass_latest_path,
        near_miss_path=near_miss_path,
        near_miss_latest_path=near_miss_latest_path,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
        report=report,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build pass-review and near-miss review packs for active supplier wave.")
    parser.add_argument("--baseline-path", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--row-state-path", type=Path, default=DEFAULT_ROW_STATE_PATH)
    parser.add_argument("--first-checks-path", type=Path, default=DEFAULT_FIRST_CHECKS_PATH)
    parser.add_argument("--scrape-evidence-path", type=Path, default=DEFAULT_SCRAPE_EVIDENCE_PATH)
    parser.add_argument("--page-evidence-backfill-results-path", type=Path, default=DEFAULT_PAGE_EVIDENCE_BACKFILL_RESULTS_PATH)
    parser.add_argument("--backtest-summary-path", type=Path, default=DEFAULT_BACKTEST_SUMMARY_PATH)
    parser.add_argument("--profit-audit-path", type=Path, default=DEFAULT_PROFIT_AUDIT_PATH)
    parser.add_argument("--review-events-path", type=Path, default=DEFAULT_REVIEW_EVENTS_PATH)
    parser.add_argument("--supplier-inbox-dir", type=Path, default=DEFAULT_SUPPLIER_INBOX_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--observed-utc", default="")
    parser.add_argument("--review-batch-size", type=int, default=DEFAULT_REVIEW_BATCH_SIZE)
    parser.add_argument("--active-supplier-id", default="")
    parser.add_argument("--active-run-id", default="")
    parser.add_argument("--source-seen-at-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_live_price_file_near_miss_pack(
        baseline_path=args.baseline_path,
        row_state_path=args.row_state_path,
        first_checks_path=args.first_checks_path,
        scrape_evidence_path=args.scrape_evidence_path,
        page_evidence_backfill_results_path=args.page_evidence_backfill_results_path,
        backtest_summary_path=args.backtest_summary_path,
        profit_audit_path=args.profit_audit_path,
        review_events_path=args.review_events_path,
        supplier_inbox_dir=args.supplier_inbox_dir,
        output_dir=args.output_dir,
        observed_utc=_normalize_text(args.observed_utc) or None,
        review_batch_size=max(int(args.review_batch_size), 1),
        active_supplier_id=args.active_supplier_id,
        active_run_id=args.active_run_id,
        source_seen_at_utc_override=args.source_seen_at_utc,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
