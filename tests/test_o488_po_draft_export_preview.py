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

from scripts.flows.O.O488_build_po_draft_export_preview import build_po_draft_export_preview
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T16:30:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _file_shape_line(*, state: str = "ready_for_local_po_draft_file_shape_review_only", po_file_write_allowed: str = "0") -> dict[str, str]:
    return {
        "shape_utc": OBSERVED,
        "po_draft_file_shape_preview_id": "file-shape-1",
        "po_draft_hold_review_id": "hold-review-1",
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "source_hold_utc": OBSERVED,
        "batch_id": "batch-1",
        "session_id": "o_restock_session_v1",
        "row_id": "row-1",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_class": "native_o",
        "seller_sku": "SKU1",
        "asin": "ASIN1",
        "title": "Product",
        "supplier_sku": "SUP1",
        "barcode": "123",
        "file_shape_qty": "2",
        "file_shape_unit_cost_gbp": "3",
        "file_shape_line_value_gbp": "6",
        "source_hold_review_line_state": "held_for_local_po_draft_review_only",
        "source_po_file_write_allowed": "0",
        "source_po_creation_allowed": "0",
        "source_purchase_commitment_allowed": "0",
        "source_receiving_allowed": "0",
        "source_send_to_amazon_allowed": "0",
        "source_creates_live_action": "0",
        "file_shape_line_state": state,
        "file_shape_block_reasons": "" if state == "ready_for_local_po_draft_file_shape_review_only" else "source_hold_review_not_ready",
        "po_file_write_allowed": po_file_write_allowed,
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
        "expected_profit_per_unit_gbp": "1.25",
        "expected_roi_pct": "41.67",
        "profit_verdict": "ok",
        "market_price_proof_state": "verified",
        "refund_proof_state": "not_verified",
        "inbound_cost_proof_state": "not_verified",
        "latest_supplier_proof_id": "supplier-proof-1",
        "latest_pack_moq_proof_id": "pack-proof-1",
        "source_classes": "native_o",
        "file_shape_basis": "local_po_draft_file_shape_preview_only",
    }


def _review_control(*, state: str = "local_po_draft_shape_ready_not_po", po_file_write_allowed: str = "0") -> dict[str, str]:
    return {
        "control_utc": OBSERVED,
        "po_draft_file_shape_preview_id": "file-shape-1",
        "po_draft_hold_review_id": "hold-review-1",
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "source_shape_utc": OBSERVED,
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "line_count": "1",
        "ready_line_count": "1",
        "blocked_line_count": "0",
        "file_shape_value_gbp": "6",
        "source_file_shape_state": "ready_for_local_po_draft_file_shape_review_only",
        "latest_decision_state": state,
        "latest_control_event_id": "control-event-1",
        "latest_decision_utc": OBSERVED,
        "review_control_state": state,
        "review_control_reasons": "" if state == "local_po_draft_shape_ready_not_po" else "kept_on_local_hold",
        "po_file_write_allowed": po_file_write_allowed,
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
        "source_classes": "native_o",
        "latest_decision_note": "local only",
    }


def test_o488_builds_local_export_preview_without_po_action(tmp_path: Path) -> None:
    _write_contract_rows(tmp_path, "restock_po_draft_file_shape_preview_lines_live", [_file_shape_line()])
    _write_contract_rows(tmp_path, "restock_po_draft_review_controls_live", [_review_control()])

    lines_df, summary_df, health_df = build_po_draft_export_preview(
        root=tmp_path,
        export_preview_utc=OBSERVED,
        refresh_review_controls=False,
    )

    line = lines_df.iloc[0]
    assert line["export_preview_line_state"] == "ready_for_local_po_draft_export_preview_only"
    assert line["source_review_control_state"] == "local_po_draft_shape_ready_not_po"
    assert line["po_file_write_allowed"] == "0"
    assert line["po_creation_allowed"] == "0"
    assert line["purchase_commitment_allowed"] == "0"
    assert line["receiving_allowed"] == "0"
    assert line["send_to_amazon_allowed"] == "0"
    assert line["creates_live_action"] == "0"
    assert summary_df.iloc[0]["export_preview_state"] == "ready_for_local_po_draft_export_preview_only"
    assert set(health_df["status"].tolist()) == {"ok"}

    written = read_o_contract_df(tmp_path, "restock_po_draft_export_preview_lines_live")
    assert len(written.index) == 1


def test_o488_blocks_when_review_control_is_not_shape_ready(tmp_path: Path) -> None:
    _write_contract_rows(tmp_path, "restock_po_draft_file_shape_preview_lines_live", [_file_shape_line()])
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_review_controls_live",
        [_review_control(state="local_po_draft_keep_on_hold")],
    )

    lines_df, summary_df, health_df = build_po_draft_export_preview(
        root=tmp_path,
        export_preview_utc=OBSERVED,
        refresh_review_controls=False,
    )

    line = lines_df.iloc[0]
    assert line["export_preview_line_state"] == "blocked_from_local_po_draft_export_preview"
    assert "review_control_not_shape_ready" in line["export_preview_block_reasons"]
    assert summary_df.iloc[0]["export_preview_state"] == "blocked_from_local_po_draft_export_preview"
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o488_fails_health_when_source_action_flag_is_not_zero(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_file_shape_preview_lines_live",
        [_file_shape_line(po_file_write_allowed="1")],
    )
    _write_contract_rows(tmp_path, "restock_po_draft_review_controls_live", [_review_control()])

    lines_df, _summary_df, health_df = build_po_draft_export_preview(
        root=tmp_path,
        export_preview_utc=OBSERVED,
        refresh_review_controls=False,
    )

    line = lines_df.iloc[0]
    assert line["source_po_file_write_allowed"] == "1"
    assert line["po_file_write_allowed"] == "0"
    assert line["export_preview_line_state"] == "blocked_from_local_po_draft_export_preview"
    assert "source_action_flags_not_zero" in line["export_preview_block_reasons"]
    assert "fail" in set(health_df["status"].tolist())
