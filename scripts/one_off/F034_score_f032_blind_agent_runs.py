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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_PLAN_DIR = ROOT / "plans" / "active" / "f-new-product-review-fail-automation-v1"
DEFAULT_EXPECTED_PATH = DEFAULT_PLAN_DIR / "f032_blind_validation_expected.csv"
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_RUN_GLOB = "f032_blind_agent_run_*_latest.csv"
DEFAULT_RESULTS_PATH = DEFAULT_OUTPUT_DIR / "f032_blind_validation_results_latest.csv"
DEFAULT_CASE_CONSISTENCY_PATH = DEFAULT_OUTPUT_DIR / "f032_blind_validation_case_consistency_latest.csv"
DEFAULT_HEALTH_PATH = DEFAULT_OUTPUT_DIR / "f032_blind_validation_score_health_latest.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "f032_blind_validation_score_summary_latest.md"

REQUIRED_RUN_COLUMNS = {
    "blind_case_id",
    "f032_action",
    "f032_decision_bucket",
}


@dataclass(frozen=True)
class F034Result:
    result_df: pd.DataFrame
    case_consistency_df: pd.DataFrame
    health_df: pd.DataFrame
    report: dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _acceptable_match(action: str, acceptable_actions: str) -> bool:
    allowed = {_normalize_text(item) for item in acceptable_actions.split("|") if _normalize_text(item)}
    return _normalize_text(action) in allowed


def _load_agent_runs(run_dir: Path, run_glob: str) -> tuple[pd.DataFrame, list[str], list[str]]:
    rows: list[dict[str, str]] = []
    files: list[str] = []
    missing_column_details: list[str] = []
    for path in sorted(run_dir.glob(run_glob)):
        df = _read_csv(path)
        run_name = path.stem.replace("_latest", "")
        files.append(str(path))
        missing = sorted(REQUIRED_RUN_COLUMNS - set(df.columns))
        if missing:
            missing_column_details.append(f"{path.name}:{','.join(missing)}")
            continue
        for _, row in df.iterrows():
            rows.append(
                {
                    "run_name": run_name,
                    "run_file": str(path),
                    "blind_case_id": _normalize_text(row.get("blind_case_id", "")),
                    "f032_action": _normalize_text(row.get("f032_action", "")),
                    "f032_decision_bucket": _normalize_text(row.get("f032_decision_bucket", "")),
                    "confidence": _normalize_text(row.get("confidence", "")),
                    "reason_short": _normalize_text(row.get("reason_short", "")),
                }
            )
    return pd.DataFrame(rows), files, missing_column_details


