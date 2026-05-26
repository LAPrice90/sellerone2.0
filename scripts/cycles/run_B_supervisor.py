from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

BOOT_ROOT = Path(__file__).resolve().parents[2]
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))
if str(BOOT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT / "scripts"))

try:
    from scripts.core.runtime_owner_contract import (
        RuntimeOwnerContractError,
        assert_flow_owner_mapping,
        is_truthy,
    )
    from scripts.core.runtime_stream import (
        build_lock_payload,
        parse_lock_pid as parse_stream_lock_pid,
        replace_lock_heartbeat as replace_stream_lock_heartbeat,
    )
except ModuleNotFoundError:
    from core.runtime_owner_contract import (
        RuntimeOwnerContractError,
        assert_flow_owner_mapping,
        is_truthy,
    )
    from core.runtime_stream import (
        build_lock_payload,
        parse_lock_pid as parse_stream_lock_pid,
        replace_lock_heartbeat as replace_stream_lock_heartbeat,
    )


ROOT = BOOT_ROOT
B_LIVE_DIR = ROOT / "out" / "systems" / "B" / "live"
B_LIVE_DIR.mkdir(parents=True, exist_ok=True)

SUPERVISOR_LOCK_PATH = Path(
    os.environ.get("B_SUPERVISOR_LOCK_PATH", B_LIVE_DIR / "B_supervisor.lock")
).resolve()
SUPERVISOR_LOG_PATH = Path(
    os.environ.get("B_SUPERVISOR_LOG_PATH", B_LIVE_DIR / "B_supervisor.log")
).resolve()
WORKER_PATH = Path(
    os.environ.get("B_SUPERVISOR_WORKER_PATH", ROOT / "scripts" / "cycles" / "run_B_cycle.py")
).resolve()

HEARTBEAT_SECONDS = max(float(os.environ.get("B_SUPERVISOR_HEARTBEAT_SECONDS", "5") or "5"), 1.0)
RESTART_DELAY_CLEAN_SECONDS = max(
    float(os.environ.get("B_SUPERVISOR_RESTART_DELAY_CLEAN_SECONDS", "3") or "3"),
    0.0,
)
RESTART_DELAY_FAIL_SECONDS = max(
    float(os.environ.get("B_SUPERVISOR_RESTART_DELAY_FAIL_SECONDS", "5") or "5"),
    0.0,
)
RUN_ONCE = str(os.environ.get("B_RUN_ONCE", "0")).strip().lower() in {"1", "true", "yes", "on"}
STOP_ON_SIGINT = str(os.environ.get("B_SUPERVISOR_STOP_ON_SIGINT", "0")).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STOP_EVENT = threading.Event()


