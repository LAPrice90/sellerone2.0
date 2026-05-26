from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.tools import log_housekeeping as hk


def _touch(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_registry_declares_h_non_gate_observability_rule() -> None:
    registry_path = ROOT / "project_control" / "log_housekeeping_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    rules = registry.get("rules", [])
    row = next((r for r in rules if str(r.get("id", "")).strip() == "h_non_gate_observability"), None)
    assert row is not None
    assert str(row.get("class", "")).strip() == "L5"
    globs = set(str(x) for x in (row.get("path_globs", []) or []))
    assert "out/cycle_alerts/checklist_H_split.csv" in globs
    assert "out/health_status_H.csv" in globs


def test_registry_declares_storage_guard_rules() -> None:
    registry_path = ROOT / "project_control" / "log_housekeeping_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    rules = {str(r.get("id", "")).strip(): r for r in registry.get("rules", [])}

    sql_rule = rules.get("sql_primary_database_protected")
    assert sql_rule is not None
    assert sql_rule.get("protected") is True
    assert "out/sql/sellerone_dev.sqlite3" in set(sql_rule.get("path_globs", []))

    f_rule = rules.get("f_storage_drift_reconcile_backups")
    assert f_rule is not None
    assert f_rule.get("target_type") == "directory"
    assert f_rule.get("cleanup_eligible") is True
    assert int(f_rule.get("retention", {}).get("max_file_count")) == 1

    h_rule = rules.get("h_staged_publish_snapshots")
    assert h_rule is not None
    assert h_rule.get("target_type") == "directory"
    assert int(h_rule.get("retention", {}).get("max_file_count")) == 5


def test_non_gate_observability_files_are_reported_as_non_cleanup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    _touch(tmp_path / "out" / "cycle_alerts" / "checklist_H_split.csv")
    _touch(tmp_path / "out" / "health_status_H.csv")

    registry = {
        "scan_roots": [],
        "classes": {"L5": "historical_audit_event_logs"},
        "rules": [
            {
                "id": "h_non_gate_observability",
                "class": "L5",
                "owner": "H observability",
                "reason": "non-gate",
                "mandatory": False,
                "path_globs": ["out/cycle_alerts/checklist_H_split.csv", "out/health_status_H.csv"],
                "retention": {"ttl_days": 1, "archive_days": 180},
                "action_on_expiry": "archive",
                "protected": False,
                "live_cleanup_allowed": False,
                "safety_blockers": [],
            }
        ],
    }
    rules = hk._build_rules(registry)
    files, _ = hk._collect_paths(registry, rules)
    rows = hk._build_rows(
        files,
        rules,
        registry["classes"],
        {"h_run_unfinalized": False, "h_run_unfinalized_reason": "test", "h_lock_active": False, "h_lock_active_reason": "test"},
    )
    assert len(rows) == 2
    for row in rows:
        assert row["decision"] == "keep"
        assert row["reason"] == "non_cleanup_class"
        assert row["class"] == "L5"


def test_apply_skips_l5_even_when_row_requests_archive(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    target = tmp_path / "out" / "health_status_H.csv"
    _touch(target, "old\n")

    rules = [
        hk.Rule(
            id="h_non_gate_observability",
            class_id="L5",
            owner="H observability",
            reason="non-gate",
            mandatory=False,
            path_globs=["out/health_status_H.csv"],
            ttl_days=1.0,
            max_file_count=None,
            max_total_size_mb=None,
            action_on_expiry="archive",
            protected=False,
            live_cleanup_allowed=True,
            safety_blockers=[],
        )
    ]
    rows = [
        {
            "path": "out/health_status_H.csv",
            "class": "L5",
            "rule_id": "h_non_gate_observability",
            "decision": "would_archive",
            "action_taken": "none",
            "action_error": "",
        }
    ]
    out_dir = tmp_path / "out" / "housekeeping"
    ledger_rows = hk._apply_actions(
        rows,
        rules,
        out_dir,
        {"h_run_unfinalized": False, "h_run_unfinalized_reason": "test", "h_lock_active": False, "h_lock_active_reason": "test"},
    )
    assert target.exists()
    assert rows[0]["action_taken"] == "skipped"
    assert rows[0]["action_error"] == "live_cleanup_not_allowed"
    assert len(ledger_rows) == 1
    assert ledger_rows[0]["action_error"] == "live_cleanup_not_allowed"


def test_apply_deletes_l4_when_allowed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    target = tmp_path / "out" / "tmp_demo.log"
    _touch(target, "debug\n")

    rules = [
        hk.Rule(
            id="debug_tmp",
            class_id="L4",
            owner="ops",
            reason="debug",
            mandatory=False,
            path_globs=["out/tmp_demo.log"],
            ttl_days=1.0,
            max_file_count=None,
            max_total_size_mb=None,
            action_on_expiry="delete",
            protected=False,
            live_cleanup_allowed=True,
            safety_blockers=[],
        )
    ]
    rows = [
        {
            "path": "out/tmp_demo.log",
            "class": "L4",
            "rule_id": "debug_tmp",
            "decision": "would_delete",
            "action_taken": "none",
            "action_error": "",
        }
    ]
    out_dir = tmp_path / "out" / "housekeeping"
    ledger_rows = hk._apply_actions(
        rows,
        rules,
        out_dir,
        {"h_run_unfinalized": False, "h_run_unfinalized_reason": "test", "h_lock_active": False, "h_lock_active_reason": "test"},
    )
    assert not target.exists()
    assert rows[0]["action_taken"] == "deleted"
    assert rows[0]["action_error"] == ""
    assert len(ledger_rows) == 1
    assert ledger_rows[0]["action_taken"] == "deleted"


def test_directory_family_rule_deletes_oldest_over_count_cap(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    old_dir = tmp_path / "out" / "backups" / "f_storage_drift_reconcile_old"
    new_dir = tmp_path / "out" / "backups" / "f_storage_drift_reconcile_new"
    _touch(old_dir / "sellerone_dev.sqlite3", "old backup\n")
    _touch(new_dir / "sellerone_dev.sqlite3", "new backup\n")
    os.utime(old_dir, (100, 100))
    os.utime(new_dir, (200, 200))

    registry = {
        "scan_roots": [],
        "classes": {"L6": "temp_subprocess_artifacts"},
        "rules": [
            {
                "id": "f_storage_drift_reconcile_backups",
                "class": "L6",
                "owner": "F storage",
                "flow": "F",
                "target_type": "directory",
                "path_globs": ["out/backups/f_storage_drift_reconcile_*"],
                "retention": {"max_file_count": 1},
                "action_on_expiry": "delete",
                "protected": False,
                "live_cleanup_allowed": True,
                "cleanup_eligible": True,
                "safety_blockers": [],
            }
        ],
    }
    rules = hk._build_rules(registry)
    paths, _ = hk._collect_paths(registry, rules)
    rows = hk._build_rows(
        paths,
        rules,
        registry["classes"],
        {"h_run_unfinalized": False, "h_run_unfinalized_reason": "test", "h_lock_active": False, "h_lock_active_reason": "test"},
    )

    by_path = {row["path"]: row for row in rows}
    assert by_path["out/backups/f_storage_drift_reconcile_old"]["item_type"] == "directory"
    assert by_path["out/backups/f_storage_drift_reconcile_old"]["decision"] == "would_delete"
    assert by_path["out/backups/f_storage_drift_reconcile_new"]["decision"] == "keep"

    hk._apply_actions(
        rows,
        rules,
        tmp_path / "out" / "housekeeping",
        {"h_run_unfinalized": False, "h_run_unfinalized_reason": "test", "h_lock_active": False, "h_lock_active_reason": "test"},
    )
    assert not old_dir.exists()
    assert new_dir.exists()


def test_apply_is_globally_blocked_when_h_unfinalized(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    target = tmp_path / "out" / "tmp_demo.log"
    _touch(target, "debug\n")
    rules = [
        hk.Rule(
            id="debug_tmp",
            class_id="L4",
            owner="ops",
            reason="debug",
            mandatory=False,
            path_globs=["out/tmp_demo.log"],
            ttl_days=1.0,
            max_file_count=None,
            max_total_size_mb=None,
            action_on_expiry="delete",
            protected=False,
            live_cleanup_allowed=True,
            safety_blockers=[],
        )
    ]
    rows = [
        {
            "path": "out/tmp_demo.log",
            "class": "L4",
            "rule_id": "debug_tmp",
            "decision": "would_delete",
            "action_taken": "none",
            "action_error": "",
        }
    ]
    out_dir = tmp_path / "out" / "housekeeping"
    ledger_rows = hk._apply_actions(
        rows,
        rules,
        out_dir,
        {"h_run_unfinalized": True, "h_run_unfinalized_reason": "test", "h_lock_active": False, "h_lock_active_reason": "test"},
    )
    assert target.exists()
    assert rows[0]["action_taken"] == "skipped"
    assert rows[0]["action_error"] == "apply_blocked:h_run_unfinalized"
    assert len(ledger_rows) == 1
    assert ledger_rows[0]["action_error"] == "apply_blocked:h_run_unfinalized"


def test_apply_is_globally_blocked_when_h_lock_active(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    target = tmp_path / "out" / "tmp_demo.log"
    _touch(target, "debug\n")
    rules = [
        hk.Rule(
            id="debug_tmp",
            class_id="L4",
            owner="ops",
            reason="debug",
            mandatory=False,
            path_globs=["out/tmp_demo.log"],
            ttl_days=1.0,
            max_file_count=None,
            max_total_size_mb=None,
            action_on_expiry="delete",
            protected=False,
            live_cleanup_allowed=True,
            safety_blockers=[],
        )
    ]
    rows = [
        {
            "path": "out/tmp_demo.log",
            "class": "L4",
            "rule_id": "debug_tmp",
            "decision": "would_delete",
            "action_taken": "none",
            "action_error": "",
        }
    ]
    ledger_rows = hk._apply_actions(
        rows,
        rules,
        tmp_path / "out" / "housekeeping",
        {
            "h_run_unfinalized": False,
            "h_run_unfinalized_reason": "test",
            "h_lock_active": True,
            "h_lock_active_reason": "test",
        },
    )
    assert target.exists()
    assert rows[0]["action_taken"] == "skipped"
    assert rows[0]["action_error"] == "apply_blocked:h_lock_active"
    assert len(ledger_rows) == 1


def test_write_action_ledger_outputs_run_and_latest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    out_dir = tmp_path / "out" / "housekeeping"
    rows = [
        {
            "timestamp_utc": "2026-04-07T09:00:00Z",
            "path": "out/tmp_demo.log",
            "rule_id": "debug_tmp",
            "decision": "would_delete",
            "action_taken": "deleted",
            "action_error": "",
        }
    ]
    run_path, latest_path = hk._write_action_ledger(out_dir, "20260407T090000Z", rows)
    assert run_path.exists()
    assert latest_path.exists()
    text = latest_path.read_text(encoding="utf-8")
    assert "action_taken" in text
    assert "deleted" in text
    assert (out_dir / "storage_housekeeping_actions.latest.csv").exists()


def test_write_summary_outputs_storage_alias(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    out_dir = tmp_path / "out" / "housekeeping"
    payload = {
        "generated_utc": "2026-05-25T09:00:00Z",
        "mode": "dry_run",
        "total_items": 0,
        "decision_counts": {},
        "action_counts": {},
        "context": {"h_run_unfinalized": False, "h_run_unfinalized_reason": "test", "h_lock_active": False, "h_lock_active_reason": "test"},
        "apply_allowed": True,
        "apply_block_reason": "",
        "action_ledger": "",
    }
    hk._write_summary(out_dir, "20260525T090000Z", payload)
    assert (out_dir / "storage_housekeeping_summary.latest.json").exists()


def test_storage_health_fails_unclassified_scan_items(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    target = tmp_path / "out" / "systems" / "X" / "new_output.csv"
    _touch(target, "new\n")
    registry = {
        "storage_health": {"free_space_warn_gb": 0, "free_space_fail_gb": 0},
        "scan_roots": [{"path": "out/systems/X", "recursive": True}],
        "classes": {},
        "rules": [],
    }
    rules = hk._build_rules(registry)
    paths, _ = hk._collect_paths(registry, rules)
    rows = hk._build_rows(
        paths,
        rules,
        {},
        {"h_run_unfinalized": False, "h_run_unfinalized_reason": "test", "h_lock_active": False, "h_lock_active_reason": "test"},
    )
    health_rows = hk._build_storage_health_rows(rows, rules, registry)
    by_id = {row["check_id"]: row for row in health_rows}
    assert by_id["unclassified_scan_items"]["status"] == "FAIL"
    assert by_id["unclassified_scan_items"]["value"] == "1"


def test_flow_filter_skips_other_flow_scan_roots(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    _touch(tmp_path / "out" / "systems" / "H" / "live" / "unknown_h.txt")
    _touch(tmp_path / "out" / "systems" / "F" / "temp" / "unknown_f.txt")
    registry = {
        "scan_roots": [
            {"flow": "H", "path": "out/systems/H/live", "recursive": True},
            {"flow": "F", "path": "out/systems/F/temp", "recursive": True},
        ],
        "classes": {},
        "rules": [],
    }
    paths, _ = hk._collect_paths(registry, [], flow_filter="F")
    rels = {hk._relative(path) for path in paths}
    assert rels == {"out/systems/F/temp/unknown_f.txt"}


def test_rule_flow_filter_infers_old_h_rule_from_path() -> None:
    h_rule = hk.Rule(
        id="old_h_rule",
        class_id="L4",
        owner="H",
        reason="old",
        mandatory=False,
        path_globs=["out/systems/H/live/*.log"],
        ttl_days=None,
        max_file_count=None,
        max_total_size_mb=None,
        action_on_expiry="delete",
        protected=False,
        live_cleanup_allowed=True,
        safety_blockers=[],
    )
    f_rule = hk.Rule(
        id="new_f_rule",
        class_id="L6",
        owner="F",
        reason="new",
        mandatory=False,
        path_globs=["out/systems/F/temp/*"],
        ttl_days=None,
        max_file_count=None,
        max_total_size_mb=None,
        action_on_expiry="delete",
        protected=False,
        live_cleanup_allowed=True,
        safety_blockers=[],
    )
    assert not hk._rule_matches_flow(h_rule, "F")
    assert hk._rule_matches_flow(f_rule, "F")


def test_source_hash_evidence_accepts_run_state_source_hash_in_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hk, "ROOT", tmp_path)
    supplier_dir = tmp_path / "out" / "systems" / "F" / "inbox" / "suppliers" / "supplier_a"
    _touch(
        supplier_dir / "run_state.csv",
        "supplier_id,source_file_path\nsupplier_a,C:/Source/supplier_20260519_ab12cd34ef.csv\n",
    )
    assert hk._source_hash_evidence_exists(supplier_dir)
