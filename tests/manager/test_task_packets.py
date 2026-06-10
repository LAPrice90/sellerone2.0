from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main
from sellerone_manager.current_state import build_current_state
from sellerone_manager.schemas import APPROVED_TASK_PACKET_COLUMNS
from sellerone_manager.task_packets import claim_next_approved_task, refresh_approved_task_packets, update_approved_task_status


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_base_manager_outputs(root: Path) -> None:
    output_dir = root / "out" / "systems" / "M"
    _write_csv(
        output_dir / "f_price_list_manager_snapshot.csv",
        ["observed_utc", "status", "active_blocker_summary", "needs_user", "user_action"],
        [
            {
                "observed_utc": "2026-05-26T12:00:00Z",
                "status": "ok",
                "active_blocker_summary": "No active F manager blocker detected by the read-only manager.",
                "needs_user": "0",
                "user_action": "No user action.",
            }
        ],
    )
    _write_csv(
        output_dir / "manager_health.csv",
        ["check", "status", "value", "notes", "observed_utc", "source_path"],
        [{"check": "manager_execution", "status": "ok", "value": "0", "notes": "0 active manager execution errors"}],
    )
    _write_csv(
        output_dir / "manager_incidents.csv",
        ["observed_utc", "flow", "severity", "incident_code", "summary", "needs_user", "root_artifact", "remediation_hint"],
        [],
    )
    _write_csv(output_dir / "codex_repair_queue.csv", ["task_id", "status", "task_summary"], [])
    _write_csv(
        output_dir / "self_organisation" / "latest_f_manifest_priority_ranking.csv",
        ["rank", "script_path", "recommended_action", "priority_band"],
        [],
    )


def _write_active_autonomy_policy(root: Path) -> None:
    path = root / "config" / "manager" / "autonomy_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "active",
                "controlled_technical_pause_resume_allowed": True,
                "business_decisions_delegated": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_quiet_autonomy_policy(root: Path) -> None:
    path = root / "config" / "manager" / "autonomy_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "active",
                "mode": "quiet_autonomy",
                "controlled_technical_pause_resume_allowed": True,
                "controlled_technical_pause_requires_controller": True,
                "business_decisions_delegated": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_flow_state(root: Path) -> None:
    _write_csv(
        root / "out" / "systems" / "M" / "flow_maintenance_state.csv",
        [
            "observed_utc",
            "flow",
            "rollout_rank",
            "status",
            "classification",
            "fail_count",
            "warn_count",
            "needs_luke_decision",
            "luke_decision",
        ],
        [
            {
                "observed_utc": "2026-05-26T12:00:00Z",
                "flow": "A",
                "rollout_rank": "1",
                "status": "ok",
                "classification": "calm",
                "fail_count": "0",
                "warn_count": "0",
                "needs_luke_decision": "0",
                "luke_decision": "",
            }
        ],
    )


def _mot_worklist_columns() -> list[str]:
    return [
        "observed_utc",
        "created_utc",
        "updated_utc",
        "last_seen_utc",
        "seen_count",
        "work_item_id",
        "job_ref",
        "flow",
        "check",
        "producer",
        "title",
        "status",
        "priority",
        "source_path",
        "root_cause_guess",
        "manager_action",
        "allowed_scope",
        "forbidden_actions",
        "proof_required",
        "retest_command",
        "safe_repair_boundary",
        "luke_action_required",
        "notes",
    ]


def _write_mot_worklist(root: Path, *, status: str = "new", luke: str = "0") -> None:
    _write_csv(
        root / "out" / "systems" / "M" / "mot" / "mot_worklist.csv",
        _mot_worklist_columns(),
        [
            {
                "observed_utc": "2026-05-26T12:00:00Z",
                "created_utc": "2026-05-26T12:00:00Z",
                "updated_utc": "2026-05-26T12:00:00Z",
                "last_seen_utc": "2026-05-26T12:00:00Z",
                "seen_count": "1",
                "work_item_id": "MOT_A_A001_LISTINGS_LATEST",
                "job_ref": "",
                "flow": "A",
                "check": "a001_listings_latest",
                "producer": "A001_run_listings_to_sheet.py",
                "title": "A MOT: a001_listings_latest needs repair",
                "status": status,
                "priority": "high",
                "source_path": "out/merchant_listings_latest.csv",
                "root_cause_guess": "Expected A output is stale.",
                "manager_action": "Repair local refresh only.",
                "allowed_scope": "A001 local refresh code only.",
                "forbidden_actions": "no price changes; no queue edits; no legacy Sheet writes",
                "proof_required": "Retest with MOT.",
                "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow A",
                "safe_repair_boundary": "A001 local refresh code only.",
                "luke_action_required": luke,
                "notes": "stale",
            }
        ],
    )


