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

from scripts.one_off import HF012_build_strategy_review_pack as hf012


def _write_csv(path: Path, rows: list[dict[str, object]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_hf012_strategy_review_pack_separates_classes(tmp_path: Path, monkeypatch) -> None:
    scorecard_path = tmp_path / "out" / "analysis_reports" / "hf_strategy_scorecard_latest.csv"
    alignment_path = tmp_path / "out" / "analysis_reports" / "hf_learning_alignment_30d_latest.csv"
    summary_path = tmp_path / "out" / "analysis_reports" / "hf_scope_expansion_summary_latest.csv"

    _write_csv(
        scorecard_path,
        [
            {
                "snapshot_utc": "2026-04-18T12:10:00Z",
                "scenario_type": "multi_seller_ladder_cap",
                "decision_rows": "87",
                "sample_min_rows": "150",
                "sample_mature_flag": "0",
                "review_status": "blocked",
                "dominant_alignment_class": "missing_expected_baseline",
                "missing_expected_baseline_rate": "0.66",
                "underperform_rate": "0.12",
            },
            {
                "snapshot_utc": "2026-04-18T12:10:00Z",
                "scenario_type": "suppression_reactivation",
                "decision_rows": "62",
                "sample_min_rows": "20",
                "sample_mature_flag": "1",
                "review_status": "eligible_shadow",
                "dominant_alignment_class": "aligned",
                "missing_expected_baseline_rate": "0.10",
                "underperform_rate": "0.05",
            },
        ],
        columns=[
            "snapshot_utc",
            "scenario_type",
            "decision_rows",
            "sample_min_rows",
            "sample_mature_flag",
            "review_status",
            "dominant_alignment_class",
            "missing_expected_baseline_rate",
            "underperform_rate",
        ],
    )

    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-18T12:11:00Z",
                "sku": "SKU-1",
                "asin": "A1",
                "dominant_discrepancy_class": "missing_expected_baseline",
            },
            {
                "alignment_window_end_utc": "2026-04-18T12:11:00Z",
                "sku": "SKU-2",
                "asin": "A2",
                "dominant_discrepancy_class": "underperform_vs_expected",
            },
            {
                "alignment_window_end_utc": "2026-04-18T12:11:00Z",
                "sku": "SKU-3",
                "asin": "A3",
                "dominant_discrepancy_class": "aligned",
            },
        ],
        columns=["alignment_window_end_utc", "sku", "asin", "dominant_discrepancy_class"],
    )

    _write_csv(
        summary_path,
        [
            {"snapshot_utc": "2026-04-18T12:00:00Z", "metric_name": "identity_snapshot_utc", "metric_value": "2026-04-18T08:03:52Z"},
            {"snapshot_utc": "2026-04-18T12:00:00Z", "metric_name": "outside_h_scope_rows", "metric_value": "6979"},
        ],
        columns=["snapshot_utc", "metric_name", "metric_value"],
    )

    monkeypatch.setattr(hf012, "SCORECARD_PATH", scorecard_path)
    monkeypatch.setattr(hf012, "ALIGNMENT_PATH", alignment_path)
    monkeypatch.setattr(hf012, "SCOPE_SUMMARY_PATH", summary_path)
    monkeypatch.setattr(hf012, "REQUIRED_INPUTS", [scorecard_path, alignment_path])
    monkeypatch.setattr(hf012, "_utc_now_iso", lambda: "2026-04-18T12:30:00Z")

    output_path = tmp_path / "out" / "reports" / "hf_strategy_review_pack_latest.csv"
    result = hf012.build_strategy_review_pack(output_path=output_path)

    assert result.rows >= 6
    assert result.alignment_class_rows == 3
    assert result.tactic_rows == 2

    review_df = pd.read_csv(output_path, dtype=str).fillna("")
    assert review_df.columns.tolist() == hf012.REVIEW_COLUMNS

    class_df = review_df[review_df["review_section"] == "alignment_class"].set_index("record_key")
    assert class_df.loc["missing_expected_baseline", "record_count"] == "1"
    assert class_df.loc["underperform_vs_expected", "record_count"] == "1"
    assert class_df.loc["missing_expected_baseline", "recommendation"] == "recover_overlap_first"
    assert class_df.loc["underperform_vs_expected", "recommendation"] == "investigate_true_underperformance"

    tactic_df = review_df[review_df["review_section"] == "tactic_scorecard"].set_index("scenario_type")
    assert tactic_df.loc["multi_seller_ladder_cap", "recommendation"] == "sample_too_thin"
    assert tactic_df.loc["suppression_reactivation", "recommendation"] == "eligible_for_shadow_experiment"
