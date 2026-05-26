from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
CANDIDATE_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_scope_expansion_candidates_latest.csv"
SUMMARY_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "hf_scope_expansion_summary_latest.csv"

IDENTITY_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv"
FOUNDATION_METRICS_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_foundation_metrics_latest.csv"
ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"

REQUIRED_INPUTS = [IDENTITY_PATH, FOUNDATION_METRICS_PATH, ALIGNMENT_PATH]

CAPTURE_OWNER_PATH = (
    "scripts/one_off/F007_prepare_targeted_rescrape_subset.py|"
    "scripts/flows/F/F061_run_legacy_first_checks_local.py|"
    "scripts/one_off/F008_capture_full_bbp_evidence_pack.py"
)

CANDIDATE_COLUMNS = [
    "observed_utc",
    "candidate_id",
    "supplier_id",
    "supplier_sku",
    "asin",
    "identity_status",
    "route_bucket",
    "in_h_scope_flag",
    "recommended_capture_path",
    "priority_rank",
    "current_alignment_class",
    "latest_source_utc",
    "latest_source_name",
    "route_reason",
]

SUMMARY_COLUMNS = ["snapshot_utc", "metric_name", "metric_value", "notes"]


@dataclass(frozen=True)
class ScopeExpansionBuildResult:
    candidate_output_path: Path
    candidate_rows: int
    summary_output_path: Path
    summary_rows: int
    outside_h_scope_rows: int
    no_asin_rows: int
    stale_source_rows: int


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def _read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required batch-001 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _safe_int(value: object, default: int = 0) -> int:
    text = _normalize_text(value)
    if text == "":
        return int(default)
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return int(default)


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required batch-001 input missing: {path}")


def _alignment_class_map(alignment_df: pd.DataFrame) -> tuple[dict[str, str], str]:
    if alignment_df.empty:
        return {}, ""
    work = pd.DataFrame()
    work["alignment_window_end_utc"] = alignment_df.get("alignment_window_end_utc", "").map(_normalize_text)
    work["asin"] = alignment_df.get("asin", "").map(_normalize_text)
    work["dominant_discrepancy_class"] = alignment_df.get("dominant_discrepancy_class", "").map(_normalize_text)
    work = work[(work["asin"] != "") & (work["dominant_discrepancy_class"] != "")].copy()
    if work.empty:
        latest_snapshot = _normalize_text(alignment_df.get("alignment_window_end_utc", pd.Series([], dtype=str)).max())
        return {}, latest_snapshot
    work = work.sort_values(["asin", "alignment_window_end_utc"], ascending=[True, False], kind="stable")
    work = work.drop_duplicates(subset=["asin"], keep="first")
    latest_snapshot = _normalize_text(work["alignment_window_end_utc"].max())
    return {row["asin"]: row["dominant_discrepancy_class"] for _, row in work.iterrows()}, latest_snapshot


def _route_fields(identity_status: str) -> tuple[str, int, str, int, str]:
    status = _normalize_text(identity_status)
    if status in {"RESOLVED_FROM_H_SNAPSHOT", "UNRESOLVED_AMBIGUOUS_ASIN"}:
        return (
            "already_in_h_scope",
            1,
            "already_in_h_scope_no_capture",
            90,
            "identity_status_maps_to_h_scope",
        )
    if status == "UNRESOLVED_ASIN_NOT_IN_H_SCOPE":
        return (
            "outside_h_scope_with_capture_path",
            0,
            CAPTURE_OWNER_PATH,
            10,
            "asin_present_outside_h_scope",
        )
    if status == "UNRESOLVED_NO_ASIN_SOURCE_STALE":
        return (
            "stale_source",
            0,
            CAPTURE_OWNER_PATH,
            20,
            "no_asin_and_source_stale",
        )
    if status == "UNRESOLVED_NO_ASIN":
        return (
            "no_asin",
            0,
            CAPTURE_OWNER_PATH,
            30,
            "no_asin_identity_incomplete",
        )
    if status == "UNRESOLVED_MULTI_ASIN":
        return (
            "asin_conflict",
            0,
            CAPTURE_OWNER_PATH,
            40,
            "multiple_asins_require_resolution",
        )
    return (
        "unclassified_blocker",
        0,
        CAPTURE_OWNER_PATH,
        50,
        f"unmapped_identity_status:{status or 'blank'}",
    )


