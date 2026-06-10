from __future__ import annotations

import sys
import time
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O400_operator_ui import (
    _apply_reorder_draft,
    _amazon_dp_url,
    _clear_reorder_drafts,
    _extract_reorder_draft,
    _feeder_review_done_key,
    _feeder_review_lane_display_label,
    _feeder_review_pack_work_phrase,
    _filter_restock_approval_preview_status,
    _filter_restock_approval_readiness_lane,
    _pad_asin_to_10,
    _humanize_intake_evidence_summary,
    _admin_compact_strip_html,
    _intake_choice_panel_html,
    _intake_focus_strip_html,
    _intake_submit_panel_html,
    _intake_image_html,
    _latest_price_list_live_event,
    _normalize_feeder_review_decision,
    _operator_sidebar_button_label,
    _operator_metric_card_html,
    _operator_local_form_panel_html,
    _operator_task_brief_html,
    _operator_work_card_html,
    _intake_alert_html,
    _intake_detail_drawer_html,
    _operator_dataset_names_for_route,
    _inbound_fba_source_options_summary,
    _profit_input_blocker_summary,
    _token_cost_trust_label,
    _render_inline_notice,
    _render_intake_empty_state_html,
    _render_intake_sent_choice_card_html,
    _render_operator_theme_css,
    _render_po_draft_line_html,
    _restock_inbound_cost_proof_summary,
    _latest_price_list_live_status,
    _price_list_child_status,
    _price_list_active_run_counts,
    _price_list_auth_state,
    _price_list_login_button_state,
    _price_list_login_counts,
    _price_list_live_result_counts,
    _price_list_live_progress_total,
    _price_list_live_eta,
    _price_list_login_badge_html,
    _price_list_manager_mode_state,
    _price_list_supervisor_badge_html,
    _price_list_supervisor_state,
    _build_o_restock_progress_df,
    _apply_restock_approval_preview_context,
    _apply_restock_po_preview_context,
    _apply_supplier_file_card_context,
    _confirmed_price_safety,
    _o_progress_next_step,
    _price_proof_chips_html,
    _price_list_recovery_counts,
    _profit_check_badge_html,
    _read_price_list_next_action_report,
    _read_price_list_queue_df,
    _read_scanner_timeout_policy_df,
    _restock_card_control_key,
    _restock_card_default_draft_qty,
    _restock_card_approval_preview_status_html,
    _restock_card_exact_match_label,
    _restock_card_pack_label,
    _restock_card_safe_save_guidance,
    _restock_card_supplier_file_asof,
    _restock_card_supplier_file_reference,
    _compose_supplier_card_proof_note,
    _apply_restock_card_proof_history_context,
    _build_restock_supplier_readiness_summary,
    _filter_restock_supplier_action_bucket,
    _filter_restock_missing_proof_worklist,
    _restock_card_missing_proof_detail,
    _restock_card_missing_proof_items,
    _restock_missing_proof_worklist_counts,
    _restock_missing_proof_worklist_options,
    _restock_next_proof_hint,
    _restock_next_proof_hint_html,
    _restock_selected_row_proof_checklist_html,
    _restock_selected_row_proof_checklist_items,
    _build_restock_supplier_action_bucket_counts,
    _build_restock_approval_preview_status_counts,
    _filter_restock_real_po_gate_clearance_lane,
    _build_restock_approval_preview_visibility_summary,
    _build_restock_po_preview_status_counts,
    _build_restock_po_preview_visibility_summary,
    _build_restock_real_po_gate_clearance_worklist_summary,
    _build_restock_real_po_supplier_gate_clearance_summary,
    _build_restock_supplier_file_evidence_visibility_summary,
    _build_restock_supplier_file_proof_coverage_summary,
    _build_restock_supplier_proof_action_workbench_summary,
    _build_restock_supplier_proof_field_focus_counts,
    _filter_restock_supplier_proof_queue_focus,
    _filter_restock_supplier_proof_field_focus,
    _build_restock_supplier_proof_work_queue_summary,
    _restock_supplier_proof_field_focus_options,
    _restock_supplier_proof_queue_focus_options,
    _restock_real_po_gate_clearance_lane_counts,
    _restock_real_po_gate_clearance_lane_options,
    _build_restock_real_po_readiness_gate_summary,
    _build_restock_protected_stage_visibility_summary,
    _build_restock_approval_readiness_lane_counts,
    _build_restock_supplier_info_needed_counts,
    _filter_restock_po_preview_status,
    _restock_supplier_action_bucket_options,
    _restock_supplier_action_buckets_html,
    _restock_approval_readiness_lane,
    _restock_approval_readiness_lane_html,
    _restock_approval_readiness_lane_options,
    _restock_approval_preview_visibility_panel_html,
    _restock_approval_preview_status_bucket,
    _restock_approval_preview_status_options,
    _restock_card_po_preview_status_html,
    _restock_po_preview_status_bucket,
    _restock_po_preview_status_options,
    _restock_po_preview_visibility_panel_html,
    _restock_protected_stage_visibility_panel_html,
    _restock_real_po_gate_clearance_worklist_panel_html,
    _restock_real_po_readiness_gate_panel_html,
    _restock_real_po_supplier_gate_clearance_panel_html,
    _restock_supplier_file_evidence_visibility_panel_html,
    _restock_supplier_file_proof_coverage_map_panel_html,
    _restock_supplier_proof_action_workbench_panel_html,
    _restock_supplier_proof_work_queue_panel_html,
    _restock_supplier_info_needed_panel_html,
    _restock_supplier_readiness_summary_html,
    _restock_row_position_marker,
    _sort_restock_rows_for_local_action,
    _review_widget_key,
    _reorder_row_identity,
    _reorder_widget_key,
    _restock_local_actions_header_html,
    _restock_review_focus_strip_html,
    FEEDER_REVIEW_COLUMN_WIDTHS,
    FEEDER_REVIEW_HEADER_LABELS,
    OPERATOR_PAGE_OPTIONS,
    OPERATOR_HIDDEN_PAGE_REDIRECTS,
    TODAY_OPERATOR_F_DATASET_NAMES,
    TODAY_OPERATOR_DATASET_NAMES,
    RESTOCK_SESSION_DATASET_NAMES,
    apply_price_list_handoff_approval,
    apply_price_list_queue_control,
    build_ai_product_check_gate_df,
    build_amazon_listing_draft_display_df,
    build_brand_approval_queue_display_df,
    build_product_listing_profile_review_df,
    build_feeder_review_sent_df,
    build_feeder_review_window_df,
    build_price_list_queue_summary,
    build_po_draft_review_df,
    build_price_list_lookup_results,
    build_test_orders_df,
    build_recommendations_display_df,
    build_reorder_input_df,
    filter_reorder_rows,
    get_submission_targets,
    list_feeder_review_pack_options,
    load_feeder_review_summary,
    load_feeder_review_source_df,
    load_backtest_calibration_df,
    load_feeder_review_events_df,
    load_backtest_policy_live_row,
    load_feeder_review_ui_drafts_df,
    load_operator_datasets,
    save_feeder_review_ui_drafts,
    select_flagged_backtest_calibration_rows,
    clear_feeder_review_ui_drafts,
    submit_feeder_review_batch,
    submit_amazon_listing_profile_batch,
    submit_brand_approval_decision_batch,
    submit_feeder_review_reopen_batch,
    submit_backtest_policy_update_event,
    _render_recommendation_cards,
    _restock_card_html,
    _restock_path_strip_html,
    _restock_supplier_card_html,
    _build_restock_scanner_check_summary,
    _restock_scanner_lane_text,
    _copy_value_html,
    validate_backtest_policy_values,
    reset_scanner_timeout_policy_from_ui,
    request_price_list_login_mode_from_ui,
    save_scanner_timeout_policy_from_ui,
    run_amazon_listing_preview_for_draft,
    submit_amazon_listing_draft_approval,
    submit_reorder_batch,
    submit_decision_event,
    submit_receiving_event,
    _restock_card_next_action,
    submit_restock_session_draft_decision,
    submit_restock_session_pack_moq_proof_event,
    submit_restock_session_supplier_proof_event,
    submit_purchase_approval_decision_event,
    submit_po_draft_export_gate_event,
    submit_send_handoff_event,
)
from scripts.flows.F.price_list_manager._schemas import (
    BATCH_ROW_COLUMNS,
    PRICE_LIST_BATCH_COLUMNS,
    REVIEW_HANDOFF_MANIFEST_COLUMNS,
    SUPPLIER_REGISTRY_COLUMNS,
)
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.O._schemas import get_o_output_contract
from scripts.core.storage import write_review_pack_snapshots_sql_compat


def _write_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_o_output_contract(contract_name)
    path = tmp_path / contract.rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [*contract.required_columns, *contract.optional_columns]
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({col: str(row.get(col, "") or "") for col in cols})
    pd.DataFrame(normalized, columns=cols).to_csv(path, index=False)


def _write_f_contract_rows(tmp_path: Path, contract_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_f_output_contract(contract_name)
    path = tmp_path / contract.rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [*contract.required_columns, *contract.optional_columns]
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({col: str(row.get(col, "") or "") for col in cols})
    pd.DataFrame(normalized, columns=cols).to_csv(path, index=False)


def test_operator_nav_keeps_ai_gate_out_of_daily_navigation() -> None:
    labels = [label for label, _ in OPERATOR_PAGE_OPTIONS]
    routes = {route: label for label, route in OPERATOR_PAGE_OPTIONS}

    assert "Restock Session" in labels
    assert routes["restock_session"] == "Restock Session"
    assert "New Product Review" in labels
    assert "AI Gate QA" not in labels
    assert "AI Product Check Gate" not in labels
    assert "ai_product_check_gate" not in routes
    assert OPERATOR_HIDDEN_PAGE_REDIRECTS["ai_product_check_gate"] == "new_product_review"


def test_operator_dataset_loader_uses_small_restock_page_bundle() -> None:
    names, f_names = _operator_dataset_names_for_route("restock_session")

    assert names == RESTOCK_SESSION_DATASET_NAMES
    assert f_names == ()
    assert "restock_session_review_live" in names
    assert "supplier_price_list_change_log_live" not in names
    assert "product_db_operator_view" not in names


def test_operator_dataset_loader_uses_small_today_page_bundle() -> None:
    names, f_names = _operator_dataset_names_for_route("today")

    assert names == TODAY_OPERATOR_DATASET_NAMES
    assert f_names == TODAY_OPERATOR_F_DATASET_NAMES
    assert "restock_session_review_live" in names
    assert "product_db_operator_view" in names
    assert "amazon_listing_drafts_live" in f_names
    assert "brand_approval_queue_live" in f_names
    assert "supplier_price_list_change_log_live" not in names


def test_operator_dataset_loader_skips_bundle_for_self_loading_pages() -> None:
    names, f_names = _operator_dataset_names_for_route("new_product_review")

    assert names == ()
    assert f_names == ()


def test_o_restock_progress_df_shows_next_missing_stage() -> None:
    datasets = {
        "restock_session_review_live": pd.DataFrame(
            [{"row_status": "blocked", "seller_sku": "SKU1"}]
        ),
        "restock_session_health": pd.DataFrame([{"status": "ok"}]),
        "restock_session_supplier_batch_lines_live": pd.DataFrame(),
        "restock_session_supplier_batch_health": pd.DataFrame([{"status": "ok"}]),
    }

    progress_df = _build_o_restock_progress_df(datasets)
    session_row = progress_df[progress_df["Stage"] == "Session view"].iloc[0]
    batch_row = progress_df[progress_df["Stage"] == "Supplier batch drafts"].iloc[0]

    assert session_row["Rows"] == "1"
    assert session_row["Blocked"] == "1"
    assert session_row["State"] == "blocked rows visible"
    assert batch_row["Rows"] == "0"
    assert batch_row["State"] == "waiting for rows"
    assert _o_progress_next_step(progress_df) == "Save a local draft quantity for a chosen row."


def test_o_restock_progress_df_marks_export_preview_ready_without_live_action() -> None:
    datasets = {
        "restock_po_draft_export_preview_lines_live": pd.DataFrame(
            [
                {
                    "export_preview_line_state": "ready_for_local_po_draft_export_preview_only",
                    "po_file_write_allowed": "0",
                    "po_creation_allowed": "0",
                    "purchase_commitment_allowed": "0",
                    "receiving_allowed": "0",
                    "send_to_amazon_allowed": "0",
                    "creates_live_action": "0",
                }
            ]
        ),
        "restock_po_draft_export_preview_health": pd.DataFrame([{"status": "ok"}]),
    }

    progress_df = _build_o_restock_progress_df(datasets)
    export_row = progress_df[progress_df["Stage"] == "PO export preview"].iloc[0]

    assert export_row["Rows"] == "1"
    assert export_row["Ready"] == "1"
    assert export_row["State"] == "local rows ready"


def test_restock_card_shows_supplier_file_probe_result_on_normal_card() -> None:
    review_df = pd.DataFrame(
        [
            {
                "row_id": "row-1",
                "supplier_name": "ABGee",
                "seller_sku": "12-749B-9EB5",
                "asin": "B084HZRR8G",
                "title": "Leatherface",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_cost_proof_state": "bridge_cost_only",
                "fee_proof_state": "fee_proof_missing",
                "refund_proof_state": "missing_refund_confidence",
                "inbound_cost_proof_state": "missing_inbound_cost_confidence",
                "pack_moq_proof_state": "pack_moq_not_verified",
                "action_block_reason": "supplier:missing_from_latest_supplier_file",
            }
        ]
    )
    probe_df = pd.DataFrame(
        [
            {
                "probe_utc": "2026-06-03T19:20:00Z",
                "row_id": "row-1",
                "seller_sku": "12-749B-9EB5",
                "identity_match_state": "not_found_in_latest_local_supplier_file",
                "latest_supplier_file_name": "ABGee_Stock_Feed_20260602T103226Z_f11a7d69a5.xlsx",
                "latest_supplier_file_mtime_utc": "2026-06-02T10:32:26Z",
                "searched_row_count": "8793",
                "source_index_handoff_state": "f_status_failed_local_file_available",
            }
        ]
    )

    enriched = _apply_supplier_file_card_context(review_df, probe_df)
    html = _restock_card_html(enriched.iloc[0])

    assert enriched.iloc[0]["supplier_file_card_state"] == "not_found_in_latest_local_supplier_file"
    assert "Supplier file: Not found in latest supplier file" in html
    assert "exact supplier SKU/barcode not found" in html
    assert "ABGee_Stock_Feed_20260602T103226Z_f11a7d69a5.xlsx" in html
    assert "8793 rows searched" in html
    assert "F stale/failed but local file available" in html
    assert "Safest next action:" in html
    assert "Investigate supplier. If this is discontinued, draft Drop; if it may return, draft Snooze." in html


def test_restock_card_next_action_respects_existing_draft_decisions() -> None:
    assert _restock_card_next_action({"latest_draft_decision_code": "drop"}).startswith("Already drafted to drop.")

    snooze_text = _restock_card_next_action(
        {
            "latest_draft_decision_code": "snooze",
            "latest_draft_snooze_until_utc": "2026-06-10T00:00:00Z",
        }
    )
    assert "Already drafted to snooze until 2026-06-10T00:00:00Z." in snooze_text

    draft_qty_text = _restock_card_next_action({"latest_draft_decision_code": "order_qty_draft"})
    assert draft_qty_text == "Draft quantity saved. Wait for supplier, pack, cost, and profit proof before any approval step."


def test_restock_card_next_action_guides_supplier_file_misses() -> None:
    action = _restock_card_next_action(
        {
            "supplier_file_card_state": "not_found_in_latest_local_supplier_file",
            "action_block_reason": "supplier:missing_from_latest_supplier_file",
        }
    )

    assert action == "Investigate supplier. If this is discontinued, draft Drop; if it may return, draft Snooze."


def test_restock_card_safe_save_guidance_respects_existing_drafts() -> None:
    assert "already locally marked Drop" in _restock_card_safe_save_guidance({"latest_draft_decision_code": "drop"})
    assert "already locally set to Check later" in _restock_card_safe_save_guidance({"latest_draft_decision_code": "snooze"})
    assert "quantity is already drafted locally" in _restock_card_safe_save_guidance(
        {"latest_draft_decision_code": "order_qty_draft"}
    )


def test_restock_card_safe_save_guidance_points_to_supplier_proof_first() -> None:
    guidance = _restock_card_safe_save_guidance(
        {
            "row_status": "blocked",
            "supplier_proof_missing_reasons": "supplier_stock_not_verified|backorder_not_verified",
            "supplier_stock_state": "supplier_stock_not_verified",
            "backorder_state": "backorder_not_verified",
        }
    )

    assert guidance.startswith("Safe local save: use Save supplier proof")
    assert "This does not approve buying." in guidance


def test_restock_card_safe_save_guidance_points_to_pack_proof_when_pack_is_missing() -> None:
    guidance = _restock_card_safe_save_guidance(
        {
            "row_status": "blocked",
            "action_block_reason": "pack_moq:pack_moq_not_verified",
            "supplier_stock_state": "supplier_stock_verified_in_stock",
            "backorder_state": "backorder_none_confirmed",
            "supplier_cost_proof_state": "supplier_cost_verified",
            "pack_moq_proof_state": "pack_moq_not_verified",
        }
    )

    assert guidance.startswith("Safe local save: use Save pack/MOQ proof")
    assert "pack size, MOQ, and order step" in guidance


def test_restock_card_safe_save_guidance_handles_discontinued_and_non_card_blockers() -> None:
    discontinued = _restock_card_safe_save_guidance(
        {
            "supplier_file_card_state": "not_found_in_latest_local_supplier_file",
            "action_block_reason": "supplier:missing_from_latest_supplier_file",
        }
    )
    non_card = _restock_card_safe_save_guidance(
        {
            "row_status": "blocked",
            "action_block_reason": "refund:missing_refund_confidence|inbound_cost:missing_inbound_cost_confidence",
            "refund_proof_state": "missing_refund_confidence",
            "inbound_cost_proof_state": "missing_inbound_cost_confidence",
        }
    )

    assert "Mark drop" in discontinued
    assert "Check later" in discontinued
    assert "Do not Save local qty" in discontinued
    assert non_card.startswith("Safe local save: use Check later or leave the row on hold.")
    assert "not cleared by card controls" in non_card


def test_restock_card_safe_save_guidance_points_to_local_qty_for_review_ready_rows() -> None:
    guidance = _restock_card_safe_save_guidance(
        {
            "row_status": "ready",
            "old_suggested_qty": "4",
            "action_block_reason": "",
            "supplier_stock_state": "supplier_stock_verified_in_stock",
            "supplier_cost_proof_state": "supplier_cost_verified",
            "market_price_proof_state": "market_price_verified",
            "fee_proof_state": "fee_proof_verified",
            "refund_proof_state": "refund_proof_verified",
            "inbound_cost_proof_state": "inbound_cost_proof_verified",
            "pack_moq_proof_state": "pack_moq_verified",
        }
    )
    html = _restock_card_html(
        {
            "row_id": "ready-row",
            "seller_sku": "SKU-READY",
            "supplier_name": "Supplier",
            "title": "Ready Product",
            "row_status": "ready",
            "old_suggested_qty": "4",
            "supplier_stock_state": "supplier_stock_verified_in_stock",
            "supplier_cost_proof_state": "supplier_cost_verified",
            "market_price_proof_state": "market_price_verified",
            "fee_proof_state": "fee_proof_verified",
            "refund_proof_state": "refund_proof_verified",
            "inbound_cost_proof_state": "inbound_cost_proof_verified",
            "pack_moq_proof_state": "pack_moq_verified",
        }
    )

    assert guidance.startswith("Safe local save: use Save local qty")
    assert "still not a purchase order" in guidance
    assert "Safe local save:" in html
    assert "Save local qty" in html


def test_operator_metric_card_shows_zero_counts() -> None:
    html = _operator_metric_card_html("Ready candidates", 0, "Still needs Luke's choice", "warn")

    assert "<div class='o-metric-value'>0</div>" in html


def test_operator_task_brief_reads_like_plain_workflow() -> None:
    html = _operator_task_brief_html(
        kicker="Today",
        title="Start with Supplier Intake",
        body="2 scanner-found products need Luke's confirmation.",
        steps=[
            ("Check scanner finds", "Confirm supplier products first."),
            ("Return to Restocking", "Open one supplier group."),
        ],
        safe_note="Read-only starting point.",
        tone="warn",
    )

    assert "o-task-brief warn" in html
    assert "Start with Supplier Intake" in html
    assert "Check scanner finds" in html
    assert "Return to Restocking" in html
    assert "Read-only starting point." in html


def test_operator_work_card_is_compact_plain_html() -> None:
    html = _operator_work_card_html("Supplier Intake", 2, "2 clean passes waiting.", "warn")

    assert "o-work-card warn" in html
    assert "Supplier Intake" in html
    assert "<div class='o-work-value'>2</div>" in html
    assert "2 clean passes waiting." in html


def test_operator_local_form_panel_keeps_save_action_plain() -> None:
    html = _operator_local_form_panel_html(
        title="Save a local receipt record",
        body="This records local proof only and does not send anything to Amazon.",
    )

    assert "o-intake-submit-panel" in html
    assert "Save a local receipt record" in html
    assert "records local proof only" in html
    assert "does not send anything to Amazon" in html


def test_operator_theme_has_mobile_cross_page_polish() -> None:
    css = _render_operator_theme_css()

    assert "@media (max-width: 640px)" in css
    assert ".o-task-safe" in css
    assert ".o-work-grid" in css
    assert ".o-intake-focus-strip" in css
    assert ".o-restock-filter-strip" in css
    assert ".o-po-line-grid" in css
    assert 'div[data-testid="stHorizontalBlock"]' in css
    assert "overflow-x: auto" in css


def test_po_draft_line_uses_responsive_card_classes() -> None:
    html = _render_po_draft_line_html(
        pd.Series(
            {
                "title": "Example order line",
                "seller_sku": "SKU-1",
                "asin": "B000000001",
                "ordered_qty": "12",
                "ordered_unit_cost_gbp": "2.50",
                "line_value_gbp": "30.00",
                "source_label": "Native O",
            }
        )
    )

    assert "o-po-line-card" in html
    assert "o-po-line-grid" in html
    assert "o-po-line-label" in html
    assert "Example order line" in html
    assert "SKU-1" in html


def test_restock_path_strip_is_single_guided_panel() -> None:
    html = _restock_path_strip_html(
        [
            ("Choose a supplier", "Start with one supplier group."),
            ("Review product cards", "See cost, stock, profit, and blockers."),
        ]
    )

    assert "Today's restock path" in html
    assert "o-restock-path-strip" in html
    assert "Choose a supplier" in html
    assert "Review product cards" in html


def test_restock_supplier_card_reads_like_supplier_job() -> None:
    html = _restock_supplier_card_html(
        {
            "supplier": "ABGee",
            "review_products": "9",
            "clean_buy_products": "0",
            "blocked_products": "9",
            "draft_qty_products": "1",
            "main_blocker": "Supplier cost missing",
        }
    )

    assert "ABGee" in html
    assert "Needs proof before buying" in html
    assert "<strong>9</strong>" in html
    assert "0 ready candidates" in html
    assert "1 draft qty saved" in html
    assert "<strong>Main blocker:</strong> Supplier cost missing" in html


def test_restock_card_local_control_keys_are_stable() -> None:
    key = _restock_card_control_key(
        {
            "row_id": "o_restock_session_v1:native_o:ABGee:12-749B-9EB5",
            "seller_sku": "12-749B-9EB5",
        },
        "save qty",
    )

    assert key == "o_restock_card_o_restock_session_v1_native_o_abgee_12_749b_9eb5_save_qty"


def test_restock_card_default_draft_qty_prefers_existing_then_suggested() -> None:
    assert _restock_card_default_draft_qty({"order_qty_draft": "4", "old_suggested_qty": "2"}) == 4
    assert _restock_card_default_draft_qty({"order_qty_draft": "", "old_suggested_qty": "2"}) == 2
    assert _restock_card_default_draft_qty({"order_qty_draft": "", "old_suggested_qty": ""}) == 1


def test_restock_card_supplier_proof_defaults_use_read_only_evidence() -> None:
    row = {
        "supplier_file_card_state": "not_found_in_latest_local_supplier_file",
        "supplier_file_card_file_name": "ABGee_Stock_Feed_20260602T103226Z_f11a7d69a5.xlsx",
        "supplier_file_card_file_mtime_utc": "2026-06-02T10:32:26Z",
        "pack_moq_proof_state": "pack_or_moq_visible",
    }

    assert _restock_card_exact_match_label(row) == "Not found in latest supplier file"
    assert _restock_card_supplier_file_reference(row) == "ABGee_Stock_Feed_20260602T103226Z_f11a7d69a5.xlsx"
    assert _restock_card_supplier_file_asof(row) == "2026-06-02T10:32:26Z"
    assert _restock_card_pack_label(row) == "Verified"


def test_supplier_card_proof_note_keeps_exact_match_and_cost_as_notes() -> None:
    note = _compose_supplier_card_proof_note(
        exact_match_label="Exact SKU/barcode visible",
        cost_note="cost GBP 3.20 visible",
        proof_note="checked current supplier file",
    )

    assert note == "Exact match: Exact SKU/barcode visible | Cost note: cost GBP 3.20 visible | checked current supplier file"


def test_restock_card_shows_no_local_proof_history_when_none_saved() -> None:
    html = _restock_card_html(
        {
            "row_id": "row-1",
            "seller_sku": "SKU-1",
            "asin": "ASIN-1",
            "supplier_name": "Supplier",
            "title": "Product",
        }
    )

    assert "Latest local proof:" in html
    assert "Supplier proof: No local supplier proof saved yet." in html
    assert "Pack/MOQ proof: No local pack/MOQ proof saved yet." in html
    assert "<details class='o-restock-detail-drawer'>" in html
    assert "<summary>Proof details</summary>" in html


def test_restock_card_missing_proof_items_use_existing_blockers() -> None:
    items = _restock_card_missing_proof_items(
        {
            "row_id": "row-1",
            "seller_sku": "SKU-1",
            "row_status": "blocked",
            "supplier_proof_missing_reasons": (
                "exact_supplier_match_not_proved|supplier_cost_not_proved|"
                "supplier_stock_not_verified|backorder_not_verified|supplier_file_asof_missing"
            ),
            "supplier_batch_readiness_reasons": (
                "line_state:review_only_blocked|action_safety:blocked_from_clean_buy|"
                "supplier_proof:exact_supplier_match_not_proved"
            ),
            "action_block_reason": (
                "supplier_cost:bridge_cost_only|market_price:bridge_market_only|"
                "refund:missing_refund_confidence|inbound_cost:missing_inbound_cost_confidence"
            ),
            "supplier_match_state": "missing_from_latest_supplier_file",
            "supplier_stock_state": "supplier_stock_not_verified",
            "backorder_state": "backorder_not_verified",
            "supplier_cost_proof_state": "bridge_cost_only",
            "market_price_proof_state": "bridge_market_only",
            "refund_proof_state": "missing_refund_confidence",
            "inbound_cost_proof_state": "missing_inbound_cost_confidence",
            "pack_moq_proof_state": "pack_or_moq_visible",
        },
        limit=20,
    )

    assert "Exact supplier match not proved" in items
    assert "Supplier cost not proved" in items
    assert "Supplier stock not checked" in items
    assert "Backorder not checked" in items
    assert "Supplier file date missing" in items
    assert "Older supplier cost proof only" in items
    assert "Older Amazon price proof only" in items
    assert "Refund proof missing" in items
    assert "Inbound/FBA cost proof missing" in items
    assert "Pack/MOQ visible" not in items
    assert "Action Safety: Blocked from clean buy" not in items


def test_restock_card_missing_proof_detail_has_clean_fallback_for_ready_rows() -> None:
    detail = _restock_card_missing_proof_detail(
        {
            "row_id": "row-1",
            "seller_sku": "SKU-1",
            "row_status": "ready",
            "action_block_reason": "",
            "supplier_stock_state": "supplier_stock_verified_in_stock",
            "supplier_cost_proof_state": "supplier_cost_verified",
            "market_price_proof_state": "market_price_verified",
            "fee_proof_state": "fee_proof_verified",
            "refund_proof_state": "refund_proof_verified",
            "inbound_cost_proof_state": "inbound_cost_proof_verified",
            "pack_moq_proof_state": "pack_moq_verified",
        }
    )

    assert detail == "No missing local proof shown for this card."


def test_restock_inbound_cost_proof_summary_keeps_unlinked_costs_warning_only() -> None:
    proof_df = pd.DataFrame(
        [
            {
                "check_name": "inbound_cost_events",
                "status": "warn",
                "source_rows": "32",
                "linked_rows": "0",
                "proof_message": "Inbound/FBA cost rows exist but do not carry a shipment link.",
            },
            {
                "check_name": "sku_cost_allocation",
                "status": "warn",
                "linked_rows": "0",
            },
            {
                "check_name": "restock_source_attachment",
                "status": "warn",
                "restock_rows_with_sku_cost": "0",
                "restock_rows_missing_sku_cost": "608",
                "proof_message": "O restock rows still need SKU-level inbound/FBA cost proof before profit is clean.",
            },
        ]
    )

    summary = _restock_inbound_cost_proof_summary(proof_df)

    assert summary["status"] == "warn"
    assert summary["event_rows"] == "32"
    assert summary["event_linked_rows"] == "0"
    assert summary["sku_cost_rows"] == "0"
    assert summary["restock_missing_rows"] == "608"


def test_profit_input_blocker_summary_reports_lanes_from_health() -> None:
    blocker_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-1",
                "primary_blocker": "inbound_fba_cost_missing",
                "safe_for_clean_buy": "0",
                "safe_for_po": "0",
            },
            {
                "seller_sku": "SKU-2",
                "primary_blocker": "inbound_fba_cost_missing",
                "safe_for_clean_buy": "0",
                "safe_for_po": "0",
            },
        ]
    )
    health_df = pd.DataFrame(
        [
            {
                "check": "profit_input_blocker_rows",
                "status": "warn",
                "value": "minimum_input_rows=8;weak_rows=2",
            },
            {
                "check": "weak_input_lanes",
                "status": "warn",
                "value": "refund=0;inbound=2;profit=2",
            },
        ]
    )

    summary = _profit_input_blocker_summary(blocker_df, health_df)

    assert summary["status"] == "warn"
    assert summary["minimum_rows"] == "8"
    assert summary["weak_rows"] == "2"
    assert summary["refund"] == "0"
    assert summary["inbound"] == "2"
    assert summary["profit"] == "2"


def test_inbound_fba_source_options_summary_reports_direct_and_protected_routes() -> None:
    options_df = pd.DataFrame(
        [
            {"route_id": "direct_fee_event_shipment_link"},
            {"route_id": "inbound_fee_average_policy"},
        ]
    )
    health_df = pd.DataFrame(
        [
            {
                "check": "direct_safe_routes",
                "status": "warn",
                "value": "direct_safe_routes=0;protected_routes=2",
            }
        ]
    )

    summary = _inbound_fba_source_options_summary(options_df, health_df)

    assert summary["status"] == "warn"
    assert summary["route_rows"] == "2"
    assert summary["direct_safe"] == "0"
    assert summary["protected"] == "2"


def test_token_cost_trust_label_uses_plain_english() -> None:
    assert _token_cost_trust_label("trusted") == "Token cost trusted"
    assert _token_cost_trust_label("weak_fallback_cost") == "Fallback token cost risk"
    assert _token_cost_trust_label("not_verified") == "Token cost not proved"


def test_restock_card_html_renders_missing_proof_checklist() -> None:
    html = _restock_card_html(
        {
            "row_id": "row-1",
            "seller_sku": "SKU-1",
            "asin": "ASIN-1",
            "supplier_name": "Supplier",
            "title": "Product",
            "row_status": "blocked",
            "supplier_proof_missing_reasons": "supplier_stock_not_verified|supplier_file_asof_missing",
            "action_block_reason": "supplier_cost:bridge_cost_only|refund:missing_refund_confidence",
            "supplier_stock_state": "supplier_stock_not_verified",
            "supplier_cost_proof_state": "bridge_cost_only",
            "refund_proof_state": "missing_refund_confidence",
        }
    )

    assert "Still blocking approval readiness:" in html
    assert "<li>Supplier stock not checked</li>" in html
    assert "<li>Supplier file date missing</li>" in html
    assert "<li>Older supplier cost proof only</li>" in html
    assert "<li>Refund proof missing</li>" in html
    assert html.index("Safest next action:") < html.index("<summary>Proof details</summary>")


def test_restock_card_moves_proof_chips_inside_proof_details_drawer() -> None:
    html = _restock_card_html(
        {
            "row_id": "row-1",
            "seller_sku": "SKU-1",
            "supplier_name": "Supplier",
            "title": "Product",
            "supplier_stock_state": "supplier_stock_not_verified",
            "supplier_cost_proof_state": "bridge_cost_only",
        }
    )

    drawer_start = html.index("<details class='o-restock-detail-drawer'>")
    assert html.index("Supplier stock: Supplier stock not checked") > drawer_start
    assert html.index("Supplier cost: Older supplier cost proof only") > drawer_start


def test_restock_supplier_readiness_summary_separates_local_and_protected_counts() -> None:
    df = pd.DataFrame(
        [
            {
                "row_id": "ready-row",
                "seller_sku": "SKU-READY",
                "supplier_name": "CLF",
                "suggested_action": "full_restock",
                "old_suggested_qty": "4",
                "order_qty_draft": "",
                "latest_draft_decision_code": "",
                "row_status": "ready",
                "action_block_reason": "",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "refund_proof_verified",
                "inbound_cost_proof_state": "inbound_cost_proof_verified",
                "pack_moq_proof_state": "pack_moq_verified",
            },
            {
                "row_id": "proof-missing-row",
                "seller_sku": "SKU-MISSING",
                "supplier_name": "CLF",
                "suggested_action": "full_restock",
                "old_suggested_qty": "3",
                "order_qty_draft": "",
                "latest_draft_decision_code": "",
                "row_status": "blocked",
                "action_block_reason": "supplier_cost:bridge_cost_only|refund:missing_refund_confidence",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_cost_proof_state": "bridge_cost_only",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "missing_refund_confidence",
                "inbound_cost_proof_state": "inbound_cost_proof_verified",
                "pack_moq_proof_state": "pack_moq_verified",
            },
            {
                "row_id": "draft-row",
                "seller_sku": "SKU-DRAFT",
                "supplier_name": "CLF",
                "suggested_action": "",
                "old_suggested_qty": "",
                "order_qty_draft": "2",
                "latest_draft_decision_code": "order_qty_draft",
                "row_status": "blocked",
                "action_block_reason": "inbound_cost:missing_inbound_cost_confidence",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "refund_proof_verified",
                "inbound_cost_proof_state": "missing_inbound_cost_confidence",
                "pack_moq_proof_state": "pack_moq_verified",
            },
        ]
    )

    summary = _build_restock_supplier_readiness_summary(df)
    html = _restock_supplier_readiness_summary_html(df, supplier_label="CLF")

    assert summary["products"] == 3
    assert summary["local_draft_candidates"] == 3
    assert summary["local_qty_drafts"] == 1
    assert summary["ready_candidates"] == 1
    assert summary["missing_proof_rows"] == 2
    assert summary["protected_action_blocked_rows"] == 2
    assert "Selected supplier readiness: CLF" in html
    assert "Local draft candidates" in html
    assert "Missing proof rows" in html
    assert "Protected-action blocked" in html
    assert "Protected-action blocked means O must not approve, buy, receive, or send these rows to Amazon" in html
    assert "What this supplier needs" in html


