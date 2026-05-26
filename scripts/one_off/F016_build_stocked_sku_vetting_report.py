from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import ceil, floor
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_CURRENT_PACK_PATH = DEFAULT_OUTPUT_DIR / "f_live_test_readiness_pack_latest.csv"
DEFAULT_ACTUALS_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_actuals_latest.csv"
DEFAULT_FULL_CAPTURE_MANIFEST_DIR = DEFAULT_OUTPUT_DIR
DEFAULT_PROFIT_FLOOR_GBP = 20.0
DEFAULT_LOOKBACK_DAYS = 30


REPORT_COLUMNS = [
    "observed_utc",
    "decision_cutoff_date",
    "asin",
    "seller_sku",
    "current_commercial_decision_state",
    "current_live_test_readiness_state",
    "current_truth_decision_state",
    "current_actual_units_30d",
    "current_actual_profit_30d_gbp",
    "current_sales_lower_30d",
    "current_sales_upper_30d",
    "current_rank_risk_state",
    "current_starter_order_band",
    "current_starter_test_qty_recommended",
    "prior_window_units_30d",
    "prior_window_profit_30d_gbp",
    "prior_window_truth_decision_state",
    "decision_30d_ago_state",
    "decision_30d_ago_live_test_readiness_state",
    "decision_30d_ago_sales_lower_30d",
    "decision_30d_ago_sales_upper_30d",
    "decision_30d_ago_rank_best_observed",
    "decision_30d_ago_rank_worst_observed",
    "decision_30d_ago_rank_stability_band",
    "decision_30d_ago_rank_risk_state",
    "decision_30d_ago_profit_risk_band",
    "decision_30d_ago_negative_mode_state",
    "decision_30d_ago_starter_order_band",
    "decision_30d_ago_starter_test_qty",
    "decision_30d_ago_reason",
    "outcome_next_30d_units",
    "outcome_next_30d_profit_gbp",
    "outcome_next_30d_truth_decision_state",
    "decision_30d_ago_vs_outcome",
]

SUMMARY_COLUMNS = ["observed_utc", "metric", "value"]


@dataclass(frozen=True)
class StockedSkuVettingReportResult:
    report_df: pd.DataFrame
    summary_df: pd.DataFrame
    report_path: Path
    report_latest_path: Path
    summary_path: Path
    summary_latest_path: Path
    markdown_path: Path
    markdown_latest_path: Path


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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = raw.replace(",", "").replace("GBP", "").replace("gbp", "")
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


def _int_or_none(value: object) -> int | None:
    num = _num_or_none(value)
    if num is None:
        return None
    return int(round(num))


def _demand_consistency_band(error_ratio: float | None) -> str:
    if error_ratio is None:
        return "unknown"
    ratio = abs(error_ratio)
    if ratio <= 0.35:
        return "stable"
    if ratio <= 0.8:
        return "variable"
    return "unstable"


def _sales_band(center_units: float | None, consistency_band: str) -> tuple[int | None, int | None]:
    if center_units is None:
        return None, None
    center = max(float(center_units), 0.0)
    factors = {
        "stable": (0.75, 1.25),
        "variable": (0.55, 1.60),
        "unstable": (0.35, 2.10),
        "unknown": (0.45, 1.80),
    }
    lo_mult, hi_mult = factors.get(consistency_band, factors["unknown"])
    lower = int(max(0, floor(center * lo_mult)))
    upper = int(max(lower, ceil(center * hi_mult)))
    if center > 0 and upper == lower:
        upper = lower + 1
    return lower, upper


def _rank_profile(rank_30: float | None, rank_90: float | None) -> tuple[int | None, int | None, str, str]:
    values = [int(v) for v in [rank_30, rank_90] if v is not None and v > 0]
    if not values:
        return None, None, "untrusted_missing_window", "untrusted_rank_window"

    best_rank = min(values)
    worst_rank = max(values)

    if len(values) == 1:
        stability = "single_snapshot"
    else:
        ratio = float(worst_rank) / max(float(best_rank), 1.0)
        if ratio <= 1.5:
            stability = "stable"
        elif ratio <= 3.0:
            stability = "variable"
        else:
            stability = "unstable"

    if worst_rank <= 50000:
        risk = "low_rank_risk"
    elif worst_rank <= 100000:
        risk = "moderate_rank_risk"
    else:
        risk = "high_rank_risk"
    return best_rank, worst_rank, stability, risk


