from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
DEFAULT_QUEUE_STATE_PATH = ROOT / "out" / "systems" / "F" / "inbox" / "supplier_price_list_queue_state.csv"
DEFAULT_ROW_STATE_PATH = ROOT / "out" / "systems" / "F" / "live" / "f_screening_row_state_live.csv"
DEFAULT_FIRST_CHECKS_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_first_checks_live.csv"
DEFAULT_SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
DEFAULT_RECOMMENDATIONS_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_candidate_recommendations_live.csv"
DEFAULT_APPROVAL_QUEUE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_approval_queue_live.csv"

BASELINE_COLUMNS = [
    "observed_utc",
    "active_supplier_id",
    "active_run_id",
    "queue_updated_at_utc",
    "raw_rows",
    "canonical_rows",
    "row_state_rows_active_supplier",
    "row_state_completed_rows",
    "row_state_pending_rows",
    "row_state_timeout_rows",
    "row_state_pass_rows",
    "row_state_rescan_rows",
    "row_state_fail_rows",
    "row_state_latest_updated_at_utc",
    "first_checks_rows",
    "first_checks_pass_rows",
    "scrape_rows",
    "scrape_pass_rows",
    "scrape_rescan_rows",
    "scrape_fail_rows",
    "recommendations_rows",
    "recommendations_active_supplier_rows",
    "recommendations_latest_utc",
    "recommendations_supplier_mismatch_flag",
    "recommendations_stale_vs_row_state_flag",
    "approval_rows",
    "approval_active_supplier_rows",
    "approval_latest_utc",
    "approval_supplier_mismatch_flag",
    "approval_stale_vs_row_state_flag",
    "derived_launch_surface_safe_flag",
    "completed_ratio",
    "pending_ratio",
    "launch_readiness_state",
    "launch_readiness_reason",
]

SUMMARY_COLUMNS = ["observed_utc", "metric", "value"]


@dataclass(frozen=True)
class LivePriceFileLaunchPackResult:
    baseline_df: pd.DataFrame
    summary_df: pd.DataFrame
    baseline_path: Path
    baseline_latest_path: Path
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
    if text.lower() in {"", "none", "null", "nan"}:
        return ""
    return text


def _normalize_key(value: object) -> str:
    return _normalize_text(value).lower()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        header = path.read_bytes()[:4]
    except OSError:
        header = b""
    # Some supplier feeds arrive as XLSX files with a .csv suffix.
    if header.startswith(b"PK"):
        try:
            return pd.read_excel(path, dtype=str).fillna("")
        except Exception:
            return pd.DataFrame()
    read_attempts = [
        {"dtype": str},
        {"dtype": str, "encoding": "utf-8-sig"},
        {"dtype": str, "encoding": "cp1252"},
        {"dtype": str, "encoding": "latin1"},
        {"dtype": str, "engine": "python", "on_bad_lines": "skip"},
    ]
    for kwargs in read_attempts:
        try:
            return pd.read_csv(path, **kwargs).fillna("")
        except (pd.errors.EmptyDataError, UnicodeDecodeError, pd.errors.ParserError, OSError):
            continue
    return pd.DataFrame()


def _num_text(value: int | float) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _utc_series_max(df: pd.DataFrame, *columns: str) -> str:
    best: pd.Timestamp | None = None
    for column in columns:
        if column not in df.columns:
            continue
        series = pd.to_datetime(df[column].map(_normalize_text), errors="coerce", utc=True)
        if series.empty:
            continue
        col_max = series.max()
        if pd.isna(col_max):
            continue
        if best is None or col_max > best:
            best = col_max
    if best is None:
        return ""
    return best.strftime("%Y-%m-%dT%H:%M:%SZ")


def _supplier_filtered(df: pd.DataFrame, active_supplier_id: str) -> pd.DataFrame:
    if df.empty:
        return df
    if "supplier_id" not in df.columns:
        return df
    key = _normalize_key(active_supplier_id)
    if key == "":
        return df.iloc[0:0].copy()
    work = df.copy()
    work["_supplier_key"] = work["supplier_id"].map(_normalize_key)
    out = work.loc[work["_supplier_key"] == key].copy()
    return out.drop(columns=["_supplier_key"], errors="ignore")