def test_restock_supplier_action_buckets_count_safe_local_actions() -> None:
    df = pd.DataFrame(
        [
            {
                "row_id": "supplier-proof-row",
                "seller_sku": "SKU-SUPPLIER",
                "row_status": "blocked",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "supplier_stock_state": "supplier_stock_not_verified",
            },
            {
                "row_id": "pack-row",
                "seller_sku": "SKU-PACK",
                "row_status": "blocked",
                "action_block_reason": "pack_moq:pack_moq_not_verified",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "pack_moq_proof_state": "pack_moq_not_verified",
            },
            {
                "row_id": "qty-row",
                "seller_sku": "SKU-QTY",
                "row_status": "ready",
                "old_suggested_qty": "4",
                "action_block_reason": "",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "refund_proof_verified",
                "inbound_cost_proof_state": "inbound_cost_proof_verified",
                "pack_moq_proof_state": "pack_moq_verified",
            },
            {
                "row_id": "check-later-row",
                "seller_sku": "SKU-HOLD",
                "row_status": "blocked",
                "action_block_reason": "refund:missing_refund_confidence",
                "refund_proof_state": "missing_refund_confidence",
            },
            {
                "row_id": "drop-row",
                "seller_sku": "SKU-DROP",
                "row_status": "blocked",
                "supplier_file_card_state": "not_found_in_latest_local_supplier_file",
                "action_block_reason": "supplier:missing_from_latest_supplier_file",
            },
        ]
    )

    counts = _build_restock_supplier_action_bucket_counts(df)
    html = _restock_supplier_action_buckets_html(df)

    assert counts["Supplier proof"] == 1
    assert counts["Pack/MOQ proof"] == 1
    assert counts["Local qty"] == 1
    assert counts["Check later"] == 1
    assert counts["Mark drop"] == 1
    assert "What this supplier needs" in html
    assert "Use Save supplier proof" in html
    assert "Use Save pack/MOQ proof" in html
    assert "Use Save local qty" in html
    assert "Use Check later or hold" in html
    assert "Use Mark drop" in html
    assert "Action buckets are local guidance only" in html


def test_restock_supplier_info_needed_panel_counts_supplier_evidence_gaps() -> None:
    df = pd.DataFrame(
        [
            {
                "row_id": "stock-row",
                "seller_sku": "SKU-STOCK",
                "row_status": "blocked",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified|backorder_not_verified",
                "supplier_stock_state": "supplier_stock_not_verified",
                "backorder_state": "backorder_not_verified",
            },
            {
                "row_id": "cost-row",
                "seller_sku": "SKU-COST",
                "row_status": "blocked",
                "supplier_proof_missing_reasons": "supplier_cost_not_exact",
                "supplier_cost_proof_state": "supplier_cost_not_exact",
            },
            {
                "row_id": "pack-row",
                "seller_sku": "SKU-PACK",
                "row_status": "blocked",
                "action_block_reason": "pack_moq:pack_moq_not_verified",
                "pack_moq_proof_state": "pack_moq_not_verified",
            },
            {
                "row_id": "missing-row",
                "seller_sku": "SKU-MISSING",
                "row_status": "blocked",
                "supplier_file_card_state": "not_found_in_latest_local_supplier_file",
                "action_block_reason": "supplier:missing_from_latest_supplier_file",
            },
            {
                "row_id": "market-row",
                "seller_sku": "SKU-MARKET",
                "row_status": "blocked",
                "action_block_reason": "price:missing_current_market_price",
                "market_price_proof_state": "missing_current_market_price",
            },
        ]
    )

    counts = _build_restock_supplier_info_needed_counts(df)
    html = _restock_supplier_info_needed_panel_html(df)
    readiness_html = _restock_supplier_readiness_summary_html(df, supplier_label="CLF")

    assert counts["identity_stock"]["count"] == 1
    assert counts["cost"]["count"] == 1
    assert counts["pack_moq"]["count"] == 1
    assert counts["missing_supplier_file"]["count"] == 1
    assert counts["non_supplier_proof"]["count"] == 1
    assert "Supplier info still needed" in html
    assert "Identity/stock" in html
    assert "Current cost" in html
    assert "Pack/MOQ" in html
    assert "Missing/discontinued" in html
    assert "Other proof" in html
    assert "does not run scans, write supplier files, or buy stock" in html
    assert "Supplier info still needed" in readiness_html


def test_restock_approval_readiness_lane_counts_preview_stages() -> None:
    df = pd.DataFrame(
        [
            {
                "row_id": "preview-ready-row",
                "seller_sku": "SKU-PREVIEW",
                "row_status": "ready",
                "action_block_reason": "",
                "order_qty_draft": "3",
                "supplier_batch_readiness_state": "ready_for_purchase_approval_review_only",
            },
            {
                "row_id": "qty-row",
                "seller_sku": "SKU-QTY",
                "row_status": "ready",
                "action_block_reason": "",
                "old_suggested_qty": "5",
            },
            {
                "row_id": "supplier-row",
                "seller_sku": "SKU-SUPPLIER",
                "row_status": "blocked",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "supplier_stock_state": "supplier_stock_not_verified",
            },
            {
                "row_id": "pack-row",
                "seller_sku": "SKU-PACK",
                "row_status": "blocked",
                "action_block_reason": "pack_moq:pack_moq_not_verified",
                "pack_moq_proof_state": "pack_moq_not_verified",
            },
            {
                "row_id": "profit-row",
                "seller_sku": "SKU-PROFIT",
                "row_status": "blocked",
                "action_block_reason": "price:missing_current_market_price",
                "market_price_proof_state": "missing_current_market_price",
            },
            {
                "row_id": "hold-row",
                "seller_sku": "SKU-HOLD",
                "row_status": "waiting",
                "old_suggested_qty": "0",
            },
        ]
    )

    counts = _build_restock_approval_readiness_lane_counts(df)
    html = _restock_approval_readiness_lane_html(df)
    readiness_html = _restock_supplier_readiness_summary_html(df, supplier_label="CLF")

    assert _restock_approval_readiness_lane(df.iloc[0]) == "Ready for approval preview"
    assert counts["Ready for approval preview"]["count"] == 1
    assert counts["Needs local qty"]["count"] == 1
    assert counts["Needs supplier proof"]["count"] == 1
    assert counts["Needs pack/MOQ proof"]["count"] == 1
    assert counts["Needs profit/safety proof"]["count"] == 1
    assert counts["Hold or drop only"]["count"] == 1
    assert "Approval preview readiness" in html
    assert "review-only preview shape; still not an order" in html
    assert "does not approve buying, create purchase orders, receive stock, or send anything to Amazon" in html
    assert "Approval preview readiness" in readiness_html


def test_restock_approval_readiness_filter_options_and_rows_match_lanes() -> None:
    df = pd.DataFrame(
        [
            {
                "row_id": "preview-ready-row",
                "seller_sku": "SKU-PREVIEW",
                "row_status": "ready",
                "action_block_reason": "",
                "order_qty_draft": "3",
                "supplier_batch_readiness_state": "ready_for_purchase_approval_review_only",
            },
            {
                "row_id": "qty-row",
                "seller_sku": "SKU-QTY",
                "row_status": "ready",
                "action_block_reason": "",
                "old_suggested_qty": "5",
            },
            {
                "row_id": "supplier-row",
                "seller_sku": "SKU-SUPPLIER",
                "row_status": "blocked",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "supplier_stock_state": "supplier_stock_not_verified",
            },
            {
                "row_id": "profit-row",
                "seller_sku": "SKU-PROFIT",
                "row_status": "blocked",
                "action_block_reason": "price:missing_current_market_price",
                "market_price_proof_state": "missing_current_market_price",
            },
        ]
    )

    options = _restock_approval_readiness_lane_options(df)
    preview_rows = _filter_restock_approval_readiness_lane(df, "Ready for approval preview")
    qty_rows = _filter_restock_approval_readiness_lane(df, "Needs local qty")
    supplier_rows = _filter_restock_approval_readiness_lane(df, "Needs supplier proof")
    profit_rows = _filter_restock_approval_readiness_lane(df, "Needs profit/safety proof")
    all_rows = _filter_restock_approval_readiness_lane(df, "All approval lanes")

    assert options == [
        "All approval lanes",
        "Ready for approval preview",
        "Needs local qty",
        "Needs supplier proof",
        "Needs profit/safety proof",
    ]
    assert preview_rows["seller_sku"].tolist() == ["SKU-PREVIEW"]
    assert qty_rows["seller_sku"].tolist() == ["SKU-QTY"]
    assert supplier_rows["seller_sku"].tolist() == ["SKU-SUPPLIER"]
    assert profit_rows["seller_sku"].tolist() == ["SKU-PROFIT"]
    assert all_rows["seller_sku"].tolist() == ["SKU-PREVIEW", "SKU-QTY", "SKU-SUPPLIER", "SKU-PROFIT"]


def test_restock_approval_preview_visibility_matches_existing_packet_status() -> None:
    review_df = pd.DataFrame(
        [
            {
                "row_id": "row-1",
                "seller_sku": "SKU-PREVIEW",
                "asin": "ASIN-PREVIEW",
                "title": "Preview Product",
                "row_status": "ready",
                "action_block_reason": "",
                "order_qty_draft": "2",
            },
            {
                "row_id": "row-2",
                "seller_sku": "SKU-NOT-PREVIEW",
                "asin": "ASIN-NOT",
                "title": "Not Preview Product",
                "row_status": "blocked",
                "action_block_reason": "supplier:missing_supplier_cost",
            },
        ]
    )
    approval_lines_df = pd.DataFrame(
        [
            {
                "preview_utc": "2026-06-03T08:30:00Z",
                "approval_packet_id": "packet-1",
                "row_id": "row-1",
                "seller_sku": "SKU-PREVIEW",
                "asin": "ASIN-PREVIEW",
                "draft_order_qty": "2",
                "draft_line_value_gbp": "6",
                "approval_preview_state": "ready_for_purchase_approval_review_only",
                "approval_block_reasons": "",
                "creates_live_action": "0",
            }
        ]
    )
    approval_summary_df = pd.DataFrame(
        [
            {
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "draft_order_value_gbp": "6",
                "approval_packet_state": "ready_for_purchase_approval_review_only",
                "creates_live_action": "0",
            }
        ]
    )

    enriched_df = _apply_restock_approval_preview_context(review_df, approval_lines_df)
    summary = _build_restock_approval_preview_visibility_summary(enriched_df, approval_summary_df)
    panel_html = _restock_approval_preview_visibility_panel_html(enriched_df, approval_summary_df)
    preview_card_html = _restock_card_approval_preview_status_html(enriched_df.iloc[0])
    no_preview_card_html = _restock_card_approval_preview_status_html(enriched_df.iloc[1])
    full_card_html = _restock_card_html(enriched_df.iloc[0])

    assert enriched_df.iloc[0]["approval_preview_card_packet_id"] == "packet-1"
    assert enriched_df.iloc[1]["approval_preview_card_packet_id"] == ""
    assert summary["preview_rows"] == 1
    assert summary["ready_preview_rows"] == 1
    assert summary["blocked_preview_rows"] == 0
    assert summary["packet_count"] == 1
    assert summary["draft_order_value_gbp"] == "6"
    assert "Existing approval preview packet status" in panel_html
    assert "Approval preview status is read-only" in panel_html
    assert "does not approve buying, create purchase orders, write PO files, receive stock, or send anything to Amazon" in panel_html
    assert "packet packet-1" in preview_card_html
    assert "Review-only, not a purchase order" in preview_card_html
    assert "Not in a local approval preview packet yet" in no_preview_card_html
    assert "o-restock-approval-preview-status" in full_card_html


def test_restock_approval_preview_status_filter_matches_card_status() -> None:
    df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-READY",
                "approval_preview_card_packet_id": "packet-ready",
                "approval_preview_card_state": "ready_for_purchase_approval_review_only",
                "approval_preview_card_block_reasons": "",
                "approval_preview_card_creates_live_action": "0",
            },
            {
                "seller_sku": "SKU-BLOCKED",
                "approval_preview_card_packet_id": "packet-blocked",
                "approval_preview_card_state": "blocked_from_purchase_approval",
                "approval_preview_card_block_reasons": "supplier:missing_supplier_cost",
                "approval_preview_card_creates_live_action": "0",
            },
            {
                "seller_sku": "SKU-NOT-PREVIEW",
                "approval_preview_card_packet_id": "",
                "approval_preview_card_state": "",
                "approval_preview_card_block_reasons": "",
                "approval_preview_card_creates_live_action": "",
            },
        ]
    )

    counts = _build_restock_approval_preview_status_counts(df)
    options = _restock_approval_preview_status_options(df)
    ready_rows = _filter_restock_approval_preview_status(df, "Ready preview line")
    blocked_rows = _filter_restock_approval_preview_status(df, "Blocked preview line")
    not_preview_rows = _filter_restock_approval_preview_status(df, "Not in approval preview")
    all_rows = _filter_restock_approval_preview_status(df, "All preview statuses")

    assert _restock_approval_preview_status_bucket(df.iloc[0]) == "Ready preview line"
    assert _restock_approval_preview_status_bucket(df.iloc[1]) == "Blocked preview line"
    assert _restock_approval_preview_status_bucket(df.iloc[2]) == "Not in approval preview"
    assert counts == {
        "Ready preview line": 1,
        "Blocked preview line": 1,
        "Not in approval preview": 1,
    }
    assert options == [
        "All preview statuses",
        "Ready preview line",
        "Blocked preview line",
        "Not in approval preview",
    ]
    assert ready_rows["seller_sku"].tolist() == ["SKU-READY"]
    assert blocked_rows["seller_sku"].tolist() == ["SKU-BLOCKED"]
    assert not_preview_rows["seller_sku"].tolist() == ["SKU-NOT-PREVIEW"]
    assert all_rows["seller_sku"].tolist() == ["SKU-READY", "SKU-BLOCKED", "SKU-NOT-PREVIEW"]


def test_restock_po_preview_visibility_matches_existing_preview_chain() -> None:
    review_df = pd.DataFrame(
        [
            {
                "row_id": "row-export",
                "seller_sku": "SKU-EXPORT",
                "asin": "ASIN-EXPORT",
                "title": "Export Preview Product",
                "supplier_name": "Supplier",
                "row_status": "ready",
                "action_block_reason": "",
            },
            {
                "row_id": "row-hold",
                "seller_sku": "SKU-HOLD",
                "asin": "ASIN-HOLD",
                "title": "Held Preview Product",
                "supplier_name": "Supplier",
                "row_status": "blocked",
                "action_block_reason": "po:held_for_local_review",
            },
            {
                "row_id": "row-unsafe",
                "seller_sku": "SKU-UNSAFE",
                "asin": "ASIN-UNSAFE",
                "title": "Unsafe Flag Product",
                "supplier_name": "Supplier",
                "row_status": "blocked",
                "action_block_reason": "po:unsafe_flag",
            },
            {
                "row_id": "row-not-preview",
                "seller_sku": "SKU-NOT-PO",
                "asin": "ASIN-NOT-PO",
                "title": "Not In Preview Product",
                "supplier_name": "Supplier",
                "row_status": "blocked",
                "action_block_reason": "supplier:missing_supplier_cost",
            },
        ]
    )
    po_hold_lines_df = pd.DataFrame(
        [
            {
                "hold_utc": "2026-06-03T09:00:00Z",
                "po_draft_hold_review_id": "hold-1",
                "row_id": "row-hold",
                "seller_sku": "SKU-HOLD",
                "asin": "ASIN-HOLD",
                "hold_order_qty": "2",
                "hold_line_value_gbp": "12",
                "hold_review_line_state": "held_for_local_po_draft_review_only",
                "hold_review_reasons": "local_po_review_hold",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ]
    )
    po_file_shape_lines_df = pd.DataFrame(
        [
            {
                "shape_utc": "2026-06-03T09:05:00Z",
                "po_draft_file_shape_preview_id": "shape-unsafe",
                "row_id": "row-unsafe",
                "seller_sku": "SKU-UNSAFE",
                "asin": "ASIN-UNSAFE",
                "file_shape_qty": "1",
                "file_shape_line_value_gbp": "7",
                "file_shape_line_state": "ready_for_local_po_draft_file_shape_review_only",
                "file_shape_block_reasons": "",
                "po_file_write_allowed": "1",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ]
    )
    po_export_preview_lines_df = pd.DataFrame(
        [
            {
                "export_preview_utc": "2026-06-03T09:10:00Z",
                "po_draft_export_preview_id": "export-1",
                "row_id": "row-export",
                "seller_sku": "SKU-EXPORT",
                "asin": "ASIN-EXPORT",
                "export_preview_qty": "3",
                "export_preview_line_value_gbp": "GBP 21",
                "export_preview_line_state": "ready_for_local_po_draft_export_preview_only",
                "export_preview_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ]
    )
    po_construction_summary_df = pd.DataFrame(
        [
            {
                "summary_utc": "2026-06-03T09:15:00Z",
                "stage_key": "po_export_preview",
                "stage_label": "PO export preview",
                "stage_state": "preview_only_no_po_created",
                "creates_live_action": "0",
            }
        ]
    )

    enriched_df = _apply_restock_po_preview_context(
        review_df,
        po_hold_review_lines_df=po_hold_lines_df,
        po_file_shape_lines_df=po_file_shape_lines_df,
        po_export_preview_lines_df=po_export_preview_lines_df,
    )
    summary = _build_restock_po_preview_visibility_summary(enriched_df, po_construction_summary_df)
    counts = _build_restock_po_preview_status_counts(enriched_df)
    options = _restock_po_preview_status_options(enriched_df)
    panel_html = _restock_po_preview_visibility_panel_html(enriched_df, po_construction_summary_df)
    export_card_html = _restock_card_po_preview_status_html(enriched_df.iloc[0])
    no_preview_card_html = _restock_card_po_preview_status_html(enriched_df.iloc[3])
    full_card_html = _restock_card_html(enriched_df.iloc[0])
    ready_rows = _filter_restock_po_preview_status(enriched_df, "Ready PO preview line")
    held_rows = _filter_restock_po_preview_status(enriched_df, "Held PO preview line")
    unsafe_rows = _filter_restock_po_preview_status(enriched_df, "Unsafe PO preview flag")
    not_preview_rows = _filter_restock_po_preview_status(enriched_df, "Not in PO preview")

    assert enriched_df.iloc[0]["po_preview_card_stage_key"] == "po_export_preview"
    assert enriched_df.iloc[0]["po_preview_card_packet_id"] == "export-1"
    assert enriched_df.iloc[1]["po_preview_card_stage_key"] == "po_hold_review"
    assert enriched_df.iloc[2]["po_preview_card_unsafe_flags"] == "po_file_write_allowed"
    assert enriched_df.iloc[3]["po_preview_card_stage_key"] == ""
    assert _restock_po_preview_status_bucket(enriched_df.iloc[0]) == "Ready PO preview line"
    assert _restock_po_preview_status_bucket(enriched_df.iloc[1]) == "Held PO preview line"
    assert _restock_po_preview_status_bucket(enriched_df.iloc[2]) == "Unsafe PO preview flag"
    assert _restock_po_preview_status_bucket(enriched_df.iloc[3]) == "Not in PO preview"
    assert counts == {
        "Ready PO preview line": 1,
        "Held PO preview line": 1,
        "Blocked PO preview line": 0,
        "Unsafe PO preview flag": 1,
        "Not in PO preview": 1,
    }
    assert options == [
        "All PO preview statuses",
        "Ready PO preview line",
        "Held PO preview line",
        "Unsafe PO preview flag",
        "Not in PO preview",
    ]
    assert summary["preview_rows"] == 3
    assert summary["unsafe_rows"] == 1
    assert summary["stage_counts"]["po_hold_review"] == 1
    assert summary["stage_counts"]["po_file_shape"] == 1
    assert summary["stage_counts"]["po_export_preview"] == 1
    assert summary["furthest_stage_label"] == "PO export preview"
    assert "Existing PO preview construction status" in panel_html
    assert "PO preview status is read-only" in panel_html
    assert "does not create PO files, create purchase orders, commit buying, receive stock, or send anything to Amazon" in panel_html
    assert "packet export-1" in export_card_html
    assert "value GBP 21" in export_card_html
    assert "Local preview only, no PO file" in export_card_html
    assert "Not in the local PO-preview construction chain yet" in no_preview_card_html
    assert "o-restock-po-preview-status" in full_card_html
    assert ready_rows["seller_sku"].tolist() == ["SKU-EXPORT"]
    assert held_rows["seller_sku"].tolist() == ["SKU-HOLD"]
    assert unsafe_rows["seller_sku"].tolist() == ["SKU-UNSAFE"]
    assert not_preview_rows["seller_sku"].tolist() == ["SKU-NOT-PO"]


def test_restock_protected_stage_visibility_shows_local_only_status() -> None:
    approval_guardrails_df = pd.DataFrame(
        [
            {
                "approval_guardrail_state": "blocked_preview_not_ready",
                "creates_live_action": "0",
            }
        ]
    )
    po_review_controls_df = pd.DataFrame(
        [
            {
                "review_control_state": "blocked_file_shape_not_ready",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ]
    )
    po_export_gate_df = pd.DataFrame(
        [
            {
                "export_gate_state": "blocked_export_preview_not_ready",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ]
    )
    purchase_orders_df = pd.DataFrame(
        [
            {"po_id": "legacy-po-1", "po_status": "legacy"},
            {"po_id": "legacy-po-2", "po_status": "legacy"},
        ]
    )
    purchase_order_lines_df = pd.DataFrame(
        [
            {"po_line_id": "line-1", "receipt_status": "not_received"},
            {"po_line_id": "line-2", "receipt_status": "not_received"},
            {"po_line_id": "line-3", "receipt_status": "not_received"},
        ]
    )
    receiving_events_df = pd.DataFrame([{"event_id": "recv-1"}])
    receiving_event_holds_df = pd.DataFrame([{"event_id": "hold-1"}, {"event_id": "hold-2"}])
    send_to_amazon_queue_df = pd.DataFrame(columns=["send_status", "creates_live_action"])
    send_to_amazon_handoff_log_df = pd.DataFrame(columns=["handoff_status", "creates_live_action"])

    summary = _build_restock_protected_stage_visibility_summary(
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
        purchase_orders_df=purchase_orders_df,
        purchase_order_lines_df=purchase_order_lines_df,
        receiving_events_df=receiving_events_df,
        receiving_event_holds_df=receiving_event_holds_df,
        send_to_amazon_queue_df=send_to_amazon_queue_df,
        send_to_amazon_handoff_log_df=send_to_amazon_handoff_log_df,
    )
    panel_html = _restock_protected_stage_visibility_panel_html(
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
        purchase_orders_df=purchase_orders_df,
        purchase_order_lines_df=purchase_order_lines_df,
        receiving_events_df=receiving_events_df,
        receiving_event_holds_df=receiving_event_holds_df,
        send_to_amazon_queue_df=send_to_amazon_queue_df,
        send_to_amazon_handoff_log_df=send_to_amazon_handoff_log_df,
    )

    assert summary["approval_guardrail_rows"] == 1
    assert summary["approval_guardrail_state"] == "Blocked preview not ready"
    assert summary["po_review_control_state"] == "Blocked file shape not ready"
    assert summary["po_export_gate_state"] == "Blocked export preview not ready"
    assert summary["purchase_order_rows"] == 2
    assert summary["purchase_order_line_rows"] == 3
    assert summary["receiving_event_rows"] == 1
    assert summary["receiving_hold_rows"] == 2
    assert summary["send_queue_rows"] == 0
    assert summary["send_handoff_rows"] == 0
    assert summary["unsafe_flags"] == 0
    assert "Protected stages still local-only" in panel_html
    assert "No protected action enabled" in panel_html
    assert "Existing rows are proof/history until native O completion is proven" in panel_html
    assert "This panel is read-only" in panel_html
    assert "does not approve buying, create purchase orders, write PO files, receive stock, or send anything to Amazon" in panel_html


def test_restock_real_po_readiness_gate_stays_closed_until_proof_is_ready() -> None:
    review_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-BLOCKED",
                "row_status": "blocked",
                "action_block_reason": "supplier:missing_supplier_cost",
            }
        ]
    )
    approval_guardrails_df = pd.DataFrame(
        [{"approval_guardrail_state": "blocked_preview_not_ready", "creates_live_action": "0"}]
    )
    po_review_controls_df = pd.DataFrame(
        [
            {
                "review_control_state": "blocked_file_shape_not_ready",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ]
    )
    po_export_gate_df = pd.DataFrame(
        [
            {
                "export_gate_state": "blocked_export_preview_not_ready",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ]
    )

    summary = _build_restock_real_po_readiness_gate_summary(
        review_df,
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
    )
    panel_html = _restock_real_po_readiness_gate_panel_html(
        review_df,
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
    )

    assert summary["gate_state"] == "closed"
    assert summary["ready_rows"] == 0
    assert summary["unsafe_flags"] == 0
    assert summary["reasons"] == [
        "no clean buy-ready rows in this view",
        "approval guardrail is not accepted",
        "PO review control is not ready",
        "PO export gate is not ready",
    ]
    assert "Real PO readiness gate" in panel_html
    assert "Closed" in panel_html
    assert "A closed gate is healthy while O is mid-build" in panel_html
    assert "does not approve buying, create purchase orders, write PO files, receive stock, or send anything to Amazon" in panel_html


def test_restock_real_po_gate_clearance_worklist_counts_blocker_lanes() -> None:
    review_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-ALL",
                "row_status": "blocked",
                "action_block_reason": "supplier_cost:missing_supplier_cost|refund:missing_refund_confidence|inbound_cost:missing_inbound_cost_confidence|order:proof_missing|supplier:likely_discontinued_candidate",
                "missing_input_reasons": "missing_supplier_cost|missing_market_price|missing_forward_roi|missing_forward_profit|missing_net_fee_model",
                "profit_check_message": "Profit check: Needs price check before this is a clean buy.",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "market_price_proof_state": "missing_current_market_price",
                "fee_proof_state": "fee_proof_missing",
                "refund_proof_state": "missing_refund_confidence",
                "inbound_cost_proof_state": "missing_inbound_cost_confidence",
                "order_qty_draft": "",
                "supplier_order_viability_state": "unknown_no_order_qty",
            }
        ]
    )
    approval_guardrails_df = pd.DataFrame(
        [{"approval_guardrail_state": "blocked_preview_not_ready", "creates_live_action": "0"}]
    )
    po_review_controls_df = pd.DataFrame(
        [{"review_control_state": "blocked_file_shape_not_ready", "creates_live_action": "0"}]
    )
    po_export_gate_df = pd.DataFrame(
        [{"export_gate_state": "blocked_export_preview_not_ready", "creates_live_action": "0"}]
    )

    summary = _build_restock_real_po_gate_clearance_worklist_summary(
        review_df,
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
    )
    panel_html = _restock_real_po_gate_clearance_worklist_panel_html(
        review_df,
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
    )

    counts = summary["counts"]
    assert counts["Supplier stock proof"]["count"] == 1
    assert counts["Supplier cost proof"]["count"] == 1
    assert counts["Market and profit proof"]["count"] == 1
    assert counts["Refund and inbound proof"]["count"] == 1
    assert counts["Local order quantity proof"]["count"] == 1
    assert counts["Approval and PO gates"]["count"] == 1
    assert summary["top_lane"] == "Approval and PO gates"
    assert "Real PO gate clearance worklist" in panel_html
    assert "Supplier stock proof" in panel_html
    assert "Refund and inbound proof" in panel_html
    assert "This is a read-only worklist" in panel_html
    assert "does not approve buying, write PO files, create purchase orders, receive stock, or send anything to Amazon" in panel_html


def test_restock_real_po_gate_clearance_filter_matches_lane_rows() -> None:
    review_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-STOCK",
                "row_status": "blocked",
                "action_block_reason": "supplier:likely_discontinued_candidate",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "current_supplier_cost_gbp": "2.00",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "refund_proof_verified",
                "inbound_cost_proof_state": "inbound_cost_proof_verified",
                "order_qty_draft": "2",
                "supplier_order_viability_state": "review_only_not_po",
            },
            {
                "seller_sku": "SKU-COST",
                "row_status": "blocked",
                "action_block_reason": "supplier_cost:missing_supplier_cost",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_match_state": "supplier_match_verified",
                "backorder_state": "backorder_not_needed",
                "supplier_file_asof_utc": "2026-06-03T10:00:00Z",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "refund_proof_verified",
                "inbound_cost_proof_state": "inbound_cost_proof_verified",
                "order_qty_draft": "2",
                "supplier_order_viability_state": "review_only_not_po",
            },
            {
                "seller_sku": "SKU-REFUND",
                "row_status": "blocked",
                "action_block_reason": "refund:missing_refund_confidence|inbound_cost:missing_inbound_cost_confidence",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_match_state": "supplier_match_verified",
                "backorder_state": "backorder_not_needed",
                "supplier_file_asof_utc": "2026-06-03T10:00:00Z",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "current_supplier_cost_gbp": "2.00",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "missing_refund_confidence",
                "inbound_cost_proof_state": "missing_inbound_cost_confidence",
                "order_qty_draft": "2",
                "supplier_order_viability_state": "review_only_not_po",
            },
        ]
    )
    approval_guardrails_df = pd.DataFrame(
        [{"approval_guardrail_state": "blocked_preview_not_ready", "creates_live_action": "0"}]
    )
    po_review_controls_df = pd.DataFrame(
        [{"review_control_state": "blocked_file_shape_not_ready", "creates_live_action": "0"}]
    )
    po_export_gate_df = pd.DataFrame(
        [{"export_gate_state": "blocked_export_preview_not_ready", "creates_live_action": "0"}]
    )

    counts = _restock_real_po_gate_clearance_lane_counts(
        review_df,
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
    )
    options = _restock_real_po_gate_clearance_lane_options(
        review_df,
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
    )
    stock_rows = _filter_restock_real_po_gate_clearance_lane(review_df, "Supplier stock proof")
    cost_rows = _filter_restock_real_po_gate_clearance_lane(review_df, "Supplier cost proof")
    refund_rows = _filter_restock_real_po_gate_clearance_lane(review_df, "Refund and inbound proof")
    gate_rows = _filter_restock_real_po_gate_clearance_lane(
        review_df,
        "Approval and PO gates",
        approval_guardrails_df=approval_guardrails_df,
        po_review_controls_df=po_review_controls_df,
        po_export_gate_df=po_export_gate_df,
    )
    all_rows = _filter_restock_real_po_gate_clearance_lane(review_df, "All gate clearance lanes")

    assert counts["Supplier stock proof"] == 1
    assert counts["Supplier cost proof"] == 1
    assert counts["Refund and inbound proof"] == 1
    assert counts["Approval and PO gates"] == 3
    assert options[0] == "All gate clearance lanes"
    assert "Approval and PO gates" in options
    assert stock_rows["seller_sku"].tolist() == ["SKU-STOCK"]
    assert cost_rows["seller_sku"].tolist() == ["SKU-COST"]
    assert refund_rows["seller_sku"].tolist() == ["SKU-REFUND"]
    assert gate_rows["seller_sku"].tolist() == ["SKU-STOCK", "SKU-COST", "SKU-REFUND"]
    assert all_rows["seller_sku"].tolist() == ["SKU-STOCK", "SKU-COST", "SKU-REFUND"]


def test_restock_real_po_supplier_gate_clearance_panel_counts_supplier_lanes() -> None:
    review_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-BOTH",
                "action_block_reason": "supplier:missing_supplier_match|supplier_cost:missing_supplier_cost",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
            },
            {
                "seller_sku": "SKU-STOCK",
                "action_block_reason": "supplier:likely_discontinued_candidate",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "current_supplier_cost_gbp": "2.00",
            },
            {
                "seller_sku": "SKU-COST",
                "action_block_reason": "supplier_cost:missing_supplier_cost",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_match_state": "supplier_match_verified",
                "backorder_state": "backorder_not_needed",
                "supplier_file_asof_utc": "2026-06-03T10:00:00Z",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
            },
            {
                "seller_sku": "SKU-CLEAR",
                "action_block_reason": "refund:missing_refund_confidence",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_match_state": "supplier_match_verified",
                "backorder_state": "backorder_not_needed",
                "supplier_file_asof_utc": "2026-06-03T10:00:00Z",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "current_supplier_cost_gbp": "2.00",
            },
        ]
    )

    summary = _build_restock_real_po_supplier_gate_clearance_summary(review_df)
    panel_html = _restock_real_po_supplier_gate_clearance_panel_html(review_df)

    assert summary["visible_rows"] == 4
    assert summary["stock_rows"] == 2
    assert summary["cost_rows"] == 2
    assert summary["both_rows"] == 1
    assert summary["stock_only_rows"] == 1
    assert summary["cost_only_rows"] == 1
    assert summary["supplier_lanes_clear_rows"] == 1
    assert "Supplier gate clearance" in panel_html
    assert "Stock proof lane" in panel_html
    assert "Cost proof lane" in panel_html
    assert "Both supplier lanes" in panel_html
    assert "SKU-BOTH" in panel_html
    assert "This is a read-only supplier gate view" in panel_html
    assert "does not fetch supplier files, change supplier files, approve buying, create purchase orders, receive stock, or send anything to Amazon" in panel_html


def test_restock_supplier_file_evidence_visibility_panel_matches_visible_rows() -> None:
    review_df = pd.DataFrame(
        [
            {"row_id": "row-found", "seller_sku": "SKU-FOUND"},
            {"row_id": "row-missing", "seller_sku": "SKU-MISSING"},
            {"row_id": "row-unprobed", "seller_sku": "SKU-UNPROBED"},
        ]
    )
    probe_df = pd.DataFrame(
        [
            {
                "row_id": "row-found",
                "seller_sku": "SKU-FOUND",
                "latest_supplier_file_name": "supplier_file.xlsx",
                "latest_supplier_file_state": "latest_local_supplier_file_checked",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
                "read_error": "",
            },
            {
                "row_id": "row-missing",
                "seller_sku": "SKU-MISSING",
                "latest_supplier_file_name": "supplier_file.xlsx",
                "latest_supplier_file_state": "latest_local_supplier_file_checked",
                "identity_match_state": "not_found_in_latest_local_supplier_file",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
                "read_error": "",
            },
            {
                "row_id": "other-row",
                "seller_sku": "OTHER-SKU",
                "latest_supplier_file_name": "other.xlsx",
                "latest_supplier_file_state": "latest_local_supplier_file_checked",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "clears_supplier_proof": "1",
                "purchase_approval_allowed": "1",
                "po_creation_allowed": "1",
                "purchase_commitment_allowed": "1",
                "creates_live_action": "1",
                "read_error": "",
            },
        ]
    )

    summary = _build_restock_supplier_file_evidence_visibility_summary(review_df, probe_df)
    panel_html = _restock_supplier_file_evidence_visibility_panel_html(review_df, probe_df)

    assert summary["visible_rows"] == 3
    assert summary["probe_rows"] == 2
    assert summary["file_checked_rows"] == 2
    assert summary["exact_match_rows"] == 1
    assert summary["not_found_rows"] == 1
    assert summary["unsafe_rows"] == 0
    assert summary["file_examples"] == ["supplier_file.xlsx"]
    assert "Supplier file evidence" in panel_html
    assert "Probe rows" in panel_html
    assert "Exact matches found" in panel_html
    assert "This panel is read-only" in panel_html
    assert "does not import supplier files, change F status, clear supplier proof, approve buying, create purchase orders, receive stock, or send anything to Amazon" in panel_html


def test_restock_supplier_file_evidence_visibility_counts_unsafe_probe_flags() -> None:
    review_df = pd.DataFrame([{"row_id": "row-unsafe", "seller_sku": "SKU-UNSAFE"}])
    probe_df = pd.DataFrame(
        [
            {
                "row_id": "row-unsafe",
                "seller_sku": "SKU-UNSAFE",
                "latest_supplier_file_name": "supplier_file.xlsx",
                "latest_supplier_file_state": "latest_local_supplier_file_checked",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "clears_supplier_proof": "1",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
                "read_error": "",
            }
        ]
    )

    summary = _build_restock_supplier_file_evidence_visibility_summary(review_df, probe_df)
    panel_html = _restock_supplier_file_evidence_visibility_panel_html(review_df, probe_df)

    assert summary["unsafe_rows"] == 1
    assert "Unsafe flags" in panel_html
    assert "Must stay 0" in panel_html


