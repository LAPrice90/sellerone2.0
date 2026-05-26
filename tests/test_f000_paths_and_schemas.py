from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F._paths import ensure_f_directories, get_f_path_contract
from scripts.flows.F._schemas import get_f_output_column_types, get_f_output_contracts


def test_f_path_contract_defaults_to_repo_paths() -> None:
    contract = get_f_path_contract()
    assert contract.live_dir.as_posix().endswith("out/systems/F/live")
    assert contract.history_dir.as_posix().endswith("out/systems/F/history")
    assert contract.inbox_dir.as_posix().endswith("out/systems/F/inbox")


def test_ensure_f_directories_is_idempotent(tmp_path: Path) -> None:
    first = ensure_f_directories(root=tmp_path)
    second = ensure_f_directories(root=tmp_path)
    assert first.live_dir.exists()
    assert first.history_dir.exists()
    assert first.inbox_dir.exists()
    assert second.live_dir == first.live_dir
    assert second.history_dir == first.history_dir
    assert second.inbox_dir == first.inbox_dir


def test_f_output_contracts_present() -> None:
    contracts = get_f_output_contracts()
    assert set(contracts.keys()) == {
        "supplier_discovery_handoff",
        "feeder_candidate_intake_live",
        "feeder_candidate_intake_holds",
        "feeder_intake_health",
        "feeder_candidate_normalized_live",
        "feeder_candidate_first_pass_classification_live",
        "feeder_candidate_first_pass_holds",
        "feeder_classification_health",
        "supplier_price_list_universal_live",
        "supplier_price_list_universal_holds",
        "supplier_price_list_active_run",
        "supplier_price_list_run_state",
        "supplier_price_list_queue_state",
        "supplier_price_list_health",
        "feeder_shared_pass_logic_live",
        "feeder_shared_pass_logic_holds",
        "feeder_shared_pass_logic_health",
        "feeder_candidate_recommendations_live",
        "feeder_approval_queue_live",
        "feeder_approval_decisions_log",
        "feeder_approval_health",
        "feeder_po_handoff_ready_live",
        "feeder_po_handoff_holds",
        "feeder_po_handoff_health",
        "feeder_legacy_first_checks_live",
        "f_screening_row_state_live",
        "feeder_legacy_scrape_evidence_live",
        "feeder_legacy_chart_daily_raw_live",
        "feeder_legacy_second_checks_live",
        "feeder_legacy_bot_status_live",
        "feeder_legacy_sheet_health",
        "f_scanner_speed_ledger_live",
        "feeder_backtest_policy_live",
        "feeder_backtest_policy_update_events",
        "feeder_backtest_input_view_live",
        "feeder_backtest_replay_daily_live",
        "feeder_backtest_summary_live",
        "feeder_backtest_health",
        "feeder_review_events",
        "amazon_listing_profile_events",
        "amazon_listing_intake_live",
        "amazon_listing_sku_reservations_live",
        "amazon_listing_drafts_live",
        "amazon_listing_draft_events",
        "amazon_listing_preview_events",
        "amazon_listing_preview_issues_live",
        "amazon_listing_submission_events",
        "amazon_listing_readback_events",
        "amazon_listing_reconciliation_live",
        "amazon_listing_restrictions_live",
        "amazon_listing_restriction_events",
        "brand_approval_queue_live",
        "brand_approval_decision_events",
        "amazon_listing_holds_live",
        "amazon_listing_health",
    }


def test_f_output_contract_metadata_is_consistent() -> None:
    contracts = get_f_output_contracts()
    for contract in contracts.values():
        assert contract.owner == "F"
        assert contract.state in {"live", "history", "inbox"}
        assert contract.behavior in {"append_only", "current_state"}
        assert contract.required_columns
        assert len(set(contract.required_columns)) == len(contract.required_columns)
        assert set(contract.required_columns).isdisjoint(set(contract.optional_columns))
        if "/live/" in contract.rel_path:
            assert contract.state == "live"


def test_f_column_types_cover_all_columns_as_strings() -> None:
    contracts = get_f_output_contracts()
    for name, contract in contracts.items():
        all_columns = [*contract.required_columns, *contract.optional_columns]
        column_types = get_f_output_column_types(name)
        assert set(column_types.keys()) == set(all_columns)
        assert set(column_types.values()) == {"string"}
