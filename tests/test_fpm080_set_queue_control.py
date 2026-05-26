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

from scripts.flows.F.price_list_manager.FPM080_set_queue_control import set_queue_control
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, QUEUE_CONTROL_COLUMNS


def test_fpm080_sets_and_clears_test_mode_queue_control(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"

    summary = set_queue_control(
        supplier_id="heo",
        control_state="prioritised",
        priority_rank="2",
        reason="operator test",
        root=tmp_path,
        updated_at_utc="2026-04-30T12:00:00Z",
    )

    controls = pd.read_csv(test_dir / "queue_controls.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")
    assert summary["status"] == "success"
    assert summary["control_rows"] == 1
    assert list(controls.columns) == QUEUE_CONTROL_COLUMNS
    assert list(health.columns) == MANAGER_HEALTH_COLUMNS
    assert controls.iloc[0]["supplier_id"] == "heo"
    assert controls.iloc[0]["control_state"] == "prioritised"
    assert controls.iloc[0]["priority_rank"] == "2"

    clear_summary = set_queue_control(
        supplier_id="heo",
        control_state="normal",
        root=tmp_path,
        updated_at_utc="2026-04-30T12:05:00Z",
    )

    cleared = pd.read_csv(test_dir / "queue_controls.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")
    assert clear_summary["control_rows"] == 0
    assert cleared.empty
    assert health.iloc[-1]["notes"] == "control_state=normal;priority_rank="