def _write_manager_candidate(
    root: Path,
    *,
    status: str = "proposed",
    needs_luke: str = "0",
    flow: str = "B",
    task_id: str = "B_repair_out_cycle_alerts",
    title: str = "Repair B active FAIL group",
    root_artifact: str = "out/cycle_alerts/checklist_B_split.csv",
    notes: str = "1 active fail row found.",
) -> None:
    _write_csv(
        root / "out" / "systems" / "M" / "manager_task_candidates.csv",
        [
            "observed_utc",
            "flow",
            "task_id",
            "job_ref",
            "task_type",
            "priority",
            "status",
            "title",
            "root_artifact",
            "allowed_scope",
            "forbidden_actions",
            "proof_required",
            "stop_condition",
            "needs_luke_decision",
            "notes",
        ],
        [
            {
                "observed_utc": "2026-05-26T12:00:00Z",
                "flow": flow,
                "task_id": task_id,
                "job_ref": "",
                "task_type": "repair",
                "priority": "high",
                "status": status,
                "title": title,
                "root_artifact": root_artifact,
                "allowed_scope": f"manager classification, {flow} proof planning, and scoped Codex repair task creation",
                "forbidden_actions": "no overlapping B run; no worker restart; no legacy Sheet write",
                "proof_required": f"Use {flow} maintenance handoff only when a proof window is approved.",
                "stop_condition": "Stop after manager classification and task packaging.",
                "needs_luke_decision": needs_luke,
                "notes": notes,
            }
        ],
    )


def _write_h_repair_package(
    root: Path,
    *,
    suffix: str = "",
    root_cause_line: str = "- The active H FAIL group is one checklist row: `h_strategy_outcome_daily_count_integrity`.",
    proof_heading: str = "Proof Path For A Future Repair",
) -> Path:
    package_path = (
        root
        / "plans"
        / "active"
        / "sellerone-manager-control-plane-v1"
        / f"H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli{suffix}.md"
    )
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(
        f"""# H Repair Package - MGR_H_repair_out_cycle_alerts_checkli

## Root Cause Summary
{root_cause_line}

## Allowed Files For A Future Repair Batch
- `scripts/phase1/phase1_storage.py`
- focused H rollup tests under `tests/`
- `out/h_strategy_outcome_daily.csv` only through generated rebuild path after timestamped backup

## Forbidden Files And Actions
- Do not change prices.
- Do not write Google Sheets.
- Do not edit queues.
- Do not change scheduler ownership.

## {proof_heading}
- Re-aggregate `out/h_strategy_outcome_log.csv`.
- Run focused tests.

## Rollback Path
- Restore timestamped backups of `out/h_strategy_outcome_daily.csv`.

## Stop Condition
- Stop if the repair crosses a protected boundary.
""",
        encoding="utf-8",
    )
    return package_path


def _write_b_repair_package(root: Path) -> Path:
    package_path = (
        root
        / "plans"
        / "active"
        / "sellerone-manager-control-plane-v1"
        / "B_REPAIR_PACKAGE_MOT_B_B_SELLERBOARD_REFUND_FEE_ROI_BRIDGE_20260531.md"
    )
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(
        """# B Repair Package - Refund Fee Shipping ROI Proof

## Root Cause Summary
- The active B warning is `b_sellerboard_refund_fee_roi_bridge`.
- Refund, fee, shipping, and ROI support is visible, but not fully API-proven.

## Allowed Files For A Future Repair Batch
- `sellerone_manager/sellerboard_bridge.py`
- `sellerone_manager/hourly_mot.py`
- focused B manager tests under `tests/manager/`

## Forbidden Files And Actions
- Do not run or restart B.
- Do not write Google Sheets.
- Do not correct token or order data.
- Do not align local DB facts.
- Do not delete outputs.
- Do not use Sellerboard bridge values as final ROI or restocking truth.
- Do not change prices or queues.

## Proof Path For A Future Repair
- Keep Sellerboard values labelled as bridge evidence only.
- Add or confirm API-backed labels for refund, fee, shipping, and ROI evidence.
- Retest B through the independent MOT.

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow B

## Rollback Path
- Use git diff for code rollback.
- Do not rewrite business data outputs to make the warning disappear.

## Stop Condition
- Stop when B MOT can prove the bridge is API-backed or correctly labelled as not yet proven.
- Stop immediately if the repair would require data correction, live B run, DB alignment, Sheets, prices, or queues.
""",
        encoding="utf-8",
    )
    return package_path


