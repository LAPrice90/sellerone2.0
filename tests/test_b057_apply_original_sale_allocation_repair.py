from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B057_apply_original_sale_allocation_repair as b057


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _seed_case(tmp_path: Path, *, duplicate_allocation: bool = False) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_original_allocation_gap_audit.csv",
        [
            {"order_id": "ORDER-LEGACY", "sku": "SKU-LEGACY", "allocation_gap_conclusion": "order_seen_allocation_missing"},
            {"order_id": "ORDER-RUNTIME", "sku": "SKU-RUNTIME", "allocation_gap_conclusion": "order_seen_allocation_missing"},
        ],
        ["order_id", "sku", "allocation_gap_conclusion"],
    )
    _write_csv(
        tmp_path / "out" / "orders_missing_tokens.csv",
        [
            {
                "Order ID": "ORDER-LEGACY",
                "SKU": "SKU-LEGACY",
                "Date": "2025-10-25T15:51:26Z",
                "lvl": "3",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "missing_token_reason_class": "missing_token_placeholder_applied",
                "receipt_state_class": "placeholder_applied_shortage_open",
            },
            {
                "Order ID": "ORDER-RUNTIME",
                "SKU": "SKU-RUNTIME",
                "Date": "2025-10-27T07:59:06Z",
                "lvl": "3",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "missing_token_reason_class": "missing_token_placeholder_applied",
                "receipt_state_class": "placeholder_applied_shortage_open",
            },
        ],
        [
            "Order ID",
            "SKU",
            "Date",
            "lvl",
            "Quantity Ordered",
            "currency_code",
            "missing_token_reason_class",
            "receipt_state_class",
        ],
    )
    _write_csv(
        tmp_path / "out" / "token_shortages_by_sku.csv",
        [
            {"seller_sku": "SKU-LEGACY", "missing_qty": "1", "shortage_class": "legacy_baseline_gap", "next_action": "needs_user_decision"},
            {"seller_sku": "SKU-RUNTIME", "missing_qty": "1", "shortage_class": "runtime_adjustment_pending", "next_action": "rerun_b009"},
        ],
        ["seller_sku", "missing_qty", "shortage_class", "next_action"],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "BASIS-LEGACY",
                "seller_sku": "SKU-LEGACY",
                "cost_per_unit": "1.25",
                "currency": "GBP",
                "status": "allocated",
                "allocated_order_id": "OLD-ORDER",
                "source": "live_stock_backdate",
            },
            {
                "token_id": "BASIS-RUNTIME",
                "seller_sku": "SKU-RUNTIME",
                "cost_per_unit": "2.50",
                "currency": "GBP",
                "status": "allocated",
                "allocated_order_id": "OLD-ORDER",
                "source": "live_stock_backdate",
            },
        ],
        ["token_id", "seller_sku", "cost_per_unit", "currency", "status", "allocated_order_id", "source"],
    )
    allocation_rows = []
    if duplicate_allocation:
        allocation_rows.append(
            {
                "order_id": "ORDER-LEGACY",
                "order_date": "2025-10-25T15:51:26Z",
                "seller_sku": "SKU-LEGACY",
                "quantity": "1",
                "token_id": "EXISTING",
            }
        )
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        allocation_rows,
        ["order_id", "order_date", "seller_sku", "quantity", "token_id"],
    )
    _write_csv(
        tmp_path / "out" / "token_cogs_ledger.csv",
        [],
        ["order_id", "order_date", "seller_sku", "token_id", "token_cost", "currency"],
    )
    _write_csv(
        tmp_path / "out" / "manual_token_correction_events.csv",
        [],
        ["event_id", "event_ts", "seller_sku", "quantity", "applied_qty", "status", "correction_class", "approval_reference", "reason", "note"],
    )


