from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B044_apply_return_token_reuse_repair as b044


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "amazon_return_disposition",
    "amazon_return_date",
    "returned_pending_token_ids",
    "reusable_return_token_ids",
    "return_cogs_token_ids",
    "repair_lane",
    "repair_readiness",
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
    "notes",
    "source",
    "source_batch_id",
    "source_order_key",
    "created_at",
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
]


def test_b044_refuses_without_protected_approval(tmp_path: Path) -> None:
    result = b044.apply_return_token_reuse_repair(root=tmp_path, approve_protected_b009_repair=False)

    assert result.status == "blocked_needs_approval"
    assert result.applied_rows == 0
    assert (tmp_path / "out" / "systems" / "B" / "refunds" / "b009_return_token_reuse_manifest.json").exists()


def test_b044_applies_order_aware_reuse_to_local_b009_shapes(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "SELLABLE",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "returned_pending_token_ids": "TOKEN-1",
                "reusable_return_token_ids": "",
                "return_cogs_token_ids": "",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "cost_per_unit": "4.25",
                "currency": "GBP",
                "status": "returned_pending",
                "received_date": "2026-04-01",
                "notes": "existing_note",
                "source": "purchase",
                "source_batch_id": "BATCH-1",
                "source_order_key": "PO-1",
                "created_at": "2026-04-01T09:00:00Z",
                "allocated_order_id": "ORDER-1",
                "allocated_date": "2026-05-19T09:00:00Z",
                "return_order_id": "ORDER-1",
                "return_date": "2026-05-21T10:00:00Z",
                "return_event_id": "REF-1",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
            }
        ],
        LEDGER_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "live" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "cost_per_unit": "4.25",
                "currency": "GBP",
                "status": "returned_pending",
                "received_date": "2026-04-01",
                "notes": "existing_note",
                "source": "purchase",
                "source_batch_id": "BATCH-1",
                "source_order_key": "PO-1",
                "created_at": "2026-04-01T09:00:00Z",
                "allocated_order_id": "ORDER-1",
                "allocated_date": "2026-05-19T09:00:00Z",
                "return_order_id": "ORDER-1",
                "return_date": "2026-05-21T10:00:00Z",
                "return_event_id": "REF-1",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
            }
        ],
        LEDGER_COLUMNS,
    )

    result = b044.apply_return_token_reuse_repair(
        root=tmp_path,
        approve_protected_b009_repair=True,
        observed_utc="2026-06-03T12:00:00Z",
    )

    assert result.status == "applied"
    assert result.token_rows_updated == 1
    assert result.created_token_rows == 1
    assert result.return_ledger_rows == 1
    assert result.stock_event_rows == 1
    assert result.snapshot_dir is not None
    assert (result.snapshot_dir / "token_ledger_live.csv").exists()

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    original = ledger[ledger["token_id"] == "TOKEN-1"].iloc[0]
    created = ledger[ledger["token_id"] != "TOKEN-1"].iloc[0]
    assert original["status"] == "returned_complete"
    assert "return_closed:" in original["notes"]
    assert original["last_return_order_id"] == "ORDER-1"
    assert created["status"] == "available"
    assert created["allocated_order_id"] == ""
    assert created["return_order_id"] == ""
    assert created["last_return_order_id"] == "ORDER-1"
    assert created["notes"].startswith("return_sellable_dup:")

    return_ledger = pd.read_csv(tmp_path / "out" / "token_return_ledger.csv", dtype=str).fillna("")
    assert len(return_ledger) == 1
    assert return_ledger.loc[0, "seller_sku"] == "SKU-A"
    assert return_ledger.loc[0, "token_id"] == created["token_id"]
    assert return_ledger.loc[0, "token_cost"] == "4.25"
    assert return_ledger.loc[0, "source"] == "amazon_customer_return_order_aware"

    events = pd.read_csv(tmp_path / "out" / "stock_adjustment_token_events.csv", dtype=str).fillna("")
    assert len(events) == 1
    assert events.loc[0, "disposition"] == "SELLABLE"
    assert events.loc[0, "applied_qty"] == "1"
    assert "order_aware_customer_return:ORDER-1" in events.loc[0, "note"]


