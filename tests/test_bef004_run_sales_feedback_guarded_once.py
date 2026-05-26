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

from scripts.one_off import BEF004_run_sales_feedback_guarded_once as bef004


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_guarded_run_blocks_when_freshness_fail_active(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "838.53", "status": "fail", "notes": "lag_gt_fail_threshold"},
            {"metric": "freshness_fail_count", "value": "1", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [{"asin": "A1", "actuals_basis": "summary_asin_map"}],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "A1", "learning_outcome": "right_call"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "A1", "example_class": "right_call"}],
    )

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T16:10:00Z",
        run_builders=False,
    )

    assert result.report_latest_path.exists()
    guard = result.report["guard_decision"]
    assert guard["guard_status"] == "blocked"
    assert "freshness_fail_active" in guard["hard_block_reasons"]
    assert guard["next_action"] == "refresh_ledger_then_rerun_guarded_once"


def test_guarded_run_ready_clean_when_core_inputs_exist(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "5.00", "status": "ok", "notes": "lag_within_threshold"},
            {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [
            {"asin": "A1", "actuals_basis": "summary_direct_bridge"},
            {"asin": "A1", "actuals_basis": "operational_baseline"},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "A1", "learning_outcome": "right_call"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "A1", "example_class": "right_call"}],
    )

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T16:11:00Z",
        run_builders=False,
    )

    guard = result.report["guard_decision"]
    metrics = result.report["metrics"]
    assert guard["guard_status"] == "ready"
    assert guard["readiness_label"] == "ready_clean"
    assert guard["hard_block_reasons"] == []
    assert guard["warnings"] == []
    assert guard["next_action"] == "safe_for_scheduled_one_off"
    assert int(metrics["actuals_summary_direct_bridge_rows"]) == 1


def test_guarded_run_marks_seed_replay_overlap_recovery_when_summary_map_is_zero(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "5.00", "status": "ok", "notes": "lag_within_threshold"},
            {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [
            {"asin": "A1", "actuals_basis": "operational_seed_replay"},
            {"asin": "A1", "actuals_basis": "operational_baseline"},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "A1", "learning_outcome": "pending_outcome"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "A1", "example_class": "overlap_gap_no_summary_match"}],
    )

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T16:11:30Z",
        run_builders=False,
    )

    guard = result.report["guard_decision"]
    metrics = result.report["metrics"]
    assert guard["guard_status"] == "ready"
    assert "summary_asin_overlap_zero" not in guard["warnings"]
    assert "summary_asin_overlap_recovered_by_seed_replay" in guard["warnings"]
    assert "summary_direct_bridge_overlap_zero" in guard["warnings"]
    assert guard["next_action"] == "monitor_seed_replay_and_expand_true_overlap"
    assert int(metrics["actuals_seed_replay_rows"]) == 1
    assert int(metrics["actuals_recovered_overlap_rows"]) == 1
    assert int(metrics["actuals_summary_direct_bridge_rows"]) == 0


def test_guarded_run_marks_alignment_overlap_recovery_when_summary_map_is_zero(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "5.00", "status": "ok", "notes": "lag_within_threshold"},
            {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [
            {"asin": "A1", "actuals_basis": "alignment_asin_map"},
            {"asin": "A1", "actuals_basis": "operational_baseline"},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "A1", "learning_outcome": "right_call"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "A1", "example_class": "model_error_demand_too_high"}],
    )

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T16:11:40Z",
        run_builders=False,
    )

    guard = result.report["guard_decision"]
    metrics = result.report["metrics"]
    assert guard["guard_status"] == "ready"
    assert "summary_asin_overlap_recovered_by_alignment_map" in guard["warnings"]
    assert "summary_direct_bridge_overlap_zero" in guard["warnings"]
    assert guard["next_action"] == "monitor_alignment_map_and_expand_true_overlap"
    assert int(metrics["actuals_alignment_map_rows"]) == 1
    assert int(metrics["actuals_native_overlap_rows"]) == 1
    assert int(metrics["actuals_summary_direct_bridge_rows"]) == 0


