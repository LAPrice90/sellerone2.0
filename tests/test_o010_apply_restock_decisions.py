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

from scripts.flows.O.O010_apply_restock_decisions import apply_restock_decisions
from scripts.flows.O._schemas import get_o_output_contract


def _write_recommendations(tmp_path: Path) -> None:
    rec_path = tmp_path / get_o_output_contract("restock_recommendations_live").rel_path
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_df = pd.DataFrame(
        [
            {
                "asof_utc": "2026-04-03T12:00:00Z",
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "reason_codes": "ROI_OK",
                "recommended_qty_raw": "6",
                "recommended_qty_rounded": "6",
                "target_days_cover": "30",
                "days_cover_available_only": "2",
                "days_cover_total_pipeline": "2",
                "current_supplier_buy_cost_gbp": "10",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "12",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "20",
                "forward_profit_per_unit_gbp": "2",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "asof_utc": "2026-04-03T12:00:00Z",
                "seller_sku": "SKU-B",
                "asin": "ASIN-B",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "recommendation_status": "test_restock",
                "reason_codes": "ROI_MID_BAND",
                "recommended_qty_raw": "5",
                "recommended_qty_rounded": "5",
                "target_days_cover": "10",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "current_supplier_buy_cost_gbp": "10",
                "current_supplier_cost_source": "supplier_cost_snapshot_test",
                "market_price_gbp": "11.5",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "15",
                "forward_profit_per_unit_gbp": "1.5",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
            },
            {
                "asof_utc": "2026-04-03T12:00:00Z",
                "seller_sku": "SKU-C",
                "asin": "ASIN-C",
                "supplier_code": "SUP-C",
                "supplier_name": "Gamma",
                "recommendation_status": "wait",
                "reason_codes": "ROI_BELOW_MIN_THRESHOLD",
                "recommended_qty_raw": "0",
                "recommended_qty_rounded": "0",
                "target_days_cover": "0",
                "days_cover_available_only": "12",
                "days_cover_total_pipeline": "12",
                "current_supplier_buy_cost_gbp": "8",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "8.2",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "forward_roi_pct": "2.5",
                "forward_profit_per_unit_gbp": "0.2",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ]
    )
    rec_df.to_csv(rec_path, index=False)


def _write_events(tmp_path: Path) -> None:
    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    events_df = pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T13:00:00Z",
                "event_id": "evt-001",
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "11.2",
                "confirmed_qty": "6",
                "snooze_until_utc": "",
                "decision_note": "price changed by supplier",
                "actor": "tester",
                "cost_mode": "live",
                "source_reference": "test",
                "profit_verdict": "safe_to_review",
                "profit_proof_source": "native_profit_proof",
                "profit_check_reference": "profit-check:SKU-A",
            },
            {
                "event_utc": "2026-04-03T13:01:00Z",
                "event_id": "evt-002",
                "seller_sku": "SKU-B",
                "asin": "ASIN-B",
                "action": "snooze",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "snooze_until_utc": "2026-04-08T00:00:00Z",
                "decision_note": "review next week",
                "actor": "tester",
                "cost_mode": "test",
                "source_reference": "test",
            },
            {
                "event_utc": "2026-04-03T13:02:00Z",
                "event_id": "evt-003",
                "seller_sku": "SKU-C",
                "asin": "ASIN-C",
                "action": "wait",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "snooze_until_utc": "",
                "decision_note": "leave as wait",
                "actor": "tester",
                "cost_mode": "live",
                "source_reference": "test",
            },
            {
                "event_utc": "2026-04-03T13:03:00Z",
                "event_id": "evt-004",
                "seller_sku": "SKU-B",
                "asin": "ASIN-B",
                "action": "bulk_review",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "snooze_until_utc": "",
                "decision_note": "review with supplier batch",
                "actor": "tester",
                "cost_mode": "test",
                "source_reference": "test",
            },
            {
                "event_utc": "2026-04-03T13:04:00Z",
                "event_id": "evt-005",
                "seller_sku": "SKU-C",
                "asin": "ASIN-C",
                "action": "skip",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "snooze_until_utc": "",
                "decision_note": "skip this cycle",
                "actor": "tester",
                "cost_mode": "live",
                "source_reference": "test",
            },
            {
                "event_utc": "2026-04-03T13:05:00Z",
                "event_id": "evt-001",
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "11.2",
                "confirmed_qty": "6",
                "snooze_until_utc": "",
                "decision_note": "duplicate event id",
                "actor": "tester",
                "cost_mode": "live",
                "source_reference": "test",
            },
        ]
    )
    events_df.to_csv(inbox_path, index=False)


