from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F010_build_feeder_candidate_intake import build_feeder_candidate_intake
from scripts.flows.F._schemas import get_f_output_contract


FIXTURE_PATH = ROOT / "tests" / "fixtures" / "f_phase1" / "supplier_discovery_handoff_fixture.csv"


def _status_by_check(health_df):
    return {
        row["check"]: row["status"]
        for _, row in health_df.iterrows()
    }


def test_f010_builds_intake_and_holds_from_fixture(tmp_path: Path) -> None:
    handoff_contract = get_f_output_contract("supplier_discovery_handoff")
    inbox_path = tmp_path / handoff_contract.rel_path
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURE_PATH, inbox_path)

    intake_df, holds_df, health_df = build_feeder_candidate_intake(
        root=tmp_path,
        intake_utc="2026-04-07T12:00:00Z",
    )

    intake_contract = get_f_output_contract("feeder_candidate_intake_live")
    holds_contract = get_f_output_contract("feeder_candidate_intake_holds")
    health_contract = get_f_output_contract("feeder_intake_health")

    assert len(intake_df) == 2
    assert len(holds_df) == 4
    assert set(intake_df["candidate_id"]) == {"DC-1001", "DC-1006"}
    assert "duplicate_discovery_candidate_id" in set(holds_df["hold_reason_codes"])
    assert (tmp_path / intake_contract.rel_path).exists()
    assert (tmp_path / holds_contract.rel_path).exists()
    assert (tmp_path / health_contract.rel_path).exists()
    assert list(intake_df.columns) == [*intake_contract.required_columns, *intake_contract.optional_columns]
    assert list(holds_df.columns) == [*holds_contract.required_columns, *holds_contract.optional_columns]
    statuses = _status_by_check(health_df)
    assert statuses["feeder_intake_source_contract"] == "ok"
    assert statuses["feeder_intake_quality"] == "warn"


def test_f010_missing_source_emits_warn_health(tmp_path: Path) -> None:
    intake_df, holds_df, health_df = build_feeder_candidate_intake(
        root=tmp_path,
        intake_utc="2026-04-07T12:30:00Z",
    )
    assert intake_df.empty
    assert holds_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_intake_source_contract"] == "warn"
    assert statuses["feeder_intake_quality"] == "warn"


def test_f010_missing_required_columns_emits_fail_health(tmp_path: Path) -> None:
    handoff_contract = get_f_output_contract("supplier_discovery_handoff")
    inbox_path = tmp_path / handoff_contract.rel_path
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text("discovery_candidate_id\nDC-ONLY-1\n", encoding="utf-8")

    intake_df, holds_df, health_df = build_feeder_candidate_intake(
        root=tmp_path,
        intake_utc="2026-04-07T13:00:00Z",
    )
    assert intake_df.empty
    assert holds_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_intake_source_contract"] == "fail"
    assert statuses["feeder_intake_quality"] == "fail"