def _count_equals(df: pd.DataFrame, column: str, token: str) -> int:
    if df.empty or column not in df.columns:
        return 0
    target = _normalize_key(token)
    return int((df[column].map(_normalize_key) == target).sum())


def _stale_vs(reference_utc: str, candidate_utc: str) -> bool:
    if _normalize_text(reference_utc) == "" or _normalize_text(candidate_utc) == "":
        return False
    ref_ts = pd.to_datetime(reference_utc, errors="coerce", utc=True)
    cand_ts = pd.to_datetime(candidate_utc, errors="coerce", utc=True)
    if pd.isna(ref_ts) or pd.isna(cand_ts):
        return False
    return bool(cand_ts < ref_ts)


def _launch_readiness_state(
    *,
    active_supplier_id: str,
    row_state_rows: int,
    completed_rows: int,
    derived_safe: bool,
) -> tuple[str, str]:
    if _normalize_text(active_supplier_id) == "":
        return "not_ready_missing_active_supplier", "queue_state_has_no_active_supplier"
    if row_state_rows <= 0:
        return "not_ready_missing_screening_truth", "no_row_state_rows_for_active_supplier"
    if completed_rows <= 0:
        return "not_ready_no_completed_rows", "screening_has_not_produced_any_completed_rows"
    if not derived_safe:
        return (
            "ready_for_pass_review_with_stale_derived_surfaces",
            "use_row_state_truth_for_review;do_not_trust_stale_recommendation_or_approval_surfaces",
        )
    return "ready_for_pass_review", "active_supplier_wave_has_completed_rows_and_fresh_derived_surfaces"


