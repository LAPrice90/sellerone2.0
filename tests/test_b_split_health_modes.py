import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts import run_B_cycle as b_cycle


class BSplitHealthModeTests(unittest.TestCase):
    def test_shadow_state_and_auto_cutover_for_b(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_state_path = b_cycle.SPLIT_SHADOW_STATE_PATH
            old_log_path = b_cycle.LOG_PATH
            old_mode = b_cycle.B_SPLIT_HEALTH_MODE
            try:
                b_cycle.SPLIT_SHADOW_STATE_PATH = root / "split_shadow_state.json"
                b_cycle.LOG_PATH = root / "B_cycle.log"
                b_cycle.B_SPLIT_HEALTH_MODE = "shadow"

                state = {
                    "a_match_streak": 10,
                    "b_match_streak": 9,
                    "e_match_streak": 10,
                    "ready_for_cutover": False,
                    "updated_utc": "2026-02-18T00:00:00Z",
                }
                b_cycle._write_split_shadow_state(state)
                updated = b_cycle._update_b_shadow_streak(True)
                self.assertEqual(int(updated.get("a_match_streak", 0)), 10)
                self.assertEqual(int(updated.get("b_match_streak", 0)), 10)
                self.assertEqual(int(updated.get("e_match_streak", 0)), 10)
                self.assertTrue(bool(updated.get("ready_for_cutover", False)))
                self.assertEqual(b_cycle._effective_b_split_mode(), "split")

                updated = b_cycle._update_b_shadow_streak(False)
                self.assertEqual(int(updated.get("b_match_streak", 0)), 0)
                self.assertFalse(bool(updated.get("ready_for_cutover", False)))
            finally:
                b_cycle.SPLIT_SHADOW_STATE_PATH = old_state_path
                b_cycle.LOG_PATH = old_log_path
                b_cycle.B_SPLIT_HEALTH_MODE = old_mode

    def test_append_split_shadow_compare_writes_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_compare_path = b_cycle.SPLIT_SHADOW_COMPARE_PATH
            try:
                b_cycle.SPLIT_SHADOW_COMPARE_PATH = root / "split_shadow_compare.csv"
                b_cycle._append_split_shadow_compare(
                    {
                        "timestamp_utc": "2026-02-18T10:00:00Z",
                        "cycle_start_utc": "2026-02-18T10:00:00Z",
                        "cycle": "B",
                        "mode_requested": "shadow",
                        "mode_effective": "shadow",
                        "legacy_fail_count": "0",
                        "legacy_warn_count": "1",
                        "legacy_gate_block": "0",
                        "split_fail_count": "0",
                        "split_warn_count": "1",
                        "split_gate_block": "0",
                        "decision_match": "1",
                        "a_match_streak": "8",
                        "b_match_streak": "4",
                        "e_match_streak": "3",
                        "ready_for_cutover": "0",
                        "legacy_source": "checklist_B.csv",
                        "split_source": "checklist_B_split.csv",
                        "notes": "ok",
                    }
                )
                df = pd.read_csv(b_cycle.SPLIT_SHADOW_COMPARE_PATH, dtype=str).fillna("")
                self.assertEqual(len(df.index), 1)
                self.assertEqual(df.loc[0, "cycle"], "B")
                self.assertEqual(df.loc[0, "decision_match"], "1")
                self.assertEqual(df.loc[0, "split_source"], "checklist_B_split.csv")
            finally:
                b_cycle.SPLIT_SHADOW_COMPARE_PATH = old_compare_path


if __name__ == "__main__":
    unittest.main()
