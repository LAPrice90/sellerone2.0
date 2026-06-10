from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.flows.B import B047_build_token_shortage_repair_preview as b047
from scripts.flows.B import B048_apply_token_shortage_repair as b048
from scripts.flows.B import B049_build_legacy_baseline_gap_preview as b049
from scripts.flows.B import B050_apply_legacy_baseline_gap_repair as b050


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


SHORTAGE_COLUMNS = ["timestamp", "seller_sku", "missing_qty", "shortage_class", "evidence_note", "next_action"]
MISSING_COLUMNS = [
    "Order ID",
    "SKU",
    "Date",
    "lvl",
    "Quantity Ordered",
    "currency_code",
    "placeholder_cost_per_unit",
]
LEDGER_COLUMNS = [
    "token_id",
    "seller_sku",
    "cost_per_unit",
    "currency",
    "status",
    "received_date",
    "allocated_order_id",
    "allocated_date",
    "notes",
    "source",
    "source_batch_id",
    "created_at",
    "return_order_id",
    "return_date",
    "return_event_id",
    "last_return_order_id",
    "last_return_date",
    "last_return_event_id",
    "disposed_event_id",
    "disposed_date",
    "disposed_reason",
    "source_order_key",
]
ALLOC_COLUMNS = [
    "order_id",
    "order_date",
    "seller_sku",
    "quantity",
    "token_id",
    "token_cost",
    "currency",
    "allocation_date",
    "source_level",
    "notes",
]
COGS_COLUMNS = [
    "order_id",
    "order_date",
    "seller_sku",
    "token_id",
    "token_cost",
    "currency",
    "allocation_date",
    "quantity",
    "source",
    "built_at",
    "vat_rate_pct",
    "cogs_exvat",
    "cogs_vat",
    "cogs_total",
]
ADJUSTMENT_COLUMNS = [
    "event_id",
    "sku",
    "event_date",
    "event_type",
    "disposition",
    "quantity",
    "applied_qty",
    "status",
    "note",
    "event_ts",
]
MANUAL_EVENT_COLUMNS = [
    "event_id",
    "event_ts",
    "seller_sku",
    "quantity",
    "applied_qty",
    "status",
    "correction_class",
    "approval_reference",
    "reason",
    "note",
]


