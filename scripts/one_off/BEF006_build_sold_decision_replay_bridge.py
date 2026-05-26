from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_SOLD_TRUTH_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_actuals_latest.csv"
DEFAULT_REVIEW_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_review_latest.csv"
DEFAULT_SUMMARY_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
DEFAULT_ALIGNMENT_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_alignment_30d_latest.csv"
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f_sold_decision_replay_latest.csv"
DEFAULT_SUMMARY_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "f_sold_decision_replay_summary_latest.csv"
DEFAULT_DECISION_PROFIT_FLOOR_GBP = 20.0


REPLAY_COLUMNS = [
    "observed_utc",
    "asin",
    "sold_seller_sku",
    "model_seller_sku",
    "model_snapshot_utc",
    "model_source",
    "replay_basis",
    "decision_source",
    "estimate_units_source",
    "estimate_profit_source",
    "model_decision_state",
    "model_decision_confidence",
    "model_expected_units_next_30d",
    "model_expected_profit_next_30d_gbp",
    "model_minimum_expected_profit_gbp",
    "estimated_demand",
    "recommended_test_qty",
    "recommendation_status",
    "commercial_guidance_source",
]


@dataclass(frozen=True)
class SoldDecisionReplayBridgeResult:
    replay_df: pd.DataFrame
    summary_df: pd.DataFrame
    replay_path: Path
    replay_latest_path: Path
    summary_path: Path
    summary_latest_path: Path


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


def _parse_decision_state(value: object) -> str:
    token = _normalize_text(value).lower().replace(" ", "_")
    if token in {"pass", "fail", "manual_review"}:
        return token
    if token in {"manual", "manualreview", "review"}:
        return "manual_review"
    return ""


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


def _demand_bucket_from_units(expected_units: float | None) -> str:
    if expected_units is None:
        return ""
    if expected_units >= 8:
        return "high"
    if expected_units >= 5:
        return "medium"
    if expected_units > 0:
        return "low"
    return "low"


def _recommendation_status_from_decision(decision_state: str) -> str:
    if decision_state == "pass":
        return "approve_test_buy"
    if decision_state == "fail":
        return "reject"
    if decision_state == "manual_review":
        return "manual_review"
    return ""


def _recommended_qty(*, demand_bucket: str, recommendation_status: str) -> str:
    if recommendation_status == "approve_test_buy":
        if demand_bucket == "high":
            return "8"
        if demand_bucket == "medium":
            return "5"
        if demand_bucket == "low":
            return "3"
    if recommendation_status == "watch":
        return "1"
    return "0"


def _infer_decision_from_estimates(
    *,
    expected_units: float | None,
    expected_profit: float | None,
    decision_profit_floor_gbp: float,
) -> str:
    if expected_units is None and expected_profit is None:
        return ""
    if expected_units is not None and expected_units <= 0:
        return "fail"
    if expected_profit is None:
        return ""
    if expected_profit >= decision_profit_floor_gbp:
        return "pass"
    return "fail"


def _safe_str_count(series: pd.Series, token: str) -> int:
    return int((series.map(_normalize_text) == token).sum())


