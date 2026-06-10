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

from scripts.flows.O.O486_build_po_draft_review_controls import (
    build_po_draft_review_controls,
    submit_po_draft_review_control_event,
)
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


OBSERVED = "2026-06-03T15:30:00Z"


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    write_o_contract_df(tmp_path, contract_name, pd.DataFrame(rows))


def _file_shape_summary(
    *,
    state: str = "ready_for_local_po_draft_file_shape_review_only",
    line_count: str = "1",
    ready_count: str = "1",
    blocked_count: str = "0",
    po_file_write_allowed: str = "0",
) -> dict[str, str]:
    return {
        "shape_utc": OBSERVED,
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
        "file_shape_qty_total": "2",
        "file_shape_value_gbp": "6",
        "file_shape_state": state,
        "file_shape_block_reasons": "" if state == "ready_for_local_po_draft_file_shape_review_only" else "source_hold_review_not_ready",
        "po_file_write_allowed": po_file_write_allowed,
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
        "source_classes": "native_o",
    }


def _control_event(decision_state: str = "local_po_draft_shape_ready_not_po") -> dict[str, str]:
    return {
        "event_utc": OBSERVED,
        "control_event_id": "control-event-1",
        "po_draft_file_shape_preview_id": "file-shape-1",
        "po_draft_hold_review_id": "hold-review-1",
        "po_draft_packet_review_id": "packet-review-1",
        "po_line_design_packet_id": "line-design-packet-1",
        "approval_packet_id": "packet-1",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_shape_utc": OBSERVED,
        "decision_state": decision_state,
        "expected_line_count": "1",
        "expected_ready_line_count": "1",
        "expected_blocked_line_count": "0",
        "expected_file_shape_value_gbp": "6",
        "decision_note": "local only",
        "actor": "operator_ui",
        "event_source_reference": "o_ui_po_draft_review_controls",
        "decision_status": "local_po_draft_review_control",
        "po_file_write_allowed": "0",
        "po_creation_allowed": "0",
        "purchase_commitment_allowed": "0",
        "receiving_allowed": "0",
        "send_to_amazon_allowed": "0",
        "creates_live_action": "0",
        "source_classes": "native_o",
    }


def test_o486_builds_waiting_control_without_event(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_file_shape_preview_summary_live",
        [_file_shape_summary()],
    )

    controls_df, health_df = build_po_draft_review_controls(
        root=tmp_path,
        control_utc=OBSERVED,
        refresh_construction_summary=False,
    )

    control = controls_df.iloc[0]
    assert control["review_control_state"] == "waiting_for_local_po_draft_review_control"
    assert control["review_control_reasons"] == "no_local_po_draft_review_control"
    assert control["po_file_write_allowed"] == "0"
    assert control["po_creation_allowed"] == "0"
    assert control["purchase_commitment_allowed"] == "0"
    assert control["receiving_allowed"] == "0"
    assert control["send_to_amazon_allowed"] == "0"
    assert control["creates_live_action"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o486_saves_local_shape_ready_control_without_po_action(tmp_path: Path) -> None:
    summary = _file_shape_summary()
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_file_shape_preview_summary_live",
        [summary],
    )

    saved = submit_po_draft_review_control_event(
        root=tmp_path,
        file_shape_summary_row=summary,
        decision_state="local_po_draft_shape_ready_not_po",
        decision_note="checked locally",
    )
    controls_df, health_df = build_po_draft_review_controls(
        root=tmp_path,
        control_utc=OBSERVED,
        refresh_construction_summary=False,
    )

    control = controls_df.iloc[0]
    assert saved["creates_live_action"] == "0"
    assert saved["po_creation_allowed"] == "0"
    assert control["review_control_state"] == "local_po_draft_shape_ready_not_po"
    assert control["latest_decision_state"] == "local_po_draft_shape_ready_not_po"
    assert control["po_file_write_allowed"] == "0"
    assert set(health_df["status"].tolist()) == {"ok"}

    events = read_o_contract_df(tmp_path, "restock_po_draft_review_control_events")
    assert len(events.index) == 1


def test_o486_rejects_shape_ready_when_file_shape_is_not_ready(tmp_path: Path) -> None:
    blocked_summary = _file_shape_summary(
        state="blocked_from_local_po_draft_file_shape_review",
        ready_count="0",
        blocked_count="1",
    )

    with pytest.raises(ValueError, match="local_po_draft_shape_ready_requires_ready_file_shape"):
        submit_po_draft_review_control_event(
            root=tmp_path,
            file_shape_summary_row=blocked_summary,
            decision_state="local_po_draft_shape_ready_not_po",
        )


def test_o486_flags_manual_false_ready_event(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_file_shape_preview_summary_live",
        [
            _file_shape_summary(
                state="blocked_from_local_po_draft_file_shape_review",
                ready_count="0",
                blocked_count="1",
            )
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_review_control_events",
        [_control_event()],
    )

    controls_df, health_df = build_po_draft_review_controls(
        root=tmp_path,
        control_utc=OBSERVED,
        refresh_construction_summary=False,
    )

    control = controls_df.iloc[0]
    assert control["review_control_state"] == "blocked_false_local_po_draft_shape_ready"
    assert "shape_ready_decision_without_ready_file_shape" in control["review_control_reasons"]
    assert "fail" in set(health_df["status"].tolist())
