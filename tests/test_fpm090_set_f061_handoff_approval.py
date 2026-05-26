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

from scripts.flows.F.price_list_manager.FPM090_set_f061_handoff_approval import set_f061_handoff_approval
from scripts.flows.F.price_list_manager._schemas import F061_HANDOFF_APPROVAL_COLUMNS, MANAGER_HEALTH_COLUMNS


def test_fpm090_records_test_mode_handoff_approval(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"

    summary = set_f061_handoff_approval(
        supplier_id="stax",
        batch_id="stax_batch",
        approval_state="approved",
        approved_by="operator",
        reason="scanner idle proof",
        root=tmp_path,
        approved_at_utc="2026-04-30T13:30:00Z",
    )

    approvals = pd.read_csv(test_dir / "f061_handoff_approvals.csv", dtype=str).fillna("")
    health = pd.read_csv(test_dir / "health.csv", dtype=str).fillna("")
    assert summary["status"] == "success"
    assert summary["approval_state"] == "approved"
    assert list(approvals.columns) == F061_HANDOFF_APPROVAL_COLUMNS
    assert list(health.columns) == MANAGER_HEALTH_COLUMNS
    assert approvals.iloc[0]["approval_id"] == summary["approval_id"]
    assert approvals.iloc[0]["supplier_id"] == "stax"
    assert approvals.iloc[0]["batch_id"] == "stax_batch"
    assert approvals.iloc[0]["approved_by"] == "operator"
    assert health.iloc[-1]["check"] == "f061_handoff_approval_recorded"
