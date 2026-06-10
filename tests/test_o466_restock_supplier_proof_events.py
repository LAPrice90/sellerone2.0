from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O466_restock_supplier_proof_events import (
    build_restock_session_supplier_proof_row,
    latest_restock_session_supplier_proof_events,
    submit_restock_session_supplier_proof_event,
    validate_restock_session_supplier_proof_event,
)
from scripts.flows.O._contract_io import read_o_contract_df


SESSION_ROW = {
    "session_id": "o_restock_session_v1",
    "row_id": "o_restock_session_v1:native_o:supplier:sku",
    "seller_sku": "SKU-PROOF",
    "asin": "ASIN-PROOF",
    "supplier_name": "Supplier",
    "supplier_code": "SUP",
    "source_class": "native_o",
    "row_source_reference": "native_o:SKU-PROOF",
    "title": "Proof Product",
    "supplier_sku": "SUP-PROOF",
    "barcode": "123",
}


def test_o466_saves_supplier_proof_event_as_local_only(tmp_path: Path) -> None:
    saved = submit_restock_session_supplier_proof_event(
        root=tmp_path,
        session_row=SESSION_ROW,
        supplier_stock_state="supplier_stock_verified_in_stock",
        supplier_stock_qty="6",
        backorder_state="backorder_none_confirmed",
        supplier_file_asof_utc="2026-06-02",
        supplier_file_reference="supplier-file.csv",
        proof_note="checked supplier file",
        actor="tester",
        event_source_reference="test",
    )

    assert saved["proof_id"].startswith("o-session-supplier-proof-")
    assert saved["supplier_stock_state"] == "supplier_stock_verified_in_stock"
    assert saved["supplier_stock_qty"] == "6"
    assert saved["backorder_state"] == "backorder_none_confirmed"
    assert saved["supplier_file_asof_utc"] == "2026-06-02T00:00:00Z"
    assert saved["proof_status"] == "draft_proof"
    assert saved["creates_live_action"] == "0"

    event_df = read_o_contract_df(tmp_path, "restock_session_supplier_proof_events")
    assert len(event_df.index) == 1
    assert event_df.iloc[0]["creates_live_action"] == "0"


def test_o466_rejects_bad_supplier_proof_states() -> None:
    with pytest.raises(ValueError) as exc:
        build_restock_session_supplier_proof_row(
            session_row=SESSION_ROW,
            supplier_stock_state="buy_now",
            supplier_stock_qty="1",
            backorder_state="backorder_none_confirmed",
        )

    assert "missing_supplier_stock_state" in str(exc.value)


def test_o466_validation_catches_live_action_attempt() -> None:
    row = build_restock_session_supplier_proof_row(
        session_row=SESSION_ROW,
        supplier_stock_state="supplier_stock_verified_zero",
        supplier_stock_qty="0",
        backorder_state="backorder_not_verified",
    )
    row["creates_live_action"] = "1"

    assert "creates_live_action_must_be_zero" in validate_restock_session_supplier_proof_event(row)


def test_o466_latest_supplier_proof_keeps_newest_safe_event() -> None:
    rows = [
        {
            **SESSION_ROW,
            "event_utc": "2026-06-02T10:00:00Z",
            "proof_id": "proof-old",
            "supplier_stock_state": "supplier_stock_not_verified",
            "supplier_stock_qty": "",
            "backorder_state": "backorder_not_verified",
            "backorder_eta_utc": "",
            "supplier_file_asof_utc": "",
            "supplier_file_reference": "",
            "proof_note": "old",
            "actor": "tester",
            "event_source_reference": "test",
            "proof_status": "draft_proof",
            "creates_live_action": "0",
        },
        {
            **SESSION_ROW,
            "event_utc": "2026-06-02T11:00:00Z",
            "proof_id": "proof-new",
            "supplier_stock_state": "supplier_stock_verified_zero",
            "supplier_stock_qty": "0",
            "backorder_state": "backorder_none_confirmed",
            "backorder_eta_utc": "",
            "supplier_file_asof_utc": "2026-06-02T09:00:00Z",
            "supplier_file_reference": "new-file.csv",
            "proof_note": "new",
            "actor": "tester",
            "event_source_reference": "test",
            "proof_status": "draft_proof",
            "creates_live_action": "0",
        },
    ]

    latest = latest_restock_session_supplier_proof_events(pd.DataFrame(rows))

    assert len(latest.index) == 1
    assert latest.iloc[0]["proof_id"] == "proof-new"
    assert latest.iloc[0]["supplier_stock_state"] == "supplier_stock_verified_zero"
