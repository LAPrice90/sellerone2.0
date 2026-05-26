from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DEFAULT_OUTPUT_DIR = OUT / "analysis_reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off import BEF000_build_sales_truth_foundation as bef000
from scripts.one_off import BEF001_build_operational_feedback_seed as bef001
from scripts.one_off import BEF002_build_sales_feedback_actuals as bef002
from scripts.one_off import BEF003_build_sales_feedback_examples as bef003
from scripts.one_off import F012_build_sales_history_learning_pack as f012
from scripts.one_off import HF010_build_scope_expansion_candidates as hf010

HEALTH_PATH = DEFAULT_OUTPUT_DIR / "bef_sales_feedback_health_latest.csv"
ACTUALS_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_actuals_latest.csv"
REVIEW_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_learning_review_latest.csv"
EXAMPLES_PATH = DEFAULT_OUTPUT_DIR / "bef_sales_feedback_examples_latest.csv"
SUMMARY_LIVE_PATH = OUT / "systems" / "F" / "live" / "feeder_backtest_summary_live.csv"
IDENTITY_BRIDGE_PATH = DEFAULT_OUTPUT_DIR / "hf_learning_identity_bridge_latest.csv"
SOLD_TRUTH_REPLAY_QUEUE_PATH = DEFAULT_OUTPUT_DIR / "f_sold_truth_replay_capture_queue_latest.csv"
SCOPE_EXPANSION_CANDIDATES_PATH = DEFAULT_OUTPUT_DIR / "hf_scope_expansion_candidates_latest.csv"
SCOPE_EXPANSION_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "hf_scope_expansion_summary_latest.csv"
ACCURACY_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "f_sales_history_accuracy_summary_latest.csv"
LATEST_GUARD_REPORT_PATH = DEFAULT_OUTPUT_DIR / "bef_sales_feedback_guarded_run_latest.json"


@dataclass(frozen=True)
class GuardedRunResult:
    report: dict[str, Any]
    report_path: Path
    report_latest_path: Path


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


