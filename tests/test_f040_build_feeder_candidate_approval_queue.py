from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F040_build_feeder_candidate_approval_queue import build_feeder_candidate_approval_queue
from scripts.flows.F._schemas import get_f_output_contract


def _status_by_check(health_df):
    return {row["check"]: row["status"] for _, row in health_df.iterrows()}


def test_f040_builds_recommendations_queue_and_decision_lineage(tmp_path: Path) -> None:
    source_contract = get_f_output_contract("feeder_shared_pass_logic_live")
    source_path = tmp_path / source_contract.rel_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        "\n".join(
            [
                "feeder_candidate_id,supplier_id,supplier_name,supplier_sku,supplier_title,barcode,unit_cost,currency,vat_rate,pass_logic_status,pass_logic_reason_codes,legacy_status_code,ready_for_amazon_checks_flag,manual_review_flag,hold_flag,pass_logic_utc,source_row_hash,source_file_path,source_seen_at_utc",
                "F-A,shure_cosmetics,Shure Cosmetics,SCS-A,Alpha Ready Product,5012345678901,9.99,GBP,20,ready_for_amazon_checks,,PASS,1,0,0,2026-04-07T16:00:00Z,hash-a,raw.csv,2026-04-07T15:59:00Z",
                "F-B,shure_cosmetics,Shure Cosmetics,SCS-B,Beta Watch Product,5012345678902,170.00,GBP,20,ready_for_amazon_checks,,PASS,1,0,0,2026-04-07T16:00:00Z,hash-b,raw.csv,2026-04-07T15:59:00Z",
                "F-C,shure_cosmetics,Shure Cosmetics,SCS-C,Gamma Manual Product,,12.00,GBP,20,manual_review,MISSING_BARCODE_TITLE_ONLY,REVIEW,0,1,0,2026-04-07T16:00:00Z,hash-c,raw.csv,2026-04-07T15:59:00Z",
                "F-D,shure_cosmetics,Shure Cosmetics,SCS-D,Delta Hold Product,,0,GBP,20,hold,NOCOST,FAIL,0,0,1,2026-04-07T16:00:00Z,hash-d,raw.csv,2026-04-07T15:59:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rec_df, queue_df, decisions_df, health_df = build_feeder_candidate_approval_queue(
        root=tmp_path,
        recommendation_utc="2026-04-07T18:10:00Z",
    )

    rec_contract = get_f_output_contract("feeder_candidate_recommendations_live")
    queue_contract = get_f_output_contract("feeder_approval_queue_live")
    decisions_contract = get_f_output_contract("feeder_approval_decisions_log")
    health_contract = get_f_output_contract("feeder_approval_health")

    assert len(rec_df) == 4
    assert len(queue_df) == 4
    assert len(decisions_df) == 4
    assert list(rec_df.columns) == [*rec_contract.required_columns, *rec_contract.optional_columns]
    assert list(queue_df.columns) == [*queue_contract.required_columns, *queue_contract.optional_columns]
    assert list(decisions_df.columns) == [*decisions_contract.required_columns, *decisions_contract.optional_columns]
    assert (tmp_path / rec_contract.rel_path).exists()
    assert (tmp_path / queue_contract.rel_path).exists()
    assert (tmp_path / decisions_contract.rel_path).exists()
    assert (tmp_path / health_contract.rel_path).exists()

    rec_status = dict(zip(rec_df["candidate_id"], rec_df["recommendation_status"]))
    assert rec_status["F-A"] == "approve_test_buy"
    assert rec_status["F-B"] == "watch"
    assert rec_status["F-C"] == "manual_review"
    assert rec_status["F-D"] == "reject"

    queue_status = dict(zip(queue_df["candidate_id"], queue_df["queue_status"]))
    assert queue_status["F-A"] == "needs_review"
    assert queue_status["F-B"] == "watch"
    assert queue_status["F-C"] == "manual_review"
    assert queue_status["F-D"] == "needs_review"

    statuses = _status_by_check(health_df)
    assert statuses["feeder_approval_source_contract"] == "ok"
    assert statuses["feeder_approval_quality"] == "ok"
    assert statuses["feeder_approval_manual_review_pressure"] == "warn"


def test_f040_missing_source_emits_warn_health(tmp_path: Path) -> None:
    rec_df, queue_df, decisions_df, health_df = build_feeder_candidate_approval_queue(
        root=tmp_path,
        recommendation_utc="2026-04-07T18:12:00Z",
    )
    assert rec_df.empty
    assert queue_df.empty
    assert decisions_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_approval_source_contract"] == "warn"
    assert statuses["feeder_approval_quality"] == "warn"
    assert statuses["feeder_approval_manual_review_pressure"] == "warn"


def test_f040_missing_required_columns_emits_fail_health(tmp_path: Path) -> None:
    source_contract = get_f_output_contract("feeder_shared_pass_logic_live")
    source_path = tmp_path / source_contract.rel_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("feeder_candidate_id\nF-ONLY\n", encoding="utf-8")

    rec_df, queue_df, decisions_df, health_df = build_feeder_candidate_approval_queue(
        root=tmp_path,
        recommendation_utc="2026-04-07T18:14:00Z",
    )
    assert rec_df.empty
    assert queue_df.empty
    assert decisions_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_approval_source_contract"] == "fail"
    assert statuses["feeder_approval_quality"] == "fail"
    assert statuses["feeder_approval_manual_review_pressure"] == "warn"


def test_f040_decision_lineage_seed_is_idempotent_for_pending_state(tmp_path: Path) -> None:
    source_contract = get_f_output_contract("feeder_shared_pass_logic_live")
    source_path = tmp_path / source_contract.rel_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        "\n".join(
            [
                "feeder_candidate_id,supplier_id,supplier_name,supplier_sku,supplier_title,barcode,unit_cost,currency,vat_rate,pass_logic_status,pass_logic_reason_codes,legacy_status_code,ready_for_amazon_checks_flag,manual_review_flag,hold_flag,pass_logic_utc,source_row_hash,source_file_path,source_seen_at_utc",
                "F-SEED,td_synnex,TD Synnex,TD-001,Seed Product,5012345678901,14.00,GBP,20,ready_for_amazon_checks,,PASS,1,0,0,2026-04-07T16:00:00Z,hash-seed,raw.tsv,2026-04-07T15:59:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _, _, first_decisions_df, _ = build_feeder_candidate_approval_queue(
        root=tmp_path,
        recommendation_utc="2026-04-07T18:20:00Z",
    )
    _, _, second_decisions_df, _ = build_feeder_candidate_approval_queue(
        root=tmp_path,
        recommendation_utc="2026-04-07T18:21:00Z",
    )

    assert len(first_decisions_df) == 1
    assert len(second_decisions_df) == 1
