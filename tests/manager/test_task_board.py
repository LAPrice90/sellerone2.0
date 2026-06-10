from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.task_board import TaskCard, load_task_board, lane_names
from sellerone_manager.task_board_ui import _card_html, _needs_luke_html


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_task_index(root: Path) -> None:
    fields = [
        "task_id",
        "job_ref",
        "flow",
        "status",
        "priority",
        "title",
        "luke_action_required",
        "notes",
        "proof_required",
        "retest_command",
        "allowed_scope",
        "forbidden_actions",
        "packet_path",
        "source_path",
    ]
    _write_csv(
        root / "out" / "systems" / "M" / "approved_task_packets.csv",
        fields,
        [
            {
                "task_id": "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF",
                "job_ref": "F-EMAIL-SOURCE",
                "flow": "F",
                "status": "in_progress",
                "priority": "high",
                "title": "F MOT: email price-list source proof needs repair",
                "luke_action_required": "0",
                "notes": "fail=1",
                "proof_required": "Retest with F MOT.",
                "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
                "allowed_scope": "Email source proof only.",
                "forbidden_actions": "no F061 run; no queue edit; no price change",
                "packet_path": "sellerone_manager/tasks/approved/MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF.md",
            },
            {
                "task_id": "MOT_B_B_ORIGINAL_RETURN_STATUS_APPLY_DECISION",
                "job_ref": "B-ORIGINAL-TOKEN",
                "flow": "B",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "B original returned-token live-status repair needs protected decision",
                "luke_action_required": "1",
                "notes": "Protected original-token decision.",
                "proof_required": "Requires protected approval before live write.",
                "forbidden_actions": "no token correction without approval",
            },
            {
                "task_id": "MGR_O_RESTOCK_SESSION_V1",
                "job_ref": "O-RESTOCK-SESSION",
                "flow": "O",
                "status": "proved",
                "priority": "normal",
                "title": "O Restock Session v1",
                "luke_action_required": "0",
                "notes": "Proved history.",
            },
            {
                "task_id": "MGR_H_REPAIR_PACK",
                "job_ref": "H-REPAIR-PACK",
                "flow": "H",
                "status": "parked",
                "priority": "normal",
                "title": "H parked proof package",
                "luke_action_required": "0",
                "notes": "Parked until H manager proof exists.",
            },
        ],
    )


def test_task_board_maps_statuses_and_hides_proved_by_default(tmp_path: Path) -> None:
    _write_task_index(tmp_path)

    board = load_task_board(root=tmp_path)

    assert board.total_cards == 3
    assert board.lane_counts["In Progress"] == 1
    assert board.lane_counts["Blocked"] == 1
    assert board.lane_counts["Parked"] == 1
    assert {card.task_id for card in board.cards} == {
        "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF",
        "MOT_B_B_ORIGINAL_RETURN_STATUS_APPLY_DECISION",
        "MGR_H_REPAIR_PACK",
    }
    assert {card.job_ref for card in board.cards} == {
        "F-EMAIL-SOURCE",
        "B-ORIGINAL-TOKEN",
        "H-REPAIR-PACK",
    }


def test_task_board_can_include_proved_when_active_only_is_disabled(tmp_path: Path) -> None:
    _write_task_index(tmp_path)

    board = load_task_board(root=tmp_path, active_only=False)

    assert board.total_cards == 4
    assert board.lane_counts["Proven"] == 1
    assert "Proven" in lane_names(active_only=False)


def test_task_board_searches_by_job_ref_and_keeps_proved_hidden_by_default(tmp_path: Path) -> None:
    _write_task_index(tmp_path)

    board = load_task_board(root=tmp_path, search="F-EMAIL-SOURCE")

    assert board.total_cards == 1
    assert board.cards[0].task_id == "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF"

    hidden_proved = load_task_board(root=tmp_path, search="O-RESTOCK-SESSION")
    included_proved = load_task_board(root=tmp_path, active_only=False, search="O-RESTOCK-SESSION")

    assert hidden_proved.total_cards == 0
    assert included_proved.total_cards == 1
    assert included_proved.cards[0].lane == "Proven"


def test_task_board_handles_missing_inputs(tmp_path: Path) -> None:
    board = load_task_board(root=tmp_path)

    assert board.total_cards == 0
    assert board.lane_counts["Not Started"] == 0
    assert board.lane_counts["Blocked"] == 0


