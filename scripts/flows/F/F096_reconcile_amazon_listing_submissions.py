from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _latest_readback_by_draft(events_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if events_df.empty:
        return {}
    work = events_df.copy()
    work["_event_sort"] = pd.to_datetime(work.get("event_utc", ""), errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "event_id"], ascending=[True, True], kind="stable")
    latest: dict[str, dict[str, str]] = {}
    for _, row in work.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        draft_id = row_dict.get("draft_id", "")
        if draft_id:
            latest[draft_id] = row_dict
    return latest


def _reconciliation_status(readback: dict[str, str]) -> tuple[str, str]:
    status = _normalize_text(readback.get("readback_status", ""))
    asin_match = _normalize_text(readback.get("asin_match_status", ""))
    blocking = _normalize_text(readback.get("blocking_issue_count", ""))
    if status == "confirmed" and asin_match in {"match", "not_checked"} and blocking in {"", "0"}:
        return "confirmed_product_db_eligible", ""
    if status == "":
        return "pending_readback", "missing_readback_event"
    if status == "confirmed" and asin_match == "mismatch":
        return "blocked", "asin_mismatch"
    return "blocked", status or "readback_not_confirmed"


def _active_brand_approval_blocks(queue_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if queue_df.empty:
        return {}
    blocks: dict[str, dict[str, str]] = {}
    for _, row in queue_df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        draft_id = row_dict.get("draft_id", "")
        if not draft_id:
            continue
        approval_status = row_dict.get("approval_status", "")
        if approval_status in {"approval_cleared", "approved", "restriction_clear"}:
            continue
        blocks[draft_id] = row_dict
    return blocks


def _write_health(root: Path, *, observed_utc: str, confirmed_rows: int, blocked_rows: int, pending_rows: int) -> None:
    check_name = "amazon_listing_reconciliation"
    status = "fail" if blocked_rows > 0 else ("warn" if pending_rows > 0 else "ok")
    existing = read_f_contract_df(root, "amazon_listing_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    row = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": str(confirmed_rows),
                "notes": f"confirmed_rows={confirmed_rows};blocked_rows={blocked_rows};pending_rows={pending_rows}",
                "observed_utc": observed_utc,
                "source_path": str(root / "out" / "systems" / "F" / "history" / "amazon_listing_readback_events.csv"),
            }
        ]
    )
    write_f_contract_df(root, "amazon_listing_health", pd.concat([retained, row], ignore_index=True))


def reconcile_amazon_listing_submissions(
    *,
    root: Path | None = None,
    observed_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_f_path_contract().root
    ensure_f_directories(root=root_path)
    observed = observed_utc or _utc_now_iso()
    drafts_df = read_f_contract_df(root_path, "amazon_listing_drafts_live")
    readback_df = read_f_contract_df(root_path, "amazon_listing_readback_events")
    brand_queue_df = read_f_contract_df(root_path, "brand_approval_queue_live")
    latest_readback = _latest_readback_by_draft(readback_df)
    brand_blocks = _active_brand_approval_blocks(brand_queue_df)

    rows: list[dict[str, str]] = []
    for _, draft in drafts_df.iterrows():
        draft_row = {key: _normalize_text(value) for key, value in draft.to_dict().items()}
        if draft_row.get("draft_status", "") != "submitted_to_amazon" or draft_row.get("amazon_submission_status", "") != "submitted":
            continue
        draft_id = draft_row.get("draft_id", "")
        readback = latest_readback.get(draft_id, {})
        reconciliation_status, block_reason = _reconciliation_status(readback)
        brand_block = brand_blocks.get(draft_id, {})
        if brand_block:
            reconciliation_status = "blocked"
            block_reason = _normalize_text(brand_block.get("approval_status", "")) or "brand_approval_required"
        rows.append(
            {
                "observed_utc": observed,
                "draft_id": draft_id,
                "expected_seller_sku": draft_row.get("expected_seller_sku", ""),
                "asin": draft_row.get("asin", ""),
                "marketplace_id": draft_row.get("marketplace_id", ""),
                "submission_id": draft_row.get("amazon_submission_id", ""),
                "readback_status": readback.get("readback_status", ""),
                "asin_match_status": readback.get("asin_match_status", ""),
                "blocking_issue_count": readback.get("blocking_issue_count", ""),
                "reconciliation_status": reconciliation_status,
                "block_reason": block_reason,
                "updated_at_utc": observed,
                "candidate_id": draft_row.get("candidate_id", ""),
                "amazon_asin": readback.get("amazon_asin", ""),
                "http_status": readback.get("http_status", ""),
                "latest_readback_event_id": readback.get("event_id", ""),
                "latest_readback_utc": readback.get("event_utc", ""),
                "source_reference": (
                    "amazon_listing_drafts_live|amazon_listing_readback_events"
                    + ("|brand_approval_queue_live" if brand_block else "")
                ),
            }
        )
    out = pd.DataFrame(rows)
    finalized = write_f_contract_df(root_path, "amazon_listing_reconciliation_live", out)
    confirmed_rows = int((finalized["reconciliation_status"].map(_normalize_text) == "confirmed_product_db_eligible").sum()) if not finalized.empty else 0
    blocked_rows = int((finalized["reconciliation_status"].map(_normalize_text) == "blocked").sum()) if not finalized.empty else 0
    pending_rows = int((finalized["reconciliation_status"].map(_normalize_text) == "pending_readback").sum()) if not finalized.empty else 0
    _write_health(root_path, observed_utc=observed, confirmed_rows=confirmed_rows, blocked_rows=blocked_rows, pending_rows=pending_rows)
    print(
        {
            "status": "success",
            "reconciliation_rows": int(len(finalized.index)),
            "confirmed_rows": confirmed_rows,
            "blocked_rows": blocked_rows,
            "pending_rows": pending_rows,
        }
    )
    return finalized


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile submitted Amazon listing drafts from read-back events.")
    parser.add_argument("--root", default="")
    parser.add_argument("--observed-utc", default="")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    observed = _normalize_text(args.observed_utc) or None
    reconcile_amazon_listing_submissions(root=root, observed_utc=observed)


if __name__ == "__main__":
    main()
