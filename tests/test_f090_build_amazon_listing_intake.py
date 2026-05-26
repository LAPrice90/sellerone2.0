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

from scripts.flows.F.F090_build_amazon_listing_intake import build_amazon_listing_intake
from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df


OBSERVED = "2026-05-01T10:30:00Z"


def _write_manifest_and_pass_pack(tmp_path: Path, *, include_cost: bool = True) -> None:
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
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "f_live_price_file_pass_review_latest.csv"
    pass_row = {
        "observed_utc": "2026-05-01T10:00:00Z",
        "active_supplier_id": "supplier_a",
        "active_run_id": "run_1",
        "review_batch_id": "pass_batch_001",
        "candidate_id": "cand_1",
        "supplier_sku": "SUP-1",
        "barcode": "5012345678901",
        "asin": "B000000001",
        "title": "Review Product",
        "brand": "Brand A",
        "main_rank": "1234",
        "review_priority_score": "10",
        "f032_decision_id": "f032_test_decision",
        "f032_action": "allow_if_other_checks_pass",
    }
    if include_cost:
        pass_row["supplier_cost_gbp"] = "3.50"
    pd.DataFrame([pass_row]).to_csv(pass_path, index=False)

    manifest = pd.DataFrame(
        [
            {
                "built_at_utc": OBSERVED,
                "supplier_id": "supplier_a",
                "supplier_name": "Supplier A",
                "run_id": "run_1",
                "review_snapshot_id": "20260501T103000Z",
                "source_file_path": "source.xlsx",
                "source_seen_at_utc": "2026-05-01T09:00:00Z",
                "completed_at_utc": "2026-05-01T10:00:00Z",
                "pass_review_rows": "1",
                "near_miss_review_rows": "0",
                "hard_reject_rows": "0",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": "",
                "summary_path": "",
                "handoff_dir": str(handoff_dir),
                "published_to_operator_latest_flag": "0",
                "ai_gate_status": "passed",
                "ai_gate_observed_utc": OBSERVED,
                "ai_gate_version": "F032_review_intelligence_v1",
                "ai_gate_health_path": str(handoff_dir / "ai_review_intelligence_gate_health.csv"),
                "ai_gate_decision_path": str(handoff_dir / "ai_review_intelligence_decisions.csv"),
                "ai_gate_checklist_path": str(handoff_dir / "ai_review_intelligence_checklist.csv"),
                "ai_gate_rule_suggestion_path": str(handoff_dir / "ai_rule_tightening_suggestions.csv"),
                "ai_gate_rescan_queue_path": str(handoff_dir / "ai_rescan_queue.csv"),
                "ai_gate_removed_audit_path": str(handoff_dir / "ai_removed_from_clean_pass_audit.csv"),
                "ai_gate_manual_review_path": str(handoff_dir / "ai_manual_review.csv"),
                "raw_candidate_manifest_path": str(handoff_dir / "candidate_manifest.csv"),
                "raw_pass_review_path": str(handoff_dir / "raw_pass.csv"),
                "raw_near_miss_review_path": str(handoff_dir / "raw_near.csv"),
                "ai_gate_fail_rows": "0",
                "ai_gate_warn_rows": "0",
                "ai_gate_clear_rows": "1",
                "ai_gate_manual_rows": "0",
                "ai_gate_rescan_rows": "0",
                "ai_gate_removed_rows": "0",
                "operator_ready_flag": "1",
                "block_reason": "",
                "notes": "test manifest",
            }
        ]
    )
    manifest.to_csv(handoff_dir / "manifest.csv", index=False)


def _write_latest_analysis_pass_pack(tmp_path: Path) -> None:
    report_dir = tmp_path / "out" / "analysis_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-05-01T10:00:00Z",
                "active_supplier_id": "supplier_a",
                "active_run_id": "run_1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand_1",
                "supplier_sku": "SUP-1",
                "barcode": "5012345678901",
                "asin": "B000000001",
                "title": "Review Product",
                "brand": "Brand A",
                "main_rank": "1234",
                "review_priority_score": "10",
                "supplier_cost_gbp": "3.50",
            }
        ]
    ).to_csv(report_dir / "f_live_price_file_pass_review_latest.csv", index=False)
    pd.DataFrame(
        [
            {"observed_utc": OBSERVED, "metric": "active_supplier_id", "value": "supplier_a"},
            {"observed_utc": OBSERVED, "metric": "active_run_id", "value": "run_1"},
            {"observed_utc": OBSERVED, "metric": "source_seen_at_utc", "value": "2026-05-01T09:00:00Z"},
            {"observed_utc": OBSERVED, "metric": "pass_review_rows", "value": "1"},
        ]
    ).to_csv(report_dir / "f_live_price_file_review_summary_latest.csv", index=False)


def _write_dashboard_cost_lookup(tmp_path: Path, *, unit_cost: str = "3.50") -> None:
    report_dir = tmp_path / "out" / "analysis_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand_1",
                "supplier_sku": "SUP-1",
                "asin": "B000000001",
                "unit_cost": unit_cost,
            }
        ]
    ).to_csv(report_dir / "f_dashboard_yes_no_rescan_plan_latest.csv", index=False)


