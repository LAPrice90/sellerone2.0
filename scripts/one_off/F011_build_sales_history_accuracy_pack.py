from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

# Backward-compatible defaults retained for callers that still pass these paths.
DEFAULT_CALIBRATION_PATH = ROOT / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv"
DEFAULT_OPERATOR_CHECKS_PATH = ROOT / "out" / "analysis_reports" / "f_operator_sales_checks_latest.csv"

DEFAULT_SOLD_TRUTH_PATH = ROOT / "out" / "analysis_reports" / "f_sales_history_learning_actuals_latest.csv"
DEFAULT_SUMMARY_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
DEFAULT_ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
DEFAULT_REPLAY_PATH = ROOT / "out" / "analysis_reports" / "f_sold_decision_replay_latest.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_DECISION_PROFIT_FLOOR_GBP = 20.0


@dataclass(frozen=True)
class SalesHistoryAccuracyPackResult:
    accuracy_df: pd.DataFrame
    summary_df: pd.DataFrame
    template_df: pd.DataFrame
    queue_df: pd.DataFrame
    accuracy_path: Path
    accuracy_latest_path: Path
    summary_path: Path
    summary_latest_path: Path
    template_path: Path
    template_latest_path: Path
    queue_path: Path
    queue_latest_path: Path


ACCURACY_COLUMNS = [
    "observed_utc",
    "seller_sku",
    "asin",
    "amazon_link",
    "sold_truth_observed_utc",
    "sold_truth_basis",
    "actuals_source_state_30d",
    "actuals_source_state_60d",
    "actuals_source_state_90d",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "actual_units_60d",
    "actual_profit_60d_gbp",
    "actual_units_90d",
    "actual_profit_90d_gbp",
    "model_snapshot_utc",
    "model_source",
    "model_decision_state",
    "model_decision_confidence",
    "model_expected_units_next_30d",
    "model_expected_profit_next_30d_gbp",
    "model_minimum_expected_profit_gbp",
    "estimated_demand",
    "recommended_test_qty",
    "recommendation_status",
    "commercial_guidance_source",
    "model_side_evidence_state",
    "truth_decision_profit_floor_gbp",
    "truth_decision_state",
    "decision_alignment_state",
    "demand_alignment_state",
    "demand_error_units_30d",
    "demand_error_ratio_30d",
    "profit_alignment_state",
    "profit_error_gbp_30d",
    "profit_error_ratio_30d",
    "judged_accuracy_flag",
    "decision_judged_flag",
    "mismatch_flag",
    "accuracy_bucket_codes",
]

TEMPLATE_COLUMNS = [
    "seller_sku",
    "asin",
    "amazon_link",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "model_decision_state",
    "model_expected_units_next_30d",
    "model_expected_profit_next_30d_gbp",
    "estimated_demand",
    "recommended_test_qty",
    "recommendation_status",
    "model_side_evidence_state",
    "truth_decision_state",
    "accuracy_bucket_codes",
]