def test_guarded_run_flags_direct_bridge_gap_when_only_summary_asin_overlap_exists(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "5.00", "status": "ok", "notes": "lag_within_threshold"},
            {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [
            {"asin": "A1", "actuals_basis": "summary_asin_map"},
            {"asin": "A1", "actuals_basis": "operational_baseline"},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "A1", "learning_outcome": "right_call"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "A1", "example_class": "right_call"}],
    )

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T16:11:50Z",
        run_builders=False,
    )

    guard = result.report["guard_decision"]
    metrics = result.report["metrics"]
    assert guard["guard_status"] == "ready"
    assert "summary_direct_bridge_overlap_zero" in guard["warnings"]
    assert guard["next_action"] == "expand_identity_bridge_resolution"
    assert int(metrics["actuals_summary_direct_bridge_rows"]) == 0
    assert int(metrics["actuals_summary_asin_rows"]) == 1


def test_guarded_run_uses_scope_expansion_action_when_candidates_ready(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "5.00", "status": "ok", "notes": "lag_within_threshold"},
            {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [
            {"asin": "A1", "actuals_basis": "alignment_asin_map"},
            {"asin": "A1", "actuals_basis": "operational_baseline"},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "A1", "learning_outcome": "right_call"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "A1", "example_class": "right_call"}],
    )
    _write_csv(
        analysis_dir / "hf_scope_expansion_summary_latest.csv",
        [
            {"snapshot_utc": "2026-04-21T09:45:00Z", "metric_name": "candidate_rows_total", "metric_value": "20", "notes": ""},
            {"snapshot_utc": "2026-04-21T09:45:00Z", "metric_name": "outside_h_scope_rows", "metric_value": "12", "notes": ""},
            {"snapshot_utc": "2026-04-21T09:45:00Z", "metric_name": "no_asin_rows", "metric_value": "5", "notes": ""},
            {"snapshot_utc": "2026-04-21T09:45:00Z", "metric_name": "stale_source_rows", "metric_value": "3", "notes": ""},
        ],
    )

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-21T09:46:00Z",
        run_builders=False,
    )

    guard = result.report["guard_decision"]
    metrics = result.report["metrics"]
    assert guard["guard_status"] == "ready"
    assert "scope_expansion_candidates_ready" in guard["warnings"]
    assert guard["next_action"] == "run_scope_expansion_capture_path"
    assert int(metrics["scope_expansion_candidate_rows"]) == 20
    assert int(metrics["scope_expansion_outside_h_scope_rows"]) == 12


def test_guarded_run_prioritizes_sold_truth_replay_capture_when_queue_exists(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "5.00", "status": "ok", "notes": "lag_within_threshold"},
            {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [
            {"asin": "A1", "actuals_basis": "alignment_asin_map"},
            {"asin": "A1", "actuals_basis": "operational_baseline"},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "A1", "learning_outcome": "right_call"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "A1", "example_class": "right_call"}],
    )
    _write_csv(
        analysis_dir / "f_sold_truth_replay_capture_queue_latest.csv",
        [
            {
                "observed_utc": "2026-04-21T12:30:00Z",
                "asin": "B00TEST001",
                "seller_sku": "OPER::B00TEST001",
                "amazon_link": "https://www.amazon.co.uk/dp/B00TEST001",
                "capture_reason": "missing_model_side_evidence_for_sold_truth_row",
                "current_model_side_evidence_state": "missing",
            }
        ],
    )
    _write_csv(
        analysis_dir / "hf_scope_expansion_summary_latest.csv",
        [
            {"snapshot_utc": "2026-04-21T09:45:00Z", "metric_name": "candidate_rows_total", "metric_value": "20", "notes": ""},
            {"snapshot_utc": "2026-04-21T09:45:00Z", "metric_name": "outside_h_scope_rows", "metric_value": "12", "notes": ""},
            {"snapshot_utc": "2026-04-21T09:45:00Z", "metric_name": "no_asin_rows", "metric_value": "5", "notes": ""},
            {"snapshot_utc": "2026-04-21T09:45:00Z", "metric_name": "stale_source_rows", "metric_value": "3", "notes": ""},
        ],
    )

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-21T12:31:00Z",
        run_builders=False,
    )

    guard = result.report["guard_decision"]
    metrics = result.report["metrics"]
    assert guard["guard_status"] == "ready"
    assert "sold_truth_replay_capture_required" in guard["warnings"]
    assert guard["next_action"] == "run_sold_truth_replay_capture_path"
    assert int(metrics["sold_truth_replay_queue_rows"]) == 1


