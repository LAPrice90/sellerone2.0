from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "hf_strategy_scorecard_latest.csv"

ACTION_OUTCOMES_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_action_outcomes_latest.csv"
ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
DAILY_STRATEGY_PATH = ROOT / "out" / "h_strategy_outcome_daily.csv"
SKU_PERFORMANCE_PATH = ROOT / "out" / "sku_performance_summary.csv"
H_CYCLE_STATE_PATH = ROOT / "out" / "h_pricing_cycle_state.json"

REQUIRED_INPUTS = [ACTION_OUTCOMES_PATH, ALIGNMENT_PATH, DAILY_STRATEGY_PATH, SKU_PERFORMANCE_PATH]

SCORECARD_COLUMNS = [
    "snapshot_utc",
    "scenario_type",
    "decision_rows",
    "sample_decision_rows_live",
    "sample_min_rows",
    "sample_gap_rows",
    "sample_mature_flag",
    "provisional_sample_flag",
    "eligible_to_write_rows",
    "decision_to_change_rows",
    "write_attempted_rows",
    "write_applied_rows",
    "write_applied_rate",
    "failed_rows",
    "failed_rate",
    "expired_rows",
    "expired_rate",
    "actual_units_30d",
    "actual_profit_30d_gbp",
    "avg_seller_count",
    "missing_expected_baseline_rate",
    "underperform_rate",
    "dominant_alignment_class",
    "review_status",
    "action_scope_date",
    "daily_sample_asof_date",
    "alignment_snapshot_utc",
]


@dataclass(frozen=True)
class StrategyScorecardResult:
    output_path: Path
    rows: int
    mature_rows: int
    blocked_rows: int
    action_scope_date: str
    daily_sample_asof_date: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _to_int(value: object, default: int = 0) -> int:
    text = _normalize_text(value)
    if text == "":
        return int(default)
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return int(default)


def _to_float(value: object) -> float | None:
    text = _normalize_text(value)
    if text == "":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0000"
    return f"{(numerator / denominator):.4f}"


