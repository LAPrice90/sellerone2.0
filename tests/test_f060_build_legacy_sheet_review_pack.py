from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F060_build_legacy_sheet_review_pack import build_legacy_sheet_review_pack
from scripts.flows.F._schemas import get_f_output_contract


def _status_by_check(health_df):
    return {row["check"]: row["status"] for _, row in health_df.iterrows()}


def test_f060_builds_shure_only_legacy_review_pack(tmp_path: Path) -> None:
    rec_contract = get_f_output_contract("feeder_candidate_recommendations_live")
    rec_path = tmp_path / rec_contract.rel_path
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(
        "\n".join(
            [
                "candidate_id,feeder_candidate_id,supplier_id,supplier_name,supplier_sku,supplier_title,barcode,unit_cost,currency,vat_rate,viability_status,viability_reason_codes,estimated_demand,estimated_roi_pct,estimated_margin_gbp,recommended_test_qty,recommendation_status,recommendation_reason_codes,approval_required_flag,decision_status,recommendation_utc,source_row_hash,source_file_path,source_seen_at_utc",
                "F-S1,F-S1,shure_cosmetics,Shure Cosmetics,SCS-1,Shure One,5012345678901,10.00,GBP,20,viable,baseline_viable,high,20.00,2.00,5,approve_test_buy,approve_baseline_viable,1,pending_review,2026-04-07T18:30:00Z,hash-s1,raw.csv,2026-04-07T18:20:00Z",
                "F-S2,F-S2,shure_cosmetics,Shure Cosmetics,SCS-2,Shure Two,5012345678902,8.00,GBP,20,review,pass_logic_manual_review,medium,12.00,0.96,3,manual_review,manual_review_upstream,1,pending_review,2026-04-07T18:30:00Z,hash-s2,raw.csv,2026-04-07T18:20:00Z",
                "F-TD1,F-TD1,td_synnex,TD Synnex,TD-1,TD One,5012345678903,12.00,GBP,20,viable,baseline_viable,high,20.00,2.40,6,approve_test_buy,approve_baseline_viable,1,pending_review,2026-04-07T18:30:00Z,hash-td1,raw.tsv,2026-04-07T18:20:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    dec_contract = get_f_output_contract("feeder_approval_decisions_log")
    dec_path = tmp_path / dec_contract.rel_path
    dec_path.parent.mkdir(parents=True, exist_ok=True)
    dec_path.write_text(
        "\n".join(
            [
                "decision_utc,event_id,candidate_id,feeder_candidate_id,decision_action,final_decision_status,decision_source,recommendation_status,recommended_test_qty,actor,decision_note,source_row_hash,source_file_path,source_seen_at_utc,supplier_id,supplier_sku",
                "2026-04-07T18:32:00Z,FDEC-S1,F-S1,F-S1,approve,approved_for_po,user,approve_test_buy,5,ops,approved,hash-s1,raw.csv,2026-04-07T18:20:00Z,shure_cosmetics,SCS-1",
                "2026-04-07T18:33:00Z,FDEC-S2,F-S2,F-S2,seed_pending_review,pending_review,system_seed,manual_review,3,system,pending,hash-s2,raw.csv,2026-04-07T18:20:00Z,shure_cosmetics,SCS-2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first_df, second_df, bot_df, health_df = build_legacy_sheet_review_pack(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        review_utc="2026-04-07T19:10:00Z",
    )

    first_contract = get_f_output_contract("feeder_legacy_first_checks_live")
    second_contract = get_f_output_contract("feeder_legacy_second_checks_live")
    bot_contract = get_f_output_contract("feeder_legacy_bot_status_live")
    health_contract = get_f_output_contract("feeder_legacy_sheet_health")

    assert len(first_df) == 2
    assert len(second_df) == 2
    assert len(bot_df) == 1
    assert list(first_df.columns) == [*first_contract.required_columns, *first_contract.optional_columns]
    assert list(second_df.columns) == [*second_contract.required_columns, *second_contract.optional_columns]
    assert list(bot_df.columns) == [*bot_contract.required_columns, *bot_contract.optional_columns]
    assert (tmp_path / first_contract.rel_path).exists()
    assert (tmp_path / second_contract.rel_path).exists()
    assert (tmp_path / bot_contract.rel_path).exists()
    assert (tmp_path / health_contract.rel_path).exists()

    assert set(first_df["supplier"]) == {"Shure Cosmetics"}
    assert "TD One" not in set(first_df["title"])
    pf_map = dict(zip(first_df["supplier_sku"], first_df["pf"]))
    assert pf_map["SCS-1"] == "PASS"
    assert pf_map["SCS-2"] == "FAIL"

    send_map = dict(zip(second_df["sku"], second_df["send"]))
    assert send_map["SCS-1"] == "SEND"
    assert send_map["SCS-2"] == ""

    statuses = _status_by_check(health_df)
    assert statuses["feeder_legacy_sheet_source_contract"] == "ok"
    assert statuses["feeder_legacy_sheet_quality"] == "ok"
    assert statuses["feeder_legacy_sheet_send_ready"] == "ok"


def test_f060_missing_source_emits_warn_health(tmp_path: Path) -> None:
    first_df, second_df, bot_df, health_df = build_legacy_sheet_review_pack(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        review_utc="2026-04-07T19:12:00Z",
    )
    assert first_df.empty
    assert second_df.empty
    assert bot_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_legacy_sheet_source_contract"] == "warn"
    assert statuses["feeder_legacy_sheet_quality"] == "warn"
    assert statuses["feeder_legacy_sheet_send_ready"] == "warn"


def test_f060_missing_required_columns_emits_fail_health(tmp_path: Path) -> None:
    rec_contract = get_f_output_contract("feeder_candidate_recommendations_live")
    rec_path = tmp_path / rec_contract.rel_path
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text("candidate_id\nF-ONLY\n", encoding="utf-8")

    first_df, second_df, bot_df, health_df = build_legacy_sheet_review_pack(
        root=tmp_path,
        supplier_id="shure_cosmetics",
        review_utc="2026-04-07T19:14:00Z",
    )
    assert first_df.empty
    assert second_df.empty
    assert bot_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_legacy_sheet_source_contract"] == "fail"
    assert statuses["feeder_legacy_sheet_quality"] == "fail"
    assert statuses["feeder_legacy_sheet_send_ready"] == "warn"
