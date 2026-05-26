from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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
from scripts.core.storage import (
    SQL_TABLE_FEEDER_REVIEW_EVENTS,
    read_dataframe_with_sql_fallback,
    read_review_pack_dataframe,
)
from scripts.flows.F._scanner_state import (
    dashboard_delivery_classification,
    dashboard_separate_delivery_required,
)


DEFAULT_PASS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
DEFAULT_NEAR_MISS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
DEFAULT_EVENTS_PATH = ROOT / get_f_output_contract("feeder_review_events").rel_path
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / get_f_output_contract("feeder_legacy_scrape_evidence_live").rel_path
DEFAULT_DEMAND_AUDIT_PATH = ROOT / "out" / "analysis_reports" / "f_demand_range_bbp_conflict_audit_latest.csv"
DEFAULT_HISTORY_AUDIT_PATH = ROOT / "out" / "analysis_reports" / "f_history_risk_pass_conflict_audit_latest.csv"
DEFAULT_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_new_product_review_fail_triage_latest.csv"
DEFAULT_REVIEW_HANDOFFS_ROOT = (
    ROOT / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"
)
REVIEW_HANDOFF_PASS_FILENAME = "f_live_price_file_pass_review_latest.csv"
REVIEW_HANDOFF_NEAR_MISS_FILENAME = "f_live_price_file_near_miss_review_latest.csv"

OUTPUT_COLUMNS = [
    "asin",
    "candidate_id",
    "supplier_sku",
    "review_pack_type",
    "review_batch_id",
    "fail_type",
    "fail_reason_code",
    "evidence_source",
    "demand_conflict_code",
    "demand_recommended_action",
    "demand_evidence_source",
    "demand_supporting_codes",
    "history_risk_code",
    "history_recommended_action",
    "history_evidence_source",
    "history_supporting_codes",
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
    "observed_utc",
]

VALID_FAIL_TYPES = {
    "type_1_data_or_calc",
    "type_2_known_policy_or_memory",
    "type_3_missing_evidence_rescan_needed",
}

TYPE_3_NEAR_MISS_REASON_CODES = {
    "SCRAPEFAIL",
    "RESCAN",
    "NODATE",
    "NOASIN",
    "MISSING_EVIDENCE",
    "EVIDENCE_MISSING",
}

MISSING_TEXT_MARKERS = {"", "na", "n/a", "none", "null", "nan"}
DEMAND_CONFLICT_UNITS_THRESHOLD = 50.0
LOW_HISTORICAL_UK_REVIEWS_THRESHOLD = 5
HIGH_PARENT_REVIEW_THRESHOLD = 100
HIGH_VARIANT_REVIEW_THRESHOLD = 50
SELLER_STOCK_COUNT_COLUMNS = (
    "seller_stock_count",
    "seller_stock",
    "stock_count",
    "amazon_seller_stock_count",
    "seller_qty",
)

DEMAND_PRIMARY_PRIORITY = {
    "amazon_blank_bbp_high": 10,
    "amazon_50_bbp_inflated": 20,
    "amazon_50_bbp_warn": 30,
    "seller_stock_missing_for_demand_check": 40,
    "amazon_50_bbp_reasonable": 80,
    "amazon_blank_bbp_low": 90,
    "weak_uk_review_confirms_demand_risk": 100,
}

DEMAND_TRIAGE_RULES = {
    "amazon_blank_bbp_high": (
        "type_1_data_or_calc",
        "demand_amazon_blank_bbp_high",
        "remove_from_clean_pass",
    ),
    "amazon_50_bbp_inflated": (
        "type_1_data_or_calc",
        "demand_amazon_50_bbp_inflated",
        "remove_from_clean_pass",
    ),
    "amazon_50_bbp_warn": (
        "type_1_data_or_calc",
        "demand_amazon_50_bbp_warn_manual_review",
        "manual_review",
    ),
    "seller_stock_missing_for_demand_check": (
        "type_3_missing_evidence_rescan_needed",
        "demand_seller_stock_missing_for_demand_check",
        "targeted_rescan_needed",
    ),
}

DEMAND_SUPPORTING_ONLY_CODES = {"weak_uk_review_confirms_demand_risk"}
HISTORY_PRIMARY_PRIORITY = {
    "history_fail_phase_avoid": 10,
    "exit_only_clean_pass": 20,
    "backtest_avoid_commercial_avoid_or_exit": 30,
    "failure_events_100_plus": 40,
    "selloff_days_exceed_normal_days": 50,
    "history_risk_clear": 90,
}
HISTORY_TRIAGE_RULES = {
    "history_fail_phase_avoid": (
        "type_1_data_or_calc",
        "history_risk_history_fail_phase_avoid",
        "remove_from_clean_pass",
    ),
    "backtest_avoid_commercial_avoid_or_exit": (
        "type_1_data_or_calc",
        "history_risk_backtest_avoid_commercial_avoid_or_exit",
        "remove_from_clean_pass",
    ),
    "exit_only_clean_pass": (
        "type_1_data_or_calc",
        "history_risk_exit_only_clean_pass",
        "remove_from_clean_pass",
    ),
    "failure_events_100_plus": (
        "type_1_data_or_calc",
        "history_risk_failure_events_100_plus_manual_review",
        "manual_review",
    ),
    "selloff_days_exceed_normal_days": (
        "type_1_data_or_calc",
        "history_risk_selloff_days_exceed_normal_days_manual_review",
        "manual_review",
    ),
}
HISTORY_SUPPORTING_ONLY_CODES = {"history_risk_clear"}
UK_REVIEW_PRIMARY_PRIORITY = {
    "uk_reviews_lt3": 10,
    "uk_reviews_3_to_5": 20,
    "uk_reviews_missing": 30,
    "uk_reviews_6_to_9": 90,
    "uk_reviews_10_plus": 100,
}
UK_REVIEW_TRIAGE_RULES = {
    "uk_reviews_lt3": (
        "type_1_data_or_calc",
        "uk_review_uk_reviews_lt3",
        "remove_from_clean_pass",
    ),
    "uk_reviews_3_to_5": (
        "type_1_data_or_calc",
        "uk_review_uk_reviews_3_to_5_manual_review",
        "manual_review",
    ),
    "uk_reviews_missing": (
        "type_3_missing_evidence_rescan_needed",
        "uk_review_missing_targeted_rescan_needed",
        "targeted_rescan_needed",
    ),
}
UK_REVIEW_SUPPORTING_ONLY_CODES = {"uk_reviews_6_to_9", "uk_reviews_10_plus"}
SELLER_HISTORY_TRIAGE_RULES = {
    "dashboard_no_low_seller_count": (
        "type_1_data_or_calc",
        "seller_history_dashboard_no_low_seller_count",
        "remove_from_clean_pass",
    ),
    "amazon_only_single_seller": (
        "type_1_data_or_calc",
        "seller_history_amazon_only_single_seller",
        "remove_from_clean_pass",
    ),
    "brand_owner_single_seller": (
        "type_1_data_or_calc",
        "seller_history_brand_owner_single_seller",
        "remove_from_clean_pass",
    ),
    "brand_owner_top_seller": (
        "type_1_data_or_calc",
        "seller_history_brand_owner_top_seller",
        "remove_from_clean_pass",
    ),
    "single_seller_owner_unclear": (
        "type_1_data_or_calc",
        "seller_history_single_seller_owner_unclear_manual_review",
        "manual_review",
    ),
}
SELLER_HISTORY_SUPPORTING_ONLY_CODES = {
    "dashboard_no_multi_seller_count",
    "seller_history_clear",
    "seller_history_missing",
    "single_fba_seller_amazon_absent",
}


