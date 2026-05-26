from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
DEFAULT_INPUT_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_input_view_live.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_TARGET_COUNT = 18

BUCKET_ORDER = [
    "certain_fail",
    "almost_pass",
    "just_passed",
    "on_the_line",
    "manual_review_or_unclear",
    "demand_or_profit_inflation_risk",
]

SUMMARY_REQUIRED_COLUMNS = [
    "seller_sku",
    "asin",
    "summary_status",
    "summary_reason_codes",
    "history_confidence",
    "market_viability_score",
    "exit_risk_score",
    "estimated_total_profit_gbp",
    "estimated_monthly_profit_gbp",
    "capital_lockup_days",
    "sellable_ceiling_zone",
    "amazon_risk_level",
    "compression_risk_level",
    "recommendation",
    "manual_review_reason",
    "share_assumption_basis",
    "seasonality_flag",
    "failure_event_count",
    "longest_failure_streak_days",
]

UNCLEAR_REASON_NEEDLES = [
    "input_not_ready",
    "insufficient_paired_price_bsr_days",
    "history_confidence_low",
    "attribution_confidence_low",
    "attribution_channel_pairing_sparse",
    "attribution_buy_box_coverage_low",
    "no_product_db_match",
    "needs_human",
    "unclear",
]


@dataclass(frozen=True)
class CalibrationBuildResult:
    selected_df: pd.DataFrame
    report_path: Path
    latest_path: Path
    markdown_path: Path
    blockers: tuple[str, ...]
    bucket_availability: dict[str, int]


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


def _normalize_lower(value: object) -> str:
    return _normalize_text(value).lower()


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _to_float(value: object) -> float:
    text = _normalize_text(value)
    if text == "":
        return 0.0
    try:
        parsed = float(text)
    except ValueError:
        return 0.0
    if math.isnan(parsed) or math.isinf(parsed):
        return 0.0
    return parsed


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _ensure_summary_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in SUMMARY_REQUIRED_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out


def _summary_status(row: pd.Series) -> str:
    return _normalize_lower(row.get("summary_status", ""))


def _recommendation(row: pd.Series) -> str:
    return _normalize_lower(row.get("recommendation", ""))


def _history_confidence(row: pd.Series) -> str:
    return _normalize_lower(row.get("history_confidence", ""))


def _market_viability(row: pd.Series) -> float:
    return _to_float(row.get("market_viability_score", ""))


def _exit_risk(row: pd.Series) -> float:
    return _to_float(row.get("exit_risk_score", ""))


def _monthly_profit(row: pd.Series) -> float:
    return _to_float(row.get("estimated_monthly_profit_gbp", ""))


def _total_profit(row: pd.Series) -> float:
    return _to_float(row.get("estimated_total_profit_gbp", ""))


def _capital_lockup_days(row: pd.Series) -> float:
    return _to_float(row.get("capital_lockup_days", ""))


def _failure_streak_days(row: pd.Series) -> float:
    return _to_float(row.get("longest_failure_streak_days", ""))


def _reason_blob(row: pd.Series) -> str:
    parts = [
        _normalize_lower(row.get("manual_review_reason", "")),
        _normalize_lower(row.get("summary_reason_codes", "")),
    ]
    return "|".join(part for part in parts if part)


def _is_ready(row: pd.Series) -> bool:
    return _summary_status(row) == "ready"


def _is_learning_confidence(row: pd.Series) -> bool:
    return _history_confidence(row) in {"medium", "high"}


def _is_amazon_learning_case(row: pd.Series) -> bool:
    return _is_learning_confidence(row) and _normalize_lower(row.get("amazon_risk_level", "")) in {"high", "critical"}


def _is_compression_learning_case(row: pd.Series) -> bool:
    return _is_learning_confidence(row) and _normalize_lower(row.get("compression_risk_level", "")) == "high"


def _has_share_prior_risk(row: pd.Series) -> bool:
    reason_blob = _reason_blob(row)
    share_basis = _normalize_lower(row.get("share_assumption_basis", ""))
    return (
        "prior" in share_basis
        or "share_source_sparse_asin_blend" in reason_blob
        or "share_sparse_asin_history" in reason_blob
    )


