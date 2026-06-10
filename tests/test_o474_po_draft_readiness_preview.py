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

from scripts.flows.O.O474_build_po_draft_readiness_preview import build_po_draft_readiness_preview
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T10:30:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _approval_line(
    *,
    packet_id: str,
    row_id: str,
    sku: str,
    approval_state: str = "ready_for_purchase_approval_review_only",
    supplier_proof: str = "supplier_proof_clear",
    qty: str = "2",
    cost: str = "3",
    creates_live_action: str = "0",
) -> dict[str, str]:
    return {
        "preview_utc": OBSERVED,
        "approval_packet_id": packet_id,
        "batch_id": f"batch-{packet_id}",
        "session_id": "o_restock_session_v1",
        "row_id": row_id,
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_class": "native_o",
        "seller_sku": sku,
        "asin": f"ASIN-{sku}",
        "title": f"Product {sku}",
        "supplier_sku": f"SUP-{sku}",
        "barcode": "123",
        "draft_order_qty": qty,
        "current_supplier_cost_gbp": cost,
        "draft_line_value_gbp": "6",
        "supplier_batch_readiness_state": "ready_for_purchase_approval_review_only",
        "supplier_batch_readiness_reasons": "",
        "supplier_proof_checklist_status": supplier_proof,
        "supplier_proof_missing_reasons": "" if supplier_proof == "supplier_proof_clear" else "supplier_stock_not_verified",
        "approval_preview_state": approval_state,
        "approval_block_reasons": "" if approval_state == "ready_for_purchase_approval_review_only" else "proof_missing",
        "creates_live_action": creates_live_action,
    }


def _guardrail(packet_id: str, state: str) -> dict[str, str]:
    return {
        "guardrail_utc": OBSERVED,
        "approval_packet_id": packet_id,
        "source_preview_utc": OBSERVED,
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "line_count": "1",
        "ready_line_count": "1",
        "blocked_line_count": "0",
        "draft_order_value_gbp": "6",
        "preview_packet_state": "ready_for_purchase_approval_review_only",
        "latest_decision_state": state,
        "latest_decision_id": "decision-1" if state == "local_review_accept_not_commitment" else "",
        "latest_decision_utc": OBSERVED if state == "local_review_accept_not_commitment" else "",
        "approval_guardrail_state": state,
        "approval_guardrail_reasons": "" if state == "local_review_accept_not_commitment" else state,
        "creates_live_action": "0",
        "source_classes": "native_o",
    }


def test_o474_builds_local_po_draft_readiness_preview(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_preview_lines_live",
        [
            _approval_line(packet_id="packet-ready", row_id="row-ready", sku="SKU-READY"),
            _approval_line(packet_id="packet-blocked", row_id="row-blocked", sku="SKU-BLOCK"),
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_guardrails_live",
        [
            _guardrail("packet-ready", "local_review_accept_not_commitment"),
            _guardrail("packet-blocked", "no_local_review_decision"),
        ],
    )

    lines_df, summary_df, health_df = build_po_draft_readiness_preview(
        root=tmp_path,
        preview_utc=OBSERVED,
        refresh_guardrails=False,
    )

    ready = lines_df[lines_df["seller_sku"] == "SKU-READY"].iloc[0]
    blocked = lines_df[lines_df["seller_sku"] == "SKU-BLOCK"].iloc[0]
    assert ready["po_draft_readiness_state"] == "ready_for_local_po_draft_review_only"
    assert ready["po_creation_allowed"] == "0"
    assert ready["creates_live_action"] == "0"
    assert blocked["po_draft_readiness_state"] == "blocked_from_local_po_draft_review"
    assert "local_review_not_accepted" in blocked["po_draft_block_reasons"]
    assert set(health_df["status"].tolist()) == {"ok"}
    assert summary_df["po_creation_allowed"].eq("0").all()

    written = read_o_contract_df(tmp_path, "restock_po_draft_readiness_preview_lines_live")
    assert len(written.index) == 2


def test_o474_blocks_missing_qty_and_cost_even_after_local_accept(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_preview_lines_live",
        [
            _approval_line(
                packet_id="packet-missing",
                row_id="row-missing",
                sku="SKU-MISSING",
                qty="",
                cost="",
            )
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_guardrails_live",
        [_guardrail("packet-missing", "local_review_accept_not_commitment")],
    )

    lines_df, _summary_df, health_df = build_po_draft_readiness_preview(
        root=tmp_path,
        preview_utc=OBSERVED,
        refresh_guardrails=False,
    )

    line = lines_df.iloc[0]
    assert line["po_draft_readiness_state"] == "blocked_from_local_po_draft_review"
    assert "missing_or_invalid_draft_qty" in line["po_draft_block_reasons"]
    assert "missing_or_invalid_unit_cost" in line["po_draft_block_reasons"]
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o474_blocks_upstream_live_action_without_creating_po_action(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_preview_lines_live",
        [
            _approval_line(
                packet_id="packet-unsafe",
                row_id="row-unsafe",
                sku="SKU-UNSAFE",
                creates_live_action="1",
            )
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_guardrails_live",
        [_guardrail("packet-unsafe", "local_review_accept_not_commitment")],
    )

    lines_df, _summary_df, health_df = build_po_draft_readiness_preview(
        root=tmp_path,
        preview_utc=OBSERVED,
        refresh_guardrails=False,
    )

    line = lines_df.iloc[0]
    assert line["po_draft_readiness_state"] == "blocked_from_local_po_draft_review"
    assert "approval_preview_creates_live_action" in line["po_draft_block_reasons"]
    assert line["po_creation_allowed"] == "0"
    assert line["creates_live_action"] == "0"
    assert "fail" in set(health_df["status"].tolist())
