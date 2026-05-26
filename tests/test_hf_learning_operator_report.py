from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off import HF005_build_learning_operator_report as hf005


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_build_operator_report_rolls_up_metrics(tmp_path: Path, monkeypatch) -> None:
    paths = {
        "ACTION_OUTCOMES_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_action_outcomes_latest.csv",
        "SCRAPE_GAP_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_scrape_gap_report_latest.csv",
        "ALIGNMENT_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv",
        "FACTOR_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_factor_impacts_latest.csv",
        "HEALTH_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_health_checklist_latest.csv",
    }

    _write_csv(
        paths["ACTION_OUTCOMES_PATH"],
        [
            {"write_applied_flag": "1", "decision_to_change_price_flag": "1", "writer_outcome": "APPLIED", "seller_count": "2"},
            {"write_applied_flag": "0", "decision_to_change_price_flag": "0", "writer_outcome": "READ_ONLY_NO_WRITE", "seller_count": "4"},
        ],
        columns=["write_applied_flag", "decision_to_change_price_flag", "writer_outcome", "seller_count"],
    )
    _write_csv(
        paths["SCRAPE_GAP_PATH"],
        [
            {"scrape_coverage_status": "missing"},
            {"scrape_coverage_status": "thin"},
            {"scrape_coverage_status": "ok"},
        ],
        columns=["scrape_coverage_status"],
    )
    _write_csv(
        paths["ALIGNMENT_PATH"],
        [
            {"dominant_discrepancy_class": "missing_expected_baseline"},
            {"dominant_discrepancy_class": "aligned"},
        ],
        columns=["dominant_discrepancy_class"],
    )
    _write_csv(
        paths["FACTOR_PATH"],
        [
            {"rescrape_trigger_flag": "1", "rescrape_trigger_reason": "missing_rate_gt_80pct"},
        ],
        columns=["rescrape_trigger_flag", "rescrape_trigger_reason"],
    )
    _write_csv(
        paths["HEALTH_PATH"],
        [
            {"status": "ok"},
            {"status": "warn"},
            {"status": "fail"},
        ],
        columns=["status"],
    )

    for attr, path in paths.items():
        monkeypatch.setattr(hf005, attr, path)
    monkeypatch.setattr(hf005, "REQUIRED_INPUTS", list(paths.values()))
    monkeypatch.setattr(hf005, "_utc_now_iso", lambda: "2026-04-17T19:00:00Z")

    output_path = tmp_path / "out" / "reports" / "operator.csv"
    result = hf005.build_operator_report(output_path=output_path)

    assert output_path.exists()
    assert result.rows > 0
    assert result.health_fail_count == 1
    assert result.health_warn_count == 1

    report_df = pd.read_csv(output_path, dtype=str).fillna("").set_index("metric_key")
    assert report_df.loc["write_applied_rate", "metric_value"] == "0.5000"
    assert report_df.loc["missing_rate", "metric_value"] == "0.3333"
    assert report_df.loc["missing_expected_class_rate", "metric_value"] == "0.5000"
    assert report_df.loc["expected_units_coverage_rate", "metric_value"] == "0.0000"
    assert report_df.loc["expected_units_primary_coverage_rate", "metric_value"] == "0.0000"
    assert report_df.loc["expected_units_no_source_rate", "metric_value"] == "0.0000"
    assert report_df.loc["rescrape_trigger_flag", "metric_value"] == "1"
    assert report_df.loc["health_fail_count", "metric_value"] == "1"