def _profit_risk_band(profit_30d: float | None, model_profit_30d: float | None, floor_profit: float) -> str:
    basis = profit_30d if profit_30d is not None else model_profit_30d
    if basis is None:
        return "unknown"
    if basis <= 0:
        return "negative"
    if basis < floor_profit:
        return "near_floor"
    if basis < floor_profit * 2:
        return "healthy"
    return "strong"


def _negative_mode_truth_state(profit_30d: float | None, floor_profit: float) -> str:
    if profit_30d is None:
        return "unknown"
    if profit_30d <= 0:
        return "negative_mode_active"
    if profit_30d < floor_profit:
        return "negative_mode_risk"
    return "negative_mode_clear"


def _heuristic_qty_from_lower_sales(lower_sales_30d: int | None) -> int:
    if lower_sales_30d is None or lower_sales_30d <= 0:
        return 0
    if lower_sales_30d <= 2:
        return 1
    if lower_sales_30d <= 8:
        return 3
    if lower_sales_30d <= 20:
        return 5
    return 8


def _starter_qty(
    *,
    lower_sales_30d: int | None,
    recommended_qty: int | None,
    recommendation_status: str,
    negative_mode_state: str,
) -> int:
    if recommendation_status == "reject" or negative_mode_state == "negative_mode_active":
        return 0

    heuristic = _heuristic_qty_from_lower_sales(lower_sales_30d)
    if recommended_qty is None:
        return heuristic
    if recommended_qty <= 0:
        return 0
    if heuristic <= 0:
        return recommended_qty
    return min(recommended_qty, heuristic)


def _starter_order_band(starter_qty: int) -> str:
    if starter_qty <= 0:
        return "hold"
    if starter_qty <= 2:
        return "micro_test"
    if starter_qty <= 5:
        return "controlled_test"
    if starter_qty <= 8:
        return "broad_test"
    return "scale_test"


def _commercial_decision(
    *,
    recommendation_status: str,
    demand_consistency_band: str,
    profit_risk_band: str,
    rank_risk_state: str,
    starter_qty: int,
) -> str:
    if profit_risk_band == "negative":
        return "reject"
    if starter_qty <= 0:
        return "reject"
    if recommendation_status == "reject" and profit_risk_band not in {"healthy", "strong"}:
        return "reject"
    if rank_risk_state in {"high_rank_risk", "untrusted_rank_window"}:
        return "watch"
    if demand_consistency_band == "unstable" and profit_risk_band in {"near_floor", "unknown"}:
        return "reject"
    if profit_risk_band in {"healthy", "strong"} and demand_consistency_band in {"stable", "variable"}:
        return "test_buy"
    return "watch"


def _live_test_readiness_state(rank_risk_state: str, commercial_decision_state: str) -> str:
    if rank_risk_state == "untrusted_rank_window":
        return "not_ready_rank_gap"
    if commercial_decision_state == "test_buy":
        return "ready_for_live_test"
    return "not_ready_commercial"


def _truth_decision_state(actual_profit: float | None, floor_profit: float) -> str:
    if actual_profit is None:
        return "unknown"
    return "pass" if actual_profit >= floor_profit else "fail"


def _decision_vs_outcome(decision_state: str, outcome_state: str) -> str:
    if decision_state == "test_buy" and outcome_state == "pass":
        return "good_test"
    if decision_state == "test_buy" and outcome_state == "fail":
        return "bad_test"
    if decision_state in {"watch", "reject"} and outcome_state == "pass":
        return "missed_winner"
    if decision_state in {"watch", "reject"} and outcome_state == "fail":
        return "avoided_loser"
    return "unknown"


def _decision_reason(*, profit_risk: str, negative_mode: str, rank_risk: str, demand_band: str, starter_band: str) -> str:
    return "|".join(
        [
            f"profit_{profit_risk}",
            negative_mode,
            rank_risk,
            f"demand_{demand_band}",
            f"starter_{starter_band}",
        ]
    )


