from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

HF006_SCRIPT = ROOT / "scripts" / "one_off" / "HF006_build_alignment_missing_asin_pack.py"
F008_SCRIPT = ROOT / "scripts" / "one_off" / "F008_capture_full_bbp_evidence_pack.py"
F009_SCRIPT = ROOT / "scripts" / "one_off" / "F009_build_full_capture_consistency_audit.py"
HF001_SCRIPT = ROOT / "scripts" / "one_off" / "HF001_build_learning_baseline.py"
HF002_SCRIPT = ROOT / "scripts" / "one_off" / "HF002_build_learning_alignment.py"
HF003_SCRIPT = ROOT / "scripts" / "one_off" / "HF003_build_learning_health_checks.py"
HF005_SCRIPT = ROOT / "scripts" / "one_off" / "HF005_build_learning_operator_report.py"

ANALYSIS_OUTPUT_DIR = ROOT / "out" / "analysis_reports"
ASIN_PACK_LATEST_PATH = ANALYSIS_OUTPUT_DIR / "hf_alignment_missing_asin_pack_latest.csv"
MANIFEST_LATEST_PATH = ANALYSIS_OUTPUT_DIR / "f_full_capture_manifest_latest.csv"
ALIGNMENT_PATH = ANALYSIS_OUTPUT_DIR / "hf_learning_alignment_30d_latest.csv"
SCRAPE_GAP_PATH = ANALYSIS_OUTPUT_DIR / "hf_learning_scrape_gap_report_latest.csv"
HEALTH_PATH = ANALYSIS_OUTPUT_DIR / "hf_learning_health_checklist_latest.csv"

PRIMARY_EXPECTED_SOURCES = {"assumption_candidate_sku_asin", "sales_validation_asin", "full_capture_asin"}


@dataclass(frozen=True)
class CoverageMetrics:
    alignment_total_rows: int
    no_source_rows: int
    expected_coverage_rate: float
    expected_primary_coverage_rate: float
    scrape_gap_missing_rate: float
    health_fail_count: int
    health_warn_count: int


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


def _to_int(value: object, *, default: int = 0) -> int:
    text = _normalize_text(value)
    if text == "":
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def _to_float(value: object, *, default: float = 0.0) -> float:
    text = _normalize_text(value)
    if text == "":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _json_from_stdout(stdout: str) -> dict[str, object]:
    for raw_line in reversed(stdout.splitlines()):
        line = raw_line.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    return {}


def collect_metrics(
    *,
    alignment_path: Path | None = None,
    scrape_gap_path: Path | None = None,
    health_path: Path | None = None,
) -> CoverageMetrics:
    alignment_path = alignment_path or ALIGNMENT_PATH
    scrape_gap_path = scrape_gap_path or SCRAPE_GAP_PATH
    health_path = health_path or HEALTH_PATH

    alignment_df = _read_csv(alignment_path)
    scrape_gap_df = _read_csv(scrape_gap_path)
    health_df = _read_csv(health_path)

    alignment_total_rows = int(len(alignment_df.index))
    no_source_rows = 0
    expected_coverage_rate = 0.0
    expected_primary_coverage_rate = 0.0
    if alignment_total_rows > 0:
        source_series = alignment_df.get("expected_units_source", "").map(_normalize_text)
        expected_series = alignment_df.get("expected_units_30d", "").map(_normalize_text)
        no_source_rows = int(source_series.isin({"", "no_source"}).sum())
        expected_rows = int((expected_series != "").sum())
        primary_rows = int(((expected_series != "") & source_series.isin(PRIMARY_EXPECTED_SOURCES)).sum())
        expected_coverage_rate = float(expected_rows) / float(alignment_total_rows)
        expected_primary_coverage_rate = float(primary_rows) / float(alignment_total_rows)

    scrape_gap_missing_rate = 0.0
    if not scrape_gap_df.empty and "scrape_coverage_status" in scrape_gap_df.columns:
        total = float(len(scrape_gap_df.index))
        if total > 0:
            missing = float((scrape_gap_df["scrape_coverage_status"].map(_normalize_text) == "missing").sum())
            scrape_gap_missing_rate = missing / total

    health_fail_count = 0
    health_warn_count = 0
    if not health_df.empty and "status" in health_df.columns:
        status_series = health_df["status"].map(_normalize_text)
        health_fail_count = int((status_series == "fail").sum())
        health_warn_count = int((status_series == "warn").sum())

    return CoverageMetrics(
        alignment_total_rows=alignment_total_rows,
        no_source_rows=no_source_rows,
        expected_coverage_rate=expected_coverage_rate,
        expected_primary_coverage_rate=expected_primary_coverage_rate,
        scrape_gap_missing_rate=scrape_gap_missing_rate,
        health_fail_count=health_fail_count,
        health_warn_count=health_warn_count,
    )


