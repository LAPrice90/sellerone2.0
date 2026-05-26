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
from scripts.flows.F.F020_build_feeder_candidate_classification import build_feeder_candidate_first_pass_classification
from scripts.flows.F._schemas import get_f_output_contract


SUPPLIER_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "f_phase1" / "supplier_discovery_handoff_fixture.csv"


def _status_by_check(health_df):
    return {
        row["check"]: row["status"]
        for _, row in health_df.iterrows()
    }


def test_f020_builds_normalized_and_first_pass_outputs_from_f010(tmp_path: Path) -> None:
    handoff_contract = get_f_output_contract("supplier_discovery_handoff")
    inbox_path = tmp_path / handoff_contract.rel_path
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(SUPPLIER_FIXTURE_PATH, inbox_path)

    build_feeder_candidate_intake(
        root=tmp_path,
        intake_utc="2026-04-07T12:00:00Z",
    )
    normalized_df, classification_df, holds_df, health_df = build_feeder_candidate_first_pass_classification(
        root=tmp_path,
        classification_utc="2026-04-07T12:10:00Z",
    )

    normalized_contract = get_f_output_contract("feeder_candidate_normalized_live")
    classification_contract = get_f_output_contract("feeder_candidate_first_pass_classification_live")
    holds_contract = get_f_output_contract("feeder_candidate_first_pass_holds")
    health_contract = get_f_output_contract("feeder_classification_health")

    assert len(normalized_df) == 2
    assert len(classification_df) == 2
    assert len(holds_df) == 0
    assert set(classification_df["first_pass_status"]) == {"ready_for_viability"}
    assert list(normalized_df.columns) == [*normalized_contract.required_columns, *normalized_contract.optional_columns]
    assert list(classification_df.columns) == [*classification_contract.required_columns, *classification_contract.optional_columns]
    assert list(holds_df.columns) == [*holds_contract.required_columns, *holds_contract.optional_columns]
    assert (tmp_path / normalized_contract.rel_path).exists()
    assert (tmp_path / classification_contract.rel_path).exists()
    assert (tmp_path / holds_contract.rel_path).exists()
    assert (tmp_path / health_contract.rel_path).exists()
    statuses = _status_by_check(health_df)
    assert statuses["feeder_classification_source_contract"] == "ok"
    assert statuses["feeder_classification_quality"] == "ok"


def test_f020_missing_source_emits_warn_health(tmp_path: Path) -> None:
    normalized_df, classification_df, holds_df, health_df = build_feeder_candidate_first_pass_classification(
        root=tmp_path,
        classification_utc="2026-04-07T12:30:00Z",
    )
    assert normalized_df.empty
    assert classification_df.empty
    assert holds_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_classification_source_contract"] == "warn"
    assert statuses["feeder_classification_quality"] == "warn"


def test_f020_missing_required_columns_emits_fail_health(tmp_path: Path) -> None:
    intake_contract = get_f_output_contract("feeder_candidate_intake_live")
    intake_path = tmp_path / intake_contract.rel_path
    intake_path.parent.mkdir(parents=True, exist_ok=True)
    intake_path.write_text("candidate_id\nC-100\n", encoding="utf-8")

    normalized_df, classification_df, holds_df, health_df = build_feeder_candidate_first_pass_classification(
        root=tmp_path,
        classification_utc="2026-04-07T13:00:00Z",
    )
    assert normalized_df.empty
    assert classification_df.empty
    assert holds_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_classification_source_contract"] == "fail"
    assert statuses["feeder_classification_quality"] == "fail"


def test_f020_routes_ready_manual_review_and_hold_rows(tmp_path: Path) -> None:
    intake_contract = get_f_output_contract("feeder_candidate_intake_live")
    intake_path = tmp_path / intake_contract.rel_path
    intake_path.parent.mkdir(parents=True, exist_ok=True)
    intake_path.write_text(
        "\n".join(
            [
                "candidate_id,source_discovery_candidate_id,source_discovery_run_id,asin,barcode,brand,chosen_supplier_id,chosen_supplier_name,price_list_status,price_list_artifact_path,handoff_ready_flag,intake_status,intake_reason_codes,intake_received_utc,source_row_ref,source_file_path,title,keyword_source,category_source,last_reviewed_utc",
                "READY-1,DC-READY-1,DR-A,B0READY001,,BrandR,SUP-1,Supplier One,acquired,out/raw/sup1.csv,1,intake_ready,,2026-04-07T12:00:00Z,2,tests/inbox.csv,Ready Title,kw,cat,2026-04-07T12:00:00Z",
                "MANUAL-1,DC-MANUAL-1,DR-B,B0MANU1234,5012345678901,BrandM,SUP-2,Supplier Two,acquired,out/raw/sup2.csv,1,intake_ready,,2026-04-07T12:00:00Z,3,tests/inbox.csv,Manual Title,kw,cat,2026-04-07T12:00:00Z",
                "HOLD-1,DC-HOLD-1,DR-C,,12345,BrandH,SUP-3,Supplier Three,acquired,out/raw/sup3.csv,1,intake_ready,,2026-04-07T12:00:00Z,4,tests/inbox.csv,Hold Title,kw,cat,2026-04-07T12:00:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    normalized_df, classification_df, holds_df, health_df = build_feeder_candidate_first_pass_classification(
        root=tmp_path,
        classification_utc="2026-04-07T13:10:00Z",
    )

    assert len(normalized_df) == 3
    assert len(classification_df) == 3
    assert len(holds_df) == 2
    status_map = dict(zip(classification_df["candidate_id"], classification_df["first_pass_status"]))
    assert status_map["READY-1"] == "ready_for_viability"
    assert status_map["MANUAL-1"] == "manual_review"
    assert status_map["HOLD-1"] == "hold"

    hold_reasons = holds_df.set_index("candidate_id")["hold_reason_codes"].to_dict()
    assert hold_reasons["MANUAL-1"] == "identity_dual_key_review"
    assert "invalid_barcode_format" in hold_reasons["HOLD-1"]
    assert "missing_identity_key" in hold_reasons["HOLD-1"]

    statuses = _status_by_check(health_df)
    assert statuses["feeder_classification_source_contract"] == "ok"
    assert statuses["feeder_classification_quality"] == "warn"
