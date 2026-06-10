from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B052_build_amazon_return_coverage_audit as b052


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


PREVIEW_COLUMNS = [
    "order_id",
    "sku",
    "refund_posted_date",
    "repair_lane",
    "repair_readiness",
]

RETURNS_COLUMNS = [
    "order-id",
    "sku",
    "return-date",
    "detailed-disposition",
    "reason",
    "status",
]

TOKEN_COLUMNS = [
    "token_id",
    "seller_sku",
    "status",
    "allocated_order_id",
    "return_order_id",
    "last_return_order_id",
    "notes",
]

STOCK_COLUMNS = [
    "event_id",
    "sku",
    "event_date",
    "event_type",
    "disposition",
    "quantity",
]

SUMMARY_COLUMNS = ["metric", "value"]


def test_b052_classifies_stock_adjustment_without_customer_return_order_proof(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2026-01-10T00:00:00Z",
                "repair_lane": "amazon_return_coverage_review",
                "repair_readiness": "blocked_missing_amazon_order_return_proof",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [
            {
                "order-id": "OTHER-ORDER",
                "sku": "SKU-A",
                "return-date": "2026-01-09T00:00:00Z",
                "detailed-disposition": "SELLABLE",
                "reason": "UNWANTED_ITEM",
                "status": "Unit returned to inventory",
            }
        ],
        RETURNS_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fba_customer_returns_summary.csv",
        [
            {"metric": "start_utc", "value": "2026-01-01T00:00:00Z"},
            {"metric": "end_utc", "value": "2026-02-01T00:00:00Z"},
        ],
        SUMMARY_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-RETURNED",
                "seller_sku": "SKU-A",
                "status": "returned_complete",
                "allocated_order_id": "ORDER-1",
                "return_order_id": "ORDER-1",
                "last_return_order_id": "ORDER-1",
                "notes": "return_closed:FBA123-retry49",
            },
            {
                "token_id": "TOKEN-DUP",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "ORDER-2",
                "return_order_id": "",
                "last_return_order_id": "ORDER-1",
                "notes": "return_sellable_dup:FBA123-retry49",
            },
        ],
        TOKEN_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "stock_adjustment_token_events.csv",
        [
            {
                "event_id": "FBA123-retry49",
                "sku": "SKU-A",
                "event_date": "2026-01-09T00:00:00Z",
                "event_type": "Receipts",
                "disposition": "SELLABLE",
                "quantity": "1",
            }
        ],
        STOCK_COLUMNS,
    )

    result = b052.build_amazon_return_coverage_audit(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    audit = result["audit"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["audit_rows"] == "1"
    assert summary["stock_adjustment_without_customer_return_rows"] == "1"
    assert summary["return_report_window_covered_rows"] == "1"
    assert summary["inventory_ledger_signal_not_order_return_rows"] == "1"
    assert summary["source_event_order_level_safe_rows"] == "0"
    assert audit.iloc[0]["exact_customer_return_rows"] == "0"
    assert audit.iloc[0]["coverage_conclusion"] == "stock_adjustment_without_customer_return_order_proof"
    assert audit.iloc[0]["manager_coverage_label"] == "stock_adjustment_only"
    assert audit.iloc[0]["customer_return_report_window_state"] == "return_report_window_covers_refund_date"
    assert audit.iloc[0]["source_event_kind"] == "inventory_ledger_signal_not_order_return"
    assert audit.iloc[0]["source_event_order_level_safe"] == "0"
    assert audit.iloc[0]["preview_live_write_allowed"] == "0"
    assert audit.iloc[0]["roi_or_restock_use_allowed"] == "0"


def test_b052_classifies_exact_customer_return_order_proof(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "refund_posted_date": "2026-01-10T00:00:00Z",
                "repair_lane": "amazon_return_coverage_review",
                "repair_readiness": "blocked_missing_amazon_order_return_proof",
            }
        ],
        PREVIEW_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [
            {
                "order-id": "ORDER-1",
                "sku": "SKU-A",
                "return-date": "2026-01-09T00:00:00Z",
                "detailed-disposition": "SELLABLE",
                "reason": "UNWANTED_ITEM",
                "status": "Unit returned to inventory",
            }
        ],
        RETURNS_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_fba_customer_returns_summary.csv",
        [
            {"metric": "start_utc", "value": "2026-01-01T00:00:00Z"},
            {"metric": "end_utc", "value": "2026-02-01T00:00:00Z"},
        ],
        SUMMARY_COLUMNS,
    )

    result = b052.build_amazon_return_coverage_audit(root=tmp_path, observed_utc="2026-06-03T16:00:00Z")
    audit = result["audit"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ok"
    assert summary["exact_customer_return_matched_rows"] == "1"
    assert summary["manager_exact_amazon_return_proved_rows"] == "1"
    assert summary["source_event_order_level_safe_rows"] == "1"
    assert audit.iloc[0]["coverage_conclusion"] == "customer_return_order_proved"
    assert audit.iloc[0]["manager_coverage_label"] == "exact_amazon_return_proved"
    assert audit.iloc[0]["customer_return_match_state"] == "exact_order_sku_match"
    assert audit.iloc[0]["customer_return_report_window_state"] == "return_report_window_covers_refund_date"
    assert audit.iloc[0]["source_event_order_level_safe"] == "1"