def _write_review_event(
    tmp_path: Path,
    *,
    decision: str,
    event_utc: str = "2026-05-01T10:20:00Z",
    country_of_origin: str = "GB",
    starting_price_gbp: str = "12.34",
) -> None:
    write_f_contract_df(
        tmp_path,
        "feeder_review_events",
        pd.DataFrame(
            [
                {
                    "event_utc": event_utc,
                    "event_id": f"evt-{decision or 'blank'}-{event_utc[-3:-1]}",
                    "active_supplier_id": "supplier_a",
                    "active_run_id": "run_1",
                    "review_pack_type": "passes",
                    "review_batch_id": "pass_batch_001",
                    "candidate_id": "cand_1",
                    "supplier_sku": "SUP-1",
                    "asin_raw": "B000000001",
                    "asin_padded": "B000000001",
                    "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                    "review_decision": decision,
                    "review_note": "operator checked",
                    "actor": "tester",
                    "source_reference": "unit_test",
                    "title": "Review Product",
                    "brand": "Brand A",
                    "main_rank": "1234",
                    "review_priority_score": "10",
                    "country_of_origin": country_of_origin,
                    "product_tax_code": "A_GEN_STANDARD",
                    "currency_code": "GBP",
                    "price_includes_tax": "1",
                    "starting_price_gbp": starting_price_gbp,
                }
            ]
        ),
    )


def _write_profile_event(
    tmp_path: Path,
    *,
    event_utc: str = "2026-05-01T10:25:00Z",
    country_of_origin: str = "GB",
    starting_price_gbp: str = "12.34",
    purchase_pack_size: str = "1",
    sold_pack_size: str = "1",
    vat_confirmed_flag: str = "1",
) -> None:
    write_f_contract_df(
        tmp_path,
        "amazon_listing_profile_events",
        pd.DataFrame(
            [
                {
                    "event_utc": event_utc,
                    "event_id": f"profile-{event_utc[-3:-1]}",
                    "active_supplier_id": "supplier_a",
                    "active_run_id": "run_1",
                    "review_pack_type": "passes",
                    "review_batch_id": "pass_batch_001",
                    "candidate_id": "cand_1",
                    "supplier_sku": "SUP-1",
                    "asin_raw": "B000000001",
                    "asin_padded": "B000000001",
                    "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                    "profile_status": "complete",
                    "country_of_origin": country_of_origin,
                    "purchase_pack_size": purchase_pack_size,
                    "sold_pack_size": sold_pack_size,
                    "vat_confirmed_flag": vat_confirmed_flag,
                    "product_tax_code": "A_GEN_STANDARD",
                    "currency_code": "GBP",
                    "price_includes_tax": "1",
                    "starting_price_gbp": starting_price_gbp,
                    "actor": "tester",
                    "source_reference": "unit_test_profile",
                    "vat_source_value": "20%",
                    "supplier_case_qty": "1",
                    "supplier_case_multiple": "0",
                    "valid_order_step": "1",
                    "moq": "1",
                    "target_margin": "30",
                    "starting_quantity": "0",
                    "condition_type": "new_new",
                    "profile_note": "profile complete",
                }
            ]
        ),
    )


def test_f090_raw_scanner_pass_without_review_event_creates_no_intake(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_reason"] == "no_review_pass_event"


def test_f090_pass_missing_required_dashboard_yes_no_is_held_for_backtrack(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)
    pass_path = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
        / "f_live_price_file_pass_review_latest.csv"
    )
    pass_df = pd.read_csv(pass_path, dtype=str).fillna("")
    pass_df["seller_history_code"] = "seller_history_clear"
    pass_df["seller_history_dashboard_yes_or_no"] = ""
    pass_df.to_csv(pass_path, index=False)

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_reason"] == "dashboard_yes_no_backtrack_required"


def test_f090_likely_dashboard_pass_is_not_held_for_backtrack(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)
    pass_path = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
        / "f_live_price_file_pass_review_latest.csv"
    )
    pass_df = pd.read_csv(pass_path, dtype=str).fillna("")
    pass_df["seller_history_code"] = "seller_history_clear"
    pass_df["seller_history_dashboard_yes_or_no"] = "LIKELY"
    pass_df["seller_history_dashboard_delivery_classification"] = "LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY"
    pass_df["seller_history_dashboard_separate_delivery_required"] = "1"
    pass_df.to_csv(pass_path, index=False)
    _write_review_event(tmp_path, decision="pass")
    _write_profile_event(tmp_path)

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 1
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert holds.empty


def test_f090_review_pass_without_completed_pack_is_held(tmp_path: Path) -> None:
    _write_review_event(tmp_path, decision="pass")

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_reason"] == "no_completed_review_pack"


