from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O024_build_inbound_fba_source_options import build_inbound_fba_source_options


def test_o024_classifies_unlinked_fee_rows_as_no_direct_safe_route(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "inbound_cost_events.csv").write_text(
        "amount,currency,inbound_shipment_id,parsed_fba_shipment_id,shipment_id\n"
        "-12.05,GBP,,,\n",
        encoding="utf-8",
    )
    (out / "inbound_shipment_contents.csv").write_text(
        "inbound_shipment_id,sku,quantity\nFBA123,SKU-1,10\n",
        encoding="utf-8",
    )
    (out / "inbound_costs_allocated_sku.csv").write_text(
        "shipment_id,sku,received_qty,total_received_qty,currency,allocated_amount,allocated_tax,allocated_total\n",
        encoding="utf-8",
    )
    (out / "transaction_expense_allocations.csv").write_text(
        "status,allocated_sku,amount_value\nunallocated,,-12.05\n",
        encoding="utf-8",
    )
    (out / "inbound_history.csv").write_text(
        "timestamp_utc,sku,inbound_total\n2026-06-04T00:00:00Z,SKU-1,5\n",
        encoding="utf-8",
    )
    (out / "financial_events_inbound_summary.csv").write_text(
        "date,amount_type,currency,total_amount\n2026-06-04,FBAInboundTransportationFee,GBP,-12.05\n",
        encoding="utf-8",
    )

    options, health = build_inbound_fba_source_options(root=tmp_path, proof_utc="2026-06-04T12:00:00Z")
    by_route = options.set_index("route_id")
    by_check = health.set_index("check")

    assert by_route.loc["direct_fee_event_shipment_link", "status"] == "missing"
    assert by_route.loc["shipment_contents_sku_link", "status"] == "available_waiting_fee_link"
    assert by_route.loc["inbound_fee_average_policy", "needs_luke_decision"] == "1"
    assert by_route.loc["inbound_fee_average_policy", "safe_for_profit_use"] == "0"
    assert by_check.loc["direct_safe_routes", "status"] == "warn"
    assert by_check.loc["direct_safe_routes", "value"] == "direct_safe_routes=0;protected_routes=3"


def test_o024_marks_sku_allocation_file_as_direct_safe_when_present(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "inbound_cost_events.csv").write_text(
        "amount,currency,inbound_shipment_id,parsed_fba_shipment_id,shipment_id\n"
        "-12.00,GBP,FBA123,,\n",
        encoding="utf-8",
    )
    (out / "inbound_shipment_contents.csv").write_text(
        "inbound_shipment_id,sku,quantity\nFBA123,SKU-1,10\n",
        encoding="utf-8",
    )
    (out / "inbound_costs_allocated_sku.csv").write_text(
        "shipment_id,sku,received_qty,total_received_qty,currency,allocated_amount,allocated_tax,allocated_total\n"
        "FBA123,SKU-1,10,10,GBP,-10,-2,-12\n",
        encoding="utf-8",
    )
    (out / "transaction_expense_allocations.csv").write_text(
        "status,allocated_sku,amount_value\nallocated,SKU-1,-12\n",
        encoding="utf-8",
    )
    (out / "inbound_history.csv").write_text(
        "timestamp_utc,sku,inbound_total\n",
        encoding="utf-8",
    )
    (out / "financial_events_inbound_summary.csv").write_text(
        "date,amount_type,currency,total_amount\n",
        encoding="utf-8",
    )

    options, health = build_inbound_fba_source_options(root=tmp_path, proof_utc="2026-06-04T12:00:00Z")
    by_route = options.set_index("route_id")
    by_check = health.set_index("check")

    assert by_route.loc["sku_cost_allocation_file", "status"] == "safe"
    assert by_route.loc["sku_cost_allocation_file", "safe_for_profit_use"] == "1"
    assert by_route.loc["transaction_expense_sku_allocation", "safe_for_profit_use"] == "1"
    assert by_check.loc["direct_safe_routes", "status"] == "ok"