def _seed_shortage_case(root: Path) -> None:
    _write_csv(
        root / "out" / "token_shortages_by_sku.csv",
        [
            {
                "timestamp": "2026-06-03T13:50:18Z",
                "seller_sku": "AK-OB6V-HIYD",
                "missing_qty": "2",
                "shortage_class": "true_live_shortage",
                "evidence_note": "missing_qty=2;open_rows=2;levels=2.0;available_tokens=0;research_pending_tokens=0",
                "next_action": "wait_for_receipt_or_approved_stock_correction",
            },
            {
                "timestamp": "2026-06-03T13:50:18Z",
                "seller_sku": "T8-6UWL-I3E1",
                "missing_qty": "1",
                "shortage_class": "runtime_adjustment_pending",
                "evidence_note": "missing_qty=1;open_rows=1;levels=2.0;stock_events_raw_exists=1;status=partial;note=insufficient_tokens_to_remove;base_event_id=20016618004617;required=1;applied=0",
                "next_action": "rerun_b009_when_stock_events_raw_available",
            },
        ],
        SHORTAGE_COLUMNS,
    )
    _write_csv(
        root / "out" / "orders_missing_tokens.csv",
        [
            {
                "Order ID": "403-8818028-4046746",
                "SKU": "AK-OB6V-HIYD",
                "Date": "2026-06-01T14:19:38Z",
                "lvl": "2",
                "Quantity Ordered": "1",
                "currency_code": "EUR",
                "placeholder_cost_per_unit": "1.21",
            },
            {
                "Order ID": "026-7329933-6889938",
                "SKU": "AK-OB6V-HIYD",
                "Date": "2026-06-02T11:45:01Z",
                "lvl": "2",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "placeholder_cost_per_unit": "1.21",
            },
            {
                "Order ID": "202-4810318-2382705",
                "SKU": "T8-6UWL-I3E1",
                "Date": "2026-05-31T10:47:40Z",
                "lvl": "2",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "placeholder_cost_per_unit": "1.48",
            },
        ],
        MISSING_COLUMNS,
    )
    _write_csv(
        root / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "AK-BASIS",
                "seller_sku": "AK-OB6V-HIYD",
                "cost_per_unit": "1.21",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-04-28",
                "allocated_order_id": "OLD-AK",
                "allocated_date": "2026-05-30T00:00:00Z",
                "notes": "",
                "source": "stock_receipt",
                "source_batch_id": "SR-1",
                "created_at": "2026-05-16T05:01:13Z",
                "return_order_id": "",
                "return_date": "",
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
                "source_order_key": "",
            },
            {
                "token_id": "T8-BASIS",
                "seller_sku": "T8-6UWL-I3E1",
                "cost_per_unit": "1.48",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2025-08-26",
                "allocated_order_id": "OLD-T8",
                "allocated_date": "2026-02-09T00:00:00Z",
                "notes": "",
                "source": "live_stock_backdate",
                "source_batch_id": "T8-BATCH",
                "created_at": "",
                "return_order_id": "",
                "return_date": "",
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
                "source_order_key": "",
            },
        ],
        LEDGER_COLUMNS,
    )
    _write_csv(root / "out" / "token_allocations_live.csv", [], ALLOC_COLUMNS)
    _write_csv(root / "out" / "token_cogs_ledger.csv", [], COGS_COLUMNS)
    _write_csv(
        root / "out" / "stock_adjustment_token_events.csv",
        [
            {
                "event_id": "20016618004617",
                "sku": "T8-6UWL-I3E1",
                "event_date": "2026-04-11T01:00:00+0100",
                "event_type": "Adjustments",
                "disposition": "SELLABLE",
                "quantity": "-1",
                "applied_qty": "0",
                "status": "partial",
                "note": "insufficient_tokens_to_remove",
                "event_ts": "2026-04-29T05:06:04Z",
            },
            {
                "event_id": "20016618004617-retry40",
                "sku": "T8-6UWL-I3E1",
                "event_date": "2026-04-11T01:00:00+0100",
                "event_type": "Adjustments",
                "disposition": "SELLABLE",
                "quantity": "-1",
                "applied_qty": "0",
                "status": "partial",
                "note": "insufficient_tokens_to_remove",
                "event_ts": "2026-06-03T05:24:23Z",
            },
        ],
        ADJUSTMENT_COLUMNS,
    )
    _write_csv(root / "out" / "manual_token_correction_events.csv", [], MANUAL_EVENT_COLUMNS)


def test_b047_builds_preview_for_approved_shortages_only(tmp_path: Path) -> None:
    _seed_shortage_case(tmp_path)

    result = b047.build_token_shortage_repair_preview(root=tmp_path)
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "ready"
    assert len(preview) == 2
    assert (preview["new_token_role"] == "SALE").sum() == 2
    assert (preview["new_token_role"] == "ADJUSTMENT").sum() == 0
    sale_ids = set(preview.loc[preview["new_token_role"] == "SALE", "new_token_id"])
    assert any("403-8818028-4046746" in token_id for token_id in sale_ids)
    assert any("026-7329933-6889938" in token_id for token_id in sale_ids)
    assert not any("202-4810318-2382705" in token_id for token_id in sale_ids)
    assert set(preview["preview_live_write_allowed"]) == {"0"}
    assert set(preview["roi_or_restock_use_allowed"]) == {"0"}


def test_b048_requires_protected_approval(tmp_path: Path) -> None:
    _seed_shortage_case(tmp_path)

    result = b048.apply_token_shortage_repair(root=tmp_path)

    assert result.status == "blocked_needs_approval"
    assert result.created_token_rows == 0


def test_b048_applies_bounded_token_shortage_repair_with_snapshot(tmp_path: Path) -> None:
    _seed_shortage_case(tmp_path)

    result = b048.apply_token_shortage_repair(
        root=tmp_path,
        approve_protected_token_shortage_repair=True,
        observed_utc="2026-06-03T15:00:00Z",
    )

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    allocations = pd.read_csv(tmp_path / "out" / "token_allocations_live.csv", dtype=str).fillna("")
    shortages = pd.read_csv(tmp_path / "out" / "token_shortages_by_sku.csv", dtype=str).fillna("")
    missing = pd.read_csv(tmp_path / "out" / "orders_missing_tokens.csv", dtype=str).fillna("")
    cogs = pd.read_csv(tmp_path / "out" / "token_cogs_ledger.csv", dtype=str).fillna("")
    adjustments = pd.read_csv(tmp_path / "out" / "stock_adjustment_token_events.csv", dtype=str).fillna("")
    applied = pd.read_csv(result.applied_path, dtype=str).fillna("")

    assert result.status == "applied"
    assert result.created_token_rows == 2
    assert result.allocated_token_rows == 2
    assert result.disposed_token_rows == 0
    assert result.shortage_rows_removed == 1
    assert result.missing_order_rows_removed == 2
    assert result.snapshot_dir is not None
    assert result.snapshot_dir.exists()
    assert len(applied) == 2
    assert len(ledger[ledger["source"] == "manager_approved_token_shortage_repair"]) == 2
    assert len(allocations) == 2
    assert len(cogs) == 2
    assert set(shortages["seller_sku"]) == {"T8-6UWL-I3E1"}
    assert set(missing["SKU"]) == {"T8-6UWL-I3E1"}
    assert "20016618004617-retry41" not in set(adjustments["event_id"])
    assert (tmp_path / "out" / "systems" / "B" / "live" / "token_ledger_live.csv").exists()


