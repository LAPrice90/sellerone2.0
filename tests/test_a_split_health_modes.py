import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts import run_A_all as a_cycle


class ASplitHealthModeTests(unittest.TestCase):
    def test_shadow_state_and_auto_cutover_for_a(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_state_path = a_cycle.FLOW_SELFTEST_STATE_PATH
            old_mode = a_cycle.A_SPLIT_HEALTH_MODE
            try:
                a_cycle.FLOW_SELFTEST_STATE_PATH = root / "flow_selftest_state.json"
                a_cycle.A_SPLIT_HEALTH_MODE = "shadow"
                a_cycle._write_flow_selftest_state(
                    {
                        "a_match_streak": 9,
                        "b_match_streak": 10,
                        "e_match_streak": 10,
                        "ready_for_cutover": False,
                        "updated_utc": "2026-02-18T00:00:00Z",
                    }
                )
                updated = a_cycle._update_a_shadow_streak(True)
                self.assertEqual(int(updated.get("a_match_streak", 0)), 10)
                self.assertEqual(int(updated.get("b_match_streak", 0)), 10)
                self.assertEqual(int(updated.get("e_match_streak", 0)), 10)
                self.assertTrue(bool(updated.get("ready_for_cutover", False)))
                self.assertEqual(a_cycle._effective_a_split_mode(), "split")
            finally:
                a_cycle.FLOW_SELFTEST_STATE_PATH = old_state_path
                a_cycle.A_SPLIT_HEALTH_MODE = old_mode

    def test_append_flow_selftest_compare_writes_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_compare = a_cycle.FLOW_SELFTEST_COMPARE_PATH
            try:
                a_cycle.FLOW_SELFTEST_COMPARE_PATH = root / "flow_selftest_compare.csv"
                a_cycle._append_flow_selftest_compare(
                    {
                        "timestamp_utc": "2026-02-18T10:00:00Z",
                        "cycle_start_utc": "20260218T100000Z",
                        "cycle": "A",
                        "mode_requested": "shadow",
                        "mode_effective": "shadow",
                        "legacy_fail_count": "0",
                        "legacy_warn_count": "1",
                        "legacy_gate_block": "0",
                        "split_fail_count": "0",
                        "split_warn_count": "0",
                        "split_gate_block": "0",
                        "decision_match": "1",
                        "a_match_streak": "7",
                        "b_match_streak": "8",
                        "e_match_streak": "9",
                        "ready_for_cutover": "0",
                        "legacy_source": "system_health_checklist.csv",
                        "split_source": "checklist_A_split.csv",
                        "notes": "ok",
                    }
                )
                df = pd.read_csv(a_cycle.FLOW_SELFTEST_COMPARE_PATH, dtype=str).fillna("")
                self.assertEqual(len(df.index), 1)
                self.assertEqual(df.loc[0, "cycle"], "A")
                self.assertEqual(df.loc[0, "split_source"], "checklist_A_split.csv")
            finally:
                a_cycle.FLOW_SELFTEST_COMPARE_PATH = old_compare


if __name__ == "__main__":
    unittest.main()

