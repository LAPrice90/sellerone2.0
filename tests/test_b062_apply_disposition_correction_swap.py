from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B062_apply_disposition_correction_swap as b062


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


PREVIEW_COLUMNS = [
    "return_order_id",
    "sku",
    "amazon_return_disposition",
    "reused_token_id",
    "downstream_order_id",
    "downstream_order_status",
    "replacement_candidate_token_id",
    "replacement_candidate_cost",
    "replacement_candidate_currency",
    "correction_apply_lane",
    "protected_decision_required",
    "requires_luke_live_apply",
    "preview_live_write_allowed",
    "roi_or_restock_use_allowed",
    "sellerboard_final_truth_allowed",
]

LEDGER_COLUMNS = [
    "token_id",
    "seller_sku",
    "status",
    "allocated_order_id",
    "allocated_date",
    "last_return_order_id",
    "last_return_date",
    "notes",
    "disposed_date",
    "disposed_reason",
    "cost_per_unit",
    "currency",
]

ALLOC_COLUMNS = [
    "order_id",
    "order_date",
    "seller_sku",
    "token_id",
    "token_cost",
    "currency",
    "allocation_date",
    "source_level",
    "notes",
]

COGS_COLUMNS = [
    "order_id",
    "order_date",
    "seller_sku",
    "token_id",
    "token_cost",
    "currency",
    "allocation_date",
    "quantity",
    "source",
    "built_at",
    "vat_rate_pct",
    "cogs_exvat",
    "cogs_vat",
    "cogs_total",
]


def _seed_swap_ready(tmp_path: Path, *, duplicate_replacement: bool = False) -> None:
    preview_rows = [
        {
            "return_order_id": "RETURN-1",
            "sku": "SKU-A",
            "amazon_return_disposition": "CUSTOMER_DAMAGED",
            "reused_token_id": "BAD-1",
            "downstream_order_id": "LATER-1",
            "downstream_order_status": "Shipped",
            "replacement_candidate_token_id": "CLEAN-1",
            "replacement_candidate_cost": "2.50",
            "replacement_candidate_currency": "GBP",
            "correction_apply_lane": "shipped_order_replacement_swap_preview_ready",
            "protected_decision_required": "1",
            "requires_luke_live_apply": "1",
            "preview_live_write_allowed": "0",
            "roi_or_restock_use_allowed": "0",
            "sellerboard_final_truth_allowed": "0",
        }
    ]
    if duplicate_replacement:
        preview_rows.append({**preview_rows[0], "return_order_id": "RETURN-2", "reused_token_id": "BAD-2", "downstream_order_id": "LATER-2"})
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        preview_rows,
        PREVIEW_COLUMNS,
    )
    ledger_rows = [
        {
            "token_id": "BAD-1",
            "seller_sku": "SKU-A",
            "status": "allocated",
            "allocated_order_id": "LATER-1",
            "allocated_date": "2026-02-01T10:00:00Z",
            "last_return_order_id": "RETURN-1",
            "last_return_date": "2026-01-01",
            "notes": "return_sellable_dup:RET-1",
            "disposed_date": "",
            "disposed_reason": "",
            "cost_per_unit": "2.00",
            "currency": "GBP",
        },
        {
            "token_id": "CLEAN-1",
            "seller_sku": "SKU-A",
            "status": "available",
            "allocated_order_id": "",
            "allocated_date": "",
            "last_return_order_id": "",
            "last_return_date": "",
            "notes": "",
            "disposed_date": "",
            "disposed_reason": "",
            "cost_per_unit": "2.50",
            "currency": "GBP",
        },
    ]
    if duplicate_replacement:
        ledger_rows.append(
            {
                "token_id": "BAD-2",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "LATER-2",
                "allocated_date": "2026-02-01T11:00:00Z",
                "last_return_order_id": "RETURN-2",
                "last_return_date": "2026-01-01",
                "notes": "return_sellable_dup:RET-2",
                "disposed_date": "",
                "disposed_reason": "",
                "cost_per_unit": "2.00",
                "currency": "GBP",
            }
        )
    _write_csv(tmp_path / "out" / "token_ledger_live.csv", ledger_rows, LEDGER_COLUMNS)
    alloc_rows = [
        {
            "order_id": "LATER-1",
            "order_date": "2026-02-01T10:00:00Z",
            "seller_sku": "SKU-A",
            "token_id": "BAD-1",
            "token_cost": "2.00",
            "currency": "GBP",
            "allocation_date": "2026-02-01T10:01:00Z",
            "source_level": "live_allocation",
            "notes": "live_allocation",
        }
    ]
    if duplicate_replacement:
        alloc_rows.append({**alloc_rows[0], "order_id": "LATER-2", "token_id": "BAD-2"})
    _write_csv(tmp_path / "out" / "token_allocations_live.csv", alloc_rows, ALLOC_COLUMNS)
    cogs_rows = [
        {
            "order_id": "LATER-1",
            "order_date": "2026-02-01T10:00:00Z",
            "seller_sku": "SKU-A",
            "token_id": "BAD-1",
            "token_cost": "2.00",
            "currency": "GBP",
            "allocation_date": "2026-02-01T10:01:00Z",
            "quantity": "1",
            "source": "token_allocations_live",
            "built_at": "2026-02-01T10:02:00Z",
            "vat_rate_pct": "20.0",
            "cogs_exvat": "2.00",
            "cogs_vat": "0.40",
            "cogs_total": "2.40",
        }
    ]
    if duplicate_replacement:
        cogs_rows.append({**cogs_rows[0], "order_id": "LATER-2", "token_id": "BAD-2"})
    _write_csv(tmp_path / "out" / "token_cogs_ledger.csv", cogs_rows, COGS_COLUMNS)


