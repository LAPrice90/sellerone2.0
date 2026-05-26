from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off.F014_build_live_test_data_sufficiency_gate import build_live_test_data_sufficiency_gate


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _state(summary_df: pd.DataFrame, family: str) -> str:
    rows = summary_df.loc[summary_df["family"] == family]
    if rows.empty:
        return ""
    return str(rows.iloc[0]["state"])


def test_f014_classifies_mixed_readiness_with_replay_and_rank_gaps(tmp_path: Path) -> None:
    accuracy_path = tmp_path / "accuracy.csv"
    accuracy_summary_path = tmp_path / "accuracy_summary.csv"
    capture_pack_path = tmp_path / "capture_pack.csv"
    capture_report_path = tmp_path / "capture_report.json"
    backtest_path = tmp_path / "backtest.csv"
    output_dir = tmp_path / "out"

    accuracy_rows = [
        {
            "asin": "A1",
            "truth_decision_state": "pass",
            "actual_units_30d": "10",
            "actual_profit_30d_gbp": "25",
            "model_side_evidence_state": "estimate_only",
            "model_decision_state": "",
            "decision_judged_flag": "0",
            "model_expected_units_next_30d": "12",
            "recommended_test_qty": "",
            "estimated_demand": "",
        },
        {
            "asin": "A2",
            "truth_decision_state": "pass",
            "actual_units_30d": "8",
            "actual_profit_30d_gbp": "24",
            "model_side_evidence_state": "estimate_only",
            "model_decision_state": "",
            "decision_judged_flag": "0",
            "model_expected_units_next_30d": "9",
            "recommended_test_qty": "",
            "estimated_demand": "",
        },
        {
            "asin": "A3",
            "truth_decision_state": "fail",
            "actual_units_30d": "4",
            "actual_profit_30d_gbp": "19",
            "model_side_evidence_state": "estimate_only",
            "model_decision_state": "",
            "decision_judged_flag": "0",
            "model_expected_units_next_30d": "20",
            "recommended_test_qty": "",
            "estimated_demand": "",
        },
        {
            "asin": "A4",
            "truth_decision_state": "fail",
            "actual_units_30d": "2",
            "actual_profit_30d_gbp": "4",
            "model_side_evidence_state": "estimate_only",
            "model_decision_state": "",
            "decision_judged_flag": "0",
            "model_expected_units_next_30d": "14",
            "recommended_test_qty": "",
            "estimated_demand": "",
        },
        {
            "asin": "A5",
            "truth_decision_state": "fail",
            "actual_units_30d": "1",
            "actual_profit_30d_gbp": "-3",
            "model_side_evidence_state": "estimate_only",
            "model_decision_state": "",
            "decision_judged_flag": "0",
            "model_expected_units_next_30d": "7",
            "recommended_test_qty": "",
            "estimated_demand": "",
        },
        {
            "asin": "A6",
            "truth_decision_state": "fail",
            "actual_units_30d": "2",
            "actual_profit_30d_gbp": "10",
            "model_side_evidence_state": "estimate_only",
            "model_decision_state": "",
            "decision_judged_flag": "0",
            "model_expected_units_next_30d": "6",
            "recommended_test_qty": "",
            "estimated_demand": "",
        },
    ]
    _write_csv(accuracy_path, accuracy_rows)
    _write_csv(accuracy_summary_path, [])
    _write_csv(capture_pack_path, [{"asin": "A3"}, {"asin": "A4"}, {"asin": "A5"}, {"asin": "A6"}])
    _write_json(
        capture_report_path,
        {"metrics": {"capture_success_rows": 4, "capture_failed_rows": 0}},
    )
    _write_csv(
        backtest_path,
        [
            {"asin": "A1", "bsr_median_30d": "", "bsr_median_90d": ""},
            {"asin": "A2", "bsr_median_30d": "", "bsr_median_90d": ""},
            {"asin": "A3", "bsr_median_30d": "", "bsr_median_90d": ""},
        ],
    )

    result = build_live_test_data_sufficiency_gate(
        accuracy_path=accuracy_path,
        accuracy_summary_path=accuracy_summary_path,
        sold_capture_pack_path=capture_pack_path,
        sold_capture_report_path=capture_report_path,
        backtest_input_view_path=backtest_path,
        output_dir=output_dir,
        min_sold_rows=6,
        min_decision_rows=4,
        min_rank_overlap_rows=3,
        min_pass_rows=2,
        min_fail_rows=2,
        min_near_floor_rows=1,
        near_floor_band_gbp=1.5,
        observed_utc="2026-04-21T16:10:00Z",
    )

    assert _state(result.summary_df, "sold_truth_state") == "ready_now"
    assert _state(result.summary_df, "model_side_evidence_state") == "ready_now"
    assert _state(result.summary_df, "decision_replay_state") == "ready_after_replay_bridge"
    assert _state(result.summary_df, "sales_band_data_state") == "ready_now"
    assert _state(result.summary_df, "starter_qty_input_state") == "ready_after_replay_bridge"
    assert _state(result.summary_df, "rank_window_state") == "needs_rank_window_capture"
    assert _state(result.summary_df, "sample_mix_state") == "ready_now"

    assert set(result.gap_df["family"].tolist()) == {
        "decision_replay_state",
        "starter_qty_input_state",
        "rank_window_state",
    }
    assert result.summary_latest_path.exists()
    assert result.gap_latest_path.exists()


