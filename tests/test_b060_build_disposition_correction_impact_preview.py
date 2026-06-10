from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B060_build_disposition_correction_impact_preview as b060


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


DECISION_COLUMNS = [
    "order_id",
    "sku",
    "amazon_return_disposition",
    "reusable_return_token_ids",
    "reusable_return_token_allocated_order_ids",
    "return_cogs_rows",
    "protected_decision_required",
]


def test_b060_builds_no_write_downstream_correction_impact_preview(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv",
        [
            {
                "order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "reusable_return_token_ids": "TOKEN-1",
                "reusable_return_token_allocated_order_ids": "TOKEN-1:LATER-ORDER",
                "return_cogs_rows": "2",
                "protected_decision_required": "1",
            }
        ],
        DECISION_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [{"token_id": "TOKEN-1", "seller_sku": "SKU-A", "status": "sold", "allocated_order_id": "LATER-ORDER"}],
        ["token_id", "seller_sku", "status", "allocated_order_id"],
    )
    _write_csv(
        tmp_path / "out" / "orders_all.csv",
        [{"amazon_order_id": "LATER-ORDER", "order_status": "Shipped"}],
        ["amazon_order_id", "order_status"],
    )
    _write_csv(
        tmp_path / "out" / "order_items_all.csv",
        [{"AmazonOrderId": "LATER-ORDER", "SellerSKU": "SKU-A"}],
        ["AmazonOrderId", "SellerSKU"],
    )

    result = b060.build_disposition_correction_impact_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["preview_rows"] == "1"
    assert summary["protected_decision_rows"] == "1"
    assert summary["downstream_allocated_rows"] == "1"
    assert summary["downstream_order_header_seen_rows"] == "1"
    assert summary["downstream_item_match_rows"] == "1"
    assert summary["with_return_cogs_rows"] == "1"
    assert preview.loc[0, "correction_impact_lane"] == "downstream_order_and_cogs_review_required"
    assert preview.loc[0, "downstream_order_statuses"] == "LATER-ORDER:Shipped"
    assert preview.loc[0, "protected_decision_required"] == "1"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"
    assert preview.loc[0, "sellerboard_final_truth_allowed"] == "0"


def test_b060_labels_missing_downstream_item_match_without_live_write(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_decision_preview.csv",
        [
            {
                "order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "reusable_return_token_ids": "TOKEN-1",
                "reusable_return_token_allocated_order_ids": "TOKEN-1:LATER-ORDER",
                "return_cogs_rows": "2",
                "protected_decision_required": "1",
            }
        ],
        DECISION_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "orders_all.csv",
        [{"amazon_order_id": "LATER-ORDER", "order_status": "Shipped"}],
        ["amazon_order_id", "order_status"],
    )
    _write_csv(
        tmp_path / "out" / "order_items_all.csv",
        [{"amazon_order_id": "LATER-ORDER", "seller_sku": "OTHER-SKU"}],
        ["amazon_order_id", "seller_sku"],
    )

    result = b060.build_disposition_correction_impact_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["downstream_item_match_rows"] == "0"
    assert preview.loc[0, "correction_impact_lane"] == "downstream_order_missing_item_match_cogs_review_required"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
