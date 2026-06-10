from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B041_build_return_token_repair_preview as b041


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


AUDIT_COLUMNS = [
    "order_id",
    "sku",
    "proof_label",
    "mismatch_state",
    "refund_posted_date",
    "amazon_return_date",
    "amazon_return_disposition",
    "token_return_state",
    "refund_money_state",
    "return_cogs_recovered_exvat",
    "b008_applied_qty",
    "diagnosis",
]

BRIDGE_COLUMNS = [
    "order_id",
    "sku",
    "return_cogs_recovered_exvat",
]


def test_b041_previews_order_aware_b009_repair_without_live_write(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "proof_label": "returned_sellable_token_missing",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "SELLABLE",
                "token_return_state": "returned_pending",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "b008_applied_qty": "1",
                "diagnosis": "B009 saw sellable stock movement near the Amazon return date but did not apply it.",
            }
        ],
        AUDIT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [{"order_id": "ORDER-1", "sku": "SKU-A", "return_cogs_recovered_exvat": "0"}],
        BRIDGE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1",
                "seller_sku": "SKU-A",
                "status": "returned_pending",
                "return_order_id": "ORDER-1",
                "last_return_order_id": "",
                "allocated_order_id": "ORDER-1",
                "notes": "",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "allocated_order_id", "notes"],
    )

    result = b041.build_return_token_repair_preview(root=tmp_path)
    preview = result["preview"]

    assert len(preview) == 1
    assert preview.loc[0, "repair_lane"] == "b009_order_aware_sellable_return"
    assert preview.loc[0, "repair_readiness"] == "ready_for_b009_order_aware_preview"
    assert preview.loc[0, "returned_pending_token_ids"] == "TOKEN-1"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "roi_or_restock_use_allowed"] == "0"
    assert preview.loc[0, "protected_before_apply"] == "1"


def test_b041_blocks_non_sellable_reuse_conflict(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        [
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "proof_label": "returned_unsellable_no_reuse",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "token_return_state": "reusable_return_token_seen",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "4.20",
                "b008_applied_qty": "1",
                "diagnosis": "Amazon says the return was not sellable, but B has reusable-token evidence for the same order/SKU.",
            }
        ],
        AUDIT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [{"order_id": "ORDER-2", "sku": "SKU-B", "return_cogs_recovered_exvat": "4.20"}],
        BRIDGE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-2-R",
                "seller_sku": "SKU-B",
                "status": "available",
                "return_order_id": "",
                "last_return_order_id": "ORDER-2",
                "allocated_order_id": "",
                "notes": "return_sellable_dup:RET-2",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "allocated_order_id", "notes"],
    )

    preview = b041.build_return_token_repair_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "repair_lane"] == "protected_disposition_conflict"
    assert preview.loc[0, "repair_readiness"] == "blocked_needs_protected_review"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "protected_before_apply"] == "1"


def test_b041_does_not_count_unsellable_token_as_reusable_even_with_old_sellable_note(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        [
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "proof_label": "returned_unsellable_no_reuse",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "token_return_state": "unsellable",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "b008_applied_qty": "1",
                "diagnosis": "Amazon says the return was not sellable, and the token is now blocked.",
            }
        ],
        AUDIT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [{"order_id": "ORDER-2", "sku": "SKU-B", "return_cogs_recovered_exvat": "0"}],
        BRIDGE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-2-R",
                "seller_sku": "SKU-B",
                "status": "unsellable",
                "return_order_id": "",
                "last_return_order_id": "ORDER-2",
                "allocated_order_id": "",
                "notes": "return_sellable_dup:RET-2;non_sellable_return_correction_blocked",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "allocated_order_id", "notes"],
    )

    preview = b041.build_return_token_repair_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "repair_lane"] != "protected_disposition_conflict"
    assert preview.loc[0, "reusable_return_token_ids"] == ""


def test_b041_routes_non_sellable_return_cogs_residual_to_protected_review(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        [
            {
                "order_id": "ORDER-2C",
                "sku": "SKU-B",
                "proof_label": "returned_unsellable_no_reuse",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "token_return_state": "returned_complete_no_available_token_seen",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "4.20",
                "b008_applied_qty": "1",
                "diagnosis": "non-sellable return has return COGS recovery evidence",
            }
        ],
        AUDIT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [{"order_id": "ORDER-2C", "sku": "SKU-B", "return_cogs_recovered_exvat": "4.20"}],
        BRIDGE_COLUMNS,
    )

    preview = b041.build_return_token_repair_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "repair_lane"] == "protected_return_cogs_residual_conflict"
    assert preview.loc[0, "repair_readiness"] == "blocked_needs_protected_review"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "protected_before_apply"] == "1"


