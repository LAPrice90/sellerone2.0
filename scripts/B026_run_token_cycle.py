"""
Run the November-anchored token cycle end-to-end (CSV-only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
LOG_PATH = OUT_DIR / "token_cycle.log"
SUMMARY_PATH = OUT_DIR / "token_cycle_summary.json"


BASE_STEPS = [
    ("build_token_cogs_ledger", ["scripts/B025_build_token_cogs_ledger.py"]),
    ("rebuild_level1_from_archive", ["scripts/one_off/T023_rebuild_level1_from_archive.py"]),
    ("build_order_master", ["scripts/B004_build_order_master.py"]),
    ("build_token_tests_daily", ["scripts/one_off/T001_B011_build_token_tests_daily.py"]),
    ("build_token_daily_checklist", ["scripts/B014_build_token_daily_checklist.py"]),
]

STEPS = list(BASE_STEPS)


def run_step(name: str, args: list[str]) -> dict:
    start = datetime.now(timezone.utc)
    result = subprocess.run(
        [sys.executable] + args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    end = datetime.now(timezone.utc)
    return {
        "step": name,
        "command": " ".join([sys.executable] + args),
        "status": "ok" if result.returncode == 0 else "fail",
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "started_at": start.isoformat(),
        "ended_at": end.isoformat(),
        "duration_sec": (end - start).total_seconds(),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    steps_out = []
    for name, args in STEPS:
        info = run_step(name, args)
        steps_out.append(info)
        with LOG_PATH.open("a", encoding="ascii") as fh:
            fh.write(json.dumps(info, ensure_ascii=True) + "\n")
        if info["status"] != "ok":
            break

    summary = {
        "status": "success" if all(s["status"] == "ok" for s in steps_out) else "failed",
        "steps": steps_out,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=True, indent=2), encoding="ascii")
    print({"status": summary["status"], "log": str(LOG_PATH), "summary": str(SUMMARY_PATH)})


if __name__ == "__main__":
    main()