QUEUE_COLUMNS = [
    "observed_utc",
    "asin",
    "seller_sku",
    "amazon_link",
    "capture_reason",
    "current_model_side_evidence_state",
]


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


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    cleaned = (
        raw.replace(",", "")
        .replace("GBP", "")
        .replace("gbp", "")
        .replace("PS", "")
        .replace("ps", "")
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def _num_to_text(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _amazon_link(asin: str) -> str:
    asin_key = _normalize_text(asin)
    if asin_key == "":
        return ""
    return f"https://www.amazon.co.uk/dp/{asin_key}"


def _parse_decision_state(value: object) -> str:
    token = _normalize_text(value).lower().replace(" ", "_")
    if token in {"pass", "fail", "manual_review"}:
        return token
    if token in {"manual", "manualreview", "review"}:
        return "manual_review"
    return ""


def _split_codes(value: object) -> list[str]:
    raw = _normalize_text(value)
    if raw == "":
        return []
    return [token for token in raw.split("|") if _normalize_text(token) != ""]


def _latest_by_asin(
    df: pd.DataFrame,
    *,
    asin_col: str,
    timestamp_candidates: tuple[str, ...],
) -> dict[str, dict[str, str]]:
    if df.empty or asin_col not in df.columns:
        return {}
    work = df.copy()
    work["_asin"] = work.get(asin_col, "").map(_normalize_key)
    work = work[work["_asin"] != ""].copy()
    if work.empty:
        return {}

    ts_col = ""
    for candidate in timestamp_candidates:
        if candidate in work.columns:
            ts_col = candidate
            break
    if ts_col != "":
        work["_ts"] = pd.to_datetime(work.get(ts_col, "").map(_normalize_text), errors="coerce", utc=True)
        work = work.sort_values("_ts", ascending=False, kind="stable")

    out: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        asin = _normalize_key(row.get(asin_col, ""))
        if asin in out:
            continue
        out[asin] = {column: _normalize_text(value) for column, value in row.to_dict().items()}
    return out


def _sold_truth_rows(actuals_df: pd.DataFrame) -> pd.DataFrame:
    if actuals_df.empty:
        return pd.DataFrame()

    work = actuals_df.copy()
    work["asin"] = work.get("asin", "").map(_normalize_key)
    work["seller_sku"] = work.get("seller_sku", "").map(_normalize_text)
    work["actuals_basis"] = work.get("actuals_basis", "").map(_normalize_text).str.lower()
    work = work[(work["asin"] != "") & (work["actuals_basis"] == "operational_baseline")].copy()
    if work.empty:
        return pd.DataFrame()

    for window in ("30", "60", "90"):
        work[f"_actual_units_{window}d_num"] = pd.to_numeric(
            work.get(f"actual_units_{window}d", "").map(_normalize_text),
            errors="coerce",
        ).fillna(0.0)
        work[f"_actual_profit_{window}d_num"] = pd.to_numeric(
            work.get(f"actual_profit_{window}d_gbp", "").map(_normalize_text),
            errors="coerce",
        ).fillna(0.0)

    work["_sold_in_last_90d"] = (
        (work["_actual_units_30d_num"] > 0)
        | (work["_actual_units_60d_num"] > 0)
        | (work["_actual_units_90d_num"] > 0)
    )
    work = work[work["_sold_in_last_90d"]].copy()
    if work.empty:
        return pd.DataFrame()

    ts_col = ""
    for candidate in ("actuals_observed_utc", "decision_snapshot_utc", "observed_utc"):
        if candidate in work.columns:
            ts_col = candidate
            break
    if ts_col != "":
        work["_ts"] = pd.to_datetime(work.get(ts_col, "").map(_normalize_text), errors="coerce", utc=True)
        work = work.sort_values("_ts", ascending=False, kind="stable")

    work = work.drop_duplicates(subset=["asin"], keep="first")
    return work.reset_index(drop=True)


def _truth_decision_state(
    *,
    actual_units_30d: float | None,
    actual_profit_30d: float | None,
    decision_profit_floor_gbp: float,
) -> str:
    if actual_units_30d is None and actual_profit_30d is None:
        return ""
    if actual_units_30d is not None and actual_units_30d <= 0:
        return "fail"
    if actual_profit_30d is None:
        return ""
    if actual_profit_30d >= decision_profit_floor_gbp:
        return "pass"
    return "fail"


def _error_alignment_state(
    *,
    expected_value: float | None,
    actual_value: float | None,
) -> tuple[str, float | None, float | None]:
    if expected_value is None:
        return "missing_model_estimate", None, None
    if actual_value is None:
        return "missing_actual_value", None, None

    delta = expected_value - actual_value
    ratio = abs(delta) / max(abs(actual_value), 1.0)

    if ratio <= 0.2:
        return "aligned", delta, ratio

    severity = "moderate" if ratio <= 0.5 else "severe"
    direction = "overestimate" if delta > 0 else "underestimate"
    return f"{severity}_model_{direction}", delta, ratio


def _decision_alignment_state(*, model_decision: str, truth_decision: str) -> str:
    if truth_decision == "":
        return "missing_truth_decision"
    if model_decision == "":
        return "missing_model_decision"
    if model_decision == truth_decision:
        return "aligned"
    return "mismatch"


def _model_side_evidence_state(*, has_model_estimate: bool, has_model_decision: bool) -> str:
    if has_model_estimate and has_model_decision:
        return "full_decision_and_estimate"
    if has_model_estimate:
        return "estimate_only"
    if has_model_decision:
        return "decision_only"
    return "missing"


def _bucket_codes(
    *,
    model_side_state: str,
    decision_alignment_state: str,
    model_decision: str,
    truth_decision: str,
    demand_alignment_state: str,
    profit_alignment_state: str,
) -> list[str]:
    codes: list[str] = []

    if model_side_state == "missing":
        codes.append("missing_model_side_evidence")
    if model_side_state in {"missing", "decision_only"}:
        codes.append("missing_model_estimate")
    if model_side_state in {"missing", "estimate_only"}:
        codes.append("missing_model_decision")

    if decision_alignment_state == "mismatch":
        codes.append("decision_mismatch")
        if model_decision == "pass" and truth_decision == "fail":
            codes.append("model_false_pass")
        elif model_decision == "fail" and truth_decision == "pass":
            codes.append("model_false_fail")
        else:
            codes.append("model_decision_mismatch_other")

    if "overestimate" in demand_alignment_state:
        codes.append("demand_overestimate")
        if demand_alignment_state.startswith("severe_"):
            codes.append("demand_overestimate_severe")
    elif "underestimate" in demand_alignment_state:
        codes.append("demand_underestimate")
        if demand_alignment_state.startswith("severe_"):
            codes.append("demand_underestimate_severe")

    if "overestimate" in profit_alignment_state:
        codes.append("profit_overestimate")
        if profit_alignment_state.startswith("severe_"):
            codes.append("profit_overestimate_severe")
    elif "underestimate" in profit_alignment_state:
        codes.append("profit_underestimate")
        if profit_alignment_state.startswith("severe_"):
            codes.append("profit_underestimate_severe")

    if not codes:
        codes.append("accuracy_aligned")

    deduped: list[str] = []
    seen: set[str] = set()
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        deduped.append(code)
    return deduped


def _mismatch_flag(bucket_codes: list[str]) -> str:
    mismatch_codes = {
        "model_false_pass",
        "model_false_fail",
        "demand_overestimate",
        "demand_underestimate",
        "profit_overestimate",
        "profit_underestimate",
    }
    for code in bucket_codes:
        if code in mismatch_codes:
            return "1"
    return "0"


def _metric_value(summary_df: pd.DataFrame, metric: str) -> str:
    if summary_df.empty:
        return ""
    rows = summary_df.loc[summary_df["metric"].map(_normalize_text) == metric]
    if rows.empty:
        return ""
    return _normalize_text(rows.iloc[0].get("value", ""))


def build_sales_history_accuracy_pack(
    *,
    sold_truth_path: Path = DEFAULT_SOLD_TRUTH_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    alignment_path: Path = DEFAULT_ALIGNMENT_PATH,
    replay_path: Path = DEFAULT_REPLAY_PATH,
    calibration_path: Path = DEFAULT_CALIBRATION_PATH,
    operator_checks_path: Path = DEFAULT_OPERATOR_CHECKS_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    decision_profit_floor_gbp: float = DEFAULT_DECISION_PROFIT_FLOOR_GBP,
    observed_utc: str | None = None,
) -> SalesHistoryAccuracyPackResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    sold_truth_df = _read_csv(sold_truth_path)
    summary_df = _read_csv(summary_path)
    alignment_df = _read_csv(alignment_path)
    replay_df = _read_csv(replay_path)

    # Retained for backward compatibility and side-context metrics.
    calibration_df = _read_csv(calibration_path)
    _ = _read_csv(operator_checks_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)
    accuracy_path = output_dir / f"f_sales_history_accuracy_pack_{ts_slug}.csv"
    accuracy_latest_path = output_dir / "f_sales_history_accuracy_pack_latest.csv"
    summary_out_path = output_dir / f"f_sales_history_accuracy_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "f_sales_history_accuracy_summary_latest.csv"
    template_path = output_dir / f"f_operator_sales_checks_template_{ts_slug}.csv"
    template_latest_path = output_dir / "f_operator_sales_checks_template_latest.csv"
    queue_path = output_dir / f"f_sold_truth_replay_capture_queue_{ts_slug}.csv"
    queue_latest_path = output_dir / "f_sold_truth_replay_capture_queue_latest.csv"

    sold_rows_df = _sold_truth_rows(sold_truth_df)
    replay_by_asin = _latest_by_asin(
        replay_df,
        asin_col="asin",
        timestamp_candidates=("observed_utc", "model_snapshot_utc"),
    )
    summary_by_asin = _latest_by_asin(
        summary_df,
        asin_col="asin",
        timestamp_candidates=("observed_utc",),
    )
    alignment_by_asin = _latest_by_asin(
        alignment_df,
        asin_col="asin",
        timestamp_candidates=("alignment_window_end_utc", "observed_utc"),
    )

    rows: list[dict[str, str]] = []
    template_rows: list[dict[str, str]] = []
    queue_rows: list[dict[str, str]] = []
    sold_asin_set: set[str] = set()
    sold_decision_replay_coverage_rows = 0
    rows_with_demand_bucket = 0
    rows_with_recommended_test_qty = 0
    rows_with_recommendation_status = 0

    for _, truth_row in sold_rows_df.iterrows():
        asin = _normalize_key(truth_row.get("asin", ""))
        if asin == "":
            continue
        sold_asin_set.add(asin)
        seller_sku = _normalize_text(truth_row.get("seller_sku", ""))

        replay_row = replay_by_asin.get(asin, {})
        summary_row = summary_by_asin.get(asin, {})
        alignment_row = alignment_by_asin.get(asin, {})
        replay_decision = _parse_decision_state(replay_row.get("model_decision_state", ""))
        summary_decision = _parse_decision_state(summary_row.get("decision_state", ""))
        model_decision = replay_decision or summary_decision

        replay_confidence = _normalize_text(replay_row.get("model_decision_confidence", "")).lower()
        summary_confidence = _normalize_text(summary_row.get("decision_confidence", "")).lower()
        model_confidence = replay_confidence or summary_confidence

        replay_units = _num_or_none(replay_row.get("model_expected_units_next_30d", ""))
        summary_units = _num_or_none(summary_row.get("expected_units_next_30d", ""))
        alignment_units = _num_or_none(alignment_row.get("expected_units_30d", ""))
        model_units = None
        estimate_units_source = "missing"
        if replay_units is not None:
            model_units = replay_units
            estimate_units_source = "replay_bridge"
        elif summary_units is not None:
            model_units = summary_units
            estimate_units_source = "summary_live"
        elif alignment_units is not None:
            model_units = alignment_units
            estimate_units_source = "alignment_fill"

        replay_profit = _num_or_none(replay_row.get("model_expected_profit_next_30d_gbp", ""))
        summary_profit = _num_or_none(summary_row.get("expected_profit_next_30d_gbp", ""))
        alignment_profit = _num_or_none(alignment_row.get("expected_profit_30d_gbp", ""))
        model_profit = None
        estimate_profit_source = "missing"
        if replay_profit is not None:
            model_profit = replay_profit
            estimate_profit_source = "replay_bridge"
        elif summary_profit is not None:
            model_profit = summary_profit
            estimate_profit_source = "summary_live"
        elif alignment_profit is not None:
            model_profit = alignment_profit
            estimate_profit_source = "alignment_fill"

        replay_floor = _num_or_none(replay_row.get("model_minimum_expected_profit_gbp", ""))
        summary_floor = _num_or_none(summary_row.get("minimum_expected_profit_gbp", ""))
        model_floor = replay_floor if replay_floor is not None else summary_floor
        if model_floor is None:
            model_floor = decision_profit_floor_gbp

        decision_source = "missing"
        if replay_decision != "":
            decision_source = "replay_bridge"
            sold_decision_replay_coverage_rows += 1
        elif summary_decision != "":
            decision_source = "summary_live"

        replay_model_source = _normalize_text(replay_row.get("model_source", ""))
        if replay_model_source != "":
            model_source = replay_model_source
        elif decision_source == "replay_bridge" and (
            "alignment_fill" in {estimate_units_source, estimate_profit_source}
            or "summary_live" in {estimate_units_source, estimate_profit_source}
        ):
            model_source = "replay_bridge_with_fill"
        elif decision_source == "replay_bridge" or (
            "replay_bridge" in {estimate_units_source, estimate_profit_source}
        ):
            model_source = "replay_bridge"
        elif decision_source == "summary_live" and (
            "alignment_fill" in {estimate_units_source, estimate_profit_source}
        ):
            model_source = "summary_plus_alignment_fill"
        elif decision_source == "summary_live" or (
            "summary_live" in {estimate_units_source, estimate_profit_source}
        ):
            model_source = "summary_live"
        elif "alignment_fill" in {estimate_units_source, estimate_profit_source}:
            model_source = "alignment_only"
        else:
            model_source = "missing"

        estimated_demand = _normalize_text(replay_row.get("estimated_demand", "")).lower()
        recommended_test_qty = _normalize_text(replay_row.get("recommended_test_qty", ""))
        recommendation_status = _normalize_text(replay_row.get("recommendation_status", "")).lower()
        commercial_guidance_source = _normalize_text(replay_row.get("commercial_guidance_source", ""))
        if estimated_demand != "":
            rows_with_demand_bucket += 1
        if recommended_test_qty != "":
            rows_with_recommended_test_qty += 1
        if recommendation_status != "":
            rows_with_recommendation_status += 1

        has_model_estimate = model_units is not None or model_profit is not None
        has_model_decision = model_decision != ""
        model_side_state = _model_side_evidence_state(
            has_model_estimate=has_model_estimate,
            has_model_decision=has_model_decision,
        )

        actual_units_30d = _num_or_none(truth_row.get("actual_units_30d", ""))
        actual_profit_30d = _num_or_none(truth_row.get("actual_profit_30d_gbp", ""))
        actual_units_60d = _num_or_none(truth_row.get("actual_units_60d", ""))
        actual_profit_60d = _num_or_none(truth_row.get("actual_profit_60d_gbp", ""))
        actual_units_90d = _num_or_none(truth_row.get("actual_units_90d", ""))
        actual_profit_90d = _num_or_none(truth_row.get("actual_profit_90d_gbp", ""))

        truth_decision = _truth_decision_state(
            actual_units_30d=actual_units_30d,
            actual_profit_30d=actual_profit_30d,
            decision_profit_floor_gbp=decision_profit_floor_gbp,
        )
        decision_alignment = _decision_alignment_state(
            model_decision=model_decision,
            truth_decision=truth_decision,
        )

        demand_alignment, demand_delta, demand_ratio = _error_alignment_state(
            expected_value=model_units,
            actual_value=actual_units_30d,
        )
        profit_alignment, profit_delta, profit_ratio = _error_alignment_state(
            expected_value=model_profit,
            actual_value=actual_profit_30d,
        )

        buckets = _bucket_codes(
            model_side_state=model_side_state,
            decision_alignment_state=decision_alignment,
            model_decision=model_decision,
            truth_decision=truth_decision,
            demand_alignment_state=demand_alignment,
            profit_alignment_state=profit_alignment,
        )
        mismatch_flag = _mismatch_flag(buckets)
        judged_accuracy_flag = "1" if has_model_estimate and actual_units_30d is not None else "0"
        decision_judged_flag = "1" if has_model_decision and truth_decision != "" else "0"

        accuracy_row = {
            "observed_utc": snapshot_utc,
            "seller_sku": seller_sku,
            "asin": asin,
            "amazon_link": _amazon_link(asin),
            "sold_truth_observed_utc": _normalize_text(
                truth_row.get("actuals_observed_utc", truth_row.get("decision_snapshot_utc", ""))
            ),
            "sold_truth_basis": "operational_baseline",
            "actuals_source_state_30d": _normalize_text(truth_row.get("actuals_source_state_30d", "")),
            "actuals_source_state_60d": _normalize_text(truth_row.get("actuals_source_state_60d", "")),
            "actuals_source_state_90d": _normalize_text(truth_row.get("actuals_source_state_90d", "")),
            "actual_units_30d": _num_to_text(actual_units_30d),
            "actual_profit_30d_gbp": _num_to_text(actual_profit_30d),
            "actual_units_60d": _num_to_text(actual_units_60d),
            "actual_profit_60d_gbp": _num_to_text(actual_profit_60d),
            "actual_units_90d": _num_to_text(actual_units_90d),
            "actual_profit_90d_gbp": _num_to_text(actual_profit_90d),
            "model_snapshot_utc": _normalize_text(
                replay_row.get(
                    "model_snapshot_utc",
                    replay_row.get(
                        "observed_utc",
                        summary_row.get("observed_utc", alignment_row.get("alignment_window_end_utc", "")),
                    ),
                )
            ),
            "model_source": model_source,
            "model_decision_state": model_decision,
            "model_decision_confidence": model_confidence,
            "model_expected_units_next_30d": _num_to_text(model_units),
            "model_expected_profit_next_30d_gbp": _num_to_text(model_profit),
            "model_minimum_expected_profit_gbp": _num_to_text(model_floor),
            "estimated_demand": estimated_demand,
            "recommended_test_qty": recommended_test_qty,
            "recommendation_status": recommendation_status,
            "commercial_guidance_source": commercial_guidance_source,
            "model_side_evidence_state": model_side_state,
            "truth_decision_profit_floor_gbp": _num_to_text(decision_profit_floor_gbp),
            "truth_decision_state": truth_decision,
            "decision_alignment_state": decision_alignment,
            "demand_alignment_state": demand_alignment,
            "demand_error_units_30d": _num_to_text(demand_delta),
            "demand_error_ratio_30d": _num_to_text(demand_ratio),
            "profit_alignment_state": profit_alignment,
            "profit_error_gbp_30d": _num_to_text(profit_delta),
            "profit_error_ratio_30d": _num_to_text(profit_ratio),
            "judged_accuracy_flag": judged_accuracy_flag,
            "decision_judged_flag": decision_judged_flag,
            "mismatch_flag": mismatch_flag,
            "accuracy_bucket_codes": "|".join(buckets),
        }
        rows.append({column: _normalize_text(accuracy_row.get(column, "")) for column in ACCURACY_COLUMNS})
        template_rows.append({column: _normalize_text(accuracy_row.get(column, "")) for column in TEMPLATE_COLUMNS})
        if model_side_state == "missing":
            queue_rows.append(
                {
                    "observed_utc": snapshot_utc,
                    "asin": asin,
                    "seller_sku": seller_sku,
                    "amazon_link": _amazon_link(asin),
                    "capture_reason": "missing_model_side_evidence_for_sold_truth_row",
                    "current_model_side_evidence_state": model_side_state,
                }
            )

    accuracy_df = pd.DataFrame(rows, columns=ACCURACY_COLUMNS)
    if not accuracy_df.empty:
        accuracy_df = accuracy_df.sort_values(
            by=["asin", "seller_sku"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

    template_df = pd.DataFrame(template_rows, columns=TEMPLATE_COLUMNS)
    if not template_df.empty:
        template_df = template_df.sort_values(
            by=["asin", "seller_sku"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

    queue_df = pd.DataFrame(queue_rows, columns=QUEUE_COLUMNS)
    if not queue_df.empty:
        queue_df = queue_df.sort_values(
            by=["asin", "seller_sku"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

    bucket_counts: dict[str, int] = {}
    for raw_codes in accuracy_df.get("accuracy_bucket_codes", pd.Series([], dtype=str)).map(_normalize_text).tolist():
        for code in _split_codes(raw_codes):
            bucket_counts[code] = int(bucket_counts.get(code, 0)) + 1

    model_side_counts: dict[str, int] = {}
    for state in accuracy_df.get("model_side_evidence_state", pd.Series([], dtype=str)).map(_normalize_text).tolist():
        if state == "":
            continue
        model_side_counts[state] = int(model_side_counts.get(state, 0)) + 1

    summary_asin_set = {
        _normalize_key(value)
        for value in summary_df.get("asin", pd.Series([], dtype=str)).map(_normalize_text).tolist()
        if _normalize_key(value) != ""
    }
    model_rows_missing_sold_truth = max(len(summary_asin_set - sold_asin_set), 0)

    calibration_asin_set = {
        _normalize_key(value)
        for value in calibration_df.get("asin", pd.Series([], dtype=str)).map(_normalize_text).tolist()
        if _normalize_key(value) != ""
    }
    calibration_rows_missing_sold_truth = max(len(calibration_asin_set - sold_asin_set), 0)

    summary_rows = [
        {"observed_utc": snapshot_utc, "metric": "sold_rows_total", "value": str(int(len(accuracy_df.index)))},
        {
            "observed_utc": snapshot_utc,
            "metric": "sold_rows_with_model_side_evidence",
            "value": str(
                int(
                    (
                        accuracy_df.get("model_side_evidence_state", pd.Series([], dtype=str))
                        .map(_normalize_text)
                        != "missing"
                    ).sum()
                )
            ),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "sold_rows_with_full_model_evidence",
            "value": str(
                int(
                    (
                        accuracy_df.get("model_side_evidence_state", pd.Series([], dtype=str))
                        .map(_normalize_text)
                        == "full_decision_and_estimate"
                    ).sum()
                )
            ),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "sold_rows_missing_model_side_evidence",
            "value": str(
                int(
                    (
                        accuracy_df.get("model_side_evidence_state", pd.Series([], dtype=str))
                        .map(_normalize_text)
                        == "missing"
                    ).sum()
                )
            ),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "sold_truth_replay_queue_rows",
            "value": str(int(len(queue_df.index))),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "judged_accuracy_rows",
            "value": str(
                int((accuracy_df.get("judged_accuracy_flag", pd.Series([], dtype=str)).map(_normalize_text) == "1").sum())
            ),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "decision_judged_rows",
            "value": str(
                int((accuracy_df.get("decision_judged_flag", pd.Series([], dtype=str)).map(_normalize_text) == "1").sum())
            ),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "sold_decision_replay_coverage_rows",
            "value": str(int(sold_decision_replay_coverage_rows)),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "rows_with_demand_bucket",
            "value": str(int(rows_with_demand_bucket)),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "rows_with_recommended_test_qty",
            "value": str(int(rows_with_recommended_test_qty)),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "rows_with_recommendation_status",
            "value": str(int(rows_with_recommendation_status)),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "rows_missing_sold_truth",
            "value": "0",
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "model_universe_rows_missing_sold_truth",
            "value": str(model_rows_missing_sold_truth),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "calibration_rows_missing_sold_truth",
            "value": str(calibration_rows_missing_sold_truth),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "false_pass_rows",
            "value": str(int(bucket_counts.get("model_false_pass", 0))),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "false_fail_rows",
            "value": str(int(bucket_counts.get("model_false_fail", 0))),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "bucket::missing_model_decision",
            "value": str(int(bucket_counts.get("missing_model_decision", 0))),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "demand_overestimate_rows",
            "value": str(int(bucket_counts.get("demand_overestimate", 0))),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "demand_underestimate_rows",
            "value": str(int(bucket_counts.get("demand_underestimate", 0))),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "profit_overestimate_rows",
            "value": str(int(bucket_counts.get("profit_overestimate", 0))),
        },
        {
            "observed_utc": snapshot_utc,
            "metric": "profit_underestimate_rows",
            "value": str(int(bucket_counts.get("profit_underestimate", 0))),
        },
    ]

    for state, count in sorted(model_side_counts.items()):
        summary_rows.append(
            {
                "observed_utc": snapshot_utc,
                "metric": f"model_evidence_state::{state}",
                "value": str(int(count)),
            }
        )

    explicit_bucket_metrics = {"missing_model_decision"}
    for bucket, count in sorted(bucket_counts.items()):
        if bucket in explicit_bucket_metrics:
            continue
        summary_rows.append(
            {
                "observed_utc": snapshot_utc,
                "metric": f"bucket::{bucket}",
                "value": str(int(count)),
            }
        )

    top_buckets = sorted(bucket_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    for idx, (bucket, count) in enumerate(top_buckets, start=1):
        summary_rows.append(
            {
                "observed_utc": snapshot_utc,
                "metric": f"top_bucket_{idx}",
                "value": f"{bucket}:{count}",
            }
        )

    summary_out_df = pd.DataFrame(summary_rows, columns=["observed_utc", "metric", "value"])

    accuracy_df.to_csv(accuracy_path, index=False)
    accuracy_df.to_csv(accuracy_latest_path, index=False)
    summary_out_df.to_csv(summary_out_path, index=False)
    summary_out_df.to_csv(summary_latest_path, index=False)
    template_df.to_csv(template_path, index=False)
    template_df.to_csv(template_latest_path, index=False)
    queue_df.to_csv(queue_path, index=False)
    queue_df.to_csv(queue_latest_path, index=False)

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "sold_rows_total": int(len(accuracy_df.index)),
                "sold_rows_with_model_side_evidence": int(
                    _num_or_none(_metric_value(summary_out_df, "sold_rows_with_model_side_evidence")) or 0
                ),
                "sold_rows_missing_model_side_evidence": int(
                    _num_or_none(_metric_value(summary_out_df, "sold_rows_missing_model_side_evidence")) or 0
                ),
                "sold_truth_replay_queue_rows": int(
                    _num_or_none(_metric_value(summary_out_df, "sold_truth_replay_queue_rows")) or 0
                ),
                "judged_accuracy_rows": int(_num_or_none(_metric_value(summary_out_df, "judged_accuracy_rows")) or 0),
                "decision_judged_rows": int(_num_or_none(_metric_value(summary_out_df, "decision_judged_rows")) or 0),
                "sold_decision_replay_coverage_rows": int(
                    _num_or_none(_metric_value(summary_out_df, "sold_decision_replay_coverage_rows")) or 0
                ),
                "rows_with_demand_bucket": int(
                    _num_or_none(_metric_value(summary_out_df, "rows_with_demand_bucket")) or 0
                ),
                "rows_with_recommended_test_qty": int(
                    _num_or_none(_metric_value(summary_out_df, "rows_with_recommended_test_qty")) or 0
                ),
                "rows_with_recommendation_status": int(
                    _num_or_none(_metric_value(summary_out_df, "rows_with_recommendation_status")) or 0
                ),
                "false_pass_rows": int(_num_or_none(_metric_value(summary_out_df, "false_pass_rows")) or 0),
                "false_fail_rows": int(_num_or_none(_metric_value(summary_out_df, "false_fail_rows")) or 0),
                "demand_overestimate_rows": int(_num_or_none(_metric_value(summary_out_df, "demand_overestimate_rows")) or 0),
                "demand_underestimate_rows": int(_num_or_none(_metric_value(summary_out_df, "demand_underestimate_rows")) or 0),
                "profit_overestimate_rows": int(_num_or_none(_metric_value(summary_out_df, "profit_overestimate_rows")) or 0),
                "profit_underestimate_rows": int(_num_or_none(_metric_value(summary_out_df, "profit_underestimate_rows")) or 0),
                "accuracy_csv_output": str(accuracy_path),
                "accuracy_latest_csv": str(accuracy_latest_path),
                "summary_csv_output": str(summary_out_path),
                "summary_latest_csv": str(summary_latest_path),
                "template_csv_output": str(template_path),
                "template_latest_csv": str(template_latest_path),
                "queue_csv_output": str(queue_path),
                "queue_latest_csv": str(queue_latest_path),
            }
        )
    )

    return SalesHistoryAccuracyPackResult(
        accuracy_df=accuracy_df,
        summary_df=summary_out_df,
        template_df=template_df,
        queue_df=queue_df,
        accuracy_path=accuracy_path,
        accuracy_latest_path=accuracy_latest_path,
        summary_path=summary_out_path,
        summary_latest_path=summary_latest_path,
        template_path=template_path,
        template_latest_path=template_latest_path,
        queue_path=queue_path,
        queue_latest_path=queue_latest_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build sold-product truth-first sales-history accuracy pack using B/E actuals and best-available model evidence."
        )
    )
    parser.add_argument("--sold-truth-path", default=str(DEFAULT_SOLD_TRUTH_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--alignment-path", default=str(DEFAULT_ALIGNMENT_PATH))
    parser.add_argument("--replay-path", default=str(DEFAULT_REPLAY_PATH))
    parser.add_argument("--calibration-path", default=str(DEFAULT_CALIBRATION_PATH))
    parser.add_argument("--operator-checks-path", default=str(DEFAULT_OPERATOR_CHECKS_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--decision-profit-floor-gbp",
        default=str(DEFAULT_DECISION_PROFIT_FLOOR_GBP),
        help="Profit floor used for truth pass/fail decision.",
    )
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_sales_history_accuracy_pack(
        sold_truth_path=Path(args.sold_truth_path),
        summary_path=Path(args.summary_path),
        alignment_path=Path(args.alignment_path),
        replay_path=Path(args.replay_path),
        calibration_path=Path(args.calibration_path),
        operator_checks_path=Path(args.operator_checks_path),
        output_dir=Path(args.output_dir),
        decision_profit_floor_gbp=float(args.decision_profit_floor_gbp),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
