from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
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
    read_review_pack_dataframe,
)


DEFAULT_PASS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
DEFAULT_NEAR_MISS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_BACKTEST_SUMMARY_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
DEFAULT_REVIEW_EVENTS_PATH = ROOT / "out" / "systems" / "F" / "inbox" / "feeder_review_events.csv"
DEFAULT_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_demand_range_bbp_conflict_audit_latest.csv"

OUTPUT_COLUMNS = [
    "asin",
    "candidate_id",
    "supplier_sku",
    "review_pack_type",
    "amazon_demand_signal",
    "amazon_demand_floor",
    "amazon_demand_ceiling",
    "bbp_units",
    "expected_units_next_30d",
    "demand_conflict_code",
    "uk_reviews",
    "variant_reviews",
    "confidence_adjustment",
    "recommended_action",
    "evidence_source",
]

VALID_DEMAND_CONFLICT_CODES = {
    "amazon_blank_bbp_high",
    "amazon_blank_bbp_low",
    "amazon_50_bbp_reasonable",
    "amazon_50_bbp_warn",
    "amazon_50_bbp_inflated",
    "weak_uk_review_confirms_demand_risk",
    "seller_stock_missing_for_demand_check",
}

BASE_RECOMMENDED_ACTIONS = {
    "amazon_blank_bbp_high": "remove_from_clean_pass",
    "amazon_blank_bbp_low": "allow_if_other_checks_pass",
    "amazon_50_bbp_reasonable": "allow_if_other_checks_pass",
    "amazon_50_bbp_warn": "manual_review",
    "amazon_50_bbp_inflated": "remove_from_clean_pass",
    "weak_uk_review_confirms_demand_risk": "strengthen_demand_risk_action",
    "seller_stock_missing_for_demand_check": "targeted_rescan_needed",
}

HIGH_OR_REVIEW_RISK_CODES = {
    "amazon_blank_bbp_high",
    "amazon_50_bbp_warn",
    "amazon_50_bbp_inflated",
}

MISSING_TEXT_MARKERS = {"", "na", "n/a", "none", "null", "nan"}
AMAZON_BLANK_CEILING = 49.0
AMAZON_50_REASONABLE_MAX = 100.0
AMAZON_50_WARN_MAX = 250.0
WEAK_UK_REVIEW_THRESHOLD = 6.0

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


@dataclass(frozen=True)
class DemandRangeBbpConflictAuditResult:
    audit_df: pd.DataFrame
    output_path: Path
    report: dict[str, Any]


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


def _parse_float(value: object) -> float | None:
    text = _normalize_text(value)
    if _value_is_missing(text):
        return None
    cleaned = text.replace(",", "").replace("GBP", "").replace("gbp", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_to_text(value: float | int | None) -> str:
    if value is None:
        return ""
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _parse_amazon_sold_floor(value: object) -> float | None:
    text = _normalize_text(value)
    if _value_is_missing(text):
        return None
    direct = _parse_float(text)
    if direct is not None:
        return direct

    match = AMAZON_SOLD_PATTERN.search(text)
    if not match:
        return None
    parsed = _parse_float(match.group("number"))
    if parsed is None:
        return None
    suffix = _normalize_text(match.group("suffix"))
    if suffix.lower() == "k":
        parsed *= 1000.0
    return parsed


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
        if key_norm:
            tokens[key_norm] = _normalize_text(value)
    return tokens


def _latest_records(
    df: pd.DataFrame,
    *,
    key_columns: list[str],
    utc_columns: list[str],
) -> dict[tuple[str, ...], dict[str, str]]:
    if df.empty:
        return {}
    work = df.copy()
    for column in key_columns + utc_columns:
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)

    utc_sort = None
    for column in utc_columns:
        parsed = pd.to_datetime(work[column], errors="coerce", utc=True, format="mixed")
        utc_sort = parsed if utc_sort is None else utc_sort.fillna(parsed)
    if utc_sort is not None:
        work["_utc_sort"] = utc_sort
        work = work.sort_values("_utc_sort", ascending=False, kind="stable")

    records: dict[tuple[str, ...], dict[str, str]] = {}
    for _, row in work.iterrows():
        key = tuple(_normalize_key(row.get(column, "")) for column in key_columns)
        if any(part == "" for part in key):
            continue
        if key in records:
            continue
        records[key] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return records