def test_b048_blocks_existing_allocation_and_preserves_ledger(tmp_path: Path) -> None:
    _seed_shortage_case(tmp_path)
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        [
            {
                "order_id": "403-8818028-4046746",
                "order_date": "2026-06-01T14:19:38Z",
                "seller_sku": "AK-OB6V-HIYD",
                "quantity": "1",
                "token_id": "EXISTING",
                "token_cost": "1.21",
                "currency": "GBP",
                "allocation_date": "2026-06-03T14:00:00Z",
                "source_level": "2",
                "notes": "existing",
            }
        ],
        ALLOC_COLUMNS,
    )
    before = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")

    result = b048.apply_token_shortage_repair(
        root=tmp_path,
        approve_protected_token_shortage_repair=True,
        observed_utc="2026-06-03T15:00:00Z",
    )
    after = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")

    assert result.status == "blocked"
    assert result.created_token_rows == 0
    assert len(after) == len(before)


def test_b048_blocks_new_live_b_lock_and_preserves_ledger(tmp_path: Path) -> None:
    _seed_shortage_case(tmp_path)
    live_lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    live_lock.parent.mkdir(parents=True, exist_ok=True)
    live_lock.write_text("B|pid=123|heartbeat=2026-06-03T15:00:00Z", encoding="utf-8")
    before = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")

    result = b048.apply_token_shortage_repair(
        root=tmp_path,
        approve_protected_token_shortage_repair=True,
        observed_utc="2026-06-03T15:00:00Z",
    )
    after = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")

    assert result.status == "blocked_active_b_lock"
    assert result.created_token_rows == 0
    assert len(after) == len(before)


def test_b048_applies_inside_matching_b_maintenance_window(tmp_path: Path) -> None:
    _seed_shortage_case(tmp_path)
    request_id = "B048_TEST"
    live_lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    live_lock.parent.mkdir(parents=True, exist_ok=True)
    live_lock.write_text("B|pid=123|heartbeat=2026-06-03T15:00:00Z", encoding="utf-8")
    maintenance_flag = tmp_path / "out" / "locks" / "b_cycle.maintenance"
    maintenance_ready = tmp_path / "out" / "locks" / "maintenance.ready"
    maintenance_flag.parent.mkdir(parents=True, exist_ok=True)
    maintenance_flag.write_text(f"target_flow=B|action=pause|request_id={request_id}", encoding="utf-8")
    maintenance_ready.write_text(f"B_READY|pid=123|ts=2026-06-03T15:00:00Z|request_id={request_id}", encoding="utf-8")

    result = b048.apply_token_shortage_repair(
        root=tmp_path,
        approve_protected_token_shortage_repair=True,
        observed_utc="2026-06-03T15:00:00Z",
        maintenance_request_id=request_id,
    )

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    allocations = pd.read_csv(tmp_path / "out" / "token_allocations_live.csv", dtype=str).fillna("")
    shortages = pd.read_csv(tmp_path / "out" / "token_shortages_by_sku.csv", dtype=str).fillna("")

    assert result.status == "applied"
    assert result.created_token_rows == 2
    assert result.allocated_token_rows == 2
    assert result.snapshot_dir is not None
    assert len(ledger[ledger["source"] == "manager_approved_token_shortage_repair"]) == 2
    assert len(allocations) == 2
    assert set(shortages["seller_sku"]) == {"T8-6UWL-I3E1"}


