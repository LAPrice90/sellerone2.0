from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B061_build_disposition_correction_apply_preview as b061


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


IMPACT_COLUMNS = [
    "return_order_id",
    "sku",
    "amazon_return_disposition",
    "reusable_return_token_ids",
    "downstream_allocated_order_ids",
    "downstream_order_statuses",
]


def test_b061_builds_no_write_replacement_swap_preview_when_clean_token_exists(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "reusable_return_token_ids": "BAD-RETURN-TOKEN",
                "downstream_allocated_order_ids": "LATER-ORDER",
                "downstream_order_statuses": "LATER-ORDER:Shipped",
            }
        ],
        IMPACT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "BAD-RETURN-TOKEN",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "LATER-ORDER",
                "received_date": "2026-01-01",
                "cost_per_unit": "2.00",
                "currency": "GBP",
                "sort_rank": "2",
            },
            {
                "token_id": "CLEAN-REPLACEMENT",
                "seller_sku": "SKU-A",
                "status": "available",
                "allocated_order_id": "",
                "received_date": "2026-01-01",
                "cost_per_unit": "2.50",
                "currency": "GBP",
                "sort_rank": "1",
            },
        ],
        [
            "token_id",
            "seller_sku",
            "status",
            "allocated_order_id",
            "received_date",
            "cost_per_unit",
            "currency",
            "sort_rank",
        ],
    )
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        [
            {
                "order_id": "LATER-ORDER",
                "order_date": "2026-02-01T10:00:00Z",
                "seller_sku": "SKU-A",
                "token_id": "BAD-RETURN-TOKEN",
            }
        ],
        ["order_id", "order_date", "seller_sku", "token_id"],
    )
    _write_csv(
        tmp_path / "out" / "token_cogs_ledger.csv",
        [{"order_id": "LATER-ORDER", "seller_sku": "SKU-A", "token_id": "BAD-RETURN-TOKEN"}],
        ["order_id", "seller_sku", "token_id"],
    )

    result = b061.build_disposition_correction_apply_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["preview_rows"] == "1"
    assert summary["replacement_swap_preview_ready_rows"] == "1"
    assert preview.loc[0, "correction_apply_lane"] == "shipped_order_replacement_swap_preview_ready"
    assert preview.loc[0, "replacement_candidate_token_id"] == "CLEAN-REPLACEMENT"
    assert preview.loc[0, "replacement_candidate_date_relation"] == "on_or_before_downstream_order"
    assert preview.loc[0, "replacement_candidate_days_after_order"] == "-31"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "requires_luke_live_apply"] == "1"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"


def test_b061_keeps_row_protected_when_no_replacement_token_exists(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "reusable_return_token_ids": "BAD-RETURN-TOKEN",
                "downstream_allocated_order_ids": "LATER-ORDER",
                "downstream_order_statuses": "LATER-ORDER:Shipped",
            }
        ],
        IMPACT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "BAD-RETURN-TOKEN",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "LATER-ORDER",
                "received_date": "2026-01-01",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "received_date"],
    )
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        [
            {
                "order_id": "LATER-ORDER",
                "order_date": "2026-02-01T10:00:00Z",
                "seller_sku": "SKU-A",
                "token_id": "BAD-RETURN-TOKEN",
            }
        ],
        ["order_id", "order_date", "seller_sku", "token_id"],
    )

    result = b061.build_disposition_correction_apply_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["no_replacement_rows"] == "1"
    assert preview.loc[0, "correction_apply_lane"] == "no_replacement_token_protected_shortage_or_exception_review"
    assert preview.loc[0, "replacement_candidate_token_id"] == ""
    assert preview.loc[0, "replacement_candidate_date_relation"] == "no_replacement_candidate"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"


def test_b061_labels_after_order_replacement_candidate_as_date_validation(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "reusable_return_token_ids": "BAD-RETURN-TOKEN",
                "downstream_allocated_order_ids": "LATER-ORDER",
                "downstream_order_statuses": "LATER-ORDER:Shipped",
            }
        ],
        IMPACT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "CLEAN-LATE",
                "seller_sku": "SKU-A",
                "status": "available",
                "allocated_order_id": "",
                "received_date": "2026-02-05",
                "sort_rank": "1",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "received_date", "sort_rank"],
    )
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        [
            {
                "order_id": "LATER-ORDER",
                "order_date": "2026-02-01T10:00:00Z",
                "seller_sku": "SKU-A",
                "token_id": "BAD-RETURN-TOKEN",
            }
        ],
        ["order_id", "order_date", "seller_sku", "token_id"],
    )

    result = b061.build_disposition_correction_apply_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["replacement_date_validation_rows"] == "1"
    assert summary["replacement_candidate_after_order_rows"] == "1"
    assert preview.loc[0, "correction_apply_lane"] == "replacement_candidate_date_validation_required"
    assert preview.loc[0, "replacement_candidate_token_id"] == "CLEAN-LATE"
    assert preview.loc[0, "replacement_candidate_date_relation"] == "after_downstream_order"
    assert preview.loc[0, "replacement_candidate_days_after_order"] == "4"
    assert "after the downstream order" in preview.loc[0, "replacement_date_validation_reason"]
    assert preview.loc[0, "preview_live_write_allowed"] == "0"


def test_b061_does_not_reuse_same_replacement_candidate_twice(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        [
            {
                "return_order_id": "RETURN-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "reusable_return_token_ids": "BAD-1",
                "downstream_allocated_order_ids": "LATER-1",
                "downstream_order_statuses": "LATER-1:Shipped",
            },
            {
                "return_order_id": "RETURN-2",
                "sku": "SKU-A",
                "amazon_return_disposition": "DEFECTIVE",
                "reusable_return_token_ids": "BAD-2",
                "downstream_allocated_order_ids": "LATER-2",
                "downstream_order_statuses": "LATER-2:Shipped",
            },
        ],
        IMPACT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "CLEAN-1",
                "seller_sku": "SKU-A",
                "status": "available",
                "allocated_order_id": "",
                "received_date": "2026-01-01",
                "sort_rank": "1",
            },
            {
                "token_id": "CLEAN-2",
                "seller_sku": "SKU-A",
                "status": "available",
                "allocated_order_id": "",
                "received_date": "2026-01-01",
                "sort_rank": "2",
            },
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "received_date", "sort_rank"],
    )
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        [
            {"order_id": "LATER-1", "order_date": "2026-02-01T10:00:00Z", "seller_sku": "SKU-A", "token_id": "BAD-1"},
            {"order_id": "LATER-2", "order_date": "2026-02-01T11:00:00Z", "seller_sku": "SKU-A", "token_id": "BAD-2"},
        ],
        ["order_id", "order_date", "seller_sku", "token_id"],
    )

    result = b061.build_disposition_correction_apply_preview(root=tmp_path)
    preview = result["preview"]

    assert list(preview["replacement_candidate_token_id"]) == ["CLEAN-1", "CLEAN-2"]
