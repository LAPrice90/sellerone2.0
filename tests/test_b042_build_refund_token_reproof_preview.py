from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B042_build_refund_token_reproof_preview as b042


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


SOURCE_COLUMNS = [
    "order_id",
    "sku",
    "repair_lane",
    "repair_readiness",
    "diagnosis",
    "allocated_original_token_ids",
]


def test_b042_previews_b008_order_sku_reproof_without_live_write(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "repair_lane": "b008_refund_token_marking",
                "repair_readiness": "ready_for_b008_order_sku_reproof",
                "diagnosis": "B008 did not prove a returned-pending token.",
                "allocated_original_token_ids": "TOKEN-1",
            }
        ],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "status": "allocated",
                "allocated_order_id": "ORDER-1",
                "return_order_id": "",
                "last_return_order_id": "",
                "notes": "",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"],
    )

    preview = b042.build_refund_token_reproof_preview(root=tmp_path)["preview"]

    assert len(preview) == 1
    assert preview.loc[0, "reproof_lane"] == "b008_refund_token_marking"
    assert preview.loc[0, "reproof_readiness"] == "ready_for_b008_order_sku_reproof"
    assert preview.loc[0, "ledger_allocated_token_ids"] == "TOKEN-1"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"


def test_b042_blocks_missing_original_allocation(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "repair_lane": "b008_allocation_gap",
                "repair_readiness": "blocked_missing_original_allocation",
                "diagnosis": "B008 did not prove a returned-pending token.",
                "allocated_original_token_ids": "",
            }
        ],
        SOURCE_COLUMNS,
    )

    preview = b042.build_refund_token_reproof_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "reproof_lane"] == "original_allocation_gap"
    assert preview.loc[0, "reproof_readiness"] == "blocked_missing_original_allocation"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"


def test_b042_falls_back_to_live_order_sku_ledger_token(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-2B",
                "sku": "SKU-B",
                "repair_lane": "b008_refund_token_marking",
                "repair_readiness": "ready_for_b008_order_sku_reproof",
                "diagnosis": "B008 did not prove a returned-pending token.",
                "allocated_original_token_ids": "TOKEN-STALE",
            }
        ],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [
            {
                "order_id": "ORDER-2B",
                "sku": "SKU-B",
                "requested_qty": "1",
                "applied_qty": "0",
                "status": "missing_allocations",
                "refund_event_id": "REF-2B",
            }
        ],
        ["order_id", "sku", "requested_qty", "applied_qty", "status", "refund_event_id"],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-LIVE",
                "seller_sku": "SKU-B",
                "status": "allocated",
                "allocated_order_id": "ORDER-2B",
                "return_order_id": "",
                "last_return_order_id": "",
                "notes": "",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"],
    )

    preview = b042.build_refund_token_reproof_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "reproof_lane"] == "b008_refund_token_marking"
    assert preview.loc[0, "reproof_readiness"] == "ready_for_b008_order_sku_reproof"
    assert preview.loc[0, "allocation_token_ids"] == "TOKEN-LIVE"
    assert preview.loc[0, "ledger_allocated_token_ids"] == "TOKEN-LIVE"
    assert preview.loc[0, "b008_event_ids"] == "REF-2B"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"


def test_b042_blocks_allocated_token_missing_from_ledger_without_order_sku_fallback(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-2C",
                "sku": "SKU-B",
                "repair_lane": "b008_refund_token_marking",
                "repair_readiness": "ready_for_b008_order_sku_reproof",
                "diagnosis": "B008 did not prove a returned-pending token.",
                "allocated_original_token_ids": "TOKEN-MISSING",
            }
        ],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "OTHER",
                "seller_sku": "SKU-B",
                "status": "allocated",
                "allocated_order_id": "OTHER-ORDER",
                "return_order_id": "",
                "last_return_order_id": "",
                "notes": "",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"],
    )

    preview = b042.build_refund_token_reproof_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "reproof_lane"] == "token_ledger_gap"
    assert preview.loc[0, "reproof_readiness"] == "blocked_missing_allocated_token_in_ledger"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"