def test_b057_requires_protected_approval(tmp_path: Path) -> None:
    _seed_case(tmp_path)

    result = b057.apply_original_sale_allocation_repair(root=tmp_path, observed_utc="2026-06-03T17:00:00Z")

    assert result.status == "blocked_needs_approval"
    assert result.created_token_rows == 0


def test_b057_blocks_active_b_owner_without_matching_maintenance(tmp_path: Path) -> None:
    _seed_case(tmp_path)
    lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("B|pid=123|heartbeat=2026-06-03T17:00:00Z", encoding="utf-8")

    result = b057.apply_original_sale_allocation_repair(
        root=tmp_path,
        approve_protected_original_sale_allocation_repair=True,
        observed_utc="2026-06-03T17:00:00Z",
    )

    assert result.status == "blocked_active_b_owner"
    assert result.created_token_rows == 0


def test_b057_applies_sale_allocation_inside_matching_maintenance(tmp_path: Path) -> None:
    _seed_case(tmp_path)
    request_id = "B057_TEST"
    lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("B|pid=123|heartbeat=2026-06-03T17:00:00Z", encoding="utf-8")
    requested = tmp_path / "out" / "locks" / "maintenance.requested"
    ready = tmp_path / "out" / "locks" / "maintenance.ready"
    requested.parent.mkdir(parents=True, exist_ok=True)
    requested.write_text(f"requested_by=codex_b057|reason=original_sale_allocation|request_id={request_id}", encoding="utf-8")
    ready.write_text(f"B_READY|pid=123|ts=2026-06-03T17:00:00Z|request_id={request_id}", encoding="utf-8")

    result = b057.apply_original_sale_allocation_repair(
        root=tmp_path,
        approve_protected_original_sale_allocation_repair=True,
        observed_utc="2026-06-03T17:00:00Z",
        maintenance_request_id=request_id,
    )

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    allocations = pd.read_csv(tmp_path / "out" / "token_allocations_live.csv", dtype=str).fillna("")
    cogs = pd.read_csv(tmp_path / "out" / "token_cogs_ledger.csv", dtype=str).fillna("")
    shortages = pd.read_csv(tmp_path / "out" / "token_shortages_by_sku.csv", dtype=str).fillna("")
    missing = pd.read_csv(tmp_path / "out" / "orders_missing_tokens.csv", dtype=str).fillna("")
    manual_events = pd.read_csv(tmp_path / "out" / "manual_token_correction_events.csv", dtype=str).fillna("")
    applied = pd.read_csv(result.applied_path, dtype=str).fillna("")

    assert result.status == "applied"
    assert result.created_token_rows == 2
    assert result.allocated_token_rows == 2
    assert result.cogs_rows == 2
    assert result.shortage_rows_removed == 2
    assert result.missing_order_rows_removed == 2
    assert result.runtime_adjustment_deferred_rows == 1
    assert result.snapshot_dir is not None
    assert result.snapshot_dir.exists()
    assert len(ledger[ledger["source"] == "manager_approved_original_sale_allocation_repair"]) == 2
    assert len(allocations[allocations["notes"] == "manager_approved_original_sale_allocation_repair"]) == 2
    assert len(cogs[cogs["source"] == "token_allocations_live"]) == 2
    assert len(manual_events[manual_events["approval_reference"] == b057.APPROVAL_REFERENCE]) == 2
    assert shortages.empty
    assert missing.empty
    assert len(applied) == 2
    assert set(applied["runtime_stock_adjustment_closed"]) == {"0"}


def test_b057_blocks_duplicate_allocation(tmp_path: Path) -> None:
    _seed_case(tmp_path, duplicate_allocation=True)

    result = b057.apply_original_sale_allocation_repair(
        root=tmp_path,
        approve_protected_original_sale_allocation_repair=True,
        observed_utc="2026-06-03T17:00:00Z",
    )

    assert result.status == "blocked"
    assert result.created_token_rows == 0
    assert any("already has a token allocation" in reason for reason in result.reasons)
