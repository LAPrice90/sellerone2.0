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

from scripts.flows.O.O480_build_po_draft_hold_review import build_po_draft_hold_review
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T13:30:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _packet_line(
    *,
    row_id: str,
    sku: str,
    packet_state: str = "ready_for_local_po_draft_packet_review_only",
    qty: str = "2",
    cost: str = "3",
    line_value: str = "6",
    po_file_write_allowed: str = "0",
    po_creation_allowed: str = "0",
    purchase_commitment_allowed: str = "0",
    receiving_allowed: str = "0",
    send_to_amazon_allowed: str = "0",
    creates_live_action: str = "0",
) -> dict[str, str]:
    return {
        "review_utc": OBSERVED,
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_id": f"line-design-{row_id}",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "source_design_utc": OBSERVED,
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
        "review_order_qty": qty,
        "review_unit_cost_gbp": cost,
        "review_line_value_gbp": line_value,
        "source_line_design_state": "ready_for_local_po_line_design_review_only",
        "source_po_file_write_allowed": "0",
        "source_po_creation_allowed": "0",
        "source_purchase_commitment_allowed": "0",
        "source_receiving_allowed": "0",
        "source_send_to_amazon_allowed": "0",
        "source_creates_live_action": "0",
        "packet_review_line_state": packet_state,
        "packet_review_block_reasons": "" if packet_state == "ready_for_local_po_draft_packet_review_only" else "source_line_design_not_ready",
        "po_file_write_allowed": po_file_write_allowed,
        "po_creation_allowed": po_creation_allowed,
        "purchase_commitment_allowed": purchase_commitment_allowed,
        "receiving_allowed": receiving_allowed,
        "send_to_amazon_allowed": send_to_amazon_allowed,
        "creates_live_action": creates_live_action,
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


def test_o480_builds_local_po_draft_hold_review(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_packet_review_lines_live",
        [_packet_line(row_id="row-ready", sku="SKU-READY")],
    )

    lines_df, summary_df, health_df = build_po_draft_hold_review(
        root=tmp_path,
        hold_utc=OBSERVED,
        refresh_packet_review=False,
    )

    line = lines_df.iloc[0]
    assert line["hold_review_line_state"] == "held_for_local_po_draft_review_only"
    assert line["hold_review_reasons"] == "local_review_hold_zero_action"
    assert line["hold_order_qty"] == "2"
    assert line["hold_unit_cost_gbp"] == "3"
    assert line["hold_line_value_gbp"] == "6"
    assert line["source_po_file_write_allowed"] == "0"
    assert line["po_file_write_allowed"] == "0"
    assert line["po_creation_allowed"] == "0"
    assert line["purchase_commitment_allowed"] == "0"
    assert line["receiving_allowed"] == "0"
    assert line["send_to_amazon_allowed"] == "0"
    assert line["creates_live_action"] == "0"
    assert summary_df.iloc[0]["hold_review_state"] == "held_for_local_po_draft_review_only"
    assert summary_df.iloc[0]["po_creation_allowed"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}

    written = read_o_contract_df(tmp_path, "restock_po_draft_hold_review_lines_live")
    assert len(written.index) == 1


def test_o480_blocks_missing_qty_and_cost_even_after_packet_review(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_packet_review_lines_live",
        [_packet_line(row_id="row-missing", sku="SKU-MISSING", qty="", cost="", line_value="")],
    )

    lines_df, _summary_df, health_df = build_po_draft_hold_review(
        root=tmp_path,
        hold_utc=OBSERVED,
        refresh_packet_review=False,
    )

    line = lines_df.iloc[0]
    assert line["hold_review_line_state"] == "blocked_from_local_po_draft_hold_review"
    assert "missing_or_invalid_hold_qty" in line["hold_review_reasons"]
    assert "missing_or_invalid_unit_cost" in line["hold_review_reasons"]
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o480_blocks_source_action_flag_without_writing_po_path(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_packet_review_lines_live",
        [_packet_line(row_id="row-unsafe", sku="SKU-UNSAFE", po_file_write_allowed="1")],
    )

    lines_df, _summary_df, health_df = build_po_draft_hold_review(
        root=tmp_path,
        hold_utc=OBSERVED,
        refresh_packet_review=False,
    )

    line = lines_df.iloc[0]
    assert line["hold_review_line_state"] == "blocked_from_local_po_draft_hold_review"
    assert "source_po_file_write_allowed_not_zero" in line["hold_review_reasons"]
    assert line["source_po_file_write_allowed"] == "1"
    assert line["po_file_write_allowed"] == "0"
    assert line["po_creation_allowed"] == "0"
    assert line["purchase_commitment_allowed"] == "0"
    assert line["creates_live_action"] == "0"
    assert "fail" in set(health_df["status"].tolist())
