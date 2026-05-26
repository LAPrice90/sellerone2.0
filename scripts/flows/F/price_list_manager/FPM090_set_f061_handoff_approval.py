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
from scripts.flows.F.price_list_manager._schemas import F061_HANDOFF_APPROVAL_COLUMNS, MANAGER_HEALTH_COLUMNS


VALID_APPROVAL_STATES = {"approved", "revoked"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def set_f061_handoff_approval(
    *,
    supplier_id: str,
    batch_id: str,
    approval_state: str,
    approved_by: str = "operator",
    reason: str = "",
    expires_at_utc: str = "",
    root: Path | None = None,
    approved_at_utc: str | None = None,
) -> dict[str, object]:
    paths = ensure_manager_test_mode_dir(root=root)
    supplier = normalize_text(supplier_id)
    batch = normalize_text(batch_id)
    state = normalize_text(approval_state).lower()
    if not supplier:
        raise ValueError("supplier_id is required")
    if not batch:
        raise ValueError("batch_id is required")
    if state not in VALID_APPROVAL_STATES:
        raise ValueError(f"approval_state must be one of: {', '.join(sorted(VALID_APPROVAL_STATES))}")

    observed = approved_at_utc or _utc_now_iso()
    approvals_path = paths.test_mode_dir / "f061_handoff_approvals.csv"
    health_path = paths.test_mode_dir / "health.csv"
    approval_id = f"handoff_approval_{supplier}_{batch}_{observed.replace('-', '').replace(':', '')}"
    row = {
        "approval_id": approval_id,
        "supplier_id": supplier,
        "batch_id": batch,
        "approval_state": state,
        "approved_by": normalize_text(approved_by) or "operator",
        "approved_at_utc": observed,
        "expires_at_utc": normalize_text(expires_at_utc),
        "reason": normalize_text(reason),
    }

    approvals = read_csv(approvals_path, F061_HANDOFF_APPROVAL_COLUMNS)
    approvals = write_csv(
        approvals_path,
        pd.concat([approvals, pd.DataFrame([row])], ignore_index=True),
        F061_HANDOFF_APPROVAL_COLUMNS,
    )

    existing_health = read_csv(health_path, MANAGER_HEALTH_COLUMNS)
    health = write_csv(
        health_path,
        pd.concat(
            [
                existing_health,
                pd.DataFrame(
                    [
                        {
                            "check": "f061_handoff_approval_recorded",
                            "status": "ok",
                            "value": state,
                            "notes": f"supplier_id={supplier};batch_id={batch};approval_id={approval_id}",
                            "observed_utc": observed,
                            "source_path": str(approvals_path),
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
        "approval_id": approval_id,
        "supplier_id": supplier,
        "batch_id": batch,
        "approval_state": state,
        "approval_rows": int(len(approvals.index)),
        "health_fail_rows": int((health["status"].map(lambda value: normalize_text(value).lower()) == "fail").sum()),
        "approvals_path": str(approvals_path),
    }
    print(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a test-mode F061 handoff approval.")
    parser.add_argument("--supplier-id", required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--approval-state", required=True, choices=sorted(VALID_APPROVAL_STATES))
    parser.add_argument("--approved-by", default="operator")
    parser.add_argument("--reason", default="")
    parser.add_argument("--expires-at-utc", default="")
    parser.add_argument("--approved-at-utc", default=None)
    parser.add_argument("--root", default=None)
    args = parser.parse_args()

    root = Path(args.root) if args.root else None
    set_f061_handoff_approval(
        supplier_id=args.supplier_id,
        batch_id=args.batch_id,
        approval_state=args.approval_state,
        approved_by=args.approved_by,
        reason=args.reason,
        expires_at_utc=args.expires_at_utc,
        root=root,
        approved_at_utc=args.approved_at_utc,
    )


if __name__ == "__main__":
    main()
