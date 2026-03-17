import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts import run_H_pricing_cycle as h_cycle


class HSplitHealthGateTests(unittest.TestCase):
    def test_split_mode_fail_closed_blocks_when_snapshot_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_fail_closed = h_cycle.H_HEALTH_FAIL_CLOSED
            old_checklist = h_cycle.H_SPLIT_CHECKLIST_PATH
            old_state_path = h_cycle.SPLIT_SHADOW_STATE_PATH
            old_compare_path = h_cycle.SPLIT_SHADOW_COMPARE_PATH
            try:
                h_cycle.H_HEALTH_FAIL_CLOSED = True
                h_cycle.H_SPLIT_CHECKLIST_PATH = root / "checklist_H_split.csv"
                h_cycle.SPLIT_SHADOW_STATE_PATH = root / "split_shadow_state.json"
                h_cycle.SPLIT_SHADOW_COMPARE_PATH = root / "split_shadow_compare.csv"
                payload = h_cycle._resolve_h_split_gate(
                    now_utc=h_cycle._utc_now(),
                    run_id="20260218T100000Z",
                    mode_requested="split",
                    mode_effective="split",
                    state={"h_gate_health_run_utc": "2999-01-01T00:00:00Z"},
                )
                self.assertEqual(payload.get("h_gate_block_live_writes"), "1")
                self.assertEqual(payload.get("h_gate_fail_count"), "")
                self.assertEqual(payload.get("h_gate_warn_count"), "")
            finally:
                h_cycle.H_HEALTH_FAIL_CLOSED = old_fail_closed
                h_cycle.H_SPLIT_CHECKLIST_PATH = old_checklist
                h_cycle.SPLIT_SHADOW_STATE_PATH = old_state_path
                h_cycle.SPLIT_SHADOW_COMPARE_PATH = old_compare_path

    def test_shadow_mode_never_blocks_live_writes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_checklist = h_cycle.H_SPLIT_CHECKLIST_PATH
            old_state_path = h_cycle.SPLIT_SHADOW_STATE_PATH
            old_compare_path = h_cycle.SPLIT_SHADOW_COMPARE_PATH
            try:
                h_cycle.H_SPLIT_CHECKLIST_PATH = root / "checklist_H_split.csv"
                h_cycle.SPLIT_SHADOW_STATE_PATH = root / "split_shadow_state.json"
                h_cycle.SPLIT_SHADOW_COMPARE_PATH = root / "split_shadow_compare.csv"
                h_cycle.H_SPLIT_CHECKLIST_PATH.write_text(
                    "check,status,value,notes\nh_check_a,fail,1,x\nh_check_b,warn,1,y\n",
                    encoding="utf-8",
                )
                payload = h_cycle._resolve_h_split_gate(
                    now_utc=h_cycle._utc_now(),
                    run_id="20260218T110000Z",
                    mode_requested="shadow",
                    mode_effective="shadow",
                    state={"h_gate_health_run_utc": "2999-01-01T00:00:00Z"},
                )
                self.assertEqual(payload.get("h_gate_fail_count"), "1")
                self.assertEqual(payload.get("h_gate_warn_count"), "1")
                self.assertEqual(payload.get("h_gate_block_live_writes"), "0")
            finally:
                h_cycle.H_SPLIT_CHECKLIST_PATH = old_checklist
                h_cycle.SPLIT_SHADOW_STATE_PATH = old_state_path
                h_cycle.SPLIT_SHADOW_COMPARE_PATH = old_compare_path

    def test_effective_mode_auto_cutover_when_ready(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_mode = h_cycle.H_SPLIT_HEALTH_MODE
            old_state_path = h_cycle.SPLIT_SHADOW_STATE_PATH
            try:
                h_cycle.H_SPLIT_HEALTH_MODE = "shadow"
                h_cycle.SPLIT_SHADOW_STATE_PATH = root / "split_shadow_state.json"
                h_cycle.SPLIT_SHADOW_STATE_PATH.write_text(
                    '{"b_match_streak":10,"h_clean_streak":10,"ready_for_cutover":true,"updated_utc":"2026-02-18T11:00:00Z"}',
                    encoding="utf-8",
                )
                self.assertEqual(h_cycle._effective_h_split_mode(), "split")
            finally:
                h_cycle.H_SPLIT_HEALTH_MODE = old_mode
                h_cycle.SPLIT_SHADOW_STATE_PATH = old_state_path


if __name__ == "__main__":
    unittest.main()

