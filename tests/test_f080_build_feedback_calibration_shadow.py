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

from scripts.flows.F import F080_build_feedback_calibration_shadow as f080


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _patch_paths(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    paths = {
        "FACTOR_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_factor_impacts_latest.csv",
        "ALIGNMENT_PATH": tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv",
        "QUEUE_PATH": tmp_path / "out" / "systems" / "F" / "live" / "feeder_approval_queue_live.csv",
        "DECISIONS_PATH": tmp_path / "out" / "systems" / "F" / "history" / "feeder_approval_decisions_log.csv",
        "SCRAPE_EVIDENCE_PATH": tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_scrape_evidence_live.csv",
        "SCRAPE_CHART_PATH": tmp_path / "out" / "systems" / "F" / "live" / "feeder_legacy_chart_daily_raw_live.csv",
    }
    for attr, path in paths.items():
        monkeypatch.setattr(f080, attr, path)
    monkeypatch.setattr(f080, "REQUIRED_INPUTS", [paths[k] for k in ["FACTOR_PATH", "ALIGNMENT_PATH", "QUEUE_PATH", "DECISIONS_PATH", "SCRAPE_EVIDENCE_PATH", "SCRAPE_CHART_PATH"]])
    monkeypatch.setattr(f080, "WATCHED_SOURCE_FILES", [paths[k] for k in ["QUEUE_PATH", "DECISIONS_PATH", "SCRAPE_EVIDENCE_PATH", "SCRAPE_CHART_PATH"]])
    return paths


def test_f080_builds_shadow_rows_and_preserves_sources(tmp_path: Path, monkeypatch) -> None:
    paths = _patch_paths(tmp_path, monkeypatch)

    _write_csv(
        paths["FACTOR_PATH"],
        [
            {
                "snapshot_utc": "2026-04-17T18:00:00Z",
                "factor_bucket": "missing_expected_baseline",
                "sample_rows": "95",
                "avg_units_error_pct": "",
                "avg_profit_error_pct": "",
                "avg_seller_count": "2.1",
                "amazon_presence_share_pct": "0.2",
                "rescrape_trigger_flag": "1",
                "rescrape_trigger_reason": "missing_rate_gt_80pct",
                "rescrape_owner_path": "F007|F061",
                "recommended_collection_mode": "F061_MODE=data_collection",
                "thin_sample_flag": "0",
            }
        ],
        columns=[
            "snapshot_utc",
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
            "thin_sample_flag",
        ],
    )
    _write_csv(
        paths["ALIGNMENT_PATH"],
        [
            {"sku": "SKU1", "asin": "A1", "dominant_discrepancy_class": "missing_expected_baseline"},
            {"sku": "SKU2", "asin": "A2", "dominant_discrepancy_class": "missing_expected_baseline"},
        ],
        columns=["sku", "asin", "dominant_discrepancy_class"],
    )
    _write_csv(paths["QUEUE_PATH"], [{"candidate_id": "C1"}], columns=["candidate_id"])
    _write_csv(paths["DECISIONS_PATH"], [{"candidate_id": "C1"}], columns=["candidate_id"])
    _write_csv(paths["SCRAPE_EVIDENCE_PATH"], [{"candidate_id": "C1"}], columns=["candidate_id"])
    _write_csv(paths["SCRAPE_CHART_PATH"], [{"candidate_id": "C1"}], columns=["candidate_id"])

    output_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_feedback_calibration_live.csv"
    result = f080.build_shadow_calibration(root=tmp_path, output_path=output_path, observed_utc="2026-04-17T18:05:00Z")

    assert output_path.exists()
    assert result.output_rows == 1
    assert result.source_hash_verified is True

    output_df = pd.read_csv(output_path, dtype=str).fillna("")
    row = output_df.iloc[0]
    assert row["shadow_only_flag"] == "1"
    assert row["apply_to_live_decisions_flag"] == "0"
    assert row["calibration_status"] == "shadow_ready"
    assert row["alignment_class_rows"] == "2"


def test_f080_emits_no_factor_control_row(tmp_path: Path, monkeypatch) -> None:
    paths = _patch_paths(tmp_path, monkeypatch)

    _write_csv(paths["FACTOR_PATH"], [], columns=["factor_bucket", "sample_rows"])
    _write_csv(paths["ALIGNMENT_PATH"], [], columns=["sku", "asin", "dominant_discrepancy_class"])
    _write_csv(paths["QUEUE_PATH"], [], columns=["candidate_id"])
    _write_csv(paths["DECISIONS_PATH"], [], columns=["candidate_id"])
    _write_csv(paths["SCRAPE_EVIDENCE_PATH"], [], columns=["candidate_id"])
    _write_csv(paths["SCRAPE_CHART_PATH"], [], columns=["candidate_id"])

    output_path = tmp_path / "out" / "systems" / "F" / "live" / "feeder_feedback_calibration_live.csv"
    result = f080.build_shadow_calibration(root=tmp_path, output_path=output_path, observed_utc="2026-04-17T18:05:00Z")

    assert result.output_rows == 1
    output_df = pd.read_csv(output_path, dtype=str).fillna("")
    row = output_df.iloc[0]
    assert row["factor_bucket"] == "NO_FACTOR_DATA"
    assert row["shadow_only_flag"] == "1"
    assert row["apply_to_live_decisions_flag"] == "0"
    assert row["calibration_status"] == "shadow_blocked_no_factor_data"