def _seed_legacy_baseline_gap_case(root: Path, *, duplicate_allocation: bool = False) -> None:
    _write_csv(
        root / "out" / "token_shortages_by_sku.csv",
        [
            {
                "timestamp": "2026-06-03T14:30:01Z",
                "seller_sku": "MW-9K5M-VKW8",
                "missing_qty": "1",
                "shortage_class": "legacy_baseline_gap",
                "evidence_note": "missing_qty=1;open_rows=1;levels=2.0;all_existing_tokens_live_stock_backdate=1",
                "next_action": "needs_user_decision_baseline_correction_or_exception",
            }
        ],
        SHORTAGE_COLUMNS,
    )
    _write_csv(
        root / "out" / "orders_missing_tokens.csv",
        [
            {
                "Order ID": "204-5340430-7253949",
                "SKU": "MW-9K5M-VKW8",
                "Date": "2026-06-01T16:50:13Z",
                "lvl": "2",
                "Quantity Ordered": "1",
                "currency_code": "GBP",
                "placeholder_cost_per_unit": "13.65",
            }
        ],
        MISSING_COLUMNS,
    )
    _write_csv(
        root / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "MW-BASIS",
                "seller_sku": "MW-9K5M-VKW8",
                "cost_per_unit": "13.65",
                "currency": "GBP",
                "status": "allocated",
                "received_date": "2026-03-18",
                "allocated_order_id": "OLD-MW",
                "allocated_date": "2026-05-31T00:00:00Z",
                "notes": "",
                "source": "stock_receipt",
                "source_batch_id": "SR-20260318-026",
                "created_at": "2026-03-18T00:00:00Z",
                "return_order_id": "",
                "return_date": "",
                "return_event_id": "",
                "last_return_order_id": "",
                "last_return_date": "",
                "last_return_event_id": "",
                "disposed_event_id": "",
                "disposed_date": "",
                "disposed_reason": "",
                "source_order_key": "",
            }
        ],
        LEDGER_COLUMNS,
    )
    _write_csv(
        root / "out" / "manual_token_corrections_approved.csv",
        [
            {
                "seller_sku": "MW-9K5M-VKW8",
                "quantity": "2",
                "correction_class": "approved_baseline_correction",
                "approval_reference": "TOKEN_SHORTAGES_20260506_USER_APPROVED_ALL",
                "reason": "legacy_baseline_gap_user_approved",
            }
        ],
        ["seller_sku", "quantity", "correction_class", "approval_reference", "reason"],
    )
    _write_csv(
        root / "out" / "stock_receipt_summary.csv",
        [
            {
                "row_num": "76",
                "intake_date": "18/03/2026",
                "seller_sku": "MW-9K5M-VKW8",
                "qty": "20",
                "cost_per_unit": "13.65",
                "status": "APPLIED",
                "batch_id": "SR-20260318-026",
                "tokens_created": "20",
            }
        ],
        ["row_num", "intake_date", "seller_sku", "qty", "cost_per_unit", "status", "batch_id", "tokens_created"],
    )
    allocation_rows = []
    if duplicate_allocation:
        allocation_rows.append(
            {
                "order_id": "204-5340430-7253949",
                "order_date": "2026-06-01T16:50:13Z",
                "seller_sku": "MW-9K5M-VKW8",
                "quantity": "1",
                "token_id": "EXISTING-MW",
                "token_cost": "13.65",
                "currency": "GBP",
                "allocation_date": "2026-06-03T14:00:00Z",
                "source_level": "2",
                "notes": "existing",
            }
        )
    _write_csv(root / "out" / "token_allocations_live.csv", allocation_rows, ALLOC_COLUMNS)


def test_b049_builds_decision_ready_legacy_baseline_preview_without_live_write(tmp_path: Path) -> None:
    _seed_legacy_baseline_gap_case(tmp_path)
    live_lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    live_lock.parent.mkdir(parents=True, exist_ok=True)
    live_lock.write_text("B|pid=123|heartbeat=2026-06-03T15:00:00Z", encoding="utf-8")

    result = b049.build_legacy_baseline_gap_preview(root=tmp_path, observed_utc="2026-06-03T15:00:00Z")
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "decision_ready"
    assert summary["preview_rows"] == "1"
    assert summary["decision_ready_rows"] == "1"
    assert summary["active_b_owner_seen"] == "1"
    assert preview.loc[0, "sku"] == "MW-9K5M-VKW8"
    assert preview.loc[0, "order_id"] == "204-5340430-7253949"
    assert preview.loc[0, "basis_cost_per_unit"] == "13.65"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"


