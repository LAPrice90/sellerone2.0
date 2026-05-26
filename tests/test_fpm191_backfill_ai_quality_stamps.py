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

from scripts.flows.F.price_list_manager import FPM191_backfill_ai_quality_stamps as fpm191_module
from scripts.flows.F.price_list_manager.FPM191_backfill_ai_quality_stamps import (
    QUALITY_STAMP_BACKFILL_COLUMNS,
    backfill_ai_quality_stamps,
)
from scripts.flows.F.price_list_manager._schemas import REVIEW_HANDOFF_MANIFEST_COLUMNS


OBSERVED = "2026-05-22T12:55:00Z"


def _write_manifest_pair(tmp_path: Path) -> tuple[Path, Path]:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
    )
    manifest_row = {
        "built_at_utc": OBSERVED,
        "supplier_id": "supplier_a",
        "supplier_name": "Supplier A",
        "run_id": "run_1",
        "review_snapshot_id": "snapshot_1",
        "pass_review_rows": "1",
        "near_miss_review_rows": "0",
        "pass_review_path": str(handoff_dir / "pass.csv"),
        "near_miss_review_path": str(handoff_dir / "near.csv"),
        "summary_path": str(handoff_dir / "summary.csv"),
        "handoff_dir": str(handoff_dir),
        "ai_gate_status": "passed",
        "ai_gate_quality_status": "",
        "ai_gate_quality_fail_checks": "",
        "ai_gate_quality_warn_checks": "",
        "ai_gate_quality_report_path": "",
        "operator_ready_flag": "1",
        "block_reason": "",
        "notes": "ai_gated_operator_review_pack_built",
    }
    handoff_dir.mkdir(parents=True, exist_ok=True)
    live_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([manifest_row], columns=REVIEW_HANDOFF_MANIFEST_COLUMNS).to_csv(handoff_dir / "manifest.csv", index=False)
    pd.DataFrame([manifest_row], columns=REVIEW_HANDOFF_MANIFEST_COLUMNS).to_csv(
        live_dir / "review_handoff_manifest.csv",
        index=False,
    )
    return handoff_dir / "manifest.csv", live_dir / "review_handoff_manifest.csv"


def _quality_summary(tmp_path: Path, *, status: str = "ok", fail_checks: int = 0) -> dict[str, object]:
    return {
        "status": status,
        "fail_checks": fail_checks,
        "warn_checks": 0,
        "report_path": str(tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_gate_quality_report.csv"),
        "summary_path": str(tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_gate_quality_summary.md"),
    }


def test_fpm191_backfills_quality_stamps_after_fpm156_passes(tmp_path: Path, monkeypatch) -> None:
    handoff_manifest, live_manifest = _write_manifest_pair(tmp_path)

    monkeypatch.setattr(
        fpm191_module,
        "build_ai_gate_quality_report",
        lambda **_: _quality_summary(tmp_path),
    )

    summary = backfill_ai_quality_stamps(root=tmp_path, observed_utc=OBSERVED, emit_json=False)

    handoff_df = pd.read_csv(handoff_manifest, dtype=str).fillna("")
    live_df = pd.read_csv(live_manifest, dtype=str).fillna("")
    report = pd.read_csv(summary["report_path"], dtype=str).fillna("")

    assert summary["status"] == "ok"
    assert summary["updated_rows"] == 2
    assert Path(summary["backup_dir"]).exists()
    assert handoff_df.iloc[0]["ai_gate_quality_status"] == "ok"
    assert handoff_df.iloc[0]["ai_gate_quality_fail_checks"] == "0"
    assert handoff_df.iloc[0]["ai_gate_quality_report_path"].endswith("ai_gate_quality_report.csv")
    assert "quality_fail_checks=0" in handoff_df.iloc[0]["notes"]
    assert live_df.iloc[0]["ai_gate_quality_status"] == "ok"
    assert list(report.columns) == QUALITY_STAMP_BACKFILL_COLUMNS


def test_fpm191_stops_without_writing_when_fpm156_fails(tmp_path: Path, monkeypatch) -> None:
    handoff_manifest, live_manifest = _write_manifest_pair(tmp_path)
    before_handoff = handoff_manifest.read_text(encoding="utf-8")
    before_live = live_manifest.read_text(encoding="utf-8")

    monkeypatch.setattr(
        fpm191_module,
        "build_ai_gate_quality_report",
        lambda **_: _quality_summary(tmp_path, status="fail", fail_checks=1),
    )

    summary = backfill_ai_quality_stamps(root=tmp_path, observed_utc=OBSERVED, emit_json=False)

    report = pd.read_csv(summary["report_path"], dtype=str).fillna("")

    assert summary["status"] == "fail"
    assert summary["updated_rows"] == 0
    assert summary["backup_dir"] == ""
    assert handoff_manifest.read_text(encoding="utf-8") == before_handoff
    assert live_manifest.read_text(encoding="utf-8") == before_live
    assert report.iloc[0]["action"] == "blocked"
    assert report.iloc[0]["status"] == "fail"