def _target_reason(metrics: CoverageMetrics, *, target_coverage: float, target_no_source: int) -> str:
    coverage_met = target_coverage > 0 and metrics.expected_coverage_rate >= target_coverage
    no_source_met = target_no_source >= 0 and metrics.no_source_rows <= target_no_source
    if coverage_met and no_source_met:
        return "target_coverage_and_no_source_met"
    if coverage_met:
        return "target_coverage_met"
    if no_source_met:
        return "target_no_source_met"
    return ""


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
        tmp_path = output_dir / "_tmp_hf007_manifest_union.csv"
        pd.DataFrame(columns=["observed_utc", "run_id", "asin"]).to_csv(tmp_path, index=False)
        return tmp_path

    union_df = pd.concat(frames, ignore_index=True).fillna("")
    if "run_id" in union_df.columns:
        union_df["run_id"] = union_df["run_id"].map(_normalize_text)
        union_df["observed_utc"] = union_df.get("observed_utc", "").map(_normalize_text)
        union_df = union_df.sort_values(["run_id", "observed_utc", "_source_path"], ascending=[True, False, True], kind="stable")
        union_df = union_df.drop_duplicates(subset=["run_id"], keep="first")
    union_df = union_df.drop(columns=["_source_path"], errors="ignore")

    tmp_path = output_dir / "_tmp_hf007_manifest_union.csv"
    union_df.to_csv(tmp_path, index=False)
    return tmp_path


def _run_script(script_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(script_path), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-20:])
        raise RuntimeError(f"script_failed={script_path.name}\n{stderr_tail}")
    return result