def test_b049_blocks_duplicate_allocation(tmp_path: Path) -> None:
    _seed_legacy_baseline_gap_case(tmp_path, duplicate_allocation=True)

    result = b049.build_legacy_baseline_gap_preview(root=tmp_path, observed_utc="2026-06-03T15:00:00Z")
    preview = result["preview"]
    summary = {row["metric"]: row["value"] for _, row in result["summary"].iterrows()}

    assert summary["status"] == "blocked"
    assert summary["blocked_rows"] == "1"
    assert preview.loc[0, "review_readiness"] == "blocked"
    assert preview.loc[0, "duplicate_allocation_count"] == "1"


def test_b050_requires_protected_approval(tmp_path: Path) -> None:
    _seed_legacy_baseline_gap_case(tmp_path)

    result = b050.apply_legacy_baseline_gap_repair(root=tmp_path, observed_utc="2026-06-03T15:00:00Z")

    assert result.status == "blocked_needs_approval"
    assert result.created_token_rows == 0


def test_b050_blocks_active_b_owner_without_matching_maintenance(tmp_path: Path) -> None:
    _seed_legacy_baseline_gap_case(tmp_path)
    live_lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    live_lock.parent.mkdir(parents=True, exist_ok=True)
    live_lock.write_text("B|pid=123|heartbeat=2026-06-03T15:00:00Z", encoding="utf-8")
    before = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")

    result = b050.apply_legacy_baseline_gap_repair(
        root=tmp_path,
        approve_protected_legacy_baseline_repair=True,
        observed_utc="2026-06-03T15:00:00Z",
    )
    after = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")

    assert result.status == "blocked_active_b_owner"
    assert result.created_token_rows == 0
    assert len(after) == len(before)


def test_b050_applies_one_token_repair_inside_matching_maintenance_window(tmp_path: Path) -> None:
    _seed_legacy_baseline_gap_case(tmp_path)
    request_id = "B050_TEST"
    live_lock = tmp_path / "out" / "systems" / "B" / "live" / "B_cycle.lock"
    live_lock.parent.mkdir(parents=True, exist_ok=True)
    live_lock.write_text("B|pid=123|heartbeat=2026-06-03T15:00:00Z", encoding="utf-8")
    maintenance_flag = tmp_path / "out" / "locks" / "b_cycle.maintenance"
    maintenance_ready = tmp_path / "out" / "locks" / "maintenance.ready"
    maintenance_flag.parent.mkdir(parents=True, exist_ok=True)
    maintenance_flag.write_text(f"target_flow=B|action=pause|request_id={request_id}", encoding="utf-8")
    maintenance_ready.write_text(f"B_READY|pid=123|ts=2026-06-03T15:00:00Z|request_id={request_id}", encoding="utf-8")

    result = b050.apply_legacy_baseline_gap_repair(
        root=tmp_path,
        approve_protected_legacy_baseline_repair=True,
        observed_utc="2026-06-03T15:00:00Z",
        maintenance_request_id=request_id,
    )

    ledger = pd.read_csv(tmp_path / "out" / "token_ledger_live.csv", dtype=str).fillna("")
    allocations = pd.read_csv(tmp_path / "out" / "token_allocations_live.csv", dtype=str).fillna("")
    shortages = pd.read_csv(tmp_path / "out" / "token_shortages_by_sku.csv", dtype=str).fillna("")
    missing = pd.read_csv(tmp_path / "out" / "orders_missing_tokens.csv", dtype=str).fillna("")
    cogs = pd.read_csv(tmp_path / "out" / "token_cogs_ledger.csv", dtype=str).fillna("")
    manual_events = pd.read_csv(tmp_path / "out" / "manual_token_correction_events.csv", dtype=str).fillna("")
    applied = pd.read_csv(result.applied_path, dtype=str).fillna("")

    assert result.status == "applied"
    assert result.created_token_rows == 1
    assert result.allocated_token_rows == 1
    assert result.cogs_rows == 1
    assert result.shortage_rows_removed == 1
    assert result.missing_order_rows_removed == 1
    assert result.snapshot_dir is not None
    assert result.snapshot_dir.exists()
    assert len(ledger[ledger["source"] == "manager_approved_legacy_baseline_gap_repair"]) == 1
    assert len(allocations[allocations["seller_sku"] == "MW-9K5M-VKW8"]) == 1
    assert len(cogs[cogs["seller_sku"] == "MW-9K5M-VKW8"]) == 1
    assert len(manual_events[manual_events["approval_reference"] == b050.APPROVAL_REFERENCE]) == 1
    assert shortages.empty
    assert missing.empty
    assert len(applied) == 1
