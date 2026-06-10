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

from scripts.flows.O.O484_build_po_preview_construction_summary import build_po_preview_construction_summary
from scripts.flows.O._contract_io import write_o_contract_df


OBSERVED = "2026-06-03T14:45:00Z"
STAGES = (
    (
        "restock_po_draft_readiness_preview_lines_live",
        "restock_po_draft_readiness_preview_health",
        "po_draft_readiness_state",
        "ready_for_local_po_draft_review_only",
    ),
    (
        "restock_po_line_design_preview_lines_live",
        "restock_po_line_design_preview_health",
        "line_design_state",
        "ready_for_local_po_line_design_review_only",
    ),
    (
        "restock_po_draft_packet_review_lines_live",
        "restock_po_draft_packet_review_health",
        "packet_review_line_state",
        "ready_for_local_po_draft_packet_review_only",
    ),
    (
        "restock_po_draft_hold_review_lines_live",
        "restock_po_draft_hold_review_health",
        "hold_review_line_state",
        "held_for_local_po_draft_review_only",
    ),
    (
        "restock_po_draft_file_shape_preview_lines_live",
        "restock_po_draft_file_shape_preview_health",
        "file_shape_line_state",
        "ready_for_local_po_draft_file_shape_review_only",
    ),
)


def _write_stage_sources(tmp_path: Path, *, bad_health_contract: str = "", skip_contract: str = "") -> None:
    for line_contract, health_contract, state_column, ready_state in STAGES:
        if line_contract != skip_contract:
            write_o_contract_df(
                tmp_path,
                line_contract,
                pd.DataFrame(
                    [
                        {
                            state_column: ready_state,
                            "row_id": f"{line_contract}-row",
                            "seller_sku": "SKU1",
                            "po_file_write_allowed": "0",
                            "po_creation_allowed": "0",
                            "purchase_commitment_allowed": "0",
                            "receiving_allowed": "0",
                            "send_to_amazon_allowed": "0",
                            "creates_live_action": "0",
                        }
                    ]
                ),
            )
        if health_contract != skip_contract:
            status = "fail" if health_contract == bad_health_contract else "ok"
            write_o_contract_df(
                tmp_path,
                health_contract,
                pd.DataFrame(
                    [
                        {
                            "check_utc": OBSERVED,
                            "check": "local_only_guard",
                            "status": status,
                            "value": "live_action_rows=0",
                            "notes": "local",
                            "source_path": "test",
                        }
                    ]
                ),
            )


def test_o484_builds_local_po_preview_construction_summary(tmp_path: Path) -> None:
    _write_stage_sources(tmp_path)

    summary_df, health_df = build_po_preview_construction_summary(
        root=tmp_path,
        summary_utc=OBSERVED,
        refresh_file_shape=False,
    )

    assert len(summary_df.index) == 5
    assert set(summary_df["stage_state"].tolist()) == {"local_preview_ready_or_held"}
    assert set(summary_df["po_file_write_allowed"].tolist()) == {"0"}
    assert set(summary_df["po_creation_allowed"].tolist()) == {"0"}
    assert set(summary_df["purchase_commitment_allowed"].tolist()) == {"0"}
    assert set(summary_df["receiving_allowed"].tolist()) == {"0"}
    assert set(summary_df["send_to_amazon_allowed"].tolist()) == {"0"}
    assert set(summary_df["creates_live_action"].tolist()) == {"0"}
    assert set(health_df["status"].tolist()) == {"ok"}


def test_o484_fails_when_source_stage_health_is_bad(tmp_path: Path) -> None:
    _write_stage_sources(
        tmp_path,
        bad_health_contract="restock_po_draft_packet_review_health",
    )

    summary_df, health_df = build_po_preview_construction_summary(
        root=tmp_path,
        summary_utc=OBSERVED,
        refresh_file_shape=False,
    )

    packet_row = summary_df[summary_df["stage_key"] == "po_draft_packet_review"].iloc[0]
    assert packet_row["stage_state"] == "blocked_by_stage_health"
    assert packet_row["health_bad_rows"] == "1"
    assert "source_health_not_ok" in packet_row["stage_block_reasons"]
    assert "fail" in set(health_df["status"].tolist())


def test_o484_fails_when_source_stage_file_is_missing(tmp_path: Path) -> None:
    _write_stage_sources(
        tmp_path,
        skip_contract="restock_po_draft_file_shape_preview_lines_live",
    )

    summary_df, health_df = build_po_preview_construction_summary(
        root=tmp_path,
        summary_utc=OBSERVED,
        refresh_file_shape=False,
    )

    file_shape_row = summary_df[summary_df["stage_key"] == "po_draft_file_shape"].iloc[0]
    assert file_shape_row["stage_state"] == "not_verified_missing_source"
    assert "missing_stage_file" in file_shape_row["stage_block_reasons"]
    assert "fail" in set(health_df["status"].tolist())
