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

from scripts.flows.O.O468_restock_pack_moq_proof_events import (
    build_restock_session_pack_moq_proof_row,
    latest_restock_session_pack_moq_proof_events,
    submit_restock_session_pack_moq_proof_event,
    validate_restock_session_pack_moq_proof_event,
)
from scripts.flows.O._contract_io import read_o_contract_df


SESSION_ROW = {
    "session_id": "o_restock_session_v1",
    "row_id": "o_restock_session_v1:native_o:supplier:sku",
    "seller_sku": "SKU-PACK",
    "asin": "ASIN-PACK",
    "supplier_name": "Supplier",
    "supplier_code": "SUP",
    "source_class": "native_o",
    "row_source_reference": "native_o:SKU-PACK",
    "title": "Pack Product",
    "supplier_sku": "SUP-PACK",
    "barcode": "123",
}


def test_o468_saves_pack_moq_proof_event_as_local_only(tmp_path: Path) -> None:
    saved = submit_restock_session_pack_moq_proof_event(
        root=tmp_path,
        session_row=SESSION_ROW,
        pack_moq_proof_state="pack_moq_verified",
        pack_multiple="6",
        supplier_moq="12",
        valid_order_step="6",
        proof_file_reference="pack-file.csv",
        proof_note="checked pack and MOQ",
        actor="tester",
        event_source_reference="test",
    )

    assert saved["proof_id"].startswith("o-session-pack-moq-proof-")
    assert saved["pack_moq_proof_state"] == "pack_moq_verified"
    assert saved["pack_multiple"] == "6"
    assert saved["supplier_moq"] == "12"
    assert saved["valid_order_step"] == "6"
    assert saved["proof_status"] == "draft_proof"
    assert saved["creates_live_action"] == "0"

    event_df = read_o_contract_df(tmp_path, "restock_session_pack_moq_proof_events")
    assert len(event_df.index) == 1
    assert event_df.iloc[0]["creates_live_action"] == "0"


def test_o468_rejects_bad_pack_moq_states() -> None:
    with pytest.raises(ValueError) as exc:
        build_restock_session_pack_moq_proof_row(
            session_row=SESSION_ROW,
            pack_moq_proof_state="buy_now",
            valid_order_step="1",
        )

    assert "missing_pack_moq_proof_state" in str(exc.value)


def test_o468_validation_catches_live_action_attempt() -> None:
    row = build_restock_session_pack_moq_proof_row(
        session_row=SESSION_ROW,
        pack_moq_proof_state="pack_moq_verified",
        pack_multiple="1",
        valid_order_step="1",
    )
    row["creates_live_action"] = "1"

    assert "creates_live_action_must_be_zero" in validate_restock_session_pack_moq_proof_event(row)


def test_o468_latest_pack_moq_proof_keeps_newest_safe_event() -> None:
    rows = [
        {
            **SESSION_ROW,
            "event_utc": "2026-06-02T10:00:00Z",
            "proof_id": "proof-old",
            "pack_moq_proof_state": "pack_moq_verified",
            "pack_multiple": "1",
            "supplier_moq": "",
            "valid_order_step": "1",
            "proof_file_reference": "old.csv",
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
            "pack_moq_proof_state": "pack_moq_verified",
            "pack_multiple": "6",
            "supplier_moq": "12",
            "valid_order_step": "6",
            "proof_file_reference": "new.csv",
            "proof_note": "new",
            "actor": "tester",
            "event_source_reference": "test",
            "proof_status": "draft_proof",
            "creates_live_action": "0",
        },
    ]

    latest = latest_restock_session_pack_moq_proof_events(pd.DataFrame(rows))

    assert len(latest.index) == 1
    assert latest.iloc[0]["proof_id"] == "proof-new"
    assert latest.iloc[0]["valid_order_step"] == "6"
