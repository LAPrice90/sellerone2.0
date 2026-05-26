from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O003_build_restock_review_queue import build_restock_review_queue
from scripts.flows.O._contract_io import write_o_contract_df


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "o_phase1"


def _write_recommendations_fixture(tmp_root: Path) -> None:
    rec_dir = tmp_root / "out" / "systems" / "O" / "live"
    rec_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_DIR / "restock_recommendations_for_o003.csv", rec_dir / "restock_recommendations_live.csv")


def test_o003_builds_readable_queue_projection_without_extra_business_logic(tmp_path: Path) -> None:
    tmp_root = tmp_path
    _write_recommendations_fixture(tmp_root)

    queue_df = build_restock_review_queue(root=tmp_root, queue_utc="2026-04-03T11:30:00Z")
    required_view_cols = {
        "seller_sku",
        "asin",
        "supplier_code",
        "supplier_name",
        "suggested_action",
        "suggested_qty",
        "suggested_unit_cost_gbp",
        "expected_forward_roi_pct",
        "days_cover_available_only",
        "key_reason",
        "confidence_note",
    }
    assert required_view_cols.issubset(set(queue_df.columns))

    by_sku = queue_df.set_index("seller_sku")
    assert by_sku.loc["SKU-FULL", "suggested_qty"] == "20"
    assert by_sku.loc["SKU-TEST", "suggested_qty"] == "8"
    assert by_sku.loc["SKU-WAIT", "suggested_qty"] == "0"
    assert by_sku.loc["SKU-WAIT", "queue_status"] == "watch_or_wait"


def test_o003_excludes_active_snoozed_items_when_requested(tmp_path: Path) -> None:
    tmp_root = tmp_path
    _write_recommendations_fixture(tmp_root)

    decisions_path = tmp_root / "out" / "systems" / "O" / "live" / "restock_decisions_log.csv"
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    decisions_path.write_text(
        "decision_utc,event_utc,event_id,seller_sku,asin,original_recommendation_status,original_recommendation_reason,decision_action,final_decision_status,confirmed_unit_cost,confirmed_qty,recalculated_forward_roi_pct,decision_note,snooze_until_utc,actor,cost_mode,recommendation_basis,recommendation_asof_utc\n"
        "2026-04-03T11:00:00Z,2026-04-03T10:59:00Z,evt-1,SKU-TEST,ASINTEST001,test_restock,ROI_MID_BAND,snooze,snooze,,,,'review later',2026-04-10T00:00:00Z,tester,test,test_cost_snapshot,2026-04-03T10:00:00Z\n",
        encoding="utf-8",
    )

    queue_all = build_restock_review_queue(
        root=tmp_root,
        queue_utc="2026-04-03T11:30:00Z",
        exclude_snoozed=False,
    )
    queue_filtered = build_restock_review_queue(
        root=tmp_root,
        queue_utc="2026-04-03T11:30:00Z",
        exclude_snoozed=True,
    )

    assert "SKU-TEST" in set(queue_all["seller_sku"])
    row = queue_all.loc[queue_all["seller_sku"] == "SKU-TEST"].iloc[0]
    assert row["queue_status"] == "snoozed"
    assert row["is_snoozed"] == "1"
    assert row["snooze_until_utc"] == "2026-04-10T00:00:00Z"

    assert "SKU-TEST" not in set(queue_filtered["seller_sku"])


def test_o003_carries_supplier_cost_confirmation_fields(tmp_path: Path) -> None:
    write_o_contract_df(
        tmp_path,
        "restock_recommendations_live",
        pd.DataFrame(
            [
                {
                    "asof_utc": "2026-05-19T12:20:00Z",
                    "seller_sku": "SKU-CHECK",
                    "asin": "ASIN-CHECK",
                    "supplier_code": "SUP-A",
                    "supplier_name": "Alpha",
                    "recommendation_status": "full_restock",
                    "reason_codes": "SUPPLIER_COST_USER_CONFIRMATION_REQUIRED",
                    "recommended_qty_raw": "30",
                    "recommended_qty_rounded": "30",
                    "target_days_cover": "30",
                    "days_cover_available_only": "0",
                    "days_cover_total_pipeline": "0",
                    "current_supplier_buy_cost_gbp": "2.25",
                    "current_supplier_cost_source": "supplier_buy_cost_truth",
                    "market_price_gbp": "3.00",
                    "market_price_basis_used": "BUY_BOX_PRICE",
                    "forward_roi_pct": "28.888889",
                    "forward_profit_per_unit_gbp": "0.65",
                    "cost_mode": "live",
                    "recommendation_basis": "live_cost_inputs",
                    "max_break_even_purchase_price_gbp": "2.9",
                    "max_target_roi_purchase_price_gbp": "2.636364",
                    "target_roi_pct": "10",
                    "purchase_price_safety_status": "within_target_roi_max",
                    "user_price_check_required": "1",
                    "supplier_cost_review_reason": "discount_assumption_needs_confirmation",
                    "expected_next_unit_cost_gbp": "2.25",
                }
            ]
        ),
    )

    queue_df = build_restock_review_queue(root=tmp_path, queue_utc="2026-05-19T12:30:00Z")
    row = queue_df.iloc[0]

    assert row["user_price_check_required"] == "1"
    assert row["supplier_cost_review_reason"] == "discount_assumption_needs_confirmation"
    assert row["expected_next_unit_cost_gbp"] == "2.25"
    assert row["max_target_roi_purchase_price_gbp"] == "2.636364"
    assert row["purchase_price_safety_status"] == "within_target_roi_max"