def _build_results(expected_df: pd.DataFrame, run_df: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    columns = [
        "observed_utc",
        "run_name",
        "blind_case_id",
        "supplier_sku",
        "asin",
        "expected_action",
        "acceptable_actions",
        "expected_bucket",
        "f032_action",
        "f032_decision_bucket",
        "action_exact_match",
        "action_acceptable_match",
        "bucket_exact_match",
        "confidence",
        "reason_short",
    ]
    if expected_df.empty or run_df.empty:
        return pd.DataFrame(columns=columns)
    work = run_df.merge(expected_df, on="blind_case_id", how="left", suffixes=("", "_expected")).fillna("")
    rows: list[dict[str, str]] = []
    for _, row in work.iterrows():
        action = _normalize_text(row.get("f032_action", ""))
        expected_action = _normalize_text(row.get("expected_action", ""))
        acceptable_actions = _normalize_text(row.get("acceptable_actions", ""))
        bucket = _normalize_text(row.get("f032_decision_bucket", ""))
        expected_bucket = _normalize_text(row.get("expected_bucket", ""))
        rows.append(
            {
                "observed_utc": observed_utc,
                "run_name": _normalize_text(row.get("run_name", "")),
                "blind_case_id": _normalize_text(row.get("blind_case_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "expected_action": expected_action,
                "acceptable_actions": acceptable_actions,
                "expected_bucket": expected_bucket,
                "f032_action": action,
                "f032_decision_bucket": bucket,
                "action_exact_match": "1" if action == expected_action else "0",
                "action_acceptable_match": "1" if _acceptable_match(action, acceptable_actions) else "0",
                "bucket_exact_match": "1" if bucket == expected_bucket else "0",
                "confidence": _normalize_text(row.get("confidence", "")),
                "reason_short": _normalize_text(row.get("reason_short", "")),
            }
        )
    return pd.DataFrame(rows, columns=columns).fillna("")


def _build_case_consistency(result_df: pd.DataFrame, expected_df: pd.DataFrame, observed_utc: str) -> pd.DataFrame:
    columns = [
        "observed_utc",
        "blind_case_id",
        "supplier_sku",
        "asin",
        "run_count",
        "unique_action_count",
        "unique_bucket_count",
        "action_consistent",
        "bucket_consistent",
        "fail_to_clear_flip",
        "actions_seen",
        "buckets_seen",
    ]
    if expected_df.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, str]] = []
    for _, expected in expected_df.iterrows():
        case_id = _normalize_text(expected.get("blind_case_id", ""))
        case = result_df[result_df["blind_case_id"] == case_id] if not result_df.empty else pd.DataFrame()
        actions = sorted({_normalize_text(value) for value in case.get("f032_action", pd.Series(dtype=str)).tolist() if _normalize_text(value)})
        buckets = sorted({_normalize_text(value) for value in case.get("f032_decision_bucket", pd.Series(dtype=str)).tolist() if _normalize_text(value)})
        fail_to_clear_flip = "remove_from_clean_pass" in actions and "allow_if_other_checks_pass" in actions
        rows.append(
            {
                "observed_utc": observed_utc,
                "blind_case_id": case_id,
                "supplier_sku": _normalize_text(expected.get("supplier_sku", "")),
                "asin": _normalize_text(expected.get("asin", "")),
                "run_count": str(len(case.index)),
                "unique_action_count": str(len(actions)),
                "unique_bucket_count": str(len(buckets)),
                "action_consistent": "1" if len(actions) == 1 else "0",
                "bucket_consistent": "1" if len(buckets) == 1 else "0",
                "fail_to_clear_flip": "1" if fail_to_clear_flip else "0",
                "actions_seen": "|".join(actions),
                "buckets_seen": "|".join(buckets),
            }
        )
    return pd.DataFrame(rows, columns=columns).fillna("")


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def _build_health(
    result_df: pd.DataFrame,
    case_consistency_df: pd.DataFrame,
    expected_df: pd.DataFrame,
    run_files: list[str],
    missing_column_details: list[str],
    observed_utc: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, str]] = []

    def add(metric: str, value: int | float | str, status: str, detail: str = "") -> None:
        rows.append({"observed_utc": observed_utc, "metric": metric, "value": str(value), "status": status, "detail": detail})

    expected_rows = len(expected_df.index)
    run_count = len(run_files)
    result_rows = len(result_df.index)
    expected_decision_rows = expected_rows * run_count
    exact_action_matches = int(result_df["action_exact_match"].eq("1").sum()) if not result_df.empty else 0
    acceptable_action_matches = int(result_df["action_acceptable_match"].eq("1").sum()) if not result_df.empty else 0
    bucket_matches = int(result_df["bucket_exact_match"].eq("1").sum()) if not result_df.empty else 0
    action_consistent_cases = int(case_consistency_df["action_consistent"].eq("1").sum()) if not case_consistency_df.empty else 0
    bucket_consistent_cases = int(case_consistency_df["bucket_consistent"].eq("1").sum()) if not case_consistency_df.empty else 0
    fail_to_clear_flips = int(case_consistency_df["fail_to_clear_flip"].eq("1").sum()) if not case_consistency_df.empty else 0
    exact_action_pct = _pct(exact_action_matches, result_rows)
    acceptable_action_pct = _pct(acceptable_action_matches, result_rows)
    bucket_pct = _pct(bucket_matches, result_rows)
    action_consistency_pct = _pct(action_consistent_cases, expected_rows)
    bucket_consistency_pct = _pct(bucket_consistent_cases, expected_rows)

    expected_action_counts = expected_df["expected_action"].value_counts().to_dict() if not expected_df.empty else {}
    min_seed_ready = (
        int(expected_action_counts.get("allow_if_other_checks_pass", 0)) >= 20
        and int(expected_action_counts.get("remove_from_clean_pass", 0)) >= 20
        and int(expected_action_counts.get("manual_review", 0)) >= 20
    )

    add("agent_run_file_count", run_count, "PASS" if run_count >= 3 else "WARN", "target is 3 consistency runs")
    add("expected_rows", expected_rows, "PASS" if expected_rows else "FAIL")
    add("agent_decision_rows", result_rows, "PASS" if result_rows == expected_decision_rows else "FAIL")
    add("run_files_missing_required_columns", len(missing_column_details), "FAIL" if missing_column_details else "PASS", "|".join(missing_column_details))
    add("acceptable_action_agreement_pct", acceptable_action_pct, "PASS" if acceptable_action_pct >= 95.0 else "WARN")
    add("exact_action_agreement_pct", exact_action_pct, "PASS" if exact_action_pct >= 95.0 else "WARN")
    add("exact_bucket_agreement_pct", bucket_pct, "PASS" if bucket_pct >= 90.0 else "WARN")
    add("action_consistency_pct", action_consistency_pct, "PASS" if action_consistency_pct >= 98.0 else "WARN")
    add("bucket_consistency_pct", bucket_consistency_pct, "PASS" if bucket_consistency_pct >= 95.0 else "WARN")
    add("fail_to_clear_flip_cases", fail_to_clear_flips, "FAIL" if fail_to_clear_flips else "PASS")
    add("minimum_seed_set_ready", "yes" if min_seed_ready else "no", "PASS" if min_seed_ready else "WARN")

    report = {
        "observed_utc": observed_utc,
        "agent_run_file_count": run_count,
        "expected_rows": expected_rows,
        "agent_decision_rows": result_rows,
        "acceptable_action_agreement_pct": acceptable_action_pct,
        "exact_action_agreement_pct": exact_action_pct,
        "exact_bucket_agreement_pct": bucket_pct,
        "action_consistency_pct": action_consistency_pct,
        "bucket_consistency_pct": bucket_consistency_pct,
        "fail_to_clear_flip_cases": fail_to_clear_flips,
        "minimum_seed_set_ready": "yes" if min_seed_ready else "no",
        "health_fail_rows": int(sum(1 for row in rows if row["status"] == "FAIL")),
        "health_warn_rows": int(sum(1 for row in rows if row["status"] == "WARN")),
    }
    return pd.DataFrame(rows), report