def _has_ceiling_risk(row: pd.Series) -> bool:
    return _normalize_lower(row.get("sellable_ceiling_zone", "")) in {"stretched", "probable_ceiling_breach"}


def _has_long_lockup(row: pd.Series) -> bool:
    return _capital_lockup_days(row) >= 180.0


def _has_seasonality_signal(row: pd.Series) -> bool:
    return _normalize_text(row.get("seasonality_flag", "")) != ""


def _has_positive_profit(row: pd.Series) -> bool:
    return _monthly_profit(row) > 0.0 or _total_profit(row) > 0.0


def _is_manual_review_or_unclear(row: pd.Series) -> bool:
    reason_blob = _reason_blob(row)
    return (
        not _is_ready(row)
        or _recommendation(row) == "manual review"
        or _history_confidence(row) == "low"
        or _contains_any(reason_blob, UNCLEAR_REASON_NEEDLES)
    )


def _has_profit_inflation_risk(row: pd.Series) -> bool:
    return (
        _has_share_prior_risk(row)
        or _has_ceiling_risk(row)
        or _has_long_lockup(row)
        or _has_seasonality_signal(row)
    )


def _bucket_membership(row: pd.Series) -> dict[str, bool]:
    recommendation = _recommendation(row)
    viability = _market_viability(row)
    exit_risk = _exit_risk(row)
    monthly_profit = _monthly_profit(row)
    total_profit = _total_profit(row)
    amazon_risk = _normalize_lower(row.get("amazon_risk_level", ""))
    compression_risk = _normalize_lower(row.get("compression_risk_level", ""))

    manual_review_or_unclear = _is_manual_review_or_unclear(row)
    demand_or_profit_inflation_risk = (
        _is_ready(row) and not manual_review_or_unclear and _has_positive_profit(row) and _has_profit_inflation_risk(row)
    )
    certain_fail = (
        _is_ready(row)
        and not manual_review_or_unclear
        and recommendation in {"avoid", "exit-only"}
        and (
            viability < 35.0
            or exit_risk >= 70.0
            or amazon_risk == "critical"
            or (monthly_profit <= 0.0 and total_profit <= 0.0)
            or _failure_streak_days(row) >= 90.0
        )
    )
    almost_pass = (
        _is_ready(row)
        and not manual_review_or_unclear
        and recommendation in {"avoid", "exit-only"}
        and not certain_fail
        and (
            (35.0 <= viability < 55.0)
            or (_has_positive_profit(row) and exit_risk < 25.0)
            or ((45.0 <= viability <= 60.0) and amazon_risk in {"medium", "high"})
            or compression_risk == "high"
        )
    )
    just_passed = (
        _is_ready(row)
        and not manual_review_or_unclear
        and recommendation in {"normal fit", "managed fit"}
        and not demand_or_profit_inflation_risk
        and (
            recommendation == "managed fit"
            or viability < 85.0
            or exit_risk >= 10.0
            or amazon_risk in {"high", "critical"}
            or compression_risk == "high"
        )
    )
    on_the_line = (
        _is_ready(row)
        and not manual_review_or_unclear
        and not certain_fail
        and not demand_or_profit_inflation_risk
        and (
            recommendation in {"managed fit", "exit-only"}
            or (45.0 <= viability <= 70.0)
            or (10.0 <= exit_risk <= 35.0)
            or (recommendation == "normal fit" and amazon_risk in {"high", "critical"})
            or (recommendation == "normal fit" and compression_risk == "high")
        )
    )

    return {
        "certain_fail": certain_fail,
        "almost_pass": almost_pass,
        "just_passed": just_passed,
        "on_the_line": on_the_line,
        "manual_review_or_unclear": manual_review_or_unclear,
        "demand_or_profit_inflation_risk": demand_or_profit_inflation_risk,
    }


