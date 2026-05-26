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

from scripts.one_off import HF013_build_strategy_experiment_queue as hf013


def _write_csv(path: Path, rows: list[dict[str, object]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_hf013_build_strategy_experiment_queue(tmp_path: Path, monkeypatch) -> None:
    scorecard_path = tmp_path / "out" / "analysis_reports" / "hf_strategy_scorecard_latest.csv"
    review_path = tmp_path / "out" / "reports" / "hf_strategy_review_pack_latest.csv"

    _write_csv(
        scorecard_path,
        [
            {
                "snapshot_utc": "2026-04-18T12:30:00Z",
                "scenario_type": "multi_seller_ladder_cap",
                "decision_rows": "87",
                "sample_min_rows": "150",
                "sample_mature_flag": "0",
                "review_status": "blocked",
                "write_applied_rate": "0.0100",
                "failed_rate": "0.3000",
                "expired_rate": "0.5000",
            },
            {
                "snapshot_utc": "2026-04-18T12:30:00Z",
                "scenario_type": "share_hold",
                "decision_rows": "300",
                "sample_min_rows": "30",
                "sample_mature_flag": "1",
                "review_status": "overlap_first",
                "write_applied_rate": "0.2500",
                "failed_rate": "0.0100",
                "expired_rate": "0.0200",
            },
            {
                "snapshot_utc": "2026-04-18T12:30:00Z",
                "scenario_type": "controlled_exit",
                "decision_rows": "45",
                "sample_min_rows": "30",
                "sample_mature_flag": "1",
                "review_status": "keep_observing",
                "write_applied_rate": "0.2000",
                "failed_rate": "0.4200",
                "expired_rate": "0.1500",
            },
            {
                "snapshot_utc": "2026-04-18T12:30:00Z",
                "scenario_type": "suppression_reactivation",
                "decision_rows": "120",
                "sample_min_rows": "20",
                "sample_mature_flag": "1",
                "review_status": "eligible_shadow",
                "write_applied_rate": "0.3500",
                "failed_rate": "0.0100",
                "expired_rate": "0.0200",
            },
        ],
        columns=[
            "snapshot_utc",
            "scenario_type",
            "decision_rows",
            "sample_min_rows",
            "sample_mature_flag",
            "review_status",
            "write_applied_rate",
            "failed_rate",
            "expired_rate",
        ],
    )

    _write_csv(
        review_path,
        [
            {
                "snapshot_utc": "2026-04-18T12:35:00Z",
                "review_section": "tactic_scorecard",
                "scenario_type": "multi_seller_ladder_cap",
                "recommendation": "sample_too_thin",
            },
            {
                "snapshot_utc": "2026-04-18T12:35:00Z",
                "review_section": "tactic_scorecard",
                "scenario_type": "share_hold",
                "recommendation": "recover_overlap_first",
            },
            {
                "snapshot_utc": "2026-04-18T12:35:00Z",
                "review_section": "tactic_scorecard",
                "scenario_type": "controlled_exit",
                "recommendation": "keep_observing",
            },
            {
                "snapshot_utc": "2026-04-18T12:35:00Z",
                "review_section": "tactic_scorecard",
                "scenario_type": "suppression_reactivation",
                "recommendation": "eligible_for_shadow_experiment",
            },
        ],
        columns=["snapshot_utc", "review_section", "scenario_type", "recommendation"],
    )

    monkeypatch.setattr(hf013, "SCORECARD_PATH", scorecard_path)
    monkeypatch.setattr(hf013, "REVIEW_PACK_PATH", review_path)
    monkeypatch.setattr(hf013, "REQUIRED_INPUTS", [scorecard_path, review_path])
    monkeypatch.setattr(hf013, "_utc_now_iso", lambda: "2026-04-18T12:40:00Z")

    output_path = tmp_path / "out" / "analysis_reports" / "hf_strategy_experiment_queue_latest.csv"
    result = hf013.build_strategy_experiment_queue(output_path=output_path)

    assert result.rows == 4
    assert result.pass_rows == 1
    assert result.review_rows == 1
    assert result.fail_rows == 2

    queue_df = pd.read_csv(output_path, dtype=str).fillna("").set_index("scenario_type")
    assert queue_df.columns.tolist() == [col for col in hf013.QUEUE_COLUMNS if col != "scenario_type"]
    assert (queue_df["shadow_only_flag"] == "1").all()

    assert queue_df.loc["multi_seller_ladder_cap", "risk_gate_status"] == "fail"
    assert queue_df.loc["multi_seller_ladder_cap", "max_cohort_size"] == "0"
    assert queue_df.loc["share_hold", "risk_gate_status"] == "fail"
    assert "missing_baseline_overlap_recovery_required" in queue_df.loc["share_hold", "required_review_reason"]

    assert queue_df.loc["controlled_exit", "risk_gate_status"] == "review"
    assert queue_df.loc["controlled_exit", "max_cohort_size"] == "10"

    assert queue_df.loc["suppression_reactivation", "risk_gate_status"] == "pass"
    assert int(queue_df.loc["suppression_reactivation", "max_cohort_size"]) >= 10