def test_restock_supplier_file_proof_coverage_map_counts_global_and_current_view() -> None:
    review_df = pd.DataFrame(
        [
            {"row_id": "row-a", "seller_sku": "SKU-A", "supplier_name": "Supplier A", "_supplier_label": "Supplier A"},
            {"row_id": "row-b", "seller_sku": "SKU-B", "supplier_name": "Supplier A", "_supplier_label": "Supplier A"},
            {"row_id": "row-c", "seller_sku": "SKU-C", "supplier_name": "Supplier B", "_supplier_label": "Supplier B"},
        ]
    )
    current_view_df = review_df[review_df["_supplier_label"] == "Supplier A"].copy()
    probe_df = pd.DataFrame(
        [
            {
                "row_id": "row-a",
                "seller_sku": "SKU-A",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            },
            {
                "row_id": "row-c",
                "seller_sku": "SKU-C",
                "identity_match_state": "not_found_in_latest_local_supplier_file",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            },
        ]
    )

    summary = _build_restock_supplier_file_proof_coverage_summary(review_df, probe_df, current_view_df)
    panel_html = _restock_supplier_file_proof_coverage_map_panel_html(review_df, probe_df, current_view_df)

    assert summary["review_rows"] == 3
    assert summary["covered_rows"] == 2
    assert summary["uncovered_rows"] == 1
    assert summary["supplier_count"] == 2
    assert summary["covered_supplier_count"] == 2
    assert summary["uncovered_supplier_count"] == 0
    assert summary["current_view_rows"] == 2
    assert summary["current_view_covered_rows"] == 1
    assert summary["exact_match_probe_rows"] == 1
    assert summary["not_found_probe_rows"] == 1
    assert summary["unsafe_rows"] == 0
    assert summary["uncovered_supplier_examples"] == ["Supplier A (1)"]
    assert "Supplier file proof coverage" in panel_html
    assert "Rows with probe evidence" in panel_html
    assert "Rows without probe evidence" in panel_html
    assert "Current view coverage" in panel_html
    assert "This map is read-only" in panel_html
    assert "does not fetch supplier files, import supplier files, change F status, clear supplier proof, approve buying, create purchase orders, receive stock, or send anything to Amazon" in panel_html


def test_restock_supplier_file_proof_coverage_map_counts_unsafe_probe_flags() -> None:
    review_df = pd.DataFrame(
        [{"row_id": "row-unsafe", "seller_sku": "SKU-UNSAFE", "supplier_name": "Supplier", "_supplier_label": "Supplier"}]
    )
    probe_df = pd.DataFrame(
        [
            {
                "row_id": "row-unsafe",
                "seller_sku": "SKU-UNSAFE",
                "identity_match_state": "exact_supplier_sku_or_barcode_found",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "1",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            }
        ]
    )

    summary = _build_restock_supplier_file_proof_coverage_summary(review_df, probe_df, review_df)
    panel_html = _restock_supplier_file_proof_coverage_map_panel_html(review_df, probe_df, review_df)

    assert summary["covered_rows"] == 1
    assert summary["unsafe_rows"] == 1
    assert "Unsafe flags" in panel_html
    assert "Must stay 0" in panel_html


