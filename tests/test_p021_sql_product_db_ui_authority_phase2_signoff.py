from __future__ import annotations

import json
from pathlib import Path

from scripts.one_off import P021_sql_product_db_ui_authority_phase2_signoff as p021


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_p021_builds_completion_report_when_all_phase_summaries_pass(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "proof"
    paths = {
        "p015_sql_authority": output_dir / "product_db_sql_authority_rehearsal_summary.json",
        "p016_tracker_cutover": output_dir / "repricer_tracker_ui_cutover_summary.json",
        "p017_tracker_parity": output_dir / "repricer_tracker_ui_parity_summary.json",
        "p018_mirror_drift": output_dir / "product_db_mirror_drift_guard_summary.json",
        "p019_reader_map": output_dir / "product_db_reader_dependency_summary.json",
        "p020_postgres_rehearsal": output_dir / "product_db_postgres_promotion_rehearsal_summary.json",
    }
    monkeypatch.setattr(p021, "SUMMARY_PATHS", paths)
    _write_json(paths["p015_sql_authority"], {"status": "warn", "fail_count": 0, "sql_rows": 2, "sql_unique_seller_sku": 2, "o_view_rows": 2, "csv_mirror_rows": 1})
    _write_json(paths["p016_tracker_cutover"], {"status": "ready_with_stale_audit_warning", "fail_count": 0, "tracker_rows": 3, "terminal_run_id": "RUN-1"})
    _write_json(paths["p017_tracker_parity"], {"status": "ready_with_stale_audit_warning", "fail_count": 0})
    _write_json(paths["p018_mirror_drift"], {"status": "warn", "fail_count": 0})
    _write_json(paths["p019_reader_map"], {"status": "warn", "unknown_owner_count": 0, "reader_reference_rows": 5})
    _write_json(paths["p020_postgres_rehearsal"], {"status": "ok", "promotion_status": "not_run_requires_explicit_approval"})

    report_path = tmp_path / "COMPLETION_REPORT.md"
    payload = p021.run_check(output_dir=output_dir, report_path=report_path, observed_utc="2026-05-01T11:00:00Z")

    assert payload["status"] == "complete_locally_pending_explicit_cutover_approvals"
    assert payload["fail_count"] == 0
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "SQL Product DB UI Authority Phase 2 Completion Report" in report
    assert "## Boundaries Honored" in report
    assert "## Observation Decision" in report
    assert "No Google Sheets writes" in report


def test_p021_fails_when_required_summary_missing(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "proof"
    paths = {name: output_dir / f"{name}.json" for name in p021.SUMMARY_PATHS}
    monkeypatch.setattr(p021, "SUMMARY_PATHS", paths)

    payload = p021.run_check(output_dir=output_dir, report_path=tmp_path / "report.md", observed_utc="2026-05-01T11:00:00Z")

    assert payload["status"] == "fail"
    assert payload["fail_count"] > 0
