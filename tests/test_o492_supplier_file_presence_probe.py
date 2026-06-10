from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O492_build_supplier_file_presence_probe import (
    build_supplier_file_presence_probe,
)
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T18:30:00Z"


def _write_batch_lines(root: Path, *, supplier_sku: str = "985 49830", barcode: str = "889698498302") -> None:
    write_o_contract_df(
        root,
        "restock_session_supplier_batch_lines_live",
        pd.DataFrame(
            [
                {
                    "batch_utc": OBSERVED,
                    "batch_id": "batch-abgee",
                    "session_id": "o_restock_session_v1",
                    "row_id": "row-1",
                    "draft_id": "draft-1",
                    "draft_event_utc": OBSERVED,
                    "supplier_name": "ABGee",
                    "supplier_code": "ABG",
                    "source_class": "legacy_bridge",
                    "seller_sku": "12-749B-9EB5",
                    "asin": "B084HZRR8G",
                    "title": "Leatherface",
                    "supplier_sku": supplier_sku,
                    "barcode": barcode,
                    "draft_order_qty": "1",
                    "current_supplier_cost_gbp": "7.59",
                    "draft_line_value_gbp": "7.59",
                    "supplier_order_viability_state": "review_only_not_po",
                    "action_safety_state": "blocked_from_clean_buy",
                    "action_block_reason": "supplier:missing_current_file_match",
                    "line_state": "review_only_blocked",
                    "creates_live_action": "0",
                    "supplier_proof_checklist_status": "needs_supplier_proof",
                    "supplier_proof_missing_reasons": "exact_supplier_match_not_proved",
                    "supplier_match_state": "missing_from_latest_supplier_file",
                    "supplier_proof_state": "missing_from_latest_supplier_file",
                    "supplier_stock_state": "supplier_stock_not_verified",
                    "backorder_state": "backorder_not_verified",
                    "supplier_file_asof_utc": "",
                    "supplier_cost_proof_state": "bridge_cost_only",
                    "pack_moq_proof_state": "pack_moq_not_verified",
                }
            ]
        ),
    )


def _write_price_file(root: Path, name: str, rows: list[dict[str, object]], *, mtime: int) -> Path:
    folder = root / "ABGee" / "inbox"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    pd.DataFrame(rows).to_csv(path, index=False)
    os.utime(path, (mtime, mtime))
    return path


def test_o492_finds_exact_supplier_sku_in_latest_local_file(tmp_path: Path) -> None:
    price_root = tmp_path / "price_files"
    _write_batch_lines(tmp_path)
    _write_price_file(
        price_root,
        "ABGee_Stock_Feed_latest.csv",
        [
            {
                "Product Code": "985 49830",
                "Product Name": "Leatherface",
                "Unit Code": "",
                "Qty": "4",
                "Barcode": "889698498302",
                "Trade": "7.59",
            }
        ],
        mtime=200,
    )

    probe_df, health_df = build_supplier_file_presence_probe(
        root=tmp_path,
        probe_utc=OBSERVED,
        refresh_batches=False,
        price_files_root=price_root,
    )

    row = probe_df.iloc[0]
    assert row["identity_match_state"] == "exact_supplier_sku_or_barcode_found"
    assert "supplier_sku" in row["matched_by"]
    assert row["matched_row_count"] == "1"
    assert row["source_index_handoff_state"] == "local_file_available_no_f_status"
    assert row["clears_supplier_proof"] == "0"
    assert row["purchase_commitment_allowed"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}

    written = read_o_contract_df(tmp_path, "restock_supplier_file_presence_probe_live")
    assert written.iloc[0]["creates_live_action"] == "0"


def test_o492_uses_latest_file_and_reports_absent_supplier_identity(tmp_path: Path) -> None:
    price_root = tmp_path / "price_files"
    _write_batch_lines(tmp_path)
    _write_price_file(
        price_root,
        "ABGee_Stock_Feed_old.csv",
        [
            {
                "Product Code": "985 49830",
                "Product Name": "Leatherface",
                "Unit Code": "",
                "Qty": "4",
                "Barcode": "889698498302",
                "Trade": "7.59",
            }
        ],
        mtime=100,
    )
    _write_price_file(
        price_root,
        "ABGee_Stock_Feed_latest.csv",
        [
            {
                "Product Code": "222 NS5061",
                "Product Name": "Texas Tubbx Boxed Leatherface",
                "Unit Code": "",
                "Qty": "2",
                "Barcode": "5056280459941",
                "Trade": "8.74",
            }
        ],
        mtime=200,
    )

    probe_df, health_df = build_supplier_file_presence_probe(
        root=tmp_path,
        probe_utc=OBSERVED,
        refresh_batches=False,
        price_files_root=price_root,
    )

    row = probe_df.iloc[0]
    assert row["latest_supplier_file_name"] == "ABGee_Stock_Feed_latest.csv"
    assert row["identity_match_state"] == "not_found_in_latest_local_supplier_file"
    assert row["source_index_handoff_state"] == "local_file_available_no_f_status"
    assert row["matched_row_count"] == "0"
    assert "exact supplier SKU or barcode was not found" in row["probe_explanation"]
    assert row["clears_supplier_proof"] == "0"
    assert row["po_creation_allowed"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o492_keeps_row_not_checked_when_supplier_file_is_missing(tmp_path: Path) -> None:
    price_root = tmp_path / "price_files"
    _write_batch_lines(tmp_path)

    probe_df, health_df = build_supplier_file_presence_probe(
        root=tmp_path,
        probe_utc=OBSERVED,
        refresh_batches=False,
        price_files_root=price_root,
    )

    row = probe_df.iloc[0]
    assert row["identity_match_state"] == "not_checked_no_local_supplier_file"
    assert row["latest_supplier_file_state"] == "local_price_files_root_missing"
    assert row["creates_live_action"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}