def build_live_price_file_launch_pack(
    *,
    queue_state_path: Path = DEFAULT_QUEUE_STATE_PATH,
    row_state_path: Path = DEFAULT_ROW_STATE_PATH,
    first_checks_path: Path = DEFAULT_FIRST_CHECKS_PATH,
    scrape_evidence_path: Path = DEFAULT_SCRAPE_EVIDENCE_PATH,
    recommendations_path: Path = DEFAULT_RECOMMENDATIONS_PATH,
    approval_queue_path: Path = DEFAULT_APPROVAL_QUEUE_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    observed_utc: str | None = None,
) -> LivePriceFileLaunchPackResult:
    observed_utc_value = observed_utc or _utc_now_iso()
    ts_slug = _to_timestamp_slug(observed_utc_value)
    output_dir.mkdir(parents=True, exist_ok=True)

    queue_df = _read_csv(queue_state_path)
    queue_row = queue_df.iloc[0].to_dict() if not queue_df.empty else {}
    active_supplier_id = _normalize_text(queue_row.get("current_supplier_id", ""))
    active_run_id = _normalize_text(queue_row.get("current_run_id", ""))
    queue_updated_at_utc = _normalize_text(queue_row.get("updated_at_utc", ""))

    raw_path = queue_state_path.parent / "suppliers" / active_supplier_id / "raw_current.csv" if active_supplier_id else Path("")
    canonical_path = (
        queue_state_path.parent / "suppliers" / active_supplier_id / "canonical_current.csv" if active_supplier_id else Path("")
    )
    raw_df = _read_csv(raw_path) if active_supplier_id else pd.DataFrame()
    canonical_df = _read_csv(canonical_path) if active_supplier_id else pd.DataFrame()

    row_state_df = _read_csv(row_state_path)
    row_state_active_df = _supplier_filtered(row_state_df, active_supplier_id)
    row_state_latest_utc = _utc_series_max(row_state_active_df, "updated_at_utc", "observed_utc")

    row_state_rows = int(len(row_state_active_df.index))
    row_state_pending_rows = _count_equals(row_state_active_df, "row_status", "pending")
    row_state_timeout_rows = _count_equals(row_state_active_df, "row_status", "timeout")
    row_state_pass_rows = _count_equals(row_state_active_df, "row_status", "pass")
    row_state_rescan_rows = _count_equals(row_state_active_df, "status_reason", "RESCAN")
    row_state_fail_rows = _count_equals(row_state_active_df, "pf", "FAIL")
    row_state_completed_rows = row_state_timeout_rows + row_state_pass_rows

    first_checks_df = _read_csv(first_checks_path)
    first_checks_rows = int(len(first_checks_df.index))
    first_checks_pass_rows = _count_equals(first_checks_df, "pf", "PASS")

    scrape_df = _read_csv(scrape_evidence_path)
    scrape_rows = int(len(scrape_df.index))
    scrape_pass_rows = _count_equals(scrape_df, "pf", "PASS")
    scrape_rescan_rows = _count_equals(scrape_df, "pf", "RESCAN")
    scrape_fail_rows = _count_equals(scrape_df, "pf", "FAIL")

    recommendations_df = _read_csv(recommendations_path)
    recommendations_rows = int(len(recommendations_df.index))
    recommendations_active_df = _supplier_filtered(recommendations_df, active_supplier_id)
    recommendations_active_rows = int(len(recommendations_active_df.index))
    recommendations_latest_utc = _utc_series_max(recommendations_df, "recommendation_utc", "source_seen_at_utc")
    recommendations_supplier_mismatch = recommendations_rows > 0 and recommendations_active_rows == 0
    recommendations_stale = _stale_vs(row_state_latest_utc, recommendations_latest_utc)

    approval_df = _read_csv(approval_queue_path)
    approval_rows = int(len(approval_df.index))
    approval_active_df = _supplier_filtered(approval_df, active_supplier_id)
    approval_active_rows = int(len(approval_active_df.index))
    approval_latest_utc = _utc_series_max(approval_df, "queue_utc", "source_seen_at_utc")
    approval_supplier_mismatch = approval_rows > 0 and approval_active_rows == 0
    approval_stale = _stale_vs(row_state_latest_utc, approval_latest_utc)

    derived_safe = not (
        recommendations_supplier_mismatch
        or recommendations_stale
        or approval_supplier_mismatch
        or approval_stale
    )
    completed_ratio = float(row_state_completed_rows / row_state_rows) if row_state_rows > 0 else 0.0
    pending_ratio = float(row_state_pending_rows / row_state_rows) if row_state_rows > 0 else 0.0
    launch_readiness_state, launch_readiness_reason = _launch_readiness_state(
        active_supplier_id=active_supplier_id,
        row_state_rows=row_state_rows,
        completed_rows=row_state_completed_rows,
        derived_safe=derived_safe,
    )

    baseline_row = {
        "observed_utc": observed_utc_value,
        "active_supplier_id": active_supplier_id,
        "active_run_id": active_run_id,
        "queue_updated_at_utc": queue_updated_at_utc,
        "raw_rows": _num_text(int(len(raw_df.index))),
        "canonical_rows": _num_text(int(len(canonical_df.index))),
        "row_state_rows_active_supplier": _num_text(row_state_rows),
        "row_state_completed_rows": _num_text(row_state_completed_rows),
        "row_state_pending_rows": _num_text(row_state_pending_rows),
        "row_state_timeout_rows": _num_text(row_state_timeout_rows),
        "row_state_pass_rows": _num_text(row_state_pass_rows),
        "row_state_rescan_rows": _num_text(row_state_rescan_rows),
        "row_state_fail_rows": _num_text(row_state_fail_rows),
        "row_state_latest_updated_at_utc": row_state_latest_utc,
        "first_checks_rows": _num_text(first_checks_rows),
        "first_checks_pass_rows": _num_text(first_checks_pass_rows),
        "scrape_rows": _num_text(scrape_rows),
        "scrape_pass_rows": _num_text(scrape_pass_rows),
        "scrape_rescan_rows": _num_text(scrape_rescan_rows),
        "scrape_fail_rows": _num_text(scrape_fail_rows),
        "recommendations_rows": _num_text(recommendations_rows),
        "recommendations_active_supplier_rows": _num_text(recommendations_active_rows),
        "recommendations_latest_utc": recommendations_latest_utc,
        "recommendations_supplier_mismatch_flag": "1" if recommendations_supplier_mismatch else "0",
        "recommendations_stale_vs_row_state_flag": "1" if recommendations_stale else "0",
        "approval_rows": _num_text(approval_rows),
        "approval_active_supplier_rows": _num_text(approval_active_rows),
        "approval_latest_utc": approval_latest_utc,
        "approval_supplier_mismatch_flag": "1" if approval_supplier_mismatch else "0",
        "approval_stale_vs_row_state_flag": "1" if approval_stale else "0",
        "derived_launch_surface_safe_flag": "1" if derived_safe else "0",
        "completed_ratio": _num_text(completed_ratio),
        "pending_ratio": _num_text(pending_ratio),
        "launch_readiness_state": launch_readiness_state,
        "launch_readiness_reason": launch_readiness_reason,
    }
    baseline_df = pd.DataFrame([baseline_row], columns=BASELINE_COLUMNS)

    summary_rows: list[dict[str, str]] = [
        {"observed_utc": observed_utc_value, "metric": "active_supplier_id", "value": active_supplier_id},
        {"observed_utc": observed_utc_value, "metric": "active_run_id", "value": active_run_id},
        {"observed_utc": observed_utc_value, "metric": "raw_rows", "value": baseline_row["raw_rows"]},
        {"observed_utc": observed_utc_value, "metric": "canonical_rows", "value": baseline_row["canonical_rows"]},
        {
            "observed_utc": observed_utc_value,
            "metric": "row_state_rows_active_supplier",
            "value": baseline_row["row_state_rows_active_supplier"],
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "row_state_completed_rows",
            "value": baseline_row["row_state_completed_rows"],
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "row_state_pending_rows",
            "value": baseline_row["row_state_pending_rows"],
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "row_state_timeout_rows",
            "value": baseline_row["row_state_timeout_rows"],
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "row_state_pass_rows",
            "value": baseline_row["row_state_pass_rows"],
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "row_state_rescan_rows",
            "value": baseline_row["row_state_rescan_rows"],
        },
        {"observed_utc": observed_utc_value, "metric": "scrape_rows", "value": baseline_row["scrape_rows"]},
        {"observed_utc": observed_utc_value, "metric": "scrape_pass_rows", "value": baseline_row["scrape_pass_rows"]},
        {
            "observed_utc": observed_utc_value,
            "metric": "scrape_rescan_rows",
            "value": baseline_row["scrape_rescan_rows"],
        },
        {"observed_utc": observed_utc_value, "metric": "scrape_fail_rows", "value": baseline_row["scrape_fail_rows"]},
        {
            "observed_utc": observed_utc_value,
            "metric": "recommendations_rows",
            "value": baseline_row["recommendations_rows"],
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "recommendations_active_supplier_rows",
            "value": baseline_row["recommendations_active_supplier_rows"],
        },
        {"observed_utc": observed_utc_value, "metric": "approval_rows", "value": baseline_row["approval_rows"]},
        {
            "observed_utc": observed_utc_value,
            "metric": "approval_active_supplier_rows",
            "value": baseline_row["approval_active_supplier_rows"],
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "derived_launch_surface_safe_flag",
            "value": baseline_row["derived_launch_surface_safe_flag"],
        },
        {"observed_utc": observed_utc_value, "metric": "completed_ratio", "value": baseline_row["completed_ratio"]},
        {"observed_utc": observed_utc_value, "metric": "pending_ratio", "value": baseline_row["pending_ratio"]},
        {
            "observed_utc": observed_utc_value,
            "metric": "launch_readiness_state",
            "value": launch_readiness_state,
        },
        {
            "observed_utc": observed_utc_value,
            "metric": "launch_readiness_reason",
            "value": launch_readiness_reason,
        },
    ]
    summary_df = pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)

    baseline_path = output_dir / f"f_live_price_file_launch_baseline_{ts_slug}.csv"
    baseline_latest_path = output_dir / "f_live_price_file_launch_baseline_latest.csv"
    summary_path = output_dir / f"f_live_price_file_launch_summary_{ts_slug}.csv"
    summary_latest_path = output_dir / "f_live_price_file_launch_summary_latest.csv"

    baseline_df.to_csv(baseline_path, index=False)
    baseline_df.to_csv(baseline_latest_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    summary_df.to_csv(summary_latest_path, index=False)

    report = {
        "observed_utc": observed_utc_value,
        "active_supplier_id": active_supplier_id,
        "active_run_id": active_run_id,
        "row_state_rows_active_supplier": row_state_rows,
        "row_state_completed_rows": row_state_completed_rows,
        "row_state_pending_rows": row_state_pending_rows,
        "row_state_pass_rows": row_state_pass_rows,
        "row_state_timeout_rows": row_state_timeout_rows,
        "row_state_rescan_rows": row_state_rescan_rows,
        "scrape_rows": scrape_rows,
        "scrape_pass_rows": scrape_pass_rows,
        "scrape_rescan_rows": scrape_rescan_rows,
        "scrape_fail_rows": scrape_fail_rows,
        "recommendations_rows": recommendations_rows,
        "recommendations_active_supplier_rows": recommendations_active_rows,
        "approval_rows": approval_rows,
        "approval_active_supplier_rows": approval_active_rows,
        "derived_launch_surface_safe_flag": derived_safe,
        "launch_readiness_state": launch_readiness_state,
        "launch_readiness_reason": launch_readiness_reason,
        "baseline_latest_path": str(baseline_latest_path),
        "summary_latest_path": str(summary_latest_path),
    }

    return LivePriceFileLaunchPackResult(
        baseline_df=baseline_df,
        summary_df=summary_df,
        baseline_path=baseline_path,
        baseline_latest_path=baseline_latest_path,
        summary_path=summary_path,
        summary_latest_path=summary_latest_path,
        report=report,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build live supplier-wave launch baseline pack for active price file.")
    parser.add_argument(
        "--queue-state-path",
        type=Path,
        default=DEFAULT_QUEUE_STATE_PATH,
        help="Path to supplier queue state file.",
    )
    parser.add_argument(
        "--row-state-path",
        type=Path,
        default=DEFAULT_ROW_STATE_PATH,
        help="Path to canonical screening row-state live file.",
    )
    parser.add_argument(
        "--first-checks-path",
        type=Path,
        default=DEFAULT_FIRST_CHECKS_PATH,
        help="Path to feeder first-checks live file.",
    )
    parser.add_argument(
        "--scrape-evidence-path",
        type=Path,
        default=DEFAULT_SCRAPE_EVIDENCE_PATH,
        help="Path to feeder scrape evidence live file.",
    )
    parser.add_argument(
        "--recommendations-path",
        type=Path,
        default=DEFAULT_RECOMMENDATIONS_PATH,
        help="Path to feeder recommendations live file.",
    )
    parser.add_argument(
        "--approval-queue-path",
        type=Path,
        default=DEFAULT_APPROVAL_QUEUE_PATH,
        help="Path to feeder approval queue live file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where analysis report outputs are written.",
    )
    parser.add_argument(
        "--observed-utc",
        default="",
        help="Optional fixed observed UTC timestamp in format YYYY-MM-DDTHH:MM:SSZ.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_live_price_file_launch_pack(
        queue_state_path=args.queue_state_path,
        row_state_path=args.row_state_path,
        first_checks_path=args.first_checks_path,
        scrape_evidence_path=args.scrape_evidence_path,
        recommendations_path=args.recommendations_path,
        approval_queue_path=args.approval_queue_path,
        output_dir=args.output_dir,
        observed_utc=_normalize_text(args.observed_utc) or None,
    )
    print(json.dumps(result.report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