def test_task_board_ignores_malformed_task_ids(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        ["task_id", "flow", "status", "title"],
        [
            {
                "task_id": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow B`",
                "flow": "B",
                "status": "approved",
                "title": "Malformed row",
            }
        ],
    )

    board = load_task_board(root=tmp_path)

    assert board.total_cards == 0


def test_task_board_uses_mot_worklist_when_task_index_missing(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "mot" / "mot_worklist.csv",
        [
            "work_item_id",
            "job_ref",
            "flow",
            "status",
            "priority",
            "title",
            "luke_action_required",
            "manager_action",
            "proof_required",
            "retest_command",
            "safe_repair_boundary",
        ],
        [
            {
                "work_item_id": "MOT_A_TEST",
                "job_ref": "A-TEST",
                "flow": "A",
                "status": "new",
                "priority": "high",
                "title": "A MOT task",
                "luke_action_required": "0",
                "manager_action": "Package A proof.",
                "proof_required": "Retest with A MOT.",
                "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow A",
                "safe_repair_boundary": "A proof only.",
            }
        ],
    )

    board = load_task_board(root=tmp_path)

    assert board.total_cards == 1
    assert board.cards[0].flow == "A"
    assert board.cards[0].lane == "Not Started"


def test_task_board_does_not_show_luke_decision_wording_for_non_luke_parked_mot_card(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "mot" / "mot_worklist.csv",
        [
            "work_item_id",
            "job_ref",
            "flow",
            "status",
            "priority",
            "title",
            "luke_action_required",
            "manager_action",
        ],
        [
            {
                "work_item_id": "MOT_B_B_ORDER_TRUTH_COMPLETION",
                "job_ref": "B-ORDER-TRUTH",
                "flow": "B",
                "status": "parked",
                "priority": "normal",
                "title": "B MOT: b_order_truth_completion needs Luke decision",
                "luke_action_required": "0",
                "manager_action": "Keep bridge values labelled.",
            }
        ],
    )

    board = load_task_board(root=tmp_path)

    assert board.total_cards == 1
    assert board.cards[0].lane == "Parked"
    assert board.cards[0].luke_action_required is False
    assert "needs Luke decision" not in board.cards[0].title
    assert board.cards[0].title == "B MOT: b_order_truth_completion is parked"


def test_task_board_enriches_indexed_card_from_markdown_packet(tmp_path: Path) -> None:
    packet = tmp_path / "sellerone_manager" / "tasks" / "blocked" / "MOT_A_TEST.md"
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text(
        """# A blocked proof packet

## Manager Authority
- task_id: MOT_A_TEST
- job_ref: A-BLOCKED-PROOF
- status: blocked_needs_luke
- luke_action_required: 1

## Plain English
Luke must approve the protected proof.
""",
        encoding="utf-8",
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        ["task_id", "job_ref", "flow", "status", "priority", "title", "luke_action_required", "packet_path"],
        [
            {
                "task_id": "MOT_A_TEST",
                "job_ref": "",
                "flow": "A",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "A blocked proof packet",
                "luke_action_required": "1",
                "packet_path": str(packet),
            }
        ],
    )

    board = load_task_board(root=tmp_path)

    assert board.total_cards == 1
    assert board.cards[0].flow == "A"
    assert board.cards[0].job_ref == "A-BLOCKED-PROOF"
    assert board.cards[0].lane == "Blocked"
    assert board.cards[0].luke_action_required is True
    assert "Luke must approve" in board.cards[0].notes


def test_task_board_filters_flow_and_protected_only(tmp_path: Path) -> None:
    _write_task_index(tmp_path)

    board = load_task_board(root=tmp_path, flows=["B"], protected_only=True)

    assert board.total_cards == 1
    assert board.cards[0].task_id == "MOT_B_B_ORIGINAL_RETURN_STATUS_APPLY_DECISION"


def test_task_board_card_html_contains_cycle_and_status() -> None:
    card = TaskCard(
        task_id="MOT_F_TEST",
        title="F source proof card",
        job_ref="F-SOURCE-PROOF",
        flow="F",
        status="in_progress",
        lane="In Progress",
        priority="high",
        luke_action_required=False,
        source_type="mot",
        updated_utc="2026-06-04T08:00:00Z",
        notes="Source proof needs cleanup.",
        proof_required="Retest with F MOT.",
        retest_command="python -m sellerone_manager.app --hourly-mot --mot-flow F",
        allowed_scope="Read-only proof.",
        forbidden_actions="no F061 run; no queue edit",
        packet_path="sellerone_manager/tasks/approved/MOT_F_TEST.md",
        source_path="out/systems/F/proof.csv",
    )

    html = _card_html(card)

    assert card.flow in html
    assert "Job ref: F-SOURCE-PROOF" in html
    assert card.status.replace("_", " ") in html
    assert "Task id" in html
    assert "MOT_F_TEST" in html


def test_needs_luke_strip_lists_blocked_jobs_by_ref(tmp_path: Path) -> None:
    _write_task_index(tmp_path)
    board = load_task_board(root=tmp_path)

    html = _needs_luke_html(list(board.cards))

    assert "Needs Luke" in html
    assert "B-ORIGINAL-TOKEN" in html
    assert "MOT_B_B_ORIGINAL_RETURN_STATUS_APPLY_DECISION" not in html