def _lookup_latest(
    primary: dict[tuple[str, ...], dict[str, str]],
    primary_key: tuple[str, ...],
    secondary: dict[tuple[str, ...], dict[str, str]],
    secondary_key: tuple[str, ...],
    tertiary: dict[tuple[str, ...], dict[str, str]],
    tertiary_key: tuple[str, ...],
) -> dict[str, str]:
    if primary_key in primary:
        return primary[primary_key]
    if secondary_key in secondary:
        return secondary[secondary_key]
    if tertiary_key in tertiary:
        return tertiary[tertiary_key]
    return {}


def _build_review_event_index(
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
    for column in ("event_utc", "event_id", "review_pack_type", "candidate_id", "asin_padded", "asin_raw"):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)

    work["_event_utc_ts"] = pd.to_datetime(work["event_utc"], errors="coerce", utc=True, format="mixed")
    work = work.sort_values(by=["_event_utc_ts", "event_id"], ascending=[False, False], kind="stable")

    for _, row in work.iterrows():
        event = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        pack_type = _normalize_key(event.get("review_pack_type", ""))
        candidate = _normalize_key(event.get("candidate_id", ""))
        asin = _normalize_key(event.get("asin_padded", "")) or _normalize_key(event.get("asin_raw", ""))

        if candidate:
            by_candidate.setdefault(candidate, event)
            if pack_type:
                by_pack_candidate.setdefault((pack_type, candidate), event)
        if asin:
            by_asin.setdefault(asin, event)
            if pack_type:
                by_pack_asin.setdefault((pack_type, asin), event)

    return by_pack_candidate, by_pack_asin, by_candidate, by_asin


def _find_review_event(
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

    if pack and candidate and (pack, candidate) in by_pack_candidate:
        return by_pack_candidate[(pack, candidate)]
    if pack and asin_key and (pack, asin_key) in by_pack_asin:
        return by_pack_asin[(pack, asin_key)]
    if candidate and candidate in by_candidate:
        return by_candidate[candidate]
    if asin_key and asin_key in by_asin:
        return by_asin[asin_key]
    return None


def _amazon_range(scrape_row: dict[str, str]) -> tuple[str, float, float | None]:
    raw_signal = _normalize_text(scrape_row.get("monthly_sold", ""))
    signal_floor = _parse_amazon_sold_floor(raw_signal)
    floor_column = _parse_amazon_sold_floor(scrape_row.get("amazon_bought_floor", ""))

    floor = signal_floor if signal_floor is not None else floor_column
    if floor is None or floor < 50:
        return "", 0.0, AMAZON_BLANK_CEILING

    signal = raw_signal
    if signal == "":
        signal = f"{_num_to_text(floor)}+ bought in past month"
    return signal, floor, None


def _pick_bbp_units(scrape_row: dict[str, str], backtest_row: dict[str, str]) -> float | None:
    for value in (
        scrape_row.get("bbp_sales_replay_demand_basis_units", ""),
        backtest_row.get("raw_monthly_units", ""),
        scrape_row.get("bbp_monthly_units_chosen", ""),
        backtest_row.get("qualified_monthly_units", ""),
    ):
        parsed = _parse_float(value)
        if parsed is not None:
            return parsed
    return None


def _pick_expected_units(source_row: dict[str, str], backtest_row: dict[str, str]) -> float | None:
    for value in (
        source_row.get("expected_units_next_30d", ""),
        backtest_row.get("expected_units_next_30d", ""),
        backtest_row.get("qualified_monthly_units", ""),
    ):
        parsed = _parse_float(value)
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
    source_row: dict[str, str],
    scrape_row: dict[str, str],
    backtest_row: dict[str, str],
    seller_stock_columns_found: list[str],
) -> bool:
    if not seller_stock_columns_found:
        return True
    for column in seller_stock_columns_found:
        for row in (source_row, scrape_row, backtest_row):
            if column in row and not _value_is_missing(row.get(column, "")):
                return False
    return True


def _uk_review_is_weak(uk_reviews: float | None) -> bool:
    return uk_reviews is not None and uk_reviews < WEAK_UK_REVIEW_THRESHOLD