def _write_outputs(
    results_path: Path,
    case_consistency_path: Path,
    health_path: Path,
    summary_path: Path,
    result: F034Result,
) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    case_consistency_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    result.result_df.to_csv(results_path, index=False)
    result.case_consistency_df.to_csv(case_consistency_path, index=False)
    result.health_df.to_csv(health_path, index=False)
    lines = [
        "# F032 Blind Validation Score Summary",
        "",
        f"- observed_utc: `{result.report['observed_utc']}`",
        f"- agent_run_file_count: `{result.report['agent_run_file_count']}`",
        f"- expected_rows: `{result.report['expected_rows']}`",
        f"- agent_decision_rows: `{result.report['agent_decision_rows']}`",
        f"- acceptable_action_agreement_pct: `{result.report['acceptable_action_agreement_pct']}`",
        f"- exact_action_agreement_pct: `{result.report['exact_action_agreement_pct']}`",
        f"- exact_bucket_agreement_pct: `{result.report['exact_bucket_agreement_pct']}`",
        f"- action_consistency_pct: `{result.report['action_consistency_pct']}`",
        f"- bucket_consistency_pct: `{result.report['bucket_consistency_pct']}`",
        f"- fail_to_clear_flip_cases: `{result.report['fail_to_clear_flip_cases']}`",
        f"- minimum_seed_set_ready: `{result.report['minimum_seed_set_ready']}`",
        "",
        "## Health",
        "",
    ]
    for row in result.health_df.to_dict("records"):
        lines.append(f"- {row['metric']}: `{row['value']}` ({row['status']})")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def score_f032_blind_agent_runs(
    *,
    expected_path: Path = DEFAULT_EXPECTED_PATH,
    run_dir: Path = DEFAULT_OUTPUT_DIR,
    run_glob: str = DEFAULT_RUN_GLOB,
    results_path: Path = DEFAULT_RESULTS_PATH,
    case_consistency_path: Path = DEFAULT_CASE_CONSISTENCY_PATH,
    health_path: Path = DEFAULT_HEALTH_PATH,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    observed_utc: str | None = None,
    write_outputs: bool = True,
) -> F034Result:
    observed = observed_utc or _utc_now_iso()
    expected_df = _read_csv(expected_path)
    run_df, run_files, missing_column_details = _load_agent_runs(run_dir, run_glob)
    result_df = _build_results(expected_df, run_df, observed)
    case_consistency_df = _build_case_consistency(result_df, expected_df, observed)
    health_df, report = _build_health(result_df, case_consistency_df, expected_df, run_files, missing_column_details, observed)
    result = F034Result(result_df=result_df, case_consistency_df=case_consistency_df, health_df=health_df, report=report)
    if write_outputs:
        _write_outputs(results_path, case_consistency_path, health_path, summary_path, result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score F032 blind agent run outputs against the hidden expected-answer file.")
    parser.add_argument("--expected-path", type=Path, default=DEFAULT_EXPECTED_PATH)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-glob", default=DEFAULT_RUN_GLOB)
    parser.add_argument("--results-path", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--case-consistency-path", type=Path, default=DEFAULT_CASE_CONSISTENCY_PATH)
    parser.add_argument("--health-path", type=Path, default=DEFAULT_HEALTH_PATH)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = score_f032_blind_agent_runs(
        expected_path=args.expected_path,
        run_dir=args.run_dir,
        run_glob=args.run_glob,
        results_path=args.results_path,
        case_consistency_path=args.case_consistency_path,
        health_path=args.health_path,
        summary_path=args.summary_path,
        observed_utc=_normalize_text(args.observed_utc) or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
