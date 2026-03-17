"""
Wrapper for B010_apply_researching_delta.py so it runs in the A cycle.
Keeps process labeling consistent (A = inventory state).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BOOT_ROOT = Path(__file__).resolve().parents[3]
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

try:
    from scripts.core.script_locator import resolve_script_path
except ModuleNotFoundError:
    from core.script_locator import resolve_script_path


def main() -> int:
    scripts = Path(__file__).resolve().parents[3] / "scripts"
    target = resolve_script_path(scripts, "B010_apply_researching_delta.py")
    if not target.exists():
        print(f"[A010] missing: {target}")
        return 1
    print("[A010] running: B010_apply_researching_delta.py")
    result = subprocess.run([sys.executable, str(target)])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