def _write_e_repair_package(root: Path) -> Path:
    package_path = (
        root
        / "plans"
        / "active"
        / "sellerone-manager-control-plane-v1"
        / "E_REPAIR_PACKAGE_E_CONFIDENCE_ROI_CONSUMPTION_SAFETY_20260531.md"
    )
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(
        """# E Repair Package - Confidence And ROI Consumption Safety

## Root Cause Summary
- E has warning-level ROI coverage and must not let bridge-only money proof look business-ready.

## Approved Check
- `e_b_money_truth_dependency`

## Allowed Files For A Future Repair Batch
- `sellerone_manager/hourly_mot.py`
- focused E manager tests under `tests/manager/`

## Forbidden Files And Actions
- Do not run E live.
- Do not fake ROI fill.
- Do not make business reorder decisions.
- Do not write Google Sheets.

## Proof Path For A Future Repair
- Keep E ROI gaps warning-labelled when upstream money proof is incomplete.
- Retest E through the independent MOT.

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow E

## Rollback Path
- Use git diff for code rollback.
- Do not rewrite business data outputs to make the warning disappear.

## Stop Condition
- Stop when E MOT can clearly show whether upstream money truth is safe, bridge-only, or not yet proven.
""",
        encoding="utf-8",
    )
    return package_path


def _write_f_repair_package(root: Path) -> Path:
    package_path = (
        root
        / "plans"
        / "active"
        / "sellerone-manager-control-plane-v1"
        / "F_REPAIR_PACKAGE_F_SOURCE_PROOF_REFRESH_20260531.md"
    )
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(
        """# F Repair Package - Source Proof Refresh

## Root Cause Summary
- F scanner heartbeat is OK, but source-intake proof is stale.

## Approved Check
- `f_source_proof_refresh`

## Allowed Files For A Future Repair Batch
- `sellerone_manager/hourly_mot.py`
- focused F manager tests under `tests/manager/`

## Forbidden Files And Actions
- Do not run F061.
- Do not edit F061 queue state.
- Do not fetch Gmail.
- Do not download supplier files.
- Do not delete outputs.

## Proof Path For A Future Repair
- Keep source-proof gaps warning-labelled or refresh them through an approved F proof path.
- Retest F through the independent MOT.

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow F

## Rollback Path
- Use git diff for code rollback.

## Stop Condition
- Stop if the work crosses a protected F boundary.
""",
        encoding="utf-8",
    )
    return package_path


