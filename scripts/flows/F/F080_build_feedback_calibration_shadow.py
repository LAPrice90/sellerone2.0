from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract


OUTPUT_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_feedback_calibration_live.csv"

FACTOR_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_factor_impacts_latest.csv"
ALIGNMENT_PATH = ROOT / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
QUEUE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_approval_queue_live.csv"
DECISIONS_PATH = ROOT / "out" / "systems" / "F" / "history" / "feeder_approval_decisions_log.csv"
SCRAPE_EVIDENCE_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv"
SCRAPE_CHART_PATH = ROOT / "out" / "systems" / "F" / "live" / "feeder_legacy_chart_daily_raw_live.csv"

REQUIRED_INPUTS = [
    FACTOR_PATH,
    ALIGNMENT_PATH,
    QUEUE_PATH,
    DECISIONS_PATH,
    SCRAPE_EVIDENCE_PATH,
    SCRAPE_CHART_PATH,
]

WATCHED_SOURCE_FILES = [
    QUEUE_PATH,
    DECISIONS_PATH,
    SCRAPE_EVIDENCE_PATH,
    SCRAPE_CHART_PATH,
]


@dataclass(frozen=True)
class ShadowBuildResult:
    output_path: Path
    output_rows: int
    queue_rows: int
    decision_rows: int
    source_hash_verified: bool


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
        raise FileNotFoundError(f"required phase-4 input missing: {path}")
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _ensure_required_inputs() -> None:
    for path in REQUIRED_INPUTS:
        if not path.exists():
            raise FileNotFoundError(f"required phase-4 input missing: {path}")


