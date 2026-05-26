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

from scripts.one_off.F034_score_f032_blind_agent_runs import score_f032_blind_agent_runs


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _metric(df: pd.DataFrame, metric: str) -> dict[str, str]:
    rows = df.loc[df["metric"] == metric]
    assert not rows.empty, metric
    return rows.iloc[0].to_dict()


def test_f034_scores_three_blind_runs_and_consistency(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.csv"
    run_dir = tmp_path / "runs"
    _write_csv(
        expected_path,
        [
            {
                "blind_case_id": "case-clear",
                "supplier_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "expected_action": "allow_if_other_checks_pass",
                "acceptable_actions": "allow_if_other_checks_pass",
                "expected_bucket": "ai_review_clear",
            },
            {
                "blind_case_id": "case-fail",
                "supplier_sku": "SKU-FAIL",
                "asin": "ASIN-FAIL",
                "expected_action": "remove_from_clean_pass",
                "acceptable_actions": "remove_from_clean_pass",
                "expected_bucket": "high_roi_identity_suspicion",
            },
            {
                "blind_case_id": "case-rescan",
                "supplier_sku": "SKU-RESCAN",
                "asin": "ASIN-RESCAN",
                "expected_action": "manual_review",
                "acceptable_actions": "manual_review|rescan_needed",
                "expected_bucket": "needs_user_guidance",
            },
        ],
    )
    rows = [
        {
            "blind_case_id": "case-clear",
            "f032_action": "allow_if_other_checks_pass",
            "f032_decision_bucket": "ai_review_clear",
            "confidence": "high",
            "reason_short": "titles match",
        },
        {
            "blind_case_id": "case-fail",
            "f032_action": "remove_from_clean_pass",
            "f032_decision_bucket": "high_roi_identity_suspicion",
            "confidence": "high",
            "reason_short": "high roi wrong product",
        },
        {
            "blind_case_id": "case-rescan",
            "f032_action": "rescan_needed",
            "f032_decision_bucket": "missing_evidence_rescan_needed",
            "confidence": "high",
            "reason_short": "missing title evidence",
        },
    ]
    for run_no in range(1, 4):
        _write_csv(run_dir / f"f032_blind_agent_run_{run_no}_latest.csv", rows)

    result = score_f032_blind_agent_runs(
        expected_path=expected_path,
        run_dir=run_dir,
        results_path=tmp_path / "results.csv",
        case_consistency_path=tmp_path / "consistency.csv",
        health_path=tmp_path / "health.csv",
        summary_path=tmp_path / "summary.md",
        observed_utc="2026-05-20T12:00:00Z",
    )

    assert result.report["agent_run_file_count"] == 3
    assert result.report["agent_decision_rows"] == 9
    assert result.report["acceptable_action_agreement_pct"] == 100.0
    assert result.report["action_consistency_pct"] == 100.0
    assert result.report["fail_to_clear_flip_cases"] == 0
    assert _metric(result.health_df, "agent_decision_rows")["status"] == "PASS"
    assert _metric(result.health_df, "fail_to_clear_flip_cases")["status"] == "PASS"
    assert (tmp_path / "results.csv").exists()
    assert (tmp_path / "consistency.csv").exists()
    assert (tmp_path / "summary.md").exists()


def test_f034_health_fails_when_run_file_is_missing_required_columns(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.csv"
    run_dir = tmp_path / "runs"
    _write_csv(
        expected_path,
        [
            {
                "blind_case_id": "case-clear",
                "supplier_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "expected_action": "allow_if_other_checks_pass",
                "acceptable_actions": "allow_if_other_checks_pass",
                "expected_bucket": "ai_review_clear",
            }
        ],
    )
    _write_csv(
        run_dir / "f032_blind_agent_run_1_latest.csv",
        [
            {
                "blind_case_id": "case-clear",
                "f032_action": "allow_if_other_checks_pass",
            }
        ],
    )

    result = score_f032_blind_agent_runs(
        expected_path=expected_path,
        run_dir=run_dir,
        results_path=tmp_path / "results.csv",
        case_consistency_path=tmp_path / "consistency.csv",
        health_path=tmp_path / "health.csv",
        summary_path=tmp_path / "summary.md",
        observed_utc="2026-05-20T12:00:00Z",
    )

    assert _metric(result.health_df, "run_files_missing_required_columns")["status"] == "FAIL"
    assert _metric(result.health_df, "agent_decision_rows")["status"] == "FAIL"