def run_alignment_coverage_recovery(
    *,
    max_rounds: int,
    batch_size: int,
    passes: int,
    output_dir: Path,
    webscrape_mode: str,
    skip_date_scraping: bool,
    only_not_in_scrape: bool,
    target_coverage: float,
    target_no_source: int,
    runner: Callable[[Path, list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, object]:
    script_runner = runner or _run_script
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline = collect_metrics()
    baseline_reason = _target_reason(
        baseline,
        target_coverage=target_coverage,
        target_no_source=target_no_source,
    )
    if baseline_reason != "":
        summary = {
            "status": "success",
            "rounds_executed": 0,
            "stop_reason": f"{baseline_reason}_already_true",
            "baseline_metrics": {
                "alignment_total_rows": baseline.alignment_total_rows,
                "no_source_rows": baseline.no_source_rows,
                "expected_coverage_rate": round(baseline.expected_coverage_rate, 4),
                "expected_primary_coverage_rate": round(baseline.expected_primary_coverage_rate, 4),
                "scrape_gap_missing_rate": round(baseline.scrape_gap_missing_rate, 4),
                "health_fail_count": baseline.health_fail_count,
                "health_warn_count": baseline.health_warn_count,
            },
            "final_metrics": {
                "alignment_total_rows": baseline.alignment_total_rows,
                "no_source_rows": baseline.no_source_rows,
                "expected_coverage_rate": round(baseline.expected_coverage_rate, 4),
                "expected_primary_coverage_rate": round(baseline.expected_primary_coverage_rate, 4),
                "scrape_gap_missing_rate": round(baseline.scrape_gap_missing_rate, 4),
                "health_fail_count": baseline.health_fail_count,
                "health_warn_count": baseline.health_warn_count,
            },
            "rounds": [],
        }
        print(json.dumps(summary))
        return summary

    rounds: list[dict[str, object]] = []
    stop_reason = "max_rounds_reached"
    final_metrics = baseline

    for round_index in range(1, max(max_rounds, 1) + 1):
        hf006_args = [
            "--output-dir",
            str(output_dir),
            "--max-asins",
            str(max(batch_size, 1)),
        ]
        if only_not_in_scrape:
            hf006_args.append("--only-not-in-scrape")
        hf006_result = script_runner(HF006_SCRIPT, hf006_args)
        hf006_summary = _json_from_stdout(hf006_result.stdout)
        pack_rows = _to_int(hf006_summary.get("pack_rows", 0))
        if pack_rows <= 0:
            stop_reason = "asin_pack_empty"
            break

        f008_args = [
            "--asin-pack-path",
            str(ASIN_PACK_LATEST_PATH),
            "--max-asins",
            str(min(pack_rows, max(batch_size, 1))),
            "--passes",
            str(max(passes, 1)),
            "--webscrape-mode",
            _normalize_text(webscrape_mode) or "data",
            "--output-dir",
            str(output_dir),
        ]
        if skip_date_scraping:
            f008_args.append("--skip-date-scraping")
        f008_result = script_runner(F008_SCRIPT, f008_args)
        f008_summary = _json_from_stdout(f008_result.stdout)

        manifest_union_path = _build_manifest_union_temp(output_dir=output_dir)
        try:
            script_runner(
                F009_SCRIPT,
                [
                    "--manifest-path",
                    str(manifest_union_path),
                    "--output-dir",
                    str(output_dir),
                ],
            )
        finally:
            if manifest_union_path.exists():
                try:
                    os.remove(manifest_union_path)
                except OSError:
                    pass
        script_runner(HF001_SCRIPT, [])
        script_runner(HF002_SCRIPT, [])
        script_runner(HF003_SCRIPT, [])
        script_runner(HF005_SCRIPT, [])

        final_metrics = collect_metrics()
        round_record = {
            "round_index": round_index,
            "pack_rows": pack_rows,
            "capture_success_rows": _to_int(f008_summary.get("success_rows", 0)),
            "capture_failed_rows": _to_int(f008_summary.get("failed_rows", 0)),
            "alignment_total_rows": final_metrics.alignment_total_rows,
            "no_source_rows": final_metrics.no_source_rows,
            "expected_coverage_rate": round(final_metrics.expected_coverage_rate, 4),
            "expected_primary_coverage_rate": round(final_metrics.expected_primary_coverage_rate, 4),
            "scrape_gap_missing_rate": round(final_metrics.scrape_gap_missing_rate, 4),
            "health_fail_count": final_metrics.health_fail_count,
            "health_warn_count": final_metrics.health_warn_count,
        }
        rounds.append(round_record)
        print(json.dumps({"event": "round_complete", **round_record}))

        reason = _target_reason(
            final_metrics,
            target_coverage=target_coverage,
            target_no_source=target_no_source,
        )
        if reason != "":
            stop_reason = reason
            break

    summary = {
        "status": "success",
        "rounds_executed": len(rounds),
        "stop_reason": stop_reason,
        "baseline_metrics": {
            "alignment_total_rows": baseline.alignment_total_rows,
            "no_source_rows": baseline.no_source_rows,
            "expected_coverage_rate": round(baseline.expected_coverage_rate, 4),
            "expected_primary_coverage_rate": round(baseline.expected_primary_coverage_rate, 4),
            "scrape_gap_missing_rate": round(baseline.scrape_gap_missing_rate, 4),
            "health_fail_count": baseline.health_fail_count,
            "health_warn_count": baseline.health_warn_count,
        },
        "final_metrics": {
            "alignment_total_rows": final_metrics.alignment_total_rows,
            "no_source_rows": final_metrics.no_source_rows,
            "expected_coverage_rate": round(final_metrics.expected_coverage_rate, 4),
            "expected_primary_coverage_rate": round(final_metrics.expected_primary_coverage_rate, 4),
            "scrape_gap_missing_rate": round(final_metrics.scrape_gap_missing_rate, 4),
            "health_fail_count": final_metrics.health_fail_count,
            "health_warn_count": final_metrics.health_warn_count,
        },
        "targets": {
            "target_coverage": round(target_coverage, 4),
            "target_no_source": target_no_source,
            "max_rounds": max_rounds,
            "batch_size": batch_size,
            "passes": passes,
        },
        "rounds": rounds,
    }
    print(json.dumps(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run bounded HF no-source coverage recovery rounds by chaining "
            "HF006 -> F008 -> F009 -> HF001 -> HF002 -> HF003 -> HF005."
        )
    )
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--output-dir", default=str(ANALYSIS_OUTPUT_DIR))
    parser.add_argument("--webscrape-mode", default="data", choices=["data", "decision"])
    parser.add_argument("--skip-date-scraping", action="store_true")
    parser.add_argument("--only-not-in-scrape", action="store_true")
    parser.add_argument("--target-coverage", type=float, default=0.30)
    parser.add_argument("--target-no-source", type=int, default=60)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    run_alignment_coverage_recovery(
        max_rounds=max(args.max_rounds, 1),
        batch_size=max(args.batch_size, 1),
        passes=max(args.passes, 1),
        output_dir=Path(args.output_dir),
        webscrape_mode=args.webscrape_mode,
        skip_date_scraping=bool(args.skip_date_scraping),
        only_not_in_scrape=bool(args.only_not_in_scrape),
        target_coverage=float(args.target_coverage),
        target_no_source=int(args.target_no_source),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
