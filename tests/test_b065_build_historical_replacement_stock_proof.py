from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B.B065_build_historical_replacement_stock_proof import (
    build_historical_replacement_stock_proof,
)


PREVIEW_COLUMNS = [
    "return_order_id",
    "sku",
    "reused_token_id",
    "downstream_order_id",
    "downstream_order_date",
    "replacement_candidate_token_id",
    "replacement_candidate_received_date",
    "replacement_candidate_date_relation",
    "correction_apply_lane",
]

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


def _write_base(root: Path, *, downstream_date: str = "2026-02-01T10:00:00Z") -> None:
    _write_csv_rows(
        root / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        PREVIEW_COLUMNS,
        [
            {
                "return_order_id": "RETURN-ORDER",
                "sku": "SKU-A",
                "reused_token_id": "BAD-TOKEN",
                "downstream_order_id": "DOWNSTREAM-ORDER",
                "downstream_order_date": downstream_date,
                "replacement_candidate_token_id": "VISIBLE-CANDIDATE",
                "replacement_candidate_received_date": "2026-04-01",
                "replacement_candidate_date_relation": "after_downstream_order",
                "correction_apply_lane": "replacement_candidate_date_validation_required",
            }
        ],
    )
    _write_csv_rows(root / "out" / "token_allocations_live.csv", ALLOCATION_COLUMNS, [])
    _write_csv_rows(root / "out" / "token_cogs_ledger.csv", COGS_COLUMNS, [])


def _proof_row(root: Path) -> dict[str, str]:
    result = build_historical_replacement_stock_proof(root=root, observed_utc="2026-06-04T10:00:00Z")
    proof = result["proof"]
    assert len(proof) == 1
    return proof.iloc[0].to_dict()


def test_date_valid_currently_available_token_is_labelled_but_not_live_write(tmp_path: Path) -> None:
    _write_base(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "BAD-TOKEN",
                "seller_sku": "SKU-A",
                "status": "returned_pending",
                "received_date": "2026-01-01",
            },
            {
                "token_id": "CLEAN-BEFORE",
                "seller_sku": "SKU-A",
                "status": "available",
                "received_date": "2026-01-01",
                "sort_rank": "1",
            },
        ],
    )

    row = _proof_row(tmp_path)

    assert row["historical_replacement_label"] == "date_valid_currently_available"
    assert row["historical_candidate_token_id"] == "CLEAN-BEFORE"
    assert row["direct_replacement_swap_ready"] == "1"
    assert row["preview_live_write_allowed"] == "0"
    assert row["roi_or_restock_use_allowed"] == "0"


def test_date_valid_token_already_used_later_is_not_direct_swap_ready(tmp_path: Path) -> None:
    _write_base(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "CLEAN-USED-LATER",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "OTHER-ORDER",
                "allocated_date": "2026-03-01T09:00:00Z",
                "received_date": "2026-01-01",
                "sort_rank": "1",
            }
        ],
    )
    _write_csv_rows(
        tmp_path / "out" / "token_allocations_live.csv",
        ALLOCATION_COLUMNS,
        [
            {
                "order_id": "OTHER-ORDER",
                "order_date": "2026-03-01T09:00:00Z",
                "allocation_date": "2026-03-01T09:00:00Z",
                "seller_sku": "SKU-A",
                "token_id": "CLEAN-USED-LATER",
            }
        ],
    )

    row = _proof_row(tmp_path)

    assert row["historical_replacement_label"] == "date_valid_but_already_used_later"
    assert row["historical_candidate_token_id"] == "CLEAN-USED-LATER"
    assert row["direct_replacement_swap_ready"] == "0"


def test_replacement_arrived_after_sale_stays_blocked(tmp_path: Path) -> None:
    _write_base(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "CLEAN-LATE",
                "seller_sku": "SKU-A",
                "status": "available",
                "received_date": "2026-04-01",
            }
        ],
    )

    row = _proof_row(tmp_path)

    assert row["historical_replacement_label"] == "replacement_arrived_after_sale"
    assert row["historical_candidate_token_id"] == "CLEAN-LATE"
    assert row["direct_replacement_swap_ready"] == "0"


def test_missing_order_or_token_dates_create_missing_date_proof(tmp_path: Path) -> None:
    _write_base(tmp_path, downstream_date="")
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "MISSING-DATE",
                "seller_sku": "SKU-A",
                "status": "available",
                "received_date": "",
            }
        ],
    )

    row = _proof_row(tmp_path)

    assert row["historical_replacement_label"] == "missing_date_proof"
    assert row["direct_replacement_swap_ready"] == "0"


def test_bad_returned_token_is_never_chosen_as_its_own_replacement(tmp_path: Path) -> None:
    _write_base(tmp_path)
    _write_csv_rows(
        tmp_path / "out" / "token_ledger_live.csv",
        TOKEN_COLUMNS,
        [
            {
                "token_id": "BAD-TOKEN",
                "seller_sku": "SKU-A",
                "status": "available",
                "received_date": "2026-01-01",
                "sort_rank": "1",
            }
        ],
    )

    row = _proof_row(tmp_path)

    assert row["historical_candidate_token_id"] != "BAD-TOKEN"
    assert row["historical_replacement_label"] == "replacement_arrived_after_sale"
    assert row["direct_replacement_swap_ready"] == "0"
