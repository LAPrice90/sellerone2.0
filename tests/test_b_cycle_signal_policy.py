from __future__ import annotations

import os
import signal
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.cycles import run_B_cycle as b_cycle


def test_ignore_sigint_defaults_on_when_supervisor_active(monkeypatch) -> None:
    monkeypatch.delenv("B_IGNORE_SIGINT", raising=False)
    monkeypatch.setenv("B_SUPERVISOR_ACTIVE", "1")
    assert b_cycle._ignore_sigint_enabled() is True


def test_ignore_sigint_can_be_forced_off(monkeypatch) -> None:
    monkeypatch.setenv("B_SUPERVISOR_ACTIVE", "1")
    monkeypatch.setenv("B_IGNORE_SIGINT", "0")
    assert b_cycle._ignore_sigint_enabled() is False


def test_sigint_ignored_does_not_set_exit_code(monkeypatch) -> None:
    monkeypatch.setenv("B_SUPERVISOR_ACTIVE", "1")
    monkeypatch.delenv("B_IGNORE_SIGINT", raising=False)
    log_lines: list[str] = []
    monkeypatch.setattr(b_cycle, "_log", lambda msg: log_lines.append(str(msg)))
    b_cycle._SIGNAL_EXIT_CODE = None

    b_cycle._install_lock_cleanup_handlers()
    handler = signal.getsignal(signal.SIGINT)
    assert callable(handler)
    handler(signal.SIGINT, None)

    assert b_cycle._SIGNAL_EXIT_CODE is None
    assert any("signum=2; ignored" in line for line in log_lines)


def test_sigint_not_ignored_sets_exit_code(monkeypatch) -> None:
    monkeypatch.setenv("B_IGNORE_SIGINT", "0")
    monkeypatch.setenv("B_SUPERVISOR_ACTIVE", "1")
    log_lines: list[str] = []
    monkeypatch.setattr(b_cycle, "_log", lambda msg: log_lines.append(str(msg)))
    b_cycle._SIGNAL_EXIT_CODE = None

    b_cycle._install_lock_cleanup_handlers()
    handler = signal.getsignal(signal.SIGINT)
    assert callable(handler)
    handler(signal.SIGINT, None)

    assert b_cycle._SIGNAL_EXIT_CODE == 130
    assert any("graceful_shutdown_requested" in line for line in log_lines)

