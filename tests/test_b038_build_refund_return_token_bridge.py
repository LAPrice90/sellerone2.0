from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B038_build_refund_return_token_bridge as b038


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def _base_refund_row(order_id: str, sku: str, *, api_state: str = "api_proved") -> dict[str, str]:
    return {
        "order_id": order_id,
        "sku": sku,
        "refund_posted_date": "2026-05-20T09:00:00Z",
        "api_refund_proof_state": api_state,
        "refund_units": "1",
        "refund_price_total": "-12",
        "return_cogs_recovered_exvat": "0",
        "sellerboard_match_state": "sellerboard_return_witness" if api_state == "api_proved" else "sellerboard_return_unmatched_to_api_refund",
    }


def test_b038_sellable_return_with_reusable_token_is_clean(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-1", "SKU-A")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [
            {
                "order-id": "ORDER-1",
                "sku": "SKU-A",
                "return-date": "2026-05-21T10:00:00Z",
                "quantity": "1",
                "detailed-disposition": "SELLABLE",
                "status": "Unit returned to inventory",
                "reason": "ORDERED_WRONG_ITEM",
            }
        ],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition", "status", "reason"],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-1-RRET-1",
                "seller_sku": "SKU-A",
                "status": "available",
                "last_return_order_id": "ORDER-1",
                "return_order_id": "",
                "notes": "return_sellable_dup:RET-1",
            }
        ],
        ["token_id", "seller_sku", "status", "last_return_order_id", "return_order_id", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [{"return_event_id": "RET-1", "seller_sku": "SKU-A", "token_id": "TOKEN-1-RRET-1", "token_cost": "2.50"}],
        ["return_event_id", "seller_sku", "token_id", "token_cost"],
    )

    result = b038.build_refund_return_token_bridge(root=tmp_path, observed_utc="2026-05-22T00:00:00Z")
    bridge = result["bridge"]

    assert bridge.loc[0, "proof_label"] == "returned_sellable_token_reused"
    assert bridge.loc[0, "roi_stock_recovery_state"] == "stock_recovery_api_and_token_proved"
    assert bridge.loc[0, "mismatch_state"] == "ok"
    assert bridge.loc[0, "return_cogs_recovered_exvat"] == "2.5"


