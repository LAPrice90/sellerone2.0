from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.cycles import run_B_supervisor as supervisor_mod


ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "scripts" / "cycles" / "run_B_supervisor.py"


class TestBSupervisor(unittest.TestCase):
    def test_run_once_cleans_lock_and_logs_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worker = tmp_path / "fake_worker.py"
            worker.write_text("print('fake worker ok')\n", encoding="utf-8")
            lock_path = tmp_path / "B_supervisor.lock"
            log_path = tmp_path / "B_supervisor.log"

            env = os.environ.copy()
            env["B_RUN_ONCE"] = "1"
            env["B_SUPERVISOR_WORKER_PATH"] = str(worker)
            env["B_SUPERVISOR_LOCK_PATH"] = str(lock_path)
            env["B_SUPERVISOR_LOG_PATH"] = str(log_path)
            env["B_CYCLE_LOCK_PATH"] = str(tmp_path / "B_cycle.lock")
            env["RUN_LOCK_PATH"] = str(tmp_path / "B_cycle.lock")

            result = subprocess.run(
                [sys.executable, str(SUPERVISOR)],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertFalse(lock_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("supervisor_started", log_text)
            self.assertIn("worker_exit rc=0", log_text)
            self.assertIn("supervisor_stopped", log_text)

    def test_stale_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worker = tmp_path / "fake_worker.py"
            worker.write_text(
                textwrap.dedent(
                    """
                    from pathlib import Path
                    Path(__file__).with_name('worker_marker.txt').write_text('ok', encoding='utf-8')
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            lock_path = tmp_path / "B_supervisor.lock"
            log_path = tmp_path / "B_supervisor.log"
            lock_path.write_text("B_SUPERVISOR|pid=999999|start=x|heartbeat=x\n", encoding="utf-8")

            env = os.environ.copy()
            env["B_RUN_ONCE"] = "1"
            env["B_SUPERVISOR_WORKER_PATH"] = str(worker)
            env["B_SUPERVISOR_LOCK_PATH"] = str(lock_path)
            env["B_SUPERVISOR_LOG_PATH"] = str(log_path)
            env["B_CYCLE_LOCK_PATH"] = str(tmp_path / "B_cycle.lock")
            env["RUN_LOCK_PATH"] = str(tmp_path / "B_cycle.lock")

            result = subprocess.run(
                [sys.executable, str(SUPERVISOR)],
                cwd=str(tmp_path),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertFalse(lock_path.exists())
            self.assertTrue((tmp_path / "worker_marker.txt").exists())
            self.assertIn("recovering_stale_lock", log_path.read_text(encoding="utf-8"))

    def test_live_non_supervisor_pid_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            lock_path = tmp_path / "B_supervisor.lock"
            log_path = tmp_path / "B_supervisor.log"
            lock_path.write_text("B_SUPERVISOR|pid=1234|start=x|heartbeat=x\n", encoding="utf-8")

            old_lock = supervisor_mod.SUPERVISOR_LOCK_PATH
            old_log = supervisor_mod.SUPERVISOR_LOG_PATH
            old_pid_alive = supervisor_mod._pid_alive
            old_pid_owner = supervisor_mod._pid_is_supervisor_owner
            try:
                supervisor_mod.SUPERVISOR_LOCK_PATH = lock_path
                supervisor_mod.SUPERVISOR_LOG_PATH = log_path
                supervisor_mod._pid_alive = lambda pid: int(pid) == 1234
                supervisor_mod._pid_is_supervisor_owner = lambda pid: False
                acquired = supervisor_mod._acquire_lock()
                self.assertTrue(acquired)
                payload = lock_path.read_text(encoding="utf-8")
                self.assertIn(f"pid={os.getpid()}", payload)
                self.assertIn("reason=pid_reused_non_supervisor", log_path.read_text(encoding="utf-8"))
            finally:
                supervisor_mod.SUPERVISOR_LOCK_PATH = old_lock
                supervisor_mod.SUPERVISOR_LOG_PATH = old_log
                supervisor_mod._pid_alive = old_pid_alive
                supervisor_mod._pid_is_supervisor_owner = old_pid_owner

    def test_touch_lock_heartbeat_preserves_start_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            lock_path = tmp_path / "B_supervisor.lock"
            log_path = tmp_path / "B_supervisor.log"

            old_lock = supervisor_mod.SUPERVISOR_LOCK_PATH
            old_log = supervisor_mod.SUPERVISOR_LOG_PATH
            try:
                supervisor_mod.SUPERVISOR_LOCK_PATH = lock_path
                supervisor_mod.SUPERVISOR_LOG_PATH = log_path
                supervisor_mod._write_lock()
                first_payload = lock_path.read_text(encoding="utf-8")
                first_start = ""
                for token in first_payload.split("|"):
                    part = token.strip()
                    if part.startswith("start="):
                        first_start = part.split("=", 1)[1].strip()
                        break
                self.assertTrue(first_start)
                supervisor_mod._touch_lock_heartbeat()
                second_payload = lock_path.read_text(encoding="utf-8")
                second_start = ""
                for token in second_payload.split("|"):
                    part = token.strip()
                    if part.startswith("start="):
                        second_start = part.split("=", 1)[1].strip()
                        break
                self.assertEqual(first_start, second_start)
            finally:
                supervisor_mod.SUPERVISOR_LOCK_PATH = old_lock
                supervisor_mod.SUPERVISOR_LOG_PATH = old_log


if __name__ == "__main__":
    unittest.main()
