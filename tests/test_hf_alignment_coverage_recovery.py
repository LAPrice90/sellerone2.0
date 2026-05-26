from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off import HF007_run_alignment_coverage_recovery as hf007


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    alignment_path = analysis_dir / "hf_learning_alignment_30d_latest.csv"
    scrape_path = analysis_dir / "hf_learning_scrape_gap_report_latest.csv"
    health_path = analysis_dir / "hf_learning_health_checklist_latest.csv"
    pack_path = analysis_dir / "hf_alignment_missing_asin_pack_latest.csv"
    manifest_path = analysis_dir / "f_full_capture_manifest_latest.csv"

    monkeypatch.setattr(hf007, "ANALYSIS_OUTPUT_DIR", analysis_dir)
    monkeypatch.setattr(hf007, "ALIGNMENT_PATH", alignment_path)
    monkeypatch.setattr(hf007, "SCRAPE_GAP_PATH", scrape_path)
    monkeypatch.setattr(hf007, "HEALTH_PATH", health_path)
    monkeypatch.setattr(hf007, "ASIN_PACK_LATEST_PATH", pack_path)
    monkeypatch.setattr(hf007, "MANIFEST_LATEST_PATH", manifest_path)

    monkeypatch.setattr(hf007, "HF006_SCRIPT", tmp_path / "HF006.py")
    monkeypatch.setattr(hf007, "F008_SCRIPT", tmp_path / "F008.py")
    monkeypatch.setattr(hf007, "F009_SCRIPT", tmp_path / "F009.py")
    monkeypatch.setattr(hf007, "HF001_SCRIPT", tmp_path / "HF001.py")
    monkeypatch.setattr(hf007, "HF002_SCRIPT", tmp_path / "HF002.py")
    monkeypatch.setattr(hf007, "HF003_SCRIPT", tmp_path / "HF003.py")
    monkeypatch.setattr(hf007, "HF005_SCRIPT", tmp_path / "HF005.py")

    return {
        "analysis_dir": analysis_dir,
        "alignment_path": alignment_path,
        "scrape_path": scrape_path,
        "health_path": health_path,
        "pack_path": pack_path,
        "manifest_path": manifest_path,
    }


def test_collect_metrics_reports_expected_rates(tmp_path: Path, monkeypatch) -> None:
    paths = _patch_paths(tmp_path, monkeypatch)

    _write_csv(
        paths["alignment_path"],
        [
            {"expected_units_30d": "", "expected_units_source": "no_source"},
            {"expected_units_30d": "5", "expected_units_source": "full_capture_asin"},
            {"expected_units_30d": "", "expected_units_source": ""},
            {"expected_units_30d": "3", "expected_units_source": "sales_validation_asin"},
        ],
        columns=["expected_units_30d", "expected_units_source"],
    )
    _write_csv(
        paths["scrape_path"],
        [
            {"scrape_coverage_status": "missing"},
            {"scrape_coverage_status": "missing"},
            {"scrape_coverage_status": "ok"},
            {"scrape_coverage_status": "thin"},
        ],
        columns=["scrape_coverage_status"],
    )
    _write_csv(
        paths["health_path"],
        [
            {"status": "ok"},
            {"status": "warn"},
            {"status": "fail"},
        ],
        columns=["status"],
    )

    metrics = hf007.collect_metrics(
        alignment_path=paths["alignment_path"],
        scrape_gap_path=paths["scrape_path"],
        health_path=paths["health_path"],
    )
    assert metrics.alignment_total_rows == 4
    assert metrics.no_source_rows == 2
    assert metrics.expected_coverage_rate == 0.5
    assert metrics.expected_primary_coverage_rate == 0.5
    assert metrics.scrape_gap_missing_rate == 0.5
    assert metrics.health_warn_count == 1
    assert metrics.health_fail_count == 1