def test_o010_applies_valid_events_with_recalc_and_supported_actions(tmp_path: Path) -> None:
    _write_recommendations(tmp_path)
    _write_events(tmp_path)

    append_df, full_log_df = apply_restock_decisions(
        root=tmp_path,
        applied_utc="2026-04-03T14:00:00Z",
    )
    by_event = append_df.set_index("event_id")

    assert len(append_df) == 5
    assert len(full_log_df) == 5

    approve = by_event.loc["evt-001"]
    assert approve["decision_action"] == "approve_full_restock"
    assert approve["original_recommendation_status"] == "full_restock"
    assert approve["final_decision_status"] == "wait"
    assert float(approve["recalculated_forward_roi_pct"]) < 10.0
    assert approve["decision_result_note"] == "status_changed_after_confirmed_cost_recalc"
    assert approve["profit_verdict"] == "safe_to_review"
    assert approve["profit_proof_source"] == "native_profit_proof"
    assert approve["profit_check_reference"] == "profit-check:SKU-A"

    snooze = by_event.loc["evt-002"]
    assert snooze["final_decision_status"] == "snooze"
    assert snooze["snooze_until_utc"] == "2026-04-08T00:00:00Z"

    wait = by_event.loc["evt-003"]
    assert wait["final_decision_status"] == "wait"

    bulk = by_event.loc["evt-004"]
    assert bulk["final_decision_status"] == "bulk_review"

    skip = by_event.loc["evt-005"]
    assert skip["final_decision_status"] == "skip"


def test_o010_uses_legacy_bridge_for_no_data_test_candidate(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "O" / "live"
    inbox_dir = tmp_path / "out" / "systems" / "O" / "inbox"
    live_dir.mkdir(parents=True, exist_ok=True)
    inbox_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {
                "asof_utc": "2026-05-22T09:00:00Z",
                "seller_sku": "SKU-LEGACY-NODATA",
                "asin": "ASIN-LEGACY-NODATA",
                "supplier_code": "NATIVE",
                "supplier_name": "Native Supplier",
                "recommendation_status": "wait",
                "reason_codes": "NATIVE_STALE_WAIT",
                "recommended_qty_raw": "0",
                "recommended_qty_rounded": "0",
                "target_days_cover": "0",
                "days_cover_available_only": "99",
                "days_cover_total_pipeline": "99",
                "current_supplier_buy_cost_gbp": "8",
                "current_supplier_cost_source": "native",
                "market_price_gbp": "8.1",
                "market_price_basis_used": "native",
                "forward_roi_pct": "1",
                "forward_profit_per_unit_gbp": "0.1",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            }
        ]
    ).to_csv(live_dir / "restock_recommendations_live.csv", index=False)
    pd.DataFrame(
        [
            {
                "bridge_utc": "2026-05-22T10:00:00Z",
                "source_system": "legacy_purchase_list",
                "source_sheet_id": "sheet-1",
                "source_sheet_title": "Amazon Supplier Process",
                "source_tab": "Purchase List",
                "source_row_number": "12",
                "source_reference": "legacy_purchase_list:sheet-1:Purchase List:row12",
                "supplier_name": "Legacy Supplier",
                "seller_sku": "SKU-LEGACY-NODATA",
                "asin": "ASIN-LEGACY-NODATA",
                "title": "Legacy No Data",
                "display_qtys_label": "Unit",
                "suggested_action": "test_restock",
                "recommendation_status": "test_restock",
                "sheet_recommend_label": "No Data",
                "suggested_qty": "1",
                "recommended_qty_rounded": "1",
                "current_supplier_buy_cost_gbp": "3",
                "suggested_unit_cost_gbp": "3",
                "queue_status": "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_no_data",
                "bridge_status": "ready",
                "bridge_note": "LEGACY_PURCHASE_LIST_NO_DATA|NO_DATA_TEST_CANDIDATE",
                "reason_codes": "LEGACY_PURCHASE_LIST_NO_DATA|NO_DATA_TEST_CANDIDATE",
            }
        ]
    ).to_csv(live_dir / "legacy_purchase_list_bridge.csv", index=False)
    pd.DataFrame(
        [
            {
                "event_utc": "2026-05-22T10:05:00Z",
                "event_id": "evt-legacy-nodata",
                "seller_sku": "SKU-LEGACY-NODATA",
                "asin": "ASIN-LEGACY-NODATA",
                "action": "approve_test_restock",
                "confirmed_unit_cost": "3",
                "confirmed_qty": "1",
                "snooze_until_utc": "",
                "decision_note": "legacy no data test",
                "actor": "tester",
                "cost_mode": "legacy_sheet",
                "source_reference": "o_ui_supplier_batch:Legacy Supplier|legacy_purchase_list|legacy_purchase_list:sheet-1:Purchase List:row12",
            }
        ]
    ).to_csv(inbox_dir / "restock_decision_events.csv", index=False)

    append_df, _ = apply_restock_decisions(
        root=tmp_path,
        applied_utc="2026-05-22T10:10:00Z",
    )

    row = append_df.iloc[0]
    assert row["original_recommendation_status"] == "test_restock"
    assert row["final_decision_status"] == "test_restock"
    assert row["cost_mode"] == "legacy_sheet"
    assert row["recommendation_basis"] == "legacy_purchase_list_no_data"
    assert row["recommendation_asof_utc"] == "2026-05-22T10:00:00Z"
    assert row["decision_result_note"] == "legacy_no_data_test_candidate_no_roi_recalc"


