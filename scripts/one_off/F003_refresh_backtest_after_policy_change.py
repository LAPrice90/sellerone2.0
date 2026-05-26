from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

REFRESH_COMMANDS = [
    [sys.executable, "-m", "scripts.flows.F.F075_apply_backtest_policy_updates"],
    [sys.executable, "-m", "scripts.flows.F.F071_build_backtest_input_view"],
    [sys.executable, "-m", "scripts.flows.F.F072_run_backtest_replay"],
    [sys.executable, "-m", "scripts.flows.F.F073_build_backtest_summary"],
    [sys.executable, "-m", "scripts.flows.F.F074_build_backtest_health"],
    [sys.executable, "scripts/one_off/F002_build_backtest_calibration_set.py"],
]


def refresh_backtest_after_policy_change(root: Path = ROOT) -> list[dict[str, object]]:
    steps: list[dict[str, object]] = []
    for command in REFRESH_COMMANDS:
        proc = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        step = {
            "command": " ".join(command),
            "returncode": int(proc.returncode),
            "stdout_tail": proc.stdout[-600:].strip(),
            "stderr_tail": proc.stderr[-600:].strip(),
        }
        steps.append(step)
        if proc.returncode != 0:
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "failed_command": " ".join(command),
                        "steps": steps,
                    }
                )
            )
            raise SystemExit(proc.returncode)
    print(json.dumps({"status": "success", "steps": steps}))
    return steps


def main() -> None:
    refresh_backtest_after_policy_change(root=ROOT)


if __name__ == "__main__":
    main()
