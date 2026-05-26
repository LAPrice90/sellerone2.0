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

from scripts.one_off.BEF006_build_sold_decision_replay_bridge import build_sold_decision_replay_bridge


def _write_csv(path: Path, rows: list[dict[str, object]], *, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=columns) if columns is not None else pd.DataFrame(rows)
    frame.to_csv(path, index=False)


def _summary_metric(summary_df: pd.DataFrame, name: str) -> str:
    rows = summary_df.loc[summary_df["metric"] == name]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["value"])


def test_bef006_replay_decision_with_alignment_fill_and_commercial_derivation(tmp_path: Path) -> None:
    sold_truth_path = tmp_path / "actuals.csv"
    review_path = tmp_path / "review.csv"
    summary_path = tmp_path / "summary.csv"
    alignment_path = tmp_path / "alignment.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sold_truth_path,
        [
            {
                "seller_sku": "OPER::B00TEST001",
                "asin": "B00TEST001",
                "actual_units_30d": "3",
                "actual_units_60d": "3",
                "actual_units_90d": "3",
                "actuals_basis": "operational_baseline",
                "actuals_observed_utc": "2026-04-21T15:00:00Z",
            }
        ],
    )
    _write_csv(
        review_path,
        [
            {
                "observed_utc": "2026-04-21T15:01:00Z",
                "decision_snapshot_utc": "2026-04-21T14:59:00Z",
                "seller_sku": "SKU-001",
                "asin": "B00TEST001",
                "decision_state_at_snapshot": "pass",
                "decision_confidence_at_snapshot": "medium",
                "expected_units_next_30d": "",
                "expected_profit_next_30d_gbp": "",
            }
        ],
    )
    _write_csv(summary_path, [], columns=["observed_utc", "seller_sku", "asin"])
    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-21T15:02:00Z",
                "asin": "B00TEST001",
                "expected_units_30d": "9",
                "expected_profit_30d_gbp": "30",
            }
        ],
    )

    result = build_sold_decision_replay_bridge(
        sold_truth_path=sold_truth_path,
        review_path=review_path,
        summary_path=summary_path,
        alignment_path=alignment_path,
        output_dir=output_dir,
        output_path=output_dir / "f_sold_decision_replay_latest.csv",
        summary_output_path=output_dir / "f_sold_decision_replay_summary_latest.csv",
        observed_utc="2026-04-21T15:05:00Z",
    )

    assert len(result.replay_df.index) == 1
    row = result.replay_df.iloc[0]
    assert row["decision_source"] == "replay_bridge"
    assert row["estimate_units_source"] == "alignment_fill"
    assert row["estimate_profit_source"] == "alignment_fill"
    assert row["model_decision_state"] == "pass"
    assert row["model_decision_confidence"] == "medium"
    assert row["model_expected_units_next_30d"] == "9"
    assert row["model_expected_profit_next_30d_gbp"] == "30"
    assert row["estimated_demand"] == "high"
    assert row["recommendation_status"] == "approve_test_buy"
    assert row["recommended_test_qty"] == "8"
    assert row["commercial_guidance_source"] == "derived_from_model_expected_units"

    assert _summary_metric(result.summary_df, "sold_rows_total") == "1"
    assert _summary_metric(result.summary_df, "sold_decision_replay_coverage_rows") == "1"
    assert _summary_metric(result.summary_df, "rows_with_recommended_test_qty") == "1"


def test_bef006_summary_fallback_when_replay_missing(tmp_path: Path) -> None:
    sold_truth_path = tmp_path / "actuals.csv"
    review_path = tmp_path / "review.csv"
    summary_path = tmp_path / "summary.csv"
    alignment_path = tmp_path / "alignment.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        sold_truth_path,
        [
            {
                "seller_sku": "OPER::B00TEST002",
                "asin": "B00TEST002",
                "actual_units_30d": "1",
                "actual_units_60d": "1",
                "actual_units_90d": "1",
                "actuals_basis": "operational_baseline",
                "actuals_observed_utc": "2026-04-21T16:00:00Z",
            }
        ],
    )
    _write_csv(review_path, [], columns=["observed_utc", "decision_snapshot_utc", "seller_sku", "asin"])
    _write_csv(
        summary_path,
        [
            {
                "observed_utc": "2026-04-21T16:01:00Z",
                "seller_sku": "SKU-002",
                "asin": "B00TEST002",
                "decision_state": "fail",
                "decision_confidence": "low",
                "expected_units_next_30d": "2",
                "expected_profit_next_30d_gbp": "5",
                "minimum_expected_profit_gbp": "20",
            }
        ],
    )
    _write_csv(
        alignment_path,
        [
            {
                "alignment_window_end_utc": "2026-04-21T16:02:00Z",
                "asin": "B00TEST002",
                "expected_units_30d": "20",
                "expected_profit_30d_gbp": "80",
            }
        ],
    )

    result = build_sold_decision_replay_bridge(
        sold_truth_path=sold_truth_path,
        review_path=review_path,
        summary_path=summary_path,
        alignment_path=alignment_path,
        output_dir=output_dir,
        output_path=output_dir / "f_sold_decision_replay_latest.csv",
        summary_output_path=output_dir / "f_sold_decision_replay_summary_latest.csv",
        observed_utc="2026-04-21T16:05:00Z",
    )

    assert len(result.replay_df.index) == 1
    row = result.replay_df.iloc[0]
    assert row["decision_source"] == "summary_live"
    assert row["model_source"] == "summary_live"
    assert row["model_decision_state"] == "fail"
    assert row["model_expected_units_next_30d"] == "2"
    assert row["model_expected_profit_next_30d_gbp"] == "5"
    assert row["estimated_demand"] == "low"
    assert row["recommendation_status"] == "reject"
    assert row["recommended_test_qty"] == "0"

    assert _summary_metric(result.summary_df, "sold_decision_replay_coverage_rows") == "0"
