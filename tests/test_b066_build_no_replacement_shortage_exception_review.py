from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B.B066_build_no_replacement_shortage_exception_review import (
    build_no_replacement_shortage_exception_review,
)


PREVIEW_COLUMNS = [
    "return_order_id",
    "sku",
    "amazon_return_disposition",
    "reused_token_id",
    "downstream_order_id",
    "downstream_order_date",
    "reused_token_allocation_rows",
    "reused_token_cogs_rows",
    "correction_apply_lane",
]

IMPACT_COLUMNS = ["return_order_id", "sku", "return_cogs_rows"]

TOKEN_COLUMNS = [
    "token_id",
    "seller_sku",
    "status",
    "allocated_order_id",
    "allocated_date",
    "received_date",
    "sort_rank",
    "lot_rank_num",
    "return_order_id",
    "last_return_order_id",
    "return_event_id",
    "last_return_event_id",
    "disposed_event_id",
    "disposed_date",
    "disposed_reason",
    "notes",
]

ALLOCATION_COLUMNS = ["order_id", "order_date", "allocation_date", "seller_sku", "token_id"]
COGS_COLUMNS = ["order_id", "seller_sku", "token_id"]


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_base(root: Path, *, downstream_date: str = "2026-02-23T11:23:29Z") -> None:
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        PREVIEW_COLUMNS,
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "reused_token_id": "BAD-RETURN-TOKEN",
                "downstream_order_id": "DOWNSTREAM-ORDER",
                "downstream_order_date": downstream_date,
                "reused_token_allocation_rows": "1",
                "reused_token_cogs_rows": "1",
                "correction_apply_lane": "no_replacement_token_protected_shortage_or_exception_review",
            }
        ],
    )
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_impact_preview.csv",
        IMPACT_COLUMNS,
        [{"return_order_id": "RETURN-ORDER", "sku": "SKU-A", "return_cogs_rows": "2"}],
    )
    _write_csv_rows(root / "out" / "token_allocations_live.csv", ALLOCATION_COLUMNS, [])
    _write_csv_rows(root / "out" / "token_cogs_ledger.csv", COGS_COLUMNS, [])


def _review_row(root: Path) -> dict[str, str]:
    result = build_no_replacement_shortage_exception_review(root=root, observed_utc="2026-06-04T10:00:00Z")
    review = result["review"]
    assert len(review) == 1
    return review.iloc[0].to_dict()


def test_true_no_replacement_shortage_when_clean_stock_was_used_before_sale(tmp_path: Path) -> None:
    _write_base(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "CLEAN-USED-BEFORE",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "OLDER-ORDER",
                "allocated_date": "2026-01-01T10:00:00Z",
                "received_date": "2025-12-01",
                "sort_rank": "1",
            },
            {
                "token_id": "BAD-RETURN-TOKEN",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "DOWNSTREAM-ORDER",
                "received_date": "2025-12-01",
            },
        ],
    )

    row = _review_row(tmp_path)

    assert row["review_label"] == "true_no_replacement_shortage"
    assert row["clean_stock_used_before_sale_count"] == "1"
    assert row["direct_replacement_swap_ready"] == "0"
    assert row["preview_live_write_allowed"] == "0"
    assert row["roi_or_restock_use_allowed"] == "0"


def test_available_before_token_becomes_mapping_gap_not_live_swap(tmp_path: Path) -> None:
    _write_base(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "CLEAN-AVAILABLE",
                "seller_sku": "SKU-A",
                "status": "available",
                "received_date": "2025-12-01",
                "sort_rank": "1",
            }
        ],
    )

    row = _review_row(tmp_path)

    assert row["review_label"] == "replacement_mapping_gap"
    assert row["candidate_token_id"] == "CLEAN-AVAILABLE"
    assert row["direct_replacement_swap_ready"] == "0"


def test_date_valid_token_already_used_later_stays_parked(tmp_path: Path) -> None:
    _write_base(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "CLEAN-USED-LATER",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "FUTURE-ORDER",
                "allocated_date": "2026-03-01T10:00:00Z",
                "received_date": "2025-12-01",
            }
        ],
    )

    row = _review_row(tmp_path)

    assert row["review_label"] == "date_valid_but_already_used_later"
    assert row["candidate_token_id"] == "CLEAN-USED-LATER"
    assert row["direct_replacement_swap_ready"] == "0"


def test_missing_downstream_date_creates_missing_date_proof(tmp_path: Path) -> None:
    _write_base(tmp_path, downstream_date="")
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "CLEAN-AVAILABLE",
                "seller_sku": "SKU-A",
                "status": "available",
                "received_date": "2025-12-01",
            }
        ],
    )

    row = _review_row(tmp_path)

    assert row["review_label"] == "missing_date_proof"
    assert row["direct_replacement_swap_ready"] == "0"


def test_bad_returned_token_is_never_chosen_as_replacement(tmp_path: Path) -> None:
    _write_base(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "BAD-RETURN-TOKEN",
                "seller_sku": "SKU-A",
                "status": "available",
                "received_date": "2025-12-01",
                "sort_rank": "1",
            }
        ],
    )

    row = _review_row(tmp_path)

    assert row["candidate_token_id"] != "BAD-RETURN-TOKEN"
    assert row["review_label"] == "true_no_replacement_shortage"
    assert row["direct_replacement_swap_ready"] == "0"