def test_restock_supplier_proof_work_queue_groups_uncovered_rows_by_supplier_and_action() -> None:
    review_df = pd.DataFrame(
        [
            {
                "row_id": "row-a1",
                "seller_sku": "SKU-A1",
                "supplier_name": "Supplier A",
                "_supplier_label": "Supplier A",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "row_id": "row-a2",
                "seller_sku": "SKU-A2",
                "supplier_name": "Supplier A",
                "_supplier_label": "Supplier A",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "row_id": "row-b1",
                "seller_sku": "SKU-B1",
                "supplier_name": "Supplier B",
                "_supplier_label": "Supplier B",
                "supplier_proof_missing_reasons": "missing_from_latest_supplier_file",
                "action_block_reason": "supplier:likely_discontinued_candidate",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "row_id": "row-covered",
                "seller_sku": "SKU-COVERED",
                "supplier_name": "Supplier C",
                "_supplier_label": "Supplier C",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
        ]
    )
    current_view_df = review_df[review_df["_supplier_label"] == "Supplier A"].copy()
    probe_df = pd.DataFrame([{"row_id": "row-covered", "seller_sku": "SKU-COVERED"}])

    summary = _build_restock_supplier_proof_work_queue_summary(review_df, probe_df, current_view_df)
    panel_html = _restock_supplier_proof_work_queue_panel_html(review_df, probe_df, current_view_df)

    assert summary["uncovered_rows"] == 3
    assert summary["supplier_groups"] == 2
    assert summary["top_supplier"] == "Supplier A"
    assert summary["top_supplier_rows"] == 2
    assert summary["top_supplier_action"] == "Supplier proof"
    assert summary["top_action"] == "Supplier proof"
    assert summary["top_action_rows"] == 2
    assert summary["current_view_uncovered_rows"] == 2
    assert "Supplier proof work queue" in panel_html
    assert "Uncovered proof rows" in panel_html
    assert "Supplier groups to work" in panel_html
    assert "Top supplier group" in panel_html
    assert "Current view uncovered" in panel_html
    assert "This queue is read-only" in panel_html
    assert "does not fetch supplier files, clear supplier proof, save events, approve buying, create purchase orders, receive stock, or send anything to Amazon" in panel_html


def test_restock_supplier_proof_action_workbench_counts_field_lanes() -> None:
    review_df = pd.DataFrame(
        [
            {
                "row_id": "row-a1",
                "seller_sku": "SKU-A1",
                "supplier_name": "Supplier A",
                "_supplier_label": "Supplier A",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified|supplier_cost_not_proved|supplier_file_asof_missing",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
            {
                "row_id": "row-b1",
                "seller_sku": "SKU-B1",
                "supplier_name": "Supplier B",
                "_supplier_label": "Supplier B",
                "supplier_proof_missing_reasons": "missing_from_latest_supplier_file",
                "action_block_reason": "supplier:likely_discontinued_candidate",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
            {
                "row_id": "row-covered",
                "seller_sku": "SKU-COVERED",
                "supplier_name": "Supplier C",
                "_supplier_label": "Supplier C",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
        ]
    )
    probe_df = pd.DataFrame([{"row_id": "row-covered", "seller_sku": "SKU-COVERED"}])

    summary = _build_restock_supplier_proof_action_workbench_summary(review_df, probe_df, review_df)
    panel_html = _restock_supplier_proof_action_workbench_panel_html(review_df, probe_df, review_df)
    field_counts = summary["field_counts"]

    assert summary["selected_queue_rows"] == 2
    assert summary["all_uncovered_rows"] == 2
    assert field_counts["Exact match check"] == 2
    assert field_counts["Stock/backorder check"] == 2
    assert field_counts["Cost check"] == 2
    assert field_counts["File/ref check"] == 2
    assert field_counts["Drop/check-later"] == 1
    assert "Supplier proof action workbench" in panel_html
    assert "Exact match check" in panel_html
    assert "Stock/backorder check" in panel_html
    assert "Cost check" in panel_html
    assert "File/ref check" in panel_html
    assert "Drop/check-later" in panel_html
    assert "This workbench is read-only" in panel_html
    assert "does not fetch supplier files, save proof, clear proof, approve buying, create purchase orders, receive stock, or send anything to Amazon" in panel_html


def test_restock_supplier_proof_field_focus_options_and_filter_match_field_counts() -> None:
    review_df = pd.DataFrame(
        [
            {
                "row_id": "row-a1",
                "seller_sku": "SKU-A1",
                "supplier_name": "Supplier A",
                "_supplier_label": "Supplier A",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified|supplier_cost_not_proved|supplier_file_asof_missing",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
            {
                "row_id": "row-a2",
                "seller_sku": "SKU-A2",
                "supplier_name": "Supplier A",
                "_supplier_label": "Supplier A",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified|supplier_cost_not_proved|supplier_file_asof_missing",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
            {
                "row_id": "row-b1",
                "seller_sku": "SKU-B1",
                "supplier_name": "Supplier B",
                "_supplier_label": "Supplier B",
                "supplier_proof_missing_reasons": "missing_from_latest_supplier_file",
                "action_block_reason": "supplier:likely_discontinued_candidate",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
            {
                "row_id": "row-covered",
                "seller_sku": "SKU-COVERED",
                "supplier_name": "Supplier C",
                "_supplier_label": "Supplier C",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified|supplier_cost_not_proved|supplier_file_asof_missing",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
                "current_supplier_cost_gbp": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
            },
        ]
    )
    probe_df = pd.DataFrame([{"row_id": "row-covered", "seller_sku": "SKU-COVERED"}])

    counts = _build_restock_supplier_proof_field_focus_counts(review_df, probe_df)
    options = _restock_supplier_proof_field_focus_options(review_df, probe_df)
    all_rows = _filter_restock_supplier_proof_field_focus(review_df, probe_df, "All supplier proof fields")
    cost_rows = _filter_restock_supplier_proof_field_focus(review_df, probe_df, "Cost check")
    drop_rows = _filter_restock_supplier_proof_field_focus(review_df, probe_df, "Drop/check-later")

    assert counts["All supplier proof fields"] == 3
    assert counts["Exact match check"] == 3
    assert counts["Stock/backorder check"] == 3
    assert counts["Cost check"] == 3
    assert counts["File/ref check"] == 3
    assert counts["Drop/check-later"] == 1
    assert options == [
        "All supplier proof fields",
        "Exact match check",
        "Stock/backorder check",
        "Cost check",
        "File/ref check",
        "Drop/check-later",
    ]
    assert all_rows["seller_sku"].tolist() == ["SKU-A1", "SKU-A2", "SKU-B1", "SKU-COVERED"]
    assert cost_rows["seller_sku"].tolist() == ["SKU-A1", "SKU-A2", "SKU-B1"]
    assert drop_rows["seller_sku"].tolist() == ["SKU-B1"]


def test_restock_supplier_proof_queue_focus_options_and_filter_match_top_queue() -> None:
    review_df = pd.DataFrame(
        [
            {
                "row_id": "row-a1",
                "seller_sku": "SKU-A1",
                "supplier_name": "Supplier A",
                "_supplier_label": "Supplier A",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "row_id": "row-a2",
                "seller_sku": "SKU-A2",
                "supplier_name": "Supplier A",
                "_supplier_label": "Supplier A",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "row_id": "row-b1",
                "seller_sku": "SKU-B1",
                "supplier_name": "Supplier B",
                "_supplier_label": "Supplier B",
                "supplier_proof_missing_reasons": "missing_from_latest_supplier_file",
                "action_block_reason": "supplier:likely_discontinued_candidate",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
            {
                "row_id": "row-covered",
                "seller_sku": "SKU-COVERED",
                "supplier_name": "Supplier C",
                "_supplier_label": "Supplier C",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "action_block_reason": "supplier:missing_supplier_match",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_match_state": "not_verified",
                "supplier_cost_proof_state": "missing_supplier_cost",
            },
        ]
    )
    probe_df = pd.DataFrame([{"row_id": "row-covered", "seller_sku": "SKU-COVERED"}])

    options = _restock_supplier_proof_queue_focus_options(review_df, probe_df)
    current_rows = _filter_restock_supplier_proof_queue_focus(
        review_df,
        probe_df,
        "Current supplier selection",
        selected_supplier="Supplier B",
    )
    all_uncovered_rows = _filter_restock_supplier_proof_queue_focus(
        review_df,
        probe_df,
        "All uncovered supplier-proof rows",
        selected_supplier="Supplier B",
    )
    top_supplier_rows = _filter_restock_supplier_proof_queue_focus(
        review_df,
        probe_df,
        "Top queue supplier: Supplier A (2)",
        selected_supplier="Supplier B",
    )
    top_action_rows = _filter_restock_supplier_proof_queue_focus(
        review_df,
        probe_df,
        "Top queue action: Supplier proof (2)",
        selected_supplier="Supplier B",
    )
    top_supplier_action_rows = _filter_restock_supplier_proof_queue_focus(
        review_df,
        probe_df,
        "Top supplier plus action: Supplier A / Supplier proof (2)",
        selected_supplier="Supplier B",
    )

    assert options[0] == "Current supplier selection"
    assert "All uncovered supplier-proof rows" in options
    assert "Top queue supplier: Supplier A (2)" in options
    assert "Top queue action: Supplier proof (2)" in options
    assert "Top supplier plus action: Supplier A / Supplier proof (2)" in options
    assert current_rows["seller_sku"].tolist() == ["SKU-B1"]
    assert all_uncovered_rows["seller_sku"].tolist() == ["SKU-A1", "SKU-A2", "SKU-B1"]
    assert top_supplier_rows["seller_sku"].tolist() == ["SKU-A1", "SKU-A2"]
    assert top_action_rows["seller_sku"].tolist() == ["SKU-A1", "SKU-A2"]
    assert top_supplier_action_rows["seller_sku"].tolist() == ["SKU-A1", "SKU-A2"]


def test_restock_supplier_action_bucket_options_and_filter_match_safe_save_buckets() -> None:
    df = pd.DataFrame(
        [
            {
                "row_id": "supplier-proof-row",
                "seller_sku": "SKU-SUPPLIER",
                "row_status": "blocked",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "supplier_stock_state": "supplier_stock_not_verified",
            },
            {
                "row_id": "pack-row",
                "seller_sku": "SKU-PACK",
                "row_status": "blocked",
                "action_block_reason": "pack_moq:pack_moq_not_verified",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "pack_moq_proof_state": "pack_moq_not_verified",
            },
            {
                "row_id": "qty-row",
                "seller_sku": "SKU-QTY",
                "row_status": "ready",
                "old_suggested_qty": "4",
                "action_block_reason": "",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "refund_proof_verified",
                "inbound_cost_proof_state": "inbound_cost_proof_verified",
                "pack_moq_proof_state": "pack_moq_verified",
            },
            {
                "row_id": "drop-row",
                "seller_sku": "SKU-DROP",
                "row_status": "blocked",
                "supplier_file_card_state": "not_found_in_latest_local_supplier_file",
                "action_block_reason": "supplier:missing_from_latest_supplier_file",
            },
        ]
    )

    options = _restock_supplier_action_bucket_options(df)
    supplier_rows = _filter_restock_supplier_action_bucket(df, "Supplier proof")
    pack_rows = _filter_restock_supplier_action_bucket(df, "Pack/MOQ proof")
    qty_rows = _filter_restock_supplier_action_bucket(df, "Local qty")
    drop_rows = _filter_restock_supplier_action_bucket(df, "Mark drop")
    all_rows = _filter_restock_supplier_action_bucket(df, "All local actions")

    assert options == ["All local actions", "Supplier proof", "Pack/MOQ proof", "Local qty", "Mark drop"]
    assert supplier_rows["seller_sku"].tolist() == ["SKU-SUPPLIER"]
    assert pack_rows["seller_sku"].tolist() == ["SKU-PACK"]
    assert qty_rows["seller_sku"].tolist() == ["SKU-QTY"]
    assert drop_rows["seller_sku"].tolist() == ["SKU-DROP"]
    assert all_rows["seller_sku"].tolist() == ["SKU-SUPPLIER", "SKU-PACK", "SKU-QTY", "SKU-DROP"]


def test_restock_row_priority_sorting_orders_buckets_and_ties() -> None:
    df = pd.DataFrame(
        [
            {
                "row_id": "check-later-row",
                "seller_sku": "SKU-HOLD",
                "title": "Hold Row",
                "row_status": "blocked",
                "old_suggested_qty": "99",
                "action_block_reason": "refund:missing_refund_confidence",
                "refund_proof_state": "missing_refund_confidence",
            },
            {
                "row_id": "supplier-low-row",
                "seller_sku": "SKU-SUP-LOW",
                "title": "Supplier Low",
                "row_status": "blocked",
                "old_suggested_qty": "2",
                "expected_profit_per_unit_gbp": "GBP 10",
                "velocity_30d": "1",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "supplier_stock_state": "supplier_stock_not_verified",
            },
            {
                "row_id": "supplier-high-row",
                "seller_sku": "SKU-SUP-HIGH",
                "title": "Supplier High",
                "row_status": "blocked",
                "old_suggested_qty": "7",
                "expected_profit_per_unit_gbp": "GBP 1",
                "velocity_30d": "1",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified",
                "supplier_stock_state": "supplier_stock_not_verified",
            },
            {
                "row_id": "pack-row",
                "seller_sku": "SKU-PACK",
                "title": "Pack Row",
                "row_status": "blocked",
                "old_suggested_qty": "4",
                "action_block_reason": "pack_moq:pack_moq_not_verified",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "pack_moq_proof_state": "pack_moq_not_verified",
            },
            {
                "row_id": "drop-row",
                "seller_sku": "SKU-DROP",
                "title": "Drop Row",
                "row_status": "blocked",
                "old_suggested_qty": "1",
                "supplier_file_card_state": "not_found_in_latest_local_supplier_file",
                "action_block_reason": "supplier:missing_from_latest_supplier_file",
            },
        ]
    )

    sorted_df = _sort_restock_rows_for_local_action(df)

    assert sorted_df["seller_sku"].tolist() == [
        "SKU-SUP-HIGH",
        "SKU-SUP-LOW",
        "SKU-DROP",
        "SKU-PACK",
        "SKU-HOLD",
    ]
    assert set(sorted_df["seller_sku"]) == set(df["seller_sku"])


def test_restock_row_position_marker_explains_visible_order_reason() -> None:
    row = {
        "row_id": "supplier-proof-row",
        "seller_sku": "SKU-SUPPLIER",
        "row_status": "blocked",
        "old_suggested_qty": "7",
        "expected_profit_per_unit_gbp": "GBP 1.23",
        "velocity_30d": "3",
        "supplier_proof_missing_reasons": "supplier_stock_not_verified",
        "supplier_stock_state": "supplier_stock_not_verified",
    }

    marker = _restock_row_position_marker(row, position_index=2, total_visible=5)
    html = _restock_card_html(row, position_index=2, total_visible=5)

    assert "Work position #2 of 5" in marker
    assert "Supplier proof" in marker
    assert "supplier proof rows come first" in marker
    assert "suggested buy 7" in marker
    assert "profit each GBP 1.23" in marker
    assert "recent sales 3" in marker
    assert "o-restock-position-marker" in html
    assert "Why this card is here" in html
    assert "Work position #2 of 5" in html


def test_restock_review_focus_strip_is_plain_current_view_summary() -> None:
    html = _restock_review_focus_strip_html(
        supplier="CLF",
        products=14,
        proof_filter="Backorder not checked",
        blocked=6,
    )

    assert "o-restock-filter-strip" in html
    assert "Supplier" in html
    assert "CLF" in html
    assert "Products shown" in html
    assert "14" in html
    assert "Proof problem" in html
    assert "Backorder not checked" in html
    assert "Blocked from clean buy" in html
    assert "6" in html


def test_restock_local_actions_header_is_explicitly_local_only() -> None:
    html = _restock_local_actions_header_html({"seller_sku": "SKU-1"})

    assert "Local actions for this card" in html
    assert "SKU-1" in html
    assert "do not buy stock" in html
    assert "create purchase orders" in html
    assert "write Sheets" in html
    assert "touch scanner queues" in html


def test_restock_missing_proof_worklist_options_and_filter_match_card_labels() -> None:
    df = pd.DataFrame(
        [
            {
                "row_id": "ready-row",
                "seller_sku": "SKU-READY",
                "suggested_action": "full_restock",
                "old_suggested_qty": "4",
                "row_status": "ready",
                "action_block_reason": "",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "refund_proof_verified",
                "inbound_cost_proof_state": "inbound_cost_proof_verified",
                "pack_moq_proof_state": "pack_moq_verified",
            },
            {
                "row_id": "cost-refund-row",
                "seller_sku": "SKU-REFUND",
                "suggested_action": "full_restock",
                "old_suggested_qty": "3",
                "row_status": "blocked",
                "action_block_reason": "supplier_cost:bridge_cost_only|refund:missing_refund_confidence",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_cost_proof_state": "bridge_cost_only",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "missing_refund_confidence",
                "inbound_cost_proof_state": "inbound_cost_proof_verified",
                "pack_moq_proof_state": "pack_moq_verified",
            },
            {
                "row_id": "inbound-row",
                "seller_sku": "SKU-INBOUND",
                "suggested_action": "full_restock",
                "old_suggested_qty": "2",
                "row_status": "blocked",
                "action_block_reason": "inbound_cost:missing_inbound_cost_confidence",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "market_price_proof_state": "market_price_verified",
                "fee_proof_state": "fee_proof_verified",
                "refund_proof_state": "refund_proof_verified",
                "inbound_cost_proof_state": "missing_inbound_cost_confidence",
                "pack_moq_proof_state": "pack_moq_verified",
            },
        ]
    )

    counts = _restock_missing_proof_worklist_counts(df)
    options = _restock_missing_proof_worklist_options(df)
    refund_rows = _filter_restock_missing_proof_worklist(df, "Refund proof missing")
    inbound_rows = _filter_restock_missing_proof_worklist(df, "Inbound/FBA cost proof missing")
    all_rows = _filter_restock_missing_proof_worklist(df, "All missing proof types")

    assert counts["All missing proof types"] == 3
    assert counts["Older supplier cost proof only"] == 1
    assert counts["Refund proof missing"] == 1
    assert counts["Inbound/FBA cost proof missing"] == 1
    assert options[0] == "All missing proof types"
    assert "Supplier stock not checked" in options
    assert refund_rows["seller_sku"].tolist() == ["SKU-REFUND"]
    assert inbound_rows["seller_sku"].tolist() == ["SKU-INBOUND"]
    assert all_rows["seller_sku"].tolist() == ["SKU-READY", "SKU-REFUND", "SKU-INBOUND"]


def test_restock_missing_proof_cards_understand_e_roi_tokens() -> None:
    row = {
        "seller_sku": "SKU-E-ROI",
        "row_status": "blocked",
        "restock_missing_proof": "missing_roi;velocity_only_sales_truth;bridge_labelled_money",
        "missing_roi_reason": "velocity_only_sales_truth",
        "restock_decision_state": "blocked_missing_roi",
        "restock_business_ready": "no",
    }

    labels = _restock_card_missing_proof_items(row)

    assert "ROI missing" in labels
    assert "Velocity-only sales proof" in labels
    assert "Old B money proof only" in labels
    assert "Blocked: ROI missing" in labels


def test_restock_next_proof_hint_uses_selected_or_top_missing_proof() -> None:
    counts = {
        "All missing proof types": 3,
        "Refund proof missing": 2,
        "Supplier stock not checked": 1,
    }

    top_hint = _restock_next_proof_hint("All missing proof types", counts)
    selected_hint = _restock_next_proof_hint("Supplier stock not checked", counts)
    html = _restock_next_proof_hint_html("Supplier stock not checked", counts)

    assert top_hint.startswith("Next proof to collect: Refund proof missing (2 rows).")
    assert "Check refund-impact proof before approval." in top_hint
    assert selected_hint.startswith("Next proof to collect: Supplier stock not checked (1 row).")
    assert "Confirm current supplier stock" in selected_hint
    assert "Next proof to collect:" in html
    assert "<div class='o-restock-next-proof-hint'>" in html


def test_restock_selected_row_proof_checklist_maps_blockers_to_card_fields() -> None:
    row = {
        "row_id": "row-1",
        "seller_sku": "SKU-1",
        "row_status": "blocked",
        "supplier_proof_missing_reasons": (
            "exact_supplier_match_not_proved|supplier_stock_not_verified|"
            "backorder_not_verified|supplier_file_asof_missing"
        ),
        "action_block_reason": "supplier_cost:bridge_cost_only|pack_moq:pack_moq_not_verified",
        "supplier_stock_state": "supplier_stock_not_verified",
        "backorder_state": "backorder_not_verified",
        "supplier_cost_proof_state": "bridge_cost_only",
        "pack_moq_proof_state": "pack_moq_not_verified",
    }

    items = _restock_selected_row_proof_checklist_items(row, limit=20)
    html = _restock_selected_row_proof_checklist_html(row)

    assert any("Exact supplier match not proved: set Exact match, File/ref, File date" in item for item in items)
    assert any("Supplier stock not checked: set Stock proof, Stock qty" in item for item in items)
    assert any("Backorder not checked: set Backorder, Backorder ETA" in item for item in items)
    assert any("Older supplier cost proof only: fill Cost note" in item for item in items)
    assert any("Pack/MOQ proof missing: set Pack/MOQ, Pack, MOQ, Step" in item for item in items)
    assert "Selected row proof checklist:" in html
    assert "Save supplier proof" in html
    assert "Save pack/MOQ proof" in html


def test_restock_selected_row_proof_checklist_keeps_non_card_proof_blocked() -> None:
    row = {
        "row_id": "row-1",
        "seller_sku": "SKU-1",
        "row_status": "blocked",
        "action_block_reason": (
            "market_price:bridge_market_only|refund:missing_refund_confidence|"
            "inbound_cost:missing_inbound_cost_confidence"
        ),
        "market_price_proof_state": "bridge_market_only",
        "refund_proof_state": "missing_refund_confidence",
        "inbound_cost_proof_state": "missing_inbound_cost_confidence",
    }

    items = _restock_selected_row_proof_checklist_items(row, limit=20)

    assert any("Older Amazon price proof only: not saved from this card." in item for item in items)
    assert any("Refund proof missing: not saved from this card." in item for item in items)
    assert any("Inbound/FBA cost proof missing: not saved from this card." in item for item in items)
    assert not any("Save supplier proof clears" in item for item in items)


def test_restock_card_hides_internal_bridge_and_profit_tokens() -> None:
    html = _restock_card_html(
        {
            "row_id": "row-1",
            "seller_sku": "SKU-1",
            "asin": "ASIN-1",
            "supplier_name": "Supplier",
            "title": "Product",
            "row_status": "blocked",
            "action_block_reason": (
                "legacy_bridge_not_native_supplier_truth|"
                "profit_check:test only - roi 0 percent, gbp 0 profit/unit."
            ),
        }
    )

    assert "Old supplier proof, needs current check" in html
    assert "Test-only profit check, no profit shown" in html
    assert "Legacy bridge not native supplier truth" not in html
    assert "gbp 0 profit/unit" not in html


def test_restock_card_merges_latest_supplier_and_pack_proof_history() -> None:
    review_df = pd.DataFrame(
        [
            {
                "row_id": "row-1",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "supplier_name": "Supplier",
                "title": "Product",
            }
        ]
    )
    supplier_events = pd.DataFrame(
        [
            {
                "event_utc": "2026-06-03T10:00:00Z",
                "proof_id": "old-proof",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "supplier_stock_state": "supplier_stock_not_verified",
                "supplier_stock_qty": "",
                "backorder_state": "backorder_not_verified",
                "backorder_eta_utc": "",
                "supplier_file_asof_utc": "",
                "supplier_file_reference": "",
                "proof_note": "old note",
                "actor": "tester",
                "proof_status": "draft_proof",
                "creates_live_action": "0",
            },
            {
                "event_utc": "2026-06-03T11:00:00Z",
                "proof_id": "new-proof",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_stock_qty": "4",
                "backorder_state": "backorder_none_confirmed",
                "backorder_eta_utc": "",
                "supplier_file_asof_utc": "2026-06-03T09:00:00Z",
                "supplier_file_reference": "supplier-file.csv",
                "proof_note": "Exact match: Exact SKU/barcode visible | Cost note: cost GBP 3.20 visible",
                "actor": "tester",
                "proof_status": "draft_proof",
                "creates_live_action": "0",
            },
        ]
    )
    pack_events = pd.DataFrame(
        [
            {
                "event_utc": "2026-06-03T11:05:00Z",
                "proof_id": "pack-proof",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "pack_moq_proof_state": "pack_moq_verified",
                "pack_multiple": "6",
                "supplier_moq": "12",
                "valid_order_step": "6",
                "proof_file_reference": "pack-file.csv",
                "proof_note": "checked pack",
                "actor": "tester",
                "proof_status": "draft_proof",
                "creates_live_action": "0",
            }
        ]
    )

    enriched = _apply_restock_card_proof_history_context(review_df, supplier_events, pack_events)
    html = _restock_card_html(enriched.iloc[0])

    assert enriched.iloc[0]["supplier_proof_card_id"] == "new-proof"
    assert "Supplier proof: 2026-06-03T11:00:00Z; stock Supplier stock verified in stock, qty 4" in html
    assert "file/ref supplier-file.csv" in html
    assert "Cost note: cost GBP 3.20 visible" in html
    assert "Pack/MOQ proof: 2026-06-03T11:05:00Z; Pack moq verified; pack 6; MOQ 12; step 6" in html
    assert "file/ref pack-file.csv" in html


def test_load_operator_datasets_includes_restock_session_draft_events(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_session_draft_decision_events",
        [
            {
                "event_utc": "2026-06-02T20:00:00Z",
                "draft_id": "draft-1",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:native_o:supplier:sku",
                "seller_sku": "SKU-DRAFT",
                "asin": "ASIN-DRAFT",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "row_source_reference": "native_o:SKU-DRAFT",
                "decision_code": "drop",
                "draft_order_qty": "",
                "snooze_until_utc": "",
                "decision_note": "drop for now",
                "actor": "operator_ui",
                "event_source_reference": "test",
                "draft_status": "draft",
                "creates_live_action": "0",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)

    assert "restock_session_draft_decision_events" in datasets
    assert datasets["restock_session_draft_decision_events"].iloc[0]["creates_live_action"] == "0"


def test_load_operator_datasets_includes_restock_session_supplier_proof_events(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_session_supplier_proof_events",
        [
            {
                "event_utc": "2026-06-02T20:30:00Z",
                "proof_id": "proof-1",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:native_o:supplier:sku",
                "seller_sku": "SKU-PROOF",
                "asin": "ASIN-PROOF",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "row_source_reference": "native_o:SKU-PROOF",
                "supplier_stock_state": "supplier_stock_verified_in_stock",
                "supplier_stock_qty": "4",
                "backorder_state": "backorder_none_confirmed",
                "backorder_eta_utc": "",
                "supplier_file_asof_utc": "2026-06-02T00:00:00Z",
                "supplier_file_reference": "supplier-file.csv",
                "proof_note": "checked supplier file",
                "actor": "operator_ui",
                "event_source_reference": "test",
                "proof_status": "draft_proof",
                "creates_live_action": "0",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)

    assert "restock_session_supplier_proof_events" in datasets
    assert datasets["restock_session_supplier_proof_events"].iloc[0]["proof_status"] == "draft_proof"
    assert datasets["restock_session_supplier_proof_events"].iloc[0]["creates_live_action"] == "0"


def test_load_operator_datasets_includes_restock_session_pack_moq_proof_events(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_session_pack_moq_proof_events",
        [
            {
                "event_utc": "2026-06-02T20:40:00Z",
                "proof_id": "pack-proof-1",
                "session_id": "o_restock_session_v1",
                "row_id": "o_restock_session_v1:native_o:supplier:sku",
                "seller_sku": "SKU-PACK",
                "asin": "ASIN-PACK",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "row_source_reference": "native_o:SKU-PACK",
                "pack_moq_proof_state": "pack_moq_verified",
                "pack_multiple": "6",
                "supplier_moq": "12",
                "valid_order_step": "6",
                "proof_file_reference": "pack-file.csv",
                "proof_note": "checked pack",
                "actor": "operator_ui",
                "event_source_reference": "test",
                "proof_status": "draft_proof",
                "creates_live_action": "0",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)

    assert "restock_session_pack_moq_proof_events" in datasets
    assert datasets["restock_session_pack_moq_proof_events"].iloc[0]["pack_moq_proof_state"] == "pack_moq_verified"
    assert datasets["restock_session_pack_moq_proof_events"].iloc[0]["creates_live_action"] == "0"


def test_load_operator_datasets_includes_supplier_batch_draft_outputs(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_session_supplier_batch_lines_live",
        [
            {
                "batch_utc": "2026-06-02T21:00:00Z",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "draft_id": "draft-1",
                "draft_event_utc": "2026-06-02T20:59:00Z",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-BATCH",
                "asin": "ASIN-BATCH",
                "title": "Batch Product",
                "supplier_sku": "SUP-BATCH",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "supplier_order_viability_state": "review_only_not_po",
                "action_safety_state": "blocked_from_clean_buy",
                "action_block_reason": "refund:missing_refund_confidence",
                "line_state": "review_only_blocked",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": "needs_supplier_proof",
                "supplier_proof_missing_reasons": "supplier_stock_not_verified|backorder_not_verified",
                "supplier_match_state": "exact_supplier_sku_or_barcode_match",
                "supplier_proof_state": "supplier_exact_match_proved",
                "supplier_stock_state": "supplier_stock_not_verified",
                "backorder_state": "backorder_not_verified",
                "supplier_file_asof_utc": "",
                "supplier_cost_proof_state": "supplier_cost_verified",
                "pack_moq_proof_state": "pack_or_moq_visible",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_session_supplier_batch_summary_live",
        [
            {
                "batch_utc": "2026-06-02T21:00:00Z",
                "batch_id": "batch-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "draft_order_qty_total": "2",
                "draft_order_value_gbp": "6",
                "source_classes": "native_o",
                "blocked_line_count": "1",
                "native_line_count": "1",
                "legacy_bridge_line_count": "0",
                "batch_state": "review_only_blocked",
                "block_reasons": "refund:missing_refund_confidence",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_session_supplier_batch_health",
        [
            {
                "check_utc": "2026-06-02T21:00:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_lines=0",
                "notes": "local only",
                "source_path": "test",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)

    assert datasets["restock_session_supplier_batch_lines_live"].iloc[0]["creates_live_action"] == "0"
    assert datasets["restock_session_supplier_batch_lines_live"].iloc[0]["supplier_proof_checklist_status"] == "needs_supplier_proof"
    assert "supplier_stock_not_verified" in datasets["restock_session_supplier_batch_lines_live"].iloc[0]["supplier_proof_missing_reasons"]
    assert datasets["restock_session_supplier_batch_summary_live"].iloc[0]["batch_state"] == "review_only_blocked"
    assert datasets["restock_session_supplier_batch_health"].iloc[0]["status"] == "ok"


def test_load_operator_datasets_includes_supplier_file_presence_probe_outputs(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_supplier_file_presence_probe_live",
        [
            {
                "probe_utc": "2026-06-03T18:30:00Z",
                "probe_id": "probe-1",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "ABGee",
                "supplier_code": "ABG",
                "seller_sku": "12-749B-9EB5",
                "asin": "B084HZRR8G",
                "title": "Leatherface",
                "supplier_sku": "985 49830",
                "barcode": "889698498302",
                "draft_order_qty": "1",
                "price_files_root": "price-files",
                "supplier_folder_path": "price-files/ABGee",
                "latest_supplier_file_path": "price-files/ABGee/inbox/latest.csv",
                "latest_supplier_file_name": "latest.csv",
                "latest_supplier_file_mtime_utc": "2026-06-03T18:00:00Z",
                "latest_supplier_file_state": "latest_local_supplier_file_checked",
                "identity_match_state": "not_found_in_latest_local_supplier_file",
                "matched_by": "",
                "matched_row_count": "0",
                "searched_row_count": "1",
                "searched_identity_columns": "Barcode|Product Code",
                "probe_explanation": "Latest local supplier file was checked; exact supplier SKU or barcode was not found.",
                "clears_supplier_proof": "0",
                "purchase_approval_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_supplier_file_presence_probe_health",
        [
            {
                "check_utc": "2026-06-03T18:30:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "unsafe_rows=0",
                "notes": "local only",
                "source_path": "test",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)

    assert datasets["restock_supplier_file_presence_probe_live"].iloc[0]["identity_match_state"] == "not_found_in_latest_local_supplier_file"
    assert datasets["restock_supplier_file_presence_probe_live"].iloc[0]["clears_supplier_proof"] == "0"
    assert datasets["restock_supplier_file_presence_probe_health"].iloc[0]["status"] == "ok"


def test_load_operator_datasets_includes_supplier_file_source_index_outputs(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_supplier_file_source_index_live",
        [
            {
                "index_utc": "2026-06-03T19:15:00Z",
                "supplier_key": "abgee",
                "supplier_id": "abgee",
                "supplier_name": "ABGee",
                "f_source_status": "fail",
                "f_source_state": "error",
                "f_source_location": "gmail_label:ABGee",
                "f_latest_source_path": "old.xlsx",
                "f_latest_source_name": "old.xlsx",
                "f_latest_source_mtime_utc": "2026-05-22T13:55:17Z",
                "f_latest_source_path_exists": "0",
                "f_checked_at_utc": "2026-06-03T19:15:00Z",
                "local_price_files_root": "price-files",
                "local_supplier_folder_path": "price-files/ABGee",
                "local_latest_file_path": "price-files/ABGee/inbox/latest.xlsx",
                "local_latest_file_name": "latest.xlsx",
                "local_latest_file_mtime_utc": "2026-06-03T18:00:00Z",
                "local_file_count": "1",
                "source_handoff_state": "f_status_failed_local_file_available",
                "handoff_explanation": "F source status is failed, but O found a readable local supplier file.",
                "can_be_used_for_presence_probe": "1",
                "clears_supplier_proof": "0",
                "imports_supplier_file": "0",
                "updates_f_status": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_supplier_file_source_index_health",
        [
            {
                "check_utc": "2026-06-03T19:15:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "unsafe_rows=0",
                "notes": "local only",
                "source_path": "test",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)

    assert datasets["restock_supplier_file_source_index_live"].iloc[0]["source_handoff_state"] == "f_status_failed_local_file_available"
    assert datasets["restock_supplier_file_source_index_live"].iloc[0]["updates_f_status"] == "0"
    assert datasets["restock_supplier_file_source_index_health"].iloc[0]["status"] == "ok"


def test_load_operator_datasets_includes_purchase_approval_preview_outputs(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_preview_lines_live",
        [
            {
                "preview_utc": "2026-06-03T08:30:00Z",
                "approval_packet_id": "packet-1",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-PREVIEW",
                "asin": "ASIN-PREVIEW",
                "title": "Preview Product",
                "supplier_sku": "SUP-PREVIEW",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "supplier_batch_readiness_state": "ready_for_purchase_approval_review_only",
                "supplier_batch_readiness_reasons": "",
                "supplier_proof_checklist_status": "supplier_proof_clear",
                "supplier_proof_missing_reasons": "",
                "approval_preview_state": "ready_for_purchase_approval_review_only",
                "approval_block_reasons": "",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_preview_summary_live",
        [
            {
                "preview_utc": "2026-06-03T08:30:00Z",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "draft_order_qty_total": "2",
                "draft_order_value_gbp": "6",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "source_classes": "native_o",
                "approval_packet_state": "ready_for_purchase_approval_review_only",
                "approval_block_reasons": "",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_preview_health",
        [
            {
                "check_utc": "2026-06-03T08:30:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_decision_events",
        [
            {
                "event_utc": "2026-06-03T08:31:00Z",
                "decision_id": "decision-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_preview_utc": "2026-06-03T08:30:00Z",
                "decision_state": "local_review_accept_not_commitment",
                "expected_line_count": "1",
                "expected_ready_line_count": "1",
                "expected_blocked_line_count": "0",
                "expected_order_value_gbp": "6",
                "decision_note": "local review only",
                "actor": "operator_ui",
                "event_source_reference": "o_ui_purchase_approval_guardrails",
                "decision_status": "draft_guardrail_decision",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_guardrails_live",
        [
            {
                "guardrail_utc": "2026-06-03T08:31:00Z",
                "approval_packet_id": "packet-1",
                "source_preview_utc": "2026-06-03T08:30:00Z",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "draft_order_value_gbp": "6",
                "preview_packet_state": "ready_for_purchase_approval_review_only",
                "latest_decision_state": "local_review_accept_not_commitment",
                "latest_decision_id": "decision-1",
                "latest_decision_utc": "2026-06-03T08:31:00Z",
                "approval_guardrail_state": "local_review_accept_not_commitment",
                "approval_guardrail_reasons": "",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_purchase_approval_guardrails_health",
        [
            {
                "check_utc": "2026-06-03T08:31:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "unsafe_events=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_readiness_preview_lines_live",
        [
            {
                "preview_utc": "2026-06-03T08:32:00Z",
                "po_readiness_preview_id": "po-preview-1",
                "approval_packet_id": "packet-1",
                "source_preview_utc": "2026-06-03T08:30:00Z",
                "guardrail_utc": "2026-06-03T08:31:00Z",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-PREVIEW",
                "asin": "ASIN-PREVIEW",
                "title": "Preview Product",
                "supplier_sku": "SUP-PREVIEW",
                "barcode": "123",
                "draft_order_qty": "2",
                "current_supplier_cost_gbp": "3",
                "draft_line_value_gbp": "6",
                "approval_preview_state": "ready_for_purchase_approval_review_only",
                "approval_guardrail_state": "local_review_accept_not_commitment",
                "po_draft_readiness_state": "ready_for_local_po_draft_review_only",
                "po_draft_block_reasons": "",
                "po_creation_allowed": "0",
                "creates_live_action": "0",
                "supplier_proof_checklist_status": "supplier_proof_clear",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_readiness_preview_summary_live",
        [
            {
                "preview_utc": "2026-06-03T08:32:00Z",
                "po_readiness_preview_id": "po-preview-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "draft_order_qty_total": "2",
                "draft_order_value_gbp": "6",
                "approval_guardrail_state": "local_review_accept_not_commitment",
                "po_draft_preview_state": "ready_for_local_po_draft_review_only",
                "po_draft_block_reasons": "",
                "po_creation_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_readiness_preview_health",
        [
            {
                "check_utc": "2026-06-03T08:32:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_line_design_preview_lines_live",
        [
            {
                "preview_utc": "2026-06-03T08:33:00Z",
                "po_line_design_id": "line-design-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "po_readiness_preview_id": "po-preview-1",
                "approval_packet_id": "packet-1",
                "source_readiness_utc": "2026-06-03T08:32:00Z",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-PREVIEW",
                "asin": "ASIN-PREVIEW",
                "title": "Preview Product",
                "supplier_sku": "SUP-PREVIEW",
                "barcode": "123",
                "designed_order_qty": "2",
                "designed_unit_cost_gbp": "3",
                "designed_line_value_gbp": "6",
                "source_po_draft_readiness_state": "ready_for_local_po_draft_review_only",
                "line_design_state": "ready_for_local_po_line_design_review_only",
                "line_design_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_line_design_preview_summary_live",
        [
            {
                "preview_utc": "2026-06-03T08:33:00Z",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "designed_order_qty_total": "2",
                "designed_order_value_gbp": "6",
                "line_design_packet_state": "ready_for_local_po_line_design_review_only",
                "line_design_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_line_design_preview_health",
        [
            {
                "check_utc": "2026-06-03T08:33:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_packet_review_lines_live",
        [
            {
                "review_utc": "2026-06-03T08:34:00Z",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_id": "line-design-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_design_utc": "2026-06-03T08:33:00Z",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-PREVIEW",
                "asin": "ASIN-PREVIEW",
                "title": "Preview Product",
                "supplier_sku": "SUP-PREVIEW",
                "barcode": "123",
                "review_order_qty": "2",
                "review_unit_cost_gbp": "3",
                "review_line_value_gbp": "6",
                "source_line_design_state": "ready_for_local_po_line_design_review_only",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "packet_review_line_state": "ready_for_local_po_draft_packet_review_only",
                "packet_review_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_packet_review_summary_live",
        [
            {
                "review_utc": "2026-06-03T08:34:00Z",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "review_order_qty_total": "2",
                "review_order_value_gbp": "6",
                "packet_review_state": "ready_for_local_po_draft_packet_review_only",
                "packet_review_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_packet_review_health",
        [
            {
                "check_utc": "2026-06-03T08:34:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_hold_review_lines_live",
        [
            {
                "hold_utc": "2026-06-03T08:35:00Z",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_packet_review_utc": "2026-06-03T08:34:00Z",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-PREVIEW",
                "asin": "ASIN-PREVIEW",
                "title": "Preview Product",
                "supplier_sku": "SUP-PREVIEW",
                "barcode": "123",
                "hold_order_qty": "2",
                "hold_unit_cost_gbp": "3",
                "hold_line_value_gbp": "6",
                "source_packet_review_line_state": "ready_for_local_po_draft_packet_review_only",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "hold_review_line_state": "held_for_local_po_draft_review_only",
                "hold_review_reasons": "local_review_hold_zero_action",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_hold_review_summary_live",
        [
            {
                "hold_utc": "2026-06-03T08:35:00Z",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "held_line_count": "1",
                "blocked_line_count": "0",
                "hold_order_qty_total": "2",
                "hold_order_value_gbp": "6",
                "hold_review_state": "held_for_local_po_draft_review_only",
                "hold_review_reasons": "local_review_hold_zero_action",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_hold_review_health",
        [
            {
                "check_utc": "2026-06-03T08:35:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_file_shape_preview_lines_live",
        [
            {
                "shape_utc": "2026-06-03T08:36:00Z",
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_hold_utc": "2026-06-03T08:35:00Z",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU-PREVIEW",
                "asin": "ASIN-PREVIEW",
                "title": "Preview Product",
                "supplier_sku": "SUP-PREVIEW",
                "barcode": "123",
                "file_shape_qty": "2",
                "file_shape_unit_cost_gbp": "3",
                "file_shape_line_value_gbp": "6",
                "source_hold_review_line_state": "held_for_local_po_draft_review_only",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "file_shape_line_state": "ready_for_local_po_draft_file_shape_review_only",
                "file_shape_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_file_shape_preview_summary_live",
        [
            {
                "shape_utc": "2026-06-03T08:36:00Z",
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "file_shape_qty_total": "2",
                "file_shape_value_gbp": "6",
                "file_shape_state": "ready_for_local_po_draft_file_shape_review_only",
                "file_shape_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_file_shape_preview_health",
        [
            {
                "check_utc": "2026-06-03T08:36:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_preview_construction_summary_live",
        [
            {
                "summary_utc": "2026-06-03T08:37:00Z",
                "stage_key": "po_draft_file_shape",
                "stage_label": "PO draft file-shape preview",
                "source_contract": "restock_po_draft_file_shape_preview_lines_live",
                "source_health_contract": "restock_po_draft_file_shape_preview_health",
                "state_column": "file_shape_line_state",
                "line_rows": "1",
                "ready_or_held_rows": "1",
                "blocked_rows": "0",
                "health_rows": "1",
                "health_bad_rows": "0",
                "stage_state": "local_preview_ready_or_held",
                "stage_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_preview_construction_summary_health",
        [
            {
                "check_utc": "2026-06-03T08:37:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_review_control_events",
        [
            {
                "event_utc": "2026-06-03T08:38:00Z",
                "control_event_id": "control-event-1",
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_shape_utc": "2026-06-03T08:36:00Z",
                "decision_state": "local_po_draft_shape_ready_not_po",
                "expected_line_count": "1",
                "expected_ready_line_count": "1",
                "expected_blocked_line_count": "0",
                "expected_file_shape_value_gbp": "6",
                "decision_note": "local only",
                "actor": "operator_ui",
                "event_source_reference": "o_ui_po_draft_review_controls",
                "decision_status": "local_po_draft_review_control",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_review_controls_live",
        [
            {
                "control_utc": "2026-06-03T08:38:00Z",
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_shape_utc": "2026-06-03T08:36:00Z",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "file_shape_value_gbp": "6",
                "source_file_shape_state": "ready_for_local_po_draft_file_shape_review_only",
                "latest_decision_state": "local_po_draft_shape_ready_not_po",
                "latest_control_event_id": "control-event-1",
                "latest_decision_utc": "2026-06-03T08:38:00Z",
                "review_control_state": "local_po_draft_shape_ready_not_po",
                "review_control_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_review_controls_health",
        [
            {
                "check_utc": "2026-06-03T08:38:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_export_preview_lines_live",
        [
            {
                "export_preview_utc": "2026-06-03T08:39:00Z",
                "po_draft_export_preview_id": "export-preview-1",
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_shape_utc": "2026-06-03T08:36:00Z",
                "source_control_utc": "2026-06-03T08:38:00Z",
                "batch_id": "batch-1",
                "session_id": "o_restock_session_v1",
                "row_id": "row-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_class": "native_o",
                "seller_sku": "SKU1",
                "asin": "ASIN1",
                "title": "Product",
                "supplier_sku": "SUP1",
                "barcode": "123",
                "export_preview_qty": "2",
                "export_preview_unit_cost_gbp": "3",
                "export_preview_line_value_gbp": "6",
                "source_file_shape_line_state": "ready_for_local_po_draft_file_shape_review_only",
                "source_review_control_state": "local_po_draft_shape_ready_not_po",
                "source_po_file_write_allowed": "0",
                "source_po_creation_allowed": "0",
                "source_purchase_commitment_allowed": "0",
                "source_receiving_allowed": "0",
                "source_send_to_amazon_allowed": "0",
                "source_creates_live_action": "0",
                "control_po_file_write_allowed": "0",
                "control_po_creation_allowed": "0",
                "control_purchase_commitment_allowed": "0",
                "control_receiving_allowed": "0",
                "control_send_to_amazon_allowed": "0",
                "control_creates_live_action": "0",
                "export_preview_line_state": "ready_for_local_po_draft_export_preview_only",
                "export_preview_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_export_preview_summary_live",
        [
            {
                "export_preview_utc": "2026-06-03T08:39:00Z",
                "po_draft_export_preview_id": "export-preview-1",
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "export_preview_qty_total": "2",
                "export_preview_value_gbp": "6",
                "export_preview_state": "ready_for_local_po_draft_export_preview_only",
                "export_preview_block_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_export_preview_health",
        [
            {
                "check_utc": "2026-06-03T08:39:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_export_gate_events",
        [
            {
                "event_utc": "2026-06-03T08:40:00Z",
                "gate_event_id": "gate-event-1",
                "po_draft_export_preview_id": "export-preview-1",
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "source_export_preview_utc": "2026-06-03T08:39:00Z",
                "decision_state": "local_export_candidate_ready_not_po",
                "expected_line_count": "1",
                "expected_ready_line_count": "1",
                "expected_blocked_line_count": "0",
                "expected_export_preview_value_gbp": "6",
                "decision_note": "local only",
                "actor": "operator_ui",
                "event_source_reference": "o_ui_po_draft_export_gate",
                "decision_status": "local_po_draft_export_gate",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_export_gate_live",
        [
            {
                "gate_utc": "2026-06-03T08:40:00Z",
                "po_draft_export_preview_id": "export-preview-1",
                "po_draft_file_shape_preview_id": "file-shape-1",
                "po_draft_hold_review_id": "hold-review-1",
                "po_draft_packet_review_id": "packet-review-1",
                "po_line_design_packet_id": "line-design-packet-1",
                "approval_packet_id": "packet-1",
                "source_export_preview_utc": "2026-06-03T08:39:00Z",
                "supplier_name": "Supplier",
                "supplier_code": "SUP",
                "line_count": "1",
                "ready_line_count": "1",
                "blocked_line_count": "0",
                "export_preview_value_gbp": "6",
                "source_export_preview_state": "ready_for_local_po_draft_export_preview_only",
                "latest_decision_state": "local_export_candidate_ready_not_po",
                "latest_gate_event_id": "gate-event-1",
                "latest_decision_utc": "2026-06-03T08:40:00Z",
                "export_gate_state": "local_export_candidate_ready_not_po",
                "export_gate_reasons": "",
                "po_file_write_allowed": "0",
                "po_creation_allowed": "0",
                "purchase_commitment_allowed": "0",
                "receiving_allowed": "0",
                "send_to_amazon_allowed": "0",
                "creates_live_action": "0",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_po_draft_export_gate_health",
        [
            {
                "check_utc": "2026-06-03T08:40:00Z",
                "check": "local_only_guard",
                "status": "ok",
                "value": "live_action_rows=0",
                "notes": "local",
                "source_path": "test",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)

    assert datasets["restock_purchase_approval_preview_lines_live"].iloc[0]["creates_live_action"] == "0"
    assert datasets["restock_purchase_approval_preview_lines_live"].iloc[0]["approval_preview_state"] == "ready_for_purchase_approval_review_only"
    assert datasets["restock_purchase_approval_preview_summary_live"].iloc[0]["ready_line_count"] == "1"
    assert datasets["restock_purchase_approval_preview_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_purchase_approval_decision_events"].iloc[0]["creates_live_action"] == "0"
    assert datasets["restock_purchase_approval_guardrails_live"].iloc[0]["approval_guardrail_state"] == "local_review_accept_not_commitment"
    assert datasets["restock_purchase_approval_guardrails_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_draft_readiness_preview_lines_live"].iloc[0]["po_creation_allowed"] == "0"
    assert datasets["restock_po_draft_readiness_preview_lines_live"].iloc[0]["po_draft_readiness_state"] == "ready_for_local_po_draft_review_only"
    assert datasets["restock_po_draft_readiness_preview_summary_live"].iloc[0]["ready_line_count"] == "1"
    assert datasets["restock_po_draft_readiness_preview_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_line_design_preview_lines_live"].iloc[0]["po_file_write_allowed"] == "0"
    assert datasets["restock_po_line_design_preview_lines_live"].iloc[0]["line_design_state"] == "ready_for_local_po_line_design_review_only"
    assert datasets["restock_po_line_design_preview_summary_live"].iloc[0]["send_to_amazon_allowed"] == "0"
    assert datasets["restock_po_line_design_preview_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_draft_packet_review_lines_live"].iloc[0]["source_po_file_write_allowed"] == "0"
    assert datasets["restock_po_draft_packet_review_lines_live"].iloc[0]["packet_review_line_state"] == "ready_for_local_po_draft_packet_review_only"
    assert datasets["restock_po_draft_packet_review_summary_live"].iloc[0]["send_to_amazon_allowed"] == "0"
    assert datasets["restock_po_draft_packet_review_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_draft_hold_review_lines_live"].iloc[0]["source_po_file_write_allowed"] == "0"
    assert datasets["restock_po_draft_hold_review_lines_live"].iloc[0]["hold_review_line_state"] == "held_for_local_po_draft_review_only"
    assert datasets["restock_po_draft_hold_review_summary_live"].iloc[0]["send_to_amazon_allowed"] == "0"
    assert datasets["restock_po_draft_hold_review_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_draft_file_shape_preview_lines_live"].iloc[0]["source_po_file_write_allowed"] == "0"
    assert datasets["restock_po_draft_file_shape_preview_lines_live"].iloc[0]["file_shape_line_state"] == "ready_for_local_po_draft_file_shape_review_only"
    assert datasets["restock_po_draft_file_shape_preview_summary_live"].iloc[0]["send_to_amazon_allowed"] == "0"
    assert datasets["restock_po_draft_file_shape_preview_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_preview_construction_summary_live"].iloc[0]["stage_key"] == "po_draft_file_shape"
    assert datasets["restock_po_preview_construction_summary_live"].iloc[0]["creates_live_action"] == "0"
    assert datasets["restock_po_preview_construction_summary_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_draft_review_control_events"].iloc[0]["creates_live_action"] == "0"
    assert datasets["restock_po_draft_review_control_events"].iloc[0]["po_creation_allowed"] == "0"
    assert datasets["restock_po_draft_review_controls_live"].iloc[0]["review_control_state"] == "local_po_draft_shape_ready_not_po"
    assert datasets["restock_po_draft_review_controls_live"].iloc[0]["po_file_write_allowed"] == "0"
    assert datasets["restock_po_draft_review_controls_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_draft_export_preview_lines_live"].iloc[0]["export_preview_line_state"] == "ready_for_local_po_draft_export_preview_only"
    assert datasets["restock_po_draft_export_preview_lines_live"].iloc[0]["po_file_write_allowed"] == "0"
    assert datasets["restock_po_draft_export_preview_summary_live"].iloc[0]["send_to_amazon_allowed"] == "0"
    assert datasets["restock_po_draft_export_preview_health"].iloc[0]["status"] == "ok"
    assert datasets["restock_po_draft_export_gate_events"].iloc[0]["creates_live_action"] == "0"
    assert datasets["restock_po_draft_export_gate_live"].iloc[0]["export_gate_state"] == "local_export_candidate_ready_not_po"
    assert datasets["restock_po_draft_export_gate_live"].iloc[0]["po_file_write_allowed"] == "0"
    assert datasets["restock_po_draft_export_gate_health"].iloc[0]["status"] == "ok"


def test_operator_ui_reexports_safe_restock_session_draft_submitter(tmp_path: Path) -> None:
    session_row = {
        "session_id": "o_restock_session_v1",
        "row_id": "o_restock_session_v1:native_o:supplier:sku",
        "seller_sku": "SKU-DRAFT",
        "asin": "ASIN-DRAFT",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_class": "native_o",
        "source_reference": "native_o:SKU-DRAFT",
    }

    saved = submit_restock_session_draft_decision(
        root=tmp_path,
        session_row=session_row,
        decision_code="drop",
        decision_note="drop for now",
        actor="operator_ui",
        event_source_reference="test",
    )

    assert saved["decision_code"] == "drop"
    assert saved["creates_live_action"] == "0"


def test_operator_ui_reexports_safe_supplier_proof_submitter(tmp_path: Path) -> None:
    session_row = {
        "session_id": "o_restock_session_v1",
        "row_id": "o_restock_session_v1:native_o:supplier:sku",
        "seller_sku": "SKU-PROOF",
        "asin": "ASIN-PROOF",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_class": "native_o",
        "row_source_reference": "native_o:SKU-PROOF",
    }

    saved = submit_restock_session_supplier_proof_event(
        root=tmp_path,
        session_row=session_row,
        supplier_stock_state="supplier_stock_verified_zero",
        supplier_stock_qty="0",
        backorder_state="backorder_not_verified",
        proof_note="supplier out of stock",
        actor="operator_ui",
        event_source_reference="test",
    )

    assert saved["supplier_stock_state"] == "supplier_stock_verified_zero"
    assert saved["proof_status"] == "draft_proof"
    assert saved["creates_live_action"] == "0"


def test_operator_ui_reexports_safe_pack_moq_proof_submitter(tmp_path: Path) -> None:
    session_row = {
        "session_id": "o_restock_session_v1",
        "row_id": "o_restock_session_v1:native_o:supplier:sku",
        "seller_sku": "SKU-PACK",
        "asin": "ASIN-PACK",
        "supplier_name": "Supplier",
        "supplier_code": "SUP",
        "source_class": "native_o",
        "row_source_reference": "native_o:SKU-PACK",
    }

    saved = submit_restock_session_pack_moq_proof_event(
        root=tmp_path,
        session_row=session_row,
        pack_moq_proof_state="pack_moq_verified",
        pack_multiple="6",
        supplier_moq="12",
        valid_order_step="6",
        proof_file_reference="pack-file.csv",
        proof_note="checked pack",
        actor="operator_ui",
        event_source_reference="test",
    )

    assert saved["pack_moq_proof_state"] == "pack_moq_verified"
    assert saved["proof_status"] == "draft_proof"
    assert saved["creates_live_action"] == "0"


def test_feeder_review_headers_keep_roi_in_own_column() -> None:
    assert "ROI" in FEEDER_REVIEW_HEADER_LABELS
    assert "Profit" in FEEDER_REVIEW_HEADER_LABELS
    assert "ROI / Profit" not in FEEDER_REVIEW_HEADER_LABELS
    assert FEEDER_REVIEW_HEADER_LABELS.index("ROI") < FEEDER_REVIEW_HEADER_LABELS.index("Profit")
    assert len(FEEDER_REVIEW_HEADER_LABELS) == len(FEEDER_REVIEW_COLUMN_WIDTHS)


def test_supplier_intake_evidence_summary_is_plain_english() -> None:
    summary = _humanize_intake_evidence_summary(
        "screen_status=PASS | original_score=4 | rank=1483 | "
        "units_likely_30d=9 | profit_likely_gbp=13.35"
    )

    assert "screen_status" not in summary
    assert "Passed the scanner checks." in summary
    assert "Scanner score: 4." in summary
    assert "Amazon rank: #1,483." in summary
    assert "Likely 30 day sales: 9." in summary


def test_supplier_intake_evidence_summary_handles_empty_scanner_fields() -> None:
    summary = _humanize_intake_evidence_summary(
        "decision_confidence=NA | stability_state=NA",
        fallback="No extra warning from scanner.",
    )

    assert summary == "No extra warning from scanner."


def test_supplier_intake_plain_choice_labels_keep_internal_decisions() -> None:
    assert _normalize_feeder_review_decision("Keep for listing check") == "pass"
    assert _normalize_feeder_review_decision("Reject") == "fail"
    assert _normalize_feeder_review_decision("Needs re-scan") == "rescan"
    assert _normalize_feeder_review_decision("Re scan") == "rescan"


def test_supplier_intake_missing_image_links_to_amazon() -> None:
    html = _intake_image_html("", "https://www.amazon.co.uk/dp/B083TLCKWB")

    assert "Image unavailable" in html
    assert "Open Amazon" in html
    assert "B083TLCKWB" in html


def test_supplier_intake_top_labels_are_plain_english() -> None:
    assert _feeder_review_lane_display_label("Passes") == "Best finds"
    assert _feeder_review_lane_display_label("Manual review") == "Needs Luke's judgement"
    assert _feeder_review_lane_display_label("Near misses") == "Close calls"
    assert _feeder_review_pack_work_phrase("Passes", 1, unique=True) == "1 unique scanner find waiting"
    assert _feeder_review_pack_work_phrase("Manual review", 2) == "2 judgement checks waiting"
    assert _feeder_review_pack_work_phrase("Near misses", 1) == "1 close call waiting"


def test_operator_sidebar_active_label_is_visible_plain_text() -> None:
    assert _operator_sidebar_button_label("Supplier Intake", active=True) == "Selected - Supplier Intake"
    assert _operator_sidebar_button_label("Supplier Intake", active=False) == "Supplier Intake"


def test_supplier_intake_notice_and_empty_state_use_readable_text() -> None:
    notice_html = _render_inline_notice("Saved 1 local choice.")
    empty_html = _render_intake_empty_state_html("No products need a choice", "Try a different supplier.")

    assert "color:#0f4fb8" in notice_html
    assert "Saved 1 local choice." in notice_html
    assert "No products need a choice" in empty_html
    assert "Try a different supplier." in empty_html


def test_supplier_intake_focus_strip_summarizes_current_view_plainly() -> None:
    html = _intake_focus_strip_html(
        work_pack="Best finds",
        supplier="CLF",
        batch="Auto next 10",
        shown=10,
        waiting=7,
        saved=3,
    )

    assert "o-intake-focus-strip" in html
    assert "Work pack" in html
    assert "Best finds" in html
    assert "Supplier" in html
    assert "CLF" in html
    assert "Products shown" in html
    assert "10" in html
    assert "Need choice" in html
    assert "Already saved" in html


def test_supplier_intake_choice_and_submit_panels_are_local_only() -> None:
    choice_html = _intake_choice_panel_html({"supplier_sku": "SKU-1"})
    submit_html = _intake_submit_panel_html(ready=2, need_choice=8)

    assert "Luke's choice for this product" in choice_html
    assert "SKU-1" in choice_html
    assert "Nothing is sent until the local choices button is pressed" in choice_html
    assert "Save this page's local choices" in submit_html
    assert "2 choices ready to save locally" in submit_html
    assert "8 products still need Luke" in submit_html
    assert "does not buy stock" in submit_html
    assert "run the scanner" in submit_html


def test_admin_compact_strip_is_light_plain_summary_html() -> None:
    html = _admin_compact_strip_html([("Suppliers", 14), ("Blocked", 2)])

    assert "o-admin-compact-strip" in html
    assert "Suppliers" in html
    assert "14" in html
    assert "Blocked" in html
    assert "2" in html


def test_supplier_intake_compact_alert_and_detail_drawer_are_plain() -> None:
    alert_html = _intake_alert_html("What to check", "Confirm pack size before keeping.")
    drawer_html = _intake_detail_drawer_html(
        why_label="Why this is here",
        why_body="Passed scanner checks.",
        id_line_html="Supplier code: ABC | ASIN: B000000001",
        rank_text="#1,483",
        score_text="4",
        profit_range_text="GBP 4 / GBP 8 / GBP 12",
    )

    assert "o-intake-alert" in alert_html
    assert "Confirm pack size before keeping." in alert_html
    assert "<details class='o-intake-detail-drawer'>" in drawer_html
    assert "<summary>Scanner details</summary>" in drawer_html
    assert "Passed scanner checks." in drawer_html
    assert "Amazon rank: #1,483" in drawer_html
    assert "Supplier code: ABC" in drawer_html


def test_supplier_intake_sent_choice_card_is_plain_english() -> None:
    card_html = _render_intake_sent_choice_card_html(
        decision="pass",
        sku="SKU-1",
        title="Example Product",
        note="Looks right",
        when="2026-06-03T10:00:00Z",
    )

    assert "PASS - SKU-1" in card_html
    assert "Example Product" in card_html
    assert "Note: Looks right" in card_html
    assert "Sent: 2026-06-03T10:00:00Z" in card_html


def test_price_list_queue_loader_and_summary_reads_dashboard_csv(tmp_path: Path) -> None:
    dashboard_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "status_dashboard.csv"
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "queue_position": "1",
                "supplier_id": "shure_cosmetics",
                "supplier_name": "Shure Cosmetics",
                "source_method": "CSV link",
                "source_location": "https://aux.shure-cosmetics.co.uk/pricelist/",
                "file_state": "Ready",
                "queue_state": "Active",
                "operator_action": "Ready for test queue",
                "control_state": "Pause and prioritise planned",
                "price_list_date": "2026-04-30T09:00:00Z",
                "bot_status": "Test Ready",
                "web_unprocessed": "10",
                "web_pass": "0",
                "web_fail": "0",
                "web_rescan": "0",
                "second_unprocessed": "0",
                "second_pass": "0",
                "second_fail": "0",
            },
            {
                "queue_position": "2",
                "supplier_id": "dhb",
                "supplier_name": "DHB",
                "source_method": "Email request",
                "source_location": r"C:\Users\Luke\Desktop\SellerOne Price Files\DHB\inbox",
                "file_state": "Missing",
                "queue_state": "Needs Manual File",
                "operator_action": "Request price file",
                "control_state": "Pause and prioritise planned",
                "price_list_date": "",
                "bot_status": "Missing",
                "web_unprocessed": "0",
                "web_pass": "0",
                "web_fail": "0",
                "web_rescan": "0",
                "second_unprocessed": "0",
                "second_pass": "0",
                "second_fail": "0",
            },
        ]
    ).to_csv(dashboard_path, index=False)

    queue_df = _read_price_list_queue_df(tmp_path)
    summary = build_price_list_queue_summary(queue_df)

    assert len(queue_df) == 2
    assert queue_df.iloc[0]["supplier_name"] == "Shure Cosmetics"
    assert summary == {
        "total_suppliers": 2,
        "active": 1,
        "manual_missing": 1,
        "blocked": 0,
        "web_unprocessed": 10,
        "web_pass": 0,
        "web_fail": 0,
        "web_rescan": 0,
    }


def test_price_list_queue_summary_can_ignore_non_active_sample_results() -> None:
    queue_df = pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "queue_state": "Recommended",
                "web_unprocessed": "19683",
                "web_pass": "124",
                "web_fail": "1977",
                "web_rescan": "0",
            },
            {
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "queue_state": "Queued",
                "web_unprocessed": "1506",
                "web_pass": "0",
                "web_fail": "0",
                "web_rescan": "0",
            },
        ]
    )

    summary = build_price_list_queue_summary(queue_df)

    assert summary["web_unprocessed"] == 21189
    assert summary["web_pass"] == 124
    assert summary["web_fail"] == 1977
    assert summary["web_rescan"] == 0


def test_price_list_queue_report_loader_reads_markdown(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "next_action_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# Price List Next Action Report\n\n- Supplier: Bliss Distribution\n- Safe to hand off to F061: 0\n",
        encoding="utf-8",
    )

    report = _read_price_list_next_action_report(tmp_path)

    assert "Bliss Distribution" in report
    assert "Safe to hand off to F061: 0" in report


def test_scanner_timeout_policy_ui_save_writes_only_policy_file(tmp_path: Path) -> None:
    health_path = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode" / "health.csv"
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text("check,status,value,notes,observed_utc,source_path\nseed,ok,1,seed,2026-05-01T00:00:00Z,seed\n")

    policy = _read_scanner_timeout_policy_df(tmp_path)
    before_files = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file())
    before_health = health_path.read_text()

    edited = policy.copy()
    edited.loc[edited["fail_code"] == "NOASIN", "notes"] = "operator edited note"
    result = save_scanner_timeout_policy_from_ui(
        tmp_path,
        edited,
        observed_utc="2026-05-01T10:00:00Z",
    )

    after_files = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file())
    saved = pd.read_csv(tmp_path / "config" / "feeder" / "f_scanner_timeout_policy.csv", dtype=str).fillna("")

    assert result["policy_rows"] == 15
    assert before_files == after_files
    assert health_path.read_text() == before_health
    assert saved.loc[saved["fail_code"] == "NOASIN", "notes"].iloc[0] == "operator edited note"


def test_scanner_timeout_policy_ui_reset_restores_defaults(tmp_path: Path) -> None:
    edited = _read_scanner_timeout_policy_df(tmp_path)
    edited.loc[edited["fail_code"] == "NOASIN", "timeout_mode"] = "disabled"
    save_scanner_timeout_policy_from_ui(tmp_path, edited, observed_utc="2026-05-01T10:00:00Z")

    result = reset_scanner_timeout_policy_from_ui(tmp_path, observed_utc="2026-05-01T11:00:00Z")
    reset = pd.read_csv(tmp_path / "config" / "feeder" / "f_scanner_timeout_policy.csv", dtype=str).fillna("")

    assert result["policy_rows"] == 15
    assert reset.loc[reset["fail_code"] == "NOASIN", "timeout_mode"].iloc[0] == "fixed_days"
    assert reset.loc[reset["fail_code"] == "NOASIN", "updated_at_utc"].iloc[0] == "2026-05-01T11:00:00Z"


def test_price_list_login_counts_read_active_login_backtrack_rows(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "normal",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "supplier_title": "Normal Row",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
            },
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "login",
                "supplier_sku": "S2",
                "barcode": "5000000000002",
                "supplier_title": "Login Row",
                "unit_cost": "2.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "1",
                "last_attempt_utc": "2026-05-09T01:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
                "completion_block_reason": "bbp_login_required",
            },
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "dashboard",
                "supplier_sku": "S4",
                "barcode": "5000000000004",
                "supplier_title": "Dashboard Row",
                "unit_cost": "4.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "1",
                "last_attempt_utc": "2026-05-09T01:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
                "completion_block_reason": "dashboard_yes_no_backtrack_required",
            },
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "login_reason",
                "supplier_sku": "S3",
                "barcode": "5000000000003",
                "supplier_title": "Login Reason Row",
                "unit_cost": "3.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "1",
                "last_attempt_utc": "2026-05-09T01:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
                "completion_block_reason": "bbp_login_required",
            },
            {
                "run_id": "run_b",
                "supplier_id": "heo",
                "supplier_name": "Heo",
                "row_key": "other_login",
                "supplier_sku": "H1",
                "barcode": "6000000000001",
                "supplier_title": "Other Login Row",
                "unit_cost": "4.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "login_backtrack_pending",
                "scan_reason": "login_backtrack_required",
                "attempt_count": "1",
                "last_attempt_utc": "2026-05-09T01:00:00Z",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
                "completion_block_reason": "bbp_login_required",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 3, "bbp_login": 2, "dashboard_login": 1, "login_pending": 2, "login_running": 0}


def test_price_list_login_counts_include_unpromoted_ledger_backlog(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "supplier_price_list_active_run",
        [
            {
                "run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "row_key": "normal",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "supplier_title": "Normal Row",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-05-09T00:00:00Z",
            },
        ],
    )
    _write_f_contract_rows(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-dashboard",
                "backtrack_observed_utc": "2026-05-09T01:00:00Z",
                "original_observed_utc": "2026-05-09T00:30:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S2",
                "barcode": "5000000000002",
                "candidate_id": "dashboard-row",
                "unit_cost": "2.00",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-unresolved",
                "backtrack_observed_utc": "2026-05-09T01:01:00Z",
                "original_observed_utc": "2026-05-09T00:31:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S3",
                "barcode": "5000000000003",
                "candidate_id": "unresolved-row",
                "unit_cost": "3.00",
                "backtrack_attempt_number": "3",
                "backtrack_status": "dashboard_yes_no_unresolved",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-bbp",
                "backtrack_observed_utc": "2026-05-09T01:02:00Z",
                "original_observed_utc": "2026-05-09T00:32:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S4",
                "barcode": "5000000000004",
                "candidate_id": "bbp-row",
                "unit_cost": "4.00",
                "backtrack_attempt_number": "1",
                "backtrack_status": "blocked_login",
                "merged_into_candidate_flag": "0",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 3, "bbp_login": 1, "dashboard_login": 2, "login_pending": 0, "login_running": 0}


def test_price_list_login_counts_ignore_stale_resolved_ledger_rows(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-old",
                "backtrack_observed_utc": "2026-05-13T10:00:00Z",
                "original_observed_utc": "2026-05-13T09:30:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "candidate_id": "row-1",
                "unit_cost": "2.00",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-new",
                "backtrack_observed_utc": "2026-05-13T11:00:00Z",
                "original_observed_utc": "2026-05-13T09:30:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "supplier_sku": "S1",
                "barcode": "5000000000001",
                "candidate_id": "row-1",
                "unit_cost": "2.00",
                "backtrack_attempt_number": "2",
                "backtrack_status": "resolved",
                "merged_into_candidate_flag": "0",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 0, "bbp_login": 0, "dashboard_login": 0, "login_pending": 0, "login_running": 0}


def test_price_list_login_counts_ignore_stale_unresolved_when_latest_is_merged(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-old",
                "backtrack_observed_utc": "2026-05-13T10:00:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "candidate_id": "row-1",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-new",
                "backtrack_observed_utc": "2026-05-13T11:00:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "candidate_id": "row-1",
                "backtrack_attempt_number": "2",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "1",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 0, "bbp_login": 0, "dashboard_login": 0, "login_pending": 0, "login_running": 0}


def test_price_list_login_counts_scope_latest_ledger_rows_by_run(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "f_login_backtrack_evidence_live",
        [
            {
                "backtrack_id": "bt-run-a",
                "backtrack_observed_utc": "2026-05-13T10:00:00Z",
                "original_observed_utc": "2026-05-13T09:30:00Z",
                "original_run_id": "run_a",
                "supplier_id": "stax",
                "candidate_id": "same-row",
                "backtrack_attempt_number": "1",
                "backtrack_status": "missing_dashboard_yes_no",
                "merged_into_candidate_flag": "0",
            },
            {
                "backtrack_id": "bt-run-b",
                "backtrack_observed_utc": "2026-05-13T11:00:00Z",
                "original_observed_utc": "2026-05-13T10:30:00Z",
                "original_run_id": "run_b",
                "supplier_id": "stax",
                "candidate_id": "same-row",
                "backtrack_attempt_number": "1",
                "backtrack_status": "resolved",
                "merged_into_candidate_flag": "0",
            },
        ],
    )

    counts = _price_list_login_counts(tmp_path, "run_a")

    assert counts == {"login": 1, "bbp_login": 0, "dashboard_login": 1, "login_pending": 0, "login_running": 0}


def test_price_list_auth_state_and_login_button_state(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=LOGIN_REQUIRED|reason=auth_required|updated_utc=2026-05-09T09:00:00Z\n",
        encoding="utf-8",
    )

    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["auth_state"] == "LOGIN_REQUIRED"
    assert auth["login_mode_request_exists"] == "0"
    assert button["badge_state"] == "required"
    assert button["disabled"] is False

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=AMAZON_DASHBOARD_LOGIN_REQUIRED|reason=amazon_dashboard_login_required|updated_utc=2026-05-09T09:01:00Z\n",
        encoding="utf-8",
    )
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["auth_state"] == "AMAZON_DASHBOARD_LOGIN_REQUIRED"
    assert button["badge_state"] == "dashboard_required"
    assert button["label"] == "YES/NO Login"
    assert button["disabled"] is False

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=BBP_LOGIN_REQUIRED|reason=bbp_login_required|updated_utc=2026-05-09T09:02:00Z\n",
        encoding="utf-8",
    )
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["auth_state"] == "BBP_LOGIN_REQUIRED"
    assert button["badge_state"] == "bbp_required"
    assert button["label"] == "BBP Login"
    assert button["disabled"] is False

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=visible|browser_state=VISIBLE|auth_state=LOGIN_REQUIRED|reason=auth_required|updated_utc=2026-05-09T09:03:00Z\n",
        encoding="utf-8",
    )
    (live_dir / "f061_login_mode.requested").write_text("status=requested\n", encoding="ascii")
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["login_mode_request_exists"] == "1"
    assert button["badge_state"] == "required"
    assert button["label"] == "Login"
    assert button["disabled"] is False

    (live_dir / "f061_browser_visibility_state.txt").write_text(
        "state=hidden|browser_state=HIDDEN|auth_state=LOGGED_IN|reason=child_started_minimized|updated_utc=2026-05-09T09:05:00Z\n",
        encoding="utf-8",
    )
    (live_dir / "f061_login_mode.requested").write_text("status=holding\n", encoding="ascii")
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=3,
        auth_state=auth["auth_state"],
        request_exists=auth["login_mode_request_exists"] == "1",
        request_status=auth["login_mode_request_status"],
    )

    assert auth["login_mode_request_exists"] == "1"
    assert auth["login_mode_request_status"] == "holding"
    assert auth["auth_state"] == ""
    assert button["badge_state"] == "requested"
    assert button["label"] == "Login Requested"
    assert button["disabled"] is True

    (live_dir / "f061_login_mode.requested").write_text("status=drained\n", encoding="ascii")
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=0,
        auth_state="LOGGED_IN",
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["login_mode_request_exists"] == "0"
    assert auth["login_mode_request_status"] == "drained"
    assert button["badge_state"] == "logged_in"
    assert button["disabled"] is True

    button = _price_list_login_button_state(
        login_rows=2,
        auth_state="LOGGED_IN",
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert button["badge_state"] == "catching_up"
    assert button["label"] == "Catching Up"
    assert button["disabled"] is True

    (live_dir / "f061_login_mode.requested").write_text("status=still_required\n", encoding="ascii")
    auth = _price_list_auth_state(tmp_path)
    button = _price_list_login_button_state(
        login_rows=2,
        auth_state="LOGIN_REQUIRED",
        request_exists=auth["login_mode_request_exists"] == "1",
    )

    assert auth["login_mode_request_exists"] == "0"
    assert auth["login_mode_request_status"] == "still_required"
    assert button["badge_state"] == "required"
    assert button["disabled"] is False

    button = _price_list_login_button_state(
        login_rows=2,
        auth_state="AMAZON_DASHBOARD_LOGIN_REQUIRED",
        request_exists=True,
    )

    assert button["badge_state"] == "dashboard_required"
    assert button["label"] == "YES/NO Login"
    assert button["disabled"] is False


def test_price_list_manager_mode_state_drives_operator_badge(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_manager_mode_state.txt").write_text(
        "mode=Catching Up|auth_state=LOGGED_IN|browser_mode=minimized|browser_visibility=hidden|updated_utc=2026-05-14T10:00:00Z\n",
        encoding="ascii",
    )

    state = _price_list_manager_mode_state(tmp_path)
    badge = _price_list_login_badge_html(
        {"badge_state": "logged_in"},
        login_rows=9,
        auth_state="LOGGED_IN",
        manager_mode=state["mode"],
    )

    assert state["mode"] == "Catching Up"
    assert "CATCHING UP" in badge
    assert "9 rows" in badge


def test_price_list_supervisor_state_drives_visible_badge(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "fpm_live_supervisor_state.txt").write_text(
        "state=ok|reason=freshest_live_state_seconds=2.0|manager_pids=123|child_pids=456|updated_utc=2026-05-14T14:31:23Z\n",
        encoding="ascii",
    )

    state = _price_list_supervisor_state(tmp_path)
    badge = _price_list_supervisor_badge_html(state)

    assert state["state"] == "ok"
    assert state["badge_state"] == "ok"
    assert "SUPERVISOR OK" in badge
    assert "freshest_live_state_seconds=2.0" in badge


def test_price_list_supervisor_badge_warns_when_process_is_alive_but_rows_are_not_moving(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "fpm_live_supervisor_state.txt").write_text(
        "state=ok|reason=process_alive_seconds=2.0|manager_pids=123|child_pids=456|stale_seconds=900|updated_utc=2026-05-14T14:31:23Z\n",
        encoding="ascii",
    )
    (live_dir / "live_cycle_events.csv").write_text(
        "event_utc,event_type,status,supplier_id,rows\n"
        "2000-01-01T00:00:00Z,scanner_chunk,success,td_synnex,25\n",
        encoding="ascii",
    )

    state = _price_list_supervisor_state(tmp_path)
    badge = _price_list_supervisor_badge_html(state)

    assert state["state"] == "ok"
    assert state["badge_state"] == "no_progress"
    assert state["progress_state"] == "no_row_progress"
    assert "PROCESS ALIVE - NO ROW PROGRESS" in badge
    assert "scanner_progress_seconds=" in badge


def test_price_list_login_mode_request_writes_control_file_and_event_only(tmp_path: Path) -> None:
    result = request_price_list_login_mode_from_ui(
        tmp_path,
        supplier_id="stax",
        run_id="fpm_stax_20260507T151124Z",
        observed_utc="2026-05-09T09:15:00Z",
    )

    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    request_path = live_dir / "f061_login_mode.requested"
    event_path = live_dir / "live_cycle_events.csv"
    event_df = pd.read_csv(event_path, dtype=str).fillna("")

    assert result["status"] == "requested"
    assert request_path.exists()
    assert "requested_by=operator_ui" in request_path.read_text(encoding="ascii")
    assert "controller_owner=F_LOGIN_CONTROLLER_REWRITE_V1" in request_path.read_text(encoding="ascii")
    assert "mode=login_recovery" in request_path.read_text(encoding="ascii")
    assert "hold_seconds=900" in request_path.read_text(encoding="ascii")
    assert result["hold_seconds"] == "900"
    assert not (live_dir / "f061_visible_login.requested").exists()
    assert event_df.iloc[-1]["event_type"] == "login_mode_requested"
    assert event_df.iloc[-1]["supplier_id"] == "stax"
    assert event_df.iloc[-1]["f061_run_id"] == "fpm_stax_20260507T151124Z"


def test_price_list_live_progress_helpers_read_runtime_files(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-30T20:00:00Z",
                "loop_run_id": "fpm_live_old",
                "pid": "111",
                "state": "running",
                "supplier_id": "old_supplier",
                "f061_run_id": "old_run",
                "pending_before": "12",
                "action": "resume_f061_active_run",
                "action_status": "success",
                "chunk_rows": "5",
                "safe_to_handoff_flag": "0",
                "detail": "old",
            },
            {
                "observed_utc": "2026-04-30T20:02:00Z",
                "loop_run_id": "fpm_live_new",
                "pid": "222",
                "state": "running",
                "supplier_id": "entertainment_trading",
                "f061_run_id": "fpm_entertainment_trading_20260430T151417Z",
                "pending_before": "7",
                "action": "resume_f061_active_run",
                "action_status": "success",
                "chunk_rows": "5",
                "safe_to_handoff_flag": "0",
                "detail": "f061_subprocess_completed",
            },
        ]
    ).to_csv(live_dir / "live_cycle_status.csv", index=False)
    (live_dir / "live_cycle_events.csv").write_text(
        "observed_utc,run_id,event_type,active_supplier_id,active_f061_run_id,status,chunk_rows,detail\n"
        "2026-04-30T20:02:30Z,fpm_live_new,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,5,pending_after=7\n",
        encoding="utf-8",
    )

    active_run = tmp_path / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv"
    active_run.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"barcode": "111", "scan_status": "done"},
            {"barcode": "222", "scan_status": "pending"},
            {"barcode": "333", "scan_status": "pending"},
        ]
    ).to_csv(active_run, index=False)

    status = _latest_price_list_live_status(tmp_path)
    counts = _price_list_active_run_counts(tmp_path)
    event = _latest_price_list_live_event(tmp_path)
    progress_total = _price_list_live_progress_total(tmp_path, "fpm_entertainment_trading_20260430T151417Z")

    assert status["supplier_id"] == "entertainment_trading"
    assert status["pending_before"] == "7"
    assert counts == {"total": 3, "pending": 2, "done": 1, "held": 0}
    assert event == (
        "2026-04-30T20:02:30Z,fpm_live_new,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,5,pending_after=7"
    )
    assert progress_total == 12


def test_price_list_child_status_reads_live_heartbeat(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_child_status.txt").write_text(
        "pid=19600|supplier_id=entertainment_trading|chunk_rows=5|heartbeat=2026-04-30T20:27:19Z",
        encoding="utf-8",
    )

    assert "pid=19600" in _price_list_child_status(tmp_path)


def test_price_list_child_status_flags_stale_child_output(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "f061_child_status.txt").write_text(
        "pid=19600|supplier_id=entertainment_trading|chunk_rows=5|heartbeat=2026-04-30T20:27:19Z",
        encoding="utf-8",
    )
    stdout = live_dir / "f061_child_stdout.log"
    stdout.write_text("stale output\n", encoding="utf-8")
    stale_epoch = time.time() - 3600
    stdout.touch()

    os.utime(stdout, (stale_epoch, stale_epoch))

    status = _price_list_child_status(tmp_path)

    assert "pid=19600" in status
    assert "warning=no_child_output_30m" in status


def test_price_list_live_progress_total_reads_runtime_event_columns(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "live_cycle_events.csv").write_text(
        "event_utc,cycle_run_id,event_type,supplier_id,f061_run_id,status,rows,notes\n"
        "2026-04-30T15:14:17Z,fpm_live,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,50,pending_after=20033\n",
        encoding="utf-8",
    )

    progress_total = _price_list_live_progress_total(tmp_path, "fpm_entertainment_trading_20260430T151417Z")

    assert progress_total == 20083


def test_price_list_live_eta_uses_current_run_speed(tmp_path: Path) -> None:
    live_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "live_cycle_events.csv").write_text(
        "event_utc,cycle_run_id,event_type,supplier_id,f061_run_id,status,rows,notes\n"
        "2026-04-30T20:00:00Z,fpm_live,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,5,pending_after=95\n"
        "2026-04-30T21:00:00Z,fpm_live,scanner_chunk,entertainment_trading,"
        "fpm_entertainment_trading_20260430T151417Z,success,5,pending_after=55\n",
        encoding="utf-8",
    )

    eta = _price_list_live_eta(tmp_path, "fpm_entertainment_trading_20260430T151417Z", 80)

    assert round(float(eta["rows_per_hour"]), 1) == 45.0
    assert eta["eta_label"] == "1h 47m"
    assert eta["sample_rows"] == 45


def test_price_list_live_result_counts_read_current_run_state(tmp_path: Path) -> None:
    inbox_dir = tmp_path / "out" / "systems" / "F" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "run_id": "fpm_entertainment_trading_20260430T151417Z",
                "run_status": "running",
                "source_url": "",
                "source_file_path": "Stocklist.xlsx",
                "source_seen_at_utc": "2026-04-30T14:13:50Z",
                "normalized_utc": "2026-04-30T15:14:17Z",
                "total_rows": "20083",
                "pending_rows": "19693",
                "done_rows": "390",
                "failed_rows": "383",
                "held_rows": "0",
                "next_row_index": "1",
                "updated_at_utc": "2026-04-30T20:09:59Z",
                "completed_at_utc": "",
            }
        ]
    ).to_csv(inbox_dir / "supplier_price_list_run_state.csv", index=False)
    screening_dir = tmp_path / "out" / "systems" / "F" / "live"
    screening_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"run_id": "fpm_entertainment_trading_20260430T151417Z", "row_status": "pass", "pf": "PASS"},
            {"run_id": "fpm_entertainment_trading_20260430T151417Z", "row_status": "timeout", "pf": "FAIL"},
            {"run_id": "fpm_entertainment_trading_20260430T151417Z", "row_status": "rescan", "pf": "RESCAN"},
            {"run_id": "other_run", "row_status": "rescan"},
        ]
    ).to_csv(screening_dir / "f_screening_row_state_live.csv", index=False)

    counts = _price_list_live_result_counts(tmp_path, "fpm_entertainment_trading_20260430T151417Z")

    assert counts == {"pass": 1, "fail": 1, "rescan": 1, "done": 390, "pending": 19693, "held": 0}


def test_price_list_live_counts_are_scoped_to_active_run(tmp_path: Path) -> None:
    inbox_dir = tmp_path / "out" / "systems" / "F" / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "dhb",
                "supplier_name": "DHB",
                "run_id": "dhb_run",
                "run_status": "running",
                "total_rows": "959",
                "pending_rows": "914",
                "done_rows": "45",
                "failed_rows": "45",
                "held_rows": "0",
            },
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "run_id": "stax_run",
                "run_status": "paused",
                "total_rows": "24205",
                "pending_rows": "0",
                "done_rows": "3943",
                "failed_rows": "3616",
                "held_rows": "20262",
            },
        ]
    ).to_csv(inbox_dir / "supplier_price_list_run_state.csv", index=False)
    pd.DataFrame(
        [
            {"run_id": "dhb_run", "scan_status": "pending"},
            {"run_id": "dhb_run", "scan_status": "pending"},
            {"run_id": "dhb_run", "scan_status": "done"},
            {"run_id": "stax_run", "scan_status": "held"},
            {"run_id": "stax_run", "scan_status": "held"},
        ]
    ).to_csv(inbox_dir / "supplier_price_list_active_run.csv", index=False)

    active_counts = _price_list_active_run_counts(tmp_path, "dhb_run")
    result_counts = _price_list_live_result_counts(tmp_path, "dhb_run")

    assert active_counts == {"total": 3, "pending": 2, "done": 1, "held": 0}
    assert result_counts["done"] == 45
    assert result_counts["pending"] == 914
    assert result_counts["held"] == 0


def test_price_list_recovery_counts_read_legacy_import_progress(tmp_path: Path) -> None:
    progress_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    progress_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "imported_at_utc": "2026-04-30T14:50:01Z",
                "supplier_id": "entertainment_trading",
                "batch_id": "entertainment_trading_source",
                "legacy_run_id": "stocklist_supplier_webscrape_reset_20260429T164504Z",
                "legacy_total_rows": "21817",
                "legacy_pending_rows": "20116",
                "legacy_done_rows": "1701",
                "legacy_failed_rows": "1584",
                "pending_source_rows": "20116",
                "pending_matched_rows": "20083",
                "pending_held_rows": "33",
                "pending_unmatched_rows": "0",
                "manager_valid_rows": "20083",
                "manager_scan_now_rows": "20083",
                "manager_recovery_skipped_rows": "22366",
                "manager_held_rows": "268",
                "legacy_active_run_path": "active_run.csv",
                "legacy_run_state_path": "run_state.csv",
            }
        ]
    ).to_csv(progress_dir / "f061_recovery_progress.csv", index=False)

    counts = _price_list_recovery_counts(tmp_path, "entertainment_trading")

    assert counts == {
        "legacy_done": 1701,
        "legacy_pass": 117,
        "legacy_fail": 1584,
        "legacy_pending": 20116,
        "matched_pending": 20083,
    }


def test_price_list_queue_control_helper_prioritises_supplier_and_rebuilds_dashboard(tmp_path: Path) -> None:
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"
    test_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "stax",
                "supplier_name": "Stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_url": "https://example.test/stax.csv",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "stax",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "1",
                "manual_request_required_flag": "0",
                "priority_band": "api",
                "active_flag": "1",
                "notes": "test",
            },
            {
                "supplier_id": "heo",
                "supplier_name": "Heo",
                "source_type": "api_pull",
                "source_subtype": "api",
                "source_url": "https://example.test/heo",
                "source_folder_path": "",
                "existing_supplier_config_path": "",
                "converter_id": "heo",
                "normal_refresh_days": "1",
                "minimum_rescan_days": "1",
                "large_file_flag": "0",
                "manual_request_required_flag": "0",
                "priority_band": "api",
                "active_flag": "1",
                "notes": "test",
            },
        ],
        columns=SUPPLIER_REGISTRY_COLUMNS,
    ).to_csv(test_dir / "supplier_registry.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "source_type": "api_pull",
                "source_subtype": "csv_link",
                "source_received_at_utc": "2026-04-30T10:00:00Z",
                "source_file_path": "stax.csv",
                "source_file_hash": "hash_s",
                "converted_file_path": "stax_converted.csv",
                "source_row_count": "2",
                "valid_row_count": "2",
                "held_row_count": "0",
                "new_row_count": "2",
                "changed_row_count": "0",
                "eligible_row_count": "2",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:01:00Z",
            },
            {
                "batch_id": "heo_batch",
                "supplier_id": "heo",
                "source_type": "api_pull",
                "source_subtype": "api",
                "source_received_at_utc": "2026-04-30T10:05:00Z",
                "source_file_path": "heo.csv",
                "source_file_hash": "hash_h",
                "converted_file_path": "heo_converted.csv",
                "source_row_count": "1",
                "valid_row_count": "1",
                "held_row_count": "0",
                "new_row_count": "1",
                "changed_row_count": "0",
                "eligible_row_count": "1",
                "skipped_cooldown_row_count": "0",
                "batch_status": "imported_from_source",
                "status_reason": "ready_source_file_imported",
                "updated_at_utc": "2026-04-30T10:06:00Z",
            },
        ],
        columns=PRICE_LIST_BATCH_COLUMNS,
    ).to_csv(test_dir / "price_list_batches.csv", index=False)
    pd.DataFrame(
        [
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "row_key": "s1",
                "supplier_sku": "S1",
                "supplier_title": "Stax 1",
                "barcode": "5000000000001",
                "unit_cost": "1.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "s1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "stax_batch",
                "supplier_id": "stax",
                "row_key": "s2",
                "supplier_sku": "S2",
                "supplier_title": "Stax 2",
                "barcode": "5000000000002",
                "unit_cost": "2.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "s2",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
            {
                "batch_id": "heo_batch",
                "supplier_id": "heo",
                "row_key": "h1",
                "supplier_sku": "H1",
                "supplier_title": "Heo 1",
                "barcode": "6000000000001",
                "unit_cost": "3.00",
                "currency": "GBP",
                "vat_rate": "20",
                "source_row_hash": "h1",
                "row_change_status": "new",
                "scan_eligibility": "scan_now",
                "eligibility_reason": "valid",
                "last_memory_key": "",
                "cooldown_until_utc": "",
            },
        ],
        columns=BATCH_ROW_COLUMNS,
    ).to_csv(test_dir / "batch_rows.csv", index=False)

    result = apply_price_list_queue_control(
        root=tmp_path,
        supplier_id="heo",
        control_state="prioritised",
        priority_rank="1",
        reason="operator test",
        observed_utc="2026-04-30T12:00:00Z",
    )

    dashboard = pd.read_csv(test_dir / "status_dashboard.csv", dtype=str).fillna("")
    decisions = pd.read_csv(test_dir / "manager_decisions.csv", dtype=str).fillna("")
    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    by_supplier = dashboard.set_index("supplier_id")
    assert result["status"] == "success"
    assert result["decision"]["selected_supplier_id"] == "heo"
    assert decisions.iloc[-1]["reason_code"] == "operator_prioritised_supplier"
    assert by_supplier.loc["heo", "queue_position"] == "1"
    assert by_supplier.loc["heo", "queue_state"] == "Recommended"
    assert by_supplier.loc["heo", "control_state"] == "Prioritised #1"
    assert preview.iloc[-1]["supplier_id"] == "heo"
    assert preview.iloc[-1]["technical_ready_flag"] == "1"
    assert preview.iloc[-1]["approval_state"] == "required"
    assert preview.iloc[-1]["live_apply_allowed"] == "0"


def test_price_list_handoff_approval_helper_records_exact_batch_and_rebuilds_preview(tmp_path: Path) -> None:
    test_price_list_queue_control_helper_prioritises_supplier_and_rebuilds_dashboard(tmp_path)
    test_dir = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "test_mode"

    approve = apply_price_list_handoff_approval(
        root=tmp_path,
        supplier_id="heo",
        batch_id="heo_batch",
        approval_state="approved",
        reason="operator ui test approval",
        observed_utc="2026-04-30T12:10:00Z",
    )

    approvals = pd.read_csv(test_dir / "f061_handoff_approvals.csv", dtype=str).fillna("")
    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    assert approve["status"] == "success"
    assert approve["approval"]["approval_state"] == "approved"
    assert approve["handoff"]["approval_state"] == "approved"
    assert approve["handoff"]["technical_ready_flag"] == "1"
    assert approve["handoff"]["live_apply_allowed"] == "1"
    assert approvals.iloc[-1]["supplier_id"] == "heo"
    assert approvals.iloc[-1]["batch_id"] == "heo_batch"
    assert approvals.iloc[-1]["approved_by"] == "operator_ui"
    assert preview.iloc[-1]["approval_id"] == approve["approval"]["approval_id"]

    revoke = apply_price_list_handoff_approval(
        root=tmp_path,
        supplier_id="heo",
        batch_id="heo_batch",
        approval_state="revoked",
        reason="operator ui test revoke",
        observed_utc="2026-04-30T12:15:00Z",
    )

    preview = pd.read_csv(test_dir / "f061_handoff_preview.csv", dtype=str).fillna("")
    assert revoke["handoff"]["approval_state"] == "revoked"
    assert revoke["handoff"]["live_apply_allowed"] == "0"
    assert preview.iloc[-1]["approval_state"] == "revoked"


def test_copy_value_html_builds_click_to_copy_button() -> None:
    html = _copy_value_html("ABC-123")
    assert "navigator.clipboard.writeText(" in html
    assert "ABC-123" in html
    assert ">ABC-123<" in html


def test_reorder_draft_uses_stable_identity_and_clears_after_send() -> None:
    row = {
        "seller_sku": "SKU-KEEP",
        "asin": "ASIN-KEEP",
        "supplier_name": "Alpha",
        "title": "Draft Product",
        "send": False,
        "snze": False,
        "disc": False,
        "drop": False,
        "order_qty": "",
        "confirmed_price": "",
        "snooze_date": "",
    }
    identity = _reorder_row_identity(row)
    drafts = {
        identity: {
            "send": True,
            "snze": True,
            "disc": False,
            "drop": False,
            "order_qty": "12",
            "confirmed_price": "4.50",
            "snooze_date": "2026-04-20",
        }
    }

    applied_identity, merged = _apply_reorder_draft(row, drafts)

    assert applied_identity == identity
    assert merged["send"] is True
    assert merged["snze"] is True
    assert merged["order_qty"] == "12"
    assert merged["confirmed_price"] == "4.50"
    assert _extract_reorder_draft(merged)["snooze_date"] == "2026-04-20"

    row_key = _reorder_widget_key(merged)
    session_state = {
        "o_reorder_drafts": {identity: _extract_reorder_draft(merged)},
        f"qty_{row_key}": "12",
        f"price_{row_key}": "4.50",
        f"send_{row_key}": True,
        f"snze_{row_key}": True,
        f"snooze_{row_key}": "2026-04-20",
    }
    _clear_reorder_drafts(session_state, [merged])

    assert identity not in session_state["o_reorder_drafts"]
    assert f"qty_{row_key}" not in session_state
    assert f"price_{row_key}" not in session_state
    assert f"send_{row_key}" not in session_state


def test_ui_loads_decision_event_inbox_dataset(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_decision_events",
        [
            {
                "event_utc": "2026-04-17T10:00:00Z",
                "event_id": "evt-1",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "5.5",
                "confirmed_qty": "12",
                "snooze_until_utc": "",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Alpha",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    assert "restock_decision_events" in datasets
    assert len(datasets["restock_decision_events"]) == 1
    assert "product_db_operator_view" in datasets
    assert "product_db_edit_events" in datasets
    assert "product_db_edit_holds" in datasets
    assert "amazon_listing_drafts_live" in datasets
    assert "amazon_listing_preview_events" in datasets
    assert "amazon_listing_preview_issues_live" in datasets
    assert "amazon_listing_holds_live" in datasets


def test_build_amazon_listing_draft_display_df_merges_hold_reason(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "amazon_listing_drafts_live",
        [
            {
                "observed_utc": "2026-05-01T10:50:00Z",
                "draft_id": "draft-1",
                "supplier_id": "supplier_a",
                "supplier_name": "Supplier A",
                "source_run_id": "run-1",
                "review_snapshot_id": "snap-1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-1",
                "supplier_sku": "SUP-1",
                "barcode": "5012345678901",
                "asin": "B000000001",
                "amazon_title": "Review Product",
                "supplier_cost_gbp": "",
                "expected_seller_sku": "NP-SUP-ABC12345",
                "sku_reservation_status": "reserved",
                "sku_reservation_reason": "reserved",
                "marketplace_id": "A1F83G8C2ARO7P",
                "product_type": "",
                "condition_type": "new_new",
                "fulfillment_channel": "AFN",
                "starting_price_gbp": "",
                "starting_quantity": "0",
                "listing_mode": "existing_asin_offer",
                "draft_status": "blocked_missing_local_data",
                "block_reason": "missing_local_data:supplier_cost_gbp,product_type,starting_price_gbp",
                "amazon_preview_status": "not_run",
                "amazon_preview_issue_count": "0",
                "amazon_submission_status": "not_submitted",
                "amazon_submission_id": "",
                "updated_at_utc": "2026-05-01T10:50:00Z",
                "source_intake_id": "intake-1",
            }
        ],
    )
    _write_f_contract_rows(
        tmp_path,
        "amazon_listing_holds_live",
        [
            {
                "hold_utc": "2026-05-01T10:50:00Z",
                "hold_id": "hold-1",
                "hold_stage": "draft_builder",
                "supplier_id": "supplier_a",
                "active_run_id": "run-1",
                "candidate_id": "cand-1",
                "asin": "B000000001",
                "expected_seller_sku": "NP-SUP-ABC12345",
                "hold_reason": "missing_local_data:supplier_cost_gbp,product_type,starting_price_gbp",
                "hold_note": "Draft is blocked",
                "source_reference": "test",
                "intake_id": "intake-1",
                "draft_id": "draft-1",
                "marketplace_id": "A1F83G8C2ARO7P",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    display_df = build_amazon_listing_draft_display_df(datasets)

    assert len(display_df.index) == 1
    assert display_df.iloc[0]["expected_seller_sku"] == "NP-SUP-ABC12345"
    assert display_df.iloc[0]["hold_reason"] == "missing_local_data:supplier_cost_gbp,product_type,starting_price_gbp"


def test_submit_amazon_listing_draft_approval_marks_ready_for_preview(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "amazon_listing_drafts_live",
        [
            {
                "observed_utc": "2026-05-01T10:50:00Z",
                "draft_id": "draft-approve",
                "supplier_id": "supplier_a",
                "supplier_name": "Supplier A",
                "source_run_id": "run-1",
                "review_snapshot_id": "snap-1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-1",
                "supplier_sku": "SUP-1",
                "barcode": "5012345678901",
                "asin": "B000000001",
                "amazon_title": "Review Product",
                "supplier_cost_gbp": "3.50",
                "expected_seller_sku": "NP-SUP-ABC12345",
                "sku_reservation_status": "reserved",
                "sku_reservation_reason": "reserved",
                "marketplace_id": "A1F83G8C2ARO7P",
                "product_type": "PRODUCT",
                "condition_type": "new_new",
                "fulfillment_channel": "AFN",
                "starting_price_gbp": "9.99",
                "starting_quantity": "0",
                "listing_mode": "existing_asin_offer",
                "draft_status": "ready_for_listing_approval",
                "block_reason": "",
                "amazon_preview_status": "not_run",
                "amazon_preview_issue_count": "0",
                "amazon_submission_status": "not_submitted",
                "amazon_submission_id": "",
                "updated_at_utc": "2026-05-01T10:50:00Z",
                "listing_approval_status": "pending_operator_approval",
            }
        ],
    )

    ok, status, row = submit_amazon_listing_draft_approval(
        root=tmp_path,
        draft_id="draft-approve",
        actor="tester",
    )

    assert ok is True
    assert status == "approved_for_preview"
    assert row["draft_status"] == "ready_for_amazon_preview"
    drafts = load_operator_datasets(root=tmp_path)["amazon_listing_drafts_live"]
    assert drafts.iloc[0]["listing_approval_status"] == "approved_for_preview"
    events = load_operator_datasets(root=tmp_path)["amazon_listing_draft_events"]
    assert len(events.index) == 1
    assert events.iloc[0]["event_type"] == "listing_draft_approved"


def test_submit_amazon_listing_draft_approval_refuses_blocked_draft(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "amazon_listing_drafts_live",
        [
            {
                "observed_utc": "2026-05-01T10:50:00Z",
                "draft_id": "draft-blocked",
                "candidate_id": "cand-1",
                "asin": "B000000001",
                "expected_seller_sku": "NP-SUP-ABC12345",
                "marketplace_id": "A1F83G8C2ARO7P",
                "draft_status": "blocked_missing_local_data",
                "block_reason": "missing_local_data:product_type",
            }
        ],
    )

    ok, status, _ = submit_amazon_listing_draft_approval(root=tmp_path, draft_id="draft-blocked")

    assert ok is False
    assert status == "draft_blocked"
    events = load_operator_datasets(root=tmp_path)["amazon_listing_draft_events"]
    assert len(events.index) == 0


def test_run_amazon_listing_preview_for_draft_calls_f093(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run_amazon_listing_preview(**kwargs):
        captured.update(kwargs)
        return {
            "eligible_rows": 1,
            "attempted_rows": 1,
            "passed_rows": 1,
            "rejected_rows": 0,
            "failed_rows": 0,
        }

    monkeypatch.setattr(
        "scripts.flows.F.F093_run_amazon_listing_preview.run_amazon_listing_preview",
        fake_run_amazon_listing_preview,
    )

    result = run_amazon_listing_preview_for_draft(root=tmp_path, draft_id="draft-1")

    assert result["passed_rows"] == 1
    assert captured["root"] == tmp_path
    assert captured["draft_ids"] == ["draft-1"]
    assert captured["run_preview"] is True
    assert captured["max_rows"] == 1


def test_build_test_orders_df_groups_latest_sample_submissions(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-17T09:00:00Z",
                "seller_sku": "SKU-T1",
                "asin": "ASIN-T1",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "2.5",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "5.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "roi_at_market_price_pct": "30",
                "source_inventory_asof": "2026-04-17T09:00:00Z",
                "source_velocity_asof": "2026-04-17",
                "source_performance_asof": "2026-04-17",
                "title": "Alpha Test Item",
                "supplier_sku": "ALPHA-SUP-1",
                "barcode": "123456",
            },
            {
                "asof_utc": "2026-04-17T09:00:00Z",
                "seller_sku": "SKU-T2",
                "asin": "ASIN-T2",
                "supplier_code": "SUP-B",
                "supplier_name": "Beta",
                "sale_status": "active",
                "available_now": "0",
                "total_quantity_now": "0",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "3.0",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "6.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "roi_at_market_price_pct": "30",
                "source_inventory_asof": "2026-04-17T09:00:00Z",
                "source_velocity_asof": "2026-04-17",
                "source_performance_asof": "2026-04-17",
                "title": "Beta Test Item",
                "supplier_sku": "BETA-SUP-2",
                "barcode": "654321",
            },
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_decision_events",
        [
            {
                "event_utc": "2026-04-17T10:00:00Z",
                "event_id": "evt-old",
                "seller_sku": "SKU-T1",
                "asin": "ASIN-T1",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "2.4",
                "confirmed_qty": "10",
                "snooze_until_utc": "",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Alpha",
            },
            {
                "event_utc": "2026-04-17T10:05:00Z",
                "event_id": "evt-new",
                "seller_sku": "SKU-T1",
                "asin": "ASIN-T1",
                "action": "approve_full_restock",
                "confirmed_unit_cost": "2.5",
                "confirmed_qty": "12",
                "snooze_until_utc": "",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Alpha",
            },
            {
                "event_utc": "2026-04-17T10:06:00Z",
                "event_id": "evt-beta",
                "seller_sku": "SKU-T2",
                "asin": "ASIN-T2",
                "action": "approve_test_restock",
                "confirmed_unit_cost": "3.0",
                "confirmed_qty": "8",
                "snooze_until_utc": "",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Beta",
            },
            {
                "event_utc": "2026-04-17T10:07:00Z",
                "event_id": "evt-ignore",
                "seller_sku": "SKU-X",
                "asin": "ASIN-X",
                "action": "snooze",
                "confirmed_unit_cost": "",
                "confirmed_qty": "",
                "snooze_until_utc": "2026-04-21T00:00:00Z",
                "decision_note": "",
                "actor": "operator_ui",
                "cost_mode": "live",
                "source_reference": "o_ui_supplier_batch:Other",
            },
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    test_orders_df = build_test_orders_df(datasets)
    assert len(test_orders_df) == 2
    alpha = test_orders_df[test_orders_df["seller_sku"] == "SKU-T1"].iloc[0]
    beta = test_orders_df[test_orders_df["seller_sku"] == "SKU-T2"].iloc[0]
    assert alpha["supplier_name"] == "Alpha"
    assert alpha["title"] == "Alpha Test Item"
    assert alpha["supply_code"] == "ALPHA-SUP-1"
    assert alpha["ordered_qty"] == "12"
    assert alpha["ordered_unit_cost_gbp"] == "2.5"
    assert alpha["line_value_gbp"] == "30"
    assert beta["supplier_name"] == "Beta"
    assert beta["ordered_qty"] == "8"
    assert beta["action"] == "approve_test_restock"


def test_build_po_draft_review_df_presents_operator_fields() -> None:
    datasets = {
        "purchase_orders_live": pd.DataFrame(
            [
                {
                    "po_id": "PO-DRAFT-1",
                    "supplier_name": "ABGee",
                    "po_status": "draft",
                    "total_lines": "1",
                    "total_units": "2",
                    "total_value_gbp": "15.18",
                }
            ]
        ),
        "purchase_order_lines_live": pd.DataFrame(
            [
                {
                    "po_id": "PO-DRAFT-1",
                    "po_line_id": "PO-DRAFT-1-L001",
                    "seller_sku": "12-749B-9EB5",
                    "asin": "B084HZRR8G",
                    "title": "Leatherface Funko Pop",
                    "ordered_qty": "2",
                    "ordered_unit_cost_gbp": "7.59",
                    "supplier_sku": "985 49830",
                    "barcode": "889698498302",
                    "source_bridge_reference": "legacy_purchase_list:sheet:Purchase List:row3",
                }
            ]
        ),
        "product_db_operator_view": pd.DataFrame(
            [
                {
                    "seller_sku": "12-749B-9EB5",
                    "asin": "B084HZRR8G",
                    "main_image": "https://example.com/leatherface.jpg",
                }
            ]
        ),
    }

    review_df = build_po_draft_review_df(datasets)

    assert len(review_df) == 1
    row = review_df.iloc[0]
    assert row["supplier_name"] == "ABGee"
    assert row["seller_sku"] == "12-749B-9EB5"
    assert row["ordered_qty"] == "2"
    assert row["ordered_unit_cost_gbp"] == "7.59"
    assert row["line_value_gbp"] == "15.18"
    assert row["supplier_sku"] == "985 49830"
    assert row["barcode"] == "889698498302"
    assert row["main_image"] == "https://example.com/leatherface.jpg"
    assert row["source_label"] == "Google Sheet bridge"


def test_ui_loads_current_o_outputs_and_builds_recommendation_display(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-1",
                "asin": "ASIN-1",
                "title": "Example Product",
                "main_image": "https://example.com/image.jpg",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "12",
                "suggested_unit_cost_gbp": "5",
                "suggested_market_price_gbp": "8",
                "expected_forward_roi_pct": "60",
                "expected_forward_profit_per_unit_gbp": "3",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "confidence_note": "",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "snooze_until_utc": "",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    assert "restock_review_queue" in datasets
    assert len(datasets["restock_review_queue"]) == 1

    display_df = build_recommendations_display_df(datasets)
    assert len(display_df) == 1
    row = display_df.iloc[0]
    assert row["title"] == "Example Product"
    assert row["main_image"] == "https://example.com/image.jpg"
    assert row["seller_sku"] == "SKU-1"
    assert row["suggested_action"] == "full_restock"
    assert row["recommendation_reason"] == "ROI_OK"
    assert row["cost_mode"] == "test"
    assert row["recommendation_basis"] == "test_cost_snapshot"
    assert row["queue_status"] == "needs_review"

    card_html = _render_recommendation_cards(display_df)
    assert "Example Product" in card_html
    assert "SKU: SKU-1" in card_html
    assert "ASIN: ASIN-1" in card_html
    assert "https://example.com/image.jpg" in card_html


def test_ui_recommendation_cards_render_backtest_section_from_source_view(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-BT1",
                "asin": "ASIN-BT1",
                "title": "Backtest Product",
                "main_image": "",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "8",
                "suggested_unit_cost_gbp": "4.2",
                "suggested_market_price_gbp": "7.9",
                "expected_forward_roi_pct": "40",
                "expected_forward_profit_per_unit_gbp": "1.5",
                "days_cover_available_only": "3",
                "days_cover_total_pipeline": "3",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-BT1",
                "asin": "ASIN-BT1",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "3",
                "total_quantity_now": "3",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "4.2",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "7.9",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "roi_at_market_price_pct": "40",
                "source_inventory_asof": "2026-04-03T09:00:00Z",
                "source_velocity_asof": "2026-04-03",
                "source_performance_asof": "2026-04-03",
                "backtest_policy_id": "policy_live_default",
                "backtest_history_confidence": "high",
                "backtest_market_viability_score": "81.2",
                "backtest_exit_risk_score": "22.0",
                "backtest_estimated_total_profit_gbp": "250.0",
                "backtest_estimated_monthly_profit_gbp": "35.7",
                "backtest_capital_lockup_days": "18",
                "backtest_sellable_ceiling_zone": "normal",
                "backtest_amazon_risk_level": "low",
                "backtest_compression_risk_level": "medium",
                "backtest_recommendation": "Normal fit",
                "backtest_manual_review_reason": "",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    display_df = build_recommendations_display_df(datasets)
    row = display_df.iloc[0]
    assert row["backtest_recommendation"] == "Normal fit"
    assert row["backtest_estimated_monthly_profit_gbp"] == "35.7"
    assert row["backtest_market_viability_score"] == "81.2"

    card_html = _render_recommendation_cards(display_df)
    assert "Backtest:" in card_html
    assert "Normal fit" in card_html
    assert "Monthly:" in card_html
    assert "Viability:" in card_html


def test_ui_decision_submission_writes_to_decision_inbox(tmp_path: Path) -> None:
    out_row = submit_decision_event(
        root=tmp_path,
        seller_sku="SKU-2",
        asin="ASIN-2",
        action="snooze",
        snooze_until_utc="2026-04-10T00:00:00Z",
        decision_note="wait for supplier confirmation",
        actor="tester",
        cost_mode="test",
        source_reference="o_ui_test",
    )

    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-decision-")
    assert row["seller_sku"] == "SKU-2"
    assert row["action"] == "snooze"
    assert row["snooze_until_utc"] == "2026-04-10T00:00:00Z"
    assert row["actor"] == "tester"
    assert row["source_reference"] == "o_ui_test"
    assert out_row["event_id"] == row["event_id"]


def test_ui_receiving_submission_writes_to_receiving_inbox(tmp_path: Path) -> None:
    out_row = submit_receiving_event(
        root=tmp_path,
        po_id="PO-1",
        po_line_id="PO-1-L001",
        seller_sku="SKU-REC",
        received_qty="3",
        warehouse_ref="WH-A",
        note="partial receive",
        actor="tester",
    )

    inbox_path = tmp_path / get_o_output_contract("receiving_events_inbox").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-receive-")
    assert row["po_id"] == "PO-1"
    assert row["po_line_id"] == "PO-1-L001"
    assert row["seller_sku"] == "SKU-REC"
    assert row["received_qty"] == "3"
    assert row["actor"] == "tester"
    assert out_row["event_id"] == row["event_id"]


def test_ui_handoff_submission_writes_to_handoff_inbox(tmp_path: Path) -> None:
    out_row = submit_send_handoff_event(
        root=tmp_path,
        po_id="PO-2",
        po_line_id="PO-2-L001",
        seller_sku="SKU-HND",
        handoff_qty="2",
        shipment_ref="SHIP-1",
        handoff_status="handoff_closed",
        note="close line",
        actor="tester",
    )

    inbox_path = tmp_path / get_o_output_contract("send_to_amazon_handoff_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-handoff-")
    assert row["po_id"] == "PO-2"
    assert row["po_line_id"] == "PO-2-L001"
    assert row["seller_sku"] == "SKU-HND"
    assert row["handoff_qty"] == "2"
    assert row["shipment_ref"] == "SHIP-1"
    assert row["handoff_status"] == "handoff_closed"
    assert out_row["event_id"] == row["event_id"]


def test_ui_submission_targets_are_inbox_only_and_no_direct_apply_imports(tmp_path: Path) -> None:
    targets = get_submission_targets(root=tmp_path)
    assert set(targets.keys()) == {"decision_events", "receiving_events", "send_handoff_events", "feeder_review_events"}
    for target in targets.values():
        assert "\\inbox\\" in str(target)

    module_text = (ROOT / "scripts" / "flows" / "O" / "O400_operator_ui.py").read_text(encoding="utf-8")
    assert "O010_apply_restock_decisions" not in module_text
    assert "O210_apply_receiving_events" not in module_text
    assert "O310_close_send_to_amazon_handoff" not in module_text


def test_feeder_review_asin_padding_and_url_builder() -> None:
    assert _pad_asin_to_10("B006SYGN9O") == "B006SYGN9O"
    assert _pad_asin_to_10("6SYGN9O") == "0006SYGN9O"
    assert _amazon_dp_url("6SYGN9O") == "https://www.amazon.co.uk/dp/0006SYGN9O"


def test_feeder_review_window_shows_only_first_10_undecided_rows(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for idx in range(12):
        rows.append(
            {
                "observed_utc": "2026-04-22T14:43:41Z",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": str(100 - idx),
                "candidate_id": f"cand-{idx}",
                "supplier_sku": f"SKU-{idx}",
                "asin": f"B0000000{idx:02d}"[-10:],
                "title": f"Product {idx}",
                "brand": "Brand",
                "main_rank": str(idx + 1),
                "screening_status_reason": "PASS",
                "backtest_decision_state": "pass",
                "expected_units_next_30d": "50",
                "sales_lower_30d": "30",
                "sales_upper_30d": "70",
                "expected_profit_next_30d_gbp": "25",
                "estimated_monthly_profit_gbp": "25",
                "profit_per_unit_30d_gbp": "2.5",
                "conservative_starter_qty": "8",
                "pass_reason_summary": "profit_floor_met",
                "commercial_note": "Looks fine",
            }
        )
    pd.DataFrame(rows).to_csv(report_path, index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-04-22T15:00:00Z",
                "event_id": "evt-1",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-0",
                "supplier_sku": "SKU-0",
                "asin_raw": "B000000000",
                "asin_padded": "B000000000",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000000",
                "review_decision": "pass",
                "review_note": "approved",
                "actor": "tester",
                "source_reference": "test",
                "title": "Product 0",
                "brand": "Brand",
                "main_rank": "1",
                "review_priority_score": "100",
            }
        ],
    )

    window_df, meta = build_feeder_review_window_df("passes", root=tmp_path)

    assert len(window_df.index) == 10
    assert "cand-0" not in set(window_df["candidate_id"])
    assert window_df.iloc[0]["candidate_id"] == "cand-1"
    assert meta["undecided_rows"] == 11
    assert meta["visible_rows"] == 10


def test_restock_scanner_summary_counts_waiting_supplier_intake_rows(tmp_path: Path) -> None:
    reports_dir = tmp_path / "out" / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-06-03T10:00:00Z",
                "metric": "active_supplier_id",
                "value": "stocklist_supplier",
            },
            {
                "observed_utc": "2026-06-03T10:00:00Z",
                "metric": "active_run_id",
                "value": "run-1",
            },
            {
                "observed_utc": "2026-06-03T10:00:00Z",
                "metric": "source_seen_at_utc",
                "value": "2026-06-03T09:30:00Z",
            },
        ]
    ).to_csv(reports_dir / "f_live_price_file_review_summary_latest.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "100",
                "candidate_id": "pass-1",
                "supplier_sku": "SKU-PASS-1",
                "asin": "B000000001",
                "title": "Already reviewed scanner product",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "90",
                "candidate_id": "pass-2",
                "supplier_sku": "SKU-PASS-2",
                "asin": "B000000002",
                "title": "Waiting scanner product 1",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "80",
                "candidate_id": "pass-3",
                "supplier_sku": "SKU-PASS-3",
                "asin": "B000000003",
                "title": "Waiting scanner product 2",
            },
        ]
    ).to_csv(reports_dir / "f_live_price_file_pass_review_latest.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "near_batch_001",
                "review_priority_score": "70",
                "candidate_id": "manual-1",
                "supplier_sku": "SKU-MANUAL-1",
                "asin": "B000000004",
                "title": "Waiting manual scanner product",
                "near_miss_type": "manual_review",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "near_batch_001",
                "review_priority_score": "60",
                "candidate_id": "near-1",
                "supplier_sku": "SKU-NEAR-1",
                "asin": "B000000005",
                "title": "Waiting close-call scanner product",
                "near_miss_type": "",
            },
        ]
    ).to_csv(reports_dir / "f_live_price_file_near_miss_review_latest.csv", index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-06-03T10:15:00Z",
                "event_id": "evt-pass-1",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "pass-1",
                "supplier_sku": "SKU-PASS-1",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "pass",
                "review_note": "already checked",
                "actor": "tester",
                "source_reference": "test",
                "title": "Already reviewed scanner product",
            }
        ],
    )

    summary = _build_restock_scanner_check_summary(tmp_path)

    assert summary["waiting_count"] == 4
    assert summary["supplier_count"] == 1
    assert summary["suggested_lane"] == "Passes"
    assert summary["suggested_snapshot"] == "latest"
    assert summary["lane_counts"] == {"Passes": 2, "Manual review": 1, "Near misses": 1}
    assert _restock_scanner_lane_text(summary["lane_counts"]) == "2 clean passes, 1 manual check, 1 close call"


def test_feeder_review_submission_writes_f_inbox_events(tmp_path: Path) -> None:
    out = submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-10",
                "supplier_sku": "SKU-10",
                "asin": "6SYGN9O",
                "title": "Example title",
                "brand": "Brand",
                "main_rank": "5000",
                "review_priority_score": "123.4",
                "review_decision": "pass",
                "review_reason_code": "wrong product",
                "review_note": "Good enough for a first test",
                "country_of_origin": "gb",
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "gbp",
                "price_includes_tax": "1",
                "starting_price_gbp": "12.34",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )

    inbox_path = tmp_path / get_f_output_contract("feeder_review_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")

    assert out["events_applied"] == 1
    assert len(inbox_df.index) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-f-review-")
    assert row["candidate_id"] == "cand-10"
    assert row["review_decision"] == "pass"
    assert row["asin_padded"] == "0006SYGN9O"
    assert row["amazon_dp_url"] == "https://www.amazon.co.uk/dp/0006SYGN9O"
    assert row["review_reason_code"] == "wrong_product"
    assert row["review_reason_label"] == "Wrong product"
    assert row["review_note"] == "Good enough for a first test"
    assert row["source_reference"] == "o_ui_feeder_review:test"
    assert row["country_of_origin"] == "GB"
    assert row["product_tax_code"] == "A_GEN_STANDARD"
    assert row["currency_code"] == "GBP"
    assert row["price_includes_tax"] == "1"
    assert row["starting_price_gbp"] == "12.34"


def test_feeder_review_submission_accepts_rescan_decision(tmp_path: Path) -> None:
    out = submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_test",
                "review_pack_type": "near_misses",
                "review_batch_id": "near_miss_batch_001",
                "candidate_id": "bliss-row-1",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                "brand": "Yu-Gi-Oh!",
                "main_rank": "43073",
                "review_priority_score": "18.6",
                "review_decision": "Re scan",
                "review_note": "Needs fresh scanner evidence before ordering",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )

    inbox_path = tmp_path / get_f_output_contract("feeder_review_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")

    assert out["events_applied"] == 1
    assert out["skipped_rows"] == []
    assert inbox_df.iloc[0]["review_decision"] == "rescan"
    assert inbox_df.iloc[0]["supplier_sku"] == "KONKKS"
    assert build_product_listing_profile_review_df(root=tmp_path).empty


def test_feeder_review_pass_without_country_of_origin_routes_to_profile_review(tmp_path: Path) -> None:
    out = submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-10",
                "supplier_sku": "SKU-10",
                "asin": "B000000001",
                "review_decision": "pass",
                "review_note": "Good enough for a first test",
                "starting_price_gbp": "12.34",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )

    inbox_path = tmp_path / get_f_output_contract("feeder_review_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")

    assert out["events_applied"] == 1
    assert out["skipped_rows"] == []
    assert len(inbox_df.index) == 1
    assert inbox_df.iloc[0]["review_decision"] == "pass"
    pending = build_product_listing_profile_review_df(root=tmp_path)
    assert len(pending.index) == 1
    assert pending.iloc[0]["candidate_id"] == "cand-10"


def test_product_listing_profile_requires_profile_fields(tmp_path: Path) -> None:
    out = submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-11",
                "supplier_sku": "SKU-11",
                "asin": "B000000011",
                "review_decision": "pass",
                "review_note": "Good enough for a first test",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )
    assert out["events_applied"] == 1

    result = submit_amazon_listing_profile_batch(
        root=tmp_path,
        profile_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-11",
                "supplier_sku": "SKU-11",
                "asin": "B000000011",
                "country_of_origin": "GB",
                "purchase_pack_size": "1",
                "sold_pack_size": "1",
                "supplier_case_qty": "1",
                "supplier_case_multiple": "0",
                "valid_order_step": "1",
                "moq": "1",
                "target_margin": "30",
                "vat_confirmed_flag": "0",
                "vat_source_value": "",
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "GBP",
                "price_includes_tax": "1",
                "starting_price_gbp": "",
            }
        ],
        actor="tester",
        source_reference="o_ui_profile_review:test",
    )

    assert result["events_applied"] == 0
    assert result["skipped_rows"] == ["cand-11:missing_listing_profile:vat_source_value,vat_confirmed_flag,starting_price_gbp"]


def test_product_listing_profile_completion_writes_profile_event(tmp_path: Path) -> None:
    submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-12",
                "supplier_sku": "SKU-12",
                "asin": "B000000012",
                "title": "Profile product",
                "review_decision": "pass",
            }
        ],
        actor="tester",
        source_reference="o_ui_feeder_review:test",
    )

    result = submit_amazon_listing_profile_batch(
        root=tmp_path,
        profile_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-12",
                "supplier_sku": "SKU-12",
                "asin": "B000000012",
                "country_of_origin": "gb",
                "purchase_pack_size": "6",
                "sold_pack_size": "2",
                "supplier_case_qty": "12",
                "supplier_case_multiple": "1",
                "valid_order_step": "12",
                "moq": "12",
                "target_margin": "30%",
                "vat_source_value": "20%",
                "vat_confirmed_flag": "1",
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "gbp",
                "price_includes_tax": "1",
                "starting_price_gbp": "19.99",
                "starting_quantity": "0",
                "condition_type": "new_new",
            }
        ],
        actor="tester",
        source_reference="o_ui_profile_review:test",
    )

    profile_path = tmp_path / get_f_output_contract("amazon_listing_profile_events").rel_path
    profile_df = pd.read_csv(profile_path, dtype=str).fillna("")

    assert result["events_applied"] == 1
    row = profile_df.iloc[0]
    assert row["profile_status"] == "complete"
    assert row["country_of_origin"] == "GB"
    assert row["purchase_pack_size"] == "6"
    assert row["sold_pack_size"] == "2"
    assert row["supplier_case_qty"] == "12"
    assert row["supplier_case_multiple"] == "1"
    assert row["valid_order_step"] == "12"
    assert row["moq"] == "12"
    assert row["target_margin"] == "30"
    assert row["vat_source_value"] == "20"
    assert row["vat_confirmed_flag"] == "1"
    assert row["currency_code"] == "GBP"
    assert row["starting_price_gbp"] == "19.99"
    pending = build_product_listing_profile_review_df(root=tmp_path)
    assert pending.empty


def test_brand_approval_queue_decision_writes_event(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "brand_approval_queue_live",
        [
            {
                "observed_utc": "2026-05-01T13:00:00Z",
                "queue_id": "brand_approval_1",
                "draft_id": "draft-1",
                "candidate_id": "cand-approval",
                "expected_seller_sku": "NP-SUP-APPROVAL",
                "asin": "B000000099",
                "marketplace_id": "A1F83G8C2ARO7P",
                "brand": "Brand A",
                "amazon_title": "Approval product",
                "approval_status": "approval_required",
                "approval_required_flag": "1",
                "reason_code": "APPROVAL_REQUIRED",
                "reason_message": "You need approval to list this brand.",
                "approval_link": "https://sellercentral.amazon.co.uk/approval",
                "invoice_unit_cost_gbp": "7.00",
                "recheck_trigger": "operator_decision_required",
                "updated_at_utc": "2026-05-01T13:00:00Z",
                "source_reference": "test",
            }
        ],
    )

    display = build_brand_approval_queue_display_df(root=tmp_path)
    assert len(display.index) == 1
    assert display.iloc[0]["brand"] == "Brand A"

    result = submit_brand_approval_decision_batch(
        root=tmp_path,
        actor="tester",
        decision_rows=[
            {
                "queue_id": "brand_approval_1",
                "draft_id": "draft-1",
                "candidate_id": "cand-approval",
                "expected_seller_sku": "NP-SUP-APPROVAL",
                "asin": "B000000099",
                "marketplace_id": "A1F83G8C2ARO7P",
                "brand": "Brand A",
                "operator_decision": "invoice_planned",
                "decision_reason": "10 units is acceptable",
                "invoice_required_quantity": "10",
                "invoice_unit_cost_gbp": "7.00",
            }
        ],
    )

    assert result["events_applied"] == 1
    decision_path = tmp_path / get_f_output_contract("brand_approval_decision_events").rel_path
    decisions = pd.read_csv(decision_path, dtype=str).fillna("")
    row = decisions.iloc[0]
    assert row["operator_decision"] == "invoice_planned"
    assert row["invoice_required_quantity"] == "10"
    assert row["invoice_total_risk_gbp"] == "70.00"


def test_feeder_review_source_loader_normalizes_pass_and_near_miss_reports(tmp_path: Path) -> None:
    pass_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    pass_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-pass",
                "asin": "6SYGN9O",
                "why_data_summary": "units_likely_30d=40 | profit_likely_gbp=25",
                "watch_data_summary": "decision_confidence=medium",
                "pass_reason_summary": "screening_pass|profit_floor_met",
                "commercial_note": "Avoid|qualification_factor_reduced|stability_state_drifting_up|decision_confidence_medium|PASS",
                "profit_on_cost_pct": "42.25",
                "estimated_monthly_profit_gbp": "25",
                "profit_per_unit_30d_gbp": "2.50",
                "original_point_score": "4.0",
                "original_test_result": "PASS",
                "original_test_status_reason": "PASS_SCORE",
                "original_test_gate": "3.5",
            }
        ]
    ).to_csv(pass_path, index=False)
    near_miss_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-near",
                "asin": "B006SYGN9O",
                "why_data_summary": "fail_code=ROIFAIL | profit_likely_gbp=12",
                "watch_data_summary": "recovery_hint=economics_below_pass_floor_but_close_enough_for_manual_review",
                "estimated_monthly_profit_gbp": "12",
                "profit_per_unit_30d_gbp": "1.20",
                "screening_fail_code": "ROIFAIL",
                "recovery_hint": "close enough",
                "original_point_score": "2.5",
                "original_test_result": "FAIL",
                "original_test_status_reason": "PRICE_TOO_HIGH",
                "original_test_gate": "3.5",
            },
            {
                "candidate_id": "cand-near-empty",
                "asin": "B000000001",
                "screening_fail_code": "EVIDENCE_MISSING",
                "recovery_hint": "",
            }
        ]
    ).to_csv(near_miss_path, index=False)

    pass_df = load_feeder_review_source_df("passes", root=tmp_path)
    near_df = load_feeder_review_source_df("near_misses", root=tmp_path)
    near_by_candidate = {row["candidate_id"]: row for row in near_df.to_dict("records")}

    assert pass_df.iloc[0]["asin_padded"] == "0006SYGN9O"
    assert pass_df.iloc[0]["why_label"] == "Why it passed"
    assert pass_df.iloc[0]["why_text"] == "units_likely_30d=40 | profit_likely_gbp=25"
    assert pass_df.iloc[0]["helper_label"] == "What to watch"
    assert pass_df.iloc[0]["helper_text"] == "decision_confidence=medium"
    assert pass_df.iloc[0]["original_point_score"] == "4.0"
    assert pass_df.iloc[0]["original_test_result"] == "PASS"
    assert pass_df.iloc[0]["original_test_status_reason"] == "PASS_SCORE"
    assert pass_df.iloc[0]["original_test_gate"] == "3.5"
    assert pass_df.iloc[0]["review_roi_pct"] == "42.25"
    assert pass_df.iloc[0]["review_roi_text"] == "42%"
    assert pass_df.iloc[0]["review_profit_signal_text"] == "unit_profit=GBP 2.5 | 30d_profit=GBP 25"

    near = near_by_candidate["cand-near"]
    assert near["why_label"] == "Why it nearly failed"
    assert near["why_text"] == "fail_code=ROIFAIL | profit_likely_gbp=12"
    assert near["helper_text"] == "recovery_hint=economics_below_pass_floor_but_close_enough_for_manual_review"
    assert near["original_point_score"] == "2.5"
    assert near["original_test_result"] == "FAIL"
    assert near["original_test_status_reason"] == "PRICE_TOO_HIGH"
    assert near["original_test_gate"] == "3.5"
    assert near["review_roi_pct"] == ""
    assert near["review_roi_text"] == "-"
    assert near["review_profit_signal_text"] == "unit_profit=GBP 1.2 | 30d_profit=GBP 12"

    near_empty = near_by_candidate["cand-near-empty"]
    assert near_empty["helper_text"] == ""
    assert near_empty["original_point_score"] == ""
    assert near_empty["original_test_result"] == ""
    assert near_empty["original_test_status_reason"] == ""
    assert near_empty["original_test_gate"] == ""


def test_feeder_review_source_loader_merges_roi_from_ai_queue_for_human_review(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "sample_supplier"
        / "run_001"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "f_live_price_file_pass_review_latest.csv"
    queue_path = handoff_dir / "ai_review_queue.csv"
    pd.DataFrame(
        [
            {
                "supplier_id": "sample_supplier",
                "supplier_name": "Sample Supplier",
                "run_id": "run_001",
            }
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": "sample_supplier",
                "supplier_name": "Sample Supplier",
                "run_id": "run_001",
                "ai_gate_status": "passed",
                "operator_ready_flag": "1",
                "pass_review_path": str(pass_path),
                "ai_review_queue_path": str(queue_path),
            }
        ]
    ).to_csv(handoff_dir / "manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-roi",
                "f032_decision_id": "f032-roi",
                "supplier_sku": "SKU-ROI",
                "asin": "B000ROI001",
                "title": "ROI visible product",
                "estimated_monthly_profit_gbp": "30",
                "profit_per_unit_30d_gbp": "3",
            }
        ]
    ).to_csv(pass_path, index=False)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-roi",
                "f032_decision_id": "f032-roi",
                "supplier_sku": "SKU-ROI",
                "asin": "B000ROI001",
                "profit_on_cost_pct": "145.333333",
                "supplier_unit_cost_gbp": "2.50",
                "amazon_sell_price_gbp": "9.99",
            }
        ]
    ).to_csv(queue_path, index=False)

    review_df = load_feeder_review_source_df(
        "passes",
        root=tmp_path,
        review_pack_snapshot="handoff|sample_supplier|run_001",
    )

    row = review_df.iloc[0]
    assert row["review_roi_pct"] == "145.333333"
    assert row["review_roi_text"] == "145%"
    assert row["supplier_unit_cost_gbp"] == "2.50"
    assert row["amazon_sell_price_gbp"] == "9.99"


def test_feeder_review_pass_row_adds_ai_compare_note_to_what_to_watch(tmp_path: Path) -> None:
    pass_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    pass_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "candidate_id": "cand-ai-pass",
                "asin": "B000000010",
                "title": "Minecraft Plastic Replica Enchanted Sword 51 cm",
                "watch_data_summary": "decision_confidence=medium",
                "codex_ai_action": "allow_if_other_checks_pass",
                "codex_ai_confidence": "high",
                "codex_ai_reason": "Same Minecraft enchanted toy sword; 51cm vs 50cm is normal rounding.",
            }
        ]
    ).to_csv(pass_path, index=False)

    pass_df = load_feeder_review_source_df("passes", root=tmp_path)

    row = pass_df.iloc[0]
    assert row["helper_label"] == "What to watch"
    assert row["helper_text"] == (
        "decision_confidence=medium | ai_match_confidence=high | "
        "ai_compare=Same Minecraft enchanted toy sword; 51cm vs 50cm is normal rounding."
    )
    assert row["ai_compare_watch_note"] == (
        "ai_match_confidence=high | "
        "ai_compare=Same Minecraft enchanted toy sword; 51cm vs 50cm is normal rounding."
    )


def test_feeder_review_manual_review_lane_splits_near_miss_pack(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "batch-1",
                "review_priority_score": "90",
                "candidate_id": "manual-seller-history",
                "supplier_sku": "SKU-MAN-1",
                "asin": "B000000001",
                "title": "NO with enough sellers",
                "near_miss_type": "seller_history_manual_review",
                "seller_history_recommended_action": "manual_review",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "batch-1",
                "review_priority_score": "80",
                "candidate_id": "manual-demand",
                "supplier_sku": "SKU-MAN-2",
                "asin": "B000000002",
                "title": "Demand warning",
                "near_miss_type": "demand_range_warning",
                "demand_recommended_action": "manual_review",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "batch-1",
                "review_priority_score": "70",
                "candidate_id": "standard-near",
                "supplier_sku": "SKU-NEAR",
                "asin": "B000000003",
                "title": "Standard near miss",
                "near_miss_type": "commercial_near_miss",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
            },
        ]
    ).to_csv(report_path, index=False)

    all_df, all_meta = build_feeder_review_window_df("near_misses", root=tmp_path, page_size=10)
    manual_df, manual_meta = build_feeder_review_window_df(
        "near_misses",
        root=tmp_path,
        lane_filter="manual_review",
        page_size=10,
    )
    near_df, near_meta = build_feeder_review_window_df(
        "near_misses",
        root=tmp_path,
        lane_filter="near_misses",
        page_size=10,
    )

    assert all_meta["available_rows"] == 3
    assert set(all_df["candidate_id"]) == {"manual-seller-history", "manual-demand", "standard-near"}
    assert manual_meta["available_rows"] == 2
    assert set(manual_df["candidate_id"]) == {"manual-seller-history", "manual-demand"}
    assert near_meta["available_rows"] == 1
    assert list(near_df["candidate_id"]) == ["standard-near"]
    assert set(manual_df["review_pack_type"]) == {"near_misses"}


def test_feeder_review_manual_row_prefers_ai_check_note(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_near_miss_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "run-1",
                "review_batch_id": "batch-1",
                "review_priority_score": "90",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                "near_miss_type": "f032_manual_review",
                "watch_data_summary": "old scanner watch note",
                "f032_action": "manual_review",
                "codex_ai_action": "manual_review",
                "codex_ai_decision_bucket": "pack_size_or_quantity_needs_user_guidance",
                "codex_ai_reason": "Supplier title says Sleeves 50 Pack, but Amazon title does not confirm the count.",
                "codex_ai_evidence": "supplier_quantities=50|amazon_quantities=",
            }
        ]
    ).to_csv(report_path, index=False)

    manual_df, meta = build_feeder_review_window_df(
        "near_misses",
        root=tmp_path,
        lane_filter="manual_review",
        page_size=10,
    )

    assert meta["available_rows"] == 1
    row = manual_df.iloc[0]
    assert row["helper_label"] == "What to watch"
    assert row["helper_text"] == (
        "old scanner watch note | ai_compare=confirm the Amazon listing is for 50 units per pack."
    )
    assert row["f032_operator_check_note"] == "AI check: confirm the Amazon listing is for 50 units per pack."
    assert row["ai_compare_watch_note"] == "ai_compare=confirm the Amazon listing is for 50 units per pack."


def test_feeder_review_can_load_timestamped_pack_without_latest(tmp_path: Path) -> None:
    reports_dir = tmp_path / "out" / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir = tmp_path / "out" / "systems" / "O" / "live"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_code": "stocklist_supplier",
                "supplier_name": "Entertainment Trading",
            }
        ]
    ).to_csv(profiles_dir / "supplier_profiles.csv", index=False)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-23T15:13:40Z",
                "metric": "active_supplier_id",
                "value": "stocklist_supplier",
            },
            {
                "observed_utc": "2026-04-23T15:13:40Z",
                "metric": "active_run_id",
                "value": "entertainment_trading_20260423",
            },
            {
                "observed_utc": "2026-04-23T15:13:40Z",
                "metric": "source_seen_at_utc",
                "value": "2026-04-21T09:30:00Z",
            },
            {"observed_utc": "2026-04-23T15:13:40Z", "metric": "pass_review_rows", "value": "47"},
            {"observed_utc": "2026-04-23T15:13:40Z", "metric": "near_miss_review_rows", "value": "3276"},
        ]
    ).to_csv(reports_dir / "f_live_price_file_review_summary_20260423T151340Z.csv", index=False)
    pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-29T07:22:19Z",
                "metric": "active_supplier_id",
                "value": "stocklist_supplier",
            },
            {
                "observed_utc": "2026-04-29T07:22:19Z",
                "metric": "active_run_id",
                "value": "stocklist_20260429",
            },
            {
                "observed_utc": "2026-04-29T07:22:19Z",
                "metric": "source_seen_at_utc",
                "value": "2026-04-29T07:00:00Z",
            },
            {"observed_utc": "2026-04-29T07:22:19Z", "metric": "pass_review_rows", "value": "26"},
            {"observed_utc": "2026-04-29T07:22:19Z", "metric": "near_miss_review_rows", "value": "1568"},
        ]
    ).to_csv(reports_dir / "f_live_price_file_review_summary_latest.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "entertainment_trading_20260423",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "100",
                "candidate_id": "game-cand",
                "supplier_sku": "SKU-GAME",
                "asin": "B000000123",
                "title": "Nintendo Switch game",
            }
        ]
    ).to_csv(reports_dir / "f_live_price_file_pass_review_20260423T151340Z.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "stocklist_20260429",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "50",
                "candidate_id": "fragrance-cand",
                "supplier_sku": "SKU-FRAG",
                "asin": "B000000456",
                "title": "BOSS fragrance",
            }
        ]
    ).to_csv(reports_dir / "f_live_price_file_pass_review_latest.csv", index=False)

    default_options = list_feeder_review_pack_options(root=tmp_path)
    options = list_feeder_review_pack_options(root=tmp_path, include_history=True)
    snapshot_df = load_feeder_review_source_df(
        "passes",
        root=tmp_path,
        review_pack_snapshot="20260423T151340Z",
    )
    latest_df = load_feeder_review_source_df("passes", root=tmp_path)

    assert any(option["id"] == "20260423T151340Z" for option in default_options)
    assert any(option["id"] == "20260423T151340Z" for option in options)
    assert any(option["label"] == "Entertainment Trading - 21 Apr 09:30" for option in options)
    assert [option["id"] for option in default_options] == ["20260423T151340Z", "latest"]
    assert snapshot_df.iloc[0]["candidate_id"] == "game-cand"
    assert latest_df.iloc[0]["candidate_id"] == "fragrance-cand"


def test_feeder_review_can_load_completed_handoff_pack(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "f_live_price_file_pass_review_20260501T090600Z.csv"
    near_path = handoff_dir / "f_live_price_file_near_miss_review_20260501T090600Z.csv"
    summary_path = handoff_dir / "f_live_price_file_review_summary_20260501T090600Z.csv"
    pd.DataFrame(
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "fpm_entertainment_trading_test",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "60",
                "candidate_id": "handoff-pass",
                "supplier_sku": "ET-1",
                "asin": "B000000001",
                "title": "Completed handoff product",
                "f032_decision_id": "f032_handoff_pass",
                "f032_action": "allow_if_other_checks_pass",
            }
        ]
    ).to_csv(pass_path, index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "fpm_entertainment_trading_test",
                "review_batch_id": "near_miss_batch_001",
                "review_priority_score": "40",
                "candidate_id": "handoff-near",
                "supplier_sku": "ET-2",
                "asin": "B000000002",
                "title": "Completed handoff near miss",
                "near_miss_type": "commercial_near_miss",
                "f032_decision_id": "f032_handoff_near",
                "f032_action": "allow_if_other_checks_pass",
            }
        ]
    ).to_csv(near_path, index=False)
    pd.DataFrame(
        [
            {"observed_utc": "2026-05-01T09:06:00Z", "metric": "active_supplier_id", "value": "entertainment_trading"},
            {
                "observed_utc": "2026-05-01T09:06:00Z",
                "metric": "active_run_id",
                "value": "fpm_entertainment_trading_test",
            },
            {"observed_utc": "2026-05-01T09:06:00Z", "metric": "source_seen_at_utc", "value": "2026-04-30T14:13:50Z"},
            {"observed_utc": "2026-05-01T09:06:00Z", "metric": "pass_review_rows", "value": "1"},
            {"observed_utc": "2026-05-01T09:06:00Z", "metric": "near_miss_review_rows", "value": "1"},
        ]
    ).to_csv(summary_path, index=False)
    pd.DataFrame(
        [
            {
                "built_at_utc": "2026-05-01T09:06:00Z",
                "supplier_id": "entertainment_trading",
                "supplier_name": "Entertainment Trading",
                "run_id": "fpm_entertainment_trading_test",
                "review_snapshot_id": "20260501T090600Z",
                "source_file_path": "Stocklist.xlsx",
                "source_seen_at_utc": "2026-04-30T14:13:50Z",
                "completed_at_utc": "2026-05-01T09:05:00Z",
                "pass_review_rows": "1",
                "near_miss_review_rows": "1",
                "hard_reject_rows": "0",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": str(near_path),
                "summary_path": str(summary_path),
                "handoff_dir": str(handoff_dir),
                "published_to_operator_latest_flag": "0",
                "ai_gate_status": "passed",
                "ai_gate_observed_utc": "2026-05-01T09:06:00Z",
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
                "notes": "test",
            }
        ],
        columns=REVIEW_HANDOFF_MANIFEST_COLUMNS,
    ).to_csv(handoff_dir / "manifest.csv", index=False)

    snapshot_id = "handoff|entertainment_trading|fpm_entertainment_trading_test"
    options = list_feeder_review_pack_options(root=tmp_path)
    summary = load_feeder_review_summary(root=tmp_path, review_pack_snapshot=snapshot_id)
    pass_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot=snapshot_id)
    near_df = load_feeder_review_source_df("near_misses", root=tmp_path, review_pack_snapshot=snapshot_id)

    assert any(option["id"] == snapshot_id for option in options)
    assert any(option["label"] == "Entertainment Trading - completed 01 May 09:05" for option in options)
    assert summary["active_supplier_id"] == "entertainment_trading"
    assert summary["active_supplier_label"] == "Entertainment Trading"
    assert summary["active_run_id"] == "fpm_entertainment_trading_test"
    assert summary["completed_at_utc"] == "2026-05-01T09:05:00Z"
    assert pass_df.iloc[0]["candidate_id"] == "handoff-pass"
    assert near_df.iloc[0]["candidate_id"] == "handoff-near"


def test_feeder_review_pack_options_are_lane_todo_lists(tmp_path: Path) -> None:
    handoff_root = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"

    def write_handoff(
        *,
        supplier_id: str,
        supplier_name: str,
        run_id: str,
        pass_rows: list[dict[str, str]],
        near_rows: list[dict[str, str]],
        completed_at: str,
    ) -> str:
        handoff_dir = handoff_root / supplier_id / run_id
        handoff_dir.mkdir(parents=True, exist_ok=True)
        pass_path = handoff_dir / "ai_operator_pass_review.csv"
        near_path = handoff_dir / "ai_operator_near_miss_review.csv"
        pass_columns = [
            "active_supplier_id",
            "active_run_id",
            "review_batch_id",
            "candidate_id",
            "supplier_sku",
            "asin",
            "title",
            "f032_action",
        ]
        near_columns = [*pass_columns, "near_miss_type"]
        pd.DataFrame(pass_rows, columns=pass_columns).to_csv(pass_path, index=False)
        pd.DataFrame(near_rows, columns=near_columns).to_csv(near_path, index=False)
        pd.DataFrame(
            [
                {
                    "built_at_utc": completed_at,
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "run_id": run_id,
                    "review_snapshot_id": completed_at.replace("-", "").replace(":", "").replace("Z", "Z"),
                    "completed_at_utc": completed_at,
                    "pass_review_rows": str(len(pass_rows)),
                    "near_miss_review_rows": str(len(near_rows)),
                    "pass_review_path": str(pass_path),
                    "near_miss_review_path": str(near_path),
                    "handoff_dir": str(handoff_dir),
                    "ai_gate_status": "passed",
                    "operator_ready_flag": "1",
                }
            ],
            columns=REVIEW_HANDOFF_MANIFEST_COLUMNS,
        ).to_csv(handoff_dir / "manifest.csv", index=False)
        return f"handoff|{supplier_id}|{run_id}"

    bliss_id = write_handoff(
        supplier_id="bliss_distribution",
        supplier_name="Bliss Distribution",
        run_id="run_bliss",
        completed_at="2026-05-17T09:16:00Z",
        pass_rows=[
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "run_bliss",
                "review_batch_id": "pass_batch",
                "candidate_id": f"bliss-{idx}",
                "supplier_sku": f"BLISS-{idx}",
                "asin": f"B000BLISS{idx}",
                "title": f"Bliss product {idx}",
                "f032_action": "allow_if_other_checks_pass",
            }
            for idx in range(3)
        ],
        near_rows=[],
    )
    entertainment_id = write_handoff(
        supplier_id="entertainment_trading",
        supplier_name="Entertainment Trading",
        run_id="run_entertainment",
        completed_at="2026-05-21T12:25:00Z",
        pass_rows=[],
        near_rows=[
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "run_entertainment",
                "review_batch_id": "manual_batch",
                "candidate_id": f"manual-{idx}",
                "supplier_sku": f"ET-{idx}",
                "asin": f"B000ETMAN{idx}",
                "title": f"Entertainment manual product {idx}",
                "f032_action": "manual_review",
                "near_miss_type": "manual_review",
            }
            for idx in range(4)
        ],
    )
    completed_id = write_handoff(
        supplier_id="completed_supplier",
        supplier_name="Completed Supplier",
        run_id="run_completed",
        completed_at="2026-05-18T08:00:00Z",
        pass_rows=[
            {
                "active_supplier_id": "completed_supplier",
                "active_run_id": "run_completed",
                "review_batch_id": "pass_batch",
                "candidate_id": "completed-pass",
                "supplier_sku": "DONE-1",
                "asin": "B000DONE01",
                "title": "Already reviewed product",
                "f032_action": "allow_if_other_checks_pass",
            }
        ],
        near_rows=[],
    )
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-05-18T09:00:00Z",
                "event_id": "evt-completed",
                "active_supplier_id": "completed_supplier",
                "active_run_id": "run_completed",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch",
                "candidate_id": "completed-pass",
                "supplier_sku": "DONE-1",
                "asin_raw": "B000DONE01",
                "asin_padded": "B000DONE01",
                "amazon_dp_url": "",
                "review_decision": "pass",
                "review_note": "",
                "actor": "test",
                "source_reference": "test",
            }
        ],
    )

    pass_options = list_feeder_review_pack_options(
        root=tmp_path,
        pack_type="passes",
        lane_filter="passes",
        lane_label="Passes",
    )
    manual_options = list_feeder_review_pack_options(
        root=tmp_path,
        pack_type="near_misses",
        lane_filter="manual_review",
        lane_label="Manual review",
    )
    history_options = list_feeder_review_pack_options(
        root=tmp_path,
        include_history=True,
        pack_type="passes",
        lane_filter="passes",
        lane_label="Passes",
    )

    assert {option["id"] for option in pass_options} == {"handoff_group|bliss_distribution"}
    assert pass_options[0]["label"] == "Bliss Distribution - 3 unique scanner finds waiting"
    assert {option["id"] for option in manual_options} == {"handoff_group|entertainment_trading"}
    assert manual_options[0]["label"] == "Entertainment Trading - 4 judgement checks waiting"
    assert completed_id not in {option["id"] for option in pass_options}
    assert completed_id in {option["id"] for option in history_options}
    assert any(option["label"] == "Completed Supplier - 0 scanner finds waiting" for option in history_options)


def test_feeder_review_handoff_groups_dedupe_supplier_asin_and_close_old_runs(tmp_path: Path) -> None:
    handoff_root = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"

    def write_dhb_handoff(run_id: str, completed_at: str, rows: list[dict[str, str]]) -> str:
        handoff_dir = handoff_root / "dhb" / run_id
        handoff_dir.mkdir(parents=True, exist_ok=True)
        pass_path = handoff_dir / "ai_operator_pass_review.csv"
        pass_columns = [
            "active_supplier_id",
            "active_run_id",
            "review_batch_id",
            "candidate_id",
            "supplier_sku",
            "asin",
            "title",
            "f032_action",
        ]
        pd.DataFrame(rows, columns=pass_columns).to_csv(pass_path, index=False)
        pd.DataFrame(columns=pass_columns).to_csv(handoff_dir / "ai_operator_near_miss_review.csv", index=False)
        pd.DataFrame(
            [
                {
                    "built_at_utc": completed_at,
                    "supplier_id": "dhb",
                    "supplier_name": "DHB",
                    "run_id": run_id,
                    "review_snapshot_id": completed_at.replace("-", "").replace(":", "").replace("Z", "Z"),
                    "completed_at_utc": completed_at,
                    "pass_review_rows": str(len(rows)),
                    "near_miss_review_rows": "0",
                    "pass_review_path": str(pass_path),
                    "near_miss_review_path": str(handoff_dir / "ai_operator_near_miss_review.csv"),
                    "handoff_dir": str(handoff_dir),
                    "ai_gate_status": "passed",
                    "operator_ready_flag": "1",
                }
            ],
            columns=REVIEW_HANDOFF_MANIFEST_COLUMNS,
        ).to_csv(handoff_dir / "manifest.csv", index=False)
        return f"handoff|dhb|{run_id}"

    old_id = write_dhb_handoff(
        "fpm_dhb_old",
        "2026-05-07T03:00:00Z",
        [
            {
                "active_supplier_id": "dhb",
                "active_run_id": "fpm_dhb_old",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "candidate-old-b001",
                "supplier_sku": "PDL504",
                "asin": "B001AI8AKI",
                "title": "TePe Interdental Brush Blue 0.6mm Pack of 6",
                "f032_action": "allow_if_other_checks_pass",
            }
        ],
    )
    latest_id = write_dhb_handoff(
        "fpm_dhb_latest",
        "2026-05-07T06:00:00Z",
        [
            {
                "active_supplier_id": "dhb",
                "active_run_id": "fpm_dhb_latest",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "candidate-latest-b001",
                "supplier_sku": "PDL504",
                "asin": "B001AI8AKI",
                "title": "TePe Interdental Brush Blue 0.6mm Pack of 6",
                "f032_action": "allow_if_other_checks_pass",
            },
            {
                "active_supplier_id": "dhb",
                "active_run_id": "fpm_dhb_latest",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "candidate-latest-b085",
                "supplier_sku": "TEP084",
                "asin": "B0853KGR7X",
                "title": "TePe Good Compact Toothbrush",
                "f032_action": "allow_if_other_checks_pass",
            },
        ],
    )
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-05-08T09:27:41Z",
                "event_id": "evt-b001-fail",
                "active_supplier_id": "dhb",
                "active_run_id": "fpm_dhb_latest",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "candidate-latest-b001",
                "supplier_sku": "PDL504",
                "asin_raw": "B001AI8AKI",
                "asin_padded": "B001AI8AKI",
                "amazon_dp_url": "",
                "review_decision": "fail",
                "review_note": "not clean",
                "actor": "test",
                "source_reference": "test",
            },
            {
                "event_utc": "2026-05-08T09:30:14Z",
                "event_id": "evt-b085-fail",
                "active_supplier_id": "dhb",
                "active_run_id": "fpm_dhb_latest",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "candidate-latest-b085",
                "supplier_sku": "TEP084",
                "asin_raw": "B0853KGR7X",
                "asin_padded": "B0853KGR7X",
                "amazon_dp_url": "",
                "review_decision": "fail",
                "review_note": "not enough profit upside",
                "actor": "test",
                "source_reference": "test",
            },
        ],
    )

    pass_options = list_feeder_review_pack_options(
        root=tmp_path,
        pack_type="passes",
        lane_filter="passes",
        lane_label="Passes",
    )
    history_options = list_feeder_review_pack_options(
        root=tmp_path,
        include_history=True,
        pack_type="passes",
        lane_filter="passes",
        lane_label="Passes",
    )
    grouped_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot="handoff_group|dhb")
    window_df, meta = build_feeder_review_window_df(
        "passes",
        root=tmp_path,
        review_pack_snapshot="handoff_group|dhb",
        lane_filter="passes",
    )
    sent_df = build_feeder_review_sent_df(
        "passes",
        root=tmp_path,
        review_pack_snapshot="handoff_group|dhb",
        lane_filter="passes",
        page_size=10,
    )

    assert old_id not in {option["id"] for option in pass_options}
    assert latest_id not in {option["id"] for option in pass_options}
    assert "handoff_group|dhb" not in {option["id"] for option in pass_options}
    assert {row["asin"] for _, row in grouped_df.iterrows()} == {"B001AI8AKI", "B0853KGR7X"}
    assert set(grouped_df["active_run_id"]) == {"fpm_dhb_latest"}
    assert window_df.empty
    assert meta["undecided_rows"] == 0
    assert set(sent_df["latest_review_decision"]) == {"fail"}
    assert any(option["id"] == old_id and option["label"] == "DHB - 0 scanner finds waiting" for option in history_options)
    assert any(option["id"] == latest_id and option["label"] == "DHB - 0 scanner finds waiting" for option in history_options)