def _to_int(value: object, *, default: int = 0) -> int:
    text = _normalize_text(value)
    if text == "":
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_health_metrics(health_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if health_df.empty:
        return {}
    out: dict[str, dict[str, str]] = {}
    for _, row in health_df.iterrows():
        metric = _normalize_text(row.get("metric", ""))
        if metric == "":
            continue
        if metric in out:
            continue
        out[metric] = {
            "value": _normalize_text(row.get("value", "")),
            "status": _normalize_text(row.get("status", "")).lower(),
            "notes": _normalize_text(row.get("notes", "")),
        }
    return out


def _actuals_counts(actuals_df: pd.DataFrame) -> dict[str, int]:
    if actuals_df.empty:
        return {
            "rows_total": 0,
            "summary_direct_bridge_rows": 0,
            "summary_asin_rows": 0,
            "alignment_map_rows": 0,
            "native_overlap_rows": 0,
            "seed_replay_rows": 0,
            "recovered_overlap_rows": 0,
            "operational_baseline_rows": 0,
        }
    basis = actuals_df.get("actuals_basis", pd.Series([], dtype=str)).map(_normalize_text).str.lower()
    direct_rows = int((basis == "summary_direct_bridge").sum())
    summary_rows = int((basis == "summary_asin_map").sum())
    alignment_rows = int((basis == "alignment_asin_map").sum())
    native_overlap_rows = direct_rows + summary_rows + alignment_rows
    seed_replay_rows = int((basis == "operational_seed_replay").sum())
    baseline_rows = int((basis == "operational_baseline").sum())
    return {
        "rows_total": int(len(actuals_df.index)),
        "summary_direct_bridge_rows": direct_rows,
        "summary_asin_rows": summary_rows,
        "alignment_map_rows": alignment_rows,
        "native_overlap_rows": native_overlap_rows,
        "seed_replay_rows": seed_replay_rows,
        "recovered_overlap_rows": native_overlap_rows + seed_replay_rows,
        "operational_baseline_rows": baseline_rows,
    }


def _review_counts(review_df: pd.DataFrame) -> dict[str, int]:
    if review_df.empty:
        return {"rows_total": 0, "pending_outcome_rows": 0}
    outcomes = review_df.get("learning_outcome", pd.Series([], dtype=str)).map(_normalize_text).str.lower()
    pending = int((outcomes == "pending_outcome").sum())
    return {
        "rows_total": int(len(review_df.index)),
        "pending_outcome_rows": pending,
    }


def _example_class_counts(examples_df: pd.DataFrame) -> dict[str, int]:
    if examples_df.empty or "example_class" not in examples_df.columns:
        return {}
    counts_raw = examples_df["example_class"].map(_normalize_text).value_counts().to_dict()
    return {str(k): int(v) for k, v in counts_raw.items() if _normalize_text(k) != ""}


def _sold_truth_replay_queue_rows(queue_df: pd.DataFrame) -> int:
    if queue_df.empty:
        return 0
    return int(len(queue_df.index))


def _scope_expansion_metrics(summary_df: pd.DataFrame) -> dict[str, int]:
    if summary_df.empty:
        return {
            "candidate_rows": 0,
            "outside_h_scope_rows": 0,
            "no_asin_rows": 0,
            "stale_source_rows": 0,
        }
    work = pd.DataFrame()
    work["metric_name"] = summary_df.get("metric_name", "").map(_normalize_text)
    work["metric_value"] = summary_df.get("metric_value", "").map(_normalize_text)
    metric_map: dict[str, str] = {}
    for _, row in work.iterrows():
        name = _normalize_text(row.get("metric_name", ""))
        value = _normalize_text(row.get("metric_value", ""))
        if name != "" and name not in metric_map:
            metric_map[name] = value
    return {
        "candidate_rows": _to_int(metric_map.get("candidate_rows_total", ""), default=0),
        "outside_h_scope_rows": _to_int(metric_map.get("outside_h_scope_rows", ""), default=0),
        "no_asin_rows": _to_int(metric_map.get("no_asin_rows", ""), default=0),
        "stale_source_rows": _to_int(metric_map.get("stale_source_rows", ""), default=0),
    }


def _summary_metric_value(summary_df: pd.DataFrame, metric: str) -> str:
    if summary_df.empty:
        return ""
    rows = summary_df.loc[summary_df.get("metric", pd.Series([], dtype=str)).map(_normalize_text) == metric]
    if rows.empty:
        return ""
    return _normalize_text(rows.iloc[0].get("value", ""))


def _direct_bridge_feasibility(
    *,
    actuals_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    identity_df: pd.DataFrame,
) -> dict[str, int]:
    if actuals_df.empty or summary_df.empty or identity_df.empty:
        return {
            "baseline_asin_rows": 0,
            "summary_identity_pair_overlap_rows": 0,
            "direct_bridge_feasible_pair_rows": 0,
        }

    basis = actuals_df.get("actuals_basis", pd.Series([], dtype=str)).map(_normalize_text).str.lower()
    actuals_asin = actuals_df.get("asin", pd.Series([], dtype=str)).map(_normalize_text).str.upper()
    baseline_asins = {
        asin
        for asin, b in zip(actuals_asin.tolist(), basis.tolist())
        if b == "operational_baseline" and asin != ""
    }

    summary_pairs_df = pd.DataFrame()
    summary_pairs_df["seller_sku"] = summary_df.get("seller_sku", "").map(_normalize_text).str.upper()
    summary_pairs_df["asin"] = summary_df.get("asin", "").map(_normalize_text).str.upper()
    summary_pairs_df = summary_pairs_df[
        (summary_pairs_df["seller_sku"] != "") & (summary_pairs_df["asin"] != "")
    ].drop_duplicates(subset=["seller_sku", "asin"], keep="last")
    if summary_pairs_df.empty:
        return {
            "baseline_asin_rows": int(len(baseline_asins)),
            "summary_identity_pair_overlap_rows": 0,
            "direct_bridge_feasible_pair_rows": 0,
        }

    identity_pairs_df = pd.DataFrame()
    identity_pairs_df["seller_sku"] = identity_df.get("supplier_sku", "").map(_normalize_text).str.upper()
    identity_pairs_df["asin"] = identity_df.get("asin", "").map(_normalize_text).str.upper()
    identity_pairs_df = identity_pairs_df[
        (identity_pairs_df["seller_sku"] != "") & (identity_pairs_df["asin"] != "")
    ].drop_duplicates(subset=["seller_sku", "asin"], keep="last")
    if identity_pairs_df.empty:
        return {
            "baseline_asin_rows": int(len(baseline_asins)),
            "summary_identity_pair_overlap_rows": 0,
            "direct_bridge_feasible_pair_rows": 0,
        }

    overlap_pairs = summary_pairs_df.merge(identity_pairs_df, on=["seller_sku", "asin"], how="inner")
    if overlap_pairs.empty:
        return {
            "baseline_asin_rows": int(len(baseline_asins)),
            "summary_identity_pair_overlap_rows": 0,
            "direct_bridge_feasible_pair_rows": 0,
        }

    feasible_pairs = overlap_pairs[overlap_pairs["asin"].isin(baseline_asins)].copy()
    return {
        "baseline_asin_rows": int(len(baseline_asins)),
        "summary_identity_pair_overlap_rows": int(len(overlap_pairs.index)),
        "direct_bridge_feasible_pair_rows": int(len(feasible_pairs.index)),
    }


def _run_builders(*, output_dir: Path, observed_utc: str) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []

    bef000.build_sales_truth_foundation(output_dir=output_dir, observed_utc=observed_utc)
    steps.append({"step": "BEF000", "status": "success"})

    bef001.build_operational_feedback_seed(output_dir=output_dir, observed_utc=observed_utc)
    steps.append({"step": "BEF001", "status": "success"})

    bef002.build_sales_feedback_actuals(output_dir=output_dir, observed_utc=observed_utc)
    steps.append({"step": "BEF002", "status": "success"})

    f012.build_sales_history_learning_pack(
        actuals_path=output_dir / "f_sales_history_learning_actuals_latest.csv",
        output_dir=output_dir,
        observed_utc=observed_utc,
    )
    steps.append({"step": "F012", "status": "success"})

    bef003.build_sales_feedback_examples(
        output_path=output_dir / "bef_sales_feedback_examples_latest.csv",
        observed_utc=observed_utc,
    )
    steps.append({"step": "BEF003", "status": "success"})

    return steps


def run_sales_feedback_guarded_once(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
    run_builders: bool = True,
) -> GuardedRunResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)

    builder_steps: list[dict[str, str]] = []
    if run_builders:
        builder_steps = _run_builders(output_dir=output_dir, observed_utc=snapshot_utc)

    health_df = _read_csv(output_dir / HEALTH_PATH.name)
    actuals_df = _read_csv(output_dir / ACTUALS_PATH.name)
    review_df = _read_csv(output_dir / REVIEW_PATH.name)
    examples_df = _read_csv(output_dir / EXAMPLES_PATH.name)
    summary_live_df = _read_csv(SUMMARY_LIVE_PATH)
    identity_bridge_df = _read_csv(output_dir / IDENTITY_BRIDGE_PATH.name)
    sold_truth_queue_df = _read_csv(output_dir / SOLD_TRUTH_REPLAY_QUEUE_PATH.name)
    accuracy_summary_df = _read_csv(output_dir / ACCURACY_SUMMARY_PATH.name)

    health_metrics = _read_health_metrics(health_df)
    actuals_counts = _actuals_counts(actuals_df)
    review_counts = _review_counts(review_df)
    class_counts = _example_class_counts(examples_df)
    sold_truth_replay_queue_rows = _sold_truth_replay_queue_rows(sold_truth_queue_df)
    sold_decision_replay_coverage_rows = _to_int(
        _summary_metric_value(accuracy_summary_df, "sold_decision_replay_coverage_rows"),
        default=0,
    )
    sold_rows_total = _to_int(_summary_metric_value(accuracy_summary_df, "sold_rows_total"), default=0)
    direct_bridge_feasibility = _direct_bridge_feasibility(
        actuals_df=actuals_df,
        summary_df=summary_live_df,
        identity_df=identity_bridge_df,
    )
    scope_expansion_status = "not_run"
    if (
        run_builders
        and output_dir == DEFAULT_OUTPUT_DIR
        and actuals_counts["summary_direct_bridge_rows"] == 0
    ):
        try:
            hf010.build_scope_expansion(
                candidate_output_path=output_dir / SCOPE_EXPANSION_CANDIDATES_PATH.name,
                summary_output_path=output_dir / SCOPE_EXPANSION_SUMMARY_PATH.name,
            )
            scope_expansion_status = "built"
        except FileNotFoundError:
            scope_expansion_status = "missing_inputs"
        except Exception:
            scope_expansion_status = "build_error"
    scope_summary_df = _read_csv(output_dir / SCOPE_EXPANSION_SUMMARY_PATH.name)
    scope_metrics = _scope_expansion_metrics(scope_summary_df)

    freshness_fail_count = _to_int(health_metrics.get("freshness_fail_count", {}).get("value", ""))
    freshness_lag_minutes = _normalize_text(health_metrics.get("freshness_lag_minutes", {}).get("value", ""))
    freshness_status = _normalize_text(health_metrics.get("freshness_lag_minutes", {}).get("status", ""))

    hard_block_reasons: list[str] = []
    warnings: list[str] = []

    if freshness_fail_count > 0 or freshness_status == "fail":
        hard_block_reasons.append("freshness_fail_active")
    if actuals_counts["rows_total"] <= 0:
        hard_block_reasons.append("actuals_output_empty")
    if review_counts["rows_total"] <= 0:
        hard_block_reasons.append("review_output_empty")
    if int(len(examples_df.index)) <= 0:
        hard_block_reasons.append("example_output_empty")

    if actuals_counts["recovered_overlap_rows"] == 0:
        warnings.append("summary_asin_overlap_zero")
    elif actuals_counts["native_overlap_rows"] == 0 and actuals_counts["seed_replay_rows"] > 0:
        warnings.append("summary_asin_overlap_recovered_by_seed_replay")
    elif (
        actuals_counts["summary_direct_bridge_rows"] == 0
        and actuals_counts["summary_asin_rows"] == 0
        and actuals_counts["alignment_map_rows"] > 0
    ):
        warnings.append("summary_asin_overlap_recovered_by_alignment_map")
    if actuals_counts["summary_direct_bridge_rows"] == 0 and actuals_counts["recovered_overlap_rows"] > 0:
        warnings.append("summary_direct_bridge_overlap_zero")
    if (
        actuals_counts["summary_direct_bridge_rows"] == 0
        and scope_metrics["outside_h_scope_rows"] > 0
    ):
        if (
            direct_bridge_feasibility["summary_identity_pair_overlap_rows"] > 0
            and direct_bridge_feasibility["direct_bridge_feasible_pair_rows"] == 0
        ):
            warnings.append("summary_direct_bridge_no_feasible_overlap")
        else:
            warnings.append("scope_expansion_candidates_ready")
    if review_counts["rows_total"] > 0 and review_counts["pending_outcome_rows"] == review_counts["rows_total"]:
        warnings.append("all_review_rows_pending_outcome")

    no_coverage_rows = int(class_counts.get("no_operational_truth_coverage", 0))
    if review_counts["rows_total"] > 0 and no_coverage_rows == review_counts["rows_total"]:
        warnings.append("all_examples_no_operational_truth_coverage")
    if sold_truth_replay_queue_rows > 0:
        warnings.append("sold_truth_replay_capture_required")
    replay_target = 40
    if sold_rows_total > 0 and sold_decision_replay_coverage_rows < replay_target:
        warnings.append("sold_decision_replay_coverage_low")

    guard_status = "blocked" if hard_block_reasons else "ready"
    if guard_status == "blocked":
        readiness_label = "blocked"
    elif warnings:
        readiness_label = "ready_with_warnings"
    else:
        readiness_label = "ready_clean"

    next_action = "safe_for_scheduled_one_off"
    if "freshness_fail_active" in hard_block_reasons:
        next_action = "refresh_ledger_then_rerun_guarded_once"
    elif hard_block_reasons:
        next_action = "fix_blockers_then_rerun_guarded_once"
    elif "summary_asin_overlap_zero" in warnings:
        next_action = "run_overlap_recovery_then_repeat_cycle"
    elif "sold_truth_replay_capture_required" in warnings:
        next_action = "run_sold_truth_replay_capture_path"
    elif "sold_decision_replay_coverage_low" in warnings:
        next_action = "expand_sold_decision_replay_coverage"
    elif "summary_direct_bridge_no_feasible_overlap" in warnings:
        next_action = "expand_identity_bridge_resolution"
    elif "scope_expansion_candidates_ready" in warnings:
        next_action = "run_scope_expansion_capture_path"
    elif "summary_asin_overlap_recovered_by_seed_replay" in warnings:
        next_action = "monitor_seed_replay_and_expand_true_overlap"
    elif "summary_asin_overlap_recovered_by_alignment_map" in warnings:
        next_action = "monitor_alignment_map_and_expand_true_overlap"
    elif "summary_direct_bridge_overlap_zero" in warnings:
        next_action = "expand_identity_bridge_resolution"

    report = {
        "status": "success",
        "observed_utc": snapshot_utc,
        "pipeline": {
            "builders_run": "1" if run_builders else "0",
            "builder_steps": builder_steps,
        },
        "artifacts": {
            "health_csv": str(output_dir / HEALTH_PATH.name),
            "actuals_csv": str(output_dir / ACTUALS_PATH.name),
            "review_csv": str(output_dir / REVIEW_PATH.name),
            "examples_csv": str(output_dir / EXAMPLES_PATH.name),
            "sold_truth_replay_queue_csv": str(output_dir / SOLD_TRUTH_REPLAY_QUEUE_PATH.name),
            "scope_expansion_candidates_csv": str(output_dir / SCOPE_EXPANSION_CANDIDATES_PATH.name),
            "scope_expansion_summary_csv": str(output_dir / SCOPE_EXPANSION_SUMMARY_PATH.name),
        },
        "metrics": {
            "freshness_fail_count": freshness_fail_count,
            "freshness_lag_minutes": freshness_lag_minutes,
            "actuals_rows_total": actuals_counts["rows_total"],
            "actuals_summary_direct_bridge_rows": actuals_counts["summary_direct_bridge_rows"],
            "actuals_summary_asin_rows": actuals_counts["summary_asin_rows"],
            "actuals_alignment_map_rows": actuals_counts["alignment_map_rows"],
            "actuals_native_overlap_rows": actuals_counts["native_overlap_rows"],
            "actuals_seed_replay_rows": actuals_counts["seed_replay_rows"],
            "actuals_recovered_overlap_rows": actuals_counts["recovered_overlap_rows"],
            "actuals_operational_baseline_rows": actuals_counts["operational_baseline_rows"],
            "review_rows_total": review_counts["rows_total"],
            "review_pending_outcome_rows": review_counts["pending_outcome_rows"],
            "examples_rows_total": int(len(examples_df.index)),
            "example_class_counts": class_counts,
            "sold_truth_replay_queue_rows": sold_truth_replay_queue_rows,
            "sold_rows_total": sold_rows_total,
            "sold_decision_replay_coverage_rows": sold_decision_replay_coverage_rows,
            "scope_expansion_candidate_rows": scope_metrics["candidate_rows"],
            "scope_expansion_outside_h_scope_rows": scope_metrics["outside_h_scope_rows"],
            "scope_expansion_no_asin_rows": scope_metrics["no_asin_rows"],
            "scope_expansion_stale_source_rows": scope_metrics["stale_source_rows"],
            "scope_expansion_status": scope_expansion_status,
            "direct_bridge_baseline_asin_rows": direct_bridge_feasibility["baseline_asin_rows"],
            "direct_bridge_summary_identity_pair_overlap_rows": direct_bridge_feasibility[
                "summary_identity_pair_overlap_rows"
            ],
            "direct_bridge_feasible_pair_rows": direct_bridge_feasibility["direct_bridge_feasible_pair_rows"],
        },
        "guard_decision": {
            "guard_status": guard_status,
            "readiness_label": readiness_label,
            "hard_block_reasons": hard_block_reasons,
            "warnings": warnings,
            "next_action": next_action,
        },
    }

    ts_slug = _to_timestamp_slug(snapshot_utc)
    report_path = output_dir / f"bef_sales_feedback_guarded_run_{ts_slug}.json"
    report_latest_path = output_dir / LATEST_GUARD_REPORT_PATH.name
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return GuardedRunResult(
        report=report,
        report_path=report_path,
        report_latest_path=report_latest_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one guarded B/E/F sales-feedback execution and emit a gate report.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--observed-utc", default=None, help="Override observed UTC timestamp in ISO format.")
    parser.add_argument(
        "--skip-builders",
        action="store_true",
        help="Do not run BEF/F builders; evaluate gate using current latest artifacts only.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_sales_feedback_guarded_once(
        output_dir=Path(args.output_dir),
        observed_utc=args.observed_utc,
        run_builders=not args.skip_builders,
    )
    print(json.dumps(result.report))
    if result.report["guard_decision"]["guard_status"] != "ready":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
