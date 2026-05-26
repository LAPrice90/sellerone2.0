from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.core.storage import read_review_pack_dataframe


DEFAULT_NEAR_MISS_PATH = ROOT / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "f_history_borderline_near_miss_audit_latest.csv"
DEFAULT_SUMMARY_PATH = ROOT / "out" / "analysis_reports" / "f_history_borderline_near_miss_summary_latest.md"

OUTPUT_COLUMNS = [
    "supplier_sku",
    "asin",
    "candidate_id",
    "title",
    "near_miss_type",
    "reviewability_state",
    "screening_fail_code",
    "history_risk_code",
    "history_recommended_action",
    "history_borderline_code",
    "suggested_action",
    "borderline_reason",
    "phase_profit_pct",
    "phase_low_roi_pct",
    "phase_break_even_pct",
    "phase_loss_pct",
    "weak_days_pct",
    "phase_profit_pct_180d",
    "phase_loss_pct_180d",
    "phase_weak_pct_180d",
    "phase_profit_pct_90d",
    "phase_loss_pct_90d",
    "phase_weak_pct_90d",
    "phase_profit_pct_30d",
    "phase_loss_pct_30d",
    "phase_weak_pct_30d",
    "amazon_price_days",
    "amazon_below_be_pct_365d",
    "amazon_below_be_pct_180d",
    "amazon_below_be_pct_90d",
    "amazon_good_above_be20_pct_90d",
    "amazon_pressure_signal",
    "avg_30_day_price",
    "break_even",
    "avg_price_vs_break_even_pct",
    "phase_longest_profit_days",
    "phase_longest_loss_days",
    "pricing_history_score",
    "ranking_history_score",
    "history_operational_score",
    "history_recommendation",
    "phase_recommendation",
    "exit_strategy",
    "expected_units_next_30d",
    "expected_profit_next_30d_gbp",
    "profit_per_unit_30d_gbp",
    "main_rank",
    "evidence_source",
]

VALID_BORDERLINE_CODES = {
    "history_recent_recovery_pass_candidate",
    "history_amazon_below_be_fail_supported",
    "history_recent_weakness_fail_supported",
    "history_pass_candidate_after_user_calibration",
    "strong_borderline_history_review_candidate",
    "borderline_but_limited_upside",
    "possible_borderline_history_review_candidate",
    "history_fail_supported",
    "history_metrics_missing",
}


@dataclass(frozen=True)
class HistoryBorderlineNearMissAuditResult:
    audit_df: pd.DataFrame
    output_path: Path
    summary_path: Path
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_near_miss_review_pack(path: Path) -> pd.DataFrame:
    return read_review_pack_dataframe(path, pack_type="near_misses", dtype=str).fillna("")


