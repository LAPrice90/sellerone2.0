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

from scripts.flows.O.O023_build_profit_input_blocker_breakdown import build_profit_input_blocker_breakdown


def test_o023_builds_read_only_breakdown_for_minimum_input_profit_blocker(tmp_path: Path) -> None:
    live = tmp_path / "out" / "systems" / "O" / "live"
    live.mkdir(parents=True)
    (live / "restock_source_view.csv").write_text(
        "asof_utc,seller_sku,asin,supplier_name,supplier_code,title,has_minimum_restock_inputs,"
        "current_supplier_buy_cost_gbp,market_price_gbp,expected_refund_cost_per_unit_gbp,"
        "refund_proof_state,refund_sample_confidence,expected_inbound_cost_per_unit_gbp,"
        "inbound_cost_basis,inbound_cost_confidence,profit_input_confidence,profit_input_blockers,"
        "token_cost_trust_state,token_cost_trust_basis,token_cost_trust_blockers\n"
        "2026-06-04T12:00:00Z,SKU-1,ASIN-1,Supplier,SUP,Product,1,2.50,7.50,0,"
        "api_proved_or_not_applicable,high,,missing_sku_inbound_cost_allocation,missing,"
        "missing_profit_inputs,missing_inbound_cost_confidence,trusted,no_b_fallback_cost_risk_for_sku,\n"
        "2026-06-04T12:00:00Z,SKU-2,ASIN-2,Supplier,SUP,Product 2,1,2.50,7.50,0,"
        "api_proved_or_not_applicable,high,0.2,allocated_inbound_cost_per_received_unit,sku_allocated,"
        "profit_inputs_verified,,trusted,no_b_fallback_cost_risk_for_sku,\n",
        encoding="utf-8",
    )
    (live / "restock_session_review_live.csv").write_text(
        "seller_sku,asin,source_class,action_safety_state\n"
        "SKU-1,ASIN-1,native_o,blocked_from_clean_buy\n",
        encoding="utf-8",
    )
    (live / "reorder_input_coverage_report.csv").write_text(
        "seller_sku,asin,action_ready_now\nSKU-1,ASIN-1,0\n",
        encoding="utf-8",
    )

    breakdown, health = build_profit_input_blocker_breakdown(root=tmp_path, proof_utc="2026-06-04T12:00:00Z")

    assert len(breakdown.index) == 1
    row = breakdown.iloc[0]
    assert row["seller_sku"] == "SKU-1"
    assert row["primary_blocker"] == "inbound_fba_cost_missing"
    assert row["next_safe_action"] == "build_sku_level_inbound_fba_cost_proof"
    assert row["needs_luke_decision"] == "0"
    assert row["safe_for_clean_buy"] == "0"
    assert row["safe_for_po"] == "0"

    by_check = health.set_index("check")
    assert by_check.loc["profit_input_blocker_rows", "status"] == "warn"
    assert by_check.loc["profit_input_blocker_rows", "value"] == "minimum_input_rows=2;weak_rows=1"
    assert by_check.loc["weak_input_lanes", "value"] == "refund=0;inbound=1;profit=1;token_cost=0"


def test_o023_clears_when_minimum_input_rows_have_clean_profit_inputs(tmp_path: Path) -> None:
    live = tmp_path / "out" / "systems" / "O" / "live"
    live.mkdir(parents=True)
    (live / "restock_source_view.csv").write_text(
        "asof_utc,seller_sku,asin,supplier_name,supplier_code,has_minimum_restock_inputs,"
        "refund_proof_state,refund_sample_confidence,expected_inbound_cost_per_unit_gbp,"
        "inbound_cost_basis,inbound_cost_confidence,profit_input_confidence,profit_input_blockers,"
        "token_cost_trust_state,token_cost_trust_basis,token_cost_trust_blockers\n"
        "2026-06-04T12:00:00Z,SKU-1,ASIN-1,Supplier,SUP,1,api_proved_or_not_applicable,high,"
        "0.2,allocated_inbound_cost_per_received_unit,sku_allocated,profit_inputs_verified,"
        ",trusted,no_b_fallback_cost_risk_for_sku,\n",
        encoding="utf-8",
    )

    breakdown, health = build_profit_input_blocker_breakdown(root=tmp_path, proof_utc="2026-06-04T12:00:00Z")

    assert breakdown.empty
    by_check = health.set_index("check")
    assert by_check.loc["profit_input_blocker_rows", "status"] == "ok"
    assert by_check.loc["profit_input_blocker_rows", "value"] == "minimum_input_rows=1;weak_rows=0"