def test_feeder_review_latest_is_blocked_while_ai_gate_is_pending(tmp_path: Path) -> None:
    reports_dir = tmp_path / "out" / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "fpm_entertainment_trading_test",
                "candidate_id": "raw-latest-pass",
                "supplier_sku": "ET-RAW",
                "asin": "B000000999",
                "title": "Raw latest product",
            }
        ]
    ).to_csv(reports_dir / "f_live_price_file_pass_review_latest.csv", index=False)
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "entertainment_trading"
        / "fpm_entertainment_trading_test"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "supplier_id": "entertainment_trading",
                "run_id": "fpm_entertainment_trading_test",
                "operator_ready_flag": "0",
            }
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)

    latest_df = load_feeder_review_source_df("passes", root=tmp_path)

    assert latest_df.empty


def test_ai_product_check_gate_builds_statuses_from_queue_and_decisions(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "sample_supplier"
        / "run_001"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    queue_path = handoff_dir / "ai_review_queue.csv"
    decision_path = handoff_dir / "codex_ai_review_decisions.csv"
    manifest_path = handoff_dir / "manifest.csv"
    pd.DataFrame(
        [
            {"supplier_id": "sample_supplier", "supplier_name": "Sample Supplier", "run_id": "run_001"},
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": "sample_supplier",
                "supplier_name": "Sample Supplier",
                "run_id": "run_001",
                "ai_gate_status": "passed",
                "operator_ready_flag": "1",
                "ai_review_queue_path": str(queue_path),
                "codex_ai_decision_path": str(decision_path),
            }
        ]
    ).to_csv(manifest_path, index=False)
    pd.DataFrame(
        [
            {
                "f032_decision_id": "pending",
                "supplier_sku": "SKU-P",
                "asin": "B000PENDING",
                "supplier_title": "Supplier pending product",
                "amazon_title": "Amazon pending product",
                "profit_on_cost_pct": "45.5",
            },
            {
                "f032_decision_id": "clear",
                "supplier_sku": "SKU-C",
                "asin": "B000CLEAR1",
                "supplier_title": "Supplier clear product",
                "amazon_title": "Amazon clear product",
                "amazon_product_description": "Each pack contains 50 card sleeves.",
                "profit_on_cost_pct": "22",
            },
            {
                "f032_decision_id": "manual",
                "supplier_sku": "SKU-M",
                "asin": "B000MANUAL",
                "supplier_title": "Supplier filter",
                "amazon_title": "Amazon machine",
                "profit_on_cost_pct": "240",
            },
            {
                "f032_decision_id": "rescan",
                "supplier_sku": "SKU-R",
                "asin": "B000RESCAN",
                "supplier_title": "Supplier rescan product",
                "amazon_title": "Amazon rescan product",
            },
            {
                "f032_decision_id": "missing-page-clear",
                "supplier_sku": "SKU-MPC",
                "asin": "B000PAGECLR",
                "supplier_title": "One Piece World Seeker PS4",
                "amazon_title": "One Piece World Seeker (PS4)",
                "f032_rule_action": "allow_if_other_checks_pass",
                "f032_rule_bucket": "ai_review_clear",
                "f032_rule_confidence": "medium",
                "f032_rule_reason": "F032 found no interpretive blocker in the available evidence.",
            },
            {
                "f032_decision_id": "missing-page-manual",
                "supplier_sku": "SKU-MPM",
                "asin": "B000PAGEMAN",
                "supplier_title": "Yu-Gi-Oh! Kuriboh Kollection Sleeves 50 Pack",
                "amazon_title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                "f032_rule_action": "manual_review",
                "f032_rule_bucket": "needs_user_guidance",
                "f032_rule_confidence": "medium",
                "f032_rule_fail_category": "pack_size_or_quantity",
                "f032_rule_reason": "pack_or_quantity_mismatch_needs_user_guidance",
            },
            {
                "f032_decision_id": "reject",
                "supplier_sku": "SKU-X",
                "asin": "B000REJECT",
                "supplier_title": "Supplier refill",
                "amazon_title": "Amazon device",
            },
        ]
    ).to_csv(queue_path, index=False)
    pd.DataFrame(
        [
            {
                "f032_decision_id": "clear",
                "codex_ai_action": "allow_if_other_checks_pass",
                "codex_ai_decision_bucket": "ai_review_clear",
                "codex_ai_confidence": "high",
                "codex_ai_reason": "Titles describe the same product.",
                "codex_ai_reviewed_utc": "2026-05-21T07:00:00Z",
            },
            {
                "f032_decision_id": "manual",
                "codex_ai_action": "manual_review",
                "codex_ai_decision_bucket": "possible_wrong_product",
                "codex_ai_confidence": "medium",
                "codex_ai_reason": "Same brand but supplier says filter and Amazon says device.",
                "codex_ai_reviewed_utc": "2026-05-21T07:01:00Z",
            },
            {
                "f032_decision_id": "rescan",
                "codex_ai_action": "rescan_needed",
                "codex_ai_decision_bucket": "missing_page_evidence",
                "codex_ai_confidence": "low",
                "codex_ai_reason": "Page evidence is incomplete.",
                "codex_ai_reviewed_utc": "2026-05-21T07:02:00Z",
            },
            {
                "f032_decision_id": "missing-page-clear",
                "codex_ai_action": "rescan_needed",
                "codex_ai_decision_bucket": "missing_page_evidence",
                "codex_ai_fail_category": "missing_page_evidence",
                "codex_ai_confidence": "low",
                "codex_ai_reason": "Page evidence is incomplete.",
                "codex_ai_reviewed_utc": "2026-05-21T07:02:30Z",
            },
            {
                "f032_decision_id": "missing-page-manual",
                "codex_ai_action": "rescan_needed",
                "codex_ai_decision_bucket": "missing_page_evidence",
                "codex_ai_fail_category": "missing_page_evidence",
                "codex_ai_confidence": "low",
                "codex_ai_reason": "Page evidence is incomplete.",
                "codex_ai_reviewed_utc": "2026-05-21T07:02:45Z",
            },
            {
                "f032_decision_id": "reject",
                "codex_ai_action": "remove_from_clean_pass",
                "codex_ai_decision_bucket": "clear_breach",
                "codex_ai_confidence": "high",
                "codex_ai_reason": "Supplier title is a refill and Amazon title is a device.",
                "codex_ai_reviewed_utc": "2026-05-21T07:03:00Z",
            },
        ]
    ).to_csv(decision_path, index=False)

    gate_df = build_ai_product_check_gate_df(root=tmp_path)
    by_id = gate_df.set_index("f032_decision_id").to_dict("index")

    assert by_id["pending"]["queue_state"] == "pending_ai_check"
    assert by_id["clear"]["queue_state"] == "ai_cleared"
    assert by_id["clear"]["operator_visible_flag"] == "1"
    assert by_id["clear"]["amazon_description_snippet"] == "Each pack contains 50 card sleeves."
    assert by_id["manual"]["queue_state"] == "needs_user_guidance"
    assert by_id["manual"]["operator_visible_flag"] == "1"
    assert by_id["rescan"]["queue_state"] == "rescan_needed"
    assert by_id["rescan"]["operator_visible_flag"] == "0"
    assert by_id["missing-page-clear"]["queue_state"] == "ai_cleared"
    assert by_id["missing-page-clear"]["operator_visible_flag"] == "1"
    assert "secondary evidence" in by_id["missing-page-clear"]["codex_ai_reason"]
    assert by_id["missing-page-manual"]["queue_state"] == "needs_user_guidance"
    assert by_id["missing-page-manual"]["operator_visible_flag"] == "1"
    assert by_id["missing-page-manual"]["codex_ai_confidence"] == "medium"
    assert by_id["reject"]["queue_state"] == "ai_rejected"
    assert by_id["reject"]["operator_visible_flag"] == "0"


