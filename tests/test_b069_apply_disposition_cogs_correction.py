from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B069_apply_disposition_cogs_correction as b069


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
    "cost_per_unit",
    "currency",
    "status",
    "received_date",
    "allocated_order_id",
    "allocated_date",
    "return_order_id",
    "return_date",
    "return_event_id",
    "last_return_order_id",
    "last_return_date",
    "last_return_event_id",
    "disposed_event_id",
    "disposed_date",
    "disposed_reason",
    "notes",
    "source",
    "source_batch_id",
    "source_order_key",
    "created_at",
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


def _approved_key() -> tuple[str, str, str, str]:
    return ("RETURN-1", "SKU-A", "LATER-1", "BAD-RETURN-1")


def _seed(tmp_path: Path, *, key: tuple[str, str, str, str] | None = None) -> tuple[str, str, str, str]:
    return_order, sku, downstream_order, reused_token = key or _approved_key()
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_disposition_correction_apply_preview.csv",
        [
            {
                "return_order_id": return_order,
                "sku": sku,
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "reused_token_id": reused_token,
                "downstream_order_id": downstream_order,
                "downstream_order_status": "Shipped",
                "correction_apply_lane": "no_replacement_token_protected_shortage_or_exception_review",
                "protected_decision_required": "1",
                "requires_luke_live_apply": "1",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    ledger_rows = [
        {
            "token_id": reused_token,
            "seller_sku": sku,
            "cost_per_unit": "2.50",
            "currency": "GBP",
            "status": "allocated",
            "received_date": "2026-01-01",
            "allocated_order_id": downstream_order,
            "allocated_date": "2026-02-01T10:01:00Z",
            "return_order_id": "",
            "return_date": "",
            "return_event_id": "",
            "last_return_order_id": return_order,
            "last_return_date": "2026-01-20T10:00:00Z",
            "last_return_event_id": "RETURN-EVENT-1",
            "disposed_event_id": "",
            "disposed_date": "",
            "disposed_reason": "",
            "notes": "return_sellable_dup:RETURN-EVENT-1",
            "source": "live_stock_backdate",
            "source_batch_id": "BATCH-1",
            "source_order_key": "",
            "created_at": "",
        }
    ]
    _write_csv(tmp_path / "out" / "token_ledger_live.csv", ledger_rows, LEDGER_COLUMNS)
    _write_csv(tmp_path / "out" / "systems" / "B" / "live" / "token_ledger_live.csv", ledger_rows, LEDGER_COLUMNS)
    alloc_rows = [
        {
            "order_id": downstream_order,
            "order_date": "2026-02-01T10:00:00Z",
            "seller_sku": sku,
            "token_id": reused_token,
            "token_cost": "2.50",
            "currency": "GBP",
            "allocation_date": "2026-02-01T10:01:00Z",
            "source_level": "live_allocation",
            "notes": "live_allocation",
        }
    ]
    _write_csv(tmp_path / "out" / "token_allocations_live.csv", alloc_rows, ALLOC_COLUMNS)
    _write_csv(tmp_path / "out" / "systems" / "B" / "live" / "token_allocations_live.csv", alloc_rows, ALLOC_COLUMNS)
    _write_csv(
        tmp_path / "out" / "token_cogs_ledger.csv",
        [
            {
                "order_id": downstream_order,
                "order_date": "2026-02-01T10:00:00Z",
                "seller_sku": sku,
                "token_id": reused_token,
                "token_cost": "2.50",
                "currency": "GBP",
                "allocation_date": "2026-02-01T10:01:00Z",
                "quantity": "1",
                "source": "token_allocations_live",
                "built_at": "2026-02-01T10:02:00Z",
                "vat_rate_pct": "20.0",
                "cogs_exvat": "2.50",
                "cogs_vat": "0.50",
                "cogs_total": "3.00",
            }
        ],
        COGS_COLUMNS,
    )
    return return_order, sku, downstream_order, reused_token


def test_b069_blocks_without_protected_approval(tmp_path: Path) -> None:
    key = _seed(tmp_path)

    result = b069.apply_disposition_cogs_correction(root=tmp_path, approved_keys={key})

    assert result.status == "blocked_needs_approval"
    assert result.applied_rows == 0


def test_b069_applies_allocated_only_cogs_correction_token(tmp_path: Path) -> None:
    key = _seed(tmp_path)

    result = b069.apply_disposition_cogs_correction(
        root=tmp_path,
        approve_protected_disposition_cogs_correction=True,
        observed_utc="2026-06-04T17:30:00Z",
        approved_keys={key},
    )

    assert result.status == "applied"
    assert result.applied_rows == 1
    assert result.created_token_rows == 1
    assert result.token_rows_updated == 1
    assert result.allocation_rows_updated == 1
    assert result.cogs_rows_updated == 1
    assert result.snapshot_dir is not None

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("").set_index("token_id")
    bad_token = key[3]
    correction_token = [token_id for token_id in ledger.index if token_id != bad_token][0]
    assert ledger.loc[bad_token, "status"] == "unsellable"
    assert ledger.loc[bad_token, "allocated_order_id"] == ""
    assert "non_sellable_return_correction_blocked" in ledger.loc[bad_token, "notes"]
    assert ledger.loc[correction_token, "status"] == "allocated"
    assert ledger.loc[correction_token, "allocated_order_id"] == key[2]
    assert ledger.loc[correction_token, "last_return_order_id"] == ""
    assert "return_sellable_dup" not in ledger.loc[correction_token, "notes"]
    assert "manager_cogs_correction_token" in ledger.loc[correction_token, "notes"]

    allocations = pd.read_csv(tmp_path / "out" / "token_allocations_live.csv", dtype=str).fillna("")
    cogs = pd.read_csv(tmp_path / "out" / "token_cogs_ledger.csv", dtype=str).fillna("")
    assert allocations.loc[0, "token_id"] == correction_token
    assert allocations.loc[0, "source_level"] == "manager_cogs_correction"
    assert cogs.loc[0, "token_id"] == correction_token
    assert cogs.loc[0, "cogs_exvat"] == "2.5"
    assert cogs.loc[0, "cogs_total"] == "3"


def test_b069_blocks_active_b_owner_without_matching_maintenance(tmp_path: Path) -> None:
    key = _seed(tmp_path)
    lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("B|pid=123|heartbeat=2026-06-04T17:00:00Z", encoding="utf-8")

    result = b069.apply_disposition_cogs_correction(
        root=tmp_path,
        approve_protected_disposition_cogs_correction=True,
        observed_utc="2026-06-04T17:30:00Z",
        approved_keys={key},
    )

    assert result.status == "blocked_active_b_owner"
    assert result.applied_rows == 0


def test_b069_blocks_unapproved_preview_rows(tmp_path: Path) -> None:
    key = _seed(tmp_path)

    result = b069.apply_disposition_cogs_correction(
        root=tmp_path,
        approve_protected_disposition_cogs_correction=True,
        observed_utc="2026-06-04T17:30:00Z",
        approved_keys={("OTHER", key[1], key[2], key[3])},
    )

    assert result.status == "blocked_validation_failed"
    assert result.applied_rows == 0
    assert any("unapproved" in reason or "missing" in reason for reason in result.reasons)
