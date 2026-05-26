from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O008_build_supplier_cost_confirmation_queue import build_supplier_cost_confirmation_queue
from scripts.flows.O._contract_io import write_o_contract_df


def test_o008_queues_only_cost_rows_that_need_user_price_check(tmp_path: Path) -> None:
    truth = pd.DataFrame(
        [
            {
                "asof_utc": "2026-05-19T12:00:00Z",
                "seller_sku": "SKU-SAME",
                "asin": "ASIN-SAME",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_sku": "ALPHA-SAME",
                "barcode": "1111111111111",
                "price_list_unit_cost_gbp": "2.50",
                "price_list_currency": "GBP",
                "price_list_source_batch_id": "alpha_20260519",
                "price_list_source_received_at_utc": "2026-05-19T09:00:00Z",
                "price_list_source_row_key": "row_same",
                "purchase_reference_list_cost_gbp": "2.00",
                "actual_paid_unit_cost_gbp": "2.00",
                "actual_paid_source": "product_db_last_purchase_price",
                "actual_vs_list_ratio": "1",
                "discount_assumption_pct": "",
                "expected_next_unit_cost_gbp": "2.50",
                "expected_cost_source": "supplier_price_list_no_discount",
                "cost_confidence": "price_list_actual_match",
                "user_price_check_required": "0",
                "review_reason": "",
                "source_lineage": "product_db_preview|f_price_list_batch:alpha_20260519",
            },
            {
                "asof_utc": "2026-05-19T12:00:00Z",
                "seller_sku": "SKU-DISCOUNT",
                "asin": "ASIN-DISCOUNT",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "supplier_sku": "ALPHA-DISCOUNT",
                "barcode": "2222222222222",
                "price_list_unit_cost_gbp": "2.50",
                "price_list_currency": "GBP",
                "price_list_source_batch_id": "alpha_20260519",
                "price_list_source_received_at_utc": "2026-05-19T09:00:00Z",
                "price_list_source_row_key": "row_discount",
                "purchase_reference_list_cost_gbp": "2.00",
                "actual_paid_unit_cost_gbp": "1.80",
                "actual_paid_source": "product_db_last_purchase_price",
                "actual_vs_list_ratio": "0.9",
                "discount_assumption_pct": "10",
                "expected_next_unit_cost_gbp": "2.25",
                "expected_cost_source": "discount_assumption_from_actual_paid",
                "cost_confidence": "discount_assumption_needs_confirmation",
                "user_price_check_required": "1",
                "review_reason": "discount_assumption_needs_confirmation|price_list_changed_after_discounted_purchase",
                "source_lineage": "product_db_preview|f_price_list_batch:alpha_20260519",
            },
        ]
    )
    write_o_contract_df(tmp_path, "supplier_buy_cost_truth", truth)

    queue = build_supplier_cost_confirmation_queue(root=tmp_path, queue_utc="2026-05-19T12:05:00Z")

    assert len(queue.index) == 1
    row = queue.iloc[0]
    assert row["seller_sku"] == "SKU-DISCOUNT"
    assert row["confirmation_status"] == "needs_user_price_check"
    assert row["expected_next_unit_cost_gbp"] == "2.25"
    assert "latest list is 2.50" in row["user_prompt"]
