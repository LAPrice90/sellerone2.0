from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SNOOZE_PATH = ROOT / "out" / "locks" / "health_alert_snooze.json"


def _to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _read_state() -> dict:
    if not SNOOZE_PATH.exists():
        return {}
    try:
        payload = json.loads(SNOOZE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _print_status(now_utc: datetime) -> int:
    state = _read_state()
    if not state:
        print("health alert snooze: off")
        return 0
    until_raw = str(state.get("snooze_until_utc", "")).strip()
    reason = str(state.get("reason", "")).strip()
    if not until_raw:
        print("health alert snooze: invalid (missing snooze_until_utc)")
        return 1
    try:
        until_dt = _parse_utc(until_raw)
    except Exception:
        print("health alert snooze: invalid (bad snooze_until_utc)")
        return 1
    if until_dt > now_utc:
        msg = f"health alert snooze: active until {until_raw}"
        if reason:
            msg += f" reason={reason}"
        print(msg)
    else:
        print(f"health alert snooze: expired at {until_raw}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set, clear, or view health-check toast snooze."
    )
    parser.add_argument(
        "--minutes",
        type=float,
        default=None,
        help="Snooze for this many minutes from now (UTC).",
    )
    parser.add_argument(
        "--until",
        type=str,
        default="",
        help="Absolute UTC end time, ISO format (example: 2026-02-11T17:30:00Z).",
    )
    parser.add_argument(
        "--reason",
        type=str,
        default="",
        help="Optional short reason saved with the snooze.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear current snooze.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current snooze status.",
    )
    args = parser.parse_args()

    now_utc = datetime.now(timezone.utc)

    if args.status:
        raise SystemExit(_print_status(now_utc))

    if args.clear:
        if SNOOZE_PATH.exists():
            SNOOZE_PATH.unlink()
            print("health alert snooze: cleared")
        else:
            print("health alert snooze: already off")
        return

    if args.minutes is None and not args.until.strip():
        parser.error("provide --minutes or --until (or use --status / --clear)")

    if args.minutes is not None and args.until.strip():
        parser.error("use only one of --minutes or --until")

    if args.minutes is not None:
        if args.minutes <= 0:
            parser.error("--minutes must be greater than 0")
        until_dt = now_utc + timedelta(minutes=float(args.minutes))
    else:
        try:
            until_dt = _parse_utc(args.until.strip())
        except Exception:
            parser.error("--until must be a valid ISO UTC time, example 2026-02-11T17:30:00Z")
        if until_dt <= now_utc:
            parser.error("--until must be in the future")

    payload = {
        "snooze_until_utc": _to_iso_z(until_dt),
        "set_at_utc": _to_iso_z(now_utc),
        "reason": args.reason.strip(),
    }
    SNOOZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNOOZE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"health alert snooze: active until {payload['snooze_until_utc']}")
    if payload["reason"]:
        print(f"reason={payload['reason']}")


if __name__ == "__main__":
    main()

