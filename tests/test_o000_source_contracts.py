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

from scripts.flows.O._source_contracts import get_phase1_source_contracts


def _csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        return next(reader)


def test_phase1_source_contracts_present() -> None:
    contracts = get_phase1_source_contracts()
    assert set(contracts.keys()) == {
        "inventory_summaries",
        "order_master",
        "sku_sales_velocity",
        "sku_performance_summary",
        "inbound_costs_allocated_sku",
        "product_db_preview",
        "listing_offer_snapshot_latest",
        "feeder_backtest_summary_live",
        "f_price_list_manager_batch_rows",
        "f_price_list_manager_batches",
    }


def test_source_contract_metadata_is_complete() -> None:
    contracts = get_phase1_source_contracts()
    for contract in contracts.values():
        assert contract.source_path.startswith("out/")
        assert contract.phase1_requirement in {"mandatory", "optional"}
        assert contract.required_columns
        assert len(set(contract.required_columns)) == len(contract.required_columns)
        assert contract.fallback_rules
        assert contract.must_not_duplicate


def test_source_contract_required_columns_match_live_headers_when_available() -> None:
    contracts = get_phase1_source_contracts()
    for name, contract in contracts.items():
        csv_path = ROOT / contract.source_path
        if not csv_path.exists():
            assert contract.phase1_requirement == "optional", f"mandatory source missing: {name}"
            continue
        headers = set(_csv_headers(csv_path))
        missing = [col for col in contract.required_columns if col not in headers]
        assert not missing, f"{name} missing required columns: {missing}"


def test_source_contracts_explicitly_protect_upstream_truth() -> None:
    contracts = get_phase1_source_contracts()
    protected_claims: set[str] = set()
    for contract in contracts.values():
        for claim in contract.must_not_duplicate:
            assert claim not in protected_claims
            protected_claims.add(claim)
