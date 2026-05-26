from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_ACCURACY_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_accuracy_pack_latest.csv"
DEFAULT_ACCURACY_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_accuracy_summary_latest.csv"
DEFAULT_SOLD_CAPTURE_PACK_PATH = DEFAULT_OUTPUT_DIR / "f_sold_truth_replay_capture_pack_latest.csv"
DEFAULT_SOLD_CAPTURE_REPORT_PATH = DEFAULT_OUTPUT_DIR / "bef_sold_truth_replay_capture_latest.json"
DEFAULT_BACKTEST_INPUT_VIEW_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_backtest_input_view_live.csv"
DEFAULT_FULL_CAPTURE_MANIFEST_DIR = DEFAULT_OUTPUT_DIR
DEFAULT_DECISION_PROFIT_FLOOR_GBP = 20.0
DEFAULT_NEAR_FLOOR_BAND_GBP = 5.0


@dataclass(frozen=True)
class LiveTestDataSufficiencyResult:
    summary_df: pd.DataFrame
    gap_df: pd.DataFrame
    summary_path: Path
    summary_latest_path: Path
    gap_path: Path
    gap_latest_path: Path
    report: dict[str, Any]


SUMMARY_COLUMNS = [
    "observed_utc",
    "family",
    "state",
    "current_count",
    "required_count",
    "missing_count",
    "notes",
]