def _to_float_text(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required batch-002 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_json_optional(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required batch-002 input missing: {path}")


def _build_performance_maps(perf_df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    if perf_df.empty:
        return {}, {}
    work = pd.DataFrame()
    work["sku"] = perf_df.get("sku", "").map(_normalize_text)
    work["window_days"] = perf_df.get("window_days", "").map(_normalize_text)
    work["units_sold"] = perf_df.get("units_sold", "").map(_to_float)
    work["profit_exvat_gbp"] = perf_df.get("profit_exvat_gbp", "").map(_to_float)
    work = work[work["sku"] != ""].copy()
    work = work[(work["window_days"] == "30") | (work["window_days"] == "")].copy()
    work = work.sort_values(["sku", "window_days"], ascending=[True, True], kind="stable")
    work = work.drop_duplicates(subset=["sku"], keep="first")
    units_map: dict[str, float] = {}
    profit_map: dict[str, float] = {}
    for _, row in work.iterrows():
        sku = _normalize_text(row.get("sku", ""))
        units = row.get("units_sold")
        profit = row.get("profit_exvat_gbp")
        if sku == "":
            continue
        if units is not None:
            units_map[sku] = float(units)
        if profit is not None:
            profit_map[sku] = float(profit)
    return units_map, profit_map


def _build_daily_sample_map(daily_df: pd.DataFrame) -> tuple[dict[str, dict[str, int]], str]:
    if daily_df.empty:
        return {}, ""
    work = pd.DataFrame()
    work["asof_date"] = daily_df.get("asof_date", "").map(_normalize_text)
    work["scenario_type"] = daily_df.get("scenario_type", "").map(_normalize_text)
    work["decision_rows"] = daily_df.get("decision_rows", "").map(_to_int)
    work["sample_min_rows"] = daily_df.get("sample_min_rows", "").map(_to_int)
    work["provisional_sample_flag"] = daily_df.get("provisional_sample_flag", "").map(_to_int)
    work["failed_rows"] = daily_df.get("failed_rows", "").map(_to_int)
    work["expired_rows"] = daily_df.get("expired_rows", "").map(_to_int)
    work = work[(work["asof_date"] != "") & (work["scenario_type"] != "")].copy()
    if work.empty:
        return {}, ""
    latest_asof_date = _normalize_text(work["asof_date"].max())
    latest = work[work["asof_date"] == latest_asof_date].copy()
    out: dict[str, dict[str, int]] = {}
    grouped = latest.groupby("scenario_type", dropna=False)
    for scenario, group in grouped:
        scenario_name = _normalize_text(scenario)
        out[scenario_name] = {
            "decision_rows": int(group["decision_rows"].sum()),
            "sample_min_rows": int(group["sample_min_rows"].max()),
            "provisional_sample_flag": int(group["provisional_sample_flag"].max()),
            "failed_rows": int(group["failed_rows"].sum()),
            "expired_rows": int(group["expired_rows"].sum()),
        }
    return out, latest_asof_date


def _apply_cycle_state_overrides(
    sample_map: dict[str, dict[str, int]],
    cycle_state: dict[str, object],
) -> dict[str, dict[str, int]]:
    out = {scenario: values.copy() for scenario, values in sample_map.items()}
    prefix = "h_strategy_sample_live_"
    suffix_map = {
        "_decision_rows": "decision_rows",
        "_sample_min_rows": "sample_min_rows",
        "_provisional_flag": "provisional_sample_flag",
    }
    parsed: dict[str, dict[str, int]] = {}
    for key, raw_value in cycle_state.items():
        key_text = _normalize_text(key)
        if not key_text.startswith(prefix):
            continue
        for suffix, field_name in suffix_map.items():
            if not key_text.endswith(suffix):
                continue
            scenario_name = key_text[len(prefix) : -len(suffix)]
            scenario_name = _normalize_text(scenario_name)
            if scenario_name == "":
                continue
            parsed.setdefault(scenario_name, {})
            parsed[scenario_name][field_name] = _to_int(raw_value)
            break

    for scenario_name, overrides in parsed.items():
        current = out.get(
            scenario_name,
            {
                "decision_rows": 0,
                "sample_min_rows": 0,
                "provisional_sample_flag": 0,
                "failed_rows": 0,
                "expired_rows": 0,
            },
        ).copy()
        for field_name, value in overrides.items():
            current[field_name] = int(value)
        out[scenario_name] = current
    return out


def _build_action_scope_map(action_df: pd.DataFrame) -> tuple[dict[str, dict[str, object]], str]:
    if action_df.empty:
        return {}, ""
    work = pd.DataFrame()
    work["event_date"] = action_df.get("event_ts_utc", "").map(_normalize_text).str.slice(0, 10)
    work["scenario_type"] = action_df.get("scenario_type", "").map(_normalize_text)
    work["eligible_to_write_flag"] = action_df.get("eligible_to_write_flag", "").map(_normalize_text)
    work["decision_to_change_price_flag"] = action_df.get("decision_to_change_price_flag", "").map(_normalize_text)
    work["write_attempted_flag"] = action_df.get("write_attempted_flag", "").map(_normalize_text)
    work["write_applied_flag"] = action_df.get("write_applied_flag", "").map(_normalize_text)
    work["tactic_success_state"] = action_df.get("tactic_success_state", "").map(_normalize_text).str.lower()
    work["seller_count"] = action_df.get("seller_count", "").map(_to_float)
    work["sku"] = action_df.get("sku", "").map(_normalize_text)
    work = work[(work["event_date"] != "") & (work["scenario_type"] != "")].copy()
    if work.empty:
        return {}, ""

    latest_date = _normalize_text(work["event_date"].max())
    scoped = work[work["event_date"] == latest_date].copy()
    out: dict[str, dict[str, object]] = {}
    grouped = scoped.groupby("scenario_type", dropna=False)
    for scenario, group in grouped:
        scenario_name = _normalize_text(scenario)
        seller_values = [float(v) for v in group["seller_count"].tolist() if v is not None]
        sku_values = sorted({sku for sku in group["sku"].tolist() if _normalize_text(sku) != ""})
        out[scenario_name] = {
            "decision_rows": int(len(group.index)),
            "eligible_rows": int((group["eligible_to_write_flag"] == "1").sum()),
            "decision_change_rows": int((group["decision_to_change_price_flag"] == "1").sum()),
            "write_attempted_rows": int((group["write_attempted_flag"] == "1").sum()),
            "write_applied_rows": int((group["write_applied_flag"] == "1").sum()),
            "failed_rows": int((group["tactic_success_state"] == "failed").sum()),
            "expired_rows": int((group["tactic_success_state"] == "expired").sum()),
            "avg_seller_count": (sum(seller_values) / len(seller_values)) if seller_values else None,
            "skus": sku_values,
        }
    return out, latest_date


def _build_alignment_maps(alignment_df: pd.DataFrame) -> tuple[dict[str, str], str]:
    if alignment_df.empty:
        return {}, ""
    work = pd.DataFrame()
    work["alignment_window_end_utc"] = alignment_df.get("alignment_window_end_utc", "").map(_normalize_text)
    work["sku"] = alignment_df.get("sku", "").map(_normalize_text)
    work["dominant_discrepancy_class"] = alignment_df.get("dominant_discrepancy_class", "").map(_normalize_text)
    work = work[(work["sku"] != "") & (work["dominant_discrepancy_class"] != "")].copy()
    if work.empty:
        latest_snapshot = _normalize_text(alignment_df.get("alignment_window_end_utc", pd.Series([], dtype=str)).max())
        return {}, latest_snapshot
    work = work.sort_values(["sku", "alignment_window_end_utc"], ascending=[True, False], kind="stable")
    work = work.drop_duplicates(subset=["sku"], keep="first")
    latest_snapshot = _normalize_text(work["alignment_window_end_utc"].max())
    return {row["sku"]: row["dominant_discrepancy_class"] for _, row in work.iterrows()}, latest_snapshot


def _alignment_rates_for_scenario(
    *,
    skus: list[str],
    alignment_by_sku: dict[str, str],
) -> tuple[str, str, str]:
    if not skus:
        return "0.0000", "0.0000", "no_alignment_source"
    classes: list[str] = []
    for sku in skus:
        cls = _normalize_text(alignment_by_sku.get(sku, ""))
        if cls != "":
            classes.append(cls)
    if not classes:
        return "0.0000", "0.0000", "no_alignment_source"
    total = len(classes)
    missing_count = sum(1 for value in classes if value == "missing_expected_baseline")
    underperform_count = sum(1 for value in classes if value == "underperform_vs_expected")
    class_counts: dict[str, int] = {}
    for value in classes:
        class_counts[value] = class_counts.get(value, 0) + 1
    dominant_class = sorted(class_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return _to_rate(missing_count, total), _to_rate(underperform_count, total), dominant_class


def _review_status(
    *,
    sample_mature_flag: int,
    missing_expected_rate: float,
    failed_rate: float,
    expired_rate: float,
    write_applied_rate: float,
) -> str:
    if sample_mature_flag != 1:
        return "blocked"
    if missing_expected_rate >= 0.50:
        return "overlap_first"
    if failed_rate > 0.35 or expired_rate > 0.60:
        return "keep_observing"
    if write_applied_rate <= 0.02:
        return "keep_observing"
    return "eligible_shadow"


def build_strategy_scorecard(*, output_path: Path) -> StrategyScorecardResult:
    _ensure_required_inputs()
    snapshot_utc = _utc_now_iso()

    action_df = _read_csv_required(ACTION_OUTCOMES_PATH)
    alignment_df = _read_csv_required(ALIGNMENT_PATH)
    daily_df = _read_csv_required(DAILY_STRATEGY_PATH)
    perf_df = _read_csv_required(SKU_PERFORMANCE_PATH)
    cycle_state = _read_json_optional(H_CYCLE_STATE_PATH)

    action_scope_map, action_scope_date = _build_action_scope_map(action_df)
    daily_sample_map, daily_sample_asof_date = _build_daily_sample_map(daily_df)
    daily_sample_map = _apply_cycle_state_overrides(daily_sample_map, cycle_state)
    alignment_by_sku, alignment_snapshot_utc = _build_alignment_maps(alignment_df)
    units_by_sku, profit_by_sku = _build_performance_maps(perf_df)

    scenarios = sorted(set(action_scope_map.keys()) | set(daily_sample_map.keys()))
    rows: list[dict[str, object]] = []
    for scenario in scenarios:
        action_stats = action_scope_map.get(
            scenario,
            {
                "decision_rows": 0,
                "eligible_rows": 0,
                "decision_change_rows": 0,
                "write_attempted_rows": 0,
                "write_applied_rows": 0,
                "failed_rows": 0,
                "expired_rows": 0,
                "avg_seller_count": None,
                "skus": [],
            },
        )
        sample_stats = daily_sample_map.get(
            scenario,
            {
                "decision_rows": int(action_stats.get("decision_rows", 0)),
                "sample_min_rows": 0,
                "provisional_sample_flag": 0,
                "failed_rows": int(action_stats.get("failed_rows", 0)),
                "expired_rows": int(action_stats.get("expired_rows", 0)),
            },
        )

        sample_decision_rows = max(_to_int(sample_stats.get("decision_rows", 0)), 0)
        sample_min_rows = max(_to_int(sample_stats.get("sample_min_rows", 0)), 0)
        provisional_flag = 1 if _to_int(sample_stats.get("provisional_sample_flag", 0)) > 0 else 0
        sample_gap_rows = max(sample_min_rows - sample_decision_rows, 0)
        sample_mature_flag = 1 if sample_decision_rows >= sample_min_rows and provisional_flag == 0 and sample_min_rows > 0 else 0

        action_decision_rows = max(_to_int(action_stats.get("decision_rows", 0)), 0)
        eligible_rows = max(_to_int(action_stats.get("eligible_rows", 0)), 0)
        decision_change_rows = max(_to_int(action_stats.get("decision_change_rows", 0)), 0)
        write_attempted_rows = max(_to_int(action_stats.get("write_attempted_rows", 0)), 0)
        write_applied_rows = max(_to_int(action_stats.get("write_applied_rows", 0)), 0)

        failed_rows = max(_to_int(sample_stats.get("failed_rows", action_stats.get("failed_rows", 0))), 0)
        expired_rows = max(_to_int(sample_stats.get("expired_rows", action_stats.get("expired_rows", 0))), 0)

        rate_denominator = action_decision_rows if action_decision_rows > 0 else 1
        maturity_denominator = sample_decision_rows if sample_decision_rows > 0 else 1
        write_applied_rate_text = _to_rate(write_applied_rows, rate_denominator)
        failed_rate_text = _to_rate(failed_rows, maturity_denominator)
        expired_rate_text = _to_rate(expired_rows, maturity_denominator)

        skus = list(action_stats.get("skus", []))
        actual_units_total = sum(units_by_sku.get(sku, 0.0) for sku in skus if sku in units_by_sku)
        actual_profit_total = sum(profit_by_sku.get(sku, 0.0) for sku in skus if sku in profit_by_sku)
        actual_units_text = _to_float_text(actual_units_total if skus else None)
        actual_profit_text = _to_float_text(actual_profit_total if skus else None)

        missing_rate_text, underperform_rate_text, dominant_alignment_class = _alignment_rates_for_scenario(
            skus=skus,
            alignment_by_sku=alignment_by_sku,
        )
        missing_rate_float = _to_float(missing_rate_text) or 0.0
        failed_rate_float = _to_float(failed_rate_text) or 0.0
        expired_rate_float = _to_float(expired_rate_text) or 0.0
        write_applied_rate_float = _to_float(write_applied_rate_text) or 0.0

        review_status = _review_status(
            sample_mature_flag=sample_mature_flag,
            missing_expected_rate=missing_rate_float,
            failed_rate=failed_rate_float,
            expired_rate=expired_rate_float,
            write_applied_rate=write_applied_rate_float,
        )

        rows.append(
            {
                "snapshot_utc": snapshot_utc,
                "scenario_type": scenario,
                "decision_rows": sample_decision_rows,
                "sample_decision_rows_live": sample_decision_rows,
                "sample_min_rows": sample_min_rows,
                "sample_gap_rows": sample_gap_rows,
                "sample_mature_flag": sample_mature_flag,
                "provisional_sample_flag": provisional_flag,
                "eligible_to_write_rows": eligible_rows,
                "decision_to_change_rows": decision_change_rows,
                "write_attempted_rows": write_attempted_rows,
                "write_applied_rows": write_applied_rows,
                "write_applied_rate": write_applied_rate_text,
                "failed_rows": failed_rows,
                "failed_rate": failed_rate_text,
                "expired_rows": expired_rows,
                "expired_rate": expired_rate_text,
                "actual_units_30d": actual_units_text,
                "actual_profit_30d_gbp": actual_profit_text,
                "avg_seller_count": _to_float_text(action_stats.get("avg_seller_count")),
                "missing_expected_baseline_rate": missing_rate_text,
                "underperform_rate": underperform_rate_text,
                "dominant_alignment_class": dominant_alignment_class,
                "review_status": review_status,
                "action_scope_date": action_scope_date,
                "daily_sample_asof_date": daily_sample_asof_date,
                "alignment_snapshot_utc": alignment_snapshot_utc,
            }
        )

    scorecard_df = pd.DataFrame(rows).fillna("")
    if not scorecard_df.empty:
        scorecard_df = scorecard_df.sort_values(["scenario_type"], ascending=[True], kind="stable")
    for column in SCORECARD_COLUMNS:
        if column not in scorecard_df.columns:
            scorecard_df[column] = ""
    scorecard_df = scorecard_df[SCORECARD_COLUMNS]
    for column in scorecard_df.columns:
        if column in {
            "decision_rows",
            "sample_decision_rows_live",
            "sample_min_rows",
            "sample_gap_rows",
            "sample_mature_flag",
            "provisional_sample_flag",
            "eligible_to_write_rows",
            "decision_to_change_rows",
            "write_attempted_rows",
            "write_applied_rows",
            "failed_rows",
            "expired_rows",
        }:
            continue
        scorecard_df[column] = scorecard_df[column].map(_normalize_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scorecard_df.to_csv(output_path, index=False)

    mature_rows = int((scorecard_df["sample_mature_flag"] == 1).sum()) if not scorecard_df.empty else 0
    blocked_rows = int((scorecard_df["review_status"] == "blocked").sum()) if not scorecard_df.empty else 0
    return StrategyScorecardResult(
        output_path=output_path,
        rows=int(len(scorecard_df.index)),
        mature_rows=mature_rows,
        blocked_rows=blocked_rows,
        action_scope_date=action_scope_date,
        daily_sample_asof_date=daily_sample_asof_date,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build HF strategy scorecard with maturity gates (Phase 2).")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path for strategy scorecard")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_strategy_scorecard(output_path=Path(args.output))
    print(f"strategy_scorecard_output_path={result.output_path}")
    print(f"strategy_scorecard_rows={result.rows}")
    print(f"strategy_scorecard_mature_rows={result.mature_rows}")
    print(f"strategy_scorecard_blocked_rows={result.blocked_rows}")
    print(f"action_scope_date={result.action_scope_date}")
    print(f"daily_sample_asof_date={result.daily_sample_asof_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