def test_f090_raw_manifest_without_ai_gate_is_ignored(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)
    manifest_path = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "supplier_a"
        / "run_1"
        / "manifest.csv"
    )
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    manifest["ai_gate_status"] = ""
    manifest["operator_ready_flag"] = "0"
    manifest.to_csv(manifest_path, index=False)
    _write_review_event(tmp_path, decision="pass")
    _write_profile_event(tmp_path)

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_reason"] == "no_completed_review_pack"


def test_f090_completed_pack_plus_latest_pass_creates_one_intake(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)
    _write_review_event(tmp_path, decision="pass")
    _write_profile_event(tmp_path)

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 1
    row = out.iloc[0]
    assert row["candidate_id"] == "cand_1"
    assert row["asin"] == "B000000001"
    assert row["supplier_cost_gbp"] == "3.50"
    assert row["starting_price_gbp"] == "12.34"
    assert row["country_of_origin"] == "GB"
    assert row["purchase_pack_size"] == "1"
    assert row["sold_pack_size"] == "1"
    assert row["supplier_case_qty"] == "1"
    assert row["valid_order_step"] == "1"
    assert row["moq"] == "1"
    assert row["target_margin"] == "30"
    assert row["vat_source_value"] == "20"
    assert row["vat_confirmed_flag"] == "1"
    assert row["product_tax_code"] == "A_GEN_STANDARD"
    assert row["currency_code"] == "GBP"
    assert row["price_includes_tax"] == "1"
    assert row["intake_status"] == "ready_for_sku_reservation"


def test_f090_latest_analysis_pack_fallback_is_blocked_when_manifest_missing(tmp_path: Path) -> None:
    _write_latest_analysis_pass_pack(tmp_path)
    _write_review_event(tmp_path, decision="pass")
    _write_profile_event(tmp_path)

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_reason"] == "no_completed_review_pack"


def test_f090_uses_dashboard_cost_lookup_when_pass_pack_cost_is_missing(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path, include_cost=False)
    _write_dashboard_cost_lookup(tmp_path, unit_cost="4.25")
    _write_review_event(tmp_path, decision="pass")
    _write_profile_event(tmp_path)

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 1
    assert out.iloc[0]["supplier_cost_gbp"] == "4.25"


def test_f090_review_pass_without_profile_review_is_held(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)
    _write_review_event(tmp_path, decision="pass")

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_reason"] == "product_listing_profile_required"


def test_f090_profile_review_missing_country_of_origin_is_held(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)
    _write_review_event(tmp_path, decision="pass")
    _write_profile_event(tmp_path, country_of_origin="")

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_reason"] == "missing_listing_compliance:country_of_origin"


def test_f090_profile_review_missing_pack_size_and_vat_confirmation_is_held(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)
    _write_review_event(tmp_path, decision="pass")
    _write_profile_event(tmp_path, purchase_pack_size="", vat_confirmed_flag="0")

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert len(holds.index) == 1
    assert holds.iloc[0]["hold_reason"] == "missing_listing_compliance:purchase_pack_size,vat_confirmed_flag"


def test_f090_later_fail_after_pass_blocks_intake(tmp_path: Path) -> None:
    _write_manifest_and_pass_pack(tmp_path)
    write_f_contract_df(
        tmp_path,
        "feeder_review_events",
        pd.DataFrame(
            [
                {
                    "event_utc": "2026-05-01T10:20:00Z",
                    "event_id": "evt-pass",
                    "active_supplier_id": "supplier_a",
                    "active_run_id": "run_1",
                    "review_pack_type": "passes",
                    "review_batch_id": "pass_batch_001",
                    "candidate_id": "cand_1",
                    "supplier_sku": "SUP-1",
                    "asin_raw": "B000000001",
                    "asin_padded": "B000000001",
                    "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                    "review_decision": "pass",
                    "review_note": "",
                    "actor": "tester",
                    "source_reference": "unit_test",
                    "country_of_origin": "GB",
                    "product_tax_code": "A_GEN_STANDARD",
                    "currency_code": "GBP",
                    "price_includes_tax": "1",
                    "starting_price_gbp": "12.34",
                },
                {
                    "event_utc": "2026-05-01T10:21:00Z",
                    "event_id": "evt-fail",
                    "active_supplier_id": "supplier_a",
                    "active_run_id": "run_1",
                    "review_pack_type": "passes",
                    "review_batch_id": "pass_batch_001",
                    "candidate_id": "cand_1",
                    "supplier_sku": "SUP-1",
                    "asin_raw": "B000000001",
                    "asin_padded": "B000000001",
                    "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                    "review_decision": "fail",
                    "review_note": "changed mind",
                    "actor": "tester",
                    "source_reference": "unit_test",
                },
            ]
        ),
    )

    out = build_amazon_listing_intake(root=tmp_path, observed_utc=OBSERVED)

    assert len(out.index) == 0
    holds = read_f_contract_df(tmp_path, "amazon_listing_holds_live")
    assert holds.iloc[0]["hold_reason"] == "latest_review_decision_not_pass"
