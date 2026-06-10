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

from scripts.flows.O.O460_build_restock_session_view import build_restock_session_view
from scripts.flows.O.O462_restock_session_draft_decisions import (
    build_restock_session_draft_row,
    submit_restock_session_draft_decision,
    validate_restock_session_draft_decision,
)
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-02T19:55:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _write_minimal_session_source(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": OBSERVED,
                "seller_sku": "SKU-DRAFT",
                "asin": "ASIN-DRAFT",
                "supplier_code": "SUP",
                "supplier_name": "Supplier",
                "recommendation_status": "test_restock",
                "suggested_qty": "2",
                "suggested_unit_cost_gbp": "5",
                "suggested_market_price_gbp": "12",
                "expected_forward_roi_pct": "20",
                "expected_forward_profit_per_unit_gbp": "2",
                "reason_codes": "ROI_OK",
                "queue_status": "ready",
            }
        ],
    )


def test_o462_saves_local_order_qty_and_o460_merges_latest_draft(tmp_path: Path) -> None:
    _write_minimal_session_source(tmp_path)
    review_df, _summary_df, _reason_df, _health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
    )
    session_row = review_df.iloc[0].to_dict()

    saved = submit_restock_session_draft_decision(
        root=tmp_path,
        session_row=session_row,
        decision_code="order_qty_draft",
        draft_order_qty="4",
        decision_note="draft four units",
        actor="operator_ui",
        event_source_reference="test",
    )

    assert saved["creates_live_action"] == "0"
    assert saved["draft_status"] == "draft"
    assert saved["decision_code"] == "order_qty_draft"
    assert saved["draft_order_qty"] == "4"

    event_df = read_o_contract_df(tmp_path, "restock_session_draft_decision_events")
    assert len(event_df.index) == 1
    assert set(event_df["creates_live_action"].tolist()) == {"0"}

    review_df, summary_df, _reason_df, health_df = build_restock_session_view(
        root=tmp_path,
        session_utc=OBSERVED,
        write_outputs=False,
    )
    merged = review_df.set_index("seller_sku").loc["SKU-DRAFT"]

    assert merged["operator_decision_state"] == "order_qty_draft"
    assert merged["order_qty_draft"] == "4"
    assert merged["latest_draft_decision_code"] == "order_qty_draft"
    assert merged["latest_draft_note"] == "draft four units"
    assert merged["draft_order_value_gbp"] == "20"
    assert summary_df.set_index("supplier_name").loc["Supplier", "draft_order_qty_total"] == "4"
    assert summary_df.set_index("supplier_name").loc["Supplier", "draft_order_value_gbp"] == "20"
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o462_rejects_unsafe_or_incomplete_draft_decisions(tmp_path: Path) -> None:
    session_row = {
        "session_id": "o_restock_session_v1",
        "row_id": "o_restock_session_v1:native_o:supplier:sku",
        "seller_sku": "SKU-DRAFT",
        "asin": "ASIN-DRAFT",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_class": "native_o",
        "source_reference": "native_o:SKU-DRAFT",
    }

    with pytest.raises(ValueError, match="unsupported_decision_code"):
        submit_restock_session_draft_decision(
            root=tmp_path,
            session_row=session_row,
            decision_code="create_purchase_order",
            actor="operator_ui",
        )

    with pytest.raises(ValueError, match="order_qty_draft_requires_positive_whole_quantity"):
        submit_restock_session_draft_decision(
            root=tmp_path,
            session_row=session_row,
            decision_code="order_qty_draft",
            draft_order_qty="1.5",
            actor="operator_ui",
        )

    with pytest.raises(ValueError, match="snooze_requires_valid_date"):
        submit_restock_session_draft_decision(
            root=tmp_path,
            session_row=session_row,
            decision_code="snooze",
            actor="operator_ui",
        )

    bad_row = build_restock_session_draft_row(
        session_row=session_row,
        decision_code="drop",
        actor="operator_ui",
    )
    bad_row["creates_live_action"] = "1"

    assert "creates_live_action_must_be_zero" in validate_restock_session_draft_decision(bad_row)
