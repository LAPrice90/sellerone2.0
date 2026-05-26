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

from scripts.flows.F._source_contracts import get_f_source_contracts


def _csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        return next(reader)


def test_f_source_contracts_present() -> None:
    contracts = get_f_source_contracts()
    assert set(contracts.keys()) == {
        "supplier_discovery_handoff",
        "supplier_price_list_universal_live",
        "feeder_shared_pass_logic_live",
        "feeder_approval_queue_live",
        "feeder_approval_decisions_log",
        "feeder_candidate_recommendations_live",
        "feeder_legacy_chart_daily_raw_live",
        "feeder_legacy_scrape_evidence_live",
        "feeder_legacy_first_checks_live",
        "f_screening_row_state_live",
        "product_db_preview",
        "sku_sales_velocity",
        "sku_performance_summary",
        "listing_offer_snapshot_latest",
        "feeder_backtest_policy_live",
        "feeder_backtest_input_view_live",
        "feeder_backtest_replay_daily_live",
    }


def test_f_source_contract_metadata_is_complete() -> None:
    for contract in get_f_source_contracts().values():
        assert contract.source_path.startswith("out/")
        assert contract.phase1_requirement in {"mandatory", "optional"}
        assert contract.required_columns
        assert len(set(contract.required_columns)) == len(contract.required_columns)
        assert contract.fallback_rules
        assert contract.must_not_duplicate


def test_f_source_contract_required_columns_match_fixture_headers() -> None:
    fixture_map = {
        "supplier_discovery_handoff": ROOT / "tests" / "fixtures" / "f_phase1" / "supplier_discovery_handoff_fixture.csv",
        "supplier_price_list_universal_live": ROOT / "tests" / "fixtures" / "f_phase1" / "supplier_price_list_universal_fixture.csv",
        "feeder_shared_pass_logic_live": ROOT / "tests" / "fixtures" / "f_phase1" / "feeder_shared_pass_logic_fixture.csv",
        "feeder_approval_queue_live": ROOT / "tests" / "fixtures" / "f_phase1" / "feeder_approval_queue_fixture.csv",
        "feeder_approval_decisions_log": ROOT / "tests" / "fixtures" / "f_phase1" / "feeder_approval_decisions_fixture.csv",
        "feeder_candidate_recommendations_live": ROOT / "tests" / "fixtures" / "f_phase1" / "feeder_candidate_recommendations_fixture.csv",
        "feeder_legacy_chart_daily_raw_live": ROOT / "tests" / "fixtures" / "f_backtest" / "feeder_legacy_chart_daily_raw_fixture.csv",
        "feeder_legacy_scrape_evidence_live": ROOT / "tests" / "fixtures" / "f_backtest" / "feeder_legacy_scrape_evidence_live_fixture.csv",
        "feeder_legacy_first_checks_live": ROOT / "tests" / "fixtures" / "f_backtest" / "feeder_legacy_first_checks_live_fixture.csv",
        "f_screening_row_state_live": ROOT / "tests" / "fixtures" / "f_backtest" / "f_screening_row_state_live_fixture.csv",
        "product_db_preview": ROOT / "tests" / "fixtures" / "f_backtest" / "product_db_preview_fixture.csv",
        "sku_sales_velocity": ROOT / "tests" / "fixtures" / "f_backtest" / "sku_sales_velocity_fixture.csv",
        "sku_performance_summary": ROOT / "tests" / "fixtures" / "f_backtest" / "sku_performance_summary_fixture.csv",
        "listing_offer_snapshot_latest": ROOT / "tests" / "fixtures" / "f_backtest" / "listing_offer_snapshot_latest_fixture.csv",
        "feeder_backtest_policy_live": ROOT / "tests" / "fixtures" / "f_backtest" / "feeder_backtest_policy_live_fixture.csv",
        "feeder_backtest_input_view_live": ROOT / "tests" / "fixtures" / "f_backtest" / "feeder_backtest_input_view_live_fixture.csv",
        "feeder_backtest_replay_daily_live": ROOT / "tests" / "fixtures" / "f_backtest" / "feeder_backtest_replay_daily_live_fixture.csv",
    }
    for contract_name, fixture_path in fixture_map.items():
        assert fixture_path.exists()
        headers = set(_csv_headers(fixture_path))
        contract = get_f_source_contracts()[contract_name]
        missing = [column for column in contract.required_columns if column not in headers]
        assert not missing
