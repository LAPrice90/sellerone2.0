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

from scripts.one_off import HF003_build_learning_health_checks as hf003


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_required_paths(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    paths = {
        "identity": tmp_path / "out" / "analysis_reports" / "hf_learning_identity_bridge_latest.csv",
        "assumption": tmp_path / "out" / "analysis_reports" / "hf_learning_assumption_snapshots_latest.csv",
        "foundation_metrics": tmp_path / "out" / "analysis_reports" / "hf_learning_foundation_metrics_latest.csv",
        "market_facts": tmp_path / "out" / "analysis_reports" / "hf_learning_market_facts_latest.csv",
        "action_outcomes": tmp_path / "out" / "analysis_reports" / "hf_learning_action_outcomes_latest.csv",
        "scrape_gap": tmp_path / "out" / "analysis_reports" / "hf_learning_scrape_gap_report_latest.csv",
        "alignment": tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv",
        "factor": tmp_path / "out" / "analysis_reports" / "hf_learning_factor_impacts_latest.csv",
    }
    monkeypatch.setattr(hf003, "REQUIRED_PATHS", paths)
    return paths


def test_health_checks_pass_for_valid_fixture(tmp_path: Path, monkeypatch) -> None:
    paths = _patch_required_paths(tmp_path, monkeypatch)

    _write_csv(paths["identity"], [{"snapshot_utc": "2026-04-17T18:00:00Z", "candidate_id": "C1", "sku_resolution_status": "RESOLVED_FROM_H_SNAPSHOT", "sku_resolution_source": "event"}], columns=hf003.REQUIRED_COLUMNS["identity"])
    _write_csv(paths["assumption"], [{"snapshot_utc": "2026-04-17T18:00:00Z", "candidate_id": "C1", "snapshot_stage": "approval_decision", "assumption_anchor_source": "approval_decision"}], columns=hf003.REQUIRED_COLUMNS["assumption"])
    _write_csv(paths["foundation_metrics"], [{"snapshot_utc": "2026-04-17T18:00:00Z", "metric_name": "identity_rows_total", "metric_value": "1"}], columns=hf003.REQUIRED_COLUMNS["foundation_metrics"])
    _write_csv(paths["market_facts"], [{"observation_utc": "2026-04-17T18:00:00Z", "asof_date": "2026-04-17", "sku": "SKU1", "asin": "A1", "amazon_present_flag": "0", "delivery_parity_flag": "1"}], columns=hf003.REQUIRED_COLUMNS["market_facts"])
    _write_csv(paths["action_outcomes"], [{"event_ts_utc": "2026-04-17T18:00:00Z", "run_id": "RUN-1", "sku": "SKU1", "asin": "A1", "eligible_to_write_flag": "1", "write_applied_flag": "1"}], columns=hf003.REQUIRED_COLUMNS["action_outcomes"])
    _write_csv(paths["scrape_gap"], [{"observed_utc": "2026-04-17T18:00:00Z", "candidate_id": "C1", "scrape_coverage_status": "ok", "rescrape_needed_flag": "0", "queue_owner_path": "F007|F061"}], columns=hf003.REQUIRED_COLUMNS["scrape_gap"])
    _write_csv(paths["alignment"], [{"alignment_window_end_utc": "2026-04-17T18:00:00Z", "sku": "SKU1", "asin": "A1", "dominant_discrepancy_class": "aligned", "rescrape_signal_flag": "0", "expected_units_30d": "5"}], columns=hf003.REQUIRED_COLUMNS["alignment"] + ["expected_units_30d"])
    _write_csv(paths["factor"], [{"snapshot_utc": "2026-04-17T18:00:00Z", "factor_bucket": "aligned", "sample_rows": "1", "rescrape_trigger_flag": "0", "rescrape_trigger_reason": "none"}], columns=hf003.REQUIRED_COLUMNS["factor"])

    output_path = tmp_path / "out" / "analysis_reports" / "health.csv"
    result = hf003.build_health_checklist(output_path=output_path)

    assert output_path.exists()
    assert result.fail_count == 0
    checklist = pd.read_csv(output_path, dtype=str).fillna("")
    assert (checklist["status"] == "ok").any()


def test_health_checks_surface_fail_and_warn_conditions(tmp_path: Path, monkeypatch) -> None:
    paths = _patch_required_paths(tmp_path, monkeypatch)

    _write_csv(paths["identity"], [], columns=hf003.REQUIRED_COLUMNS["identity"])
    _write_csv(paths["assumption"], [], columns=hf003.REQUIRED_COLUMNS["assumption"])
    _write_csv(paths["foundation_metrics"], [], columns=hf003.REQUIRED_COLUMNS["foundation_metrics"])
    _write_csv(paths["market_facts"], [{"observation_utc": "2026-04-17T18:00:00Z"}], columns=["observation_utc"])
    _write_csv(paths["action_outcomes"], [], columns=hf003.REQUIRED_COLUMNS["action_outcomes"])

    scrape_rows = []
    for idx in range(9):
        scrape_rows.append(
            {
                "observed_utc": "2026-04-17T18:00:00Z",
                "candidate_id": f"C{idx}",
                "scrape_coverage_status": "missing",
                "rescrape_needed_flag": "1",
                "queue_owner_path": "F007|F061",
            }
        )
    scrape_rows.append(
        {
            "observed_utc": "2026-04-17T18:00:00Z",
            "candidate_id": "C_OK",
            "scrape_coverage_status": "ok",
            "rescrape_needed_flag": "0",
            "queue_owner_path": "F007|F061",
        }
    )
    _write_csv(paths["scrape_gap"], scrape_rows, columns=hf003.REQUIRED_COLUMNS["scrape_gap"])
    _write_csv(paths["alignment"], [{"alignment_window_end_utc": "2026-04-17T18:00:00Z", "sku": "SKU1", "asin": "A1", "dominant_discrepancy_class": "missing_expected_baseline", "rescrape_signal_flag": "1", "expected_units_30d": ""}], columns=hf003.REQUIRED_COLUMNS["alignment"] + ["expected_units_30d"])
    _write_csv(paths["factor"], [{"snapshot_utc": "2026-04-17T18:00:00Z", "factor_bucket": "missing_expected_baseline", "sample_rows": "1", "rescrape_trigger_flag": "0", "rescrape_trigger_reason": "none"}], columns=hf003.REQUIRED_COLUMNS["factor"])

    output_path = tmp_path / "out" / "analysis_reports" / "health.csv"
    result = hf003.build_health_checklist(output_path=output_path)

    assert result.fail_count >= 1
    assert result.warn_count >= 1
    checklist = pd.read_csv(output_path, dtype=str).fillna("").set_index("check")
    assert checklist.loc["hf_market_facts_schema", "status"] == "fail"
    assert checklist.loc["hf_scrape_gap_missing_rate", "status"] == "warn"
    assert checklist.loc["hf_rescrape_trigger_consistency", "status"] == "fail"

