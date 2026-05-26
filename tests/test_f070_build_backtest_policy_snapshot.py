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

from scripts.flows.F.F070_build_backtest_policy_snapshot import build_backtest_policy_snapshot
from scripts.flows.F._schemas import get_f_output_contract


def test_f070_builds_single_active_policy_row_with_v1_defaults(tmp_path: Path) -> None:
    out_df = build_backtest_policy_snapshot(
        root=tmp_path,
        observed_utc="2026-04-10T10:00:00Z",
    )
    assert len(out_df) == 1
    row = out_df.iloc[0]
    assert row["observed_utc"] == "2026-04-10T10:00:00Z"
    assert row["policy_id"] == "f_backtest_policy_v1"
    assert row["policy_status"] == "active"
    assert row["minimum_expected_profit_gbp"] == "20"
    assert row["entry_target_roi_pct"] == "20"
    assert row["working_floor_roi_pct"] == "10"
    assert row["exit_floor_roi_pct"] == "0"
    assert row["emergency_floor_roi_pct"] == "-5"
    assert row["recency_weight_30d"] == "0.5"
    assert row["recency_weight_90d"] == "0.3"
    assert row["recency_weight_180d"] == "0.15"
    assert row["recency_weight_365d"] == "0.05"
    assert row["ceiling_warn_ratio_30d"] == "1.25"
    assert row["ceiling_red_ratio_30d"] == "1.5"
    assert row["ceiling_extreme_ratio_30d"] == "2"
    assert row["shock_trigger_pct_1d"] == "20"
    assert row["shared_sales_default_pct"] == "50"

    out_path = tmp_path / get_f_output_contract("feeder_backtest_policy_live").rel_path
    assert out_path.exists()
    disk_df = pd.read_csv(out_path, dtype=str).fillna("")
    assert len(disk_df) == 1
    assert disk_df.iloc[0]["policy_id"] == "f_backtest_policy_v1"


def test_f070_applies_editable_control_overrides(tmp_path: Path) -> None:
    out_df = build_backtest_policy_snapshot(
        root=tmp_path,
        observed_utc="2026-04-10T11:00:00Z",
        policy_id="f_backtest_policy_custom",
        policy_version="1.1",
        minimum_expected_profit_gbp=175.0,
        entry_target_roi_pct=22.0,
        working_floor_roi_pct=12.0,
        exit_floor_roi_pct=2.0,
        emergency_floor_roi_pct=-3.5,
        policy_source="manual_operator_override",
        notes="custom test profile",
    )
    row = out_df.iloc[0]
    assert row["policy_id"] == "f_backtest_policy_custom"
    assert row["policy_version"] == "1.1"
    assert row["minimum_expected_profit_gbp"] == "175"
    assert row["entry_target_roi_pct"] == "22"
    assert row["working_floor_roi_pct"] == "12"
    assert row["exit_floor_roi_pct"] == "2"
    assert row["emergency_floor_roi_pct"] == "-3.5"
    assert row["policy_source"] == "manual_operator_override"
    assert row["notes"] == "custom test profile"
