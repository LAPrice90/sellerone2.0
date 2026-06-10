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

from scripts.flows.O.O022_build_inbound_fba_cost_proof import build_inbound_fba_cost_proof


def test_o022_labels_unlinked_inbound_costs_as_not_profit_safe(tmp_path: Path) -> None:
    out = tmp_path / "out"
    live = out / "systems" / "O" / "live"
    live.mkdir(parents=True)
    (out / "inbound_cost_events.csv").write_text(
        "amount,currency,inbound_shipment_id,parsed_fba_shipment_id,shipment_id\n"
        "-12.05,GBP,,,\n"
        "-0.60,GBP,,,\n",
        encoding="utf-8",
    )
    (out / "inbound_costs_allocated.csv").write_text(
        "shipment_id,currency,event_count,total_amount,total_tax,total_with_tax\n",
        encoding="utf-8",
    )
    (out / "inbound_costs_allocated_sku.csv").write_text(
        "shipment_id,sku,received_qty,total_received_qty,currency,allocated_amount,allocated_tax,allocated_total\n",
        encoding="utf-8",
    )
    (out / "inbound_costs_unallocated.csv").write_text(
        "amount,currency,unallocated_reason\n-12.05,GBP,missing_or_unknown_shipment_id\n",
        encoding="utf-8",
    )
    (out / "transaction_expense_allocations.csv").write_text(
        "status,allocated_sku,amount_value\nunallocated,,-12.05\n",
        encoding="utf-8",
    )
    (live / "restock_source_view.csv").write_text(
        "seller_sku,inbound_cost_confidence,expected_inbound_cost_per_unit_gbp\n"
        "SKU-1,missing,\n"
        "SKU-2,missing,\n",
        encoding="utf-8",
    )

    proof = build_inbound_fba_cost_proof(root=tmp_path, proof_utc="2026-06-04T12:00:00Z")
    by_check = proof.set_index("check_name")

    assert by_check.loc["inbound_cost_events", "status"] == "warn"
    assert by_check.loc["inbound_cost_events", "linked_rows"] == "0"
    assert by_check.loc["sku_cost_allocation", "safe_for_profit_use"] == "0"
    assert by_check.loc["restock_source_attachment", "restock_rows_missing_sku_cost"] == "2"


def test_o022_accepts_sku_level_gbp_cost_proof(tmp_path: Path) -> None:
    out = tmp_path / "out"
    live = out / "systems" / "O" / "live"
    live.mkdir(parents=True)
    (out / "inbound_cost_events.csv").write_text(
        "amount,currency,inbound_shipment_id,parsed_fba_shipment_id,shipment_id\n"
        "-12.00,GBP,FBA123,,\n",
        encoding="utf-8",
    )
    (out / "inbound_costs_allocated.csv").write_text(
        "shipment_id,currency,event_count,total_amount,total_tax,total_with_tax\n"
        "FBA123,GBP,1,-10,-2,-12\n",
        encoding="utf-8",
    )
    (out / "inbound_costs_allocated_sku.csv").write_text(
        "shipment_id,sku,received_qty,total_received_qty,currency,allocated_amount,allocated_tax,allocated_total\n"
        "FBA123,SKU-1,10,10,GBP,-10,-2,-12\n",
        encoding="utf-8",
    )
    (out / "inbound_costs_unallocated.csv").write_text(
        "amount,currency,unallocated_reason\n",
        encoding="utf-8",
    )
    (out / "transaction_expense_allocations.csv").write_text(
        "status,allocated_sku,amount_value\nallocated,SKU-1,-12\n",
        encoding="utf-8",
    )
    (live / "restock_source_view.csv").write_text(
        "seller_sku,inbound_cost_confidence,expected_inbound_cost_per_unit_gbp\n"
        "SKU-1,sku_allocated,1.2\n",
        encoding="utf-8",
    )

    proof = build_inbound_fba_cost_proof(root=tmp_path, proof_utc="2026-06-04T12:00:00Z")
    by_check = proof.set_index("check_name")

    assert by_check.loc["inbound_cost_events", "status"] == "ok"
    assert by_check.loc["sku_cost_allocation", "safe_for_profit_use"] == "1"
    assert by_check.loc["restock_source_attachment", "status"] == "ok"
    assert by_check.loc["restock_source_attachment", "restock_rows_with_sku_cost"] == "1"
