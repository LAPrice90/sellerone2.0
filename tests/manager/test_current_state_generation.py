from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.current_state import build_and_write_current_state, build_current_state
from sellerone_manager.schemas import APPROVED_TASK_PACKET_COLUMNS


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_manager_outputs(root: Path, *, status: str = "ok", needs_user: str = "0") -> None:
    output_dir = root / "out" / "systems" / "M"
    _write_csv(
        output_dir / "f_price_list_manager_snapshot.csv",
        [
            "observed_utc",
            "status",
            "active_blocker_summary",
            "needs_user",
            "user_action",
        ],
        [
            {
                "observed_utc": "2026-05-26T12:00:00Z",
                "status": status,
                "active_blocker_summary": "No active F manager blocker detected by the read-only manager.",
                "needs_user": needs_user,
                "user_action": "No user action." if needs_user == "0" else "Upload the missing supplier file.",
            }
        ],
    )
    _write_csv(
        output_dir / "manager_health.csv",
        ["check", "status", "value", "notes", "observed_utc", "source_path"],
        [
            {
                "check": "manager_execution",
                "status": "ok",
                "value": "0",
                "notes": "0 active manager execution errors",
            }
        ],
    )
    _write_csv(
        output_dir / "manager_incidents.csv",
        ["observed_utc", "flow", "severity", "incident_code", "summary", "needs_user", "root_artifact", "remediation_hint"],
        [],
    )
    _write_csv(
        output_dir / "codex_repair_queue.csv",
        ["task_id", "status", "task_summary"],
        [],
    )
    _write_csv(
        output_dir / "self_organisation" / "latest_f_manifest_priority_ranking.csv",
        ["rank", "script_path", "recommended_action", "priority_band"],
        [
            {
                "rank": "1",
                "script_path": "scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py",
                "recommended_action": "candidate_manifest",
                "priority_band": "top_3",
            }
        ],
    )
    (output_dir / "latest_f_price_list_manager_report.md").write_text("# report\n", encoding="utf-8")


def test_current_state_generation_uses_manager_outputs_only(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path)

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert state["system_status"] == "OK"
    assert state["manager_execution_errors"] == 0
    assert state["active_flow"] == "F Price List Manager"
    assert state["luke_action_required"] is False
    assert state["luke_action"] == "No Luke decision needed from this manager snapshot."
    assert state["codex_task_available"] is True
    assert state["codex_task_title"] == "Create manager manifests for: FPM060_build_status_dashboard"
    assert state["current_state"].startswith("No Luke decision needed")
    assert state["latest_evidence"]["manager_report"].endswith("latest_f_price_list_manager_report.md")


def test_current_state_json_is_written_as_canonical_state(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path)

    state, path = build_and_write_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert path == tmp_path / "sellerone_manager" / "current_state.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["system_status"] == "OK"
    assert payload["current_state_path"] == str(path)
    assert payload["next_safe_batch"] == state["next_safe_batch"]


def test_current_state_marks_true_luke_action(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path, status="needs_user", needs_user="1")

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert state["system_status"] == "BLOCKED"
    assert state["luke_action_required"] is True
    assert state["luke_action"] == "Upload the missing supplier file."


def test_current_state_reads_mot_worklist_as_codex_task(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "mot" / "mot_worklist.csv",
        [
            "work_item_id",
            "status",
            "title",
            "luke_action_required",
            "safe_repair_boundary",
            "manager_action",
        ],
        [
            {
                "work_item_id": "MOT_A_A001_LISTINGS_LATEST",
                "status": "new",
                "title": "A MOT: a001_listings_latest needs repair",
                "luke_action_required": "0",
                "safe_repair_boundary": "A001 local refresh code only.",
                "manager_action": "Separate local refresh from legacy Sheet writing.",
            }
        ],
    )

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert state["system_status"] == "BLOCKED"
    assert state["luke_action_required"] is False
    assert state["codex_task_available"] is True
    assert state["codex_task_title"].startswith("MOT_A_A001_LISTINGS_LATEST")


def test_parked_business_decision_does_not_stop_safe_approved_task(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {
                "task_id": "MOT_A_A001_LISTINGS_LATEST",
                "source_type": "mot",
                "source_id": "MOT_A_A001_LISTINGS_LATEST",
                "flow": "A",
                "task_type": "bounded_code_repair",
                "authority": "standing_safe_code_repair",
                "status": "approved",
                "priority": "high",
                "title": "A MOT: a001_listings_latest needs repair",
                "allowed_scope": "A001 local refresh code only.",
                "luke_action_required": "0",
            },
            {
                "task_id": "MOT_B_B_ORDER_PROMOTION_PREVIEW",
                "source_type": "mot",
                "source_id": "MOT_B_B_ORDER_PROMOTION_PREVIEW",
                "flow": "B",
                "task_type": "blocked_decision",
                "authority": "needs_luke_decision",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "B MOT: b_order_promotion_preview needs Luke decision",
                "luke_action_required": "1",
                "notes": "Luke must approve the protected B order promotion repair window before Codex can write live B outputs.",
            },
        ],
    )

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert state["luke_action_required"] is False
    assert state["codex_task_available"] is True
    assert state["codex_task_title"].startswith("MOT_A_A001_LISTINGS_LATEST")
    assert "approved task packet" in state["current_state"]


