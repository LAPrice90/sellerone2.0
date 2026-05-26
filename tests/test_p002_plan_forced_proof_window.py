import os
import tempfile
import unittest
from pathlib import Path

from scripts.one_off import P002_plan_forced_proof_window as p002


class ForcedProofWindowPlannerTests(unittest.TestCase):
    def test_a_plan_forbids_a015_alone(self) -> None:
        plan = p002.build_plan("a")
        self.assertEqual(plan["proof_mode"], "owned_a_cycle")
        self.assertFalse(plan["wait_for_next_scheduled_cycle_allowed"])
        self.assertTrue(
            any("A015_build_system_health_check.py alone" in item for item in plan["disallowed_shortcuts"])
        )

    def test_b_plan_uses_run_once_and_forbids_mid_cycle_checks(self) -> None:
        plan = p002.build_plan("b")
        self.assertEqual(plan["proof_mode"], "boundary_safe_b_run_once")
        self.assertTrue(any("B_RUN_ONCE" in item for item in plan["command_sequence"]))
        self.assertTrue(any("middle of the B loop" in item for item in plan["disallowed_shortcuts"]))

    def test_e_plan_uses_owned_cycle(self) -> None:
        plan = p002.build_plan("e")
        self.assertEqual(plan["proof_mode"], "owned_e_cycle")
        self.assertEqual(plan["command_sequence"], ["python scripts/cycles/run_E_cycle.py"])

    def test_h_plan_uses_controlled_isolation_and_h_profile(self) -> None:
        plan = p002.build_plan("h")
        self.assertEqual(plan["proof_mode"], "controlled_h_isolation")
        self.assertTrue(any("run_H_isolation_pause.bat" in item for item in plan["command_sequence"]))
        self.assertTrue(any("--profile h --no-toast" in item for item in plan["command_sequence"]))

    def test_b_active_lock_requires_boundary_not_next_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            live = root / "out" / "systems" / "B" / "live"
            live.mkdir(parents=True, exist_ok=True)
            lock_path = live / "B_cycle.lock"
            lock_path.write_text(
                f"B|pid={os.getpid()}|run_id=B_RUN_1|heartbeat=2026-04-17T10:00:00Z\n",
                encoding="utf-8",
            )

            plan = p002.build_plan("b", root=root)

        self.assertEqual(plan["proof_window_status"], "boundary_or_pause_required")
        self.assertTrue(plan["can_proceed_without_next_cycle"])
        self.assertFalse(plan["wait_for_next_scheduled_cycle_allowed"])

    def test_b_plan_uses_scoped_marker_when_cross_flow_owners_are_active(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            b_live = root / "out" / "systems" / "B" / "live"
            h_live = root / "out" / "systems" / "H" / "live"
            f_live = root / "out" / "systems" / "F" / "price_list_manager" / "live"
            b_live.mkdir(parents=True, exist_ok=True)
            h_live.mkdir(parents=True, exist_ok=True)
            f_live.mkdir(parents=True, exist_ok=True)
            (b_live / "B_cycle.lock").write_text(f"B|pid={os.getpid()}|heartbeat=2026-05-18T12:00:00Z\n", encoding="utf-8")
            (h_live / "H_cycle.lock").write_text(f"H|pid={os.getpid()}|heartbeat=2026-05-18T12:00:00Z\n", encoding="utf-8")
            (f_live / "live_cycle.lock").write_text(f"pid={os.getpid()}|heartbeat=2026-05-18T12:00:00Z|owner=FPM130_live_cycle\n", encoding="utf-8")

            plan = p002.build_plan("b", root=root)

        self.assertIn("global maintenance.requested", plan["state_reason"])
        self.assertTrue(any("b_cycle.maintenance" in item for item in plan["command_sequence"]))
        self.assertTrue(any("global maintenance.requested" in item for item in plan["disallowed_shortcuts"]))

    def test_h_controlled_mode_marks_ready_now(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            locks = root / "out" / "locks"
            locks.mkdir(parents=True, exist_ok=True)
            (locks / "h_controlled_mode.active").write_text("controlled_mode=1\n", encoding="utf-8")

            plan = p002.build_plan("h", root=root)

        self.assertEqual(plan["proof_window_status"], "ready_now")
        self.assertTrue(plan["can_proceed_without_next_cycle"])


if __name__ == "__main__":
    unittest.main()
