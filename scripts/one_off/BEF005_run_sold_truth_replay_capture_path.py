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

from scripts.one_off import BEF004_run_sales_feedback_guarded_once as bef004
from scripts.one_off import F008_capture_full_bbp_evidence_pack as f008
from scripts.one_off import F009_build_full_capture_consistency_audit as f009
from scripts.one_off import F011_build_sales_history_accuracy_pack as f011
from scripts.one_off import HF001_build_learning_baseline as hf001
from scripts.one_off import HF002_build_learning_alignment as hf002
from scripts.one_off import HF003_build_learning_health_checks as hf003
from scripts.one_off import HF005_build_learning_operator_report as hf005

QUEUE_PATH = DEFAULT_OUTPUT_DIR / "f_sold_truth_replay_capture_queue_latest.csv"
CAPTURE_PACK_LATEST_PATH = DEFAULT_OUTPUT_DIR / "f_sold_truth_replay_capture_pack_latest.csv"
MANIFEST_LATEST_PATH = DEFAULT_OUTPUT_DIR / "f_full_capture_manifest_latest.csv"
LATEST_REPORT_PATH = DEFAULT_OUTPUT_DIR / "bef_sold_truth_replay_capture_latest.json"


@dataclass(frozen=True)
class SoldTruthReplayCaptureResult:
    report: dict[str, Any]
    report_path: Path
    report_latest_path: Path
    capture_pack_path: Path
    capture_pack_latest_path: Path


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


def _capture_pack_from_queue(queue_df: pd.DataFrame, *, max_asins: int) -> pd.DataFrame:
    if queue_df.empty:
        return pd.DataFrame(
            columns=[
                "asin",
                "supplier_sku",
                "validation_case",
                "sample_rank",
                "amazon_link",
                "queue_observed_utc",
                "capture_reason",
            ]
        )

    work = pd.DataFrame()
    work["asin"] = queue_df.get("asin", "").map(_normalize_text)
    work["supplier_sku"] = queue_df.get("seller_sku", "").map(_normalize_text)
    work["amazon_link"] = queue_df.get("amazon_link", "").map(_normalize_text)
    work["queue_observed_utc"] = queue_df.get("observed_utc", "").map(_normalize_text)
    work["capture_reason"] = queue_df.get("capture_reason", "").map(_normalize_text)
    work["asin_key"] = work["asin"].map(_normalize_key)
    work = work[work["asin_key"] != ""].copy()
    if work.empty:
        return pd.DataFrame(
            columns=[
                "asin",
                "supplier_sku",
                "validation_case",
                "sample_rank",
                "amazon_link",
                "queue_observed_utc",
                "capture_reason",
            ]
        )

    work["_obs_ts"] = pd.to_datetime(work["queue_observed_utc"], errors="coerce", utc=True)
    work = work.sort_values(["asin_key", "_obs_ts"], ascending=[True, False], kind="stable")
    work = work.drop_duplicates(subset=["asin_key"], keep="first").reset_index(drop=True)
    if max_asins > 0:
        work = work.iloc[:max_asins].copy()
    work["validation_case"] = "sold_truth_replay_capture"
    work["sample_rank"] = [str(idx) for idx in range(1, len(work.index) + 1)]
    work = work[
        [
            "asin",
            "supplier_sku",
            "validation_case",
            "sample_rank",
            "amazon_link",
            "queue_observed_utc",
            "capture_reason",
        ]
    ].copy()
    return work.fillna("")


def _build_manifest_union_temp(*, output_dir: Path) -> Path:
    manifest_paths = sorted(output_dir.glob("f_full_capture_manifest_*.csv"))
    if MANIFEST_LATEST_PATH.exists():
        manifest_paths.append(MANIFEST_LATEST_PATH)

    frames: list[pd.DataFrame] = []
    for path in manifest_paths:
        df = _read_csv(path)
        if df.empty:
            continue
        df["_source_path"] = str(path)
        frames.append(df)

    if not frames:
        tmp_path = output_dir / "_tmp_bef005_manifest_union.csv"
        pd.DataFrame(columns=["observed_utc", "run_id", "asin"]).to_csv(tmp_path, index=False)
        return tmp_path

    union_df = pd.concat(frames, ignore_index=True).fillna("")
    if "run_id" in union_df.columns:
        union_df["run_id"] = union_df["run_id"].map(_normalize_text)
        union_df["observed_utc"] = union_df.get("observed_utc", "").map(_normalize_text)
        union_df = union_df.sort_values(
            ["run_id", "observed_utc", "_source_path"],
            ascending=[True, False, True],
            kind="stable",
        )
        union_df = union_df.drop_duplicates(subset=["run_id"], keep="first")
    union_df = union_df.drop(columns=["_source_path"], errors="ignore")

    tmp_path = output_dir / "_tmp_bef005_manifest_union.csv"
    union_df.to_csv(tmp_path, index=False)
    return tmp_path