def test_safe_mot_worklist_row_becomes_approved_task_packet(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_mot_worklist(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    assert result["approved_count"] == 1
    row = result["rows"][0]
    assert row["task_id"] == "MOT_A_A001_LISTINGS_LATEST"
    assert row["authority"] == "standing_safe_code_repair"
    assert row["status"] == "approved"
    packet = Path(row["packet_path"])
    assert packet.exists()
    assert "Exact Source Row" in packet.read_text(encoding="utf-8")
    assert row["job_ref"] == "A-A001-LISTINGS"
    assert "- job_ref: A-A001-LISTINGS" in packet.read_text(encoding="utf-8")


def test_parked_mot_worklist_row_stays_out_of_approved_repair_queue(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_mot_worklist(tmp_path, status="parked")

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    assert result["approved_count"] == 0
    row = result["rows"][0]
    assert row["task_id"] == "MOT_A_A001_LISTINGS_LATEST"
    assert row["status"] == "parked"
    assert row["luke_action_required"] == "0"
    assert Path(row["packet_path"]).parent.name == "approved"


def test_generated_mot_job_refs_match_named_examples(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "mot" / "mot_worklist.csv",
        _mot_worklist_columns(),
        [
            {
                "observed_utc": "2026-06-04T09:00:00Z",
                "created_utc": "2026-06-04T09:00:00Z",
                "updated_utc": "2026-06-04T09:00:00Z",
                "last_seen_utc": "2026-06-04T09:00:00Z",
                "seen_count": "1",
                "work_item_id": "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF",
                "flow": "F",
                "check": "f_email_price_list_source_proof",
                "title": "F MOT: f_email_price_list_source_proof needs repair",
                "status": "new",
                "priority": "high",
                "allowed_scope": "F source proof only.",
                "forbidden_actions": "no F061 queue edits",
                "proof_required": "Retest F MOT.",
                "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
                "luke_action_required": "0",
            },
            {
                "observed_utc": "2026-06-04T09:00:00Z",
                "created_utc": "2026-06-04T09:00:00Z",
                "updated_utc": "2026-06-04T09:00:00Z",
                "last_seen_utc": "2026-06-04T09:00:00Z",
                "seen_count": "1",
                "work_item_id": "MOT_B_B_ORIGINAL_RETURN_STATUS_APPLY_DECISION",
                "flow": "B",
                "check": "b_original_return_status_apply_decision",
                "title": "B MOT: original returned-token live-status repair needs protected decision",
                "status": "blocked_needs_luke",
                "priority": "high",
                "allowed_scope": "B proof planning only.",
                "forbidden_actions": "no token edits",
                "proof_required": "Needs protected decision before apply.",
                "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow B",
                "luke_action_required": "1",
            },
        ],
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-06-04T09:05:00Z")

    rows = {row["task_id"]: row for row in result["rows"]}
    assert rows["MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF"]["job_ref"] == "F-EMAIL-SOURCE"
    assert rows["MOT_B_B_ORIGINAL_RETURN_STATUS_APPLY_DECISION"]["job_ref"] == "B-ORIGINAL-TOKEN"


def test_existing_job_ref_is_preserved_across_refresh(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_mot_worklist(tmp_path)
    first = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-06-04T09:05:00Z")
    first["rows"][0]["job_ref"] = "A-CUSTOM-LISTINGS"
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        first["rows"],
    )

    second = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-06-04T09:06:00Z")

    row = second["rows"][0]
    assert row["job_ref"] == "A-CUSTOM-LISTINGS"
    assert "- job_ref: A-CUSTOM-LISTINGS" in Path(row["packet_path"]).read_text(encoding="utf-8")


def test_duplicate_job_refs_get_stable_suffixes(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    base_row = {
        "observed_utc": "2026-06-04T09:00:00Z",
        "created_utc": "2026-06-04T09:00:00Z",
        "updated_utc": "2026-06-04T09:00:00Z",
        "last_seen_utc": "2026-06-04T09:00:00Z",
        "seen_count": "1",
        "flow": "F",
        "producer": "F source proof",
        "title": "F MOT: f_email_price_list_source_proof needs repair",
        "status": "new",
        "priority": "high",
        "allowed_scope": "F source proof only.",
        "forbidden_actions": "no F061 queue edits",
        "proof_required": "Retest F MOT.",
        "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
        "luke_action_required": "0",
    }
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "mot" / "mot_worklist.csv",
        _mot_worklist_columns(),
        [
            {
                **base_row,
                "work_item_id": "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF",
                "check": "f_email_price_list_source_proof",
            },
            {
                **base_row,
                "work_item_id": "MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF_ALT",
                "check": "f_email_price_list_source_proof_alt",
            },
        ],
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-06-04T09:05:00Z")

    refs = {row["task_id"]: row["job_ref"] for row in result["rows"]}
    assert refs["MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF"] == "F-EMAIL-SOURCE"
    assert refs["MOT_F_F_EMAIL_PRICE_LIST_SOURCE_PROOF_ALT"] == "F-EMAIL-SOURCE-02"


def test_status_update_resolves_unique_job_ref(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_mot_worklist(tmp_path)
    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-06-04T09:05:00Z")

    row = update_approved_task_status(
        root=tmp_path,
        task_id="A-A001-LISTINGS",
        status="fixed_needs_retest",
        note="Ready by job ref.",
        observed_utc="2026-06-04T09:06:00Z",
    )

    assert row["task_id"] == "MOT_A_A001_LISTINGS_LATEST"
    assert row["status"] == "fixed_needs_retest"


def test_ambiguous_job_ref_fails_safely(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "approved_task_packets.csv",
        APPROVED_TASK_PACKET_COLUMNS,
        [
            {"task_id": "MOT_F_ONE", "job_ref": "F-EMAIL-SOURCE", "status": "approved", "luke_action_required": "0"},
            {"task_id": "MOT_F_TWO", "job_ref": "F-EMAIL-SOURCE", "status": "approved", "luke_action_required": "0"},
        ],
    )

    with pytest.raises(ValueError, match="ambiguous job_ref"):
        update_approved_task_status(
            root=tmp_path,
            task_id="F-EMAIL-SOURCE",
            status="fixed_needs_retest",
            observed_utc="2026-06-04T09:06:00Z",
        )


def test_manager_candidate_becomes_task_packaging_only_packet(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_manager_candidate(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    row = result["rows"][0]
    assert row["task_type"] == "task_packaging_only"
    assert row["authority"] == "manager_task_packaging_only"
    assert row["job_ref"].startswith("B-")
    assert "manager classification" in row["allowed_scope"]


def test_completed_repair_package_turns_packaging_candidate_proved(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_manager_candidate(
        tmp_path,
        flow="H",
        task_id="H_repair_out_cycle_alerts_checkli",
        title="Repair H active FAIL group",
        root_artifact="out/cycle_alerts/checklist_H.csv",
    )
    _write_h_repair_package(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    packaging = next(row for row in result["rows"] if row["task_id"] == "MGR_H_repair_out_cycle_alerts_checkli")
    assert packaging["status"] == "proved"


def test_suffixed_h_repair_package_can_prove_current_fail_group(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_manager_candidate(
        tmp_path,
        flow="H",
        task_id="H_repair_out_cycle_alerts_checkli",
        title="Repair H active FAIL group",
        root_artifact="out/cycle_alerts/checklist_H.csv",
        notes="2 active FAIL/blocker rows found.",
    )
    _write_h_repair_package(
        tmp_path,
        suffix="_20260527_current_failures",
        root_cause_line=(
            "- The active H FAIL group has 2 active FAIL/blocker rows: "
            "`h_ceiling_events_required_fields_non_blank` and `h_market_context_fill_nonzero`."
        ),
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    packaging = next(row for row in result["rows"] if row["task_id"] == "MGR_H_repair_out_cycle_alerts_checkli")
    assert packaging["status"] == "proved"


def test_plain_h_check_in_repair_package_creates_readable_repair_task(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    package_path = _write_h_repair_package(
        tmp_path,
        suffix="_20260527_current_failures",
        root_cause_line=(
            "- The active H FAIL group has 2 active FAIL/blocker rows: "
            "h_ceiling_events_required_fields_non_blank and h_market_context_fill_nonzero."
        ),
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    row = next(row for row in result["rows"] if row["source_id"] == package_path.stem)
    assert row["task_id"] == "MGR_H_repair_h_ceiling_events_required_fields_non_blank"


def test_repair_package_accepts_plain_proof_path_heading(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    package_path = _write_h_repair_package(
        tmp_path,
        suffix="_plain_proof_heading",
        root_cause_line="- The active H FAIL group is one checklist row: `h_market_context_fill_nonzero`.",
        proof_heading="Proof Path For Future Repair",
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    row = next(row for row in result["rows"] if row["source_id"] == package_path.stem)
    assert "Re-aggregate" in row["proof_required"]


def test_stale_h_repair_package_does_not_prove_changed_fail_group(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_manager_candidate(
        tmp_path,
        flow="H",
        task_id="H_repair_out_cycle_alerts_checkli",
        title="Repair H active FAIL group",
        root_artifact="out/cycle_alerts/checklist_H.csv",
        notes="2 active FAIL/blocker rows found.",
    )
    _write_h_repair_package(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    packaging = next(row for row in result["rows"] if row["task_id"] == "MGR_H_repair_out_cycle_alerts_checkli")
    assert packaging["status"] == "approved"


def test_changed_h_repair_group_reopens_previous_proved_packaging_task(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_manager_candidate(
        tmp_path,
        flow="H",
        task_id="H_repair_out_cycle_alerts_checkli",
        title="Repair H active FAIL group",
        root_artifact="out/cycle_alerts/checklist_H.csv",
        notes="1 active FAIL/blocker rows found.",
    )
    _write_h_repair_package(tmp_path)
    first = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")
    assert next(row for row in first["rows"] if row["task_id"] == "MGR_H_repair_out_cycle_alerts_checkli")[
        "status"
    ] == "proved"

    _write_manager_candidate(
        tmp_path,
        flow="H",
        task_id="H_repair_out_cycle_alerts_checkli",
        title="Repair H active FAIL group",
        root_artifact="out/cycle_alerts/checklist_H.csv",
        notes="2 active FAIL/blocker rows found.",
    )

    second = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:31:00Z")

    packaging = next(row for row in second["rows"] if row["task_id"] == "MGR_H_repair_out_cycle_alerts_checkli")
    assert packaging["status"] == "approved"


def test_h_repair_package_becomes_standing_approved_repair_packet(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    package_path = _write_h_repair_package(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    row = result["rows"][0]
    assert row["task_id"] == "MGR_H_repair_h_strategy_outcome_daily_count_integrity"
    assert row["source_type"] == "repair_package"
    assert row["source_id"] == package_path.stem
    assert row["task_type"] == "bounded_code_repair"
    assert row["authority"] == "standing_safe_code_repair"
    assert row["status"] == "approved"
    assert row["luke_action_required"] == "0"
    assert "phase1_storage.py" in row["allowed_scope"]
    assert "Do not change prices" in row["forbidden_actions"]
    assert Path(row["packet_path"]).exists()


def test_b_repair_package_becomes_standing_approved_proof_packet(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_quiet_autonomy_policy(tmp_path)
    package_path = _write_b_repair_package(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-31T07:30:00Z")

    row = result["rows"][0]
    assert row["task_id"] == "MGR_B_repair_b_sellerboard_refund_fee_roi_bridge"
    assert row["source_type"] == "repair_package"
    assert row["source_id"] == package_path.stem
    assert row["flow"] == "B"
    assert row["task_type"] == "bounded_code_repair"
    assert row["authority"] == "standing_safe_code_repair"
    assert row["job_ref"].startswith("B-")
    assert row["status"] == "approved"
    assert row["luke_action_required"] == "0"
    assert "sellerboard_bridge.py" in row["allowed_scope"]
    assert "Do not run or restart B" in row["forbidden_actions"]
    assert "API-backed labels" in row["proof_required"]
    assert row["retest_command"] == "python -m sellerone_manager.app --hourly-mot --mot-flow B"
    assert Path(row["packet_path"]).exists()


def test_b_repair_package_uses_approved_check_over_first_warning_code(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    package_path = (
        tmp_path
        / "plans"
        / "active"
        / "sellerone-manager-control-plane-v1"
        / "B_REPAIR_PACKAGE_B_REFUND_FEE_SHIPPING_ROI_API_PROOF_20260531.md"
    )
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(
        """# B Repair Package - API Refund Fee Shipping ROI Proof

## Root Cause Summary
- The existing B warning is `b_sellerboard_refund_fee_roi_bridge`.

## Approved Check
- `b_refund_fee_shipping_roi_api_proof`

## Allowed Files For A Future Repair Batch
- `sellerone_manager/sellerboard_bridge.py`

## Forbidden Files And Actions
- Do not run or restart B.

## Proof Path For A Future Repair
- Add API-backed proof labels.

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow B

## Rollback Path
- Use git diff for code rollback.

## Stop Condition
- Stop if the work crosses a protected B boundary.
""",
        encoding="utf-8",
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-31T09:55:00Z")

    row = next(row for row in result["rows"] if row["source_id"] == package_path.stem)
    assert row["task_id"] == "MGR_B_repair_b_refund_fee_shipping_roi_api_proof"
    assert row["task_id"] != "MGR_B_repair_b_sellerboard_refund_fee_roi_bridge"


def test_e_repair_package_becomes_standing_approved_proof_packet(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    package_path = _write_e_repair_package(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-31T12:20:00Z")

    row = next(row for row in result["rows"] if row["source_id"] == package_path.stem)
    assert row["task_id"] == "MGR_E_repair_e_b_money_truth_dependency"
    assert row["flow"] == "E"
    assert row["status"] == "approved"
    assert row["retest_command"] == "python -m sellerone_manager.app --hourly-mot --mot-flow E"


def test_f_repair_package_becomes_standing_approved_proof_packet(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    package_path = _write_f_repair_package(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-31T12:25:00Z")

    row = next(row for row in result["rows"] if row["source_id"] == package_path.stem)
    assert row["task_id"] == "MGR_F_repair_f_source_proof_refresh"
    assert row["flow"] == "F"
    assert row["status"] == "approved"
    assert row["retest_command"] == "python -m sellerone_manager.app --hourly-mot --mot-flow F"


def test_h_repair_package_uses_approved_check_over_first_warning_code(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    package_path = (
        tmp_path
        / "plans"
        / "active"
        / "sellerone-manager-control-plane-v1"
        / "H_REPAIR_PACKAGE_MOT_H_H_BOUNDARY_FINALIZER_TRUTH_20260531.md"
    )
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(
        """# H Repair Package - Boundary Finalizer Proof

## Root Cause Summary
- The old health clue is `h_health_snapshot_as_clue`.

## Approved Check
- `h_boundary_finalizer_truth`

## Allowed Files For A Future Repair Batch
- `scripts/phase1/phase1_main_loop.py`

## Forbidden Files And Actions
- Do not change prices.

## Proof Path For A Future Repair
- Run focused H lifecycle tests.

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow H

## Rollback Path
- Use git diff for code rollback.

## Stop Condition
- Stop if the work crosses a protected H boundary.
""",
        encoding="utf-8",
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-31T09:55:00Z")

    row = next(row for row in result["rows"] if row["source_id"] == package_path.stem)
    assert row["task_id"] == "MGR_H_repair_h_boundary_finalizer_truth"
    assert row["task_id"] != "MGR_H_repair_h_health_snapshot_as_clue"


def test_quiet_autonomy_parks_h_repair_package_packets(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_quiet_autonomy_policy(tmp_path)
    package_path = _write_h_repair_package(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    row = result["rows"][0]
    assert row["source_id"] == package_path.stem
    assert row["status"] == "parked"
    assert row["luke_action_required"] == "0"
    assert "H repair waits" in row["notes"]


def test_blocked_repair_package_status_survives_refresh(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_h_repair_package(tmp_path)
    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")
    update_approved_task_status(
        root=tmp_path,
        task_id="MGR_H_repair_h_strategy_outcome_daily_count_integrity",
        status="blocked_needs_luke",
        note="Protected proof action required.",
        observed_utc="2026-05-26T12:31:00Z",
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:32:00Z")

    row = next(row for row in result["rows"] if row["task_id"] == "MGR_H_repair_h_strategy_outcome_daily_count_integrity")
    assert row["status"] == "blocked_needs_luke"
    assert row["luke_action_required"] == "1"
    assert row["notes"] == "Protected proof action required."


def test_technical_pause_blocked_repair_package_reopens_when_policy_allows_it(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_h_repair_package(tmp_path)
    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")
    update_approved_task_status(
        root=tmp_path,
        task_id="MGR_H_repair_h_strategy_outcome_daily_count_integrity",
        status="blocked_needs_luke",
        note="Live retest needs protected H scheduler pause approval.",
        observed_utc="2026-05-26T12:31:00Z",
    )
    _write_active_autonomy_policy(tmp_path)

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:32:00Z")

    row = next(row for row in result["rows"] if row["task_id"] == "MGR_H_repair_h_strategy_outcome_daily_count_integrity")
    assert row["status"] == "approved"
    assert row["luke_action_required"] == "0"


def test_protected_rows_stay_blocked_and_current_state_requires_luke(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_manager_candidate(tmp_path, status="blocked_needs_user_decision", needs_luke="1")
    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:31:00Z")

    assert state["system_status"] == "BLOCKED"
    assert state["luke_action_required"] is True
    assert state["codex_task_available"] is False


def test_current_state_prefers_approved_task_over_raw_mot_worklist(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_mot_worklist(tmp_path)
    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:31:00Z")

    assert state["codex_task_available"] is True
    assert state["codex_task_title"].startswith("A-A001-LISTINGS")
    assert "Codex owns A-A001-LISTINGS" in state["current_state"]
    assert "approved manager task" in state["next_safe_batch"]


def test_current_state_ignores_terminal_manager_candidate_packet(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_flow_state(tmp_path)
    _write_manager_candidate(
        tmp_path,
        flow="A",
        task_id="A_proof_gap_project_control_EXPECTAT",
        title="Add or confirm A manager proof coverage",
        root_artifact="project_control/EXPECTATIONS/A_cycle_expectations.md",
        notes="2 expectations are not yet manager-verified.",
    )
    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")
    update_approved_task_status(
        root=tmp_path,
        task_id="MGR_A_proof_gap_project_control_EXPECTAT",
        status="proved",
        note="Package created and reviewed.",
        observed_utc="2026-05-26T12:31:00Z",
    )

    state = build_current_state(root=tmp_path, generated_utc="2026-05-26T12:32:00Z")

    assert state["codex_task_available"] is False
    assert "Add or confirm A manager proof coverage" not in state["next_safe_batch"]


def test_manual_approved_task_packet_is_indexed_and_preserved_on_claim(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    packet_path = tmp_path / "sellerone_manager" / "tasks" / "approved" / "MGR_O_RESTOCK_SESSION_V1.md"
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(
        """# O Restock Session v1

## Manager Authority
- task_id: MGR_O_RESTOCK_SESSION_V1
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: approved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Boundary
- allowed_scope: O restock-session view only.
- forbidden_actions: no purchase order; no Sheets; no price changes.
- proof_required: Retest O MOT.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff.
- stop_condition: Stop for protected actions.

## Detailed Instructions
Keep this rich manual packet body intact.
""",
        encoding="utf-8",
    )

    result = refresh_approved_task_packets(root=tmp_path, observed_utc="2026-06-02T18:31:49Z")

    row = next(row for row in result["rows"] if row["task_id"] == "MGR_O_RESTOCK_SESSION_V1")
    assert row["source_type"] == "manual_task_file"
    assert row["flow"] == "O"
    assert row["job_ref"] == "O-RESTOCK-SESSION"
    assert row["priority"] == "high"
    assert row["status"] == "approved"
    assert row["packet_path"] == str(packet_path)
    assert "rich manual packet" in packet_path.read_text(encoding="utf-8")

    claimed = claim_next_approved_task(root=tmp_path, observed_utc="2026-06-02T18:32:00Z")

    assert claimed["task_id"] == "MGR_O_RESTOCK_SESSION_V1"
    packet_text = packet_path.read_text(encoding="utf-8")
    assert "- job_ref: O-RESTOCK-SESSION" in packet_text
    assert "- status: in_progress" in packet_text
    assert "Keep this rich manual packet body intact." in packet_text


def test_refresh_backfills_orphan_packet_markdown_job_ref(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    packet_path = tmp_path / "sellerone_manager" / "tasks" / "approved" / "MOT_F_OLD_SOURCE_PACKET.md"
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(
        """# F Old Source Packet

## Manager Authority
- task_id: MOT_F_OLD_SOURCE_PACKET
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Source
- source_type: mot
- source_id: MOT_F_OLD_SOURCE_PACKET

## Detailed Instructions
Keep this old generated packet body intact.
""",
        encoding="utf-8",
    )

    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-06-04T09:08:00Z")

    packet_text = packet_path.read_text(encoding="utf-8")
    assert "- job_ref: F-OLD-SOURCE" in packet_text
    assert "Keep this old generated packet body intact." in packet_text


def test_claim_and_status_updates_sync_mot_retest_queue(tmp_path: Path) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_mot_worklist(tmp_path)
    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-05-26T12:30:00Z")

    claimed = claim_next_approved_task(root=tmp_path, observed_utc="2026-05-26T12:31:00Z")
    assert claimed["status"] == "in_progress"
    mot_rows = _read_csv(tmp_path / "out" / "systems" / "M" / "mot" / "mot_worklist.csv")
    assert mot_rows[0]["status"] == "in_progress"

    updated = update_approved_task_status(
        root=tmp_path,
        task_id=claimed["task_id"],
        status="fixed_needs_retest",
        note="Code repair ready for MOT retest.",
        observed_utc="2026-05-26T12:32:00Z",
    )
    assert updated["status"] == "fixed_needs_retest"
    retest_rows = _read_csv(tmp_path / "out" / "systems" / "M" / "mot" / "mot_retest_queue.csv")
    assert retest_rows[0]["work_item_id"] == "MOT_A_A001_LISTINGS_LATEST"
    assert retest_rows[0]["status"] == "pending"


def test_claim_and_status_cli_print_job_ref_and_task_id(tmp_path: Path, capsys) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_mot_worklist(tmp_path)
    refresh_approved_task_packets(root=tmp_path, observed_utc="2026-06-04T09:05:00Z")

    claim_exit = app_main(["--root", str(tmp_path), "--claim-approved-task", "--observed-utc", "2026-06-04T09:06:00Z"])
    claim_output = capsys.readouterr().out

    assert claim_exit == 0
    assert "job_ref=A-A001-LISTINGS" in claim_output
    assert "task_id=MOT_A_A001_LISTINGS_LATEST" in claim_output

    status_exit = app_main(
        [
            "--root",
            str(tmp_path),
            "--approved-task-status",
            "A-A001-LISTINGS",
            "--status",
            "fixed_needs_retest",
            "--observed-utc",
            "2026-06-04T09:07:00Z",
        ]
    )
    status_output = capsys.readouterr().out

    assert status_exit == 0
    assert "job_ref=A-A001-LISTINGS" in status_output
    assert "task_id=MOT_A_A001_LISTINGS_LATEST" in status_output


def test_what_next_refreshes_and_surfaces_approved_packet(tmp_path: Path, capsys) -> None:
    _write_base_manager_outputs(tmp_path)
    _write_mot_worklist(tmp_path)

    exit_code = app_main(["--root", str(tmp_path), "--what-next", "--observed-utc", "2026-05-26T12:30:00Z"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "CODEX TASK AVAILABLE:\nyes" in output
    assert "A-A001-LISTINGS" in output
    payload = json.loads((tmp_path / "sellerone_manager" / "current_state.json").read_text(encoding="utf-8"))
    assert payload["latest_evidence"]["approved_task_packets"].endswith("approved_task_packets.csv")