def build_sold_decision_replay_bridge(
    *,
    sold_truth_path: Path = DEFAULT_SOLD_TRUTH_PATH,
    review_path: Path = DEFAULT_REVIEW_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    alignment_path: Path = DEFAULT_ALIGNMENT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    summary_output_path: Path = DEFAULT_SUMMARY_OUTPUT_PATH,
    decision_profit_floor_gbp: float = DEFAULT_DECISION_PROFIT_FLOOR_GBP,
    observed_utc: str | None = None,
) -> SoldDecisionReplayBridgeResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)

    sold_truth_df = _read_csv(sold_truth_path)
    review_df = _read_csv(review_path)
    summary_df = _read_csv(summary_path)
    alignment_df = _read_csv(alignment_path)

    sold_rows_df = _sold_truth_rows(sold_truth_df)
    review_by_asin = _latest_by_asin(
        review_df,
        asin_col="asin",
        timestamp_candidates=("observed_utc", "decision_snapshot_utc"),
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
    for _, sold_row in sold_rows_df.iterrows():
        asin = _normalize_key(sold_row.get("asin", ""))
        if asin == "":
            continue
        sold_seller_sku = _normalize_text(sold_row.get("seller_sku", ""))

        replay_row = review_by_asin.get(asin, {})
        summary_row = summary_by_asin.get(asin, {})
        alignment_row = alignment_by_asin.get(asin, {})

        replay_decision = _parse_decision_state(replay_row.get("decision_state_at_snapshot", ""))
        summary_decision = _parse_decision_state(summary_row.get("decision_state", ""))
        replay_decision_inferred = False

        replay_confidence = _normalize_text(replay_row.get("decision_confidence_at_snapshot", "")).lower()
        summary_confidence = _normalize_text(summary_row.get("decision_confidence", "")).lower()
        model_confidence = replay_confidence or summary_confidence

        replay_units = _num_or_none(replay_row.get("expected_units_next_30d", ""))
        summary_units = _num_or_none(summary_row.get("expected_units_next_30d", ""))
        alignment_units = _num_or_none(alignment_row.get("expected_units_30d", ""))

        replay_profit = _num_or_none(replay_row.get("expected_profit_next_30d_gbp", ""))
        summary_profit = _num_or_none(summary_row.get("expected_profit_next_30d_gbp", ""))
        alignment_profit = _num_or_none(alignment_row.get("expected_profit_30d_gbp", ""))

        estimate_units_source = "missing"
        model_units = None
        if replay_units is not None:
            model_units = replay_units
            estimate_units_source = "replay_bridge"
        elif summary_units is not None:
            model_units = summary_units
            estimate_units_source = "summary_live"
        elif alignment_units is not None:
            model_units = alignment_units
            estimate_units_source = "alignment_fill"

        estimate_profit_source = "missing"
        model_profit = None
        if replay_profit is not None:
            model_profit = replay_profit
            estimate_profit_source = "replay_bridge"
        elif summary_profit is not None:
            model_profit = summary_profit
            estimate_profit_source = "summary_live"
        elif alignment_profit is not None:
            model_profit = alignment_profit
            estimate_profit_source = "alignment_fill"

        model_floor = _num_or_none(replay_row.get("model_minimum_expected_profit_gbp", ""))
        if model_floor is None:
            model_floor = _num_or_none(summary_row.get("minimum_expected_profit_gbp", ""))
        if model_floor is None:
            model_floor = decision_profit_floor_gbp

        if replay_decision == "" and bool(replay_row):
            inferred_decision = _infer_decision_from_estimates(
                expected_units=model_units,
                expected_profit=model_profit,
                decision_profit_floor_gbp=model_floor,
            )
            if inferred_decision != "":
                replay_decision = inferred_decision
                replay_decision_inferred = True
                if model_confidence == "":
                    model_confidence = "low"

        model_decision = replay_decision or summary_decision

        if replay_decision != "":
            decision_source = "replay_bridge"
        elif summary_decision != "":
            decision_source = "summary_live"
        else:
            decision_source = "missing"

        if decision_source == "replay_bridge" and (
            estimate_units_source == "replay_bridge" or estimate_profit_source == "replay_bridge"
        ):
            model_source = "replay_bridge"
            replay_basis = "sales_history_learning_review"
        elif decision_source == "replay_bridge":
            model_source = "replay_bridge_with_fill"
            replay_basis = "sales_history_learning_review_plus_fill"
        elif decision_source == "summary_live" and (
            estimate_units_source == "summary_live" or estimate_profit_source == "summary_live"
        ):
            model_source = "summary_live"
            replay_basis = "summary_live"
        elif decision_source == "summary_live":
            model_source = "summary_live_with_alignment_fill"
            replay_basis = "summary_plus_alignment_fill"
        elif estimate_units_source == "alignment_fill" or estimate_profit_source == "alignment_fill":
            model_source = "alignment_only"
            replay_basis = "alignment_only"
        else:
            model_source = "missing"
            replay_basis = "missing"

        if replay_decision_inferred and model_source.startswith("replay_bridge"):
            model_source = f"{model_source}_inferred_decision"

        source_estimated_demand = _normalize_text(replay_row.get("estimated_demand", ""))
        source_recommended_qty = _normalize_text(replay_row.get("recommended_test_qty", ""))
        source_recommendation_status = _normalize_text(replay_row.get("recommendation_status", "")).lower()
        commercial_guidance_source = "missing"

        estimated_demand = source_estimated_demand
        if estimated_demand == "":
            estimated_demand = _demand_bucket_from_units(model_units)
        if estimated_demand != "":
            commercial_guidance_source = (
                "replay_source_field" if source_estimated_demand != "" else "derived_from_model_expected_units"
            )

        recommendation_status = source_recommendation_status
        if recommendation_status == "":
            recommendation_status = _recommendation_status_from_decision(model_decision)
        if recommendation_status != "" and commercial_guidance_source == "missing":
            commercial_guidance_source = "derived_from_model_decision"

        recommended_test_qty = source_recommended_qty
        if recommended_test_qty == "":
            recommended_test_qty = _recommended_qty(
                demand_bucket=estimated_demand,
                recommendation_status=recommendation_status,
            )
        if source_recommended_qty != "":
            commercial_guidance_source = "replay_source_field"
        elif recommended_test_qty != "" and commercial_guidance_source == "missing":
            commercial_guidance_source = "derived_from_model_expected_units"

        model_snapshot_utc = _normalize_text(
            replay_row.get(
                "decision_snapshot_utc",
                summary_row.get("observed_utc", alignment_row.get("alignment_window_end_utc", "")),
            )
        )
        model_seller_sku = _normalize_text(replay_row.get("seller_sku", summary_row.get("seller_sku", "")))

        row = {
            "observed_utc": snapshot_utc,
            "asin": asin,
            "sold_seller_sku": sold_seller_sku,
            "model_seller_sku": model_seller_sku,
            "model_snapshot_utc": model_snapshot_utc,
            "model_source": model_source,
            "replay_basis": replay_basis,
            "decision_source": decision_source,
            "estimate_units_source": estimate_units_source,
            "estimate_profit_source": estimate_profit_source,
            "model_decision_state": model_decision,
            "model_decision_confidence": model_confidence,
            "model_expected_units_next_30d": _num_to_text(model_units),
            "model_expected_profit_next_30d_gbp": _num_to_text(model_profit),
            "model_minimum_expected_profit_gbp": _num_to_text(model_floor),
            "estimated_demand": estimated_demand,
            "recommended_test_qty": recommended_test_qty,
            "recommendation_status": recommendation_status,
            "commercial_guidance_source": commercial_guidance_source,
        }
        rows.append({column: _normalize_text(row.get(column, "")) for column in REPLAY_COLUMNS})

    replay_df = pd.DataFrame(rows, columns=REPLAY_COLUMNS)
    if not replay_df.empty:
        replay_df = replay_df.sort_values(
            by=["asin"],
            key=lambda s: s.map(lambda v: _normalize_text(v).upper()),
            kind="stable",
        ).reset_index(drop=True)

    sold_rows_total = int(len(replay_df.index))
    decision_series = replay_df.get("model_decision_state", pd.Series([], dtype=str)).map(_normalize_text)
    estimate_units_series = replay_df.get("model_expected_units_next_30d", pd.Series([], dtype=str)).map(_normalize_text)
    estimate_profit_series = replay_df.get("model_expected_profit_next_30d_gbp", pd.Series([], dtype=str)).map(_normalize_text)
    replay_decision_rows = _safe_str_count(replay_df.get("decision_source", pd.Series([], dtype=str)), "replay_bridge")
    summary_decision_rows = _safe_str_count(replay_df.get("decision_source", pd.Series([], dtype=str)), "summary_live")

    has_estimate_rows = int(((estimate_units_series != "") | (estimate_profit_series != "")).sum())
    full_model_rows = int(((decision_series != "") & ((estimate_units_series != "") | (estimate_profit_series != ""))).sum())
    demand_rows = int((replay_df.get("estimated_demand", pd.Series([], dtype=str)).map(_normalize_text) != "").sum())
    qty_rows = int((replay_df.get("recommended_test_qty", pd.Series([], dtype=str)).map(_normalize_text) != "").sum())
    status_rows = int((replay_df.get("recommendation_status", pd.Series([], dtype=str)).map(_normalize_text) != "").sum())

    summary_rows = [
        {"observed_utc": snapshot_utc, "metric": "sold_rows_total", "value": str(sold_rows_total)},
        {"observed_utc": snapshot_utc, "metric": "sold_decision_replay_rows", "value": str(replay_decision_rows)},
        {
            "observed_utc": snapshot_utc,
            "metric": "sold_decision_replay_coverage_rows",
            "value": str(replay_decision_rows),
        },
        {"observed_utc": snapshot_utc, "metric": "sold_summary_decision_rows", "value": str(summary_decision_rows)},
        {
            "observed_utc": snapshot_utc,
            "metric": "sold_rows_with_decision_state",
            "value": str(int((decision_series != "").sum())),
        },
        {"observed_utc": snapshot_utc, "metric": "sold_rows_with_estimate", "value": str(has_estimate_rows)},
        {"observed_utc": snapshot_utc, "metric": "sold_rows_with_full_model_evidence", "value": str(full_model_rows)},
        {"observed_utc": snapshot_utc, "metric": "rows_with_demand_bucket", "value": str(demand_rows)},
        {"observed_utc": snapshot_utc, "metric": "rows_with_recommended_test_qty", "value": str(qty_rows)},
        {"observed_utc": snapshot_utc, "metric": "rows_with_recommendation_status", "value": str(status_rows)},
    ]
    summary_out_df = pd.DataFrame(summary_rows, columns=["observed_utc", "metric", "value"])

    replay_path = output_dir / f"f_sold_decision_replay_{ts_slug}.csv"
    replay_latest_path = output_path
    summary_path = output_dir / f"f_sold_decision_replay_summary_{ts_slug}.csv"
    summary_latest_path = summary_output_path

    replay_df.to_csv(replay_path, index=False)
    replay_df.to_csv(replay_latest_path, index=False)
    summary_out_df.to_csv(summary_path, index=False)
    summary_out_df.to_csv(summary_latest_path, index=False)

    print(
        json.dumps(
            {
                "status": "success",
                "observed_utc": snapshot_utc,
                "sold_rows_total": sold_rows_total,
                "sold_decision_replay_coverage_rows": replay_decision_rows,
                "sold_rows_with_full_model_evidence": full_model_rows,
                "rows_with_demand_bucket": demand_rows,
                "rows_with_recommended_test_qty": qty_rows,
                "rows_with_recommendation_status": status_rows,
                "replay_csv_output": str(replay_path),
                "replay_latest_csv": str(replay_latest_path),
                "summary_csv_output": str(summary_path),
                "summary_latest_csv": str(summary_latest_path),
            }
        )
    )

    return SoldDecisionReplayBridgeResult(
        replay_df=replay_df,
        summary_df=summary_out_df,
        replay_path=replay_path,
        replay_latest_path=replay_latest_path,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build sold-universe decision replay bridge for commercial accuracy scoring.")
    parser.add_argument("--sold-truth-path", default=str(DEFAULT_SOLD_TRUTH_PATH))
    parser.add_argument("--review-path", default=str(DEFAULT_REVIEW_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--alignment-path", default=str(DEFAULT_ALIGNMENT_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--summary-output-path", default=str(DEFAULT_SUMMARY_OUTPUT_PATH))
    parser.add_argument(
        "--decision-profit-floor-gbp",
        default=str(DEFAULT_DECISION_PROFIT_FLOOR_GBP),
        help="Fallback minimum expected profit floor when missing from model source.",
    )
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_sold_decision_replay_bridge(
        sold_truth_path=Path(args.sold_truth_path),
        review_path=Path(args.review_path),
        summary_path=Path(args.summary_path),
        alignment_path=Path(args.alignment_path),
        output_dir=Path(args.output_dir),
        output_path=Path(args.output_path),
        summary_output_path=Path(args.summary_output_path),
        decision_profit_floor_gbp=float(args.decision_profit_floor_gbp),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