def _run_post_capture_rebuild_chain(*, output_dir: Path, observed_utc: str) -> dict[str, Any]:
    manifest_union_path = _build_manifest_union_temp(output_dir=output_dir)
    try:
        consistency = f009.build_full_capture_consistency_audit(
            manifest_path=manifest_union_path,
            output_dir=output_dir,
            observed_utc=observed_utc,
        )
    finally:
        if manifest_union_path.exists():
            try:
                manifest_union_path.unlink()
            except OSError:
                pass

    baseline = hf001.build_baseline(
        repo_root=ROOT,
        market_facts_output_path=output_dir / hf001.MARKET_FACTS_OUTPUT_PATH.name,
        action_outcomes_output_path=output_dir / hf001.ACTION_OUTCOMES_OUTPUT_PATH.name,
        scrape_gap_output_path=output_dir / hf001.SCRAPE_GAP_OUTPUT_PATH.name,
    )
    alignment = hf002.build_alignment(
        repo_root=ROOT,
        alignment_output_path=output_dir / hf002.ALIGNMENT_OUTPUT_PATH.name,
        factor_output_path=output_dir / hf002.FACTOR_OUTPUT_PATH.name,
    )
    health = hf003.build_health_checklist(output_path=output_dir / hf003.OUTPUT_PATH.name)
    operator = hf005.build_operator_report(output_path=hf005.OUTPUT_PATH)
    return {
        "consistency_facts_rows": int(len(consistency.facts_df.index)),
        "consistency_monthly_points_rows": int(len(consistency.monthly_points_df.index)),
        "consistency_discrepancy_rows": int(len(consistency.discrepancies_df.index)),
        "baseline_scrape_gap_rows": int(baseline.scrape_gap_rows),
        "alignment_rows": int(alignment.alignment_rows),
        "alignment_rescrape_trigger_flag": "1" if bool(alignment.rescrape_trigger_flag) else "0",
        "health_fail_count": int(health.fail_count),
        "health_warn_count": int(health.warn_count),
        "operator_rows": int(operator.rows),
    }


def _run_rescore(*, output_dir: Path, observed_utc: str) -> dict[str, Any]:
    accuracy = f011.build_sales_history_accuracy_pack(
        output_dir=output_dir,
        observed_utc=observed_utc,
    )
    guard = bef004.run_sales_feedback_guarded_once(
        output_dir=output_dir,
        observed_utc=observed_utc,
        run_builders=False,
    )
    guard_decision = guard.report.get("guard_decision", {})
    return {
        "queue_rows_after": int(len(accuracy.queue_df.index)),
        "guard_status": _normalize_text(guard_decision.get("guard_status", "")),
        "guard_readiness_label": _normalize_text(guard_decision.get("readiness_label", "")),
        "guard_next_action": _normalize_text(guard_decision.get("next_action", "")),
        "guard_warnings": guard_decision.get("warnings", []) if isinstance(guard_decision.get("warnings", []), list) else [],
    }