def _bucket_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    bucket_flags: dict[str, list[bool]] = {bucket: [] for bucket in BUCKET_ORDER}
    for _, row in df.iterrows():
        membership = _bucket_membership(row)
        for bucket in BUCKET_ORDER:
            bucket_flags[bucket].append(bool(membership[bucket]))
    return {
        bucket: pd.Series(values, index=df.index, dtype=bool)
        for bucket, values in bucket_flags.items()
    }


def _row_sort_key(row: pd.Series) -> tuple[str, str]:
    return (_normalize_text(row.get("asin", "")).upper(), _normalize_text(row.get("seller_sku", "")).upper())


def _primary_bucket(index: int, masks: dict[str, pd.Series], df: pd.DataFrame) -> str:
    for bucket in BUCKET_ORDER:
        if bool(masks[bucket].loc[index]):
            return bucket
    row = df.loc[index]
    if _is_manual_review_or_unclear(row):
        return "manual_review_or_unclear"
    return "on_the_line"


def _candidate_priority(row: pd.Series, bucket: str) -> tuple[object, ...]:
    viability = _market_viability(row)
    exit_risk = _exit_risk(row)
    monthly_profit = _monthly_profit(row)
    lockup = _capital_lockup_days(row)
    inflation_signals = (
        int(_has_share_prior_risk(row))
        + int(_has_ceiling_risk(row))
        + int(_has_long_lockup(row))
        + int(_has_seasonality_signal(row))
    )
    amazon_learning_case = _is_amazon_learning_case(row)
    compression_learning_case = _is_compression_learning_case(row)
    learning_priority = 0 if (amazon_learning_case or compression_learning_case) else 1
    asin_key, sku_key = _row_sort_key(row)

    if bucket == "certain_fail":
        return (learning_priority, viability, -exit_risk, -lockup, asin_key, sku_key)
    if bucket == "almost_pass":
        return (learning_priority, abs(viability - 50.0), exit_risk, -monthly_profit, asin_key, sku_key)
    if bucket == "just_passed":
        return (
            0 if (amazon_learning_case or compression_learning_case) else 1,
            abs(viability - 65.0),
            -exit_risk,
            monthly_profit,
            asin_key,
            sku_key,
        )
    if bucket == "on_the_line":
        return (
            learning_priority,
            abs(viability - 55.0) + abs(exit_risk - 20.0),
            -monthly_profit,
            asin_key,
            sku_key,
        )
    if bucket == "manual_review_or_unclear":
        reason_blob = _reason_blob(row)
        return (
            0 if "input_not_ready" in reason_blob else 1,
            0 if "history_confidence_low" in reason_blob else 1,
            asin_key,
            sku_key,
        )
    if bucket == "demand_or_profit_inflation_risk":
        return (learning_priority, -inflation_signals, -monthly_profit, -lockup, asin_key, sku_key)
    return (asin_key, sku_key)


def _selected_bucket_counts_from_index_map(selected_bucket_by_index: dict[int, str]) -> dict[str, int]:
    counts = {bucket: 0 for bucket in BUCKET_ORDER}
    for bucket in selected_bucket_by_index.values():
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _ensure_learning_case_coverage(
    *,
    selected_indexes: list[int],
    selected_bucket_by_index: dict[int, str],
    used_indexes: set[int],
    masks: dict[str, pd.Series],
    df: pd.DataFrame,
    learning_check,
) -> None:
    if any(learning_check(df.loc[idx]) for idx in selected_indexes):
        return

    candidate_indexes = [
        int(idx)
        for idx in df.index.tolist()
        if int(idx) not in used_indexes and learning_check(df.loc[idx])
    ]
    if not candidate_indexes:
        return

    candidate_indexes = sorted(
        candidate_indexes,
        key=lambda idx: _candidate_priority(df.loc[idx], _primary_bucket(idx, masks, df)),
    )
    candidate_idx = candidate_indexes[0]

    selected_counts = _selected_bucket_counts_from_index_map(selected_bucket_by_index)
    removable_indexes = [
        idx
        for idx in selected_indexes
        if selected_counts.get(selected_bucket_by_index[idx], 0) > 1 and not learning_check(df.loc[idx])
    ]
    if not removable_indexes:
        return

    removable_indexes = sorted(
        removable_indexes,
        key=lambda idx: (
            -selected_counts.get(selected_bucket_by_index[idx], 0),
            *_candidate_priority(df.loc[idx], selected_bucket_by_index[idx]),
        ),
    )
    remove_idx = removable_indexes[0]
    remove_pos = selected_indexes.index(remove_idx)

    selected_indexes[remove_pos] = candidate_idx
    used_indexes.discard(remove_idx)
    used_indexes.add(candidate_idx)
    selected_bucket_by_index.pop(remove_idx, None)
    selected_bucket_by_index[candidate_idx] = _primary_bucket(candidate_idx, masks, df)


