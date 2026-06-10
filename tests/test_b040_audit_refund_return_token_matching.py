from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B040_audit_refund_return_token_matching as b040


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


BRIDGE_COLUMNS = [
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
    "unsafe_original_return_tokens",
    "reusable_return_tokens",
]


def test_b040_identifies_b008_missing_return_pending_proof(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            {
                "order_id": "ORDER-1",
                "sku": "SKU-A",
                "proof_label": "returned_sellable_token_missing",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "SELLABLE",
                "token_return_state": "no_token_return_state",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "reusable_return_tokens": "0",
            }
        ],
        BRIDGE_COLUMNS,
    )

    audit = b040.build_matching_audit(root=tmp_path)["audit"]

    assert len(audit) == 1
    assert audit.loc[0, "b008_status"] == "missing"
    assert "B008 did not prove" in audit.loc[0, "diagnosis"]


def test_b040_identifies_b009_sellable_partial_gap(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            {
                "order_id": "ORDER-2",
                "sku": "SKU-B",
                "proof_label": "returned_sellable_token_missing",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "SELLABLE",
                "token_return_state": "returned_pending",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "reusable_return_tokens": "0",
            }
        ],
        BRIDGE_COLUMNS,
    )
    _write_csv(
        tmp_path / "out" / "refund_token_events.csv",
        [{"order_id": "ORDER-2", "sku": "SKU-B", "requested_qty": "1", "applied_qty": "1", "status": "ok", "note": ""}],
        ["order_id", "sku", "requested_qty", "applied_qty", "status", "note"],
    )
    _write_csv(
        tmp_path / "out" / "stock_adjustment_token_events.csv",
        [
            {
                "event_id": "EV-1",
                "sku": "SKU-B",
                "event_date": "2026-05-21T12:00:00Z",
                "event_type": "CustomerReturns",
                "disposition": "SELLABLE",
                "quantity": "1",
                "applied_qty": "0",
                "status": "partial",
                "note": "insufficient_returned_pending",
            }
        ],
        ["event_id", "sku", "event_date", "event_type", "disposition", "quantity", "applied_qty", "status", "note"],
    )

    audit = b040.build_matching_audit(root=tmp_path)["audit"]

    assert audit.loc[0, "b008_status"] == "ok"
    assert audit.loc[0, "b009_nearby_sellable_partial_events"] == "1"
    assert "B009 saw sellable stock movement" in audit.loc[0, "diagnosis"]


def test_b040_identifies_non_sellable_reuse_conflict(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            {
                "order_id": "ORDER-3",
                "sku": "SKU-C",
                "proof_label": "returned_unsellable_no_reuse",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "DEFECTIVE",
                "token_return_state": "reusable_return_token_seen",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "4.2",
                "reusable_return_tokens": "1",
            }
        ],
        BRIDGE_COLUMNS,
    )

    audit = b040.build_matching_audit(root=tmp_path)["audit"]

    assert "Amazon says the return was not sellable" in audit.loc[0, "diagnosis"]
    assert "B009 FIFO matching" in audit.loc[0, "bounded_worker_task"]


def test_b040_identifies_reused_sellable_token_missing_cogs_trace(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            {
                "order_id": "ORDER-4",
                "sku": "SKU-D",
                "proof_label": "returned_sellable_token_reused",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "2026-05-21T10:00:00Z",
                "amazon_return_disposition": "SELLABLE",
                "token_return_state": "reusable_return_token_seen",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "reusable_return_tokens": "1",
            }
        ],
        BRIDGE_COLUMNS,
    )

    audit = b040.build_matching_audit(root=tmp_path)["audit"]

    assert "return token reuse is proved" in audit.loc[0, "diagnosis"]
    assert "return COGS trace proof" in audit.loc[0, "bounded_worker_task"]


def test_b040_identifies_original_return_token_live_status_conflict(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "B" / "refunds" / "b_refund_return_token_bridge.csv",
        [
            {
                "order_id": "ORDER-5",
                "sku": "SKU-E",
                "proof_label": "token_reuse_without_amazon_return_proof",
                "mismatch_state": "warning",
                "refund_posted_date": "2026-05-20T10:00:00Z",
                "amazon_return_date": "",
                "amazon_return_disposition": "",
                "token_return_state": "original_return_token_live_status_conflict",
                "refund_money_state": "api_proved",
                "return_cogs_recovered_exvat": "0",
                "unsafe_original_return_tokens": "1",
                "reusable_return_tokens": "0",
            }
        ],
        BRIDGE_COLUMNS,
    )

    audit = b040.build_matching_audit(root=tmp_path)["audit"]

    assert audit.loc[0, "unsafe_original_return_tokens"] == "1"
    assert "Original returned token has a live status" in audit.loc[0, "diagnosis"]
    assert "B008/B009 state agrees" in audit.loc[0, "bounded_worker_task"]
