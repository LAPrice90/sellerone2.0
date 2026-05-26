from __future__ import annotations

import pandas as pd

from scripts.one_off import T030_apply_approved_token_corrections as t030


def test_apply_corrections_appends_available_tokens_from_latest_cost_basis() -> None:
    ledger = pd.DataFrame(
        [
            {
                "token_id": "old-1",
                "seller_sku": "SKU-1",
                "cost_per_unit": "2.50",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-01-01",
                "created_at": "2026-01-01T00:00:00Z",
                "source": "stock_receipt",
            },
            {
                "token_id": "old-2",
                "seller_sku": "SKU-1",
                "cost_per_unit": "3.25",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-02-01",
                "created_at": "2026-02-01T00:00:00Z",
                "source": "stock_receipt",
            },
        ]
    )
    corrections = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-1",
                "quantity": "2",
                "correction_class": "approved_stock_correction",
                "approval_reference": "APPROVED-1",
                "reason": "operator_approved",
            }
        ]
    )

    updated, audit = t030.apply_corrections(corrections, ledger, now_iso="2026-05-06T10:00:00Z")

    created = updated.loc[updated["source"].eq("manual_approved_correction")]
    assert len(created.index) == 2
    assert set(created["status"]) == {"available"}
    assert set(created["cost_per_unit"]) == {"3.25"}
    assert audit.iloc[0]["applied_qty"] == "2"
    assert audit.iloc[0]["status"] == "ok"


def test_apply_corrections_skips_when_cost_basis_missing() -> None:
    ledger = pd.DataFrame(
        [
            {
                "token_id": "old-1",
                "seller_sku": "SKU-1",
                "cost_per_unit": "",
                "status": "allocated",
            }
        ]
    )
    corrections = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-1",
                "quantity": "1",
                "correction_class": "approved_baseline_correction",
                "approval_reference": "APPROVED-1",
                "reason": "operator_approved",
            }
        ]
    )

    updated, audit = t030.apply_corrections(corrections, ledger, now_iso="2026-05-06T10:00:00Z")

    assert len(updated.index) == 1
    assert audit.iloc[0]["status"] == "skip"
    assert audit.iloc[0]["note"] == "missing_positive_cost_basis"


def test_apply_corrections_does_not_reapply_existing_event_id() -> None:
    ledger = pd.DataFrame(
        [
            {
                "token_id": "old-1",
                "seller_sku": "SKU-1",
                "cost_per_unit": "3.25",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-02-01",
                "created_at": "2026-02-01T00:00:00Z",
                "source": "stock_receipt",
            }
        ]
    )
    corrections = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-1",
                "quantity": "1",
                "correction_class": "approved_baseline_correction",
                "approval_reference": "APPROVED-1",
                "reason": "operator_approved",
            }
        ]
    )

    updated, audit = t030.apply_corrections(
        corrections,
        ledger,
        now_iso="2026-05-06T10:00:00Z",
        existing_event_ids={"T030-APPROVED-1-SKU-1"},
    )

    assert len(updated.index) == 1
    assert audit.iloc[0]["applied_qty"] == "0"
    assert audit.iloc[0]["status"] == "already_applied"
    assert audit.iloc[0]["note"] == "already_applied_event_id"
