from __future__ import annotations

import pandas as pd

from scripts.flows.B import B007_allocate_tokens_live as b007


def test_reconcile_token_ledger_with_allocations_marks_allocated_rows():
    token_df = pd.DataFrame(
        [
            {
                "token_id": "tok-1",
                "seller_sku": "SKU-1",
                "status": "available",
                "allocated_order_id": "",
                "allocated_date": "",
            },
            {
                "token_id": "tok-2",
                "seller_sku": "SKU-1",
                "status": "available",
                "allocated_order_id": "",
                "allocated_date": "",
            },
        ]
    )
    alloc_df = pd.DataFrame(
        [
            {
                "token_id": "tok-1",
                "order_id": "ORDER-1",
                "order_date": "2026-04-03T12:00:00Z",
            }
        ]
    )

    reconciled, count = b007._reconcile_token_ledger_with_allocations(token_df, alloc_df)

    assert count == 1
    row = reconciled.loc[reconciled["token_id"] == "tok-1"].iloc[0]
    assert row["status"] == "allocated"
    assert row["allocated_order_id"] == "ORDER-1"
    assert row["allocated_date"] == "2026-04-03T12:00:00Z"
    untouched = reconciled.loc[reconciled["token_id"] == "tok-2"].iloc[0]
    assert untouched["status"] == "available"


def test_reconcile_token_ledger_preserves_existing_allocation_fields():
    token_df = pd.DataFrame(
        [
            {
                "token_id": "tok-1",
                "seller_sku": "SKU-1",
                "status": "available",
                "allocated_order_id": "KEEP-ME",
                "allocated_date": "2026-04-02T10:00:00Z",
            }
        ]
    )
    alloc_df = pd.DataFrame(
        [
            {
                "token_id": "tok-1",
                "order_id": "OTHER-ORDER",
                "order_date": "2026-04-03T12:00:00Z",
            }
        ]
    )

    reconciled, count = b007._reconcile_token_ledger_with_allocations(token_df, alloc_df)

    assert count == 1
    row = reconciled.iloc[0]
    assert row["status"] == "allocated"
    assert row["allocated_order_id"] == "KEEP-ME"
    assert row["allocated_date"] == "2026-04-02T10:00:00Z"


def test_reconcile_token_ledger_does_not_reallocate_return_lifecycle_tokens():
    token_df = pd.DataFrame(
        [
            {
                "token_id": "tok-returned",
                "seller_sku": "SKU-1",
                "status": "returned_complete",
                "allocated_order_id": "ORDER-OLD",
                "allocated_date": "2026-04-02T10:00:00Z",
                "last_return_order_id": "ORDER-OLD",
            },
            {
                "token_id": "tok-research",
                "seller_sku": "SKU-1",
                "status": "research_pending",
                "allocated_order_id": "ORDER-OLD",
                "allocated_date": "2026-04-02T10:00:00Z",
                "last_return_order_id": "ORDER-OLD",
            },
            {
                "token_id": "tok-available-return",
                "seller_sku": "SKU-1",
                "status": "available",
                "allocated_order_id": "",
                "allocated_date": "",
                "last_return_order_id": "ORDER-OLD",
            },
        ]
    )
    alloc_df = pd.DataFrame(
        [
            {"token_id": "tok-returned", "order_id": "ORDER-OLD", "order_date": "2026-04-03T12:00:00Z"},
            {"token_id": "tok-research", "order_id": "ORDER-OLD", "order_date": "2026-04-03T12:00:00Z"},
            {"token_id": "tok-available-return", "order_id": "ORDER-NEW", "order_date": "2026-04-04T12:00:00Z"},
        ]
    )

    reconciled, count = b007._reconcile_token_ledger_with_allocations(token_df, alloc_df)

    assert count == 1
    returned = reconciled.loc[reconciled["token_id"] == "tok-returned"].iloc[0]
    research = reconciled.loc[reconciled["token_id"] == "tok-research"].iloc[0]
    reusable = reconciled.loc[reconciled["token_id"] == "tok-available-return"].iloc[0]
    assert returned["status"] == "returned_complete"
    assert research["status"] == "research_pending"
    assert reusable["status"] == "allocated"
    assert reusable["allocated_order_id"] == "ORDER-NEW"