def _owner_contract_enforced() -> bool:
    return is_truthy(os.environ.get("B_OWNER_CONTRACT_ENFORCE", "1"))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(message: str) -> None:
    SUPERVISOR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUPERVISOR_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{_ts()} [B_supervisor pid={os.getpid()}] {message}\n")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            output = (result.stdout or "").strip()
            return bool(output) and "No tasks are running" not in output
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _pid_command_line(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        if os.name == "nt":
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {int(pid)}\" | Select-Object -ExpandProperty CommandLine)",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return (result.stdout or "").strip()
        proc_cmdline = Path(f"/proc/{int(pid)}/cmdline")
        if proc_cmdline.exists():
            return proc_cmdline.read_text(encoding="utf-8", errors="replace").replace("\x00", " ").strip()
    except Exception:
        return ""
    return ""


def _pid_is_supervisor_owner(pid: int) -> bool:
    if not _pid_alive(pid):
        return False
    cmd = _pid_command_line(pid).lower()
    if not cmd:
        return False
    return "run_b_supervisor.py" in cmd


def _parse_lock_pid(payload: str) -> int | None:
    return parse_stream_lock_pid(payload)


def _write_lock() -> None:
    now = _ts()
    payload = build_lock_payload(
        owner="B_SUPERVISOR",
        pid=os.getpid(),
        fields={"worker": str(WORKER_PATH)},
        start_utc=now,
        heartbeat_utc=now,
    )
    SUPERVISOR_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUPERVISOR_LOCK_PATH.write_text(payload, encoding="utf-8")


def _heartbeat_loop() -> None:
    while not STOP_EVENT.wait(HEARTBEAT_SECONDS):
        try:
            _touch_lock_heartbeat()
        except Exception as exc:
            _log(f"heartbeat_write_failed detail={exc}")


def _touch_lock_heartbeat() -> None:
    now = _ts()
    try:
        existing = SUPERVISOR_LOCK_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        existing = ""
    payload = ""
    if existing:
        existing_pid = _parse_lock_pid(existing)
        if existing_pid == os.getpid():
            payload = replace_stream_lock_heartbeat(existing, heartbeat_utc=now)
    if not payload:
        payload = build_lock_payload(
            owner="B_SUPERVISOR",
            pid=os.getpid(),
            fields={"worker": str(WORKER_PATH)},
            start_utc=now,
            heartbeat_utc=now,
        )
    SUPERVISOR_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUPERVISOR_LOCK_PATH.write_text(payload, encoding="utf-8")


def _release_lock() -> None:
    try:
        if not SUPERVISOR_LOCK_PATH.exists():
            return
        payload = SUPERVISOR_LOCK_PATH.read_text(encoding="utf-8", errors="replace")
        pid = _parse_lock_pid(payload)
        if pid == os.getpid() or pid is None or not _pid_is_supervisor_owner(pid):
            SUPERVISOR_LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def _install_handlers() -> None:
    def _handle_signal(signum, _frame) -> None:
        signum_int = int(signum)
        if signum_int == int(getattr(signal, "SIGINT", 2)) and not STOP_ON_SIGINT:
            _log(f"signal_received signum={signum_int}; ignored")
            return
        _log(f"signal_received signum={signum_int}; shutting down")
        STOP_EVENT.set()

    for signum_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signum = getattr(signal, signum_name, None)
        if signum is not None:
            try:
                signal.signal(signum, _handle_signal)
            except Exception:
                continue
    atexit.register(_release_lock)


def _acquire_lock() -> bool:
    if SUPERVISOR_LOCK_PATH.exists():
        try:
            payload = SUPERVISOR_LOCK_PATH.read_text(encoding="utf-8", errors="replace")
        except Exception:
            payload = ""
        existing_pid = _parse_lock_pid(payload)
        if existing_pid is not None and _pid_is_supervisor_owner(existing_pid):
            _log(f"duplicate_exit existing_supervisor_pid={existing_pid}")
            return False
        if existing_pid is not None and _pid_alive(existing_pid):
            _log(f"recovering_stale_lock previous_pid={existing_pid} reason=pid_reused_non_supervisor")
        else:
            _log(f"recovering_stale_lock previous_pid={existing_pid or 0}")
        try:
            SUPERVISOR_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass
    _write_lock()
    return True


def _build_child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["B_SUPERVISOR_PID"] = str(os.getpid())
    env["B_SUPERVISOR_ACTIVE"] = "1"
    env.setdefault("PYTHONPATH", str(ROOT))
    return env


def _run_worker_once() -> int:
    cmd = [sys.executable, str(WORKER_PATH)]
    _log(f"worker_launch cmd={cmd}")
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=_build_child_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    rc = int(result.returncode)
    if rc != 0:
        stdout_tail = " | ".join((result.stdout or "").splitlines()[-5:]).strip()
        stderr_tail = " | ".join((result.stderr or "").splitlines()[-8:]).strip()
        if len(stdout_tail) > 600:
            stdout_tail = stdout_tail[-600:]
        if len(stderr_tail) > 1200:
            stderr_tail = stderr_tail[-1200:]
        _log(f"worker_exit rc={rc} stdout_tail={stdout_tail} stderr_tail={stderr_tail}")
    else:
        _log(f"worker_exit rc={rc}")
    return int(result.returncode)


def main() -> int:
    if _owner_contract_enforced():
        try:
            kwargs = {
                "flow": "B",
                "runtime_owner": Path(__file__),
                "launcher_entrypoint": ROOT / "run_B_cycle.bat",
            }
            if "B_SUPERVISOR_WORKER_PATH" not in os.environ:
                kwargs["worker_entry"] = WORKER_PATH
            assert_flow_owner_mapping(**kwargs)
        except RuntimeOwnerContractError as exc:
            _log(f"owner_contract_violation detail={exc}")
            return 2

    _install_handlers()
    if not _acquire_lock():
        return 0

    heartbeat = threading.Thread(target=_heartbeat_loop, name="BSupervisorHeartbeat", daemon=True)
    heartbeat.start()
    _log("supervisor_started")

    try:
        while True:
            rc = _run_worker_once()
            if RUN_ONCE:
                _log(f"run_once_exit rc={rc}")
                return rc
            delay = RESTART_DELAY_CLEAN_SECONDS if rc == 0 else RESTART_DELAY_FAIL_SECONDS
            _log(f"restart_scheduled delay_seconds={delay:.1f} rc={rc}")
            if STOP_EVENT.wait(delay):
                return 0
    finally:
        STOP_EVENT.set()
        heartbeat.join(timeout=2.0)
        _release_lock()
        _log("supervisor_stopped")


if __name__ == "__main__":
    raise SystemExit(main())