def test_recovery_runs_one_round_and_stops_on_target_no_source(tmp_path: Path, monkeypatch) -> None:
    paths = _patch_paths(tmp_path, monkeypatch)

    _write_csv(
        paths["alignment_path"],
        [
            {"expected_units_30d": "", "expected_units_source": "no_source"},
            {"expected_units_30d": "", "expected_units_source": "no_source"},
            {"expected_units_30d": "", "expected_units_source": "no_source"},
            {"expected_units_30d": "", "expected_units_source": "no_source"},
            {"expected_units_30d": "", "expected_units_source": "no_source"},
        ],
        columns=["expected_units_30d", "expected_units_source"],
    )
    _write_csv(
        paths["scrape_path"],
        [{"scrape_coverage_status": "missing"} for _ in range(5)],
        columns=["scrape_coverage_status"],
    )
    _write_csv(
        paths["health_path"],
        [{"status": "warn"}],
        columns=["status"],
    )

    calls: list[str] = []

    def _runner(script_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(script_path.name)
        if script_path.name == "HF006.py":
            return subprocess.CompletedProcess([], 0, '{"pack_rows":3}\n', "")
        if script_path.name == "F008.py":
            return subprocess.CompletedProcess([], 0, '{"success_rows":3,"failed_rows":0}\n', "")
        if script_path.name == "HF005.py":
            _write_csv(
                paths["alignment_path"],
                [
                    {"expected_units_30d": "5", "expected_units_source": "full_capture_asin"},
                    {"expected_units_30d": "4", "expected_units_source": "full_capture_asin"},
                    {"expected_units_30d": "", "expected_units_source": "no_source"},
                    {"expected_units_30d": "", "expected_units_source": "no_source"},
                    {"expected_units_30d": "", "expected_units_source": "no_source"},
                ],
                columns=["expected_units_30d", "expected_units_source"],
            )
            _write_csv(
                paths["scrape_path"],
                [
                    {"scrape_coverage_status": "missing"},
                    {"scrape_coverage_status": "missing"},
                    {"scrape_coverage_status": "ok"},
                    {"scrape_coverage_status": "ok"},
                    {"scrape_coverage_status": "ok"},
                ],
                columns=["scrape_coverage_status"],
            )
            _write_csv(
                paths["health_path"],
                [{"status": "ok"}],
                columns=["status"],
            )
        return subprocess.CompletedProcess([], 0, "", "")

    summary = hf007.run_alignment_coverage_recovery(
        max_rounds=3,
        batch_size=5,
        passes=1,
        output_dir=paths["analysis_dir"],
        webscrape_mode="data",
        skip_date_scraping=True,
        only_not_in_scrape=False,
        target_coverage=0.0,
        target_no_source=3,
        runner=_runner,
    )

    assert summary["rounds_executed"] == 1
    assert summary["stop_reason"] == "target_no_source_met"
    assert summary["final_metrics"]["no_source_rows"] == 3
    assert calls == ["HF006.py", "F008.py", "F009.py", "HF001.py", "HF002.py", "HF003.py", "HF005.py"]


def test_recovery_stops_when_pack_empty(tmp_path: Path, monkeypatch) -> None:
    paths = _patch_paths(tmp_path, monkeypatch)

    _write_csv(
        paths["alignment_path"],
        [
            {"expected_units_30d": "", "expected_units_source": "no_source"},
            {"expected_units_30d": "", "expected_units_source": "no_source"},
        ],
        columns=["expected_units_30d", "expected_units_source"],
    )
    _write_csv(
        paths["scrape_path"],
        [{"scrape_coverage_status": "missing"} for _ in range(2)],
        columns=["scrape_coverage_status"],
    )
    _write_csv(
        paths["health_path"],
        [{"status": "warn"}],
        columns=["status"],
    )

    calls: list[str] = []

    def _runner(script_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(script_path.name)
        if script_path.name == "HF006.py":
            return subprocess.CompletedProcess([], 0, '{"pack_rows":0}\n', "")
        return subprocess.CompletedProcess([], 0, "", "")

    summary = hf007.run_alignment_coverage_recovery(
        max_rounds=2,
        batch_size=5,
        passes=1,
        output_dir=paths["analysis_dir"],
        webscrape_mode="data",
        skip_date_scraping=True,
        only_not_in_scrape=False,
        target_coverage=0.8,
        target_no_source=0,
        runner=_runner,
    )

    assert summary["rounds_executed"] == 0
    assert summary["stop_reason"] == "asin_pack_empty"
    assert calls == ["HF006.py"]


def test_manifest_union_temp_includes_history_and_dedupes_run_id(tmp_path: Path, monkeypatch) -> None:
    paths = _patch_paths(tmp_path, monkeypatch)

    manifest_a = paths["analysis_dir"] / "f_full_capture_manifest_20260417T100000Z.csv"
    manifest_b = paths["analysis_dir"] / "f_full_capture_manifest_20260417T110000Z.csv"
    latest = paths["manifest_path"]

    _write_csv(
        manifest_a,
        [
            {"observed_utc": "2026-04-17T10:00:00Z", "run_id": "R1", "asin": "A1"},
            {"observed_utc": "2026-04-17T10:00:01Z", "run_id": "R2", "asin": "A2"},
        ],
        columns=["observed_utc", "run_id", "asin"],
    )
    _write_csv(
        manifest_b,
        [
            {"observed_utc": "2026-04-17T11:00:00Z", "run_id": "R3", "asin": "A3"},
        ],
        columns=["observed_utc", "run_id", "asin"],
    )
    _write_csv(
        latest,
        [
            {"observed_utc": "2026-04-17T11:05:00Z", "run_id": "R3", "asin": "A3"},
        ],
        columns=["observed_utc", "run_id", "asin"],
    )

    union_path = hf007._build_manifest_union_temp(output_dir=paths["analysis_dir"])
    try:
        union_df = pd.read_csv(union_path, dtype=str).fillna("")
        assert set(union_df["run_id"].tolist()) == {"R1", "R2", "R3"}
        assert len(union_df.index) == 3
    finally:
        if union_path.exists():
            union_path.unlink()