def test_ai_product_check_gate_shows_waiting_row_when_queue_is_missing(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "sample_supplier"
        / "run_002"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"supplier_id": "sample_supplier", "supplier_name": "Sample Supplier", "run_id": "run_002"},
        ]
    ).to_csv(handoff_dir / "candidate_manifest.csv", index=False)

    gate_df = build_ai_product_check_gate_df(root=tmp_path)

    assert len(gate_df.index) == 1
    assert gate_df.iloc[0]["queue_state"] == "waiting_for_ai_queue"
    assert gate_df.iloc[0]["operator_visible_flag"] == "0"


def test_legacy_handoff_is_blocked_from_new_product_review_and_shown_in_ai_gate(tmp_path: Path) -> None:
    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "bliss_distribution"
        / "fpm_bliss_distribution_20260518T094415Z"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "f_live_price_file_pass_review_20260518T115122Z.csv"
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "18.6",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
            }
        ]
    ).to_csv(pass_path, index=False)
    near_path = handoff_dir / "f_live_price_file_near_miss_review_20260518T115122Z.csv"
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "near_miss_batch_001",
                "review_priority_score": "11.2",
                "candidate_id": "kuriboh-near",
                "supplier_sku": "KONKKS-NEAR",
                "asin": "B09HKZWBD0",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves near miss",
            }
        ]
    ).to_csv(near_path, index=False)
    pd.DataFrame(
        [
            {
                "built_at_utc": "2026-05-18T11:51:22Z",
                "supplier_id": "bliss_distribution",
                "supplier_name": "Bliss Distribution",
                "run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_snapshot_id": "20260518T115122Z",
                "completed_at_utc": "2026-05-18T11:51:22Z",
                "pass_review_rows": "1",
                "near_miss_review_rows": "1",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": str(near_path),
                "summary_path": "",
                "handoff_dir": str(handoff_dir),
                "published_to_operator_latest_flag": "0",
                "block_reason": "",
                "notes": "legacy pre AI gate",
            }
        ]
    ).to_csv(handoff_dir / "manifest.csv", index=False)

    snapshot_id = "handoff|bliss_distribution|fpm_bliss_distribution_20260518T094415Z"
    options = list_feeder_review_pack_options(root=tmp_path, include_history=True)
    pass_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot=snapshot_id)
    gate_df = build_ai_product_check_gate_df(root=tmp_path)

    assert not any(option["id"] == snapshot_id for option in options)
    assert pass_df.empty
    assert "B09HKZWBDN" in set(gate_df["asin"])
    row = gate_df[gate_df["asin"] == "B09HKZWBDN"].iloc[0]
    assert row["queue_state"] == "legacy_needs_ai_gate"
    assert row["source_review_pack_type"] == "passes"
    assert row["operator_visible_flag"] == "0"
    near_row = gate_df[gate_df["asin"] == "B09HKZWBD0"].iloc[0]
    assert near_row["queue_state"] == "legacy_manual_near_backlog"
    assert near_row["source_review_pack_type"] == "near_misses"