def _sold_actuals_by_asin(actuals_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if actuals_df.empty:
        return {}
    work = actuals_df.copy()
    work["asin"] = work.get("asin", "").map(_normalize_key)
    work["seller_sku"] = work.get("seller_sku", "").map(_normalize_text)
    work["actuals_basis"] = work.get("actuals_basis", "").map(_normalize_text).str.lower()
    work = work[(work["asin"] != "") & (work["actuals_basis"] == "operational_baseline")].copy()
    if work.empty:
        return {}
    if "actuals_observed_utc" in work.columns:
        work["_actuals_ts"] = pd.to_datetime(
            work.get("actuals_observed_utc", "").map(_normalize_text),
            errors="coerce",
            utc=True,
        )
        work = work.sort_values("_actuals_ts", ascending=False, kind="stable")
    work = work.drop_duplicates(subset=["asin"], keep="first")
    return {
        _normalize_key(row.get("asin", "")): {column: _normalize_text(value) for column, value in row.to_dict().items()}
        for _, row in work.iterrows()
    }


def _parse_bsr_series(series_text: str) -> list[tuple[date, float]]:
    raw = _normalize_text(series_text)
    if raw == "":
        return []
    points: list[tuple[date, float]] = []
    for token in raw.split(";"):
        chunk = _normalize_text(token)
        if chunk == "" or "=" not in chunk:
            continue
        day_token, value_token = chunk.split("=", 1)
        try:
            day_value = date.fromisoformat(_normalize_text(day_token))
        except ValueError:
            continue
        value = _num_or_none(value_token)
        if value is None or value <= 0:
            continue
        points.append((day_value, float(value)))
    return points


def _capture_rank_series_by_asin(manifest_dir: Path) -> dict[str, dict[date, float]]:
    manifest_paths = sorted(manifest_dir.glob("f_full_capture_manifest_*.csv"))
    if not manifest_paths:
        return {}

    frames: list[pd.DataFrame] = []
    for path in manifest_paths:
        df = _read_csv(path)
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return {}

    manifest_df = pd.concat(frames, ignore_index=True).fillna("")
    if manifest_df.empty:
        return {}

    if "run_id" in manifest_df.columns:
        manifest_df["_run_id"] = manifest_df.get("run_id", "").map(_normalize_text)
        manifest_df["_observed_utc"] = manifest_df.get("observed_utc", "").map(_normalize_text)
        manifest_df = manifest_df.sort_values(
            by=["_run_id", "_observed_utc"],
            ascending=[True, False],
            kind="stable",
        )
        manifest_df = manifest_df.drop_duplicates(subset=["_run_id"], keep="first")

    if "capture_status" in manifest_df.columns:
        manifest_df = manifest_df[
            manifest_df.get("capture_status", "").map(lambda value: _normalize_text(value).lower()) == "success"
        ].copy()
    if manifest_df.empty:
        return {}

    out: dict[str, dict[date, float]] = {}
    for _, row in manifest_df.iterrows():
        asin = _normalize_key(row.get("asin", ""))
        if asin == "":
            continue
        raw_json_path = Path(_normalize_text(row.get("raw_json_path", "")))
        if not raw_json_path.exists():
            continue
        payload = _read_json(raw_json_path)
        scraped = payload.get("scraped_data", {}) if isinstance(payload.get("scraped_data", {}), dict) else {}
        series_text = _normalize_text(scraped.get("chart_raw_bsr_daily_series", ""))
        if series_text == "":
            series_text = _normalize_text(scraped.get("chart_bsr_daily_series", ""))
        series = _parse_bsr_series(series_text)
        if not series:
            continue
        asin_days = out.setdefault(asin, {})
        for day_value, rank_value in series:
            asin_days[day_value] = rank_value
    return out


def _median_rank_until(day_map: dict[date, float], cutoff: date, trailing_days: int) -> float | None:
    eligible_days = sorted(day for day in day_map if day <= cutoff)
    if not eligible_days:
        return None
    eligible_values = [day_map[day] for day in eligible_days if day_map[day] > 0]
    if not eligible_values:
        return None
    trailing_values = eligible_values[-trailing_days:]
    return float(statistics.median(trailing_values))


def _historical_rank_window(rank_series_by_asin: dict[str, dict[date, float]], asin: str, cutoff: date) -> tuple[float | None, float | None]:
    day_map = rank_series_by_asin.get(asin, {})
    if not day_map:
        return None, None
    return _median_rank_until(day_map, cutoff, 30), _median_rank_until(day_map, cutoff, 90)


def _build_markdown(
    *,
    observed_utc: str,
    cutoff_date: str,
    summary_df: pd.DataFrame,
    report_df: pd.DataFrame,
) -> str:
    metric_map = {
        _normalize_text(row.get("metric", "")): _normalize_text(row.get("value", ""))
        for _, row in summary_df.iterrows()
    }
    lines = [
        "# Stocked SKU Vetting Report",
        "",
        f"- Observed UTC: `{observed_utc}`",
        f"- Reconstructed decision date: `{cutoff_date}`",
        "",
        "## Today plan",
        "- Use sold SKUs with real outcome data as the truth set.",
        "- Read current live-test state from the commercial readiness pack.",
        "- Reconstruct a 30-days-ago vetting view from the prior 30-day sales/profit window and dated rank history.",
        "- Use this to decide which products are safe to test now and which patterns should be blocked.",
        "",
        "## Summary",
        f"- SKU rows reviewed: `{metric_map.get('rows_total', '0')}`",
        f"- Current `test_buy` rows: `{metric_map.get('current_test_buy_rows', '0')}`",
        f"- Current `watch` rows: `{metric_map.get('current_watch_rows', '0')}`",
        f"- Current `reject` rows: `{metric_map.get('current_reject_rows', '0')}`",
        f"- Reconstructed 30-days-ago `test_buy` rows: `{metric_map.get('prior_test_buy_rows', '0')}`",
        f"- Reconstructed 30-days-ago `watch` rows: `{metric_map.get('prior_watch_rows', '0')}`",
        f"- Reconstructed 30-days-ago `reject` rows: `{metric_map.get('prior_reject_rows', '0')}`",
        f"- Rows with nonzero prior 30-day units: `{metric_map.get('prior_nonzero_units_rows', '0')}`",
        f"- Rows with nonzero prior 30-day profit: `{metric_map.get('prior_nonzero_profit_rows', '0')}`",
        f"- 30-days-ago good tests: `{metric_map.get('prior_good_test_rows', '0')}`",
        f"- 30-days-ago bad tests: `{metric_map.get('prior_bad_test_rows', '0')}`",
        f"- 30-days-ago missed winners: `{metric_map.get('prior_missed_winner_rows', '0')}`",
        f"- 30-days-ago avoided losers: `{metric_map.get('prior_avoided_loser_rows', '0')}`",
        "",
        "## Top rows to inspect first",
    ]

    preview_columns = [
        "seller_sku",
        "asin",
        "current_commercial_decision_state",
        "decision_30d_ago_state",
        "outcome_next_30d_truth_decision_state",
        "decision_30d_ago_vs_outcome",
    ]
    preview_df = report_df.loc[:, preview_columns].head(15)
    lines.extend(_markdown_table(preview_df))
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- `current_commercial_decision_state` is what the system says now.")
    lines.append("- `decision_30d_ago_state` is a reconstructed screen using the prior 30-day window, not a frozen archived decision snapshot.")
    lines.append("- `outcome_next_30d_truth_decision_state` is the real result over the following 30 days based on actual profit.")
    lines.append("- If prior-window units and profit are zero across the sample, that means this sold set has no earlier 30-day movement to learn from yet.")
    return "\n".join(lines) + "\n"


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["No rows"]
    headers = [str(column) for column in df.columns]
    rows = [[_normalize_text(value) for value in row] for row in df.astype(str).itertuples(index=False, name=None)]
    header_line = "| " + " | ".join(headers) + " |"
    divider_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return [header_line, divider_line, *body_lines]


def build_stocked_sku_vetting_report(
    *,
    current_pack_path: Path = DEFAULT_CURRENT_PACK_PATH,
    actuals_path: Path = DEFAULT_ACTUALS_PATH,
    full_capture_manifest_dir: Path = DEFAULT_FULL_CAPTURE_MANIFEST_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    decision_profit_floor_gbp: float = DEFAULT_PROFIT_FLOOR_GBP,
) -> StockedSkuVettingReportResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(snapshot_utc)
    cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=lookback_days)).isoformat()
    cutoff_day = date.fromisoformat(cutoff_date)

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"f_stocked_sku_vetting_report_{ts_slug}.csv"
    report_latest_path = output_dir / "f_stocked_sku_vetting_report_latest.csv"
    summary_path = output_dir / f"f_stocked_sku_vetting_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "f_stocked_sku_vetting_summary_latest.csv"
    markdown_path = output_dir / f"f_stocked_sku_vetting_report_{ts_slug}.md"
    markdown_latest_path = output_dir / "f_stocked_sku_vetting_report_latest.md"

    current_pack_df = _read_csv(current_pack_path)
    actuals_df = _read_csv(actuals_path)
    actuals_map = _sold_actuals_by_asin(actuals_df)
    rank_series_by_asin = _capture_rank_series_by_asin(full_capture_manifest_dir)

    rows: list[dict[str, str]] = []
    for _, row in current_pack_df.iterrows():
        asin = _normalize_key(row.get("asin", ""))
        if asin == "":
            continue
        actuals_row = actuals_map.get(asin, {})
        if not actuals_row:
            continue

        seller_sku = _normalize_text(row.get("seller_sku", ""))
        current_truth_state = _normalize_text(row.get("truth_decision_state", "")).lower()
        current_actual_units = _num_or_none(row.get("actual_units_30d", ""))
        current_actual_profit = _num_or_none(row.get("actual_profit_30d_gbp", ""))
        current_sales_lower = _int_or_none(row.get("sales_lower_30d", ""))
        current_sales_upper = _int_or_none(row.get("sales_upper_30d", ""))
        current_rank_risk = _normalize_text(row.get("rank_snapshot_risk_state", ""))
        current_starter_band = _normalize_text(row.get("starter_order_band", ""))
        current_starter_qty = _int_or_none(row.get("starter_test_qty_recommended", ""))
        current_state = _normalize_text(row.get("commercial_decision_state", ""))
        current_readiness = _normalize_text(row.get("live_test_readiness_state", ""))

        actual_units_30 = _num_or_none(actuals_row.get("actual_units_30d", ""))
        actual_units_60 = _num_or_none(actuals_row.get("actual_units_60d", ""))
        actual_profit_30 = _num_or_none(actuals_row.get("actual_profit_30d_gbp", ""))
        actual_profit_60 = _num_or_none(actuals_row.get("actual_profit_60d_gbp", ""))

        prior_units = None
        if actual_units_60 is not None and actual_units_30 is not None:
            prior_units = max(actual_units_60 - actual_units_30, 0.0)

        prior_profit = None
        if actual_profit_60 is not None and actual_profit_30 is not None:
            prior_profit = actual_profit_60 - actual_profit_30

        expected_units = _num_or_none(row.get("model_expected_units_next_30d", ""))
        expected_profit = _num_or_none(row.get("model_expected_profit_next_30d_gbp", ""))
        recommendation_status = _normalize_text(row.get("recommendation_status", "")).lower()
        recommended_qty = _int_or_none(row.get("recommended_test_qty", ""))

        prior_error_ratio = None
        if expected_units is not None and prior_units is not None:
            denom = max(prior_units, 1.0)
            prior_error_ratio = (expected_units - prior_units) / denom
        prior_demand_band = _demand_consistency_band(prior_error_ratio)
        prior_sales_lower, prior_sales_upper = _sales_band(expected_units, prior_demand_band)

        rank_30, rank_90 = _historical_rank_window(rank_series_by_asin, asin, cutoff_day)
        rank_best, rank_worst, rank_stability, rank_risk = _rank_profile(rank_30, rank_90)

        prior_profit_risk = _profit_risk_band(prior_profit, expected_profit, decision_profit_floor_gbp)
        prior_negative_mode = _negative_mode_truth_state(prior_profit, decision_profit_floor_gbp)
        prior_starter_qty = _starter_qty(
            lower_sales_30d=prior_sales_lower,
            recommended_qty=recommended_qty,
            recommendation_status=recommendation_status,
            negative_mode_state=prior_negative_mode,
        )
        prior_starter_band = _starter_order_band(prior_starter_qty)
        prior_state = _commercial_decision(
            recommendation_status=recommendation_status,
            demand_consistency_band=prior_demand_band,
            profit_risk_band=prior_profit_risk,
            rank_risk_state=rank_risk,
            starter_qty=prior_starter_qty,
        )
        prior_readiness = _live_test_readiness_state(rank_risk, prior_state)
        prior_truth_state = _truth_decision_state(prior_profit, decision_profit_floor_gbp)
        outcome_truth_state = _truth_decision_state(current_actual_profit, decision_profit_floor_gbp)

        rows.append(
            {
                "observed_utc": snapshot_utc,
                "decision_cutoff_date": cutoff_date,
                "asin": asin,
                "seller_sku": seller_sku,
                "current_commercial_decision_state": current_state,
                "current_live_test_readiness_state": current_readiness,
                "current_truth_decision_state": current_truth_state,
                "current_actual_units_30d": _num_to_text(current_actual_units),
                "current_actual_profit_30d_gbp": _num_to_text(current_actual_profit),
                "current_sales_lower_30d": _num_to_text(current_sales_lower),
                "current_sales_upper_30d": _num_to_text(current_sales_upper),
                "current_rank_risk_state": current_rank_risk,
                "current_starter_order_band": current_starter_band,
                "current_starter_test_qty_recommended": _num_to_text(current_starter_qty),
                "prior_window_units_30d": _num_to_text(prior_units),
                "prior_window_profit_30d_gbp": _num_to_text(prior_profit),
                "prior_window_truth_decision_state": prior_truth_state,
                "decision_30d_ago_state": prior_state,
                "decision_30d_ago_live_test_readiness_state": prior_readiness,
                "decision_30d_ago_sales_lower_30d": _num_to_text(prior_sales_lower),
                "decision_30d_ago_sales_upper_30d": _num_to_text(prior_sales_upper),
                "decision_30d_ago_rank_best_observed": _num_to_text(rank_best),
                "decision_30d_ago_rank_worst_observed": _num_to_text(rank_worst),
                "decision_30d_ago_rank_stability_band": rank_stability,
                "decision_30d_ago_rank_risk_state": rank_risk,
                "decision_30d_ago_profit_risk_band": prior_profit_risk,
                "decision_30d_ago_negative_mode_state": prior_negative_mode,
                "decision_30d_ago_starter_order_band": prior_starter_band,
                "decision_30d_ago_starter_test_qty": _num_to_text(prior_starter_qty),
                "decision_30d_ago_reason": _decision_reason(
                    profit_risk=prior_profit_risk,
                    negative_mode=prior_negative_mode,
                    rank_risk=rank_risk,
                    demand_band=prior_demand_band,
                    starter_band=prior_starter_band,
                ),
                "outcome_next_30d_units": _num_to_text(current_actual_units),
                "outcome_next_30d_profit_gbp": _num_to_text(current_actual_profit),
                "outcome_next_30d_truth_decision_state": outcome_truth_state,
                "decision_30d_ago_vs_outcome": _decision_vs_outcome(prior_state, outcome_truth_state),
            }
        )

    report_df = pd.DataFrame(rows, columns=REPORT_COLUMNS).fillna("")
    if not report_df.empty:
        report_df = report_df.sort_values(
            by=[
                "current_commercial_decision_state",
                "decision_30d_ago_state",
                "outcome_next_30d_truth_decision_state",
                "asin",
            ],
            ascending=[True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)

    summary_rows = [
        {"observed_utc": snapshot_utc, "metric": "rows_total", "value": str(len(report_df))},
        {
            "observed_utc": snapshot_utc,
            "metric": "current_test_buy_rows",
            "value": str(int((report_df.get("current_commercial_decision_state", pd.Series(dtype=str)) == "test_buy").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "current_watch_rows",
            "value": str(int((report_df.get("current_commercial_decision_state", pd.Series(dtype=str)) == "watch").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "current_reject_rows",
            "value": str(int((report_df.get("current_commercial_decision_state", pd.Series(dtype=str)) == "reject").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "current_ready_for_live_test_rows",
            "value": str(int((report_df.get("current_live_test_readiness_state", pd.Series(dtype=str)) == "ready_for_live_test").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_test_buy_rows",
            "value": str(int((report_df.get("decision_30d_ago_state", pd.Series(dtype=str)) == "test_buy").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_watch_rows",
            "value": str(int((report_df.get("decision_30d_ago_state", pd.Series(dtype=str)) == "watch").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_reject_rows",
            "value": str(int((report_df.get("decision_30d_ago_state", pd.Series(dtype=str)) == "reject").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_nonzero_units_rows",
            "value": str(
                int(
                    pd.to_numeric(
                        report_df.get("prior_window_units_30d", pd.Series(dtype=str)).map(_normalize_text),
                        errors="coerce",
                    ).fillna(0.0).gt(0).sum()
                )
            ),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_nonzero_profit_rows",
            "value": str(
                int(
                    pd.to_numeric(
                        report_df.get("prior_window_profit_30d_gbp", pd.Series(dtype=str)).map(_normalize_text),
                        errors="coerce",
                    ).fillna(0.0).gt(0).sum()
                )
            ),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_good_test_rows",
            "value": str(int((report_df.get("decision_30d_ago_vs_outcome", pd.Series(dtype=str)) == "good_test").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_bad_test_rows",
            "value": str(int((report_df.get("decision_30d_ago_vs_outcome", pd.Series(dtype=str)) == "bad_test").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_missed_winner_rows",
            "value": str(int((report_df.get("decision_30d_ago_vs_outcome", pd.Series(dtype=str)) == "missed_winner").sum())),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "prior_avoided_loser_rows",
            "value": str(int((report_df.get("decision_30d_ago_vs_outcome", pd.Series(dtype=str)) == "avoided_loser").sum())),
        },
    ]
    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)

    report_df.to_csv(report_path, index=False)
    report_df.to_csv(report_latest_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    summary_df.to_csv(summary_latest_path, index=False)

    markdown_text = _build_markdown(
        observed_utc=snapshot_utc,
        cutoff_date=cutoff_date,
        summary_df=summary_df,
        report_df=report_df,
    )
    markdown_path.write_text(markdown_text, encoding="utf-8")
    markdown_latest_path.write_text(markdown_text, encoding="utf-8")

    return StockedSkuVettingReportResult(
        report_df=report_df,
        summary_df=summary_df,
        report_path=report_path,
        report_latest_path=report_latest_path,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
        markdown_path=markdown_path,
        markdown_latest_path=markdown_latest_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stocked-SKU current vs 30-days-ago vetting report.")
    parser.add_argument("--current-pack-path", default=str(DEFAULT_CURRENT_PACK_PATH))
    parser.add_argument("--actuals-path", default=str(DEFAULT_ACTUALS_PATH))
    parser.add_argument("--full-capture-manifest-dir", default=str(DEFAULT_FULL_CAPTURE_MANIFEST_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--decision-profit-floor-gbp", type=float, default=DEFAULT_PROFIT_FLOOR_GBP)
    parser.add_argument("--observed-utc", default="")
    args = parser.parse_args()

    result = build_stocked_sku_vetting_report(
        current_pack_path=Path(args.current_pack_path),
        actuals_path=Path(args.actuals_path),
        full_capture_manifest_dir=Path(args.full_capture_manifest_dir),
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc or None,
        lookback_days=args.lookback_days,
        decision_profit_floor_gbp=float(args.decision_profit_floor_gbp),
    )
    print(
        json.dumps(
            {
                "report_path": str(result.report_path),
                "report_rows": int(len(result.report_df)),
                "summary_path": str(result.summary_path),
                "markdown_path": str(result.markdown_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