def test_f014_marks_all_ready_when_thresholds_are_met(tmp_path: Path) -> None:
    accuracy_path = tmp_path / "accuracy.csv"
    accuracy_summary_path = tmp_path / "accuracy_summary.csv"
    capture_pack_path = tmp_path / "capture_pack.csv"
    capture_report_path = tmp_path / "capture_report.json"
    backtest_path = tmp_path / "backtest.csv"
    output_dir = tmp_path / "out"

    _write_csv(
        accuracy_path,
        [
            {
                "asin": "B1",
                "truth_decision_state": "pass",
                "actual_units_30d": "12",
                "actual_profit_30d_gbp": "26",
                "model_side_evidence_state": "full_decision_and_estimate",
                "model_decision_state": "pass",
                "decision_judged_flag": "1",
                "model_expected_units_next_30d": "11",
                "recommended_test_qty": "5",
                "estimated_demand": "medium",
            },
            {
                "asin": "B2",
                "truth_decision_state": "fail",
                "actual_units_30d": "5",
                "actual_profit_30d_gbp": "19",
                "model_side_evidence_state": "full_decision_and_estimate",
                "model_decision_state": "fail",
                "decision_judged_flag": "1",
                "model_expected_units_next_30d": "6",
                "recommended_test_qty": "3",
                "estimated_demand": "low",
            },
            {
                "asin": "B3",
                "truth_decision_state": "fail",
                "actual_units_30d": "2",
                "actual_profit_30d_gbp": "8",
                "model_side_evidence_state": "full_decision_and_estimate",
                "model_decision_state": "fail",
                "decision_judged_flag": "1",
                "model_expected_units_next_30d": "2",
                "recommended_test_qty": "2",
                "estimated_demand": "low",
            },
            {
                "asin": "B4",
                "truth_decision_state": "pass",
                "actual_units_30d": "9",
                "actual_profit_30d_gbp": "31",
                "model_side_evidence_state": "full_decision_and_estimate",
                "model_decision_state": "pass",
                "decision_judged_flag": "1",
                "model_expected_units_next_30d": "10",
                "recommended_test_qty": "6",
                "estimated_demand": "high",
            },
        ],
    )
    _write_csv(accuracy_summary_path, [])
    _write_csv(capture_pack_path, [{"asin": "B1"}, {"asin": "B2"}, {"asin": "B3"}, {"asin": "B4"}])
    _write_json(capture_report_path, {"metrics": {"capture_success_rows": 4, "capture_failed_rows": 0}})
    _write_csv(
        backtest_path,
        [
            {"asin": "B1", "bsr_median_30d": "1000", "bsr_median_90d": "1200"},
            {"asin": "B2", "bsr_median_30d": "5000", "bsr_median_90d": "6000"},
            {"asin": "B3", "bsr_median_30d": "22000", "bsr_median_90d": "25000"},
            {"asin": "B4", "bsr_median_30d": "900", "bsr_median_90d": "1000"},
        ],
    )

    result = build_live_test_data_sufficiency_gate(
        accuracy_path=accuracy_path,
        accuracy_summary_path=accuracy_summary_path,
        sold_capture_pack_path=capture_pack_path,
        sold_capture_report_path=capture_report_path,
        backtest_input_view_path=backtest_path,
        output_dir=output_dir,
        min_sold_rows=4,
        min_decision_rows=4,
        min_rank_overlap_rows=4,
        min_pass_rows=1,
        min_fail_rows=1,
        min_near_floor_rows=1,
        near_floor_band_gbp=1.5,
        observed_utc="2026-04-21T16:11:00Z",
    )

    assert all(result.summary_df["state"].tolist()[idx] == "ready_now" for idx in range(len(result.summary_df.index)))
    assert result.gap_df.empty