def test_legacy_timestamped_snapshot_is_hidden_when_ai_gate_is_active(tmp_path: Path) -> None:
    reports_dir = tmp_path / "out" / "analysis_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    handoff_root = tmp_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"
    handoff_root.mkdir(parents=True, exist_ok=True)
    snapshot = "20260518T115122Z"
    pd.DataFrame(
        [
            {"observed_utc": "2026-05-18T11:51:22Z", "metric": "active_supplier_id", "value": "bliss_distribution"},
            {
                "observed_utc": "2026-05-18T11:51:22Z",
                "metric": "active_run_id",
                "value": "fpm_bliss_distribution_20260518T094415Z",
            },
            {"observed_utc": "2026-05-18T11:51:22Z", "metric": "pass_review_rows", "value": "1"},
        ]
    ).to_csv(reports_dir / f"f_live_price_file_review_summary_{snapshot}.csv", index=False)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
            }
        ]
    ).to_csv(reports_dir / f"f_live_price_file_pass_review_{snapshot}.csv", index=False)

    options = list_feeder_review_pack_options(root=tmp_path, include_history=True)
    snapshot_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot=snapshot)

    assert not any(option["id"] == snapshot for option in options)
    assert snapshot_df.empty


def test_feeder_review_ui_loads_sql_review_pack_without_csv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    snapshot = "20260429T150000Z"
    pass_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "stocklist_20260429",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "50",
                "candidate_id": "sql-cand",
                "supplier_sku": "SKU-SQL",
                "asin": "B000000789",
                "title": "SQL only row",
            }
        ]
    )
    near_df = pd.DataFrame(columns=pass_df.columns)
    summary_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "metric": "active_supplier_id",
                "value": "stocklist_supplier",
            },
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "metric": "active_run_id",
                "value": "stocklist_20260429",
            },
            {
                "observed_utc": "2026-04-29T15:00:00Z",
                "metric": "source_seen_at_utc",
                "value": "2026-04-29T14:45:00Z",
            },
        ]
    )
    write_review_pack_snapshots_sql_compat(
        pass_df=pass_df,
        near_miss_df=near_df,
        summary_df=summary_df,
        snapshot_id=snapshot,
    )

    options = list_feeder_review_pack_options(root=tmp_path, include_history=True)
    latest_summary = load_feeder_review_summary(root=tmp_path)
    latest_df = load_feeder_review_source_df("passes", root=tmp_path)
    historical_df = load_feeder_review_source_df("passes", root=tmp_path, review_pack_snapshot=snapshot)

    assert not (tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv").exists()
    assert any(option["id"] == snapshot for option in options)
    assert latest_summary["active_run_id"] == "stocklist_20260429"
    assert latest_df.iloc[0]["candidate_id"] == "sql-cand"
    assert historical_df.iloc[0]["candidate_id"] == "sql-cand"


def test_latest_ai_gated_manifest_csv_overrides_stale_sql_latest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    stale_sql_pass_df = pd.DataFrame(
        [
            {
                "observed_utc": "2026-05-18T11:51:22Z",
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "fpm_bliss_distribution_20260518T094415Z",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "kuriboh-sleeves",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
            }
        ]
    )
    write_review_pack_snapshots_sql_compat(
        pass_df=stale_sql_pass_df,
        near_miss_df=pd.DataFrame(columns=stale_sql_pass_df.columns),
        summary_df=pd.DataFrame(
            [
                {"observed_utc": "2026-05-18T11:51:22Z", "metric": "active_supplier_id", "value": "bliss_distribution"},
                {
                    "observed_utc": "2026-05-18T11:51:22Z",
                    "metric": "active_run_id",
                    "value": "fpm_bliss_distribution_20260518T094415Z",
                },
            ]
        ),
        snapshot_id="sql_stale_bliss_snapshot",
    )

    handoff_dir = (
        tmp_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / "stocklist_supplier"
        / "legacy_latest_pass_page_evidence_20260520T210352Z"
    )
    handoff_dir.mkdir(parents=True, exist_ok=True)
    pass_path = handoff_dir / "ai_operator_pass_review.csv"
    near_path = handoff_dir / "ai_operator_near_miss_review.csv"
    summary_path = handoff_dir / "ai_operator_review_summary.csv"
    live_manifest_path = (
        tmp_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_manifest.csv"
    )
    live_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "stocklist_supplier_rescrape_subset_20260421T103451Z",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "stocklist-ai-cleared",
                "supplier_sku": "1144846",
                "asin": "B082NMTZC2",
                "title": "JVC Boombox",
                "f032_decision_id": "f032-stocklist",
                "f032_action": "allow_if_other_checks_pass",
                "codex_ai_action": "allow_if_other_checks_pass",
            }
        ]
    ).to_csv(pass_path, index=False)
    pd.DataFrame(columns=pd.read_csv(pass_path, dtype=str).columns).to_csv(near_path, index=False)
    pd.DataFrame(
        [
            {"observed_utc": "2026-05-20T21:03:52Z", "metric": "active_supplier_id", "value": "stocklist_supplier"},
            {
                "observed_utc": "2026-05-20T21:03:52Z",
                "metric": "active_run_id",
                "value": "legacy_latest_pass_page_evidence_20260520T210352Z",
            },
            {"observed_utc": "2026-05-20T21:03:52Z", "metric": "pass_review_rows", "value": "1"},
        ]
    ).to_csv(summary_path, index=False)
    pd.DataFrame(
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "run_id": "legacy_latest_pass_page_evidence_20260520T210352Z",
                "review_snapshot_id": "20260520T210352Z",
                "pass_review_path": str(pass_path),
                "near_miss_review_path": str(near_path),
                "summary_path": str(summary_path),
                "ai_gate_status": "passed",
                "operator_ready_flag": "1",
            }
        ]
    ).to_csv(live_manifest_path, index=False)

    latest_summary = load_feeder_review_summary(root=tmp_path)
    latest_df = load_feeder_review_source_df("passes", root=tmp_path)

    assert latest_summary["active_supplier_id"] == "stocklist_supplier"
    assert set(latest_df["asin"]) == {"B082NMTZC2"}
    assert "B09HKZWBDN" not in set(latest_df["asin"])


def test_feeder_review_window_scopes_latest_decisions_by_run_and_pack(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "50",
                "candidate_id": "cand-shared",
                "supplier_sku": "SKU-1",
                "asin": "B000000001",
                "title": "Run 1 row",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-2",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "40",
                "candidate_id": "cand-shared",
                "supplier_sku": "SKU-2",
                "asin": "B000000002",
                "title": "Run 2 row",
            },
        ]
    ).to_csv(report_path, index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-04-22T15:00:00Z",
                "event_id": "evt-run1",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-shared",
                "supplier_sku": "SKU-1",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "pass",
                "review_note": "done",
                "actor": "tester",
                "source_reference": "test",
                "title": "Run 1 row",
                "brand": "",
                "main_rank": "",
                "review_priority_score": "50",
            }
        ],
    )

    window_df, meta = build_feeder_review_window_df("passes", root=tmp_path)

    assert meta["undecided_rows"] == 1
    assert len(window_df.index) == 1
    assert window_df.iloc[0]["candidate_id"] == "cand-shared"
    assert window_df.iloc[0]["active_run_id"] == "run-2"


def test_feeder_review_window_keeps_source_order_before_limit(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "10",
                "candidate_id": "cand-low",
                "supplier_sku": "SKU-LOW",
                "asin": "B000000010",
                "title": "Low",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "200",
                "candidate_id": "cand-high",
                "supplier_sku": "SKU-HIGH",
                "asin": "B000000200",
                "title": "High",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "50",
                "candidate_id": "cand-mid",
                "supplier_sku": "SKU-MID",
                "asin": "B000000050",
                "title": "Mid",
            },
        ]
    ).to_csv(report_path, index=False)

    window_df, _ = build_feeder_review_window_df("passes", root=tmp_path, page_size=3)

    assert list(window_df["candidate_id"]) == ["cand-low", "cand-high", "cand-mid"]


def test_feeder_review_done_key_is_scoped_to_view_filters() -> None:
    key_a = _feeder_review_done_key(
        pack_type="passes",
        supplier_filter="stocklist_supplier",
        review_batch_id="pass_batch_001",
        search_text="",
    )
    key_b = _feeder_review_done_key(
        pack_type="passes",
        supplier_filter="stocklist_supplier",
        review_batch_id="pass_batch_002",
        search_text="",
    )
    key_c = _feeder_review_done_key(
        pack_type="passes",
        supplier_filter="another_supplier",
        review_batch_id="pass_batch_001",
        search_text="",
    )

    assert key_a != key_b
    assert key_a != key_c


