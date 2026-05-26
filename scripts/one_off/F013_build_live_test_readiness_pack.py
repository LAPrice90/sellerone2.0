from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil, floor
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_ACCURACY_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_accuracy_pack_latest.csv"
DEFAULT_PANEL_PATH = DEFAULT_OUTPUT_DIR / "f_live_test_validation_panel_15_latest.csv"
DEFAULT_BACKTEST_INPUT_VIEW_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_input_view_live.csv"
DEFAULT_FULL_CAPTURE_MANIFEST_DIR = DEFAULT_OUTPUT_DIR
DEFAULT_DECISION_PROFIT_FLOOR_GBP = 20.0

PACK_COLUMNS = [
    "observed_utc",
    "asin",
    "seller_sku",
    "truth_decision_state",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "model_expected_units_next_30d",
    "model_expected_profit_next_30d_gbp",
    "estimated_demand",
    "recommended_test_qty",
    "recommendation_status",
    "demand_consistency_band",
    "sales_lower_30d",
    "sales_upper_30d",
    "sales_rank_best_observed",
    "sales_rank_worst_observed",
    "sales_rank_stability_band",
    "rank_snapshot_risk_state",
    "profit_risk_band",
    "negative_mode_truth_state",
    "starter_test_qty_recommended",
    "starter_order_band",
    "commercial_decision_state",
    "live_test_readiness_state",
    "band_hit_flag",
    "false_green_flag",
    "false_red_flag",
    "negative_mode_miss_flag",
    "starter_qty_too_high_flag",
    "starter_qty_too_low_flag",
    "panel_group",
    "panel_rank",
    "panel_selection_reason",
]

SUMMARY_COLUMNS = ["observed_utc", "metric", "value"]


@dataclass(frozen=True)
class LiveTestReadinessPackResult:
    pack_df: pd.DataFrame
    summary_df: pd.DataFrame
    pack_path: Path
    pack_latest_path: Path
    summary_path: Path
    summary_latest_path: Path
    report: dict[str, Any]


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