def test_f014_counts_rank_window_from_full_capture_manifest_when_backtest_rank_is_blank(tmp_path: Path) -> None:
    accuracy_path = tmp_path / "accuracy.csv"
    accuracy_summary_path = tmp_path / "accuracy_summary.csv"
    capture_pack_path = tmp_path / "capture_pack.csv"
    capture_report_path = tmp_path / "capture_report.json"
    backtest_path = tmp_path / "backtest.csv"
    full_capture_dir = tmp_path / "capture_manifests"
    output_dir = tmp_path / "out"

    _write_csv(
        accuracy_path,
        [
            {
                "asin": "C1",
                "truth_decision_state": "pass",
                "actual_units_30d": "12",
                "actual_profit_30d_gbp": "30",
                "model_side_evidence_state": "full_decision_and_estimate",
                "model_decision_state": "pass",
                "decision_judged_flag": "1",
                "model_expected_units_next_30d": "10",
                "recommended_test_qty": "5",
                "estimated_demand": "high",
            },
            {
                "asin": "C2",
                "truth_decision_state": "fail",
                "actual_units_30d": "3",
                "actual_profit_30d_gbp": "18.8",
                "model_side_evidence_state": "full_decision_and_estimate",
                "model_decision_state": "fail",
                "decision_judged_flag": "1",
                "model_expected_units_next_30d": "4",
                "recommended_test_qty": "2",
                "estimated_demand": "low",
            },
        ],
    )
    _write_csv(accuracy_summary_path, [])
    _write_csv(capture_pack_path, [{"asin": "C1"}, {"asin": "C2"}])
    _write_json(capture_report_path, {"metrics": {"capture_success_rows": 2, "capture_failed_rows": 0}})
    _write_csv(
        backtest_path,
        [
            {"asin": "C1", "bsr_median_30d": "", "bsr_median_90d": ""},
            {"asin": "C2", "bsr_median_30d": "", "bsr_median_90d": ""},
        ],
    )

    full_capture_dir.mkdir(parents=True, exist_ok=True)
    raw_c1 = tmp_path / "raw_c1.json"
    raw_c2 = tmp_path / "raw_c2.json"
    raw_c1.write_text(
        json.dumps({"scraped_data": {"chart_raw_bsr_daily_series": "2026-03-01=22000;2026-03-02=21000;2026-03-03=20000"}}),
        encoding="utf-8",
    )
    raw_c2.write_text(
        json.dumps({"scraped_data": {"chart_raw_bsr_daily_series": "2026-03-01=80000;2026-03-02=82000;2026-03-03=78000"}}),
        encoding="utf-8",
    )
    _write_csv(
        full_capture_dir / "f_full_capture_manifest_20260421T200000Z.csv",
        [
            {
                "observed_utc": "2026-04-21T20:00:00Z",
                "run_id": "20260421T200000Z_C1_p1",
                "asin": "C1",
                "capture_status": "success",
                "raw_json_path": str(raw_c1),
            },
            {
                "observed_utc": "2026-04-21T20:00:00Z",
                "run_id": "20260421T200000Z_C2_p1",
                "asin": "C2",
                "capture_status": "success",
                "raw_json_path": str(raw_c2),
            },
        ],
    )

    result = build_live_test_data_sufficiency_gate(
        accuracy_path=accuracy_path,
        accuracy_summary_path=accuracy_summary_path,
        sold_capture_pack_path=capture_pack_path,
        sold_capture_report_path=capture_report_path,
        backtest_input_view_path=backtest_path,
        full_capture_manifest_dir=full_capture_dir,
        output_dir=output_dir,
        min_sold_rows=2,
        min_decision_rows=2,
        min_rank_overlap_rows=2,
        min_pass_rows=1,
        min_fail_rows=1,
        min_near_floor_rows=1,
        near_floor_band_gbp=1.5,
        observed_utc="2026-04-21T16:12:00Z",
    )

    assert _state(result.summary_df, "rank_window_state") == "ready_now"