def test_b041_previews_b008_reproof_when_refund_token_mark_missing(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        [
            {
                "order_id": "ORDER-3",
                "sku": "SKU-C",
                "proof_label": "returned_sellable_token_missing",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "SELLABLE",
                "token_return_state": "no_token_return_state",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "b008_applied_qty": "0",
                "diagnosis": "B008 did not prove a returned-pending token for this refunded order/SKU.",
            }
        ],
        AUDIT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_allocations_live.csv",
        [{"order_id": "ORDER-3", "seller_sku": "SKU-C", "token_id": "TOKEN-3"}],
        ["order_id", "seller_sku", "token_id"],
    )

    preview = b041.build_return_token_repair_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "repair_lane"] == "b008_refund_token_marking"
    assert preview.loc[0, "repair_readiness"] == "ready_for_b008_order_sku_reproof"
    assert preview.loc[0, "allocated_original_token_ids"] == "TOKEN-3"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"


def test_b041_blocks_original_return_live_status_conflict(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        [
            {
                "order_id": "ORDER-4",
                "sku": "SKU-D",
                "proof_label": "token_reuse_without_amazon_return_proof",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "",
                "amazon_return_disposition": "",
                "token_return_state": "original_return_token_live_status_conflict",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "b008_applied_qty": "1",
                "diagnosis": "Original returned token has a live status, but reusable returned-stock proof is not clean for this order/SKU.",
            }
        ],
        AUDIT_COLUMNS,
    )

    preview = b041.build_return_token_repair_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "repair_lane"] == "protected_original_return_status_conflict"
    assert preview.loc[0, "repair_readiness"] == "blocked_needs_protected_review"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "protected_before_apply"] == "1"


def test_b041_routes_live_original_return_token_to_protected_original_lane(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        [
            {
                "order_id": "ORDER-4B",
                "sku": "SKU-D",
                "proof_label": "returned_unsellable_no_reuse",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "CUSTOMER_DAMAGED",
                "token_return_state": "original_return_token_live_status_conflict",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "b008_applied_qty": "0",
                "diagnosis": "Amazon says the return was not sellable, but B has live original-token evidence for the same order/SKU.",
            }
        ],
        AUDIT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-4B",
                "seller_sku": "SKU-D",
                "status": "allocated",
                "return_order_id": "",
                "last_return_order_id": "ORDER-4B",
                "allocated_order_id": "DOWNSTREAM-ORDER",
                "notes": "return_unsellable:ORDER-4B",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "allocated_order_id", "notes"],
    )

    preview = b041.build_return_token_repair_preview(root=tmp_path)["preview"]

    assert preview.loc[0, "repair_lane"] == "protected_original_return_status_conflict"
    assert preview.loc[0, "repair_readiness"] == "blocked_needs_protected_review"
    assert preview.loc[0, "unsafe_original_token_ids"] == "TOKEN-4B"
    assert preview.loc[0, "preview_live_write_allowed"] == "0"
    assert preview.loc[0, "protected_before_apply"] == "1"


def test_b041_does_not_count_current_pending_token_against_older_return_order(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_return_token_matching_audit.csv",
        [
            {
                "order_id": "OLDER-ORDER",
                "sku": "SKU-E",
                "proof_label": "returned_sellable_token_missing",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-01T10:00:00Z",
                "amazon_return_date": "2026-05-02T10:00:00Z",
                "amazon_return_disposition": "SELLABLE",
                "token_return_state": "returned_pending",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "b008_applied_qty": "1",
                "diagnosis": "B009 cannot see returned_pending.",
            },
            {
                "order_id": "CURRENT-ORDER",
                "sku": "SKU-E",
                "proof_label": "returned_sellable_token_missing",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "SELLABLE",
                "token_return_state": "returned_pending",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "b008_applied_qty": "1",
                "diagnosis": "B009 cannot see returned_pending.",
            },
        ],
        AUDIT_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-5",
                "seller_sku": "SKU-E",
                "status": "returned_pending",
                "return_order_id": "CURRENT-ORDER",
                "last_return_order_id": "OLDER-ORDER",
                "allocated_order_id": "CURRENT-ORDER",
                "notes": "return_sellable_dup:OLDER-EVENT",
            }
        ],
        ["token_id", "seller_sku", "status", "return_order_id", "last_return_order_id", "allocated_order_id", "notes"],
    )

    preview = b041.build_return_token_repair_preview(root=tmp_path)["preview"].set_index("order_id")

    assert preview.loc["CURRENT-ORDER", "repair_lane"] == "b009_order_aware_sellable_return"
    assert preview.loc["CURRENT-ORDER", "returned_pending_token_ids"] == "TOKEN-5"
    assert preview.loc["OLDER-ORDER", "repair_lane"] == "b009_waiting_for_returned_pending_trace"
    assert preview.loc["OLDER-ORDER", "returned_pending_token_ids"] == ""
