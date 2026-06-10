from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import core_truth_roles, get_o_output_contracts


def test_o_path_contract_defaults_to_repo_paths() -> None:
    contract = get_o_path_contract()
    assert contract.live_dir.as_posix().endswith("out/systems/O/live")
    assert contract.history_dir.as_posix().endswith("out/systems/O/history")
    assert contract.inbox_dir.as_posix().endswith("out/systems/O/inbox")


def test_ensure_o_directories_is_idempotent(tmp_path: Path) -> None:
    first = ensure_o_directories(root=tmp_path)
    second = ensure_o_directories(root=tmp_path)
    assert first.live_dir.exists()
    assert first.history_dir.exists()
    assert first.inbox_dir.exists()
    assert second.live_dir == first.live_dir
    assert second.history_dir == first.history_dir
    assert second.inbox_dir == first.inbox_dir


def test_all_phase0_output_contracts_present() -> None:
    contracts = get_o_output_contracts()
    phase0_contracts = {
        "restock_source_view",
        "sku_quantity_profiles",
        "special_order_profiles",
        "restock_recommendations_live",
        "restock_review_queue",
        "restock_profit_checks_live",
        "restock_profit_check_health",
        "restock_market_refresh_candidates_live",
        "restock_profit_check_history",
        "legacy_purchase_list_bridge",
        "legacy_purchase_list_bridge_health",
        "reorder_input_coverage_report",
        "reorder_input_coverage_by_supplier",
        "reorder_input_block_reasons",
        "restock_decision_events",
        "restock_decisions_log",
        "restock_review_log",
        "feeder_review_ui_drafts",
        "supplier_buy_cost_truth",
        "supplier_paid_cost_profiles_live",
        "supplier_price_list_change_log_live",
        "supplier_cost_confirmation_queue",
        "purchase_orders_live",
        "purchase_order_lines_live",
        "purchase_order_draft_holds",
        "receiving_events",
        "receiving_events_inbox",
        "receiving_event_holds",
        "ordered_stock_state",
        "send_to_amazon_queue",
        "send_to_amazon_handoff_events",
        "send_to_amazon_handoff_log",
        "send_to_amazon_handoff_holds",
        "product_db_operator_view",
        "product_db_source_health",
        "product_db_edit_events",
        "product_db_edit_holds",
        "product_db_promotion_candidates_live",
        "product_db_promotion_holds_live",
        "product_db_promotion_health",
        "repricer_tracker_view",
        "repricer_tracker_health",
        "supplier_profiles",
        "supplier_lead_time_history",
        "supplier_cost_snapshot_test",
    }
    assert phase0_contracts.issubset(set(contracts.keys()))


def test_output_contract_metadata_is_consistent() -> None:
    contracts = get_o_output_contracts()
    for contract in contracts.values():
        assert contract.owner == "O"
        assert contract.state in {"live", "history", "inbox"}
        assert contract.behavior in {"append_only", "current_state"}
        assert contract.required_columns
        assert len(set(contract.required_columns)) == len(contract.required_columns)
        assert set(contract.required_columns).isdisjoint(set(contract.optional_columns))
        if "/live/" in contract.rel_path:
            assert contract.state == "live"


def test_no_o_phase0_contract_claims_core_truth_role() -> None:
    blocked_roles = set(core_truth_roles())
    contracts = get_o_output_contracts()
    for contract in contracts.values():
        assert contract.role not in blocked_roles


def test_fixture_pack_loads_all_required_scenarios() -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "o_phase0" / "restock_scenarios.csv"
    supplier_fixture_path = ROOT / "tests" / "fixtures" / "o_phase0" / "supplier_profiles_fixture.csv"
    assert fixture_path.exists()
    assert supplier_fixture_path.exists()

    with fixture_path.open("r", encoding="utf-8", newline="") as fh:
        scenario_rows = list(csv.DictReader(fh))
    with supplier_fixture_path.open("r", encoding="utf-8", newline="") as fh:
        supplier_rows = list(csv.DictReader(fh))

    scenario_ids = {row["scenario_id"] for row in scenario_rows}
    assert scenario_ids == {
        "normal_fast_mover",
        "tight_margin_sku",
        "stale_out_of_stock_sku",
        "bulk_long_lead_sku",
        "backorder_heavy_sku",
        "supplier_threshold_free_shipping",
    }
    assert len(supplier_rows) >= 6
    assert any(row.get("supplier_code") == "SUP-F" for row in supplier_rows)
