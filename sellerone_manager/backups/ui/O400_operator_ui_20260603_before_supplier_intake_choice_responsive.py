from __future__ import annotations

import csv
import html
import json
import re
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict
from urllib.parse import quote

BOOT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOT_ROOT))

import pandas as pd

try:
    from scripts.flows.O.O410_product_database_ui import render_product_database_ui
    from scripts.flows.O.O420_product_database_edit_ui import render_product_database_edit_ui
    from scripts.flows.O.O450_repricing_tracker_ui import render_repricing_tracker_ui
    from scripts.flows.O.O460_build_restock_session_view import build_restock_session_view
    from scripts.flows.O.O462_restock_session_draft_decisions import submit_restock_session_draft_decision
    from scripts.flows.O.O464_build_restock_supplier_batch_drafts import build_restock_supplier_batch_drafts
    from scripts.flows.O.O466_restock_supplier_proof_events import submit_restock_session_supplier_proof_event
    from scripts.flows.O.O468_restock_pack_moq_proof_events import submit_restock_session_pack_moq_proof_event
    from scripts.flows.O.O470_build_purchase_approval_preview import build_purchase_approval_preview
    from scripts.flows.O.O472_build_purchase_approval_guardrails import (
        build_purchase_approval_guardrails,
        submit_purchase_approval_decision_event,
    )
    from scripts.flows.O.O474_build_po_draft_readiness_preview import build_po_draft_readiness_preview
    from scripts.flows.O.O476_build_po_line_design_preview import build_po_line_design_preview
    from scripts.flows.O.O478_build_po_draft_packet_review import build_po_draft_packet_review
    from scripts.flows.O.O480_build_po_draft_hold_review import build_po_draft_hold_review
    from scripts.flows.O.O482_build_po_draft_file_shape_preview import build_po_draft_file_shape_preview
    from scripts.flows.O.O484_build_po_preview_construction_summary import build_po_preview_construction_summary
    from scripts.flows.O.O486_build_po_draft_review_controls import (
        build_po_draft_review_controls,
        submit_po_draft_review_control_event,
    )
    from scripts.flows.O.O488_build_po_draft_export_preview import build_po_draft_export_preview
    from scripts.flows.O.O490_build_po_draft_export_gate import (
        build_po_draft_export_gate,
        submit_po_draft_export_gate_event,
    )
    from scripts.flows.O.O492_build_supplier_file_presence_probe import build_supplier_file_presence_probe
    from scripts.flows.O._contract_io import (
        append_o_contract_row,
        empty_o_contract_df,
        o_contract_columns,
        read_o_contract_df,
        write_o_contract_df,
    )
    from scripts.flows.F._contract_io import (
        append_f_contract_row,
        f_contract_columns,
        read_f_contract_df,
        write_f_contract_df,
    )
    from scripts.flows.F.price_list_manager.FPM040_build_next_action import build_next_action
    from scripts.flows.F.price_list_manager.FPM050_build_next_action_report import build_next_action_report
    from scripts.flows.F.price_list_manager.FPM060_build_status_dashboard import build_status_dashboard
    from scripts.flows.F.price_list_manager.FPM070_stage_f061_handoff import stage_f061_handoff
    from scripts.flows.F.price_list_manager.FPM080_set_queue_control import set_queue_control
    from scripts.flows.F.price_list_manager.FPM090_set_f061_handoff_approval import set_f061_handoff_approval
    from scripts.flows.F.price_list_manager._schemas import F061_HANDOFF_PREVIEW_COLUMNS, LIVE_CYCLE_EVENT_COLUMNS
    from scripts.flows.F.F098_build_brand_approval_queue import record_brand_approval_decisions
    from scripts.flows.F.f_scanner_timeout_policy import (
        ALLOWED_TIMEOUT_MODES,
        policy_df_from_display,
        policy_display_df,
        read_timeout_policy_df,
        reset_timeout_policy_to_defaults,
        timeout_policy_path,
        write_timeout_policy_df,
    )
    from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
    from scripts.flows.O._schemas import get_o_output_contract
    from scripts.flows.F._schemas import get_f_output_contract
except ModuleNotFoundError:
    # Streamlit can resolve modules from scripts/ first on some launches.
    from flows.O.O410_product_database_ui import render_product_database_ui
    from flows.O.O420_product_database_edit_ui import render_product_database_edit_ui
    from flows.O.O450_repricing_tracker_ui import render_repricing_tracker_ui
    from flows.O.O460_build_restock_session_view import build_restock_session_view
    from flows.O.O462_restock_session_draft_decisions import submit_restock_session_draft_decision
    from flows.O.O464_build_restock_supplier_batch_drafts import build_restock_supplier_batch_drafts
    from flows.O.O466_restock_supplier_proof_events import submit_restock_session_supplier_proof_event
    from flows.O.O468_restock_pack_moq_proof_events import submit_restock_session_pack_moq_proof_event
    from flows.O.O470_build_purchase_approval_preview import build_purchase_approval_preview
    from flows.O.O472_build_purchase_approval_guardrails import (
        build_purchase_approval_guardrails,
        submit_purchase_approval_decision_event,
    )
    from flows.O.O474_build_po_draft_readiness_preview import build_po_draft_readiness_preview
    from flows.O.O476_build_po_line_design_preview import build_po_line_design_preview
    from flows.O.O478_build_po_draft_packet_review import build_po_draft_packet_review
    from flows.O.O480_build_po_draft_hold_review import build_po_draft_hold_review
    from flows.O.O482_build_po_draft_file_shape_preview import build_po_draft_file_shape_preview
    from flows.O.O484_build_po_preview_construction_summary import build_po_preview_construction_summary
    from flows.O.O486_build_po_draft_review_controls import (
        build_po_draft_review_controls,
        submit_po_draft_review_control_event,
    )
    from flows.O.O488_build_po_draft_export_preview import build_po_draft_export_preview
    from flows.O.O490_build_po_draft_export_gate import (
        build_po_draft_export_gate,
        submit_po_draft_export_gate_event,
    )
    from flows.O.O492_build_supplier_file_presence_probe import build_supplier_file_presence_probe
    from flows.O._contract_io import (
        append_o_contract_row,
        empty_o_contract_df,
        o_contract_columns,
        read_o_contract_df,
        write_o_contract_df,
    )
    from flows.F._contract_io import (
        append_f_contract_row,
        f_contract_columns,
        read_f_contract_df,
        write_f_contract_df,
    )
    from flows.F.price_list_manager.FPM040_build_next_action import build_next_action
    from flows.F.price_list_manager.FPM050_build_next_action_report import build_next_action_report
    from flows.F.price_list_manager.FPM060_build_status_dashboard import build_status_dashboard
    from flows.F.price_list_manager.FPM070_stage_f061_handoff import stage_f061_handoff
    from flows.F.price_list_manager.FPM080_set_queue_control import set_queue_control
    from flows.F.price_list_manager.FPM090_set_f061_handoff_approval import set_f061_handoff_approval
    from flows.F.price_list_manager._schemas import F061_HANDOFF_PREVIEW_COLUMNS, LIVE_CYCLE_EVENT_COLUMNS
    from flows.F.F098_build_brand_approval_queue import record_brand_approval_decisions
    from flows.F.f_scanner_timeout_policy import (
        ALLOWED_TIMEOUT_MODES,
        policy_df_from_display,
        policy_display_df,
        read_timeout_policy_df,
        reset_timeout_policy_to_defaults,
        timeout_policy_path,
        write_timeout_policy_df,
    )
    from flows.O._paths import ensure_o_directories, get_o_path_contract
    from flows.O._schemas import get_o_output_contract
    from flows.F._schemas import get_f_output_contract

try:
    from scripts.core.storage import (
        list_review_summary_snapshots,
        read_review_pack_dataframe,
        read_review_summary_dataframe,
    )
except ModuleNotFoundError:
    from core.storage import (
        list_review_summary_snapshots,
        read_review_pack_dataframe,
        read_review_summary_dataframe,
    )


DECISION_ACTIONS = (
    "approve_full_restock",
    "approve_test_restock",
    "wait",
    "snooze",
    "skip",
    "bulk_review",
)

HANDOFF_STATUSES = (
    "handoff_closed",
    "queued_for_shipment",
    "ready_for_shipment",
)

BACKTEST_SOURCE_COLUMNS = (
    "seller_sku",
    "backtest_policy_id",
    "backtest_history_confidence",
    "backtest_market_viability_score",
    "backtest_exit_risk_score",
    "backtest_estimated_total_profit_gbp",
    "backtest_estimated_monthly_profit_gbp",
    "backtest_capital_lockup_days",
    "backtest_sellable_ceiling_zone",
    "backtest_amazon_risk_level",
    "backtest_compression_risk_level",
    "backtest_recommendation",
    "backtest_manual_review_reason",
)

BACKTEST_POLICY_EDITABLE_COLUMNS = (
    "minimum_expected_profit_gbp",
    "entry_target_roi_pct",
    "working_floor_roi_pct",
    "exit_floor_roi_pct",
    "emergency_floor_roi_pct",
)

BACKTEST_CALIBRATION_VIEW_COLUMNS = (
    "seller_sku",
    "asin",
    "recommendation",
    "amazon_risk_level",
    "market_viability_score",
    "exit_risk_score",
    "calibration_review_flag",
    "calibration_review_reason",
)

REORDER_COLUMN_WIDTHS = [0.62, 1.9, 2.65, 0.9, 1.5, 0.74, 0.64, 0.64, 0.64, 0.64, 0.84, 0.64, 0.44, 0.44, 0.44, 0.78, 0.78, 0.55]
REORDER_HEADER_LABELS = [
    "",
    "SKU / ASIN",
    "Name",
    "Qtys",
    "Supply / Barcode",
    "CPU",
    "Stock",
    "ROI",
    "Vlcity",
    "Days",
    "Recommend",
    "Restk",
    "Disc",
    "Drop",
    "Snze",
    "Ordered",
    "Price",
    "Send",
]
TEST_ORDER_COLUMNS = [
    "event_utc",
    "supplier_name",
    "supplier_code",
    "seller_sku",
    "asin",
    "title",
    "supply_code",
    "barcode",
    "ordered_qty",
    "ordered_unit_cost_gbp",
    "line_value_gbp",
    "action",
]
REORDER_INPUT_COLUMNS = [
    "send",
    "seller_sku",
    "title",
    "main_image",
    "supplier_name",
    "suggested_action",
    "suggested_qty",
    "suggested_unit_cost_gbp",
    "suggested_market_price_gbp",
    "order_qty",
    "confirmed_price",
    "disc",
    "drop",
    "snze",
    "snooze_date",
    "row_status",
    "recommendation_reason",
    "expected_forward_roi_pct",
    "days_cover_available_only",
    "profit_verdict",
    "profit_proof_source",
    "profit_check_message",
    "current_sell_price_gbp",
    "sell_price_basis",
    "forward_profit_per_unit_gbp",
    "break_even_max_cost_gbp",
    "target_roi_max_cost_gbp",
    "profit_guardrail_flags",
    "price_list_unit_cost_gbp",
    "price_list_source_received_at_utc",
    "price_list_unit_code",
    "price_list_pack_size",
    "price_list_pack_cost_gbp",
    "price_list_moq",
    "cost_match_method",
    "cost_confidence",
    "supplier_cost_review_reason",
    "expected_cost_source",
    "actual_paid_unit_cost_gbp",
    "usual_paid_unit_cost_gbp",
    "usual_paid_cost_basis",
    "usual_paid_cost_confidence",
    "usual_paid_sample_count",
    "usual_paid_discount_vs_list_pct",
    "usual_paid_vs_list_delta_gbp",
    "price_list_change_status",
    "price_list_previous_unit_cost_gbp",
    "price_list_previous_pack_size",
    "price_list_previous_seen_at_utc",
    "price_list_change_delta_gbp",
    "price_list_change_pct",
    "max_safe_unit_cost_gbp",
    "price_status",
    "price_status_message",
    "recommended_snooze_until_utc",
    "confirmed_price_safety_status",
    "confirmed_vs_max_delta_gbp",
    "price_list_vs_actual_paid_delta_gbp",
    "price_list_vs_purchase_reference_delta_gbp",
    "price_proof_summary",
    "asin",
    "cost_mode",
    "recommendation_basis",
    "queue_status",
    "backtest_policy_id",
    "backtest_history_confidence",
    "backtest_market_viability_score",
    "backtest_exit_risk_score",
    "backtest_estimated_total_profit_gbp",
    "backtest_estimated_monthly_profit_gbp",
    "backtest_capital_lockup_days",
    "backtest_sellable_ceiling_zone",
    "backtest_amazon_risk_level",
    "backtest_compression_risk_level",
    "backtest_recommendation",
    "backtest_manual_review_reason",
    "decision_note",
    "barcode",
    "qtys",
    "supply_code",
    "cpu",
    "stock",
    "ordered_open",
    "vlcity",
    "days",
    "recommend",
    "restk",
    "resk_val",
    "supplier_sku",
    "supplier_pack_size",
    "order_qty_mode",
    "order_qty_unit_label",
    "sell_pack_qty",
    "supplier_case_qty",
    "supplier_case_multiple",
    "valid_order_step",
    "repack_required",
    "bundle_required",
    "display_qtys_label",
    "pack_conversion_note",
    "source_system",
    "source_reference",
    "sheet_recommend_label",
]
FEEDER_REVIEW_PAGE_SIZE = 10
FEEDER_REVIEW_PACK_PATHS = {
    "passes": "out/analysis_reports/f_live_price_file_pass_review_latest.csv",
    "near_misses": "out/analysis_reports/f_live_price_file_near_miss_review_latest.csv",
}
FEEDER_REVIEW_SUMMARY_PATH = "out/analysis_reports/f_live_price_file_review_summary_latest.csv"
FEEDER_REVIEW_PACK_FILE_STEMS = {
    "passes": "f_live_price_file_pass_review",
    "near_misses": "f_live_price_file_near_miss_review",
}
FEEDER_REVIEW_HANDOFF_ID_PREFIX = "handoff|"
AI_PRODUCT_CHECK_GATE_COLUMNS = [
    "handoff_id",
    "supplier_id",
    "supplier_name",
    "run_id",
    "source_review_pack_type",
    "queue_state",
    "ai_gate_status",
    "operator_ready_flag",
    "operator_visible_flag",
    "f032_decision_id",
    "supplier_sku",
    "asin",
    "supplier_title",
    "amazon_title",
    "amazon_description_snippet",
    "roi_pct",
    "f032_rule_action",
    "f032_rule_bucket",
    "f032_rule_reason",
    "codex_ai_action",
    "codex_ai_decision_bucket",
    "codex_ai_confidence",
    "codex_ai_needs_user_guidance",
    "codex_ai_rescan_needed",
    "codex_ai_reason",
    "codex_ai_evidence",
    "codex_ai_reviewed_utc",
    "codex_ai_reviewer",
    "queue_path",
    "decision_path",
    "manifest_path",
]
AI_PRODUCT_CHECK_GATE_STATUS_LABELS = {
    "legacy_needs_ai_gate": "Needs AI Gate",
    "legacy_manual_near_backlog": "Legacy Manual/Near Backlog",
    "pending_ai_check": "Pending AI Check",
    "ai_cleared": "AI Cleared",
    "needs_user_guidance": "Needs User Guidance",
    "rescan_needed": "Rescan Needed",
    "ai_rejected": "AI Rejected",
    "invalid_ai_decision": "Invalid AI Decision",
    "waiting_for_ai_queue": "Waiting For AI Queue",
}
AI_PRODUCT_CHECK_GATE_STATUS_ORDER = [
    "legacy_needs_ai_gate",
    "legacy_manual_near_backlog",
    "pending_ai_check",
    "needs_user_guidance",
    "rescan_needed",
    "ai_rejected",
    "invalid_ai_decision",
    "waiting_for_ai_queue",
    "ai_cleared",
]
OPERATOR_PAGE_OPTIONS = [
    ("Today", "today"),
    ("Restock Session", "restock_session"),
    ("Reorder Workbench", "reorder"),
    ("Products", "product_db"),
    ("New Product Review", "new_product_review"),
    ("Orders and P&L", "po_drafts"),
    ("Receiving", "receiving"),
    ("Send to Amazon", "send_to_amazon"),
    ("Product DB Edit", "product_db_edit"),
    ("Listing Profile Review", "product_listing_profile_review"),
    ("Brand Approval Queue", "brand_approval_queue"),
    ("Price List Queue", "price_list_queue"),
    ("Repricer Tracker", "repricer_tracker"),
    ("Decision Log", "decision_log"),
]
OPERATOR_NAV_LABELS = {
    "restock_session": "Restocking",
    "new_product_review": "Supplier Intake",
    "reorder": "Old Reorder Workbench",
}
OPERATOR_NAV_SECTIONS = [
    (
        "Business work",
        "Luke's normal working path.",
        (
            "today",
            "restock_session",
            "product_db",
            "new_product_review",
            "po_drafts",
            "receiving",
            "send_to_amazon",
        ),
    ),
    (
        "Proof / Admin",
        "Maintenance and proof views only.",
        (
            "product_db_edit",
            "product_listing_profile_review",
            "brand_approval_queue",
            "price_list_queue",
            "repricer_tracker",
            "decision_log",
            "reorder",
        ),
    ),
]
OPERATOR_PAGE_DESCRIPTIONS = {
    "today": "Read-only daily starting point.",
    "restock_session": "Manual restocking proof and blocker review.",
    "reorder": "Old dense supplier table. Use only when you need the legacy controls.",
    "product_db": "Product truth and freshness view.",
    "new_product_review": "Check scanner-found supplier products. No buying or listing happens here.",
    "po_drafts": "Local draft order review.",
    "receiving": "Record stock that has arrived.",
    "send_to_amazon": "Record stock ready for Amazon handoff.",
    "product_db_edit": "Manual Product DB edits.",
    "product_listing_profile_review": "Listing setup proof.",
    "brand_approval_queue": "Brand approval proof and decisions.",
    "price_list_queue": "Scanner queue and login/admin proof.",
    "repricer_tracker": "Repricing proof tracker.",
    "decision_log": "Raw local decision event log.",
}
OPERATOR_HIDDEN_PAGE_REDIRECTS = {
    "ai_product_check_gate": "new_product_review",
}
FEEDER_REVIEW_LANE_SPECS = {
    "Passes": {"lane_id": "passes", "pack_type": "passes", "lane_filter": "passes"},
    "Manual review": {"lane_id": "manual_review", "pack_type": "near_misses", "lane_filter": "manual_review"},
    "Near misses": {"lane_id": "near_misses", "pack_type": "near_misses", "lane_filter": "near_misses"},
}
FEEDER_REVIEW_LANE_DISPLAY = {
    "Passes": "Best finds",
    "Manual review": "Needs Luke's judgement",
    "Near misses": "Close calls",
}
FEEDER_REVIEW_MANUAL_ACTION_COLUMNS = (
    "identity_recommended_action",
    "profit_recommended_action",
    "demand_recommended_action",
    "history_recommended_action",
    "uk_review_recommended_action",
    "seller_history_recommended_action",
)
SUPPLIER_PROFILES_PATH = "out/systems/O/live/supplier_profiles.csv"
FEEDER_REVIEW_DECISIONS = ("pass", "fail", "rescan")
FEEDER_REVIEW_DECISION_DISPLAY = {
    "": "Choose",
    "pass": "Keep for listing check",
    "fail": "Reject",
    "rescan": "Needs re-scan",
}
FEEDER_REVIEW_DECISION_OPTIONS = list(FEEDER_REVIEW_DECISION_DISPLAY.values())
FEEDER_REVIEW_REASON_OPTIONS = (
    ("", "Select reason"),
    ("wrong_product", "Wrong product"),
    ("seller_controlled", "Seller controlled"),
    ("profit_too_weak", "Profit too weak"),
    ("demand_too_weak", "Demand too weak"),
    ("review_or_variant_risk", "Review or variant risk"),
    ("missing_evidence", "Missing evidence"),
    ("other", "Other"),
)
FEEDER_REVIEW_REASON_LABELS = {code: label for code, label in FEEDER_REVIEW_REASON_OPTIONS}
DEFAULT_FEEDER_REVIEW_PRODUCT_TAX_CODE = "A_GEN_STANDARD"
DEFAULT_FEEDER_REVIEW_CURRENCY_CODE = "GBP"
DEFAULT_FEEDER_REVIEW_PRICE_INCLUDES_TAX = "1"
FEEDER_REVIEW_COLUMN_WIDTHS = [1.15, 2.75, 0.78, 0.54, 0.95, 0.62, 0.5, 0.55, 0.68, 0.8, 1.1, 1.45, 0.38]
FEEDER_REVIEW_HEADER_LABELS = [
    "SKU / ASIN",
    "Product",
    "30d",
    "ROI",
    "Profit",
    "Score",
    "Start",
    "Rank",
    "Sig",
    "Decision",
    "Reason",
    "Note",
    "Done",
]
AMAZON_LISTING_DRAFT_DISPLAY_COLUMNS = [
    "supplier_name",
    "supplier_sku",
    "asin",
    "amazon_title",
    "expected_seller_sku",
    "supplier_cost_gbp",
    "starting_price_gbp",
    "country_of_origin",
    "product_tax_code",
    "currency_code",
    "price_includes_tax",
    "draft_status",
    "listing_approval_status",
    "amazon_preview_status",
    "amazon_preview_issue_count",
    "amazon_submission_status",
    "block_reason",
    "hold_reason",
]
PRICE_LIST_QUEUE_DASHBOARD_PATH = "out/systems/F/price_list_manager/test_mode/status_dashboard.csv"
PRICE_LIST_NEXT_ACTION_REPORT_PATH = "out/systems/F/price_list_manager/test_mode/next_action_report.md"
PRICE_LIST_HANDOFF_PREVIEW_PATH = "out/systems/F/price_list_manager/test_mode/f061_handoff_preview.csv"
PRICE_LIST_LIVE_STATUS_PATH = "out/systems/F/price_list_manager/live/live_cycle_status.csv"
PRICE_LIST_LIVE_EVENTS_PATH = "out/systems/F/price_list_manager/live/live_cycle_events.csv"
PRICE_LIST_ACTIVE_RUN_PATH = "out/systems/F/inbox/supplier_price_list_active_run.csv"
PRICE_LIST_RUN_STATE_PATH = "out/systems/F/inbox/supplier_price_list_run_state.csv"
PRICE_LIST_SCREENING_STATE_PATH = "out/systems/F/live/f_screening_row_state_live.csv"
PRICE_LIST_RECOVERY_PROGRESS_PATH = "out/systems/F/price_list_manager/test_mode/f061_recovery_progress.csv"
PRICE_LIST_CHILD_STATUS_PATH = "out/systems/F/price_list_manager/live/f061_child_status.txt"
PRICE_LIST_MANAGER_MODE_STATE_PATH = "out/systems/F/price_list_manager/live/f061_manager_mode_state.txt"
PRICE_LIST_SUPERVISOR_STATE_PATH = "out/systems/F/price_list_manager/live/fpm_live_supervisor_state.txt"
PRICE_LIST_CHILD_STDOUT_PATH = "out/systems/F/price_list_manager/live/f061_child_stdout.log"
PRICE_LIST_CHILD_STDERR_PATH = "out/systems/F/price_list_manager/live/f061_child_stderr.log"
PRICE_LIST_BROWSER_VISIBILITY_STATE_PATH = "out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt"
PRICE_LIST_LOGIN_MODE_REQUEST_PATH = "out/systems/F/price_list_manager/live/f061_login_mode.requested"
PRICE_LIST_LOGIN_MODE_INACTIVE_STATUSES = {"canceled", "cancelled", "completed", "consumed", "drained", "still_required"}
PRICE_LIST_QUEUE_COLUMNS = (
    "queue_position",
    "supplier_id",
    "supplier_name",
    "source_method",
    "source_location",
    "file_state",
    "queue_state",
    "operator_action",
    "control_state",
    "price_list_date",
    "bot_status",
    "web_unprocessed",
    "web_pass",
    "web_fail",
    "web_rescan",
    "second_unprocessed",
    "second_pass",
    "second_fail",
)
PRICE_LIST_QUEUE_COLUMN_WIDTHS = [0.45, 2.2, 1.25, 1.05, 1.05, 1.2, 0.85, 0.7, 0.7, 0.78, 0.78, 0.82, 0.95]
PRICE_LIST_QUEUE_HEADER_LABELS = [
    "#",
    "Supplier",
    "State",
    "Method",
    "File",
    "Control",
    "Scan",
    "PASS",
    "FAIL",
    "LOGIN",
    "Rescan",
    "Pause",
    "Priority",
]
RESTOCK_SESSION_DISPLAY_COLUMNS = [
    "seller_sku",
    "asin",
    "title",
    "source_class",
    "supplier_sku",
    "barcode",
    "old_suggested_qty",
    "current_supplier_cost_gbp",
    "current_amazon_price_gbp",
    "expected_profit_per_unit_gbp",
    "expected_roi_pct",
    "supplier_match_state",
    "supplier_stock_state",
    "supplier_cost_proof_state",
    "market_price_proof_state",
    "fee_proof_state",
    "refund_proof_state",
    "inbound_cost_proof_state",
    "pack_moq_proof_state",
    "supplier_order_viability_state",
    "operator_decision_state",
    "order_qty_draft",
    "latest_draft_decision_code",
    "latest_draft_note",
    "snooze_until_utc",
    "action_block_reason",
]
RESTOCK_WORKBENCH_COLUMNS = [
    "supplier_name",
    "seller_sku",
    "asin",
    "title",
    "available_now",
    "ordered_open",
    "velocity_30d",
    "old_suggested_qty",
    "order_qty_draft",
    "display_qtys_label",
    "current_supplier_cost_gbp",
    "current_amazon_price_gbp",
    "expected_profit_per_unit_gbp",
    "expected_roi_pct",
    "refund_sample_confidence",
    "fee_proof_state",
    "net_fee_model_status",
    "inbound_cost_proof_state",
    "supplier_match_state",
    "supplier_stock_state",
    "supplier_cost_proof_state",
    "pack_moq_proof_state",
    "supplier_order_viability_state",
    "row_status",
    "action_block_reason",
    "latest_draft_decision_code",
    "latest_draft_note",
]
RESTOCK_WORKBENCH_COLUMN_LABELS = {
    "supplier_name": "Supplier",
    "seller_sku": "SKU",
    "asin": "ASIN",
    "title": "Product",
    "available_now": "Stock",
    "ordered_open": "Already Ordered",
    "velocity_30d": "30d Velocity",
    "old_suggested_qty": "Suggested Qty",
    "order_qty_draft": "Luke Draft Qty",
    "display_qtys_label": "Pack/Case",
    "current_supplier_cost_gbp": "Buy Cost",
    "current_amazon_price_gbp": "Amazon Price",
    "expected_profit_per_unit_gbp": "Profit/Unit",
    "expected_roi_pct": "ROI",
    "refund_sample_confidence": "Refund Confidence",
    "fee_proof_state": "Fee Confidence",
    "net_fee_model_status": "Net Fee Model",
    "inbound_cost_proof_state": "Inbound/FBA Cost",
    "supplier_match_state": "Supplier Match",
    "supplier_stock_state": "Supplier Stock",
    "supplier_cost_proof_state": "Supplier Cost Proof",
    "pack_moq_proof_state": "Pack/MOQ Proof",
    "supplier_order_viability_state": "Order Viability",
    "row_status": "State",
    "action_block_reason": "Blocker",
    "latest_draft_decision_code": "Luke Decision",
    "latest_draft_note": "Decision Note",
}
FEEDER_REVIEW_IDENTITY_COLUMNS = (
    "active_supplier_id",
    "active_run_id",
    "review_pack_type",
    "candidate_id",
)
FEEDER_REVIEW_PRODUCT_IDENTITY_COLUMNS = (
    "active_supplier_id",
    "review_pack_type",
    "asin_padded",
)
FEEDER_REVIEW_HANDOFF_GROUP_ID_PREFIX = "handoff_group|"
REORDER_DRAFT_FIELDS = (
    "send",
    "snze",
    "disc",
    "drop",
    "order_qty",
    "confirmed_price",
    "snooze_date",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _feeder_review_lane_display_label(lane_label: object) -> str:
    clean = _normalize_text(lane_label)
    return FEEDER_REVIEW_LANE_DISPLAY.get(clean, clean or "Products to check")


def _normalize_feeder_review_decision(value: object) -> str:
    token = _normalize_text(value).lower().replace("_", " ").replace("-", " ")
    token = " ".join(token.split())
    if token in {"pass", "keep", "keep for listing check", "looks good", "approve", "yes"}:
        return "pass"
    if token in {"fail", "reject", "no", "drop", "do not use", "not suitable"}:
        return "fail"
    if token in {"rescan", "re scan", "needs re scan", "needs rescan", "retry", "scan again", "recheck", "re check"}:
        return "rescan"
    return ""


def _normalize_feeder_review_reason_code(value: object) -> str:
    raw = _normalize_text(value).lower().replace(" ", "_").replace("-", "_")
    label_to_code = {
        label.lower().replace(" ", "_").replace("-", "_"): code
        for code, label in FEEDER_REVIEW_REASON_OPTIONS
        if code
    }
    if raw in FEEDER_REVIEW_REASON_LABELS:
        return raw
    if raw in label_to_code:
        return label_to_code[raw]
    return ""


def _feeder_review_reason_label(reason_code: object) -> str:
    code = _normalize_feeder_review_reason_code(reason_code)
    return FEEDER_REVIEW_REASON_LABELS.get(code, "")


def _contract_columns(contract_name: str) -> list[str]:
    return o_contract_columns(contract_name)


def _empty_contract_df(contract_name: str) -> pd.DataFrame:
    return empty_o_contract_df(contract_name)


def _read_contract_df(root: Path, contract_name: str) -> pd.DataFrame:
    return read_o_contract_df(root, contract_name)


def _merge_backtest_columns(rec_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
    rec = rec_df.copy()
    backtest_cols = list(BACKTEST_SOURCE_COLUMNS[1:])
    for col in backtest_cols:
        if col not in rec.columns:
            rec[col] = ""
    if source_df.empty:
        return rec

    src = source_df.copy()
    for col in BACKTEST_SOURCE_COLUMNS:
        if col not in src.columns:
            src[col] = ""
    src = src[list(BACKTEST_SOURCE_COLUMNS)].drop_duplicates(subset=["seller_sku"], keep="first")

    rec = rec.drop(columns=backtest_cols, errors="ignore")
    rec = rec.merge(src, on="seller_sku", how="left")
    for col in backtest_cols:
        if col not in rec.columns:
            rec[col] = ""
        rec[col] = rec[col].map(_normalize_text)
    return rec


def _append_contract_row(root: Path, contract_name: str, row: Dict[str, str]) -> dict[str, str]:
    return append_o_contract_row(root, contract_name, row)


def _write_contract_rows(root: Path, contract_name: str, rows: list[Dict[str, str]]) -> list[dict[str, str]]:
    ordered_cols = _contract_columns(contract_name)
    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        normalized: dict[str, str] = {}
        for col in ordered_cols:
            normalized[col] = _normalize_text(row.get(col, ""))
        normalized_rows.append(normalized)
    out_df = pd.DataFrame(normalized_rows, columns=ordered_cols)
    write_o_contract_df(root, contract_name, out_df)
    return normalized_rows


def _f_contract_columns(contract_name: str) -> list[str]:
    return f_contract_columns(contract_name)


def _read_f_contract_df(root: Path, contract_name: str) -> pd.DataFrame:
    return read_f_contract_df(root, contract_name)


def _append_f_contract_row(root: Path, contract_name: str, row: Dict[str, str]) -> dict[str, str]:
    return append_f_contract_row(root, contract_name, row)


def _append_f_contract_rows(root: Path, contract_name: str, rows: list[Dict[str, str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    existing_df = _read_f_contract_df(root, contract_name)
    ordered_cols = _f_contract_columns(contract_name)
    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        normalized: dict[str, str] = {}
        for col in ordered_cols:
            normalized[col] = _normalize_text(row.get(col, ""))
        normalized_rows.append(normalized)
    out_df = pd.concat([existing_df, pd.DataFrame(normalized_rows)], ignore_index=True)
    out_df = out_df[ordered_cols + [c for c in out_df.columns if c not in ordered_cols]]
    write_f_contract_df(root, contract_name, out_df)
    return normalized_rows


def _number_text(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _to_float(value: object) -> float:
    text = _normalize_text(value)
    if text == "":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _build_ordered_open_lookup(df: pd.DataFrame) -> dict[str, str]:
    if df.empty or "seller_sku" not in df.columns:
        return {}
    work = df.copy()
    if "remaining_open_qty" not in work.columns:
        work["remaining_open_qty"] = work.get("ordered_qty", "")
    work["seller_sku"] = work["seller_sku"].map(lambda v: _normalize_text(v).upper())
    work = work[work["seller_sku"] != ""].copy()
    if work.empty:
        return {}
    work["_remaining_open_qty_num"] = work["remaining_open_qty"].map(_to_float)
    grouped = work.groupby("seller_sku", sort=False)["_remaining_open_qty_num"].sum()
    return {sku: (_num_text(value) if value > 0 else "0") for sku, value in grouped.items()}


def validate_backtest_policy_values(values: dict[str, object]) -> tuple[dict[str, str], list[str]]:
    parsed: dict[str, str] = {}
    errors: list[str] = []
    numeric_values: dict[str, float] = {}
    for field in BACKTEST_POLICY_EDITABLE_COLUMNS:
        raw = _normalize_text(values.get(field, ""))
        if raw == "":
            errors.append(f"{field} is required")
            continue
        try:
            number = float(raw)
        except ValueError:
            errors.append(f"{field} must be numeric")
            continue
        numeric_values[field] = number
        parsed[field] = _number_text(number)
    if errors:
        return {}, errors
    entry = numeric_values["entry_target_roi_pct"]
    working = numeric_values["working_floor_roi_pct"]
    exit_floor = numeric_values["exit_floor_roi_pct"]
    emergency = numeric_values["emergency_floor_roi_pct"]
    if not (entry >= working >= exit_floor >= emergency):
        errors.append(
            "ROI ordering must be entry_target_roi_pct >= working_floor_roi_pct >= "
            "exit_floor_roi_pct >= emergency_floor_roi_pct"
        )
        return {}, errors
    return parsed, []


def load_backtest_policy_live_row(root: Path | None = None) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    policy_df = _read_f_contract_df(root_path, "feeder_backtest_policy_live")
    if policy_df.empty:
        empty_row: dict[str, str] = {"observed_utc": "", "policy_id": "", "policy_status": ""}
        for col in BACKTEST_POLICY_EDITABLE_COLUMNS:
            empty_row[col] = ""
        return empty_row
    active_df = policy_df[
        policy_df.get("policy_status", "").map(lambda v: _normalize_text(v).lower() == "active")
    ]
    row = active_df.iloc[-1] if not active_df.empty else policy_df.iloc[-1]
    out: dict[str, str] = {
        "observed_utc": _normalize_text(row.get("observed_utc", "")),
        "policy_id": _normalize_text(row.get("policy_id", "")),
        "policy_status": _normalize_text(row.get("policy_status", "")),
    }
    for col in BACKTEST_POLICY_EDITABLE_COLUMNS:
        out[col] = _normalize_text(row.get(col, ""))
    return out


def submit_backtest_policy_update_event(
    *,
    root: Path | None = None,
    policy_values: dict[str, object],
    actor: str = "operator_ui",
    source_reference: str = "o_ui_backtest_policy",
    decision_note: str = "",
    action: str = "apply",
    policy_id: str = "",
) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    normalized_values, errors = validate_backtest_policy_values(policy_values)
    if errors:
        raise ValueError(" ; ".join(errors))
    event_id = f"o-ui-f-policy-{uuid.uuid4().hex[:12]}"
    effective_policy_id = _normalize_text(policy_id)
    if effective_policy_id == "":
        effective_policy_id = _normalize_text(load_backtest_policy_live_row(root=root_path).get("policy_id", ""))
    if effective_policy_id == "":
        raise ValueError("policy_id is required and no active live backtest policy was found")
    row = {
        "event_utc": _utc_now_iso(),
        "event_id": event_id,
        "policy_id": effective_policy_id,
        "action": _normalize_text(action) or "apply",
        "minimum_expected_profit_gbp": normalized_values["minimum_expected_profit_gbp"],
        "entry_target_roi_pct": normalized_values["entry_target_roi_pct"],
        "working_floor_roi_pct": normalized_values["working_floor_roi_pct"],
        "exit_floor_roi_pct": normalized_values["exit_floor_roi_pct"],
        "emergency_floor_roi_pct": normalized_values["emergency_floor_roi_pct"],
        "actor": _normalize_text(actor),
        "source_reference": _normalize_text(source_reference) or "o_ui_backtest_policy",
        "decision_note": _normalize_text(decision_note),
    }
    return _append_f_contract_row(root_path, "feeder_backtest_policy_update_events", row)


def load_backtest_calibration_df(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    in_path = root_path / "out" / "analysis_reports" / "f_backtest_calibration_set_latest.csv"
    if not in_path.exists():
        return pd.DataFrame(columns=list(BACKTEST_CALIBRATION_VIEW_COLUMNS))
    df = pd.read_csv(in_path, dtype=str).fillna("")
    for col in BACKTEST_CALIBRATION_VIEW_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


def select_flagged_backtest_calibration_rows(calibration_df: pd.DataFrame) -> pd.DataFrame:
    if calibration_df.empty:
        return pd.DataFrame(columns=list(BACKTEST_CALIBRATION_VIEW_COLUMNS))
    work = calibration_df.copy()
    for col in BACKTEST_CALIBRATION_VIEW_COLUMNS:
        if col not in work.columns:
            work[col] = ""
    flagged = work[
        work.get("calibration_review_flag", "").map(lambda v: _normalize_text(v).lower() in {"1", "true", "yes"})
        | work.get("calibration_review_reason", "").map(lambda v: _normalize_text(v) != "")
    ].copy()
    return flagged[list(BACKTEST_CALIBRATION_VIEW_COLUMNS)]


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def _pad_asin_to_10(asin: object) -> str:
    value = _normalize_text(asin).upper()
    if value == "":
        return ""
    return value.rjust(10, "0")


def _amazon_dp_url(asin: object) -> str:
    padded = _pad_asin_to_10(asin)
    if padded == "":
        return ""
    return f"https://www.amazon.co.uk/dp/{quote(padded)}"


def _normalize_country_of_origin(value: object) -> str:
    text = _normalize_text(value).upper()
    if len(text) == 2 and text.isalpha():
        return text
    return ""


def _normalize_currency_code(value: object) -> str:
    text = _normalize_text(value).upper()
    if len(text) == 3 and text.isalpha():
        return text
    return ""


def _normalize_positive_money(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed <= 0:
        return ""
    return f"{parsed:.2f}"


def _normalize_positive_int_text(value: object) -> str:
    text = _normalize_text(value).replace(",", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed <= 0 or parsed != int(parsed):
        return ""
    return str(int(parsed))


def _normalize_non_negative_money(value: object) -> str:
    text = _normalize_text(value).replace(",", "").replace("%", "")
    if text == "":
        return ""
    try:
        parsed = float(text)
    except Exception:
        return ""
    if parsed < 0:
        return ""
    return f"{parsed:.2f}".rstrip("0").rstrip(".")


def _normalize_truthy_flag(value: object) -> str:
    text = _normalize_text(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return "1"
    if text in {"0", "false", "no", "n", "off"}:
        return "0"
    return ""


def _normalize_price_includes_tax(value: object, *, default: str = DEFAULT_FEEDER_REVIEW_PRICE_INCLUDES_TAX) -> str:
    text = _normalize_text(value).lower()
    if text == "":
        return default
    if text in {"0", "false", "no", "n", "off"}:
        return "0"
    if text in {"1", "true", "yes", "y", "on"}:
        return "1"
    return default


_PASS_REASON_LABELS = {
    "screening_pass": "Passed the initial screen.",
    "backtest_pass": "Past backtest checks also support it.",
    "profit_floor_met": "Profit clears the minimum floor.",
    "demand_evidence_present": "There is usable demand evidence behind the estimate.",
}

_FAIL_REASON_LABELS = {
    "roifail": "Margin looks too weak at the current buy price.",
    "over50k": "Sales rank is weaker than the normal pass line.",
    "noasin": "No reliable Amazon match was found.",
    "fail": "It failed a core commercial screen.",
    "nodate": "Sales history is incomplete, so the estimate is not safe yet.",
    "hazmatfail": "Hazmat restrictions make this unsuitable.",
    "scrapefail": "The scrape evidence is incomplete or unreliable.",
}

_RECOVERY_HINT_LABELS = {
    "economics_below_pass_floor_but_close_enough_for_manual_review": "Close enough on economics to justify a manual check.",
}

_COMMERCIAL_TOKEN_LABELS = {
    "qualification_factor_reduced": "Forecast has already been trimmed back for safety.",
    "seasonality_state_seasonal_confirmed": "Seasonal pattern looks confirmed.",
    "seasonality_state_possible_seasonal": "This may be seasonal.",
    "seasonality_state_insufficient_history": "History is still too thin to judge seasonality well.",
    "seasonality_state_spiky_not_proven_seasonal": "Recent spikes are not yet proven as true seasonality.",
    "stability_state_drifting_up": "Trend is improving.",
    "stability_state_spiky": "Demand looks spiky rather than steady.",
    "stability_state_too_new": "Listing still looks too new.",
    "recent_vs_baseline_state_overperforming": "Recent demand is running ahead of baseline.",
    "recent_vs_baseline_state_underperforming": "Recent demand is below baseline.",
    "recent_vs_baseline_state_insufficient_history": "There is not enough history to compare against baseline.",
    "decision_confidence_high": "Confidence is high.",
    "decision_confidence_medium": "Confidence is medium.",
    "decision_confidence_low": "Confidence is low.",
    "confidence_maturity_full_year": "There is roughly a full year of history behind this read.",
    "confidence_maturity_partial": "Only partial history is available.",
    "summary_not_ready": "The model still wants a manual check before calling this clean.",
    "confidence_summary_not_ready": "Confidence is not strong enough for a fully automatic call.",
    "confidence_stability_spiky": "Stability confidence is weak because demand is spiky.",
    "confidence_seasonality_unproven_spike": "Seasonal spike evidence is not proven yet.",
}


def _split_review_tokens(raw_text: object) -> list[str]:
    text = _normalize_text(raw_text)
    if text == "":
        return []
    return [token.strip() for token in text.split("|") if token.strip()]


def _format_review_number(value: object, *, decimals_when_needed: int = 1) -> str:
    text = _normalize_text(value)
    if text == "":
        return "-"
    num = _to_float(text)
    if abs(num - round(num)) < 0.05:
        return f"{int(round(num)):,}"
    return f"{num:,.{decimals_when_needed}f}".rstrip("0").rstrip(".")


def _format_review_currency_gbp(value: object) -> str:
    text = _normalize_text(value)
    if text == "":
        return "-"
    num = _to_float(text)
    if abs(num) >= 1000:
        body = f"{num:,.0f}"
    elif abs(num) >= 100:
        body = f"{num:,.1f}".rstrip("0").rstrip(".")
    else:
        body = f"{num:,.2f}".rstrip("0").rstrip(".")
    return f"GBP {body}"


def _format_review_percent(value: object) -> str:
    text = _normalize_text(value).replace("%", "").replace(",", "")
    if text == "":
        return "-"
    num = _to_float(text)
    return f"{num:,.0f}%"


def _first_review_value(row: pd.Series | dict[str, object], fields: list[str]) -> str:
    for field in fields:
        value = _normalize_text(row.get(field, ""))
        if value:
            return value
    return ""


def _feeder_review_roi_pct(row: pd.Series | dict[str, object]) -> str:
    return _first_review_value(
        row,
        [
            "review_roi_pct",
            "profit_on_cost_pct",
            "title_match_profit_on_cost_pct",
            "roi_pct",
            "expected_forward_roi_pct",
            "forward_roi_pct",
            "roi",
        ],
    ).replace("%", "").strip()


def _feeder_review_profit_signal_text(row: pd.Series | dict[str, object]) -> str:
    per_unit = _first_review_value(
        row,
        ["profit_per_unit_30d_gbp", "profit_per_unit_gbp", "corrected_profit_per_unit_gbp"],
    )
    expected = _first_review_value(
        row,
        [
            "expected_profit_next_30d_gbp",
            "estimated_monthly_profit_gbp",
            "expected_profit_gbp",
            "corrected_expected_profit_next_30d_gbp",
        ],
    )
    parts: list[str] = []
    if per_unit:
        parts.append(f"unit_profit={_format_review_currency_gbp(per_unit)}")
    if expected:
        parts.append(f"30d_profit={_format_review_currency_gbp(expected)}")
    return " | ".join(parts)


def _sentence_case(text: str) -> str:
    clean = " ".join(_normalize_text(text).replace("_", " ").split())
    if clean == "":
        return ""
    return clean[0].upper() + clean[1:]


def _humanize_pass_reason_summary(raw_text: object) -> str:
    messages: list[str] = []
    for token in _split_review_tokens(raw_text):
        label = _PASS_REASON_LABELS.get(token.lower())
        if label and label not in messages:
            messages.append(label)
    if not messages:
        return "Passed the main screening checks."
    return " ".join(messages[:3])


def _humanize_fail_reason(raw_text: object) -> str:
    token = _normalize_text(raw_text).lower()
    if token == "":
        return "It fell short of the normal pass line."
    if token in _FAIL_REASON_LABELS:
        return _FAIL_REASON_LABELS[token]
    return _sentence_case(token) + "."


def _humanize_recovery_hint(raw_text: object) -> str:
    token = _normalize_text(raw_text).lower()
    if token == "":
        return ""
    if token in _RECOVERY_HINT_LABELS:
        return _RECOVERY_HINT_LABELS[token]
    return _sentence_case(token) + "."


def _humanize_commercial_note(raw_text: object) -> str:
    original_text = _normalize_text(raw_text)
    tokens = _split_review_tokens(raw_text)
    if not tokens:
        return original_text

    lead = ""
    notes: list[str] = []
    for token in tokens:
        normalized = token.lower()
        if normalized in {"pass", "fail"}:
            continue
        if normalized in {"avoid", "manual review", "exit-only"}:
            lead_map = {
                "avoid": "Use caution on this one.",
                "manual review": "Worth a manual look before buying.",
                "exit-only": "Looks safer as a cautious or short-term test.",
            }
            lead = lead_map.get(normalized, "")
            continue
        label = _COMMERCIAL_TOKEN_LABELS.get(normalized)
        if label and label not in notes:
            notes.append(label)

    sentences: list[str] = []
    if lead:
        sentences.append(lead)
    sentences.extend(notes[:3])
    if sentences:
        return " ".join(sentences)
    return original_text


def _humanize_intake_evidence_summary(raw_text: object, *, fallback: str = "") -> str:
    original_text = _normalize_text(raw_text)
    tokens = _split_review_tokens(raw_text)
    if not tokens:
        return fallback or original_text

    values: dict[str, str] = {}
    plain_tokens: list[str] = []
    for token in tokens:
        if "=" not in token:
            plain_tokens.append(token)
            continue
        key, value = token.split("=", 1)
        normalized_key = _normalize_text(key).lower()
        normalized_value = _normalize_text(value)
        if normalized_value.lower() in {"", "blank", "none", "n/a", "na", "null", "unknown"}:
            continue
        values[normalized_key] = normalized_value

    sentences: list[str] = []
    status = _normalize_text(values.get("screen_status") or values.get("original_result") or values.get("original_test_result"))
    if status.lower() == "pass":
        sentences.append("Passed the scanner checks.")
    elif status:
        sentences.append(f"Scanner result: {status}.")

    score = values.get("original_score") or values.get("score")
    if score:
        sentences.append(f"Scanner score: {_format_review_number(score)}.")

    rank = values.get("rank") or values.get("main_rank")
    if rank:
        sentences.append(f"Amazon rank: #{_format_review_number(rank, decimals_when_needed=0)}.")

    units_likely = values.get("units_likely_30d") or values.get("expected_units_next_30d")
    if units_likely:
        sentences.append(f"Likely 30 day sales: {_format_review_number(units_likely)}.")

    units_band = values.get("units_band_30d")
    if units_band and ".." in units_band:
        low, high = units_band.split("..", 1)
        sentences.append(
            f"Sales range: {_format_review_number(low)} to {_format_review_number(high)} units."
        )

    profit_likely = values.get("profit_likely_gbp") or values.get("expected_profit_next_30d_gbp")
    if profit_likely:
        sentences.append(f"Likely 30 day profit: {_format_review_currency_gbp(profit_likely)}.")

    unit_profit = values.get("unit_profit") or values.get("profit_per_unit_30d_gbp")
    if unit_profit:
        unit_profit = unit_profit.replace("GBP", "").strip()
        sentences.append(f"Profit per unit: {_format_review_currency_gbp(unit_profit)}.")

    confidence = values.get("decision_confidence") or values.get("ai_match_confidence")
    if confidence:
        sentences.append(f"Confidence: {confidence.replace('_', ' ')}.")

    stability = values.get("stability_state")
    if stability:
        sentences.append(f"Demand stability: {stability.replace('_', ' ')}.")

    if sentences:
        return " ".join(sentences[:5])
    if plain_tokens:
        return _humanize_commercial_note("|".join(plain_tokens)) or " ".join(plain_tokens)
    return fallback or original_text


def _evidence_value(raw_text: object, key: str) -> str:
    text = _normalize_text(raw_text)
    if text == "":
        return ""
    match = re.search(rf"(?:^|\|)\s*{re.escape(key)}=([^|]*)", text)
    value = _normalize_text(match.group(1)) if match else ""
    return "" if value.lower() in {"blank", "none", "n/a", "na", "null"} else value


def _f032_operator_check_note(row: pd.Series | dict[str, object]) -> str:
    action = _normalize_text(row.get("codex_ai_action", "")) or _normalize_text(row.get("f032_action", ""))
    if action not in {"manual_review", "rescan_needed", "remove_from_clean_pass"}:
        return ""

    bucket_text = " ".join(
        [
            _normalize_text(row.get("codex_ai_decision_bucket", "")),
            _normalize_text(row.get("codex_ai_fail_category", "")),
            _normalize_text(row.get("f032_decision_bucket", "")),
            _normalize_text(row.get("f032_fail_category", "")),
        ]
    ).lower()
    evidence = _normalize_text(row.get("codex_ai_evidence", "")) or _normalize_text(row.get("f032_evidence", ""))
    reason = _normalize_text(row.get("codex_ai_reason", "")) or _normalize_text(row.get("f032_reason", ""))

    supplier_qty = _evidence_value(evidence, "supplier_quantities")
    amazon_qty = _evidence_value(evidence, "amazon_quantities")
    if "pack" in bucket_text or "quantity" in bucket_text or supplier_qty or amazon_qty:
        if supplier_qty and amazon_qty and supplier_qty != amazon_qty:
            return f"AI check: confirm pack size. Supplier says {supplier_qty}; Amazon says {amazon_qty}."
        if supplier_qty and not amazon_qty:
            return f"AI check: confirm the Amazon listing is for {supplier_qty} units per pack."
        if amazon_qty and not supplier_qty:
            return f"AI check: supplier pack count is missing; Amazon mentions {amazon_qty} units."
        if reason:
            return f"AI check: {reason}"

    if reason:
        return f"AI check: {reason}"
    return ""


def _strip_ai_note_prefix(text: object) -> str:
    note = _normalize_text(text)
    if note.lower().startswith("ai check:"):
        return note.split(":", 1)[1].strip()
    return note


def _ai_compare_watch_note(row: pd.Series | dict[str, object]) -> str:
    action = _normalize_text(row.get("codex_ai_action", "")) or _normalize_text(row.get("f032_action", ""))
    if action == "":
        return ""
    confidence = _normalize_text(row.get("codex_ai_confidence", "")) or _normalize_text(row.get("f032_confidence", ""))
    reason = _strip_ai_note_prefix(_f032_operator_check_note(row)) or _normalize_text(
        row.get("codex_ai_reason", "")
    ) or _normalize_text(row.get("f032_reason", ""))
    parts: list[str] = []
    if confidence:
        parts.append(f"ai_match_confidence={confidence}")
    if reason:
        parts.append(f"ai_compare={reason}")
    return " | ".join(parts)


def _append_summary_note(existing: object, note: object) -> str:
    base = _normalize_text(existing)
    addition = _normalize_text(note)
    if addition == "":
        return base
    if base == "":
        return addition
    existing_parts = {_normalize_text(part).lower() for part in _summary_parts(base)}
    new_parts = [part for part in _summary_parts(addition) if _normalize_text(part).lower() not in existing_parts]
    if not new_parts:
        return base
    return f"{base} | {' | '.join(new_parts)}"


def _format_data_summary_tooltip(label: str, raw_text: object) -> str:
    text = _normalize_text(raw_text)
    if text == "":
        return f"{label}: -"
    parts = [part.strip() for part in text.split("|") if part.strip()]
    if not parts:
        return f"{label}: {text}"
    return f"{label}:\n- " + "\n- ".join(parts)


def _summary_parts(raw_text: object) -> list[str]:
    text = _normalize_text(raw_text)
    if text == "":
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


_SUMMARY_KEY_LABELS = {
    "screen_status": "Screen status",
    "original_score": "Original score",
    "original_result": "Original result",
    "rank": "Rank",
    "units_likely_30d": "Units likely (30d)",
    "units_band_30d": "Units band (30d)",
    "profit_likely_gbp": "Profit likely (GBP)",
    "starter_qty": "Starter qty",
    "backtest_state": "Backtest state",
    "decision_confidence": "Decision confidence",
    "ai_match_confidence": "AI match confidence",
    "ai_compare": "AI compare",
    "stability_state": "Stability",
    "seasonality_state": "Seasonality",
    "recent_vs_baseline_state": "Recent vs baseline",
    "opportunity_recommendation": "Opportunity recommendation",
    "history_recommendation": "History recommendation",
    "demand_confidence_note": "Demand note",
    "fail_code": "Fail code",
    "last_stage": "Last stage",
    "recovery_hint": "Recovery hint",
}


def _humanize_summary_value(value: str) -> str:
    token = _normalize_text(value)
    if token == "":
        return "-"
    token = token.replace("..", " to ")
    if "_" in token:
        token = token.replace("_", " ")
    return token


def _humanize_summary_item(item: str) -> str:
    token = _normalize_text(item)
    if token == "":
        return "-"
    if "=" not in token:
        return _humanize_summary_value(token)
    key, value = token.split("=", 1)
    key_norm = _normalize_text(key).lower()
    label = _SUMMARY_KEY_LABELS.get(key_norm, _humanize_summary_value(key_norm).title())
    pretty_value = _humanize_summary_value(value)
    return f"{label}: {pretty_value}"


def _hover_badge_html(
    *,
    symbol: str,
    border_color: str,
    text_color: str,
    heading: str,
    details_text: object,
) -> str:
    parts = _summary_parts(details_text)
    if not parts:
        parts = ["-"]
    list_html = "".join(f"<li>{html.escape(_humanize_summary_item(part))}</li>" for part in parts)
    return (
        "<span class='o-hover-wrap' tabindex='0'>"
        f"<span style='display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;"
        f"border:1px solid {border_color};border-radius:999px;color:{text_color};"
        "font-size:12px;font-weight:700;cursor:help;'>"
        f"{html.escape(symbol)}</span>"
        "<span class='o-hover-panel'>"
        f"<div class='o-hover-title'>{html.escape(heading)}</div>"
        f"<ul class='o-hover-list'>{list_html}</ul>"
        "</span>"
        "</span>"
    )


def _feeder_review_pack_path(root_path: Path, pack_type: str, review_pack_snapshot: str = "latest") -> Path:
    snapshot = _normalize_text(review_pack_snapshot) or "latest"
    if _is_feeder_review_handoff_snapshot(snapshot):
        manifest = _read_feeder_review_handoff_manifest(root_path, snapshot)
        if manifest and not _feeder_review_handoff_ready_for_operator(manifest):
            return root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_review_gate_not_ready.csv"
        field = "pass_review_path" if pack_type == "passes" else "near_miss_review_path"
        path_text = _normalize_text(manifest.get(field, ""))
        if path_text:
            return Path(path_text)
    if snapshot == "latest":
        manifest = _read_feeder_review_live_manifest(root_path)
        if _feeder_review_handoff_ready_for_operator(manifest):
            field = "pass_review_path" if pack_type == "passes" else "near_miss_review_path"
            path_text = _normalize_text(manifest.get(field, ""))
            if path_text:
                return Path(path_text)
        if _has_pending_feeder_review_ai_gate(root_path) or _raw_latest_review_pack_requires_ai_gate(root_path):
            return root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_review_gate_pending.csv"
        rel_path = FEEDER_REVIEW_PACK_PATHS.get(pack_type)
        if not rel_path:
            raise ValueError(f"unsupported feeder review pack_type: {pack_type}")
        return root_path / rel_path
    stem = FEEDER_REVIEW_PACK_FILE_STEMS.get(pack_type)
    if not stem:
        raise ValueError(f"unsupported feeder review pack_type: {pack_type}")
    path = root_path / "out" / "analysis_reports" / f"{stem}_{snapshot}.csv"
    if _review_pack_file_requires_ai_gate(root_path, path, pack_type=pack_type, snapshot_id=snapshot):
        return root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_review_gate_not_ready.csv"
    return path


def _feeder_review_summary_path(root_path: Path, review_pack_snapshot: str = "latest") -> Path:
    snapshot = _normalize_text(review_pack_snapshot) or "latest"
    if _is_feeder_review_handoff_snapshot(snapshot):
        manifest = _read_feeder_review_handoff_manifest(root_path, snapshot)
        if manifest and not _feeder_review_handoff_ready_for_operator(manifest):
            return root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_review_gate_not_ready_summary.csv"
        path_text = _normalize_text(manifest.get("summary_path", ""))
        if path_text:
            return Path(path_text)
    if snapshot == "latest":
        manifest = _read_feeder_review_live_manifest(root_path)
        if _feeder_review_handoff_ready_for_operator(manifest):
            path_text = _normalize_text(manifest.get("summary_path", ""))
            if path_text:
                return Path(path_text)
        if _has_pending_feeder_review_ai_gate(root_path) or _raw_latest_review_pack_requires_ai_gate(root_path):
            return root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_review_gate_pending_summary.csv"
        return root_path / FEEDER_REVIEW_SUMMARY_PATH
    if _review_snapshot_requires_ai_gate(root_path, snapshot):
        return root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_review_gate_not_ready_summary.csv"
    return root_path / "out" / "analysis_reports" / f"f_live_price_file_review_summary_{snapshot}.csv"


def _feeder_review_reader_snapshot_id(root_path: Path, review_pack_snapshot: str = "latest") -> str:
    snapshot = _normalize_text(review_pack_snapshot) or "latest"
    if _is_feeder_review_handoff_snapshot(snapshot):
        return snapshot
    if snapshot != "latest":
        return snapshot
    manifest = _read_feeder_review_live_manifest(root_path)
    if not _feeder_review_handoff_ready_for_operator(manifest):
        return snapshot
    supplier_id = _normalize_text(manifest.get("supplier_id", ""))
    run_id = _normalize_text(manifest.get("run_id", ""))
    if supplier_id and run_id:
        return _feeder_review_handoff_snapshot_id(supplier_id, run_id)
    return "latest_ai_gated_manifest"


def _feeder_review_handoff_snapshot_id(supplier_id: object, run_id: object) -> str:
    supplier = _normalize_text(supplier_id)
    run = _normalize_text(run_id)
    return f"{FEEDER_REVIEW_HANDOFF_ID_PREFIX}{supplier}|{run}"


def _is_feeder_review_handoff_snapshot(snapshot: object) -> bool:
    return _normalize_text(snapshot).startswith(FEEDER_REVIEW_HANDOFF_ID_PREFIX)


def _feeder_review_handoff_group_snapshot_id(supplier_id: object) -> str:
    supplier = _normalize_text(supplier_id)
    return f"{FEEDER_REVIEW_HANDOFF_GROUP_ID_PREFIX}{supplier}"


def _is_feeder_review_handoff_group_snapshot(snapshot: object) -> bool:
    return _normalize_text(snapshot).startswith(FEEDER_REVIEW_HANDOFF_GROUP_ID_PREFIX)


def _parse_feeder_review_handoff_group_snapshot(snapshot: object) -> str:
    raw = _normalize_text(snapshot)
    if not raw.startswith(FEEDER_REVIEW_HANDOFF_GROUP_ID_PREFIX):
        return ""
    return raw[len(FEEDER_REVIEW_HANDOFF_GROUP_ID_PREFIX) :].strip()


def _parse_feeder_review_handoff_snapshot(snapshot: object) -> tuple[str, str]:
    raw = _normalize_text(snapshot)
    if not raw.startswith(FEEDER_REVIEW_HANDOFF_ID_PREFIX):
        return "", ""
    parts = raw.split("|", 2)
    if len(parts) < 3:
        return "", ""
    return parts[1], parts[2]


def _read_feeder_review_handoff_manifest(root_path: Path, snapshot: object) -> dict[str, str]:
    supplier_id, run_id = _parse_feeder_review_handoff_snapshot(snapshot)
    if not supplier_id or not run_id:
        return {}
    manifest_path = (
        root_path
        / "out"
        / "systems"
        / "F"
        / "price_list_manager"
        / "review_handoffs"
        / supplier_id
        / run_id
        / "manifest.csv"
    )
    if not manifest_path.exists():
        return {}
    try:
        df = pd.read_csv(manifest_path, dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return {}
    if df.empty:
        return {}
    return {column: _normalize_text(value) for column, value in df.iloc[0].to_dict().items()}


def _read_feeder_review_live_manifest(root_path: Path) -> dict[str, str]:
    manifest_path = root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_manifest.csv"
    if not manifest_path.exists():
        return {}
    try:
        df = pd.read_csv(manifest_path, dtype=str).fillna("")
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return {}
    if df.empty:
        return {}
    return {column: _normalize_text(value) for column, value in df.iloc[0].to_dict().items()}


def _feeder_review_handoff_ready_for_operator(manifest: dict[str, str]) -> bool:
    return (
        _normalize_text(manifest.get("ai_gate_status", "")).lower() == "passed"
        and _normalize_text(manifest.get("operator_ready_flag", "")) == "1"
        and _normalize_text(manifest.get("pass_review_path", "")) != ""
    )


def _feeder_review_ai_gate_is_active(root_path: Path) -> bool:
    handoff_root = root_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"
    live_manifest_path = root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "review_handoff_manifest.csv"
    return handoff_root.exists() or live_manifest_path.exists()


def _review_pack_df_requires_ai_gate(source_df: pd.DataFrame) -> bool:
    if source_df.empty:
        return False
    required_columns = ("f032_decision_id", "f032_action", "codex_ai_action")
    missing_required_columns = [column for column in required_columns if column not in source_df.columns]
    if missing_required_columns:
        return True
    for column in required_columns:
        if source_df[column].map(_normalize_text).eq("").any():
            return True
    return False


def _review_pack_file_requires_ai_gate(
    root_path: Path,
    path: Path,
    *,
    pack_type: str,
    snapshot_id: str,
) -> bool:
    if not _feeder_review_ai_gate_is_active(root_path):
        return False
    source_df = read_review_pack_dataframe(
        path,
        pack_type=pack_type,
        snapshot_id=snapshot_id,
        dtype=str,
    )
    return _review_pack_df_requires_ai_gate(source_df)


def _review_snapshot_requires_ai_gate(root_path: Path, snapshot: str) -> bool:
    if _is_feeder_review_handoff_snapshot(snapshot):
        return False
    clean_snapshot = _normalize_text(snapshot) or "latest"
    for pack_type, stem in FEEDER_REVIEW_PACK_FILE_STEMS.items():
        file_name = f"{stem}_{clean_snapshot}.csv" if clean_snapshot != "latest" else f"{stem}_latest.csv"
        path = root_path / "out" / "analysis_reports" / file_name
        if _review_pack_file_requires_ai_gate(root_path, path, pack_type=pack_type, snapshot_id=clean_snapshot):
            return True
    return False


def _raw_latest_review_pack_requires_ai_gate(root_path: Path) -> bool:
    return _review_snapshot_requires_ai_gate(root_path, "latest")


def _has_pending_feeder_review_ai_gate(root_path: Path) -> bool:
    handoff_root = root_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"
    if not handoff_root.exists():
        return False
    for candidate_manifest_path in handoff_root.glob("*/*/candidate_manifest.csv"):
        manifest_path = candidate_manifest_path.with_name("manifest.csv")
        if not manifest_path.exists():
            return True
        try:
            df = pd.read_csv(manifest_path, dtype=str).fillna("")
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return True
        if df.empty:
            return True
        manifest = {column: _normalize_text(value) for column, value in df.iloc[0].to_dict().items()}
        if not _feeder_review_handoff_ready_for_operator(manifest):
            return True
    return False


def _list_feeder_review_handoff_manifests(root_path: Path) -> list[dict[str, str]]:
    handoff_root = root_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"
    if not handoff_root.exists():
        return []
    manifests: list[dict[str, str]] = []
    for manifest_path in sorted(handoff_root.glob("*/*/manifest.csv")):
        try:
            df = pd.read_csv(manifest_path, dtype=str).fillna("")
        except (FileNotFoundError, pd.errors.EmptyDataError):
            continue
        if df.empty:
            continue
        row = {column: _normalize_text(value) for column, value in df.iloc[0].to_dict().items()}
        if not _feeder_review_handoff_ready_for_operator(row):
            continue
        supplier_id = _normalize_text(row.get("supplier_id", ""))
        run_id = _normalize_text(row.get("run_id", ""))
        if not supplier_id or not run_id:
            continue
        row["_snapshot_id"] = _feeder_review_handoff_snapshot_id(supplier_id, run_id)
        manifests.append(row)
    return manifests


def _feeder_review_handoff_manifest_sort_date(manifest: dict[str, str]) -> str:
    return (
        _normalize_text(manifest.get("completed_at_utc", ""))
        or _normalize_text(manifest.get("source_seen_at_utc", ""))
        or _normalize_text(manifest.get("built_at_utc", ""))
    )


def _list_feeder_review_handoff_group_manifests(root_path: Path, supplier_id: str) -> list[dict[str, str]]:
    supplier = _normalize_text(supplier_id)
    if not supplier:
        return []
    manifests = [
        manifest
        for manifest in _list_feeder_review_handoff_manifests(root_path)
        if _normalize_text(manifest.get("supplier_id", "")) == supplier
    ]
    manifests.sort(
        key=lambda row: (
            _feeder_review_handoff_manifest_sort_date(row),
            _normalize_text(row.get("run_id", "")),
        )
    )
    return manifests


def _ai_product_check_gate_handoff_root(root_path: Path) -> Path:
    return root_path / "out" / "systems" / "F" / "price_list_manager" / "review_handoffs"


def _ai_product_check_gate_resolve_path(root_path: Path, path_text: object) -> Path:
    clean = _normalize_text(path_text)
    if clean == "":
        return Path()
    path = Path(clean)
    if path.is_absolute():
        return path
    return root_path / path


def _ai_product_check_gate_snippet(*values: object, limit: int = 220) -> str:
    text = " ".join(" ".join(_normalize_text(value).split()) for value in values if _normalize_text(value))
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _ai_product_check_gate_decision_lookup(decision_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if decision_df.empty or "f032_decision_id" not in decision_df.columns:
        return {}
    lookup: dict[str, dict[str, str]] = {}
    for _, row in decision_df.iterrows():
        row_dict = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        decision_id = _normalize_text(row_dict.get("f032_decision_id", ""))
        if decision_id:
            lookup[decision_id] = row_dict
    return lookup


def _ai_product_check_gate_secondary_reason(
    *,
    rule_action: str,
    rule_fail_category: str,
    rule_reason: str,
    supplier_title: str,
    amazon_title: str,
) -> str:
    title_note = ""
    if supplier_title and amazon_title:
        title_note = f" Supplier title: {supplier_title}. Amazon title: {amazon_title}."
    reason_note = f" F032 reason: {rule_reason}." if rule_reason else ""
    if rule_action == "allow_if_other_checks_pass":
        return (
            "Titles carry enough evidence for this row; product description/page text is secondary evidence, "
            "so the old missing-page rescan was not allowed to block a clear title match."
            f"{title_note}{reason_note}"
        )
    if rule_action == "manual_review":
        category = rule_fail_category.replace("_", " ") or "title evidence"
        return (
            f"Needs user guidance because the title evidence points to {category}; product description/page text "
            "can help, but it is not the only valid evidence source."
            f"{title_note}{reason_note}"
        )
    if rule_action == "remove_from_clean_pass":
        category = rule_fail_category.replace("_", " ") or "clear title breach"
        return (
            f"Removed from clean pass because the title evidence points to {category}; missing page text is "
            "secondary and must not rescue a bad match."
            f"{title_note}{reason_note}"
        )
    if rule_action == "rescan_needed":
        category = rule_fail_category.replace("_", " ") or "missing core evidence"
        return (
            f"Rescan needed because the current evidence still points to {category}; page text remains useful "
            "supporting evidence for this row."
            f"{title_note}{reason_note}"
        )
    return (
        "Product description/page text is secondary evidence here, and the stale missing-page decision was "
        "replaced by the current F032 decision."
        f"{title_note}{reason_note}"
    )


def _ai_product_check_gate_effective_decision(
    queue_data: dict[str, str],
    decision: dict[str, str],
) -> dict[str, str]:
    rule_action = _normalize_text(queue_data.get("f032_rule_action", ""))
    rule_bucket = _normalize_text(queue_data.get("f032_rule_bucket", ""))
    rule_confidence = _normalize_text(queue_data.get("f032_rule_confidence", ""))
    rule_reason = _normalize_text(queue_data.get("f032_rule_reason", ""))
    rule_fail_category = _normalize_text(queue_data.get("f032_rule_fail_category", ""))
    supplier_title = _normalize_text(queue_data.get("supplier_title", "")) or _normalize_text(queue_data.get("title", ""))
    amazon_title = _normalize_text(queue_data.get("amazon_title", ""))
    codex_action = _normalize_text(decision.get("codex_ai_action", ""))
    codex_fail_category = _normalize_text(decision.get("codex_ai_fail_category", ""))
    codex_reviewer = _normalize_text(decision.get("codex_ai_reviewer", ""))
    codex_evidence = _normalize_text(decision.get("codex_ai_evidence", ""))
    if (
        rule_action != ""
        and (
            (
                codex_action == "rescan_needed"
                and codex_fail_category == "missing_page_evidence"
            )
            or (
                codex_reviewer == "fpm155_secondary_evidence_guard"
                and "stale_missing_page_rescan_deferred_to_f032" in codex_evidence
            )
        )
        and not (
            rule_action == "rescan_needed"
            and rule_fail_category in {"", "missing_evidence_rescan_needed", "missing_page_evidence"}
            and codex_action == "rescan_needed"
            and codex_fail_category == "missing_page_evidence"
        )
    ):
        effective = dict(decision)
        effective["codex_ai_action"] = rule_action
        effective["codex_ai_decision_bucket"] = rule_bucket or ("ai_review_clear" if rule_action == "allow_if_other_checks_pass" else rule_action)
        effective["codex_ai_confidence"] = rule_confidence or "medium"
        effective["codex_ai_needs_user_guidance"] = "1" if rule_action == "manual_review" else "0"
        effective["codex_ai_rescan_needed"] = "1" if rule_action == "rescan_needed" else "0"
        effective["codex_ai_reason"] = _ai_product_check_gate_secondary_reason(
            rule_action=rule_action,
            rule_fail_category=rule_fail_category,
            rule_reason=rule_reason,
            supplier_title=supplier_title,
            amazon_title=amazon_title,
        )
        effective["codex_ai_evidence"] = (
            f"stale_missing_page_rescan_deferred_to_f032 | "
            f"f032_rule_action={rule_action} | "
            f"f032_rule_fail_category={rule_fail_category} | "
            f"supplier_title={supplier_title} | "
            f"amazon_title={amazon_title} | "
            f"f032_rule_reason={rule_reason}"
        )
        effective["codex_ai_fail_category"] = "" if rule_action == "allow_if_other_checks_pass" else rule_fail_category
        return effective
    return decision


def _ai_product_check_gate_status(action: object, *, queue_exists: bool = True) -> str:
    if not queue_exists:
        return "waiting_for_ai_queue"
    clean_action = _normalize_text(action).lower()
    if clean_action == "":
        return "pending_ai_check"
    if clean_action == "allow_if_other_checks_pass":
        return "ai_cleared"
    if clean_action == "manual_review":
        return "needs_user_guidance"
    if clean_action == "rescan_needed":
        return "rescan_needed"
    if clean_action == "remove_from_clean_pass":
        return "ai_rejected"
    return "invalid_ai_decision"


def _ai_product_check_gate_legacy_review_rows(
    root_path: Path,
    *,
    manifest: dict[str, str],
    supplier_id: str,
    supplier_name: str,
    run_id: str,
    handoff_id: str,
    ai_gate_status: str,
    operator_ready_flag: str,
    queue_path: Path,
    decision_path: Path,
    manifest_path: Path,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    review_paths = (
        ("passes", _normalize_text(manifest.get("pass_review_path", ""))),
        ("near_misses", _normalize_text(manifest.get("near_miss_review_path", ""))),
    )
    for pack_type, path_text in review_paths:
        review_path = _ai_product_check_gate_resolve_path(root_path, path_text)
        if review_path == Path():
            continue
        review_df = _read_csv_safe(review_path)
        if review_df.empty:
            continue
        for _, review_row in review_df.iterrows():
            review_data = {column: _normalize_text(value) for column, value in review_row.to_dict().items()}
            rows.append(
                {
                    "handoff_id": handoff_id,
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "run_id": run_id,
                    "source_review_pack_type": pack_type,
                    "queue_state": "legacy_needs_ai_gate" if pack_type == "passes" else "legacy_manual_near_backlog",
                    "ai_gate_status": ai_gate_status,
                    "operator_ready_flag": operator_ready_flag,
                    "operator_visible_flag": "0",
                    "f032_decision_id": _normalize_text(review_data.get("f032_decision_id", "")),
                    "supplier_sku": _normalize_text(review_data.get("supplier_sku", "")),
                    "asin": _normalize_text(review_data.get("asin", "")).upper(),
                    "supplier_title": _normalize_text(review_data.get("supplier_title", ""))
                    or _normalize_text(review_data.get("supplier_product_title", ""))
                    or _normalize_text(review_data.get("title", "")),
                    "amazon_title": _normalize_text(review_data.get("amazon_title", ""))
                    or _normalize_text(review_data.get("title", "")),
                    "amazon_description_snippet": _ai_product_check_gate_snippet(
                        review_data.get("amazon_product_description", ""),
                        review_data.get("amazon_product_detail_text", ""),
                        review_data.get("amazon_feature_bullets", ""),
                    ),
                    "roi_pct": _normalize_text(review_data.get("profit_on_cost_pct", ""))
                    or _normalize_text(review_data.get("title_match_profit_on_cost_pct", ""))
                    or _normalize_text(review_data.get("roi_pct", "")),
                    "f032_rule_action": _normalize_text(review_data.get("f032_rule_action", ""))
                    or _normalize_text(review_data.get("f032_action", "")),
                    "f032_rule_bucket": _normalize_text(review_data.get("f032_rule_bucket", "")),
                    "f032_rule_reason": _normalize_text(review_data.get("f032_rule_reason", "")),
                    "codex_ai_action": _normalize_text(review_data.get("codex_ai_action", "")),
                    "codex_ai_decision_bucket": _normalize_text(review_data.get("codex_ai_decision_bucket", "")),
                    "codex_ai_confidence": _normalize_text(review_data.get("codex_ai_confidence", "")),
                    "codex_ai_needs_user_guidance": _normalize_text(
                        review_data.get("codex_ai_needs_user_guidance", "")
                    ),
                    "codex_ai_rescan_needed": _normalize_text(review_data.get("codex_ai_rescan_needed", "")),
                    "codex_ai_reason": _normalize_text(review_data.get("codex_ai_reason", "")),
                    "codex_ai_evidence": _normalize_text(review_data.get("codex_ai_evidence", "")),
                    "codex_ai_reviewed_utc": _normalize_text(review_data.get("codex_ai_reviewed_utc", "")),
                    "queue_path": str(queue_path),
                    "decision_path": str(decision_path),
                    "manifest_path": str(manifest_path),
                }
            )
    return rows


def _ai_product_check_gate_current_key(row: pd.Series) -> str:
    supplier = _normalize_text(row.get("supplier_id", "")).lower()
    supplier_sku = _normalize_text(row.get("supplier_sku", "")).upper()
    asin = _normalize_text(row.get("asin", "")).upper()
    if supplier and supplier_sku and asin:
        return f"product|{supplier}|{supplier_sku}|{asin}"
    decision_id = _normalize_text(row.get("f032_decision_id", ""))
    if supplier and decision_id:
        return f"decision|{supplier}|{decision_id}"
    handoff_id = _normalize_text(row.get("handoff_id", ""))
    run_id = _normalize_text(row.get("run_id", ""))
    return f"row|{handoff_id}|{run_id}|{decision_id}|{supplier_sku}|{asin}"


def _ai_product_check_gate_sort_current_first(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_current_key"] = out.apply(_ai_product_check_gate_current_key, axis=1)
    out["_current_sort_reviewed"] = out["codex_ai_reviewed_utc"].map(_normalize_text)
    out["_current_sort_run"] = out["run_id"].map(_normalize_text)
    out["_current_sort_handoff"] = out["handoff_id"].map(_normalize_text)
    out = out.sort_values(
        by=["_current_key", "_current_sort_reviewed", "_current_sort_run", "_current_sort_handoff"],
        ascending=[True, False, False, False],
    )
    out["_current_rank"] = out.groupby("_current_key").cumcount()
    return out


def build_ai_product_check_gate_df(root: Path | None = None, *, include_history: bool = False) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    handoff_root = _ai_product_check_gate_handoff_root(root_path)
    if not handoff_root.exists():
        return pd.DataFrame(columns=AI_PRODUCT_CHECK_GATE_COLUMNS)

    rows: list[dict[str, str]] = []
    run_dirs = {path.parent for path in handoff_root.glob("*/*/candidate_manifest.csv")}
    run_dirs.update(path.parent for path in handoff_root.glob("*/*/manifest.csv"))
    for run_dir in sorted(run_dirs):
        candidate_manifest_path = run_dir / "candidate_manifest.csv"
        manifest_path = run_dir / "manifest.csv"
        candidate_df = _read_csv_safe(candidate_manifest_path)
        manifest_df = _read_csv_safe(manifest_path)
        candidate_manifest = (
            {column: _normalize_text(value) for column, value in candidate_df.iloc[0].to_dict().items()}
            if not candidate_df.empty
            else {}
        )
        manifest = (
            {column: _normalize_text(value) for column, value in manifest_df.iloc[0].to_dict().items()}
            if not manifest_df.empty
            else {}
        )
        supplier_id = (
            _normalize_text(manifest.get("supplier_id", ""))
            or _normalize_text(candidate_manifest.get("supplier_id", ""))
            or run_dir.parent.name
        )
        supplier_name = (
            _normalize_text(manifest.get("supplier_name", ""))
            or _normalize_text(candidate_manifest.get("supplier_name", ""))
            or supplier_id
        )
        run_id = _normalize_text(manifest.get("run_id", "")) or _normalize_text(candidate_manifest.get("run_id", "")) or run_dir.name
        handoff_id = _feeder_review_handoff_snapshot_id(supplier_id, run_id)
        ai_gate_status = _normalize_text(manifest.get("ai_gate_status", "")) or "not_completed"
        operator_ready_flag = _normalize_text(manifest.get("operator_ready_flag", ""))
        queue_path = _ai_product_check_gate_resolve_path(
            root_path,
            _normalize_text(manifest.get("ai_review_queue_path", "")) or str(run_dir / "ai_review_queue.csv"),
        )
        decision_path = _ai_product_check_gate_resolve_path(
            root_path,
            _normalize_text(manifest.get("codex_ai_decision_path", ""))
            or _normalize_text(manifest.get("ai_gate_decision_path", ""))
            or str(run_dir / "codex_ai_review_decisions.csv"),
        )
        queue_df = _read_csv_safe(queue_path) if queue_path != Path() else pd.DataFrame()
        decision_lookup = _ai_product_check_gate_decision_lookup(
            _read_csv_safe(decision_path) if decision_path != Path() else pd.DataFrame()
        )
        if queue_df.empty:
            legacy_rows = (
                _ai_product_check_gate_legacy_review_rows(
                    root_path,
                    manifest=manifest,
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    run_id=run_id,
                    handoff_id=handoff_id,
                    ai_gate_status=ai_gate_status,
                    operator_ready_flag=operator_ready_flag,
                    queue_path=queue_path,
                    decision_path=decision_path,
                    manifest_path=manifest_path,
                )
                if manifest and not _feeder_review_handoff_ready_for_operator(manifest)
                else []
            )
            if legacy_rows:
                rows.extend(legacy_rows)
                continue
            if manifest and not candidate_manifest_path.exists():
                continue
            rows.append(
                {
                    "handoff_id": handoff_id,
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "run_id": run_id,
                    "source_review_pack_type": "",
                    "queue_state": _ai_product_check_gate_status("", queue_exists=False),
                    "ai_gate_status": ai_gate_status,
                    "operator_ready_flag": operator_ready_flag,
                    "operator_visible_flag": "0",
                    "queue_path": str(queue_path),
                    "decision_path": str(decision_path),
                    "manifest_path": str(manifest_path),
                }
            )
            continue

        for _, queue_row in queue_df.iterrows():
            queue_data = {column: _normalize_text(value) for column, value in queue_row.to_dict().items()}
            decision_id = _normalize_text(queue_data.get("f032_decision_id", ""))
            decision = _ai_product_check_gate_effective_decision(queue_data, decision_lookup.get(decision_id, {}))
            action = _normalize_text(decision.get("codex_ai_action", "")) or _normalize_text(
                queue_data.get("codex_ai_action", "")
            )
            action_normalized = action.lower()
            queue_state = _ai_product_check_gate_status(action)
            operator_visible = (
                "1"
                if operator_ready_flag == "1" and action_normalized in {"allow_if_other_checks_pass", "manual_review"}
                else "0"
            )
            rows.append(
                {
                    "handoff_id": handoff_id,
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "run_id": run_id,
                    "source_review_pack_type": _normalize_text(queue_data.get("source_review_pack_type", "")),
                    "queue_state": queue_state,
                    "ai_gate_status": ai_gate_status,
                    "operator_ready_flag": operator_ready_flag,
                    "operator_visible_flag": operator_visible,
                    "f032_decision_id": decision_id,
                    "supplier_sku": _normalize_text(queue_data.get("supplier_sku", "")),
                    "asin": _normalize_text(queue_data.get("asin", "")).upper(),
                    "supplier_title": _normalize_text(queue_data.get("supplier_title", ""))
                    or _normalize_text(queue_data.get("title", "")),
                    "amazon_title": _normalize_text(queue_data.get("amazon_title", "")),
                    "amazon_description_snippet": _ai_product_check_gate_snippet(
                        queue_data.get("amazon_product_description", ""),
                        queue_data.get("amazon_product_detail_text", ""),
                        queue_data.get("amazon_feature_bullets", ""),
                    ),
                    "roi_pct": _normalize_text(queue_data.get("profit_on_cost_pct", ""))
                    or _normalize_text(queue_data.get("title_match_profit_on_cost_pct", "")),
                    "f032_rule_action": _normalize_text(queue_data.get("f032_rule_action", "")),
                    "f032_rule_bucket": _normalize_text(queue_data.get("f032_rule_bucket", "")),
                    "f032_rule_reason": _normalize_text(queue_data.get("f032_rule_reason", "")),
                    "codex_ai_action": action,
                    "codex_ai_decision_bucket": _normalize_text(decision.get("codex_ai_decision_bucket", ""))
                    or _normalize_text(queue_data.get("codex_ai_decision_bucket", "")),
                    "codex_ai_confidence": _normalize_text(decision.get("codex_ai_confidence", ""))
                    or _normalize_text(queue_data.get("codex_ai_confidence", "")),
                    "codex_ai_needs_user_guidance": _normalize_text(
                        decision.get("codex_ai_needs_user_guidance", "")
                    ),
                    "codex_ai_rescan_needed": _normalize_text(decision.get("codex_ai_rescan_needed", "")),
                    "codex_ai_reason": _normalize_text(decision.get("codex_ai_reason", ""))
                    or _normalize_text(queue_data.get("codex_ai_reason", "")),
                    "codex_ai_evidence": _normalize_text(decision.get("codex_ai_evidence", ""))
                    or _normalize_text(queue_data.get("codex_ai_evidence", "")),
                    "codex_ai_reviewed_utc": _normalize_text(decision.get("codex_ai_reviewed_utc", "")),
                    "codex_ai_reviewer": _normalize_text(decision.get("codex_ai_reviewer", "")),
                    "queue_path": str(queue_path),
                    "decision_path": str(decision_path),
                    "manifest_path": str(manifest_path),
                }
            )

    out = pd.DataFrame(rows)
    for column in AI_PRODUCT_CHECK_GATE_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    if out.empty:
        return out[AI_PRODUCT_CHECK_GATE_COLUMNS]
    if not include_history:
        out = _ai_product_check_gate_sort_current_first(out)
        out = out[out["_current_rank"].eq(0)].copy()
    state_order = {state: idx for idx, state in enumerate(AI_PRODUCT_CHECK_GATE_STATUS_ORDER)}
    out["_state_sort"] = out["queue_state"].map(lambda value: state_order.get(_normalize_text(value), 99))
    out = out.sort_values(
        by=["_state_sort", "codex_ai_reviewed_utc", "supplier_id", "run_id", "supplier_sku"],
        ascending=[True, False, True, True, True],
    )
    return out[AI_PRODUCT_CHECK_GATE_COLUMNS].reset_index(drop=True)


def _feeder_review_handoff_label(manifest: dict[str, str], summary: dict[str, str]) -> str:
    supplier = (
        _normalize_text(manifest.get("supplier_name", ""))
        or _normalize_text(summary.get("active_supplier_label", ""))
        or _normalize_text(manifest.get("supplier_id", ""))
        or "Supplier"
    )
    date_source = (
        _normalize_text(manifest.get("completed_at_utc", ""))
        or _normalize_text(manifest.get("source_seen_at_utc", ""))
        or _normalize_text(manifest.get("built_at_utc", ""))
    )
    label_date = "completed"
    if date_source:
        try:
            parsed = datetime.fromisoformat(date_source.replace("Z", "+00:00"))
            label_date = parsed.strftime("%d %b %H:%M")
        except ValueError:
            label_date = date_source
    return f"{supplier} - completed {label_date}"


def _format_review_pack_snapshot_date(snapshot: str) -> str:
    raw = _normalize_text(snapshot)
    if raw == "" or raw == "latest":
        return "latest"
    try:
        parsed = datetime.strptime(raw, "%Y%m%dT%H%M%SZ")
        return parsed.strftime("%d %b %H:%M")
    except ValueError:
        return raw


def _supplier_review_pack_label(summary: dict[str, str], snapshot: str) -> str:
    supplier = (
        _normalize_text(summary.get("active_supplier_label", ""))
        or _normalize_text(summary.get("active_supplier_id", ""))
        or "Supplier"
    )
    pack_date = _format_review_pack_snapshot_date(snapshot)
    source_seen_utc = _normalize_text(summary.get("source_seen_at_utc", ""))
    observed_utc = _normalize_text(summary.get("observed_utc", ""))
    date_source = source_seen_utc or observed_utc
    if date_source:
        try:
            parsed = datetime.fromisoformat(date_source.replace("Z", "+00:00"))
            pack_date = parsed.strftime("%d %b %H:%M")
        except ValueError:
            pass
    return f"{supplier} - {pack_date}"


def _feeder_review_pack_supplier_name(label: str) -> str:
    text = _normalize_text(label)
    if " - " in text:
        return text.split(" - ", 1)[0].strip() or text
    return text or "Supplier"


def _feeder_review_pack_work_phrase(lane_label: str, count: int, *, unique: bool = False) -> str:
    lane = _normalize_text(lane_label).lower()
    if lane == "passes":
        uniqueness = "unique " if unique else ""
        return f"{count} {uniqueness}scanner {'find' if count == 1 else 'finds'} waiting"
    if lane == "manual review":
        return f"{count} judgement {'check' if count == 1 else 'checks'} waiting"
    if lane == "near misses":
        return f"{count} close {'call' if count == 1 else 'calls'} waiting"
    return f"{count} {'product' if count == 1 else 'products'} waiting"


def _feeder_review_pack_label_for_lane(
    label: str,
    lane_label: str,
    counts: dict[str, int],
    *,
    unique: bool = False,
) -> str:
    count = int(counts.get("undecided_rows", 0))
    return f"{_feeder_review_pack_supplier_name(label)} - {_feeder_review_pack_work_phrase(lane_label, count, unique=unique)}"


def _feeder_review_lane_todo_counts(
    root_path: Path,
    snapshot: str,
    *,
    pack_type: str,
    lane_filter: str,
    latest_events_df: pd.DataFrame,
) -> dict[str, int]:
    normalized_pack_type = _normalize_text(pack_type)
    if not normalized_pack_type:
        return {"available_rows": 0, "undecided_rows": 0}
    source_df = load_feeder_review_source_df(normalized_pack_type, root=root_path, review_pack_snapshot=snapshot)
    source_df = _apply_feeder_review_lane_filter(source_df, pack_type=normalized_pack_type, lane_filter=lane_filter)
    source_df = _merge_latest_review_columns(source_df, latest_events_df)
    if source_df.empty:
        return {"available_rows": 0, "undecided_rows": 0}
    undecided_rows = int(source_df["latest_review_decision"].map(_normalize_text).eq("").sum())
    return {"available_rows": int(len(source_df.index)), "undecided_rows": undecided_rows}


def _feeder_review_price_file_key(summary: dict[str, str]) -> tuple[str, str]:
    supplier = _normalize_text(summary.get("active_supplier_id", ""))
    batch_id = (
        _normalize_text(summary.get("price_file_batch_id", ""))
        or _normalize_text(summary.get("source_seen_at_utc", ""))
        or _normalize_text(summary.get("active_run_id", ""))
    )
    return supplier, batch_id


def _feeder_review_pack_sort_key(summary: dict[str, str], snapshot: str) -> tuple[str, str, str]:
    supplier = _normalize_text(summary.get("active_supplier_id", ""))
    date_source = (
        _normalize_text(summary.get("source_seen_at_utc", ""))
        or _normalize_text(summary.get("observed_utc", ""))
    )
    if not date_source:
        raw_snapshot = _normalize_text(snapshot)
        if raw_snapshot and raw_snapshot != "latest":
            date_source = raw_snapshot
    return date_source, supplier, _normalize_text(snapshot)


def list_feeder_review_pack_options(
    root: Path | None = None,
    *,
    include_history: bool = False,
    pack_type: str = "",
    lane_filter: str = "",
    lane_label: str = "",
) -> list[dict[str, str]]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    reports_dir = root_path / "out" / "analysis_reports"
    options: list[dict[str, str]] = []
    seen_pack_keys: set[tuple[str, str]] = set()
    seen_active_runs: set[tuple[str, str]] = set()
    seen_snapshots: set[str] = set()
    normalized_pack_type = _normalize_text(pack_type)
    normalized_lane_filter = _normalize_text(lane_filter)
    normalized_lane_label = _normalize_text(lane_label)
    latest_events_df = (
        _latest_feeder_review_event_by_identity(load_feeder_review_events_df(root=root_path))
        if normalized_pack_type
        else pd.DataFrame()
    )

    def _counts_for_snapshot(snapshot_id: str) -> dict[str, int]:
        if not normalized_pack_type:
            return {"available_rows": 0, "undecided_rows": 0}
        return _feeder_review_lane_todo_counts(
            root_path,
            snapshot_id,
            pack_type=normalized_pack_type,
            lane_filter=normalized_lane_filter,
            latest_events_df=latest_events_df,
        )

    def _option_label(label: str, counts: dict[str, int]) -> str:
        if not normalized_pack_type:
            return label
        return _feeder_review_pack_label_for_lane(label, normalized_lane_label, counts)

    def _skip_for_lane(counts: dict[str, int]) -> bool:
        return bool(normalized_pack_type and not include_history and int(counts.get("undecided_rows", 0)) <= 0)

    handoff_manifests = _list_feeder_review_handoff_manifests(root_path)
    if normalized_pack_type and not include_history:
        grouped_handoffs: dict[str, list[dict[str, str]]] = {}
        for manifest in handoff_manifests:
            supplier_id = _normalize_text(manifest.get("supplier_id", ""))
            if supplier_id:
                grouped_handoffs.setdefault(supplier_id, []).append(manifest)
        for supplier_id, manifests in grouped_handoffs.items():
            snapshot = _feeder_review_handoff_group_snapshot_id(supplier_id)
            if snapshot in seen_snapshots:
                continue
            summary = load_feeder_review_summary(root=root_path, review_pack_snapshot=snapshot)
            lane_counts = _counts_for_snapshot(snapshot)
            if _skip_for_lane(lane_counts):
                continue
            supplier_label = _normalize_text(summary.get("active_supplier_label", "")) or supplier_id
            seen_snapshots.add(snapshot)
            for manifest in manifests:
                seen_snapshots.add(_normalize_text(manifest.get("_snapshot_id", "")))
                seen_active_runs.add(
                    (
                        _normalize_text(manifest.get("supplier_id", "")),
                        _normalize_text(manifest.get("run_id", "")),
                    )
                )
            seen_pack_keys.add(_feeder_review_price_file_key(summary))
            options.append(
                {
                    "id": snapshot,
                    "label": _feeder_review_pack_label_for_lane(
                        supplier_label,
                        normalized_lane_label,
                        lane_counts,
                        unique=True,
                    ),
                    "_sort_key": "|".join(_feeder_review_pack_sort_key(summary, snapshot)),
                }
            )
    else:
        for manifest in handoff_manifests:
            snapshot = _normalize_text(manifest.get("_snapshot_id", ""))
            if not snapshot or snapshot in seen_snapshots:
                continue
            summary = load_feeder_review_summary(root=root_path, review_pack_snapshot=snapshot)
            lane_counts = _counts_for_snapshot(snapshot)
            if _skip_for_lane(lane_counts):
                continue
            pack_key = _feeder_review_price_file_key(summary)
            active_run_key = (
                _normalize_text(summary.get("active_supplier_id", "")),
                _normalize_text(summary.get("active_run_id", "")),
            )
            seen_snapshots.add(snapshot)
            seen_pack_keys.add(pack_key)
            seen_active_runs.add(active_run_key)
            options.append(
                {
                    "id": snapshot,
                    "label": _option_label(_feeder_review_handoff_label(manifest, summary), lane_counts),
                    "_sort_key": "|".join(_feeder_review_pack_sort_key(summary, snapshot)),
                }
            )

    latest_summary = load_feeder_review_summary(root=root_path, review_pack_snapshot="latest")
    if latest_summary:
        lane_counts = _counts_for_snapshot("latest")
        latest_label = _supplier_review_pack_label(latest_summary, "latest")
        latest_pack_key = _feeder_review_price_file_key(latest_summary)
        latest_active_run_key = (
            _normalize_text(latest_summary.get("active_supplier_id", "")),
            _normalize_text(latest_summary.get("active_run_id", "")),
        )
        duplicate_latest = latest_pack_key in seen_pack_keys or latest_active_run_key in seen_active_runs
        if not _skip_for_lane(lane_counts) and (include_history or not duplicate_latest):
            options.append(
                {
                    "id": "latest",
                    "label": _option_label(latest_label, lane_counts),
                    "_sort_key": "|".join(_feeder_review_pack_sort_key(latest_summary, "latest")),
                }
            )
            seen_snapshots.add("latest")
            seen_pack_keys.add(latest_pack_key)
            seen_active_runs.add(latest_active_run_key)
    elif not normalized_pack_type:
        options.append({"id": "latest", "label": "latest", "_sort_key": "latest||latest"})
        seen_snapshots.add("latest")

    for snapshot in list_review_summary_snapshots():
        snapshot = _normalize_text(snapshot)
        if snapshot == "" or snapshot in seen_snapshots:
            continue
        if _review_snapshot_requires_ai_gate(root_path, snapshot):
            continue
        summary = load_feeder_review_summary(root=root_path, review_pack_snapshot=snapshot)
        pack_key = _feeder_review_price_file_key(summary)
        active_run_key = (
            _normalize_text(summary.get("active_supplier_id", "")),
            _normalize_text(summary.get("active_run_id", "")),
        )
        has_download_timestamp = bool(
            _normalize_text(summary.get("source_seen_at_utc", ""))
            or _normalize_text(summary.get("price_file_batch_id", ""))
        )
        if not include_history and not has_download_timestamp and active_run_key in seen_active_runs:
            continue
        if not include_history and pack_key in seen_pack_keys:
            continue
        lane_counts = _counts_for_snapshot(snapshot)
        if _skip_for_lane(lane_counts):
            continue
        seen_snapshots.add(snapshot)
        seen_pack_keys.add(pack_key)
        seen_active_runs.add(active_run_key)
        options.append(
            {
                "id": snapshot,
                "label": _option_label(_supplier_review_pack_label(summary, snapshot), lane_counts),
                "_sort_key": "|".join(_feeder_review_pack_sort_key(summary, snapshot)),
            }
        )

    if not reports_dir.exists():
        options.sort(key=lambda option: option.get("_sort_key", ""))
        return [{k: v for k, v in option.items() if not k.startswith("_")} for option in options]

    prefix = "f_live_price_file_review_summary_"
    suffix = ".csv"
    for path in sorted(reports_dir.glob(f"{prefix}*.csv"), reverse=True):
        name = path.name
        if name.endswith("_latest.csv") or not name.startswith(prefix) or not name.endswith(suffix):
            continue
        snapshot = name[len(prefix) : -len(suffix)]
        if snapshot in seen_snapshots:
            continue
        if _review_snapshot_requires_ai_gate(root_path, snapshot):
            continue
        summary = load_feeder_review_summary(root=root_path, review_pack_snapshot=snapshot)
        pack_key = _feeder_review_price_file_key(summary)
        active_run_key = (
            _normalize_text(summary.get("active_supplier_id", "")),
            _normalize_text(summary.get("active_run_id", "")),
        )
        has_download_timestamp = bool(
            _normalize_text(summary.get("source_seen_at_utc", ""))
            or _normalize_text(summary.get("price_file_batch_id", ""))
        )
        if not include_history and not has_download_timestamp and active_run_key in seen_active_runs:
            continue
        if not include_history and pack_key in seen_pack_keys:
            continue
        lane_counts = _counts_for_snapshot(snapshot)
        if _skip_for_lane(lane_counts):
            continue
        seen_snapshots.add(snapshot)
        seen_pack_keys.add(pack_key)
        seen_active_runs.add(active_run_key)
        options.append(
            {
                "id": snapshot,
                "label": _option_label(_supplier_review_pack_label(summary, snapshot), lane_counts),
                "_sort_key": "|".join(_feeder_review_pack_sort_key(summary, snapshot)),
            }
        )
    options.sort(key=lambda option: option.get("_sort_key", ""))
    return [{k: v for k, v in option.items() if not k.startswith("_")} for option in options]


def load_feeder_review_summary(root: Path | None = None, review_pack_snapshot: str = "latest") -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    snapshot = _normalize_text(review_pack_snapshot) or "latest"
    if _is_feeder_review_handoff_group_snapshot(snapshot):
        supplier_id = _parse_feeder_review_handoff_group_snapshot(snapshot)
        manifests = _list_feeder_review_handoff_group_manifests(root_path, supplier_id)
        if not manifests:
            return {}
        latest_manifest = manifests[-1]
        supplier_label = (
            _normalize_text(latest_manifest.get("supplier_name", ""))
            or _normalize_text(_supplier_display_map(root_path).get(supplier_id, ""))
            or supplier_id
        )
        return {
            "active_supplier_id": supplier_id,
            "active_run_id": "multiple_handoffs",
            "active_supplier_label": supplier_label,
            "observed_utc": _feeder_review_handoff_manifest_sort_date(latest_manifest),
            "completed_at_utc": _normalize_text(latest_manifest.get("completed_at_utc", "")),
            "review_snapshot_id": snapshot,
        }
    summary_path = _feeder_review_summary_path(root_path, review_pack_snapshot)
    summary_df = read_review_summary_dataframe(
        summary_path,
        snapshot_id=_feeder_review_reader_snapshot_id(root_path, snapshot),
        dtype=str,
    )
    summary: dict[str, str] = {}
    if summary_df.empty:
        summary = {}
    else:
        if "observed_utc" in summary_df.columns:
            observed_values = [v for v in summary_df["observed_utc"].map(_normalize_text).tolist() if v]
            if observed_values:
                summary["observed_utc"] = observed_values[0]
        for _, row in summary_df.iterrows():
            metric = _normalize_text(row.get("metric", ""))
            if metric:
                summary[metric] = _normalize_text(row.get("value", ""))
    if _is_feeder_review_handoff_snapshot(snapshot):
        manifest = _read_feeder_review_handoff_manifest(root_path, snapshot)
        if manifest:
            summary["active_supplier_id"] = _normalize_text(manifest.get("supplier_id", "")) or _normalize_text(
                summary.get("active_supplier_id", "")
            )
            summary["active_run_id"] = _normalize_text(manifest.get("run_id", "")) or _normalize_text(
                summary.get("active_run_id", "")
            )
            summary["active_supplier_label"] = _normalize_text(manifest.get("supplier_name", "")) or _normalize_text(
                summary.get("active_supplier_label", "")
            )
            summary["source_file_path"] = _normalize_text(manifest.get("source_file_path", ""))
            summary["source_seen_at_utc"] = _normalize_text(manifest.get("source_seen_at_utc", "")) or _normalize_text(
                summary.get("source_seen_at_utc", "")
            )
            summary["completed_at_utc"] = _normalize_text(manifest.get("completed_at_utc", ""))
            summary["review_snapshot_id"] = _normalize_text(manifest.get("review_snapshot_id", ""))
    active_supplier_id = _normalize_text(summary.get("active_supplier_id", ""))
    if active_supplier_id:
        supplier_name = _normalize_text(_supplier_display_map(root_path).get(active_supplier_id, ""))
        if supplier_name:
            summary["active_supplier_label"] = supplier_name
    return summary


def _ensure_feeder_review_manual_columns(source_df: pd.DataFrame) -> pd.DataFrame:
    work = source_df.copy()
    if "near_miss_type" not in work.columns:
        work["near_miss_type"] = ""
    for col in FEEDER_REVIEW_MANUAL_ACTION_COLUMNS:
        if col not in work.columns:
            work[col] = ""
    return work


def _feeder_review_manual_review_mask(source_df: pd.DataFrame) -> pd.Series:
    work = _ensure_feeder_review_manual_columns(source_df)
    if work.empty:
        return pd.Series([], dtype=bool, index=work.index)
    mask = work["near_miss_type"].map(_normalize_text).str.lower().str.contains("manual_review", regex=False)
    for col in FEEDER_REVIEW_MANUAL_ACTION_COLUMNS:
        mask = mask | work[col].map(_normalize_text).str.lower().eq("manual_review")
    return mask.fillna(False)


def _apply_feeder_review_lane_filter(source_df: pd.DataFrame, *, pack_type: str, lane_filter: str = "") -> pd.DataFrame:
    if source_df.empty or pack_type != "near_misses":
        return source_df.copy()
    normalized_filter = _normalize_text(lane_filter).lower()
    if normalized_filter not in {"manual_review", "near_misses"}:
        return source_df.copy()
    manual_mask = _feeder_review_manual_review_mask(source_df)
    if normalized_filter == "manual_review":
        return source_df[manual_mask].copy()
    return source_df[~manual_mask].copy()


def _feeder_review_manifest_for_snapshot(root_path: Path, review_pack_snapshot: str) -> dict[str, str]:
    snapshot = _normalize_text(review_pack_snapshot) or "latest"
    if _is_feeder_review_handoff_snapshot(snapshot):
        return _read_feeder_review_handoff_manifest(root_path, snapshot)
    if snapshot == "latest":
        manifest = _read_feeder_review_live_manifest(root_path)
        return manifest if _feeder_review_handoff_ready_for_operator(manifest) else {}
    return {}


def _queue_lookup_keys(row: dict[str, str]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    decision_id = _normalize_text(row.get("f032_decision_id", ""))
    candidate_id = _normalize_text(row.get("candidate_id", ""))
    supplier_sku = _normalize_text(row.get("supplier_sku", "")).upper()
    asin = _normalize_text(row.get("asin", "")).upper()
    if decision_id:
        keys.append(("decision", decision_id))
    if candidate_id:
        keys.append(("candidate", candidate_id))
    if supplier_sku and asin:
        keys.append(("sku_asin", f"{supplier_sku}|{asin}"))
    return keys


def _merge_feeder_review_ai_queue_commercial_fields(
    root_path: Path,
    work: pd.DataFrame,
    *,
    review_pack_snapshot: str,
) -> pd.DataFrame:
    if work.empty:
        return work
    manifest = _feeder_review_manifest_for_snapshot(root_path, review_pack_snapshot)
    queue_path = _ai_product_check_gate_resolve_path(root_path, manifest.get("ai_review_queue_path", ""))
    if queue_path == Path() or not queue_path.exists():
        return work
    queue_df = _read_csv_safe(queue_path)
    if queue_df.empty:
        return work

    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for _, row in queue_df.iterrows():
        record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        for key in _queue_lookup_keys(record):
            lookup[key] = record

    out = work.copy()
    fill_map = {
        "profit_on_cost_pct": ["profit_on_cost_pct", "title_match_profit_on_cost_pct"],
        "title_match_profit_on_cost_pct": ["title_match_profit_on_cost_pct", "profit_on_cost_pct"],
        "profit_per_unit_30d_gbp": ["profit_per_unit_gbp"],
        "expected_profit_next_30d_gbp": ["expected_profit_gbp"],
        "estimated_monthly_profit_gbp": ["expected_profit_gbp"],
        "supplier_unit_cost_gbp": ["supplier_unit_cost_gbp"],
        "amazon_sell_price_gbp": ["amazon_sell_price_gbp"],
    }
    for target in fill_map:
        if target not in out.columns:
            out[target] = ""

    for idx, row in out.iterrows():
        row_record = {column: _normalize_text(value) for column, value in row.to_dict().items()}
        queue_record: dict[str, str] = {}
        for key in _queue_lookup_keys(row_record):
            queue_record = lookup.get(key, {})
            if queue_record:
                break
        if not queue_record:
            continue
        for target, sources in fill_map.items():
            if _normalize_text(out.at[idx, target]):
                continue
            for source in sources:
                value = _normalize_text(queue_record.get(source, ""))
                if value:
                    out.at[idx, target] = value
                    break
    return out


def _dedupe_feeder_review_source_by_product(source_df: pd.DataFrame) -> pd.DataFrame:
    if source_df.empty:
        return source_df
    work = source_df.copy()
    for column in ("active_supplier_id", "review_pack_type", "asin_padded", "active_run_id", "candidate_id"):
        if column not in work.columns:
            work[column] = ""
        work[column] = work[column].map(_normalize_text)
    work["_product_dedupe_key"] = work["asin_padded"].map(_normalize_text)
    missing_asin = work["_product_dedupe_key"].eq("")
    if missing_asin.any():
        work.loc[missing_asin, "_product_dedupe_key"] = (
            "candidate|"
            + work.loc[missing_asin, "active_run_id"].map(_normalize_text)
            + "|"
            + work.loc[missing_asin, "candidate_id"].map(_normalize_text)
        )
    if "_handoff_group_sort_date" not in work.columns:
        work["_handoff_group_sort_date"] = ""
    if "_handoff_group_source_row" not in work.columns:
        work["_handoff_group_source_row"] = ""
    work["_handoff_group_sort_date"] = work["_handoff_group_sort_date"].map(_normalize_text)
    work["_handoff_group_source_row"] = pd.to_numeric(work["_handoff_group_source_row"], errors="coerce")
    work = work.sort_values(
        by=["_handoff_group_sort_date", "_handoff_group_source_row"],
        ascending=[False, True],
        kind="stable",
    )
    work = work.drop_duplicates(
        subset=["active_supplier_id", "review_pack_type", "_product_dedupe_key"],
        keep="first",
    )
    return work.drop(
        columns=["_product_dedupe_key", "_handoff_group_sort_date", "_handoff_group_source_row"],
        errors="ignore",
    ).reset_index(drop=True)


def _load_feeder_review_handoff_group_source_df(
    pack_type: str,
    *,
    root_path: Path,
    supplier_id: str,
) -> pd.DataFrame:
    manifests = _list_feeder_review_handoff_group_manifests(root_path, supplier_id)
    if not manifests:
        return pd.DataFrame()
    parts: list[pd.DataFrame] = []
    for manifest in manifests:
        snapshot_id = _normalize_text(manifest.get("_snapshot_id", ""))
        if not snapshot_id:
            continue
        part = load_feeder_review_source_df(pack_type, root=root_path, review_pack_snapshot=snapshot_id)
        if part.empty:
            continue
        part = part.copy()
        part["_handoff_group_sort_date"] = _feeder_review_handoff_manifest_sort_date(manifest)
        part["_handoff_group_source_row"] = range(len(part.index))
        parts.append(part)
    if not parts:
        return pd.DataFrame()
    combined = pd.concat(parts, ignore_index=True)
    return _dedupe_feeder_review_source_by_product(combined)


def load_feeder_review_source_df(
    pack_type: str,
    *,
    root: Path | None = None,
    review_pack_snapshot: str = "latest",
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    snapshot = _normalize_text(review_pack_snapshot) or "latest"
    if _is_feeder_review_handoff_group_snapshot(snapshot):
        supplier_id = _parse_feeder_review_handoff_group_snapshot(snapshot)
        return _load_feeder_review_handoff_group_source_df(pack_type, root_path=root_path, supplier_id=supplier_id)
    source_df = read_review_pack_dataframe(
        _feeder_review_pack_path(root_path, pack_type, snapshot),
        pack_type=pack_type,
        snapshot_id=_feeder_review_reader_snapshot_id(root_path, snapshot),
        dtype=str,
    )
    if source_df.empty:
        return source_df
    work = source_df.copy()
    work = _merge_feeder_review_ai_queue_commercial_fields(
        root_path,
        work,
        review_pack_snapshot=review_pack_snapshot,
    )
    work["_source_row_num"] = range(len(work.index))
    work["review_pack_type"] = pack_type
    if "active_supplier_id" not in work.columns:
        work["active_supplier_id"] = ""
    if "active_run_id" not in work.columns:
        work["active_run_id"] = ""
    if "review_batch_id" not in work.columns:
        work["review_batch_id"] = ""
    if "candidate_id" not in work.columns:
        work["candidate_id"] = ""
    if "supplier_sku" not in work.columns:
        work["supplier_sku"] = ""
    if "asin" not in work.columns:
        work["asin"] = ""
    if "title" not in work.columns:
        work["title"] = ""
    if "main_image" not in work.columns:
        work["main_image"] = ""
    if "brand" not in work.columns:
        work["brand"] = ""
    if "main_rank" not in work.columns:
        work["main_rank"] = ""
    if "review_priority_score" not in work.columns:
        work["review_priority_score"] = ""
    if "commercial_note" not in work.columns:
        work["commercial_note"] = ""
    if "why_data_summary" not in work.columns:
        work["why_data_summary"] = ""
    if "watch_data_summary" not in work.columns:
        work["watch_data_summary"] = ""
    if "pass_reason_summary" not in work.columns:
        work["pass_reason_summary"] = ""
    if "screening_fail_code" not in work.columns:
        work["screening_fail_code"] = ""
    if "recovery_hint" not in work.columns:
        work["recovery_hint"] = ""
    if "original_point_score" not in work.columns:
        work["original_point_score"] = ""
    if "original_test_result" not in work.columns:
        work["original_test_result"] = ""
    if "original_test_status_reason" not in work.columns:
        work["original_test_status_reason"] = ""
    if "original_test_gate" not in work.columns:
        work["original_test_gate"] = ""
    work = _ensure_feeder_review_manual_columns(work)
    work["asin_padded"] = work["asin"].map(_pad_asin_to_10)
    work["amazon_dp_url"] = work["asin"].map(_amazon_dp_url)
    work["review_roi_pct"] = work.apply(_feeder_review_roi_pct, axis=1)
    work["review_roi_text"] = work["review_roi_pct"].map(_format_review_percent)
    work["review_profit_signal_text"] = work.apply(_feeder_review_profit_signal_text, axis=1)
    if pack_type == "passes":
        work["why_label"] = "Why it passed"
        work["why_text"] = work["why_data_summary"].map(_normalize_text)
        missing_why = work["why_text"].eq("")
        if missing_why.any():
            work.loc[missing_why, "why_text"] = work.loc[missing_why, "pass_reason_summary"].map(_humanize_pass_reason_summary)
        work["helper_label"] = "What to watch"
        work["helper_text"] = work["watch_data_summary"].map(_normalize_text)
        missing_helper = work["helper_text"].eq("")
        if missing_helper.any():
            work.loc[missing_helper, "helper_text"] = work.loc[missing_helper, "commercial_note"].map(_humanize_commercial_note)
    else:
        fail_codes = work["why_data_summary"].map(_normalize_text)
        missing_fail = fail_codes.eq("")
        if missing_fail.any():
            fail_codes.loc[missing_fail] = work.loc[missing_fail, "screening_fail_code"].map(_humanize_fail_reason)
        recovery = work["watch_data_summary"].map(_normalize_text)
        missing_recovery = recovery.eq("")
        if missing_recovery.any():
            recovery.loc[missing_recovery] = work.loc[missing_recovery, "recovery_hint"].map(_humanize_recovery_hint)
        work["why_label"] = "Why it nearly failed"
        work["why_text"] = fail_codes
        work["helper_label"] = "Why it is still worth a look"
        work["helper_text"] = recovery
    work["f032_operator_check_note"] = work.apply(_f032_operator_check_note, axis=1)
    work["ai_compare_watch_note"] = work.apply(_ai_compare_watch_note, axis=1)
    ai_note_mask = work["ai_compare_watch_note"].map(_normalize_text).ne("")
    if ai_note_mask.any():
        work.loc[ai_note_mask, "helper_label"] = "What to watch"
        work.loc[ai_note_mask, "helper_text"] = work.loc[ai_note_mask].apply(
            lambda row: _append_summary_note(row.get("helper_text", ""), row.get("ai_compare_watch_note", "")),
            axis=1,
        )
    return work


def load_feeder_review_events_df(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    return _read_f_contract_df(root_path, "feeder_review_events")


def _latest_feeder_review_event_by_identity(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df.empty:
        return pd.DataFrame(columns=_f_contract_columns("feeder_review_events"))
    work = events_df.copy()
    for col in FEEDER_REVIEW_IDENTITY_COLUMNS:
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].map(_normalize_text)
    work["_event_sort"] = pd.to_datetime(work.get("event_utc", ""), errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "event_id"], ascending=[False, False], kind="stable")
    work = work.drop_duplicates(subset=list(FEEDER_REVIEW_IDENTITY_COLUMNS), keep="first")
    return work.drop(columns=["_event_sort"], errors="ignore").reset_index(drop=True)


def _latest_feeder_review_event_by_product(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df.empty:
        return pd.DataFrame(columns=_f_contract_columns("feeder_review_events"))
    work = events_df.copy()
    for col in FEEDER_REVIEW_PRODUCT_IDENTITY_COLUMNS:
        if col not in work.columns:
            work[col] = ""
        work[col] = work[col].map(_normalize_text)
    work = work[work["asin_padded"].map(_normalize_text).ne("")].copy()
    if work.empty:
        return pd.DataFrame(columns=_f_contract_columns("feeder_review_events"))
    work["_event_sort"] = pd.to_datetime(work.get("event_utc", ""), errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "event_id"], ascending=[False, False], kind="stable")
    work = work.drop_duplicates(subset=list(FEEDER_REVIEW_PRODUCT_IDENTITY_COLUMNS), keep="first")
    return work.drop(columns=["_event_sort"], errors="ignore").reset_index(drop=True)


def _merge_latest_review_columns(source_df: pd.DataFrame, latest_events_df: pd.DataFrame) -> pd.DataFrame:
    merged = source_df.copy()
    for col in FEEDER_REVIEW_IDENTITY_COLUMNS:
        if col not in merged.columns:
            merged[col] = ""
        merged[col] = merged[col].map(_normalize_text)
    if "asin_padded" not in merged.columns:
        asin_source = merged["asin"] if "asin" in merged.columns else pd.Series([""] * len(merged.index), index=merged.index)
        merged["asin_padded"] = asin_source.map(_pad_asin_to_10)
    else:
        merged["asin_padded"] = merged["asin_padded"].map(_normalize_text)
    if latest_events_df.empty:
        merged["latest_review_decision"] = ""
        merged["latest_review_note"] = ""
        merged["latest_review_reason_code"] = ""
        merged["latest_review_reason_label"] = ""
        merged["latest_review_utc"] = ""
        return merged
    joined = merged.merge(
        latest_events_df[
            [
                *FEEDER_REVIEW_IDENTITY_COLUMNS,
                "review_decision",
                "review_note",
                "review_reason_code",
                "review_reason_label",
                "event_utc",
            ]
        ].rename(
            columns={
                "review_decision": "latest_review_decision",
                "review_note": "latest_review_note",
                "review_reason_code": "latest_review_reason_code",
                "review_reason_label": "latest_review_reason_label",
                "event_utc": "latest_review_utc",
            }
        ),
        on=list(FEEDER_REVIEW_IDENTITY_COLUMNS),
        how="left",
    )
    joined = joined.fillna("")
    product_events = _latest_feeder_review_event_by_product(latest_events_df)
    if product_events.empty:
        return joined
    product_cols = [
        *FEEDER_REVIEW_PRODUCT_IDENTITY_COLUMNS,
        "review_decision",
        "review_note",
        "review_reason_code",
        "review_reason_label",
        "event_utc",
    ]
    product_join = product_events[product_cols].rename(
        columns={
            "review_decision": "_product_latest_review_decision",
            "review_note": "_product_latest_review_note",
            "review_reason_code": "_product_latest_review_reason_code",
            "review_reason_label": "_product_latest_review_reason_label",
            "event_utc": "_product_latest_review_utc",
        }
    )
    joined = joined.merge(product_join, on=list(FEEDER_REVIEW_PRODUCT_IDENTITY_COLUMNS), how="left").fillna("")
    use_product = joined["latest_review_decision"].map(_normalize_text).eq("") & joined[
        "_product_latest_review_decision"
    ].map(_normalize_text).ne("")
    if use_product.any():
        copy_pairs = (
            ("latest_review_decision", "_product_latest_review_decision"),
            ("latest_review_note", "_product_latest_review_note"),
            ("latest_review_reason_code", "_product_latest_review_reason_code"),
            ("latest_review_reason_label", "_product_latest_review_reason_label"),
            ("latest_review_utc", "_product_latest_review_utc"),
        )
        for target, source in copy_pairs:
            joined.loc[use_product, target] = joined.loc[use_product, source]
    return joined.drop(
        columns=[
            "_product_latest_review_decision",
            "_product_latest_review_note",
            "_product_latest_review_reason_code",
            "_product_latest_review_reason_label",
            "_product_latest_review_utc",
        ],
        errors="ignore",
    )


def build_feeder_review_window_df(
    pack_type: str,
    *,
    root: Path | None = None,
    review_pack_snapshot: str = "latest",
    lane_filter: str = "",
    supplier_filter: str = "All suppliers",
    review_batch_id: str = "Auto next 10",
    search_text: str = "",
    page_size: int = FEEDER_REVIEW_PAGE_SIZE,
) -> tuple[pd.DataFrame, dict[str, object]]:
    source_df = load_feeder_review_source_df(pack_type, root=root, review_pack_snapshot=review_pack_snapshot)
    source_df = _apply_feeder_review_lane_filter(source_df, pack_type=pack_type, lane_filter=lane_filter)
    latest_events_df = _latest_feeder_review_event_by_identity(load_feeder_review_events_df(root=root))

    undecided_count_before = int(len(source_df.index))
    source_df = _merge_latest_review_columns(source_df, latest_events_df)

    if source_df.empty:
        meta = {
            "available_rows": 0,
            "undecided_rows": 0,
            "decided_rows": 0,
            "visible_rows": 0,
            "review_batch_options": [],
            "supplier_options": [],
        }
        return source_df, meta

    undecided_source_df = source_df[source_df["latest_review_decision"].map(_normalize_text).eq("")].copy()
    supplier_pool_df = undecided_source_df if not undecided_source_df.empty else source_df
    supplier_options = ["All suppliers", *sorted({v for v in supplier_pool_df["active_supplier_id"].map(_normalize_text) if v})]
    review_batch_options = ["Auto next 10", *sorted({v for v in supplier_pool_df["review_batch_id"].map(_normalize_text) if v})]

    filtered_df = source_df.copy()
    if supplier_filter != "All suppliers":
        filtered_df = filtered_df[
            filtered_df["active_supplier_id"].map(_normalize_text).eq(_normalize_text(supplier_filter))
        ].copy()
    if review_batch_id != "Auto next 10":
        filtered_df = filtered_df[
            filtered_df["review_batch_id"].map(_normalize_text).eq(_normalize_text(review_batch_id))
        ].copy()

    query = _normalize_text(search_text).lower()
    if query:
        filtered_df = filtered_df[
            filtered_df["title"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["supplier_sku"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["asin"].astype(str).str.lower().str.contains(query, na=False)
        ].copy()

    available_rows = int(len(filtered_df.index))
    undecided_df = filtered_df[filtered_df["latest_review_decision"].map(_normalize_text).eq("")].copy()
    undecided_df["_source_row_num"] = pd.to_numeric(undecided_df.get("_source_row_num", ""), errors="coerce")
    undecided_df["_priority_num"] = undecided_df["review_priority_score"].map(_to_float)
    undecided_df = undecided_df.sort_values(
        by=["_source_row_num", "_priority_num", "review_batch_id", "candidate_id"],
        ascending=[True, False, True, True],
        kind="stable",
    )
    undecided_rows = int(len(undecided_df.index))
    decided_rows = int(available_rows - undecided_rows)

    visible_df = undecided_df.head(page_size).copy()
    visible_df = visible_df.drop(columns=["_source_row_num", "_priority_num"], errors="ignore").reset_index(drop=True)

    meta = {
        "available_rows": available_rows,
        "undecided_rows": undecided_rows,
        "decided_rows": decided_rows,
        "visible_rows": int(len(visible_df.index)),
        "review_batch_options": review_batch_options,
        "supplier_options": supplier_options,
        "all_rows_before_decisions": undecided_count_before,
    }
    return visible_df, meta


def build_feeder_review_sent_df(
    pack_type: str,
    *,
    root: Path | None = None,
    review_pack_snapshot: str = "latest",
    lane_filter: str = "",
    supplier_filter: str = "All suppliers",
    review_batch_id: str = "Auto next 10",
    search_text: str = "",
    page_size: int = FEEDER_REVIEW_PAGE_SIZE,
) -> pd.DataFrame:
    source_df = load_feeder_review_source_df(pack_type, root=root, review_pack_snapshot=review_pack_snapshot)
    source_df = _apply_feeder_review_lane_filter(source_df, pack_type=pack_type, lane_filter=lane_filter)
    latest_events_df = _latest_feeder_review_event_by_identity(load_feeder_review_events_df(root=root))
    source_df = _merge_latest_review_columns(source_df, latest_events_df)
    if source_df.empty:
        return source_df

    filtered_df = source_df.copy()
    if supplier_filter != "All suppliers":
        filtered_df = filtered_df[
            filtered_df["active_supplier_id"].map(_normalize_text).eq(_normalize_text(supplier_filter))
        ].copy()
    if review_batch_id != "Auto next 10":
        filtered_df = filtered_df[
            filtered_df["review_batch_id"].map(_normalize_text).eq(_normalize_text(review_batch_id))
        ].copy()
    query = _normalize_text(search_text).lower()
    if query:
        filtered_df = filtered_df[
            filtered_df["title"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["supplier_sku"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["asin"].astype(str).str.lower().str.contains(query, na=False)
        ].copy()

    decided_df = filtered_df[
        filtered_df["latest_review_decision"].map(lambda v: _normalize_text(v).lower() in FEEDER_REVIEW_DECISIONS)
    ].copy()
    if decided_df.empty:
        return decided_df
    decided_df["_decision_sort"] = pd.to_datetime(decided_df.get("latest_review_utc", ""), errors="coerce", utc=True)
    decided_df["_priority_num"] = decided_df["review_priority_score"].map(_to_float)
    decided_df = decided_df.sort_values(
        by=["_decision_sort", "_priority_num", "candidate_id"],
        ascending=[False, False, True],
        kind="stable",
    )
    return decided_df.drop(columns=["_decision_sort", "_priority_num"], errors="ignore").head(page_size).reset_index(drop=True)


def build_product_listing_profile_review_df(
    root: Path | None = None,
    *,
    page_size: int = 50,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    latest_review = _latest_feeder_review_event_by_identity(load_feeder_review_events_df(root=root_path))
    profile_df = _read_f_contract_df(root_path, "amazon_listing_profile_events")
    latest_profile = _latest_feeder_review_event_by_identity(profile_df) if not profile_df.empty else pd.DataFrame()
    completed_keys: set[tuple[str, str, str, str]] = set()
    if not latest_profile.empty:
        for _, row in latest_profile.iterrows():
            row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
            if row_dict.get("profile_status", "").lower() != "complete":
                continue
            completed_keys.add(
                (
                    row_dict.get("active_supplier_id", ""),
                    row_dict.get("active_run_id", ""),
                    row_dict.get("review_pack_type", ""),
                    row_dict.get("candidate_id", ""),
                )
            )

    rows: list[dict[str, str]] = []
    for _, event in latest_review.iterrows():
        row = {key: _normalize_text(value) for key, value in event.to_dict().items()}
        if row.get("review_decision", "").lower() != "pass":
            continue
        key = (
            row.get("active_supplier_id", ""),
            row.get("active_run_id", ""),
            row.get("review_pack_type", ""),
            row.get("candidate_id", ""),
        )
        if key in completed_keys:
            continue
        rows.append(
            {
                "active_supplier_id": key[0],
                "active_run_id": key[1],
                "review_pack_type": key[2],
                "review_batch_id": row.get("review_batch_id", ""),
                "candidate_id": key[3],
                "supplier_sku": row.get("supplier_sku", ""),
                "asin": row.get("asin_padded", "") or row.get("asin_raw", ""),
                "title": row.get("title", ""),
                "brand": row.get("brand", ""),
                "main_rank": row.get("main_rank", ""),
                "review_priority_score": row.get("review_priority_score", ""),
                "latest_review_utc": row.get("event_utc", ""),
                "profile_status": "profile_review_required",
            }
        )
    if not rows:
        return pd.DataFrame(columns=[
            "active_supplier_id",
            "active_run_id",
            "review_pack_type",
            "review_batch_id",
            "candidate_id",
            "supplier_sku",
            "asin",
            "title",
            "brand",
            "main_rank",
            "review_priority_score",
            "latest_review_utc",
            "profile_status",
        ])
    out = pd.DataFrame(rows)
    out["_sort"] = pd.to_datetime(out["latest_review_utc"], errors="coerce", utc=True)
    out = out.sort_values(by=["_sort", "candidate_id"], ascending=[False, True], kind="stable")
    return out.drop(columns=["_sort"], errors="ignore").head(max(int(page_size), 0)).reset_index(drop=True)


def submit_feeder_review_batch(
    *,
    root: Path | None = None,
    reviewed_rows: list[dict[str, object]],
    actor: str = "operator_ui",
    source_reference: str = "o_ui_feeder_review",
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    out_rows: list[dict[str, str]] = []
    skipped_rows: list[str] = []

    for row in reviewed_rows:
        candidate_id = _normalize_text(row.get("candidate_id", ""))
        review_decision = _normalize_feeder_review_decision(row.get("review_decision", ""))
        if candidate_id == "" or review_decision not in FEEDER_REVIEW_DECISIONS:
            skipped_rows.append(candidate_id or "(missing_candidate_id)")
            continue
        country_of_origin = _normalize_country_of_origin(row.get("country_of_origin", ""))
        product_tax_code = _normalize_text(row.get("product_tax_code", ""))
        currency_code = _normalize_currency_code(row.get("currency_code", ""))
        price_includes_tax = _normalize_price_includes_tax(row.get("price_includes_tax", ""))
        starting_price_gbp = _normalize_positive_money(row.get("starting_price_gbp", ""))
        review_reason_code = _normalize_feeder_review_reason_code(row.get("review_reason_code", ""))
        out_row = {
            "event_utc": _utc_now_iso(),
            "event_id": f"o-ui-f-review-{uuid.uuid4().hex[:12]}",
            "active_supplier_id": _normalize_text(row.get("active_supplier_id", "")),
            "active_run_id": _normalize_text(row.get("active_run_id", "")),
            "review_pack_type": _normalize_text(row.get("review_pack_type", "")),
            "review_batch_id": _normalize_text(row.get("review_batch_id", "")),
            "candidate_id": candidate_id,
            "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
            "asin_raw": _normalize_text(row.get("asin", "")),
            "asin_padded": _pad_asin_to_10(row.get("asin", "")),
            "amazon_dp_url": _amazon_dp_url(row.get("asin", "")),
            "review_decision": review_decision,
            "review_note": _normalize_text(row.get("review_note", "")),
            "actor": _normalize_text(actor),
            "source_reference": _normalize_text(source_reference) or "o_ui_feeder_review",
            "title": _normalize_text(row.get("title", "")),
            "brand": _normalize_text(row.get("brand", "")),
            "main_rank": _normalize_text(row.get("main_rank", "")),
            "review_priority_score": _normalize_text(row.get("review_priority_score", "")),
            "review_reason_code": review_reason_code,
            "review_reason_label": _feeder_review_reason_label(review_reason_code),
            "country_of_origin": country_of_origin,
            "product_tax_code": product_tax_code,
            "currency_code": currency_code,
            "price_includes_tax": price_includes_tax,
            "starting_price_gbp": starting_price_gbp,
            "f032_decision_id": _normalize_text(row.get("f032_decision_id", "")),
            "f032_action": _normalize_text(row.get("f032_action", "")),
            "f032_decision_bucket": _normalize_text(row.get("f032_decision_bucket", "")),
            "f032_fail_category": _normalize_text(row.get("f032_fail_category", "")),
            "f032_confidence": _normalize_text(row.get("f032_confidence", "")),
            "f032_reason": _normalize_text(row.get("f032_reason", "")),
            "f032_operator_check_note": _normalize_text(row.get("f032_operator_check_note", "")),
            "codex_ai_action": _normalize_text(row.get("codex_ai_action", "")),
            "codex_ai_decision_bucket": _normalize_text(row.get("codex_ai_decision_bucket", "")),
            "codex_ai_reason": _normalize_text(row.get("codex_ai_reason", "")),
            "codex_ai_evidence": _normalize_text(row.get("codex_ai_evidence", "")),
        }
        out_rows.append(out_row)

    normalized_rows = _append_f_contract_rows(root_path, "feeder_review_events", out_rows)
    applied_event_ids = [_normalize_text(row.get("event_id", "")) for row in normalized_rows]
    applied_candidate_ids = [_normalize_text(row.get("candidate_id", "")) for row in normalized_rows]

    return {
        "events_applied": len(applied_event_ids),
        "applied_event_ids": applied_event_ids,
        "applied_candidate_ids": applied_candidate_ids,
        "skipped_rows": skipped_rows,
        "blocked_rows": skipped_rows,
    }


def submit_amazon_listing_profile_batch(
    *,
    root: Path | None = None,
    profile_rows: list[dict[str, object]],
    actor: str = "operator_ui",
    source_reference: str = "o_ui_product_listing_profile_review",
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    out_rows: list[dict[str, str]] = []
    skipped_rows: list[str] = []

    for row in profile_rows:
        candidate_id = _normalize_text(row.get("candidate_id", ""))
        if candidate_id == "":
            skipped_rows.append("(missing_candidate_id)")
            continue
        country_of_origin = _normalize_country_of_origin(row.get("country_of_origin", ""))
        purchase_pack_size = _normalize_positive_int_text(row.get("purchase_pack_size", ""))
        sold_pack_size = _normalize_positive_int_text(row.get("sold_pack_size", ""))
        supplier_case_qty = _normalize_positive_int_text(row.get("supplier_case_qty", "")) or purchase_pack_size
        supplier_case_multiple = _normalize_truthy_flag(row.get("supplier_case_multiple", ""))
        valid_order_step = _normalize_positive_int_text(row.get("valid_order_step", "")) or supplier_case_qty
        moq = _normalize_positive_int_text(row.get("moq", "")) or "1"
        target_margin = _normalize_non_negative_money(row.get("target_margin", ""))
        vat_confirmed_flag = _normalize_truthy_flag(row.get("vat_confirmed_flag", ""))
        vat_source_value = _normalize_non_negative_money(row.get("vat_source_value", ""))
        product_tax_code = _normalize_text(row.get("product_tax_code", "")) or DEFAULT_FEEDER_REVIEW_PRODUCT_TAX_CODE
        raw_currency = _normalize_text(row.get("currency_code", ""))
        currency_code = _normalize_currency_code(raw_currency)
        if currency_code == "" and raw_currency == "":
            currency_code = DEFAULT_FEEDER_REVIEW_CURRENCY_CODE
        price_includes_tax = _normalize_price_includes_tax(row.get("price_includes_tax", ""))
        starting_price_gbp = _normalize_positive_money(row.get("starting_price_gbp", ""))
        missing: list[str] = []
        if country_of_origin == "":
            missing.append("country_of_origin")
        if purchase_pack_size == "":
            missing.append("purchase_pack_size")
        if sold_pack_size == "":
            missing.append("sold_pack_size")
        if supplier_case_qty == "":
            missing.append("supplier_case_qty")
        if valid_order_step == "":
            missing.append("valid_order_step")
        if moq == "":
            missing.append("moq")
        if vat_source_value == "":
            missing.append("vat_source_value")
        if vat_confirmed_flag != "1":
            missing.append("vat_confirmed_flag")
        if product_tax_code == "":
            missing.append("product_tax_code")
        if currency_code == "":
            missing.append("currency_code")
        if price_includes_tax == "":
            missing.append("price_includes_tax")
        if starting_price_gbp == "":
            missing.append("starting_price_gbp")
        if missing:
            skipped_rows.append(f"{candidate_id}:missing_listing_profile:{','.join(missing)}")
            continue

        asin_raw = _normalize_text(row.get("asin", "")) or _normalize_text(row.get("asin_raw", ""))
        out_rows.append(
            {
                "event_utc": _utc_now_iso(),
                "event_id": f"o-ui-listing-profile-{uuid.uuid4().hex[:12]}",
                "active_supplier_id": _normalize_text(row.get("active_supplier_id", "")),
                "active_run_id": _normalize_text(row.get("active_run_id", "")),
                "review_pack_type": _normalize_text(row.get("review_pack_type", "")) or "passes",
                "review_batch_id": _normalize_text(row.get("review_batch_id", "")),
                "candidate_id": candidate_id,
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "asin_raw": asin_raw,
                "asin_padded": _pad_asin_to_10(asin_raw),
                "amazon_dp_url": _amazon_dp_url(asin_raw),
                "profile_status": "complete",
                "country_of_origin": country_of_origin,
                "purchase_pack_size": purchase_pack_size,
                "sold_pack_size": sold_pack_size,
                "supplier_case_qty": supplier_case_qty,
                "supplier_case_multiple": supplier_case_multiple,
                "valid_order_step": valid_order_step,
                "moq": moq,
                "target_margin": target_margin,
                "vat_confirmed_flag": vat_confirmed_flag,
                "product_tax_code": product_tax_code,
                "currency_code": currency_code,
                "price_includes_tax": price_includes_tax,
                "starting_price_gbp": starting_price_gbp,
                "actor": _normalize_text(actor),
                "source_reference": _normalize_text(source_reference) or "o_ui_product_listing_profile_review",
                "title": _normalize_text(row.get("title", "")),
                "brand": _normalize_text(row.get("brand", "")),
                "main_rank": _normalize_text(row.get("main_rank", "")),
                "review_priority_score": _normalize_text(row.get("review_priority_score", "")),
                "vat_source_value": vat_source_value,
                "starting_quantity": _normalize_positive_int_text(row.get("starting_quantity", "")),
                "condition_type": _normalize_text(row.get("condition_type", "")),
                "profile_note": _normalize_text(row.get("profile_note", "")),
            }
        )

    normalized_rows = _append_f_contract_rows(root_path, "amazon_listing_profile_events", out_rows)
    return {
        "events_applied": len(normalized_rows),
        "applied_event_ids": [_normalize_text(row.get("event_id", "")) for row in normalized_rows],
        "applied_candidate_ids": [_normalize_text(row.get("candidate_id", "")) for row in normalized_rows],
        "skipped_rows": skipped_rows,
        "blocked_rows": skipped_rows,
    }


BRAND_APPROVAL_DECISIONS = {
    "Fail now": "fail_now",
    "Park": "park",
    "Try Seller Central": "try_seller_central",
    "Plan invoice": "invoice_planned",
    "Invoice uploaded": "invoice_uploaded",
    "Recheck approval": "approved_recheck",
}


def build_brand_approval_queue_display_df(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    queue = _read_f_contract_df(root_path, "brand_approval_queue_live")
    if queue.empty:
        return pd.DataFrame(
            columns=[
                "queue_id",
                "draft_id",
                "candidate_id",
                "expected_seller_sku",
                "asin",
                "marketplace_id",
                "brand",
                "amazon_title",
                "approval_status",
                "reason_message",
                "approval_link",
                "invoice_required_quantity",
                "invoice_unit_cost_gbp",
                "invoice_total_risk_gbp",
                "operator_decision",
                "cooldown_until_utc",
                "recheck_trigger",
            ]
        )
    out = queue.copy()
    for column in out.columns:
        out[column] = out[column].map(_normalize_text)
    out["_sort"] = pd.to_datetime(out.get("observed_utc", ""), errors="coerce", utc=True)
    out = out.sort_values(by=["_sort", "brand", "asin"], ascending=[False, True, True], kind="stable")
    return out.drop(columns=["_sort"], errors="ignore").reset_index(drop=True)


def submit_brand_approval_decision_batch(
    *,
    root: Path | None = None,
    decision_rows: list[dict[str, object]],
    actor: str = "operator_ui",
    source_reference: str = "o_ui_brand_approval_queue",
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    normalized_rows: list[dict[str, object]] = []
    skipped_rows: list[str] = []
    for row in decision_rows:
        draft_id = _normalize_text(row.get("draft_id", ""))
        queue_id = _normalize_text(row.get("queue_id", ""))
        decision = _normalize_text(row.get("operator_decision", "")).lower()
        if decision not in BRAND_APPROVAL_DECISIONS.values():
            skipped_rows.append(f"{draft_id or queue_id}:invalid_decision")
            continue
        normalized_rows.append(
            {
                **row,
                "queue_id": queue_id,
                "draft_id": draft_id,
                "candidate_id": _normalize_text(row.get("candidate_id", "")),
                "expected_seller_sku": _normalize_text(row.get("expected_seller_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "marketplace_id": _normalize_text(row.get("marketplace_id", "")),
                "brand": _normalize_text(row.get("brand", "")),
                "operator_decision": decision,
                "decision_reason": _normalize_text(row.get("decision_reason", "")),
                "invoice_required_quantity": _normalize_positive_int_text(row.get("invoice_required_quantity", "")),
                "invoice_unit_cost_gbp": _normalize_positive_money(row.get("invoice_unit_cost_gbp", "")),
                "invoice_total_risk_gbp": _normalize_positive_money(row.get("invoice_total_risk_gbp", "")),
                "approval_application_status": _normalize_text(row.get("approval_application_status", "")),
                "invoice_artifact_reference": _normalize_text(row.get("invoice_artifact_reference", "")),
            }
        )
    if not normalized_rows:
        return {"events_applied": 0, "skipped_rows": skipped_rows, "applied_event_ids": []}
    result = record_brand_approval_decisions(
        root=root_path,
        decision_rows=normalized_rows,
        actor=actor,
        source_reference=source_reference,
    )
    return {
        "events_applied": result.get("events_applied", 0),
        "skipped_rows": [*skipped_rows, *list(result.get("skipped_rows", []))],
        "applied_event_ids": list(result.get("applied_event_ids", [])),
    }


def submit_feeder_review_reopen_batch(
    *,
    root: Path | None = None,
    rows_to_reopen: list[dict[str, object]],
    actor: str = "operator_ui",
    source_reference: str = "o_ui_feeder_review_reopen",
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    out_rows: list[dict[str, str]] = []
    for row in rows_to_reopen:
        candidate_id = _normalize_text(row.get("candidate_id", ""))
        if candidate_id == "":
            continue
        asin_raw = _normalize_text(row.get("asin", "")) or _normalize_text(row.get("asin_raw", ""))
        out_rows.append(
            {
                "event_utc": _utc_now_iso(),
                "event_id": f"o-ui-f-review-{uuid.uuid4().hex[:12]}",
                "active_supplier_id": _normalize_text(row.get("active_supplier_id", "")),
                "active_run_id": _normalize_text(row.get("active_run_id", "")),
                "review_pack_type": _normalize_text(row.get("review_pack_type", "")),
                "review_batch_id": _normalize_text(row.get("review_batch_id", "")),
                "candidate_id": candidate_id,
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "asin_raw": asin_raw,
                "asin_padded": _pad_asin_to_10(asin_raw),
                "amazon_dp_url": _amazon_dp_url(asin_raw),
                "review_decision": "",
                "review_note": _normalize_text(row.get("review_note", "")),
                "actor": _normalize_text(actor),
                "source_reference": _normalize_text(source_reference) or "o_ui_feeder_review_reopen",
                "title": _normalize_text(row.get("title", "")),
                "brand": _normalize_text(row.get("brand", "")),
                "main_rank": _normalize_text(row.get("main_rank", "")),
                "review_priority_score": _normalize_text(row.get("review_priority_score", "")),
            }
        )
    normalized_rows = _append_f_contract_rows(root_path, "feeder_review_events", out_rows)
    return {
        "events_applied": len(normalized_rows),
        "applied_candidate_ids": [_normalize_text(row.get("candidate_id", "")) for row in normalized_rows],
    }


def get_submission_targets(root: Path | None = None) -> dict[str, Path]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    return {
        "decision_events": root_path / get_o_output_contract("restock_decision_events").rel_path,
        "receiving_events": root_path / get_o_output_contract("receiving_events_inbox").rel_path,
        "send_handoff_events": root_path / get_o_output_contract("send_to_amazon_handoff_events").rel_path,
        "feeder_review_events": root_path / get_f_output_contract("feeder_review_events").rel_path,
    }


def load_operator_datasets(root: Path | None = None) -> dict[str, pd.DataFrame]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    names = (
        "restock_source_view",
        "restock_decision_events",
        "restock_review_queue",
        "restock_recommendations_live",
        "restock_profit_checks_live",
        "restock_profit_check_health",
        "restock_session_review_live",
        "restock_session_supplier_summary_live",
        "restock_session_reason_codes",
        "restock_session_health",
        "restock_session_draft_decision_events",
        "restock_session_supplier_proof_events",
        "restock_session_pack_moq_proof_events",
        "restock_session_supplier_batch_lines_live",
        "restock_session_supplier_batch_summary_live",
        "restock_session_supplier_batch_health",
        "restock_supplier_file_source_index_live",
        "restock_supplier_file_source_index_health",
        "restock_supplier_file_presence_probe_live",
        "restock_supplier_file_presence_probe_health",
        "restock_purchase_approval_preview_lines_live",
        "restock_purchase_approval_preview_summary_live",
        "restock_purchase_approval_preview_health",
        "restock_purchase_approval_decision_events",
        "restock_purchase_approval_guardrails_live",
        "restock_purchase_approval_guardrails_health",
        "restock_po_draft_readiness_preview_lines_live",
        "restock_po_draft_readiness_preview_summary_live",
        "restock_po_draft_readiness_preview_health",
        "restock_po_line_design_preview_lines_live",
        "restock_po_line_design_preview_summary_live",
        "restock_po_line_design_preview_health",
        "restock_po_draft_packet_review_lines_live",
        "restock_po_draft_packet_review_summary_live",
        "restock_po_draft_packet_review_health",
        "restock_po_draft_hold_review_lines_live",
        "restock_po_draft_hold_review_summary_live",
        "restock_po_draft_hold_review_health",
        "restock_po_draft_file_shape_preview_lines_live",
        "restock_po_draft_file_shape_preview_summary_live",
        "restock_po_draft_file_shape_preview_health",
        "restock_po_preview_construction_summary_live",
        "restock_po_preview_construction_summary_health",
        "restock_po_draft_review_control_events",
        "restock_po_draft_review_controls_live",
        "restock_po_draft_review_controls_health",
        "restock_po_draft_export_preview_lines_live",
        "restock_po_draft_export_preview_summary_live",
        "restock_po_draft_export_preview_health",
        "restock_po_draft_export_gate_events",
        "restock_po_draft_export_gate_live",
        "restock_po_draft_export_gate_health",
        "supplier_buy_cost_truth",
        "supplier_paid_cost_profiles_live",
        "supplier_price_list_change_log_live",
        "legacy_purchase_list_bridge",
        "product_db_operator_view",
        "product_db_edit_events",
        "product_db_edit_holds",
        "restock_decisions_log",
        "purchase_orders_live",
        "purchase_order_lines_live",
        "purchase_order_draft_holds",
        "ordered_stock_state",
        "receiving_events",
        "receiving_event_holds",
        "send_to_amazon_queue",
        "send_to_amazon_handoff_log",
        "send_to_amazon_handoff_holds",
    )
    datasets = {name: _read_contract_df(root_path, name) for name in names}
    f_names = (
        "amazon_listing_intake_live",
        "amazon_listing_sku_reservations_live",
        "amazon_listing_drafts_live",
        "amazon_listing_draft_events",
        "amazon_listing_preview_events",
        "amazon_listing_profile_events",
        "amazon_listing_preview_issues_live",
        "amazon_listing_restrictions_live",
        "brand_approval_queue_live",
        "brand_approval_decision_events",
        "amazon_listing_holds_live",
        "amazon_listing_health",
    )
    datasets.update({name: _read_f_contract_df(root_path, name) for name in f_names})
    return datasets


def build_amazon_listing_draft_display_df(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    drafts_df = datasets.get("amazon_listing_drafts_live", pd.DataFrame()).copy()
    holds_df = datasets.get("amazon_listing_holds_live", pd.DataFrame()).copy()
    if drafts_df.empty:
        return pd.DataFrame(columns=AMAZON_LISTING_DRAFT_DISPLAY_COLUMNS)

    for col in AMAZON_LISTING_DRAFT_DISPLAY_COLUMNS:
        if col not in drafts_df.columns:
            drafts_df[col] = ""
    drafts_df["hold_reason"] = ""
    drafts_df["hold_note"] = ""

    if not holds_df.empty:
        holds = holds_df.copy()
        for col in ("draft_id", "intake_id", "candidate_id", "expected_seller_sku", "hold_reason", "hold_note"):
            if col not in holds.columns:
                holds[col] = ""
            holds[col] = holds[col].map(_normalize_text)
        hold_by_draft: dict[str, pd.Series] = {}
        hold_by_intake: dict[str, pd.Series] = {}
        hold_by_candidate_sku: dict[tuple[str, str], pd.Series] = {}
        for _, hold in holds.iterrows():
            draft_id = _normalize_text(hold.get("draft_id", ""))
            intake_id = _normalize_text(hold.get("intake_id", ""))
            candidate_id = _normalize_text(hold.get("candidate_id", "")).upper()
            sku = _normalize_text(hold.get("expected_seller_sku", "")).upper()
            if draft_id and draft_id not in hold_by_draft:
                hold_by_draft[draft_id] = hold
            if intake_id and intake_id not in hold_by_intake:
                hold_by_intake[intake_id] = hold
            if candidate_id and sku and (candidate_id, sku) not in hold_by_candidate_sku:
                hold_by_candidate_sku[(candidate_id, sku)] = hold

        for idx, draft in drafts_df.iterrows():
            hold = hold_by_draft.get(_normalize_text(draft.get("draft_id", "")))
            if hold is None:
                hold = hold_by_intake.get(_normalize_text(draft.get("source_intake_id", "")))
            if hold is None:
                key = (
                    _normalize_text(draft.get("candidate_id", "")).upper(),
                    _normalize_text(draft.get("expected_seller_sku", "")).upper(),
                )
                hold = hold_by_candidate_sku.get(key)
            if hold is not None:
                drafts_df.at[idx, "hold_reason"] = _normalize_text(hold.get("hold_reason", ""))
                drafts_df.at[idx, "hold_note"] = _normalize_text(hold.get("hold_note", ""))

    drafts_df["_status_sort"] = drafts_df.get("draft_status", "").map(
        lambda value: {
            "ready_for_amazon_preview": 0,
            "ready_for_live_submit": 1,
            "ready_for_listing_approval": 2,
            "blocked_amazon_preview": 3,
            "blocked_missing_local_data": 4,
        }.get(_normalize_text(value), 9)
    )
    drafts_df = drafts_df.sort_values(
        by=["_status_sort", "supplier_name", "candidate_id", "asin"],
        ascending=[True, True, True, True],
        kind="stable",
    )
    return drafts_df[AMAZON_LISTING_DRAFT_DISPLAY_COLUMNS].reset_index(drop=True)


def submit_amazon_listing_draft_approval(
    *,
    root: Path | None = None,
    draft_id: str,
    actor: str = "operator_ui",
    source_reference: str = "o_ui_amazon_listing_draft_lane",
) -> tuple[bool, str, dict[str, str]]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    drafts_df = _read_f_contract_df(root_path, "amazon_listing_drafts_live")
    draft_key = _normalize_text(draft_id)
    if draft_key == "":
        return False, "missing_draft_id", {}
    if drafts_df.empty or "draft_id" not in drafts_df.columns:
        return False, "draft_not_found", {}
    mask = drafts_df["draft_id"].map(_normalize_text).eq(draft_key)
    if not mask.any():
        return False, "draft_not_found", {}

    row_index = drafts_df[mask].index[0]
    row = drafts_df.loc[row_index].to_dict()
    block_reason = _normalize_text(row.get("block_reason", ""))
    draft_status = _normalize_text(row.get("draft_status", ""))
    if block_reason != "" or draft_status == "blocked_missing_local_data":
        return False, "draft_blocked", {key: _normalize_text(value) for key, value in row.items()}

    now_utc = _utc_now_iso()
    drafts_df.loc[row_index, "listing_approval_status"] = "approved_for_preview"
    drafts_df.loc[row_index, "draft_status"] = "ready_for_amazon_preview"
    drafts_df.loc[row_index, "updated_at_utc"] = now_utc
    write_f_contract_df(root_path, "amazon_listing_drafts_live", drafts_df)

    updated = {key: _normalize_text(value) for key, value in drafts_df.loc[row_index].to_dict().items()}
    event = {
        "event_utc": now_utc,
        "event_id": f"o-ui-amazon-draft-{uuid.uuid4().hex[:12]}",
        "draft_id": draft_key,
        "event_type": "listing_draft_approved",
        "draft_status": "ready_for_amazon_preview",
        "candidate_id": updated.get("candidate_id", ""),
        "expected_seller_sku": updated.get("expected_seller_sku", ""),
        "asin": updated.get("asin", ""),
        "marketplace_id": updated.get("marketplace_id", ""),
        "notes": f"approved_by={_normalize_text(actor)}",
        "source_reference": _normalize_text(source_reference),
    }
    existing_events = _read_f_contract_df(root_path, "amazon_listing_draft_events")
    write_f_contract_df(
        root_path,
        "amazon_listing_draft_events",
        pd.concat([existing_events, pd.DataFrame([event])], ignore_index=True),
    )
    return True, "approved_for_preview", updated


def refresh_amazon_listing_draft_pipeline(root: Path | None = None) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    try:
        from scripts.flows.F.F090_build_amazon_listing_intake import build_amazon_listing_intake
        from scripts.flows.F.F091_reserve_amazon_listing_skus import reserve_amazon_listing_skus
        from scripts.flows.F.F092_build_amazon_listing_drafts import build_amazon_listing_drafts
    except ModuleNotFoundError:
        from flows.F.F090_build_amazon_listing_intake import build_amazon_listing_intake
        from flows.F.F091_reserve_amazon_listing_skus import reserve_amazon_listing_skus
        from flows.F.F092_build_amazon_listing_drafts import build_amazon_listing_drafts

    intake = build_amazon_listing_intake(root=root_path)
    reservations = reserve_amazon_listing_skus(root=root_path)
    drafts = build_amazon_listing_drafts(root=root_path)
    return {
        "intake_rows": int(len(intake.index)),
        "reservation_rows": int(len(reservations.index)),
        "draft_rows": int(len(drafts.index)),
        "ready_draft_rows": int((drafts.get("draft_status", pd.Series(dtype=str)) == "ready_for_listing_approval").sum()),
        "approved_for_preview_rows": int((drafts.get("draft_status", pd.Series(dtype=str)) == "ready_for_amazon_preview").sum()),
        "blocked_draft_rows": int((drafts.get("draft_status", pd.Series(dtype=str)) == "blocked_missing_local_data").sum()),
    }


def run_amazon_listing_preview_for_draft(root: Path | None = None, *, draft_id: str) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    try:
        from scripts.flows.F.F093_run_amazon_listing_preview import run_amazon_listing_preview
    except ModuleNotFoundError:
        from flows.F.F093_run_amazon_listing_preview import run_amazon_listing_preview

    return run_amazon_listing_preview(
        root=root_path,
        draft_ids=[draft_id],
        run_preview=True,
        max_rows=1,
    )


def _build_lookup(df: pd.DataFrame) -> tuple[dict[str, pd.Series], dict[str, pd.Series]]:
    by_sku: dict[str, pd.Series] = {}
    by_asin: dict[str, pd.Series] = {}
    if df.empty:
        return by_sku, by_asin
    for _, row in df.iterrows():
        sku = _normalize_text(row.get("seller_sku", "")).upper()
        asin = _normalize_text(row.get("asin", "")).upper()
        if sku and sku not in by_sku:
            by_sku[sku] = row
        if asin and asin not in by_asin:
            by_asin[asin] = row
    return by_sku, by_asin


def _uses_legacy_purchase_list_source(value: object) -> bool:
    return "legacy_purchase_list" in _normalize_text(value).lower()


def build_test_orders_df(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    events_df = datasets.get("restock_decision_events", pd.DataFrame()).copy()
    source_df = datasets.get("restock_source_view", pd.DataFrame()).copy()
    bridge_df = datasets.get("legacy_purchase_list_bridge", pd.DataFrame()).copy()
    if events_df.empty:
        return pd.DataFrame(columns=TEST_ORDER_COLUMNS)

    work = events_df.copy()
    work = work[
        work.get("source_reference", "").map(lambda v: _normalize_text(v).startswith("o_ui_supplier_batch:"))
        & work.get("action", "").map(lambda v: _normalize_text(v).lower() in {"approve_full_restock", "approve_test_restock"})
    ].copy()
    if work.empty:
        return pd.DataFrame(columns=TEST_ORDER_COLUMNS)

    work["_event_sort"] = pd.to_datetime(work.get("event_utc", ""), errors="coerce", utc=True)
    work = work.sort_values(by=["_event_sort", "event_id"], ascending=[False, False], kind="stable")
    work["_identity_key"] = work.apply(
        lambda row: (
            _normalize_text(row.get("seller_sku", "")).upper()
            or _normalize_text(row.get("asin", "")).upper()
            or f"EVENT::{_normalize_text(row.get('event_id', ''))}"
        ),
        axis=1,
    )
    work = work.drop_duplicates(subset=["_identity_key"], keep="first")

    src_by_sku, src_by_asin = _build_lookup(source_df)
    bridge_by_sku, bridge_by_asin = _build_lookup(bridge_df)
    rows: list[dict[str, str]] = []
    for _, row in work.iterrows():
        sku_norm = _normalize_text(row.get("seller_sku", "")).upper()
        asin_norm = _normalize_text(row.get("asin", "")).upper()
        bridge_row = bridge_by_sku.get(sku_norm)
        if bridge_row is None:
            bridge_row = bridge_by_asin.get(asin_norm)
        src_row = src_by_sku.get(sku_norm)
        if src_row is None:
            src_row = src_by_asin.get(asin_norm)
        if _uses_legacy_purchase_list_source(row.get("source_reference", "")) and bridge_row is not None:
            src_row = bridge_row
        elif src_row is None and bridge_row is not None:
            src_row = bridge_row
        supplier_name = _normalize_text(src_row.get("supplier_name", "")) if src_row is not None else ""
        supplier_code = _normalize_text(src_row.get("supplier_code", "")) if src_row is not None else ""
        supply_code = _normalize_text(src_row.get("supplier_sku", "")) if src_row is not None else ""
        if supply_code == "" and src_row is not None:
            supply_code = _normalize_text(src_row.get("supplier_code", ""))
        barcode = _normalize_text(src_row.get("barcode", "")) if src_row is not None else ""
        title = _normalize_text(src_row.get("title", "")) if src_row is not None else ""
        ordered_qty = _positive_number_text(row.get("confirmed_qty", ""))
        ordered_unit_cost = _positive_number_text(row.get("confirmed_unit_cost", ""))
        line_value = ""
        qty_num = _to_float(ordered_qty)
        cost_num = _to_float(ordered_unit_cost)
        if qty_num > 0 and cost_num > 0:
            line_value = _num_text(float(qty_num * cost_num))
        rows.append(
            {
                "event_utc": _normalize_text(row.get("event_utc", "")),
                "supplier_name": supplier_name or "(Unknown supplier)",
                "supplier_code": supplier_code,
                "seller_sku": _normalize_text(row.get("seller_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "title": title,
                "supply_code": supply_code,
                "barcode": barcode,
                "ordered_qty": ordered_qty,
                "ordered_unit_cost_gbp": ordered_unit_cost,
                "line_value_gbp": line_value,
                "action": _normalize_text(row.get("action", "")),
            }
        )

    out_df = pd.DataFrame(rows)
    if out_df.empty:
        return out_df
    out_df["_supplier_label"] = out_df["supplier_name"].map(_supplier_label)
    out_df = out_df.sort_values(by=["_supplier_label", "seller_sku"], ascending=[True, True], kind="stable")
    return out_df.drop(columns=["_supplier_label"], errors="ignore").reset_index(drop=True)


PO_DRAFT_REVIEW_COLUMNS = [
    "po_id",
    "supplier_name",
    "po_status",
    "total_lines",
    "total_units",
    "total_value_gbp",
    "po_line_id",
    "seller_sku",
    "asin",
    "title",
    "main_image",
    "ordered_qty",
    "ordered_unit_cost_gbp",
    "supplier_pack_size",
    "ordered_supplier_packs",
    "line_value_gbp",
    "supplier_sku",
    "barcode",
    "source_label",
]


def _build_product_image_lookup(datasets: dict[str, pd.DataFrame]) -> dict[str, str]:
    image_by_key: dict[str, str] = {}
    for dataset_name in (
        "purchase_order_lines_live",
        "product_db_operator_view",
        "restock_source_view",
        "restock_review_queue",
    ):
        source_df = datasets.get(dataset_name, pd.DataFrame())
        if source_df.empty or "main_image" not in source_df.columns:
            continue
        for _, row in source_df.iterrows():
            image_url = _normalize_text(row.get("main_image", ""))
            if not image_url:
                continue
            for key_col in ("seller_sku", "asin"):
                key_value = _normalize_text(row.get(key_col, ""))
                if key_value:
                    image_by_key.setdefault(f"{key_col}:{key_value.upper()}", image_url)
    return image_by_key


def _product_image_for_row(row: pd.Series, image_lookup: dict[str, str]) -> str:
    for key_col in ("seller_sku", "asin"):
        key_value = _normalize_text(row.get(key_col, ""))
        if not key_value:
            continue
        image_url = image_lookup.get(f"{key_col}:{key_value.upper()}")
        if image_url:
            return image_url
    return ""


def _fill_missing_product_images(rows_df: pd.DataFrame, datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if rows_df.empty:
        return rows_df
    out = rows_df.copy()
    if "main_image" not in out.columns:
        out["main_image"] = ""
    image_lookup = _build_product_image_lookup(datasets)
    if not image_lookup:
        return out
    out["main_image"] = out.apply(
        lambda row: _normalize_text(row.get("main_image", "")) or _product_image_for_row(row, image_lookup),
        axis=1,
    )
    return out


PROFIT_CHECK_COLUMNS = [
    "profit_verdict",
    "profit_proof_source",
    "profit_check_message",
    "current_sell_price_gbp",
    "sell_price_basis",
    "forward_profit_per_unit_gbp",
    "break_even_max_cost_gbp",
    "target_roi_max_cost_gbp",
    "profit_guardrail_flags",
    "price_list_unit_cost_gbp",
    "price_list_source_received_at_utc",
    "price_list_unit_code",
    "price_list_pack_size",
    "price_list_pack_cost_gbp",
    "price_list_moq",
    "cost_match_method",
    "cost_confidence",
    "supplier_cost_review_reason",
    "expected_cost_source",
    "actual_paid_unit_cost_gbp",
    "usual_paid_unit_cost_gbp",
    "usual_paid_cost_basis",
    "usual_paid_cost_confidence",
    "usual_paid_sample_count",
    "usual_paid_discount_vs_list_pct",
    "usual_paid_vs_list_delta_gbp",
    "price_list_change_status",
    "price_list_previous_unit_cost_gbp",
    "price_list_previous_pack_size",
    "price_list_previous_seen_at_utc",
    "price_list_change_delta_gbp",
    "price_list_change_pct",
    "max_safe_unit_cost_gbp",
    "price_status",
    "price_status_message",
    "recommended_snooze_until_utc",
    "price_list_vs_actual_paid_delta_gbp",
    "price_list_vs_purchase_reference_delta_gbp",
    "price_proof_summary",
]


def _build_profit_check_lookup(profit_df: pd.DataFrame) -> dict[str, pd.Series]:
    lookup: dict[str, pd.Series] = {}
    if profit_df.empty:
        return lookup
    for _, row in profit_df.iterrows():
        for key_col in ("seller_sku", "asin"):
            key_value = _normalize_text(row.get(key_col, ""))
            if key_value:
                lookup.setdefault(f"{key_col}:{key_value.upper()}", row)
    return lookup


def _profit_check_for_row(row: pd.Series, lookup: dict[str, pd.Series]) -> pd.Series | None:
    for key_col in ("seller_sku", "asin"):
        key_value = _normalize_text(row.get(key_col, ""))
        if not key_value:
            continue
        profit_row = lookup.get(f"{key_col}:{key_value.upper()}")
        if profit_row is not None:
            return profit_row
    return None


def _fill_profit_check_fields(rows_df: pd.DataFrame, datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if rows_df.empty:
        return rows_df
    out = rows_df.copy()
    for col in PROFIT_CHECK_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    lookup = _build_profit_check_lookup(datasets.get("restock_profit_checks_live", pd.DataFrame()))
    if not lookup:
        return out

    def fill_row(row: pd.Series) -> pd.Series:
        profit_row = _profit_check_for_row(row, lookup)
        if profit_row is None:
            return row
        for col in PROFIT_CHECK_COLUMNS:
            value = _normalize_text(row.get(col, ""))
            if value == "":
                source_col = "guardrail_flags" if col == "profit_guardrail_flags" else col
                row[col] = _normalize_text(profit_row.get(source_col, ""))
        if _normalize_text(row.get("expected_forward_roi_pct", "")) == "":
            row["expected_forward_roi_pct"] = _normalize_text(profit_row.get("forward_roi_pct", ""))
        return row

    return out.apply(fill_row, axis=1)


def _fill_current_pack_order_fields(rows_df: pd.DataFrame, datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if rows_df.empty:
        return rows_df
    source_df = datasets.get("restock_source_view", pd.DataFrame()).copy()
    if source_df.empty:
        return rows_df
    source_lookup: dict[str, pd.Series] = {}
    for _, source_row in source_df.iterrows():
        for key_col in ("seller_sku", "asin"):
            key_value = _normalize_text(source_row.get(key_col, ""))
            if key_value:
                source_lookup.setdefault(f"{key_col}:{key_value.upper()}", source_row)

    out = rows_df.copy()
    for col in (
        "supplier_pack_size",
        "order_qty_mode",
        "order_qty_unit_label",
        "sell_pack_qty",
        "supplier_case_qty",
        "supplier_case_multiple",
        "valid_order_step",
        "display_qtys_label",
        "pack_conversion_note",
    ):
        if col not in out.columns:
            out[col] = ""

    def fill_row(row: pd.Series) -> pd.Series:
        source_row = _profit_check_for_row(row, source_lookup)
        if source_row is None:
            return row
        pack_size = _positive_int_value(
            _first_non_blank(source_row.get("price_list_pack_size", ""), source_row.get("supplier_pack_size", ""))
        )
        if not pack_size or pack_size <= 1:
            return row
        current_cost = _positive_number_text(
            _first_non_blank(source_row.get("current_supplier_buy_cost_gbp", ""), source_row.get("price_list_unit_cost_gbp", ""))
        )
        row["supplier_pack_size"] = str(pack_size)
        row["order_qty_mode"] = "sell_packs"
        row["order_qty_unit_label"] = "Packs"
        row["sell_pack_qty"] = str(pack_size)
        row["supplier_case_qty"] = str(pack_size)
        row["supplier_case_multiple"] = "1"
        row["valid_order_step"] = str(pack_size)
        row["display_qtys_label"] = _normalize_text(source_row.get("display_qtys_label", "")) or f"Pack {pack_size} | Case {pack_size}"
        row["qtys"] = row["display_qtys_label"]
        row["pack_conversion_note"] = _normalize_text(source_row.get("pack_conversion_note", "")) or row.get("pack_conversion_note", "")
        if current_cost:
            row["suggested_unit_cost_gbp"] = current_cost
            row["current_supplier_buy_cost_gbp"] = current_cost
            row["cpu"] = current_cost
        row["restk"] = _derive_restock_qty_label(row.to_dict())
        return row

    return out.apply(fill_row, axis=1)


def build_po_draft_review_df(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    headers_df = datasets.get("purchase_orders_live", pd.DataFrame()).copy()
    lines_df = datasets.get("purchase_order_lines_live", pd.DataFrame()).copy()
    if headers_df.empty or lines_df.empty:
        return pd.DataFrame(columns=PO_DRAFT_REVIEW_COLUMNS)

    for col in ("po_id", "supplier_name", "po_status", "total_lines", "total_units", "total_value_gbp"):
        if col not in headers_df.columns:
            headers_df[col] = ""
    for col in (
        "po_id",
        "po_line_id",
        "seller_sku",
        "asin",
        "title",
        "main_image",
        "ordered_qty",
        "ordered_unit_cost_gbp",
        "supplier_pack_size",
        "ordered_supplier_packs",
        "supplier_sku",
        "barcode",
        "source_bridge_reference",
    ):
        if col not in lines_df.columns:
            lines_df[col] = ""

    merged = lines_df.merge(
        headers_df[["po_id", "supplier_name", "po_status", "total_lines", "total_units", "total_value_gbp"]],
        on="po_id",
        how="left",
    )
    merged = _fill_missing_product_images(merged, datasets)
    qty = pd.to_numeric(merged.get("ordered_qty", ""), errors="coerce").fillna(0)
    cost = pd.to_numeric(merged.get("ordered_unit_cost_gbp", ""), errors="coerce").fillna(0)
    merged["line_value_gbp"] = (qty * cost).map(lambda value: _num_text(float(value)) if value > 0 else "")
    merged["source_label"] = merged.get("source_bridge_reference", "").map(
        lambda value: "Google Sheet bridge" if _uses_legacy_purchase_list_source(value) else "Native O"
    )
    for col in PO_DRAFT_REVIEW_COLUMNS:
        if col not in merged.columns:
            merged[col] = ""
    return merged[PO_DRAFT_REVIEW_COLUMNS].sort_values(
        by=["supplier_name", "po_id", "seller_sku"],
        ascending=[True, True, True],
        kind="stable",
    ).reset_index(drop=True)


def _render_po_draft_line_html(row: pd.Series) -> str:
    title = html.escape(_display_plain(row.get("title", ""), "Untitled product"))
    sku = html.escape(_display_plain(row.get("seller_sku", ""), "-"))
    asin = html.escape(_display_plain(row.get("asin", ""), "-"))
    qty = html.escape(_display_plain(row.get("ordered_qty", ""), "0"))
    unit_cost = html.escape(_display_plain(row.get("ordered_unit_cost_gbp", ""), "0"))
    supplier_pack_size = _positive_int_value(row.get("supplier_pack_size", ""))
    ordered_supplier_packs = _normalize_text(row.get("ordered_supplier_packs", ""))
    if ordered_supplier_packs == "" and supplier_pack_size and supplier_pack_size > 1:
        qty_num = _num_or_none(row.get("ordered_qty", ""))
        if qty_num is not None and qty_num > 0 and abs(qty_num / supplier_pack_size - round(qty_num / supplier_pack_size)) <= 0.000001:
            ordered_supplier_packs = str(int(round(qty_num / supplier_pack_size)))
    pack_line = ""
    if ordered_supplier_packs and supplier_pack_size and supplier_pack_size > 1:
        pack_line = f"<br>{html.escape(ordered_supplier_packs)} pack(s) of {supplier_pack_size}"
    line_value = html.escape(_display_plain(row.get("line_value_gbp", ""), "0"))
    supplier_sku = html.escape(_display_plain(row.get("supplier_sku", ""), "-"))
    barcode = html.escape(_display_plain(row.get("barcode", ""), "-"))
    source = html.escape(_display_plain(row.get("source_label", ""), "-"))
    image_url = _normalize_text(row.get("main_image", ""))
    image_html = (
        _image_frame_html(image_url, size=72)
        if image_url
        else (
            "<div style='width:72px;height:72px;border:1px solid #e5e7eb;border-radius:10px;background:#f8fafc;"
            "display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:11px;font-weight:700;"
            "flex:0 0 72px;'>No image</div>"
        )
    )
    return (
        "<div style='padding:10px 0;border-top:1px solid #e5e7eb;display:flex;gap:12px;align-items:flex-start;'>"
        f"{image_html}"
        "<div style='flex:1;min-width:0;'>"
        f"<div style='font-weight:700;font-size:14px;line-height:1.25;color:#111827;'>{title}</div>"
        "<div style='display:grid;grid-template-columns:minmax(130px,1.1fr) minmax(130px,.8fr) minmax(90px,.7fr) minmax(110px,.7fr);gap:10px;margin-top:8px;'>"
        f"<div><div style='font-size:11px;color:#64748b;font-weight:700;'>SKU / ASIN</div><div style='overflow-wrap:anywhere;'>{sku}<br>{asin}</div></div>"
        f"<div><div style='font-size:11px;color:#64748b;font-weight:700;'>Supply / Barcode</div><div style='overflow-wrap:anywhere;'>{supplier_sku}<br>{barcode}</div></div>"
        f"<div><div style='font-size:11px;color:#64748b;font-weight:700;'>Order</div><div>{qty} units{pack_line}<br>GBP {unit_cost} each</div></div>"
        f"<div><div style='font-size:11px;color:#64748b;font-weight:700;'>Line total</div><div>GBP {line_value}<br>{source}</div></div>"
        "</div>"
        "</div>"
        "</div>"
    )


def render_po_drafts_review_tab(datasets: dict[str, pd.DataFrame]) -> None:
    import streamlit as st

    review_df = build_po_draft_review_df(datasets)
    holds_df = datasets.get("purchase_order_draft_holds", pd.DataFrame()).copy()
    st.subheader("PO Draft Review")
    st.caption("Review what you would order from each supplier. These are local drafts only.")

    if review_df.empty:
        st.info("No PO drafts are available yet.")
    else:
        total_pos = review_df["po_id"].nunique()
        total_lines = len(review_df.index)
        total_units = int(pd.to_numeric(review_df["ordered_qty"], errors="coerce").fillna(0).sum())
        total_value = pd.to_numeric(review_df["line_value_gbp"], errors="coerce").fillna(0).sum()
        metric_cols = st.columns(4, gap="small")
        metric_cols[0].metric("Draft POs", total_pos)
        metric_cols[1].metric("Lines", total_lines)
        metric_cols[2].metric("Units", total_units)
        metric_cols[3].metric("Value", f"GBP {_num_text(float(total_value))}")

        for po_id, po_df in review_df.groupby("po_id", sort=False):
            first = po_df.iloc[0]
            supplier_name = _display_plain(first.get("supplier_name", ""), "(Unknown supplier)")
            status = _display_plain(first.get("po_status", ""), "draft")
            units = _display_plain(first.get("total_units", ""), "0")
            value = _display_plain(first.get("total_value_gbp", ""), "0")
            label = f"{po_id} - {supplier_name} - {len(po_df.index)} line - {units} units - GBP {value}"
            with st.expander(label, expanded=True):
                st.markdown(
                    f"**Supplier:** {html.escape(supplier_name)}  \n"
                    f"**Status:** {html.escape(status)}  \n"
                    f"**Draft total:** {html.escape(units)} units, GBP {html.escape(value)}",
                )
                for _, row in po_df.iterrows():
                    st.markdown(_render_po_draft_line_html(row), unsafe_allow_html=True)

    if not holds_df.empty:
        st.warning("Some approved rows could not become PO draft lines. Review these before batch ordering.")
        friendly_cols = [
            col
            for col in ("seller_sku", "decision_action", "final_decision_status", "hold_reason", "hold_note", "source_reference")
            if col in holds_df.columns
        ]
        st.dataframe(holds_df[friendly_cols], width="stretch", hide_index=True)
    else:
        st.success("No PO draft holds.")

    with st.expander("Technical audit tables"):
        st.caption("These are the raw files for debugging and rollback checks.")
        st.subheader("PO Headers")
        st.dataframe(datasets["purchase_orders_live"], width="stretch", hide_index=True)
        st.subheader("PO Lines")
        st.dataframe(datasets["purchase_order_lines_live"], width="stretch", hide_index=True)
        st.subheader("Draft Holds")
        st.dataframe(datasets["purchase_order_draft_holds"], width="stretch", hide_index=True)


def build_recommendations_display_df(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    source_df = datasets.get("restock_source_view", pd.DataFrame())
    base_columns = [
        "title",
        "main_image",
        "seller_sku",
        "asin",
        "supplier_name",
        "suggested_action",
        "suggested_qty",
        "suggested_unit_cost_gbp",
        "suggested_market_price_gbp",
        "expected_forward_roi_pct",
        "days_cover_available_only",
        "recommendation_reason",
        "cost_mode",
        "recommendation_basis",
        "queue_status",
        "snooze_until_utc",
    ]
    out_columns = base_columns + list(BACKTEST_SOURCE_COLUMNS[1:])

    queue_df = datasets.get("restock_review_queue", pd.DataFrame())
    if queue_df.empty:
        rec_df = datasets.get("restock_recommendations_live", pd.DataFrame())
        if rec_df.empty:
            return pd.DataFrame(columns=out_columns)
        rec_df = rec_df.copy()
        rec_df["suggested_action"] = rec_df.get("recommendation_status", "")
        rec_df["suggested_qty"] = rec_df.get("recommended_qty_rounded", "")
        rec_df["suggested_unit_cost_gbp"] = rec_df.get("current_supplier_buy_cost_gbp", "")
        rec_df["suggested_market_price_gbp"] = rec_df.get("market_price_gbp", "")
        rec_df["expected_forward_roi_pct"] = rec_df.get("forward_roi_pct", "")
        rec_df["recommendation_reason"] = rec_df.get("reason_codes", "")
        rec_df["queue_status"] = "unknown"
        rec_df["snooze_until_utc"] = ""
        rec_df = _merge_backtest_columns(rec_df, source_df)
        for col in base_columns:
            if col not in rec_df.columns:
                rec_df[col] = ""
        return rec_df[out_columns]

    queue_df = queue_df.copy()
    if "suggested_action" not in queue_df.columns:
        queue_df["suggested_action"] = queue_df.get("recommendation_status", "")
    if "snooze_until_utc" not in queue_df.columns:
        queue_df["snooze_until_utc"] = ""
    if "queue_status" not in queue_df.columns:
        queue_df["queue_status"] = ""
    if "cost_mode" not in queue_df.columns:
        queue_df["cost_mode"] = ""
    if "recommendation_basis" not in queue_df.columns:
        queue_df["recommendation_basis"] = ""
    if "title" not in queue_df.columns:
        queue_df["title"] = ""
    if "main_image" not in queue_df.columns:
        queue_df["main_image"] = ""
    queue_df["recommendation_reason"] = queue_df.get("key_reason", queue_df.get("reason_codes", ""))
    queue_df = _merge_backtest_columns(queue_df, source_df)
    for col in base_columns:
        if col not in queue_df.columns:
            queue_df[col] = ""
    return queue_df[out_columns]


def _render_recommendation_cards(rec_display: pd.DataFrame) -> str:
    if rec_display.empty:
        return "<p>No recommendations available.</p>"

    cards: list[str] = []
    for _, row in rec_display.iterrows():
        title = _normalize_text(row.get("title", "")) or "Untitled product"
        sku = _normalize_text(row.get("seller_sku", ""))
        asin = _normalize_text(row.get("asin", ""))
        supplier = _normalize_text(row.get("supplier_name", ""))
        action = _normalize_text(row.get("suggested_action", ""))
        qty = _normalize_text(row.get("suggested_qty", ""))
        roi = _normalize_text(row.get("expected_forward_roi_pct", ""))
        days_left = _normalize_text(row.get("days_cover_available_only", ""))
        reason = _normalize_text(row.get("recommendation_reason", ""))
        queue_status = _normalize_text(row.get("queue_status", ""))
        backtest_recommendation = _normalize_text(row.get("backtest_recommendation", ""))
        backtest_monthly_profit = _normalize_text(row.get("backtest_estimated_monthly_profit_gbp", ""))
        backtest_total_profit = _normalize_text(row.get("backtest_estimated_total_profit_gbp", ""))
        backtest_viability = _normalize_text(row.get("backtest_market_viability_score", ""))
        backtest_exit_risk = _normalize_text(row.get("backtest_exit_risk_score", ""))
        backtest_amazon_risk = _normalize_text(row.get("backtest_amazon_risk_level", ""))
        backtest_confidence = _normalize_text(row.get("backtest_history_confidence", ""))
        image_url = _normalize_text(row.get("main_image", ""))
        image_html = (
            f'<img src="{image_url}" style="max-width:72px;max-height:72px;object-fit:contain;" />'
            if image_url
            else '<div style="width:72px;height:72px;display:flex;align-items:center;justify-content:center;color:#888;font-size:12px;">No image</div>'
        )
        backtest_pairs: list[tuple[str, str]] = []
        if backtest_monthly_profit:
            backtest_pairs.append(("Monthly", f"\u00A3{backtest_monthly_profit}"))
        if backtest_total_profit:
            backtest_pairs.append(("Total", f"\u00A3{backtest_total_profit}"))
        if backtest_viability:
            backtest_pairs.append(("Viability", backtest_viability))
        if backtest_exit_risk:
            backtest_pairs.append(("Exit risk", backtest_exit_risk))
        if backtest_amazon_risk:
            backtest_pairs.append(("Amazon risk", backtest_amazon_risk))
        if backtest_confidence:
            backtest_pairs.append(("Confidence", backtest_confidence))
        backtest_section = ""
        if backtest_recommendation or backtest_pairs:
            chips = "".join([f"<span><strong>{label}:</strong> {value}</span>" for label, value in backtest_pairs])
            recommendation_html = f"<div><strong>Backtest:</strong> {backtest_recommendation or '-'}</div>"
            backtest_section = (
                "<div style=\"margin-top:8px;padding:8px;border:1px solid #dde7f6;border-radius:8px;background:#f7faff;\">"
                f"{recommendation_html}"
                f"<div style=\"display:flex;flex-wrap:wrap;gap:8px 12px;font-size:12px;margin-top:4px;\">{chips}</div>"
                "</div>"
            )

        cards.append(
            f"""
            <div style="display:flex;gap:14px;padding:12px 0;border-bottom:1px solid #e9e9e9;">
              <div style="width:86px;height:86px;background:#fff;border:1px solid #ddd;border-radius:10px;display:flex;align-items:center;justify-content:center;flex:0 0 86px;overflow:hidden;">
                {image_html}
              </div>
              <div style="min-width:0;flex:1;">
                <div style="font-size:17px;font-weight:600;line-height:1.25;margin-bottom:4px;">{title}</div>
                <div style="font-size:14px;font-weight:700;color:#222;margin-bottom:2px;">SKU: {sku}</div>
                <div style="font-size:12px;color:#666;margin-bottom:8px;">ASIN: {asin or "-"} | Supplier: {supplier or "-"}</div>
                <div style="display:flex;flex-wrap:wrap;gap:8px 12px;font-size:13px;">
                  <span><strong>Action:</strong> {action or "-"}</span>
                  <span><strong>Qty:</strong> {qty or "-"}</span>
                  <span><strong>ROI:</strong> {roi or "-"}</span>
                  <span><strong>Days Left:</strong> {days_left or "-"}</span>
                  <span><strong>Status:</strong> {queue_status or "-"}</span>
                </div>
                <div style="font-size:12px;color:#555;margin-top:8px;"><strong>Reason:</strong> {reason or "-"}</div>
                {backtest_section}
              </div>
            </div>
            """
        )
    return "".join(cards)


def _default_decision_action(suggested_action: str) -> str:
    action = _normalize_text(suggested_action).lower()
    if action == "full_restock":
        return "approve_full_restock"
    if action == "test_restock":
        return "approve_test_restock"
    return "wait"


def _coerce_flag(value: object) -> bool:
    token = _normalize_text(value).lower()
    return token in {"1", "true", "yes", "y", "on"}


def _positive_number_text(value: object) -> str:
    raw = _normalize_text(value)
    if raw == "":
        return ""
    try:
        as_float = float(raw)
    except ValueError:
        return ""
    if as_float <= 0:
        return ""
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.6f}".rstrip("0").rstrip(".")


def _first_non_blank(*values: object) -> str:
    for value in values:
        text = _normalize_text(value)
        if text != "":
            return text
    return ""


def _num_or_none(value: object) -> float | None:
    raw = _normalize_text(value)
    if raw == "":
        return None
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _positive_int_value(value: object) -> int | None:
    number = _num_or_none(value)
    if number is None or number <= 0 or not number.is_integer():
        return None
    return int(number)


def _normalize_order_qty_mode(value: object) -> str:
    token = _normalize_text(value).lower()
    if token in {"raw_units", "sell_packs", "bundles"}:
        return token
    return "raw_units"


def _derive_order_qty_unit_label(row_data: dict[str, object]) -> str:
    explicit = _normalize_text(row_data.get("order_qty_unit_label", ""))
    if explicit != "":
        return explicit
    return {
        "raw_units": "Units",
        "sell_packs": "Packs",
        "bundles": "Bundles",
    }.get(_normalize_order_qty_mode(row_data.get("order_qty_mode", "")), "Units")


def _derive_qtys_label(row_data: dict[str, object]) -> str:
    explicit = _normalize_text(row_data.get("display_qtys_label", ""))
    if explicit != "":
        return explicit

    mode = _normalize_order_qty_mode(row_data.get("order_qty_mode", ""))
    sell_pack_qty = _positive_int_value(_first_non_blank(row_data.get("sell_pack_qty", ""), row_data.get("amazon_pack_size", ""))) or 1
    amazon_pack_size = _positive_int_value(_first_non_blank(row_data.get("amazon_pack_size", ""), row_data.get("sell_pack_qty", ""))) or sell_pack_qty
    supplier_case_qty = _positive_int_value(_first_non_blank(row_data.get("supplier_case_qty", ""), row_data.get("supplier_pack_size", ""))) or 1
    supplier_case_multiple = _coerce_flag(row_data.get("supplier_case_multiple", False))
    valid_order_step = _positive_int_value(row_data.get("valid_order_step", ""))

    parts: list[str] = []
    if mode == "bundles":
        parts.append(f"Bundle {amazon_pack_size}")
    elif mode == "sell_packs":
        parts.append(f"Pack {sell_pack_qty}")
    elif supplier_case_multiple and supplier_case_qty > 1:
        parts.append(f"Case {supplier_case_qty}")
    else:
        parts.append("Unit")

    if mode in {"sell_packs", "bundles"} and supplier_case_qty > 1:
        parts.append(f"Case {supplier_case_qty}")

    if valid_order_step and valid_order_step > 1:
        skip_step = mode == "raw_units" and supplier_case_multiple and supplier_case_qty > 1 and valid_order_step == supplier_case_qty
        if not skip_step:
            parts.append(f"Step {valid_order_step}")

    return " | ".join(parts)


def _derive_supply_code(row_data: dict[str, object]) -> str:
    return _first_non_blank(
        row_data.get("supplier_sku", ""),
        row_data.get("supply_code", ""),
        row_data.get("supplier_code", ""),
    )


def _derive_restock_qty_label(row_data: dict[str, object]) -> str:
    raw_qty = _first_non_blank(row_data.get("suggested_qty", ""), row_data.get("restk", ""))
    qty_num = _num_or_none(raw_qty)
    if qty_num is None or qty_num <= 0:
        return _display_plain(raw_qty, "0")
    mode = _normalize_order_qty_mode(row_data.get("order_qty_mode", ""))
    pack_size = _positive_int_value(_first_non_blank(row_data.get("sell_pack_qty", ""), row_data.get("supplier_pack_size", "")))
    if mode == "sell_packs" and pack_size and pack_size > 1:
        pack_qty = int(qty_num // pack_size)
        if qty_num % pack_size:
            pack_qty += 1
        rounded_qty = pack_qty * pack_size
        return f"{pack_qty}pk ({_num_text(float(rounded_qty))})"
    return _display_plain(_num_text(qty_num), "0")


def _order_qty_to_raw_event_qty(row_data: dict[str, object]) -> str:
    order_qty = _positive_number_text(row_data.get("order_qty", ""))
    if order_qty == "":
        return ""

    mode = _normalize_order_qty_mode(row_data.get("order_qty_mode", ""))
    if mode == "raw_units":
        return order_qty

    multiplier = _positive_int_value(_first_non_blank(row_data.get("sell_pack_qty", ""), row_data.get("amazon_pack_size", "")))
    order_qty_num = _num_or_none(order_qty)
    if order_qty_num is None or order_qty_num <= 0 or not order_qty_num.is_integer() or multiplier is None:
        return ""
    return str(int(order_qty_num) * multiplier)


def _derive_row_status(row: pd.Series) -> str:
    if _normalize_text(row.get("queue_status", "")).lower() == "snoozed":
        return "snoozed"
    suggested = _normalize_text(row.get("suggested_action", "")).lower()
    order_qty = _positive_number_text(row.get("order_qty", ""))
    confirmed_price = _positive_number_text(row.get("confirmed_price", ""))
    if suggested in {"full_restock", "test_restock"}:
        if confirmed_price == "":
            return "needs_price"
        if _confirmed_price_safety(row.to_dict(), confirmed_price).get("status") == "confirmed_over_max_blocked":
            return "blocked"
        if order_qty == "":
            return "needs_qty"
        return "ready"
    if suggested == "wait":
        return "blocked"
    return "watch"


def _empty_reorder_input_df() -> pd.DataFrame:
    return pd.DataFrame(columns=REORDER_INPUT_COLUMNS)


def _ensure_reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in REORDER_INPUT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[REORDER_INPUT_COLUMNS]


def _legacy_bridge_reorder_input_df(bridge_df: pd.DataFrame) -> pd.DataFrame:
    if bridge_df.empty:
        return _empty_reorder_input_df()

    work = bridge_df.copy()
    required = [
        "bridge_status",
        "seller_sku",
        "asin",
        "title",
        "supplier_name",
        "suggested_action",
        "suggested_qty",
        "suggested_unit_cost_gbp",
        "suggested_market_price_gbp",
        "order_qty",
        "confirmed_price",
        "disc_flag",
        "drop_flag",
        "snooze_flag",
        "bridge_note",
        "expected_forward_roi_pct",
        "days_cover_available_only",
        "cost_mode",
        "recommendation_basis",
        "queue_status",
        "barcode",
        "display_qtys_label",
        "supplier_sku",
        "current_supplier_buy_cost_gbp",
        "available_now",
        "ordered_open",
        "velocity_30d",
        "sheet_recommend_label",
        "reorder_value_gbp",
        "order_qty_mode",
        "order_qty_unit_label",
        "sell_pack_qty",
        "supplier_case_qty",
        "supplier_case_multiple",
        "valid_order_step",
        "repack_required",
        "bundle_required",
        "pack_conversion_note",
        "source_system",
        "source_reference",
        "operator_text",
    ]
    for col in required:
        if col not in work.columns:
            work[col] = ""
    work = work[work["bridge_status"].map(lambda v: _normalize_text(v).lower() in {"", "ready"})].copy()
    if work.empty:
        return _empty_reorder_input_df()

    out = pd.DataFrame()
    out["send"] = False
    out["seller_sku"] = work["seller_sku"].map(_normalize_text)
    out["title"] = work["title"].map(_normalize_text)
    out["main_image"] = ""
    out["supplier_name"] = work["supplier_name"].map(_normalize_text)
    out["suggested_action"] = work["suggested_action"].map(_normalize_text)
    out["suggested_qty"] = work["suggested_qty"].map(_normalize_text)
    out["suggested_unit_cost_gbp"] = work["suggested_unit_cost_gbp"].map(_normalize_text)
    out["suggested_market_price_gbp"] = work["suggested_market_price_gbp"].map(_normalize_text)
    out["order_qty"] = work["order_qty"].map(_normalize_text)
    out["confirmed_price"] = work["confirmed_price"].map(_normalize_text)
    out["disc"] = work["disc_flag"].map(_coerce_flag)
    out["drop"] = work["drop_flag"].map(_coerce_flag)
    out["snze"] = work["snooze_flag"].map(_coerce_flag)
    out["snooze_date"] = ""
    out["recommendation_reason"] = work["bridge_note"].map(_normalize_text)
    out["expected_forward_roi_pct"] = work["expected_forward_roi_pct"].map(_normalize_text)
    out["days_cover_available_only"] = work["days_cover_available_only"].map(_normalize_text)
    out["asin"] = work["asin"].map(_normalize_text)
    out["cost_mode"] = work["cost_mode"].map(lambda v: _normalize_text(v) or "legacy_sheet")
    out["recommendation_basis"] = work["recommendation_basis"].map(_normalize_text)
    out["queue_status"] = work["queue_status"].map(lambda v: _normalize_text(v) or "needs_review")
    for col in BACKTEST_SOURCE_COLUMNS[1:]:
        out[col] = ""
    out["decision_note"] = work["operator_text"].map(_normalize_text)
    out["barcode"] = work["barcode"].map(lambda v: _display_plain(v, ""))
    out["qtys"] = work["display_qtys_label"].map(lambda v: _display_plain(v, "Unit"))
    out["supply_code"] = work["supplier_sku"].map(lambda v: _display_plain(v, ""))
    out["cpu"] = work["current_supplier_buy_cost_gbp"].map(lambda v: _display_plain(v, ""))
    out["stock"] = work["available_now"].map(lambda v: _display_plain(v, "0"))
    out["ordered_open"] = work["ordered_open"].map(lambda v: _display_plain(v, "0"))
    out["vlcity"] = work["velocity_30d"].map(lambda v: _display_plain(v, "0"))
    out["days"] = work["days_cover_available_only"].map(lambda v: _display_plain(v, "0"))
    out["recommend"] = work["sheet_recommend_label"].map(lambda v: _display_plain(v, ""))
    out["resk_val"] = work["reorder_value_gbp"].map(lambda v: _display_plain(v, ""))
    out["supplier_sku"] = work["supplier_sku"].map(_normalize_text)
    out["order_qty_mode"] = work["order_qty_mode"].map(lambda v: _normalize_text(v) or "raw_units")
    out["order_qty_unit_label"] = work["order_qty_unit_label"].map(lambda v: _normalize_text(v) or "Units")
    out["sell_pack_qty"] = work["sell_pack_qty"].map(lambda v: _normalize_text(v) or "1")
    out["supplier_case_qty"] = work["supplier_case_qty"].map(lambda v: _normalize_text(v) or "1")
    out["supplier_case_multiple"] = work["supplier_case_multiple"].map(lambda v: _normalize_text(v) or "0")
    out["valid_order_step"] = work["valid_order_step"].map(lambda v: _normalize_text(v) or "1")
    out["repack_required"] = work["repack_required"].map(lambda v: _normalize_text(v) or "0")
    out["bundle_required"] = work["bundle_required"].map(lambda v: _normalize_text(v) or "0")
    out["display_qtys_label"] = work["display_qtys_label"].map(lambda v: _display_plain(v, "Unit"))
    out["pack_conversion_note"] = work["pack_conversion_note"].map(_normalize_text)
    out["source_system"] = work["source_system"].map(lambda v: _normalize_text(v) or "legacy_purchase_list")
    out["source_reference"] = work["source_reference"].map(_normalize_text)
    out["sheet_recommend_label"] = work["sheet_recommend_label"].map(_normalize_text)
    out["restk"] = out.apply(lambda row: _derive_restock_qty_label(row.to_dict()), axis=1)
    out["row_status"] = out.apply(_derive_row_status, axis=1)
    return _ensure_reorder_columns(out)


def _merge_bridge_and_native_reorder_rows(bridge_rows: pd.DataFrame, native_rows: pd.DataFrame) -> pd.DataFrame:
    bridge_out = _ensure_reorder_columns(bridge_rows)
    native_out = _ensure_reorder_columns(native_rows)
    if bridge_out.empty:
        return native_out
    if native_out.empty:
        return bridge_out

    bridge_skus = {
        _normalize_text(value).upper()
        for value in bridge_out.get("seller_sku", pd.Series(dtype=str)).tolist()
        if _normalize_text(value) != ""
    }
    bridge_asins = {
        _normalize_text(value).upper()
        for value in bridge_out.get("asin", pd.Series(dtype=str)).tolist()
        if _normalize_text(value) != ""
    }

    def covered(row: pd.Series) -> bool:
        sku = _normalize_text(row.get("seller_sku", "")).upper()
        asin = _normalize_text(row.get("asin", "")).upper()
        return (sku != "" and sku in bridge_skus) or (asin != "" and asin in bridge_asins)

    native_out = native_out[~native_out.apply(covered, axis=1)].copy()
    return pd.concat([bridge_out, native_out], ignore_index=True)


def build_reorder_input_df(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rec = build_recommendations_display_df(datasets).copy()
    source_df = datasets.get("restock_source_view", pd.DataFrame()).copy()
    ordered_stock_df = datasets.get("ordered_stock_state", pd.DataFrame()).copy()
    bridge_rows = _legacy_bridge_reorder_input_df(datasets.get("legacy_purchase_list_bridge", pd.DataFrame()).copy())
    if rec.empty:
        merged_rows = _merge_bridge_and_native_reorder_rows(bridge_rows, _empty_reorder_input_df())
        merged_rows = _fill_current_pack_order_fields(merged_rows, datasets)
        merged_rows = _fill_missing_product_images(merged_rows, datasets)
        return _fill_profit_check_fields(merged_rows, datasets)

    source_cols = [
        "seller_sku",
        "supplier_pack_size",
        "supplier_code",
        "supplier_sku",
        "barcode",
        "amazon_pack_size",
        "pack_conversion_note",
        "order_qty_mode",
        "order_qty_unit_label",
        "sell_pack_qty",
        "supplier_case_qty",
        "supplier_case_multiple",
        "valid_order_step",
        "repack_required",
        "bundle_required",
        "display_qtys_label",
        "current_supplier_buy_cost_gbp",
        "available_now",
        "velocity_30d",
        "backtest_policy_id",
        "backtest_history_confidence",
        "backtest_market_viability_score",
        "backtest_exit_risk_score",
        "backtest_estimated_total_profit_gbp",
        "backtest_estimated_monthly_profit_gbp",
        "backtest_capital_lockup_days",
        "backtest_sellable_ceiling_zone",
        "backtest_amazon_risk_level",
        "backtest_compression_risk_level",
        "backtest_recommendation",
        "backtest_manual_review_reason",
        "price_list_unit_cost_gbp",
        "price_list_source_received_at_utc",
        "price_list_unit_code",
        "price_list_pack_size",
        "price_list_pack_cost_gbp",
        "price_list_moq",
        "cost_match_method",
        "current_cost_confidence",
        "supplier_cost_review_reason",
        "expected_cost_source",
        "actual_paid_unit_cost_gbp",
        "usual_paid_unit_cost_gbp",
        "usual_paid_cost_basis",
        "usual_paid_cost_confidence",
        "usual_paid_sample_count",
        "usual_paid_discount_vs_list_pct",
        "usual_paid_vs_list_delta_gbp",
        "price_list_change_status",
        "price_list_previous_unit_cost_gbp",
        "price_list_previous_pack_size",
        "price_list_previous_seen_at_utc",
        "price_list_change_delta_gbp",
        "price_list_change_pct",
        "max_safe_unit_cost_gbp",
        "price_list_vs_actual_paid_delta_gbp",
        "price_list_vs_purchase_reference_delta_gbp",
    ]
    if not source_df.empty:
        for col in source_cols:
            if col not in source_df.columns:
                source_df[col] = ""
        source_df = source_df[source_cols].drop_duplicates(subset=["seller_sku"], keep="first")
        rec = rec.merge(source_df, on="seller_sku", how="left")
    else:
        for col in source_cols:
            if col != "seller_sku":
                rec[col] = ""

    ordered_open_lookup = _build_ordered_open_lookup(ordered_stock_df)

    rec["send"] = False
    rec["order_qty"] = ""
    rec["confirmed_price"] = ""
    rec["disc"] = False
    rec["drop"] = False
    rec["snze"] = rec.get("queue_status", "").map(lambda v: _normalize_text(v).lower() == "snoozed")
    rec["snooze_date"] = rec.get("snooze_until_utc", "").map(lambda v: _normalize_text(v)[:10])
    rec["decision_note"] = ""
    rec["row_status"] = rec.apply(_derive_row_status, axis=1)
    rec["barcode"] = rec.get("barcode", "").map(lambda v: _display_plain(v, ""))
    rec["qtys"] = rec.apply(lambda row: _derive_qtys_label(row.to_dict()), axis=1)
    rec["supply_code"] = rec.apply(lambda row: _derive_supply_code(row.to_dict()), axis=1)
    rec["cpu"] = rec.get("suggested_unit_cost_gbp", "").map(lambda v: _display_plain(v, ""))
    rec["stock"] = rec.get("available_now", "").map(lambda v: _display_plain(v, "0"))
    rec["ordered_open"] = rec.get("seller_sku", "").map(lambda v: ordered_open_lookup.get(_normalize_text(v).upper(), "0"))
    rec["vlcity"] = rec.get("velocity_30d", "").map(lambda v: _display_plain(v, "0"))
    rec["days"] = rec.get("days_cover_available_only", "").map(lambda v: _display_plain(v, "0"))
    rec["recommend"] = rec.get("suggested_action", "").map(_action_label)
    rec["restk"] = rec.apply(lambda row: _derive_restock_qty_label(row.to_dict()), axis=1)
    rec["resk_val"] = (
        pd.to_numeric(rec.get("suggested_qty", ""), errors="coerce").fillna(0)
        * pd.to_numeric(rec.get("suggested_unit_cost_gbp", ""), errors="coerce").fillna(0)
    ).map(lambda v: _num_text(v) if v > 0 else "")
    rec["cost_confidence"] = rec.get("current_cost_confidence", "").map(_normalize_text)
    rec["source_system"] = "native_o"
    rec["source_reference"] = rec.get("seller_sku", "").map(lambda v: f"native_o:{_normalize_text(v)}")
    rec["sheet_recommend_label"] = ""

    for col in REORDER_INPUT_COLUMNS:
        if col not in rec.columns:
            rec[col] = ""
    merged_rows = _merge_bridge_and_native_reorder_rows(bridge_rows, rec[REORDER_INPUT_COLUMNS])
    merged_rows = _fill_current_pack_order_fields(merged_rows, datasets)
    merged_rows = _fill_missing_product_images(merged_rows, datasets)
    return _fill_profit_check_fields(merged_rows, datasets)


def _supplier_label(value: object) -> str:
    text = _normalize_text(value)
    return text if text else "(Unknown supplier)"


def _supplier_display_map(root: Path | None = None) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    profiles_df = _read_contract_df(root_path, "supplier_profiles")
    label_map: dict[str, str] = {}
    if profiles_df.empty:
        return label_map
    for _, row in profiles_df.iterrows():
        supplier_code = _normalize_text(row.get("supplier_code", ""))
        supplier_name = _normalize_text(row.get("supplier_name", ""))
        if supplier_code and supplier_name and supplier_code not in label_map:
            label_map[supplier_code] = supplier_name
    return label_map


def _supplier_option_label(value: object, label_map: dict[str, str]) -> str:
    text = _normalize_text(value)
    if text == "All suppliers":
        return text
    return _normalize_text(label_map.get(text, "")) or _supplier_label(text)


def _supplier_key_fragment(value: str) -> str:
    lowered = _normalize_text(value).lower()
    chars: list[str] = []
    for ch in lowered:
        if ch.isalnum():
            chars.append(ch)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or "unknown_supplier"


def _image_frame_html(image_url: str, *, size: int = 52) -> str:
    safe_url = quote(image_url, safe=":/?&=%+-._~#")
    return (
        f"<div style='width:{size}px;height:{size}px;border:1px solid #e5e7eb;border-radius:10px;background:#fff;"
        f"display:flex;align-items:center;justify-content:center;overflow:hidden;flex:0 0 {size}px;'>"
        f"<img src=\"{safe_url}\" style='width:100%;height:100%;object-fit:contain;display:block;background:#fff;'/>"
        f"</div>"
    )


def _intake_image_html(image_url: object, amazon_dp_url: object) -> str:
    image_text = _normalize_text(image_url)
    amazon_url = _normalize_text(amazon_dp_url)
    if image_text:
        safe_url = quote(image_text, safe=":/?&=%+-._~#")
        return (
            "<div class='o-intake-image-frame'>"
            f"<img src=\"{safe_url}\" alt='Product image' loading='lazy'/>"
            "</div>"
        )
    amazon_link = ""
    if amazon_url:
        amazon_link = (
            f"<a href='{html.escape(amazon_url, quote=True)}' target='_blank' "
            "rel='noopener noreferrer'>Open Amazon</a>"
        )
    return (
        "<div class='o-intake-image-placeholder'>"
        "<div>Image unavailable</div>"
        f"{amazon_link}"
        "</div>"
    )


def _display_money(value: object) -> str:
    text = _normalize_text(value)
    if text == "":
        return "-"
    return f"£{text}"


def _display_stock_ordered_stack(stock_value: object, ordered_value: object) -> str:
    stock_text = html.escape(_display_plain(stock_value, "0"))
    ordered_text = html.escape(_display_plain(ordered_value, "0"))
    return (
        "<div style='margin-top:2px;line-height:1.08;'>"
        "<div style='font:600 10px sans-serif;color:#93c5fd;margin-bottom:2px;'>Stock</div>"
        f"<div style='margin-bottom:5px;'>{stock_text}</div>"
        "<div style='font:600 10px sans-serif;color:#93c5fd;margin-bottom:2px;'>Ordered</div>"
        f"<div>{ordered_text}</div>"
        "</div>"
    )


def _display_plain(value: object, fallback: str = "-") -> str:
    text = _normalize_text(value)
    return text if text else fallback


def _action_label(value: object) -> str:
    token = _normalize_text(value).lower()
    labels = {
        "full_restock": "Restock",
        "test_restock": "Test",
        "wait": "Wait",
    }
    return labels.get(token, token.replace("_", " ").title() or "-")


def _copy_value_html(value: object, *, fallback: str = "-") -> str:
    content = _copy_value_fragment(value, fallback=fallback)
    return (
        "<!doctype html><html><body style='margin:0;padding:0;background:transparent;'>"
        f"{content}</body></html>"
    )


def _copy_value_fragment(value: object, *, fallback: str = "-") -> str:
    text = _normalize_text(value)
    if text == "":
        return f"<div style='color:#cbd5e1;font:500 12px sans-serif;line-height:1.08;'>{html.escape(fallback)}</div>"
    escaped_text = html.escape(text)
    js_text = html.escape(json.dumps(text), quote=True)
    return (
        "<div style='display:flex;align-items:flex-start;gap:6px;width:100%;'>"
        f"<button type='button' title='Copy {escaped_text}' "
        f"onclick=\"navigator.clipboard.writeText({js_text});const badge=this.nextElementSibling;"
        "badge.style.opacity='1';const timer=Number(this.dataset.timer||'0');if(timer){window.clearTimeout(timer);}this.dataset.timer=String(window.setTimeout(()=>{badge.style.opacity='0';},900));\" "
        "style='background:none;border:none;padding:0;margin:0;color:#dbe4ee;cursor:pointer;"
        "font:500 12px sans-serif;text-align:left;line-height:1.08;white-space:nowrap;"
        "overflow:hidden;text-overflow:ellipsis;width:100%;'>"
        f"{escaped_text}</button>"
        "<div style='opacity:0;transition:opacity .18s ease;flex:0 0 auto;"
        "margin-top:1px;padding:1px 6px;border:1px solid #38bdf8;border-radius:999px;"
        "color:#7dd3fc;font:600 10px sans-serif;'>Copied</div>"
        "</div>"
    )


def _copy_pair_html(
    top_label: str,
    top_value: object,
    bottom_label: str,
    bottom_value: object,
    *,
    top_fallback: str = "-",
    bottom_fallback: str = "-",
) -> str:
    return (
        "<!doctype html><html><body style='margin:0;padding:0;background:transparent;'>"
        f"<div style='font:600 10px sans-serif;color:#93c5fd;margin:0 0 2px 0;letter-spacing:0;'>{html.escape(top_label)}</div>"
        f"{_copy_value_fragment(top_value, fallback=top_fallback)}"
        f"<div style='font:600 10px sans-serif;color:#93c5fd;margin:6px 0 2px 0;letter-spacing:0;'>{html.escape(bottom_label)}</div>"
        f"{_copy_value_fragment(bottom_value, fallback=bottom_fallback)}"
        "</body></html>"
    )


def _render_copy_pair(
    top_label: str,
    top_value: object,
    bottom_label: str,
    bottom_value: object,
    *,
    top_fallback: str = "-",
    bottom_fallback: str = "-",
) -> None:
    import streamlit.components.v1 as components

    components.html(
        _copy_pair_html(
            top_label,
            top_value,
            bottom_label,
            bottom_value,
            top_fallback=top_fallback,
            bottom_fallback=bottom_fallback,
        ),
        height=68,
        scrolling=False,
    )


def _backtest_brief_label(row_data: dict[str, object]) -> str:
    recommendation = _normalize_text(row_data.get("backtest_recommendation", ""))
    monthly_profit = _normalize_text(row_data.get("backtest_estimated_monthly_profit_gbp", ""))
    viability_score = _normalize_text(row_data.get("backtest_market_viability_score", ""))
    exit_risk_score = _normalize_text(row_data.get("backtest_exit_risk_score", ""))
    confidence = _normalize_text(row_data.get("backtest_history_confidence", ""))
    if not any((recommendation, monthly_profit, viability_score, exit_risk_score, confidence)):
        return ""
    parts: list[str] = []
    if recommendation:
        parts.append(f"Backtest: {recommendation}")
    if monthly_profit:
        parts.append(f"M £{monthly_profit}")
    if viability_score:
        parts.append(f"V {viability_score}")
    if exit_risk_score:
        parts.append(f"E {exit_risk_score}")
    if confidence:
        parts.append(f"C {confidence}")
    return " | ".join(parts[:4])


def _profit_check_badge_html(row_data: dict[str, object]) -> str:
    verdict = _normalize_text(row_data.get("profit_verdict", ""))
    message = _normalize_text(row_data.get("profit_check_message", ""))
    source = _normalize_text(row_data.get("profit_proof_source", ""))
    roi = _normalize_text(row_data.get("expected_forward_roi_pct", "")) or _normalize_text(row_data.get("forward_roi_pct", ""))
    profit = _normalize_text(row_data.get("forward_profit_per_unit_gbp", ""))
    market = _normalize_text(row_data.get("current_sell_price_gbp", "")) or _normalize_text(row_data.get("suggested_market_price_gbp", ""))
    cost = _normalize_text(row_data.get("cpu", "")) or _normalize_text(row_data.get("suggested_unit_cost_gbp", ""))
    flags = _normalize_text(row_data.get("profit_guardrail_flags", ""))
    price_proof = _normalize_text(row_data.get("price_proof_summary", ""))

    if verdict == "" and not any((roi, profit, market, cost)):
        return ""

    labels = {
        "safe_to_review": "Profit: review",
        "test_only": "Profit: test only",
        "do_not_buy_now": "Profit: do not buy now",
        "needs_price_check": "Profit: check price",
        "missing_profit_inputs": "Profit: missing proof",
        "temporary_market_risk": "Profit: temp market risk",
        "drop_review_only": "Profit: drop review",
    }
    colors = {
        "safe_to_review": ("#064e3b", "#d1fae5", "#10b981"),
        "test_only": ("#713f12", "#fef3c7", "#f59e0b"),
        "do_not_buy_now": ("#7f1d1d", "#fee2e2", "#ef4444"),
        "needs_price_check": ("#7c2d12", "#ffedd5", "#fb923c"),
        "missing_profit_inputs": ("#334155", "#f1f5f9", "#94a3b8"),
        "temporary_market_risk": ("#1e3a8a", "#dbeafe", "#3b82f6"),
        "drop_review_only": ("#581c87", "#f3e8ff", "#a855f7"),
    }
    text_color, bg_color, border_color = colors.get(verdict, ("#334155", "#f8fafc", "#cbd5e1"))
    label = labels.get(verdict, "Profit check")
    if message == "":
        parts = []
        if roi:
            parts.append(f"ROI {roi} percent")
        if profit:
            parts.append(f"GBP {profit} profit/unit")
        if market:
            parts.append(f"sell GBP {market}")
        if cost:
            parts.append(f"cost GBP {cost}")
        message = ", ".join(parts) if parts else "Current profit proof is not available."
    detail_parts = [message]
    message_lower = message.lower()
    if source == "legacy_sheet_profit_hint" and "sheet roi hint only" not in message_lower:
        detail_parts.append("Sheet ROI hint only.")
    elif source == "native_profit_incomplete" and "native proof incomplete" not in message_lower:
        detail_parts.append("Native proof incomplete.")
    if flags:
        short_flags = flags.replace("|", ", ")
        detail_parts.append(f"Guardrail: {short_flags}.")
    if price_proof == "":
        proof_parts: list[str] = []
        list_cost = _normalize_text(row_data.get("price_list_unit_cost_gbp", ""))
        list_date = _normalize_text(row_data.get("price_list_source_received_at_utc", ""))
        match_method = _normalize_text(row_data.get("cost_match_method", ""))
        confidence = _normalize_text(row_data.get("cost_confidence", ""))
        review_reason = _normalize_text(row_data.get("supplier_cost_review_reason", ""))
        if list_cost:
            proof_parts.append(f"current list GBP {list_cost}")
        if list_date:
            proof_parts.append(f"list date {list_date[:10]}")
        if match_method:
            proof_parts.append(f"matched by {match_method.replace('_', ' ')}")
        if confidence:
            proof_parts.append(f"confidence {confidence.replace('_', ' ')}")
        if review_reason:
            proof_parts.append(f"check reason {review_reason.replace('|', ', ').replace('_', ' ')}")
        price_proof = "; ".join(proof_parts)
    if price_proof:
        detail_parts.append(f"Price proof: {price_proof}.")

    details_text = " | ".join(part for part in detail_parts if _normalize_text(part))
    help_symbol = _hover_badge_html(
        symbol="?",
        border_color=border_color,
        text_color=text_color,
        heading=label,
        details_text=details_text,
    )

    return (
        "<div style='margin-top:4px;display:flex;align-items:center;gap:6px;flex-wrap:nowrap;'>"
        f"<span style='display:inline-flex;align-items:center;min-height:20px;padding:2px 7px;"
        f"border:1px solid {border_color};border-radius:7px;background:{bg_color};color:{text_color};"
        "font-size:11px;font-weight:700;line-height:1.1;white-space:nowrap;'>"
        f"{html.escape(label)}</span>"
        f"{help_symbol}"
        "</div>"
    )


def _confirmed_price_safety(row_data: dict[str, object], confirmed_price: object) -> dict[str, str]:
    confirmed = _num_or_none(confirmed_price)
    max_safe = _num_or_none(
        _first_non_blank(row_data.get("max_safe_unit_cost_gbp", ""), row_data.get("target_roi_max_cost_gbp", ""))
    )
    if confirmed is None or confirmed <= 0:
        return {
            "status": "confirmed_price_missing",
            "delta": "",
            "blocked": "0",
            "message": "Type the confirmed unit cost before sending.",
        }
    if max_safe is None or max_safe <= 0:
        return {
            "status": "max_safe_cost_missing",
            "delta": "",
            "blocked": "0",
            "message": "Max pay is missing, so this is a manual price-check row.",
        }
    delta = confirmed - max_safe
    if delta > 0.000001:
        return {
            "status": "confirmed_over_max_blocked",
            "delta": _num_text(delta),
            "blocked": "1",
            "message": f"Typed cost is GBP {_num_text(delta)} over Max pay. Snooze and recheck next week.",
        }
    return {
        "status": "confirmed_under_max",
        "delta": _num_text(delta),
        "blocked": "0",
        "message": "Typed cost is under Max pay.",
    }


def _price_chip(label: str, value: str, *, tone: str = "neutral") -> str:
    colors = {
        "good": ("#064e3b", "#d1fae5", "#10b981"),
        "caution": ("#713f12", "#fef3c7", "#f59e0b"),
        "bad": ("#7f1d1d", "#fee2e2", "#ef4444"),
        "neutral": ("#334155", "#f8fafc", "#cbd5e1"),
    }
    text_color, bg_color, border_color = colors.get(tone, colors["neutral"])
    return (
        f"<span style='display:inline-flex;align-items:center;gap:4px;min-height:19px;padding:2px 6px;"
        f"border:1px solid {border_color};border-radius:7px;background:{bg_color};color:{text_color};"
        "font-size:10px;font-weight:700;line-height:1.1;white-space:nowrap;'>"
        f"{html.escape(label)} {html.escape(value or '-')}</span>"
    )


def _price_status_tone(price_status: str, confirmed_status: str) -> str:
    if confirmed_status == "confirmed_over_max_blocked" or price_status == "over_max_snooze_candidate":
        return "bad"
    if price_status in {"caution_usual_paid_under_list", "caution_price_increased", "check_price", "max_safe_cost_missing"}:
        return "caution"
    if price_status in {"clean_price_ok", "list_cheaper_than_usual_paid"} or confirmed_status == "confirmed_under_max":
        return "good"
    return "neutral"


def _price_proof_chips_html(row_data: dict[str, object], confirmed_price: object = "") -> str:
    list_cost = _normalize_text(row_data.get("price_list_unit_cost_gbp", ""))
    usual_paid = _normalize_text(row_data.get("usual_paid_unit_cost_gbp", ""))
    max_safe = _first_non_blank(row_data.get("max_safe_unit_cost_gbp", ""), row_data.get("target_roi_max_cost_gbp", ""))
    price_status = _normalize_text(row_data.get("price_status", ""))
    price_status_message = _normalize_text(row_data.get("price_status_message", ""))
    confirmed_safety = _confirmed_price_safety(row_data, confirmed_price)
    display_status = confirmed_safety["status"] if _normalize_text(confirmed_price) else price_status
    tone = _price_status_tone(price_status, confirmed_safety["status"])
    if not any((list_cost, usual_paid, max_safe, price_status, confirmed_safety["status"])):
        return ""
    status_labels = {
        "clean_price_ok": "OK",
        "list_cheaper_than_usual_paid": "List cheaper",
        "caution_usual_paid_under_list": "Caution",
        "caution_price_increased": "Price up",
        "check_price": "Check price",
        "max_safe_cost_missing": "No max",
        "over_max_snooze_candidate": "Over max",
        "confirmed_price_missing": "Type price",
        "confirmed_under_max": "Typed OK",
        "confirmed_over_max_blocked": "Blocked",
    }
    details = [
        price_status_message,
        _normalize_text(row_data.get("price_proof_summary", "")),
        confirmed_safety["message"] if _normalize_text(confirmed_price) else "",
    ]
    help_symbol = _hover_badge_html(
        symbol="?",
        border_color={"good": "#10b981", "caution": "#f59e0b", "bad": "#ef4444"}.get(tone, "#cbd5e1"),
        text_color={"good": "#064e3b", "caution": "#713f12", "bad": "#7f1d1d"}.get(tone, "#334155"),
        heading="Price proof",
        details_text=" | ".join(part for part in details if _normalize_text(part)),
    )
    return (
        "<div style='margin-top:4px;display:flex;align-items:center;gap:5px;flex-wrap:wrap;'>"
        f"{_price_chip('List', 'GBP ' + list_cost if list_cost else '-', tone='neutral')}"
        f"{_price_chip('Usual', 'GBP ' + usual_paid if usual_paid else '-', tone='neutral')}"
        f"{_price_chip('Max pay', 'GBP ' + _normalize_text(max_safe) if max_safe else '-', tone='neutral')}"
        f"{_price_chip('Status', status_labels.get(display_status, display_status.replace('_', ' ') or '-'), tone=tone)}"
        f"{help_symbol}"
        "</div>"
    )


def _num_text(value: float | int) -> str:
    as_float = float(value)
    if as_float.is_integer():
        return str(int(as_float))
    return f"{as_float:.2f}".rstrip("0").rstrip(".")


def _reorder_row_identity(row_data: dict[str, object]) -> str:
    sku = _normalize_text(row_data.get("seller_sku", "")).upper()
    if sku:
        return f"sku::{sku}"
    asin = _normalize_text(row_data.get("asin", "")).upper()
    if asin:
        return f"asin::{asin}"
    supplier = _normalize_text(row_data.get("supplier_name", "")).lower()
    title = _normalize_text(row_data.get("title", "")).lower()
    return f"row::{supplier}::{title}"


def _reorder_widget_key(row_data: dict[str, object]) -> str:
    return _supplier_key_fragment(_reorder_row_identity(row_data))


def _apply_reorder_draft(
    row_data: dict[str, object],
    drafts: dict[str, dict[str, object]],
) -> tuple[str, dict[str, object]]:
    row_identity = _reorder_row_identity(row_data)
    draft = drafts.get(row_identity, {})
    if not draft:
        return row_identity, row_data
    merged = dict(row_data)
    for field in REORDER_DRAFT_FIELDS:
        if field in draft:
            merged[field] = draft[field]
    return row_identity, merged


def _extract_reorder_draft(row_data: dict[str, object]) -> dict[str, object]:
    return {field: row_data.get(field, "") for field in REORDER_DRAFT_FIELDS}


def _clear_reorder_drafts(
    session_state: object,
    rows: list[dict[str, object]],
) -> None:
    drafts = session_state.get("o_reorder_drafts", {})
    for row_data in rows:
        row_identity = _reorder_row_identity(row_data)
        drafts.pop(row_identity, None)
        row_key = _reorder_widget_key(row_data)
        for prefix in ("disc_", "drop_", "snze_", "qty_", "price_", "send_", "snooze_"):
            session_state.pop(f"{prefix}{row_key}", None)


def _render_reorder_supplier_cards(
    supplier_df: pd.DataFrame,
    *,
    supplier_label: str,
) -> pd.DataFrame:
    import streamlit as st

    edited_rows: list[dict[str, object]] = []
    drafts = st.session_state.setdefault("o_reorder_drafts", {})

    header_cols = st.columns(REORDER_COLUMN_WIDTHS, gap="small")
    for col, label in zip(header_cols, REORDER_HEADER_LABELS):
        col.markdown(f"<div style='font-size:12px;font-weight:700;color:#9ca3af;'>{label}</div>", unsafe_allow_html=True)

    for idx, (_, row) in enumerate(supplier_df.iterrows()):
        row_data = row.to_dict()
        _, row_data = _apply_reorder_draft(row_data, drafts)
        sku = _normalize_text(row_data.get("seller_sku", ""))
        row_key = _reorder_widget_key(row_data)

        with st.container():
            cols = st.columns(REORDER_COLUMN_WIDTHS, gap="small")

            with cols[0]:
                image_url = _normalize_text(row_data.get("main_image", ""))
                if image_url:
                    st.markdown(_image_frame_html(image_url, size=60), unsafe_allow_html=True)
                else:
                    st.markdown(
                        "<div style='width:60px;height:60px;border:1px solid #e5e7eb;border-radius:10px;background:#fff;"
                        "display:flex;align-items:center;justify-content:center;color:#9ca3af;font-size:10px;'>No image</div>",
                        unsafe_allow_html=True,
                    )

            with cols[1]:
                _render_copy_pair("SKU", sku, "ASIN", row_data.get("asin", ""), bottom_fallback="-")
            with cols[2]:
                backtest_brief = _backtest_brief_label(row_data)
                profit_badge = _profit_check_badge_html(row_data)
                st.markdown(
                    f"<div style='margin-top:2px;line-height:1.15;display:-webkit-box;-webkit-line-clamp:3;"
                    f"-webkit-box-orient:vertical;overflow:hidden;'>{_display_plain(row_data.get('title', '-'))}</div>"
                    f"<div style='font-size:11px;color:#475569;margin-top:3px;line-height:1.15;'>{_display_plain(backtest_brief, '')}</div>",
                    unsafe_allow_html=True,
                )
                if profit_badge:
                    st.markdown(profit_badge, unsafe_allow_html=True)
            with cols[3]:
                st.markdown(f"<div style='margin-top:4px;'>{_display_plain(row_data.get('qtys', '-'))}</div>", unsafe_allow_html=True)
            with cols[4]:
                _render_copy_pair("Supply", row_data.get("supply_code", ""), "Barcode", row_data.get("barcode", ""), top_fallback="-", bottom_fallback="-")
            with cols[5]:
                st.markdown(f"<div style='margin-top:4px;'>{_display_money(row_data.get('cpu', ''))}</div>", unsafe_allow_html=True)
            with cols[6]:
                st.markdown(
                    _display_stock_ordered_stack(row_data.get("stock", "0"), row_data.get("ordered_open", "0")),
                    unsafe_allow_html=True,
                )
            with cols[7]:
                roi = _display_plain(row_data.get("expected_forward_roi_pct", "0"), "0")
                st.markdown(f"<div style='margin-top:4px;'>{roi}%</div>", unsafe_allow_html=True)
            with cols[8]:
                st.markdown(f"<div style='margin-top:4px;'>{_display_plain(row_data.get('vlcity', '0'))}</div>", unsafe_allow_html=True)
            with cols[9]:
                st.markdown(f"<div style='margin-top:4px;'>{_display_plain(row_data.get('days', '0'))}</div>", unsafe_allow_html=True)
            with cols[10]:
                st.markdown(
                    f"<div style='margin-top:4px;font-weight:700;'>{_display_plain(row_data.get('recommend', '-'))}</div>",
                    unsafe_allow_html=True,
                )
            with cols[11]:
                st.markdown(f"<div style='margin-top:4px;'>{_display_plain(row_data.get('restk', '0'))}</div>", unsafe_allow_html=True)
            with cols[12]:
                disc_value = st.checkbox("Disc", value=_coerce_flag(row_data.get("disc", False)), key=f"disc_{row_key}", label_visibility="collapsed")
            with cols[13]:
                drop_value = st.checkbox("Drop", value=_coerce_flag(row_data.get("drop", False)), key=f"drop_{row_key}", label_visibility="collapsed")
            with cols[14]:
                snze_value = st.checkbox("Snze", value=_coerce_flag(row_data.get("snze", False)), key=f"snze_{row_key}", label_visibility="collapsed")
            with cols[15]:
                order_qty_value = st.text_input(
                    "Ordered",
                    value=_normalize_text(row_data.get("order_qty", "")),
                    key=f"qty_{row_key}",
                    label_visibility="collapsed",
                    placeholder=_derive_order_qty_unit_label(row_data),
                )
            with cols[16]:
                confirmed_price_value = st.text_input(
                    "Price",
                    value=_normalize_text(row_data.get("confirmed_price", "")),
                    key=f"price_{row_key}",
                    label_visibility="collapsed",
                )
            price_safety = _confirmed_price_safety(row_data, confirmed_price_value)
            price_blocked = _coerce_flag(price_safety.get("blocked", "0"))
            with cols[17]:
                send_value = st.checkbox(
                    "Send",
                    value=False if price_blocked else _coerce_flag(row_data.get("send", False)),
                    key=f"send_{row_key}",
                    label_visibility="collapsed",
                    disabled=price_blocked,
                )

            snooze_date_value = _normalize_text(row_data.get("snooze_date", ""))
            if snze_value:
                selected_snooze_date = _next_monday()
                if snooze_date_value:
                    try:
                        selected_snooze_date = date.fromisoformat(snooze_date_value)
                    except ValueError:
                        selected_snooze_date = _next_monday()
                snooze_date_value = st.date_input(
                    "Snooze Date",
                    value=selected_snooze_date,
                    key=f"snooze_{row_key}",
                ).isoformat()

            price_chips = _price_proof_chips_html(row_data, confirmed_price_value)
            if price_chips:
                st.markdown(price_chips, unsafe_allow_html=True)

            st.markdown("<div style='height:1px;background:#262b36;margin:0 0 4px 0;'></div>", unsafe_allow_html=True)

        row_data["send"] = False if price_blocked else send_value
        row_data["snze"] = snze_value
        row_data["disc"] = disc_value
        row_data["drop"] = drop_value
        row_data["order_qty"] = order_qty_value
        row_data["confirmed_price"] = confirmed_price_value
        row_data["confirmed_price_safety_status"] = price_safety.get("status", "")
        row_data["confirmed_vs_max_delta_gbp"] = price_safety.get("delta", "")
        row_data["snooze_date"] = snooze_date_value
        row_data["decision_note"] = ""
        row_data["row_status"] = _derive_row_status(pd.Series(row_data))
        drafts[_reorder_row_identity(row_data)] = _extract_reorder_draft(row_data)
        edited_rows.append(row_data)

    return pd.DataFrame(edited_rows)


def filter_reorder_rows(
    reorder_df: pd.DataFrame,
    *,
    include_wait: bool = False,
    include_snoozed: bool = False,
    include_held: bool = False,
    supplier_filter: str = "",
    search_text: str = "",
) -> pd.DataFrame:
    if reorder_df.empty:
        return reorder_df.copy()

    df = reorder_df.copy()
    df["_supplier_label"] = df["supplier_name"].map(_supplier_label)
    df["_suggested_action_norm"] = df["suggested_action"].map(lambda x: _normalize_text(x).lower())
    df["_row_status_norm"] = df["row_status"].map(lambda x: _normalize_text(x).lower())
    df["_price_status_norm"] = df.get("price_status", pd.Series("", index=df.index)).map(lambda x: _normalize_text(x).lower())
    df["_profit_verdict_norm"] = df.get("profit_verdict", pd.Series("", index=df.index)).map(lambda x: _normalize_text(x).lower())

    base_mask = df["_suggested_action_norm"].isin({"full_restock", "test_restock"})
    if include_wait:
        base_mask = base_mask | df["_suggested_action_norm"].eq("wait")
    if include_snoozed:
        base_mask = base_mask | df["_row_status_norm"].eq("snoozed")
    if include_held:
        base_mask = base_mask | df["_row_status_norm"].isin({"blocked", "watch"})

    df = df[base_mask].copy()
    if df.empty:
        return df.drop(columns=["_supplier_label", "_suggested_action_norm", "_row_status_norm", "_price_status_norm", "_profit_verdict_norm"], errors="ignore")

    supplier_filter_norm = _normalize_text(supplier_filter)
    if supplier_filter_norm and supplier_filter_norm != "All suppliers":
        df = df[df["_supplier_label"] == supplier_filter_norm].copy()

    query = _normalize_text(search_text).lower()
    if query:
        title_matches = df["title"].astype(str).str.lower().str.contains(query, na=False)
        sku_matches = df["seller_sku"].astype(str).str.lower().str.contains(query, na=False)
        asin_matches = df["asin"].astype(str).str.lower().str.contains(query, na=False)
        df = df[title_matches | sku_matches | asin_matches].copy()

    status_priority = {"ready": 0, "needs_price": 1, "needs_qty": 2, "snoozed": 3, "blocked": 4, "watch": 5}
    action_priority = {"full_restock": 0, "test_restock": 1, "wait": 2}
    price_priority = {
        "clean_price_ok": 0,
        "list_cheaper_than_usual_paid": 0,
        "caution_usual_paid_under_list": 1,
        "caution_price_increased": 1,
        "check_price": 2,
        "max_safe_cost_missing": 2,
        "over_max_snooze_candidate": 3,
    }
    df["_status_order"] = df["_row_status_norm"].map(lambda v: status_priority.get(v, 99))
    df["_action_order"] = df["_suggested_action_norm"].map(lambda v: action_priority.get(v, 99))
    df["_price_order"] = df.apply(
        lambda row: 4
        if _normalize_text(row.get("_profit_verdict_norm", "")) == "drop_review_only"
        else price_priority.get(_normalize_text(row.get("_price_status_norm", "")), 2),
        axis=1,
    )
    df = df.sort_values(
        by=["_supplier_label", "_price_order", "_status_order", "_action_order", "seller_sku"],
        ascending=[True, True, True, True, True],
        kind="stable",
    )

    return df.drop(
        columns=[
            "_suggested_action_norm",
            "_row_status_norm",
            "_price_status_norm",
            "_profit_verdict_norm",
            "_status_order",
            "_action_order",
            "_price_order",
        ],
        errors="ignore",
    )


def build_price_list_lookup_results(
    datasets: dict[str, pd.DataFrame],
    *,
    query: str,
    supplier_filter: str = "",
    limit: int = 50,
) -> pd.DataFrame:
    query_norm = _normalize_text(query).lower()
    supplier_filter_norm = _normalize_text(supplier_filter)
    rows: list[dict[str, str]] = []

    change_df = datasets.get("supplier_price_list_change_log_live", pd.DataFrame()).copy()
    if not change_df.empty:
        for _, row in change_df.iterrows():
            rows.append(
                {
                    "supplier": _normalize_text(row.get("supplier_name", "")),
                    "supply_code": _normalize_text(row.get("supplier_sku", "")),
                    "barcode": _normalize_text(row.get("barcode", "")),
                    "title": _normalize_text(row.get("title", "")),
                    "unit_cost_gbp": _first_non_blank(row.get("current_unit_cost_gbp", ""), row.get("previous_unit_cost_gbp", "")),
                    "pack_size": _first_non_blank(row.get("current_pack_size", ""), row.get("previous_pack_size", "")),
                    "pack_cost_gbp": _first_non_blank(row.get("current_pack_cost_gbp", ""), row.get("previous_pack_cost_gbp", "")),
                    "price_status": _normalize_text(row.get("change_status", "")),
                    "source": _first_non_blank(row.get("current_source_batch_id", ""), row.get("previous_source_batch_id", "")),
                }
            )

    truth_df = datasets.get("supplier_buy_cost_truth", pd.DataFrame()).copy()
    if not truth_df.empty:
        for _, row in truth_df.iterrows():
            rows.append(
                {
                    "supplier": _normalize_text(row.get("supplier_name", "")),
                    "supply_code": _normalize_text(row.get("supplier_sku", "")),
                    "barcode": _normalize_text(row.get("barcode", "")),
                    "title": _normalize_text(row.get("title", "")),
                    "unit_cost_gbp": _normalize_text(row.get("price_list_unit_cost_gbp", "")),
                    "pack_size": _normalize_text(row.get("price_list_pack_size", "")),
                    "pack_cost_gbp": _normalize_text(row.get("price_list_pack_cost_gbp", "")),
                    "price_status": _normalize_text(row.get("price_list_change_status", "")),
                    "source": _normalize_text(row.get("price_list_source_batch_id", "")),
                }
            )

    if not rows:
        return pd.DataFrame(columns=["supplier", "supply_code", "barcode", "title", "unit_cost_gbp", "pack_size", "pack_cost_gbp", "price_status", "source"])

    out = pd.DataFrame(rows).drop_duplicates(
        subset=["supplier", "supply_code", "barcode", "unit_cost_gbp", "pack_size", "source"],
        keep="first",
    )
    if supplier_filter_norm and supplier_filter_norm != "All suppliers":
        out = out[out["supplier"].map(_supplier_label).eq(supplier_filter_norm)].copy()
    if query_norm:
        haystack = (
            out["supplier"].astype(str)
            + " "
            + out["supply_code"].astype(str)
            + " "
            + out["barcode"].astype(str)
            + " "
            + out["title"].astype(str)
        ).str.lower()
        out = out[haystack.str.contains(re.escape(query_norm), na=False)].copy()
    if out.empty:
        return out
    return out.sort_values(by=["supplier", "supply_code", "barcode"], kind="stable").head(limit)


def _render_price_list_lookup_panel(datasets: dict[str, pd.DataFrame], *, supplier_filter: str) -> None:
    import streamlit as st

    with st.expander("Price-list lookup", expanded=False):
        lookup_query = st.text_input(
            "Search supplier code / barcode / SKU / title",
            value="",
            key="o_reorder_price_lookup",
        )
        lookup_df = build_price_list_lookup_results(
            datasets,
            query=lookup_query,
            supplier_filter=supplier_filter,
        )
        if lookup_query and lookup_df.empty:
            st.caption("No current local price-list match found.")
        elif not lookup_df.empty:
            st.dataframe(lookup_df, width="stretch", hide_index=True)
        else:
            st.caption("Type a supplier code, barcode, SKU, or title to check the local supplier price-list evidence.")


def submit_reorder_batch(
    *,
    root: Path | None = None,
    rows_df: pd.DataFrame,
    actor: str = "operator_ui",
    source_reference: str = "o_ui_batch",
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)

    applied_event_ids: list[str] = []
    applied_skus: list[str] = []
    skipped_rows: list[str] = []

    for _, row in rows_df.iterrows():
        if not _coerce_flag(row.get("send", False)):
            continue

        seller_sku = _normalize_text(row.get("seller_sku", ""))
        asin = _normalize_text(row.get("asin", ""))
        suggested_action = _normalize_text(row.get("suggested_action", ""))
        action = _default_decision_action(suggested_action)
        if _coerce_flag(row.get("snze", False)):
            action = "snooze"
        elif _coerce_flag(row.get("drop", False)):
            action = "skip"
        elif _coerce_flag(row.get("disc", False)):
            action = "wait"

        confirmed_qty = _order_qty_to_raw_event_qty(row.to_dict())
        confirmed_unit_cost = _positive_number_text(row.get("confirmed_price", ""))
        if action in {"approve_full_restock", "approve_test_restock"} and (
            confirmed_qty == "" or confirmed_unit_cost == ""
        ):
            skipped_rows.append(f"{seller_sku}:missing_qty_or_price")
            continue
        price_safety = _confirmed_price_safety(row.to_dict(), confirmed_unit_cost)
        if action in {"approve_full_restock", "approve_test_restock"} and _coerce_flag(price_safety.get("blocked", "0")):
            skipped_rows.append(f"{seller_sku}:confirmed_price_above_max_safe_cost")
            continue

        snooze_date = _normalize_text(row.get("snooze_date", ""))
        snooze_until = f"{snooze_date}T00:00:00Z" if (action == "snooze" and snooze_date) else ""
        decision_note = _normalize_text(row.get("decision_note", ""))
        if decision_note == "":
            decision_note = _normalize_text(row.get("recommendation_reason", ""))

        row_source_system = _normalize_text(row.get("source_system", ""))
        row_source_reference = _normalize_text(row.get("source_reference", ""))
        event_source_reference = _normalize_text(source_reference) or "o_ui_batch"
        if row_source_system or row_source_reference:
            event_source_reference = "|".join(
                part
                for part in [event_source_reference, row_source_system, row_source_reference]
                if _normalize_text(part) != ""
            )
        profit_verdict = _normalize_text(row.get("profit_verdict", ""))
        profit_proof_source = _normalize_text(row.get("profit_proof_source", ""))
        if action in {"approve_full_restock", "approve_test_restock"}:
            if profit_proof_source == "native_profit_proof" and profit_verdict in {"safe_to_review", "test_only"}:
                approval_profit_source = "native_profit_proof"
            elif profit_proof_source.startswith("legacy_sheet"):
                approval_profit_source = "legacy_sheet_profit_hint"
            else:
                approval_profit_source = "operator_override"
        else:
            approval_profit_source = profit_proof_source

        out_row = submit_decision_event(
            root=root_path,
            seller_sku=seller_sku,
            asin=asin,
            action=action,
            confirmed_unit_cost=confirmed_unit_cost,
            confirmed_qty=confirmed_qty,
            snooze_until_utc=snooze_until,
            decision_note=decision_note,
            actor=actor,
            cost_mode=_normalize_text(row.get("cost_mode", "")) or "live",
            source_reference=event_source_reference,
            profit_verdict=profit_verdict,
            profit_proof_source=approval_profit_source,
            profit_check_reference=_normalize_text(row.get("source_reference", "")),
            max_safe_unit_cost_gbp=_first_non_blank(row.get("max_safe_unit_cost_gbp", ""), row.get("target_roi_max_cost_gbp", "")),
            current_price_list_unit_cost_gbp=_normalize_text(row.get("price_list_unit_cost_gbp", "")),
            usual_paid_unit_cost_gbp=_normalize_text(row.get("usual_paid_unit_cost_gbp", "")),
            price_list_change_status=_normalize_text(row.get("price_list_change_status", "")),
            confirmed_price_safety_status=price_safety.get("status", ""),
            confirmed_vs_max_delta_gbp=price_safety.get("delta", ""),
            price_status=_normalize_text(row.get("price_status", "")),
            price_status_message=_normalize_text(row.get("price_status_message", "")),
            recommended_snooze_until_utc=_normalize_text(row.get("recommended_snooze_until_utc", "")),
        )
        applied_event_ids.append(_normalize_text(out_row.get("event_id", "")))
        applied_skus.append(seller_sku)

    return {
        "rows_seen": int(len(rows_df.index)),
        "rows_marked_send": int(rows_df.get("send", pd.Series(dtype=bool)).map(_coerce_flag).sum()) if not rows_df.empty else 0,
        "events_applied": len(applied_event_ids),
        "applied_event_ids": applied_event_ids,
        "applied_skus": applied_skus,
        "skipped_rows": skipped_rows,
    }


def submit_decision_event(
    *,
    root: Path | None = None,
    seller_sku: str,
    asin: str,
    action: str,
    confirmed_unit_cost: str = "",
    confirmed_qty: str = "",
    snooze_until_utc: str = "",
    decision_note: str = "",
    actor: str = "operator_ui",
    cost_mode: str = "live",
    source_reference: str = "o_ui",
    profit_verdict: str = "",
    profit_proof_source: str = "",
    profit_check_reference: str = "",
    max_safe_unit_cost_gbp: str = "",
    current_price_list_unit_cost_gbp: str = "",
    usual_paid_unit_cost_gbp: str = "",
    price_list_change_status: str = "",
    confirmed_price_safety_status: str = "",
    confirmed_vs_max_delta_gbp: str = "",
    price_status: str = "",
    price_status_message: str = "",
    recommended_snooze_until_utc: str = "",
) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)

    if action not in DECISION_ACTIONS:
        raise ValueError(f"unsupported decision action: {action}")
    event_id = f"o-ui-decision-{uuid.uuid4().hex[:12]}"
    row = {
        "event_utc": _utc_now_iso(),
        "event_id": event_id,
        "seller_sku": _normalize_text(seller_sku),
        "asin": _normalize_text(asin),
        "action": action,
        "confirmed_unit_cost": _normalize_text(confirmed_unit_cost),
        "confirmed_qty": _normalize_text(confirmed_qty),
        "snooze_until_utc": _normalize_text(snooze_until_utc),
        "decision_note": _normalize_text(decision_note),
        "actor": _normalize_text(actor),
        "cost_mode": _normalize_text(cost_mode) or "live",
        "source_reference": _normalize_text(source_reference) or "o_ui",
        "profit_verdict": _normalize_text(profit_verdict),
        "profit_proof_source": _normalize_text(profit_proof_source),
        "profit_check_reference": _normalize_text(profit_check_reference),
        "max_safe_unit_cost_gbp": _normalize_text(max_safe_unit_cost_gbp),
        "current_price_list_unit_cost_gbp": _normalize_text(current_price_list_unit_cost_gbp),
        "usual_paid_unit_cost_gbp": _normalize_text(usual_paid_unit_cost_gbp),
        "price_list_change_status": _normalize_text(price_list_change_status),
        "confirmed_price_safety_status": _normalize_text(confirmed_price_safety_status),
        "confirmed_vs_max_delta_gbp": _normalize_text(confirmed_vs_max_delta_gbp),
        "price_status": _normalize_text(price_status),
        "price_status_message": _normalize_text(price_status_message),
        "recommended_snooze_until_utc": _normalize_text(recommended_snooze_until_utc),
    }
    return _append_contract_row(root_path, "restock_decision_events", row)


def submit_receiving_event(
    *,
    root: Path | None = None,
    po_id: str,
    po_line_id: str,
    seller_sku: str,
    received_qty: str,
    warehouse_ref: str,
    event_source: str = "o_ui",
    note: str = "",
    actor: str = "operator_ui",
) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    row = {
        "event_utc": _utc_now_iso(),
        "event_id": f"o-ui-receive-{uuid.uuid4().hex[:12]}",
        "po_id": _normalize_text(po_id),
        "po_line_id": _normalize_text(po_line_id),
        "seller_sku": _normalize_text(seller_sku),
        "received_qty": _normalize_text(received_qty),
        "warehouse_ref": _normalize_text(warehouse_ref),
        "event_source": _normalize_text(event_source) or "o_ui",
        "note": _normalize_text(note),
        "actor": _normalize_text(actor),
    }
    return _append_contract_row(root_path, "receiving_events_inbox", row)


def submit_send_handoff_event(
    *,
    root: Path | None = None,
    po_id: str,
    po_line_id: str,
    seller_sku: str,
    handoff_qty: str,
    shipment_ref: str,
    handoff_status: str = "handoff_closed",
    note: str = "",
    actor: str = "operator_ui",
) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    if handoff_status not in HANDOFF_STATUSES:
        raise ValueError(f"unsupported handoff_status: {handoff_status}")
    row = {
        "event_utc": _utc_now_iso(),
        "event_id": f"o-ui-handoff-{uuid.uuid4().hex[:12]}",
        "po_id": _normalize_text(po_id),
        "po_line_id": _normalize_text(po_line_id),
        "seller_sku": _normalize_text(seller_sku),
        "handoff_qty": _normalize_text(handoff_qty),
        "shipment_ref": _normalize_text(shipment_ref),
        "handoff_status": handoff_status,
        "note": _normalize_text(note),
        "actor": _normalize_text(actor),
    }
    return _append_contract_row(root_path, "send_to_amazon_handoff_events", row)


def _next_monday(from_date: date | None = None) -> date:
    base = from_date or datetime.now(timezone.utc).date()
    days_ahead = (7 - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return date.fromordinal(base.toordinal() + days_ahead)


def _render_operator_theme_css() -> str:
    return """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(76, 154, 255, 0.13), transparent 280px),
            radial-gradient(circle at top right, rgba(23, 184, 144, 0.13), transparent 260px),
            linear-gradient(180deg, #f7fbff 0%, #f3f8f5 46%, #ffffff 100%);
        color: #172033;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stHeader"] {
        background: transparent;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] label,
    [data-testid="stCaptionContainer"],
    .stRadio label,
    .stSelectbox label,
    .stTextInput label {
        color: #334155;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #102033;
        letter-spacing: 0;
    }
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #d7e3ef;
        box-shadow: 1px 0 18px rgba(37, 99, 235, 0.07);
    }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #334155;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button {
        width: 100%;
        justify-content: flex-start;
        border-radius: 8px;
        min-height: 38px;
        font-weight: 650;
        background: #ffffff;
        border: 1px solid #d7e3ef;
        color: #172033;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover {
        border-color: #2f80ed;
        color: #0f4fb8;
        background: #eef6ff;
    }
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #1d72e8 0%, #13a388 100%);
        border: 1px solid #1d72e8;
        color: #ffffff;
        box-shadow: 0 8px 18px rgba(29, 114, 232, 0.16);
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        border-color: #0f766e;
        color: #ffffff;
        filter: brightness(1.02);
    }
    div[data-testid="stButton"] button[kind="primary"] p {
        color: #ffffff !important;
    }
    div[data-testid="stButton"] button[kind="secondary"],
    div[data-testid="stButton"] button:not([kind="primary"]) {
        background: #ffffff !important;
        border: 1px solid #b9d4ea !important;
        color: #172033 !important;
        box-shadow: 0 5px 14px rgba(38, 91, 150, 0.08);
    }
    div[data-testid="stButton"] button[kind="secondary"] p,
    div[data-testid="stButton"] button:not([kind="primary"]) p {
        color: #172033 !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover,
    div[data-testid="stButton"] button:not([kind="primary"]):hover {
        background: #eef7ff !important;
        border-color: #2f80ed !important;
        color: #0f4fb8 !important;
    }
    .o-shell-hero {
        border: 1px solid #cfe4f4;
        border-radius: 8px;
        background:
            linear-gradient(135deg, rgba(255, 255, 255, 0.96) 0%, rgba(238, 247, 255, 0.98) 55%, rgba(235, 249, 243, 0.98) 100%);
        padding: 14px 16px;
        margin: 0 0 14px 0;
        box-shadow: 0 10px 24px rgba(38, 91, 150, 0.08);
    }
    .o-shell-eyebrow {
        color: #475569;
        font-size: 12px;
        font-weight: 750;
        margin-bottom: 4px;
    }
    .o-shell-title {
        color: #0f172a;
        font-size: 24px;
        line-height: 1.22;
        font-weight: 800;
    }
    .o-shell-subtitle {
        color: #475569;
        font-size: 14px;
        line-height: 1.35;
        margin-top: 4px;
    }
    .o-metric-card {
        min-height: 128px;
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        padding: 17px 18px 15px 18px;
        margin: 0 0 16px 0;
        box-shadow: 0 8px 20px rgba(38, 91, 150, 0.07);
    }
    .o-metric-card.good {
        border-left: 5px solid #10a66a;
        background: linear-gradient(180deg, #ffffff 0%, #f1fbf6 100%);
    }
    .o-metric-card.warn {
        border-left: 5px solid #f2a900;
        background: linear-gradient(180deg, #ffffff 0%, #fff8df 100%);
    }
    .o-metric-card.stop {
        border-left: 5px solid #df4f42;
        background: linear-gradient(180deg, #ffffff 0%, #fff1ef 100%);
    }
    .o-metric-card.neutral {
        border-left: 5px solid #2f80ed;
        background: linear-gradient(180deg, #ffffff 0%, #f0f7ff 100%);
    }
    .o-metric-label {
        color: #475569;
        font-size: 12px;
        line-height: 1.25;
        font-weight: 750;
    }
    .o-metric-value {
        color: #0f172a;
        font-size: 28px;
        line-height: 1.15;
        font-weight: 850;
        margin-top: 8px;
    }
    .o-metric-note {
        color: #64748b;
        font-size: 12px;
        line-height: 1.3;
        margin-top: 8px;
    }
    .o-decision-card {
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: #ffffff;
        padding: 16px;
        margin: 8px 0 14px 0;
        box-shadow: 0 8px 20px rgba(38, 91, 150, 0.06);
    }
    .o-decision-card.good {
        background: #eefbf4;
        border-color: #9fe7bf;
    }
    .o-decision-card.warn {
        background: #fff7dc;
        border-color: #f5d46b;
    }
    .o-decision-card.neutral {
        background: #edf7ff;
        border-color: #b7daf7;
    }
    .o-decision-title {
        color: #0f172a;
        font-size: 18px;
        line-height: 1.25;
        font-weight: 800;
        margin-bottom: 6px;
    }
    .o-decision-body {
        color: #334155;
        font-size: 14px;
        line-height: 1.42;
    }
    .o-intake-work-header {
        border: 1px solid #cfe4f4;
        border-radius: 8px;
        background: linear-gradient(135deg, #f7fbff 0%, #fffaf0 100%);
        padding: 14px 16px;
        margin: 4px 0 14px 0;
        box-shadow: 0 8px 20px rgba(38, 91, 150, 0.06);
    }
    .o-intake-work-kicker {
        color: #2563eb;
        font-size: 12px;
        line-height: 1.2;
        font-weight: 850;
        margin-bottom: 5px;
    }
    .o-intake-work-title {
        color: #0f172a;
        font-size: 22px;
        line-height: 1.2;
        font-weight: 850;
    }
    .o-intake-work-body {
        color: #475569;
        font-size: 14px;
        line-height: 1.4;
        margin-top: 6px;
        max-width: 760px;
    }
    .o-intake-filter-title {
        color: #0f172a;
        font-size: 15px;
        line-height: 1.25;
        font-weight: 850;
        margin: 2px 0 4px 0;
    }
    .o-intake-filter-note {
        color: #64748b;
        font-size: 13px;
        line-height: 1.35;
        margin: 0 0 8px 0;
    }
    .o-intake-status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
        gap: 10px;
        margin: 10px 0 12px 0;
    }
    .o-intake-status-card {
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: #ffffff;
        padding: 10px 11px;
        min-height: 72px;
        box-shadow: 0 6px 16px rgba(38, 91, 150, 0.05);
    }
    .o-intake-status-card.good {
        border-left: 4px solid #10a66a;
    }
    .o-intake-status-card.warn {
        border-left: 4px solid #f2a900;
    }
    .o-intake-status-card.neutral {
        border-left: 4px solid #2f80ed;
    }
    .o-intake-status-label {
        color: #64748b;
        font-size: 12px;
        line-height: 1.2;
        font-weight: 850;
    }
    .o-intake-status-value {
        color: #0f172a;
        font-size: 20px;
        line-height: 1.15;
        font-weight: 850;
        margin-top: 6px;
        overflow-wrap: anywhere;
    }
    .o-intake-safe-note {
        border: 1px solid #b7e4ca;
        border-radius: 8px;
        background: #f0fbf5;
        color: #166534;
        font-size: 13px;
        line-height: 1.35;
        font-weight: 750;
        padding: 9px 11px;
        margin: 6px 0 12px 0;
    }
    .o-intake-summary-strip {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
        padding: 10px 12px;
        border: 1px solid #cfe4f4;
        border-radius: 8px;
        background: #f7fbff;
        box-shadow: 0 6px 16px rgba(38, 91, 150, 0.05);
        margin: 8px 0 14px 0;
    }
    .o-intake-summary-label {
        font-size: 12px;
        color: #2563eb;
        font-weight: 800;
    }
    .o-intake-summary-value {
        font-size: 13px;
        color: #0f172a;
        font-weight: 800;
    }
    .o-intake-summary-divider {
        color: #b7c7d8;
    }
    .o-intake-card {
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        padding: 16px;
        margin: 12px 0 10px 0;
        box-shadow: 0 8px 20px rgba(38, 91, 150, 0.07);
    }
    .o-intake-top {
        display: grid;
        grid-template-columns: 124px minmax(0, 1fr);
        gap: 16px;
        align-items: start;
    }
    .o-intake-image-placeholder {
        width: 112px;
        min-height: 112px;
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%);
        color: #64748b;
        display: flex;
        flex-direction: column;
        gap: 6px;
        align-items: center;
        justify-content: center;
        text-align: center;
        font-size: 12px;
        font-weight: 750;
        padding: 8px;
    }
    .o-intake-image-placeholder a {
        color: #0f4fb8;
        font-weight: 850;
        text-decoration: none;
    }
    .o-intake-image-frame {
        width: 112px;
        height: 112px;
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
    }
    .o-intake-image-frame img {
        width: 100%;
        height: 100%;
        object-fit: contain;
        display: block;
        background: #ffffff;
    }
    .o-intake-supplier {
        color: #2563eb;
        font-size: 12px;
        line-height: 1.2;
        font-weight: 850;
        margin-bottom: 5px;
    }
    .o-intake-title {
        color: #0f172a;
        font-size: 18px;
        line-height: 1.22;
        font-weight: 850;
        overflow-wrap: anywhere;
    }
    .o-intake-subline {
        color: #475569;
        font-size: 13px;
        line-height: 1.35;
        margin-top: 5px;
        overflow-wrap: anywhere;
    }
    .o-intake-facts {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
        gap: 8px;
        margin-top: 12px;
    }
    .o-intake-fact {
        border: 1px solid #dce8f3;
        border-radius: 8px;
        background: #f7fbff;
        padding: 8px 9px;
        min-height: 62px;
    }
    .o-intake-fact-label {
        color: #64748b;
        font-size: 11px;
        line-height: 1.2;
        font-weight: 850;
    }
    .o-intake-fact-value {
        color: #0f172a;
        font-size: 14px;
        line-height: 1.25;
        font-weight: 800;
        margin-top: 5px;
        overflow-wrap: anywhere;
    }
    .o-intake-notes {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-top: 12px;
    }
    .o-intake-note {
        border: 1px solid #dbeafe;
        border-radius: 8px;
        background: #f8fbff;
        padding: 10px 11px;
    }
    .o-intake-note.warn {
        border-color: #f5d46b;
        background: #fffaf0;
    }
    .o-intake-note-label {
        color: #334155;
        font-size: 12px;
        line-height: 1.2;
        font-weight: 850;
    }
    .o-intake-note-body {
        color: #475569;
        font-size: 13px;
        line-height: 1.35;
        margin-top: 5px;
        overflow-wrap: anywhere;
    }
    .o-intake-idline {
        color: #64748b;
        font-size: 12px;
        line-height: 1.35;
        margin-top: 10px;
        overflow-wrap: anywhere;
    }
    .o-intake-idline a {
        color: #0f4fb8;
        font-weight: 800;
        text-decoration: none;
    }
    .o-intake-action-title {
        color: #0f172a;
        font-size: 14px;
        line-height: 1.25;
        font-weight: 850;
        margin: 4px 0 6px 0;
    }
    .o-intake-choice-strip {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        border: 1px solid #cfe4f4;
        border-radius: 8px;
        background: #f7fbff;
        padding: 10px 12px;
        margin: 12px 0 10px 0;
    }
    .o-intake-choice-main {
        color: #0f172a;
        font-size: 14px;
        line-height: 1.3;
        font-weight: 850;
        margin-right: 6px;
    }
    .o-intake-choice-chip {
        border: 1px solid #d7e3ef;
        border-radius: 999px;
        background: #ffffff;
        color: #334155;
        font-size: 12px;
        line-height: 1.2;
        font-weight: 800;
        padding: 5px 8px;
    }
    .o-intake-choice-chip.good {
        border-color: #9fe7bf;
        background: #eefbf4;
        color: #166534;
    }
    .o-intake-choice-chip.warn {
        border-color: #f5d46b;
        background: #fff7dc;
        color: #78350f;
    }
    .o-intake-divider {
        height: 1px;
        background: #d7e3ef;
        margin: 12px 0 8px 0;
    }
    .o-intake-recent-title {
        color: #0f172a;
        font-size: 14px;
        line-height: 1.25;
        font-weight: 850;
        margin: 16px 0 8px 0;
    }
    @media (max-width: 760px) {
        .o-intake-card {
            padding: 12px;
        }
        .o-intake-top {
            grid-template-columns: 94px minmax(0, 1fr);
            gap: 12px;
        }
        .o-intake-image-placeholder,
        .o-intake-image-frame {
            width: 88px;
            height: 88px;
            min-height: 88px;
        }
        .o-intake-image-placeholder {
            font-size: 11px;
            padding: 6px;
        }
        .o-intake-title {
            font-size: 16px;
            line-height: 1.24;
        }
        .o-intake-facts {
            grid-template-columns: repeat(auto-fit, minmax(104px, 1fr));
            gap: 7px;
            margin-top: 10px;
        }
        .o-intake-fact {
            min-height: 56px;
            padding: 7px 8px;
        }
        .o-intake-notes {
            grid-template-columns: 1fr;
        }
    }
    @media (max-width: 520px) {
        .o-intake-top {
            grid-template-columns: 1fr;
        }
        .o-intake-image-placeholder,
        .o-intake-image-frame {
            width: 96px;
            height: 96px;
            min-height: 96px;
        }
        .o-intake-facts {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
    .o-small-list {
        margin: 8px 0 0 18px;
        color: #334155;
        font-size: 13px;
        line-height: 1.35;
    }
    .o-small-list li {
        margin: 0 0 4px 0;
    }
    .o-restock-card {
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        padding: 14px;
        margin: 10px 0;
        box-shadow: 0 8px 20px rgba(38, 91, 150, 0.07);
    }
    .o-restock-card.warn {
        border-left: 5px solid #f2a900;
    }
    .o-restock-card.good {
        border-left: 5px solid #10a66a;
    }
    .o-restock-card.neutral {
        border-left: 5px solid #2f80ed;
    }
    .o-restock-top {
        display: grid;
        grid-template-columns: 82px minmax(0, 1fr);
        gap: 12px;
        align-items: start;
    }
    .o-restock-title {
        color: #0f172a;
        font-size: 16px;
        line-height: 1.25;
        font-weight: 800;
        overflow-wrap: anywhere;
    }
    .o-restock-meta {
        color: #475569;
        font-size: 12px;
        line-height: 1.35;
        margin-top: 4px;
        overflow-wrap: anywhere;
    }
    .o-restock-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
        gap: 8px;
        margin-top: 12px;
    }
    .o-restock-fact {
        border: 1px solid #dce8f3;
        border-radius: 8px;
        background: #f7fbff;
        padding: 8px;
        min-height: 62px;
    }
    .o-restock-fact-label {
        color: #64748b;
        font-size: 11px;
        line-height: 1.2;
        font-weight: 800;
    }
    .o-restock-fact-value {
        color: #0f172a;
        font-size: 14px;
        line-height: 1.25;
        font-weight: 750;
        margin-top: 5px;
        overflow-wrap: anywhere;
    }
    .o-restock-proof {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 12px;
    }
    .o-restock-chip {
        border: 1px solid #cbd5e1;
        border-radius: 999px;
        background: #f8fafc;
        color: #334155;
        font-size: 12px;
        line-height: 1.2;
        font-weight: 700;
        padding: 5px 8px;
    }
    .o-restock-chip.warn {
        border-color: #fbbf24;
        background: #fffbeb;
        color: #78350f;
    }
    .o-restock-chip.good {
        border-color: #86efac;
        background: #f0fdf4;
        color: #166534;
    }
    .o-restock-blocker {
        margin-top: 12px;
        border-radius: 8px;
        background: #fff7ed;
        border: 1px solid #fed7aa;
        color: #7c2d12;
        padding: 9px 10px;
        font-size: 13px;
        line-height: 1.35;
    }
    .o-restock-next-action {
        margin-top: 10px;
        border-radius: 8px;
        background: #eef6ff;
        border: 1px solid #bfdbfe;
        color: #1e3a8a;
        padding: 9px 10px;
        font-size: 13px;
        line-height: 1.35;
        overflow-wrap: anywhere;
    }
    .o-restock-site-hero {
        border: 1px solid #c7e2f0;
        border-radius: 8px;
        background:
            linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(234, 247, 255, 0.98) 50%, rgba(232, 249, 241, 0.98) 100%);
        padding: 22px;
        margin: 8px 0 16px 0;
        box-shadow: 0 14px 30px rgba(38, 91, 150, 0.09);
    }
    .o-restock-site-title {
        color: #0f172a;
        font-size: 30px;
        line-height: 1.12;
        font-weight: 850;
        margin: 0;
    }
    .o-restock-site-copy {
        color: #334155;
        font-size: 15px;
        line-height: 1.42;
        max-width: 760px;
        margin-top: 8px;
    }
    .o-restock-path-card {
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
        padding: 18px;
        min-height: 132px;
        margin: 4px 0 18px 0;
        box-shadow: 0 8px 20px rgba(38, 91, 150, 0.07);
    }
    .o-restock-path-step {
        color: #2563eb;
        font-size: 12px;
        line-height: 1.2;
        font-weight: 850;
        margin-bottom: 8px;
    }
    .o-restock-path-title {
        color: #0f172a;
        font-size: 16px;
        line-height: 1.25;
        font-weight: 800;
    }
    .o-restock-path-body {
        color: #475569;
        font-size: 13px;
        line-height: 1.35;
        margin-top: 6px;
    }
    .o-restock-supplier-card {
        border: 1px solid #d7e3ef;
        border-radius: 8px;
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        padding: 14px;
        margin: 8px 0;
        box-shadow: 0 8px 20px rgba(38, 91, 150, 0.07);
    }
    .o-restock-supplier-card.ready {
        border-left: 5px solid #10a66a;
    }
    .o-restock-supplier-card.blocked {
        border-left: 5px solid #f2a900;
    }
    .o-restock-supplier-name {
        color: #0f172a;
        font-size: 17px;
        line-height: 1.2;
        font-weight: 850;
        overflow-wrap: anywhere;
    }
    .o-restock-supplier-stats {
        color: #334155;
        font-size: 13px;
        line-height: 1.35;
        margin-top: 7px;
    }
    .o-restock-supplier-note {
        color: #64748b;
        font-size: 12px;
        line-height: 1.35;
        margin-top: 7px;
    }
    @media (max-width: 700px) {
        .o-restock-top {
            grid-template-columns: 1fr;
        }
    }
    div[data-testid="stTextInput"] input,
    div[data-baseweb="input"] input,
    .stTextInput input {
        background: #ffffff !important;
        color: #172033 !important;
        caret-color: #172033 !important;
        border: 2px solid #9cccf2 !important;
        border-radius: 6px;
    }
    div[data-testid="stTextInput"] input:focus,
    div[data-baseweb="input"] input:focus,
    .stTextInput input:focus {
        border-color: #2f80ed !important;
        box-shadow: 0 0 0 2px rgba(47, 128, 237, 0.14) !important;
    }
    div[data-baseweb="select"] > div,
    div[data-testid="stExpander"] details,
    div[data-testid="stDataFrame"] {
        background: #ffffff;
        border-color: #d7e3ef;
        color: #172033;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input,
    div[data-testid="stExpander"] summary,
    div[data-testid="stExpander"] p {
        color: #172033;
    }
    .o-hover-wrap {
        position: relative;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }
    .o-hover-panel {
        position: absolute;
        left: 0;
        top: 24px;
        min-width: 320px;
        max-width: 460px;
        max-height: 220px;
        overflow-y: auto;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid #334155;
        background: linear-gradient(180deg, #0f172a 0%, #0b1220 100%);
        box-shadow: 0 12px 28px rgba(2, 6, 23, 0.65);
        color: #e2e8f0;
        font-size: 12px;
        line-height: 1.28;
        z-index: 1000;
        opacity: 0;
        visibility: hidden;
        transform: translateY(4px);
        transition: opacity 0.14s ease, transform 0.14s ease, visibility 0.14s ease;
        pointer-events: none;
        white-space: normal;
    }
    .o-hover-wrap:hover .o-hover-panel,
    .o-hover-wrap:focus .o-hover-panel,
    .o-hover-wrap:focus-within .o-hover-panel {
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
        pointer-events: auto;
    }
    .o-hover-title {
        color: #93c5fd;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .o-hover-list {
        margin: 0;
        padding-left: 14px;
    }
    .o-hover-list li {
        margin: 0 0 3px 0;
    }
    </style>
    """


def _render_inline_notice(message: str) -> str:
    return (
        "<div style='display:inline-flex;align-items:center;gap:8px;"
        "padding:6px 10px;border:1px solid #38bdf8;border-radius:999px;"
        "background:rgba(14,165,233,0.08);color:#dbeafe;font:500 12px sans-serif;'>"
        "<span style='width:7px;height:7px;border-radius:999px;background:#38bdf8;display:inline-block;'></span>"
        f"{html.escape(message)}"
        "</div>"
    )


def _operator_metric_card_html(label: str, value: object, note: str = "", tone: str = "neutral") -> str:
    safe_tone = tone if tone in {"good", "warn", "stop", "neutral"} else "neutral"
    return (
        f"<div class='o-metric-card {safe_tone}'>"
        f"<div class='o-metric-label'>{html.escape(_normalize_text(label))}</div>"
        f"<div class='o-metric-value'>{html.escape(_normalize_text(value))}</div>"
        f"<div class='o-metric-note'>{html.escape(_normalize_text(note))}</div>"
        "</div>"
    )


def _operator_decision_card_html(title: str, body: str, tone: str = "neutral") -> str:
    safe_tone = tone if tone in {"good", "warn", "neutral"} else "neutral"
    return (
        f"<div class='o-decision-card {safe_tone}'>"
        f"<div class='o-decision-title'>{html.escape(_normalize_text(title))}</div>"
        f"<div class='o-decision-body'>{html.escape(_normalize_text(body))}</div>"
        "</div>"
    )


def _operator_shell_header_html(page_label: str, page_description: str) -> str:
    return (
        "<div class='o-shell-hero'>"
        "<div class='o-shell-eyebrow'>SellerOne local operator UI</div>"
        f"<div class='o-shell-title'>{html.escape(_normalize_text(page_label))}</div>"
        f"<div class='o-shell-subtitle'>{html.escape(_normalize_text(page_description))}</div>"
        "</div>"
    )


def _norm_series(df: pd.DataFrame, column: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=str)
    if column not in df.columns:
        return pd.Series([""] * len(df.index), index=df.index, dtype=str)
    return df[column].map(lambda value: _normalize_text(value).lower())


def _text_series(df: pd.DataFrame, column: str) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=str)
    if column not in df.columns:
        return pd.Series([""] * len(df.index), index=df.index, dtype=str)
    return df[column].map(_normalize_text)


def _contains_any(df: pd.DataFrame, columns: list[str], tokens: set[str]) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(False, index=df.index)
    token_pattern = "|".join(re.escape(token) for token in sorted(tokens) if token)
    if token_pattern == "":
        return mask
    for column in columns:
        if column in df.columns:
            mask = mask | _norm_series(df, column).str.contains(token_pattern, na=False, regex=True)
    return mask


def _count_truthy_or_text_rows(df: pd.DataFrame, columns: list[str]) -> int:
    if df.empty:
        return 0
    mask = pd.Series(False, index=df.index)
    emptyish = {"", "0", "0.0", "false", "no", "none", "nan", "ok", "ready", "clear"}
    for column in columns:
        if column not in df.columns:
            continue
        values = _norm_series(df, column)
        mask = mask | values.map(lambda value: value not in emptyish)
    return int(mask.sum())


def _sum_numeric_column(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def _supplier_count(df: pd.DataFrame) -> int:
    if df.empty or "supplier_name" not in df.columns:
        return 0
    labels = df["supplier_name"].map(_supplier_label)
    labels = labels[labels.map(lambda value: _normalize_text(value) not in {"", "(Unknown supplier)"})]
    return int(labels.nunique())


def _supplier_count_for_mask(df: pd.DataFrame, mask: pd.Series) -> int:
    if df.empty or "supplier_name" not in df.columns or mask.empty:
        return 0
    subset = df[mask].copy()
    return _supplier_count(subset)


def _restock_ready_mask(review_df: pd.DataFrame) -> pd.Series:
    if review_df.empty:
        return pd.Series(dtype=bool)
    row_status = _norm_series(review_df, "row_status")
    block_reason = _norm_series(review_df, "action_block_reason")
    ready_status = row_status.isin(
        {
            "ready",
            "ready_for_review",
            "review_ready",
            "order_ready",
            "clean",
            "ok",
        }
    )
    return ready_status & block_reason.eq("")


def _restock_blocked_mask(review_df: pd.DataFrame) -> pd.Series:
    if review_df.empty:
        return pd.Series(dtype=bool)
    block_columns = [
        "row_status",
        "action_block_reason",
        "supplier_match_state",
        "supplier_stock_state",
        "supplier_cost_proof_state",
        "market_price_proof_state",
        "fee_proof_state",
        "refund_proof_state",
        "inbound_cost_proof_state",
        "pack_moq_proof_state",
        "supplier_order_viability_state",
        "operator_decision_state",
    ]
    return _contains_any(
        review_df,
        block_columns,
        {
            "blocked",
            "block",
            "hold",
            "held",
            "missing",
            "stale",
            "not_ready",
            "not ready",
            "not_proven",
            "not proven",
            "unsafe",
            "needs",
        },
    )


def _top_restock_blocker_items(review_df: pd.DataFrame, limit: int = 5) -> list[tuple[str, int]]:
    if review_df.empty:
        return []
    reason_columns = [
        "action_block_reason",
        "row_status",
        "supplier_match_state",
        "supplier_stock_state",
        "supplier_cost_proof_state",
        "market_price_proof_state",
        "fee_proof_state",
        "refund_proof_state",
        "inbound_cost_proof_state",
        "pack_moq_proof_state",
        "supplier_order_viability_state",
    ]
    emptyish = {"", "ok", "ready", "clean", "0", "false", "no", "none"}
    counts: dict[str, int] = {}
    for column in reason_columns:
        if column not in review_df.columns:
            continue
        for value in _text_series(review_df, column).tolist():
            normalized = _normalize_text(value)
            if normalized.lower() in emptyish:
                continue
            label = " ".join(normalized.replace("_", " ").split())
            counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _build_today_operator_summary(datasets: dict[str, pd.DataFrame]) -> dict[str, object]:
    review_df = datasets.get("restock_session_review_live", pd.DataFrame()).copy()
    product_df = datasets.get("product_db_operator_view", pd.DataFrame()).copy()
    holds_df = datasets.get("purchase_order_draft_holds", pd.DataFrame()).copy()
    receiving_holds_df = datasets.get("receiving_event_holds", pd.DataFrame()).copy()
    handoff_holds_df = datasets.get("send_to_amazon_handoff_holds", pd.DataFrame()).copy()
    brand_queue_df = datasets.get("brand_approval_queue_live", pd.DataFrame()).copy()
    listing_drafts_df = datasets.get("amazon_listing_drafts_live", pd.DataFrame()).copy()

    summary_warning = ""
    try:
        reorder_df = build_reorder_input_df(datasets)
    except Exception as exc:
        reorder_df = pd.DataFrame()
        summary_warning = f"Reorder summary could not be built: {exc}"

    ready_mask = _restock_ready_mask(review_df)
    blocked_mask = _restock_blocked_mask(review_df)
    urgent_mask = pd.Series(dtype=bool)
    if not reorder_df.empty:
        urgent_mask = _norm_series(reorder_df, "suggested_action").isin({"full_restock", "test_restock"})

    po_review_df = build_po_draft_review_df(datasets)
    po_count = int(po_review_df["po_id"].nunique()) if not po_review_df.empty and "po_id" in po_review_df.columns else 0
    po_units = int(_sum_numeric_column(po_review_df, "ordered_qty")) if not po_review_df.empty else 0
    po_value = _sum_numeric_column(po_review_df, "line_value_gbp") if not po_review_df.empty else 0.0

    status_columns = [
        column
        for column in ("product_status", "operator_status", "lifecycle_state", "status", "listing_status", "product_state")
        if column in product_df.columns
    ]
    product_live = int(_contains_any(product_df, status_columns, {"live", "active"}).sum()) if status_columns else 0
    product_dropped = int(_contains_any(product_df, status_columns, {"dropped", "discontinued", "inactive"}).sum()) if status_columns else 0
    stale_columns = [column for column in product_df.columns if "stale" in column.lower() or "freshness" in column.lower()]
    issue_columns = [
        column
        for column in product_df.columns
        if "issue" in column.lower() or "block" in column.lower() or "hold" in column.lower()
    ]
    product_stale = _count_truthy_or_text_rows(product_df, stale_columns)
    product_issues = _count_truthy_or_text_rows(product_df, issue_columns)

    listing_ready = 0
    if not listing_drafts_df.empty and "draft_status" in listing_drafts_df.columns:
        listing_ready = int(
            _norm_series(listing_drafts_df, "draft_status").isin(
                {"ready_for_listing_approval", "ready_for_amazon_preview", "ready_for_live_submit"}
            ).sum()
        )

    business_decisions_waiting = (
        po_count
        + int(len(holds_df.index))
        + int(len(receiving_holds_df.index))
        + int(len(handoff_holds_df.index))
        + int(len(brand_queue_df.index))
        + listing_ready
    )

    return {
        "summary_warning": summary_warning,
        "restock_rows": int(len(review_df.index)),
        "restock_ready_rows": int(ready_mask.sum()) if not ready_mask.empty else 0,
        "restock_blocked_rows": int(blocked_mask.sum()) if not blocked_mask.empty else 0,
        "restock_suppliers": _supplier_count(review_df),
        "restock_ready_suppliers": _supplier_count_for_mask(review_df, ready_mask),
        "urgent_restock_candidates": int(urgent_mask.sum()) if not urgent_mask.empty else 0,
        "urgent_restock_suppliers": _supplier_count_for_mask(reorder_df, urgent_mask),
        "top_blockers": _top_restock_blocker_items(review_df),
        "po_count": po_count,
        "po_lines": int(len(po_review_df.index)),
        "po_units": po_units,
        "po_value": po_value,
        "po_holds": int(len(holds_df.index)),
        "receiving_holds": int(len(receiving_holds_df.index)),
        "handoff_holds": int(len(handoff_holds_df.index)),
        "brand_queue_rows": int(len(brand_queue_df.index)),
        "listing_ready_rows": listing_ready,
        "business_decisions_waiting": int(business_decisions_waiting),
        "product_rows": int(len(product_df.index)),
        "product_live": product_live,
        "product_dropped": product_dropped,
        "product_stale": product_stale,
        "product_issues": product_issues,
    }


def _render_operator_sidebar(
    *,
    active_page_route: str,
    label_by_route: dict[str, str],
    navigate_to,
) -> None:
    import streamlit as st

    st.sidebar.title("SellerOne")
    st.sidebar.caption("Operator UI")
    for section_title, section_caption, routes in OPERATOR_NAV_SECTIONS:
        st.sidebar.markdown(f"**{section_title}**")
        st.sidebar.caption(section_caption)
        for route in routes:
            label = OPERATOR_NAV_LABELS.get(route, label_by_route.get(route, route.replace("_", " ").title()))
            clicked = st.sidebar.button(
                label,
                key=f"o_sidebar_nav_{route}",
                type="primary" if route == active_page_route else "secondary",
                use_container_width=True,
                help=OPERATOR_PAGE_DESCRIPTIONS.get(route, ""),
            )
            if clicked:
                navigate_to(route)
        st.sidebar.markdown("")
    st.sidebar.caption("No page takes a business action unless Luke presses that page's save or record button.")


def _render_today_page(datasets: dict[str, pd.DataFrame], navigate_to) -> None:
    import streamlit as st

    summary = _build_today_operator_summary(datasets)
    warning = _normalize_text(summary.get("summary_warning", ""))
    if warning:
        st.warning(warning)

    ready_rows = int(summary["restock_ready_rows"])
    blocked_rows = int(summary["restock_blocked_rows"])
    restock_rows = int(summary["restock_rows"])
    urgent_candidates = int(summary["urgent_restock_candidates"])
    po_count = int(summary["po_count"])

    if ready_rows > 0:
        decision_title = "Start with Restocking"
        decision_body = (
            f"{ready_rows} row"
            f"{'' if ready_rows == 1 else 's'} currently look ready for manual review. "
            "The screen still waits for Luke to choose any action."
        )
        decision_tone = "good"
        target_route = "restock_session"
        target_label = "Open Restocking"
    elif restock_rows > 0:
        decision_title = "Restocking is the useful workflow, but buying is not clean yet"
        decision_body = (
            f"{blocked_rows} row"
            f"{'' if blocked_rows == 1 else 's'} are blocked from a clean buy. "
            "Use Restocking to inspect supplier proof and blocker reasons before trusting any order."
        )
        decision_tone = "warn"
        target_route = "restock_session"
        target_label = "Open Restocking"
    elif po_count > 0:
        decision_title = "Review local draft orders"
        decision_body = (
            f"{po_count} local draft PO"
            f"{'' if po_count == 1 else 's'} are available. "
            "They are still local drafts and do not count as approved purchases."
        )
        decision_tone = "neutral"
        target_route = "po_drafts"
        target_label = "Open Orders and P&L"
    else:
        decision_title = "No clean buying task is ready"
        decision_body = "The UI can still show products and proof, but there is no automatic business action to take from Today."
        decision_tone = "neutral"
        target_route = "product_db"
        target_label = "Open Products"

    st.markdown(_operator_decision_card_html(decision_title, decision_body, decision_tone), unsafe_allow_html=True)
    action_cols = st.columns([1.1, 1.1, 3.2], gap="small")
    if action_cols[0].button(target_label, type="primary", key="o_today_open_primary"):
        navigate_to(target_route)
    if action_cols[1].button("Open Products", key="o_today_open_products"):
        navigate_to("product_db")
    action_cols[2].caption("Today is read-only. It does not approve buys, create POs, write Sheets, change prices, or touch scanner queues.")

    metric_cols = st.columns(4, gap="medium")
    metric_cols[0].markdown(
        _operator_metric_card_html(
            "Urgent restock candidates",
            urgent_candidates,
            f"{summary['urgent_restock_suppliers']} supplier group(s)",
            "neutral",
        ),
        unsafe_allow_html=True,
    )
    metric_cols[1].markdown(
        _operator_metric_card_html(
            "Order-ready rows",
            ready_rows,
            f"{summary['restock_ready_suppliers']} supplier group(s) with ready proof",
            "good" if ready_rows else "warn",
        ),
        unsafe_allow_html=True,
    )
    metric_cols[2].markdown(
        _operator_metric_card_html(
            "Blocked rows",
            blocked_rows,
            f"{restock_rows} total restock session row(s)",
            "warn" if blocked_rows else "good",
        ),
        unsafe_allow_html=True,
    )
    metric_cols[3].markdown(
        _operator_metric_card_html(
            "Business decisions waiting",
            summary["business_decisions_waiting"],
            "Drafts, holds, listing setup, and approvals",
            "neutral",
        ),
        unsafe_allow_html=True,
    )

    st.markdown("### Restocking blockers")
    blocker_items = summary.get("top_blockers", [])
    if blocker_items:
        list_html = "<ul class='o-small-list'>"
        for reason, count in blocker_items:
            list_html += f"<li>{html.escape(reason)}: {int(count)}</li>"
        list_html += "</ul>"
        st.markdown(list_html, unsafe_allow_html=True)
    else:
        st.success("No restocking blockers are visible in the current local proof files.")

    lower_cols = st.columns(3, gap="small")
    lower_cols[0].markdown(
        _operator_metric_card_html(
            "Products",
            summary["product_rows"],
            f"{summary['product_live']} live, {summary['product_dropped']} dropped",
            "neutral",
        ),
        unsafe_allow_html=True,
    )
    lower_cols[1].markdown(
        _operator_metric_card_html(
            "Product proof issues",
            summary["product_issues"],
            f"{summary['product_stale']} stale/freshness flags",
            "warn" if int(summary["product_issues"]) or int(summary["product_stale"]) else "good",
        ),
        unsafe_allow_html=True,
    )
    lower_cols[2].markdown(
        _operator_metric_card_html(
            "Local draft POs",
            summary["po_count"],
            f"{summary['po_lines']} line(s), {summary['po_units']} unit(s), GBP {_num_text(float(summary['po_value']))}",
            "neutral",
        ),
        unsafe_allow_html=True,
    )

    with st.expander("Proof/Admin stays available"):
        st.caption("Scanner queue, repricer tracker, raw decision log, and proof tables are kept under Proof / Admin in the left navigation.")
        admin_cols = st.columns([1.2, 1.2, 3.2], gap="small")
        if admin_cols[0].button("Open Proof/Admin", key="o_today_open_proof_admin"):
            navigate_to("price_list_queue")
        if admin_cols[1].button("Open Decision Log", key="o_today_open_decision_log"):
            navigate_to("decision_log")
        admin_cols[2].caption("These screens show maintenance proof. They are not part of Luke's normal restocking path.")


def _read_price_list_queue_df(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_QUEUE_DASHBOARD_PATH
    if not path.exists():
        return pd.DataFrame(columns=PRICE_LIST_QUEUE_COLUMNS)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=PRICE_LIST_QUEUE_COLUMNS)
    for column in PRICE_LIST_QUEUE_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[list(PRICE_LIST_QUEUE_COLUMNS)]


def _read_price_list_next_action_report(root: Path | None = None) -> str:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_NEXT_ACTION_REPORT_PATH
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _read_price_list_handoff_preview_df(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_HANDOFF_PREVIEW_PATH
    columns = list(F061_HANDOFF_PREVIEW_COLUMNS)
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df[columns]


SCANNER_TIMEOUT_POLICY_FLAG_COLUMNS = (
    "enabled",
    "cost_change_resets_flag",
    "source_change_resets_flag",
    "manual_review_required_flag",
)


def _read_scanner_timeout_policy_df(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    return read_timeout_policy_df(root=root_path, create_if_missing=True)


def _scanner_timeout_policy_editor_df(root: Path | None = None) -> pd.DataFrame:
    policy = _read_scanner_timeout_policy_df(root)
    display = policy_display_df(policy)
    for column in SCANNER_TIMEOUT_POLICY_FLAG_COLUMNS:
        if column in display.columns:
            display[column] = display[column].map(lambda value: _normalize_text(value) == "1")
    return display


def save_scanner_timeout_policy_from_ui(
    root: Path | None,
    edited_df: pd.DataFrame,
    *,
    observed_utc: str | None = None,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    policy_df = policy_df_from_display(edited_df)
    written = write_timeout_policy_df(root_path, policy_df, observed_utc=observed_utc or _utc_now_iso())
    return {
        "status": "success",
        "policy_rows": int(len(written.index)),
        "policy_path": str(timeout_policy_path(root_path)),
    }


def reset_scanner_timeout_policy_from_ui(
    root: Path | None,
    *,
    observed_utc: str | None = None,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    written = reset_timeout_policy_to_defaults(root_path, observed_utc=observed_utc or _utc_now_iso())
    return {
        "status": "success",
        "policy_rows": int(len(written.index)),
        "policy_path": str(timeout_policy_path(root_path)),
    }


def _latest_price_list_handoff_preview(root: Path | None = None) -> dict[str, str]:
    preview = _read_price_list_handoff_preview_df(root)
    if preview.empty:
        return {}
    work = preview.copy()
    work["_built"] = work["built_at_utc"].map(_normalize_text)
    work = work.sort_values("_built", ascending=False, kind="stable")
    return {column: _normalize_text(work.iloc[0].get(column, "")) for column in F061_HANDOFF_PREVIEW_COLUMNS}


def _latest_price_list_live_status(root: Path | None = None) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_LIVE_STATUS_PATH
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return {}
    if df.empty:
        return {}
    return {str(column): _normalize_text(df.iloc[-1].get(column, "")) for column in df.columns}


def _price_list_active_run_counts(root: Path | None = None, active_f061_run_id: str = "") -> dict[str, int]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_ACTIVE_RUN_PATH
    if not path.exists():
        return {"total": 0, "pending": 0, "done": 0, "held": 0}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return {"total": 0, "pending": 0, "done": 0, "held": 0}
    active_run_id = _normalize_text(active_f061_run_id)
    if active_run_id and "run_id" in df.columns:
        df = df[df["run_id"].map(_normalize_text).eq(active_run_id)].copy()
    if df.empty:
        return {"total": 0, "pending": 0, "done": 0, "held": 0}
    status_col = "scan_status" if "scan_status" in df.columns else "row_status"
    if status_col not in df.columns:
        return {"total": int(len(df.index)), "pending": 0, "done": int(len(df.index)), "held": 0}
    statuses = df[status_col].map(_normalize_text).str.lower()
    pending = int(statuses.eq("pending").sum())
    held = int(statuses.eq("held").sum())
    total = int(len(df.index))
    return {"total": total, "pending": pending, "done": max(total - pending - held, 0), "held": held}


def _price_list_login_counts(root: Path | None = None, active_f061_run_id: str = "") -> dict[str, int]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_ACTIVE_RUN_PATH
    empty = {"login": 0, "bbp_login": 0, "dashboard_login": 0, "login_pending": 0, "login_running": 0}
    active_keys: set[str] = set()
    if not path.exists():
        df = pd.DataFrame()
    else:
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()
    active_run_id = _normalize_text(active_f061_run_id)
    if not df.empty and active_run_id and "run_id" in df.columns:
        df = df[df["run_id"].map(_normalize_text).eq(active_run_id)].copy()

    if df.empty:
        status = pd.Series(dtype=str)
        pending_mask = pd.Series(dtype=bool)
        running_mask = pd.Series(dtype=bool)
        dashboard_mask = pd.Series(dtype=bool)
        bbp_mask = pd.Series(dtype=bool)
        login_mask = pd.Series(dtype=bool)
    else:
        if {"supplier_id", "run_id", "row_key"}.issubset(df.columns):
            for _, row in df.iterrows():
                active_keys.add(
                    "|".join(
                        [
                            _normalize_text(row.get("supplier_id", "")).lower(),
                            _normalize_text(row.get("run_id", "")),
                            _normalize_text(row.get("row_key", "")),
                        ]
                    )
                )
        status = df.get("scan_status", pd.Series([""] * len(df.index), index=df.index)).map(
            lambda value: _normalize_text(value).lower()
        )
        block_reason = df.get("completion_block_reason", pd.Series([""] * len(df.index), index=df.index)).map(
            lambda value: _normalize_text(value).lower()
        )
        pending_mask = status.eq("login_backtrack_pending")
        running_mask = status.eq("login_backtrack_running")
        dashboard_mask = (
            status.eq("dashboard_yes_no_unresolved")
            | block_reason.str.contains("dashboard_yes_no", regex=False)
            | block_reason.str.contains("amazon_dashboard_login_required", regex=False)
        )
        bbp_mask = (
            block_reason.str.contains("bbp_login_required", regex=False)
            | block_reason.eq("login_required")
            | (pending_mask & ~dashboard_mask)
            | (running_mask & ~dashboard_mask)
        )
        login_mask = pending_mask | running_mask | bbp_mask | dashboard_mask

    ledger_bbp = 0
    ledger_dashboard = 0
    ledger_path = root_path / get_f_output_contract("f_login_backtrack_evidence_live").rel_path
    if ledger_path.exists():
        try:
            ledger = pd.read_csv(ledger_path, dtype=str).fillna("")
        except pd.errors.EmptyDataError:
            ledger = pd.DataFrame()
        if not ledger.empty:
            run_col = "original_run_id" if "original_run_id" in ledger.columns else "run_id"
            if active_run_id and run_col in ledger.columns:
                ledger = ledger[ledger[run_col].map(_normalize_text).eq(active_run_id)].copy()
            if not ledger.empty:
                for column in ["candidate_id", "backtrack_observed_utc", "backtrack_attempt_number"]:
                    if column not in ledger.columns:
                        ledger[column] = ""
                ledger = ledger[ledger["candidate_id"].map(_normalize_text).ne("")].copy()
                if not ledger.empty:
                    ledger["_sort_ts"] = pd.to_datetime(
                        ledger["backtrack_observed_utc"].map(_normalize_text),
                        errors="coerce",
                    )
                    ledger["_attempt"] = pd.to_numeric(
                        ledger["backtrack_attempt_number"].map(_normalize_text),
                        errors="coerce",
                    ).fillna(0)
                    ledger = (
                        ledger.sort_values(["_sort_ts", "_attempt"], ascending=[True, True], kind="stable")
                        .groupby(["supplier_id", run_col, "candidate_id"], dropna=False)
                        .tail(1)
                        .drop(columns=["_sort_ts", "_attempt"], errors="ignore")
                    )
                if "merged_into_candidate_flag" in ledger.columns:
                    ledger = ledger[ledger["merged_into_candidate_flag"].map(_normalize_text).ne("1")].copy()
                if {"supplier_id", run_col, "candidate_id"}.issubset(ledger.columns) and active_keys:
                    ledger = ledger[
                        ~ledger.apply(
                            lambda row: "|".join(
                                [
                                    _normalize_text(row.get("supplier_id", "")).lower(),
                                    _normalize_text(row.get(run_col, "")),
                                    _normalize_text(row.get("candidate_id", "")),
                                ]
                            )
                            in active_keys,
                            axis=1,
                        )
                    ].copy()
                statuses = ledger.get("backtrack_status", pd.Series([""] * len(ledger.index), index=ledger.index)).map(
                    lambda value: _normalize_text(value).lower()
                )
                ledger_dashboard = int(
                    statuses.isin({"missing_dashboard_yes_no", "dashboard_yes_no_unresolved"}).sum()
                )
                ledger_bbp = int(statuses.eq("blocked_login").sum())

    active_login = int(login_mask.sum())
    active_bbp = int(bbp_mask.sum())
    active_dashboard = int(dashboard_mask.sum())
    return {
        "login": active_login + ledger_bbp + ledger_dashboard,
        "bbp_login": active_bbp + ledger_bbp,
        "dashboard_login": active_dashboard + ledger_dashboard,
        "login_pending": int(pending_mask.sum()),
        "login_running": int(running_mask.sum()),
    }


def _latest_price_list_run_state(root: Path | None = None, active_f061_run_id: str = "") -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_RUN_STATE_PATH
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return {}
    if df.empty:
        return {}
    active_run_id = _normalize_text(active_f061_run_id)
    if active_run_id and "run_id" in df.columns:
        matched = df[df["run_id"].map(_normalize_text).eq(active_run_id)].copy()
        if not matched.empty:
            df = matched
    return {str(column): _normalize_text(df.iloc[-1].get(column, "")) for column in df.columns}


def _price_list_live_result_counts(root: Path | None, active_f061_run_id: str) -> dict[str, int]:
    run_state = _latest_price_list_run_state(root, active_f061_run_id)
    done_rows = _price_list_int(run_state.get("done_rows", "0"))
    failed_rows = _price_list_int(run_state.get("failed_rows", "0"))
    pending_rows = _price_list_int(run_state.get("pending_rows", "0"))
    held_rows = _price_list_int(run_state.get("held_rows", "0"))
    pass_rows = max(done_rows - failed_rows - held_rows, 0)

    rescan_rows = 0
    active_run_id = _normalize_text(active_f061_run_id)
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_SCREENING_STATE_PATH
    if active_run_id and path.exists():
        try:
            df = pd.read_csv(path, dtype=str, usecols=lambda col: col in {"run_id", "row_status", "pf"}).fillna("")
        except (pd.errors.EmptyDataError, ValueError):
            df = pd.DataFrame()
        if not df.empty and "run_id" in df.columns:
            run_rows = df[df["run_id"].map(_normalize_text).eq(active_run_id)].copy()
            if not run_rows.empty:
                pf = run_rows.get("pf", pd.Series([""] * len(run_rows.index), index=run_rows.index)).map(
                    lambda value: _normalize_text(value).upper()
                )
                statuses = run_rows.get("row_status", pd.Series([""] * len(run_rows.index), index=run_rows.index)).map(
                    lambda value: _normalize_text(value).lower()
                )
                pass_rows = int((pf.eq("PASS") | statuses.eq("pass")).sum())
                failed_rows = int((pf.eq("FAIL") | statuses.isin(["timeout", "fail", "failed"])).sum())
                rescan_rows = int(
                    (pf.eq("RESCAN") | statuses.isin(["rescan", "re_scan", "retry", "retry_pending"])).sum()
                )

    return {
        "pass": pass_rows,
        "fail": failed_rows,
        "rescan": rescan_rows,
        "done": done_rows,
        "pending": pending_rows,
        "held": held_rows,
    }


def _price_list_recovery_counts(root: Path | None, supplier_id: str) -> dict[str, int]:
    supplier = _normalize_text(supplier_id)
    if not supplier:
        return {"legacy_done": 0, "legacy_pass": 0, "legacy_fail": 0, "legacy_pending": 0, "matched_pending": 0}
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_RECOVERY_PROGRESS_PATH
    if not path.exists():
        return {"legacy_done": 0, "legacy_pass": 0, "legacy_fail": 0, "legacy_pending": 0, "matched_pending": 0}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return {"legacy_done": 0, "legacy_pass": 0, "legacy_fail": 0, "legacy_pending": 0, "matched_pending": 0}
    if df.empty or "supplier_id" not in df.columns:
        return {"legacy_done": 0, "legacy_pass": 0, "legacy_fail": 0, "legacy_pending": 0, "matched_pending": 0}
    matched = df[df["supplier_id"].map(_normalize_text).eq(supplier)]
    if matched.empty:
        return {"legacy_done": 0, "legacy_pass": 0, "legacy_fail": 0, "legacy_pending": 0, "matched_pending": 0}
    row = matched.iloc[-1]
    legacy_done = _price_list_int(row.get("legacy_done_rows", "0"))
    legacy_fail = _price_list_int(row.get("legacy_failed_rows", "0"))
    return {
        "legacy_done": legacy_done,
        "legacy_pass": max(legacy_done - legacy_fail, 0),
        "legacy_fail": legacy_fail,
        "legacy_pending": _price_list_int(row.get("legacy_pending_rows", "0")),
        "matched_pending": _price_list_int(row.get("pending_matched_rows", "0")),
    }


def _latest_price_list_live_event(root: Path | None = None) -> str:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_LIVE_EVENTS_PATH
    if not path.exists():
        return ""
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    except OSError:
        return ""
    if len(lines) <= 1:
        return ""
    return lines[-1]


def _price_list_child_status(root: Path | None = None) -> str:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_CHILD_STATUS_PATH
    status = ""
    if not path.exists():
        status = ""
    else:
        try:
            status = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            status = ""

    newest_output_mtime = 0.0
    for rel_path in (PRICE_LIST_CHILD_STDOUT_PATH, PRICE_LIST_CHILD_STDERR_PATH):
        output_path = root_path / rel_path
        try:
            if output_path.exists():
                newest_output_mtime = max(newest_output_mtime, float(output_path.stat().st_mtime))
        except OSError:
            continue
    if newest_output_mtime <= 0:
        return status

    age_seconds = max(datetime.now(timezone.utc).timestamp() - newest_output_mtime, 0.0)
    output_note = f"last_output={_format_price_list_duration(age_seconds)} ago"
    if age_seconds >= 1800:
        output_note = f"{output_note}|warning=no_child_output_30m"
    return f"{status}|{output_note}" if status else output_note


def _price_list_manager_mode_state(root: Path | None = None) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_MANAGER_MODE_STATE_PATH
    if not path.exists():
        return {}
    try:
        line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return {}
    return _price_list_parse_state_line(line)


def _price_list_supervisor_state(root: Path | None = None) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_SUPERVISOR_STATE_PATH
    if not path.exists():
        return {"state": "missing", "age_label": "-", "badge_state": "missing"}
    try:
        line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        mtime = path.stat().st_mtime
    except (OSError, IndexError):
        return {"state": "unreadable", "age_label": "-", "badge_state": "stale"}
    parts = _price_list_parse_state_line(line)
    age_seconds = max(datetime.now(timezone.utc).timestamp() - float(mtime), 0.0)
    parts["age_seconds"] = f"{age_seconds:.1f}"
    parts["age_label"] = _format_price_list_duration(age_seconds)
    state = _normalize_text(parts.get("state", "")).lower()
    if state == "ok" and age_seconds < 120:
        badge_state = "ok"
    elif state == "restart_manager" and age_seconds < 300:
        badge_state = "recovering"
    else:
        badge_state = "stale"
    parts["badge_state"] = badge_state
    return parts


def _price_list_parse_state_line(line: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for item in [part.strip() for part in _normalize_text(line).split("|") if part.strip()]:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[_normalize_text(key).lstrip("\ufeff")] = _normalize_text(value)
    return parts


def _price_list_parse_key_value_text(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for item in text.replace("\r", "\n").replace("|", "\n").splitlines():
        clean = _normalize_text(item)
        if not clean or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        parts[_normalize_text(key).lower().lstrip("\ufeff")] = _normalize_text(value)
    return parts


def _price_list_auth_state(root: Path | None = None) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    state_path = root_path / PRICE_LIST_BROWSER_VISIBILITY_STATE_PATH
    request_path = root_path / PRICE_LIST_LOGIN_MODE_REQUEST_PATH
    parts: dict[str, str] = {}
    if state_path.exists():
        try:
            parts = _price_list_parse_state_line(state_path.read_text(encoding="utf-8", errors="replace").splitlines()[0])
        except (OSError, IndexError):
            parts = {}
    request_parts: dict[str, str] = {}
    if request_path.exists():
        try:
            request_parts = _price_list_parse_key_value_text(request_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            request_parts = {}
    request_status = _normalize_text(request_parts.get("status", "requested" if request_path.exists() else "")).lower()
    request_active = request_path.exists() and request_status not in PRICE_LIST_LOGIN_MODE_INACTIVE_STATUSES
    reason = _normalize_text(parts.get("reason", "")).lower()
    if reason in {"child_started_minimized", "child_started_hidden"}:
        parts["auth_state"] = ""
    parts["login_mode_request_exists"] = "1" if request_active else "0"
    parts["login_mode_request_status"] = request_status
    parts["login_mode_request_path"] = str(request_path)
    return parts


def _append_price_list_live_event(
    root_path: Path,
    *,
    event_type: str,
    supplier_id: str,
    f061_run_id: str,
    status: str,
    notes: str,
    observed_utc: str,
) -> None:
    path = root_path / PRICE_LIST_LIVE_EVENTS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    row_values = {
        "event_utc": observed_utc,
        "observed_utc": observed_utc,
        "cycle_run_id": "operator_ui",
        "run_id": "operator_ui",
        "event_type": event_type,
        "supplier_id": supplier_id,
        "active_supplier_id": supplier_id,
        "f061_run_id": f061_run_id,
        "active_f061_run_id": f061_run_id,
        "status": status,
        "rows": "0",
        "chunk_rows": "0",
        "notes": notes,
        "detail": notes,
    }
    if path.exists():
        try:
            with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
                header = next(csv.reader(fh), [])
        except (OSError, StopIteration):
            header = []
    else:
        header = []
    if not header:
        header = list(LIVE_CYCLE_EVENT_COLUMNS)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([row_values.get(column, "") for column in header])


def request_price_list_login_mode_from_ui(
    root: Path | None,
    *,
    supplier_id: str,
    run_id: str,
    hold_seconds: int = 900,
    observed_utc: str | None = None,
) -> dict[str, str]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    observed = observed_utc or _utc_now_iso()
    clean_supplier = _normalize_text(supplier_id)
    clean_run = _normalize_text(run_id)
    if not clean_supplier:
        return {"status": "blocked", "block_reason": "supplier_id_missing"}
    if not clean_run:
        return {"status": "blocked", "block_reason": "run_id_missing"}
    request_path = root_path / PRICE_LIST_LOGIN_MODE_REQUEST_PATH
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        "\n".join(
            [
                f"requested_utc={observed}",
                "requested_by=operator_ui",
                "mode=login_recovery",
                f"supplier_id={clean_supplier}",
                f"run_id={clean_run}",
                "status=requested",
                f"hold_seconds={max(int(hold_seconds), 1)}",
                "reason=operator_login_button",
                "",
            ]
        ),
        encoding="ascii",
        newline="\n",
    )
    _append_price_list_live_event(
        root_path,
        event_type="login_mode_requested",
        supplier_id=clean_supplier,
        f061_run_id=clean_run,
        status="requested",
        notes=f"request_path={request_path};hold_seconds={max(int(hold_seconds), 1)}",
        observed_utc=observed,
    )
    return {
        "status": "requested",
        "request_path": str(request_path),
        "supplier_id": clean_supplier,
        "run_id": clean_run,
        "hold_seconds": str(max(int(hold_seconds), 1)),
        "requested_utc": observed,
    }


def _price_list_login_button_state(
    *,
    login_rows: int,
    auth_state: str,
    request_exists: bool,
    request_status: str = "",
) -> dict[str, object]:
    auth = _normalize_text(auth_state).upper()
    if request_exists:
        if auth == "AMAZON_DASHBOARD_LOGIN_REQUIRED":
            return {
                "label": "YES/NO Login",
                "disabled": False,
                "badge_state": "dashboard_required",
                "button_type": "primary",
            }
        if auth == "BBP_LOGIN_REQUIRED":
            return {
                "label": "BBP Login",
                "disabled": False,
                "badge_state": "bbp_required",
                "button_type": "primary",
            }
        if auth == "LOGIN_REQUIRED":
            return {
                "label": "Login",
                "disabled": False,
                "badge_state": "required",
                "button_type": "primary",
            }
        if int(login_rows) > 0 and auth == "LOGGED_IN":
            return {
                "label": "Catching Up",
                "disabled": True,
                "badge_state": "catching_up",
                "button_type": "secondary",
            }
        return {
            "label": "Login Requested",
            "disabled": True,
            "badge_state": "requested",
            "button_type": "secondary",
        }
    if auth == "AMAZON_DASHBOARD_LOGIN_REQUIRED":
        return {
            "label": "YES/NO Login",
            "disabled": False,
            "badge_state": "dashboard_required",
            "button_type": "primary",
        }
    if auth == "BBP_LOGIN_REQUIRED":
        return {
            "label": "BBP Login",
            "disabled": False,
            "badge_state": "bbp_required",
            "button_type": "primary",
        }
    if login_rows > 0 and auth == "LOGGED_IN":
        return {
            "label": "Catching Up",
            "disabled": True,
            "badge_state": "catching_up",
            "button_type": "secondary",
        }
    if login_rows > 0 or auth == "LOGIN_REQUIRED":
        return {
            "label": "Login",
            "disabled": False,
            "badge_state": "required",
            "button_type": "primary",
        }
    return {
        "label": "Login",
        "disabled": True,
        "badge_state": "logged_in" if auth == "LOGGED_IN" else "idle",
        "button_type": "secondary",
    }


def _price_list_login_badge_html(
    button_state: dict[str, object],
    *,
    login_rows: int,
    auth_state: str,
    manager_mode: str = "",
) -> str:
    badge_state = _normalize_text(button_state.get("badge_state", "idle"))
    mode = _normalize_text(manager_mode)
    palette = {
        "required": ("#7f1d1d", "#fee2e2", "#ef4444", "LOGIN REQUIRED"),
        "bbp_required": ("#7f1d1d", "#fee2e2", "#ef4444", "BBP LOGIN REQUIRED"),
        "dashboard_required": ("#854d0e", "#fef9c3", "#eab308", "YES/NO LOGIN REQUIRED"),
        "requested": ("#78350f", "#fef3c7", "#f59e0b", "LOGIN REQUESTED"),
        "catching_up": ("#164e63", "#cffafe", "#06b6d4", "CATCHING UP"),
        "logged_in": ("#14532d", "#dcfce7", "#22c55e", "LOGGED IN"),
        "idle": ("#374151", "#f3f4f6", "#9ca3af", "LOGIN"),
    }
    if mode == "Catching Up":
        badge_state = "catching_up"
    elif mode == "Scanning Hidden":
        badge_state = "logged_in"
    elif mode in {"Login Window Open", "Restarting Scanner"}:
        badge_state = "requested"
    color, background, dot, label = palette.get(badge_state, palette["idle"])
    if mode:
        label = mode.upper()
    detail = f"{int(login_rows)} rows"
    auth = _normalize_text(auth_state).upper()
    if auth:
        detail = f"{detail} | {auth}"
    return (
        "<span style='display:inline-flex;align-items:center;gap:6px;"
        f"color:{color};background:{background};border:1px solid {dot};"
        "padding:4px 9px;border-radius:999px;font-size:12px;font-weight:800;'>"
        f"<span style='width:7px;height:7px;border-radius:999px;background:{dot};display:inline-block;'></span>"
        f"{html.escape(label)}"
        f"<span style='font-weight:600;opacity:0.8;'>{html.escape(detail)}</span>"
        "</span>"
    )


def _price_list_supervisor_badge_html(supervisor_state: dict[str, str]) -> str:
    badge_state = _normalize_text(supervisor_state.get("badge_state", "missing")).lower()
    palette = {
        "ok": ("#14532d", "#dcfce7", "#22c55e", "SUPERVISOR OK"),
        "recovering": ("#854d0e", "#fef9c3", "#eab308", "SUPERVISOR RECOVERING"),
        "stale": ("#7f1d1d", "#fee2e2", "#ef4444", "SUPERVISOR STALE"),
        "missing": ("#7f1d1d", "#fee2e2", "#ef4444", "SUPERVISOR MISSING"),
    }
    color, background, dot, label = palette.get(badge_state, palette["missing"])
    state = _normalize_text(supervisor_state.get("state", "-")) or "-"
    age = _normalize_text(supervisor_state.get("age_label", "-")) or "-"
    reason = _normalize_text(supervisor_state.get("reason", ""))
    detail = f"{state} | {age} ago"
    if reason:
        detail = f"{detail} | {reason}"
    return (
        "<span style='display:inline-flex;align-items:center;gap:6px;"
        f"color:{color};background:{background};border:1px solid {dot};"
        "padding:4px 9px;border-radius:999px;font-size:12px;font-weight:800;'>"
        f"<span style='width:7px;height:7px;border-radius:999px;background:{dot};display:inline-block;'></span>"
        f"{html.escape(label)}"
        f"<span style='font-weight:600;opacity:0.8;'>{html.escape(detail)}</span>"
        "</span>"
    )


def _price_list_live_progress_total(root: Path | None, active_f061_run_id: str) -> int:
    active_run_id = _normalize_text(active_f061_run_id)
    if not active_run_id:
        return 0
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_LIVE_EVENTS_PATH
    if not path.exists():
        return 0
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return 0
    run_col = "active_f061_run_id" if "active_f061_run_id" in df.columns else "f061_run_id"
    detail_col = "detail" if "detail" in df.columns else "notes"
    chunk_col = "chunk_rows" if "chunk_rows" in df.columns else "rows"
    if df.empty or run_col not in df.columns:
        return 0
    work = df[df[run_col].map(_normalize_text).eq(active_run_id)].copy()
    if work.empty or detail_col not in work.columns:
        return 0
    best_total = 0
    for _, row in work.iterrows():
        detail = _normalize_text(row.get(detail_col, ""))
        if "pending_after=" not in detail:
            continue
        pending_after = _price_list_int(detail.split("pending_after=", 1)[1].split()[0])
        chunk_rows = _price_list_int(row.get(chunk_col, "0"))
        best_total = max(best_total, pending_after + chunk_rows)
    return best_total


def _format_price_list_duration(seconds: float) -> str:
    if seconds <= 0:
        return "-"
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 48:
        return f"{hours}h {remaining_minutes}m" if remaining_minutes else f"{hours}h"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days}d {remaining_hours}h" if remaining_hours else f"{days}d"


def _price_list_live_eta(root: Path | None, active_f061_run_id: str, pending_rows: int) -> dict[str, object]:
    active_run_id = _normalize_text(active_f061_run_id)
    if not active_run_id or pending_rows <= 0:
        return {"rows_per_hour": 0.0, "eta_label": "-", "sample_rows": 0}
    root_path = Path(root) if root is not None else get_o_path_contract().root
    path = root_path / PRICE_LIST_LIVE_EVENTS_PATH
    if not path.exists():
        return {"rows_per_hour": 0.0, "eta_label": "-", "sample_rows": 0}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return {"rows_per_hour": 0.0, "eta_label": "-", "sample_rows": 0}
    run_col = "active_f061_run_id" if "active_f061_run_id" in df.columns else "f061_run_id"
    detail_col = "detail" if "detail" in df.columns else "notes"
    chunk_col = "chunk_rows" if "chunk_rows" in df.columns else "rows"
    time_col = "observed_utc" if "observed_utc" in df.columns else "event_utc"
    if df.empty or not {run_col, detail_col, time_col}.issubset(df.columns):
        return {"rows_per_hour": 0.0, "eta_label": "-", "sample_rows": 0}

    work = df[df[run_col].map(_normalize_text).eq(active_run_id)].copy()
    if work.empty:
        return {"rows_per_hour": 0.0, "eta_label": "-", "sample_rows": 0}
    rows: list[dict[str, object]] = []
    for _, row in work.iterrows():
        detail = _normalize_text(row.get(detail_col, ""))
        if "pending_after=" not in detail:
            continue
        event_time = pd.to_datetime(_normalize_text(row.get(time_col, "")), errors="coerce", utc=True)
        if pd.isna(event_time):
            continue
        pending_after = _price_list_int(detail.split("pending_after=", 1)[1].split()[0])
        chunk_rows = _price_list_int(row.get(chunk_col, "0"))
        rows.append(
            {
                "event_time": event_time.to_pydatetime(),
                "pending_after": pending_after,
                "total_at_event": pending_after + chunk_rows,
            }
        )
    if len(rows) < 2:
        return {"rows_per_hour": 0.0, "eta_label": "-", "sample_rows": 0}

    rows = sorted(rows, key=lambda item: item["event_time"])
    first = rows[0]
    last = rows[-1]
    elapsed_seconds = (last["event_time"] - first["event_time"]).total_seconds()
    processed_rows = int(first["total_at_event"]) - int(last["pending_after"])
    if elapsed_seconds <= 0 or processed_rows <= 0:
        return {"rows_per_hour": 0.0, "eta_label": "-", "sample_rows": processed_rows}
    rows_per_second = processed_rows / elapsed_seconds
    rows_per_hour = rows_per_second * 3600
    eta_seconds = pending_rows / rows_per_second
    return {
        "rows_per_hour": rows_per_hour,
        "eta_label": _format_price_list_duration(eta_seconds),
        "sample_rows": processed_rows,
    }


def _price_list_int(value: object) -> int:
    raw = _normalize_text(value)
    if raw == "":
        return 0
    try:
        return int(float(raw.replace(",", "")))
    except ValueError:
        return 0


def build_price_list_queue_summary(queue_df: pd.DataFrame) -> dict[str, int]:
    if queue_df.empty:
        return {
            "total_suppliers": 0,
            "active": 0,
            "manual_missing": 0,
            "blocked": 0,
            "web_unprocessed": 0,
            "web_pass": 0,
            "web_fail": 0,
            "web_rescan": 0,
        }
    states = queue_df["queue_state"].map(_normalize_text)
    return {
        "total_suppliers": int(len(queue_df.index)),
        "active": int(states.isin(["Active", "Recommended"]).sum()),
        "manual_missing": int((states == "Needs Manual File").sum()),
        "blocked": int((states == "Blocked").sum()),
        "web_unprocessed": int(queue_df["web_unprocessed"].map(_price_list_int).sum()),
        "web_pass": int(queue_df["web_pass"].map(_price_list_int).sum()),
        "web_fail": int(queue_df["web_fail"].map(_price_list_int).sum()),
        "web_rescan": int(queue_df["web_rescan"].map(_price_list_int).sum()),
    }


def apply_price_list_queue_control(
    *,
    root: Path | None,
    supplier_id: str,
    control_state: str,
    priority_rank: str = "",
    reason: str = "",
    observed_utc: str | None = None,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    observed = observed_utc or _utc_now_iso()
    control_summary = set_queue_control(
        supplier_id=supplier_id,
        control_state=control_state,
        priority_rank=priority_rank,
        reason=reason,
        root=root_path,
        updated_at_utc=observed,
    )
    decision_summary = build_next_action(root=root_path, observed_utc=observed)
    report_summary = build_next_action_report(root=root_path, built_at_utc=observed)
    handoff_summary: dict[str, object] = {"status": "not_staged", "reason": "no_selected_supplier"}
    if _normalize_text(decision_summary.get("selected_supplier_id", "")):
        handoff_summary = stage_f061_handoff(root=root_path, built_at_utc=observed)
    dashboard_summary = build_status_dashboard(root=root_path, built_at_utc=observed)
    return {
        "status": "success",
        "control": control_summary,
        "decision": decision_summary,
        "report": report_summary,
        "handoff": handoff_summary,
        "dashboard": dashboard_summary,
    }


def apply_price_list_handoff_approval(
    *,
    root: Path | None,
    supplier_id: str,
    batch_id: str,
    approval_state: str,
    reason: str = "",
    observed_utc: str | None = None,
) -> dict[str, object]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    observed = observed_utc or _utc_now_iso()
    approval_summary = set_f061_handoff_approval(
        supplier_id=supplier_id,
        batch_id=batch_id,
        approval_state=approval_state,
        approved_by="operator_ui",
        reason=reason,
        root=root_path,
        approved_at_utc=observed,
    )
    handoff_summary = stage_f061_handoff(root=root_path, built_at_utc=observed)
    dashboard_summary = build_status_dashboard(root=root_path, built_at_utc=observed)
    return {
        "status": "success",
        "approval": approval_summary,
        "handoff": handoff_summary,
        "dashboard": dashboard_summary,
    }


def _price_list_queue_badge(state: str) -> str:
    normalized = _normalize_text(state)
    palette = {
        "Active": ("#064e3b", "#d1fae5", "#10b981"),
        "Recommended": ("#064e3b", "#d1fae5", "#10b981"),
        "Ready": ("#064e3b", "#d1fae5", "#10b981"),
        "Approved": ("#064e3b", "#d1fae5", "#10b981"),
        "Auto Armed": ("#064e3b", "#d1fae5", "#10b981"),
        "Prioritised": ("#581c87", "#f3e8ff", "#a855f7"),
        "Paused": ("#374151", "#f3f4f6", "#6b7280"),
        "Needs Manual File": ("#7f1d1d", "#fee2e2", "#ef4444"),
        "Blocked": ("#7c2d12", "#ffedd5", "#f97316"),
        "Ready When Due": ("#1e3a8a", "#dbeafe", "#3b82f6"),
        "Queued": ("#334155", "#e2e8f0", "#64748b"),
        "Complete": ("#365314", "#ecfccb", "#84cc16"),
    }
    color, background, dot = palette.get(normalized, ("#334155", "#e2e8f0", "#64748b"))
    return (
        "<span style='display:inline-flex;align-items:center;gap:6px;"
        f"color:{color};background:{background};border:1px solid {dot};"
        "padding:3px 8px;border-radius:999px;font-size:12px;font-weight:700;'>"
        f"<span style='width:7px;height:7px;border-radius:999px;background:{dot};display:inline-block;'></span>"
        f"{html.escape(normalized or '-')}"
        "</span>"
    )


def _price_list_queue_metric_html(label: str, value: int | str, color: str = "#e2e8f0") -> str:
    return (
        "<div class='fpm-queue-metric'>"
        f"<div class='fpm-queue-metric-label'>{html.escape(label)}</div>"
        f"<div class='fpm-queue-metric-value' style='color:{color};'>{html.escape(str(value))}</div>"
        "</div>"
    )


def _price_list_queue_chip_html(label: str, value: str) -> str:
    return (
        "<span class='fpm-queue-chip'>"
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(value or '-')}</strong>"
        "</span>"
    )


def _render_scanner_timeout_settings(root_path: Path) -> None:
    import streamlit as st

    with st.expander("Scanner Timeout Settings", expanded=False):
        editor_df = _scanner_timeout_policy_editor_df(root_path)
        st.caption(
            "These settings are editable policy records only. Phase 23A keeps live scanner timeout and skip decisions unchanged."
        )
        edited_df = st.data_editor(
            editor_df,
            hide_index=True,
            width="stretch",
            key="scanner_timeout_policy_editor",
            disabled=["fail_code", "meaning", "stage", "recommendation", "updated_at_utc"],
            column_config={
                "enabled": st.column_config.CheckboxColumn("Enabled"),
                "timeout_mode": st.column_config.SelectboxColumn(
                    "Timeout mode",
                    options=sorted(ALLOWED_TIMEOUT_MODES),
                ),
                "cost_change_resets_flag": st.column_config.CheckboxColumn("Cost reset"),
                "source_change_resets_flag": st.column_config.CheckboxColumn("Source reset"),
                "manual_review_required_flag": st.column_config.CheckboxColumn("Manual"),
            },
        )
        button_cols = st.columns([1, 1, 5], gap="small")
        save_clicked = button_cols[0].button("Save", key="scanner_timeout_policy_save")
        reset_clicked = button_cols[1].button("Reset Defaults", key="scanner_timeout_policy_reset")
        if save_clicked:
            try:
                result = save_scanner_timeout_policy_from_ui(root_path, edited_df)
                st.success(f"Saved {result['policy_rows']} timeout policy rows.")
                st.rerun()
            except Exception as exc:
                st.error(f"Timeout policy save failed: {exc}")
        if reset_clicked:
            try:
                result = reset_scanner_timeout_policy_from_ui(root_path)
                st.success(f"Reset {result['policy_rows']} timeout policy rows to current legacy defaults.")
                st.rerun()
            except Exception as exc:
                st.error(f"Timeout policy reset failed: {exc}")


def _render_price_list_queue_tab(root_path: Path) -> None:
    import streamlit as st
    import streamlit.components.v1 as components

    queue_df = _read_price_list_queue_df(root_path)
    live_status = _latest_price_list_live_status(root_path)
    active_counts = _price_list_active_run_counts(root_path)
    latest_event = _latest_price_list_live_event(root_path)
    child_status = _price_list_child_status(root_path)
    components.html(
        "<script>setTimeout(function(){window.parent.location.reload();}, 60000);</script>",
        height=0,
    )
    st.subheader("Price List Queue")
    notice = st.session_state.pop("fpm_queue_control_notice", "")
    if notice:
        st.success(notice)
    if queue_df.empty:
        st.info("No price-list queue data yet.")
        _render_scanner_timeout_settings(root_path)
        return

    if live_status:
        active_supplier_for_overlay = _normalize_text(live_status.get("active_supplier_id", ""))
        active_run_for_overlay = _normalize_text(live_status.get("active_f061_run_id", ""))
        if active_supplier_for_overlay:
            overlay_results = _price_list_live_result_counts(root_path, active_run_for_overlay)
            overlay_recovery = _price_list_recovery_counts(root_path, active_supplier_for_overlay)
            active_mask = queue_df["supplier_id"].map(_normalize_text).eq(active_supplier_for_overlay)
            queue_df = queue_df.copy()
            sample_result_columns = [
                "web_pass",
                "web_fail",
                "web_rescan",
                "second_unprocessed",
                "second_pass",
                "second_fail",
            ]
            queue_df.loc[~active_mask, sample_result_columns] = "0"
            queue_df.loc[active_mask, "web_unprocessed"] = str(int(overlay_results.get("pending", 0)))
            queue_df.loc[active_mask, "web_pass"] = str(
                int(overlay_results.get("pass", 0)) + int(overlay_recovery.get("legacy_pass", 0))
            )
            queue_df.loc[active_mask, "web_fail"] = str(
                int(overlay_results.get("fail", 0)) + int(overlay_recovery.get("legacy_fail", 0))
            )
            queue_df.loc[active_mask, "web_rescan"] = str(int(overlay_results.get("rescan", 0)))

    summary = build_price_list_queue_summary(queue_df)
    handoff_preview = _latest_price_list_handoff_preview(root_path)
    if live_status:
        active_supplier_id = _normalize_text(live_status.get("active_supplier_id", ""))
        active_supplier = active_supplier_id
        if active_supplier_id and not queue_df.empty:
            matched = queue_df[queue_df["supplier_id"].map(_normalize_text).eq(active_supplier_id)]
            if not matched.empty:
                active_supplier = _normalize_text(matched.iloc[0].get("supplier_name", "")) or active_supplier_id
        state = _normalize_text(live_status.get("state", "")) or "-"
        last_action_status = _normalize_text(live_status.get("last_action_status", "")) or "-"
        pending = _price_list_int(live_status.get("pending_rows", active_counts.get("pending", 0)))
        active_f061_run_id = _normalize_text(live_status.get("active_f061_run_id", ""))
        active_counts = _price_list_active_run_counts(root_path, active_f061_run_id)
        result_counts = _price_list_live_result_counts(root_path, active_f061_run_id)
        login_counts = _price_list_login_counts(root_path, active_f061_run_id)
        login_rows = int(login_counts.get("login", 0))
        bbp_login_rows = int(login_counts.get("bbp_login", 0))
        dashboard_login_rows = int(login_counts.get("dashboard_login", 0))
        recovery_counts = _price_list_recovery_counts(root_path, active_supplier_id)
        eta = _price_list_live_eta(root_path, active_f061_run_id, pending)
        auth_parts = _price_list_auth_state(root_path)
        auth_state = _normalize_text(auth_parts.get("auth_state", ""))
        manager_mode_parts = _price_list_manager_mode_state(root_path)
        manager_mode = _normalize_text(manager_mode_parts.get("mode", ""))
        supervisor_state = _price_list_supervisor_state(root_path)
        login_button_state = _price_list_login_button_state(
            login_rows=login_rows,
            auth_state=auth_state,
            request_exists=auth_parts.get("login_mode_request_exists", "0") == "1",
            request_status=auth_parts.get("login_mode_request_status", ""),
        )
        combined_pass = int(result_counts.get("pass", 0)) + int(recovery_counts.get("legacy_pass", 0))
        combined_fail = int(result_counts.get("fail", 0)) + int(recovery_counts.get("legacy_fail", 0))
        combined_done = int(result_counts.get("done", 0)) + int(recovery_counts.get("legacy_done", 0))
        total = max(
            int(active_counts.get("total", 0)),
            int(result_counts.get("done", 0)) + pending,
            _price_list_live_progress_total(root_path, active_f061_run_id),
        )
        done = max(int(active_counts.get("done", 0)), int(result_counts.get("done", 0)), total - pending)
        pct = round((done / total) * 100, 1) if total else 0.0
        chunk_rows = _normalize_text(live_status.get("chunk_rows", "")) or "-"
        observed = _normalize_text(live_status.get("observed_utc", "")) or "-"
        st.markdown(
            "<div style='border:1px solid #164e63;background:#07131f;color:#e0f2fe;"
            "padding:12px 14px;margin:0 0 12px 0;border-radius:8px;'>"
            "<div style='display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;'>"
            "<div>"
            "<div style='font-size:12px;color:#7dd3fc;font-weight:700;'>Active Scanner</div>"
            f"<div style='font-size:18px;color:#f8fafc;font-weight:800;'>{html.escape(active_supplier or '-')}</div>"
            "</div>"
            "<div style='display:flex;gap:18px;flex-wrap:wrap;'>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>State</div><div style='font-size:14px;font-weight:700;'>{html.escape(state)}</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>Done</div><div style='font-size:14px;font-weight:700;'>{done}</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>Pending</div><div style='font-size:14px;font-weight:700;'>{pending}</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>PASS</div><div style='font-size:14px;font-weight:700;color:#86efac;'>{int(result_counts.get('pass', 0))}</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>FAIL</div><div style='font-size:14px;font-weight:700;color:#fca5a5;'>{int(result_counts.get('fail', 0))}</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>BBP</div><div style='font-size:14px;font-weight:700;color:#f87171;'>{bbp_login_rows}</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>YES/NO</div><div style='font-size:14px;font-weight:700;color:#facc15;'>{dashboard_login_rows}</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>RE SCAN</div><div style='font-size:14px;font-weight:700;color:#fde68a;'>{int(result_counts.get('rescan', 0))}</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>Progress</div><div style='font-size:14px;font-weight:700;'>{pct:.1f}%</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>Speed</div><div style='font-size:14px;font-weight:700;'>{float(eta.get('rows_per_hour', 0.0)):.1f}/h</div></div>"
            f"<div><div style='font-size:11px;color:#7dd3fc;'>ETA</div><div style='font-size:14px;font-weight:700;'>{html.escape(str(eta.get('eta_label', '-')))}</div></div>"
            "</div>"
            "</div>"
            "<div style='height:6px;background:#0f172a;border-radius:999px;margin-top:10px;overflow:hidden;'>"
            f"<div style='height:6px;width:{min(max(pct, 0), 100):.1f}%;background:#38bdf8;'></div>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        login_cols = st.columns([1.4, 1.7, 1.1, 4.3], gap="small")
        login_cols[0].markdown(
            _price_list_login_badge_html(
                login_button_state,
                login_rows=login_rows,
                auth_state=auth_state,
                manager_mode=manager_mode,
            ),
            unsafe_allow_html=True,
        )
        login_cols[1].markdown(
            _price_list_supervisor_badge_html(supervisor_state),
            unsafe_allow_html=True,
        )
        login_clicked = login_cols[2].button(
            str(login_button_state.get("label", "Login")),
            key="fpm_login_mode_request",
            disabled=bool(login_button_state.get("disabled", True)),
            type=str(login_button_state.get("button_type", "secondary")),
        )
        if login_clicked:
            try:
                result = request_price_list_login_mode_from_ui(
                    root_path,
                    supplier_id=active_supplier_id,
                    run_id=active_f061_run_id,
                )
                if result.get("status") == "requested":
                    st.session_state["fpm_queue_control_notice"] = "Login Mode requested for the next normal F061 child."
                    st.rerun()
                else:
                    st.error(f"Login Mode request blocked: {result.get('block_reason', 'unknown')}")
            except Exception as exc:
                st.error(f"Login Mode request failed: {exc}")
        with st.expander("Active scanner details", expanded=False):
            st.markdown(
                "\n".join(
                    [
                        f"- Run: `{active_f061_run_id or '-'}`",
                        f"- State: `{state}`",
                        f"- Chunk: `{chunk_rows}`",
                        f"- Last action: `{last_action_status}`",
                        f"- Updated: `{observed}`",
                        f"- Latest event: `{latest_event or '-'}`",
                        f"- Login backlog: `{login_rows}` rows (`{bbp_login_rows}` BBP, `{dashboard_login_rows}` YES/NO)",
                        f"- Auth state: `{auth_state or '-'}`",
                        f"- Operator mode: `{manager_mode or '-'}`",
                        (
                            f"- Supervisor: `{_normalize_text(supervisor_state.get('state', '-')) or '-'}` "
                            f"(`{_normalize_text(supervisor_state.get('age_label', '-')) or '-'}` ago, "
                            f"reason `{_normalize_text(supervisor_state.get('reason', '-')) or '-'}`)"
                        ),
                        (
                            f"- Current speed: `{float(eta.get('rows_per_hour', 0.0)):.1f} rows/hour` "
                            f"from `{int(eta.get('sample_rows', 0))}` completed rows in this resumed run"
                        ),
                        f"- Child: `{child_status or '-'}`",
                        (
                            "- Previous imported scan: "
                            f"`{int(recovery_counts.get('legacy_done', 0))}` done, "
                            f"`{int(recovery_counts.get('legacy_pass', 0))}` pass, "
                            f"`{int(recovery_counts.get('legacy_fail', 0))}` fail"
                        ),
                        (
                            "- Combined scan: "
                            f"`{combined_done}` done, `{combined_pass}` pass, `{combined_fail}` fail"
                        ),
                    ]
                )
            )
    st.markdown(
        "<div style='display:flex;align-items:center;gap:12px;flex-wrap:wrap;"
        "padding:8px 10px;border:1px solid #1f2937;border-radius:10px;background:#0b1220;'>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Suppliers</span><span style='font-size:12px;color:#e2e8f0;'>{summary['total_suppliers']}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Recommended</span><span style='font-size:12px;color:#e2e8f0;'>{summary['active']}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Manual missing</span><span style='font-size:12px;color:#e2e8f0;'>{summary['manual_missing']}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Blocked</span><span style='font-size:12px;color:#e2e8f0;'>{summary['blocked']}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Scan</span><span style='font-size:12px;color:#e2e8f0;'>{summary['web_unprocessed']}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>PASS</span><span style='font-size:12px;color:#e2e8f0;'>{summary['web_pass']}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>FAIL</span><span style='font-size:12px;color:#e2e8f0;'>{summary['web_fail']}</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<style>
.fpm-queue-card {
    padding: 4px 2px 2px 2px;
}
.fpm-queue-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 10px;
    align-items: start;
}
.fpm-queue-position {
    color: #93c5fd;
    font-size: 12px;
    font-weight: 800;
    margin-bottom: 3px;
}
.fpm-queue-supplier {
    color: #f8fafc;
    font-size: 17px;
    font-weight: 800;
    line-height: 1.2;
    overflow-wrap: anywhere;
}
.fpm-queue-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}
.fpm-queue-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 26px;
    max-width: 100%;
    padding: 3px 8px;
    border: 1px solid #1f2937;
    border-radius: 999px;
    background: #0b1220;
    color: #94a3b8;
    font-size: 12px;
}
.fpm-queue-chip strong {
    color: #e2e8f0;
    font-weight: 800;
    overflow-wrap: anywhere;
}
.fpm-queue-metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(74px, 1fr));
    gap: 8px;
    margin-top: 12px;
}
.fpm-queue-metric {
    min-width: 0;
    padding: 7px 8px;
    border: 1px solid #1f2937;
    border-radius: 8px;
    background: #07111f;
}
.fpm-queue-metric-label {
    color: #7dd3fc;
    font-size: 11px;
    font-weight: 700;
    line-height: 1.1;
}
.fpm-queue-metric-value {
    margin-top: 3px;
    font-size: 15px;
    font-weight: 800;
    line-height: 1.15;
    overflow-wrap: anywhere;
}
.fpm-queue-note {
    margin-top: 10px;
    color: #cbd5e1;
    font-size: 12px;
    line-height: 1.35;
    overflow-wrap: anywhere;
}
@media (max-width: 900px) {
    .fpm-queue-head {
        grid-template-columns: 1fr;
    }
    .fpm-queue-meta {
        gap: 5px;
    }
    .fpm-queue-chip {
        width: 100%;
        justify-content: space-between;
        border-radius: 8px;
    }
    .fpm-queue-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
</style>
        """,
        unsafe_allow_html=True,
    )

    manual_df = queue_df[queue_df["queue_state"].map(_normalize_text) == "Needs Manual File"].copy()
    if not manual_df.empty:
        st.markdown("### Manual File Alerts")
        for _, row in manual_df.iterrows():
            st.markdown(
                "<div style='border:1px solid #7f1d1d;background:#1f1115;color:#fecaca;"
                "padding:8px 10px;margin:0 0 6px 0;border-radius:8px;'>"
                f"<strong>{html.escape(_normalize_text(row.get('supplier_name', '')))}</strong>"
                f"<span style='font-size:12px;color:#fca5a5;margin-left:10px;'>{html.escape(_normalize_text(row.get('operator_action', '')))}</span>"
                f"<div style='font-size:12px;color:#cbd5e1;margin-top:3px;'>{html.escape(_normalize_text(row.get('source_location', '')))}</div>"
                "</div>",
                unsafe_allow_html=True,
            )

    st.markdown("### Queue")
    for _, row in queue_df.iterrows():
        supplier_id = _normalize_text(row.get("supplier_id", ""))
        supplier = _normalize_text(row.get("supplier_name", ""))
        method = _normalize_text(row.get("source_method", ""))
        file_state = _normalize_text(row.get("file_state", ""))
        queue_state = _normalize_text(row.get("queue_state", ""))
        source_location = _normalize_text(row.get("source_location", ""))
        date_text = _normalize_text(row.get("price_list_date", "")) or "-"
        action_text = _normalize_text(row.get("operator_action", "")) or "-"
        queue_position = _normalize_text(row.get("queue_position", ""))
        control_state = _normalize_text(row.get("control_state", ""))
        unprocessed = _price_list_int(row.get("web_unprocessed", ""))
        passed = _price_list_int(row.get("web_pass", ""))
        failed = _price_list_int(row.get("web_fail", ""))
        login = 0
        rescan = _price_list_int(row.get("web_rescan", ""))
        if live_status and supplier_id == _normalize_text(live_status.get("active_supplier_id", "")):
            active_run_id = _normalize_text(live_status.get("active_f061_run_id", ""))
            row_result_counts = _price_list_live_result_counts(root_path, active_run_id)
            row_login_counts = _price_list_login_counts(root_path, active_run_id)
            row_recovery_counts = _price_list_recovery_counts(root_path, supplier_id)
            unprocessed = int(row_result_counts.get("pending", 0))
            passed = int(row_result_counts.get("pass", 0)) + int(row_recovery_counts.get("legacy_pass", 0))
            failed = int(row_result_counts.get("fail", 0)) + int(row_recovery_counts.get("legacy_fail", 0))
            login = int(row_login_counts.get("login", 0))
            rescan = int(row_result_counts.get("rescan", 0))
        second_unprocessed = _price_list_int(row.get("second_unprocessed", ""))
        second_pass = _price_list_int(row.get("second_pass", ""))
        second_fail = _price_list_int(row.get("second_fail", ""))

        with st.container(border=True):
            normalized_control = control_state.lower()
            button_key = _supplier_key_fragment(supplier_id or supplier)
            pause_label = "Resume" if normalized_control.startswith("paused") else "Pause"
            priority_label = "Clear Priority" if normalized_control.startswith("prioritised") else "Prioritise"
            inactive_for_priority = queue_state in {"Needs Manual File", "Blocked", "Complete"} or unprocessed <= 0
            metric_html = "".join(
                [
                    _price_list_queue_metric_html("Scan", unprocessed),
                    _price_list_queue_metric_html("PASS", passed, "#86efac"),
                    _price_list_queue_metric_html("FAIL", failed, "#fca5a5"),
                    _price_list_queue_metric_html("LOGIN", login, "#f87171"),
                    _price_list_queue_metric_html("Rescan", rescan, "#fde68a"),
                    _price_list_queue_metric_html("2nd wait", second_unprocessed),
                    _price_list_queue_metric_html("2nd pass", second_pass, "#86efac"),
                    _price_list_queue_metric_html("2nd fail", second_fail, "#fca5a5"),
                ]
            )
            meta_html = "".join(
                [
                    _price_list_queue_chip_html("Method", method),
                    _price_list_queue_chip_html("File", file_state or "-"),
                    _price_list_queue_chip_html("Control", control_state or "Normal"),
                    _price_list_queue_chip_html("Date", date_text),
                ]
            )
            st.markdown(
                "<div class='fpm-queue-card'>"
                "<div class='fpm-queue-head'>"
                "<div>"
                f"<div class='fpm-queue-position'>#{html.escape(queue_position or '-')}</div>"
                f"<div class='fpm-queue-supplier'>{html.escape(supplier or supplier_id or '-')}</div>"
                f"<div class='fpm-queue-meta'>{meta_html}</div>"
                "</div>"
                f"<div>{_price_list_queue_badge(queue_state)}</div>"
                "</div>"
                f"<div class='fpm-queue-metrics'>{metric_html}</div>"
                "<div class='fpm-queue-note'>"
                f"{html.escape(source_location or '-')}<br>"
                f"Action: {html.escape(action_text)}<br>"
                "Buttons write test-mode controls only. Live F061 handoff is still disabled."
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            action_cols = st.columns([1, 1, 4], gap="small")
            pause_clicked = action_cols[0].button(
                pause_label,
                key=f"fpm_pause_{button_key}",
                disabled=not supplier_id,
            )
            priority_clicked = action_cols[1].button(
                priority_label,
                key=f"fpm_priority_{button_key}",
                disabled=(not supplier_id or inactive_for_priority),
            )
            if pause_clicked:
                target_state = "normal" if normalized_control.startswith("paused") else "paused"
                reason = "operator resumed supplier" if target_state == "normal" else "operator paused supplier"
                try:
                    result = apply_price_list_queue_control(
                        root=root_path,
                        supplier_id=supplier_id,
                        control_state=target_state,
                        reason=reason,
                    )
                    selected = _normalize_text(result["decision"].get("selected_supplier_id", ""))
                    st.session_state["fpm_queue_control_notice"] = (
                        f"{supplier} set to {target_state}. Next recommendation: {selected or 'none'}."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Queue control failed: {exc}")
            if priority_clicked:
                target_state = "normal" if normalized_control.startswith("prioritised") else "prioritised"
                reason = (
                    "operator cleared priority"
                    if target_state == "normal"
                    else "operator prioritised supplier from UI"
                )
                try:
                    result = apply_price_list_queue_control(
                        root=root_path,
                        supplier_id=supplier_id,
                        control_state=target_state,
                        priority_rank="1" if target_state == "prioritised" else "",
                        reason=reason,
                    )
                    selected = _normalize_text(result["decision"].get("selected_supplier_id", ""))
                    st.session_state["fpm_queue_control_notice"] = (
                        f"{supplier} set to {target_state}. Next recommendation: {selected or 'none'}."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Queue control failed: {exc}")

    report_text = _read_price_list_next_action_report(root_path)
    if report_text:
        with st.expander("Next Action Explanation", expanded=False):
            st.markdown(report_text)
    _render_scanner_timeout_settings(root_path)


def _format_skipped_restock_rows(skipped_rows: list[str]) -> str:
    if not skipped_rows:
        return ""
    friendly: list[str] = []
    for item in skipped_rows:
        sku, _, reason = item.partition(":")
        reason_key = _normalize_text(reason)
        if reason_key == "missing_qty_or_price":
            friendly.append(f"{sku} needs Qty and Price")
        else:
            friendly.append(_normalize_text(item))
    return "Not sent: " + ", ".join(friendly)


def _review_widget_key(row_data: dict[str, object], *, pack_type: str) -> str:
    identity = "|".join(
        [
            _normalize_text(pack_type),
            _normalize_text(row_data.get("active_supplier_id", "")),
            _normalize_text(row_data.get("active_run_id", "")),
            _normalize_text(row_data.get("candidate_id", "")),
        ]
    )
    return _supplier_key_fragment(identity or uuid.uuid4().hex[:8])


def _feeder_review_done_key(
    *,
    pack_type: str,
    supplier_filter: str,
    review_batch_id: str,
    search_text: str,
) -> str:
    scope = "|".join(
        [
            _normalize_text(pack_type),
            _normalize_text(supplier_filter),
            _normalize_text(review_batch_id),
            _normalize_text(search_text),
        ]
    )
    return f"o_feeder_review_done_{_supplier_key_fragment(scope)}"


def _feeder_review_identity_tuple(row_data: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        _normalize_text(row_data.get("active_supplier_id", "")),
        _normalize_text(row_data.get("active_run_id", "")),
        _normalize_text(row_data.get("review_pack_type", "")),
        _normalize_text(row_data.get("candidate_id", "")),
    )


def load_feeder_review_ui_drafts_df(root: Path | None = None) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    return _read_contract_df(root_path, "feeder_review_ui_drafts")


def _build_feeder_review_draft_map(drafts_df: pd.DataFrame) -> dict[tuple[str, str, str, str], dict[str, str]]:
    if drafts_df.empty:
        return {}
    out: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for _, row in drafts_df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        identity = (
            row_dict.get("active_supplier_id", ""),
            row_dict.get("active_run_id", ""),
            row_dict.get("review_pack_type", ""),
            row_dict.get("candidate_id", ""),
        )
        if any(token == "" for token in identity):
            continue
        out[identity] = row_dict
    return out


def _seed_feeder_review_widget_draft(
    row_data: dict[str, object],
    *,
    pack_type: str,
    draft_map: dict[tuple[str, str, str, str], dict[str, str]],
) -> None:
    import streamlit as st

    scoped_row = dict(row_data)
    scoped_row["review_pack_type"] = pack_type
    identity = _feeder_review_identity_tuple(scoped_row)
    draft = draft_map.get(identity)
    if draft is None:
        return
    widget_key = _review_widget_key(scoped_row, pack_type=pack_type)
    decision_key = f"feeder_decision_{widget_key}"
    reason_key = f"feeder_reason_{widget_key}"
    note_key = f"feeder_note_{widget_key}"
    done_key = f"feeder_done_{widget_key}"
    coo_key = f"feeder_coo_{widget_key}"
    price_key = f"feeder_price_{widget_key}"
    tax_key = f"feeder_tax_{widget_key}"
    currency_key = f"feeder_currency_{widget_key}"
    tax_included_key = f"feeder_tax_included_{widget_key}"

    draft_decision = _normalize_feeder_review_decision(draft.get("draft_decision", ""))
    decision_display = FEEDER_REVIEW_DECISION_DISPLAY.get(draft_decision, FEEDER_REVIEW_DECISION_DISPLAY[""])
    if decision_key not in st.session_state:
        st.session_state[decision_key] = decision_display
    elif st.session_state.get(decision_key) not in FEEDER_REVIEW_DECISION_OPTIONS:
        current_decision = _normalize_feeder_review_decision(st.session_state.get(decision_key, ""))
        st.session_state[decision_key] = FEEDER_REVIEW_DECISION_DISPLAY.get(current_decision, FEEDER_REVIEW_DECISION_DISPLAY[""])
    draft_reason_code = _normalize_feeder_review_reason_code(draft.get("draft_reason_code", ""))
    if reason_key not in st.session_state:
        st.session_state[reason_key] = _feeder_review_reason_label(draft_reason_code) or "Select reason"
    if note_key not in st.session_state:
        st.session_state[note_key] = _normalize_text(draft.get("draft_note", ""))
    if done_key not in st.session_state:
        draft_done = _normalize_text(draft.get("draft_done", "")).lower()
        st.session_state[done_key] = draft_done in {"1", "true", "yes", "y"}
    if coo_key not in st.session_state:
        st.session_state[coo_key] = _normalize_text(draft.get("draft_country_of_origin", "")).upper()
    if price_key not in st.session_state:
        st.session_state[price_key] = _normalize_text(draft.get("draft_starting_price_gbp", ""))
    if tax_key not in st.session_state:
        st.session_state[tax_key] = (
            _normalize_text(draft.get("draft_product_tax_code", "")) or DEFAULT_FEEDER_REVIEW_PRODUCT_TAX_CODE
        )
    if currency_key not in st.session_state:
        st.session_state[currency_key] = (
            _normalize_currency_code(draft.get("draft_currency_code", "")) or DEFAULT_FEEDER_REVIEW_CURRENCY_CODE
        )
    if tax_included_key not in st.session_state:
        draft_price_includes_tax = _normalize_price_includes_tax(draft.get("draft_price_includes_tax", ""))
        st.session_state[tax_included_key] = draft_price_includes_tax == "1"


def save_feeder_review_ui_drafts(
    *,
    root: Path | None = None,
    reviewed_rows: list[dict[str, object]],
    supplier_filter: str,
    review_batch_id: str,
    search_text: str,
) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    existing_df = load_feeder_review_ui_drafts_df(root=root_path)
    existing_rows = [{key: _normalize_text(value) for key, value in row.items()} for row in existing_df.to_dict("records")]

    incoming_by_identity: dict[tuple[str, str, str, str], dict[str, str] | None] = {}
    for row in reviewed_rows:
        row_dict = {key: _normalize_text(value) for key, value in row.items()}
        identity = (
            row_dict.get("active_supplier_id", ""),
            row_dict.get("active_run_id", ""),
            row_dict.get("review_pack_type", ""),
            row_dict.get("candidate_id", ""),
        )
        if any(token == "" for token in identity):
            continue
        decision = _normalize_feeder_review_decision(row.get("review_decision", ""))
        reason_code = _normalize_feeder_review_reason_code(row.get("review_reason_code", ""))
        note = _normalize_text(row.get("review_note", ""))
        done = bool(row.get("row_done"))
        draft_country_of_origin = _normalize_text(row_dict.get("country_of_origin", "")).upper()
        draft_product_tax_code = (
            _normalize_text(row_dict.get("product_tax_code", "")) or DEFAULT_FEEDER_REVIEW_PRODUCT_TAX_CODE
        )
        draft_currency_code = (
            _normalize_currency_code(row_dict.get("currency_code", "")) or DEFAULT_FEEDER_REVIEW_CURRENCY_CODE
        )
        draft_price_includes_tax = _normalize_price_includes_tax(row_dict.get("price_includes_tax", ""))
        draft_starting_price_gbp = _normalize_positive_money(row_dict.get("starting_price_gbp", ""))
        keep_row = (
            decision in FEEDER_REVIEW_DECISIONS
            or reason_code != ""
            or note != ""
            or done
            or draft_country_of_origin != ""
            or _normalize_text(row_dict.get("starting_price_gbp", "")) != ""
            or _normalize_text(row_dict.get("product_tax_code", "")) != ""
            or _normalize_text(row_dict.get("currency_code", "")) != ""
        )
        if keep_row:
            incoming_by_identity[identity] = {
                "updated_utc": _utc_now_iso(),
                "active_supplier_id": identity[0],
                "active_run_id": identity[1],
                "review_pack_type": identity[2],
                "review_batch_id": _normalize_text(row_dict.get("review_batch_id", "")),
                "candidate_id": identity[3],
                "draft_decision": decision if decision in FEEDER_REVIEW_DECISIONS else "",
                "draft_reason_code": reason_code,
                "draft_note": note,
                "draft_done": "1" if done else "0",
                "supplier_sku": _normalize_text(row_dict.get("supplier_sku", "")),
                "asin": _normalize_text(row_dict.get("asin", "")),
                "title": _normalize_text(row_dict.get("title", "")),
                "main_rank": _normalize_text(row_dict.get("main_rank", "")),
                "review_priority_score": _normalize_text(row_dict.get("review_priority_score", "")),
                "draft_country_of_origin": draft_country_of_origin,
                "draft_product_tax_code": draft_product_tax_code,
                "draft_currency_code": draft_currency_code,
                "draft_price_includes_tax": draft_price_includes_tax,
                "draft_starting_price_gbp": draft_starting_price_gbp,
                "context_supplier_filter": _normalize_text(supplier_filter),
                "context_review_batch_id": _normalize_text(review_batch_id),
                "context_search_text": _normalize_text(search_text),
            }
        else:
            incoming_by_identity[identity] = None

    replace_keys = set(incoming_by_identity.keys())
    retained_rows: list[dict[str, str]] = []
    for row in existing_rows:
        identity = (
            _normalize_text(row.get("active_supplier_id", "")),
            _normalize_text(row.get("active_run_id", "")),
            _normalize_text(row.get("review_pack_type", "")),
            _normalize_text(row.get("candidate_id", "")),
        )
        if identity in replace_keys:
            continue
        retained_rows.append(row)

    saved_rows = [row for row in incoming_by_identity.values() if row is not None]
    out_rows = [*retained_rows, *saved_rows]
    _write_contract_rows(root_path, "feeder_review_ui_drafts", out_rows)
    return {"rows_saved": len(saved_rows), "rows_total": len(out_rows)}


def clear_feeder_review_ui_drafts(
    *,
    root: Path | None = None,
    rows: list[dict[str, object]],
) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    existing_df = load_feeder_review_ui_drafts_df(root=root_path)
    if existing_df.empty or not rows:
        return {"rows_removed": 0}
    remove_keys: set[tuple[str, str, str, str]] = set()
    for row in rows:
        row_dict = {key: _normalize_text(value) for key, value in row.items()}
        identity = (
            row_dict.get("active_supplier_id", ""),
            row_dict.get("active_run_id", ""),
            row_dict.get("review_pack_type", ""),
            row_dict.get("candidate_id", ""),
        )
        if any(token == "" for token in identity):
            continue
        remove_keys.add(identity)

    retained_rows: list[dict[str, str]] = []
    rows_removed = 0
    for _, row in existing_df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        identity = (
            row_dict.get("active_supplier_id", ""),
            row_dict.get("active_run_id", ""),
            row_dict.get("review_pack_type", ""),
            row_dict.get("candidate_id", ""),
        )
        if identity in remove_keys:
            rows_removed += 1
            continue
        retained_rows.append(row_dict)
    _write_contract_rows(root_path, "feeder_review_ui_drafts", retained_rows)
    return {"rows_removed": rows_removed}


def _render_feeder_review_card(row_data: dict[str, object], *, pack_type: str) -> dict[str, str]:
    import streamlit as st

    candidate_id = _normalize_text(row_data.get("candidate_id", ""))
    widget_key = _review_widget_key(row_data, pack_type=pack_type)
    title = _normalize_text(row_data.get("title", "")) or "(Untitled product)"
    supplier_sku = _normalize_text(row_data.get("supplier_sku", ""))
    asin_raw = _normalize_text(row_data.get("asin", ""))
    asin_padded = _normalize_text(row_data.get("asin_padded", ""))
    amazon_dp_url = _normalize_text(row_data.get("amazon_dp_url", ""))
    image_url = _normalize_text(row_data.get("main_image", ""))
    brand = _normalize_text(row_data.get("brand", ""))
    main_rank = _normalize_text(row_data.get("main_rank", ""))
    sales_lower = _normalize_text(row_data.get("sales_lower_30d", ""))
    sales_expected = _normalize_text(row_data.get("expected_units_next_30d", ""))
    sales_upper = _normalize_text(row_data.get("sales_upper_30d", ""))
    profit_expected = _normalize_text(row_data.get("expected_profit_next_30d_gbp", ""))
    if not profit_expected:
        profit_expected = _normalize_text(row_data.get("estimated_monthly_profit_gbp", ""))
    profit_per_unit = _normalize_text(row_data.get("profit_per_unit_30d_gbp", ""))
    if not profit_per_unit:
        profit_per_unit = _normalize_text(row_data.get("profit_per_unit_gbp", ""))
    original_point_score = _normalize_text(row_data.get("original_point_score", ""))
    original_test_result = _normalize_text(row_data.get("original_test_result", "")).upper()
    starter_qty = _normalize_text(row_data.get("conservative_starter_qty", ""))
    commercial_note = _normalize_text(row_data.get("commercial_note", ""))
    why_label = _normalize_text(row_data.get("why_label", ""))
    why_text = _normalize_text(row_data.get("why_text", ""))
    helper_label = _normalize_text(row_data.get("helper_label", ""))
    helper_text = _normalize_text(row_data.get("helper_text", ""))
    sales_low_text = _format_review_number(sales_lower)
    sales_likely_text = _format_review_number(sales_expected)
    sales_high_text = _format_review_number(sales_upper)
    starter_qty_text = _format_review_number(starter_qty, decimals_when_needed=0)
    rank_text = f"#{_format_review_number(main_rank, decimals_when_needed=0)}" if _normalize_text(main_rank) else "-"
    og_score_text = _format_review_number(original_point_score) if original_point_score else "-"
    expected_units_num = _to_float(sales_expected)
    low_units_num = _to_float(sales_lower)
    high_units_num = _to_float(sales_upper)
    expected_profit_num = _to_float(profit_expected)
    per_unit_num = _to_float(profit_per_unit)
    if per_unit_num > 0:
        low_profit_num = low_units_num * per_unit_num
        likely_profit_num = expected_units_num * per_unit_num
        high_profit_num = high_units_num * per_unit_num
    elif expected_units_num > 0:
        low_profit_num = expected_profit_num * (low_units_num / expected_units_num)
        likely_profit_num = expected_profit_num
        high_profit_num = expected_profit_num * (high_units_num / expected_units_num)
    else:
        low_profit_num = expected_profit_num
        likely_profit_num = expected_profit_num
        high_profit_num = expected_profit_num
    low_profit_text = _format_review_currency_gbp(low_profit_num)
    likely_profit_text = _format_review_currency_gbp(likely_profit_num)
    high_profit_text = _format_review_currency_gbp(high_profit_num)
    roi_pct = _normalize_text(row_data.get("review_roi_pct", "")) or _feeder_review_roi_pct(row_data)
    roi_text = _format_review_percent(roi_pct)
    profit_signal_text = (
        _normalize_text(row_data.get("review_profit_signal_text", ""))
        or _feeder_review_profit_signal_text(row_data)
        or "profit_signal=missing"
    )
    roi_title = (
        f"ROI: {roi_text}. {profit_signal_text}. Low/Likely/High estimated profit from current range."
    )
    commercial_note_human = _humanize_commercial_note(commercial_note)
    watch_text = helper_text or commercial_note_human or "-"
    why_display_text = _humanize_intake_evidence_summary(
        why_text,
        fallback="No explanation was included in this scanner pack.",
    )
    watch_display_text = _humanize_intake_evidence_summary(
        watch_text,
        fallback="No extra warning from scanner.",
    )
    asin_display = asin_padded or asin_raw
    supplier_id = _normalize_text(row_data.get("active_supplier_id", ""))
    supplier_label = _normalize_text(row_data.get("active_supplier_label", ""))
    if not supplier_label and supplier_id:
        supplier_label = supplier_id.replace("_", " ").title()
    supplier_label = supplier_label or "Supplier"
    image_html = _intake_image_html(image_url, amazon_dp_url)
    if amazon_dp_url:
        amazon_link = (
            f"<a href='{html.escape(amazon_dp_url, quote=True)}' target='_blank' "
            "rel='noopener noreferrer'>Open Amazon</a>"
        )
    else:
        amazon_link = ""

    def _fact_html(label: str, value: object, *, title_text: str = "") -> str:
        title_attr = f" title='{html.escape(title_text, quote=True)}'" if title_text else ""
        return (
            f"<div class='o-intake-fact'{title_attr}>"
            f"<div class='o-intake-fact-label'>{html.escape(label)}</div>"
            f"<div class='o-intake-fact-value'>{html.escape(_display_plain(value))}</div>"
            "</div>"
        )

    sales_range_text = f"{sales_low_text} / {sales_likely_text} / {sales_high_text}"
    profit_range_text = f"{low_profit_text} / {likely_profit_text} / {high_profit_text}"
    subline_parts = []
    if brand:
        subline_parts.append(f"Brand: {brand}")
    if original_test_result:
        subline_parts.append(f"Scanner result: {original_test_result}")
    subline = " | ".join(subline_parts) or "Price-list scanner candidate"
    id_parts = []
    if supplier_sku:
        id_parts.append(f"Supplier code: {supplier_sku}")
    if asin_display:
        id_parts.append(f"ASIN: {asin_display}")
    id_line = " | ".join(id_parts)
    if amazon_link:
        id_line = f"{id_line} | {amazon_link}" if id_line else amazon_link

    product_html = (
        "<div class='o-intake-card'>"
        "<div class='o-intake-top'>"
        f"{image_html}"
        "<div>"
        f"<div class='o-intake-supplier'>{html.escape(supplier_label)}</div>"
        f"<div class='o-intake-title'>{html.escape(title)}</div>"
        f"<div class='o-intake-subline'>{html.escape(subline)}</div>"
        "<div class='o-intake-facts'>"
        f"{_fact_html('30d sales range', sales_range_text, title_text='Low / likely / high estimated units')}"
        f"{_fact_html('ROI', roi_text, title_text=roi_title)}"
        f"{_fact_html('Likely profit', likely_profit_text, title_text=f'Low / likely / high profit: {profit_range_text}')}"
        f"{_fact_html('Start qty', starter_qty_text)}"
        f"{_fact_html('Amazon rank', rank_text)}"
        f"{_fact_html('Score', og_score_text)}"
        "</div>"
        "</div>"
        "</div>"
        "<div class='o-intake-notes'>"
        "<div class='o-intake-note'>"
        f"<div class='o-intake-note-label'>{html.escape(why_label or 'Why this is here')}</div>"
        f"<div class='o-intake-note-body'>{html.escape(why_display_text)}</div>"
        "</div>"
        "<div class='o-intake-note warn'>"
        f"<div class='o-intake-note-label'>{html.escape(helper_label or 'What to check')}</div>"
        f"<div class='o-intake-note-body'>{html.escape(watch_display_text)}</div>"
        "</div>"
        "</div>"
        f"<div class='o-intake-idline'>{id_line}</div>"
        "</div>"
    )

    with st.container():
        st.markdown(product_html, unsafe_allow_html=True)
        st.markdown("<div class='o-intake-action-title'>Choose what to do</div>", unsafe_allow_html=True)
        decision_key = f"feeder_decision_{widget_key}"
        if decision_key in st.session_state and st.session_state.get(decision_key) not in FEEDER_REVIEW_DECISION_OPTIONS:
            current_decision = _normalize_feeder_review_decision(st.session_state.get(decision_key, ""))
            st.session_state[decision_key] = FEEDER_REVIEW_DECISION_DISPLAY.get(
                current_decision,
                FEEDER_REVIEW_DECISION_DISPLAY[""],
            )
        decision_value = st.radio(
            "Choice",
            options=FEEDER_REVIEW_DECISION_OPTIONS,
            index=0,
            key=decision_key,
            horizontal=True,
        )
        action_cols = st.columns([1.35, 2.45, 0.9], gap="medium")
        with action_cols[0]:
            reason_labels = [label for _code, label in FEEDER_REVIEW_REASON_OPTIONS]
            reason_value = st.selectbox(
                "Reason",
                options=reason_labels,
                index=0,
                key=f"feeder_reason_{widget_key}",
            )
        with action_cols[1]:
            note_value = st.text_input(
                "Optional note",
                value="",
                key=f"feeder_note_{widget_key}",
                placeholder="Add note",
            )
        with action_cols[2]:
            row_done = st.checkbox(
                "Checked",
                value=False,
                key=f"feeder_done_{widget_key}",
            )

        st.markdown("<div class='o-intake-divider'></div>", unsafe_allow_html=True)

    return {
        "candidate_id": candidate_id,
        "review_decision": _normalize_feeder_review_decision(decision_value),
        "review_reason_code": _normalize_feeder_review_reason_code(reason_value),
        "review_reason_label": _feeder_review_reason_label(reason_value),
        "review_note": _normalize_text(note_value),
        "row_done": bool(row_done),
        "active_supplier_id": _normalize_text(row_data.get("active_supplier_id", "")),
        "active_run_id": _normalize_text(row_data.get("active_run_id", "")),
        "review_pack_type": pack_type,
        "review_batch_id": _normalize_text(row_data.get("review_batch_id", "")),
        "supplier_sku": supplier_sku,
        "asin": asin_raw,
        "title": title,
        "brand": brand,
        "main_rank": main_rank,
        "review_priority_score": _normalize_text(row_data.get("review_priority_score", "")),
        "country_of_origin": "",
        "product_tax_code": "",
        "currency_code": "",
        "price_includes_tax": "",
        "starting_price_gbp": "",
        "f032_decision_id": _normalize_text(row_data.get("f032_decision_id", "")),
        "f032_action": _normalize_text(row_data.get("f032_action", "")),
        "f032_decision_bucket": _normalize_text(row_data.get("f032_decision_bucket", "")),
        "f032_fail_category": _normalize_text(row_data.get("f032_fail_category", "")),
        "f032_confidence": _normalize_text(row_data.get("f032_confidence", "")),
        "f032_reason": _normalize_text(row_data.get("f032_reason", "")),
        "f032_operator_check_note": _normalize_text(row_data.get("f032_operator_check_note", "")),
        "codex_ai_action": _normalize_text(row_data.get("codex_ai_action", "")),
        "codex_ai_decision_bucket": _normalize_text(row_data.get("codex_ai_decision_bucket", "")),
        "codex_ai_reason": _normalize_text(row_data.get("codex_ai_reason", "")),
        "codex_ai_evidence": _normalize_text(row_data.get("codex_ai_evidence", "")),
    }


def _render_ai_product_check_gate_tab(root_path: Path) -> None:
    import streamlit as st

    st.subheader("AI Gate QA")
    st.caption(
        "Backend diagnostics for tuning the AI checker. Daily product review should happen from New Product Review."
    )

    quality_path = root_path / "out" / "systems" / "F" / "price_list_manager" / "live" / "ai_gate_quality_report.csv"
    quality_df = _read_csv_safe(quality_path)
    if not quality_df.empty and "status" in quality_df.columns:
        fail_checks = int(quality_df["status"].map(_normalize_text).eq("fail").sum())
        warn_checks = int(quality_df["status"].map(_normalize_text).eq("warn").sum())
        if fail_checks:
            st.error(f"AI gate quality has {fail_checks} hard fail checks. Do not treat clean-pass output as ready.")
        elif warn_checks:
            st.warning(f"AI gate quality has {warn_checks} warnings. Clean-pass blockers are clear, but evidence gaps remain.")
        else:
            st.success("AI gate quality checks are clear.")

    gate_df = build_ai_product_check_gate_df(root=root_path)
    if gate_df.empty:
        st.info("No AI product check rows yet.")
        return

    status_counts = gate_df["queue_state"].value_counts().to_dict()
    legacy_pass_needs_gate_count = int(status_counts.get("legacy_needs_ai_gate", 0))
    legacy_manual_near_count = int(status_counts.get("legacy_manual_near_backlog", 0))
    metric_cols = st.columns(9, gap="small")
    metric_cols[0].metric("Total", len(gate_df.index))
    metric_cols[1].metric("Legacy Pass", legacy_pass_needs_gate_count)
    metric_cols[2].metric("Legacy Manual/Near", legacy_manual_near_count)
    metric_cols[3].metric("Queue Pending", int(status_counts.get("pending_ai_check", 0)))
    metric_cols[4].metric("Waiting Queue", int(status_counts.get("waiting_for_ai_queue", 0)))
    metric_cols[5].metric("Cleared", int(status_counts.get("ai_cleared", 0)))
    metric_cols[6].metric("User Guidance", int(status_counts.get("needs_user_guidance", 0)))
    metric_cols[7].metric("Rescan", int(status_counts.get("rescan_needed", 0)))
    metric_cols[8].metric("Rejected", int(status_counts.get("ai_rejected", 0)))

    work = gate_df.copy()
    work["queue_state_label"] = work["queue_state"].map(
        lambda value: AI_PRODUCT_CHECK_GATE_STATUS_LABELS.get(_normalize_text(value), _normalize_text(value))
    )
    work["handoff_label"] = work.apply(
        lambda row: (
            f"{_normalize_text(row.get('supplier_name', '')) or _normalize_text(row.get('supplier_id', ''))}"
            f" | {_normalize_text(row.get('run_id', ''))}"
        ),
        axis=1,
    )
    if legacy_pass_needs_gate_count or legacy_manual_near_count:
        st.info(
            f"{legacy_pass_needs_gate_count} old clean-pass rows need AI gate conversion. "
            f"{legacy_manual_near_count} old manual/near rows are legacy review rows, not clean passes. "
            "Both groups are blocked from New Product Review until deliberately converted or archived."
        )

    filter_cols = st.columns([1.5, 1.2, 2.4], gap="small")
    handoff_options = ["All handoffs", *sorted({v for v in work["handoff_label"].map(_normalize_text) if v})]
    selected_handoff = filter_cols[0].selectbox(
        "Handoff",
        options=handoff_options,
        key="o_ai_product_check_handoff_filter",
    )
    status_options = [
        "All statuses",
        *[
            AI_PRODUCT_CHECK_GATE_STATUS_LABELS.get(status, status)
            for status in AI_PRODUCT_CHECK_GATE_STATUS_ORDER
            if int(status_counts.get(status, 0)) > 0
        ],
    ]
    selected_status_label = filter_cols[1].selectbox(
        "Status",
        options=status_options,
        key="o_ai_product_check_status_filter",
    )
    search_text = filter_cols[2].text_input(
        "Search SKU / ASIN / title / reason",
        value="",
        key="o_ai_product_check_search",
    )

    filtered = work.copy()
    if selected_handoff != "All handoffs":
        filtered = filtered[filtered["handoff_label"].map(_normalize_text).eq(selected_handoff)].copy()
    if selected_status_label != "All statuses":
        selected_status = next(
            (
                status
                for status, label in AI_PRODUCT_CHECK_GATE_STATUS_LABELS.items()
                if label == selected_status_label
            ),
            "",
        )
        if selected_status:
            filtered = filtered[filtered["queue_state"].map(_normalize_text).eq(selected_status)].copy()
    query = _normalize_text(search_text).lower()
    if query:
        search_columns = [
            "supplier_sku",
            "asin",
            "supplier_title",
            "amazon_title",
            "codex_ai_reason",
            "codex_ai_evidence",
        ]
        mask = pd.Series(False, index=filtered.index)
        for column in search_columns:
            mask = mask | filtered[column].map(lambda value: query in _normalize_text(value).lower())
        filtered = filtered[mask].copy()

    st.caption(f"Showing {len(filtered.index)} of {len(gate_df.index)} AI check rows.")
    if filtered.empty:
        st.info("No rows match the current filters.")
        return

    table_columns = [
        "queue_state_label",
        "source_review_pack_type",
        "supplier_name",
        "supplier_sku",
        "asin",
        "supplier_title",
        "amazon_title",
        "roi_pct",
        "codex_ai_confidence",
        "operator_visible_flag",
        "codex_ai_reason",
    ]
    table_df = filtered[table_columns].rename(
        columns={
            "queue_state_label": "AI status",
            "source_review_pack_type": "Source lane",
            "supplier_name": "Supplier",
            "supplier_sku": "Supplier SKU",
            "asin": "ASIN",
            "supplier_title": "Supplier title",
            "amazon_title": "Amazon title",
            "roi_pct": "ROI %",
            "codex_ai_confidence": "Confidence",
            "operator_visible_flag": "Visible to user",
            "codex_ai_reason": "AI note",
        }
    )
    st.dataframe(table_df, hide_index=True, use_container_width=True)

    with st.expander("Decision detail"):
        for idx, (_, row) in enumerate(filtered.head(25).iterrows(), start=1):
            row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
            st.markdown(
                f"**{idx}. {row_dict.get('supplier_sku') or '-'} | {row_dict.get('asin') or '-'} | "
                f"{row_dict.get('queue_state_label') or '-'}**"
            )
            st.markdown(
                f"Supplier title: {row_dict.get('supplier_title') or '-'}\n\n"
                f"Amazon title: {row_dict.get('amazon_title') or '-'}\n\n"
                f"Amazon description: {row_dict.get('amazon_description_snippet') or '-'}\n\n"
                f"ROI: {row_dict.get('roi_pct') or '-'} | Confidence: {row_dict.get('codex_ai_confidence') or '-'}\n\n"
                f"AI note: {row_dict.get('codex_ai_reason') or '-'}\n\n"
                f"AI evidence: {row_dict.get('codex_ai_evidence') or '-'}\n\n"
                f"Rule reason: {row_dict.get('f032_rule_reason') or '-'}"
            )
            st.caption(
                f"Queue: {row_dict.get('queue_path') or '-'} | Decision: {row_dict.get('decision_path') or '-'}"
            )
            st.markdown("<div style='height:1px;background:#1f2937;margin:6px 0;'></div>", unsafe_allow_html=True)


def _render_new_product_review_tab(root_path: Path) -> None:
    import streamlit as st

    st.markdown(
        "<div class='o-intake-work-header'>"
        "<div class='o-intake-work-kicker'>Manual supplier check</div>"
        "<div class='o-intake-work-title'>Pick the supplier products to check</div>"
        "<div class='o-intake-work-body'>"
        "Work through scanner-found products one supplier batch at a time. "
        "Your choices stay local and do not buy stock, list products, change prices, write Sheets, or run the scanner."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    lane_map = FEEDER_REVIEW_LANE_SPECS
    lane_options = list(lane_map.keys())
    lane_key = "o_feeder_review_lane"
    requested_lane_label = _normalize_text(st.session_state.pop("o_feeder_review_requested_lane", ""))
    if requested_lane_label in lane_map:
        st.session_state.pop(lane_key, None)
        selected_lane_label = requested_lane_label
    else:
        selected_lane_label = _normalize_text(st.session_state.get(lane_key, "Passes")) or "Passes"
    if selected_lane_label not in lane_map:
        selected_lane_label = "Passes"
    st.markdown(
        "<div class='o-intake-filter-title'>Choose the work pack</div>"
        "<div class='o-intake-filter-note'>Start with the best scanner finds, or switch to judgement checks and close calls.</div>",
        unsafe_allow_html=True,
    )
    top_control_cols = st.columns([1.55, 1.05, 3.0], gap="small")
    selected_lane_label = top_control_cols[0].selectbox(
        "What to check",
        options=lane_options,
        index=lane_options.index(selected_lane_label),
        key=lane_key,
        format_func=_feeder_review_lane_display_label,
    )
    selected_lane_display = _feeder_review_lane_display_label(selected_lane_label)
    lane_spec = lane_map[selected_lane_label]
    lane_id = lane_spec["lane_id"]
    pack_type = lane_spec["pack_type"]
    lane_filter = lane_spec["lane_filter"]

    show_pack_history_key = "o_feeder_review_show_pack_history"
    show_pack_history = top_control_cols[1].checkbox(
        "History",
        value=bool(st.session_state.get(show_pack_history_key, False)),
        key=show_pack_history_key,
        help="Use only when you need to look back at older saved supplier checks.",
    )
    pack_options = list_feeder_review_pack_options(
        root=root_path,
        include_history=show_pack_history,
        pack_type=pack_type,
        lane_filter=lane_filter,
        lane_label=selected_lane_label,
    )
    if not pack_options:
        st.info(
            f"No {selected_lane_display.lower()} are waiting. "
            "Tick History if you need to inspect older saved checks."
        )
        return
    pack_option_ids = [option["id"] for option in pack_options] or ["latest"]
    pack_option_labels = {option["id"]: option["label"] for option in pack_options}
    pack_key = "o_feeder_review_pack_snapshot"
    requested_pack_snapshot = _normalize_text(st.session_state.pop("o_feeder_review_requested_pack_snapshot", ""))
    if requested_pack_snapshot in pack_option_ids:
        st.session_state.pop(pack_key, None)
        selected_pack_snapshot = requested_pack_snapshot
    else:
        selected_pack_snapshot = _normalize_text(st.session_state.get(pack_key, "latest")) or "latest"
    if selected_pack_snapshot not in pack_option_ids:
        selected_pack_snapshot = pack_option_ids[0]

    selected_pack_snapshot = top_control_cols[2].selectbox(
        "Supplier batch",
        options=pack_option_ids,
        index=pack_option_ids.index(selected_pack_snapshot),
        format_func=lambda value: pack_option_labels.get(value, value),
        key=pack_key,
    )

    summary = load_feeder_review_summary(root=root_path, review_pack_snapshot=selected_pack_snapshot)
    recent_notice = _normalize_text(st.session_state.get("o_recent_feeder_review_notice", ""))
    if recent_notice:
        st.markdown(_render_inline_notice(recent_notice), unsafe_allow_html=True)

    active_supplier = (
        _normalize_text(summary.get("active_supplier_label", ""))
        or _normalize_text(summary.get("active_supplier_id", ""))
        or "-"
    )
    pass_count_df = load_feeder_review_source_df(
        "passes",
        root=root_path,
        review_pack_snapshot=selected_pack_snapshot,
    )
    near_miss_count_df = load_feeder_review_source_df(
        "near_misses",
        root=root_path,
        review_pack_snapshot=selected_pack_snapshot,
    )
    clean_pass_rows = str(len(pass_count_df.index))
    manual_review_rows = str(
        len(
            _apply_feeder_review_lane_filter(
                near_miss_count_df,
                pack_type="near_misses",
                lane_filter="manual_review",
            ).index
        )
    )
    near_miss_lane_rows = str(
        len(
            _apply_feeder_review_lane_filter(
                near_miss_count_df,
                pack_type="near_misses",
                lane_filter="near_misses",
            ).index
        )
    )
    st.markdown(
        "<div class='o-intake-status-grid'>"
        "<div class='o-intake-status-card neutral'>"
        "<div class='o-intake-status-label'>Supplier</div>"
        f"<div class='o-intake-status-value'>{html.escape(active_supplier)}</div>"
        "</div>"
        "<div class='o-intake-status-card good'>"
        "<div class='o-intake-status-label'>Best scanner finds</div>"
        f"<div class='o-intake-status-value'>{html.escape(clean_pass_rows)}</div>"
        "</div>"
        "<div class='o-intake-status-card warn'>"
        "<div class='o-intake-status-label'>Needs judgement</div>"
        f"<div class='o-intake-status-value'>{html.escape(manual_review_rows)}</div>"
        "</div>"
        "<div class='o-intake-status-card warn'>"
        "<div class='o-intake-status-label'>Close calls</div>"
        f"<div class='o-intake-status-value'>{html.escape(near_miss_lane_rows)}</div>"
        "</div>"
        "</div>"
        "<div class='o-intake-safe-note'>Safe local review only: no buying, listing, price changes, Sheet writes, or scanner runs.</div>",
        unsafe_allow_html=True,
    )

    supplier_key = f"o_feeder_review_supplier_{lane_id}"
    batch_key = f"o_feeder_review_batch_{lane_id}"
    search_key = f"o_feeder_review_search_{lane_id}"
    seed_supplier = _normalize_text(st.session_state.get(supplier_key, "All suppliers")) or "All suppliers"
    seed_batch = _normalize_text(st.session_state.get(batch_key, "Auto next 10")) or "Auto next 10"
    seed_search = _normalize_text(st.session_state.get(search_key, ""))
    _, seed_meta = build_feeder_review_window_df(
        pack_type,
        root=root_path,
        review_pack_snapshot=selected_pack_snapshot,
        lane_filter=lane_filter,
        supplier_filter=seed_supplier,
        review_batch_id=seed_batch,
        search_text=seed_search,
        page_size=FEEDER_REVIEW_PAGE_SIZE,
    )
    supplier_options = seed_meta.get("supplier_options", []) or ["All suppliers"]
    review_batch_options = seed_meta.get("review_batch_options", []) or ["Auto next 10"]
    if seed_supplier not in supplier_options:
        seed_supplier = supplier_options[0]
    if seed_batch not in review_batch_options:
        seed_batch = review_batch_options[0]

    control_cols = st.columns([1.1, 1.2, 2.2], gap="small")
    supplier_label_map = _supplier_display_map(root_path)
    supplier_filter = control_cols[0].selectbox(
        "Supplier",
        options=supplier_options,
        index=supplier_options.index(seed_supplier),
        key=supplier_key,
        format_func=lambda value: _supplier_option_label(value, supplier_label_map),
    )
    review_batch_id = control_cols[1].selectbox(
        "Working group",
        options=review_batch_options,
        index=review_batch_options.index(seed_batch),
        key=batch_key,
    )
    search_text = control_cols[2].text_input("Search title / SKU / ASIN", value=seed_search, key=search_key)

    visible_df, meta = build_feeder_review_window_df(
        pack_type,
        root=root_path,
        review_pack_snapshot=selected_pack_snapshot,
        lane_filter=lane_filter,
        supplier_filter=supplier_filter,
        review_batch_id=review_batch_id,
        search_text=search_text,
        page_size=FEEDER_REVIEW_PAGE_SIZE,
    )
    sent_df = build_feeder_review_sent_df(
        pack_type,
        root=root_path,
        review_pack_snapshot=selected_pack_snapshot,
        lane_filter=lane_filter,
        supplier_filter=supplier_filter,
        review_batch_id=review_batch_id,
        search_text=search_text,
        page_size=10,
    )
    draft_map = _build_feeder_review_draft_map(load_feeder_review_ui_drafts_df(root=root_path))

    st.caption(
        f"Showing {meta['visible_rows']} product{'' if meta['visible_rows'] == 1 else 's'}. "
        f"Waiting for choice: {meta['undecided_rows']}. Already sent: {meta['decided_rows']}."
    )
    reviewed_rows: list[dict[str, object]] = []
    if visible_df.empty:
        st.success("No undecided rows are left in this view.")
    else:
        for _, row in visible_df.iterrows():
            row_data = row.to_dict()
            _seed_feeder_review_widget_draft(row_data, pack_type=pack_type, draft_map=draft_map)
            reviewed_rows.append(_render_feeder_review_card(row_data, pack_type=pack_type))

    save_feeder_review_ui_drafts(
        root=root_path,
        reviewed_rows=reviewed_rows,
        supplier_filter=supplier_filter,
        review_batch_id=review_batch_id,
        search_text=search_text,
    )

    pass_selected = sum(1 for row in reviewed_rows if _normalize_text(row.get("review_decision", "")) == "pass")
    fail_selected = sum(1 for row in reviewed_rows if _normalize_text(row.get("review_decision", "")) == "fail")
    rescan_selected = sum(1 for row in reviewed_rows if _normalize_text(row.get("review_decision", "")) == "rescan")
    decided_rows = [
        row for row in reviewed_rows if _normalize_text(row.get("review_decision", "")).lower() in FEEDER_REVIEW_DECISIONS
    ]
    done_rows = [row for row in reviewed_rows if bool(row.get("row_done"))]
    done_decided_rows = [row for row in done_rows if row in decided_rows]
    done_missing_decision = len(done_rows) - len(done_decided_rows)
    if reviewed_rows:
        remaining_choices = len(reviewed_rows) - pass_selected - fail_selected - rescan_selected
        st.markdown(
            "<div class='o-intake-choice-strip'>"
            f"<span class='o-intake-choice-main'>{len(decided_rows)} choice{'' if len(decided_rows) == 1 else 's'} ready to send</span>"
            f"<span class='o-intake-choice-chip good'>Pass {pass_selected}</span>"
            f"<span class='o-intake-choice-chip warn'>Fail {fail_selected}</span>"
            f"<span class='o-intake-choice-chip'>Re-scan {rescan_selected}</span>"
            f"<span class='o-intake-choice-chip'>Need choice {remaining_choices}</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    if done_missing_decision > 0:
        st.warning("Some products are marked checked but still need a choice before they can be sent.")
    last_send_key = f"o_feeder_last_send_rows_{lane_id}"
    last_send_rows = st.session_state.get(last_send_key, [])
    action_cols = st.columns([1.8, 1.8, 3.2])
    send_disabled = len(decided_rows) == 0
    send_clicked = action_cols[0].button(
        "Send Choices",
        type="secondary" if send_disabled else "primary",
        disabled=send_disabled,
        key=f"o_feeder_send_{lane_id}",
        use_container_width=True,
    )
    undo_clicked = action_cols[1].button(
        "Undo Last Choices",
        disabled=(len(last_send_rows) == 0),
        key=f"o_feeder_undo_{lane_id}",
        use_container_width=True,
    )
    action_cols[2].caption(
        "This records only the choices selected on this page. It does not buy stock, change prices, write Sheets, or run the scanner."
    )

    if send_clicked:
        result = submit_feeder_review_batch(
            root=root_path,
            reviewed_rows=decided_rows,
            actor="operator_ui",
            source_reference=(
                f"o_ui_feeder_review:{pack_type}:{lane_id}:"
                f"{_normalize_text(review_batch_id) or 'auto_next_10'}"
            ),
        )
        applied_candidate_ids = {_normalize_text(candidate_id) for candidate_id in result.get("applied_candidate_ids", [])}
        applied_rows = [
            row for row in decided_rows if _normalize_text(row.get("candidate_id", "")) in applied_candidate_ids
        ]
        clear_feeder_review_ui_drafts(root=root_path, rows=applied_rows)
        st.session_state[last_send_key] = [
            {
                "active_supplier_id": _normalize_text(row.get("active_supplier_id", "")),
                "active_run_id": _normalize_text(row.get("active_run_id", "")),
                "review_pack_type": _normalize_text(row.get("review_pack_type", "")),
                "review_batch_id": _normalize_text(row.get("review_batch_id", "")),
                "candidate_id": _normalize_text(row.get("candidate_id", "")),
                "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
                "asin": _normalize_text(row.get("asin", "")),
                "title": _normalize_text(row.get("title", "")),
                "brand": _normalize_text(row.get("brand", "")),
                "main_rank": _normalize_text(row.get("main_rank", "")),
                "review_priority_score": _normalize_text(row.get("review_priority_score", "")),
            }
            for row in applied_rows
        ]
        skipped_count = len(result.get("skipped_rows", []))
        skipped_note = f" Skipped {skipped_count} row{'' if skipped_count == 1 else 's'}." if skipped_count else ""
        st.session_state["o_recent_feeder_review_notice"] = (
            f"Sent {result['events_applied']} choice"
            f"{'' if result['events_applied'] == 1 else 's'} from {selected_lane_display.lower()}."
            f"{skipped_note} Pass choices move to the next listing check. Nothing is listed automatically."
        )
        st.rerun()

    if undo_clicked:
        undo_result = submit_feeder_review_reopen_batch(
            root=root_path,
            rows_to_reopen=last_send_rows,
            actor="operator_ui",
            source_reference=f"o_ui_feeder_review_reopen:{pack_type}:{lane_id}",
        )
        st.session_state[last_send_key] = []
        st.session_state["o_recent_feeder_review_notice"] = (
            f"Reopened {undo_result['events_applied']} choice"
            f"{'' if undo_result['events_applied'] == 1 else 's'} in {selected_lane_display.lower()}."
        )
        st.rerun()

    if not sent_df.empty:
        st.markdown("<div class='o-intake-recent-title'>Recently sent choices</div>", unsafe_allow_html=True)
        for idx, (_, row) in enumerate(sent_df.iterrows()):
            row_data = row.to_dict()
            decision = _normalize_text(row_data.get("latest_review_decision", "")).upper()
            sku = _normalize_text(row_data.get("supplier_sku", ""))
            title = _normalize_text(row_data.get("title", "")) or "(Untitled product)"
            note = _normalize_text(row_data.get("latest_review_note", ""))
            when = _normalize_text(row_data.get("latest_review_utc", ""))
            display_cols = st.columns([4.5, 1.2], gap="medium")
            display_cols[0].markdown(
                f"**{decision or '-'}** - {sku or '-'} - {title}\n\n"
                f"Note: {note or '-'}\n\n"
                f"When: {when or '-'}"
            )
            reopen_key = (
                f"o_feeder_reopen_{lane_id}_"
                f"{_supplier_key_fragment(str(row_data.get('candidate_id', '')))}_{idx}"
            )
            if display_cols[1].button("Reopen Choice", key=reopen_key):
                reopen_result = submit_feeder_review_reopen_batch(
                    root=root_path,
                    rows_to_reopen=[row_data],
                    actor="operator_ui",
                    source_reference=f"o_ui_feeder_review_reopen:{pack_type}:{lane_id}:single",
                )
                st.session_state["o_recent_feeder_review_notice"] = (
                    f"Reopened {reopen_result['events_applied']} choice from recently sent choices."
                )
                st.rerun()


def _render_amazon_listing_draft_lane(root_path: Path, datasets: dict[str, pd.DataFrame]) -> None:
    import streamlit as st

    st.subheader("Approved For Amazon Listing")
    notice = _normalize_text(st.session_state.get("o_recent_amazon_listing_notice", ""))
    if notice:
        st.markdown(_render_inline_notice(notice), unsafe_allow_html=True)

    action_cols = st.columns([1.4, 4.0], gap="small")
    if action_cols[0].button("Refresh Drafts", key="o_amazon_listing_refresh"):
        result = refresh_amazon_listing_draft_pipeline(root=root_path)
        st.session_state["o_recent_amazon_listing_notice"] = (
            f"Draft refresh: intake {result['intake_rows']} | SKU reservations {result['reservation_rows']} | "
            f"drafts {result['draft_rows']} | blocked {result['blocked_draft_rows']}."
        )
        st.rerun()
    action_cols[1].caption(
        "Refresh builds local intake, reserves SKUs, and creates drafts only. It does not call Amazon or write Product DB."
    )

    display_df = build_amazon_listing_draft_display_df(datasets)
    drafts_df = datasets.get("amazon_listing_drafts_live", pd.DataFrame())
    holds_df = datasets.get("amazon_listing_holds_live", pd.DataFrame())
    health_df = datasets.get("amazon_listing_health", pd.DataFrame())
    preview_issues_df = datasets.get("amazon_listing_preview_issues_live", pd.DataFrame())

    total = int(len(drafts_df.index)) if not drafts_df.empty else 0
    ready_for_approval = int(
        (drafts_df.get("draft_status", pd.Series(dtype=str)).map(_normalize_text) == "ready_for_listing_approval").sum()
    )
    ready_for_preview = int(
        (drafts_df.get("draft_status", pd.Series(dtype=str)).map(_normalize_text) == "ready_for_amazon_preview").sum()
    )
    ready_for_submit = int(
        (drafts_df.get("draft_status", pd.Series(dtype=str)).map(_normalize_text) == "ready_for_live_submit").sum()
    )
    blocked = int(
        drafts_df.get("draft_status", pd.Series(dtype=str))
        .map(_normalize_text)
        .isin({"blocked_missing_local_data", "blocked_amazon_preview"})
        .sum()
    )
    st.markdown(
        "<div style='display:flex;align-items:center;gap:12px;flex-wrap:wrap;"
        "padding:8px 10px;border:1px solid #1f2937;border-radius:10px;background:#0b1220;'>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Drafts</span><span style='font-size:12px;color:#e2e8f0;'>{total}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Ready approval</span><span style='font-size:12px;color:#e2e8f0;'>{ready_for_approval}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Ready preview</span><span style='font-size:12px;color:#e2e8f0;'>{ready_for_preview}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Preview passed</span><span style='font-size:12px;color:#e2e8f0;'>{ready_for_submit}</span>"
        "<span style='color:#334155;'>|</span>"
        f"<span style='font-size:12px;color:#7dd3fc;'>Blocked</span><span style='font-size:12px;color:#e2e8f0;'>{blocked}</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if display_df.empty:
        st.info("No Amazon listing drafts yet.")
    else:
        filter_cols = st.columns([1.2, 1.2, 2.6], gap="small")
        status_options = ["All statuses", *sorted({v for v in display_df["draft_status"].map(_normalize_text) if v})]
        selected_status = filter_cols[0].selectbox(
            "Draft Status",
            options=status_options,
            key="o_amazon_listing_status_filter",
        )
        supplier_options = ["All suppliers", *sorted({v for v in display_df["supplier_name"].map(_normalize_text) if v})]
        selected_supplier = filter_cols[1].selectbox(
            "Supplier",
            options=supplier_options,
            key="o_amazon_listing_supplier_filter",
        )
        search_text = filter_cols[2].text_input(
            "Search SKU / ASIN / Title",
            value="",
            key="o_amazon_listing_search",
        )

        filtered = display_df.copy()
        if selected_status != "All statuses":
            filtered = filtered[filtered["draft_status"].map(_normalize_text).eq(selected_status)].copy()
        if selected_supplier != "All suppliers":
            filtered = filtered[filtered["supplier_name"].map(_normalize_text).eq(selected_supplier)].copy()
        query = _normalize_text(search_text).lower()
        if query:
            filtered = filtered[
                filtered["expected_seller_sku"].astype(str).str.lower().str.contains(query, na=False)
                | filtered["supplier_sku"].astype(str).str.lower().str.contains(query, na=False)
                | filtered["asin"].astype(str).str.lower().str.contains(query, na=False)
                | filtered["amazon_title"].astype(str).str.lower().str.contains(query, na=False)
            ].copy()

        if filtered.empty:
            st.info("No drafts match the current filters.")
        else:
            st.dataframe(
                filtered[AMAZON_LISTING_DRAFT_DISPLAY_COLUMNS],
                width="stretch",
                hide_index=True,
            )
            draft_lookup = {
                _normalize_text(row.get("draft_id", "")): row
                for row in drafts_df.to_dict("records")
                if _normalize_text(row.get("draft_id", "")) != ""
            }
            for idx, (_, row) in enumerate(filtered.head(20).iterrows()):
                row_dict = row.to_dict()
                sku = _normalize_text(row_dict.get("expected_seller_sku", ""))
                asin = _normalize_text(row_dict.get("asin", ""))
                title = _normalize_text(row_dict.get("amazon_title", "")) or "(Untitled product)"
                draft_id = ""
                for candidate_draft_id, draft_row in draft_lookup.items():
                    if (
                        _normalize_text(draft_row.get("expected_seller_sku", "")) == sku
                        and _normalize_text(draft_row.get("asin", "")) == asin
                    ):
                        draft_id = candidate_draft_id
                        break
                draft_status = _normalize_text(row_dict.get("draft_status", ""))
                block_reason = _normalize_text(row_dict.get("block_reason", ""))
                button_cols = st.columns([4.2, 1.25, 1.25, 1.25], gap="small")
                button_cols[0].markdown(f"**{sku or '-'}** - {asin or '-'} - {title}")
                approve_disabled = draft_id == "" or block_reason != "" or draft_status not in {
                    "ready_for_listing_approval",
                    "ready_for_amazon_preview",
                }
                if button_cols[1].button(
                    "Approve listing draft",
                    disabled=approve_disabled or draft_status == "ready_for_amazon_preview",
                    key=f"o_amazon_listing_approve_{idx}_{draft_id}",
                ):
                    ok, status, _ = submit_amazon_listing_draft_approval(
                        root=root_path,
                        draft_id=draft_id,
                        actor="operator_ui",
                    )
                    st.session_state["o_recent_amazon_listing_notice"] = (
                        f"{sku}: {status}." if ok else f"{sku or draft_id}: {status}."
                    )
                    st.rerun()
                if button_cols[2].button(
                    "Run Amazon preview",
                    disabled=draft_id == "" or draft_status != "ready_for_amazon_preview",
                    key=f"o_amazon_listing_preview_{idx}_{draft_id}",
                ):
                    result = run_amazon_listing_preview_for_draft(root=root_path, draft_id=draft_id)
                    st.session_state["o_recent_amazon_listing_notice"] = (
                        f"{sku}: preview attempted {result['attempted_rows']} | "
                        f"passed {result['passed_rows']} | rejected {result['rejected_rows']} | failed {result['failed_rows']}."
                    )
                    st.rerun()
                button_cols[3].button(
                    "Submit to Amazon",
                    disabled=True,
                    key=f"o_amazon_listing_submit_{idx}_{draft_id}",
                )

    if not health_df.empty:
        with st.expander("Amazon listing bridge health"):
            st.dataframe(health_df, width="stretch", hide_index=True)
    if not holds_df.empty:
        with st.expander("Amazon listing holds"):
            st.dataframe(holds_df, width="stretch", hide_index=True)
    if not preview_issues_df.empty:
        with st.expander("Amazon preview issues"):
            st.dataframe(preview_issues_df, width="stretch", hide_index=True)


def _render_product_listing_profile_review_tab(root_path: Path) -> None:
    import streamlit as st

    st.subheader("Product Listing Profile Review")
    notice = _normalize_text(st.session_state.get("o_recent_listing_profile_notice", ""))
    if notice:
        st.markdown(_render_inline_notice(notice), unsafe_allow_html=True)

    profile_df = build_product_listing_profile_review_df(root=root_path, page_size=50)
    if profile_df.empty:
        st.success("No products are waiting for listing profile review.")
        return

    st.caption(
        "Complete product setup here before Amazon draft approval. First-page Pass only moves a product into this queue."
    )
    submitted_rows: list[dict[str, object]] = []
    for idx, row in profile_df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        key_base = f"listing_profile_{_supplier_key_fragment(row_dict.get('candidate_id', str(idx)))}_{idx}"
        with st.container():
            top_cols = st.columns([1.1, 1.1, 4.0, 1.0], gap="small")
            top_cols[0].markdown(f"**SKU**  \n{row_dict.get('supplier_sku', '-') or '-'}")
            top_cols[1].markdown(f"**ASIN**  \n{row_dict.get('asin', '-') or '-'}")
            top_cols[2].markdown(f"**{row_dict.get('title', '(Untitled product)') or '(Untitled product)'}**")
            top_cols[3].markdown(f"**Status**  \n{row_dict.get('profile_status', '-') or '-'}")

            edit_cols = st.columns([0.7, 0.85, 0.85, 0.9, 1.05, 0.85, 0.75, 0.8, 0.75], gap="small")
            country_of_origin = edit_cols[0].text_input("COO", value="", max_chars=2, key=f"{key_base}_coo")
            purchase_pack_size = edit_cols[1].text_input("Buy pack", value="", key=f"{key_base}_buy_pack")
            sold_pack_size = edit_cols[2].text_input("Sold pack", value="1", key=f"{key_base}_sold_pack")
            vat_source_value = edit_cols[3].text_input("VAT source", value="", key=f"{key_base}_vat_source")
            vat_confirmed = edit_cols[4].checkbox("VAT confirmed", value=False, key=f"{key_base}_vat_confirmed")
            product_tax_code = edit_cols[5].text_input(
                "Tax code",
                value=DEFAULT_FEEDER_REVIEW_PRODUCT_TAX_CODE,
                key=f"{key_base}_tax_code",
            )
            currency_code = edit_cols[6].text_input(
                "Currency",
                value=DEFAULT_FEEDER_REVIEW_CURRENCY_CODE,
                max_chars=3,
                key=f"{key_base}_currency",
            )
            starting_price_gbp = edit_cols[7].text_input("Price", value="", key=f"{key_base}_price")
            starting_quantity = edit_cols[8].text_input("Qty", value="0", key=f"{key_base}_qty")
            db_cols = st.columns([0.9, 0.9, 0.9, 0.75, 0.9], gap="small")
            supplier_case_qty = db_cols[0].text_input("Case qty", value="", key=f"{key_base}_case_qty")
            supplier_case_multiple = db_cols[1].checkbox("Case multiple", value=False, key=f"{key_base}_case_multiple")
            valid_order_step = db_cols[2].text_input("Order step", value="", key=f"{key_base}_order_step")
            moq = db_cols[3].text_input("MOQ", value="1", key=f"{key_base}_moq")
            target_margin = db_cols[4].text_input("Target margin", value="", key=f"{key_base}_target_margin")
            lower_cols = st.columns([1.0, 3.0, 1.0], gap="small")
            condition_type = lower_cols[0].text_input("Condition", value="new_new", key=f"{key_base}_condition")
            profile_note = lower_cols[1].text_input("Profile note", value="", key=f"{key_base}_note")
            mark_complete = lower_cols[2].checkbox("Complete", value=False, key=f"{key_base}_complete")

            if mark_complete:
                submitted_rows.append(
                    {
                        **row_dict,
                        "country_of_origin": country_of_origin,
                        "purchase_pack_size": purchase_pack_size,
                        "sold_pack_size": sold_pack_size,
                        "supplier_case_qty": supplier_case_qty,
                        "supplier_case_multiple": "1" if supplier_case_multiple else "0",
                        "valid_order_step": valid_order_step,
                        "moq": moq,
                        "target_margin": target_margin,
                        "vat_source_value": vat_source_value,
                        "vat_confirmed_flag": "1" if vat_confirmed else "0",
                        "product_tax_code": product_tax_code,
                        "currency_code": currency_code,
                        "price_includes_tax": "1",
                        "starting_price_gbp": starting_price_gbp,
                        "starting_quantity": starting_quantity,
                        "condition_type": condition_type,
                        "profile_note": profile_note,
                    }
                )
            st.markdown("<div style='height:1px;background:#1f2937;margin:6px 0;'></div>", unsafe_allow_html=True)

    action_cols = st.columns([1.4, 4.0])
    if action_cols[0].button(
        "Save Completed Profiles",
        type="primary",
        disabled=(len(submitted_rows) == 0),
        key="o_listing_profile_save_completed",
    ):
        result = submit_amazon_listing_profile_batch(
            root=root_path,
            profile_rows=submitted_rows,
            actor="operator_ui",
            source_reference="o_ui_product_listing_profile_review",
        )
        skipped_count = len(result.get("skipped_rows", []))
        skipped_note = f" Skipped {skipped_count} incomplete row{'' if skipped_count == 1 else 's'}." if skipped_count else ""
        st.session_state["o_recent_listing_profile_notice"] = (
            f"Saved {result['events_applied']} completed profile"
            f"{'' if result['events_applied'] == 1 else 's'}."
            f"{skipped_note}"
        )
        st.rerun()
    action_cols[1].caption("Rows only leave this page after all required profile fields are saved.")


def _render_brand_approval_queue_tab(root_path: Path) -> None:
    import streamlit as st

    st.subheader("Brand Approval Queue")
    notice = _normalize_text(st.session_state.get("o_recent_brand_approval_notice", ""))
    if notice:
        st.markdown(_render_inline_notice(notice), unsafe_allow_html=True)

    queue_df = build_brand_approval_queue_display_df(root=root_path)
    if queue_df.empty:
        st.success("No products are waiting for brand approval decisions.")
        return

    decision_rows: list[dict[str, object]] = []
    for idx, row in queue_df.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        key_base = f"brand_approval_{_supplier_key_fragment(row_dict.get('queue_id', str(idx)))}_{idx}"
        with st.container():
            top_cols = st.columns([1.1, 1.1, 1.2, 3.6, 1.1], gap="small")
            top_cols[0].markdown(f"**SKU**  \n{row_dict.get('expected_seller_sku', '-') or '-'}")
            top_cols[1].markdown(f"**ASIN**  \n{row_dict.get('asin', '-') or '-'}")
            top_cols[2].markdown(f"**Brand**  \n{row_dict.get('brand', '-') or '-'}")
            top_cols[3].markdown(f"**{row_dict.get('amazon_title', '(Untitled product)') or '(Untitled product)'}**")
            top_cols[4].markdown(f"**Status**  \n{row_dict.get('approval_status', '-') or '-'}")
            reason = row_dict.get("reason_message", "")
            approval_link = row_dict.get("approval_link", "")
            if approval_link:
                st.markdown(f"[Seller Central approval link]({approval_link})")
            if reason:
                st.caption(reason)

            input_cols = st.columns([0.85, 0.8, 0.85, 1.15, 1.2, 2.2, 0.75], gap="small")
            decision_label = input_cols[0].selectbox(
                "Decision",
                options=list(BRAND_APPROVAL_DECISIONS.keys()),
                index=1,
                key=f"{key_base}_decision",
            )
            invoice_required_quantity = input_cols[1].text_input(
                "Invoice qty",
                value=row_dict.get("invoice_required_quantity", ""),
                key=f"{key_base}_invoice_qty",
            )
            invoice_unit_cost_gbp = input_cols[2].text_input(
                "Unit cost",
                value=row_dict.get("invoice_unit_cost_gbp", ""),
                key=f"{key_base}_unit_cost",
            )
            invoice_total_risk_gbp = input_cols[3].text_input(
                "Total risk",
                value=row_dict.get("invoice_total_risk_gbp", ""),
                key=f"{key_base}_total_risk",
            )
            invoice_artifact_reference = input_cols[4].text_input(
                "Invoice ref",
                value=row_dict.get("invoice_artifact_reference", ""),
                key=f"{key_base}_invoice_ref",
            )
            decision_reason = input_cols[5].text_input(
                "Note",
                value=row_dict.get("decision_reason", ""),
                key=f"{key_base}_note",
            )
            apply_decision = input_cols[6].checkbox("Apply", value=False, key=f"{key_base}_apply")

            if apply_decision:
                decision_rows.append(
                    {
                        **row_dict,
                        "operator_decision": BRAND_APPROVAL_DECISIONS[decision_label],
                        "invoice_required_quantity": invoice_required_quantity,
                        "invoice_unit_cost_gbp": invoice_unit_cost_gbp,
                        "invoice_total_risk_gbp": invoice_total_risk_gbp,
                        "invoice_artifact_reference": invoice_artifact_reference,
                        "decision_reason": decision_reason,
                    }
                )
            st.markdown("<div style='height:1px;background:#1f2937;margin:6px 0;'></div>", unsafe_allow_html=True)

    action_cols = st.columns([1.3, 4.0])
    if action_cols[0].button(
        "Save Decisions",
        type="primary",
        disabled=(len(decision_rows) == 0),
        key="o_brand_approval_save_decisions",
    ):
        result = submit_brand_approval_decision_batch(
            root=root_path,
            decision_rows=decision_rows,
            actor="operator_ui",
            source_reference="o_ui_brand_approval_queue",
        )
        skipped_count = len(result.get("skipped_rows", []))
        skipped_note = f" Skipped {skipped_count} row{'' if skipped_count == 1 else 's'}." if skipped_count else ""
        st.session_state["o_recent_brand_approval_notice"] = (
            f"Saved {result['events_applied']} brand approval decision"
            f"{'' if result['events_applied'] == 1 else 's'}."
            f"{skipped_note}"
        )
        st.rerun()
    action_cols[1].caption("Approval-blocked rows stay out of Product DB and repricer until approval clears.")


def _build_restock_workbench_display_df(filtered_df: pd.DataFrame) -> pd.DataFrame:
    if filtered_df.empty:
        return pd.DataFrame(columns=[RESTOCK_WORKBENCH_COLUMN_LABELS[col] for col in RESTOCK_WORKBENCH_COLUMNS])
    out = filtered_df.copy()
    for column in RESTOCK_WORKBENCH_COLUMNS:
        if column not in out.columns:
            out[column] = ""
    out = out[RESTOCK_WORKBENCH_COLUMNS].copy()
    return out.rename(columns=RESTOCK_WORKBENCH_COLUMN_LABELS)


def _restock_workable_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool)
    suggested = _norm_series(df, "suggested_action")
    suggested_qty = pd.to_numeric(_text_series(df, "old_suggested_qty"), errors="coerce").fillna(0)
    draft_qty = pd.to_numeric(_text_series(df, "order_qty_draft"), errors="coerce").fillna(0)
    latest_decision = _text_series(df, "latest_draft_decision_code")
    return suggested.isin({"full_restock", "test_restock"}) | (suggested_qty > 0) | (draft_qty > 0) | latest_decision.ne("")


_RESTOCK_TOKEN_LABELS = {
    "missing_supplier_cost": "Supplier cost missing",
    "missing_current_market_price": "Amazon price missing",
    "missing_refund_confidence": "Refund proof missing",
    "missing_inbound_cost_confidence": "Inbound/FBA cost proof missing",
    "missing_market_price": "Amazon price missing",
    "missing_forward_roi": "ROI missing",
    "missing_forward_profit": "Profit missing",
    "missing_net_fee_model": "Fee model missing",
    "proof_missing": "Proof missing",
    "likely_discontinued_candidate": "May be discontinued",
    "legacy_bridge_not_native_truth": "Old source evidence",
    "supplier_stock_not_verified": "Supplier stock not checked",
    "missing_from_latest_supplier_file": "Missing from latest supplier file",
    "exact_supplier_sku_or_barcode_found": "Found in supplier file",
    "not_found_in_latest_local_supplier_file": "Not found in latest supplier file",
    "not_checked_no_supplier_identity": "No supplier code/barcode to search",
    "not_checked_no_local_supplier_file": "No local supplier file",
    "not_checked_supplier_file_read_error": "Supplier file read error",
    "f_status_failed_local_file_available": "F stale/failed, local file available",
    "local_file_newer_than_f_status": "Newer local supplier file",
    "f_status_matches_local_file": "Source file matched",
    "missing_supplier_cost": "Supplier cost missing",
    "fee_proof_missing": "Fee proof missing",
    "missing_refund_confidence": "Refund proof missing",
    "missing_inbound_cost_confidence": "Inbound/FBA cost proof missing",
    "pack_or_moq_visible": "Pack/MOQ visible",
    "blocked_from_clean_buy": "Blocked from clean buy",
    "unknown_no_order_qty": "No order quantity yet",
    "review_only_not_po": "Review only",
    "market_or_history_clue_only": "Only market/history clues",
}


def _humanize_restock_token(raw_value: object) -> str:
    token = _normalize_text(raw_value)
    if token == "":
        return "-"
    if ":" in token:
        prefix, token = token.split(":", 1)
        prefix_label = prefix.replace("_", " ").strip().title()
    else:
        prefix_label = ""
    clean = token.strip().lower().replace(" ", "_")
    label = _RESTOCK_TOKEN_LABELS.get(clean)
    if not label:
        label = " ".join(clean.replace("_", " ").split()).capitalize()
    if prefix_label and prefix_label.lower() not in label.lower():
        return f"{prefix_label}: {label}"
    return label


def _humanize_restock_list(raw_value: object, *, limit: int = 3) -> str:
    text = _normalize_text(raw_value)
    if text == "":
        return "-"
    parts = [part.strip() for part in re.split(r"[|;]", text) if part.strip()]
    labels: list[str] = []
    for part in parts:
        label = _humanize_restock_token(part)
        if label not in labels:
            labels.append(label)
    if not labels:
        return "-"
    if len(labels) > limit:
        return ", ".join(labels[:limit]) + f", plus {len(labels) - limit} more"
    return ", ".join(labels)


def _restock_fact_value(row: pd.Series | dict[str, object], *fields: str, fallback: str = "-") -> str:
    for field in fields:
        value = _normalize_text(row.get(field, ""))
        if value != "":
            return value
    return fallback


def _restock_money_value(row: pd.Series | dict[str, object], field: str) -> str:
    value = _normalize_text(row.get(field, ""))
    if value == "":
        return "-"
    return f"GBP {value}"


def _restock_percent_value(row: pd.Series | dict[str, object], field: str) -> str:
    value = _normalize_text(row.get(field, ""))
    if value == "":
        return "-"
    return value if value.endswith("%") else f"{value}%"


def _restock_chip_tone(value: object) -> str:
    text = _normalize_text(value).lower()
    if text in {
        "",
        "ok",
        "ready",
        "verified",
        "clean",
        "pack_or_moq_visible",
        "supplier_stock_verified_in_stock",
        "exact_supplier_sku_or_barcode_found",
    }:
        return "good"
    if "missing" in text or "not_verified" in text or "blocked" in text or "unknown" in text or "not_found" in text or "failed" in text:
        return "warn"
    return ""


def _supplier_file_card_detail(row: pd.Series | dict[str, object]) -> str:
    state = _normalize_text(row.get("supplier_file_card_state", ""))
    file_name = _normalize_text(row.get("supplier_file_card_file_name", ""))
    file_time = _normalize_text(row.get("supplier_file_card_file_mtime_utc", ""))
    searched = _normalize_text(row.get("supplier_file_card_searched_rows", ""))
    handoff = _normalize_text(row.get("supplier_file_card_handoff_state", ""))
    if state == "":
        return ""
    if state == "exact_supplier_sku_or_barcode_found":
        result = "exact supplier SKU/barcode found"
    elif state == "not_found_in_latest_local_supplier_file":
        result = "exact supplier SKU/barcode not found"
    elif state == "not_checked_no_supplier_identity":
        result = "no supplier SKU/barcode to search"
    elif state == "not_checked_no_local_supplier_file":
        result = "no local supplier file found"
    elif state == "not_checked_supplier_file_read_error":
        result = "supplier file could not be read"
    else:
        result = _humanize_restock_token(state)
    parts = [result]
    if file_name:
        parts.append(f"file {file_name}")
    if searched:
        parts.append(f"{searched} rows searched")
    if file_time:
        parts.append(f"file time {file_time}")
    if handoff == "f_status_failed_local_file_available":
        parts.append("F stale/failed but local file available")
    return "; ".join(parts)


def _apply_supplier_file_card_context(review_df: pd.DataFrame, supplier_file_probe_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return review_df
    out = review_df.copy()
    for column in (
        "supplier_file_card_state",
        "supplier_file_card_file_name",
        "supplier_file_card_file_mtime_utc",
        "supplier_file_card_searched_rows",
        "supplier_file_card_handoff_state",
        "supplier_file_card_detail",
    ):
        if column not in out.columns:
            out[column] = ""
    if supplier_file_probe_df.empty:
        return out

    probe = supplier_file_probe_df.copy()
    for column in (
        "row_id",
        "seller_sku",
        "identity_match_state",
        "latest_supplier_file_name",
        "latest_supplier_file_mtime_utc",
        "searched_row_count",
        "source_index_handoff_state",
        "probe_utc",
    ):
        if column not in probe.columns:
            probe[column] = ""
        probe[column] = probe[column].map(_normalize_text)
    if "probe_utc" in probe.columns:
        probe = probe.sort_values("probe_utc")
    by_row_id = {
        _normalize_text(row.get("row_id", "")): row
        for _, row in probe.iterrows()
        if _normalize_text(row.get("row_id", ""))
    }
    by_sku = {
        _normalize_text(row.get("seller_sku", "")): row
        for _, row in probe.iterrows()
        if _normalize_text(row.get("seller_sku", ""))
    }
    for idx, row in out.iterrows():
        match = by_row_id.get(_normalize_text(row.get("row_id", "")))
        if match is None:
            match = by_sku.get(_normalize_text(row.get("seller_sku", "")))
        if match is None:
            continue
        out.at[idx, "supplier_file_card_state"] = _normalize_text(match.get("identity_match_state", ""))
        out.at[idx, "supplier_file_card_file_name"] = _normalize_text(match.get("latest_supplier_file_name", ""))
        out.at[idx, "supplier_file_card_file_mtime_utc"] = _normalize_text(match.get("latest_supplier_file_mtime_utc", ""))
        out.at[idx, "supplier_file_card_searched_rows"] = _normalize_text(match.get("searched_row_count", ""))
        out.at[idx, "supplier_file_card_handoff_state"] = _normalize_text(match.get("source_index_handoff_state", ""))
    for idx, row in out.iterrows():
        out.at[idx, "supplier_file_card_detail"] = _supplier_file_card_detail(row)
    return out


def _restock_card_next_action(row: pd.Series | dict[str, object]) -> str:
    decision = _normalize_text(row.get("latest_draft_decision_code", ""))
    if decision == "drop":
        return "Already drafted to drop. Keep it out of the buying path unless Luke changes the decision."
    if decision == "snooze":
        snooze_until = _normalize_text(row.get("latest_draft_snooze_until_utc", "")) or _normalize_text(row.get("snooze_until_utc", ""))
        suffix = f" until {snooze_until}" if snooze_until else ""
        return f"Already drafted to snooze{suffix}. Wait before reviewing again."
    if decision == "order_qty_draft":
        return "Draft quantity saved. Wait for supplier, pack, cost, and profit proof before any approval step."

    ready = bool(_restock_ready_mask(pd.DataFrame([dict(row)])).sum())
    if ready:
        return "Review the quantity and proof before local approval. This still does not create a purchase order."

    supplier_file_state = _normalize_text(row.get("supplier_file_card_state", ""))
    supplier_file_handoff = _normalize_text(row.get("supplier_file_card_handoff_state", ""))
    reason_text = " ".join(
        _normalize_text(row.get(field, "")).lower()
        for field in (
            "action_block_reason",
            "missing_input_reasons",
            "profit_check_message",
            "supplier_proof_missing_reasons",
            "supplier_batch_readiness_reasons",
            "supplier_match_state",
            "supplier_proof_state",
            "supplier_stock_state",
            "backorder_state",
            "supplier_cost_proof_state",
            "pack_moq_proof_state",
            "market_price_proof_state",
            "refund_proof_state",
            "inbound_cost_proof_state",
        )
    )

    if supplier_file_state == "not_found_in_latest_local_supplier_file":
        return "Investigate supplier. If this is discontinued, draft Drop; if it may return, draft Snooze."
    if supplier_file_state in {"not_checked_no_local_supplier_file", "not_checked_supplier_file_read_error"}:
        return "Wait for supplier-file proof or investigate the local supplier file before drafting a buy quantity."
    if supplier_file_state == "not_checked_no_supplier_identity":
        return "Investigate supplier code or barcode before this can move toward approval."
    if supplier_file_handoff in {"f_status_failed_local_file_available", "local_file_newer_than_f_status"} and supplier_file_state == "":
        return "Refresh local proof so O checks the newest local supplier file before deciding."

    if any(token in reason_text for token in ("missing_from_latest_supplier_file", "likely_discontinued_candidate")):
        return "Investigate supplier. If the item is gone, draft Drop; if uncertain, draft Snooze."
    if any(token in reason_text for token in ("supplier_stock_not_verified", "backorder_not_verified", "exact_supplier_match_not_proved")):
        return "Wait for supplier stock/backorder proof before approval."
    if any(token in reason_text for token in ("supplier_cost_not_proved", "bridge_cost_only", "missing_supplier_cost", "supplier_cost_not_exact")):
        return "Wait for exact supplier cost proof before approval."
    if any(token in reason_text for token in ("pack_moq_not_verified", "pack_moq")):
        return "Add pack/MOQ proof before approval."
    if any(token in reason_text for token in ("missing_current_market_price", "missing_market_price", "market_price", "needs_price_check")):
        return "Wait for market price proof before approval."
    if any(token in reason_text for token in ("missing_refund_confidence", "refund")):
        return "Wait for refund-impact proof before approval."
    if any(token in reason_text for token in ("missing_inbound_cost_confidence", "inbound")):
        return "Wait for inbound/FBA cost proof before approval."

    return "Keep on hold and wait for the missing proof shown above."


def _restock_card_html(row: pd.Series | dict[str, object]) -> str:
    title = html.escape(_display_plain(row.get("title", ""), "Untitled product"))
    supplier = html.escape(_display_plain(row.get("supplier_name", ""), "Unknown supplier"))
    image_url = _normalize_text(row.get("main_image", ""))
    image_html = _image_frame_html(image_url, size=76) if image_url else (
        "<div style='width:76px;height:76px;border:1px solid #e5e7eb;border-radius:10px;background:#f8fafc;"
        "display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:11px;font-weight:800;'>No image</div>"
    )
    ready = bool(_restock_ready_mask(pd.DataFrame([dict(row)])).sum())
    suggested_action = _normalize_text(row.get("suggested_action", ""))
    tone = "good" if ready else ("warn" if suggested_action in {"full_restock", "test_restock"} else "neutral")
    facts = [
        ("Stock", _restock_fact_value(row, "available_now", fallback="0")),
        ("Already ordered", _restock_fact_value(row, "ordered_open", fallback="0")),
        ("30d velocity", _restock_fact_value(row, "velocity_30d")),
        ("Suggested qty", _restock_fact_value(row, "old_suggested_qty")),
        ("Buy cost", _restock_money_value(row, "current_supplier_cost_gbp")),
        ("Amazon price", _restock_money_value(row, "current_amazon_price_gbp")),
        ("Profit/unit", _restock_money_value(row, "expected_profit_per_unit_gbp")),
        ("ROI", _restock_percent_value(row, "expected_roi_pct")),
    ]
    fact_html = "".join(
        "<div class='o-restock-fact'>"
        f"<div class='o-restock-fact-label'>{html.escape(label)}</div>"
        f"<div class='o-restock-fact-value'>{html.escape(value)}</div>"
        "</div>"
        for label, value in facts
    )
    proof_fields = [
        ("Supplier stock", "supplier_stock_state"),
        ("Supplier file", "supplier_file_card_state"),
        ("Supplier cost", "supplier_cost_proof_state"),
        ("Fees", "fee_proof_state"),
        ("Refunds", "refund_proof_state"),
        ("Inbound/FBA", "inbound_cost_proof_state"),
        ("Pack/MOQ", "pack_moq_proof_state"),
    ]
    proof_html = ""
    for label, field in proof_fields:
        raw_value = _normalize_text(row.get(field, ""))
        if field == "supplier_file_card_state" and raw_value == "":
            continue
        chip_tone = _restock_chip_tone(raw_value)
        tone_class = f" {chip_tone}" if chip_tone else ""
        proof_html += (
            f"<span class='o-restock-chip{tone_class}'>"
            f"{html.escape(label)}: {html.escape(_humanize_restock_token(raw_value))}"
            "</span>"
        )
    blocker = _humanize_restock_list(
        _restock_fact_value(row, "action_block_reason", "missing_input_reasons", "profit_check_message", fallback=""),
        limit=4,
    )
    blocker_html = "" if blocker == "-" else f"<div class='o-restock-blocker'><strong>Why not clean yet:</strong> {html.escape(blocker)}</div>"
    supplier_file_detail = _normalize_text(row.get("supplier_file_card_detail", ""))
    supplier_file_html = (
        ""
        if supplier_file_detail == ""
        else f"<div class='o-restock-meta'><strong>Supplier file:</strong> {html.escape(supplier_file_detail)}</div>"
    )
    next_action = _restock_card_next_action(row)
    next_action_html = f"<div class='o-restock-next-action'><strong>Safest next action:</strong> {html.escape(next_action)}</div>"
    decision = _humanize_restock_token(row.get("latest_draft_decision_code", "")) if _normalize_text(row.get("latest_draft_decision_code", "")) else "No Luke decision yet"
    note = _normalize_text(row.get("latest_draft_note", ""))
    decision_html = (
        f"<div class='o-restock-meta'><strong>Luke decision:</strong> {html.escape(decision)}"
        f"{' - ' + html.escape(note) if note else ''}</div>"
    )
    return (
        f"<div class='o-restock-card {tone}'>"
        "<div class='o-restock-top'>"
        f"{image_html}"
        "<div>"
        f"<div class='o-restock-title'>{title}</div>"
        f"<div class='o-restock-meta'><strong>Supplier:</strong> {supplier}</div>"
        f"{decision_html}"
        "</div>"
        "</div>"
        f"<div class='o-restock-grid'>{fact_html}</div>"
        f"<div class='o-restock-proof'>{proof_html}</div>"
        f"{blocker_html}"
        f"{supplier_file_html}"
        f"{next_action_html}"
        "</div>"
    )


def _restock_card_control_key(row: pd.Series | dict[str, object], suffix: str) -> str:
    identity = (
        _normalize_text(row.get("row_id", ""))
        or _normalize_text(row.get("seller_sku", ""))
        or _normalize_text(row.get("asin", ""))
        or "row"
    )
    return f"o_restock_card_{_supplier_key_fragment(identity)}_{_supplier_key_fragment(suffix)}"


def _restock_card_default_draft_qty(row: pd.Series | dict[str, object]) -> int:
    return (
        _positive_int_value(row.get("order_qty_draft", ""))
        or _positive_int_value(row.get("old_suggested_qty", ""))
        or 1
    )


RESTOCK_CARD_STOCK_LABEL_TO_STATE = {
    "Not verified": "supplier_stock_not_verified",
    "In stock": "supplier_stock_verified_in_stock",
    "Out of stock": "supplier_stock_verified_zero",
}
RESTOCK_CARD_BACKORDER_LABEL_TO_STATE = {
    "Not verified": "backorder_not_verified",
    "No backorder": "backorder_none_confirmed",
    "Backorder wait": "backorder_wait",
}
RESTOCK_CARD_PACK_LABEL_TO_STATE = {
    "Not verified": "pack_moq_not_verified",
    "Verified": "pack_moq_verified",
}
RESTOCK_CARD_EXACT_MATCH_OPTIONS = ("Not proved", "Exact SKU/barcode visible", "Not found in latest supplier file")


def _label_for_restock_state(value: object, label_to_state: dict[str, str], default_label: str) -> str:
    state = _normalize_text(value)
    for label, mapped_state in label_to_state.items():
        if state == mapped_state:
            return label
    return default_label


def _restock_card_exact_match_label(row: pd.Series | dict[str, object]) -> str:
    supplier_file_state = _normalize_text(row.get("supplier_file_card_state", ""))
    supplier_proof_state = _normalize_text(row.get("supplier_proof_state", ""))
    if supplier_file_state == "not_found_in_latest_local_supplier_file":
        return "Not found in latest supplier file"
    if "exact" in supplier_proof_state and "proved" in supplier_proof_state:
        return "Exact SKU/barcode visible"
    return "Not proved"


def _restock_card_pack_label(row: pd.Series | dict[str, object]) -> str:
    state = _normalize_text(row.get("pack_moq_proof_state", ""))
    if state in {"pack_moq_verified", "pack_or_moq_visible"}:
        return "Verified"
    return "Not verified"


def _restock_card_supplier_file_reference(row: pd.Series | dict[str, object]) -> str:
    return (
        _normalize_text(row.get("supplier_file_card_file_name", ""))
        or _normalize_text(row.get("latest_supplier_file_name", ""))
        or _normalize_text(row.get("supplier_file_reference", ""))
    )


def _restock_card_supplier_file_asof(row: pd.Series | dict[str, object]) -> str:
    return (
        _normalize_text(row.get("supplier_file_card_file_mtime_utc", ""))
        or _normalize_text(row.get("supplier_file_asof_utc", ""))
    )


def _refresh_restock_card_local_chain(root_path: Path) -> None:
    build_restock_session_view(root=root_path)
    build_restock_supplier_batch_drafts(root=root_path, refresh_session=False)
    build_supplier_file_presence_probe(root=root_path, refresh_batches=False)
    build_purchase_approval_preview(root=root_path, refresh_batches=False)
    build_purchase_approval_guardrails(root=root_path, refresh_preview=False)
    build_po_draft_readiness_preview(root=root_path, refresh_guardrails=False)
    build_po_line_design_preview(root=root_path, refresh_readiness=False)
    build_po_draft_packet_review(root=root_path, refresh_design=False)
    build_po_draft_hold_review(root=root_path, refresh_packet_review=False)
    build_po_draft_file_shape_preview(root=root_path, refresh_hold_review=False)
    build_po_preview_construction_summary(root=root_path, refresh_file_shape=False)
    build_po_draft_review_controls(root=root_path, refresh_construction_summary=False)
    build_po_draft_export_preview(root=root_path, refresh_review_controls=False)
    build_po_draft_export_gate(root=root_path, refresh_export_preview=False)


def _render_restock_card_local_controls(row: pd.Series | dict[str, object], *, root_path: Path) -> None:
    import streamlit as st

    row_dict = dict(row)
    row_id = _normalize_text(row_dict.get("row_id", ""))
    sku_or_asin = _normalize_text(row_dict.get("seller_sku", "")) or _normalize_text(row_dict.get("asin", ""))
    disabled = row_id == "" or sku_or_asin == ""
    note = st.text_input(
        "Local note",
        value="",
        key=_restock_card_control_key(row_dict, "note"),
        placeholder="Optional note",
        disabled=disabled,
    )
    control_cols = st.columns([1.0, 1.0, 1.0, 2.1], gap="small")
    draft_qty = control_cols[0].number_input(
        "Draft qty",
        min_value=1,
        step=1,
        value=_restock_card_default_draft_qty(row_dict),
        key=_restock_card_control_key(row_dict, "draft_qty"),
        disabled=disabled,
    )
    snooze_until = control_cols[1].date_input(
        "Snooze until",
        value=_next_monday(),
        key=_restock_card_control_key(row_dict, "snooze_until"),
        disabled=disabled,
    )
    if control_cols[0].button("Save qty draft", key=_restock_card_control_key(row_dict, "save_qty"), disabled=disabled):
        try:
            saved = submit_restock_session_draft_decision(
                root=root_path,
                session_row=row_dict,
                decision_code="order_qty_draft",
                draft_order_qty=draft_qty,
                decision_note=note,
                actor="operator_ui",
                event_source_reference="o_ui_restock_session_card",
            )
            _refresh_restock_card_local_chain(root_path)
            st.session_state["o_recent_submit_notice"] = (
                f"Saved local draft quantity for {saved.get('seller_sku', '') or saved.get('asin', '')}."
            )
            st.rerun()
        except ValueError as exc:
            st.error(f"Draft not saved: {exc}")
    if control_cols[1].button("Snooze", key=_restock_card_control_key(row_dict, "save_snooze"), disabled=disabled):
        try:
            saved = submit_restock_session_draft_decision(
                root=root_path,
                session_row=row_dict,
                decision_code="snooze",
                snooze_until_utc=snooze_until,
                decision_note=note,
                actor="operator_ui",
                event_source_reference="o_ui_restock_session_card",
            )
            _refresh_restock_card_local_chain(root_path)
            st.session_state["o_recent_submit_notice"] = (
                f"Snoozed {saved.get('seller_sku', '') or saved.get('asin', '')} locally."
            )
            st.rerun()
        except ValueError as exc:
            st.error(f"Snooze not saved: {exc}")
    if control_cols[2].button("Drop", key=_restock_card_control_key(row_dict, "save_drop"), disabled=disabled):
        try:
            saved = submit_restock_session_draft_decision(
                root=root_path,
                session_row=row_dict,
                decision_code="drop",
                decision_note=note,
                actor="operator_ui",
                event_source_reference="o_ui_restock_session_card",
            )
            _refresh_restock_card_local_chain(root_path)
            st.session_state["o_recent_submit_notice"] = (
                f"Saved local drop draft for {saved.get('seller_sku', '') or saved.get('asin', '')}."
            )
            st.rerun()
        except ValueError as exc:
            st.error(f"Drop not saved: {exc}")
    control_cols[3].caption("Card controls are local drafts only. They do not buy stock or create purchase orders.")


def _compose_supplier_card_proof_note(*, exact_match_label: str, cost_note: object, proof_note: object) -> str:
    parts = [f"Exact match: {_normalize_text(exact_match_label)}"]
    cost_text = _normalize_text(cost_note)
    note_text = _normalize_text(proof_note)
    if cost_text:
        parts.append(f"Cost note: {cost_text}")
    if note_text:
        parts.append(note_text)
    return " | ".join(parts)


def _render_restock_card_supplier_proof_controls(row: pd.Series | dict[str, object], *, root_path: Path) -> None:
    import streamlit as st

    row_dict = dict(row)
    row_id = _normalize_text(row_dict.get("row_id", ""))
    sku_or_asin = _normalize_text(row_dict.get("seller_sku", "")) or _normalize_text(row_dict.get("asin", ""))
    disabled = row_id == "" or sku_or_asin == ""
    expander_label = f"Local supplier proof - {sku_or_asin or 'row'}"
    with st.expander(expander_label, expanded=False):
        st.caption(
            "Local proof only. Exact match and cost entries are notes until native O proof confirms them."
        )
        exact_label = st.selectbox(
            "Exact match",
            options=list(RESTOCK_CARD_EXACT_MATCH_OPTIONS),
            index=list(RESTOCK_CARD_EXACT_MATCH_OPTIONS).index(_restock_card_exact_match_label(row_dict)),
            key=_restock_card_control_key(row_dict, "supplier_exact_match"),
            disabled=disabled,
        )
        supplier_cols = st.columns([1.0, 0.8, 1.0, 1.0, 1.2], gap="small")
        stock_default = _label_for_restock_state(
            row_dict.get("supplier_stock_state", ""),
            RESTOCK_CARD_STOCK_LABEL_TO_STATE,
            "Not verified",
        )
        stock_label = supplier_cols[0].selectbox(
            "Stock proof",
            options=list(RESTOCK_CARD_STOCK_LABEL_TO_STATE.keys()),
            index=list(RESTOCK_CARD_STOCK_LABEL_TO_STATE.keys()).index(stock_default),
            key=_restock_card_control_key(row_dict, "supplier_stock_state"),
            disabled=disabled,
        )
        stock_qty = supplier_cols[1].text_input(
            "Stock qty",
            value=_normalize_text(row_dict.get("supplier_stock_qty", "")),
            key=_restock_card_control_key(row_dict, "supplier_stock_qty"),
            disabled=disabled,
        )
        backorder_default = _label_for_restock_state(
            row_dict.get("backorder_state", ""),
            RESTOCK_CARD_BACKORDER_LABEL_TO_STATE,
            "Not verified",
        )
        backorder_label = supplier_cols[2].selectbox(
            "Backorder",
            options=list(RESTOCK_CARD_BACKORDER_LABEL_TO_STATE.keys()),
            index=list(RESTOCK_CARD_BACKORDER_LABEL_TO_STATE.keys()).index(backorder_default),
            key=_restock_card_control_key(row_dict, "supplier_backorder_state"),
            disabled=disabled,
        )
        backorder_eta = supplier_cols[3].text_input(
            "Backorder ETA",
            value=_normalize_text(row_dict.get("backorder_eta_utc", "")),
            key=_restock_card_control_key(row_dict, "supplier_backorder_eta"),
            disabled=disabled,
        )
        supplier_file_asof = supplier_cols[4].text_input(
            "File date",
            value=_restock_card_supplier_file_asof(row_dict),
            key=_restock_card_control_key(row_dict, "supplier_file_asof"),
            disabled=disabled,
        )
        supplier_ref_cols = st.columns([1.3, 1.4, 1.6], gap="small")
        supplier_file_ref = supplier_ref_cols[0].text_input(
            "File/ref",
            value=_restock_card_supplier_file_reference(row_dict),
            key=_restock_card_control_key(row_dict, "supplier_file_ref"),
            disabled=disabled,
        )
        cost_note = supplier_ref_cols[1].text_input(
            "Cost note",
            value="",
            key=_restock_card_control_key(row_dict, "supplier_cost_note"),
            placeholder="Example: cost GBP 3.20 visible",
            disabled=disabled,
        )
        supplier_note = supplier_ref_cols[2].text_input(
            "Supplier proof note",
            value="",
            key=_restock_card_control_key(row_dict, "supplier_proof_note"),
            disabled=disabled,
        )
        if st.button("Save supplier proof", key=_restock_card_control_key(row_dict, "save_supplier_proof"), disabled=disabled):
            try:
                saved = submit_restock_session_supplier_proof_event(
                    root=root_path,
                    session_row=row_dict,
                    supplier_stock_state=RESTOCK_CARD_STOCK_LABEL_TO_STATE.get(stock_label, "supplier_stock_not_verified"),
                    supplier_stock_qty=stock_qty,
                    backorder_state=RESTOCK_CARD_BACKORDER_LABEL_TO_STATE.get(backorder_label, "backorder_not_verified"),
                    backorder_eta_utc=backorder_eta,
                    supplier_file_asof_utc=supplier_file_asof,
                    supplier_file_reference=supplier_file_ref,
                    proof_note=_compose_supplier_card_proof_note(
                        exact_match_label=exact_label,
                        cost_note=cost_note,
                        proof_note=supplier_note,
                    ),
                    actor="operator_ui",
                    event_source_reference="o_ui_restock_session_card_supplier_proof",
                )
                _refresh_restock_card_local_chain(root_path)
                st.session_state["o_recent_submit_notice"] = (
                    f"Saved local supplier proof for {saved.get('seller_sku', '') or saved.get('asin', '')}."
                )
                st.rerun()
            except ValueError as exc:
                st.error(f"Supplier proof not saved: {exc}")

        pack_cols = st.columns([1.0, 0.8, 0.8, 0.8, 1.3], gap="small")
        pack_label = pack_cols[0].selectbox(
            "Pack/MOQ",
            options=list(RESTOCK_CARD_PACK_LABEL_TO_STATE.keys()),
            index=list(RESTOCK_CARD_PACK_LABEL_TO_STATE.keys()).index(_restock_card_pack_label(row_dict)),
            key=_restock_card_control_key(row_dict, "pack_moq_state"),
            disabled=disabled,
        )
        pack_multiple = pack_cols[1].text_input(
            "Pack",
            value=_normalize_text(row_dict.get("pack_multiple", "")),
            key=_restock_card_control_key(row_dict, "pack_multiple"),
            disabled=disabled,
        )
        supplier_moq = pack_cols[2].text_input(
            "MOQ",
            value=_normalize_text(row_dict.get("supplier_moq", "")),
            key=_restock_card_control_key(row_dict, "supplier_moq"),
            disabled=disabled,
        )
        valid_order_step = pack_cols[3].text_input(
            "Step",
            value=_normalize_text(row_dict.get("valid_order_step", "")),
            key=_restock_card_control_key(row_dict, "valid_order_step"),
            disabled=disabled,
        )
        pack_file_ref = pack_cols[4].text_input(
            "Pack file/ref",
            value="",
            key=_restock_card_control_key(row_dict, "pack_file_ref"),
            disabled=disabled,
        )
        pack_note = st.text_input(
            "Pack/MOQ note",
            value="",
            key=_restock_card_control_key(row_dict, "pack_moq_note"),
            disabled=disabled,
        )
        if st.button("Save pack/MOQ proof", key=_restock_card_control_key(row_dict, "save_pack_moq"), disabled=disabled):
            try:
                saved = submit_restock_session_pack_moq_proof_event(
                    root=root_path,
                    session_row=row_dict,
                    pack_moq_proof_state=RESTOCK_CARD_PACK_LABEL_TO_STATE.get(pack_label, "pack_moq_not_verified"),
                    pack_multiple=pack_multiple,
                    supplier_moq=supplier_moq,
                    valid_order_step=valid_order_step,
                    proof_file_reference=pack_file_ref,
                    proof_note=pack_note,
                    actor="operator_ui",
                    event_source_reference="o_ui_restock_session_card_pack_moq",
                )
                _refresh_restock_card_local_chain(root_path)
                st.session_state["o_recent_submit_notice"] = (
                    f"Saved local pack/MOQ proof for {saved.get('seller_sku', '') or saved.get('asin', '')}."
                )
                st.rerun()
            except ValueError as exc:
                st.error(f"Pack/MOQ proof not saved: {exc}")


def _build_restock_site_supplier_worklist(review_df: pd.DataFrame, summary_df: pd.DataFrame) -> pd.DataFrame:
    if review_df.empty:
        return pd.DataFrame(
            columns=[
                "supplier",
                "review_products",
                "all_products",
                "clean_buy_products",
                "blocked_products",
                "draft_qty_products",
                "main_blocker",
            ]
        )

    work = review_df.copy()
    for column in (
        "supplier_name",
        "row_status",
        "seller_sku",
        "asin",
        "title",
        "suggested_action",
        "old_suggested_qty",
        "order_qty_draft",
        "latest_draft_decision_code",
        "action_block_reason",
    ):
        if column not in work.columns:
            work[column] = ""
    work["_supplier_label"] = work["supplier_name"].map(_supplier_label)
    work["_workable_candidate"] = _restock_workable_mask(work)

    review_source = work[work["_workable_candidate"]].copy()
    if review_source.empty:
        review_source = work.copy()

    summary_lookup: dict[str, pd.Series] = {}
    if not summary_df.empty and "supplier_name" in summary_df.columns:
        summary_work = summary_df.copy()
        summary_work["_supplier_label"] = summary_work["supplier_name"].map(_supplier_label)
        for _, summary_row in summary_work.iterrows():
            supplier = _normalize_text(summary_row.get("_supplier_label", ""))
            if supplier and supplier not in summary_lookup:
                summary_lookup[supplier] = summary_row

    rows: list[dict[str, object]] = []
    for supplier, supplier_review_df in review_source.groupby("_supplier_label", sort=False):
        supplier_all_df = work[work["_supplier_label"] == supplier].copy()
        ready_mask = _restock_ready_mask(supplier_review_df)
        blocked_mask = _restock_blocked_mask(supplier_review_df)
        draft_qty_products = int(
            _text_series(supplier_review_df, "order_qty_draft").map(lambda value: _normalize_text(value) != "").sum()
        )
        summary_row = summary_lookup.get(_normalize_text(supplier))
        main_blocker = ""
        if summary_row is not None:
            main_blocker = _humanize_restock_list(summary_row.get("top_block_reasons", ""), limit=2)
        if main_blocker in {"", "-"}:
            blockers = _top_restock_blocker_items(supplier_review_df, limit=1)
            main_blocker = _humanize_restock_token(blockers[0][0]) if blockers else "-"

        rows.append(
            {
                "supplier": _normalize_text(supplier) or "(Unknown supplier)",
                "review_products": int(len(supplier_review_df.index)),
                "all_products": int(len(supplier_all_df.index)),
                "clean_buy_products": int(ready_mask.sum()) if not ready_mask.empty else 0,
                "blocked_products": int(blocked_mask.sum()) if not blocked_mask.empty else 0,
                "draft_qty_products": draft_qty_products,
                "main_blocker": main_blocker,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_supplier_sort"] = out["supplier"].map(lambda value: _normalize_text(value).lower())
    out = out.sort_values(
        by=["clean_buy_products", "review_products", "_supplier_sort"],
        ascending=[False, False, True],
    ).drop(columns=["_supplier_sort"])
    return out.reset_index(drop=True)


def _restock_site_hero_html() -> str:
    return (
        "<div class='o-restock-site-hero'>"
        "<div class='o-restock-site-title'>Restocking starts with suppliers</div>"
        "<div class='o-restock-site-copy'>"
        "This page keeps the warehouse-style data out of the way. Start with the supplier queue, "
        "open one supplier, then check only the products that need Luke's attention."
        "</div>"
        "</div>"
    )


def _restock_path_card_html(step: str, title: str, body: str) -> str:
    return (
        "<div class='o-restock-path-card'>"
        f"<div class='o-restock-path-step'>{html.escape(_normalize_text(step))}</div>"
        f"<div class='o-restock-path-title'>{html.escape(_normalize_text(title))}</div>"
        f"<div class='o-restock-path-body'>{html.escape(_normalize_text(body))}</div>"
        "</div>"
    )


def _restock_supplier_card_html(row: pd.Series | dict[str, object]) -> str:
    supplier = _display_plain(row.get("supplier", ""), "(Unknown supplier)")
    review_products = _display_plain(row.get("review_products", "0"), "0")
    clean_buy_products = _display_plain(row.get("clean_buy_products", "0"), "0")
    blocked_products = _display_plain(row.get("blocked_products", "0"), "0")
    draft_qty_products = _display_plain(row.get("draft_qty_products", "0"), "0")
    blocker = _display_plain(row.get("main_blocker", ""), "-")
    tone = "ready" if int(float(clean_buy_products or 0)) > 0 else "blocked"
    return (
        f"<div class='o-restock-supplier-card {tone}'>"
        f"<div class='o-restock-supplier-name'>{html.escape(supplier)}</div>"
        "<div class='o-restock-supplier-stats'>"
        f"{html.escape(review_products)} product{'' if review_products == '1' else 's'} to check. "
        f"{html.escape(clean_buy_products)} clean-buy candidate{'' if clean_buy_products == '1' else 's'}. "
        f"{html.escape(blocked_products)} blocked."
        "</div>"
        f"<div class='o-restock-supplier-note'>Draft qty saved: {html.escape(draft_qty_products)}. Main blocker: {html.escape(blocker)}.</div>"
        "</div>"
    )


def _build_restock_scanner_check_summary(root_path: Path) -> dict[str, object]:
    latest_events_df = _latest_feeder_review_event_by_identity(load_feeder_review_events_df(root=root_path))
    lane_counts: dict[str, int] = {}
    supplier_names: set[str] = set()
    total_waiting = 0
    pack_count = 0
    suggested_lane = "Passes"
    suggested_snapshot = "latest"
    suggested_waiting = 0

    for lane_label, lane_spec in FEEDER_REVIEW_LANE_SPECS.items():
        options = list_feeder_review_pack_options(
            root=root_path,
            pack_type=lane_spec["pack_type"],
            lane_filter=lane_spec["lane_filter"],
            lane_label=lane_label,
        )
        lane_waiting = 0
        for option in options:
            snapshot = _normalize_text(option.get("id", ""))
            if not snapshot:
                continue
            counts = _feeder_review_lane_todo_counts(
                root_path,
                snapshot,
                pack_type=lane_spec["pack_type"],
                lane_filter=lane_spec["lane_filter"],
                latest_events_df=latest_events_df,
            )
            waiting = _price_list_int(counts.get("undecided_rows", 0))
            if waiting <= 0:
                continue
            pack_count += 1
            lane_waiting += waiting
            if waiting > suggested_waiting:
                suggested_lane = lane_label
                suggested_snapshot = snapshot
                suggested_waiting = waiting
            summary = load_feeder_review_summary(root=root_path, review_pack_snapshot=snapshot)
            supplier_name = (
                _normalize_text(summary.get("active_supplier_label", ""))
                or _normalize_text(summary.get("active_supplier_id", ""))
            )
            if supplier_name:
                supplier_names.add(supplier_name)
        if lane_waiting > 0:
            lane_counts[lane_label] = lane_waiting
            total_waiting += lane_waiting

    return {
        "waiting_count": total_waiting,
        "supplier_count": len(supplier_names),
        "pack_count": pack_count,
        "lane_counts": lane_counts,
        "suggested_lane": suggested_lane,
        "suggested_snapshot": suggested_snapshot,
    }


def _restock_scanner_lane_text(lane_counts: dict[str, int]) -> str:
    display_labels = {
        "Passes": ("clean pass", "clean passes"),
        "Manual review": ("manual check", "manual checks"),
        "Near misses": ("close call", "close calls"),
    }
    parts: list[str] = []
    for lane_label in FEEDER_REVIEW_LANE_SPECS:
        count = _price_list_int(lane_counts.get(lane_label, 0))
        if count <= 0:
            continue
        singular, plural = display_labels.get(lane_label, (lane_label.lower(), f"{lane_label.lower()}s"))
        parts.append(f"{count} {singular if count == 1 else plural}")
    return ", ".join(parts)


def _render_restock_site_overview(
    root_path: Path,
    review_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> None:
    import streamlit as st

    supplier_worklist_df = _build_restock_site_supplier_worklist(review_df, summary_df)
    scanner_check_summary = _build_restock_scanner_check_summary(root_path)
    scanner_waiting_count = _price_list_int(scanner_check_summary.get("waiting_count", 0))
    workable_mask = _restock_workable_mask(review_df)
    review_products = int(workable_mask.sum()) if not workable_mask.empty else 0
    if review_products == 0 and not review_df.empty:
        review_products = int(len(review_df.index))
    clean_buy_products = int(_restock_ready_mask(review_df).sum()) if not review_df.empty else 0
    blocked_products = int(_restock_blocked_mask(review_df).sum()) if not review_df.empty else 0

    st.markdown(_restock_site_hero_html(), unsafe_allow_html=True)
    if clean_buy_products:
        st.markdown(
            _operator_decision_card_html(
                "Clean-buy candidates are waiting",
                f"{clean_buy_products} product{'' if clean_buy_products == 1 else 's'} look ready for Luke to review. Opening a supplier only changes this screen.",
                "good",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            _operator_decision_card_html(
                "No clean buy is ready yet",
                "The useful job is to clear supplier proof and product blockers. Nothing on this page buys stock automatically.",
                "warn",
            ),
            unsafe_allow_html=True,
        )

    if scanner_waiting_count > 0:
        lane_text = _restock_scanner_lane_text(scanner_check_summary.get("lane_counts", {}))
        supplier_count = _price_list_int(scanner_check_summary.get("supplier_count", 0))
        supplier_phrase = (
            f" across {supplier_count} supplier{'' if supplier_count == 1 else 's'}"
            if supplier_count
            else ""
        )
        detail = f"{lane_text}{supplier_phrase}" if lane_text else f"{scanner_waiting_count} waiting"
        st.markdown(
            _operator_decision_card_html(
                "Supplier Intake should happen first",
                (
                    f"{scanner_waiting_count} price-list scanner product"
                    f"{'' if scanner_waiting_count == 1 else 's'} need Luke's confirmation before restocking. "
                    f"Waiting now: {detail}."
                ),
                "warn",
            ),
            unsafe_allow_html=True,
        )
        intake_cols = st.columns([1.15, 3.0], gap="small")
        if intake_cols[0].button("Open Supplier Intake", type="primary", key="o_restock_open_supplier_intake"):
            suggested_lane = _normalize_text(scanner_check_summary.get("suggested_lane", "Passes")) or "Passes"
            if suggested_lane in FEEDER_REVIEW_LANE_SPECS:
                st.session_state["o_feeder_review_requested_lane"] = suggested_lane
            suggested_snapshot = _normalize_text(scanner_check_summary.get("suggested_snapshot", ""))
            if suggested_snapshot:
                st.session_state["o_feeder_review_requested_pack_snapshot"] = suggested_snapshot
            st.session_state["o_feeder_review_show_pack_history"] = False
            st.session_state["o_active_page_route"] = "new_product_review"
            try:
                st.query_params["page"] = "new_product_review"
            except Exception:
                st.experimental_set_query_params(page="new_product_review")
            st.rerun()
        intake_cols[1].caption(
            "This only opens the review page. It does not run the scanner, change queues, buy stock, or write Sheets."
        )
    else:
        st.markdown(
            _operator_decision_card_html(
                "Supplier Intake is clear",
                "0 price-list scanner products are waiting for Luke before this restocking check.",
                "neutral",
            ),
            unsafe_allow_html=True,
        )

    metric_row_one = st.columns(2, gap="medium")
    metric_row_two = st.columns(2, gap="medium")
    metric_row_one[0].markdown(
        _operator_metric_card_html("Products to check", review_products, "Filtered to useful restocking work", "neutral"),
        unsafe_allow_html=True,
    )
    metric_row_one[1].markdown(
        _operator_metric_card_html("Supplier groups", len(supplier_worklist_df.index), "Open one supplier at a time", "neutral"),
        unsafe_allow_html=True,
    )
    metric_row_two[0].markdown(
        _operator_metric_card_html("Clean-buy candidates", clean_buy_products, "Still needs Luke's choice", "good" if clean_buy_products else "warn"),
        unsafe_allow_html=True,
    )
    metric_row_two[1].markdown(
        _operator_metric_card_html("Blocked products", blocked_products, "Proof or safety issue visible", "warn" if blocked_products else "good"),
        unsafe_allow_html=True,
    )

    path_cols = st.columns(3, gap="medium")
    path_cols[0].markdown(
        _restock_path_card_html("Step 1", "Choose a supplier", "Pick the supplier group that has the most useful restocking work."),
        unsafe_allow_html=True,
    )
    path_cols[1].markdown(
        _restock_path_card_html("Step 2", "Review products", "Only then show product cards, costs, proof, and blockers."),
        unsafe_allow_html=True,
    )
    path_cols[2].markdown(
        _restock_path_card_html("Step 3", "Save local notes", "Drafts stay local and never create a purchase order by themselves."),
        unsafe_allow_html=True,
    )

    st.markdown("### Supplier queue")
    if supplier_worklist_df.empty:
        st.info("No restocking supplier queue is available yet.")
        return

    supplier_options = supplier_worklist_df["supplier"].tolist()
    current_supplier = _normalize_text(st.session_state.get("o_restock_selected_supplier", ""))
    if current_supplier not in supplier_options:
        current_supplier = supplier_options[0]
    selected_supplier = st.selectbox(
        "Choose supplier",
        options=supplier_options,
        index=supplier_options.index(current_supplier),
        key="o_restock_overview_supplier_pick",
        format_func=lambda value: f"{value} ({int(supplier_worklist_df[supplier_worklist_df['supplier'] == value]['review_products'].iloc[0])})",
    )
    action_cols = st.columns([1.1, 3.0], gap="small")
    if action_cols[0].button("Open supplier review", type="primary", key="o_restock_open_supplier_review"):
        st.session_state["o_restock_selected_supplier"] = selected_supplier
        st.session_state["o_restock_requested_site_mode"] = "Supplier Review"
        st.rerun()
    action_cols[1].caption("This opens the local review screen only. It does not buy stock, change prices, write Sheets, or touch scanner queues.")

    for idx, (_, supplier_row) in enumerate(supplier_worklist_df.head(8).iterrows(), start=1):
        card_cols = st.columns([4.0, 0.9], gap="small")
        card_cols[0].markdown(_restock_supplier_card_html(supplier_row), unsafe_allow_html=True)
        supplier_name = _normalize_text(supplier_row.get("supplier", ""))
        if card_cols[1].button("Review", key=f"o_restock_supplier_card_{idx}_{_supplier_key_fragment(supplier_name)}"):
            st.session_state["o_restock_selected_supplier"] = supplier_name
            st.session_state["o_restock_requested_site_mode"] = "Supplier Review"
            st.rerun()


def _render_restock_workbench_overview(filtered_df: pd.DataFrame) -> None:
    import streamlit as st

    if filtered_df.empty:
        st.info("No rows match the current Restocking filters.")
        return

    ready_mask = _restock_ready_mask(filtered_df)
    blocked_mask = _restock_blocked_mask(filtered_df)
    draft_qty_rows = (
        int(_text_series(filtered_df, "order_qty_draft").map(lambda value: _normalize_text(value) != "").sum())
        if "order_qty_draft" in filtered_df.columns
        else 0
    )
    supplier_count = filtered_df["_supplier_label"].nunique() if "_supplier_label" in filtered_df.columns else _supplier_count(filtered_df)
    ready_rows = int(ready_mask.sum()) if not ready_mask.empty else 0
    blocked_rows = int(blocked_mask.sum()) if not blocked_mask.empty else 0
    if ready_rows > 0:
        st.markdown(
            _operator_decision_card_html(
                "Manual review rows are available",
                f"{ready_rows} row{'' if ready_rows == 1 else 's'} look ready for manual review. Luke still has to save any draft decision himself.",
                "good",
            ),
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            _operator_decision_card_html(
                "No clean-buy rows in this view",
                "Use the product cards below to see what proof is missing and why the buy is blocked before any buying decision.",
                "warn",
            ),
            unsafe_allow_html=True,
        )

    metric_cols = st.columns(4, gap="small")
    metric_cols[0].markdown(
        _operator_metric_card_html("Products in view", len(filtered_df.index), f"{supplier_count} supplier group(s)", "neutral"),
        unsafe_allow_html=True,
    )
    metric_cols[1].markdown(
        _operator_metric_card_html("Order-ready products", ready_rows, "Still requires Luke's draft decision", "good" if ready_rows else "warn"),
        unsafe_allow_html=True,
    )
    metric_cols[2].markdown(
        _operator_metric_card_html("Blocked products", blocked_rows, "Proof or safety blocker visible", "warn" if blocked_rows else "good"),
        unsafe_allow_html=True,
    )
    metric_cols[3].markdown(
        _operator_metric_card_html("Draft qty products", draft_qty_rows, "Local drafts only", "neutral"),
        unsafe_allow_html=True,
    )


def _render_restock_workbench_table(filtered_df: pd.DataFrame, *, root_path: Path) -> None:
    import streamlit as st

    st.markdown("### Products to review")
    st.caption(
        "These cards are the normal working view. Technical proof tables are lower down if Codex needs them."
    )
    if filtered_df.empty:
        st.info("No rows match the current Restocking filters.")
        return
    for _, row in filtered_df.head(60).iterrows():
        st.markdown(_restock_card_html(row), unsafe_allow_html=True)
        _render_restock_card_local_controls(row, root_path=root_path)
        _render_restock_card_supplier_proof_controls(row, root_path=root_path)
    if len(filtered_df.index) > 60:
        st.caption(f"Showing the first 60 rows. Use supplier or search filters to narrow the remaining {len(filtered_df.index) - 60}.")


def _o_health_bad_count(health_df: pd.DataFrame) -> int:
    if health_df.empty or "status" not in health_df.columns:
        return 0
    return int(
        health_df["status"].map(lambda value: _normalize_text(value).lower() not in {"", "ok"}).sum()
    )


def _o_stage_state_counts(df: pd.DataFrame, state_col: str, ready_states: set[str]) -> tuple[int, int]:
    if df.empty or state_col not in df.columns:
        return 0, 0
    states = df[state_col].map(_normalize_text)
    blocked_count = int(states.map(lambda value: value == "blocked" or "blocked" in value).sum())
    ready_count = int(states.map(lambda value: value in ready_states).sum())
    return ready_count, blocked_count


def _o_progress_row(
    *,
    stage: str,
    rows_df: pd.DataFrame,
    health_df: pd.DataFrame,
    state_col: str,
    ready_states: set[str],
    meaning: str,
    next_step: str,
) -> dict[str, str]:
    row_count = len(rows_df.index)
    health_bad = _o_health_bad_count(health_df)
    ready_count, blocked_count = _o_stage_state_counts(rows_df, state_col, ready_states)
    if health_bad:
        state = "health blocker"
    elif row_count == 0:
        state = "waiting for rows"
    elif ready_count and blocked_count:
        state = "part ready"
    elif ready_count:
        state = "local rows ready"
    elif blocked_count:
        state = "blocked rows visible"
    else:
        state = "rows visible"
    return {
        "Stage": stage,
        "Rows": str(row_count),
        "Ready": str(ready_count),
        "Blocked": str(blocked_count),
        "State": state,
        "Meaning": meaning,
        "Next local step": next_step,
    }


def _build_o_restock_progress_df(datasets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    stages = [
        {
            "stage": "Session view",
            "rows": "restock_session_review_live",
            "health": "restock_session_health",
            "state_col": "row_status",
            "ready": {"ready", "manual_review_ready", "review_ready"},
            "meaning": "Products are visible for local restock review.",
            "next": "Refresh the local restock proof.",
        },
        {
            "stage": "Supplier batch drafts",
            "rows": "restock_session_supplier_batch_lines_live",
            "health": "restock_session_supplier_batch_health",
            "state_col": "supplier_batch_readiness_state",
            "ready": {"ready_for_purchase_approval_review_only"},
            "meaning": "Draft quantities are grouped by supplier.",
            "next": "Save a local draft quantity for a chosen row.",
        },
        {
            "stage": "Supplier source index",
            "rows": "restock_supplier_file_source_index_live",
            "health": "restock_supplier_file_source_index_health",
            "state_col": "source_handoff_state",
            "ready": {
                "local_file_available_no_f_status",
                "local_file_newer_than_f_status",
                "f_status_failed_local_file_available",
                "f_status_matches_local_file",
            },
            "meaning": "O compares F source status with the latest local supplier folders.",
            "next": "Refresh the local supplier-file source index.",
        },
        {
            "stage": "Supplier file probe",
            "rows": "restock_supplier_file_presence_probe_live",
            "health": "restock_supplier_file_presence_probe_health",
            "state_col": "identity_match_state",
            "ready": {"exact_supplier_sku_or_barcode_found"},
            "meaning": "Latest local supplier files are checked for the exact supplier SKU or barcode.",
            "next": "Check the latest local supplier file proof.",
        },
        {
            "stage": "Purchase approval preview",
            "rows": "restock_purchase_approval_preview_lines_live",
            "health": "restock_purchase_approval_preview_health",
            "state_col": "approval_preview_state",
            "ready": {"ready_for_purchase_approval_review_only"},
            "meaning": "Rows are shaped for local approval review.",
            "next": "Complete supplier proof and pack/MOQ proof.",
        },
        {
            "stage": "Approval guardrails",
            "rows": "restock_purchase_approval_guardrails_live",
            "health": "restock_purchase_approval_guardrails_health",
            "state_col": "approval_guardrail_state",
            "ready": {"local_review_accept_not_commitment"},
            "meaning": "Local approval decisions are checked against safety rules.",
            "next": "Save a local approval guardrail decision.",
        },
        {
            "stage": "PO draft readiness",
            "rows": "restock_po_draft_readiness_preview_lines_live",
            "health": "restock_po_draft_readiness_preview_health",
            "state_col": "po_draft_readiness_state",
            "ready": {"ready_for_local_po_draft_review_only"},
            "meaning": "Rows are checked before local PO draft design.",
            "next": "Build the local PO draft readiness preview.",
        },
        {
            "stage": "PO line design",
            "rows": "restock_po_line_design_preview_lines_live",
            "health": "restock_po_line_design_preview_health",
            "state_col": "line_design_state",
            "ready": {"ready_for_local_po_line_design_review_only"},
            "meaning": "Local line quantities, costs, and values are shaped.",
            "next": "Build the local PO line design preview.",
        },
        {
            "stage": "PO packet review",
            "rows": "restock_po_draft_packet_review_lines_live",
            "health": "restock_po_draft_packet_review_health",
            "state_col": "packet_review_line_state",
            "ready": {"ready_for_local_po_draft_packet_review_only"},
            "meaning": "Local lines are grouped into a supplier packet.",
            "next": "Build the local supplier packet review.",
        },
        {
            "stage": "PO hold review",
            "rows": "restock_po_draft_hold_review_lines_live",
            "health": "restock_po_draft_hold_review_health",
            "state_col": "hold_review_line_state",
            "ready": {"held_for_local_po_draft_review_only"},
            "meaning": "Rows are held locally before any real PO path exists.",
            "next": "Build the local hold review.",
        },
        {
            "stage": "PO file-shape preview",
            "rows": "restock_po_draft_file_shape_preview_lines_live",
            "health": "restock_po_draft_file_shape_preview_health",
            "state_col": "file_shape_line_state",
            "ready": {"ready_for_local_po_draft_file_shape_review_only"},
            "meaning": "The future file shape is previewed locally.",
            "next": "Build the local file-shape preview.",
        },
        {
            "stage": "PO review controls",
            "rows": "restock_po_draft_review_controls_live",
            "health": "restock_po_draft_review_controls_health",
            "state_col": "review_control_state",
            "ready": {"local_po_draft_shape_ready_not_po"},
            "meaning": "A local operator control marks the file shape decision.",
            "next": "Save a local file-shape review control.",
        },
        {
            "stage": "PO export preview",
            "rows": "restock_po_draft_export_preview_lines_live",
            "health": "restock_po_draft_export_preview_health",
            "state_col": "export_preview_line_state",
            "ready": {"ready_for_local_po_draft_export_preview_only"},
            "meaning": "The future export packet is previewed locally.",
            "next": "Build the local export preview.",
        },
        {
            "stage": "PO export gate",
            "rows": "restock_po_draft_export_gate_live",
            "health": "restock_po_draft_export_gate_health",
            "state_col": "export_gate_state",
            "ready": {"local_export_candidate_ready_not_po"},
            "meaning": "A local operator gate marks candidate-ready, still not a PO.",
            "next": "Save a local export-gate decision.",
        },
    ]
    return pd.DataFrame(
        [
            _o_progress_row(
                stage=stage["stage"],
                rows_df=datasets.get(stage["rows"], pd.DataFrame()).copy(),
                health_df=datasets.get(stage["health"], pd.DataFrame()).copy(),
                state_col=stage["state_col"],
                ready_states=set(stage["ready"]),
                meaning=stage["meaning"],
                next_step=stage["next"],
            )
            for stage in stages
        ]
    )


def _o_progress_next_step(progress_df: pd.DataFrame) -> str:
    if progress_df.empty:
        return "Refresh the local restock proof."
    for _, row in progress_df.iterrows():
        state = _normalize_text(row.get("State", ""))
        rows = _normalize_text(row.get("Rows", ""))
        if state == "health blocker":
            return _normalize_text(row.get("Next local step", "")) or "Fix the local health blocker."
        if rows == "0":
            return _normalize_text(row.get("Next local step", "")) or "Build the next local preview stage."
    return "Stay local until a protected real-PO decision is approved."


def _render_o_restock_progress_strip(datasets: dict[str, pd.DataFrame]) -> None:
    import streamlit as st

    progress_df = _build_o_restock_progress_df(datasets)
    next_step = _o_progress_next_step(progress_df)
    st.subheader("Restock progress")
    st.caption(f"Next local step: {next_step}")
    st.dataframe(progress_df, width="stretch", hide_index=True)


def _render_restock_session_tab(root_path: Path, datasets: dict[str, pd.DataFrame]) -> None:
    import streamlit as st

    st.subheader("Restocking")
    st.caption("Local supplier review only. It does not create purchase orders.")

    with st.expander("Local proof controls", expanded=False):
        refresh_col, refresh_note_col = st.columns([1, 3])
        if refresh_col.button("Refresh local proof", key="o_restock_session_refresh"):
            build_restock_session_view(root=root_path)
            build_restock_supplier_batch_drafts(root=root_path, refresh_session=False)
            build_supplier_file_presence_probe(root=root_path, refresh_batches=False)
            build_purchase_approval_preview(root=root_path, refresh_batches=False)
            build_purchase_approval_guardrails(root=root_path, refresh_preview=False)
            build_po_draft_readiness_preview(root=root_path, refresh_guardrails=False)
            build_po_line_design_preview(root=root_path, refresh_readiness=False)
            build_po_draft_packet_review(root=root_path, refresh_design=False)
            build_po_draft_hold_review(root=root_path, refresh_packet_review=False)
            build_po_draft_file_shape_preview(root=root_path, refresh_hold_review=False)
            build_po_preview_construction_summary(root=root_path, refresh_file_shape=False)
            build_po_draft_review_controls(root=root_path, refresh_construction_summary=False)
            build_po_draft_export_preview(root=root_path, refresh_review_controls=False)
            build_po_draft_export_gate(root=root_path, refresh_export_preview=False)
            st.session_state["o_recent_submit_notice"] = "Restocking proof refreshed locally."
            st.rerun()
        refresh_note_col.caption("This refreshes local proof only. It does not buy stock, write Sheets, change prices, or touch scanner queues.")

    health_df = datasets.get("restock_session_health", pd.DataFrame()).copy()
    review_df = datasets.get("restock_session_review_live", pd.DataFrame()).copy()
    summary_df = datasets.get("restock_session_supplier_summary_live", pd.DataFrame()).copy()
    reason_df = datasets.get("restock_session_reason_codes", pd.DataFrame()).copy()
    draft_events_df = datasets.get("restock_session_draft_decision_events", pd.DataFrame()).copy()
    supplier_proof_events_df = datasets.get("restock_session_supplier_proof_events", pd.DataFrame()).copy()
    pack_moq_proof_events_df = datasets.get("restock_session_pack_moq_proof_events", pd.DataFrame()).copy()
    batch_lines_df = datasets.get("restock_session_supplier_batch_lines_live", pd.DataFrame()).copy()
    batch_summary_df = datasets.get("restock_session_supplier_batch_summary_live", pd.DataFrame()).copy()
    batch_health_df = datasets.get("restock_session_supplier_batch_health", pd.DataFrame()).copy()
    supplier_file_source_index_df = datasets.get("restock_supplier_file_source_index_live", pd.DataFrame()).copy()
    supplier_file_source_index_health_df = datasets.get("restock_supplier_file_source_index_health", pd.DataFrame()).copy()
    supplier_file_probe_df = datasets.get("restock_supplier_file_presence_probe_live", pd.DataFrame()).copy()
    supplier_file_probe_health_df = datasets.get("restock_supplier_file_presence_probe_health", pd.DataFrame()).copy()
    approval_preview_lines_df = datasets.get("restock_purchase_approval_preview_lines_live", pd.DataFrame()).copy()
    approval_preview_summary_df = datasets.get("restock_purchase_approval_preview_summary_live", pd.DataFrame()).copy()
    approval_preview_health_df = datasets.get("restock_purchase_approval_preview_health", pd.DataFrame()).copy()
    approval_decision_events_df = datasets.get("restock_purchase_approval_decision_events", pd.DataFrame()).copy()
    approval_guardrails_df = datasets.get("restock_purchase_approval_guardrails_live", pd.DataFrame()).copy()
    approval_guardrails_health_df = datasets.get("restock_purchase_approval_guardrails_health", pd.DataFrame()).copy()
    po_readiness_lines_df = datasets.get("restock_po_draft_readiness_preview_lines_live", pd.DataFrame()).copy()
    po_readiness_summary_df = datasets.get("restock_po_draft_readiness_preview_summary_live", pd.DataFrame()).copy()
    po_readiness_health_df = datasets.get("restock_po_draft_readiness_preview_health", pd.DataFrame()).copy()
    po_line_design_lines_df = datasets.get("restock_po_line_design_preview_lines_live", pd.DataFrame()).copy()
    po_line_design_summary_df = datasets.get("restock_po_line_design_preview_summary_live", pd.DataFrame()).copy()
    po_line_design_health_df = datasets.get("restock_po_line_design_preview_health", pd.DataFrame()).copy()
    po_packet_review_lines_df = datasets.get("restock_po_draft_packet_review_lines_live", pd.DataFrame()).copy()
    po_packet_review_summary_df = datasets.get("restock_po_draft_packet_review_summary_live", pd.DataFrame()).copy()
    po_packet_review_health_df = datasets.get("restock_po_draft_packet_review_health", pd.DataFrame()).copy()
    po_hold_review_lines_df = datasets.get("restock_po_draft_hold_review_lines_live", pd.DataFrame()).copy()
    po_hold_review_summary_df = datasets.get("restock_po_draft_hold_review_summary_live", pd.DataFrame()).copy()
    po_hold_review_health_df = datasets.get("restock_po_draft_hold_review_health", pd.DataFrame()).copy()
    po_file_shape_lines_df = datasets.get("restock_po_draft_file_shape_preview_lines_live", pd.DataFrame()).copy()
    po_file_shape_summary_df = datasets.get("restock_po_draft_file_shape_preview_summary_live", pd.DataFrame()).copy()
    po_file_shape_health_df = datasets.get("restock_po_draft_file_shape_preview_health", pd.DataFrame()).copy()
    po_construction_summary_df = datasets.get("restock_po_preview_construction_summary_live", pd.DataFrame()).copy()
    po_construction_summary_health_df = datasets.get("restock_po_preview_construction_summary_health", pd.DataFrame()).copy()
    po_review_control_events_df = datasets.get("restock_po_draft_review_control_events", pd.DataFrame()).copy()
    po_review_controls_df = datasets.get("restock_po_draft_review_controls_live", pd.DataFrame()).copy()
    po_review_controls_health_df = datasets.get("restock_po_draft_review_controls_health", pd.DataFrame()).copy()
    po_export_preview_lines_df = datasets.get("restock_po_draft_export_preview_lines_live", pd.DataFrame()).copy()
    po_export_preview_summary_df = datasets.get("restock_po_draft_export_preview_summary_live", pd.DataFrame()).copy()
    po_export_preview_health_df = datasets.get("restock_po_draft_export_preview_health", pd.DataFrame()).copy()
    po_export_gate_events_df = datasets.get("restock_po_draft_export_gate_events", pd.DataFrame()).copy()
    po_export_gate_df = datasets.get("restock_po_draft_export_gate_live", pd.DataFrame()).copy()
    po_export_gate_health_df = datasets.get("restock_po_draft_export_gate_health", pd.DataFrame()).copy()

    bad_health = pd.DataFrame()
    if not health_df.empty and "status" in health_df.columns:
        bad_health = health_df[health_df["status"].map(lambda value: _normalize_text(value).lower() != "ok")].copy()
    if not health_df.empty and not bad_health.empty:
        st.warning("Restocking proof has warnings or blockers.")

    recent_notice = _normalize_text(st.session_state.get("o_recent_submit_notice", ""))
    if recent_notice:
        st.markdown(_render_inline_notice(recent_notice), unsafe_allow_html=True)

    if review_df.empty:
        st.info("No session rows yet. Refresh the local proof to build the current session view.")
        if not health_df.empty:
            st.dataframe(health_df, width="stretch", hide_index=True)
        return

    for col in (
        "supplier_name",
        "source_class",
        "row_status",
        "seller_sku",
        "asin",
        "title",
        "supplier_sku",
        "barcode",
        "suggested_action",
        "old_suggested_qty",
        "order_qty_draft",
        "latest_draft_decision_code",
    ):
        if col not in review_df.columns:
            review_df[col] = ""
    review_df = _apply_supplier_file_card_context(review_df, supplier_file_probe_df)
    review_df["_supplier_label"] = review_df["supplier_name"].map(_supplier_label)
    review_df["_workable_candidate"] = _restock_workable_mask(review_df)

    mode_options = ["Overview", "Supplier Review", "Admin Proof"]
    requested_mode = _normalize_text(st.session_state.get("o_restock_requested_site_mode", ""))
    if requested_mode in mode_options:
        st.session_state["o_restock_site_mode"] = requested_mode
        st.session_state["o_restock_requested_site_mode"] = ""
    if st.session_state.get("o_restock_site_mode") not in mode_options:
        st.session_state["o_restock_site_mode"] = "Overview"
    page_mode = st.radio(
        "Restocking view",
        options=mode_options,
        key="o_restock_site_mode",
        horizontal=True,
    )

    if page_mode == "Overview":
        _render_restock_site_overview(root_path, review_df, summary_df)
        return

    if page_mode == "Admin Proof":
        st.markdown("### Admin proof")
        st.caption("Maintenance proof and local preview outputs live here. This mode is for Codex/admin checks, not Luke's normal restocking path.")
        _render_o_restock_progress_strip(datasets)
    else:
        st.markdown("### Supplier review")
        st.caption("Pick one supplier and review only the products that need attention.")

    view_options = ["Worth checking", "All supplier products"]
    controls_a, controls_b, controls_c = st.columns([1.35, 1.35, 2.4])
    view_filter = controls_a.selectbox(
        "Products",
        options=view_options,
        index=0,
        key="o_session_view_filter_v3",
    )
    base_df = review_df[review_df["_workable_candidate"]].copy() if view_filter == "Worth checking" else review_df.copy()
    if base_df.empty:
        base_df = review_df.copy()
    supplier_counts = base_df["_supplier_label"].value_counts().sort_values(ascending=False)
    supplier_options = supplier_counts.index.tolist()
    if not supplier_options:
        supplier_options = ["(Unknown supplier)"]
    preferred_supplier = _normalize_text(st.session_state.get("o_restock_selected_supplier", ""))
    supplier_index = supplier_options.index(preferred_supplier) if preferred_supplier in supplier_options else 0
    supplier_filter = controls_b.selectbox(
        "Supplier",
        options=supplier_options,
        index=supplier_index,
        key="o_session_supplier_filter_v3",
        format_func=lambda value: f"{value} ({int(supplier_counts.get(value, 0))})",
    )
    st.session_state["o_restock_selected_supplier"] = supplier_filter
    search_text = controls_c.text_input("Search product", value="", key="o_session_search_v3")

    source_filter = "All sources"
    row_status_filter = "All rows"
    with st.expander("More filters", expanded=False):
        source_options = ["All sources", *sorted({_normalize_text(value) for value in base_df["source_class"].tolist() if _normalize_text(value)})]
        status_options = ["All rows", *sorted({_normalize_text(value) for value in base_df["row_status"].tolist() if _normalize_text(value)})]
        more_a, more_b = st.columns([1.1, 1.1])
        source_filter = more_a.selectbox("Source", options=source_options, index=0, key="o_session_source_filter_v2")
        row_status_filter = more_b.selectbox("State", options=status_options, index=0, key="o_session_status_filter_v2")

    filtered_df = base_df.copy()
    filtered_df = filtered_df[filtered_df["_supplier_label"] == supplier_filter].copy()
    if source_filter != "All sources":
        filtered_df = filtered_df[filtered_df["source_class"].map(_normalize_text) == source_filter].copy()
    if row_status_filter != "All rows":
        filtered_df = filtered_df[filtered_df["row_status"].map(_normalize_text) == row_status_filter].copy()
    query = _normalize_text(search_text).lower()
    if query:
        mask = pd.Series(False, index=filtered_df.index)
        for col in ("seller_sku", "asin", "title", "supplier_sku", "barcode"):
            mask = mask | filtered_df[col].astype(str).str.lower().str.contains(query, na=False)
        filtered_df = filtered_df[mask].copy()

    blocked_count = int(filtered_df.get("row_status", pd.Series(dtype=str)).map(_normalize_text).eq("blocked").sum())
    if page_mode != "Admin Proof":
        st.caption(
            f"Showing {len(filtered_df.index)} product{'' if len(filtered_df.index) == 1 else 's'} for {supplier_filter}. "
            f"Blocked from clean buy: {blocked_count}."
        )
    supplier_summary_match = summary_df.copy()
    if not supplier_summary_match.empty and "supplier_name" in supplier_summary_match.columns:
        supplier_summary_match["_supplier_label"] = supplier_summary_match["supplier_name"].map(_supplier_label)
        supplier_summary_match = supplier_summary_match[supplier_summary_match["_supplier_label"] == supplier_filter].copy()
    if page_mode != "Admin Proof" and not supplier_summary_match.empty:
        supplier_row = supplier_summary_match.iloc[0]
        top_reasons = _humanize_restock_list(supplier_row.get("top_block_reasons", ""), limit=3)
        st.markdown(
            _operator_decision_card_html(
                f"Supplier: {supplier_filter}",
                (
                    f"{_display_plain(supplier_row.get('total_rows', len(filtered_df.index)), str(len(filtered_df.index)))} total product(s). "
                    f"{_display_plain(supplier_row.get('ready_for_review_rows', '0'), '0')} ready. "
                    f"Main blocker: {top_reasons}."
                ),
                "neutral",
            ),
            unsafe_allow_html=True,
        )
    if page_mode != "Admin Proof":
        _render_restock_workbench_overview(filtered_df)
        _render_restock_workbench_table(filtered_df, root_path=root_path)

    for col in ("reason_code", "reason_label", "safe_to_draft", "creates_live_action"):
        if col not in reason_df.columns:
            reason_df[col] = ""
    allowed_reasons = reason_df[
        (reason_df["safe_to_draft"].map(lambda value: _normalize_text(value) == "1"))
        & (reason_df["creates_live_action"].map(lambda value: _normalize_text(value) == "0"))
        & (reason_df["reason_code"].map(_normalize_text) != "")
    ].copy()
    reason_label_by_code = {
        _normalize_text(row.get("reason_code", "")): _normalize_text(row.get("reason_label", "")) or _normalize_text(row.get("reason_code", ""))
        for _, row in allowed_reasons.iterrows()
    }
    decision_codes = [code for code in reason_label_by_code if code]

    with st.expander("Save a local decision", expanded=False):
        if filtered_df.empty:
            st.info("No filtered rows to draft against.")
        elif not decision_codes:
            st.warning("No local draft reason codes are available.")
        else:
            row_choices: list[tuple[str, str]] = []
            for _, row in filtered_df.iterrows():
                row_id = _normalize_text(row.get("row_id", ""))
                sku = _normalize_text(row.get("seller_sku", ""))
                asin = _normalize_text(row.get("asin", ""))
                title = _normalize_text(row.get("title", ""))
                supplier = _normalize_text(row.get("supplier_name", ""))
                label = " | ".join(part for part in (supplier, sku or asin, title[:80]) if part)
                if row_id:
                    row_choices.append((label or row_id, row_id))
            if not row_choices:
                st.warning("Filtered rows are missing session row IDs.")
                return
            row_label_to_id = {label: row_id for label, row_id in row_choices}
            selected_row_label = st.selectbox(
                "Row",
                options=list(row_label_to_id.keys()),
                key="o_session_draft_row",
            )
            decision_label_to_code = {
                reason_label_by_code[code]: code
                for code in decision_codes
            }
            selected_decision_label = st.selectbox(
                "Decision",
                options=list(decision_label_to_code.keys()),
                key="o_session_draft_decision",
            )
            selected_row_id = row_label_to_id.get(selected_row_label, "")
            selected_row_df = filtered_df[filtered_df["row_id"].map(_normalize_text) == selected_row_id].copy()
            selected_row = selected_row_df.iloc[0].to_dict() if not selected_row_df.empty else {}
            decision_code = decision_label_to_code.get(selected_decision_label, "")
            draft_qty: object = ""
            snooze_value: object = ""
            form_cols = st.columns([1.0, 1.0, 2.4])
            if decision_code == "order_qty_draft":
                default_qty = _positive_int_value(selected_row.get("old_suggested_qty", "")) or 1
                draft_qty = form_cols[0].number_input(
                    "Qty",
                    min_value=1,
                    step=1,
                    value=default_qty,
                    key="o_session_draft_qty",
                )
            elif decision_code == "snooze":
                snooze_value = form_cols[1].date_input(
                    "Snooze until",
                    value=_next_monday(),
                    key="o_session_draft_snooze_until",
                )
            decision_note = form_cols[2].text_input("Note", value="", key="o_session_draft_note")
            save_cols = st.columns([1.0, 3.0])
            if save_cols[0].button("Save Draft", type="primary", key="o_session_save_draft"):
                try:
                    saved = submit_restock_session_draft_decision(
                        root=root_path,
                        session_row=selected_row,
                        decision_code=decision_code,
                        draft_order_qty=draft_qty,
                        snooze_until_utc=snooze_value,
                        decision_note=decision_note,
                        actor="operator_ui",
                        event_source_reference="o_ui_restock_session",
                    )
                    build_restock_session_view(root=root_path)
                    build_restock_supplier_batch_drafts(root=root_path, refresh_session=False)
                    build_supplier_file_presence_probe(root=root_path, refresh_batches=False)
                    build_purchase_approval_preview(root=root_path, refresh_batches=False)
                    build_purchase_approval_guardrails(root=root_path, refresh_preview=False)
                    build_po_draft_readiness_preview(root=root_path, refresh_guardrails=False)
                    build_po_line_design_preview(root=root_path, refresh_readiness=False)
                    build_po_draft_packet_review(root=root_path, refresh_design=False)
                    build_po_draft_hold_review(root=root_path, refresh_packet_review=False)
                    build_po_draft_file_shape_preview(root=root_path, refresh_hold_review=False)
                    build_po_preview_construction_summary(root=root_path, refresh_file_shape=False)
                    build_po_draft_review_controls(root=root_path, refresh_construction_summary=False)
                    build_po_draft_export_preview(root=root_path, refresh_review_controls=False)
                    build_po_draft_export_gate(root=root_path, refresh_export_preview=False)
                    st.session_state["o_recent_submit_notice"] = (
                        f"Saved draft decision {saved.get('decision_code', '')} for {saved.get('seller_sku', '') or saved.get('asin', '')}."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(f"Draft not saved: {exc}")
            save_cols[1].caption("Drafts stay local. They do not create purchase orders, receiving events, or Amazon handoffs.")

        if not draft_events_df.empty:
            show_cols = [
                col
                for col in (
                    "event_utc",
                    "seller_sku",
                    "asin",
                    "supplier_name",
                    "decision_code",
                    "draft_order_qty",
                    "snooze_until_utc",
                    "decision_note",
                    "creates_live_action",
                )
                if col in draft_events_df.columns
            ]
            st.dataframe(draft_events_df.tail(25)[show_cols], width="stretch", hide_index=True)

    if page_mode == "Supplier Review":
        return

    with st.expander("Supplier batch drafts", expanded=False):
        st.caption("Local draft batches only. These are not purchase orders and cannot commit a buy.")
        if batch_lines_df.empty:
            st.info("No supplier batch draft lines yet. Save an order quantity draft first.")
        else:
            if not batch_summary_df.empty:
                st.dataframe(batch_summary_df, width="stretch", hide_index=True)
            line_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "source_class",
                    "draft_order_qty",
                    "current_supplier_cost_gbp",
                    "draft_line_value_gbp",
                    "supplier_proof_checklist_status",
                    "supplier_proof_missing_reasons",
                    "supplier_match_state",
                    "supplier_stock_state",
                    "supplier_stock_qty",
                    "backorder_state",
                    "backorder_eta_utc",
                    "supplier_file_asof_utc",
                    "supplier_file_reference",
                    "latest_supplier_proof_id",
                    "pack_moq_proof_state",
                    "pack_multiple",
                    "supplier_moq",
                    "valid_order_step",
                    "latest_pack_moq_proof_id",
                    "supplier_batch_readiness_state",
                    "supplier_batch_readiness_reasons",
                    "line_state",
                    "action_block_reason",
                    "creates_live_action",
                )
                if col in batch_lines_df.columns
            ]
            st.dataframe(batch_lines_df[line_cols], width="stretch", hide_index=True)

            st.markdown("#### Supplier proof")
            proof_choices: list[tuple[str, int]] = []
            for idx, row in batch_lines_df.reset_index(drop=True).iterrows():
                label = " | ".join(
                    part
                    for part in (
                        _normalize_text(row.get("supplier_name", "")),
                        _normalize_text(row.get("seller_sku", "")) or _normalize_text(row.get("asin", "")),
                        _normalize_text(row.get("title", ""))[:80],
                    )
                    if part
                )
                proof_choices.append((label or _normalize_text(row.get("row_id", "")) or f"row {idx + 1}", int(idx)))
            proof_label_to_index = {label: idx for label, idx in proof_choices}
            selected_proof_label = st.selectbox(
                "Batch line",
                options=list(proof_label_to_index.keys()),
                key="o_session_supplier_proof_row",
            )
            selected_proof_row = batch_lines_df.reset_index(drop=True).iloc[proof_label_to_index[selected_proof_label]].to_dict()
            stock_label_to_state = {
                "Not verified": "supplier_stock_not_verified",
                "In stock": "supplier_stock_verified_in_stock",
                "Out of stock": "supplier_stock_verified_zero",
            }
            backorder_label_to_state = {
                "Not verified": "backorder_not_verified",
                "No backorder": "backorder_none_confirmed",
                "Backorder wait": "backorder_wait",
            }
            proof_cols = st.columns([1.1, 0.7, 1.1, 0.9, 1.3, 1.8])
            stock_label = proof_cols[0].selectbox(
                "Stock",
                options=list(stock_label_to_state.keys()),
                key="o_session_supplier_proof_stock_state",
            )
            stock_qty = proof_cols[1].text_input("Stock qty", value="", key="o_session_supplier_proof_stock_qty")
            backorder_label = proof_cols[2].selectbox(
                "Backorder",
                options=list(backorder_label_to_state.keys()),
                key="o_session_supplier_proof_backorder_state",
            )
            backorder_eta = proof_cols[3].text_input("ETA", value="", key="o_session_supplier_proof_backorder_eta")
            file_asof = proof_cols[4].text_input("File date", value="", key="o_session_supplier_proof_file_asof")
            file_reference = proof_cols[5].text_input("File ref", value="", key="o_session_supplier_proof_file_ref")
            proof_note = st.text_input("Proof note", value="", key="o_session_supplier_proof_note")
            proof_save_cols = st.columns([1.2, 3.2])
            if proof_save_cols[0].button("Save Supplier Proof", type="primary", key="o_session_save_supplier_proof"):
                try:
                    saved = submit_restock_session_supplier_proof_event(
                        root=root_path,
                        session_row=selected_proof_row,
                        supplier_stock_state=stock_label_to_state.get(stock_label, "supplier_stock_not_verified"),
                        supplier_stock_qty=stock_qty,
                        backorder_state=backorder_label_to_state.get(backorder_label, "backorder_not_verified"),
                        backorder_eta_utc=backorder_eta,
                        supplier_file_asof_utc=file_asof,
                        supplier_file_reference=file_reference,
                        proof_note=proof_note,
                        actor="operator_ui",
                        event_source_reference="o_ui_restock_supplier_proof",
                    )
                    build_restock_supplier_batch_drafts(root=root_path, refresh_session=False)
                    build_supplier_file_presence_probe(root=root_path, refresh_batches=False)
                    build_purchase_approval_preview(root=root_path, refresh_batches=False)
                    build_purchase_approval_guardrails(root=root_path, refresh_preview=False)
                    build_po_draft_readiness_preview(root=root_path, refresh_guardrails=False)
                    build_po_line_design_preview(root=root_path, refresh_readiness=False)
                    build_po_draft_packet_review(root=root_path, refresh_design=False)
                    build_po_draft_hold_review(root=root_path, refresh_packet_review=False)
                    build_po_draft_file_shape_preview(root=root_path, refresh_hold_review=False)
                    build_po_preview_construction_summary(root=root_path, refresh_file_shape=False)
                    build_po_draft_review_controls(root=root_path, refresh_construction_summary=False)
                    build_po_draft_export_preview(root=root_path, refresh_review_controls=False)
                    build_po_draft_export_gate(root=root_path, refresh_export_preview=False)
                    st.session_state["o_recent_submit_notice"] = (
                        f"Saved supplier proof for {saved.get('seller_sku', '') or saved.get('asin', '')}."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(f"Supplier proof not saved: {exc}")
            proof_save_cols[1].caption("Supplier proof stays local. It does not create purchase orders or change Product DB facts.")

            if not supplier_proof_events_df.empty:
                proof_event_cols = [
                    col
                    for col in (
                        "event_utc",
                        "seller_sku",
                        "asin",
                        "supplier_name",
                        "supplier_stock_state",
                        "supplier_stock_qty",
                        "backorder_state",
                        "backorder_eta_utc",
                        "supplier_file_asof_utc",
                        "supplier_file_reference",
                        "proof_note",
                        "creates_live_action",
                    )
                    if col in supplier_proof_events_df.columns
                ]
                st.dataframe(supplier_proof_events_df.tail(25)[proof_event_cols], width="stretch", hide_index=True)

            st.markdown("#### Pack / MOQ proof")
            pack_label = st.selectbox(
                "Pack line",
                options=list(proof_label_to_index.keys()),
                key="o_session_pack_moq_proof_row",
            )
            selected_pack_row = batch_lines_df.reset_index(drop=True).iloc[proof_label_to_index[pack_label]].to_dict()
            pack_state_label_to_value = {
                "Not verified": "pack_moq_not_verified",
                "Verified": "pack_moq_verified",
            }
            pack_cols = st.columns([1.0, 0.8, 0.8, 0.8, 1.7])
            pack_state_label = pack_cols[0].selectbox(
                "Pack state",
                options=list(pack_state_label_to_value.keys()),
                key="o_session_pack_moq_state",
            )
            pack_multiple = pack_cols[1].text_input("Pack", value="", key="o_session_pack_moq_pack")
            supplier_moq = pack_cols[2].text_input("MOQ", value="", key="o_session_pack_moq_moq")
            valid_order_step = pack_cols[3].text_input("Step", value="", key="o_session_pack_moq_step")
            pack_file_ref = pack_cols[4].text_input("Pack file ref", value="", key="o_session_pack_moq_file_ref")
            pack_note = st.text_input("Pack note", value="", key="o_session_pack_moq_note")
            pack_save_cols = st.columns([1.2, 3.2])
            if pack_save_cols[0].button("Save Pack Proof", type="primary", key="o_session_save_pack_moq_proof"):
                try:
                    saved = submit_restock_session_pack_moq_proof_event(
                        root=root_path,
                        session_row=selected_pack_row,
                        pack_moq_proof_state=pack_state_label_to_value.get(pack_state_label, "pack_moq_not_verified"),
                        pack_multiple=pack_multiple,
                        supplier_moq=supplier_moq,
                        valid_order_step=valid_order_step,
                        proof_file_reference=pack_file_ref,
                        proof_note=pack_note,
                        actor="operator_ui",
                        event_source_reference="o_ui_restock_pack_moq_proof",
                    )
                    build_restock_supplier_batch_drafts(root=root_path, refresh_session=False)
                    build_supplier_file_presence_probe(root=root_path, refresh_batches=False)
                    build_purchase_approval_preview(root=root_path, refresh_batches=False)
                    build_purchase_approval_guardrails(root=root_path, refresh_preview=False)
                    build_po_draft_readiness_preview(root=root_path, refresh_guardrails=False)
                    build_po_line_design_preview(root=root_path, refresh_readiness=False)
                    build_po_draft_packet_review(root=root_path, refresh_design=False)
                    build_po_draft_hold_review(root=root_path, refresh_packet_review=False)
                    build_po_draft_file_shape_preview(root=root_path, refresh_hold_review=False)
                    build_po_preview_construction_summary(root=root_path, refresh_file_shape=False)
                    build_po_draft_review_controls(root=root_path, refresh_construction_summary=False)
                    build_po_draft_export_preview(root=root_path, refresh_review_controls=False)
                    build_po_draft_export_gate(root=root_path, refresh_export_preview=False)
                    st.session_state["o_recent_submit_notice"] = (
                        f"Saved pack/MOQ proof for {saved.get('seller_sku', '') or saved.get('asin', '')}."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(f"Pack/MOQ proof not saved: {exc}")
            pack_save_cols[1].caption("Pack/MOQ proof stays local. It does not create purchase orders or change Product DB facts.")

            if not pack_moq_proof_events_df.empty:
                pack_event_cols = [
                    col
                    for col in (
                        "event_utc",
                        "seller_sku",
                        "asin",
                        "supplier_name",
                        "pack_moq_proof_state",
                        "pack_multiple",
                        "supplier_moq",
                        "valid_order_step",
                        "proof_file_reference",
                        "proof_note",
                        "creates_live_action",
                    )
                    if col in pack_moq_proof_events_df.columns
                ]
                st.dataframe(pack_moq_proof_events_df.tail(25)[pack_event_cols], width="stretch", hide_index=True)
        if not batch_health_df.empty:
            health_bad = batch_health_df[
                batch_health_df.get("status", pd.Series(dtype=str)).map(lambda value: _normalize_text(value).lower() != "ok")
            ].copy()
            if health_bad.empty:
                st.caption("Supplier batch draft proof is local and safe.")
            else:
                st.warning("Supplier batch draft proof has a blocker.")
                st.dataframe(health_bad, width="stretch", hide_index=True)

    with st.expander("Supplier file source index", expanded=False):
        st.caption("Read-only source handoff proof. This compares F source status with local supplier folders and does not import files or rewrite F.")
        if supplier_file_source_index_df.empty:
            st.info("No supplier file source index rows yet. Refresh local proof first.")
        else:
            source_index_cols = [
                col
                for col in (
                    "supplier_name",
                    "supplier_id",
                    "f_source_status",
                    "f_source_state",
                    "f_latest_source_name",
                    "f_latest_source_mtime_utc",
                    "f_latest_source_path_exists",
                    "local_latest_file_name",
                    "local_latest_file_mtime_utc",
                    "local_file_count",
                    "source_handoff_state",
                    "handoff_explanation",
                    "can_be_used_for_presence_probe",
                    "clears_supplier_proof",
                    "imports_supplier_file",
                    "updates_f_status",
                    "creates_live_action",
                )
                if col in supplier_file_source_index_df.columns
            ]
            st.dataframe(supplier_file_source_index_df[source_index_cols], width="stretch", hide_index=True)
        if not supplier_file_source_index_health_df.empty:
            source_index_health_bad = supplier_file_source_index_health_df[
                supplier_file_source_index_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if source_index_health_bad.empty:
                st.caption("Supplier file source index is local and safe.")
            else:
                st.warning("Supplier file source index has a blocker.")
                st.dataframe(source_index_health_bad, width="stretch", hide_index=True)

    with st.expander("Supplier file probe", expanded=False):
        st.caption("Read-only local supplier-file check. This does not clear supplier proof, approve buying, create purchase orders, or commit stock.")
        if supplier_file_probe_df.empty:
            st.info("No supplier file probe rows yet. Save an order quantity draft and refresh local proof first.")
        else:
            probe_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "supplier_sku",
                    "barcode",
                    "latest_supplier_file_name",
                    "latest_supplier_file_mtime_utc",
                    "latest_supplier_file_state",
                    "identity_match_state",
                    "matched_by",
                    "matched_row_count",
                    "searched_row_count",
                    "searched_identity_columns",
                    "probe_explanation",
                    "source_index_handoff_state",
                    "source_index_handoff_explanation",
                    "clears_supplier_proof",
                    "purchase_approval_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "creates_live_action",
                )
                if col in supplier_file_probe_df.columns
            ]
            st.dataframe(supplier_file_probe_df[probe_cols], width="stretch", hide_index=True)
        if not supplier_file_probe_health_df.empty:
            probe_health_bad = supplier_file_probe_health_df[
                supplier_file_probe_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if probe_health_bad.empty:
                st.caption("Supplier file probe is local and safe.")
            else:
                st.warning("Supplier file probe has a blocker.")
                st.dataframe(probe_health_bad, width="stretch", hide_index=True)

    with st.expander("Purchase approval preview", expanded=False):
        st.caption("Local preview only. This does not approve buying and does not create purchase orders.")
        if approval_preview_lines_df.empty:
            st.info("No approval preview lines yet. Save an order quantity draft and clear local proof first.")
        else:
            if not approval_preview_summary_df.empty:
                st.dataframe(approval_preview_summary_df, width="stretch", hide_index=True)
            preview_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "draft_order_qty",
                    "current_supplier_cost_gbp",
                    "draft_line_value_gbp",
                    "approval_preview_state",
                    "approval_block_reasons",
                    "supplier_batch_readiness_state",
                    "supplier_proof_checklist_status",
                    "source_class",
                    "creates_live_action",
                )
                if col in approval_preview_lines_df.columns
            ]
            st.dataframe(approval_preview_lines_df[preview_cols], width="stretch", hide_index=True)
        if not approval_preview_health_df.empty:
            preview_health_bad = approval_preview_health_df[
                approval_preview_health_df.get("status", pd.Series(dtype=str)).map(lambda value: _normalize_text(value).lower() != "ok")
            ].copy()
            if preview_health_bad.empty:
                st.caption("Purchase approval preview is local and safe.")
            else:
                st.warning("Purchase approval preview has a blocker.")
                st.dataframe(preview_health_bad, width="stretch", hide_index=True)

    with st.expander("Approval decision guardrails", expanded=False):
        st.caption("Local guardrail only. A local accept does not create a purchase order or commit a buy.")
        if approval_preview_summary_df.empty:
            st.info("No approval preview packets yet.")
        else:
            packet_choices: list[tuple[str, int]] = []
            for idx, row in approval_preview_summary_df.reset_index(drop=True).iterrows():
                label = " | ".join(
                    part
                    for part in (
                        _normalize_text(row.get("supplier_name", "")),
                        _normalize_text(row.get("approval_packet_id", "")),
                        f"ready { _normalize_text(row.get('ready_line_count', '0')) }",
                        f"blocked { _normalize_text(row.get('blocked_line_count', '0')) }",
                    )
                    if part
                )
                packet_choices.append((label or f"packet {idx + 1}", int(idx)))
            packet_label_to_index = {label: idx for label, idx in packet_choices}
            selected_packet_label = st.selectbox(
                "Packet",
                options=list(packet_label_to_index.keys()),
                key="o_session_approval_guard_packet",
            )
            selected_packet = approval_preview_summary_df.reset_index(drop=True).iloc[
                packet_label_to_index[selected_packet_label]
            ].to_dict()
            decision_label_to_state = {
                "Needs more proof": "local_review_more_proof_needed",
                "Reject local review": "local_review_reject",
                "Accept local review": "local_review_accept_not_commitment",
            }
            decision_label = st.selectbox(
                "Local decision",
                options=list(decision_label_to_state.keys()),
                key="o_session_approval_guard_decision",
            )
            guard_note = st.text_input("Guardrail note", value="", key="o_session_approval_guard_note")
            guard_save_cols = st.columns([1.2, 3.2])
            if guard_save_cols[0].button("Save Local Review", type="primary", key="o_session_save_approval_guard"):
                try:
                    saved = submit_purchase_approval_decision_event(
                        root=root_path,
                        preview_summary_row=selected_packet,
                        decision_state=decision_label_to_state.get(decision_label, "local_review_more_proof_needed"),
                        decision_note=guard_note,
                        actor="operator_ui",
                        event_source_reference="o_ui_purchase_approval_guardrails",
                    )
                    build_purchase_approval_guardrails(root=root_path, refresh_preview=False)
                    build_po_draft_readiness_preview(root=root_path, refresh_guardrails=False)
                    build_po_line_design_preview(root=root_path, refresh_readiness=False)
                    build_po_draft_packet_review(root=root_path, refresh_design=False)
                    build_po_draft_hold_review(root=root_path, refresh_packet_review=False)
                    build_po_draft_file_shape_preview(root=root_path, refresh_hold_review=False)
                    build_po_preview_construction_summary(root=root_path, refresh_file_shape=False)
                    build_po_draft_review_controls(root=root_path, refresh_construction_summary=False)
                    build_po_draft_export_preview(root=root_path, refresh_review_controls=False)
                    build_po_draft_export_gate(root=root_path, refresh_export_preview=False)
                    st.session_state["o_recent_submit_notice"] = (
                        f"Saved local review decision for {saved.get('supplier_name', '') or saved.get('approval_packet_id', '')}."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(f"Local review not saved: {exc}")
            guard_save_cols[1].caption("Guardrail decisions stay local and cannot create purchase orders.")

        if not approval_guardrails_df.empty:
            guardrail_cols = [
                col
                for col in (
                    "supplier_name",
                    "approval_packet_id",
                    "line_count",
                    "ready_line_count",
                    "blocked_line_count",
                    "draft_order_value_gbp",
                    "preview_packet_state",
                    "latest_decision_state",
                    "approval_guardrail_state",
                    "approval_guardrail_reasons",
                    "creates_live_action",
                )
                if col in approval_guardrails_df.columns
            ]
            st.dataframe(approval_guardrails_df[guardrail_cols], width="stretch", hide_index=True)
        if not approval_decision_events_df.empty:
            event_cols = [
                col
                for col in (
                    "event_utc",
                    "approval_packet_id",
                    "supplier_name",
                    "decision_state",
                    "expected_line_count",
                    "expected_ready_line_count",
                    "expected_blocked_line_count",
                    "decision_note",
                    "creates_live_action",
                )
                if col in approval_decision_events_df.columns
            ]
            st.dataframe(approval_decision_events_df.tail(25)[event_cols], width="stretch", hide_index=True)
        if not approval_guardrails_health_df.empty:
            guardrail_health_bad = approval_guardrails_health_df[
                approval_guardrails_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if guardrail_health_bad.empty:
                st.caption("Approval decision guardrails are local and safe.")
            else:
                st.warning("Approval decision guardrails have a blocker.")
                st.dataframe(guardrail_health_bad, width="stretch", hide_index=True)

    with st.expander("PO preview construction summary", expanded=False):
        st.caption("Local construction summary only. This shows the preview chain and does not create purchase orders or write PO files.")
        if po_construction_summary_df.empty:
            st.info("No PO preview construction summary yet. Refresh the local proof to build the chain view.")
        else:
            construction_cols = [
                col
                for col in (
                    "stage_label",
                    "line_rows",
                    "ready_or_held_rows",
                    "blocked_rows",
                    "health_bad_rows",
                    "stage_state",
                    "stage_block_reasons",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_construction_summary_df.columns
            ]
            st.dataframe(po_construction_summary_df[construction_cols], width="stretch", hide_index=True)
        if not po_construction_summary_health_df.empty:
            construction_health_bad = po_construction_summary_health_df[
                po_construction_summary_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if construction_health_bad.empty:
                st.caption("PO preview construction summary is local and safe.")
            else:
                st.warning("PO preview construction summary has a blocker.")
                st.dataframe(construction_health_bad, width="stretch", hide_index=True)

    with st.expander("PO draft readiness preview", expanded=False):
        st.caption("Local readiness preview only. This does not create purchase orders or write to PO files.")
        if po_readiness_lines_df.empty:
            st.info("No PO draft readiness lines yet. A preview packet needs a local accepted review first.")
        else:
            if not po_readiness_summary_df.empty:
                st.dataframe(po_readiness_summary_df, width="stretch", hide_index=True)
            po_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "draft_order_qty",
                    "current_supplier_cost_gbp",
                    "draft_line_value_gbp",
                    "approval_guardrail_state",
                    "po_draft_readiness_state",
                    "po_draft_block_reasons",
                    "po_creation_allowed",
                    "creates_live_action",
                )
                if col in po_readiness_lines_df.columns
            ]
            st.dataframe(po_readiness_lines_df[po_cols], width="stretch", hide_index=True)
        if not po_readiness_health_df.empty:
            po_health_bad = po_readiness_health_df[
                po_readiness_health_df.get("status", pd.Series(dtype=str)).map(lambda value: _normalize_text(value).lower() != "ok")
            ].copy()
            if po_health_bad.empty:
                st.caption("PO draft readiness preview is local and safe.")
            else:
                st.warning("PO draft readiness preview has a blocker.")
                st.dataframe(po_health_bad, width="stretch", hide_index=True)

    with st.expander("PO line design preview", expanded=False):
        st.caption("Local design preview only. This does not create purchase orders, write PO files, receive stock, or send to Amazon.")
        if po_line_design_lines_df.empty:
            st.info("No PO line design rows yet. PO readiness rows need a local accepted review first.")
        else:
            if not po_line_design_summary_df.empty:
                st.dataframe(po_line_design_summary_df, width="stretch", hide_index=True)
            line_design_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "designed_order_qty",
                    "designed_unit_cost_gbp",
                    "designed_line_value_gbp",
                    "source_po_draft_readiness_state",
                    "line_design_state",
                    "line_design_block_reasons",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_line_design_lines_df.columns
            ]
            st.dataframe(po_line_design_lines_df[line_design_cols], width="stretch", hide_index=True)
        if not po_line_design_health_df.empty:
            line_design_health_bad = po_line_design_health_df[
                po_line_design_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if line_design_health_bad.empty:
                st.caption("PO line design preview is local and safe.")
            else:
                st.warning("PO line design preview has a blocker.")
                st.dataframe(line_design_health_bad, width="stretch", hide_index=True)

    with st.expander("PO draft packet review", expanded=False):
        st.caption("Local packet review only. This does not create purchase orders, write PO files, receive stock, or send to Amazon.")
        if po_packet_review_lines_df.empty:
            st.info("No PO draft packet review rows yet. PO line design rows need to be locally ready first.")
        else:
            if not po_packet_review_summary_df.empty:
                st.dataframe(po_packet_review_summary_df, width="stretch", hide_index=True)
            packet_review_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "review_order_qty",
                    "review_unit_cost_gbp",
                    "review_line_value_gbp",
                    "source_line_design_state",
                    "packet_review_line_state",
                    "packet_review_block_reasons",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_packet_review_lines_df.columns
            ]
            st.dataframe(po_packet_review_lines_df[packet_review_cols], width="stretch", hide_index=True)
        if not po_packet_review_health_df.empty:
            packet_review_health_bad = po_packet_review_health_df[
                po_packet_review_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if packet_review_health_bad.empty:
                st.caption("PO draft packet review is local and safe.")
            else:
                st.warning("PO draft packet review has a blocker.")
                st.dataframe(packet_review_health_bad, width="stretch", hide_index=True)

    with st.expander("PO draft hold review", expanded=False):
        st.caption("Local hold review only. This does not create purchase orders, write PO files, write PO hold files, receive stock, or send to Amazon.")
        if po_hold_review_lines_df.empty:
            st.info("No PO draft hold review rows yet. PO draft packet review rows need to be locally ready first.")
        else:
            if not po_hold_review_summary_df.empty:
                st.dataframe(po_hold_review_summary_df, width="stretch", hide_index=True)
            hold_review_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "hold_order_qty",
                    "hold_unit_cost_gbp",
                    "hold_line_value_gbp",
                    "source_packet_review_line_state",
                    "hold_review_line_state",
                    "hold_review_reasons",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_hold_review_lines_df.columns
            ]
            st.dataframe(po_hold_review_lines_df[hold_review_cols], width="stretch", hide_index=True)
        if not po_hold_review_health_df.empty:
            hold_review_health_bad = po_hold_review_health_df[
                po_hold_review_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if hold_review_health_bad.empty:
                st.caption("PO draft hold review is local and safe.")
            else:
                st.warning("PO draft hold review has a blocker.")
                st.dataframe(hold_review_health_bad, width="stretch", hide_index=True)

    with st.expander("PO draft file-shape preview", expanded=False):
        st.caption("Local file-shape preview only. This does not create purchase orders, write PO files, write PO hold files, receive stock, or send to Amazon.")
        if po_file_shape_lines_df.empty:
            st.info("No PO draft file-shape preview rows yet. PO draft hold review rows need to be locally held first.")
        else:
            if not po_file_shape_summary_df.empty:
                st.dataframe(po_file_shape_summary_df, width="stretch", hide_index=True)
            file_shape_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "file_shape_qty",
                    "file_shape_unit_cost_gbp",
                    "file_shape_line_value_gbp",
                    "source_hold_review_line_state",
                    "file_shape_line_state",
                    "file_shape_block_reasons",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_file_shape_lines_df.columns
            ]
            st.dataframe(po_file_shape_lines_df[file_shape_cols], width="stretch", hide_index=True)
        if not po_file_shape_health_df.empty:
            file_shape_health_bad = po_file_shape_health_df[
                po_file_shape_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if file_shape_health_bad.empty:
                st.caption("PO draft file-shape preview is local and safe.")
            else:
                st.warning("PO draft file-shape preview has a blocker.")
                st.dataframe(file_shape_health_bad, width="stretch", hide_index=True)

    with st.expander("PO draft review controls", expanded=False):
        st.caption("Local review controls only. These decisions do not create purchase orders or write PO files.")
        if po_file_shape_summary_df.empty:
            st.info("No PO draft file-shape packets yet.")
        else:
            packet_choices: list[tuple[str, int]] = []
            for idx, row in po_file_shape_summary_df.reset_index(drop=True).iterrows():
                label = " | ".join(
                    part
                    for part in (
                        _normalize_text(row.get("supplier_name", "")),
                        _normalize_text(row.get("po_draft_file_shape_preview_id", "")),
                        f"ready { _normalize_text(row.get('ready_line_count', '0')) }",
                        f"blocked { _normalize_text(row.get('blocked_line_count', '0')) }",
                    )
                    if part
                )
                packet_choices.append((label or f"file-shape packet {idx + 1}", int(idx)))
            packet_label_to_index = {label: idx for label, idx in packet_choices}
            selected_packet_label = st.selectbox(
                "File-shape packet",
                options=list(packet_label_to_index.keys()),
                key="o_session_po_draft_review_control_packet",
            )
            selected_packet = po_file_shape_summary_df.reset_index(drop=True).iloc[
                packet_label_to_index[selected_packet_label]
            ].to_dict()
            decision_label_to_state = {
                "Needs more proof": "local_po_draft_more_proof_needed",
                "Keep on local hold": "local_po_draft_keep_on_hold",
                "Shape ready only": "local_po_draft_shape_ready_not_po",
            }
            decision_label = st.selectbox(
                "Local control",
                options=list(decision_label_to_state.keys()),
                key="o_session_po_draft_review_control_decision",
            )
            control_note = st.text_input("Control note", value="", key="o_session_po_draft_review_control_note")
            control_save_cols = st.columns([1.2, 3.2])
            if control_save_cols[0].button("Save Review Control", type="primary", key="o_session_save_po_draft_review_control"):
                try:
                    saved = submit_po_draft_review_control_event(
                        root=root_path,
                        file_shape_summary_row=selected_packet,
                        decision_state=decision_label_to_state.get(decision_label, "local_po_draft_more_proof_needed"),
                        decision_note=control_note,
                        actor="operator_ui",
                        event_source_reference="o_ui_po_draft_review_controls",
                    )
                    build_po_draft_review_controls(root=root_path, refresh_construction_summary=False)
                    build_po_draft_export_preview(root=root_path, refresh_review_controls=False)
                    build_po_draft_export_gate(root=root_path, refresh_export_preview=False)
                    st.session_state["o_recent_submit_notice"] = (
                        f"Saved local PO draft review control for {saved.get('supplier_name', '') or saved.get('po_draft_file_shape_preview_id', '')}."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(f"Review control not saved: {exc}")
            control_save_cols[1].caption("Review controls stay local. They cannot create purchase orders, receiving events, or Amazon handoffs.")

        if not po_review_controls_df.empty:
            control_cols = [
                col
                for col in (
                    "supplier_name",
                    "po_draft_file_shape_preview_id",
                    "line_count",
                    "ready_line_count",
                    "blocked_line_count",
                    "file_shape_value_gbp",
                    "source_file_shape_state",
                    "latest_decision_state",
                    "review_control_state",
                    "review_control_reasons",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_review_controls_df.columns
            ]
            st.dataframe(po_review_controls_df[control_cols], width="stretch", hide_index=True)
        if not po_review_control_events_df.empty:
            event_cols = [
                col
                for col in (
                    "event_utc",
                    "po_draft_file_shape_preview_id",
                    "supplier_name",
                    "decision_state",
                    "expected_line_count",
                    "expected_ready_line_count",
                    "expected_blocked_line_count",
                    "decision_note",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_review_control_events_df.columns
            ]
            st.dataframe(po_review_control_events_df.tail(25)[event_cols], width="stretch", hide_index=True)
        if not po_review_controls_health_df.empty:
            controls_health_bad = po_review_controls_health_df[
                po_review_controls_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if controls_health_bad.empty:
                st.caption("PO draft review controls are local and safe.")
            else:
                st.warning("PO draft review controls have a blocker.")
                st.dataframe(controls_health_bad, width="stretch", hide_index=True)

    with st.expander("PO draft export preview", expanded=False):
        st.caption("Local export preview only. This does not create purchase orders, write PO files, commit buying, receive stock, or send to Amazon.")
        if po_export_preview_lines_df.empty:
            st.info("No PO draft export preview rows yet. A file-shape packet needs a local shape-ready review control first.")
        else:
            if not po_export_preview_summary_df.empty:
                st.dataframe(po_export_preview_summary_df, width="stretch", hide_index=True)
            export_preview_cols = [
                col
                for col in (
                    "supplier_name",
                    "seller_sku",
                    "asin",
                    "title",
                    "export_preview_qty",
                    "export_preview_unit_cost_gbp",
                    "export_preview_line_value_gbp",
                    "source_file_shape_line_state",
                    "source_review_control_state",
                    "export_preview_line_state",
                    "export_preview_block_reasons",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_export_preview_lines_df.columns
            ]
            st.dataframe(po_export_preview_lines_df[export_preview_cols], width="stretch", hide_index=True)
        if not po_export_preview_health_df.empty:
            export_preview_health_bad = po_export_preview_health_df[
                po_export_preview_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if export_preview_health_bad.empty:
                st.caption("PO draft export preview is local and safe.")
            else:
                st.warning("PO draft export preview has a blocker.")
                st.dataframe(export_preview_health_bad, width="stretch", hide_index=True)

    with st.expander("PO draft export gate", expanded=False):
        st.caption("Local final gate only. This can mark a preview as candidate-ready, but it still does not create or write a purchase order.")
        if po_export_preview_summary_df.empty:
            st.info("No PO draft export preview packets yet.")
        else:
            export_packet_choices: list[tuple[str, int]] = []
            for idx, row in po_export_preview_summary_df.reset_index(drop=True).iterrows():
                label = " | ".join(
                    part
                    for part in (
                        _normalize_text(row.get("supplier_name", "")),
                        _normalize_text(row.get("po_draft_export_preview_id", "")),
                        f"ready { _normalize_text(row.get('ready_line_count', '0')) }",
                        f"blocked { _normalize_text(row.get('blocked_line_count', '0')) }",
                    )
                    if part
                )
                export_packet_choices.append((label or f"export packet {idx + 1}", int(idx)))
            export_packet_label_to_index = {label: idx for label, idx in export_packet_choices}
            selected_export_packet_label = st.selectbox(
                "Export preview packet",
                options=list(export_packet_label_to_index.keys()),
                key="o_session_po_draft_export_gate_packet",
            )
            selected_export_packet = po_export_preview_summary_df.reset_index(drop=True).iloc[
                export_packet_label_to_index[selected_export_packet_label]
            ].to_dict()
            export_gate_label_to_state = {
                "Needs more proof": "local_export_more_proof_needed",
                "Keep on local hold": "local_export_keep_on_hold",
                "Candidate ready only": "local_export_candidate_ready_not_po",
            }
            export_gate_label = st.selectbox(
                "Local export gate",
                options=list(export_gate_label_to_state.keys()),
                key="o_session_po_draft_export_gate_decision",
            )
            export_gate_note = st.text_input("Gate note", value="", key="o_session_po_draft_export_gate_note")
            export_gate_save_cols = st.columns([1.2, 3.2])
            if export_gate_save_cols[0].button("Save Export Gate", type="primary", key="o_session_save_po_draft_export_gate"):
                try:
                    saved = submit_po_draft_export_gate_event(
                        root=root_path,
                        export_summary_row=selected_export_packet,
                        decision_state=export_gate_label_to_state.get(export_gate_label, "local_export_more_proof_needed"),
                        decision_note=export_gate_note,
                        actor="operator_ui",
                        event_source_reference="o_ui_po_draft_export_gate",
                    )
                    build_po_draft_export_gate(root=root_path, refresh_export_preview=False)
                    st.session_state["o_recent_submit_notice"] = (
                        f"Saved local PO draft export gate for {saved.get('supplier_name', '') or saved.get('po_draft_export_preview_id', '')}."
                    )
                    st.rerun()
                except ValueError as exc:
                    st.error(f"Export gate not saved: {exc}")
            export_gate_save_cols[1].caption("Export gates stay local. They cannot create purchase orders, receiving events, or Amazon handoffs.")

        if not po_export_gate_df.empty:
            export_gate_cols = [
                col
                for col in (
                    "supplier_name",
                    "po_draft_export_preview_id",
                    "line_count",
                    "ready_line_count",
                    "blocked_line_count",
                    "export_preview_value_gbp",
                    "source_export_preview_state",
                    "latest_decision_state",
                    "export_gate_state",
                    "export_gate_reasons",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_export_gate_df.columns
            ]
            st.dataframe(po_export_gate_df[export_gate_cols], width="stretch", hide_index=True)
        if not po_export_gate_events_df.empty:
            gate_event_cols = [
                col
                for col in (
                    "event_utc",
                    "po_draft_export_preview_id",
                    "supplier_name",
                    "decision_state",
                    "expected_line_count",
                    "expected_ready_line_count",
                    "expected_blocked_line_count",
                    "decision_note",
                    "po_file_write_allowed",
                    "po_creation_allowed",
                    "purchase_commitment_allowed",
                    "receiving_allowed",
                    "send_to_amazon_allowed",
                    "creates_live_action",
                )
                if col in po_export_gate_events_df.columns
            ]
            st.dataframe(po_export_gate_events_df.tail(25)[gate_event_cols], width="stretch", hide_index=True)
        if not po_export_gate_health_df.empty:
            export_gate_health_bad = po_export_gate_health_df[
                po_export_gate_health_df.get("status", pd.Series(dtype=str)).map(
                    lambda value: _normalize_text(value).lower() != "ok"
                )
            ].copy()
            if export_gate_health_bad.empty:
                st.caption("PO draft export gate is local and safe.")
            else:
                st.warning("PO draft export gate has a blocker.")
                st.dataframe(export_gate_health_bad, width="stretch", hide_index=True)

    if not summary_df.empty:
        with st.expander("Supplier summary", expanded=False):
            st.dataframe(summary_df, width="stretch", hide_index=True)

    with st.expander("Session health", expanded=False):
        if health_df.empty:
            st.info("No health proof yet.")
        else:
            st.dataframe(health_df, width="stretch", hide_index=True)


def render_operator_ui(root: Path | None = None) -> None:
    import streamlit as st

    root_path = Path(root) if root is not None else get_o_path_contract().root
    st.set_page_config(page_title="O Flow Operator", layout="wide")
    st.markdown(_render_operator_theme_css(), unsafe_allow_html=True)
    if "o_recent_submit_notice" not in st.session_state:
        st.session_state["o_recent_submit_notice"] = ""
    if "o_recent_skipped_notice" not in st.session_state:
        st.session_state["o_recent_skipped_notice"] = ""
    if "o_recent_receiving_notice" not in st.session_state:
        st.session_state["o_recent_receiving_notice"] = ""
    if "o_recent_handoff_notice" not in st.session_state:
        st.session_state["o_recent_handoff_notice"] = ""
    if "o_recent_feeder_review_notice" not in st.session_state:
        st.session_state["o_recent_feeder_review_notice"] = ""
    if "o_recent_listing_profile_notice" not in st.session_state:
        st.session_state["o_recent_listing_profile_notice"] = ""
    if "o_recent_brand_approval_notice" not in st.session_state:
        st.session_state["o_recent_brand_approval_notice"] = ""
    if "o_feeder_last_send_rows_passes" not in st.session_state:
        st.session_state["o_feeder_last_send_rows_passes"] = []
    if "o_feeder_last_send_rows_manual_review" not in st.session_state:
        st.session_state["o_feeder_last_send_rows_manual_review"] = []
    if "o_feeder_last_send_rows_near_misses" not in st.session_state:
        st.session_state["o_feeder_last_send_rows_near_misses"] = []
    if "o_submitted_skus" not in st.session_state:
        st.session_state["o_submitted_skus"] = []
    if "o_reorder_drafts" not in st.session_state:
        st.session_state["o_reorder_drafts"] = {}

    datasets = load_operator_datasets(root=root_path)

    page_options = list(OPERATOR_PAGE_OPTIONS)
    page_labels = [label for label, _ in page_options]
    route_by_label = {label: route for label, route in page_options}
    label_by_route = {route: label for label, route in page_options}
    valid_routes = set(label_by_route)

    def _query_page_route() -> str:
        raw = ""
        try:
            raw = st.query_params.get("page", "")
            if isinstance(raw, list):
                raw = raw[0] if raw else ""
        except Exception:
            try:
                raw = st.experimental_get_query_params().get("page", [""])[0]
            except Exception:
                raw = ""
        route = _normalize_text(raw).lower().replace("-", "_")
        if route in OPERATOR_HIDDEN_PAGE_REDIRECTS:
            return OPERATOR_HIDDEN_PAGE_REDIRECTS[route]
        return route if route in valid_routes else "today"

    def _set_query_page_route(route: str) -> None:
        safe_route = route if route in valid_routes else "today"
        try:
            st.query_params["page"] = safe_route
        except Exception:
            st.experimental_set_query_params(page=safe_route)

    def _navigate_to(route: str) -> None:
        safe_route = _normalize_text(route).lower().replace("-", "_")
        if safe_route in OPERATOR_HIDDEN_PAGE_REDIRECTS:
            safe_route = OPERATOR_HIDDEN_PAGE_REDIRECTS[safe_route]
        if safe_route not in valid_routes:
            safe_route = "today"
        st.session_state["o_active_page_route"] = safe_route
        _set_query_page_route(safe_route)
        st.rerun()

    if "o_active_page_route" not in st.session_state:
        st.session_state["o_active_page_route"] = _query_page_route()
    query_route = _query_page_route()
    if query_route != st.session_state.get("o_active_page_route", "today"):
        st.session_state["o_active_page_route"] = query_route
    active_page_route = _normalize_text(st.session_state.get("o_active_page_route", "today")).lower().replace("-", "_")
    if active_page_route in OPERATOR_HIDDEN_PAGE_REDIRECTS:
        active_page_route = OPERATOR_HIDDEN_PAGE_REDIRECTS[active_page_route]
        st.session_state["o_active_page_route"] = active_page_route
    elif active_page_route not in valid_routes:
        active_page_route = "today"
        st.session_state["o_active_page_route"] = active_page_route

    _set_query_page_route(active_page_route)
    _render_operator_sidebar(
        active_page_route=active_page_route,
        label_by_route=label_by_route,
        navigate_to=_navigate_to,
    )
    active_page_label = OPERATOR_NAV_LABELS.get(active_page_route, label_by_route.get(active_page_route, "Today"))
    st.markdown(
        _operator_shell_header_html(
            active_page_label,
            OPERATOR_PAGE_DESCRIPTIONS.get(active_page_route, ""),
        ),
        unsafe_allow_html=True,
    )

    if active_page_route == "today":
        _render_today_page(datasets, _navigate_to)

    if active_page_route == "reorder":
        st.subheader("Old Reorder Workbench")
        st.warning(
            "This is the old dense supplier table. Use Restocking for the normal buying review."
        )
        show_legacy_reorder = st.checkbox(
            "Show old dense reorder table",
            value=False,
            key="o_show_legacy_reorder_workbench",
        )
        if not show_legacy_reorder:
            st.info("The cleaner Restocking page is the main working path. Nothing runs from this old page unless you open it and press its send controls.")
            st.stop()
        reorder_df = build_reorder_input_df(datasets)
        st.caption(
            "Work one supplier at a time. Fill in Qty and Price only for the rows you are sending."
        )
        if reorder_df.empty:
            st.info("No reorder rows yet.")
        else:
            reorder_df["_supplier_label"] = reorder_df["supplier_name"].map(_supplier_label)
            supplier_options = ["All suppliers", *sorted(reorder_df["_supplier_label"].unique().tolist())]

            controls_a, controls_b, controls_c, controls_d, controls_e = st.columns([1, 1, 1, 2, 2])
            include_wait = controls_a.checkbox("Show Wait", value=False, key="o_reorder_include_wait")
            include_snoozed = controls_b.checkbox("Show Snoozed", value=False, key="o_reorder_include_snoozed")
            include_held = controls_c.checkbox("Show Held", value=False, key="o_reorder_include_held")
            supplier_filter = controls_d.selectbox(
                "Supplier",
                options=supplier_options,
                index=0,
                key="o_reorder_supplier_filter",
            )
            search_text = controls_e.text_input("Search SKU / Title / ASIN", value="", key="o_reorder_search")

            _render_price_list_lookup_panel(datasets, supplier_filter=supplier_filter)

            filtered_df = filter_reorder_rows(
                reorder_df,
                include_wait=include_wait,
                include_snoozed=include_snoozed,
                include_held=include_held,
                supplier_filter=supplier_filter,
                search_text=search_text,
            )
            submitted_skus = {str(sku).strip() for sku in st.session_state.get("o_submitted_skus", []) if str(sku).strip()}
            if submitted_skus and not filtered_df.empty:
                filtered_df = filtered_df[~filtered_df["seller_sku"].astype(str).str.strip().isin(submitted_skus)].copy()

            recent_notice = _normalize_text(st.session_state.get("o_recent_submit_notice", ""))
            if recent_notice:
                st.markdown(_render_inline_notice(recent_notice), unsafe_allow_html=True)
            skipped_notice = _normalize_text(st.session_state.get("o_recent_skipped_notice", ""))
            if skipped_notice:
                st.markdown(_render_inline_notice(skipped_notice), unsafe_allow_html=True)

            if filtered_df.empty:
                st.info("No rows match the current view.")
            else:
                total_rows = len(filtered_df.index)
                total_suppliers = filtered_df["_supplier_label"].nunique()
                st.caption(f"Showing {total_rows} rows across {total_suppliers} suppliers.")

                grouped = filtered_df.groupby("_supplier_label", sort=True)
                for supplier_label, supplier_df in grouped:
                    supplier_df = supplier_df.drop(columns=["_supplier_label"], errors="ignore").reset_index(drop=True)

                    ready_count = int((supplier_df["row_status"].astype(str).str.lower() == "ready").sum())
                    st.markdown(f"### {supplier_label}")
                    st.caption(f"Rows: {len(supplier_df.index)} | Ready: {ready_count}")
                    merged_submit_df = _render_reorder_supplier_cards(
                        supplier_df,
                        supplier_label=supplier_label,
                    )

                    submit_col_a, submit_col_b = st.columns([1, 3])
                    send_label = f"Send {supplier_label}"
                    send_key = f"o_reorder_send_supplier_{_supplier_key_fragment(supplier_label)}"
                    send_supplier_clicked = submit_col_a.button(send_label, type="primary", key=send_key)
                    submit_col_b.markdown("")

                    if send_supplier_clicked:
                        result = submit_reorder_batch(
                            root=root_path,
                            rows_df=merged_submit_df,
                            actor="operator_ui",
                            source_reference=f"o_ui_supplier_batch:{supplier_label}",
                        )
                        if result["events_applied"] > 0 and result.get("applied_skus"):
                            submitted_skus_now = [str(sku).strip() for sku in result["applied_skus"] if str(sku).strip()]
                            existing_skus = [str(sku).strip() for sku in st.session_state.get("o_submitted_skus", [])]
                            st.session_state["o_submitted_skus"] = [*existing_skus, *submitted_skus_now]
                            applied_rows = merged_submit_df[
                                merged_submit_df["seller_sku"].astype(str).str.strip().isin(submitted_skus_now)
                            ].to_dict("records")
                            _clear_reorder_drafts(st.session_state, applied_rows)
                        st.session_state["o_recent_submit_notice"] = (
                            f"{supplier_label}: sent {result['events_applied']} row"
                            f"{'' if result['events_applied'] == 1 else 's'}."
                        )
                        st.session_state["o_recent_skipped_notice"] = _format_skipped_restock_rows(result["skipped_rows"])
                        st.rerun()

    if active_page_route == "restock_session":
        _render_restock_session_tab(root_path, datasets)

    if active_page_route == "price_list_queue":
        _render_price_list_queue_tab(root_path)

    if active_page_route == "new_product_review":
        _render_new_product_review_tab(root_path)

    if active_page_route == "product_listing_profile_review":
        _render_product_listing_profile_review_tab(root_path)
        _render_amazon_listing_draft_lane(root_path, datasets)

    if active_page_route == "brand_approval_queue":
        _render_brand_approval_queue_tab(root_path)

    if active_page_route == "product_db":
        render_product_database_ui(root=root_path)

    if active_page_route == "product_db_edit":
        render_product_database_edit_ui(root=root_path)

    if active_page_route == "repricer_tracker":
        render_repricing_tracker_ui(root=root_path)

    if active_page_route == "decision_log":
        st.subheader("Decision Log")
        st.dataframe(datasets["restock_decisions_log"], width="stretch", hide_index=True)

    if active_page_route == "po_drafts":
        render_po_drafts_review_tab(datasets)

    if active_page_route == "receiving":
        st.subheader("Receiving")
        receiving_notice = _normalize_text(st.session_state.get("o_recent_receiving_notice", ""))
        if receiving_notice:
            st.markdown(_render_inline_notice(receiving_notice), unsafe_allow_html=True)

        st.caption("Record stock that has arrived.")
        st.subheader("Ordered Stock")
        st.dataframe(datasets["ordered_stock_state"], width="stretch", hide_index=True)
        st.subheader("Receiving Holds")
        st.dataframe(datasets["receiving_event_holds"], width="stretch", hide_index=True)

        with st.form("receiving_event_form"):
            po_id = st.text_input("PO ID")
            po_line_id = st.text_input("PO Line ID")
            seller_sku = st.text_input("SKU", key="receiving_seller_sku")
            received_qty = st.text_input("Received Qty")
            warehouse_ref = st.text_input("Warehouse Ref")
            note = st.text_input("Note", value="")
            submitted = st.form_submit_button("Record Receipt")

        if submitted:
            row = submit_receiving_event(
                root=root_path,
                po_id=po_id,
                po_line_id=po_line_id,
                seller_sku=seller_sku,
                received_qty=received_qty,
                warehouse_ref=warehouse_ref,
                note=note,
                actor="operator_ui",
            )
            st.session_state["o_recent_receiving_notice"] = f"Receipt recorded for {seller_sku or row['event_id']}."
            st.rerun()

    if active_page_route == "send_to_amazon":
        st.subheader("Send to Amazon")
        handoff_notice = _normalize_text(st.session_state.get("o_recent_handoff_notice", ""))
        if handoff_notice:
            st.markdown(_render_inline_notice(handoff_notice), unsafe_allow_html=True)

        st.caption("Record stock that is ready to send in.")
        st.subheader("Queue")
        st.dataframe(datasets["send_to_amazon_queue"], width="stretch", hide_index=True)
        st.subheader("Handoff Log")
        st.dataframe(datasets["send_to_amazon_handoff_log"], width="stretch", hide_index=True)
        st.subheader("Handoff Holds")
        st.dataframe(datasets["send_to_amazon_handoff_holds"], width="stretch", hide_index=True)

        with st.form("handoff_event_form"):
            po_id = st.text_input("PO ID", key="handoff_po_id")
            po_line_id = st.text_input("PO Line ID", key="handoff_po_line_id")
            seller_sku = st.text_input("SKU", key="handoff_seller_sku")
            handoff_qty = st.text_input("Handoff Qty")
            shipment_ref = st.text_input("Shipment Ref")
            handoff_status = st.selectbox("Status", options=list(HANDOFF_STATUSES))
            note = st.text_input("Note", value="", key="handoff_note")
            submitted = st.form_submit_button("Record Handoff")

        if submitted:
            row = submit_send_handoff_event(
                root=root_path,
                po_id=po_id,
                po_line_id=po_line_id,
                seller_sku=seller_sku,
                handoff_qty=handoff_qty,
                shipment_ref=shipment_ref,
                handoff_status=handoff_status,
                note=note,
                actor="operator_ui",
            )
            st.session_state["o_recent_handoff_notice"] = f"Handoff recorded for {seller_sku or row['event_id']}."
            st.rerun()


def main() -> None:
    render_operator_ui()


if __name__ == "__main__":
    main()
