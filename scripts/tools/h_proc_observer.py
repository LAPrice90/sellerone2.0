from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = ROOT / "out" / "systems" / "H" / "live"
LOG_PATH = LIVE_DIR / "H_PROC_OBSERVER.log"
HEARTBEAT_PATH = LIVE_DIR / "H_pricing_cycle.HEARTBEAT.txt"
LOCK_PATH = LIVE_DIR / "H_pricing_cycle.lock"
TARGET = "run_H_pricing_cycle.py"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _trim(text: str, max_len: int = 200) -> str:
    raw = str(text or "").strip()
    if len(raw) <= max_len:
        return raw
    return raw[: max_len - 3] + "..."


def _append(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")


def _file_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        st = path.stat()
        ts = datetime.fromtimestamp(st.st_mtime, timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        return f"mtime_utc={ts} size={st.st_size}"
    except Exception as exc:
        return f"error={type(exc).__name__}"


def _list_python_processes() -> list[dict[str, object]]:
    cmd = (
        "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
        "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


def _matching_processes() -> dict[int, dict[str, object]]:
    out: dict[int, dict[str, object]] = {}
    for rec in _list_python_processes():
        cmdline = str(rec.get("CommandLine") or "")
        if TARGET.lower() not in cmdline.lower():
            continue
        try:
            pid = int(rec.get("ProcessId"))
        except Exception:
            continue
        out[pid] = {
            "ppid": int(rec.get("ParentProcessId") or 0),
            "cmdline": cmdline,
        }
    return out


def run(minutes: float) -> int:
    deadline = datetime.now(timezone.utc) + timedelta(minutes=max(float(minutes), 0.0))
    seen: dict[int, dict[str, object]] = {}
    _append(f"{_utc_now_iso()} event=START minutes={minutes}")

    while datetime.now(timezone.utc) < deadline:
        current = _matching_processes()

        # Log newly seen target processes.
        for pid, meta in current.items():
            if pid in seen:
                continue
            seen[pid] = meta
            _append(
                f"{_utc_now_iso()} event=FOUND pid={pid} "
                f"ppid={int(meta.get('ppid') or 0)} "
                f"cmdline=\"{_trim(str(meta.get('cmdline') or ''), 200)}\""
            )

        # Log disappeared processes and file states.
        for pid in list(seen.keys()):
            if pid in current:
                continue
            _append(f"{_utc_now_iso()} event=DISAPPEARED pid={pid}")
            _append(
                f"{_utc_now_iso()} event=FILE_STATE pid={pid} "
                f"heartbeat={_file_state(HEARTBEAT_PATH)} "
                f"lock={_file_state(LOCK_PATH)}"
            )
            del seen[pid]

        time.sleep(1.0)

    _append(f"{_utc_now_iso()} event=END")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe run_H_pricing_cycle.py process start/stop without admin rights.")
    parser.add_argument("--minutes", type=float, default=10.0, help="Observer runtime in minutes (default 10).")
    args = parser.parse_args()
    return run(args.minutes)


if __name__ == "__main__":
    raise SystemExit(main())