def test_b044_completes_existing_stock_event_without_duplicate(tmp_path: Path) -> None:
    event_id = b044._event_id("ORDER-1", "SKU-A", "TOKEN-1", 1)
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "SELLABLE",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "returned_pending_token_ids": "TOKEN-1",
                "reusable_return_token_ids": "",
                "return_cogs_token_ids": "",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "cost_per_unit": "4.25",
                "currency": "GBP",
                "status": "returned_pending",
                "received_date": "2026-04-01",
                "notes": "existing_note",
                "source": "purchase",
                "source_batch_id": "BATCH-1",
                "source_order_key": "PO-1",
                "created_at": "2026-04-01T09:00:00Z",
                "allocated_order_id": "ORDER-1",
                "allocated_date": "2026-05-19T09:00:00Z",
                "return_order_id": "ORDER-1",
                "return_date": "2026-05-21T10:00:00Z",
                "return_event_id": "REF-1",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
            }
        ],
        LEDGER_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "stock_adjustment_token_events.csv",
        [
            {
                "event_id": event_id,
                "sku": "SKU-A",
                "event_date": "2026-05-21T10:00:00Z",
                "event_type": "CustomerReturns",
                "disposition": "SELLABLE",
                "quantity": "1",
                "applied_qty": "1",
                "status": "ok",
                "note": "order_aware_customer_return:ORDER-1",
                "event_ts": "2026-06-03T12:00:00Z",
            }
        ],
        b044.STOCK_EVENT_COLUMNS,
    )

    result = b044.apply_return_token_reuse_repair(
        root=tmp_path,
        approve_protected_b009_repair=True,
        observed_utc="2026-06-03T12:00:00Z",
    )

    assert result.status == "applied"
    assert result.applied_rows == 1
    assert result.return_ledger_rows == 1
    assert result.stock_event_rows == 0

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    assert set(ledger["status"].tolist()) == {"returned_complete", "available"}
    events = pd.read_csv(tmp_path / "out" / "stock_adjustment_token_events.csv", dtype=str).fillna("")
    assert len(events) == 1
    assert events.loc[0, "event_id"] == event_id


def test_b044_completes_existing_stock_and_return_events_without_duplicate(tmp_path: Path) -> None:
    event_id = b044._event_id("ORDER-1", "SKU-A", "TOKEN-1", 1)
    reusable_token_id = f"TOKEN-1-R{event_id}"
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "SELLABLE",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "returned_pending_token_ids": "TOKEN-1",
                "reusable_return_token_ids": "",
                "return_cogs_token_ids": "",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "cost_per_unit": "4.25",
                "currency": "GBP",
                "status": "returned_pending",
                "received_date": "2026-04-01",
                "notes": "existing_note",
                "source": "purchase",
                "source_batch_id": "BATCH-1",
                "source_order_key": "PO-1",
                "created_at": "2026-04-01T09:00:00Z",
                "allocated_order_id": "ORDER-1",
                "allocated_date": "2026-05-19T09:00:00Z",
                "return_order_id": "ORDER-1",
                "return_date": "2026-05-21T10:00:00Z",
                "return_event_id": "REF-1",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
            }
        ],
        LEDGER_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "stock_adjustment_token_events.csv",
        [
            {
                "event_id": event_id,
                "sku": "SKU-A",
                "event_date": "2026-05-21T10:00:00Z",
                "event_type": "CustomerReturns",
                "disposition": "SELLABLE",
                "quantity": "1",
                "applied_qty": "1",
                "status": "ok",
                "note": "order_aware_customer_return:ORDER-1",
                "event_ts": "2026-06-03T12:00:00Z",
            }
        ],
        b044.STOCK_EVENT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_return_ledger.csv",
        [
            {
                "return_event_id": event_id,
                "return_date": "2026-05-21T10:00:00Z",
                "seller_sku": "SKU-A",
                "token_id": reusable_token_id,
                "token_cost": "4.25",
                "currency": "GBP",
                "source": "amazon_customer_return_order_aware",
                "event_type": "CustomerReturns",
            }
        ],
        b044.RETURN_LEDGER_COLUMNS,
    )

    result = b044.apply_return_token_reuse_repair(
        root=tmp_path,
        approve_protected_b009_repair=True,
        observed_utc="2026-06-03T12:00:00Z",
    )

    assert result.status == "applied"
    assert result.applied_rows == 1
    assert result.return_ledger_rows == 0
    assert result.stock_event_rows == 0

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    created = ledger[ledger["token_id"] == reusable_token_id].iloc[0]
    assert created["status"] == "available"
    return_ledger = pd.read_csv(tmp_path / "out" / "token_return_ledger.csv", dtype=str).fillna("")
    assert len(return_ledger) == 1
    events = pd.read_csv(tmp_path / "out" / "stock_adjustment_token_events.csv", dtype=str).fillna("")
    assert len(events) == 1


def test_b044_blocks_active_b_owner_without_matching_maintenance(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "SELLABLE",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "returned_pending_token_ids": "TOKEN-1",
                "reusable_return_token_ids": "",
                "return_cogs_token_ids": "",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [{"token_id": "TOKEN-1", "seller_sku": "SKU-A", "status": "returned_pending", "return_order_id": "ORDER-1"}],
        ["token_id", "seller_sku", "status", "return_order_id"],
    )
    lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("B|pid=123|heartbeat=2026-06-03T17:00:00Z", encoding="utf-8")

    result = b044.apply_return_token_reuse_repair(
        root=tmp_path,
        approve_protected_b009_repair=True,
        observed_utc="2026-06-03T17:00:00Z",
    )

    assert result.status == "blocked_active_b_owner"
    assert result.applied_rows == 0


