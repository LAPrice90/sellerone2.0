from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
ALIGNMENT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_alignment_30d_latest.csv"
FACTOR_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_factor_impacts_latest.csv"

MARKET_FACTS_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_market_facts_latest.csv"
ACTION_OUTCOMES_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_action_outcomes_latest.csv"
SCRAPE_GAP_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_scrape_gap_report_latest.csv"
SKU_PERFORMANCE_PATH = ROOT / "out" / "sku_performance_summary.csv"
IDENTITY_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv"
ASSUMPTION_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_assumption_snapshots_latest.csv"
F_SALES_VALIDATION_PATH = ROOT / "out" / "analysis_reports" / "f_sales_history_validation_latest.csv"
F_CALIBRATION_PATH = ROOT / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv"
F_FULL_CAPTURE_FACTS_PATH = ROOT / "out" / "analysis_reports" / "f_full_capture_normalized_facts_latest.csv"

REQUIRED_INPUTS = [
    MARKET_FACTS_PATH,
    ACTION_OUTCOMES_PATH,
    SCRAPE_GAP_PATH,
    SKU_PERFORMANCE_PATH,
    IDENTITY_PATH,
    ASSUMPTION_PATH,
    F_SALES_VALIDATION_PATH,
    F_CALIBRATION_PATH,
]

RESCRAPE_MISSING_RATE_TRIGGER = 0.80
RESCRAPE_THIN_RATE_TRIGGER = 0.05
RESCRAPE_STALE_RATE_TRIGGER = 0.10

DEMAND_BUCKET_TO_UNITS = {
    "high": 8.0,
    "medium": 5.0,
    "low": 2.0,
}


