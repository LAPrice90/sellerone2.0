from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B045_build_original_return_status_conflict_preview as b045


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


REPAIR_COLUMNS = [
    "order_id",
    "sku",
    "diagnosis",
    "repair_lane",
    "repair_readiness",
    "unsafe_original_token_ids",
    "reusable_return_token_ids",
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


def test_b045_splits_original_conflict_with_reusable_duplicate(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "diagnosis": "Original returned token has a live status.",
                "repair_lane": "protected_original_return_status_conflict",
                "repair_readiness": "blocked_needs_protected_review",
                "unsafe_original_token_ids": "TOKEN-ORIG",
                "reusable_return_token_ids": "TOKEN-DUP",
            }
        ],
        REPAIR_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-ORIG",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "notes": "return_closed:RET-1",
                "allocated_order_id": "ORDER-2",
                "return_order_id": "",
                "last_return_order_id": "ORDER-1",
            },
            {
                "token_id": "TOKEN-DUP",
                "seller_sku": "SKU-A",
                "status": "available",
                "notes": "return_sellable_dup:RET-1",
                "allocated_order_id": "",
                "return_order_id": "",
                "last_return_order_id": "ORDER-1",
            },
        ],
        LEDGER_COLUMNS,
    )

    result = b045.build_original_return_status_conflict_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert len(preview) == 1
    assert preview.loc[0, "review_lane"] == "original_allocated_after_return_with_duplicate"
    assert preview.loc[0, "unsafe_original_token_id"] == "TOKEN-ORIG"
    assert preview.loc[0, "reusable_return_token_ids"] == "TOKEN-DUP"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "protected_before_apply"] == "1"
    assert summary["with_reusable_duplicate_rows"] == "1"
    assert summary["without_reusable_duplicate_rows"] == "0"


def test_b045_splits_original_conflict_without_reusable_duplicate(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "diagnosis": "Original returned token has a live status.",
                "repair_lane": "protected_original_return_status_conflict",
                "repair_readiness": "blocked_needs_protected_review",
                "unsafe_original_token_ids": "TOKEN-ORIG-2",
                "reusable_return_token_ids": "",
            }
        ],
        REPAIR_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-ORIG-2",
                "seller_sku": "SKU-B",
                "status": "allocated",
                "notes": "return_unsellable:RET-2",
                "allocated_order_id": "ORDER-3",
                "return_order_id": "",
                "last_return_order_id": "ORDER-2",
            }
        ],
        LEDGER_COLUMNS,
    )

    result = b045.build_original_return_status_conflict_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert len(preview) == 1
    assert preview.loc[0, "review_lane"] == "original_allocated_after_return_no_duplicate"
    assert preview.loc[0, "unsafe_original_token_id"] == "TOKEN-ORIG-2"
    assert preview.loc[0, "has_reusable_duplicate_token"] == "0"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"
    assert summary["with_reusable_duplicate_rows"] == "0"
    assert summary["without_reusable_duplicate_rows"] == "1"
