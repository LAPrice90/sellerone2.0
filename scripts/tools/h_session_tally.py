from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = ROOT / "out" / "systems" / "H" / "live"
TALLY_PATH = LIVE_DIR / "H_session_tally.json"
RUN_ID_PATH = LIVE_DIR / "H_cycle_current_run_id.txt"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _session_id() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=True, indent=2)
        fh.write("\n")
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _read_run_id(path: Path) -> str | None:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            run_id = fh.readline().strip()
            return run_id or None
    except Exception:
        return None


def _new_payload(now_iso: str) -> dict:
    return {
        "session_id": _session_id(),
        "started_at": now_iso,
        "loops_total": 0,
        "exit_0": 0,
        "exit_97": 0,
        "exit_other": 0,
        "consecutive_success": 0,
        "last_rc": None,
        "last_run_id": None,
        "last_updated_at": now_iso,
    }


def cmd_init(tally_file: Path) -> int:
    now_iso = _utc_now_iso()
    payload = _new_payload(now_iso)
    _atomic_write_json(tally_file, payload)
    return 0


def cmd_update(tally_file: Path, rc: int, run_id_file: Path) -> int:
    now_iso = _utc_now_iso()
    payload = _read_json(tally_file)
    if not payload:
        payload = _new_payload(now_iso)

    loops_total = int(payload.get("loops_total", 0) or 0) + 1
    exit_0 = int(payload.get("exit_0", 0) or 0)
    exit_97 = int(payload.get("exit_97", 0) or 0)
    exit_other = int(payload.get("exit_other", 0) or 0)
    consecutive_success = int(payload.get("consecutive_success", 0) or 0)

    if rc == 0:
        exit_0 += 1
        consecutive_success += 1
    elif rc == 97:
        exit_97 += 1
        consecutive_success = 0
    else:
        exit_other += 1
        consecutive_success = 0

    payload["loops_total"] = loops_total
    payload["exit_0"] = exit_0
    payload["exit_97"] = exit_97
    payload["exit_other"] = exit_other
    payload["consecutive_success"] = consecutive_success
    payload["last_rc"] = int(rc)
    payload["last_run_id"] = _read_run_id(run_id_file)
    payload["last_updated_at"] = now_iso

    _atomic_write_json(tally_file, payload)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize and update H launcher session tally.")
    parser.add_argument("--tally_file", default=str(TALLY_PATH))

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Reset tally for a new launcher session.")

    p_update = subparsers.add_parser("update", help="Update tally after one loop.")
    p_update.add_argument("--rc", required=True, type=int)
    p_update.add_argument("--run_id_file", default=str(RUN_ID_PATH))

    args = parser.parse_args()
    tally_file = Path(args.tally_file)

    if args.command == "init":
        return cmd_init(tally_file)
    if args.command == "update":
        return cmd_update(tally_file, int(args.rc), Path(args.run_id_file))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