def test_b062_blocks_without_protected_approval(tmp_path: Path) -> None:
    _seed_swap_ready(tmp_path)

    result = b062.apply_disposition_correction_swap(root=tmp_path)

    assert result.status == "blocked_needs_approval"
    assert result.applied_rows == 0


def test_b062_applies_swap_and_blocks_reused_token_with_snapshot(tmp_path: Path) -> None:
    _seed_swap_ready(tmp_path)

    result = b062.apply_disposition_correction_swap(
        root=tmp_path,
        approve_protected_disposition_correction_swap=True,
        observed_utc="2026-06-03T22:45:00Z",
    )

    assert result.status == "applied"
    assert result.applied_rows == 1
    assert result.token_rows_updated == 2
    assert result.allocation_rows_updated == 1
    assert result.cogs_rows_updated == 1
    assert result.snapshot_dir is not None
    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("").set_index("token_id")
    allocations = pd.read_csv(tmp_path / "out" / "token_allocations_live.csv", dtype=str).fillna("")
    cogs = pd.read_csv(tmp_path / "out" / "token_cogs_ledger.csv", dtype=str).fillna("")

    assert ledger.loc["BAD-1", "status"] == "unsellable"
    assert ledger.loc["BAD-1", "allocated_order_id"] == ""
    assert "non_sellable_return_correction_blocked" in ledger.loc["BAD-1", "notes"]
    assert ledger.loc["CLEAN-1", "status"] == "allocated"
    assert ledger.loc["CLEAN-1", "allocated_order_id"] == "LATER-1"
    assert allocations.loc[0, "token_id"] == "CLEAN-1"
    assert allocations.loc[0, "token_cost"] == "2.50"
    assert cogs.loc[0, "token_id"] == "CLEAN-1"
    assert cogs.loc[0, "cogs_exvat"] == "2.5"
    assert cogs.loc[0, "cogs_total"] == "3"


def test_b062_blocks_duplicate_replacement_token(tmp_path: Path) -> None:
    _seed_swap_ready(tmp_path, duplicate_replacement=True)

    result = b062.apply_disposition_correction_swap(
        root=tmp_path,
        approve_protected_disposition_correction_swap=True,
        observed_utc="2026-06-03T22:45:00Z",
    )

    assert result.status == "blocked_validation_failed"
    assert result.applied_rows == 0
    assert any("used more than once" in reason for reason in result.reasons)
