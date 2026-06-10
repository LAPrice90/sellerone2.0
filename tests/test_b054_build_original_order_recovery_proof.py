from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B054_build_original_order_recovery_proof as b054


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


GAP_COLUMNS = [
    "order_id",
    "sku",
    "refund_posted_date",
    "allocation_gap_conclusion",
]


def test_b054_classifies_missing_original_order_as_api_fetch_needed(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2025-11-02T00:00:00Z",
                "allocation_gap_conclusion": "refund_money_without_original_order_or_allocation_proof",
            }
        ],
        GAP_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2025-11-02T00:00:00Z",
                "notes": "original_order_not_found",
            }
        ],
        ["order_id", "sku", "refund_posted_date", "notes"],
    )
    _write_csv(
        tmp_path / "out" / "financial_events_refunds.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "posted_date": "2025-11-02T00:00:00Z"}],
        ["order_id", "sku", "posted_date"],
    )

    result = b054.build_original_order_recovery_proof(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    proof = result["proof"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["proof_rows"] == "1"
    assert summary["needs_api_original_order_fetch_rows"] == "1"
    assert proof.iloc[0]["original_order_recovery_state"] == "needs_api_original_order_fetch_to_quarantine"
    assert proof.iloc[0]["api_refund_rows"] == "1"
    assert proof.iloc[0]["orders_all_rows"] == "0"
    assert proof.iloc[0]["quarantine_api_proved_rows"] == "0"
    assert proof.iloc[0]["roi_or_restock_use_allowed"] == "0"


def test_b054_classifies_api_quarantine_order_as_proof_not_live_truth(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2025-11-02T00:00:00Z",
                "allocation_gap_conclusion": "refund_money_without_original_order_or_allocation_proof",
            }
        ],
        GAP_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "financial_events_refunds.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "posted_date": "2025-11-02T00:00:00Z"}],
        ["order_id", "sku", "posted_date"],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "recovery_quarantine" / "b_order_recovery_quarantine.csv",
        [
            {
                "amazon_order_id": "ORDER-1",
                "marketplace_id": "A1F83G8C2ARO7P",
                "purchase_utc": "2025-10-20T10:00:00Z",
                "order_status": "Shipped",
                "sku": "SKU-A",
                "asin": "ASIN-A",
                "order_item_ids": "ITEM-1",
                "currency": "GBP",
                "proof_label": "API proved",
                "duplicate_state": "unique_in_quarantine",
                "ready_for_live_merge": "0",
            }
        ],
        [
            "amazon_order_id",
            "marketplace_id",
            "purchase_utc",
            "order_status",
            "sku",
            "asin",
            "order_item_ids",
            "currency",
            "proof_label",
            "duplicate_state",
            "ready_for_live_merge",
        ],
    )

    result = b054.build_original_order_recovery_proof(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    proof = result["proof"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["api_quarantine_original_order_rows"] == "1"
    assert proof.iloc[0]["original_order_recovery_state"] == "api_quarantine_original_order_proof_exists"
    assert proof.iloc[0]["purchase_date_proof"] == "2025-10-20T10:00:00Z"
    assert proof.iloc[0]["order_item_proof"] == "ITEM-1"
    assert proof.iloc[0]["preview_live_write_allowed"] == "0"


def test_b054_blocks_duplicate_quarantine_risk(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2025-11-02T00:00:00Z",
                "allocation_gap_conclusion": "refund_money_without_original_order_or_allocation_proof",
            }
        ],
        GAP_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "financial_events_refunds.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "posted_date": "2025-11-02T00:00:00Z"}],
        ["order_id", "sku", "posted_date"],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "recovery_quarantine" / "b_order_recovery_quarantine.csv",
        [
            {
                "amazon_order_id": "ORDER-1",
                "marketplace_id": "A1F83G8C2ARO7P",
                "purchase_utc": "2025-10-20T10:00:00Z",
                "order_status": "Shipped",
                "sku": "SKU-A",
                "asin": "ASIN-A",
                "order_item_ids": "ITEM-1",
                "currency": "GBP",
                "proof_label": "API proved",
                "duplicate_state": "duplicate_in_local_outputs",
                "ready_for_live_merge": "0",
            }
        ],
        [
            "amazon_order_id",
            "marketplace_id",
            "purchase_utc",
            "order_status",
            "sku",
            "asin",
            "order_item_ids",
            "currency",
            "proof_label",
            "duplicate_state",
            "ready_for_live_merge",
        ],
    )

    result = b054.build_original_order_recovery_proof(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    proof = result["proof"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["duplicate_risk_rows"] == "1"
    assert proof.iloc[0]["original_order_recovery_state"] == "quarantine_duplicate_risk_blocks_recovery"
    assert proof.iloc[0]["roi_or_restock_use_allowed"] == "0"


def test_b054_clears_when_upstream_gap_has_no_missing_original_order_rows(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2025-11-02T00:00:00Z",
                "allocation_gap_conclusion": "order_seen_allocation_missing",
            }
        ],
        GAP_COLUMNS,
    )

    result = b054.build_original_order_recovery_proof(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["proof_rows"] == "0"
    assert summary["needs_api_original_order_fetch_rows"] == "0"
