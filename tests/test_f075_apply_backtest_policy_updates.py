from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F070_build_backtest_policy_snapshot import build_backtest_policy_snapshot
from scripts.flows.F.F075_apply_backtest_policy_updates import apply_backtest_policy_updates
from scripts.flows.F._schemas import get_f_output_contract


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_f_output_contract(contract_name)
    out_path = tmp_path / contract.rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = [*contract.required_columns, *contract.optional_columns]
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({col: str(row.get(col, "") or "") for col in cols})
    pd.DataFrame(normalized, columns=cols).to_csv(out_path, index=False)


def _read_policy_df(tmp_path: Path) -> pd.DataFrame:
    in_path = tmp_path / get_f_output_contract("feeder_backtest_policy_live").rel_path
    return pd.read_csv(in_path, dtype=str).fillna("")


def test_f075_valid_event_updates_live_policy(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_contract_rows(
        tmp_path,
        "feeder_backtest_policy_update_events",
        [
            {
                "event_utc": "2026-04-10T10:05:00Z",
                "event_id": "evt-001",
                "policy_id": "f_backtest_policy_v1",
                "action": "apply",
                "minimum_expected_profit_gbp": "150",
                "entry_target_roi_pct": "25",
                "working_floor_roi_pct": "15",
                "exit_floor_roi_pct": "5",
                "emergency_floor_roi_pct": "0",
                "actor": "operator_ui",
                "source_reference": "unit_test",
                "decision_note": "raise target profitability",
            }
        ],
    )

    out_df = apply_backtest_policy_updates(root=tmp_path, observed_utc="2026-04-10T10:10:00Z")
    assert len(out_df.index) == 1
    row = out_df.iloc[0]
    assert row["observed_utc"] == "2026-04-10T10:10:00Z"
    assert row["minimum_expected_profit_gbp"] == "150"
    assert row["entry_target_roi_pct"] == "25"
    assert row["working_floor_roi_pct"] == "15"
    assert row["exit_floor_roi_pct"] == "5"
    assert row["emergency_floor_roi_pct"] == "0"
    assert row["policy_status"] == "active"
    assert row["policy_source"] == "policy_update_event:evt-001|source:unit_test"
    assert "raise target profitability" in row["notes"]


def test_f075_invalid_ordering_is_rejected_and_live_policy_stays_unchanged(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    before = _read_policy_df(tmp_path).iloc[0].to_dict()
    _write_contract_rows(
        tmp_path,
        "feeder_backtest_policy_update_events",
        [
            {
                "event_utc": "2026-04-10T10:05:00Z",
                "event_id": "evt-invalid-order",
                "policy_id": "f_backtest_policy_v1",
                "action": "apply",
                "minimum_expected_profit_gbp": "100",
                "entry_target_roi_pct": "10",
                "working_floor_roi_pct": "20",
                "exit_floor_roi_pct": "5",
                "emergency_floor_roi_pct": "0",
                "actor": "operator_ui",
                "source_reference": "unit_test",
                "decision_note": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="no valid policy update events found"):
        apply_backtest_policy_updates(root=tmp_path, observed_utc="2026-04-10T10:10:00Z")

    after = _read_policy_df(tmp_path).iloc[0].to_dict()
    assert after == before


def test_f075_missing_values_are_rejected_and_live_policy_stays_unchanged(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    before = _read_policy_df(tmp_path).iloc[0].to_dict()
    _write_contract_rows(
        tmp_path,
        "feeder_backtest_policy_update_events",
        [
            {
                "event_utc": "2026-04-10T10:05:00Z",
                "event_id": "evt-missing-values",
                "policy_id": "f_backtest_policy_v1",
                "action": "apply",
                "minimum_expected_profit_gbp": "",
                "entry_target_roi_pct": "20",
                "working_floor_roi_pct": "10",
                "exit_floor_roi_pct": "0",
                "emergency_floor_roi_pct": "-5",
                "actor": "operator_ui",
                "source_reference": "unit_test",
                "decision_note": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="no valid policy update events found"):
        apply_backtest_policy_updates(root=tmp_path, observed_utc="2026-04-10T10:10:00Z")

    after = _read_policy_df(tmp_path).iloc[0].to_dict()
    assert after == before


def test_f075_latest_valid_event_wins_and_policy_stays_single_row(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    _write_contract_rows(
        tmp_path,
        "feeder_backtest_policy_update_events",
        [
            {
                "event_utc": "2026-04-10T10:05:00Z",
                "event_id": "evt-older-valid",
                "policy_id": "f_backtest_policy_v1",
                "action": "apply",
                "minimum_expected_profit_gbp": "110",
                "entry_target_roi_pct": "21",
                "working_floor_roi_pct": "11",
                "exit_floor_roi_pct": "1",
                "emergency_floor_roi_pct": "-4",
                "actor": "operator_ui",
                "source_reference": "unit_test",
                "decision_note": "",
            },
            {
                "event_utc": "2026-04-10T10:06:00Z",
                "event_id": "evt-latest-valid",
                "policy_id": "f_backtest_policy_v1",
                "action": "apply",
                "minimum_expected_profit_gbp": "120",
                "entry_target_roi_pct": "22",
                "working_floor_roi_pct": "12",
                "exit_floor_roi_pct": "2",
                "emergency_floor_roi_pct": "-3",
                "actor": "operator_ui",
                "source_reference": "unit_test",
                "decision_note": "",
            },
            {
                "event_utc": "2026-04-10T10:07:00Z",
                "event_id": "evt-newest-invalid",
                "policy_id": "f_backtest_policy_v1",
                "action": "apply",
                "minimum_expected_profit_gbp": "",
                "entry_target_roi_pct": "22",
                "working_floor_roi_pct": "12",
                "exit_floor_roi_pct": "2",
                "emergency_floor_roi_pct": "-3",
                "actor": "operator_ui",
                "source_reference": "unit_test",
                "decision_note": "",
            },
        ],
    )

    out_df = apply_backtest_policy_updates(root=tmp_path, observed_utc="2026-04-10T10:10:00Z")
    assert len(out_df.index) == 1
    row = out_df.iloc[0]
    assert row["minimum_expected_profit_gbp"] == "120"
    assert row["entry_target_roi_pct"] == "22"
    assert row["working_floor_roi_pct"] == "12"
    assert row["exit_floor_roi_pct"] == "2"
    assert row["emergency_floor_roi_pct"] == "-3"

    disk_df = _read_policy_df(tmp_path)
    assert len(disk_df.index) == 1
    assert int((disk_df["policy_status"].str.lower() == "active").sum()) == 1


def test_f075_no_events_is_safe_no_change(tmp_path: Path) -> None:
    build_backtest_policy_snapshot(root=tmp_path, observed_utc="2026-04-10T10:00:00Z")
    before = _read_policy_df(tmp_path).iloc[0].to_dict()

    out_df = apply_backtest_policy_updates(root=tmp_path, observed_utc="2026-04-10T10:20:00Z")
    assert len(out_df.index) == 1

    after = _read_policy_df(tmp_path).iloc[0].to_dict()
    assert after == before
