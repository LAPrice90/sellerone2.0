from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B053_build_original_allocation_gap_audit as b053


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


REPROOF_COLUMNS = [
    "order_id",
    "sku",
    "refund_posted_date",
    "reproof_lane",
    "reproof_readiness",
]


def test_b053_classifies_refund_money_without_original_order(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2025-11-02T00:00:00Z",
                "reproof_lane": "original_allocation_gap",
                "reproof_readiness": "blocked_missing_original_allocation",
            }
        ],
        REPROOF_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "original_units": "0",
                "notes": "original_order_not_found",
            }
        ],
        ["order_id", "sku", "original_units", "notes"],
    )
    _write_csv(
        tmp_path / "out" / "financial_events_refunds.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "amount": "-5.00"}],
        ["order_id", "sku", "amount"],
    )

    result = b053.build_original_allocation_gap_audit(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    audit = result["audit"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["audit_rows"] == "1"
    assert summary["refund_money_without_original_order_rows"] == "1"
    assert audit.iloc[0]["api_refund_rows"] == "1"
    assert audit.iloc[0]["orders_all_rows"] == "0"
    assert audit.iloc[0]["allocation_gap_conclusion"] == "refund_money_without_original_order_or_allocation_proof"
    assert audit.iloc[0]["roi_or_restock_use_allowed"] == "0"


def test_b053_classifies_order_seen_allocation_missing(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_token_reproof_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2025-11-02T00:00:00Z",
                "reproof_lane": "original_allocation_gap",
                "reproof_readiness": "blocked_missing_original_allocation",
            }
        ],
        REPROOF_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "orders_all.csv",
        [{"amazon_order_id": "ORDER-1", "purchase_date": "2025-10-01T00:00:00Z"}],
        ["amazon_order_id", "purchase_date"],
    )
    _write_csv(
        tmp_path / "out" / "order_items_all.csv",
        [{"amazon_order_id": "ORDER-1", "seller_sku": "SKU-A", "quantity_ordered": "1"}],
        ["amazon_order_id", "seller_sku", "quantity_ordered"],
    )

    result = b053.build_original_allocation_gap_audit(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    audit = result["audit"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["order_seen_allocation_missing_rows"] == "1"
    assert audit.iloc[0]["orders_all_rows"] == "1"
    assert audit.iloc[0]["order_items_all_rows"] == "1"
    assert audit.iloc[0]["token_allocation_rows"] == "0"
    assert audit.iloc[0]["allocation_gap_conclusion"] == "order_seen_allocation_missing"
