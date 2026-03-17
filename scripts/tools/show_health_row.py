from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.A.A015_build_system_health_check import (  # noqa: E402
    _default_checklist_for_profile,
    _normalize_profile,
)


def _resolve_checklist_path(profile_raw: str) -> Path:
    profile = _normalize_profile(profile_raw)
    path = _default_checklist_for_profile(profile)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _last_write_time_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _matching_row_lines(path: Path, key: str) -> list[str]:
    matches: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            try:
                cols = next(csv.reader([line]))
            except Exception:
                continue
            if cols and cols[0].strip() == key:
                matches.append(line)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="Show matching health checklist row(s) for a profile/key.")
    parser.add_argument("--profile", default="global", choices=["global", "a", "b", "e", "h"])
    parser.add_argument("--key", required=True, help="Checklist check key to print (for example h_cycle_stale_lock).")
    args = parser.parse_args()

    checklist_path = _resolve_checklist_path(args.profile)
    print(f"checklist={checklist_path}")
    if not checklist_path.exists():
        print(f"missing_file={checklist_path}")
        return 0

    print(f"LastWriteTimeUtc={_last_write_time_utc(checklist_path)}")
    rows = _matching_row_lines(checklist_path, args.key)
    if not rows:
        print(f"no_rows key={args.key}")
        return 0

    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