def build_shadow_calibration(
    *,
    root: Path | None = None,
    output_path: Path = OUTPUT_PATH,
    observed_utc: str | None = None,
) -> ShadowBuildResult:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    _ensure_required_inputs()
    snapshot_utc = observed_utc or _utc_now_iso()

    source_hash_before = {path: _sha256_file(path) for path in WATCHED_SOURCE_FILES}

    factor_df = _read_csv_required(FACTOR_PATH)
    alignment_df = _read_csv_required(ALIGNMENT_PATH)
    queue_df = _read_csv_required(QUEUE_PATH)
    decisions_df = _read_csv_required(DECISIONS_PATH)
    _ = _read_csv_required(SCRAPE_EVIDENCE_PATH)
    _ = _read_csv_required(SCRAPE_CHART_PATH)

    queue_rows = int(len(queue_df.index))
    decision_rows = int(len(decisions_df.index))
    queue_hash = source_hash_before[QUEUE_PATH]
    decision_hash = source_hash_before[DECISIONS_PATH]

    alignment_class_counts: dict[str, int] = {}
    if not alignment_df.empty and "dominant_discrepancy_class" in alignment_df.columns:
        grouped = alignment_df.groupby("dominant_discrepancy_class").size()
        for key, count in grouped.items():
            alignment_class_counts[_normalize_text(key)] = int(count)

    rows: list[dict[str, str]] = []
    if factor_df.empty:
        rows.append(
            {
                "observed_utc": snapshot_utc,
                "factor_bucket": "NO_FACTOR_DATA",
                "sample_rows": "0",
                "avg_units_error_pct": "",
                "avg_profit_error_pct": "",
                "avg_seller_count": "",
                "amazon_presence_share_pct": "",
                "rescrape_trigger_flag": "0",
                "rescrape_trigger_reason": "no_factor_data",
                "rescrape_owner_path": "",
                "recommended_collection_mode": "F061_MODE=data_collection",
                "alignment_class_rows": "0",
                "queue_rows_current": str(queue_rows),
                "decision_rows_current": str(decision_rows),
                "queue_snapshot_hash": queue_hash,
                "decision_snapshot_hash": decision_hash,
                "source_alignment_path": str(ALIGNMENT_PATH),
                "source_factor_path": str(FACTOR_PATH),
                "shadow_only_flag": "1",
                "apply_to_live_decisions_flag": "0",
                "calibration_status": "shadow_blocked_no_factor_data",
            }
        )
    else:
        for _, row in factor_df.iterrows():
            bucket = _normalize_text(row.get("factor_bucket", ""))
            sample_rows = _normalize_text(row.get("sample_rows", "0"))
            bucket_sample = int(sample_rows) if sample_rows.isdigit() else 0
            rows.append(
                {
                    "observed_utc": snapshot_utc,
                    "factor_bucket": bucket,
                    "sample_rows": sample_rows,
                    "avg_units_error_pct": _normalize_text(row.get("avg_units_error_pct", "")),
                    "avg_profit_error_pct": _normalize_text(row.get("avg_profit_error_pct", "")),
                    "avg_seller_count": _normalize_text(row.get("avg_seller_count", "")),
                    "amazon_presence_share_pct": _normalize_text(row.get("amazon_presence_share_pct", "")),
                    "rescrape_trigger_flag": _normalize_text(row.get("rescrape_trigger_flag", "")),
                    "rescrape_trigger_reason": _normalize_text(row.get("rescrape_trigger_reason", "")),
                    "rescrape_owner_path": _normalize_text(row.get("rescrape_owner_path", "")),
                    "recommended_collection_mode": _normalize_text(row.get("recommended_collection_mode", "F061_MODE=data_collection")),
                    "alignment_class_rows": str(alignment_class_counts.get(bucket, 0)),
                    "queue_rows_current": str(queue_rows),
                    "decision_rows_current": str(decision_rows),
                    "queue_snapshot_hash": queue_hash,
                    "decision_snapshot_hash": decision_hash,
                    "source_alignment_path": str(ALIGNMENT_PATH),
                    "source_factor_path": str(FACTOR_PATH),
                    "shadow_only_flag": "1",
                    "apply_to_live_decisions_flag": "0",
                    "calibration_status": "shadow_ready" if bucket_sample >= 10 else "shadow_thin_sample",
                }
            )

    out_df = pd.DataFrame(rows).fillna("")
    ordered_columns = [
        "observed_utc",
        "factor_bucket",
        "sample_rows",
        "avg_units_error_pct",
        "avg_profit_error_pct",
        "avg_seller_count",
        "amazon_presence_share_pct",
        "rescrape_trigger_flag",
        "rescrape_trigger_reason",
        "rescrape_owner_path",
        "recommended_collection_mode",
        "alignment_class_rows",
        "queue_rows_current",
        "decision_rows_current",
        "queue_snapshot_hash",
        "decision_snapshot_hash",
        "source_alignment_path",
        "source_factor_path",
        "shadow_only_flag",
        "apply_to_live_decisions_flag",
        "calibration_status",
    ]
    for column in ordered_columns:
        if column not in out_df.columns:
            out_df[column] = ""
    out_df = out_df[ordered_columns]
    for column in out_df.columns:
        out_df[column] = out_df[column].map(_normalize_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)

    source_hash_after = {path: _sha256_file(path) for path in WATCHED_SOURCE_FILES}
    source_hash_verified = source_hash_before == source_hash_after
    if not source_hash_verified:
        raise RuntimeError("source mutation detected while building shadow calibration")

    return ShadowBuildResult(
        output_path=output_path,
        output_rows=int(len(out_df.index)),
        queue_rows=queue_rows,
        decision_rows=decision_rows,
        source_hash_verified=source_hash_verified,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build F shadow calibration output from HF factor impacts (Phase 4).")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_shadow_calibration(output_path=Path(args.output))
    print(f"shadow_output_path={result.output_path}")
    print(f"shadow_output_rows={result.output_rows}")
    print(f"queue_rows_current={result.queue_rows}")
    print(f"decision_rows_current={result.decision_rows}")
    print(f"source_hash_verified={int(result.source_hash_verified)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
