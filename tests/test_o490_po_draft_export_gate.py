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

from scripts.flows.O.O490_build_po_draft_export_gate import (
    build_po_draft_export_gate,
    submit_po_draft_export_gate_event,
)
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T17:30:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _export_summary(
    *,
    state: str = "ready_for_local_po_draft_export_preview_only",
    line_count: str = "1",
    ready_count: str = "1",
    blocked_count: str = "0",
    po_file_write_allowed: str = "0",
) -> dict[str, str]:
    return {
        "export_preview_utc": OBSERVED,
        "po_draft_export_preview_id": "export-preview-1",
        "po_draft_file_shape_preview_id": "file-shape-1",
        "po_draft_hold_review_id": "hold-review-1",
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "line_count": line_count,
        "ready_line_count": ready_count,
        "blocked_line_count": blocked_count,
        "export_preview_qty_total": "2",
        "export_preview_value_gbp": "6",
        "export_preview_state": state,
        "export_preview_block_reasons": "" if state == "ready_for_local_po_draft_export_preview_only" else "review_control_not_shape_ready",
        "po_file_write_allowed": po_file_write_allowed,
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
        "source_classes": "native_o",
    }


def _gate_event(decision_state: str = "local_export_candidate_ready_not_po") -> dict[str, str]:
    return {
        "event_utc": OBSERVED,
        "gate_event_id": "gate-event-1",
        "po_draft_export_preview_id": "export-preview-1",
        "po_draft_file_shape_preview_id": "file-shape-1",
        "po_draft_hold_review_id": "hold-review-1",
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_export_preview_utc": OBSERVED,
        "decision_state": decision_state,
        "expected_line_count": "1",
        "expected_ready_line_count": "1",
        "expected_blocked_line_count": "0",
        "expected_export_preview_value_gbp": "6",
        "decision_note": "local only",
        "actor": "operator_ui",
        "event_source_reference": "o_ui_po_draft_export_gate",
        "decision_status": "local_po_draft_export_gate",
        "po_file_write_allowed": "0",
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
        "source_classes": "native_o",
    }


def test_o490_builds_waiting_gate_without_event(tmp_path: Path) -> None:
    _write_contract_rows(tmp_path, "restock_po_draft_export_preview_summary_live", [_export_summary()])

    gates_df, health_df = build_po_draft_export_gate(
        root=tmp_path,
        gate_utc=OBSERVED,
        refresh_export_preview=False,
    )

    gate = gates_df.iloc[0]
    assert gate["export_gate_state"] == "waiting_for_local_export_gate_control"
    assert gate["export_gate_reasons"] == "no_local_export_gate_control"
    assert gate["po_file_write_allowed"] == "0"
    assert gate["po_creation_allowed"] == "0"
    assert gate["purchase_commitment_allowed"] == "0"
    assert gate["receiving_allowed"] == "0"
    assert gate["send_to_amazon_allowed"] == "0"
    assert gate["creates_live_action"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o490_saves_candidate_ready_gate_without_po_action(tmp_path: Path) -> None:
    summary = _export_summary()
    _write_contract_rows(tmp_path, "restock_po_draft_export_preview_summary_live", [summary])

    saved = submit_po_draft_export_gate_event(
        root=tmp_path,
        export_summary_row=summary,
        decision_state="local_export_candidate_ready_not_po",
        decision_note="checked locally",
    )
    gates_df, health_df = build_po_draft_export_gate(
        root=tmp_path,
        gate_utc=OBSERVED,
        refresh_export_preview=False,
    )

    gate = gates_df.iloc[0]
    assert saved["creates_live_action"] == "0"
    assert saved["po_creation_allowed"] == "0"
    assert gate["export_gate_state"] == "local_export_candidate_ready_not_po"
    assert gate["latest_decision_state"] == "local_export_candidate_ready_not_po"
    assert gate["po_file_write_allowed"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}

    events = read_o_contract_df(tmp_path, "restock_po_draft_export_gate_events")
    assert len(events.index) == 1


def test_o490_rejects_candidate_ready_when_export_preview_is_not_ready(tmp_path: Path) -> None:
    blocked_summary = _export_summary(
        state="blocked_from_local_po_draft_export_preview",
        ready_count="0",
        blocked_count="1",
    )

    with pytest.raises(ValueError, match="local_export_candidate_ready_requires_ready_export_preview"):
        submit_po_draft_export_gate_event(
            root=tmp_path,
            export_summary_row=blocked_summary,
            decision_state="local_export_candidate_ready_not_po",
        )


def test_o490_flags_manual_false_ready_event(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_export_preview_summary_live",
        [
            _export_summary(
                state="blocked_from_local_po_draft_export_preview",
                ready_count="0",
                blocked_count="1",
            )
        ],
    )
    _write_contract_rows(tmp_path, "restock_po_draft_export_gate_events", [_gate_event()])

    gates_df, health_df = build_po_draft_export_gate(
        root=tmp_path,
        gate_utc=OBSERVED,
        refresh_export_preview=False,
    )

    gate = gates_df.iloc[0]
    assert gate["export_gate_state"] == "blocked_false_local_export_candidate_ready"
    assert "candidate_ready_decision_without_ready_export_preview" in gate["export_gate_reasons"]
    assert "fail" in set(health_df["status"].tolist())