def _evidence_source(
    *,
    review_pack_type: str,
    scrape_row: dict[str, str],
    backtest_row: dict[str, str],
    review_event: dict[str, str] | None,
) -> str:
    review_file_stem = {
        "passes": "pass",
        "near_misses": "near_miss",
    }.get(review_pack_type, review_pack_type)
    parts = [f"f_live_price_file_{review_file_stem}_review_latest.csv"]
    parts.append("feeder_legacy_scrape_evidence_live.csv" if scrape_row else "scrape_evidence_missing")
    parts.append("feeder_backtest_summary_live.csv" if backtest_row else "backtest_summary_missing")
    if review_event is not None:
        event_id = _normalize_text(review_event.get("event_id", "")) or "unknown_event_id"
        parts.append(f"feeder_review_events:{event_id}")
    return "|".join(parts)


def _build_output_row(
    *,
    source_row: dict[str, str],
    review_pack_type: str,
    amazon_signal: str,
    amazon_floor: float,
    amazon_ceiling: float | None,
    bbp_units: float | None,
    expected_units: float | None,
    demand_conflict_code: str,
    uk_reviews: float | None,
    variant_reviews: float | None,
    confidence_adjustment: str,
    recommended_action: str,
    evidence_source: str,
) -> dict[str, str]:
    return {
        "asin": _normalize_text(source_row.get("asin", "")),
        "candidate_id": _normalize_text(source_row.get("candidate_id", "")),
        "supplier_sku": _normalize_text(source_row.get("supplier_sku", "")),
        "review_pack_type": review_pack_type,
        "amazon_demand_signal": amazon_signal,
        "amazon_demand_floor": _num_to_text(amazon_floor),
        "amazon_demand_ceiling": _num_to_text(amazon_ceiling),
        "bbp_units": _num_to_text(bbp_units),
        "expected_units_next_30d": _num_to_text(expected_units),
        "demand_conflict_code": demand_conflict_code,
        "uk_reviews": _num_to_text(uk_reviews),
        "variant_reviews": _num_to_text(variant_reviews),
        "confidence_adjustment": confidence_adjustment,
        "recommended_action": recommended_action,
        "evidence_source": evidence_source,
    }


def _audit_source_row(
    *,
    source_row: dict[str, str],
    review_pack_type: str,
    scrape_row: dict[str, str],
    backtest_row: dict[str, str],
    review_event: dict[str, str] | None,
    seller_stock_columns_found: list[str],
) -> list[dict[str, str]]:
    amazon_signal, amazon_floor, amazon_ceiling = _amazon_range(scrape_row)
    bbp_units = _pick_bbp_units(scrape_row, backtest_row)
    expected_units = _pick_expected_units(source_row, backtest_row)
    primary_code = _classify_primary_demand(
        amazon_floor=amazon_floor,
        bbp_units=bbp_units,
        expected_units=expected_units,
    )
    uk_reviews = _parse_float(scrape_row.get("historical_uk_reviews", ""))
    variant_reviews = _parse_float(scrape_row.get("variant_reviews", ""))
    if variant_reviews is None:
        variant_reviews = _parse_float(scrape_row.get("matching_variant_reviews", ""))

    demand_risk = primary_code in HIGH_OR_REVIEW_RISK_CODES
    weak_uk_reviews = demand_risk and _uk_review_is_weak(uk_reviews)
    base_evidence = _evidence_source(
        review_pack_type=review_pack_type,
        scrape_row=scrape_row,
        backtest_row=backtest_row,
        review_event=review_event,
    )

    rows = [
        _build_output_row(
            source_row=source_row,
            review_pack_type=review_pack_type,
            amazon_signal=amazon_signal,
            amazon_floor=amazon_floor,
            amazon_ceiling=amazon_ceiling,
            bbp_units=bbp_units,
            expected_units=expected_units,
            demand_conflict_code=primary_code,
            uk_reviews=uk_reviews,
            variant_reviews=variant_reviews,
            confidence_adjustment="weak_uk_review_confirms_demand_risk" if weak_uk_reviews else "",
            recommended_action=BASE_RECOMMENDED_ACTIONS[primary_code],
            evidence_source=base_evidence,
        )
    ]

    if weak_uk_reviews:
        rows.append(
            _build_output_row(
                source_row=source_row,
                review_pack_type=review_pack_type,
                amazon_signal=amazon_signal,
                amazon_floor=amazon_floor,
                amazon_ceiling=amazon_ceiling,
                bbp_units=bbp_units,
                expected_units=expected_units,
                demand_conflict_code="weak_uk_review_confirms_demand_risk",
                uk_reviews=uk_reviews,
                variant_reviews=variant_reviews,
                confidence_adjustment="uk_reviews_below_6",
                recommended_action=BASE_RECOMMENDED_ACTIONS["weak_uk_review_confirms_demand_risk"],
                evidence_source="feeder_legacy_scrape_evidence_live.csv",
            )
        )

    if demand_risk and _seller_stock_missing_for_record(
        source_row=source_row,
        scrape_row=scrape_row,
        backtest_row=backtest_row,
        seller_stock_columns_found=seller_stock_columns_found,
    ):
        rows.append(
            _build_output_row(
                source_row=source_row,
                review_pack_type=review_pack_type,
                amazon_signal=amazon_signal,
                amazon_floor=amazon_floor,
                amazon_ceiling=amazon_ceiling,
                bbp_units=bbp_units,
                expected_units=expected_units,
                demand_conflict_code="seller_stock_missing_for_demand_check",
                uk_reviews=uk_reviews,
                variant_reviews=variant_reviews,
                confidence_adjustment="seller_stock_count_not_stored",
                recommended_action=BASE_RECOMMENDED_ACTIONS["seller_stock_missing_for_demand_check"],
                evidence_source="seller_stock_count_missing",
            )
        )

    return rows