def _build_candidates(
    *,
    identity_df: pd.DataFrame,
    alignment_class_by_asin: dict[str, str],
    observed_utc: str,
) -> tuple[pd.DataFrame, dict[str, int], int]:
    if identity_df.empty:
        empty_df = pd.DataFrame(columns=CANDIDATE_COLUMNS)
        return empty_df, {}, 0

    work = pd.DataFrame()
    work["candidate_id"] = identity_df.get("candidate_id", "").map(_normalize_text)
    work["supplier_id"] = identity_df.get("supplier_id", "").map(_normalize_text)
    work["supplier_sku"] = identity_df.get("supplier_sku", "").map(_normalize_text)
    work["asin"] = identity_df.get("asin", "").map(_normalize_text)
    work["identity_status"] = identity_df.get("sku_resolution_status", "").map(_normalize_text)
    work["latest_source_utc"] = identity_df.get("latest_source_utc", "").map(_normalize_text)
    work["latest_source_name"] = identity_df.get("latest_source_name", "").map(_normalize_text)
    work["row_sort_order"] = range(len(work.index))

    work = work.sort_values(
        ["candidate_id", "supplier_id", "supplier_sku", "latest_source_utc", "row_sort_order"],
        ascending=[True, True, True, False, False],
        kind="stable",
    )
    work = work.drop_duplicates(subset=["candidate_id", "supplier_id", "supplier_sku"], keep="first")
    work = work.drop(columns=["row_sort_order"])

    required_key_mask = (work["candidate_id"] != "") & (work["supplier_id"] != "") & (work["supplier_sku"] != "")
    dropped_missing_key_rows = int((~required_key_mask).sum())
    work = work[required_key_mask].copy()

    rows: list[dict[str, object]] = []
    for _, row in work.iterrows():
        route_bucket, in_scope_flag, capture_path, priority_group, route_reason = _route_fields(
            _normalize_text(row.get("identity_status", ""))
        )
        asin = _normalize_text(row.get("asin", ""))
        rows.append(
            {
                "observed_utc": observed_utc,
                "candidate_id": _normalize_text(row.get("candidate_id", "")),
                "supplier_id": _normalize_text(row.get("supplier_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "asin": asin,
                "identity_status": _normalize_text(row.get("identity_status", "")),
                "route_bucket": route_bucket,
                "in_h_scope_flag": int(in_scope_flag),
                "recommended_capture_path": capture_path,
                "priority_group": int(priority_group),
                "priority_rank": 0,
                "current_alignment_class": alignment_class_by_asin.get(asin, ""),
                "latest_source_utc": _normalize_text(row.get("latest_source_utc", "")),
                "latest_source_name": _normalize_text(row.get("latest_source_name", "")),
                "route_reason": route_reason,
            }
        )

    candidates = pd.DataFrame(rows).fillna("")
    if candidates.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS), {}, dropped_missing_key_rows

    candidates = candidates.sort_values(
        [
            "priority_group",
            "latest_source_utc",
            "candidate_id",
            "supplier_id",
            "supplier_sku",
        ],
        ascending=[True, True, True, True, True],
        kind="stable",
    ).reset_index(drop=True)
    candidates["priority_rank"] = [idx + 1 for idx in range(len(candidates.index))]

    route_counts: dict[str, int] = {}
    grouped = candidates.groupby("route_bucket", dropna=False).size()
    for key, count in grouped.items():
        route_counts[_normalize_text(key)] = int(count)

    candidates = candidates.drop(columns=["priority_group"])
    for column in CANDIDATE_COLUMNS:
        if column not in candidates.columns:
            candidates[column] = ""
    candidates = candidates[CANDIDATE_COLUMNS]
    for column in candidates.columns:
        if column in {"in_h_scope_flag", "priority_rank"}:
            continue
        candidates[column] = candidates[column].map(_normalize_text)
    return candidates, route_counts, dropped_missing_key_rows


def _build_summary(
    *,
    observed_utc: str,
    candidates_df: pd.DataFrame,
    route_counts: dict[str, int],
    dropped_missing_key_rows: int,
    foundation_df: pd.DataFrame,
    identity_df: pd.DataFrame,
    alignment_snapshot_utc: str,
) -> pd.DataFrame:
    metric_lookup: dict[str, str] = {}
    if not foundation_df.empty:
        for _, row in foundation_df.iterrows():
            metric_name = _normalize_text(row.get("metric_name", ""))
            metric_value = _normalize_text(row.get("metric_value", ""))
            if metric_name != "" and metric_name not in metric_lookup:
                metric_lookup[metric_name] = metric_value

    identity_snapshot_utc = _normalize_text(identity_df.get("snapshot_utc", pd.Series([], dtype=str)).max())
    foundation_snapshot_utc = _normalize_text(foundation_df.get("snapshot_utc", pd.Series([], dtype=str)).max())

    rows: list[dict[str, str]] = []

    def add(metric_name: str, metric_value: object, notes: str = "") -> None:
        rows.append(
            {
                "snapshot_utc": observed_utc,
                "metric_name": _normalize_text(metric_name),
                "metric_value": _normalize_text(metric_value),
                "notes": _normalize_text(notes),
            }
        )

    add("identity_snapshot_utc", identity_snapshot_utc)
    add("foundation_snapshot_utc", foundation_snapshot_utc)
    add("alignment_snapshot_utc", alignment_snapshot_utc)
    add("candidate_rows_total", len(candidates_df.index))
    add("candidate_rows_dropped_missing_key", dropped_missing_key_rows)

    for route_bucket in sorted(route_counts.keys()):
        add(f"route_bucket_count:{route_bucket}", route_counts[route_bucket])

    outside_count = int((candidates_df["route_bucket"] == "outside_h_scope_with_capture_path").sum()) if not candidates_df.empty else 0
    outside_unique_asin = (
        int(candidates_df.loc[candidates_df["route_bucket"] == "outside_h_scope_with_capture_path", "asin"].replace("", pd.NA).dropna().nunique())
        if not candidates_df.empty
        else 0
    )
    no_asin_count = int((candidates_df["route_bucket"] == "no_asin").sum()) if not candidates_df.empty else 0
    stale_count = int((candidates_df["route_bucket"] == "stale_source").sum()) if not candidates_df.empty else 0
    already_in_scope = int((candidates_df["route_bucket"] == "already_in_h_scope").sum()) if not candidates_df.empty else 0

    add("outside_h_scope_rows", outside_count)
    add("outside_h_scope_unique_asin", outside_unique_asin)
    add("no_asin_rows", no_asin_count)
    add("stale_source_rows", stale_count)
    add("already_in_h_scope_rows", already_in_scope)

    for metric_name in [
        "identity_rows_with_asin",
        "identity_rows_asin_in_h_scope",
        "identity_rows_asin_not_in_h_scope",
        "identity_asin_h_scope_overlap_rate",
    ]:
        add(f"foundation_metric:{metric_name}", metric_lookup.get(metric_name, ""))

    foundation_not_in_scope = _safe_int(metric_lookup.get("identity_rows_asin_not_in_h_scope", ""), default=-1)
    reconcile_status = "not_available"
    if foundation_not_in_scope >= 0:
        reconcile_status = "match" if foundation_not_in_scope == outside_count else "mismatch"
    add(
        "reconcile_identity_asin_not_in_scope_vs_outside_bucket",
        reconcile_status,
        f"foundation={foundation_not_in_scope if foundation_not_in_scope >= 0 else 'na'};outside={outside_count}",
    )

    summary_df = pd.DataFrame(rows, columns=SUMMARY_COLUMNS).fillna("")
    for column in summary_df.columns:
        summary_df[column] = summary_df[column].map(_normalize_text)
    return summary_df


def build_scope_expansion(
    *,
    candidate_output_path: Path,
    summary_output_path: Path,
) -> ScopeExpansionBuildResult:
    _ensure_required_inputs()
    observed_utc = _utc_now_iso()

    identity_df = _read_csv_required(IDENTITY_PATH)
    foundation_df = _read_csv_required(FOUNDATION_METRICS_PATH)
    alignment_df = _read_csv_required(ALIGNMENT_PATH)
    alignment_map, alignment_snapshot_utc = _alignment_class_map(alignment_df)

    candidates_df, route_counts, dropped_missing_key_rows = _build_candidates(
        identity_df=identity_df,
        alignment_class_by_asin=alignment_map,
        observed_utc=observed_utc,
    )

    summary_df = _build_summary(
        observed_utc=observed_utc,
        candidates_df=candidates_df,
        route_counts=route_counts,
        dropped_missing_key_rows=dropped_missing_key_rows,
        foundation_df=foundation_df,
        identity_df=identity_df,
        alignment_snapshot_utc=alignment_snapshot_utc,
    )

    candidate_output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    candidates_df.to_csv(candidate_output_path, index=False)
    summary_df.to_csv(summary_output_path, index=False)

    outside_count = int((candidates_df["route_bucket"] == "outside_h_scope_with_capture_path").sum()) if not candidates_df.empty else 0
    no_asin_count = int((candidates_df["route_bucket"] == "no_asin").sum()) if not candidates_df.empty else 0
    stale_count = int((candidates_df["route_bucket"] == "stale_source").sum()) if not candidates_df.empty else 0

    return ScopeExpansionBuildResult(
        candidate_output_path=candidate_output_path,
        candidate_rows=int(len(candidates_df.index)),
        summary_output_path=summary_output_path,
        summary_rows=int(len(summary_df.index)),
        outside_h_scope_rows=outside_count,
        no_asin_rows=no_asin_count,
        stale_source_rows=stale_count,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build HF scope expansion candidates and summary (Phase 1).")
    parser.add_argument(
        "--candidate-output",
        default=str(CANDIDATE_OUTPUT_PATH),
        help="Output CSV path for scope expansion candidates",
    )
    parser.add_argument(
        "--summary-output",
        default=str(SUMMARY_OUTPUT_PATH),
        help="Output CSV path for scope expansion summary",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_scope_expansion(
        candidate_output_path=Path(args.candidate_output),
        summary_output_path=Path(args.summary_output),
    )
    print(f"scope_candidate_output_path={result.candidate_output_path}")
    print(f"scope_candidate_rows={result.candidate_rows}")
    print(f"scope_summary_output_path={result.summary_output_path}")
    print(f"scope_summary_rows={result.summary_rows}")
    print(f"outside_h_scope_rows={result.outside_h_scope_rows}")
    print(f"no_asin_rows={result.no_asin_rows}")
    print(f"stale_source_rows={result.stale_source_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