def test_build_shortage_by_sku_includes_zero_available_skus():
    order_df = pd.DataFrame(
        [
            {"SKU": "SKU-1", "remaining_qty": 3},
            {"SKU": "SKU-2", "remaining_qty": 2},
        ]
    )
    new_allocations = [
        {"seller_sku": "SKU-2", "quantity": 1},
    ]

    shortages = b007._build_shortage_by_sku(order_df, new_allocations, {"SKU-1": 0, "SKU-2": 0})

    assert shortages == {"SKU-1": 3, "SKU-2": 1}


def test_build_shortage_by_sku_subtracts_research_pending():
    order_df = pd.DataFrame(
        [
            {"SKU": "SKU-1", "remaining_qty": 4},
        ]
    )

    shortages = b007._build_shortage_by_sku(order_df, [], {"SKU-1": 2})

    assert shortages == {"SKU-1": 2}


def test_build_shortage_classification_rows_splits_root_causes():
    shortages = {
        "LEGACY-PARTIAL": 1,
        "RUNTIME-PENDING": 2,
        "LIVE-SHORT": 1,
    }
    order_df = pd.DataFrame(
        [
            {"SKU": "LEGACY-PARTIAL", "remaining_qty": 1, "lvl": "3"},
            {"SKU": "RUNTIME-PENDING", "remaining_qty": 2, "lvl": "1"},
            {"SKU": "LIVE-SHORT", "remaining_qty": 1, "lvl": "1"},
        ]
    )
    token_df = pd.DataFrame(
        [
            {
                "seller_sku": "LEGACY-PARTIAL",
                "status": "allocated",
                "source": "live_stock_backdate",
                "notes": "live_stock_backdate",
            },
            {
                "seller_sku": "LIVE-SHORT",
                "status": "allocated",
                "source": "stock_receipt",
                "notes": "",
            },
        ]
    )
    backdate = pd.DataFrame(
        [
            {
                "seller_sku": "LEGACY-PARTIAL",
                "required_qty": "16",
                "built_qty": "15",
                "note": "partial",
            }
        ]
    )
    adjustments = pd.DataFrame(
        [
            {
                "sku": "RUNTIME-PENDING",
                "status": "partial",
                "note": "insufficient_returned_pending",
            }
        ]
    )

    rows = b007._build_shortage_classification_rows(
        shortages,
        order_df,
        token_df,
        token_backdate_summary=backdate,
        stock_adjustment_events=adjustments,
        stock_events_exists=False,
    )
    by_sku = {row["seller_sku"]: row for row in rows}

    assert by_sku["LEGACY-PARTIAL"]["shortage_class"] == "legacy_baseline_gap"
    assert by_sku["RUNTIME-PENDING"]["shortage_class"] == "runtime_reproof_pending"
    assert by_sku["LIVE-SHORT"]["shortage_class"] == "true_live_shortage"


def test_build_shortage_classification_ignores_cleared_adjustment_retry():
    shortages = {
        "RUNTIME-CLEARED": 1,
    }
    order_df = pd.DataFrame(
        [
            {"SKU": "RUNTIME-CLEARED", "remaining_qty": 1, "lvl": "1"},
        ]
    )
    token_df = pd.DataFrame(
        [
            {
                "seller_sku": "RUNTIME-CLEARED",
                "status": "allocated",
                "source": "stock_receipt",
                "notes": "",
            },
        ]
    )
    adjustments = pd.DataFrame(
        [
            {
                "sku": "RUNTIME-CLEARED",
                "event_id": "adjust-1",
                "quantity": "1",
                "applied_qty": "0",
                "status": "partial",
                "note": "insufficient_returned_pending",
            },
            {
                "sku": "RUNTIME-CLEARED",
                "event_id": "adjust-1-retry2",
                "quantity": "1",
                "applied_qty": "1",
                "status": "ok",
                "note": "reapply_partial:adjust-1",
            },
        ]
    )

    rows = b007._build_shortage_classification_rows(
        shortages,
        order_df,
        token_df,
        stock_adjustment_events=adjustments,
        stock_events_exists=True,
    )

    assert rows[0]["shortage_class"] == "true_live_shortage"
    assert "available_tokens=0;research_pending_tokens=0" in rows[0]["evidence_note"]