DemandAuditIndex = dict[str, dict[object, list[dict[str, str]]]]
HistoryAuditIndex = dict[str, dict[object, list[dict[str, str]]]]


@dataclass(frozen=True)
class NewProductReviewFailTriageResult:
    triage_df: pd.DataFrame
    output_path: Path
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).upper()


def _value_is_missing(value: object) -> bool:
    return _normalize_text(value).lower() in MISSING_TEXT_MARKERS


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_review_pack(path: Path, pack_type: str) -> pd.DataFrame:
    return read_review_pack_dataframe(path, pack_type=pack_type, dtype=str).fillna("")


def _read_review_events(path: Path) -> pd.DataFrame:
    try:
        return read_dataframe_with_sql_fallback(path, SQL_TABLE_FEEDER_REVIEW_EVENTS, dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _safe_handoff_segment(value: object, *, fallback: str) -> str:
    text = _normalize_text(value)
    if text == "":
        text = fallback
    return text.replace("/", "_").replace("\\", "_")


def _review_event_handoff_dirs(
    review_events_df: pd.DataFrame,
    review_handoffs_root: Path | None,
) -> tuple[list[Path], list[Path]]:
    if review_handoffs_root is None or review_events_df.empty:
        return [], []

    root = Path(review_handoffs_root)
    if not root.exists():
        return [], []

    dirs: list[Path] = []
    missing_dirs: list[Path] = []
    seen: set[str] = set()

    for _, row in review_events_df.iterrows():
        supplier_id = _normalize_text(row.get("active_supplier_id", ""))
        run_id = _normalize_text(row.get("active_run_id", ""))
        if supplier_id == "" or run_id == "":
            continue

        handoff_dir = (
            root
            / _safe_handoff_segment(supplier_id, fallback="unknown_supplier")
            / _safe_handoff_segment(run_id, fallback="unknown_run")
        )
        key = str(handoff_dir)
        if key in seen:
            continue
        seen.add(key)

        if handoff_dir.exists():
            dirs.append(handoff_dir)
        else:
            missing_dirs.append(handoff_dir)

    return dirs, missing_dirs


def _read_review_handoff_pack_frames(
    review_events_df: pd.DataFrame,
    review_handoffs_root: Path | None,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], list[str], list[str], int, int]:
    handoff_dirs, missing_dirs = _review_event_handoff_dirs(review_events_df, review_handoffs_root)
    pass_frames: list[pd.DataFrame] = []
    near_miss_frames: list[pd.DataFrame] = []
    pass_rows = 0
    near_miss_rows = 0

    for handoff_dir in handoff_dirs:
        pass_df = _read_csv(handoff_dir / REVIEW_HANDOFF_PASS_FILENAME)
        near_miss_df = _read_csv(handoff_dir / REVIEW_HANDOFF_NEAR_MISS_FILENAME)
        if not pass_df.empty:
            pass_rows += int(len(pass_df.index))
            pass_frames.append(pass_df)
        if not near_miss_df.empty:
            near_miss_rows += int(len(near_miss_df.index))
            near_miss_frames.append(near_miss_df)

    return (
        pass_frames,
        near_miss_frames,
        [str(path) for path in handoff_dirs],
        [str(path) for path in missing_dirs],
        pass_rows,
        near_miss_rows,
    )


def _dedupe_review_pack_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    key_columns = [
        "active_supplier_id",
        "active_run_id",
        "review_batch_id",
        "candidate_id",
        "supplier_sku",
        "asin",
    ]
    identity_columns = ["candidate_id", "supplier_sku", "asin"]
    seen: set[tuple[str, ...]] = set()
    keep: list[bool] = []

    for _, row in frame.iterrows():
        identity = tuple(_normalize_key(row.get(column, "")) for column in identity_columns)
        if all(part == "" for part in identity):
            keep.append(True)
            continue

        key = tuple(_normalize_key(row.get(column, "")) for column in key_columns)
        if key in seen:
            keep.append(False)
            continue
        seen.add(key)
        keep.append(True)

    return frame.loc[keep].reset_index(drop=True)