def build_demand_range_bbp_conflict_audit(
    *,
    pass_path: Path = DEFAULT_PASS_PATH,
    near_miss_path: Path = DEFAULT_NEAR_MISS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    backtest_summary_path: Path = DEFAULT_BACKTEST_SUMMARY_PATH,
    review_events_path: Path = DEFAULT_REVIEW_EVENTS_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> DemandRangeBbpConflictAuditResult:
    pass_df = _read_review_pack(pass_path, "passes")
    near_miss_df = _read_review_pack(near_miss_path, "near_misses")
    scrape_df = _read_csv(scrape_evidence_path)
    backtest_df = _read_csv(backtest_summary_path)
    review_events_df = _read_review_events(review_events_path)

    scrape_by_candidate = _latest_records(scrape_df, key_columns=["candidate_id"], utc_columns=["observed_utc", "scan_day"])
    scrape_by_supplier_asin = _latest_records(
        scrape_df,
        key_columns=["supplier_sku", "asin"],
        utc_columns=["observed_utc", "scan_day"],
    )
    scrape_by_asin = _latest_records(scrape_df, key_columns=["asin"], utc_columns=["observed_utc", "scan_day"])
    backtest_by_supplier_asin = _latest_records(
        backtest_df,
        key_columns=["seller_sku", "asin"],
        utc_columns=["observed_utc"],
    )
    backtest_by_asin = _latest_records(backtest_df, key_columns=["asin"], utc_columns=["observed_utc"])
    by_pack_candidate, by_pack_asin, by_candidate, by_asin = _build_review_event_index(review_events_df)

    seller_stock_columns_found = _seller_stock_count_columns_found([pass_df, near_miss_df, scrape_df, backtest_df])
    output_rows: list[dict[str, str]] = []

    for review_pack_type, source_df in (("passes", pass_df), ("near_misses", near_miss_df)):
        if source_df.empty:
            continue
        for _, row in source_df.iterrows():
            source_row = {column: _normalize_text(value) for column, value in row.to_dict().items()}
            candidate_key = (_normalize_key(source_row.get("candidate_id", "")),)
            supplier_asin_key = (_normalize_key(source_row.get("supplier_sku", "")), _normalize_key(source_row.get("asin", "")))
            asin_key = (_normalize_key(source_row.get("asin", "")),)
            scrape_row = _lookup_latest(
                scrape_by_candidate,
                candidate_key,
                scrape_by_supplier_asin,
                supplier_asin_key,
                scrape_by_asin,
                asin_key,
            )
            backtest_row = {}
            if supplier_asin_key in backtest_by_supplier_asin:
                backtest_row = backtest_by_supplier_asin[supplier_asin_key]
            elif asin_key in backtest_by_asin:
                backtest_row = backtest_by_asin[asin_key]
            review_event = _find_review_event(
                review_pack_type=review_pack_type,
                candidate_id=source_row.get("candidate_id", ""),
                asin=source_row.get("asin", ""),
                by_pack_candidate=by_pack_candidate,
                by_pack_asin=by_pack_asin,
                by_candidate=by_candidate,
                by_asin=by_asin,
            )
            output_rows.extend(
                _audit_source_row(
                    source_row=source_row,
                    review_pack_type=review_pack_type,
                    scrape_row=scrape_row,
                    backtest_row=backtest_row,
                    review_event=review_event,
                    seller_stock_columns_found=seller_stock_columns_found,
                )
            )

    audit_df = pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS)
    if not audit_df.empty:
        audit_df = audit_df.sort_values(
            by=["review_pack_type", "asin", "candidate_id", "supplier_sku", "demand_conflict_code"],
            ascending=[True, True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)

    unclassified_rows = 0
    if not audit_df.empty:
        unclassified_rows += int((~audit_df["demand_conflict_code"].isin(VALID_DEMAND_CONFLICT_CODES)).sum())
        unclassified_rows += int((audit_df["demand_conflict_code"].map(_normalize_text) == "").sum())
        unclassified_rows += int((audit_df["recommended_action"].map(_normalize_text) == "").sum())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(output_path, index=False)

    code_counts = (
        {str(key): int(value) for key, value in audit_df["demand_conflict_code"].value_counts().sort_index().items()}
        if not audit_df.empty
        else {}
    )
    action_counts = (
        {str(key): int(value) for key, value in audit_df["recommended_action"].value_counts().sort_index().items()}
        if not audit_df.empty
        else {}
    )
    b0_rows = audit_df.loc[audit_df["asin"].map(_normalize_key) == "B0C8C3JF9X"].to_dict("records") if not audit_df.empty else []

    report = {
        "pass_input_rows": int(len(pass_df.index)),
        "near_miss_input_rows": int(len(near_miss_df.index)),
        "total_input_rows_audited": int(len(pass_df.index) + len(near_miss_df.index)),
        "audit_output_rows": int(len(audit_df.index)),
        "scrape_evidence_rows": int(len(scrape_df.index)),
        "backtest_summary_rows": int(len(backtest_df.index)),
        "review_event_rows": int(len(review_events_df.index)),
        "seller_stock_count_columns_found": seller_stock_columns_found,
        "unclassified_rows": int(unclassified_rows),
        "demand_conflict_code_counts": code_counts,
        "recommended_action_counts": action_counts,
        "b0c8c3jf9x_flagged": bool(b0_rows),
        "b0c8c3jf9x_codes": sorted({row["demand_conflict_code"] for row in b0_rows}),
        "rules_requiring_new_data_before_enforcement": (
            ["seller_stock_missing_for_demand_check"] if not seller_stock_columns_found else []
        ),
        "output_path": str(output_path),
    }
    return DemandRangeBbpConflictAuditResult(audit_df=audit_df, output_path=output_path, report=report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only Amazon demand range versus BBP demand conflict audit.")
    parser.add_argument("--pass-path", type=Path, default=DEFAULT_PASS_PATH)
    parser.add_argument("--near-miss-path", type=Path, default=DEFAULT_NEAR_MISS_PATH)
    parser.add_argument("--scrape-evidence-path", type=Path, default=DEFAULT_SCRAPE_EVIDENCE_PATH)
    parser.add_argument("--backtest-summary-path", type=Path, default=DEFAULT_BACKTEST_SUMMARY_PATH)
    parser.add_argument("--review-events-path", type=Path, default=DEFAULT_REVIEW_EVENTS_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_demand_range_bbp_conflict_audit(
        pass_path=args.pass_path,
        near_miss_path=args.near_miss_path,
        scrape_evidence_path=args.scrape_evidence_path,
        backtest_summary_path=args.backtest_summary_path,
        review_events_path=args.review_events_path,
        output_path=args.output_path,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