def test_blocked_repair_packet_is_luke_action_before_background_decision(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {
                "task_id": "MGR_F_user_decision_out_systems_F_live_f_log",
                "source_type": "manager_candidate",
                "source_id": "F_user_decision_out_systems_F_live_f_log",
                "flow": "F",
                "task_type": "blocked_decision",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "Review unresolved Entertainment Trading dashboard Yes/No backtrack row",
                "luke_action_required": "1",
                "notes": "Background F decision.",
            },
            {
                "task_id": "MGR_H_repair_h_ceiling_events_required_fields_non_blank",
                "source_type": "repair_package",
                "source_id": "H_REPAIR_PACKAGE_current_failures",
                "flow": "H",
                "task_type": "bounded_code_repair",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "H Repair Package - Current Active Failures",
                "luke_action_required": "1",
                "notes": "Code fix applied; live retest now needs protected H scheduler pause approval.",
            },
        ],
    )

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert state["luke_action_required"] is True
    assert state["luke_action"] == (
        "MGR_H_repair_h_ceiling_events_required_fields_non_blank - "
        "Code fix applied; live retest now needs protected H scheduler pause approval."
    )


def test_resolved_f_parked_decision_packet_is_not_luke_action(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "mot" / "mot_latest.csv",
        ["observed_utc", "flow", "check", "status", "value", "luke_action_required"],
        [
            {
                "observed_utc": "2026-05-26T12:15:00Z",
                "flow": "F",
                "check": "f_parked_decision_rows",
                "status": "ok",
                "value": "0",
                "luke_action_required": "0",
            }
        ],
    )
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {
                "task_id": "MGR_F_user_decision_out_systems_F_live_f_log",
                "source_type": "manager_candidate",
                "source_id": "F_user_decision_out_systems_F_live_f_log",
                "flow": "F",
                "task_type": "blocked_decision",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "Review unresolved Entertainment Trading dashboard Yes/No backtrack row",
                "luke_action_required": "1",
                "notes": "Still unresolved for supplier_sku 1243976.",
            },
        ],
    )

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert state["luke_action_required"] is False
    assert "Entertainment Trading" not in state["luke_action"]


def test_unresolved_f_parked_decision_stays_out_of_main_blocker(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {
                "task_id": "MGR_F_user_decision_out_systems_F_live_f_log",
                "source_type": "manager_candidate",
                "source_id": "F_user_decision_out_systems_F_live_f_log",
                "flow": "F",
                "task_type": "blocked_decision",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "Review unresolved Entertainment Trading dashboard Yes/No backtrack row",
                "luke_action_required": "1",
                "notes": "Still unresolved for supplier_sku 1243976 / ASIN B0000DC4EL.",
            },
        ],
    )

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert state["luke_action_required"] is False
    assert state["system_status"] == "OK"
    assert "Entertainment Trading" not in state["luke_action"]


def test_blocked_approved_task_stays_visible_when_safe_task_exists(tmp_path: Path) -> None:
    _write_manager_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {
                "task_id": "MOT_A_A001_LISTINGS_LATEST",
                "source_type": "mot",
                "source_id": "MOT_A_A001_LISTINGS_LATEST",
                "flow": "A",
                "task_type": "bounded_code_repair",
                "authority": "standing_safe_code_repair",
                "status": "approved",
                "priority": "high",
                "title": "A MOT: a001_listings_latest needs repair",
                "allowed_scope": "A001 local refresh code only.",
                "luke_action_required": "0",
            },
            {
                "task_id": "MOT_B_B_SELLERBOARD_EMAIL_ADMIN_INBOX_ACCESS",
                "source_type": "mot",
                "source_id": "MOT_B_B_SELLERBOARD_EMAIL_ADMIN_INBOX_ACCESS",
                "flow": "B",
                "task_type": "blocked_decision",
                "authority": "needs_luke_decision",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "B MOT: b_sellerboard_email_admin_inbox_access needs Luke decision",
                "luke_action_required": "1",
                "notes": "Luke must connect or re-authorize local Gmail OAuth access for admin@drjselect.co.uk.",
            },
        ],
    )

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:30:00Z")

    assert state["luke_action_required"] is True
    assert "admin@drjselect.co.uk" in state["luke_action"]
    assert state["codex_task_available"] is True
    assert state["codex_task_title"].startswith("MOT_A_A001_LISTINGS_LATEST")
    assert state["next_safe_batch"].startswith("Claim or continue approved manager task MOT_A_A001_LISTINGS_LATEST")
