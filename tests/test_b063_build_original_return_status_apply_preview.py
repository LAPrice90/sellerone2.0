from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B063_build_original_return_status_apply_preview as b063


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


SOURCE_COLUMNS = [
    "order_id",
    "sku",
    "unsafe_original_token_id",
    "review_lane",
    "review_readiness",
    "has_reusable_duplicate_token",
    "reusable_return_token_ids",
    "preview_live_write_allowed",
    "protected_before_apply",
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


def test_b063_previews_ready_original_return_status_repairs_without_live_write(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "unsafe_original_token_id": "TOKEN-CLOSED",
                "review_lane": "original_allocated_after_return_with_duplicate",
                "review_readiness": "blocked_needs_protected_review",
                "has_reusable_duplicate_token": "1",
                "reusable_return_token_ids": "TOKEN-DUP",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            },
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "unsafe_original_token_id": "TOKEN-UNSELLABLE",
                "review_lane": "original_allocated_after_return_no_duplicate",
                "review_readiness": "blocked_needs_protected_review",
                "has_reusable_duplicate_token": "0",
                "reusable_return_token_ids": "",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            },
        ],
        SOURCE_COLUMNS,
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

    result = b063.build_original_return_status_apply_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert len(preview) == 2
    assert set(preview["apply_preview_lane"]) == {"original_return_status_apply_preview_ready"}
    assert set(preview["target_status"]) == {"returned_complete", "unsellable"}
    assert set(preview["preview_live_write_allowed"]) == {"0"}
    assert set(preview["maintenance_required_before_apply"]) == {"1"}
    assert set(preview["requires_luke_live_apply"]) == {"1"}
    assert summary["ready_apply_rows"] == "2"
    assert summary["blocked_rows"] == "0"
    assert summary["live_write_allowed_rows"] == "0"
    assert summary["roi_or_restock_allowed_rows"] == "0"


def test_b063_blocks_unknown_lifecycle_marker_without_live_write(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_return_status_conflict_preview.csv",
        [
            {
                "order_id": "ORDER-3",
                "sku": "SKU-C",
                "unsafe_original_token_id": "TOKEN-UNKNOWN",
                "review_lane": "original_allocated_after_return_no_duplicate",
                "review_readiness": "blocked_needs_protected_review",
                "has_reusable_duplicate_token": "0",
                "reusable_return_token_ids": "",
                "preview_live_write_allowed": "0",
                "protected_before_apply": "1",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        SOURCE_COLUMNS,
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

    result = b063.build_original_return_status_apply_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert preview.loc[0, "apply_preview_lane"] == "original_return_status_apply_blocked_missing_return_lifecycle_marker"
    assert preview.loc[0, "block_reason"] == "missing_return_lifecycle_marker"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"
    assert summary["ready_apply_rows"] == "0"
    assert summary["blocked_rows"] == "1"