GAP_COLUMNS = [
    "observed_utc",
    "family",
    "current_state",
    "current_count",
    "required_count",
    "missing_count",
    "acquisition_path",
    "owning_batch",
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
    cleaned = raw.replace(",", "").replace("GBP", "").replace("gbp", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


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
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


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


def _capture_rank_window_asins(manifest_dir: Path) -> set[str]:
    manifest_paths = sorted(manifest_dir.glob("f_full_capture_manifest_*.csv"))
    if not manifest_paths:
        return set()

    frames: list[pd.DataFrame] = []
    for path in manifest_paths:
        df = _read_csv(path)
        if df.empty:
            continue
        frames.append(df)
    if not frames:
        return set()

    manifest_df = pd.concat(frames, ignore_index=True).fillna("")
    if manifest_df.empty:
        return set()

    if "run_id" in manifest_df.columns:
        manifest_df["_run_id"] = manifest_df.get("run_id", "").map(_normalize_text)
        manifest_df["_observed_utc"] = manifest_df.get("observed_utc", "").map(_normalize_text)
        manifest_df = manifest_df.sort_values(by=["_run_id", "_observed_utc"], ascending=[True, False], kind="stable")
        manifest_df = manifest_df.drop_duplicates(subset=["_run_id"], keep="first")

    if "capture_status" in manifest_df.columns:
        manifest_df = manifest_df[
            manifest_df.get("capture_status", "").map(lambda value: _normalize_text(value).lower()) == "success"
        ].copy()
    if manifest_df.empty:
        return set()

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

    asins_with_rank_window: set[str] = set()
    for asin, day_map in asin_day_values.items():
        if not day_map:
            continue
        ordered_days = sorted(day_map.keys())
        ordered_values = [day_map[day] for day in ordered_days if day_map[day] > 0]
        if not ordered_values:
            continue
        trailing_30 = ordered_values[-30:]
        trailing_90 = ordered_values[-90:]
        median_30 = float(statistics.median(trailing_30)) if trailing_30 else None
        median_90 = float(statistics.median(trailing_90)) if trailing_90 else None
        if median_30 is not None or median_90 is not None:
            asins_with_rank_window.add(asin)
    return asins_with_rank_window


def _summary_metric(summary_df: pd.DataFrame, name: str) -> float | None:
    if summary_df.empty:
        return None
    if "metric" not in summary_df.columns:
        return None
    rows = summary_df.loc[summary_df["metric"].map(_normalize_text) == name]
    if rows.empty:
        return None
    return _num_or_none(rows.iloc[0].get("value", ""))


def _count_nonblank(df: pd.DataFrame, column: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    return int((df[column].map(_normalize_text) != "").sum())


def _count_with_condition(df: pd.DataFrame, column: str, expected: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    token = _normalize_text(expected).lower()
    return int((df[column].map(lambda value: _normalize_text(value).lower()) == token).sum())


def _family_state_row(
    *,
    observed_utc: str,
    family: str,
    state: str,
    current_count: int,
    required_count: int,
    notes: str,
) -> dict[str, str]:
    missing_count = max(required_count - current_count, 0)
    return {
        "observed_utc": observed_utc,
        "family": family,
        "state": state,
        "current_count": str(int(current_count)),
        "required_count": str(int(required_count)),
        "missing_count": str(int(missing_count)),
        "notes": notes,
    }


def _gap_row(
    *,
    observed_utc: str,
    family: str,
    current_state: str,
    current_count: int,
    required_count: int,
    acquisition_path: str,
    owning_batch: str,
) -> dict[str, str]:
    missing_count = max(required_count - current_count, 0)
    return {
        "observed_utc": observed_utc,
        "family": family,
        "current_state": current_state,
        "current_count": str(int(current_count)),
        "required_count": str(int(required_count)),
        "missing_count": str(int(missing_count)),
        "acquisition_path": acquisition_path,
        "owning_batch": owning_batch,
    }


def build_live_test_data_sufficiency_gate(
    *,
    accuracy_path: Path = DEFAULT_ACCURACY_PATH,
    accuracy_summary_path: Path = DEFAULT_ACCURACY_SUMMARY_PATH,
    sold_capture_pack_path: Path = DEFAULT_SOLD_CAPTURE_PACK_PATH,
    sold_capture_report_path: Path = DEFAULT_SOLD_CAPTURE_REPORT_PATH,
    backtest_input_view_path: Path = DEFAULT_BACKTEST_INPUT_VIEW_PATH,
    full_capture_manifest_dir: Path = DEFAULT_FULL_CAPTURE_MANIFEST_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    decision_profit_floor_gbp: float = DEFAULT_DECISION_PROFIT_FLOOR_GBP,
    near_floor_band_gbp: float = DEFAULT_NEAR_FLOOR_BAND_GBP,
    min_sold_rows: int = 40,
    min_decision_rows: int = 40,
    min_rank_overlap_rows: int = 40,
    min_pass_rows: int = 5,
    min_fail_rows: int = 5,
    min_near_floor_rows: int = 5,
    observed_utc: str | None = None,
) -> LiveTestDataSufficiencyResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(snapshot_utc)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / f"f_live_test_data_sufficiency_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "f_live_test_data_sufficiency_summary_latest.csv"
    gap_path = output_dir / f"f_live_test_data_gap_plan_{ts_slug}.csv"
    gap_latest_path = output_dir / "f_live_test_data_gap_plan_latest.csv"

    accuracy_df = _read_csv(accuracy_path)
    accuracy_summary_df = _read_csv(accuracy_summary_path)
    sold_capture_df = _read_csv(sold_capture_pack_path)
    sold_capture_report = _read_json(sold_capture_report_path)
    backtest_df = _read_csv(backtest_input_view_path)

    sold_rows_total = int(len(accuracy_df.index))
    sold_rows_with_model_side_evidence = _count_nonblank(accuracy_df, "model_side_evidence_state") - _count_with_condition(
        accuracy_df, "model_side_evidence_state", "missing"
    )
    sold_rows_with_model_side_evidence = max(sold_rows_with_model_side_evidence, 0)

    sold_rows_with_full_model_evidence = _count_with_condition(
        accuracy_df, "model_side_evidence_state", "full_decision_and_estimate"
    )
    if sold_rows_with_full_model_evidence == 0:
        fallback_full = 0
        for _, row in accuracy_df.iterrows():
            decision_token = _normalize_text(row.get("model_decision_state", ""))
            has_decision = decision_token != ""
            has_estimate = _normalize_text(row.get("model_expected_units_next_30d", "")) != "" or _normalize_text(
                row.get("model_expected_profit_next_30d_gbp", "")
            ) != ""
            if has_decision and has_estimate:
                fallback_full += 1
        sold_rows_with_full_model_evidence = fallback_full

    summary_decision_judged = _summary_metric(accuracy_summary_df, "decision_judged_rows")
    decision_judged_rows = int(summary_decision_judged) if summary_decision_judged is not None else _count_with_condition(
        accuracy_df, "decision_judged_flag", "1"
    )

    pass_rows = _count_with_condition(accuracy_df, "truth_decision_state", "pass")
    fail_rows = _count_with_condition(accuracy_df, "truth_decision_state", "fail")

    near_floor_rows = 0
    rows_with_actual_units_profit = 0
    for _, row in accuracy_df.iterrows():
        actual_units = _num_or_none(row.get("actual_units_30d", ""))
        actual_profit = _num_or_none(row.get("actual_profit_30d_gbp", ""))
        if actual_units is not None and actual_profit is not None:
            rows_with_actual_units_profit += 1
        if actual_profit is None:
            continue
        if abs(actual_profit - decision_profit_floor_gbp) <= near_floor_band_gbp:
            near_floor_rows += 1

    rows_with_recommended_test_qty = _count_nonblank(accuracy_df, "recommended_test_qty")
    if rows_with_recommended_test_qty == 0:
        maybe_summary_qty = _summary_metric(accuracy_summary_df, "rows_with_recommended_test_qty")
        if maybe_summary_qty is not None:
            rows_with_recommended_test_qty = int(maybe_summary_qty)

    rows_with_demand_bucket = _count_nonblank(accuracy_df, "estimated_demand")
    if rows_with_demand_bucket == 0:
        maybe_summary_bucket = _summary_metric(accuracy_summary_df, "rows_with_demand_bucket")
        if maybe_summary_bucket is not None:
            rows_with_demand_bucket = int(maybe_summary_bucket)

    sold_capture_rows = int(len(sold_capture_df.index))
    report_metrics = sold_capture_report.get("metrics", {}) if isinstance(sold_capture_report.get("metrics", {}), dict) else {}
    sold_capture_success_rows = int(_num_or_none(report_metrics.get("capture_success_rows", sold_capture_rows)) or 0)
    sold_capture_failed_rows = int(_num_or_none(report_metrics.get("capture_failed_rows", 0)) or 0)

    sold_asins: set[str] = {
        _normalize_key(value)
        for value in accuracy_df.get("asin", pd.Series([], dtype=str)).map(_normalize_text).tolist()
        if _normalize_key(value) != ""
    }
    backtest_rank_asins: set[str] = set()
    rank_overlap_rows_backtest = 0
    rank_overlap_rows_capture = 0
    if not backtest_df.empty and "asin" in backtest_df.columns:
        work = backtest_df.copy()
        work["_asin_key"] = work.get("asin", "").map(_normalize_key)
        work = work[work["_asin_key"].isin(sold_asins)].copy()
        if not work.empty:
            has_bsr_30 = work.get("bsr_median_30d", "").map(_normalize_text) != ""
            has_bsr_90 = work.get("bsr_median_90d", "").map(_normalize_text) != ""
            with_rank = work[has_bsr_30 | has_bsr_90].copy()
            backtest_rank_asins = {
                _normalize_key(value) for value in with_rank["_asin_key"].tolist() if _normalize_key(value) != ""
            }
            rank_overlap_rows_backtest = int(len(backtest_rank_asins))
    capture_rank_asins = _capture_rank_window_asins(full_capture_manifest_dir)
    rank_overlap_rows_capture = int(len(capture_rank_asins & sold_asins))
    rank_overlap_rows = int(len((capture_rank_asins & sold_asins) | backtest_rank_asins))
    rank_overlap_row_count = rank_overlap_rows

    summary_rows: list[dict[str, str]] = []
    gap_rows: list[dict[str, str]] = []

    sold_truth_state = "ready_now" if sold_rows_total >= min_sold_rows else "insufficient_sample_mix"
    summary_rows.append(
        _family_state_row(
            observed_utc=snapshot_utc,
            family="sold_truth_state",
            state=sold_truth_state,
            current_count=sold_rows_total,
            required_count=min_sold_rows,
            notes=f"sold_rows_total={sold_rows_total}",
        )
    )
    if sold_truth_state != "ready_now":
        gap_rows.append(
            _gap_row(
                observed_utc=snapshot_utc,
                family="sold_truth_state",
                current_state=sold_truth_state,
                current_count=sold_rows_total,
                required_count=min_sold_rows,
                acquisition_path="Expand sold-truth rows via operational baseline recovery and sold replay capture path reruns.",
                owning_batch="EXECUTION_BATCH_014",
            )
        )

    model_side_state = "ready_now" if sold_rows_with_model_side_evidence >= min_sold_rows else "insufficient_sample_mix"
    summary_rows.append(
        _family_state_row(
            observed_utc=snapshot_utc,
            family="model_side_evidence_state",
            state=model_side_state,
            current_count=sold_rows_with_model_side_evidence,
            required_count=min_sold_rows,
            notes=f"sold_rows_with_model_side_evidence={sold_rows_with_model_side_evidence}",
        )
    )
    if model_side_state != "ready_now":
        gap_rows.append(
            _gap_row(
                observed_utc=snapshot_utc,
                family="model_side_evidence_state",
                current_state=model_side_state,
                current_count=sold_rows_with_model_side_evidence,
                required_count=min_sold_rows,
                acquisition_path="Replay sold capture queue and refresh model-side evidence sources for missing sold rows.",
                owning_batch="EXECUTION_BATCH_014",
            )
        )

    decision_current_count = min(sold_rows_with_full_model_evidence, decision_judged_rows)
    decision_state = "ready_now" if decision_current_count >= min_decision_rows else "ready_after_replay_bridge"
    summary_rows.append(
        _family_state_row(
            observed_utc=snapshot_utc,
            family="decision_replay_state",
            state=decision_state,
            current_count=decision_current_count,
            required_count=min_decision_rows,
            notes=(
                f"sold_rows_with_full_model_evidence={sold_rows_with_full_model_evidence};"
                f"decision_judged_rows={decision_judged_rows}"
            ),
        )
    )
    if decision_state != "ready_now":
        gap_rows.append(
            _gap_row(
                observed_utc=snapshot_utc,
                family="decision_replay_state",
                current_state=decision_state,
                current_count=decision_current_count,
                required_count=min_decision_rows,
                acquisition_path=(
                    "Run EXECUTION_BATCH_012 sold decision replay bridge to populate model_decision_state, "
                    "model_decision_confidence, and full decision judging on sold rows."
                ),
                owning_batch="EXECUTION_BATCH_012",
            )
        )

    sales_band_state = "ready_now" if rows_with_actual_units_profit >= min_sold_rows else "insufficient_sample_mix"
    summary_rows.append(
        _family_state_row(
            observed_utc=snapshot_utc,
            family="sales_band_data_state",
            state=sales_band_state,
            current_count=rows_with_actual_units_profit,
            required_count=min_sold_rows,
            notes=f"rows_with_actual_units_profit={rows_with_actual_units_profit}",
        )
    )
    if sales_band_state != "ready_now":
        gap_rows.append(
            _gap_row(
                observed_utc=snapshot_utc,
                family="sales_band_data_state",
                current_state=sales_band_state,
                current_count=rows_with_actual_units_profit,
                required_count=min_sold_rows,
                acquisition_path="Increase sold-truth rows with complete units and profit fields before commercial band scoring.",
                owning_batch="EXECUTION_BATCH_014",
            )
        )

    starter_current_count = min(rows_with_recommended_test_qty, rows_with_demand_bucket)
    starter_state = "ready_now" if starter_current_count >= min_decision_rows else "ready_after_replay_bridge"
    summary_rows.append(
        _family_state_row(
            observed_utc=snapshot_utc,
            family="starter_qty_input_state",
            state=starter_state,
            current_count=starter_current_count,
            required_count=min_decision_rows,
            notes=(
                f"rows_with_recommended_test_qty={rows_with_recommended_test_qty};"
                f"rows_with_demand_bucket={rows_with_demand_bucket}"
            ),
        )
    )
    if starter_state != "ready_now":
        gap_rows.append(
            _gap_row(
                observed_utc=snapshot_utc,
                family="starter_qty_input_state",
                current_state=starter_state,
                current_count=starter_current_count,
                required_count=min_decision_rows,
                acquisition_path=(
                    "Carry estimated_demand and recommended_test_qty into sold decision replay output, "
                    "then rebuild F011 and rerun this gate."
                ),
                owning_batch="EXECUTION_BATCH_012",
            )
        )

    rank_state = "ready_now" if rank_overlap_rows >= min_rank_overlap_rows else "needs_rank_window_capture"
    summary_rows.append(
        _family_state_row(
            observed_utc=snapshot_utc,
            family="rank_window_state",
            state=rank_state,
            current_count=rank_overlap_rows,
            required_count=min_rank_overlap_rows,
            notes=(
                f"rank_overlap_backtest_rows={rank_overlap_rows_backtest};"
                f"rank_overlap_full_capture_rows={rank_overlap_rows_capture}"
            ),
        )
    )
    if rank_state != "ready_now":
        gap_rows.append(
            _gap_row(
                observed_utc=snapshot_utc,
                family="rank_window_state",
                current_state=rank_state,
                current_count=rank_overlap_rows,
                required_count=min_rank_overlap_rows,
                acquisition_path=(
                    "Build sold-universe rank-window data by ASIN from BSR history capture, then score best and worst rank bands."
                ),
                owning_batch="EXECUTION_BATCH_013",
            )
        )

    sample_current_count = min(pass_rows, fail_rows, near_floor_rows)
    sample_required_count = min(min_pass_rows, min_fail_rows, min_near_floor_rows)
    sample_state = "ready_now" if sample_current_count >= sample_required_count else "insufficient_sample_mix"
    summary_rows.append(
        _family_state_row(
            observed_utc=snapshot_utc,
            family="sample_mix_state",
            state=sample_state,
            current_count=sample_current_count,
            required_count=sample_required_count,
            notes=f"pass_rows={pass_rows};fail_rows={fail_rows};near_floor_rows={near_floor_rows}",
        )
    )
    if sample_state != "ready_now":
        gap_rows.append(
            _gap_row(
                observed_utc=snapshot_utc,
                family="sample_mix_state",
                current_state=sample_state,
                current_count=sample_current_count,
                required_count=sample_required_count,
                acquisition_path="Expand sold sample mix with additional pass, fail, and near-floor rows before classifier tuning.",
                owning_batch="EXECUTION_BATCH_014",
            )
        )

    summary_out_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)
    gap_out_df = pd.DataFrame(gap_rows, columns=GAP_COLUMNS)

    summary_out_df.to_csv(summary_path, index=False)
    summary_out_df.to_csv(summary_latest_path, index=False)
    gap_out_df.to_csv(gap_path, index=False)
    gap_out_df.to_csv(gap_latest_path, index=False)

    report = {
        "status": "success",
        "observed_utc": snapshot_utc,
        "metrics": {
            "sold_rows_total": sold_rows_total,
            "sold_rows_with_model_side_evidence": sold_rows_with_model_side_evidence,
            "sold_rows_with_full_model_evidence": sold_rows_with_full_model_evidence,
            "decision_judged_rows": decision_judged_rows,
            "pass_rows": pass_rows,
            "fail_rows": fail_rows,
            "near_floor_rows": near_floor_rows,
            "rows_with_recommended_test_qty": rows_with_recommended_test_qty,
            "rows_with_demand_bucket": rows_with_demand_bucket,
            "sold_capture_rows": sold_capture_rows,
            "sold_capture_success_rows": sold_capture_success_rows,
            "sold_capture_failed_rows": sold_capture_failed_rows,
            "sold_asin_bsr_window_overlap_rows": rank_overlap_rows,
            "sold_asin_bsr_window_overlap_row_count": rank_overlap_row_count,
            "sold_asin_bsr_overlap_backtest_rows": rank_overlap_rows_backtest,
            "sold_asin_bsr_overlap_full_capture_rows": rank_overlap_rows_capture,
        },
        "states": {
            row["family"]: row["state"] for row in summary_rows
        },
        "artifacts": {
            "summary_csv_output": str(summary_path),
            "summary_latest_csv": str(summary_latest_path),
            "gap_csv_output": str(gap_path),
            "gap_latest_csv": str(gap_latest_path),
        },
    }
    print(json.dumps(report))

    return LiveTestDataSufficiencyResult(
        summary_df=summary_out_df,
        gap_df=gap_out_df,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
        gap_path=gap_path,
        gap_latest_path=gap_latest_path,
        report=report,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build commercial live-test data sufficiency gate summary and explicit gap plan."
    )
    parser.add_argument("--accuracy-path", default=str(DEFAULT_ACCURACY_PATH))
    parser.add_argument("--accuracy-summary-path", default=str(DEFAULT_ACCURACY_SUMMARY_PATH))
    parser.add_argument("--sold-capture-pack-path", default=str(DEFAULT_SOLD_CAPTURE_PACK_PATH))
    parser.add_argument("--sold-capture-report-path", default=str(DEFAULT_SOLD_CAPTURE_REPORT_PATH))
    parser.add_argument("--backtest-input-view-path", default=str(DEFAULT_BACKTEST_INPUT_VIEW_PATH))
    parser.add_argument("--full-capture-manifest-dir", default=str(DEFAULT_FULL_CAPTURE_MANIFEST_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--decision-profit-floor-gbp", default=str(DEFAULT_DECISION_PROFIT_FLOOR_GBP))
    parser.add_argument("--near-floor-band-gbp", default=str(DEFAULT_NEAR_FLOOR_BAND_GBP))
    parser.add_argument("--min-sold-rows", default="40")
    parser.add_argument("--min-decision-rows", default="40")
    parser.add_argument("--min-rank-overlap-rows", default="40")
    parser.add_argument("--min-pass-rows", default="5")
    parser.add_argument("--min-fail-rows", default="5")
    parser.add_argument("--min-near-floor-rows", default="5")
    parser.add_argument("--observed-utc", default=None, help="Override observed_utc in YYYY-MM-DDTHH:MM:SSZ.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_live_test_data_sufficiency_gate(
        accuracy_path=Path(args.accuracy_path),
        accuracy_summary_path=Path(args.accuracy_summary_path),
        sold_capture_pack_path=Path(args.sold_capture_pack_path),
        sold_capture_report_path=Path(args.sold_capture_report_path),
        backtest_input_view_path=Path(args.backtest_input_view_path),
        full_capture_manifest_dir=Path(args.full_capture_manifest_dir),
        output_dir=Path(args.output_dir),
        decision_profit_floor_gbp=float(args.decision_profit_floor_gbp),
        near_floor_band_gbp=float(args.near_floor_band_gbp),
        min_sold_rows=int(args.min_sold_rows),
        min_decision_rows=int(args.min_decision_rows),
        min_rank_overlap_rows=int(args.min_rank_overlap_rows),
        min_pass_rows=int(args.min_pass_rows),
        min_fail_rows=int(args.min_fail_rows),
        min_near_floor_rows=int(args.min_near_floor_rows),
        observed_utc=args.observed_utc,
    )


if __name__ == "__main__":
    main()
