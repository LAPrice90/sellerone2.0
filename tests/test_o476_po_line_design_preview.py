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

from scripts.flows.O.O476_build_po_line_design_preview import build_po_line_design_preview
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T11:30:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _readiness_line(
    *,
    row_id: str,
    sku: str,
    readiness_state: str = "ready_for_local_po_draft_review_only",
    qty: str = "2",
    cost: str = "3",
    line_value: str = "6",
    po_creation_allowed: str = "0",
    creates_live_action: str = "0",
) -> dict[str, str]:
    return {
        "preview_utc": OBSERVED,
        "po_readiness_preview_id": "po-preview-1",
        "approval_packet_id": "packet-1",
        "source_preview_utc": OBSERVED,
        "guardrail_utc": OBSERVED,
        "batch_id": "batch-1",
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
        "draft_line_value_gbp": line_value,
        "approval_preview_state": "ready_for_purchase_approval_review_only",
        "approval_guardrail_state": "local_review_accept_not_commitment",
        "po_draft_readiness_state": readiness_state,
        "po_draft_block_reasons": "" if readiness_state == "ready_for_local_po_draft_review_only" else "local_review_not_accepted",
        "po_creation_allowed": po_creation_allowed,
        "creates_live_action": creates_live_action,
        "supplier_proof_checklist_status": "supplier_proof_clear",
        "expected_profit_per_unit_gbp": "1.25",
        "expected_roi_pct": "41.67",
        "profit_verdict": "pass",
        "market_price_proof_state": "not_verified",
        "refund_proof_state": "not_verified",
        "inbound_cost_proof_state": "not_verified",
        "latest_supplier_proof_id": "supplier-proof-1",
        "latest_pack_moq_proof_id": "pack-proof-1",
        "source_classes": "native_o",
    }


def test_o476_builds_local_po_line_design_preview(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_readiness_preview_lines_live",
        [_readiness_line(row_id="row-ready", sku="SKU-READY")],
    )

    lines_df, summary_df, health_df = build_po_line_design_preview(
        root=tmp_path,
        preview_utc=OBSERVED,
        refresh_readiness=False,
    )

    line = lines_df.iloc[0]
    assert line["line_design_state"] == "ready_for_local_po_line_design_review_only"
    assert line["designed_order_qty"] == "2"
    assert line["designed_unit_cost_gbp"] == "3"
    assert line["designed_line_value_gbp"] == "6"
    assert line["po_file_write_allowed"] == "0"
    assert line["po_creation_allowed"] == "0"
    assert line["purchase_commitment_allowed"] == "0"
    assert line["receiving_allowed"] == "0"
    assert line["send_to_amazon_allowed"] == "0"
    assert line["creates_live_action"] == "0"
    assert summary_df.iloc[0]["line_design_packet_state"] == "ready_for_local_po_line_design_review_only"
    assert summary_df.iloc[0]["po_creation_allowed"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}

    written = read_o_contract_df(tmp_path, "restock_po_line_design_preview_lines_live")
    assert len(written.index) == 1


def test_o476_blocks_missing_qty_and_cost_even_after_po_readiness(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_readiness_preview_lines_live",
        [_readiness_line(row_id="row-missing", sku="SKU-MISSING", qty="", cost="", line_value="")],
    )

    lines_df, _summary_df, health_df = build_po_line_design_preview(
        root=tmp_path,
        preview_utc=OBSERVED,
        refresh_readiness=False,
    )

    line = lines_df.iloc[0]
    assert line["line_design_state"] == "blocked_from_local_po_line_design_review"
    assert "missing_or_invalid_design_qty" in line["line_design_block_reasons"]
    assert "missing_or_invalid_unit_cost" in line["line_design_block_reasons"]
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o476_blocks_upstream_action_flag_without_writing_po_path(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_readiness_preview_lines_live",
        [
            _readiness_line(
                row_id="row-unsafe",
                sku="SKU-UNSAFE",
                po_creation_allowed="1",
            )
        ],
    )

    lines_df, _summary_df, health_df = build_po_line_design_preview(
        root=tmp_path,
        preview_utc=OBSERVED,
        refresh_readiness=False,
    )

    line = lines_df.iloc[0]
    assert line["line_design_state"] == "blocked_from_local_po_line_design_review"
    assert "source_po_creation_flag_not_zero" in line["line_design_block_reasons"]
    assert line["po_file_write_allowed"] == "0"
    assert line["po_creation_allowed"] == "0"
    assert line["purchase_commitment_allowed"] == "0"
    assert line["creates_live_action"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}