def test_b038_allocated_return_duplicate_counts_as_reuse_proof(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-ALLOC", "SKU-ALLOC")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [{"order-id": "ORDER-ALLOC", "sku": "SKU-ALLOC", "return-date": "2026-05-21", "quantity": "1", "detailed-disposition": "SELLABLE"}],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition"],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-ALLOC-R",
                "seller_sku": "SKU-ALLOC",
                "status": "allocated",
                "last_return_order_id": "ORDER-ALLOC",
                "return_order_id": "",
                "notes": "return_sellable_dup:RET-ALLOC",
            }
        ],
        ["token_id", "seller_sku", "status", "last_return_order_id", "return_order_id", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [{"return_event_id": "RET-ALLOC", "seller_sku": "SKU-ALLOC", "token_id": "TOKEN-ALLOC-R", "token_cost": "3.20"}],
        ["return_event_id", "seller_sku", "token_id", "token_cost"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "returned_sellable_token_reused"
    assert bridge.loc[0, "token_return_state"] == "reusable_return_token_seen"
    assert bridge.loc[0, "allocated_reusable_return_tokens"] == "1"
    assert bridge.loc[0, "mismatch_state"] == "ok"


def test_b038_return_ledger_proves_reuse_even_if_returned_token_later_sold_again(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-FIRST", "SKU-FIRST")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [{"order-id": "ORDER-FIRST", "sku": "SKU-FIRST", "return-date": "2026-05-21", "quantity": "1", "detailed-disposition": "SELLABLE"}],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition"],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-FIRST",
                "seller_sku": "SKU-FIRST",
                "status": "returned_complete",
                "allocated_order_id": "ORDER-FIRST",
                "return_order_id": "ORDER-FIRST",
                "last_return_order_id": "ORDER-FIRST",
                "return_event_id": "REF-FIRST",
                "last_return_event_id": "REF-FIRST",
                "notes": "return_closed:RET-FIRST",
            },
            {
                "token_id": "TOKEN-FIRST-R",
                "seller_sku": "SKU-FIRST",
                "status": "allocated",
                "allocated_order_id": "ORDER-LATER",
                "return_order_id": "",
                "last_return_order_id": "ORDER-LATER",
                "return_event_id": "",
                "last_return_event_id": "REF-LATER",
                "notes": "return_sellable_dup:RET-FIRST;return_closed:RET-LATER",
            },
        ],
        [
            "token_id",
            "seller_sku",
            "status",
            "allocated_order_id",
            "return_order_id",
            "last_return_order_id",
            "return_event_id",
            "last_return_event_id",
            "notes",
        ],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [{"return_event_id": "RET-FIRST", "seller_sku": "SKU-FIRST", "token_id": "TOKEN-FIRST-R", "token_cost": "3.20"}],
        ["return_event_id", "seller_sku", "token_id", "token_cost"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "returned_sellable_token_reused"
    assert bridge.loc[0, "token_return_state"] == "reusable_return_token_seen"
    assert bridge.loc[0, "return_cogs_recovered_exvat"] == "3.2"
    assert bridge.loc[0, "return_cogs_source"] == "token_return_ledger"
    assert bridge.loc[0, "mismatch_state"] == "ok"


def test_b038_sellable_return_without_token_reuse_creates_warning(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-2", "SKU-B")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [{"order-id": "ORDER-2", "sku": "SKU-B", "return-date": "2026-05-21", "quantity": "1", "detailed-disposition": "SELLABLE"}],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "returned_sellable_token_missing"
    assert bridge.loc[0, "mismatch_state"] == "warning"


def test_b038_sellable_return_later_unsellable_does_not_create_reusable_stock_warning(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-LATER-UNSELLABLE", "SKU-UNSELLABLE")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [
            {
                "order-id": "ORDER-LATER-UNSELLABLE",
                "sku": "SKU-UNSELLABLE",
                "return-date": "2026-05-21",
                "quantity": "1",
                "detailed-disposition": "SELLABLE",
            }
        ],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition"],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-LATER-UNSELLABLE",
                "seller_sku": "SKU-UNSELLABLE",
                "status": "unsellable",
                "last_return_order_id": "ORDER-LATER-UNSELLABLE",
                "return_order_id": "",
                "notes": "return_unsellable:DISPOSED-1",
            }
        ],
        ["token_id", "seller_sku", "status", "last_return_order_id", "return_order_id", "notes"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "returned_sellable_later_unsellable_no_reuse"
    assert bridge.loc[0, "roi_stock_recovery_state"] == "stock_recovery_blocked_by_token_disposal"
    assert bridge.loc[0, "mismatch_state"] == "ok"
    assert bridge.loc[0, "return_cogs_recovered_exvat"] == "0"


def test_b038_reused_stock_from_older_return_does_not_clear_current_return(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-OLD-REUSED", "SKU-OLD")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [{"order-id": "ORDER-OLD-REUSED", "sku": "SKU-OLD", "return-date": "2026-05-21", "quantity": "1", "detailed-disposition": "SELLABLE"}],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition"],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-OLD-R",
                "seller_sku": "SKU-OLD",
                "status": "returned_pending",
                "allocated_order_id": "ORDER-OLD-REUSED",
                "return_order_id": "ORDER-OLD-REUSED",
                "last_return_order_id": "OLDER-RETURN-ORDER",
                "notes": "return_sellable_dup:OLDER-EVENT",
            }
        ],
        ["token_id", "seller_sku", "status", "allocated_order_id", "return_order_id", "last_return_order_id", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [{"return_event_id": "OLDER-EVENT", "seller_sku": "SKU-OLD", "token_id": "TOKEN-OLD-R", "token_cost": "2.50"}],
        ["return_event_id", "seller_sku", "token_id", "token_cost"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "token_return_state"] == "returned_pending"
    assert bridge.loc[0, "reusable_return_tokens"] == "0"
    assert bridge.loc[0, "return_cogs_recovered_exvat"] == "0"
    assert bridge.loc[0, "proof_label"] == "returned_sellable_token_missing"
    assert bridge.loc[0, "mismatch_state"] == "warning"


def test_b038_unsellable_return_does_not_expect_reusable_stock(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-3", "SKU-C")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [{"order-id": "ORDER-3", "sku": "SKU-C", "return-date": "2026-05-21", "quantity": "1", "detailed-disposition": "CUSTOMER_DAMAGED"}],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition"],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [{"token_id": "TOKEN-3", "seller_sku": "SKU-C", "status": "unsellable", "last_return_order_id": "ORDER-3", "return_order_id": ""}],
        ["token_id", "seller_sku", "status", "last_return_order_id", "return_order_id"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "returned_unsellable_no_reuse"
    assert bridge.loc[0, "roi_stock_recovery_state"] == "not_safe_unsellable"
    assert bridge.loc[0, "mismatch_state"] == "ok"


def test_b038_unsellable_token_with_old_sellable_note_does_not_count_as_reuse(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-3B", "SKU-C")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [{"order-id": "ORDER-3B", "sku": "SKU-C", "return-date": "2026-05-21", "quantity": "1", "detailed-disposition": "CUSTOMER_DAMAGED"}],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition"],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-3B-R",
                "seller_sku": "SKU-C",
                "status": "unsellable",
                "last_return_order_id": "ORDER-3B",
                "return_order_id": "",
                "notes": "return_sellable_dup:RET-3B;non_sellable_return_correction_blocked",
            }
        ],
        ["token_id", "seller_sku", "status", "last_return_order_id", "return_order_id", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [{"return_event_id": "RET-3B", "seller_sku": "SKU-C", "token_id": "TOKEN-3B-R", "token_cost": "2.50"}],
        ["return_event_id", "seller_sku", "token_id", "token_cost"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "returned_unsellable_no_reuse"
    assert bridge.loc[0, "reusable_return_tokens"] == "0"
    assert bridge.loc[0, "return_cogs_recovered_exvat"] == "0"
    assert bridge.loc[0, "mismatch_state"] == "ok"


def test_b038_unsellable_return_cogs_residual_warns_without_reusable_token_count(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-3C", "SKU-C")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv",
        [{"order-id": "ORDER-3C", "sku": "SKU-C", "return-date": "2026-05-21", "quantity": "1", "detailed-disposition": "CUSTOMER_DAMAGED"}],
        ["order-id", "sku", "return-date", "quantity", "detailed-disposition"],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-3C-R",
                "seller_sku": "SKU-C",
                "status": "returned_complete",
                "last_return_order_id": "ORDER-3C",
                "return_order_id": "",
                "notes": "return_closed:RET-3C",
            }
        ],
        ["token_id", "seller_sku", "status", "last_return_order_id", "return_order_id", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [{"return_event_id": "RET-3C", "seller_sku": "SKU-C", "token_id": "TOKEN-3C-R", "token_cost": "2.50"}],
        ["return_event_id", "seller_sku", "token_id", "token_cost"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "returned_unsellable_no_reuse"
    assert bridge.loc[0, "reusable_return_tokens"] == "0"
    assert bridge.loc[0, "return_cogs_recovered_exvat"] == "0"
    assert bridge.loc[0, "blocked_return_cogs_exvat"] == "2.5"
    assert bridge.loc[0, "mismatch_state"] == "ok"
    assert bridge.loc[0, "notes"] == ""


def test_b038_sellerboard_only_return_stays_witness_only(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-4", "SKU-D", api_state="sellerboard_bridge_only")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "sellerboard_witness_only"
    assert bridge.loc[0, "refund_money_state"] == "sellerboard_bridge_only"
    assert bridge.loc[0, "mismatch_state"] == "warning"


def test_b038_token_reuse_without_amazon_return_proof_warns(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-5", "SKU-E")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-5-R",
                "seller_sku": "SKU-E",
                "status": "available",
                "last_return_order_id": "ORDER-5",
                "return_order_id": "",
                "notes": "return_sellable_dup:RET-5",
            }
        ],
        ["token_id", "seller_sku", "status", "last_return_order_id", "return_order_id", "notes"],
    )
    _write_csv(
        out / "token_return_ledger.csv",
        [{"return_event_id": "RET-5", "seller_sku": "SKU-E", "token_id": "TOKEN-5-R", "token_cost": "2.50"}],
        ["return_event_id", "seller_sku", "token_id", "token_cost"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "token_reuse_without_amazon_return_proof"
    assert bridge.loc[0, "return_cogs_recovered_exvat"] == "0"
    assert bridge.loc[0, "blocked_return_cogs_exvat"] == "2.5"
    assert bridge.loc[0, "mismatch_state"] == "warning"


def test_b038_original_returned_token_live_status_is_conflict_not_reuse(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _write_csv(
        out / "systems" / "B" / "refunds" / "b_refund_pnl_bridge.csv",
        [_base_refund_row("ORDER-6", "SKU-F")],
        [
            "order_id",
            "sku",
            "refund_posted_date",
            "api_refund_proof_state",
            "refund_units",
            "refund_price_total",
            "return_cogs_recovered_exvat",
            "sellerboard_match_state",
        ],
    )
    _write_csv(
        out / "token_ledger_live.csv",
        [
            {
                "token_id": "TOKEN-6",
                "seller_sku": "SKU-F",
                "status": "allocated",
                "last_return_order_id": "ORDER-6",
                "return_order_id": "",
                "notes": "return_closed:RET-6",
            }
        ],
        ["token_id", "seller_sku", "status", "last_return_order_id", "return_order_id", "notes"],
    )

    bridge = b038.build_refund_return_token_bridge(root=tmp_path)["bridge"]

    assert bridge.loc[0, "proof_label"] == "token_reuse_without_amazon_return_proof"
    assert bridge.loc[0, "roi_stock_recovery_state"] == "not_safe_original_return_token_status_conflict"
    assert bridge.loc[0, "reusable_return_tokens"] == "0"
    assert bridge.loc[0, "unsafe_original_return_tokens"] == "1"
    assert bridge.loc[0, "mismatch_state"] == "warning"