def test_guarded_run_uses_identity_resolution_when_direct_bridge_not_feasible(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    systems_dir = tmp_path / "out" / "systems" / "F" / "live"
    systems_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "5.00", "status": "ok", "notes": "lag_within_threshold"},
            {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [
            {"asin": "B00BASE001", "actuals_basis": "operational_baseline"},
            {"asin": "B00MAP001", "actuals_basis": "alignment_asin_map"},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "B00BASE001", "learning_outcome": "right_call"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "B00BASE001", "example_class": "right_call"}],
    )
    _write_csv(
        analysis_dir / "hf_scope_expansion_summary_latest.csv",
        [
            {"snapshot_utc": "2026-04-21T14:00:00Z", "metric_name": "candidate_rows_total", "metric_value": "30", "notes": ""},
            {"snapshot_utc": "2026-04-21T14:00:00Z", "metric_name": "outside_h_scope_rows", "metric_value": "12", "notes": ""},
            {"snapshot_utc": "2026-04-21T14:00:00Z", "metric_name": "no_asin_rows", "metric_value": "8", "notes": ""},
            {"snapshot_utc": "2026-04-21T14:00:00Z", "metric_name": "stale_source_rows", "metric_value": "4", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "hf_learning_identity_bridge_latest.csv",
        [
            {
                "snapshot_utc": "2026-04-21T14:00:00Z",
                "supplier_sku": "SUP001",
                "asin": "B00NOTSOLD1",
                "sku": "",
                "sku_resolution_status": "UNRESOLVED_ASIN_NOT_IN_H_SCOPE",
            }
        ],
    )
    _write_csv(
        systems_dir / "feeder_backtest_summary_live.csv",
        [
            {
                "observed_utc": "2026-04-21T14:00:00Z",
                "seller_sku": "SUP001",
                "asin": "B00NOTSOLD1",
                "decision_state": "fail",
            }
        ],
    )

    original_summary_path = bef004.SUMMARY_LIVE_PATH
    try:
        bef004.SUMMARY_LIVE_PATH = systems_dir / "feeder_backtest_summary_live.csv"
        result = bef004.run_sales_feedback_guarded_once(
            output_dir=analysis_dir,
            observed_utc="2026-04-21T14:01:00Z",
            run_builders=False,
        )
    finally:
        bef004.SUMMARY_LIVE_PATH = original_summary_path

    guard = result.report["guard_decision"]
    metrics = result.report["metrics"]
    assert guard["guard_status"] == "ready"
    assert "summary_direct_bridge_no_feasible_overlap" in guard["warnings"]
    assert "scope_expansion_candidates_ready" not in guard["warnings"]
    assert guard["next_action"] == "expand_identity_bridge_resolution"
    assert int(metrics["direct_bridge_summary_identity_pair_overlap_rows"]) == 1
    assert int(metrics["direct_bridge_feasible_pair_rows"]) == 0


def test_guarded_run_routes_to_replay_coverage_when_sold_decision_coverage_low(tmp_path: Path) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    _write_csv(
        analysis_dir / "bef_sales_feedback_health_latest.csv",
        [
            {"metric": "freshness_lag_minutes", "value": "5.00", "status": "ok", "notes": "lag_within_threshold"},
            {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_actuals_latest.csv",
        [
            {"asin": "B00BASE001", "actuals_basis": "operational_baseline"},
            {"asin": "B00MAP001", "actuals_basis": "alignment_asin_map"},
        ],
    )
    _write_csv(
        analysis_dir / "f_sales_history_learning_review_latest.csv",
        [{"asin": "B00BASE001", "learning_outcome": "right_call"}],
    )
    _write_csv(
        analysis_dir / "bef_sales_feedback_examples_latest.csv",
        [{"asin": "B00BASE001", "example_class": "right_call"}],
    )
    _write_csv(
        analysis_dir / "f_sales_history_accuracy_summary_latest.csv",
        [
            {"observed_utc": "2026-04-21T15:00:00Z", "metric": "sold_rows_total", "value": "57"},
            {
                "observed_utc": "2026-04-21T15:00:00Z",
                "metric": "sold_decision_replay_coverage_rows",
                "value": "10",
            },
        ],
    )
    _write_csv(
        analysis_dir / "hf_scope_expansion_summary_latest.csv",
        [
            {"snapshot_utc": "2026-04-21T15:00:00Z", "metric_name": "candidate_rows_total", "metric_value": "20", "notes": ""},
            {"snapshot_utc": "2026-04-21T15:00:00Z", "metric_name": "outside_h_scope_rows", "metric_value": "12", "notes": ""},
            {"snapshot_utc": "2026-04-21T15:00:00Z", "metric_name": "no_asin_rows", "metric_value": "5", "notes": ""},
            {"snapshot_utc": "2026-04-21T15:00:00Z", "metric_name": "stale_source_rows", "metric_value": "3", "notes": ""},
        ],
    )

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-21T15:01:00Z",
        run_builders=False,
    )

    guard = result.report["guard_decision"]
    metrics = result.report["metrics"]
    assert guard["guard_status"] == "ready"
    assert "sold_decision_replay_coverage_low" in guard["warnings"]
    assert guard["next_action"] == "expand_sold_decision_replay_coverage"
    assert int(metrics["sold_rows_total"]) == 57
    assert int(metrics["sold_decision_replay_coverage_rows"]) == 10


def test_guarded_run_executes_builder_chain_when_enabled(tmp_path: Path, monkeypatch) -> None:
    analysis_dir = tmp_path / "out" / "analysis_reports"
    call_order: list[str] = []

    def fake_bef000(*, output_dir: Path, observed_utc: str):
        call_order.append("BEF000")
        _write_csv(
            output_dir / "bef_sales_feedback_health_latest.csv",
            [
                {"metric": "freshness_lag_minutes", "value": "10.00", "status": "ok", "notes": "lag_within_threshold"},
                {"metric": "freshness_fail_count", "value": "0", "status": "ok", "notes": ""},
            ],
        )
        return None

    def fake_bef001(*, output_dir: Path, observed_utc: str):
        call_order.append("BEF001")
        return None

    def fake_bef002(*, output_dir: Path, observed_utc: str):
        call_order.append("BEF002")
        _write_csv(
            output_dir / "f_sales_history_learning_actuals_latest.csv",
            [{"asin": "A1", "actuals_basis": "summary_asin_map"}],
        )
        return None

    def fake_f012(*, actuals_path: Path, output_dir: Path, observed_utc: str):
        call_order.append("F012")
        _write_csv(
            output_dir / "f_sales_history_learning_review_latest.csv",
            [{"asin": "A1", "learning_outcome": "right_call"}],
        )
        return None

    def fake_bef003(*, output_path: Path, observed_utc: str):
        call_order.append("BEF003")
        _write_csv(
            output_path,
            [{"asin": "A1", "example_class": "right_call"}],
        )
        return None

    monkeypatch.setattr(bef004.bef000, "build_sales_truth_foundation", fake_bef000)
    monkeypatch.setattr(bef004.bef001, "build_operational_feedback_seed", fake_bef001)
    monkeypatch.setattr(bef004.bef002, "build_sales_feedback_actuals", fake_bef002)
    monkeypatch.setattr(bef004.f012, "build_sales_history_learning_pack", fake_f012)
    monkeypatch.setattr(bef004.bef003, "build_sales_feedback_examples", fake_bef003)

    result = bef004.run_sales_feedback_guarded_once(
        output_dir=analysis_dir,
        observed_utc="2026-04-20T16:12:00Z",
        run_builders=True,
    )

    assert call_order == ["BEF000", "BEF001", "BEF002", "F012", "BEF003"]
    assert len(result.report["pipeline"]["builder_steps"]) == 5
    assert result.report["guard_decision"]["guard_status"] == "ready"