def _latest_backtest_by_asin(backtest_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if backtest_df.empty or "asin" not in backtest_df.columns:
        return {}
    work = backtest_df.copy()
    work["_asin_key"] = work.get("asin", "").map(_normalize_key)
    work = work[work["_asin_key"] != ""].copy()
    if work.empty:
        return {}
    if "observed_utc" in work.columns:
        work["_obs_ts"] = pd.to_datetime(work.get("observed_utc", "").map(_normalize_text), errors="coerce", utc=True)
        work = work.sort_values("_obs_ts", ascending=False, kind="stable")

    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        asin = _normalize_key(row.get("_asin_key", ""))
        if asin in out:
            continue
        out[asin] = {col: _normalize_text(val) for col, val in row.to_dict().items()}
    return out


def _parse_bsr_series(series_text: str) -> list[tuple[str, float]]:
    raw = _normalize_text(series_text)
    if raw == "":
        return []
    points: list[tuple[str, float]] = []
    for token in raw.split(";"):
        chunk = _normalize_text(token)
        if chunk == "" or "=" not in chunk:
            continue
        day_token, value_token = chunk.split("=", 1)
        day_key = _normalize_text(day_token)
        value = _num_or_none(value_token)
        if day_key == "" or value is None or value <= 0:
            continue
        points.append((day_key, float(value)))
    return points


def _capture_rank_window_by_asin(manifest_dir: Path) -> dict[str, dict[str, float]]:
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

    asin_day_values: dict[str, dict[str, float]] = {}
    for _, row in manifest_df.iterrows():
        asin = _normalize_key(row.get("asin", ""))
        if asin == "":
            continue
        raw_json_path = Path(_normalize_text(row.get("raw_json_path", "")))
        if not raw_json_path.exists():
            continue
        payload = _read_json(raw_json_path)
        scraped = payload.get("scraped_data", {}) if isinstance(payload.get("scraped_data", {}), dict) else {}
        series = _normalize_text(scraped.get("chart_raw_bsr_daily_series", ""))
        if series == "":
            series = _normalize_text(scraped.get("chart_bsr_daily_series", ""))
        parsed_points = _parse_bsr_series(series)
        if not parsed_points:
            continue
        day_map = asin_day_values.setdefault(asin, {})
        for day_key, value in parsed_points:
            day_map[day_key] = value

    rank_map: dict[str, dict[str, float]] = {}
    for asin, day_map in asin_day_values.items():
        if not day_map:
            continue
        ordered_days = sorted(day_map.keys())
        ordered_values = [day_map[day] for day in ordered_days if day_map[day] > 0]
        if not ordered_values:
            continue
        trailing_30 = ordered_values[-30:]
        trailing_90 = ordered_values[-90:]
        rank_map[asin] = {
            "bsr_median_30d": float(statistics.median(trailing_30)) if trailing_30 else float(statistics.median(ordered_values)),
            "bsr_median_90d": float(statistics.median(trailing_90)) if trailing_90 else float(statistics.median(ordered_values)),
        }
    return rank_map


def _panel_by_asin(panel_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if panel_df.empty or "asin" not in panel_df.columns:
        return {}
    out: dict[str, dict[str, str]] = {}
    for _, row in panel_df.iterrows():
        asin = _normalize_key(row.get("asin", ""))
        if asin == "" or asin in out:
            continue
        out[asin] = {col: _normalize_text(val) for col, val in row.to_dict().items()}
    return out


def build_live_test_readiness_pack(
    *,
    accuracy_path: Path = DEFAULT_ACCURACY_PATH,
    panel_path: Path = DEFAULT_PANEL_PATH,
    backtest_input_view_path: Path = DEFAULT_BACKTEST_INPUT_VIEW_PATH,
    full_capture_manifest_dir: Path = DEFAULT_FULL_CAPTURE_MANIFEST_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    decision_profit_floor_gbp: float = DEFAULT_DECISION_PROFIT_FLOOR_GBP,
    observed_utc: str | None = None,
) -> LiveTestReadinessPackResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(snapshot_utc)
    output_dir.mkdir(parents=True, exist_ok=True)

    pack_path = output_dir / f"f_live_test_readiness_pack_{ts_slug}.csv"
    pack_latest_path = output_dir / "f_live_test_readiness_pack_latest.csv"
    summary_path = output_dir / f"f_live_test_readiness_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "f_live_test_readiness_summary_latest.csv"

    accuracy_df = _read_csv(accuracy_path)
    panel_df = _read_csv(panel_path)
    backtest_df = _read_csv(backtest_input_view_path)

    panel_map = _panel_by_asin(panel_df)
    backtest_map = _latest_backtest_by_asin(backtest_df)
    capture_rank_map = _capture_rank_window_by_asin(full_capture_manifest_dir)

    rows: list[dict[str, str]] = []
    rows_using_backtest_rank = 0
    rows_using_capture_rank = 0
    rows_missing_rank = 0
    for _, row in accuracy_df.iterrows():
        asin = _normalize_key(row.get("asin", ""))
        if asin == "":
            continue

        seller_sku = _normalize_text(row.get("seller_sku", ""))
        truth_decision_state = _normalize_text(row.get("truth_decision_state", "")).lower()
        actual_units = _num_or_none(row.get("actual_units_30d", ""))
        actual_profit = _num_or_none(row.get("actual_profit_30d_gbp", ""))
        expected_units = _num_or_none(row.get("model_expected_units_next_30d", ""))
        expected_profit = _num_or_none(row.get("model_expected_profit_next_30d_gbp", ""))
        error_ratio = _num_or_none(row.get("demand_error_ratio_30d", ""))

        demand_consistency = _demand_consistency_band(error_ratio)
        sales_center = expected_units if expected_units is not None else actual_units
        sales_lower, sales_upper = _sales_band(sales_center, demand_consistency)

        backtest_row = backtest_map.get(asin, {})
        rank_30 = _num_or_none(backtest_row.get("bsr_median_30d", ""))
        rank_90 = _num_or_none(backtest_row.get("bsr_median_90d", ""))
        used_backtest_rank = False
        used_capture_rank = False
        if rank_30 is not None or rank_90 is not None:
            used_backtest_rank = True
        if rank_30 is None or rank_90 is None:
            capture_row = capture_rank_map.get(asin, {})
            capture_rank_30 = _num_or_none(capture_row.get("bsr_median_30d", ""))
            capture_rank_90 = _num_or_none(capture_row.get("bsr_median_90d", ""))
            if rank_30 is None and capture_rank_30 is not None:
                rank_30 = capture_rank_30
                used_capture_rank = True
            if rank_90 is None and capture_rank_90 is not None:
                rank_90 = capture_rank_90
                used_capture_rank = True
        rank_best, rank_worst, rank_stability, rank_risk = _rank_profile(rank_30, rank_90)
        if used_capture_rank:
            rows_using_capture_rank += 1
        elif used_backtest_rank:
            rows_using_backtest_rank += 1
        else:
            rows_missing_rank += 1

        profit_risk = _profit_risk_band(actual_profit, expected_profit, decision_profit_floor_gbp)
        negative_mode = _negative_mode_truth_state(actual_profit, decision_profit_floor_gbp)

        recommendation_status = _normalize_text(row.get("recommendation_status", "")).lower()
        recommended_qty = _int_or_none(row.get("recommended_test_qty", ""))
        starter_qty = _starter_qty(
            lower_sales_30d=sales_lower,
            recommended_qty=recommended_qty,
            recommendation_status=recommendation_status,
            negative_mode_state=negative_mode,
        )
        starter_band = _starter_order_band(starter_qty)

        commercial_state = _commercial_decision(
            recommendation_status=recommendation_status,
            demand_consistency_band=demand_consistency,
            profit_risk_band=profit_risk,
            rank_risk_state=rank_risk,
            starter_qty=starter_qty,
        )
        live_readiness = _live_test_readiness_state(rank_risk, commercial_state)

        band_hit = (
            1
            if (
                actual_units is not None
                and sales_lower is not None
                and sales_upper is not None
                and float(sales_lower) <= float(actual_units) <= float(sales_upper)
            )
            else 0
        )
        false_green = 1 if commercial_state == "test_buy" and truth_decision_state == "fail" else 0
        false_red = 1 if commercial_state == "reject" and truth_decision_state == "pass" else 0
        negative_mode_miss = 1 if negative_mode == "negative_mode_active" and commercial_state != "reject" else 0
        starter_too_high = 1 if (actual_units is not None and starter_qty > int(actual_units) and starter_qty > 0) else 0
        starter_too_low = 1 if (truth_decision_state == "pass" and starter_qty <= 0) else 0

        panel_row = panel_map.get(asin, {})
        panel_group = _normalize_text(panel_row.get("panel_group", ""))
        panel_rank = _normalize_text(panel_row.get("panel_rank", ""))
        panel_reason = _normalize_text(panel_row.get("selection_reason", ""))

        out_row = {
            "observed_utc": snapshot_utc,
            "asin": asin,
            "seller_sku": seller_sku,
            "truth_decision_state": truth_decision_state,
            "actual_units_30d": _num_to_text(actual_units),
            "actual_profit_30d_gbp": _num_to_text(actual_profit),
            "model_expected_units_next_30d": _num_to_text(expected_units),
            "model_expected_profit_next_30d_gbp": _num_to_text(expected_profit),
            "estimated_demand": _normalize_text(row.get("estimated_demand", "")).lower(),
            "recommended_test_qty": _normalize_text(row.get("recommended_test_qty", "")),
            "recommendation_status": recommendation_status,
            "demand_consistency_band": demand_consistency,
            "sales_lower_30d": _num_to_text(sales_lower),
            "sales_upper_30d": _num_to_text(sales_upper),
            "sales_rank_best_observed": _num_to_text(rank_best),
            "sales_rank_worst_observed": _num_to_text(rank_worst),
            "sales_rank_stability_band": rank_stability,
            "rank_snapshot_risk_state": rank_risk,
            "profit_risk_band": profit_risk,
            "negative_mode_truth_state": negative_mode,
            "starter_test_qty_recommended": _num_to_text(starter_qty),
            "starter_order_band": starter_band,
            "commercial_decision_state": commercial_state,
            "live_test_readiness_state": live_readiness,
            "band_hit_flag": str(int(band_hit)),
            "false_green_flag": str(int(false_green)),
            "false_red_flag": str(int(false_red)),
            "negative_mode_miss_flag": str(int(negative_mode_miss)),
            "starter_qty_too_high_flag": str(int(starter_too_high)),
            "starter_qty_too_low_flag": str(int(starter_too_low)),
            "panel_group": panel_group,
            "panel_rank": panel_rank,
            "panel_selection_reason": panel_reason,
        }
        rows.append({col: _normalize_text(out_row.get(col, "")) for col in PACK_COLUMNS})

    pack_df = pd.DataFrame(rows, columns=PACK_COLUMNS)
    if not pack_df.empty:
        pack_df = pack_df.sort_values(
            by=["asin", "seller_sku"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

    commercial_judged_rows = int((pack_df.get("commercial_decision_state", pd.Series([], dtype=str)).map(_normalize_text) != "").sum())
    false_green_rows = int((pack_df.get("false_green_flag", pd.Series([], dtype=str)).map(_normalize_text) == "1").sum())
    false_red_rows = int((pack_df.get("false_red_flag", pd.Series([], dtype=str)).map(_normalize_text) == "1").sum())
    negative_mode_miss_rows = int(
        (pack_df.get("negative_mode_miss_flag", pd.Series([], dtype=str)).map(_normalize_text) == "1").sum()
    )
    starter_qty_too_high_rows = int(
        (pack_df.get("starter_qty_too_high_flag", pd.Series([], dtype=str)).map(_normalize_text) == "1").sum()
    )
    starter_qty_too_low_rows = int(
        (pack_df.get("starter_qty_too_low_flag", pd.Series([], dtype=str)).map(_normalize_text) == "1").sum()
    )
    band_hit_rows = int((pack_df.get("band_hit_flag", pd.Series([], dtype=str)).map(_normalize_text) == "1").sum())
    live_test_ready_rows = int(
        (pack_df.get("live_test_readiness_state", pd.Series([], dtype=str)).map(_normalize_text) == "ready_for_live_test").sum()
    )
    rank_gap_rows = int(
        (pack_df.get("live_test_readiness_state", pd.Series([], dtype=str)).map(_normalize_text) == "not_ready_rank_gap").sum()
    )

    panel_rows = pack_df[pack_df.get("panel_group", pd.Series([], dtype=str)).map(_normalize_text) != ""].copy()
    panel_rows_total = int(len(panel_rows.index))
    panel_blank_commercial_state_rows = int(
        (panel_rows.get("commercial_decision_state", pd.Series([], dtype=str)).map(_normalize_text) == "").sum()
    )

    summary_rows: list[dict[str, str]] = [
        {"observed_utc": snapshot_utc, "metric": "commercial_rows_total", "value": str(int(len(pack_df.index)))},
        {"observed_utc": snapshot_utc, "metric": "commercial_judged_rows", "value": str(commercial_judged_rows)},
        {"observed_utc": snapshot_utc, "metric": "false_green_rows", "value": str(false_green_rows)},
        {"observed_utc": snapshot_utc, "metric": "false_red_rows", "value": str(false_red_rows)},
        {"observed_utc": snapshot_utc, "metric": "negative_mode_miss_rows", "value": str(negative_mode_miss_rows)},
        {"observed_utc": snapshot_utc, "metric": "starter_qty_too_high_rows", "value": str(starter_qty_too_high_rows)},
        {"observed_utc": snapshot_utc, "metric": "starter_qty_too_low_rows", "value": str(starter_qty_too_low_rows)},
        {"observed_utc": snapshot_utc, "metric": "band_hit_rows", "value": str(band_hit_rows)},
        {"observed_utc": snapshot_utc, "metric": "live_test_ready_rows", "value": str(live_test_ready_rows)},
        {"observed_utc": snapshot_utc, "metric": "rank_gap_rows", "value": str(rank_gap_rows)},
        {"observed_utc": snapshot_utc, "metric": "rows_using_backtest_rank_window", "value": str(rows_using_backtest_rank)},
        {"observed_utc": snapshot_utc, "metric": "rows_using_full_capture_rank_window", "value": str(rows_using_capture_rank)},
        {"observed_utc": snapshot_utc, "metric": "rows_missing_rank_window", "value": str(rows_missing_rank)},
        {"observed_utc": snapshot_utc, "metric": "panel_rows_total", "value": str(panel_rows_total)},
        {
            "observed_utc": snapshot_utc,
            "metric": "panel_rows_with_blank_commercial_state",
            "value": str(panel_blank_commercial_state_rows),
        },
    ]

    for group in ["big_pass", "big_fail", "on_the_line"]:
        subset = panel_rows[panel_rows["panel_group"].map(_normalize_text) == group].copy()
        summary_rows.append(
            {"observed_utc": snapshot_utc, "metric": f"panel_{group}_rows", "value": str(int(len(subset.index)))}
        )
        for decision in ["test_buy", "watch", "reject"]:
            summary_rows.append(
                {
                    "observed_utc": snapshot_utc,
                    "metric": f"panel_{group}_{decision}_rows",
                    "value": str(
                        int((subset.get("commercial_decision_state", pd.Series([], dtype=str)).map(_normalize_text) == decision).sum())
                    ),
                }
            )

    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)

    pack_df.to_csv(pack_path, index=False)
    pack_df.to_csv(pack_latest_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    summary_df.to_csv(summary_latest_path, index=False)

    report = {
        "status": "success",
        "observed_utc": snapshot_utc,
        "metrics": {
            "commercial_rows_total": int(len(pack_df.index)),
            "commercial_judged_rows": commercial_judged_rows,
            "false_green_rows": false_green_rows,
            "false_red_rows": false_red_rows,
            "negative_mode_miss_rows": negative_mode_miss_rows,
            "starter_qty_too_high_rows": starter_qty_too_high_rows,
            "starter_qty_too_low_rows": starter_qty_too_low_rows,
            "band_hit_rows": band_hit_rows,
            "live_test_ready_rows": live_test_ready_rows,
            "rank_gap_rows": rank_gap_rows,
            "rows_using_backtest_rank_window": rows_using_backtest_rank,
            "rows_using_full_capture_rank_window": rows_using_capture_rank,
            "rows_missing_rank_window": rows_missing_rank,
            "panel_rows_total": panel_rows_total,
            "panel_rows_with_blank_commercial_state": panel_blank_commercial_state_rows,
        },
        "artifacts": {
            "pack_csv_output": str(pack_path),
            "pack_latest_csv": str(pack_latest_path),
            "summary_csv_output": str(summary_path),
            "summary_latest_csv": str(summary_latest_path),
        },
    }
    print(json.dumps(report))

    return LiveTestReadinessPackResult(
        pack_df=pack_df,
        summary_df=summary_df,
        pack_path=pack_path,
        pack_latest_path=pack_latest_path,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
        report=report,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build commercial decision bands and live-test readiness pack.")
    parser.add_argument("--accuracy-path", default=str(DEFAULT_ACCURACY_PATH))
    parser.add_argument("--panel-path", default=str(DEFAULT_PANEL_PATH))
    parser.add_argument("--backtest-input-view-path", default=str(DEFAULT_BACKTEST_INPUT_VIEW_PATH))
    parser.add_argument("--full-capture-manifest-dir", default=str(DEFAULT_FULL_CAPTURE_MANIFEST_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--decision-profit-floor-gbp", default=str(DEFAULT_DECISION_PROFIT_FLOOR_GBP))
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_live_test_readiness_pack(
        accuracy_path=Path(args.accuracy_path),
        panel_path=Path(args.panel_path),
        backtest_input_view_path=Path(args.backtest_input_view_path),
        full_capture_manifest_dir=Path(args.full_capture_manifest_dir),
        output_dir=Path(args.output_dir),
        decision_profit_floor_gbp=float(args.decision_profit_floor_gbp),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