def test_b044_blocks_duplicate_reuse_proof(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "SELLABLE",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "returned_pending_token_ids": "TOKEN-1",
                "reusable_return_token_ids": "TOKEN-1-R",
                "return_cogs_token_ids": "",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "status": "returned_pending",
                "return_order_id": "ORDER-1",
                "return_date": "2026-05-21T10:00:00Z",
                "return_event_id": "REF-1",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "return_date", "return_event_id"],
    )

    result = b044.apply_return_token_reuse_repair(root=tmp_path, approve_protected_b009_repair=True)

    assert result.status == "blocked_no_rows_applied"
    assert result.applied_rows == 0
    assert any("duplicate reuse" in reason for reason in result.reasons)


def test_b044_blocks_non_pending_token_status(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "amazon_return_disposition": "SELLABLE",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "returned_pending_token_ids": "TOKEN-1",
                "reusable_return_token_ids": "",
                "return_cogs_token_ids": "",
                "repair_lane": "b009_order_aware_sellable_return",
                "repair_readiness": "ready_for_b009_order_aware_preview",
                "preview_live_write_allowed": "0",
                "roi_or_restock_use_allowed": "0",
                "sellerboard_final_truth_allowed": "0",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "return_order_id": "ORDER-1",
                "return_date": "2026-05-21T10:00:00Z",
                "return_event_id": "REF-1",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "return_date", "return_event_id"],
    )

    result = b044.apply_return_token_reuse_repair(root=tmp_path, approve_protected_b009_repair=True)

    assert result.status == "blocked_no_rows_applied"
    assert result.applied_rows == 0
    assert any("not returned_pending" in reason for reason in result.reasons)


def test_b044_restores_prior_b009_original_status_without_duplicate_tokens(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b009_return_token_reuse_applied.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "event_id": "B009-ORDER-1",
                "original_token_id": "TOKEN-1",
                "reusable_token_id": "TOKEN-1-R",
                "previous_status": "returned_pending",
                "original_new_status": "returned_complete",
                "reusable_new_status": "available",
                "return_date": "2026-05-21T10:00:00Z",
                "token_cost": "4.25",
                "currency": "GBP",
                "action": "closed_pending_token_and_created_reusable_return_token",
            }
        ],
        b044.APPLIED_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "cost_per_unit": "4.25",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-04-01",
                "notes": "",
                "source": "purchase",
                "source_batch_id": "BATCH-1",
                "source_order_key": "PO-1",
                "created_at": "2026-04-01T09:00:00Z",
                "allocated_order_id": "ORDER-1",
                "allocated_date": "2026-05-19T09:00:00Z",
                "return_order_id": "ORDER-1",
                "return_date": "2026-05-21T10:00:00Z",
                "return_event_id": "REF-1",
                "last_return_order_id": "ORDER-1",
                "last_return_date": "2026-05-21T10:00:00Z",
                "last_return_event_id": "REF-1",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
            },
            {
                "token_id": "TOKEN-1-R",
                "seller_sku": "SKU-A",
                "cost_per_unit": "4.25",
                "currency": "GBP",
                "status": "available",
                "received_date": "2026-04-01",
                "notes": "return_sellable_dup:B009-ORDER-1",
                "source": "purchase",
                "source_batch_id": "BATCH-1",
                "source_order_key": "PO-1",
                "created_at": "2026-04-01T09:00:00Z",
                "allocated_order_id": "",
                "allocated_date": "",
                "return_order_id": "",
                "return_date": "",
                "return_event_id": "",
                "last_return_order_id": "ORDER-1",
                "last_return_date": "2026-05-21T10:00:00Z",
                "last_return_event_id": "REF-1",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
            },
        ],
        LEDGER_COLUMNS,
    )

    result = b044.apply_return_token_reuse_repair(
        root=tmp_path,
        approve_protected_b009_repair=True,
        observed_utc="2026-06-03T12:10:00Z",
    )

    assert result.status == "applied"
    assert result.token_rows_updated == 1
    assert result.created_token_rows == 0
    assert result.return_ledger_rows == 0
    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    assert len(ledger.index) == 2
    original = ledger[ledger["token_id"] == "TOKEN-1"].iloc[0]
    reusable = ledger[ledger["token_id"] == "TOKEN-1-R"].iloc[0]
    assert original["status"] == "returned_complete"
    assert "return_closed:B009-ORDER-1" in original["notes"]
    assert reusable["status"] == "available"