@dataclass(frozen=True)
class AlignmentBuildResult:
    alignment_output_path: Path
    alignment_rows: int
    factor_output_path: Path
    factor_rows: int
    rescrape_missing_rate: float
    rescrape_thin_rate: float
    rescrape_stale_rate: float
    rescrape_trigger_flag: bool
    rescrape_trigger_reason: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _column_as_text(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column].map(_normalize_text)
    return pd.Series([""] * len(df.index), index=df.index, dtype=str)


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required batch-002 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _to_float(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _is_finite_number(value: object) -> bool:
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _to_float_text(value: float | None) -> str:
    if value is None or not _is_finite_number(value):
        return ""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _expected_units_from_assumption(*, estimated_demand: object, recommended_test_qty: object) -> float | None:
    qty_value = _to_float(recommended_test_qty)
    if qty_value is not None and _is_finite_number(qty_value) and qty_value > 0:
        return float(qty_value)

    demand_value = _to_float(estimated_demand)
    if demand_value is not None and _is_finite_number(demand_value) and demand_value > 0:
        return float(demand_value)

    demand_bucket = _normalize_text(estimated_demand).lower()
    if demand_bucket in DEMAND_BUCKET_TO_UNITS:
        return DEMAND_BUCKET_TO_UNITS[demand_bucket]

    return None


def _build_expected_maps(
    *,
    identity_df: pd.DataFrame,
    assumption_df: pd.DataFrame,
    sales_validation_df: pd.DataFrame,
    calibration_df: pd.DataFrame,
    full_capture_facts_df: pd.DataFrame,
) -> tuple[
    dict[tuple[str, str], float],
    dict[tuple[str, str], float],
    dict[str, float],
    dict[str, float],
    dict[str, float],
    dict[str, float],
]:
    identity = pd.DataFrame()
    identity["candidate_id"] = _column_as_text(identity_df, "candidate_id")
    identity["supplier_sku"] = _column_as_text(identity_df, "supplier_sku")
    identity["sku"] = _column_as_text(identity_df, "sku")
    identity["asin"] = _column_as_text(identity_df, "asin")
    identity = identity[(identity["candidate_id"] != "") & (identity["asin"] != "")].copy()

    assumption = pd.DataFrame()
    assumption["candidate_id"] = _column_as_text(assumption_df, "candidate_id")
    assumption["estimated_demand"] = _column_as_text(assumption_df, "estimated_demand")
    assumption["recommended_test_qty"] = _column_as_text(assumption_df, "recommended_test_qty")
    assumption["estimated_margin_gbp"] = _column_as_text(assumption_df, "estimated_margin_gbp")
    assumption = assumption[assumption["candidate_id"] != ""].copy()

    joined = identity.merge(assumption, on="candidate_id", how="left")
    joined = joined[(joined["sku"] != "") & (joined["asin"] != "")].copy()
    joined["expected_units"] = joined.apply(
        lambda row: _expected_units_from_assumption(
            estimated_demand=row.get("estimated_demand", ""),
            recommended_test_qty=row.get("recommended_test_qty", ""),
        ),
        axis=1,
    )
    joined["margin"] = joined["estimated_margin_gbp"].map(_to_float)
    joined["expected_profit"] = joined.apply(
        lambda row: row["expected_units"] * row["margin"]
        if row["expected_units"] is not None and row["margin"] is not None
        else None,
        axis=1,
    )

    expected_units_by_sku_asin: dict[tuple[str, str], float] = {}
    expected_profit_by_sku_asin: dict[tuple[str, str], float] = {}
    if not joined.empty:
        grouped = joined.groupby(["sku", "asin"], dropna=False)
        for (sku, asin), group in grouped:
            units = [float(value) for value in group["expected_units"].tolist() if _is_finite_number(value)]
            profit = [float(value) for value in group["expected_profit"].tolist() if _is_finite_number(value)]
            units_avg = _avg(units)
            profit_avg = _avg(profit)
            if units_avg is not None:
                expected_units_by_sku_asin[(str(sku), str(asin))] = units_avg
            if profit_avg is not None:
                expected_profit_by_sku_asin[(str(sku), str(asin))] = profit_avg

    expected_units_by_asin: dict[str, float] = {}
    if not sales_validation_df.empty:
        sales = pd.DataFrame()
        sales["asin"] = _column_as_text(sales_validation_df, "asin")
        sales["month_units"] = _column_as_text(sales_validation_df, "month_units").map(_to_float)
        sales["trusted_for_demand_basis"] = _column_as_text(sales_validation_df, "trusted_for_demand_basis")
        sales = sales[(sales["asin"] != "") & (sales["trusted_for_demand_basis"] == "1")].copy()
        if not sales.empty:
            grouped = sales.groupby("asin")
            for asin, group in grouped:
                values = [float(value) for value in group["month_units"].tolist() if _is_finite_number(value)]
                avg_value = _avg(values)
                if avg_value is not None:
                    expected_units_by_asin[str(asin)] = avg_value

    expected_profit_by_asin: dict[str, float] = {}
    if not calibration_df.empty:
        calib = pd.DataFrame()
        calib["asin"] = _column_as_text(calibration_df, "asin")
        calib["estimated_monthly_profit_gbp"] = _column_as_text(calibration_df, "estimated_monthly_profit_gbp").map(_to_float)
        calib = calib[calib["asin"] != ""].copy()
        if not calib.empty:
            grouped = calib.groupby("asin")
            for asin, group in grouped:
                values = [float(value) for value in group["estimated_monthly_profit_gbp"].tolist() if _is_finite_number(value)]
                avg_value = _avg(values)
                if avg_value is not None:
                    expected_profit_by_asin[str(asin)] = avg_value

    expected_units_by_asin_from_full_capture: dict[str, float] = {}
    expected_profit_by_asin_from_full_capture: dict[str, float] = {}
    if not full_capture_facts_df.empty:
        full_capture = pd.DataFrame()
        full_capture["asin"] = _column_as_text(full_capture_facts_df, "asin")
        full_capture["capture_status"] = _column_as_text(full_capture_facts_df, "capture_status")
        full_capture["basis_source"] = _column_as_text(full_capture_facts_df, "bbp_sales_replay_demand_basis_source")
        full_capture["basis_units"] = _column_as_text(full_capture_facts_df, "bbp_sales_replay_demand_basis_units").map(_to_float)
        full_capture["estimated_monthly_profit"] = _column_as_text(
            full_capture_facts_df, "estimated_monthly_profit"
        ).map(_to_float)
        full_capture = full_capture[(full_capture["asin"] != "") & (full_capture["capture_status"] == "success")].copy()
        if not full_capture.empty:
            full_capture = full_capture[
                full_capture["basis_source"].isin({"bbp_last_completed_month", "bbp_zero_history"})
            ].copy()
            if not full_capture.empty:
                grouped = full_capture.groupby("asin")
                for asin, group in grouped:
                    units_values = [
                        float(value)
                        for value in group["basis_units"].tolist()
                        if _is_finite_number(value)
                    ]
                    profit_values = [
                        float(value)
                        for value in group["estimated_monthly_profit"].tolist()
                        if _is_finite_number(value)
                    ]
                    units_avg = _avg(units_values)
                    profit_avg = _avg(profit_values)
                    if units_avg is not None:
                        expected_units_by_asin_from_full_capture[str(asin)] = units_avg
                    if profit_avg is not None:
                        expected_profit_by_asin_from_full_capture[str(asin)] = profit_avg

    return (
        expected_units_by_sku_asin,
        expected_profit_by_sku_asin,
        expected_units_by_asin,
        expected_profit_by_asin,
        expected_units_by_asin_from_full_capture,
        expected_profit_by_asin_from_full_capture,
    )


def _build_actual_maps(perf_df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    perf = pd.DataFrame()
    perf["sku"] = _column_as_text(perf_df, "sku")
    perf["window_days"] = _column_as_text(perf_df, "window_days")
    perf["actual_units_30d"] = _column_as_text(perf_df, "units_sold").map(_to_float)
    perf["actual_profit_30d_gbp"] = _column_as_text(perf_df, "profit_exvat_gbp").map(_to_float)
    perf = perf[perf["sku"] != ""].copy()
    perf = perf[(perf["window_days"] == "30") | (perf["window_days"] == "")].copy()
    perf = perf.sort_values(["sku", "window_days"], ascending=[True, True], kind="stable")
    perf = perf.drop_duplicates(subset=["sku"], keep="first")

    units_map: dict[str, float] = {}
    profit_map: dict[str, float] = {}
    for _, row in perf.iterrows():
        sku = _normalize_text(row.get("sku", ""))
        units = row.get("actual_units_30d")
        profit = row.get("actual_profit_30d_gbp")
        if sku == "":
            continue
        if _is_finite_number(units):
            units_map[sku] = float(units)
        if _is_finite_number(profit):
            profit_map[sku] = float(profit)
    return units_map, profit_map


def _build_market_factor_maps(market_facts_df: pd.DataFrame, action_outcomes_df: pd.DataFrame) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    market = pd.DataFrame()
    market["sku"] = _column_as_text(market_facts_df, "sku")
    market["asin"] = _column_as_text(market_facts_df, "asin")
    market["amazon_present_flag"] = _column_as_text(market_facts_df, "amazon_present_flag").map(_to_float)
    market["buy_box_price"] = _column_as_text(market_facts_df, "buy_box_price_gbp").map(_to_float)
    market["lowest_fba"] = _column_as_text(market_facts_df, "lowest_fba_price_gbp").map(_to_float)
    market["lowest_fbm"] = _column_as_text(market_facts_df, "lowest_fbm_price_gbp").map(_to_float)
    market = market[(market["sku"] != "") & (market["asin"] != "")].copy()

    amazon_share_map: dict[tuple[str, str], float] = {}
    undercut_gap_map: dict[tuple[str, str], float] = {}
    if not market.empty:
        grouped = market.groupby(["sku", "asin"], dropna=False)
        for (sku, asin), group in grouped:
            amazon_values = [float(value) for value in group["amazon_present_flag"].tolist() if _is_finite_number(value)]
            amazon_avg = _avg(amazon_values)
            if amazon_avg is not None:
                amazon_share_map[(str(sku), str(asin))] = amazon_avg

            gaps: list[float] = []
            for _, row in group.iterrows():
                buy_box = row.get("buy_box_price")
                lowest_fba = row.get("lowest_fba")
                lowest_fbm = row.get("lowest_fbm")
                candidates = [float(value) for value in [lowest_fba, lowest_fbm] if _is_finite_number(value)]
                if not _is_finite_number(buy_box) or not candidates:
                    continue
                gaps.append(float(buy_box) - min(candidates))
            gap_avg = _avg(gaps)
            if gap_avg is not None:
                undercut_gap_map[(str(sku), str(asin))] = gap_avg

    actions = pd.DataFrame()
    actions["sku"] = _column_as_text(action_outcomes_df, "sku")
    actions["asin"] = _column_as_text(action_outcomes_df, "asin")
    actions["seller_count"] = _column_as_text(action_outcomes_df, "seller_count").map(_to_float)
    actions = actions[(actions["sku"] != "") & (actions["asin"] != "")].copy()

    seller_count_map: dict[tuple[str, str], float] = {}
    if not actions.empty:
        grouped = actions.groupby(["sku", "asin"], dropna=False)
        for (sku, asin), group in grouped:
            values = [float(value) for value in group["seller_count"].tolist() if _is_finite_number(value)]
            avg_value = _avg(values)
            if avg_value is not None:
                seller_count_map[(str(sku), str(asin))] = avg_value

    return amazon_share_map, undercut_gap_map, seller_count_map


def _discrepancy_class(expected_units: float | None, actual_units: float | None) -> str:
    if expected_units is None:
        return "missing_expected_baseline"
    if actual_units is None:
        return "missing_actual_30d"
    if expected_units <= 0:
        return "expected_zero_actual_positive" if actual_units > 0 else "matched_zero"
    error_pct = (actual_units - expected_units) / expected_units
    if abs(error_pct) <= 0.20:
        return "aligned"
    if error_pct < -0.20:
        return "underperform_vs_expected"
    return "outperform_vs_expected"


def _rescrape_trigger(scrape_gap_df: pd.DataFrame) -> tuple[bool, str, float, float, float, str]:
    if scrape_gap_df.empty:
        return False, "none", 0.0, 0.0, 0.0, ""

    total = float(len(scrape_gap_df.index))
    missing = float((scrape_gap_df["scrape_coverage_status"] == "missing").sum())
    thin = float((scrape_gap_df["scrape_coverage_status"] == "thin").sum())
    stale = float((scrape_gap_df["scrape_coverage_status"] == "stale").sum())
    missing_rate = missing / total if total > 0 else 0.0
    thin_rate = thin / total if total > 0 else 0.0
    stale_rate = stale / total if total > 0 else 0.0

    reasons: list[str] = []
    if missing_rate > RESCRAPE_MISSING_RATE_TRIGGER:
        reasons.append("missing_rate_gt_80pct")
    if thin_rate > RESCRAPE_THIN_RATE_TRIGGER:
        reasons.append("thin_rate_gt_5pct")
    if stale_rate > RESCRAPE_STALE_RATE_TRIGGER:
        reasons.append("stale_rate_gt_10pct")

    owner_path = ""
    if "queue_owner_path" in scrape_gap_df.columns:
        owner_non_empty = scrape_gap_df["queue_owner_path"].map(_normalize_text)
        owner_non_empty = owner_non_empty[owner_non_empty != ""]
        if not owner_non_empty.empty:
            owner_path = owner_non_empty.iloc[0]

    return len(reasons) > 0, ";".join(reasons) if reasons else "none", missing_rate, thin_rate, stale_rate, owner_path


def _build_alignment(
    *,
    market_facts_df: pd.DataFrame,
    action_outcomes_df: pd.DataFrame,
    scrape_gap_df: pd.DataFrame,
    expected_units_by_sku_asin: dict[tuple[str, str], float],
    expected_profit_by_sku_asin: dict[tuple[str, str], float],
    expected_units_by_asin: dict[str, float],
    expected_profit_by_asin: dict[str, float],
    expected_units_by_asin_from_full_capture: dict[str, float],
    expected_profit_by_asin_from_full_capture: dict[str, float],
    actual_units_by_sku: dict[str, float],
    actual_profit_by_sku: dict[str, float],
    snapshot_utc: str,
) -> tuple[pd.DataFrame, pd.DataFrame, bool, str, float, float, float]:
    base = pd.DataFrame()
    base["sku"] = _column_as_text(market_facts_df, "sku")
    base["asin"] = _column_as_text(market_facts_df, "asin")
    base = base[(base["sku"] != "") & (base["asin"] != "")].copy()
    base = base.drop_duplicates(subset=["sku", "asin"], keep="first")

    amazon_share_map, undercut_gap_map, seller_count_map = _build_market_factor_maps(market_facts_df, action_outcomes_df)
    rescrape_trigger_flag, rescrape_reason, missing_rate, thin_rate, stale_rate, owner_path = _rescrape_trigger(scrape_gap_df)

    scrape_status_by_asin: dict[str, str] = {}
    if not scrape_gap_df.empty:
        scrape = pd.DataFrame()
        scrape["asin"] = _column_as_text(scrape_gap_df, "asin")
        scrape["status"] = _column_as_text(scrape_gap_df, "scrape_coverage_status")
        scrape = scrape[scrape["asin"] != ""].copy()
        priority = {"missing": 3, "stale": 2, "thin": 1, "ok": 0}
        if not scrape.empty:
            grouped = scrape.groupby("asin")
            for asin, group in grouped:
                ranked = sorted(group["status"].tolist(), key=lambda value: priority.get(_normalize_text(value), -1), reverse=True)
                scrape_status_by_asin[str(asin)] = _normalize_text(ranked[0]) if ranked else ""

    alignment_rows: list[dict[str, str]] = []
    for _, row in base.iterrows():
        sku = _normalize_text(row.get("sku", ""))
        asin = _normalize_text(row.get("asin", ""))
        key = (sku, asin)

        expected_units_source = "no_source"
        expected_profit_source = "no_source"

        expected_units = expected_units_by_sku_asin.get(key)
        if expected_units is not None:
            expected_units_source = "assumption_candidate_sku_asin"
        else:
            expected_units = expected_units_by_asin.get(asin)
            if expected_units is not None:
                expected_units_source = "sales_validation_asin"
            else:
                expected_units = expected_units_by_asin_from_full_capture.get(asin)
                if expected_units is not None:
                    expected_units_source = "full_capture_asin"

        expected_profit = expected_profit_by_sku_asin.get(key)
        if expected_profit is not None:
            expected_profit_source = "assumption_candidate_sku_asin"
        else:
            expected_profit = expected_profit_by_asin.get(asin)
            if expected_profit is not None:
                expected_profit_source = "calibration_asin"
            else:
                expected_profit = expected_profit_by_asin_from_full_capture.get(asin)
                if expected_profit is not None:
                    expected_profit_source = "full_capture_asin"

        actual_units = actual_units_by_sku.get(sku)
        actual_profit = actual_profit_by_sku.get(sku)

        units_error_pct = None
        if expected_units is not None and expected_units > 0 and actual_units is not None:
            units_error_pct = (actual_units - expected_units) / expected_units
        profit_error_pct = None
        if expected_profit is not None and expected_profit != 0 and actual_profit is not None:
            profit_error_pct = (actual_profit - expected_profit) / expected_profit

        discrepancy = _discrepancy_class(expected_units, actual_units)
        scrape_status = scrape_status_by_asin.get(asin, "")
        scrape_signal_flag = "1" if scrape_status in {"missing", "stale", "thin"} else "0"
        scrape_signal_reason = f"asin_scrape_status:{scrape_status}" if scrape_signal_flag == "1" else "none"

        alignment_rows.append(
            {
                "alignment_window_end_utc": snapshot_utc,
                "sku": sku,
                "asin": asin,
                "expected_units_30d": _to_float_text(expected_units),
                "expected_units_source": expected_units_source,
                "expected_profit_30d_gbp": _to_float_text(expected_profit),
                "expected_profit_source": expected_profit_source,
                "actual_units_30d": _to_float_text(actual_units),
                "actual_profit_30d_gbp": _to_float_text(actual_profit),
                "units_error_pct": _to_float_text(units_error_pct),
                "profit_error_pct": _to_float_text(profit_error_pct),
                "avg_seller_count": _to_float_text(seller_count_map.get(key)),
                "amazon_presence_share_pct": _to_float_text(amazon_share_map.get(key)),
                "avg_undercut_gap_gbp": _to_float_text(undercut_gap_map.get(key)),
                "dominant_discrepancy_class": discrepancy,
                "rescrape_signal_flag": scrape_signal_flag,
                "rescrape_signal_reason": scrape_signal_reason,
                "rescrape_owner_path": owner_path,
            }
        )

    alignment_df = pd.DataFrame(alignment_rows).fillna("")
    alignment_df = alignment_df.sort_values(["sku", "asin"], ascending=[True, True], kind="stable")

    factor_rows: list[dict[str, str]] = []
    if not alignment_df.empty:
        grouped = alignment_df.groupby("dominant_discrepancy_class", dropna=False)
        for discrepancy, group in grouped:
            units_errors = [float(value) for value in group["units_error_pct"].map(_to_float).tolist() if _is_finite_number(value)]
            profit_errors = [float(value) for value in group["profit_error_pct"].map(_to_float).tolist() if _is_finite_number(value)]
            seller_values = [float(value) for value in group["avg_seller_count"].map(_to_float).tolist() if _is_finite_number(value)]
            amazon_values = [float(value) for value in group["amazon_presence_share_pct"].map(_to_float).tolist() if _is_finite_number(value)]

            factor_rows.append(
                {
                    "snapshot_utc": snapshot_utc,
                    "factor_bucket": _normalize_text(discrepancy),
                    "sample_rows": str(int(len(group.index))),
                    "avg_units_error_pct": _to_float_text(_avg(units_errors)),
                    "avg_profit_error_pct": _to_float_text(_avg(profit_errors)),
                    "avg_seller_count": _to_float_text(_avg(seller_values)),
                    "amazon_presence_share_pct": _to_float_text(_avg(amazon_values)),
                    "rescrape_trigger_flag": "1" if rescrape_trigger_flag else "0",
                    "rescrape_trigger_reason": rescrape_reason,
                    "rescrape_owner_path": owner_path,
                    "recommended_collection_mode": "F061_MODE=data_collection",
                    "thin_sample_flag": "1" if len(group.index) < 10 else "0",
                }
            )

    factor_df = pd.DataFrame(factor_rows).fillna("")
    factor_df = factor_df.sort_values(["factor_bucket"], ascending=[True], kind="stable")

    return (
        alignment_df,
        factor_df,
        rescrape_trigger_flag,
        rescrape_reason,
        missing_rate,
        thin_rate,
        stale_rate,
    )


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required batch-002 input missing: {path}")


def build_alignment(
    *,
    repo_root: Path,
    alignment_output_path: Path,
    factor_output_path: Path,
) -> AlignmentBuildResult:
    _ = repo_root
    _ensure_required_inputs()
    snapshot_utc = _utc_now_iso()

    market_facts_df = _read_csv_required(MARKET_FACTS_PATH)
    action_outcomes_df = _read_csv_required(ACTION_OUTCOMES_PATH)
    scrape_gap_df = _read_csv_required(SCRAPE_GAP_PATH)
    perf_df = _read_csv_required(SKU_PERFORMANCE_PATH)
    identity_df = _read_csv_required(IDENTITY_PATH)
    assumption_df = _read_csv_required(ASSUMPTION_PATH)
    sales_validation_df = _read_csv_required(F_SALES_VALIDATION_PATH)
    calibration_df = _read_csv_required(F_CALIBRATION_PATH)
    full_capture_facts_df = _read_csv_optional(F_FULL_CAPTURE_FACTS_PATH)

    (
        expected_units_by_sku_asin,
        expected_profit_by_sku_asin,
        expected_units_by_asin,
        expected_profit_by_asin,
        expected_units_by_asin_from_full_capture,
        expected_profit_by_asin_from_full_capture,
    ) = _build_expected_maps(
        identity_df=identity_df,
        assumption_df=assumption_df,
        sales_validation_df=sales_validation_df,
        calibration_df=calibration_df,
        full_capture_facts_df=full_capture_facts_df,
    )
    actual_units_by_sku, actual_profit_by_sku = _build_actual_maps(perf_df)

    (
        alignment_df,
        factor_df,
        rescrape_trigger_flag,
        rescrape_reason,
        missing_rate,
        thin_rate,
        stale_rate,
    ) = _build_alignment(
        market_facts_df=market_facts_df,
        action_outcomes_df=action_outcomes_df,
        scrape_gap_df=scrape_gap_df,
        expected_units_by_sku_asin=expected_units_by_sku_asin,
        expected_profit_by_sku_asin=expected_profit_by_sku_asin,
        expected_units_by_asin=expected_units_by_asin,
        expected_profit_by_asin=expected_profit_by_asin,
        expected_units_by_asin_from_full_capture=expected_units_by_asin_from_full_capture,
        expected_profit_by_asin_from_full_capture=expected_profit_by_asin_from_full_capture,
        actual_units_by_sku=actual_units_by_sku,
        actual_profit_by_sku=actual_profit_by_sku,
        snapshot_utc=snapshot_utc,
    )

    alignment_output_path.parent.mkdir(parents=True, exist_ok=True)
    factor_output_path.parent.mkdir(parents=True, exist_ok=True)
    alignment_df.to_csv(alignment_output_path, index=False)
    factor_df.to_csv(factor_output_path, index=False)

    return AlignmentBuildResult(
        alignment_output_path=alignment_output_path,
        alignment_rows=int(len(alignment_df.index)),
        factor_output_path=factor_output_path,
        factor_rows=int(len(factor_df.index)),
        rescrape_missing_rate=missing_rate,
        rescrape_thin_rate=thin_rate,
        rescrape_stale_rate=stale_rate,
        rescrape_trigger_flag=rescrape_trigger_flag,
        rescrape_trigger_reason=rescrape_reason,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build HF 30-day alignment and factor impact outputs (Batch 002).")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root")
    parser.add_argument(
        "--alignment-output",
        default=str(ALIGNMENT_OUTPUT_PATH),
        help="Output CSV path for alignment 30d output",
    )
    parser.add_argument(
        "--factor-output",
        default=str(FACTOR_OUTPUT_PATH),
        help="Output CSV path for factor impact output",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_alignment(
        repo_root=Path(args.repo_root),
        alignment_output_path=Path(args.alignment_output),
        factor_output_path=Path(args.factor_output),
    )
    print(f"alignment_output_path={result.alignment_output_path}")
    print(f"alignment_rows={result.alignment_rows}")
    print(f"factor_output_path={result.factor_output_path}")
    print(f"factor_rows={result.factor_rows}")
    print(f"rescrape_missing_rate={result.rescrape_missing_rate:.4f}")
    print(f"rescrape_thin_rate={result.rescrape_thin_rate:.4f}")
    print(f"rescrape_stale_rate={result.rescrape_stale_rate:.4f}")
    print(f"rescrape_trigger_flag={int(result.rescrape_trigger_flag)}")
    print(f"rescrape_trigger_reason={result.rescrape_trigger_reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
