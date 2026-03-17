import os
import tempfile
import unittest
from pathlib import Path

from scripts import run_E_cycle as e_cycle


class ESplitHealthGateTests(unittest.TestCase):
    def test_split_mode_fail_closed_blocks_publish(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_run_log = e_cycle.E_RUN_LOG
            old_decision_log = e_cycle.E_DECISION_LOG
            old_split_checklist = e_cycle.E_SPLIT_CHECKLIST_PATH
            old_mode = e_cycle.E_SPLIT_HEALTH_MODE
            old_fail_closed = e_cycle.E_HEALTH_FAIL_CLOSED
            old_tasks = list(e_cycle.TASKS)
            old_run = e_cycle._run
            old_profile_runner = e_cycle._run_a015_profile_e
            old_compare = e_cycle.FLOW_SELFTEST_COMPARE_PATH
            old_state = e_cycle.FLOW_SELFTEST_STATE_PATH
            old_enforce = os.environ.get("E_ENFORCE_CADENCE")
            old_write = os.environ.get("E_WRITE_SHEETS")
            try:
                e_cycle.E_RUN_LOG = root / "e_run_log.jsonl"
                e_cycle.E_DECISION_LOG = root / "e_decision_log.csv"
                e_cycle.E_SPLIT_CHECKLIST_PATH = root / "checklist_E_split.csv"
                e_cycle.FLOW_SELFTEST_COMPARE_PATH = root / "flow_selftest_compare.csv"
                e_cycle.FLOW_SELFTEST_STATE_PATH = root / "flow_selftest_state.json"
                e_cycle.E_SPLIT_HEALTH_MODE = "split"
                e_cycle.E_HEALTH_FAIL_CLOSED = True
                e_cycle.TASKS = []
                e_cycle._run = lambda _label, _script: 0.0
                e_cycle._run_a015_profile_e = lambda: (2, False)
                os.environ["E_ENFORCE_CADENCE"] = "0"
                os.environ["E_WRITE_SHEETS"] = "1"

                e_cycle.main()
                rows = [ln.strip() for ln in e_cycle.E_RUN_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
                self.assertTrue(rows)
                self.assertIn('"status": "gated_fail"', rows[-1])
            finally:
                e_cycle.E_RUN_LOG = old_run_log
                e_cycle.E_DECISION_LOG = old_decision_log
                e_cycle.E_SPLIT_CHECKLIST_PATH = old_split_checklist
                e_cycle.E_SPLIT_HEALTH_MODE = old_mode
                e_cycle.E_HEALTH_FAIL_CLOSED = old_fail_closed
                e_cycle.TASKS = old_tasks
                e_cycle._run = old_run
                e_cycle._run_a015_profile_e = old_profile_runner
                e_cycle.FLOW_SELFTEST_COMPARE_PATH = old_compare
                e_cycle.FLOW_SELFTEST_STATE_PATH = old_state
                if old_enforce is None:
                    os.environ.pop("E_ENFORCE_CADENCE", None)
                else:
                    os.environ["E_ENFORCE_CADENCE"] = old_enforce
                if old_write is None:
                    os.environ.pop("E_WRITE_SHEETS", None)
                else:
                    os.environ["E_WRITE_SHEETS"] = old_write

    def test_shadow_mode_logs_compare_and_allows_publish(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_run_log = e_cycle.E_RUN_LOG
            old_decision_log = e_cycle.E_DECISION_LOG
            old_split_checklist = e_cycle.E_SPLIT_CHECKLIST_PATH
            old_mode = e_cycle.E_SPLIT_HEALTH_MODE
            old_tasks = list(e_cycle.TASKS)
            old_run = e_cycle._run
            old_profile_runner = e_cycle._run_a015_profile_e
            old_compare = e_cycle.FLOW_SELFTEST_COMPARE_PATH
            old_state = e_cycle.FLOW_SELFTEST_STATE_PATH
            old_enforce = os.environ.get("E_ENFORCE_CADENCE")
            old_write = os.environ.get("E_WRITE_SHEETS")
            publish_calls: list[str] = []
            try:
                e_cycle.E_RUN_LOG = root / "e_run_log.jsonl"
                e_cycle.E_DECISION_LOG = root / "e_decision_log.csv"
                e_cycle.E_SPLIT_CHECKLIST_PATH = root / "checklist_E_split.csv"
                e_cycle.FLOW_SELFTEST_COMPARE_PATH = root / "flow_selftest_compare.csv"
                e_cycle.FLOW_SELFTEST_STATE_PATH = root / "flow_selftest_state.json"
                e_cycle._write_flow_selftest_state(
                    {
                        "a_match_streak": 0,
                        "b_match_streak": 0,
                        "e_match_streak": 0,
                        "ready_for_cutover": False,
                        "updated_utc": "2026-02-18T00:00:00Z",
                    }
                )
                e_cycle.E_SPLIT_HEALTH_MODE = "shadow"
                e_cycle.TASKS = []

                def _fake_run(label: str, _script: Path) -> float:
                    publish_calls.append(label)
                    return 0.0

                e_cycle._run = _fake_run
                e_cycle._run_a015_profile_e = lambda: (2, True)
                os.environ["E_ENFORCE_CADENCE"] = "0"
                os.environ["E_WRITE_SHEETS"] = "1"

                e_cycle.main()
                rows = [ln.strip() for ln in e_cycle.E_RUN_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
                self.assertTrue(rows)
                self.assertIn('"status": "success"', rows[-1])
                self.assertIn("E010_publish_e_outputs.py", publish_calls)
                self.assertTrue(e_cycle.FLOW_SELFTEST_COMPARE_PATH.exists())
            finally:
                e_cycle.E_RUN_LOG = old_run_log
                e_cycle.E_DECISION_LOG = old_decision_log
                e_cycle.E_SPLIT_CHECKLIST_PATH = old_split_checklist
                e_cycle.E_SPLIT_HEALTH_MODE = old_mode
                e_cycle.TASKS = old_tasks
                e_cycle._run = old_run
                e_cycle._run_a015_profile_e = old_profile_runner
                e_cycle.FLOW_SELFTEST_COMPARE_PATH = old_compare
                e_cycle.FLOW_SELFTEST_STATE_PATH = old_state
                if old_enforce is None:
                    os.environ.pop("E_ENFORCE_CADENCE", None)
                else:
                    os.environ["E_ENFORCE_CADENCE"] = old_enforce
                if old_write is None:
                    os.environ.pop("E_WRITE_SHEETS", None)
                else:
                    os.environ["E_WRITE_SHEETS"] = old_write


if __name__ == "__main__":
    unittest.main()

