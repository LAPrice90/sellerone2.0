from __future__ import annotations

import os
import sys
import time
import traceback
import signal
import faulthandler
import threading
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", errors="replace")


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(text)


def main() -> int:
    root = _resolve_root()
    live = _live_dir(root)

    # Make Python behave like a "real service" process
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["PYTHONFAULTHANDLER"] = "1"

    crash_log = live / "H_pricing_cycle.CRASH.log"
    heartbeat = live / "H_pricing_cycle.HEARTBEAT.txt"
    phase = live / "H_pricing_cycle.PHASE.txt"
    fault_log = live / "H_pricing_cycle.FAULT.log"
    _fault_fh = fault_log.open("a", encoding="utf-8", errors="replace")
    faulthandler.enable(_fault_fh)
    diagnostic_mode = os.environ.get("H_GUARD_DIAGNOSTIC_MODE", "0").strip() == "1"
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
            f"PHASE=phase1_pilot({pilot_mode}) phase1_intel({intel_mode}) phase1_publish({publish_mode})\n"
            f"GUARD_DIAGNOSTIC_MODE={'1' if diagnostic_mode else '0'}\n"
            f"BISECT_FORCE_INLINE={bisect_force_inline}\n"
            f"STAGES snapshot_refresh={stage_snapshot_refresh} item_offers={stage_item_offers} "
            f"phase1_pilot={stage_phase1_pilot} phase1_intel={stage_phase1_intel} "
            f"phase1_publish={stage_phase1_publish}\n"
        ),
    )

    _real_os_exit = os._exit

    if diagnostic_mode:
        # Monkeypatch only in diagnostic mode to avoid side effects in steady state.
        def _patched_os_exit(code: int = 0) -> None:
            _append_text(
                heartbeat,
                (
                    f"OS_EXIT utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                    f"rc={code}\n"
                ),
            )
            _fault_fh.flush()
            _real_os_exit(code)

        os._exit = _patched_os_exit  # type: ignore

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
        # Import your real entrypoint
        # This matches what run_H_pricing_cycle.py currently does, but with guardrails.
        from scripts.cycles.run_H_pricing_cycle import main as real_main  # type: ignore

        if diagnostic_mode:
            def _one_dump() -> None:
                try:
                    time.sleep(20)
                    faulthandler.dump_traceback(file=_fault_fh, all_threads=True)
                    _fault_fh.flush()
                except Exception:
                    pass

            threading.Thread(target=_one_dump, daemon=True).start()
        _write_text(phase, "before_real_main\n")
        rc = int(real_main())
        _write_text(phase, "after_real_main\n")
        stop_flag.set()
        _append_text(
            heartbeat,
            f"EXIT_OK utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\nrc={rc}\n",
        )
        return rc

    except SystemExit as e:
        # Some code uses SystemExit for control flow. Capture it explicitly.
        code = e.code
        rc = int(code) if isinstance(code, int) else 1
        stop_flag.set()
        _append_text(
            heartbeat,
            (
                f"SYSTEMEXIT utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                f"rc={rc}\ncode={code!r}\n"
            ),
        )
        return rc

    except BaseException:
        # Guaranteed traceback, even if logging is dead/buffered
        tb = traceback.format_exc()
        stop_flag.set()
        _write_text(
            crash_log,
            f"UTC={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            f"argv={sys.argv!r}\n\n"
            f"{tb}\n",
        )
        _append_text(
            heartbeat,
            f"EXIT_CRASH utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\nrc=2\n",
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
