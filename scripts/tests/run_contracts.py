from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "scripts/tests/test_phase1_write_gate_contract.py",
    ]
    for test_path in tests:
        proc = subprocess.run([sys.executable, test_path], cwd=ROOT)
        if proc.returncode != 0:
            return proc.returncode
    print("PASS contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
