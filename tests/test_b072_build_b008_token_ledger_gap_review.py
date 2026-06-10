from pathlib import Path

import pandas as pd

from scripts.flows.B import B072_build_b008_token_ledger_gap_review as b072


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_b072_classifies_b057_missing_ledger_token_without_live_use(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "allocation_token_ids": "MANAGER-CORR-SKU-A-B057-ORDER-1-0001",
                "reproof_lane": "token_ledger_gap",
            }
        ],
        ["order_id", "sku", "allocation_token_ids", "reproof_lane"],
    )
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        [
            {
                "order_id": "ORDER-1",
                "seller_sku": "SKU-A",
                "token_id": "MANAGER-CORR-SKU-A-B057-ORDER-1-0001",
            }
        ],
        ["order_id", "seller_sku", "token_id"],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [],
        ["token_id"],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_sale_allocation_repair_applied.csv",
        [{"new_token_id": "MANAGER-CORR-SKU-A-B057-ORDER-1-0001"}],
        ["new_token_id"],
    )

    result = b072.build_b008_token_ledger_gap_review(root=tmp_path)
    review = result["review"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert len(review) == 1
    assert review.loc[0, "gap_label"] == "b057_allocation_token_missing_from_ledger"
    assert review.loc[0, "manager_state"] == "protected_ledger_alignment_needed"
    assert review.loc[0, "preview_live_write_allowed"] == "0"
    assert review.loc[0, "roi_or_restock_use_allowed"] == "0"
    assert summary["status"] == "ok"
    assert summary["protected_ledger_alignment_rows"] == "1"


def test_b072_marks_stale_preview_when_token_is_now_visible(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "allocation_token_ids": "TOKEN-1", "reproof_lane": "token_ledger_gap"}],
        ["order_id", "sku", "allocation_token_ids", "reproof_lane"],
    )
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        [{"order_id": "ORDER-1", "seller_sku": "SKU-A", "token_id": "TOKEN-1"}],
        ["order_id", "seller_sku", "token_id"],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [{"token_id": "TOKEN-1"}],
        ["token_id"],
    )

    result = b072.build_b008_token_ledger_gap_review(root=tmp_path)
    review = result["review"]

    assert review.loc[0, "gap_label"] == "stale_preview_token_now_visible"
    assert review.loc[0, "manager_state"] == "retest_b042"
    assert review.loc[0, "protected_before_apply"] == "0"

