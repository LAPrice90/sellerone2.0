from __future__ import annotations

import os
import sys
import time
import traceback
import signal
import faulthandler
import threading
import subprocess
from pathlib import Path

# IMPORTANT:
# This wrapper does NOT change your cycle logic.
# It forces unbuffered output + writes a guaranteed traceback file if anything goes wrong,
# even if your normal logger never flushes.


def _resolve_root() -> Path:
    # This file is scripts/cycles/run_H_pricing_cycle_guarded.py
    # Repo root is two parents up from scripts/
    return Path(__file__).resolve().parents[2]


def _live_dir(root: Path) -> Path:
    live = root / "out" / "systems" / "H" / "live"
    live.mkdir(parents=True, exist_ok=True)
    return live


def _write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")
    except BaseException:
        pass


def _append_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(text)
    except BaseException:
        pass


def _truthy_env(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    root = _resolve_root()
    live = _live_dir(root)

    # Make Python behave like a "real service" process
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["PYTHONFAULTHANDLER"] = "1"

    crash_log = live / "H_pricing_cycle.CRASH.log"
    heartbeat = live / "H_pricing_cycle.HEARTBEAT.txt"
    exit_status = live / "H_pricing_cycle.EXIT_STATUS.txt"
    phase = live / "H_pricing_cycle.PHASE.txt"
    fault_log = live / "H_pricing_cycle.FAULT.log"
    _fault_fh = fault_log.open("a", encoding="utf-8", errors="replace")
    faulthandler.enable(_fault_fh)
    diagnostic_mode = os.environ.get("H_GUARD_DIAGNOSTIC_MODE", "0").strip() == "1"
    ignore_keyboard_interrupt = _truthy_env("H_GUARD_IGNORE_KEYBOARD_INTERRUPT", "1") and not diagnostic_mode
    if diagnostic_mode:
        # Diagnostic mode is intentionally noisy and can affect runtime behavior.
        faulthandler.dump_traceback_later(30, repeat=True, file=_fault_fh)

    # Heartbeat at process start
    pilot_mode = (os.environ.get("H_PHASE1_PILOT_MODE", "inline").strip().lower() or "inline")
    intel_mode = (os.environ.get("H_PHASE1_INTEL_MODE", "inline").strip().lower() or "inline")
    publish_mode = (os.environ.get("H_PHASE1_PUBLISH_MODE", "inline").strip().lower() or "inline")
    bisect_force_inline = "1" if os.environ.get("H_BISECT_FORCE_INLINE", "0").strip() == "1" else "0"
    stage_snapshot_refresh = "1" if os.environ.get("H_STAGE_SNAPSHOT_REFRESH", "1").strip() == "1" else "0"
    stage_item_offers = "1" if os.environ.get("H_STAGE_ITEM_OFFERS", "1").strip() == "1" else "0"
    stage_phase1_pilot = "1" if os.environ.get("H_STAGE_PHASE1_PILOT", "1").strip() == "1" else "0"
    stage_phase1_intel = "1" if os.environ.get("H_STAGE_PHASE1_INTEL", "1").strip() == "1" else "0"
    stage_phase1_publish = "1" if os.environ.get("H_STAGE_PHASE1_PUBLISH", "1").strip() == "1" else "0"
    _write_text(
        heartbeat,
        (
            f"START utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            f"argv={sys.argv!r}\n"
            f"MODE={'diagnostic' if diagnostic_mode else 'steady'}\n"
            f"PHASE=phase1_pilot({pilot_mode}) phase1_intel({intel_mode}) phase1_publish({publish_mode})\n"
            f"GUARD_DIAGNOSTIC_MODE={'1' if diagnostic_mode else '0'}\n"
            f"BISECT_FORCE_INLINE={bisect_force_inline}\n"
            f"STAGES snapshot_refresh={stage_snapshot_refresh} item_offers={stage_item_offers} "
            f"phase1_pilot={stage_phase1_pilot} phase1_intel={stage_phase1_intel} "
            f"phase1_publish={stage_phase1_publish}\n"
        ),
    )
    _write_text(
        exit_status,
        (
            f"START utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            f"status=running\n"
        ),
    )

    _real_os_exit = os._exit

    # Always record hard exits so launcher checks can catch non-graceful paths.
    def _patched_os_exit(code: int = 0) -> None:
        utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        _append_text(
            heartbeat,
            (
                f"OS_EXIT utc={utc}\n"
                f"rc={code}\n"
            ),
        )
        _write_text(
            exit_status,
            (
                f"OS_EXIT utc={utc}\n"
                f"rc={code}\n"
            ),
        )
        _fault_fh.flush()
        _real_os_exit(code)

    os._exit = _patched_os_exit  # type: ignore

    if diagnostic_mode:

        def _on_signal(signum, frame):  # type: ignore
            _append_text(
                heartbeat,
                (
                    f"SIGNAL utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                    f"signum={signum}\n"
                ),
            )
            _fault_fh.flush()
            raise SystemExit(128 + int(signum))

        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)
    elif ignore_keyboard_interrupt:
        # In steady state, ignore external console-style interrupts so launcher loops stay resilient.
        def _ignore_signal(signum, _frame):  # type: ignore
            _append_text(
                heartbeat,
                (
                    f"SIGNAL utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                    f"signum={signum}\n"
                    "ignored=1\n"
                ),
            )

        for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, _ignore_signal)
            except Exception:
                continue

    stop_flag = threading.Event()

    if diagnostic_mode:
        def _ticker() -> None:
            while not stop_flag.is_set():
                _append_text(
                    heartbeat,
                    f"ALIVE utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n",
                )
                time.sleep(2)

        t = threading.Thread(target=_ticker, daemon=True)
        t.start()

    try:
        # Run the real cycle in a supervised child process so wrapper markers survive child crashes.
        child_cmd = [
            sys.executable,
            "-u",
            str(root / "scripts" / "cycles" / "run_H_pricing_cycle.py"),
            *sys.argv[1:],
        ]
        _write_text(phase, "before_real_main_subprocess\n")
        popen_kwargs = {"cwd": str(root)}
        if os.name == "nt":
            create_new_group = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            if create_new_group:
                popen_kwargs["creationflags"] = create_new_group
        child = subprocess.Popen(child_cmd, **popen_kwargs)
        while True:
            try:
                rc = int(child.wait(timeout=1.0))
                break
            except subprocess.TimeoutExpired:
                continue
            except KeyboardInterrupt:
                utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                _append_text(
                    heartbeat,
                    (
                        f"SIGNAL utc={utc}\n"
                        "signum=SIGINT\n"
                        f"ignored={'1' if ignore_keyboard_interrupt else '0'}\n"
                    ),
                )
                if ignore_keyboard_interrupt:
                    continue
                raise
        _write_text(phase, "after_real_main_subprocess\n")
        stop_flag.set()
        utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        if rc == 0:
            _append_text(
                heartbeat,
                f"EXIT_OK utc={utc}\nrc={rc}\n",
            )
            _write_text(
                exit_status,
                (
                    f"EXIT_OK utc={utc}\n"
                    f"rc={rc}\n"
                ),
            )
        else:
            _append_text(
                heartbeat,
                f"SYSTEMEXIT utc={utc}\nrc={rc}\ncode=child_rc\n",
            )
            _write_text(
                exit_status,
                (
                    f"SYSTEMEXIT utc={utc}\n"
                    f"rc={rc}\n"
                    "code=child_rc\n"
                ),
            )
        return rc

    except SystemExit as e:
        # Some code uses SystemExit for control flow. Capture it explicitly.
        code = e.code
        rc = int(code) if isinstance(code, int) else 1
        stop_flag.set()
        utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        _append_text(
            heartbeat,
            (
                f"SYSTEMEXIT utc={utc}\n"
                f"rc={rc}\ncode={code!r}\n"
            ),
        )
        _write_text(
            exit_status,
            (
                f"SYSTEMEXIT utc={utc}\n"
                f"rc={rc}\n"
                f"code={code!r}\n"
            ),
        )
        return rc

    except BaseException:
        # Guaranteed traceback, even if logging is dead/buffered
        tb = traceback.format_exc()
        stop_flag.set()
        utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        _write_text(
            crash_log,
            f"UTC={utc}\n"
            f"argv={sys.argv!r}\n\n"
            f"{tb}\n",
        )
        _append_text(
            heartbeat,
            f"EXIT_CRASH utc={utc}\nrc=2\n",
        )
        _write_text(
            exit_status,
            (
                f"EXIT_CRASH utc={utc}\n"
                "rc=2\n"
            ),
        )
        return 2
    finally:
        stop_flag.set()
        if diagnostic_mode:
            faulthandler.cancel_dump_traceback_later()
        _fault_fh.flush()
        _fault_fh.close()
        os._exit = _real_os_exit  # type: ignore


if __name__ == "__main__":
    raise SystemExit(main())
