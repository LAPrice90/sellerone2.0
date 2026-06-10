from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B058_build_disposition_conflict_preview as b058


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


SOURCE_COLUMNS = [
    "order_id",
    "sku",
    "proof_label",
    "diagnosis",
    "amazon_return_disposition",
    "amazon_return_status",
    "amazon_return_date",
    "refund_posted_date",
    "unsafe_original_token_ids",
    "reusable_return_token_ids",
    "return_cogs_token_ids",
    "repair_lane",
]

TOKEN_COLUMNS = [
    "token_id",
    "seller_sku",
    "status",
    "allocated_order_id",
    "return_order_id",
    "last_return_order_id",
    "notes",
]

RETURN_COGS_COLUMNS = ["return_event_id", "seller_sku", "token_id", "token_cost"]


def test_b058_previews_non_sellable_reusable_conflict_without_live_write(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "proof_label": "returned_unsellable_no_reuse",
                "diagnosis": "Amazon says the return was not sellable, but B has reusable-token evidence.",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "amazon_return_status": "Unit returned to inventory",
                "amazon_return_date": "2026-01-10T00:00:00Z",
                "refund_posted_date": "2026-01-09T00:00:00Z",
                "unsafe_original_token_ids": "TOKEN-ORIG",
                "reusable_return_token_ids": "TOKEN-REUSE",
                "return_cogs_token_ids": "TOKEN-REUSE",
                "repair_lane": "protected_disposition_conflict",
            }
        ],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-ORIG",
                "seller_sku": "SKU-A",
                "status": "returned_complete",
                "allocated_order_id": "ORDER-1",
                "return_order_id": "ORDER-1",
                "last_return_order_id": "ORDER-1",
                "notes": "return_unsellable:RET-1",
            },
            {
                "token_id": "TOKEN-REUSE",
                "seller_sku": "SKU-A",
                "status": "available",
                "allocated_order_id": "ORDER-LATER",
                "return_order_id": "",
                "last_return_order_id": "ORDER-1",
                "notes": "return_sellable_dup:RET-1",
            },
        ],
        TOKEN_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_return_ledger.csv",
        [{"return_event_id": "RET-1", "seller_sku": "SKU-A", "token_id": "TOKEN-REUSE", "token_cost": "2.50"}],
        RETURN_COGS_COLUMNS,
    )

    result = b058.build_disposition_conflict_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["preview_rows"] == "1"
    assert summary["with_reusable_token_rows"] == "1"
    assert summary["with_return_cogs_rows"] == "1"
    assert summary["allocated_reusable_token_rows"] == "1"
    assert summary["customer_damaged_rows"] == "1"
    assert preview.loc[0, "conflict_lane"] == "non_sellable_return_has_reusable_token_and_cogs"
    assert preview.loc[0, "reusable_return_token_allocated_order_ids"] == "TOKEN-REUSE:ORDER-LATER"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"
    assert preview.loc[0, "sellerboard_final_truth_allowed"] == "0"
    assert preview.loc[0, "protected_before_apply"] == "1"


def test_b058_ignores_non_target_lanes(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "proof_label": "returned_sellable_token_missing",
                "diagnosis": "Needs B009.",
                "amazon_return_disposition": "SELLABLE",
                "amazon_return_status": "Unit returned to inventory",
                "amazon_return_date": "2026-01-10T00:00:00Z",
                "refund_posted_date": "2026-01-09T00:00:00Z",
                "unsafe_original_token_ids": "",
                "reusable_return_token_ids": "",
                "return_cogs_token_ids": "",
                "repair_lane": "b009_order_aware_sellable_return",
            }
        ],
        SOURCE_COLUMNS,
    )

    result = b058.build_disposition_conflict_preview(root=tmp_path)
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert len(result["preview"]) == 0
    assert summary["status"] == "ok"
    assert summary["preview_rows"] == "0"
    assert summary["source_conflict_rows"] == "0"