def test_o010_is_append_only_and_skips_duplicate_event_ids(tmp_path: Path) -> None:
    _write_recommendations(tmp_path)
    _write_events(tmp_path)

    _, first_full_log = apply_restock_decisions(
        root=tmp_path,
        applied_utc="2026-04-03T14:00:00Z",
    )
    _, second_full_log = apply_restock_decisions(
        root=tmp_path,
        applied_utc="2026-04-03T14:10:00Z",
    )
    assert len(first_full_log) == 5
    assert len(second_full_log) == 5


def test_o010_event_id_scope_applies_only_selected_inbox_event(tmp_path: Path) -> None:
    _write_recommendations(tmp_path)
    _write_events(tmp_path)

    append_df, full_log_df = apply_restock_decisions(
        root=tmp_path,
        applied_utc="2026-04-03T14:00:00Z",
        event_ids={"evt-003"},
    )

    assert list(append_df["event_id"]) == ["evt-003"]
    assert list(full_log_df["event_id"]) == ["evt-003"]
    assert full_log_df.iloc[0]["final_decision_status"] == "wait"


def test_o010_rejects_commit_action_without_confirmed_price(tmp_path: Path) -> None:
    _write_recommendations(tmp_path)
    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T13:00:00Z",
                "event_id": "evt-missing-cost",
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "",
                "confirmed_qty": "5",
                "snooze_until_utc": "",
                "decision_note": "missing cost",
                "actor": "tester",
                "cost_mode": "live",
                "source_reference": "test",
            }
        ]
    ).to_csv(inbox_path, index=False)

    append_df, _ = apply_restock_decisions(
        root=tmp_path,
        applied_utc="2026-04-03T14:00:00Z",
    )
    row = append_df.iloc[0]
    assert row["final_decision_status"] == "invalid_event"
    assert row["decision_result_note"] == "confirmed_unit_cost_required_for_approval"


def test_o010_blocks_over_max_confirmed_cost_even_if_event_submitted(tmp_path: Path) -> None:
    _write_recommendations(tmp_path)
    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "event_utc": "2026-04-03T13:00:00Z",
                "event_id": "evt-over-max",
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "12",
                "confirmed_qty": "5",
                "snooze_until_utc": "",
                "decision_note": "over max test",
                "actor": "tester",
                "cost_mode": "live",
                "source_reference": "test",
                "max_safe_unit_cost_gbp": "10",
                "current_price_list_unit_cost_gbp": "12",
                "usual_paid_unit_cost_gbp": "9",
                "price_list_change_status": "cost_up",
                "price_status": "over_max_snooze_candidate",
            }
        ]
    ).to_csv(inbox_path, index=False)

    append_df, _ = apply_restock_decisions(
        root=tmp_path,
        applied_utc="2026-04-03T14:00:00Z",
    )

    row = append_df.iloc[0]
    assert row["final_decision_status"] == "wait"
    assert row["decision_result_note"] == "confirmed_cost_above_max_safe_cost"
    assert row["confirmed_price_safety_status"] == "confirmed_over_max_blocked"
    assert row["confirmed_vs_max_delta_gbp"] == "2"
