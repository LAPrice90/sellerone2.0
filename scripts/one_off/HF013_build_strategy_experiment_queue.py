from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "out" / "analysis_reports" / "hf_strategy_experiment_queue_latest.csv"

SCORECARD_PATH = ROOT / "out" / "analysis_reports" / "hf_strategy_scorecard_latest.csv"
REVIEW_PACK_PATH = ROOT / "out" / "reports" / "hf_strategy_review_pack_latest.csv"

REQUIRED_INPUTS = [SCORECARD_PATH, REVIEW_PACK_PATH]

QUEUE_COLUMNS = [
    "snapshot_utc",
    "experiment_id",
    "scenario_type",
    "shadow_only_flag",
    "risk_gate_status",
    "sample_mature_flag",
    "max_cohort_size",
    "required_review_reason",
    "review_status",
    "decision_rows",
    "sample_min_rows",
    "write_applied_rate",
    "failed_rate",
    "expired_rate",
    "source_scorecard_snapshot_utc",
    "source_review_snapshot_utc",
]


@dataclass(frozen=True)
class StrategyExperimentQueueResult:
    output_path: Path
    rows: int
    pass_rows: int
    review_rows: int
    fail_rows: int


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


def _to_float(value: object, default: float = 0.0) -> float:
    text = _normalize_text(value)
    if text == "":
        return float(default)
    try:
        return float(text)
    except (TypeError, ValueError):
        return float(default)


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required batch-004 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required batch-004 input missing: {path}")


def _scenario_recommendation_map(review_df: pd.DataFrame) -> dict[str, str]:
    if review_df.empty:
        return {}
    work = review_df.copy()
    work["review_section"] = work.get("review_section", "").map(_normalize_text)
    work["scenario_type"] = work.get("scenario_type", "").map(_normalize_text)
    work["recommendation"] = work.get("recommendation", "").map(_normalize_text)
    work = work[(work["review_section"] == "tactic_scorecard") & (work["scenario_type"] != "")].copy()
    if work.empty:
        return {}
    work = work.sort_values(["scenario_type", "recommendation"], ascending=[True, True], kind="stable")
    work = work.drop_duplicates(subset=["scenario_type"], keep="first")
    return {row["scenario_type"]: row["recommendation"] for _, row in work.iterrows()}


def _risk_gate(
    *,
    sample_mature_flag: int,
    review_status: str,
    failed_rate: float,
    expired_rate: float,
    write_applied_rate: float,
) -> tuple[str, str]:
    status = _normalize_text(review_status)
    if sample_mature_flag != 1:
        return "fail", "sample_below_min_rows"
    if status in {"overlap_first", "blocked"}:
        if status == "overlap_first":
            return "fail", "missing_baseline_overlap_recovery_required"
        return "fail", "blocked_in_scorecard"
    if failed_rate > 0.35:
        return "review", "failed_rate_above_35pct"
    if expired_rate > 0.60:
        return "review", "expired_rate_above_60pct"
    if write_applied_rate <= 0.02:
        return "review", "write_applied_rate_below_2pct"
    return "pass", "eligible_shadow_no_live_promotion"


def _max_cohort_size(*, risk_gate_status: str, decision_rows: int) -> int:
    if risk_gate_status == "pass":
        candidate = int(round(decision_rows * 0.10))
        candidate = max(candidate, 10)
        return min(candidate, 50)
    if risk_gate_status == "review":
        return 10
    return 0


def _experiment_id(scenario_type: str) -> str:
    clean = _normalize_text(scenario_type).upper().replace("_", "-")
    return f"HFEXP-{clean}" if clean else "HFEXP-UNKNOWN"


