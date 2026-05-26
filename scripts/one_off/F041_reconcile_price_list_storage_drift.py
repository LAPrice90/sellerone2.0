from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager.FPM129_storage_drift_guard import (
    parse_contract_list,
    run_storage_drift_check,
    utc_now_iso,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diff or reconcile F price-list runtime SQL tables from fresher CSV contracts."
    )
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--contracts", default="")
    parser.add_argument("--sqlite-path", default=None)
    parser.add_argument("--observed-utc", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    observed = args.observed_utc or utc_now_iso()
    summary = run_storage_drift_check(
        root=Path(args.root),
        contracts=parse_contract_list(args.contracts),
        observed_utc=observed,
        apply=bool(args.apply),
        sqlite_path=args.sqlite_path,
        require_sql_mode=False,
        backup=bool(args.apply) and not bool(args.no_backup),
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, indent=2, sort_keys=True))
    if summary["status"] == "blocked_storage_drift":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
