from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O050_build_repricing_tracker_view import (
    build_repricing_tracker_glance_df,
    build_repricing_tracker_view,
    filter_repricing_tracker_view,
    repricer_tracker_counts,
)
from scripts.flows.O._schemas import get_o_output_contract


def _write_h_sources(root: Path) -> None:
    runtime_path = root / "out" / "phase1_runtime_floor_snapshot_latest.csv"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "snapshot_utc": "2026-05-01T14:20:53Z",
                "sku": "SKU-APPLY",
                "asin": "ASIN-1",
                "current_cycle_run_id": "RUN-LATEST",
                "execution_state": "REGAIN",
                "execution_write_status": "APPLIED",
                "execution_write_error": "",
                "execution_old_price_gbp": "9.99",
                "execution_new_price_gbp": "9.49",
                "execution_hard_floor_gbp": "8.50",
                "execution_final_ceiling_landed_gbp": "11.00",
                "write_attempted_flag": "1",
                "write_applied_flag": "1",
                "truth_status": "WRITE_APPLIED",
                "true_binding_ceiling_gbp": "11.00",
                "unified_buy_box_state": "LOST_TO_COMPETITOR",
                "unified_strategy_state": "REGAIN",
                "unified_writer_outcome": "APPLIED",
                "current_cycle_decision": "execute",
                "current_cycle_decision_reason_code": "eligible",
                "current_cycle_blocker_code": "",
                "trace_asof_utc": "2026-05-01T14:21:00Z",
                "trace_floor_total_gbp": "8.50",
                "execution_reason_codes_json": "[]",
            },
            {
                "snapshot_utc": "2026-05-01T14:20:53Z",
                "sku": "SKU-BLANK",
                "asin": "ASIN-2",
                "current_cycle_run_id": "RUN-LATEST",
                "execution_state": "",
                "execution_write_status": "",
                "execution_write_error": "",
                "execution_old_price_gbp": "",
                "execution_new_price_gbp": "",
                "execution_hard_floor_gbp": "",
                "execution_final_ceiling_landed_gbp": "",
                "write_attempted_flag": "0",
                "write_applied_flag": "0",
                "truth_status": "",
                "true_binding_ceiling_gbp": "",
                "unified_buy_box_state": "",
                "unified_strategy_state": "",
                "unified_writer_outcome": "",
                "current_cycle_decision": "skip_no_market_data",
                "current_cycle_decision_reason_code": "",
                "current_cycle_blocker_code": "NO_MARKET_DATA",
                "trace_asof_utc": "",
                "trace_floor_total_gbp": "",
                "execution_reason_codes_json": "",
            },
            {
                "snapshot_utc": "2026-05-01T14:05:05Z",
                "sku": "SKU-OLD",
                "asin": "ASIN-3",
                "current_cycle_run_id": "RUN-OLD",
                "execution_state": "HOLD_OBSERVE",
                "execution_write_status": "NO_WRITE_REQUIRED",
                "execution_write_error": "",
                "execution_old_price_gbp": "5.00",
                "execution_new_price_gbp": "5.00",
                "execution_hard_floor_gbp": "4.50",
                "execution_final_ceiling_landed_gbp": "6.00",
                "write_attempted_flag": "0",
                "write_applied_flag": "0",
                "truth_status": "READ_ONLY",
                "true_binding_ceiling_gbp": "6.00",
                "unified_buy_box_state": "NORMAL",
                "unified_strategy_state": "HOLD_OBSERVE",
                "unified_writer_outcome": "NO_WRITE_REQUIRED",
                "current_cycle_decision": "execute",
                "current_cycle_decision_reason_code": "eligible",
                "current_cycle_blocker_code": "",
                "trace_asof_utc": "",
                "trace_floor_total_gbp": "",
                "execution_reason_codes_json": "",
            },
        ]
    ).to_csv(runtime_path, index=False)
    pd.DataFrame(
        [
            {"sku": "SKU-APPLY", "execution_write_status": "APPLIED"},
            {"sku": "SKU-BLANK", "execution_write_status": ""},
        ]
    ).to_csv(root / "out" / "pricing_output.csv", index=False)
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    (live / "H_cycle_last_terminal_info.txt").write_text(
        "run_id=RUN-LATEST\nutc=2026-05-01T14:35:40Z\nstate=finalized\npublish_status=ok\n",
        encoding="utf-8",
    )
    (live / "H_cycle_last_publish_info.txt").write_text(
        "run_id=RUN-LATEST\nutc=2026-05-01T14:20:53Z\nrows=2\nstatus=ok\n",
        encoding="utf-8",
    )