def _combine_review_pack_frames(primary: pd.DataFrame, extra_frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [frame for frame in [primary, *extra_frames] if not frame.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    return _dedupe_review_pack_rows(combined)


def _parse_float(value: object) -> float | None:
    text = _normalize_text(value).replace(",", "")
    if _value_is_missing(text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: object) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _normalize_observed_utc(value: object, *, fallback_utc: str) -> str:
    raw = _normalize_text(value)
    if raw == "":
        return fallback_utc
    parsed = pd.to_datetime(raw, errors="coerce", utc=True, format="mixed")
    if pd.isna(parsed):
        return fallback_utc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_summary_tokens(raw_text: object) -> dict[str, str]:
    text = _normalize_text(raw_text)
    if text == "":
        return {}
    tokens: dict[str, str] = {}
    for chunk in text.split("|"):
        part = _normalize_text(chunk)
        if part == "" or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key_norm = _normalize_key(key)
        if key_norm == "":
            continue
        tokens[key_norm] = _normalize_text(value)
    return tokens


def _latest_records(df: pd.DataFrame, *, key_columns: list[str], utc_columns: list[str]) -> dict[tuple[str, ...], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    for col in key_columns + utc_columns:
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].map(_normalize_text)

    utc_sort = None
    for col in utc_columns:
        parsed = pd.to_datetime(work[col], errors="coerce", utc=True, format="mixed")
        utc_sort = parsed if utc_sort is None else utc_sort.fillna(parsed)
    work["_utc_sort"] = utc_sort
    work = work.sort_values(by=["_utc_sort"], ascending=[False], kind="stable")

    out: dict[tuple[str, ...], dict[str, str]] = {}
    for _, row in work.iterrows():
        key = tuple(_normalize_key(row.get(col, "")) for col in key_columns)
        if any(part == "" for part in key):
            continue
        if key in out:
            continue
        out[key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _dedupe_join(values: list[object]) -> str:
    out: list[str] = []
    for value in values:
        text = _normalize_text(value)
        if text != "" and text not in out:
            out.append(text)
    return "|".join(out)


def _demand_sort_key(row: dict[str, str]) -> tuple[int, str]:
    code = _normalize_text(row.get("demand_conflict_code", ""))
    return (DEMAND_PRIMARY_PRIORITY.get(code, 999), code)


def _build_demand_audit_index(demand_audit_df: pd.DataFrame) -> DemandAuditIndex:
    index: DemandAuditIndex = {
        "by_pack_candidate": defaultdict(list),
        "by_pack_asin": defaultdict(list),
        "by_candidate": defaultdict(list),
        "by_asin": defaultdict(list),
    }
    if demand_audit_df.empty:
        return index

    work = demand_audit_df.copy()
    for column in (
        "review_pack_type",
        "candidate_id",
        "asin",
        "demand_conflict_code",
        "recommended_action",
        "evidence_source",
    ):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)

    for _, row in work.iterrows():
        record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        code = _normalize_text(record.get("demand_conflict_code", ""))
        if code == "":
            continue
        pack = _normalize_key(record.get("review_pack_type", ""))
        candidate = _normalize_key(record.get("candidate_id", ""))
        asin = _normalize_key(record.get("asin", ""))

        if pack and candidate:
            index["by_pack_candidate"][(pack, candidate)].append(record)
        if pack and asin:
            index["by_pack_asin"][(pack, asin)].append(record)
        if candidate:
            index["by_candidate"][candidate].append(record)
        if asin:
            index["by_asin"][asin].append(record)

    return index


def _find_demand_audit_records(
    *,
    review_pack_type: str,
    candidate_id: str,
    asin: str,
    demand_audit_index: DemandAuditIndex,
) -> list[dict[str, str]]:
    pack = _normalize_key(review_pack_type)
    candidate = _normalize_key(candidate_id)
    asin_key = _normalize_key(asin)

    lookup_order: list[tuple[str, object]] = []
    if pack and candidate:
        lookup_order.append(("by_pack_candidate", (pack, candidate)))
    if pack and asin_key:
        lookup_order.append(("by_pack_asin", (pack, asin_key)))
    if candidate:
        lookup_order.append(("by_candidate", candidate))
    if asin_key:
        lookup_order.append(("by_asin", asin_key))

    seen_codes: set[str] = set()
    records: list[dict[str, str]] = []
    for bucket, key in lookup_order:
        for record in demand_audit_index[bucket].get(key, []):
            code = _normalize_text(record.get("demand_conflict_code", ""))
            if code == "" or code in seen_codes:
                continue
            seen_codes.add(code)
            records.append(record)
        if records:
            break
    return sorted(records, key=_demand_sort_key)


def _demand_context(records: list[dict[str, str]]) -> dict[str, str]:
    if not records:
        return {
            "demand_conflict_code": "",
            "demand_recommended_action": "",
            "demand_evidence_source": "",
            "demand_supporting_codes": "",
        }

    primary = sorted(records, key=_demand_sort_key)[0]
    primary_code = _normalize_text(primary.get("demand_conflict_code", ""))
    primary_action = _normalize_text(primary.get("recommended_action", ""))
    supporting_codes = _dedupe_join(
        [_normalize_text(record.get("demand_conflict_code", "")) for record in sorted(records, key=_demand_sort_key)]
    )
    evidence_sources = _dedupe_join(
        [_normalize_text(record.get("evidence_source", "")) for record in sorted(records, key=_demand_sort_key)]
    )
    return {
        "demand_conflict_code": primary_code,
        "demand_recommended_action": primary_action,
        "demand_evidence_source": evidence_sources,
        "demand_supporting_codes": supporting_codes,
    }


def _classify_demand_context(context: dict[str, str]) -> tuple[str, str, str] | None:
    code = _normalize_text(context.get("demand_conflict_code", ""))
    if code in DEMAND_SUPPORTING_ONLY_CODES:
        return None
    rule = DEMAND_TRIAGE_RULES.get(code)
    if rule is None:
        return None
    fail_type, fail_reason_code, _demand_action = rule
    return fail_type, fail_reason_code, "f_demand_range_bbp_conflict_audit_latest.csv"


def _history_sort_key(row: dict[str, str]) -> tuple[int, str]:
    code = _normalize_text(row.get("history_risk_code", ""))
    return (HISTORY_PRIMARY_PRIORITY.get(code, 999), code)


def _build_history_audit_index(history_audit_df: pd.DataFrame) -> HistoryAuditIndex:
    index: HistoryAuditIndex = {
        "by_pack_candidate": defaultdict(list),
        "by_pack_asin": defaultdict(list),
        "by_candidate": defaultdict(list),
        "by_asin": defaultdict(list),
    }
    if history_audit_df.empty:
        return index

    work = history_audit_df.copy()
    for column in (
        "review_pack_type",
        "candidate_id",
        "asin",
        "history_risk_code",
        "history_recommended_action",
        "evidence_source",
    ):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)

    for _, row in work.iterrows():
        record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        code = _normalize_text(record.get("history_risk_code", ""))
        if code == "":
            continue
        pack = _normalize_key(record.get("review_pack_type", ""))
        candidate = _normalize_key(record.get("candidate_id", ""))
        asin = _normalize_key(record.get("asin", ""))

        if pack and candidate:
            index["by_pack_candidate"][(pack, candidate)].append(record)
        if pack and asin:
            index["by_pack_asin"][(pack, asin)].append(record)
        if candidate:
            index["by_candidate"][candidate].append(record)
        if asin:
            index["by_asin"][asin].append(record)

    return index


def _find_history_audit_records(
    *,
    review_pack_type: str,
    candidate_id: str,
    asin: str,
    history_audit_index: HistoryAuditIndex,
) -> list[dict[str, str]]:
    pack = _normalize_key(review_pack_type)
    candidate = _normalize_key(candidate_id)
    asin_key = _normalize_key(asin)

    lookup_order: list[tuple[str, object]] = []
    if pack and candidate:
        lookup_order.append(("by_pack_candidate", (pack, candidate)))
    if pack and asin_key:
        lookup_order.append(("by_pack_asin", (pack, asin_key)))
    if candidate:
        lookup_order.append(("by_candidate", candidate))
    if asin_key:
        lookup_order.append(("by_asin", asin_key))

    seen_codes: set[str] = set()
    records: list[dict[str, str]] = []
    for bucket, key in lookup_order:
        for record in history_audit_index[bucket].get(key, []):
            code = _normalize_text(record.get("history_risk_code", ""))
            if code == "" or code in seen_codes:
                continue
            seen_codes.add(code)
            records.append(record)
        if records:
            break
    return sorted(records, key=_history_sort_key)


def _history_context(
    records: list[dict[str, str]],
    *,
    source_row: dict[str, str] | None = None,
) -> dict[str, str]:
    if not records:
        if source_row is None:
            return {
                "history_risk_code": "",
                "history_recommended_action": "",
                "history_evidence_source": "",
                "history_supporting_codes": "",
            }
        return {
            "history_risk_code": _normalize_text(source_row.get("history_risk_code", "")),
            "history_recommended_action": _normalize_text(source_row.get("history_recommended_action", "")),
            "history_evidence_source": _normalize_text(source_row.get("history_evidence_source", "")),
            "history_supporting_codes": _normalize_text(source_row.get("history_supporting_codes", "")),
        }

    primary = sorted(records, key=_history_sort_key)[0]
    primary_code = _normalize_text(primary.get("history_risk_code", ""))
    primary_action = _normalize_text(primary.get("history_recommended_action", ""))
    supporting_codes = _dedupe_join(
        [_normalize_text(record.get("history_risk_code", "")) for record in sorted(records, key=_history_sort_key)]
    )
    evidence_sources = _dedupe_join(
        [_normalize_text(record.get("evidence_source", "")) for record in sorted(records, key=_history_sort_key)]
    )
    return {
        "history_risk_code": primary_code,
        "history_recommended_action": primary_action,
        "history_evidence_source": evidence_sources,
        "history_supporting_codes": supporting_codes,
    }


def _classify_history_context(context: dict[str, str]) -> tuple[str, str, str] | None:
    code = _normalize_text(context.get("history_risk_code", ""))
    if code in HISTORY_SUPPORTING_ONLY_CODES:
        return None
    rule = HISTORY_TRIAGE_RULES.get(code)
    if rule is None:
        return None
    fail_type, fail_reason_code, _history_action = rule
    return fail_type, fail_reason_code, "f_history_risk_pass_conflict_audit_latest.csv"


def _uk_review_sort_key(code: str) -> tuple[int, str]:
    normalized = _normalize_text(code)
    return (UK_REVIEW_PRIMARY_PRIORITY.get(normalized, 999), normalized)


def _classify_uk_review_code(uk_reviews: int | None) -> str:
    if uk_reviews is None:
        return "uk_reviews_missing"
    if uk_reviews < 3:
        return "uk_reviews_lt3"
    if uk_reviews < 6:
        return "uk_reviews_3_to_5"
    if uk_reviews < 10:
        return "uk_reviews_6_to_9"
    return "uk_reviews_10_plus"


def _uk_review_context(*, source_row: dict[str, str], scrape_row: dict[str, str]) -> dict[str, str]:
    source_code = _normalize_text(source_row.get("uk_review_code", ""))
    source_action = _normalize_text(source_row.get("uk_review_recommended_action", ""))
    source_supporting = _normalize_text(source_row.get("uk_review_supporting_codes", ""))
    source_evidence = _normalize_text(source_row.get("uk_review_evidence_source", ""))
    if source_code != "":
        fallback_action = (
            "supporting_evidence_only"
            if source_code == "uk_reviews_6_to_9"
            else "allow_if_other_checks_pass" if source_code == "uk_reviews_10_plus" else ""
        )
        return {
            "uk_review_code": source_code,
            "uk_review_recommended_action": source_action or fallback_action,
            "uk_review_supporting_codes": source_supporting or source_code,
            "uk_review_evidence_source": source_evidence or "f_live_price_file_pass_or_near_miss_review_latest.csv",
        }

    uk_reviews = _parse_int(scrape_row.get("historical_uk_reviews", ""))
    code = _classify_uk_review_code(uk_reviews)
    action = {
        "uk_reviews_lt3": "remove_from_clean_pass",
        "uk_reviews_3_to_5": "manual_review",
        "uk_reviews_6_to_9": "supporting_evidence_only",
        "uk_reviews_10_plus": "allow_if_other_checks_pass",
        "uk_reviews_missing": "targeted_rescan_needed",
    }[code]
    return {
        "uk_review_code": code,
        "uk_review_recommended_action": action,
        "uk_review_supporting_codes": code,
        "uk_review_evidence_source": (
            "feeder_legacy_scrape_evidence_live.csv:historical_uk_reviews"
            if _normalize_text(scrape_row.get("historical_uk_reviews", "")) != ""
            else "feeder_legacy_scrape_evidence_live.csv:historical_uk_reviews_missing"
        ),
    }


def _classify_uk_review_context(context: dict[str, str]) -> tuple[str, str, str] | None:
    code = _normalize_text(context.get("uk_review_code", ""))
    if code in UK_REVIEW_SUPPORTING_ONLY_CODES:
        return None
    rule = UK_REVIEW_TRIAGE_RULES.get(code)
    if rule is None:
        return None
    fail_type, fail_reason_code, _action = rule
    return fail_type, fail_reason_code, "f_live_price_file_pass_or_near_miss_review_latest.csv"


def _seller_history_context(*, source_row: dict[str, str], scrape_row: dict[str, str]) -> dict[str, str]:
    source_code = _normalize_text(source_row.get("seller_history_code", ""))
    source_action = _normalize_text(source_row.get("seller_history_recommended_action", ""))
    source_supporting = _normalize_text(source_row.get("seller_history_supporting_codes", ""))
    source_evidence = _normalize_text(source_row.get("seller_history_evidence_source", ""))
    source_new_30 = _normalize_text(source_row.get("seller_history_new_30", ""))
    source_new_90 = _normalize_text(source_row.get("seller_history_new_90", ""))
    source_new_180 = _normalize_text(source_row.get("seller_history_new_180", ""))
    source_dashboard = _normalize_text(source_row.get("seller_history_dashboard_yes_or_no", ""))
    source_dashboard_delivery = _normalize_text(source_row.get("seller_history_dashboard_delivery_classification", ""))
    source_dashboard_delivery_required = _normalize_text(
        source_row.get("seller_history_dashboard_separate_delivery_required", "")
    )
    if source_dashboard_delivery == "":
        source_dashboard_delivery = dashboard_delivery_classification(source_dashboard)
    if source_dashboard_delivery_required == "":
        source_dashboard_delivery_required = "1" if dashboard_separate_delivery_required(source_dashboard) else "0"
    if source_code != "":
        if source_code in {
            "amazon_only_single_seller",
            "brand_owner_single_seller",
            "brand_owner_top_seller",
            "dashboard_no_low_seller_count",
        }:
            fallback_action = "remove_from_clean_pass"
        elif source_code in {"single_seller_owner_unclear"}:
            fallback_action = "manual_review"
        elif source_code in {"seller_history_clear", "single_fba_seller_amazon_absent", "dashboard_no_multi_seller_count"}:
            fallback_action = "allow_if_other_checks_pass"
        else:
            fallback_action = "missing_evidence_only"
        return {
            "seller_history_code": source_code,
            "seller_history_recommended_action": source_action or fallback_action,
            "seller_history_supporting_codes": source_supporting or source_code,
            "seller_history_evidence_source": source_evidence
            or "f_live_price_file_pass_or_near_miss_review_latest.csv",
            "seller_history_new_30": source_new_30,
            "seller_history_new_90": source_new_90,
            "seller_history_new_180": source_new_180,
            "seller_history_dashboard_yes_or_no": source_dashboard,
            "seller_history_dashboard_delivery_classification": source_dashboard_delivery,
            "seller_history_dashboard_separate_delivery_required": source_dashboard_delivery_required,
        }

    new_30 = _normalize_text(scrape_row.get("price_hist_new_30", ""))
    new_90 = _normalize_text(scrape_row.get("price_hist_new_90", ""))
    new_180 = _normalize_text(scrape_row.get("price_hist_new_180", ""))
    dashboard = _normalize_text(scrape_row.get("bbp_dashboard_yes_or_no", "")).upper()
    dashboard_delivery = _normalize_text(scrape_row.get("bbp_dashboard_delivery_classification", ""))
    if dashboard_delivery == "":
        dashboard_delivery = dashboard_delivery_classification(dashboard)
    dashboard_delivery_required = _normalize_text(scrape_row.get("bbp_dashboard_separate_delivery_required", ""))
    if dashboard_delivery_required == "":
        dashboard_delivery_required = "1" if dashboard_separate_delivery_required(dashboard) else "0"
    values = [_parse_float(new_30), _parse_float(new_90), _parse_float(new_180)]
    if all(value is not None for value in values):
        max_sellers = max(float(value) for value in values if value is not None)
        if dashboard == "NO" and max_sellers < 2.0:
            code = "dashboard_no_low_seller_count"
        elif dashboard == "NO":
            code = "dashboard_no_multi_seller_count"
        elif max_sellers < 2.0:
            amazon_values = [
                _parse_float(scrape_row.get("price_hist_amazon_30", "")),
                _parse_float(scrape_row.get("price_hist_amazon_90", "")),
                _parse_float(scrape_row.get("price_hist_amazon_180", "")),
            ]
            fba_values = [
                _parse_float(scrape_row.get("price_hist_fba_30", "")),
                _parse_float(scrape_row.get("price_hist_fba_90", "")),
                _parse_float(scrape_row.get("price_hist_fba_180", "")),
            ]
            buy_box_values = [
                _parse_float(scrape_row.get("price_hist_buy_box_30", "")),
                _parse_float(scrape_row.get("price_hist_buy_box_90", "")),
                _parse_float(scrape_row.get("price_hist_buy_box_180", "")),
            ]
            amazon_present = any(value is not None and value > 0 for value in amazon_values)
            fba_present = any(value is not None and value > 0 for value in fba_values)
            buy_box_present = any(value is not None and value > 0 for value in buy_box_values)
            if amazon_present and not fba_present:
                code = "amazon_only_single_seller"
            elif not amazon_present and fba_present and buy_box_present:
                code = "single_fba_seller_amazon_absent"
            else:
                code = "single_seller_owner_unclear"
        else:
            code = "seller_history_clear"
    else:
        code = "seller_history_missing"
    action = {
        "dashboard_no_low_seller_count": "remove_from_clean_pass",
        "dashboard_no_multi_seller_count": "allow_if_other_checks_pass",
        "amazon_only_single_seller": "remove_from_clean_pass",
        "single_fba_seller_amazon_absent": "allow_if_other_checks_pass",
        "single_seller_owner_unclear": "manual_review",
        "seller_history_clear": "allow_if_other_checks_pass",
        "seller_history_missing": "missing_evidence_only",
    }[code]
    return {
        "seller_history_code": code,
        "seller_history_recommended_action": action,
        "seller_history_supporting_codes": code,
        "seller_history_evidence_source": (
            "feeder_legacy_scrape_evidence_live.csv:price_hist_new_30_90_180"
            if code != "seller_history_missing"
            else "feeder_legacy_scrape_evidence_live.csv:price_hist_new_30_90_180_missing"
        ),
        "seller_history_new_30": new_30,
        "seller_history_new_90": new_90,
        "seller_history_new_180": new_180,
        "seller_history_dashboard_yes_or_no": dashboard,
        "seller_history_dashboard_delivery_classification": dashboard_delivery,
        "seller_history_dashboard_separate_delivery_required": dashboard_delivery_required,
    }


def _classify_seller_history_context(context: dict[str, str]) -> tuple[str, str, str] | None:
    code = _normalize_text(context.get("seller_history_code", ""))
    if code in SELLER_HISTORY_SUPPORTING_ONLY_CODES:
        return None
    rule = SELLER_HISTORY_TRIAGE_RULES.get(code)
    if rule is None:
        return None
    fail_type, fail_reason_code, _action = rule
    return fail_type, fail_reason_code, "f_live_price_file_pass_or_near_miss_review_latest.csv"


def _build_fail_memory_index(
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
    for col in ("event_utc", "event_id", "review_decision", "review_pack_type", "candidate_id", "asin_padded", "asin_raw"):
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].map(_normalize_text)

    work = work[work["review_decision"].map(lambda value: value.lower() == "fail")].copy()
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


def _find_fail_memory_event(
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


def _classify_near_miss_row(
    row: dict[str, str],
    *,
    fail_memory_event: dict[str, str] | None,
) -> tuple[str, str, str]:
    if fail_memory_event is not None:
        event_id = _normalize_text(fail_memory_event.get("event_id", "")) or "unknown_event_id"
        return "type_2_known_policy_or_memory", "review_memory_fail_decision", f"feeder_review_events:{event_id}"

    reviewability_state = _normalize_key(row.get("reviewability_state", ""))
    if reviewability_state == "TARGETED_RESCAN_NEEDED":
        fail_code = _normalize_key(row.get("screening_fail_code", "")) or "TARGETED_RESCAN_NEEDED"
        return (
            "type_3_missing_evidence_rescan_needed",
            "screening_" + fail_code.lower(),
            "f_live_price_file_near_miss_review_latest.csv",
        )

    fail_code = _normalize_key(row.get("screening_fail_code", "")) or _normalize_key(row.get("screening_status_reason", ""))
    if fail_code in TYPE_3_NEAR_MISS_REASON_CODES:
        return (
            "type_3_missing_evidence_rescan_needed",
            "screening_" + fail_code.lower(),
            "f_live_price_file_near_miss_review_latest.csv",
        )
    if fail_code == "":
        return (
            "type_3_missing_evidence_rescan_needed",
            "missing_fail_code",
            "f_live_price_file_near_miss_review_latest.csv",
        )
    return (
        "type_1_data_or_calc",
        "screening_" + fail_code.lower(),
        "f_live_price_file_near_miss_review_latest.csv",
    )


def _classify_pass_lane_noise_cut(
    row: dict[str, str],
    *,
    scrape_row: dict[str, str],
    seller_stock_count_available: bool,
    suppress_legacy_demand_conflict: bool = False,
) -> tuple[str, str, str] | None:
    watch_tokens = _parse_summary_tokens(row.get("watch_data_summary", ""))
    demand_confidence = _normalize_key(watch_tokens.get("DEMAND_CONFIDENCE_NOTE", "") or scrape_row.get("demand_confidence_note", ""))
    expected_units = _parse_float(row.get("expected_units_next_30d", ""))
    monthly_sold = _normalize_text(scrape_row.get("monthly_sold", ""))

    if (
        not suppress_legacy_demand_conflict
        and demand_confidence == "AMAZON_MISSING_BBP_CAPPED_TO_50"
        and expected_units is not None
        and expected_units > DEMAND_CONFLICT_UNITS_THRESHOLD
        and _value_is_missing(monthly_sold)
    ):
        return (
            "type_1_data_or_calc",
            "demand_conflict_missing_amazon_50_signal",
            "pass_pack+feeder_legacy_scrape_evidence_live",
        )

    screening_status = _normalize_key(row.get("screening_status_reason", ""))
    history_recommendation = _normalize_key(
        watch_tokens.get("HISTORY_RECOMMENDATION", "") or scrape_row.get("history_recommendation", "")
    )
    phase_recommendation = _normalize_key(scrape_row.get("phase_recommendation", ""))
    if screening_status.startswith("PASS") and (history_recommendation == "FAIL" or phase_recommendation == "AVOID"):
        return (
            "type_1_data_or_calc",
            "history_fail_overrides_pass",
            "pass_pack+feeder_legacy_scrape_evidence_live",
        )

    if (
        demand_confidence == "AMAZON_MISSING_BBP_CAPPED_TO_50"
        and expected_units is not None
        and expected_units > DEMAND_CONFLICT_UNITS_THRESHOLD
        and not seller_stock_count_available
    ):
        return (
            "type_3_missing_evidence_rescan_needed",
            "seller_stock_count_missing_rescan_required",
            "missing_seller_stock_count",
        )

    return None


def _build_triage_row(
    source_row: dict[str, str],
    *,
    review_pack_type: str,
    fail_type: str,
    fail_reason_code: str,
    evidence_source: str,
    fallback_observed_utc: str,
    demand_context: dict[str, str] | None = None,
    history_context: dict[str, str] | None = None,
    uk_review_context: dict[str, str] | None = None,
    seller_history_context: dict[str, str] | None = None,
) -> dict[str, str]:
    safe_fail_type = fail_type if fail_type in VALID_FAIL_TYPES else "type_3_missing_evidence_rescan_needed"
    safe_reason = _normalize_text(fail_reason_code) or "unclassified_missing_reason"
    demand_values = demand_context or {}
    history_values = history_context or {}
    uk_values = uk_review_context or {}
    seller_history_values = seller_history_context or {}
    return {
        "asin": _normalize_text(source_row.get("asin", "")),
        "candidate_id": _normalize_text(source_row.get("candidate_id", "")),
        "supplier_sku": _normalize_text(source_row.get("supplier_sku", "")),
        "review_pack_type": review_pack_type,
        "review_batch_id": _normalize_text(source_row.get("review_batch_id", "")),
        "fail_type": safe_fail_type,
        "fail_reason_code": safe_reason,
        "evidence_source": _normalize_text(evidence_source),
        "demand_conflict_code": _normalize_text(demand_values.get("demand_conflict_code", "")),
        "demand_recommended_action": _normalize_text(demand_values.get("demand_recommended_action", "")),
        "demand_evidence_source": _normalize_text(demand_values.get("demand_evidence_source", "")),
        "demand_supporting_codes": _normalize_text(demand_values.get("demand_supporting_codes", "")),
        "history_risk_code": _normalize_text(history_values.get("history_risk_code", "")),
        "history_recommended_action": _normalize_text(history_values.get("history_recommended_action", "")),
        "history_evidence_source": _normalize_text(history_values.get("history_evidence_source", "")),
        "history_supporting_codes": _normalize_text(history_values.get("history_supporting_codes", "")),
        "uk_review_code": _normalize_text(uk_values.get("uk_review_code", "")),
        "uk_review_recommended_action": _normalize_text(uk_values.get("uk_review_recommended_action", "")),
        "uk_review_supporting_codes": _normalize_text(uk_values.get("uk_review_supporting_codes", "")),
        "uk_review_evidence_source": _normalize_text(uk_values.get("uk_review_evidence_source", "")),
        "seller_history_code": _normalize_text(seller_history_values.get("seller_history_code", "")),
        "seller_history_recommended_action": _normalize_text(
            seller_history_values.get("seller_history_recommended_action", "")
        ),
        "seller_history_supporting_codes": _normalize_text(
            seller_history_values.get("seller_history_supporting_codes", "")
        ),
        "seller_history_evidence_source": _normalize_text(
            seller_history_values.get("seller_history_evidence_source", "")
        ),
        "seller_history_new_30": _normalize_text(seller_history_values.get("seller_history_new_30", "")),
        "seller_history_new_90": _normalize_text(seller_history_values.get("seller_history_new_90", "")),
        "seller_history_new_180": _normalize_text(seller_history_values.get("seller_history_new_180", "")),
        "seller_history_dashboard_yes_or_no": _normalize_text(
            seller_history_values.get("seller_history_dashboard_yes_or_no", "")
        ),
        "seller_history_dashboard_delivery_classification": _normalize_text(
            seller_history_values.get("seller_history_dashboard_delivery_classification", "")
        ),
        "seller_history_dashboard_separate_delivery_required": _normalize_text(
            seller_history_values.get("seller_history_dashboard_separate_delivery_required", "")
        ),
        "observed_utc": _normalize_observed_utc(source_row.get("observed_utc", ""), fallback_utc=fallback_observed_utc),
    }


def build_new_product_review_fail_triage(
    *,
    pass_path: Path = DEFAULT_PASS_PATH,
    near_miss_path: Path = DEFAULT_NEAR_MISS_PATH,
    review_events_path: Path = DEFAULT_EVENTS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    demand_audit_path: Path = DEFAULT_DEMAND_AUDIT_PATH,
    history_audit_path: Path = DEFAULT_HISTORY_AUDIT_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    review_handoffs_root: Path | None = DEFAULT_REVIEW_HANDOFFS_ROOT,
    observed_utc: str | None = None,
) -> NewProductReviewFailTriageResult:
    observed_utc_value = _normalize_text(observed_utc) or _utc_now_iso()

    review_events_df = _read_review_events(review_events_path)
    handoff_pass_frames, handoff_near_miss_frames, handoff_dirs, missing_handoff_dirs, handoff_pass_rows, handoff_near_miss_rows = (
        _read_review_handoff_pack_frames(review_events_df, review_handoffs_root)
    )
    pass_df = _combine_review_pack_frames(_read_review_pack(pass_path, "passes"), handoff_pass_frames)
    near_miss_df = _combine_review_pack_frames(
        _read_review_pack(near_miss_path, "near_misses"),
        handoff_near_miss_frames,
    )
    scrape_evidence_df = _read_csv(scrape_evidence_path)
    demand_audit_df = _read_csv(demand_audit_path)
    history_audit_df = _read_csv(history_audit_path)

    review_events_missing = not review_events_path.exists()
    scrape_evidence_missing = not scrape_evidence_path.exists()
    demand_audit_missing = not demand_audit_path.exists()
    history_audit_missing = not history_audit_path.exists()

    by_pack_candidate, by_pack_asin, by_candidate, by_asin = _build_fail_memory_index(review_events_df)
    demand_audit_index = _build_demand_audit_index(demand_audit_df)
    history_audit_index = _build_history_audit_index(history_audit_df)
    scrape_by_candidate = _latest_records(scrape_evidence_df, key_columns=["candidate_id"], utc_columns=["observed_utc", "scan_day"])
    scrape_by_asin = _latest_records(scrape_evidence_df, key_columns=["asin"], utc_columns=["observed_utc", "scan_day"])

    seller_stock_count_columns_found = sorted(
        {
            column
            for column in SELLER_STOCK_COUNT_COLUMNS
            if column in pass_df.columns or column in near_miss_df.columns or column in scrape_evidence_df.columns
        }
    )
    seller_stock_count_available = bool(seller_stock_count_columns_found)

    triage_rows: list[dict[str, str]] = []
    pass_rows_included = 0
    near_miss_rows_included = 0

    if not pass_df.empty:
        for _, row in pass_df.iterrows():
            row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
            demand_records = _find_demand_audit_records(
                review_pack_type="passes",
                candidate_id=row_dict.get("candidate_id", ""),
                asin=row_dict.get("asin", ""),
                demand_audit_index=demand_audit_index,
            )
            demand_values = _demand_context(demand_records)
            history_records = _find_history_audit_records(
                review_pack_type="passes",
                candidate_id=row_dict.get("candidate_id", ""),
                asin=row_dict.get("asin", ""),
                history_audit_index=history_audit_index,
            )
            history_values = _history_context(history_records, source_row=row_dict)
            scrape_row = scrape_by_candidate.get((_normalize_key(row_dict.get("candidate_id", "")),), {})
            if not scrape_row:
                scrape_row = scrape_by_asin.get((_normalize_key(row_dict.get("asin", "")),), {})
            uk_values = _uk_review_context(source_row=row_dict, scrape_row=scrape_row)
            seller_history_values = _seller_history_context(source_row=row_dict, scrape_row=scrape_row)
            fail_memory_event = _find_fail_memory_event(
                review_pack_type="passes",
                candidate_id=row_dict.get("candidate_id", ""),
                asin=row_dict.get("asin", ""),
                by_pack_candidate=by_pack_candidate,
                by_pack_asin=by_pack_asin,
                by_candidate=by_candidate,
                by_asin=by_asin,
            )
            if fail_memory_event is not None:
                event_id = _normalize_text(fail_memory_event.get("event_id", "")) or "unknown_event_id"
                triage_rows.append(
                    _build_triage_row(
                        row_dict,
                        review_pack_type="passes",
                        fail_type="type_2_known_policy_or_memory",
                        fail_reason_code="review_memory_fail_decision",
                        evidence_source=f"feeder_review_events:{event_id}",
                        fallback_observed_utc=observed_utc_value,
                        demand_context=demand_values,
                        history_context=history_values,
                        uk_review_context=uk_values,
                        seller_history_context=seller_history_values,
                    )
                )
                pass_rows_included += 1
                continue

            history_rule = _classify_history_context(history_values)
            if history_rule is not None:
                fail_type, fail_reason_code, evidence_source = history_rule
                triage_rows.append(
                    _build_triage_row(
                        row_dict,
                        review_pack_type="passes",
                        fail_type=fail_type,
                        fail_reason_code=fail_reason_code,
                        evidence_source=evidence_source,
                        fallback_observed_utc=observed_utc_value,
                        demand_context=demand_values,
                        history_context=history_values,
                        uk_review_context=uk_values,
                        seller_history_context=seller_history_values,
                    )
                )
                pass_rows_included += 1
                continue

            seller_history_rule = _classify_seller_history_context(seller_history_values)
            if seller_history_rule is not None:
                fail_type, fail_reason_code, evidence_source = seller_history_rule
                triage_rows.append(
                    _build_triage_row(
                        row_dict,
                        review_pack_type="passes",
                        fail_type=fail_type,
                        fail_reason_code=fail_reason_code,
                        evidence_source=evidence_source,
                        fallback_observed_utc=observed_utc_value,
                        demand_context=demand_values,
                        history_context=history_values,
                        uk_review_context=uk_values,
                        seller_history_context=seller_history_values,
                    )
                )
                pass_rows_included += 1
                continue

            demand_rule = _classify_demand_context(demand_values)
            if demand_rule is not None:
                fail_type, fail_reason_code, evidence_source = demand_rule
                triage_rows.append(
                    _build_triage_row(
                        row_dict,
                        review_pack_type="passes",
                        fail_type=fail_type,
                        fail_reason_code=fail_reason_code,
                        evidence_source=evidence_source,
                        fallback_observed_utc=observed_utc_value,
                        demand_context=demand_values,
                        history_context=history_values,
                        uk_review_context=uk_values,
                        seller_history_context=seller_history_values,
                    )
                )
                pass_rows_included += 1
                continue

            uk_rule = _classify_uk_review_context(uk_values)
            if uk_rule is not None:
                fail_type, fail_reason_code, evidence_source = uk_rule
                triage_rows.append(
                    _build_triage_row(
                        row_dict,
                        review_pack_type="passes",
                        fail_type=fail_type,
                        fail_reason_code=fail_reason_code,
                        evidence_source=evidence_source,
                        fallback_observed_utc=observed_utc_value,
                        demand_context=demand_values,
                        history_context=history_values,
                        uk_review_context=uk_values,
                        seller_history_context=seller_history_values,
                    )
                )
                pass_rows_included += 1
                continue

            pass_rule = _classify_pass_lane_noise_cut(
                row_dict,
                scrape_row=scrape_row,
                seller_stock_count_available=seller_stock_count_available,
                suppress_legacy_demand_conflict=bool(demand_values.get("demand_conflict_code", "")),
            )
            if pass_rule is None:
                continue
            fail_type, fail_reason_code, evidence_source = pass_rule
            triage_rows.append(
                _build_triage_row(
                    row_dict,
                    review_pack_type="passes",
                    fail_type=fail_type,
                    fail_reason_code=fail_reason_code,
                    evidence_source=evidence_source,
                    fallback_observed_utc=observed_utc_value,
                demand_context=demand_values,
                history_context=history_values,
                uk_review_context=uk_values,
                seller_history_context=seller_history_values,
            )
            )
            pass_rows_included += 1

    if not near_miss_df.empty:
        for _, row in near_miss_df.iterrows():
            row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
            demand_records = _find_demand_audit_records(
                review_pack_type="near_misses",
                candidate_id=row_dict.get("candidate_id", ""),
                asin=row_dict.get("asin", ""),
                demand_audit_index=demand_audit_index,
            )
            demand_values = _demand_context(demand_records)
            history_records = _find_history_audit_records(
                review_pack_type="near_misses",
                candidate_id=row_dict.get("candidate_id", ""),
                asin=row_dict.get("asin", ""),
                history_audit_index=history_audit_index,
            )
            history_values = _history_context(history_records, source_row=row_dict)
            scrape_row = scrape_by_candidate.get((_normalize_key(row_dict.get("candidate_id", "")),), {})
            if not scrape_row:
                scrape_row = scrape_by_asin.get((_normalize_key(row_dict.get("asin", "")),), {})
            uk_values = _uk_review_context(source_row=row_dict, scrape_row=scrape_row)
            seller_history_values = _seller_history_context(source_row=row_dict, scrape_row=scrape_row)
            fail_memory_event = _find_fail_memory_event(
                review_pack_type="near_misses",
                candidate_id=row_dict.get("candidate_id", ""),
                asin=row_dict.get("asin", ""),
                by_pack_candidate=by_pack_candidate,
                by_pack_asin=by_pack_asin,
                by_candidate=by_candidate,
                by_asin=by_asin,
            )
            fail_type, fail_reason_code, evidence_source = _classify_near_miss_row(
                row_dict,
                fail_memory_event=fail_memory_event,
            )
            triage_rows.append(
                _build_triage_row(
                    row_dict,
                    review_pack_type="near_misses",
                    fail_type=fail_type,
                    fail_reason_code=fail_reason_code,
                    evidence_source=evidence_source,
                    fallback_observed_utc=observed_utc_value,
                    demand_context=demand_values,
                    history_context=history_values,
                    uk_review_context=uk_values,
                    seller_history_context=seller_history_values,
                )
            )
            near_miss_rows_included += 1

    triage_df = pd.DataFrame(triage_rows, columns=OUTPUT_COLUMNS)
    if not triage_df.empty:
        triage_df = triage_df.sort_values(
            by=["fail_type", "review_pack_type", "review_batch_id", "asin", "candidate_id", "supplier_sku"],
            ascending=[True, True, True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    triage_df.to_csv(output_path, index=False)

    fail_type_counts = (
        {name: int((triage_df["fail_type"] == name).sum()) for name in sorted(VALID_FAIL_TYPES)}
        if not triage_df.empty
        else {name: 0 for name in sorted(VALID_FAIL_TYPES)}
    )
    unclassified_rows = 0
    if not triage_df.empty:
        unclassified_rows += int((~triage_df["fail_type"].isin(list(VALID_FAIL_TYPES))).sum())
        unclassified_rows += int((triage_df["fail_reason_code"].map(_normalize_text) == "").sum())

    demand_action_counts = (
        {
            str(key): int(value)
            for key, value in triage_df.loc[
                triage_df["demand_recommended_action"].map(_normalize_text) != "",
                "demand_recommended_action",
            ]
            .value_counts()
            .sort_index()
            .items()
        }
        if not triage_df.empty
        else {}
    )
    history_action_counts = (
        {
            str(key): int(value)
            for key, value in triage_df.loc[
                triage_df["history_recommended_action"].map(_normalize_text) != "",
                "history_recommended_action",
            ]
            .value_counts()
            .sort_index()
            .items()
        }
        if not triage_df.empty
        else {}
    )
    uk_review_action_counts = (
        {
            str(key): int(value)
            for key, value in triage_df.loc[
                triage_df["uk_review_recommended_action"].map(_normalize_text) != "",
                "uk_review_recommended_action",
            ]
            .value_counts()
            .sort_index()
            .items()
        }
        if not triage_df.empty
        else {}
    )
    seller_history_action_counts = (
        {
            str(key): int(value)
            for key, value in triage_df.loc[
                triage_df["seller_history_recommended_action"].map(_normalize_text) != "",
                "seller_history_recommended_action",
            ]
            .value_counts()
            .sort_index()
            .items()
        }
        if not triage_df.empty
        else {}
    )

    warnings: list[str] = []
    if review_events_missing:
        warnings.append("review memory file missing; type_2 classification needs feeder_review_events fail rows")
    if scrape_evidence_missing:
        warnings.append("scrape evidence file missing; pass-lane noise rules may downgrade to type_3 rescan requirements")
    if demand_audit_missing:
        warnings.append("demand audit file missing; Phase 3 demand-range triage columns will be blank")
    if history_audit_missing:
        warnings.append("history audit file missing; history-risk triage columns may rely on pass and near-miss pack fields")
    if not seller_stock_count_available:
        warnings.append("seller stock count is not stored in triage sources; treat stock-count-dependent checks as type_3 rescan")

    report = {
        "observed_utc": observed_utc_value,
        "pass_path": str(pass_path),
        "near_miss_path": str(near_miss_path),
        "review_events_path": str(review_events_path),
        "scrape_evidence_path": str(scrape_evidence_path),
        "demand_audit_path": str(demand_audit_path),
        "history_audit_path": str(history_audit_path),
        "output_path": str(output_path),
        "review_handoffs_root": str(review_handoffs_root) if review_handoffs_root is not None else "",
        "review_handoff_dirs_loaded": handoff_dirs,
        "review_handoff_dirs_missing": missing_handoff_dirs,
        "review_handoff_pass_input_rows": int(handoff_pass_rows),
        "review_handoff_near_miss_input_rows": int(handoff_near_miss_rows),
        "pass_input_rows": int(len(pass_df.index)),
        "near_miss_input_rows": int(len(near_miss_df.index)),
        "pass_rows_included": int(pass_rows_included),
        "near_miss_rows_included": int(near_miss_rows_included),
        "review_event_rows": int(len(review_events_df.index)),
        "review_memory_fail_rows_indexed": int(len(by_candidate)),
        "scrape_evidence_rows": int(len(scrape_evidence_df.index)),
        "demand_audit_rows": int(len(demand_audit_df.index)),
        "history_audit_rows": int(len(history_audit_df.index)),
        "seller_stock_count_available": bool(seller_stock_count_available),
        "seller_stock_count_columns_found": seller_stock_count_columns_found,
        "fail_type_counts": fail_type_counts,
        "demand_action_counts": demand_action_counts,
        "history_action_counts": history_action_counts,
        "uk_review_action_counts": uk_review_action_counts,
        "seller_history_action_counts": seller_history_action_counts,
        "unclassified_rows": int(unclassified_rows),
        "warnings": warnings,
    }
    return NewProductReviewFailTriageResult(triage_df=triage_df, output_path=output_path, report=report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build New Product Review fail triage using pass and near-miss review packs.")
    parser.add_argument("--pass-path", type=Path, default=DEFAULT_PASS_PATH)
    parser.add_argument("--near-miss-path", type=Path, default=DEFAULT_NEAR_MISS_PATH)
    parser.add_argument("--review-events-path", type=Path, default=DEFAULT_EVENTS_PATH)
    parser.add_argument("--scrape-evidence-path", type=Path, default=DEFAULT_SCRAPE_EVIDENCE_PATH)
    parser.add_argument("--demand-audit-path", type=Path, default=DEFAULT_DEMAND_AUDIT_PATH)
    parser.add_argument("--history-audit-path", type=Path, default=DEFAULT_HISTORY_AUDIT_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--review-handoffs-root", type=Path, default=DEFAULT_REVIEW_HANDOFFS_ROOT)
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_new_product_review_fail_triage(
        pass_path=args.pass_path,
        near_miss_path=args.near_miss_path,
        review_events_path=args.review_events_path,
        scrape_evidence_path=args.scrape_evidence_path,
        demand_audit_path=args.demand_audit_path,
        history_audit_path=args.history_audit_path,
        output_path=args.output_path,
        review_handoffs_root=args.review_handoffs_root,
        observed_utc=_normalize_text(args.observed_utc) or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
