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

from scripts.flows.F.f_scanner_timeout_policy import default_timeout_policy_df
from scripts.flows.F.price_list_manager.timeout_queue import build_timeout_queue_eligibility


def _row(
    *,
    batch_id: str = "batch_1",
    supplier_id: str = "supplier_b",
    row_key: str = "row_1",
    barcode: str = "5000000000001",
    unit_cost: str = "5.00",
    source_row_hash: str = "row_hash_1",
) -> dict[str, str]:
    return {
        "batch_id": batch_id,
        "supplier_id": supplier_id,
        "row_key": row_key,
        "supplier_sku": f"{supplier_id.upper()}-1",
        "supplier_title": "Test Product",
        "barcode": barcode,
        "unit_cost": unit_cost,
        "currency": "GBP",
        "vat_rate": "20",
        "source_row_hash": source_row_hash,
        "row_change_status": "new",
        "scan_eligibility": "scan_now",
        "eligibility_reason": "test",
        "last_memory_key": "",
        "cooldown_until_utc": "",
    }


def _memory(
    *,
    memory_key: str,
    supplier_id: str,
    barcode: str = "5000000000001",
    fail_code: str,
    scanned_at: str,
    updated_at: str | None = None,
    row_hash: str = "old_hash",
) -> dict[str, str]:
    scope = "global_barcode" if memory_key.startswith("barcode:") else "supplier_offer"
    return {
        "memory_key": memory_key,
        "memory_scope": scope,
        "supplier_id": supplier_id,
        "barcode": barcode,
        "asin": "",
        "last_result_status": "FAIL",
        "last_fail_code": fail_code,
        "last_stage": "webscrape",
        "last_scanned_at_utc": scanned_at,
        "cooldown_until_utc": "",
        "cooldown_basis": fail_code,
        "attempt_count": "1",
        "last_batch_id": "old_batch",
        "last_row_hash": row_hash,
        "updated_at_utc": updated_at or scanned_at,
    }


def test_global_barcode_timeout_blocks_same_barcode_for_another_supplier() -> None:
    eligibility = build_timeout_queue_eligibility(
        batch_rows=pd.DataFrame([_row(supplier_id="supplier_b")]),
        memory=pd.DataFrame(
            [
                _memory(
                    memory_key="barcode:5000000000001",
                    supplier_id="supplier_a",
                    fail_code="PRICEHISTORYFAIL",
                    scanned_at="2026-05-01T00:00:00Z",
                )
            ]
        ),
        timeout_policy=default_timeout_policy_df("2026-05-01T00:00:00Z"),
        observed_utc="2026-06-01T00:00:00Z",
    )

    row = eligibility.iloc[0]
    assert row["scan_decision"] == "skip"
    assert row["decision_reason"] == "timeout_active"
    assert row["memory_key"] == "barcode:5000000000001"
    assert row["cooldown_until_utc"] == "2026-10-28T00:00:00Z"


def test_supplier_offer_timeout_resets_when_cost_changes() -> None:
    eligibility = build_timeout_queue_eligibility(
        batch_rows=pd.DataFrame([_row(supplier_id="dhb", unit_cost="4.50")]),
        memory=pd.DataFrame(
            [
                _memory(
                    memory_key="supplier_offer:dhb:5000000000001:5.00",
                    supplier_id="dhb",
                    fail_code="ROIFAIL",
                    scanned_at="2026-05-01T00:00:00Z",
                )
            ]
        ),
        timeout_policy=default_timeout_policy_df("2026-05-01T00:00:00Z"),
        observed_utc="2026-05-02T00:00:00Z",
    )

    row = eligibility.iloc[0]
    assert row["scan_decision"] == "scan"
    assert row["decision_reason"] == "cost_changed_reset"
    assert row["memory_key"] == "supplier_offer:dhb:5000000000001:5.00"


def test_expired_timeout_re_enters_scan_queue() -> None:
    eligibility = build_timeout_queue_eligibility(
        batch_rows=pd.DataFrame([_row(supplier_id="supplier_a")]),
        memory=pd.DataFrame(
            [
                _memory(
                    memory_key="barcode:5000000000001",
                    supplier_id="supplier_a",
                    fail_code="SELLERHISTORYFAIL",
                    scanned_at="2026-01-01T00:00:00Z",
                )
            ]
        ),
        timeout_policy=default_timeout_policy_df("2026-01-01T00:00:00Z"),
        observed_utc="2026-08-01T00:00:00Z",
    )

    row = eligibility.iloc[0]
    assert row["scan_decision"] == "scan"
    assert row["decision_reason"] == "timeout_expired_or_missing"
    assert row["cooldown_until_utc"] == "2026-06-30T00:00:00Z"

