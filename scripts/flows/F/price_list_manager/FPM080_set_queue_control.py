from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.price_list_manager._io import normalize_text, read_csv, write_csv
from scripts.flows.F.price_list_manager._paths import ensure_manager_test_mode_dir
from scripts.flows.F.price_list_manager._schemas import MANAGER_HEALTH_COLUMNS, QUEUE_CONTROL_COLUMNS


VALID_CONTROL_STATES = {"normal", "paused", "prioritised"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_rank(value: object) -> str:
    raw = normalize_text(value)
    if not raw:
        return ""
    try:
        rank = int(float(raw))
    except ValueError as exc:
        raise ValueError("priority_rank must be a whole number") from exc
    if rank < 1:
        raise ValueError("priority_rank must be 1 or higher")
    return str(rank)


def set_queue_control(
    *,
    supplier_id: str,
    control_state: str,
    priority_rank: str = "",
    reason: str = "",
    root: Path | None = None,
    updated_at_utc: str | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    supplier = normalize_text(supplier_id)
    state = normalize_text(control_state).lower()
    if not supplier:
        raise ValueError("supplier_id is required")
    if state not in VALID_CONTROL_STATES:
        raise ValueError(f"control_state must be one of: {', '.join(sorted(VALID_CONTROL_STATES))}")

    updated_at = updated_at_utc or _utc_now_iso()
    controls_path = paths.test_mode_dir / "queue_controls.csv"
    health_path = paths.test_mode_dir / "health.csv"
    controls = read_csv(controls_path, QUEUE_CONTROL_COLUMNS)
    controls = controls[controls["supplier_id"].map(normalize_text) != supplier].copy()

    clean_rank = _clean_rank(priority_rank)
    if state == "prioritised" and not clean_rank:
        clean_rank = "1"

    if state != "normal":
        controls = pd.concat(
            [
                controls,
                pd.DataFrame(
                    [
                        {
                            "supplier_id": supplier,
                            "control_state": state,
                            "priority_rank": clean_rank,
                            "reason": normalize_text(reason),
                            "updated_at_utc": updated_at,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    controls = write_csv(controls_path, controls, QUEUE_CONTROL_COLUMNS)

    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health = write_csv(
        health_path,
        pd.concat(
            [
                existing_health,
                pd.DataFrame(
                    [
                        {
                            "check": "queue_control_update",
                            "status": "ok",
                            "value": supplier,
                            "notes": f"control_state={state};priority_rank={clean_rank}",
                            "observed_utc": updated_at,
                            "source_path": str(controls_path),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        ),
        MANAGER_HEALTH_COLUMNS,
    )

    summary = {
        "status": "success",
        "supplier_id": supplier,
        "control_state": state,
        "priority_rank": clean_rank,
        "control_rows": int(len(controls.index)),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "controls_path": str(controls_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Set a test-mode price-list queue control.")
    parser.add_argument("--supplier-id", required=True)
    parser.add_argument("--control-state", required=True, choices=sorted(VALID_CONTROL_STATES))
    parser.add_argument("--priority-rank", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--root", default=None)
    parser.add_argument("--updated-at-utc", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    set_queue_control(
        supplier_id=args.supplier_id,
        control_state=args.control_state,
        priority_rank=args.priority_rank,
        reason=args.reason,
        root=root,
        updated_at_utc=args.updated_at_utc,
    )


if __name__ == "__main__":
    main()
