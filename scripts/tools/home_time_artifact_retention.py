from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.tools.home_time_common import run_home_time_artifact_retention


def main() -> int:
    try:
        stats = run_home_time_artifact_retention(ROOT)
    except Exception as exc:
        payload = {"error": f"{type(exc).__name__}:{exc}"}
        print(json.dumps(payload, ensure_ascii=True))
        return 1
    print(json.dumps(stats, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

