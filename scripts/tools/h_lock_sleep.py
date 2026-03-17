from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone
from pathlib import Path


def _parse_heartbeat(lock_payload: str) -> datetime | None:
    match = re.search(r"(?:^|\|)heartbeat=([^|]+)", lock_payload)
    if not match:
        return None
    raw = match.group(1).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _target_stale_seconds() -> int:
    override = os.environ.get("H_LOCK_STALE_SECONDS_OVERRIDE")
    if override is not None:
        try:
            return int(override)
        except ValueError:
            pass
    return 900


def recommended_sleep(lock_path: Path) -> int:
    base = _target_stale_seconds()
    if base < 0:
        base = 0
    try:
        payload = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return 15
    heartbeat = _parse_heartbeat(payload)
    if heartbeat is None:
        return 15
    now_utc = datetime.now(timezone.utc)
    age = int((now_utc - heartbeat).total_seconds())
    sleep = base - age + 5
    if sleep < 15:
        sleep = 15
    return int(sleep)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock-path", default=os.environ.get("H_CYCLE_LOCK_PATH", ""))
    args = parser.parse_args()
    lock_path = Path(args.lock_path) if args.lock_path else Path("out/systems/H/live/H_pricing_cycle.lock")
    print(recommended_sleep(lock_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