def _bucket_tags(row: pd.Series, primary_bucket: str) -> str:
    membership = _bucket_membership(row)
    tags = [bucket for bucket in BUCKET_ORDER if bucket != primary_bucket and membership[bucket]]

    if _is_amazon_learning_case(row):
        tags.append("amazon_risk_learning_case")
    if _is_compression_learning_case(row):
        tags.append("compression_risk_learning_case")
    if _has_share_prior_risk(row):
        tags.append("share_prior_risk")
    if _has_ceiling_risk(row):
        tags.append(_normalize_lower(row.get("sellable_ceiling_zone", "")) or "ceiling_risk")
    if _has_long_lockup(row):
        tags.append("capital_lockup_risk")
    seasonality_flag = _normalize_lower(row.get("seasonality_flag", ""))
    if seasonality_flag:
        tags.append(seasonality_flag)
    if _history_confidence(row) == "low":
        tags.append("low_confidence")
    if not _is_ready(row):
        tags.append("not_ready")
    if _critical_amazon_recommendation_mismatch_flag(row):
        tags.append("critical_amazon_recommendation_mismatch")

    seen: set[str] = set()
    ordered_tags: list[str] = []
    for tag in tags:
        if tag and tag not in seen:
            seen.add(tag)
            ordered_tags.append(tag)
    return "|".join(ordered_tags)


def _int_text(value: float) -> str:
    return str(int(round(value)))


def _review_prompt(row: pd.Series, primary_bucket: str) -> str:
    recommendation = _normalize_text(row.get("recommendation", "")) or "Manual review"
    confidence = _normalize_text(row.get("history_confidence", "")) or "unknown"
    viability_text = _int_text(_market_viability(row))
    exit_risk_text = _int_text(_exit_risk(row))
    monthly_profit_text = _int_text(_monthly_profit(row))

    detail_parts = [
        f"current result {recommendation}",
        f"viability {viability_text}",
        f"exit risk {exit_risk_text}",
        f"monthly profit GBP {monthly_profit_text}",
        f"confidence {confidence.lower()}",
    ]

    amazon_risk = _normalize_lower(row.get("amazon_risk_level", ""))
    compression_risk = _normalize_lower(row.get("compression_risk_level", ""))
    if amazon_risk not in {"", "low", "unknown"}:
        detail_parts.append(f"Amazon risk {amazon_risk}")
    if compression_risk not in {"", "low", "unknown"}:
        detail_parts.append(f"compression risk {compression_risk}")
    if _has_share_prior_risk(row):
        detail_parts.append("profit leans on sparse share evidence")
    if _has_ceiling_risk(row):
        detail_parts.append(
            f"ceiling zone {_normalize_text(row.get('sellable_ceiling_zone', '')).replace('_', ' ').lower()}"
        )
    if _has_long_lockup(row):
        detail_parts.append(f"capital lockup about {_int_text(_capital_lockup_days(row))} days")
    if _has_seasonality_signal(row):
        detail_parts.append(_normalize_text(row.get("seasonality_flag", "")).replace("_", " ").lower())
    if not _is_ready(row):
        detail_parts.append("row is not ready")

    detail_text = ". ".join(detail_parts) + "."
    prompts = {
        "certain_fail": "Clear fail check - would you still reject it?",
        "almost_pass": "Near miss check - is the current fail too harsh?",
        "just_passed": "Borderline pass check - is this a rightful pass or too soft?",
        "on_the_line": "Decision-line check - should this be pass, fail, or manual review?",
        "manual_review_or_unclear": "Evidence quality check - is manual review the right outcome?",
        "demand_or_profit_inflation_risk": "Profit inflation check - do you trust this pass story?",
    }
    return f"{prompts.get(primary_bucket, 'Review this row.')} {detail_text}"


