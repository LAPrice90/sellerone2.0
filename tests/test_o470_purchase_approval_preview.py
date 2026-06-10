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

from scripts.flows.O.O470_build_purchase_approval_preview import build_purchase_approval_preview
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T08:30:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def test_o470_builds_review_only_purchase_approval_preview(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_session_supplier_batch_lines_live",
        [
            {
                "batch_utc": OBSERVED,
                "batch_id": "batch-ready",
                "session_id": "o_restock_session_v1",
                "row_id": "row-ready",
                "draft_id": "draft-ready",
                "draft_event_utc": OBSERVED,
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-READY",
                "asin": "ASIN-READY",
                "title": "Ready Product",
                "supplier_sku": "SUP-READY",
                "barcode": "123",
                "draft_order_qty": "6",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "18",
                "supplier_order_viability_state": "review_only_not_po",
                "action_safety_state": "clean_review_ready_not_po",
                "action_block_reason": "",
                "line_state": "review_only_ready",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": "supplier_proof_clear",
                "supplier_proof_missing_reasons": "",
                "supplier_match_state": "exact_supplier_sku_or_barcode_match",
                "supplier_proof_state": "supplier_exact_match_proved",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "backorder_state": "backorder_none_confirmed",
                "supplier_file_asof_utc": OBSERVED,
                "supplier_cost_proof_state": "supplier_cost_verified",
                "pack_moq_proof_state": "pack_moq_verified",
                "supplier_batch_readiness_state": "ready_for_purchase_approval_review_only",
                "supplier_batch_readiness_reasons": "",
            },
            {
                "batch_utc": OBSERVED,
                "batch_id": "batch-blocked",
                "session_id": "o_restock_session_v1",
                "row_id": "row-blocked",
                "draft_id": "draft-blocked",
                "draft_event_utc": OBSERVED,
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-BLOCK",
                "asin": "ASIN-BLOCK",
                "title": "Blocked Product",
                "supplier_sku": "SUP-BLOCK",
                "barcode": "456",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "supplier_order_viability_state": "review_only_not_po",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "proof_missing",
                "line_state": "review_only_blocked",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": "needs_supplier_proof",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "supplier_match_state": "exact_supplier_sku_or_barcode_match",
                "supplier_proof_state": "supplier_exact_match_proved",
                "supplier_stock_state": "supplier_stock_not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "pack_moq_proof_state": "pack_moq_not_verified",
                "supplier_batch_readiness_state": "blocked_from_purchase_approval",
                "supplier_batch_readiness_reasons": "supplier_proof:supplier_stock_not_verified",
            },
        ],
    )

    lines_df, summary_df, health_df = build_purchase_approval_preview(
        root=tmp_path,
        preview_utc=OBSERVED,
        refresh_batches=False,
    )

    assert len(lines_df.index) == 2
    ready = lines_df[lines_df["seller_sku"] == "SKU-READY"].iloc[0]
    blocked = lines_df[lines_df["seller_sku"] == "SKU-BLOCK"].iloc[0]
    assert ready["approval_preview_state"] == "ready_for_purchase_approval_review_only"
    assert ready["approval_block_reasons"] == ""
    assert ready["creates_live_action"] == "0"
    assert blocked["approval_preview_state"] == "blocked_from_purchase_approval_review"
    assert "supplier_stock_not_verified" in blocked["approval_block_reasons"]
    assert set(health_df["status"].tolist()) == {"ok"}
    assert summary_df["creates_live_action"].eq("0").all()

    written = read_o_contract_df(tmp_path, "restock_purchase_approval_preview_lines_live")
    assert len(written.index) == 2


def test_o470_blocks_bad_upstream_live_action_in_preview(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_session_supplier_batch_lines_live",
        [
            {
                "batch_utc": OBSERVED,
                "batch_id": "batch-unsafe",
                "session_id": "o_restock_session_v1",
                "row_id": "row-unsafe",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-UNSAFE",
                "asin": "ASIN-UNSAFE",
                "draft_order_qty": "1",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "3",
                "creates_live_action": "1",
                "supplier_proof_checklist_status": "supplier_proof_clear",
                "supplier_batch_readiness_state": "ready_for_purchase_approval_review_only",
            }
        ],
    )

    lines_df, _summary_df, health_df = build_purchase_approval_preview(
        root=tmp_path,
        preview_utc=OBSERVED,
        refresh_batches=False,
    )

    line = lines_df.iloc[0]
    assert line["creates_live_action"] == "0"
    assert line["approval_preview_state"] == "blocked_from_purchase_approval_review"
    assert "creates_live_action_not_zero" in line["approval_block_reasons"]
    assert set(health_df["status"].tolist()) == {"ok"}
