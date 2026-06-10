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

    def test_write_maintenance_handoff_proof_records_cleanup_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_request = a_cycle.MAINTENANCE_REQUEST_PATH
            old_ready = a_cycle.MAINTENANCE_READY_PATH
            old_active = a_cycle.MAINTENANCE_ACTIVE_PATH
            old_latest = a_cycle.A_MAINTENANCE_HANDOFF_LATEST_PATH
            old_history = a_cycle.A_MAINTENANCE_HANDOFF_HISTORY_PATH
            try:
                a_cycle.MAINTENANCE_REQUEST_PATH = root / "maintenance.requested"
                a_cycle.MAINTENANCE_READY_PATH = root / "maintenance.ready"
                a_cycle.MAINTENANCE_ACTIVE_PATH = root / "maintenance.active"
                a_cycle.A_MAINTENANCE_HANDOFF_LATEST_PATH = root / "out" / "systems" / "A" / "live" / "a_maintenance_handoff_latest.json"
                a_cycle.A_MAINTENANCE_HANDOFF_HISTORY_PATH = root / "out" / "systems" / "A" / "history" / "a_maintenance_handoff_history.jsonl"

                a_cycle.MAINTENANCE_READY_PATH.write_text(
                    "B_READY|pid=123|ts=2026-05-27T07:00:00Z|request_id=REQ_A\n",
                    encoding="utf-8",
                )
                a_cycle.MAINTENANCE_ACTIVE_PATH.write_text(
                    "active_by=A|pid=456|ts=2026-05-27T07:01:00Z|request_id=REQ_A\n",
                    encoding="utf-8",
                )
                ready_evidence = a_cycle._marker_evidence(a_cycle.MAINTENANCE_READY_PATH)
                active_evidence = a_cycle._marker_evidence(a_cycle.MAINTENANCE_ACTIVE_PATH)
                a_cycle.MAINTENANCE_READY_PATH.unlink()
                a_cycle.MAINTENANCE_ACTIVE_PATH.unlink()

                payload = a_cycle._write_a_maintenance_handoff_proof(
                    request_id="REQ_A",
                    handoff_mode="b_ready",
                    b_ready_evidence=ready_evidence,
                    b_status_at_handoff={"running": False},
                    a_active_evidence=active_evidence,
                    final_run_id="A_TEST",
                    final_state="completed",
                    final_exit_code=0,
                    manifest_path="out/manifests/A/test.json",
                )

                self.assertEqual(payload["proof_status"], "ok")
                self.assertTrue(a_cycle.A_MAINTENANCE_HANDOFF_LATEST_PATH.exists())
                self.assertTrue(a_cycle.A_MAINTENANCE_HANDOFF_HISTORY_PATH.exists())
                self.assertIn("REQ_A", a_cycle.A_MAINTENANCE_HANDOFF_HISTORY_PATH.read_text(encoding="utf-8"))
            finally:
                a_cycle.MAINTENANCE_REQUEST_PATH = old_request
                a_cycle.MAINTENANCE_READY_PATH = old_ready
                a_cycle.MAINTENANCE_ACTIVE_PATH = old_active
                a_cycle.A_MAINTENANCE_HANDOFF_LATEST_PATH = old_latest
                a_cycle.A_MAINTENANCE_HANDOFF_HISTORY_PATH = old_history


if __name__ == "__main__":
    unittest.main()