def test_o050_builds_read_only_repricing_tracker_and_health(tmp_path: Path) -> None:
    _write_h_sources(tmp_path)

    out_df = build_repricing_tracker_view(root=tmp_path, asof_utc="2026-05-01T15:00:00Z")

    assert len(out_df.index) == 3
    counts = repricer_tracker_counts(out_df)
    assert counts == {
        "rows": 3,
        "latest_run_rows": 2,
        "write_applied": 1,
        "write_attempted": 1,
        "eligible_to_write": 2,
        "missing_write_status": 1,
    }
    blank = out_df[out_df["sku"] == "SKU-BLANK"].iloc[0]
    assert blank["write_status_issue"] == "blank_execution_write_status"
    assert blank["tracker_status"] == "MISSING_WRITE_STATUS"

    view_path = tmp_path / get_o_output_contract("repricer_tracker_view").rel_path
    health_path = tmp_path / get_o_output_contract("repricer_tracker_health").rel_path
    assert view_path.exists()
    assert health_path.exists()
    health = pd.read_csv(health_path, dtype=str).fillna("")
    blank_health = health[health["check"] == "repricer_tracker_blank_execution_write_status"].iloc[0]
    assert blank_health["status"] == "fail"
    assert blank_health["value"] == "1"


def test_o050_marks_old_compact_pricing_output_as_stale_audit_evidence(tmp_path: Path) -> None:
    _write_h_sources(tmp_path)
    pricing_path = tmp_path / "out" / "pricing_output.csv"
    runtime_path = tmp_path / "out" / "phase1_runtime_floor_snapshot_latest.csv"
    os.utime(pricing_path, (1000, 1000))
    os.utime(runtime_path, (2000, 2000))

    build_repricing_tracker_view(root=tmp_path, asof_utc="2026-05-01T15:00:00Z")

    health_path = tmp_path / get_o_output_contract("repricer_tracker_health").rel_path
    health = pd.read_csv(health_path, dtype=str).fillna("")
    freshness = health[health["check"] == "repricer_tracker_pricing_output_freshness"].iloc[0]
    compact_blank = health[health["check"] == "repricer_tracker_pricing_output_blank_execution_write_status"].iloc[0]
    assert freshness["status"] == "warn"
    assert freshness["value"] == "pricing_output_older_than_runtime_and_missing_latest_runtime_run"
    assert compact_blank["status"] == "warn"
    assert compact_blank["value"] == "1"


def test_o050_compares_publish_rows_to_filtered_dashboard_view_not_raw_runtime_rows(tmp_path: Path) -> None:
    _write_h_sources(tmp_path)
    (tmp_path / "out" / "systems" / "H" / "live" / "H_cycle_last_publish_info.txt").write_text(
        "run_id=RUN-LATEST\nutc=2026-05-01T14:20:53Z\nrows=1\nstatus=ok\n",
        encoding="utf-8",
    )
    view_dir = tmp_path / "out" / "analysis_reports"
    view_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"SKU": "SKU-APPLY", "Status": "OK"}]).to_csv(
        view_dir / "phase1_observation_view_2026-05-01.csv",
        index=False,
    )

    build_repricing_tracker_view(root=tmp_path, asof_utc="2026-05-01T15:00:00Z")

    health_path = tmp_path / get_o_output_contract("repricer_tracker_health").rel_path
    health = pd.read_csv(health_path, dtype=str).fillna("")
    raw_runtime = health[health["check"] == "repricer_tracker_terminal_rows_vs_publish_rows"].iloc[0]
    dashboard = health[health["check"] == "repricer_tracker_publish_rows_vs_dashboard_view_rows"].iloc[0]
    assert raw_runtime["status"] == "ok"
    assert raw_runtime["value"] == "2/1"
    assert "raw processed SKUs" in raw_runtime["notes"]
    assert dashboard["status"] == "ok"
    assert dashboard["value"] == "1/1"


def test_o050_filters_and_glance_projection(tmp_path: Path) -> None:
    _write_h_sources(tmp_path)
    out_df = build_repricing_tracker_view(root=tmp_path, asof_utc="2026-05-01T15:00:00Z")

    current_issues = filter_repricing_tracker_view(out_df, current_run_only=True, issues_only=True)
    assert list(current_issues["sku"]) == ["SKU-BLANK"]

    writes = filter_repricing_tracker_view(out_df, current_run_only=True, writes_only=True)
    assert list(writes["sku"]) == ["SKU-APPLY"]

    glance = build_repricing_tracker_glance_df(writes)
    assert list(glance.columns) == [
        "Status",
        "SKU",
        "Old",
        "New",
        "Floor",
        "Ceiling",
        "Eligible",
        "Attempted",
        "Applied",
        "Write Result",
        "Issue",
        "State",
        "Buy Box",
        "Run",
    ]
    assert glance.iloc[0]["Write Result"] == "APPLIED"