def test_feeder_review_ui_draft_save_restore_and_clear(tmp_path: Path) -> None:
    save_result = save_feeder_review_ui_drafts(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin": "B000000001",
                "title": "Title A",
                "main_rank": "120",
                "review_priority_score": "90",
                "review_decision": "pass",
                "review_reason_code": "profit_too_weak",
                "review_note": "looks good",
                "row_done": True,
                "country_of_origin": "GB",
                "product_tax_code": "A_GEN_STANDARD",
                "currency_code": "GBP",
                "price_includes_tax": "1",
                "starting_price_gbp": "12.34",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-b",
                "supplier_sku": "SKU-B",
                "asin": "B000000002",
                "title": "Title B",
                "main_rank": "220",
                "review_priority_score": "80",
                "review_decision": "",
                "review_note": "",
                "row_done": False,
            },
        ],
        supplier_filter="stocklist_supplier",
        review_batch_id="pass_batch_001",
        search_text="controller",
    )
    assert save_result["rows_saved"] == 1
    drafts_df = load_feeder_review_ui_drafts_df(root=tmp_path)
    assert len(drafts_df.index) == 1
    row = drafts_df.iloc[0]
    assert row["candidate_id"] == "cand-a"
    assert row["draft_decision"] == "pass"
    assert row["draft_reason_code"] == "profit_too_weak"
    assert row["draft_note"] == "looks good"
    assert row["draft_done"] == "1"
    assert row["draft_country_of_origin"] == "GB"
    assert row["draft_product_tax_code"] == "A_GEN_STANDARD"
    assert row["draft_currency_code"] == "GBP"
    assert row["draft_price_includes_tax"] == "1"
    assert row["draft_starting_price_gbp"] == "12.34"

    clear_result = clear_feeder_review_ui_drafts(
        root=tmp_path,
        rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "candidate_id": "cand-a",
            }
        ],
    )
    assert clear_result["rows_removed"] == 1
    drafts_after_clear = load_feeder_review_ui_drafts_df(root=tmp_path)
    assert len(drafts_after_clear.index) == 0


def test_feeder_review_event_and_draft_logs_read_sql_when_csv_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))
    save_feeder_review_ui_drafts(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-draft",
                "supplier_sku": "SKU-D",
                "asin": "B000000001",
                "title": "Draft Title",
                "review_decision": "pass",
                "review_reason_code": "seller_controlled",
                "review_note": "draft note",
                "row_done": True,
            }
        ],
        supplier_filter="stocklist_supplier",
        review_batch_id="pass_batch_001",
        search_text="",
    )
    submit_feeder_review_batch(
        root=tmp_path,
        reviewed_rows=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-event",
                "supplier_sku": "SKU-E",
                "asin": "B000000002",
                "title": "Event Title",
                "review_decision": "fail",
                "review_reason_code": "missing_evidence",
                "review_note": "event note",
            }
        ],
    )
    (tmp_path / get_o_output_contract("feeder_review_ui_drafts").rel_path).unlink()
    (tmp_path / get_f_output_contract("feeder_review_events").rel_path).unlink()

    drafts_df = load_feeder_review_ui_drafts_df(root=tmp_path)
    events_df = load_feeder_review_events_df(root=tmp_path)

    assert drafts_df.iloc[0]["candidate_id"] == "cand-draft"
    assert drafts_df.iloc[0]["draft_reason_code"] == "seller_controlled"
    assert events_df.iloc[0]["candidate_id"] == "cand-event"
    assert events_df.iloc[0]["review_reason_code"] == "missing_evidence"


def test_feeder_review_widget_key_is_scoped_to_pack_and_run() -> None:
    row_a = {
        "active_supplier_id": "stocklist_supplier",
        "active_run_id": "run-1",
        "candidate_id": "cand-1",
    }
    row_b = {
        "active_supplier_id": "stocklist_supplier",
        "active_run_id": "run-2",
        "candidate_id": "cand-1",
    }
    key_a = _review_widget_key(row_a, pack_type="passes")
    key_b = _review_widget_key(row_b, pack_type="passes")
    key_c = _review_widget_key(row_a, pack_type="near_misses")
    assert key_a != key_b
    assert key_a != key_c


def test_feeder_review_sent_df_returns_latest_decisions_only(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "90",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin": "B000000001",
                "title": "A",
            }
        ]
    ).to_csv(report_path, index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-04-22T15:00:00Z",
                "event_id": "evt-a",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "fail",
                "review_note": "bad listing",
                "actor": "tester",
                "source_reference": "test",
                "title": "A",
                "brand": "",
                "main_rank": "",
                "review_priority_score": "90",
            }
        ],
    )

    sent_df = build_feeder_review_sent_df("passes", root=tmp_path, page_size=10)

    assert len(sent_df.index) == 1
    assert sent_df.iloc[0]["candidate_id"] == "cand-a"
    assert sent_df.iloc[0]["latest_review_decision"] == "fail"
    assert sent_df.iloc[0]["latest_review_note"] == "bad listing"


def test_feeder_review_reopen_batch_restores_candidate_to_undecided(tmp_path: Path) -> None:
    report_path = tmp_path / "out" / "analysis_reports" / "f_live_price_file_pass_review_latest.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "review_priority_score": "90",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin": "B000000001",
                "title": "A",
            }
        ]
    ).to_csv(report_path, index=False)
    _write_f_contract_rows(
        tmp_path,
        "feeder_review_events",
        [
            {
                "event_utc": "2026-04-22T15:00:00Z",
                "event_id": "evt-a",
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin_raw": "B000000001",
                "asin_padded": "B000000001",
                "amazon_dp_url": "https://www.amazon.co.uk/dp/B000000001",
                "review_decision": "pass",
                "review_note": "ok",
                "actor": "tester",
                "source_reference": "test",
                "title": "A",
                "brand": "",
                "main_rank": "",
                "review_priority_score": "90",
            }
        ],
    )

    before_df, before_meta = build_feeder_review_window_df("passes", root=tmp_path)
    assert before_meta["undecided_rows"] == 0
    assert before_df.empty

    reopen_result = submit_feeder_review_reopen_batch(
        root=tmp_path,
        rows_to_reopen=[
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-a",
                "supplier_sku": "SKU-A",
                "asin": "B000000001",
                "title": "A",
                "brand": "",
                "main_rank": "",
                "review_priority_score": "90",
            }
        ],
    )
    assert reopen_result["events_applied"] == 1

    after_df, after_meta = build_feeder_review_window_df("passes", root=tmp_path)
    assert after_meta["undecided_rows"] == 1
    assert len(after_df.index) == 1
    assert after_df.iloc[0]["candidate_id"] == "cand-a"


def test_reorder_input_df_leaves_qty_and_price_blank_but_keeps_suggestions_visible(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-R1",
                "asin": "ASIN-R1",
                "title": "Row Product",
                "main_image": "https://example.com/r1.jpg",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "12",
                "suggested_unit_cost_gbp": "5.5",
                "suggested_market_price_gbp": "8",
                "expected_forward_roi_pct": "60",
                "expected_forward_profit_per_unit_gbp": "3",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "confidence_note": "",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "snooze_until_utc": "",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    reorder_df = build_reorder_input_df(datasets)
    assert len(reorder_df) == 1
    row = reorder_df.iloc[0]
    assert row["seller_sku"] == "SKU-R1"
    assert row["order_qty"] == ""
    assert row["confirmed_price"] == ""
    assert row["restk"] == "12"
    assert row["cpu"] == "5.5"
    assert row["row_status"] == "needs_price"
    assert bool(row["send"]) is False


def test_reorder_input_df_uses_pack_profile_for_operator_qty_and_lookup_fields(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-RPACK",
                "asin": "ASIN-RPACK",
                "title": "Pack Product",
                "main_image": "https://example.com/rpack.jpg",
                "supplier_code": "SUP-P",
                "supplier_name": "Gamma",
                "recommendation_status": "full_restock",
                "suggested_qty": "60",
                "suggested_unit_cost_gbp": "5.5",
                "suggested_market_price_gbp": "8",
                "expected_forward_roi_pct": "60",
                "expected_forward_profit_per_unit_gbp": "3",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "confidence_note": "",
                "cost_mode": "test",
                "recommendation_basis": "test_cost_snapshot",
                "snooze_until_utc": "",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-RPACK",
                "asin": "ASIN-RPACK",
                "supplier_code": "SUP-P",
                "supplier_name": "Gamma",
                "sale_status": "active",
                "available_now": "7",
                "total_quantity_now": "9",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "2.2",
                "velocity_30d": "2.0",
                "velocity_90d": "1.9",
                "current_supplier_buy_cost_gbp": "5.5",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "8.0",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0.1",
                "roi_at_market_price_pct": "60",
                "source_inventory_asof": "2026-04-03T09:00:00Z",
                "source_velocity_asof": "2026-04-03",
                "source_performance_asof": "2026-04-03",
                "supplier_sku": "GAMMA-RAW-20",
                "barcode": "1234567890123",
                "amazon_pack_size": "3",
                "pack_conversion_note": "repack into packs of 3",
                "order_qty_mode": "sell_packs",
                "order_qty_unit_label": "Packs",
                "sell_pack_qty": "3",
                "supplier_case_qty": "20",
                "supplier_case_multiple": "1",
                "valid_order_step": "20",
                "repack_required": "1",
                "bundle_required": "0",
                "display_qtys_label": "Pack 3 | Case 20 | Step 20",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    reorder_df = build_reorder_input_df(datasets)
    assert len(reorder_df) == 1
    row = reorder_df.iloc[0]
    assert row["qtys"] == "Pack 3 | Case 20 | Step 20"
    assert row["barcode"] == "1234567890123"
    assert row["supply_code"] == "GAMMA-RAW-20"
    assert row["order_qty"] == ""
    assert row["restk"] == "20pk (60)"
    assert row["order_qty_mode"] == "sell_packs"
    assert row["order_qty_unit_label"] == "Packs"
    assert row["row_status"] == "needs_price"


def test_reorder_input_df_shows_legacy_bridge_rows_before_native_duplicates(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "legacy_purchase_list_bridge",
        [
            {
                "bridge_utc": "2026-05-22T10:00:00Z",
                "source_system": "legacy_purchase_list",
                "source_sheet_id": "sheet-1",
                "source_sheet_title": "Amazon Supplier Process",
                "source_tab": "Purchase List",
                "source_row_number": "7",
                "source_reference": "legacy_purchase_list:sheet-1:Purchase List:row7",
                "supplier_name": "Legacy Supplier",
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "title": "Bridge Product",
                "display_qtys_label": "Unit",
                "barcode": "5000000000001",
                "supplier_sku": "SUPPLY-7",
                "suggested_action": "full_restock",
                "recommendation_status": "full_restock",
                "sheet_recommend_label": "Restock",
                "suggested_qty": "8",
                "recommended_qty_rounded": "8",
                "current_supplier_buy_cost_gbp": "2.5",
                "suggested_unit_cost_gbp": "2.5",
                "suggested_market_price_gbp": "4",
                "market_price_gbp": "4",
                "expected_forward_roi_pct": "60",
                "forward_roi_pct": "60",
                "forward_profit_per_unit_gbp": "1.5",
                "ordered_open": "2",
                "available_now": "0",
                "velocity_30d": "1.2",
                "days_cover_available_only": "0",
                "queue_status": "needs_review",
                "cost_mode": "legacy_sheet",
                "recommendation_basis": "legacy_purchase_list_restock",
                "bridge_status": "ready",
                "bridge_note": "LEGACY_PURCHASE_LIST_RESTOCK|NATIVE_O_PARITY_PENDING",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-05-22T10:01:00Z",
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "supplier_code": "NATIVE",
                "supplier_name": "Native Supplier",
                "recommendation_status": "wait",
                "suggested_qty": "0",
                "suggested_unit_cost_gbp": "9",
                "suggested_market_price_gbp": "10",
                "expected_forward_roi_pct": "1",
                "expected_forward_profit_per_unit_gbp": "1",
                "days_cover_available_only": "99",
                "days_cover_total_pipeline": "99",
                "reason_codes": "NATIVE_STALE_WAIT",
                "queue_status": "needs_review",
                "suggested_action": "wait",
                "key_reason": "NATIVE_STALE_WAIT",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "queue_utc": "2026-05-22T10:01:00Z",
                "seller_sku": "SKU-NATIVE",
                "asin": "ASIN-NATIVE",
                "supplier_code": "NATIVE",
                "supplier_name": "Native Supplier",
                "recommendation_status": "full_restock",
                "suggested_qty": "3",
                "suggested_unit_cost_gbp": "5",
                "suggested_market_price_gbp": "8",
                "expected_forward_roi_pct": "60",
                "expected_forward_profit_per_unit_gbp": "3",
                "days_cover_available_only": "1",
                "days_cover_total_pipeline": "1",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ],
    )
    _write_contract_rows(
        tmp_path,
        "product_db_operator_view",
        [
            {
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "title": "Bridge Product",
                "main_image": "https://example.com/bridge.jpg",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-05-22T10:01:00Z",
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "supplier_code": "LEGACY",
                "supplier_name": "Legacy Supplier",
                "sale_status": "active",
                "current_supplier_buy_cost_gbp": "2.4",
                "price_list_unit_cost_gbp": "2.4",
                "price_list_unit_code": "PK8",
                "price_list_pack_size": "8",
                "price_list_pack_cost_gbp": "19.20",
                "price_list_moq": "8",
                "supplier_pack_size": "8",
                "moq": "8",
                "order_qty_mode": "sell_packs",
                "order_qty_unit_label": "Packs",
                "sell_pack_qty": "8",
                "supplier_case_qty": "8",
                "supplier_case_multiple": "1",
                "valid_order_step": "8",
                "display_qtys_label": "Pack 8 | Case 8",
                "pack_conversion_note": "Supplier list PK8",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_profit_checks_live",
        [
            {
                "check_utc": "2026-05-22T10:02:00Z",
                "seller_sku": "SKU-BRIDGE",
                "asin": "ASIN-BRIDGE",
                "supplier_name": "Legacy Supplier",
                "suggested_action": "full_restock",
                "profit_verdict": "safe_to_review",
                "profit_proof_source": "legacy_sheet_profit_hint",
                "profit_check_message": "Profit check: Review - Sheet ROI hint only.",
                "current_sell_price_gbp": "4",
                "sell_price_basis": "LEGACY_PURCHASE_LIST_ROI_BACKSOLVE",
                "supplier_cost_gbp": "2.5",
                "fee_drag_gbp": "",
                "refund_drag_gbp": "",
                "forward_profit_per_unit_gbp": "1.5",
                "forward_roi_pct": "60",
                "break_even_max_cost_gbp": "",
                "target_roi_max_cost_gbp": "",
                "target_roi_pct": "10",
                "demand_status": "demand_present",
                "demand_units_per_day": "1.2",
                "days_cover_available_only": "0",
                "effective_supply_units": "2",
                "recommended_qty": "8",
                "missing_input_reasons": "",
                "guardrail_flags": "legacy_sheet_profit_not_native_proof",
                "bad_economics_snapshot_count": "0",
                "bad_economics_window_days": "0",
                "drop_review_eligible": "0",
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:sheet-1:Purchase List:row7",
                "price_list_unit_cost_gbp": "2.4",
                "price_list_source_received_at_utc": "2026-05-22T07:30:00Z",
                "cost_match_method": "barcode_supplier_matched",
                "cost_confidence": "price_list_actual_match",
                "supplier_cost_review_reason": "",
                "expected_cost_source": "supplier_price_list_no_discount",
                "actual_paid_unit_cost_gbp": "2.5",
                "price_list_vs_actual_paid_delta_gbp": "-0.1",
                "price_list_vs_purchase_reference_delta_gbp": "-0.1",
                "price_proof_summary": "Current supplier list GBP 2.4; matched by barcode supplier matched",
            }
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    reorder_df = build_reorder_input_df(datasets)

    assert list(reorder_df["seller_sku"]) == ["SKU-BRIDGE", "SKU-NATIVE"]
    bridge = reorder_df.iloc[0]
    assert bridge["source_system"] == "legacy_purchase_list"
    assert bridge["source_reference"] == "legacy_purchase_list:sheet-1:Purchase List:row7"
    assert bridge["supplier_name"] == "Legacy Supplier"
    assert bridge["supply_code"] == "SUPPLY-7"
    assert bridge["barcode"] == "5000000000001"
    assert bridge["qtys"] == "Pack 8 | Case 8"
    assert bridge["restk"] == "1pk (8)"
    assert bridge["order_qty_mode"] == "sell_packs"
    assert bridge["order_qty_unit_label"] == "Packs"
    assert bridge["sell_pack_qty"] == "8"
    assert bridge["cpu"] == "2.4"
    assert bridge["recommend"] == "Restock"
    assert bridge["main_image"] == "https://example.com/bridge.jpg"
    assert bridge["profit_verdict"] == "safe_to_review"
    assert bridge["profit_proof_source"] == "legacy_sheet_profit_hint"
    assert bridge["profit_guardrail_flags"] == "legacy_sheet_profit_not_native_proof"
    assert bridge["price_list_unit_cost_gbp"] == "2.4"
    assert bridge["cost_match_method"] == "barcode_supplier_matched"
    assert "Current supplier list GBP 2.4" in bridge["price_proof_summary"]


def test_profit_check_badge_keeps_long_explanation_in_hover_panel() -> None:
    badge_html = _profit_check_badge_html(
        {
            "profit_verdict": "needs_price_check",
            "profit_proof_source": "legacy_sheet_profit_hint",
            "profit_check_message": "Needs price check before this is a clean buy.",
            "profit_guardrail_flags": (
                "legacy_sheet_profit_not_native_proof|legacy_roi_backsolved_from_sheet|"
                "supplier_cost_confirmation_required"
            ),
            "price_proof_summary": (
                "No current supplier list match; confidence actual paid without list reference; "
                "old paid GBP 7.59; check reason missing current price list cost"
            ),
            "expected_forward_roi_pct": "36",
            "forward_profit_per_unit_gbp": "2.73",
            "current_sell_price_gbp": "15.18",
            "cpu": "7.59",
        }
    )

    assert "Profit: check price" in badge_html
    assert "o-hover-wrap" in badge_html
    assert "o-hover-panel" in badge_html
    assert "Needs price check before this is a clean buy." in badge_html
    assert "Sheet ROI hint only" in badge_html
    assert "Guardrail:" in badge_html
    assert "Price proof:" in badge_html
    assert "<strong>" not in badge_html
    assert "<br>" not in badge_html


def test_reorder_input_df_adds_open_ordered_qty_from_ordered_stock_state(tmp_path: Path) -> None:
    _write_contract_rows(
        tmp_path,
        "restock_review_queue",
        [
            {
                "queue_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-ONORDER",
                "asin": "ASIN-ONORDER",
                "title": "Open Ordered Product",
                "main_image": "",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "recommendation_status": "full_restock",
                "suggested_qty": "10",
                "suggested_unit_cost_gbp": "2.5",
                "suggested_market_price_gbp": "5",
                "expected_forward_roi_pct": "40",
                "expected_forward_profit_per_unit_gbp": "1",
                "days_cover_available_only": "2",
                "days_cover_total_pipeline": "3",
                "reason_codes": "ROI_OK",
                "queue_status": "needs_review",
                "suggested_action": "full_restock",
                "key_reason": "ROI_OK",
                "confidence_note": "",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
                "snooze_until_utc": "",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "restock_source_view",
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "seller_sku": "SKU-ONORDER",
                "asin": "ASIN-ONORDER",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "sale_status": "active",
                "available_now": "4",
                "total_quantity_now": "4",
                "amazon_inbound_working": "0",
                "amazon_inbound_shipped": "0",
                "amazon_inbound_receiving": "0",
                "velocity_7d": "1",
                "velocity_30d": "1",
                "velocity_90d": "1",
                "current_supplier_buy_cost_gbp": "2.5",
                "current_supplier_cost_source": "supplier_catalog_price",
                "market_price_gbp": "5",
                "market_price_basis_used": "BUY_BOX_PRICE",
                "expected_refund_cost_per_unit_gbp": "0",
                "roi_at_market_price_pct": "40",
                "source_inventory_asof": "2026-04-03T09:00:00Z",
                "source_velocity_asof": "2026-04-03",
                "source_performance_asof": "2026-04-03",
            }
        ],
    )
    _write_contract_rows(
        tmp_path,
        "ordered_stock_state",
        [
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "po_id": "PO-1",
                "po_line_id": "PO-1-L001",
                "seller_sku": "SKU-ONORDER",
                "asin": "ASIN-ONORDER",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "ordered_qty": "7",
                "received_qty": "2",
                "remaining_open_qty": "5",
                "receipt_status": "partial_received",
                "expected_arrival_utc": "2026-04-10T00:00:00Z",
                "backorder_flag": "0",
                "source_event_id": "evt-1",
                "source_decision_action": "approve_full_restock",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
            {
                "asof_utc": "2026-04-03T10:00:00Z",
                "po_id": "PO-2",
                "po_line_id": "PO-2-L001",
                "seller_sku": "SKU-ONORDER",
                "asin": "ASIN-ONORDER",
                "supplier_code": "SUP-A",
                "supplier_name": "Alpha",
                "ordered_qty": "4",
                "received_qty": "0",
                "remaining_open_qty": "4",
                "receipt_status": "not_received",
                "expected_arrival_utc": "2026-04-11T00:00:00Z",
                "backorder_flag": "0",
                "source_event_id": "evt-2",
                "source_decision_action": "approve_test_restock",
                "cost_mode": "live",
                "recommendation_basis": "live_cost_inputs",
            },
        ],
    )

    datasets = load_operator_datasets(root=tmp_path)
    reorder_df = build_reorder_input_df(datasets)
    row = reorder_df.iloc[0]
    assert row["stock"] == "4"
    assert row["ordered_open"] == "9"


def test_reorder_batch_submits_selected_rows_to_decision_inbox(tmp_path: Path) -> None:
    rows_df = pd.DataFrame(
        [
            {
                "send": True,
                "seller_sku": "SKU-B1",
                "asin": "ASIN-B1",
                "suggested_action": "full_restock",
                "order_qty": "9",
                "confirmed_price": "4.2",
                "disc": False,
                "drop": False,
                "snze": False,
                "snooze_date": "",
                "cost_mode": "test",
                "recommendation_reason": "ROI_OK",
                "decision_note": "batch submit",
                "source_system": "legacy_purchase_list",
                "source_reference": "legacy_purchase_list:sheet-1:Purchase List:row7",
                "profit_verdict": "safe_to_review",
                "profit_proof_source": "legacy_sheet_profit_hint",
            },
            {
                "send": True,
                "seller_sku": "SKU-B2",
                "asin": "ASIN-B2",
                "suggested_action": "test_restock",
                "order_qty": "",
                "confirmed_price": "",
                "disc": False,
                "drop": False,
                "snze": False,
                "snooze_date": "",
                "cost_mode": "live",
                "recommendation_reason": "needs info",
                "decision_note": "",
            },
            {
                "send": True,
                "seller_sku": "SKU-B3",
                "asin": "ASIN-B3",
                "suggested_action": "wait",
                "order_qty": "",
                "confirmed_price": "",
                "disc": False,
                "drop": False,
                "snze": True,
                "snooze_date": "2026-04-10",
                "cost_mode": "live",
                "recommendation_reason": "snooze it",
                "decision_note": "",
            },
        ]
    )

    result = submit_reorder_batch(root=tmp_path, rows_df=rows_df, actor="tester", source_reference="batch_test")
    assert result["events_applied"] == 2
    assert len(result["skipped_rows"]) == 1
    assert "SKU-B2:missing_qty_or_price" in result["skipped_rows"]

    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 2
    first = inbox_df[inbox_df["seller_sku"] == "SKU-B1"].iloc[0]
    snoozed = inbox_df[inbox_df["seller_sku"] == "SKU-B3"].iloc[0]
    assert first["action"] == "approve_full_restock"
    assert first["confirmed_qty"] == "9"
    assert first["confirmed_unit_cost"] == "4.2"
    assert first["actor"] == "tester"
    assert first["source_reference"] == "batch_test|legacy_purchase_list|legacy_purchase_list:sheet-1:Purchase List:row7"
    assert first["profit_verdict"] == "safe_to_review"
    assert first["profit_proof_source"] == "legacy_sheet_profit_hint"
    assert snoozed["action"] == "snooze"
    assert snoozed["snooze_until_utc"] == "2026-04-10T00:00:00Z"


def test_reorder_batch_converts_operator_pack_qty_back_to_raw_units(tmp_path: Path) -> None:
    rows_df = pd.DataFrame(
        [
            {
                "send": True,
                "seller_sku": "SKU-PACK-B1",
                "asin": "ASIN-PACK-B1",
                "suggested_action": "full_restock",
                "order_qty": "20",
                "confirmed_price": "4.2",
                "disc": False,
                "drop": False,
                "snze": False,
                "snooze_date": "",
                "cost_mode": "test",
                "recommendation_reason": "ROI_OK",
                "decision_note": "pack submit",
                "order_qty_mode": "sell_packs",
                "sell_pack_qty": "3",
                "amazon_pack_size": "3",
            }
        ]
    )

    result = submit_reorder_batch(root=tmp_path, rows_df=rows_df, actor="tester", source_reference="batch_test")
    assert result["events_applied"] == 1
    assert result["skipped_rows"] == []

    inbox_path = tmp_path / get_o_output_contract("restock_decision_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df) == 1
    row = inbox_df.iloc[0]
    assert row["seller_sku"] == "SKU-PACK-B1"
    assert row["confirmed_qty"] == "60"
    assert row["confirmed_unit_cost"] == "4.2"


def test_reorder_price_safety_blocks_over_max_submit_and_renders_hover() -> None:
    row = {
        "seller_sku": "SKU-PRICE",
        "suggested_action": "full_restock",
        "max_safe_unit_cost_gbp": "1.90",
        "price_list_unit_cost_gbp": "2.00",
        "usual_paid_unit_cost_gbp": "1.70",
        "price_status": "caution_usual_paid_under_list",
        "price_status_message": "usual paid is under list",
        "price_proof_summary": "usual paid GBP 1.70; max safe buy cost GBP 1.90",
    }
    under = _confirmed_price_safety(row, "1.70")
    over = _confirmed_price_safety(row, "2.00")
    chips = _price_proof_chips_html(row, "2.00")

    assert under["status"] == "confirmed_under_max"
    assert over["status"] == "confirmed_over_max_blocked"
    assert over["blocked"] == "1"
    assert "Max pay" in chips
    assert "Blocked" in chips


def test_reorder_submit_blocks_typed_price_above_max(tmp_path: Path) -> None:
    rows_df = pd.DataFrame(
        [
            {
                "send": True,
                "seller_sku": "SKU-OVER-MAX",
                "asin": "ASIN-OVER-MAX",
                "suggested_action": "full_restock",
                "order_qty": "2",
                "confirmed_price": "2.00",
                "max_safe_unit_cost_gbp": "1.90",
                "price_list_unit_cost_gbp": "2.00",
                "usual_paid_unit_cost_gbp": "1.70",
                "price_list_change_status": "cost_up",
                "price_status": "over_max_snooze_candidate",
                "price_status_message": "Current expected cost is above Max pay.",
                "disc": False,
                "drop": False,
                "snze": False,
                "snooze_date": "",
                "cost_mode": "live",
            }
        ]
    )

    result = submit_reorder_batch(root=tmp_path, rows_df=rows_df, actor="tester", source_reference="batch_test")

    assert result["events_applied"] == 0
    assert result["skipped_rows"] == ["SKU-OVER-MAX:confirmed_price_above_max_safe_cost"]


def test_price_list_lookup_searches_change_log_and_cost_truth() -> None:
    datasets = {
        "supplier_price_list_change_log_live": pd.DataFrame(
            [
                {
                    "supplier_name": "ABGee",
                    "supplier_sku": "985 49830",
                    "barcode": "889698498302",
                    "title": "Leatherface",
                    "change_status": "cost_up",
                    "current_unit_cost_gbp": "7.59",
                    "current_pack_size": "12",
                    "current_pack_cost_gbp": "91.08",
                    "current_source_batch_id": "abgee_20260522",
                }
            ]
        ),
        "supplier_buy_cost_truth": pd.DataFrame(),
    }

    result = build_price_list_lookup_results(datasets, query="889698498302", supplier_filter="ABGee")

    assert len(result.index) == 1
    assert result.iloc[0]["supply_code"] == "985 49830"
    assert result.iloc[0]["pack_size"] == "12"


def test_filter_reorder_rows_defaults_to_actionable_and_sorts_by_supplier() -> None:
    reorder_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-WAIT",
                "title": "Wait product",
                "asin": "ASIN-WAIT",
                "supplier_name": "Zulu",
                "suggested_action": "wait",
                "row_status": "blocked",
            },
            {
                "seller_sku": "SKU-READY-A",
                "title": "Ready A",
                "asin": "ASIN-RA",
                "supplier_name": "Alpha",
                "suggested_action": "full_restock",
                "row_status": "ready",
            },
            {
                "seller_sku": "SKU-READY-Z",
                "title": "Ready Z",
                "asin": "ASIN-RZ",
                "supplier_name": "Zulu",
                "suggested_action": "test_restock",
                "row_status": "needs_price",
            },
        ]
    )
    filtered = filter_reorder_rows(reorder_df)
    assert list(filtered["seller_sku"]) == ["SKU-READY-A", "SKU-READY-Z"]
    assert "_supplier_label" in filtered.columns
    assert filtered.iloc[0]["_supplier_label"] == "Alpha"
    assert filtered.iloc[1]["_supplier_label"] == "Zulu"


def test_filter_reorder_rows_supplier_and_search_filters() -> None:
    reorder_df = pd.DataFrame(
        [
            {
                "seller_sku": "SKU-A1",
                "title": "Toothpaste Kids",
                "asin": "ASIN-A1",
                "supplier_name": "Alpha",
                "suggested_action": "full_restock",
                "row_status": "ready",
            },
            {
                "seller_sku": "SKU-B1",
                "title": "Protein Shake",
                "asin": "ASIN-B1",
                "supplier_name": "Beta",
                "suggested_action": "test_restock",
                "row_status": "ready",
            },
        ]
    )
    filtered = filter_reorder_rows(
        reorder_df,
        supplier_filter="Beta",
        search_text="protein",
    )
    assert len(filtered.index) == 1
    row = filtered.iloc[0]
    assert row["seller_sku"] == "SKU-B1"
    assert row["_supplier_label"] == "Beta"


def test_o_ui_loads_current_backtest_policy_values(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            {
                "observed_utc": "2026-04-10T14:40:00Z",
                "policy_id": "f_backtest_policy_v1",
                "policy_version": "1.0",
                "policy_status": "active",
                "minimum_expected_profit_gbp": "100",
                "entry_target_roi_pct": "20",
                "working_floor_roi_pct": "10",
                "exit_floor_roi_pct": "0",
                "emergency_floor_roi_pct": "-5",
                "recency_weight_30d": "0.5",
                "recency_weight_90d": "0.3",
                "recency_weight_180d": "0.15",
                "recency_weight_365d": "0.05",
                "ceiling_warn_ratio_30d": "1.25",
                "ceiling_red_ratio_30d": "1.5",
                "ceiling_extreme_ratio_30d": "2",
                "shock_trigger_pct_1d": "20",
                "shared_sales_default_pct": "50",
                "policy_source": "system_default_v1",
                "notes": "",
            }
        ],
    )
    row = load_backtest_policy_live_row(root=tmp_path)
    assert row["policy_id"] == "f_backtest_policy_v1"
    assert row["minimum_expected_profit_gbp"] == "100"
    assert row["entry_target_roi_pct"] == "20"
    assert row["working_floor_roi_pct"] == "10"
    assert row["exit_floor_roi_pct"] == "0"
    assert row["emergency_floor_roi_pct"] == "-5"


def test_o_ui_policy_update_submission_writes_f_inbox_event(tmp_path: Path) -> None:
    _write_f_contract_rows(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            {
                "observed_utc": "2026-04-10T14:40:00Z",
                "policy_id": "f_backtest_policy_v1",
                "policy_version": "1.0",
                "policy_status": "active",
                "minimum_expected_profit_gbp": "100",
                "entry_target_roi_pct": "20",
                "working_floor_roi_pct": "10",
                "exit_floor_roi_pct": "0",
                "emergency_floor_roi_pct": "-5",
                "recency_weight_30d": "0.5",
                "recency_weight_90d": "0.3",
                "recency_weight_180d": "0.15",
                "recency_weight_365d": "0.05",
                "ceiling_warn_ratio_30d": "1.25",
                "ceiling_red_ratio_30d": "1.5",
                "ceiling_extreme_ratio_30d": "2",
                "shock_trigger_pct_1d": "20",
                "shared_sales_default_pct": "50",
                "policy_source": "system_default_v1",
                "notes": "",
            }
        ],
    )

    out_row = submit_backtest_policy_update_event(
        root=tmp_path,
        policy_values={
            "minimum_expected_profit_gbp": "120",
            "entry_target_roi_pct": "22",
            "working_floor_roi_pct": "12",
            "exit_floor_roi_pct": "2",
            "emergency_floor_roi_pct": "-3",
        },
        actor="tester",
        source_reference="o_ui_test",
        decision_note="manual operator update",
    )
    inbox_path = tmp_path / get_f_output_contract("feeder_backtest_policy_update_events").rel_path
    inbox_df = pd.read_csv(inbox_path, dtype=str).fillna("")
    assert len(inbox_df.index) == 1
    row = inbox_df.iloc[0]
    assert row["event_id"].startswith("o-ui-f-policy-")
    assert row["policy_id"] == "f_backtest_policy_v1"
    assert row["action"] == "apply"
    assert row["minimum_expected_profit_gbp"] == "120"
    assert row["entry_target_roi_pct"] == "22"
    assert row["working_floor_roi_pct"] == "12"
    assert row["exit_floor_roi_pct"] == "2"
    assert row["emergency_floor_roi_pct"] == "-3"
    assert row["actor"] == "tester"
    assert row["source_reference"] == "o_ui_test"
    assert row["decision_note"] == "manual operator update"
    assert out_row["event_id"] == row["event_id"]


def test_o_ui_policy_value_validation_handles_empty_and_invalid_inputs() -> None:
    _, errors = validate_backtest_policy_values(
        {
            "minimum_expected_profit_gbp": "",
            "entry_target_roi_pct": "abc",
            "working_floor_roi_pct": "10",
            "exit_floor_roi_pct": "0",
            "emergency_floor_roi_pct": "-5",
        }
    )
    assert len(errors) >= 2
    assert any("minimum_expected_profit_gbp is required" in error for error in errors)
    assert any("entry_target_roi_pct must be numeric" in error for error in errors)

    _, ordering_errors = validate_backtest_policy_values(
        {
            "minimum_expected_profit_gbp": "100",
            "entry_target_roi_pct": "10",
            "working_floor_roi_pct": "20",
            "exit_floor_roi_pct": "5",
            "emergency_floor_roi_pct": "0",
        }
    )
    assert len(ordering_errors) == 1
    assert "ROI ordering must be" in ordering_errors[0]


def test_o_ui_calibration_loader_reads_latest_and_selects_flagged_rows(tmp_path: Path) -> None:
    cal_path = tmp_path / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv"
    cal_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "seller_sku": "SKU-A",
                "asin": "ASIN-A",
                "recommendation": "Normal fit",
                "amazon_risk_level": "low",
                "market_viability_score": "80",
                "exit_risk_score": "20",
                "calibration_review_flag": "0",
                "calibration_review_reason": "",
            },
            {
                "seller_sku": "SKU-B",
                "asin": "ASIN-B",
                "recommendation": "Exit-only",
                "amazon_risk_level": "critical",
                "market_viability_score": "42",
                "exit_risk_score": "70",
                "calibration_review_flag": "1",
                "calibration_review_reason": "critical_amazon_recommendation_mismatch",
            },
        ]
    ).to_csv(cal_path, index=False)

    cal_df = load_backtest_calibration_df(root=tmp_path)
    assert len(cal_df.index) == 2
    flagged_df = select_flagged_backtest_calibration_rows(cal_df)
    assert len(flagged_df.index) == 1
    flagged_row = flagged_df.iloc[0]
    assert flagged_row["seller_sku"] == "SKU-B"
    assert flagged_row["calibration_review_flag"] == "1"


def test_o_ui_calibration_loader_handles_missing_file_gracefully(tmp_path: Path) -> None:
    cal_df = load_backtest_calibration_df(root=tmp_path)
    assert cal_df.empty
    assert set(cal_df.columns) == {
        "seller_sku",
        "asin",
        "recommendation",
        "amazon_risk_level",
        "market_viability_score",
        "exit_risk_score",
        "calibration_review_flag",
        "calibration_review_reason",
    }
