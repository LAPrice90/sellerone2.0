import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.cycles import run_A_all as a_cycle


class AMaintenanceHandoffTests(unittest.TestCase):
    def test_b_cycle_running_treats_live_pid_with_fresh_heartbeat_as_running(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock_path = root / "B_cycle.lock"
            old_live_path = a_cycle.B_CYCLE_LOCK_PATH
            old_legacy_path = a_cycle.B_LEGACY_CYCLE_LOCK_PATH
            try:
                a_cycle.B_CYCLE_LOCK_PATH = lock_path
                a_cycle.B_LEGACY_CYCLE_LOCK_PATH = root / "B_cycle_legacy.lock"
                now_utc = a_cycle.datetime.now(a_cycle.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                lock_path.write_text(
                    f"B|pid={a_cycle.os.getpid()}|start={now_utc}|heartbeat={now_utc}\n",
                    encoding="utf-8",
                )
                self.assertTrue(a_cycle._b_cycle_running())
            finally:
                a_cycle.B_CYCLE_LOCK_PATH = old_live_path
                a_cycle.B_LEGACY_CYCLE_LOCK_PATH = old_legacy_path

    def test_wait_for_ready_returns_timeout_b_running_when_b_still_running(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock_path = root / "B_cycle.lock"
            ready_path = root / "maintenance.ready"
            old_live_path = a_cycle.B_CYCLE_LOCK_PATH
            old_legacy_path = a_cycle.B_LEGACY_CYCLE_LOCK_PATH
            old_ready_path = a_cycle.MAINTENANCE_READY_PATH
            old_timeout = a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS
            old_poll = a_cycle.MAINTENANCE_READY_POLL_SECONDS
            old_log_every = a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS
            old_stable = a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS
            try:
                a_cycle.B_CYCLE_LOCK_PATH = lock_path
                a_cycle.B_LEGACY_CYCLE_LOCK_PATH = root / "B_cycle_legacy.lock"
                a_cycle.MAINTENANCE_READY_PATH = ready_path
                a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS = 0
                a_cycle.MAINTENANCE_READY_POLL_SECONDS = 1.0
                a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS = 9999.0
                a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS = 0.0
                now_utc = a_cycle.datetime.now(a_cycle.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                lock_path.write_text(
                    f"B|pid={a_cycle.os.getpid()}|start={now_utc}|heartbeat={now_utc}\n",
                    encoding="utf-8",
                )
                self.assertEqual(a_cycle._wait_for_b_maintenance_ready("REQ_1"), "timeout_b_running")
            finally:
                a_cycle.B_CYCLE_LOCK_PATH = old_live_path
                a_cycle.B_LEGACY_CYCLE_LOCK_PATH = old_legacy_path
                a_cycle.MAINTENANCE_READY_PATH = old_ready_path
                a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS = old_timeout
                a_cycle.MAINTENANCE_READY_POLL_SECONDS = old_poll
                a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS = old_log_every
                a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS = old_stable

    def test_wait_for_ready_returns_b_not_running_when_no_live_lock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_live_path = a_cycle.B_CYCLE_LOCK_PATH
            old_legacy_path = a_cycle.B_LEGACY_CYCLE_LOCK_PATH
            old_ready_path = a_cycle.MAINTENANCE_READY_PATH
            old_timeout = a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS
            old_poll = a_cycle.MAINTENANCE_READY_POLL_SECONDS
            old_log_every = a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS
            old_stable = a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS
            try:
                a_cycle.B_CYCLE_LOCK_PATH = root / "B_cycle.lock"
                a_cycle.B_LEGACY_CYCLE_LOCK_PATH = root / "B_cycle_legacy.lock"
                a_cycle.MAINTENANCE_READY_PATH = root / "maintenance.ready"
                a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS = 0
                a_cycle.MAINTENANCE_READY_POLL_SECONDS = 1.0
                a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS = 9999.0
                a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS = 0.0
                self.assertEqual(a_cycle._wait_for_b_maintenance_ready("REQ_2"), "b_not_running")
            finally:
                a_cycle.B_CYCLE_LOCK_PATH = old_live_path
                a_cycle.B_LEGACY_CYCLE_LOCK_PATH = old_legacy_path
                a_cycle.MAINTENANCE_READY_PATH = old_ready_path
                a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS = old_timeout
                a_cycle.MAINTENANCE_READY_POLL_SECONDS = old_poll
                a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS = old_log_every
                a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS = old_stable

    def test_wait_for_ready_requires_matching_request_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ready_path = root / "maintenance.ready"
            old_ready_path = a_cycle.MAINTENANCE_READY_PATH
            old_live_path = a_cycle.B_CYCLE_LOCK_PATH
            old_legacy_path = a_cycle.B_LEGACY_CYCLE_LOCK_PATH
            old_timeout = a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS
            old_poll = a_cycle.MAINTENANCE_READY_POLL_SECONDS
            old_log_every = a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS
            old_stable = a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS
            try:
                a_cycle.MAINTENANCE_READY_PATH = ready_path
                a_cycle.B_CYCLE_LOCK_PATH = root / "B_cycle.lock"
                a_cycle.B_LEGACY_CYCLE_LOCK_PATH = root / "B_cycle_legacy.lock"
                a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS = 0
                a_cycle.MAINTENANCE_READY_POLL_SECONDS = 1.0
                a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS = 9999.0
                a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS = 0.0
                ready_path.write_text(
                    "B_READY|pid=123|ts=2026-03-30T20:00:00Z|context=after cycle end|request_id=OTHER_REQ\n",
                    encoding="utf-8",
                )
                self.assertEqual(a_cycle._wait_for_b_maintenance_ready("REQ_EXPECTED"), "b_not_running")
                self.assertFalse(ready_path.exists())
            finally:
                a_cycle.MAINTENANCE_READY_PATH = old_ready_path
                a_cycle.B_CYCLE_LOCK_PATH = old_live_path
                a_cycle.B_LEGACY_CYCLE_LOCK_PATH = old_legacy_path
                a_cycle.MAINTENANCE_READY_TIMEOUT_SECONDS = old_timeout
                a_cycle.MAINTENANCE_READY_POLL_SECONDS = old_poll
                a_cycle.MAINTENANCE_WAIT_LOG_EVERY_SECONDS = old_log_every
                a_cycle.MAINTENANCE_B_NOT_RUNNING_STABLE_SECONDS = old_stable

    def test_run_step_subprocess_defaults_cwd_to_repo_root(self) -> None:
        class _Proc:
            def wait(self) -> int:
                return 0

        with mock.patch.object(a_cycle.subprocess, "Popen", return_value=_Proc()) as popen_mock:
            result = a_cycle._run_step_subprocess(
                "dummy_step.py",
                ["python", "-c", "print('ok')"],
                env={},
            )

        self.assertEqual(int(result.get("returncode", -1)), 0)
        self.assertFalse(bool(result.get("interrupted", True)))
        self.assertEqual(str(a_cycle.ROOT), str(popen_mock.call_args.kwargs.get("cwd")))


if __name__ == "__main__":
    unittest.main()
