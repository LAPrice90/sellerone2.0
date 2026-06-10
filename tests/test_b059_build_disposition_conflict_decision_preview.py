from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B059_build_disposition_conflict_decision_preview as b059


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


SOURCE_COLUMNS = [
    "order_id",
    "sku",
    "amazon_return_disposition",
    "proof_label",
    "reusable_return_token_ids",
    "reusable_return_token_allocated_order_ids",
    "return_cogs_rows",
]


def test_b059_builds_downstream_protected_decision_preview_without_live_write(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_preview.csv",
        [
            {
                "order_id": "ORDER-RETURN",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "proof_label": "returned_unsellable_no_reuse",
                "reusable_return_token_ids": "TOKEN-REUSE",
                "reusable_return_token_allocated_order_ids": "TOKEN-REUSE:ORDER-LATER",
                "return_cogs_rows": "2",
            }
        ],
        SOURCE_COLUMNS,
    )

    result = b059.build_disposition_conflict_decision_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["preview_rows"] == "1"
    assert summary["protected_decision_rows"] == "1"
    assert summary["downstream_allocated_rows"] == "1"
    assert summary["with_return_cogs_rows"] == "1"
    assert preview.loc[0, "decision_lane"] == "downstream_allocated_non_sellable_reuse_with_cogs"
    assert preview.loc[0, "downstream_allocated_order_ids"] == "ORDER-LATER"
    assert preview.loc[0, "protected_decision_required"] == "1"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"
    assert preview.loc[0, "sellerboard_final_truth_allowed"] == "0"


def test_b059_keeps_unallocated_non_sellable_reuse_as_protected_decision(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_conflict_preview.csv",
        [
            {
                "order_id": "ORDER-RETURN",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "proof_label": "returned_unsellable_no_reuse",
                "reusable_return_token_ids": "TOKEN-REUSE",
                "reusable_return_token_allocated_order_ids": "",
                "return_cogs_rows": "0",
            }
        ],
        SOURCE_COLUMNS,
    )

    result = b059.build_disposition_conflict_decision_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["protected_decision_rows"] == "1"
    assert summary["downstream_allocated_rows"] == "0"
    assert preview.loc[0, "decision_lane"] == "unallocated_non_sellable_reuse"
    assert preview.loc[0, "protected_decision_required"] == "1"