def _parse_float(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
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


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return (float(numerator) / float(denominator)) * 100.0


def _parse_phase_series(value: object) -> list[tuple[date, str]]:
    records: list[tuple[date, str]] = []
    for part in _normalize_text(value).split(";"):
        if "=" not in part:
            continue
        raw_day, raw_phase = part.split("=", 1)
        parsed = pd.to_datetime(raw_day, errors="coerce")
        if pd.isna(parsed):
            continue
        phase = _normalize_text(raw_phase).lower()
        if phase == "":
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
        price = _parse_float(raw_price)
        if pd.isna(parsed) or price is None or price <= 0:
            continue
        records.append((parsed.date(), price))
    return records


def _phase_window_metrics(records: list[tuple[date, str]], *, anchor: date | None, days: int) -> dict[str, float | int | None]:
    if anchor is None:
        return {
            "days": 0,
            "profit_pct": None,
            "loss_pct": None,
            "low_roi_pct": None,
            "break_even_pct": None,
            "weak_pct": None,
        }
    start = anchor - timedelta(days=days - 1)
    values = [phase for observed_day, phase in records if observed_day >= start]
    total = len(values)
    loss = sum(1 for phase in values if phase == "loss")
    low_roi = sum(1 for phase in values if phase == "low_roi")
    break_even = sum(1 for phase in values if phase == "break_even")
    weak = loss + low_roi + break_even
    profit = sum(1 for phase in values if phase == "profit")
    return {
        "days": total,
        "profit_pct": _pct(profit, total),
        "loss_pct": _pct(loss, total),
        "low_roi_pct": _pct(low_roi, total),
        "break_even_pct": _pct(break_even, total),
        "weak_pct": _pct(weak, total),
    }


def _amazon_window_metrics(
    records: list[tuple[date, float]],
    *,
    break_even: float | None,
    anchor: date | None,
    days: int,
) -> dict[str, float | int | None]:
    if break_even is None or break_even <= 0 or anchor is None:
        return {
            "days": 0,
            "below_be_pct": None,
            "near_be_pct": None,
            "good_above_be20_pct": None,
        }
    start = anchor - timedelta(days=days - 1)
    values = [price for observed_day, price in records if observed_day >= start]
    total = len(values)
    below = sum(1 for price in values if price < break_even)
    near = sum(1 for price in values if break_even <= price < break_even * 1.2)
    good = sum(1 for price in values if price >= break_even * 1.2)
    return {
        "days": total,
        "below_be_pct": _pct(below, total),
        "near_be_pct": _pct(near, total),
        "good_above_be20_pct": _pct(good, total),
    }


def _history_rule_metrics(scrape: dict[str, str]) -> dict[str, float | int | str | None]:
    phase_records = _parse_phase_series(scrape.get("chart_phase_daily_series", ""))
    amazon_records = _parse_price_series(scrape.get("chart_raw_amazon_daily_series", ""))
    phase_anchor = max((observed_day for observed_day, _ in phase_records), default=None)
    amazon_anchor = max(
        [observed_day for observed_day, _ in phase_records] + [observed_day for observed_day, _ in amazon_records],
        default=None,
    )
    break_even = _parse_float(scrape.get("break_even", ""))

    metrics: dict[str, float | int | str | None] = {
        "phase_records": len(phase_records),
        "amazon_price_days": len(amazon_records),
    }
    for days in (180, 90, 30):
        window = _phase_window_metrics(phase_records, anchor=phase_anchor, days=days)
        metrics[f"phase_profit_pct_{days}d"] = window["profit_pct"]
        metrics[f"phase_loss_pct_{days}d"] = window["loss_pct"]
        metrics[f"phase_low_roi_pct_{days}d"] = window["low_roi_pct"]
        metrics[f"phase_break_even_pct_{days}d"] = window["break_even_pct"]
        metrics[f"phase_weak_pct_{days}d"] = window["weak_pct"]
        metrics[f"phase_days_{days}d"] = window["days"]

    for days in (365, 180, 90, 30):
        window = _amazon_window_metrics(amazon_records, break_even=break_even, anchor=amazon_anchor, days=days)
        metrics[f"amazon_days_{days}d"] = window["days"]
        metrics[f"amazon_below_be_pct_{days}d"] = window["below_be_pct"]
        metrics[f"amazon_near_be_pct_{days}d"] = window["near_be_pct"]
        metrics[f"amazon_good_above_be20_pct_{days}d"] = window["good_above_be20_pct"]

    metrics["amazon_pressure_signal"] = _amazon_pressure_signal(metrics)
    return metrics


def _metric_float(metrics: dict[str, float | int | str | None], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, str):
        return _parse_float(value)
    if value is None:
        return None
    return float(value)


def _metric_int(metrics: dict[str, float | int | str | None], key: str) -> int:
    value = metrics.get(key)
    if value is None or isinstance(value, str):
        return 0
    return int(value)


def _amazon_hard_fail(metrics: dict[str, float | int | str | None]) -> bool:
    amazon_days_365 = _metric_int(metrics, "amazon_days_365d")
    amazon_days_180 = _metric_int(metrics, "amazon_days_180d")
    amazon_days_90 = _metric_int(metrics, "amazon_days_90d")
    below_365 = _metric_float(metrics, "amazon_below_be_pct_365d")
    below_180 = _metric_float(metrics, "amazon_below_be_pct_180d")
    below_90 = _metric_float(metrics, "amazon_below_be_pct_90d")

    if amazon_days_365 < 30 or below_365 is None:
        return False
    if below_365 >= 15 and amazon_days_180 >= 20:
        return True
    if below_365 >= 15 and below_180 is not None and amazon_days_180 >= 20 and below_180 >= 10:
        return True
    if below_365 >= 15 and below_90 is not None and amazon_days_90 >= 5 and below_90 >= 50:
        return True
    return False


def _amazon_pressure_signal(metrics: dict[str, float | int | str | None]) -> str:
    amazon_days_365 = _metric_int(metrics, "amazon_days_365d")
    amazon_days_90 = _metric_int(metrics, "amazon_days_90d")
    below_365 = _metric_float(metrics, "amazon_below_be_pct_365d")
    below_90 = _metric_float(metrics, "amazon_below_be_pct_90d")
    good_90 = _metric_float(metrics, "amazon_good_above_be20_pct_90d")

    if _amazon_hard_fail(metrics):
        return "amazon_below_break_even_hard_fail"
    if amazon_days_365 < 30:
        return "amazon_sparse_or_absent"
    if amazon_days_90 >= 20 and below_90 == 0 and good_90 is not None and good_90 >= 75 and (below_365 or 0) < 15:
        return "amazon_recent_above_break_even_recovered"
    return "amazon_watch"


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


def _lookup_scrape(
    *,
    row: dict[str, str],
    by_candidate: dict[tuple[str, ...], dict[str, str]],
    by_supplier_asin: dict[tuple[str, ...], dict[str, str]],
    by_asin: dict[tuple[str, ...], dict[str, str]],
) -> dict[str, str]:
    candidate_key = (_normalize_key(row.get("candidate_id", "")),)
    supplier_asin_key = (_normalize_key(row.get("supplier_sku", "")), _normalize_key(row.get("asin", "")))
    asin_key = (_normalize_key(row.get("asin", "")),)
    if candidate_key in by_candidate:
        return by_candidate[candidate_key]
    if supplier_asin_key in by_supplier_asin:
        return by_supplier_asin[supplier_asin_key]
    if asin_key in by_asin:
        return by_asin[asin_key]
    return {}


def _classify_borderline_history(
    row: dict[str, str],
    scrape: dict[str, str],
    metrics: dict[str, float | int | str | None],
) -> tuple[str, str, str]:
    profit_pct = _parse_float(scrape.get("phase_profit_pct", ""))
    loss_pct = _parse_float(scrape.get("phase_loss_pct", ""))
    low_roi_pct = _parse_float(scrape.get("phase_low_roi_pct", ""))
    break_even_pct = _parse_float(scrape.get("phase_break_even_pct", ""))
    longest_loss = _parse_float(scrape.get("phase_longest_loss_days", ""))
    pricing_score = _parse_float(scrape.get("pricing_history_score", ""))
    operational_score = _parse_float(scrape.get("history_operational_score", ""))
    upside_pct = _avg_price_vs_break_even_pct(scrape)
    profit_per_unit = _parse_float(row.get("profit_per_unit_30d_gbp", ""))

    required = [profit_pct, low_roi_pct, break_even_pct, loss_pct, longest_loss, pricing_score, operational_score]
    if any(value is None for value in required):
        return "history_metrics_missing", "targeted_rescan_needed", "history metrics missing from scrape evidence"

    weak_days_pct = low_roi_pct + loss_pct + break_even_pct
    phase_records = _metric_int(metrics, "phase_records")
    if phase_records <= 0:
        return _classify_full_year_fallback(
            profit_pct=profit_pct,
            loss_pct=loss_pct,
            low_roi_pct=low_roi_pct,
            break_even_pct=break_even_pct,
            longest_loss=longest_loss,
            pricing_score=pricing_score,
            operational_score=operational_score,
            upside_pct=upside_pct,
            profit_per_unit=profit_per_unit,
        )

    if _amazon_hard_fail(metrics):
        return (
            "history_amazon_below_be_fail_supported",
            "keep_remove_from_clean_pass",
            "Amazon has meaningful history below our break-even, so recent seller recovery is not enough",
        )

    phase_30_loss = _metric_float(metrics, "phase_loss_pct_30d")
    phase_30_low_roi = _metric_float(metrics, "phase_low_roi_pct_30d")
    if (
        upside_pct is not None
        and upside_pct < 30
        and phase_30_loss is not None
        and phase_30_loss == 0
        and phase_30_low_roi is not None
        and phase_30_low_roi >= 25
    ):
        return (
            "borderline_but_limited_upside",
            "keep_remove_from_clean_pass",
            "recent history is not losing money, but it is spending too much time just above break-even",
        )

    if _recent_recovery_pass(metrics, upside_pct=upside_pct, profit_per_unit=profit_per_unit):
        return (
            "history_recent_recovery_pass_candidate",
            "manual_review_candidate",
            "recent 30/90/180 day evidence has recovered enough that old bad history should not hard-fail it",
        )

    if (
        profit_pct >= 75
        and weak_days_pct <= 20
        and profit_per_unit is not None
        and profit_per_unit >= 4
        and upside_pct is not None
        and upside_pct >= 40
    ):
        return (
            "history_pass_candidate_after_user_calibration",
            "manual_review_candidate",
            "strong full-year profitable history with limited weak days and enough upside above break-even",
        )

    if _recent_weakness_fail(metrics):
        return (
            "history_recent_weakness_fail_supported",
            "keep_remove_from_clean_pass",
            "recent 30/90 day history is still weak, so old recovery is not proven enough",
        )

    return _classify_full_year_fallback(
        profit_pct=profit_pct,
        loss_pct=loss_pct,
        low_roi_pct=low_roi_pct,
        break_even_pct=break_even_pct,
        longest_loss=longest_loss,
        pricing_score=pricing_score,
        operational_score=operational_score,
        upside_pct=upside_pct,
        profit_per_unit=profit_per_unit,
    )


def _recent_recovery_pass(
    metrics: dict[str, float | int | str | None],
    *,
    upside_pct: float | None,
    profit_per_unit: float | None,
) -> bool:
    if profit_per_unit is None or profit_per_unit < 3:
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
    amazon_below_365 = _metric_float(metrics, "amazon_below_be_pct_365d") or 0
    amazon_good_90 = _metric_float(metrics, "amazon_good_above_be20_pct_90d")

    recent_phase_clean = (
        phase_90_profit is not None
        and phase_90_profit >= 95
        and phase_90_loss == 0
        and phase_90_weak is not None
        and phase_90_weak <= 5
        and phase_30_profit is not None
        and phase_30_profit >= 95
        and phase_30_loss == 0
    )
    if recent_phase_clean:
        return True

    sparse_amazon_recent_recovery = (
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
    )
    if sparse_amazon_recent_recovery:
        return True

    amazon_recovered_support = (
        amazon_days_90 >= 20
        and amazon_below_90 == 0
        and amazon_good_90 is not None
        and amazon_good_90 >= 75
        and amazon_below_365 < 15
        and upside_pct is not None
        and upside_pct >= 30
    )
    return amazon_recovered_support


def _recent_weakness_fail(metrics: dict[str, float | int | str | None]) -> bool:
    phase_30_weak = _metric_float(metrics, "phase_weak_pct_30d")
    phase_90_weak = _metric_float(metrics, "phase_weak_pct_90d")
    phase_90_profit = _metric_float(metrics, "phase_profit_pct_90d")
    phase_90_loss = _metric_float(metrics, "phase_loss_pct_90d")
    phase_180_weak = _metric_float(metrics, "phase_weak_pct_180d")
    if phase_90_loss is not None and phase_90_loss >= 10:
        return True
    if phase_90_weak is not None and phase_90_weak >= 25:
        return True
    if (
        phase_180_weak is not None
        and phase_180_weak >= 30
        and phase_90_profit is not None
        and phase_90_profit < 90
    ):
        return True
    if phase_30_weak is not None and phase_30_weak >= 30:
        return True
    return False


def _classify_full_year_fallback(
    *,
    profit_pct: float,
    loss_pct: float,
    low_roi_pct: float,
    break_even_pct: float,
    longest_loss: float,
    pricing_score: float,
    operational_score: float,
    upside_pct: float | None,
    profit_per_unit: float | None,
) -> tuple[str, str, str]:
    weak_days_pct = low_roi_pct + loss_pct + break_even_pct
    if (
        profit_pct >= 75
        and weak_days_pct <= 20
        and profit_per_unit is not None
        and profit_per_unit >= 4
        and upside_pct is not None
        and upside_pct >= 40
    ):
        return (
            "history_pass_candidate_after_user_calibration",
            "manual_review_candidate",
            "strong full-year profitable history with limited weak days and enough upside above break-even",
        )

    strong_shape = (
        profit_pct >= 60
        and loss_pct <= 10
        and longest_loss <= 14
        and pricing_score >= 65
        and operational_score >= 60
    )
    if strong_shape and upside_pct is not None and upside_pct >= 40:
        return (
            "strong_borderline_history_review_candidate",
            "manual_review_candidate",
            "strong profit history with low loss exposure, short loss streak, and real upside above break-even",
        )

    if strong_shape:
        return (
            "borderline_but_limited_upside",
            "keep_remove_from_clean_pass",
            "history shape is good, but upside above break-even is not strong enough",
        )

    if profit_pct >= 50 and loss_pct <= 25 and pricing_score >= 55 and operational_score >= 55:
        return (
            "possible_borderline_history_review_candidate",
            "inspect_before_rule_change",
            "majority profitable history, but loss or low-ROI exposure still needs inspection",
        )

    return (
        "history_fail_supported",
        "keep_remove_from_clean_pass",
        "history failure supported by loss exposure or weak history scores",
    )


def _avg_price_vs_break_even_pct(scrape: dict[str, str]) -> float | None:
    avg_price = _parse_float(scrape.get("avg_30_day_price", ""))
    break_even = _parse_float(scrape.get("break_even", ""))
    if avg_price is None or break_even is None or break_even <= 0:
        return None
    return ((avg_price - break_even) / break_even) * 100.0


def _build_summary_markdown(report: dict[str, Any], audit_df: pd.DataFrame) -> str:
    counts = report.get("history_borderline_code_counts", {})
    action_counts = report.get("suggested_action_counts", {})
    lines = [
        "# History Borderline Near Miss Audit",
        "",
        f"- Input near-miss rows: `{report.get('input_near_miss_rows', 0)}`",
        f"- History conflict rows audited: `{report.get('history_conflict_rows', 0)}`",
        f"- Unclassified rows: `{report.get('unclassified_rows', 0)}`",
        "",
        "## Counts by Borderline Code",
    ]
    for key, value in counts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Counts by Suggested Action"])
    for key, value in action_counts.items():
        lines.append(f"- `{key}`: `{value}`")

    sample = audit_df.loc[
        audit_df["history_borderline_code"].isin(
            [
                "history_recent_recovery_pass_candidate",
                "history_amazon_below_be_fail_supported",
                "history_recent_weakness_fail_supported",
                "strong_borderline_history_review_candidate",
                "history_pass_candidate_after_user_calibration",
                "borderline_but_limited_upside",
                "possible_borderline_history_review_candidate",
            ]
        )
    ].head(20)
    lines.extend(["", "## Borderline Sample"])
    if sample.empty:
        lines.append("- No borderline candidates found.")
    else:
        for _, row in sample.iterrows():
            lines.append(
                "- "
                f"`{row['supplier_sku']}` / `{row['asin']}` - "
                f"{row['history_borderline_code']} - "
                f"90d_profit={row['phase_profit_pct_90d']}%, "
                f"90d_weak={row['phase_weak_pct_90d']}%, "
                f"amazon_below_365d={row['amazon_below_be_pct_365d']}%, "
                f"upside={row['avg_price_vs_break_even_pct']}%, "
                f"longest_loss={row['phase_longest_loss_days']}, "
                f"amazon_signal={row['amazon_pressure_signal']}"
            )
    lines.append("")
    return "\n".join(lines)


def build_history_borderline_near_miss_audit(
    *,
    near_miss_path: Path = DEFAULT_NEAR_MISS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
) -> HistoryBorderlineNearMissAuditResult:
    near_df = _read_near_miss_review_pack(near_miss_path)
    scrape_df = _read_csv(scrape_evidence_path)

    by_candidate = _latest_records(scrape_df, key_columns=["candidate_id"], utc_columns=["observed_utc", "scan_day"])
    by_supplier_asin = _latest_records(
        scrape_df,
        key_columns=["supplier_sku", "asin"],
        utc_columns=["observed_utc", "scan_day"],
    )
    by_asin = _latest_records(scrape_df, key_columns=["asin"], utc_columns=["observed_utc", "scan_day"])

    rows: list[dict[str, str]] = []
    if not near_df.empty:
        for _, source in near_df.iterrows():
            source_row = {column: _normalize_text(value) for column, value in source.to_dict().items()}
            if _normalize_text(source_row.get("near_miss_type", "")) != "history_risk_conflict":
                continue
            scrape_row = _lookup_scrape(
                row=source_row,
                by_candidate=by_candidate,
                by_supplier_asin=by_supplier_asin,
                by_asin=by_asin,
            )
            metrics = _history_rule_metrics(scrape_row)
            borderline_code, suggested_action, reason = _classify_borderline_history(source_row, scrape_row, metrics)
            avg_price = _parse_float(scrape_row.get("avg_30_day_price", ""))
            break_even = _parse_float(scrape_row.get("break_even", ""))
            upside_pct = _avg_price_vs_break_even_pct(scrape_row)
            phase_low_roi_pct = _parse_float(scrape_row.get("phase_low_roi_pct", ""))
            phase_break_even_pct = _parse_float(scrape_row.get("phase_break_even_pct", ""))
            phase_loss_pct = _parse_float(scrape_row.get("phase_loss_pct", ""))
            rows.append(
                {
                    "supplier_sku": source_row.get("supplier_sku", ""),
                    "asin": source_row.get("asin", ""),
                    "candidate_id": source_row.get("candidate_id", ""),
                    "title": source_row.get("title", ""),
                    "near_miss_type": source_row.get("near_miss_type", ""),
                    "reviewability_state": source_row.get("reviewability_state", ""),
                    "screening_fail_code": source_row.get("screening_fail_code", ""),
                    "history_risk_code": source_row.get("history_risk_code", ""),
                    "history_recommended_action": source_row.get("history_recommended_action", ""),
                    "history_borderline_code": borderline_code,
                    "suggested_action": suggested_action,
                    "borderline_reason": reason,
                    "phase_profit_pct": _num_to_text(_parse_float(scrape_row.get("phase_profit_pct", ""))),
                    "phase_low_roi_pct": _num_to_text(phase_low_roi_pct),
                    "phase_break_even_pct": _num_to_text(phase_break_even_pct),
                    "phase_loss_pct": _num_to_text(phase_loss_pct),
                    "weak_days_pct": _num_to_text(
                        (phase_low_roi_pct or 0)
                        + (phase_break_even_pct or 0)
                        + (phase_loss_pct or 0)
                    ),
                    "phase_profit_pct_180d": _num_to_text(_metric_float(metrics, "phase_profit_pct_180d")),
                    "phase_loss_pct_180d": _num_to_text(_metric_float(metrics, "phase_loss_pct_180d")),
                    "phase_weak_pct_180d": _num_to_text(_metric_float(metrics, "phase_weak_pct_180d")),
                    "phase_profit_pct_90d": _num_to_text(_metric_float(metrics, "phase_profit_pct_90d")),
                    "phase_loss_pct_90d": _num_to_text(_metric_float(metrics, "phase_loss_pct_90d")),
                    "phase_weak_pct_90d": _num_to_text(_metric_float(metrics, "phase_weak_pct_90d")),
                    "phase_profit_pct_30d": _num_to_text(_metric_float(metrics, "phase_profit_pct_30d")),
                    "phase_loss_pct_30d": _num_to_text(_metric_float(metrics, "phase_loss_pct_30d")),
                    "phase_weak_pct_30d": _num_to_text(_metric_float(metrics, "phase_weak_pct_30d")),
                    "amazon_price_days": _num_to_text(_metric_float(metrics, "amazon_price_days")),
                    "amazon_below_be_pct_365d": _num_to_text(_metric_float(metrics, "amazon_below_be_pct_365d")),
                    "amazon_below_be_pct_180d": _num_to_text(_metric_float(metrics, "amazon_below_be_pct_180d")),
                    "amazon_below_be_pct_90d": _num_to_text(_metric_float(metrics, "amazon_below_be_pct_90d")),
                    "amazon_good_above_be20_pct_90d": _num_to_text(
                        _metric_float(metrics, "amazon_good_above_be20_pct_90d")
                    ),
                    "amazon_pressure_signal": _normalize_text(metrics.get("amazon_pressure_signal", "")),
                    "avg_30_day_price": _num_to_text(avg_price),
                    "break_even": _num_to_text(break_even),
                    "avg_price_vs_break_even_pct": _num_to_text(upside_pct),
                    "phase_longest_profit_days": _num_to_text(_parse_float(scrape_row.get("phase_longest_profit_days", ""))),
                    "phase_longest_loss_days": _num_to_text(_parse_float(scrape_row.get("phase_longest_loss_days", ""))),
                    "pricing_history_score": _num_to_text(_parse_float(scrape_row.get("pricing_history_score", ""))),
                    "ranking_history_score": _num_to_text(_parse_float(scrape_row.get("ranking_history_score", ""))),
                    "history_operational_score": _num_to_text(_parse_float(scrape_row.get("history_operational_score", ""))),
                    "history_recommendation": _normalize_text(scrape_row.get("history_recommendation", "")),
                    "phase_recommendation": _normalize_text(scrape_row.get("phase_recommendation", "")),
                    "exit_strategy": _normalize_text(scrape_row.get("exit_strategy", "")),
                    "expected_units_next_30d": source_row.get("expected_units_next_30d", ""),
                    "expected_profit_next_30d_gbp": source_row.get("expected_profit_next_30d_gbp", ""),
                    "profit_per_unit_30d_gbp": source_row.get("profit_per_unit_30d_gbp", ""),
                    "main_rank": source_row.get("main_rank", ""),
                    "evidence_source": (
                        "f_live_price_file_near_miss_review_latest.csv|feeder_legacy_scrape_evidence_live.csv"
                        if scrape_row
                        else "f_live_price_file_near_miss_review_latest.csv|scrape_evidence_missing"
                    ),
                }
            )

    audit_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    unclassified_rows = int(
        audit_df["history_borderline_code"].map(lambda value: value not in VALID_BORDERLINE_CODES).sum()
    ) if not audit_df.empty else 0
    code_counts = audit_df["history_borderline_code"].value_counts().sort_index().to_dict() if not audit_df.empty else {}
    action_counts = audit_df["suggested_action"].value_counts().sort_index().to_dict() if not audit_df.empty else {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(output_path, index=False)

    report = {
        "near_miss_path": str(near_miss_path),
        "scrape_evidence_path": str(scrape_evidence_path),
        "output_path": str(output_path),
        "summary_path": str(summary_path),
        "input_near_miss_rows": int(len(near_df.index)),
        "history_conflict_rows": int(len(audit_df.index)),
        "unclassified_rows": unclassified_rows,
        "history_borderline_code_counts": {key: int(value) for key, value in code_counts.items()},
        "suggested_action_counts": {key: int(value) for key, value in action_counts.items()},
    }

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(_build_summary_markdown(report, audit_df), encoding="utf-8")

    return HistoryBorderlineNearMissAuditResult(
        audit_df=audit_df,
        output_path=output_path,
        summary_path=summary_path,
        report=report,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only audit for borderline history near misses.")
    parser.add_argument("--near-miss-path", type=Path, default=DEFAULT_NEAR_MISS_PATH)
    parser.add_argument("--scrape-evidence-path", type=Path, default=DEFAULT_SCRAPE_EVIDENCE_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_history_borderline_near_miss_audit(
        near_miss_path=args.near_miss_path,
        scrape_evidence_path=args.scrape_evidence_path,
        output_path=args.output_path,
        summary_path=args.summary_path,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
