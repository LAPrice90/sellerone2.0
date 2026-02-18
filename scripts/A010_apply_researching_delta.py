"""
Wrapper for B010_apply_researching_delta.py so it runs in the A cycle.
Keeps process labeling consistent (A = inventory state).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    scripts = Path(__file__).resolve().parent
    target = scripts / "B010_apply_researching_delta.py"
    if not target.exists():
        print(f"[A010] missing: {target}")
        return 1
    print("[A010] running: B010_apply_researching_delta.py")
    result = subprocess.run([sys.executable, str(target)])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