def _critical_amazon_recommendation_mismatch_flag(row: pd.Series) -> bool:
    recommendation = _recommendation(row)
    amazon_risk = _normalize_lower(row.get("amazon_risk_level", ""))
    return amazon_risk == "critical" and recommendation in {"normal fit", "managed fit"}


def _select_rows(df: pd.DataFrame, target_count: int) -> tuple[pd.DataFrame, dict[str, int]]:
    if df.empty or target_count <= 0:
        return pd.DataFrame(columns=df.columns), {bucket: 0 for bucket in BUCKET_ORDER}

    masks = _bucket_masks(df)
    availability = {bucket: int(masks[bucket].sum()) for bucket in BUCKET_ORDER}

    quota = max(1, target_count // len(BUCKET_ORDER))
    selected_indexes: list[int] = []
    used_indexes: set[int] = set()
    selected_bucket_by_index: dict[int, str] = {}

    for bucket in BUCKET_ORDER:
        if len(selected_indexes) >= target_count:
            break

        candidate_indexes = [
            int(idx)
            for idx in df.index.tolist()
            if bool(masks[bucket].loc[idx]) and int(idx) not in used_indexes
        ]
        candidate_indexes = sorted(
            candidate_indexes,
            key=lambda idx: _candidate_priority(df.loc[idx], bucket),
        )

        bucket_pick_count = 0
        for idx in candidate_indexes:
            if len(selected_indexes) >= target_count or bucket_pick_count >= quota:
                break
            selected_indexes.append(idx)
            used_indexes.add(idx)
            selected_bucket_by_index[idx] = bucket
            bucket_pick_count += 1

    if len(selected_indexes) < target_count:
        remaining_indexes = [int(idx) for idx in df.index.tolist() if int(idx) not in used_indexes]
        remaining_indexes = sorted(
            remaining_indexes,
            key=lambda idx: (
                -sum(int(bool(mask.loc[idx])) for mask in masks.values()),
                0 if (_is_amazon_learning_case(df.loc[idx]) or _is_compression_learning_case(df.loc[idx])) else 1,
                *_row_sort_key(df.loc[idx]),
            ),
        )
        for idx in remaining_indexes:
            selected_indexes.append(idx)
            selected_bucket_by_index[idx] = _primary_bucket(idx, masks, df)
            if len(selected_indexes) >= target_count:
                break

    _ensure_learning_case_coverage(
        selected_indexes=selected_indexes,
        selected_bucket_by_index=selected_bucket_by_index,
        used_indexes=used_indexes,
        masks=masks,
        df=df,
        learning_check=_is_amazon_learning_case,
    )
    _ensure_learning_case_coverage(
        selected_indexes=selected_indexes,
        selected_bucket_by_index=selected_bucket_by_index,
        used_indexes=used_indexes,
        masks=masks,
        df=df,
        learning_check=_is_compression_learning_case,
    )

    selected = df.loc[selected_indexes].copy()
    if selected.empty:
        return selected, availability

    selected["__source_index"] = selected.index.map(int)
    selected = selected.sort_values(
        by=["asin", "seller_sku"],
        key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
    ).reset_index(drop=True)
    selected["calibration_rank"] = [str(i + 1) for i in range(len(selected))]

    row_to_primary: list[str] = []
    row_to_tags: list[str] = []
    row_to_prompts: list[str] = []
    row_to_mismatch: list[str] = []
    row_to_review_flag: list[str] = []
    row_to_review_reason: list[str] = []
    for _, row in selected.iterrows():
        idx = int(row.get("__source_index", -1))
        source_row = df.loc[idx] if idx >= 0 else row
        primary_bucket = selected_bucket_by_index.get(idx, _primary_bucket(idx, masks, df))
        mismatch = _critical_amazon_recommendation_mismatch_flag(source_row)

        row_to_primary.append(primary_bucket)
        row_to_tags.append(_bucket_tags(source_row, primary_bucket))
        row_to_prompts.append(_review_prompt(source_row, primary_bucket))
        row_to_mismatch.append("1" if mismatch else "0")
        row_to_review_flag.append("1" if mismatch else "0")
        row_to_review_reason.append("critical_amazon_recommendation_mismatch" if mismatch else "")

    selected["calibration_bucket"] = row_to_primary
    selected["bucket_tags"] = row_to_tags
    selected["review_prompt"] = row_to_prompts
    selected["critical_amazon_recommendation_mismatch_flag"] = row_to_mismatch
    selected["calibration_review_flag"] = row_to_review_flag
    selected["calibration_review_reason"] = row_to_review_reason
    selected = selected.drop(columns=["__source_index"], errors="ignore")

    ordered_cols = [
        "calibration_rank",
        "calibration_bucket",
        "bucket_tags",
        "review_prompt",
        "calibration_review_flag",
        "calibration_review_reason",
        "critical_amazon_recommendation_mismatch_flag",
        "seller_sku",
        "asin",
        "summary_status",
        "recommendation",
        "history_confidence",
        "market_viability_score",
        "exit_risk_score",
        "estimated_monthly_profit_gbp",
        "estimated_total_profit_gbp",
        "capital_lockup_days",
        "failure_event_count",
        "longest_failure_streak_days",
        "sellable_ceiling_zone",
        "amazon_risk_level",
        "compression_risk_level",
        "share_assumption_basis",
        "seasonality_flag",
        "manual_review_reason",
        "summary_reason_codes",
    ]
    for col in ordered_cols:
        if col not in selected.columns:
            selected[col] = ""
    return selected[ordered_cols], availability


def _build_blockers(
    summary_df: pd.DataFrame,
    input_df: pd.DataFrame,
    availability: dict[str, int],
) -> list[str]:
    blockers: list[str] = []
    if summary_df.empty:
        blockers.append("summary_missing_or_empty")
        return blockers

    ready_rows = int((summary_df["summary_status"].map(_normalize_lower) == "ready").sum())
    if ready_rows <= 0:
        blockers.append("no_ready_summary_rows")

    for bucket in BUCKET_ORDER:
        if availability.get(bucket, 0) <= 0:
            blockers.append(f"missing_bucket_{bucket}")

    if not input_df.empty and "mapping_status" in input_df.columns:
        no_match_rows = int(
            input_df["mapping_status"].map(_normalize_lower).isin({"no_product_db_match"}).sum()
        )
        if no_match_rows > 0:
            blockers.append("input_contains_no_product_db_match_rows")
    return blockers


def _selected_bucket_counts(selected_df: pd.DataFrame) -> dict[str, int]:
    counts = {bucket: 0 for bucket in BUCKET_ORDER}
    if selected_df.empty or "calibration_bucket" not in selected_df.columns:
        return counts
    selected_counts = selected_df["calibration_bucket"].map(_normalize_lower).value_counts().to_dict()
    for bucket in BUCKET_ORDER:
        counts[bucket] = int(selected_counts.get(bucket, 0))
    return counts


def _selected_learning_case_counts(selected_df: pd.DataFrame) -> dict[str, int]:
    amazon_learning = 0
    compression_learning = 0
    inflation_risk = 0
    for _, row in selected_df.iterrows():
        if _is_amazon_learning_case(row):
            amazon_learning += 1
        if _is_compression_learning_case(row):
            compression_learning += 1
        if _has_profit_inflation_risk(row):
            inflation_risk += 1
    return {
        "amazon_risk_learning_cases": amazon_learning,
        "compression_risk_learning_cases": compression_learning,
        "demand_or_profit_inflation_cases": inflation_risk,
    }


def _write_markdown_summary(
    *,
    observed_utc: str,
    target_count: int,
    selected_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    availability: dict[str, int],
    blockers: list[str],
    markdown_path: Path,
) -> None:
    summary_rows = int(len(summary_df))
    ready_rows = int((summary_df["summary_status"].map(_normalize_lower) == "ready").sum()) if summary_rows else 0
    manual_review_rows = (
        int((summary_df["recommendation"].map(_normalize_lower) == "manual review").sum()) if summary_rows else 0
    )
    selected_counts = _selected_bucket_counts(selected_df)
    learning_case_counts = _selected_learning_case_counts(selected_df)

    lines: list[str] = []
    lines.append("# F Backtest Calibration Set")
    lines.append("")
    lines.append(f"- observed_utc: `{observed_utc}`")
    lines.append(f"- target_count: `{target_count}`")
    lines.append(f"- selected_count: `{len(selected_df)}`")
    lines.append(f"- summary_rows: `{summary_rows}`")
    lines.append(f"- ready_rows: `{ready_rows}`")
    lines.append(f"- manual_review_rows: `{manual_review_rows}`")
    lines.append("")
    lines.append("## Scenario availability")
    lines.append("")
    for bucket in BUCKET_ORDER:
        lines.append(f"- {bucket}: `{availability.get(bucket, 0)}`")
    lines.append("")
    lines.append("## Selected pack coverage")
    lines.append("")
    for bucket in BUCKET_ORDER:
        lines.append(f"- {bucket}: `{selected_counts.get(bucket, 0)}`")
    lines.append("")
    lines.append("## Learning-case coverage")
    lines.append("")
    for label, value in learning_case_counts.items():
        lines.append(f"- {label}: `{value}`")
    lines.append("")
    lines.append("## Blockers")
    lines.append("")
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Root-cause note")
    lines.append("")
    if "no_ready_summary_rows" in blockers:
        lines.append(
            "- Calibration cannot balance pass and fail review scenarios until upstream mapping produces ready rows."
        )
    else:
        lines.append(
            "- Calibration pack now groups rows into plain-English review scenarios so user feedback can focus on repeatable judgment patterns."
        )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def build_backtest_calibration_set(
    *,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    input_path: Path = DEFAULT_INPUT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    target_count: int = DEFAULT_TARGET_COUNT,
    observed_utc: str | None = None,
) -> CalibrationBuildResult:
    if target_count <= 0:
        raise ValueError("target_count must be > 0")
    if target_count > 50:
        raise ValueError("target_count must be <= 50")

    snapshot_utc = observed_utc or _utc_now_iso()
    summary_df = _ensure_summary_columns(_read_csv(summary_path))
    input_df = _read_csv(input_path)

    selected_df, availability = _select_rows(summary_df, target_count=target_count)
    blockers = _build_blockers(summary_df, input_df, availability)

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)
    report_path = output_dir / f"f_backtest_calibration_set_{ts_slug}.csv"
    latest_path = output_dir / "f_backtest_calibration_set_latest.csv"
    markdown_path = output_dir / "f_backtest_calibration_set_latest.md"

    selected_df.to_csv(report_path, index=False)
    selected_df.to_csv(latest_path, index=False)
    _write_markdown_summary(
        observed_utc=snapshot_utc,
        target_count=target_count,
        selected_df=selected_df,
        summary_df=summary_df,
        availability=availability,
        blockers=blockers,
        markdown_path=markdown_path,
    )

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "target_count": target_count,
                "selected_count": int(len(selected_df)),
                "selected_bucket_counts": _selected_bucket_counts(selected_df),
                "blockers": blockers,
                "csv_output": str(report_path),
                "latest_csv": str(latest_path),
                "latest_md": str(markdown_path),
            }
        )
    )
    return CalibrationBuildResult(
        selected_df=selected_df,
        report_path=report_path,
        latest_path=latest_path,
        markdown_path=markdown_path,
        blockers=tuple(blockers),
        bucket_availability=availability,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a one-off F backtest calibration selection set.")
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--input-path", default=str(DEFAULT_INPUT_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--target-count", type=int, default=DEFAULT_TARGET_COUNT)
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_backtest_calibration_set(
        summary_path=Path(args.summary_path),
        input_path=Path(args.input_path),
        output_dir=Path(args.output_dir),
        target_count=int(args.target_count),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