def test_b042_blocks_conflicting_token_state(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-3",
                "sku": "SKU-C",
                "repair_lane": "b008_refund_token_marking",
                "repair_readiness": "ready_for_b008_order_sku_reproof",
                "diagnosis": "B008 did not prove a returned-pending token.",
                "allocated_original_token_ids": "TOKEN-3",
            }
        ],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-3",
                "seller_sku": "SKU-C",
                "status": "disposed",
                "allocated_order_id": "ORDER-3",
                "return_order_id": "",
                "last_return_order_id": "",
                "notes": "",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"],
    )

    preview = b042.build_refund_token_reproof_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "reproof_lane"] == "token_state_conflict"
    assert preview.loc[0, "reproof_readiness"] == "blocked_needs_protected_review"
    assert preview.loc[0, "protected_before_apply"] == "1"


def test_b042_routes_applied_event_without_pending_to_state_reproof(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-4",
                "sku": "SKU-D",
                "repair_lane": "b009_waiting_for_returned_pending_trace",
                "repair_readiness": "blocked_missing_returned_pending_token",
                "diagnosis": "B009 cannot see returned_pending.",
                "allocated_original_token_ids": "TOKEN-4",
            }
        ],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [
            {
                "order_id": "ORDER-4",
                "sku": "SKU-D",
                "requested_qty": "1",
                "applied_qty": "1",
                "status": "ok",
                "refund_event_id": "REF-4",
            }
        ],
        ["order_id", "sku", "requested_qty", "applied_qty", "status", "refund_event_id"],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-4",
                "seller_sku": "SKU-D",
                "status": "allocated",
                "allocated_order_id": "ORDER-4",
                "return_order_id": "",
                "last_return_order_id": "",
                "notes": "",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"],
    )

    preview = b042.build_refund_token_reproof_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "reproof_lane"] == "b008_event_ledger_state_drift"
    assert preview.loc[0, "reproof_readiness"] == "ready_for_b008_state_reproof_preview"
    assert preview.loc[0, "b008_event_ids"] == "REF-4"


def test_b042_blocks_original_return_token_live_status_conflict(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-5",
                "sku": "SKU-E",
                "repair_lane": "b009_waiting_for_returned_pending_trace",
                "repair_readiness": "blocked_missing_returned_pending_token",
                "diagnosis": "B009 cannot see returned_pending.",
                "allocated_original_token_ids": "TOKEN-5",
            }
        ],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [
            {
                "order_id": "ORDER-5",
                "sku": "SKU-E",
                "requested_qty": "1",
                "applied_qty": "1",
                "status": "ok",
                "refund_event_id": "REF-5",
            }
        ],
        ["order_id", "sku", "requested_qty", "applied_qty", "status", "refund_event_id"],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-5",
                "seller_sku": "SKU-E",
                "status": "allocated",
                "allocated_order_id": "ORDER-5",
                "return_order_id": "",
                "last_return_order_id": "ORDER-5",
                "notes": "return_unsellable:EVENT-5",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"],
    )

    preview = b042.build_refund_token_reproof_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "reproof_lane"] == "token_state_conflict"
    assert preview.loc[0, "reproof_readiness"] == "blocked_needs_protected_review"
    assert preview.loc[0, "protected_before_apply"] == "1"


def test_b042_reused_stock_sold_on_current_order_can_still_need_b008(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_repair_preview.csv",
        [
            {
                "order_id": "ORDER-6",
                "sku": "SKU-F",
                "repair_lane": "b008_refund_token_marking",
                "repair_readiness": "ready_for_b008_order_sku_reproof",
                "diagnosis": "B008 did not prove a returned-pending token.",
                "allocated_original_token_ids": "TOKEN-6",
            }
        ],
        SOURCE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [
            {
                "order_id": "ORDER-6",
                "sku": "SKU-F",
                "requested_qty": "1",
                "applied_qty": "0",
                "status": "missing_allocations",
                "refund_event_id": "REF-6",
            }
        ],
        ["order_id", "sku", "requested_qty", "applied_qty", "status", "refund_event_id"],
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-6",
                "seller_sku": "SKU-F",
                "status": "allocated",
                "allocated_order_id": "ORDER-6",
                "return_order_id": "",
                "last_return_order_id": "OLDER-RETURN-ORDER",
                "notes": "return_sellable_dup:OLDER-EVENT",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"],
    )

    preview = b042.build_refund_token_reproof_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "reproof_lane"] == "b008_refund_token_marking"
    assert preview.loc[0, "reproof_readiness"] == "ready_for_b008_order_sku_reproof"
    assert preview.loc[0, "ledger_allocated_token_ids"] == "TOKEN-6"
