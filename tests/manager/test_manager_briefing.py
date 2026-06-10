from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sellerone_manager.app import main as app_main
from sellerone_manager.manager_briefing import (
    build_manager_briefing,
    render_manager_briefing_markdown,
    write_manager_briefing_outputs,
)
from sellerone_manager.manager_briefing_ui import _card_html, _manager_panel_html


TASK_COLUMNS = [
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


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_fixture(root: Path) -> None:
    manager_dir = root / "sellerone_manager"
    manager_dir.mkdir(parents=True, exist_ok=True)
    manager_dir.joinpath("MANAGER_PROGRESS_TRACKER.md").write_text(
        """# SellerOne Manager Progress Tracker

## Overall Manager Takeover

```text
[#############-------] 67%
```

| Lane | Owner | Goal | Current Status | Progress |
|---|---|---|---|---|
| B refunds, fees, shipping, ROI | B cycle | Tie returns to ROI | B token-cost proof is still the trust blocker. | 45% |
| O restocking proof | O cycle | Restocking workspace | O is usable as a review screen, not an auto-buyer. | 47% |
| F scanner login recovery | F cycle | Scanner login | F is logged in but still has one protected parked row. | 57% |
| E confidence bridge | E cycle | Confidence | E is warning-only. | 82% |
| H repricing safety | H cycle | Repricing safety | H stays bounded. | 63% |
| Main manager board | Main manager | Calm relay | The board exists. | 80% |
""",
        encoding="utf-8",
    )
    manager_dir.joinpath("current_state.json").write_text(
        json.dumps(
            {
                "generated_utc": "2026-06-06T10:00:00Z",
                "system_status": "BLOCKED",
                "flow_states": [
                    {"flow": "A", "status": "ok", "classification": "calm", "covered_expectations": "5", "total_expectations": "5"},
                    {"flow": "B", "status": "warn", "classification": "warning", "first_blocker_summary": "B has warning evidence."},
                    {"flow": "E", "status": "warn", "classification": "warning"},
                    {"flow": "H", "status": "parked", "classification": "high_risk_bounded_repair_only"},
                    {"flow": "F", "status": "blocked", "classification": "blocker", "luke_decision": "Use scanner-owned browser only."},
                    {"flow": "O", "status": "ok", "classification": "calm"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        root / "out" / "systems" / "M" / "approved_task_packets.csv",
        TASK_COLUMNS,
        [
            {
                "task_id": "MOT_B_TOKEN",
                "job_ref": "B-FALLBACK-PROOF-RECONCILE",
                "flow": "B",
                "status": "approved",
                "priority": "high",
                "title": "B fallback proof reconcile",
                "notes": "Read-only proof only.",
                "proof_required": "Retest B MOT.",
                "luke_action_required": "0",
            },
            {
                "task_id": "MOT_F_RESCAN",
                "job_ref": "F-RESCAN-PRIORITY-02",
                "flow": "F",
                "status": "blocked_needs_luke",
                "priority": "high",
                "title": "F rescan priority decision",
                "notes": "Protected scanner decision.",
                "luke_action_required": "1",
            },
            {
                "task_id": "MGR_O_DONE",
                "job_ref": "O-PROVED-HISTORY",
                "flow": "O",
                "status": "proved",
                "priority": "normal",
                "title": "O proved history",
                "luke_action_required": "0",
            },
        ],
    )
    _write_csv(
        root / "out" / "systems" / "M" / "hourly_mot_F.csv",
        ["check", "status", "value", "actual_proof"],
        [
            {
                "check": "f_live_owner_status",
                "status": "fail",
                "value": "running/supplier_progress_stalled",
                "actual_proof": (
                    "active_supplier_id=dhb;scanner_forward_state=stalled;"
                    "recent_scanner_chunks=5;scanner_span_minutes=24.4;"
                    "first_pending_after=5489;latest_pending_after=5489;"
                    "pending_drop=0;processed_rows=9;memory_import_blocked_recent=5"
                ),
            }
        ],
    )


def test_manager_briefing_builds_cards_and_progress_from_existing_truth(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    briefing = build_manager_briefing(root=tmp_path)
    cards = {card.flow: card for card in briefing.managers}

    assert set(cards) == {"A", "B", "E", "H", "F", "O", "M"}
    assert cards["B"].progress_pct == 45
    assert cards["B"].status == "working"
    assert cards["F"].status == "blocked"
    assert cards["F"].luke_action_required is True
    assert briefing.restocking_readiness_pct == 55
    assert any(item.label == "F live scanner movement" and item.state == "Stalled" for item in briefing.movement_watch)


def test_manager_briefing_hides_proved_history_by_default(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    briefing = build_manager_briefing(root=tmp_path)
    o_card = next(card for card in briefing.managers if card.flow == "O")
    briefing_with_history = build_manager_briefing(root=tmp_path, include_proved_history=True)
    o_with_history = next(card for card in briefing_with_history.managers if card.flow == "O")

    assert o_card.proved_history_count == 1
    assert all(job.job_ref != "O-PROVED-HISTORY" for job in o_card.jobs)
    assert any(job.job_ref == "O-PROVED-HISTORY" for job in o_with_history.jobs)


def test_manager_briefing_writes_markdown_json_and_github_manifest(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    briefing = build_manager_briefing(root=tmp_path, observed_utc="2026-06-06T10:00:00Z")

    result = write_manager_briefing_outputs(briefing, root=tmp_path, write_github_snapshot=True)
    manifest = json.loads(result.github_manifest_json.read_text(encoding="utf-8"))

    assert result.latest_json.exists()
    assert result.latest_md.exists()
    assert result.history_md.name == "manager_briefing_20260606-1000.md"
    assert result.github_latest_md.as_posix().endswith("docs/manager-briefing/latest.md")
    assert result.github_history_md.as_posix().endswith("docs/manager-briefing/history/20260606-1000.md")
    assert manifest["status"] == "prepared_for_github_connector"
    assert [item["path"] for item in manifest["files"]] == [
        "docs/manager-briefing/latest.md",
        "docs/manager-briefing/history/20260606-1000.md",
    ]
    assert "no prices" in manifest["safety"]["forbidden_actions"]


def test_manager_briefing_markdown_and_ui_are_human_level(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    briefing = build_manager_briefing(root=tmp_path)
    b_card = next(card for card in briefing.managers if card.flow == "B")

    markdown = render_manager_briefing_markdown(briefing)
    card_html = _card_html(b_card)
    panel_html = _manager_panel_html(b_card, show_details=False)

    assert "SellerOne Manager Briefing" in markdown
    assert "B-FALLBACK-PROOF-RECONCILE" in markdown
    assert "Movement Watch" in markdown
    assert "F live scanner movement: Stalled" in markdown
    assert "C:\\Users" not in markdown
    assert "45%" in card_html
    assert "B fallback proof reconcile" in panel_html


def test_manager_briefing_cli_build_and_publish(tmp_path: Path, capsys) -> None:
    _write_fixture(tmp_path)

    build_rc = app_main(["--root", str(tmp_path), "--manager-briefing-build", "--observed-utc", "2026-06-06T10:00:00Z"])
    build_output = capsys.readouterr().out
    publish_rc = app_main(["--root", str(tmp_path), "--manager-briefing-publish-github", "--observed-utc", "2026-06-06T10:00:00Z"])
    publish_output = capsys.readouterr().out

    assert build_rc == 0
    assert "restocking_readiness_pct=55" in build_output
    assert publish_rc == 0
    assert "github_publish_status=prepared_for_connector" in publish_output
