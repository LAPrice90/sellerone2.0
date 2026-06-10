from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B046_apply_original_return_status_repair as b046


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "unsafe_original_token_id",
    "unsafe_original_status",
    "review_lane",
    "review_readiness",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
]

LEDGER_COLUMNS = [
    "token_id",
    "seller_sku",
    "status",
    "notes",
    "allocated_order_id",
    "return_order_id",
    "last_return_order_id",
]


def test_b046_requires_protected_approval(tmp_path: Path) -> None:
    result = b046.apply_original_return_status_repair(root=tmp_path)

    assert result.status == "blocked_needs_approval"
    assert result.approved is False
    assert result.applied_rows == 0


def test_b046_blocks_active_b_owner_without_matching_maintenance_ready(tmp_path: Path) -> None:
    (tmp_path / "out" / "systems" / "B" / "live").mkdir(parents=True, exist_ok=True)
    (tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock").write_text("pid=123", encoding="utf-8")

    result = b046.apply_original_return_status_repair(
        root=tmp_path,
        approve_protected_original_return_status_repair=True,
        observed_utc="2026-06-03T13:30:00Z",
    )

    assert result.status == "blocked_active_b_owner"
    assert result.applied_rows == 0
    assert result.token_rows_updated == 0


def test_b046_repairs_original_return_statuses_with_snapshot(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "unsafe_original_token_id": "TOKEN-CLOSED",
                "unsafe_original_status": "allocated",
                "review_lane": "original_allocated_after_return_with_duplicate",
                "review_readiness": "blocked_needs_protected_review",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            },
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "unsafe_original_token_id": "TOKEN-UNSELLABLE",
                "unsafe_original_status": "allocated",
                "review_lane": "original_allocated_after_return_no_duplicate",
                "review_readiness": "blocked_needs_protected_review",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            },
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-CLOSED",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "notes": "return_closed:RET-1",
                "allocated_order_id": "ORDER-1",
                "return_order_id": "",
                "last_return_order_id": "ORDER-1",
            },
            {
                "token_id": "TOKEN-UNSELLABLE",
                "seller_sku": "SKU-B",
                "status": "allocated",
                "notes": "return_unsellable:RET-2",
                "allocated_order_id": "ORDER-2",
                "return_order_id": "",
                "last_return_order_id": "ORDER-2",
            },
        ],
        LEDGER_COLUMNS,
    )

    result = b046.apply_original_return_status_repair(
        root=tmp_path,
        approve_protected_original_return_status_repair=True,
        observed_utc="2026-06-03T13:30:00Z",
    )
    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    statuses = dict(zip(ledger["token_id"], ledger["status"]))
    applied = pd.read_csv(result.applied_path, dtype=str).fillna("")

    assert result.status == "applied"
    assert result.applied_rows == 2
    assert statuses["TOKEN-CLOSED"] == "returned_complete"
    assert statuses["TOKEN-UNSELLABLE"] == "unsellable"
    assert len(applied) == 2
    assert result.snapshot_dir is not None
    assert result.snapshot_dir.exists()


def test_b046_blocks_unknown_lifecycle_marker_and_preserves_ledger(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv",
        [
            {
                "order_id": "ORDER-3",
                "sku": "SKU-C",
                "unsafe_original_token_id": "TOKEN-UNKNOWN",
                "unsafe_original_status": "allocated",
                "review_lane": "original_allocated_after_return_no_duplicate",
                "review_readiness": "blocked_needs_protected_review",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-UNKNOWN",
                "seller_sku": "SKU-C",
                "status": "allocated",
                "notes": "manual-note",
                "allocated_order_id": "ORDER-3",
                "return_order_id": "",
                "last_return_order_id": "ORDER-3",
            }
        ],
        LEDGER_COLUMNS,
    )

    result = b046.apply_original_return_status_repair(
        root=tmp_path,
        approve_protected_original_return_status_repair=True,
        observed_utc="2026-06-03T13:30:00Z",
    )
    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")

    assert result.status == "blocked"
    assert result.applied_rows == 0
    assert ledger.loc[0, "status"] == "allocated"