def test_release_canceled_order_allocations_releases_when_not_in_current_demand():
    token_df = pd.DataFrame(
        [
            {
                "token_id": "tok-cancel",
                "seller_sku": "SKU-1",
                "status": "allocated",
                "allocated_order_id": "ORDER-CANCEL",
                "allocated_date": "2026-04-10T10:00:00Z",
                "notes": "",
            },
            {
                "token_id": "tok-live",
                "seller_sku": "SKU-1",
                "status": "allocated",
                "allocated_order_id": "ORDER-LIVE",
                "allocated_date": "2026-04-11T10:00:00Z",
                "notes": "",
            },
        ]
    )
    alloc_df = pd.DataFrame(
        [
            {
                "order_id": "ORDER-CANCEL",
                "seller_sku": "SKU-1",
                "quantity": "1",
                "token_id": "tok-cancel",
                "allocation_date": "2026-04-10T10:00:00Z",
            },
            {
                "order_id": "ORDER-LIVE",
                "seller_sku": "SKU-1",
                "quantity": "1",
                "token_id": "tok-live",
                "allocation_date": "2026-04-11T10:00:00Z",
            },
        ]
    )

    updated_tokens, remaining_alloc, events, released_units = b007._release_canceled_order_allocations(
        token_df,
        alloc_df,
        demand_keys={("ORDER-LIVE", "SKU-1")},
        canceled_order_ids={"ORDER-CANCEL"},
        now_iso="2026-04-22T13:30:00Z",
    )

    assert released_units == 1
    assert len(events.index) == 1
    assert events.iloc[0]["order_id"] == "ORDER-CANCEL"
    cancel_row = updated_tokens.loc[updated_tokens["token_id"] == "tok-cancel"].iloc[0]
    assert cancel_row["status"] == "available"
    assert cancel_row["allocated_order_id"] == ""
    assert "canceled_order_release:2026-04-22T13:30:00Z" in str(cancel_row["notes"])
    assert not ((remaining_alloc["order_id"] == "ORDER-CANCEL") & (remaining_alloc["seller_sku"] == "SKU-1")).any()


def test_release_canceled_order_allocations_keeps_allocation_when_still_in_demand():
    token_df = pd.DataFrame(
        [
            {
                "token_id": "tok-cancel",
                "seller_sku": "SKU-1",
                "status": "allocated",
                "allocated_order_id": "ORDER-CANCEL",
                "allocated_date": "2026-04-10T10:00:00Z",
                "notes": "",
            }
        ]
    )
    alloc_df = pd.DataFrame(
        [
            {
                "order_id": "ORDER-CANCEL",
                "seller_sku": "SKU-1",
                "quantity": "1",
                "token_id": "tok-cancel",
                "allocation_date": "2026-04-10T10:00:00Z",
            }
        ]
    )

    updated_tokens, remaining_alloc, events, released_units = b007._release_canceled_order_allocations(
        token_df,
        alloc_df,
        demand_keys={("ORDER-CANCEL", "SKU-1")},
        canceled_order_ids={"ORDER-CANCEL"},
        now_iso="2026-04-22T13:30:00Z",
    )

    assert released_units == 0
    assert events.empty
    assert len(remaining_alloc.index) == 1
    assert updated_tokens.iloc[0]["status"] == "allocated"
