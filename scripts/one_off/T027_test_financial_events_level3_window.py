"""
One-click runner for a fixed posted window for Level 3 financial events.
"""

import os
import runpy
from pathlib import Path


POSTED_AFTER = "2025-12-15T00:00:00Z"
POSTED_BEFORE = "2025-12-27T23:59:59Z"


def main() -> None:
    os.environ["FIN_L3_CLEAN"] = "1"
    os.environ["FIN_L3_POSTED_AFTER"] = POSTED_AFTER
    os.environ["FIN_L3_POSTED_BEFORE"] = POSTED_BEFORE

    runner_path = Path(__file__).resolve().parent / "B003_run_financial_events_level3.py"
    runpy.run_path(str(runner_path), run_name="__main__")


if __name__ == "__main__":
    main()