def run_sold_truth_replay_capture_path(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    queue_path: Path = QUEUE_PATH,
    max_asins: int = 0,
    passes: int = 2,
    webscrape_mode: str = "data",
    skip_date_scraping: bool = True,
    run_rebuild_chain: bool = True,
    run_rescore: bool = True,
    observed_utc: str | None = None,
) -> SoldTruthReplayCaptureResult:
    snapshot_utc = observed_utc or _utc_now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = _to_timestamp_slug(snapshot_utc)
    capture_pack_path = output_dir / f"f_sold_truth_replay_capture_pack_{ts_slug}.csv"
    capture_pack_latest_path = output_dir / CAPTURE_PACK_LATEST_PATH.name

    queue_df = _read_csv(queue_path)
    queue_rows_before = int(len(queue_df.index))
    capture_pack_df = _capture_pack_from_queue(queue_df, max_asins=max(max_asins, 0))
    capture_pack_df.to_csv(capture_pack_path, index=False)
    capture_pack_df.to_csv(capture_pack_latest_path, index=False)

    capture_state = "skipped_queue_empty"
    capture_manifest_rows = 0
    capture_success_rows = 0
    capture_failed_rows = 0
    manifest_path = ""
    rebuild_metrics: dict[str, Any] = {}

    if not capture_pack_df.empty:
        capture = f008.capture_full_bbp_evidence_pack(
            asin_pack_path=capture_pack_latest_path,
            output_dir=output_dir,
            max_asins=int(len(capture_pack_df.index)),
            passes=max(int(passes), 1),
            observed_utc=snapshot_utc,
            skip_date_scraping=bool(skip_date_scraping),
            webscrape_mode=_normalize_text(webscrape_mode) or "data",
        )
        capture_state = "captured"
        manifest_path = str(capture.latest_path)
        capture_manifest_rows = int(len(capture.manifest_df.index))
        capture_success_rows = int((capture.manifest_df.get("capture_status", "").map(_normalize_text) == "success").sum())
        capture_failed_rows = int((capture.manifest_df.get("capture_status", "").map(_normalize_text) == "failed").sum())

        if run_rebuild_chain:
            rebuild_metrics = _run_post_capture_rebuild_chain(
                output_dir=output_dir,
                observed_utc=snapshot_utc,
            )

    rescore_metrics: dict[str, Any] = {}
    queue_rows_after = queue_rows_before
    if run_rescore:
        rescore_metrics = _run_rescore(output_dir=output_dir, observed_utc=snapshot_utc)
        queue_rows_after = int(rescore_metrics.get("queue_rows_after", queue_rows_before))

    queue_rows_reduced = max(queue_rows_before - queue_rows_after, 0)
    queue_reduction_rate = 0.0
    if queue_rows_before > 0:
        queue_reduction_rate = float(queue_rows_reduced) / float(queue_rows_before)

    report = {
        "status": "success",
        "observed_utc": snapshot_utc,
        "capture_state": capture_state,
        "inputs": {
            "queue_path": str(queue_path),
            "max_asins": int(max(max_asins, 0)),
            "passes": int(max(int(passes), 1)),
            "webscrape_mode": _normalize_text(webscrape_mode) or "data",
            "skip_date_scraping": "1" if skip_date_scraping else "0",
            "run_rebuild_chain": "1" if run_rebuild_chain else "0",
            "run_rescore": "1" if run_rescore else "0",
        },
        "artifacts": {
            "capture_pack_csv": str(capture_pack_path),
            "capture_pack_latest_csv": str(capture_pack_latest_path),
            "full_capture_manifest_latest_csv": manifest_path or str(output_dir / MANIFEST_LATEST_PATH.name),
            "full_capture_facts_latest_csv": str(output_dir / "f_full_capture_normalized_facts_latest.csv"),
            "alignment_latest_csv": str(output_dir / "hf_learning_alignment_30d_latest.csv"),
            "accuracy_summary_latest_csv": str(output_dir / "f_sales_history_accuracy_summary_latest.csv"),
            "guard_report_latest_json": str(output_dir / "bef_sales_feedback_guarded_run_latest.json"),
        },
        "metrics": {
            "queue_rows_before": queue_rows_before,
            "capture_pack_rows": int(len(capture_pack_df.index)),
            "capture_manifest_rows": capture_manifest_rows,
            "capture_success_rows": capture_success_rows,
            "capture_failed_rows": capture_failed_rows,
            "queue_rows_after": queue_rows_after,
            "queue_rows_reduced": queue_rows_reduced,
            "queue_reduction_rate": round(queue_reduction_rate, 4),
            **rebuild_metrics,
            **rescore_metrics,
        },
    }

    report_path = output_dir / f"bef_sold_truth_replay_capture_{ts_slug}.json"
    report_latest_path = output_dir / LATEST_REPORT_PATH.name
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return SoldTruthReplayCaptureResult(
        report=report,
        report_path=report_path,
        report_latest_path=report_latest_path,
        capture_pack_path=capture_pack_path,
        capture_pack_latest_path=capture_pack_latest_path,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute sold-truth replay capture path: queue -> live BBP capture -> post-capture rebuild "
            "-> sold-truth re-score."
        )
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--queue-path", default=str(QUEUE_PATH))
    parser.add_argument("--max-asins", type=int, default=0, help="0 means all queued ASINs.")
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--webscrape-mode", default="data", choices=["data", "decision"])
    parser.add_argument(
        "--include-date-scraping",
        action="store_true",
        help="Enable date scraping during capture (default skips date scraping).",
    )
    parser.add_argument("--skip-rebuild-chain", action="store_true")
    parser.add_argument("--skip-rescore", action="store_true")
    parser.add_argument("--observed-utc", default=None, help="Override observed UTC timestamp in ISO format.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_sold_truth_replay_capture_path(
        output_dir=Path(args.output_dir),
        queue_path=Path(args.queue_path),
        max_asins=args.max_asins,
        passes=args.passes,
        webscrape_mode=args.webscrape_mode,
        skip_date_scraping=not bool(args.include_date_scraping),
        run_rebuild_chain=not bool(args.skip_rebuild_chain),
        run_rescore=not bool(args.skip_rescore),
        observed_utc=args.observed_utc,
    )
    print(json.dumps(result.report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
