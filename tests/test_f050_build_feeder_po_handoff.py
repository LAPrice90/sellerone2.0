from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F050_build_feeder_po_handoff import build_feeder_po_handoff
from scripts.flows.F._schemas import get_f_output_contract


def _status_by_check(health_df):
    return {row["check"]: row["status"] for _, row in health_df.iterrows()}


def test_f050_builds_approved_only_handoff_and_explicit_holds(tmp_path: Path) -> None:
    queue_contract = get_f_output_contract("feeder_approval_queue_live")
    queue_path = tmp_path / queue_contract.rel_path
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        "\n".join(
            [
                "queue_utc,candidate_id,feeder_candidate_id,supplier_id,supplier_name,supplier_sku,supplier_title,recommendation_status,recommended_test_qty,queue_status,decision_status,approval_required_flag,owner,snooze_until_utc,source_row_hash,source_file_path,source_seen_at_utc",
                "2026-04-07T18:30:00Z,F-A,F-A,shure_cosmetics,Shure Cosmetics,SCS-A,Approved Product,approve_test_buy,5,needs_review,pending_review,1,feeder_operator,,hash-a,raw.csv,2026-04-07T18:20:00Z",
                "2026-04-07T18:30:00Z,F-B,F-B,shure_cosmetics,Shure Cosmetics,SCS-B,Pending Product,approve_test_buy,5,needs_review,pending_review,1,feeder_operator,,hash-b,raw.csv,2026-04-07T18:20:00Z",
                "2026-04-07T18:30:00Z,F-C,F-C,td_synnex,TD Synnex,TD-C,Other Supplier,approve_test_buy,6,needs_review,pending_review,1,feeder_operator,,hash-c,raw.tsv,2026-04-07T18:20:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    decisions_contract = get_f_output_contract("feeder_approval_decisions_log")
    decisions_path = tmp_path / decisions_contract.rel_path
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    decisions_path.write_text(
        "\n".join(
            [
                "decision_utc,event_id,candidate_id,feeder_candidate_id,decision_action,final_decision_status,decision_source,recommendation_status,recommended_test_qty,actor,decision_note,source_row_hash,source_file_path,source_seen_at_utc,supplier_id,supplier_sku",
                "2026-04-07T18:33:00Z,FDEC-A,F-A,F-A,approve,approved_for_po,user,approve_test_buy,5,ops,approved,hash-a,raw.csv,2026-04-07T18:20:00Z,shure_cosmetics,SCS-A",
                "2026-04-07T18:34:00Z,FDEC-B,F-B,F-B,seed_pending_review,pending_review,system_seed,approve_test_buy,5,system,pending,hash-b,raw.csv,2026-04-07T18:20:00Z,shure_cosmetics,SCS-B",
                "2026-04-07T18:35:00Z,FDEC-C,F-C,F-C,approve,approved_for_po,user,approve_test_buy,6,ops,approved,hash-c,raw.tsv,2026-04-07T18:20:00Z,td_synnex,TD-C",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rec_contract = get_f_output_contract("feeder_candidate_recommendations_live")
    rec_path = tmp_path / rec_contract.rel_path
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(
        "\n".join(
            [
                "candidate_id,feeder_candidate_id,supplier_id,supplier_name,supplier_sku,supplier_title,barcode,unit_cost,currency,vat_rate,viability_status,viability_reason_codes,estimated_demand,estimated_roi_pct,estimated_margin_gbp,recommended_test_qty,recommendation_status,recommendation_reason_codes,approval_required_flag,decision_status,recommendation_utc,source_row_hash,source_file_path,source_seen_at_utc,source_url,pass_logic_status,pass_logic_reason_codes,notes",
                "F-A,F-A,shure_cosmetics,Shure Cosmetics,SCS-A,Approved Product,5012345678901,10.00,GBP,20,viable,baseline_viable,high,20.00,2.00,5,approve_test_buy,approve_baseline_viable,1,pending_review,2026-04-07T18:30:00Z,hash-a,raw.csv,2026-04-07T18:20:00Z,https://example,ready_for_amazon_checks,,",
                "F-B,F-B,shure_cosmetics,Shure Cosmetics,SCS-B,Pending Product,5012345678902,11.00,GBP,20,viable,baseline_viable,high,20.00,2.20,5,approve_test_buy,approve_baseline_viable,1,pending_review,2026-04-07T18:30:00Z,hash-b,raw.csv,2026-04-07T18:20:00Z,https://example,ready_for_amazon_checks,,",
                "F-C,F-C,td_synnex,TD Synnex,TD-C,Other Supplier,5012345678903,12.00,GBP,20,viable,baseline_viable,high,20.00,2.40,6,approve_test_buy,approve_baseline_viable,1,pending_review,2026-04-07T18:30:00Z,hash-c,raw.tsv,2026-04-07T18:20:00Z,https://example,ready_for_amazon_checks,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ready_df, holds_df, health_df = build_feeder_po_handoff(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        handoff_utc="2026-04-07T18:40:00Z",
    )

    ready_contract = get_f_output_contract("feeder_po_handoff_ready_live")
    holds_contract = get_f_output_contract("feeder_po_handoff_holds")
    health_contract = get_f_output_contract("feeder_po_handoff_health")

    assert len(ready_df) == 1
    assert len(holds_df) == 1
    assert list(ready_df.columns) == [*ready_contract.required_columns, *ready_contract.optional_columns]
    assert list(holds_df.columns) == [*holds_contract.required_columns, *holds_contract.optional_columns]
    assert (tmp_path / ready_contract.rel_path).exists()
    assert (tmp_path / holds_contract.rel_path).exists()
    assert (tmp_path / health_contract.rel_path).exists()

    assert set(ready_df["candidate_id"]) == {"F-A"}
    assert ready_df.iloc[0]["approved_test_qty"] == "5"
    assert ready_df.iloc[0]["initial_unit_cost"] == "10.00"
    assert set(holds_df["candidate_id"]) == {"F-B"}
    assert "decision_not_approved:pending_review" in holds_df.iloc[0]["hold_reason_codes"]

    statuses = _status_by_check(health_df)
    assert statuses["feeder_po_handoff_source_contract"] == "ok"
    assert statuses["feeder_po_handoff_quality"] == "ok"


def test_f050_missing_source_emits_warn_health(tmp_path: Path) -> None:
    ready_df, holds_df, health_df = build_feeder_po_handoff(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        handoff_utc="2026-04-07T18:42:00Z",
    )
    assert ready_df.empty
    assert holds_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_po_handoff_source_contract"] == "warn"
    assert statuses["feeder_po_handoff_quality"] == "warn"


def test_f050_missing_required_columns_emits_fail_health(tmp_path: Path) -> None:
    queue_contract = get_f_output_contract("feeder_approval_queue_live")
    queue_path = tmp_path / queue_contract.rel_path
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text("candidate_id\nF-ONLY\n", encoding="utf-8")

    decisions_contract = get_f_output_contract("feeder_approval_decisions_log")
    decisions_path = tmp_path / decisions_contract.rel_path
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    decisions_path.write_text("candidate_id\nF-ONLY\n", encoding="utf-8")

    ready_df, holds_df, health_df = build_feeder_po_handoff(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        handoff_utc="2026-04-07T18:44:00Z",
    )
    assert ready_df.empty
    assert holds_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_po_handoff_source_contract"] == "fail"
    assert statuses["feeder_po_handoff_quality"] == "fail"
