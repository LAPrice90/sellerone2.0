from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_api_collection import run_listing_offer_collection  # noqa: E402


def main() -> None:
    raise SystemExit(run_listing_offer_collection())


if __name__ == "__main__":
    main()
