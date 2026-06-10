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

from scripts.flows.O.O472_build_purchase_approval_guardrails import (
    build_purchase_approval_guardrails,
    submit_purchase_approval_decision_event,
)
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T09:30:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _ready_summary() -> dict[str, str]:
    return {
        "preview_utc": OBSERVED,
        "approval_packet_id": "packet-ready",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "line_count": "2",
        "draft_order_qty_total": "6",
        "draft_order_value_gbp": "18",
        "ready_line_count": "2",
        "blocked_line_count": "0",
        "source_classes": "native_o",
        "approval_packet_state": "ready_for_purchase_approval_review_only",
        "approval_block_reasons": "",
        "creates_live_action": "0",
    }


def _blocked_summary() -> dict[str, str]:
    return {
        "preview_utc": OBSERVED,
        "approval_packet_id": "packet-blocked",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "line_count": "1",
        "draft_order_qty_total": "2",
        "draft_order_value_gbp": "6",
        "ready_line_count": "0",
        "blocked_line_count": "1",
        "source_classes": "native_o",
        "approval_packet_state": "blocked_from_purchase_approval_review",
        "approval_block_reasons": "supplier_stock_not_verified",
        "creates_live_action": "0",
    }


def test_o472_builds_local_only_guardrails_from_preview_packets(tmp_path: Path) -> None:
    ready = _ready_summary()
    blocked = _blocked_summary()
    _write_contract_rows(tmp_path, "restock_purchase_approval_preview_summary_live", [ready, blocked])

    submit_purchase_approval_decision_event(
        root=tmp_path,
        preview_summary_row=ready,
        decision_state="local_review_accept_not_commitment",
        decision_note="ready for next local design step",
    )
    submit_purchase_approval_decision_event(
        root=tmp_path,
        preview_summary_row=blocked,
        decision_state="local_review_more_proof_needed",
        decision_note="stock proof still missing",
    )

    events_df, guardrails_df, health_df = build_purchase_approval_guardrails(
        root=tmp_path,
        guardrail_utc=OBSERVED,
        refresh_preview=False,
    )

    assert len(events_df.index) == 2
    assert set(health_df["status"].tolist()) == {"ok"}
    ready_guard = guardrails_df[guardrails_df["approval_packet_id"] == "packet-ready"].iloc[0]
    blocked_guard = guardrails_df[guardrails_df["approval_packet_id"] == "packet-blocked"].iloc[0]
    assert ready_guard["approval_guardrail_state"] == "local_review_accept_not_commitment"
    assert ready_guard["creates_live_action"] == "0"
    assert blocked_guard["latest_decision_state"] == "local_review_more_proof_needed"
    assert blocked_guard["approval_guardrail_state"] == "blocked_preview_not_ready"
    assert "supplier_stock_not_verified" in blocked_guard["approval_guardrail_reasons"]

    written = read_o_contract_df(tmp_path, "restock_purchase_approval_guardrails_live")
    assert len(written.index) == 2


def test_o472_refuses_local_accept_for_blocked_preview_packet(tmp_path: Path) -> None:
    blocked = _blocked_summary()

    with pytest.raises(ValueError, match="local_review_accept_requires_ready_preview_packet"):
        submit_purchase_approval_decision_event(
            root=tmp_path,
            preview_summary_row=blocked,
            decision_state="local_review_accept_not_commitment",
        )


def test_o472_health_fails_malformed_live_action_decision_event(tmp_path: Path) -> None:
    ready = _ready_summary()
    _write_contract_rows(tmp_path, "restock_purchase_approval_preview_summary_live", [ready])
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_decision_events",
        [
            {
                "event_utc": OBSERVED,
                "decision_id": "bad-decision",
                "approval_packet_id": "packet-ready",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_preview_utc": OBSERVED,
                "decision_state": "local_review_accept_not_commitment",
                "expected_line_count": "2",
                "expected_ready_line_count": "2",
                "expected_blocked_line_count": "0",
                "expected_order_value_gbp": "18",
                "decision_note": "bad event",
                "actor": "operator_ui",
                "event_source_reference": "o_ui_purchase_approval_guardrails",
                "decision_status": "draft_guardrail_decision",
                "creates_live_action": "1",
            }
        ],
    )

    _events_df, guardrails_df, health_df = build_purchase_approval_guardrails(
        root=tmp_path,
        guardrail_utc=OBSERVED,
        refresh_preview=False,
    )

    assert guardrails_df.iloc[0]["approval_guardrail_state"] == "no_local_review_decision"
    assert health_df[health_df["check"] == "decision_event_contract"].iloc[0]["status"] == "fail"
    assert health_df[health_df["check"] == "local_only_guard"].iloc[0]["status"] == "fail"
