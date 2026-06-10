from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_operating_outputs(root: Path) -> None:
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
        [
            {
                "rank": "1",
                "script_path": "scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py",
                "recommended_action": "candidate_manifest",
                "priority_band": "top_3",
            },
            {
                "rank": "2",
                "script_path": "scripts/flows/F/price_list_manager/FPM070_stage_f061_handoff.py",
                "recommended_action": "candidate_manifest",
                "priority_band": "top_3",
            },
        ],
    )
    (output_dir / "latest_f_price_list_manager_report.md").write_text("# report\n", encoding="utf-8")


def test_what_next_output_is_short_operator_front_door(tmp_path: Path, capsys) -> None:
    _write_operating_outputs(tmp_path)

    exit_code = app_main(["--root", str(tmp_path), "--what-next", "--observed-utc", "2026-05-26T12:30:00Z"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "SELLERONE MANAGER" in output
    assert "SYSTEM STATUS:\nOK" in output
    assert "ACTIVE FLOW:\nF Price List Manager" in output
    assert "CURRENT STATE:" in output
    assert "No Luke decision needed" in output
    assert "LUKE ACTION REQUIRED:\nno" in output
    assert "CODEX TASK AVAILABLE:\nyes" in output
    assert "NEXT SAFE BATCH:" in output
    assert "DO NOT TOUCH:" in output
    assert "LATEST EVIDENCE:" in output
    assert len(output.splitlines()) <= 50

    current_state_path = tmp_path / "sellerone_manager" / "current_state.json"
    assert current_state_path.exists()
    payload = json.loads(current_state_path.read_text(encoding="utf-8"))
    assert payload["system_status"] == "OK"
    assert not (tmp_path / "out" / "systems" / "F").exists()


def test_what_next_surfaces_active_codex_task(tmp_path: Path, capsys) -> None:
    _write_operating_outputs(tmp_path)
    _write_csv(
        tmp_path / "out" / "systems" / "M" / "codex_repair_queue.csv",
        ["task_id", "status", "task_summary"],
        [{"task_id": "F_example_task", "status": "queued", "task_summary": "Fix a manager-owned technical blocker."}],
    )

    exit_code = app_main(["--root", str(tmp_path), "--what-next", "--observed-utc", "2026-05-26T12:30:00Z"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "CODEX TASK AVAILABLE:\nyes" in output
    assert "F_example_task: Fix a manager-owned technical blocker." in output
    assert "Continue the active Codex-owned manager task only." in output