def build_strategy_experiment_queue(*, output_path: Path) -> StrategyExperimentQueueResult:
    _ensure_required_inputs()
    snapshot_utc = _utc_now_iso()

    scorecard_df = _read_csv_required(SCORECARD_PATH)
    review_df = _read_csv_required(REVIEW_PACK_PATH)

    review_recommendation = _scenario_recommendation_map(review_df)
    scorecard_snapshot_utc = _normalize_text(scorecard_df.get("snapshot_utc", pd.Series([], dtype=str)).max())
    review_snapshot_utc = _normalize_text(review_df.get("snapshot_utc", pd.Series([], dtype=str)).max())

    rows: list[dict[str, str]] = []
    if not scorecard_df.empty:
        work = scorecard_df.copy()
        work["scenario_type"] = work.get("scenario_type", "").map(_normalize_text)
        work = work[work["scenario_type"] != ""].copy()
        work = work.sort_values(["scenario_type"], ascending=[True], kind="stable")

        for _, row in work.iterrows():
            scenario_type = _normalize_text(row.get("scenario_type", ""))
            sample_mature_flag = 1 if _to_int(row.get("sample_mature_flag", 0)) == 1 else 0
            review_status = _normalize_text(row.get("review_status", ""))
            decision_rows = max(_to_int(row.get("decision_rows", 0)), 0)
            sample_min_rows = max(_to_int(row.get("sample_min_rows", 0)), 0)
            write_applied_rate = _to_float(row.get("write_applied_rate", 0.0))
            failed_rate = _to_float(row.get("failed_rate", 0.0))
            expired_rate = _to_float(row.get("expired_rate", 0.0))
            gate_status, base_reason = _risk_gate(
                sample_mature_flag=sample_mature_flag,
                review_status=review_status,
                failed_rate=failed_rate,
                expired_rate=expired_rate,
                write_applied_rate=write_applied_rate,
            )
            recommendation = _normalize_text(review_recommendation.get(scenario_type, ""))
            required_reason = base_reason if recommendation == "" else f"{base_reason}|{recommendation}"
            max_cohort_size = _max_cohort_size(risk_gate_status=gate_status, decision_rows=decision_rows)

            rows.append(
                {
                    "snapshot_utc": snapshot_utc,
                    "experiment_id": _experiment_id(scenario_type),
                    "scenario_type": scenario_type,
                    "shadow_only_flag": "1",
                    "risk_gate_status": gate_status,
                    "sample_mature_flag": str(sample_mature_flag),
                    "max_cohort_size": str(max_cohort_size),
                    "required_review_reason": required_reason,
                    "review_status": review_status,
                    "decision_rows": str(decision_rows),
                    "sample_min_rows": str(sample_min_rows),
                    "write_applied_rate": _normalize_text(row.get("write_applied_rate", "")),
                    "failed_rate": _normalize_text(row.get("failed_rate", "")),
                    "expired_rate": _normalize_text(row.get("expired_rate", "")),
                    "source_scorecard_snapshot_utc": scorecard_snapshot_utc,
                    "source_review_snapshot_utc": review_snapshot_utc,
                }
            )

    queue_df = pd.DataFrame(rows).fillna("")
    if not queue_df.empty:
        queue_df = queue_df.sort_values(["scenario_type"], ascending=[True], kind="stable")
    for column in QUEUE_COLUMNS:
        if column not in queue_df.columns:
            queue_df[column] = ""
    queue_df = queue_df[QUEUE_COLUMNS]
    for column in queue_df.columns:
        queue_df[column] = queue_df[column].map(_normalize_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    queue_df.to_csv(output_path, index=False)

    pass_rows = int((queue_df["risk_gate_status"] == "pass").sum()) if not queue_df.empty else 0
    review_rows = int((queue_df["risk_gate_status"] == "review").sum()) if not queue_df.empty else 0
    fail_rows = int((queue_df["risk_gate_status"] == "fail").sum()) if not queue_df.empty else 0
    return StrategyExperimentQueueResult(
        output_path=output_path,
        rows=int(len(queue_df.index)),
        pass_rows=pass_rows,
        review_rows=review_rows,
        fail_rows=fail_rows,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build HF strategy experiment queue (Phase 4).")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path for strategy experiment queue")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_strategy_experiment_queue(output_path=Path(args.output))
    print(f"strategy_experiment_queue_output_path={result.output_path}")
    print(f"strategy_experiment_queue_rows={result.rows}")
    print(f"strategy_experiment_queue_pass_rows={result.pass_rows}")
    print(f"strategy_experiment_queue_review_rows={result.review_rows}")
    print(f"strategy_experiment_queue_fail_rows={result.fail_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
